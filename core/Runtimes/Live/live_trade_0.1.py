import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta
import logging
from data_fetcher import fetch_data
from strategy import STRATEGIES

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('ccxt').setLevel(logging.WARNING)  # Suppress CCXT debug logs

# Strategy parameters
SYMBOLS = ['BTCUSDT_UMCBL', 'ETHUSDT_UMCBL', 'SOLUSDT_UMCBL', 'DOGEUSDT_UMCBL', 'XRPUSDT_UMCBL']  # Futures symbols
INITIAL_BALANCE = 10.0
LEVERAGE = 10
POSITION_SIZE = 2.0
PROFIT_TARGET = 0.012  # 1.2% gross
STOP_LOSS = 0.025  # 2.5% loss
MAX_TRADES_PER_DAY = 5
STRATEGY_NAME = 'best_momentum'

# Initialize Bitget API
exchange = ccxt.bitget({
    'apiKey': 'YOUR_SANDBOX_API_KEY',
    'secret': 'YOUR_SANDBOX_SECRET_KEY',
    'password': 'YOUR_SANDBOX_PASSPHRASE',
    'enableRateLimit': True,
    'verbose': False,
    'options': {'defaultType': 'swap', 'PAPTRADING': '1', 'marginMode': 'isolated'},
    'headers': {'PAPTRADING': '1'}
})
exchange.set_sandbox_mode(True)
logging.info("Using Bitget sandbox mode for live trading with isolated margin")

def fetch_sandbox_balance():
    """
    Fetch sandbox balance for futures account in isolated margin mode.
    Returns:
        float: Available USDT balance.
    """
    try:
        balance = exchange.fetch_balance(params={'marketType': 'umcbl', 'marginMode': 'isolated', 'PAPTRADING': '1'})
        available_usdt = balance['USDT']['free']
        logging.info(f"Sandbox available balance: {available_usdt} USDT")
        return available_usdt
    except Exception as e:
        logging.error(f"Failed to fetch balance: {e}")
        return None

def place_trade(symbol, price, amount, stop_loss_price, take_profit_price):
    """
    Place a market buy order, stop-loss, and take-profit order for futures in isolated margin mode.
    Returns:
        dict: Order details (buy order ID, stop-loss order ID, take-profit order ID).
    """
    try:
        # Set leverage with isolated margin mode
        exchange.set_leverage(leverage=LEVERAGE, symbol=symbol, params={'marginMode': 'isolated', 'marketType': 'umcbl', 'PAPTRADING': '1'})
        logging.info(f"Set leverage {LEVERAGE}x for {symbol} in isolated margin mode")

        # Place market buy order
        buy_order = exchange.create_market_buy_order(symbol, amount, params={'marketType': 'umcbl', 'marginMode': 'isolated', 'productType': 'umcbl', 'PAPTRADING': '1'})
        logging.info(f"Placed buy order for {symbol} at {price}, amount: {amount}")

        # Place stop-market sell order
        stop_loss_params = {
            'triggerPrice': stop_loss_price,
            'planType': 'loss_plan',
            'side': 'sell',
            'size': amount,
            'orderType': 'market',
            'marketType': 'umcbl',
            'marginMode': 'isolated',
            'PAPTRADING': '1'
        }
        stop_loss_order = exchange.create_order(symbol, 'stop', 'sell', amount, price=stop_loss_price, params=stop_loss_params)
        logging.info(f"Placed stop-loss order for {symbol} at {stop_loss_price}")

        # Place take-profit sell order
        take_profit_params = {
            'triggerPrice': take_profit_price,
            'planType': 'profit_plan',
            'side': 'sell',
            'size': amount,
            'orderType': 'market',
            'marketType': 'umcbl',
            'marginMode': 'isolated',
            'PAPTRADING': '1'
        }
        take_profit_order = exchange.create_order(symbol, 'stop', 'sell', amount, price=take_profit_price, params=take_profit_params)
        logging.info(f"Placed take-profit order for {symbol} at {take_profit_price}")

        return {
            'buy_order_id': buy_order['id'],
            'stop_loss_order_id': stop_loss_order['id'],
            'take_profit_order_id': take_profit_order['id']
        }

    except Exception as e:
        logging.error(f"Failed to place trade for {symbol}: {e}")
        return None

