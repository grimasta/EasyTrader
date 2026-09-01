from abc import ABC, abstractmethod
from encodings.punycode import selective_len

from venues.structured.indicators import calculate_rsi, calculate_bollinger_bands, calculate_volume_ma, calculate_ema, calculate_stochastic_rsi, calculate_fourier_seasonality, calculate_rolling_sum, calculate_macd, calculate_sma, calculate_atr
import logging


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
    """Fourier seasonality, rolling sum momentum, Stochastic RSI < 0.2, 4h BB."""
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
        return abs(price - bb_lower) / price < 0.05

    def check_signals(self, df_5m, df_4h, idx):
        latest = df_5m.iloc[idx]
        prev = df_5m.iloc[idx-1]
        buy_signal = (latest['stoch_rsi'] < 0.2) and (latest['close'] > latest['bb_lower']) and (prev['close'] <= prev['bb_lower'])
        volume_spike = latest['volume'] > 1.2 * latest['volume_ma']
        fourier_buy = latest['fourier_signal'] == 1
        momentum_buy = latest['rolling_sum'] < 0
        confluence = self.check_4h_confluence(df_4h, latest['timestamp'])
        return buy_signal and volume_spike and fourier_buy and momentum_buy and confluence

class BestMomentumStrategy(Strategy):
    """Stochastic RSI, MACD, Volume, relaxed conditions."""
    def apply_indicators(self, df, timeframe='5m'):
        df = df.copy()
        df['stoch_rsi'] = calculate_stochastic_rsi(df, window=14)
        df['bb_lower'], df['bb_upper'] = calculate_bollinger_bands(df, window=20, std_dev=2)
        df['volume_ma'] = calculate_volume_ma(df, window=20)
        df['macd'], df['signal'] = calculate_macd(df, fast=6, slow=13, signal=5)
        df['atr'] = calculate_atr(df)
        return df

    def check_4h_confluence(self, df_4h, current_time):
        return True  # No 4h requirement

    def check_signals(self, df_5m, df_4h, idx):
        latest = df_5m.iloc[idx]
        prev = df_5m.iloc[idx-1] if idx > 0 else latest
        buy_signal = (latest['stoch_rsi'] < 0.3)
        volume_spike = latest['volume'] > 1.2 * latest['volume_ma']
        macd_signal = latest['macd'] > latest['signal']
        confluence = self.check_4h_confluence(df_4h, latest['timestamp'])
        atr = latest['atr']
        # Debug logging
        logging.debug(f"Signal check for {df_5m.iloc[idx]['timestamp']}: "
                      f"stoch_rsi={latest['stoch_rsi']:.3f}, "
                      f"volume_spike={latest['volume'] > 1.2 * latest['volume_ma']}, "
                      f"macd={latest['macd']:.2f}, signal={latest['signal']:.2f}, "
                      f"macd_signal={macd_signal}, "
                      f"confluence={confluence}")

        return (buy_signal or macd_signal) and volume_spike and confluence, atr

class BestMomentumStrategyO200(Strategy):
    """Stochastic RSI, MACD, Volume, relaxed conditions."""
    def apply_indicators(self, df, timeframe='5m'):
        df = df.copy()
        df['stoch_rsi'] = calculate_stochastic_rsi(df, window=14)
        df['bb_lower'], df['bb_upper'] = calculate_bollinger_bands(df, window=20, std_dev=2)
        df['volume_ma'] = calculate_volume_ma(df, window=20)
        df['macd'], df['signal'] = calculate_macd(df, fast=6, slow=13, signal=5)
        df['atr'] = calculate_atr(df)
        if timeframe == '4h':
            df['ema_100'] = calculate_ema(df, window=100)
        elif timeframe == '5m':
            df['5m_ema200'] = calculate_ema(df, window=200)
        return df

    def check_4h_confluence(self, df_4h, current_time):
        return True  # No 4h requirement

    def check_signals(self, df_5m, df_4h, idx):
        latest = df_5m.iloc[idx]
        prev = df_5m.iloc[idx-1] if idx > 0 else latest
        buy_signal = (latest['stoch_rsi'] < 0.3)
        volume_spike = latest['volume'] > 1.2 * latest['volume_ma']
        macd_signal = latest['macd'] > latest['signal']
        confluence = self.check_4h_confluence(df_4h, latest['timestamp'])
        o200 = latest['5m_ema200'] < latest['close']
        atr = latest['atr']
        # Debug logging
        logging.debug(f"Signal check for {df_5m.iloc[idx]['timestamp']}: "
                      f"stoch_rsi={latest['stoch_rsi']:.3f}, "
                      f"volume_spike={latest['volume'] > 1.2 * latest['volume_ma']}, "
                      f"macd={latest['macd']:.2f}, signal={latest['signal']:.2f}, "
                      f"macd_signal={macd_signal}, "
                      f"confluence={confluence}")

        return (buy_signal or macd_signal) and volume_spike and confluence and o200, atr


