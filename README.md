# Jarvis AI — Asistente Personal Voice-First

> Asistente personal estilo Iron Man. FastAPI backend + Electron frontend. Routing inteligente: Claude > Free AI (Gemini/Cerebras) > Ollama local.

## Stack

- **Backend**: FastAPI (Python 3.11), async
- **Frontend**: Electron + React
- **Voz**: faster-whisper (STT), edge-tts (TTS)
- **IA**: routing jerarquico — Claude (primary) → Gemini/Cerebras (free tier) → Ollama local (fallback)
- **Integraciones**: Obsidian, Shopify, Spotify, PC Control, y 4 mas

## Quick Start

```bash
# Backend
cd backend
python -m venv venv
./venv/Scripts/activate
pip install -r requirements.txt
python main.py

# Frontend
cd frontend
npm install
npm run dev
```

O usar el shortcut: `start-jarvis.bat`

## Estructura

```
backend/    FastAPI server, routing IA, integraciones
frontend/   Electron + React UI
data/       Conversaciones, memoria, contexto
scripts/    Utilidades (setup, backup, diag)
generated/  Output temporal
```

## Variables de entorno (.env)

- `ANTHROPIC_API_KEY` — Claude
- `GEMINI_API_KEY` — Gemini free tier
- `CEREBRAS_API_KEY` — Cerebras free
- `OLLAMA_URL` — http://localhost:11434 (default)

## Autor

Emmanuel Pedraza ([Corgipollo](https://github.com/Corgipollo))
