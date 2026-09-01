# ------------ CONFIG ------------
import time

from core.Runtimes.Live.live_constants import PRODUCT_TYPE, MARGIN_COIN
from venues.bitget_v2.api_client.v2_bootstrap_client import _req


# ------------ HELPERS ------------
def _get_pending_buy_order_id(symbol: str) -> str | None:
    """Most recent pending BUY/OPEN order id (live or partially_filled)."""
    ids = []
    for st in ("live", "partially_filled"):
        res = _req("GET", "/api/v2/mix/order/orders-pending", params={
            "productType": PRODUCT_TYPE,
            "symbol": symbol,
            "status": st,
            "limit": "100",
        })
        data = (res.get("data") or {})
        rows = data.get("entrustedList") or []
        for o in rows:
            # V2 uses side=buy/sell and tradeSide=open/close (or side=open_long/close_short on v1)
            side = o.get("side")
            trade_side = o.get("tradeSide")
            if (trade_side in (None, "open")) and (side in ("buy", "open_long")):
                ids.append(o)
    if not ids:
        return None
    ids.sort(key=lambda x: int(x.get("cTime") or 0))
    return ids[-1].get("orderId")

def _get_last_entry_order_id_from_history(symbol: str, lookback_hours: int = 72) -> str | None:
    """
    Most recent executed BUY/OPEN order id from futures order history (last N hours).
    Uses the correct V2 endpoint: /api/v2/mix/order/orders-history
    """
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - lookback_hours * 3600 * 1000

    res = _req("GET", "/api/v2/mix/order/orders-history", params={
        "productType": PRODUCT_TYPE,   # e.g., "USDT-FUTURES"
        "symbol": symbol,              # e.g., "BTCUSDT"
        "startTime": str(start_ms),
        "endTime": str(now_ms),
        "limit": "100",                # max 100 per page
    })

    data = res.get("data") or {}
    rows = data.get("entrustedList", []) or res.get("data", []) or []  # some SDKs expose the list directly
    if type(rows) is not list:
        rows = []
    # Keep only executed open-side buys (V2 uses side=buy/sell, tradeSide=open/close)
    cand = [o for o in rows if (o.get("tradeSide") == "open" and o.get("side") in ("buy", "open_long"))]
    if not cand:
        return None

    cand.sort(key=lambda x: int(x.get("cTime") or 0))
    return cand[-1].get("orderId")

def _get_pending_tpsl_client_oids(symbol: str) -> tuple[str | None, str | None]:
    """
    Returns (tp_client_oid, sl_client_oid) from pending TPSL plans.
    We pick the most recently created profit_loss plan for the symbol.
    """
    res = _req("GET", "/api/v2/mix/order/orders-plan-pending", params={
        "productType": PRODUCT_TYPE,
        "symbol": symbol,
        "planType": "profit_loss",
        "limit": "100",
    })
    rows = ((res.get("data") or {}).get("entrustedList")) or []
    if not rows:
        return (None, None)
    rows.sort(key=lambda r: int(r.get("cTime") or 0))
    row = rows[-1]
    tp_oid = row.get("stopSurplusClientOid") or row.get("clientOid")
    sl_oid = row.get("stopLossClientOid") or row.get("clientOid")
    return (tp_oid, sl_oid)

def _get_position(symbol: str) -> tuple[float | None, float | None]:
    """(avgEntryPrice, size) for current position (one-way long/buy preferred)."""
    res = _req("GET", "/api/v2/mix/position/single-position", params={
        "symbol": symbol,
        "productType": PRODUCT_TYPE,
        "marginCoin": MARGIN_COIN,
    })
    data = res.get("data")
    rows = data if isinstance(data, list) else ([data] if data else [])
    # Prefer long/buy; if one-way, holdSide may be 'buy' or None
    pick = None
    for p in rows:
        hs = p.get("holdSide")
        if hs in ("long", "buy", None):
            pick = p
            break
    if not pick:
        return (None, None)
    entry = pick.get("avgEntryPrice") or pick.get("averageOpenPrice")
    size = pick.get("total")  # base units
    return (float(entry) if entry else None, float(size) if size else None)

# ------------ MAIN API ------------
def open_order_summary(symbol: str) -> dict:
    """
    Returns:
      {
        'symbol': ...,
        'buy_order_id': ... or None,
        'stop_loss_order_id': ...,        # SL client OID
        'take_profit_order_id': ...,      # TP client OID
        'entry_price': float or None,
        'amount': float or None
      }
    """
    buy_id = _get_pending_buy_order_id(symbol)
    if not buy_id:
        # If entry is already filled (market), pull most recent buy/open from history
        buy_id = _get_last_entry_order_id_from_history(symbol)

    tp_oid, sl_oid = _get_pending_tpsl_client_oids(symbol)
    entry, amt = _get_position(symbol)

    return {
        "symbol": symbol,
        "buy_order_id": buy_id,
        "stop_loss_order_id": sl_oid,
        "take_profit_order_id": tp_oid,
        "entry_price": entry,
        "amount": amt,
    }

def open_order_summary_for(symbols: list[str]) -> list[dict]:
    """Batch version for multiple instruments."""
    open_orders = [open_order_summary(sym) for sym in symbols]
    empty_orders = []
    for order in open_orders:
        if order['stop_loss_order_id'] is None:
            empty_orders.append(order)
    for order in empty_orders:
        open_orders.remove(order)

    return open_orders

# --------- Example ---------
# symbols = ["BTCUSDT", "ETHUSDT", "DOGEUSDT", "SOLUSDT", "XRPUSDT"]
# print(open_order_summary_for(symbols))