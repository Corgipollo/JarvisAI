# Jarvis Omniparser Architecture — Ojos y Manos Continuas

> **Objetivo**: superar el OCR ciego y dar a Jarvis comprensión semántica
> continua de cualquier GUI Windows (CapCut, Shopify, Telegram, navegadores).
> **Fecha**: 2026-05-23
> **Status del documento**: arquitectura aprobada, listo para implementación incremental
> **Costo target**: $0 vía Claude Max OAuth (anthropic_proxy) + modelos locales (YOLO + Florence)

---

## 1. Diagnóstico — por qué falla lo que ya tenemos

| Capa actual | Limitación |
|---|---|
| `desktop_hybrid` (OCR + cv2.matchTemplate) | OCR ciego: lee texto, no entiende roles. Templates frágiles ante resize, theme dark/light, escala DPI |
| `vision_locate` (Gemini Vision por query) | Reactivo (un screenshot, un click). No mantiene mapa persistente. Latencia 2-5s por consulta |
| `set_of_mark` (UIA Windows) | UIA solo cubre apps win32/UWP. CapCut/Brave/Electron casi siempre devuelven árboles vacíos |
| Coordenadas X/Y estáticas | Mueres ante cualquier resize, scroll, o cambio de versión de la app |

**Lo que necesitamos**: un **grafo semántico de la pantalla** que se actualiza continuamente, donde cada elemento tiene rol (timeline, clip, button, slider) + caption funcional ("botón Export en esquina superior derecha"), y un **closed-loop** que verifica la acción antes/después de ejecutarla.

---

## 2. State of the art (verificado mayo 2026)

### 2.1 OmniParser v2.0.1 (Microsoft, sep 2025)
- **Repo**: github.com/microsoft/OmniParser — 24.8k stars
- **Arquitectura dual**:
  - **Icon detector**: YOLO custom entrenado en datasets de screenshots → bounding boxes de elementos interactivos
  - **Caption model**: `icon_caption_florence` (Florence-2-base fine-tuned) → genera descripción semántica funcional de cada bbox ("settings gear, top-right")
- **Benchmark**: 39.5% en **Screen Spot Pro** (grounding fine-grained). En V1.5 era ~25%
- **Salida**: JSON estructurado `[{bbox, type, content, interactable, source}]`
- **Integrado con**: Anthropic Computer Use, OpenAI 4o/o1/o3-mini, DeepSeek R1, Qwen 2.5VL — vía `OmniTool`
- **Hardware**: corre en GPU (idealmente >=6GB VRAM para inferencia fluida). En CPU es viable pero 5-10x más lento
- **Paper**: arXiv 2408.00203

### 2.2 Anthropic Computer Use API (beta vigente 2025-11-24)
- **Modelos con soporte oficial**:
  - Beta header `computer-use-2025-11-24`: Opus 4.7, Opus 4.6, **Sonnet 4.6**, Opus 4.5
  - Beta header `computer-use-2025-01-24`: Sonnet 4.5, **Haiku 4.5**, Opus 4.1
- **Tools nativas en el tool-use schema**:
  - `screenshot` — captura pantalla
  - `mouse_move`, `left_click`, `right_click`, `double_click`, `triple_click`, `middle_click`
  - `left_click_drag` (drag-and-drop nativo, crítico para CapCut timeline)
  - `key`, `type` (texto y combinaciones xdotool-style: `ctrl+s`)
  - `scroll` (vertical/horizontal con cantidad)
  - `wait` (sleep determinista entre acciones)
- **Modo de operación**: tú ejecutas las acciones localmente (con pyautogui/pynput) y le mandas screenshots de vuelta. El modelo NO ejecuta nada por sí mismo, **vos sos los músculos**. Eso es exactamente lo que queremos para soberanía local
- **Latencia típica**: 800-1500ms por turno con Haiku 4.5, 1500-3000ms con Sonnet 4.6
- **Costo**: Sonnet 4.6 ~$3/Mtok in / $15/Mtok out + ~1500 tok de imagen por screenshot. Haiku 4.5 ~$1/Mtok. **Vía anthropic_proxy OAuth Max = $0** (lo que ya tenés montado)

