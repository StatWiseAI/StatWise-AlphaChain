"""Market data access: real-time quotes first (TradingView / Binance), provenance throughout.

Provider chain
--------------
Quotes  : 1) Binance (crypto)            -> real-time
          2) TradingView scanner endpoint -> real-time, no API key (gold spot via OANDA,
             FX, futures, equities, indices - the same public endpoint the original
             AlphaChain prototype used successfully)
          3) Stooq CSV                    -> fallback quote + independent cross-check
          4) Yahoo Finance                -> last-resort quote (can be delayed)
Candles : 1) Binance klines (crypto)     -> real OHLCV
          2) Yahoo Finance               -> real OHLCV history (e.g. GC=F for gold)
          3) Synthetic-anchored series   -> clearly labelled last resort, anchored to
             the LIVE quote so levels stay realistic

Every Quote carries provider, mapped symbol, timestamp, realtime flag, and (where
configured) an independent cross-check price so the user can verify the live value.
"""
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

TV_SYMBOL_URL = "https://scanner.tradingview.com/symbol"
BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
STOOQ_QUOTE_URL = "https://stooq.com/q/l/"

_thread_local = threading.local()


def _session() -> requests.Session:
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update({"User-Agent": "AlphaChainPro/3.0"})
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


# --------------------------------------------------------------------------- #
# Quotes
# --------------------------------------------------------------------------- #
def fetch_tv_quote(tv_symbol: str, timeout: float = 5.0) -> Optional[tuple[float, float]]:
    """Real-time (last_price, change_pct) from TradingView's public scanner endpoint."""
    try:
        response = _session().get(
            TV_SYMBOL_URL,
            params={"symbol": tv_symbol, "fields": "close,change", "no_404": "true"},
            timeout=timeout,
        )
        if not response.ok:
            return None
        data = response.json()
        last = data.get("close")
        if last is None:
            return None
        return float(last), float(data.get("change") or 0.0)
    except Exception:
        return None


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
        if rows and isinstance(rows[0], dict) and "code" in rows[0]:
            return []  # Binance restriction / error payload
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


def fetch_stooq_quote(ticker: str, timeout: float = 6.0) -> Optional[tuple[float, float, float]]:
    """Independent (close, open, ts) from Stooq's lightweight CSV endpoint."""
    try:
        response = _session().get(
            STOOQ_QUOTE_URL,
            params={"s": ticker.lower(), "f": "sd2t2ohlcv", "h": "", "e": "csv"},
            timeout=timeout,
        )
        if not response.ok:
            return None
        rows = response.text.strip().splitlines()
        if len(rows) < 2:
            return None
        cells = rows[1].split(",")
        if len(cells) < 7:
            return None
        close = float(cells[6])
        open_ = float(cells[3])
        stamp = f"{cells[1]} {cells[2]}" if len(cells) > 2 and cells[2] not in {"", "0"} else cells[1]
        try:
            ts = pd.Timestamp(stamp).timestamp()
        except Exception:
            ts = time.time()
        if close <= 0:
            return None
        return close, open_, ts
    except Exception:
        return None


def _flatten_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    return frame


def fetch_yfinance_quote(yahoo_symbol: str) -> Optional[dict]:
    """Last-resort quote with provenance: quote timestamp, realtime flag, delay note."""
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
                return {
                    "price": price,
                    "change_pct": change,
                    "quote_ts": pd.Timestamp(close.index[-1]).timestamp(),
                    "realtime": False,
                    "delay_note": "Yahoo quote may be delayed up to 15 minutes.",
                }
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
        return {
            "price": price,
            "change_pct": change,
            "quote_ts": pd.Timestamp(closes.index[-1]).timestamp(),
            "realtime": False,
            "delay_note": "Market closed - showing the last official close, not a ticking price.",
        }
    except Exception:
        return None


def _finish_quote(symbol_cfg: SymbolConfig, price: float, change_pct: float, provider: str,
                  provider_symbol: str, realtime: bool, delay_note: str | None) -> Quote:
    quote = Quote(
        symbol_id=symbol_cfg.id,
        price=price,
        change_pct=change_pct,
        ts=time.time(),
        provider=provider,
        provider_symbol=provider_symbol,
        quote_ts=time.time() if realtime else None,
        is_realtime=realtime,
        delay_note=delay_note,
    )
    if quote.quote_ts is None:
        quote.quote_ts = time.time()
    # Independent cross-check where a Stooq symbol is configured.
    if symbol_cfg.stooq:
        cross = fetch_stooq_quote(symbol_cfg.stooq)
        if cross is not None:
            cross_price, _open, cross_ts = cross
            quote.cross_source = f"Stooq {symbol_cfg.stooq.upper()}"
            quote.cross_price = cross_price
            quote.cross_ts = cross_ts
    return quote


def get_quote(symbol_cfg: SymbolConfig) -> Optional[Quote]:
    """Real-time quote through the provider chain, with full provenance."""
    # 1) Crypto: Binance real-time; TradingView as regional fallback.
    if symbol_cfg.binance:
        payload = fetch_binance_quote(symbol_cfg.binance)
        if payload is not None:
            price, change = payload
            return _finish_quote(symbol_cfg, price, change, "Binance", symbol_cfg.binance, True, None)
    # 2) TradingView public scanner - real-time across all asset classes.
    if symbol_cfg.tradingview:
        payload = fetch_tv_quote(symbol_cfg.tradingview)
        if payload is not None:
            price, change = payload
            return _finish_quote(symbol_cfg, price, change, "TradingView", symbol_cfg.tradingview, True, None)
    # 3) Stooq.
    if symbol_cfg.stooq:
        cross = fetch_stooq_quote(symbol_cfg.stooq)
        if cross is not None:
            close, open_, ts = cross
            change = ((close - open_) / open_ * 100) if open_ else 0.0
            quote = _finish_quote(symbol_cfg, close, change, "Stooq", symbol_cfg.stooq.upper(), False,
                                  "Stooq quote (delayed/official close).")
            quote.quote_ts = ts
            quote.cross_source = None
            quote.cross_price = None
            return quote
    # 4) Yahoo Finance last resort.
    payload = fetch_yfinance_quote(symbol_cfg.yahoo or "")
    if payload is None:
        return None
    return _finish_quote(
        symbol_cfg,
        payload["price"],
        payload["change_pct"],
        "Yahoo Finance",
        symbol_cfg.yahoo,
        payload["realtime"],
        payload["delay_note"],
    )


# --------------------------------------------------------------------------- #
# Candles
# --------------------------------------------------------------------------- #
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
            note="Candle history unavailable; synthetic series anchored to the LIVE quote - levels are demonstrative.",
            last_updated_ts=time.time(),
        ),
    )


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