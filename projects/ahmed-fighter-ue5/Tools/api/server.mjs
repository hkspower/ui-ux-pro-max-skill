/* AHMED — Kuwait Fighter :: the live API
   ==========================================================================
   The bridge between the browser project -- where every number in the game
   is tuned -- and a running Unreal build. Three things, and the game needs
   none of them to play: it ships with the same tables baked in and is
   complete with the server unreachable.

     Balance.  GET /v1/revision            { Revision, GeneratedAt }
               GET /v1/config              the whole payload; If-None-Match / 304
               GET /v1/tables              the table names in the payload
               GET /v1/tables/{Name}       one table -- Fighters, Attacks, Stages,
                                           World, Colors, Sounds ... -- with its
                                           own ETag, for a tool that wants one
                                           thing and not the 40 KB

     Saves.    GET /v1/saves/{id}          a profile, or 404
               PUT /v1/saves/{id}          store one (JSON, <= 256 KB, must carry
                                           SchemaVersion and Progress)
               DELETE /v1/saves/{id}       forget it
               {id} is 1..64 of [A-Za-z0-9_-]. Set SAVE_TOKEN in the environment
               and every save call must carry `Authorization: Bearer <token>`.

     Live.     GET /v1/live  (WebSocket)   the server says hello with its
                                           revision, then pushes
                                           {"Type":"revision","Revision":…}
                                           every time the payload on disk
                                           changes. The Unreal client refetches
                                           on that message; a retune in the
                                           panel reaches a running game in
                                           about a second. Pings every 25 s.

               GET /health                 for whatever is watching the process

   Run:  node Tools/api/server.mjs                  (port 8787)
         PORT=9000 node Tools/api/server.mjs
         node Tools/api/server.mjs --watch          (re-read on every request too)
         node Tools/api/test.mjs                    (the whole surface, end to end)

   No dependencies. Node 18+ for the HTTP; the WebSocket is written here
   (RFC 6455, text frames, ping/pong, close) rather than pulled in, because
   the one rule this folder has is that it runs with nothing installed.

   BEFORE YOU PUT THIS ON THE INTERNET
   ---------------------------------------------------------------------------
   It terminates plain HTTP and knows nothing about TLS. iOS will not let a
   shipped app talk to it over plain HTTP without an ATS exception you do
   not want to ship, and a save endpoint with no token is a save endpoint
   anyone can write to. Put it behind a TLS terminator, set SAVE_TOKEN, and
   point the game at the https:// and wss:// addresses.
   ========================================================================== */

import { createServer } from 'node:http';
import { readFileSync, writeFileSync, existsSync, statSync, mkdirSync, unlinkSync,
         watchFile, unwatchFile } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const HERE = dirname(fileURLToPath(import.meta.url));
const CONFIG = process.env.AHMED_CONFIG || resolve(HERE, '../../Content/Data/config.json');
const SAVES = process.env.AHMED_SAVES || resolve(HERE, 'saves');
const SAVE_TOKEN = process.env.SAVE_TOKEN || '';

const PORT = Number(process.env.PORT || 8787);
const HOST = process.env.HOST || '0.0.0.0';
const WATCH = process.argv.includes('--watch');
const MAX_SAVE = 256 * 1024;
const SAVE_ID = /^[A-Za-z0-9_-]{1,64}$/;

/* ---------------------------------------------------------------- payload */
let cache = null;
function payload(){
  if(cache && !WATCH) return cache;
  return reload();
}
function reload(){
  if(!existsSync(CONFIG)){
    throw new Error('Content/Data/config.json is missing — run:\n' +
                    '  node Tools/export/export.mjs --api');
  }
  const raw = readFileSync(CONFIG, 'utf8');
  const body = JSON.parse(raw);
  const revision = body.Revision || createHash('sha256').update(raw).digest('hex').slice(0, 16);
  const tables = {};
  for(const [k, v] of Object.entries(body)){
    if(Array.isArray(v) || (v && typeof v === 'object')) tables[k] = v;
  }
  cache = {
    raw, body, revision, tables,
    generatedAt: body.GeneratedAt || statSync(CONFIG).mtime.toISOString(),
    etag: '"' + revision + '"'
  };
  return cache;
}

