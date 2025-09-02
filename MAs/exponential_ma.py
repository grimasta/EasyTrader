import numpy as np


def exponential_moving_average(alpha, window_size, data):
    # Calculate weights using exponential decay formula
    weights = np.exp(np.linspace(-1.0, 0.0, window_size) / alpha)

    # Normalize weights to sum to 1
    weights /= weights.sum()

    # Use convolution to calculate EMA
    ema = np.convolve(data, weights, mode='full')[:len(data)]

    return ema