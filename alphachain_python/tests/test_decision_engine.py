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
