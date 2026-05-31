# ⚡ Quick Start: Build & Ship Installer

**TL;DR**: 5 commands to go from code to downloadable installer on GitHub Releases.

---

## ✅ Prerequisites (One-Time Setup)

```powershell
# Install GitHub CLI if needed
choco install gh
# OR download from https://cli.github.com

# Authenticate
gh auth login
```

---

## 🚀 Complete Workflow (Copy-Paste)

```powershell
# 1. Navigate to project
cd C:\Users\Emmanuel\Documents\JarvisAI

# 2. Ensure clean state
git checkout master
git pull

# 3. Install frontend dependencies
cd frontend
npm install

# 4. Build installer (~5-10 min)
cd ..
.\scripts\build-installer.ps1

# Expected output: dist-installer/JarvisAI-Setup-1.0.0-alpha.exe (~100 MB)

# 5. Test locally (optional but recommended)
.\scripts\test-installer.ps1 -InstallerPath ".\dist-installer\JarvisAI-Setup-1.0.0-alpha.exe" -GenerateReport

# 6. Publish to GitHub Releases
.\scripts\create-github-release.ps1

# 7. Update landing page (already done, just push)
git push origin master

# Done! Installer is live at:
# https://github.com/Corgipollo/JarvisAI/releases/download/v1.0.0-alpha/JarvisAI-Setup-1.0.0-alpha.exe
```

**Total time**: 15-20 minutes (mostly automated)

---

## 🧪 Manual Test on VM (CRITICAL)

**Before announcing publicly**, test on clean Windows VM:

```powershell
# 1. Spin up Windows 11 VM (VirtualBox/Hyper-V)
# 2. Download installer from GitHub Releases
# 3. Run installer
# 4. Verify:
#    - Installation completes
#    - Python detection works
#    - App launches
#    - Voice interaction works: "Hola Jarvis, ¿qué puedes hacer?"
# 5. Uninstall and verify clean removal
```

---

## 📋 What Each Script Does

### `build-installer.ps1`
- Validates Python 3.11 + Node.js 18+
- Installs dependencies
- Bundles frontend + backend with electron-builder
- Creates NSIS installer in `dist-installer/`
- Verifies output

**Flags**:
- `-SkipTests` — Skip backend health check (faster)

### `test-installer.ps1`
- Static analysis (file size, format, signature)
- Prerequisites check (Python, ports, disk space)
- Documentation verification
- Git status check

**Flags**:
- `-GenerateReport` — Save markdown report

### `create-github-release.ps1`
- Creates GitHub release with tag `v1.0.0-alpha`
- Uploads installer as release asset
- Generates release notes
- Marks as prerelease

**Flags**:
- `-Version "1.0.1-alpha"` — Custom version
- `-InstallerPath "path/to/installer.exe"` — Custom installer

---

## 🔗 Important URLs

- **Landing page**: https://corgipollo.github.io/JarvisAI/
- **Releases**: https://github.com/Corgipollo/JarvisAI/releases
- **Repo**: https://github.com/Corgipollo/JarvisAI

---

## 🚨 Troubleshooting

### Build fails with "icon.ico not found"
```powershell
# Option 1: Create icon from PNG
# Use https://convertio.co/png-ico/
# Convert frontend/src/assets/jarvis-icon.png
# Save as frontend/build/icon.ico

# Option 2: Skip icon (uses default)
# Edit frontend/build.json, remove "icon" line
```

### "electron-builder not found"
```powershell
cd frontend
npm install electron-builder --save-dev
```

### Release fails with "not authenticated"
```powershell
gh auth login
# Follow prompts
```

### Installer too large (>150 MB)
```powershell
# Check if dev dependencies are bundled
cd frontend
npm prune --production

# Rebuild
cd ..
.\scripts\build-installer.ps1
```

---

## 📊 Success Checklist

After running all steps:

- [ ] Installer created in `dist-installer/`
- [ ] Installer size ~80-120 MB
- [ ] GitHub release published at `/releases/tag/v1.0.0-alpha`
- [ ] Direct download URL works
- [ ] Landing page shows Download button
- [ ] Tested on clean VM successfully
- [ ] No CRITICAL bugs reported

---

## 🔜 Next Steps After Release

1. **Monitor downloads**: Check GitHub Insights → Traffic
2. **Track issues**: Watch Issues tab for installation bugs
3. **Collect feedback**: GitHub Discussions + email
4. **Plan beta**: Address alpha feedback for v1.0.0-beta

---

## 📚 Full Documentation

- **Complete guide**: `INSTALLER-GUIDE.md`
- **Checklist**: `DISTRIBUTION-CHECKLIST.md`
- **Summary**: `INSTALLER-PRODUCTION-SUMMARY.md`
- **User install**: `README-INSTALL.md`

---

**Generated**: 2026-05-31  
**Quick ref for**: Emmanuel Pedraza

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
