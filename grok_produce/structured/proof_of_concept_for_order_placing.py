import os, time, json, hmac, base64, hashlib, requests
from decimal import Decimal
from typing import Any, Dict, Optional, List

from grok_produce.structured.api_client import API_SECRET, API_PASSPHRASE, API_KEY

BASE_URL = "https://api.bitget.com"
SIM_HEADERS = {"PAPTRADING": "1"}
PRODUCT_TYPE_V2 = "usdt-futures"           # v2 productType
PRODUCT_TYPE_V1 = "umcbl"                  # v1 productType
MARGIN_COIN = "USDT"
PRODUCT_TYPE = "USDT-FUTURES"
PRODUCT_TYPE_CAPS = "USDT-FUTURES"   # for most V2 endpoints
PRODUCT_TYPE_LOWER = "usdt-futures"  # some plan endpoints show lowercase in docs
TARGET_COINS = {
    'BTC', 'ETH', 'SOL', 'DOGE',
    'XRP', 'BNB', 'TRX', 'ADA',
    'LINK',
    # 'HYPE',
    'DOT',
    # 'KSM',
    # 'HNT',
    # 'AAVE',
    # 'SUI',
    'AVAX',
    # 'HBAR', 'SEI',
    'ICP',
    'LTC',
    # 'TAO',
    # 'INJ', 'TIA', 'WLD',
    'NEAR'
}

def _ts_ms() -> str:
    return str(int(time.time() * 1000))

# --- Canonical query encoding (sorted!) ---
def _q(params: Optional[Dict[str, Any]]) -> str:
    if not params:
        return ""
    from urllib.parse import urlencode, quote_plus
    # sort keys for stable signing; bitget expects identical query in both places
    items = []
    for k in sorted(params.keys()):
        v = params[k]
        if isinstance(v, list):
            for vv in v:
                items.append((k, vv))
        else:
            items.append((k, v))
    # urlencode uses quote_plus by default; keep it consistent
    return "?" + urlencode(items, doseq=True, quote_via=quote_plus)

# --- Server time (ms) to avoid clock skew ---
_server_time_ms: Optional[int] = None
_server_time_last: float = 0.0

def _now_ms() -> str:
    global _server_time_ms, _server_time_last
    # refresh server time every 30s
    if (_server_time_ms is None) or (time.time() - _server_time_last > 30):
        try:
            r = requests.get(BASE_URL + "/api/v2/public/time", timeout=10)
            r.raise_for_status()
            data = r.json().get("data", {})
            # Bitget returns {"serverTime": 169...}
            sv = data.get("serverTime") or data.get("timestamp") or data.get("time")
            _server_time_ms = int(str(sv))
            _server_time_last = time.time()
        except Exception:
            # fallback to local if public/time fails
            _server_time_ms = int(time.time() * 1000)
            _server_time_last = time.time()
    return str(_server_time_ms + int((time.time() - _server_time_last) * 1000))

def _sign(secret: str, prehash: str) -> str:
    import hmac, hashlib, base64
    return base64.b64encode(hmac.new(secret.encode(), prehash.encode(), hashlib.sha256).digest()).decode()

# def _auth_headers(method: str, request_path_with_query: str, body: Optional[dict]) -> Dict[str, str]:
#     ts = _now_ms()  # << use server-synced ms timestamp
#     body_str = "" if (not body or method.upper() == "GET") else json.dumps(body, separators=(",", ":"), ensure_ascii=False)
#     prehash = f"{ts}{method.upper()}{request_path_with_query}{body_str}"
#     headers = {
#         "ACCESS-KEY": API_KEY,
#         "ACCESS-SIGN": _sign(API_SECRET, prehash),
#         "ACCESS-TIMESTAMP": ts,
#         "ACCESS-PASSPHRASE": API_PASSPHRASE,
#         "Content-Type": "application/json",
#     }
#     headers.update(SIM_HEADERS)  # PAPTRADING: '1'
#     return headers
#
# def _req(method: str, path: str, *, params: Optional[dict] = None, body: Optional[dict] = None):
#     qp = _q(params)
#     request_path_with_query = path + qp                  # exact string used for signing
#     url = BASE_URL + request_path_with_query             # and exact same string sent to server
#     headers = _auth_headers(method, request_path_with_query, body)
#
#     try:
#         if method.upper() == "GET":
#             r = requests.get(url, headers=headers, timeout=20)         # NOTE: no params= here
#         else:
#             payload = json.dumps(body or {}, separators=(",", ":"), ensure_ascii=False)
#             r = requests.post(url, headers=headers, data=payload, timeout=20)
#         if not (200 <= r.status_code < 300):
#             raise requests.HTTPError(f"{r.status_code} {r.reason}: {r.text}", response=r)
#         return r.json()
#     except requests.HTTPError:
#         raise

