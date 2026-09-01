import time, json, requests
from typing import Any, Dict, Optional, List
from venues.bitget_v2.api_client import API_PASSPHRASE, API_SECRET, API_KEY
from core.Runtimes.Live.live_constants import PRODUCT_TYPE_V2, PRODUCT_TYPE_V1, MARGIN_COIN, \
    SYMBOLS

BASE_URL = "https://api.bitget.com"
SIM_HEADERS = {"PAPTRADING": "1"}


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

def _auth_headers(method: str, request_path_with_query: str, body: Optional[dict]) -> Dict[str, str]:
    ts = _now_ms()  # << use server-synced ms timestamp
    body_str = "" if (not body or method.upper() == "GET") else json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    prehash = f"{ts}{method.upper()}{request_path_with_query}{body_str}"
    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": _sign(API_SECRET, prehash),
        "ACCESS-TIMESTAMP": ts,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
        "Content-Type": "application/json",
    }
    headers.update(SIM_HEADERS)  # PAPTRADING: '1'
    return headers

def _req(method: str, path: str, *, params: Optional[dict] = None, body: Optional[dict] = None):
    qp = _q(params)
    request_path_with_query = path + qp                  # exact string used for signing
    url = BASE_URL + request_path_with_query             # and exact same string sent to server
    headers = _auth_headers(method, request_path_with_query, body)

    try:
        if method.upper() == "GET":
            r = requests.get(url, headers=headers, timeout=20)         # NOTE: no params= here
        else:
            payload = json.dumps(body or {}, separators=(",", ":"), ensure_ascii=False)
            r = requests.post(url, headers=headers, data=payload, timeout=20)
        if not (200 <= r.status_code < 300):
            raise requests.HTTPError(f"{r.status_code} {r.reason}: {r.text}", response=r)
        return r.json()
    except requests.HTTPError:
        raise

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

# def get_pos_mode(symbol: str) -> str:
#     r = _req("GET", "/api/v2/mix/account/account",
#              params={"symbol": symbol, "productType": "USDT-FUTURES", "marginCoin": "USDT"})
#     data = r.get("data") or {}
#     return (data.get("posMode") or "one_way_mode").lower()

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
        for tc in SYMBOLS:
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
