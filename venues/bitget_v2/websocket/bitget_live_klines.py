
# bitget_live_klines.py
# -------------------------------------------------------------
# A drop-in manager that:
#  - Cold-starts by REST backfilling per (symbol, timeframe)
#  - Opens a WebSocket and keeps appending/updating candles
#  - Exposes get_5m_from(symbol) / get_4h_from(symbol) to match
#    your current client usage (no start_date needed).
#  - Thread-safe merging, auto-reconnect, and optional gap-fill.
#
# Requirements: pandas, requests, websocket-client
#   pip install pandas requests websocket-client
#
# IMPORTANT:
# Bitget has multiple API business lines (SPOT/UTA/MIX) and versions (v2/v3).
# The defaults here target **Futures (MIX) v2** documented at:
#   GET /api/v2/mix/market/candles
# and WebSocket at:
#   wss://ws.bitget.com/mix/v1/stream
# If you run UTA v3 instead, see the notes at the bottom for how to configure.
# -------------------------------------------------------------

from __future__ import annotations

import json
import re
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple
import requests
import pandas as pd
from websocket import WebSocketApp
import websocket
# websocket.enableTrace(True)  # VERY verbose; disable in prod
# -------------------- Utilities --------------------

_TIMEFRAME_TO_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "12h": 43200,
    "1d": 86400,
}

def timeframe_seconds(tf: str) -> int:
    if tf not in _TIMEFRAME_TO_SECONDS:
        raise ValueError(f"Unsupported timeframe: {tf}")
    return _TIMEFRAME_TO_SECONDS[tf]

def floor_to_bucket_start(ts_ms: int, tf: str) -> int:
    # Return bucket start in milliseconds
    sec = timeframe_seconds(tf)
    return (ts_ms // (sec * 1000)) * (sec * 1000)

def _now_ms() -> int:
    return int(time.time() * 1000)

# -------------------- Config dataclass --------------------

@dataclass
class BitgetEndpoints:
    # REST: return a fully-qualified URL and params for a kline request
    def rest_kline_params(self, symbol: str, timeframe: str, limit: int) -> Tuple[str, Dict]:
        base = self.rest_base.rstrip("/")
        gran = self.timeframe_to_granularity.get(timeframe, timeframe)
        params = {
            self.symbol_param: symbol,
            self.granularity_param: gran,
            "limit": limit,
        }
        if self.product_type_param and self.product_type_value:
            params[self.product_type_param] = self.product_type_value
        return f"{base}{self.rest_path}", params

    # ---- Defaults for MIX v2 futures ----
    ws_url: str = "wss://ws.bitget.com/mix/v1/stream"
    rest_base: str = "https://api.bitget.com"
    rest_path: str = "/api/v2/mix/market/candles"

    # Parameter names (tune to your API flavor)
    symbol_param: str = "symbol"
    granularity_param: str = "granularity"
    product_type_param: Optional[str] = "productType"
    product_type_value: Optional[str] = "USDT-FUTURES"  # set to None for SPOT
    ws_volume_is_cumulative: bool = True
    # Map friendly tf -> API granularity tokens (case matters for some endpoints)
    timeframe_to_granularity: Dict[str, str] = None

    # WebSocket candlestick subscription args
    def ws_sub_args(self, symbol: str, timeframe: str) -> Dict:
        gran = self.timeframe_to_granularity.get(timeframe, timeframe)
        return {
            "channel": f"candle{gran}",  # e.g., "candle5m", "candle4H"
            "instId": symbol,  # "BTCUSDT"
            "instType": self.ws_inst_type  # "USDT-FUTURES" (or "SPOT" if spot)
        }

    # If your WS requires an instType (e.g., 'USDT-FUTURES' for futures / 'SPOT' for spot)
    ws_inst_type: Optional[str] = "USDT-FUTURES"

    # WebSocket ping (None to disable custom pings)
    ping_interval_sec: Optional[int] = 15

    # Parse REST response into canonical rows:
    # Each row: (openTimeMs:int, open:float, high:float, low:float, close:float, volume:float)
    def parse_rest_klines(self, response_json: dict) -> List[Tuple[int, float, float, float, float, float]]:
        data = response_json.get("data") or response_json
        rows = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, list) and len(item) >= 6:
                    ts, o, h, l, c, v = item[:6]
                elif isinstance(item, dict):
                    ts = item.get("ts") or item.get("t") or item.get("time") or item.get("openTime") or item.get("openTimeMs")
                    o  = item.get("o") or item.get("open")
                    h  = item.get("h") or item.get("high")
                    l  = item.get("l") or item.get("low")
                    c  = item.get("c") or item.get("close")
                    v  = item.get("v") or item.get("volume")
                else:
                    continue
                try:
                    ts = int(ts)
                    o, h, l, c, v = float(o), float(h), float(l), float(c), float(v)
                    rows.append((ts, o, h, l, c, v))
                except Exception:
                    continue
        return rows

    # Parse a single WS message (JSON-decoded dict) and return rows like REST parse
    def parse_ws_klines(self, message: dict) -> List[Tuple[int, float, float, float, float, float]]:
        data = message.get("data")
        rows = []
        if not data:
            return rows
        for item in data:
            if isinstance(item, list) and len(item) >= 6:
                ts, o, h, l, c, v = item[:6]
            elif isinstance(item, dict):
                ts = item.get("ts") or item.get("t") or item.get("time") or item.get("openTime") or item.get("openTimeMs")
                o  = item.get("o") or item.get("open")
                h  = item.get("h") or item.get("high")
                l  = item.get("l") or item.get("low")
                c  = item.get("c") or item.get("close")
                v  = item.get("v") or item.get("volume")
            else:
                continue
            try:
                ts = int(ts)
                if ts < 10_000_000_000:  # naive check: treat < 10^10 as seconds
                    ts *= 1000
                o, h, l, c, v = float(o), float(h), float(l), float(c), float(v)
                rows.append((ts, o, h, l, c, v))
            except Exception:
                continue
        return rows

