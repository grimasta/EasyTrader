from grok_produce.structured.indicators import calculate_rsi, calculate_bollinger_bands, calculate_volume_ma, \
    calculate_ema

def apply_indicators(df, timeframe='5m'):
    """
    Apply indicators to DataFrame based on timeframe.
    Args:
        df (pd.DataFrame): OHLCV DataFrame.
        timeframe (str): '5m' or '4h'.
    Returns:
        pd.DataFrame: DataFrame with indicator columns.
    """
    df = df.copy()
    df['rsi'] = calculate_rsi(df, window=14)
    df['bb_lower'], df['bb_upper'] = calculate_bollinger_bands(df, window=20, std_dev=2)
    df['volume_ma'] = calculate_volume_ma(df, window=20)
    if timeframe == '4h':
        df['ema_100'] = calculate_ema(df, window=100)
    return df

def check_4h_confluence(df_4h, current_time):
    """
    Check 4-hour timeframe for confluence.
    Args:
        df_4h (pd.DataFrame): 4-hour DataFrame with indicators.
        current_time (pd.Timestamp): Current 5-minute timestamp.
    Returns:
        bool: True if confluence conditions are met.
    """
    valid_candles = df_4h[df_4h['timestamp'] <= current_time]
    if valid_candles.empty:
        return False
    latest_4h = valid_candles.iloc[-1]
    price = latest_4h['close']
    bb_lower = latest_4h['bb_lower']
    ema_100 = latest_4h['ema_100']
    # Loosened to 2% proximity
    return abs(price - bb_lower) / price < 0.02 and price < ema_100

def check_signals(df_5m, df_4h, idx):
    """
    Check for trade signals using 5-minute and 4-hour data.
    Args:
        df_5m (pd.DataFrame): 5-minute DataFrame with indicators.
        df_4h (pd.DataFrame): 4-hour DataFrame with indicators.
        idx (int): Current index in df_5m.
    Returns:
        bool: True if buy signal is detected.
    """
    latest = df_5m.iloc[idx]
    prev = df_5m.iloc[idx-1]
    buy_signal = (latest['rsi'] < 30) and (latest['close'] > latest['bb_lower']) and (prev['close'] <= prev['bb_lower'])
    volume_spike = latest['volume'] > 1.2 * latest['volume_ma']
    confluence = check_4h_confluence(df_4h, latest['timestamp'])
    return buy_signal and volume_spike and confluence