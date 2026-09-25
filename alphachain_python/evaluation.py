"""Persistent signal evaluation with richer professional metrics."""
from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Optional

from .decision_engine import Signal

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_id TEXT NOT NULL,
    timeframe TEXT,
    session_key TEXT,
    direction TEXT NOT NULL,
    status TEXT,
    entry REAL NOT NULL,
    take_profit REAL NOT NULL,
    stop_loss REAL NOT NULL,
    risk_reward REAL NOT NULL,
    confidence INTEGER,
    conviction REAL,
    entry_type TEXT,
    data_provider TEXT,
    synthetic INTEGER DEFAULT 0,
    opened_ts REAL NOT NULL,
    closed_ts REAL,
    outcome TEXT,
    r_multiple REAL
);
"""


@dataclass
class EvalSummary:
    total_closed: int
    total_open: int
    wins: int
    losses: int
    win_rate_pct: float
    avg_r: float
    profit_factor: float


class SignalLedger:
    def __init__(self, db_path: str = "alphachain.sqlite3"):
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        with self._lock:
            self.conn.execute(SCHEMA)
            self.conn.commit()

    def open_signal(self, sig: Signal, timeframe: str) -> int:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO signals (symbol_id, timeframe, session_key, direction, status, entry, take_profit, stop_loss, risk_reward, confidence, conviction, entry_type, data_provider, synthetic, opened_ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    sig.symbol_id,
                    timeframe,
                    sig.current_session_label,
                    sig.direction,
                    sig.status,
                    sig.entry,
                    sig.take_profit,
                    sig.stop_loss,
                    sig.risk_reward,
                    sig.confidence,
                    sig.conviction,
                    sig.entry_type,
                    sig.data_quality.provider,
                    1 if sig.data_quality.synthetic else 0,
                    time.time(),
                ),
            )
            self.conn.commit()
            return cur.lastrowid

    def mark_outcome(self, signal_row_id: int, hit_take_profit: bool):
        with self._lock:
            row = self.conn.execute("SELECT risk_reward FROM signals WHERE id=?", (signal_row_id,)).fetchone()
            if not row:
                return
            rr = row[0]
            outcome = "WIN" if hit_take_profit else "LOSS"
            r_multiple = rr if hit_take_profit else -1.0
            self.conn.execute(
                "UPDATE signals SET closed_ts=?, outcome=?, r_multiple=? WHERE id=?",
                (time.time(), outcome, r_multiple, signal_row_id),
            )
            self.conn.commit()

    def check_price_against_open_signals(self, symbol_id: str, current_price: float):
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, direction, take_profit, stop_loss FROM signals WHERE symbol_id=? AND outcome IS NULL",
                (symbol_id,),
            ).fetchall()
        for row_id, direction, tp, sl in rows:
            if direction == "BUY":
                if current_price >= tp:
                    self.mark_outcome(row_id, True)
                elif current_price <= sl:
                    self.mark_outcome(row_id, False)
            else:
                if current_price <= tp:
                    self.mark_outcome(row_id, True)
                elif current_price >= sl:
                    self.mark_outcome(row_id, False)

    def summary(self, symbol_id: Optional[str] = None) -> EvalSummary:
        q = "SELECT outcome, r_multiple FROM signals WHERE outcome IS NOT NULL"
        open_q = "SELECT COUNT(*) FROM signals WHERE outcome IS NULL"
        params: tuple = ()
        if symbol_id:
            q += " AND symbol_id=?"
            open_q += " AND symbol_id=?"
            params = (symbol_id,)
        with self._lock:
            rows = self.conn.execute(q, params).fetchall()
            open_count = self.conn.execute(open_q, params).fetchone()[0]
        total = len(rows)
        wins = sum(1 for outcome, _ in rows if outcome == "WIN")
        losses = total - wins
        sum_win = sum(r for outcome, r in rows if outcome == "WIN")
        sum_loss = sum(abs(r) for outcome, r in rows if outcome == "LOSS")
        avg_r = (sum(r for _, r in rows) / total) if total else 0.0
        profit_factor = (sum_win / sum_loss) if sum_loss else float(sum_win) if sum_win else 0.0
        win_rate = (wins / total * 100) if total else 0.0
        return EvalSummary(total, open_count, wins, losses, round(win_rate, 1), round(avg_r, 3), round(profit_factor, 2))

    def win_rate_by_market(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute("SELECT symbol_id, outcome FROM signals WHERE outcome IS NOT NULL").fetchall()
        agg: dict[str, list[int]] = {}
        for sym, outcome in rows:
            agg.setdefault(sym, [0, 0])
            agg[sym][1] += 1
            if outcome == "WIN":
                agg[sym][0] += 1
        return sorted(
            [{"symbol_id": sym, "wins": wins, "total": total, "win_rate_pct": round(wins / total * 100, 1)} for sym, (wins, total) in agg.items()],
            key=lambda item: -item["win_rate_pct"],
        )

    def recent_history(self, limit: int = 100) -> list[tuple]:
        with self._lock:
            return self.conn.execute(
                "SELECT symbol_id, timeframe, session_key, direction, status, entry, take_profit, stop_loss, outcome, r_multiple, confidence, opened_ts FROM signals ORDER BY opened_ts DESC LIMIT ?",
                (limit,),
            ).fetchall()

    def open_positions(self) -> list[tuple]:
        with self._lock:
            return self.conn.execute(
                "SELECT symbol_id, timeframe, session_key, direction, entry, take_profit, stop_loss, confidence, opened_ts FROM signals WHERE outcome IS NULL ORDER BY opened_ts DESC"
            ).fetchall()
