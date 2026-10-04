from __future__ import annotations

import time
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from alphachain_python.charting import build_price_chart
from alphachain_python.config import (
    APP_NAME,
    APP_TAGLINE,
    DB_PATH,
    HIGHER_TIMEFRAME,
    LOWER_TIMEFRAME,
    SYMBOLS,
    SYMBOL_MAP,
    TIMEFRAMES,
    WATCHLIST_TIMEFRAME,
    get_market_session,
)
from alphachain_python.data_layer import get_candles, get_quote
from alphachain_python.decision_engine import build_signal, position_size
from alphachain_python.evaluation import SignalLedger
from alphachain_python.news_layer import NewsFeed
from alphachain_python.reporting import signal_email_body, signal_email_subject
from alphachain_python.ui_components import badge, gate_row, inject_theme, live_pill, verdict_card

st.set_page_config(page_title=APP_NAME, page_icon="📈", layout="wide")
inject_theme()

VERDICT_SORT = {"ENTER LONG": 0, "ENTER SHORT": 0, "WAIT": 1, "NO TRADE": 2}


@st.cache_resource
def get_ledger() -> SignalLedger:
    return SignalLedger(DB_PATH)


@st.cache_resource
def get_news() -> NewsFeed:
    return NewsFeed()


@st.cache_data(ttl=30)
def cached_quote(symbol_id: str):
    return get_quote(SYMBOL_MAP[symbol_id])


@st.cache_data(ttl=120)
def cached_series(symbol_id: str, timeframe: str, anchor_price: float):
    return get_candles(SYMBOL_MAP[symbol_id], anchor_price=anchor_price, timeframe=timeframe)


def fmt(value: float, decimals: int) -> str:
    return f"{value:,.{decimals}f}"


def utc_stamp(ts: float | None) -> str:
    if not ts:
        return "-"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S UTC")


def freshness(quote) -> tuple[str, str]:
    if quote is None:
        return "stale", "no live quote - use Refresh data in the sidebar"
    ref = quote.quote_ts or quote.ts
    age = time.time() - ref
    stamp = utc_stamp(ref)
    if quote.is_realtime and age <= 300:
        return "live", f"LIVE - {quote.provider} - {stamp}"
    if age <= 1800:
        return "delayed", f"DELAYED - {quote.provider} - {stamp}"
    return "stale", f"OFF-SESSION - last official data {stamp}"


def render_header() -> None:
    session_state = get_market_session()
    st.markdown(f"# {APP_NAME}")
    st.caption(APP_TAGLINE)
    st.markdown(
        badge(session_state.primary_label, "info")
        + badge(session_state.local_time_label, "neutral")
        + badge("SCM-derived decision engine", "good")
        + badge("Decision support - not auto-execution", "warn"),
        unsafe_allow_html=True,
    )


def render_sidebar():
    st.sidebar.title("Control Tower")
    symbol_index = st.sidebar.selectbox(
        "Instrument",
        options=range(len(SYMBOLS)),
        format_func=lambda idx: f"{SYMBOLS[idx].name} - {SYMBOLS[idx].full}",
        index=0,
    )
    timeframe = st.sidebar.selectbox("Execution timeframe", list(TIMEFRAMES.keys()), index=1)
    account = st.sidebar.number_input("Account size", min_value=1000.0, value=25000.0, step=1000.0)
    risk_pct = st.sidebar.number_input("Risk per trade (%)", min_value=0.1, max_value=5.0, value=1.0, step=0.1)
    auto_live = st.sidebar.toggle("Live price updates every 30 s", value=True)
    st.sidebar.divider()

    symbol_cfg = SYMBOLS[symbol_index]
    with st.sidebar.expander("Market data provenance", expanded=True):
        quote = cached_quote(symbol_cfg.id)
        state, label = freshness(quote)
        st.markdown(live_pill(state, label), unsafe_allow_html=True)
        if quote:
            st.caption(f"Primary feed: {quote.provider} ({quote.provider_symbol})")
            if quote.delay_note:
                st.caption(quote.delay_note)
            if quote.cross_price:
                basis = (quote.price - quote.cross_price) / quote.cross_price * 100
                st.caption(
                    f"Independent cross-check - {quote.cross_source}: "
                    f"{fmt(quote.cross_price, symbol_cfg.decimals)} (basis {basis:+.2f}%)"
                )
        else:
            st.caption("No quote returned - check connectivity or press Refresh data.")

    if st.sidebar.button("Refresh data"):
        st.cache_data.clear()
        st.rerun()
    return symbol_cfg, timeframe, account, risk_pct, auto_live


