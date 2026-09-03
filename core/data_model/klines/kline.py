from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Kline:
    """
    A single OHLCV candlestick. Immutable — a kline is a historical fact.

    A kline has no knowledge of the symbol it belongs to or the timeframe
    it represents. That context is carried by KlineBuffer, which owns the
    collection and knows its symbol and timeframe.

    All price and volume fields use Decimal to avoid floating-point
    precision errors in indicator calculations and order placement.
    """

    timestamp_ms: int
    """Opening timestamp of the candle in Unix epoch milliseconds."""

    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal