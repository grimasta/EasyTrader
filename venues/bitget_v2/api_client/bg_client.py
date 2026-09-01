import ccxt
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import logging
import os
from dotenv import load_dotenv
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()
# Bitget API credentials (replace with your actual credentials)
API_KEY = os.getenv("BITGET_API_KEY")
SECRET_KEY = os.getenv("BITGET_API_SECRET")
PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")

API_KEY = os.getenv("BITGET_API_KEY2")
API_SECRET = os.getenv("BITGET_API_SECRET2")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE2")

# Sandbox mode flag (set to True for mock environment, False for live market data)
SANDBOX_MODE = False
# SANDBOX_MODE = True
if SANDBOX_MODE:
    API_KEY = os.getenv("BITGET_API_KEY3")
    SECRET_KEY = os.getenv("BITGET_API_SECRET3")
    PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE3")
    passo = ""
    exchange = ccxt.bitget({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'password': PASSPHRASE,
        'enableRateLimit': True,
        'verbose': False,
        'options': {'defaultType': 'swap', 'PAPTRADING': '1', 'marginMode': 'isolated'}
    })
else:
    exchange = ccxt.bitget({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'password': PASSPHRASE,
        'enableRateLimit': True,
        'verbose': False,
        'options': {'defaultType': 'swap', 'marginMode': 'isolated'}
    })
# Initialize Bitget API
if SANDBOX_MODE:
    exchange.set_sandbox_mode(True)
    logging.info("Using Bitget sandbox mode for data fetching")
else:
    logging.info("Using Bitget live market for data fetching")


def fetch_data(symbol, timeframe='5m', start_date=None, end_date=None, limit=1000):
    """
    Fetch historical OHLCV data from Bitget with robust pagination.
    Args:
        symbol (str): Trading pair (e.g., 'BTCUSDT').
        timeframe (str): Candle timeframe ('5m' or '4h').
        start_date (str): Start date in 'YYYY-MM-DD' format.
        end_date (str): End date in 'YYYY-MM-DD' format.
        limit (int): Candles per request (max 1000).
    Returns:
        pd.DataFrame: OHLCV data with columns ['timestamp', 'open', 'high', 'low', 'close', 'volume'].
    """
    # try:
    start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
    end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
    all_ohlcv = []
    current_ts = start_ts
    max_candles = (end_ts - start_ts) / 60000 #minutes
    max_candles_5m = max_candles / 5
    max_candles = max_candles / 60 #hours
    max_candles_4h = max_candles / 4
    print(max_candles_5m, max_candles_4h)
    # exit()
    max_candles = max_candles_5m if timeframe == '5m' else max_candles_4h
    # if SANDBOX_MODE:
        # symbol = symbol.replace('USDT', 'USDT_UMCBL') if 'USDT_UMCBL' not in symbol else symbol
    # if timeframe == '5m':
    step = 5 * limit * 60 * 1000
    # else:
        # step = 5 *
    while current_ts < end_ts and len(all_ohlcv) < max_candles:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=current_ts, limit=limit)
            if not ohlcv:
                logging.warning(f"No more data for {symbol} at {datetime.fromtimestamp(current_ts/1000)}")
                current_ts += step
                continue
            all_ohlcv.extend(ohlcv)
            current_ts = ohlcv[-1][0] + 1
            # logging.debug(f"Fetched {len(ohlcv)} candles for {symbol} up to {datetime.fromtimestamp(current_ts/1000)}")
            time.sleep(exchange.rateLimit / 1000)
        except Exception as e:
            logging.error(f"Bitget API error for {symbol}: {e}")
            time.sleep(2)
    print(len(all_ohlcv), timeframe)
    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    # exit()
    start_date_dt = pd.to_datetime(start_date, format='%Y-%m-%d').timestamp()*1000
    # end_date_dt = pd.to_datetime(end_date, format='%Y-%m-%d').timestamp()*1000
    # print(start_date_dt)
    # print(end_date_dt)
    # print(df['timestamp'])
    # print(df.head())
    # l_timestamps = df['timestamp'].tolist()
    # print([datetime.strptime(datetime.fromtimestamp(ts/1000).strftime('%Y-%m-%d-%H-%M') , '%Y-%m-%d-%H-%M') for ts in l_timestamps][0:5])
    df = df[(df['timestamp'] >= start_date_dt)]
    df = df.drop_duplicates(subset=['timestamp'])
    logging.info(f"Fetched {len(df)} candles for {symbol} ({timeframe}). Range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    return df
    # df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    # df = df[(df['timestamp'] >= pd.to_datetime(start_date)) & (df['timestamp'] <= pd.to_datetime(end_date))]
    # df = df.drop_duplicates(subset=['timestamp'])
    # # logging.info(f"Fetched {len(df)} candles for {symbol} ({timeframe}). Range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    # return df

    # except Exception as e:
    #     logging.error(f"Failed to fetch data for {symbol}: {e}")
    #     return None


def fetch_data_coingecko(symbol, timeframe, start_date, end_date):
    """
    Fetch historical data from CoinGecko, interpolating to specified timeframe.
    """
    try:
        coin_map = {
            'BTCUSDT': 'bitcoin',
            'ETHUSDT': 'ethereum',
            'SOLUSDT': 'solana',
            'DOGEUSDT': 'dogecoin',
            'XRPUSDT': 'ripple'
        }
        coin = coin_map.get(symbol, symbol.lower().replace('usdt', ''))

        start_ts = int((datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=1)).timestamp())
        end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp())

        url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart/range"
        params = {
            'vs_currency': 'usd',
            'from': start_ts,
            'to': end_ts,
            'interval': 'hourly' if timeframe == '5m' else 'daily'
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        prices = data['prices']
        volumes = data['total_volumes']
        df = pd.DataFrame(prices, columns=['timestamp', 'close'])
        df['volume'] = [v[1] for v in volumes]
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['open'] = df['close'].shift(1).fillna(df['close'])
        df['high'] = df[['open', 'close']].max(axis=1)
        df['low'] = df[['open', 'close']].min(axis=1)

        freq = '5T' if timeframe == '5m' else '4H'
        df.set_index('timestamp', inplace=True)
        new_index = pd.date_range(start=start_date, end=end_date, freq=freq)
        df = df.reindex(new_index, method='ffill').reset_index()
        df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        logging.info(f"Fetched {len(df)} candles from CoinGecko for {symbol} ({timeframe}). Range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        return df

    except Exception as e:
        logging.error(f"CoinGecko API failed for {symbol}: {e}")
        return None