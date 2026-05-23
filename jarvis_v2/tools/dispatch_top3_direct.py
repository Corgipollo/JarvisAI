"""dispatch_top3_direct.py - Ejecuta el dispatch TOP-3 sin pasar por el worker.

Worker condensa steps y el graph.execute_real no llega a file_write. Bypass:
  - Lee MOCs directo
  - Llama Gemini API (gemini-2.0-flash-exp) 1x por proyecto
  - Escribe 3 .md en data/reports/

Razon de bypass: 2 dispatches consecutivos a Jarvis V2 marcaron status=done con
result={} y 0 archivos creados. Bug separado del graph (planner condensa).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

VAULT = Path(r"C:\Users\Emmanuel\Documents\CerebroEmmanuel\01-Proyectos")
OUT_DIR = ROOT / "data" / "reports"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_env():
    env = ROOT / ".env"
    if not env.exists():
        return
    for ln in env.read_text(encoding="utf-8").splitlines():
        if "=" in ln and not ln.strip().startswith("#"):
            k, _, v = ln.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


load_env()
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
assert GEMINI_KEY, "GEMINI_API_KEY missing"


PROJECTS = [
    {
        "slug": "grop",
        "name": "GROP Ecommerce",
        "moc": VAULT / "GROP-Ecommerce" / "MOC - GROP Ecommerce.md",
        "extra_files": [
            VAULT / "GROP-Ecommerce" / "Plan 7 Dias - Primera Venta GROP.md",
            VAULT / "GROP-Ecommerce" / "FIX - grop.js TypeError querySelector null.md",
        ],
        "context": (
            "Stack: Shopify (grop-7604.myshopify.com), AutoDS, Judge.me, theme custom. "
            "50 productos activos. Pricing costo x2 + 1.45-1.80x por mercado. "
            "Repo local: 07-Codigo/grop-theme. "
            "Foco de negocio: flujo de caja directo, primera venta."
        ),
    },
    {
        "slug": "manhua",
        "name": "Manhua Narrado",
        "moc": VAULT / "Manhua-Narrado" / "MOC - Manhua Narrado.md",
        "extra_files": [
            VAULT / "Manhua-Narrado" / "GUIA-PRODUCCION-MANHWA.md",
        ],
        "context": (
            "Pipeline OCR + Gemini Vision + F5-TTS voice clone + ffmpeg Ken Burns + Edge TTS. "
            "Script canonico: auto_video_v6_vivienne_fixed.py (Ingeniero) + auto_video_v6_tbate.py. "
            "Path: C:/Users/Emmanuel/Manhua-Narrado/. "
            "Render NVENC 1080p. 1,348 paneles, 28/30 caps procesados. "
            "Estado V6/V7: 6 videos publicados, falta upgrade voz Edge TTS -> F5-TTS final."
        ),
    },
    {
        "slug": "video_clone",
        "name": "Video Clone Style (JCySharp)",
        "moc": VAULT / "Video-Clone-Style" / "MOC - Video Clone Style.md",
        "extra_files": [
            VAULT / "Video-Clone-Style" / "blueprint-replica.md",
        ],
        "context": (
            "Clonar formato JCySharp video viral 22 min ('Cuerpo Virtual a Gemini'). "
            "TODOs explicitos en MOC: VRoid Studio + VTube Studio setup, avatar Vtuber, "
            "mascota PNGs, Remotion HUD reutilizable, decidir tema (Claude / Bot Forex / GROP), "
            "guion 22 min 5 actos, storyboard 28 escenas, render Remotion. "
            "Fase 1 (validacion tecnica), Fase 2 (primer video), Fase 3 (template + serie)."
        ),
    },
]


def read_safely(p: Path, max_chars: int = 6000) -> str:
    if not p.exists():
        return f"[no existe: {p}]"
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
        if len(txt) > max_chars:
            return txt[:max_chars] + "\n\n[...TRUNCADO...]"
        return txt
    except Exception as e:
        return f"[read error: {e}]"


PROMPT_TEMPLATE = """Eres el ingeniero principal de Emmanuel Pedraza. Necesitas escribir un ROADMAP TECNICO ACCIONABLE para el proyecto '{name}'.

CONTEXTO DEL PROYECTO:
{context}

MOC del proyecto (notas Obsidian, fuente de verdad):
=================
{moc_content}
=================

ARCHIVOS COMPLEMENTARIOS:
{extra_content}

ENTREGABLE OBLIGATORIO — Roadmap markdown con esta estructura EXACTA (no agregues secciones, no preguntes, no preambulo):