def _auth_headers(method: str, request_path_with_query: str, payload_str: str) -> Dict[str, str]:
    ts = _now_ms()
    prehash = f"{ts}{method.upper()}{request_path_with_query}{payload_str}"
    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": _sign(API_SECRET, prehash),
        "ACCESS-TIMESTAMP": ts,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
        "Content-Type": "application/json",
        **SIM_HEADERS,   # PAPTRADING: '1'
    }

def _req(method: str, path: str, *, params: Optional[dict] = None, body: Optional[dict] = None):
    qp = _q(params)
    request_path_with_query = path + qp
    url = BASE_URL + request_path_with_query

    # one canonical payload string
    if method.upper() == "GET":
        payload_str = ""
    else:
        payload_str = json.dumps(body or {}, separators=(",", ":"), ensure_ascii=False)

    headers = _auth_headers(method, request_path_with_query, payload_str)

    if method.upper() == "GET":
        r = requests.get(url, headers=headers, timeout=20)
    else:
        r = requests.post(url, headers=headers, data=payload_str, timeout=20)

    if not (200 <= r.status_code < 300):
        raise requests.HTTPError(f"{r.status_code} {r.reason}: {r.text}", response=r)
    return r.json()


# ---------- Create Unique IDs and Monitor them ------
import uuid
from decimal import Decimal, ROUND_DOWN

def make_client_oid(prefix: str) -> str:
    # compact, unique, human-readable
    return f"{prefix}-{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}"

_contract_cache: dict[str, dict] = {}

def get_contract(symbol: str) -> dict:
    if symbol not in _contract_cache:
        res = _req("GET", "/api/v2/mix/market/contracts",
                   params={"productType": "usdt-futures", "symbol": symbol})
        data = res.get("data") or []
        if not data:
            raise RuntimeError(f"No contract info for {symbol}")
        _contract_cache[symbol] = data[0]
    return _contract_cache[symbol]

def quantize_price(symbol: str, price: float | str) -> str:
    c = get_contract(symbol)
    places = int(c.get("pricePlace", "4"))
    step_units = Decimal(str(c.get("priceEndStep", "1")))  # usually "1"
    unit = Decimal(f"1e-{places}")
    step = unit * step_units
    d = Decimal(str(price)).quantize(unit, rounding=ROUND_DOWN)
    d = ((d / step).to_integral_value(rounding=ROUND_DOWN) * step)
    return f"{d:.{places}f}"

def get_pos_mode(symbol: str) -> str:
    r = _req("GET", "/api/v2/mix/account/account",
             params={"symbol": symbol, "productType": "USDT-FUTURES", "marginCoin": "USDT"})
    data = r.get("data") or {}
    return (data.get("posMode") or "one_way_mode").lower()

# ---------- Market: list futures contracts ----------
def list_umcbl_contracts() -> List[Dict[str, Any]]:
    # v2
    try:
        res = _req("GET", "/api/v2/mix/market/contracts", params={"productType": PRODUCT_TYPE_V2})
        if res.get("data") is not None:
            return res["data"]
    except Exception:
        pass
    # v1 fallback
    res = _req("GET", "/api/mix/v1/market/contracts", params={"productType": PRODUCT_TYPE_V1})
    return res.get("data", [])

def filter_target_symbols(contracts: List[Dict[str, Any]]) -> List[str]:
    out = []
    for c in contracts:
        sym = c.get("symbol") or c.get("symbolName") or ""
        for tc in TARGET_COINS:
            if tc in sym[0:4]:
                out.append(sym)
        # if sym.endswith("_UMCBL"):  # USDT-M perp
        #     base = sym.split("USDT")[0].replace("/", "")
        #     if base in TARGET_COINS:
        #         out.append(sym)
    return sorted(out)

# # 1) Public time (no auth, should work)
# print(requests.get(BASE_URL + "/api/v2/public/time", timeout=10).json())
#
# # 2) Auth ping – get account list for USDT-FUTURES (should return code 00000)
# print(_req("GET", "/api/v2/mix/account/accounts",
#            params={"productType":"USDT-FUTURES", "marginCoin":"USDT"}))
#
# # 3) List contracts (public)
# print(_req("GET", "/api/v2/mix/market/contracts", params={"productType":"usdt-futures"}))
# exit()

# ---------- Account: set isolated & leverage ----------

