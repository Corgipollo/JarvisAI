# 📦 Jarvis AI Installer — Production Guide

**Date**: 2026-05-31  
**Version**: 1.0.0-alpha  
**Target**: Windows 10/11 (64-bit)

---

## 🎯 Overview

This guide covers the complete process to create, test, and distribute a production-ready Windows installer for Jarvis AI.

### What Gets Packaged

The installer bundles:
- ✅ **Electron Frontend** (UI + system tray)
- ✅ **Python Backend** (FastAPI server)
- ✅ **Dependencies** (npm + pip packages)
- ✅ **Configuration** (.env template)
- ✅ **Scripts** (startup, health checks)

**Installer Size**: ~80-120 MB (compressed)  
**Installed Size**: ~500 MB (with dependencies)

---

## 🛠️ Prerequisites (Build Machine)

| Tool | Version | Install Command |
|------|---------|-----------------|
| **Node.js** | 18.x+ | [nodejs.org](https://nodejs.org) |
| **Python** | 3.11.x | [python.org](https://www.python.org/downloads/release/python-3110/) |
| **Git** | 2.x+ | [git-scm.com](https://git-scm.com) |
| **GitHub CLI** | Latest | `choco install gh` or [cli.github.com](https://cli.github.com) |
| **PowerShell** | 5.1+ | Included in Windows |

**RAM**: 8GB+ recommended for build process  
**Disk**: 5GB+ free space

---

## 🚀 Quick Start (Build Installer)

```powershell
# 1. Navigate to project
cd C:\Users\Emmanuel\Documents\JarvisAI

# 2. Install frontend dev dependencies
cd frontend
npm install

# 3. Build installer (automated)
cd ..
.\scripts\build-installer.ps1

# Output: dist-installer/JarvisAI-Setup-1.0.0-alpha.exe
```

**Build time**: 5-10 minutes (first build)

---

## 📋 Step-by-Step Build Process

### Step 1: Prepare Build Environment

```powershell
# Clone repo if you haven't
git clone https://github.com/Corgipollo/JarvisAI.git
cd JarvisAI

# Ensure on master branch
git checkout master
git pull origin master

# Check prerequisites
node --version   # Should be 18.x+
python --version # Should be 3.11.x
gh --version     # Should be installed
```

### Step 2: Configure Build Assets

The installer requires some assets in `frontend/build/`:

```powershell
cd frontend

# Create build directory if missing
if (!(Test-Path build)) { New-Item -ItemType Directory -Path build }

# CRITICAL: Create/copy icon.ico
# Option A: Convert existing PNG
#   Use online tool: https://convertio.co/png-ico/
#   Upload: src/assets/jarvis-icon.png
#   Download as: build/icon.ico

# Option B: Use placeholder (will use Electron default)
#   Skip this step - electron-builder will warn but proceed

# Create installer banner images (optional)
# - build/installerHeader.bmp (150x57 pixels)
# - build/installerSidebar.bmp (164x314 pixels)
# Use any image editor to create branded images
```

### Step 3: Review Build Configuration

Check `frontend/build.json` settings:

```json
{
  "appId": "com.corgipollo.jarvisai",
  "productName": "Jarvis AI",
  "win": {
    "target": "nsis",
    "icon": "build/icon.ico"
  },
  "nsis": {
    "oneClick": false,
    "allowToChangeInstallationDirectory": true,
    "createDesktopShortcut": true,
    "createStartMenuShortcut": true
  }
}
```

**Key settings**:
- `oneClick: false` → User can choose install directory
- `runAfterFinish: true` → Auto-launches Jarvis after install
- `extraResources` → Bundles backend folder

### Step 4: Build Installer

```powershell
# From project root
.\scripts\build-installer.ps1

# Flags available:
# -SkipTests    : Skip backend health check
# -Publish      : Upload to GitHub Releases (requires auth)

# Example: Quick build without tests
.\scripts\build-installer.ps1 -SkipTests
```

**Build process**:
1. ✅ Validates Python 3.11 + Node.js 18+
2. ✅ Installs npm dependencies
3. ✅ Runs backend health check (unless `-SkipTests`)
4. ✅ Bundles backend + frontend with electron-builder
5. ✅ Creates NSIS installer in `dist-installer/`
6. ✅ Verifies output file size

**Expected output**:
```
dist-installer/
  JarvisAI-Setup-1.0.0-alpha.exe  (~100MB)
  latest.yml                       (auto-update manifest)
```

### Step 5: Test Installer Locally

**Test on your development machine**:

```powershell
# Run installer
.\dist-installer\JarvisAI-Setup-1.0.0-alpha.exe

# Follow wizard:
# 1. Choose install directory (default: C:\Users\<You>\AppData\Local\Programs\jarvis-ai)
# 2. Select shortcuts (desktop + start menu recommended)
# 3. Wait for installation (~2-3 min)
# 4. Jarvis should auto-launch

# Verify installation:
# - Desktop shortcut exists
# - Start menu entry exists
# - App launches successfully
# - Backend starts on http://localhost:8000
# - Frontend connects to backend
# - Microphone permission requested

# Uninstall test:
# 1. Settings → Apps → Jarvis AI → Uninstall
# 2. Verify clean removal (no leftover files)
```

**Test on clean VM** (CRITICAL):

```powershell
# Spin up Windows 11 VM (VirtualBox, Hyper-V, or Azure)
# - Fresh install (no dev tools)
# - 8GB RAM minimum
# - Internet connected

# Copy installer to VM
# Run installer
# Verify:
# - Python 3.11 detection works (installer should prompt to download if missing)
# - Installation completes without errors
# - App launches successfully
# - Can speak to Jarvis and get response
```

---

## 📤 Publish to GitHub Releases

### Option A: Automated Script (Recommended)

```powershell
# Authenticate with GitHub (one-time)
gh auth login
# Follow prompts to authenticate

# Create release and upload installer
.\scripts\create-github-release.ps1

# Custom version:
.\scripts\create-github-release.ps1 -Version "1.0.0-beta"

# Custom installer path:
.\scripts\create-github-release.ps1 -InstallerPath "C:\path\to\installer.exe"
```

**What it does**:
1. Checks if release already exists (prompts to overwrite)
2. Generates release notes from template
3. Creates GitHub release (prerelease flag set)
4. Uploads installer as release asset
5. Prints direct download URL

### Option B: Manual via GitHub Web UI

1. **Go to**: https://github.com/Corgipollo/JarvisAI/releases/new
2. **Tag**: `v1.0.0-alpha` (create new tag)
3. **Title**: `Jarvis AI v1.0.0-alpha - Alpha Release`
4. **Description**: Copy from `scripts/create-github-release.ps1` release notes
5. **Attach files**: Upload `dist-installer/JarvisAI-Setup-1.0.0-alpha.exe`
6. **Prerelease**: ✅ Check (this is alpha)
7. **Publish**

### Option C: Manual via GitHub CLI

```powershell
gh release create v1.0.0-alpha `
  .\dist-installer\JarvisAI-Setup-1.0.0-alpha.exe `
  --title "Jarvis AI v1.0.0-alpha - Alpha Release" `
  --notes "First public alpha. See README for details." `
  --prerelease
```

---

## 🌐 Update Landing Page

Once the release is published, update the landing page download button.

### Get Direct Download URL

After publishing, GitHub generates a permanent download URL:

```
https://github.com/Corgipollo/JarvisAI/releases/download/v1.0.0-alpha/JarvisAI-Setup-1.0.0-alpha.exe
```

### Update Landing Page HTML

Edit `docs/index.html`:

```html
<!-- Find the Download CTA button (around line 50-60) -->

<!-- BEFORE: -->
<a href="https://github.com/Corgipollo/JarvisAI" class="btn-primary">
  Join Beta
</a>

<!-- AFTER: -->
<a href="https://github.com/Corgipollo/JarvisAI/releases/download/v1.0.0-alpha/JarvisAI-Setup-1.0.0-alpha.exe" 
   class="btn-primary"
   download>
  Download Jarvis AI
  <span style="font-size: 0.8em; opacity: 0.9;">(v1.0.0-alpha • Windows)</span>
</a>

<!-- Add secondary button for other platforms -->
<a href="https://github.com/Corgipollo/JarvisAI#installation" class="btn-secondary">
  Install Manually
</a>
```

### Add System Requirements Notice

Add before download button:

```html
<div style="margin-top: 1rem; padding: 1rem; background: rgba(255,255,255,0.1); border-radius: 8px;">
  <strong>System Requirements:</strong>
  <ul style="margin: 0.5rem 0; list-style: none;">
    <li>✓ Windows 10/11 (64-bit)</li>
    <li>✓ 8GB RAM</li>
    <li>✓ Python 3.11 (auto-detected)</li>
    <li>✓ Internet connection</li>
  </ul>
</div>
```

### Deploy Updated Landing

```powershell
cd docs

# Verify changes
git diff index.html

# Commit
git add index.html
git commit -m "feat: add direct download link for v1.0.0-alpha installer"

# Push to GitHub (triggers auto-deploy to Pages)
git push origin master

# Verify live in ~2 minutes:
# https://corgipollo.github.io/JarvisAI/
```

---

## 🧪 Smoke Test Installation

After publishing, run a final smoke test as an end-user would:

```powershell
# Test 1: Download from landing page
# 1. Open: https://corgipollo.github.io/JarvisAI/
# 2. Click "Download Jarvis AI"
# 3. Verify download starts (check browser downloads)
# 4. Verify file size matches (~100MB)

# Test 2: Run installer
# 1. Run downloaded .exe
# 2. Follow installation wizard
# 3. Verify Python 3.11 check works
# 4. Complete installation
# 5. Verify Jarvis auto-launches

# Test 3: Functional test
# 1. Grant microphone permission
# 2. Say: "Hola Jarvis"
# 3. Verify wake word detection
# 4. Say: "¿Qué puedes hacer?"
# 5. Verify response with voice

# Test 4: Uninstall
# 1. Uninstall via Settings
# 2. Verify clean removal
# 3. Check no orphaned files in AppData
```

**Create smoke test report**:

```markdown
## Smoke Test Report - v1.0.0-alpha

**Date**: 2026-05-31  
**Tester**: Emmanuel  
**Platform**: Windows 11 Pro

### Test Results

| Test | Status | Notes |
|------|--------|-------|
| Download from landing | ✅ PASS | 98.4 MB, 12s download |
| Installer launches | ✅ PASS | No UAC issues |
| Python check | ✅ PASS | Detected 3.11.5 |
| Installation | ✅ PASS | 2m 34s total |
| Auto-launch | ✅ PASS | Jarvis started immediately |
| Microphone permission | ✅ PASS | Prompt shown, granted |
| Wake word | ✅ PASS | "Hola Jarvis" detected |
| Voice response | ✅ PASS | TTS working |
| Uninstall | ✅ PASS | Clean removal |

### Issues Found
- None

### Verdict
✅ **READY FOR ALPHA RELEASE**
```

---

## 📊 Metrics to Track

After release, monitor these metrics:

### GitHub Metrics
- **Download count**: Check Insights → Traffic → Releases
- **Star growth**: Track repo stars
- **Issue reports**: Monitor Issues tab

### Landing Page Metrics (if GA/Plausible installed)
- **Download CTA click rate**: Should be >30%
- **Download completion rate**: % who click and actually download
- **Bounce rate**: Should decrease with Download option

### User Feedback
- **GitHub Discussions**: Monitor for feedback
- **Email feedback**: emmanuel@corgipollo.dev
- **Twitter mentions**: @Corgipollo

---

## 🐛 Troubleshooting

### Build fails with "icon.ico not found"

**Fix**:
```powershell
# Create minimal icon
cd frontend/build

# Option 1: Use online converter
# Go to: https://convertio.co/png-ico/
# Upload: ../src/assets/jarvis-icon.png
# Download as: icon.ico

# Option 2: Skip icon (uses Electron default)
# Edit build.json, remove "icon" line
```

### Build fails with "Cannot find module electron-builder"

**Fix**:
```powershell
cd frontend
npm install electron-builder --save-dev
npm run build
```

### Installer size is >200MB

**Cause**: Dev dependencies bundled

**Fix**:
```powershell
# Edit package.json
# Move all devDependencies to devDependencies section
# Ensure build.json has:
{
  "files": ["**/*", "!node_modules/.cache"]
}

# Rebuild
npm run build
```

### Installer fails to detect Python on user machine

**Cause**: NSIS script registry check failing

**Fix**: Edit `frontend/build/installer.nsh`:
```nsi
; Check both HKLM and HKCU
ReadRegStr $0 HKLM "SOFTWARE\Python\PythonCore\3.11\InstallPath" ""
${If} $0 == ""
  ReadRegStr $0 HKCU "SOFTWARE\Python\PythonCore\3.11\InstallPath" ""
${EndIf}
```

### Backend doesn't start after installation

**Cause**: pip dependencies failed to install

**Fix**: Add better error handling in installer.nsh:
```nsi
nsExec::ExecToLog 'python -m pip install -r "$INSTDIR\resources\backend\requirements.txt"'
Pop $0
${If} $0 != 0
  MessageBox MB_OK "Failed to install Python dependencies. Check logs."
${EndIf}
```

---

## 🔜 Next Steps

After successful alpha release:

1. **Collect feedback** (1-2 weeks)
   - Monitor GitHub Issues
   - Email feedback from early testers
   - Analytics from landing page

2. **Fix critical bugs** (based on feedback)
   - Prioritize blockers (can't install, can't launch)
   - Document workarounds in TROUBLESHOOTING.md

3. **Plan beta release** (v1.0.0-beta)
   - Address alpha feedback
   - Add auto-update mechanism (electron-updater)
   - Improve onboarding wizard

4. **Prepare for v1.0 stable**
   - macOS support (electron-builder supports)
   - Linux support (.deb, .AppImage)
   - Signed installer (code signing certificate)

---

## 📞 Support

**Build issues**: emmanuel@corgipollo.dev  
**Documentation**: [README-INSTALL.md](./README-INSTALL.md)  
**Troubleshooting**: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

---

**Generated**: 2026-05-31  
**Last Updated**: 2026-05-31  
**Version**: 1.0

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
