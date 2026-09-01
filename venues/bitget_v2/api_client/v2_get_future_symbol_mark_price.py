from venues.bitget_v2.api_client.v2_bootstrap_client import _req
from decimal import Decimal


def get_future_symbol_mark_price(symbol: str):
    return float(get_futures_prices(symbol)['mark'])


def get_futures_prices(symbol: str):
    """Returns last, index, and mark for a futures symbol like 'BTC'."""
    r = _req("GET", "/api/v2/mix/market/symbol-price",
             params={"productType": "USDT-FUTURES", "symbol": symbol})
    d = (r.get("data") or [{}])[0]
    return {
        "last":  Decimal(d["price"]),      # latest traded price
        "index": Decimal(d["indexPrice"]), # index
        "mark":  Decimal(d["markPrice"]),  # mark price
        "ts":    int(d["ts"]),
        "symbol": d.get("symbol", symbol),
    }
