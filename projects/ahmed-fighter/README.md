# AHMED — Kuwait Fighter

A 2D mobile Metroidvania beat-'em-up. Ahmed is a young Kuwaiti fighter working his
way from the old souq to the national title, MMA / kickboxing style. Kuwait is one
connected world — you walk between its nine places, and most of the routes between
them stay sealed until you earn the talent that opens them.

Everything is procedural — the characters, the backgrounds, the sound and the music
are all generated in code — so the whole game is **one HTML file with no assets and
no dependencies**. Open it and play.

---

## Run it

**Phone / tablet:** copy the folder onto any web host (or open `index.html` straight
from the file system) and open it in the browser. Turn the device to landscape.

**Add to home screen:** served over `http(s)`, the manifest + service worker make it
installable and fully playable offline.

**Desktop:** double-click `index.html`.

> The service worker only registers over `http(s)`. From `file://` the game still runs
> fine, just without offline caching.

---

## Controls

| Action | Touch | Keyboard |
| --- | --- | --- |
| Move (x and depth) | Virtual stick — anywhere on the left half | `WASD` / arrows |
| Punch combo | `PUNCH` — tap 3× fast for jab → cross → hook | `J` |
| Kick / knee | `KICK` — roundhouse at range, knee up close | `K` |
| Block | Hold `BLOCK` (−80% damage) | Hold `L` |
| Perfect parry | Tap `BLOCK` in the instant a blow lands | `L` on the beat |
| Dodge dash | Tap `BLOCK` while moving (brief i-frames) | `L` while moving |
| Rage finisher | `RAGE` at 100% meter | `Space` |
| Pause | Pause button, top right | `Esc` / `P` |

**Stamina** (blue bar) pays for strikes and dashes and refills quickly.
**Rage** (purple bar) fills as you land and absorb hits; at 100% it unleashes a
spinning finisher that hits everyone around Ahmed.

**Perfect parry** is the skill ceiling. Press block within a fifth of a second of
an incoming blow and Ahmed takes no damage at all, the attacker is staggered out
of their swing, and you get rage and stamina back. Holding block the whole time
never parries — you have to read the punch.

Phones vibrate on impact — toggle it in the pause menu, along with sound, music
and fullscreen.

---

## Loot

Crates and barrels line every stage and each one takes two hits. Smashing them
drops pickups you collect by walking over them:

- **Skewer (green)** — heals 28% of max health.
- **Rage orb (purple)** — adds 45% rage.

Beaten enemies drop loot too, about one in six. A downed boss always does.

---

## The world

Kuwait is one connected place, not a stage list. Walk off the east edge of an
area and you arrive at the west edge of the next one — no menu, no loading
screen, carrying the health, mana, rage and weapon you were holding a step
earlier. Walk back and you return the same way.

The world is a ring with a hub. Souq Mubarakiya is the hub: its east edge starts
the loop, its west edge is a shortcut to the Desert Camp that only exists once
you have beaten the Desert from the other side, and a door partway along it
leads to the Arena. Every link is two-way, and every link is symmetric — if a
route wants POWER KICK from one side it wants POWER KICK from the other, so no
route can ever strand you.

Most routes are sealed until you carry the right talent. Walking into a sealed
route pushes you back and names what it wants (`SEALED — NEEDS VAULT`). A route
whose talent you hold but whose far side you have not yet earned says
`NO WAY THROUGH YET` instead.

An area you have cleared stops spawning ambushes and becomes a corridor — the
scenery and the loot stay, the waves do not. That is what makes backtracking
for a talent bearable.

`assets/world.js` is the whole graph:

```js
areas: [
  { w:{to:7,needs:'vault',afterCleared:7}, e:{to:1}, d:{to:8,at:1900,needs:'hawk'} },
  ...
]
```

`w` and `e` are the west and east edges, `d` is a door at a given `x`. `needs`
names a talent; `afterCleared` names an area that has to be beaten first.
Editing this file re-wires the world — nothing else needs to change.

## The map

