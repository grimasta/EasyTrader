import pandas as pd

def calculate_volume_ma(df, window=20):
    """
    Calculate moving average of volume.
    Args:
        df (pd.DataFrame): DataFrame with 'volume' column.
        window (int): Period for moving average.
    Returns:
        pd.Series: Volume MA values.
    """
    return df['volume'].rolling(window=window).mean()