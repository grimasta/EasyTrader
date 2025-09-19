from grok_produce.structured.api_client.v2_bootstrap_client import _req
from decimal import Decimal


def get_account_current(margin_coin: str = "USDT"):
    return float(get_futures_balance(margin_coin)['equity'])


def get_account_balance(margin_coin: str = "USDT"):
    return float(get_futures_balance(margin_coin)['available'])


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


