# ---------- your constants ----------
SYMBOLS = ['BTCUSDT','ETHUSDT','SOLUSDT','DOGEUSDT','XRPUSDT','BNBUSDT','TRXUSDT',
           'ADAUSDT','LINKUSDT','DOTUSDT','AVAXUSDT',
           # 'ICPUSDT',
           'LTCUSDT','NEARUSDT']
LEVERAGE = 10
POSITION_SIZE = 0.01
PROFIT_TARGET = 0.012          # 1.2% gross by default; you can tune per symbol
STOP_LOSS = 0.02
MAX_TRADES_PER_DAY = 10
STRATEGY_NAME = 'best_momentum'
LOSS_LIMIT = 0.40               # stop if equity drops by 40%
WATCH_TIMEFRAME = "5m"          # which TF to use for on-close checks
SKIP_DAY_DELAY = 1
BASE_URL = "https://api.bitget.com"
SIM_HEADERS = {"PAPTRADING": "1"}
PRODUCT_TYPE_V2 = "usdt-futures"           # v2 productType
PRODUCT_TYPE_V1 = "umcbl"                  # v1 productType
MARGIN_COIN = "USDT"
PRODUCT_TYPE = "USDT-FUTURES"
PRODUCT_TYPE_CAPS = "USDT-FUTURES"   # for most V2 endpoints
PRODUCT_TYPE_LOWER = "usdt-futures"  # some plan endpoints show lowercase in docs