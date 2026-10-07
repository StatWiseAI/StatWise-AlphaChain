"""Professional light-theme styling and small HTML UI primitives."""
from __future__ import annotations

import streamlit as st


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        .main .block-container {padding-top: 1.1rem; padding-bottom: 2.6rem; max-width: 1500px;}
        h1, h2, h3, h4 {color: #0F172A !important; letter-spacing: -0.01em;}
        .alpha-card {background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 14px; padding: 1rem 1.1rem; box-shadow: 0 1px 2px rgba(15,23,42,0.05);}
        .alpha-badge {display: inline-block; padding: 0.22rem 0.6rem; border-radius: 999px; font-size: 0.82rem; font-weight: 700; letter-spacing: 0.01em; margin-right: 0.4rem; margin-bottom: 0.3rem;}
        .alpha-badge.good {background: #ECFDF5; color: #047857; border: 1px solid #A7F3D0;}
        .alpha-badge.warn {background: #FFFBEB; color: #B45309; border: 1px solid #FDE68A;}
        .alpha-badge.bad {background: #FEF2F2; color: #B91C1C; border: 1px solid #FECACA;}
        .alpha-badge.info {background: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE;}
        .alpha-badge.neutral {background: #F1F5F9; color: #475569; border: 1px solid #E2E8F0;}
        .alpha-muted {color: #64748B; font-size: 0.92rem;}
        .alpha-verdict {border-radius: 16px; padding: 1.05rem 1.35rem; margin: 0.3rem 0 0.9rem 0; color: #FFFFFF;}
        .alpha-verdict .v-title {font-size: 1.45rem; font-weight: 800; margin: 0; line-height: 1.25;}
        .alpha-verdict .v-sub {margin: 0.35rem 0 0 0; font-size: 0.98rem; opacity: 0.94;}
        .alpha-verdict.enter {background: linear-gradient(135deg, #047857, #059669); box-shadow: 0 6px 16px rgba(5,150,105,0.22);}
        .alpha-verdict.wait {background: linear-gradient(135deg, #B45309, #F59E0B); box-shadow: 0 6px 16px rgba(245,158,11,0.20);}
        .alpha-verdict.no {background: linear-gradient(135deg, #475569, #64748B); box-shadow: 0 6px 16px rgba(71,85,105,0.18);}
        .alpha-live {display: inline-flex; align-items: center; gap: 0.45rem; font-weight: 700; font-size: 0.88rem; color: #334155;}
        .alpha-live .dot {width: 9px; height: 9px; border-radius: 50%; background: #16A34A; animation: alphapulse 1.6s infinite;}
        .alpha-live.delayed .dot {background: #D97706; animation: none;}
        .alpha-live.stale .dot {background: #DC2626; animation: none;}
        @keyframes alphapulse {0% {box-shadow: 0 0 0 0 rgba(22,163,74,0.45);} 70% {box-shadow: 0 0 0 7px rgba(22,163,74,0);} 100% {box-shadow: 0 0 0 0 rgba(22,163,74,0);}}
        .alpha-gate {display: flex; justify-content: space-between; align-items: baseline; gap: 0.8rem; padding: 0.5rem 0.85rem; border: 1px solid #E2E8F0; border-radius: 10px; margin-bottom: 0.4rem; background: #FFFFFF;}
        .alpha-gate .g-name {font-weight: 700; color: #0F172A; white-space: nowrap;}
        .alpha-gate .g-detail {color: #64748B; font-size: 0.9rem; text-align: right;}
        .alpha-gate.pass {border-left: 4px solid #059669;}
        .alpha-gate.fail {border-left: 4px solid #DC2626; background: #FFFBFA;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def badge(label: str, tone: str = "info") -> str:
    return f'<span class="alpha-badge {tone}">{label}</span>'


def verdict_card(verdict: str, reason: str, meta: str) -> str:
    tone = "enter" if verdict.startswith("ENTER") else "wait" if verdict == "WAIT" else "no"
    return (
        f'<div class="alpha-verdict {tone}">'
        f'<p class="v-title">{verdict}</p>'
        f'<p class="v-sub">{reason}</p>'
        f'<p class="v-sub" style="opacity:0.8">{meta}</p>'
        "</div>"
    )


def live_pill(state: str, text: str) -> str:
    return f'<span class="alpha-live {state}"><span class="dot"></span>{text}</span>'


def gate_row(name: str, passed: bool, detail: str) -> str:
    state = "pass" if passed else "fail"
    mark = "&#10003;" if passed else "&#10007;"
    color = "#047857" if passed else "#B91C1C"
    return (
        f'<div class="alpha-gate {state}">'
        f'<span class="g-name"><span style="color:{color};font-weight:800;margin-right:0.5rem;">{mark}</span>{name}</span>'
        f'<span class="g-detail">{detail}</span>'
        "</div>"
    )
