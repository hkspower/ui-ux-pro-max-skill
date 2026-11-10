// Drives FighterIK through a real skeleton in a real scene: bones parented to
// bones, a ground to raycast against, and Unity's own call order. Everything
// here was out of reach of a pure test -- Apply's rotation composition, the
// foot ray, the crowd filter, and whether a pose accumulates over frames.
using System; using System.Collections.Generic; using UnityEngine;
using Ahmed.Combat; using Ahmed.Data;

public static class Pose {
    static int fails = 0;
    static void Check(bool ok, string w) { if (!ok) { fails++; Console.WriteLine("  FAIL " + w); } }

    // The generator's joint table, in Unity's axes. Blender (x, y, z) leaves as
    // Unity (x, z, -y): the exporter sends Blender's -Y, the way Ahmed faces,
    // to Unity's +Z, and Blender's +Z, up, to Unity's +Y.
    static readonly string[,] Chain = {
        {"thigh",   "0.092  0.952  0"},     {"calf", "0.088 0.513 0"},   {"foot", "0.082 0.070 0"},
        {"upperarm","0.178  1.442  0.006"}, {"lowerarm","0.415 1.205 0"},{"hand", "0.601 1.019 0"},
    };
    static Vector3 P(string s, float sign) {
        string[] p = s.Split(new[]{' '}, StringSplitOptions.RemoveEmptyEntries);
        return new Vector3(float.Parse(p[0]) * sign, float.Parse(p[1]), float.Parse(p[2]));
    }

    class Rig { public GameObject Root; public EnemyFighter Fighter; public FighterIK IK;
                public Dictionary<string,Transform> Bones = new Dictionary<string,Transform>(); }

    static Rig BuildFighter(string name, Vector3 at) { return BuildFighter(name, at, 1f); }

    // size: the man against Ahmed. The bones stand at their scaled places and the root
    // is left unscaled, as EnemyFighter.SetStature leaves it (it scales the Mesh child
    // and the controller); the harness's Transform does not compose a parent's scale.
    static Rig BuildFighter(string name, Vector3 at, float size) {
        GameObject go = new GameObject(name);
        go.transform.position = at;
        CharacterController body = go.AddComponent<CharacterController>();
        body.height = 1.8f * size; body.radius = 0.32f * size; body.center = new Vector3(0f, 0.9f * size, 0f);

        GameObject mesh = new GameObject("Mesh");
        mesh.transform.SetParent(go.transform, false);

        Rig r = new Rig(); r.Root = go;
        for (int side = 0; side < 2; side++) {
            float sign = side == 0 ? 1f : -1f; string suffix = side == 0 ? "_l" : "_r";
            Transform parent = mesh.transform;
            for (int i = 0; i < Chain.GetLength(0); i++) {
                if (i == 3) parent = mesh.transform;              // the arm starts again at the mesh
                string bone = Chain[i,0] + suffix;
                GameObject b = new GameObject(bone);
                b.transform.SetParent(parent, false);
                // local offset from the parent bone, in the parent's frame
                Vector3 world = P(Chain[i,1], sign) * size + at;
                b.transform.position = world;
                r.Bones[bone] = b.transform;
                parent = b.transform;
            }
        }
        r.Fighter = go.AddComponent<EnemyFighter>();
        r.IK = go.AddComponent<FighterIK>();
        return r;
    }

    static GameObject Slab(string name, Vector3 centre, Vector3 size) {
        GameObject g = new GameObject(name);
        g.transform.position = centre; g.transform.localScale = size;
        g.AddComponent<BoxCollider>();
        return g;
    }

    static float AnkleY(Rig r, string side) { return r.Bones["foot_" + side].position.y; }
    static float Len(Rig r, string a, string b) { return (r.Bones[a].position - r.Bones[b].position).magnitude; }