class BestMomentumStrategyO200_4hATR(Strategy):
    """Stochastic RSI, MACD, Volume, relaxed conditions."""
    def apply_indicators(self, df, timeframe='5m'):
        df = df.copy()
        df['stoch_rsi'] = calculate_stochastic_rsi(df, window=14)
        df['bb_lower'], df['bb_upper'] = calculate_bollinger_bands(df, window=20, std_dev=2)
        df['volume_ma'] = calculate_volume_ma(df, window=20)
        df['macd'], df['signal'] = calculate_macd(df, fast=6, slow=13, signal=5)
        df['atr'] = calculate_atr(df)
        if timeframe == '4h':
            df['ema_100'] = calculate_ema(df, window=100)
        elif timeframe == '5m':
            df['5m_ema200'] = calculate_ema(df, window=200)
        return df

    def check_4h_confluence(self, df_4h, current_time):
        return True  # No 4h requirement

    def check_signals(self, df_5m, df_4h, idx):
        return True, 0

    def check_signal_buy(self, df_5m, df_4h, idx):
        latest = df_5m.iloc[idx]
        prev = df_5m.iloc[idx-1] if idx > 0 else latest
        buy_signal = (latest['stoch_rsi'] < 0.3)
        volume_spike = latest['volume'] > 1.2 * latest['volume_ma']
        macd_signal = latest['macd'] > latest['signal']
        confluence = self.check_4h_confluence(df_4h, latest['timestamp'])
        o200 = latest['5m_ema200'] < latest['close']
        atr_4h = df_4h.iloc[-1]['atr']
        atr_4h_over_required = atr_4h > 0.02 * latest['close']
        atr = latest['atr']
        # Debug logging
        logging.debug(f"Signal check for {df_5m.iloc[idx]['timestamp']}: "
                      f"stoch_rsi={latest['stoch_rsi']:.3f}, "
                      f"volume_spike={latest['volume'] > 1.2 * latest['volume_ma']}, "
                      f"macd={latest['macd']:.2f}, signal={latest['signal']:.2f}, "
                      f"macd_signal={macd_signal}, "
                      f"confluence={confluence}")

        return (buy_signal or macd_signal) and volume_spike and confluence and o200, atr

    def check_signal_sell(self, df_5m, df_4h, idx):
        latest = df_5m.iloc[idx]
        prev = df_5m.iloc[idx-1] if idx > 0 else latest
        sell_signal = (latest['stoch_rsi'] > 0.9)
        volume_spike = latest['volume'] > 1.2 * latest['volume_ma']
        macd_signal = latest['macd'] < latest['signal']
        confluence = self.check_4h_confluence(df_4h, latest['timestamp'])
        o200 = latest['5m_ema200'] > latest['close']
        atr_4h = df_4h.iloc[-1]['atr']
        atr_4h_over_required = atr_4h > 0.02 * latest['close']
        atr = latest['atr']
        # Debug logging
        logging.debug(f"Signal check for {df_5m.iloc[idx]['timestamp']}: "
                      f"stoch_rsi={latest['stoch_rsi']:.3f}, "
                      f"volume_spike={latest['volume'] > 1.2 * latest['volume_ma']}, "
                      f"macd={latest['macd']:.2f}, signal={latest['signal']:.2f}, "
                      f"macd_signal={macd_signal}, "
                      f"confluence={confluence}")

        return (sell_signal or macd_signal) and volume_spike and confluence and o200, atr

STRATEGIES = {
    'current': CurrentStrategy(),
    'stochastic': StochasticStrategy(),
    'fourier_momentum': FourierMomentumStrategy(),
    'best_momentum': BestMomentumStrategy(),
    'best_momentum_o200': BestMomentumStrategyO200(),
    'best_momentum_o200_4hATR': BestMomentumStrategyO200_4hATR()
}