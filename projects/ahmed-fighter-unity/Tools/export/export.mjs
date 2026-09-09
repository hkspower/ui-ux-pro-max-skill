/* AHMED — Kuwait Fighter :: assets -> Unity
   ==========================================================================
   The browser build's assets/*.js are the source of truth for every number in
   the game, and the control panel edits them. This turns them into the JSON
   Unity reads, so the builds cannot drift: retune in the panel, run this,
   press play.

   It is a sibling of ../../../ahmed-fighter-ue5/Tools/export/export.mjs and
   reads exactly the same files. It is a separate program rather than a flag
   on that one because the two targets disagree about almost everything on the
   way out:

     Units.     The browser works in canvas pixels and Unreal in centimetres;
                Unity works in metres. One constant, applied in one function,
                for the same reason as over there -- get it wrong in one place
                and reach, knockback and stage length stop agreeing.

     Shape.     Unreal wants DataTable CSV with PascalCase columns. Unity's
                JsonUtility maps JSON keys onto field names exactly, cannot
                read a top-level array, and reads enums as integers -- so
                every table is {"items":[...]}, every field is camelCase, and
                every enum crosses as its name for the loader to parse.

     Styles.    Fight styles are derived from the roster rather than authored.
                Unreal derives them in Tools/levels/build_data_assets.py, at
                asset-build time. Unity has no equivalent step, so the same
                derivation runs here. The two must agree; see STRIKE_BANDS.

   Run:  node Tools/export/export.mjs           (writes Assets/Resources/Data)
         node Tools/export/export.mjs --check   (fails if anything is stale)

   No dependencies. Node 18+.
   ========================================================================== */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const UNITY = resolve(HERE, '../..');
const WEB = resolve(UNITY, '../ahmed-fighter');
const OUT = join(UNITY, 'Assets/Resources/Data');

/* One canvas pixel in metres. The Unreal export fixed a pixel at 2.4 cm from
   the playfield -- reach against stage length is the ratio that has to hold --
   and this is that same number in Unity's units. Changing one without the
   other silently gives the two ports different games. */
const PX_TO_M = 0.024;
const m = px => +(px * PX_TO_M).toFixed(4);

/* --------------------------------------------------------------- loading */
/* The asset files are plain scripts that assign to `window`. Evaluating them
   against a stub is the simplest way to read them and the only way guaranteed
   to agree with what the browser sees, since it is the same code path. */
function loadAssets(){
  const names = ['ahmed','enemies','hits','talents','upgrades','weapons',
                 'levels','world','stages','colors'];
  const win = {};
  for(const n of names){
    const path = join(WEB, 'assets', `${n}.js`);
    if(!existsSync(path)) die(`missing ${path}`);
    new Function('window', readFileSync(path, 'utf8'))(win);
  }
  const missing = names.filter(n => !win['ASSET_' + n.toUpperCase()]);
  if(missing.length) die(`these files did not define their table: ${missing}`);
  return {
    ahmed:win.ASSET_AHMED, enemies:win.ASSET_ENEMIES, hits:win.ASSET_HITS,
    talents:win.ASSET_TALENTS, upgrades:win.ASSET_UPGRADES,
    weapons:win.ASSET_WEAPONS, levels:win.ASSET_LEVELS,
    world:win.ASSET_WORLD, stages:win.ASSET_STAGES, colors:win.ASSET_COLORS
  };
}

function die(msg){ console.error('export: ' + msg); process.exit(1); }

/* ----------------------------------------------------------------- names */
const pascal = s => String(s).replace(/(^|[^a-z0-9])([a-z0-9])/gi,
                      (_, __, c) => c.toUpperCase()).replace(/[^A-Za-z0-9]/g, '');
/* Stage names are shouted in the browser ("SOUQ MUBARAKIYA"), and shouting
   survives pascal() as SOUQMUBARAKIYA. Lower the words first, then case them. */
const pascalWords = s => pascal(String(s).toLowerCase());

/* The browser's ability keys against the Ability enum. Anything absent is a
   talent this port does not know about, and the export says so rather than
   writing a value that will not parse. */
const ABILITY = {
  vault:'Vault', dashleap:'DashLeap', powerkick:'PowerKick',
  haymaker:'Haymaker', hawk:'HawkFist'
};
const GATE = { stash:'Stash', ledge:'Ledge', gap:'Gap', shutter:'Shutter', wall:'Wall' };
const FAMILY = { box:'Box', kick:'Kick' };

