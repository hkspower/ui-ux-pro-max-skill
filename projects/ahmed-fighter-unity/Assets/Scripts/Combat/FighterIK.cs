using UnityEngine;
using Ahmed.Data;

namespace Ahmed.Combat
{
    /// <summary>
    /// The pose, computed. There is no animation in this port: the mesh
    /// stood in its A-pose while the fighter walked, turned and struck. This
    /// keeps the feet on the ground under him and throws the strikes -- the
    /// limb the attack row names goes to the row's reach over the row's
    /// startup, holds through its active frames and comes back over its
    /// recovery -- so a new move needs no animation, only its limb and the
    /// height it lands at.
    ///
    /// Conventions. The model faces +Z, is Y-up, in metres, and stands on
    /// y = 0 of the fighter's root, which carries the CharacterController and
    /// the Fighter. Fighter.Facing is the unit vector the root looks along in
    /// the ground plane. Bones are found by the generator's names. Every
    /// frame starts by putting the eight chain bones back to their rest
    /// rotation, because nothing else does: without that, each frame's solve
    /// would stack on the last.
    ///
    /// Runs after Fighter's LateUpdate, which is where the root moves and
    /// turns; the execution order below is what guarantees that, since Unity
    /// makes no promise between scripts otherwise.
    /// </summary>
    [DefaultExecutionOrder(100)]
    public class FighterIK : MonoBehaviour
    {
        /// <summary>Ankle height above the sole, from the joint table.</summary>
        public const float AnkleHeight = 0.070f;
        /// <summary>Shoulder and hip heights, from the joint table.</summary>
        public const float ShoulderHeight = 1.442f;
        public const float HipHeight = 0.952f;
        /// <summary>How far above the ankle's rest position the foot ray starts.</summary>
        private const float RayStart = 0.6f;
        /// <summary>Where a raised guard puts the hands, in the fighter's own
        /// frame: up at the chin, forward a little, one either side of it.</summary>
        public const float GuardHeight = 1.50f;
        public const float GuardForward = 0.26f;
        public const float GuardSpread = 0.11f;
        /// <summary>Guard weight per second. A guard goes up fast or it is not
        /// a guard, but not in one frame or it reads as a glitch.</summary>
        private const float GuardBlend = 9f;

        /// <summary>Shared, because LateUpdate is one at a time and the hits
        /// are consumed before the next fighter runs. Eight is more than a
        /// metre of floor under one foot can plausibly hold.</summary>
        private static readonly RaycastHit[] Hits = new RaycastHit[8];

        private struct Limb
        {
            public Transform Root, Mid, End;
            public Quaternion RootRest, MidRest;
            /// <summary>The end's rest position in the fighter's frame.</summary>
            public Vector3 EndRestLocal;
            /// <summary>Root to end at rest, and how far the root stands over the
            /// end: what the hips' drop needs to know of a leg (ReachDrop).</summary>
            public float Span, Stand;
            public bool Ok;
        }

        private Fighter _fighter;
        private Limb _legL, _legR, _armL, _armR;
        private float _guard;
        private bool _southpaw;
        private string _stanceFrom;

        /// <summary>This frame's rays and targets, for the debug view (IKDebug).</summary>
        private IKDebug.View _view;
        private readonly System.Collections.Generic.List<IKDebug.Prim> _prims = new System.Collections.Generic.List<IKDebug.Prim>();

        /// <summary>The skeleton's parent and where it rests under the root: the
        /// hips' drop lowers it, and every frame starts from its rest.</summary>
        private Transform _mesh;
        private Vector3 _meshRest;
        private float _hipDrop;
        private bool _hipKnown;

        /// <summary>The man's size against Ahmed's, measured off his own
        /// skeleton each frame (SizeOf).</summary>
        private float _size = 1f;

        /// <summary>
        /// A man's size against Ahmed's: how high his hip joints stand over
        /// his root, against Ahmed's HipHeight (2026-11-10, the IK reviewed:
        /// "nothing in the pose grows with the man"). The size was read off
        /// the root's scale, and the root is never scaled -- SetStature scales
        /// the Mesh child and the controller -- so it was 1 for every man:
        /// the bosses raised their guard to their belly, ZAYOS to his hips
        /// (1.50 m up on a man whose chin is at 2.3), and a giant's feet were
        /// held by Ahmed's 12 cm. Taken from the bones, not from a scale:
        /// it holds whatever the imported model's own scale is, and whenever
        /// SetStature runs. A leg that did not bind does not count; with none,
        /// or a height that is not a height, the size is Ahmed's. Pure.
        /// </summary>
        public static float SizeOf(float hipL, bool okL, float hipR, bool okR)
        {
            float sum = 0f; int n = 0;
            if (okL) { sum += hipL; n++; }
            if (okR) { sum += hipR; n++; }
            if (n == 0) { return 1f; }
            float size = sum / n / HipHeight;
            return size > 0.01f && size < 100f ? size : 1f;
        }

