# Test Jarvis AI Installer
# Smoke test for production installer before publishing to GitHub Releases

param(
    [Parameter(Mandatory=$true)]
    [string]$InstallerPath,

    [switch]$GenerateReport
)

$ErrorActionPreference = "Continue" # Continue on errors to complete full test
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "Jarvis AI Installer Smoke Test" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Verify installer exists
if (-not (Test-Path $InstallerPath)) {
    Write-Host "ERROR: Installer not found: $InstallerPath" -ForegroundColor Red
    exit 1
}

$installerName = Split-Path $InstallerPath -Leaf
$installerSize = [math]::Round((Get-Item $InstallerPath).Length / 1MB, 2)

Write-Host "Testing installer: $installerName ($installerSize MB)" -ForegroundColor Yellow
Write-Host ""

# Test Results
$results = @{
    "Installer file exists" = $true
    "File size reasonable (<150MB)" = ($installerSize -lt 150)
    "File is executable" = ($installerName -like "*.exe")
}

# Static analysis
Write-Host "[1/6] Static Analysis..." -ForegroundColor Yellow

# Check digital signature (will fail for unsigned, but that's OK for alpha)
try {
    $signature = Get-AuthenticodeSignature -FilePath $InstallerPath
    $results["Digital signature"] = ($signature.Status -eq "Valid")
    if ($signature.Status -ne "Valid") {
        Write-Host "  ⚠ WARNING: Installer not digitally signed (expected for alpha)" -ForegroundColor Yellow
        Write-Host "    For production, get code signing certificate" -ForegroundColor Gray
    } else {
        Write-Host "  ✓ Installer is digitally signed" -ForegroundColor Green
    }
} catch {
    $results["Digital signature"] = $false
    Write-Host "  ⚠ WARNING: Could not verify signature" -ForegroundColor Yellow
}

# Check if NSIS installer (Windows only)
try {
    $fileHeader = [System.IO.File]::ReadAllBytes($InstallerPath)[0..100]
    $headerString = [System.Text.Encoding]::ASCII.GetString($fileHeader)
    $isNSIS = $headerString -match "Nullsoft"
    $results["NSIS installer format"] = $isNSIS
    if ($isNSIS) {
        Write-Host "  ✓ NSIS installer detected" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ WARNING: Not an NSIS installer (may be different format)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ⚠ WARNING: Could not detect installer format" -ForegroundColor Yellow
}

Write-Host ""

# Prerequisites check
Write-Host "[2/6] Prerequisites Check..." -ForegroundColor Yellow

# Check Python 3.11
$pythonVersion = python --version 2>$null
if ($pythonVersion -match "Python 3\.11") {
    Write-Host "  ✓ Python 3.11.x installed: $pythonVersion" -ForegroundColor Green
    $results["Python 3.11 installed"] = $true
} else {
    Write-Host "  ⚠ WARNING: Python 3.11 not found (installer should prompt user)" -ForegroundColor Yellow
    Write-Host "    Current: $pythonVersion" -ForegroundColor Gray
    $results["Python 3.11 installed"] = $false
}

# Check available disk space
$drive = (Get-Item $env:SystemDrive)
$freeSpaceGB = [math]::Round((Get-PSDrive $drive.Name).Free / 1GB, 2)
$results["Sufficient disk space (>2GB)"] = ($freeSpaceGB -gt 2)
if ($freeSpaceGB -gt 2) {
    Write-Host "  ✓ Disk space available: $freeSpaceGB GB" -ForegroundColor Green
} else {
    Write-Host "  ⚠ WARNING: Low disk space: $freeSpaceGB GB (need 2GB+)" -ForegroundColor Yellow
}

# Check ports 8000/3000 available
$port8000InUse = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
$port3000InUse = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
$results["Port 8000 available"] = ($null -eq $port8000InUse)
$results["Port 3000 available"] = ($null -eq $port3000InUse)

if ($null -eq $port8000InUse) {
    Write-Host "  ✓ Port 8000 available" -ForegroundColor Green
} else {
    Write-Host "  ⚠ WARNING: Port 8000 in use (may conflict with Jarvis backend)" -ForegroundColor Yellow
}

if ($null -eq $port3000InUse) {
    Write-Host "  ✓ Port 3000 available" -ForegroundColor Green
} else {
    Write-Host "  ⚠ WARNING: Port 3000 in use (may conflict with Jarvis frontend)" -ForegroundColor Yellow
}

Write-Host ""

# Installation simulation (dry run)
Write-Host "[3/6] Installation Simulation..." -ForegroundColor Yellow
Write-Host "  ℹ️ Skipping actual installation (manual test required)" -ForegroundColor Cyan
Write-Host "  → To test manually:" -ForegroundColor Gray
Write-Host "    1. Run: $InstallerPath" -ForegroundColor Gray
Write-Host "    2. Follow installation wizard" -ForegroundColor Gray
Write-Host "    3. Verify Jarvis launches" -ForegroundColor Gray
Write-Host "    4. Test voice interaction" -ForegroundColor Gray
Write-Host "    5. Uninstall via Settings" -ForegroundColor Gray
Write-Host ""

# Backend health (if backend is running)
Write-Host "[4/6] Backend Health Check..." -ForegroundColor Yellow
try {
    $health = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
    if ($health.StatusCode -eq 200) {
        Write-Host "  ✓ Backend is running and healthy" -ForegroundColor Green
        $results["Backend health check"] = $true
    }
} catch {
    Write-Host "  ℹ️ Backend not running (expected if not installed yet)" -ForegroundColor Cyan
    $results["Backend health check"] = "N/A (not running)"
}

Write-Host ""

# Documentation check
Write-Host "[5/6] Documentation Check..." -ForegroundColor Yellow

$requiredDocs = @(
    "README.md",
    "README-INSTALL.md",
    "TROUBLESHOOTING.md",
    ".env.example",
    "LICENSE"
)

foreach ($doc in $requiredDocs) {
    $docPath = Join-Path $ProjectRoot $doc
    if (Test-Path $docPath) {
        Write-Host "  ✓ $doc exists" -ForegroundColor Green
        $results["Doc: $doc"] = $true
    } else {
        Write-Host "  ⚠ WARNING: $doc missing" -ForegroundColor Yellow
        $results["Doc: $doc"] = $false
    }
}

Write-Host ""

# Release readiness
Write-Host "[6/6] Release Readiness..." -ForegroundColor Yellow

# Check git status
Push-Location $ProjectRoot
try {
    $gitStatus = git status --porcelain 2>$null
    if ([string]::IsNullOrWhiteSpace($gitStatus)) {
        Write-Host "  ✓ Git working tree clean" -ForegroundColor Green
        $results["Git clean"] = $true
    } else {
        Write-Host "  ⚠ WARNING: Uncommitted changes detected" -ForegroundColor Yellow
        Write-Host "    Run 'git status' to see changes" -ForegroundColor Gray
        $results["Git clean"] = $false
    }

    # Check current branch
    $currentBranch = git rev-parse --abbrev-ref HEAD 2>$null
    if ($currentBranch -eq "master") {
        Write-Host "  ✓ On master branch" -ForegroundColor Green
        $results["On master branch"] = $true
    } else {
        Write-Host "  ⚠ WARNING: Not on master branch (current: $currentBranch)" -ForegroundColor Yellow
        $results["On master branch"] = $false
    }

    # Check if gh CLI is authenticated
    $ghAuth = gh auth status 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ GitHub CLI authenticated" -ForegroundColor Green
        $results["GitHub CLI authenticated"] = $true
    } else {
        Write-Host "  ⚠ WARNING: GitHub CLI not authenticated" -ForegroundColor Yellow
        Write-Host "    Run: gh auth login" -ForegroundColor Gray
        $results["GitHub CLI authenticated"] = $false
    }
} catch {
    Write-Host "  ⚠ WARNING: Could not check git status" -ForegroundColor Yellow
} finally {
    Pop-Location
}

