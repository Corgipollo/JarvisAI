"""voice_daemon.py - Sistema nervioso auditivo + vocal de Jarvis (Iron Man mode).

Arquitectura hibrida:
  - Trigger 1: HOTKEY F12 (hold-to-talk) -> graba mientras esta presionado
  - Trigger 2: WAKE WORD 'jarvis' -> loop de escucha continua ligera
  - STT: faster-whisper modelo 'tiny' en CUDA float16 (~70MB, <500ms)
  - Procesamiento: POST a http://127.0.0.1:5000/execute con X-Jarvis-Token
  - TTS respuesta: edge-tts (es-MX-DaliaNeural) + pygame mixer

Estado: corre como 8vo daemon junto con API, worker, proxy_fast,
omniparser_researcher, etc. Registrado como Jarvis_VoiceDaemon via
install_voice.ps1.

REQUISITOS (no instala automaticamente - ver install_voice.ps1):
  pip install faster-whisper sounddevice pygame keyboard edge-tts numpy

Modo seguro:
  - No transcribe ni envia si el silencio es <0.4s (evita falsos triggers)
  - Hold-to-talk F12 es preferible al wake word si trabajas en VS Code
    (las teclas alfanumericas no disparan accidentalmente)
  - Telemetria a data/voice_daemon.log
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import queue
import sys
import threading
import time
import wave
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

LOG_PATH = ROOT / "data" / "voice_daemon.log"
API_URL = os.environ.get("JARVIS_API_URL", "http://127.0.0.1:5000")
API_TOKEN = os.environ.get("JARVIS_API_TOKEN", "jarvis_a8x29kfp3lz7m2qw9bdv")

# Config tunable via env
HOTKEY = os.environ.get("VOICE_HOTKEY", "f12")
WAKE_WORD = os.environ.get("VOICE_WAKE_WORD", "jarvis")
WAKE_WORD_ENABLED = os.environ.get("VOICE_WAKE_WORD_ENABLED", "0") == "1"
WHISPER_MODEL = os.environ.get("VOICE_WHISPER_MODEL", "tiny")
WHISPER_DEVICE = os.environ.get("VOICE_WHISPER_DEVICE", "cuda")
WHISPER_COMPUTE = os.environ.get("VOICE_WHISPER_COMPUTE", "float16")
TTS_VOICE = os.environ.get("VOICE_TTS_VOICE", "es-MX-DaliaNeural")
SAMPLE_RATE = 16000
SILENCE_THRESHOLD = 0.01  # RMS umbral para considerar "silencio"
SILENCE_DURATION_S = 1.0   # silencio sostenido para cortar grabacion
MAX_RECORDING_S = 30        # cap por grabacion individual


def _log(msg: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ============================================================================
# STT — faster-whisper en CUDA
# ============================================================================
_whisper_model = None


def _load_whisper():
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    from faster_whisper import WhisperModel
    _log(f"loading whisper '{WHISPER_MODEL}' on {WHISPER_DEVICE} ({WHISPER_COMPUTE})")
    _whisper_model = WhisperModel(
        WHISPER_MODEL, device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE,
    )
    _log("whisper loaded")
    return _whisper_model


def transcribe(audio_pcm_int16: bytes) -> str:
    """Recibe PCM 16-bit mono 16kHz, devuelve texto."""
    import numpy as np
    model = _load_whisper()
    audio = np.frombuffer(audio_pcm_int16, dtype=np.int16).astype(np.float32) / 32768.0
    segments, info = model.transcribe(
        audio, language="es", beam_size=1, vad_filter=True,
    )
    text = " ".join(s.text for s in segments).strip()
    _log(f"transcribed: '{text[:120]}'")
    return text


# ============================================================================
# Recording — sounddevice con detecion de silencio
# ============================================================================
def record_until_silence(max_duration_s: int = MAX_RECORDING_S) -> bytes:
    """Graba microfono hasta silencio sostenido o max_duration_s. Devuelve PCM."""
    import sounddevice as sd
    import numpy as np
    chunks: list[bytes] = []
    silence_chunks = 0
    chunks_per_sec = 10
    silence_target_chunks = int(SILENCE_DURATION_S * chunks_per_sec)
    chunk_size = SAMPLE_RATE // chunks_per_sec
    started_at = time.time()

    def callback(indata, frames, t, status):
        nonlocal silence_chunks
        if status:
            _log(f"stream status: {status}")
        # Convert float32 [-1,1] to int16 PCM
        pcm = (indata[:, 0] * 32767).astype(np.int16).tobytes()
        chunks.append(pcm)
        rms = float(np.sqrt(np.mean(indata[:, 0] ** 2)))
        if rms < SILENCE_THRESHOLD:
            silence_chunks += 1
        else:
            silence_chunks = 0

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                          blocksize=chunk_size, callback=callback):
        _log("recording...")
        while True:
            time.sleep(0.05)
            if silence_chunks >= silence_target_chunks and len(chunks) > silence_target_chunks * 2:
                break
            if time.time() - started_at > max_duration_s:
                _log("max_duration reached, stopping")
                break
    return b"".join(chunks)


# ============================================================================
# TTS — edge-tts + pygame
# ============================================================================
async def _tts_to_file(text: str, out_path: Path) -> None:
    import edge_tts
    comm = edge_tts.Communicate(text, TTS_VOICE)
    await comm.save(str(out_path))


def speak(text: str) -> None:
    """Genera audio con edge-tts y reproduce con pygame."""
    if not text:
        return
    out = ROOT / "data" / f"voice_tts_{int(time.time() * 1000)}.mp3"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        asyncio.run(_tts_to_file(text, out))
    except RuntimeError:
        # En caso de loop ya activo, usar new event loop
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_tts_to_file(text, out))
        loop.close()
    try:
        import pygame
        pygame.mixer.init()
        pygame.mixer.music.load(str(out))
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        pygame.mixer.quit()
    except Exception as e:
        _log(f"playback fail: {e}")
    finally:
        try:
            out.unlink(missing_ok=True)
        except Exception:
            pass


# ============================================================================
# Dispatch — POST a la API
# ============================================================================
def dispatch_text(text: str) -> dict:
    import requests
    if not text or len(text.strip()) < 3:
        return {"ok": False, "skipped": "too_short"}
    try:
        r = requests.post(
            f"{API_URL}/queue/add",
            json={"objective": text, "priority": 7},
            headers={"X-Jarvis-Token": API_TOKEN,
                     "Content-Type": "application/json"},
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _log(f"dispatch fail: {e}")
        return {"ok": False, "error": str(e)}


# ============================================================================
# Pipeline completo
# ============================================================================
def listen_record_dispatch_respond() -> None:
    """Un ciclo: graba -> STT -> POST -> TTS confirma."""
    try:
        pcm = record_until_silence()
        if len(pcm) < SAMPLE_RATE * 2 * 0.5:  # <0.5s
            _log("recording too short, skip")
            return
        text = transcribe(pcm)
        if not text:
            speak("No entendi nada, repite.")
            return
        result = dispatch_text(text)
        qid = result.get("qid", "?")
        if result.get("ok") or result.get("queued"):
            speak(f"Encolado y procesando. Identificador {qid[:6]}.")
        else:
            speak(f"Hubo un problema al encolar. Revisa el log.")
    except Exception as e:
        _log(f"pipeline error: {e}")
        try:
            speak("Hubo un error interno.")
        except Exception:
            pass


# ============================================================================
# Triggers — hotkey + wake word
# ============================================================================
_triggered = threading.Event()


def hotkey_listener():
    """Hotkey F12 hold-to-talk."""
    try:
        import keyboard
    except ImportError:
        _log("keyboard lib no instalada - hotkey desactivado")
        return
    _log(f"hotkey activo: {HOTKEY}")
    while True:
        keyboard.wait(HOTKEY)
        _log(f"hotkey {HOTKEY} pressed")
        _triggered.set()
        # debounce: espera a que suelte para no spammear
        while keyboard.is_pressed(HOTKEY):
            time.sleep(0.05)


def wake_word_listener():
    """Loop ligero de escucha continua para wake word.

    NOTA: implementacion basica que captura buffers cortos y los transcribe.
    Una version production-grade usaria un detector dedicado (Porcupine).
    """
    if not WAKE_WORD_ENABLED:
        _log("wake word desactivado (set VOICE_WAKE_WORD_ENABLED=1 para activarlo)")
        return
    import sounddevice as sd
    import numpy as np
    _log(f"wake word activo: '{WAKE_WORD}'")
    buffer_s = 2  # ventana de 2s deslizante
    while True:
        try:
            audio = sd.rec(int(buffer_s * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                            channels=1, dtype="float32")
            sd.wait()
            rms = float(np.sqrt(np.mean(audio ** 2)))
            if rms < SILENCE_THRESHOLD * 2:
                continue  # silencio total, no transcribir
            pcm = (audio[:, 0] * 32767).astype(np.int16).tobytes()
            text = transcribe(pcm).lower()
            if WAKE_WORD in text:
                _log(f"wake word detected in: '{text}'")
                _triggered.set()
        except Exception as e:
            _log(f"wake word error: {e}")
            time.sleep(1)


def main_loop():
    _log("=== voice_daemon started ===")
    _log(f"  hotkey={HOTKEY} wake_word={WAKE_WORD} enabled={WAKE_WORD_ENABLED}")
    _log(f"  whisper={WHISPER_MODEL}@{WHISPER_DEVICE} tts={TTS_VOICE}")
    _log(f"  API={API_URL}")

    # Pre-cargar Whisper (evita latencia en el primer trigger)
    try:
        _load_whisper()
    except Exception as e:
        _log(f"whisper preload fail: {e} - continuara en lazy load")

    # Lanza listeners en threads
    t1 = threading.Thread(target=hotkey_listener, daemon=True)
    t1.start()
    if WAKE_WORD_ENABLED:
        t2 = threading.Thread(target=wake_word_listener, daemon=True)
        t2.start()

    speak("Jarvis listo. Presiona F12 para hablar.")

    while True:
        _triggered.wait()
        _triggered.clear()
        listen_record_dispatch_respond()


if __name__ == "__main__":
    main_loop()
