import pytest
from decimal import Decimal
from core.data_model.klines.kline import Kline
from core.data_model.klines.kline_buffer import KlineBuffer


def make_kline(timestamp_ms: int, close: float = 50000.0) -> Kline:
    return Kline(
        timestamp_ms=timestamp_ms,
        open=Decimal(str(close)),
        high=Decimal(str(close + 100)),
        low=Decimal(str(close - 100)),
        close=Decimal(str(close)),
        volume=Decimal("10"),
    )


def make_buffer(max_size: int = 10) -> KlineBuffer:
    return KlineBuffer(symbol="BTCUSDT", timeframe="5m", max_size=max_size)


# --- Construction ---

def test_buffer_construction():
    b = make_buffer()
    assert b.symbol == "BTCUSDT"
    assert b.timeframe == "5m"
    assert b.max_size == 10
    assert len(b) == 0


def test_buffer_rejects_zero_max_size():
    with pytest.raises(ValueError):
        KlineBuffer(symbol="BTCUSDT", timeframe="5m", max_size=0)


def test_buffer_rejects_negative_max_size():
    with pytest.raises(ValueError):
        KlineBuffer(symbol="BTCUSDT", timeframe="5m", max_size=-1)


# --- Append and len ---

def test_append_increases_length():
    b = make_buffer()
    b.append(make_kline(1000))
    assert len(b) == 1


def test_append_multiple():
    b = make_buffer()
    for i in range(5):
        b.append(make_kline(i * 1000))
    assert len(b) == 5


# --- Capacity and eviction ---

def test_buffer_does_not_exceed_max_size():
    b = make_buffer(max_size=3)
    for i in range(10):
        b.append(make_kline(i * 1000))
    assert len(b) == 3


def test_oldest_kline_is_evicted_when_full():
    b = make_buffer(max_size=3)
    for i in range(4):
        b.append(make_kline(i * 1000))
    assert b.oldest.timestamp_ms == 1000  # 0 was evicted


def test_latest_kline_is_most_recently_appended():
    b = make_buffer()
    b.append(make_kline(1000))
    b.append(make_kline(2000))
    assert b.latest.timestamp_ms == 2000


# --- is_empty and is_ready ---

def test_is_empty_on_new_buffer():
    assert make_buffer().is_empty()


def test_is_not_empty_after_append():
    b = make_buffer()
    b.append(make_kline(1000))
    assert not b.is_empty()


def test_is_ready_false_when_below_min():
    b = make_buffer()
    b.append(make_kline(1000))
    assert not b.is_ready(min_size=5)


def test_is_ready_true_when_at_min():
    b = make_buffer()
    for i in range(5):
        b.append(make_kline(i * 1000))
    assert b.is_ready(min_size=5)


def test_is_ready_true_when_above_min():
    b = make_buffer()
    for i in range(7):
        b.append(make_kline(i * 1000))
    assert b.is_ready(min_size=5)


# --- latest and oldest on empty buffer ---

def test_latest_returns_none_on_empty_buffer():
    assert make_buffer().latest is None


def test_oldest_returns_none_on_empty_buffer():
    assert make_buffer().oldest is None


# --- extend ---

def test_extend_appends_all_klines():
    b = make_buffer()
    klines = [make_kline(i * 1000) for i in range(5)]
    b.extend(klines)
    assert len(b) == 5


def test_extend_respects_max_size():
    b = make_buffer(max_size=3)
    klines = [make_kline(i * 1000) for i in range(10)]
    b.extend(klines)
    assert len(b) == 3


# --- clear ---

def test_clear_empties_buffer():
    b = make_buffer()
    for i in range(5):
        b.append(make_kline(i * 1000))
    b.clear()
    assert b.is_empty()
    assert len(b) == 0


# --- as_sequence ---

def test_as_sequence_returns_list():
    b = make_buffer()
    b.append(make_kline(1000))
    result = b.as_sequence()
    assert isinstance(result, list)


def test_as_sequence_is_copy():
    b = make_buffer()
    b.append(make_kline(1000))
    seq = b.as_sequence()
    seq.clear()
    assert len(b) == 1  # buffer unaffected


def test_as_sequence_ascending_order():
    b = make_buffer()
    for i in range(5):
        b.append(make_kline(i * 1000))
    seq = b.as_sequence()
    timestamps = [k.timestamp_ms for k in seq]
    assert timestamps == sorted(timestamps)


# --- closes ---

def test_closes_returns_close_prices():
    b = make_buffer()
    b.append(make_kline(1000, close=100.0))
    b.append(make_kline(2000, close=200.0))
    assert b.closes() == [Decimal("100.0"), Decimal("200.0")]


# --- repr ---

def test_repr_contains_symbol_and_timeframe():
    b = make_buffer()
    r = repr(b)
    assert "BTCUSDT" in r
    assert "5m" in r
    assert "0/10" in r


def test_repr_shows_current_size():
    b = make_buffer(max_size=10)
    b.append(make_kline(1000))
    b.append(make_kline(2000))
    assert "2/10" in repr(b)


# --- Config integration sanity check ---

def test_buffer_size_matches_config_defaults():
    from core.config import Config
    cfg = Config()
    b = KlineBuffer("BTCUSDT", "5m", max_size=cfg.kline_buffer_size)
    assert b.max_size == cfg.kline_buffer_size
    assert b.is_ready(cfg.max_indicator_lookback) is False