/* AHMED — Kuwait Fighter :: assets -> Unreal
   ==========================================================================
   The browser build's assets/*.js are the source of truth for every number in
   the game, and the control panel edits them. This turns them into the tables
   Unreal reads, so the two builds cannot drift: retune in the panel, run this,
   rebuild.

   It does three things the files themselves cannot:

     Units.     The browser works in canvas pixels; Unreal works in
                centimetres. Every distance crosses through PX_TO_CM. Get this
                wrong in one place and reach, knockback and stage length stop
                agreeing with each other, which is why it is one constant
                applied in one function rather than a factor typed per field.

     Functions. levels.need(), levels.title() and upgrades.cost() are code, and
                a DataTable cannot hold code. They are sampled instead: every
                level from 1 to max, every upgrade level from 1 to maxLevel,
                written out as rows. Unreal gets a lookup table, which is what
                it wanted anyway.

     Names.     The browser keys things 'powerkick'; Unreal's UENUM is
                PowerKick and its row names are PascalCase. The mapping lives
                here so neither side has to know about the other's spelling.

   Run:  node Tools/export/export.mjs            (writes Content/Data)
         node Tools/export/export.mjs --check    (fails if anything is stale)
         node Tools/export/export.mjs --api      (also writes the API payload)

   No dependencies. Node 18+.
   ========================================================================== */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const HERE = dirname(fileURLToPath(import.meta.url));
const UE5 = resolve(HERE, '../..');
const WEB = resolve(UE5, '../ahmed-fighter');
const DATA = join(UE5, 'Content/Data');

/* One canvas pixel in centimetres. The browser fighter is ~130px tall and a
   fighter is ~185cm, but the number that actually has to hold is reach
   against stage length, so it was fixed from the playfield: 2.4. */
const PX_TO_CM = 2.4;
const cm = px => Math.round(px * PX_TO_CM);
const cm1 = px => +(px * PX_TO_CM).toFixed(1);

/* --------------------------------------------------------------- loading */
/* The asset files are plain scripts that assign to `window`. Evaluating them
   against a stub is both the simplest way to read them and the only way that
   is guaranteed to agree with what the browser sees, since it is the same
   code path. */
function loadAssets(){
  const names = ['ahmed','enemies','hits','talents','upgrades','weapons',
                 'levels','world','stages'];
  const win = {};
  for(const n of names){
    const path = join(WEB, 'assets', `${n}.js`);
    if(!existsSync(path)) die(`missing ${path}`);
    const src = readFileSync(path, 'utf8');
    // eslint-disable-next-line no-new-func
    new Function('window', src)(win);
  }
  const missing = names.filter(n => !win['ASSET_' + n.toUpperCase()]);
  if(missing.length) die(`these files did not define their table: ${missing}`);
  return {
    ahmed:win.ASSET_AHMED, enemies:win.ASSET_ENEMIES, hits:win.ASSET_HITS,
    talents:win.ASSET_TALENTS, upgrades:win.ASSET_UPGRADES,
    weapons:win.ASSET_WEAPONS, levels:win.ASSET_LEVELS,
    world:win.ASSET_WORLD, stages:win.ASSET_STAGES
  };
}

function die(msg){ console.error('export: ' + msg); process.exit(1); }

/* ----------------------------------------------------------------- names */
const pascal = s => String(s).replace(/(^|[^a-z0-9])([a-z0-9])/gi,
                      (_, __, c) => c.toUpperCase()).replace(/[^A-Za-z0-9]/g, '');

/* The browser's ability keys against Unreal's EAbility. Anything absent here
   is a talent Unreal does not know about yet, and the export says so rather
   than writing a row that will not resolve. */
const ABILITY = {
  vault:'Vault', dashleap:'DashLeap', powerkick:'PowerKick',
  haymaker:'Haymaker', hawk:'HawkFist'
};
const GATE = {
  stash:'Stash', ledge:'Ledge', gap:'Gap', shutter:'Shutter', wall:'Wall'
};
const FAMILY = { box:'Box', kick:'Kick' };

/* ------------------------------------------------------------------- csv */
function csvCell(v){
  if(v === null || v === undefined) return '';
  const s = String(v);
  return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}