**THE WORLD** draws that graph rather than a row of stage buttons:

- A route you can walk is **solid gold**; one that is sealed is **dashed grey**
  with the icon of the talent it wants sitting on it.
- An area you have not reached is a grey **?**. One you have visited is red;
  one you have cleared is green.
- The area you are standing in carries a pulsing gold ring.
- A gold **!** on an area means you now hold the key to something still sealed
  inside it.
- Tap any **visited** area to fast-travel there. Unvisited ones are inert —
  you have to walk to a place once before the map will send you back.

## Stages

Nine areas, each with its own backdrop, enemy mix and story beat. Fast-travel
opens a briefing first — the story so far, who is waiting, and your best rank
there.

| # | Stage | الاسم |
| --- | --- | --- |
| 1 | Souq Mubarakiya | سوق المباركية |
| 2 | Salmiya Gym | نادي السالمية |
| 3 | Sharq Fish Market | سوق شرق للسمك |
| 4 | Kuwait Towers | أبراج الكويت |
| 5 | Marina Crescent — boss: **AL-SAQR / الصقر** | مارينا كريسنت |
| 6 | Failaka Island | جزيرة فيلكا |
| 7 | Jahra Road | طريق الجهراء |
| 8 | Desert Camp | مخيم البر |
| 9 | Kuwait Arena — boss: **AL-WAHSH / الوحش** | بطولة الكويت |

## Levels, XP and MP

Two currencies that are easy to confuse, so the code keeps them apart:

- `save.xp` is **spendable** — the training camp draws it down.
- `save.xpTotal` is **earned** — it only goes up, and it is what sets the level.

Spending everything in training therefore never costs you a level. Every award
routes through one `grantXp()` so the two can't drift, and it is what fires the
rank-up toast. Twenty levels, each worth +6 max HP and +4 max MP, with a rank
title (ROOKIE → CHAMPION) shown under Ahmed's name.

**MP** is the fourth bar, and it exists so talents have a cost. It refills
slowly on its own and by 4 on every landed hit, so it rewards staying in the
fight rather than backing off — and a lit punch that lands spends it while a
cold one earns it back.

Saves from before levels existed have no `xpTotal`; it is seeded from the
spendable balance, which under-counts anything already spent. That is the safe
direction — a returning player gains levels, never loses one.

## Talents

Five now, all found in the world rather than bought (see `assets/talents.js`).
The fifth is **HAWK FIST / قبضة الباز**, behind the cracked wall at the Desert
Camp — the stage that already had a fire burning in it.

It sets Ahmed's punches alight: ×1.55 damage, a little more reach and
knockback, and fire on the fist that flares on the swing. **Punches only —
kicks stay cold.** Each lit punch that lands burns 14 MP, so the loop is spend
it down, throw cold jabs to earn it back, and pick your moment. It is a
resource you manage, not a permanent damage upgrade.

Like the weapon swing, a lit attack builds its own copy of the `ATK` entry
rather than editing the shared table — otherwise every enemy's punches would
catch fire the moment Ahmed found it.

## Weapons

Crates and barrels drop a **steel pipe**, **plank** or **crowbar** as well as
food and rage orbs. Walk over one to pick it up.

Every weapon boosts punches **only, never kicks**. That is the whole design: an
armed Ahmed hits harder and reaches further but gives up the kick game, so
picking one up is a choice about how to open a crowd rather than a free
upgrade. Uses are spent on swings that **connect**, so whiffing costs nothing
but time, and the HUD counts down the swings left.

| | Punch damage | Reach | Swings |
| --- | --- | --- | --- |
| Steel pipe | x1.9 | +26 | 12 |
| Plank | x1.6 | +22, heaviest knockback | 8 |
| Crowbar | x2.2 | +20 | 9 |

The `ATK` entries are shared between every fighter, so an armed swing builds
its own copy rather than letting the weapon rewrite the table in place — which
would have had every enemy hitting like a crowbar the moment Ahmed picked one
up.

## Who you fight