        private void Start()
        {
            _fighter = GetComponent<Fighter>();
            Transform mesh = transform.Find("Mesh");
            if (_fighter == null || mesh == null)
            {
                Debug.LogWarning("[Ahmed] FighterIK needs a Fighter and a Mesh child; disabling.");
                enabled = false;
                return;
            }
            _mesh = mesh;
            _meshRest = mesh.localPosition;
            _legL = Bind(mesh, "thigh_l", "calf_l", "foot_l");
            _legR = Bind(mesh, "thigh_r", "calf_r", "foot_r");
            _armL = Bind(mesh, "upperarm_l", "lowerarm_l", "hand_l");
            _armR = Bind(mesh, "upperarm_r", "lowerarm_r", "hand_r");
        }

        private Limb Bind(Transform mesh, string root, string mid, string end)
        {
            Limb limb = new Limb();
            limb.Root = FindDeep(mesh, root);
            limb.Mid = FindDeep(mesh, mid);
            limb.End = FindDeep(mesh, end);
            limb.Ok = limb.Root != null && limb.Mid != null && limb.End != null;
            if (!limb.Ok)
            {
                // One limb missing disables that limb and nothing else. The
                // mesh must never be the thing that stops a build running.
                Debug.LogWarning("[Ahmed] FighterIK: no bones " + root + "/" + mid + "/" + end
                    + " under " + mesh.name + "; that limb stays as it is.");
                return limb;
            }
            limb.RootRest = limb.Root.localRotation;
            limb.MidRest = limb.Mid.localRotation;
            limb.EndRestLocal = transform.InverseTransformPoint(limb.End.position);
            limb.Span = (limb.End.position - limb.Root.position).magnitude;
            limb.Stand = limb.Root.position.y - limb.End.position.y;
            return limb;
        }

        /// <summary>Transform.Find is one level deep; a skeleton is not.</summary>
        private static Transform FindDeep(Transform t, string name)
        {
            for (int i = 0; i < t.childCount; i++)
            {
                Transform c = t.GetChild(i);
                if (c.name == name) { return c; }
                Transform deeper = FindDeep(c, name);
                if (deeper != null) { return deeper; }
            }
            return null;
        }

        private void LateUpdate()
        {
            Reset(ref _legL); Reset(ref _legR); Reset(ref _armL); Reset(ref _armR);
            RefreshStance();
            _view = new IKDebug.View();

            bool strikeRight;
            bool strikeLeg = StrikingLeg(out strikeRight);
            bool strikeL = strikeLeg && !strikeRight, strikeR = strikeLeg && strikeRight;
            // The ground under each foot first; then the hips come down to
            // the lower one; then the legs are solved from where the hips are.
            _mesh.localPosition = _meshRest;
            // his size, off his own hips while they are at rest (SizeOf)
            _size = SizeOf(_legL.Ok ? transform.InverseTransformPoint(_legL.Root.position).y : 0f, _legL.Ok,
                           _legR.Ok ? transform.InverseTransformPoint(_legR.Root.position).y : 0f, _legR.Ok);
            Vector3 targetL, targetR;
            // (each foot is told how far the other has been carried, for the settle)
            float driftL = _holdL.Held ? Flat(_holdL.Anchor, transform.TransformPoint(_legL.EndRestLocal)) : 0f;
            float driftR = _holdR.Held ? Flat(_holdR.Anchor, transform.TransformPoint(_legR.EndRestLocal)) : 0f;
            bool maySettle = _fighter.State != FighterState.Attack;
            bool onL = FindFoot(ref _legL, ref _holdL, _holdR.Stepping, strikeL, maySettle, driftR, ref _view.FootL, out targetL);
            bool onR = FindFoot(ref _legR, ref _holdR, _holdL.Stepping, strikeR, maySettle, driftL, ref _view.FootR, out targetR);
            float rootY = transform.position.y;
            float want = HipDrop(onL && !strikeL, _view.FootL.Point.y - rootY, onR && !strikeR, _view.FootR.Point.y - rootY);
            // ... and far enough that each standing leg reaches its foot where the hold has it (ReachDrop)
            float atOnce = 0f;
            if (onL && !strikeL) { Reach(ref _legL, targetL, rootY - _view.FootL.Point.y, rootY, ref want, ref atOnce); }
            if (onR && !strikeR) { Reach(ref _legR, targetR, rootY - _view.FootR.Point.y, rootY, ref want, ref atOnce); }
            want = Mathf.Min(want, MaxHipDrop);
            if (!_hipKnown) { _hipDrop = want; _hipKnown = true; }
            else if (!_fighter.Frozen) { _hipDrop = StepDrop(_hipDrop, want, atOnce, Time.deltaTime); }
            if (_hipDrop > 0f)
            {
                _mesh.position = _mesh.position + Vector3.down * _hipDrop;
                _view.HipsOn = _hipDrop > 0.001f;
                _view.HipsFrom = transform.position + Vector3.up * (HipHeight * _size);
                _view.HipsTo = _view.HipsFrom + Vector3.down * _hipDrop;
            }
            if (onL) { SolveFoot(ref _legL, targetL); }
            if (onR) { SolveFoot(ref _legR, targetR); }

            // Guard first, strike over the top. A strike re-solves from
            // wherever the guard left the arm, so the two compose rather than
            // fight, and the hand that is not throwing stays up.
            // The guard does not blend through hit stop either: the pair are
            // frozen on the contact frame, hands included.
            if (!_fighter.Frozen)
            {
                _guard = Mathf.Clamp01(_guard + (_fighter.Blocking ? 1f : -1f)
                                                * GuardBlend * Time.deltaTime);
            }
            Guard();
            Strike();

            // The debug view: F8 cycles it, read once a frame on Ahmed's own IK.
            bool isPlayer = _fighter is PlayerFighter;
            if (isPlayer && Input.GetKeyDown(KeyCode.F8)) { IKDebug.Show = IKDebug.Next(IKDebug.Show); }
            if (IKDebug.Draws(IKDebug.Show, isPlayer))
            {
                IKDebug.Build(_view, _prims);
                IKDebug.Draw(_prims);
            }
        }

