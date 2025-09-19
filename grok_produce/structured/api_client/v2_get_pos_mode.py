from grok_produce.structured.api_client.v2_bootstrap_client import _req


def get_pos_mode(symbol: str) -> str:
    r = _req("GET", "/api/v2/mix/account/account",
             params={"symbol": symbol, "productType": "USDT-FUTURES", "marginCoin": "USDT"})
    data = r.get("data") or {}
    return (data.get("posMode") or "one_way_mode").lower()