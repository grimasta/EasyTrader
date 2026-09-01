import pandas as pd

def calculate_sma(df, window=50):
    """
    Calculate Simple Moving Average.
    Args:
        df (pd.DataFrame): DataFrame with 'close' column.
        window (int): SMA period.
    Returns:
        pd.Series: SMA values.
    """
    return df['close'].rolling(window=window).mean()