def set_margin_mode_isolated(symbol: str):
    """
    V2 requires: symbol WITHOUT _UMCBL, productType, marginCoin, marginMode.
    Fails (400) if you have open orders/positions on that symbol.
    """
    body = {
        "symbol": symbol,                 # e.g. "XRPUSDT"
        "productType": PRODUCT_TYPE, # USDT-M futures
        "marginCoin": MARGIN_COIN,
        "marginMode": "isolated",
    }
    print("Set margin mode: isolated …")
    # print(_req("POST", "/api/v2/mix/account/set-margin-mode", body={
    #     "symbol": symbol,
    #     "productType": PRODUCT_TYPE,
    #     "marginCoin": MARGIN_COIN,
    #     "marginMode": "isolated"
    # }))  # must have no open orders/positions to succeed. :contentReference[oaicite:3]{index=3}
    return _req("POST", "/api/v2/mix/account/set-margin-mode", body=body)


def set_leverage(symbol: str, leverage: int = 5):
    """
    V2 leverage: include productType & marginCoin. 'leverage' is fine for one-way or same L/S.
    """
    body = {
        "symbol": symbol,
        "productType": PRODUCT_TYPE,
        "marginCoin": MARGIN_COIN,
        "leverage": str(leverage),
        # if using hedge mode and different L/S, send longLeverage/shortLeverage instead.
    }
    print(f"Set leverage {leverage}x …")
    # print(_req("POST", "/api/v2/mix/account/set-leverage", body={
    #     "symbol": symbol,
    #     "productType": PRODUCT_TYPE,
    #     "marginCoin": MARGIN_COIN,
    #     "leverage": "5"
    # }))
    return _req("POST", "/api/v2/mix/account/set-leverage", body=body)

# sample_out_from_place_market_long = {'code': '00000', 'msg': 'success', 'requestTime': 1755894878623,
#                                      'data': {'clientOid': '1342885941014003712', 'orderId': '1342885941005615105'}}
def place_market_long(symbol: str, size: str, client_oid: str | None = None):
    """
    V2 place order: include productType + marginMode + marginCoin.
    Use 'side' + 'tradeSide' (open) for hedge; tradeSide ignored in one-way.
    """
    body = {
        "symbol": symbol,
        "productType": PRODUCT_TYPE,
        "marginMode": "isolated",
        "marginCoin": MARGIN_COIN,
        "size": size,                # base coin amount, e.g. "0.001"
        "side": "buy",
        "tradeSide": "open",
        "orderType": "market",
        "timeInForceValue": "normal",
    }
    print("Place market BUY …")
    # order = _req("POST", "/api/v2/mix/order/place-order", body={
    #     "symbol": symbol,
    #     "productType": PRODUCT_TYPE,
    #     "marginMode": "isolated",
    #     "marginCoin": MARGIN_COIN,
    #     "size": size,          # XRP size is in *base coin units*; 0.001 is too tiny for XRP
    #     "side": "buy",
    #     "tradeSide": "open",
    #     "orderType": "market",
    #     "timeInForceValue": "normal",
    # })
    # print(order)
    if client_oid:
        body["clientOid"] = client_oid
    return _req("POST", "/api/v2/mix/order/place-order", body=body)


def get_entry_price(symbol: str) -> float | None:
    """
    Read your position to compute TP/SL prices. V2 queries by symbol (no suffix) + productType.
    """
    # get entry price (for TP/SL calculation)
    pos = _req("GET", "/api/v2/mix/position/single-position",
               params={"symbol": symbol, "productType": PRODUCT_TYPE, "marginCoin": MARGIN_COIN})
    # print(pos)
    # exit()
    items = pos.get("data") if isinstance(pos.get("data"), list) else [pos.get("data")]
    entry = None
    for p in items or []:
        ep = (p or {}).get("openPriceAvg") or (p or {}).get("openPriceAvg")
        if ep:
            entry = float(ep);
            return entry
            break
    return None


PRODUCT_TYPE = "USDT-FUTURES"