    public static int Main() {
        // ---------------------------------------------------- feet on the floor
        Console.WriteLine("FEET");
        Scene.Reset();
        Slab("Ground", new Vector3(0f, -0.5f, 0f), new Vector3(200f, 1f, 200f));   // top at y = 0
        Rig a = BuildFighter("Ahmed", Vector3.zero);
        float thighLen = Len(a, "thigh_l", "calf_l"), calfLen = Len(a, "calf_l", "foot_l");
        Scene.Step(4);
        Check(Math.Abs(AnkleY(a, "l") - FighterIK.AnkleHeight) < 2e-3f,
              "left ankle sits an ankle's height above flat ground (" + AnkleY(a,"l").ToString("0.0000") + ")");
        Check(Math.Abs(AnkleY(a, "r") - FighterIK.AnkleHeight) < 2e-3f, "right ankle likewise");
        Check(Math.Abs(Len(a,"thigh_l","calf_l") - thighLen) < 1e-3f, "the thigh keeps its length through Apply");
        Check(Math.Abs(Len(a,"calf_l","foot_l") - calfLen) < 1e-3f, "the shin keeps its length through Apply");

        // ------------------------------------------------------- uneven ground
        // This is the check that proves the foot ray drives anything at all:
        // on flat ground at y = 0 the target lands exactly where the ankle
        // already rests, so a do-nothing IK passes. A step does not.
        Console.WriteLine("\nSTEP");
        Scene.Reset();
        Slab("Ground", new Vector3(0f, -0.5f, 0f), new Vector3(200f, 1f, 200f));
        Slab("Step", new Vector3(0.30f, 0.05f, 0f), new Vector3(0.36f, 0.30f, 0.60f));  // top at 0.20, clear of the root
        Rig b = BuildFighter("Ahmed", new Vector3(0.20f, 0f, 0f));
        float bThigh = Len(b, "thigh_l", "calf_l"), bCalf = Len(b, "calf_l", "foot_l");
        Scene.Step(4);
        float rootY = b.Root.transform.position.y;
        float legSpan = bThigh + bCalf;
        float hipY = b.Bones["thigh_l"].position.y;
        Check(Math.Abs(AnkleY(b,"l") - (0.20f + FighterIK.AnkleHeight)) < 5e-3f,
              "the foot on the step rises to it (" + AnkleY(b,"l").ToString("0.0000") + ")");
        Check(Math.Abs(Len(b,"thigh_l","calf_l") - bThigh) < 1e-3f, "and the thigh keeps its length doing it");
        // The other foot's ground is 0.20 m under the root: the controller rode
        // up onto the step, and the legs rest straight, so that floor is out
        // of reach by exactly the step. Until 2026-11-09 the low leg hung at
        // full extension over it; now the hips come down to the lower foot
        // (FighterIK.HipDrop) and the leg on the step bends.
        Check(Math.Abs(AnkleY(b,"r") - FighterIK.AnkleHeight) < 5e-3f,
              "the hips come down and the low foot stands on the floor (" + AnkleY(b,"r").ToString("0.0000") + ")");
        Check(Math.Abs(hipY - (rootY + 0.952f - 0.20f)) < 5e-3f,
              "the hips are lower by the step (" + hipY.ToString("0.000") + " m)");
        float highReach = (b.Bones["thigh_l"].position - b.Bones["foot_l"].position).magnitude;
        Check(highReach < legSpan - 0.05f,
              "and the leg on the step bends its knee (" + highReach.ToString("0.000") + " m of a " + legSpan.ToString("0.000") + " m leg)");
        Check(Math.Abs(Len(b,"thigh_r","calf_r") - bThigh) < 1e-3f && Math.Abs(Len(b,"calf_r","foot_r") - bCalf) < 1e-3f,
              "the low leg keeps its lengths");
        Console.WriteLine("  standing on a 0.20 m step: root rides to " + rootY.ToString("0.00")
            + " m, the hips come down " + (rootY + 0.952f - hipY).ToString("0.00") + " m,");
        Console.WriteLine("  the low foot stands on the floor and the leg on the step bends.");

        // --------------------------------------------- the crowd, the real one
        Console.WriteLine("\nCROWD");
        Scene.Reset();
        Slab("Ground", new Vector3(0f, -0.5f, 0f), new Vector3(200f, 1f, 200f));
        // The hazard is narrower than I claimed when I fixed it, and this is
        // the check that establishes how narrow. A foot ray is vertical and
        // starts 0.67 m above the fighter's own feet. Another fighter's
        // capsule runs the full 1.8 m from theirs, so on level ground the ray
        // either misses them horizontally or starts inside them -- and a ray
        // that starts inside a collider reports nothing. Sweep the spacings
        // and none of them puts a fighter in the path.
        int worstOnLevel = 0;
        for (int step = 0; step < 12; step++) {
            float gap = 0.05f + step * 0.05f;
            Scene.Reset();
            Slab("Ground", new Vector3(0f, -0.5f, 0f), new Vector3(200f, 1f, 200f));
            Rig mid = BuildFighter("Ahmed", Vector3.zero);
            BuildFighter("Other", new Vector3(gap, 0f, 0f));
            Scene.Step(4);
            RaycastHit[] probe = new RaycastHit[8];
            Vector3 from = new Vector3(0.082f, 0.670f, 0f);
            int hit = Physics.RaycastNonAlloc(from, Vector3.down, probe, 1.6f);
            int fighters = 0;
            for (int i2 = 0; i2 < hit; i2++)
                if (probe[i2].collider.GetComponentInParent<Fighter>() != null) fighters++;
            worstOnLevel = Math.Max(worstOnLevel, fighters);
            Check(Math.Abs(AnkleY(mid, "l") - FighterIK.AnkleHeight) < 2e-3f,
                  "a fighter " + gap.ToString("0.00") + " m away changes nothing");
        }
        Check(worstOnLevel == 0,
              "on level ground a foot ray never reaches another fighter, at any spacing");
        Console.WriteLine("  twelve spacings from 0.05 to 0.60 m: the ray reached a fighter in none of them.");
        Console.WriteLine("  So the filter in GroundUnder is defensive, not a fix for a live bug -- it only");
        Console.WriteLine("  matters once a fighter can stand low enough for their head to break your floor,");
        Console.WriteLine("  and every district today is one flat slab.");

        // ------------------------------------------------- no drift over frames
        Console.WriteLine("\nSTEADINESS");
        Scene.Reset();
        Slab("Ground", new Vector3(0f, -0.5f, 0f), new Vector3(200f, 1f, 200f));
        Rig c = BuildFighter("Ahmed", Vector3.zero);
        Scene.Step(3);
        float settled = AnkleY(c, "l"); float settledLen = Len(c, "thigh_l", "calf_l");
        Scene.Step(400);
        Check(Math.Abs(AnkleY(c,"l") - settled) < 1e-4f, "400 frames later the foot has not drifted");
        Check(Math.Abs(Len(c,"thigh_l","calf_l") - settledLen) < 1e-4f, "and the thigh has not stretched");

        // the root moves and the pose follows it in the same frame
        c.Root.transform.position = new Vector3(6f, 0f, -4f);
        Scene.Step(1);
        Check(Math.Abs(AnkleY(c,"l") - FighterIK.AnkleHeight) < 2e-3f,
              "after the root moves, the feet are still on the ground that frame");

        // ---------------------------------------------------------------- guard
        Console.WriteLine("\nGUARD");
        Scene.Reset();
        Slab("Ground", new Vector3(0f, -0.5f, 0f), new Vector3(200f, 1f, 200f));
        Rig g = BuildFighter("Ahmed", Vector3.zero);
        Scene.Step(2);
        float restL = g.Bones["hand_l"].position.y, upperLen = Len(g, "upperarm_l", "lowerarm_l");
        g.Fighter.Blocking = true;
        Scene.Step(30);                                   // half a second
        float upL = g.Bones["hand_l"].position.y, upR = g.Bones["hand_r"].position.y;
        Check(upL > restL + 0.15f, "blocking lifts the left hand (" + restL.ToString("0.00") + " -> " + upL.ToString("0.00") + ")");
        Check(Math.Abs(upL - FighterIK.GuardHeight) < 0.05f, "to about chin height");
        Check(Math.Abs(upL - upR) < 1e-3f, "both hands to the same height");
        // Hurt, the same guard is carried lower. It is the only thing in the
        // world that says how much an enemy has left. The rig carries no
        // vitals of its own, so it is given a thug's before it is hurt.
        ((Ahmed.Combat.EnemyFighter)g.Fighter).ConfigureFrom(
            new Ahmed.Data.FighterRow { name = "Thug", maxHealth = 46f, moves = new string[] { "Jab" } },
            0, 1f, 1f);
        Scene.Step(2);
        upL = g.Bones["hand_l"].position.y;
        g.Fighter.SetCondition(g.Fighter.MaxHealth * 0.15f, g.Fighter.MaxStamina);
        Scene.Step(2);
        float hurtL = g.Bones["hand_l"].position.y;
        Check(hurtL < upL - 0.02f, "a hurt fighter carries the guard lower ("
              + upL.ToString("0.00") + " -> " + hurtL.ToString("0.00") + ")");
        g.Fighter.SetCondition(g.Fighter.MaxHealth, g.Fighter.MaxStamina);
        Scene.Step(2);
        // Facing defaults to +X, not +Z, so "in front" is along the facing.
        Vector3 ahead = g.Fighter.Facing;
        float reach = Vector3.Dot(g.Bones["hand_l"].position - g.Root.transform.position, ahead);
        Check(reach > 0.15f, "and in front of him along his facing (" + reach.ToString("0.00") + " m)");
        Check(Math.Abs(Len(g,"upperarm_l","lowerarm_l") - upperLen) < 1e-3f, "the upper arm keeps its length in the guard");
        g.Fighter.Blocking = false;
        Scene.Step(30);
        Check(Math.Abs(g.Bones["hand_l"].position.y - restL) < 1e-3f, "dropping the guard returns the hand to rest");

        // ------------------------------------------------- 2026-11-10: the man's size
        Console.WriteLine("\nSIZE");
        foreach (float size in new[] { 0.94f, 1.26f, 1.55f }) {
            Scene.Reset();
            Slab("Ground", new Vector3(0f, -0.5f, 0f), new Vector3(200f, 1f, 200f));
            Rig z = BuildFighter("Man", Vector3.zero, size);
            Scene.Step(4);
            string tag = " (a man " + size.ToString("0.00") + " of Ahmed's size)";
            Check(Math.Abs(AnkleY(z, "l") - FighterIK.AnkleHeight * size) < 2e-3f && Math.Abs(AnkleY(z, "r") - FighterIK.AnkleHeight * size) < 2e-3f,
                  "standing on flat ground his ankles keep their own height, " + (AnkleY(z, "l") * 100).ToString("0.00") + " cm" + tag);
            Check(Math.Abs(z.Bones["thigh_l"].position.y - 0.952f * size) < 1e-3f, "and his hips do not sink" + tag);
            float rest = z.Bones["hand_l"].position.y;
            z.Fighter.Blocking = true;
            Scene.Step(30);
            float up = z.Bones["hand_l"].position.y, fwd = Vector3.Dot(z.Bones["hand_l"].position, z.Fighter.Facing);
            Check(Math.Abs(up - FighterIK.GuardHeight * size) < 0.05f && up > rest + 0.15f,
                  "his guard comes up to his own chin, " + up.ToString("0.00") + " m" + tag);
            Check(Math.Abs(fwd - FighterIK.GuardForward * size) < 0.03f, "and as far in front of him as he is big" + tag);
            Console.WriteLine("  " + size.ToString("0.00") + ": ankles at " + (AnkleY(z, "l") * 100).ToString("0.0") + " cm, the guard at " + up.ToString("0.00") + " m");
        }
        {
            // the hold's distances are his: carried 15 cm, Ahmed's foot steps after him, a giant's stays
            float[] moved = new float[2];
            for (int k = 0; k < 2; k++) {
                float size = k == 0 ? 1f : 1.55f;
                Scene.Reset();
                Slab("Ground", new Vector3(0f, -0.5f, 0f), new Vector3(200f, 1f, 200f));
                Rig z = BuildFighter("Man", Vector3.zero, size);
                Scene.Step(4);
                Vector3 was = z.Bones["foot_l"].position;
                z.Root.transform.position = new Vector3(0f, 0f, 0.15f);
                Scene.Step(6);                                // 0.1 s: a step has begun if it is going to
                moved[k] = (z.Bones["foot_l"].position - was).magnitude;
            }
            Check(moved[0] > 0.02f && moved[1] < 0.005f,
                  "carried 15 cm, Ahmed's foot steps after him and a man half again his size keeps his (" + (moved[0] * 100).ToString("0.0") + " and " + (moved[1] * 100).ToString("0.0") + " cm)");
        }

        // ------------------------------------- 2026-11-10: a held foot is on the floor
        Console.WriteLine("\nWALK");
        float worstOff = 0f, worstSlide = 0f, worstBob = 0f;
        foreach (float size in new[] { 1f, 0.94f, 1.55f })
        foreach (float hz in new[] { 30f, 60f, 120f })
        foreach (float speed in new[] { 1.0f, 2.5f, 3.408f }) {
            Scene.Reset(); Scene.DeltaTime = 1f / hz;
            Slab("Ground", new Vector3(0f, -0.5f, 0f), new Vector3(400f, 1f, 400f));
            Rig w = BuildFighter("Man", Vector3.zero, size);
            Scene.Step(4);
            float ankle = FighterIK.AnkleHeight * size, lo = 1e9f, hi = -1e9f;
            Vector3[] last = { w.Bones["foot_l"].position, w.Bones["foot_r"].position };
            bool[] down = { true, true };
            for (int i = 0; i < (int)(3f * hz); i++) {
                w.Root.transform.position = w.Root.transform.position + new Vector3(0f, 0f, speed / hz);
                Scene.Step(1);
                for (int f = 0; f < 2; f++) {
                    Vector3 at = w.Bones[f == 0 ? "foot_l" : "foot_r"].position;
                    float along = (float)Math.Sqrt((at.x - last[f].x) * (at.x - last[f].x) + (at.z - last[f].z) * (at.z - last[f].z));
                    bool still = along < 5e-4f;                           // not carried along the ground this frame: held
                    if (still) worstOff = Math.Max(worstOff, Math.Abs(at.y - ankle) / size);
                    bool onFloor = Math.Abs(at.y - ankle) < 1e-3f;
                    if (onFloor && down[f] && along < 0.02f) worstSlide = Math.Max(worstSlide, along / size);   // on the floor two frames running, and not the frame it landed
                    down[f] = onFloor; last[f] = at;
                }
                if (i > hz) { float hip = w.Bones["thigh_l"].position.y; lo = Math.Min(lo, hip); hi = Math.Max(hi, hip); }
            }
            if (hz == 60f) worstBob = Math.Max(worstBob, (hi - lo) / size);
        }
        Scene.DeltaTime = 1f / 60f;
        Console.WriteLine("  walking and running 1.0-3.4 m/s at 30, 60 and 120 Hz, three sizes: a held foot is " + (worstOff * 100).ToString("0.00")
            + " cm off the floor at worst, slides " + (worstSlide * 100).ToString("0.00") + " cm; the hips bob " + (worstBob * 100).ToString("0.0") + " cm at 60 Hz");
        Check(worstOff < 0.005f, "walking, a foot that is held is on the floor");
        Check(worstSlide < 0.002f, "and does not slide while it is there");
        Check(worstBob < 0.016f, "and the hips do not bob with every step (under 1.6 cm at 60 Hz)");

        // ---------------------------------------------- 2026-11-10: the settle
        Console.WriteLine("\nSETTLE");
        Scene.Reset();
        Slab("Ground", new Vector3(0f, -0.5f, 0f), new Vector3(200f, 1f, 200f));
        Rig st = BuildFighter("Ahmed", Vector3.zero);
        Scene.Step(4);
        st.Root.transform.position = new Vector3(0.08f, 0f, 0f);          // carried 8 cm: under the step's 12, so both feet stay
        Scene.Step(6);
        float leftBehind = Math.Abs(st.Bones["foot_l"].position.x - (0.082f + 0.08f));
        Scene.Step(60);
        float offL = Math.Abs(st.Bones["foot_l"].position.x - (0.082f + 0.08f)), offR = Math.Abs(st.Bones["foot_r"].position.x - (-0.082f + 0.08f));
        Check(leftBehind > 0.07f, "carried 8 cm, his feet stay where they were planted (" + (leftBehind * 100).ToString("0.0") + " cm behind)");
        Check(offL < 0.005f && offR < 0.005f && Math.Abs(AnkleY(st, "l") - FighterIK.AnkleHeight) < 2e-3f,
              "and a second later both have stepped back under him (" + (offL * 100).ToString("0.0") + " and " + (offR * 100).ToString("0.0") + " cm off)");

        Console.WriteLine(fails == 0 ? "\nall pose checks passed" : "\n" + fails + " FAILURES");
        return fails == 0 ? 0 : 1;
    }
}
