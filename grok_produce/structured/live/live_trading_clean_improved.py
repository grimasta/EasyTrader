import logging, time, json
from datetime import datetime, timedelta
import pandas as pd

# STRATEGY + API bits you already have
from grok_produce.structured.strategies.strategies_live import STRATEGIES
from grok_produce.structured.api_client.v2_calc_correct_pos import compute_position_size
from grok_produce.structured.proof_of_concept_for_order_placing import (
    get_future_symbol_mark_price, get_account_balance, get_account_current, get_entry_price
)
from grok_produce.structured.api_client.v2_runtime_rebuild import rebuild_runtime_state

# Unified background coordinator (limit entry + on-close TP/SL + recovery)
from grok_produce.structured.api_client.background_order_tpsl_coordinator import (
    place_limit_long, handle_sl_if_any, recover_open_positions_and_watch, dump_bracket, poke_eval_now,
    force_register_bracket_from_position, audit_and_fix_brackets
)
from grok_produce.structured.api_client.entry_guard import is_blocked as guard_blocked
from grok_produce.structured.api_client.v2_on_candle_close_tp_sl import has_active_bracket

# Live candles (global manager)
from grok_produce.structured.websocket.bitget_live_klines import (
    init_global_manager, BitgetEndpoints, get_5m_from, get_4h_from, warn_if_stale
)

# ---------- your constants ----------
SYMBOLS = ['BTCUSDT','ETHUSDT','SOLUSDT','DOGEUSDT','XRPUSDT','BNBUSDT','TRXUSDT',
           'ADAUSDT','LINKUSDT','DOTUSDT','AVAXUSDT','ICPUSDT','LTCUSDT','NEARUSDT']
LEVERAGE = 10
POSITION_SIZE = 0.01
PROFIT_TARGET = 0.012          # 1.2% gross by default; you can tune per symbol
STOP_LOSS = 0.02
MAX_TRADES_PER_DAY = 10
STRATEGY_NAME = 'best_momentum'
LOSS_LIMIT = 0.40               # stop if equity drops by 40%
WATCH_TIMEFRAME = "5m"          # which TF to use for on-close checks

# ---------- logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s"
)

