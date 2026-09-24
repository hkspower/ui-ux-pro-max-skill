/* SAUD — Kuwait Fighter
   SAUD — the player character.

   His stats scale with the upgrade tracks, so `base` holds the level-zero
   values and `perLevel` what each bought level adds. `look` is the kit: the
   same flags the enemies use, listed here so his appearance can be changed
   without going near the renderer.

   Loaded as a plain script before the game, so it works opened straight off
   disk with no build step and no server. Edit the numbers here; the game
   reads them and never keeps its own copy.
   ========================================================================== */
window.ASSET_SAUD = {

  name: 'SAUD',
  ar:   'سعود',

  // Where he starts a stage, and how big he draws.
  spawn: { x: 140, z: 0.62, sc: 1.05 },

  base:     { hp: 100, stam: 100, mp: 40, pow: 1, spd: 142, reach: 58 },
  // What one bought level of each upgrade track is worth.
  // `iron` is IRON ARM: the fraction each level takes off what a BLOCKED
  // hit costs him -- the stamina (14) and the push (a third of the blow's).
  // A blocked hit already costs no health, in this build and the engine's.
  perLevel: { vit: 18, stam: 12, spd: 9, iron: { stam: 0.12, push: 0.10 } },
  // MP powers the talents. It refills on its own and on landed hits, so it
  // rewards staying in the fight rather than hoarding.
  mpRegen:  { idle: 5, onHit: 4 },

  // Skin, 2026-09-24: measured skin, not a swatch. It was #f0d8c4 -- a
  // Northern European's (CIELAB L* 88, ITA 80 degrees) -- and is now an
  // eighteen-year-old Kuwaiti's: L* 64, a* 12.6, b* 20, ITA 35 (light-tan,
  // olive). Every man's skin was moved the same way; see enemies.js.
  // Street clothes: black fitted tee, black track pants, trainers. The
  // accent is Kuwait's own red, pushed brighter and more saturated than a
  // flag-swatch red -- requested 2026-09-20 for more vibrancy/pop in his
  // kit; it is the one colour every draw call reads (waistband, trouser
  // stripe, dash trail, glove, his UI swatch -- see index.html's uses of
  // col.band), so this alone is what makes him read as more vivid.
  col: { skin:'#bd9278', top:'#15171c', bottom:'#0e1014', band:'#ff1a3c' },

  look: {
    tee:    true,          // sleeves over the upper arms
    pants:  true,          // long trousers rather than fight shorts
    stripe: true,          // his are track pants, not jeans
    patch:  true,          // Kuwait flag on the chest
    hairStyle: 'quiff',    // swept-up hair with faded sides (the cuts: enemies.js)
    watch:  true,          // wristwatch on the lead arm
    hands:  'wraps',       // taped fists — nobody wears gloves with jeans
    build:  1.12,          // thicker limbs: the shirt is a muscle fit
    hair:   '#1e150f',
    // Light stubble, not a filled-in beard -- he is eighteen. Same colour as
    // the hair, alpha down from .94 to .30: a shadow of growth, not a groomed
    // beard a grown man would have.
    beard:  'rgba(24,17,12,.30)'
  }
};
