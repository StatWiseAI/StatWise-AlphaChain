from __future__ import annotations

import pandas as pd
import streamlit as st

from alphachain_python.charting import build_price_chart
from alphachain_python.config import APP_NAME, APP_TAGLINE, DB_PATH, HIGHER_TIMEFRAME, LOWER_TIMEFRAME, SYMBOLS, SYMBOL_MAP, TIMEFRAMES, WATCHLIST_TIMEFRAME, get_market_session
from alphachain_python.data_layer import get_candles, get_quote
from alphachain_python.decision_engine import build_signal, position_size
from alphachain_python.evaluation import SignalLedger
from alphachain_python.news_layer import NewsFeed
from alphachain_python.reporting import signal_email_body, signal_email_subject
from alphachain_python.ui_components import badge, inject_theme

st.set_page_config(page_title=APP_NAME, page_icon="📊", layout="wide")
inject_theme()


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


def render_header() -> None:
    session_state = get_market_session()
    st.markdown(f"# {APP_NAME}")
    st.caption(APP_TAGLINE)
    st.markdown(
        badge(session_state.primary_label, "info") + badge(session_state.local_time_label, "good") + badge("Thesis-aligned decision engine", "good"),
        unsafe_allow_html=True,
    )


def render_sidebar():
    st.sidebar.title("Control Tower")
    symbol_index = st.sidebar.selectbox(
        "Instrument",
        options=range(len(SYMBOLS)),
        format_func=lambda idx: f"{SYMBOLS[idx].name} · {SYMBOLS[idx].full}",
        index=0,
    )
    timeframe = st.sidebar.selectbox("Execution timeframe", list(TIMEFRAMES.keys()), index=1)
    account = st.sidebar.number_input("Account size", min_value=1000.0, value=25000.0, step=1000.0)
    risk_pct = st.sidebar.number_input("Risk per trade (%)", min_value=0.1, max_value=5.0, value=1.0, step=0.1)
    st.sidebar.divider()
    if st.sidebar.button("Refresh data"):
        st.cache_data.clear()
        st.rerun()
    return SYMBOLS[symbol_index], timeframe, account, risk_pct


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


