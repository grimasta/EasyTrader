import pandas as pd
import numpy as np

def calculate_atr(df, window=14):
    """
    Calculate Average True Range (ATR) for a given DataFrame.

    Args:
        df (pd.DataFrame): DataFrame with columns ['open', 'high', 'low', 'close']
        window (int): Lookback period for ATR calculation (default: 14)

    Returns:
        pd.Series: ATR values
    """
    df = df.copy()

    # Calculate True Range (TR)
    df['high_low'] = df['high'] - df['low']
    df['high_prev_close'] = abs(df['high'] - df['close'].shift(1))
    df['low_prev_close'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['high_low', 'high_prev_close', 'low_prev_close']].max(axis=1)

    # Calculate ATR (exponential moving average of TR)
    atr = df['tr'].ewm(span=window, adjust=False).mean()

    return atr.rename('atr')