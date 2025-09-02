# ---------- Delayed (on-close) exits ----------
from dataclasses import dataclass, field
from typing import Optional, Dict
import logging
from grok_produce.structured.api_client.v2_bootstrap_client import PRODUCT_TYPE, _req


@dataclass
class DelayedBracket:
    symbol: str
    side: str = "long"      # your use-case
    tp_price: Optional[float] = None
    sl_price: Optional[float] = None
    active: bool = True
    meta: dict = field(default_factory=dict)  # store entry info/order ids if you want

delayed_brackets: Dict[str, DelayedBracket] = {}  # keyed by symbol

def register_delayed_bracket(symbol: str, entry_price: float,
                             tp_pct: float | None = None,
                             sl_pct: float | None = None,
                             tp_abs: float | None = None,
                             sl_abs: float | None = None,
                             side: str = "long"):
    """
    Registers/overwrites the bracket for a symbol.
    If only pct are provided, compute absolute targets from entry_price.
    """
    b = delayed_brackets.get(symbol)
    if b is None:
        b = DelayedBracket(symbol=symbol)
        delayed_brackets[symbol] = b

    b.symbol = symbol
    b.entry_price = float(entry_price)

    # Compute absolutes if needed (long side)
    if tp_abs is None and tp_pct is not None:
        tp_abs = b.entry_price * (1.0 + float(tp_pct))
    if sl_abs is None and sl_pct is not None:
        sl_abs = b.entry_price * (1.0 - float(sl_pct))

    b.tp = float(tp_abs) if tp_abs is not None else getattr(b, "tp", None)
    b.sl = float(sl_abs) if sl_abs is not None else getattr(b, "sl", None)

    b.side = side
    b.active = True
    logging.info(f"[BRACKET] upsert {symbol}: entry={b.entry_price} tp={b.tp} sl={b.sl} side={b.side}")
    return b

def on_candle_close(symbol: str, close_price: float):
    """
    Call this right after you compute a candle close for `symbol`.
    If TP/SL condition is met by close, send a market close and remove the bracket.
    """
    br = delayed_brackets.get(symbol)
    if not br or not br.active:
        return None

    # Long example:
    if br.sl_price and close_price <= br.sl_price:
        # send market close for the long (flash close)
        try:
            _req("POST", "/api/v2/mix/order/close-positions",
                 body={"symbol": symbol, "productType": PRODUCT_TYPE, "holdSide": "long"})
        except e:
            print(e)
        br.active = False
        return {"symbol": symbol, "exit": "SL", "price": close_price}

    if br.tp_price and close_price >= br.tp_price:
        try:
            _req("POST", "/api/v2/mix/order/close-positions",
                 body={"symbol": symbol, "productType": PRODUCT_TYPE, "holdSide": "long"})
        except e:
            print(e)
        br.active = False
        return {"symbol": symbol, "exit": "TP", "price": close_price}

    return None
