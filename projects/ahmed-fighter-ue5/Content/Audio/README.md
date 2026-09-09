# Content/Audio — what goes here

The game plays sound by **cue name** and `Content/Data/DT_Sounds.csv` maps each
cue to an asset in this folder. Nothing in C++ names a file. To give a cue a
sound: drop a `.wav` here with the file name below, import it (drag into the
Content Browser, same folder), and the row already points at it. To recast a
cue, change the row. To add a cue, add a row and fire it from code with
`UAhmedAudioSubsystem::Play(TEXT("Name"), this)`.

A cue whose file is not here yet **logs once and stays silent** — the game
never fails to start over a missing sound. `LogAhmedAudio` lists what is
missing the first time each cue fires, so play a stage and read the log.

Recording notes: 48 kHz, mono for anything spatial (everything under Combat,
Movement and World), stereo for UI and Music. Trim the head to the transient;
the game adds no pre-delay. Pitch drift is applied at play time, so record
one clean take rather than variations. Loop points on Music only.

The Description column in `DT_Sounds.csv` says what each one should sound
like — read it before recording or buying a replacement.

## What is here now

**All 39 effects are present and were generated with ElevenLabs**
(`eleven_text_to_sound_v2`), prompted from the Description column in the
tables below — which is why those descriptions were worth writing. Two takes
of each were rendered and the first is the one shipped; both live on the flow:

    https://elevenlabs.io/app/flows/Nh0sYMtTulfFbKLPvSrZ

They are a **first pass, and nobody has listened to them.** They were made and
processed in an environment with no audio output, so they are correct in
format and unheard in content. Play a stage before trusting any of them.

Each was converted to the spec above: levelled so the Volume column in
`DT_Sounds.csv` is the thing setting the level rather than whatever the model
happened to render, 48 kHz, mono where the cue is spatial and stereo where it
is not.

**Then they were cut to their timing (2026-09-09).** The first pass had
trimmed silence, not sound: most clips still carried the model's generation
length, so `S_Block` was 2.2 s with its thud at 1.78 s, `S_Whoosh_Light` was
0.6 s with the swish at 0.56 s under a jab whose startup is 0.07 s, and
`S_UI_Tap` ran a full second for a sound the table calls instant. Every clip
was measured with a 5 ms RMS envelope and cut from the original so that it is
as long as its sound: impacts start at their onset, one-shots end when the
event does, rewards and stings keep the tail the Description asks for, and a
swing's transient sits at a short, known lead. Fades are 2 ms in and 20 to
100 ms out. Nothing was re-levelled or resampled. The 39 effects went from
46.0 s to 24.3 s.

**The Lead column** is that lead, measured from the file after the cut: the
seconds from the start of the clip to its transient. The fighters read it.
`AFighterBase::StartAttack` no longer plays the swing; it schedules the cue
at `max(0, Startup - Lead)` and `TickAttack` starts the clip when the attack
crosses that time, so the swish peaks on the first active frame instead of on
the button press. A swing interrupted before then never sounds. The three
swing cues are cut so their lead fits inside the shortest startup they play
under -- `Whoosh_Light` 0.050 s under the 0.070 s jab, `Whoosh_Heavy` 0.100 s
under the 0.130 s knee, `Rage` 0.150 s under the 0.180 s finisher -- and
the Unity build's `AudioLibrary.Lead` reads the same number. **Re-measure
Lead whenever a clip is recast**; a wrong lead is a swing that sounds early
or late by exactly the error.

**To recast one**, open the flow, re-roll that node with a different prompt,
drop the new take in over the file, and set its Lead. Nothing in code names a
file, so nothing else has to change.

**Known suspect:**

- `S_Block.wav` and `S_Dash_Leap.wav` came back at 12 and 14 seconds against
  the one-shot everything else rendered as. That is the model looping rather
  than answering the prompt. The block is now the 0.38 s around its thud and
  the leap the first 0.8 s, which is a cut of the right sound, not a
  recording of it — they are still the two most likely to want re-rolling.
- `S_UI_Tap.wav` was quiet enough that the silence trim removed the entire
  file on the first pass. It is now 90 ms long. Check it is audible at all in
  the mix.
