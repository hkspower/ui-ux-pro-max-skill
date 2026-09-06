/* AHMED — Kuwait Fighter
   TALENTS — abilities found in the world, and the gates they open.

   These are never bought. Each one is the key to a kind of sealed route, so
   picking one up opens ground in stages already cleared. Upgrades are the
   other half of progression and live in upgrades.js.

   Loaded as a plain script before the game, so it works opened straight off
   disk with no build step and no server. Edit the numbers here; the game
   reads them and never keeps its own copy.
   ========================================================================== */
window.ASSET_TALENTS = {

  abilities: {
  vault:    {n:'VAULT',      ar:'وثبة',      icon:'⤴',
             d:'Climb low ledges. Hold toward one and Ahmed pulls himself up.'},
  dashleap: {n:'DASH LEAP',  ar:'قفزة',      icon:'⇥',
             d:'Your dodge dash carries you across broken ground.'},
  powerkick:{n:'POWER KICK', ar:'ركلة قوية', icon:'⚡',
             d:'Kicks tear steel shutters off their rails.'},
  haymaker: {n:'HAYMAKER',   ar:'قاضية',     icon:'✊',
             d:'A loaded hook that punches through cracked masonry.'},
  hawk:     {n:'HAWK FIST',  ar:'قبضة الباز', icon:'✷', mp:14,
             d:'Your punches carry fire. Burns MP, and only punches — kicks stay cold.'}
},

  gates: {
  ledge:   {need:'vault',     n:'LEDGE',          ar:'حافة',   how:'Needs VAULT'},
  gap:     {need:'dashleap',  n:'BROKEN GROUND',  ar:'هوّة',   how:'Needs DASH LEAP'},
  shutter: {need:'powerkick', n:'STEEL SHUTTER',  ar:'باب حديد', how:'Needs POWER KICK', breakBy:'kick'},
  wall:    {need:'haymaker',  n:'CRACKED WALL',   ar:'جدار متصدع', how:'Needs HAYMAKER',  breakBy:'box'},
  stash:   {need:null,        n:'LOCKER',         ar:'خزانة',   how:'Walk up to it'}
},

  // Gates sit against the back wall so they never block the critical path.
  gateZ: 0.13
};
