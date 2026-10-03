# Content/Audio — what goes here

The game plays sound by **cue name** and `Content/Data/DT_Sounds.csv` maps each
cue to an asset in this folder. Nothing in C++ names a file. To give a cue a
sound: drop a `.wav` here with the file name below, import it (drag into the
Content Browser, same folder), and the row already points at it. To recast a
cue, change the row. To add a cue, add a row and fire it from code with
`USaudAudioSubsystem::Play(TEXT("Name"), this)`.

A cue whose file is not here yet **logs once and stays silent** — the game
never fails to start over a missing sound. `LogSaudAudio` lists what is
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
is not. **That levelling did not survive the cut below** -- see *Then they
were mastered*.

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

**Then they were mastered (2026-09-17).** The cut above says "nothing was
re-levelled", and that is exactly what went wrong with it: the first pass
levelled the *renders*, then the cut took a window out of each render and
kept whatever level that window happened to have. So the level of a clip
became the level of the part of the render that survived, and by the time
anyone measured, peaks ran from 0.002 to 0.85 -- a factor of four hundred,
with the Volume column sitting on top of it and multiplying the mess.

Six cues were effectively silent: `UI_Tap` peaked at 0.002, which is -54
dBFS, times a Volume of 0.60. `Weapon_Hit`, `Dash_Leap`, `Land`,
`Exit_Travel` and `UI_Denied` were the others. A KO -- the loudest moment a
fight has -- peaked 14 dB *under* a footstep.

`Tools/audio/master.py` fixes what can be measured, and only that:

- **DC offset off each channel.** `S_Whoosh_Light` sat 0.0106 off centre and
  `S_Hit_Light` 0.0081. That is headroom spent on nothing and a click on the
  first sample. Per channel, not one figure for both -- taking a stereo
  clip's overall mean off both sides leaves each side off centre.
- **Peak to -1 dBFS, up as readily as down.** Not 0: a full-scale sample can
  still overshoot once an engine resamples or encodes it, and a fight plays
  a lot of these at once. The *file* now carries the headroom and the
  *table* carries the mix, so a cue's loudness is the Volume column and
  nothing else. Lifts ran from +0.4 dB to +51 dB.
- **2 ms in, 8 ms out, on edges that are not silent.** Only where the edge is
  hot, so a hit whose crack is its first frame is not softened for nothing.
  `S_Wave_Start` ended on a sample at 0.029, which is a click on every play.

The levels are the whole of it. **Gain is not free**: `UI_Tap` came up 51 dB
and everything underneath it came up 51 dB too. Nobody has heard the result,
so if a quiet cue now hisses, that is the clip to re-roll rather than
re-level.

**Lead was not touched, and the first version of that tool was wrong to think
it should be.** It measured the transient as the first sample reaching a tenth
of the peak, decided twenty-six of forty rows were wrong by up to 489 ms, and
would have written `Whoosh_Heavy` down to 0.001 s -- landing every heavy
swing's swish 99 ms *after* the punch. A tenth of the peak finds where a
whoosh starts winding up; this column holds where the sound lands. Measured
the way the cut measured it, off a 5 ms RMS envelope, the committed values are
right to within 2-3 ms nearly everywhere, and the four cues the game actually
schedules off Lead -- `Whoosh_Light`, `Whoosh_Heavy`, `Weapon_Swing`, `Rage`
-- agree to within 1 ms after mastering. Mastering cannot move them anyway:
gain is uniform, so where a clip peaks is where it peaked.

The tool prints the five rows that do disagree by more than 10 ms rather than
changing them, because they are judgement rather than error -- `Hit_Knockdown`
(0.056 against 0.102) and `Dash` (0.074 against 0.030) are cues with two bangs
in them, and which one is "the" transient is a decision, not a measurement.
None of the five is a swing cue, so none of them changes when a sound plays.

Run it from the Unreal project root:

    python3 Tools/audio/master.py            # master both ports in place
    python3 Tools/audio/master.py --check    # measure what is on disk; fails if unmastered

It is idempotent -- a second pass writes byte-identical files -- it mirrors
every clip into the Unity port's `Assets/Resources/Audio` so the two builds
cannot disagree about what a punch sounds like, and it does not write
`DT_Sounds.csv`. An earlier version did, and threw partway through on a row
whose description was written with commas and without quotes, truncating the
table and taking the four music rows with it. The music is not touched
either: those loops were cut to measured seams and levelled against each
other, and peak-normalising a loop is the wrong operation on one.

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
  file on the first pass. It is now 90 ms long. It was also the quietest clip
  in the game by a distance -- 0.002 peak, -54 dBFS -- which is measured, not
  a guess, and mastering has since brought it up 51 dB. Whether it is *right*
  at 90 ms is still unheard.
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

