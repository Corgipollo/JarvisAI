# 🤖 Jarvis AI — Asistente Personal Voice-First

> **Asistente de voz inteligente para Windows que controla tu PC, gestiona tareas y se conecta a tus sistemas.**

Jarvis AI es un asistente personal local que funciona completamente en tu máquina Windows. Combina múltiples proveedores de IA (Claude, Gemini, Cerebras, Ollama) con capacidades de control del sistema, visión por computadora y voice-first interaction.

---

## 🎯 Características Principales

- **Voice-First**: Transcripción en tiempo real con faster-whisper + síntesis de voz con edge-tts
- **Routing Inteligente de IA**: Prioriza Claude API → Gemini/Cerebras (free tier) → Ollama local
- **Control del Sistema**: Abre apps, controla Spotify, ejecuta código Python, gestiona archivos
- **Integración Obsidian**: Lee y escribe en tu vault personal
- **Visión**: Captura y analiza screenshots con Claude Vision
- **WebSearch**: Busca en tiempo real con Serper API
- **Memoria Persistente**: Recuerda hechos clave entre sesiones

---

## 📋 Requisitos del Sistema

### Obligatorios
- **Windows 11** (probado en 24H2)
- **Python 3.11+** (NO usar 3.12+ por compatibilidad faster-whisper)
- **Node.js 20+** (para Electron frontend)
- **Git** (para clonar el repo)
- **16+ GB RAM** (24 GB recomendado)

### Opcionales pero Recomendados
- **NVIDIA RTX GPU** (para faster-whisper con CUDA)
- **CUDA Toolkit 12.x** (si tienes GPU NVIDIA)
- **Ollama** instalado localmente (fallback offline)

---

## 🚀 Instalación Rápida (Script Automatizado)

### Opción 1: Script PowerShell (Recomendado)

```powershell
# Ejecutar como Administrador
cd C:\Users\Corgipollo\Documents
git clone https://github.com/Corgipollo/JarvisAI.git
cd JarvisAI
.\install.ps1
```

El script `install.ps1` hace:
1. ✅ Verifica requisitos del sistema (Python, Node, RAM)
2. ✅ Instala dependencias Python (requirements.txt)
3. ✅ Instala dependencias Node (frontend)
4. ✅ Crea `.env` desde template
5. ✅ Valida APIs configuradas
6. ✅ Configura autostart opcional

---

## 🛠️ Instalación Manual (Paso a Paso)

### 1. Clonar el Repositorio

```bash
cd C:\Users\Corgipollo\Documents
git clone https://github.com/Corgipollo/JarvisAI.git
cd JarvisAI
```

### 2. Configurar Backend (Python)

```bash
# Crear entorno virtual (recomendado)
python -m venv venv
venv\Scripts\activate

# Instalar dependencias
cd backend
pip install -r requirements.txt
```

**IMPORTANTE**: Si tienes GPU NVIDIA, instalar CUDA dependencies:
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### 3. Configurar Frontend (Electron)

```bash
cd ..\frontend
npm install
```

### 4. Configurar Variables de Entorno

Copiar `.env.example` a `.env` en la raíz del proyecto:

```env
# === PROVEEDORES DE IA ===
GEMINI_API_KEY=tu_key_aqui
OPENROUTER_API_KEY=tu_key_aqui
JARVIS_LLM_PROVIDER=anthropic_proxy
JARVIS_CLAUDE_PROXY=http://127.0.0.1:8088
JARVIS_LLM_FALLBACK=gemini_api,openrouter,ollama

# === SEGURIDAD ===
JARVIS_API_TOKEN=jarvis_a8x29kfp3lz7m2qw9bdv

# === CONFIGURACION ===
CEO_CYCLE_SEC=30
JARVIS_TASK_HARD_TIMEOUT_SEC=120
JARVIS_GRAPH_RECURSION_LIMIT=150
JARVIS_STATE_MAX_MESSAGES=200
```

**Obtener API Keys**:
- **Gemini**: https://aistudio.google.com/apikey (GRATIS)
- **Cerebras**: https://cerebras.ai (GRATIS)
- **OpenRouter**: https://openrouter.ai (pago por uso)
- **Claude**: Proxy local o API directa de Anthropic

### 5. Configurar Ollama (Opcional pero Recomendado)