def _quote_strip(symbol_cfg) -> None:
    quote = cached_quote(symbol_cfg.id)
    state, label = freshness(quote)
    cols = st.columns([1.0, 2.0, 1.4])
    with cols[0]:
        if quote:
            st.metric(f"{symbol_cfg.name} live", fmt(quote.price, symbol_cfg.decimals), f"{quote.change_pct:+.2f}%")
        else:
            st.metric(f"{symbol_cfg.name} live", "n/a")
    with cols[1]:
        st.markdown(live_pill(state, label), unsafe_allow_html=True)
        if quote:
            st.caption(f"Primary: {quote.provider} ({quote.provider_symbol})")
            if quote.delay_note:
                st.caption(quote.delay_note)
    with cols[2]:
        if quote and quote.cross_price:
            basis = (quote.price - quote.cross_price) / quote.cross_price * 100
            st.metric("Cross-check (Stooq)", fmt(quote.cross_price, symbol_cfg.decimals), f"basis {basis:+.2f}%")
        else:
            st.caption("No independent cross-check configured for this instrument.")


if hasattr(st, "fragment"):
    _quote_strip_fragment = st.fragment(run_every="30s")(_quote_strip)


def quote_strip(symbol_cfg, auto_live: bool) -> None:
    if auto_live and hasattr(st, "fragment"):
        _quote_strip_fragment(symbol_cfg)
    else:
        _quote_strip(symbol_cfg)


def build_signal_package(symbol_cfg, timeframe: str):
    quote = cached_quote(symbol_cfg.id)
    anchor = quote.price if quote else 100.0
    execution = cached_series(symbol_cfg.id, timeframe, anchor)
    higher = cached_series(symbol_cfg.id, HIGHER_TIMEFRAME[timeframe], anchor)
    lower = cached_series(symbol_cfg.id, LOWER_TIMEFRAME[timeframe], anchor)
    feed = get_news()
    signal = build_signal(
        symbol_cfg=symbol_cfg,
        candles=execution.candles,
        live_price=quote.price if quote else execution.candles[-1].c,
        data_quality=execution.quality,
        session_state=get_market_session(),
        higher_timeframe_candles=higher.candles,
        lower_timeframe_candles=lower.candles,
        news_bias=feed.bias_for_symbol(symbol_cfg.id),
    )
    return quote, execution, higher, lower, signal


