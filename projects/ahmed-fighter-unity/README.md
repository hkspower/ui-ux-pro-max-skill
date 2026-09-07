# AHMED — Kuwait Fighter (Unity)

The third build of the game, in Unity and C#. The browser game in
`../ahmed-fighter` is the source of truth for every number; `../ahmed-fighter-ue5`
is the Unreal port of the same thing.

**Status: it is an open world you can walk around and fight in.** Nine
districts, 131 to 260 metres a side, joined by the world graph's own eighteen
links — ten of which want a talent you have to find. Combat, the fight styles,
the encounters, the gates and the whole data pipeline are ported. Saving,
audio, the HUD and any actual art are not. See **What is not here yet** at the
bottom — that list is the honest one.

---

## Running it

```bash
node Tools/export/export.mjs      # browser assets -> Assets/Resources/Data
```

Open the project in Unity 2022.3 or newer, make an empty scene, add an empty
GameObject and put `Ahmed.Game.Bootstrap` on it. Press play. Tick
**Unlock Everything** on it to walk the whole map without earning the talents
first — without it the world is correctly mostly shut, and four of the nine
districts are all you can reach.

`Bootstrap` builds Ahmed, a camera that follows him and an enemy template out
of primitives, then hands the world to `DistrictRuntime`. It exists because
there are no authored scenes yet and a project you cannot press play on is not
a port. Nothing else refers to it, so deleting it later costs nothing.

**Controls** are the legacy Input Manager, on purpose — no package, so the
project opens and plays in a bare Unity install:

| | |
| --- | --- |
| Move | WASD / arrows — **relative to the camera**, not the world |
| Swing the camera | Q / E |
| Punch | Fire1 (left mouse / left ctrl) — jab → cross → hook if you keep it going |
| Kick | Fire2 (right mouse / left alt) — a knee inside, a roundhouse outside |
| Guard | Fire3 / left shift — a hit in the first 0.2 s is a **parry** |
| Dash | Space while moving — invulnerable through it |
| Rage | R, once the meter is full |

---

## What is implemented

| System | Class | Notes |
| --- | --- | --- |
| Shared combat | `Fighter` | startup/active/recovery attacks, health, stamina, blocking, parry, knockdown, hit resolution |
| Player | `PlayerFighter` | jab→cross→hook chain, dodge dash, perfect parry, rage meter and finisher |
| Enemy | `EnemyFighter` | flanking lanes, attack tokens, hit-and-run, boss phase two |
| Fight styles | `FightStyleRunner` | range discipline, footwork, range-banded strike selection, reactions |
| The world | `DistrictRuntime` | builds a district, wakes encounters by proximity, hands out gates, carries you across to the next |
| District layout | `District` | derives an open field from the stage that used to be a corridor |
| What the world remembers | `WorldState` | cleared encounters, opened gates, talents found |
| Crowd control | `CrowdControl` | at most two enemies swinging at once, everywhere in the world |
| Camera | `FollowCamera` | trails the player at a yaw you can swing |
| Data | `GameData` | every table, loaded from `Assets/Resources/Data` |
| Bring-up | `Bootstrap` | a playable world with no authored scene |
| Corridor mode | `WaveDirector` | the old stage-at-a-time flow. **Nothing uses it now** — kept because survival waves live there and the open world has no replacement for them yet |

---

## What makes it an open world

Three changes, and the first is the one everything else needed.

**The fight left the strip.** Every build resolves hits as "in front of me,
within reach, within a band either side". On a corridor that band was the
world's own Z axis and "in front" was a sign on X — there were only two
directions to face. `Fighter.InHitbox` now measures both along the direction
the fighter is *facing*: reach along it, the same tolerance across it. The
numbers did not change and the spacing the whole game was tuned around is
intact; they are just taken along a vector instead of an axis. The property
that has to hold is that rotating an attacker and a target together changes
nothing, and it is checked rather than assumed.

Movement is read off the camera rather than the world, because a camera that
swings makes "push the stick away from you" mean something different every
second otherwise.

**Districts are derived, not authored.** Each area already carried a stage: its
length, its waves and how far along each one triggered, its gates and what they
want — all tuned by hand in the browser build. Hand-placing new content across
a field would mean re-tuning the pacing of the entire game, so instead the one
number that stops meaning anything in the open — *distance along the stage* —
is reinterpreted as *how far around the district*. Sites land on an outward
spiral by that fraction, jittered by a hash of the area and the site index.

So if you walk out from the middle you meet things in the order the stage
intended, but you can come at any of them from any direction, ignore them, or
come back later — which is the part that makes it a world rather than a queue.
It is deterministic: the same area lays out identically every run, so a player
can learn it and a bug can be reproduced.

