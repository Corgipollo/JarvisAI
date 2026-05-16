"""test_swarm.py - Smoke tests del swarm concurrent."""
from __future__ import annotations

import asyncio
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def test_1_human_mouse_lock_singleton():
    print("\n=== TEST 1: gui_mouse_lock es singleton compartido ===")
    from jarvis_v2.swarm.human_mouse import gui_mouse_lock
    from jarvis_v2.swarm.human_mouse import gui_mouse_lock as lock2
    assert gui_mouse_lock is lock2, "Lock should be singleton"
    print("  [OK] PASSED")


def test_2_lock_blocks_concurrent():
    print("\n=== TEST 2: lock blocks 2 threads from mouse simultaneously ===")
    from jarvis_v2.swarm.human_mouse import gui_mouse_lock
    timeline = []

    def worker_a():
        with gui_mouse_lock:
            timeline.append(("A", "in", time.time()))
            time.sleep(0.3)
            timeline.append(("A", "out", time.time()))

    def worker_b():
        time.sleep(0.05)  # Start slightly after A
        with gui_mouse_lock:
            timeline.append(("B", "in", time.time()))
            time.sleep(0.1)
            timeline.append(("B", "out", time.time()))

    ta = threading.Thread(target=worker_a)
    tb = threading.Thread(target=worker_b)
    ta.start(); tb.start()
    ta.join(); tb.join()

    # A entra primero, sale, luego B entra
    assert timeline[0] == ("A", "in", timeline[0][2])
    assert timeline[1] == ("A", "out", timeline[1][2])
    assert timeline[2] == ("B", "in", timeline[2][2])
    assert timeline[3] == ("B", "out", timeline[3][2])
    print("  [OK] PASSED")


def test_3_orchestrator_starts_stops_clean():
    print("\n=== TEST 3: orchestrator inicia y se detiene limpio ===")
    from jarvis_v2.swarm.orchestrator import SwarmOrchestrator, write_status

    async def _run():
        swarm = SwarmOrchestrator(enable={"sentinel": True,
                                           "secretary": False,
                                           "creative": False})
        task = asyncio.create_task(swarm.run())
        await asyncio.sleep(2)  # let sentinel tick
        swarm.request_stop()
        try:
            await asyncio.wait_for(task, timeout=10)
        except asyncio.TimeoutError:
            pass
        return swarm

    s = asyncio.run(_run())
    assert s.stop_event.is_set()
    print("  [OK] PASSED")


def test_4_extendscript_generation():
    print("\n=== TEST 4: extendscript generation ===")
    from jarvis_v2.swarm.creative_worker import generate_extendscript
    jsx = generate_extendscript(
        template_aep="C:\\path\\to\\template.aep",
        output_path="C:\\path\\to\\out.mp4",
        variables={"Title": 'Hello "world"', "Subtitle": "sub"},
    )
    assert "setTextLayer" in jsx
    assert "C:\\\\path\\\\to\\\\template.aep" in jsx  # backslash escaped
    assert 'Hello \\"world\\"' in jsx  # quote escaped
    print(f"  jsx length: {len(jsx)} chars")
    print("  [OK] PASSED")


def test_5_status_board_atomic_write():
    print("\n=== TEST 5: status board updates from multiple writers ===")
    from jarvis_v2.swarm.orchestrator import write_status, STATUS_BOARD
    import json

    write_status("dept_a", {"status": "running", "v": 1})
    write_status("dept_b", {"status": "idle", "v": 2})
    write_status("dept_a", {"status": "done", "v": 3})

    assert STATUS_BOARD.exists()
    data = json.loads(STATUS_BOARD.read_text(encoding="utf-8"))
    assert "departments" in data
    assert data["departments"]["dept_a"]["v"] == 3  # last write wins
    assert data["departments"]["dept_b"]["v"] == 2
    print(f"  departments: {list(data['departments'].keys())}")
    print("  [OK] PASSED")


def main():
    tests = [
        test_1_human_mouse_lock_singleton,
        test_2_lock_blocks_concurrent,
        test_3_orchestrator_starts_stops_clean,
        test_4_extendscript_generation,
        test_5_status_board_atomic_write,
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
    sys.exit(0 if main() else 1)