def _plan_lookup(symbol: str, *, client_oid: str, kind: str):
    """
    kind: 'tp' or 'sl'
    """
    assert kind in ("tp", "sl")
    plan_type = "profit_loss"  # per Bitget for TPSL plans
    # pending
    p = _req("GET", "/api/v2/mix/order/orders-plan-pending", params={
        "productType": PRODUCT_TYPE,
        "planType": plan_type,
        "symbol": symbol,
        "clientOid": client_oid,
        "limit": "50",
    })
    entr = ((p.get("data") or {}).get("entrustedList") or [])
    if entr:
        row = entr[0]
        return {
            "status": "live",
            "side": kind,
            "orderId": row.get("orderId"),
            "clientOid": row.get("clientOid"),
            "triggerPrice": row.get("stopSurplusTriggerPrice") if kind=="tp" else row.get("stopLossTriggerPrice"),
            "triggerType": row.get("stopSurplusTriggerType") if kind=="tp" else row.get("stopLossTriggerType"),
            "uTime": row.get("uTime"),
        }

    # history
    h = _req("GET", "/api/v2/mix/order/orders-plan-history", params={
        "productType": PRODUCT_TYPE,
        "planType": plan_type,
        "symbol": symbol,
        "clientOid": client_oid,
        "limit": "50",
        # you could add "planStatus": "executed" to show only fired ones
    })
    hlist = ((h.get("data") or {}).get("entrustedList") or [])
    if not hlist:
        return {"status": "not_found", "side": kind, "clientOid": client_oid}

    row = hlist[0]
    status = row.get("planStatus")  # executed | cancelled | fail_execute
    detail = {
        "status": status,
        "side": kind,
        "orderId": row.get("orderId"),
        "clientOid": row.get("clientOid"),
        "executeOrderId": row.get("executeOrderId"),
        "executePrice": row.get("executePrice"),
        "cTime": row.get("cTime"),
        "uTime": row.get("uTime"),
    }

    # drill into the actual execution if it fired
    exec_id = row.get("executeOrderId")
    if status == "executed" and exec_id:
        try:
            od = _req("GET", "/api/v2/mix/order/detail",
                      params={"productType": PRODUCT_TYPE, "symbol": symbol, "orderId": exec_id})
            detail["executionOrder"] = od.get("data") or {}
        except Exception:
            pass
        try:
            fills = _req("GET", "/api/v2/mix/order/fills",
                         params={"productType": PRODUCT_TYPE, "symbol": symbol, "orderId": exec_id})
            detail["fills"] = fills.get("data") or []
        except Exception:
            pass
    return detail

# order status check output (_plan_lookup output)
sample_output_for_1342838604632178688 = \
    {
        'status': 'executed', 'side': 'sl', 'orderId': '1342838604632178688',
         'clientOid': 'sl-xrpusdt-long-1755883591826-b4836a', 'executeOrderId': '1342843790087520257',
         'executePrice': '', 'cTime': '1755883592756', 'uTime': '1755884829104',
         'executionOrder': {
             'symbol': 'XRP', 'size': '3', 'orderId': '1342843790087520257', 'clientOid': '1342838604632178688',
             'baseVolume': '3', 'fee': '-0.00551502', 'price': '', 'priceAvg': '3.0639', 'state': 'filled', 'side': 'buy',
             'force': 'gtc', 'totalProfits': '-0.0681', 'posSide': 'long', 'marginCoin': '',
             'presetStopSurplusPrice': '', 'presetStopSurplusType': '', 'presetStopSurplusExecutePrice': '',
             'presetStopLossPrice': '', 'presetStopLossExecutePrice': '', 'presetStopLossType': '',
             'quoteVolume': '9.1917', 'orderType': 'market', 'leverage': '10', 'marginMode': 'isolated',
             'reduceOnly': 'YES', 'enterPointSource': 'WEB', 'tradeSide': 'close', 'posMode': 'hedge_mode',
             'orderSource': 'pos_loss_market', 'newTradeSide': 'close', 'cancelReason': '', 'cTime': '1755884829090',
             'uTime': '1755884829225'
         },
         'fills': {
             'fillList': [
                 {
                     'tradeId': '1342843790724988929', 'symbol': 'XRP', 'orderId': '1342843790087520257',
                     'price': '3.0639', 'baseVolume': '3',
                     'feeDetail': [
                         {
                             'deduction': 'no', 'feeCoin': '', 'totalDeductionFee': None, 'totalFee': '-0.00551502'
                         }
                     ],
                     'side': 'buy', 'quoteVolume': '9.1917', 'profit': '-0.0681', 'enterPointSource': 'web',
                     'tradeSide': 'close', 'posMode': 'hedge_mode', 'tradeScope': 'taker', 'cTime': '1755884829217'
                 }
             ],
             'endId': '1342843790724988929'
         }
    }

def get_tp_executed(symbol: str, tp_client_oid: str):
    return 'executed' in _plan_lookup(symbol, client_oid=tp_client_oid, kind="tp")['status']

