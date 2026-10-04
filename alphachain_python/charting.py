"""Light-theme professional candlestick chart with decision overlays and live marker."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .decision_engine import Signal
from .models import Candle


def build_price_chart(candles: list[Candle], signal: Signal, title: str, decimals: int = 2, live_note: str | None = None) -> go.Figure:
    df = pd.DataFrame(
        [
            {"ts": pd.to_datetime(c.ts, unit="s"), "open": c.o, "high": c.h, "low": c.l, "close": c.c, "volume": c.v}
            for c in candles
        ]
    )
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=df["ts"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            increasing_line_color="#16A34A",
            decreasing_line_color="#DC2626",
            name="Price",
        )
    )
    for label, value, color, dash in [
        ("Entry mid", signal.entry, "#2563EB", "dot"),
        ("TP1", signal.take_profit, "#059669", "solid"),
        ("Stop", signal.stop_loss, "#DC2626", "solid"),
        ("Support", signal.support, "#94A3B8", "dash"),
        ("Resistance", signal.resistance, "#94A3B8", "dash"),
    ]:
        fig.add_hline(y=value, line_width=1.2, line_dash=dash, line_color=color, annotation_text=label, annotation_position="right", annotation_font_color=color)
    if candles:
        last_close = candles[-1].c
        fig.add_hline(
            y=last_close,
            line_width=1.4,
            line_dash="dot",
            line_color="#0F172A",
            annotation_text=f"Live {last_close:,.{decimals}f}",
            annotation_position="top left",
            annotation_font_color="#0F172A",
        )
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color="#0F172A")),
        height=490,
        template="plotly_white",
        margin=dict(l=12, r=12, t=74, b=12),
        xaxis_rangeslider_visible=False,
        xaxis=dict(
            rangeselector=dict(
                buttons=[
                    dict(count=1, label="1D", step="day", stepmode="backward"),
                    dict(count=3, label="3D", step="day", stepmode="backward"),
                    dict(count=7, label="1W", step="day", stepmode="backward"),
                    dict(count=1, label="1M", step="month", stepmode="backward"),
                    dict(step="all", label="All"),
                ],
                bgcolor="#F1F5F9",
                activecolor="#DBEAFE",
            ),
        ),
        font=dict(color="#0F172A", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
    )
    if live_note:
        fig.add_annotation(
            xref="paper",
            yref="paper",
            x=0,
            y=1.155,
            showarrow=False,
            text=live_note,
            font=dict(size=12, color="#334155"),
            bgcolor="rgba(241,245,249,0.95)",
            bordercolor="#E2E8F0",
            borderpad=5,
            align="left",
        )
    return fig
