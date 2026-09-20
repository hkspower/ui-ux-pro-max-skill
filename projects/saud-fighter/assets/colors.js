/* SAUD — Kuwait Fighter
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
   lighting rigs (THEME in index.html), the fighters' kits (saud.js,
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
     a glance instead of decorative.

     HP, MP and RG are three thin bars stacked in one place with no numeral
     and no icon -- fill colour is the only thing that says which is which,
     so any two of them sitting close under a colour-vision simulation is a
     real bug, not a palette nitpick. hurt and rage were both measured too
     close to a neighbour this way and were moved: hurt away from mana (they
     used to sit within a tenth of each other under every simulated
     deficiency), rage brightened until it also clears WCAG's 3:1 floor
     against a panel, which the un-mixed fill colour of a bar has to. Ranks
     were checked the same way and left alone: S/A/B/C always draw the
     letter itself over the colour, so a badge is never colour-only. */
  state: {
    health:    '#37c26b',   // HP, and a good result
    critical:  '#e2413f',   // under a quarter health, and anything refused
    hurt:      '#f9cee9',   // the far end of the critical pulse
    mana:      '#ff9a3c',   // MP
    stamina:   '#59b6ff',   // ST
    rage:      '#9160a8',   // RG, filling
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
  line: { accent:'rgba(237,190,87,.20)', soft:'rgba(255,255,255,.07)' },

  /* ------------------------------------------------------------------------
     The six groups below are the same job as the ones above, done later. Each
     one was found the way the original four were: by reading the value off
     the call sites that already draw it, not by choosing a colour. The counts
     quoted are what was in index.html before they moved here.
     --------------------------------------------------------------------- */

  /* The dark wash -- putting a readout on top of a fight without losing
     either. One job, spelled eleven ways across drawHUD, drawMap, drawPause
     and uiButton: four different near-blacks (8,10,16 / 6,8,14 / 4,6,11 /
     10,13,20, and plain black) at eight opacities between .55 and .92, on
     shapes all doing the same thing. The tint is ink.void for every one of
     them -- the four are within five levels of each other and of it, which
     is below what anyone can see through a wash -- and the four steps are
     the opacities actually in use, each literal moved to its nearest. Same
     rule as UI.bw and UI.r in index.html: a small scale, and nothing
     between its steps. */
  scrim: {
    chip:   'rgba(5,7,11,.62)',    // a HUD readout sitting over the fight
    panel:  'rgba(5,7,11,.72)',    // a band drawn across it
    screen: 'rgba(5,7,11,.82)',    // the pause wash, over everything
    solid:  'rgba(5,7,11,.92)'     // a map node; a wash only in name
  },

  /* A mark that sits ON a bright ground -- the letter inside a gold rank
     badge, the ! on a map pin. Every colour in `fg` above assumes a dark
     ground and none of them is legible here, so this was typed at two call
     sites instead. It is the gold's own hue taken almost to black rather
     than a neutral, so a badge reads as one object and not as a black chip
     dropped on a gold disc. */
  onBrand: { ink: '#1a1408' },

  /* A screen's own ground. ink.screen is the neutral one; these are the
     three tints the menu, the map and the achievements list each typed at
     the top of their own draw function. They are a hue apart on purpose --
     it is part of how you know at a glance which screen you are on -- but
     that makes them scheme, not painting. */
  ground: { menu:'#1a2233', map:'#131b2a', awards:'#191426' },

  /* Nothing there yet: a slot with no award in it, a stage never visited, a
     plate with nothing on it. The player reads absence off these, which
     makes them states like any other. White at a low alpha rather than
     three greys, for the same reason the muted text steps are -- a grey
     shifts hue against a tinted ground and a veil does not. A veil is a
     fill; the one seam that is a STROKE stays line.soft above. */
  veil: {
    empty: 'rgba(255,255,255,.05)',
    dim:   'rgba(255,255,255,.08)',
    idle:  'rgba(255,255,255,.10)'
  },

  /* The map, the one screen that reports on the whole game at once: a stage
     cleared, a stage still standing, a way that is open and one that is
     shut. The first two are brand.green and brand.red at the alpha the map
     draws them at; naming them here is what stops the next screen that
     needs "done" inventing a fourth green. */
  progress: {
    done:   'rgba(0,122,61,.85)',
    todo:   'rgba(200,16,46,.9)',
    open:   'rgba(237,190,87,.55)',
    shut:   'rgba(150,158,172,.42)',
    unseen: 'rgba(21,27,40,.92)',    // ink.panel: a place not yet reached
    marker: 'rgba(237,190,87,.92)'   // the pin that says you are here
  },

  /* Menu buttons, as against the four fight controls above. `off` is a
     control that cannot be pressed, `danger` one that throws work away, and
     `label` the cream a primary button's word is set in -- warmer than
     fg.bright because it sits on gold, where a neutral white goes blue. */
  button: {
    off:    'rgba(14,18,26,.72)',
    danger: 'rgba(74,18,26,.9)',
    label:  'rgba(255,236,206,.92)'
  }
};
