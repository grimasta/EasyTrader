# from venues.structured.websocket.bitget_live_klines import init_global_manager, get_5m_from, get_4h_from, BitgetEndpoints
#
# # from bitget_live_klines import init_global_manager, get_5m_from, get_4h_from, BitgetEndpoints
#
# # Futures (mix v2)
# endpoints = BitgetEndpoints(
#     timeframe_to_granularity={"5m": "5m", "4h": "4H"},
#     product_type_value="USDT-FUTURES",
#     ws_inst_type="USDT-FUTURES",
#     rest_base="https://api.bitget.com",
#     rest_path="/api/v2/mix/market/candles",
#     symbol_param="symbol",
#     granularity_param="granularity",
#     product_type_param="productType",
#     ws_url="wss://ws.bitget.com/mix/v1/stream",
# )
#
# init_global_manager(
#     symbols=["BTCUSDT", "ETHUSDT"],
#     timeframes_windows={"5m": 100, "4h": 200},
#     endpoints=endpoints,
# )
#
# # Your existing calls still work (start_date is ignored now)
# df_5m = get_5m_from("BTCUSDT")
# df_4h = get_4h_from("BTCUSDT")
#
# print(df_5m.head(10))