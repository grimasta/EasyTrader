from grok_produce.structured.api_client.v2_bootstrap_client import quantize_price
from grok_produce.structured.api_client.v2_bootstrap_client import _req
import re
from typing import Optional

from grok_produce.structured.live.live_constants import PRODUCT_TYPE, MARGIN_COIN


# assumes you already have: _req(...), PRODUCT_TYPE="USDT-FUTURES", MARGIN_COIN="USDT"
# and (optionally) quantize_price(symbol, price) from earlier



def _parse_duration_to_ms(s: str) -> int:
    """
    '5m' -> 5 * 60 * 1000 ; '15m', '1h', '30s', '2h', '1d' supported
    """
    if not s:
        return 0
    m = re.fullmatch(r"\s*(\d+)\s*([smhdSMHD])\s*", s)
    if not m:
        raise ValueError("duration must look like '5m', '15m', '1h', '30s', '1d'")
    n = int(m.group(1))
    unit = m.group(2).lower()
    mult = {"s": 1000, "m": 60_000, "h": 3_600_000, "d": 86_400_000}[unit]
    return n * mult

def cancel_order(symbol: str, order_id: Optional[str] = None, client_oid: Optional[str] = None):
    """POST /api/v2/mix/order/cancel-order (either orderId or clientOid)."""
    body = {
        "symbol": symbol,
        "productType": PRODUCT_TYPE,   # e.g. "USDT-FUTURES"
        "marginCoin": MARGIN_COIN,     # optional per docs, but nice to include
    }
    if order_id:
        body["orderId"] = order_id
    if client_oid and "orderId" not in body:
        body["clientOid"] = client_oid
    return _req("POST", "/api/v2/mix/order/cancel-order", body=body)  # returns orderId/clientOid on success

def cancel_if_expired(symbol: str, order_id: Optional[str], client_oid: Optional[str], expires_at_ms: int):
    """No-op until `now` >= expires_at_ms, then tries to cancel. Safe to call in your main loop."""
    if not expires_at_ms:
        return None
    now = int(time.time() * 1000)
    if now < expires_at_ms:
        return None
    try:
        return cancel_order(symbol, order_id=order_id, client_oid=client_oid)
    except Exception as e:
        return {"error": str(e)}

def place_limit_long(
    symbol: str,
    size: str,
    price: str | float,
    *,
    duration: str = "5m",            # e.g. "5m", "15m", "1h", "30s"
    tif: str = "gtc",                # "gtc", "post_only", "ioc", "fok"
    client_oid: str | None = None,
    auto_cancel: bool = False
):
    """
    Places a LIMIT Buy (open) with a TTL you control.
    Returns dict with orderId/clientOid and expires_at_ms (if duration given).
    If auto_cancel=True, blocks until TTL passes and cancels if still pending.
    """
    # normalize/quantize price if you have the helper
    try:
        qprice = quantize_price(symbol, price)  # your earlier helper
    except NameError:
        qprice = str(price)

    # Bitget V2 uses 'force' for time-in-force on LIMIT orders:
    #   ioc | fok | gtc (default) | post_only
    # (No native GTD, so we cancel after duration ourselves.)
    body = {
        "symbol": symbol,
        "productType": PRODUCT_TYPE,
        "marginMode": "isolated",
        "marginCoin": MARGIN_COIN,
        "size": str(size),           # base coin amount
        "price": str(qprice),        # limit price
        "side": "buy",
        "tradeSide": "open",         # ignored in one-way mode per docs
        "orderType": "limit",
        "force": tif.lower(),        # <- time in force
    }
    if client_oid:
        body["clientOid"] = client_oid

    print(f"Place LIMIT BUY {symbol} size={size} @ {qprice} tif={body['force']} …")
    res = _req("POST", "/api/v2/mix/order/place-order", body=body)
    data = res.get("data") or {}
    order_id = data.get("orderId")
    coid = data.get("clientOid") or client_oid

    ttl_ms = _parse_duration_to_ms(duration) if duration else 0
    expires_at_ms = int(time.time() * 1000) + ttl_ms if ttl_ms else 0

    out = {
        "apiResponse": res,
        "orderId": order_id,
        "clientOid": coid,
        "expires_at_ms": expires_at_ms,
        "tif": body["force"],
        "price": qprice,
    }

    # Optional: block this call and auto-cancel after TTL if still pending
    if auto_cancel and ttl_ms and body["force"] in ("gtc", "post_only"):
        time.sleep(ttl_ms / 1000.0)
        try:
            # You can check if it's still pending first (orders-pending), or just attempt cancel:
            cancel_res = cancel_order(symbol, order_id=order_id, client_oid=coid)
            out["cancelAfterTTL"] = cancel_res
        except Exception as e:
            out["cancelAfterTTL"] = {"error": str(e)}

    return out

# ---------- Non-blocking TTL cancel scheduler ----------
import heapq, time

class CancelScheduler:
    def __init__(self):
        self._heap = []  # (deadline_ms, symbol, orderId)

    def add(self, symbol: str, order_id: str, ttl_seconds: int):
        deadline = int(time.time() * 1000) + ttl_seconds * 1000
        heapq.heappush(self._heap, (deadline, symbol, order_id))

    def poll(self):
        now = int(time.time() * 1000)
        while self._heap and self._heap[0][0] <= now:
            _, symbol, order_id = heapq.heappop(self._heap)
            try:
                _req("POST", "/api/v2/mix/order/cancel-order",
                     body={"symbol": symbol, "productType": PRODUCT_TYPE, "orderId": order_id})
            except Exception as e:
                # log it; optionally requeue
                pass

# usage in your loop:
# scheduler = CancelScheduler()
# when placing a GTC limit: scheduler.add(symbol, order_id, ttl_seconds=300)
# every tick/iteration: scheduler.poll()