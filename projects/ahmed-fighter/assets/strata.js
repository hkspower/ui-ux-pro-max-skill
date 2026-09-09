/* AHMED — Kuwait Fighter
   STRATA — the three levels of every district: under, middle, up.

   The Unity port is the open-world build, and this is what makes it a
   world you go DOWN into and UP through rather than only across. Every
   district has a cellar and a roof: the same place, deeper and higher.

   The ring is not touched. The canon says the map is the argument -- the
   loop is closed and the arena is the room at its hub -- and that if the
   world ever needs to be bigger it gets bigger INSIDE the wheel. Under and
   up are inside the wheel: no level has a way out of the district it is
   under or over, and the only way between districts is still the street.
   Clearing a district, for the ring's own gates, still means the street.

   A level is DERIVED from its street, the way a district is derived from
   its stage (see ../../ahmed-fighter-unity/CLAUDE.md): the same waves, one
   tier deeper underground, with a cache of XP where the street had its
   gate. `override` is where a level is authored by hand instead, and the
   only one so far is the cellar under the striking house, where ZAYOS is.

   Distances (`at`) are FRACTIONS of the street stage's `len`, not pixels,
   because a level has no length of its own -- it is its street, again.
   Heights are world px above the street, so both exporters convert them
   with the same constant as everything else (one px is 2.4 cm / 0.024 m).

   The browser build does not read this file. It is data for the ports and
   lives here because this folder is the source of truth for every number.
   ========================================================================== */
window.ASSET_STRATA = {

  /* Where the two extra floors sit relative to the street. */
  height: { under: -500, up: 580 },          // -12.0 m, +13.9 m

  /* The shaft is the stair or the ladder between two floors: where along
     the street it stands, and what it wants before it lets you through.
     Stairs go down for nothing. A ladder up wants VAULT -- the first thing
     the Halqa teaches him is how to get higher. */
  shaft: { under: { at: 0.50, needs: null },
           up:    { at: 0.50, needs: 'vault' } },

  /* The derivation rule for a level that has no override. `tier` is added
     to the street's tier; `cache` replaces the street's gate with an XP
     cache worth that fraction of it (300 if the street has none). */
  rule: { under: { tier: 1, cache: { type: 'wall',  xp: 0.5 } },
          up:    { tier: 0, cache: { type: 'ledge', xp: 0.5 } } },

  /* Levels authored by hand. Keyed by area index, then by level. A wave
     with `boss:true` is a title fight: the music changes for it. */
  override: {
    // 1 BAYT AL-DARB -- the cellar under the striking house.
    //
    // The house wants to see what the stranger can do. Upstairs is six
    // rounds. Downstairs is where they keep ZAYOS, and nobody who goes
    // down to him has ever needed the stairs back up.
    1: { under: {
      waves: [ { at: 0.28, e: [['brawler', 2]] },
               { at: 0.58, e: [['grappler', 1], ['brawler', 1]] },
               { at: 0.90, e: [['zayos', 1]], boss: true } ],
      gates: [ { at: 0.74, type: 'wall', reward: { xp: 400 } } ],
      shaft: { at: 0.50, needs: null },
      story: 'Under the striking house. They keep ZAYOS down here. Nobody who went down to him has needed the stairs back up.',
      storyAr: 'تحت بيت الضرب. هنا يحتفظون بزايوس.'
    } }
  }
};
