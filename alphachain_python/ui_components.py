from __future__ import annotations

import streamlit as st


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        .stApp {background: radial-gradient(circle at top left, #111827 0%, #0f172a 45%, #020617 100%); color: #e2e8f0;}
        .main .block-container {padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1400px;}
        .alpha-card {background: linear-gradient(180deg, rgba(15,23,42,0.88), rgba(15,23,42,0.72)); border: 1px solid rgba(148,163,184,0.18); border-radius: 18px; padding: 1rem 1.1rem; box-shadow: 0 10px 30px rgba(2,6,23,0.35);}
        .alpha-badge {display: inline-block; padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.82rem; font-weight: 700; letter-spacing: 0.02em; margin-right: 0.4rem; margin-bottom: 0.3rem;}
        .alpha-badge.good {background: rgba(16,185,129,0.12); color: #34d399; border: 1px solid rgba(52,211,153,0.35);}
        .alpha-badge.warn {background: rgba(251,191,36,0.12); color: #fbbf24; border: 1px solid rgba(251,191,36,0.35);}
        .alpha-badge.bad {background: rgba(248,113,113,0.12); color: #f87171; border: 1px solid rgba(248,113,113,0.35);}
        .alpha-badge.info {background: rgba(96,165,250,0.12); color: #60a5fa; border: 1px solid rgba(96,165,250,0.35);}
        .alpha-muted {color: #94a3b8; font-size: 0.92rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def badge(label: str, tone: str = "info") -> str:
    return f'<span class="alpha-badge {tone}">{label}</span>'
