from __future__ import annotations
import re, time, threading, logging, csv, os
from dataclasses import dataclass
from typing import Optional, Dict, Tuple, Deque
from collections import deque
from datetime import datetime

# ==== Your existing primitives (from the files you shared) =====================================
from grok_produce.structured.api_client.v2_bootstrap_client import quantize_price
from grok_produce.structured.proof_of_concept_for_order_placing import _req
from grok_produce.structured.proof_of_concept_for_order_placing import MARGIN_COIN, PRODUCT_TYPE  # e.g., USDT / USDT-FUTURES

from grok_produce.structured.api_client.self_cancel_timer import schedule_self_cancel  # threading.Timer helper

from grok_produce.structured.api_client.v2_on_candle_close_tp_sl import register_delayed_bracket, on_candle_close, delayed_brackets

from grok_produce.structured.websocket.bitget_live_klines import get_5m_from, get_4h_from
# ===============================================================================================


OrderId = str

# ----------------------------- config / I/O ----------------------------------------------------
EXIT_LOG_FILE = "exit_log.csv"      # TP/SL hits appended here (CSV)
LOSS_LOG_PREFIX = "loss_log_"       # keep compatibility with your earlier naming
TP_LOG_PREFIX = "tp_log_"           # optional separate TP stream if you want


# ----------------------------- duration parsing -----------------------------------------------
def _parse_duration_to_ms(s: str) -> int:
    """
    '5m' -> 5 * 60 * 1000 ; supports '30s', '5m', '15m', '1h', '1d' etc.
    """
    if not s:
        return 0
    m = re.fullmatch(r"\s*(\d+)\s*([smhdSMHD])\s*", s)
    if not m:
        raise ValueError("duration must look like '5m', '15m', '1h', '30s', '1d'")
    n = int(m.group(1))
    unit = m.group(2).lower()
    mult = {"s": 1000, "m": 60_000, "h": 3_600_000, "d": 86_400_000}[unit]
    return n * mult


# ----------------------------- Bitget helpers (detail / cancel) -------------------------------
def _get_order_detail(symbol: str, *, order_id: Optional[str] = None, client_oid: Optional[str] = None) -> dict:
    """
    POST /api/v2/mix/order/detail (accepts orderId or clientOid)
    """
    body = {"symbol": symbol, "productType": PRODUCT_TYPE}
    if order_id:
        body["orderId"] = order_id
    if client_oid and "orderId" not in body:
        body["clientOid"] = client_oid
    return _req("POST", "/api/v2/mix/order/detail", body=body)

def _is_done(symbol: str, order_id: Optional[str], client_oid: Optional[str]) -> bool:
    """
    Returns True if the order is no longer working (filled, canceled, etc.)
    """
    try:
        res = _get_order_detail(symbol, order_id=order_id, client_oid=client_oid)
        data = res.get("data") or {}
        state = str(data.get("state") or data.get("status") or "").lower()
        return state in {"filled", "canceled", "cancelled", "closed", "finished", "rejected"}
    except Exception as e:
        logging.error(f"Exception Raised in _is_done: {e}")
        return False

def _cancel_order(symbol: str, *, order_id: Optional[str], client_oid: Optional[str]):
    """
    POST /api/v2/mix/order/cancel-order
    """
    body = {"symbol": symbol, "productType": PRODUCT_TYPE}
    if order_id:
        body["orderId"] = order_id
    if client_oid and "orderId" not in body:
        body["clientOid"] = client_oid
    return _req("POST", "/api/v2/mix/order/cancel-order", body=body)


# ----------------------------- exit event bus (for logging & accounting) ----------------------
@dataclass
class ExitEvent:
    symbol: str
    exit_type: str     # "TP" or "SL"
    price: float
    ts: float          # epoch seconds
    meta: dict

_EXIT_EVENTS: Deque[ExitEvent] = deque(maxlen=4096)  # candle-close thread -> main loop


