# AHMED — Kuwait Fighter (Unreal Engine 5)

Guidance for anyone — person or assistant — working in this directory.

## The story

Canon lives in `../ahmed-fighter/CLAUDE.md` and applies to this build too.
The short of it: Ahmed is a young MMA professional who falls through a hole
in the street into an outer world, and fights his way through it — which is
why talents, levels and upgrades are the plot rather than systems bolted onto
one. Read it before writing story text, naming anything, or deciding what a
place looks like.

## Art direction

**This build is not cartoonish.** The browser project next door is stylised on
purpose, because it draws every pixel in code and stylisation is what makes
that possible. This one has an engine underneath it, so it is held to what an
engine can actually do.

The target is an adult action game with the highest graphics the hardware will
carry — the register of a modern console fighter, not a mobile stylised one.
Concretely, and in order of how much each one matters:

- **Realistic human proportions and anatomy.** Eight heads tall, real muscle
  insertion, hands that are hands. No exaggerated silhouettes, no oversized
  heads, no simplified limbs.
- **Physically based materials.** Skin with subsurface scattering, cloth with
  real fibre response, sweat, leather, metal. Every surface answers to the
  light rather than carrying its shading painted in.
- **Real lighting.** Lumen where the device can hold it, shadow maps where it
  cannot. Light comes from sources in the scene and everything obeys the same
  ones — the browser build's lighting rig is the design intent; this build has
  the means to do it properly.
- **Motion-capture-grade animation.** Weight, follow-through, recovery you can
  read. Contact frames that land. No looping idle that snaps.
- **Grounded, muted colour.** Kuwait's own palette — sand, concrete, dusk,
  neon over water. Saturation earns its place; it is not the default.
- **Damage that accumulates.** Bruising, swelling, torn cloth, blood, dust and
  sweat that build across a fight and stay.

**What to avoid:** rounded cartoon shapes, flat cel shading, toon outlines,
bright primary palettes, chibi or stylised proportions, bouncy squash-and-
stretch animation, anything that reads as a mobile-store art style.

This applies to models, materials, animation, VFX, lighting and UI in this
directory. It does **not** apply to `../ahmed-fighter`, the browser build,
which keeps its own stylised look deliberately.

## Gameplay architecture

Combat and traversal run on the **Gameplay Ability System**. Before adding
anything to this project:

- **A new move is an ability and a Data Asset, not a branch.** If you find
  yourself adding a case to a tick function, the thing you are adding is an
  ability.
- **A new fact about a fighter is a tag or an attribute.** Not a bool on the
  character. If two systems need to know it, it is a tag.
- **Tags are declared in `Gameplay/AhmedGameplayTags.h`**, natively, so a typo
  fails to compile. Never spell one as a string at a call site.
- **Damage goes through `IncomingDamage`**, never straight into Health. The
  attribute set is the one place that decides what a damage number means.
- **A talent added to `EAbility` must be added to the tag bridge** in
  `AhmedTypes.cpp`, and vice versa. They are the same fact in two languages.
- **How an enemy fights is a style, not a branch.** `UAhmedFightStyleData`
  answers where it stands, how it moves, what it throws from where it is, and
  what it does after. If you find yourself giving one archetype a special case
  in a tick function, the thing you are reaching for is a dial on its style.
  The styles are generated from `DT_Fighters` by `build_data_assets.py`; do not
  hand-author one, and do not write to a style asset at runtime — it is shared
  by every fighter of that archetype for the rest of the session.

## The fight is not on a strip any more

Since 2026-09-16 this build is a 3D game rather than a 2.5 D corridor, and
the rules that came out of that are load-bearing:

- **A facing is a vector, never a sign.** `AFighterBase::Facing` is a unit
  direction on the ground. Reach, lateral tolerance, the lunge, the
  knockback and whether a guard covers a blow are all measured along and
  across it. Anything that reaches for `X` to mean "forward" or `Y` to mean
  "sideways" is a bug left from the corridor.
- **The geometry lives in `Combat/AhmedArena.h`, with no engine in it.** The
  hitbox, the guard's hemisphere, the stick-to-world mapping, the arena
  clamp, the crowd's slots and the district spiral are free functions over
  `FVector`. That is what makes them testable: `Tools/harness/run.sh` builds
  that header with g++ against a stub and property-tests it, and it is the
  only part of this project that has ever run. Put a new piece of fight
  geometry there and check it; do not put actors, components or a world in
  it.
- **An arena is a circle.** Any other shape tells the player which way the
  level used to run. `AhmedGameplay::ArenaRadius`, around wherever the wave
  woke — not two numbers on X.
- **Movement is measured against the camera.** The boom is the player's to
  swing and pitch. A camera that turns makes world-axis input meaningless.
- **A crowd spreads around him and pushes off itself.** `CrowdSlot` gives
  each fighter a bearing and a ring; `PushApart` stops two of them wanting
  the same ground. Both were found to be necessary by the harness, not
  guessed.

## L_Prologue -- Ahmed's life before he fell

