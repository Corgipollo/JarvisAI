"""ui_tars_service.py - Servicio FastAPI con UI-TARS en RTX 3050.

VM Jarvis POST screenshot + tarea → Devuelve (x, y) + accion.
Esto reemplaza Claude vision para clicks: 10x mas preciso, 0 costo, local.

Modelo default: ByteDance-Seed/UI-TARS-1.5-7B con int4 (cabe en 4GB VRAM).
Puerto: 8090. Acceso VM: http://10.0.2.2:8090
"""
from __future__ import annotations

import io
import os
import sys
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
import uvicorn
from PIL import Image

# Lazy-load to allow fast startup of FastAPI itself
MODEL = None
PROCESSOR = None

PORT = int(os.getenv("UI_TARS_PORT", "8090"))
MODEL_NAME = os.getenv("UI_TARS_MODEL", "ByteDance-Seed/UI-TARS-1.5-7B")

app = FastAPI(title="Jarvis UI-TARS Service")


def load_model():
    global MODEL, PROCESSOR
    if MODEL is not None:
        return
    print(f"[ui_tars] cargando {MODEL_NAME} con int4...", flush=True)
    import torch
    from transformers import (
        Qwen2VLForConditionalGeneration, AutoProcessor, BitsAndBytesConfig,
    )

    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
    )
    MODEL = Qwen2VLForConditionalGeneration.from_pretrained(
        MODEL_NAME,
        quantization_config=bnb,
        device_map="auto",
        torch_dtype=torch.float16,
    )
    PROCESSOR = AutoProcessor.from_pretrained(MODEL_NAME)
    print(f"[ui_tars] modelo listo en GPU", flush=True)


@app.get("/health")
def health():
    return {
        "ok": True,
        "model": MODEL_NAME,
        "model_loaded": MODEL is not None,
        "ts": datetime.now().isoformat(),
    }


@app.post("/predict_click")
async def predict_click(
    file: UploadFile = File(...),
    task: str = Form(...),
):
    """Recibe screenshot + tarea ('click on Save button'), devuelve {x, y}."""
    try:
        if MODEL is None:
            load_model()
        img_bytes = await file.read()
        img = Image.open(io.BytesIO(img_bytes))

        prompt = (
            f"Given the screenshot, perform: {task}\n"
            "Output the action as: click(x=N, y=N)"
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": img},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        from qwen_vl_utils import process_vision_info
        text = PROCESSOR.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = PROCESSOR(
            text=[text], images=image_inputs, videos=video_inputs,
            padding=True, return_tensors="pt",
        ).to("cuda")

        t0 = datetime.now()
        import torch
        with torch.no_grad():
            gen = MODEL.generate(**inputs, max_new_tokens=64, do_sample=False)
        gen_trimmed = gen[:, inputs.input_ids.shape[1]:]
        text_out = PROCESSOR.batch_decode(gen_trimmed, skip_special_tokens=True)[0]
        elapsed = (datetime.now() - t0).total_seconds()

        import re
        m = re.search(r"click\s*\(\s*x\s*=\s*(\d+)\s*,\s*y\s*=\s*(\d+)\s*\)", text_out)
        if not m:
            return {"raw": text_out, "elapsed_s": elapsed, "found": False}
        x, y = int(m.group(1)), int(m.group(2))
        w, h = img.size
        return {
            "x": x, "y": y, "x_pct": x / w * 100, "y_pct": y / h * 100,
            "found": True, "raw": text_out, "elapsed_s": elapsed,
            "img_w": w, "img_h": h,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    print(f"[ui_tars] arrancando en 0.0.0.0:{PORT} (VM via http://10.0.2.2:{PORT})", flush=True)
    print(f"[ui_tars] modelo se carga al primer request (lazy)", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