function csv(header, rows){
  return [header.join(','), ...rows.map(r => r.map(csvCell).join(','))].join('\n') + '\n';
}
/* Unreal parses a TArray<FName> cell as ("A","B"). Returned raw -- csvCell
   escapes it on the way out, and doing it here as well was how the first run
   produced a cell wrapped in three sets of quotes. */
function nameArray(items){
  return '(' + items.map(i => '"' + i + '"').join(',') + ')';
}

/* ============================================================== the tables */

function attacks(A){
  const header = ['Name','Family','Damage','Startup','Active','Recovery','Reach',
                  'DepthTolerance','Knockback','StaminaCost','bHeavy','bMultiHit'];
  const rows = Object.entries(A.hits).map(([k, h]) => {
    if(!FAMILY[h.fam]) die(`attack ${k} has family '${h.fam}', which Unreal's EAttackFamily does not have`);
    return [pascal(k), FAMILY[h.fam], h.dmg, h.su, h.ac, h.rc,
            cm(h.reach), 80, cm(h.push), h.stam,
            !!h.heavy, !!h.multi];
  });
  return csv(header, rows);
}

function fighters(A){
  const header = ['Name','DisplayName','DisplayNameArabic','MaxHealth','PowerMultiplier',
                  'MoveSpeed','PreferredRange','AttackInterval','GuardChance',
                  'bHitAndRun','bIsBoss','ExperienceValue','Moves'];
  const rows = [];

  // Ahmed himself, so the table is the whole roster rather than the enemies
  // only. His moves are the punch chain the player actually throws.
  const P = A.ahmed;
  rows.push(['Ahmed', P.name, P.ar, P.base.hp, P.base.pow, cm(P.base.spd),
             cm(P.base.reach), 0, 0, false, false, 0,
             nameArray(['Jab','Cross','Hook','Kick','Knee'])]);

  for(const [k, e] of Object.entries(A.enemies)){
    const moves = (e.moves || []).map(pascal);
    const unknown = moves.filter(m => !A.hits[m.toLowerCase()]);
    if(unknown.length) die(`${k} uses moves not in hits.js: ${unknown}`);
    rows.push([pascal(k), e.name, e.ar, e.hp, e.pow, cm(e.spd), cm(e.reach),
               e.rate, guardChanceFor(e), !!e.hitRun, isBoss(k, e), e.xp,
               nameArray(moves)]);
  }
  return csv(header, rows);
}
/* The browser has no guard chance -- enemies block as a function of their
   archetype. Rather than invent a field the panel does not edit, it is
   derived: heavier, slower archetypes guard more. */
function guardChanceFor(e){
  const g = 0.10 + (e.hp / 500) * 0.5 + (e.rate - 1) * 0.10;
  return +Math.max(0.05, Math.min(0.55, g)).toFixed(2);
}
const isBoss = (k, e) => e.hp >= 250 || k === 'boss' || k === 'saqr';

function talents(A){
  const header = ['Name','Ability','DisplayName','DisplayNameArabic','Icon',
                  'ManaCost','Description'];
  const rows = Object.entries(A.talents.abilities).map(([k, t]) => {
    if(!ABILITY[k]) die(`talent '${k}' has no EAbility in AhmedTypes.h — add it there first`);
    return [ABILITY[k], ABILITY[k], t.n, t.ar, t.icon, t.mp || 0, t.d];
  });
  return csv(header, rows);
}

function gates(A){
  const header = ['Name','GateType','RequiredAbility','DisplayName',
                  'DisplayNameArabic','Hint','BreakFamily'];
  const rows = Object.entries(A.talents.gates).map(([k, g]) => {
    if(!GATE[k]) die(`gate '${k}' has no EGateType in AhmedTypes.h`);
    return [GATE[k], GATE[k], g.need ? ABILITY[g.need] : 'None',
            g.n, g.ar, g.how, g.breakBy ? FAMILY[g.breakBy] : 'None'];
  });
  return csv(header, rows);
}

function upgrades(A){
  const header = ['Name','Track','DisplayName','DisplayNameArabic','Description',
                  'Level','Cost','CumulativeCost'];
  const rows = [];
  for(const t of A.upgrades.tracks){
    let cum = 0;
    for(let lvl = 0; lvl < A.upgrades.maxLevel; lvl++){
      const c = Math.round(A.upgrades.cost(lvl));
      cum += c;
      rows.push([`${pascal(t.k)}_${lvl + 1}`, pascal(t.k), t.n, t.ar, t.d,
                 lvl + 1, c, cum]);
    }
  }
  return csv(header, rows);
}