def get_tp_executed_price(symbol: str, tp_client_oid: str):
    return float(_plan_lookup(symbol, client_oid=tp_client_oid, kind="tp")['executionOrder']['priceAvg'])

def get_tp_profit(symbol: str, tp_client_oid: str):
    return float(_plan_lookup(symbol, client_oid=tp_client_oid, kind="tp")['fills']['fillList'][0]['profit'])

def get_sl_executed(symbol: str, sl_client_oid: str):
    return 'executed' in _plan_lookup(symbol, client_oid=sl_client_oid, kind="sl")['status']

def get_sl_executed_price(symbol: str, sl_client_oid: str):
    return float(_plan_lookup(symbol, client_oid=sl_client_oid, kind="sl")['executionOrder']['priceAvg'])

def get_sl_profit(symbol: str, sl_client_oid: str):
    return float(_plan_lookup(symbol, client_oid=sl_client_oid, kind="sl")['fills']['fillList'][0]['profit'])

_PROCESSED_SL: set[str] = set()

def get_sl_event(symbol: str, sl_client_oid: str, *, grace_ms: int = 1500) -> dict:
    """
    Returns a SINGLE snapshot containing:
      {
        'status': 'live'|'executed'|'cancelled'|'fail_execute'|'not_found'|'lag',
        'executeOrderId': str|None,
        'execute_price': float|None,
        'pnl': float|None,
        'raw': {...}   # raw plan row for your own debugging
      }
    """
    # 1) pending first
    pend = _req("GET", "/api/v2/mix/order/orders-plan-pending", params={
        "productType": PRODUCT_TYPE,
        "planType": "profit_loss",
        "symbol": symbol,
        "clientOid": sl_client_oid,
        "limit": "50",
    })
    rows = ((pend.get("data") or {}).get("entrustedList")) or []
    if rows:
        return {"status": "live", "executeOrderId": None, "execute_price": None, "pnl": None, "raw": rows[0]}

    # 2) if not in pending, peek history (it may take a moment to appear)
    hist = _req("GET", "/api/v2/mix/order/orders-plan-history", params={
        "productType": PRODUCT_TYPE,
        "planType": "profit_loss",
        "symbol": symbol,
        "clientOid": sl_client_oid,
        "limit": "50",
    })
    hrows = ((hist.get("data") or {}).get("entrustedList")) or []
    if not hrows:
        # short grace: sometimes the record just migrated out of pending but isn't in history yet
        time.sleep(grace_ms / 1000.0)
        hist2 = _req("GET", "/api/v2/mix/order/orders-plan-history", params={
            "productType": PRODUCT_TYPE,
            "planType": "profit_loss",
            "symbol": symbol,
            "clientOid": sl_client_oid,
            "limit": "50",
        })
        hrows = ((hist2.get("data") or {}).get("entrustedList")) or []
        if not hrows:
            return {"status": "not_found", "executeOrderId": None, "execute_price": None, "pnl": None, "raw": {}}

    row = hrows[0]
    status = (row.get("planStatus") or "").lower()  # executed | cancelled | fail_execute

    if status != "executed":
        return {"status": status, "executeOrderId": None, "execute_price": None, "pnl": None, "raw": row}

    # 3) get execution order & fills once
    exec_id = row.get("executeOrderId")
    exec_price = None
    pnl = None

    if exec_id:
        try:
            od = _req("GET", "/api/v2/mix/order/detail",
                      params={"productType": PRODUCT_TYPE, "symbol": symbol, "orderId": exec_id})
            d = od.get("data") or {}
            # priceAvg /cumulativeFillAvgPrice varies by response version
            exec_price = float(d.get("priceAvg") or d.get("cumulativeFillAvgPrice") or 0) or None
        except Exception:
            pass

        try:
            fills = _req("GET", "/api/v2/mix/order/fills",
                        params={"productType": PRODUCT_TYPE, "symbol": symbol, "orderId": exec_id})
            flist = fills.get("data") or []
            # Some payloads nest under 'fillList'; normalize:
            if flist and isinstance(flist[0], dict) and "fillList" in flist[0]:
                flist = flist[0]["fillList"]
            if flist:
                # Sum profit across fills (Bitget returns per-fill 'profit' in USDT)
                pnl = sum(float(f.get("profit") or 0) for f in flist)
                # If no exec_price yet, compute VWAP
                if exec_price is None:
                    num = sum(float(f.get("priceAvg") or f.get("price") or 0) * float(f.get("baseVolume") or f.get("size") or 0) for f in flist)
                    den = sum(float(f.get("baseVolume") or f.get("size") or 0) for f in flist)
                    exec_price = (num / den) if den else None
        except Exception:
            pass

    return {"status": "executed", "executeOrderId": exec_id, "execute_price": exec_price, "pnl": pnl, "raw": row}


