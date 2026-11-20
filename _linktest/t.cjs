const fs = require('fs');
const url = require('url');
const p = 'D:/Projects/kog/_linktest/libreoffice-kit/package.json';
console.log('realpath', fs.realpathSync.native(p));
const u = url.pathToFileURL(p).href;
import(u).then(m => console.log('import ok', Object.keys(m).slice(0,3))).catch(e => console.log('import err', e.code || e.message));
