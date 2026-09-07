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
  any of it as verified until it has actually built.
- **iOS is Mac-only.** There is no cross-compile. `Tools/ios/build-ios.sh`
  checks for this and says so rather than failing halfway through a cook.
