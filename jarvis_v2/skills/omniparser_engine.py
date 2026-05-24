"""omniparser_engine.py - Wrapper Jarvis sobre OmniParser v2.0.

API publica:
    parse(image) -> list[Element]
    where Element = {
        "bbox": (x1, y1, x2, y2),    # int pixels
        "center": (cx, cy),           # int pixels
        "type": str,                  # icon|text|button|... (YOLO class)
        "caption": str,               # Florence semantic description
        "interactable": bool,
        "confidence": float,
    }

    match(elements, description, top_k=1) -> list[Element]
        Busca semanticamente el elemento que mejor matchea la descripcion.

Tier 2 VRAM optimizations (2026-05-24):
- INT8 quantization via bitsandbytes (Florence-2 1GB -> ~250-500MB VRAM).
  Fallback automatico a FP16 si bitsandbytes no esta disponible (Windows
  + CUDA sin compilar a veces falla en imports).
- Auto-unload tras 5 min de inactividad. Thread daemon en background revisa
  cada 30s; si _last_used_ts > IDLE_UNLOAD_SECONDS, destruye modelos,
  llama gc.collect() y torch.cuda.empty_cache(). Re-load al proximo parse().
- GC agresivo post-inferencia: tras cada parse() libera tensores intermedios
  con gc + empty_cache para que VRAM no se acumule entre llamadas.

Hardware objetivo: RTX 3050 Laptop 4GB. Antes: 1GB+ constante.
Tras Tier 2: 250-500MB durante inferencia, 0MB en idle.
"""
from __future__ import annotations

import gc
import io
import os
import sys
import threading
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MODELS_DIR = ROOT / "models" / "omniparser"
# Repo HF expone subfolder 'icon_caption' (no 'icon_caption_florence') y
# el YOLO weight se llama 'model.pt' (no 'best.pt'). Verificado 2026-05-23.
YOLO_WEIGHTS = MODELS_DIR / "icon_detect" / "model.pt"
FLORENCE_DIR = MODELS_DIR / "icon_caption"

# Tier 2 config
IDLE_UNLOAD_SECONDS = int(os.environ.get("OMNIPARSER_IDLE_UNLOAD_SEC", "300"))
IDLE_CHECK_INTERVAL = 30
USE_INT8 = os.environ.get("OMNIPARSER_INT8", "1") not in ("0", "false", "False")

_yolo = None
_florence_proc = None
_florence_model = None
_device = None
_last_used_ts: float = 0.0
_lock = threading.Lock()
_unload_thread_started = False
_quant_mode = "uninitialized"  # informational: int8|fp16|fp32|none


def _device_pref() -> str:
    global _device
    if _device is not None:
        return _device
    try:
        import torch
        _device = "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        _device = "cpu"
    return _device


def _start_idle_watcher() -> None:
    """Background thread que descarga modelos tras IDLE_UNLOAD_SECONDS sin uso."""
    global _unload_thread_started
    if _unload_thread_started:
        return
    _unload_thread_started = True

    def _watcher():
        while True:
            time.sleep(IDLE_CHECK_INTERVAL)
            try:
                with _lock:
                    if _florence_model is None and _yolo is None:
                        continue
                    if _last_used_ts == 0:
                        continue
                    idle = time.time() - _last_used_ts
                    if idle >= IDLE_UNLOAD_SECONDS:
                        _unload_locked(reason=f"idle {int(idle)}s >= {IDLE_UNLOAD_SECONDS}s")
            except Exception as e:
                print(f"[omniparser] idle watcher error: {e}", flush=True)

    t = threading.Thread(target=_watcher, name="omniparser-idle-watcher", daemon=True)
    t.start()


def _unload_locked(reason: str = "manual") -> None:
    """Destruye modelos + libera VRAM. CALLER MUST HOLD _lock."""
    global _yolo, _florence_proc, _florence_model, _last_used_ts, _quant_mode
    if _yolo is None and _florence_model is None:
        return
    print(f"[omniparser] unloading models ({reason})", flush=True)
    _yolo = None
    _florence_proc = None
    _florence_model = None
    _last_used_ts = 0.0
    _quant_mode = "uninitialized"
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception:
        pass


def unload() -> None:
    """API publica: forzar descarga de modelos (libera VRAM ya)."""
    with _lock:
        _unload_locked(reason="explicit unload()")