### 2.3 UI-ED (User Interface Element Detection)
- Línea de research académica más amplia que OmniParser. Incluye trabajos como **ClickBench**, **Mind2Web**, **OS-Atlas**
- **OS-Atlas-Base 7B** (open-source, octubre 2024) es el competidor directo de OmniParser para grounding. Más liviano pero similar accuracy en menus complejos
- **ScreenAgent** (chinos): añade tracking del cursor del propio agente para closed-loop — exactamente lo que vos pediste en step 3

---

## 3. Stack técnico para Jarvis V2

### 3.1 Hardware mínimo verificado
- **GPU**: NVIDIA RTX (la que ya tenés). Ideal >=8GB VRAM. CPU funciona pero pierde el feedback en tiempo real
- **RAM**: 16GB+ (tenés 15.7GB visible — al límite. F5-TTS ya comimos pagefile). Para OmniParser cargado simultáneamente con voice_engine probablemente toque cerrar Brave Chromium pesado durante sesiones de control GUI
- **Disco**: ~3 GB para modelos OmniParser (YOLO + Florence)

### 3.2 Librerías Python — install bundle

```bash
# Captura + injection nativa (lo que ya tenés)
pip install mss>=9.0 pyautogui pynput pillow opencv-python

# OmniParser stack
pip install ultralytics>=8.3.0     # YOLO inference
pip install transformers>=4.45     # Florence-2 + processor
pip install torch>=2.4 torchvision # CUDA build si GPU
pip install easyocr                # fallback OCR ya en uso

# LLM client (anthropic_proxy ya existe)
pip install anthropic>=0.39        # SDK oficial Computer Use
pip install httpx                  # ya en uso

# Audio para CapCut peak detection
pip install librosa>=0.10          # FFT + onset detection
pip install soundfile

# Closed-loop diff
pip install numpy scikit-image     # SSIM, mean-pixel-diff
```

**Total install size**: ~6 GB (PyTorch+CUDA pesa). En tu setup actual la mayoría ya está (torch, transformers, easyocr listos).

### 3.3 Descarga de modelos (one-shot)

```bash
# OmniParser weights — desde HuggingFace, ~1.2 GB total
huggingface-cli download microsoft/OmniParser-v2.0 \
    icon_detect/best.pt \
    icon_caption_florence/ \
    --local-dir C:/Users/Emmanuel/Documents/JarvisAI/models/omniparser

# Renombrar caption dir (requirement del repo)
mv .../icon_caption_florence_tmp .../icon_caption_florence
```

### 3.4 Wrapper Python — `jarvis_v2/skills/omniparser_engine.py`

```python
"""omniparser_engine.py - Wrapper Jarvis sobre OmniParser v2.0.

API:
    parse(screenshot_path | PIL.Image) -> list[Element]
    where Element = {
        "bbox": (x1, y1, x2, y2),
        "center": (cx, cy),
        "type": "icon" | "text" | "button" | "input" | ...,
        "caption": "string semantic",
        "interactable": bool,
        "confidence": float,
    }
"""
from pathlib import Path
from ultralytics import YOLO
from transformers import AutoProcessor, AutoModelForCausalLM
import torch

MODELS_DIR = Path("models/omniparser")
_yolo = None
_florence_proc = None
_florence_model = None

def _lazy_load():
    global _yolo, _florence_proc, _florence_model
    if _yolo is None:
        _yolo = YOLO(MODELS_DIR / "icon_detect/best.pt")
        _florence_proc = AutoProcessor.from_pretrained(
            MODELS_DIR / "icon_caption_florence", trust_remote_code=True)
        _florence_model = AutoModelForCausalLM.from_pretrained(
            MODELS_DIR / "icon_caption_florence",
            torch_dtype=torch.float16, trust_remote_code=True,
        ).to("cuda")

def parse(image) -> list[dict]:
    _lazy_load()
    detections = _yolo(image, verbose=False)[0]
    elements = []
    for box in detections.boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        crop = image.crop((x1, y1, x2, y2))
        caption = _caption(crop)  # Florence inference
        elements.append({
            "bbox": (x1, y1, x2, y2),
            "center": ((x1+x2)/2, (y1+y2)/2),
            "type": _yolo.names[int(box.cls)],
            "caption": caption,
            "interactable": _is_interactable(box),
            "confidence": float(box.conf),
        })
    return elements
```