```bash
# Instalar Ollama desde https://ollama.ai/download
ollama pull qwen2.5:3b
ollama pull qwen2.5:7b
```

Modelos recomendados:
- `qwen2.5:3b` - Rápido, para tareas simples
- `qwen2.5:7b` - Balance calidad/velocidad
- `llama3.2:3b` - Alternativa ligera

---

## 🎮 Uso

### Iniciar Jarvis

**Método 1: Batch File (Recomendado)**
```bash
START_JARVIS_FULL.bat
```

**Método 2: Manual**
```bash
# Terminal 1: Backend
cd backend
python main.py

# Terminal 2: Frontend
cd frontend
npm run dev
```

### Comandos de Voz Comunes

```
"Jarvis, abre Visual Studio Code"
"¿Qué tiempo hace en CDMX?"
"Busca información sobre Claude 4.0"
"Toma una captura y analízala"
"Lee mi vault de Obsidian sobre IA"
"Reproduce música en Spotify"
```

### API REST

Backend corre en `http://localhost:8000`

**Endpoints principales**:
- `POST /chat` - Enviar mensaje de texto
- `POST /voice` - Enviar audio (base64)
- `GET /health` - Health check
- `GET /models` - Modelos disponibles

---

## 📁 Estructura del Proyecto

```
JarvisAI/
├── backend/
│   ├── main.py              # FastAPI server principal
│   ├── config.py            # Configuración (settings.py)
│   ├── core/
│   │   ├── ollama_client.py    # Cliente Ollama
│   │   ├── claude_client.py    # Cliente Claude
│   │   ├── free_ai_client.py   # Gemini/Cerebras
│   │   ├── voice.py            # faster-whisper + edge-tts
│   │   ├── camera.py           # Screenshot + vision
│   │   └── memory.py           # Memoria persistente
│   ├── integrations/
│   │   ├── obsidian.py         # Vault reader
│   │   ├── weather.py          # Weather API
│   │   ├── shopify_client.py   # Shopify API
│   │   ├── spotify_client.py   # Spotify control
│   │   ├── web_search.py       # Serper API
│   │   └── pc_control.py       # System control
│   └── requirements.txt
├── frontend/
│   ├── main.js              # Electron main process
│   ├── src/
│   │   └── App.jsx          # React UI
│   └── package.json
├── data/
│   ├── jarvis-service.log   # Logs principales
│   ├── memory.json          # Memoria de hechos
│   └── chat_history.json    # Historial de chat
├── .env                     # Variables de entorno
├── install.ps1              # Script de instalación
└── README.md                # Este archivo
```

---

## 🔧 Troubleshooting

### Error: "No module named 'faster_whisper'"
```bash
pip install faster-whisper==1.0.3
```

### Error: "CUDA not available"
Si tienes GPU NVIDIA pero faster-whisper no detecta CUDA:
```bash
pip uninstall torch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Error: "Ollama connection refused"
```bash
# Iniciar Ollama server
ollama serve
```

### Frontend no conecta al backend
Verificar que el backend esté corriendo en `http://localhost:8000`:
```bash
curl http://localhost:8000/health
```

### Logs de Debug
```bash
tail -f data/jarvis-service.log
```

---

## 🔐 Seguridad

- **NUNCA** commitear `.env` al repo (está en `.gitignore`)
- **NUNCA** compartir `JARVIS_API_TOKEN` públicamente
- **Rotar** API keys cada 90 días
- **Restringir** permisos de lectura del vault Obsidian

---

## 🚢 Modelo de Entrega

Ver `MODELO-ENTREGA.md` para opciones de distribución:
1. **Repo Privado** (GitHub/GitLab)
2. **Binario Empaquetado** (Electron + PyInstaller)
3. **Servicio Hosted** (VM dedicada)

---

## 📝 Licencia

Propiedad de **Emmanuel Pedraza** (@Corgipollo). Uso comercial exclusivo.

---

## 🆘 Soporte

- **Documentación**: `docs/`
- **Issues**: GitHub Issues (repo privado)
- **Telegram**: @corgipollo
- **Email**: emmanuel@jarvis-ai.local

---

## 🎯 Roadmap

- [ ] Multi-tenancy (usuarios separados)
- [ ] Interfaz web (acceso remoto)
- [ ] Integración WhatsApp
- [ ] Skills personalizados (plugins)
- [ ] Mobile app (React Native)