/* ------------------------------------------------------------------- http */
/* `head` travels with the request rather than sitting in a module variable:
   two requests in flight at once would otherwise decide each other's method. */
function send(res, code, body, headers = {}, head = false){
  const buf = Buffer.from(body);
  res.writeHead(code, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': buf.length,
    'access-control-allow-origin': '*',
    'access-control-allow-methods': 'GET, HEAD, PUT, DELETE',
    'access-control-allow-headers': 'authorization, content-type, if-none-match',
    'cache-control': 'no-cache',
    'x-content-type-options': 'nosniff',
    ...headers
  });
  res.end(head ? undefined : buf);
}
const json = o => JSON.stringify(o);
const etagOf = s => '"' + createHash('sha256').update(s).digest('hex').slice(0, 16) + '"';
const matches = (req, etag) => {
  const seen = req.headers['if-none-match'];
  return !!seen && seen.split(',').some(t => t.trim() === etag);
};

/* Over the limit is answered, not cut off: destroying the socket mid-upload
   shows the client ECONNRESET instead of the 413 that says why. A declared
   length is checked before a byte is read; an undeclared one is drained. */
function readBody(req, limit){
  return new Promise((ok, fail) => {
    const declared = Number(req.headers['content-length'] || 0);
    if(declared > limit){ req.resume(); fail(new Error('too large')); return; }
    const chunks = []; let size = 0, over = false;
    req.on('data', c => {
      if(over) return;
      size += c.length;
      if(size > limit){ over = true; chunks.length = 0; return; }
      chunks.push(c);
    });
    req.on('end', () => over ? fail(new Error('too large')) : ok(Buffer.concat(chunks).toString('utf8')));
    req.on('error', fail);
  });
}

function authorised(req){
  if(!SAVE_TOKEN) return true;
  const h = req.headers['authorization'] || '';
  return h === 'Bearer ' + SAVE_TOKEN;
}

/* A save is a profile the game wrote. It is stored as it came, but it has to
   look like one first: an object carrying SchemaVersion and Progress, which
   is the shape UAhmedSaveGame serialises to. */
function validSave(text){
  let o;
  try { o = JSON.parse(text); } catch(e){ return 'not JSON'; }
  if(!o || typeof o !== 'object' || Array.isArray(o)) return 'not an object';
  if(typeof o.SchemaVersion !== 'number') return 'no SchemaVersion';
  if(!o.Progress || typeof o.Progress !== 'object') return 'no Progress';
  return null;
}