Five cues, five files. Four made 2026-09-10 (Riyadh) with ElevenLabs Music
v2 on the flow below, one render each, then cut to loops: a bar-aligned 60 s
window from the body of the render (past any intro), the tail crossfaded
into the head over 1.5 s so the seam is inaudible — measured: the jump
across the seam is at or below the mean sample-to-sample step on every
loop — and loudness-normalised so the Volume column sets the level.
48 kHz, stereo, 16-bit. **Nobody has listened to them**: they were made and
cut in an environment with no audio output, like the effects were. The
Unity build (frozen) plays the 2026-09-10 files from
`Assets/Resources/Audio/Music`; it does not get the 2026-09-28 stage loop.

**2026-09-28 (Riyadh): the main theme, and the stage loop recast in its
rhythm.** Asked as "create main game theme like same rhythm" with a link to
a track on YouTube that cannot be fetched or heard from here, and settled
with the author as: epic drums / orchestral, and both cues — a title theme
for `Music_Menu`, which had no file, and `Music_Stage` made again in the
same rhythm. Both are one render each on the same flow (nodes
`3FMuoNHVe0pjxg61oE38` the theme, `dHp9JzL5gHvJpicapZa4` the loop), cut and
checked by `Tools/audio/loop_cut.py`, which is the tool this section used
to say did not exist. "Same rhythm" is by the author's description of the
reference, not by anything heard: the prompt asked for a taiko-scale
pattern — a heavy hit on 1 and 3, a doubled snap on the "and" of 2 and on
4, sixteenth toms under it — at 120 BPM in D Hijaz, and the loop cutter
measured both renders at exactly 120 BPM.

    https://elevenlabs.io/app/flows/hNoQD2fFLdMb3eyOQZqK

| File | Cue | What it is |
| --- | --- | --- |
| `M_Stage.wav` | `Music_Stage` | The street, recast 2026-09-28. Taiko-scale drums on the theme's pattern with darbuka accents, a distorted bass pulse on the kick, low-brass stabs, an oud riff over a choir pad, staccato strings on the offbeats. D Hijaz at 120 BPM, 28 bars (56.0 s), the window opened at 17.49 s of a 90 s render where the seam matched best (onsets r 0.86), tail into head over 1.5 s. Until this it was the 2026-09-10 loop: darbuka and frame drum, sawtooth bass, oud stabs at 100 BPM, 25 bars — the browser build's procedural loop, played by people. |
| `M_Under.wav` | `Music_Under` | The cellars. Sub-bass drone, a darbuka echoing in stone, sparse low oud, metallic hits. 88 BPM, 22 bars. |
| `M_Up.wav` | `Music_Up` | The roofs. Wind-like pads, oud and qanun ostinato, light frame drum, wide reverb. 104 BPM, 26 bars. |
| `M_Boss.wav` | `Music_Boss` | The title fights — ZAYOS, AL-SAQR, AL-WAHSH. Darbuka over taiko-scale drums, distorted bass, brass stabs. 118 BPM, 29 bars. |
| `M_Menu.wav` | `Music_Menu` | The title screen, made 2026-09-28. A whole piece, not a loop: eight quiet bars of a low string drone, a solo oud on the theme and a distant frame drum; then the full taiko-scale drums, the theme on low brass and unison strings over a choir pad, to a brass-and-drums climax and a hard cymbal-and-taiko ending. 84.2 s (1.70–85.95 s of a 90 s render, trimmed to where it rises out of and sinks back into silence, 20 ms ramps, no crossfade), so it plays through and its intro follows after the quiet the model left at the end. Mastered 2026-09-30 by `Tools/audio/master_music.py` (below): -15.7 LUFS, -1.7 dBTP, the seam at -46 / -31 dBFS. The pre-master cut is the file this row shipped as on 2026-09-28 (git `32fab19`). |

The renders were requested instrumental but the model's "instrumental"
setting was left on auto, so each full render was put through Scribe: all
six transcripts came back empty, so none of them carries a vocal line.
That is the one thing about them that is verified. To recast one, re-roll
that node on the flow and cut it again:

    python3 Tools/audio/loop_cut.py RENDER Content/Audio/Music/M_X.wav --bpm 120 --bars 28 --lufs -15.7
    python3 Tools/audio/loop_cut.py RENDER Content/Audio/Music/M_Menu.wav --whole --lufs -15.7
    python3 Tools/audio/loop_cut.py --bite

