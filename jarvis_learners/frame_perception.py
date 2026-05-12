"""frame_perception.py — Analisis frame-by-frame de tutoriales YouTube.

En vez de extraer un frame cada N segundos (pierde clicks rapidos),
extrae TODOS los keyframes (cambios visuales reales). Asi captura:
  - Cada click (cambia el highlight/cursor/elemento activo)
  - Cada apertura de ventana
  - Cada scroll significativo
  - Cada escritura (textbox cambia)

Pipeline por video:
  1. ffmpeg extrae todos los keyframes a frames/ (~500-2000 por video de 5min)
  2. perceptual hash (imagehash) descarta frames duplicados (queda 100-300)
  3. Tesseract OCR sobre cada frame (texto visible)
  4. Cluster por similitud temporal+visual
  5. Cada cluster va a Claude (con jarvis_brain.ask_claude_with_image) preguntando:
     "Que accion sucedio entre el frame anterior y este?"
  6. Output: lista de acciones temporales con (timestamp, ocr, accion_claude)

Eso le da al skill_learner los principios reales del tutorial,
no solo "snapshots aleatorios" cada 5 segundos.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg: str):
    print(f"[frame_perception] {msg}", flush=True)


# =============================================================================
# STEP 1: Extraer keyframes con ffmpeg
# =============================================================================
def extract_keyframes(video_path: Path, out_dir: Path, max_frames: int = 500) -> list[Path]:
    """Extrae keyframes (escenas que cambian visualmente).

    Usa filtro scenecut de ffmpeg con threshold 0.3 (cambio moderado).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    out_pattern = out_dir / "frame_%05d.jpg"

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(video_path),
        "-vf", "select='gt(scene,0.3)',showinfo",
        "-vsync", "vfr",
        "-q:v", "3",  # buena calidad sin pesar mucho
        "-frames:v", str(max_frames),
        str(out_pattern),
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except Exception as e:
        log(f"  ffmpeg fallo: {e}")
        return []
    return sorted(out_dir.glob("frame_*.jpg"))


# =============================================================================
# STEP 2: Descartar duplicados visuales (perceptual hash)
# =============================================================================
def deduplicate_frames(frames: list[Path], hash_threshold: int = 5) -> list[Path]:
    """Quita frames con phash muy similar al anterior."""
    try:
        from PIL import Image
        import imagehash
    except ImportError:
        log("  WARN: imagehash/PIL no instalado, devuelvo frames tal cual")
        return frames

    kept = []
    last_hash = None
    for f in frames:
        try:
            h = imagehash.phash(Image.open(f))
            if last_hash is None or (h - last_hash) > hash_threshold:
                kept.append(f)
                last_hash = h
        except Exception:
            kept.append(f)
    log(f"  dedup: {len(frames)} -> {len(kept)} frames unicos")
    return kept


# =============================================================================
# STEP 3: OCR cada frame
# =============================================================================
def ocr_frame(frame_path: Path) -> str:
    """Texto visible en el frame."""
    try:
        import pytesseract
        from PIL import Image
        return pytesseract.image_to_string(Image.open(frame_path), lang="eng+spa")[:500]
    except Exception:
        return ""


# =============================================================================
# STEP 4: Pedir a Claude que interprete cada transicion frame_n -> frame_n+1
# =============================================================================
def analyze_transition(prev_frame: Path, curr_frame: Path, prev_ocr: str, curr_ocr: str) -> str | None:
    """Pregunta a Claude que cambio entre 2 frames."""
    try:
        from jarvis_bridge.jarvis_brain import ask_claude_with_image
    except ImportError:
        return None

    prompt = (
        f"Compara estos 2 frames consecutivos de un tutorial Windows.\n"
        f"OCR frame anterior: {prev_ocr[:200]}\n"
        f"OCR frame actual:   {curr_ocr[:200]}\n\n"
        f"Pregunta: ¿Que accion sucedio entre ambos? "
        f"Responde en 1 oracion corta tipo: 'Abrio Telegram desde Start' "
        f"o 'Click en boton Send' o 'Tipeo nombre en search'. "
        f"Si no hay accion clara, di: 'sin cambio'."
    )
    # Solo mandamos el frame ACTUAL (el anterior va en OCR)
    return ask_claude_with_image(prompt, curr_frame, max_tokens=200)


# =============================================================================
# API publica
# =============================================================================
def analyze_video(video_path: Path, work_dir: Path | None = None,
                  max_keyframes: int = 200, deep: bool = False) -> dict:
    """Pipeline completo: video -> lista de acciones temporales.

    Args:
        deep: si True, analiza CADA transicion con Claude (caro pero preciso).
              si False, solo agrupa por OCR significativo.
    """
    video_path = Path(video_path)
    if work_dir is None:
        work_dir = video_path.parent / f"{video_path.stem}_analysis"
    work_dir.mkdir(parents=True, exist_ok=True)

    log(f"=== analyze_video: {video_path.name} ===")

    # 1. Keyframes
    log("[1] extrayendo keyframes...")
    frames_dir = work_dir / "frames"
    raw_frames = extract_keyframes(video_path, frames_dir, max_frames=max_keyframes)
    log(f"  {len(raw_frames)} keyframes")

    # 2. Dedup
    log("[2] deduplicando...")
    frames = deduplicate_frames(raw_frames)

    # 3. OCR
    log("[3] OCR cada frame...")
    ocr_results = []
    for i, f in enumerate(frames):
        text = ocr_frame(f)
        ocr_results.append({"index": i, "frame": str(f), "ocr": text})
    log(f"  OCR completo, {sum(1 for x in ocr_results if x['ocr']) } frames con texto")

    # 4. Transiciones
    transitions = []
    if deep:
        log(f"[4] analizando {len(frames)-1} transiciones con Claude (deep mode)...")
        for i in range(1, len(frames)):
            prev = ocr_results[i-1]
            curr = ocr_results[i]
            if prev["ocr"] == curr["ocr"]:
                continue  # mismo texto, skip
            action = analyze_transition(frames[i-1], frames[i], prev["ocr"], curr["ocr"])
            if action and "sin cambio" not in (action or "").lower():
                transitions.append({
                    "from_frame": i-1,
                    "to_frame": i,
                    "action": action,
                    "ocr_before": prev["ocr"][:100],
                    "ocr_after": curr["ocr"][:100],
                })
                log(f"    [{i}] {action[:80]}")
    else:
        # Modo rapido: solo guarda OCR diff
        for i in range(1, len(frames)):
            prev, curr = ocr_results[i-1], ocr_results[i]
            if prev["ocr"] != curr["ocr"] and curr["ocr"].strip():
                transitions.append({
                    "from_frame": i-1, "to_frame": i,
                    "ocr_diff_new": curr["ocr"][:200],
                })

    result = {
        "video": str(video_path),
        "total_keyframes": len(raw_frames),
        "unique_frames": len(frames),
        "frames": ocr_results,
        "transitions": transitions,
        "deep_analysis": deep,
    }
    out_json = work_dir / "analysis.json"
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"OK guardado en {out_json}")
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python frame_perception.py <video.mp4> [--deep]")
        sys.exit(0)
    deep = "--deep" in sys.argv
    video = [a for a in sys.argv[1:] if not a.startswith("--")][0]
    res = analyze_video(Path(video), deep=deep)
    print(json.dumps({
        "video": res["video"],
        "unique_frames": res["unique_frames"],
        "transitions": len(res["transitions"]),
    }, indent=2))
