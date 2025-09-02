import ccxt
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize Bitget API (mock environment)
exchange = ccxt.bitget({
    'apiKey': '***REMOVED***',
    'secret': '***REMOVED***',
    'password': '***REMOVED***',  # If enabled
    'enableRateLimit': True,
})


# exchange.set_sandbox_mode(True)
# Modified fetch_data function for backtesting
def fetch_data(symbol, timeframe='5m', start_date='2024-08-01', end_date='2025-08-01'):
    """
    Fetch historical OHLCV data for backtesting, prioritizing CoinGecko due to Bitget API limitations.
    Args:
        symbol (str): Trading pair (e.g., 'BTCUSDT').
        timeframe (str): Candle timeframe (e.g., '5m').
        start_date (str): Start date in 'YYYY-MM-DD' format.
        end_date (str): End date in 'YYYY-MM-DD' format.
    Returns:
        pd.DataFrame: OHLCV data with columns ['timestamp', 'open', 'high', 'low', 'close', 'volume'].
    """
    # Try Bitget API first
    try:
        start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
        limit = 1000
        all_ohlcv = []
        current_ts = start_ts

        while current_ts < end_ts:
            try:
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=current_ts, limit=limit)
                if not ohlcv:
                    logging.warning(f"No data returned for {symbol} at {current_ts}. Falling back to CoinGecko.")
                    return fetch_data_coingecko(symbol, start_date, end_date)
                all_ohlcv.extend(ohlcv)
                current_ts = ohlcv[-1][0] + 1
                time.sleep(exchange.rateLimit / 1000)
            except Exception as e:
                logging.error(f"Bitget API error for {symbol} at {current_ts}: {e}")
                return fetch_data_coingecko(symbol, start_date, end_date)

        df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df[df['timestamp'] <= pd.to_datetime(end_date)]
        logging.info(f"Fetched {len(df)} candles from Bitget for {symbol}")
        return df

    except Exception as e:
        logging.error(f"Bitget API failed for {symbol}: {e}. Falling back to CoinGecko.")
        return fetch_data_coingecko(symbol, start_date, end_date)

# CoinGecko fallback
def fetch_data_coingecko(symbol, start_date, end_date):
    """
    Fetch historical data from CoinGecko, interpolating to 5-minute intervals.
    """
    try:
        # Map trading pair to CoinGecko coin ID
        coin_map = {
            'BTCUSDT': 'bitcoin',
            'ETHUSDT': 'ethereum',
            'SOLUSDT': 'solana',
            'DOGEUSDT': 'dogecoin',
            'XRPUSDT': 'ripple'
        }
        coin = coin_map.get(symbol, symbol.lower().replace('usdt', ''))

        start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp())
        end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp())

        url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart/range"
        params = {
            'vs_currency': 'usd',
            'from': start_ts,
            'to': end_ts,
            'interval': 'hourly'  # CoinGecko provides hourly data
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        # Create DataFrame from prices and volumes
        prices = data['prices']
        volumes = data['total_volumes']
        df = pd.DataFrame(prices, columns=['timestamp', 'close'])
        df['volume'] = [v[1] for v in volumes]
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['open'] = df['close'].shift(1).fillna(df['close'])
        df['high'] = df[['open', 'close']].max(axis=1)
        df['low'] = df[['open', 'close']].min(axis=1)

        # Interpolate to 5-minute intervals
        df.set_index('timestamp', inplace=True)
        new_index = pd.date_range(start=start_date, end=end_date, freq='5T')
        df = df.reindex(new_index, method='ffill').reset_index()
        df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        logging.info(f"Fetched {len(df)} candles from CoinGecko for {symbol}")
        return df

    except Exception as e:
        logging.error(f"CoinGecko API failed for {symbol}: {e}")
        return None