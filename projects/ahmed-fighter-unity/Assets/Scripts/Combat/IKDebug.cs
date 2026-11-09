using System.Collections.Generic;
using UnityEngine;

namespace Ahmed.Combat
{
    /// <summary>
    /// The computed pose, drawn. Asked 2026-10-31 (Riyadh) as "add to unity",
    /// after the Unreal build's IK debug view (saud.ik.Show, its
    /// Combat/SaudIKDebug.h): the same idea over this port's own IK, which is
    /// smaller -- FighterIK plants the feet on a ray, raises the guard and
    /// drives the striking limb; it holds no feet, meets no blow and turns no
    /// head, so none of that is drawn.
    ///
    /// F8 cycles <see cref="Show"/>: off, every fighter, Ahmed only. Drawn
    /// each frame:
    ///  - each foot's ground ray, blue where it found ground and red where it
    ///    found nothing, a cross where it hit and one where the ankle goes --
    ///    green while the foot is held where it was planted, yellow while it
    ///    steps after him (FighterIK.HoldFoot, 2026-10-31);
    ///  - the hips' drop, a white line from where they rest to where they are
    ///    (FighterIK.HipDrop, 2026-11-09);
    ///  - the guard's two fist targets while the guard is up;
    ///  - the strike's target, its cross growing as the strike comes on.
    ///
    /// Build is pure (a view in, a list out) and executed in the harness
    /// (Tools/harness/tests/IKDebug.cs). Draw uses Debug.DrawLine, which Unity
    /// shows in the editor: always in the Scene view, in the Game view with
    /// Gizmos on, and never in a player build.
    /// </summary>
    public static class IKDebug
    {
        /// <summary>0 off, 1 every fighter, 2 the player's man only.</summary>
        public static int Show;

        public static int Next(int show) { return (show + 1) % 3; }

        public static bool Draws(int show, bool isPlayer)
        {
            return show == 1 || (show == 2 && isPlayer);
        }

        public enum Colour { Hit, Missed, Ankle, Free, Guard, Strike, Hips }

        public static Color ColourOf(Colour c)
        {
            switch (c)
            {
                case Colour.Hit: return new Color(0.35f, 0.67f, 1f, 1f);      // blue: the ray found ground
                case Colour.Missed: return new Color(1f, 0.2f, 0.2f, 1f);     // red: it found nothing
                case Colour.Ankle: return new Color(0.24f, 0.86f, 0.35f, 1f); // green: a held foot's ankle
                case Colour.Free: return new Color(0.98f, 0.78f, 0.16f, 1f);  // yellow: a foot stepping after him
                case Colour.Guard: return new Color(0.67f, 0.35f, 1f, 1f);    // violet: a guard fist's target
                case Colour.Strike: return new Color(1f, 0.47f, 0.12f, 1f);   // orange: the strike's target
                case Colour.Hips: return new Color(1f, 1f, 1f, 1f);           // white: the hips' drop
            }
            return new Color(1f, 1f, 1f, 1f);
        }

        public enum Shape { Line, Cross }

        /// <summary>A line A to B, or a cross at A of half-size Size. Metres.</summary>
        public struct Prim
        {
            public Shape Shape;
            public Vector3 A, B;
            public float Size;
            public Colour Colour;
        }

        /// <summary>One foot's ray as FighterIK cast it, and where it sent the ankle.</summary>
        public struct FootView
        {
            public bool Cast, Hit, Held;
            public Vector3 From, To, Point, Ankle;
        }

        public struct View
        {
            public FootView FootL, FootR;
            public bool HipsOn;
            public Vector3 HipsFrom, HipsTo;
            public bool GuardOn;
            public Vector3 GuardL, GuardR;
            public bool StrikeOn;
            public Vector3 StrikeTarget;
            public float StrikeWeight;
        }

        public const float PointSize = 0.03f;    // a ray's hit, an ankle's target
        public const float GuardSize = 0.04f;
        public const float StrikeMin = 0.03f;    // the strike's cross at no weight ...
        public const float StrikeMax = 0.08f;    // ... and at full

        /// <summary>What to draw for one fighter this frame. Into is cleared first.</summary>
        public static void Build(View v, List<Prim> into)
        {
            into.Clear();
            Foot(v.FootL, into);
            Foot(v.FootR, into);
            if (v.HipsOn) { into.Add(Line(v.HipsFrom, v.HipsTo, Colour.Hips)); }
            if (v.GuardOn)
            {
                into.Add(Cross(v.GuardL, GuardSize, Colour.Guard));
                into.Add(Cross(v.GuardR, GuardSize, Colour.Guard));
            }
            if (v.StrikeOn && v.StrikeWeight > 0f)
            {
                float w = Mathf.Clamp01(v.StrikeWeight);
                into.Add(Cross(v.StrikeTarget, StrikeMin + (StrikeMax - StrikeMin) * w, Colour.Strike));
            }
        }

        private static void Foot(FootView f, List<Prim> into)
        {
            if (!f.Cast) { return; }
            into.Add(Line(f.From, f.To, f.Hit ? Colour.Hit : Colour.Missed));
            if (!f.Hit) { return; }
            into.Add(Cross(f.Point, PointSize, Colour.Hit));
            into.Add(Cross(f.Ankle, PointSize, f.Held ? Colour.Ankle : Colour.Free));
        }

        public static Prim Line(Vector3 a, Vector3 b, Colour c)
        {
            Prim p = new Prim(); p.Shape = Shape.Line; p.A = a; p.B = b; p.Colour = c;
            return p;
        }

        public static Prim Cross(Vector3 at, float size, Colour c)
        {
            Prim p = new Prim(); p.Shape = Shape.Cross; p.A = at; p.B = at; p.Size = size; p.Colour = c;
            return p;
        }

        /// <summary>Into the editor's views for this frame (Debug.DrawLine's default: one frame).</summary>
        public static void Draw(List<Prim> prims)
        {
            for (int i = 0; i < prims.Count; i++)
            {
                Prim p = prims[i];
                Color c = ColourOf(p.Colour);
                if (p.Shape == Shape.Line)
                {
                    Debug.DrawLine(p.A, p.B, c);
                    continue;
                }
                Debug.DrawLine(p.A - Vector3.right * p.Size, p.A + Vector3.right * p.Size, c);
                Debug.DrawLine(p.A - Vector3.up * p.Size, p.A + Vector3.up * p.Size, c);
                Debug.DrawLine(p.A - Vector3.forward * p.Size, p.A + Vector3.forward * p.Size, c);
            }
        }
    }
}
