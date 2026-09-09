# Adobe check — Ahmed's design

Run 2026-09-10, 02:10 Riyadh, against the key art in this folder and the
character renders in `../ahmed-fighter-ue5/Docs/renders/`. What Adobe's tools
could reach, what they said, and what was measured by hand where they could
not reach.

## What ran, and what could not

Adobe Fonts ran: every typeface the key art and the game name was looked up
in the library (`find_fonts`) and the library was asked what it would put on
this game (`font_recommend`). **Adobe's image tools did not run.** They take a
file only by upload to `at.adobe.com`, and this environment's network policy
refuses that host (`connect_rejected`) — so the auto-tone, subject-select and
composition analysis that would have come from Photoshop and Lightroom is
not here. The numbers in the *Key art* and *Character* sections below were
measured in the image directly, and say so.

## Type

The key art HTML (`keyart-express.html`) loads a Typekit kit and names four
families. Adobe Fonts answers:

| Named in the kit | Adobe Fonts | Falls back to |
| --- | --- | --- |
| `acumin-pro` | **available** — `AcuminPro-Regular` | — |
| `chamfer-gothic-ludlow` (the AHMED title) | **not found** | Impact |
| `oaks` | available — `Oaks-MediumRegular` | — |
| `co-arabic` (مقاتل الكويت) | **not found** | Segoe UI / Tahoma |

So two of the four, including the title face, do not exist under those names
in the library the kit is served from: the poster's title and its Arabic are
whatever the viewer's machine has. The game itself draws its text with
`"Segoe UI", Tahoma, Arial` and all three resolve (`SegoeUIBlack`, `Tahoma`,
`ArialMT`), which is why the in-game title and the poster's title do not
match — the poster asked for a face it never got.

What the library recommends, filtered hard: its first pages were comic faces
and Papyrus, which are the opposite of the brief, and are left out. Two
survive it. For the Latin title, [Condor](https://fonts.adobe.com/fonts/condor)
Black Italic by David Jonathan Ross (DJR) — condensed, heavy, a forward lean
that fits a fighter without tipping into a sports jersey. For the Arabic,
[Noto Sans Arabic](https://fonts.adobe.com/fonts/noto-sans-arabic) Bold and
ExtraBold by Monotype Design Studio, Nadine Chahine and Nizar Qandah — a real
Arabic design rather than a system fallback, with weights that can stand next
to a black Latin title and a SemiBold that reads at HUD size. Neither is in
the game; they are the two the check would put forward.

## Key art (`keyart-poster.png`, 3200×1800), measured

Text against its own background, WCAG contrast:

| | Colour on ground | Ratio | |
| --- | --- | --- | --- |
| AHMED | `#e0b34a` on `#141c2d` | **8.7:1** | passes AAA |
| KUWAIT FIGHTER | `#fdfaf2` on `#131a2b` | **16.6:1** | passes AAA |
| 9 STAGES · 2 BOSSES · ENDLESS SURVIVAL | `#e8dcc0` on `#111727` | **13.1:1** | passes AAA |
| Almuhallab Code — Kuwait | `#6c707b` on `#101726` | **3.6:1** | passes AA for large text only; fails for its size |

Composition: the title block sits in the left third (x 0.07–0.32, y
0.30–0.45 of the frame) and the figures' centre of mass is at (0.74, 0.44) —
title on the left third line, subject on the right third line, both a little
above centre. That is a sound poster layout and nothing about it needs
moving. The figures cover 10.6% of the right half; the rest is ground, and
the poster relies on the warm radial light behind Ahmed to fill it.

Two things the check flags that are not about pixels: the tagline says
**2 BOSSES** and there are three title fights now (ZAYOS, AL-SAQR,
AL-WAHSH — Unity build); and, as the canon file already records, the press
kit still tells the Kuwait story rather than the Halqa. Neither was touched.

## Character (`ahmed-guard-3d.png`, `ahmed-kick-3d.png`, `ahmed-apose-3d.png`)

Measured against `../ahmed-fighter-ue5/CLAUDE.md`, which is the brief for
this body: eight heads, real anatomy, hands that are hands, PBR skin and
cloth, no rounded cartoon shapes.

- **Proportion is right.** From the joint table in `build_ahmed.py`, crown
  1.806 m and chin 1.575 m on a 1.80 m stature is 7.8 heads — the brief's
  eight. The A-pose render reads leggy, but that is the 45° arm pose and
  the camera, not the skeleton.
- **Hands are stumps.** `hand` → `hand_end` is two joints and a skin radius;
  there are no fingers, no knuckles, no thumb. The brief's "hands that are
  hands" is the largest single gap in the render, and in a boxing game the
  fist is what the camera looks at.
- **The head is an egg under a cap.** Hair is a smooth shell, the face is
  eyes on a surface; no brow ridge, no nose bridge, no ear, no jaw line
  from the side. In the guard render the head reads as a helmet.
- **No cloth, no materials.** The tee and trousers are the body's own
  surface painted a colour: no collar, no sleeve hem, no seam, no fold. The
  eight material slots are flat colours with a roughness; there is no
  subsurface on the skin and no fibre on the cloth, which the brief names
  first among what a PBR body needs.
- **Silhouette is even.** The limbs taper the way the comments say they
  should, and from the front the stance is not bow-legged. What is missing
  is mass — trapezius, deltoid cap, forearm flexors, calf — the shapes that
  say athlete rather than mannequin.

None of that is a criticism of the generator's numbers; it is the distance
between a blockout and the body the Unreal brief describes, and it is what
the character work is for.

## The HUD at a distance

The platform note says the HUD is read from a couch. The smallest role in
the browser build's type scale is `micro` at 11 logical px on a 1280-wide
canvas: 16.5 px on a 1080p screen, 33 px at 4K. At 1080p on a 55-inch TV at
three metres that is on the small side for a label a player must read
mid-fight; it is the one size in the scale the check would raise, and it was
not changed.
