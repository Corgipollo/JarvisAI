# JARVIS_MAX_POWER.ps1 — Da al Claude de la VM PODER TOTAL
#
# Hace:
#   1. Pone Claude Code en bypassPermissions PERMANENTE (~/.claude/settings.json)
#   2. Clona CerebroEmmanuel a C:\Jarvis\cerebro\ (privado, requiere token)
#   3. Copia/sincroniza skills/agents/CLAUDE.md global a C:\Jarvis\.claude\
#   4. Inyecta un CLAUDE.md maestro en C:\Jarvis\ apuntando a TODO
#   5. Re-arranca Claude con --continue para que conserve la sesion
#
# Uso (dentro de la VM, PowerShell admin):
#   cd C:\Jarvis
#   git pull
#   .\JARVIS_MAX_POWER.ps1

$ErrorActionPreference = "Stop"

function Banner($msg) {
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Yellow
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host ""
}

Banner "[1/5] BYPASS PERMISSIONS PERMANENTE"

$claudeDir = "$env:USERPROFILE\.claude"
$settingsFile = "$claudeDir\settings.json"
if (-not (Test-Path $claudeDir)) { New-Item -ItemType Directory -Path $claudeDir -Force | Out-Null }

# Leer settings existente si hay, o crear nuevo
if (Test-Path $settingsFile) {
    try { $settings = Get-Content $settingsFile -Raw | ConvertFrom-Json -AsHashtable } catch { $settings = @{} }
} else {
    $settings = @{}
}

# Forzar bypass mode
if (-not $settings.ContainsKey("permissions")) { $settings["permissions"] = @{} }
$settings["permissions"]["defaultMode"] = "bypassPermissions"
$settings["permissions"]["allowAll"] = $true

# Tools permitidos sin pedir
$settings["permissions"]["tools"] = @{
    "Bash"   = "allow"
    "Edit"   = "allow"
    "Write"  = "allow"
    "Read"   = "allow"
    "Glob"   = "allow"
    "Grep"   = "allow"
    "WebFetch" = "allow"
    "WebSearch" = "allow"
}

$settings | ConvertTo-Json -Depth 10 | Set-Content $settingsFile -Encoding UTF8
Write-Host "  OK Claude settings: bypassPermissions activo en $settingsFile"

Banner "[2/5] CLONAR CEREBRO COMPLETO"

$cerebroDir = "C:\Jarvis\cerebro"
if (Test-Path "$cerebroDir\.git") {
    Write-Host "  Actualizando cerebro existente..."
    Set-Location $cerebroDir
    git pull 2>&1 | Out-Host
} else {
    Write-Host "  Clonando CerebroEmmanuel (publico vault)..."
    # Si es publico:
    git clone https://github.com/Corgipollo/CerebroEmmanuel.git $cerebroDir 2>&1 | Out-Host
    # Si falla por privado, el user tendra que dar token
    if (-not (Test-Path "$cerebroDir\.git")) {
        Write-Host "  AVISO: Si el repo es privado, ejecuta:" -ForegroundColor Yellow
        Write-Host "    git clone https://<TOKEN>@github.com/Corgipollo/CerebroEmmanuel.git $cerebroDir" -ForegroundColor Yellow
    }
}

Banner "[3/5] CLONAR SKILLS/AGENTES GLOBALES"

$claudeJarvis = "C:\Jarvis\.claude_global"
if (-not (Test-Path $claudeJarvis)) { New-Item -ItemType Directory -Path $claudeJarvis -Force | Out-Null }

# Las skills/agents globales viven en el repo JarvisAI bajo claude_global/ (si las copiamos alli)
# O en ~/.claude/skills/ del host (no accesible desde VM sin shared folder)
# Por ahora dejamos placeholder y agregamos un README para que Emmanuel sepa
Set-Content "$claudeJarvis\README.md" -Encoding UTF8 -Value @"
# Claude Global Resources (mirror)

Este directorio mirror las skills y agentes globales del Claude host.
Para sincronizarlo, ejecuta desde el host:

    git -C C:\Users\Emmanuel\Documents\JarvisAI subtree add --prefix=claude_global --squash <host-claude-repo> main

O via shared folder de VirtualBox (requiere Guest Additions instaladas).
"@

Banner "[4/5] INYECTAR CLAUDE.md MAESTRO EN C:\Jarvis"

$masterClaudeMd = @"
# Claude Master Instructions — Jarvis VM

> Este archivo se carga automaticamente cuando Claude Code corre en C:\Jarvis\

## Identidad

Eres **Jarvis**, el asistente personal autonomo de Emmanuel Pedraza. Corres dentro de una Windows VM aislada. Tu mundo es C:\Jarvis\ y las apps instaladas en esta VM.

## Acceso al cerebro de Emmanuel

- **Vault Obsidian completo**: ``C:\Jarvis\cerebro\`` (clonado de https://github.com/Corgipollo/CerebroEmmanuel)
  - 22 proyectos activos
  - 2100+ notas tecnicas, procesos, decisiones
  - MOCs principales en cada carpeta de proyecto
  - Lee CLAUDE.md del cerebro para contexto especifico

- **Repo Jarvis**: ``C:\Jarvis\`` (este mismo)
  - backend/skills/ — tus skills nativas
  - jarvis_bridge/ — proxy, telegram, semantic memory
  - jarvis_learners/ — self_improvement, coach, content_pipeline
  - data/ — skills aprendidas, gaps, learnings, errores

## Reglas

1. **Bypass permissions activo** — no preguntes, ejecuta. Si rompes algo es recuperable (es VM).
2. **Consulta el cerebro PRIMERO** — antes de inventar, busca en ``C:\Jarvis\cerebro\`` con Glob/Grep.
3. **Estilo Emmanuel**: directo, en espanol, sin preamble, resultados primero.
4. **Idempotencia**: chequea si algo ya existe antes de crearlo.
5. **Reporta a data/jarvis_learnings.jsonl** cada tarea ejecutada.

## Servicios corriendo

- :8088 — claude_proxy (tu propia API)
- :7777 — dashboard
- self_improvement loop, coach, self_optimizer, proactive_suggester

## Primera tarea recomendada

Lee ``C:\Jarvis\JARVIS_VM_BOOTSTRAP.md`` y ejecuta las 5 tareas que estan ahi.
"@

Set-Content "C:\Jarvis\CLAUDE.md" -Encoding UTF8 -Value $masterClaudeMd
Write-Host "  OK CLAUDE.md maestro en C:\Jarvis\CLAUDE.md"

Banner "[5/5] LISTO — REINICIA CLAUDE"

Write-Host "Para activar el modo bypass + acceso al cerebro:" -ForegroundColor Green
Write-Host ""
Write-Host "  1. Cierra Claude actual (escribe /exit o Ctrl+C dos veces)"
Write-Host "  2. cd C:\Jarvis"
Write-Host "  3. claude --dangerously-skip-permissions --continue"
Write-Host ""
Write-Host "El nuevo Claude ya:"
Write-Host "  - NO te pedira permisos (bypass activo)"
Write-Host "  - Lee CLAUDE.md maestro automatico al arrancar"
Write-Host "  - Tiene acceso a C:\Jarvis\cerebro\ (vault completo)"
Write-Host "  - Sabe que es Jarvis y como trabaja Emmanuel"
Write-Host ""
