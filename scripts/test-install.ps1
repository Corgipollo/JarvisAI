# ===================================================================
# Jarvis AI — Test de Instalación Automatizado
# ===================================================================
# Valida que la instalación sea exitosa sin intervención manual
# Genera reporte con evidencia verificable
# ===================================================================

param(
    [string]$Component = "all",  # all | backend | frontend
    [switch]$GenerateReport,
    [switch]$Verbose
)

$ErrorActionPreference = "Continue"
if ($Verbose) { $VerbosePreference = "Continue" }

# ===================================================================
# CONFIGURACIÓN
# ===================================================================

$script:TestResults = @()
$script:StartTime = Get-Date
$script:ReportPath = ".\install-test-report-$(Get-Date -Format 'yyyy-MM-dd-HHmmss').md"

# ===================================================================
# FUNCIONES AUXILIARES
# ===================================================================

function Write-TestHeader {
    param([string]$Message)
    Write-Host "`n═══════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
}

function Write-TestStep {
    param([string]$Message)
    Write-Host "▶ $Message" -ForegroundColor Yellow
}

function Write-TestSuccess {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-TestFailure {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Add-TestResult {
    param(
        [string]$Category,
        [string]$Test,
        [bool]$Passed,
        [string]$Details = ""
    )

    $script:TestResults += [PSCustomObject]@{
        Category = $Category
        Test = $Test
        Passed = $Passed
        Details = $Details
        Timestamp = Get-Date -Format "HH:mm:ss"
    }
}

function Test-CommandExists {
    param([string]$Command)
    $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

function Test-PortListening {
    param([int]$Port, [int]$TimeoutSeconds = 5)

    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $result = $client.ConnectAsync("localhost", $Port).Wait($TimeoutSeconds * 1000)
        $client.Close()
        return $result
    } catch {
        return $false
    }
}

function Test-HttpEndpoint {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 10,
        [string]$ExpectedContent = ""
    )

    try {
        $response = Invoke-WebRequest -Uri $Url -TimeoutSec $TimeoutSeconds -UseBasicParsing
        $statusOk = $response.StatusCode -eq 200

        if ($ExpectedContent -and $statusOk) {
            return $response.Content -like "*$ExpectedContent*"
        }

        return $statusOk
    } catch {
        return $false
    }
}

# ===================================================================
# TESTS: REQUISITOS DEL SISTEMA
# ===================================================================

function Test-SystemRequirements {
    Write-TestHeader "TEST 1: Requisitos del Sistema"

    # Python 3.11.x
    Write-TestStep "Verificando Python 3.11.x..."
    $pythonExists = Test-CommandExists "python"
    if ($pythonExists) {
        $pythonVersion = (python --version 2>&1).ToString().Split(" ")[1]
        $versionObj = [version]$pythonVersion
        $python311 = ($versionObj -ge [version]"3.11.0" -and $versionObj -lt [version]"3.12.0")

        if ($python311) {
            Write-TestSuccess "Python $pythonVersion instalado ✓"
            Add-TestResult -Category "Sistema" -Test "Python 3.11.x" -Passed $true -Details $pythonVersion
        } else {
            Write-TestFailure "Python $pythonVersion incompatible (requiere 3.11.x)"
            Add-TestResult -Category "Sistema" -Test "Python 3.11.x" -Passed $false -Details $pythonVersion
        }
    } else {
        Write-TestFailure "Python no encontrado en PATH"
        Add-TestResult -Category "Sistema" -Test "Python 3.11.x" -Passed $false -Details "No instalado"
    }

    # Node.js 18+
    Write-TestStep "Verificando Node.js 18+..."
    $nodeExists = Test-CommandExists "node"
    if ($nodeExists) {
        $nodeVersion = (node --version 2>&1).ToString().TrimStart("v")
        $versionObj = [version]$nodeVersion
        $node18 = $versionObj -ge [version]"18.0.0"

        if ($node18) {
            Write-TestSuccess "Node.js $nodeVersion instalado ✓"
            Add-TestResult -Category "Sistema" -Test "Node.js 18+" -Passed $true -Details $nodeVersion
        } else {
            Write-TestFailure "Node.js $nodeVersion muy antiguo (requiere 18+)"
            Add-TestResult -Category "Sistema" -Test "Node.js 18+" -Passed $false -Details $nodeVersion
        }
    } else {
        Write-TestFailure "Node.js no encontrado en PATH"
        Add-TestResult -Category "Sistema" -Test "Node.js 18+" -Passed $false -Details "No instalado"
    }

    # Git
    Write-TestStep "Verificando Git..."
    $gitExists = Test-CommandExists "git"
    if ($gitExists) {
        $gitVersion = (git --version 2>&1).ToString().Split(" ")[2]
        Write-TestSuccess "Git $gitVersion instalado ✓"
        Add-TestResult -Category "Sistema" -Test "Git" -Passed $true -Details $gitVersion
    } else {
        Write-TestFailure "Git no encontrado en PATH"
        Add-TestResult -Category "Sistema" -Test "Git" -Passed $false -Details "No instalado"
    }

    # RAM
    Write-TestStep "Verificando RAM..."
    $ram = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB
    $ramOk = $ram -ge 8
    if ($ramOk) {
        Write-TestSuccess "$([math]::Round($ram, 2)) GB RAM disponible ✓"
        Add-TestResult -Category "Sistema" -Test "RAM 8GB+" -Passed $true -Details "$([math]::Round($ram, 2)) GB"
    } else {
        Write-TestFailure "$([math]::Round($ram, 2)) GB RAM (se recomiendan 8+ GB)"
        Add-TestResult -Category "Sistema" -Test "RAM 8GB+" -Passed $false -Details "$([math]::Round($ram, 2)) GB"
    }

    # Espacio en disco
    Write-TestStep "Verificando espacio en disco..."
    $drive = (Get-Location).Drive.Name
    $freeSpace = (Get-PSDrive $drive).Free / 1GB
    $diskOk = $freeSpace -ge 5
    if ($diskOk) {
        Write-TestSuccess "$([math]::Round($freeSpace, 2)) GB libres ✓"
        Add-TestResult -Category "Sistema" -Test "Disco 5GB+" -Passed $true -Details "$([math]::Round($freeSpace, 2)) GB"
    } else {
        Write-TestFailure "$([math]::Round($freeSpace, 2)) GB libres (se recomiendan 5+ GB)"
        Add-TestResult -Category "Sistema" -Test "Disco 5GB+" -Passed $false -Details "$([math]::Round($freeSpace, 2)) GB"
    }
}

# ===================================================================
# TESTS: ESTRUCTURA DEL PROYECTO
# ===================================================================

function Test-ProjectStructure {
    Write-TestHeader "TEST 2: Estructura del Proyecto"

    $requiredPaths = @(
        @{Path = "backend"; Type = "Directory"; Critical = $true},
        @{Path = "frontend"; Type = "Directory"; Critical = $true},
        @{Path = "backend/requirements.txt"; Type = "File"; Critical = $true},
        @{Path = "frontend/package.json"; Type = "File"; Critical = $true},
        @{Path = ".env.example"; Type = "File"; Critical = $false},
        @{Path = ".env"; Type = "File"; Critical = $true},
        @{Path = "data"; Type = "Directory"; Critical = $false},
        @{Path = "models"; Type = "Directory"; Critical = $false}
    )

    foreach ($item in $requiredPaths) {
        Write-TestStep "Verificando $($item.Path)..."

        $exists = if ($item.Type -eq "Directory") {
            Test-Path $item.Path -PathType Container
        } else {
            Test-Path $item.Path -PathType Leaf
        }

        if ($exists) {
            Write-TestSuccess "$($item.Path) existe ✓"
            Add-TestResult -Category "Estructura" -Test $item.Path -Passed $true
        } else {
            if ($item.Critical) {
                Write-TestFailure "$($item.Path) NO existe (CRÍTICO)"
                Add-TestResult -Category "Estructura" -Test $item.Path -Passed $false -Details "CRÍTICO"
            } else {
                Write-TestFailure "$($item.Path) NO existe (se creará en primer uso)"
                Add-TestResult -Category "Estructura" -Test $item.Path -Passed $false -Details "Opcional"
            }
        }
    }
}

# ===================================================================
# TESTS: DEPENDENCIAS BACKEND
# ===================================================================

function Test-BackendDependencies {
    Write-TestHeader "TEST 3: Dependencias Backend"

    # Verificar que requirements.txt tenga contenido
    Write-TestStep "Verificando requirements.txt..."
    if (Test-Path "backend/requirements.txt") {
        $requirements = Get-Content "backend/requirements.txt" | Where-Object { $_ -and $_ -notmatch "^#" }
        $reqCount = $requirements.Count

        if ($reqCount -gt 0) {
            Write-TestSuccess "requirements.txt contiene $reqCount paquetes ✓"
            Add-TestResult -Category "Backend" -Test "requirements.txt" -Passed $true -Details "$reqCount paquetes"

            # Verificar que los críticos estén presentes
            $criticalPackages = @("fastapi", "uvicorn", "faster-whisper", "edge-tts")
            foreach ($pkg in $criticalPackages) {
                $found = $requirements | Where-Object { $_ -like "$pkg*" }
                if ($found) {
                    Write-TestSuccess "  - $pkg presente ✓"
                    Add-TestResult -Category "Backend" -Test "Paquete $pkg" -Passed $true
                } else {
                    Write-TestFailure "  - $pkg FALTANTE"
                    Add-TestResult -Category "Backend" -Test "Paquete $pkg" -Passed $false
                }
            }
        } else {
            Write-TestFailure "requirements.txt vacío"
            Add-TestResult -Category "Backend" -Test "requirements.txt" -Passed $false
        }
    } else {
        Write-TestFailure "requirements.txt no existe"
        Add-TestResult -Category "Backend" -Test "requirements.txt" -Passed $false
    }

    # Verificar instalación de paquetes (solo si Python existe)
    if (Test-CommandExists "python") {
        Write-TestStep "Verificando paquetes instalados..."
        $installedPackages = pip list --format=freeze 2>&1

        $criticalInstalled = @("fastapi", "uvicorn", "faster-whisper")
        foreach ($pkg in $criticalInstalled) {
            $found = $installedPackages | Where-Object { $_ -like "$pkg*" }
            if ($found) {
                Write-TestSuccess "  - $pkg instalado ✓"
                Add-TestResult -Category "Backend" -Test "$pkg instalado" -Passed $true
            } else {
                Write-TestFailure "  - $pkg NO instalado"
                Add-TestResult -Category "Backend" -Test "$pkg instalado" -Passed $false
            }
        }
    }
}

# ===================================================================
# TESTS: DEPENDENCIAS FRONTEND
# ===================================================================

function Test-FrontendDependencies {
    Write-TestHeader "TEST 4: Dependencias Frontend"

    # Verificar package.json
    Write-TestStep "Verificando package.json..."
    if (Test-Path "frontend/package.json") {
        $packageJson = Get-Content "frontend/package.json" -Raw | ConvertFrom-Json

        if ($packageJson.dependencies -and $packageJson.dependencies.electron) {
            $electronVersion = $packageJson.dependencies.electron
            Write-TestSuccess "Electron $electronVersion en package.json ✓"
            Add-TestResult -Category "Frontend" -Test "package.json" -Passed $true -Details "Electron $electronVersion"
        } else {
            Write-TestFailure "Electron no encontrado en package.json"
            Add-TestResult -Category "Frontend" -Test "package.json" -Passed $false
        }
    } else {
        Write-TestFailure "package.json no existe"
        Add-TestResult -Category "Frontend" -Test "package.json" -Passed $false
    }

    # Verificar node_modules instalados
    Write-TestStep "Verificando node_modules..."
    if (Test-Path "frontend/node_modules") {
        $electronPath = "frontend/node_modules/electron"
        if (Test-Path $electronPath) {
            Write-TestSuccess "Electron instalado en node_modules ✓"
            Add-TestResult -Category "Frontend" -Test "Electron instalado" -Passed $true
        } else {
            Write-TestFailure "Electron NO instalado (ejecutar npm install)"
            Add-TestResult -Category "Frontend" -Test "Electron instalado" -Passed $false
        }
    } else {
        Write-TestFailure "node_modules no existe (ejecutar npm install)"
        Add-TestResult -Category "Frontend" -Test "node_modules" -Passed $false
    }
}

# ===================================================================
# TESTS: SERVICIOS RUNNING
# ===================================================================

function Test-RunningServices {
    Write-TestHeader "TEST 5: Servicios en Ejecución"

    # Backend en puerto 8000
    Write-TestStep "Verificando backend en puerto 8000..."
    $backendRunning = Test-PortListening -Port 8000 -TimeoutSeconds 3

    if ($backendRunning) {
        Write-TestSuccess "Backend escuchando en puerto 8000 ✓"
        Add-TestResult -Category "Servicios" -Test "Backend puerto 8000" -Passed $true

        # Test health endpoint
        Write-TestStep "Verificando endpoint /health..."
        $healthOk = Test-HttpEndpoint -Url "http://localhost:8000/health" -ExpectedContent "ok"

        if ($healthOk) {
            Write-TestSuccess "Backend health check OK ✓"
            Add-TestResult -Category "Servicios" -Test "Backend /health" -Passed $true
        } else {
            Write-TestFailure "Backend health check FALLÓ"
            Add-TestResult -Category "Servicios" -Test "Backend /health" -Passed $false
        }
    } else {
        Write-TestFailure "Backend NO está corriendo (iniciar con: cd backend && python main.py)"
        Add-TestResult -Category "Servicios" -Test "Backend puerto 8000" -Passed $false -Details "No iniciado"
    }

    # Ollama (opcional)
    Write-TestStep "Verificando Ollama (opcional)..."
    $ollamaRunning = Test-PortListening -Port 11434 -TimeoutSeconds 2

    if ($ollamaRunning) {
        Write-TestSuccess "Ollama corriendo en puerto 11434 ✓"
        Add-TestResult -Category "Servicios" -Test "Ollama" -Passed $true
    } else {
        Write-TestFailure "Ollama NO detectado (opcional, instalar: https://ollama.ai)"
        Add-TestResult -Category "Servicios" -Test "Ollama" -Passed $false -Details "Opcional"
    }
}

# ===================================================================
# TESTS: CONFIGURACIÓN (.env)
# ===================================================================

function Test-Configuration {
    Write-TestHeader "TEST 6: Configuración (.env)"

    Write-TestStep "Verificando archivo .env..."
    if (Test-Path ".env") {
        Write-TestSuccess ".env existe ✓"
        Add-TestResult -Category "Config" -Test ".env existe" -Passed $true

        # Leer .env y verificar keys críticas
        $envContent = Get-Content ".env" -Raw
        $requiredKeys = @(
            "CLAUDE_API_KEY",
            "GEMINI_API_KEY",
            "CEREBRAS_API_KEY",
            "OLLAMA_BASE_URL"
        )

        $atLeastOne = $false
        foreach ($key in $requiredKeys) {
            if ($envContent -match "$key=\w+") {
                Write-TestSuccess "  - $key configurada ✓"
                Add-TestResult -Category "Config" -Test $key -Passed $true
                $atLeastOne = $true
            } else {
                Write-TestFailure "  - $key NO configurada (o vacía)"
                Add-TestResult -Category "Config" -Test $key -Passed $false
            }
        }

        if (-not $atLeastOne) {
            Write-TestFailure "ADVERTENCIA: Ninguna API key configurada"
        }
    } else {
        Write-TestFailure ".env NO existe (copiar desde .env.example)"
        Add-TestResult -Category "Config" -Test ".env existe" -Passed $false
    }
}

# ===================================================================
# GENERACIÓN DE REPORTE
# ===================================================================

function Generate-Report {
    Write-TestHeader "Generando Reporte"

    $totalTests = $script:TestResults.Count
    $passedTests = ($script:TestResults | Where-Object { $_.Passed }).Count
    $failedTests = $totalTests - $passedTests
    $successRate = if ($totalTests -gt 0) { [math]::Round(($passedTests / $totalTests) * 100, 2) } else { 0 }

    $duration = (Get-Date) - $script:StartTime

    $reportContent = @"
# 🧪 Jarvis AI — Reporte de Test de Instalación

**Fecha**: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
**Duración**: $($duration.TotalSeconds) segundos
**Tests Totales**: $totalTests
**✓ Exitosos**: $passedTests
**✗ Fallidos**: $failedTests
**Tasa de Éxito**: $successRate%

---

## 📊 Resumen por Categoría

| Categoría | Exitosos | Fallidos | Total |
|-----------|----------|----------|-------|
"@

    # Agrupar por categoría
    $categories = $script:TestResults | Group-Object -Property Category
    foreach ($cat in $categories) {
        $catPassed = ($cat.Group | Where-Object { $_.Passed }).Count
        $catFailed = $cat.Count - $catPassed
        $reportContent += "| $($cat.Name) | $catPassed | $catFailed | $($cat.Count) |`n"
    }

    $reportContent += @"

---

## 📝 Detalle de Tests

"@

    # Detalle por test
    foreach ($result in $script:TestResults) {
        $icon = if ($result.Passed) { "✓" } else { "✗" }
        $status = if ($result.Passed) { "PASS" } else { "FAIL" }
        $details = if ($result.Details) { " — $($result.Details)" } else { "" }

        $reportContent += "- [$icon] **$($result.Category)** / $($result.Test): **$status**$details`n"
    }

    $reportContent += @"

---

## 🔍 Diagnóstico

"@

    if ($successRate -eq 100) {
        $reportContent += @"
✅ **Instalación PERFECTA** — Todos los tests pasaron.

Jarvis está listo para usar. Ejecutar:

``````powershell
# Iniciar backend
cd backend
python main.py

# Iniciar frontend (otra terminal)
cd frontend
npm run dev
``````

"@
    } elseif ($successRate -ge 80) {
        $reportContent += @"
⚠️ **Instalación FUNCIONAL** — $failedTests test(s) fallido(s).

La mayoría de componentes están listos. Revisar los tests fallidos arriba.

Tests críticos a revisar:
- Backend puerto 8000
- .env configurado
- Python 3.11.x + Node.js 18+

"@
    } else {
        $reportContent += @"
❌ **Instalación INCOMPLETA** — $failedTests test(s) fallido(s).

Acción requerida:

1. Verificar requisitos del sistema (Python 3.11.x, Node.js 18+)
2. Ejecutar installer: ``.\install-v2-zero-friction.ps1 -Unattended``
3. Configurar .env con API keys
4. Re-ejecutar este test: ``.\scripts\test-install.ps1 -GenerateReport``

"@
    }

    $reportContent += @"

---

**Generado por**: test-install.ps1
**Versión**: 1.0
**Más info**: README-INSTALL.md
"@

    # Guardar reporte
    Set-Content -Path $script:ReportPath -Value $reportContent -Encoding UTF8
    Write-TestSuccess "Reporte guardado en: $script:ReportPath"

    # Mostrar resumen en consola
    Write-Host "`n" -NoNewline
    Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  RESUMEN FINAL" -ForegroundColor Cyan
    Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "Total: $totalTests | Exitosos: $passedTests | Fallidos: $failedTests" -ForegroundColor White
    Write-Host "Tasa de Éxito: $successRate%" -ForegroundColor $(if ($successRate -eq 100) { "Green" } elseif ($successRate -ge 80) { "Yellow" } else { "Red" })
    Write-Host ""
}

# ===================================================================
# MAIN
# ===================================================================

Write-Host @"

     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝

        🧪 TEST DE INSTALACIÓN AUTOMATIZADO 🧪

"@ -ForegroundColor Magenta

Write-Host "Componente: $Component" -ForegroundColor Cyan
Write-Host ""

# Ejecutar tests según componente
switch ($Component.ToLower()) {
    "backend" {
        Test-SystemRequirements
        Test-ProjectStructure
        Test-BackendDependencies
        Test-Configuration
        Test-RunningServices
    }
    "frontend" {
        Test-SystemRequirements
        Test-ProjectStructure
        Test-FrontendDependencies
    }
    "all" {
        Test-SystemRequirements
        Test-ProjectStructure
        Test-BackendDependencies
        Test-FrontendDependencies
        Test-RunningServices
        Test-Configuration
    }
    default {
        Write-Host "Componente inválido: $Component (usar: all, backend, frontend)" -ForegroundColor Red
        exit 1
    }
}

# Generar reporte si se solicitó
if ($GenerateReport) {
    Generate-Report
}

Write-Host "`n✅ Tests completados" -ForegroundColor Green
Write-Host ""
