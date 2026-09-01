import pandas as pd
import logging
# import colorlog
import os
# Create a logger
# logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO) # Set the desired logging level

# Create a ColorizingStreamHandler
# handler = colorlog.StreamHandler()
from venues.bitget_v2.api_client import fetch_data
from strategies.strategies import STRATEGIES

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger().setLevel(logging.INFO)

# Strategy parameters
SYMBOLS = [
    'BTCUSDT','ETHUSDT','SOLUSDT','DOGEUSDT','XRPUSDT','BNBUSDT','TRXUSDT',
    'ADAUSDT','LINKUSDT','DOTUSDT','AVAXUSDT','ICPUSDT','LTCUSDT',
    # 'NEARUSDT', # negative with best_momentum_o200
    'HBARUSDT',
    'FETUSDT',
    'SEIUSDT','AAVEUSDT','SUIUSDT','HNTUSDT','SUSHIUSDT',
    # 'SANDUSDT', # negative with best_momentum_o200
    # 'SXPUSDT', # negative with best_momentum_o200
    'CHRUSDT',
    # 'SFPUSDT', # negative with best_momentum_o200
    'BCHUSDT','BATUSDT',
    # 'KSMUSDT', # negative with best_momentum_o200
    # 'EOSUSDT', # negative with best_momentum_o200
    'XLMUSDT',
    # 'ATOMUSDT','ALGOUSDT','POLUSDT', # negative with best_momentum_o200
    # 'SUSDT'
    ]
# ICP backtest negative!!!!
# LTC backtest neutral (slightly negative!!!)
# NEAR backtest very negative!!!!
INITIAL_BALANCE = 28.44 # 2022-04-01 - 2023-01-01
INITIAL_BALANCE = 14.69 # 2023-01-01 - 2023-08-01
INITIAL_BALANCE = 80.16 # 2023-08-01 - 2024-04-01
INITIAL_BALANCE = 322.11 # 2024-04-01 - 2025-01-01
INITIAL_BALANCE = 1535.58 # 2025-01-01 - 2025-08-01
INITIAL_BALANCE = 10 # 2025-01-01 - 2025-08-01

LEVERAGE = 10
POSITION_SIZE = 0.01
PROFIT_TARGET = 0.015  # 1.2% gross
STOP_LOSS = 0.03  # 2.5% loss
MAX_TRADES_PER_DAY = 10  # Increased
STRATEGY_NAME = 'best_momentum'
STRATEGY_NAME = 'best_momentum_o200_4hATR'

# formatter = colorlog.ColoredFormatter(
#     '%(log_color)s%(levelname)-8s%(reset)s %(message)s',
#     log_colors={
#         'INFO': 'green',  # Set INFO messages to green
#         'WARNING': 'yellow',
#         'ERROR': 'red',
#         'CRITICAL': 'bold_red',
#     },
#     reset=True,
#     style='%'
# )


# Simulate trade
def simulate_trade(symbol, entry_price, amount, df_5m, start_idx, atr):
    """
    Simulate a trade with profit target, stop-loss, or EOD exit.
    Returns:
        float: Multiplier for balance.
    """
    for idx in range(start_idx, len(df_5m)):
        current_price_h = df_5m.iloc[idx]['close']
        current_price_l = df_5m.iloc[idx]['close']
        profit = (current_price_h - entry_price) / entry_price
        loss = (entry_price - current_price_l) / entry_price
        current_time = df_5m.iloc[idx]['timestamp']
        current_day = current_time.date()

        # if profit >= PROFIT_TARGET:

        if loss >= STOP_LOSS:

            # logging.info(f"LOSS   {current_day}:{current_time} Closed {symbol} at {current_price_l} for {loss*100:.2f}% loss")
            return (1 - (loss * LEVERAGE) - 0.002) * amount, idx - start_idx
        elif profit >= PROFIT_TARGET:
            # profit = (current_price_h - entry_price) / entry_price
            # logging.info(f"PROFIT {current_day}:{current_time} Closed {symbol} at {current_price_h} for {profit*100:.2f}% profit")
            return (1 + (profit * LEVERAGE) - 0.002) * amount, idx - start_idx
        # elif current_time.time().strftime("%H:%M") >= "23:59":
        #     logging.info(f"Closed {symbol} at {current_price_h} at EOD")
        #     return (1 + (((current_price_h - entry_price) / entry_price) * LEVERAGE) - 0.002) * amount, start_idx + idx

    return 1.0 * amount, idx - start_idx


