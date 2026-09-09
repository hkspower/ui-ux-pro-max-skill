using UnityEngine;

namespace Ahmed.Combat
{
    /// <summary>
    /// A two-bone inverse kinematics solver: a hip, a knee and an ankle, or a
    /// shoulder, an elbow and a wrist, and where the end should be.
    ///
    /// <see cref="Solve"/> is pure -- positions in, positions out, no
    /// Transform, no engine -- on purpose. It is the piece of the runtime
    /// pose that is only geometry, and keeping it free of the scene is what
    /// lets it be executed and checked without an editor: ten thousand
    /// random targets, the limb lands on every reachable one and points at
    /// every unreachable one, and the joint always bends toward the pole.
    /// <see cref="Apply"/> is the thin part that turns the answer into bone
    /// rotations, and it is the part an editor has to see.
    /// </summary>
    public static class TwoBoneIK
    {
        public const float Epsilon = 1e-5f;

        /// <summary>
        /// Where the middle joint and the end go for a chain of two fixed
        /// lengths reaching from <paramref name="root"/> toward
        /// <paramref name="target"/>, bending toward <paramref name="pole"/>.
        ///
        /// Law of cosines: with the root-to-target distance d and the two
        /// lengths a and b, the joint sits a distance x = (a² - b² + d²) / 2d
        /// along the root-to-target line and h = sqrt(a² - x²) off it, in the
        /// plane the pole picks. A target beyond reach straightens the limb
        /// toward it; a target at the root falls back to the chain's current
        /// direction, so nothing divides by zero and nothing snaps.
        /// </summary>
        public static void Solve(Vector3 root, Vector3 mid, Vector3 end, Vector3 target, Vector3 pole,
                                 out Vector3 newMid, out Vector3 newEnd)
        {
            float upper = (mid - root).magnitude;
            float lower = (end - mid).magnitude;
            float reach = upper + lower;

            Vector3 toTarget = target - root;
            float dist = toTarget.magnitude;
            if (dist < Epsilon)
            {
                toTarget = end - root;
                dist = toTarget.magnitude;
                if (dist < Epsilon) { newMid = mid; newEnd = end; return; }
            }
            Vector3 axis = toTarget / dist;

            // The bend plane: the pole's direction with the part along the
            // limb removed. A pole on the line says nothing, so fall back to
            // the way the joint already bends, then to anything perpendicular.
            Vector3 bend = pole - root;
            bend -= axis * Vector3.Dot(bend, axis);
            if (bend.sqrMagnitude < Epsilon * Epsilon)
            {
                bend = mid - root;
                bend -= axis * Vector3.Dot(bend, axis);
            }
            if (bend.sqrMagnitude < Epsilon * Epsilon)
            {
                bend = Vector3.Cross(axis, Vector3.up);
                if (bend.sqrMagnitude < Epsilon * Epsilon) { bend = Vector3.Cross(axis, Vector3.right); }
            }
            bend.Normalize();

            if (dist >= reach - Epsilon)
            {
                newMid = root + axis * upper;
                newEnd = root + axis * reach;
                return;
            }

            float x = (upper * upper - lower * lower + dist * dist) / (2f * dist);
            float h = Mathf.Sqrt(Mathf.Max(0f, upper * upper - x * x));
            newMid = root + axis * x + bend * h;
            newEnd = target;
        }

        /// <summary>
        /// Rotate two bones so the chain lands where <see cref="Solve"/> says.
        /// Each rotation is the smallest one that turns the bone's current
        /// direction into the solved one, composed onto what the bone already
        /// has, so twist is left alone and only the bend changes.
        /// </summary>
        public static void Apply(Transform rootBone, Transform midBone, Transform endBone,
                                 Vector3 target, Vector3 pole)
        {
            Vector3 a = rootBone.position, b = midBone.position, c = endBone.position;
            Vector3 newMid, newEnd;
            Solve(a, b, c, target, pole, out newMid, out newEnd);

            rootBone.rotation = Quaternion.FromToRotation(b - a, newMid - a) * rootBone.rotation;
            // The mid and end moved with the root; read them again.
            Vector3 bNow = midBone.position, cNow = endBone.position;
            midBone.rotation = Quaternion.FromToRotation(cNow - bNow, newEnd - bNow) * midBone.rotation;
        }
    }
}
