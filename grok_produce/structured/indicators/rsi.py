import pandas as pd
import ta

def calculate_rsi(df, window=14):
    """
    Calculate RSI for the DataFrame's close prices.
    Args:
        df (pd.DataFrame): DataFrame with 'close' column.
        window (int): RSI period.
    Returns:
        pd.Series: RSI values.
    """
    return ta.momentum.RSIIndicator(df['close'], window=window).rsi()