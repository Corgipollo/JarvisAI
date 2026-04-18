const electron = require('electron');
console.log('[DEBUG] electron module keys:', Object.keys(electron));
console.log('[DEBUG] app:', typeof electron.app);
const { app, BrowserWindow, ipcMain, globalShortcut, session, Tray, Menu, nativeImage, screen } = electron;
const path = require('path');
const fs = require('fs');

let mainWindow;
let tray = null;
let isCompact = true; // Modo widget por defecto

// Dimensiones del widget compacto
const COMPACT = { width: 420, height: 520 };
const FULL = { width: 1200, height: 800 };

function createTrayIcon() {
  // Crear icono desde SVG convertido a data URL para el tray
  const iconPath = path.join(__dirname, 'src', 'assets', 'jarvis-icon.png');
  let trayIcon;

  if (fs.existsSync(iconPath)) {
    trayIcon = nativeImage.createFromPath(iconPath);
  } else {
    // Icono fallback: circulo cyan 16x16
    trayIcon = nativeImage.createEmpty();
  }

  tray = new Tray(trayIcon.isEmpty() ? nativeImage.createFromBuffer(createFallbackIcon()) : trayIcon);
  tray.setToolTip('Jarvis AI — Alt+J para abrir');

  const contextMenu = Menu.buildFromTemplate([
    { label: 'Mostrar Jarvis', click: () => showJarvis() },
    { label: 'Modo Compacto', type: 'checkbox', checked: isCompact, click: (item) => toggleMode(item.checked) },
    { label: 'Siempre Arriba', type: 'checkbox', checked: true, click: (item) => mainWindow?.setAlwaysOnTop(item.checked) },
    { type: 'separator' },
    { label: 'Salir', click: () => { app.isQuitting = true; app.quit(); } }
  ]);
  tray.setContextMenu(contextMenu);
  tray.on('click', () => showJarvis());
}

function createFallbackIcon() {
  // 16x16 PNG cyan circle como fallback
  const { createCanvas } = (() => {
    try { return require('canvas'); } catch(e) { return {}; }
  })();
  // Si no hay canvas, retorna un buffer minimo PNG transparente
  return Buffer.from('iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAADklEQVQ4jWNgGAWDEwAAAhAAAbMjsFkAAAAASUVORK5CYII=', 'base64');
}

function createWindow() {
  const { width: screenW } = screen.getPrimaryDisplay().workAreaSize;

  mainWindow = new BrowserWindow({
    width: COMPACT.width,
    height: COMPACT.height,
    x: 8, // Arriba izquierda
    y: 8,
    minWidth: 380,
    minHeight: 400,
    frame: false,
    transparent: false,
    backgroundColor: '#0a0e17',
    alwaysOnTop: true,
    skipTaskbar: false,
    resizable: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: true,
    },
    icon: path.join(__dirname, 'src', 'assets', 'jarvis-logo.svg'),
    title: 'Jarvis AI',
    show: true,
  });

  // AUTO-GRANT permisos de microfono y camara
  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    const allowed = ['media', 'mediaKeySystem', 'microphone', 'camera', 'audio'];
    callback(allowed.includes(permission));
  });

  session.defaultSession.setPermissionCheckHandler((webContents, permission) => {
    const allowed = ['media', 'mediaKeySystem', 'microphone', 'camera', 'audio'];
    return allowed.includes(permission);
  });

  mainWindow.loadFile(path.join(__dirname, 'src', 'index.html'));

  if (process.argv.includes('--dev')) {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }

  // === HOTKEYS ===
  // Alt+J: Mostrar/Ocultar Jarvis
  globalShortcut.register('Alt+J', () => toggleVisibility());

  // Alt+X (MSX): Mostrar/Ocultar Jarvis (hotkey adicional)
  globalShortcut.register('Alt+X', () => toggleVisibility());

  // Alt+M: Toggle modo compacto/full
  globalShortcut.register('Alt+M', () => toggleMode(!isCompact));

  mainWindow.on('closed', () => { mainWindow = null; });

  // Minimizar al cerrar en vez de salir (se queda en tray)
  mainWindow.on('close', (e) => {
    if (!app.isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });

  createTrayIcon();
}

function toggleVisibility() {
  if (!mainWindow) return;
  if (mainWindow.isVisible() && mainWindow.isFocused()) {
    mainWindow.hide();
  } else {
    mainWindow.show();
    mainWindow.focus();
    // Reposicionar arriba izquierda si esta en compacto
    if (isCompact) {
      mainWindow.setPosition(8, 8);
    }
  }
}

function showJarvis() {
  if (!mainWindow) return;
  mainWindow.show();
  mainWindow.focus();
}

function toggleMode(compact) {
  if (!mainWindow) return;
  isCompact = compact;
  if (isCompact) {
    mainWindow.setSize(COMPACT.width, COMPACT.height, true);
    mainWindow.setPosition(8, 8, true);
    mainWindow.setAlwaysOnTop(true);
  } else {
    const { width: sw, height: sh } = screen.getPrimaryDisplay().workAreaSize;
    mainWindow.setSize(FULL.width, FULL.height, true);
    mainWindow.center();
    mainWindow.setAlwaysOnTop(false);
  }
  // Notificar al renderer del cambio de modo
  mainWindow.webContents.send('mode-change', isCompact ? 'compact' : 'full');
}

app.commandLine.appendSwitch('enable-speech-dispatcher');
app.commandLine.appendSwitch('enable-features', 'WebSpeechAPI');

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  globalShortcut.unregisterAll();
  if (process.platform !== 'win32') app.quit();
});

app.on('activate', () => {
  if (!mainWindow) createWindow();
  else showJarvis();
});

// IPC handlers
ipcMain.on('window-minimize', () => mainWindow?.minimize());
ipcMain.on('window-maximize', () => {
  if (mainWindow?.isMaximized()) mainWindow.unmaximize();
  else mainWindow?.maximize();
});
ipcMain.on('window-close', () => mainWindow?.hide());
ipcMain.on('window-toggle-always-on-top', () => {
  const isOnTop = mainWindow?.isAlwaysOnTop();
  mainWindow?.setAlwaysOnTop(!isOnTop);
});
ipcMain.on('toggle-compact', () => toggleMode(!isCompact));
