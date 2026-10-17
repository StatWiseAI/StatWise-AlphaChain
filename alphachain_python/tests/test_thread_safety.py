"""Concurrency stress test for SignalLedger and NewsFeed thread safety."""
from __future__ import annotations

import os
import random
import tempfile
import threading
import time
import traceback

from alphachain_python.decision_engine import Signal
from alphachain_python.evaluation import SignalLedger
from alphachain_python.models import DataQuality
from alphachain_python.news_layer import NewsFeed


def make_signal(i: int) -> Signal:
    return Signal(
        symbol_id=f"SYM{i % 5}",
        direction="BUY" if i % 2 == 0 else "SELL",
        status="ACTIVE",
        entry=100.0 + i,
        entry_type="limit",
        entry_min=99.0 + i,
        entry_max=101.0 + i,
        take_profit=110.0 + i,
        stop_loss=95.0 + i,
        expected_move_pct=1.5,
        risk_reward=2.0,
        confidence=60,
        conviction=0.5,
        support=90.0,
        resistance=110.0,
        higher_timeframe_bias="Bull",
        lower_timeframe_bias="Bull",
        regime="Trend",
        event_risk="Low",
        current_session_label="European Session",
        data_quality=DataQuality("Test", False, "ok", time.time()),
        setup_quality="Moderate",
        invalidation_level=95.0,
        expires_in_hours=8,
        confluence=[],
        reasons=[],
        session_plans=[],
    )


def run():
    db_fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(db_fd)
    ledger = SignalLedger(db_path)
    news = NewsFeed()

    errors: list[str] = []
    errors_lock = threading.Lock()

    def record_error(where: str, exc: Exception):
        with errors_lock:
            errors.append(f"{where}: {exc}\n{traceback.format_exc()}")

    def writer_thread(n: int):
        for i in range(30):
            try:
                row_id = ledger.open_signal(make_signal(n * 100 + i), timeframe="15m")
                if random.random() < 0.5:
                    ledger.mark_outcome(row_id, hit_take_profit=random.random() < 0.5)
                else:
                    ledger.check_price_against_open_signals(f"SYM{i % 5}", 100.0 + random.random() * 20)
            except Exception as exc:
                record_error(f"writer_thread[{n}]", exc)

    def reader_thread(n: int):
        for _ in range(30):
            try:
                ledger.summary()
                ledger.win_rate_by_market()
                ledger.recent_history(limit=20)
                ledger.open_positions()
            except Exception as exc:
                record_error(f"reader_thread[{n}]", exc)

    def news_thread(n: int):
        for _ in range(30):
            try:
                news.refresh()
                news.for_symbol("XAUUSD")
                news.sorted_by_recency()
                news.bias_for_symbol("XAUUSD")
            except Exception as exc:
                record_error(f"news_thread[{n}]", exc)

    threads = []
    for n in range(8):
        threads.append(threading.Thread(target=writer_thread, args=(n,)))
    for n in range(8):
        threads.append(threading.Thread(target=reader_thread, args=(n,)))
    for n in range(4):
        threads.append(threading.Thread(target=news_thread, args=(n,)))

    start = time.time()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    elapsed = time.time() - start

    os.unlink(db_path)

    if errors:
        print(f"FAILED -- {len(errors)} error(s) across {len(threads)} threads:")
        for err in errors:
            print("---")
            print(err)
        raise SystemExit(1)

    final = ledger.summary()
    print(f"OK -- {len(threads)} threads, 30 ops each, {elapsed:.2f}s, no exceptions. Final ledger: {final.total_closed} closed signals.")


if __name__ == "__main__":
    run()
