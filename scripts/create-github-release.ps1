# Create GitHub Release for Jarvis AI
# Uploads installer to GitHub Releases

param(
    [Parameter(Mandatory=$false)]
    [string]$Version = "1.0.0-alpha",

    [Parameter(Mandatory=$false)]
    [string]$InstallerPath
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "GitHub Release Creator - Jarvis AI" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Check if gh CLI is installed
$ghVersion = gh --version 2>$null
if (-not $ghVersion) {
    Write-Host "ERROR: GitHub CLI (gh) not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "Install it from: https://cli.github.com" -ForegroundColor Yellow
    Write-Host "Or use Chocolatey: choco install gh" -ForegroundColor Yellow
    exit 1
}
Write-Host "✓ GitHub CLI installed: $($ghVersion[0])" -ForegroundColor Green

# Find installer if not specified
if (-not $InstallerPath) {
    $distDir = Join-Path $ProjectRoot "dist-installer"
    $installerPattern = Join-Path $distDir "JarvisAI-Setup-*.exe"
    $installerFile = Get-ChildItem -Path $installerPattern -ErrorAction SilentlyContinue |
                     Sort-Object LastWriteTime -Descending |
                     Select-Object -First 1

    if (-not $installerFile) {
        Write-Host "ERROR: No installer found in $distDir" -ForegroundColor Red
        Write-Host "Run .\scripts\build-installer.ps1 first" -ForegroundColor Yellow
        exit 1
    }

    $InstallerPath = $installerFile.FullName
}

if (-not (Test-Path $InstallerPath)) {
    Write-Host "ERROR: Installer not found: $InstallerPath" -ForegroundColor Red
    exit 1
}

$installerName = Split-Path $InstallerPath -Leaf
$sizeInMB = [math]::Round((Get-Item $InstallerPath).Length / 1MB, 2)

Write-Host ""
Write-Host "Release Details:" -ForegroundColor Yellow
Write-Host "  Version: v$Version" -ForegroundColor White
Write-Host "  Installer: $installerName" -ForegroundColor White
Write-Host "  Size: $sizeInMB MB" -ForegroundColor White
Write-Host ""

# Create release notes
$releaseNotes = @"
# Jarvis AI v$Version - Alpha Release

**First public alpha release** of Jarvis AI - your local voice-first AI assistant.

## 🎯 What's Included

- ✅ **Voice-First Interface**: Talk to Jarvis naturally, no keyboard needed
- ✅ **Hybrid AI Routing**: Claude API → Gemini Pro → Cerebras → Ollama local
- ✅ **100% Local**: All processing on your machine (except cloud AI APIs)
- ✅ **Obsidian Integration**: Remembers context from your notes
- ✅ **PC Control**: Open apps, search web, control Spotify, take screenshots
- ✅ **Fast STT/TTS**: faster-whisper + edge-tts for real-time voice

## 📦 Installation

### Windows 10/11 (Recommended)

1. **Download** \`$installerName\` (${sizeInMB}MB)
2. **Run installer** - follows setup wizard
3. **Grant microphone permission** when prompted
4. **Add API key** (Claude/Gemini/Cerebras - at least one required)
5. **Say "Hola Jarvis"** to start!

### System Requirements

- **OS**: Windows 10/11 (64-bit)
- **RAM**: 8GB+ recommended
- **Python**: 3.11.x (installer checks and prompts if missing)
- **GPU**: NVIDIA CUDA (optional, for faster STT)
- **Internet**: Required for cloud AI APIs (Ollama works offline)

## 🚀 Quick Start

After installation:

\`\`\`bash
# Backend starts automatically on port 8000
# Frontend Electron app launches

# Try these commands:
"Jarvis, ¿qué puedes hacer?"
"Jarvis, abre Visual Studio Code"
"Jarvis, busca noticias sobre IA"
"Jarvis, captura mi pantalla"
\`\`\`

## 📖 Documentation

- **Installation Guide**: [README-INSTALL.md](https://github.com/Corgipollo/JarvisAI/blob/master/README-INSTALL.md)
- **Troubleshooting**: [TROUBLESHOOTING.md](https://github.com/Corgipollo/JarvisAI/blob/master/TROUBLESHOOTING.md)
- **Full README**: [README.md](https://github.com/Corgipollo/JarvisAI/blob/master/README.md)

## 🐛 Known Issues (Alpha)

- [ ] Installer may take 10-15 min on slow internet (downloads Python deps)
- [ ] GPU detection sometimes fails - manually edit \`.env\` to force CPU/GPU mode
- [ ] Wake word detection in noisy environments needs tuning
- [ ] Electron app may require firewall permission on first launch

## 💬 Feedback

This is an **alpha release** - bugs are expected! Please report issues:

- 🐞 **Bug reports**: [GitHub Issues](https://github.com/Corgipollo/JarvisAI/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/Corgipollo/JarvisAI/discussions)
- 📧 **Email**: emmanuel@corgipollo.dev

## 🔜 Roadmap (v1.0)

- [ ] macOS/Linux support
- [ ] One-click API key setup wizard
- [ ] Custom wake word training
- [ ] Plugin system for custom integrations
- [ ] Auto-update mechanism

---

**Built by**: Emmanuel Pedraza ([@Corgipollo](https://github.com/Corgipollo))
**License**: MIT
**Landing Page**: [https://corgipollo.github.io/JarvisAI/](https://corgipollo.github.io/JarvisAI/)

---

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
"@

# Create release
Write-Host "Creating GitHub release v$Version..." -ForegroundColor Yellow

Push-Location $ProjectRoot
try {
    # Check if release already exists
    $existingRelease = gh release view "v$Version" 2>$null
    if ($existingRelease) {
        Write-Host ""
        Write-Host "⚠ Release v$Version already exists!" -ForegroundColor Yellow
        $overwrite = Read-Host "Delete and recreate? (y/N)"
        if ($overwrite -eq 'y') {
            Write-Host "Deleting existing release..." -ForegroundColor Cyan
            gh release delete "v$Version" --yes
        } else {
            Write-Host "Cancelled." -ForegroundColor Yellow
            exit 0
        }
    }

    # Create release with installer
    Write-Host "Uploading installer to GitHub..." -ForegroundColor Cyan
    $notesFile = Join-Path $env:TEMP "jarvis-release-notes.md"
    $releaseNotes | Out-File -FilePath $notesFile -Encoding UTF8

    gh release create "v$Version" `
        $InstallerPath `
        --title "Jarvis AI v$Version - Alpha Release" `
        --notes-file $notesFile `
        --draft=false `
        --prerelease

    if ($LASTEXITCODE -ne 0) {
        throw "gh release create failed"
    }

    Remove-Item $notesFile -ErrorAction SilentlyContinue

    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor Green
    Write-Host "✓ RELEASE CREATED SUCCESSFULLY" -ForegroundColor Green
    Write-Host "=" * 80 -ForegroundColor Green
    Write-Host ""
    Write-Host "Release URL:" -ForegroundColor Yellow
    Write-Host "  https://github.com/Corgipollo/JarvisAI/releases/tag/v$Version" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Direct Download:" -ForegroundColor Yellow
    Write-Host "  https://github.com/Corgipollo/JarvisAI/releases/download/v$Version/$installerName" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Test download from release page" -ForegroundColor White
    Write-Host "  2. Update landing page Download button:" -ForegroundColor White
    Write-Host "     https://corgipollo.github.io/JarvisAI/" -ForegroundColor Cyan
    Write-Host "  3. Announce on Twitter/LinkedIn/HN" -ForegroundColor White
    Write-Host ""

} catch {
    Write-Host ""
    Write-Host "ERROR: Failed to create release" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "  - Ensure you're authenticated: gh auth login" -ForegroundColor White
    Write-Host "  - Check repo permissions (requires write access)" -ForegroundColor White
    Write-Host "  - Verify installer file exists and is not corrupted" -ForegroundColor White
    exit 1
} finally {
    Pop-Location
}
