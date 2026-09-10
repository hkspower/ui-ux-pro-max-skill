# AHMED — Kuwait Fighter (Unity)

Guidance for anyone — person or assistant — working in this directory.

## The story

Canon lives in `../ahmed-fighter/CLAUDE.md` and applies to this build too.
Ahmed is a young MMA professional who falls through a hole in the street into
an outer world and fights his way through it — which is why talents, levels and
upgrades are the plot rather than systems bolted onto one. Read it before
writing story text, naming anything, or deciding what a place looks like.

## Working rules

- **The browser project is the source of truth for every number.** Balance
  lives in `../ahmed-fighter/assets/*.js`. Never hand-edit anything under
  `Assets/Resources/Data` — change the assets (the control panel at
  `../ahmed-fighter/panel/` is the comfortable way) and run
  `node Tools/export/export.mjs`. `--check` fails if the two have drifted.
- **Don't add things that were not asked for.** Build the requested change and
  nothing beside it. If something else looks wrong or missing, say so in a
  sentence and wait to be told.
- **This project has never run in Unity.** It was written without an editor.
  The C# type-checks against a stub of the UnityEngine API and the data is
  verified against the browser assets, but nothing has been pressed play on.
  Do not describe any of it as working until it has been.
- **Materials, the render pipeline and the quality settings need an editor.**
  They are not written here and cannot be. The mesh arrives with six
  materials named and its baked textures beside it, and nothing here wires
  them into a Unity material; do not describe the look as done.

## The world

- **A district's layout is derived from its stage, never authored.** Length,
  waves, wave trigger distances and gates all come from the browser project;
  `District.Spiral` turns "distance along the stage" into "how far around the
  district". Hand-placing content would fork the pacing away from the build it
  was tuned in. If a district needs more in it, that content belongs in the
  browser project first.
- **Layout must stay deterministic.** It uses a hash of the area and site
  index, not `Random`, so a district is the same every run. A player learns a
  place; a bug in one has to be reproducible.
- **`WorldState` is what makes it a world.** A fight won stays won and a gate
  opened stays open. Anything that should survive backtracking goes there —
  and anything in it that should survive quitting goes into `SaveGame.Encode`
  in the same commit, or it is lost silently the first time someone closes the
  game.
- **There is one hub and it is at the centre of the starting district.** The
  canon is explicit that the map is the argument: the ring is closed and the
  arena is the room at its hub. A second safe room out on the loop would be a
  second answer to a question the world only gets to answer once. It is
  derived like every other site — the centre of whichever area the world graph
  starts in — not placed at a coordinate.
- **A district is three floors, and the floors are inside the wheel.** The
  cellar and the roofs are derived from the street by the exporter unless
  `strata.js` authors one by hand; no floor may carry an exit, and the
  ring's gates read the street only. Do not add a fourth floor, a floor
  with a way out, or a boss to a derived floor — a title fight happens once.
  The runtime measures only against sites on the floor Ahmed is on; anything
  that reaches across floors is a bug.
- **Encounters wake on proximity and let you leave.** Do not add a lock that
  holds the player in a fight; that is the corridor design and it is the thing
  this replaced.

## Units and axes

- **Metres.** One canvas pixel is 0.024 m, applied in one function in the
  exporter. The Unreal port uses centimetres and the same 2.4 cm per pixel;
  changing one without the other silently gives the ports different games.
- **X and Z are the ground plane, Y is up.** The browser draws Y down and
  Unreal uses Y for depth. There is no "depth axis" here any more: a fighter
  faces any direction, and reach and tolerance are measured along and across
  that facing vector, not along a world axis. Anything that reaches for
  `position.x` to mean "forward" is a bug left from the strip.

## Architecture

- **A new move is a row in `attacks.json`, not a branch.** If you are adding a
  case to a tick function, the thing you are adding is data.
- **How an enemy fights is a style, not a special case.** `StyleRow` answers
  where it stands, how it moves, what it throws from where it is, and what it
  does after. Styles are derived from the roster by the exporter; do not
  hand-author one, and do not write to a `StyleRow` at runtime — it is shared
  by every fighter of that archetype for the rest of the session. Use
  `FightStyleRunner.Haste` and `AddStrike` instead.
- **JsonUtility binds JSON keys to field names exactly.** A renamed field is a
  silently defaulted field, not an error. Rename in the exporter and the C# in
  the same commit, and enums cross as strings so that reordering one cannot
  turn every jab into a kick.
- **Enemy strikes go through `Fighter.StartAttack`**, the same door the player
  uses. A fight style decides; it does not add reach, damage or moves.
- **The music is cues, like every other sound.** `MusicDirector.Play` takes a
  cue name off `sounds.json`; the world tells it the floor and whether a
  title fight is live, and it decides nothing itself. Do not play music from
  anywhere else.
- **Nothing names an audio file.** Game code says
  `AudioLibrary.Play("Hit_Heavy", where)` and the table decides the rest, so
  recasting a sound is a row and a file. `sounds.json` is the one table the
  browser build cannot produce — it has no audio — so it is generated from the
  Unreal build's `DT_Sounds.csv` and the clips are the same recordings. The
  two ports must not disagree about what a punch sounds like.
- **The pose is computed, and a strike's look comes from its row.** There is
  no animation. `FighterIK` plants the feet, raises the guard and drives the
  striking limb to the attack row's reach over the row's own startup, active
  and recovery, so a new move needs no animation clip — it needs its limb and
  landing height in `FighterIK.StrikeLimb`, and nothing else.
- **A limb is lead or rear, never left or right.** Naming sides in the strike
  map is what made every fighter in the game throw with the same hand. Which
  side a lead limb is comes from the stance, and a stance comes from a hash of
  the archetype's name — deterministic for the same reason district layout is:
  a player learns an archetype, so it has to fight the same way every run.
- **Anything the pose reads must be state the fight already keeps.** The guard
  is `Fighter.Blocking`, the strike is the attack row. Do not add a field to a
  fighter so the pose can have something to look at. `TwoBoneIK.Solve` is pure on
  purpose: it is the geometry, and keeping it free of Transforms is what lets
  it be executed and checked without an editor. Do not put scene access in it.
- **The character mesh is generated, not authored.**
  `../ahmed-fighter-ue5/Tools/blender/build_ahmed.py` (the pipeline under
  `hero/` beside it) is the game's only mesh generator and writes
  `Assets/Resources/Models/Ahmed.fbx` and its textures itself, in metres and
  Y-up, alongside the Unreal one. Do not edit the FBX and do not copy the
  Unreal build's — its units and bone axes are that engine's, not this one's.
  Resources rather than a folder of your choosing, because `Bootstrap` has no
  scene to place a model in and `Resources.Load` is the only way it can reach
  one.

## Relationship to the other two builds

Three builds, one set of numbers. The browser build is playable and stylised on
purpose; the Unreal port is the console-grade one and has never been compiled;
this one is the newest and least finished. When behaviour disagrees between
them, the browser build is right by definition — it is the one the numbers were
tuned in.