Every archetype is built to be recognised across the arena, before it swings.
Silhouette does the work — height, bulk and headwear read at a glance where a
colour swap does not, especially in a five-enemy wave.

| | Trait | Reads as |
| --- | --- | --- |
| Thug / بلطجي | Basic punches, barely guards. | smallest man on screen, grey tee |
| Brawler / مشاكس | Three-punch pressure. | stocky, bearded, rust tee |
| Runner / خطّاف | Very fast, low health, strikes and retreats. | slight, orange hoodie, peaked cap |
| Kickboxer / ملاكم | Long range, kick-heavy. | green hoodie, track pants, taped fists |
| Bouncer / حارس | Slow wall of a man, guards 62% of the time. | bald, sunglasses, black on black |
| Grappler / مصارع | Knees and hooks, hard to knock down. | bald, scarred, grey tee, huge |
| Enforcer / مُنفّذ | Fast technical combos. | sunglasses but hair, teal jacket |
| Contender / منافس | Uses the full moveset. | purple jacket over indigo jeans |
| **AL-SAQR / الصقر** | Mid-campaign boss. All legs, no patience. | navy hoodie, track pants |
| **AL-WAHSH / الوحش** | Final boss. Two phases. | biggest, bald, full beard, black |

Everyone fights in street clothes, not gym kit: a shirt or hoodie or jacket
over separate trousers, and trainers. Two rules make that read.

**The top and the trousers have to be different tones.** Matching them turns
the whole figure into one silhouette that scans as a tracksuit, not as someone
who got dressed. Every archetype pairs a coloured top against dark denim — the
Bouncer is the deliberate exception, black on black, because a doorman is
supposed to look like that.

**A stripe down the seam is track pants, so it is its own flag.** `stripe` is
opt-in rather than riding along with `pants`; Ahmed, the Kickboxer and AL-SAQR
have it, everyone else is in jeans.

Nobody wears boxing gloves with jeans, so `hands` picks `bare` knuckles or
taped `wraps` instead. Ahmed keeps red, now as tape.

The kit is a `look` object on each `TYPES` entry, applied in `makeEnemy`, and
it uses the same flags Ahmed does — plus `hoodie`, `jacket`, `hands`, `stripe`,
`bald`, `cap`, `headband`, `shades` and `scar`. Adding an archetype means
adding a look, not new drawing code.

Each stage scrolls through three locked waves. Clear a wave to move on, reach the
gold **EXIT** gate to finish the stage.

**Both bosses fight in two phases.** Below half health they go berserk — faster,
harder, and they gain the spinning finisher. They also shrug off most knockdowns,
so you cannot stunlock them the way you can the smaller fighters.

**SURVIVAL** unlocks once you take the title. Endless waves that grow in size and
tier, a boss every sixth wave, and your furthest wave is recorded. It ends only
when Ahmed goes down.

## Abilities and sealed routes

Abilities seal two different things, and it is worth keeping them apart:

- **Routes between areas** (in `assets/world.js`) are the spine of the world.
  These *do* block the way forward — that is the point — and the graph is built
  so that whatever you can reach always contains the talent for the next route.
- **Gates inside an area** sit in the back wall, so an area is always completable
  without them. They hide XP caches and the talents themselves.

Finding a talent sends you back through areas you have already cleared, which
by then are quiet corridors. The map marks the trip: a gold **!** on an area
means you now carry the key to something still sealed there, and a dashed grey
route means you do not.

| Ability | Found | Opens |
| --- | --- | --- |
| **VAULT** ⤴ / وثبة | Salmiya Gym, in a locker | ledges |
| **DASH LEAP** ⇥ / قفزة | Sharq Fish Market, up a ledge | broken ground, and lengthens your dodge |
| **POWER KICK** ⚡ / ركلة قوية | Marina Crescent, across a gap | steel shutters |
| **HAYMAKER** ✊ / قاضية | Jahra Road, behind a shutter | cracked walls |

Ledges and gaps open by reaching them. **Shutters take three kicks; cracked
walls take three punches** — the right family of strike, not just any hit. Once
HAYMAKER is yours, cracked walls in Souq Mubarakiya, Kuwait Towers and Desert
Camp pay out XP caches.

