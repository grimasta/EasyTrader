import time
import requests
import pandas as pd
from datetime import datetime, timezone
from typing import List, Dict, Any

BASE_URL = "https://api.bitget.com"

# Map granularity strings to milliseconds (for cursor math & boundary align)
GRAN_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
    "1H": 3_600_000, "2H": 7_200_000, "4H": 14_400_000, "6H": 21_600_000, "12H": 43_200_000,
    "1D": 86_400_000, "3D": 259_200_000, "1W": 604_800_000, "1M": 2_592_000_000
}

def _public_get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.get(BASE_URL + path, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

def _candles_to_df(rows: List[List[str]]) -> pd.DataFrame:
    """Convert Bitget rows to the requested schema; sort oldest→newest."""
    if not rows:
        return pd.DataFrame(columns=['timestamp','open','high','low','close','volume'])
    out = []
    for r in rows:
        ts_ms = int(r[0])
        o, h, l, c = map(float, r[1:5])
        base_vol = float(r[5])  # index[5] = base volume (index[6] = quote)
        out.append([ts_ms, o, h, l, c, base_vol])
    df = pd.DataFrame(out, columns=['timestamp','open','high','low','close','volume'])
    return df.sort_values('timestamp').reset_index(drop=True)

def _floor_to_candle(ts_ms: int, gran_ms: int) -> int:
    return (ts_ms // gran_ms) * gran_ms

def fetch_mix_candles_from_date(
        symbol: str,
        granularity: str,           # e.g., "5m" or "4H"
        start_date: str,            # "YYYY-MM-DD-HH-MM" (UTC)
        product_type: str = "usdt-futures",
        kline_type: str = "MARKET", # or "MARK"/"INDEX"
        page_limit: int = 1000
) -> pd.DataFrame:
    """
    Forward‑paginates /api/v2/mix/market/candles from start_date → now by advancing startTime.
    Each loop passes a *new* startTime so responses don't repeat.
    """
    if granularity not in GRAN_MS:
        raise ValueError(f"Unsupported granularity '{granularity}'")
    step_ms = GRAN_MS[granularity]

    # Parse input as UTC and align to candle boundary (Bitget requires it)
    start_dt = datetime.strptime(start_date, "%Y-%m-%d-%H-%M").replace(tzinfo=timezone.utc)
    cursor = _floor_to_candle(int(start_dt.timestamp() * 1000), step_ms)
    all_rows: List[List[str]] = []
    while True:
        params = {
            "productType": product_type,    # v2 futures product type
            "symbol": symbol,               # e.g., "BTCUSDT"
            "granularity": granularity,     # e.g., "5m" or "4H" (string per docs)
            "kLineType": kline_type,        # MARKET by default
            "limit": str(page_limit),
            "startTime": str(cursor)        # <-- advancing cursor ("shift") each loop
        }
        data = _public_get("/api/v2/mix/market/candles", params).get("data", [])
        if not data:
            break

        # Bitget returns rows in *ascending* order for startTime queries (oldest→newest).
        all_rows.extend(data)

        last_ts = int(data[-1][0])
        next_cursor = last_ts + step_ms
        if next_cursor == cursor or last_ts > datetime.now().timestamp():
            # safety: if server didn't move us forward, avoid infinite loop
            break
        cursor = next_cursor

        # If we got fewer than requested, we've likely reached "now"
        if len(data) < page_limit:
            break

        time.sleep(0.05)  # be polite

    return _candles_to_df(all_rows)

# Convenience wrappers you asked for:
def get_5m_from(symbol: str, start_date: str) -> pd.DataFrame:
    return fetch_mix_candles_from_date(symbol, "5m", start_date)

def get_4h_from(symbol: str, start_date: str) -> pd.DataFrame:
    return fetch_mix_candles_from_date(symbol, "4H", start_date)

# Example:
# df_5m = get_5m_from("BTCUSDT", "2025-08-01-00-00")
# df_4h = get_4h_from("BTCUSDT", "2025-06-01-00-00")
# ---- Example usage ----
if __name__ == "__main__":
    sym = "BTCUSDT"
    start = "2025-08-20-00-00"   # August 1st 2025 00:00 UTC

    df_5m = get_5m_from(sym, start)
    print(sym, "5m from", start, "rows:", df_5m.shape)
    print(df_5m.head(), "\n", df_5m.tail())

    df_4h = get_4h_from(sym, start)
    print(sym, "4h from", start, "rows:", df_4h.shape)
    print(df_4h.head(), "\n", df_4h.tail())
