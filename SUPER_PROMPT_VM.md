# SUPER PROMPT — Pegar a Claude dentro de la VM Win11Jarvis

Copia TODO lo de abajo (entre las dos líneas de ===) y pégalo en Antigravity / Claude CLI / Cursor dentro de la VM. Una sola conversación, una sola vez.

---

==========================================================================

# CONTEXTO COMPLETO — LEE TODO ANTES DE EJECUTAR NADA

Soy Emmanuel Pedraza (Corgipollo en GitHub). Tú eres Claude operando dentro
de una VM Windows 11 aislada llamada **Win11Jarvis**, montada en VirtualBox
en mi PC real (el host). El propósito de esta VM: ser la "PC dentro de la PC"
donde vive un agente autónomo llamado **Jarvis** que voy a usar como
secretaria/trabajador 24/7.

## Visión a largo plazo (lo que estamos construyendo)

Quiero un agente que:
1. Sepa usar el mouse con precisión (drag, click, hover, scroll humano)
2. Sepa navegar páginas web (Playwright + descubrimiento empírico)
3. Sepa usar TODAS las apps de Windows (descubre clickando + ve tutoriales)
4. Sepa editar video en CapCut, programar en VS Code, manejar Excel/Word/Outlook
5. Eventualmente: edite mis videos, suba a YouTube, conteste mi WhatsApp, haga
   investigación, busque proyectos freelance, "hacer una empresa"
6. Si NO sabe algo → busca tutoriales en YouTube + repos en GitHub →
   APRENDE (no copia literal, abstrae principios)
7. Memoria persistente (todo en JSONL + role_library + skill_library)
8. Multi-agente: puede consultar paneles de 4 sub-Claudes (analyst/critic/
   researcher/expert) para decisiones complejas
9. Acceso completo a mi cerebro Obsidian (2107 notas, 22 proyectos)
10. Telegram bot: yo le mando tareas desde mi celular → ella las ejecuta en
    esta VM → resultado de vuelta a Telegram

## Estado actual (el otro Claude — afuera, en el host — ya construyó)

En el host hay un repo completo `JarvisAI/` que está mapeado aquí adentro
de la VM como **shared folder read-write**:

```
\\VBoxSvr\JarvisAI         (write OK)  ← todo el código
\\VBoxSvr\CerebroEmmanuel  (read-only) ← mi vault Obsidian de 2107 notas
```

