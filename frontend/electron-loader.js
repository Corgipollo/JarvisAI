// Loader especial que parchea require() para Electron
console.log('[LOADER] Starting Electron loader...');
console.log('[LOADER] Node:', process.version, 'Electron:', process.versions?.electron);

// Guardar require original
const originalRequire = require('module').prototype.require;

// Monkey-patch require para interceptar 'electron'
require('module').prototype.require = function(id) {
  if (id === 'electron') {
    console.log('[LOADER] Intercepting require("electron")...');

    // Llamar al require original
    const result = originalRequire.apply(this, arguments);

    console.log('[LOADER] Original require returned type:', typeof result);

    // Si es string (el bug), intentar resolver el módulo real
    if (typeof result === 'string') {
      console.log('[LOADER] Detected path string bug, attempting fix...');

      // Intentar cargar el módulo real desde el dist
      const path = require('path');
      const electronPath = path.dirname(result);
      const resourcesPath = path.join(electronPath, 'resources');

      console.log('[LOADER] Electron path:', electronPath);
      console.log('[LOADER] Resources path:', resourcesPath);

      // En el contexto de Electron, el módulo real está disponible globalmente
      // Intentar acceder via process.atomBinding (API interna de Electron)
      if (typeof process.atomBinding === 'function') {
        console.log('[LOADER] Found process.atomBinding, using Electron internals...');
        // Esto es muy interno y puede no funcionar, pero es nuestro último recurso
      }

      // Otra estrategia: el módulo electron REAL debería estar en la app empaquetada
      try {
        const electronReal = originalRequire.call(this, path.join(resourcesPath, 'electron.asar'));
        if (electronReal && typeof electronReal === 'object') {
          console.log('[LOADER] ✓ Found real Electron module in electron.asar!');
          return electronReal;
        }
      } catch (e) {
        console.log('[LOADER] electron.asar not found:', e.message);
      }

      // Si todo falla, retornar el string original y dejar que falle
      console.log('[LOADER] ✗ All recovery attempts failed');
      return result;
    }

    // Si no es string, retornar normalmente
    console.log('[LOADER] ✓ Electron module is object, returning normally');
    return result;
  }

  // Para otros módulos, usar require original
  return originalRequire.apply(this, arguments);
};

console.log('[LOADER] Require monkey-patch installed');
console.log('[LOADER] Loading main.js...');

// Ahora cargar el main real
require('./main.js');
