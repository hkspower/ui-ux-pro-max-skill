/* AHMED — Kuwait Fighter
   COLORS — every colour the interface and the readouts are made of.

   Colour was the one thing in this game that was not data. Two palettes had
   grown side by side -- a flat `C` from before the design system and the `UI`
   tokens that replaced it -- and the values a player actually reads, the four
   bars and the rank badges and the pickup glows, were typed at the call site
   in eight different places. This file is the single answer, the way
   stages.js is the single answer for stages.

   WHAT IS HERE: the scheme. Surfaces, text, the brand marks, the states a
   player reads off a bar or a badge, the edges. It is the same colour on
   every screen and it means the same thing every time.

   WHAT IS NOT HERE, on purpose: painting. The nine stage backdrops and their
   lighting rigs (THEME in index.html), the fighters' kits (ahmed.js,
   enemies.js) and the weapon materials (weapons.js) are art belonging to one
   subject, not a scheme shared across the game. A sky gradient is not a
   token, and pretending it is would put nine unrelated skies in one list.

   Loaded as a plain script before the game, so it works opened straight off
   disk with no build step and no server. Edit the values here; the game reads
   them and never keeps its own copy.
   ========================================================================== */
window.ASSET_COLORS = {

  /* The surfaces, darkest first. ink0 is the void behind everything, ink1 a
     screen, ink2 a panel on it, ink3 a control on the panel. Anything raised
     goes up a step; nothing skips one. */
  ink: {
    void:   '#05070b',
    screen: '#0b101a',
    panel:  '#151b28',
    raised: '#1e2534',
    deep:   '#0a0c11'      // the pre-system ink, still the fight's own backdrop
  },

  /* Text, brightest first. Three steps and no more: a heading, a label, and
     something switched off. The two muted steps are the same cream at lower
     opacity rather than three greys, so text never shifts hue as it dims. */
  fg: {
    bright: '#f4f1e8',
    muted:  'rgba(244,241,232,.62)',
    faint:  'rgba(244,241,232,.32)',
    white:  '#fdfaf2',     // pure-ish, for the one line that has to shout
    sand:   '#e8dcc0',     // warm body text on a dark ground
    dim:    '#8a8574'      // a thing that is off, unearned or unavailable
  },

  /* The marks. These three are the game's identity and are not free to move:
     they are the hoist bar, and the gold is the one accent the whole interface
     is built on. */
  brand: {
    red:   '#c8102e',
    green: '#007a3d',
    gold:  '#edbe57'
  },

  /* What a player reads off a bar, a badge or a glow. Each of these means one
     thing and is used nowhere else -- that is what makes a colour legible at
     a glance instead of decorative. */
  state: {
    health:    '#37c26b',   // HP, and a good result
    critical:  '#e2413f',   // under a quarter health, and anything refused
    hurt:      '#ff9a97',   // the far end of the critical pulse
    mana:      '#ff9a3c',   // MP
    stamina:   '#59b6ff',   // ST
    rage:      '#7a4a90',   // RG, filling
    rageFull:  '#e05cf0',   // RG at 100, and the finisher
    rageText:  '#e9a7ff'    // the READY flash beside it
  },

  /* Ranks. S is the finisher's colour on purpose: the best result in the game
     and the biggest thing you can do in it read as the same achievement. */
  rank: { s:'#e05cf0', a:'#edbe57', b:'#37c26b', c:'#8a8574' },

  /* What is lying on the floor. A pickup's glow is its promise. */
  pickup: { health:'#37c26b', weapon:'#c9d2de', rage:'#e05cf0' },

  /* The four on-screen controls. Softer than the bar colours they echo --
     a 50 px circle at full saturation sits on top of the fight instead of
     beside it -- but the pairing is deliberate: block is the stamina blue,
     rage is the rage purple, and a player who has learnt the bars has
     already learnt the buttons. */
  control: { punch:'#e2413f', kick:'#edbe57', block:'#5aa9e6', rage:'#b46ce0' },

  /* The three difficulty rows, ramped from safe to punishing. */
  difficulty: { rookie:'#37c26b', pro:'#edbe57', champion:'#e2413f' },

  /* Edges. Gold at a fifth for anything that matters, plain white at almost
     nothing for a seam that only needs to exist. */
  line: { accent:'rgba(237,190,87,.20)', soft:'rgba(255,255,255,.07)' }
};