Si NO ves esas carpetas en Win+E → "Esta PC", instala primero **Guest
Additions** (menú VirtualBox → Dispositivos → "Insertar imagen CD de Guest
Additions"). Después aparecen.

Repo completo en GitHub: https://github.com/Corgipollo/JarvisAI

### Lo que YA está construido (30+ módulos)

```
backend/
  integrations/
    pc_control.py        Cascade 6 estrategias para abrir apps + verify psutil
    windows_intel.py     Inventario sistema (apps instaladas, hardware, red)
    claude_client.py     Conexión Claude API
  skills/
    mouse.py             click/drag_human con bezier + jitter humano
    vision.py            screenshot + OCR Tesseract + fallback Gemini Vision
    browser.py           Playwright async wrapper
    files.py             read/write/copy/grep
    nlp.py               parse_intent regex + fallback ask_brain
    ask_brain.py         Claude CLI devuelve JSON plan ejecutable

jarvis_core/
  loop.py                Loop principal asyncio (tick 3s)
  state_machine.py       idle/working/sleeping/overloaded/error
  queue_manager.py       Queue persistente JSON atómico
  event_stream.py        Stream JSONL para dashboard live
  web_server.py          FastAPI :7777 con endpoint /events
  web/dashboard.html     UI cinematic con avatar + terminal + skills list

jarvis_learners/         AUTO-MEJORA 24/7
  skill_learner.py       Aprende viendo YouTube (yt-dlp + whisper + frames+OCR)
  github_learner.py      Aprende leyendo repos
  role_learner.py        Aprende ROLES completos (secretaria/contador/editor)
  mouse_explorer.py      Exploración activa (toca y descubre)
  coach.py               Tutor IA que decide curriculum
  self_improvement.py    Loop autónomo: detecta gaps → aprende → valida
  skill_executor.py      Mide % executability de skill aprendida

jarvis_bridge/
  claude_proxy.py        Proxy Anthropic API → Claude CLI (usa mi plan Max gratis)
  cerebro_reader.py      Acceso al vault Obsidian del host
  multi_agent_dialog.py  Panel 4 sub-Claudes para decisiones
  telegram_bot.py        Bot Telegram para tareas remotas

data/
  skill_library/         1 skill aprendida (screenshot Windows 77.8% ejecutable)
  role_library/          1 rol aprendido (secretaria: 9 daily_tasks + 8 tools)
  gaps.json              ~30 skills pendientes en curriculum
  tutorial_cache/        4 videos YouTube + 1174 frames procesados
  windows_inventory.json Inventario completo del HOST (referencia)
```

## TU TAREA (en orden, sin preguntar)

Ejecuta los siguientes pasos. **NO me preguntes "¿quieres que haga X?" — sólo
hazlo.** Si algo falla, retry con tu propio criterio.

### Paso 1: instalar dependencias del sistema

Abre PowerShell admin y ejecuta:

```powershell
# Python 3.11
winget install --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements

# Node.js (para Claude CLI)
winget install --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements

# Git
winget install --id Git.Git --accept-package-agreements --accept-source-agreements

# Tesseract OCR
winget install --id UB-Mannheim.TesseractOCR --accept-package-agreements --accept-source-agreements

# VirtualBox Guest Additions (para que shared folders funcionen)
# Si no aparece como CD montado, ir al menú VirtualBox arriba: Dispositivos → Insertar CD Guest Additions
```

Reinicia PowerShell para que PATH se actualice.

### Paso 2: clonar Jarvis a una carpeta writable

```powershell
$dest = "C:\Jarvis"
git clone https://github.com/Corgipollo/JarvisAI.git $dest
cd $dest
```

Alternativa (si el shared folder está OK): copy del montado.

### Paso 3: instalar dependencias Python

```powershell
cd C:\Jarvis
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyautogui psutil pygetwindow pyyaml pywin32 fastapi uvicorn pytesseract pillow easyocr faster-whisper edge-tts requests playwright python-telegram-bot anthropic yt-dlp
python -m playwright install chromium
```

### Paso 4: instalar Claude CLI

```powershell
npm install -g @anthropic-ai/claude-code
claude --version
# Hacer login: claude login (sigue el flujo OAuth)
```

### Paso 5: arrancar los 4 servicios core (cada uno en su terminal)

**Terminal 1 — Claude proxy** (puerto 8088):
```powershell
cd C:\Jarvis
python -m uvicorn jarvis_bridge.claude_proxy:app --host 127.0.0.1 --port 8088
```

**Terminal 2 — Dashboard web** (puerto 7777):
```powershell
cd C:\Jarvis
python -m uvicorn jarvis_core.web_server:app --host 127.0.0.1 --port 7777
```

Abre browser DENTRO de la VM: http://localhost:7777 ← dashboard cinematic
con avatar animado, eventos live, stats, skills.

**Terminal 3 — Self-improvement loop:**
```powershell
cd C:\Jarvis
$env:JARVIS_SANDBOX = "0"
python jarvis_learners/self_improvement.py
```

**Terminal 4 — Coach loop:**
```powershell
cd C:\Jarvis
python jarvis_learners/coach.py
```

### Paso 6: validar todo está corriendo

```powershell
# Health check del proxy
curl http://127.0.0.1:8088/health

# Test claude CLI vía proxy
curl -X POST http://127.0.0.1:8088/v1/messages -H "Content-Type: application/json" -d '{\"model\":\"claude-sonnet-4-6\",\"messages\":[{\"role\":\"user\",\"content\":\"di OK\"}],\"max_tokens\":50}'

# Stats del dashboard
curl http://127.0.0.1:7777/events
```

### Paso 7: ejecutar PRIMER role_learner (editor de video TikTok)

```powershell
cd C:\Jarvis
python jarvis_learners/role_learner.py "editor de video TikTok viral"
```

Este pipeline:
1. Baja 5 tutoriales de "como ser editor TikTok viral"
2. Transcribe con Whisper
3. Sintetiza el rol completo (daily_tasks, tools, workflows, deliverables)
4. Auto-encola 10-15 skills atómicas en `data/gaps.json`
5. El self_improvement loop las aprende sin que digas nada

## Reglas inviolables (de Emmanuel)

1. **NUNCA preguntes** "¿quieres que haga X?" — sólo hazlo.
2. **Modo autónomo total** — si falla, retry hasta lograr o cae a alternativa.
3. **Aprender ≠ duplicar** — abstrae principios, no copies tutorial literal.
4. **Memoria persistente** — todo se guarda en JSONL en `data/`.
5. **TODOS los frames** del video se procesan (1 fps, no muestreo).
6. **Multi-agente** disponible: cuando dudes en decisión compleja, consulta
   `multi_agent_dialog.consult_panel(pregunta)` → 4 sub-Claudes te ayudan.
7. **Cerebro Obsidian** disponible: si la tarea es sobre algún proyecto mío
   (GROP, BotForex, ClipForge, Manhua, Jarvis, NeuroGrain, etc.), consulta
   `cerebro_reader.search_notes(query)` antes.
8. **NO toques apps reales del host** — sólo trabajas dentro de esta VM.
9. **Telegram bot** opcional: si quiero conectarlo te paso token vía
   `config_telegram.json` y arrancas `python jarvis_bridge/telegram_bot.py`.

## Cómo reportarme cuando termines el setup

Escribe un mensaje resumiendo:
1. Servicios corriendo (proxy/dashboard/loop/coach) — puertos
2. URLs accesibles dentro de la VM
3. Skills en library / roles en library
4. Resultado del primer role_learner (editor TikTok): cuántas skills nuevas se encolaron
5. Próximo task que el self_improvement loop va a procesar

## Si algo se rompe

- Proxy timeout → reduce prompt en `synthesize_role()` (cambia `[:4500]` a `[:3000]`)
- Hyper-V/CPU conflict → ya está deshabilitado al boot via `bcdedit /set hypervisorlaunchtype off`
- Encoding cp1252 → el código ya usa `sys.stdout.reconfigure(encoding="utf-8")`
- "No bootable" → ya está fixed con SATA disk + IDE DVD attached
- IDE diagnostics warnings sobre `faster_whisper`/`pytesseract` no encontrados → IRRELEVANTES (el linter mira Python 3.14, el código corre en 3.11 que sí los tiene)

## Última cosa importante

Cuando hayas terminado todo y reportado, **NO te detengas**. Sigue el loop:
- Cada vez que el self_improvement learn una skill nueva, valida con
  `skill_executor.py` y reportame el % de executability.
- Cuando el coach proponga un nuevo rol, ejecútalo automáticamente.
- Si ves un patrón en lo que aprendí, sugiéreme nuevos roles para enseñarme.

Empieza ahora. Sin preguntas.

==========================================================================

---

**Eso. Lo copias y pegas tal cual.**