/* JsonUtility cannot read a top-level array, so every table is an object with
   one `items` field. That is not a stylistic choice; it is the whole reason
   these files look the way they do. */
const table = items => JSON.stringify({ items }, null, 2) + '\n';

/* ============================================================== the tables */

function attacks(A){
  return table(Object.entries(A.hits).map(([k, h]) => {
    if(!FAMILY[h.fam]) die(`attack ${k} has family '${h.fam}', which the Family enum does not have`);
    return {
      name: pascal(k), family: FAMILY[h.fam],
      damage: h.dmg, startup: h.su, active: h.ac, recovery: h.rc,
      reach: m(h.reach), depthTolerance: 0.80, knockback: m(h.push),
      staminaCost: h.stam, heavy: !!h.heavy, multiHit: !!h.multi
    };
  }));
}

/* The browser has no guard chance -- enemies block as a function of their
   archetype. Rather than invent a field the panel does not edit it is
   derived, by the same formula the Unreal export uses. */
function guardChanceFor(e){
  const g = 0.10 + (e.hp / 500) * 0.5 + (e.rate - 1) * 0.10;
  return +Math.max(0.05, Math.min(0.55, g)).toFixed(2);
}
const isBoss = (k, e) => e.hp >= 250 || k === 'boss' || k === 'saqr';

function fighters(A){
  const P = A.ahmed;
  const rows = [{
    name: 'Ahmed', displayName: P.name, displayNameArabic: P.ar,
    maxHealth: P.base.hp, powerMultiplier: P.base.pow,
    moveSpeed: m(P.base.spd), preferredRange: m(P.base.reach),
    attackInterval: 0, guardChance: 0, hitAndRun: false, boss: false,
    experienceValue: 0, moves: ['Jab','Cross','Hook','Kick','Knee'],
    fightStyle: ''            // the player is not driven by one
  }];
  for(const [k, e] of Object.entries(A.enemies)){
    const moves = (e.moves || []).map(pascal);
    const unknown = moves.filter(x => !A.hits[x.toLowerCase()]);
    if(unknown.length) die(`${k} uses moves not in hits.js: ${unknown}`);
    rows.push({
      name: pascal(k), displayName: e.name, displayNameArabic: e.ar,
      maxHealth: e.hp, powerMultiplier: e.pow,
      moveSpeed: m(e.spd), preferredRange: m(e.reach),
      attackInterval: e.rate, guardChance: guardChanceFor(e),
      hitAndRun: !!e.hitRun, boss: isBoss(k, e), experienceValue: e.xp,
      moves, fightStyle: pascal(k)
    });
  }
  return table(rows);
}

/* ------------------------------------------------------------- the styles */
/* Where each move is worth throwing from, and how likely it is to open a
   combination rather than be the whole of it. Bands are a property of the
   move, not of the archetype: a knee is a close-range strike whoever throws
   it, and an archetype that only knows knees has to get inside to do anything
   at all. That is what makes a grappler read as a grappler.

   This table and the four formulas below must match
   ../../../ahmed-fighter-ue5/Tools/levels/build_data_assets.py. */
const STRIKE_BANDS = {
  Jab:     { bands:['Mid','Close'],  weight:1.6, opener:0.75 },
  Cross:   { bands:['Mid'],          weight:1.1, opener:0.35 },
  Hook:    { bands:['Mid','Close'],  weight:0.9, opener:0.20 },
  Kick:    { bands:['Long','Mid'],   weight:1.0, opener:0.15 },
  Knee:    { bands:['Close'],        weight:1.2, opener:0.30 },
  Special: { bands:['Mid','Close'],  weight:0.5, opener:0.00 },
  Rage:    { bands:['Mid','Close'],  weight:0.5, opener:0.00 }
};