def handle_sl_if_any(symbol: str, open_positions: dict, current_balance: float, df_5m, idx: int, strategy_name: str, skip_day):
    """
    Atomically checks & consumes the SL event for the symbol.
    Returns updated current_balance and whether we closed the position.
    """
    if symbol not in open_positions:
        return current_balance, False

    sl_oid = open_positions[symbol].get("stop_loss_order_id")
    if not sl_oid or sl_oid in _PROCESSED_SL:
        return current_balance, False

    snap = get_sl_event(symbol, sl_oid)

    if snap["status"] != "executed":
        # still live (or cancelled/not_found); keep watching later
        return current_balance, False

    exit_price = snap["execute_price"]
    pnl = snap["pnl"]

    # Fallbacks if some fields are missing
    if exit_price is None:
        # last resort: read from position or ticker (less accurate)
        try:
            t = _req("GET", "/api/v2/mix/market/ticker",
                     params={"productType": "USDT-FUTURES", "symbol": symbol})
            exit_price = float((t.get("data") or [{}])[0].get("markPrice") or 0) or None
        except Exception:
            pass
    if pnl is None:
        # compute pnl from position delta if you store entry/size; otherwise, set 0
        size = open_positions[symbol].get("amount") or 0
        entry = open_positions[symbol].get("entry_price") or 0
        if exit_price and size and entry:
            pnl = (exit_price - entry) * size * (-1.0)  # SL on long → negative PnL

    # Safety: don’t crash if still None
    pnl = float(pnl or 0.0)

    pos_return = pnl / float(current_balance or 1.0)
    current_balance += pnl

    loss_log = [{
        'symbol': symbol,
        'strategy': strategy_name,
        'timestamp': df_5m.iloc[idx]['timestamp'],
        'entry_price': open_positions[symbol].get('entry_price'),
        'exit_price': exit_price,
        'return': pos_return,
        'balance': current_balance,
        'stop_loss_hit': True,
    }]
    try:
        import pandas as pd, logging
        pd.DataFrame(loss_log).to_csv(f'loss_log_{strategy_name}.csv', mode='a', index=False, header=False)
        logging.info(f"Stop-loss hit for {symbol} at {exit_price}. Balance: ${current_balance:.2f}")
        skip_day[symbol] = 1
    except Exception:
        pass

    # mark consumed to avoid double-processing
    _PROCESSED_SL.add(sl_oid)
    # remove from open positions
    del open_positions[symbol]
    return current_balance, True



# --------------- new attach_tp_sl ------------ don't know if working
def attach_tp_sl(
        symbol: str,
        entry_price: float,
        tp_pct: float = 0.01,
        sl_pct: float = 0.02,
        *,
        tp_client_oid: str | None = None,
        sl_client_oid: str | None = None
):
    tp = quantize_price(symbol, entry_price * (1 + tp_pct))
    sl = quantize_price(symbol, entry_price * (1 - sl_pct))

    pos_mode = get_pos_mode(symbol)
    hold_side = "buy" if pos_mode == "one_way_mode" else "long"

    # generate OIDs if not provided
    tp_oid = tp_client_oid or make_client_oid(f"tp-{symbol.lower()}-{hold_side}")
    sl_oid = sl_client_oid or make_client_oid(f"sl-{symbol.lower()}-{hold_side}")

    body = {
        "symbol": symbol,
        "productType": "usdt-futures",     # this endpoint accepts lowercase
        "marginCoin": "USDT",
        "holdSide": hold_side,

        "stopSurplusTriggerType": "mark_price",
        "stopSurplusTriggerPrice": tp,
        "stopSurplusClientOid": tp_oid,    # <-- your TP client OID

        "stopLossTriggerType": "mark_price",
        "stopLossTriggerPrice": sl,
        "stopLossClientOid": sl_oid,       # <-- your SL client OID

        # execute prices omitted => market on trigger
    }

    res = _req("POST", "/api/v2/mix/order/place-pos-tpsl", body=body)
    return {"apiResponse": res, "tpClientOid": tp_oid, "slClientOid": sl_oid}

