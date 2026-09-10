# AHMED — how this work is done

Guidance for anyone — person or assistant — working on either build of the
game. The story canon is in `ahmed-fighter/CLAUDE.md`; the Unreal build's own
rules are in `ahmed-fighter-ue5/CLAUDE.md`. This file is the things that are
true of both, and of the way the author wants to be worked with.

Recorded 2026-09-07 (Riyadh), from the game's author.

---

## Who this is for

**Sporta** — a Kuwait-based app and website selling sportswear and
sports-related goods: athletic clothing, footwear, equipment and accessories.
Managed by **Almuhallab Code Company**, Kuwait. The game is Sporta's, and
anything shipped under it is theirs.

---

## How the author wants to work

These are standing instructions, not preferences for one task.

- **Deliver only the files that changed.** After any update, list the changed
  files and nothing else. Never hand over the whole package.
- **Don't add anything that was not asked for.** Build the requested change
  and nothing beside it. If something else looks wrong or missing, say so in
  one sentence and wait to be told. This one has been repeated; take it
  literally.
- **Ask before a wide task, once.** When a request could reasonably mean the
  browser build or the Unreal build, ask which — then build exactly that.
- **Times are Saudi Arabia time (UTC+3).** Dates and timestamps in notes,
  commits and replies use Riyadh time.
- **The author does not use GitHub or Lovable.** Work still commits and pushes
  to the branch it is told to, but don't route them through the GitHub UI, and
  don't open pull requests unless they explicitly ask.
- **Say what is unverified.** If something has not been run, built or tested,
  say so plainly rather than describing it as done.

---

## Platform

**AHMED is a console and PC game. It is not a mobile game.**

That decides things that would otherwise be guesses:

- **Assets are built for a screen you sit in front of**, not one you hold.
  Budget for a console GPU: real meshes, real materials, real lighting. Do not
  size textures, poly counts or effects for a phone.
- **Input is a gamepad and a keyboard.** Not touch. Nothing should depend on
  a touch control existing, and nothing should be laid out for a thumb.
- **The HUD is read at a distance**, from a couch or a desk, not at arm's
  length. Type and targets are sized for that.
- The browser build still runs in a mobile browser and its graphics tiers
  still exist — that is a property of shipping in a browser, not a statement
  that the game is aimed at phones. **Do not strip mobile support out of it
  without being asked**, and do not add anything new to it *because* of
  phones either.

---

## The three builds

| | `ahmed-fighter/` | `ahmed-fighter-ue5/` | `ahmed-fighter-unity/` |
| --- | --- | --- | --- |
| What it is | The playable game. One HTML file, canvas 2D, no external assets, PWA with a versioned service worker. | The Unreal Engine 5 port. | The Unity port, in C#. **The open-world one** — nine districts rather than nine corridors, since 2026-09-10 each on three floors (under / street / up), with ZAYOS in the cellar under the striking house and music, and since 2026-09-11 a derived place on every floor — street, buildings, rim — streamed in around the player. |
| Art direction | Stylised **on purpose** — it draws every pixel in code, and stylisation is what makes that possible. | **Not cartoonish.** Adult action game, highest graphics the hardware carries. See its own CLAUDE.md. | Console and PC grade. Was capsules; the real mesh and the sound are in now. |
| State | Runs. Verified in headless Chromium across phone/tablet/desktop, all ten stages, all three graphics tiers. | **Has never been compiled.** No engine has ever been run against it. | **Has never run in Unity.** Compiles, and its pure logic is executed and checked under Mono; nothing has been pressed play on. |
| Units | Canvas pixels. | Centimetres. X along, **Y depth**, Z up. | Metres. X and Z are the ground plane, Y up. No depth axis — a fighter faces any direction. |
| Balance data | `assets/*.js` — **the source of truth for every number in all three builds**, since 2026-09-09 for the colour scheme too (`assets/colors.js`), and since 2026-09-10 for the Unity floors (`assets/strata.js`, which the browser build itself does not read). | Generated. Never hand-edit `Content/Data`. | Generated. Never hand-edit `Assets/Resources/Data`. |

**The browser project owns the numbers.** Change them in `assets/*.js` — the
control panel at `ahmed-fighter/panel/` is the comfortable way — then re-export
into whichever ports you care about:

```
ahmed-fighter-ue5    node Tools/export/export.mjs --api
ahmed-fighter-unity  node Tools/export/export.mjs
```

`--check` on either fails if that port has drifted from the assets. One pixel
is 2.4 cm and 0.024 m; the two exporters must agree about that or the ports
quietly become different games.

---

## Git

- All work goes on branch **`claude/ahmed-mobile-game-87gx8c`**. Never push
  anywhere else without being asked.
- Never open a pull request unless the author asks for one.
