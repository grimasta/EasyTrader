import mplfinance as mpf
import pandas as pd
from ta.trend import SMAIndicator
from ta.momentum import 
import matplotlib.pyplot as plt
# Function to identify trend changes based on moving averages

def identify_trend_changes(data, short_window=10, long_window=50):
    # Calculate short-term and long-term moving averages
    data['SMA_short'] = SMAIndicator(data["Close"], window=short_window).sma_indicator()
    data['SMA_long'] = SMAIndicator(data["Close"], window=long_window).sma_indicator()

    # Identify trend changes based on crossover or crossunder
    data['Signal'] = 0  # 0 represents no signal, 1 for bullish (crossover), -1 for bearish (crossunder)
    data.loc[data['SMA_short'] > data['SMA_long'], 'Signal'] = 1
    data.loc[data['SMA_short'] < data['SMA_long'], 'Signal'] = -1

    return data


ta.trend.

# Sample candlestick data (replace this with your actual data)
num_rows = 10  # Adjust the number of rows as needed
candle_data = pd.DataFrame({
    'Date': pd.date_range('2023-01-01', periods=num_rows),
    'Open': [100, 105, 110, 95, 92, 105, 112, 118, 125, 120],
    'High': [105, 115, 120, 100, 102, 112, 120, 125, 130, 128],
    'Low': [98, 100, 105, 90, 88, 100, 110, 112, 118, 115],
    'Close': [102, 110, 115, 98, 95, 110, 115, 122, 125, 122],
    'Volume': [100000, 120000, 150000, 90000, 85000, 110000, 130000, 140000, 160000, 150000]
})
# Set 'Date' column as the index with DatetimeIndex
candle_data.set_index('Date', inplace=True)

# data = {"Close": [102,    110,     115,    98,    95,    110,    115,    122,    125,    122]}
# Identify trend changes
candle_data = identify_trend_changes(candle_data)

# Plot candlestick chart with trend changes
mpf.plot(candle_data, type='candle', addplot=[
    mpf.make_addplot(candle_data['SMA_short'], color='orange', secondary_y=False),
    mpf.make_addplot(candle_data['SMA_long'], color='blue', secondary_y=False),
    mpf.make_addplot(candle_data['Signal'], color='green', secondary_y=True, markersize=8)
], style='yahoo', volume=True)

# Show the plot
plt.show()