        /// <summary>
        /// Which way round this fighter stands. An archetype's stance is a
        /// hash of its own name, not a random draw and not a field in the
        /// data: it has to be the same every time or the player cannot learn
        /// that a kickboxer leads with the other side, and it has to differ
        /// across the roster or six enemies around you read as one animation
        /// played six times. Ahmed is always orthodox -- his chain, and the
        /// right round kick the mesh generator poses, are built that way.
        /// </summary>
        private void RefreshStance()
        {
            EnemyFighter enemy = _fighter as EnemyFighter;
            string archetype = enemy != null ? enemy.Archetype : null;
            if (!ReferenceEquals(archetype, _stanceFrom))
            {
                _stanceFrom = archetype;
                _southpaw = Southpaw(archetype);
            }
        }

        /// <summary>Stable across runs, and spread across the roster.</summary>
        public static bool Southpaw(string archetype)
        {
            if (string.IsNullOrEmpty(archetype)) { return false; }
            int h = 0;
            for (int i = 0; i < archetype.Length; i++) { h = h * 31 + archetype[i]; }
            return ((h >> 3) & 1) == 1;
        }

        private static void Reset(ref Limb limb)
        {
            if (!limb.Ok) { return; }
            limb.Root.localRotation = limb.RootRest;
            limb.Mid.localRotation = limb.MidRest;
        }

        // -------------------------------------------------------------- feet

        /// <summary>
        /// One foot's hold on the ground (2026-10-31, after the Unreal build's
        /// SaudIK feet: "a planted ball is held at its spot in the world and
        /// steps after the man"). There is no animation here, so the foot's
        /// own place is its rest point under the root, which slides with him;
        /// held, the foot stays where it was planted, and once he has carried
        /// its rest point StepDrift away it steps there over StepSeconds,
        /// lifting StepLift at the middle. One foot at a time, unless the
        /// standing one is carried ForceDrift. Put somewhere new (SnapDrift),
        /// the hold starts again where he is. The striking leg and a foot over
        /// no ground are not held.
        /// </summary>
        public struct FootHold
        {
            public bool Held, Stepping;
            public Vector3 Anchor, From;   // world; Y not used
            public float T;                // 0..1 through a step
            /// <summary>The settle (2026-11-10): how long the foot has stood off
            /// its place without the man moving, and how far off it was last frame.</summary>
            public float Still, LastDrift;
            /// <summary>Where its rest point was last frame, once there has been one.</summary>
            public Vector3 LastRest;
            public bool Known;
        }

        public const float StepDrift = 0.12f;
        public const float ForceDrift = 0.30f;
        public const float SnapDrift = 1.0f;
        public const float StepSeconds = 0.14f;
        public const float StepLift = 0.06f;
        /// <summary>The settle, after the Unreal build's (SaudIK: SettleDrift 3 cm,
        /// SettleSeconds 0.25 s): standing still, a foot left more than SettleDrift
        /// off its place steps back under him after SettleSeconds. Still means its
        /// drift changed less than SettleStill in the frame.</summary>
        public const float SettleDrift = 0.03f;
        public const float SettleSeconds = 0.25f;
        public const float SettleStill = 0.0005f;

        private FootHold _holdL, _holdR;

        private static float Flat(Vector3 a, Vector3 b)
        {
            float x = a.x - b.x, z = a.z - b.z;
            return Mathf.Sqrt(x * x + z * z);
        }