def check_stop_loss(symbol, stop_loss_order_id):
    """
    Check if stop-loss order has been hit.
    Returns:
        bool: True if stop-loss order is filled, False otherwise.
    """
    try:
        order = exchange.fetch_order(stop_loss_order_id, symbol, params={'marketType': 'umcbl', 'marginMode': 'isolated', 'PAPTRADING': '1'})
        status = order['status']
        logging.debug(f"Stop-loss order {stop_loss_order_id} for {symbol}: status={status}")
        return status in ['closed', 'filled']
    except Exception as e:
        logging.error(f"Failed to check stop-loss for {symbol}: {e}")
        return False

def check_take_profit(symbol, take_profit_order_id):
    """
    Check if take-profit order has been hit.
    Returns:
        bool: True if take-profit order is filled, False otherwise.
    """
    try:
        order = exchange.fetch_order(take_profit_order_id, symbol, params={'marketType': 'umcbl', 'marginMode': 'isolated', 'PAPTRADING': '1'})
        status = order['status']
        logging.debug(f"Take-profit order {take_profit_order_id} for {symbol}: status={status}")
        return status in ['closed', 'filled']
    except Exception as e:
        logging.error(f"Failed to check take-profit for {symbol}: {e}")
        return False

def is_position_open(symbol):
    """
    Check if a position is open for the symbol in isolated margin mode.
    Returns:
        bool: True if position is open, False otherwise.
    """
    try:
        positions = exchange.fetch_positions([symbol], params={'marketType': 'umcbl', 'marginMode': 'isolated', 'PAPTRADING': '1'})
        for pos in positions:
            if pos['contracts'] > 0:
                return True
        return False
    except Exception as e:
        logging.error(f"Failed to check position for {symbol}: {e}")
        return False