Since 2026-09-19, and **only in this build**: the game opens on a level that
is not one of the nine districts. `L_Prologue` is a title bout in Ahmed's own
gym, followed by a short walk to the hole in the street. It plays once --
`AAhmedPrologueGameMode` marks it seen on entry and sends every later launch
straight to `L_SouqAlDawar`, exactly where the game has always begun.

This is a deliberate exception to the canon in `../ahmed-fighter/CLAUDE.md`:
"we never see above, it is never named ... If the player never sees home, the
player cannot miss it either." Requested, not assumed. It does not touch the
browser build or the Unity build, and the canon file itself, not this one, is
where that exception is recorded so a future reader does not take it as
general.

What is actually new:

- `Source/AhmedFighter/Prologue/AhmedPrologueGameMode.{h,cpp}` -- the level's
  own Game Mode, set on `L_Prologue`'s World Settings, not the project
  default. It does not touch `AAhmedGameMode`; the duel pays no XP, earns no
  rank and writes no row into `ClearedStages` or `StageRanks`, because it is
  not a stage in that economy.
- `Content/Data/DT_Prologue.json` -- hand-authored, one row, `Champ` (the
  Contender archetype already in `DT_Fighters`) as the opponent. Like
  `DT_Sounds.csv`, this is not exported from the browser build and
  `Tools/export/export.mjs --check` does not know it exists.
- `Tools/levels/build_prologue.py` -- builds `L_Prologue`, run inside the
  editor the same way as `build_levels.py`. Written to the circular-arena
  model this file describes above, not the strip `build_levels.py` still
  blocks out in -- see that script's own docstring for why the two were kept
  separate rather than teaching one file both.
- `FAhmedProgress::bSeenPrologue` in `Game/AhmedSaveGame.h` -- the one field
  on that struct that does not mirror the browser build's save schema, since
  the browser build has no prologue for it to mirror.
- `Config/DefaultEngine.ini` -- `GameDefaultMap` and `EditorStartupMap` now
  point at `L_Prologue` instead of `L_SouqAlDawar`.

The duel itself needed no new combat code: it is one `AWaveDirector` with a
single wave and no gates, and the fall is one ordinary `AAreaExit`. Losing
the bout is handled exactly like losing a real stage -- a Blueprint event
fires and nothing forces a restart -- because that is how `AAhmedGameMode`
handles it too; the story ("he wins") is not a rule enforced in code any more
than any other stage's ending is.

**Unverified like everything else here, and more than most of it.** Nothing
Unreal has ever built this project, so `build_prologue.py`'s Python Editor
Scripting calls are the same kind of best-effort, checked-by-reading code as
`build_levels.py`'s always were. One line is flagged in the script itself as
the most likely to need correcting: the property name for a level's Game Mode
Override, which has moved between engine versions before. What can be checked
without an engine has been: `build_prologue.py --check`-equivalent logic
(its own `check()` function) confirms every placed actor stands on the ground
plane it was given and that the exit sits outside the fight circle, the same
discipline `Tools/fab/lay_out_world.py` holds its own layout to.

## Working rules

- **Don't add things that were not asked for.** Build the requested change and
  nothing beside it. If something else looks wrong or missing, say so in a
  sentence and wait to be told.
- **The browser project is the source of truth for every number.** Balance
  lives in `../ahmed-fighter/assets/*.js`. Never hand-edit anything in
  `Content/Data` — change the assets (the control panel at
  `../ahmed-fighter/panel/` is the comfortable way) and run
  `node Tools/export/export.mjs --api`. `--check` fails a build if the two
  have drifted.
- **This project has never been compiled.** It was written without an engine
  to build against. The C++ is idiomatic UE 5.4 and the data is complete, but
  expect to fix a compile error or two on a first build, and do not describe
  any of it as verified until it has actually built. The two exceptions are
  `Combat/AhmedArena.h`, which `Tools/harness/run.sh` compiles and executes
  — that file's arithmetic is checked, and no other C++ here is — and
  `Tools/audio/master.py`, which is Python, runs, and has.
- **iOS is Mac-only.** There is no cross-compile. `Tools/ios/build-ios.sh`
  checks for this and says so rather than failing halfway through a cook.

## Known, not fixed

Written down rather than fixed, because fixing them was not what was asked.
Don't re-discover them; don't fix them without being told to.

- **The player's rage finisher does nothing.** `AhmedCharacter::Input_Rage`
  calls `StartAttack(TEXT("Rage"))`, and there has never been a `Rage` row in
  the attack table — the finisher is `Special`. `StartAttack` returns false,
  so the meter never spends and nothing happens. One word to fix. The same
  bug on the enraged boss *was* fixed, because that one was inside the fight
  style work.
- **Enemy strikes do not go through the ability system.** Enemies (and the
  player) still throw via the legacy `AFighterBase::StartAttack` state
  machine; the GAS layer exists beside it rather than under it. Moving combat
  onto abilities for both sides is a separate job, and a large one.
