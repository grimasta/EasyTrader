# Setup Guide

This guide covers local development setup. Deployment to a remote server
will (later) be covered in `Docs/ARCHITECTURE.md`.

---

## Prerequisites

- Python 3.11+
- A Bitget account with API access enabled (for live or paper trading)
- Git

---

## Before you begin

make a directory for easytrader, somewhere in your user directory, then cd into it.

A virtual environment (conda or venv) is * strongly * recommended:

```bash
# conda
conda create -n easytrader python=3.11
conda activate easytrader
pip install -r requirements.txt

# venv
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Clone and install dependencies

```bash
git clone https://github.com/grimasta/EasyTrader.git
cd EasyTrader
pip install -r requirements.txt
```

---

## Configure your environment

EasyTrader uses a `.env` file for all secrets and environment-specific
configuration. This file is gitignored and must never be committed.

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

Then edit `.env`:

```
# Bitget API credentials
# Create these paper trading: https://www.bitget.com/account/paper
# Required permissions: Read, Trade
# Or use real api keys that can be created at: https://www.bitget.com/account/newapi (* stronly * indavisable)
# IP whitelist recommended for production use
BITGET_API_KEY=your_api_key_here
BITGET_API_SECRET=your_api_secret_here
BITGET_API_PASSPHRASE=your_passphrase_here

# Path for the exit log file (TP/SL events)
# The directory must exist before running the system
EXIT_LOG_FILE=.logs/exit_log.csv

# Binance credentials (optional — Binance venue not yet implemented)
BINANCE_API_KEY=
BINANCE_API_SECRET=
BINANCE_API_PASSPHRASE=
```

Create the logs directory:

```bash
mkdir -p .logs
```

---

## API key security

- Never share your API keys.
- Never commit your `.env` file.
- Use read + trade permissions only ***never withdrawal permissions***.
- Whitelist your IP address on the exchange if running from a fixed IP.
- If you suspect a key has been exposed, revoke it immediately on the
  exchange and generate a new one. 
- Good practice, create API keyes with expiration dates and change them frequently

---

## Run the system

```bash
python main.py
```

The CLI interface (`UIs/CLI`) is under development. Until it is complete,
runtime parameters are configured via `core/config.py` defaults and
`core/Runtimes/Live/live_constants.py`.

---

## Run the tests

```bash
pytest test/ -v
```

---

## Paper trading

To run in paper trading mode, enable the `PAPTRADING` header in
`core/Runtimes/Live/live_constants.py`. This submits orders to Bitget's
paper trading environment using your real API key — no real funds are used.

---

## Persistence backends

EasyTrader will support two persistence backends for kline data:

| Backend | Use case |
|---|---|
| `parquet` | Default. Local files, no infrastructure required. |
| `timescale` | Production. Requires a running TimescaleDB instance. |

Set `persistence_backend` in `core/config.py` or via CLI argument
(CLI not yet implemented).

For `timescale`, set the DSN in `.env`:

```
TIMESCALE_DSN=postgresql://user:password@host:5432/easytrader
```