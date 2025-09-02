#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backtest: 10:00 -> 11:00 New York time, daily, long-only on BTC, ETH, SOL, DOGE, XRP.

Strategy (from your spec):
- At 10:00 a.m. New York time, buy 1% of current equity (margin) *per asset* in BTC, ETH, SOL, DOGE, XRP
- Leverage: 10×, isolated
- Take-profit: +5% move from entry price within the hour (assumes exit exactly at +5% when touched)
- If a position is liquidated, so be it; we approximate liquidation for 10× as a -10% price move from entry
  (in real futures, liq depends on maintenance margin, fees, etc.; this is a simple approximation)
- All remaining positions close at 11:00 a.m. New York time (end of the 10:00–11:00 candle)
- Trades every single calendar day (weekends & holidays)
- Initial capital: $10

Assumptions/Simplifications:
- Uses Binance spot hourly candles as a proxy for intrahour path
- No fees, slippage, funding, or maker/taker differences
- If both TP and LIQ are touched during the hour, LIQ is assumed to happen first (conservative)
"""

import sys
import time
import math
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, List

import requests
import pandas as pd
import numpy as np
import pytz
from dateutil.relativedelta import relativedelta
import os
os.environ["MPLBACKEND"] = "Agg"   # must be set before importing pyplot

import matplotlib
matplotlib.use("Agg", force=True)  # ensure a non-GUI backend


import matplotlib.pyplot as plt

NY_TZ = pytz.timezone("America/New_York")
UTC = pytz.UTC

BINANCE_BASE = "https://api.binance.com"  # public, no API key needed

DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "XRPUSDT"]


def binance_klines(symbol: str, interval: str, start_utc: datetime, end_utc: datetime, limit: int = 1000) -> pd.DataFrame:
    """Fetch klines from Binance's public REST API in a loop to cover [start_utc, end_utc)."""
    url = f"{BINANCE_BASE}/api/v3/klines"
    start_ms = int(start_utc.timestamp() * 1000)
    end_ms = int(end_utc.timestamp() * 1000)
    out = []
    while start_ms < end_ms:
        params = dict(symbol=symbol, interval=interval, startTime=start_ms, endTime=end_ms, limit=limit)
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        out.extend(data)
        last_open = data[-1][0]
        # advance one interval (1h) past last_open to keep moving
        start_ms = last_open + 60 * 60 * 1000
        time.sleep(0.15)  # polite pacing
    if not out:
        return pd.DataFrame(columns=["open_time", "open", "high", "low", "close", "close_time"])
    cols = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "trades", "taker_base",
        "taker_quote", "ignore"
    ]
    df = pd.DataFrame(out, columns=cols)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    for c in ["open", "high", "low", "close"]:
        df[c] = df[c].astype(float)
    return df[["open_time", "open", "high", "low", "close", "close_time"]]


def select_10am_candles(df: pd.DataFrame) -> pd.DataFrame:
    """Return only the hourly candles that start at 10:00 America/New_York for each local date."""
    if df.empty:
        return df
    tmp = df.copy()
    tmp["open_time_ny"] = tmp["open_time"].dt.tz_convert(NY_TZ)
    tmp["date"] = tmp["open_time_ny"].dt.date
    tmp["hour"] = tmp["open_time_ny"].dt.hour
    # 10:00-11:00 candle has hour==10
    ten = tmp[tmp["hour"] == 10].copy()
    ten.rename(columns={
        "open": "entry_open",
        "high": "hour_high",
        "low": "hour_low",
        "close": "hour_close"
    }, inplace=True)
    ten = ten[["date", "open_time", "open_time_ny", "entry_open", "hour_high", "hour_low", "hour_close"]]
    return ten


