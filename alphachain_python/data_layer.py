"""Market data access with explicit provenance and fallbacks."""
from __future__ import annotations

import random
import threading
import time
from typing import Optional

import pandas as pd
import requests
import yfinance as yf

from .config import TIMEFRAMES
from .models import Candle, DataQuality, PriceSeries, Quote, SymbolConfig

BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"

_thread_local = threading.local()


def _session() -> requests.Session:
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update({"User-Agent": "AlphaChainPro/2.0"})
        _thread_local.session = session
    return session


def _frame_to_candles(frame: pd.DataFrame, limit: int, symbol_id: str, timeframe: str, provider: str) -> PriceSeries | None:
    if frame is None or frame.empty:
        return None
    frame = frame.reset_index()
    time_col = "Datetime" if "Datetime" in frame.columns else "Date"
    candles: list[Candle] = []
    for _, row in frame.tail(limit).iterrows():
        candles.append(
            Candle(
                ts=pd.Timestamp(row[time_col]).timestamp(),
                o=float(row["Open"]),
                h=float(row["High"]),
                l=float(row["Low"]),
                c=float(row["Close"]),
                v=float(row.get("Volume", 0.0) or 0.0),
            )
        )
    return PriceSeries(
        symbol_id=symbol_id,
        timeframe=timeframe,
        candles=candles,
        quality=DataQuality(provider=provider, synthetic=False, note="Live market candles", last_updated_ts=time.time()),
    )


def fetch_binance_quote(pair: str, timeout: float = 5.0) -> Optional[tuple[float, float]]:
    try:
        response = _session().get(BINANCE_TICKER_URL, params={"symbol": pair}, timeout=timeout)
        if not response.ok:
            return None
        payload = response.json()
        return float(payload["lastPrice"]), float(payload["priceChangePercent"])
    except Exception:
        return None


def fetch_binance_klines(pair: str, interval: str, limit: int, timeout: float = 6.0) -> list[Candle]:
    try:
        response = _session().get(
            BINANCE_KLINES_URL,
            params={"symbol": pair, "interval": interval, "limit": limit},
            timeout=timeout,
        )
        if not response.ok:
            return []
        rows = response.json()
        return [
            Candle(
                ts=float(k[0]) / 1000.0,
                o=float(k[1]),
                h=float(k[2]),
                l=float(k[3]),
                c=float(k[4]),
                v=float(k[5]),
            )
            for k in rows
        ]
    except Exception:
        return []


def _flatten_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    return frame


def fetch_yfinance_quote(yahoo_symbol: str) -> Optional[tuple[float, float]]:
    try:
        intraday = _flatten_columns(
            yf.download(
                tickers=yahoo_symbol,
                period="1d",
                interval="1m",
                auto_adjust=False,
                progress=False,
                prepost=True,
                threads=False,
            )
        )
        if intraday is not None and not intraday.empty:
            close = intraday["Close"].dropna()
            open_ = intraday["Open"].dropna()
            if not close.empty and not open_.empty:
                price = float(close.iloc[-1])
                day_open = float(open_.iloc[0])
                change = ((price - day_open) / day_open * 100) if day_open else 0.0
                return price, change
        daily = _flatten_columns(
            yf.download(
                tickers=yahoo_symbol,
                period="5d",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
            )
        )
        if daily is None or daily.empty:
            return None
        closes = daily["Close"].dropna()
        price = float(closes.iloc[-1])
        prev = float(closes.iloc[-2]) if len(closes) > 1 else price
        change = ((price - prev) / prev * 100) if prev else 0.0
        return price, change
    except Exception:
        return None


def fetch_yfinance_candles(symbol_cfg: SymbolConfig, timeframe: str) -> PriceSeries | None:
    tf = TIMEFRAMES[timeframe]
    if not symbol_cfg.yahoo:
        return None
    try:
        frame = _flatten_columns(
            yf.download(
                tickers=symbol_cfg.yahoo,
                period=tf.yahoo_period,
                interval=tf.yahoo_interval,
                auto_adjust=False,
                progress=False,
                prepost=True,
                threads=False,
            )
        )
        return _frame_to_candles(frame, tf.bars, symbol_cfg.id, timeframe, "Yahoo Finance")
    except Exception:
        return None


def get_quote(symbol_cfg: SymbolConfig) -> Optional[Quote]:
    if symbol_cfg.binance:
        payload = fetch_binance_quote(symbol_cfg.binance)
        provider = "Binance"
    else:
        payload = fetch_yfinance_quote(symbol_cfg.yahoo or "")
        provider = "Yahoo Finance"
    if payload is None:
        return None
    price, change = payload
    return Quote(symbol_id=symbol_cfg.id, price=price, change_pct=change, ts=time.time(), provider=provider)


def synth_candles(anchor_price: float, volatility: float, n: int = 120, seed: Optional[int] = None) -> list[Candle]:
    rng = random.Random(seed or int(anchor_price * 10000) % 2_147_483_647)
    series: list[Candle] = []
    price = anchor_price * (1 - volatility * max(n / 18, 1))
    ts = time.time() - n * 300
    for _ in range(n):
        o = price
        drift = (rng.random() - 0.48) * 2 * volatility
        c = max(0.0001, o * (1 + drift))
        h = max(o, c) * (1 + rng.random() * volatility * 0.7)
        l = min(o, c) * (1 - rng.random() * volatility * 0.7)
        series.append(Candle(ts=ts, o=o, h=h, l=l, c=c, v=abs(h - l) * 1000))
        ts += 300
        price = c
    series[-1] = Candle(ts=series[-1].ts, o=series[-1].o, h=max(series[-1].h, anchor_price), l=min(series[-1].l, anchor_price), c=anchor_price, v=series[-1].v)
    return series


def get_candles(symbol_cfg: SymbolConfig, anchor_price: float, timeframe: str = "15m") -> PriceSeries:
    tf = TIMEFRAMES[timeframe]
    if symbol_cfg.binance:
        candles = fetch_binance_klines(symbol_cfg.binance, tf.binance_interval, tf.bars)
        if candles:
            return PriceSeries(
                symbol_id=symbol_cfg.id,
                timeframe=timeframe,
                candles=candles,
                quality=DataQuality(provider="Binance", synthetic=False, note="Live market candles", last_updated_ts=time.time()),
            )
    yf_series = fetch_yfinance_candles(symbol_cfg, timeframe)
    if yf_series is not None and yf_series.candles:
        return yf_series
    fallback_price = anchor_price or 100.0
    return PriceSeries(
        symbol_id=symbol_cfg.id,
        timeframe=timeframe,
        candles=synth_candles(fallback_price, symbol_cfg.fallback_volatility, tf.bars),
        quality=DataQuality(
            provider="Synthetic fallback",
            synthetic=True,
            note="Provider unavailable; technical levels are demonstrative until a live feed returns.",
            last_updated_ts=time.time(),
        ),
    )
