import pandas as pd
import ta

def calculate_macd(df, fast=12, slow=26, signal=9):
    """
    Calculate MACD and signal line.
    Args:
        df (pd.DataFrame): DataFrame with 'close' column.
        fast (int): Fast EMA period.
        slow (int): Slow EMA period.
        signal (int): Signal line period.
    Returns:
        tuple: (macd_line, signal_line) as pd.Series.
    """
    macd = ta.trend.MACD(df['close'], window_fast=fast, window_slow=slow, window_sign=signal)
    return macd.macd(), macd.macd_signal()