def simulate_trade_short(symbol, entry_price, amount, df_5m, start_idx, atr):
    """
    Simulate a trade with profit target, stop-loss, or EOD exit.
    Returns:
        float: Multiplier for balance.
    """
    for idx in range(start_idx, len(df_5m)):
        current_price_h = df_5m.iloc[idx]['close']
        current_price_l = df_5m.iloc[idx]['close']
        loss = (current_price_h - entry_price) / entry_price
        profit = (entry_price - current_price_l) / entry_price
        current_time = df_5m.iloc[idx]['timestamp']
        current_day = current_time.date()

        # if profit >= PROFIT_TARGET:

        if loss >= STOP_LOSS:

            # logging.info(f"LOSS   {current_day}:{current_time} Closed {symbol} at {current_price_l} for {loss*100:.2f}% loss")
            return (1 - (loss * LEVERAGE) - 0.002) * amount, idx - start_idx
        elif profit >= PROFIT_TARGET:
            # profit = (entry_price - current_price_l) / entry_price
            # logging.info(f"PROFIT {current_day}:{current_time} Closed {symbol} at {current_price_h} for {profit*100:.2f}% profit")
            return (1 + (profit * LEVERAGE) - 0.002) * amount, idx - start_idx
        # elif current_time.time().strftime("%H:%M") >= "23:59":
        #     logging.info(f"Closed {symbol} at {current_price_h} at EOD")
        #     return (1 + (((current_price_h - entry_price) / entry_price) * LEVERAGE) - 0.002) * amount, start_idx + idx

    return 1.0 * amount, idx - start_idx