def signal_workspace(symbol_cfg, timeframe, account, risk_pct, auto_live):
    quote, execution, higher, lower, signal = build_signal_package(symbol_cfg, timeframe)

    # 1) Live price strip (auto-refreshing when enabled).
    quote_strip(symbol_cfg, auto_live)

    # 2) The verdict - one unambiguous call to action.
    meta = f"{signal.confidence}% confidence - {signal.current_session_label} - horizon {signal.expires_in_hours} h - data: {execution.quality.provider}"
    st.markdown(verdict_card(signal.verdict, signal.verdict_reason, meta), unsafe_allow_html=True)

    # 3) Trade geometry.
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Entry zone", f"{fmt(signal.entry_min, symbol_cfg.decimals)} - {fmt(signal.entry_max, symbol_cfg.decimals)}")
    m2.metric("Stop loss", fmt(signal.stop_loss, symbol_cfg.decimals))
    m3.metric("Target 1", fmt(signal.take_profit, symbol_cfg.decimals))
    m4.metric("Target 2", fmt(signal.tp2, symbol_cfg.decimals) if signal.tp2 else "-")
    m5.metric("Reward : risk", f"1 : {signal.risk_reward}")
    m6.metric("Conviction", f"{signal.conviction:.2f}")

    # 4) Chart with decision overlays and live marker.
    live_note = None
    if quote:
        live_note = f"{quote.provider} ({quote.provider_symbol}) - as of {utc_stamp(quote.quote_ts or quote.ts)} UTC"
    st.plotly_chart(
        build_price_chart(execution.candles, signal, f"{symbol_cfg.name} - {timeframe} execution map", decimals=symbol_cfg.decimals, live_note=live_note),
        use_container_width=True,
    )
    if execution.quality.synthetic:
        st.warning(execution.quality.note)

    # 5) The entry checklist - when do I actually trade?
    st.markdown("### Entry checklist")
    st.caption("The verdict above is generated from exactly these conditions. Enter only when every row passes; otherwise stay flat and re-check later.")
    st.markdown("".join(gate_row(g.name, g.passed, g.detail) for g in signal.gates), unsafe_allow_html=True)
    passed = sum(1 for g in signal.gates if g.passed)
    tone = "good" if passed == len(signal.gates) else "bad" if passed < len(signal.gates) - 2 else "warn"
    st.markdown(badge(f"{passed}/{len(signal.gates)} conditions met", tone), unsafe_allow_html=True)

    # 6) Execution plan - what to do, step by step.
    st.markdown("### Execution plan")
    for idx, step in enumerate(signal.entry_instructions, start=1):
        st.markdown(f"**{idx}.** {step}")

    # 7) AI rationale (explanation layer).
    st.markdown("### Why this signal - AI rationale")
    for reason in signal.reasons:
        st.write(f"- {reason}")

    st.markdown("### Confluence map")
    cols = st.columns(len(signal.confluence))
    for col, item in zip(cols, signal.confluence):
        with col:
            st.markdown(badge(item.name, "good" if item.ok else "warn"), unsafe_allow_html=True)
            st.caption(item.note)

    st.markdown("### Session playbook")
    cols = st.columns(3)
    for col, plan in zip(cols, signal.session_plans):
        with col:
            tone = "good" if plan.status == "ACTIVE" else "warn" if plan.status == "WAIT" else "bad"
            st.markdown(
                f"<div class='alpha-card'>{badge(plan.session_label, 'info')}{badge(plan.status, tone)}"
                f"<p><strong>{plan.direction}</strong> - {plan.setup_type.replace('_', ' ')}</p>"
                f"<p class='alpha-muted'>Entry type: {plan.entry_type}</p>"
                f"<p>Entry zone: <strong>{fmt(plan.entry_min, symbol_cfg.decimals)} - {fmt(plan.entry_max, symbol_cfg.decimals)}</strong><br>"
                f"Stop: <strong>{fmt(plan.stop_loss, symbol_cfg.decimals)}</strong><br>"
                f"TP1: <strong>{fmt(plan.take_profit, symbol_cfg.decimals)}</strong><br>"
                f"TP2: <strong>{fmt(plan.secondary_target, symbol_cfg.decimals)}</strong><br>"
                f"Risk / reward: <strong>1:{plan.risk_reward}</strong><br>"
                f"Confidence: <strong>{plan.confidence}%</strong></p>"
                + "".join(f"<p class='alpha-muted'>- {note}</p>" for note in plan.notes)
                + "</div>",
                unsafe_allow_html=True,
            )

    st.markdown("### Position and distribution")
    pos = position_size(account, risk_pct, signal.entry, signal.stop_loss, signal.risk_reward)
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Risk amount", f"${pos['risk_amount']:,.2f}")
    p2.metric("Reward at TP1", f"${pos['reward_amount']:,.2f}")
    p3.metric("Units", f"{pos['units']:.4f}")
    p4.metric("Notional", f"${pos['notional']:,.2f}")
    st.caption(f"Invalidation level: {fmt(signal.invalidation_level, symbol_cfg.decimals)} - Decision-support output only, not auto-execution.")

    if st.button("Log current signal"):
        row_id = get_ledger().open_signal(signal, timeframe=timeframe)
        st.success(f"Signal #{row_id} logged to the persistent evaluation ledger.")

    st.markdown("### Email-ready analyst brief")
    subject = signal_email_subject(symbol_cfg, signal)
    body = signal_email_body(symbol_cfg, signal, timeframe, get_market_session())
    st.text_input("Subject", value=subject)
    st.text_area("Body", value=body, height=320)
    st.download_button("Download analyst brief (.txt)", body, file_name=f"{symbol_cfg.id.lower()}_signal_brief.txt")


