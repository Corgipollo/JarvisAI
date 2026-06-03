# 🤖 Jarvis V3 - Asistente Personal AI

> **Agente autónomo Computer Use para Windows** - Piensa antes de actuar, no es un macro.

Jarvis V3 es una secretaria inteligente que puede:
- ✅ Ejecutar tareas complejas en Windows (GUI + código)
- ✅ Navegar navegadores, llenar formularios, subir archivos
- ✅ Aprender de sus ejecuciones (skills con memoria persistente)
- ✅ Verificar resultados reales (no "se ve bien", sino validación por comando)
- ✅ Usar Claude Opus 4.6 via tu suscripción ($0 costo de modelo)

---

## ⚡ Instalación Rápida (5 minutos)

### Windows 11 - One-Click Installer

```batch
# 1. Descarga el release v1.0.0
# 2. Descomprime jarvis-v3-v1.0.0.zip
# 3. Ejecuta:
setup_jarvis.bat

# 4. Configura API keys:
cd jarvis_v3
copy .env.template .env
notepad .env

# 5. Lanza Jarvis:
# Doble-click en "Jarvis V3" en tu Desktop
```

**¡Listo!** 🚀

---

## 📋 Requisitos

| Item | Mínimo | Recomendado |
|------|--------|-------------|
| **OS** | Windows 10 | Windows 11 |
| **Python** | 3.10+ | 3.11+ |
| **RAM** | 8 GB | 16 GB |
| **GPU** | Ninguna (CPU OK) | NVIDIA RTX (CUDA) |
| **Disco** | 10 GB | 20 GB |

---

## 🧠 API Keys (Gratis)

### 1. Gemini Free (1500 req/día)
```bash
# https://aistudio.google.com/app/apikey
GEMINI_API_KEY=AIza...
```

### 2. Cerebras Fast (Gratis ilimitado)
```bash
# https://cloud.cerebras.ai/
CEREBRAS_API_KEY=csk-...
```

### 3. Claude API (Opcional - usa tu suscripción)
```bash
# https://console.anthropic.com/settings/keys
ANTHROPIC_API_KEY=sk-ant-api03-...
```

---

## 🎯 ¿Qué Puede Hacer?

### Ejemplos Reales

```python
from jarvis_v3_core.sdk_agent import run_agent

# Ejemplo 1: Subir video a YouTube
run_agent("""
Sube el video E:/content/video.mp4 a YouTube:
- Título: "Demo Jarvis V3"
- Descripción: generala tú
- Etiquetas: AI, automation, jarvis
""")

# Ejemplo 2: Crear cuenta con datos reales
run_agent("""
Crea cuenta en example.com con mis datos:
- Email: emmanuel@example.com
- Password: genera uno seguro y guárdalo
""")

# Ejemplo 3: Investigación + acción
run_agent("""
Investiga los 3 mejores plugins de WordPress para SEO,
instálalos en mi sitio local, y configúralos según best practices
""")
```

### Características Clave

- 🧠 **Piensa antes de actuar** - Ciclo: PLAN → EJECUTA → VERIFICA
- 🔄 **Aprendizaje persistente** - Guarda skills exitosos para reusar
- 🛡️ **Safety guards** - Bloquea comandos destructivos automáticamente
- 🔍 **Verificación real** - Confirma con comandos, no con la vista
- 📊 **Multi-cerebro** - Claude (premium) → Gemini/Cerebras (gratis) → Ollama (local)

---

## 📁 Estructura del Proyecto

```
JarvisAI/
├── setup_jarvis.bat              ← Instalador one-click
├── verificar_instalacion.bat     ← Test post-instalación
├── requirements.txt              ← Dependencias master
├── README.md                     ← Este archivo
│
└── jarvis_v3/
    ├── .env.template             ← Template de configuración
    ├── jarvis_v3_core/           ← Core engine
    │   ├── sdk_agent.py          ← SDK principal
    │   ├── run_forever.py        ← Daemon mode
    │   └── mcp_server.py         ← MCP server
    ├── ufo/                      ← Windows automation (submodule)
    ├── appagent/                 ← Visual perception (submodule)
    └── data/autonomy/            ← Skills aprendidos + logs
```

---

## 🚀 Uso

### Modo Desktop (Recomendado)

1. Doble-click en "Jarvis V3" en Desktop
2. Habla o escribe tu tarea
3. Jarvis ejecuta y verifica

### Modo Programático

```python
from jarvis_v3_core.sdk_agent import run_agent

result = run_agent("Tu tarea aquí")
print(result)
```

### Modo Daemon (24/7)

