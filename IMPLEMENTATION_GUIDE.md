# AlphaChain Pro — Implementation Guide

## 1. Purpose

This package turns the original prototype into a professional decision-support application for discretionary traders, market analysts, and AI-assisted research workflows.

It is designed to:

- operationalise the AlphaChain framework architecture,
- provide actionable trade plans instead of raw directional bias,
- separate execution logic by Asian, European, and American sessions,
- and generate a client-ready summary that can be sent by email.

## 2. What is included

### Core modules

- `alphachain_python/models.py` — domain contracts for symbols, sessions, candles, and data quality.
- `alphachain_python/config.py` — instrument universe, timeframes, session definitions, and runtime constants.
- `alphachain_python/data_layer.py` — live market data via Binance and Yahoo Finance with explicit fallback handling. For gold, the free feed uses the `GC=F` futures proxy.
- `alphachain_python/engines.py` — framework engines:
  - Demand Pressure Score
  - Risk Buffer Score
  - Amplification Risk Index
- `alphachain_python/decision_engine.py` — signal orchestration, gating, session plans, and execution geometry.
- `alphachain_python/charting.py` — professional candlestick view with entry, TP, SL, support, and resistance overlays.
- `alphachain_python/reporting.py` — email-ready subject and body generation.
- `alphachain_python/evaluation.py` — persistent signal ledger and metrics.
- `app.py` — production-style Streamlit workspace.

## 3. Functional design

The app follows the framework architecture strictly:

1. **Data Layer**
   - retrieves quotes and candles,
   - discloses the provider,
   - falls back to synthetic candles only when live history is unavailable.

2. **Supply Chain Intelligence Layer**
   - computes demand pressure,
   - sizes the risk buffer,
   - detects amplification or overreaction.

3. **Decision Engine**
   - creates a trade plan,
   - gates weak setups,
   - returns `ACTIVE`, `WAIT`, or `NO_TRADE`,
   - prepares separate session-specific plans.

4. **AI Explanation Layer**
   - generates transparent rationale,
   - exposes confluence checks,
   - exports an email briefing.

## 4. Session logic

### Asian session
- Lower volatility bias.
- Best suited to range retests and patient entries.
- Avoid chasing weak breakouts.

### European session
- Stronger trend initiation and cleaner breakout/pullback structures.
- Best session for directional continuation if higher timeframe bias aligns.

### American session
- Highest event sensitivity.
- Wider stops and confirmation-first posture.
- Better suited to post-release continuation rather than pre-release guessing.

## 5. How to run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 6. How to deploy professionally

### Recommended immediate deployment
- Streamlit Community Cloud for demonstration.
- Railway / Render / Azure App Service for persistent hosting.

### Recommended production hardening
1. Replace SQLite with Postgres.
2. Add authenticated user accounts.
3. Replace demo intelligence feed with live connectors:
   - FRED
   - NY Fed GSCPI
   - Freightos / Drewry
   - economic-calendar feed
   - Reuters / Bloomberg / institutional news API
4. Add broker or execution API only after signal validation.
5. Add benchmark and walk-forward evaluation.

## 7. Email workflow

The app now generates an analyst brief in plain text. The intended workflow is:

1. Analyst reviews signal.
2. Analyst copies or downloads the text brief.
3. Brief is sent to end users via email or CRM.

For full email automation, add SMTP / Microsoft Graph / Gmail API credentials in a separate secure module.

## 8. Limitations to address next

1. News/event feed is still a structured professional placeholder layer, not yet a live institutional feed.
2. Supply chain macro series are architected for integration but not yet wired into the scoring engine.
3. Historical backtest and walk-forward framework should be added before any production capital allocation.

## 9. Recommended next build phase

If you want the next version to be genuinely institutional-grade, the next engineering sprint should add:

- FRED + GSCPI ingestion,
- Freightos / Drewry / Baltic Dry data,
- benchmark reporting,
- user authentication,
- email/API automation,
- and a server-side database.

## 10. Framework alignment summary

This package keeps the central contribution of the framework intact:

- SCM concepts are translated into market decision-support modules.
- Signals remain explainable.
- Risk is handled as a structured buffer, not intuition.
- Session-specific execution guidance improves direct usability for traders.