# ----------------------------- candle-close coordinator ---------------------------------------
class _CandleCloseCoordinator:
    """
    Maintains a single background thread that, for each (symbol, timeframe) we care about,
    detects candle close and calls on_candle_close(symbol, close_price) once per new bucket.
    If on_candle_close() returns a hit, we:
      - append an ExitEvent to _EXIT_EVENTS
      - write to CSV
      - log via logging.info
    """
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._last_seen: Dict[tuple[str, str], int] = {}
        self._watch: Dict[tuple[str, str], bool] = {}

    def ensure_running(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="CandleCloseCoordinator", daemon=True)
            self._thread.start()

    def watch(self, symbol: str, timeframe: str):
        with self._lock:
            self._watch[(symbol, timeframe)] = True

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as e:
                logging.exception(f"[CandleCloseCoordinator] tick failed: {e}")
            self._stop.wait(1.0)  # 1s cadence

    def _tick(self):
        with self._lock:
            to_check = list(self._watch.keys())

        for symbol, tf in to_check:
            # pull live window from your global manager:
            if tf == "5m":
                df = get_5m_from(symbol)
            elif tf == "4h":
                df = get_4h_from(symbol)
            else:
                continue

            if df is None or df.empty:
                continue

            last_t = int(df.index[-1])
            last_c = float(df.iloc[-1]["c"])
            key = (symbol, tf)
            prev_t = self._last_seen.get(key)
            first_seen = prev_t is None
            if first_seen:
                logging.info(f"[WATCH] first bucket seen for {symbol} {tf} t={last_t}")

            # fire only once per new bucket
            if prev_t is None or last_t > prev_t:
                self._last_seen[key] = last_t

                # only if there's an active bracket
                br = delayed_brackets.get(symbol)
                if not br or not br.active:
                    continue

                try:
                    logging.debug(f"[BRACKET] eval {symbol} {tf}: close={last_c}, "
                                  f"active={bool(br and br.active)} "
                                  f"targets={{tp:{getattr(br,'tp',None)}, sl:{getattr(br,'sl',None)}, entry:{getattr(br,'entry_price',None)}}}")
                    res = on_candle_close(symbol, last_c)  # may trigger close
                except Exception as e:
                    logging.exception(f"[BRACKET] on_candle_close() crashed for {symbol} {tf}: {e}")
                    continue

                # res = on_candle_close(symbol, last_c)   # returns {"symbol", "exit": "TP|SL", "price"} or None
                if res:
                    evt = ExitEvent(
                        symbol=res["symbol"],
                        exit_type=res["exit"],
                        price=float(res["price"]),
                        ts=time.time(),
                        meta={"timeframe": tf, "close_price": last_c, "bucket": last_t},
                    )
                    _EXIT_EVENTS.append(evt)
                    _write_exit_csv(evt)
                    logging.info(f"[EXIT] {evt.exit_type} hit on {evt.symbol} @ {evt.price:.6f} (tf={tf})")


_COORD = _CandleCloseCoordinator()


def _write_exit_csv(evt: ExitEvent):
    exists = os.path.exists(EXIT_LOG_FILE)
    with open(EXIT_LOG_FILE, "a", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["timestamp_iso", "symbol", "exit_type", "price", "timeframe", "bucket_ms", "close_price"])
        w.writerow([
            datetime.fromtimestamp(evt.ts).isoformat(timespec="seconds"),
            evt.symbol,
            evt.exit_type,
            f"{evt.price:.8f}",
            evt.meta.get("timeframe"),
            evt.meta.get("bucket"),
            f"{evt.meta.get('close_price', float('nan')):.8f}",
        ])


# ----------------------------- public entry: place_limit_long ---------------------------------
@dataclass
class PlaceResult:
    apiResponse: dict
    orderId: Optional[str]
    clientOid: Optional[str]
    expires_at_ms: int
    tif: str
    price: str
    timer_started: bool
    watcher_started: bool


