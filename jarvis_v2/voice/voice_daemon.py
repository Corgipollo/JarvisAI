"""voice_daemon.py - Bridge microfono -> graph.run_objective() async.

Reescrito usando RealtimeSTT (KoljaB) que ya integra:
  - Wake word (Porcupine OR OpenWakeWord, configurable)
  - VAD (Silero por defecto, mejor que webrtcvad)
  - faster-whisper (CPU int8)
  - Threading interno, callbacks streaming

Mejoras sobre v1 (que escribiamos desde cero):
  - 1 dependencia integrada vs 4 (Porcupine + pyaudio + webrtcvad + whisper)
  - Silero VAD > webrtcvad accuracy
  - Patrón productor-consumidor: listening NUNCA bloquea aun si graph tarda 10min
  - Interrupt detection: si dices "stop"/"cancela" durante ejecucion -> kill task
  - Rolling context: ultimos 5 comandos para referencias ("lo que acabamos de hacer")
  - Optional TTS responses via edge-tts
"""
from __future__ import annotations

import os
import queue
import re
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Config
WAKE_WORDS = os.environ.get("JARVIS_WAKE_WORD", "jarvis,computer").split(",")
PICOVOICE_KEY = os.environ.get("JARVIS_PICOVOICE_KEY", "")
WHISPER_MODEL = os.environ.get("JARVIS_WHISPER_MODEL", "base")
ENABLE_TTS = os.environ.get("JARVIS_TTS", "0") == "1"

# Interrupt phrases - parseadas ANTES de mandar al LLM
INTERRUPT_PHRASES = [
    r"\b(stop|cancela|cancelar|cancel|para|parar|detente|aborta)\b",
    r"\b(silencio|callate|cierra)\b",
]
INTERRUPT_REGEX = re.compile("|".join(INTERRUPT_PHRASES), re.IGNORECASE)