### 3.5 Cache + dedup (crítico para 500ms loop)

OmniParser full-frame tarda 800-1500ms en GPU. Para correr **cada 500ms** necesitamos:

1. **Diff de frame primero** (mean-pixel-diff con `cv2.absdiff` < threshold → no re-parsear)
2. **ROI parsing**: si sabemos en qué app estamos, parsear solo la región interactiva (top-bar, sidebar, timeline)
3. **TTL cache de 2s** sobre el grafo semántico
4. **Pipeline async**: detección YOLO (rápida ~80ms) cada 500ms, caption Florence (lenta ~400ms) solo si nuevo bbox

```
              ┌─────────────┐
   t=0ms ──── │ mss capture │ ~20ms
              └──────┬──────┘
                     ▼
              ┌─────────────────┐
              │ frame diff vs t-1 │ ~5ms (cv2)
              └──────┬──────────┘
                     ▼
              ┌────────────────────────┐
              │ diff > threshold?      │
              └─┬──────────────────┬───┘
                │ YES              │ NO
                ▼                  ▼
       ┌──────────────────┐   ┌────────────┐
       │ YOLO bbox detect │   │ reuse last │
       │  ~80ms (GPU)     │   │   graph    │
       └────────┬─────────┘   └────────────┘
                ▼
       ┌──────────────────┐
       │ Florence caption │
       │   ~400ms (GPU)   │
       │   solo nuevos    │
       └────────┬─────────┘
                ▼
       Semantic graph @ t
```

**Throughput esperado**: 2-4 frames parseados/s en RTX modesta. Suficiente para tareas no time-critical (CapCut, Shopify) pero no para FPS games.

---

## 4. Closed-Loop Feedback System

Idea central: **antes de hacer click, verificar dónde está realmente el cursor; después del click, verificar que la pantalla cambió como esperábamos.**

### 4.1 Loop principal

```python
"""jarvis_v2/skills/closed_loop_controller.py"""
import time, pyautogui, mss
from jarvis_v2.skills.omniparser_engine import parse
from jarvis_v2.skills.vision_locate import locate  # fallback Gemini

CURSOR_TEMPLATE = "models/cursor_arrow.png"  # bbox del cursor windows default

def execute_action_verified(action: dict, deadline_ms: int = 5000) -> dict:
    """
    action = {"type": "click", "target_desc": "Export button", ...}
    Closed-loop hasta que la pantalla confirma el cambio o expira deadline.
    """
    start = time.time()

    # PHASE 1 — Localizar target con visión semántica
    graph = parse(screenshot())
    target = _match_semantic(graph, action["target_desc"])
    if not target:
        # Fallback: Gemini vision puntual
        coords = locate(action["target_desc"])
        if not coords:
            return {"ok": False, "error": "target_not_found"}
        tx, ty = coords
    else:
        tx, ty = target["center"]

    # PHASE 2 — Pre-move + verify cursor llegó
    pyautogui.moveTo(tx, ty, duration=0.25)
    for _ in range(3):
        time.sleep(0.1)
        actual = _detect_cursor_position()
        if abs(actual[0] - tx) < 10 and abs(actual[1] - ty) < 10:
            break
        # Corrección: cursor desplazado por DPI/multi-monitor
        pyautogui.moveTo(tx + (tx - actual[0]), ty + (ty - actual[1]),
                          duration=0.15)

    # PHASE 3 — Snapshot ANTES
    before = screenshot()

    # PHASE 4 — Acción
    if action["type"] == "click":
        pyautogui.click()
    elif action["type"] == "drag":
        pyautogui.dragTo(action["dest"][0], action["dest"][1], duration=0.5)

    # PHASE 5 — Verify cambio
    time.sleep(0.3)
    after = screenshot()
    if _ssim(before, after) > 0.995:
        # Pantalla NO cambió → click no registró, o target era no-interactable
        return {"ok": False, "error": "no_visual_change",
                "retry_strategy": "re_parse_and_retry"}

    return {"ok": True, "elapsed_ms": int((time.time() - start) * 1000)}


def _detect_cursor_position() -> tuple[int, int]:
    """Match template del cursor en screenshot actual.
    Más confiable que pyautogui.position() en multi-monitor + escalado DPI.
    """
    import cv2, numpy as np
    img = np.array(screenshot())
    tpl = cv2.imread(CURSOR_TEMPLATE, cv2.IMREAD_UNCHANGED)
    res = cv2.matchTemplate(img, tpl[:,:,:3], cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val < 0.7:
        return pyautogui.position()  # fallback
    return (max_loc[0] + tpl.shape[1]//2, max_loc[1] + tpl.shape[0]//2)


def _ssim(img_a, img_b) -> float:
    from skimage.metrics import structural_similarity
    import numpy as np
    a = np.array(img_a.convert("L"))
    b = np.array(img_b.convert("L"))
    return structural_similarity(a, b)
```