def place_limit_long(
    symbol: str,
    size: str,
    price: str | float,
    *,
    duration: str = "5m",            # e.g. "5m", "15m", "1h", "30s"
    tif: str = "gtc",                # "gtc", "post_only", "ioc", "fok"
    client_oid: str | None = None,
    auto_cancel: bool = False,
    # on-close bracket defaults (overridable per call)
    tp_pct: float = 0.01,
    sl_pct: float = 0.02,
    watch_timeframe: str = "5m",
) -> PlaceResult:
    """
    1) Places a LIMIT Buy (open) on Bitget MIX v2.
    2) Optionally starts a self-cancel timer (for GTC/post_only) based on 'duration'.
    3) Starts a fill-watcher; when filled, registers an on-close TP/SL bracket and
       ensures the candle-close coordinator is running & watching (symbol, timeframe).
    """
    # ----- 1) place the limit ---------------------------------------------------
    try:
        qprice = quantize_price(symbol, price)
    except NameError:
        qprice = str(price)

    body = {
        "symbol": symbol,
        "productType": PRODUCT_TYPE,
        "marginMode": "isolated",
        "marginCoin": MARGIN_COIN,
        "size": str(size),
        "price": str(qprice),
        "side": "buy",
        "tradeSide": "open",
        "orderType": "limit",
        "force": tif.lower(),
    }
    if client_oid:
        body["clientOid"] = client_oid

    res = _req("POST", "/api/v2/mix/order/place-order", body=body)
    data = res.get("data") or {}
    order_id: Optional[str] = data.get("orderId")
    coid: Optional[str] = data.get("clientOid") or client_oid

    ttl_ms = _parse_duration_to_ms(duration) if duration else 0
    expires_at_ms = int(time.time() * 1000) + ttl_ms if ttl_ms else 0

    # ----- 2) optional TTL timer ------------------------------------------------
    timer_started = False
    if auto_cancel and ttl_ms and body["force"] in ("gtc", "post_only"):
        timeout_s = ttl_ms / 1000.0
        schedule_self_cancel(
            order_id or coid,
            timeout_s=timeout_s,
            cancel=lambda oid: _cancel_order(symbol, order_id=order_id, client_oid=coid),
            is_done=lambda oid: _is_done(symbol, order_id=order_id, client_oid=coid),
            name=f"SC-{symbol}-{order_id or coid}",
        )
        timer_started = True


    # ----- 3) fill-watcher -> delayed bracket -> candles loop -------------------
    def _fill_watcher():
        while True:
            if _is_done(symbol, order_id=order_id, client_oid=coid):
                break
            time.sleep(0.3)

        # Fetch final detail to detect fill price; fall back to limit price if not present
        avg_fill = None
        try:
            det = _get_order_detail(symbol, order_id=order_id, client_oid=coid).get("data") or {}
            for k in ("fillPrice", "avgPrice", "priceAvg", "fillAvgPrice", "dealAvgPrice"):
                if det.get(k) is not None:
                    avg_fill = float(det[k])
                    break
        except Exception:
            pass
        entry_price = float(avg_fill if avg_fill is not None else qprice)
        logging.info(f"[FILL] {symbol} detected filled; entry_price={entry_price:.8f}")
        logging.info(f"[BRACKET] registering {symbol}: tp_pct={tp_pct}, sl_pct={sl_pct}")
        register_delayed_bracket(symbol, entry_price=entry_price, tp_pct=tp_pct, sl_pct=sl_pct)
        b = delayed_brackets.get(symbol)
        logging.info(f"[BRACKET] registered {symbol}: active={bool(b and b.active)} entry={getattr(b,'entry_price',None)} tp={getattr(b,'tp',None)} sl={getattr(b,'sl',None)}")
        # logging.info(f"[BRACKET] registering {symbol}: entry={entry_price:.8f} tp_pct={tp_pct} sl_pct={sl_pct}")
        # register_delayed_bracket(symbol, entry_price=entry_price, tp_pct=tp_pct, sl_pct=sl_pct)
        logging.info(f"[BRACKET] registered {symbol}: tp={getattr(delayed_brackets.get(symbol),'tp',None)} sl={getattr(delayed_brackets.get(symbol),'sl',None)}")
        # register_delayed_bracket(symbol, entry_price=entry_price, tp_pct=tp_pct, sl_pct=sl_pct)

        _COORD.ensure_running()
        _COORD.watch(symbol, watch_timeframe)

    watcher_started = False
    if order_id or coid:
        t = threading.Thread(target=_fill_watcher, name=f"FillWatcher-{symbol}-{order_id or coid}", daemon=True)
        t.start()
        watcher_started = True

    return PlaceResult(
        apiResponse=res,
        orderId=order_id,
        clientOid=coid,
        expires_at_ms=expires_at_ms,
        tif=body["force"],
        price=str(qprice),
        timer_started=timer_started,
        watcher_started=watcher_started,
    )