# Roadmap Tecnico — {name}

## Estado actual
3-5 bullets honestos de donde esta el proyecto HOY (no historia).

## Bloqueadores reales
Los 2-3 problemas concretos que estan frenando avance. NO genericos. Cita archivos, commands, dependencias especificas.

## Pendientes priorizados (TOP 5)
Lista ordenada de 5 acciones tecnicas concretas que hay que ejecutar YA. Por cada una:
- **Accion**: que hacer en 1 linea
- **Archivos a tocar**: rutas absolutas o relativas exactas
- **Comandos**: comandos shell/python concretos
- **Tiempo estimado**: en minutos u horas
- **Criterio de exito**: medible (archivo X existe, comando Y devuelve Z, etc.)

## Quick wins (< 30 min)
2-3 acciones triviales que dan resultado visible inmediato.

## Notas finales
1-2 lineas con riesgo principal o cuello de botella latente.

REGLAS:
- Concreto, en espanol, sin disclaimers, sin "podria", siempre imperativo
- Si algo no se sabe del MOC, di "INFERIR" en lugar de inventar
- Comandos copy-pasteables reales (no pseudo-codigo)
- Max ~1200 palabras
- Output markdown puro, sin code fences alrededor del documento
"""


GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-2.0-flash",
]


def call_gemini_with_fallback(prompt: str) -> str:
    last_err = ""
    for model in GEMINI_MODELS:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={GEMINI_KEY}"
        )
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 4096,
            },
        }
        try:
            with httpx.Client(timeout=90) as cli:
                r = cli.post(url, json=payload)
        except Exception as e:
            last_err = f"http_exc {model}: {e}"
            continue
        if r.status_code == 200:
            try:
                data = r.json()
                txt = data["candidates"][0]["content"]["parts"][0]["text"]
                print(f"    OK via {model}", flush=True)
                return txt
            except Exception as e:
                last_err = f"parse {model}: {e}"
                continue
        last_err = f"{model} http {r.status_code}"
        print(f"    fail {last_err}, trying next", flush=True)
    return f"[gemini todos fallaron. last={last_err}]"


def call_gemini(prompt: str, model: str = "ignored") -> str:
    return call_gemini_with_fallback(prompt)


def call_brain(prompt: str) -> str:
    """Usa jarvis_brain.ask_claude (cascading: openrouter -> anthropic_proxy -> gemini)."""
    from jarvis_bridge.jarvis_brain import ask_claude
    system = (
        "Eres el ingeniero principal de Emmanuel. Generas roadmaps tecnicos "
        "concretos, accionables, en espanol, sin preamble, sin disclaimers, "
        "siempre imperativo. Output markdown puro."
    )
    out = ask_claude(prompt, system=system, max_tokens=4000, retries=2,
                      timeout=120)
    if not out:
        return "[brain ALL_PROVIDERS_FAILED]"
    return out


def build_prompt(proj: dict) -> str:
    moc_content = read_safely(proj["moc"])
    extras = []
    for ef in proj.get("extra_files", []):
        extras.append(f"### {ef.name}\n{read_safely(ef, max_chars=3000)}")
    extra_content = "\n\n".join(extras) if extras else "[ninguno]"
    return PROMPT_TEMPLATE.format(
        name=proj["name"],
        context=proj["context"],
        moc_content=moc_content,
        extra_content=extra_content,
    )


def main():
    results = []
    for proj in PROJECTS:
        print(f"\n=== {proj['name']} ===", flush=True)
        prompt = build_prompt(proj)
        print(f"  prompt {len(prompt)} chars -> brain (cascading)...", flush=True)
        body = call_brain(prompt)
        if body.startswith("[brain"):
            print(f"    brain fallo, trying gemini direct fallback", flush=True)
            body = call_gemini(prompt)
        out = OUT_DIR / f"roadmap_{proj['slug']}.md"
        out.write_text(body, encoding="utf-8")
        size = out.stat().st_size
        ok = size > 500 and not body.startswith("[gemini http")
        print(f"  {'OK' if ok else 'FAIL'} {out} ({size}b)", flush=True)
        results.append({"proj": proj["slug"], "ok": ok, "path": str(out),
                        "size": size})

    # Summary
    summary_path = OUT_DIR / "dispatch_top3_summary.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    print(f"\n=== Summary: {summary_path} ===", flush=True)
    for r in results:
        print(f"  {'[OK]' if r['ok'] else '[FAIL]'} {r['proj']}: {r['size']}b")


if __name__ == "__main__":
    main()
