# ═══════════════════════════════════════════════════
#   JARVIS AI — Setup Automatico
# ═══════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host ""
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  JARVIS AI — Instalacion Automatica" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ─── 1. Verificar Python ───
Write-Host "[1/5] Verificando Python..." -ForegroundColor Yellow
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    $pyVersion = python --version 2>&1
    Write-Host "  OK: $pyVersion" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Python no encontrado. Instala Python 3.10+" -ForegroundColor Red
    exit 1
}

# ─── 2. Verificar Node.js ───
Write-Host "[2/5] Verificando Node.js..." -ForegroundColor Yellow
$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) {
    $nodeVersion = node --version 2>&1
    Write-Host "  OK: Node.js $nodeVersion" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Node.js no encontrado. Instala Node.js 18+" -ForegroundColor Red
    exit 1
}

# ─── 3. Instalar dependencias Python ───
Write-Host "[3/5] Instalando dependencias Python..." -ForegroundColor Yellow
Push-Location "$root\backend"
pip install -r requirements.txt --quiet 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK: Dependencias Python instaladas" -ForegroundColor Green
} else {
    Write-Host "  WARN: Algunos paquetes fallaron, reintentando..." -ForegroundColor Yellow
    pip install -r requirements.txt
}
Pop-Location

# ─── 4. Instalar dependencias Electron ───
Write-Host "[4/5] Instalando Electron..." -ForegroundColor Yellow
Push-Location "$root\frontend"
npm install --silent 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK: Electron instalado" -ForegroundColor Green
} else {
    Write-Host "  WARN: Reintentando npm install..." -ForegroundColor Yellow
    npm install
}
Pop-Location

# ─── 5. Verificar/Instalar Ollama ───
Write-Host "[5/5] Verificando Ollama..." -ForegroundColor Yellow
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollama) {
    Write-Host "  OK: Ollama encontrado" -ForegroundColor Green

    # Verificar modelos
    Write-Host "  Descargando modelos necesarios..." -ForegroundColor Yellow
    $models = ollama list 2>&1

    if ($models -notmatch "llama3.2") {
        Write-Host "  Descargando llama3.2 (esto tarda unos minutos)..." -ForegroundColor Yellow
        ollama pull llama3.2
    } else {
        Write-Host "  OK: llama3.2 ya instalado" -ForegroundColor Green
    }
} else {
    Write-Host "  Ollama no encontrado. Instalando..." -ForegroundColor Yellow
    Write-Host "  Descargando Ollama..." -ForegroundColor Yellow

    $ollamaInstaller = "$env:TEMP\OllamaSetup.exe"
    Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $ollamaInstaller

    Write-Host "  Ejecutando instalador de Ollama..." -ForegroundColor Yellow
    Start-Process -FilePath $ollamaInstaller -Wait

    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

    Write-Host "  Descargando modelo llama3.2..." -ForegroundColor Yellow
    ollama pull llama3.2
}

# ─── Crear .env si no existe ───
$envFile = "$root\.env"
if (-not (Test-Path $envFile)) {
    @"
# Jarvis AI - Configuracion
# Rellena las API keys que quieras usar (todas son opcionales)

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

# Clima (wttr.in es gratis, no necesita key)
WEATHER_CITY=Monterrey
WEATHER_COUNTRY=MX

# Shopify (opcional - para consultar la tienda)
SHOPIFY_STORE=grop-7604.myshopify.com
SHOPIFY_ACCESS_TOKEN=

# Obsidian vault path
OBSIDIAN_VAULT=C:\Users\Emmanuel\Documents\CerebroEmmanuel
"@ | Out-File -FilePath $envFile -Encoding utf8
    Write-Host ""
    Write-Host "  Archivo .env creado en $envFile" -ForegroundColor Green
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  JARVIS AI — Instalacion Completa!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "  Para iniciar Jarvis:" -ForegroundColor White
Write-Host "    .\scripts\start.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "  O manualmente:" -ForegroundColor White
Write-Host "    1. ollama serve" -ForegroundColor Cyan
Write-Host "    2. cd backend && python main.py" -ForegroundColor Cyan
Write-Host "    3. cd frontend && npm start" -ForegroundColor Cyan
Write-Host ""