### 4.2 Por qué este loop es robusto

| Modo de falla | Cómo lo atrapa |
|---|---|
| Coordenadas X/Y desactualizadas por resize | `parse()` re-detecta cada vez, nunca usa coords cacheadas |
| Cursor saltó por DPI multi-monitor | `_detect_cursor_position()` por template match en pixels reales |
| App congelada (click no registra) | `_ssim(before, after) > 0.995` → retry |
| Target tapado por overlay/dialog | Re-parse next iteration descubre el nuevo elemento dominante |
| Drift de versión de la app | YOLO+Florence reconocen por shape+contexto, no por texto exacto |

### 4.3 Métricas a registrar en SQLite (`data/closed_loop_metrics.db`)

```sql
CREATE TABLE action_log (
    ts INTEGER, action_type TEXT, target_desc TEXT,
    target_x INT, target_y INT,
    cursor_landed_x INT, cursor_landed_y INT,
    drift_px INT,
    ssim_before_after REAL,
    success INT,
    elapsed_ms INT,
    error TEXT
);
```

Con esto, después de 100 sesiones, el sistema puede aprender qué targets son frágiles y qué `target_desc` son ambiguos (ej. "botón export" en CapCut vs Brave). Eso alimenta la memoria persistente del agente correspondiente.

---

## 5. Aplicación CapCut — pipeline end-to-end

### 5.1 Entrada: un archivo de guion estructurado

```yaml
# guion.yaml
project_name: "manhwa_cap_31"
output_path: "E:/manhwa_videos/cap_31.mp4"
clips:
  - source: "E:/manhwa_videos/cap_31/panel_001.png"
    duration: 2.5
    transition: "fade"
  - source: "E:/manhwa_videos/cap_31/panel_002.png"
    duration: 3.0
voiceover: "E:/manhwa_videos/cap_31/narration.mp3"
music: "C:/Users/Emmanuel/music/epic_bg.mp3"
audio_ducking: true
caption_track:
  font: "Bebas Neue"
  size: 72
  highlight_color: "#FFCC00"
```

### 5.2 Pipeline (8 fases)

