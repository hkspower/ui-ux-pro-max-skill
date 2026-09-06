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

| File | Cue | What it is |
| --- | --- | --- |
| `M_Stage.wav` | `Music_Stage` | The fight loop. One track per theme is the intent; start with one and cast per stage later. |
| `M_Menu.wav` | `Music_Menu` | The title screen. Slower than the fight loop, same key. |
| `M_Boss.wav` | `Music_Boss` | The two title fights. The stage loop with the floor taken out. |

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
