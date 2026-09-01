import pandas as pd
import logging

from venues.bitget_v2.api_client import fetch_data

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Strategy parameters
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT', 'XRPUSDT']
INITIAL_BALANCE = 10.0
LEVERAGE = 10
POSITION_SIZE = 2.0
PROFIT_TARGET = 0.012  # 1.2% gross
STOP_LOSS = 0.015  # 1.5% loss (increased)
MAX_TRADES_PER_DAY = 2

# Simulate trade
def simulate_trade(symbol, entry_price, amount, df_5m, start_idx):
    """
    Simulate a trade with profit target, stop-loss, or EOD exit.
    Returns:
        float: Multiplier for balance (e.g., 1.01 for 1% net gain).
    """
    start_time = df_5m.iloc[start_idx]['timestamp']
    start_day = start_time.date()
    for idx in range(start_idx, len(df_5m)):
        current_price = df_5m.iloc[idx]['close']
        loss = ((current_price - entry_price) / entry_price) * amount
        profit = ((entry_price - current_price) / entry_price) * amount
        current_time = df_5m.iloc[idx]['timestamp']
        current_day = current_time.date()

        if profit >= PROFIT_TARGET:
            logging.info(f"Closed {symbol} at {current_price} for {profit*100:.2f}% profit")
            return 1 + PROFIT_TARGET - 0.002
        elif loss >= STOP_LOSS:
            logging.info(f"Closed {symbol} at {current_price} for {loss*100:.2f}% loss")
            return 1 - STOP_LOSS - 0.002
        elif current_day > start_day:
            logging.info(f"Closed {symbol} at {current_price} at EOD")
            return 1 + (current_price - entry_price) / entry_price - 0.002

    return 1.0

