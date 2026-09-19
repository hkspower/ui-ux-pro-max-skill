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
  clamp, the crowd's slots, the district spiral and (since 2026-09-19) how
  big a district is at all -- `DistrictExtent` -- are free functions over
  `FVector` and floats. That is what makes them testable: `Tools/harness/
  run.sh` builds that header with g++ against a stub and property-tests it,
  and it is the only part of this project that has ever run. Put a new piece
  of fight geometry there and check it; do not put actors, components or a
  world in it.
- **An arena is a circle.** Any other shape tells the player which way the
  level used to run. `AhmedGameplay::ArenaRadius`, around wherever the wave
  woke — not two numbers on X.
- **Movement is measured against the camera.** The boom is the player's to
  swing and pitch. A camera that turns makes world-axis input meaningless.
- **A crowd spreads around him and pushes off itself.** `CrowdSlot` gives
  each fighter a bearing and a ring; `PushApart` stops two of them wanting
  the same ground. Both were found to be necessary by the harness, not
  guessed.

## The nine stages are round, and the map has to agree with the code

Since 2026-09-19. `Tools/levels/build_levels.py`, which blocks out the nine
per-stage levels, went 2026-09-16 to 2026-09-19 not believing its own file's
opening line any more: it still put down a corridor -- depth walls, a back
wall gates sat into, exits at two ends of a line -- three days after
`Combat/AhmedArena.h` stopped believing a fight was ever on one. It now
matches `Tools/fab/lay_out_world.py`'s model exactly: each level is a round
district of `AhmedArena::DistrictExtent(Length)`, waves and gates sit on the
spiral `SpiralPoint` already draws, and doors stand on the rim. The one real
difference from the open-world script -- a standalone level never coexists
with its neighbours, so there is no real position to aim a door's bearing at
-- is handled by fixing the three roles instead: West at 180 degrees, East at
0, Door at 90, the same three for every stage. See that script's own
docstring, "A LEVEL HERE IS ONE DISTRICT, ALONE," for why.

**This was not only a blockout gap.** `AWaveDirector::Contains()` and
`ApplyArenaBounds()` were clamping an unlocked player to a circle of radius
`Stage->Length` -- the strip's own, unscaled measurement -- while every
district, on both the per-stage maps and the ALREADY-SHIPPED open world, is
built to `DistrictExtent(Length)`, a bigger, differently-scaled number for
anything longer than about 3.5 km of the old strip's units. A player on the
open-world map was already being clamped tighter than the ground under him.
Both now read `DistrictExtent`, which fixes that everywhere the class is
used, not only in the new blockout.

`AAhmedGameMode::PlaceArrivingPlayer()` changed the same way: it used to
reposition an "East" arrival along X by a strip formula (`Stage->Length -
360`) that has nothing to do with a round district's actual size, and never
handled a "Door" arrival at all. It now finds the correct door on the
arriving district's own rim, at that role's fixed bearing, using the same
`DistrictExtent`/`ExitMargin` the level was built with -- so the game and the
map cannot disagree about where a doorway is, the property `AhmedArena::
SpiralPoint`'s own comment already asks for.

New: `AhmedGameplay::ExitMargin` (`Combat/AhmedTypes.h`), matching
`Tools/fab/lay_out_world.py`'s `EXIT_MARGIN` and now also this script's.
`Tools/harness/tests/arena.cpp` gained a `District()` test: `DistrictExtent`
is checked against the nine real stage lengths, cross-checked against
`Tools/fab/lay_out_world.py`'s own `extent_of()` over the same numbers.

**Unverified, the same way `Tools/fab/lay_out_world.py` always has been**:
`build_levels.py`'s own `check()` (mirroring that script's three assertions)
passes outside the editor, `DistrictExtent` is compiled and executed by the
harness, and the harness as a whole still passes -- but `WaveDirector.cpp`
and `AhmedGameMode.cpp` cannot be compiled by anything here, so the two C++
changes to them are read-reviewed, not run.

## The open world is built, not bought

Since 2026-09-19 there are two ways to get AL-HALQA as one map, and they
build the same world:

- `Tools/fab/lay_out_world.py` lays the game over a map you have imported
  from Fab. The ground, the buildings and the sky are the map's; this only
  adds directors, gates, doorways and a player start at positions worked out
  from the tables. It is the better-looking of the two and always will be,
  because a bought map is real art.
