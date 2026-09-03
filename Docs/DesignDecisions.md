# Design Decisions and Candidate Designs

└── LiveTradingLoop
    │
    ├── MarketDataSource  (abstract) ← BitgetWebSocket implements this
    ├── OrderExecutor     (abstract) ← BitgetOrderExecutor implements this  
    ├── InstrumentRegistry           ← holds your InstrumentSpec objects
    └── Strategy                     ← already abstract

---
    └── Live Trading Loop
        └── KlineBuffer (in-memory, populated by WebSocket)
            └── KlineParser (transforms raw WebSocket frames)

---
    └── Background Persistence (separate concern, separate thread/process)
            └── KlineRepository
                └── gap detection: last persisted timestamp → now
                └── batch fetch from REST at startup
                └── periodic sync every N hours
                └── rate limiter awareness

### ** Dataflow **

    Live:        WebSocket → KlineParser → KlineBuffer → Strategy
    Backtest:    ParquetRepository → KlineBuffer → Strategy