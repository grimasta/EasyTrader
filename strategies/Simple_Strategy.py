import requests
import os
import pandas as pd
from datetime import datetime


ROOT_DIR = "../results/"

# Fetch OHLCV data from Binance API
def get_ohlcv_data(pair="DOTUSDT", interval="1h", limit=500):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": pair, "interval": interval, "limit": limit}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        ohlcv_data = []
        for entry in data:
            timestamp = entry[0]
            open_price = float(entry[1])
            high = float(entry[2])
            low = float(entry[3])
            close = float(entry[4])
            date_time = datetime.fromtimestamp(timestamp / 1000)
            ohlcv_data.append([date_time.strftime('%Y-%m-%d %H:%M:%S'), open_price, high, low, close])
        return ohlcv_data
    else:
        print("Failed to retrieve data:", response.status_code, response.text)
        return None


# Calculate Heikin-Ashi values
def calculate_heikin_ashi(data):
    df = pd.DataFrame(data, columns=["Date Time", "Open", "High", "Low", "Close"])

    # Create new Heikin-Ashi columns
    df["HA_Close"] = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4

    ha_open = [df["Open"].iloc[0]]  # The first HA Open is the same as the first Open
    for i in range(1, len(df)):
        ha_open.append((ha_open[-1] + df["HA_Close"].iloc[i - 1]) / 2)
    df["HA_Open"] = ha_open

    df["HA_High"] = df[["High", "HA_Open", "HA_Close"]].max(axis=1)
    df["HA_Low"] = df[["Low", "HA_Open", "HA_Close"]].min(axis=1)

    return df


# Calculate EMA10
def calculate_ema10(data, period=10):
    df = pd.DataFrame(data)
    df["EMA_10"] = df["HA_Close"].ewm(span=period, adjust=True).mean().round(3)
    return df

# Calculate EMA50
def calculate_ema50(data, period=50):
    df = pd.DataFrame(data)
    df["EMA_50"] = df["HA_Close"].ewm(span=period, adjust=True).mean().round(3)
    return df



# Calculate ATR using RMA
def calculate_atr_rma(data, period=14):
    df = pd.DataFrame(data, columns=["Date Time", "HA_Open", "HA_High", "HA_Low", "HA_Close"])
    df["Previous HA_Close"] = df["HA_Close"].shift(1)

    # Calculate True Range (TR)
    df["TR"] = df[["HA_High", "HA_Low", "Previous HA_Close"]].apply(
        lambda row: max(row["HA_High"] - row["HA_Low"],
                        abs(row["HA_High"] - row["Previous HA_Close"]),
                        abs(row["HA_Low"] - row["Previous HA_Close"])),
        axis=1,
    )

    # Calculate RMA for ATR
    atr_values = [0.0] * len(df)
    atr_values[period - 1] = df["TR"].iloc[:period].mean()
    for i in range(period, len(df)):
        atr_values[i] = (atr_values[i - 1] * (period - 1) + df["TR"].iloc[i]) / period
    df["ATR"] = atr_values
    df["ATR"] = df["ATR"].round(3)

    return df


