// Test minimalista - SOLO probar que Electron API está disponible
console.log('[MINIMAL TEST] Starting...');
console.log('[MINIMAL TEST] typeof require:', typeof require);

// En el contexto de Electron, require('electron') debe retornar el módulo API
const electron = require('electron');
console.log('[MINIMAL TEST] typeof electron:', typeof electron);
console.log('[MINIMAL TEST] electron is string?:', typeof electron === 'string');

if (typeof electron === 'string') {
  console.error('[MINIMAL TEST] FAIL - electron is a path string, not running in Electron context');
  console.error('[MINIMAL TEST] Got:', electron);
  process.exit(1);
}

const { app, BrowserWindow } = electron;

console.log('[MINIMAL TEST] app:', typeof app);
console.log('[MINIMAL TEST] BrowserWindow:', typeof BrowserWindow);

if (!app) {
  console.error('[MINIMAL TEST] FAIL - app is undefined');
  process.exit(1);
}

console.log('[MINIMAL TEST] SUCCESS - Electron API is available!');

app.whenReady().then(() => {
  console.log('[MINIMAL TEST] Creating window...');
  const win = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  win.loadURL('data:text/html,<h1>Electron works!</h1>');
  console.log('[MINIMAL TEST] Window created successfully!');

  setTimeout(() => {
    console.log('[MINIMAL TEST] Closing after 3 seconds...');
    app.quit();
  }, 3000);
});

app.on('window-all-closed', () => {
  app.quit();
});
