# # This is a sample Python script.
#
# # Press Shift+F10 to execute it or replace it with your code.
# # Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
# import pandas as pd
# import requests
# import json
#
# from py._path.svnwc import cache
#
# from scratch_pad_bollinger import plot_with_bb
#
#
# def do_get_on_url(the_url, the_symbol=None):
#     try:
#         response = requests.get(the_url)
#         if response.status_code == 200:
#             response = response.text
#         else:
#             print(f"Error: {response.status_code}")
#             print(f"code: {response.content}")
#     except:
#         print("an exception occurred")
#         exit()
#     return response
#
#
# def fetch_candlesticks(symbol, timeframe, number):
#     import time
#     the_real_url = "https://api.crypto.com/exchange/v1/"
#     the_get_candlestick_endpoint = "public/get-candlestick?instrument_name="
#     the_get_candlestick_endpoint_period_string = "&timeframe="
#
#     periods = [300] * (number//300)
#     if number%300 > 0:
#         periods.append(number%300)
#     end_time = 0
#     responses = {"result":{"data":[]}}
#     for period in periods:
#         the_get_url = the_real_url + the_get_candlestick_endpoint + symbol
#         the_get_url += f"&timeframe={timeframe}&count={period}"
#         if end_time > 0:
#             the_get_url += f"&end_ts={end_time}"
#         time.sleep(0.5)
#         response = json.loads(do_get_on_url(the_get_url))
#         [responses["result"]["data"].append(i) for i in response["result"]["data"]]
#         end_time = min([i['t'] for i in response["result"]["data"]])
#     responses["result"]["data"] = sorted(responses["result"]["data"], key=lambda x:x['t'])
#     return convert_candlesticks_to_numpy(responses)
#
# the_real_url = "https://api.crypto.com/exchange/v1/"
# the_get_candlestick_endpoint = "public/get-candlestick?instrument_name="
# the_get_candlestick_endpoint_period_string = "&timeframe="
# the_api_key_no_trading = "***REMOVED***"
# the_sandbox_url = "https://uat-api.3ona.co/exchange/v1/"
# the_get_book_endpoint = "public/get-book?instrument_name="
# the_get_instruments_endpoint = "public/get-instruments"
# the_get_candlestick_timeframes = {"1m" : '1m',
#                                  "5m" : '5m',
#                                  "15m" : '15m',
#                                  "30m" : '30m',
#                                  "1h" : '1h',
#                                  "2h" : '2h',
#                                  "4h" : '4h',
#                                  "12h" : '12h',
#                                  "1D" : '1D',
#                                  "7D" : '7D',
#                                  "14D" : '14D',
#                                  "1M" : '1M'}
# the_market_method = "market"
# the_user_method = "user"
#
# def convert_numpy_to_pd(numpy_candlesticks):
#     df = pd.DataFrame({
#         "Date": numpy_candlesticks[0, :],
#         "Open": numpy_candlesticks[3, :],
#         "High": numpy_candlesticks[1, :],
#         "Low": numpy_candlesticks[2, :],
#         "Close": numpy_candlesticks[4, :],
#         "Volume": numpy_candlesticks[5, :]
#     })
#     df['Date'] = pd.to_datetime(df['Date'], unit='ms')
#     print(df.head())
#     return df
#
# import numpy as np
# def convert_candlesticks_to_numpy(json_candlesticks):
#     highs = []
#     lows = []
#     opens = []
#     closes = []
#     volumes = []
#     dates = []
#     for candlestick_i in range(len(json_candlesticks["result"]["data"])):
#         candlestick = json_candlesticks["result"]["data"][candlestick_i]
#         t = float(candlestick['t'])
#         h = float(candlestick['h'])
#         l = float(candlestick['l'])
#         o = float(candlestick['o'])
#         c = float(candlestick['c'])
#         v = float(candlestick['v'])
#         if len(dates) == 0:
#             dates.append(float(candlestick['t']))
#             highs.append(float(candlestick['h']))
#             lows.append(float(candlestick['l']))
#             opens.append(float(candlestick['o']))
#             closes.append(float(candlestick['c']))
#             volumes.append(float(candlestick['v']))
#         else:
#             csp = {k:float(v) for  k,v in json_candlesticks["result"]["data"][candlestick_i-1].items()}
#             dates.append(t)
#             highs.append((h - csp['h'])/csp['h'])
#             lows.append((l - csp['l'])/csp['l'])
#             opens.append((o - csp['o'])/csp['o'])
#             closes.append((c - csp['c'])/csp['c'])
#             volumes.append((v - csp['v'])/csp['v'])
#     np_dates = np.array(dates[1::])
#     np_highs = np.array(highs[1::])
#     np_lows = np.array(lows[1::])
#     np_opens = np.array(opens[1::])
#     np_closes = np.array(closes[1::])
#     np_volumes = np.array(volumes[1::])
#     np_all = np.vstack((np_dates, np_highs, np_lows, np_opens, np_closes, np_volumes))
#     # np_all = np.vstack(np_all, np_opens)
#     # np_all = np.vstack(np_all, np_closes)
#     # np_all = np.vstack(np_all, np_volumes)
#     return np_all
#
#
# def exponential_moving_average(data, alpha, window_size):
#     # Calculate weights using exponential decay formula
#     weights = np.exp(np.linspace(-1.0, 0.0, window_size) / alpha)
#
#     # Normalize weights to sum to 1
#     weights /= weights.sum()
#
#     # Use convolution to calculate EMA
#     ema = np.convolve(data, weights, mode='full')[:len(data)]
#
#     return ema
#
#
# import numpy as np
# # import matplotlib.pyplot as plt
# # import ruptures as rpt
#
# def change_point_detection(data_series):
#     # Generate a synthetic time series with two segments
#     np.random.seed(42)
#     data = np.concatenate([np.random.normal(0, 1, 50), np.random.normal(4, 1, 50)])
#     data = data_series
#
#     # Specify the change point detection algorithm (Pelt method in this case)
#     model = rpt.Pelt(model="rbf").fit(data)
#     result = model.predict(pen=10)  # Adjust the penalty parameter as needed
#
#     # Plot the original time series and highlight change points
#     plt.plot(data, label="Original Time Series")
#     plt.title("Change Point Detection with Ruptures")
#     for change_point in result:
#         plt.axvline(x=change_point, color="red", linestyle="--", linewidth=1, label="Change Point")
#     plt.legend()
#     plt.show()
#
#
# # Generate a synthetic time series
# np.random.seed(42)
# time = np.arange('2023-01-01', '2023-02-01', dtype='datetime64[D]')
# data = np.cumsum(np.random.randn(len(time)))
#
# # Function to calculate rolling slopes
# def calculate_rolling_slopes(data, window_sizes):
#     slopes = {}
#
#     for window_size in window_sizes:
#         # Calculate the rolling slope using np.polyfit
#         slope = np.convolve(data, np.ones(window_size)/window_size, mode='valid', )  # Rolling mean
#         slope = np.gradient(slope, axis=0)
#         slopes[f'Window_{window_size}'] = np.concatenate([np.full(window_size-1, np.nan), slope])
#
#     return slopes
#
#
# # Press the green button in the gutter to run the script.
# if __name__ == '__main__':
#
#     the_complete_url = the_sandbox_url + the_get_book_endpoint + "BTCUSD-PERP&depth=100"
#     # response = fetch_symbol_history(the_complete_url)
#     # print(response)
#     the_complete_candlestick = the_real_url + the_get_candlestick_endpoint
#     response = do_get_on_url(the_sandbox_url + the_get_instruments_endpoint)
#     json_response = json.loads(response)
#     # for instrument_details in json_response["result"]["data"]:
#     #     if 'ADA_USDT' in instrument_details["symbol"]:
#     #         print(instrument_details["symbol"])
#     #         candlesticks = do_get_on_url(the_complete_candlestick + "ADA_USDT" +
#     #                                      the_get_candlestick_endpoint_period_string +
#     #                                      the_get_candlestick_timeframes["4h"] + "&count=" + "1000")
#     #         json_candlesticks = json.loads(candlesticks)
#     #         numpy_candlesticks = convert_candlesticks_to_numpy(json_candlesticks)
#     #         closing_ema_21 = exponential_moving_average(numpy_candlesticks[3,:], 0.2, 21)
#     #         closing_ema_89 = exponential_moving_average(numpy_candlesticks[3,:], 0.2, 89)
#     #         closing_ema_144 = exponential_moving_average(numpy_candlesticks[3,:], 0.2, 144)
#     #         closing_ema_233 = exponential_moving_average(numpy_candlesticks[3,:], 0.2, 233)
#     #         import matplotlib.pyplot as plt
#     #         plt.plot(numpy_candlesticks[3,:], label='Original Data', color='black')
#     #         for i in [21, 89, 200]:
#     #             closing_ema = exponential_moving_average(numpy_candlesticks[3,:], 0.2, i)[i-1::]
#     #             plt.plot(np.arange(i-1, len(numpy_candlesticks[3,:])), closing_ema, label=f'MA ({i})')
#     #         plt.xlabel('Data Point')
#     #         plt.ylabel('Value')
#     #         plt.title('Moving Averages of Different Lengths')
#     #         plt.legend()
#     #         plt.show()
#     #
#     #         break
#
#     sui_usdt = fetch_candlesticks("SUI_USDT", '15m', 400)
#     from sklearn.svm import SVC
#     from sklearn.linear_model import LogisticRegression
#     from sklearn.neural_network import MLPClassifier
#     from keras.models import Sequential
#     from keras.layers import SimpleRNN, Dense
#     rfr = MLPClassifier(hidden_layer_sizes=(21, 34, 55, 89, 144))
#     # from sklearn.utils.random import sample_without_replacement
#     sui_usdt_train, sui_usdt_test = sui_usdt[[1,2,3,5], 0:349], sui_usdt[[1,2,3,5], 351:399]
#     sui_usdt_train = np.transpose(sui_usdt_train)
#     sui_usdt_test = np.transpose(sui_usdt_test)
#     target = [1  if i >=0 else 0 for i in sui_usdt[4, 1:350]]
#
#     print(target)
#     target_test = [1  if i >=0 else 0 for i in sui_usdt[4, 351::]]
#     #===================================================================================================================
#     #===================================================================================================================
#     #===================================================================================================================
#     import numpy as np
#     from sklearn.model_selection import train_test_split
#     from sklearn.preprocessing import StandardScaler
#     from sklearn.datasets import make_classification
#     from sklearn.metrics import accuracy_score
#     from sklearn.pipeline import make_pipeline
#     from sklearn.base import BaseEstimator, ClassifierMixin
#
#     from keras.models import Sequential
#     from keras.layers import SimpleRNN, Dense
#
#     # Generate some example data for binary classification
#     # X, y = make_classification(n_samples=1000, n_features=10, n_informative=5, n_classes=2, random_state=42)
#     X_train = sui_usdt_train
#     y_train = target
#     X_test = sui_usdt_test
#     y_test = target_test
#     # Split the data into training and testing sets
#     # X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
#
#     # Standardize the data
#     scaler = StandardScaler()
#     X_train_scaled = scaler.fit_transform(X_train)
#     X_test_scaled = scaler.transform(X_test)
#
#     # Define an RNN model for binary classification using Keras
#     model = Sequential()
#     model.add(SimpleRNN(50, input_shape=(X_train.shape[1], 1)))
#     model.add(Dense(1, activation='sigmoid'))  # Output layer with sigmoid activation for binary classification
#
#     # Compile the model
#     model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
#
#     # Reshape input data to fit the RNN input shape
#     X_train_reshaped = X_train_scaled.reshape((X_train_scaled.shape[0], X_train_scaled.shape[1], 1))
#     X_test_reshaped = X_test_scaled.reshape((X_test_scaled.shape[0], X_test_scaled.shape[1], 1))
#
#     # Fit the model
#     model.fit(X_train_reshaped, y_train, epochs=10, batch_size=32, validation_split=0.2)
#
#     # Make predictions on the test set
#     y_pred_prob = model.predict(X_test_reshaped)
#     y_pred = (y_pred_prob > 0.5).astype(int)  # Convert probabilities to binary predictions
#
#     # Evaluate the model
#     accuracy = accuracy_score(y_test, y_pred)
#     print(f'Accuracy on Test Set: {accuracy}')
#
# #===================================================================================================================
#     #===================================================================================================================
#     #===================================================================================================================
#     rfr.fit(sui_usdt_train, target)
#     target_predicted = rfr.predict(sui_usdt_test)
#     # print(target_predicted, target_test)
#     from sklearn.metrics import r2_score, mean_squared_error, confusion_matrix
#     # print(r2_score(target_test, target_predicted))
#
#     # print(mean_squared_error(target_test, target_predicted))
#     for i in range(len(target_test)):
#         print(target_test[i], target_predicted[i])
#     cm = confusion_matrix(target_test, target_predicted)
#     print(cm)
#     exit()
#     # ada_usdt
#     numpy_candlesticks = sui_usdt
#     pd_candlesticks = convert_numpy_to_pd(numpy_candlesticks)
#     candle_data = pd_candlesticks
#     data = candle_data
#     plot_with_bb(data)
#     change_point_detection(numpy_candlesticks[3,:])
#     closing_ema_21 = exponential_moving_average(numpy_candlesticks[3,:], 0.2, 21)
#     closing_ema_89 = exponential_moving_average(numpy_candlesticks[3,:], 0.2, 89)
#     closing_ema_144 = exponential_moving_average(numpy_candlesticks[3,:], 0.2, 144)
#     closing_ema_233 = exponential_moving_average(numpy_candlesticks[3,:], 0.2, 233)
#     import matplotlib.pyplot as plt
#     plt.plot(numpy_candlesticks[3,:], label='Original Data', color='black')
#     for i in [21, 89, 200]:
#         closing_ema = exponential_moving_average(numpy_candlesticks[3,:], 0.2, i)[i-1::]
#         plt.plot(np.arange(i-1, len(numpy_candlesticks[3,:])), closing_ema, label=f'MA ({i})')
#     plt.xlabel('Data Point')
#     plt.ylabel('Value')
#     plt.title('Moving Averages of Different Lengths')
#     plt.legend()
#     plt.show()
#
#
#     # Specify the window sizes for rolling slopes
#     window_sizes = [610]
#
#     # Create a dictionary with rolling slopes
#     rolling_slopes_dict = calculate_rolling_slopes(numpy_candlesticks[3,:], window_sizes)
#     data = numpy_candlesticks[3, :]
#
#     # Plot the original time series
#     fig, ax1 = plt.subplots(figsize=(10, 6))
#     color = 'tab:red'
#     ax1.set_xlabel('Time')
#     ax1.set_ylabel('Value', color=color)
#     ax1.plot(data, color=color, label='Original Time Series')
#     ax1.tick_params(axis='y', labelcolor=color)
#
#     # Create a twin Axes sharing the xaxis
#     ax2 = ax1.twinx()
#     color = 'tab:blue'
#     ax2.set_ylabel('Slope', color=color)
#     for window_size in window_sizes:
#         ax2.plot(rolling_slopes_dict[f'Window_{window_size}'], label=f'Rolling Slope ({window_size}-day window)', linestyle='--')
#     ax2.tick_params(axis='y', labelcolor=color)
#
#     # Title and show the plot
#     plt.title('Original Time Series and Rolling Slopes')
#     plt.show()
#
#
#
#
# # print(response)
# # See PyCharm help at https://www.jetbrains.com/help/pycharm/
