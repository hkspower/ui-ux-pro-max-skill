# AHMED — Kuwait Fighter (Unity)

The third build of the game, in Unity and C#. The browser game in
`../ahmed-fighter` is the source of truth for every number; `../ahmed-fighter-ue5`
is the Unreal port of the same thing.

**Status: it is an open world you can walk around, fight in, and come back to.** Nine
districts, 131 to 260 metres a side, joined by the world graph's own eighteen
links — ten of which want a talent you have to find — and since 2026-09-10
each district is **three floors**: a cellar under it, the street, and the
roofs above, joined by stairs and ladders inside the district. ZAYOS, the
first title fight, is in the cellar under the striking house. The game has
music now, one loop per floor and one for the title fights. Combat, the fight styles,
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
| Floors | walk into a stairhead (the tall marker) — down for nothing, up once you have VAULT |
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
| The world | `DistrictRuntime` | builds a district on its three floors, wakes encounters by proximity on the floor you are on, hands out gates, takes you up and down the shafts, carries you across to the next district |
| District layout | `District` | derives an open field from the stage that used to be a corridor, and its cellar and roofs from `strata.json` |
| Music | `MusicDirector` | one loop at a time, crossfaded: the floor's own, or the title fight's while one is live |
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
| floors | 1 | **3** — 1,329,500 m² on all of them |

### Three floors

Every district has a cellar and roofs. This is the world getting bigger
*inside* the wheel — the one direction the canon allows — and nothing about
the ring changes: no floor has a way out of its district, the only route
between districts is still the street, and the ring's own "after this area
is cleared" gates still read the street, so clearing a district still means
clearing its street.

A floor is **derived from its street** the way the district was derived from
its stage: the same waves, one tier deeper underground, with a cache of XP
where the street had its gate — so eighteen new fields did not mean
re-tuning the game. The rule is data (`../ahmed-fighter/assets/strata.js`)
and so is the one floor authored by hand: the cellar under the striking
house, two fights and then **ZAYOS**. A street wave with a boss in it is never
copied to a floor; a title fight happens once.

Floors are separate fields at their own height (−12 m, 0, +13.9 m). The
runtime only measures against sites on the floor Ahmed is standing on, so a
fight in the cellar does not wake because he walked over it on the street,
and a fight he leaves by the stairs goes back to sleep like one he walks
away from. Each floor's spiral has its own phase, so the cellar is not the
street traced onto a lower slab — checked. The stairs come in pairs, one end
on each floor at the same x and z, placed where they are clear of every
fight on both floors — the first version put three cellars' stairs inside an
ambush's wake radius, and the test caught it. Stairs down want nothing;
ladders up want VAULT, the first talent, so the roofs open the moment the
striking house teaches him to climb.

ZAYOS is the roster's `zayos` row, exported like everyone else, with one new
column: `scale`. The port has one body and scales it — mesh and controller
together — so he is 1.55 of a man to the collision system as well as to the
eye. His gloves are not modelled: the mesh generator has no kit system yet,
so he is Ahmed's body, larger, until the character work gives it one.

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

`strata.json` is the floors: derived by the exporter from `strata.js` and the
stages, eighteen rows, two per district. `Tools/harness/gen-testdata.mjs`
writes the harness fixture from the exported tables — run it after an
export, or the tests run against yesterday's world.

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

- **No district art.** A flat slab per floor and a cylinder per site. The nine areas'
  looks, backdrops and props are not ported, and every district is the same
  grey square.
- **No level ladder.** XP is spent at the hub now, but the rank titles in
  `levels.json` are still exported and unread — nothing calls Ahmed a
  CONTENDER.
- **No HUD.** Health, stamina, rage and mana are tracked and never drawn.
- **No materials in the editor.** The mesh arrives with six materials named
  and their textures beside it in `Ahmed.fbm` — base colour, normal and
  roughness for skin, hair, tee, trousers and trainers, a colour for the
  eye — and a material is a Unity asset there is no editor here to author,
  so nothing wires those maps up. The same goes for the render pipeline and
  the quality settings: this port has never had either set.
- **The mesh has no avatar and no animation, so its pose is computed.**
  `Assets/Resources/Models/Ahmed.fbx` is the real body — about 52k triangles,
  62 bones counting the fingers, `root` and the mannequin's seven IK targets,
  1.818 m. `FighterIK`
  moves it: every frame it puts the eight limb bones back to rest, plants each
  foot on the nearest thing under it that is not another fighter (which is
  defensive rather than a fix — measured across twelve spacings from 0.05 to
  0.60 m, a foot ray never reaches another fighter on level ground, because it
  is vertical and either misses them or starts inside them), raises the
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
  a target inside the limb's fold radius folds it double instead of throwing
  the joint away, every attack row is at full reach for its whole active
  window and back at rest by the end of recovery, orthodox resolves to exactly
  the sides that shipped before and southpaw to their mirror, and the raised
  guard sits above the shoulder, in front, symmetric, and at 46% of the arm's
  reach.

  The stub those tests run against is checked too, because a stub whose maths
  lies turns every one of them into a test of the stub. Four thousand random
  cases of its quaternion and vector algebra are recomputed independently in
  numpy through rotation matrices — a different formulation from the stub's
  vector-form quaternion product — and agree to about 1e-7, with
  `AngleAxis(90, up) * forward == +X` and `Cross(up, forward) == +X` pinning
  it to Unity's left-handed convention. What no substitute reaches: Transform,
  Physics and the frame loop. Those need the editor.
  The part that turns the answer into bone rotations, the foot ray and the
  script order behind `LateUpdate` have not been seen in an editor. A Humanoid
  avatar and real animation are still the editor job they were.
- **The music has never been heard.** Four loops, made with ElevenLabs
  Music v2 and cut in an environment with no audio output; the seams
  measure clean and the levels match, and that is all anyone knows about
  them. See `../ahmed-fighter-ue5/Content/Audio/README.md`. `Music_Menu`
  has no file; this build has no menu.
- **Twenty of the thirty-nine sounds are never fired.** Every cue resolves to a
  real clip, and the nineteen the port can actually reach are wired. The rest
  belong to systems that are not ported: weapons, pickups, breakable crates and
  gates, the interface, the level-up, and the footstep, which wants an
  animation event this build has no animation for.
- **None of this has run in Unity.** There is no editor in the environment it
  was written in, and no way to get one: every `unity3d.com` host is blocked
  here, download and licensing alike. What *is* earned is in `Tools/harness`,
  and one command runs all of it:

  ```bash
  Tools/harness/run.sh
  ```

  That builds the port with warnings as errors and executes five suites against
  a small `UnityEngine` that composes transforms through their parents, answers
  downward raycasts, and drives Awake/Start/Update/LateUpdate by reflection in
  script order — so the port's own private methods run. The district layout,
  world reachability, the hitbox geometry, the two-bone solver, the save format,
  the upgrade economy and `FighterIK` on a real skeleton are all executed and
  measured. The harness's own algebra is recomputed independently in numpy so a
  stub whose maths lies cannot quietly pass everything above it.

  It is still not Unity. There is no renderer, no animation system, no real
  physics solver, and raycasts go straight down only. Nothing has been pressed
  play on, and materials, lighting, input and the real frame loop are exactly
  what a harness cannot stand in for.
- **The feet have no pelvis drop.** Measured on a 0.20 m step: the controller
  rides up onto it, and the leg on the low side hangs at full extension instead
  of the hips lowering to meet the floor. Real foot IK lowers the pelvis to the
  lower foot; this does not. Every district is one flat slab today, so it never
  shows — it will the moment the ground stops being flat.