## Difficulty

Set on the map screen; it applies immediately to every fight.

| | Enemy damage | Enemy health |
| --- | --- | --- |
| ROOKIE / مبتدئ | ×0.62 | ×0.78 |
| PRO / محترف | ×1.00 | ×1.00 |
| CHAMPION / بطل | ×1.45 | ×1.38 |

## Achievements

Twelve awards track the long game — first knockdown, a 25-hit combo, 50 crates,
25 perfect parries, beating each boss, an S rank, a Champion clear, maxing a
training track, survival wave 10, and clearing all nine stages. They pop as a
toast the moment you earn one; the full list lives under **AWARDS** on the menu.

## Ranks

Clearing a campaign stage scores you **S / A / B / C** from kills, best combo,
health remaining and time taken, adjusted for difficulty. Your best rank per stage
shows on the map — chasing S is the reason to replay a stage you have already won.

## Progression

Kills and clear bonuses pay XP. Spend it in **TRAIN** on five tracks (5 levels each):
**Boxing** (+10% jab/cross/hook), **Kicking** (+10% kick/knee/rage), Vitality,
Speed and Stamina. Abilities are never bought — they are found in the world, and
TRAIN shows which ones you are still missing. Progress, XP, ranks, difficulty, the survival
record, achievements, lifetime stats and settings are saved in `localStorage`
under `ahmed_kuwait_fighter_v1` — the game runs fine without storage (private
mode), it just won't remember anything.

**Settings** (menu → SETTINGS, or from pause) covers difficulty, sound, music,
vibration, fullscreen, lifetime stats and a reset-progress option behind a
confirmation.

---

## Ahmed's look

Ahmed is styled as a gym-built Kuwaiti fighter: fair skin, a broad-shouldered
V-taper on a heavier build, a black fitted training tee with short sleeves,
black long trousers with a red seam stripe over a red waistband, a Kuwait flag
patch on the chest, dark trainers, a swept-up quiff with
faded sides, a full trimmed beard, a black wristwatch and red gloves. The
character flags that drive it live on the fighter object, so any fighter can
wear the same kit:

| Flag | Effect |
| --- | --- |
| `tee` | draws shirt sleeves over the upper arms |
| `pants` | legs are drawn in the trouser colour, not skin, with a stripe down the outer seam, a knee crease and an ankle cuff |
| `patch` | a small Kuwait flag on the chest of the tee |
| `build` | multiplies limb thickness and chest width; 1 is lean, Ahmed is 1.12 |
| `quiff` | swept-up hair with faded sides instead of a rounded cap, no headband |
| `beard` | full beard and moustache (a colour string) |
| `hair` | overrides the hair colour |
| `watch` | wristwatch on the lead arm |
| `sil` | featureless silhouette, used for the key art's opposition |

## Assets

The game's data lives in `assets/`, one file per thing, so a table can be
edited without opening the 4,000-line renderer:

| File | Holds |
| --- | --- |
| `assets/ahmed.js` | the player: base stats, what each upgrade level adds, palette and kit |
| `assets/enemies.js` | the ten archetypes — stats, palette, `look` |
| `assets/hits.js` | every strike: damage, startup/active/recovery, reach, cost |
| `assets/talents.js` | abilities found in the world, and the gates they open |
| `assets/upgrades.js` | the five stat tracks XP is spent on, and the price curve |
| `assets/weapons.js` | what a smashed crate can put in your hands |
| `assets/levels.js` | the XP curve, what a level is worth, and the rank titles |

They are **plain scripts, not modules**, loaded in order before the game.
That is deliberate: ES modules do not load over `file://`, and this game has
to keep working opened straight off disk with no server and no build step.

The game reads these and never keeps its own copy — `ATK`, `TYPES`, `UPS`,
`ABILITIES` and `GATES` are now bindings, not literals. On start it checks all
five are present and throws naming the missing file, because a game running
with an empty enemy table is worse than one that refuses to start. `sw.js`
caches them with the same weight as `index.html`, so offline play still works.