# Backtesting function
def backtest():
    balance = INITIAL_BALANCE
    daily_returns = []
    start_date = '2023-08-01'
    end_date = '2025-08-18'
    trades_today = {symbol: {} for symbol in SYMBOLS}
    trade_log = []  # Store trade details for analysis
    symbol_balance = {}
    df_1m_symbol = {}
    lens = 0
    timeframe = '1m'
    for symbol in SYMBOLS:
        import os
        if symbol not in symbol_balance:
            symbol_balance[symbol] = 2
        logging.info(f"Backtesting {symbol}")
        if (symbol + "_" + str(timeframe) + "_" + str(start_date) + "_" + str(end_date) + '.csv') in os.listdir():
            symbol_data = \
                pd.read_csv(symbol + "_" + str(timeframe) + "_" + str(start_date) + "_" + str(end_date) + '.csv',
                            parse_dates=['timestamp'],
                            dtype={
                                'open': float, 'high': float, 'low': float, 'close': float,
                                'volume': float
                            }
                            )
        else:
            symbol_data = fetch_data(symbol, timeframe=timeframe, start_date=start_date, end_date=end_date)
            symbol_data.to_csv(symbol + "_" + str(timeframe) + "_" + str(start_date) + "_" + str(end_date) + '.csv')
        df_1m_symbol[symbol] = symbol_data
        if len(df_1m_symbol[symbol]) > lens:
            lens = len(df_1m_symbol[symbol])
        # df_4h = fetch_data(symbol, timeframe='4h', start_date=start_date, end_date=end_date)
        # if df_5m is None or df_4h is None or len(df_5m) < 20 or len(df_4h) < 100:
        #     logging.warning(f"Insufficient data for {symbol}")
        #     continue
    open_symbol = {'BTCUSDT':False, 'ETHUSDT':False, 'SOLUSDT':False, 'DOGEUSDT':False, 'XRPUSDT':False}
    symbol_entry = {}
    current_day = ""
    start_time = "10:00"
    end_time = "11:00"
    symbol_balance = {}
    for idx in range(20, lens):
        # df_5m = apply_indicators(df_5m, timeframe='5m')
        # df_4h = apply_indicators(df_4h, timeframe='4h')
        # df_5m = df_5m.dropna()
        # df_4h = df_4h.dropna()
        # if current_day == "":
        #     current_day = df_1m_symbol[symbol].iloc[idx]['timestamp'].date()
        # if df_1m_symbol[symbol].iloc[idx]['timestamp'].date() > current_day:
        #     current_day = df_1m_symbol[symbol].iloc[idx]['timestamp'].date()
        #     print(f"end of {current_day} funds : ", balance)
        for symbol in df_1m_symbol:
            # current_day = df_5m.iloc[idx]['timestamp'].date()
            if df_1m_symbol[symbol].iloc[idx]['timestamp'].time().strftime("%H:%M") == start_time:
                symbol_entry[symbol] = df_1m_symbol[symbol].iloc[idx]['close']
                open_symbol[symbol]=True
                symbol_balance[symbol] = 0.01 * balance
            if open_symbol[symbol] and ((df_1m_symbol[symbol].iloc[idx]['close'] -
                                         symbol_entry[symbol])/symbol_entry[symbol]) < -0.1:
                open_symbol[symbol]=False
                exit_price = df_1m_symbol[symbol].iloc[idx]['close']
                # print(entry_price, exit_price, (exit_price-entry_price)/entry_price)
                # balance -= 0.01 * balance * (1 + ((exit_price-
                #                                    symbol_entry[symbol])/symbol_entry[symbol]) * LEVERAGE)
                balance -= symbol_balance[symbol]
                logging.info(f"trade closed at SL for {symbol} with current balance = {balance}")
                # print(symbol_balance[symbol])
            if open_symbol[symbol] and ((df_1m_symbol[symbol].iloc[idx]['close'] -
                                         symbol_entry[symbol])/symbol_entry[symbol]) > 0.026:
                open_symbol[symbol]=False
                exit_price = df_1m_symbol[symbol].iloc[idx]['close']
                # print(entry_price, exit_price, (exit_price-entry_price)/entry_price)
                balance += symbol_balance[symbol] * (((exit_price-
                                                   symbol_entry[symbol])/symbol_entry[symbol]) * LEVERAGE)
                logging.info(f"trade closed at TP for {symbol} with current balance = {balance}")
                # print(symbol_balance[symbol])
            if df_1m_symbol[symbol].iloc[idx]['timestamp'].time().strftime("%H:%M") == end_time and open_symbol[symbol]:
                open_symbol[symbol]=False
                exit_price = df_1m_symbol[symbol].iloc[idx]['close']
                # print(entry_price, exit_price, (exit_price-entry_price)/entry_price)
                balance += symbol_balance[symbol] * (((exit_price-
                                                   symbol_entry[symbol])/symbol_entry[symbol]) * LEVERAGE)
                logging.info(f"trade closed at {end_time} for {symbol} with current balance = {balance}")
                # print(symbol_balance[symbol])
    #         if current_day not in trades_today[symbol]:
    #             trades_today[symbol][current_day] = 0
    #
    #         if trades_today[symbol][current_day] >= MAX_TRADES_PER_DAY:
    #             continue
    #
    #         if check_signals(df_5m, df_4h, idx):
    #             price = df_5m.iloc[idx]['close']
    #             amount = (POSITION_SIZE * LEVERAGE) / price
    #             multiplier = simulate_trade(symbol, price, amount, df_5m, idx)
    #             balance *= multiplier
    #             daily_returns.append(multiplier - 1)
    #             trades_today[symbol][current_day] += 1
    #             # Log trade details
    #             trade_log.append({
    #                 'symbol': symbol,
    #                 'timestamp': df_5m.iloc[idx]['timestamp'],
    #                 'entry_price': price,
    #                 'exit_price': df_5m.iloc[idx]['close'] if idx < len(df_5m) else price,
    #                 'return': (multiplier - 1) * 100,
    #                 'balance': balance
    #             })
    #             logging.info(f"New balance: ${balance:.2f}")
    #
    # avg_daily_return = sum(daily_returns) / len(daily_returns) if daily_returns else 0
    # annual_return = (1 + avg_daily_return) ** 365 - 1
    logging.info(f"Final balance: ${balance:.2f}")
    # logging.info(f"Average daily return: {avg_daily_return*100:.2f}%")
    # logging.info(f"Compounded annual return: {annual_return*100:.2f}%")

    # Save trade log to CSV for analysis
    # pd.DataFrame(trade_log).to_csv('trade_log.csv', index=False)
    # logging.info("Trade log saved to trade_log.csv")

if __name__ == "__main__":
    backtest()