const electron = require('electron');
console.log('electron keys:', Object.keys(electron));
console.log('app type:', typeof electron.app);
if (electron.app) {
  electron.app.whenReady().then(() => {
    console.log('APP READY');
    electron.app.quit();
  });
} else {
  console.log('app is undefined! Full module:', JSON.stringify(electron).substring(0, 200));
  process.exit(1);
}
