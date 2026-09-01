# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-
# """
# Backtest (data from local CSVs with 1m candles):
# - Universe: BTC, ETH, SOL, DOGE, XRP (map to your CSVs below)
# - Data columns: index, timestamp, open, high, low, close, volume
# - Period: 2023-08-01 to 2025-08-18 (inclusive)
# - Entry: 10:00 a.m. America/New_York (simultaneous across symbols)
# - Size: 1% of START-OF-DAY equity per asset, isolated, 10x leverage
# - TP: +0.5% (0.005) from entry; fill as soon as any 1m candle high ≥ TP
# - LIQ: -10% from entry (approx for 10x). If a minute’s low ≤ LIQ, liquidate (lose full margin).
#   If both TP and LIQ are hit in the same minute, LIQ takes precedence (conservative).
# - Exit: 11:00 a.m. (use the 10:59 candle’s close if no TP/LIQ hit)
# - No fees/slippage/funding.
#
# Outputs:
# - results_local_daily_equity.csv
# - results_local_trades.csv
# - results_local_summary.json
# - results_local_equity_curve.png
# """
#
# import os
# import math
# import json
# from datetime import datetime, timedelta, date
# from typing import Dict, List
#
# import pandas as pd
# import numpy as np
# import pytz
#
# # Force a non-GUI backend for Matplotlib (safe on servers/IDEs)
# os.environ["MPLBACKEND"] = "Agg"
# import matplotlib
# matplotlib.use("Agg", force=True)
# import matplotlib.pyplot as plt
#
# # --------- CONFIGURE THESE PATHS ---------
# # Map your 5 instruments to CSV file paths.
# # The 'symbol' key is just a label for reporting.
# FILE_MAP = {
#     "BTCUSDT": "BTCUSDT_1m_2023-08-01_2025-08-18.csv",
#     "ETHUSDT": "ETHUSDT_1m_2023-08-01_2025-08-18.csv",
#     "SOLUSDT": "SOLUSDT_1m_2023-08-01_2025-08-18.csv",
#     "DOGEUSDT": "DOGEUSDT_1m_2023-08-01_2025-08-18.csv",
#     "XRPUSDT": "XRPUSDT_1m_2023-08-01_2025-08-18.csv",
# }
# # -----------------------------------------
#
# NY_TZ = pytz.timezone("America/New_York")
# UTC = pytz.UTC
#
# START_DATE_LOCAL = "2023-08-01"
# END_DATE_LOCAL   = "2025-08-18"
#
# INITIAL_EQUITY = 10.0
# MARGIN_FRAC_PER_ASSET = 0.01      # 1%
# LEVERAGE = 10.0
# TP_PCT = 0.005                    # +0.5%
# LIQ_PCT = -0.10                   # -10%
# OUT_PREFIX = "results_local"
#
# # ---- Helpers ----
#
# def load_1m_csv(path: str) -> pd.DataFrame:
#     """
#     Load a CSV with columns: index,timestamp,open,high,low,close,volume
#     - timestamp can be ISO-8601 or epoch-like; pd.to_datetime handles both.
#     - Interprets timestamps as UTC (adjust below if your files are local time).
#     """
#     df = pd.read_csv(path)
#     # Standardize column names (case-insensitive, extra spaces tolerated)
#     cols = {c.lower().strip(): c for c in df.columns}
#     required = ["timestamp", "open", "high", "low", "close", "volume"]
#     for r in required:
#         if r not in {k.lower().strip() for k in df.columns}:
#             raise ValueError(f"CSV {path} must contain column '{r}'")
#
#     # Normalize
#     df = df.rename(columns={cols["timestamp"]: "timestamp",
#                             cols["open"]: "open",
#                             cols["high"]: "high",
#                             cols["low"]: "low",
#                             cols["close"]: "close",
#                             cols["volume"]: "volume"})
#     # Parse time; assume input timestamps are UTC
#     df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
#     df = df.dropna(subset=["timestamp"])
#     # Ensure numeric OHLC
#     for c in ["open", "high", "low", "close", "volume"]:
#         df[c] = pd.to_numeric(df[c], errors="coerce")
#     df = df.dropna(subset=["open", "high", "low", "close"])
#     df = df.sort_values("timestamp").reset_index(drop=True)
#     return df[["timestamp", "open", "high", "low", "close", "volume"]]
#
#
# def minute_slice_for_hour(df: pd.DataFrame, day: date) -> pd.DataFrame:
#     """
#     For a given NY local date, return 1-minute candles from 10:00:00 to 10:59:59 NY time (inclusive).
#     We’ll use:
#       - entry at 10:00:00 open
#       - possible TP/LIQ checks on each minute candle inside 10:00..10:59
#       - exit at 10:59 close if no TP/LIQ
#     """
#     # Convert a copy to NY timezone for easy filtering; keep original UTC index for values
#     tmp = df.copy()
#     tmp["ts_ny"] = tmp["timestamp"].dt.tz_convert(NY_TZ)
#
#     # Start/end window in NY
#     start_ny = NY_TZ.localize(datetime.combine(day, datetime.min.time())) + timedelta(hours=10)
#     end_ny   = start_ny + timedelta(hours=1)  # 11:00
#
#     # Keep minutes where ts_ny >= 10:00 and < 11:00
#     mask = (tmp["ts_ny"] >= start_ny) & (tmp["ts_ny"] < end_ny)
#     window = tmp.loc[mask].copy()
#
#     # It’s 1-minute bars; we expect up to 60 rows. Missing data is possible → we’ll handle it later.
#     return window.reset_index(drop=True)
#
#
# def backtest_from_files(
#         files: Dict[str, str],
#         start_date_local: str,
#         end_date_local: str,
#         initial_equity: float = INITIAL_EQUITY,
#         margin_frac: float = MARGIN_FRAC_PER_ASSET,
#         leverage: float = LEVERAGE,
#         tp_pct: float = TP_PCT,
#         liq_pct: float = LIQ_PCT,
#         out_prefix: str = OUT_PREFIX
# ):
#     # Load all dataframes into memory
#     data = {}
#     for sym, path in files.items():
#         if not os.path.exists(path):
#             raise FileNotFoundError(f"File for {sym} not found: {path}")
#         print(f"Loading {sym} from {path} ...")
#         df = load_1m_csv(path)
#         data[sym] = df
#
#     # Build calendar of NY-local dates
#     dr = pd.date_range(start=start_date_local, end=end_date_local, freq="D")
#     equity = initial_equity
#
#     daily_rows = []
#     trade_rows = []
#     tp_count = 0
#     liq_count = 0
#     total_trades = 0
#
#     for d in dr:
#         day = d.date()
#         eq_start = equity
#         day_pnl_total = 0.0
#
#         for sym, df in data.items():
#             win = minute_slice_for_hour(df, day)
#             # Need at least the entry minute (10:00)
#             if win.empty:
#                 continue
#
#             # Entry at exactly 10:00:00 — find the minute where NY hour==10 and minute==0
#             # Since we’ve already filtered 10:00..10:59, the first row that has minute==0 is entry.
#             # But in case of missing the 10:00 bar, we skip this symbol/day.
#             win["ny_hour"] = win["timestamp"].dt.tz_convert(NY_TZ).dt.hour
#             win["ny_min"]  = win["timestamp"].dt.tz_convert(NY_TZ).dt.minute
#
#             entry_row = win[(win["ny_hour"] == 10) & (win["ny_min"] == 0)]
#             if entry_row.empty:
#                 # Missing the 10:00 bar → skip this symbol/day
#                 continue
#
#             entry_idx = entry_row.index[0]
#             entry_price = float(win.loc[entry_idx, "open"])
#
#             # Targets
#             tp_price  = entry_price * (1.0 + tp_pct)
#             liq_price = entry_price * (1.0 + liq_pct)
#
#             # Position sizing: 1% of start-of-day equity per asset
#             margin_usd = margin_frac * eq_start
#
#             # Iterate minute-by-minute from 10:00 to 10:59 (inclusive)
#             outcome = "EOH"  # default end-of-hour
#             pnl = 0.0
#             exit_price = None
#
#             # Window to scan includes the entry minute and up to the last minute before 11:00.
#             for i in range(entry_idx, len(win)):
#                 hi = float(win.loc[i, "high"])
#                 lo = float(win.loc[i, "low"])
#                 # Conservative: liquidation dominates if both happen within a minute.
#                 if lo <= liq_price:
#                     outcome = "LIQ"
#                     pnl = -margin_usd
#                     exit_price = liq_price
#                     liq_count += 1
#                     break
#                 if hi >= tp_price:
#                     outcome = "TP"
#                     pnl = margin_usd * leverage * tp_pct
#                     exit_price = tp_price
#                     tp_count += 1
#                     break
#
#             # If no TP/LIQ, exit at 11:00 — i.e., use the 10:59 close if present.
#             if outcome == "EOH":
#                 last_1059 = win[(win["ny_hour"] == 10) & (win["ny_min"] == 59)]
#                 if last_1059.empty:
#                     # No 10:59 bar; use the last available minute in the window
#                     last_idx = win.index[-1]
#                     exit_price = float(win.loc[last_idx, "close"])
#                 else:
#                     last_idx = last_1059.index[0]
#                     exit_price = float(last_1059.loc[last_idx, "close"])
#                 intrahour_ret = (exit_price - entry_price) / entry_price
#                 pnl = margin_usd * leverage * intrahour_ret
#
#             total_trades += 1
#             day_pnl_total += pnl
#
#             trade_rows.append({
#                 "date": str(day),
#                 "symbol": sym,
#                 "entry_price": entry_price,
#                 "tp_price": tp_price,
#                 "liq_price": liq_price,
#                 "exit_price": exit_price,
#                 "exit_reason": outcome,
#                 "margin_usd": margin_usd,
#                 "leverage": leverage,
#                 "pnl_usd": pnl
#             })
#
#         equity += day_pnl_total
#         daily_rows.append({
#             "date": str(day),
#             "equity_before": eq_start,
#             "day_pnl_usd": day_pnl_total,
#             "equity": equity
#         })
#
#     daily_df = pd.DataFrame(daily_rows)
#     trades_df = pd.DataFrame(trade_rows)
#
#     # Metrics
#     final_equity = float(equity)
#     total_return = (final_equity / initial_equity) - 1.0 if initial_equity > 0 else np.nan
#     # Max drawdown on daily equity
#     if not daily_df.empty:
#         eq = daily_df["equity"].to_numpy()
#         peak = np.maximum.accumulate(eq)
#         dd = (eq - peak) / peak
#         max_dd = float(dd.min())
#     else:
#         max_dd = np.nan
#
#     tp_rate = tp_count / total_trades if total_trades else np.nan
#     liq_rate = liq_count / total_trades if total_trades else np.nan
#
#     summary = {
#         "initial_equity": initial_equity,
#         "final_equity": final_equity,
#         "total_return_pct": (total_return * 100.0) if not math.isnan(total_return) else np.nan,
#         "max_drawdown_pct": (max_dd * 100.0) if not math.isnan(max_dd) else np.nan,
#         "total_trades": total_trades,
#         "tp_trades": tp_count,
#         "liq_trades": liq_count,
#         "tp_rate_pct": (tp_rate * 100.0) if not math.isnan(tp_rate) else np.nan,
#         "liq_rate_pct": (liq_rate * 100.0) if not math.isnan(liq_rate) else np.nan,
#         "symbols": list(files.keys()),
#         "params": {
#             "margin_frac_per_asset": margin_frac,
#             "leverage": leverage,
#             "take_profit_pct": tp_pct,
#             "liquidation_pct": liq_pct,
#             "start_date_local": start_date_local,
#             "end_date_local": end_date_local
#         }
#     }
#
#     # Save outputs
#     daily_csv = f"{out_prefix}_daily_equity.csv"
#     trades_csv = f"{out_prefix}_trades.csv"
#     summary_json = f"{out_prefix}_summary.json"
#     daily_df.to_csv(daily_csv, index=False)
#     trades_df.to_csv(trades_csv, index=False)
#     with open(summary_json, "w") as f:
#         json.dump(summary, f, indent=2)
#
#     # Plot equity curve
#     try:
#         if not daily_df.empty:
#             fig = plt.figure(figsize=(10, 5))
#             plt.plot(pd.to_datetime(daily_df["date"]), daily_df["equity"])
#             plt.xlabel("Date")
#             plt.ylabel("Equity (USD)")
#             plt.title("Equity Curve: 10→11 NY, 1%/asset, 10x, TP 0.5%, LIQ -10% (1m checks)")
#             plt.tight_layout()
#             eq_png = f"{out_prefix}_equity_curve.png"
#             plt.savefig(eq_png, dpi=144)
#             plt.close(fig)
#     except Exception as e:
#         print("Skipping plot due to backend error:", e)
#
#     print("\n=== SUMMARY ===")
#     for k, v in summary.items():
#         if k in ("symbols", "params"):
#             continue
#         print(f"{k}: {v}")
#     print("\nParams:", json.dumps(summary["params"], indent=2))
#     print(f"\nWrote:\n- {daily_csv}\n- {trades_csv}\n- {summary_json}\n- {out_prefix}_equity_curve.png (equity curve)")
#
#     return summary
#
#
# if __name__ == "__main__":
#     backtest_from_files(
#         files=FILE_MAP,
#         start_date_local=START_DATE_LOCAL,
#         end_date_local=END_DATE_LOCAL,
#         initial_equity=INITIAL_EQUITY,
#         margin_frac=MARGIN_FRAC_PER_ASSET,
#         leverage=LEVERAGE,
#         tp_pct=TP_PCT,
#         liq_pct=LIQ_PCT,
#         out_prefix=OUT_PREFIX
#     )
