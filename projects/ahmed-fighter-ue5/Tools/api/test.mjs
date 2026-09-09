/* The live API, end to end: starts the server on a free port against a copy
   of the payload and a scratch save store, and exercises every endpoint --
   including the WebSocket push when the payload on disk changes, which is the
   one thing here that cannot be checked by reading the code.
   Run:  node Tools/api/test.mjs   (needs Node 22 for the WebSocket client) */
import { spawn } from 'node:child_process';
import { mkdtempSync, copyFileSync, writeFileSync, readFileSync, rmSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const REAL = resolve(HERE, '../../Content/Data/config.json');
const tmp = mkdtempSync(join(tmpdir(), 'ahmed-api-'));
const CONFIG = join(tmp, 'config.json'), SAVES = join(tmp, 'saves');
copyFileSync(REAL, CONFIG);

let fails = 0, passes = 0;
const check = (ok, what) => { if(ok) passes++; else { fails++; console.log('  FAIL ' + what); } };
const sleep = ms => new Promise(r => setTimeout(r, ms));

const PORT = 18000 + Math.floor(Math.random() * 1000);
const BASE = `http://127.0.0.1:${PORT}`;
const server = spawn(process.execPath, [join(HERE, 'server.mjs')], {
  env: { ...process.env, PORT: String(PORT), HOST: '127.0.0.1', AHMED_CONFIG: CONFIG, AHMED_SAVES: SAVES, SAVE_TOKEN: 'sesame' },
  stdio: ['ignore', 'pipe', 'inherit']
});
let log = ''; server.stdout.on('data', d => { log += d; });
for(let i = 0; i < 50; i++){ await sleep(100); try { await fetch(BASE + '/health'); break; } catch(e){} }

try {
  // ---------------------------------------------------------------- balance
  console.log('BALANCE');
  let r = await fetch(BASE + '/health'); let j = await r.json();
  check(r.status === 200 && j.ok === true && /^[0-9a-f]{16}$/.test(j.revision), 'health carries the revision');
  const revision = j.revision;

  r = await fetch(BASE + '/v1/revision'); j = await r.json();
  check(j.Revision === revision && typeof j.GeneratedAt === 'string', '/v1/revision');
  check(r.headers.get('etag') === `"${revision}"`, 'revision ETag is the revision');

  r = await fetch(BASE + '/v1/config'); const cfg = await r.json();
  check(r.status === 200 && cfg.Revision === revision, '/v1/config is the payload');
  check(Array.isArray(cfg.Fighters) && cfg.Fighters.some(f => f.Name === 'Zayos'), 'the payload has the roster, ZAYOS included');
  check(Array.isArray(cfg.Colors) && cfg.Colors.length === 38, 'the payload carries the 38 colours (' + (cfg.Colors || []).length + ')');
  check(Array.isArray(cfg.Sounds) && cfg.Sounds.some(s => s.Name === 'Music_Under'), 'and the sound catalogue with the new music cues');
  r = await fetch(BASE + '/v1/config', { headers: { 'if-none-match': `"${revision}"` } });
  check(r.status === 304, 'a current ETag gets 304');
  r = await fetch(BASE + '/v1/config', { method: 'HEAD' });
  check(r.status === 200 && Number(r.headers.get('content-length')) > 1000, 'HEAD answers with the length and no body');

  r = await fetch(BASE + '/v1/tables'); j = await r.json();
  check(r.status === 200 && j.Tables.includes('Fighters') && j.Tables.includes('Colors') && j.Tables.includes('World'), '/v1/tables lists the tables: ' + j.Tables.join(','));
  r = await fetch(BASE + '/v1/tables/Fighters'); j = await r.json();
  check(r.status === 200 && j.Name === 'Fighters' && j.Rows.length === cfg.Fighters.length && j.Revision === revision, 'one table on its own');
  const tEtag = r.headers.get('etag');
  r = await fetch(BASE + '/v1/tables/Fighters', { headers: { 'if-none-match': tEtag } });
  check(r.status === 304, 'a table has its own ETag');
  r = await fetch(BASE + '/v1/tables/Nope'); j = await r.json();
  check(r.status === 404 && Array.isArray(j.tables), 'an unknown table is 404 and says what exists');
  r = await fetch(BASE + '/v1/config', { method: 'POST', body: '{}' });
  check(r.status === 405, 'the balance side is read only');
  r = await fetch(BASE + '/nope'); j = await r.json();
  check(r.status === 404 && j.endpoints.length >= 6, 'an unknown path lists the endpoints');

  // ------------------------------------------------------------------ saves
  console.log('SAVES');
  const auth = { authorization: 'Bearer sesame', 'content-type': 'application/json' };
  const save = { SchemaVersion: 1, Progress: { Experience: 1234, Abilities: ['Vault'], CurrentStage: 'BaytAlDarb' } };
  r = await fetch(BASE + '/v1/saves/player-1', { method: 'PUT', body: JSON.stringify(save) });
  check(r.status === 401 && r.headers.get('www-authenticate') === 'Bearer', 'no token, no save');
  r = await fetch(BASE + '/v1/saves/player-1', { headers: { authorization: 'Bearer sesame' } });
  check(r.status === 404, 'nothing stored yet is 404');
  r = await fetch(BASE + '/v1/saves/player-1', { method: 'PUT', headers: auth, body: JSON.stringify(save) }); j = await r.json();
  check(r.status === 201 && j.ok && j.id === 'player-1', 'first store is 201');
  r = await fetch(BASE + '/v1/saves/player-1', { headers: { authorization: 'Bearer sesame' } }); j = await r.json();
  check(r.status === 200 && j.Progress.Experience === 1234 && j.Progress.Abilities[0] === 'Vault', 'and it comes back byte for byte');
  const sEtag = r.headers.get('etag');
  r = await fetch(BASE + '/v1/saves/player-1', { headers: { authorization: 'Bearer sesame', 'if-none-match': sEtag } });
  check(r.status === 304, 'a save has an ETag too');
  save.Progress.Experience = 2000;
  r = await fetch(BASE + '/v1/saves/player-1', { method: 'PUT', headers: auth, body: JSON.stringify(save) });
  check(r.status === 200, 'a second store is 200');
  r = await fetch(BASE + '/v1/saves/player-1', { headers: { authorization: 'Bearer sesame' } }); j = await r.json();
  check(j.Progress.Experience === 2000, 'and replaces the first');
  r = await fetch(BASE + '/v1/saves/player-1', { method: 'PUT', headers: auth, body: '{"hello":1}' });
  check(r.status === 422, 'a body that is not a save is refused (422)');
  r = await fetch(BASE + '/v1/saves/player-1', { method: 'PUT', headers: auth, body: 'not json' });
  check(r.status === 422, 'so is junk');
  r = await fetch(BASE + '/v1/saves/player-1', { method: 'PUT', headers: auth, body: JSON.stringify({ SchemaVersion: 1, Progress: { pad: 'x'.repeat(300 * 1024) } }) });
  check(r.status === 413, 'and anything over 256 KB (' + r.status + ')');
  r = await fetch(BASE + '/v1/saves/player-1', { headers: { authorization: 'Bearer sesame' } }); j = await r.json();
  check(j.Progress.Experience === 2000, 'a refused store changes nothing');
  r = await fetch(BASE + '/v1/saves/..%2Fescape', { method: 'PUT', headers: auth, body: JSON.stringify(save) });
  check(r.status === 400 || r.status === 404, 'a save id cannot leave the store (' + r.status + ')');
  r = await fetch(BASE + '/v1/saves/' + 'a'.repeat(65), { method: 'PUT', headers: auth, body: JSON.stringify(save) });
  check(r.status === 400, 'or be longer than 64');
  r = await fetch(BASE + '/v1/saves/player-1', { method: 'DELETE', headers: auth });
  check(r.status === 204, 'delete is 204');
  r = await fetch(BASE + '/v1/saves/player-1', { headers: { authorization: 'Bearer sesame' } });
  check(r.status === 404, 'and it is gone');

  // ------------------------------------------------------------------- live
  console.log('LIVE');
  const msgs = [];
  const ws = new WebSocket(`ws://127.0.0.1:${PORT}/v1/live`);
  await new Promise((ok, fail) => { ws.onopen = ok; ws.onerror = e => fail(new Error('ws failed to open')); });
  ws.onmessage = e => msgs.push(JSON.parse(e.data));
  await sleep(200);
  check(msgs.length === 1 && msgs[0].Type === 'hello' && msgs[0].Revision === revision, 'the server says hello with its revision');
  ws.send(JSON.stringify({ Type: 'ping' }));
  await sleep(200);
  check(msgs.length === 2 && msgs[1].Type === 'pong' && msgs[1].Revision === revision, 'a ping gets a pong');
  r = await fetch(BASE + '/health'); j = await r.json();
  check(j.live === 1, 'health counts the live client');

  // The push: rewrite the payload with a different revision, as the exporter would.
  const body = JSON.parse(readFileSync(CONFIG, 'utf8'));
  body.Revision = 'feedfacefeedface';
  body.Fighters[0].MaxHealth = 999;
  writeFileSync(CONFIG, JSON.stringify(body, null, 2) + '\n');
  for(let i = 0; i < 40 && msgs.length < 3; i++) await sleep(100);
  check(msgs.length === 3 && msgs[2].Type === 'revision' && msgs[2].Revision === 'feedfacefeedface', 'a changed payload on disk is pushed to the client');
  r = await fetch(BASE + '/v1/revision'); j = await r.json();
  check(j.Revision === 'feedfacefeedface', 'and the HTTP side serves the new revision without a restart');
  r = await fetch(BASE + '/v1/tables/Fighters'); j = await r.json();
  check(j.Rows[0].MaxHealth === 999, 'with the new numbers');

  // A second client, and closing.
  const ws2 = new WebSocket(`ws://127.0.0.1:${PORT}/v1/live`);
  await new Promise(ok => { ws2.onopen = ok; });
  await sleep(150);
  r = await fetch(BASE + '/health'); j = await r.json();
  check(j.live === 2, 'two clients');
  ws2.close();
  await sleep(200);
  r = await fetch(BASE + '/health'); j = await r.json();
  check(j.live === 1, 'a closed client is forgotten');
  const wsBad = new WebSocket(`ws://127.0.0.1:${PORT}/v1/nope`);
  const badResult = await new Promise(ok => { wsBad.onerror = () => ok('error'); wsBad.onopen = () => ok('open'); });
  check(badResult === 'error', 'an upgrade on any other path is refused');
  ws.close();
} finally {
  server.kill('SIGTERM');
  await sleep(300);
  rmSync(tmp, { recursive: true, force: true });
}
console.log(`\n${passes} passed, ${fails} failed`);
process.exit(fails ? 1 : 0);
