# Tools/harness — running the port without Unity

This project has never been opened in Unity. The harness is how anything in it
gets checked anyway: a small `UnityEngine` that is enough to **run** the port's
logic under Mono, plus the suites that drive it.

```bash
Tools/harness/run.sh          # needs mono-mcs and mono-runtime; numpy is optional
```

It lives under `Tools/` and not `Assets/` deliberately. Inside `Assets/` Unity
would compile `UnityEngine.cs` and every type in it would collide with the real
engine's.

## What is here

| | |
| --- | --- |
| `UnityEngine.cs` | The engine surface the port uses. Transforms compose through their parents, colliders answer downward raycasts, and MonoBehaviours get Awake/Start/Update/LateUpdate driven by reflection in `DefaultExecutionOrder`, so the port's own private methods run. |
| `tests/World.cs` | District layout, world reachability, the spiral. |
| `tests/IK.cs` | The two-bone solver and the strike timeline, as pure maths. |
| `tests/Pose.cs` | `FighterIK` driven through a real skeleton in a real scene. |
| `tests/Hub.cs` | The save format, the upgrade economy, hub placement. |
| `tests/Algebra.cs` | The stub's quaternions against known rotations. |
| `xcheck/` | 4,000 random cases of the stub's algebra recomputed in numpy through rotation matrices — a different formulation — to catch a stub whose maths lies. |

## What it is not

It is **not Unity**, and every behaviour in it is an assertion about Unity that
a person wrote down. It has no renderer, no animation system, no real physics
solver and no real frame loop. Raycasts go straight down only, because every
ray the port casts goes straight down and a general solver would be pretence.
`CharacterController.Move` stands on what is under it and nothing more.

So a green run means the logic is consistent and the maths is sound. It does
not mean the game works. Pressing play in a real editor is still the check
nobody has done.

## When you touch it

- If the port needs an API the harness lacks, add it with the **real** Unity
  signature and real behaviour. A stub whose maths lies turns every test into a
  test of the stub — that has happened here twice, and both times a test passed
  over a live bug.
- A test that passes when the code does nothing is not a test. The feet on flat
  ground read the same planted or unplanted, which is why `Pose.cs` puts a step
  under one foot.
