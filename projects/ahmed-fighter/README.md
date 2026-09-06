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
| Dodge dash | Tap `BLOCK` while moving (brief i-frames) | `L` while moving |
| Rage finisher | `RAGE` at 100% meter | `Space` |
| Pause | Pause button, top right | `Esc` / `P` |

**Stamina** (blue bar) pays for strikes and dashes and refills quickly.
**Rage** (purple bar) fills as you land and absorb hits; at 100% it unleashes a
spinning finisher that hits everyone around Ahmed.

Phones vibrate on impact — toggle it in the pause menu alongside sound.

---

## Loot

Crates and barrels line every stage and each one takes two hits. Smashing them
drops pickups you collect by walking over them:

- **Skewer (green)** — heals 28% of max health.
- **Rage orb (purple)** — adds 45% rage.

Beaten enemies drop loot too, about one in six. A downed boss always does.

---

## Stages

| # | Stage | الاسم |
| --- | --- | --- |
| 1 | Souq Mubarakiya | سوق المباركية |
| 2 | Salmiya Gym | نادي السالمية |
| 3 | Kuwait Towers | أبراج الكويت |
| 4 | Failaka Island | جزيرة فيلكا |
| 5 | Desert Camp | مخيم البر |
| 6 | Kuwait Arena — boss: **AL-WAHSH / الوحش** | بطولة الكويت |

Each stage scrolls through three locked waves. Clear a wave to move on, reach the
gold **EXIT** gate to finish the stage.

**AL-WAHSH fights in two phases.** Below half health he goes berserk — faster,
harder, and he gains the spinning finisher. He also shrugs off most knockdowns,
so you cannot stunlock him the way you can the smaller fighters.

**SURVIVAL** unlocks once you take the title. Endless waves that grow in size and
tier, a boss every sixth wave, and your furthest wave is recorded. It ends only
when Ahmed goes down.

## Difficulty

Set on the map screen; it applies immediately to every fight.

| | Enemy damage | Enemy health |
| --- | --- | --- |
| ROOKIE / مبتدئ | ×0.62 | ×0.78 |
| PRO / محترف | ×1.00 | ×1.00 |
| CHAMPION / بطل | ×1.45 | ×1.38 |

## Ranks

Clearing a campaign stage scores you **S / A / B / C** from kills, best combo,
health remaining and time taken, adjusted for difficulty. Your best rank per stage
shows on the map — chasing S is the reason to replay a stage you have already won.

## Progression

Kills and clear bonuses pay XP. Spend it in **TRAIN** on four tracks (5 levels each):
Power, Vitality, Speed, Stamina. Progress, XP, ranks, difficulty, the survival
record and settings are saved in `localStorage` under `ahmed_kuwait_fighter_v1` —
the game runs fine without storage (private mode), it just won't remember anything.

---

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
- `THEME` — per-stage parallax background painters.
- `UPS` / `upCost` — upgrade effects and pricing.

Enemy stats scale with the stage's `tier`, so raising a stage's tier makes every
enemy in it tougher without editing the enemy table.
