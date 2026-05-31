# 🔌 INTEGRACIÓN DEL FIRST RUN WIZARD — Snippets de Código

Este archivo contiene los snippets exactos para integrar el wizard en JarvisAI.

---

## 📁 Archivo 1: `backend/main.py`

### Agregar al Inicio (Después de Imports)

```python
# === IMPORTS EXISTENTES ===
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
# ... otros imports ...

# === AGREGAR ESTE IMPORT ===
from first_run_wizard import init_wizard_routes, FirstRunWizard
```

### Agregar Después de Crear `app = FastAPI()`

```python
# === CÓDIGO EXISTENTE ===
app = FastAPI(title="Jarvis AI Backend")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === AGREGAR ESTAS LÍNEAS ===

# Inicializar First Run Wizard
init_wizard_routes(app)

# Log si es primera ejecución
wizard = FirstRunWizard()
if wizard.is_first_run():
    logger.info("⭐ PRIMERA EJECUCIÓN DETECTADA — First Run Wizard activado")
else:
    logger.info("✓ Wizard ya completado anteriormente")
```

---

## 📁 Archivo 2: `frontend/src/App.jsx`

### Agregar Import al Inicio

```jsx
// === IMPORTS EXISTENTES ===
import React, { useState, useEffect } from 'react';
import './App.css';

// === AGREGAR ESTE IMPORT ===
import FirstRunWizard from './components/FirstRunWizard';
```

### Agregar State para el Wizard

```jsx
function App() {
  // === STATE EXISTENTE ===
  const [messages, setMessages] = useState([]);
  const [isRecording, setIsRecording] = useState(false);
  // ... otros states ...

  // === AGREGAR ESTE STATE ===
  const [showWizard, setShowWizard] = useState(false);
  const [isFirstRun, setIsFirstRun] = useState(false);
```

### Agregar useEffect para Detectar Primera Ejecución

```jsx
  // === AGREGAR ESTE useEffect AL FINAL DE LOS DEMÁS ===
  
  // Detectar si es primera ejecución
  useEffect(() => {
    const checkFirstRun = async () => {
      try {
        const response = await fetch('http://localhost:8000/wizard/status');
        const data = await response.json();
        
        if (data.is_first_run) {
          setIsFirstRun(true);
          setShowWizard(true);
        }
      } catch (error) {
        console.error('Error verificando primera ejecución:', error);
      }
    };

    // Esperar 2 segundos después de montar antes de mostrar wizard
    // (para que el backend termine de iniciar)
    const timer = setTimeout(() => {
      checkFirstRun();
    }, 2000);

    return () => clearTimeout(timer);
  }, []);
```

### Agregar Wizard al JSX Return

```jsx
  return (
    <div className="App">
      {/* === AGREGAR ESTE COMPONENTE AL INICIO === */}
      {showWizard && (
        <FirstRunWizard onClose={() => setShowWizard(false)} />
      )}

      {/* === RESTO DEL JSX EXISTENTE === */}
      <header className="App-header">
        <h1>Jarvis AI</h1>
        {/* ... resto del código ... */}
      </header>
      
      {/* ... resto de componentes ... */}
    </div>
  );
}
```

---

## 📁 Archivo 3: Crear `backend/data/.gitkeep`

Para asegurar que la carpeta `data/` exista en el repo:

```bash
# Ejecutar en terminal desde la raíz de JarvisAI
mkdir -p backend/data
touch backend/data/.gitkeep
```

Agregar a `.gitignore`:
```
# First Run Wizard state
backend/data/first_run_completed.flag
backend/data/wizard_state.json
```

---

## 📁 Archivo 4: Actualizar `backend/requirements.txt`

No hay dependencias nuevas necesarias (solo usa stdlib), pero asegúrate de tener:

```txt
fastapi==0.115.0
uvicorn[standard]==0.30.0
httpx==0.27.0  # Para verificar Claude proxy
```

---

## 🧪 TEST MANUAL

### 1. Test del Backend (Wizard API)

```bash
# Desde la raíz de JarvisAI
cd backend
python first_run_wizard.py
```

**Output esperado:**
```
=== FIRST RUN WIZARD TEST ===

¿Es primera ejecución? True

=== INTEGRACIONES DETECTADAS ===
✓ Gemini
✗ Spotify
✗ Obsidian
✗ Ollama
✗ Claude

=== CASOS DE USO DISPONIBLES ===
⭐ 🎤 Test Básico de Voz
   Prueba comandos simples sin integraciones
   Tiempo estimado: 1 min

=== TUTORIAL: Test Básico de Voz ===
Paso 1: Di hola
  Di: 'Jarvis, hola'
  Comando: 'Jarvis, hola'
...
```

