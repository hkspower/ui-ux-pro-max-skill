/* AHMED — Kuwait Fighter :: the balance API
   ==========================================================================
   Serves the exported tables to a packaged build, so numbers can change
   without shipping an update. The game never *needs* this: it ships with the
   same tables baked in and plays fine with the server unreachable. What the
   server buys is turning a two-day store review into a thirty-second change.

   Endpoints:

     GET /v1/revision   { "Revision": "3d9e1e67…", "GeneratedAt": "…" }
                        Cheap. The client asks this first and stops there if
                        the revision matches what it already has.

     GET /v1/config     the whole payload. Honours If-None-Match and answers
                        304 when the client's ETag is current.

     GET /health        for whatever is watching the process.

   Run:  node Tools/api/server.mjs                  (port 8787)
         PORT=9000 node Tools/api/server.mjs
         node Tools/api/server.mjs --watch          (re-read on every request)

   No dependencies. Node 18+.

   BEFORE YOU PUT THIS ON THE INTERNET
   ---------------------------------------------------------------------------
   It is read-only and serves one file, which is most of what keeps it safe,
   but it terminates plain HTTP and knows nothing about TLS. iOS will not let
   a shipped app talk to it over plain HTTP without an ATS exception you do
   not want to ship. Put it behind a TLS terminator — any reverse proxy, or a
   platform that gives you HTTPS — and point the game at the https:// address.
   ========================================================================== */

import { createServer } from 'node:http';
import { readFileSync, existsSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const HERE = dirname(fileURLToPath(import.meta.url));
const CONFIG = resolve(HERE, '../../Content/Data/config.json');

const PORT = Number(process.env.PORT || 8787);
const HOST = process.env.HOST || '0.0.0.0';
const WATCH = process.argv.includes('--watch');

let cache = null;
function payload(){
  if(cache && !WATCH) return cache;
  if(!existsSync(CONFIG)){
    throw new Error('Content/Data/config.json is missing — run:\n' +
                    '  node Tools/export/export.mjs --api');
  }
  const raw = readFileSync(CONFIG, 'utf8');
  const body = JSON.parse(raw);
  cache = {
    raw,
    revision: body.Revision || createHash('sha256').update(raw).digest('hex').slice(0, 16),
    generatedAt: body.GeneratedAt || statSync(CONFIG).mtime.toISOString()
  };
  cache.etag = '"' + cache.revision + '"';
  return cache;
}

/* `head` travels with the request rather than sitting in a module variable:
   two requests in flight at once would otherwise decide each other's method. */
function send(res, code, body, headers = {}, head = false){
  const buf = Buffer.from(body);
  res.writeHead(code, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': buf.length,
    // The client is a game on someone's phone, not a browser, but a stray
    // browser hitting this should not be able to read it into a page.
    'access-control-allow-origin': '*',
    'cache-control': 'public, max-age=60',
    'x-content-type-options': 'nosniff',
    ...headers
  });
  res.end(head ? undefined : buf);
}

const server = createServer((req, res) => {
  const head = req.method === 'HEAD';
  if(req.method !== 'GET' && !head){
    return send(res, 405, JSON.stringify({ error: 'read only' }), { allow: 'GET, HEAD' });
  }
  const url = new URL(req.url, 'http://localhost');
  let p;
  try { p = payload(); }
  catch(e){
    console.error(e.message);
    return send(res, 503, JSON.stringify({ error: 'config not exported yet' }), {}, head);
  }

  switch(url.pathname){
    case '/health':
      return send(res, 200, JSON.stringify({ ok: true, revision: p.revision }), {}, head);

    case '/v1/revision':
      return send(res, 200, JSON.stringify({
        Revision: p.revision, GeneratedAt: p.generatedAt
      }), { etag: p.etag }, head);

    case '/v1/config': {
      const seen = req.headers['if-none-match'];
      if(seen && seen.split(',').some(t => t.trim() === p.etag)){
        res.writeHead(304, { etag: p.etag, 'cache-control': 'public, max-age=60' });
        return res.end();
      }
      return send(res, 200, p.raw, { etag: p.etag }, head);
    }

    default:
      return send(res, 404, JSON.stringify({
        error: 'not found',
        endpoints: ['/v1/revision', '/v1/config', '/health']
      }), {}, head);
  }
});

server.listen(PORT, HOST, () => {
  let rev = '(not exported yet)';
  try { rev = payload().revision; } catch(e){}
  console.log(`AHMED balance API on http://${HOST}:${PORT}`);
  console.log(`  revision ${rev}${WATCH ? '   [--watch: re-reads every request]' : ''}`);
  console.log('  GET /v1/revision   GET /v1/config   GET /health');
});
