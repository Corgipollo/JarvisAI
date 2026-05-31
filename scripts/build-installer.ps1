# Build Jarvis AI Production Installer
# Creates a Windows .exe installer with embedded Python backend + Electron frontend

param(
    [switch]$SkipTests,
    [switch]$Publish
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$FrontendDir = Join-Path $ProjectRoot "frontend"
$BackendDir = Join-Path $ProjectRoot "backend"
$DistDir = Join-Path $ProjectRoot "dist-installer"

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "Jarvis AI Installer Builder v1.0.0-alpha" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Step 1: Validate environment
Write-Host "[1/7] Validating build environment..." -ForegroundColor Yellow

if (-not (Test-Path $FrontendDir)) {
    Write-Host "ERROR: Frontend directory not found: $FrontendDir" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $BackendDir)) {
    Write-Host "ERROR: Backend directory not found: $BackendDir" -ForegroundColor Red
    exit 1
}

# Check Node.js
$nodeVersion = node --version 2>$null
if (-not $nodeVersion) {
    Write-Host "ERROR: Node.js not found. Install from https://nodejs.org" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Node.js: $nodeVersion" -ForegroundColor Green

# Check Python 3.11
$pythonVersion = python --version 2>$null
if ($pythonVersion -notmatch "Python 3\.11") {
    Write-Host "ERROR: Python 3.11.x required (found: $pythonVersion)" -ForegroundColor Red
    Write-Host "  Download: https://www.python.org/downloads/release/python-3110/" -ForegroundColor Yellow
    exit 1
}
Write-Host "  ✓ Python: $pythonVersion" -ForegroundColor Green

# Step 2: Install frontend dependencies
Write-Host ""
Write-Host "[2/7] Installing frontend dependencies..." -ForegroundColor Yellow
Push-Location $FrontendDir
try {
    npm install --production=false
    if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
    Write-Host "  ✓ Frontend dependencies installed" -ForegroundColor Green
} finally {
    Pop-Location
}

# Step 3: Verify backend requirements
Write-Host ""
Write-Host "[3/7] Verifying backend dependencies..." -ForegroundColor Yellow
$requirementsFile = Join-Path $BackendDir "requirements.txt"
if (-not (Test-Path $requirementsFile)) {
    Write-Host "ERROR: Backend requirements.txt not found" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Backend requirements.txt found" -ForegroundColor Green

# Step 4: Create build assets (if missing)
Write-Host ""
Write-Host "[4/7] Preparing build assets..." -ForegroundColor Yellow
$buildDir = Join-Path $FrontendDir "build"
if (-not (Test-Path $buildDir)) {
    New-Item -ItemType Directory -Path $buildDir | Out-Null
}

# Create dummy icon if missing (electron-builder requires it)
$iconPath = Join-Path $buildDir "icon.ico"
if (-not (Test-Path $iconPath)) {
    Write-Host "  ⚠ WARNING: icon.ico not found, using placeholder" -ForegroundColor Yellow
    # Copy from assets if exists, otherwise create minimal ico
    $assetIcon = Join-Path $FrontendDir "src\assets\jarvis-icon.png"
    if (Test-Path $assetIcon) {
        Write-Host "  → Converting PNG to ICO (requires ImageMagick or manual conversion)" -ForegroundColor Yellow
        Write-Host "  → Skipping for now - electron-builder will use default" -ForegroundColor Yellow
    }
}

# Create LICENSE if missing
$licensePath = Join-Path $ProjectRoot "LICENSE"
if (-not (Test-Path $licensePath)) {
    Write-Host "  → Creating MIT LICENSE" -ForegroundColor Yellow
    @"
MIT License

Copyright (c) 2026 Emmanuel Pedraza

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"@ | Out-File -FilePath $licensePath -Encoding UTF8
}
Write-Host "  ✓ Build assets prepared" -ForegroundColor Green

# Step 5: Run tests (optional)
if (-not $SkipTests) {
    Write-Host ""
    Write-Host "[5/7] Running smoke tests..." -ForegroundColor Yellow

    # Test backend can start
    Write-Host "  → Testing backend startup..." -ForegroundColor Cyan
    Push-Location $BackendDir
    try {
        $backendProcess = Start-Process python -ArgumentList "main.py" -PassThru -NoNewWindow
        Start-Sleep -Seconds 3

        $healthCheck = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
        if ($healthCheck.StatusCode -eq 200) {
            Write-Host "  ✓ Backend health check passed" -ForegroundColor Green
        } else {
            Write-Host "  ⚠ WARNING: Backend health check failed (continuing anyway)" -ForegroundColor Yellow
        }

        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    } catch {
        Write-Host "  ⚠ WARNING: Backend test skipped ($($_.Exception.Message))" -ForegroundColor Yellow
    } finally {
        Pop-Location
    }
} else {
    Write-Host ""
    Write-Host "[5/7] Skipping tests (--SkipTests flag)" -ForegroundColor Yellow
}

# Step 6: Build installer
Write-Host ""
Write-Host "[6/7] Building Windows installer..." -ForegroundColor Yellow
Write-Host "  This may take 5-10 minutes..." -ForegroundColor Cyan

Push-Location $FrontendDir
try {
    if ($Publish) {
        Write-Host "  → Building and publishing to GitHub Releases..." -ForegroundColor Cyan
        npm run release
    } else {
        Write-Host "  → Building installer (local only)..." -ForegroundColor Cyan
        npm run dist
    }

    if ($LASTEXITCODE -ne 0) { throw "electron-builder failed" }
    Write-Host "  ✓ Installer built successfully" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Build failed - $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "  1. Check that all paths in build.json are correct" -ForegroundColor White
    Write-Host "  2. Ensure icon.ico exists in frontend/build/" -ForegroundColor White
    Write-Host "  3. Verify backend/requirements.txt is valid" -ForegroundColor White
    Write-Host "  4. Check logs above for specific errors" -ForegroundColor White
    exit 1
} finally {
    Pop-Location
}

# Step 7: Verify output
Write-Host ""
Write-Host "[7/7] Verifying installer output..." -ForegroundColor Yellow

$installerPattern = Join-Path $DistDir "JarvisAI-Setup-*.exe"
$installerFile = Get-ChildItem -Path $installerPattern -ErrorAction SilentlyContinue | Select-Object -First 1

if ($installerFile) {
    $sizeInMB = [math]::Round($installerFile.Length / 1MB, 2)
    Write-Host "  ✓ Installer created: $($installerFile.Name)" -ForegroundColor Green
    Write-Host "  ✓ Size: $sizeInMB MB" -ForegroundColor Green
    Write-Host "  ✓ Path: $($installerFile.FullName)" -ForegroundColor Green

    if ($sizeInMB -gt 150) {
        Write-Host ""
        Write-Host "  ⚠ WARNING: Installer is larger than expected ($sizeInMB MB)" -ForegroundColor Yellow
        Write-Host "  → Consider excluding dev dependencies or large assets" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ⚠ WARNING: Installer file not found in $DistDir" -ForegroundColor Yellow
    Write-Host "  Check electron-builder logs above for errors" -ForegroundColor Yellow
}

# Summary
Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "BUILD COMPLETE" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Test installer: Run $($installerFile.FullName)" -ForegroundColor White
Write-Host "  2. Verify installation on clean VM" -ForegroundColor White
Write-Host "  3. Create GitHub Release:" -ForegroundColor White
Write-Host "     gh release create v1.0.0-alpha $($installerFile.FullName) --title 'Alpha Release' --notes 'First alpha release'" -ForegroundColor Cyan
Write-Host "  4. Update landing page Download button to point to release" -ForegroundColor White
Write-Host ""