function styles(A){
  const rows = [];
  for(const [k, e] of Object.entries(A.enemies)){
    // A move listed twice is the browser's way of saying "throw this one more
    // often". Collapsing the repeat into the weight says the same thing where
    // the selection can see it.
    const strikes = [];
    for(const move of (e.moves || []).map(pascal)){
      const spec = STRIKE_BANDS[move];
      if(!spec) die(`move '${move}' (fighter ${k}) has no range bands -- add it to STRIKE_BANDS`);
      const seen = strikes.find(s => s.attackRow === move);
      if(seen){ seen.weight = +(seen.weight + spec.weight).toFixed(2); continue; }
      strikes.push({ attackRow: move, bands: spec.bands.slice(),
                     weight: spec.weight, opensCombination: spec.opener });
    }
    if(!strikes.length) die(`fighter '${k}' has no moves to build a style from`);

    const reach = m(e.reach), rate = e.rate, speed = m(e.spd);
    const boss = isBoss(k, e), health = e.hp, hitRun = !!e.hitRun;
    /* The speed thresholds below came from the Unreal derivation, where a
       move speed is in centimetres per second. `speed` here is metres, so
       they cross as metres too. Feeding them through the pixel conversion
       instead -- which is the obvious mistake, since every other number in
       this file is pixels -- puts every threshold 2.4x out and hands the
       whole roster bounce 0 and circle 0.05, so no archetype moves its feet
       differently from any other. */
    const cms = v => v / 100;
    // A fighter that strikes and leaves holds its distance and bounces; one
    // that does not walks in and stands there. That single flag is most of
    // the difference between a runner and a bouncer.
    const discipline = hitRun ? 0.9 : Math.max(0.15, Math.min(0.85, 1 - health / 300));
    const hasLong = strikes.some(s => s.bands.includes('Long'));
    const fast = speed > cms(260);

    rows.push({
      name: pascal(k), displayName: e.name,
      // Kickers stand further out than their reach suggests: a kick thrown
      // from punching distance is a kick that jams.
      preferredRange: +(reach * (hasLong ? 1.12 : 0.95)).toFixed(4),
      rangeDiscipline: +discipline.toFixed(2),
      resetDistance: hitRun ? +(reach * 2.6).toFixed(4) : 0,
      bounceRate: fast ? +Math.min(2.2, speed / cms(260)).toFixed(2) : 0,
      bounceAmplitude: fast ? +(reach * 0.22).toFixed(4) : 0,
      // Faster feet circle more; a wall of a fighter barely does.
      circleTendency: +Math.max(0.05, Math.min(0.8, (speed - cms(200)) / cms(260))).toFixed(2),
      circleSwitchTime: +Math.max(0.8, 4 - speed / cms(130)).toFixed(2),
      strikes,
      attackInterval: rate > 0 ? rate : 1.55,
      rhythmJitter: +Math.max(0.15, Math.min(0.45, 0.55 - rate * 0.12)).toFixed(2),
      maxComboLength: boss ? 3 : (strikes.length > 2 ? 2 : 1),
      guardChance: guardChanceFor(e),
      guardsWhileAdvancing: !!(boss || health >= 90),
      counterChance: +Math.max(0.05, Math.min(0.55, 0.40 - guardChanceFor(e) * 0.5)).toFixed(2)
    });
  }
  return table(rows);
}

/* -------------------------------------------------------------- the world */

function stages(A){
  return table(A.stages.map((st, i) => ({
    name: pascalWords(st.name), index: i,
    displayName: st.name, displayNameArabic: st.ar,
    theme: pascal(st.theme),
    briefing: (st.story || []).join(' '), briefingArabic: st.storyAr || '',
    hint: st.hint || '',
    length: m(st.len), tier: st.tier | 0,
    bossStage: !!st.boss, survival: !!st.survival,
    waves: (st.waves || []).map(w => ({
      triggerDistance: w.at < 0 ? -1 : m(w.at),
      fighters: (w.e || []).flatMap(([type, n]) =>
        Array.from({ length: n }, () => pascal(type))),
      tierOverride: w.tier === undefined ? -1 : w.tier
    })),
    gates: (st.gates || []).map(g => ({
      distance: m(g.at),
      type: GATE[g.type] || die(`stage ${st.name} has gate type '${g.type}'`),
      rewardAbility: g.reward && g.reward.ability
        ? (ABILITY[g.reward.ability] || die(`unknown reward ability ${g.reward.ability}`))
        : 'None',
      rewardExperience: (g.reward && g.reward.xp) || 0
    }))
  })));
}

function world(A){
  const side = l => l ? {
    to: l.to,
    requiredAbility: l.needs ? (ABILITY[l.needs] || die(`route wants unknown talent ${l.needs}`)) : 'None',
    afterCleared: l.afterCleared === undefined ? -1 : l.afterCleared,
    distance: l.at === undefined ? -1 : m(l.at)
  } : { to: -1, requiredAbility: 'None', afterCleared: -1, distance: -1 };
  return table(A.world.layout.map((L, i) => ({
    index: i, name: L.n, mapX: L.x, mapY: L.y,
    startArea: A.world.start,
    west: side(A.world.areas[i] && A.world.areas[i].w),
    east: side(A.world.areas[i] && A.world.areas[i].e),
    door: side(A.world.areas[i] && A.world.areas[i].d)
  })));
}

