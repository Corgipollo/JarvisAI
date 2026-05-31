# 📦 Jarvis AI — Guía de Instalación Completa

> **Del `git clone` a "Jarvis listo" en menos de 5 minutos**

Este documento cubre **3 métodos de instalación** para Jarvis AI:

1. **PowerShell Installer** (Windows nativo, **RECOMENDADO** ⭐)
2. **Docker** (portable, cross-platform)
3. **Manual** (para desarrolladores)

---

## ⚡ Opción 1: PowerShell Installer (RECOMENDADO)

### Requisitos Previos

| Requisito | Versión Mínima | Descarga |
|-----------|---------------|----------|
| **Windows** | 10/11 64-bit | N/A |
| **Python** | 3.11.x | [python.org](https://www.python.org/downloads/release/python-3110/) |
| **Node.js** | 18.x+ | [nodejs.org](https://nodejs.org/) |
| **Git** | 2.x+ | [git-scm.com](https://git-scm.com/) |
| **RAM** | 8 GB+ | N/A |
| **GPU** | NVIDIA (opcional) | Para faster-whisper acelerado |

### Instalación en 3 Comandos

```powershell
# 1. Clonar repo
git clone https://github.com/Corgipollo/JarvisAI.git
cd JarvisAI

# 2. Ejecutar installer (modo unattended = sin preguntas)
powershell -ExecutionPolicy Bypass -File install-v2-zero-friction.ps1 -Unattended

# 3. ¡Listo! Jarvis se inicia automáticamente
```

### Modos del Installer

```powershell
# Modo Quick Test (solo lo mínimo para probar YA)
.\install-v2-zero-friction.ps1 -QuickTest

# Modo Dev (sin autostart, hot-reload)
.\install-v2-zero-friction.ps1 -DevMode

# Saltar validaciones (uso con precaución)
.\install-v2-zero-friction.ps1 -SkipChecks

# Modo unattended (CI/CD friendly, sin preguntas)
.\install-v2-zero-friction.ps1 -Unattended
```

### Qué Hace el Installer

El script `install-v2-zero-friction.ps1` ejecuta automáticamente:

1. ✅ **Pre-flight checks**:
   - Conexión a Internet
   - Puertos 8000/3000 libres
   - Espacio en disco (5+ GB)
   - Permisos admin (para autostart)

2. ✅ **Validación de requisitos**:
   - Python 3.11.x (faster-whisper requiere exactamente 3.11)
   - Node.js 18+
   - Git 2.x+
   - GPU CUDA (opcional, detecta automáticamente)

3. ✅ **Instalación de dependencias**:
   - Backend: `pip install -r backend/requirements.txt`
   - Frontend: `npm install` en `frontend/`
   - Modelos whisper (descarga automática en primer uso)

4. ✅ **Configuración**:
   - Crea `.env` desde template
   - Configura autostart (si permisos admin)
   - Valida puertos backend/frontend

5. ✅ **Verificación final**:
   - Backend responde en `http://localhost:8000/health`
   - Frontend carga en Electron
   - Test de integración voice (STT + TTS)

### Logs y Troubleshooting

Si algo falla, revisar:

```powershell
# Log del installer (se guarda automáticamente)
cat .\install-log-YYYY-MM-DD.txt

# Logs del servicio backend
cat .\data\jarvis-service.log

# Test manual del backend
cd backend
python main.py
# Debe decir "Uvicorn running on http://0.0.0.0:8000"

# Test manual del frontend
cd frontend
npm run dev
# Debe abrir ventana Electron
```

Ver [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) para errores comunes.

---

## 🐳 Opción 2: Docker (Cross-Platform)

### Requisitos Previos

- **Docker Desktop** 4.x+ ([docker.com](https://www.docker.com/products/docker-desktop/))
- **Docker Compose** 2.x+ (incluido en Docker Desktop)
- **Git**

### Instalación con Docker

```bash
# 1. Clonar repo
git clone https://github.com/Corgipollo/JarvisAI.git
cd JarvisAI

# 2. Copiar .env template
cp .env.example .env
# IMPORTANTE: Editar .env y agregar tus API keys

# 3. Build + run con docker-compose
docker-compose up -d

# 4. Verificar backend funcionando
curl http://localhost:8000/health
# Debe retornar: {"status":"ok"}

# 5. Ver logs
docker-compose logs -f backend
```

### Frontend con Docker (Limitación)

⚠️ **Electron en Docker es complejo** (requiere X11 forwarding en Linux, difícil en Windows).

**Recomendación**: Correr backend en Docker + frontend nativo:

```bash
# Backend en Docker
docker-compose up -d backend

# Frontend nativo (en otra terminal)
cd frontend
npm install
npm run dev
```

### GPU Support (NVIDIA CUDA)

Si tienes GPU NVIDIA y quieres acelerar faster-whisper:

```bash
# 1. Instalar nvidia-docker
# Ver: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html

# 2. Descomentar sección GPU en docker-compose.yml (líneas 52-57)

# 3. Rebuild
docker-compose up -d --build backend
```

### Comandos Útiles Docker

```bash
# Ver logs en vivo
docker-compose logs -f

# Reiniciar solo backend
docker-compose restart backend

# Entrar al contenedor
docker-compose exec backend bash

# Parar todo
docker-compose down

# Parar y limpiar volúmenes
docker-compose down -v
```

---

## 🛠️ Opción 3: Instalación Manual (Desarrolladores)

### 1. Clonar Repo

```bash
git clone https://github.com/Corgipollo/JarvisAI.git
cd JarvisAI
```

### 2. Configurar Backend

```bash
cd backend

# Crear virtualenv (recomendado)
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt

# Copiar .env template
cp ../.env.example ../.env
# Editar .env con tus API keys

# Iniciar backend
python main.py
# Debe escuchar en http://localhost:8000
```

### 3. Configurar Frontend

```bash
# En otra terminal
cd frontend

# Instalar dependencias
npm install

# Modo dev
npm run dev
# Abre ventana Electron con hot-reload

# Build producción
npm run build
# Genera ejecutable en dist/
```

### 4. Verificar Instalación

```bash
# Test backend health
curl http://localhost:8000/health

# Test WebSocket (STT stream)
# Abrir frontend y hablar por micrófono
# Logs deben mostrar transcripción en vivo
```

---

## 🧪 Testing de Instalación

### Script de Test Automatizado

Incluimos un script que valida la instalación completa:

```powershell
# Ejecutar test suite
.\scripts\test-install.ps1

# Test solo backend
.\scripts\test-install.ps1 -Component backend

# Test solo frontend
.\scripts\test-install.ps1 -Component frontend

# Test completo + guardar reporte
.\scripts\test-install.ps1 -GenerateReport
```

### Checklist Manual

- [ ] Python 3.11.x instalado y en PATH
- [ ] Node.js 18+ instalado
- [ ] Backend responde en `http://localhost:8000/health`
- [ ] Frontend abre ventana Electron
- [ ] `.env` tiene API keys válidas (Claude/Gemini/Ollama)
- [ ] Micrófono detectado (test con "Hola Jarvis")
- [ ] TTS funciona (Jarvis responde con voz)
- [ ] Logs en `data/jarvis-service.log` sin errores críticos

---

## 🔧 Configuración Post-Instalación

### API Keys Requeridas

Editar `.env` y agregar al menos UNA de estas:

```env
# Opción 1: Claude API (MEJOR calidad, contexto largo)
CLAUDE_API_KEY=sk-ant-xxxxx

# Opción 2: Gemini Pro (GRATIS hasta cierto límite)
GEMINI_API_KEY=AIzaSyxxxxx

# Opción 3: Cerebras (GRATIS, muy rápido)
CEREBRAS_API_KEY=csk_xxxxx

# Opción 4: Ollama local (NO requiere API key, offline)
# Solo asegurarse que Ollama esté corriendo: ollama serve
```

### Integración con Obsidian (Opcional)

```env
OBSIDIAN_VAULT_PATH=C:\\Users\\TuUsuario\\Documents\\TuVault
```

### Telegram Notifications (Opcional)

```env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234...
TELEGRAM_CHAT_ID=987654321
```

---

## 📊 Evidencia de Instalación Exitosa

### Logs Esperados

**Backend (data/jarvis-service.log)**:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
INFO:     Faster-whisper model loaded: base
INFO:     Edge-TTS voice ready: es-MX-DaliaNeural
```

**Frontend (consola Electron)**:
```
[Jarvis] Connected to backend ws://localhost:8000/ws
[Jarvis] Microphone access granted
[Jarvis] Ready to listen...
```

### Screenshots de Validación

Ver carpeta `docs/install-evidence/` para:
- ✅ Screenshot de health check exitoso
- ✅ Log de instalación sin errores
- ✅ Test de voz STT→LLM→TTS funcionando

---

## 🆘 Soporte

### Errores Comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `Python 3.12 incompatible` | faster-whisper requiere 3.11.x | Instalar Python 3.11 exacto |
| `Port 8000 already in use` | Otro servicio usando puerto | Matar proceso o cambiar puerto en .env |
| `CUDA not found` | GPU no detectada | Instalar CUDA Toolkit o usar CPU mode |
| `API key invalid` | Key incorrecta en .env | Verificar en dashboard del provider |
| `Module not found` | Dependencias no instaladas | `pip install -r requirements.txt` |

### Links Útiles

- 📖 [Documentación completa](./README.md)
- 🐛 [Troubleshooting](./TROUBLESHOOTING.md)
- 💬 [Discussions](https://github.com/Corgipollo/JarvisAI/discussions)
- 🐞 [Reportar bug](https://github.com/Corgipollo/JarvisAI/issues)

---

## 📝 Notas Importantes

1. **Python 3.11.x es OBLIGATORIO** — faster-whisper rompe con 3.12+
2. **No commitear `.env`** — ya está en `.gitignore`, contiene secretos
3. **GPU NVIDIA es OPCIONAL** — funciona en CPU pero más lento
4. **Electron requiere GUI** — no funciona en servidores headless (usar solo backend)
5. **Autostart solo con permisos admin** — el installer avisa si no los tienes

---

**¿Instalación exitosa? ¡Ahora prueba Jarvis!**

```powershell
# Decir: "Hola Jarvis, ¿qué puedes hacer?"
# Jarvis debería responder con voz listando sus capacidades
```

📹 Ver [video demo](./docs/demo-video.mp4) para ejemplo completo.

---

**Última actualización**: 2026-05-31  
**Versión**: 1.0  
**Autor**: Emmanuel Pedraza (@Corgipollo)
