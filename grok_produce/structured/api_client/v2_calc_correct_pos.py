from decimal import Decimal, ROUND_DOWN, ROUND_UP
from grok_produce.structured.proof_of_concept_for_order_placing import _req
PRODUCT_TYPE = "usdt-futures"   # lowercase for market endpoints
MARGIN_COIN = "USDT"

def get_contract(symbol: str) -> dict:
    """Fetch contract config for one symbol (DOTUSDT, etc.)."""
    res = _req("GET", "/api/v2/mix/market/contracts",
               params={"productType": PRODUCT_TYPE, "symbol": symbol})
    data = res.get("data") or []
    if not data:
        raise RuntimeError(f"No contract info for {symbol}")
    return data[0]

def quantize_size(symbol: str, desired_size: float, price: float) -> float:
    """
    Returns a size that is:
      - >= minTradeNum
      - >= ceil(minTradeUSDT / price) in step units
      - rounded to 'volumePlace' decimals
      - a multiple of sizeMultiplier
    """
    c = get_contract(symbol)
    volume_place = int(c.get("volumePlace", "0"))
    size_step = Decimal(str(c.get("sizeMultiplier", "1")))
    min_qty = Decimal(str(c.get("minTradeNum", "0")))
    min_usdt = Decimal(str(c.get("minTradeUSDT", "5")))
    px = Decimal(str(price))

    # 1) base candidates
    want = Decimal(str(desired_size))
    need_by_usdt = (min_usdt / px)
    # round need_by_usdt UP to the nearest step
    step_units = (need_by_usdt / size_step).to_integral_value(rounding=ROUND_UP)
    need_by_usdt = step_units * size_step

    base = max(min_qty, need_by_usdt, Decimal("0"))

    # 2) pick the larger of desired vs base
    raw = max(want, base)

    # 3) round DOWN to allowed decimals first
    unit = Decimal(f"1e-{volume_place}") if volume_place > 0 else Decimal("1")
    raw = raw.quantize(unit, rounding=ROUND_DOWN)

    # 4) align to size step (DOWN). If that drops us below constraints, bump one step up.
    stepped = (raw / size_step).to_integral_value(rounding=ROUND_DOWN) * size_step
    if stepped < base:
        stepped = ((base / size_step).to_integral_value(rounding=ROUND_UP) * size_step)

    # 5) final decimal clamp for display/JSON
    return float(stepped.quantize(unit, rounding=ROUND_DOWN))

def compute_position_size(symbol: str, current_balance: float, leverage: float, price: float,
                          position_fraction: float) -> float:
    """
    position_fraction = % of balance you want to deploy (e.g., 0.01 for 1%).
    """
    draft = (Decimal(str(position_fraction)) * Decimal(str(current_balance)) * Decimal(str(leverage))) / Decimal(str(price))
    return quantize_size(symbol, float(draft), price)

print(compute_position_size('DOTUSDT', 71, 10, 4.199, 0.01))