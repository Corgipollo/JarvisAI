# ✅ Distribution Checklist — Jarvis AI v1.0.0-alpha

**Goal**: Ship production-ready Windows installer to prospects via GitHub Releases + Landing Page

---

## 📋 Pre-Build Checklist

- [ ] **Code freeze on master branch**
  - [ ] All critical bugs fixed
  - [ ] README.md up to date
  - [ ] TROUBLESHOOTING.md complete
  - [ ] .env.example has all required keys documented

- [ ] **Build environment ready**
  - [ ] Node.js 18+ installed
  - [ ] Python 3.11.x installed
  - [ ] GitHub CLI (`gh`) installed and authenticated
  - [ ] 5GB+ free disk space

- [ ] **Assets prepared**
  - [ ] Icon created: `frontend/build/icon.ico` (or using placeholder)
  - [ ] LICENSE file exists in project root
  - [ ] Demo video recorded (optional for alpha)

---

## 🛠️ Build Process

- [ ] **1. Install frontend dependencies**
  ```powershell
  cd frontend
  npm install
  ```

- [ ] **2. Run build script**
  ```powershell
  cd ..
  .\scripts\build-installer.ps1
  ```
  - [ ] Build completes without errors
  - [ ] Installer created in `dist-installer/`
  - [ ] Installer size is reasonable (~80-120 MB)

- [ ] **3. Test installer locally**
  - [ ] Run installer on dev machine
  - [ ] Installation completes successfully
  - [ ] App launches after install
  - [ ] Backend starts on port 8000
  - [ ] Frontend connects to backend
  - [ ] Can speak to Jarvis and get response
  - [ ] Uninstall works cleanly

- [ ] **4. Test on clean VM** (CRITICAL)
  - [ ] Spin up fresh Windows 11 VM
  - [ ] Copy installer to VM
  - [ ] Run installer (should detect Python or prompt to install)
  - [ ] Complete installation
  - [ ] Verify app works end-to-end
  - [ ] Test uninstall

---

## 📤 Publish to GitHub Releases

- [ ] **1. Authenticate GitHub CLI**
  ```powershell
  gh auth login
  ```

- [ ] **2. Create release**
  ```powershell
  .\scripts\create-github-release.ps1
  ```
  - [ ] Release created successfully
  - [ ] Installer uploaded as asset
  - [ ] Release notes look correct
  - [ ] Marked as prerelease

- [ ] **3. Verify release page**
  - [ ] Visit: https://github.com/Corgipollo/JarvisAI/releases
  - [ ] v1.0.0-alpha is visible
  - [ ] Download link works
  - [ ] Release notes render correctly

---

## 🌐 Update Landing Page

- [ ] **1. Get direct download URL**
  - Copy from GitHub release page:
    ```
    https://github.com/Corgipollo/JarvisAI/releases/download/v1.0.0-alpha/JarvisAI-Setup-1.0.0-alpha.exe
    ```

- [ ] **2. Update `docs/index.html`**
  - [ ] Replace "Únete a la Beta" button with "Descargar Jarvis AI"
  - [ ] Link to direct download URL
  - [ ] Add system requirements section
  - [ ] Add links to manual install and all releases

- [ ] **3. Deploy landing page**
  ```powershell
  cd docs
  git add index.html
  git commit -m "feat: add download button for v1.0.0-alpha installer"
  git push origin master
  ```
  - [ ] Push successful
  - [ ] Wait 2-5 minutes for GitHub Pages deploy
  - [ ] Verify live at https://corgipollo.github.io/JarvisAI/

- [ ] **4. Create OG image** (optional but recommended)
  - [ ] Design 1200x630px image with logo + tagline
  - [ ] Save as `docs/og-image.jpg`
  - [ ] Update `<meta property="og:image">` in index.html
  - [ ] Redeploy

---

## 🧪 End-to-End Smoke Test

Test the complete user journey as a prospect would:

- [ ] **1. Visit landing page**
  - [ ] Open: https://corgipollo.github.io/JarvisAI/
  - [ ] Page loads correctly
  - [ ] Download button is visible and prominent

- [ ] **2. Download installer**
  - [ ] Click "Descargar Jarvis AI"
  - [ ] Download starts
  - [ ] File size matches (~100 MB)
  - [ ] File name is correct: `JarvisAI-Setup-1.0.0-alpha.exe`

- [ ] **3. Install on fresh machine/VM**
  - [ ] Run downloaded installer
  - [ ] Python 3.11 check works (prompts if not installed)
  - [ ] Installation completes in <5 minutes
  - [ ] Desktop shortcut created
  - [ ] Start menu entry created
  - [ ] App launches automatically

- [ ] **4. Functional test**
  - [ ] Microphone permission prompt appears
  - [ ] Grant permission
  - [ ] Say: "Hola Jarvis"
  - [ ] Wake word detected
  - [ ] Say: "¿Qué puedes hacer?"
  - [ ] Jarvis responds with voice listing capabilities
  - [ ] Response time is acceptable (<5 seconds)

