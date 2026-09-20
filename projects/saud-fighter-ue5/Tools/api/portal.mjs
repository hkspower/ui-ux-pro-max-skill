/* SAUD — Kuwait Fighter :: the backend portal
   ==========================================================================
   A person's way into the live API. The game talks to `/v1/*` with a bearer
   token; this is the other audience -- someone who wants to SEE what the
   backend is holding: which revision is live, what is in the tables, which
   profiles have been saved, how many games are listening on the socket.

   It is a SEPARATE AUTH REALM from the game's, on purpose and without
   exception:

     /v1/*        SAVE_TOKEN, a bearer header. Unchanged by this file.
     /portal/*    a login, a session cookie and a CSRF token. Nothing here
                  accepts SAVE_TOKEN, and nothing in /v1 accepts a session.

   That separation is the whole security argument. A portal session is a
   person at a keyboard and is allowed to browse and delete saves; a bearer
   token is a shipped game binary and is allowed to read and write its own.
   Neither can be spent as the other, so adding this file cannot widen what
   the game-facing API already grants.

   HOW A LOGIN IS CHECKED

     PORTAL_USER            the one account. No account, no portal.
     PORTAL_PASSWORD_HASH   scrypt$<salt b64>$<hash b64> -- what to use.
     PORTAL_PASSWORD        plain, for a laptop. Works; says so in the log.

   With neither set the portal is OFF and every route under it answers 503
   saying how to turn it on. There is deliberately no default password: a
   backend that ships with one is a backend anyone can open.

   Mint a hash without putting the password in your shell history or in the
   process list (argv is world-readable on most systems -- this reads stdin):

     node Tools/api/portal.mjs --hash

   WHAT IS DEFENDED, AND HOW

     guessing         per-IP rate limit, then 429 -- a lockout, so the right
                      password is refused too while it holds. The IP is the
                      socket's; X-Forwarded-For is only believed when
                      PORTAL_TRUST_PROXY=1, because a header anyone can set
                      is a rate limiter anyone can step around. The password
                      KDF runs even when the username is wrong, so a bad user
                      and a bad password take the same time and neither
                      enumerates.
     stolen cookie    HttpOnly (no script can read it), SameSite=Strict,
                      Secure unless PORTAL_INSECURE_COOKIE=1, Path=/portal.
                      Idle timeout and an absolute lifetime, both enforced
                      server-side; the cookie is a random 256-bit id and
                      carries no claims of its own.
     session fixation a new id is minted on every successful login.
     CSRF             SameSite=Strict, and on top of it every write carries
                      x-csrf-token from the session. Belt and braces, because
                      a cookie is ambient and a mistake here deletes saves.
     clickjacking     frame-ancestors 'none' and X-Frame-Options: DENY.
     injected script  a per-response CSP nonce; the page's own script and
                      style carry it and nothing else may run.
     timing           timingSafeEqual for the user, the password and the
                      CSRF token.

   STILL NOT THIS FILE'S JOB: TLS. The server terminates plain HTTP and says
   so. Behind a terminator the Secure cookie is correct; in front of one, a
   session id crosses the wire in clear. Put it behind TLS.
   ========================================================================== */

