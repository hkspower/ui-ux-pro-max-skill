# SAUD — Kuwait Fighter (Unreal Engine 5)

Guidance for anyone — person or assistant — working in this directory.

## The story

Canon lives in `../saud-fighter/CLAUDE.md` and applies to this build too.
The short of it: Saud is a young MMA professional who falls through a hole
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
directory. It does **not** apply to `../saud-fighter`, the browser build,
which keeps its own stylised look deliberately.

## Gameplay architecture

Combat and traversal run on the **Gameplay Ability System**. Before adding
anything to this project:

- **A new move is an ability and a Data Asset, not a branch.** If you find
  yourself adding a case to a tick function, the thing you are adding is an
  ability.
- **A new fact about a fighter is a tag or an attribute.** Not a bool on the
  character. If two systems need to know it, it is a tag.
- **Tags are declared in `Gameplay/SaudGameplayTags.h`**, natively, so a typo
  fails to compile. Never spell one as a string at a call site.
- **Damage goes through `IncomingDamage`**, never straight into Health. The
  attribute set is the one place that decides what a damage number means.
- **A talent added to `EAbility` must be added to the tag bridge** in
  `SaudTypes.cpp`, and vice versa. They are the same fact in two languages.
- **How an enemy fights is a style, not a branch.** `USaudFightStyleData`
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
- **The geometry lives in `Combat/SaudArena.h`, with no engine in it.** The
  hitbox, the guard's hemisphere, the stick-to-world mapping, the arena
  clamp, the crowd's slots, the district spiral and (since 2026-09-19) how
  big a district is at all -- `DistrictExtent` -- are free functions over
  `FVector` and floats. That is what makes them testable: `Tools/harness/
  run.sh` builds that header with g++ against a stub and property-tests it,
  and it is the only part of this project that has ever run. Put a new piece
  of fight geometry there and check it; do not put actors, components or a
  world in it.
- **An arena is a circle.** Any other shape tells the player which way the
  level used to run. `SaudGameplay::ArenaRadius`, around wherever the wave
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
`Combat/SaudArena.h` stopped believing a fight was ever on one. It now
matches `Tools/fab/lay_out_world.py`'s model exactly: each level is a round
district of `SaudArena::DistrictExtent(Length)`, waves and gates sit on the
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

`ASaudGameMode::PlaceArrivingPlayer()` changed the same way: it used to
reposition an "East" arrival along X by a strip formula (`Stage->Length -
360`) that has nothing to do with a round district's actual size, and never
handled a "Door" arrival at all. It now finds the correct door on the
arriving district's own rim, at that role's fixed bearing, using the same
`DistrictExtent`/`ExitMargin` the level was built with -- so the game and the
map cannot disagree about where a doorway is, the property `SaudArena::
SpiralPoint`'s own comment already asks for.

New: `SaudGameplay::ExitMargin` (`Combat/SaudTypes.h`), matching
`Tools/fab/lay_out_world.py`'s `EXIT_MARGIN` and now also this script's.
`Tools/harness/tests/arena.cpp` gained a `District()` test: `DistrictExtent`
is checked against the nine real stage lengths, cross-checked against
`Tools/fab/lay_out_world.py`'s own `extent_of()` over the same numbers.

**Unverified, the same way `Tools/fab/lay_out_world.py` always has been**:
`build_levels.py`'s own `check()` (mirroring that script's three assertions)
passes outside the editor, `DistrictExtent` is compiled and executed by the
harness, and the harness as a whole still passes -- but `WaveDirector.cpp`
and `SaudGameMode.cpp` cannot be compiled by anything here, so the two C++
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
`SaudArena::SpiralPoint`, so a district is in the same place and the same
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

## The game is played on one seamless world

Since 2026-09-23 (Riyadh), asked as "make levels all open world 3d" and
settled as: **the Unreal game plays on one continuous 3D map of all nine
districts** -- `L_AlHalqa_World`, built by `Tools/levels/build_world.py` --
not on nine separate levels. The browser build is untouched.

