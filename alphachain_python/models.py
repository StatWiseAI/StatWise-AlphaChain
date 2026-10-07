from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SymbolConfig:
    id: str
    name: str
    full: str
    category: str
    decimals: int
    base_risk_reward: float
    yahoo: str | None = None
    binance: str | None = None
    tradingview: str | None = None
    stooq: str | None = None
    fallback_volatility: float = 0.002


@dataclass(frozen=True)
class TimeframeConfig:
    key: str
    label: str
    yahoo_interval: str
    yahoo_period: str
    binance_interval: str
    bars: int


@dataclass(frozen=True)
class SessionProfile:
    key: str
    label: str
    start_hour_utc: int
    end_hour_utc: int
    volatility_bias: float
    preferred_entry: str
    style_note: str


@dataclass
class DataQuality:
    provider: str
    synthetic: bool
    note: str
    last_updated_ts: float


@dataclass
class Quote:
    symbol_id: str
    price: float
    change_pct: float
    ts: float
    provider: str
    provider_symbol: str | None = None
    quote_ts: float | None = None
    is_realtime: bool = False
    delay_note: str | None = None
    cross_source: str | None = None
    cross_price: float | None = None
    cross_ts: float | None = None


@dataclass
class Candle:
    ts: float
    o: float
    h: float
    l: float
    c: float
    v: float = 0.0


@dataclass
class PriceSeries:
    symbol_id: str
    timeframe: str
    candles: list[Candle]
    quality: DataQuality


@dataclass
class SessionState:
    primary_key: str
    primary_label: str
    local_time_label: str
    utc_time_label: str
    overlaps: list[str] = field(default_factory=list)
