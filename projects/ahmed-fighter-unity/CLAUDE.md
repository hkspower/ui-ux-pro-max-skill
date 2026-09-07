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
  opened stays open. Anything that should survive backtracking goes there.
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

## Relationship to the other two builds

Three builds, one set of numbers. The browser build is playable and stylised on
purpose; the Unreal port is the console-grade one and has never been compiled;
this one is the newest and least finished. When behaviour disagrees between
them, the browser build is right by definition — it is the one the numbers were
tuned in.
