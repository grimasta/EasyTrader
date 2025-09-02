from abc import ABC, abstractmethod
from grok_produce.structured.indicators import calculate_rsi, calculate_bollinger_bands, calculate_volume_ma, calculate_ema, calculate_stochastic_rsi, calculate_fourier_seasonality, calculate_rolling_sum

class Strategy(ABC):
    """Base class for trading strategies."""
    @abstractmethod
    def apply_indicators(self, df, timeframe='5m'):
        """Apply indicators to DataFrame."""
        pass

    @abstractmethod
    def check_signals(self, df_5m, df_4h, idx):
        """Check for trade signals."""
        pass

class CurrentStrategy(Strategy):
    """Current strategy: RSI < 30, Bollinger Band breakout, volume spike, 4h confluence."""
    def apply_indicators(self, df, timeframe='5m'):
        df = df.copy()
        df['rsi'] = calculate_rsi(df, window=14)
        df['bb_lower'], df['bb_upper'] = calculate_bollinger_bands(df, window=20, std_dev=2)
        df['volume_ma'] = calculate_volume_ma(df, window=20)
        if timeframe == '4h':
            df['ema_100'] = calculate_ema(df, window=100)
        return df

    def check_4h_confluence(self, df_4h, current_time):
        valid_candles = df_4h[df_4h['timestamp'] <= current_time]
        if valid_candles.empty:
            return False
        latest_4h = valid_candles.iloc[-1]
        price = latest_4h['close']
        bb_lower = latest_4h['bb_lower']
        ema_100 = latest_4h['ema_100']
        return abs(price - bb_lower) / price < 0.03

    def check_signals(self, df_5m, df_4h, idx):
        latest = df_5m.iloc[idx]
        prev = df_5m.iloc[idx-1]
        buy_signal = (latest['rsi'] < 30) and (latest['close'] > latest['bb_lower']) and (prev['close'] <= prev['bb_lower'])
        volume_spike = latest['volume'] > 1.2 * latest['volume_ma']
        confluence = self.check_4h_confluence(df_4h, latest['timestamp'])
        return buy_signal and volume_spike and confluence

class StochasticStrategy(Strategy):
    """Stochastic RSI < 0.2, Bollinger Band breakout, volume spike, 4h BB only."""
    def apply_indicators(self, df, timeframe='5m'):
        df = df.copy()
        df['stoch_rsi'] = calculate_stochastic_rsi(df, window=14)
        df['bb_lower'], df['bb_upper'] = calculate_bollinger_bands(df, window=20, std_dev=2)
        df['volume_ma'] = calculate_volume_ma(df, window=20)
        return df

    def check_4h_confluence(self, df_4h, current_time):
        valid_candles = df_4h[df_4h['timestamp'] <= current_time]
        if valid_candles.empty:
            return False
        latest_4h = valid_candles.iloc[-1]
        price = latest_4h['close']
        bb_lower = latest_4h['bb_lower']
        return abs(price - bb_lower) / price < 0.03

    def check_signals(self, df_5m, df_4h, idx):
        latest = df_5m.iloc[idx]
        prev = df_5m.iloc[idx-1]
        buy_signal = (latest['stoch_rsi'] < 0.2) and (latest['close'] > latest['bb_lower']) and (prev['close'] <= prev['bb_lower'])
        volume_spike = latest['volume'] > 1.2 * latest['volume_ma']
        confluence = self.check_4h_confluence(df_4h, latest['timestamp'])
        return buy_signal and volume_spike and confluence

class FourierMomentumStrategy(Strategy):
    """New strategy: Stochastic RSI < 0.2, Fourier seasonality, rolling sum momentum, 4h BB."""
    def apply_indicators(self, df, timeframe='5m'):
        df = df.copy()
        df['stoch_rsi'] = calculate_stochastic_rsi(df, window=14)
        df['bb_lower'], df['bb_upper'] = calculate_bollinger_bands(df, window=20, std_dev=2)
        df['volume_ma'] = calculate_volume_ma(df, window=20)
        df['fourier_signal'] = calculate_fourier_seasonality(df, window=100, top_n=3)
        df['rolling_sum'] = calculate_rolling_sum(df, window=100)
        return df

    def check_4h_confluence(self, df_4h, current_time):
        valid_candles = df_4h[df_4h['timestamp'] <= current_time]
        if valid_candles.empty:
            return False
        latest_4h = valid_candles.iloc[-1]
        price = latest_4h['close']
        bb_lower = latest_4h['bb_lower']
        return abs(price - bb_lower) / price < 0.05  # Increased to 5%

    def check_signals(self, df_5m, df_4h, idx):
        latest = df_5m.iloc[idx]
        prev = df_5m.iloc[idx-1]
        buy_signal = (latest['stoch_rsi'] < 0.2) and (latest['close'] > latest['bb_lower']) and (prev['close'] <= prev['bb_lower'])
        volume_spike = latest['volume'] > 1.2 * latest['volume_ma']
        fourier_buy = latest['fourier_signal'] == 1  # Cycle low
        momentum_buy = latest['rolling_sum'] < 0  # Oversold
        confluence = self.check_4h_confluence(df_4h, latest['timestamp'])
        return buy_signal and volume_spike and fourier_buy and momentum_buy and confluence

STRATEGIES = {
    'current': CurrentStrategy(),
    'stochastic': StochasticStrategy(),
    'fourier_momentum': FourierMomentumStrategy()
}