        /// <summary>
        /// Where the foot goes this frame, on the ground plane, and how high
        /// it is lifted. Rest is its place under the root; Size scales every
        /// distance with the man (1 at Ahmed's). Frozen (hit stop) holds a step
        /// where it is. Pure: executed in the harness (tests/Hold.cs).
        /// </summary>
        /// <summary>
        /// (2026-11-10, the IK reviewed.) maySettle, otherDrift: the settle --
        /// a foot a turn or a stop has left off its place (under StepDrift, so
        /// it never stepped) stood there for as long as he did, 6.7-12.2 cm
        /// out; now, while he may settle (he is not attacking) and has stood
        /// still SettleSeconds, a foot more than SettleDrift off steps back,
        /// the further foot first (otherDrift: how far the other foot is off).
        /// And a man put somewhere new is re-planted whatever the foot was
        /// doing: the test was only made of a held foot, so one caught
        /// mid-step kept stepping from where he had been, the leg flung flat
        /// toward it for the rest of the step.
        /// </summary>
        public static Vector3 HoldFoot(ref FootHold h, bool otherSteps, Vector3 rest, bool striking,
                                       bool frozen, float dt, float size, out float lift,
                                       bool maySettle = false, float otherDrift = 0f)
        {
            lift = 0f;
            float s = size > 0f ? size : 1f;
            // put somewhere new: the rest point itself jumped
            bool put = h.Known && Flat(h.LastRest, rest) > SnapDrift * s;
            h.LastRest = rest; h.Known = true;
            if (put)
            {
                h.Held = true; h.Stepping = false; h.Anchor = rest; h.Still = 0f; h.LastDrift = 0f;
                return rest;
            }
            if (striking)
            {
                // The kicking foot leaves from where it stands (2026-11-10). Until this
                // day it was let go to its rest point on the kick's first frame, when the
                // strike's weight is still nothing: out of a walk the foot jumped up to
                // 34 cm in that one frame. It stays where it was -- a step stopped where it
                // had got to -- for Strike() to take it from and bring it back to, and the
                // ordinary step takes it home after the kick.
                if (h.Stepping)
                {
                    float at = Smooth(h.T);
                    h.Anchor = new Vector3(h.From.x + (rest.x - h.From.x) * at, rest.y, h.From.z + (rest.z - h.From.z) * at);
                }
                else if (!h.Held || Flat(h.Anchor, rest) > SnapDrift * s)
                {
                    h.Anchor = rest;
                }
                h.Held = true; h.Stepping = false; h.Still = 0f; h.LastDrift = Flat(h.Anchor, rest);
                return new Vector3(h.Anchor.x, rest.y, h.Anchor.z);   // where it stands
            }
            float drift = Flat(h.Anchor, rest);
            if (h.Held)
            {
                if (drift > SnapDrift * s)
                {
                    h.Anchor = rest; h.Still = 0f; h.LastDrift = 0f;
                    return rest;
                }
                // how long he has stood still with this foot off its place
                if (!frozen)
                {
                    h.Still = maySettle && Mathf.Abs(drift - h.LastDrift) < SettleStill * s ? h.Still + dt : 0f;
                    h.LastDrift = drift;
                }
                bool settle = !frozen && !otherSteps && h.Still >= SettleSeconds && drift > SettleDrift * s
                              && otherDrift <= drift;
                bool may = !otherSteps || drift > ForceDrift * s;
                if (!settle && (frozen || drift <= StepDrift * s || !may))
                {
                    return new Vector3(h.Anchor.x, rest.y, h.Anchor.z);
                }
                h.Held = false; h.Stepping = true; h.From = h.Anchor; h.T = 0f; h.Still = 0f;
            }
            if (h.Stepping)
            {
                if (!frozen) { h.T += dt / StepSeconds; }
                if (h.T >= 1f)
                {
                    h.Stepping = false; h.Held = true; h.Anchor = rest; h.Still = 0f; h.LastDrift = 0f;
                    return rest;
                }
                float k = Smooth(h.T);
                lift = Mathf.Sin(h.T * Mathf.PI) * StepLift * s;
                return new Vector3(h.From.x + (rest.x - h.From.x) * k, rest.y, h.From.z + (rest.z - h.From.z) * k);
            }
            h.Held = true; h.Anchor = rest; h.Still = 0f; h.LastDrift = 0f;
            return rest;
        }

        /// <summary>Which leg the attack in progress is thrown with, if a leg.</summary>
        private bool StrikingLeg(out bool right)
        {
            right = false;
            AttackRow row = _fighter.ActiveAttack;
            if (_fighter.State != FighterState.Attack || row == null) { return false; }
            bool arm, rear;
            if (!StrikeLimb(row.name, out arm, out rear) || arm) { return false; }
            right = IsRightSide(rear, _southpaw);
            return true;
        }

