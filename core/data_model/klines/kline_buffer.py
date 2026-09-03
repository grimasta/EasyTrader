from __future__ import annotations

from collections import deque
from decimal import Decimal
from typing import Iterator, Sequence

from core.data_model.klines.kline import Kline


class KlineBuffer:
    """
    Bounded in-memory buffer of Kline objects for a single symbol and timeframe.

    The buffer is populated by KlineParser from a WebSocket feed (live) or
    by KlineRepository from a persistence backend (backtesting). It has no
    knowledge of either source — its only responsibility is to hold klines
    in chronological order up to a fixed capacity.

    When the buffer reaches capacity, the oldest kline is evicted
    automatically to make room for the new one. This bounds memory use
    in long-running sessions regardless of how frequently klines arrive.

    The buffer does not interact with the persistence layer. Persistence
    is a background concern handled by a separate coordinator.

    Args:
        symbol:    Canonical symbol, e.g. 'BTCUSDT'.
        timeframe: Timeframe string, e.g. '5m', '4h'.
        max_size:  Maximum number of klines to hold. Should be set to
                   2 * max_indicator_lookback from Config. Must be >= 1.
    """

    def __init__(self, symbol: str, timeframe: str, max_size: int) -> None:
        if max_size < 1:
            raise ValueError(f"max_size must be >= 1, got {max_size}")
        self._symbol = symbol
        self._timeframe = timeframe
        self._max_size = max_size
        self._klines: deque[Kline] = deque(maxlen=max_size)

    # --- Identity ---

    @property
    def symbol(self) -> str:
        return self._symbol

    @property
    def timeframe(self) -> str:
        return self._timeframe

    @property
    def max_size(self) -> int:
        return self._max_size

    # --- State ---

    def __len__(self) -> int:
        return len(self._klines)

    def is_empty(self) -> bool:
        return len(self._klines) == 0

    def is_ready(self, min_size: int) -> bool:
        """
        Returns True if the buffer holds at least min_size klines.
        Use this to guard indicator calculations that require a minimum
        number of data points before producing a valid result.
        """
        return len(self._klines) >= min_size

    # --- Mutation ---

    def append(self, kline: Kline) -> None:
        """
        Append a kline to the buffer. If the buffer is at capacity,
        the oldest kline is evicted automatically.
        """
        self._klines.append(kline)

    def extend(self, klines: Sequence[Kline]) -> None:
        """
        Append multiple klines in order. Useful for bulk loading from
        a REST endpoint or persistence backend on startup.
        Klines must be in ascending timestamp order.
        """
        for kline in klines:
            self._klines.append(kline)

    def clear(self) -> None:
        """Remove all klines from the buffer."""
        self._klines.clear()

    # --- Access ---

    @property
    def latest(self) -> Kline | None:
        """Most recent kline, or None if the buffer is empty."""
        if self.is_empty():
            return None
        return self._klines[-1]

    @property
    def oldest(self) -> Kline | None:
        """Oldest kline, or None if the buffer is empty."""
        if self.is_empty():
            return None
        return self._klines[0]

    def as_sequence(self) -> list[Kline]:
        """
        Return all klines as a list in ascending timestamp order.
        Returns a copy — mutations to the list do not affect the buffer.
        """
        return list(self._klines)

    def closes(self) -> list[Decimal]:
        """Convenience accessor for close prices in ascending order."""
        return [k.close for k in self._klines]

    def __iter__(self) -> Iterator[Kline]:
        return iter(self._klines)

    def __repr__(self) -> str:
        return (
            f"KlineBuffer(symbol={self._symbol!r}, timeframe={self._timeframe!r}, "
            f"size={len(self._klines)}/{self._max_size})"
        )