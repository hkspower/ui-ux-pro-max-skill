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

## The two builds

| | `ahmed-fighter/` | `ahmed-fighter-ue5/` |
| --- | --- | --- |
| What it is | The playable game. One HTML file, canvas 2D, no external assets, PWA with a versioned service worker. | The Unreal Engine 5 port. |
| Art direction | Stylised **on purpose** — it draws every pixel in code, and stylisation is what makes that possible. | **Not cartoonish.** Adult action game, highest graphics the hardware carries. See its own CLAUDE.md. |
| State | Runs. Verified in headless Chromium across phone/tablet/desktop, all ten stages, all three graphics tiers. | **Has never been compiled.** No engine has ever been run against it. |
| Balance data | `assets/*.js` — **the source of truth for every number in both builds.** | Generated. Never hand-edit `Content/Data`. |

**The browser project owns the numbers.** Change them in `assets/*.js` — the
control panel at `ahmed-fighter/panel/` is the comfortable way — then run
`node Tools/export/export.mjs --api` in the Unreal project. `--check` fails if
the two have drifted.

---

## Git

- All work goes on branch **`claude/ahmed-mobile-game-87gx8c`**. Never push
  anywhere else without being asked.
- Never open a pull request unless the author asks for one.
