# Jarvis AI — Instrucciones para Claude Code

## Contexto
Asistente personal voice-first. Backend FastAPI + frontend Electron. Emmanuel es el unico usuario. NO es un producto multi-tenant.

## Stack
- Python 3.11 async/await (FastAPI)
- React + Electron
- faster-whisper (STT), edge-tts (TTS)
- Ollama local (Qwen 3.6 recomendado), Claude API, Gemini free, Cerebras free

## Routing jerarquico IA
**Orden de prioridad** (implementado en `backend/ai_router.py`):
1. Claude API (capacidad + contexto largo)
2. Gemini Pro / Cerebras (free tier — tareas rapidas)
3. Ollama local (fallback offline o sensible)

Nunca invertir este orden sin motivo.

## Convenciones

- Espanol en UI, codigo y comentarios
- Logs en `data/jarvis-service.log`
- Config en `.env` (nunca hardcodear keys)
- Respuestas del asistente: concisas, directo al grano, sin preamble

## Lo que NO hacer

- No agregar proveedores de IA nuevos sin pedir a Emmanuel
- No cambiar el routing jerarquico
- No exponer APIs publicamente (solo localhost)

## Hermanos repos

- `JarvisAI-Fusion/` — fusion con otro proyecto (ver su README)
- `jarvis-windows/`, `jarvis-harsh/`, `jarvis-cam/` — branches experimentales
- `07-Codigo/Jarvis-Ethan/` (en vault) — version servicio persistente (actualmente muerta)

**JarvisAI principal es el canonico voice-first.** Cuando haya conflicto, este gana.

## Comandos frecuentes

```bash
# Backend
cd backend && python main.py

# Dev frontend
cd frontend && npm run dev

# Build Electron
cd frontend && npm run build

# Test integracion Obsidian
python scripts/test_obsidian.py
```
