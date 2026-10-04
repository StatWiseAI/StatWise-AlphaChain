# AlphaChain Pro

Professional decision-support workspace for discretionary traders, analysts, and research desks. AlphaChain Pro converts supply-chain intelligence (demand pressure, risk buffering, amplification) plus market structure into one clear, explainable verdict per instrument.

## What makes it decision-oriented

- **One verdict, no guesswork** - ENTER LONG / ENTER SHORT / WAIT / NO TRADE, each with a one-sentence reason and an expiry.
- **Entry checklist** - seven explicit conditions (demand pressure, amplification, reward-to-risk, confidence, higher-timeframe alignment, event risk, data quality). The verdict passes only when every condition passes, so it is always clear *when* to trade and when to stay flat.
- **Execution plan** - numbered steps: entry zone, protective stop, partial profit at TP1, stop-to-entry rule, trailing to TP2, order expiry, and position sizing.
- **Position calculator** - account size and risk % translate the plan into concrete units, risk amount, and notional.

## Data you can trust - and verify

- Every quote shows its **provider, symbol mapping, quote timestamp, and freshness** (LIVE / DELAYED / OFF-SESSION).
- Gold is quoted via COMEX futures (`GC=F`) with an **independent Stooq spot cross-check** and the futures basis, so the live value can be verified against a second source at a glance.
- Optional 30-second live refresh of the price strip; everything else updates on interaction or via *Refresh data*.

## Architecture

```
alphachain_python/
  models.py            domain models and data contracts
  config.py            instruments, timeframes, sessions, app constants
  data_layer.py        live quotes/candles with provenance, freshness, and cross-check
  indicators.py        ATR, RSI, FVG, regime, trend, structure analytics
  engines.py           SCM-derived engines (DPS, RBS, ARI)
  decision_engine.py   verdict, entry checklist, trade geometry, session plans
  charting.py          light-theme candlestick chart with decision overlays
  reporting.py         email-ready signal summaries
  news_layer.py        intelligence feed abstraction
  evaluation.py        persistent performance ledger (SQLite)
  tests/
app.py                 Streamlit front end (Decision Desk / Screener / Track Record / Intelligence)
IMPLEMENTATION_GUIDE.md
requirements.txt
```

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment notes

- Runs on Streamlit Community Cloud or any Python host that supports Streamlit (>= 1.39 for the live-refresh fragment).
- The SQLite track record persists locally; migrate `evaluation.py` to Postgres for multi-user production.
- The intelligence layer is ready for live connectors: FRED, NY Fed GSCPI, Freightos/Drewry, event calendars.

## Disclaimer

This is decision-support software, not financial advice and not an auto-execution system.