async function handle(req, res){
  const head = req.method === 'HEAD';
  const url = new URL(req.url, 'http://localhost');
  const path = url.pathname.replace(/\/+$/, '') || '/';

  if(req.method === 'OPTIONS'){
    return send(res, 204, '', { allow: 'GET, HEAD, PUT, DELETE, OPTIONS' });
  }

  // ----- saves (the one thing here that is written to)
  let m = path.match(/^\/v1\/saves\/([^/]+)$/);
  if(m){
    const id = m[1];
    if(!SAVE_ID.test(id)) return send(res, 400, json({ error: 'bad save id' }), {}, head);
    if(!authorised(req)) return send(res, 401, json({ error: 'token required' }), { 'www-authenticate': 'Bearer' }, head);
    const file = join(SAVES, id + '.json');

    if(req.method === 'GET' || head){
      if(!existsSync(file)) return send(res, 404, json({ error: 'no save' }), {}, head);
      const text = readFileSync(file, 'utf8');
      const etag = etagOf(text);
      if(matches(req, etag)){ res.writeHead(304, { etag }); return res.end(); }
      return send(res, 200, text, { etag, 'last-modified': statSync(file).mtime.toUTCString() }, head);
    }
    if(req.method === 'PUT'){
      let text;
      try { text = await readBody(req, MAX_SAVE); }
      catch(e){ return send(res, 413, json({ error: 'save over ' + MAX_SAVE + ' bytes' }), { connection: 'close' }); }
      const why = validSave(text);
      if(why) return send(res, 422, json({ error: 'not a save: ' + why }));
      mkdirSync(SAVES, { recursive: true });
      const existed = existsSync(file);
      writeFileSync(file, text);
      return send(res, existed ? 200 : 201, json({ ok: true, id, bytes: Buffer.byteLength(text), etag: etagOf(text) }),
                  { etag: etagOf(text) });
    }
    if(req.method === 'DELETE'){
      if(existsSync(file)) unlinkSync(file);
      return send(res, 204, '');
    }
    return send(res, 405, json({ error: 'GET, PUT or DELETE' }), { allow: 'GET, HEAD, PUT, DELETE' });
  }

  // ----- everything else is read-only
  if(req.method !== 'GET' && !head){
    return send(res, 405, json({ error: 'read only' }), { allow: 'GET, HEAD' });
  }
  let p;
  try { p = payload(); }
  catch(e){
    console.error(e.message);
    return send(res, 503, json({ error: 'config not exported yet' }), {}, head);
  }

  if(path === '/health'){
    return send(res, 200, json({ ok: true, revision: p.revision, live: sockets.size }), {}, head);
  }
  if(path === '/v1/revision'){
    return send(res, 200, json({ Revision: p.revision, GeneratedAt: p.generatedAt }), { etag: p.etag }, head);
  }
  if(path === '/v1/config'){
    if(matches(req, p.etag)){ res.writeHead(304, { etag: p.etag }); return res.end(); }
    return send(res, 200, p.raw, { etag: p.etag }, head);
  }
  if(path === '/v1/tables'){
    return send(res, 200, json({ Revision: p.revision, Tables: Object.keys(p.tables) }), { etag: p.etag }, head);
  }
  m = path.match(/^\/v1\/tables\/([A-Za-z]+)$/);
  if(m){
    const t = p.tables[m[1]];
    if(t === undefined) return send(res, 404, json({ error: 'no such table', tables: Object.keys(p.tables) }), {}, head);
    const text = JSON.stringify({ Revision: p.revision, Name: m[1], Rows: t }, null, 2) + '\n';
    const etag = etagOf(text);
    if(matches(req, etag)){ res.writeHead(304, { etag }); return res.end(); }
    return send(res, 200, text, { etag }, head);
  }
  return send(res, 404, json({
    error: 'not found',
    endpoints: ['/v1/revision', '/v1/config', '/v1/tables', '/v1/tables/{Name}',
                '/v1/saves/{id}', '/v1/live (websocket)', '/health']
  }), {}, head);
}

/* -------------------------------------------------------------- websocket */
/* RFC 6455, the parts a push channel needs: the handshake, unmasking what
   the client sends, text frames out, ping/pong, close. Nothing binary, no
   extensions, no fragments longer than one frame. */
const WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11';
const sockets = new Set();

function frame(opcode, data){
  const buf = Buffer.from(data);
  let head;
  if(buf.length < 126) head = Buffer.from([0x80 | opcode, buf.length]);
  else if(buf.length < 65536){ head = Buffer.alloc(4); head[0] = 0x80 | opcode; head[1] = 126; head.writeUInt16BE(buf.length, 2); }
  else { head = Buffer.alloc(10); head[0] = 0x80 | opcode; head[1] = 127; head.writeBigUInt64BE(BigInt(buf.length), 2); }
  return Buffer.concat([head, buf]);
}
const text = o => frame(0x1, JSON.stringify(o));

