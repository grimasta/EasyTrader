import pytest
from decimal import Decimal
from core.data_model.klines.kline import Kline


def make_kline(**overrides) -> Kline:
    defaults = dict(
        timestamp_ms=1_700_000_000_000,
        open=Decimal("50000"),
        high=Decimal("50500"),
        low=Decimal("49800"),
        close=Decimal("50200"),
        volume=Decimal("12.5"),
    )
    defaults.update(overrides)
    return Kline(**defaults)


# --- Construction ---

def test_kline_constructs_with_all_fields():
    k = make_kline()
    assert k.timestamp_ms == 1_700_000_000_000
    assert k.close == Decimal("50200")


# --- Immutability ---

def test_kline_is_immutable():
    k = make_kline()
    with pytest.raises((AttributeError, TypeError)):
        k.close = Decimal("99999")  # type: ignore


# --- Equality ---

def test_kline_equality_by_value():
    k1 = make_kline()
    k2 = make_kline()
    assert k1 == k2
    assert k1 is not k2


def test_kline_inequality_on_different_close():
    k1 = make_kline(close=Decimal("50200"))
    k2 = make_kline(close=Decimal("50300"))
    assert k1 != k2


# --- Hashability (frozen dataclass is hashable) ---

def test_kline_is_hashable():
    k = make_kline()
    s = {k}
    assert k in s


def test_kline_deduplication_in_set():
    k1 = make_kline()
    k2 = make_kline()
    assert len({k1, k2}) == 1


# --- Decimal types ---

def test_all_price_fields_are_decimal():
    k = make_kline()
    assert isinstance(k.open, Decimal)
    assert isinstance(k.high, Decimal)
    assert isinstance(k.low, Decimal)
    assert isinstance(k.close, Decimal)
    assert isinstance(k.volume, Decimal)