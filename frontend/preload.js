const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  toggleAlwaysOnTop: () => ipcRenderer.send('window-toggle-always-on-top'),
  toggleCompact: () => ipcRenderer.send('toggle-compact'),
  onModeChange: (callback) => ipcRenderer.on('mode-change', (_, mode) => callback(mode)),
});
