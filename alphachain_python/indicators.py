"""Technical analytics shared by the AlphaChain engines and UI."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import Candle


def atr(candles: list[Candle], period: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    trs = []
    for i in range(1, len(candles)):
        h, l, pc = candles[i].h, candles[i].l, candles[i - 1].c
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    window = trs[-period:]
    return sum(window) / max(1, len(window))


def rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) <= period:
        return 50.0
    gains = losses = 0.0
    for i in range(len(closes) - period, len(closes)):
        ch = closes[i] - closes[i - 1]
        if ch >= 0:
            gains += ch
        else:
            losses -= ch
    if losses == 0:
        return 100.0
    rs = (gains / period) / (losses / period)
    return round(100 - 100 / (1 + rs), 1)


@dataclass
class FVG:
    kind: str
    lo: float
    hi: float


def find_fvg(candles: list[Candle], lookback: int = 16) -> Optional[FVG]:
    n = len(candles)
    start = max(2, n - lookback)
    for i in range(n - 2, start - 1, -1):
        prev, nxt = candles[i - 1], candles[i + 1]
        if prev.h < nxt.l:
            return FVG("bullish", prev.h, nxt.l)
        if prev.l > nxt.h:
            return FVG("bearish", nxt.h, prev.l)
    return None


def swing_support_resistance(candles: list[Candle], window: int = 2) -> tuple[float, float]:
    n = len(candles)
    highs, lows = [], []
    for i in range(window, n - window):
        seg = candles[i - window : i + window + 1]
        if all(candles[i].h >= s.h for s in seg):
            highs.append(candles[i].h)
        if all(candles[i].l <= s.l for s in seg):
            lows.append(candles[i].l)
    px = candles[-1].c
    avg_atr = atr(candles, 14) or px * 0.01
    res_candidates = sorted([h for h in highs if h > px * 1.0004])
    sup_candidates = sorted([l for l in lows if l < px * 0.9996], reverse=True)
    resistance = res_candidates[0] if res_candidates else px + avg_atr * 3
    support = sup_candidates[0] if sup_candidates else px - avg_atr * 3
    return support, resistance


def volume_expanding(candles: list[Candle], recent: int = 3, lookback: int = 10) -> bool:
    if len(candles) < lookback + recent:
        return False
    ranges = [c.h - c.l for c in candles]
    avg = sum(ranges[-lookback:]) / lookback
    recent_avg = sum(ranges[-recent:]) / recent
    return recent_avg > avg * 1.05


def normalized_range(candles: list[Candle], lookback: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    window = candles[-lookback:]
    avg_close = sum(c.c for c in window) / len(window)
    return (sum(c.h - c.l for c in window) / len(window)) / avg_close if avg_close else 0.0


def sma(closes: list[float], period: int) -> float:
    window = closes[-period:]
    return sum(window) / len(window) if window else 0.0


def trend_direction(closes: list[float]) -> str:
    if len(closes) < 10:
        return "Flat"
    avg = sma(closes, 10)
    last = closes[-1]
    slope = (last - closes[-6]) / closes[-6] if len(closes) >= 6 and closes[-6] else 0.0
    if last > avg * 1.0008 and slope > 0.0005:
        return "Bull"
    if last < avg * 0.9992 and slope < -0.0005:
        return "Bear"
    return "Flat"


def trend_score(closes: list[float]) -> float:
    if len(closes) < 20:
        return 0.0
    fast = sma(closes, 8)
    slow = sma(closes, 21)
    slope = (closes[-1] - closes[-6]) / closes[-6] if len(closes) >= 6 and closes[-6] else 0.0
    score = ((fast - slow) / slow if slow else 0.0) + slope
    return max(-1.0, min(1.0, score * 25))


def classify_regime(candles: list[Candle]) -> str:
    closes = [c.c for c in candles]
    abs_trend = abs(trend_score(closes))
    n_range = normalized_range(candles)
    if n_range > 0.02 and abs_trend < 0.18:
        return "Volatile Range"
    if abs_trend > 0.24:
        return "Trend"
    if n_range < 0.006:
        return "Compression"
    return "Balanced"
