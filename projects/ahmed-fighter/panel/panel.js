/* AHMED — Kuwait Fighter :: control panel
   ==========================================================================
   Every number the game runs on lives in assets/*.js. Editing them by hand
   works, but you cannot see what a change costs: raise a hook by two damage
   and you have changed the time to kill on ten enemies, the XP rate of the
   whole campaign, and whether the training camp is affordable. This panel
   edits the same tables and shows you that second half.

   It reads the real asset files -- the same script tags the game uses -- so
   what you see here is what the game is running. Nothing is written back
   automatically: you export, and you choose what to keep.

   Plain scripts, no build, no dependencies, same as the game. Open the file.
   ========================================================================== */
'use strict';

/* ------------------------------------------------------------- asset table */
var DOMAINS = [
  { k:'ahmed', n:'Ahmed', ico:'✦', g:'ASSET_AHMED', file:'assets/ahmed.js',
    shape:'single',
    blurb:'The player character. `base` is level zero, `perLevel` is what one bought level of each track adds, and `look` is the kit — the same flags the enemies use.',
    doc:'AHMED — the player character.\n\n   His stats scale with the upgrade tracks, so `base` holds the level-zero\n   values and `perLevel` what each bought level adds. `look` is the kit: the\n   same flags the enemies use, listed here so his appearance can be changed\n   without going near the renderer.' },

  { k:'enemies', n:'Enemies', ico:'✚', g:'ASSET_ENEMIES', file:'assets/enemies.js',
    shape:'records',
    blurb:'The ten archetypes. Silhouette carries the read in a crowded wave, so build, headwear and garment matter more than colour.',
    doc:'ENEMIES — the ten archetypes.\n\n   `col` is the palette, `look` the kit. Silhouette carries the read in a\n   crowded wave, so build, headwear and garment matter more than colour:\n   see the roster table in README.md.' },

  { k:'hits', n:'Hits', ico:'✱', g:'ASSET_HITS', file:'assets/hits.js',
    shape:'records',
    blurb:'Every strike. su/ac/rc are the startup, active and recovery windows in seconds — a hit only lands during `ac`, and `rc` is what makes a whiffed heavy hurt.',
    doc:'HITS — every strike in the game.\n\n   su/ac/rc are the startup, active and recovery windows in seconds: a hit\n   only lands during `ac`, and `rc` is what makes a whiffed heavy hurt.\n   `fam` decides which upgrade track scales it and which gates it can break.' },

  { k:'stages', n:'Stages', ico:'▤', g:'ASSET_STAGES', file:'assets/stages.js',
    shape:'array',
    blurb:'What is inside each area: how far it runs, where each ambush triggers, and which sealed route it hides. How the areas connect is the World tab.',
    doc:'STAGES — the nine places, plus survival.\n\n   `len` is how far the area runs in world px; `waves` are the ambushes and\n   `at` is the x that triggers each one. A wave with `at:-1` spawns the moment\n   the one before it clears, which is how survival works. `gates` are the\n   sealed routes inside an area — always against the back wall, so an area is\n   completable without them.\n\n   How the areas CONNECT is world.js, not this file.' },

  { k:'world', n:'World', ico:'◈', g:'ASSET_WORLD', file:'assets/world.js',
    shape:'single',
    blurb:'How the nine areas connect. Every link must be two-way and both halves must carry the same `needs`, or a route is passable from one side only.',
    doc:'THE WORLD — how the nine areas connect.\n\n   This is what makes the game a Metroidvania rather than a level select: you\n   walk between areas, and a route you cannot pass is a route you come back to.\n\n   Every link is two-way and both halves carry the same `needs`, so a route is\n   sealed from whichever side you arrive at. `d` is a door partway into an\n   area rather than at its edge; `at` is where it stands.' },

  { k:'talents', n:'Talents', ico:'⤴', g:'ASSET_TALENTS', file:'assets/talents.js',
    shape:'single',
    blurb:'Abilities found in the world and the gates they open. Never bought — each one is the key to a kind of sealed route.',
    doc:'TALENTS — abilities found in the world, and the gates they open.\n\n   These are never bought. Each one is the key to a kind of sealed route, so\n   picking one up opens ground in stages already cleared. Upgrades are the\n   other half of progression and live in upgrades.js.' },

  { k:'upgrades', n:'Upgrades', ico:'▲', g:'ASSET_UPGRADES', file:'assets/upgrades.js',
    shape:'single',
    blurb:'The five stat tracks XP is spent on. Bought, unlike talents.',
    doc:'UPGRADES — the five stat tracks XP is spent on.\n\n   Bought, unlike talents. `cost` is per level and `maxLevel` was hardcoded\n   as a bare 5 in four places before this file existed.' },

  { k:'levels', n:'Levels & XP', ico:'◆', g:'ASSET_LEVELS', file:'assets/levels.js',
    shape:'single',
    blurb:'The fighter’s rank. `save.xp` is spendable and `save.xpTotal` is earned, so spending on upgrades never costs you a level.',
    doc:'LEVELS — the fighter’s rank, and what each one is worth.\n\n   Two currencies that are easy to confuse, so they are kept apart:\n     save.xp      is SPENDABLE — the training camp draws it down.\n     save.xpTotal is EARNED    — it only ever goes up, and drives the level.\n   Spending on upgrades therefore never costs you a level.' },

  { k:'weapons', n:'Weapons', ico:'⚒', g:'ASSET_WEAPONS', file:'assets/weapons.js',
    shape:'records',
    blurb:'What a smashed crate can put in your hands. Every one boosts punches only, never kicks — an armed Ahmed gives up the kick game.',
    doc:'WEAPONS — what a smashed crate can put in your hands.\n\n   Every one boosts punches only, never kicks. That is the whole design: an\n   armed Ahmed hits harder and further but gives up the kick game, so picking\n   one up is a choice rather than a straight upgrade. Uses are spent on swings\n   that connect, so whiffing costs nothing but time.' }
];

var FOOT = '\n   Loaded as a plain script before the game, so it works opened straight off\n   disk with no build step and no server. Edit the numbers here; the game\n   reads them and never keeps its own copy.\n   ========================================================================== */';

/* ------------------------------------------------------------------- state */
var D = {};            // live, editable copy — what export writes
var ORIG = {};         // pristine copy — what "changed" is measured against
var sel = 'ahmed';

function clone(v){
  if(typeof v === 'function') return v;                 // kept by reference
  if(Array.isArray(v)) return v.map(clone);
  if(v && typeof v === 'object'){
    var o = {}; for(var k in v) if(v.hasOwnProperty(k)) o[k] = clone(v[k]);
    return o;
  }
  return v;
}
function same(a, b){
  if(typeof a === 'function' || typeof b === 'function')
    return String(a) === String(b);
  if(a === b) return true;
  if(Array.isArray(a) !== Array.isArray(b)) return false;
  if(a && b && typeof a === 'object' && typeof b === 'object'){
    var ka = Object.keys(a), kb = Object.keys(b);
    if(ka.length !== kb.length) return false;
    for(var i=0;i<ka.length;i++) if(!same(a[ka[i]], b[ka[i]])) return false;
    return true;
  }
  return false;
}

function boot(){
  var missing = [];
  DOMAINS.forEach(function(d){
    if(!window[d.g]){ missing.push(d.file); return; }
    D[d.k] = clone(window[d.g]);
    ORIG[d.k] = clone(window[d.g]);
  });
  if(missing.length){
    document.querySelector('main').innerHTML =
      '<h2>Assets did not load</h2><p class="blurb">The panel could not find ' +
      missing.join(', ') + '. It has to sit in <code>panel/</code> beside ' +
      '<code>assets/</code> — open <code>panel/index.html</code> from inside ' +
      'the game folder rather than copying it elsewhere.</p>';
    return;
  }
  buildRail(); render();
}

function changedKeys(){
  return DOMAINS.filter(function(d){ return !same(D[d.k], ORIG[d.k]); })
                .map(function(d){ return d.k; });
}

/* --------------------------------------------------------------- the rail */
function buildRail(){
  var nav = document.getElementById('rail');
  nav.innerHTML = '<div class="railhead">TABLES</div>';
  DOMAINS.forEach(function(d){
    var b = document.createElement('button');
    b.className = 'tab' + (d.k === sel ? ' sel' : '');
    b.dataset.k = d.k;
    b.innerHTML = '<span class="ico">' + d.ico + '</span>' +
                  '<span class="n">' + d.n + '</span>' +
                  '<span class="ct"></span>';
    b.onclick = function(){ sel = d.k; buildRail(); render();
                            document.querySelector('main').scrollTop = 0; };
    nav.appendChild(b);
  });
  refreshRail();
}
function refreshRail(){
  var ch = changedKeys();
  [].forEach.call(document.querySelectorAll('.tab'), function(b){
    var d = byKey(b.dataset.k), ct = b.querySelector('.ct');
    var n = count(d);
    b.classList.toggle('warn', ch.indexOf(d.k) >= 0);
    ct.textContent = ch.indexOf(d.k) >= 0 ? 'EDITED' : n;
  });
  var any = ch.length > 0;
  var dot = document.getElementById('dirty');
  dot.className = 'dirty' + (any ? ' on' : '');
  dot.textContent = any ? ch.length + ' TABLE' + (ch.length>1?'S':'') + ' EDITED'
                        : 'NO CHANGES';
  document.getElementById('revert').disabled = !any;
}
function byKey(k){ for(var i=0;i<DOMAINS.length;i++) if(DOMAINS[i].k===k) return DOMAINS[i]; }
function count(d){
  var v = D[d.k];
  if(d.shape === 'records') return Object.keys(v).length;
  if(d.shape === 'array')   return v.length;
  return '·';
}

