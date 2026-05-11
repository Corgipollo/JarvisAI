# BRIEF PARA CLAUDE (dentro de la VM Win11Jarvis)

## Contexto

Eres Claude dentro de Antigravity en una VM Windows 11 aislada (VirtualBox).
El host (PC real de Emmanuel) tiene un sistema "Jarvis" que el otro Claude
construyó y necesita continuarlo aquí adentro de la VM.

Esta VM se llama **Win11Jarvis** y va a ser la "PC dentro de la PC" donde
Jarvis vive y opera 24/7 como secretaria/agente autónomo.

## Lo que YA EXISTE (en el host, mapeado a esta VM via shared folders)

Cuando abras File Explorer (Win+E) → "Esta PC" debes ver 2 carpetas de red:

```
\\VBoxSvr\JarvisAI         (read-write)  → todo el código Jarvis
\\VBoxSvr\CerebroEmmanuel  (read-only)   → 2107 notas Obsidian del usuario
```

Si no aparecen: instalar **Guest Additions** desde menú VirtualBox →
"Dispositivos" → "Insertar imagen CD de Guest Additions" → ejecutar el .exe
→ reiniciar la VM. Después aparecen.

## Estructura del código (`\\VBoxSvr\JarvisAI`)

```
JarvisAI/
├── backend/
│   ├── integrations/
│   │   ├── pc_control.py        # cascade 6 estrategias para abrir apps
│   │   ├── windows_intel.py     # inventario sistema completo
│   │   ├── claude_client.py     # conexion Claude API
│   │   ├── free_ai_client.py    # Gemini gratis
│   │   └── ...
│   ├── skills/
│   │   ├── mouse.py             # click/drag/hover/type con jitter humano
│   │   ├── vision.py            # screenshot + OCR (Tesseract + Gemini)
│   │   ├── browser.py           # Playwright async wrapper
│   │   ├── files.py             # read/write/copy/grep
│   │   ├── nlp.py               # parse intent + execute_natural
│   │   └── ask_brain.py         # Claude CLI plan JSON ejecutable
│   └── main.py                  # FastAPI principal del backend
├── jarvis_core/                 # loop principal + state machine + UI
│   ├── loop.py                  # tick cada 3s, procesa queue
│   ├── state_machine.py         # idle/working/sleeping/overloaded/error
│   ├── queue_manager.py         # queue persistente JSON atomico
│   ├── curriculum_ai.py         # IA designa tareas progresivas
│   ├── event_stream.py          # stream JSONL para dashboard live
│   ├── web_server.py            # FastAPI :7777 con dashboard
│   └── web/dashboard.html       # UI cinematic en vivo
├── jarvis_learners/             # auto-mejora
│   ├── skill_learner.py         # aprende viendo YT tutoriales
│   ├── github_learner.py        # aprende de repos
│   ├── role_learner.py          # aprende roles profesionales completos
│   ├── mouse_explorer.py        # exploracion activa (toca y descubre)
│   ├── coach.py                 # tutor IA decide curriculum
│   ├── self_improvement.py      # loop autonomo
│   └── skill_executor.py        # valida que skill aprendida es ejecutable
├── jarvis_bridge/               # bridges externos
│   ├── claude_proxy.py          # proxy Anthropic-compatible -> Claude CLI
│   ├── cerebro_reader.py        # acceso al vault Obsidian del host
│   ├── multi_agent_dialog.py    # panel 4 agentes Claude (ANALYST/CRITIC/...)
│   └── telegram_bot.py          # bot Telegram para tareas remotas
├── jarvis_trainer/              # trainer scheduled task (legacy)
├── sandbox_vm/                  # ESTA carpeta — config de esta VM
├── data/
│   ├── skill_library/           # skills aprendidas (1 ahora: screenshot)
│   ├── role_library/            # roles aprendidos (1: secretaria, 16 skills auto-encoladas)
│   ├── tutorial_cache/          # videos YT descargados
│   ├── windows_inventory.json   # inventario del host (apps instaladas)
│   ├── jarvis_queue.json        # cola de tareas pendientes
│   ├── jarvis_events.jsonl      # eventos para dashboard
│   ├── gaps.json                # ~30 skills pendientes en curriculum
│   └── ...
├── requirements.txt             # deps Python (46 paquetes)
└── BRIEF_PARA_CLAUDE_EN_VM.md   # este archivo
```

## Lo que TIENES QUE HACER aquí adentro de la VM

### Paso 1 — Instalar Python 3.11 (si no está)

