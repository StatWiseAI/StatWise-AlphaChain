"""Decision engine producing an explicit verdict, entry checklist, and trade plans."""
from __future__ import annotations

from dataclasses import dataclass, field

from . import indicators as ind
from .config import SESSIONS
from .engines import Amplification, DemandSignal, RiskBuffer, bullwhip_detection, demand_sensing, safety_stock
from .models import Candle, DataQuality, SessionProfile, SessionState, SymbolConfig


@dataclass
class ConfluenceItem:
    name: str
    ok: bool
    note: str


@dataclass
class Gate:
    """One explicit entry condition. The verdict passes only when every gate passes."""
    name: str
    passed: bool
    detail: str


@dataclass
class SessionTradePlan:
    session_key: str
    session_label: str
    status: str
    direction: str
    setup_type: str
    entry_type: str
    entry_min: float
    entry_max: float
    stop_loss: float
    take_profit: float
    secondary_target: float
    risk_reward: float
    confidence: int
    notes: list[str] = field(default_factory=list)


@dataclass
class Signal:
    symbol_id: str
    direction: str
    status: str
    entry: float
    entry_type: str
    entry_min: float
    entry_max: float
    take_profit: float
    stop_loss: float
    expected_move_pct: float
    risk_reward: float
    confidence: int
    conviction: float
    support: float
    resistance: float
    higher_timeframe_bias: str
    lower_timeframe_bias: str
    regime: str
    event_risk: str
    current_session_label: str
    data_quality: DataQuality
    setup_quality: str
    invalidation_level: float
    expires_in_hours: int
    confluence: list[ConfluenceItem] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    session_plans: list[SessionTradePlan] = field(default_factory=list)
    verdict: str = ""
    verdict_reason: str = ""
    gates: list[Gate] = field(default_factory=list)
    entry_instructions: list[str] = field(default_factory=list)
    dps: float = 0.5
    ari: float = 1.0
    tp2: float = 0.0


def _confidence_label(value: int) -> str:
    if value >= 80:
        return "High"
    if value >= 65:
        return "Moderate"
    return "Low"


def _event_risk(symbol_id: str, session_key: str, news_bias: str | None = None) -> str:
    if news_bias == "High":
        return "High"
    if session_key == "american" and symbol_id in {"XAUUSD", "EURUSD", "GBPJPY", "ES", "NAS100"}:
        return "Medium"
    return "Low"


def _session_entry_zone(direction: str, session: SessionProfile, price: float, support: float, resistance: float, atr_value: float, fvg) -> tuple[str, float, float, str]:
    buffer = atr_value * 0.35
    if session.key == "asian":
        if direction == "BUY":
            return "limit", max(support, price - buffer), min(price, support + buffer), "range_retest"
        return "limit", max(price, resistance - buffer), resistance + buffer, "range_retest"
    if session.key == "european":
        if fvg and ((fvg.kind == "bullish") == (direction == "BUY")):
            return "limit", fvg.lo, fvg.hi, "pullback_to_fvg"
        if direction == "BUY":
            return "stop", price, resistance + atr_value * 0.2, "breakout_continuation"
        return "stop", support - atr_value * 0.2, price, "breakdown_continuation"
    if direction == "BUY":
        return "market", price - buffer * 0.25, price + buffer * 0.15, "confirmation_entry"
    return "market", price - buffer * 0.15, price + buffer * 0.25, "confirmation_entry"