import { randomBytes, scryptSync, timingSafeEqual, createHash } from 'node:crypto';
import { readFileSync, existsSync, statSync, unlinkSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const USER = process.env.PORTAL_USER || '';
const PASSWORD = process.env.PORTAL_PASSWORD || '';
const PASSWORD_HASH = process.env.PORTAL_PASSWORD_HASH || '';
const INSECURE_COOKIE = process.env.PORTAL_INSECURE_COOKIE === '1';
// Only set this where a reverse proxy you control is writing X-Forwarded-For.
const TRUST_PROXY = process.env.PORTAL_TRUST_PROXY === '1';
const SESSION_HOURS = Number(process.env.PORTAL_SESSION_HOURS || 12);
const IDLE_MINUTES = Number(process.env.PORTAL_IDLE_MINUTES || 60);

const COOKIE = 'saud_portal';
const ATTEMPT_WINDOW_MS = 15 * 60 * 1000;
const ATTEMPT_LIMIT = 10;
const SCRYPT_KEYLEN = 32;

export const portalEnabled = () => !!USER && (!!PASSWORD || !!PASSWORD_HASH);

export function portalStatusLine(){
  if(!portalEnabled()) return '  portal OFF — set PORTAL_USER and PORTAL_PASSWORD_HASH to open /portal';
  const how = PASSWORD_HASH ? 'scrypt hash' : 'PLAIN PASSWORD — development only';
  return `  portal on /portal as "${USER}"  (${how})`;
}

/* ------------------------------------------------------------- passwords */
/* scrypt with the defaults Node ships: fine for one operator account behind
   a rate limiter, and no dependency to pull in. */
function hashPassword(plain, salt = randomBytes(16)){
  const key = scryptSync(plain, salt, SCRYPT_KEYLEN);
  return { salt, key };
}

export function mintHash(plain){
  const { salt, key } = hashPassword(plain);
  return `scrypt$${salt.toString('base64')}$${key.toString('base64')}`;
}

/** Same length or not, same time either way. */
function sameSecret(a, b){
  const A = Buffer.from(String(a), 'utf8'), B = Buffer.from(String(b), 'utf8');
  // timingSafeEqual throws on a length mismatch, which is itself a leak, so
  // both sides are hashed to a fixed width first.
  const ha = createHash('sha256').update(A).digest();
  const hb = createHash('sha256').update(B).digest();
  return timingSafeEqual(ha, hb);
}

/** True if `plain` is the configured password. Always does the work. */
function passwordMatches(plain){
  if(PASSWORD_HASH){
    const parts = PASSWORD_HASH.split('$');
    if(parts.length !== 3 || parts[0] !== 'scrypt'){
      // Misconfigured rather than wrong: still burn the time, still refuse.
      hashPassword(plain);
      return false;
    }
    const salt = Buffer.from(parts[1], 'base64');
    const want = Buffer.from(parts[2], 'base64');
    const got = scryptSync(plain, salt, want.length || SCRYPT_KEYLEN);
    return want.length === got.length && timingSafeEqual(want, got);
  }
  // Plain: still hash something first so this path is not measurably faster
  // than the hashed one when someone is probing which is configured.
  hashPassword(plain);
  return sameSecret(plain, PASSWORD);
}

/* -------------------------------------------------------------- sessions */
const sessions = new Map();     // id -> { user, created, lastSeen, csrf }
const attempts = new Map();     // ip -> { count, first }

function prune(){
  const now = Date.now();
  const absolute = SESSION_HOURS * 3600 * 1000;
  const idle = IDLE_MINUTES * 60 * 1000;
  for(const [id, s] of sessions){
    if(now - s.created > absolute || now - s.lastSeen > idle) sessions.delete(id);
  }
  for(const [ip, a] of attempts){
    if(now - a.first > ATTEMPT_WINDOW_MS) attempts.delete(ip);
  }
}

function newSession(user){
  const id = randomBytes(32).toString('base64url');
  const now = Date.now();
  sessions.set(id, { user, created: now, lastSeen: now, csrf: randomBytes(32).toString('base64url') });
  return id;
}

function cookies(req){
  const out = {};
  for(const part of (req.headers.cookie || '').split(';')){
    const i = part.indexOf('=');
    if(i < 0) continue;
    out[part.slice(0, i).trim()] = decodeURIComponent(part.slice(i + 1).trim());
  }
  return out;
}

/** The live session for this request, or null. Touches lastSeen. */
function sessionOf(req){
  prune();
  const id = cookies(req)[COOKIE];
  if(!id) return null;
  const s = sessions.get(id);
  if(!s) return null;
  s.lastSeen = Date.now();
  return { id, ...s };
}

function setCookie(id){
  const bits = [`${COOKIE}=${id}`, 'HttpOnly', 'SameSite=Strict', 'Path=/portal',
                `Max-Age=${SESSION_HOURS * 3600}`];
  if(!INSECURE_COOKIE) bits.push('Secure');
  return bits.join('; ');
}
const clearCookie = () =>
  `${COOKIE}=; HttpOnly; SameSite=Strict; Path=/portal; Max-Age=0` + (INSECURE_COOKIE ? '' : '; Secure');

function clientIp(req){
  // X-Forwarded-For is a header, and a header is whatever the client typed.
  // Trusting it by default would hand an attacker the rate limiter: a new
  // value per request is a fresh allowance, and the lockout never fires. So
  // the socket is the default and the header is only read when something in
  // front is known to be setting it.
  if(TRUST_PROXY){
    const fwd = (req.headers['x-forwarded-for'] || '').split(',')[0].trim();
    if(fwd) return fwd;
  }
  return req.socket.remoteAddress || 'unknown';
}

function rateLimited(ip){
  prune();
  const a = attempts.get(ip);
  return !!a && a.count >= ATTEMPT_LIMIT;
}
function recordAttempt(ip, ok){
  if(ok){ attempts.delete(ip); return; }
  const now = Date.now();
  const a = attempts.get(ip);
  if(!a || now - a.first > ATTEMPT_WINDOW_MS) attempts.set(ip, { count: 1, first: now });
  else a.count++;
}

/* ------------------------------------------------------------------ http */
function reply(res, code, body, headers = {}){
  const buf = Buffer.from(body);
  res.writeHead(code, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': buf.length,
    'cache-control': 'no-store',
    'x-content-type-options': 'nosniff',
    'x-frame-options': 'DENY',
    'referrer-policy': 'no-referrer',
    ...headers
  });
  res.end(buf);
}
const jsonReply = (res, code, o, headers) => reply(res, code, JSON.stringify(o), headers);