# -------------------- Manager --------------------

class LiveKlinesManager:
    def __init__(
        self,
        symbols: Iterable[str],
        timeframes_windows: Dict[str, int],
        endpoints: Optional[BitgetEndpoints] = None,
        rest_max_batch: int = 1000,
        rest_timeout: float = 10.0,
        ws_reconnect_backoff: Tuple[float, float] = (1.0, 30.0),
        gap_fill_on_jump: bool = True,
    ):
        """
        :param symbols: e.g., ["BTCUSDT", "ETHUSDT"]
        :param timeframes_windows: e.g., {"5m": 1000, "4h": 200}
        :param endpoints: BitgetEndpoints config (tweak URLs/params/parsers here)
        :param rest_max_batch: max 'limit' per REST call
        :param ws_reconnect_backoff: (start, max) seconds
        :param gap_fill_on_jump: if True, uses REST to fill missing buckets on jumps
        """
        self.symbols = list(symbols)
        self.tf_windows = dict(timeframes_windows)
        self.endpoints = endpoints or BitgetEndpoints(
            timeframe_to_granularity={
                "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m",
                "1h": "1H", "2h": "2H", "4h": "4H", "6h": "6H", "12h": "12H", "1d": "1D"
            }
        )
        self.rest_max_batch = rest_max_batch
        self.rest_timeout = rest_timeout
        self.ws_reconnect_backoff = ws_reconnect_backoff
        self.gap_fill_on_jump = gap_fill_on_jump
        self._stripes = [threading.RLock() for _ in range(64)]

        # Internal state
        self.store: Dict[Tuple[str, str], pd.DataFrame] = {}
        self._ws_app: Optional[WebSocketApp] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Precreate empty DFs
        for s in self.symbols:
            for tf in self.tf_windows:
                key = (s, tf)
                with self._key_lock(key):
                    self.store[key] = pd.DataFrame(columns=["t","o","h","l","c","v"]).astype({
                        "t":"int64","o":"float64","h":"float64","l":"float64","c":"float64","v":"float64"
                    }).set_index("t")

        # deprecated
        # self._lock = threading.RLock()
        # deprecated
        # Precreate locks for each DF using the same keys
        self._locks_map_lock = threading.RLock()  # protects the locks dictionary
        self._locks_by_key: Dict[Tuple[str, str], threading.RLock] = {}  # (symbol, tf) -> lock
        # for s in self.symbols:
        #     for tf in self.tf_windows:
        #         self._locks_by_key[(s, tf)] = threading.RLock()

    # ---------- Public API matching your client ----------

    def get_5m_from(self, symbol: str) -> pd.DataFrame:
        return self.get_window(symbol, "5m")

    def get_4h_from(self, symbol: str) -> pd.DataFrame:
        return self.get_window(symbol, "4h")

    def get_window(self, symbol: str, timeframe: str) -> pd.DataFrame:
        key = (symbol, timeframe)
        # key_lock = self._get_key_lock(key)
        with self._key_lock(key):
            df = self.store.get(key)
            if df is None or df.empty:
                return pd.DataFrame(columns=["t", "o", "h", "l", "c", "v"]).set_index("t")
            return df.copy()

    # ---------- Lifecycle ----------

    def _key_lock(self, key: Tuple[str, str]):
        return self._stripes[hash(key) % len(self._stripes)]

    # deprecated
    # def _get_key_lock(self, key: Tuple[str, str]) -> threading.RLock:
    #     with self._locks_map_lock:
    #         lock = self._locks_by_key.get(key)
    #         if lock is None:
    #             lock = threading.RLock()
    #             self._locks_by_key[key] = lock
    #         return lock

    def start(self):
        self._stop_event.clear()
        self._rest_backfill_all()
        self._start_ws_thread()

    def stop(self):
        self._stop_event.set()
        if self._ws_app:
            try:
                self._ws_app.close()
            except Exception:
                pass
        if self._ws_thread and self._ws_thread.is_alive():
            self._ws_thread.join(timeout=5.0)

    # ---------- Backfill ----------

    def _rest_backfill_all(self):
        for s in self.symbols:
            for tf, window in self.tf_windows.items():
                self._rest_backfill_symbol_tf(s, tf, window)

    def _rest_backfill_symbol_tf(self, symbol: str, timeframe: str, window: int):
        key = (symbol, timeframe)
        needed = window
        all_rows: List[Tuple[int,float,float,float,float,float]] = []

        while needed > 0:
            limit = min(self.rest_max_batch, needed)
            url, params = self.endpoints.rest_kline_params(symbol, timeframe, limit)
            try:
                r = requests.get(url, params=params, timeout=self.rest_timeout)
                r.raise_for_status()
                rows = self.endpoints.parse_rest_klines(r.json())
            except Exception as e:
                print(f"[REST] Error fetching {symbol} {timeframe}: {e}")
                break

            if not rows:
                logging.warning(f"[REST] rows fetched for {symbol} {timeframe} are None")
                break

            rows = sorted(rows, key=lambda x: x[0])
            all_rows.extend(rows[-limit:])
            needed = window - len(all_rows)
            if len(rows) < limit:
                logging.warning(f"[REST] rows fetched for {symbol} {timeframe} are {len(rows)}, less than defined limit {limit}")
                break

        if not all_rows:
            logging.warning(f"[REST] all_rows is None")
            return

        df = pd.DataFrame(all_rows, columns=["t","o","h","l","c","v"]).astype({
            "t":"int64","o":"float64","h":"float64","l":"float64","c":"float64","v":"float64"
        }).set_index("t").sort_index()

        with self._key_lock(key):
            self.store[key] = df.tail(window)

    # ---------- WebSocket worker ----------

    def _start_ws_thread(self):
        t = threading.Thread(target=self._ws_worker, name="BitgetWS", daemon=True)
        self._ws_thread = t
        t.start()

    def _ws_worker(self):
        backoff = self.ws_reconnect_backoff[0]
        backoff_max = self.ws_reconnect_backoff[1]
        while not self._stop_event.is_set():
            try:
                self._run_ws_once()
                # If we stayed connected > 20s, consider it healthy and reset backoff
                backoff = self.ws_reconnect_backoff[0]
            except Exception as e:
                print(f"[WS] Exception in WS loop: {e}\n{traceback.format_exc()}")
            if self._stop_event.is_set():
                break
            print(f"[WS] reconnecting in {backoff:.1f}s ...")
            time.sleep(backoff)
            backoff = min(backoff * 2, backoff_max)

    def _run_ws_once(self):
        url = self.endpoints.ws_url
        send_lock = threading.RLock()  # guard ws.send across threads
        last_msg_ts = {"ts": time.time()}  # simple watchdog state

        # NEW: local event only for this run
        local_stop = threading.Event()

        def _safe_send(payload: dict, label: str):
            try:
                data = json.dumps(payload)
            except Exception:
                logging.error("[WS] %s: json.dumps failed for %r", label, payload, exc_info=True)
                return False
            try:
                with send_lock:
                    self._ws_app.send(data)
                return True
            except Exception:
                logging.error("[WS] %s: ws.send failed", label, exc_info=True)
                return False

        # ---- callbacks ---------------------------------------------------------

        def _on_open(ws: WebSocketApp):
            try:
                args = [self.endpoints.ws_sub_args(s, tf) for s in self.symbols for tf in self.tf_windows]
                # (Some gateways have an 'args' array size limit; if you hit drops, chunk here.)
                ok = _safe_send({"op": "subscribe", "args": args}, "subscribe")
                if not ok:
                    logging.error("[WS] subscribe send failed (args count=%d)", len(args))
            except Exception:
                logging.error("[WS] subscribe assembly failed", exc_info=True)

        def _on_message(ws, message: str):
            if message == "pong" or message == "ping":
                last_msg_ts["ts"] = time.time()
                return
            try:
                msg = json.loads(message)
            except Exception:
                return

            # record liveness
            last_msg_ts["ts"] = time.time()

            # server error/event frames
            if isinstance(msg, dict) and msg.get("event") == "error":
                with open("WS_errors.log", 'a') as error_file:
                    print("[WS] server ERROR: %r", msg, file=error_file)
                return

            if isinstance(msg, dict) and msg.get("event") == "subscribe":
                # logging.info("[WS] subscribed ok: %r", msg.get("arg") or msg)
                return

            # app-level ping/pong noise
            if isinstance(msg, dict) and msg.get("op") in ("pong", "ping"):
                return

            rows = self.endpoints.parse_ws_klines(msg)
            if not rows:
                return

            # robust (symbol, timeframe) extraction
            arg = msg.get("arg") or {}
            symbol = arg.get("instId") or arg.get("symbol")
            channel = (arg.get("channel") or "").lower()
            if not symbol or not channel:
                return

            # Map known TF tokens precisely (avoid "1m" in "15m")
            # Expect channels like: "candle5m:BTCUSDT" or "kline.5m.BTCUSDT"
            tf = None
            try:
                mapped = self.endpoints.timeframe_to_granularity or {}
                # Build list like ["1m","5m","15m","4h", mapped values...]
                tf_candidates = list(self.tf_windows.keys()) + [str(mapped.get(k, k)) for k in self.tf_windows.keys()]
                tf_candidates = sorted(set(str(x).lower() for x in tf_candidates), key=len, reverse=True)
                m = re.search(r'(?:candle|kline)[\.\-:]?(\d+[smhdw])', channel)
                if m and m.group(1) in tf_candidates:
                    tf = m.group(1)
                else:
                    # fallback: exact token match on separators to avoid substr collisions
                    for tok in tf_candidates:
                        if re.search(rf'(^|[\.\-:]){re.escape(tok)}($|[\.\-:])', channel):
                            tf = tok
                            break
            except Exception:
                logging.error("[WS] timeframe parse failed for channel=%r", channel, exc_info=True)
                return

            if not tf:
                return

            # (Optional) peek at first row for visibility during dev
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug("[WS] %s %s rows=%d first=%r", symbol, tf, len(rows), rows[0] if rows else None)

            try:
                self._merge_live_rows(symbol, tf, rows)
            except Exception:
                logging.error("[WS] _merge_live_rows failed for %s %s", symbol, tf, exc_info=True)

        def _on_error(ws: WebSocketApp, error: Exception):
            # Many WS disconnects are normal (network blips, server rotations). We auto-reconnect.
            try:
                from websocket._exceptions import WebSocketConnectionClosedException as _WSClosed
            except Exception:
                _WSClosed = None
            if _WSClosed and isinstance(error, _WSClosed):
                logging.warning("WS connection closed (will reconnect): %s", error)
            else:
                logging.error("WS error", exc_info=True)

        def _on_close(ws, *args):
            code = reason = None
            if len(args) == 2:
                code, reason = args
            logging.warning("WS closed. code=%r reason=%r", code, reason)
            # Make sure pinger stops quickly after close
            local_stop.set()

        # (Optional) WS-level on_pong if you ever enable WS pings
        def _on_pong(ws, data):
            logging.debug("WS PONG: %r", data)

        # ---- app construction ---------------------------------------------------

        self._ws_app = WebSocketApp(
            url,
            on_open=_on_open,
            on_message=_on_message,
            on_error=_on_error,
            on_close=_on_close,
            on_pong=_on_pong,  # harmless if you keep WS pings off
        )

        # ---- pinger thread (app-level heartbeat) --------------------------------

        def _pinger():
            interval = int(self.endpoints.ping_interval_sec or 30)
            while not (self._stop_event.is_set() or local_stop.is_set()):
                try:
                    # only attempt if connected
                    sock = getattr(self._ws_app, "sock", None)
                    if not (sock and getattr(sock, "connected", False)):
                        return
                    self._ws_app.send("ping")  # Bitget expects a literal "ping"
                except Exception:
                    # downgrade to INFO if it’s too chatty
                    logging.info("[WS] app-ping skipped (socket closed)")
                    return
                for _ in range(interval):
                    if self._stop_event.is_set() or local_stop.is_set():
                        return
                    time.sleep(1)

        ping_thread = None
        if self.endpoints.ping_interval_sec:
            ping_thread = threading.Thread(target=_pinger, name="BitgetWS-Ping", daemon=True)
            ping_thread.start()

        # ---- optional stale-connection watchdog ---------------------------------
        # If you want: close the socket if no data in N seconds to trigger reconnect
        def _watchdog():
            timeout = getattr(self.endpoints, "stale_timeout_sec", None) or 60
            while not self._stop_event.is_set():
                if time.time() - last_msg_ts["ts"] > timeout:
                    logging.warning("[WS] no data for %ss -> closing to force reconnect", timeout)
                    try:
                        self._ws_app.close()
                    except Exception:
                        pass
                    return
                time.sleep(5)

        watchdog_thread = threading.Thread(target=_watchdog, name="BitgetWS-Watchdog", daemon=True)
        watchdog_thread.start()

        # ---- run loop -----------------------------------------------------------

        try:
            # Explicit: 0 disables WS-level ping (we use app-level)
            self._ws_app.run_forever(ping_interval=0)
        except Exception as e:
            # Downgrade expected close exceptions to INFO/WARNING to reduce noise.
            try:
                from websocket._exceptions import WebSocketConnectionClosedException as _WSClosed
            except Exception:
                _WSClosed = None
            if _WSClosed and isinstance(e, _WSClosed):
                logging.info("websocket.run_forever ended: connection closed (will reconnect): %s", e)
            else:
                logging.error("websocket.run_forever failed", exc_info=True)
        finally:
            # ensure we won’t leave background threads dangling
            pass
            # local_stop.set()

    # ---------- Merge logic ----------

    def _merge_live_rows(self, symbol: str, timeframe: str,
                         rows: List[Tuple[int, float, float, float, float, float]]):
        key = (symbol, timeframe)
        tf_sec = timeframe_seconds(timeframe)
        # key_lock = self._get_key_lock(key)

        do_backfill = False
        backfill_n = None

        with self._key_lock(key):
            df = self.store.get(key)
            if df is None or df.empty:
                df = (
                    pd.DataFrame(columns=["t", "o", "h", "l", "c", "v"])
                    .astype(
                        {"t": "int64", "o": "float64", "h": "float64", "l": "float64", "c": "float64", "v": "float64"})
                    .set_index("t")
                )
                self.store[key] = df

            # keep order predictable even if bursts are out-of-order
            rows = sorted(rows, key=lambda x: x[0])

            for (ts, o, h, l, c, v) in rows:
                bucket = floor_to_bucket_start(ts, timeframe)
                if bucket in df.index:
                    old = df.loc[bucket]
                    new_o = old["o"] if not pd.isna(old["o"]) else o
                    new_h = max(old["h"], h) if not pd.isna(old["h"]) else h
                    new_l = min(old["l"], l) if not pd.isna(old["l"]) else l

                    # IMPORTANT: Bitget kline WS volume is cumulative within candle.
                    # Do NOT sum; keep the latest (monotonic) value.
                    if self.endpoints.ws_volume_is_cumulative:
                        new_v = max(old["v"], v) if not pd.isna(old["v"]) else v
                    else:
                        new_v = old["v"] + v

                    df.loc[bucket, ["o", "h", "l", "c", "v"]] = [new_o, new_h, new_l, c, new_v]
                else:
                    df.loc[bucket, ["o", "h", "l", "c", "v"]] = [o, h, l, c, v]

            df.sort_index(inplace=True)

            # Compute whether we need a backfill (no I/O under the lock)
            if self.gap_fill_on_jump and len(df) >= 2:
                last = int(df.index[-1])
                prev = int(df.index[-2])
                expected = prev + tf_sec * 1000
                if last > expected + (tf_sec * 1000):
                    missing = int((last - expected) // (tf_sec * 1000))
                    backfill_n = min(self.tf_windows[timeframe], df.shape[0] + missing + 5)
                    do_backfill = True

            window = self.tf_windows.get(timeframe, len(df))
            self.store[key] = df.tail(window)

        # Perform REST I/O OUTSIDE the key lock
        if do_backfill:
            self._rest_backfill_symbol_tf(symbol, timeframe, backfill_n)

# -------------------- Convenience: global-style wrappers --------------------

_GLOBAL_MANAGER: Optional[LiveKlinesManager] = None

def init_global_manager(
    symbols: Iterable[str],
    timeframes_windows: Dict[str, int],
    endpoints: Optional[BitgetEndpoints] = None,
) -> LiveKlinesManager:
    global _GLOBAL_MANAGER
    _GLOBAL_MANAGER = LiveKlinesManager(symbols, timeframes_windows, endpoints=endpoints)
    _GLOBAL_MANAGER.start()
    return _GLOBAL_MANAGER

def shutdown_global_manager():
    global _GLOBAL_MANAGER
    if _GLOBAL_MANAGER is not None:
        _GLOBAL_MANAGER.stop()
        _GLOBAL_MANAGER = None

def get_5m_from(symbol: str, *_ignore) -> pd.DataFrame:
    if _GLOBAL_MANAGER is None:
        raise RuntimeError("Global manager not initialized. Call init_global_manager(...) first.")
    return _GLOBAL_MANAGER.get_5m_from(symbol)

def get_4h_from(symbol: str, *_ignore) -> pd.DataFrame:
    if _GLOBAL_MANAGER is None:
        raise RuntimeError("Global manager not initialized. Call init_global_manager(...) first.")
    return _GLOBAL_MANAGER.get_4h_from(symbol)

import time, logging

def warn_if_stale(manager=None, threshold_sec=90):
    """
    Warn if no candle has advanced for > threshold_sec OR 1.5x its timeframe.
    Call this periodically (e.g. every loop).
    """
    if manager is None:
        manager = _GLOBAL_MANAGER
    if manager is None:
        logging.warning("[WS] warn_if_stale called but no global manager running.")
        return

    now = int(time.time() * 1000)
    stale = []
    with manager._lock:
        for (symbol, tf), df in manager.store.items():
            if df is None or df.empty:
                continue
            last_t = int(df.index[-1])
            tf_sec = timeframe_seconds(tf)
            max_age_ms = max(threshold_sec * 1000, int(1.5 * tf_sec * 1000))
            age_ms = now - last_t
            if age_ms > max_age_ms:
                stale.append((symbol, tf, age_ms // 1000))

    for s, tf, age in stale:
        logging.warning(f"[WS] STALE FEED: {s} {tf} last bucket {age}s ago")

# -------------------- Example usage --------------------
if __name__ == "__main__":
    # MIX v2 (Futures) defaults

    def _endpoints():
        return BitgetEndpoints(
            # REST (kept as v2 MIX candles):
            rest_base="https://api.bitget.com",
            rest_path="/api/v2/mix/market/candles",
            product_type_param="productType",
            product_type_value="USDT-FUTURES",
            symbol_param="symbol",
            granularity_param="granularity",
            timeframe_to_granularity={"5m": "5m", "4h": "4H"},
            ws_volume_is_cumulative=True,

            # WS public v2:
            ws_url="wss://ws.bitget.com/v2/ws/public",
            ws_inst_type="USDT-FUTURES",
            ping_interval_sec=None,  # still let the library handle heartbeats
        )

    endpoints = _endpoints()
    #     timeframe_to_granularity={"5m": "5m", "4h": "4H"},
    #     product_type_value="USDT-FUTURES",
    #     ws_inst_type="USDT-FUTURES",
    #     rest_base="https://api.bitget.com",
    #     rest_path="/api/v2/mix/market/candles",
    #     symbol_param="symbol",
    #     granularity_param="granularity",
    #     product_type_param="productType",
    #     ws_url="wss://ws.bitget.com/mix/v1/stream",
    #     ping_interval_sec=15,
    # )

    mgr = init_global_manager(
        symbols=["BTCUSDT", "ETHUSDT"],
        timeframes_windows={"5m": 100, "4h": 200},
        endpoints=endpoints,
    )

    try:
        for _ in range(10):
            time.sleep(30)
            print("BTC 5m tail:\n", get_5m_from("BTCUSDT").tail(3))
            print("BTC 4h tail:\n", get_4h_from("BTCUSDT").tail(3))
    finally:
        shutdown_global_manager()

# -------------------- Notes for UTA v3 users --------------------
# If you're on UTA v3, configure endpoints like:
#
# uta_endpoints = BitgetEndpoints(
#     # v3 REST:
#     rest_base="https://api.bitget.com",
#     rest_path="/api/v3/market/candles",   # docs: GET /api/v3/market/candles
#     symbol_param="symbol",
#     granularity_param="interval",          # Param is named 'interval' in some v3 docs
#     product_type_param="category",         # 'category' instead of productType
#     product_type_value="USDT-FUTURES",     # or 'SPOT', 'COIN-FUTURES', 'USDC-FUTURES'
#     timeframe_to_granularity={"5m": "5m", "4h": "4H"},
#     # v3 WS public:
#     ws_url="wss://ws.bitget.com/v2/ws/public",
#     ws_inst_type="USDT-FUTURES",
# )
# init_global_manager(symbols=[...], timeframes_windows={"5m":100,"4h":200}, endpoints=uta_endpoints)
