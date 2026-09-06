/* AHMED — Kuwait Fighter
   WEAPONS — what a smashed crate can put in your hands.

   Every one boosts punches only, never kicks. That is the whole design: an
   armed Ahmed hits harder and further but gives up the kick game, so picking
   one up is a choice rather than a straight upgrade. Uses are spent on swings
   that connect, so whiffing costs nothing but time.

   Loaded as a plain script before the game, so it works opened straight off
   disk with no build step and no server. Edit the numbers here; the game
   reads them and never keeps its own copy.
   ========================================================================== */
window.ASSET_WEAPONS = {

  pipe: {
    n:'STEEL PIPE', ar:'ماسورة',
    dmg: 1.9,        // multiplier on the punch that swings it
    reach: 26,       // extra px of reach
    push: 150,       // extra knockback
    uses: 12,        // connecting swings before it gives out
    len: 36, thick: 4.5, col:'#98a2b0', tip:'#6f7885'
  },

  plank: {
    n:'PLANK', ar:'لوح خشب',
    dmg: 1.6, reach: 22, push: 200, uses: 8,
    len: 42, thick: 8, col:'#a5713f', tip:'#7c5230'
  },

  crowbar: {
    n:'CROWBAR', ar:'عتلة',
    dmg: 2.2, reach: 20, push: 130, uses: 9,
    len: 32, thick: 4.5, col:'#6b7280', tip:'#c8102e'
  }
};
