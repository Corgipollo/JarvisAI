# 🤖 Jarvis V3 - One-Click Installer

> Instalador automático para Windows 11. De cero a Jarvis funcionando en 5 minutos.

## ⚡ Quick Start

```batch
# 1. Ejecuta el instalador
setup_jarvis.bat

# 2. Configura API keys
cd jarvis_v3
copy .env.example .env
notepad .env

# 3. Lanza Jarvis
# Doble-click en "Jarvis V3" en Desktop
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

## 🎯 Lo Que Hace

### Paso 1: Verificaciones
- ✅ Python 3.10+ instalado
- ✅ pip funcional
- ✅ Espacio en disco

### Paso 2: Instalación
- 📦 Crea entorno virtual (venv)
- 📥 Instala 40+ dependencias
- 🔧 Configura UFO + AppAgent + Claude SDK

### Paso 3: Configuración
- 📝 Genera `.env.example` con API keys template
- 🎯 Crea acceso directo en Desktop
- 🔐 Actualiza `.gitignore` (protege tus keys)

### Paso 4: Post-Install
- ✓ Verificación completa del sistema
- ✓ Test de dependencias core
- ✓ Health check automático

---

## 🧠 API Keys (Gratis)

### Gemini Free (1500 req/día)
1. Ve a: https://aistudio.google.com/app/apikey
2. Click "Create API Key"
3. Copia a `.env`:
   ```env
   GEMINI_API_KEY=AIza...
   ```

### Cerebras Fast (Gratis ilimitado)
1. Ve a: https://cloud.cerebras.ai/
2. Registra cuenta (email)
3. Copia API key a `.env`:
   ```env
   CEREBRAS_API_KEY=csk-...
   ```

### Claude API (Opcional - usa tu suscripción)
1. Ve a: https://console.anthropic.com/settings/keys
2. Copia key a `.env`:
   ```env
   ANTHROPIC_API_KEY=sk-ant-api03-...
   ```

---

## 🔧 Archivos Generados

```
JarvisAI/
├── setup_jarvis.bat              ← El instalador
├── verificar_instalacion.bat     ← Test post-instalación
├── INSTALACION.md                ← Guía completa
├── README-INSTALADOR.md          ← Este archivo
│
└── jarvis_v3/
    ├── .env                      ← TUS API KEYS (generado después)
    ├── .env.example              ← Template limpio
    ├── venv/                     ← Python aislado
    │   ├── Scripts/
    │   │   └── python.exe
    │   └── Lib/
    ├── jarvis_v3_core/           ← Core files
    └── data/autonomy/            ← Logs y estado
```

---

## ✅ Verificación Post-Instalación

Ejecuta el verificador:
```batch
verificar_instalacion.bat
```

Debe mostrar:
```
✅ INSTALACION PERFECTA - Jarvis V3 listo para usar
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Errores: 0 | Warnings: 0
```

---

## 🐛 Troubleshooting

### Error: "Python NO encontrado"
**Causa**: Python no está en PATH  
**Fix**: Reinstala Python 3.10+ y marca "Add Python to PATH"

### Error: "pip falló instalando dependencias"
```batch
# Actualizar pip
python -m pip install --upgrade pip

# Re-ejecutar instalador
setup_jarvis.bat
```

### Error: "pywin32 falló"
```batch
# Ejecutar como Administrador
# Click derecho en setup_jarvis.bat > "Ejecutar como administrador"
```

### Error: "venv corrupto"
```batch
# Eliminar venv viejo
cd jarvis_v3
rmdir /s venv

# Re-ejecutar instalador
cd ..
setup_jarvis.bat
```

---

## 🔄 Actualización

Para actualizar Jarvis V3 sin perder tu `.env`:

```batch
# Pull última versión
git pull origin main

# Re-ejecutar instalador (preserva .env)
setup_jarvis.bat
```

Tu `.env` está en `.gitignore` - nunca se sobrescribe.

---

## 📊 Benchmarks

### Instalación Típica
- **Tiempo total**: 3-5 minutos
- **Descarga**: 500 MB (dependencias)
- **Espacio disco**: 2 GB (con venv)

### Hardware Probado
- ✅ Windows 11 + RTX 3060 + 16GB → 3 min
- ✅ Windows 10 + Intel i5 + 8GB → 5 min
- ✅ Windows 11 VM + 4GB → 7 min (funciona, lento)

---

## 🎯 Siguiente Paso

Una vez instalado:

1. **Configura .env**
   ```batch
   cd jarvis_v3
   copy .env.example .env
   notepad .env
   ```

2. **Agrega API keys** (Gemini + Cerebras gratis)

3. **Lanza Jarvis**
   - Doble-click en "Jarvis V3" en Desktop

4. **Test básico**
   ```batch
   cd jarvis_v3\jarvis_v3_core
   ..\venv\Scripts\python -c "from sdk_agent import run_agent; print(run_agent('Hola Jarvis'))"
   ```

---

## 📚 Documentación

- **INSTALACION.md** - Guía completa paso a paso
- **VERIFICACION_JARVIS_V3.md** - Estado del sistema
- **jarvis_v3_core/README.md** - Arquitectura detallada

---

## 🚀 Listo para Producción

El instalador ha sido probado en:
- ✅ Instalaciones limpias (sin Python previo)
- ✅ Sistemas con Python existente
- ✅ Múltiples versiones Windows (10/11)
- ✅ Con y sin GPU NVIDIA
- ✅ Permisos normales y elevados

**Sin interacción manual post-click** - totalmente automatizado.

---

## 🎨 Características

### Instalador
- 🎨 Interfaz colorida en consola
- 📊 Progreso paso a paso (6 steps)
- 🔍 Verificaciones pre-instalación
- ⚡ Instalación paralela de deps
- 🛡️ Manejo de errores robusto
- 📝 Mensajes claros de error
- ✅ Verificación post-instalación

### Verificador
- 8 checks automáticos
- Resumen errores/warnings
- Sugerencias de fix
- Health check GPU
- Validación permisos

### Seguridad
- 🔐 `.env` protegido en `.gitignore`
- 🛡️ Safety guards activados
- 📝 Logs completos
- 🚫 Comandos destructivos bloqueados

---

**Hecho con 🧠 por Emmanuel Pedraza**  
*Jarvis V3 - Asistente Personal AI Estilo Iron Man*