Extracting them turned up one thing worth keeping: the upgrade ceiling was a
bare `5` copied into four places. It is `ASSET_UPGRADES.maxLevel` now.

## Interface

The screens grew one control at a time, and it showed: BACK was 170x58 on the
map, 220x48 in settings, 140x64 on the briefing and 210x66 on the results
screen — the same button, four sizes, four positions. `UI` exists so that
cannot happen again.

| Token | Holds |
| --- | --- |
| `UI.sp` | the 8pt spacing scale — gaps and offsets come from here |
| `UI.t` | one type size per role: display, title, head, sub, body, label, micro |
| `UI.btn` | `lg` / `md` / `sm`; the same control is the same size everywhere |
| `UI.navY` | the single y every screen's nav row sits on |
| colour roles | `ink0..3`, `fg`/`fgMut`/`fgFaint`, `gold`, `red`, `green`, `line` |

Four components carry almost every screen: `screenHead(en, ar)` opens with the
flag mark, name and Arabic; `panel()` is the one panel treatment; `navRow()`
places the footer buttons; `flagBar()` is the Kuwait hoist bar reused as the
identity mark. A screen picks a role, never a number.

The system reaches the fight HUD, the toasts and the results screens too — the
first pass only migrated the menus. Two things that unification turned up:

**There were two golds and two greens.** `C.gold` was `#e0b34a` across 36 call
sites while `UI.gold` was `#edbe57` across 15, and the key art uses `#edbe57`.
`C` is defined before `UI`, so it cannot reference the token by name — the
brand value is written into `C` as a literal and both names now agree, which
fixed all 36 sites in one edit. `UI.green` held an invented `#1a8f52` with zero
call sites; a dead token carrying the wrong value is a trap, so it is the flag
green `#007a3d` now.

**The achievement toast never faded.** `txt()` *assigns* `ctx.globalAlpha`
rather than multiplying it, so the plate faded in and out while the type
snapped to full opacity — about 0.9s of mismatch ending in a hard cut. Every
other animated text site in the file passes its alpha explicitly; this one was
the outlier. It also sat exactly on the stage banner mid-fight (plate y 10-76,
banner y 12-74), so it now drops below it during a fight.

Three rules behind the look:

**One red thing per screen.** Red is the action you came to press — FIGHT on
the menu and the briefing, RESUME on pause. Everything else is a dark panel
with a gold hairline, so the eye lands without hunting. Gold went from being
on everything (headings, subtitles, borders, values, Arabic) to marking values
and headings only.

**The nav row is in the same place on every screen.** That is a usability
change, not a cosmetic one: BACK stops moving between screens.

**The background is the key art.** Same warm off-centre pool falling to near
black, so the poster, the store page and the title screen read as one design.
The sadu weaving — the Kuwaiti motif — is two crisp bands aligned to the
header and nav rows, replacing ten faint lines that floated mid-screen and
read as noise.

## Graphics

Everything is still drawn in code — there are no image files — but the game is
**lit** rather than coloured in. The approach is the one a 3D engine takes,
carried over to a 2D canvas: a scene owns lights, every surface answers to
them, and the finished frame goes through a post chain before you see it.

### The lighting rig

Each of the nine places owns a rig, in its `THEME` entry. Nothing downstream
knows which stage it is drawing — it asks the rig.

| | What it is | Why it matters |
| --- | --- | --- |
| `key` | the sun, or the strip light overhead — direction and colour | sets the whole mood |
| `fill` | the sky bouncing into the shadow side; always cooler, always weaker | stops shadows going dead black |
| `rim` | a light behind the fighter catching the silhouette edge | the single biggest reason a figure reads as solid rather than as a sticker |
| `toe` | where black actually sits | film never reaches 0,0,0 |
| `shoulder` | where white rolls off | highlights bend toward the key instead of clipping |
| `grade` | the split-tone that gives the stage its colour identity | |
| `bloom` `haze` `exposure` `contrast` `saturate` | the post chain's dials | |

