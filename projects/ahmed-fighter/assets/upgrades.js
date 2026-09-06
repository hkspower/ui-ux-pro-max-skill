/* AHMED — Kuwait Fighter
   UPGRADES — the five stat tracks XP is spent on.

   Bought, unlike talents. `cost` is per level and `maxLevel` was hardcoded
   as a bare 5 in four places before this file existed.

   Loaded as a plain script before the game, so it works opened straight off
   disk with no build step and no server. Edit the numbers here; the game
   reads them and never keeps its own copy.
   ========================================================================== */
window.ASSET_UPGRADES = {

  maxLevel: 5,

  cost: function(lvl){ return 120 + lvl * 130; },

  tracks: [
  {k:'box',  n:'BOXING',  ar:'ملاكمة', d:'+10% jab, cross and hook damage'},
  {k:'kick', n:'KICKING', ar:'ركل',    d:'+10% kick, knee and rage damage'},
  {k:'vit',  n:'VITALITY',ar:'صحة',    d:'+18 max health per level'},
  {k:'spd',  n:'SPEED',   ar:'سرعة',   d:'+9 movement speed per level'},
  {k:'stam', n:'STAMINA', ar:'لياقة',  d:'+12 stamina, faster recovery'}
]
};