def _to_std_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert our canonical columns o/h/l/c/v with index 't' (ms) into
    open/high/low/close/volume (+ timestamp) that indicators expect.
    Safe no-op if names already match.
    """
    if df is None or df.empty:
        return df
    out = df.copy()
    # Only rename if 'c' exists and 'close' doesn't
    if "c" in out.columns and "close" not in out.columns:
        out["open"] = out["o"]
        out["high"] = out["h"]
        out["low"]  = out["l"]
        out["close"] = out["c"]
        out["volume"] = out["v"]
    # Ensure a human-readable timestamp column for logging (your SL/TP logger uses it)
    if "timestamp" not in out.columns:
        # index is 't' in ms
        try:
            out["timestamp"] = pd.to_datetime(out.index, unit="ms")
        except Exception:
            # fall back to raw index
            out["timestamp"] = out.index
    return out


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
        ping_interval_sec = 30,  # still let the library handle heartbeats
    )


def _rotate_day(trades_today, skip_day):
    today = datetime.now().date()
    for s in trades_today.keys():
        # create a bucket for today if missing
        if today not in trades_today[s]:
            trades_today[s][today] = 0
        # decay skip counter once/day
        if skip_day[s] > 0:
            skip_day[s] -= 1

def live_trading(strategy_name=STRATEGY_NAME):
    """Production-minded runner: init feeds, recover state, trade, monitor, and log everything."""

    # 1) Start data manager (REST backfill + WS live)
    endpoints = _endpoints()
    init_global_manager(
        symbols=SYMBOLS,
        timeframes_windows={"5m": 100, "4h": 200},
        endpoints=endpoints,
    )  # live candles, threads, reconnection handled inside (REST+WS). 5m/4h getters stay the same.

    # 2) Recovery: rebuild TP/SL watchers from live positions (so exits/logging continue after restarts)
    recover_open_positions_and_watch(SYMBOLS, watch_timeframe=WATCH_TIMEFRAME)

    # 3) Strategy + capital
    strategy = STRATEGIES.get(strategy_name)
    if not strategy:
        raise ValueError(f"Unknown strategy: {strategy_name}")
    initial_balance = float(get_account_current())
    logging.info(f"=== LIVE start | strategy={strategy_name} | balance(with UPnL)={initial_balance:.2f} USDT ===")

    # 4) Runtime state (persist/restore hooks if you want)
    trades_today = {s: {} for s in SYMBOLS}       # {symbol: {date: count}}
    skip_day = {s: 0 for s in SYMBOLS}            # cool-down days after exit
    open_positions = {}                            # optional mirror; recovery also handled by coordinator

    # optional: rebuild your own runtime shadow state if you keep it
    try:
        trades_today, skip_day = rebuild_runtime_state(SYMBOLS)
        logging.info("Runtime state rebuilt from disk/cache.")
    except Exception:
        logging.info("No prior runtime snapshot found; starting fresh.")

    # 5) Main loop
    last_day = None
    i = -1
    last_audit = 0
    while True:
        # at top of live_trading, before the loop:

        # inside the while True main loop, once per ~60s:
        now = time.time()
        if now - last_audit > 60:
            audit_and_fix_brackets(SYMBOLS, default_tp_pct=PROFIT_TARGET, default_sl_pct=STOP_LOSS, tf=WATCH_TIMEFRAME)
            last_audit = now
        i += 1
        try:
            now_day = datetime.now().date()
            if last_day != now_day:
                _rotate_day(trades_today, skip_day)
                last_day = now_day
            # warn_if_stale()
            for symbol in SYMBOLS:

                if guard_blocked(symbol) or has_active_bracket(symbol):
                    continue
                # warn_if_stale()
                # Per-day limits / cooldown
                if skip_day[symbol] > 0:
                    continue
                if trades_today[symbol].get(now_day, 0) >= MAX_TRADES_PER_DAY:
                    continue

                # --- Data pull (thread-safe snapshots) ---
                df_5m = get_5m_from(symbol)
                df_4h = get_4h_from(symbol)
                if df_5m is None or df_4h is None or len(df_5m) < 20 or len(df_4h) < 100:
                    logging.debug(f"{symbol}: insufficient data (5m={len(df_5m) if df_5m is not None else 0}, 4h={len(df_4h) if df_4h is not None else 0})")
                    continue
                df_5m = _to_std_ohlcv(df_5m)
                df_4h = _to_std_ohlcv(df_4h)
                # --- Indicators & signals ---
                df_5m = strategy.apply_indicators(df_5m, timeframe='5m').dropna()
                df_4h = strategy.apply_indicators(df_4h, timeframe='4h').dropna()
                if df_5m.empty or df_4h.empty:
                    continue
                idx = -1
                signal, atr = strategy.check_signals(df_5m, df_4h, len(df_5m)-1)
                if not signal:
                    # also consume any exits logged by the background bracket (if any)
                    handle_sl_if_any(symbol, get_account_balance("USDT"), df_5m, idx, strategy_name, skip_day)
                    continue
                # --- Risk / balance check ---
                current_balance = float(get_account_balance("USDT"))
                bal_after, closed = handle_sl_if_any(symbol, current_balance, df_5m, idx, strategy_name,
                                                     skip_day)
                if closed:
                    logging.info(f"{symbol}: position closed; balance ~{bal_after:.2f} USDT")
                    continue  # or fall through; up to you

                # --- Entry sizing ---
                # mark = float(get_future_symbol_mark_price(symbol))
                mark = df_5m.iloc[len(df_5m) - 1]["close"]
                position_size = float(compute_position_size(symbol, current_balance, LEVERAGE, mark, POSITION_SIZE))
                notional = position_size * mark / LEVERAGE
                if notional > 5 * POSITION_SIZE * initial_balance:
                    logging.info(f"{symbol}: notional {notional:.3f} exceeds guard; skipping.")
                    continue
                # --- Place a GTC LIMIT at current mark (tune your price policy here) ---
                # You can bias a few ticks below mark for longs if you prefer; this keeps it simple.
                if current_balance < initial_balance * (1 - LOSS_LIMIT):
                    logging.error(f"Loss limit reached. equity={current_balance:.2f} USDT; stopping.")
                    continue
                out = place_limit_long(
                    symbol,
                    size=str(position_size),
                    price=str(mark),
                    duration="5m",          # local TTL; background module handles self-cancel if you set auto_cancel=True
                    tif="gtc",
                    client_oid=f"{strategy_name}-{symbol}-{int(time.time())}",
                    auto_cancel=True,      # set True to arm TTL self-cancel for unfilled GTCs
                    tp_pct=PROFIT_TARGET,
                    sl_pct=STOP_LOSS,
                    watch_timeframe=WATCH_TIMEFRAME,
                )
                logging.info(f"{symbol}: placed LIMIT long @ {mark:.6f} | out={out}")


                # Increment daily trade count only on successful place (keep it simple)
                trades_today[symbol][now_day] = trades_today[symbol].get(now_day, 0) + 1

                # # After placing, also check if a candle-close exit fired meanwhile (rare but safe)
                # bal_after, closed = handle_sl_if_any(symbol, current_balance, df_5m, idx, strategy_name, skip_day)
                # if closed:
                #     logging.info(f"{symbol}: position closed on exit; balance now ~{bal_after:.2f} USDT")

                # small pacing to avoid hammering your account endpoints
                time.sleep(0.2)

            # global pacing
            time.sleep(2.0)

        except KeyboardInterrupt:
            logging.warning("Interrupted. Shutting down.")
            break
        except Exception as e:
            logging.exception(f"Loop error: {e}")
            # backoff a bit on transient issues but keep running
            time.sleep(10)

live_trading(STRATEGY_NAME)