def _plan_for_session(
    session: SessionProfile,
    direction: str,
    price: float,
    support: float,
    resistance: float,
    risk: RiskBuffer,
    amp: Amplification,
    confidence: int,
    fvg,
    decimals: int,
    event_risk: str,
) -> SessionTradePlan:
    entry_type, entry_min, entry_max, setup_type = _session_entry_zone(direction, session, price, support, resistance, risk.atr_value, fvg)
    if direction == "BUY":
        stop = support - risk.stop_distance * 0.35
        take_profit = resistance if resistance > price else price + risk.atr_value * 3
        secondary = take_profit + risk.atr_value * 1.5
    else:
        stop = resistance + risk.stop_distance * 0.35
        take_profit = support if support < price else price - risk.atr_value * 3
        secondary = take_profit - risk.atr_value * 1.5

    mid_entry = (entry_min + entry_max) / 2
    risk_dist = max(abs(mid_entry - stop), 1e-9)
    reward_dist = abs(take_profit - mid_entry)
    rr = reward_dist / risk_dist if risk_dist else 0.0

    status = "ACTIVE"
    notes = [session.style_note]
    if event_risk == "High":
        status = "WAIT"
        notes.append("High event risk: wait for the first post-event candle to close before entry.")
    elif amp.ari > 1.35 and session.key != "american":
        status = "WAIT"
        notes.append("Amplification risk is elevated; avoid chasing the move.")
    elif confidence < 58:
        status = "NO_TRADE"
        notes.append("Signal confidence is below the tradeable threshold for this session.")

    return SessionTradePlan(
        session.key,
        session.label,
        status,
        direction,
        setup_type,
        entry_type,
        round(min(entry_min, entry_max), decimals),
        round(max(entry_min, entry_max), decimals),
        round(stop, decimals),
        round(take_profit, decimals),
        round(secondary, decimals),
        round(max(rr, 0.0), 2),
        confidence,
        notes,
    )