        /// <summary>
        /// Keep the sole on whatever is under it. A ray from above the
        /// ankle's rest position, straight down, finds the ground; the ankle
        /// goes to that height, the knee bends forward. On a flat slab this
        /// is a no-op to the millimetre, which is the test that it is right.
        /// The ray starts inside the fighter's own controller and so never
        /// hits it: a ray that begins inside a collider does not see it.
        /// </summary>
        private bool FindFoot(ref Limb leg, ref FootHold hold, bool otherSteps, bool striking, bool maySettle, float otherDrift,
                              ref IKDebug.FootView view, out Vector3 target)
        {
            target = Vector3.zero;
            if (!leg.Ok) { return false; }
            Vector3 ankleRest = transform.TransformPoint(leg.EndRestLocal);
            // held where it was planted, or stepping after him (HoldFoot); the
            // ground is looked for under where the foot is, not where it rests
            // (his own size, off his skeleton: the root this reads was never scaled, 2026-11-10)
            float lift;
            Vector3 place = HoldFoot(ref hold, otherSteps, ankleRest, striking, _fighter.Frozen, Time.deltaTime, _size, out lift,
                                     maySettle, otherDrift);
            Vector3 origin = place + Vector3.up * RayStart;
            Vector3 point;
            view.Cast = true;
            view.From = origin;
            view.To = origin + Vector3.down * (RayStart + 1.0f);
            if (!GroundUnder(origin, RayStart + 1.0f, out point))
            {
                // over nothing: not held; it is planted again where it rests once there is ground
                hold.Held = false; hold.Stepping = false;
                return false;
            }

            // his own ankle's height over the ground, not Ahmed's 7 cm: flat ground is a
            // no-op for a man of any size (2026-11-10)
            target = point + Vector3.up * (leg.EndRestLocal.y + lift);
            view.Hit = true;
            view.Point = point;
            view.Ankle = target;
            view.Held = hold.Held;
            return true;
        }

        /// <summary>The leg to its foot's place, from wherever the hips are now.</summary>
        private void SolveFoot(ref Limb leg, Vector3 target)
        {
            Vector3 pole = leg.Mid.position + _fighter.Facing * 0.6f;
            TwoBoneIK.Apply(leg.Root, leg.Mid, leg.End, target, pole);
        }

        /// <summary>
        /// How far the hips come down so the lower planted foot reaches its
        /// ground (2026-11-09, after the Unreal build's SaudIK: "the hips drop
        /// to the lower foot ... never rises: a step up under one foot bends
        /// that leg ... no further than 40 cm"). The legs rest straight, so
        /// ground lower than the root under a foot is out of reach by exactly
        /// that much: on a step the low foot dangled at full extension.
        /// Ground heights are against the root's, negative below it; a foot
        /// over nothing, or the striking leg, does not count. Pure.
        /// </summary>
        public static float HipDrop(bool onL, float groundL, bool onR, float groundR)
        {
            float low = 0f;
            if (onL) { low = Mathf.Min(low, groundL); }
            if (onR) { low = Mathf.Min(low, groundR); }
            return Mathf.Min(-low, MaxHipDrop);
        }

        /// <summary>The drop eased toward what is wanted, the same at 30 and 60 Hz. Pure.</summary>
        public static float EaseDrop(float current, float want, float dt)
        {
            return current + (want - current) * (1f - Mathf.Exp(-HipDropRate * Mathf.Max(0f, dt)));
        }

        public const float MaxHipDrop = 0.40f;
        public const float HipDropRate = 12f;

        /// <summary>
        /// How far the hips must come down for a leg to reach a foot that is
        /// not under its hip (2026-11-10, the IK reviewed: "a held foot is not
        /// on the floor and does not stay put"). The legs rest straight, so a
        /// foot the hold keeps Flat metres away along the ground is out of
        /// reach by the difference, and HipDrop looked at the ground's height
        /// only: on flat ground the hips never moved, the solver straightened
        /// the leg toward a target it could not reach, and a held ankle hung
        /// up to 4.2 cm over the floor and 1.4 off its place at a run. Stand:
        /// how far the hip stands over the ankle at rest; Span: hip to ankle
        /// at rest; Below: how much lower than its rest the ankle is wanted.
        /// A standing leg (Flat 0, Below 0, Stand = Span) needs none. Pure.
        /// </summary>
        public static float ReachDrop(float stand, float span, float flat, float below)
        {
            if (span <= 0f) { return 0f; }
            if (flat >= span) { return MaxHipDrop; }
            return Mathf.Clamp(below + stand - Mathf.Sqrt(span * span - flat * flat), 0f, MaxHipDrop);
        }

        /// <summary>The hips rise slower than they drop: coming down is what
        /// puts a foot on the floor; going up can wait. Measured on the suite's
        /// rig walking at 2.5 and 3.4 m/s, 60 Hz (2026-11-10): rising at the
        /// drop's own 12 a second the hips bobbed 2.6 cm with every shuffled
        /// step, 1.7 cm most in a frame; at 6, 1.7 cm; at 3, 1.0 cm and 1.0 in
        /// a frame -- he runs 4 to 5 cm lower, knees bent, and comes back up
        /// inside a second of stopping.</summary>
        public const float HipRiseRate = 3f;