function talents(A){
  return table(Object.entries(A.talents.abilities).map(([k, t]) => {
    if(!ABILITY[k]) die(`talent '${k}' has no Ability enum value -- add it first`);
    return { name: ABILITY[k], ability: ABILITY[k], displayName: t.n,
             displayNameArabic: t.ar, icon: t.icon, manaCost: t.mp || 0,
             description: t.d };
  }));
}

/* levels.need() and upgrades.cost() are code, and a table cannot hold code.
   They are sampled instead -- every level, every upgrade level, written out
   as rows. Unity gets a lookup, which is what it wanted anyway. */
function levels(A){
  const L = A.levels, rows = [];
  for(let lv = 1; lv <= L.max; lv++){
    rows.push({ level: lv, experienceToNext: lv >= L.max ? 0 : L.need(lv),
                title: L.title(lv) });
  }
  return table(rows);
}

function upgrades(A){
  /* `tracks` is an array, so Object.entries handed this the string indices
     '0'..'4' as the track key, and cost() takes one argument -- the level you
     are buying -- so passing the key first priced every level of a track the
     same and made the price depend on which track it was. The table went out
     with tracks named 0 to 4 and BOXING costing 120 at every level. The
     Unreal exporter had it right, and this now matches it. */
  const U = A.upgrades, rows = [];
  for(const t of U.tracks){
    for(let lv = 0; lv < U.maxLevel; lv++){
      rows.push({ track: pascal(t.k), level: lv + 1,
                  cost: Math.round(U.cost(lv)),
                  displayName: t.n, displayNameArabic: t.ar,
                  description: t.d });
    }
  }
  return table(rows);
}


/* ------------------------------------------------------------- the colours */
/* The scheme, flattened. It is nested by group in the asset file because that
   is how a person reads a palette, and flat here because that is how a table
   is looked up -- "State.Health" is one key, not a walk down two objects.
   Both spellings are carried: the hex a designer recognises, and the sRGB
   components an engine needs, so neither side has to parse a string. */
function colourRows(A){
  const rows = [];
  for(const [group, entries] of Object.entries(A.colors)){
    for(const [name, value] of Object.entries(entries)){
      const c = parseColour(value);
      if(!c) die(`colors.js: ${group}.${name} is not a colour: ${value}`);
      rows.push({ group: pascal(group), name: pascal(name),
                  key: `${pascal(group)}.${pascal(name)}`,
                  css: value, hex: c.hex,
                  r: c.r, g: c.g, b: c.b, a: c.a });
    }
  }
  return rows;
}

/* #rgb, #rrggbb, #rrggbbaa and rgba(). Components come out 0..1 sRGB, which
   is what both engines want; neither takes a CSS string. */
function parseColour(v){
  const s = String(v).trim();
  const round = n => Math.round(n * 1e4) / 1e4;
  const out = (r, g, b, a) => ({
    r: round(r/255), g: round(g/255), b: round(b/255), a: round(a),
    hex: '#' + [r,g,b].map(n => n.toString(16).padStart(2,'0')).join('')
  });
  let m = s.match(/^#([0-9a-f]{3,8})$/i);
  if(m){
    let h = m[1];
    if(h.length === 3) h = h.split('').map(c => c + c).join('');
    if(h.length === 6) h += 'ff';
    if(h.length !== 8) return null;
    const n = parseInt(h, 16);
    return out((n>>>24)&255, (n>>>16)&255, (n>>>8)&255, (n&255)/255);
  }
  m = s.match(/^rgba?\(([^)]+)\)$/i);
  if(m){
    const p = m[1].split(',').map(x => parseFloat(x));
    if(p.length < 3 || p.some(isNaN)) return null;
    return out(p[0], p[1], p[2], p.length > 3 ? p[3] : 1);
  }
  return null;
}

