import pandas as pd

def calculate_rolling_sum(df, window=100):
    """
    Calculate rolling sum of volume * price for bullish/bearish candles.
    Args:
        df (pd.DataFrame): DataFrame with 'open', 'close', 'volume' columns.
        window (int): Lookback period.
    Returns:
        pd.Series: Rolling sum (negative = buy territory, positive = sell territory).
    """
    sum_values = []
    for i in range(len(df)):
        if i < window:
            sum_values.append(0)
            continue
        window_df = df.iloc[i-window:i]
        total = 0
        for _, row in window_df.iterrows():
            price = row['close']
            volume = row['volume']
            if row['close'] > row['open']:
                total += volume * price  # Bullish
            else:
                total -= volume * price  # Bearish
        sum_values.append(total)
    return pd.Series(sum_values, index=df.index)