Write-Host ""

# Summary
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "SMOKE TEST RESULTS" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

$passCount = 0
$failCount = 0
$warnCount = 0

foreach ($test in $results.GetEnumerator()) {
    $status = $test.Value
    $testName = $test.Key

    if ($status -eq $true) {
        Write-Host "✓ $testName" -ForegroundColor Green
        $passCount++
    } elseif ($status -eq $false) {
        Write-Host "✗ $testName" -ForegroundColor Red
        $failCount++
    } else {
        Write-Host "⚠ $testName : $status" -ForegroundColor Yellow
        $warnCount++
    }
}

Write-Host ""
Write-Host "SUMMARY:" -ForegroundColor Yellow
Write-Host "  Passed: $passCount" -ForegroundColor Green
Write-Host "  Failed: $failCount" -ForegroundColor Red
Write-Host "  Warnings: $warnCount" -ForegroundColor Yellow
Write-Host ""

# Verdict
if ($failCount -eq 0) {
    Write-Host "VERDICT: ✅ READY FOR RELEASE" -ForegroundColor Green
    $verdict = "PASS"
} elseif ($failCount -le 2) {
    Write-Host "VERDICT: 🟡 MOSTLY READY (minor issues)" -ForegroundColor Yellow
    $verdict = "PASS_WITH_WARNINGS"
} else {
    Write-Host "VERDICT: ❌ NOT READY (fix critical issues first)" -ForegroundColor Red
    $verdict = "FAIL"
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Fix any FAILED checks above" -ForegroundColor White
Write-Host "  2. Test installer manually on clean VM" -ForegroundColor White
Write-Host "  3. Run: .\scripts\create-github-release.ps1" -ForegroundColor Cyan
Write-Host "  4. Update landing page with download link" -ForegroundColor White
Write-Host ""

# Generate report
if ($GenerateReport) {
    $timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
    $reportPath = Join-Path $ProjectRoot "installer-test-report-$timestamp.md"

    $report = @"
# Installer Smoke Test Report

**Date**: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
**Installer**: $installerName
**Size**: $installerSize MB
**Verdict**: $verdict

## Test Results

| Test | Result |
|------|--------|
$(foreach ($test in $results.GetEnumerator()) {
    $status = if ($test.Value -eq $true) { "✅ PASS" } elseif ($test.Value -eq $false) { "❌ FAIL" } else { "⚠️ $($test.Value)" }
    "| $($test.Key) | $status |"
})

## Summary

- **Passed**: $passCount
- **Failed**: $failCount
- **Warnings**: $warnCount

## Manual Test Checklist

- [ ] Run installer on development machine
- [ ] Installation completes without errors
- [ ] App launches successfully
- [ ] Backend starts on port 8000
- [ ] Frontend connects to backend
- [ ] Can speak to Jarvis and receive voice response
- [ ] Uninstall works cleanly
- [ ] Test on clean Windows VM
- [ ] Verify Python 3.11 detection
- [ ] Complete end-to-end user flow

## Next Steps

1. Fix any failed checks
2. Complete manual test checklist
3. Run \`.\scripts\create-github-release.ps1\`
4. Update landing page download link
5. Announce release

---

Generated by: test-installer.ps1
"@

    $report | Out-File -FilePath $reportPath -Encoding UTF8
    Write-Host "Report saved: $reportPath" -ForegroundColor Green
}

# Exit code
if ($verdict -eq "FAIL") {
    exit 1
} else {
    exit 0
}
