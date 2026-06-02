// Test minimalista de importación de Electron
console.log('=== TEST ELECTRON IMPORT ===');
console.log('Node version:', process.version);

try {
  const electron = require('electron');
  console.log('\n1. electron type:', typeof electron);
  console.log('2. electron is array?:', Array.isArray(electron));
  console.log('3. electron constructor:', electron.constructor.name);

  // Intentar diferentes formas de acceso
  console.log('\n4. Direct property access:');
  console.log('   electron.app:', typeof electron.app);
  console.log('   electron.BrowserWindow:', typeof electron.BrowserWindow);

  console.log('\n5. electron.default:', typeof electron.default);
  if (electron.default) {
    console.log('   electron.default.app:', typeof electron.default.app);
  }

  console.log('\n6. Object.keys(electron).slice(0, 10):', Object.keys(electron).slice(0, 10));
  console.log('   Total keys:', Object.keys(electron).length);

  // Inspeccionar el primer elemento si es array-like
  if (electron[0] !== undefined) {
    console.log('\n7. electron[0] type:', typeof electron[0]);
    console.log('   electron[0] value:', electron[0]);
  }

  // Buscar propiedades conocidas en el prototipo
  console.log('\n8. Prototype chain:');
  let proto = Object.getPrototypeOf(electron);
  console.log('   prototype:', proto?.constructor?.name);

} catch (error) {
  console.error('ERROR importing electron:', error.message);
  console.error(error.stack);
}

console.log('\n=== END TEST ===');
