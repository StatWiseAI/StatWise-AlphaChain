"""SCM-derived market intelligence engines."""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import indicators as ind
from .models import Candle


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


@dataclass
class DemandSignal:
    dps: float
    direction: str
    confidence: int
    regime: str
    higher_timeframe_bias: str


@dataclass
class RiskBuffer:
    atr_value: float
    stop_distance: float
    uncertainty_factor: float


@dataclass
class Amplification:
    ari: float
    expanding: bool
    rsi_value: float
    volatility_regime: str


def demand_sensing(candles: list[Candle], higher_timeframe_candles: list[Candle] | None = None, weights: dict | None = None) -> DemandSignal:
    weights = weights or {"trend": 1.3, "structure": 1.0, "fvg": 0.8, "momentum": 0.9, "htf": 1.1, "regime": 0.5}
    closes = [c.c for c in candles]
    px = closes[-1]

    trend = ind.trend_direction(closes)
    z_trend = 1.0 if trend == "Bull" else (-1.0 if trend == "Bear" else 0.0)

    lo, hi = min(c.l for c in candles[-20:]), max(c.h for c in candles[-20:])
    mid = (lo + hi) / 2
    z_structure = 1.0 if px > mid else -1.0

    fvg = ind.find_fvg(candles)
    z_fvg = 1.0 if fvg and fvg.kind == "bullish" else -1.0 if fvg and fvg.kind == "bearish" else 0.0

    rsi_value = ind.rsi(closes, 14)
    z_momentum = max(-1.0, min(1.0, (rsi_value - 50) / 25))

    htf_bias = "Flat"
    z_htf = 0.0
    if higher_timeframe_candles:
        htf_bias = ind.trend_direction([c.c for c in higher_timeframe_candles])
        z_htf = 1.0 if htf_bias == "Bull" else (-1.0 if htf_bias == "Bear" else 0.0)

    regime = ind.classify_regime(candles)
    z_regime = 0.25 if regime == "Trend" else (-0.25 if regime == "Volatile Range" else 0.0)

    weighted_sum = (
        weights["trend"] * z_trend
        + weights["structure"] * z_structure
        + weights["fvg"] * z_fvg
        + weights["momentum"] * z_momentum
        + weights["htf"] * z_htf
        + weights["regime"] * z_regime
    )
    dps = _logistic(weighted_sum)
    direction = "BUY" if dps >= 0.53 else "SELL" if dps <= 0.47 else "WAIT"
    confidence = int(round(42 + abs(dps - 0.5) * 2 * 50))
    return DemandSignal(round(dps, 4), direction, max(0, min(100, confidence)), regime, htf_bias)


def safety_stock(candles: list[Candle], k: float = 1.6, session_multiplier: float = 1.0, event_risk: str = "Low") -> RiskBuffer:
    atr_value = ind.atr(candles, 14)
    uncertainty_factor = 1.0
    if event_risk == "Medium":
        uncertainty_factor = 1.12
    elif event_risk == "High":
        uncertainty_factor = 1.28
    stop_distance = atr_value * k * session_multiplier * uncertainty_factor
    return RiskBuffer(atr_value, stop_distance, uncertainty_factor)


def bullwhip_detection(candles: list[Candle]) -> Amplification:
    ranges = [c.h - c.l for c in candles]
    if len(ranges) < 12:
        return Amplification(1.0, False, 50.0, "Balanced")
    avg = sum(ranges[-10:]) / 10
    recent = sum(ranges[-3:]) / 3
    ari = recent / avg if avg else 1.0
    rsi_value = ind.rsi([c.c for c in candles], 14)
    volatility_regime = "High" if ari > 1.25 else "Normal" if ari > 0.9 else "Compressed"
    return Amplification(round(ari, 3), ari > 1.05, rsi_value, volatility_regime)
