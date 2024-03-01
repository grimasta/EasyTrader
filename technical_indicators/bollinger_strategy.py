import pandas as pd
import numpy as np
# import yfinance as yf  # You can use any other library to fetch stock data

def calculate_bollinger_bands(data, window=20, num_std_dev=2):
    """
    Function to calculate Bollinger Bands.

    Args:
        data (pd.DataFrame): DataFrame containing 'Close' prices.
        window (int): Size of the rolling window.
        num_std_dev (int): Number of standard deviations for the bands.

    Returns:
        pd.DataFrame: DataFrame with Bollinger Bands ('Upper Band', 'Lower Band') added.
    """
    # Calculate rolling mean and standard deviation
    data['Rolling Mean'] = data['Close'].rolling(window=window).mean()
    data['Rolling Std'] = data['Close'].rolling(window=window).std()

    # Calculate upper and lower bands
    data['Upper Band'] = data['Rolling Mean'] + (data['Rolling Std'] * num_std_dev)
    data['Lower Band'] = data['Rolling Mean'] - (data['Rolling Std'] * num_std_dev)
    print(data)
    return data

def check_crossing_bands(data):
    """
    Function to check if the price crosses Bollinger Bands.

    Args:
        data (pd.DataFrame): DataFrame containing 'Close', 'Upper Band', and 'Lower Band'.

    Returns:
        list: List of tuples containing timestamp and type of crossing ('Upper' or 'Lower').
    """
    crossings = []
    for i in range(1, len(data)):
        if data['Close'].iloc[i] > data['Upper Band'].iloc[i] and data['Close'].iloc[i - 1] < data['Upper Band'].iloc[i - 1]:
            crossings.append((data.index[i], 'Upper'))
        elif data['Close'].iloc[i] < data['Lower Band'].iloc[i] and data['Close'].iloc[i - 1] > data['Lower Band'].iloc[i - 1]:
            crossings.append((data.index[i], 'Lower'))
    return crossings

# Fetch historical data
# stock_symbol = 'AAPL'  # Example: Apple stock
# start_date = '2023-01-01'
# end_date = '2024-01-01'
# stock_data = yf.download(stock_symbol, start=start_date, end=end_date)

# Calculate Bollinger Bands
# stock_data = calculate_bollinger_bands(stock_data)

# Check for crossings
# crossings = check_crossing_bands(stock_data)

# Print crossings
# for crossing in crossings:
#     print(f"Crossed {crossing[1]} band at {crossing[0]}")