async function readJson(req, limit = 8 * 1024){
  const chunks = [];
  let size = 0, over = false;
  for await (const c of req){
    if(over) continue;
    size += c.length;
    if(size > limit){ over = true; continue; }
    chunks.push(c);
  }
  if(over) throw new Error('too large');
  try { return JSON.parse(Buffer.concat(chunks).toString('utf8')); }
  catch(e){ throw new Error('not JSON'); }
}

/* --------------------------------------------------------------- the page */
function page(nonce){
  // One document, no build step, no CDN -- the same rule the rest of this
  // folder keeps. Colours are the game's own scheme (assets/colors.js).
  return `<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SAUD — backend</title>
<style nonce="${nonce}">
  :root{
    --ink0:#05070b; --ink1:#0b101a; --ink2:#151b28; --ink3:#1e2534;
    --fg:#f4f1e8; --muted:rgba(244,241,232,.62); --faint:rgba(244,241,232,.32);
    --gold:#edbe57; --red:#c8102e; --green:#37c26b; --crit:#e2413f;
    --line:rgba(237,190,87,.20); --soft:rgba(255,255,255,.07);
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--ink0);color:var(--fg);
       font:15px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
  header{display:flex;align-items:center;gap:12px;padding:16px 20px;
         border-bottom:1px solid var(--line);background:var(--ink1)}
  header h1{margin:0;font-size:15px;letter-spacing:.14em;text-transform:uppercase}
  header .rev{margin-left:auto;color:var(--muted);font:12px/1 ui-monospace,SFMono-Regular,Menlo,monospace}
  main{max-width:1100px;margin:0 auto;padding:20px}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:22px}
  .card{background:var(--ink2);border:1px solid var(--soft);border-radius:10px;padding:14px}
  .card b{display:block;font-size:22px;font-weight:700;margin-bottom:2px}
  .card span{color:var(--muted);font-size:12px;letter-spacing:.06em;text-transform:uppercase}
  h2{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);
     margin:26px 0 10px;font-weight:700}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--soft)}
  th{color:var(--muted);font-weight:600;font-size:11px;letter-spacing:.08em;text-transform:uppercase}
  td.num{font:12px/1 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted)}
  button{font:inherit;cursor:pointer;border-radius:8px;border:1px solid var(--line);
         background:transparent;color:var(--gold);padding:6px 12px}
  button:hover{background:rgba(237,190,87,.10)}
  button.danger{color:var(--crit);border-color:rgba(226,65,63,.35)}
  button.danger:hover{background:rgba(226,65,63,.12)}
  button.primary{background:var(--gold);color:#1a1405;border-color:var(--gold);font-weight:700}
  #login{max-width:340px;margin:12vh auto;background:var(--ink2);
         border:1px solid var(--soft);border-radius:12px;padding:24px}
  #login h1{font-size:13px;letter-spacing:.16em;text-transform:uppercase;margin:0 0 4px}
  #login p{color:var(--muted);font-size:13px;margin:0 0 18px}
  label{display:block;font-size:11px;letter-spacing:.08em;text-transform:uppercase;
        color:var(--muted);margin:12px 0 5px}
  input{width:100%;padding:9px 11px;border-radius:8px;border:1px solid var(--soft);
        background:var(--ink1);color:var(--fg);font:inherit}
  input:focus{outline:2px solid var(--line);outline-offset:1px}
  #login button{width:100%;margin-top:18px;padding:10px}
  .err{color:var(--crit);font-size:13px;min-height:20px;margin-top:10px}
  pre{background:var(--ink1);border:1px solid var(--soft);border-radius:8px;
      padding:12px;overflow:auto;max-height:420px;font-size:12px;color:var(--muted)}
  .row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
  .hidden{display:none}
  /* The script may not write style="" -- style-src is a nonce and nothing
     else, on purpose -- so anything it colours needs a class here. */
  .count{color:var(--faint)}
  .empty{color:var(--faint)}
  @media (max-width:560px){ main{padding:14px} header{padding:14px} }
</style>
</head><body>

<div id="login">
  <h1>SAUD backend</h1>
  <p>Sign in to see what the live API is holding.</p>
  <form id="loginForm" autocomplete="on">
    <label for="u">User</label>
    <input id="u" name="username" autocomplete="username" autocapitalize="none" spellcheck="false" required>
    <label for="p">Password</label>
    <input id="p" name="password" type="password" autocomplete="current-password" required>
    <button class="primary" type="submit">Sign in</button>
  </form>
  <div class="err" id="loginErr" role="alert" aria-live="polite"></div>
</div>

<div id="app" class="hidden">
  <header>
    <h1>SAUD backend</h1>
    <span class="rev" id="rev"></span>
    <button id="logout">Sign out</button>
  </header>
  <main>
    <div class="cards" id="cards"></div>

    <h2>Tables</h2>
    <div class="row" id="tables"></div>
    <pre id="tableOut" class="hidden"></pre>

    <h2>Saves</h2>
    <table><thead><tr><th>Profile</th><th>Size</th><th>Changed</th><th></th></tr></thead>
    <tbody id="saves"></tbody></table>
    <pre id="saveOut" class="hidden"></pre>
  </main>
</div>

<script nonce="${nonce}">
const $ = s => document.querySelector(s);
let csrf = '';

async function api(path, opts = {}){
  const o = { credentials: 'same-origin', headers: {}, ...opts };
  if(o.method && o.method !== 'GET') o.headers['x-csrf-token'] = csrf;
  const r = await fetch('/portal/api' + path, o);
  if(r.status === 401){ show(false); throw new Error('signed out'); }
  return r;
}
const esc = s => String(s).replace(/[&<>"']/g, c =>
  ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));

function show(in_){
  $('#login').classList.toggle('hidden', in_);
  $('#app').classList.toggle('hidden', !in_);
}

$('#loginForm').addEventListener('submit', async e => {
  e.preventDefault();
  $('#loginErr').textContent = '';
  const r = await fetch('/portal/login', {
    method: 'POST', credentials: 'same-origin',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ user: $('#u').value, password: $('#p').value })
  });
  const j = await r.json().catch(() => ({}));
  if(!r.ok){ $('#loginErr').textContent = j.error || 'Sign-in failed'; return; }
  $('#p').value = '';
  await start();
});

$('#logout').addEventListener('click', async () => {
  await fetch('/portal/logout', {
    method: 'POST', credentials: 'same-origin', headers: { 'x-csrf-token': csrf }
  }).catch(() => {});
  csrf = ''; show(false);
});

async function start(){
  const s = await (await api('/session')).json();
  csrf = s.csrf;
  show(true);
  await overview();
}

async function overview(){
  const o = await (await api('/overview')).json();
  $('#rev').textContent = 'revision ' + o.revision + ' · ' + o.generatedAt;
  $('#cards').innerHTML = [
    ['Tables', o.tables.length], ['Saves', o.saves],
    ['Games listening', o.live], ['Payload', (o.bytes / 1024).toFixed(0) + ' KB']
  ].map(([k, v]) => '<div class="card"><b>' + esc(v) + '</b><span>' + esc(k) + '</span></div>').join('');

  $('#tables').innerHTML = o.tables
    .map(t => '<button data-table="' + esc(t.name) + '">' + esc(t.name) +
              ' <span class="count">' + esc(t.rows) + '</span></button>').join('');
  for(const b of document.querySelectorAll('#tables button')){
    b.addEventListener('click', async () => {
      const j = await (await api('/tables/' + encodeURIComponent(b.dataset.table))).json();
      const out = $('#tableOut');
      out.textContent = JSON.stringify(j.Rows, null, 2);
      out.classList.remove('hidden');
    });
  }

  const rows = o.saveList.map(s =>
    '<tr><td>' + esc(s.id) + '</td><td class="num">' + esc(s.bytes) +
    '</td><td class="num">' + esc(s.modified) + '</td><td class="row">' +
    '<button data-view="' + esc(s.id) + '">View</button>' +
    '<button class="danger" data-del="' + esc(s.id) + '">Delete</button></td></tr>').join('');
  $('#saves').innerHTML = rows || '<tr><td colspan="4" class="empty">No profiles stored.</td></tr>';

  for(const b of document.querySelectorAll('[data-view]')){
    b.addEventListener('click', async () => {
      const j = await (await api('/saves/' + encodeURIComponent(b.dataset.view))).json();
      const out = $('#saveOut');
      out.textContent = JSON.stringify(j, null, 2);
      out.classList.remove('hidden');
    });
  }
  for(const b of document.querySelectorAll('[data-del]')){
    b.addEventListener('click', async () => {
      if(!confirm('Delete profile "' + b.dataset.del + '"? This cannot be undone.')) return;
      await api('/saves/' + encodeURIComponent(b.dataset.del), { method: 'DELETE' });
      $('#saveOut').classList.add('hidden');
      await overview();
    });
  }
}

// An existing cookie means straight in.
start().catch(() => show(false));
</script>
</body></html>
`;
}