```powershell
# Verificar
python --version
# Si no existe, instalar:
winget install --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
```

### Paso 2 — Copiar Jarvis a una carpeta writable de la VM

```powershell
$dest = "C:\Jarvis"
New-Item -ItemType Directory -Path $dest -Force | Out-Null
Copy-Item -Path "\\VBoxSvr\JarvisAI\*" -Destination $dest -Recurse -Force
cd $dest
```

### Paso 3 — Instalar dependencias

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyautogui psutil pygetwindow pyyaml pywin32 fastapi uvicorn pytesseract pillow easyocr faster-whisper edge-tts requests playwright python-telegram-bot
python -m playwright install chromium
```

### Paso 4 — Instalar Tesseract OCR

```powershell
winget install --id UB-Mannheim.TesseractOCR --accept-package-agreements --accept-source-agreements
```

### Paso 5 — Arrancar los 3 servicios core

**Terminal 1 — Claude proxy:**
```powershell
cd C:\Jarvis
python -m uvicorn jarvis_bridge.claude_proxy:app --host 0.0.0.0 --port 8088
```
Requiere Claude CLI instalado: `npm install -g @anthropic-ai/claude-code`

**Terminal 2 — Web dashboard:**
```powershell
python -m uvicorn jarvis_core.web_server:app --host 0.0.0.0 --port 7777
```
Abrir browser dentro de la VM: http://localhost:7777

**Terminal 3 — Loop principal:**
```powershell
$env:JARVIS_SANDBOX = "0"  # estamos en VM aislada, modo real OK
python -m jarvis_core.loop
```

### Paso 6 — Arrancar self-improvement loop (background)

```powershell
Start-Process python -ArgumentList "jarvis_learners/self_improvement.py" -WindowStyle Hidden
Start-Process python -ArgumentList "jarvis_learners/coach.py" -WindowStyle Hidden
```

### Paso 7 — (Opcional) Conectar Telegram

1. Crear bot con @BotFather → obtener token
2. Crear `config_telegram.json`:
```json
{"bot_token": "TU_TOKEN", "allowed_user_ids": [TU_USER_ID]}
```
3. Arrancar:
```powershell
python jarvis_bridge/telegram_bot.py
```

## Lo que YA APRENDIÓ Jarvis (en `data/`)

- **1 skill**: tomar screenshot en Windows (77.8% ejecutable, 9 steps + 6 atajos)
- **1 rol**: secretaria (9 daily_tasks + 8 tools + 16 skills auto-encoladas)
- **30 skills pendientes** en `gaps.json` (outlook, word, excel, capcut, etc.)
- **1174 frames** procesados de tutoriales
- **4 videos** YouTube cached

## Filosofía del sistema (importante)

- **NO duplica tutoriales** — abstrae principios
- **Aprende viendo + tocando** (skill_learner ve YT, mouse_explorer toca apps)
- **Coach IA decide curriculum** (no hardcoded)
- **Self-improvement 24/7** sin intervención humana
- **Multi-agent dialog** (consulta 4 sub-Claudes para decisiones complejas)
- **Cerebro Obsidian** del usuario montado como contexto

## Reglas que el usuario te dio (Emmanuel)

1. **NUNCA preguntar** "¿quieres que haga X?" — solo hacer
2. **Modo autónomo total** — si algo falla, retry hasta lograr
3. **Aprender, NO duplicar** — abstraer principios
4. **Memoria persistente** — todo se guarda en JSONL
5. **Trabajo como secretaria** — eventual workflows tipo "edita 10 cortes de
   este video y súbelos a TikTok"

## Tu primer task (después del setup)

Cuando todo esté arrancado dentro de la VM, ejecuta:

```powershell
python jarvis_learners/role_learner.py "editor de video TikTok viral"
```

Esto:
- Baja 5 tutoriales de "como ser editor TikTok viral"
- Transcribe con Whisper
- Sintetiza el rol completo
- Auto-encola 10-15 skills atómicas en `gaps.json`
- El self_improvement loop las aprende

Después: reporta a Emmanuel con el role profile completo + cuántas skills
nuevas se encolaron.

## Continuidad

Cuando termines el setup, escribe un mensaje a Emmanuel diciendo:
- Qué está corriendo
- Qué URL del dashboard usar (http://localhost:7777 dentro de la VM)
- Cuántas skills/roles ya hay en la library
- Qué viene siguiente

---

**Listo. Continúa el setup. Si algo falla, retry con tu propio criterio. No
preguntes "¿quieres que haga X?", solo hazlo.**
