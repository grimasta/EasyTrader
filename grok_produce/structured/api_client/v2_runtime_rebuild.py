# ---------- Cold start state rebuild ----------
from datetime import datetime, timedelta, timezone
import zoneinfo
from typing import Dict, Any, List, Tuple, Optional
from grok_produce.structured.api_client.v2_bootstrap_client import _req, MARGIN_COIN, PRODUCT_TYPE
from grok_produce.structured.api_client.entry_guard import seed_open_many

TORONTO_TZ = zoneinfo.ZoneInfo("America/Toronto")

def _utc_ms(dt: datetime) -> int:
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)

def _today_bounds_toronto() -> Tuple[int, int]:
    now_tz = datetime.now(TORONTO_TZ)
    start = now_tz.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return _utc_ms(start), _utc_ms(end)

def _get_all_positions() -> List[Dict[str, Any]]:
    """All current futures positions (any symbol, any side)."""
    res = _req("GET", "/api/v2/mix/position/all-position",
               params={"productType": PRODUCT_TYPE, "marginCoin": MARGIN_COIN})
    return res.get("data") or []

def _latest_open_buy_order_id(symbol: str, lookback_days: int = 7) -> Optional[str]:
    """Find latest executed OPEN/BUY orderId for symbol (recent window)."""
    end_ms = _utc_ms(datetime.utcnow())
    start_ms = _utc_ms(datetime.utcnow() - timedelta(days=lookback_days))
    res = _req("GET", "/api/v2/mix/order/history", params={
        "productType": PRODUCT_TYPE, "symbol": symbol,
        "startTime": str(start_ms), "endTime": str(end_ms), "limit": "100"
    })
    rows = (res.get("data") or {}).get("orderList") or []
    # Keep most recent first
    rows.sort(key=lambda r: int(r.get("cTime", 0)), reverse=True)
    for r in rows:
        # v2 fields vary by mode; prefer tradeSide=open and side in ('buy','open_long')
        if (r.get("tradeSide") == "open") and (r.get("side") in ("buy", "open_long")):
            # ensure filled(ish)
            if r.get("state") in ("filled", "full_fill", "part_filled", "success"):
                return r.get("orderId")
    return None

def _pending_tpsl_for_symbol(symbol: str) -> Dict[str, Optional[str]]:
    """
    Return separate clientOIDs for TP and SL if present among pending plan orders.
    """
    res = _req("GET", "/api/v2/mix/order/orders-plan-pending", params={
        "productType": PRODUCT_TYPE, "planType": "profit_loss", "symbol": symbol, "limit": "100"
    })
    entr = (res.get("data") or {}).get("entrustedList") or []
    tp_oid = None
    sl_oid = None
    for row in entr:
        src = (row.get("orderSource") or "").lower()
        coid = row.get("clientOid")
        # Heuristics per docs: pos_profit_* ==> TP ;  pos_loss_* ==> SL
        if "profit" in src and not tp_oid:
            tp_oid = coid
        if "loss" in src and not sl_oid:
            sl_oid = coid
        # Fallback: if not clear, use which trigger price exists
        if (not tp_oid) and row.get("stopSurplusTriggerPrice"):
            tp_oid = coid
        if (not sl_oid) and row.get("stopLossTriggerPrice"):
            sl_oid = coid
    return {"tp": tp_oid, "sl": sl_oid}

def _tp_sl_executed_today(symbol: str) -> Dict[str, bool]:
    """Check if TP or SL executed since today's start (Toronto)."""
    start_ms, end_ms = _today_bounds_toronto()
    res = _req("GET", "/api/v2/mix/order/orders-plan-history", params={
        "productType": PRODUCT_TYPE, "planType": "profit_loss", "symbol": symbol,
        "startTime": str(start_ms), "endTime": str(end_ms), "limit": "100"
    })
    rows = (res.get("data") or {}).get("entrustedList") or []
    did_tp = any(("profit" in (r.get("orderSource") or "").lower()) and r.get("planStatus") == "executed" for r in rows)
    did_sl = any(("loss"   in (r.get("orderSource") or "").lower()) and r.get("planStatus") == "executed" for r in rows)
    return {"tp": did_tp, "sl": did_sl}

