# AHMED — Kuwait Fighter (Unity)

The third build of the game, in Unity and C#. The browser game in
`../ahmed-fighter` is the source of truth for every number; `../ahmed-fighter-ue5`
is the Unreal port of the same thing.

**Status: it is an open world you can walk around, fight in, and come back to.** Nine
districts, 131 to 260 metres a side, joined by the world graph's own eighteen
links — ten of which want a talent you have to find. Combat, the fight styles,
the encounters, the gates, the whole data pipeline, Ahmed's own mesh and the
game's thirty-nine sound effects are ported. Saving, the HUD and the districts'
art are not. See **What is not here yet** at the bottom — that list is the
honest one.

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

`Bootstrap` builds Ahmed, a camera that follows him and an enemy template —
each of them the real mesh over a character controller, or a capsule if the
mesh is missing — then hands the world to `DistrictRuntime`. It exists because
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
| Sound | `AudioLibrary` | plays a cue by name off `sounds.json`: which clip, how loud, how far the pitch may drift, how often it may retrigger |
| The hub | `DistrictRuntime.TickHub` | the save point at the centre of the first district: writes the save, banks a checkpoint, heals |
| Saving | `SaveGame` | encodes and decodes the world as text; `Encode`/`Decode` are pure, the storage is PlayerPrefs |
| Upgrades | `UpgradeStore` | what XP buys and what it is worth; the rules are pure, the prices come from `upgrades.json` |
| The upgrade base | `HubPanel` | the port's only interface, IMGUI, drawn while you stand in the hub |
| Pose | `FighterIK`, `TwoBoneIK` | computes the pose: feet planted on the ground, strikes thrown from the attack rows; the solver is pure and executed |
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

`sounds.json` is the one table that does not come from the browser build — it
has no audio at all. Its rows come from `../ahmed-fighter-ue5/Content/Data/
DT_Sounds.csv`, and the clips under `Assets/Resources/Audio` are the same
recordings the Unreal build plays, so a punch sounds the same in both.

Each row carries a `lead`: how far into its clip the transient sits. A swing
is not played when the button is pressed; `Fighter.StartAttack` schedules its
cue at the attack's startup minus that lead, and the attack tick starts the
clip on the way through, so the swish peaks on the first active frame. A
swing interrupted before then never sounds. The finisher passes `Rage` as its
swing cue instead of the heavy whoosh; a sealed exit refuses you once per
approach rather than every cooldown you stand in it.

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
- **No level ladder.** XP is spent at the hub now, but the rank titles in
  `levels.json` are still exported and unread — nothing calls Ahmed a
  CONTENDER.
- **No HUD.** Health, stamina, rage and mana are tracked and never drawn.
- **No materials.** The mesh arrives with its eight material slots named and
  nothing in them, because a material is a Unity asset and there is no editor
  here to author one. The same goes for the render pipeline and the quality
  settings: this port has never had either set.
- **The mesh has no avatar and no animation, so its pose is computed.**
  `Assets/Resources/Models/Ahmed.fbx` is the real body — 4,260 verts, 32 bones
  counting `root` and the mannequin's seven IK targets, 1.802 m. `FighterIK`
  moves it: every frame it puts the eight limb bones back to rest, plants each
  foot on the nearest thing under it that is not another fighter, raises the
  hands when the fighter is blocking, and during an attack drives the limb the
  row names — lead hand for jab and hook, rear hand for cross and the
  finisher, rear leg for knee and kick — to the row's reach over its startup,
  holds it through the active frames and brings it back over the recovery.
  Which side is lead depends on the stance, and an archetype's stance is a
  hash of its own name, so a kickboxer fights the same way every run and does
  not fight the way the grappler beside it does. Ahmed is always orthodox.
  That is feet, guard and strikes and nothing else: no walk cycle, no weight
  shift, no hit reaction, nothing for a knockdown — a downed fighter is still
  standing — and the body above the hips does not move.
  The solver (`TwoBoneIK.Solve`), the strike timeline, the stance map and the
  guard's geometry are pure and are executed under Mono: ten thousand random
  targets land within a millimetre, the joint always bends toward its pole,
  every attack row is at full reach for its whole active window and back at
  rest by the end of recovery, orthodox resolves to exactly the sides that
  shipped before and southpaw to their mirror, and the raised guard sits above
  the shoulder, in front, symmetric, and at 46% of the arm's reach.
  The part that turns the answer into bone rotations, the foot ray and the
  script order behind `LateUpdate` have not been seen in an editor. A Humanoid
  avatar and real animation are still the editor job they were.
- **Twenty of the thirty-nine sounds are never fired.** Every cue resolves to a
  real clip, and the nineteen the port can actually reach are wired. The rest
  belong to systems that are not ported: weapons, pickups, breakable crates and
  gates, the interface, the level-up, and the footstep, which wants an
  animation event this build has no animation for.
- **None of this has run in Unity.** There is no editor in the environment it
  was written in. What *is* earned: every file compiles clean against a stub of
  the UnityEngine API; the data is verified against the browser assets and
  against the Unreal build's own tables; and the parts that are pure logic —
  the hitbox geometry, the district layout, world reachability — are executed
  under Mono against that stub and checked. Nothing has been pressed play on,
  and physics, input, rendering and the frame loop are exactly the parts a stub
  cannot stand in for.
