"""whisper_gpu_service.py — Servicio FastAPI en HOST que transcribe usando RTX 3050 CUDA.

VM Jarvis hace POST /transcribe con archivo de audio/video.
Host transcribe en GPU (5-10x mas rapido que CPU int8).

Run: python whisper_gpu_service.py
Default port: 8089. Accesible desde VM via http://10.0.2.2:8089 (gateway NAT VirtualBox).
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

from faster_whisper import WhisperModel

PORT = int(os.getenv("WHISPER_GPU_PORT", "8089"))
MODEL_SIZE = os.getenv("WHISPER_GPU_MODEL", "base")
DEVICE = os.getenv("WHISPER_GPU_DEVICE", "cuda")
COMPUTE_TYPE = os.getenv("WHISPER_GPU_COMPUTE", "float16")

app = FastAPI(title="Jarvis Whisper GPU Service")

print(f"[whisper_gpu] cargando modelo {MODEL_SIZE} en {DEVICE} ({COMPUTE_TYPE})...", flush=True)
try:
    MODEL = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    print(f"[whisper_gpu] modelo cargado OK", flush=True)
except Exception as e:
    print(f"[whisper_gpu] CUDA fallo, fallback CPU int8: {e}", flush=True)
    MODEL = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")


@app.get("/health")
def health():
    return {
        "ok": True,
        "model": MODEL_SIZE,
        "device": DEVICE,
        "compute_type": COMPUTE_TYPE,
        "ts": datetime.now().isoformat(),
    }


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """Recibe audio/video, transcribe, retorna texto."""
    try:
        suffix = Path(file.filename or "audio").suffix or ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            data = await file.read()
            tmp.write(data)
            tmp_path = tmp.name

        size_mb = len(data) / 1e6
        t0 = datetime.now()
        print(f"[whisper_gpu] {datetime.now().strftime('%H:%M:%S')} transcribing {file.filename} ({size_mb:.1f} MB)", flush=True)

        segs, info = MODEL.transcribe(
            tmp_path,
            language=None,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        text_chunks = [s.text.strip() for s in segs]
        full_text = " ".join(text_chunks)

        elapsed = (datetime.now() - t0).total_seconds()
        print(f"[whisper_gpu]   done in {elapsed:.1f}s ({size_mb/max(elapsed,0.1):.1f} MB/s), {len(text_chunks)} chunks", flush=True)

        try:
            os.unlink(tmp_path)
        except Exception:
            pass

        return {
            "text": full_text,
            "language": info.language if info else "unknown",
            "duration_s": info.duration if info else 0,
            "chunks": len(text_chunks),
            "elapsed_s": elapsed,
        }
    except Exception as e:
        print(f"[whisper_gpu] error: {e}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    print(f"[whisper_gpu] arrancando en 0.0.0.0:{PORT} (VM accede via http://10.0.2.2:{PORT})", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