class JarvisVoiceDaemon:
    """Daemon de voz con thread-safe task management."""

    def __init__(self):
        self.task_queue: queue.Queue = queue.Queue()
        self.current_task: threading.Thread | None = None
        self.current_task_cancel: threading.Event = threading.Event()
        self.context: deque = deque(maxlen=5)  # ultimos 5 comandos
        self.shutdown_event = threading.Event()
        self.recorder = None

    def _on_recording_start(self):
        print(f"[voice {datetime.now():%H:%M:%S}] grabando comando...", flush=True)
        try:
            import winsound
            winsound.Beep(880, 100)
        except Exception:
            pass

    def _on_recording_stop(self):
        print(f"[voice {datetime.now():%H:%M:%S}] silencio detectado, transcribiendo...",
              flush=True)

    def _on_wakeword_detected(self):
        print(f"[voice {datetime.now():%H:%M:%S}] WAKE WORD detected", flush=True)

    def _handle_transcript(self, text: str):
        text = (text or "").strip()
        if not text or len(text) < 3:
            print(f"[voice] transcript vacio, ignorando", flush=True)
            return
        print(f"[voice] transcribed: '{text}'", flush=True)
        self.context.append({"ts": datetime.now().isoformat(), "text": text})

        # Detect interrupt phrases ANTES de LLM
        if INTERRUPT_REGEX.search(text):
            self._handle_interrupt(text)
            return

        # Normal dispatch
        self.task_queue.put(text)

    def _handle_interrupt(self, text: str):
        if self.current_task and self.current_task.is_alive():
            print(f"[voice] INTERRUPT detected: '{text[:40]}' - cancelando task actual",
                  flush=True)
            self.current_task_cancel.set()
            self._tts("Cancelando")
        else:
            print(f"[voice] interrupt phrase pero no hay task activa", flush=True)

    def _tts(self, text: str):
        """Optional voice response via edge-tts."""
        if not ENABLE_TTS:
            return
        try:
            # Subprocess to avoid blocking
            import subprocess
            subprocess.Popen([
                sys.executable, "-c",
                f"import edge_tts, asyncio; "
                f"asyncio.run(edge_tts.Communicate('{text}', 'es-MX-JorgeNeural').save('_tts.mp3')); "
                f"import os; os.system('start _tts.mp3')"
            ])
        except Exception as e:
            print(f"[voice] tts failed: {e}", flush=True)

    def _task_worker(self):
        """Thread consumidor: ejecuta graph.run_objective uno a la vez."""
        while not self.shutdown_event.is_set():
            try:
                text = self.task_queue.get(timeout=1)
            except queue.Empty:
                continue
            print(f"[voice] task_worker dispatching: '{text[:60]}'", flush=True)
            self.current_task_cancel.clear()

            def _run():
                try:
                    from jarvis_v2.core.graph import run_objective
                    # Inject rolling context
                    if len(self.context) > 1:
                        history = " | ".join(c["text"] for c in list(self.context)[:-1])
                        full_obj = f"{text}\n(Contexto reciente: {history})"
                    else:
                        full_obj = text
                    result = run_objective(
                        full_obj,
                        thread_id=f"voice_{int(time.time())}",
                    )
                    print(f"[voice] task done: {list(result.keys())[:5]}", flush=True)
                    self._tts("Listo")
                except Exception as e:
                    print(f"[voice] task error: {type(e).__name__}: {e}", flush=True)
                    self._tts("Error")

            self.current_task = threading.Thread(target=_run, daemon=True)
            self.current_task.start()
            # Wait for current task before next, but check cancel periodically
            while self.current_task.is_alive():
                if self.current_task_cancel.is_set():
                    print(f"[voice] task cancelado (interrupt). Continuando listener",
                          flush=True)
                    # NOTE: thread daemonico, no se puede matar limpio en Python.
                    # En produccion: graph deberia checar un cancel_event periodicamente.
                    break
                time.sleep(0.5)

    def start(self):
        from RealtimeSTT import AudioToTextRecorder

        print(f"=== Voice Daemon arrancando ===", flush=True)
        print(f"  wake words: {WAKE_WORDS}", flush=True)
        print(f"  whisper model: {WHISPER_MODEL}", flush=True)
        print(f"  picovoice key: {'SET' if PICOVOICE_KEY else 'NOT SET (usando openwakeword fallback)'}",
              flush=True)
        print(f"  TTS: {'ON' if ENABLE_TTS else 'OFF'}", flush=True)

        # Arranca worker thread
        worker = threading.Thread(target=self._task_worker, daemon=True)
        worker.start()

        # Config RealtimeSTT
        config = {
            "spinner": False,
            "language": "es",
            "model": WHISPER_MODEL,
            "compute_type": "int8",
            "device": "cpu",
            "post_speech_silence_duration": 1.5,  # 1.5s de silencio = stop
            "min_length_of_recording": 0.5,
            "min_gap_between_recordings": 0.3,
            "enable_realtime_transcription": False,
            "on_recording_start": self._on_recording_start,
            "on_recording_stop": self._on_recording_stop,
            "on_wakeword_detected": self._on_wakeword_detected,
        }

        if PICOVOICE_KEY:
            config["wakeword_backend"] = "pvporcupine"
            config["porcupine_access_key"] = PICOVOICE_KEY
            config["wake_words"] = ",".join(WAKE_WORDS)
        else:
            # Fallback: openwakeword (libre, requiere modelos pre-trained)
            config["wakeword_backend"] = "oww"
            config["openwakeword_model_paths"] = "alexa,hey_jarvis"  # built-in OWW models

        config["wake_words_sensitivity"] = 0.6
        config["wake_word_activation_delay"] = 0.0
        config["wake_word_timeout"] = 5.0  # despues de wake, espera 5s comando

        try:
            self.recorder = AudioToTextRecorder(**config)
            print(f"[voice] listo. Di '{WAKE_WORDS[0]}' para activar", flush=True)
            while not self.shutdown_event.is_set():
                # Bloquea hasta wake+command completos
                self.recorder.text(self._handle_transcript)
        except KeyboardInterrupt:
            print(f"[voice] detenido por usuario", flush=True)
        finally:
            self.shutdown_event.set()
            if self.recorder:
                try:
                    self.recorder.shutdown()
                except Exception:
                    pass


def main():
    daemon = JarvisVoiceDaemon()
    daemon.start()


if __name__ == "__main__":
    main()
