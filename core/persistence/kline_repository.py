from __future__ import annotations

from abc import ABC, abstractmethod

from core.data_model.klines.kline import Kline
from core.data_model.klines.kline_buffer import KlineBuffer


class KlineRepository(ABC):
    """
    Abstract persistence interface for kline data.

    Implementations write klines from a KlineBuffer to a backend
    (Parquet, TimescaleDB) and read them back as lists of Kline objects.
    The live trading loop never interacts with this class — persistence
    is a background concern handled by a separate coordinator.

    Implementations: ParquetRepository, TimescaleRepository.
    """

    @abstractmethod
    def write(self, buffer: KlineBuffer) -> None:
        """
        Persist all klines currently held in the buffer.
        The repository sources symbol and timeframe from the buffer.
        Implementations should be idempotent — writing the same kline
        twice must not produce duplicates.
        """
        ...

    @abstractmethod
    def read(
        self,
        symbol: str,
        timeframe: str,
        from_ms: int,
        to_ms: int,
    ) -> list[Kline]:
        """
        Read klines for a symbol and timeframe within a time range.
        Returns klines in ascending timestamp order.
        Returns an empty list if no data exists for the given range.

        Args:
            symbol:    Canonical symbol, e.g. 'BTCUSDT'.
            timeframe: Timeframe string, e.g. '5m', '4h'.
            from_ms:   Range start, inclusive, Unix epoch milliseconds.
            to_ms:     Range end, inclusive, Unix epoch milliseconds.
        """
        ...

    @abstractmethod
    def latest_timestamp_ms(self, symbol: str, timeframe: str) -> int | None:
        """
        Return the timestamp_ms of the most recently persisted kline
        for a given symbol and timeframe, or None if no data exists.
        Used by the persistence coordinator to detect gaps on startup.
        """
        ...