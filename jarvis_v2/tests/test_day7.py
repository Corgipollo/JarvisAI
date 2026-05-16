"""test_day7.py - Day 7 components: research, github, ideation, heartbeat hooks.

No requiere red activa para tests basicos (uses mocks o cache).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def test_1_deep_research_cache():
    print("\n=== TEST 1: deep_research cache mechanism ===")
    from jarvis_v2.skills.deep_research import (
        _write_cache, _read_cache, _cache_key
    )
    q = "test_query_xyz_123"
    payload = {"query": q, "sources": [{"title": "fake", "url": "x"}],
                "raw_chunks": ["test"]}
    _write_cache(q, payload)
    got = _read_cache(q)
    assert got is not None, "Cache should hit"
    assert got["query"] == q
    print(f"  cache key: {_cache_key(q)}")
    print("  [OK] PASSED")


def test_2_github_search_no_token():
    """Sin token GH_TOKEN, search debe funcionar (60 req/h limit)."""
    print("\n=== TEST 2: GitHub search (anonymous) ===")
    from jarvis_v2.skills.github_explorer import search_trending
    repos = search_trending("langgraph", language="python",
                             min_stars=500, max_results=3)
    print(f"  found {len(repos)} repos")
    if repos:
        for r in repos:
            print(f"  - {r['full_name']} ({r['stars']}*)")
        assert all(r["stars"] >= 500 for r in repos)
        print("  [OK] PASSED")
    else:
        print("  [SKIP] No network or rate limited")


def test_3_ideation_pick_topic():
    print("\n=== TEST 3: ideation pick_topic ===")
    from jarvis_v2.core.ideation_engine import pick_topic, SEED_TOPICS
    topics = set()
    for _ in range(20):
        topics.add(pick_topic())
    print(f"  unique topics in 20 picks: {len(topics)}")
    assert len(topics) >= 2  # should sample multiple
    print("  [OK] PASSED")


def test_4_ideation_budget_check():
    print("\n=== TEST 4: ideation respects budget ===")
    from jarvis_v2.core.ideation_engine import get_remaining_budget
    budget = get_remaining_budget()
    print(f"  budget remaining: ${budget}")
    assert 0 <= budget <= 100
    print("  [OK] PASSED")


def test_5_status_board_write_read():
    print("\n=== TEST 5: status_board write/read ===")
    from jarvis_v2.core.ideation_engine import update_status_board, STATUS_BOARD
    update_status_board({
        "cycle_id": "test_123", "status": "TEST_RUN",
        "objective": "test write", "estimated_cost": 0.5,
    })
    assert STATUS_BOARD.exists()
    data = json.loads(STATUS_BOARD.read_text(encoding="utf-8"))
    assert data["latest"]["cycle_id"] == "test_123"
    print(f"  status_board has {len(data.get('history', []))} entries")
    print("  [OK] PASSED")


def test_6_voice_regex_patterns():
    print("\n=== TEST 6: voice regex (status & interrupt) ===")
    from jarvis_v2.voice.voice_daemon import STATUS_REGEX, INTERRUPT_REGEX

    # Status matches
    status_tests = [
        "dime como vas", "dame el reporte", "que estas haciendo",
        "como va jarvis", "status actual",
    ]
    for t in status_tests:
        assert STATUS_REGEX.search(t), f"Should match status: {t}"
    print(f"  status regex: {len(status_tests)}/{len(status_tests)} match")

    # Interrupt matches
    int_tests = ["cancela esto", "stop", "para todo", "abort"]
    for t in int_tests:
        assert INTERRUPT_REGEX.search(t), f"Should match interrupt: {t}"
    print(f"  interrupt regex: {len(int_tests)}/{len(int_tests)} match")

    # Negative
    assert not STATUS_REGEX.search("sube el video a youtube")
    assert not INTERRUPT_REGEX.search("compra btc")
    print("  [OK] PASSED")


def test_7_heartbeat_boredom_logic():
    print("\n=== TEST 7: heartbeat boredom detection ===")
    from jarvis_v2.heartbeat_daemon import is_bored, VOICE_ACTIVITY_LOG
    from datetime import datetime, timedelta

    # Empty / no log = bored
    if VOICE_ACTIVITY_LOG.exists():
        VOICE_ACTIVITY_LOG.unlink()
    assert is_bored(), "No log should mean bored"

    # Reciente = not bored
    VOICE_ACTIVITY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with VOICE_ACTIVITY_LOG.open("w", encoding="utf-8") as f:
        f.write(f"{datetime.utcnow().isoformat()} test\n")
    assert not is_bored(), "Recent activity should NOT be bored"

    # Viejo = bored
    with VOICE_ACTIVITY_LOG.open("w", encoding="utf-8") as f:
        old = (datetime.utcnow() - timedelta(hours=5)).isoformat()
        f.write(f"{old} old test\n")
    assert is_bored(), "5h old should be bored"
    print("  [OK] PASSED")


def main():
    tests = [
        test_1_deep_research_cache,
        test_2_github_search_no_token,
        test_3_ideation_pick_topic,
        test_4_ideation_budget_check,
        test_5_status_board_write_read,
        test_6_voice_regex_patterns,
        test_7_heartbeat_boredom_logic,
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
    print(f"\n=== RESULTS: {passed}/{len(tests)} passed ===")
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
