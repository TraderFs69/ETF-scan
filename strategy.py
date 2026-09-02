from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .indicators import add_indicators


@dataclass
class Signal:
    symbol: str
    name: str
    market: str
    category: str
    date: str
    score: int
    close: float
    rs_percentile: float
    rsi: float
    ema_rebound: str
    relative_volume: float
    average_dollar_volume: float
    atr: float
    stop: float
    target_2r: float
    target_3r: float
    risk_pct: float
    reasons: str

    def to_dict(self) -> dict:
        return asdict(self)


def _confirmed_higher_low(values: pd.Series, lookback: int = 40) -> bool:
    recent = values.tail(lookback).reset_index(drop=True)
    pivots: list[float] = []
    for index in range(2, len(recent) - 2):
        window = recent.iloc[index - 2 : index + 3]
        if recent.iloc[index] == window.min() and int((window == recent.iloc[index]).sum()) == 1:
            pivots.append(float(recent.iloc[index]))
    return len(pivots) >= 2 and pivots[-1] > pivots[-2]


def relative_strength_metrics(history: pd.DataFrame, benchmark: pd.DataFrame) -> tuple[bool, float]:
    aligned = pd.concat(
        [history["Close"].rename("ETF"), benchmark["Close"].rename("Benchmark")],
        axis=1,
        join="inner",
    ).dropna()
    if len(aligned) < 70:
        return False, float("nan")
    ratio = aligned["ETF"] / aligned["Benchmark"]
    ratio_ema50 = ratio.ewm(span=50, adjust=False).mean()
    ratio_is_strong = bool(ratio.iloc[-1] > ratio_ema50.iloc[-1] and ratio.iloc[-1] > ratio.iloc[-10])
    excess_return_63 = float(
        aligned["ETF"].pct_change(63).iloc[-1] - aligned["Benchmark"].pct_change(63).iloc[-1]
    )
    return ratio_is_strong, excess_return_63


def evaluate(
    meta: pd.Series,
    history: pd.DataFrame,
    benchmark: pd.DataFrame,
    rs_percentile: float,
    cfg: dict,
) -> Signal | None:
    minimum_sessions = int(cfg["minimum_history_sessions"])
    if len(history) < minimum_sessions or len(benchmark) < minimum_sessions:
        return None

    frame = add_indicators(history, cfg).dropna(
        subset=["EMA20", "EMA50", "EMA200", "RSI", "ATR", "DollarVolumeAverage"]
    )
    if len(frame) < 25:
        return None

    current = frame.iloc[-1]
    previous = frame.iloc[-2]
    close = float(current["Close"])
    atr = float(current["ATR"])
    market = str(meta["market"])

    minimum_price = float(cfg["minimum_price"])
    minimum_dollar_volume = float(cfg["minimum_average_dollar_volume"][market])
    average_dollar_volume = float(current["DollarVolumeAverage"])
    if close < minimum_price or average_dollar_volume < minimum_dollar_volume:
        return None
    if atr <= 0 or not np.isfinite([close, atr, rs_percentile]).all():
        return None

    trend_structure = close > current["EMA50"] > current["EMA200"]
    ema50_rising = current["EMA50"] > frame["EMA50"].iloc[-11]
    ema200_rising = current["EMA200"] > frame["EMA200"].iloc[-21]
    if not trend_structure or not ema50_rising:
        return None

    rs_is_strong, _ = relative_strength_metrics(history, benchmark)
    minimum_rs_percentile = float(cfg["minimum_rs_percentile"])
    if not rs_is_strong or rs_percentile < minimum_rs_percentile:
        return None

    pullback_lookback = int(cfg["pullback_lookback"])
    tolerance = float(cfg["ema_touch_atr_tolerance"])
    recent = frame.tail(pullback_lookback + 1).iloc[:-1]
    rebounds: list[str] = []
    for period in (20, 50):
        ema = recent[f"EMA{period}"]
        touched = (
            ((recent["Low"] - ema).abs() <= recent["ATR"] * tolerance)
            | ((recent["Low"] <= ema) & (recent["High"] >= ema))
        ).any()
        if touched and close > current[f"EMA{period}"]:
            rebounds.append(f"EMA{period}")
    if not rebounds:
        return None

    price_confirmation = close > float(previous["High"])
    if bool(cfg["require_close_above_previous_high"]) and not price_confirmation:
        return None

    extension_atr = max(0.0, (close - float(current["EMA20"])) / atr)
    if extension_atr > float(cfg["maximum_extension_atr"]):
        return None

    score = 0
    reasons: list[str] = []

    score += 15
    reasons.append("prix > EMA50 > EMA200")
    score += 5
    reasons.append("EMA50 en hausse")
    if ema200_rising:
        score += 5
        reasons.append("EMA200 en hausse")

    score += 15
    reasons.append("force relative en hausse")
    score += 10
    reasons.append(f"force relative {rs_percentile:.0f}e percentile")

    score += 15
    reasons.append("repli contrôlé sur " + "/".join(rebounds))

    rsi_recovery = (
        float(cfg["rsi_minimum"]) <= current["RSI"] <= float(cfg["rsi_maximum"])
        and current["RSI"] > previous["RSI"]
        and frame["RSI"].tail(6).min() <= float(cfg["rsi_recent_ceiling"])
    )
    if rsi_recovery:
        score += 10
        reasons.append("RSI refroidi puis en hausse")

    if bool(current["HAGreen"]) and not bool(previous["HAGreen"]):
        score += 5
        reasons.append("Heikin-Ashi rouge vers vert")

    if price_confirmation:
        score += 10
        reasons.append("clôture au-dessus du sommet précédent")

    higher_low = _confirmed_higher_low(frame["Low"])
    if higher_low:
        score += 5
        reasons.append("Higher Low")

    relative_volume = float(current["Volume"] / current["VolumeAverage"]) if current["VolumeAverage"] > 0 else 0.0
    volume_confirmation = relative_volume >= float(cfg["minimum_relative_volume_bonus"])
    if volume_confirmation:
        score += 5
        reasons.append("volume de confirmation")

    if score < int(cfg["minimum_score"]):
        return None

    swing_low = float(frame["Low"].tail(10).min())
    stop_from_atr = close - float(cfg["stop_atr"]) * atr
    stop = min(swing_low - 0.10 * atr, stop_from_atr)
    risk = close - stop
    if risk <= 0:
        return None

    return Signal(
        symbol=str(meta["symbol"]),
        name=str(meta["name"]),
        market=market,
        category=str(meta["category"]),
        date=str(pd.Timestamp(frame.index[-1]).date()),
        score=min(int(score), 100),
        close=round(close, 4),
        rs_percentile=round(rs_percentile, 1),
        rsi=round(float(current["RSI"]), 1),
        ema_rebound="/".join(rebounds),
        relative_volume=round(relative_volume, 2),
        average_dollar_volume=round(average_dollar_volume),
        atr=round(atr, 4),
        stop=round(stop, 4),
        target_2r=round(close + 2 * risk, 4),
        target_3r=round(close + 3 * risk, 4),
        risk_pct=round(100 * risk / close, 2),
        reasons="; ".join(reasons),
    )