def signal_workspace(symbol_cfg, timeframe, account, risk_pct):
    quote, execution, higher, lower, signal = build_signal_package(symbol_cfg, timeframe)
    c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1])
    c1.metric(symbol_cfg.name, fmt(quote.price if quote else signal.entry, symbol_cfg.decimals), f"{quote.change_pct:+.2f}%" if quote else "data pending")
    c2.metric("Signal status", signal.status)
    c3.metric("Confidence", f"{signal.confidence}%")
    c4.metric("Risk / reward", f"1:{signal.risk_reward}")

    st.markdown(
        "".join(
            [
                badge(signal.direction, "good" if signal.direction == "BUY" else "bad"),
                badge(signal.setup_quality, "good" if signal.setup_quality == "High" else "warn" if signal.setup_quality == "Moderate" else "bad"),
                badge(signal.regime, "info"),
                badge(f"HTF {signal.higher_timeframe_bias}", "info"),
                badge(f"LTF {signal.lower_timeframe_bias}", "info"),
                badge(f"Event risk {signal.event_risk}", "warn" if signal.event_risk != "Low" else "good"),
                badge(execution.quality.provider, "warn" if execution.quality.synthetic else "good"),
            ]
        ),
        unsafe_allow_html=True,
    )
    if execution.quality.synthetic:
        st.warning(execution.quality.note)

    st.plotly_chart(build_price_chart(execution.candles, signal, f"{symbol_cfg.name} · {timeframe} execution map"), use_container_width=True)
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Entry zone", f"{fmt(signal.entry_min, symbol_cfg.decimals)} - {fmt(signal.entry_max, symbol_cfg.decimals)}")
    m2.metric("Primary TP", fmt(signal.take_profit, symbol_cfg.decimals))
    m3.metric("Stop loss", fmt(signal.stop_loss, symbol_cfg.decimals))
    m4.metric("Conviction", f"{signal.conviction:.3f}")
    m5.metric("Expiry", f"{signal.expires_in_hours}h")

    st.markdown("### AI rationale")
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
                f"<p><strong>{plan.direction}</strong> · {plan.setup_type.replace('_', ' ')}</p>"
                f"<p class='alpha-muted'>Entry type: {plan.entry_type}</p>"
                f"<p>Entry zone: <strong>{fmt(plan.entry_min, symbol_cfg.decimals)} - {fmt(plan.entry_max, symbol_cfg.decimals)}</strong><br>"
                f"Stop: <strong>{fmt(plan.stop_loss, symbol_cfg.decimals)}</strong><br>"
                f"TP1: <strong>{fmt(plan.take_profit, symbol_cfg.decimals)}</strong><br>"
                f"TP2: <strong>{fmt(plan.secondary_target, symbol_cfg.decimals)}</strong><br>"
                f"Risk / reward: <strong>1:{plan.risk_reward}</strong><br>"
                f"Confidence: <strong>{plan.confidence}%</strong></p>"
                + "".join(f"<p class='alpha-muted'>• {note}</p>" for note in plan.notes)
                + "</div>",
                unsafe_allow_html=True,
            )

    st.markdown("### Position and distribution")
    pos = position_size(account, risk_pct, signal.entry, signal.stop_loss, signal.risk_reward)
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Risk amount", f"${pos['risk_amount']:,.2f}")
    p2.metric("Reward at TP", f"${pos['reward_amount']:,.2f}")
    p3.metric("Units", f"{pos['units']:.4f}")
    p4.metric("Notional", f"${pos['notional']:,.2f}")
    st.caption(f"Invalidation level: {fmt(signal.invalidation_level, symbol_cfg.decimals)} · Decision-support output only, not auto-execution.")

    if st.button("Log current signal"):
        row_id = get_ledger().open_signal(signal, timeframe=timeframe)
        st.success(f"Signal #{row_id} logged to the persistent evaluation ledger.")

    st.markdown("### Email-ready analyst brief")
    session_state = get_market_session()
    subject = signal_email_subject(symbol_cfg, signal)
    body = signal_email_body(symbol_cfg, signal, timeframe, session_state)
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
            "Symbol": symbol.name,
            "Category": symbol.category,
            "Price": fmt(quote.price if quote else signal.entry, symbol.decimals),
            "24h %": f"{quote.change_pct:+.2f}%" if quote else "n/a",
            "Status": signal.status,
            "Direction": signal.direction,
            "Confidence": signal.confidence,
            "R:R": signal.risk_reward,
            "Regime": signal.regime,
            "HTF": signal.higher_timeframe_bias,
            "Provider": execution.quality.provider,
        })
    df = pd.DataFrame(rows).sort_values(["Status", "Confidence"], ascending=[True, False])
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
    st.caption("This package keeps a professional demo intelligence layer that is ready to be replaced by live connectors.")
    items = feed.for_symbol(symbol_cfg.id)
    for item in items:
        st.markdown(f"**{item.source}** · `{item.kind}` · `{item.tag}` · {item.headline}")
        if item.fixed_time:
            st.caption(f"Scheduled time: {item.fixed_time}")
        st.divider()


def main():
    render_header()
    symbol_cfg, timeframe, account, risk_pct = render_sidebar()
    tabs = st.tabs(["Signal Workspace", "Screener", "Track Record", "Market Intelligence"])
    with tabs[0]:
        signal_workspace(symbol_cfg, timeframe, account, risk_pct)
    with tabs[1]:
        screener_tab()
    with tabs[2]:
        track_record_tab()
    with tabs[3]:
        intelligence_tab(symbol_cfg)


if __name__ == "__main__":
    main()
