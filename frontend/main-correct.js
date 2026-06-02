// Main process correcto para Electron
const { app, BrowserWindow } = require('electron');

console.log('[CORRECT MAIN] process.type:', process.type);
console.log('[CORRECT MAIN] Electron version:', process.versions.electron);

function createWindow () {
  const win = new BrowserWindow({
    width: 800,
    height: 600
  });

  win.loadURL('data:text/html,<h1 style="color:cyan;font-family:sans-serif;">✓ Electron funciona correctamente!</h1>');
  console.log('[CORRECT MAIN] Window created successfully');

  setTimeout(() => {
    console.log('[CORRECT MAIN] Closing...');
    app.quit();
  }, 3000);
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