def dump_bracket(symbol: str):
    b = delayed_brackets.get(symbol)
    if not b:
        logging.info(f"[BRACKET] {symbol}: no bracket")
        return
    logging.info(f"[BRACKET] {symbol}: active={b.active} entry={getattr(b,'entry_price',None)} "
                 f"tp={getattr(b,'tp',None)} sl={getattr(b,'sl',None)}")

def poke_eval_now(symbol: str, timeframe: str = "5m"):
    # Manually evaluate current close once (useful for debugging)
    if timeframe == "5m":
        df = get_5m_from(symbol)
    elif timeframe == "4h":
        df = get_4h_from(symbol)
    else:
        logging.warning(f"[BRACKET] poke_eval_now: unsupported tf={timeframe}")
        return
    if df is None or df.empty:
        logging.warning(f"[BRACKET] poke_eval_now: no data for {symbol} {timeframe}")
        return
    last_c = float(df.iloc[-1]["c"])
    try:
        res = on_candle_close(symbol, last_c)
        logging.info(f"[BRACKET] poke_eval_now res for {symbol} {timeframe}: {res}")
    except Exception as e:
        logging.exception(f"[BRACKET] poke_eval_now crashed for {symbol} {timeframe}: {e}")

# ----------------------------- “handle_sl_if_any” compatibility -------------------------------
#
# Your loop calls:
#   current_balance, closed = handle_sl_if_any(symbol, open_positions, current_balance, df_5m, idx, strategy_name, skip_day)
#
# We implement it to consume ExitEvents (TP/SL) and write logs compatible with your previous format.
#
_PROCESSED_SL: set[str] = set()  # kept for compatibility with your existing state (o.id-like); we key by symbol here.

