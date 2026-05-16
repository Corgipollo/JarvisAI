"""test_algorithmic_death.py - Tests del instinto de supervivencia."""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def reset_ledger():
    db = ROOT / "data" / "spend_ledger.sqlite"
    if db.exists():
        db.unlink()
    dm = ROOT / "data" / ".death_marker"
    if dm.exists():
        dm.unlink()
    autopsy = ROOT / "data" / "autopsy.json"
    if autopsy.exists():
        autopsy.unlink()


def seed_ledger(rows):
    """rows = [(ts_iso, amount_usd, roi)]"""
    reset_ledger()
    db = ROOT / "data" / "spend_ledger.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE IF NOT EXISTS spend (
        id INTEGER PRIMARY KEY, ts TEXT NOT NULL,
        idempotency_key TEXT UNIQUE, amount_usd REAL NOT NULL,
        action_type TEXT, result_roi REAL,
        rollback_token TEXT, notes TEXT)""")
    for i, (ts, amt, roi) in enumerate(rows):
        con.execute(
            "INSERT INTO spend (ts, idempotency_key, amount_usd, "
            "action_type, result_roi) VALUES (?,?,?,?,?)",
            (ts, f"test_{i}_{ts}", amt, "test", roi))
    con.commit()
    con.close()


def test_1_healthy_no_death():
    print("\n=== TEST 1: healthy state -> NO death ===")
    from jarvis_v2.cfo.algorithmic_death import check_death_triggers
    reset_ledger()
    now = datetime.utcnow()
    rows = [((now - timedelta(days=i)).isoformat(), 1.0, 1.5)
            for i in range(10)]  # 10 trades a 1.5x
    seed_ledger(rows)
    v = check_death_triggers()
    print(f"  triggers: {v['triggers']}")
    print(f"  metrics: {v['metrics']}")
    assert not v["should_die"], "Healthy state should NOT trigger death"
    print("  [OK] PASSED")


def test_2_low_balance_low_roi_dies():
    print("\n=== TEST 2: low balance + low ROI -> DEATH ===")
    from jarvis_v2.cfo.algorithmic_death import check_death_triggers
    reset_ledger()
    now = datetime.utcnow()
    # Lifetime spend ~$96, ROI muy bajo
    rows = []
    for i in range(20):
        rows.append(((now - timedelta(days=i % 25)).isoformat(), 4.8, 0.2))
    seed_ledger(rows)
    v = check_death_triggers()
    print(f"  balance: ${v['metrics']['balance_usd']}")
    print(f"  roi_30d: {v['metrics']['roi_30d']}")
    print(f"  triggers: {[t['id'] for t in v['triggers']]}")
    assert v["should_die"], "Should trigger death"
    print("  [OK] PASSED")


def test_3_lifetime_burn_exceeded():
    print("\n=== TEST 3: lifetime burn > $95 -> DEATH ===")
    from jarvis_v2.cfo.algorithmic_death import check_death_triggers
    reset_ledger()
    now = datetime.utcnow()
    rows = [(now.isoformat(), 96.0, 1.5)]  # 1 gasto enorme con buen ROI
    seed_ledger(rows)
    v = check_death_triggers()
    print(f"  spent: ${v['metrics']['lifetime_spent']}")
    print(f"  triggers: {[t['id'] for t in v['triggers']]}")
    assert v["should_die"], "Lifetime burn should trigger"
    assert any(t["id"] == "lifetime_burn_exceeded" for t in v["triggers"])
    print("  [OK] PASSED")


def test_4_survival_signals_balanced():
    print("\n=== TEST 4: survival_signals para Planner ===")
    from jarvis_v2.cfo.algorithmic_death import survival_signals
    reset_ledger()
    now = datetime.utcnow()
    # Health intermedia: 5 trades a 1.3x, gasto moderado
    rows = [((now - timedelta(days=i)).isoformat(), 2.0, 1.3) for i in range(5)]
    seed_ledger(rows)
    s = survival_signals()
    print(f"  runway: {s['burn_runway_days']}d")
    print(f"  roi_health: {s['roi_health']}")
    print(f"  recommendation: {s['recommendation']}")
    print(f"  max_safe: ${s['max_safe_spend_per_action']}")
    assert s["recommendation"] in ("balanced", "aggressive", "conservative")
    assert not s["is_dying"]
    print("  [OK] PASSED")


def test_5_loss_streak_triggers():
    print("\n=== TEST 5: 7+ dias loss streak -> DEATH ===")
    from jarvis_v2.cfo.algorithmic_death import check_death_triggers
    reset_ledger()
    now = datetime.utcnow()
    rows = []
    for i in range(8):  # 8 dias consecutivos de losses
        day = (now - timedelta(days=i)).isoformat()
        rows.append((day, 1.0, 0.5))  # roi 0.5 = perdida 50%
    seed_ledger(rows)
    v = check_death_triggers()
    print(f"  loss_streak: {v['metrics']['loss_streak_days']}")
    print(f"  triggers: {[t['id'] for t in v['triggers']]}")
    assert v["should_die"]
    assert any(t["id"] == "prolonged_loss_streak" for t in v["triggers"])
    print("  [OK] PASSED")


def test_6_human_drag_imports():
    print("\n=== TEST 6: human_drag function imports ===")
    from jarvis_v2.swarm.human_mouse import human_drag, gui_mouse_lock
    assert callable(human_drag)
    print("  [OK] PASSED")


def main():
    tests = [
        test_1_healthy_no_death,
        test_2_low_balance_low_roi_dies,
        test_3_lifetime_burn_exceeded,
        test_4_survival_signals_balanced,
        test_5_loss_streak_triggers,
        test_6_human_drag_imports,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERR] {type(e).__name__}: {e}")
            failed += 1
    # Reset clean state al final
    reset_ledger()
    print(f"\n=== RESULTS: {passed}/{len(tests)} passed ===")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