# ------------- old attach_tp_sl --------------- working properly
def attach_tp_sl_old(symbol: str, entry: float, tp_pct: float = 0.01, sl_pct: float = 0.02):
    """
    Attach TP/SL to the position (OCO-style). Docs show lowercase productType here; we try both.
    """
    per_symbol_prec = _req('GET', '/api/v2/mix/market/contracts?productType=usdt-futures&symbol=' + symbol + '')
    post_decimal_prec = int(per_symbol_prec['data'][0]['pricePlace'])
    print(per_symbol_prec)
    # exit()


    if entry:
        tp = entry * (1.00 + tp_pct)
        f_string = "{:." + str(post_decimal_prec) + "f}"
        tp = float(f_string.format(tp))
        sl = entry * (1.00 - sl_pct)
        sl = float(f_string.format(sl))
        print("Attach TP/SL …")
        return _req("POST", "/api/v2/mix/order/place-pos-tpsl", body={
            "symbol": symbol,
            "productType": "usdt-futures",   # this endpoint accepts lowercase per docs
            "marginCoin": MARGIN_COIN,
            "holdSide": "long",
            "stopSurplusTriggerType": "mark_price",
            "stopSurplusTriggerPrice": str(tp),
            "stopLossTriggerType": "mark_price",
            "stopLossTriggerPrice": str(sl),
        })
        # "stopSurplusExecutePrice": "0",
        # "stopLossExecutePrice": "0",
    else:
        print("No entry price found yet; TP/SL not attached.")


def cancel_all_orders():
    # Cancels ALL pending futures orders (all symbols) for this productType/marginCoin
    body = {"productType": PRODUCT_TYPE, "marginCoin": MARGIN_COIN}
    return _req("POST", "/api/v2/mix/order/cancel-all-orders", body=body)  # v2 global cancel
    # If you want per-symbol instead, use /api/v2/mix/order/batch-cancel-orders with symbol. :contentReference[oaicite:1]{index=1}


def flash_close_positions(symbol: str, hold_side: str | None = None):
    # Market-close positions quickly; omit holdSide to close both, or pass "long"/"short"
    body = {"symbol": symbol, "productType": PRODUCT_TYPE}
    if hold_side:
        body["holdSide"] = hold_side
    return _req("POST", "/api/v2/mix/order/close-positions", body=body)  # “flash close” :contentReference[oaicite:2]{index=2}


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

def get_account_balance(margin_coin: str = "USDT"):
    return float(get_futures_balance(margin_coin)['available'])

def get_account_current(margine_coin: str = "USDT"):
    return float(get_futures_balance(margine_coin)['equity'])

def get_futures_balance(margin_coin: str = "USDT"):
    """
    Returns your USDT-M futures account balances in demo mode.
    Pulls account-wide numbers (not tied to a specific symbol).
    """
    res = _req("GET", "/api/v2/mix/account/accounts",
               params={"productType": "USDT-FUTURES", "marginCoin": margin_coin})
    data = res.get("data") or []
    if not data:
        return {}

    # Bitget can return a list (one per marginCoin). We pick the first that matches.
    acct = next((a for a in data if (a or {}).get("marginCoin") == margin_coin), data[0])

    # Convert numeric strings to Decimal for safety
    def D(x): return Decimal(str(x)) if x is not None else Decimal("0")

    return {
        "marginCoin": acct.get("marginCoin", margin_coin),
        "equity": D(acct.get("usdtEquity")) +
                  D(acct.get("unrealizedPL")),          # total equity
        "available": D(acct.get("available")),          # free to trade
        "frozen": D(acct.get("frozen")),                # locked by orders
        "unrealizedPL": D(acct.get("unrealizedPL")),    # PnL on open positions
        "posMode": acct.get("posMode"),                 # one_way_mode / hedge_mode
        "marginMode": acct.get("marginMode"),           # cross / isolated (account default)
        "riskRate": acct.get("riskRate"),               # may be None if no positions
    }


def get_symbol_account(symbol: str, margin_coin: str = "USDT"):
    """
    Optional: balances/limits as they apply to a specific symbol context.
    Useful if you switch margin/leverage per symbol.
    """
    res = _req("GET", "/api/v2/mix/account/account",
               params={"symbol": symbol, "productType": "USDT-FUTURES", "marginCoin": margin_coin})
    return res.get("data") or {}


def get_min_symbol_quantity(symbol: str):
    per_symbol_prec = _req('GET', '/api/v2/mix/market/contracts?productType=usdt-futures&symbol=' + symbol + '')
    return float(per_symbol_prec['data'][0]['minTradeNum'])

