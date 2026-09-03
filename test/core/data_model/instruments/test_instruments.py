import pytest
from decimal import Decimal
from core.data_model.instruments.abstract_instrument import AbstractInstrument
from core.data_model.instruments.perpetual_contract import PerpetualContract


def make_perpetual(**overrides) -> PerpetualContract:
    defaults = dict(
        symbol="BTCUSDT",
        venue_symbol="BTCUSDT",
        venue="bitget",
        instrument_type="perpetual",
        base_asset="BTC",
        quote_asset="USDT",
        is_active=True,
        price_tick_size=Decimal("0.1"),
        qty_tick_size=Decimal("0.0001"),
        price_precision=1,
        qty_precision=4,
        min_qty=Decimal("0.0001"),
        fetched_at_ms=1_000_000_000,
        settlement_asset="USDT",
        contract_size=Decimal("1"),
        max_leverage=150,
        min_leverage=1,
        min_notional=Decimal("5"),
        max_qty=Decimal("1200"),
        max_market_qty=Decimal("220"),
        maker_fee_rate=Decimal("0.0002"),
        taker_fee_rate=Decimal("0.0006"),
        funding_interval_hours=8,
        maintenance_margin_pct=None,
        liquidation_fee_rate=None,
    )
    defaults.update(overrides)
    return PerpetualContract(**defaults)


# --- AbstractInstrument is abstract ---

def test_abstract_instrument_cannot_be_instantiated():
    with pytest.raises(TypeError):
        AbstractInstrument(  # type: ignore
            symbol="BTCUSDT",
            venue_symbol="BTCUSDT",
            venue="bitget",
            instrument_type="perpetual",
            base_asset="BTC",
            quote_asset="USDT",
            is_active=True,
            price_tick_size=Decimal("0.1"),
            qty_tick_size=Decimal("0.0001"),
            price_precision=1,
            qty_precision=4,
            min_qty=Decimal("0.0001"),
            fetched_at_ms=1_000_000_000,
        )


# --- PerpetualContract construction ---

def test_perpetual_constructs_with_all_fields():
    p = make_perpetual()
    assert p.symbol == "BTCUSDT"
    assert p.max_leverage == 150
    assert p.price_tick_size == Decimal("0.1")
    assert p.settlement_asset == "USDT"


def test_perpetual_accepts_none_for_optional_fields():
    p = make_perpetual(
        maker_fee_rate=None,
        taker_fee_rate=None,
        funding_interval_hours=None,
        maintenance_margin_pct=None,
        liquidation_fee_rate=None,
        min_notional=None,
        max_qty=None,
        max_market_qty=None,
    )
    assert p.maker_fee_rate is None
    assert p.funding_interval_hours is None


def test_perpetual_is_subclass_of_abstract_instrument():
    p = make_perpetual()
    assert isinstance(p, AbstractInstrument)


# --- Equality and identity ---

def test_perpetual_equality_by_value():
    p1 = make_perpetual()
    p2 = make_perpetual()
    assert p1 == p2
    assert p1 is not p2


def test_perpetual_inequality_on_different_field():
    p1 = make_perpetual(symbol="BTCUSDT")
    p2 = make_perpetual(symbol="ETHUSDT")
    assert p1 != p2


def test_perpetual_inequality_on_different_leverage():
    p1 = make_perpetual(max_leverage=150)
    p2 = make_perpetual(max_leverage=50)
    assert p1 != p2


# --- Decimal precision ---

def test_price_tick_size_is_decimal():
    p = make_perpetual(price_tick_size=Decimal("0.1"))
    assert isinstance(p.price_tick_size, Decimal)


def test_decimal_arithmetic_is_exact():
    p = make_perpetual(price_tick_size=Decimal("0.1"))
    result = p.price_tick_size * 3
    assert result == Decimal("0.3")
    assert result != 0.30000000000000004


# --- Repr ---

def test_perpetual_repr_contains_symbol():
    p = make_perpetual()
    assert "BTCUSDT" in repr(p)
    assert "PerpetualContract" in repr(p)