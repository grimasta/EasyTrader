from dataclasses import dataclass


@dataclass
class Config:
    """
    Runtime configuration for EasyTrader.

    This is the single source of truth for all tunable parameters.
    Defaults are set here. The CLI layer (UIs/CLI) will eventually
    construct a Config instance from parsed arguments and pass it
    into the runtime. No other module should read from live_constants.py
    or hardcode these values.
    """

    # --- Kline buffer ---
    max_indicator_lookback: int = 200
    """Longest indicator window in use, e.g. EMA200. Defines minimum buffer size."""

    kline_buffer_size: int = 400
    """
    In-memory kline buffer capacity per symbol per timeframe.
    Set to 2 * max_indicator_lookback by default, giving a comfortable
    working window while bounding memory use in long-running sessions.
    Must be >= max_indicator_lookback.
    """

    # --- Persistence ---
    persistence_backend: str = "parquet"
    """Persistence backend to use: 'parquet' or 'timescale'."""

    parquet_dir: str = ".data/parquet"
    """Root directory for parquet files. Relative to project root."""

    timescale_dsn: str = ""
    """PostgreSQL DSN for TimescaleDB, e.g. postgresql://user:pass@host/db."""

    # --- Live trading ---
    leverage: int = 10
    """Default leverage for new positions. Capped at InstrumentSpec.max_leverage."""

    strategy_name: str = "best_momentum"
    """Strategy to use for live trading. Must match a key in STRATEGIES dict."""

    # --- Cooldown ---
    skip_day_delay: int = 1
    """Number of candle cycles to skip after a stop loss before re-entering."""

    # --- Failsafe ---
    consecutive_failure_threshold: int = 5
    """Number of consecutive errors before triggering flash-close-all and alert."""

    alert_email: str = ""
    """Email address for urgent alerts. Empty string disables email alerts."""

    def __post_init__(self):
        if self.kline_buffer_size < self.max_indicator_lookback:
            raise ValueError(
                f"kline_buffer_size ({self.kline_buffer_size}) must be >= "
                f"max_indicator_lookback ({self.max_indicator_lookback})"
            )