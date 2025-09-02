import pandas as pd
import ta

def calculate_bollinger_bands(df, window=20, std_dev=2):
    """
    Calculate Bollinger Bands for the DataFrame's close prices.
    Args:
        df (pd.DataFrame): DataFrame with 'close' column.
        window (int): Period for moving average.
        std_dev (float): Standard deviations for bands.
    Returns:
        tuple: (lower_band, upper_band) as pd.Series.
    """
    bb = ta.volatility.BollingerBands(df['close'], window=window, window_dev=std_dev)
    return bb.bollinger_lband(), bb.bollinger_hband()