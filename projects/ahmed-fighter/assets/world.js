/* AHMED — Kuwait Fighter
   THE WORLD — how the nine areas connect.

   This is what makes the game a Metroidvania rather than a level select: you
   walk between areas, and a route you cannot pass is a route you come back to.

       Arena ── (hawk) ── Souq ── Gym ── Sharq ── Towers
                            │                       │ (dashleap)
                         (vault)                  Marina
                            │                       │
                         Desert ── Jahra ────── Failaka
                                (haymaker)   (powerkick)

   A ring with a hub. Souq is the hub: its east edge starts the loop, its west
   edge is the shortcut home from the Desert once you can vault, and the door
   partway through it is the Arena — the last fight, behind the last talent.

   Every link is two-way and both halves carry the same `needs`, so a route is
   sealed from whichever side you arrive at. `d` is a door partway into an
   area rather than at its edge; `at` is where it stands.

   Loaded as a plain script before the game, so it works opened straight off
   disk with no build step and no server.
   ========================================================================== */
window.ASSET_WORLD = {

  start: 0,

  /* Where the map screen draws each area, and its short name. */
  layout: [
    { x: 300, y: 250, n: 'SOUQ' },
    { x: 470, y: 250, n: 'GYM' },
    { x: 640, y: 250, n: 'SHARQ' },
    { x: 810, y: 250, n: 'TOWERS' },
    { x: 980, y: 250, n: 'MARINA' },
    { x: 980, y: 410, n: 'FAILAKA' },
    { x: 810, y: 410, n: 'JAHRA' },
    { x: 470, y: 410, n: 'DESERT' },
    { x: 130, y: 250, n: 'ARENA' }
  ],

  areas: [
    // 0 SOUQ MUBARAKIYA — the hub
    { w:{ to:7, needs:'vault', afterCleared:7 },
      e:{ to:1 },
      d:{ to:8, at:1900, needs:'hawk' } },
    // 1 SALMIYA GYM
    { w:{ to:0 }, e:{ to:2 } },
    // 2 SHARQ FISH MARKET
    { w:{ to:1 }, e:{ to:3 } },
    // 3 KUWAIT TOWERS
    { w:{ to:2 }, e:{ to:4, needs:'dashleap' } },
    // 4 MARINA CRESCENT — AL-SAQR
    { w:{ to:3, needs:'dashleap' }, e:{ to:5 } },
    // 5 FAILAKA ISLAND
    { w:{ to:4 }, e:{ to:6, needs:'powerkick' } },
    // 6 JAHRA ROAD
    { w:{ to:5, needs:'powerkick' }, e:{ to:7, needs:'haymaker' } },
    // 7 DESERT CAMP
    { w:{ to:6, needs:'haymaker' }, e:{ to:0, needs:'vault', afterCleared:7 } },
    // 8 KUWAIT ARENA — AL-WAHSH, a dead end off the hub
    { w:{ to:0, needs:'hawk' } }
  ]
};
