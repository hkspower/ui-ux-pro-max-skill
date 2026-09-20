/* The backend portal, end to end. Starts the server on a free port with a
   portal account configured, against a copy of the payload and a scratch save
   store, and exercises the login, the session, the CSRF rule, the data it
   serves and -- the part that matters most -- everything it must REFUSE.

   The refusals are the point. This is the one file in the project that stands
   between the internet and a delete button, so each test below names what it
   would mean if it failed.

   Run:  node Tools/api/test-portal.mjs                                     */
import { spawn } from 'node:child_process';
import { mkdtempSync, copyFileSync, writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const REAL = resolve(HERE, '../../Content/Data/config.json');
const tmp = mkdtempSync(join(tmpdir(), 'saud-portal-'));
const CONFIG = join(tmp, 'config.json'), SAVES = join(tmp, 'saves');
copyFileSync(REAL, CONFIG);
mkdirSync(SAVES, { recursive: true });
writeFileSync(join(SAVES, 'kuwait.json'),
  JSON.stringify({ SchemaVersion: 1, Progress: { Experience: 4200, CurrentStage: 'AlHilal' } }));

let fails = 0, passes = 0;
const check = (ok, what) => { if(ok) passes++; else { fails++; console.log('  FAIL ' + what); } };
const sleep = ms => new Promise(r => setTimeout(r, ms));

const USER = 'almuhallab';
const PASS = 'a-long-enough-passphrase-for-a-test';
const PORT = 19000 + Math.floor(Math.random() * 900);
const BASE = `http://127.0.0.1:${PORT}`;

const server = spawn(process.execPath, [join(HERE, 'server.mjs')], {
  env: { ...process.env, PORT: String(PORT), HOST: '127.0.0.1',
         SAUD_CONFIG: CONFIG, SAUD_SAVES: SAVES, SAVE_TOKEN: 'sesame',
         PORTAL_USER: USER, PORTAL_PASSWORD: PASS, PORTAL_INSECURE_COOKIE: '1' },
  stdio: ['ignore', 'pipe', 'inherit']
});
let log = ''; server.stdout.on('data', d => { log += d; });
for(let i = 0; i < 60; i++){ await sleep(100); try { await fetch(BASE + '/health'); break; } catch(e){} }

/* A browser keeps cookies; fetch does not, so this does. */
let cookie = '';
function keep(r){
  const set = r.headers.getSetCookie ? r.headers.getSetCookie() : [r.headers.get('set-cookie')].filter(Boolean);
  for(const c of set){
    const [pair] = c.split(';');
    const [k, v] = pair.split('=');
    if(k.trim() === 'saud_portal') cookie = v === '' ? '' : `saud_portal=${v}`;
  }
  return r;
}
const withCookie = (extra = {}) => cookie ? { ...extra, cookie } : extra;

try {
  // ------------------------------------------------------------- the page
  console.log('THE PAGE');
  let r = await fetch(BASE + '/portal');
  const html = await r.text();
  check(r.status === 200 && r.headers.get('content-type').startsWith('text/html'), 'GET /portal serves the page');
  check(/nonce="[A-Za-z0-9+/=]{16,}"/.test(html), 'its script and style carry a nonce');
  const csp = r.headers.get('content-security-policy') || '';
  check(csp.includes("default-src 'none'") && csp.includes("frame-ancestors 'none'"),
        'and a CSP that denies everything it did not ask for');
  check(r.headers.get('x-frame-options') === 'DENY', 'X-Frame-Options: DENY — it cannot be framed');
  check(!html.includes(PASS), 'the page does not carry the password');
  // Found by pointing a real browser at it: the script wrote style="" into
  // the rows it built, and the CSP above -- correctly -- refused every one.
  // The page's own CSP is only worth having if the page keeps it, and no
  // HTTP test notices a blocked style, so this is the cheap standing check.
  const body = html.slice(html.indexOf('</style>'));
  check(!/\sstyle="/.test(body),
        'nothing on the page carries an inline style="" — style-src is a nonce and nothing else');
  check(/<script nonce="/.test(html) && !/<script(?![^>]*nonce)/.test(html),
        'every script tag carries the nonce');

  // ------------------------------------------------------------ refusals
  console.log('\nWHAT IT REFUSES');
  r = await fetch(BASE + '/portal/api/overview');
  check(r.status === 401, 'no cookie, no overview — the data needs a session');

  r = await fetch(BASE + '/portal/api/saves/kuwait', { method: 'DELETE' });
  check(r.status === 401, 'no cookie, no delete');

  // The game's own credential must not open the portal.
  r = await fetch(BASE + '/portal/api/overview', { headers: { authorization: 'Bearer sesame' } });
  check(r.status === 401, 'SAVE_TOKEN does not open the portal — the two realms are separate');

  r = await keep(await fetch(BASE + '/portal/login', {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ user: USER, password: 'wrong' })
  }));
  check(r.status === 401 && !cookie, 'a wrong password is 401 and sets no cookie');

  r = await fetch(BASE + '/portal/login', {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ user: 'someone-else', password: PASS })
  });
  const wrongUser = await r.json();
  check(r.status === 401 && !/user/i.test(wrongUser.error.replace('wrong user or password', '')),
        'a wrong user says the same thing as a wrong password — no enumeration');

  r = await fetch(BASE + '/portal/login', { method: 'GET' });
  check(r.status === 405, 'login is POST only');

  r = await fetch(BASE + '/portal/login', {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: 'not json at all'
  });
  check(r.status === 400, 'a body that is not JSON is 400, not a crash');

  // ---------------------------------------------------------------- login
  console.log('\nSIGNING IN');
  r = await keep(await fetch(BASE + '/portal/login', {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ user: USER, password: PASS })
  }));
  const loggedIn = await r.json();
  check(r.status === 200 && loggedIn.ok === true, 'the right pair signs in');
  check(!!cookie, 'and sets a session cookie');
  const rawCookie = (r.headers.getSetCookie ? r.headers.getSetCookie() : [r.headers.get('set-cookie')]).join(';');
  check(/HttpOnly/i.test(rawCookie), 'the cookie is HttpOnly — no script can read it');
  check(/SameSite=Strict/i.test(rawCookie), 'and SameSite=Strict');
  check(/Path=\/portal/i.test(rawCookie), 'and scoped to /portal');
  check(!/\bSecure\b/i.test(rawCookie), 'Secure is off only because PORTAL_INSECURE_COOKIE=1 was set');

  r = await fetch(BASE + '/portal/api/session', { headers: withCookie() });
  const session = await r.json();
  check(r.status === 200 && session.user === USER && typeof session.csrf === 'string' && session.csrf.length > 20,
        'the session says who you are and hands over a CSRF token');
  check(!('password' in session) && !JSON.stringify(session).includes(PASS), 'and never the password');
  const csrf = session.csrf;

  // ----------------------------------------------------------------- CSRF
  console.log('\nCSRF');
  r = await fetch(BASE + '/portal/api/saves/kuwait', { method: 'DELETE', headers: withCookie() });
  check(r.status === 403, 'a cookie alone cannot delete — the CSRF token is required too');

  r = await fetch(BASE + '/portal/api/saves/kuwait', {
    method: 'DELETE', headers: withCookie({ 'x-csrf-token': 'not-the-token' })
  });
  check(r.status === 403, 'and a wrong one is refused');

  // ----------------------------------------------------------------- data
  console.log('\nWHAT IT SHOWS');
  r = await fetch(BASE + '/portal/api/overview', { headers: withCookie() });
  const o = await r.json();
  check(r.status === 200 && /^[0-9a-f]{16}$/.test(o.revision), 'the overview carries the live revision');
  check(Array.isArray(o.tables) && o.tables.some(t => t.name === 'Fighters' && t.rows > 0),
        'and every table with its row count');
  check(o.saves === 1 && o.saveList[0].id === 'kuwait', 'and the stored profiles');
  check(o.saveTokenSet === true, 'and whether the game-facing API is holding a token');

  r = await fetch(BASE + '/portal/api/tables/Fighters', { headers: withCookie() });
  const t = await r.json();
  check(r.status === 200 && t.Rows.some(f => f.Name === 'Zayos'), 'a table can be read whole');

  r = await fetch(BASE + '/portal/api/tables/Nope', { headers: withCookie() });
  check(r.status === 404, 'an unknown table is 404');

  r = await fetch(BASE + '/portal/api/saves/kuwait', { headers: withCookie() });
  const save = await r.json();
  check(r.status === 200 && save.Progress.Experience === 4200, 'a profile can be read');

  r = await fetch(BASE + '/portal/api/saves/..%2F..%2Fconfig', { headers: withCookie() });
  check(r.status === 400 || r.status === 404, 'a save id that tries to climb out of the store is refused');

  r = await fetch(BASE + '/portal/api/reload', {
    method: 'POST', headers: withCookie({ 'x-csrf-token': csrf })
  });
  const reloaded = await r.json();
  check(r.status === 200 && reloaded.ok === true, 'the payload can be re-read from disk');

  // --------------------------------------------------------------- delete
  console.log('\nDELETING');
  r = await fetch(BASE + '/portal/api/saves/kuwait', {
    method: 'DELETE', headers: withCookie({ 'x-csrf-token': csrf })
  });
  check(r.status === 200, 'cookie plus CSRF token deletes');
  r = await fetch(BASE + '/portal/api/saves/kuwait', { headers: withCookie() });
  check(r.status === 404, 'and it is gone');

  // -------------------------------------------------------------- signing out
  console.log('\nSIGNING OUT');
  r = await keep(await fetch(BASE + '/portal/logout', {
    method: 'POST', headers: withCookie({ 'x-csrf-token': csrf })
  }));
  check(r.status === 200, 'sign out answers');
  const deadCookie = cookie;
  cookie = '';
  r = await fetch(BASE + '/portal/api/overview', { headers: { cookie: deadCookie } });
  check(r.status === 401, 'and the session id stops working immediately — it is dead server-side');

  // -------------------------------------------------- the game API is untouched
  console.log('\nTHE GAME-FACING API IS UNCHANGED');
  r = await fetch(BASE + '/v1/revision');
  check(r.status === 200, '/v1/revision still open');
  r = await fetch(BASE + '/v1/saves/anything');
  check(r.status === 401, '/v1/saves still wants its bearer token');
  r = await fetch(BASE + '/v1/saves/kuwait', { headers: { authorization: 'Bearer sesame' } });
  check(r.status === 404, 'and the token still works (404: it was just deleted)');
  r = await fetch(BASE + '/v1/saves/kuwait', { headers: { cookie: deadCookie } });
  check(r.status === 401, 'a portal cookie does not open the game API either — separate, both ways');

  // --------------------------------------- the three that need their own server
  // Each of these is a claim the docstring makes about how the portal is
  // configured, so each gets a server configured that way rather than a
  // reading of the code.
  const spawnWith = async (env, port) => {
    const p = spawn(process.execPath, [join(HERE, 'server.mjs')], {
      env: { ...process.env, PORT: String(port), HOST: '127.0.0.1',
             SAUD_CONFIG: CONFIG, SAUD_SAVES: SAVES, ...env },
      stdio: ['ignore', 'pipe', 'inherit']
    });
    let out = ''; p.stdout.on('data', d => { out += d; });
    for(let i = 0; i < 60; i++){
      await sleep(100);
      try { await fetch(`http://127.0.0.1:${port}/health`); break; } catch(e){}
    }
    return { proc: p, log: () => out };
  };

  console.log('\nOFF UNLESS CONFIGURED');
  const offPort = PORT + 1;
  const off = await spawnWith({ PORTAL_USER: '', PORTAL_PASSWORD: '', PORTAL_PASSWORD_HASH: '' }, offPort);
  try {
    r = await fetch(`http://127.0.0.1:${offPort}/portal`);
    const j = await r.json();
    check(r.status === 503 && /not configured/.test(j.error),
          'with no account set the portal is closed, not open with a default password');
    check(typeof j.how === 'string' && j.how.includes('PORTAL_USER'), 'and it says how to open it');
    r = await fetch(`http://127.0.0.1:${offPort}/portal/login`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ user: '', password: '' })
    });
    check(r.status === 503, 'and an empty user/password pair cannot sign in to a closed portal');
    check(/portal OFF/.test(off.log()), 'the startup log says so out loud');
  } finally { off.proc.kill('SIGKILL'); }

  console.log('\nGUESSING');
  const ratePort = PORT + 2;
  const rate = await spawnWith(
    { PORTAL_USER: 'u', PORTAL_PASSWORD: 'correct-horse-battery', PORTAL_INSECURE_COOKIE: '1' }, ratePort);
  try {
    const codes = [];
    for(let i = 0; i < 12; i++){
      const rr = await fetch(`http://127.0.0.1:${ratePort}/portal/login`, {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ user: 'u', password: 'guess' + i })
      });
      codes.push(rr.status);
    }
    check(codes.filter(c => c === 401).length === 10 && codes.slice(10).every(c => c === 429),
          'ten wrong guesses, then 429: ' + codes.join(','));
    const good = await fetch(`http://127.0.0.1:${ratePort}/portal/login`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ user: 'u', password: 'correct-horse-battery' })
    });
    check(good.status === 429, 'and the lockout holds even for the right password — it is a lockout, not a filter');

    // The limiter counts sockets, not headers. If a made-up X-Forwarded-For
    // bought a fresh allowance, the lockout above would be worth nothing.
    const spoofed = await fetch(`http://127.0.0.1:${ratePort}/portal/login`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-forwarded-for': '203.0.113.' + Date.now() % 254 },
      body: JSON.stringify({ user: 'u', password: 'guess-again' })
    });
    check(spoofed.status === 429,
          'and a made-up X-Forwarded-For does not buy a fresh allowance (PORTAL_TRUST_PROXY is off)');
  } finally { rate.proc.kill('SIGKILL'); }

  console.log('\nA HASHED PASSWORD');
  const hashPort = PORT + 3;
  const { mintHash } = await import('./portal.mjs');
  const secret = 'a-passphrase-worth-hashing';
  const hashed = await spawnWith(
    { PORTAL_USER: 'op', PORTAL_PASSWORD: '', PORTAL_PASSWORD_HASH: mintHash(secret),
      PORTAL_INSECURE_COOKIE: '1' }, hashPort);
  try {
    r = await fetch(`http://127.0.0.1:${hashPort}/portal/login`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ user: 'op', password: secret })
    });
    check(r.status === 200, 'PORTAL_PASSWORD_HASH signs in with the password it was minted from');
    r = await fetch(`http://127.0.0.1:${hashPort}/portal/login`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ user: 'op', password: secret.slice(0, -1) })
    });
    check(r.status === 401, 'and refuses one character off');
    check(/scrypt hash/.test(hashed.log()), 'the startup log names which form is in use');
  } finally { hashed.proc.kill('SIGKILL'); }

  console.log(`\n${passes} passed, ${fails} failed`);
} finally {
  server.kill('SIGTERM');
  await sleep(200);
  server.kill('SIGKILL');
  rmSync(tmp, { recursive: true, force: true });
}
process.exit(fails ? 1 : 0);