        /// <summary>
        /// The hips' drop this frame. Down toward Want at HipDropRate, as the
        /// ground's part always was (a kerb eases); never less than AtOnce,
        /// the part a held foot's reach needs, which cannot wait a frame or
        /// the foot is off the floor for it; up at HipRiseRate. Pure.
        /// </summary>
        public static float StepDrop(float current, float want, float atOnce, float dt)
        {
            float t = Mathf.Max(0f, dt);
            float rate = want < current ? HipRiseRate : HipDropRate;
            float eased = current + (want - current) * (1f - Mathf.Exp(-rate * t));
            return Mathf.Max(eased, Mathf.Min(atOnce, MaxHipDrop));
        }

        /// <summary>One standing leg's say in the hips' drop: what its foot's
        /// place needs (ReachDrop), and the part of that the ground's own depth
        /// does not account for, which is taken at once.</summary>
        private static void Reach(ref Limb leg, Vector3 target, float groundDeep, float rootY, ref float want, ref float atOnce)
        {
            float need = ReachDrop(leg.Stand, leg.Span, Flat(leg.Root.position, target), rootY + leg.EndRestLocal.y - target.y);
            want = Mathf.Max(want, need);
            atOnce = Mathf.Max(atOnce, need - Mathf.Max(0f, groundDeep));
        }

        /// <summary>
        /// The nearest thing under a point that is not a fighter.
        ///
        /// A plain Raycast was wrong the moment there was a crowd. The ray
        /// leaves this fighter's own controller at about two thirds of a
        /// metre, and a controller is 0.32 m across and 1.8 m tall, so anyone
        /// standing within roughly 0.4 m -- which is every enemy in a ring
        /// around the player, and the player himself when one closes in --
        /// is the first thing it hits. The foot would then plant on top of
        /// the other fighter and the leg would climb him.
        /// </summary>
        private static bool GroundUnder(Vector3 origin, float distance, out Vector3 point)
        {
            point = Vector3.zero;
            int n = Physics.RaycastNonAlloc(origin, Vector3.down, Hits, distance);
            float nearest = float.MaxValue;
            bool found = false;
            for (int i = 0; i < n; i++)
            {
                Collider c = Hits[i].collider;
                if (c == null || c.GetComponentInParent<Fighter>() != null) { continue; }
                if (Hits[i].distance < nearest)
                {
                    nearest = Hits[i].distance;
                    point = Hits[i].point;
                    found = true;
                }
            }
            return found;
        }

        // ------------------------------------------------------------- guard

        /// <summary>
        /// Hands up. Every archetype has a guardChance and the grappler
        /// guards while it advances, so enemies were blocking a third of the
        /// time with nothing on screen to say so -- the one piece of state
        /// the player most needs to read off a body, and the only way to
        /// find it was to throw a punch and watch it do nothing.
        /// </summary>
        private void Guard()
        {
            // Still solved while stunned even with the guard down: that is
            // when the hands are thrown, and a fighter who wears a hook
            // without moving read as one who did not feel it.
            if (_guard <= 0.001f && _fighter.State != FighterState.Hit) { return; }
            Vector3 facing = _fighter.Facing;
            Vector3 side = Vector3.Cross(Vector3.up, facing);
            _view.GuardOn = _guard > 0.001f;
            GuardHand(ref _armL, facing, -side, ref _view.GuardL);
            GuardHand(ref _armR, facing, side, ref _view.GuardR);
        }

        private void GuardHand(ref Limb arm, Vector3 facing, Vector3 side, ref Vector3 shown)
        {
            if (!arm.Ok) { return; }
            Vector3 rest = transform.TransformPoint(arm.EndRestLocal);
            Vector3 up = GuardTarget(transform.position, facing, side, _size);
            // Tired and hurt: the hands come down as the health does. A
            // fighter with no vitals set is not a dying one -- it is one
            // nobody has told yet -- so it guards fully.
            float health = _fighter.MaxHealth > 0f ? _fighter.HealthFraction : 1f;
            Vector3 target = Vector3.Lerp(rest, up, _guard * GuardSag(health));
            if (_fighter.State == FighterState.Hit)
            {
                target += FlinchOffset(_fighter.Recoil);
            }
            shown = target;
            Vector3 pole = (arm.Root.position + target) * 0.5f - Vector3.up * 0.6f;
            TwoBoneIK.Apply(arm.Root, arm.Mid, arm.End, target, pole);
        }