def _entries_today(symbol: str) -> int:
    """
    Count how many executed OPEN/BUY orders occurred today (America/Toronto).
    Uses v2 /orders-history and paginates safely.
    """
    start_ms, end_ms = _today_bounds_toronto()

    params = {
        "productType": PRODUCT_TYPE,   # e.g., "USDT-FUTURES"
        "symbol": symbol,              # e.g., "BTCUSDT"
        "startTime": str(start_ms),
        "endTime": str(end_ms),
        "limit": "100",
    }

    total_rows = []
    while True:
        res = _req("GET", "/api/v2/mix/order/orders-history", params=params)
        data = res.get("data") or {}
        # v2 typically returns {"data": {"entrustedList": [...], "endId": "..."}}
        rows = data.get("entrustedList")
        if rows is None:
            # some SDKs flatten; fallbacks just in case
            rows = data.get("orderList") or res.get("data") or []
        total_rows.extend(rows)

        end_id = data.get("endId")
        if not end_id or len(rows) < int(params["limit"]):
            break
        params["idLessThan"] = end_id  # page older

    # Count executed opens (buy/open_long)
    n = 0
    for r in total_rows:
        trade_side = r.get("tradeSide")
        side = r.get("side")
        state = (r.get("state") or r.get("status") or "").lower()
        executed = state in {"filled", "full_fill", "success", "part_filled", "partial_filled"}
        if trade_side == "open" and side in ("buy", "open_long") and executed:
            n += 1
    return n

def rebuild_runtime_state(SYMBOLS: List[str]) -> Tuple[Dict[str, int], Dict[str, int]]:
    """
    Returns (open_positions, trades_today, skip_day) for the given SYMBOLS.
    open_positions[symbol] = {
        'buy_order_id', 'stop_loss_order_id', 'take_profit_order_id',
        'entry_price', 'amount'
    }
    NOTE: 'stop_loss_order_id' is the SL clientOid, 'take_profit_order_id' is the TP clientOid.
    """
    positions = _get_all_positions()
    open_positions: Dict[str, Any] = {}
    trades_today: Dict[str, int] = {s: {} for s in SYMBOLS}
    skip_day: Dict[str, int] = {s: 0 for s in SYMBOLS}

    # Fill trades_today and skip_day from history
    from datetime import datetime
    today = datetime.now().date()
    for sym in SYMBOLS:
        trades_today[sym][today] = _entries_today(sym)
        executed = _tp_sl_executed_today(sym)
        skip_day[sym] = 1 if executed["sl"] else 0

    # Rebuild open_positions for open LONGs in our symbol set
    for p in positions:
        sym = p.get("symbol")
        if sym not in SYMBOLS:
            continue
        if p.get("holdSide") not in ("long", "buy"):  # focus on long side per your strategy
            continue
        amount = float(p.get("total") or p.get("available") or 0.0)
        if amount <= 0:
            continue

        entry_price = float(p.get("openPriceAvg") or p.get("avgEntryPrice") or p.get("breakEvenPrice") or 0.0)
        buy_order_id = _latest_open_buy_order_id(sym)
        tpsl = _pending_tpsl_for_symbol(sym)

        open_positions[sym] = {
            "buy_order_id": buy_order_id,
            "stop_loss_order_id": tpsl.get("sl"),       # SL clientOid (if pending)
            "take_profit_order_id": tpsl.get("tp"),     # TP clientOid (if pending)
            "entry_price": entry_price,
            "amount": amount,
        }
    open_syms = [s for s, pos in positions.items() if pos and float(pos.get("amount", 0)) != 0]
    seed_open_many(open_syms)
    return trades_today, skip_day
