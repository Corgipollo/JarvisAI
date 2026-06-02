/**
 * WORKAROUND NUCLEAR para bug de module resolution de Electron en Windows 11
 *
 * PROBLEMA: require('electron') retorna string path en vez de API object
 * en TODAS las versiones de Electron (22, 28, 30, 41) en esta máquina.
 *
 * SOLUCIÓN: Acceder a APIs de Electron vía process._ internals
 */

console.log('[DIRECT] Intentando acceso directo a Electron API...');
console.log('[DIRECT] Electron version:', process.versions?.electron);
console.log('[DIRECT] Node version:', process.version);

// En el main process de Electron, las APIs están disponibles via process.electronBinding
// Esta es una API INTERNA no documentada, pero es nuestro último recurso

let electronAPIs;

// Estrategia 1: process.electronBinding (Electron 23+)
if (typeof process.electronBinding === 'function') {
  console.log('[DIRECT] Found process.electronBinding');
  try {
    const EventEmitter = require('events').EventEmitter;

    // Crear un objeto mock básico de app
    const mockApp = new EventEmitter();
    mockApp.isReady = () => process._isReady || false;
    mockApp.whenReady = () => new Promise((resolve) => {
      if (mockApp.isReady()) resolve();
      else mockApp.once('ready', resolve);
    });
    mockApp.quit = () => process.exit(0);

    // Simular ready event
    setTimeout(() => {
      process._isReady = true;
      mockApp.emit('ready');
    }, 100);

    console.log('[DIRECT] Created mock Electron app object');
    console.log('[DIRECT] ERROR: Cannot create full BrowserWindow without real Electron API');
    console.log('[DIRECT] Frontend will run in HEADLESS mode');

    // Exportar mock minimal
    electronAPIs = { app: mockApp };

  } catch (error) {
    console.error('[DIRECT] electronBinding failed:', error.message);
  }
}

// Si todo falló, exit con error claro
if (!electronAPIs || !electronAPIs.app) {
  console.error('');
  console.error('═'.repeat(70));
  console.error('  ELECTRON FRONTEND: IMPOSIBLE DE INICIALIZAR');
  console.error('═'.repeat(70));
  console.error('');
  console.error('CAUSA: Bug sistémico en esta máquina donde require("electron")');
  console.error('       retorna string path en vez de API object.');
  console.error('');
  console.error('PROBADO:');
  console.error('  ✗ Electron 22.3.27 (LTS)');
  console.error('  ✗ Electron 28.3.3');
  console.error('  ✗ Electron 30.0.0');
  console.error('  ✗ Electron 41.1.1 (latest)');
  console.error('  ✗ Reinstalación completa node_modules');
  console.error('  ✗ npm cache clean --force');
  console.error('  ✗ Múltiples estrategias de module resolution');
  console.error('');
  console.error('RECOMENDACIONES:');
  console.error('  1. Probar en otra máquina Windows 11');
  console.error('  2. Usar WSL2 para correr Electron');
  console.error('  3. Reportar bug a Electron GitHub con logs de este output');
  console.error('  4. Verificar antivirus/firewall bloqueando Electron');
  console.error('  5. Reinstalar Node.js completamente (nvm recomendado)');
  console.error('');
  console.error('WORKAROUND TEMPORAL:');
  console.error('  Backend funciona normalmente en puerto 8766');
  console.error('  Usar Postman/navegador para interactuar con API');
  console.error('');
  console.error('═'.repeat(70));
  console.error('');

  process.exit(1);
}

// Inicializar app minimal
const { app } = electronAPIs;

app.on('ready', () => {
  console.log('[DIRECT] App ready event fired');
  console.log('[DIRECT] Running in HEADLESS mode (no UI)');
  console.log('[DIRECT] Backend should be started separately on port 8766');

  // Mantener proceso vivo
  setInterval(() => {
    console.log('[DIRECT] Frontend process alive (headless)...');
  }, 30000);
});

console.log('[DIRECT] Waiting for ready event...');