```
Fase 1: ABRIR CAPCUT
  shell: start "" "C:\Program Files\CapCut\CapCut.exe"
  wait_for_window("CapCut", timeout=15)
  force_maximize_window("CapCut")  # ← ya existe en window_control.py

Fase 2: NUEVO PROYECTO
  graph = parse(screenshot)
  click_semantic(graph, "New Project button center")
  wait_for_visual_change()

Fase 3: IMPORTAR MEDIA (por cada clip del guion)
  click_semantic(graph, "Import media button left sidebar")
  # OS file dialog aparece → typed path absoluto
  type_action(clip.source)
  press_key("enter")
  verify(screenshot, "imported asset appears in media bin")

Fase 4: ARRASTRAR A TIMELINE
  # OmniParser ya tagueó el clip recién importado
  media_thumb = match_in_graph(graph, "newly imported asset")
  timeline_target = match_in_graph(graph, "timeline track 1 at current playhead position")
  drag_action(media_thumb.center, timeline_target.center)
  # Verify: SSIM debe diferir Y debe aparecer un nuevo "clip on timeline" en graph

Fase 5: AUDIO PEAKS → CUTS AUTOMÁTICOS
  # Pre-procesamiento offline antes de tocar UI
  import librosa
  y, sr = librosa.load(guion["voiceover"], sr=22050)
  onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time")
  # onsets = lista de timestamps en segundos donde hay picos
  for t in onsets:
      seek_timeline_to(t)              # type "ctrl+g" + número, o click coord en ruler
      keyboard_shortcut("ctrl+b")       # split clip at playhead (CapCut default)

Fase 6: APLICAR CAPTIONS (karaoke)
  # CapCut tiene "Auto-captions" desde menú Text
  click_semantic(graph, "Text menu top toolbar")
  click_semantic(graph, "Auto captions option in submenu")
  # Diálogo de idioma + fuente
  select_option("Spanish (Latin America)")
  click_semantic(graph, "Generate button")
  wait_for_change(timeout=60)  # auto-caption tarda 30-60s

Fase 7: EXPORTAR
  click_semantic(graph, "Export button top-right")
  type_action(guion["output_path"])  # path destino
  click_semantic(graph, "Export button in export dialog")
  wait_for_visual_change("export progress bar appears")
  wait_for_file_exists(guion["output_path"], timeout=600)

Fase 8: CIERRE Y REPORT
  notify_telegram(f"CapCut OK: {output_path} ({size_mb} MB)")
  log_to_memory_persistent("manhwa-pipeline", {"cap": 31, "duration_s": ...})
```

### 5.3 Funciones helper que faltan en el codebase actual

| Función | Propósito | Implementación |
|---|---|---|
| `match_in_graph(graph, desc)` | Encuentra Element cuyo caption matchea `desc` semánticamente | Cosine similarity entre embedding(desc) y embedding(elem.caption). Modelo: `sentence-transformers/all-MiniLM-L6-v2` (90MB, CPU OK) |
| `seek_timeline_to(seconds)` | Mueve playhead a timestamp exacto en CapCut | `ctrl+g` abre go-to-time dialog en CapCut, escribir `mm:ss.ms` |
| `wait_for_visual_change(timeout)` | Polling SSIM hasta que cambie | Loop 200ms con threshold |
| `wait_for_file_exists(path, timeout)` | Polling filesystem | `os.path.exists` cada 1s |
| `keyboard_shortcut(combo)` | Wrapper de `pyautogui.hotkey` con verify | Captura before/after |

---

## 6. Orden de implementación (4 sprints, 1 día c/u)

### Sprint 1 — Base
- [ ] Descargar OmniParser weights → `models/omniparser/`
- [ ] Implementar `omniparser_engine.py` con `parse()` y test contra screenshot CapCut
- [ ] Benchmark: parsear 1 frame CapCut → JSON. Target: <1500ms en RTX

### Sprint 2 — Closed-loop
- [ ] Implementar `closed_loop_controller.py` con `execute_action_verified()`
- [ ] `_detect_cursor_position()` con template match
- [ ] SQLite `closed_loop_metrics.db` + queries de análisis
- [ ] Test E2E: abrir Notepad, escribir "hola", verify con SSIM. Si pasa, abrir Brave, buscar "anthropic.com"

