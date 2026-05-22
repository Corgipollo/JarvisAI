"""skill_creator.py - Auto-generador de skills para Jarvis.

Flujo:
  1. recibe (skill_name, specification)
  2. genera codigo Python production-grade via LLM (Haiku por default, Sonnet si
     specification incluye 'COMPLEJO')
  3. genera test pytest/unittest aislado
  4. ejecuta el test en subprocess con timeout
  5. si falla: re-prompt al LLM con stderr + codigo previo, hasta 3 intentos
  6. si pasa: git add + commit + push
  7. devuelve dict con resultado completo

Restricciones de seguridad:
  - Rechaza skill_name con patrones destructivos (rmdir, del /s, shutil.rmtree
    sin path absoluto, modificacion de jarvis_v2/core/graph.py o similar)
  - Sandbox: subprocess.run timeout 60s
  - Max archivo generado: 15000 chars

Uso:
  from jarvis_v2.skills.skill_creator import create_autonomous_skill
  r = create_autonomous_skill(
      "instagram_scraper",
      "Skill que dado un username de Instagram publico devuelve dict con "
      "follower_count, post_count, bio. Usa requests + bs4. Sin selenium."
  )
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "jarvis_v2" / "skills"
TESTS_DIR = ROOT / "tests"
LOG_PATH = ROOT / "data" / "skill_creator.log"

DESTRUCTIVE_PATTERNS = [
    r"shutil\.rmtree\s*\(\s*(?:Path\.home\(\)|os\.environ|['\"]\.\.|['\"]C:)",
    r"rm\s+-rf?\s+/",
    r"rmdir\s+/[Ss]\s+[A-Z]:",
    r"format\s*\(\s*['\"]C:",
    r"os\.system\s*\(\s*['\"]?\s*(?:rm\s|del\s)",
    r"subprocess\.\w+\(.*?(?:rm\s+-rf|del\s+/[Ss])",
]
CORE_PATHS_FORBIDDEN = ["jarvis_v2/core/", "jarvis_v2/cfo/", "jarvis_bridge/"]


def _log(msg: str):
    line = f"[{datetime.utcnow().isoformat()}] {msg}"
    print(line, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _validate_skill_name(name: str) -> tuple[bool, str]:
    if not re.match(r"^[a-z][a-z0-9_]{2,40}$", name):
        return False, "name must be snake_case 3-40 chars [a-z0-9_], lowercase start"
    if name in ("graph", "schemas", "llm_structured", "jarvis_brain",
                 "cfo_evaluator", "cost_oracle"):
        return False, "reserved core name"
    return True, "ok"


def _safety_check_code(code: str, target_path: Path) -> tuple[bool, str]:
    """Rechaza codigo destructivo."""
    for pat in DESTRUCTIVE_PATTERNS:
        if re.search(pat, code, re.IGNORECASE):
            return False, f"destructive pattern matched: {pat}"
    # Target path no puede tocar core (acepta absolute o relative-to-ROOT)
    try:
        rel = target_path.resolve().relative_to(ROOT.resolve())
        rel_str = str(rel).replace("\\", "/")
    except (ValueError, OSError):
        rel_str = str(target_path).replace("\\", "/")
    for forbidden in CORE_PATHS_FORBIDDEN:
        if rel_str.startswith(forbidden) or f"/{forbidden}" in rel_str:
            return False, f"cannot write to forbidden path: {forbidden}"
    # Limite tamano
    if len(code) > 15000:
        return False, f"file too large: {len(code)} chars (max 15000)"
    return True, "ok"


def _extract_python_code(text: str) -> str:
    """Saca el bloque ```python...``` o devuelve text completo si parece Python."""
    m = re.search(r"```(?:python|py)?\s*\n([\s\S]*?)\n```", text)
    if m:
        return m.group(1).strip()
    # Asume todo el text es Python si empieza con import/def/class
    stripped = text.strip()
    if re.match(r"^(from|import|def |class |\"\"\"|#)", stripped):
        return stripped
    return text.strip()


def _llm_generate(prompt: str, system: str, use_heavy: bool = False) -> str | None:
    """Llama LLM con router dinamico. use_heavy=True -> forza Sonnet."""
    from jarvis_bridge.jarvis_brain import ask_claude
    # Marca explicita para que _route_model elija Sonnet si use_heavy
    if use_heavy and "MODO INGENIERO" not in system:
        system = "MODO INGENIERO. " + system
    return ask_claude(prompt, system=system, max_tokens=6000, retries=1,
                       timeout=180)


def _gen_skill_code(skill_name: str, specification: str,
                     use_heavy: bool, prev_error: str = "") -> str | None:
    """Llama LLM y devuelve codigo Python limpio."""
    system = (
        "Eres ingeniero senior Python 3.10+ Windows. Generas skill production-grade "
        "para Jarvis V2. REGLAS DURAS:\n"
        "- PEP 8, type hints completos, docstrings.\n"
        "- Try/except en I/O, network, subprocess.\n"
        "- Solo stdlib + requests/httpx + pathlib (no instalar deps exoticas).\n"
        "- Sin placeholders, sin TODO, sin '// resto del codigo'.\n"
        "- Exporta funciones publicas con nombres claros.\n"
        "- if __name__ == '__main__': smoke test minimo.\n"
        "- PROHIBIDO: shutil.rmtree de paths absolutos, rm -rf, os.system destructivo.\n"
        "- Devuelve SOLO el bloque ```python ...``` sin preamble."
    )
    fix_note = ""
    if prev_error:
        fix_note = (f"\n\nEL INTENTO ANTERIOR FALLO. Test stderr:\n```\n"
                    f"{prev_error[:2000]}\n```\nCorrige el codigo.")
    prompt = (
        f"Crea skill 'jarvis_v2/skills/{skill_name}.py'.\n\n"
        f"ESPECIFICACION:\n{specification}\n"
        f"{fix_note}\n\n"
        f"Devuelve SOLO el archivo Python completo en bloque ```python```."
    )
    raw = _llm_generate(prompt, system, use_heavy=use_heavy)
    if not raw:
        return None
    return _extract_python_code(raw)


def _gen_test_code(skill_name: str, skill_code: str, use_heavy: bool) -> str | None:
    """Genera test pytest aislado para la skill."""
    system = (
        "Eres ingeniero QA Python 3.10+. Generas test pytest aislado.\n"
        "REGLAS DURAS:\n"
        "- PRIMERA LINEA DE IMPORTS (obligatorio, exacto):\n"
        "    import sys\n"
        "    from pathlib import Path\n"
        "    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n"
        "- Luego importa la skill: from jarvis_v2.skills.NAME import funcion\n"
        "- Usa unittest.mock.patch para mockear network/disk si la skill los usa.\n"
        "- Ejecuta logica local real de la skill (no mockees TODO).\n"
        "- Al menos 2 tests con prefix 'def test_': smoke + edge case.\n"
        "- NO uses fixtures complicadas. NO uses conftest.py.\n"
        "- Devuelve SOLO bloque ```python ...```."
    )
    prompt = (
        f"Crea pytest test para 'jarvis_v2/skills/{skill_name}.py'.\n\n"
        f"CODIGO DE LA SKILL:\n```python\n{skill_code[:4000]}\n```\n\n"
        f"Usa exactamente este import path:\n"
        f"  from jarvis_v2.skills.{skill_name} import <funcion>\n\n"
        f"Devuelve SOLO el bloque python."
    )
    raw = _llm_generate(prompt, system, use_heavy=use_heavy)
    if not raw:
        return None
    return _extract_python_code(raw)


def _run_test(test_path: Path, timeout: int = 60) -> tuple[bool, str]:
    """Ejecuta pytest en subprocess aislado. Devuelve (passed, stderr)."""
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_path), "-x", "-q",
             "--tb=short"],
            capture_output=True, text=True, timeout=timeout, cwd=ROOT,
            encoding="utf-8", errors="replace",
        )
        if r.returncode == 0:
            return True, ""
        return False, (r.stdout + "\n" + r.stderr)[-2000:]
    except subprocess.TimeoutExpired:
        return False, f"test timeout after {timeout}s"
    except Exception as e:
        return False, f"test exec error: {e}"


def _git_commit_push(skill_path: Path, test_path: Path,
                      skill_name: str) -> dict:
    """git add + commit + push del skill nuevo + su test."""
    rel_skill = skill_path.relative_to(ROOT)
    rel_test = test_path.relative_to(ROOT)
    try:
        subprocess.run(["git", "add", str(rel_skill), str(rel_test)],
                       cwd=ROOT, capture_output=True, check=True)
        msg = (f"feat(skills): auto-generated skill {skill_name} with verified "
               f"unit tests\n\nAutonomamente generado por "
               f"jarvis_v2.skills.skill_creator")
        c = subprocess.run(["git", "commit", "-m", msg], cwd=ROOT,
                            capture_output=True, text=True)
        if c.returncode != 0:
            return {"committed": False, "error": c.stderr[:200]}
        h = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
        p = subprocess.run(["git", "push", "origin", "master"], cwd=ROOT,
                            capture_output=True, text=True)
        return {"committed": True, "hash": h,
                "pushed": p.returncode == 0,
                "push_err": p.stderr[:200] if p.returncode != 0 else ""}
    except subprocess.CalledProcessError as e:
        return {"committed": False, "error": f"git: {e}"}


def create_autonomous_skill(skill_name: str, specification: str,
                              do_push: bool = True,
                              max_attempts: int = 3) -> dict:
    """Genera skill nueva + test + valida + commit.

    Args:
        skill_name: snake_case identifier (ej: 'instagram_scraper').
        specification: descripcion natural de lo que hace.
        do_push: True para git add+commit+push, False para solo crear.
        max_attempts: ciclos de auto-correccion (default 3).

    Returns: dict con {ok, skill_path, test_path, attempts, error, commit}.
    """
    _log(f"=== create_autonomous_skill: {skill_name} ===")
    _log(f"spec head: {specification[:100]}")

    # Validate name
    valid, reason = _validate_skill_name(skill_name)
    if not valid:
        return {"ok": False, "step": "validate_name", "error": reason}

    skill_path = SKILLS_DIR / f"{skill_name}.py"
    if skill_path.exists():
        return {"ok": False, "step": "exists",
                "error": f"skill ya existe: {skill_path.name}"}
    test_path = TESTS_DIR / f"test_{skill_name}.py"

    use_heavy = "COMPLEJO" in specification.upper()
    _log(f"router: {'Sonnet' if use_heavy else 'Haiku'}")

    prev_stderr = ""
    skill_code = None
    test_code = None

    for attempt in range(1, max_attempts + 1):
        _log(f"--- attempt {attempt}/{max_attempts} ---")

        # Step 1: gen skill code
        skill_code = _gen_skill_code(skill_name, specification, use_heavy,
                                        prev_error=prev_stderr)
        if not skill_code:
            _log(f"  LLM no devolvio skill code")
            continue
        # Safety check
        ok, reason = _safety_check_code(skill_code, skill_path)
        if not ok:
            _log(f"  safety check FAIL: {reason}")
            return {"ok": False, "step": "safety_skill", "error": reason}

        # Step 2: gen test code
        test_code = _gen_test_code(skill_name, skill_code, use_heavy)
        if not test_code:
            _log(f"  LLM no devolvio test code")
            continue
        ok, reason = _safety_check_code(test_code, test_path)
        if not ok:
            _log(f"  safety check FAIL test: {reason}")
            return {"ok": False, "step": "safety_test", "error": reason}

        # Step 3: write to disk
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        TESTS_DIR.mkdir(parents=True, exist_ok=True)
        skill_path.write_text(skill_code, encoding="utf-8")
        test_path.write_text(test_code, encoding="utf-8")
        _log(f"  wrote {skill_path.name} ({len(skill_code)}c) + "
              f"{test_path.name} ({len(test_code)}c)")

        # Step 4: syntax check
        sc = subprocess.run([sys.executable, "-m", "py_compile",
                              str(skill_path)],
                             capture_output=True, text=True)
        if sc.returncode != 0:
            prev_stderr = f"SYNTAX ERROR skill:\n{sc.stderr}"
            _log(f"  syntax skill FAIL")
            # cleanup para reintento
            skill_path.unlink(missing_ok=True)
            test_path.unlink(missing_ok=True)
            continue
        sc = subprocess.run([sys.executable, "-m", "py_compile",
                              str(test_path)],
                             capture_output=True, text=True)
        if sc.returncode != 0:
            prev_stderr = f"SYNTAX ERROR test:\n{sc.stderr}"
            _log(f"  syntax test FAIL")
            skill_path.unlink(missing_ok=True)
            test_path.unlink(missing_ok=True)
            continue

        # Step 5: run test
        passed, stderr = _run_test(test_path)
        if passed:
            _log(f"  TEST PASSED attempt {attempt}")
            commit_info = {}
            if do_push:
                commit_info = _git_commit_push(skill_path, test_path,
                                                 skill_name)
                _log(f"  commit: {commit_info}")
            return {
                "ok": True, "step": "complete",
                "attempts": attempt,
                "skill_path": str(skill_path.relative_to(ROOT)),
                "test_path": str(test_path.relative_to(ROOT)),
                "skill_lines": skill_code.count("\n") + 1,
                "test_lines": test_code.count("\n") + 1,
                "commit": commit_info,
            }
        prev_stderr = stderr
        _log(f"  TEST FAIL stderr head: {stderr[:150]}")
        # cleanup para reintento (los re-escribimos)
        skill_path.unlink(missing_ok=True)
        test_path.unlink(missing_ok=True)

    return {"ok": False, "step": "max_attempts_exhausted",
            "attempts": max_attempts,
            "last_error": prev_stderr[:500]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("name", help="snake_case skill name")
    ap.add_argument("--spec", required=True, help="natural language spec")
    ap.add_argument("--no-push", action="store_true")
    args = ap.parse_args()
    r = create_autonomous_skill(args.name, args.spec,
                                  do_push=not args.no_push)
    print(json.dumps(r, ensure_ascii=False, indent=2))