def screener_tab():
    rows = []
    for symbol in SYMBOLS:
        quote = cached_quote(symbol.id)
        anchor = quote.price if quote else 100.0
        execution = cached_series(symbol.id, WATCHLIST_TIMEFRAME, anchor)
        higher = cached_series(symbol.id, HIGHER_TIMEFRAME[WATCHLIST_TIMEFRAME], anchor)
        lower = cached_series(symbol.id, LOWER_TIMEFRAME[WATCHLIST_TIMEFRAME], anchor)
        signal = build_signal(
            symbol_cfg=symbol,
            candles=execution.candles,
            live_price=quote.price if quote else execution.candles[-1].c,
            data_quality=execution.quality,
            session_state=get_market_session(),
            higher_timeframe_candles=higher.candles,
            lower_timeframe_candles=lower.candles,
            news_bias=get_news().bias_for_symbol(symbol.id),
        )
        rows.append({
            "Instrument": symbol.name,
            "Category": symbol.category,
            "Price": fmt(quote.price if quote else signal.entry, symbol.decimals),
            "24h %": f"{quote.change_pct:+.2f}%" if quote else "n/a",
            "Verdict": signal.verdict,
            "Direction": signal.direction,
            "Confidence": signal.confidence,
            "R:R": signal.risk_reward,
            "Regime": signal.regime,
            "Higher TF": signal.higher_timeframe_bias,
            "Data": execution.quality.provider,
        })
    df = pd.DataFrame(rows)
    df["_sort"] = df["Verdict"].map(lambda v: VERDICT_SORT.get(v, 3))
    df = df.sort_values(["_sort", "Confidence"], ascending=[True, False]).drop(columns=["_sort"])
    st.dataframe(df, use_container_width=True, hide_index=True)


def track_record_tab():
    ledger = get_ledger()
    summary = ledger.summary()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Closed", summary.total_closed)
    c2.metric("Open", summary.total_open)
    c3.metric("Win rate", f"{summary.win_rate_pct}%")
    c4.metric("Avg R", f"{summary.avg_r:+.2f}R")
    c5.metric("Profit factor", f"{summary.profit_factor}")

    by_market = ledger.win_rate_by_market()
    if by_market:
        st.markdown("#### Win rate by market")
        st.dataframe(pd.DataFrame(by_market), use_container_width=True, hide_index=True)

    open_positions = ledger.open_positions()
    if open_positions:
        st.markdown("#### Open positions")
        open_df = pd.DataFrame(open_positions, columns=["Symbol", "Timeframe", "Session", "Direction", "Entry", "TP", "SL", "Confidence", "Opened"])
        open_df["Opened"] = pd.to_datetime(open_df["Opened"], unit="s")
        st.dataframe(open_df, use_container_width=True, hide_index=True)

    history = ledger.recent_history(limit=150)
    if history:
        st.markdown("#### Signal history")
        hist_df = pd.DataFrame(history, columns=["Symbol", "Timeframe", "Session", "Direction", "Status", "Entry", "TP", "SL", "Outcome", "R", "Confidence", "Opened"])
        hist_df["Opened"] = pd.to_datetime(hist_df["Opened"], unit="s")
        st.dataframe(hist_df, use_container_width=True, hide_index=True)


def intelligence_tab(symbol_cfg):
    feed = get_news()
    st.markdown("### Market intelligence")
    st.caption("Professional demo intelligence layer, ready to be replaced by live connectors (FRED, NY Fed GSCPI, freight indices, event calendars).")
    items = feed.for_symbol(symbol_cfg.id)
    for item in items:
        st.markdown(f"**{item.source}** - `{item.kind}` - `{item.tag}` - {item.headline}")
        if item.fixed_time:
            st.caption(f"Scheduled time: {item.fixed_time}")
        st.divider()


def main():
    render_header()
    symbol_cfg, timeframe, account, risk_pct, auto_live = render_sidebar()
    tabs = st.tabs(["Decision Desk", "Watchlist Screener", "Track Record", "Market Intelligence"])
    with tabs[0]:
        signal_workspace(symbol_cfg, timeframe, account, risk_pct, auto_live)
    with tabs[1]:
        screener_tab()
    with tabs[2]:
        track_record_tab()
    with tabs[3]:
        intelligence_tab(symbol_cfg)


if __name__ == "__main__":
    main()
