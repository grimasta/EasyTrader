# Architecture

## Overview

EasyTrader is a modular algorithmic trading system for crypto perpetual
futures. The design prioritises separation of concerns: the core data model
has no knowledge of any exchange, the venue layer has no knowledge of the
trading engine, and persistence is a background concern that never blocks
the live trading loop.

---

## Package Structure

```
EasyTrader/
├── core/
│   ├── config.py                   # Single source of truth for all runtime parameters
│   ├── data_model/
│   │   ├── instruments/            # AbstractInstrument, PerpetualContract
│   │   └── klines/                 # Kline, KlineBuffer
│   ├── persistence/
│   │   └── kline_repository.py     # KlineRepository ABC
│   └── Runtimes/
│       ├── Live/                   # Live trading loop
│       └── Backtest/               # Backtesting runtime
├── venues/
│   └── bitget_v2/
│       ├── api_client/             # REST client, order placement, bracket management
│       └── websocket/              # Live kline WebSocket manager
├── strategies/                     # Strategy implementations
├── technical_indicators/           # Indicator calculations (RSI, EMA, MACD, etc.)
├── UIs/
│   ├── CLI/                        # Command-line interface (under development)
│   └── GUI/                        # Graphical interface (planned)
└── test/                           # Mirrors source tree
```

---

## Core Principles

### The data model knows nothing about venues

`core/data_model/` contains only canonical data structures — `PerpetualContract`,
`Kline`, `KlineBuffer`. These classes have no imports from `venues/`.
Venue-specific parsing (field name mapping, type casting, unit conversion)
lives entirely in the venue layer and produces data model objects as output.

### Venues know about the data model, not each other

Each venue package (`venues/bitget_v2/`, future `venues/binance/`) imports
from `core/data_model/` to produce canonical objects. Venues never import
from each other.

### Persistence never blocks the live loop

The live trading loop reads exclusively from in-memory `KlineBuffer` objects.
It never waits on a database write. Persistence is handled by a background
coordinator on its own cadence — gap-filling on startup, periodic sync
thereafter. See the Persistence section below.

### Config is the single source of truth

All tunable parameters live in `core/config.py`. No magic numbers, hardcoded
paths, or constants in business logic. The CLI layer will eventually populate
`Config` from command-line arguments; until then, defaults in `Config` apply.

---

## Data Flow

### Live trading

```
Bitget WebSocket
    └── KlineParser          (venue layer — transforms raw frames to Kline objects)
            └── KlineBuffer  (core — bounded in-memory deque, per symbol per timeframe)
                    └── Strategy.check_signals()
                            └── OrderExecutor    (venue layer — places orders via REST)
```

### Backtesting

```
KlineRepository.read()       (persistence layer — reads from Parquet or TimescaleDB)
    └── KlineBuffer          (same core object as live — strategies are unaware of source)
            └── Strategy.check_signals()
```

The `KlineBuffer` is the seam that makes backtesting and live trading use
identical strategy code. The strategy never knows whether its data came from
a WebSocket or a file.

### Background persistence

```
Background coordinator (separate thread)
    └── KlineRepository.latest_timestamp_ms()   # detect gap
    └── REST batch fetch                         # fill gap at startup
    └── KlineRepository.write(buffer)            # periodic sync
```

---

## Instrument Model

```
AbstractInstrument (ABC, @dataclass)
    └── PerpetualContract      # crypto perpetual futures — current use case
    └── Spot                   # planned
    └── Future                 # planned (dated expiry)
    └── Option                 # planned (Greeks-based model)
```

`AbstractInstrument` holds only fields universal across all instrument types:
identity, precision, minimum order size. `PerpetualContract` extends with
leverage bounds, margin model, fees, and funding parameters.

`PerpetualContract` objects are constructed by venue-specific parsers.
The rest of the system works with `PerpetualContract` without knowing which
venue produced it.

---

## Persistence Layer

```
KlineRepository (ABC)
    └── ParquetRepository      # implemented — local Parquet files
    └── TimescaleRepository    # planned — PostgreSQL + TimescaleDB extension
```

The active backend is selected by `Config.persistence_backend` and
instantiated by `PersistenceFactory` (planned). The live trading loop
and strategy code import only `KlineRepository` — they never reference
a concrete backend.

### Parquet file layout

```
.data/parquet/
    BTCUSDT/
        5m.parquet
        4h.parquet
    ETHUSDT/
        5m.parquet
        4h.parquet
```

Each file contains rows with columns:
`timestamp_ms | open | high | low | close | volume`

Symbol and timeframe are encoded in the file path, not as columns,
keeping individual files thin.

### TimescaleDB schema (planned)

One hypertable partitioned by time, indexed on `(symbol, timeframe)`:

```sql
CREATE TABLE klines (
    timestamp_ms  BIGINT        NOT NULL,
    symbol        TEXT          NOT NULL,
    timeframe     TEXT          NOT NULL,
    open          NUMERIC(20,8) NOT NULL,
    high          NUMERIC(20,8) NOT NULL,
    low           NUMERIC(20,8) NOT NULL,
    close         NUMERIC(20,8) NOT NULL,
    volume        NUMERIC(20,8) NOT NULL,
    PRIMARY KEY (timestamp_ms, symbol, timeframe)
);
SELECT create_hypertable('klines', 'timestamp_ms');
CREATE INDEX ON klines (symbol, timeframe, timestamp_ms DESC);
```

---

## Live Trading Loop

The live loop is candle-close driven. On each 5m candle close:

1. Update `KlineBuffer` for each symbol.
2. Check `EntryGuard` — skip symbols on cooldown.
3. Evaluate `Strategy.check_signals()` against the buffer.
4. If signal: fetch balance, compute position size, place limit order.
5. `BracketActor` monitors open positions for TP/SL thresholds via WebSocket.
6. On threshold cross: place reduce-only market order to close.

The exchange never knows about TP/SL thresholds — all bracket management
is local. On restart, the loop rebuilds bracket state from open positions
fetched via REST.

---

## Planned: Live Trading Loop Decoupling

The current live loop has direct imports from `venues/bitget_v2/`.
The target architecture decouples it behind abstractions:

```
LiveTradingLoop
    ├── MarketDataSource (ABC) ← BitgetWebSocket implements this
    ├── OrderExecutor    (ABC) ← BitgetOrderExecutor implements this
    ├── InstrumentRegistry     ← holds PerpetualContract objects, fetched on startup
    └── Strategy         (ABC) ← already implemented
```

This allows the loop to operate against any venue without modification.

---

## Deployment

The system will be designed to run on a Linux VPS in:
Southeast Asia (Singapore region) to minimise latency to Bitget's matching engine.
or other locations to minimise latency to the target exchange. 

in general it is inadvisable to run from home/office as a home connection
introduces 200-300ms round-trip latency on REST calls; a ''local'' VPS
reduces this to 5-15ms.

Observability via Grafana + TimescaleDB is planned for the production
deployment (open positions, running P&L, signal frequency, order hit rate).