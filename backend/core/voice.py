"""Sistema de voz: Speech-to-Text (Whisper) + Text-to-Speech (Edge-TTS)."""
import asyncio
import io
import tempfile
import subprocess
import os
import sys
from pathlib import Path
from typing import Optional

_whisper_model = None


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        from config import settings

        _whisper_model = WhisperModel(
            settings.WHISPER_MODEL, device="cpu", compute_type="int8"
        )
    return _whisper_model


async def transcribe_audio(audio_bytes: bytes, language: str = "es") -> str:
    """Transcribe audio bytes to text using faster-whisper.
    Acepta WAV, WebM, OGG, MP3 — ffmpeg convierte si es necesario."""
    model = get_whisper_model()

    # Detectar formato por magic bytes
    is_webm = audio_bytes[:4] == b'\x1a\x45\xdf\xa3'
    is_ogg = audio_bytes[:4] == b'OggS'

    if is_webm or is_ogg:
        # Convertir a WAV con ffmpeg
        suffix_in = ".webm" if is_webm else ".ogg"
        with tempfile.NamedTemporaryFile(suffix=suffix_in, delete=False) as f_in:
            f_in.write(audio_bytes)
            input_path = f_in.name

        output_path = input_path.replace(suffix_in, ".wav")
        try:
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1",
                 "-f", "wav", output_path],
                capture_output=True, timeout=10,
            )
            if result.returncode != 0:
                print(f"[Whisper] ffmpeg error: {result.stderr.decode()[:200]}")
                return ""

            segments, info = model.transcribe(
                output_path, language=language,
                vad_filter=True,  # Filtrar silencio
                vad_parameters=dict(min_silence_duration_ms=500),
            )
            text = " ".join(seg.text for seg in segments).strip()

            # === FILTRO ANTI-RUIDO ===
            text_lower = text.lower().strip()

            # 1) Muy corto = ruido
            if len(text) < 3:
                return ""

            # 2) Frases de ruido comun (TV, YouTube, etc)
            noise = ["subtítulos", "suscríbete", "gracias por ver", "music",
                     "thank you", "bye", "the end", "subscribe", "like and"]
            if any(n in text_lower for n in noise):
                return ""

            # 3) Demasiado largo = TV/radio/fondo (>60 palabras)
            word_count = len(text.split())
            if word_count > 60:
                print(f"[Whisper] FILTRADO: {word_count} palabras (TV/fondo)")
                return ""

            # 4) Si tiene >30 palabras y NO contiene palabras de comando, ignorar
            if word_count > 30:
                command_words = ["jarvis", "oye", "que", "como", "cual", "donde",
                    "cuando", "dime", "busca", "abre", "cierra", "pon",
                    "quiero", "necesito", "ayuda", "muestrame", "hazme"]
                has_command = any(w in text_lower for w in command_words)
                if not has_command:
                    print(f"[Whisper] FILTRADO: {word_count} palabras sin comando")
                    return ""

            return text
        except subprocess.TimeoutExpired:
            return ""
        except Exception as e:
            print(f"[Whisper] Error: {e}")
            return ""
        finally:
            for p in [input_path, output_path]:
                try:
                    os.unlink(p)
                except Exception:
                    pass
    else:
        # Asumir WAV directo
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            segments, _ = model.transcribe(
                temp_path, language=language,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )
            text = " ".join(seg.text for seg in segments).strip()
            if len(text) < 3:
                return ""
            return text
        except Exception as e:
            print(f"[Whisper] Error: {e}")
            return ""
        finally:
            os.unlink(temp_path)


async def text_to_speech(text: str, voice: str = None) -> bytes:
    """Convert text to speech. Voz estilo Jarvis."""
    import edge_tts

    # Voz por defecto: Ryan (britanico, tipo Jarvis) para frases cortas
    # Jorge (mexicano) para respuestas largas en espanol
    if voice is None:
        # Detectar si el texto es mayormente ingles
        english_words = sum(1 for w in text.lower().split() if w in [
            'the','is','are','was','were','have','has','do','does','not',
            'and','or','but','for','with','this','that','from','your',
        ])
        if english_words > len(text.split()) * 0.3:
            voice = "en-GB-RyanNeural"  # British Jarvis voice
        else:
            voice = "es-MX-JorgeNeural"  # Espanol mexicano

    communicate = edge_tts.Communicate(
        text, voice,
        rate="+5%",    # Ligeramente mas rapido (Jarvis es eficiente)
        pitch="-5Hz",  # Tono ligeramente mas grave
    )

    audio_data = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data.write(chunk["data"])

    return audio_data.getvalue()


async def list_voices(language: str = "es") -> list[dict]:
    """List available TTS voices."""
    import edge_tts

    voices = await edge_tts.list_voices()
    return [
        {"name": v["ShortName"], "gender": v["Gender"], "locale": v["Locale"]}
        for v in voices
        if v["Locale"].startswith(language)
    ]