        /// <summary>Where a raised fist sits. Pure, so the guard's geometry
        /// can be checked without an engine like everything else here. Size:
        /// the man's against Ahmed's (SizeOf, 2026-11-10) -- the chin of a man
        /// half again as tall is half again as high, forward and apart too;
        /// nothing or less is taken as Ahmed's.</summary>
        public static Vector3 GuardTarget(Vector3 origin, Vector3 facing, Vector3 side, float size = 1f)
        {
            float s = size > 0f ? size : 1f;
            return origin + (facing * GuardForward + side * GuardSpread
                 + Vector3.up * GuardHeight) * s;
        }

        // ----------------------------------------------------------- strikes

        /// <summary>
        /// Which limb throws each attack row, as lead or rear rather than
        /// left or right. Jab and hook come off the lead hand, cross and the
        /// finisher off the rear, knee and kick off the rear leg -- which is
        /// what those strikes are, in any stance. Naming the sides here was
        /// what made every fighter in the game throw with the same hand.
        /// </summary>
        public static bool StrikeLimb(string row, out bool arm, out bool rear)
        {
            switch (row)
            {
                case "Jab": arm = true; rear = false; return true;
                case "Hook": arm = true; rear = false; return true;
                case "Cross": arm = true; rear = true; return true;
                case "Special": arm = true; rear = true; return true;
                case "Knee": arm = false; rear = true; return true;
                case "Kick": arm = false; rear = true; return true;
            }
            arm = false; rear = false;
            return false;
        }

        /// <summary>Orthodox leads with the left, southpaw with the right.</summary>
        public static bool IsRightSide(bool rear, bool southpaw)
        {
            return rear != southpaw;
        }

        /// <summary>
        /// How far into the strike the limb is: 0 at the start, up through
        /// the startup, 1 for every active frame, back to 0 by the end of the
        /// recovery. Smoothstep in and out so the fist does not start or
        /// stop like a machine. Pure, and tested at 60 Hz for every row.
        /// </summary>
        public static float StrikeWeight(float elapsed, float startup, float active, float recovery)
        {
            if (elapsed <= 0f) { return 0f; }
            if (elapsed < startup) { return Smooth(elapsed / startup); }
            if (elapsed < startup + active) { return 1f; }
            if (elapsed < startup + active + recovery)
            {
                return 1f - Smooth((elapsed - startup - active) / recovery);
            }
            return 0f;
        }

        /// <summary>
        /// How far the limb is drawn *back* before it goes out.
        ///
        /// The reach blend alone sends the fist out from the first frame of
        /// the startup, so a punch and a haymaker look the same right up to
        /// the moment one of them lands — there is nothing to read and
        /// nothing to react to, which is the whole complaint about fighting
        /// something that never tells you what it is doing. This pulls the
        /// hand back over the first two thirds of the startup and releases it
        /// into the strike, so the wind-up is visible for exactly as long as
        /// the row says the wind-up lasts. A jab's 0.06 s startup is a twitch;
        /// a heavy's 0.18 s is a cocked arm you can step out of.
        ///
        /// Separate from <see cref="StrikeWeight"/> on purpose: that is the
        /// reach, stays 0..1, and its invariants are tested. This is the
        /// other motion. Pure, for the same reason.
        /// </summary>
        public static float WindUp(float elapsed, float startup)
        {
            if (startup <= 0f || elapsed <= 0f || elapsed >= startup) { return 0f; }
            float t = elapsed / startup;
            const float peak = 0.62f;           // where the arm is furthest back
            return t < peak
                ? Smooth(t / peak)
                : 1f - Smooth((t - peak) / (1f - peak));
        }

        /// <summary>How far back a cocked limb travels, in metres.</summary>
        public const float WindUpDraw = 0.22f;

        /// <summary>
        /// Where a struck fighter's hands are thrown. The blow that is
        /// pushing him is pushing them too, and the guard is not up while it
        /// does: a fighter who takes a hook and keeps a perfect guard reads
        /// as a fighter who did not feel it.
        /// </summary>
        public static Vector3 FlinchOffset(Vector3 recoil)
        {
            Vector3 flat = new Vector3(recoil.x, 0f, recoil.z);
            float m = flat.magnitude;
            if (m < 0.01f) { return Vector3.zero; }
            // Bounded: a big knockback must not throw the hands off the body.
            return flat / m * Mathf.Min(m * 0.05f, 0.22f) - Vector3.up * Mathf.Min(m * 0.03f, 0.14f);
        }

        /// <summary>
        /// How high the hands are carried, as a fraction of the full guard.
        /// A fighter who has taken most of a health bar carries them lower,
        /// which is the only thing in the world that says how hurt an enemy
        /// is — there is no bar over their head.
        /// </summary>
        public static float GuardSag(float healthFraction)
        {
            return Mathf.Lerp(0.72f, 1f, Mathf.Clamp01(healthFraction));
        }

        private static float Smooth(float t)
        {
            t = Mathf.Clamp01(t);
            return t * t * (3f - 2f * t);
        }