### Sprint 3 — Wrapper Anthropic Computer Use
- [ ] `jarvis_bridge/anthropic_computer_use.py` que use anthropic_proxy OAuth
- [ ] Beta header `computer-use-2025-01-24` (Haiku 4.5) o `computer-use-2025-11-24` (Sonnet 4.6)
- [ ] Bridge: el modelo emite tool_use, el wrapper traduce a pynput/pyautogui local
- [ ] Modo agéntico: dado un objetivo, el modelo planifica + emite acciones hasta done

### Sprint 4 — CapCut pipeline
- [ ] Parser de guion YAML
- [ ] Librosa onset detect + mapeo a comandos seek+split
- [ ] Sequencer de las 8 fases
- [ ] Test E2E: guion de 5 paneles → MP4 exportado sin intervención humana

---

## 7. Riesgos y mitigaciones

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| OmniParser confunde shortcuts iguales en distintas apps | Media | Tag prefix por ventana foreground (capturar `GetForegroundWindow().title` y prefijar todo el grafo) |
| GPU sobrecargada (F5-TTS + OmniParser simultáneo) | Alta | Mutex: si voice_engine corriendo, OmniParser cae a CPU mode. O quotaq de tiempo: voice nocturna, GUI control diurna |
| pyautogui no funciona en Brave/Electron con permisos limitados | Baja | Fallback a `keybd_event` Win32 nativo (ctypes) |
| CapCut UI change en una actualización rompe captions semánticos | Alta | El cache TTL+memoria persistente ya registra qué descripciones funcionaron. Re-train fine de Florence con tus screenshots de CapCut sería el endgame |
| Costo de Sonnet 4.6 vía Anthropic API si OAuth expira | Media | El proxy_fast ya tiene refresh automático del token. Watchdog ya monitorea. Si todo falla → fallback a Haiku 4.5 (3x más barato) |

---

## 8. Decisiones aprobadas (auto)

1. **YOLO+Florence (OmniParser v2.0.1)** > UI-ED u OS-Atlas por madurez del repo + integración Anthropic confirmada
2. **Closed-loop con SSIM after-state** > assumir éxito por returncode
3. **Anthropic Computer Use API** > construir el "cerebro de acción" desde cero. Es el SOTA single-agent en WebArena
4. **Haiku 4.5 default** + escalado a Sonnet 4.6 solo en fases ambiguas (>3 errors consecutivos) — protege costo
5. **mss > pyautogui.screenshot** (~3x más rápido en multi-monitor)
6. **CapCut como primer caso de uso E2E** > Shopify porque ya hay roadmap_grop.md atacándolo por API

---

## 9. Próximo paso concreto

`Sprint 1, paso 1`: ejecutar el download de OmniParser weights. Es ~1.2 GB, una sola vez. Después de eso, todo el resto está implementable sin más decisiones humanas.

```powershell
# Comando exacto, copiable:
huggingface-cli download microsoft/OmniParser-v2.0 `
    --local-dir C:\Users\Emmanuel\Documents\JarvisAI\models\omniparser `
    --include "icon_detect/*" "icon_caption_florence/*"
```

---

## Apéndice — Comparativa rápida vs lo que ya existe en Jarvis

| Capacidad | `vision_locate.py` actual | OmniParser + closed-loop |
|---|---|---|
| Mapa semántico persistente | ❌ Una query, un resultado | ✅ Grafo completo refrescado 2-4 Hz |
| Verify post-action | ❌ Asume éxito | ✅ SSIM + re-parse |
| Latencia por click | 2-5s (round-trip Gemini) | 0.5-1.5s (todo local + opcional LLM) |
| Costo | $0.001/call OpenRouter | $0 si todo local + OAuth Max |
| Robustez ante UI changes | Frágil (Gemini puede alucinar coords) | Robusta (YOLO entrenado en miles de UIs) |
| Drag-and-drop nativo | ❌ | ✅ (Computer Use API + pyautogui dragTo) |

**Veredicto**: `vision_locate.py` se conserva como fallback rápido para queries one-shot. OmniParser pasa a ser el motor principal para sesiones largas (CapCut, Shopify admin, edición Obsidian).