def handle_sl_if_any(symbol: str,
                     open_positions: dict,
                     current_balance: float,
                     df_5m,
                     idx: int,
                     strategy_name: str,
                     skip_day) -> Tuple[float, bool]:
    """
    Consumes a TP/SL event (if any) for `symbol`, updates balance/logs, and closes the position in open_positions.
    Returns (updated_balance, closed_bool).
    """
    closed = False

    # Drain any pending events for this symbol (keep only the most recent)
    pending: list[ExitEvent] = []
    try:
        # Non-blocking drain of events for 'symbol'
        n = len(_EXIT_EVENTS)
        for _ in range(n):
            evt = _EXIT_EVENTS.popleft()
            if evt.symbol == symbol:
                pending.append(evt)
            else:
                _EXIT_EVENTS.append(evt)  # put back for others
    except Exception:
        pass

    if not pending:
        return current_balance, False

    # take the latest event
    evt = pending[-1]
    exit_price = float(evt.price)
    exit_type = evt.exit_type  # "TP" | "SL"

    # compute pnl if we can
    size = open_positions.get(symbol, {}).get("amount") or 0.0
    entry = open_positions.get(symbol, {}).get("entry_price") or 0.0
    pnl = 0.0
    try:
        size = float(size)
        entry = float(entry)
        if size and entry:
            # long position
            pnl = (exit_price - entry) * size
    except Exception:
        pass

    pos_return = pnl / float(max(current_balance, 1e-9))
    new_balance = current_balance + pnl

    # write logs (CSV compatible with your earlier shape)
    loss_log = [{
        'symbol': symbol,
        'strategy': strategy_name,
        'timestamp': df_5m.iloc[idx]['timestamp'] if (df_5m is not None and len(df_5m) and 'timestamp' in df_5m.columns) else datetime.utcfromtimestamp(evt.ts).isoformat(),
        'entry_price': entry,
        'exit_price': exit_price,
        'return': pos_return,
        'balance': new_balance,
        'stop_loss_hit': (exit_type == "SL"),
        'take_profit_hit': (exit_type == "TP"),
    }]

    try:
        import pandas as pd
        # legacy loss_log_*.csv stream (works for TP too – has fields to distinguish)
        pd.DataFrame(loss_log).to_csv(f'{LOSS_LOG_PREFIX}{strategy_name}.csv', mode='a', index=False, header=not os.path.exists(f'{LOSS_LOG_PREFIX}{strategy_name}.csv'))

        # optional separate TP stream
        if exit_type == "TP":
            pd.DataFrame(loss_log).to_csv(f'{TP_LOG_PREFIX}{strategy_name}.csv', mode='a', index=False, header=not os.path.exists(f'{TP_LOG_PREFIX}{strategy_name}.csv'))

        logging.info(f"[{exit_type}] {symbol} exit at {exit_price}. Δ={pnl:.4f}; new balance={new_balance:.2f}")
        skip_day[symbol] = 1
    except Exception as e:
        logging.error(f"Failed writing TP/SL logs: {e}")

    # consume/close
    _PROCESSED_SL.add(symbol)   # keyed by symbol for compatibility
    if symbol in open_positions:
        del open_positions[symbol]
    closed = True

    return new_balance, closed


# ----------------------------- restart recovery -----------------------------------------------
def recover_open_positions_and_watch_old(symbols: list[str],
                                     watch_timeframe: str = "5m",
                                     default_tp_pct: float = 0.01,
                                     default_sl_pct: float = 0.02):
    """
    On process start, call this to discover any existing open LONG positions and pending working orders,
    recreate delayed brackets, and resume candle-close monitoring.
    """
    for symbol in symbols:
        # 1) detect open long position (Bitget V2 MIX)
        entry_price = None
        has_long = False
        try:
            # Try single-position first (if supported); otherwise fall back to all-positions.
            resp = _req("POST", "/api/v2/mix/position/single-position",
                        body={"symbol": symbol, "productType": PRODUCT_TYPE})
            data = (resp or {}).get("data") or {}
            for k in ("avgOpenPrice", "avgPrice", "openAvgPrice", "openPriceAvg"):
                if data.get(k) is not None:
                    entry_price = float(data[k]); break
            # Some APIs expose size or hold amount
            long_sz = float(data.get("total") or data.get("holdAmount") or data.get("longQty") or 0.0)
            has_long = long_sz > 0
        except Exception:
            # fallback – optional; if this fails silently, we just won't recreate a bracket.
            try:
                resp = _req("POST", "/api/v2/mix/position/all-position",
                            body={"productType": PRODUCT_TYPE})
                arr = (resp or {}).get("data") or []
                for row in arr:
                    if str(row.get("symbol")) == symbol:
                        for k in ("avgOpenPrice", "avgPrice", "openAvgPrice", "openPriceAvg"):
                            if row.get(k) is not None:
                                entry_price = float(row[k]); break
                        long_sz = float(row.get("total") or row.get("holdAmount") or row.get("longQty") or 0.0)
                        has_long = long_sz > 0
                        break
            except Exception:
                pass

        if has_long and entry_price:
            # recreate bracket & watch
            register_delayed_bracket(symbol, entry_price=entry_price,
                                     tp_pct=default_tp_pct, sl_pct=default_sl_pct)
            _COORD.ensure_running()
            _COORD.watch(symbol, watch_timeframe)
            logging.info(f"[RECOVER] watching live bracket for {symbol} (entry={entry_price})")

        # 2) detect working limit orders that might need TTL self-cancel (optional)
        try:
            # If you store clientOids, you could rebuild timers too; here we just resume watching price.
            pass
        except Exception:
            pass


