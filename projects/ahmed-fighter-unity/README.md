# AHMED — Kuwait Fighter (Unity)

The third build of the game, in Unity and C#. The browser game in
`../ahmed-fighter` is the source of truth for every number; `../ahmed-fighter-ue5`
is the Unreal port of the same thing.

**Status: the fight works, the world does not yet.** Combat, the enemy AI and
its fight styles, the wave director and the whole data pipeline are ported.
Stage geometry, sealed routes, the save profile, audio and the HUD are not.
See **What is not here yet** at the bottom — that list is the honest one.

---

## Running it

```bash
node Tools/export/export.mjs      # browser assets -> Assets/Resources/Data
```

Open the project in Unity 2022.3 or newer, make an empty scene, add an empty
GameObject and put `Ahmed.Game.Bootstrap` on it. Press play.

`Bootstrap` builds a ground plane, a camera, a light, Ahmed and an enemy
template out of primitives, then starts a `WaveDirector` on the stage index you
give it. It exists because there are no authored scenes yet and a project you
cannot press play on is not a port. Nothing else refers to it, so deleting it
once there are real scenes costs nothing.

**Controls** are the legacy Input Manager, on purpose — no package, so the
project opens and plays in a bare Unity install:

| | |
| --- | --- |
| Move | WASD / arrows |
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
| Stage flow | `WaveDirector` | wave triggers, arena lock, spawning, survival wave generation |
| Data | `GameData` | every table, loaded from `Assets/Resources/Data` |
| Bring-up | `Bootstrap` | a playable stage with no authored scene |

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

- **No stage geometry.** `Bootstrap` makes a flat slab the length of the stage.
  Backdrops, props and the nine areas' looks are not ported.
- **No sealed routes.** `AbilityGate`, the talents that open them and the world
  graph in `world.json` are exported but nothing reads them, so the
  Metroidvania shape is absent — stages do not connect.
- **No save or profile.** XP, levels and upgrades are exported and unused;
  nothing persists between runs.
- **No audio and no HUD.** Health, stamina, rage and mana are tracked and
  never drawn.
- **No character mesh.** `../ahmed-fighter-ue5/Content/Models/Ahmed.fbx` is
  exported with Unreal's conventions (Y bone axis, metres baked to
  centimetres). Unity needs its own export from
  `../ahmed-fighter-ue5/Tools/blender/build_ahmed.py`, and its Humanoid avatar
  needs a rig it can map. Until then everyone is a capsule.
- **None of this has run in Unity.** There is no editor in the environment it
  was written in. The C# is type-checked — every file compiles clean against a
  stub of the UnityEngine API — and the data is verified against the browser
  assets and against the Unreal build's own tables, but *type-checks* and
  *runs* are different words and only the first one is earned.
