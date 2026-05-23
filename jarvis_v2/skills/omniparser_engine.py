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

Modelos cargados lazy en primer parse() para no pagar startup cost cuando
no se usa. GPU si disponible, CPU fallback.
"""
from __future__ import annotations

import io
import os
import sys
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

_yolo = None
_florence_proc = None
_florence_model = None
_device = None


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


def _lazy_load() -> None:
    """Carga YOLO + Florence en memoria. Tarda 5-10s la primera vez."""
    global _yolo, _florence_proc, _florence_model
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
    print(f"[omniparser] loading YOLO + Florence on {dev}...", flush=True)
    _yolo = YOLO(str(YOLO_WEIGHTS))
    # OmniParser fine-tunea Florence-2-base-ft. El processor vive en el base
    # de HF (microsoft/Florence-2-base-ft) - lo bajamos al primer load (~150MB),
    # los WEIGHTS los cargamos desde local (los 1.08GB que ya tenemos).
    _florence_proc = AutoProcessor.from_pretrained(
        "microsoft/Florence-2-base-ft", trust_remote_code=True
    )
    dtype = torch.float16 if dev == "cuda" else torch.float32
    _florence_model = AutoModelForCausalLM.from_pretrained(
        str(FLORENCE_DIR),
        torch_dtype=dtype,
        trust_remote_code=True,
    ).to(dev)
    print("[omniparser] models loaded", flush=True)


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
    _lazy_load()
    img = _to_pil(image)
    t0 = time.time()
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
    print(f"[omniparser] parsed {n} elements in {elapsed}ms", flush=True)
    return out


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


if __name__ == "__main__":
    import json
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", help="path al screenshot. Si omitido, captura pantalla actual.")
    parser.add_argument("--match", help="descripcion a buscar tras parse.")
    parser.add_argument("--no-caption", action="store_true",
                        help="solo bboxes, sin Florence (faster).")
    args = parser.parse_args()

    if args.image:
        elements = parse(args.image, run_caption=not args.no_caption)
    else:
        elements = parse_screenshot_now(run_caption=not args.no_caption)

    if args.match:
        hits = match(elements, args.match, top_k=3)
        print(json.dumps(hits, ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(elements[:20], ensure_ascii=False, indent=2, default=str))
