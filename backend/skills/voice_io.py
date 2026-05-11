"""voice_io.py — TTS + STT + Wake Word para Jarvis.

3 capacidades:
  1. SPEAK (TTS): edge-tts con voz natural "es-MX-DaliaNeural"
  2. LISTEN (STT): faster-whisper streaming desde mic
  3. WAKE WORD: detecta "Jarvis" / "Hey Jarvis" para activar listening

Uso:
    from backend.skills.voice_io import speak, listen, wake_loop
    speak("Hola, soy Jarvis")
    text = listen(timeout=10)   # graba 10s, transcribe
    wake_loop(callback=handle_user_command)  # background, dispara cuando dice 'jarvis'
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def speak(text: str, voice: str = "es-MX-DaliaNeural", rate: str = "+0%", play: bool = True) -> str:
    """TTS: convierte texto a audio MP3 y opcionalmente lo reproduce."""
    try:
        import edge_tts
    except ImportError:
        print("[voice_io] edge-tts no instalado: pip install edge-tts")
        return ""

    out = Path(tempfile.gettempdir()) / f"jarvis_speech_{int(time.time()*1000)}.mp3"

    async def _gen():
        communicator = edge_tts.Communicate(text, voice=voice, rate=rate)
        await communicator.save(str(out))

    try:
        asyncio.run(_gen())
    except Exception as e:
        print(f"[voice_io] TTS fallo: {e}")
        return ""

    if play:
        try:
            # Windows: usa winsound o ffplay como fallback
            import subprocess
            subprocess.Popen(
                ["powershell", "-c", f"(New-Object Media.SoundPlayer '{out}').PlaySync()"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass
    return str(out)


def listen(timeout: float = 8.0, sample_rate: int = 16000,
           model_size: str = "base", language: str = "es") -> str:
    """STT: graba audio del mic por N segundos y transcribe con faster-whisper."""
    try:
        import sounddevice as sd
        import numpy as np
        from faster_whisper import WhisperModel
    except ImportError:
        print("[voice_io] falta: pip install sounddevice numpy faster-whisper")
        return ""

    print(f"[voice_io] escuchando {timeout}s...", flush=True)
    try:
        audio = sd.rec(int(timeout * sample_rate), samplerate=sample_rate, channels=1, dtype="float32")
        sd.wait()
    except Exception as e:
        print(f"[voice_io] no pude grabar: {e}")
        return ""

    audio = audio.flatten()
    try:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(audio, language=language, vad_filter=True)
        text = " ".join(s.text.strip() for s in segments)
        print(f"[voice_io] heard: {text[:120]}", flush=True)
        return text.strip()
    except Exception as e:
        print(f"[voice_io] transcribe fallo: {e}")
        return ""


def wake_loop(callback: Callable[[str], None],
              wake_words: tuple = ("jarvis", "hey jarvis", "oye jarvis"),
              chunk_seconds: float = 3.0,
              silence_after_wake: float = 8.0):
    """Loop infinito que escucha micro continuamente. Cuando detecta wake word,
    graba el siguiente comando completo y llama callback(comando).
    """
    print(f"[wake_loop] escuchando wake words: {wake_words}", flush=True)
    while True:
        try:
            chunk = listen(timeout=chunk_seconds, model_size="tiny").lower()
            if not chunk:
                continue
            if any(w in chunk for w in wake_words):
                print(f"[wake_loop] ¡detectado! grabando comando completo...", flush=True)
                speak("Sí, te escucho")
                command = listen(timeout=silence_after_wake, model_size="base")
                if command:
                    callback(command)
        except KeyboardInterrupt:
            print("[wake_loop] detenido")
            break
        except Exception as e:
            print(f"[wake_loop] error: {e}")
            time.sleep(2)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usos:")
        print("  python voice_io.py speak 'texto a decir'")
        print("  python voice_io.py listen [timeout_seconds]")
        print("  python voice_io.py wake")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "speak":
        text = " ".join(sys.argv[2:]) or "Hola, soy Jarvis"
        speak(text)
    elif cmd == "listen":
        t = float(sys.argv[2]) if len(sys.argv) > 2 else 8.0
        print(listen(timeout=t))
    elif cmd == "wake":
        def echo(cmd):
            print(f"COMANDO: {cmd}")
            speak(f"recibí: {cmd}")
        wake_loop(echo)