`loop_cut.py` (2026-09-28) is the 2026-09-10 cut written down and measured:
it finds the body of the render, opens the window in the four bars after
it where the two bars at the start best match the two bars past the end
(spectral-flux onsets), crossfades the tail into the head, normalises the
loudness, and refuses the file unless the window is bar-aligned (r ≥ 0.5),
the seam step is at or under the loop's mean step, the loudness is within
0.5 LU and the true peak under -1 dBTP, and no half second is under
-40 dBFS. `--whole` is the title theme's cut: trimmed to silence at both
ends, and the seam must lie in a fade. `--bite` breaks each rule on a
render the script makes itself and every check fails as it should (8 of
8). The 2026-09-10 loops were cut before it and were not re-cut with it.

**2026-09-30 (Riyadh): the theme, mastered.** Asked as "improve theme song quality and improve low and mid and high level sound", with nothing here able to hear it, so the work is against a written curve and every claim is a number. The cut (`loop_cut.py --whole`, identical to the file shipped 2026-09-28) was measured first: 1/3-octave band power of the mono sum relative to its 250 Hz-2 kHz mean, 65536-pt Welch PSD. Against the target it read 80 Hz +6.6 dB and 125 Hz +4.6 (the boom: the D2 tonic, 73.4 Hz, piles into the 80 Hz band), 5-16 kHz 3.8-7.5 dB under (the dull top; the render exists only as a 192 kbps MP3 with its lowpass near 16 kHz), everything 160 Hz-4 kHz already inside tolerance, a 100 Hz-10 kHz slope of -19.7 dB/decade against `M_Boss`'s -16.2, and a -20 dB bandwidth point of 12.5 kHz. Three chains were built and refuted against the same script on 2026-09-28/30 and one won: high-pass 28 Hz, bells at 76 and 128 Hz (-6, -4 dB) with the 100 Hz dip between them filled (+2.5), a presence lift at 3.5 kHz (+1.5), a shelf from 6 kHz (+4.5) and a bell at 12.5 kHz (+3, under the MP3's cutoff), three-band compression at 150 Hz / 2.5 kHz (ratios 1.5 / 1.6 / 1.3, the lows held at most 2.1 dB at the climax), the side of the top band x1.1, a limiter at -2 dBFS and the level back to -15.7 LUFS with the 20 ms ramps put back. Four ffmpeg passes, all IIR, deterministic (the same input gives the same file, md5 `ec1bd4b7…`).

What moved, in the share of the 20-20k total (dB, cut -> master): 20-60 -9.3 -> -8.9, 60-120 -2.7 -> -4.1, 120-250 -7.2 -> -7.0, 250-500 -12.6 -> -10.4, 500-1k -13.2 -> -10.9, 1-2k -15.2 -> -12.7, 2-4k -18.3 -> -14.1, 4-8k -24.2 -> -18.6, 8-12k -31.5 -> -23.5, 12-16k -40.3 -> -30.9, 16-20k -55.0 -> -47.3. The curve's RMS deviation from the target fell 3.23 -> 0.98 dB with 7 -> 0 bands out (worst now 80 Hz +2.2 of 3); the slope is -16.5 dB/decade and the -20 dB bandwidth point 16 kHz. Loudness -15.7 LUFS as before; true peak -3.1 -> -1.7 dBTP, peak-to-loudness 12.6 -> 14.0 dB, loudness range 7.2 -> 8.9 LU, crest factors 15.0 / 18.3 / 25.7 dB in the three bands against 15.1 / 19.1 / 25.5; the compressor's largest gain swing inside any second is 2.36 dB; pre-echo -1.9 -> -1.8 dB (there is no linear-phase stage). Stereo: correlation above 2.5 kHz -0.02 -> -0.09, the mono sum untouched by construction, mono-sum loss -1.3 -> -2.0 LU. The intro's quietest 4 s went 1.9 dB quieter, the tonic's 80 Hz band 4.4 dB down, the seam still at -46 / -31 dBFS with 2.0 s under -40 dBFS at it and none elsewhere.

The target: a bass plateau +5..+8 dB from 50 to 125 Hz peaking at 63-80 Hz, mids within +1.5/-2 of their mean, -1 dB per 1/3-octave above 2 kHz to 10 kHz, steeper above; tolerances +-3 dB in the bass, +-2.5 through the mids and top, +-4 at 12.5 kHz, +-6 at 16 kHz. It is a model on two published slopes -- Pestana et al., AES 8960 (2013), about -5 dB/oct density 100 Hz-4 kHz in commercial music; ProSoundWeb's classical-vs-rock long-term spectra, about -6 dB/oct above 1 kHz -- both reached as search snippets only (the hosts are egress-blocked from here), and on the game's own family: `M_Boss` sits inside it at every scored band, `M_Stage` is 2.5-3 dB dull against it at 5-10 kHz. It is not a transcription of a published orchestral spectrum.

    python3 Tools/audio/master_music.py CUT.wav Content/Audio/Music/M_Menu.wav      # master, measure, refuse on any failed rule
    python3 Tools/audio/master_music.py --check Content/Audio/Music/M_Menu.wav
    python3 Tools/audio/master_music.py --bite

