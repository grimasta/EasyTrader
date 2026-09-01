# import ccxt
# import pandas as pd
# import ta
# import requests
# import time
# from datetime import datetime, timedelta
# import logging
#
# # Configure logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
#
# # Initialize Bitget API
# exchange = ccxt.bitget({
#     'apiKey': '***REMOVED***',
#     'secret': '***REMOVED***',
#     'password': '***REMOVED***',  # If enabled
#     'enableRateLimit': True,
# })
#
# # Fetch data function
# def fetch_data(symbol, timeframe='5m', start_date='2024-08-01', end_date='2025-08-01'):
#     """
#     Fetch historical OHLCV data from Bitget, falling back to CoinGecko if necessary.
#     """
#     try:
#         # Add buffer to start_date (1 day earlier)
#         buffer_start = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
#         start_ts = int(datetime.strptime(buffer_start, '%Y-%m-%d').timestamp() * 1000)
#         end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
#         limit = 1000
#         all_ohlcv = []
#         current_ts = start_ts
#         retries = 3
#
#         while current_ts < end_ts:
#             for attempt in range(retries):
#                 try:
#                     ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=current_ts, limit=limit)
#                     if not ohlcv:
#                         logging.warning(f"No data for {symbol} at {current_ts} (attempt {attempt+1}/{retries})")
#                         if attempt == retries - 1:
#                             logging.warning(f"Bitget failed for {symbol}. Falling back to CoinGecko.")
#                             return fetch_data_coingecko(symbol, timeframe, start_date, end_date)
#                         time.sleep(2)
#                         continue
#                     all_ohlcv.extend(ohlcv)
#                     current_ts = ohlcv[-1][0] + 1
#                     time.sleep(exchange.rateLimit / 1000)
#                     break
#                 except Exception as e:
#                     logging.error(f"Bitget API error for {symbol} at {current_ts}: {e}")
#                     if attempt == retries - 1:
#                         return fetch_data_coingecko(symbol, timeframe, start_date, end_date)
#                     time.sleep(2)
#
#         df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
#         df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
#         df = df[(df['timestamp'] >= pd.to_datetime(start_date)) & (df['timestamp'] <= pd.to_datetime(end_date))]
#         logging.info(f"Fetched {len(df)} candles from Bitget for {symbol} ({timeframe}). Range: {df['timestamp'].min()} to {df['timestamp'].max()}")
#         return df
#
#     except Exception as e:
#         logging.error(f"Bitget API failed for {symbol}: {e}. Falling back to CoinGecko.")
#         return fetch_data_coingecko(symbol, timeframe, start_date, end_date)
#
# # CoinGecko fallback
# def fetch_data_coingecko(symbol, timeframe, start_date, end_date):
#     """
#     Fetch historical data from CoinGecko, interpolating to specified timeframe.
#     """
#     try:
#         coin_map = {
#             'BTCUSDT': 'bitcoin',
#             'ETHUSDT': 'ethereum',
#             'SOLUSDT': 'solana',
#             'DOGEUSDT': 'dogecoin',
#             'XRPUSDT': 'ripple'
#         }
#         coin = coin_map.get(symbol, symbol.lower().replace('usdt', ''))
#
#         start_ts = int((datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=1)).timestamp())
#         end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp())
#
#         url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart/range"
#         params = {
#             'vs_currency': 'usd',
#             'from': start_ts,
#             'to': end_ts,
#             'interval': 'hourly' if timeframe == '5m' else 'daily'
#         }
#         response = requests.get(url, params=params)
#         response.raise_for_status()
#         data = response.json()
#
#         prices = data['prices']
#         volumes = data['total_volumes']
#         df = pd.DataFrame(prices, columns=['timestamp', 'close'])
#         df['volume'] = [v[1] for v in volumes]
#         df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
#         df['open'] = df['close'].shift(1).fillna(df['close'])
#         df['high'] = df[['open', 'close']].max(axis=1)
#         df['low'] = df[['open', 'close']].min(axis=1)
#
#         freq = '5T' if timeframe == '5m' else '4H'
#         df.set_index('timestamp', inplace=True)
#         new_index = pd.date_range(start=start_date, end=end_date, freq=freq)
#         df = df.reindex(new_index, method='ffill').reset_index()
#         df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
#         logging.info(f"Fetched {len(df)} candles from CoinGecko for {symbol} ({timeframe}). Range: {df['timestamp'].min()} to {df['timestamp'].max()}")
#         return df
#
#     except Exception as e:
#         logging.error(f"CoinGecko API failed for {symbol}: {e}")
#         return None
#
# # Calculate indicators
# def calculate_indicators(df, timeframe='5m'):
#     df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=20).rsi()
#     bb = ta.volatility.BollingerBands(df['close'], window=40, window_dev=2.5)
#     df['bb_lower'] = bb.bollinger_lband()
#     df['bb_upper'] = bb.bollinger_hband()
#     df['volume_ma'] = df['volume'].rolling(window=40).mean()
#     if timeframe == '4h':
#         df['ema_100'] = ta.trend.EMAIndicator(df['close'], window=100).ema_indicator()
#     return df
#
# # Check 4-hour confluence
# def check_4h_confluence(df_4h, current_time):
#     # Find the closest 4-hour candle
#     valid_candles = df_4h[df_4h['timestamp'] <= current_time]
#     if valid_candles.empty:
#         # logging.warning(f"No 4h candle found before {current_time}. Using earliest available.")
#         valid_candles = df_4h.head(1)
#         if valid_candles.empty:
#             return False
#     latest_4h = valid_candles.iloc[-1]
#     price = latest_4h['close']
#     bb_lower = latest_4h['bb_lower']
#     ema_100 = latest_4h['ema_100']
#     return  price < ema_100
#
# # Check for trade signals
# def check_signals(df_5m, df_4h, idx):
#     latest = df_5m.iloc[idx]
#     prev = df_5m.iloc[idx-1]
#     buy_signal = (latest['rsi'] < 20) and (latest['close'] > latest['bb_lower']) and (prev['close'] <= prev['bb_lower'])
#     volume_spike = latest['volume'] > 1.2 * latest['volume_ma']
#     confluence = check_4h_confluence(df_4h, latest['timestamp'])
#     return buy_signal and volume_spike and confluence
#
# # Simulate trade
# def simulate_trade(symbol, entry_price, amount, df_5m, start_idx):
#     for idx in range(start_idx, len(df_5m)):
#         current_price = df_5m.iloc[idx]['close']
#         profit = (current_price - entry_price) / entry_price
#         loss = (entry_price - current_price) / entry_price
#         current_time = df_5m.iloc[idx]['timestamp']
#         current_day = current_time.date()
#
#         if profit >= 0.022:
#             logging.info(f"Closed {symbol} at {current_price} for {profit*100:.2f}% profit")
#             return 1 + 0.012 - 0.002
#         elif loss >= 0.02:
#             logging.info(f"Closed {symbol} at {current_price} for {loss*100:.2f}% loss")
#             return 1 - 0.01 - 0.002
#         elif current_time.time().strftime("%H:%M") >= "23:59":
#             logging.info(f"Closed {symbol} at {current_price} at EOD")
#             return 1 + (current_price - entry_price) / entry_price - 0.002
#
#     return 1.0
#
# # Backtesting function
# def backtest():
#     balance = INITIAL_BALANCE = 10.0
#     daily_returns = []
#     start_date = '2024-08-01'
#     end_date = '2025-08-01'
#     SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT', 'XRPUSDT']
#     LEVERAGE = 10
#     POSITION_SIZE = 10
#     max_trades_per_day = 5
#     trades_today = {symbol: {} for symbol in SYMBOLS}
#
#     for symbol in SYMBOLS:
#         logging.info(f"Backtesting {symbol}")
#         df_5m = fetch_data(symbol, timeframe='5m', start_date=start_date, end_date=end_date)
#         df_4h = fetch_data(symbol, timeframe='4h', start_date=start_date, end_date=end_date)
#         if df_5m is None or df_4h is None or len(df_5m) < 20 or len(df_4h) < 100:
#             logging.warning(f"Insufficient data for {symbol}")
#             continue
#
#         df_5m = calculate_indicators(df_5m, timeframe='5m')
#         df_4h = calculate_indicators(df_4h, timeframe='4h')
#         df_5m = df_5m.dropna()
#         df_4h = df_4h.dropna()
#
#         for idx in range(20, len(df_5m)):
#             current_day = df_5m.iloc[idx]['timestamp'].date()
#             if current_day not in trades_today[symbol]:
#                 trades_today[symbol][current_day] = 0
#
#             if trades_today[symbol][current_day] >= max_trades_per_day:
#                 continue
#
#             if check_signals(df_5m, df_4h, idx):
#                 price = df_5m.iloc[idx]['close']
#                 amount = (POSITION_SIZE * LEVERAGE) / price
#                 multiplier = simulate_trade(symbol, price, amount, df_5m, idx)
#                 balance *= multiplier
#                 daily_returns.append(multiplier - 1)
#                 trades_today[symbol][current_day] += 1
#                 logging.info(f"New balance: ${balance:.2f}")
#
#     avg_daily_return = sum(daily_returns) / len(daily_returns) if daily_returns else 0
#     annual_return = (1 + avg_daily_return) ** 365 - 1
#     logging.info(f"Final balance: ${balance:.2f}")
#     logging.info(f"Average daily return: {avg_daily_return*100:.2f}%")
#     logging.info(f"Compounded annual return: {annual_return*100:.2f}%")
#
# if __name__ == "__main__":
#     backtest()