function levels(A){
  const header = ['Name','Level','ExperienceRequired','StepFromPrevious',
                  'Title','BonusHealth','BonusMana'];
  const rows = [];
  for(let l = 1; l <= A.levels.max; l++){
    const need = Math.round(A.levels.need(l));
    const prev = l > 1 ? Math.round(A.levels.need(l - 1)) : 0;
    rows.push([`Level_${String(l).padStart(2, '0')}`, l, need, need - prev,
               A.levels.title(l),
               A.levels.perLevel.hp * (l - 1), A.levels.perLevel.mp * (l - 1)]);
  }
  return csv(header, rows);
}

function weapons(A){
  const header = ['Name','DisplayName','DisplayNameArabic','DamageMultiplier',
                  'BonusReach','BonusKnockback','Uses','Length','Thickness'];
  const rows = Object.entries(A.weapons).map(([k, w]) =>
    [pascal(k), w.n, w.ar, w.dmg, cm(w.reach), cm(w.push), w.uses,
     cm1(w.len), cm1(w.thick)]);
  return csv(header, rows);
}

function stages(A){
  return JSON.stringify(A.stages.map((st, i) => ({
    Name: pascal(st.name),
    Index: i,
    DisplayName: st.name,
    DisplayNameArabic: st.ar,
    Theme: pascal(st.theme),
    Briefing: (st.story || []).join(' '),
    BriefingArabic: st.storyAr || '',
    Hint: st.hint || '',
    Length: cm(st.len),
    Tier: st.tier | 0,
    bIsBossStage: !!st.boss,
    bSurvival: !!st.survival,
    Waves: (st.waves || []).map(w => ({
      TriggerDistance: w.at < 0 ? -1 : cm(w.at),
      Fighters: (w.e || []).flatMap(([type, n]) =>
        Array.from({ length: n }, () => pascal(type))),
      TierOverride: w.tier === undefined ? -1 : w.tier
    })),
    Gates: (st.gates || []).map(g => ({
      Distance: cm(g.at),
      Type: GATE[g.type] || die(`stage ${st.name} has gate type '${g.type}'`),
      RewardAbility: g.reward && g.reward.ability
        ? (ABILITY[g.reward.ability] || die(`unknown reward ability ${g.reward.ability}`))
        : 'None',
      RewardExperience: (g.reward && g.reward.xp) || 0
    }))
  })), null, 2) + '\n';
}

/* The world graph. Unreal needs it to know which stage a player can walk to
   from where, and what it wants of them -- the whole Metroidvania in one
   file. Sides are kept as w/e/d because that is what the browser calls them
   and renaming them here would only make the two harder to compare. */
function world(A){
  const side = l => l ? {
    To: l.to,
    RequiredAbility: l.needs ? (ABILITY[l.needs] || die(`route wants unknown talent ${l.needs}`)) : 'None',
    AfterCleared: l.afterCleared === undefined ? -1 : l.afterCleared,
    Distance: l.at === undefined ? -1 : cm(l.at)
  } : null;
  return JSON.stringify({
    StartArea: A.world.start,
    Areas: A.world.layout.map((L, i) => ({
      Index: i,
      Name: L.n,
      MapX: L.x, MapY: L.y,
      West: side(A.world.areas[i] && A.world.areas[i].w),
      East: side(A.world.areas[i] && A.world.areas[i].e),
      Door: side(A.world.areas[i] && A.world.areas[i].d)
    }))
  }, null, 2) + '\n';
}

/* The player's own numbers, which live nowhere else. */
function player(A){
  const P = A.ahmed;
  return JSON.stringify({
    DisplayName: P.name, DisplayNameArabic: P.ar,
    BaseHealth: P.base.hp, BaseStamina: P.base.stam, BaseMana: P.base.mp,
    BasePower: P.base.pow,
    BaseMoveSpeed: cm(P.base.spd), BaseReach: cm(P.base.reach),
    PerUpgradeLevel: {
      Vitality: P.perLevel.vit, Stamina: P.perLevel.stam,
      MoveSpeed: cm(P.perLevel.spd)
    },
    ManaRegenPerSecond: P.mpRegen.idle,
    ManaPerLandedHit: P.mpRegen.onHit,
    UpgradeMaxLevel: A.upgrades.maxLevel,
    LevelMax: A.levels.max
  }, null, 2) + '\n';
}