# Save DataFrame to CSV
def save_to_csv(data, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    data.to_csv(file_path, index=False)


# Main Script: Combine HA, EMA, ATR and Conditions into one CSV
# PAIR = ["DOTUSDT", "DOGEUSDT", "ETHUSDT", "SOLUSDT"]
current_funds = 1000
for PAIR in ["DOTUSDT", "DOGEUSDT", "ETHUSDT", "SOLUSDT", "BTCUSDT", "AAVEUSDT", "POLUSDT", "RNDRUSDT", "EGLDUSDT", "VANRY", "KSMUSDT"]:
    interval = "2h"
    ohlcv_data = get_ohlcv_data(pair=PAIR, interval=interval)

    if ohlcv_data:
        # Step 1: Calculate Heikin-Ashi values
        ha_df = calculate_heikin_ashi(ohlcv_data)

        # Step 2: Calculate EMA and ATR using Heikin-Ashi values
        ema_df10 = calculate_ema10(ha_df)
        ema_df50 = calculate_ema50(ha_df)
        atr_df = calculate_atr_rma(ha_df)

        # Merge EMA and ATR into the Heikin-Ashi DataFrame
        ha_df["EMA_10"] = ema_df10["EMA_10"]
        ha_df["EMA_50"] = ema_df50["EMA_50"]
        ha_df["ATR"] = atr_df["ATR"]

        # Step 3: Add Conditions for Low and High prices
        ha_df["Condition_Long"] = ha_df.apply(
            lambda row: 1 if row["HA_Low"] == row["HA_Open"] and row["HA_Low"] > row["EMA_10"] else 0,
            axis=1
        )
        ha_df["Condition_Short"] = ha_df.apply(
            lambda row: 1 if row["HA_High"] == row["HA_Open"] and row["HA_High"] < row["EMA_10"] else 0,
            axis=1
        )

        # Step 4: Add Conditions for further filtering using the EMA50
        ha_df["Condition_Long_EMA50_Filtered"] = ha_df.apply(
            lambda row: 1 if row["Condition_Long"] == 1 and row["HA_Low"] > row["EMA_50"] else 0,
            axis=1
        )
        ha_df["Condition_Short_EMA50_Filtered"] = ha_df.apply(
            lambda row: 1 if row["Condition_Short"] == 1 and row["HA_High"] < row["EMA_50"] else 0,
            axis=1
        )

        # Step 5: Add "EnterPoint" column with the next candle's original Open price
        original_df = pd.DataFrame(ohlcv_data, columns=["Date Time", "Open", "High", "Low", "Close"])
        ha_df["Next_Open"] = original_df["Open"].shift(-1)  # Shift Open prices up by one row

        ha_df["EnterPoint"] = ha_df.apply(
            lambda row: row["Next_Open"] if row["Condition_Long_EMA50_Filtered"] == 1
                                            or row["Condition_Short_EMA50_Filtered"] == 1 else None,
            axis=1
        )

        ha_df["HighestPoint"] = ha_df["EnterPoint"] + 2*ha_df["ATR"]
        ha_df["LowestPoint"] = ha_df["EnterPoint"] - 2*ha_df["ATR"]


        # Create the new column to see if I go LONG or SHORT
        ha_df["Position"] = ha_df.apply(lambda row: "LONG" if row["Condition_Long_EMA50_Filtered"] == 1
        else "SHORT" if row["Condition_Short_EMA50_Filtered"] == 1
        else "NULL", axis=1)

        # Initialize variables
        in_trade = False  # Track if in a trade
        trade_log = []  # Log completed trades
        active_trade = None  # Details of the current trade

        # Iterate through the DataFrame row by row
        for index, row in ha_df.iterrows():
            if not in_trade and row["Position"]!="NULL":  # Entry condition
                print("here")
                in_trade = True
                if row["Position"] == "LONG":
                    active_trade = {
                        "Trade Type": row["Position"],
                        "Entry Index": index,
                        "Entry Point": row["EnterPoint"],
                        "TP": row["HighestPoint"],
                        "SL": row["LowestPoint"],
                    }
                elif row["Position"] == "SHORT":
                    active_trade = {
                        "Trade Type": row["Position"],
                        "Entry Index": index,
                        "Entry Point": row["EnterPoint"],
                        "TP": row["LowestPoint"],
                        "SL": row["HighestPoint"],
                    }
                print(f"Entered {row['Position']} trade at index {index}")
                print(f"Active Trade Initialized: {active_trade}")

            elif in_trade and active_trade is not None:  # Check for exit conditions
                if active_trade["Trade Type"] == "LONG":
                    if row["High"] >= active_trade["TP"]:  # Take Profit hit
                        trade_log.append({
                            "Trade Type": "LONG",
                            "Entry Index": active_trade["Entry Index"],
                            "Entry Value": active_trade["Entry Point"],
                            "Exit Index": index,
                            "Exit Reason": "TP",
                            "Exit Price": active_trade["TP"],
                            "Gain Per Unit": (active_trade["TP"] - active_trade["Entry Point"])/active_trade["Entry Point"]
                        })
                        current_funds += current_funds * (active_trade["TP"] - active_trade["Entry Point"])/active_trade["Entry Point"]
                        print(f"Exited LONG trade at TP ({active_trade['TP']}) at index {index}")
                        in_trade = False
                        active_trade = None
                    elif row["Low"] <= active_trade["SL"]:  # Stop Loss hit
                        trade_log.append({
                            "Trade Type": "LONG",
                            "Entry Index": active_trade["Entry Index"],
                            "Entry Value": active_trade["Entry Point"],
                            "Exit Index": index,
                            "Exit Reason": "SL",
                            "Exit Price": active_trade["SL"],
                            "Gain Per Unit": (active_trade["SL"] - active_trade["Entry Point"])/active_trade["Entry Point"]
                        })
                        current_funds += current_funds * (active_trade["TP"] - active_trade["Entry Point"])/active_trade["Entry Point"]
                        print(f"Exited LONG trade at SL ({active_trade['SL']}) at index {index}")
                        in_trade = False
                        active_trade = None

                elif active_trade["Trade Type"] == "SHORT":
                    if row["Low"] <= active_trade["TP"]:  # Take Profit hit
                        trade_log.append({
                            "Trade Type": "SHORT",
                            "Entry Index": active_trade["Entry Index"],
                            "Entry Value": active_trade["Entry Point"],
                            "Exit Index": index,
                            "Exit Reason": "TP",
                            "Exit Price": active_trade["TP"],
                            "Gain Per Unit": (active_trade["Entry Point"] - active_trade["TP"])/active_trade["Entry Point"]
                        })
                        current_funds += current_funds * (active_trade["TP"] - active_trade["Entry Point"])/active_trade["Entry Point"]
                        print(f"Exited SHORT trade at TP ({active_trade['TP']}) at index {index}")
                        in_trade = False
                        active_trade = None
                    elif row["High"] >= active_trade["SL"]:  # Stop Loss hit
                        trade_log.append({
                            "Trade Type": "SHORT",
                            "Entry Index": active_trade["Entry Index"],
                            "Entry Value": active_trade["Entry Point"],
                            "Exit Index": index,
                            "Exit Reason": "SL",
                            "Exit Price": active_trade["SL"],
                            "Gain Per Unit": (active_trade["Entry Point"] - active_trade["SL"])/active_trade["Entry Point"]
                        })
                        current_funds += current_funds * (active_trade["TP"] - active_trade["Entry Point"])/active_trade["Entry Point"]
                        print(f"Exited SHORT trade at SL ({active_trade['SL']}) at index {index}")
                        in_trade = False
                        active_trade = None

        # Convert trade log to DataFrame and save to CSV
        trade_log_df = pd.DataFrame(trade_log)

        # Save to CSV
        output_path = ROOT_DIR + PAIR + "/" + PAIR + "_trade_log.csv"
        if not trade_log_df.empty:
            save_to_csv(trade_log_df, output_path)
            print(f"Trade log saved to {output_path}")
        else:
            print("No trades were logged.")


            # Specify output file path

        file_path1 = ROOT_DIR + PAIR + "/" + PAIR + "_heikin_ashi_conditions.csv"
        file_path2 = ROOT_DIR + PAIR + "/" + PAIR + "_trades.csv"

        # Save combined data to CSV
        save_to_csv(ha_df, file_path1)
        save_to_csv(trade_log_df, file_path2)
        print(f"Heikin-Ashi data with EMA-10, ATR, and conditions saved to {file_path1}")
    else:
        print("Could not retrieve data to process.")


print(current_funds)

