def live_trade(strategy_name=STRATEGY_NAME):
    strategy = STRATEGIES.get(strategy_name)
    if not strategy:
        raise ValueError(f"Unknown strategy: {strategy_name}")

    # Simulate $10 initial balance
    sandbox_balance = fetch_sandbox_balance()
    if sandbox_balance is None:
        logging.error("Cannot proceed without valid balance")
        return
    balance = min(INITIAL_BALANCE, sandbox_balance)
    logging.info(f"Using virtual balance: ${balance:.2f}")

    trades_today = {symbol: {} for symbol in SYMBOLS}
    trade_log = []
    open_positions = {}  # Track open trades: {symbol: {'buy_order_id': id, 'stop_loss_order_id': id, 'take_profit_order_id': id, 'entry_price': price, 'amount': amount}}

    while True:
        for symbol in SYMBOLS:
            current_day = datetime.now().date()
            if current_day not in trades_today[symbol]:
                trades_today[symbol][current_day] = 0

            if trades_today[symbol][current_day] >= MAX_TRADES_PER_DAY:
                continue

            # Set date range: end_date = now, start_date = 100 4h candles (400h) before
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(hours=400)).strftime('%Y-%m-%d')  # 100 * 4h = 400h
            logging.debug(f"Fetching data for {symbol}: start_date={start_date}, end_date={end_date}")

            # Fetch recent data
            df_5m = fetch_data(symbol, timeframe='5m', start_date=start_date, end_date=end_date, limit=100)
            df_4h = fetch_data(symbol, timeframe='4h', start_date=start_date, end_date=end_date, limit=50)

            if df_5m is None or df_4h is None or len(df_5m) < 100 or len(df_4h) < 50:
                logging.warning(f"Insufficient data for {symbol}: 5m={len(df_5m) if df_5m is not None else None}, 4h={len(df_4h) if df_4h is not None else None}")
                continue

            df_5m = strategy.apply_indicators(df_5m, timeframe='5m')
            df_4h = strategy.apply_indicators(df_4h, timeframe='4h')
            df_5m = df_5m.dropna()
            df_4h = df_4h.dropna()

            # Check signals on latest candle
            idx = -1
            if strategy.check_signals(df_5m, df_4h, idx):
                price = df_5m.iloc[idx]['close']
                stop_loss_price = price * (1 - STOP_LOSS)
                take_profit_price = price * (1 + PROFIT_TARGET)
                amount = (POSITION_SIZE * LEVERAGE) / price

                # Check if balance is sufficient
                if balance < POSITION_SIZE:
                    logging.warning(f"Insufficient virtual balance: ${balance:.2f} < ${POSITION_SIZE:.2f}")
                    continue

                # Place trade
                order_info = place_trade(symbol, price, amount, stop_loss_price, take_profit_price)
                if order_info:
                    trades_today[symbol][current_day] += 1
                    open_positions[symbol] = {
                        'buy_order_id': order_info['buy_order_id'],
                        'stop_loss_order_id': order_info['stop_loss_order_id'],
                        'take_profit_order_id': order_info['take_profit_order_id'],
                        'entry_price': price,
                        'amount': amount
                    }
                    logging.info(f"New trade for {symbol} at {price}. Virtual balance: ${balance:.2f}")

            # Check stop-loss and take-profit for open positions
            if symbol in open_positions:
                if check_stop_loss(symbol, open_positions[symbol]['stop_loss_order_id']):
                    exit_price = df_5m.iloc[idx]['close']
                    multiplier = 1 + (exit_price - open_positions[symbol]['entry_price']) / open_positions[symbol]['entry_price'] * LEVERAGE - 0.002
                    balance *= multiplier
                    trade_log.append({
                        'symbol': symbol,
                        'strategy': strategy_name,
                        'timestamp': df_5m.iloc[idx]['timestamp'],
                        'entry_price': open_positions[symbol]['entry_price'],
                        'exit_price': exit_price,
                        'return': (multiplier - 1) * 100,
                        'balance': balance,
                        'stop_loss_hit': True,
                        'take_profit_hit': False,
                        'stoch_rsi': df_5m.iloc[idx]['stoch_rsi'],
                        'macd': df_5m.iloc[idx]['macd'],
                        'signal': df_5m.iloc[idx]['signal'],
                        'atr': df_5m.iloc[idx]['atr']
                    })
                    logging.info(f"Stop-loss hit for {symbol} at {exit_price}. Virtual balance: ${balance:.2f}")
                    del open_positions[symbol]
                elif check_take_profit(symbol, open_positions[symbol]['take_profit_order_id']):
                    exit_price = df_5m.iloc[idx]['close']
                    multiplier = 1 + (exit_price - open_positions[symbol]['entry_price']) / open_positions[symbol]['entry_price'] * LEVERAGE - 0.002
                    balance *= multiplier
                    trade_log.append({
                        'symbol': symbol,
                        'strategy': strategy_name,
                        'timestamp': df_5m.iloc[idx]['timestamp'],
                        'entry_price': open_positions[symbol]['entry_price'],
                        'exit_price': exit_price,
                        'return': (multiplier - 1) * 100,
                        'balance': balance,
                        'stop_loss_hit': False,
                        'take_profit_hit': True,
                        'stoch_rsi': df_5m.iloc[idx]['stoch_rsi'],
                        'macd': df_5m.iloc[idx]['macd'],
                        'signal': df_5m.iloc[idx]['signal'],
                        'atr': df_5m.iloc[idx]['atr']
                    })
                    logging.info(f"Take-profit hit for {symbol} at {exit_price}. Virtual balance: ${balance:.2f}")
                    del open_positions[symbol]

        # Save trade log periodically
        pd.DataFrame(trade_log).to_csv(f'trade_log_{strategy_name}_live.csv', index=False)
        logging.info(f"Trade log saved to trade_log_{strategy_name}_live.csv")
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    live_trade()