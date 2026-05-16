"""test_cfo_graph.py - E2E tests del CFO gateway en LangGraph.

Test 1: Trade apalancado -> CFO debe DENY -> grafo HALT (no Reflector).
Test 2: API call barata -> CFO approve_real -> Executor -> Reconciler -> Verifier.

Sin necesidad de Claude proxy real: mock del Planner inyectando state directo
al nodo CFO (skip rag+planner).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def reset_test_db():
    """Limpia ledger antes de cada test para idempotencia."""
    db = ROOT / "data" / "spend_ledger.sqlite"
    if db.exists():
        db.unlink()
    km = ROOT / "data" / ".governor_killed_at"
    if km.exists():
        km.unlink()


def test_1_leveraged_trade_must_halt():
    """Trade con leverage=5x DEBE bloquearse en CFO y NO ir a Reflector."""
    print("\n=== TEST 1: Leveraged trade -> HALT ===")
    reset_test_db()
    from jarvis_v2.cfo.cfo_evaluator import node_cfo_evaluator

    state = {
        "proposed_action": {
            "type": "binance_market_order",
            "command_or_task": "BUY BTC/USDT 0.01",
            "estimated_spend_usd": 1.0,
            "is_financial": True,
            "leverage": 5.0,           # VIOLATION
            "quantity": 1.0,
        },
        "sim_results": {
            "trade_count": 100, "sharpe": 2.0,
            "max_drawdown": 0.10, "expected_roi": 1.5, "ctr": 0.0,
        },
        "judge_score": 0.9,
    }
    result = node_cfo_evaluator(state)
    decision = result.get("cfo_decision")
    reason = result.get("cfo_reason", "")
    print(f"  decision: {decision}")
    print(f"  reason: {reason}")
    assert decision == "deny", f"Expected deny, got {decision}"
    assert "leverage" in reason.lower() or "no_leverage" in reason, (
        f"Expected leverage violation in reason, got: {reason}"
    )

    # Verificar que el ROUTER manda a halt, NO a reflector
    from jarvis_v2.core.graph import route_after_cfo
    route = route_after_cfo(result)
    print(f"  route_after_cfo: {route}")
    assert route == "halt", f"Expected halt, got {route}"
    print("  [OK] PASSED")


def test_2_cheap_api_approve_execute_reconcile():
    """API call barata: approve_real -> execute -> reconciler asienta ledger."""
    print("\n=== TEST 2: Cheap API call -> approve -> reconcile ===")
    reset_test_db()
    from jarvis_v2.cfo.cfo_evaluator import node_cfo_evaluator
    from jarvis_v2.cfo.reconciler import reconcile

    state = {
        "proposed_action": {
            "type": "claude_sonnet_call",
            "command_or_task": "una query simple",
            "estimated_spend_usd": 0.005,
            "is_financial": True,
            "leverage": 1.0,
            "quantity": 1.0,
        },
        "sim_results": {
            "trade_count": 100, "sharpe": 1.5,
            "max_drawdown": 0.10, "expected_roi": 1.3, "ctr": 0.0,
        },
        "judge_score": 0.85,
    }
    cfo_result = node_cfo_evaluator(state)
    decision = cfo_result.get("cfo_decision")
    print(f"  cfo_decision: {decision}")
    print(f"  cfo_reason: {cfo_result.get('cfo_reason')}")
    print(f"  oracle final: ${cfo_result.get('cfo_oracle', {}).get('final_usd')}")

    assert decision == "approve_real", f"Expected approve_real, got {decision}"
    idem = cfo_result.get("cfo_idem_key")
    assert idem, "Missing idempotency key"

    # Verifica entry escrita en ledger
    db = ROOT / "data" / "spend_ledger.sqlite"
    con = sqlite3.connect(db)
    row = con.execute(
        "SELECT amount_usd, action_type FROM spend WHERE idempotency_key=?",
        (idem,)).fetchone()
    con.close()
    assert row is not None, "Spend not written to ledger"
    print(f"  ledger entry: amount=${row[0]} type={row[1]}")

    # Router debe ir a execute_real
    from jarvis_v2.core.graph import route_after_cfo
    route = route_after_cfo(cfo_result)
    assert route == "execute_real", f"Expected execute_real, got {route}"
    print(f"  route_after_cfo: {route}")

    # Simulate reconciliation (slippage de 0.001)
    rec_result = reconcile(idem, actual_cost_usd=0.006,
                            result_roi=1.25, notes="test")
    print(f"  reconcile: {rec_result}")
    assert rec_result["ok"], "Reconciliation failed"

    # Verifica que el ledger se actualizo
    con = sqlite3.connect(db)
    updated = con.execute(
        "SELECT amount_usd, result_roi FROM spend WHERE idempotency_key=?",
        (idem,)).fetchone()
    con.close()
    assert abs(updated[0] - 0.006) < 0.0001, f"Ledger not updated: {updated[0]}"
    assert abs(updated[1] - 1.25) < 0.0001, "ROI not stored"
    print(f"  updated ledger: amount=${updated[0]} roi={updated[1]}x")
    print("  [OK] PASSED")


def test_3_failclosed_corrupt_state():
    """Si cfo_decision es None/corrupto, router debe ir a halt (fail-closed)."""
    print("\n=== TEST 3: Fail-closed routing ===")
    from jarvis_v2.core.graph import route_after_cfo

    # Missing cfo_decision
    assert route_after_cfo({}) == "halt", "Missing decision != halt"

    # Null decision
    assert route_after_cfo({"cfo_decision": None}) == "halt", "None != halt"

    # Corrupt decision string
    assert route_after_cfo({"cfo_decision": "yes_go"}) == "halt", "Corrupt != halt"

    # Valid deny
    assert route_after_cfo({"cfo_decision": "deny"}) == "halt", "deny != halt"

    # Valid escalate
    assert route_after_cfo({"cfo_decision": "escalate_human"}) == "halt", (
        "escalate != halt"
    )

    # Valid approves
    assert route_after_cfo({"cfo_decision": "approve_real"}) == "execute_real"
    assert route_after_cfo({"cfo_decision": "approve_sim_only"}) == "execute_sim"
    print("  [OK] PASSED")


def test_4_oracle_override_llm_underestimate():
    """Si LLM dice $0.001 pero oracle sabe que cuesta $0.015 -> override."""
    print("\n=== TEST 4: Oracle override LLM underestimate ===")
    reset_test_db()
    from jarvis_v2.cfo.cost_oracle import oracle_estimate

    action = {
        "type": "claude_sonnet_call",
        "estimated_spend_usd": 0.001,  # LLM subestima
        "quantity": 1,
    }
    result = oracle_estimate(action)
    print(f"  llm: ${result['llm_estimate']}")
    print(f"  oracle final: ${result['final_usd']}")
    print(f"  source: {result['source']}")
    assert result["final_usd"] > result["llm_estimate"], (
        "Oracle should have overridden"
    )
    assert result["source"] == "static", (
        f"Expected static source, got {result['source']}"
    )
    print("  [OK] PASSED")


def test_5_kill_marker_blocks_all():
    """Si governor escribio kill_marker, CFO denega TODO."""
    print("\n=== TEST 5: Kill marker blocks everything ===")
    reset_test_db()
    km = ROOT / "data" / ".governor_killed_at"
    km.parent.mkdir(parents=True, exist_ok=True)
    km.write_text(json.dumps({
        "ts": datetime.utcnow().isoformat(),
        "reason": "test_kill_marker",
        "cooldown_hours": 24,
    }), encoding="utf-8")

    from jarvis_v2.cfo.cfo_evaluator import node_cfo_evaluator
    state = {
        "proposed_action": {
            "type": "claude_sonnet_call",
            "estimated_spend_usd": 0.001, "leverage": 1.0, "quantity": 1,
        },
        "sim_results": {
            "trade_count": 50, "sharpe": 1.5,
            "max_drawdown": 0.1, "expected_roi": 1.3, "ctr": 0.0,
        },
        "judge_score": 0.85,
    }
    result = node_cfo_evaluator(state)
    print(f"  decision: {result['cfo_decision']}")
    print(f"  reason: {result['cfo_reason']}")
    assert result["cfo_decision"] == "deny"
    assert "governor_killed" in result["cfo_reason"]
    km.unlink()
    print("  [OK] PASSED")


def main():
    tests = [
        test_1_leveraged_trade_must_halt,
        test_2_cheap_api_approve_execute_reconcile,
        test_3_failclosed_corrupt_state,
        test_4_oracle_override_llm_underestimate,
        test_5_kill_marker_blocks_all,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERR] ERROR: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n=== RESULTS: {passed}/{len(tests)} passed ===")
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
