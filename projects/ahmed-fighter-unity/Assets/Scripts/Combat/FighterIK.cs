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
            public bool Ok;
        }

        private Fighter _fighter;
        private Limb _legL, _legR, _armL, _armR;
        private float _guard;
        private bool _southpaw;
        private string _stanceFrom;

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

            PlantFoot(ref _legL);
            PlantFoot(ref _legR);

            // Guard first, strike over the top. A strike re-solves from
            // wherever the guard left the arm, so the two compose rather than
            // fight, and the hand that is not throwing stays up.
            _guard = Mathf.Clamp01(_guard + (_fighter.Blocking ? 1f : -1f)
                                            * GuardBlend * Time.deltaTime);
            Guard();
            Strike();
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
        /// Keep the sole on whatever is under it. A ray from above the
        /// ankle's rest position, straight down, finds the ground; the ankle
        /// goes to that height, the knee bends forward. On a flat slab this
        /// is a no-op to the millimetre, which is the test that it is right.
        /// The ray starts inside the fighter's own controller and so never
        /// hits it: a ray that begins inside a collider does not see it.
        /// </summary>
        private void PlantFoot(ref Limb leg)
        {
            if (!leg.Ok) { return; }
            Vector3 ankleRest = transform.TransformPoint(leg.EndRestLocal);
            Vector3 origin = ankleRest + Vector3.up * RayStart;
            Vector3 point;
            if (!GroundUnder(origin, RayStart + 1.0f, out point)) { return; }

            Vector3 target = point + Vector3.up * AnkleHeight;
            Vector3 pole = leg.Mid.position + _fighter.Facing * 0.6f;
            TwoBoneIK.Apply(leg.Root, leg.Mid, leg.End, target, pole);
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
            if (_guard <= 0.001f) { return; }
            Vector3 facing = _fighter.Facing;
            Vector3 side = Vector3.Cross(Vector3.up, facing);
            GuardHand(ref _armL, facing, -side);
            GuardHand(ref _armR, facing, side);
        }

        private void GuardHand(ref Limb arm, Vector3 facing, Vector3 side)
        {
            if (!arm.Ok) { return; }
            Vector3 rest = transform.TransformPoint(arm.EndRestLocal);
            Vector3 up = GuardTarget(transform.position, facing, side);
            Vector3 target = Vector3.Lerp(rest, up, _guard);
            Vector3 pole = (arm.Root.position + target) * 0.5f - Vector3.up * 0.6f;
            TwoBoneIK.Apply(arm.Root, arm.Mid, arm.End, target, pole);
        }

        /// <summary>Where a raised fist sits. Pure, so the guard's geometry
        /// can be checked without an engine like everything else here.</summary>
        public static Vector3 GuardTarget(Vector3 origin, Vector3 facing, Vector3 side)
        {
            return origin + facing * GuardForward + side * GuardSpread
                 + Vector3.up * GuardHeight;
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

        private void Strike()
        {
            AttackRow row = _fighter.ActiveAttack;
            if (_fighter.State != FighterState.Attack || row == null) { return; }

            bool arm, rear;
            if (!StrikeLimb(row.name, out arm, out rear)) { return; }
            bool right = IsRightSide(rear, _southpaw);
            Limb limb = arm ? (right ? _armR : _armL) : (right ? _legR : _legL);
            if (!limb.Ok) { return; }

            float weight = StrikeWeight(_fighter.AttackTime, row.startup, row.active, row.recovery);
            if (weight <= 0f) { return; }

            Vector3 facing = _fighter.Facing;
            Vector3 full = StrikeTarget(transform.position, facing, row.reach,
                                        arm ? ShoulderHeight : HipHeight);
            Vector3 rest = transform.TransformPoint(limb.EndRestLocal);
            Vector3 target = Vector3.Lerp(rest, full, weight);

            // Elbows hang under the punch; the kicking knee leads the foot.
            Vector3 pole = arm
                ? (limb.Root.position + target) * 0.5f - Vector3.up * 0.6f
                : limb.Root.position + facing * 0.6f;
            TwoBoneIK.Apply(limb.Root, limb.Mid, limb.End, target, pole);
        }
    }
}