So the Souq is a low warm sun down the length of the market with a cold sky
filling the shadows; Salmiya Gym is hard strip lights straight down and almost
no bounce; Marina Crescent is neon, where nothing is white and the silhouette
edge burns magenta; and the Arena is lit like a title fight — hard spots
overhead, two more behind, and blacks allowed to go black.

Limbs are shaded as lit cylinders with the key on one side, the sky bounce on
the other and the rim as a **band** at the silhouette edge — a single stop at
the very edge lands under the outline stroke and vanishes, which is what
happened the first time. Ambient occlusion at the joints takes the fill
colour rather than black, because occlusion is light that did not arrive, and
it offsets away from the key so a joint reads as a crease. Contact shadows
cast away from the key, tightening as a fighter lands and spreading as they
rise. Props are lit by the same rig — a crate shaded by a different rule than
the fighter standing next to it is the fastest way to make a scene look
assembled rather than lit.

### The post chain

Run in the order a camera would, after the scene is drawn and before the HUD:

1. **Bloom** — the frame's highlights, gathered at a sixth resolution and added
   back. The threshold is solved exactly (`brightness(b) contrast(c)` is an
   affine ramp, so `b` and `c` are chosen to put the knee at 0.84): a threshold
   that lets mid-tones through turns bloom into fog, which is the failure mode.
   Gathered on alternate frames — bloom is the lowest-frequency thing on screen.
2. **Tone map** — exposure, the S-curve and the film stock's saturation, in one
   pass through the GPU's own colour pipeline.
3. **Toe** — `lighten` with a dark tinted fill only ever raises a pixel, so it
   lifts the blacks and leaves everything above them alone.
4. **Shoulder** — `darken` with a near-white does the mirror at the top end.
5. **Grade** — the stage's split-tone.
6. **Vignette** — a lens effect, so it sits on top of the grade.
7. **Grain** — the film the whole thing was shot on.

Depth of field blurs the far layer only. The trap: a canvas filter applies to
every *draw call*, so setting one and running the backdrop blurs the whole
frame once per rectangle — that measured at **1fps**. The layer is rendered
into a half-size buffer instead and blurred once on the way back.

### The camera

A heavy landing punches the lens in toward the impact and eases out. Between
hits the frame never sits perfectly still — a slow, low-frequency drift, with
a hair of overscan so the sway never drags an empty edge into view.

### Three tiers

Scalability, measured rather than guessed. **CINEMATIC** is the full post
chain; **REALISTIC** is the lighting rig without it; **FAST** is flat fills.
The game starts at the top and walks down one step at a time until the device
holds frame rate, taking a fresh sample after each step — the post chain reads
the frame back per-pixel, which is nearly free with a GPU and ruinous without
one, so that tier can be dropped without dropping the lighting with it. A
player who sets the tier themselves is never overridden.

## How a stage is drawn

Each location is a `THEME` entry with five layers, drawn back to front:

| Hook | What it draws |
| --- | --- |
| `clouds` | a slow cloud band, config not code — every theme wants the same drift in a different colour |
| `far` | skyline, sea, dunes; barely parallaxed, and softened by depth of field |
| `mid` | the layer that names the place — arches, heavy bags, dhows, tents |
| `floor` | the ground the fight happens on |
| `air` | whatever drifts through frame: dust, gulls, embers, confetti |

### The backdrop vocabulary

`far` used to be nine hand-rolled loops of `fillRect`, which is why every
place had the same skyline in a different colour. It is also the layer the
depth-of-field pass softens — detail there is thrown away and only
**silhouette** survives. So it is built from shapes now, and stacked two or
three deep at different parallax rather than one band:

