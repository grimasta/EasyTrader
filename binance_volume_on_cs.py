# import matplotlib
# matplotlib.use('TkAgg')
# import matplotlib.pyplot as plt
# import mplfinance as mpf
# import pandas as pd
# import numpy as np
# from binance.client import Client
# import os
# from dotenv import load_dotenv
#
# load_dotenv()
# # Replace with your Binance API keys
# API_KEY = os.getenv("BINANCE_API_KEY")
# API_SECRET = os.getenv("BINANCE_API_SECRET")
# API_PASSPHRASE = os.getenv("BINANCE_API_PASSPHRASE")
#
# # Binance client for fetching data
# client = Client(API_KEY, API_SECRET)
#
# def fetch_binance_data(symbol="BTCUSDT", interval="1m", limit=100):
#     """Fetch historical candlestick data from Binance."""
#     klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
#     data = pd.DataFrame(klines, columns=[
#         "Open time", "Open", "High", "Low", "Close", "Volume",
#         "Close time", "Quote asset volume", "Number of trades",
#         "Taker buy base asset volume", "Taker buy quote asset volume", "Ignore"
#     ])
#     data = data[["Open time", "Open", "High", "Low", "Close", "Volume"]]
#     data["Open time"] = pd.to_datetime(data["Open time"], unit="ms")
#     data.set_index("Open time", inplace=True)
#     data = data.astype(float)
#     return data
#
# def generate_order_book(pip_size=10, levels=10):
#     """Simulate buy/sell order imbalances for each pip range."""
#     # Randomly simulate buy/sell volumes for demo purposes
#     buy_volumes = np.random.randint(10, 100, size=levels)
#     sell_volumes = np.random.randint(10, 100, size=levels)
#     levels_range = np.arange(-levels//2, levels//2) * pip_size
#     return levels_range, buy_volumes, sell_volumes
#
# def plot_indicator(data, pip_size=10):
#     """Plot the candlestick chart with buy/sell imbalance overlay."""
#     # Fetch simulated order book data
#     levels_range, buy_volumes, sell_volumes = generate_order_book(pip_size=pip_size)
#
#     # Calculate total buy and sell volumes and percentages
#     total_buy = buy_volumes.sum()
#     total_sell = sell_volumes.sum()
#     buy_percentage = (total_buy / (total_buy + total_sell)) * 100
#     sell_percentage = (total_sell / (total_buy + total_sell)) * 100
#
#     # Create figure and candlestick chart
#     fig, ax_candle = plt.subplots(figsize=(12, 8))
#     mpf.plot(data, type="candle", ax=ax_candle, style="charles", volume=False)
#
#     # Overlay order book imbalance
#     mid_price = data["Close"].iloc[-1]  # Center around the latest close price
#     y_positions = mid_price + (levels_range / 10000)  # Adjust pip scaling
#
#     for i, (level, buy, sell) in enumerate(zip(levels_range, buy_volumes, sell_volumes)):
#         y_pos = mid_price + level / 10000  # Center levels around the mid-price
#         ax_candle.barh(y_pos, buy, color="blue", alpha=0.6, label="Buy Volume" if i == 0 else "")
#         ax_candle.barh(y_pos, -sell, color="red", alpha=0.6, label="Sell Volume" if i == 0 else "")
#
#     # Add percentages to the top of the chart
#     ax_candle.text(0.85, 0.95, f"Buy: {buy_percentage:.1f}%", transform=ax_candle.transAxes, fontsize=12, color="blue")
#     ax_candle.text(0.85, 0.90, f"Sell: {sell_percentage:.1f}%", transform=ax_candle.transAxes, fontsize=12, color="red")
#
#     # Add legend and labels
#     ax_candle.legend(loc="upper left")
#     ax_candle.set_title(f"Buy/Sell Imbalance Overlay - Pip Size: {pip_size}")
#     ax_candle.set_xlabel("Volume")
#     ax_candle.set_ylabel("Price Levels")
#
#     plt.tight_layout()
#     plt.show()
#
# def main():
#     """Main function to fetch data and plot the indicator."""
#     # Fetch candlestick data
#     symbol = "BTCUSDT"
#     interval = "15m"
#     data = fetch_binance_data(symbol=symbol, interval=interval)
#
#     # Plot the indicator with customizable pip size
#     plot_indicator(data, pip_size=1)
#
# if __name__ == "__main__":
#     main()
#
