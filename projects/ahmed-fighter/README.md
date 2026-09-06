# AHMED — Kuwait Fighter

A 2D mobile beat-'em-up. Ahmed is a young Kuwaiti fighter working his way from the
old souq to the national title, MMA / kickboxing style.

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

## Stages

Nine stages, each with its own backdrop, enemy mix and story beat. Tapping a
stage on the map opens a briefing first — the story so far, who is waiting, and
your best rank there.

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

## Who you fight

Every archetype is built to be recognised across the arena, before it swings.
Silhouette does the work — height, bulk and headwear read at a glance where a
colour swap does not, especially in a five-enemy wave.

| | Trait | Reads as |
| --- | --- | --- |
| Thug / بلطجي | Basic punches, barely guards. | smallest man on screen, grey vest |
| Brawler / مشاكس | Three-punch pressure. | stocky, bearded, sleeved tee |
| Runner / خطّاف | Very fast, low health, strikes and retreats. | slight, orange peaked cap |
| Kickboxer / ملاكم | Long range, kick-heavy. | gold headband, white shin wraps |
| Bouncer / حارس | Slow wall of a man, guards 62% of the time. | bald, sunglasses, black kit |
| Grappler / مصارع | Knees and hooks, hard to knock down. | bald, scarred, no shirt, huge |
| Enforcer / مُنفّذ | Fast technical combos. | sunglasses but hair, teal kit |
| Contender / منافس | Uses the full moveset. | fully dressed, purple and gold |
| **AL-SAQR / الصقر** | Mid-campaign boss. All legs, no patience. | navy headband, shin wraps |
| **AL-WAHSH / الوحش** | Final boss. Two phases. | biggest, bald, full beard |

The kit is a `look` object on each `TYPES` entry, applied in `makeEnemy`, and it
uses the same flags Ahmed does — plus `bald`, `cap`, `headband`, `shades`,
`shin` and `scar`. Adding an archetype means adding a look, not new drawing
code.

Each stage scrolls through three locked waves. Clear a wave to move on, reach the
gold **EXIT** gate to finish the stage.

**Both bosses fight in two phases.** Below half health they go berserk — faster,
harder, and they gain the spinning finisher. They also shrug off most knockdowns,
so you cannot stunlock them the way you can the smaller fighters.

**SURVIVAL** unlocks once you take the title. Endless waves that grow in size and
tier, a boss every sixth wave, and your furthest wave is recorded. It ends only
when Ahmed goes down.

## Abilities and sealed routes

Every campaign stage hides one route behind an ability. Nothing sealed ever
blocks the way forward — gates sit in the back wall, so a stage is always
completable — but finding an ability sends you back through stages you have
already cleared. The map marks it: a gold **!** on a stage means you now carry
the key to something still sealed there.

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

## Graphics

Everything is still drawn in code — there are no image files — but the fighters
are rendered as lit volumes rather than flat shapes:

- **One key light** from the upper left drives every gradient in the scene.
- **Limbs** are shaded as cylinders, tapering along their length, with a muscle
  belly on the upper bone and ambient occlusion at every joint.
- **Heads** are built from a skull path with a brow ridge, eye, nose, mouth, ear,
  cheekbone and jaw shading, hair drawn as a lit mass, and jaw stubble.
- **Gloves** have a thumb, seam, specular highlight and wrist cuff; **shoes** have
  a sole and laces; **cloth** has folds and a hem.
- **Post-processing**: a split-tone colour grade (cool sky, warm ground) and
  animated film grain.

## Stages

Each location is a `THEME` entry with five layers, drawn back to front:

| Hook | What it draws |
| --- | --- |
| `clouds` | a slow cloud band, config not code — every theme wants the same drift in a different colour |
| `far` | skyline, sea, dunes; barely parallaxed |
| `mid` | the layer that names the place — arches, heavy bags, dhows, tents |
| `floor` | the ground the fight happens on |
| `air` | whatever drifts through frame: dust, gulls, embers, confetti |

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

**GRAPHICS: REALISTIC / FAST** in Settings (or pause) switches the whole shading
pipeline for flat fills. Realistic costs roughly twice the draw calls, so the
game samples real frame times once per session during a fight and drops itself to
FAST if the device can't hold ~45fps — unless you've picked a mode yourself, in
which case your choice always wins.

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

## Files

```
index.html            the entire game (canvas engine, combat, art, audio, UI)
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
- `ABILITIES` / `GATES` — the ability table and what each kind of gate wants.
  A stage's `gates:[{at, type, reward}]` places one; `reward` is either
  `{ability:'…'}` or `{xp:n}`. `GATE_Z` is how far back they sit.
- `ACHIEVEMENTS` — each award's unlock predicate.
- `MUSIC_ROOT` — the tonal centre of the music loop per stage theme.
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