| Helper | The thing it is for |
| --- | --- |
| `skyline` | a band of buildings whose crowns disagree — stepped, masted, roof-tanked, flat. A skyline of plain boxes reads as a bar chart; what makes it a city is that the tops differ. |
| `dhow` / the harbour rig | a hull that lifts to a high stern, a mast raked forward, a lateen yard the sail hangs from. A box hull with a vertical mast is a dinghy — this is the shape Sharq is recognised by. |
| `palmFar` / `palmTrunk` | fronds that droop and disagree, on a trunk that leans. Six ellipses at even angles read as a starburst, not a tree. |
| `minaret` / `domeRoof` | the two shapes that say *old city* rather than *high street*. The minaret is placed rather than sprinkled — it is the one thing taller than the arcade, so it has to clear it. |
| `duneBand` / `ridgeBand` | sand and rock. Three dune lines at different parallax is the whole desert. |
| `tentFar`, `mastField` | the camp, and the boats a marina has in it. |

Everything here draws one flat silhouette. The rig's fog and haze do the
atmospheric perspective; these only have to get the shape right, and the shape
is what tells you where you are standing.

Three rules keep the nine stages reading as one game:

**The floor is the stage.** Souq is worn flagstone, the gym is a taped mat,
Sharq is hosed-down concrete holding puddles, Marina is boardwalk under neon,
Jahra is asphalt with lane dashes, the desert is dune ripples, the arena is
championship canvas under spotlights. Before this each stage had the same
gradient slab, and nine locations looked like one.

**Ground joints run parallel, not converging.** The camera is side-on: `f.x`
is drawn at `f.x - camX` with no scaling by depth, so a vanishing point would
fight the way fighters actually move. Depth comes from the cross rows instead —
they crowd toward the back wall and fade with distance. `groundRow()` hands
callers `sc` for sizing only, never for spacing.

**Haze is applied twice.** Once over `far`, then again at a quarter strength
over `mid`, so the middle distance sits between the backdrop and the fighters
instead of reading as hard as the foreground. A short band across `FLOOR_TOP`
settles the backdrop into the floor; without it the horizon is a cut edge.

Everything in `air` and `clouds` is behind `GFX_HIGH`, so fast mode keeps the
floors and drops the atmosphere.

**GRAPHICS: CINEMATIC / REALISTIC / FAST** in Settings (or pause) cycles the
three tiers described under *Graphics*. The game samples real frame times
during a fight and steps down one tier at a time until it can hold ~46fps,
re-sampling after each step — unless you've picked a tier yourself, in which
case your choice always wins. Saves made before the tiers existed migrate:
the old realistic mode becomes CINEMATIC, the old fast mode stays FAST.

## Key art

`press/` holds promotional art rendered straight out of the game engine at
3200×1800, so the artwork and the game can never drift apart:

```
press/keyart-poster.png            16:9 key art — wordmark, hero, silhouetted opposition
press/ahmed-hero-kick.png          Ahmed mid-roundhouse on a dark plate
press/ahmed-guard.png              Ahmed in his fighting stance
press/boss-al-wahsh.png            the final boss
press/cast-lineup.png              the roster, front to back
press/screenshot-kuwait-towers.png in-game action shot
press/screenshot-souq.png          in-game action shot
```

These are renders, not hand-drawn assets — the game itself still ships with zero
image files. To re-render after changing the art code, drive the same drawing
functions with a scaled-up fighter and screenshot the canvas at a large viewport.
Set `f.sil = true` on a fighter to draw it as a featureless silhouette, which is
how the opposition in the key art is rendered.

## The control panel

`panel/index.html` — open it the same way you open the game. It loads the same
`assets/*.js` the game loads, so what it shows is what the game is running.

Editing the numbers by hand works. What it cannot show you is what a change
costs: raise the hook by two damage and you have moved the time to kill on ten
enemies, the XP rate of the whole campaign, and whether the training camp is
still affordable. The panel edits the tables and works out that second half
beside them.

