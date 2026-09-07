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

  /* XP needed to reach level n from the one below it. Quadratic, so early
     levels come quickly during the first two areas and later ones pace the
     campaign.

     The shape was right and the scale was not. At 140n + 26n^2 the twenty
     ranks cost 78,774 xp, and a COMPLETE clear of the game -- every area,
     both bosses, every cache behind every gate -- yields about 4,100. That
     is a full clear reaching level 7, level 20 costing nineteen of them, and
     the first CHAMPION rank costing fourteen. The top half of the ladder was
     unreachable in normal play.

     Which matters beyond balance: the ranks are what AL-HALQA offers Ahmed
     INSTEAD of a way out (see ../CLAUDE.md), and a ladder cannot tempt a man
     with rungs he will never stand on.

     Rescaled so one full clear lands on CONTENDER and CHAMPION is roughly
     two and a half clears -- reachable by replaying areas, working the gates
     you could not open the first time, or going back into survival. Earned,
     but not a second job. */
  need: function(level){
    if(level <= 1) return 0;
    var n = level - 1;
    return Math.round(18 * n + 3.1 * n * n);
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