/* ------------------------------------------------------------ field editor
   Generated from the data's own shape rather than hand-written per table, so
   a field added to an asset file appears here without touching the panel.  */
var COLOUR = /^(#[0-9a-fA-F]{3,8}|rgba?\()/;

var HANDLED = { waves:1, layout:1, areas:1 };
function field(label, obj, key, path){
  var v = obj[key];
  if(HANDLED[key] && (path[0] === 'stages' || path[0] === 'world')){
    var skip = document.createElement('div');
    skip.style.display = 'none';
    return skip;
  }
  var f = document.createElement('div');
  f.className = 'f';
  var id = path.join('.') + '.' + key;

  if(v && typeof v === 'object' && !Array.isArray(v) && typeof v !== 'function'){
    var box = document.createElement('div');
    box.className = 'sub-obj';
    box.innerHTML = '<div class="lg">' + esc(key.toUpperCase()) + '</div>';
    var g = document.createElement('div'); g.className = 'grid';
    Object.keys(v).forEach(function(k2){ g.appendChild(field(k2, v, k2, path.concat(key))); });
    box.appendChild(g);
    return box;
  }

  var lab = document.createElement('label');
  lab.innerHTML = esc(label.toUpperCase()) + hintFor(id);
  f.appendChild(lab);

  var el, wrap = f;
  if(typeof v === 'boolean'){
    lab.remove();
    var c = document.createElement('label');
    c.className = 'chk' + (v ? ' on' : '');
    c.innerHTML = '<input type="checkbox"' + (v?' checked':'') + '><span>' +
                  esc(label) + '</span>';
    c.querySelector('input').onchange = function(){
      obj[key] = this.checked; c.classList.toggle('on', this.checked); touched();
    };
    f.appendChild(c);
    return f;
  }
  if(typeof v === 'function'){
    el = document.createElement('textarea');
    el.value = String(v).replace(/\n {2,4}/g, '\n  ');
    el.rows = Math.min(14, String(v).split('\n').length + 1);
    el.oninput = function(){
      var fn = null;
      try { fn = (new Function('return (' + this.value + ')'))(); } catch(e){}
      var ok = typeof fn === 'function';
      this.classList.toggle('bad', !ok);
      if(ok){ obj[key] = fn; obj[key].__src = this.value; touched(); }
    };
    f.style.gridColumn = '1/-1';
  } else if(Array.isArray(v)){
    el = document.createElement(v.some(isObj) || v.some(isProse) ? 'textarea' : 'input');
    if(v.some(isObj)){
      el.value = JSON.stringify(v, null, 1);
      el.rows = Math.min(16, JSON.stringify(v, null, 1).split('\n').length);
      f.style.gridColumn = '1/-1';
      el.oninput = function(){
        try { obj[key] = JSON.parse(this.value); this.classList.remove('bad'); touched(); }
        catch(e){ this.classList.add('bad'); }
      };
    } else if(v.some(isProse)){
      // Prose lines contain commas of their own, so splitting a joined string
      // on a comma would quietly cut a sentence in half every time it was
      // edited. One item per line is the only safe round-trip.
      el = document.createElement('textarea');
      el.value = v.join('\n');
      el.rows = Math.min(8, v.length + 1);
      f.style.gridColumn = '1/-1';
      el.oninput = function(){
        obj[key] = this.value.split('\n').filter(function(s){ return s.trim() !== ''; });
        touched();
      };
    } else {
      el.type = 'text';
      el.value = v.join(', ');
      el.oninput = function(){
        var parts = this.value.split(',').map(function(s){ return s.trim(); })
                              .filter(function(s){ return s !== ''; });
        obj[key] = v.every(isNum) ? parts.map(Number) : parts;
        touched();
      };
    }
  } else if(typeof v === 'number'){
    el = document.createElement('input');
    el.type = 'number';
    el.step = (Math.abs(v) < 3 && v % 1 !== 0) ? '0.01' : (v % 1 !== 0 ? '0.1' : '1');
    el.value = v;
    el.oninput = function(){
      if(this.value === ''){ return; }
      obj[key] = Number(this.value); touched();
    };
  } else if(v === null || v === undefined){
    el = document.createElement('input');
    el.type = 'text'; el.value = v === null ? 'null' : '';
    el.placeholder = 'null';
    el.oninput = function(){
      obj[key] = (this.value === '' || this.value === 'null') ? null : this.value;
      touched();
    };
  } else {
    el = document.createElement('input');
    el.type = 'text'; el.value = v;
    el.oninput = function(){ obj[key] = this.value; touched(); paintSwatch(); };
    if(COLOUR.test(v)){
      wrap = document.createElement('div'); wrap.className = 'colrow';
      var pick = document.createElement('input');
      pick.type = 'color'; pick.value = hexOf(v);
      pick.oninput = function(){ el.value = this.value; el.oninput(); };
      wrap.appendChild(pick); wrap.appendChild(el);
      f.appendChild(wrap);
      el.dataset.pair = '1';
      mark(el, obj, key, path);
      return f;
    }
  }
  f.appendChild(el);
  mark(el, obj, key, path);
  return f;
}
function isObj(v){ return v && typeof v === 'object' }
function isProse(v){ return typeof v === 'string' && (v.indexOf(',') >= 0 || v.length > 28); }
function isNum(v){ return typeof v === 'number' }
function mark(el, obj, key, path){
  var was = get(ORIG[sel], path.slice(1).concat(key));
  if(!same(was, obj[key])) el.classList.add('changed');
}
function get(o, path){
  for(var i=0;i<path.length && o != null;i++) o = o[path[i]];
  return o;
}
function hexOf(v){
  if(v[0] === '#'){
    var h = v.slice(1);
    if(h.length === 3) h = h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
    return '#' + h.slice(0,6);
  }
  var m = v.match(/-?\d+/g);
  if(!m || m.length < 3) return '#888888';
  return '#' + [0,1,2].map(function(i){
    return ('0' + Math.max(0, Math.min(255, +m[i])).toString(16)).slice(-2);
  }).join('');
}

/* A handful of fields do not explain themselves from their name alone. */
var HINTS = {
  'su':'startup s', 'ac':'active s', 'rc':'recovery s', 'push':'knockback',
  'stam':'stamina', 'rate':'attack gap s', 'sc':'draw scale', 'reach':'px',
  'len':'world px', 'at':'trigger x', 'z':'depth 0..1', 'pow':'damage x',
  'spd':'px/s', 'build':'limb thickness', 'dmg':'x on the punch',
  'uses':'connecting swings', 'mp':'MP cost', 'gateZ':'depth of sealed routes',
  'tier':'difficulty band', 'afterCleared':'area index', 'to':'area index'
};
function hintFor(id){
  var last = id.split('.').pop();
  return HINTS[last] ? ' <span class="hint">' + esc(HINTS[last]) + '</span>' : '';
}
function esc(s){ return String(s).replace(/[&<>"]/g, function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }

function touched(){ refreshRail(); insight(); }

/* --------------------------------------------------------------- rendering */
function render(){
  var d = byKey(sel), main = document.querySelector('main');
  main.innerHTML = '';
  var head = document.createElement('div');
  head.className = 'pagehead';
  head.innerHTML = '<h2>' + esc(d.n) + '</h2><span class="file">' + esc(d.file) + '</span>';
  main.appendChild(head);
  var p = document.createElement('p');
  p.className = 'blurb'; p.textContent = d.blurb;
  main.appendChild(p);

  if(d.k === 'world'){ worldEditor(main); insight(); return; }

  if(d.shape === 'records'){
    Object.keys(D[d.k]).forEach(function(id, i){
      main.appendChild(card(id, D[d.k][id], [d.k, id], i < 2));
    });
  } else if(d.shape === 'array'){
    D[d.k].forEach(function(row, i){
      var name = row.name || row.n || ('#' + i);
      main.appendChild(card(name, row, [d.k, i], i < 1, i));
    });
  } else {
    Object.keys(D[d.k]).forEach(function(id, i){
      var v = D[d.k][id];
      if(v && typeof v === 'object' && !Array.isArray(v)){
        main.appendChild(card(id, v, [d.k, id], true));
      } else {
        main.appendChild(loose(id, D[d.k], id, [d.k]));
      }
    });
  }
  insight();
}

function card(title, obj, path, open, idx){
  var det = document.createElement('details');
  det.className = 'card'; det.open = !!open;
  var sum = document.createElement('summary');
  var dot = (obj.col && obj.col.top) ? '<span class="swatchdot" style="background:' +
              esc(obj.col.top) + '"></span>' : '';
  var sub = obj.ar ? '<span class="sub">' + esc(obj.ar) + '</span>' : '';
  var tag = idx !== undefined ? '<span class="tag">INDEX ' + idx + '</span>'
          : (obj.n && obj.n !== title ? '<span class="tag">' + esc(obj.n) + '</span>' : '');
  sum.innerHTML = dot + '<span>' + esc(obj.name || title) + '</span>' + sub + tag;
  det.appendChild(sum);

  var inner = document.createElement('div'); inner.className = 'inner';
  var g = document.createElement('div'); g.className = 'grid';
  Object.keys(obj).forEach(function(k){ g.appendChild(field(k, obj, k, path)); });
  inner.appendChild(g);
  if(obj.col && obj.look) inner.appendChild(kit(obj));
  if(obj.waves) inner.appendChild(waveEditor(obj));
  det.appendChild(inner);
  return det;
}
function loose(title, obj, key, path){
  var det = document.createElement('details');
  det.className = 'card'; det.open = true;
  det.innerHTML = '<summary><span>' + esc(title) + '</span></summary>';
  var inner = document.createElement('div'); inner.className = 'inner';
  var g = document.createElement('div'); g.className = 'grid';
  g.appendChild(field(key, obj, key, path));
  inner.appendChild(g); det.appendChild(inner);
  return det;
}

/* ------------------------------------------------------------ kit preview
   Not the game's renderer -- that lives inside the game and duplicating it
   here would guarantee the two drift apart. This is the honest subset: the
   palette, and a proportion figure driven by the same `build` and `sc` the
   renderer uses, so you can see what a silhouette change does. */
function kit(o){
  var w = document.createElement('div'); w.className = 'kit';
  var cv = document.createElement('canvas');
  cv.width = 150; cv.height = 200; w.appendChild(cv);
  drawKit(cv, o);

  var col = document.createElement('div'); col.className = 'kitcol';
  Object.keys(o.col).forEach(function(k){
    var r = document.createElement('div'); r.className = 'sw';
    r.innerHTML = '<b style="background:' + esc(o.col[k]) + '"></b>' +
                  esc(k) + ' <span style="opacity:.5">' + esc(o.col[k]) + '</span>';
    col.appendChild(r);
  });
  w.appendChild(col);

  var flags = Object.keys(o.look).filter(function(k){ return o.look[k] === true; });
  var col2 = document.createElement('div'); col2.className = 'kitcol';
  col2.innerHTML = '<div class="sw" style="color:var(--gold)">KIT</div>' +
    (flags.length ? flags.map(function(f){ return '<div class="sw">· ' + esc(f) + '</div>'; }).join('')
                  : '<div class="sw" style="opacity:.4">none</div>') +
    (o.look.hands ? '<div class="sw">· hands: ' + esc(o.look.hands) + '</div>' : '') +
    '<div class="sw">· build ' + (o.look.build || 1) + '</div>';
  w.appendChild(col2);
  return w;
}
function drawKit(cv, o){
  var g = cv.getContext('2d'), b = o.look.build || 1, s = (o.sc || 1);
  g.clearRect(0,0,150,200);
  g.save(); g.translate(75, 186); g.scale(s, s);
  var c = o.col;
  function limb(x1,y1,x2,y2,r,col){
    g.strokeStyle = col; g.lineWidth = r*2*b; g.lineCap = 'round';
    g.beginPath(); g.moveTo(x1,y1); g.lineTo(x2,y2); g.stroke();
  }
  limb(-9,-2,-9,-52, 7, c.bottom); limb(9,-2,9,-52, 7, c.bottom);   // legs
  g.fillStyle = c.top;                                              // torso
  g.beginPath();
  g.moveTo(-16*b,-52); g.lineTo(16*b,-52); g.lineTo(19*b,-108);
  g.lineTo(-19*b,-108); g.closePath(); g.fill();
  limb(-19*b,-104,-25*b,-64, 5.5, o.look.tee ? c.top : c.skin);     // arms
  limb(19*b,-104,25*b,-64, 5.5, o.look.tee ? c.top : c.skin);
  g.fillStyle = c.skin;                                             // hands
  g.beginPath(); g.arc(-25*b,-60,5.5*b,0,6.283); g.fill();
  g.beginPath(); g.arc(25*b,-60,5.5*b,0,6.283); g.fill();
  g.beginPath(); g.arc(0,-124,15,0,6.283); g.fill();                // head
  if(!o.look.bald){                                                 // hair
    g.fillStyle = o.look.hair || '#1e150f';
    g.beginPath(); g.arc(0,-127,15,Math.PI*1.06,Math.PI*1.94); g.fill();
  }
  if(o.look.band || c.band){                                        // waist band
    g.fillStyle = c.band; g.fillRect(-16*b,-56,32*b,5);
  }
  g.restore();
  g.fillStyle = 'rgba(255,255,255,.16)';
  g.fillRect(0, 190, 150, 1);
}
function paintSwatch(){
  [].forEach.call(document.querySelectorAll('.kit'), function(w){});
}

/* ==========================================================================
   INSIGHT
   The half you cannot get from a text editor. Everything below is computed
   live from the tables as edited, so a number you change moves these while
   you are still looking at it.
   ========================================================================== */
function T(h){ return h.su + h.ac + h.rc; }

/* Ahmed's sustained damage over a full chain, at a given upgrade level. A
   single strike's damage says nothing -- what matters is damage per second of
   commitment, recovery included. */
function chainDPS(keys, lvl){
  var dmg = 0, t = 0;
  keys.forEach(function(k){
    var h = D.hits[k]; if(!h) return;
    dmg += h.dmg * (1 + 0.10 * lvl); t += T(h);
  });
  return t ? dmg / t : 0;
}
function playerDPS(boxLvl, kickLvl){
  return Math.max(chainDPS(['jab','cross','hook'], boxLvl||0),
                  chainDPS(['kick','knee'], kickLvl||0));
}
/* What an enemy puts out: its move cycle, scaled by pow, with its own gap
   between attacks. */
function enemyDPS(e){
  var dmg = 0, t = 0;
  (e.moves||[]).forEach(function(k){
    var h = D.hits[k]; if(!h) return;
    dmg += h.dmg * e.pow; t += T(h) + e.rate;
  });
  return t ? dmg / t : 0;
}
function ahmedHP(level, vit){
  return D.ahmed.base.hp + D.ahmed.perLevel.vit * (vit||0) +
         D.levels.perLevel.hp * Math.max(0, (level||1) - 1);
}
/* Everything the campaign pays out, once: every enemy in every wave of every
   non-survival stage, plus the XP sitting behind gates. */
function campaignXP(){
  var xp = 0;
  D.stages.forEach(function(st){
    if(st.survival) return;
    (st.waves||[]).forEach(function(w){
      (w.e||[]).forEach(function(pair){
        var e = D.enemies[pair[0]];
        if(e) xp += e.xp * pair[1];
      });
    });
    (st.gates||[]).forEach(function(gt){
      if(gt.reward && gt.reward.xp) xp += gt.reward.xp;
    });
  });
  return xp;
}
function maxUpgradeCost(){
  var per = 0;
  for(var l=0; l<D.upgrades.maxLevel; l++) per += D.upgrades.cost(l);
  return per * D.upgrades.tracks.length;
}
function xpToMaxLevel(){ return D.levels.need(D.levels.max); }

/* ---- world graph: the two checks that matter -------------------------- */
var SIDES = ['w','e','d'], BACK = {w:'e', e:'w', d:'w'};
function worldAudit(){
  var W = D.world, bad = [], names = W.layout.map(function(l){ return l.n; });
  W.areas.forEach(function(a, i){
    SIDES.forEach(function(s){
      var link = a[s]; if(!link) return;
      if(link.to == null || !W.areas[link.to]){
        bad.push(names[i] + ' ' + s + ' leads nowhere'); return;
      }
      // find any link on the far side that points back here
      var back = null, far = W.areas[link.to];
      SIDES.forEach(function(s2){ if(far[s2] && far[s2].to === i) back = far[s2]; });
      if(!back){ bad.push(names[i] + ' → ' + names[link.to] + ' is one-way'); return; }
      if((back.needs || null) !== (link.needs || null))
        bad.push(names[i] + ' ⇄ ' + names[link.to] + ' wants different talents each way');
      if((back.afterCleared === undefined) !== (link.afterCleared === undefined))
        bad.push(names[i] + ' ⇄ ' + names[link.to] + ' is conditional one way only');
    });
  });
  return bad;
}
/* Can a cold start reach everything? Walk to a fixpoint: an area you can
   stand in gives up the talents behind gates you can already open, and those
   talents open more routes. Anything still unreached cannot be played. */
function reachability(){
  var W = D.world, got = {}, seen = {}, cleared = {}, moved = true;
  seen[W.start] = cleared[W.start] = true;
  while(moved){
    moved = false;
    Object.keys(seen).forEach(function(k){
      var i = +k, st = D.stages[i];
      (st && st.gates || []).forEach(function(gt){
        var spec = D.talents.gates[gt.type];
        if(spec && spec.need && !got[spec.need]) return;
        if(gt.reward && gt.reward.ability && !got[gt.reward.ability]){
          got[gt.reward.ability] = true; moved = true;
        }
      });
      SIDES.forEach(function(s){
        var link = W.areas[i] && W.areas[i][s]; if(!link) return;
        if(link.needs && !got[link.needs]) return;
        if(link.afterCleared !== undefined && !cleared[link.afterCleared]) return;
        if(!seen[link.to]){ seen[link.to] = cleared[link.to] = true; moved = true; }
      });
    });
  }
  return { seen:seen, got:got,
           lost:W.layout.map(function(l,i){ return i; })
                        .filter(function(i){ return !seen[i]; })
                        .map(function(i){ return W.layout[i].n; }),
           unfound:Object.keys(D.talents.abilities)
                         .filter(function(a){ return !got[a]; }) };
}

/* ------------------------------------------------------------ insight view */
function insight(){
  var a = document.querySelector('aside');
  var fns = { hits:iHits, enemies:iEnemies, levels:iLevels, upgrades:iUpgrades,
              world:iWorld, stages:iStages, weapons:iWeapons, ahmed:iAhmed,
              talents:iTalents };
  try { a.innerHTML = (fns[sel] || function(){ return ''; })(); }
  catch(e){ a.innerHTML = '<h3>DERIVED</h3><p class="note">Cannot compute — a ' +
    'field is mid-edit and does not parse yet.</p>'; }
  [].forEach.call(a.querySelectorAll('canvas[data-plot]'), function(c){
    plot(c, JSON.parse(c.dataset.plot), c.dataset.lab);
  });
}
function m(label, val, cls){
  return '<div class="metric"><span>' + label + '</span><b' +
         (cls ? ' class="' + cls + '"' : '') + '>' + val + '</b></div>';
}
function bar(v, max, cls){
  var p = Math.max(0, Math.min(100, max ? v/max*100 : 0));
  return '<div class="bar"><i class="' + (cls||'') + '" style="width:' +
         p.toFixed(1) + '%"></i></div>';
}
function n1(v){ return (Math.round(v*10)/10).toFixed(1); }
function n0(v){ return Math.round(v).toLocaleString(); }

function iHits(){
  var keys = Object.keys(D.hits);
  var rows = keys.map(function(k){
    var h = D.hits[k];
    return { k:k, dps:h.dmg/T(h), t:T(h), commit:h.rc/T(h),
             perStam:h.stam ? h.dmg/h.stam : Infinity, h:h };
  });
  var maxD = Math.max.apply(null, rows.map(function(r){ return r.dps; }));
  var out = '<h3>DAMAGE PER SECOND</h3><p class="note">Damage alone ranks every ' +
    'strike in dmg order and tells you nothing. What decides whether a move is ' +
    'worth throwing is damage over the whole window it commits you for — ' +
    'startup, active and recovery together.</p><table class="t"><tr><th>MOVE</th>' +
    '<th class="r">DPS</th><th class="r">WINDOW</th><th></th></tr>';
  rows.sort(function(x,y){ return y.dps - x.dps; }).forEach(function(r){
    out += '<tr><td class="k">' + r.k + '</td><td class="r">' + n1(r.dps) +
           '</td><td class="r">' + r.t.toFixed(2) + 's</td><td>' +
           bar(r.dps, maxD, r.h.heavy ? 'hot' : '') + '</td></tr>';
  });
  out += '</table><h3 style="margin-top:22px">PUNISHABILITY</h3>' +
    '<p class="note">Recovery as a share of the whole window. Above about half ' +
    'and a whiff hands the other fighter a free hit, which is what should make ' +
    'a heavy a decision rather than a default.</p><table class="t">';
  rows.sort(function(x,y){ return y.commit - x.commit; }).forEach(function(r){
    out += '<tr><td class="k">' + r.k + '</td><td class="r">' +
           Math.round(r.commit*100) + '%</td><td>' +
           bar(r.commit, 1, r.commit > 0.5 ? 'hot' : 'ok') + '</td></tr>';
  });
  out += '</table>' + m('Punch chain DPS', n1(playerDPS(0,0))) +
         m('…at max BOXING', n1(chainDPS(['jab','cross','hook'], D.upgrades.maxLevel))) +
         m('Kick chain DPS', n1(chainDPS(['kick','knee'], 0))) +
         m('…at max KICKING', n1(chainDPS(['kick','knee'], D.upgrades.maxLevel)));
  return out;
}

function iEnemies(){
  var dps = playerDPS(0,0), dpsMax = playerDPS(D.upgrades.maxLevel, D.upgrades.maxLevel);
  var rows = Object.keys(D.enemies).map(function(k){
    var e = D.enemies[k], ttk = e.hp / dps, edps = enemyDPS(e);
    return { k:k, e:e, ttk:ttk, ttkMax:e.hp/dpsMax, edps:edps,
             threat:edps*ttk, xpRate:e.xp/ttk };
  });
  var maxT = Math.max.apply(null, rows.map(function(r){ return r.threat; }));
  var hp1 = ahmedHP(1, 0), hpMax = ahmedHP(D.levels.max, D.upgrades.maxLevel);
  var out = '<h3>THREAT</h3><p class="note">How much health one of these takes ' +
    'off you before it goes down, one on one — its damage output multiplied by ' +
    'how long it survives. This is the number that says whether an archetype is ' +
    'dangerous, and it is not the same ranking as HP.</p>' +
    '<table class="t"><tr><th>ENEMY</th><th class="r">TTK</th>' +
    '<th class="r">COSTS</th><th></th></tr>';
  rows.sort(function(x,y){ return y.threat - x.threat; }).forEach(function(r){
    var over = r.threat > hp1;
    out += '<tr><td class="k">' + r.k + '</td><td class="r">' + n1(r.ttk) +
           's</td><td class="r"' + (over ? ' style="color:#ff8298"' : '') + '>' +
           n0(r.threat) + '</td><td>' + bar(r.threat, maxT, over?'hot':'') +
           '</td></tr>';
  });
  out += '</table>' +
    m('Ahmed HP, level 1', n0(hp1)) +
    m('Ahmed HP, fully built', n0(hpMax)) +
    m('Player DPS, level 1', n1(dps)) +
    m('Player DPS, maxed', n1(dpsMax));
  var deadly = rows.filter(function(r){ return r.threat > hp1; });
  out += deadly.length
    ? '<div class="verdict warn"><b>ONE-ON-ONE LETHAL AT LEVEL 1</b>' +
      deadly.map(function(r){ return r.k; }).join(', ') + ' would take a fresh ' +
      'Ahmed down alone if he never blocked or dodged. Fine for a boss, worth ' +
      'a look on anything that spawns in a first wave.</div>'
    : '<div class="verdict ok"><b>SURVIVABLE</b>A level-1 Ahmed can out-trade ' +
      'every archetype one on one, so difficulty comes from numbers and ' +
      'position rather than from a single enemy being unfair.</div>';
  out += '<h3 style="margin-top:20px">XP PER SECOND</h3><p class="note">What each ' +
    'archetype pays for the time it takes. Wide gaps here are what make one ' +
    'stage feel like the efficient grind.</p><table class="t">';
  var maxX = Math.max.apply(null, rows.map(function(r){ return r.xpRate; }));
  rows.sort(function(x,y){ return y.xpRate - x.xpRate; }).forEach(function(r){
    out += '<tr><td class="k">' + r.k + '</td><td class="r">' + n1(r.xpRate) +
           '</td><td>' + bar(r.xpRate, maxX, 'cool') + '</td></tr>';
  });
  return out + '</table>';
}

function iLevels(){
  var L = D.levels, pts = [], cum = [];
  for(var i=1;i<=L.max;i++){ pts.push(L.need(i)); }
  for(i=1;i<L.max;i++) cum.push(L.need(i+1) - L.need(i));
  var total = L.need(L.max), camp = campaignXP();
  var out = '<h3>THE CURVE</h3><p class="note">Cumulative XP needed to reach each ' +
    'level. Flat early is what lets the first two areas feel like progress; the ' +
    'climb is what makes the last levels mean something.</p>' +
    '<canvas class="chart" data-plot="' + esc(JSON.stringify(pts)) +
    '" data-lab="XP TO REACH LEVEL n"></canvas>' +
    m('XP to level ' + L.max, n0(total)) +
    m('Campaign pays out', n0(camp), camp >= total ? 'good' : 'warn') +
    m('Step, level 2', n0(L.need(2))) +
    m('Step, level ' + L.max, n0(L.need(L.max) - L.need(L.max-1)));
  var ratio = camp / total;
  out += '<div class="verdict ' + (ratio >= 1 ? 'ok' : ratio >= 0.7 ? 'warn' : 'bad') +
    '"><b>ONE CLEAN RUN REACHES LEVEL ' + levelFrom(camp) + '</b>' +
    'Killing everything once in all nine areas earns ' + n0(camp) + ' XP, which is ' +
    (ratio*100).toFixed(0) + '% of what level ' + L.max + ' costs. ' +
    (ratio >= 1 ? 'The cap is reachable without replaying anything.'
                : 'Reaching the cap needs replays or survival, which is a choice, ' +
                  'not a bug — but it should be a choice you made.') + '</div>';
  out += '<h3 style="margin-top:18px">TITLES</h3><table class="t">';
  var last = null;
  for(i=1;i<=L.max;i++){
    var t = L.title(i);
    if(t !== last){ out += '<tr><td class="k">' + esc(t) + '</td><td class="r">from ' +
      i + '</td><td class="r">' + n0(L.need(i)) + ' XP</td></tr>'; last = t; }
  }
  return out + '</table>';
}
function levelFrom(xp){
  var L = D.levels, n = 1;
  while(n < L.max && xp >= L.need(n+1)) n++;
  return n;
}

function iUpgrades(){
  var U = D.upgrades, camp = campaignXP(), full = maxUpgradeCost();
  var perTrack = 0, steps = [];
  for(var l=0;l<U.maxLevel;l++){ perTrack += U.cost(l); steps.push(U.cost(l)); }
  var out = '<h3>THE BILL</h3><p class="note">XP is one pool: what the training ' +
    'camp takes is not available for anything else. The question this table ' +
    'answers is whether a player who fights everything can afford everything.</p>' +
    m('One track to max', n0(perTrack)) +
    m('All ' + U.tracks.length + ' tracks', n0(full)) +
    m('Campaign pays out', n0(camp), camp >= full ? 'good' : 'warn') +
    m('Shortfall', camp >= full ? 'none' : n0(full - camp),
      camp >= full ? 'good' : 'bad');
  var pct = camp / full;
  out += '<div class="verdict ' + (pct >= 1 ? 'ok' : pct >= 0.55 ? 'warn' : 'bad') +
    '"><b>' + (pct >= 1 ? 'EVERYTHING IS AFFORDABLE' : 'A RUN BUYS ' +
      Math.round(pct*100) + '% OF THE TREE') + '</b>' +
    (pct >= 1
      ? 'One clean campaign pays for every track at every level, so the training ' +
        'camp stops being a choice. If you want builds to matter, this should be ' +
        'below 100%.'
      : 'One clean campaign buys about ' + Math.round(pct*U.tracks.length*10)/10 +
        ' tracks’ worth. That is what makes spending a decision.') + '</div>';
  out += '<h3 style="margin-top:18px">COST PER LEVEL</h3><table class="t">';
  steps.forEach(function(c, i){
    out += '<tr><td class="k">level ' + (i+1) + '</td><td class="r">' + n0(c) +
           '</td><td>' + bar(c, steps[steps.length-1]) + '</td></tr>';
  });
  out += '</table><h3 style="margin-top:18px">TRACKS</h3><table class="t">';
  U.tracks.forEach(function(t){
    out += '<tr><td class="k">' + esc(t.n) + '</td><td>' + esc(t.d) + '</td></tr>';
  });
  return out + '</table>';
}

function iWorld(){
  var bad = worldAudit(), r = reachability(), W = D.world;
  var out = '<h3>GRAPH AUDIT</h3><p class="note">Every link has to be two-way and ' +
    'both halves have to want the same talent. A route sealed from one side only ' +
    'is how a player ends up somewhere they cannot leave.</p>';
  out += bad.length
    ? '<div class="verdict bad"><b>' + bad.length + ' PROBLEM' +
      (bad.length>1?'S':'') + '</b>' + bad.map(esc).join('<br>') + '</div>'
    : '<div class="verdict ok"><b>SYMMETRIC</b>All ' + linkCount() + ' links are ' +
      'two-way and carry the same requirement from both sides.</div>';
  out += '<h3>COMPLETABILITY</h3><p class="note">Walked from a cold start: an area ' +
    'you can stand in gives up the talents behind gates you can already open, and ' +
    'those open more routes. Anything left over cannot be played at all.</p>';
  out += r.lost.length
    ? '<div class="verdict bad"><b>UNREACHABLE</b>' + r.lost.map(esc).join(', ') +
      ' cannot be reached from the start.</div>'
    : '<div class="verdict ok"><b>ALL ' + W.layout.length + ' AREAS REACHABLE</b>' +
      'A cold start can reach every area and pick up ' +
      Object.keys(r.got).length + ' of ' +
      Object.keys(D.talents.abilities).length + ' talents.</div>';
  if(r.unfound.length)
    out += '<div class="verdict warn"><b>NEVER FOUND</b>' +
      r.unfound.map(esc).join(', ') + ' — no reachable gate awards ' +
      (r.unfound.length>1?'these':'this') + '.</div>';

  out += '<h3 style="margin-top:18px">ROUTES</h3><table class="t"><tr><th>FROM</th>' +
    '<th>TO</th><th>NEEDS</th></tr>';
  W.areas.forEach(function(a, i){
    SIDES.forEach(function(s){
      var link = a[s];
      if(!link || link.to < i) return;               // one row per pair
      out += '<tr><td class="k">' + esc(W.layout[i].n) + '</td><td>' +
             esc((W.layout[link.to]||{}).n || '?') + '</td><td' +
             (link.needs ? ' style="color:var(--gold)"' : '') + '>' +
             esc(link.needs || '—') + (link.afterCleared !== undefined
               ? ' <span style="opacity:.6">+clear ' +
                 esc((W.layout[link.afterCleared]||{}).n||'?') + '</span>' : '') +
             '</td></tr>';
    });
  });
  return out + '</table>';
}
function linkCount(){
  var n = 0;
  D.world.areas.forEach(function(a){ SIDES.forEach(function(s){ if(a[s]) n++; }); });
  return n / 2 | 0;
}

function iStages(){
  var dps = playerDPS(0,0);
  var rows = D.stages.map(function(st, i){
    var hp = 0, xp = 0, n = 0;
    (st.waves||[]).forEach(function(w){
      (w.e||[]).forEach(function(p){
        var e = D.enemies[p[0]]; if(!e) return;
        hp += e.hp * p[1]; xp += e.xp * p[1]; n += p[1];
      });
    });
    (st.gates||[]).forEach(function(g){ if(g.reward && g.reward.xp) xp += g.reward.xp; });
    return { i:i, st:st, hp:hp, xp:xp, n:n, fight:hp/dps };
  });
  var live = rows.filter(function(r){ return !r.st.survival; });
  var maxHP = Math.max.apply(null, live.map(function(r){ return r.hp; }));
  var out = '<h3>DIFFICULTY RAMP</h3><p class="note">Total enemy health per area, ' +
    'which is the closest single number to how long an area takes. It should ' +
    'climb — a dip means an area plays as a rest whether you meant it to or not.</p>' +
    '<canvas class="chart" data-plot="' +
    esc(JSON.stringify(live.map(function(r){ return r.hp; }))) +
    '" data-lab="ENEMY HP PER AREA"></canvas>';
  out += '<table class="t"><tr><th>AREA</th><th class="r">FOES</th>' +
    '<th class="r">FIGHT</th><th class="r">XP</th></tr>';
  rows.forEach(function(r){
    out += '<tr><td class="k">' + esc(r.st.name) + '</td><td class="r">' + r.n +
           '</td><td class="r">' + (r.st.survival ? '∞' : n0(r.fight) + 's') +
           '</td><td class="r">' + n0(r.xp) + '</td></tr>';
  });
  out += '</table>';
  var dips = [];
  for(var i=1;i<live.length;i++) if(live[i].hp < live[i-1].hp * 0.92)
    dips.push(live[i].st.name);
  out += dips.length
    ? '<div class="verdict warn"><b>THE RAMP DIPS</b>' + dips.map(esc).join(', ') +
      ' hold less enemy health than the area before. Deliberate breathers are ' +
      'fine; accidental ones read as the game losing interest.</div>'
    : '<div class="verdict ok"><b>MONOTONIC</b>Every area holds at least as much ' +
      'enemy health as the one before it.</div>';
  out += m('Campaign XP total', n0(campaignXP())) +
         m('Total fight time', n0(live.reduce(function(a,r){ return a+r.fight; },0)/60) + ' min');
  return out;
}

function iWeapons(){
  var base = D.hits.cross, out = '<h3>ARMED VS BARE</h3><p class="note">Every ' +
    'weapon multiplies punches and none of them touch kicks, so picking one up ' +
    'trades the kick game away. These are the cross, swung with each.</p>' +
    '<table class="t"><tr><th>WEAPON</th><th class="r">CROSS</th>' +
    '<th class="r">REACH</th><th class="r">TOTAL</th></tr>' +
    '<tr><td class="k">bare</td><td class="r">' + base.dmg + '</td><td class="r">' +
    base.reach + '</td><td class="r">—</td></tr>';
  Object.keys(D.weapons).forEach(function(k){
    var w = D.weapons[k];
    out += '<tr><td class="k">' + esc(w.n) + '</td><td class="r">' +
           n1(base.dmg*w.dmg) + '</td><td class="r">' + (base.reach + w.reach) +
           '</td><td class="r">' + n0(base.dmg*w.dmg*w.uses) + '</td></tr>';
  });
  out += '</table><p class="note">TOTAL is everything a weapon can deal before it ' +
    'gives out — the number that decides whether picking one up is worth losing ' +
    'the kick game for.</p>';
  var kickDPS = chainDPS(['kick','knee'], 0);
  out += m('Kick chain DPS given up', n1(kickDPS));
  Object.keys(D.weapons).forEach(function(k){
    var w = D.weapons[k];
    var armed = chainDPS(['jab','cross','hook'], 0) * w.dmg;
    out += m(w.n + ' punch DPS', n1(armed), armed > kickDPS ? 'good' : 'bad');
  });
  return out;
}

function iAhmed(){
  var A = D.ahmed, U = D.upgrades, L = D.levels;
  var out = '<h3>THE BUILD</h3><p class="note">Level one against a fully built, ' +
    'fully levelled Ahmed. The gap is how much of the game is progression rather ' +
    'than the player getting better.</p>' +
    '<table class="t"><tr><th>STAT</th><th class="r">START</th>' +
    '<th class="r">MAXED</th><th class="r">×</th></tr>';
  var pairs = [
    ['Health', A.base.hp, ahmedHP(L.max, U.maxLevel)],
    ['Stamina', A.base.stam, A.base.stam + A.perLevel.stam * U.maxLevel],
    ['Speed', A.base.spd, A.base.spd + A.perLevel.spd * U.maxLevel],
    ['MP', A.base.mp, A.base.mp + L.perLevel.mp * (L.max - 1)],
    ['Punch DPS', playerDPS(0,0), playerDPS(U.maxLevel, U.maxLevel)]
  ];
  pairs.forEach(function(p){
    out += '<tr><td class="k">' + p[0] + '</td><td class="r">' + n0(p[1]) +
           '</td><td class="r">' + n0(p[2]) + '</td><td class="r" ' +
           'style="color:var(--gold)">' + n1(p[2]/p[1]) + '</td></tr>';
  });
  out += '</table>' + m('MP regen, idle', A.mpRegen.idle + '/s') +
         m('MP regen, per hit', '+' + A.mpRegen.onHit) +
         m('HAWK FIST costs', (D.talents.abilities.hawk||{}).mp + ' MP');
  var hawk = (D.talents.abilities.hawk||{}).mp || 0;
  var sustain = hawk ? A.mpRegen.idle / hawk : 0;
  out += '<div class="verdict ' + (sustain < 0.6 ? 'ok' : 'warn') + '"><b>HAWK FIST ' +
    'UPTIME</b>Idle regen alone pays for a flaming punch every ' +
    n1(hawk / Math.max(0.01, A.mpRegen.idle)) + 's. Landed hits give ' +
    A.mpRegen.onHit + ' back each, so staying in the fight is what keeps it lit — ' +
    'which is the point.</div>';
  return out;
}

function iTalents(){
  var r = reachability();
  var out = '<h3>WHERE THEY COME FROM</h3><p class="note">Talents are found, not ' +
    'bought. Each one is the key to a kind of gate, so the order they appear in ' +
    'sets the order the world opens.</p><table class="t">' +
    '<tr><th>TALENT</th><th>FOUND IN</th><th>OPENS</th></tr>';
  Object.keys(D.talents.abilities).forEach(function(k){
    var where = '—';
    D.stages.forEach(function(st, i){
      (st.gates||[]).forEach(function(g){
        if(g.reward && g.reward.ability === k) where = st.name;
      });
    });
    var opens = Object.keys(D.talents.gates).filter(function(g){
      return D.talents.gates[g].need === k;
    }).map(function(g){ return D.talents.gates[g].n; }).join(', ') || '—';
    out += '<tr><td class="k">' + esc(D.talents.abilities[k].n) + '</td><td>' +
           esc(where) + '</td><td>' + esc(opens) + '</td></tr>';
  });
  out += '</table>';
  var orphan = Object.keys(D.talents.abilities).filter(function(k){
    var found = false;
    D.stages.forEach(function(st){ (st.gates||[]).forEach(function(g){
      if(g.reward && g.reward.ability === k) found = true; }); });
    return !found;
  });
  out += orphan.length
    ? '<div class="verdict bad"><b>NOT PLACED</b>' + orphan.map(esc).join(', ') +
      ' is not the reward of any gate in any stage, so it can never be picked up.</div>'
    : '<div class="verdict ok"><b>ALL PLACED</b>Every talent is the reward of a ' +
      'gate somewhere, and a cold start can reach ' + Object.keys(r.got).length +
      ' of them.</div>';
  return out;
}

/* A small line plot — enough to see a curve's shape, which is the only thing
   a curve needs to be judged on. */
function plot(cv, pts, label){
  var w = cv.width = cv.clientWidth * 2, h = cv.height = cv.clientHeight * 2;
  var g = cv.getContext('2d');
  g.clearRect(0,0,w,h);
  if(!pts.length) return;
  var pad = 22, max = Math.max.apply(null, pts) || 1;
  g.strokeStyle = 'rgba(255,255,255,.08)'; g.lineWidth = 2;
  for(var i=0;i<=3;i++){
    var y = pad + (h-pad*2) * i/3;
    g.beginPath(); g.moveTo(pad, y); g.lineTo(w-pad, y); g.stroke();
  }
  function X(i){ return pad + (w-pad*2) * (pts.length<2?0.5:i/(pts.length-1)); }
  function Y(v){ return h - pad - (h-pad*2) * (v/max); }
  var grd = g.createLinearGradient(0, pad, 0, h-pad);
  grd.addColorStop(0, 'rgba(237,190,87,.34)');
  grd.addColorStop(1, 'rgba(237,190,87,0)');
  g.beginPath(); g.moveTo(X(0), h-pad);
  pts.forEach(function(v,i){ g.lineTo(X(i), Y(v)); });
  g.lineTo(X(pts.length-1), h-pad); g.closePath();
  g.fillStyle = grd; g.fill();
  g.beginPath();
  pts.forEach(function(v,i){ i ? g.lineTo(X(i), Y(v)) : g.moveTo(X(i), Y(v)); });
  g.strokeStyle = '#edbe57'; g.lineWidth = 4; g.lineJoin = 'round'; g.stroke();
  g.fillStyle = '#edbe57';
  pts.forEach(function(v,i){ g.beginPath(); g.arc(X(i), Y(v), 4, 0, 6.283); g.fill(); });
  g.fillStyle = 'rgba(244,241,232,.42)';
  g.font = '600 17px system-ui, sans-serif';
  g.fillText(label || '', pad, 20);
  g.textAlign = 'right';
  g.fillText(n0(max), w-pad, 20);
}

/* ==========================================================================
   EXPORT
   The panel never writes to disk on its own. It hands you the file, you
   choose what to keep. Output is regenerated rather than patched, so the
   formatting is the panel's rather than byte-for-byte what you had.
   ========================================================================== */
function q(s){
  return "'" + String(s).replace(/\\/g,'\\\\').replace(/'/g,"\\'")
                        .replace(/\n/g,'\\n') + "'";
}
function lit(v, ind, wide){
  if(typeof v === 'function') return (v.__src || String(v)).replace(/\n/g, '\n' + ind);
  if(v === null) return 'null';
  if(typeof v === 'number' || typeof v === 'boolean') return String(v);
  if(typeof v === 'string') return q(v);
  if(Array.isArray(v)){
    var flat = v.every(function(x){ return x === null || typeof x !== 'object'; });
    if(flat) return '[' + v.map(function(x){ return lit(x, ind); }).join(',') + ']';
    var inner = ind + '  ';
    return '[\n' + inner + v.map(function(x){ return lit(x, inner, wide); })
                            .join(',\n' + inner) + '\n' + ind + ']';
  }
  var keys = Object.keys(v);
  if(!keys.length) return '{}';
  // Small flat records stay on one line, the way the hand-written files have
  // them; anything with nesting breaks out so it stays readable.
  var flatObj = keys.every(function(k){
    var x = v[k];
    return x === null || typeof x !== 'object' || (Array.isArray(x) &&
           x.every(function(y){ return y === null || typeof y !== 'object'; }));
  });
  if(flatObj && !wide && keys.length <= 12)
    return '{' + keys.map(function(k){ return key(k) + ':' + lit(v[k], ind); }).join(', ') + '}';
  var inner2 = ind + '  ';
  return '{\n' + inner2 + keys.map(function(k){
    return key(k) + ': ' + lit(v[k], inner2);
  }).join(',\n' + inner2) + '\n' + ind + '}';
}
function key(k){ return /^[A-Za-z_$][\w$]*$/.test(k) ? k : q(k); }

function serialize(d){
  var head = '/* AHMED — Kuwait Fighter\n   ' + d.doc + '\n' + FOOT + '\n';
  var v = D[d.k], body;
  if(d.shape === 'records'){
    body = 'window.' + d.g + ' = {\n' + Object.keys(v).map(function(k){
      return '  ' + key(k) + ': ' + lit(v[k], '  ');
    }).join(',\n\n') + '\n};\n';
  } else if(d.shape === 'array'){
    body = 'window.' + d.g + ' = [\n' + v.map(function(row){
      return '  ' + lit(row, '  ', true);
    }).join(',\n\n') + '\n];\n';
  } else {
    body = 'window.' + d.g + ' = ' + lit(v, '', true) + ';\n';
  }
  return head + body;
}

var exportSel = null;
function openExport(only){
  var ch = changedKeys();
  var list = only ? [only] : (ch.length ? ch : DOMAINS.map(function(d){ return d.k; }));
  exportSel = list[0];
  var files = document.getElementById('exfiles');
  files.innerHTML = '';
  list.forEach(function(k){
    var d = byKey(k), b = document.createElement('button');
    b.textContent = d.file.replace('assets/','');
    b.className = k === exportSel ? 'sel' : '';
    b.onclick = function(){ exportSel = k; showExport(); };
    files.appendChild(b);
  });
  document.getElementById('exlist').textContent =
    list.length + ' file' + (list.length>1?'s':'') +
    (ch.length ? ' · ' + ch.length + ' edited' : ' · nothing edited yet');
  showExport();
  document.getElementById('modal').classList.add('on');
}
function showExport(){
  [].forEach.call(document.querySelectorAll('#exfiles button'), function(b, i){
    b.classList.toggle('sel', b.textContent === byKey(exportSel).file.replace('assets/',''));
  });
  document.getElementById('excode').textContent = serialize(byKey(exportSel));
}
function download(){
  var d = byKey(exportSel);
  var blob = new Blob([serialize(d)], {type:'text/javascript'});
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = d.file.split('/').pop();
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(function(){ URL.revokeObjectURL(a.href); }, 4000);
  toast('SAVED ' + a.download);
}
function copyOut(){
  var t = document.getElementById('excode').textContent;
  if(navigator.clipboard) navigator.clipboard.writeText(t).then(
    function(){ toast('COPIED'); }, fallback);
  else fallback();
  function fallback(){
    var ta = document.createElement('textarea');
    ta.value = t; document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); toast('COPIED'); } catch(e){ toast('COPY FAILED'); }
    ta.remove();
  }
}
var toastT = null;
function toast(msg){
  var el = document.getElementById('toast');
  el.textContent = msg; el.classList.add('on');
  clearTimeout(toastT);
  toastT = setTimeout(function(){ el.classList.remove('on'); }, 1900);
}

/* --------------------------------------------------------------------- go */
window.addEventListener('DOMContentLoaded', function(){
  document.getElementById('export').onclick = function(){ openExport(null); };
  document.getElementById('revert').onclick = function(){
    if(!confirm('Throw away every edit and reload the tables from disk?')) return;
    DOMAINS.forEach(function(d){ D[d.k] = clone(ORIG[d.k]); });
    render(); refreshRail(); toast('REVERTED');
  };
  document.getElementById('close').onclick =
  document.getElementById('modal').onclick = function(e){
    if(e.target === this) document.getElementById('modal').classList.remove('on');
  };
  document.getElementById('dl').onclick = download;
  document.getElementById('cp').onclick = copyOut;
  window.addEventListener('keydown', function(e){
    if(e.key === 'Escape') document.getElementById('modal').classList.remove('on');
  });
  window.addEventListener('beforeunload', function(e){
    if(changedKeys().length){ e.preventDefault(); e.returnValue = ''; }
  });
  boot();
});

/* ==========================================================================
   THE WORLD EDITOR
   The generic editor falls back to a JSON textarea for arrays of objects, and
   the world graph is the one table where that is worst: it is the table whose
   structure decides whether the game is completable, and a typo in raw JSON
   is how you get a route that is passable from one side only. So it gets a
   purpose-made editor where a link is three dropdowns and the illegal states
   are not reachable.
   ========================================================================== */
var SIDE_N = { w:'WEST EDGE', e:'EAST EDGE', d:'DOOR' };

function worldEditor(main){
  var W = D.world;

  var mapCard = document.createElement('details');
  mapCard.className = 'card'; mapCard.open = true;
  mapCard.innerHTML = '<summary><span>THE GRAPH</span>' +
    '<span class="sub">what the map screen draws</span></summary>';
  var mi = document.createElement('div'); mi.className = 'inner';
  var cv = document.createElement('canvas');
  cv.className = 'worldmap'; cv.width = 1120; cv.height = 500;
  mi.appendChild(cv);
  var st = document.createElement('div'); st.className = 'grid';
  st.appendChild(field('start', W, 'start', ['world']));
  mi.appendChild(st);
  mapCard.appendChild(mi); main.appendChild(mapCard);

  W.layout.forEach(function(L, i){
    var det = document.createElement('details');
    det.className = 'card'; det.open = i < 3;
    det.innerHTML = '<summary><span class="swatchdot" style="background:' +
      (i === W.start ? 'var(--gold)' : 'var(--ink4)') + '"></span><span>' +
      esc(L.n) + '</span><span class="tag">INDEX ' + i + '</span></summary>';
    var inner = document.createElement('div'); inner.className = 'inner';

    var g = document.createElement('div'); g.className = 'grid';
    ['n','x','y'].forEach(function(k){
      g.appendChild(field(k === 'n' ? 'name' : k + ' on map', L, k, ['world','layout',i]));
    });
    inner.appendChild(g);

    ['w','e','d'].forEach(function(s){ inner.appendChild(linkRow(i, s)); });
    det.appendChild(inner);
    main.appendChild(det);
  });
  drawWorldMap(cv);
}

function linkRow(i, s){
  var W = D.world, area = W.areas[i] || (W.areas[i] = {});
  var link = area[s];
  var box = document.createElement('div');
  box.className = 'linkrow' + (link ? '' : ' off');

  var head = document.createElement('div');
  head.className = 'lh';
  head.innerHTML = '<b>' + SIDE_N[s] + '</b>';
  var on = document.createElement('label');
  on.className = 'chk' + (link ? ' on' : '');
  on.innerHTML = '<input type="checkbox"' + (link?' checked':'') + '><span>' +
                 (link ? 'leads somewhere' : 'no route') + '</span>';
  on.querySelector('input').onchange = function(){
    if(this.checked){ area[s] = { to: firstFree(i) }; mirror(i, s); }
    else { unmirror(i, s); delete area[s]; }
    touched(); render();
  };
  head.appendChild(on);
  box.appendChild(head);
  if(!link) return box;

  var g = document.createElement('div'); g.className = 'grid';

  g.appendChild(sel3('LEADS TO', W.layout.map(function(L, j){
    return [j, L.n];
  }), link.to, function(v){
    unmirror(i, s); link.to = +v; mirror(i, s); touched(); render();
  }));

  g.appendChild(sel3('NEEDS TALENT', [['', '— open —']].concat(
    Object.keys(D.talents.abilities).map(function(a){
      return [a, D.talents.abilities[a].n];
    })), link.needs || '', function(v){
    if(v) link.needs = v; else delete link.needs;
    mirror(i, s); touched(); insight();
  }));

  g.appendChild(sel3('ONLY AFTER CLEARING', [['', '— always —']].concat(
    W.layout.map(function(L, j){ return [String(j), L.n]; })),
    link.afterCleared === undefined ? '' : String(link.afterCleared), function(v){
    if(v === '') delete link.afterCleared; else link.afterCleared = +v;
    mirror(i, s); touched(); insight();
  }));

  if(s === 'd') g.appendChild(field('at', link, 'at', ['world','areas',i,'d']));

  box.appendChild(g);

  var far = W.areas[link.to];
  var back = far && ['w','e','d'].filter(function(s2){
    return far[s2] && far[s2].to === i; })[0];
  var note = document.createElement('div');
  note.className = 'lnote ' + (back ? 'ok' : 'bad');
  note.textContent = back
    ? 'Return route: ' + W.layout[link.to].n + ' ' + SIDE_N[back].toLowerCase() +
      ' comes back here, with the same requirement.'
    : 'No return route — ' + W.layout[link.to].n + ' has nothing pointing back ' +
      'here, so this is one-way.';
  box.appendChild(note);
  return box;
}

function sel3(label, opts, value, fn){
  var f = document.createElement('div'); f.className = 'f';
  f.innerHTML = '<label>' + esc(label) + '</label>';
  var s = document.createElement('select');
  opts.forEach(function(o){
    var op = document.createElement('option');
    op.value = o[0]; op.textContent = o[1];
    if(String(o[0]) === String(value)) op.selected = true;
    s.appendChild(op);
  });
  s.onchange = function(){ fn(this.value); };
  f.appendChild(s);
  return f;
}
function firstFree(i){
  for(var j=0;j<D.world.layout.length;j++) if(j !== i) return j;
  return 0;
}
/* Keeping both halves of a link in step is the whole reason this editor
   exists: change one side here and the other side follows, so the asymmetry
   the audit looks for cannot be introduced by hand in the first place. */
function mirror(i, s){
  var W = D.world, link = W.areas[i][s], far = W.areas[link.to];
  if(!far) return;
  var back = ['w','e','d'].filter(function(s2){
    return far[s2] && far[s2].to === i; })[0];
  if(!back){ back = (s === 'e') ? 'w' : (s === 'w' ? 'e' : 'w');
             if(far[back] && far[back].to !== i) return;      // do not clobber
             far[back] = { to: i }; }
  if(link.needs) far[back].needs = link.needs; else delete far[back].needs;
  if(link.afterCleared !== undefined) far[back].afterCleared = link.afterCleared;
  else delete far[back].afterCleared;
}
function unmirror(i, s){
  var W = D.world, link = W.areas[i][s];
  if(!link) return;
  var far = W.areas[link.to]; if(!far) return;
  ['w','e','d'].forEach(function(s2){ if(far[s2] && far[s2].to === i) delete far[s2]; });
}

function drawWorldMap(cv){
  var W = D.world, g = cv.getContext('2d'), r = reachability();
  g.clearRect(0,0,cv.width,cv.height);
  var xs = W.layout.map(function(l){ return l.x; }),
      ys = W.layout.map(function(l){ return l.y; });
  var x0 = Math.min.apply(null,xs)-70, x1 = Math.max.apply(null,xs)+70;
  var y0 = Math.min.apply(null,ys)-70, y1 = Math.max.apply(null,ys)+70;
  var k = Math.min(cv.width/(x1-x0), cv.height/(y1-y0));
  function X(v){ return (v-x0)*k; } function Y(v){ return (v-y0)*k; }

  W.areas.forEach(function(a, i){
    ['w','e','d'].forEach(function(s){
      var link = a[s]; if(!link || link.to < i || !W.layout[link.to]) return;
      var A = W.layout[i], B = W.layout[link.to];
      g.save();
      g.lineWidth = link.needs ? 2 : 4;
      g.strokeStyle = link.needs ? 'rgba(150,158,172,.5)' : 'rgba(237,190,87,.55)';
      if(link.needs) g.setLineDash([7,6]);
      g.beginPath(); g.moveTo(X(A.x),Y(A.y)); g.lineTo(X(B.x),Y(B.y)); g.stroke();
      g.restore();
      if(link.needs){
        var mx=(X(A.x)+X(B.x))/2, my=(Y(A.y)+Y(B.y))/2;
        g.fillStyle='#0b101a'; g.fillRect(mx-30,my-11,60,22);
        g.strokeStyle='rgba(150,158,172,.45)'; g.lineWidth=1;
        g.strokeRect(mx-30,my-11,60,22);
        g.fillStyle='#c6ced8'; g.font='600 10px system-ui,sans-serif';
        g.textAlign='center'; g.textBaseline='middle';
        g.fillText(link.needs.toUpperCase().slice(0,9), mx, my);
      }
    });
  });
  W.layout.forEach(function(L, i){
    var here = i === W.start, lost = !r.seen[i];
    g.beginPath(); g.arc(X(L.x),Y(L.y),27,0,6.283);
    g.fillStyle = lost ? 'rgba(200,16,46,.75)' : 'rgba(21,27,40,.96)'; g.fill();
    g.lineWidth = 3;
    g.strokeStyle = here ? '#edbe57' : (lost ? '#ff8298' : 'rgba(255,255,255,.16)');
    g.stroke();
    g.fillStyle = '#f4f1e8'; g.font='700 15px system-ui,sans-serif';
    g.textAlign='center'; g.textBaseline='middle';
    g.fillText(String(i), X(L.x), Y(L.y));
    g.fillStyle='rgba(244,241,232,.66)'; g.font='600 11px system-ui,sans-serif';
    g.fillText(L.n, X(L.x), Y(L.y)+42);
  });
}

/* ==========================================================================
   THE WAVE EDITOR
   Waves are the thing you actually tune, and in raw JSON they are
   `{at:560,e:[["thug",2]]}` — correct, and unreadable. Here a wave is a
   trigger position and a list of enemy rows, with the fight it adds up to
   worked out beside it.
   ========================================================================== */
function waveEditor(st){
  var wrap = document.createElement('div');
  wrap.className = 'waves';
  var dps = playerDPS(0,0);

  var head = document.createElement('div');
  head.className = 'wh';
  head.innerHTML = '<b>WAVES</b><span>' + (st.waves||[]).length +
    ' ambushes · trigger x, then who arrives</span>';
  var add = document.createElement('button');
  add.className = 'ghost'; add.textContent = '+ WAVE';
  add.onclick = function(){
    var last = st.waves[st.waves.length-1];
    st.waves.push({ at: last ? Math.min(st.len - 200, last.at + 700) : 500,
                    e: [['thug', 2]] });
    touched(); render();
  };
  head.appendChild(add);
  wrap.appendChild(head);

  (st.waves || []).forEach(function(w, wi){
    var row = document.createElement('div'); row.className = 'wave';

    var pos = document.createElement('div'); pos.className = 'wpos';
    pos.appendChild(field('at', w, 'at', ['stages','waves',wi]));
    if(w.tier !== undefined) pos.appendChild(field('tier', w, 'tier', ['stages','waves',wi]));
    row.appendChild(pos);

    var list = document.createElement('div'); list.className = 'wlist';
    (w.e || []).forEach(function(pair, pi){
      list.appendChild(enemyRow(w, pair, pi));
    });
    var addE = document.createElement('button');
    addE.className = 'ghost tiny'; addE.textContent = '+ ENEMY';
    addE.onclick = function(){ w.e.push([Object.keys(D.enemies)[0], 1]);
                               touched(); render(); };
    list.appendChild(addE);
    row.appendChild(list);

    var hp = 0, xp = 0, n = 0;
    (w.e||[]).forEach(function(p){
      var e = D.enemies[p[0]]; if(!e) return;
      hp += e.hp * p[1]; xp += e.xp * p[1]; n += p[1];
    });
    var sum = document.createElement('div'); sum.className = 'wsum';
    sum.innerHTML = '<div><b>' + n + '</b>foes</div>' +
                    '<div><b>' + n0(hp) + '</b>HP</div>' +
                    '<div><b>' + n0(hp/dps) + 's</b>fight</div>' +
                    '<div><b>' + n0(xp) + '</b>XP</div>';
    var del = document.createElement('button');
    del.className = 'ghost tiny'; del.textContent = 'REMOVE';
    del.onclick = function(){ st.waves.splice(wi,1); touched(); render(); };
    sum.appendChild(del);
    row.appendChild(sum);

    if(w.at > st.len && !st.survival){
      var warn = document.createElement('div');
      warn.className = 'wwarn';
      warn.textContent = 'Triggers at ' + w.at + ', past the end of the area (' +
        st.len + ') — this wave can never fire.';
      row.appendChild(warn);
    }
    wrap.appendChild(row);
  });
  return wrap;
}
function enemyRow(w, pair, pi){
  var r = document.createElement('div'); r.className = 'erow';
  var dot = document.createElement('span');
  dot.className = 'swatchdot';
  dot.style.background = (D.enemies[pair[0]] || {col:{}}).col.top || '#444';
  r.appendChild(dot);

  var s = document.createElement('select');
  Object.keys(D.enemies).forEach(function(k){
    var o = document.createElement('option');
    o.value = k; o.textContent = D.enemies[k].name + '  (' + k + ')';
    if(k === pair[0]) o.selected = true;
    s.appendChild(o);
  });
  s.onchange = function(){ pair[0] = this.value; touched(); render(); };
  r.appendChild(s);

  var n = document.createElement('input');
  n.type = 'number'; n.min = 1; n.value = pair[1]; n.className = 'ct';
  n.oninput = function(){ pair[1] = Math.max(1, +this.value || 1); touched(); };
  r.appendChild(n);

  var x = document.createElement('button');
  x.className = 'ghost tiny'; x.textContent = '×';
  x.onclick = function(){ w.e.splice(pi,1); touched(); render(); };
  r.appendChild(x);
  return r;
}
