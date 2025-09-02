import pandas as pd
from datetime import datetime
import logging
from grok_produce.structured.api_client.bg_client import fetch_data
from grok_produce.structured.strategies.FourierMomentumeStrategy import STRATEGIES

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Strategy parameters
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT', 'XRPUSDT']
INITIAL_BALANCE = 10.0
LEVERAGE = 10
POSITION_SIZE = 2.0
PROFIT_TARGET = 0.012  # 1.2% gross
STOP_LOSS = 0.025  # 2.5% loss (increased)
MAX_TRADES_PER_DAY = 2
STRATEGY_NAME = 'fourier_momentum'  # Test new strategy; switch to 'current' or 'stochastic'

# Simulate trade
def simulate_trade(symbol, entry_price, amount, df_5m, start_idx):
    """
    Simulate a trade with profit target, stop-loss, or EOD exit.
    Returns:
        float: Multiplier for balance (e.g., 1.01 for 1% net gain).
    """
    for idx in range(start_idx, len(df_5m)):
        current_price = df_5m.iloc[idx]['close']
        profit = (current_price - entry_price) / entry_price
        loss = (entry_price - current_price) / entry_price
        current_time = df_5m.iloc[idx]['timestamp']
        current_day = current_time.date()

        if profit >= PROFIT_TARGET:
            logging.info(f"Closed {symbol} at {current_price} for {profit*100:.2f}% profit")
            return 1 + PROFIT_TARGET - 0.002
        elif loss >= STOP_LOSS:
            logging.info(f"Closed {symbol} at {current_price} for {loss*100:.2f}% loss")
            return 1 - STOP_LOSS - 0.002
        elif current_time.time().strftime("%H:%M") >= "23:59":
            logging.info(f"Closed {symbol} at {current_price} at EOD")
            return 1 + (current_price - entry_price) / entry_price - 0.002

    return 1.0

# Backtesting function
def backtest(strategy_name=STRATEGY_NAME):
    strategy = STRATEGIES.get(strategy_name)
    if not strategy:
        raise ValueError(f"Unknown strategy: {strategy_name}")

    balance = INITIAL_BALANCE
    daily_returns = []
    start_date = '2024-08-01'
    end_date = '2025-08-01'
    trades_today = {symbol: {} for symbol in SYMBOLS}
    trade_log = []

    for symbol in SYMBOLS:
        logging.info(f"Backtesting {symbol} with {strategy_name} strategy")
        df_5m = fetch_data(symbol, timeframe='5m', start_date=start_date, end_date=end_date)
        df_4h = fetch_data(symbol, timeframe='4h', start_date=start_date, end_date=end_date)
        if df_5m is None or df_4h is None or len(df_5m) < 100 or len(df_4h) < 100:
            logging.warning(f"Insufficient data for {symbol}")
            continue

        df_5m = strategy.apply_indicators(df_5m, timeframe='5m')
        df_4h = strategy.apply_indicators(df_4h, timeframe='4h')
        df_5m = df_5m.dropna()
        df_4h = df_4h.dropna()

        for idx in range(100, len(df_5m)):  # Start after 100 candles for Fourier
            current_day = df_5m.iloc[idx]['timestamp'].date()
            if current_day not in trades_today[symbol]:
                trades_today[symbol][current_day] = 0

            if trades_today[symbol][current_day] >= MAX_TRADES_PER_DAY:
                continue

            if strategy.check_signals(df_5m, df_4h, idx):
                price = df_5m.iloc[idx]['close']
                amount = (POSITION_SIZE * LEVERAGE) / price
                multiplier = simulate_trade(symbol, price, amount, df_5m, idx)
                balance *= multiplier
                daily_returns.append(multiplier - 1)
                trades_today[symbol][current_day] += 1
                trade_log.append({
                    'symbol': symbol,
                    'strategy': strategy_name,
                    'timestamp': df_5m.iloc[idx]['timestamp'],
                    'entry_price': price,
                    'exit_price': df_5m.iloc[idx]['close'] if idx < len(df_5m) else price,
                    'return': (multiplier - 1) * 100,
                    'balance': balance,
                    'stoch_rsi': df_5m.iloc[idx]['stoch_rsi'] if 'stoch_rsi' in df_5m.columns else None,
                    'fourier_signal': df_5m.iloc[idx]['fourier_signal'] if 'fourier_signal' in df_5m.columns else None,
                    'rolling_sum': df_5m.iloc[idx]['rolling_sum'] if 'rolling_sum' in df_5m.columns else None
                })
                logging.info(f"New balance: ${balance:.2f}")

    avg_daily_return = sum(daily_returns) / len(daily_returns) if daily_returns else 0
    annual_return = (1 + avg_daily_return) ** 365 - 1
    logging.info(f"Final balance: ${balance:.2f}")
    logging.info(f"Average daily return: {avg_daily_return*100:.2f}%")
    logging.info(f"Compounded annual return: {annual_return*100:.2f}%")

    # Save trade log
    pd.DataFrame(trade_log).to_csv(f'trade_log_{strategy_name}.csv', index=False)
    logging.info(f"Trade log saved to trade_log_{strategy_name}.csv")

if __name__ == "__main__":
    backtest()