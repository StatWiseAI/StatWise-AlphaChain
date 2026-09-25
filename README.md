# AlphaChain Pro

AlphaChain Pro is a professional Streamlit decision-support application derived from the master's thesis. It upgrades the original prototype into an execution-ready analyst workspace with:

- live multi-asset quotes and candles via Binance and Yahoo Finance,
- thesis-aligned SCM engines: Demand Pressure Score, Risk Buffer Score, and Amplification Risk Index,
- execution-grade plans with entry zone, stop loss, take profit, invalidation, and expiry,
- separate Asian, European, and American session playbooks,
- an explanation layer with confluence mapping,
- a persistent evaluation ledger,
- and an email-ready analyst brief that can be sent to end users.

## Application structure

```
alphachain_python/
  models.py            domain models and data contracts
  config.py            symbols, timeframes, sessions, app constants
  data_layer.py        live quotes/candles with explicit data-quality provenance
  indicators.py        ATR, RSI, FVG, regime, trend, structure analytics
  engines.py           SCM-derived engines (DPS, RBS, ARI)
  decision_engine.py   master signal builder + per-session trade plans
  charting.py          professional candlestick visualization
  reporting.py         email-ready signal summaries
  news_layer.py        thesis-aligned intelligence feed abstraction
  evaluation.py        persistent performance ledger in SQLite
  tests/
app.py                 Streamlit front end
IMPLEMENTATION_GUIDE.md
requirements.txt
```

## Key improvements vs. the prototype

1. **Professional UI** — dark institutional dashboard styling, clearer signal states, better visual hierarchy.
2. **Real market candles for non-crypto assets** — Yahoo Finance replaces the synthetic-first approach whenever available; gold uses the free `GC=F` futures proxy when direct spot history is unavailable.
3. **No-trade logic** — the engine can output `ACTIVE`, `WAIT`, or `NO_TRADE` instead of forcing a buy/sell every time.
4. **Session-specific playbooks** — dedicated Asian, European, and American trading plans.
5. **Email delivery** — every signal can be exported as a structured analyst brief.
6. **Richer provenance** — provider and synthetic fallback are always disclosed in the UI.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment notes

- Works in Streamlit Community Cloud or any Python hosting that supports Streamlit.
- The SQLite track record persists locally; for production multi-user deployment, migrate `evaluation.py` to Postgres.
- The market-intelligence layer is ready for live connectors such as FRED, NY Fed GSCPI, Freightos, Forex Factory, or institutional news feeds.

## Disclaimer

This is a decision-support platform, not financial advice and not an auto-execution system.
