// Debug ultra detallado
console.log('=== ELECTRON MAIN DEBUG ===');
console.log('1. process.versions.electron:', process.versions.electron);
console.log('2. process.versions.node:', process.versions.node);
console.log('3. process.versions.v8:', process.versions.v8);

console.log('\n4. Attempting require("electron")...');
let electron;
try {
  electron = require('electron');
  console.log('5. Success! typeof electron:', typeof electron);
  console.log('6. Is string?:', typeof electron === 'string');

  if (typeof electron === 'string') {
    console.log('7. PROBLEM: electron is path string:', electron);
    console.log('8. This should NEVER happen in Electron main process');
    console.log('9. Checking if this is actually Electron...');
    console.log('10. process.type:', process.type);
    console.log('11. __dirname:', __dirname);
    console.log('12. process.resourcesPath:', process.resourcesPath);
  } else {
    console.log('7. electron is object! Keys:', Object.keys(electron).slice(0, 10));
    console.log('8. electron.app:', typeof electron.app);
  }
} catch (error) {
  console.error('ERROR requiring electron:', error);
}

console.log('\n=== END DEBUG ===');
if (typeof electron !== 'string' && electron?.app) {
  electron.app.quit();
}
