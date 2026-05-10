# Jarvis Sandbox VM — PC dentro de tu PC

Windows Sandbox aislado donde Jarvis se entrena 24/7 sin tocar tu sistema real.

## Qué es

Una **VM ligera de Windows** (feature nativa de Windows 10/11 Pro) que:
- Arranca en ~10 segundos
- Usa ~6 GB RAM
- **Se borra completamente al cerrarse** → cada sesión empieza limpia
- Aislada de tu sistema (no puede tocar tus archivos ni apps reales)
- Tiene su propio Windows fresco con red

## Setup (una sola vez, requiere admin + reboot)

```powershell
# 1. Click derecho en enable_feature.ps1 → "Run with PowerShell" como admin
# 2. Acepta todo
# 3. Reiniciar PC
```

Después del reboot, ya está listo para siempre.

## Uso diario

```cmd
cd C:\Users\Emmanuel\Documents\JarvisAI\sandbox_vm
.\launch_sandbox.bat
```

Aparece una **ventana de Windows nuevo** (PC dentro de la PC). Adentro:
- `JarvisAI/` montado en Desktop (read-only desde tu host)
- Auto-bootstrap: descarga Python 3.12 embeddable, instala deps
- **Trainer corriendo en loop infinito cada 5 min**
- Logs:
  - `C:\jarvis_sandbox.log` — boot + setup
  - `C:\jarvis_iterations.log` — cada iteración del trainer

Cuando cierres la ventana de la sandbox, **se borra todo** (estado clean next time).

## Estructura

```
sandbox_vm/
├── jarvis_sandbox.wsb       # Config XML de la sandbox
├── setup_inside_sandbox.ps1 # Bootstrap + loop trainer (corre DENTRO)
├── launch_sandbox.bat       # Atajo para lanzar la sandbox
├── enable_feature.ps1       # One-time: habilitar feature (admin)
└── README.md
```

## Comportamiento del trainer dentro

- `JARVIS_SANDBOX=0` (modo REAL) — las acciones SÍ se ejecutan, abren apps,
  cierran apps, etc. **Pero todo eso pasa DENTRO de la VM aislada**, no en
  tu PC real.
- Cada 5 min ejecuta los 11 tasks del curriculum
- Acumula learnings + errors en `C:\JarvisAI\data\jarvis_*.jsonl`
- ⚠️ Logs se BORRAN al cerrar la sandbox. Si quieres conservarlos, copialos
  via clipboard antes de cerrar (ClipboardRedirection está habilitado).

## Para que los logs persistan entre runs

Cambiar `<ReadOnly>true</ReadOnly>` a `false` en `jarvis_sandbox.wsb` para
que la sandbox pueda escribir de vuelta a tu host. ⚠️ Eso rompe el aislamiento
parcial (la sandbox podría modificar tu JarvisAI). Trade-off.

## Troubleshooting

### `WindowsSandbox.exe` no encontrado
Feature no activada. Correr `enable_feature.ps1` como admin + reboot.

### Virtualización deshabilitada
Entrar al BIOS/UEFI y activar VT-x (Intel) / AMD-V. La feature requiere virtualización.

### Sandbox arranca pero no corre el trainer
Abrir `C:\jarvis_sandbox.log` dentro de la sandbox. Probable: descarga de Python falló (sin red?).

### Cerrar sin perder logs
Antes de cerrar: copiar contenido de `C:\jarvis_iterations.log` al clipboard
y pegarlo en tu host (ClipboardRedirection habilitado).

## Status

2026-05-09 — V1: config + bootstrap + loop. Pendiente activar feature en host
(`enable_feature.ps1`).