/* ------------------------------------------------------------- the routes */
/**
 * Handles anything under /portal. Returns true if it answered.
 * `ctx` is what the server owns: { payload, reload, sockets, savesDir,
 * saveTokenSet, startedAt }.
 */
export async function handlePortal(req, res, ctx){
  const path = new URL(req.url, 'http://localhost').pathname.replace(/\/+$/, '') || '/portal';
  if(path !== '/portal' && !path.startsWith('/portal/')) return false;

  if(!portalEnabled()){
    jsonReply(res, 503, {
      error: 'portal is not configured',
      how: 'set PORTAL_USER and PORTAL_PASSWORD_HASH (node Tools/api/portal.mjs --hash) and restart'
    });
    return true;
  }

  // ---- the page itself
  if(path === '/portal' && (req.method === 'GET' || req.method === 'HEAD')){
    const nonce = randomBytes(16).toString('base64');
    const body = page(nonce);
    const buf = Buffer.from(body);
    res.writeHead(200, {
      'content-type': 'text/html; charset=utf-8',
      'content-length': buf.length,
      'cache-control': 'no-store',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'DENY',
      'referrer-policy': 'no-referrer',
      'content-security-policy':
        "default-src 'none'; " +
        `script-src 'nonce-${nonce}'; style-src 'nonce-${nonce}'; ` +
        "connect-src 'self'; form-action 'none'; base-uri 'none'; frame-ancestors 'none'"
    });
    res.end(req.method === 'HEAD' ? undefined : buf);
    return true;
  }

  // ---- login
  if(path === '/portal/login'){
    if(req.method !== 'POST'){ jsonReply(res, 405, { error: 'POST' }, { allow: 'POST' }); return true; }
    const ip = clientIp(req);
    if(rateLimited(ip)){
      jsonReply(res, 429, { error: 'too many attempts — wait a few minutes' }, { 'retry-after': '900' });
      return true;
    }
    let body;
    try { body = await readJson(req); }
    catch(e){ recordAttempt(ip, false); jsonReply(res, 400, { error: 'expected JSON' }); return true; }

    const user = typeof body.user === 'string' ? body.user : '';
    const pass = typeof body.password === 'string' ? body.password : '';
    // Both checks always run: a wrong user must not be quicker than a wrong
    // password, or the pair tells an attacker which half to keep.
    const userOk = sameSecret(user, USER);
    const passOk = passwordMatches(pass);
    const ok = userOk && passOk;
    recordAttempt(ip, ok);
    if(!ok){
      jsonReply(res, 401, { error: 'wrong user or password' });
      return true;
    }
    const id = newSession(USER);      // fresh id: no fixation
    jsonReply(res, 200, { ok: true, user: USER }, { 'set-cookie': setCookie(id) });
    return true;
  }

  // ---- everything past here needs a session
  const session = sessionOf(req);
  if(path === '/portal/logout'){
    if(session) sessions.delete(session.id);
    jsonReply(res, 200, { ok: true }, { 'set-cookie': clearCookie() });
    return true;
  }
  if(!session){
    jsonReply(res, 401, { error: 'sign in' }, { 'set-cookie': clearCookie() });
    return true;
  }

  const writing = req.method !== 'GET' && req.method !== 'HEAD';
  if(writing && !sameSecret(req.headers['x-csrf-token'] || '', session.csrf)){
    jsonReply(res, 403, { error: 'bad CSRF token' });
    return true;
  }

  if(path === '/portal/api/session'){
    jsonReply(res, 200, {
      user: session.user, csrf: session.csrf,
      expiresAt: new Date(session.created + SESSION_HOURS * 3600 * 1000).toISOString()
    });
    return true;
  }

  if(path === '/portal/api/overview'){
    let p = null;
    try { p = ctx.payload(); } catch(e){ /* not exported yet */ }
    const saveList = listSaves(ctx.savesDir);
    jsonReply(res, 200, {
      revision: p ? p.revision : null,
      generatedAt: p ? p.generatedAt : null,
      bytes: p ? Buffer.byteLength(p.raw) : 0,
      tables: p ? Object.entries(p.tables).map(([name, rows]) =>
        ({ name, rows: Array.isArray(rows) ? rows.length : Object.keys(rows).length })) : [],
      live: ctx.sockets.size,
      saves: saveList.length,
      saveList,
      saveTokenSet: ctx.saveTokenSet,
      startedAt: ctx.startedAt
    });
    return true;
  }

  let m = path.match(/^\/portal\/api\/tables\/([A-Za-z]+)$/);
  if(m){
    let p;
    try { p = ctx.payload(); }
    catch(e){ jsonReply(res, 503, { error: 'config not exported yet' }); return true; }
    const rows = p.tables[m[1]];
    if(rows === undefined){ jsonReply(res, 404, { error: 'no such table' }); return true; }
    jsonReply(res, 200, { Name: m[1], Revision: p.revision, Rows: rows });
    return true;
  }

  if(path === '/portal/api/saves'){
    jsonReply(res, 200, { saves: listSaves(ctx.savesDir) });
    return true;
  }

  m = path.match(/^\/portal\/api\/saves\/([^/]+)$/);
  if(m){
    const id = m[1];
    if(!/^[A-Za-z0-9_-]{1,64}$/.test(id)){ jsonReply(res, 400, { error: 'bad save id' }); return true; }
    const file = join(ctx.savesDir, id + '.json');
    if(req.method === 'GET'){
      if(!existsSync(file)){ jsonReply(res, 404, { error: 'no save' }); return true; }
      reply(res, 200, readFileSync(file, 'utf8'));
      return true;
    }
    if(req.method === 'DELETE'){
      if(existsSync(file)) unlinkSync(file);
      jsonReply(res, 200, { ok: true, id });
      return true;
    }
    jsonReply(res, 405, { error: 'GET or DELETE' }, { allow: 'GET, DELETE' });
    return true;
  }

  if(path === '/portal/api/reload'){
    if(req.method !== 'POST'){ jsonReply(res, 405, { error: 'POST' }, { allow: 'POST' }); return true; }
    try {
      const was = ctx.revision();
      const now = ctx.reload().revision;
      if(now !== was) ctx.broadcast({ Type: 'revision', Revision: now });
      jsonReply(res, 200, { ok: true, revision: now, changed: now !== was });
    } catch(e){
      jsonReply(res, 503, { error: 'config not exported yet' });
    }
    return true;
  }

  jsonReply(res, 404, { error: 'not found' });
  return true;
}

function listSaves(dir){
  if(!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter(f => f.endsWith('.json'))
    .map(f => {
      const s = statSync(join(dir, f));
      return { id: f.slice(0, -5), bytes: s.size, modified: s.mtime.toISOString() };
    })
    .sort((a, b) => b.modified.localeCompare(a.modified));
}

/* ------------------------------------------------------ node portal --hash */
const runAsScript = process.argv[1] && process.argv[1].replace(/\\/g, '/').split('/').pop() === 'portal.mjs';
if(runAsScript && process.argv.includes('--hash')){
  process.stderr.write('password (not echoed to argv or history): ');
  let input = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', d => { input += d; });
  process.stdin.on('end', () => {
    const plain = input.replace(/\r?\n$/, '');
    if(!plain){ process.stderr.write('\nnothing read on stdin\n'); process.exit(1); }
    process.stderr.write('\n');
    console.log('PORTAL_PASSWORD_HASH=' + mintHash(plain));
  });
}