`master_music.py` (2026-09-30) is that chain with every constant named, and it refuses the file unless sixteen rules hold: the level within 0.5 LU, true peak under -1 dBTP measured twice (ebur128 and its own 4x oversampling), no full-scale or flat-top runs, `loop_cut.check_whole`, the end ramps, every scored band inside tolerance, no band moved over 8 dB, pumping under 1.4x the source's and the gain swing against its own EQ stage under 3 dB in any second, pre-echo within 2 dB of the source's, mono-sum loss within 1 LU, the intro's quietest half second lifted under 6 dB, peak-to-loudness within 2 dB, the end silence intact. `--bite` breaks each on a mix the script makes itself and every check fails as it should (10 of 10). **Nobody has listened to the result**; what is better is what those numbers say. The MP3's 16 kHz cutoff cannot be undone and nothing above it is invented; the 6 kHz shelf lifts the MP3's own 4-16 kHz coding artefacts by the same 4-8 dB as the music, and no probe here can see that.

**2026-10-03 (Riyadh): every loop on one target, and a theme for each boss -- half done.** Asked as "improve music quality", settled as all of: the stage loop mastered, the title theme again, every music file on one target, and new renders; with the bosses' "a new theme for each" (2026-10-02). Fourteen renders were started on the flow above (ElevenLabs Music v2.5, 90 s, instrumental, two takes each of the stage, cellar, rooftop and boss loops and of a theme for AL-WAHSH, AL-SAQR and ZAYOS) and **every one failed: the account had insufficient funds.** Nothing was charged and nothing was retried; the nodes are on the flow with their prompts, ready to run when there is credit.

What could be done without new audio was. `master_music.py` gained three modes: `--fit` fits stage 1 to the file's own curve (a pre-gain to the target loudness, then a third-octave bell on every scored band up to 12.5 kHz more than 0.75 dB off the target, 0.8 of the deviation, three passes, each bell held to -8/+6 dB); `--loop BPM BARS` masters a raw render whole and then cuts it with `loop_cut.make`, for the renders to come; `--loop-file` masters a loop already cut: tiled three times, run through the chain, the middle copy kept and moved by the chain's own latency (measured, 237-388 samples) so the seam lands where it was, the limiter's ceiling at most 1 dB over the source's peak-to-loudness, and held to the seam, the level, the peaks and every rule but a whole piece's ends.

| File | Before -> after (curve RMS against the target, dB) | Shipped |
| --- | --- | --- |
| `M_Stage.wav` | 2.06 -> 0.59; eight bands out -> none; slope -18.9 -> -16.6 dB/decade; PLR 11.7 -> 12.8; seam step 0.0021 against a mean step of 0.0109 | yes |
| `M_Boss.wav` | 1.17 -> 0.41; -20 dB bandwidth 12.5 -> 16 kHz; PLR 11.5 -> 12.5 | yes |
| `M_Under.wav`, `M_Up.wav` | refused by the tool (the fit fought the target: the cellar is dark and the roofs airy by design, and the target is the fight's) | no -- and nothing in the Unreal game plays them (the floors they were for are the frozen Unity port's) |
| `M_Menu.wav` | the fitted pass measured 1.29 against the shipped master's 0.98, and its top end 12.5 kHz against 16 | no -- the 2026-09-30 master stays |

The first `--loop-file` run on the stage loop failed its seam (0.0135 against 0.0109): the chain delays the audio, and the copy was cut a few hundred samples late. The latency compensation is what fixed it. `--bite` still catches 10 of 10.

**The boss themes are wired, not heard.** `SaudFeel::BossTheme` names `Music_Wahsh`, `Music_Saqr` and `Music_Zayos`; `AWaveDirector::BeginWave` starts a boss's theme with his wave, or `Music_Boss` while his theme has no row in `DT_Sounds.csv`, and the stage loop comes back when the wave is cleared. Nothing started `Music_Boss` before. The three rows are added with their files, never before: a row with no file would stop the music at the boss.

## `Content/Audio/UI/`

| File | Cue | What it is |
| --- | --- | --- |
| `S_Stage_Clear.wav` | `Stage_Clear` | An area beaten. This one can be a fanfare. |
| `S_Stage_Fail.wav` | `Stage_Fail` | Saud down. Low and slow; no sting. |
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
