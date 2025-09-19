from typing import List, Dict, Any, Optional
import pandas as pd

from grok_produce.structured.live.live_constants import MARGIN_COIN, PRODUCT_TYPE
from grok_produce.structured.api_client.v2_bootstrap_client import _req



def get_positions_all(margin_coin: str = MARGIN_COIN) -> List[Dict[str, Any]]:
    """All open positions across instruments (USDT-M futures)."""
    res = _req("GET", "/api/v2/mix/position/all-position", params={
        "productType": PRODUCT_TYPE,
        "marginCoin": margin_coin,  # optional but helpful
    })
    return res.get("data") or []


def get_position_symbol(symbol: str, margin_coin: str = MARGIN_COIN) -> List[Dict[str, Any]]:
    """Open position(s) for a single instrument, e.g. 'BTCUSDT'."""
    res = _req("GET", "/api/v2/mix/position/single-position", params={
        "symbol": symbol,
        "productType": PRODUCT_TYPE,
        "marginCoin": margin_coin,
    })
    data = res.get("data")
    if isinstance(data, list):
        return data
    elif isinstance(data, dict) and data:
        return [data]
    return []


def _normalize_pos_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten common fields so output is consistent for one-way or hedge mode."""
    out = []
    for p in rows:
        out.append({
            "symbol": p.get("symbol"),
            "holdSide": p.get("holdSide"),                 # 'long'/'short' OR 'buy'/'sell' in one-way
            "size": float(p.get("total", 0) or 0),         # position size (base units)
            "available": float(p.get("available", 0) or 0),
            "avgEntryPrice": float(p.get("avgEntryPrice") or p.get("averageOpenPrice") or 0),
            "markPrice": float(p.get("markPrice") or 0),
            "unrealizedPL": float(p.get("unrealizedPL") or 0),
            "margin": float(p.get("margin") or 0),
            "leverage": float(p.get("leverage") or 0),
            "liqPrice": float(p.get("liquidationPrice") or 0),
            "uTime": p.get("uTime") or p.get("cTime"),
        })
    return out


def positions_df(symbol: Optional[str] = None, margin_coin: str = MARGIN_COIN) -> pd.DataFrame:
    """DataFrame of your open positions. If symbol is None, returns all."""
    rows = (get_position_symbol(symbol, margin_coin) if symbol
            else get_positions_all(margin_coin))
    flat = _normalize_pos_rows(rows)
    cols = ["symbol","holdSide","size","available","avgEntryPrice","markPrice",
            "unrealizedPL","margin","leverage","liqPrice","uTime"]
    return pd.DataFrame(flat, columns=cols)

# ---- examples ----
# All open positions (across instruments)
df_all = positions_df()
print(df_all)

# Per instrument
# df_btc = positions_df("BTCUSDT")
# df_eth = positions_df("ETHUSDT")
# print(df_btc, df_eth, sep="\n")
