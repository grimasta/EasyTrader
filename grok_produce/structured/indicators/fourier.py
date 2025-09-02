import pandas as pd
import numpy as np
from scipy.fft import fft

def calculate_fourier_seasonality(df, window=100, top_n=3):
    """
    Apply Fourier Transform to close prices to identify seasonality.
    Args:
        df (pd.DataFrame): DataFrame with 'close' column.
        window (int): Lookback period for FFT.
        top_n (int): Number of dominant frequencies to consider.
    Returns:
        pd.Series: Seasonality signal (1 for cycle low, -1 for cycle high, 0 otherwise).
    """
    close = df['close'].tail(window).values
    if len(close) < window:
        return pd.Series(0, index=df.index)

    # Compute FFT
    fft_vals = fft(close)
    frequencies = np.fft.fftfreq(len(close))
    power = np.abs(fft_vals)
    positive_freqs = frequencies > 0
    top_indices = np.argsort(power[positive_freqs])[-top_n:]
    top_freqs = frequencies[positive_freqs][top_indices]

    # Estimate cycle period and phase
    cycle_periods = [1 / f for f in top_freqs if f != 0]
    signal = np.zeros(len(df))
    latest_price = close[-1]
    mean_price = np.mean(close)

    # Check if price is at cycle low or high
    for period in cycle_periods:
        phase = 2 * np.pi * (len(close) % period) / period
        if np.cos(phase) < -0.8 and latest_price < mean_price:  # Cycle low
            signal[-1] = 1
        elif np.cos(phase) > 0.8 and latest_price > mean_price:  # Cycle high
            signal[-1] = -1

    return pd.Series(signal, index=df.index)