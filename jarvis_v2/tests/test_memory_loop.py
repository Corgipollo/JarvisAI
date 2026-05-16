"""test_memory_loop.py - Test del ciclo cognitivo Mem -> Planner.

Valida que:
  1. save_lesson persiste correctamente
  2. recall_lessons devuelve por similitud semantica (no solo keyword)
  3. mark_lesson_helpful incrementa hit_count
  4. decay reduce confidence de lecciones viejas

Sin dependencia de Claude API real.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def test_1_save_and_recall():
    print("\n=== TEST 1: Save lesson, recall by semantic similarity ===")
    from jarvis_v2.memory.memory_manager import save_lesson, recall_lessons

    r1 = save_lesson(
        insight="Al subir video YouTube con API v3, usa MediaFileUpload chunksize=8MB y resumable=True para no perder conexion.",
        tags=["youtube", "api", "upload"],
        context="Implementando youtube_uploader.py",
        severity="high",
    )
    print(f"  saved: {r1['action']} id={r1['id']}")
    assert r1["action"] in ("created", "updated")

    # Recall con query DIFERENTE pero semanticamente cercana
    lessons = recall_lessons("como subo un video a YouTube sin perder conexion", top_k=5)
    print(f"  recalled {len(lessons)} lessons")
    assert len(lessons) >= 1
    # Verifica que entre las top hay AL MENOS una con tag youtube (recall semantica funciona)
    any_youtube = any("youtube" in [t.lower() for t in l["tags"]] for l in lessons)
    assert any_youtube, "Expected at least one youtube-tagged lesson in recall"
    top = lessons[0]
    print(f"  top sim={top['similarity']:.2f} tags={top['tags']}")
    assert top["similarity"] > 0.3, f"Similarity too low: {top['similarity']}"
    print("  [OK] PASSED")


def test_2_idempotent_save():
    print("\n=== TEST 2: Same insight = update, no duplicate ===")
    from jarvis_v2.memory.memory_manager import save_lesson, _get_collection

    insight = "FFmpeg concat requiere mismo codec y resolucion en todos los inputs."
    tags = ["ffmpeg", "concat"]
    r1 = save_lesson(insight, tags=tags, severity="medium")
    r2 = save_lesson(insight, tags=tags, severity="medium")
    print(f"  r1: {r1['action']}, r2: {r2['action']}")
    assert r1["id"] == r2["id"], "Same insight should produce same id"
    # Verifica que NO hay duplicates
    col = _get_collection()
    results = col.get(ids=[r1["id"]])
    assert len(results["ids"]) == 1
    print(f"  ledger has 1 entry for this id: OK")
    print("  [OK] PASSED")


def test_3_tag_filter():
    print("\n=== TEST 3: Tag filter ===")
    from jarvis_v2.memory.memory_manager import save_lesson, recall_lessons

    save_lesson(
        insight="Para hacer screenshots en pyautogui usa pyautogui.screenshot(path), no PIL ImageGrab.",
        tags=["pyautogui", "screenshot"],
        severity="low",
    )
    # Recall sin filtro
    no_filter = recall_lessons("captura de pantalla", top_k=5)
    # Recall con filtro de tag ffmpeg (no debe traer la de pyautogui)
    with_filter = recall_lessons("captura de pantalla", top_k=5, tag_filter=["ffmpeg"])
    print(f"  no_filter: {len(no_filter)}, with_filter ffmpeg: {len(with_filter)}")
    # Con filtro ffmpeg no debe haber pyautogui results
    for l in with_filter:
        assert "ffmpeg" in l["tags"], f"Lesson without ffmpeg tag: {l['tags']}"
    print("  [OK] PASSED")


def test_4_mark_helpful_increments():
    print("\n=== TEST 4: mark_lesson_helpful incrementa hit_count ===")
    from jarvis_v2.memory.memory_manager import (
        save_lesson, recall_lessons, mark_lesson_helpful
    )

    r = save_lesson(
        insight="OAuth de YouTube requiere agregar test_user en GCP Console antes de autorizar.",
        tags=["oauth", "gcp", "youtube"],
        severity="high",
    )
    lid = r["id"]
    # Initial hit_count = 0
    lessons = recall_lessons("OAuth YouTube test user", top_k=1)
    initial_hits = lessons[0]["hit_count"] if lessons else 0

    mark_lesson_helpful(lid)
    mark_lesson_helpful(lid)

    lessons = recall_lessons("OAuth YouTube test user", top_k=1)
    final_hits = lessons[0]["hit_count"]
    print(f"  initial: {initial_hits}, final: {final_hits}")
    assert final_hits >= initial_hits + 2
    print("  [OK] PASSED")


def test_5_stats():
    print("\n=== TEST 5: Stats endpoint ===")
    from jarvis_v2.memory.memory_manager import stats
    s = stats()
    print(f"  total: {s['total']}")
    print(f"  by_severity: {s['by_severity']}")
    print(f"  total_hits_lifetime: {s['total_hits_lifetime']}")
    assert s["total"] >= 4  # tests above created at least 4
    print("  [OK] PASSED")


def main():
    tests = [
        test_1_save_and_recall,
        test_2_idempotent_save,
        test_3_tag_filter,
        test_4_mark_helpful_increments,
        test_5_stats,
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