def _select_long_row(row_or_list):
    """
    Bitget v2 may return:
      - dict  (single position)
      - list[dict] (multiple entries, hedge mode or internal variants)
    Pick the long-side row with nonzero size if present; else None.
    """
    if not row_or_list:
        return None
    if isinstance(row_or_list, dict):
        # If hedge mode but single dict: ensure it's long or has size
        side = str(row_or_list.get("holdSide") or row_or_list.get("posSide") or "").lower()
        size_fields = ("total","holdAmount","longQty","totalSize","available","availableSize","size")
        any_size = any(float(row_or_list.get(k) or 0) > 0 for k in size_fields)
        if side in ("", "long") and any_size:
            return row_or_list
        # fall through: no long found
        return None

    if isinstance(row_or_list, list):
        # Prefer long side with size>0
        for r in row_or_list:
            side = str(r.get("holdSide") or r.get("posSide") or "").lower()
            if side not in ("", "long"):
                continue
            size_fields = ("total","holdAmount","longQty","totalSize","available","availableSize","size")
            if any(float(r.get(k) or 0) > 0 for k in size_fields):
                return r
        # As a fallback, pick the first with any size>0
        for r in row_or_list:
            size_fields = ("total","holdAmount","longQty","totalSize","available","availableSize","size")
            if any(float(r.get(k) or 0) > 0 for k in size_fields):
                return r
        return None

    return None


def _get_single_position(symbol: str):
    try:
        resp = _req("GET", "/api/v2/mix/position/single-position", params={
            "symbol": symbol,
            "productType": PRODUCT_TYPE,  # e.g. "USDT-FUTURES"
            "marginCoin": MARGIN_COIN,    # e.g. "USDT"
        }) or {}
        data = resp.get("data")
        return _select_long_row(data)
    except Exception as e:
        logging.debug(f"[RECOVER] single-position GET failed {symbol}: {e}")
        return None


def _get_all_positions() -> list[dict]:
    try:
        resp = _req("GET", "/api/v2/mix/position/all-position", params={
            "productType": PRODUCT_TYPE,
            "marginCoin": MARGIN_COIN,
        }) or {}
        data = resp.get("data")
        # ensure list
        return data if isinstance(data, list) else ([] if data in (None, "") else [data])
    except Exception as e:
        logging.debug(f"[RECOVER] all-position GET failed: {e}")
        return []


def _extract_entry_and_size(row_or_list) -> tuple[float|None, float|None]:
    row = _select_long_row(row_or_list)
    if not isinstance(row, dict):
        return None, None

    entry = None
    for k in ("avgOpenPrice","avgPrice","openAvgPrice","openPriceAvg","holdAvgPrice","priceAvg"):
        v = row.get(k)
        if v not in (None, "", "0", 0):
            try: entry = float(v); break
            except: pass

    size = None
    for k in ("total","holdAmount","longQty","totalSize","available","availableSize","size"):
        v = row.get(k)
        if v not in (None, "", "0", 0):
            try: size = float(v); break
            except: pass

    # If hedge mode and side is short, ignore
    side = str(row.get("holdSide") or row.get("posSide") or "").lower()
    if side and side not in ("", "long"):
        return None, None

    return entry, size


