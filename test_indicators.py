import numpy as np
import pandas as pd

from scanner.indicators import atr_wilder, heikin_ashi, rsi_wilder


def test_rsi_of_strong_uptrend_is_high():
    close = pd.Series(np.arange(1.0, 60.0))
    assert rsi_wilder(close, 14).iloc[-1] == 100.0


def test_atr_is_positive():
    close = pd.Series(np.linspace(10, 20, 60))
    frame = pd.DataFrame({
        "Open": close - 0.1,
        "High": close + 0.5,
        "Low": close - 0.5,
        "Close": close,
    })
    assert atr_wilder(frame, 14).iloc[-1] > 0


def test_heikin_ashi_returns_one_row_per_bar():
    frame = pd.DataFrame({
        "Open": [10, 11, 12],
        "High": [12, 13, 14],
        "Low": [9, 10, 11],
        "Close": [11, 12, 13],
    })
    result = heikin_ashi(frame)
    assert len(result) == len(frame)
    assert {"Open", "Close", "Green"}.issubset(result.columns)
