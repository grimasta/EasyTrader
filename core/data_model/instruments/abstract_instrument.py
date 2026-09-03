from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class AbstractInstrument(ABC):
    """
    Canonical data model for any tradable instrument.

    Holds only fields that are universally meaningful across all instrument
    types (perpetuals, spot, futures, equities, commodities, options).
    Venue-specific parsing and construction live in the venue layer —
    this class has no knowledge of any exchange.

    All price and quantity fields use Decimal to avoid floating-point
    precision errors on order placement.
    """

    # --- Identity ---
    symbol: str
    """Canonical symbol in BASEQUOTE format, e.g. BTCUSDT. No hyphens, no spaces."""

    venue_symbol: str
    """Venue-native identifier, e.g. BTC-USDT-SWAP on OKX. Used for API calls."""

    venue: str
    """Venue identifier, e.g. 'bitget', 'binance', 'okx', 'crypto_com'."""

    instrument_type: str
    """Instrument class: 'perpetual', 'future', 'spot', 'option', 'stock', 'commodity'."""

    base_asset: str
    """The asset being bought or sold, e.g. 'BTC'."""

    quote_asset: str
    """The asset used for pricing, e.g. 'USDT'."""

    is_active: bool
    """Whether the instrument is currently open for trading."""

    # --- Precision (mandatory for order placement on all venues) ---
    price_tick_size: Decimal
    """Minimum price increment. Orders must be multiples of this value."""

    qty_tick_size: Decimal
    """Minimum quantity increment. Orders must be multiples of this value."""

    price_precision: int
    """Number of decimal places for price formatting."""

    qty_precision: int
    """Number of decimal places for quantity formatting."""

    min_qty: Decimal
    """Minimum allowable order size in the base asset."""

    # --- Metadata ---
    fetched_at_ms: int
    """Unix epoch milliseconds when this spec was fetched from the venue."""

    @abstractmethod
    def instrument_category(self) -> str:
        """
        Returns a string identifying the instrument category.
        Implemented by each concrete subclass, e.g. 'perpetual', 'spot'.
        Exists to enforce that AbstractInstrument cannot be instantiated directly.
        """
        ...