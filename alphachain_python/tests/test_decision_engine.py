from __future__ import annotations

import time

from alphachain_python.config import SYMBOL_MAP, get_market_session
from alphachain_python.decision_engine import build_signal
from alphachain_python.models import Candle, DataQuality


def sample_candles(up: bool = True) -> list[Candle]:
    price = 100.0
    candles = []
    for idx in range(80):
        drift = 0.35 if up else -0.35
        o = price
        c = price + drift
        h = max(o, c) + 0.25
        l = min(o, c) - 0.25
        candles.append(Candle(ts=time.time() + idx * 60, o=o, h=h, l=l, c=c, v=1000 + idx))
        price = c
    return candles


def run() -> None:
    symbol = SYMBOL_MAP["XAUUSD"]
    quality = DataQuality(provider="UnitTest", synthetic=False, note="ok", last_updated_ts=time.time())
    signal = build_signal(
        symbol_cfg=symbol,
        candles=sample_candles(True),
        live_price=128.0,
        data_quality=quality,
        session_state=get_market_session(),
        higher_timeframe_candles=sample_candles(True),
        lower_timeframe_candles=sample_candles(True),
        news_bias="Low",
    )
    assert signal.direction == "BUY"
    assert signal.take_profit > signal.entry
    assert signal.stop_loss < signal.entry
    assert len(signal.session_plans) == 3
    assert signal.session_plans[0].entry_min <= signal.session_plans[0].entry_max
    print("OK -- decision engine")


if __name__ == "__main__":
    run()


def geometry_regression() -> None:
    """Regression: the stop must sit strictly beyond the entry zone in the trade
    direction (below for longs, above for shorts), even when raw structure levels
    land on the wrong side of price (e.g. last swing low ABOVE current price)."""
    from alphachain_python.config import SESSIONS
    from alphachain_python.decision_engine import _plan_for_session, build_signal
    from alphachain_python.engines import Amplification, RiskBuffer

    risk = RiskBuffer(atr_value=5.0, stop_distance=8.0, uncertainty_factor=1.0)
    amp = Amplification(ari=1.0, expanding=False, rsi_value=55.0, volatility_regime="Normal")

    # Broken-structure case: support (104) ABOVE price (100) - the user-reported bug.
    for key in ("asian", "european", "american"):
        plan = _plan_for_session(SESSIONS[key], "BUY", 100.0, 104.0, 96.0, risk, amp, 80, None, 2, "Low")
        assert plan.stop_loss < plan.entry_min, f"{key}: long stop {plan.stop_loss} not below entry zone {plan.entry_min}"
        assert plan.take_profit > plan.entry_max, f"{key}: long TP {plan.take_profit} not above entry zone {plan.entry_max}"
        plan = _plan_for_session(SESSIONS[key], "SELL", 100.0, 104.0, 96.0, risk, amp, 80, None, 2, "Low")
        assert plan.stop_loss > plan.entry_max, f"{key}: short stop {plan.stop_loss} not above entry zone {plan.entry_max}"
        assert plan.take_profit < plan.entry_min, f"{key}: short TP {plan.take_profit} not below entry zone {plan.entry_min}"

    # Full engine path on the standard fixture must also stay coherent.
    symbol = SYMBOL_MAP["XAUUSD"]
    quality = DataQuality(provider="UnitTest", synthetic=False, note="ok", last_updated_ts=time.time())
    sig = build_signal(
        symbol_cfg=symbol, candles=sample_candles(True), live_price=128.0, data_quality=quality,
        session_state=get_market_session(), higher_timeframe_candles=sample_candles(True),
        lower_timeframe_candles=sample_candles(True), news_bias="Low",
    )
    assert sig.stop_loss < sig.entry_min and sig.take_profit > sig.entry_max
    for plan in sig.session_plans:
        if plan.direction == "BUY":
            assert plan.stop_loss < plan.entry_min and plan.take_profit > plan.entry_max
        else:
            assert plan.stop_loss > plan.entry_max and plan.take_profit < plan.entry_min
    print("OK -- geometry regression (stops beyond entry zones in trade direction)")


if __name__ == "__main__":
    run()
    geometry_regression()
