from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .models import SessionProfile, SessionState, SymbolConfig, TimeframeConfig

APP_NAME = "AlphaChain Pro"
APP_TAGLINE = "Institutional-style AI trading decision support built from the thesis framework."
USER_TIMEZONE = "Europe/Berlin"
DB_PATH = "alphachain.sqlite3"

SYMBOLS = [
    SymbolConfig("XAUUSD", "XAU/USD", "Gold Spot", "Commodities", 2, 2.4, yahoo="GC=F", tradingview="OANDA:XAUUSD", fallback_volatility=0.0025),
    SymbolConfig("WTIUSD", "WTI Crude", "WTI Front Month", "Commodities", 2, 2.3, yahoo="CL=F", tradingview="NYMEX:CL1!", fallback_volatility=0.0050),
    SymbolConfig("EURUSD", "EUR/USD", "Euro vs US Dollar", "Forex", 4, 2.0, yahoo="EURUSD=X", tradingview="FX:EURUSD", fallback_volatility=0.0016),
    SymbolConfig("GBPJPY", "GBP/JPY", "British Pound vs Japanese Yen", "Forex", 3, 2.2, yahoo="GBPJPY=X", tradingview="FX:GBPJPY", fallback_volatility=0.0030),
    SymbolConfig("BTCUSD", "BTC/USD", "Bitcoin", "Crypto", 0, 2.2, yahoo="BTC-USD", binance="BTCUSDT", tradingview="BINANCE:BTCUSDT", fallback_volatility=0.0060),
    SymbolConfig("ETHUSD", "ETH/USD", "Ethereum", "Crypto", 2, 2.1, yahoo="ETH-USD", binance="ETHUSDT", tradingview="BINANCE:ETHUSDT", fallback_volatility=0.0065),
    SymbolConfig("AAPL", "AAPL", "Apple Inc.", "Equities", 2, 2.4, yahoo="AAPL", tradingview="NASDAQ:AAPL", fallback_volatility=0.0040),
    SymbolConfig("NVDA", "NVDA", "NVIDIA Corporation", "Equities", 2, 2.5, yahoo="NVDA", tradingview="NASDAQ:NVDA", fallback_volatility=0.0060),
    SymbolConfig("ES", "ES", "S&P 500 E-mini Futures", "Futures", 2, 2.2, yahoo="ES=F", tradingview="CME_MINI:ES1!", fallback_volatility=0.0020),
    SymbolConfig("NAS100", "NAS100", "Nasdaq 100 Futures Proxy", "Indices", 1, 2.3, yahoo="NQ=F", tradingview="NASDAQ:NDX", fallback_volatility=0.0025),
]

SYMBOL_MAP = {item.id: item for item in SYMBOLS}

TIMEFRAMES = {
    "5m": TimeframeConfig("5m", "5 minutes", "5m", "5d", "5m", 120),
    "15m": TimeframeConfig("15m", "15 minutes", "15m", "10d", "15m", 120),
    "1H": TimeframeConfig("1H", "1 hour", "60m", "1mo", "1h", 120),
    "4H": TimeframeConfig("4H", "4 hours", "1h", "3mo", "4h", 180),
    "1D": TimeframeConfig("1D", "1 day", "1d", "1y", "1d", 220),
}

HIGHER_TIMEFRAME = {"5m": "15m", "15m": "1H", "1H": "4H", "4H": "1D", "1D": "1D"}
LOWER_TIMEFRAME = {"5m": "5m", "15m": "5m", "1H": "15m", "4H": "1H", "1D": "4H"}
WATCHLIST_TIMEFRAME = "15m"

SESSIONS = {
    "asian": SessionProfile(
        key="asian",
        label="Asian Session",
        start_hour_utc=0,
        end_hour_utc=8,
        volatility_bias=0.90,
        preferred_entry="range_retest",
        style_note="Prefer patient entries near support or resistance; avoid chasing low-liquidity spikes.",
    ),
    "european": SessionProfile(
        key="european",
        label="European Session",
        start_hour_utc=7,
        end_hour_utc=16,
        volatility_bias=1.05,
        preferred_entry="breakout_or_pullback",
        style_note="Best session for trend initiation and structured breakouts when higher timeframe bias aligns.",
    ),
    "american": SessionProfile(
        key="american",
        label="American Session",
        start_hour_utc=13,
        end_hour_utc=22,
        volatility_bias=1.15,
        preferred_entry="confirmation",
        style_note="Require confirmation and wider volatility buffer, especially around macro releases.",
    ),
}


def get_market_session(now: datetime | None = None, tz_name: str = USER_TIMEZONE) -> SessionState:
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    local = now_utc.astimezone(ZoneInfo(tz_name))
    active: list[str] = []
    hour = now_utc.hour
    for key, profile in SESSIONS.items():
        if profile.start_hour_utc <= hour < profile.end_hour_utc:
            active.append(key)
    if not active:
        active = ["asian"]
    primary = active[-1]
    return SessionState(
        primary_key=primary,
        primary_label=SESSIONS[primary].label,
        local_time_label=local.strftime("%Y-%m-%d %H:%M %Z"),
        utc_time_label=now_utc.strftime("%Y-%m-%d %H:%M UTC"),
        overlaps=[SESSIONS[key].label for key in active[:-1]],
    )