/* ------------------------------------------------------------- the sounds */
/* The one table that does not come from the browser project.

   The sound catalogue -- cue name, level, pitch drift, whether it is
   positioned, how often it may retrigger -- was written in the Unreal project
   because that is where the audio subsystem was built, and it is authored by
   hand rather than derived from anything. Rather than keep a second copy here
   and let the two drift, this reads that one and reshapes it.

   If the catalogue ever moves into ../ahmed-fighter/assets where the rest of
   the game's data lives, this function is the only thing that has to change. */
function sounds(){
  const csv = resolve(UNITY, '../ahmed-fighter-ue5/Content/Data/DT_Sounds.csv');
  if(!existsSync(csv)) die(`missing ${csv} -- the sound catalogue lives in the Unreal project`);
  const lines = readFileSync(csv, 'utf8').trim().split('\n');
  const head = splitCsv(lines[0]);
  const rows = lines.slice(1).map(l => {
    const c = splitCsv(l), r = {};
    head.forEach((h, i) => { r[h] = c[i]; });
    return r;
  }).filter(r => r.Name && !r.Name.startsWith('Music_'));

  return table(rows.map(r => ({
    name: r.Name,
    // /Game/Audio/Combat/S_Hit_Heavy.S_Hit_Heavy -> Audio/Combat/S_Hit_Heavy,
    // which is what Resources.Load wants.
    clip: 'Audio/' + r.Sound.split('.')[0].split('/').slice(-2).join('/'),
    volume: +r.Volume || 1,
    pitchMin: +r.PitchMin || 1,
    pitchMax: +r.PitchMax || 1,
    spatial: String(r.bSpatial).trim().toLowerCase() === 'true',
    cooldown: +r.Cooldown || 0,
    lead: +r.Lead || 0,
    description: r.Description || ''
  })));
}

/* A CSV line, respecting quotes -- the Description column is prose and has
   commas in it, so splitting on ',' alone shifts every field after it. */
function splitCsv(line){
  const out = []; let cur = '', q = false;
  for(let i = 0; i < line.length; i++){
    const ch = line[i];
    if(q){
      if(ch === '"' && line[i+1] === '"'){ cur += '"'; i++; }
      else if(ch === '"') q = false;
      else cur += ch;
    } else if(ch === '"') q = true;
    else if(ch === ',') { out.push(cur); cur = ''; }
    else cur += ch;
  }
  out.push(cur);
  return out;
}

function player(A){
  const P = A.ahmed;
  return JSON.stringify({
    displayName: P.name, displayNameArabic: P.ar,
    baseHealth: P.base.hp, baseStamina: P.base.stam, baseMana: P.base.mp,
    basePower: P.base.pow,
    baseMoveSpeed: m(P.base.spd), baseReach: m(P.base.reach),
    healthPerVitality: P.perLevel.vit,
    staminaPerStamina: P.perLevel.stam,
    speedPerSpeed: m(P.perLevel.spd),
    manaRegenPerSecond: P.mpRegen.idle,
    manaPerLandedHit: P.mpRegen.onHit,
    upgradeMaxLevel: A.upgrades.maxLevel
  }, null, 2) + '\n';
}

/* ==================================================================== main */

const A = loadAssets();
const files = {
  'attacks.json':  attacks(A),
  'fighters.json': fighters(A),
  'styles.json':   styles(A),
  'stages.json':   stages(A),
  'colors.json':   table(colourRows(A)),
  'world.json':    world(A),
  'talents.json':  talents(A),
  'levels.json':   levels(A),
  'upgrades.json': upgrades(A),
  'player.json':   player(A),
  'sounds.json':   sounds()
};

const check = process.argv.includes('--check');
if(check){
  const stale = Object.entries(files).filter(([name, body]) => {
    const path = join(OUT, name);
    return !existsSync(path) || readFileSync(path, 'utf8') !== body;
  }).map(([name]) => name);
  if(stale.length){
    console.error('export --check: these are stale, run the export:');
    for(const n of stale) console.error('  ' + n);
    process.exit(1);
  }
  console.log('export --check: Unity\'s data matches the browser assets.');
} else {
  mkdirSync(OUT, { recursive: true });
  for(const [name, body] of Object.entries(files)){
    const path = join(OUT, name);
    const same = existsSync(path) && readFileSync(path, 'utf8') === body;
    writeFileSync(path, body);
    console.log(`  ${same ? '=' : '✎'} Assets/Resources/Data/${name}  (${body.length} bytes)`);
  }
  console.log(`\n${Object.keys(files).length} files written from ${WEB}/assets`);
}