- [ ] **5. Configuration test**
  - [ ] Open installed app directory
  - [ ] Verify `.env.example` exists
  - [ ] Edit `.env` with Claude API key
  - [ ] Restart Jarvis
  - [ ] Verify Claude routing works

- [ ] **6. Uninstall test**
  - [ ] Uninstall via Windows Settings → Apps
  - [ ] Uninstall completes
  - [ ] No leftover files in Program Files
  - [ ] No leftover files in AppData
  - [ ] Shortcuts removed

---

## 📣 Announcement Prep

- [ ] **1. Write announcement tweet**
  - [ ] Draft tweet highlighting key features
  - [ ] Include screenshot or demo GIF
  - [ ] Link to landing page
  - [ ] Hashtags: #AI #VoiceAssistant #OpenSource

- [ ] **2. Post to Hacker News** (optional)
  - [ ] Submit: "Show HN: Jarvis AI - Voice-First AI Assistant (Windows)"
  - [ ] Link to GitHub repo or landing page
  - [ ] Monitor comments and respond

- [ ] **3. LinkedIn post** (optional)
  - [ ] Professional post about building in public
  - [ ] Share journey and tech stack
  - [ ] Link to repo/landing

- [ ] **4. Email early beta testers**
  - [ ] Draft email with download link
  - [ ] Include quick start guide
  - [ ] Ask for feedback
  - [ ] Send to curated list (e.g., Roman Pushkin, johnnyfived)

---

## 📊 Post-Launch Monitoring

First 48 hours after release:

- [ ] **GitHub Metrics**
  - [ ] Check download count: Insights → Traffic
  - [ ] Monitor stars/forks growth
  - [ ] Watch for new issues
  - [ ] Respond to discussions

- [ ] **Landing Page Metrics** (if GA installed)
  - [ ] Track page views
  - [ ] Monitor download button click rate
  - [ ] Check bounce rate
  - [ ] Verify conversion funnel

- [ ] **User Feedback**
  - [ ] Monitor GitHub Issues for bugs
  - [ ] Check email for direct feedback
  - [ ] Watch Twitter mentions
  - [ ] Respond within 24 hours

- [ ] **Crash Reports** (if Sentry/error tracking installed)
  - [ ] Check for installation errors
  - [ ] Monitor runtime crashes
  - [ ] Triage critical issues

---

## 🚨 Rollback Plan

If critical issues are discovered:

- [ ] **1. Identify severity**
  - CRITICAL: Can't install, can't launch, data loss
  - HIGH: Major features broken, poor UX
  - MEDIUM: Minor bugs, workarounds exist

- [ ] **2. For CRITICAL issues**
  - [ ] Unpublish release (or mark as broken in description)
  - [ ] Add warning to landing page
  - [ ] Push hotfix branch
  - [ ] Build new installer (v1.0.1-alpha)
  - [ ] Replace release asset

- [ ] **3. For HIGH/MEDIUM issues**
  - [ ] Document in GitHub Issues
  - [ ] Add to TROUBLESHOOTING.md
  - [ ] Plan for next release
  - [ ] Notify affected users

---

## ✅ Success Criteria

**Minimum for "successful launch":**

- ✅ Installer builds and publishes without errors
- ✅ Landing page has working download link
- ✅ At least 1 successful install on clean VM
- ✅ Basic voice interaction works (STT → LLM → TTS)
- ✅ No CRITICAL bugs in first 24 hours

**Stretch goals:**

- 10+ downloads in first week
- 5+ GitHub stars in first week
- 2+ pieces of positive user feedback
- 0 CRITICAL bugs
- Featured on Hacker News front page (top 30)

---

## 📝 Post-Mortem Template

After first week, document learnings:

```markdown
## Launch Post-Mortem - Jarvis AI v1.0.0-alpha

**Launch Date**: 2026-05-31
**Distribution Channel**: GitHub Releases + Landing Page

### What Went Well
- 

### What Went Wrong
- 

### Metrics
- Downloads: X
- GitHub stars: +X
- Issues opened: X (CRITICAL: X, HIGH: X, MEDIUM: X)
- Conversion rate (landing → download): X%

### Learnings
1. 
2. 
3. 

### Action Items for Next Release
- [ ] 
- [ ] 
- [ ] 
```

---

## 🔗 Quick Reference Links

- **Repo**: https://github.com/Corgipollo/JarvisAI
- **Releases**: https://github.com/Corgipollo/JarvisAI/releases
- **Landing**: https://corgipollo.github.io/JarvisAI/
- **Issues**: https://github.com/Corgipollo/JarvisAI/issues
- **Docs**: https://github.com/Corgipollo/JarvisAI#readme

---

**Last Updated**: 2026-05-31  
**Checklist Version**: 1.0  
**Status**: ⏳ Ready to execute

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