/* ================================================================== write */

/* Everything the API serves and the game bakes in, in one object, so the two
   paths cannot serve different content. */
function apiPayload(A, files){
  const body = {
    Version: 1,
    Attacks: parseCsv(files['DT_Attacks.csv']),
    Fighters: parseCsv(files['DT_Fighters.csv']),
    Talents: parseCsv(files['DT_Talents.csv']),
    GateKinds: parseCsv(files['DT_GateKinds.csv']),
    Upgrades: parseCsv(files['DT_Upgrades.csv']),
    Levels: parseCsv(files['DT_Levels.csv']),
    Weapons: parseCsv(files['DT_Weapons.csv']),
    Stages: JSON.parse(files['DT_Stages.json']),
    World: JSON.parse(files['DT_World.json']),
    Player: JSON.parse(files['Player.json'])
  };
  // The revision is the content's own hash, so a client can ask "is this what
  // I already have?" without anyone remembering to bump a number.
  body.Revision = createHash('sha256')
    .update(JSON.stringify(body)).digest('hex').slice(0, 16);
  body.GeneratedAt = new Date().toISOString();
  return JSON.stringify(body, null, 2) + '\n';
}

/* A CSV reader that only has to read what this file just wrote. */
function parseCsv(text){
  const lines = text.trim().split('\n');
  const head = splitCsvLine(lines[0]);
  return lines.slice(1).map(l => {
    const cells = splitCsvLine(l), o = {};
    head.forEach((h, i) => { o[h] = coerce(cells[i]); });
    return o;
  });
}
function splitCsvLine(line){
  const out = []; let cur = '', q = false;
  for(let i = 0; i < line.length; i++){
    const c = line[i];
    if(q){
      if(c === '"' && line[i+1] === '"'){ cur += '"'; i++; }
      else if(c === '"') q = false;
      else cur += c;
    } else if(c === '"') q = true;
    else if(c === ','){ out.push(cur); cur = ''; }
    else cur += c;
  }
  out.push(cur);
  return out;
}
function coerce(v){
  if(v === 'True' || v === 'true') return true;
  if(v === 'False' || v === 'false') return false;
  if(v !== '' && !isNaN(Number(v))) return Number(v);
  const m = /^\((.*)\)$/.exec(v);
  if(m) return m[1] ? m[1].split(',').map(s => s.replace(/^"|"$/g, '')) : [];
  return v;
}

function main(){
  const args = process.argv.slice(2);
  const check = args.includes('--check');
  const wantApi = args.includes('--api') || check;

  const A = loadAssets();
  const files = {
    'DT_Attacks.csv':  attacks(A),
    'DT_Fighters.csv': fighters(A),
    'DT_Talents.csv':  talents(A),
    'DT_GateKinds.csv': gates(A),
    'DT_Upgrades.csv': upgrades(A),
    'DT_Levels.csv':   levels(A),
    'DT_Weapons.csv':  weapons(A),
    'DT_Stages.json':  stages(A),
    'DT_World.json':   world(A),
    'Player.json':     player(A)
  };
  if(wantApi) files['config.json'] = apiPayload(A, files);

  mkdirSync(DATA, { recursive: true });
  const stale = [];
  for(const [name, text] of Object.entries(files)){
    const path = join(DATA, name);
    const had = existsSync(path) ? readFileSync(path, 'utf8') : null;
    // GeneratedAt changes every run, so --check compares everything else.
    const same = had !== null && strip(had) === strip(text);
    if(check){ if(!same) stale.push(name); continue; }
    if(!same) writeFileSync(path, text);
    console.log(`${same ? '  =' : '  ✎'} Content/Data/${name}  (${text.length} bytes)`);
  }
  if(check){
    if(stale.length){
      console.error('export --check: these are stale, run the export:\n  ' +
                    stale.join('\n  '));
      process.exit(1);
    }
    console.log('export --check: Unreal\'s tables match the browser assets.');
    return;
  }
  const rev = /"Revision": "([a-f0-9]+)"/.exec(files['config.json'] || '');
  console.log(`\n${Object.keys(files).length} files written from ${WEB}/assets` +
              (rev ? `\nrevision ${rev[1]}` : ''));
}
const strip = t => t.replace(/"GeneratedAt": "[^"]*",?\n?/, '');

main();
