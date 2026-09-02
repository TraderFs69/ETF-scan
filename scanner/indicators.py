from __future__ import annotations

import numpy as np
import pandas as pd


def rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    average_gain = gains.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    average_loss = losses.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    relative_strength = average_gain / average_loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + relative_strength)
    return rsi.where(average_loss != 0, 100.0)


def atr_wilder(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    previous_close = frame["Close"].shift(1)
    true_range = pd.concat(
        [
            frame["High"] - frame["Low"],
            (frame["High"] - previous_close).abs(),
            (frame["Low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def heikin_ashi(frame: pd.DataFrame) -> pd.DataFrame:
    ha = pd.DataFrame(index=frame.index)
    ha["Close"] = (frame["Open"] + frame["High"] + frame["Low"] + frame["Close"]) / 4
    ha_open = np.zeros(len(frame), dtype=float)
    if len(frame):
        ha_open[0] = (float(frame["Open"].iloc[0]) + float(frame["Close"].iloc[0])) / 2
        for index in range(1, len(frame)):
            ha_open[index] = (ha_open[index - 1] + float(ha["Close"].iloc[index - 1])) / 2
    ha["Open"] = ha_open
    ha["Green"] = ha["Close"] > ha["Open"]
    return ha


def add_indicators(frame: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    out = frame.copy()
    for period in (20, 50, 200):
        out[f"EMA{period}"] = out["Close"].ewm(span=period, adjust=False).mean()

    out["RSI"] = rsi_wilder(out["Close"], int(cfg["rsi_period"]))
    out["ATR"] = atr_wilder(out, int(cfg["atr_period"]))
    volume_period = int(cfg["volume_average_period"])
    out["VolumeAverage"] = out["Volume"].rolling(volume_period).mean()
    out["DollarVolumeAverage"] = (out["Close"] * out["Volume"]).rolling(volume_period).mean()
    ha = heikin_ashi(out)
    out["HAGreen"] = ha["Green"]
    return out
