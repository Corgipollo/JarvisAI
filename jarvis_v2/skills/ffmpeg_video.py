"""ffmpeg_video.py - Edicion de video por CLI (FFmpeg + Remotion).

Operaciones:
  - cut(input, start, end, output) -> recorta
  - concat([videos], output) -> concatena
  - thumbnail(input, time, output) -> extrae frame como JPG
  - resize(input, w, h, output)
  - add_audio(video, audio, output)
  - speed(input, factor, output)
  - render_remotion(project_dir, props, output) -> render programatico
  - probe(input) -> info del video (duracion, resolucion, fps)

Sin GUI, sin abrir CapCut. Todo CLI.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run(cmd: list[str], timeout: int = 600) -> dict:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            return {"ok": False, "error": r.stderr[-500:]}
        return {"ok": True, "stdout": r.stdout[-500:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def probe(video_path: str) -> dict:
    """Info del video via ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", video_path,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return {"ok": False, "error": r.stderr[-300:]}
        data = json.loads(r.stdout)
        # Extract useful info
        fmt = data.get("format", {})
        streams = data.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), {})
        audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
        return {
            "ok": True,
            "duration_s": float(fmt.get("duration", 0)),
            "size_mb": int(fmt.get("size", 0)) / 1e6,
            "width": int(video.get("width", 0)),
            "height": int(video.get("height", 0)),
            "fps": eval(video.get("r_frame_rate", "0/1")) if video.get("r_frame_rate") else 0,
            "video_codec": video.get("codec_name", ""),
            "audio_codec": audio.get("codec_name", ""),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def cut(input_path: str, start_s: float, end_s: float, output_path: str) -> dict:
    """Recorta del segundo start al end."""
    duration = end_s - start_s
    cmd = [
        "ffmpeg", "-y", "-ss", str(start_s), "-i", input_path,
        "-t", str(duration), "-c", "copy", output_path,
    ]
    return _run(cmd)


def concat(video_paths: list[str], output_path: str) -> dict:
    """Concatena videos. Requiere mismo codec/resolucion."""
    # Create list file
    list_file = Path(output_path).with_suffix(".concat.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for v in video_paths:
            f.write(f"file '{Path(v).as_posix()}'\n")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", output_path,
    ]
    res = _run(cmd)
    try:
        list_file.unlink()
    except Exception:
        pass
    return res


def thumbnail(input_path: str, time_s: float, output_path: str,
              width: int = 1280) -> dict:
    """Extrae frame en time_s como JPG/PNG."""
    cmd = [
        "ffmpeg", "-y", "-ss", str(time_s), "-i", input_path,
        "-vframes", "1", "-vf", f"scale={width}:-1", output_path,
    ]
    return _run(cmd, timeout=60)


def resize(input_path: str, width: int, height: int, output_path: str) -> dict:
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"scale={width}:{height}",
        "-c:a", "copy", output_path,
    ]
    return _run(cmd)


def add_audio(video_path: str, audio_path: str, output_path: str,
              replace: bool = True) -> dict:
    """Combina video + audio."""
    if replace:
        cmd = [
            "ffmpeg", "-y", "-i", video_path, "-i", audio_path,
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-shortest",
            output_path,
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-i", video_path, "-i", audio_path,
            "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=shortest",
            "-c:v", "copy", output_path,
        ]
    return _run(cmd)


def speed(input_path: str, factor: float, output_path: str) -> dict:
    """Cambia velocidad. factor>1 acelera, factor<1 ralentiza."""
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-filter_complex",
        f"[0:v]setpts={1/factor}*PTS[v];[0:a]atempo={factor}[a]",
        "-map", "[v]", "-map", "[a]", output_path,
    ]
    return _run(cmd)


def render_remotion(project_dir: str, composition_id: str,
                    output_path: str, props: dict | None = None) -> dict:
    """Renderiza video con Remotion (React-based programmatic video).

    project_dir: carpeta del proyecto Remotion (npm)
    composition_id: ID definido en src/Root.tsx
    props: props que se inyectan al composition
    """
    cmd = ["npx", "remotion", "render", composition_id, output_path]
    if props:
        cmd += ["--props", json.dumps(props)]
    return _run(cmd, timeout=1800)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: ffmpeg_video.py {probe|cut|concat|thumbnail|resize} ...")
        sys.exit(0)
    op = sys.argv[1]
    if op == "probe":
        print(json.dumps(probe(sys.argv[2]), indent=2))
    elif op == "thumbnail":
        print(json.dumps(thumbnail(sys.argv[2], float(sys.argv[3]), sys.argv[4]), indent=2))
    elif op == "cut":
        print(json.dumps(cut(sys.argv[2], float(sys.argv[3]),
                             float(sys.argv[4]), sys.argv[5]), indent=2))
    else:
        print(f"unknown op: {op}")