**The flow.** `L_Prologue`'s fall opens `L_AlHalqa_World` at the souq, and
every later launch opens it straight away (`SaudGameplay::WorldLevel` in
`Combat/SaudTypes.h`; `ASaudPrologueGameMode`; `build_prologue.py`'s exit).
Inside the world, every doorway is a same-level step: `AAreaExit` with a
`DestinationExit` puts the player on the doorway that answers it, no load.
The world has one `PlayerStart`, in the souq, so a save that stopped in any
other district would wake him there; `ASaudGameMode::ResumeInDistrict` moves
him on a fresh open to the middle of the district `CurrentStage` names (3 m
out from its director, facing in, arena bounds applied). It runs only when
the map has more than one director and no `?ArriveAt`, so the standalone
levels and a step through a door are exactly as before.

**Every district is its best art, in one place.**
- **The souq is `build_souq.py`'s modelled souq** -- arcaded stalls,
  mud-brick warehouses, the minaret, crates and barrels, the cracked gate
  wall on its `AbilityGate` -- placed from that script's own `plan()`, not
  engine cubes. Nothing in it depends on where a door is except the rim's
  gaps and the street's spurs, so the world passes its door bearings in:
  the rim is re-gapped and the street re-spurred. The street is baked into
  one mesh with its spurs, so the world's is its own,
  `Content/Models/Souq/SM_Souq_Street_World.fbx`, made by
  `python3 Tools/blender/build_souq.py --world` (bpy; under a second) and
  read back whole. Every other mesh is the level's own FBX.
- **The island is `build_island.py`'s island** -- shallows, stepped beach,
  stone, the 22 rocks, a jetty to each way out, and all 94 animals with
  their parts -- built round the world's real doors. The island script's
  open sea (drawn to three extents) is left out, since it would lie under the
  neighbours; the shallows are the water. Its fights and gate stay on its
  own spiral, where its ruins and animals were placed to keep clear of them.
- The other seven are the derived city districts, as before.

**The ring is 18 m wider than `lay_out_world.py`'s.** Placement measures
the island to its water (`reach_of`: 1.34 extents) rather than its stone,
because its shallows came within 2.7 m of the dead road's ground where the
ring keeps 16 m between any two districts. The ring radius went 352 m ->
370 m. A Fab map brings its own ground and no sea, so `lay_out_world.py` is
unchanged and the two worlds now differ by that ring radius, and by nothing
else.

**Checked without an engine** (`python3 Tools/levels/build_world.py`): all
of the above, plus the island passes `build_island.check()` at the bearings
this world gives it and every piece of it, water included, stays the full
16 m gap off every neighbour; the souq passes `build_souq.check()` (16 of 16
sabotage cases still bite) and its fights, gate and doors are the world's
to the centimetre. The new checks were sabotaged too: a ring measured to the
island's stone, doors off by 10 degrees and a missing jetty board each fail.
The editor build was driven against a stub `unreal` module: 4,146 actors
spawned, no positional `Rotator` left.

**Fixed on the way, because the world would have carried them:**
- **The world builder's rotators.** `build_world.py` spawned with
  `unreal.Rotator(0, yaw, 0)`, which puts the yaw in the pitch (the Python
  order is roll, pitch, yaw) -- every turned block, wall and road would have
  stood on its side. Named now. The same call in `build_levels.py`,
  `build_island.py` and `build_prologue.py` is left as it was (see *Known,
  not fixed*).
- **The island's ground discs** gave their SURFACE height as the piece's z,
  and both builders place a cylinder by its middle: the stone stood 30 cm
  proud of its own street, jetties and every goat's feet. Each disc is let
  down by half its thickness now.
- **The souq's rim walls stood out like fins.** The wall mesh runs along its
  local X and each was turned to its bearing, so all 78 pointed straight
  out of the district. Turned a quarter less, they run along the rim and
  front the street; `build_souq.check()` asserts it and a fin bites.

**Unverified, like everything in this directory.** No engine has built the
map, imported `SM_Souq_Street_World.fbx` (its material slot is named
`M_Souq_Flagstone` and is expected to resolve to the level's imported
material of that name), or run `ResumeInDistrict`, which has never been
compiled. The standalone `L_SouqAlDawar` and `L_JaziratAlHajar_Island`
still build; nothing in the C++ or the config opens them any more.

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
`ASaudGameMode::PlaceArrivingPlayer` and `AWaveDirector` both expect it; the
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

## Saud is a man, and his face is a texture

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

**A second pass, 2026-09-20, from looking at the renders.** Asked for as
"make arm full strong manly, fix position and angles" and then "fix all
design issues". Each of these was measured before it was changed, on the
built body or the posed rig, and the number is beside it:

- **His arms.** `anatomy.arm(scale)` and `pipeline.LIMBS = {"saud": 1.18}`,
  the same shape as `FACES`: one man's difference, Thug and Brawler unlisted
  and unchanged. Weighted per ring -- 1.0 at the biceps belly and the
  forearm's flexor mass, 0.05 at the elbow, 0 at the wrist -- because a
  stronger arm grows its bellies and keeps its joints, and a flat multiply
  would have thickened the elbow with them. Biceps girth 0.376 -> 0.442 m.
- **The guard.** `build_saud.GUARD` said "fists to the chin" and put them at
  chest height, 1.36-1.40 m against a chin near 1.57: with the upper arm
  hanging straight down (z -0.98) the elbow lands 0.461 m below the chin and
  forearm + hand are 0.338 m long, so no aim of the forearm could get there.
  The elbow's drop now goes into -Y, forward, not sideways -- the first
  attempt with x 0.42 got the height and read as a chicken wing -- and the
  fist is at 1.51 m, by the jaw. `KICK` carries its own arm aims and was
  not touched. **This is shared code: Thug's and Brawler's guard and kick
  renders were struck with the old aims and are stale until they are
  rebuilt** (not done -- only Saud was asked for).
- **The eyes rendered as slits.** `sculpt.lids` had margins 3.8 + 4.8 =
  8.6 mm against the 10 mm its own docstring quotes for a human aperture,
  and the 3.5 mm remesh ate the rest. Now 4.8 + 5.2, which is also the 5 mm
  half-aperture `check_eye` already assumed. They open; whether 10 mm
  still reads heavy-lidded at full quality is judged on the render, and
  the next step if it does is 11 (the human range is 9-12), not a guess.
- **The stubble was a pencil moustache and a goatee.** The browser's beard
  is a wash with an alpha (.30 for him); the bake composited its COLOUR
  over the skin and then painted the shadow a beard casts and the relief it
  adds at full-beard strength regardless. `palette_for` now keeps the alpha
  as `beard_k` and `face.shade` scales the shadow and the relief by it.
- **The hair was a helmet with a brim.** `hair_parts`' cap was a solve
  against an older skull; measured on this one (`hair_probe`, on the built
  checkpoint) it was 26 mm thick in the single 5 mm row above the front
  hairline, 22-24 mm down the whole back and an 11 mm step at the ear
  line. Re-solved with the head loft, the hairline cut and the 3.5 mm
  remesh, exactly as the body is built: 6 mm at the front hairline
  building to 19 mm at the crown (the quiff), 5-7 mm at the back, 3-4 mm
  at the sides (a fade, under the voxel), crown still at 1.800. **Also
  shared: the "crop" style Thug and Brawler wear is this cap alone, so
  their hair is thinner too once rebuilt** (not done, as above).
- **His accent colour.** `assets/saud.js` `col.band` `#c8102e` -> `#ff1a3c`:
  Kuwait's red, brighter and more saturated, for the "more vibrant" half of
  a "Hi-Fi Rush" ask. It is the one colour every draw of him reads
  (waistband, trouser stripe, dash trail, gloves, his UI swatch), which is
  why that alone is the change. The other half of that ask -- the
  cel-shaded look -- is an engine material (stepped diffuse, rim, an
  outline pass), not anything this pipeline bakes, and no engine has ever
  been run against this project; it is in "Known, not fixed".

**A third pass, 2026-09-23: edges, shadows, tint, and the leg.** Asked as
"improve edges and shadows and tint and fix over-pixelated areas", then "fix
Saud's leg". Each found by measuring the textures and the renders:

- **Edges.** Every kit mark -- the flag patch, the trouser stripe, the
  waistband, the wraps' turns, the nails, the shoe's bars, the collar rib --
  was a hard mask on the vertices, so the bake smeared each edge across a
  3 mm triangle. They are feathered ramps now, a texel wide, painted per
  texel after the bake (`finish.kit_colour`, `repaint_kit`), the way the face
  already was. The tee's collar and hems keep two rings of vertices out of
  the decimation, so the neckline is a curve and not a sawtooth.
- **Pixelation.** The pore and weave bump ran in the texture's bounding-box
  coordinates at Detail 6: a 1.1 x 0.3 x 1.3 mm lattice whose octaves went
  down to 0.02 mm against a 0.35 mm texel, so 66-82 % of every normal map
  was per-texel white noise. It runs in metres now, two octaves, coherent
  (lag-1 autocorrelation 0.008 -> 0.60 on the skin). The hair baked into
  4.4 % of its own image; its UVs fill it now. The documentation renders
  are twice the size, and the face shot's lens 85 -> 120 mm.
- **Tint.** The render's view transform clipped saturated highlights
  (Standard); it is Khronos PBR Neutral where Blender has it. The rim lamp
  had green equal to blue, and on the shadow side of the jaw that read
  magenta-grey; it is warmer now at the same energy and red.
- **Shadows.** The beard was laid over the shading as a colour, which erased
  the shadows painted before it; it is a multiplicative wash now. The lash
  line follows the sculpted lid rather than a straight bar. The soles
  baked into the shoe's images with the images cleared first, which wiped
  the uppers baked a moment before; only the first bake of a set clears.
- **The leg.** The trousers' web between the thighs ("Seen, reported, not
  touched" under "The first area is built") was the welded crotch stretching
  under a staggered stance: the vertices there were weighted near-equally
  to the pelvis and both thighs. `rig_export.pin_crotch` tapers them onto
  the pelvis (101 on Saud); a sample vertex that moved 13 mm in the guard
  moves 0. The geometry is still welded -- a boolean cut was tried twice and
  looked worse both times.

**The pipeline builds bosses.** `hero/` now does what AL-WAHSH and ZAYOS need
and nobody had built: a bald head (`hair_parts("bald")` is empty; the hair
material is never assigned or baked), no shirt (`garments.dress(tee=False)`
leaves an empty Tee rather than None, so nothing downstream needs a second
path), boxing gloves (`anatomy.glove`, unioned over the fingers rather than
replacing them, because every man exports the same 62 bones, fingers
included; its own material, in the man's band colour), and a scar
(`face.shade(scar=True)`, over his left brow). Two bugs on the way: a BVH
tree built from no geometry answers `find_nearest` with (None, None, None,
None), not None, and the bald head crashed on it; and `palette_for` dropped
the beard of any bald man, which would have shaved AL-WAHSH. And one in the
rig check: `rig_full_ik.verify`'s toe-roll tolerances were millimetres
measured on Saud and never scaled, and ZAYOS -- 1.48 times his height --
failed them at his own true proportions. They scale with the man now; the
self-test still bites nine of nine at Saud's size.

**Not verified.** No engine has compiled or imported any of this. The
textures and the FBX are written by Blender and read back by Blender, and
that is all that has been checked.

## The bosses move now

Since 2026-09-19. `Tools/blender/build_motion.py` writes seventeen animation
clips for AL-WAHSH, AL-SAQR and ZAYOS into `Content/Animation/Bosses/`, on the
same 62-bone skeleton the hero exports.

**There was no animation in this build at all.** Not a montage, not an
AnimSequence, not an animated FBX, not a `.uasset` of any kind. SaudTypes.h
says the montage is "Optional -- the game is fully playable without
animation" and it meant it. The art direction asks for weight,
follow-through and contact frames that land; the three title fights were
three men sliding at each other.

**Every number comes from somewhere.** `DT_Attacks.csv` gives the timing, so
a clip is exactly startup + active + recovery long and its contact frame is
exactly where startup ends. `DT_Fighters.csv` gives each boss his move list.
The browser build's own `attackPose()` (index.html:1347) gives the shape --
which limb throws, how far the torso tips, how far the hip lifts, how many
turns the spin kick takes -- because it draws every fighter procedurally and
is therefore the canonical motion. `enemies.js` gives `sc` and `look.build`,
which the UE5 export drops, and which are the only numbers that say ZAYOS
should commit further past his guard than AL-SAQR. The canon gives who they
are: ZAYOS only ever punches, so he has no leg clip and a check fails if one
ever appears.

**What does not cross over** is length. The browser draws two-bone limbs at
26/25 px for an arm and 34/32 for a leg; this build's proportions are
measured off Winter's tables. Angles and timings are dimensionless and do
cross; pixel lengths do not and are not used.

**Seven things it got wrong first, all caught by measuring rather than
looking.** The root bone points UP, so its local Y is world Z -- the forward
shift was being written into the vertical and drove him into the floor. An
aim is a WORLD direction, so rotating the torso afterwards dragged the
already-aimed arm off target and turned the hook 10 cm BACKWARDS. A spine
bone's local X runs along world +X, so the obvious sign for a lean tips him
away from the man he is hitting. And the browser's `shift` moves the
SHOULDERS, not the feet: mapped to the root it walked the whole man forward
34 cm on a cross, which is a lunge and not a punch. It is now one torso
inclination derived from the browser's own shoulder offset.

The other three were found after the first version had already been
committed, by reading it back against the browser rather than against
itself:

- **He kicked while levitating.** The browser's `hipY` was mapped to the
  root, and the browser can do that because it lifts the hip and then draws
  the legs FROM the hip -- a flat drawing's cheat. On a skeleton the feet
  come up with it: the support foot left the ground by 12 cm on a round
  knee and 30 cm on the spinning kick. The lowest foot is now PLANTED by
  construction -- the root is offset by whatever keeps it at the height it
  stands at in the guard -- and the hip rise is whatever the leg geometry
  then implies. It comes back honestly because the support foot pivots onto
  its ball, heel up, which is what a kicker's does: 9.9 to 10.7 cm, against
  3.0 to 3.7 with the foot left flat. Nothing had to be relaxed to allow
  it; the 8 cm threshold `verify()` already held is unchanged.
- **The ease was the wrong curve.** It was a smoothstep under a comment
  claiming it was the browser's own. The browser's (index.html:111) is
  easeInOutQuad, `t<.5 ? 2*t*t : 1-Math.pow(-2*t+2,2)/2`, and the two part
  company by three points of travel at the quarters.
- **The idle cycles were invented.** Three of them, one per boss. The
  browser bobs every standing fighter at `Math.sin(t*2.4)*1.1`
  (index.html:1515) and that 2.4 is a constant -- a fighter's speed does not
  change how he breathes. One cycle, 2.618 s, for all three.

`verify()` puts the fist or the foot where the frame says it is and measures
how far forward of the guard it got, how far the hip rose, and whether
either foot is still on the ground. It is what caught five of the seven.
Sixteen checks guard this tool -- ten assertions over the plan, six
conditions over the motion itself -- and every one of the sixteen has been
made to fail by breaking the one thing it guards. The one that decides
which bosses have a phase two reads the browser's `isBoss` line rather than
a constant copied out of it, because a copy goes stale quietly, and it was
proved by changing the browser's answer rather than the tool's.

**Not wired, and there is nothing to wire it to.** The only line that plays a
montage is `SaudAttackAbility.cpp:85`, and nothing in C++ ever calls
`PressInput`, so that path never runs. The bosses strike through
`AFighterBase::StartAttack` (EnemyFighter.cpp:169, FightStyleComponent.cpp:297),
which fires a sound and a Blueprint event and advances a float in Tick.
`Attack->Montage` is per-ATTACK anyway, and a boss's jab is not Saud's jab.
Making that seam is engine work on a project that has never compiled.

**Not verified.** No engine has imported a single one of these clips. They
were authored in Blender, exported to FBX, read back into Blender and
measured there, and that is the whole of the proof. The read-back now
compares the round-tripped pose against the authored one bone by bone and
it agrees to 0.2 mm -- with the keys shifted one frame, which is Blender's
own FBX importer's convention and not something in the file. `Content/Animation/Bosses/boss-motion.png`
is a contact sheet of every clip drawn as the skeleton itself, which is how
they were judged.

## IRON ARM -- the sixth upgrade track

Since 2026-09-23, asked as "make upgrade arm iron arm for upgrade", then,
when asked, an upgrade with a look, whose effect is a tougher block.

**What it does, in both builds.** Bought with XP like the other five, five
levels, the same costs. A blocked hit already costs no health in either
build -- it costs 14 stamina and a third of the blow's knockback -- so each
level takes 12 % off the stamina and 10 % off the push (5.6 and half the push
at level 5): the guard holds longer before it breaks. The numbers are the
browser's (`saud-fighter/assets/saud.js`, `perLevel.iron`; the track in
`assets/upgrades.js`), exported to `DT_Upgrades.csv` (Iron_1..5) and
`Player.json`; the C++ repeats them in `SaudGameplay` like every other
per-level number `ApplyUpgrades` uses, and the block path in
`AFighterBase::ReceiveHit` asks the fighter for `GetBlockCostMultiplier`.
Checked in the browser, headless, on the real `applyHit`: level 0 blocks for
14 stamina and 90 push, level 5 for 5.6 and 45, health untouched. The shop
had room for five rows; its rows now share the space above the abilities
strip, and all six fit at phone, tablet and desktop sizes (checked in
headless Chromium).

**What it looks like, in the Unreal build only.** His right arm -- the rear,
power hand; the ask said one arm -- turns to iron a fifth of its visible
length per level, fist first, up to his sleeve. `Tools/blender/
build_iron_arm.py` bakes, in the skin's own UV layout, a mask of how far up
the arm each texel is and a forged-iron set (banded plates, rivets, worn
edges) evaluated in 3D so it runs across chart seams; which skin is the arm
comes from the skin weights to the arm's own bones, not from distances, and
a check holds every masked texel inside the right arm's and hand's own UV
charts. `ASaudCharacter::ApplyUpgrades` sets the material parameter
`IronArmLevel` (0-1). `Docs/renders/saud-ironarm-3d.png` shows levels 0, 1,
3 and 5 through the same blend in Blender. The browser build's drawing of
him is unchanged.

**Not verified, and not built:** the engine material. Nothing here makes it
-- Saud's materials are made by the engine's importer -- so the skin
material has to be given the blend written in `build_iron_arm.py`'s
docstring by whoever first opens the project. The C++ is read-reviewed, not
compiled.

**Found on the way, not touched:** `ApplyUpgrades` gives SPEED +34 cm/s a
level where the exported table says 22 (the browser's 9 px), and
`TryPurchaseUpgrade` expects track ids `Boxing`, `Kicking`, `Vitality`,
`Speed`, `Stamina` where `DT_Upgrades.csv` says `Box`, `Kick`, `Vit`, `Spd`,
`Stam` -- a shop that passes the table's own id cannot buy those five.
IRON ARM uses the table's id, `Iron`.

## Saud moves, and every clip is posed through the IK rig

Since 2026-09-23. Asked as "improve motion Saud IK", then, when asked what
that meant, all four of: Saud's own strike clips, his movement clips, the
rig itself, and the boss clips moved onto IK.

**The FK clips skated.** `build_motion.py` posed every frame bone by bone and
planted the feet afterwards by sliding the whole man up or down until his
lowest foot touched -- up and down was all that fixed. Measured on the
seventeen FBX files it had shipped, read back through Blender's importer:
the support foot slid 30-35 cm across the floor on every kick and knee,
44-54 cm round a circle on the spinning kick (it turned about the origin,
not the ball of the foot it stands on), the rear foot 9-13 cm under every
cross and hook (the hips' turn swung both legs with them), and the guard
idle's sway carried both feet 2.2 cm side to side. Measured the same way on
the files this writes: 0.0-0.2 mm.

**How.** `Tools/blender/motion_ik.py` is new. Each frame is still struck in
FK from the same shapes -- the aims, lean, twist, the browser's timing and
ease -- then every limb is handed to `rig_full_ik`'s controls: a planted foot
is an IK target that does not move, turned on its ball and rolled onto it
as far as the FK shape turned and rolled it; the hips come down only as far
as a planted leg needs to reach; a leg strike moves the body over the
support foot (standing on one foot, a man's weight has to be over it --
the FK clips had the foot skate under the hips instead); a jab and a cross
run the fist down a straight line (it swung an arc about the shoulder, 6.7
cm off the line); the spin turns on the support ball through the rig's new
pivot. The rig is then stripped and each frame's deform bones are written
as keys. The bake reproduces the rig to 0.002 mm, and every exported FBX is
read back and every bone of every frame compared: 0.00 mm.

**Three more things the FK clips had wrong, found on the way:**

- **The guard's rear knee bent backwards.** Its thigh aims 20 degrees back
  and its shin 7 forward: measured on the skeleton, the knee sat 11 cm BEHIND
  the line from hip to ankle, 29 degrees of a knee hyperextended, in every
  frame of every FK clip, and 9 more on the kick's support leg. The renders
  never showed it, because they pose through IK with the pole in front.
  Planted knees now take a forward pole; a striking leg keeps its FK chamber.
- **He never stood on the floor.** The FK guard's lead ball is 5.2 cm up and
  its rear 4.0, against 2.4 at rest, and "ground" was the guard's own lowest
  foot -- so every FK clip hovered 1.6 cm, the lead foot 1.2 more.
- **The FBX exporter simplified the curves.** Its default
  `bake_anim_simplify_factor` of 1.0 drops keys it judges close enough, and
  on a planted foot that was 8 mm of slide in the file that was not in the
  rig. Every key is kept now; the read-back is what caught it.

Two small changes of judgement, both from the contact sheet: the guard's
breath sinks from the stance instead of rising above it (legs that are all
but straight cannot lift the hips 2.6 cm, and the top of every breath was cut
flat), and its sway goes round in a closed loop rather than a half sine to
one side.

**Saud's clips.** `Content/Animation/Saud/`, 20 FBX, `DT_SaudMotion.csv` and
`saud-motion.png`. His strikes are his `DT_Fighters` row (Jab, Cross, Hook,
Kick, Knee) plus Special, the player's finisher. The rest are the states a
fight holds him in, shaped on the browser's `drawFighter` (index.html:
1504-1576) and timed by the C++ that holds him there, read out of
`FighterBase.cpp` and `SaudCharacter.cpp` rather than copied:

| clip | length | from |
| --- | --- | --- |
| Guard | 2.62 s loop | the browser's standing breath, sin(t*2.4) |
| Walk Fwd / Back / Left / Right | 0.57 s loop | the browser's moving rate, 11 rad/s; stride from MoveSpeed 341 cm/s |
| Dash Fwd / Back / Left / Right | 0.24 s | `DashRemaining` |
| Block | 2.62 s loop | the browser's block pose; fists at the forehead |
| Hit Light / Heavy | 0.22 / 0.34 s | `HitStunRemaining`; the browser's hk = hitT / 0.28 |
| Down | 0.85 s | `DownRemaining`; ends 71 degrees back (the browser's 1.30 rad) |
| GetUp | 0.60 s | the invulnerability the engine calls "brief mercy on getting up" |

Walk and Dash are four clips each because a heading is not a facing here:
the camera and the stick decide one, the opponent the other. At 341 cm/s and
the browser's 11 rad/s the walk is a run -- 35 % of the cycle on each foot
-- and sideways the lead foot steps and the other chases it, at the lag
that keeps them furthest apart; they never cross. The browser draws a dash
as a fast walk; here it is a dip, both feet off the floor and the catch.
Down does not slide 30 px back as the browser's drawing does -- a
picture's offset with no capsule under it -- he sits down and back half a
metre, so GetUp can rise forward over his feet into the guard. Death reuses
Down (the engine holds it 1.05 s against 0.85; the last frame holds).

**The rig gained** a body pivot (`CTRL_pivot`, and `MCH_unpivot` taking its
move back out, so moving it changes nothing and turning it turns everything
below about that point), IK-to-FK and FK-to-IK snapping (`snap_fk_to_ik`,
`snap_ik_to_fk`), and `verify()` checks for the pivot, both snaps, the poles
pinning the knee and elbow without moving the hand or foot, and no stretch
out of reach. `rig_full_ik.py --bite` breaks each of the thirteen mechanisms
and all thirteen checks notice. `rig_full_ik.py --refresh rigs/X.blend`
rebuilds a man's control layer in place in seconds, and every file under
`rigs/` has been refreshed with it.

**Checked, each proved to fail by `build_motion.py --bite`** (six sabotages,
each also run unbroken and passing): planted feet stay where the plan put
them; knees never bend backwards; a straight punch is straight; walking
feet never cross; Down never goes through the floor; GetUp starts where
Down ends. Also held, not bitten: loops close, a walk lifts its feet, a
dash leaves the floor and comes back to the guard, a block's fists are up,
a heavy hit sends the head further back than a light one (24.6 cm against
14.1), Down ends on the floor, GetUp ends in the guard.

**Not verified, the same way the boss clips never were.** No engine has
imported any of this, and nothing plays it: the only montage call is on the
ability path nothing drives (see "The bosses move now"). A walk blendspace,
a state machine that picks Hit or Down, and root motion for the dash are
engine work. The clips are in place; root motion is not in them.

## L_Prologue -- Saud's life before he fell

Since 2026-09-19, and **only in this build**: the game opens on a level that
is not one of the nine districts. `L_Prologue` is a title bout in Saud's own
gym, followed by a short walk to the hole in the street. It plays once --
`ASaudPrologueGameMode` marks it seen on entry and sends every later launch
straight to the souq -- in `L_AlHalqa_World` since 2026-09-23 (see "The game
is played on one seamless world"), in `L_SouqAlDawar` before that.

This is a deliberate exception to the canon in `../saud-fighter/CLAUDE.md`:
"we never see above, it is never named ... If the player never sees home, the
player cannot miss it either." Requested, not assumed. It does not touch the
browser build or the Unity build, and the canon file itself, not this one, is
where that exception is recorded so a future reader does not take it as
general.

What is actually new:

- `Source/SaudFighter/Prologue/SaudPrologueGameMode.{h,cpp}` -- the level's
  own Game Mode, set on `L_Prologue`'s World Settings, not the project
  default. It does not touch `ASaudGameMode`; the duel pays no XP, earns no
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
- `FSaudProgress::bSeenPrologue` in `Game/SaudSaveGame.h` -- the one field
  on that struct that does not mirror the browser build's save schema, since
  the browser build has no prologue for it to mirror.
- `Config/DefaultEngine.ini` -- `GameDefaultMap` and `EditorStartupMap` now
  point at `L_Prologue` instead of `L_SouqAlDawar`.

The duel itself needed no new combat code: it is one `AWaveDirector` with a
single wave and no gates, and the fall is one ordinary `AAreaExit`. Losing
the bout is handled exactly like losing a real stage -- a Blueprint event
fires and nothing forces a restart -- because that is how `ASaudGameMode`
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

## The first area is built, and the men in it are rigged

Since 2026-09-19. Three tools in `Tools/blender/`, and what they leave:

| | tool | leaves |
| --- | --- | --- |
| The place | `build_souq.py` | `Content/Models/Souq/SM_Souq_*.fbx` (34 static meshes), `SouqAlDawar.gltf` (the district placed, 558 instances), `SouqAlDawar_placement.json`, `Content/Textures/Souq/` (13 materials, 39 maps), `Docs/souq-map.png`, `Docs/renders/souq-*.png` |
| The men | `build_fighters.py` (+ `hero/roster.py`, `hero/pipeline.build_fighter`) | `Content/Models/{Saud,Thug,Brawler}.{fbx,gltf}`, `Content/Textures/<Name>/`, `Docs/renders/<name>-*-3d.png`, `Tools/blender/rigs/<Name>.blend` (the animator's file) |
| The rig | `rig_full_ik.py` | the control layer inside each `rigs/<Name>.blend`; nothing of it in the exports |
| The fight | `build_souq.py --scene` | `Tools/blender/scenes/SouqAlDawar_fight.blend`, `Docs/renders/souq-fight.png` |

**SOUQ AL-DAWAR is derived, never authored, and it is the same souq as the
map's.** `build_souq.py` runs the three derivations every other tool
duplicates -- `DistrictExtent`, `SpiralPoint`, `Hash01` -- and then runs
`Tools/levels/build_levels.py`'s own plan for stage 0 in a subprocess and
asserts that every wave, the gate and the three doors land at the SAME
centimetre. What stands on the plots is `build_world.py`'s Souq vocabulary
verbatim (stalls 2.6-5.5 m on a 10 m lattice at 72 per cent, warehouses
one in eight, the rim 2.4-3.2 m gapped at every way out); what it looks
like is the browser build's own painting of the souq (`THEME.souq`: the
arcade bay of two piers and a parabolic arch with a banner and a lantern,
mud-brick blocks with a dome or crenellations, one minaret, the cracked
gate wall of `drawGate`, crates and barrels down the street), with pixels
taken to metres through the 148 px figure. The minaret is the browser's
`minaret(x, y, h)` -- `h` is its SHAFT and the finial reaches 1.22 h -- at
the far layer's own ratio over a warehouse roof: shaft 14.78 m, 18.03 m to
the finial. The numbers the browser does not own -- brick 40 x 20,
flagstone 50, batter 4 cm, recess 60 cm, rim 1.2 m thick -- are listed in
the script's docstring so nobody mistakes them for canon. Materials are
procedural, made periodic on a torus and baked once to tileable maps;
every mesh carries box-projected UVs in metres per tile.

**Fifteen checks over the plan, each proved to bite** by breaking the one
thing it guards: the agreement with `build_levels.py`, nothing solid in the
street, in a fight or off the edge, every door a gap in the rim, the way
through staying inside, the crate the browser's crate and not the distance
constant's, every prop at the kerb, out of every fight and standing ON the
street's 3 cm rather than in it, the gate beside the road in the
AbilityGate's own box, one minaret and it the tallest, no variant far from
its plot. A stall's banner is an instance row of its own, placed once
through the stall's yaw and scale, so the manifest, the glTF and the editor
carry the same 558 objects (342 of them stalls, warehouses, walls, props
and the gate; 216 banners); the banner and the gate wall's crack are wound
to face the street, which a one-sided engine material needs. The static meshes bake centimetres and the
Z-up-to-Y-up change into their vertices (FBX scale 1.0, a file every
importer reads the same; the hero and the clips keep their shared
metres-at-scale-100 convention because a rigged mesh cannot bake its
transform), and the minaret's FBX is read back at 18.03 m and 473 vertices
to prove it. The glTF is held to exactly what was placed: 34 meshes, 558
nodes, 10,388 triangles.

**Run inside the editor it furnishes `L_SouqAlDawar`**, the level
`build_levels.py` made: the Ground cube goes, the sand disc and the street
stand where it stood, the AbilityGate keeps its class, rows and trigger and
carries the gate wall instead of a cube, and every other actor is left
where that script put it. It does not build a second level and it does not
spawn a director twice. It uses the level and actor subsystems, not the
`EditorLevelLibrary` deprecated since 5.0 that the other level scripts
still call.

**The men are the first area's men.** `DT_Stages` stage 0 is three waves of
thugs and brawlers, and Saud walks into them; those are the three built.
Everything that says what one of them looks like -- colours, kit, `sc`,
`build`, `reach` -- is read out of `assets/saud.js` and `assets/enemies.js`
by `hero/roster.py`, because `DT_Fighters.csv` carries none of it ("Known,
not fixed", above). `hero/pipeline.build_fighter` runs the hero pipeline
for a spec at Saud's coordinates up to the bake, then takes the finished
mesh and its joints to the man's own size through the browser's own
mapping (index.html:1379, 1567, 1600): height by `sc`, limb girth by
`build`, torso width by `1 + 0.7(build - 1)`. The arms are carried rigidly
out with the shoulder, hand included -- that rule is this build's, for a
mesh that cannot leave a gap at the shoulder; the browser draws its arms
outside the torso's scale and needs none. The thug is 1.714 m with limbs
at 0.80 and a torso at 0.86 of Saud's; the brawler is Saud's size with a
heavier face -- the face amplitude factors in `pipeline.FACES` are the one
set of numbers here the browser does not own, and they are labelled so.
One body, three men; one skeleton, the mannequin's 62 bones, asserted
identical for all three and exported under `Saud_Rig` for all three, or
the boss clips would not play on them.

**Saud himself was stale.** `Content/Models/Saud.fbx` and
`Content/Textures/Saud/` were last written 2026-09-10; the hero tools were
rewritten 2026-09-19 (the face as a texture, the measured body) and those
commits touched no `Content/` file, so the shipped hero was still the old
model. He is rebuilt here from the current tools.

**The control rig is what an animator poses; the engine never sees it.**
`rig_full_ik.py` puts 13 control bones and 8 mechanism bones over the
mannequin in three bone collections -- DEF is what ships, CTRL is what is
touched, MCH the mechanism between -- and every control is a real control:
four limbs with IK and pole targets and a per-limb `fk` switch; a reverse
foot with `roll` (heel pivot on the floor under the heel, toe pivot on the
floor under the BALL, so the toes stay on the floor to within a centimetre
at full roll while the heel comes up, which is what a kicker's support foot
does -- measured on the shoe's lowest vertex, not only on the bones); a
spine that follows the chest
control a third a bone; a head that tracks `CTRL_look` by `look` along
its Z, which is the face; a `fist` on each hand that tightens all fifteen
finger bones. `verify()` measures each -- the hand reaches, the elbow bends
toward its pole, FK really disconnects, the ankle rises and the toes do
not, the head turns the right way and stops, the fist tightens, the export
set is exactly the mannequin's, the mesh is weighted to deform bones only
-- and `--bite` proves all nine fail when the thing they guard is broken,
on each man's own rig. It holds with the man at the origin and with him
50 m away turned 90 degrees. `strip_for_export` then removes every
control, constraint and driver and leaves the 62 bones; `--roundtrip`
poses a man through the controls, bakes that onto the deform bones,
strips, exports, reads the FBX back and compares every bone: 0.00 mm on
all three.

**What it got wrong first, every one caught by measuring** -- the last
eleven by an adversarial review of the built files, each finding
reproduced by a second, independent pass before it was accepted:

- Every aimed pose twisted the spine, the neck, the head and the feet half
  a turn about their own length. `_aim` (and `build_saud.pose`, which
  every guard and kick render goes through) built each bone's frame with
  `to_track_quat("Y", "Z")`, whose Z is world up; a bone whose rest Z is
  world -Y (the spine, the neck, the head) or straight down (a foot) came
  out turned 180 degrees about itself. The chest faced backwards, the nose
  sat 69 mm behind the head's centre, the soles were above the insteps, the
  reverse foot's floor pivots stood 20 cm in the air, and the "tee pinches
  to a point at the waist" was this twist between the unturned pelvis and
  the turned spine, not a garment. The frame is now the bone's own, swung
  onto the aim with no twist. `Tools/blender/build_motion.py`'s own copy
  of the twisted frame (`reaim`) was fixed 2026-09-23 and then removed
  with the move onto the IK rig ("Saud moves", below).
- `stance()` read joint positions in world space and wrote the hand and
  foot targets back into `PoseBone.matrix`, which is armature space. The
  two agree with the rig at the origin, where every render of the pipeline
  had it, so the first man to stand 56 m out in the souq reached 56 m back
  for his own hands and the whole fight lay on the floor. `stance()` works
  in the man's own frame now, the world setter converts, and a self-check
  fails any stance that leaves a target 3 m from him. The guard posed at
  the origin and posed 50 m away turned 90 degrees differ by 0.01 mm.
- A custom-property write from Python does not tag the depsgraph. Drivers
  read `fk`, `roll`, `look`, `fist` and every one measured 0.0 until the
  write was followed by `update_tag()`; `set_prop` exists for that reason.
- `nla.bake` bakes the SELECTED bones, and a bone in a hidden collection
  cannot be selected. DEF and MCH are hidden for the animator, so the first
  bake wrote the controls -- which are then stripped -- and the deform
  bones fell back to rest the moment their constraints went: 807 mm on the
  hands. The bake shows every collection first.
- The IK solvers were retargeted to the controls AFTER `ik_hand_*` was made
  to follow `hand_*`, so for a moment the solver reached for a bone that
  followed its own result: a cycle the depsgraph reported fourteen times a
  build. The order is the other way now; the saved rig never carried it.
- The pole positions were read from wherever the KICK pose had left the
  Empties, 1.47 cm off rest. They are recomputed from the chains.
- A control that drives a deform bone through Copy Transforms must share
  that bone's rest exactly; `CTRL_root` along +Y rotated the hierarchy and
  put `ik_hand_gun` 1.2 off.
- The toe pivot under the toe TIP lifted the ball; it is under the ball.
- The fist at 78 degrees a joint corkscrewed the fingers; it is 10, with
  the sign probed on the built hand rather than assumed.
- The size field sheared the hands: a limb thinning applied to a hand that
  was also being carried out with the shoulder. The arms move rigidly with
  the shoulder now, hand included, and every field is evaluated on the
  canonical positions.
- Bone heat leaves a handful of weights a few thousandths over one (35 on
  Saud, up to 1.011) and the exporters call the mesh invalid for it. They
  are clamped once, on the joined mesh.
- The face's tonal zones, blood, shadow and lips in `hero/face.py` were
  written as the colours they come to on Saud's `#f0d8c4` and laid over
  any face as those absolutes: the thug had Saud's face on a brown neck.
  Each is now the same move applied to the man's own skin -- its ratio to
  `SAUD_SKIN` in linear light -- and on Saud that is the number as
  written, checked to 1e-9.
- The brawler's heavier nose put the profile's peak at 30.1 mm against the
  20-30 `sculpt.check_profile` holds every man to (a real male nose). His
  tip is 1.05, not 1.10: 29.3 mm.
- The toe box was two thirds foot and one third ball, so a toe roll pitched
  the whole shoe with the foot bone and its toe went 35 mm through the
  floor while the bones said the toes stayed flat. Everything ahead of the
  ball joint that the two bones hold now belongs to the ball, and
  `verify()` reads the shoe's lowest vertex as well as the bones.
- Cycles' diffuse colour pass includes the sheen closure's albedo, so every
  dark roster colour baked lighter: Saud's tee `#15171c` came out (32,33,37),
  more than double in linear light. The sheen is off for the colour pass.
- The soles were painted and never baked: their quadrant of the shoe's
  maps stayed black, and black roughness is a mirror. They bake into the
  shoe's own images now.
- Half of each thumb's middle segment lay outside the hand's chart and
  baked black; the chart's radius is 0.10 with an along-axis clause that
  keeps the forearm on its cylinder.
- The body was stripped under the tee up to 1.53, above the collar ring's
  lowest point at 1.507, so the 26 mm between ring and neck looked into
  the tee's black inside. The strip stops at 1.50.
- The banners were a Blender-side afterthought: parented to their stall
  and multiplied by its scale twice, 43 of 216 hung in front of the piers,
  and none was in the manifest or the editor. They are rows.
- The banner quad and the gate wall's crack were wound to face into the
  building. Cycles does not cull; an engine's default material does.
- The men, the crates and the barrel stood at z = 0, 3 cm inside the
  street that stands 3 cm proud of the sand. One constant, `STREET_Z_CM`,
  the props carry it, a check asserts it, and the scene asserts every man's
  lowest vertex is at the flagstones.
- The animator's file was saved before the render made its camera and
  deleted it, so F12 had no camera. The cameras stay and the file is saved
  after the render.
- `verify()`'s hand probes pushed the control along world -Y and read the
  reach and the bend along world Y, so a correct rig turned 180 degrees
  failed them. They work in his own frame, like the look probe.
- The control widgets were scaled by bone length as well as by the metres
  written for them: 2.4 mm pole spheres on 6 cm bones. The size is the
  metres.

And two in the souq: a spur that begins on the street's centre line lies on
the ribbon, coplanar, and a renderer's shadow ray off one face strikes the
other at zero distance -- the overlap rendered black under any light (and
would z-fight in the engine); each spur is cut where it leaves the ribbon,
tucked 5 cm under it and 1 mm lower. And the plan carried the minaret's
shaft as its height, which the FBX read-back caught the first time it ran.

**Seen, reported, not touched.** The trousers carry a web between the
thighs from the crotch down to z = 0.70 -- 218 vertices within 15 mm of the
midline, the same 218 on Saud and on the thug -- because the body's crotch
is welded shut ("The crotch is 54 mm too low", Known, not fixed) and the
garment is a shell off it. In the guard, with the legs staggered, the web
stretches between them; on the thug's thinner legs it shows plainly. It is
that item, not the size mapping, and it is left as that item is.

**The scene.** `build_souq.py --scene` appends the three rigged men into the
built souq at the second wave -- Saud, two thugs and the brawler -- in
the browser's own formation (index.html:3597, :3998: each enemy at his
reach x 0.70 plus his lane from Saud, in front of him for even, behind
for odd, browser pixels at 2.4 cm), posed through their controls: guard,
fists, every man squared up to Saud and looking at him, Saud at the
first of them, every man standing on the flagstones. It renders that and
saves it with its cameras. That file is the deliverable an animator opens.
A `--scene` run rebuilds and re-exports the district first, so the 34 FBX
files come out again with the same geometry, materials and texture
references but new object ids throughout (Blender's exporter derives every
id from Python's per-process string hash) and a new header timestamp:
every `--scene` run leaves all 34 tracked FBX files changed in git.

**Known, not fixed, found on the way:** every editor script that places a
rotated actor -- `build_levels.py:374`, `build_world.py:641,707` (fixed
2026-09-23: the open world is played on it),
`build_island.py:904,1001`, `build_prologue.py:206,247` -- calls
`unreal.Rotator(pitch, yaw, 0)` or `unreal.Rotator(0, yaw, 0)` positionally.
The Python `unreal.Rotator`'s positional order is `(roll, pitch, yaw)`, not
C++'s `FRotator(Pitch, Yaw, Roll)`, so a sun's pitch lands in its roll and
an actor's yaw in its pitch. `build_souq.py` names its arguments; the others
are left as they were because fixing them was not what was asked. And the
glTF exporter keeps four influences a vertex where heat gives some verts
five or more; the FBX, which is what Unreal imports, keeps them all.

**Unverified, like everything else here.** No engine has imported a mesh, a
texture or a rig from this work; the FBX and glTF are written by Blender and
read back by Blender, and that is the whole proof. The editor half is
read-reviewed, not run. Three things that will need an engine to settle:
the three men share one `USkeleton` with different bone lengths, so the
boss clips play on the thug only with per-bone Translation Retargeting set
-- `root` and the seven `ik_*` bones from the animation, `pelvis`
animation-scaled, the rest from the skeleton -- or his feet slide; the
street and ground are given `QUERY_AND_PHYSICS` collision and rely on the
importer's generated collision; and the glTF is a viewer artefact --
Unreal imports the per-kind FBX, not the glTF.

## Working rules

- **Don't add things that were not asked for.** Build the requested change and
  nothing beside it. If something else looks wrong or missing, say so in a
  sentence and wait to be told.
- **The browser project is the source of truth for every number.** Balance
  lives in `../saud-fighter/assets/*.js`. Never hand-edit anything in
  `Content/Data` — change the assets (the control panel at
  `../saud-fighter/panel/` is the comfortable way) and run
  `node Tools/export/export.mjs --api`. `--check` fails a build if the two
  have drifted.
- **This project has never been compiled.** It was written without an engine
  to build against. The C++ is idiomatic UE 5.4 and the data is complete, but
  expect to fix a compile error or two on a first build, and do not describe
  any of it as verified until it has actually built. The two exceptions are
  `Combat/SaudArena.h`, which `Tools/harness/run.sh` compiles and executes
  — that file's arithmetic is checked, and no other C++ here is — and
  `Tools/audio/master.py`, which is Python, runs, and has.
- **iOS is Mac-only.** There is no cross-compile. `Tools/ios/build-ios.sh`
  checks for this and says so rather than failing halfway through a cook.

## Known, not fixed

Written down rather than fixed, because fixing them was not what was asked.
Don't re-discover them; don't fix them without being told to.

- **The player's rage finisher does nothing.** `SaudCharacter::Input_Rage`
  calls `StartAttack(TEXT("Rage"))`, and there has never been a `Rage` row in
  the attack table — the finisher is `Special`. `StartAttack` returns false,
  so the meter never spends and nothing happens. One word to fix. The same
  bug on the enraged boss *was* fixed, because that one was inside the fight
  style work.
- **ZAYOS has no legal strike at Long range -- decided, 2026-09-23: as
  designed, not touched.** His style carries no Kick and no Knee, so
  `ChooseStrike` finds nothing in the 186.6-328.7 cm band. This entry used
  to say nothing in the code marked that as deliberate; it does.
  `Tools/levels/build_data_assets.py`'s `STRIKE_BANDS` table says so
  directly -- "a knee is a close-range strike whoever throws it, and an
  archetype that only knows knees is an archetype that has to get inside to
  do anything at all. That is what makes a grappler read as a grappler" --
  and `USaudFightStyleData::ChooseStrike` and `UFightStyleComponent::
  TickOffence` both carry the same call spelled out for every archetype:
  "Nothing to throw from here. Not a failure -- it is the whole reason a
  boxer walks forward instead of swinging at air," and offence returning
  empty never stops the approach tick, which closes distance every frame
  regardless of band -- so an empty Long band is a puncher having to get
  inside, not a fighter stuck standing there. No move in `STRIKE_BANDS`
  reaches Long except Kick, and ZAYOS only ever punches (`build_motion.py`
  asserts he never gets a leg clip), so the one way to give him a Long
  answer is a move type he canonically does not have. Left as it is.
- **The UE5 fighter table drops how big each man is.** The browser carries
  `sc` and `look.build` per archetype -- ZAYOS is 1.55 and 1.60, half again
  the size, which is his whole identity -- and `DT_Fighters.csv` has no
  column for either. `build_motion.py` reads them out of `enemies.js`
  directly because it needs them; anything else that needs them cannot.
- **The tee pinched to a point at the waist in the fight poses** -- and it
  was not the garment. It was the half-turn twist every aimed pose put on
  the spine above an unturned pelvis (see "The first area is built": the
  aim), and it went with that fix: the posed mesh's slice at z 1.04 was
  35 x 52 mm and is 220 x 209. The entry stays so the misdiagnosis is on
  record. `build_motion.py`'s clips carried the twist too until
  2026-09-23; they no longer do.
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
- **The editor scripts pass `unreal.Rotator` its arguments in the wrong
  order.** `build_levels.py:374`,
  `build_island.py:904,1001` and `build_prologue.py:206,247` call
  `unreal.Rotator(pitch, yaw, 0)` or `unreal.Rotator(0, yaw, 0)`; the Python
  constructor's positional order is `(roll, pitch, yaw)`, so a sun's pitch
  lands in its roll and an actor's yaw in its pitch. Found while writing
  `build_souq.py`, which names its arguments. `build_world.py` was fixed
  2026-09-23, because the game is played on its map now; the other three
  are left as they are.
- **Enemy strikes do not go through the ability system.** Enemies (and the
  player) still throw via the legacy `AFighterBase::StartAttack` state
  machine; the GAS layer exists beside it rather than under it. Moving combat
  onto abilities for both sides is a separate job, and a large one.
- **Thug and Brawler are built against the old guard aims and the old hair
  cap.** Both are shared code (`build_saud.GUARD`, `assembly.hair_parts`)
  and both changed 2026-09-20 for Saud (see "A second pass"); their models,
  renders and the fight scene's copies of them are as they were. One
  `python3 build_fighters.py thug brawler` and a `build_souq.py --scene`
  brings them level. Not run, because only Saud was asked for.
- **Saud in a cel-shaded, "Hi-Fi Rush" look -- asked 2026-09-20, Saud only.**
  That look is a real-time material: a stepped diffuse ramp, a Fresnel rim,
  an inverted-hull or post-process outline. It lives in the engine, not in
  the PBR bake this pipeline writes, and no engine has ever been run against
  this project, so nothing of it can be built or looked at here. The
  palette half of the ask was done (`col.band`). The material is for
  whoever first opens this project in the editor.
