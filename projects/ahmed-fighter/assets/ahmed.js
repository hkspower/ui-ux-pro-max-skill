/* AHMED — Kuwait Fighter
   AHMED — the player character.

   His stats scale with the upgrade tracks, so `base` holds the level-zero
   values and `perLevel` what each bought level adds. `look` is the kit: the
   same flags the enemies use, listed here so his appearance can be changed
   without going near the renderer.

   Loaded as a plain script before the game, so it works opened straight off
   disk with no build step and no server. Edit the numbers here; the game
   reads them and never keeps its own copy.
   ========================================================================== */
window.ASSET_AHMED = {

  name: 'AHMED',
  ar:   'أحمد',

  // Where he starts a stage, and how big he draws.
  spawn: { x: 140, z: 0.62, sc: 1.05 },

  base:     { hp: 100, stam: 100, pow: 1, spd: 142, reach: 58 },
  // What one bought level of each upgrade track is worth.
  perLevel: { vit: 18, stam: 12, spd: 9 },

  // Street clothes: black fitted tee, black track pants, trainers.
  col: { skin:'#f0d8c4', top:'#15171c', bottom:'#0e1014', band:'#c8102e' },

  look: {
    tee:    true,          // sleeves over the upper arms
    pants:  true,          // long trousers rather than fight shorts
    stripe: true,          // his are track pants, not jeans
    patch:  true,          // Kuwait flag on the chest
    quiff:  true,          // swept-up hair with faded sides
    watch:  true,          // wristwatch on the lead arm
    hands:  'wraps',       // taped fists — nobody wears gloves with jeans
    build:  1.12,          // thicker limbs: the shirt is a muscle fit
    hair:   '#1e150f',
    beard:  'rgba(24,17,12,.94)'
  }
};