def recover_open_positions_and_watch(symbols: list[str],
                                     watch_timeframe: str = "5m",
                                     default_tp_pct: float = 0.01,
                                     default_sl_pct: float = 0.02):
    for symbol in symbols:
        row_single = _get_single_position(symbol)
        logging.info(f"[RECOVER] {symbol}: raw(single)={row_single}")

        entry_price, size = _extract_entry_and_size(row_single)

        if not (entry_price and size and size > 0):
            allpos = _get_all_positions()
            cand_all = None
            for r in allpos:
                if str(r.get("symbol")) == symbol:
                    cand_all = r
                    break
            logging.info(f"[RECOVER] {symbol}: raw(all)={cand_all}")
            entry_price, size = _extract_entry_and_size(cand_all)

        if entry_price and size and size > 0:
            logging.info(f"[RECOVER] {symbol}: LONG detected size={size} entry={entry_price}")
            register_delayed_bracket(symbol, entry_price=entry_price,
                                     tp_pct=default_tp_pct, sl_pct=default_sl_pct)
            b = delayed_brackets.get(symbol)
            logging.info(f"[RECOVER] {symbol}: bracket active={bool(b and b.active)} tp={b.tp} sl={b.sl}")
            _COORD.ensure_running()
            _COORD.watch(symbol, watch_timeframe)
        else:
            logging.info(f"[RECOVER] {symbol}: no open long found")


def force_register_bracket_from_position(symbol: str, tf: str = "5m",
                                         tp_pct: float = 0.01, sl_pct: float = 0.02):
    row = _get_single_position(symbol)
    if row is None:
        for r in _get_all_positions():
            if str(r.get("symbol")) == symbol:
                row = r
                break

    entry_price, size = _extract_entry_and_size(row)
    if not (entry_price and size and size > 0):
        logging.error(f"[FORCE] {symbol}: no open long to attach")
        return

    logging.info(f"[FORCE] {symbol}: attach bracket entry={entry_price} tp%={tp_pct} sl%={sl_pct}")
    register_delayed_bracket(symbol, entry_price=entry_price, tp_pct=tp_pct, sl_pct=sl_pct)
    _COORD.ensure_running()
    _COORD.watch(symbol, tf)
    dump_bracket(symbol)


def _position_map_long() -> dict[str, dict]:
    out = {}
    for r in _get_all_positions():
        try:
            if str(r.get("symbol") or "") == "":
                continue
            side = str(r.get("holdSide") or r.get("posSide") or "").lower()
            # only track long side
            if side and side not in ("", "long"):
                continue
            # any positive size field?
            size = None
            for k in ("total","holdAmount","longQty","totalSize","available","availableSize","size"):
                v = r.get(k)
                if v not in (None, "", "0", 0):
                    size = float(v); break
            if size and size > 0:
                out[str(r["symbol"])] = r
        except Exception:
            pass
    return out

def audit_and_fix_brackets(symbols: list[str],
                           default_tp_pct: float = 0.01,
                           default_sl_pct: float = 0.02,
                           tf: str = "5m"):
    live = _position_map_long()
    for s in symbols:
        pos = live.get(s)
        b = delayed_brackets.get(s)
        if pos:
            # ensure bracket exists & is complete
            e, sz = _extract_entry_and_size(pos)
            if not (e and sz and sz > 0):
                continue
            if (b is None) or (not b.active):
                logging.info(f"[AUDIT] {s}: missing bracket → creating (entry={e})")
                register_delayed_bracket(s, entry_price=e,
                                         tp_pct=default_tp_pct,
                                         sl_pct=default_sl_pct)
                _COORD.ensure_running(); _COORD.watch(s, tf)
                dump_bracket(s)
            else:
                # fill in tp/sl if missing
                if getattr(b, "tp", None) is None or getattr(b, "sl", None) is None:
                    logging.info(f"[AUDIT] {s}: bracket incomplete → recomputing tp/sl from entry={b.entry_price or e}")
                    register_delayed_bracket(s, entry_price=(b.entry_price or e),
                                             tp_pct=default_tp_pct,
                                             sl_pct=default_sl_pct)
        else:
            # no live pos; deactivate any stale bracket
            if b and b.active:
                logging.info(f"[AUDIT] {s}: no live position → deactivating stale bracket")
                b.active = False