def backtest(
        start_date: str,
        end_date: str,
        symbols: List[str] = None,
        initial_equity: float = 10.0,
        margin_frac: float = 0.01,  # 1% per asset
        leverage: float = 10.0,
        take_profit: float = 0.005,  # +5%
        liquidation: float = -0.10,  # -10% (approx 10x liq)
        out_prefix: str = "results"
) -> Dict:
    symbols = symbols or DEFAULT_SYMBOLS

    # Build UTC fetch window around the requested local dates
    start_local = datetime.fromisoformat(start_date)  # naive local date
    end_local = datetime.fromisoformat(end_date)
    start_bound_utc = NY_TZ.localize(datetime.combine(start_local.date(), datetime.min.time())).astimezone(UTC) - timedelta(days=1)
    end_bound_utc = NY_TZ.localize(datetime.combine(end_local.date(), datetime.max.time())).astimezone(UTC) + timedelta(days=1)

    print(f"Fetching hourly data from Binance for {len(symbols)} symbols...")
    candles_10am: Dict[str, pd.DataFrame] = {}
    for sym in symbols:
        print(f"  - {sym} ...", flush=True)
        df = binance_klines(sym, "5m", start_bound_utc, end_bound_utc)
        ten = select_10am_candles(df)
        candles_10am[sym] = ten

    # Daily range in NY (inclusive)
    dr = pd.date_range(start=start_local.date(), end=end_local.date(), freq="D")

    equity = initial_equity
    daily_rows = []
    trade_rows = []
    total_trades = 0
    tp_count = 0
    liq_count = 0

    for d in dr:
        day = d.date()
        day_equity_before = equity
        day_pnl = 0.0

        for sym in symbols:
            ten = candles_10am[sym]
            row = ten[ten["date"] == day]
            if row.empty:
                # no candle for this symbol/day (rare) -> skip
                continue

            r = row.iloc[0]
            entry = float(r["entry_open"])
            hh = float(r["hour_high"])
            ll = float(r["hour_low"])
            cls = float(r["hour_close"])  # price at exactly 11:00

            # Allocate 1% of starting-of-day equity per asset (simultaneous entries at 10:00)
            margin_usd = margin_frac * day_equity_before

            hit_liq = ll <= entry * (1.0 + liquidation)     # liquidation ~ -10%
            hit_tp  = hh >= entry * (1.0 + take_profit)     # TP +5%

            if hit_tp:
                pnl = -margin_usd
                exit_reason = "LIQ"
                liq_count += 1
                price_return_used = liquidation
            elif hit_liq:
                pnl = margin_usd * leverage * take_profit
                exit_reason = "TP"
                tp_count += 1
                price_return_used = take_profit
            else:
                intrahour_ret = (cls - entry) / entry
                pnl = margin_usd * leverage * intrahour_ret
                exit_reason = "EOH"  # end of hour
                price_return_used = intrahour_ret

            day_pnl += pnl
            total_trades += 1

            trade_rows.append({
                "date": str(day),
                "symbol": sym,
                "entry_price": entry,
                "hour_high": hh,
                "hour_low": ll,
                "exit_price_11am": cls,
                "exit_reason": exit_reason,
                "price_return_used": price_return_used,
                "margin_usd": margin_usd,
                "leverage": leverage,
                "pnl_usd": pnl,
            })

        equity += day_pnl
        daily_rows.append({
            "date": str(day),
            "equity": equity,
            "day_pnl_usd": day_pnl,
            "equity_before": day_equity_before
        })

    daily_df = pd.DataFrame(daily_rows)
    trades_df = pd.DataFrame(trade_rows)

    # Metrics
    final_equity = float(equity)
    total_return = (final_equity / initial_equity) - 1.0 if initial_equity > 0 else np.nan

    # Max drawdown on daily equity
    if not daily_df.empty:
        eq = daily_df["equity"].values
        peak = np.maximum.accumulate(eq)
        dd = (eq - peak) / peak
        max_dd = float(dd.min())
    else:
        max_dd = np.nan

    tp_rate = tp_count / total_trades if total_trades else np.nan
    liq_rate = liq_count / total_trades if total_trades else np.nan

    summary = {
        "initial_equity": initial_equity,
        "final_equity": final_equity,
        "total_return_pct": total_return * 100.0 if not math.isnan(total_return) else np.nan,
        "max_drawdown_pct": max_dd * 100.0 if not math.isnan(max_dd) else np.nan,
        "total_trades": total_trades,
        "tp_trades": tp_count,
        "liq_trades": liq_count,
        "tp_rate_pct": tp_rate * 100.0 if not math.isnan(tp_rate) else np.nan,
        "liq_rate_pct": liq_rate * 100.0 if not math.isnan(liq_rate) else np.nan,
        "symbols": symbols,
        "params": {
            "margin_frac_per_asset": margin_frac,
            "leverage": leverage,
            "take_profit": take_profit,
            "liquidation": liquidation,
            "start_date": start_date,
            "end_date": end_date
        }
    }

    # Save outputs
    daily_csv = f"{out_prefix}_daily_equity.csv"
    trades_csv = f"{out_prefix}_trades.csv"
    summary_json = f"{out_prefix}_summary.json"
    daily_df.to_csv(daily_csv, index=False)
    trades_df.to_csv(trades_csv, index=False)
    with open(summary_json, "w") as f:
        json.dump(summary, f, indent=2)

    # Plot equity curve
    if not daily_df.empty:
        fig = plt.figure(figsize=(10, 5))
        plt.plot(pd.to_datetime(daily_df["date"]), daily_df["equity"])
        plt.xlabel("Date")
        plt.ylabel("Equity (USD)")
        plt.title("Equity Curve: 10→11am NY, 1%/asset, 10x, TP 5%, LIQ -10%, Isolated")
        plt.tight_layout()
        eq_png = f"{out_prefix}_equity_curve.png"
        plt.savefig(eq_png, dpi=144)
        plt.close(fig)

    print("\n=== SUMMARY ===")
    for k, v in summary.items():
        if k in ("symbols", "params"):
            continue
        print(f"{k}: {v}")
    print("\nParams:", json.dumps(summary["params"], indent=2))
    print(f"\nWrote:\n- {daily_csv}\n- {trades_csv}\n- {summary_json}\n- {out_prefix}_equity_curve.png (equity curve)")

    return summary


def parse_args():
    parser = argparse.ArgumentParser(description="Backtest the 10:00->11:00 NY daily long strategy on Binance hourly data.")
    parser.add_argument("--start", type=str, default=None, help="Start date (YYYY-MM-DD) in New York time (default: 2 years ago today)")
    parser.add_argument("--end", type=str, default=None, help="End date (YYYY-MM-DD) in New York time (default: yesterday)")
    parser.add_argument("--initial", type=float, default=10.0, help="Initial equity in USD (default: 10)")
    parser.add_argument("--prefix", type=str, default="results", help="Output file prefix (default: results)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    today_ny = datetime.now(NY_TZ).date()
    default_start = (today_ny - relativedelta(years=2))
    default_end = (today_ny - timedelta(days=1))  # up through yesterday

    start = args.start or str(default_start)
    end = args.end or str(default_end)

    backtest(
        start_date=start,
        end_date=end,
        symbols=DEFAULT_SYMBOLS,
        initial_equity=args.initial,
        margin_frac=0.01,
        leverage=10.0,
        take_profit=0.05,
        liquidation=-0.10,
        out_prefix=args.prefix
    )