- `S_Whoosh_Light.wav` is 0.11 s: the only swish in the render was at the
  very end of the file and there is nothing after it, so the clip has no
  tail at all. It is right for a jab. Re-roll it if it reads as a click.
- ~~The three `Music_*` cues have **no file**.~~ Four of the five have one now; see the Music section. They are loops, not effects, and
  a text-to-sound model is the wrong tool for them.

## `Content/Audio/Combat/`

| File | Cue | What it is |
| --- | --- | --- |
| `S_Whoosh_Light.wav` | `Whoosh_Light` | Air moved by a jab or cross. Short, dry, no tail. The sound of missing. |
| `S_Whoosh_Heavy.wav` | `Whoosh_Heavy` | A hook, kick or knee cutting air. Lower and longer than the light one; the wind-up should be audible. |
| `S_Hit_Light.wav` | `Hit_Light` | Fist on body, jab or cross. A slap with weight behind it, not a movie punch. Dry. |
| `S_Hit_Heavy.wav` | `Hit_Heavy` | Hook, kick or knee landing. Deep, with a crack on top. This is the one the player waits for. |
| `S_Hit_Knockdown.wav` | `Hit_Knockdown` | The blow that puts someone down. Heavier than Hit_Heavy and followed by the body hitting the ground. |
| `S_Block.wav` | `Block` | A strike caught on the forearms. Dull thud, muffled, no crack. |
| `S_Parry.wav` | `Parry` | The perfect guard. Sharp and bright with a short ring -- it has to be unmistakable from Block, because it is the reward. |
| `S_Rage.wav` | `Rage` | The finisher going off. Big, low, room-filling; the one sound allowed to be cinematic. |
| `S_Hawk_Ignite.wav` | `Hawk_Ignite` | HAWK FIST lighting up: a whump of flame catching on a fist. |
| `S_Hawk_Hit.wav` | `Hawk_Hit` | A flaming punch landing. Hit_Heavy with a burst of fire over it. |
| `S_KO.wav` | `KO` | A fighter going down for good. Body on ground, then nothing. Not a crowd sound. |
| `S_Boss_Enrage.wav` | `Boss_Enrage` | A boss crossing into phase two. A roar, or a breath drawn -- it should make the player step back. |
| `S_Weapon_Pickup.wav` | `Weapon_Pickup` | A pipe, plank or crowbar picked up out of a smashed crate. |
| `S_Weapon_Swing.wav` | `Weapon_Swing` | An armed punch cutting air. Heavier than Whoosh_Heavy and with the object's own sound: pipe ring, plank whip. |
| `S_Weapon_Hit.wav` | `Weapon_Hit` | An armed punch landing. Steel or wood on body. |
| `S_Weapon_Break.wav` | `Weapon_Break` | The last use spent: the plank splitting, the pipe clanging away. |

## `Content/Audio/Movement/`

| File | Cue | What it is |
| --- | --- | --- |
| `S_Dash.wav` | `Dash` | A dodge dash. Feet scraping and a short rush of cloth. |
| `S_Dash_Leap.wav` | `Dash_Leap` | The dash once DASH LEAP is held: the same scrape, then a beat of nothing before the landing. |
| `S_Footstep.wav` | `Footstep` | One step on the stage floor. Fired from the walk animation's notify. Wide pitch range so a walk cycle never sounds looped. |
| `S_Land.wav` | `Land` | Feet hitting the ground after a leap or a knockback. |

## `Content/Audio/Music/`

Five cues, four files. Made 2026-09-10 (Riyadh) with ElevenLabs Music v2 on
the flow below, one render each, then cut to loops: a bar-aligned 60 s
window from the body of the render (past any intro), the tail crossfaded
into the head over 1.5 s so the seam is inaudible — measured: the jump
across the seam is at or below the mean sample-to-sample step on every
loop — and loudness-normalised so the Volume column sets the level.
48 kHz, stereo, 16-bit. **Nobody has listened to them**: they were made and
cut in an environment with no audio output, like the effects were. The
Unity build plays the same four files from `Assets/Resources/Audio/Music`.

    https://elevenlabs.io/app/flows/hNoQD2fFLdMb3eyOQZqK