- `Tools/levels/build_world.py` builds the place as well as the game in it:
  the ground, the street through each district, the blocks either side, the
  rim with a gap at every way out, the roads between districts, one sun over
  all of it -- and then the same gameplay actors. **It exists because until
  it did, there was no way to get an open world out of this project without
  buying a map first.**

They agree by construction: same ring placement, same `DistrictExtent`, same
`AhmedArena::SpiralPoint`, so a district is in the same place and the same
size either way. Build this one, and replacing it later with a Fab map is an
upgrade rather than a migration.

**The place is derived, never authored.** The street IS the spiral the sites
are placed along, so the way through a district passes everything the stage
meant you to meet, in the order the browser build tuned, and a fight is always
just off the road. What stands either side is a polar lattice of plots thinned
by a per-theme density, with anything that would stand in the street, inside a
fight, or off the edge dropped. That derivation is the Unity port's
`Assets/Scripts/World/Landmarks.cs` in centimetres -- the same vocabulary per
theme, spacing, drop rules and hash -- so the two open worlds were
recognisably one place when both were live.

**Since 2026-09-19 the Unreal copy is the only live one.** The Unity port is
frozen (`../CLAUDE.md`), so the instruction that used to sit here -- change a
vocabulary number in both -- no longer applies: change it here. The C# is
left where it is as the record of where these numbers came from, and the two
were verified identical, table for table and field for field, on the day the
port was frozen.

Not ported: the Unity port's three floors. Its districts have a cellar and a
roof; this build's have a street and nothing else, because porting floors is
a job and inventing them here would be scope nobody asked for.

Checked without an engine, by the script itself: no district overlaps
another, nothing solid stands in a street or a fight or off an edge, every
way out is a gap in its own rim, every doorway opens onto the one that
answers it, and nothing walkable is laid over a hole. That last one is there
because the first draft failed it -- the roads between districts were paved
across the gap between two ground discs, which is to say across nothing, and
drawing `Docs/world-map.png` and looking at it is what caught it. Roads carry
their own ground now.

**Still unverified, like the rest of this directory**: no engine has built
the map. The Python Editor Scripting calls are read-reviewed, not run, the
same as `build_levels.py`'s and `lay_out_world.py`'s always have been.

## The stone island is an island, and there are animals on it

Since 2026-09-19. `Tools/levels/build_island.py` builds
`L_JaziratAlHajar_Island`: the sixth district of the ring with water round
it rather than as another flat disc.

**Why a separate script.** `build_world.py` lays the whole ring down as nine
ground discs, because a ring of nine discs is what the open world is. One of
those nine is called the stone island in its own briefing -- "They fall back
to the stone island ... There is nowhere to run out here" -- and a disc does
not say that. Teaching the world builder about water would put a seabed under
eight districts that do not want one, so this builds the one that does, the
same way `build_prologue.py` builds the one level that is not a district.

**It does not move the map.** The island is stage index 5, it is already on
the ring, and its extent, street, wave positions, gate and two ways out come
out of `DT_Stages.json` and `DT_World.json` through the same three
derivations everything else uses -- `DistrictExtent`, `SpiralPoint`,
`Hash01`. Nothing here adds a tenth place or opens the wheel.

**What is new is the animals, and they were asked for.** There are no animals
anywhere else in this game, in any build, in any table. Seven species live on
the island, each tied to a band of it rather than scattered over it: gulls on
the tide line, terns and cormorants on the rocks offshore, a heron standing
in the shallows, cats among the ruins, a herd of goats inland, crabs on the
wet sand. Failaka's own feral cats and left-behind goats are why those two
are there.

They are **ambient only**. They have no health, no team and no fight; they are
not in `DT_Fighters` and `check()` asserts they never get in; nothing in the
combat code knows they exist. Each carries a flee radius, which is a number
for a Blueprint that has not been written -- the behaviour is not there and is
not pretended at.

**3D modelling, in the sense this project has always meant it.** There is no
DCC tool in this repository and no mesh library, and `build_world.py`
assembles a city out of engine primitives -- so a gull is assembled the same
way: a body, a neck, a head, a beak, two wings and two legs, each a scaled
sphere, cube, cone or cylinder in the animal's own local centimetres. Ninety-
four animals, 1,102 parts. Every part carries the slot name an artist would
replace it through, and each animal is one parent actor with its parts
attached, so replacing a gull is deleting seven cubes and dropping a mesh on
the parent.

