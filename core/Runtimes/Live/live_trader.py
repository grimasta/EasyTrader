# import ccxt
import pandas as pd
from datetime import datetime, timedelta
import time
import logging
import json
from venues.bitget_v2.api_client.v2_calc_correct_pos import compute_position_size
from venues.bitget_v2.api_client import open_order_summary_for
from venues.bitget_v2.api_client.v2_order_placement_with_local_timeout import place_limit_long
from venues.bitget_v2.api_client.v2_runtime_rebuild import rebuild_runtime_state
from venues.bitget_v2.api_client.v_2_candles import get_5m_from, get_4h_from
from venues.structured.proof_of_concept_for_order_placing import get_future_symbol_mark_price, \
    get_account_balance, get_min_symbol_quantity, place_market_long, get_entry_price, attach_tp_sl, get_sl_executed, \
    get_sl_executed_price, get_sl_profit, get_account_current, handle_sl_if_any
from strategies.strategies_live import STRATEGIES
from venues.bitget_v2.websocket.bitget_live_klines import init_global_manager, get_5m_from, get_4h_from, \
    BitgetEndpoints
from venues.bitget_v2.api_client import place_limit_long, \
    recover_open_positions_and_watch

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Trading parameters
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT',
           'XRPUSDT', 'BNBUSDT', 'TRXUSDT', 'ADAUSDT',
           'LINKUSDT',
           # 'HYPEUSDT',
           'DOTUSDT',
           # 'KSMUSDT',
           # 'HNTUSDT',
           # 'AAVEUSDT',
           # 'SUIUSDT',
           'AVAXUSDT',
           # 'HBARUSDT', 'SEIUSDT',
           'ICPUSDT',
           'LTCUSDT',
           # 'TAOUSDT',
           # 'INJUSDT', 'TIAUSDT', 'WLDUSDT',
           'NEARUSDT'
           ]
LEVERAGE = 10
POSITION_SIZE = 0.01
PROFIT_TARGET = 0.04  # 1.2% gross
STOP_LOSS = 0.02  # 2.5% loss
MAX_TRADES_PER_DAY = 10 # Increased
STRATEGY_NAME = 'best_momentum'
LOSS_LIMIT = 0.4  # Stop trading if 20% of initial balance lost


def clean_open_positions(open_positions, df_symbols_open):
    to_remove = []
    for symbol in open_positions:
        if symbol not in df_symbols_open:
            to_remove.append(symbol)
    for symbol in to_remove:
        del open_positions[symbol]
    return open_positions

