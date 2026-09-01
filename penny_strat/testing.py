# import pandas as pd
# import requests
# import datetime
# from datetime import datetime, timedelta
# import xlsxwriter
#
#
# # Function to fetch historical OHLCV data for futures
# def get_ohlcv_data(pair="ETHUSDT", interval="1h", since="2025-07-01T00:00:00Z", limit=1500):
#     url = "https://fapi.binance.com/fapi/v1/klines"
#     all_ohlcv = []
#     since_timestamp = int(datetime.strptime(since, '%Y-%m-%dT%H:%M:%SZ').timestamp() * 1000)
#     end_timestamp = int(datetime.strptime('2025-08-22T23:59:59Z', '%Y-%m-%dT%H:%M:%SZ').timestamp() * 1000)
#
#     while since_timestamp < end_timestamp:
#         params = {
#             "symbol": pair,
#             "interval": interval,
#             "startTime": since_timestamp,
#             "limit": limit
#         }
#         try:
#             response = requests.get(url, params=params)
#             if response.status_code == 200:
#                 data = response.json()
#                 if not data:
#                     break
#                 for entry in data:
#                     timestamp = entry[0]
#                     open_price = float(entry[1])
#                     high = float(entry[2])
#                     low = float(entry[3])
#                     close = float(entry[4])
#                     volume = float(entry[5])
#                     date_time = pd.to_datetime(timestamp, unit='ms')
#                     all_ohlcv.append([timestamp, open_price, high, low, close, volume])
#                 since_timestamp = data[-1][0] + 1
#                 print(f"Fetched {len(data)} candles, up to {pd.to_datetime(data[-1][0], unit='ms')}")
#             else:
#                 print(f"Failed to retrieve data: {response.status_code}, {response.text}")
#                 break
#         except Exception as e:
#             print(f"Error fetching data: {e}")
#             break
#     return all_ohlcv
#
#
# # Define parameters
# symbols = ['DOGEUSDT', 'ETHUSDT', 'BTCUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 'TRXUSDT', 'ADAUSDT', 'LINKUSDT', 'HYPEUSDT']
# timeframe = '30m'
# start_date = '2020-01-01T00:00:00Z'
# initial_capital = 500.0
# fee_rate = 0.001  # 0.1% fee per trade
# per_symbol_df = {}
# # Fetch data
# for symbol in symbols:
#     symbol_ohlcv = get_ohlcv_data(symbol, timeframe, start_date)
#     if not symbol_ohlcv:
#         print("No data fetched. Using CSV fallback if available.")
#         try:
#             df = pd.read_csv('eth_usdt_futures_data.csv')
#             df['timestamp'] = pd.to_datetime(df['timestamp'])
#             df.set_index('timestamp', inplace=True)
#         except FileNotFoundError:
#             print("CSV file not found. Please provide eth_usdt_futures_data.csv with OHLCV data.")
#             exit()
#     else:
#         df = pd.DataFrame(symbol_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
#         df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
#     df.set_index('timestamp', inplace=True)
#
#     # Calculate 20 SMA from Binance futures closing prices
#     df['sma20'] = df['close'].rolling(window=40).mean()
#
#     # Debug: Print first few SMA values to verify
#     print("Sample SMA values:")
#     print(df[['close', 'sma20']].head(25))
#     df_length = len(df)
#     per_symbol_df[symbol] = df
# # Initialize variables for backtesting
# capital = initial_capital
# positions = {}  # 0: no position, 1: long, -1: short
# entry_prices = {}
# asset_amounts = {}
# for symbol in symbols:
#     positions[symbol] = 0
#     entry_prices[symbol] = 0
#     asset_amounts[symbol] = 0
# trades = []
# trade_count = 0
# win_count = 0
# SL = - 0.01
# # TP = 0.1
#
# # Backtesting logic
# for i in range(1, df_length - 1):  # Adjusted range to avoid index out of bounds
#     for symbol in symbols:
#         df = per_symbol_df[symbol]
#         prev_candle = df.iloc[i-1]
#         current_candle = df.iloc[i]
#         next_candle = df.iloc[i + 1]
#         position = positions[symbol]
#         # Debug: Print price and SMA every 100 candles
#         if i % 100 == 0:
#             print(
#                 f"Date: {current_candle.name}, Close: {current_candle['close']:.8f}, SMA20: {current_candle['sma20']:.8f}")
#
#         if position == 0:
#             pos_size = 0.01 * capital
#             leverage = 10
#             asset_amount = pos_size * leverage / next_candle['close']
#             asset_amounts[symbol] = asset_amount
#             # Long entry: Current candle closes above SMA20 and next candle is green
#             if (prev_candle['close'] < prev_candle['sma20'] and not pd.isna(prev_candle['sma20'])) and \
#                     (current_candle['close'] > current_candle['sma20'] and not pd.isna(current_candle['sma20']) and
#                      next_candle['close'] > next_candle['open']):
#                 position = 1
#                 entry_price = next_candle['close']
#                 entry_prices[symbol] = entry_price
#                 trade_count += 1
#                 trades.append({
#                     'trade_number': trade_count,
#                     'type': 'Long',
#                     'entry_time': next_candle.name,
#                     'entry_price': entry_price
#                 })
#                 print(f"Long Entry: {next_candle.name}, Price: {entry_price:.8f}")
#             # Short entry: Current candle closes below SMA20 and next candle is red
#             elif (prev_candle['close'] > prev_candle['sma20'] and not pd.isna(prev_candle['sma20'])) and \
#                     (current_candle['close'] < current_candle['sma20'] and not pd.isna(current_candle['sma20']) and
#                      next_candle['close'] < next_candle['open']):
#                 position = -1
#                 entry_price = next_candle['close']
#                 trade_count += 1
#                 trades.append({
#                     'trade_number': trade_count,
#                     'type': 'Short',
#                     'entry_time': next_candle.name,
#                     'entry_price': entry_price
#                 })
#                 print(f"Short Entry: {next_candle.name}, Price: {entry_price:.8f}")
#
#         elif position == 1:
#             asset_amount = asset_amounts[symbol]
#             entry_price = entry_prices[symbol]
#             exit_price = current_candle['close']
#             if ((exit_price - entry_price)/entry_price) < SL:
#                 profit = asset_amount * entry_price * (SL - 2 * fee_rate)
#                 capital += profit
#                 if profit > 0:
#                     win_count += 1
#                 trades[-1].update({
#                     'exit_time': current_candle.name,
#                     'exit_price': exit_price,
#                     'profit': profit
#                 })
#                 print(f"Long Exit: {current_candle.name}, Price: {exit_price:.8f}, Profit: {profit:.2f}")
#                 position = 0
#             # elif ((exit_price - entry_price)/entry_price) > TP:
#             #     profit = asset_amount * entry_price * (TP - 2 * fee_rate)
#             #     capital += profit
#             #     if profit > 0:
#             #         win_count += 1
#             #     trades[-1].update({
#             #         'exit_time': current_candle.name,
#             #         'exit_price': exit_price,
#             #         'profit': profit
#             #     })
#             #     print(f"Long Exit: {current_candle.name}, Price: {exit_price:.8f}, Profit: {profit:.2f}")
#             #     position = 0
#             elif current_candle['close'] < current_candle['sma20'] and not pd.isna(current_candle['sma20']):
#                 exit_price = current_candle['close']
#                 profit = asset_amount * entry_price * ((exit_price - entry_price)/entry_price - 2 * fee_rate)
#                 capital += profit
#                 if profit > 0:
#                     win_count += 1
#                 trades[-1].update({
#                     'exit_time': current_candle.name,
#                     'exit_price': exit_price,
#                     'profit': profit
#                 })
#                 print(f"Long Exit: {current_candle.name}, Price: {exit_price:.8f}, Profit: {profit:.2f}")
#                 position = 0
#         elif position == -1:
#             asset_amount = asset_amounts[symbol]
#             entry_price = entry_prices[symbol]
#             exit_price = current_candle['close']
#             if ((entry_price - exit_price)/entry_price) < SL:
#                 profit = asset_amount * entry_price * (SL - 2 * fee_rate)
#                 capital += profit
#                 if profit > 0:
#                     win_count += 1
#                 trades[-1].update({
#                     'exit_time': current_candle.name,
#                     'exit_price': exit_price,
#                     'profit': profit
#                 })
#                 print(f"Long Exit: {current_candle.name}, Price: {exit_price:.8f}, Profit: {profit:.2f}")
#                 position = 0
#             # elif ((entry_price - exit_price)/entry_price) > TP:
#             #     profit = asset_amount * entry_price * (TP - 2 * fee_rate)
#             #     capital += profit
#             #     if profit > 0:
#             #         win_count += 1
#             #     trades[-1].update({
#             #         'exit_time': current_candle.name,
#             #         'exit_price': exit_price,
#             #         'profit': profit
#             #     })
#             #     print(f"Long Exit: {current_candle.name}, Price: {exit_price:.8f}, Profit: {profit:.2f}")
#             #     position = 0
#             elif current_candle['close'] > current_candle['sma20'] and not pd.isna(current_candle['sma20']):
#                 exit_price = current_candle['close']
#                 profit = asset_amount * entry_price * ((entry_price - exit_price)/entry_price - 2 * fee_rate)
#                 capital += profit
#                 if profit > 0:
#                     win_count += 1
#                 trades[-1].update({
#                     'exit_time': current_candle.name,
#                     'exit_price': exit_price,
#                     'profit': profit
#                 })
#                 print(f"Short Exit: {current_candle.name}, Price: {exit_price:.8f}, Profit: {profit:.2f}")
#                 position = 0
#         positions[symbol] = position
# # Calculate metrics
# winning_rate = (win_count / trade_count * 100) if trade_count > 0 else 0
# final_profit = capital - initial_capital
#
# # Print results
# print(f"Total Trades: {trade_count}")
# print(f"Winning Rate: {winning_rate:.2f}%")
# print(f"Final Profit: ${final_profit:.2f}")
# print(f"Final Profit Perc: {(capital-initial_capital)/initial_capital*100:.2f}%")
#
# # Export to Excel with high precision
# trades_df = pd.DataFrame(trades)
# trades_df.to_excel('eth_usdt_futures_trades.xlsx', index=False, engine='xlsxwriter', float_format='%.8f')
# df.to_excel('eth_usdt_futures_data.xlsx', engine='xlsxwriter', float_format='%.8f')