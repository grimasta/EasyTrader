import time
import pandas as pd

from venues.bitget_v2.api_client import (
    handle_sl_if_any, ExitEvent, _EXIT_EVENTS
)
from core.Runtimes.Live.live_constants import SKIP_DAY_DELAY


def make_df(ts: float | None = None):
    if ts is None:
        ts = time.time()
    # handle_sl_if_any reads df_5m.iloc[idx]['timestamp'] if present
    return pd.DataFrame([
        {"timestamp": pd.Timestamp.fromtimestamp(ts).isoformat(), "c": 1.0}
    ])


def clear_events():
    try:
        while True:
            _EXIT_EVENTS.popleft()
    except IndexError:
        pass


def test_handle_sl_if_any_no_event_returns_closed_false_and_no_cooldown():
    clear_events()
    df = make_df()
    skip_day = {"BTCUSDT": 0}
    bal_after, closed = handle_sl_if_any("BTCUSDT", 1000.0, df, -1, "dummy_strategy", skip_day)
    assert bal_after == 1000.0
    assert closed is False
    assert skip_day["BTCUSDT"] == 0


def test_handle_sl_if_any_tp_event_does_not_close_and_no_cooldown():
    clear_events()
    df = make_df()
    skip_day = {"ETHUSDT": 0}
    _EXIT_EVENTS.append(ExitEvent(symbol="ETHUSDT", exit_type="TP", price=123.45, ts=time.time(), meta={}))
    bal_after, closed = handle_sl_if_any("ETHUSDT", 1000.0, df, -1, "dummy_strategy", skip_day)
    assert isinstance(bal_after, float)
    assert closed is False, "handle_sl_if_any must not return closed=True for TP exits"
    assert skip_day["ETHUSDT"] == 0, "TP must not set daily cooldown"


def test_handle_sl_if_any_sl_event_closes_and_sets_cooldown():
    clear_events()
    df = make_df()
    skip_day = {"SOLUSDT": 0}
    _EXIT_EVENTS.append(ExitEvent(symbol="SOLUSDT", exit_type="SL", price=98.76, ts=time.time(), meta={}))
    bal_after, closed = handle_sl_if_any("SOLUSDT", 1000.0, df, -1, "dummy_strategy", skip_day)
    assert isinstance(bal_after, float)
    assert closed is True, "handle_sl_if_any must return closed=True only for SL exits"
    assert skip_day["SOLUSDT"] == SKIP_DAY_DELAY, "SL must apply daily cooldown"


essential_symbols = ["ADAUSDT", "ADAUSDT"]


def test_only_latest_event_for_symbol_is_used():
    # If multiple events exist for same symbol, only the latest should be used
    clear_events()
    symbol = "ADAUSDT"
    df = make_df()
    skip_day = {symbol: 0}
    # Push an older TP then a newer SL
    _EXIT_EVENTS.append(ExitEvent(symbol=symbol, exit_type="TP", price=1.1, ts=time.time()-1, meta={}))
    _EXIT_EVENTS.append(ExitEvent(symbol=symbol, exit_type="SL", price=1.0, ts=time.time(), meta={}))

    _, closed = handle_sl_if_any(symbol, 100.0, df, -1, "dummy_strategy", skip_day)
    assert closed is True, "Latest event (SL) should determine the closed flag"
    assert skip_day[symbol] == SKIP_DAY_DELAY

    # Now push an older SL then a newer TP; result should be closed False, no cooldown
    clear_events()
    skip_day[symbol] = 0
    _EXIT_EVENTS.append(ExitEvent(symbol=symbol, exit_type="SL", price=1.0, ts=time.time()-1, meta={}))
    _EXIT_EVENTS.append(ExitEvent(symbol=symbol, exit_type="TP", price=1.1, ts=time.time(), meta={}))

    _, closed2 = handle_sl_if_any(symbol, 100.0, df, -1, "dummy_strategy", skip_day)
    assert closed2 is False, "Latest event (TP) should not set closed"
    assert skip_day[symbol] == 0, "Latest TP should not set cooldown"