def live_trading(strategy_name=STRATEGY_NAME):


    while True:
        # from bitget_live_klines import init_global_manager, get_5m_from, get_4h_from, BitgetEndpoints

        # Futures (mix v2)
        endpoints = BitgetEndpoints(
            timeframe_to_granularity={"5m": "5m", "4h": "4H"},
            product_type_value="USDT-FUTURES",
            ws_inst_type="USDT-FUTURES",
            rest_base="https://api.bitget.com",
            rest_path="/api/v2/mix/market/candles",
            symbol_param="symbol",
            granularity_param="granularity",
            product_type_param="productType",
            ws_url="wss://ws.bitget.com/mix/v1/stream",
        )

        init_global_manager(
            symbols=SYMBOLS,
            timeframes_windows={"5m": 100, "4h": 200},
            endpoints=endpoints,
        )
        recover_open_positions_and_watch(SYMBOLS, watch_timeframe="5m")
        try:
            strategy = STRATEGIES.get(strategy_name)
            if not strategy:
                raise ValueError(f"Unknown strategy: {strategy_name}")

            initial_balance = get_account_current()
            print(F'==============================================================')
            print(F'Current Account balance (including UPnL): {initial_balance:<20f}')
            print(F'==============================================================')
            # if initial_balance < POSITION_SIZE:
            #     logging.error(f"Insufficient balance: ${initial_balance} < ${POSITION_SIZE}")
            #     return


            trades_today = {symbol: {} for symbol in SYMBOLS}
            trade_log = []
            logging.info(f"Starting live trading with {strategy_name} strategy. Initial balance: ${initial_balance:.2f}")
            skip_day = {symbol: 0 for symbol in SYMBOLS}
            skip_trade = {symbol: 0 for symbol in SYMBOLS}
            open_positions = {}  # Track open trades: {symbol: {'buy_order_id': id, 'stop_loss_order_id': id, 'entry_price': price}}
            open_positions = {}
            symbol_orders = open_order_summary_for(SYMBOLS)
            # ================= rebuild state =====================================
            open_positions, trades_today, skip_day = rebuild_runtime_state(SYMBOLS)
            # ================= rebuild state =====================================
            # for entry in symbol_orders:
            #     position = copy.deepcopy(entry)
            #     del position['symbol']
            #     open_positions[entry["symbol"]] = position
            while True:
                # df_orders = positions_df()
                # df_symbols_open = df_orders['symbol'].tolist()
                # open_positions = clean_open_positions(open_positions, df_symbols_open)
                loss_log=[]
                trade_log=[]
                current_time = datetime.now()
                # with open("open_positions_best_momentum.json", 'r') as open_position_reader:
                #     open_position_string = ""
                #     for line in open_position_reader:
                #         open_position_string += line
                #     if len(open_position_string) > 0:
                #         open_positions = json.loads(open_position_string)
                #     else:
                #         open_positions = {}


                for symbol in SYMBOLS:

                    current_day = current_time.date()
                    if current_day not in trades_today[symbol]:
                        trades_today[symbol][current_day] = 0
                        if skip_day[symbol] > 0:
                            skip_day[symbol] -= 1
                    if skip_day[symbol] > 0:
                        continue

                    if trades_today[symbol][current_day] >= MAX_TRADES_PER_DAY:
                        continue
                    # start_date =
                    # end_date = str(datetime.now())
                    end_date = datetime.now().strftime('%Y-%m-%d')
                    start_date = (datetime.now() - timedelta(hours=400)).strftime('%Y-%m-%d-%H-%M')  # 100 * 4h = 400h
                    # exit()
                    # Fetch recent data
                    # df_5m = fetch_data(symbol, timeframe='5m', limit=100, start_date=start_date, end_date=end_date)
                    # df_4h = fetch_data(symbol, timeframe='4h', limit=100, start_date=start_date, end_date=end_date)
                    # df_5m = get_5m_from(symbol, start_date)
                    # df_4h = get_4h_from(symbol, start_date)

                    df_5m = get_5m_from(symbol)
                    df_4h = get_4h_from(symbol)
                    if df_5m is None or df_4h is None or len(df_5m) < 20 or len(df_4h) < 100:
                        logging.warning(f"Insufficient data for {symbol}")
                        continue

                    df_5m = strategy.apply_indicators(df_5m, timeframe='5m')
                    df_4h = strategy.apply_indicators(df_4h, timeframe='4h')
                    df_5m = df_5m.dropna()
                    df_4h = df_4h.dropna()

                    idx = -1
                    signal, atr = strategy.check_signals(df_5m, df_4h, len(df_5m)-1)
                    # Check balance
                    current_balance = get_account_balance("USDT")
                    if signal and symbol not in open_positions:
                        print("found_trade", symbol)
                        current_price = get_future_symbol_mark_price(symbol)

                        if current_balance < initial_balance * (1 - LOSS_LIMIT):
                            logging.error(f"Loss limit reached: ${current_balance:.2f}. Stopping trading.")
                            break

                        # Place order
                        position_size = compute_position_size(symbol, current_balance, LEVERAGE, current_price, POSITION_SIZE)

                        print(position_size)
                        actual_cost = position_size * current_price / LEVERAGE
                        print(f'actual cost = {actual_cost}')
                        if actual_cost > 5 * POSITION_SIZE * initial_balance:
                            print("cost of entry into trade is too expensive, skipping.")
                            continue
                        # place a 5-minute limit @ 0.221
                        out = place_limit_long("XRPUSDT", size="50", price="0.221", duration="5m", tif="gtc",
                                               client_oid="my-xrp-0-221", auto_cancel=False)
                        print(out)

                        # in your main event loop, tick this to cancel expired ones:
                        # cancel_if_expired("XRPUSDT", out["orderId"], out["clientOid"], out["expires_at_ms"])
                        # order_info = place_market_long(symbol, position_size)
                        entry_price = get_entry_price(symbol)
                        amount = position_size * entry_price / LEVERAGE
                        time.sleep(0.05)
                        tp_sl_info = attach_tp_sl(symbol, entry_price)

                        # order_info = place_order(symbol, 'buy', amount, current_price, stop_loss_price, take_profit_price)
                        # order_info = place_order(symbol, POSITION_SIZE * current_balance, amount, current_price, stop_loss_price, take_profit_price)
                        # print(current_price)
                        # print(df_5m.iloc[-1])
                        if order_info:
                            trades_today[symbol][current_day] += 1
                            open_positions[symbol] = {
                                'buy_order_id': order_info['data']['orderId'],
                                'stop_loss_order_id': tp_sl_info['tpClientOid'],
                                'take_profit_order_id': tp_sl_info['slClientOid'],
                                'entry_price': current_price,
                                'amount': amount
                            }
                            with open("open_positions_best_momentum.json", 'w') as open_positions_writer:
                                print(json.dumps(open_positions), file=open_positions_writer)
                            logging.info(f"New trade for {symbol} at {current_price}. Balance: ${current_balance:.2f}")
                            trade_log=[{
                                'symbol': symbol,
                                'strategy': strategy_name,
                                'timestamp': current_time,
                                'entry_price': current_price,
                                'amount': amount,
                                'balance': current_balance
                            }]
                            pd.DataFrame(trade_log).to_csv(f'trade_log_{strategy_name}.csv', mode='a', index=False, header=False)
                            # logging.info(f"New trade opened for {symbol}. Balance: ${current_balance:.2f}")
                        # Check stop-loss for open positions
                    handle_sl_if_any(symbol, open_positions, current_balance, df_5m, idx, strategy_name, skip_day)
                    # if symbol in open_positions:
                    #     sl_oid = open_positions[symbol]['stop_loss_order_id']
                    #     print(f"SL status for {symbol}:", get_sl_executed(symbol, sl_oid))
                    #     if get_sl_executed(symbol, sl_oid):
                    #         skip_day[symbol] = 1
                    #         skip_trade[symbol] = 0
                    #         exit_price = get_sl_executed_price(symbol, sl_oid)  # Approximate exit price
                    #         # effective_position = open_positions[symbol]['amount'] * open_positions[symbol]['entry_price']
                    #         PnL = get_sl_profit(symbol, sl_oid)
                    #         pos_return = PnL/current_balance
                    #         current_balance += PnL
                    #         loss_log=[{
                    #             'symbol': symbol,
                    #             'strategy': strategy_name,
                    #             'timestamp': df_5m.iloc[idx]['timestamp'],
                    #             'entry_price': open_positions[symbol]['entry_price'],
                    #             'exit_price': exit_price,
                    #             'return': pos_return,
                    #             'balance': current_balance,
                    #             'stop_loss_hit': True,
                    #         }]
                    #         pd.DataFrame(loss_log).to_csv(f'loss_log_{strategy_name}.csv', mode='a', index=False, header=False)
                    #         logging.info(f"Stop-loss hit for {symbol} at {exit_price}. Balance: ${current_balance:.2f}")
                    #         del open_positions[symbol]
                # Save trade log
                # pd.DataFrame(trade_log).to_csv(f'trade_log_{strategy_name}.csv', index=False)
                logging.info(f"Trade log updated: trade_log_{strategy_name}.csv")

                # Sleep to avoid overloading API
                time.sleep(2)  # Check every minute
        except Exception as e:
            time.sleep(10)
            print(f'an error occurred, described by {e}, probably some form of connectivity issue')
            print("waited 30 seconds and retrying")

if __name__ == "__main__":
    live_trading()