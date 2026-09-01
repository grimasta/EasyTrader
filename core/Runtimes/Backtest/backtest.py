import ccxt
import pandas as pd
import ta
import requests
import time
from datetime import datetime, timedelta
import logging

# Configure logging
from venues.grok_auto_bitget_2 import fetch_data

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize Bitget API
exchange = ccxt.bitget({
    'apiKey': 'YOUR_API_KEY',
    'secret': 'YOUR_SECRET_KEY',
    'password': 'YOUR_PASSPHRASE',
    'enableRateLimit': True,
})

# Fetch data function (as above)
# [Insert the fetch_data and fetch_data_coingecko functions from above]

# Strategy parameters
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT', 'XRPUSDT']
INITIAL_BALANCE = 10.0
LEVERAGE = 10
POSITION_SIZE = 2.0
PROFIT_TARGET = 0.012
STOP_LOSS = 0.02

# Calculate indicators
def calculate_indicators(df):
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    bb = ta.volatility.BollingerBands(df['close'], window=40, window_dev=2.5)
    df['bb_lower'] = bb.bollinger_lband()
    df['bb_upper'] = bb.bollinger_hband()
    df['volume_ma'] = df['volume'].rolling(window=40).mean()
    return df

# Check for trade signals
def check_signals(df, idx):
    latest = df.iloc[idx]
    prev = df.iloc[idx-1]
    buy_signal = (latest['rsi'] < 30) and (latest['close'] > latest['bb_lower']) and (prev['close'] <= prev['bb_lower'])
    volume_spike = latest['volume'] > 1.2 * latest['volume_ma']
    return buy_signal and volume_spike

# Simulate trade
def simulate_trade(symbol, entry_price, amount, df, start_idx):
    for idx in range(start_idx, len(df)):
        current_price = df.iloc[idx]['close']
        profit = (current_price - entry_price) / entry_price
        loss = (entry_price - current_price) / entry_price
        current_time = df.iloc[idx]['timestamp']
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
def backtest():
    balance = INITIAL_BALANCE
    daily_returns = []
    start_date = '2024-08-01'
    end_date = '2025-08-01'

    for symbol in SYMBOLS:
        logging.info(f"Backtesting {symbol}")
        df = fetch_data(symbol, start_date=start_date, end_date=end_date)
        if df is None or len(df) < 20:
            logging.warning(f"Insufficient data for {symbol}")
            continue

        df = calculate_indicators(df)
        df = df.dropna()

        for idx in range(20, len(df)):
            if check_signals(df, idx):
                price = df.iloc[idx]['close']
                amount = (POSITION_SIZE * LEVERAGE) / price
                multiplier = simulate_trade(symbol, price, amount, df, idx)
                balance *= multiplier
                daily_returns.append(multiplier - 1)
                logging.info(f"New balance: ${balance:.2f}")

    avg_daily_return = sum(daily_returns) / len(daily_returns) if daily_returns else 0
    annual_return = (1 + avg_daily_return) ** 365 - 1
    logging.info(f"Final balance: ${balance:.2f}")
    logging.info(f"Average daily return: {avg_daily_return*100:.2f}%")
    logging.info(f"Compounded annual return: {annual_return*100:.2f}%")

if __name__ == "__main__":
    backtest()