| File | Cue | What it is |
| --- | --- | --- |
| `M_Stage.wav` | `Music_Stage` | The street. Darbuka and frame drum, sawtooth bass, oud stabs, D Hijaz at 100 BPM — the browser build's procedural loop, played by people. 25 bars. |
| `M_Under.wav` | `Music_Under` | The cellars. Sub-bass drone, a darbuka echoing in stone, sparse low oud, metallic hits. 88 BPM, 22 bars. |
| `M_Up.wav` | `Music_Up` | The roofs. Wind-like pads, oud and qanun ostinato, light frame drum, wide reverb. 104 BPM, 26 bars. |
| `M_Boss.wav` | `Music_Boss` | The title fights — ZAYOS, AL-SAQR, AL-WAHSH. Darbuka over taiko-scale drums, distorted bass, brass stabs. 118 BPM, 29 bars. |
| — | `Music_Menu` | Still no file. The Unity build has no menu; the row waits for the Unreal one. |

The renders were requested instrumental but the model's "instrumental"
setting was left on auto, so each full render was put through Scribe: all
four transcripts came back empty, so none of them carries a vocal line.
That is the one thing about them that is verified. To recast one, re-roll
that node on the flow and cut it again with the same windows (the cut was
four ffmpeg lines; `Tools/audio` has none of this yet).

## `Content/Audio/UI/`

| File | Cue | What it is |
| --- | --- | --- |
| `S_Stage_Clear.wav` | `Stage_Clear` | An area beaten. This one can be a fanfare. |
| `S_Stage_Fail.wav` | `Stage_Fail` | Ahmed down. Low and slow; no sting. |
| `S_Level_Up.wav` | `Level_Up` | A rank gained from fighting. Bright, short, upward. |
| `S_Upgrade_Bought.wav` | `Upgrade_Bought` | XP spent at the training camp. A confirm with weight; money changing hands. |
| `S_UI_Tap.wav` | `UI_Tap` | Any button. Quiet, dry, instant. |
| `S_UI_Back.wav` | `UI_Back` | Going back a screen. UI_Tap, lower. |
| `S_UI_Denied.wav` | `UI_Denied` | A button that will not: not enough XP, a locked mode. Short, flat, not rude. |

## `Content/Audio/World/`

| File | Cue | What it is |
| --- | --- | --- |
| `S_Gate_Strike.wav` | `Gate_Strike` | A strike landing on a shutter or a cracked wall that has not given yet. Metal or stone taking a hit and holding. |
| `S_Gate_Break.wav` | `Gate_Break` | The third strike: a shutter tearing off its rails, or masonry coming down. Debris after. |
| `S_Gate_Open.wav` | `Gate_Open` | A ledge climbed, a gap crossed, a locker opened -- the quiet gates. A latch, a scrape, a hand on stone. |
| `S_Talent_Found.wav` | `Talent_Found` | A talent picked up. The biggest UI sound in the game; the world just opened. |
| `S_Exp_Cache.wav` | `Exp_Cache` | XP found behind a gate. Smaller than Talent_Found; a reward, not a milestone. |
| `S_Exit_Travel.wav` | `Exit_Travel` | Walking out of an area into the next. A door, a step through, a breath of the new place. |
| `S_Exit_Sealed.wav` | `Exit_Sealed` | A route refusing you. Solid and final -- a bolt, a hand on a locked door. Pairs with the SEALED banner. |
| `S_Wave_Start.wav` | `Wave_Start` | An ambush closing in. Low, rising, short. The arena just locked. |
| `S_Wave_Clear.wav` | `Wave_Clear` | The last of a wave down and the arena unlocking. A release, not a fanfare. |
| `S_Crate_Break.wav` | `Crate_Break` | A crate or barrel giving way. Wood splintering, or a barrel's hollow clang. |
| `S_Pickup_Health.wav` | `Pickup_Health` | The skewer. Warm, quick. |
| `S_Pickup_Rage.wav` | `Pickup_Rage` | The rage orb. A charge taken in; a little electric. |
