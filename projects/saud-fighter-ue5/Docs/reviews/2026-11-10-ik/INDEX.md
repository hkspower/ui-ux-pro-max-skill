# The IK, reviewed -- 2026-11-10 (Riyadh)

Asked as "full improve ik", settled as: all of it, both builds -- three items
already on the list (Unreal: a shoved guard takes recovery steps; Unity: the
head looks at the opponent; Unity: the block meets the blow) and a full review
of the IK in both builds, every fault the harness can measure to be fixed and
tested.

This folder is the review. Six reviewers each took one part of the IK (the
Unreal feet, arms, turns and look, and engine side; the Unity IK; and what the
Unreal IK does that the Unity one does not), measured with small programs built
on the real sources, and reported at most four findings each. Every finding of
medium or high severity then went to a second reviewer whose job was to refute
it with a program of their own. One file per finding: the scenario, the
finder's numbers and fix sketch, then the second reviewer's own numbers,
reasoning and fix advice (several tried their fix on a scratch copy and say
what it measured).

24 findings: 19 confirmed, 1 reproduced but found to be a recorded decision
(F20, the shoved guard -- the item the owner has now asked to change), 4 of low
severity not sent to a second reviewer.

`<scratch>` in these files is the review machine's scratch folder: the probe
programs named there were not kept. Line numbers are those of commit 64c86db.
Nothing here was run in an engine: the Unreal findings are measured on the
engine-free headers through the g++ harness (or read, where a finding says
so), the Unity ones on the port's sources under Mono.

Whether each has been fixed since is recorded in the project's CLAUDE.md
("The IK, reviewed"), not here.

| | build | severity | finding | review |
| --- | --- | --- | --- | --- |
| [F01](F01.md) | Unreal | high | The leg's pole is the clip's own knee: Saud's walk bends its knee backwards up a slope or onto a kerb, and a street man's lead knee bows sideways on a kerb | confirmed by a second reviewer |
| [F02](F02.md) | Unreal | medium | The guard's shuffle never runs in the game: the feet are told a state nothing ever sets | confirmed by a second reviewer |
| [F03](F03.md) | Unreal | high | A big man's punch gets no pull toward a smaller man inside his reach: the arm's gate reads the size difference as a swipe | confirmed by a second reviewer |
| [F04](F04.md) | Unreal | medium | A straight punch at a close man folds with the elbow whipped up over the fist | confirmed by a second reviewer |
| [F05](F05.md) | Unreal | medium | A body blow's cover swings the elbow sideways away from the blow, not down onto it | confirmed by a second reviewer |
| [F06](F06.md) | Unreal | high | A half-turn clip (Turn_180, Pivot_180) spins the drawn body the long way round through its 0.06 s cut when the stick is on the side away from the clip's way round | confirmed by a second reviewer |
| [F07](F07.md) | Unreal | medium | The face turns over the far shoulder, away from a man swinging on the flank: HoldSide's held side is whoever was last within the limit, not the man now looked at | confirmed by a second reviewer |
| [F08](F08.md) | Unreal | medium | Under any turn clip the chest and the face are swung back AGAINST the turn: the chain's memory is kept off the facing while the lag it was measured against is handed to the clip | confirmed by a second reviewer |
| [F09](F09.md) | Unreal | medium | A quarter turn on the spot at any stick angle but 90: the body is jerked to the clip's 90 through the 0.06 s cut, the wrong way first when the stick is under 90 | confirmed by a second reviewer |
| [F10](F10.md) | Unreal | high | A guard edged along still skates: UpdateFeet passes `St == EFighterState::Block`, a state nothing ever sets | confirmed by a second reviewer |
| [F11](F11.md) | Unreal | medium | The posture stage leaves both clavicles behind: reading the upper arms converts them, and TurnBones never sets them | confirmed by a second reviewer |
| [F12](F12.md) | Unreal | medium | The eight street men get no posture at all: their stance is looked up by their DT_Fighters row, which has none | confirmed by a second reviewer |
| [F13](F13.md) | Unity | high | A held foot is not on the floor and does not stay put: the legs rest straight, so any foot HoldFoot holds away from under the hip is out of reach, and the hips only drop for ground height | confirmed by a second reviewer |
| [F14](F14.md) | Unity | medium | A strike takes its limb in one frame: the fist leaves a raised guard for the A-pose rest point before it goes forward, a strike that is cut short drops back at once, and a kick's foot jumps to its rest point on the kick's first frame | confirmed by a second reviewer |
| [F15](F15.md) | Unity | medium | Nothing in the pose grows with the man: the size FighterIK reads is the root's scale, which is always 1 (SetStature scales the Mesh child), and the guard, the ankle height and the step are fixed metres -- the bosses guard at their belly, ZAYOS at his hips | confirmed by a second reviewer |
| [F16](F16.md) | Unity | high | Unity: nothing eases between the pose's drivers -- a guard dropped into a punch, a kick out of a walk and a swing taken away by a blow each move a limb 37-125 cm in ONE frame | confirmed by a second reviewer |
| [F17](F17.md) | Unity | high | Unity: a strike has no tip and no mark -- the Knee row drives the ANKLE on a locked-straight leg through the man, and every blow goes down the facing line while the man it lands on stands 22-34 degrees off it | confirmed by a second reviewer |
| [F18](F18.md) | Unity | medium | Unity: a turn is one frame for the whole body and is never finished by the feet -- 45-180 degrees in a frame, legs crossed 0.12 s after a half turn, feet left 6.7-12.2 cm off their places for as long as he stands | confirmed by a second reviewer |
| [F19](F19.md) | Unity | medium | Unity: every length in the pose is Ahmed's, whatever the man's size -- the guard stands 1.50 m up on all of them, 82.5 cm under ZAYOS's chin, and the hold's size is read off a root that is never scaled | confirmed by a second reviewer |
| [F20](F20.md) | Unreal | medium | A blocked blow's push slides both feet the whole way and they never step (the known complaint, reproduced) | reproduced, but a recorded decision (the owner has since asked for the change) |
| [F21](F21.md) | Unreal | low | Standing still on flat ground the heel-roll rule fires on three guards' own lead legs | low severity, not checked by a second reviewer |
| [F22](F22.md) | Unreal | low | The guard ignores a second man's blow until the first man's whole swing is over | low severity, not checked by a second reviewer |
| [F23](F23.md) | Unreal | low | A man coming back on screen is traced under where his feet were last drawn, not under him | low severity, not checked by a second reviewer |
| [F24](F24.md) | Unity | low | Put somewhere new while a foot is mid-step, that leg is flung flat toward where he came from: SnapDrift only re-plants a foot that is Held, a step keeps its old From | low severity, not checked by a second reviewer |
