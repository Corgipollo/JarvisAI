try {
  const e = require('electron');
  console.log('Type:', typeof e);
  console.log('Is string:', typeof e === 'string');
  if (typeof e === 'string') {
    console.log('Value:', e);
    // Electron built-in not loaded - try direct require
    console.log('ERROR: require("electron") returns path, not module');
  } else {
    console.log('Keys:', Object.keys(e).join(', '));
  }
} catch(err) {
  console.log('Error:', err.message);
}
process.exit(0);