        /// <summary>Where the end of the limb lands at full extension: along
        /// the facing at the row's reach, at the striking height.</summary>
        public static Vector3 StrikeTarget(Vector3 origin, Vector3 facing, float reach, float height)
        {
            return origin + facing * reach + Vector3.up * height;
        }

        // The strike solved last frame: which limb (0 left arm, 1 right arm, 2 left
        // leg, 3 right leg; -1 none) and where its end was, in the fighter's frame.
        private int _struck = -1;
        private Vector3 _struckEnd;
        // A swing taken away -- he was hit in it, or another row began -- lets its
        // limb go from where it was struck: its share runs 1 to 0 over LetGoSeconds.
        private int _goLimb = -1;
        private Vector3 _goFrom;
        private float _letGo;

        /// <summary>
        /// How long a limb takes to come off a strike that was taken away
        /// (2026-11-10). Until this day Strike() simply returned once the state
        /// left Attack, and the fist or foot was back at the guard or the floor
        /// on the frame of the blow -- 94 cm for a punch, 125 for a kick, in
        /// one frame, and that snapped pose was the one hit stop then held.
        /// The Unreal build lets a taken swing go in 0.05 s on a limb its clip
        /// already carries; here the whole limb is the IK's, so twice that.
        /// </summary>
        public const float LetGoSeconds = 0.10f;

        /// <summary>The let-go's share a frame on: it does not run through hit
        /// stop, so the contact frame holds the limb where it was struck. Pure.</summary>
        public static float LetGo(float share, float dt, bool frozen)
        {
            if (frozen) { return share; }
            return Mathf.Max(0f, share - dt / LetGoSeconds);
        }

        private Limb LimbAt(int index)
        {
            return index == 0 ? _armL : index == 1 ? _armR : index == 2 ? _legL : _legR;
        }

        /// <summary>Elbows hang under the punch; the kicking knee leads the foot.</summary>
        private void SolveStrike(Limb limb, bool arm, Vector3 target)
        {
            Vector3 pole = arm
                ? (limb.Root.position + target) * 0.5f - Vector3.up * 0.6f
                : limb.Root.position + _fighter.Facing * 0.6f;
            TwoBoneIK.Apply(limb.Root, limb.Mid, limb.End, target, pole);
        }

        private void Strike()
        {
            // which limb the swing in progress is thrown with, and how far into it
            AttackRow row = _fighter.ActiveAttack;
            int cur = -1; bool arm = false; float weight = 0f;
            if (_fighter.State == FighterState.Attack && row != null)
            {
                bool rear;
                if (StrikeLimb(row.name, out arm, out rear))
                {
                    weight = StrikeWeight(_fighter.AttackTime, row.startup, row.active, row.recovery);
                    if (weight > 0f) { cur = (arm ? 0 : 2) + (IsRightSide(rear, _southpaw) ? 1 : 0); }
                }
            }

            // a swing taken away: its limb is let go from where it was struck
            if (_struck >= 0 && _struck != cur) { _goLimb = _struck; _goFrom = _struckEnd; _letGo = 1f; }
            _struck = -1;
            if (_letGo > 0f)
            {
                _letGo = LetGo(_letGo, Time.deltaTime, _fighter.Frozen);
                Limb was = LimbAt(_goLimb);
                if (_letGo > 0f && was.Ok)
                {
                    // from where the feet and the guard have it this frame, back toward the strike
                    Vector3 held = Vector3.Lerp(was.End.position, transform.TransformPoint(_goFrom), Smooth(_letGo));
                    SolveStrike(was, _goLimb < 2, held);
                    _view.StrikeOn = true;
                    _view.StrikeTarget = held;
                    _view.StrikeWeight = Smooth(_letGo);
                }
                else { _letGo = 0f; _goLimb = -1; }
            }

            if (cur < 0) { return; }
            Limb limb = LimbAt(cur);
            if (!limb.Ok) { return; }

            Vector3 facing = _fighter.Facing;
            Vector3 full = StrikeTarget(transform.position, facing, row.reach,
                                        arm ? ShoulderHeight : HipHeight);
            // From where the limb IS this frame -- the feet, the guard and a let-go have
            // been solved -- not from its A-pose rest point (2026-11-10): a punch pressed
            // with the guard up sent the fist 49 to 66 cm down and back to that rest point
            // in the first frame it had any weight, before it went forward.
            Vector3 from = limb.End.position;
            Vector3 target = Vector3.Lerp(from, full, weight);
            // Cocked before it is thrown. This is the tell.
            target -= facing * (WindUp(_fighter.AttackTime, row.startup) * WindUpDraw);
            _view.StrikeOn = true;
            _view.StrikeTarget = target;
            _view.StrikeWeight = weight;

            SolveStrike(limb, arm, target);
            _struck = cur;
            _struckEnd = transform.InverseTransformPoint(limb.End.position);
        }
    }
}