### 2. Test del Frontend (Componente React)

```bash
# Desde la raíz de JarvisAI
cd frontend
npm run dev
```

**Verificar:**
1. Abre http://localhost:3000
2. Debería aparecer el wizard automáticamente (si es primera ejecución)
3. Click en "Empezar Tutorial"
4. Selecciona un caso de uso
5. Sigue el tutorial paso a paso

### 3. Test End-to-End

```bash
# Terminal 1: Backend
cd backend
python main.py

# Terminal 2: Frontend
cd frontend
npm run dev
```

**Flujo completo:**
1. Backend inicia → Log dice "PRIMERA EJECUCIÓN DETECTADA"
2. Frontend abre → Wizard aparece después de 2 segundos
3. Usuario completa un caso de uso
4. Wizard se cierra
5. Archivo `backend/data/first_run_completed.flag` se crea
6. Próxima vez que se inicie, wizard NO aparece

---

## 🔧 TROUBLESHOOTING

### Error: "Cannot find module 'FirstRunWizard'"

**Solución:**
Asegúrate de que el archivo existe en:
```
frontend/src/components/FirstRunWizard.jsx
frontend/src/components/FirstRunWizard.css
```

### Error: "Wizard status 404"

**Solución:**
El backend no tiene las rutas del wizard. Verifica que agregaste:
```python
from first_run_wizard import init_wizard_routes
init_wizard_routes(app)
```

### Wizard no aparece en el frontend

**Causas posibles:**
1. **Backend no está corriendo** → Iniciar `python main.py`
2. **Flag file ya existe** → Borrar `backend/data/first_run_completed.flag`
3. **CORS bloqueado** → Verificar que CORS permite `http://localhost:3000`

**Test manual:**
```bash
# Verificar que la API responde
curl http://localhost:8000/wizard/status

# Debería retornar:
# {"is_first_run": true, "completion_percentage": 0, "completed_cases": []}
```

### Wizard aparece cada vez que inicio Jarvis

**Causa:** Flag file no se está creando.

**Solución:**
```bash
# Verificar permisos de escritura
ls -la backend/data/

# Si la carpeta no existe, crearla
mkdir -p backend/data

# Test manual: crear flag
touch backend/data/first_run_completed.flag
```

---

## ✅ CHECKLIST DE INTEGRACIÓN

Antes de commitear, verificar:

- [ ] `backend/first_run_wizard.py` creado
- [ ] `frontend/src/components/FirstRunWizard.jsx` creado
- [ ] `frontend/src/components/FirstRunWizard.css` creado
- [ ] `backend/main.py` modificado (import + init_wizard_routes)
- [ ] `frontend/src/App.jsx` modificado (import + state + useEffect)
- [ ] `backend/data/.gitkeep` creado
- [ ] `.gitignore` actualizado
- [ ] Test manual del backend PASA
- [ ] Test manual del frontend PASA
- [ ] Test end-to-end PASA
- [ ] Wizard se cierra correctamente al completar
- [ ] Flag file se crea en `backend/data/`
- [ ] Segunda ejecución NO muestra wizard

---

## 🚀 DEPLOY

Una vez integrado y testeado:

1. **Commit los cambios:**
   ```bash
   git add .
   git commit -m "feat: Agregar First Run Wizard para onboarding guiado"
   ```

2. **Actualizar instalador:**
   El `install-v2-zero-friction.ps1` ya crea la carpeta `data/` automáticamente.

3. **Documentar en README:**
   Agregar sección en `README.md`:
   ```markdown
   ## 🎯 First Run Wizard
   
   La primera vez que inicias Jarvis, aparecerá un tutorial guiado que te ayudará
   a probar casos de uso reales en minutos. El wizard detecta automáticamente qué
   integraciones tienes configuradas y te sugiere el mejor punto de inicio.
   ```

---

## 📊 MÉTRICAS A TRACKEAR (Futuro)

Si quieres medir el éxito del wizard, agregar telemetría básica:

```python
# En first_run_wizard.py

def track_wizard_event(event_name: str, data: dict = None):
    """Envía evento de telemetría (opt-in)"""
    if os.getenv("JARVIS_TELEMETRY_ENABLED") == "true":
        # Implementar telemetría aquí (Mixpanel, PostHog, etc.)
        pass
```

**Eventos a trackear:**
- `wizard_started`
- `wizard_case_selected` (con `case_id`)
- `wizard_case_completed` (con `case_id` + tiempo tomado)
- `wizard_finished`
- `wizard_skipped`

---

**DONE.** Con estos snippets, el First Run Wizard está 100% integrado en JarvisAI.
