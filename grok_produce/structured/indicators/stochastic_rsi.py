import pandas as pd
import ta

def calculate_stochastic_rsi(df, window=14):
    return ta.momentum.StochRSIIndicator(df['close'], window=window).stochrsi()