# ---------- Example flow ----------
if __name__ == "__main__":

    # symbol = "XRPUSDT"  # IMPORTANT: v2 symbol (no _UMCBL); uppercase is safest
    #
    # tp_order_ids = {'slClientOid':'sl-xrpusdt-long-1755883591826-b4836a'}
    # sl_hit = get_sl_executed(symbol, tp_order_ids['slClientOid'])
    # print(sl_hit)
    # # exit()
    # while 'live' in sl_hit['status']:
    #     sl_hit = get_sl_executed(symbol, tp_order_ids['slClientOid'])
    #     # print(sl_hit)
    #     time.sleep(10)
    # print("wrong while")
    # print(sl_hit)
    # exit()
    #
    #
    #
    #
    # # If you want the context tied to a symbol (e.g., XRPUSDT):
    # print("Account (symbol context):")
    # print(get_symbol_account("XRPUSDT"))
    LEVERAGE = 10
    for sym in sorted(TARGET_COINS):
        symbol = sym + ''
        print(symbol)
        set_margin_mode_isolated(symbol)
        set_leverage(symbol, LEVERAGE)
        account_balance = float(get_futures_balance("USDT")['available'])
        print(f"USDT-M futures (demo) balance: {account_balance}")
        symbol_price = float(get_futures_prices(symbol)['mark'])
        # print(symbol_price)
        per_symbol_prec = _req('GET', '/api/v2/mix/market/contracts?productType=usdt-futures&symbol=' + symbol + '')
        # print(per_symbol_prec)
        pos_perc = 0.01
        position_size = (pos_perc*account_balance*LEVERAGE/symbol_price)
        min_position = get_min_symbol_quantity(symbol)
        # position_size = position_size if min_position < position_size  else min_position
        while position_size * symbol_price < 5 or position_size < min_position:
            pos_perc += 0.01
            position_size = (pos_perc*account_balance*LEVERAGE/symbol_price)

        # position_size = 0.01*account_balance if account_balance > 500 else 5
        print(position_size)
        print(place_market_long(symbol, position_size))
        time.sleep(1.0)
        entry_price = get_entry_price(symbol)
        tp_order_ids = attach_tp_sl(symbol, entry_price)
        sl_hit = get_sl_executed(symbol, tp_order_ids['slClientOid'])
        print(sl_hit)
        # exit()
        while not sl_hit:
            sl_hit = get_sl_executed(symbol, tp_order_ids['slClientOid'])
            print(sl_hit)
        print(sl_hit)
    # exit()
    # print("Cancel ALL pending futures orders…")
    # try:
    #     print(cancel_all_orders())
    # except Exception as e:
    #     print("cancel_all_orders:", e)
    #
    # print("Flash-close any open positions on", symbol, "…")
    # try:
    #     print(flash_close_positions(symbol))  # closes both sides if any
    # except Exception as e:
    #     print("close_positions:", e)



    #
    # # tiny pause so the position reflects
    # time.sleep(1.0)
    #
    # # get entry price (for TP/SL calculation)
    # pos = _req("GET", "/api/v2/mix/position/single-position",
    #            params={"symbol": symbol, "productType": PRODUCT_TYPE, "marginCoin": MARGIN_COIN})
    # print(pos)
    # # exit()
    # items = pos.get("data") if isinstance(pos.get("data"), list) else [pos.get("data")]
    # entry = None
    # for p in items or []:
    #     ep = (p or {}).get("openPriceAvg") or (p or {}).get("openPriceAvg")
    #     if ep:
    #         entry = float(ep); break
    #
    # per_symbol_prec = _req('GET', '/api/v2/mix/market/contracts?productType=usdt-futures&symbol=XRP')
    # post_decimal_prec = int(per_symbol_prec['data'][0]['pricePlace'])
    # print(per_symbol_prec)
    # # exit()
    #
    #
    # if entry:
    #     tp = entry * 1.01
    #     f_string = "{:." + str(post_decimal_prec) + "f}"
    #     tp = float(f_string.format(tp))
    #     sl = entry * 0.98
    #     sl = float(f_string.format(sl))
    #     print("Attach TP/SL …")
    #     print(_req("POST", "/api/v2/mix/order/place-pos-tpsl", body={
    #         "symbol": symbol,
    #         "productType": "usdt-futures",   # this endpoint accepts lowercase per docs
    #         "marginCoin": MARGIN_COIN,
    #         "holdSide": "long",
    #         "stopSurplusTriggerType": "mark_price",
    #         "stopSurplusTriggerPrice": str(tp),
    #         "stopLossTriggerType": "mark_price",
    #         "stopLossTriggerPrice": str(sl),
    #     }))
    #         # "stopSurplusExecutePrice": "0",
    #         # "stopLossExecutePrice": "0",
    # else:
    #     print("No entry price found yet; TP/SL not attached.")
