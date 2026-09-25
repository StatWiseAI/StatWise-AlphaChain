"""Market-intelligence feed used by the explanation layer and session risk overlay."""
from __future__ import annotations

import itertools
import threading
import time
from dataclasses import dataclass, field


@dataclass
class NewsItem:
    source: str
    kind: str
    symbol: str
    headline: str
    tag: str
    ts: float = field(default_factory=time.time)
    fixed_time: str | None = None


_SEED = [
    NewsItem("Macro Calendar", "Event", "USD", "US labour-market release due during New York cash open", "High", fixed_time="12:30 UTC"),
    NewsItem("Supply Chain Intel", "News", "XAUUSD", "Shipping and input-cost stress remains supportive for safe-haven demand", "Bullish"),
    NewsItem("Energy Watch", "News", "WTIUSD", "Middle East freight disruptions keep crude risk premium elevated", "Bullish"),
    NewsItem("FX Desk", "Social", "EURUSD", "EUR/USD holding value area ahead of London participation", "Neutral"),
    NewsItem("Crypto Flow", "News", "BTCUSD", "BTC liquidity improves into US hours after subdued Asian trade", "Bullish"),
    NewsItem("Equity Tape", "News", "NVDA", "Semiconductor momentum remains strong but valuation-sensitive into macro prints", "Neutral"),
]

_POOL = [
    NewsItem("Supply Chain Intel", "News", "XAUUSD", "Freight stress index remains firm, sustaining defensive allocation narratives", "Bullish"),
    NewsItem("Macro Calendar", "Event", "USD", "Fed speaker scheduled during the American session", "High"),
    NewsItem("Cross-Asset Flow", "News", "EURUSD", "Dollar flows fade after the European open; watch London fix reaction", "Neutral"),
    NewsItem("Energy Watch", "News", "WTIUSD", "Inventory expectations keep US energy complex sensitive into New York", "Med"),
    NewsItem("Equity Tape", "Social", "AAPL", "AAPL order-flow still positive but late-session momentum is cooling", "Neutral"),
]


class NewsFeed:
    def __init__(self):
        self._lock = threading.Lock()
        self.items: list[NewsItem] = list(_SEED)
        self._pool_cycle = itertools.cycle(_POOL)

    def refresh(self) -> NewsItem:
        with self._lock:
            item = next(self._pool_cycle)
            fresh = NewsItem(item.source, item.kind, item.symbol, item.headline, item.tag, ts=time.time(), fixed_time=item.fixed_time)
            self.items.insert(0, fresh)
            self.items = self.items[:40]
            return fresh

    def for_symbol(self, symbol_id: str) -> list[NewsItem]:
        with self._lock:
            return [item for item in self.items if item.symbol in (symbol_id, "USD")]

    def sorted_by_recency(self) -> list[NewsItem]:
        with self._lock:
            return sorted(self.items, key=lambda item: 0 if item.fixed_time else -item.ts)

    def bias_for_symbol(self, symbol_id: str) -> str:
        relevant = self.for_symbol(symbol_id)
        if any(item.tag == "High" for item in relevant[:4]):
            return "High"
        if any(item.tag in {"Bullish", "Bearish", "Med"} for item in relevant[:4]):
            return "Medium"
        return "Low"
