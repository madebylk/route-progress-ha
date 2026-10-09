// Local-only preview server for the actual card with a simulated hass object.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://localhost').pathname;
  const file = path.resolve(root, '.' + (pathname === '/' ? '/tests/frontend/card-preview.html' : pathname));
  if (!file.startsWith(root + path.sep)) { res.writeHead(403); return res.end(); }
  fs.readFile(file, (err, data) => {
    if(err) {res.writeHead(404); return res.end();}
    res.setHeader('Content-Type', file.endsWith('.js') ? 'text/javascript' : 'text/html; charset=utf-8');
    res.end(data);
  });
}).listen(8766, '127.0.0.1', () => console.log('Card preview: http://127.0.0.1:8766'));
