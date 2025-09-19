from grok_produce.structured.live.live_constants import PRODUCT_TYPE
from grok_produce.structured.api_client.v2_bootstrap_client import _req


def flash_close_positions(symbol: str, hold_side: str | None = None):
    # Market-close positions quickly; omit holdSide to close both, or pass "long"/"short"
    body = {"symbol": symbol, "productType": PRODUCT_TYPE}
    if hold_side:
        body["holdSide"] = hold_side
    return _req("POST", "/api/v2/mix/order/close-positions", body=body)  # “flash close” :contentReference[oaicite:2]{index=2}