```batch
cd jarvis_v3\jarvis_v3_core
..\venv\Scripts\python run_forever.py
```

---

## 🔧 Configuración Avanzada

### .env Completo

```bash
# Cerebros (prioridad: claude > free > ollama)
ANTHROPIC_API_KEY=sk-ant-api03-...
GEMINI_API_KEY=AIza...
CEREBRAS_API_KEY=csk-...
BRAIN_PRIORITY=claude,gemini,cerebras,ollama

# Hardware optimization
WHISPER_DEVICE=cuda  # o cpu
WHISPER_MODEL=base   # tiny, base, small, medium, large

# Safety
SAFETY_GUARD_ENABLED=true
MAX_RETRY_ATTEMPTS=3

# Telegram (opcional)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

---

## 📊 Benchmarks

### Instalación
- **Tiempo**: 3-5 minutos
- **Descarga**: ~500 MB
- **Espacio**: 2 GB (con venv)

### Performance (Windows 11 + RTX 3060)
- Tiempo de respuesta: 2-5s
- Percepción GUI: <1s (ui_scan)
- Ejecución código: instantánea

---

## 🐛 Troubleshooting

### Error: "Python NO encontrado"
```batch
# Reinstala Python 3.10+ y marca "Add Python to PATH"
# https://www.python.org/downloads/
```

### Error: "pip falló instalando dependencias"
```batch
python -m pip install --upgrade pip
setup_jarvis.bat
```

### Error: "pywin32 falló"
```batch
# Ejecutar como Administrador
# Click derecho en setup_jarvis.bat > "Ejecutar como administrador"
```

---

## 📚 Documentación

- **README-INSTALADOR.md** - Guía completa de instalación
- **INSTALACION.md** - Instalación paso a paso
- **jarvis_v3_core/README.md** - Arquitectura detallada
- **jarvis_v3_core/SKILLS.md** - Sistema de skills aprendidos

---

## 🔐 Seguridad

### Safety Guards Activos

- ✅ Bloquea `rm -rf`, `git clean`, `rmtree` de código
- ✅ `.env` en `.gitignore` (tus keys nunca se commitean)
- ✅ Confirmación antes de comandos destructivos
- ✅ Logs completos en `data/autonomy/logs/`

### Phishing Detection

Jarvis detecta y aborta automáticamente:
- URLs sospechosas
- Solicitudes de credenciales inesperadas
- Comandos que parecen trampa

---

## 🎨 Skills Aprendidos

Jarvis aprende de sus ejecuciones exitosas:

```python
# Primera vez: piensa paso a paso
run_agent("Sube video a YouTube con título X")
# → Navega GUI, resuelve problemas, verifica subida
# → Guarda skill "subir_youtube"

# Segunda vez: reutiliza el skill aprendido
run_agent("Sube otro video a YouTube con título Y")
# → Ejecuta skill guardado (10x más rápido)
```

Skills guardados en: `jarvis_v3/data/autonomy/skills/`

---

## 🌟 Casos de Uso

### Para Emprendedores
- Subir productos a Shopify/WooCommerce
- Publicar contenido en redes sociales
- Gestionar emails y CRM

### Para Developers
- Automatizar deploys
- Ejecutar tests E2E en navegador
- Gestionar repos GitHub

### Para Creadores
- Subir videos a YouTube/TikTok
- Editar y procesar archivos multimedia
- Investigar tendencias y competencia

---

## 🤝 Contribuir

```bash
# Fork el repo
git clone https://github.com/Corgipollo/JarvisAI.git
cd JarvisAI

# Crea branch
git checkout -b feature/nueva-funcionalidad

# Commits + push
git commit -m "feat: nueva funcionalidad"
git push origin feature/nueva-funcionalidad

# Abre PR
```

---

## 📄 Licencia

MIT License - Emmanuel Pedraza (Corgipollo)

---

## 🙏 Créditos

Construido sobre:
- [UFO](https://github.com/microsoft/UFO) - Windows UI automation
- [AppAgent](https://github.com/mnotgod96/AppAgent) - Visual perception
- [Anthropic Claude](https://anthropic.com) - Reasoning engine
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP server framework

---

## 📞 Soporte

- **GitHub Issues**: https://github.com/Corgipollo/JarvisAI/issues
- **Telegram**: [@Corgipollo](https://t.me/Corgipollo)
- **Email**: emmanuel@example.com

---

**Hecho con 🧠 por Emmanuel Pedraza**  
*Jarvis V3 - Computer Use Agent para Windows*

**Landing Page**: https://jarvis.antigravitylab.dev  
**Repo**: https://github.com/Corgipollo/JarvisAI
