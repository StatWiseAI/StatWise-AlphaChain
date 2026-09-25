from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .decision_engine import Signal
from .models import Candle


def build_price_chart(candles: list[Candle], signal: Signal, title: str) -> go.Figure:
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
            increasing_line_color="#2dd4bf",
            decreasing_line_color="#f87171",
            name="Price",
        )
    )
    for label, value, color, dash in [
        ("Entry", signal.entry, "#60a5fa", "dot"),
        ("TP", signal.take_profit, "#34d399", "solid"),
        ("SL", signal.stop_loss, "#f97316", "solid"),
        ("Support", signal.support, "#64748b", "dash"),
        ("Resistance", signal.resistance, "#64748b", "dash"),
    ]:
        fig.add_hline(y=value, line_width=1.2, line_dash=dash, line_color=color, annotation_text=label, annotation_position="right")
    fig.update_layout(
        title=title,
        height=460,
        template="plotly_dark",
        margin=dict(l=12, r=12, t=48, b=12),
        xaxis_rangeslider_visible=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,23,42,0.15)",
        font=dict(color="#E2E8F0"),
    )
    return fig
