from __future__ import annotations

from .decision_engine import Signal
from .models import SessionState, SymbolConfig


def signal_email_subject(symbol_cfg: SymbolConfig, signal: Signal) -> str:
    return f"{symbol_cfg.name} | {signal.status} {signal.direction} | {signal.current_session_label}"


def signal_email_body(symbol_cfg: SymbolConfig, signal: Signal, timeframe: str, session_state: SessionState) -> str:
    lines = [
        f"Instrument: {symbol_cfg.name} ({symbol_cfg.full})",
        f"Timeframe: {timeframe}",
        f"Current session: {session_state.primary_label}",
        f"Status: {signal.status}",
        f"Primary direction: {signal.direction}",
        f"Entry type: {signal.entry_type}",
        f"Entry zone: {signal.entry_min} - {signal.entry_max}",
        f"Stop loss: {signal.stop_loss}",
        f"Take profit: {signal.take_profit}",
        f"Risk / reward: 1:{signal.risk_reward}",
        f"Confidence: {signal.confidence}% ({signal.setup_quality})",
        f"Higher timeframe bias: {signal.higher_timeframe_bias}",
        f"Lower timeframe bias: {signal.lower_timeframe_bias}",
        f"Regime: {signal.regime}",
        f"Event risk: {signal.event_risk}",
        f"Data provider: {signal.data_quality.provider}",
        "",
        "Rationale:",
    ]
    lines.extend(f"- {reason}" for reason in signal.reasons)
    lines.append("")
    lines.append("Session plans:")
    for plan in signal.session_plans:
        lines.append(
            f"- {plan.session_label}: {plan.status} {plan.direction} via {plan.entry_type} | entry {plan.entry_min}-{plan.entry_max} | SL {plan.stop_loss} | TP {plan.take_profit} | RR {plan.risk_reward}"
        )
    lines.append("")
    lines.append("Disclaimer: decision-support output, not financial advice or auto-execution.")
    return "\n".join(lines)