| Tab | What it tells you that the file cannot |
| --- | --- |
| **Hits** | Damage per second over the whole window a move commits you for — startup, active and recovery — which is a different ranking from raw damage. Plus recovery as a share of the window: over about half, a whiff hands the other fighter a free hit. |
| **Enemies** | Threat: how much health an archetype takes off you before it goes down, one on one. That is damage output × survival time, and it is not the same order as HP. Also flags anything that would kill a level-1 Ahmed alone. |
| **Stages** | The difficulty ramp as enemy health per area, and a warning when it dips. A wave editor: trigger position, who arrives, and the fight it adds up to. |
| **World** | The graph drawn as the map screen draws it, and two checks — every link two-way with matching requirements, and every area reachable from a cold start. Routes are three dropdowns, and **changing one side updates the other**, so the asymmetry the audit looks for cannot be typed in by hand. |
| **Levels & XP** | The curve, and what one clean campaign actually pays out against what the level cap costs. |
| **Upgrades** | The bill: what maxing every track costs against what the campaign earns. If it comes to under 100%, spending is a decision; over, the training camp stops being a choice. |
| **Talents** | Where each one is found and what it opens — and a hard error if one is not the reward of any gate, because then it can never be picked up. |
| **Weapons** | Everything a weapon deals before it gives out, against the kick DPS you give up to carry it. |

Nothing is written to disk on its own. **EXPORT FILES** regenerates the tables
you have edited and hands you each file to download or copy; you save it into
`assets/` yourself. An untouched export round-trips byte-identical in content —
it is checked against the originals field by field, functions included — so
opening the panel and exporting without touching anything cannot lose you
content. The formatting is the panel's rather than byte-for-byte what you had.

## Files

```
index.html            the entire game (canvas engine, combat, art, audio, UI)
panel/index.html      the control panel — edit the tables, see what a change costs
assets/stages.js      what is inside each area: length, waves, gates, story
assets/world.js       the world graph — which area connects to which, and what each route wants
manifest.webmanifest  PWA metadata — installable, landscape, fullscreen
sw.js                 offline cache (bump CACHE when index.html changes)
icon.svg              app icon
```

## Tuning

The numbers worth touching live near the top of the script in `index.html`:

- `ATK` — damage, startup/active/recovery frames, reach, knockback and stamina cost
  of every strike.
- `TYPES` — enemy HP, power, speed, reach, attack rate, XP and colours.
- `STAGES` — stage length, theme, wave composition and where each wave triggers.
  A wave with `at: -1` spawns the moment the previous one clears (survival uses this).
- `DIFF` — the three difficulty multipliers.
- `buildProps` / `dropItem` — crate density, placement and drop odds.
- `genSurvivalWave` — how survival scales its enemy pool and wave size.
- `rankFor` — the S/A/B/C score thresholds.
- `ASSET_WORLD` (`assets/world.js`) — the world graph. `areas[i].w/e/d` are the
  west edge, east edge and door of area `i`; `needs` gates a route behind a
  talent, `afterCleared` behind a beaten area. Keep both halves of a link
  matched or the route will only work one way.
- `ABILITIES` / `GATES` — the ability table and what each kind of gate wants.
  A stage's `gates:[{at, type, reward}]` places one; `reward` is either
  `{ability:'…'}` or `{xp:n}`. `GATE_Z` is how far back they sit.
- `ACHIEVEMENTS` — each award's unlock predicate.
- `MUSIC_ROOT` — the tonal centre of the music loop per stage theme.
- `THEME[x].rig` — the stage's lights and post-chain dials. `RIG_DEFAULT` at the
  top of the render section documents every field; `BLOOM_T` is the bloom
  threshold, and the brightness/contrast pair is solved from it.
- `THEME` — per-stage parallax background painters.
- `LIGHT` — the key-light direction every gradient is derived from.
- `tube` / `litShape` / `ao` — the shading primitives: lit cylinder, lit volume,
  contact occlusion. `GFX_HIGH` swaps them all for flat fills.
- `postProcess` — colour grade and film grain.
- `samplePerf` — the automatic quality fallback and its fps threshold.
- `STRIKE_LIMB` — which limb leaves a motion trail for each attack.
- `UPS` / `upCost` — upgrade effects and pricing.

Enemy stats scale with the stage's `tier`, so raising a stage's tier makes every
enemy in it tougher without editing the enemy table.