# Backtesting function
def backtest(strategy_name=STRATEGY_NAME):
    strategy = STRATEGIES.get(strategy_name)
    if not strategy:
        raise ValueError(f"Unknown strategy: {strategy_name}")

    balance = INITIAL_BALANCE
    daily_returns = []
    start_date = '2020-01-01'
    end_date = '2025-09-01'
    trades_today = {symbol: {} for symbol in SYMBOLS}
    trade_log = []

    for symbol in SYMBOLS:
        starting_b = balance
        print(f'{balance} before {symbol}')
        if os.path.exists(f'df_5m_{symbol}.csv'):
            print("reading")
            df_5m = pd.read_csv(f'df_5m_{symbol}.csv')
            df_4h = pd.read_csv(f'df_4h_{symbol}.csv')
        else:
            logging.info(f"Backtesting {symbol} with {strategy_name} strategy")
            try:
                df_5m = fetch_data(symbol, timeframe='5m', start_date=start_date, end_date=end_date)
                df_4h = fetch_data(symbol, timeframe='4h', start_date=start_date, end_date=end_date)
            except:
                print(f"symbol: {symbol} does not exist")
                continue
            # Ensure timestamps are proper pandas datetime for downstream .date()/.time() usage
            df_5m.to_csv(f'df_5m_{symbol}.csv', index=False)
            df_4h.to_csv(f'df_4h_{symbol}.csv', index=False)
        for df in (df_5m, df_4h):
            if df is not None and 'timestamp' in df.columns:
                ts = df['timestamp']
                if not pd.api.types.is_datetime64_any_dtype(ts):
                    # Convert from milliseconds since epoch if numeric, otherwise try generic parsing
                    if pd.api.types.is_numeric_dtype(ts):
                        df['timestamp'] = pd.to_datetime(ts, unit='ms', errors='coerce')
                    else:
                        df['timestamp'] = pd.to_datetime(ts, errors='coerce')
                # Drop any rows where timestamp could not be parsed
                df.dropna(subset=['timestamp'], inplace=True)
        if df_5m is None or df_4h is None or len(df_5m) < 100 or len(df_4h) < 50:
            logging.warning(f"Insufficient data for {symbol}: 5m={len(df_5m) if df_5m is not None else None}, 4h={len(df_4h) if df_4h is not None else None}")
            continue

        df_5m = strategy.apply_indicators(df_5m, timeframe='5m')
        df_4h = strategy.apply_indicators(df_4h, timeframe='4h')
        df_5m = df_5m.dropna()
        df_4h = df_4h.dropna()

        logging.info(f"After indicators: 5m={len(df_5m)} candles, 4h={len(df_4h)} candles")
        skip_day = 0
        skip_buy = 0
        skip_sell = 0
        for idx in range(100, len(df_5m)):

            current_day = df_5m.iloc[idx]['timestamp'].date()
            if current_day not in trades_today[symbol]:
                trades_today[symbol][current_day] = 0
                skip_day -= 1

            if trades_today[symbol][current_day] >= MAX_TRADES_PER_DAY or skip_day > 0:
                continue
            signal_buy, atr = strategy.check_signal_buy(df_5m, df_4h, idx)
            signal_buy = False
            signal_sell, atr = strategy.check_signal_sell(df_5m, df_4h, idx)
            if skip_buy > 0:
                skip_buy -= 1
            else:
                if signal_buy:
                    price = df_5m.iloc[idx]['close']
                    amount = (balance * POSITION_SIZE)
                    balance -= (balance * POSITION_SIZE)
                    R_PnL, skip_buy = simulate_trade(symbol, price, amount, df_5m, idx, atr)
                    balance += R_PnL
                    daily_returns.append(R_PnL - 1)
                    if R_PnL < 0:
                        trades_today [symbol][current_day] = 10
                        skip_day = 3
                        continue
                    trades_today[symbol][current_day] += 1
                    trade_log.append({
                        'symbol': symbol,
                        'strategy': strategy_name,
                        'timestamp': df_5m.iloc[idx]['timestamp'],
                        'entry_price': price,
                        'exit_price': df_5m.iloc[idx]['close'] if idx < len(df_5m) else price,
                        'return': (R_PnL/amount)-1,
                        'balance': balance,
                        'stoch_rsi': df_5m.iloc[idx]['stoch_rsi'] if 'stoch_rsi' in df_5m.columns else None,
                        'macd': df_5m.iloc[idx]['macd'] if 'macd' in df_5m.columns else None,
                        'signal': df_5m.iloc[idx]['signal'] if 'signal' in df_5m.columns else None
                    })
            if skip_sell > 0:
                skip_sell -= 1
            else:
                if signal_sell:
                    price = df_5m.iloc[idx]['close']
                    amount = (balance * POSITION_SIZE)
                    balance -= (balance * POSITION_SIZE)
                    R_PnL, skip_sell = simulate_trade_short(symbol, price, amount, df_5m, idx, atr)
                    balance += R_PnL
                    daily_returns.append(R_PnL - 1)
                    if R_PnL < 0:
                        trades_today[symbol][current_day] = 10
                        skip_day = 3
                        continue
                    trades_today[symbol][current_day] += 1
                    trade_log.append({
                        'symbol': symbol,
                        'strategy': strategy_name,
                        'timestamp': df_5m.iloc[idx]['timestamp'],
                        'entry_price': price,
                        'exit_price': df_5m.iloc[idx]['close'] if idx < len(df_5m) else price,
                        'return': (R_PnL / amount) - 1,
                        'balance': balance,
                        'stoch_rsi': df_5m.iloc[idx]['stoch_rsi'] if 'stoch_rsi' in df_5m.columns else None,
                        'macd': df_5m.iloc[idx]['macd'] if 'macd' in df_5m.columns else None,
                        'signal': df_5m.iloc[idx]['signal'] if 'signal' in df_5m.columns else None
                    })
                # logging.info(f"New trade for {symbol} at {price}. Balance: ${balance:.2f}")
        print(f'{(balance - starting_b)/starting_b} profit for {symbol}')
    # Calculate returns
    total_days = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days
    total_return = balance / INITIAL_BALANCE - 1
    avg_daily_return = total_return / total_days if total_days > 0 else 0
    annual_return = (1 + total_return) ** (365 / total_days) - 1 if total_days > 0 else 0

    logging.info(f"Final balance: ${balance:.2f}")
    logging.info(f"Total return: {total_return*100:.2f}%")
    logging.info(f"Average daily return: {avg_daily_return*100:.2f}%")
    logging.info(f"Compounded annual return: {annual_return*100:.2f}%")
    logging.info(f"Total trades: {len(trade_log)}")

    pd.DataFrame(trade_log).to_csv(f'trade_log_{strategy_name}.csv', index=False)
    logging.info(f"Trade log saved to trade_log_{strategy_name}.csv")

if __name__ == "__main__":
    backtest()