**A way out of an island is a jetty.** The exit trigger still sits on the
district rim at `E - ExitMargin` at its role's fixed bearing, where
`AAhmedGameMode::PlaceArrivingPlayer` and `AWaveDirector` both expect it; the
jetty is what you walk along to reach it, and `check()` proves it is
continuous from the stone to the rim -- the same assertion that caught the
open world's roads being paved across nothing.

**Checked without an engine, by the script itself**, and every check was
proved to bite by breaking the island on purpose: nothing stands off the
ground it is on, nothing is under the sea, no animal is outside its band, in
the road, in a fight, in a doorway or inside another animal, every bird on a
rock is on a rock that exists, no ruin stands on the street or off the stone,
every way out has an unbroken jetty, and every exit is on the rim at its own
bearing. `Docs/island-map.png` is a plan and a section -- the section is the
half that matters, because a top-down map of an island cannot show whether
the stone is above the water.

**Unverified, like the rest of this directory.** No engine has built the
level. The Python Editor Scripting calls are read-reviewed, not run. The one
most likely to need correcting is `Actor.attach_to_actor` with three
`AttachmentRule` arguments, which has moved between engine versions; if it
fails, the animals will build as loose parts in the right places rather than
as parented actors.

## Ahmed is a man, and his face is a texture

Since 2026-09-19. `Tools/blender/` builds the hero. The art direction above
asks for "eight heads tall, real muscle insertion, hands that are hands", and
the model did not have any of the three. What it had instead is written down
here, because almost none of it was visible in a render -- it came out of
slicing the built mesh and substituting real coordinates into the masks.

**The face is painted per texel now, not per vertex.** `hero/face.py` is new
and it is the whole reason the head reads as a head. The mesh has 3.1 mm
between vertices in the face; the skin texture has 0.9 mm between texels.
Everything that says "a young man" rather than "a mannequin" is smaller than
3.1 mm -- the vermilion border of a lip, the rim of a nostril, the edge of a
brow, the lash line, the crease of an upper lid -- so painted into a vertex
colour they were averaged away before the bake ever saw them. `face.py`
describes the face once as functions of position and it is evaluated twice:
per vertex for the colour the bake starts from, and per texel afterwards by
`finish.repaint_head`, which rasterises the head's own UV chart to find where
each texel sits in space. It returns a relief as well as a colour, and the
relief becomes a normal map, so a lip has an edge that catches light without
costing a triangle. `repaint_eye` does the same for the iris, which is 11 mm
across against 2.8 degrees between the globe's vertices.

**The layout is in one place.** `hero/sculpt.py` holds it -- `EYE_Z`,
`BROW_Z`, `NOSE_Z`, `MOUTH_Z`, `EAR_Z`, `CHIN_Z`, `HAIRLINE` -- because the
sculpt, the globes, the hair cut and every region in `face.py` all key off
it, and when they each carried their own copy they disagreed.

**What was actually wrong.** Each of these was measured, and most of them had
a comment beside them saying they were something else:

- The eye line sat at 1.666 where the midpoint between the chin and the crown
  is 1.677. Eyes low in an over-tall cranium is the single thing that makes a
  head read as a puppet.
- The hairline sat at 1.738, leaving a 34 mm forehead where the other two
  thirds of the face were 62 and 59 mm.
- The hair cap was cut by a box rotated about its own centre, and the
  vertical distance from a centre to a TILTED plane is 0.25/cos(t), not 0.25.
  It cut 7.4 mm above the hairline the skin is painted to, so the band
  between them was bare skull painted hair-black. That ring was in every
  build of this model.
- The beard's mask asked `|x| < 0.088` on a skull 0.079 wide, so it never
  bit: 28 per cent of the beard was painted round the back of his head.
- The two brow Gaussians had sigma 26 mm at x = +-31 mm and summed to 0.96 at
  the midline. It was not two brows, it was one bar across the forehead.
- The moustache was a hard rectangle reaching z = 1.636, which is over the
  nostrils, and 56 mm wide against a 34 mm nose.
- The four nose Gaussians sit 12 mm apart with a 10 mm sigma, so each gave
  its neighbours half its amplitude. They summed to 35 mm and measured 27 mm
  of projection, against 19-22 on a real male nose.
- There was no nasion. The midline ran in one unbroken convex ramp from the
  hairline to the nose tip -- the shop-dummy profile.
