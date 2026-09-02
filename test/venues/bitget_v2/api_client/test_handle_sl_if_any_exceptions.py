import time
import pandas as pd
import pytest

from venues.bitget_v2.api_client.background_order_tpsl_coordinator import ExitEvent, handle_sl_if_any, _EXIT_EVENTS
from core.Runtimes.Live.live_constants import SKIP_DAY_DELAY


def make_df(ts: float | None = None):
    if ts is None:
        ts = time.time()
    return pd.DataFrame([
        {"timestamp": pd.Timestamp.fromtimestamp(ts).isoformat(), "c": 1.0}
    ])


def clear_events():
    try:
        while True:
            _EXIT_EVENTS.popleft()
    except IndexError:
        pass


def test_handle_sl_if_any_survives_csv_write_error_on_sl(monkeypatch):
    clear_events()
    symbol = "XRPUSDT"
    df = make_df()
    skip_day = {symbol: 0}

    # Push SL event so function goes into logging branch
    _EXIT_EVENTS.append(ExitEvent(symbol=symbol, exit_type="SL", price=0.5, ts=time.time(), meta={}))

    # Monkeypatch pandas.DataFrame.to_csv to raise
    def boom(*args, **kwargs):
        raise RuntimeError("disk is full")

    monkeypatch.setattr(pd.DataFrame, "to_csv", boom, raising=True)

    bal_after, closed = handle_sl_if_any(symbol, 100.0, df, -1, "dummy_strategy", skip_day)
    print(bal_after, closed, skip_day)
    # Even if CSV writing fails, function should not raise and should still apply SL semantics
    assert isinstance(bal_after, float)
    assert closed is True
    assert skip_day[symbol] == SKIP_DAY_DELAY


def test_handle_sl_if_any_survives_csv_write_error_on_tp(monkeypatch):
    clear_events()
    symbol = "BNBUSDT"
    df = make_df()
    skip_day = {symbol: 0}

    _EXIT_EVENTS.append(ExitEvent(symbol=symbol, exit_type="TP", price=500.0, ts=time.time(), meta={}))

    def boom(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(pd.DataFrame, "to_csv", boom, raising=True)

    bal_after, closed = handle_sl_if_any(symbol, 250.0, df, -1, "dummy_strategy", skip_day)
    assert isinstance(bal_after, float)
    assert closed is False  # TP should not set closed
    assert skip_day[symbol] == 0  # TP should not set cooldown even if logging failed