function upgrade(req, socket){
  const url = new URL(req.url, 'http://localhost');
  if(url.pathname.replace(/\/+$/, '') !== '/v1/live'){
    socket.end('HTTP/1.1 404 Not Found\r\nconnection: close\r\n\r\n'); return;
  }
  const key = req.headers['sec-websocket-key'];
  if(!key || req.headers['upgrade']?.toLowerCase() !== 'websocket'){
    socket.end('HTTP/1.1 400 Bad Request\r\nconnection: close\r\n\r\n'); return;
  }
  const accept = createHash('sha1').update(key + WS_GUID).digest('base64');
  socket.write('HTTP/1.1 101 Switching Protocols\r\n' +
               'upgrade: websocket\r\nconnection: Upgrade\r\n' +
               'sec-websocket-accept: ' + accept + '\r\n\r\n');
  sockets.add(socket);
  socket.setNoDelay(true);

  let rev = '(none)';
  try { rev = payload().revision; } catch(e){}
  socket.write(text({ Type: 'hello', Revision: rev, GeneratedAt: cache ? cache.generatedAt : null }));

  let pending = Buffer.alloc(0);
  socket.on('data', chunk => {
    pending = Buffer.concat([pending, chunk]);
    for(;;){
      if(pending.length < 2) return;
      const fin = pending[0] & 0x80, op = pending[0] & 0x0f;
      const masked = pending[1] & 0x80;
      let len = pending[1] & 0x7f, off = 2;
      if(len === 126){ if(pending.length < 4) return; len = pending.readUInt16BE(2); off = 4; }
      else if(len === 127){ if(pending.length < 10) return; len = Number(pending.readBigUInt64BE(2)); off = 10; }
      if(masked) off += 4;
      if(pending.length < off + len) return;
      let data = pending.subarray(off, off + len);
      if(masked){
        const mask = pending.subarray(off - 4, off);
        const out = Buffer.alloc(len);
        for(let i = 0; i < len; i++) out[i] = data[i] ^ mask[i & 3];
        data = out;
      }
      pending = pending.subarray(off + len);
      if(!fin) continue;                                   // fragments are not handled; drop
      if(op === 0x8){ socket.write(frame(0x8, data)); socket.end(); return; }
      if(op === 0x9){ socket.write(frame(0xA, data)); continue; }
      if(op === 0x1){
        let msg = null;
        try { msg = JSON.parse(data.toString('utf8')); } catch(e){}
        if(msg && msg.Type === 'ping') socket.write(text({ Type: 'pong', Revision: cache ? cache.revision : null }));
        else if(msg && msg.Type === 'revision') socket.write(text({ Type: 'revision', Revision: cache ? cache.revision : null }));
      }
    }
  });
  const drop = () => { sockets.delete(socket); };
  socket.on('close', drop); socket.on('error', drop); socket.on('end', drop);
}

function broadcast(o){
  const buf = text(o);
  for(const s of sockets){ try { s.write(buf); } catch(e){ sockets.delete(s); } }
}

/* The payload on disk is what the exporter writes. When it changes, every
   connected game is told the new revision and refetches -- which is the
   whole point of the socket: retune, export, and the game you are looking at
   has the new numbers without a restart. */
function watchPayload(){
  watchFile(CONFIG, { interval: 500 }, () => {
    let was = cache ? cache.revision : null, now;
    try { now = reload().revision; } catch(e){ console.error(e.message); return; }
    if(now !== was){
      console.log(`  payload changed: ${was} -> ${now}, telling ${sockets.size} client(s)`);
      broadcast({ Type: 'revision', Revision: now, GeneratedAt: cache.generatedAt });
    }
  });
}

/* ------------------------------------------------------------------- main */
const server = createServer((req, res) => {
  handle(req, res).catch(e => {
    console.error(e);
    try { send(res, 500, json({ error: 'server error' })); } catch(_){}
  });
});
server.on('upgrade', upgrade);

const pinger = setInterval(() => {
  for(const s of sockets){ try { s.write(frame(0x9, 'ahmed')); } catch(e){ sockets.delete(s); } }
}, 25000);
pinger.unref();

server.listen(PORT, HOST, () => {
  let rev = '(not exported yet)';
  try { rev = payload().revision; } catch(e){}
  watchPayload();
  console.log(`AHMED live API on http://${HOST}:${PORT}   ws://${HOST}:${PORT}/v1/live`);
  console.log(`  revision ${rev}${WATCH ? '   [--watch: re-reads every request]' : ''}`);
  console.log(`  saves in ${SAVES}${SAVE_TOKEN ? '  (token required)' : '  (NO TOKEN — development only)'}`);
  console.log('  GET /v1/revision  /v1/config  /v1/tables[/{Name}]   GET|PUT|DELETE /v1/saves/{id}   GET /health');
});

// Let a test stop it cleanly.
process.on('SIGTERM', () => { unwatchFile(CONFIG); for(const s of sockets) s.end(); server.close(() => process.exit(0)); });
