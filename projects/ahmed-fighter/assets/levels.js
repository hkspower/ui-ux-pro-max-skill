/* AHMED — Kuwait Fighter
   LEVELS — the fighter's rank, and what each one is worth.

   Two currencies that are easy to confuse, so they are kept apart:
     save.xp      is SPENDABLE — the training camp draws it down.
     save.xpTotal is EARNED    — it only ever goes up, and drives the level.
   Spending on upgrades therefore never costs you a level.

   Loaded as a plain script before the game, so it works opened straight off
   disk with no build step and no server. Edit the numbers here; the game
   reads them and never keeps its own copy.
   ========================================================================== */
window.ASSET_LEVELS = {

  max: 20,

  /* XP needed to reach level n from level 1. Quadratic, so early levels come
     quickly during the first two stages and later ones pace the campaign. */
  need: function(level){
    if(level <= 1) return 0;
    var n = level - 1;
    return Math.round(140 * n + 26 * n * n);
  },

  /* What one level is worth. Health and MP grow; the numbers are small enough
     that upgrades stay the bigger lever. */
  perLevel: { hp: 6, mp: 4 },

  /* Levels are the other half of progression from the training camp: they
     arrive from fighting rather than from spending. */
  title: function(level){
    if(level >= 18) return 'CHAMPION';
    if(level >= 14) return 'CONTENDER';
    if(level >= 10) return 'RANKED';
    if(level >= 6)  return 'PROSPECT';
    if(level >= 3)  return 'AMATEUR';
    return 'ROOKIE';
  }
};