**Encounters wake, they do not trigger.** A stage fired a wave when you had
walked far enough along a line and locked you in until everything was dead.
Here a fight starts because you came near it, does not stop you leaving, gives
up and goes back to sleep if you walk away, and stays cleared once won. That
one change is most of what separates a world from a level. Enemies are leashed
to their site so an encounter you brushed past does not follow you across the
district.

| | corridors | districts |
| --- | --- | --- |
| ground you can stand on | 5,400 m² | **497,200 m²** |
| per area | 77 × 8.4 m | 131 to 260 m a side |
| reachable with no talents | — | 4 of 9 districts |
| reachable with all five | — | 9 of 9 |

> **The districts are as large as the content can fill.** Each carries the
> three waves and one gate its stage had, which is sparse across 250 metres.
> Making them bigger would only make them emptier; filling them means new
> content, and content is not something to invent on your own.

Distances are in **metres**. The browser build works in canvas pixels and the
Unreal port in centimetres; one pixel is 2.4 cm, so one pixel is 0.024 m, and
that factor is applied in one function in the exporter rather than typed per
field.

Note the axes. The browser draws with Y down, Unreal runs X along the stage
with Y as depth and Z up, and **Unity is Y-up — so depth is Z here and nowhere
else.**

---

## Data comes from the browser project

```
../ahmed-fighter/assets/*.js ──(Tools/export/export.mjs)──> Assets/Resources/Data/*.json
```

Never hand-edit the JSON. Change the assets — the control panel at
`../ahmed-fighter/panel/` is the comfortable way — and re-run the export.
`node Tools/export/export.mjs --check` fails if the two have drifted.

The exporter is a sibling of the Unreal one and reads exactly the same files.
It is a separate program rather than a flag on that one because the targets
disagree about almost everything on the way out: units (metres against
centimetres), and shape — Unity's `JsonUtility` cannot read a top-level array
and binds JSON keys onto field names exactly, so every table is
`{"items":[…]}` with camelCase fields, and every enum crosses as its **name**
for the loader to parse rather than as the integer `JsonUtility` would want.
That last one is not fussiness: reordering an enum would otherwise silently
turn every jab into a kick.

### Fight styles are derived, not authored

Every archetype used to fight identically — hold a flank, close, throw a move
at random off a list — so a kickboxer and a grappler differed only in how much
health each had. A style answers four questions instead, and the archetypes
differ in all four: where it wants to stand, how it gets there, what it throws
from where it is, and what it does after.

The styles are generated per archetype from that archetype's own row, so they
cannot drift from the numbers they came from. What that produces:

```
Grappler   nothing at long, hooks at mid, 73% knees in close, flat-footed
Kicker     kicks at long, kicks and punches at mid, punches only in close
Runner     jabs, holds its distance, bounces hardest of anything in the game
Bouncer    plants its feet, barely circles, hooks and knees, no combinations
Boss       an answer at every band, three-strike combinations, walks in
```

> **The derivation lives in two places.** Unreal derives it in
> `Tools/levels/build_data_assets.py` at asset-build time; Unity has no
> equivalent step, so the same rules run in `Tools/export/export.mjs`. They
> must agree. Consolidating them is a job that has not been done.

---

## What is not here yet

Named rather than glossed, because a half-ported game that reads as finished is
worse than one that says where it stops:

- **No district art.** A flat slab and a cylinder per site. The nine areas'
  looks, backdrops and props are not ported, and every district is the same
  grey square.
- **No save.** `WorldState` remembers cleared encounters, opened gates and
  talents for as long as the game is running and forgets all of it on quit.
  Writing it out is a serialiser over three sets, not a redesign.
- **No levels or upgrades.** XP accumulates in `WorldState` and buys nothing;
  the tables are exported and unread.
- **No audio and no HUD.** Health, stamina, rage and mana are tracked and
  never drawn.
- **No character mesh.** `../ahmed-fighter-ue5/Content/Models/Ahmed.fbx` is
  exported with Unreal's conventions (Y bone axis, metres baked to
  centimetres). Unity needs its own export from
  `../ahmed-fighter-ue5/Tools/blender/build_ahmed.py`, and its Humanoid avatar
  needs a rig it can map. Until then everyone is a capsule.
- **None of this has run in Unity.** There is no editor in the environment it
  was written in. What *is* earned: every file compiles clean against a stub of
  the UnityEngine API; the data is verified against the browser assets and
  against the Unreal build's own tables; and the parts that are pure logic —
  the hitbox geometry, the district layout, world reachability — are executed
  under Mono against that stub and checked. Nothing has been pressed play on,
  and physics, input, rendering and the frame loop are exactly the parts a stub
  cannot stand in for.
