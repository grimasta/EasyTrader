import pandas as pd
import ta

def calculate_ema(df, window=100):
    """
    Calculate EMA for the DataFrame's close prices.
    Args:
        df (pd.DataFrame): DataFrame with 'close' column.
        window (int): EMA period.
    Returns:
        pd.Series: EMA values.
    """
    return ta.trend.EMAIndicator(df['close'], window=window).ema_indicator()