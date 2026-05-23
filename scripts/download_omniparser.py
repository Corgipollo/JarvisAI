"""download_omniparser.py - Descarga pesos OmniParser v2.0 desde HuggingFace.

Total: ~1.2 GB en models/omniparser/
  icon_detect/        - YOLO weights (~200 MB)
  icon_caption_florence/ - Florence-2 fine-tuned (~1 GB)

Idempotente: skip si ya existe local.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "models" / "omniparser"
TARGET.mkdir(parents=True, exist_ok=True)


def main():
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        import subprocess
        print("[download] installing huggingface_hub...", flush=True)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-q", "huggingface_hub"]
        )
        from huggingface_hub import snapshot_download

    print(f"[download] target: {TARGET}", flush=True)
    print("[download] starting snapshot from microsoft/OmniParser-v2.0...",
          flush=True)
    # NOTA: el repo expone subfolder 'icon_caption' (no 'icon_caption_florence').
    # Sin allow_patterns para garantizar todos los safetensors.
    path = snapshot_download(
        repo_id="microsoft/OmniParser-v2.0",
        local_dir=str(TARGET),
    )
    print(f"[download] OK: {path}", flush=True)

    # Sanity check
    icon_detect = TARGET / "icon_detect"
    caption = TARGET / "icon_caption_florence"
    print(f"[download] icon_detect: {icon_detect.exists()} files={len(list(icon_detect.glob('*')))}",
          flush=True)
    print(f"[download] icon_caption_florence: {caption.exists()} files={len(list(caption.glob('*')))}",
          flush=True)


if __name__ == "__main__":
    main()
