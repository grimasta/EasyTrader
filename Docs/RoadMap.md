# Roadmap

Items are grouped by milestone. Within each milestone, order reflects
implementation dependency, earlier items unblock later ones.

Status markers: `[ ]` not started · `[~]` in progress · `[x]` done

---

## Milestone 0 : Foundation (current)

Core data model and project infrastructure.

- [x] Project restructure, clean package hierarchy
- [x] Secrets management via `python-dotenv`
- [x] `.gitignore`, runtime outputs, credentials, IDE files
- [x] CI/CD, GitHub Actions, tests run on every PR
- [x] PR workflow, branch protection, required status checks
- [x] `AbstractInstrument` + `PerpetualContract` dataclasses
- [x] `Kline` (immutable) + `KlineBuffer` (bounded deque)
- [x] `KlineRepository` ABC
- [x] `Config` dataclass, single source of truth for runtime parameters
- [x] 42 passing tests
- [x] `CONTRIBUTING.md`, `SETUP.md`, `ARCHITECTURE.md`, `ROADMAP.md`
- [ ] Populate `core/data_model` package `__init__.py` interfaces
- [ ] Strategy file consolidation, remove duplication across strategies

---

## Milestone 1 : Persistence Layer

Kline storage and retrieval. Enables backtesting from persisted data
and gap-filling on live restart.

- [ ] `ParquetRepository`, implement `KlineRepository` for Parquet files
- [ ] Tests for `ParquetRepository`
- [ ] `PersistenceFactory`, `get_backend(config)` returns correct implementation
- [ ] Background persistence coordinator, gap detection, batch fetch, periodic sync
- [ ] `TimescaleRepository`, implement `KlineRepository` for TimescaleDB
- [ ] TimescaleDB schema and migration script
- [ ] Tests for `TimescaleRepository`
- [ ] update docs

---

## Milestone 2 : Instrument Spec Adoption

Fetch real instrument specs from the venue on startup. Replace hardcoded
constants with values sourced from `PerpetualContract`.

- [ ] `BitgetInstrumentParser`, maps raw API response to `PerpetualContract`
- [ ] Instrument spec fetch on startup (`/api/v2/mix/market/contracts`)
- [ ] `InstrumentRegistry`, holds `PerpetualContract` per symbol
- [ ] `InstrumentRepository`, responsible for passivating perpetual contracts with duration.
- [ ] Dynamic leverage cap, `min(Config.leverage, instrument.max_leverage)`
- [ ] Order quantity precision from `instrument.qty_precision` (replaces hardcoded)
- [ ] Order price precision from `instrument.price_precision` (replaces hardcoded)

---

## Milestone 3 : Live Loop Cleanup

Adopt the data model in the existing live trading loop. Replace
`live_constants.py` with `Config`. Replace file-based cooldown with
order history fetch.

- [ ] Order-history cooldown, replace CSV file read with REST fetch
- [ ] `KlineBuffer` adoption in live loop, replace raw DataFrame passing
- [ ] `PerpetualContract` adoption in live loop, replace constant references
- [ ] `Config` wired into live loop, replace `live_constants` imports
- [ ] Logging, replace `print` statements with `logging`
- [ ] `live_constants.py` deprecated and removed

---

## Milestone 4 : CLI

Command-line interface for configuring and launching the system.

- [ ] `argparse` entry point in `UIs/CLI/`
- [ ] `Config` populated from CLI args with defaults
- [ ] `--dry-run` flag for paper trading mode
- [ ] `--strategy` flag to select strategy by name
- [ ] `--symbols` flag to override default symbol list
- [ ] `--backend` flag to select persistence backend
- [ ] update docs(SETUP.md, README.md)

---

## Milestone 5 : Live Trading Loop Decoupling

Decouple the live loop from `venues/bitget_v2/` behind abstractions.
Prerequisite for adding a second venue.

- [ ] `MarketDataSource` ABC
- [ ] `BitgetWebSocket` implements `MarketDataSource`
- [ ] `OrderExecutor` ABC
- [ ] `BitgetOrderExecutor` implements `OrderExecutor`
- [ ] Live loop imports only ABCs, no venue-specific imports

---

## Milestone 6 : Failsafe and Observability

Production hardening.

- [ ] Failsafe, flash-close-all on N consecutive failures
- [ ] Alert email, SMTP notification on failsafe trigger
- [ ] VPS deployment, Singapore region, systemd service, update setup and architecture docs
- [ ] Grafana dashboard, open positions, running P&L, signal frequency, order hit rate
- [ ] `ruff` linter added to CI

---

## Milestone 7 : Second Venue (Binance)

Extend to a second exchange to validate the venue abstraction.

- [ ] `BinanceInstrumentParser`
- [ ] `BinanceWebSocket` implements `MarketDataSource`
- [ ] `BinanceOrderExecutor` implements `OrderExecutor`
- [ ] Binance credentials in `.env.example`

---

## Beyond v1.0

- Spot instrument support (`Spot` dataclass)
- Additional instrument types (dated futures, options)
- GUI (`UIs/GUI/`)
- Additional strategies and indicators
- Strategy performance analytics