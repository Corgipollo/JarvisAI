# 🔧 JARVIS AI — Troubleshooting Guide

**Última actualización:** 2026-05-31

Esta guía cubre los errores más comunes y cómo resolverlos.

---

## 📑 Índice Rápido

1. [Instalación y Setup](#1-instalación-y-setup)
2. [Problemas de API](#2-problemas-de-api)
3. [Errores de Voz (STT/TTS)](#3-errores-de-voz-stttts)
4. [Integraciones (Spotify, Obsidian)](#4-integraciones-spotify-obsidian)
5. [Performance y Memoria](#5-performance-y-memoria)
6. [Frontend no Conecta](#6-frontend-no-conecta)
7. [Logs y Debugging](#7-logs-y-debugging)
8. [Comandos de Diagnóstico](#8-comandos-de-diagnóstico)

---

## 1. Instalación y Setup

### ❌ Error: "No module named 'faster_whisper'"

**Síntoma:**
```
ModuleNotFoundError: No module named 'faster_whisper'
```

**Causa:** Dependencias de Python no instaladas.

**Solución:**
```bash
cd backend
pip install -r requirements.txt
```

**Si persiste:**
```bash
pip install faster-whisper==1.0.3 --force-reinstall
```

---

### ❌ Error: "CUDA not available" (con GPU NVIDIA)

**Síntoma:**
```
WARNING: CUDA not available, using CPU
```

**Causa:** PyTorch no detecta la GPU.

**Solución:**
```bash
pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**Verificar:**
```python
import torch
print(torch.cuda.is_available())  # Debe ser True
```

---

### ❌ Error: Script de instalación falla en Windows

**Síntoma:**
```
.\install.ps1 : File cannot be loaded because running scripts is disabled
```

**Causa:** PowerShell execution policy restrictiva.

**Solución:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\install.ps1
```

---

## 2. Problemas de API

### ❌ Error: "Gemini API key invalid"

**Síntoma:**
```
Error 401: Invalid API key
```

**Causa:** API key incorrecta o no configurada.

**Solución:**
1. Verifica `.env`:
   ```env
   GEMINI_API_KEY=tu_key_real_aqui
   ```

2. Obtén una key válida: https://aistudio.google.com/apikey

3. Reinicia el backend:
   ```bash
   cd backend
   python main.py
   ```

**Verificar:**
```bash
curl -X GET "http://localhost:8000/health"
# Debe responder: {"status": "healthy", "models": [...]}
```

---

### ❌ Error: "Ollama connection refused"

**Síntoma:**
```
ConnectionError: Cannot connect to Ollama at http://localhost:11434
```

**Causa:** Ollama no está corriendo.

**Solución:**
```bash
# Iniciar Ollama server
ollama serve

# En otra terminal, verificar que responde
curl http://localhost:11434/api/tags
```

**Si no tienes Ollama instalado:**
1. Descarga: https://ollama.ai/download
2. Instala
3. Pull un modelo:
   ```bash
   ollama pull qwen2.5:3b
   ```

---

## 3. Errores de Voz (STT/TTS)

### ❌ Error: "Microphone not detected"

**Síntoma:**
```
ERROR: No default input device found
```

**Causa:** No hay micrófono configurado en Windows.

**Solución:**
1. Abre **Configuración de Windows** → **Sonido**
2. Verifica que hay un **dispositivo de entrada** seleccionado
3. Habilita permisos de micrófono para Python

**Verificar en PowerShell:**
```powershell
Get-PnpDevice -Class AudioEndpoint | Where-Object {$_.FriendlyName -like "*Mic*"}
```

---

### ❌ Error: Edge-TTS no genera audio

**Síntoma:**
```
ERROR: edge-tts synthesis failed
```

**Causa:** Sin conexión a internet o servicio de Microsoft caído.

**Solución:**
```bash
# Verificar conectividad
ping speech.platform.bing.com

# Si falla, usar TTS local alternativo (instalación manual):
pip install pyttsx3
```

---

## 4. Integraciones (Spotify, Obsidian)

### ❌ Error: "Spotify authentication failed"

**Síntoma:**
```
ERROR: Spotify auth error 401
```

**Causa:** Credenciales de Spotify incorrectas o redirect URI mal configurado.

**Solución:**
1. Ve a: https://developer.spotify.com/dashboard
2. Verifica que **Redirect URI** sea exactamente:
   ```
   http://localhost:8000/callback
   ```

3. Actualiza `.env`:
   ```env
   SPOTIFY_CLIENT_ID=tu_client_id
   SPOTIFY_CLIENT_SECRET=tu_client_secret
   ```

4. Reinicia Jarvis y re-autentica.

---

### ❌ Error: "Obsidian vault not found"

**Síntoma:**
```
ERROR: Vault path does not exist: C:\Users\...\ObsidianVault
```

**Causa:** Ruta incorrecta en `.env`.

**Solución:**
1. Encuentra tu vault en Obsidian: **Settings** → **About** → **Vault path**

2. Copia la ruta EXACTA y actualiza `.env`:
   ```env
   OBSIDIAN_VAULT_PATH=C:\Users\Emmanuel\Documents\MiVault
   ```

3. Usa **barras diagonales dobles** en Windows:
   ```env
   OBSIDIAN_VAULT_PATH=C:\\Users\\Emmanuel\\Documents\\MiVault
   ```

---

## 5. Performance y Memoria

### ❌ Error: "High memory usage (>10GB)"

**Síntoma:** Jarvis consume mucha RAM después de horas de uso.

**Causa:** Memoria acumulada en caché de modelos.

**Solución:**
```bash
# Reiniciar Jarvis
# 1. Cerrar backend (Ctrl+C)
# 2. Cerrar frontend
# 3. Re-ejecutar
.\START_JARVIS_FULL.bat
```

**Configurar límites de memoria (opcional):**
```env
# En .env
JARVIS_MAX_MEMORY_GB=4
```

---

### ❌ Error: Comandos lentos (>10 segundos)

**Síntoma:** Respuestas tardan mucho.

**Causa:** Modelo de IA lento o sin GPU.

**Solución:**
1. Verifica que estés usando el modelo correcto:
   ```env
   JARVIS_LLM_PROVIDER=anthropic_proxy  # Más rápido
   # NO usar ollama para queries complejas sin GPU
   ```

2. Si usas Ollama, usa modelos ligeros:
   ```bash
   ollama pull qwen2.5:3b  # NO el 7b o 14b
   ```

---

## 6. Frontend no Conecta

### ❌ Error: "Cannot connect to backend"

**Síntoma:** Frontend muestra "Disconnected" o errores de red.

**Causa:** Backend no está corriendo o puerto incorrecto.

**Solución:**
```bash
# 1. Verificar que backend esté corriendo
curl http://localhost:8000/health

# 2. Si no responde, iniciar backend
cd backend
python main.py

# 3. Verificar logs
tail -f ../data/jarvis-service.log
```

---

### ❌ Error: CORS error en consola del navegador

**Síntoma:**
```
Access to fetch at 'http://localhost:8000' from origin 'http://localhost:3000' has been blocked by CORS policy
```

**Causa:** CORS mal configurado.

**Solución:**
Verifica `backend/main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 7. Logs y Debugging

### 📂 Ubicación de Logs

| Componente | Archivo de Log |
|------------|----------------|
| Backend principal | `data/jarvis-service.log` |
| Errores de API | `data/api.err` |
| Infinite CEO | `data/infinite_ceo.err` |
| Task Worker | `data/task_worker.err` |

### 🔍 Ver logs en tiempo real

```bash
# Backend principal
tail -f data/jarvis-service.log

# Todos los errores
tail -f data/*.err

# Filtrar solo errores críticos
grep -i "error\|critical" data/jarvis-service.log
```

---

## 8. Comandos de Diagnóstico

### ✅ Health Check Completo

```bash
# Backend health
curl http://localhost:8000/health

# Frontend health
curl http://localhost:5173

# Ollama health
curl http://localhost:11434/api/tags

# Spotify (requiere auth)
curl http://localhost:8000/integrations/spotify/status
```

---

### ✅ Test de Componentes

```bash
cd backend

# Test STT (faster-whisper)
python -c "from core.voice import test_stt; test_stt()"

# Test TTS (edge-tts)
python -c "from core.voice import test_tts; test_tts('Hola mundo')"

# Test Ollama
python -c "from core.ollama_client import test_connection; test_connection()"
```

---

### ✅ Verificar Dependencias

```bash
# Python packages
pip list | grep -E "fastapi|faster-whisper|edge-tts|ollama"

# Node packages (en frontend/)
npm list | grep -E "react|electron|axios"

# Versiones críticas
python --version  # Debe ser 3.11+
node --version    # Debe ser 20+
```

---

## 🆘 Si Nada Funciona

### Reset Completo

```bash
# 1. Backup de .env y data/
copy .env .env.backup
xcopy data data_backup /E /I

# 2. Limpiar instalación
rm -rf backend/__pycache__
rm -rf frontend/node_modules
rm -rf venv

# 3. Re-instalar
.\install.ps1

# 4. Restaurar .env
copy .env.backup .env
```

---

## 📞 Soporte

Si ninguna solución funciona:

1. **GitHub Issues**: Abre un issue en el repo privado
2. **Telegram**: @corgipollo (Emmanuel)
3. **Email**: emmanuel@jarvis-ai.local

**Al reportar un bug, incluye:**
- OS y versión (Windows 11 build?)
- Contenido de `data/jarvis-service.log` (últimas 50 líneas)
- Pasos exactos para reproducir
- Screenshot del error si aplica

---

**Última actualización:** 2026-05-31 por Claude Code
