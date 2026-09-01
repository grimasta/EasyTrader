# import yfinance as yf
# import pandas as pd
# import matplotlib.pyplot as plt
# import matplotlib
# matplotlib.use('TkAgg')
# import time
#
# # Parameters for the symbol, time interval, and historical lookback
# SYMBOL = 'BTC-USD'  # Symbol for Yahoo Finance (can be changed to ETH-USD, DOGE-USD, etc.)
# INTERVAL = '1h'  # Interval of data (1m, 5m, 15m, 1h, 1d)
# LOOKBACK_PERIOD = 3  # Number of previous candles to calculate buy/sell sentiment
#
# def fetch_yahoo_finance_data(symbol: str, interval: str, lookback_period: int = 5):
#     """Fetches the latest price data from Yahoo Finance."""
#     try:
#         df = yf.download(tickers=symbol, interval=interval, period=f'{lookback_period}mo', progress=False)
#         if df.empty:
#             print(f"No data returned for {symbol} from Yahoo Finance.")
#             return None
#         df.reset_index(inplace=True)
#         return df
#     except Exception as e:
#         print(f"Error fetching data from Yahoo Finance: {e}")
#         return None
#
# def process_data(df: pd.DataFrame):
#     """
#     Processes the OHLCV (Open, High, Low, Close, Volume) data to extract buy/sell sentiment.
#     Buy sentiment is calculated as the total volume during bullish candles (close > open),
#     and sell sentiment is calculated as the total volume during bearish candles (close < open).
#     """
#     # Calculate bullish and bearish candles
#     df['bullish'] = df['Close'] > df['Open']
#     df['bearish'] = df['Close'] < df['Open']
#     # Calculate buy/sell volume based on bullish and bearish candles
#     buy_volume = df.loc[df['bullish'], 'Volume'].sum()
#     sell_volume = df.loc[df['bearish'], 'Volume'].sum()
#     # Calculate total volume
#     total_volume = buy_volume + sell_volume
#     # Calculate buy/sell percentages
#     buy_percentage = (buy_volume.iloc[0] / total_volume.iloc[0]) * 100 if total_volume.iloc[0] > 0 else 0
#     sell_percentage = (sell_volume.iloc[0] / total_volume.iloc[0]) * 100 if total_volume.iloc[0] > 0 else 0
#
#     return buy_volume, sell_volume, buy_percentage, sell_percentage
#
# def plot_order_book(buy_percentage: float, sell_percentage: float, df: pd.DataFrame):
#     """Plots the buy/sell volume ratio and historical close prices."""
#     plt.figure(figsize=(12, 6))
#
#     # Plot Buy/Sell ratio as a bar chart
#     plt.subplot(1, 2, 1)
#     plt.bar(['Buy Volume %', 'Sell Volume %'], [buy_percentage, sell_percentage], color=['green', 'red'])
#     plt.title('Buy vs. Sell Sentiment')
#     plt.ylim(0, 100)
#     for i, v in enumerate([buy_percentage, sell_percentage]):
#         plt.text(i, v + 2, f'{v:.2f}%', ha='center', fontweight='bold')
#
#     # Plot historical price action
#     plt.subplot(1, 2, 2)
#     df['Datetime'] = pd.to_datetime(df['Datetime'])  # Ensure Datetime is in the correct format
#     df['Close'] = df['Close'].astype(float)  # Ensure Close is a float
#
#     plt.plot(df['Datetime'].values, df['Close'].values, color='blue', label='Price')
#
#     where_bullish = (df['Close'] > df['Open']).values.flatten()
#     where_bearish = (df['Close'] < df['Open']).values.flatten()
#     print(len(df['Datetime'].values))
#     print(len(df['Close'].values.squeeze()))
#     print(len(where_bullish))
#     print(len(where_bearish))
#     plt.fill_between(df['Datetime'].values, (df['Close'].values).squeeze(), where=where_bullish, color='green', alpha=0.2, label='Bullish')
#     plt.fill_between(df['Datetime'].values, (df['Close'].values).squeeze(), where=where_bearish, color='red', alpha=0.2, label='Bearish')
#
#     plt.title(f'Price Action for {SYMBOL}')
#     plt.xlabel('Time')
#     plt.ylabel('Price (USD)')
#     plt.xticks(rotation=45)
#
#     plt.legend()
#     plt.grid(True, linestyle='--', linewidth=0.5)
#
#     plt.tight_layout()
#     plt.show()
#
# def main():
#     """Main function to continuously fetch, process, and visualize the buy/sell sentiment and price action."""
#     while True:
#         print(f"Fetching data for {SYMBOL} from Yahoo Finance...")
#
#         # Step 1: Fetch historical OHLCV data from Yahoo Finance
#         df = fetch_yahoo_finance_data(SYMBOL, INTERVAL, LOOKBACK_PERIOD)
#         if df is None or df.empty:
#             print("No data returned. Retrying in 30 seconds...")
#             time.sleep(30)
#             continue
#
#         # Step 2: Process the data to calculate buy/sell sentiment
#         buy_volume, sell_volume, buy_percentage, sell_percentage = process_data(df)
#
#         # Step 3: Plot the sentiment and price action
#         plot_order_book(buy_percentage, sell_percentage, df)
#
#         # Wait 30 seconds before the next update
#         print(f"Next update in 30 seconds...")
#         time.sleep(30)
#
# if __name__ == '__main__':
#     main()