- The orbit was cut twice, a 4.5 mm boolean dish and a 5 mm Gaussian on the
  same spot, and the globe sat at the bottom of it with its cornea behind the
  lid margin. Both eyes rendered shut or as a loose bead.
- The globes were never shade-smoothed, and at roughness 0.08 under a full
  clearcoat the specular lobe is smaller than one facet, so the catchlight
  took the facet's outline: a square highlight.
- `tube()`'s `shift_front` is positive FORWARD. Every belly in the file was
  authored with the opposite sign under a comment saying what it meant to do,
  so the biceps sat on the triceps, the quadriceps behind the femur and the
  gastrocnemius on the shin.
- Every joint was the narrowest point of its limb. A joint is a local maximum
  across and a minimum through.
- The hand built the index finger where the pinky belongs and the thumb on
  the outside, and curled the fingers 24 degrees a joint toward the BACK of
  the hand. Wrist to fingertip measured 0.193 m, which is the canonical OPEN
  hand: the fist the joint table describes was never built. Fitted against
  that table the curl is 72 / 109 / 36 and the fingers run the other way.
- The trunk's shoulder shelf was 0.352 m and its iliac row 0.316 -- a ratio
  of 1.11 where a young athletic male is 1.45 to 1.55. The V everyone could
  see was not the ribcage: 193 mm of the 545 mm bideltoid came from the
  deltoid ellipsoid, which was 2.76 times as proud of the acromion as a real
  deltoid. The tee is a shell off this surface, so the shirt reproduced it as
  a puffed sleeve.
- `smooth(base, 0.7, 8)` on a 6 mm mesh diffuses over about 17 mm, one line
  after the union makes the muscle boundaries.
- And the hair was the whole heads-tall deficit. The skull crown is 1.796
  over a chin at 1.572: 8.04 heads, the figure the art direction asks for.
  But the cap topped out at 1.806 and the quiff at 1.814, so the head a
  player sees was 0.248 m and he read as 7.33.

**One that did not work.** The hairline's temple recession was also cut in
geometry, with an ellipsoid at each temple. At x = 0.063 the front of the
skull is at y = -0.027, not the -0.09 the hairline is quoted at, so cutters
placed for a forehead went through the crown and left a ridge of bare skull.
It is painted only. If it is ever cut, it has to be a scoop at the front
corner of the hairline, not a hole near the vertex.

**Four things the build now asserts**, each proved to fail when its fix is
reverted: `sculpt.check_profile` on the nose's peak and the nasion,
`assembly.check_eye` on the cornea against the lid margin (2 mm, because the
head is remeshed at a 3.5 mm voxel and anything under that is inside the
grid's own noise), and `anatomy.measure` on stature and on heads-tall.

**Not verified.** No engine has compiled or imported any of this. The
textures and the FBX are written by Blender and read back by Blender, and
that is all that has been checked.

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
- **The tee pinches to a point at the waist in the fight poses.** It is a
  shell off the body surface (`garments.dress`) taking the body's vertex
  weights by proximity, and where the torso twists the two hems converge.
  It predates the hero work -- it is in every render of this model -- and it
  is a skinning job on the garment, not a shape one.
- **The trainers read as pointed dress heels.** The shoe loft's last two rows
  drop the toe box to half the height of the heel, so the topline slopes
  down to a point instead of holding level.
- **The crotch is 54 mm too low**, at 0.855 where mid-height is 0.909. The
  trunk loft's bottom cap is at 0.900 and the thigh tubes run up to 0.978, so
  the pelvis and the thighs overlap through 78 mm with no groin geometry
  between them and the 3.5 mm voxel union welds the 16 mm slot shut wherever
  it happens to close. Nothing in the code decides where his crotch is. Long
  torso over short legs is the most age-coded proportion there is, and it is
  under the trousers, which is the only reason it is here rather than fixed.
- **The shoulder line is about 30 mm low.** The clavicle joint is at 1.448
  and the canonical acromion at this stature is near 1.478. Raising it means
  moving the joint table, and the arm's segment lengths are correct and would
  have to move with it -- a rig change, not a mesh change. The trunk's
  shoulder SHELF has been raised to 1.478; the bone under it has not.
- **Enemy strikes do not go through the ability system.** Enemies (and the
  player) still throw via the legacy `AFighterBase::StartAttack` state
  machine; the GAS layer exists beside it rather than under it. Moving combat
  onto abilities for both sides is a separate job, and a large one.