def _try_int8_florence(florence_dir: Path):
    """Carga Florence-2 con bitsandbytes INT8. Devuelve (model, quant_mode_str)."""
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig
    bnb_config = BitsAndBytesConfig(
        load_in_8bit=True,
        llm_int8_threshold=6.0,
        llm_int8_has_fp16_weight=False,
    )
    model = AutoModelForCausalLM.from_pretrained(
        str(florence_dir),
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    return model, "int8"


def _lazy_load() -> None:
    """Carga YOLO + Florence en memoria. Tarda 5-10s la primera vez."""
    global _yolo, _florence_proc, _florence_model, _quant_mode
    with _lock:
        if _yolo is not None:
            return
        if not YOLO_WEIGHTS.exists():
            raise FileNotFoundError(
                f"YOLO weights missing: {YOLO_WEIGHTS}. "
                "Run scripts/download_omniparser.py first."
            )
        if not FLORENCE_DIR.exists():
            raise FileNotFoundError(
                f"Florence dir missing: {FLORENCE_DIR}. "
                "Run scripts/download_omniparser.py first."
            )

        from ultralytics import YOLO
        from transformers import AutoProcessor, AutoModelForCausalLM
        import torch

        dev = _device_pref()
        print(f"[omniparser] loading YOLO + Florence on {dev} (INT8={USE_INT8})...", flush=True)
        _yolo = YOLO(str(YOLO_WEIGHTS))
        _florence_proc = AutoProcessor.from_pretrained(
            "microsoft/Florence-2-base-ft", trust_remote_code=True
        )

        loaded = False
        if USE_INT8 and dev == "cuda":
            try:
                _florence_model, _quant_mode = _try_int8_florence(FLORENCE_DIR)
                loaded = True
                print("[omniparser] Florence-2 loaded INT8 via bitsandbytes", flush=True)
            except ImportError as e:
                print(f"[omniparser] bitsandbytes not available ({e}); falling back FP16", flush=True)
            except Exception as e:
                print(f"[omniparser] INT8 load failed ({e.__class__.__name__}: {e}); falling back FP16", flush=True)

        if not loaded:
            dtype = torch.float16 if dev == "cuda" else torch.float32
            _florence_model = AutoModelForCausalLM.from_pretrained(
                str(FLORENCE_DIR),
                torch_dtype=dtype,
                trust_remote_code=True,
            ).to(dev)
            _quant_mode = "fp16" if dev == "cuda" else "fp32"

        print(f"[omniparser] models loaded (quant={_quant_mode})", flush=True)
        _start_idle_watcher()


def _to_pil(image: Any) -> Image.Image:
    if isinstance(image, Image.Image):
        return image.convert("RGB")
    if isinstance(image, (str, Path)):
        return Image.open(image).convert("RGB")
    if isinstance(image, bytes):
        return Image.open(io.BytesIO(image)).convert("RGB")
    raise ValueError(f"Cannot convert {type(image)} to PIL.Image")


def _caption_crop(crop: Image.Image) -> str:
    """Florence-2 caption sobre un crop. ~400ms en GPU, ~2-3s en CPU."""
    dev = _device_pref()
    prompt = "<CAPTION>"
    inputs = _florence_proc(text=prompt, images=crop, return_tensors="pt").to(dev)
    import torch
    with torch.no_grad():
        generated = _florence_model.generate(
            input_ids=inputs["input_ids"],
            pixel_values=inputs["pixel_values"],
            max_new_tokens=48,
            num_beams=1,
            do_sample=False,
        )
    text = _florence_proc.batch_decode(generated, skip_special_tokens=False)[0]
    parsed = _florence_proc.post_process_generation(
        text, task=prompt, image_size=(crop.width, crop.height)
    )
    return parsed.get(prompt, "").strip()


def _is_interactable(class_name: str, conf: float) -> bool:
    interactive_types = {"button", "icon", "input", "checkbox", "tab",
                          "link", "menu", "dropdown"}
    return class_name.lower() in interactive_types or conf > 0.5


def _post_inference_cleanup() -> None:
    """GC agresivo post-parse: libera tensores intermedios sin descargar modelo."""
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def parse(image: Any, *, max_elements: int = 100,
          run_caption: bool = True) -> list[dict]:
    """Parsea screenshot completo a lista de Elements.

    Args:
        image: PIL.Image, path, bytes, o numpy array.
        max_elements: corte si YOLO detecta demasiados (default 100).
        run_caption: si False, salta Florence (solo bboxes + class). ~3x mas rapido.

    Returns:
        list[dict] con keys: bbox, center, type, caption, interactable, confidence.
    """
    global _last_used_ts
    _lazy_load()
    _last_used_ts = time.time()
    img = _to_pil(image)
    t0 = time.time()
    try:
        detections = _yolo(img, verbose=False)[0]
        boxes = detections.boxes
        out: list[dict] = []
        n = min(len(boxes), max_elements)
        for i in range(n):
            b = boxes[i]
            x1, y1, x2, y2 = [int(v) for v in b.xyxy[0].tolist()]
            cls = _yolo.names[int(b.cls[0])]
            conf = float(b.conf[0])
            caption = ""
            if run_caption:
                try:
                    caption = _caption_crop(img.crop((x1, y1, x2, y2)))
                except Exception as e:
                    caption = f"(caption_err: {e.__class__.__name__})"
            out.append({
                "bbox": (x1, y1, x2, y2),
                "center": ((x1 + x2) // 2, (y1 + y2) // 2),
                "type": cls,
                "caption": caption,
                "interactable": _is_interactable(cls, conf),
                "confidence": conf,
            })
        elapsed = int((time.time() - t0) * 1000)
        print(f"[omniparser] parsed {n} elements in {elapsed}ms (quant={_quant_mode})", flush=True)
        _last_used_ts = time.time()
        return out
    finally:
        _post_inference_cleanup()


@lru_cache(maxsize=1)
def _get_embedder():
    """Sentence-transformer ligero para semantic match."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def match(elements: list[dict], description: str,
          top_k: int = 1, min_score: float = 0.35) -> list[dict]:
    """Match semantico description -> elementos.

    Devuelve top_k elementos ordenados por cosine similarity, filtrados por
    min_score. Lista vacia si nada matchea.
    """
    if not elements:
        return []
    try:
        from sentence_transformers import util
        emb = _get_embedder()
        q_emb = emb.encode(description, convert_to_tensor=True)
        captions = [e.get("caption", "") or e.get("type", "") for e in elements]
        c_emb = emb.encode(captions, convert_to_tensor=True)
        scores = util.cos_sim(q_emb, c_emb)[0].tolist()
        ranked = sorted(zip(elements, scores), key=lambda x: -x[1])
        out = [{**el, "match_score": float(s)}
               for el, s in ranked[:top_k] if s >= min_score]
        return out
    except ImportError:
        # Fallback: substring match
        desc_low = description.lower()
        hits = [e for e in elements
                if desc_low in (e.get("caption", "").lower() + " " + e.get("type", "").lower())]
        return hits[:top_k]


def parse_screenshot_now(**kwargs) -> list[dict]:
    """Toma screenshot ahora y lo parsea. Usa mss (rapido)."""
    import mss
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # primary screen
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    return parse(img, **kwargs)


def vram_status() -> dict:
    """Diagnostico VRAM: cuanto usa Florence ahora, quant mode, idle time."""
    info = {"quant_mode": _quant_mode, "loaded": _florence_model is not None,
            "last_used_seconds_ago": (time.time() - _last_used_ts) if _last_used_ts else None,
            "idle_unload_after_sec": IDLE_UNLOAD_SECONDS}
    try:
        import torch
        if torch.cuda.is_available():
            info["vram_allocated_mb"] = round(torch.cuda.memory_allocated() / 1024**2, 1)
            info["vram_reserved_mb"] = round(torch.cuda.memory_reserved() / 1024**2, 1)
    except Exception:
        pass
    return info


if __name__ == "__main__":
    import json
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", help="path al screenshot. Si omitido, captura pantalla actual.")
    parser.add_argument("--match", help="descripcion a buscar tras parse.")
    parser.add_argument("--no-caption", action="store_true",
                        help="solo bboxes, sin Florence (faster).")
    parser.add_argument("--vram-status", action="store_true",
                        help="solo imprime estado VRAM y exit.")
    args = parser.parse_args()

    if args.vram_status:
        print(json.dumps(vram_status(), indent=2))
        sys.exit(0)

    if args.image:
        elements = parse(args.image, run_caption=not args.no_caption)
    else:
        elements = parse_screenshot_now(run_caption=not args.no_caption)

    if args.match:
        hits = match(elements, args.match, top_k=3)
        print(json.dumps(hits, ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(elements[:20], ensure_ascii=False, indent=2, default=str))

    print("\n--- VRAM status ---")
    print(json.dumps(vram_status(), indent=2))