def build_signal(
    symbol_cfg: SymbolConfig,
    candles: list[Candle],
    live_price: float,
    data_quality: DataQuality,
    session_state: SessionState,
    higher_timeframe_candles: list[Candle] | None = None,
    lower_timeframe_candles: list[Candle] | None = None,
    news_bias: str | None = None,
) -> Signal:
    decimals = symbol_cfg.decimals
    demand: DemandSignal = demand_sensing(candles, higher_timeframe_candles)
    event_risk = _event_risk(symbol_cfg.id, session_state.primary_key, news_bias)
    risk: RiskBuffer = safety_stock(candles, session_multiplier=SESSIONS[session_state.primary_key].volatility_bias, event_risk=event_risk)
    amp: Amplification = bullwhip_detection(candles)

    support, resistance = ind.swing_support_resistance(candles)
    directional_side = "BUY" if demand.dps >= 0.5 else "SELL"
    lower_bias = ind.trend_direction([c.c for c in lower_timeframe_candles]) if lower_timeframe_candles else "Flat"
    bull = directional_side == "BUY"
    buffer = risk.stop_distance * 0.4

    entry = live_price
    if bull:
        stop = support - buffer
        target = resistance if resistance > entry * 1.0008 else entry + risk.atr_value * 3
    else:
        stop = resistance + buffer
        target = support if support < entry * 0.9992 else entry - risk.atr_value * 3

    risk_dist = abs(entry - stop)
    reward_dist = abs(target - entry)
    risk_reward = max(0.8, min(5.0, reward_dist / risk_dist)) if risk_dist else 2.0
    expected_move = (target - entry) / entry * 100 if entry else 0.0
    signal_strength = (demand.dps - 0.5) * (1.0 / max(amp.ari, 0.2))
    conviction = signal_strength / max(risk.stop_distance / max(entry, 1e-6), 1e-6)

    volume_expanding = ind.volume_expanding(candles)
    fvg = ind.find_fvg(candles)
    confidence = demand.confidence if demand.direction != "WAIT" else min(demand.confidence, 60)
    regime = demand.regime

    confluence = [
        ConfluenceItem("Structure", True, f"{'Support' if bull else 'Resistance'} {round(support if bull else resistance, decimals)}"),
        ConfluenceItem("FVG", bool(fvg) and ((fvg.kind == "bullish") == bull), f"{fvg.kind} {round(fvg.lo, decimals)}-{round(fvg.hi, decimals)}" if fvg else "none nearby"),
        ConfluenceItem("Volume / Range", volume_expanding, "expanding" if volume_expanding else "below average"),
        ConfluenceItem(f"RSI {round(amp.rsi_value)}", (amp.rsi_value < 58) if bull else (amp.rsi_value > 42), "oversold" if amp.rsi_value < 35 else "overbought" if amp.rsi_value > 65 else "neutral"),
        ConfluenceItem("Higher TF", demand.higher_timeframe_bias == ("Bull" if bull else "Bear"), demand.higher_timeframe_bias),
        ConfluenceItem("Data Quality", not data_quality.synthetic, data_quality.note),
    ]

    reasons: list[str] = []
    if bull and demand.direction != "WAIT":
        reasons.append(f"Long off the {round(support, decimals)} support with higher probability continuation toward {round(target, decimals)}.")
        if fvg and fvg.kind == "bullish":
            reasons.append(f"Unfilled bullish FVG at {round(fvg.lo, decimals)}-{round(fvg.hi, decimals)} supports a pullback entry.")
    elif (not bull) and demand.direction != "WAIT":
        reasons.append(f"Short below the {round(resistance, decimals)} resistance with downside room toward {round(target, decimals)}.")
        if fvg and fvg.kind == "bearish":
            reasons.append(f"Unfilled bearish FVG at {round(fvg.lo, decimals)}-{round(fvg.hi, decimals)} reinforces seller control.")
    else:
        reasons.append("Directional edge is weak; wait for stronger structure confirmation or a cleaner pullback.")
    reasons.append(f"Regime is {regime}; amplification risk is {amp.ari:.2f}; higher timeframe bias is {demand.higher_timeframe_bias}.")
    reasons.append(f"Risk buffer widens by uncertainty factor {risk.uncertainty_factor:.2f}, consistent with the safety-stock risk logic.")
    if event_risk != "Low":
        reasons.append(f"Event risk is {event_risk.lower()}, so confirmation is preferred before entry.")
    if data_quality.synthetic:
        reasons.append("Live historical candles were unavailable; treat this as a watchlist-quality read until live candles return.")

    # ---- Explicit entry checklist (the verdict is derived from exactly these gates) ----
    dps_threshold = 0.53 if bull else 0.47
    htf_aligned = demand.higher_timeframe_bias == ("Bull" if bull else "Bear") or demand.higher_timeframe_bias == "Flat"
    gates = [
        Gate(
            "Demand pressure direction",
            demand.direction != "WAIT",
            f"DPS {demand.dps:.2f} vs threshold {dps_threshold:.2f} ({'long' if bull else 'short'}); neutral band 0.47-0.53",
        ),
        Gate(
            "Amplification contained",
            amp.ari <= 1.6,
            f"ARI {amp.ari:.2f} (limit 1.60); above 1.0 means the move may be over-extended",
        ),
        Gate(
            "Reward-to-risk at least 1:1.4",
            risk_reward >= 1.4,
            f"plan offers 1:{risk_reward:.1f} (entry {round(entry, decimals)} - stop {round(stop, decimals)} - target {round(target, decimals)})",
        ),
        Gate(
            "Confidence at least 55%",
            confidence >= 55,
            f"model confidence {confidence}%",
        ),
        Gate(
            "Higher-timeframe alignment",
            htf_aligned,
            f"higher-timeframe bias: {demand.higher_timeframe_bias} ({'aligned' if htf_aligned else 'against the trade'})",
        ),
        Gate(
            "No high-impact event window",
            event_risk != "High",
            f"event risk: {event_risk.lower()}",
        ),
        Gate(
            "Live market data",
            not data_quality.synthetic,
            data_quality.note,
        ),
    ]
    failed = [g for g in gates if not g.passed]

    if demand.direction == "WAIT" or event_risk == "High":
        status = "WAIT"
    elif failed:
        status = "NO_TRADE"
    else:
        status = "ACTIVE"

    if status == "ACTIVE":
        verdict = f"ENTER {'LONG' if bull else 'SHORT'}"
        verdict_reason = (
            f"Demand pressure {demand.dps:.2f} with contained amplification (ARI {amp.ari:.2f}); "
            f"the plan risks 1 to make {risk_reward:.1f} at {confidence}% confidence."
        )
        tp2 = target + risk.atr_value * 1.5 if bull else target - risk.atr_value * 1.5
        entry_lo, entry_hi = round(entry - risk.atr_value * 0.2, decimals), round(entry + risk.atr_value * 0.2, decimals)
        entry_instructions = [
            f"Enter in the {entry_lo} - {entry_hi} zone (order type: {signal_entry_type(session_state.primary_key)}).",
            f"Place the protective stop at {round(stop, decimals)} - that is {abs(entry - stop):.{decimals}f} of risk, scaled by the volatility buffer.",
            f"Take the first partial profit at TP1 {round(target, decimals)} ({expected_move:+.2f}%).",
            f"After TP1 fills, move the stop to entry and trail the remainder toward TP2 {round(tp2, decimals)}.",
            f"If the order has not triggered within {expires_hours(session_state.primary_key)} h, cancel it and re-read the setup.",
            "Size the position with the calculator below (default risk: 1% of account).",
        ]
    elif status == "WAIT":
        verdict = "WAIT"
        if event_risk == "High":
            verdict_reason = "High-impact event window - enter only after the first post-event candle has closed."
        else:
            verdict_reason = f"Demand pressure is inconclusive (DPS {demand.dps:.2f}, neutral band 0.47-0.53) - there is no directional edge to trade."
        entry_instructions = [
            "Stand aside - do not force a position.",
            "Re-check once demand pressure leaves the neutral band and the checklist below turns green.",
        ]
    else:
        verdict = "NO TRADE"
        verdict_reason = "Blocked by: " + "; ".join(f"{g.name.lower()} ({g.detail})" for g in failed[:2])
        entry_instructions = [
            "No position.",
            "Re-evaluate once these checklist items pass: " + ", ".join(g.name.lower() for g in failed) + ".",
        ]

    session_plans = [
        _plan_for_session(SESSIONS[key], directional_side, live_price, support, resistance, risk, amp, confidence, fvg, decimals, _event_risk(symbol_cfg.id, key, news_bias))
        for key in ("asian", "european", "american")
    ]

    return Signal(
        symbol_id=symbol_cfg.id,
        direction=directional_side,
        status=status,
        entry=round(entry, decimals),
        entry_type="market" if session_state.primary_key == "american" else "limit",
        entry_min=round(entry - risk.atr_value * 0.2, decimals),
        entry_max=round(entry + risk.atr_value * 0.2, decimals),
        take_profit=round(target, decimals),
        stop_loss=round(stop, decimals),
        expected_move_pct=round(expected_move, 2),
        risk_reward=round(risk_reward, 1),
        confidence=confidence,
        conviction=round(conviction, 3),
        support=round(support, decimals),
        resistance=round(resistance, decimals),
        higher_timeframe_bias=demand.higher_timeframe_bias,
        lower_timeframe_bias=lower_bias,
        regime=regime,
        event_risk=event_risk,
        current_session_label=session_state.primary_label,
        data_quality=data_quality,
        setup_quality=_confidence_label(confidence),
        invalidation_level=round(stop, decimals),
        expires_in_hours=8 if session_state.primary_key == "american" else 12,
        confluence=confluence,
        reasons=reasons,
        session_plans=session_plans,
        verdict=verdict,
        verdict_reason=verdict_reason,
        gates=gates,
        entry_instructions=entry_instructions,
        dps=demand.dps,
        ari=amp.ari,
        tp2=round(tp2, decimals) if status == "ACTIVE" else 0.0,
    )


def signal_entry_type(session_key: str) -> str:
    return "market" if session_key == "american" else "limit"


def expires_hours(session_key: str) -> int:
    return 8 if session_key == "american" else 12


def position_size(account: float, risk_pct: float, entry: float, stop_loss: float, risk_reward: float):
    risk_amount = account * risk_pct / 100
    stop_distance = abs(entry - stop_loss)
    units = risk_amount / stop_distance if stop_distance else 0.0
    notional = units * entry
    reward_amount = risk_amount * risk_reward
    return {
        "risk_amount": round(risk_amount, 2),
        "reward_amount": round(reward_amount, 2),
        "stop_distance": round(stop_distance, 6),
        "units": units,
        "notional": round(notional, 2),
    }
