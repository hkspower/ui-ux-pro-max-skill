// Drives FighterIK through a real skeleton in a real scene: bones parented to
// bones, a ground to raycast against, and Unity's own call order. Everything
// here was out of reach of a pure test -- Apply's rotation composition, the
// foot ray, the crowd filter, and whether a pose accumulates over frames.
using System; using System.Collections.Generic; using UnityEngine;
using Ahmed.Combat; using Ahmed.Data;

// Where PlayerFighter.ReadInput sits in a frame: after Fighter.Update's own tick
// (order 0), before Fighter.LateUpdate and FighterIK.LateUpdate (order 100). It
// does what ReadInput does with a held block, a pressed strike and a held stick.
[DefaultExecutionOrder(50)]
public class StrikePad : MonoBehaviour {
    public Fighter F; public bool HoldBlock, Walk; public string Press; public float Speed = 3.408f;
    public Vector3 Way = Vector3.forward;
    public float HitAt = -1f; public bool Struck;
    // the stick held along Way: every frame he is free he is faced along it, as ReadInput faces him
    // (FaceTowards(position + wish)); a press that frame is thrown that way, as Punch faces the man first
    public bool Turn;
    void Update() {
        F.Blocking = HoldBlock && !F.IsBusy;
        if (!F.IsBusy) {
            if (Turn) F.FaceTowards(transform.position + Way);
            if (Press != null) { F.StartAttack(Press); Press = null; }
            else if (Walk) { transform.position = transform.position + Way * (Speed * Time.deltaTime); }
        }
        // a blow taken in the middle of his own swing: the push and the hit stop, as ReceiveHit gives them
        if (HitAt >= 0f && !Struck && F.State == FighterState.Attack && F.AttackTime >= HitAt) {
            Struck = true;
            F.ReceiveKnockback(-Way * 3f, false);
            F.Freeze(0.075f);
        }
    }
}

// A fighter whose opponents are handed to it: the harness has no player for
// EnemyFighter.GatherTargets to find. Everything else is the real EnemyFighter,
// so the real Fighter.ResolveHits sweeps the same list the IK reads.
public class AimFighter : EnemyFighter {
    public List<Fighter> Them = new List<Fighter>();
    public override void GatherTargets(List<Fighter> into) { for (int i = 0; i < Them.Count; i++) into.Add(Them[i]); }
}

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
    static Rig BuildFighter(string name, Vector3 at, float size) { return BuildFighter(name, at, size, 1f); }

    // size: the man against Ahmed. The bones stand at their scaled places and the root
    // is left unscaled, as EnemyFighter.SetStature leaves it (it scales the Mesh child
    // and the controller); the harness's Transform does not compose a parent's scale.
    // leftX: which side of the root the _l bones stand on. +1 is this suite's fixture as it
    // always was; -1 is the other. Which the real mesh imports as cannot be settled without
    // the engine (the generator's left is Blender's +X, and the axes change hand on the way).
    static Rig BuildFighter(string name, Vector3 at, float size, float leftX, bool aims = false, bool head = false) {
        GameObject go = new GameObject(name);
        go.transform.position = at;
        CharacterController body = go.AddComponent<CharacterController>();
        body.height = 1.8f * size; body.radius = 0.32f * size; body.center = new Vector3(0f, 0.9f * size, 0f);

        GameObject mesh = new GameObject("Mesh");
        mesh.transform.SetParent(go.transform, false);

        Rig r = new Rig(); r.Root = go;
        for (int side = 0; side < 2; side++) {
            float sign = side == 0 ? leftX : -leftX; string suffix = side == 0 ? "_l" : "_r";
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
        if (head) {
            // the look's two bones, and a marker a hand's width before each to read its facing off
            string[] names = { "neck_01", "throat", "head", "nose" };
            Vector3[] at4 = { new Vector3(0f, 1.53f, 0f), new Vector3(0f, 1.53f, 0.1f), new Vector3(0f, 1.672f, 0f), new Vector3(0f, 1.672f, 0.1f) };
            for (int i = 0; i < 4; i++) {
                GameObject b = new GameObject(names[i]);
                b.transform.SetParent(i == 0 ? mesh.transform : i == 2 ? r.Bones["neck_01"] : r.Bones[names[i - 1]], false);
                b.transform.position = at4[i] * size + at;
                r.Bones[names[i]] = b.transform;
            }
        }
        r.Fighter = aims ? go.AddComponent<AimFighter>() : go.AddComponent<EnemyFighter>();
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

    // ------------------------------------------------------------ 2026-11-10: strikes
    // The attack rows, read from the game's own attacks.json into GameData (the suites
    // had never run a strike through the skeleton).
    static void LoadRows() {
        GameData.Load();
        var d = (Dictionary<string, AttackRow>)typeof(GameData).GetField("_attacks",
            System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.NonPublic).GetValue(null);
        string text = System.IO.File.ReadAllText("Assets/Resources/Data/attacks.json");
        foreach (System.Text.RegularExpressions.Match item in System.Text.RegularExpressions.Regex.Matches(text, "\\{[^{}]*\"name\"[^{}]*\\}")) {
            AttackRow r = new AttackRow();
            foreach (System.Text.RegularExpressions.Match kv in System.Text.RegularExpressions.Regex.Matches(item.Value, "\"(\\w+)\"\\s*:\\s*(\"[^\"]*\"|[\\w.]+)")) {
                string k = kv.Groups[1].Value, v = kv.Groups[2].Value.Trim('"');
                System.Reflection.FieldInfo f = typeof(AttackRow).GetField(k); if (f == null) continue;
                if (f.FieldType == typeof(float)) f.SetValue(r, float.Parse(v, System.Globalization.CultureInfo.InvariantCulture));
                else if (f.FieldType == typeof(bool)) f.SetValue(r, v == "true");
                else f.SetValue(r, v);
            }
            r.Resolve(); d[r.name] = r;
        }
    }

    // A man on a flat slab facing +Z, with a pad. leftX as BuildFighter's: with +1 (the
    // fixture as written) the guard sends each fist across to the other side; with -1 it
    // does not. Both are run where the layout could matter.
    static Rig Fighter(float hz, out StrikePad pad) { return Fighter(hz, out pad, 1f); }
    static Rig Fighter(float hz, out StrikePad pad, float leftX) {
        Scene.Reset(); Scene.DeltaTime = 1f / hz;
        Slab("Ground", new Vector3(0f, -0.5f, 0f), new Vector3(2000f, 1f, 2000f));
        Rig r = BuildFighter("Ahmed", Vector3.zero, 1f, leftX);
        pad = r.Root.AddComponent<StrikePad>(); pad.F = r.Fighter; pad.Way = new Vector3(0f, 0f, 1f);
        typeof(Fighter).GetMethod("InitialiseVitals", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)
            .Invoke(r.Fighter, new object[] { 100f, 9999f });
        r.Fighter.FaceTowards(new Vector3(0f, 0f, 10f));
        Scene.Step(4);
        return r;
    }

    static string StrikeBone(string row) {
        return row == "Jab" || row == "Hook" ? "hand_l" : row == "Kick" || row == "Knee" ? "foot_r" : "hand_r";
    }

    // the largest move of the striking limb's end in one frame over a strike; first: on the frame it starts
    static float Throw(float hz, string row, bool fromGuard, float hitAt, out float first, out float frozenMove, out float whole) {
        return Throw(hz, row, fromGuard, hitAt, out first, out frozenMove, out whole, 1f);
    }
    static float Throw(float hz, string row, bool fromGuard, float hitAt, out float first, out float frozenMove, out float whole, float leftX) {
        StrikePad pad; Rig r = Fighter(hz, out pad, leftX);
        string bone = StrikeBone(row);
        if (fromGuard) { pad.HoldBlock = true; Scene.Step((int)Math.Round(hz * 0.5f)); }
        else Scene.Step((int)Math.Round(hz * 0.1f));
        AttackRow a = GameData.Attack(row);
        pad.Press = row; pad.HitAt = hitAt;
        Vector3 prev = r.Bones[bone].position, atHit = prev, home = prev;
        float worst = 0f; first = 0f; frozenMove = 0f; whole = 0f;
        int n = (int)Math.Ceiling((a.startup + a.active + a.recovery) * hz) + (int)Math.Round(hz * 0.5f);
        bool wasStruck = false;
        for (int i = 1; i <= n; i++) {
            Scene.Step();
            Vector3 q = r.Bones[bone].position; float d = (q - prev).magnitude;
            if (hitAt < 0f) { worst = Math.Max(worst, d); if (i == 1) first = d; }
            else if (pad.Struck) {
                if (!wasStruck) { atHit = prev; wasStruck = true; }
                if (r.Fighter.Frozen) frozenMove = Math.Max(frozenMove, (q - atHit).magnitude);
                worst = Math.Max(worst, d);
                home = q;
            }
            prev = q;
        }
        if (hitAt >= 0f) whole = (home - atHit).magnitude;
        return worst;
    }

    // A swing thrown facing +Z with the stick held `deg` round while it lasts: he is turned on the first
    // frame he is free. The furthest the swing's hand is from its rest place in the drawn body's own frame
    // (the Mesh child's), from the swing's last frame for 0.25 s. ankles: the nearest the two come in that time.
    static float EndsInto(string row, float deg, float hz, float leftX, out float ankles) {
        StrikePad pad; Rig r = Fighter(hz, out pad, leftX);
        Scene.Step((int)Math.Round(hz * 0.1f));
        Transform body = r.Root.transform.Find("Mesh"), hand = r.Bones[StrikeBone(row)];
        Vector3 rest = body.InverseTransformPoint(hand.position);
        pad.Press = row; Scene.Step();
        float rad = deg * Mathf.Deg2Rad;
        pad.Way = new Vector3(Mathf.Sin(rad), 0f, Mathf.Cos(rad)); pad.Turn = deg != 0f;
        float worst = 0f; int after = 0, most = (int)Math.Round(hz * 0.25f);
        ankles = 1f;
        for (int i = 0; i < 400 && after <= most; i++) {
            Scene.Step();
            if (after == 0 && r.Fighter.State == FighterState.Attack) continue;
            worst = Math.Max(worst, (body.InverseTransformPoint(hand.position) - rest).magnitude); after++;
            Vector3 apart = r.Bones["foot_l"].position - r.Bones["foot_r"].position; apart.y = 0f;
            ankles = Math.Min(ankles, apart.magnitude);
        }
        return worst;
    }

    static void Vitals(Rig r, float health = 1000f) {
        typeof(Fighter).GetMethod("InitialiseVitals", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)
            .Invoke(r.Fighter, new object[] { health, 9999f });
    }

    // A striker of his own size at the origin facing +Z, and (hisSize > 0) a man standing at `at`.
    // The row is thrown and the scene stepped to its first active frame: the frame the blow lands.
    // leftX: the striker's layout, as BuildFighter's. also: a second man, after the first in the
    // striker's list (the fight's sweep takes the first). hisHealth: the first man's. guards: he
    // faces the striker with his guard up, so the blow is blocked.
    static Rig Land(string row, float mySize, Vector3 at, float hisSize, out Rig him, float leftX = 1f, Vector3? also = null, float hisHealth = 1000f, bool guards = false) {
        Scene.Reset(); Scene.DeltaTime = 1f / 60f;
        Slab("Ground", new Vector3(0f, -0.5f, 0f), new Vector3(2000f, 1f, 2000f));
        Rig r = BuildFighter("Striker", Vector3.zero, mySize, leftX, true);
        StrikePad pad = r.Root.AddComponent<StrikePad>(); pad.F = r.Fighter;
        Vitals(r);
        r.Fighter.FaceTowards(new Vector3(0f, 0f, 10f));
        him = null;
        if (hisSize > 0f) {
            him = BuildFighter("Him", at, hisSize);
            Vitals(him, hisHealth);
            if (guards) { him.Fighter.FaceTowards(Vector3.zero); him.Fighter.Blocking = true; }
            ((AimFighter)r.Fighter).Them.Add(him.Fighter);
        }
        if (also.HasValue) {
            Rig other = BuildFighter("Other", also.Value, 1f);
            Vitals(other);
            ((AimFighter)r.Fighter).Them.Add(other.Fighter);
        }
        Scene.Step(6);
        pad.Press = row;
        AttackRow a = GameData.Attack(row);
        for (int i = 0; i < 200 && !(r.Fighter.State == FighterState.Attack && r.Fighter.AttackTime >= a.startup); i++) Scene.Step();
        return r;
    }

    static float FlatAngle(Vector3 a, Vector3 b) { return Vector3.Angle(new Vector3(a.x, 0f, a.z), new Vector3(b.x, 0f, b.z)); }

    static void Aim() {
        Console.WriteLine("\nAIM");
        // ---- pure: the mark, the gate, the aim, the knee
        bool marks = true, knees = true;
        foreach (float size in new[] { 0.94f, 1f, 1.24f, 1.55f }) {
            Vector3 man = new Vector3(0.3f, 0.2f, 1.1f);
            Vector3 m = FighterIK.StrikeMark(Vector3.zero, man, size, FighterIK.ShoulderHeight, FighterIK.KnuckleSkin);
            Vector3 flat = new Vector3(man.x - m.x, 0f, man.z - m.z);
            if (Math.Abs(flat.magnitude - (FighterIK.FrontDepth * size + FighterIK.KnuckleSkin)) > 1e-4f) marks = false;      // on his front, a skin short
            if (FlatAngle(flat, man) > 0.1f) marks = false;                                                                // on the striker's side of him
            if (Math.Abs(m.y - (man.y + FighterIK.ShoulderHeight * size)) > 1e-4f) marks = false;                          // at the height on HIS body
            // the knee: a thigh from the hip; up his front when he is nearer than a thigh, never past it
            float thigh = 0.439f * size; Vector3 hip = new Vector3(0.09f, 0.952f * size, 0f);
            foreach (float dist in new[] { 0.25f, 0.40f, 0.70f, 0.90f }) {
                Vector3 mark = FighterIK.StrikeMark(Vector3.zero, new Vector3(0f, 0f, dist * size), size, FighterIK.KneeMarkHeight, FighterIK.KneeSkin * size);
                Vector3 k = FighterIK.KneeTarget(hip, mark, thigh);
                if (Math.Abs((k - hip).magnitude - thigh) > 1e-4f) knees = false;
                if (k.z > mark.z + 1e-4f) knees = false;
                Vector3 toMark = mark - hip;
                if (toMark.magnitude < thigh && (Math.Abs(k.z - mark.z) > 1e-4f || k.y < mark.y)) knees = false;
            }
        }
        Check(marks, "a blow's mark is on the man's front, on the striker's side of him, at the height on his own body, a skin short (sizes 0.94 to 1.55)");
        Check(knees, "a knee's joint goes a thigh from the hip toward the mark, and up his front over it when he is nearer than a thigh: never past his front");
        {
            Vector3 root = new Vector3(0.18f, 1.44f, 0f), line = new Vector3(0f, 1.44f, 1.3f);
            Func<float, Vector3> at = deg => root + new Vector3(Mathf.Sin(deg * Mathf.Deg2Rad), 0f, Mathf.Cos(deg * Mathf.Deg2Rad));
            float off = FlatAngle(line - root, Vector3.forward);     // the row's own line is not quite the facing: it starts at the shoulder
            Func<float, bool, float> gate = (deg, arm) => FighterIK.AimGate(root, line, at(deg - off), arm);
            Check(gate(0f, true) == 1f && gate(29f, true) == 1f && gate(56f, true) == 0f && gate(42f, true) > 0.2f && gate(42f, true) < 0.8f
                  && gate(59f, false) == 1f && gate(91f, false) == 0f && gate(75f, false) > 0.2f && gate(75f, false) < 0.8f,
                  "a limb is swung to the man wholly inside 30 degrees of its own line and not at all past 55 (an arm), 60 and 90 (a leg)");
            Vector3 mark = root + new Vector3(0.3f, 0.1f, 0.7f);
            Vector3 aimed = FighterIK.StrikeAim(root, line, mark, 1f);
            Check((FighterIK.StrikeAim(root, line, mark, 0f) - line).magnitude < 1e-6f && (aimed - mark).magnitude < 1e-4f
                  && (FighterIK.StrikeAim(root, line, root + (mark - root) * 5f, 1f) - root).magnitude <= (line - root).magnitude + 1e-4f,
                  "the aimed limb goes to the mark and no further; a mark past the row's reach is aimed at, not stretched to; no gate, the row's own line");
        }

        // ---- the knee, through the rig
        Rig him; Rig r;
        foreach (float dist in new[] { 0.70f, 0.90f }) {
            r = Land("Knee", 1f, new Vector3(0f, 0f, dist), 1f, out him);
            Vector3 hipJ = r.Bones["thigh_r"].position, kneeJ = r.Bones["calf_r"].position, ank = r.Bones["foot_r"].position;
            float bend = Vector3.Angle(hipJ - kneeJ, ank - kneeJ);
            float front = dist - FighterIK.FrontDepth;
            Console.WriteLine("  a knee at a man " + dist.ToString("0.00") + " m ahead: the knee joint is bent " + bend.ToString("0") + " degrees, "
                + ((front - kneeJ.z) * 100).ToString("0.0") + " cm short of his front, " + ((kneeJ.z - ank.z) * 100).ToString("0.0") + " cm ahead of the ankle at "
                + (kneeJ.y * 100).ToString("0") + " cm up");
            Check(bend < 120f && kneeJ.z > ank.z + 0.02f, "a knee lands the knee, bent, ahead of the foot (" + dist.ToString("0.00") + " m)");
            Check(kneeJ.z < front + 1e-3f && ank.z < front + 1e-3f, "...and nothing of the leg passes his front (" + dist.ToString("0.00") + " m)");
            Check(Math.Abs((hipJ - kneeJ).magnitude - 0.439f) < 2e-3f && Math.Abs((kneeJ - ank).magnitude - 0.443f) < 2e-3f, "...the thigh and the shin keep their lengths (" + dist.ToString("0.00") + " m)");
        }
        r = Land("Knee", 1f, Vector3.zero, 0f, out him);
        {
            Vector3 hipJ = r.Bones["thigh_r"].position, kneeJ = r.Bones["calf_r"].position, ank = r.Bones["foot_r"].position;
            float rise = Mathf.Atan2(kneeJ.y - hipJ.y, kneeJ.z - hipJ.z) * Mathf.Rad2Deg;
            Check(Vector3.Angle(hipJ - kneeJ, ank - kneeJ) < 120f && Math.Abs(rise - FighterIK.KneeRaiseDegrees) < 1f && Math.Abs(kneeJ.x - hipJ.x) < 1e-3f,
                  "with nobody there the knee is thrown up the facing line, bent (" + rise.ToString("0.0") + " degrees above level)");
        }

        // ---- a kick stops on him; with room, it still locks out
        r = Land("Kick", 1f, new Vector3(0f, 0f, 0.90f), 1f, out him);
        {
            float front = 0.90f - FighterIK.FrontDepth, ankZ = r.Bones["foot_r"].position.z;
            Console.WriteLine("  a kick at a man 0.90 m ahead: the ankle is " + ((front - ankZ) * 100).ToString("0.0") + " cm short of his front");
            Check(ankZ < front + 1e-3f && ankZ > front - 0.05f, "a kick at a man inside its reach stops on his front, not through him");
        }
        r = Land("Kick", 1f, new Vector3(0f, 0f, 1.40f), 1f, out him);
        Check(Vector3.Angle(r.Bones["thigh_r"].position - r.Bones["calf_r"].position, r.Bones["foot_r"].position - r.Bones["calf_r"].position) > 170f,
              "...and a kick at a man further than the leg still locks out");
        {
            // A kick that stops on his front lands on a bent leg (2026-11-11): which way the knee goes. On
            // the kneecap's side of the leg's own line -- that line turned a quarter in his fore-and-aft
            // plane: up, for a leg held level -- wherever the man stands. The pole was a point straight ahead
            // of the hip, which such a kick points at: the knee folded level and sideways (22 cm), swapped
            // side (44.6 cm) for 2 cm of where the man stood, and against a taller man bent backward (23.8).
            // Men 20 cm either side and dead ahead, a taller man, the biggest from as near as two controllers
            // allow (0.82 m: the leg rises 40 degrees, where a pole merely lifted 0.6 m leaves the knee 14.7 cm
            // across), and the two places the swap lay between.
            bool bent = true; float leastOn = 1f, mostAcross = 0f, swap = 0f, upAhead = 0f;
            foreach (float leftX in new[] { 1f, -1f }) {
                float side = -leftX;                                     // the side of him his kicking hip is on
                float[][] men = { new[] { -0.20f, 0.90f, 1f }, new[] { 0f, 0.90f, 1f }, new[] { 0.20f, 0.90f, 1f }, new[] { 0f, 0.85f, 1.26f },
                                  new[] { 0f, 0.82f, 1.55f }, new[] { 0.10f * side, 0.90f, 1f }, new[] { 0.12f * side, 0.90f, 1f } };
                Vector3 kneeWas = Vector3.zero;
                for (int i = 0; i < men.Length; i++) {
                    r = Land("Kick", 1f, new Vector3(men[i][0], 0f, men[i][1]), men[i][2], out him, leftX);
                    Vector3 hipJ = r.Bones["thigh_r"].position, kneeJ = r.Bones["calf_r"].position, ank = r.Bones["foot_r"].position;
                    Vector3 line = (ank - hipJ).normalized, off = (kneeJ - hipJ) - line * Vector3.Dot(kneeJ - hipJ, line);
                    Vector3 cap = Vector3.Cross(line, Vector3.Cross(Vector3.up, r.Fighter.Facing)).normalized;
                    float on = Vector3.Dot(off, cap), across = (off - cap * on).magnitude;
                    leastOn = Math.Min(leastOn, on); mostAcross = Math.Max(mostAcross, across);
                    if (Vector3.Angle(hipJ - kneeJ, ank - kneeJ) > 165f) bent = false;
                    if (i == 1 && leftX > 0f) upAhead = kneeJ.y - hipJ.y;
                    if (i == men.Length - 1) swap = Math.Max(swap, (kneeJ - kneeWas).magnitude);
                    kneeWas = kneeJ;
                }
            }
            Console.WriteLine("  ...on a bent leg: the knee is " + (upAhead * 100).ToString("0.0") + " cm over the hip; over seven men and both layouts it is " + (leastOn * 100).ToString("0.0")
                + " cm at least on the kneecap's side of the leg's line, " + (mostAcross * 100).ToString("0.0") + " cm at most across it, and moves " + (swap * 100).ToString("0.0")
                + " cm for 2 cm of where the man stands");
            Check(bent && leastOn > 0.10f && mostAcross < 0.08f, "a kick that stops on a man's front bends its knee to the kneecap's side of the leg's line, not across it and not backward (over 10 cm there, under 8 across)");
            Check(swap < 0.03f, "...and the knee does not swap side for 2 cm of where the man stands (under 3 cm between a man 10 and 12 cm to the kicking side)");
        }

        // ---- a punch goes to the man it lands on
        r = Land("Hook", 1f, new Vector3(0.48f, 0f, 1.11f), 1f, out him);
        {
            Vector3 sh = r.Bones["upperarm_l"].position, wr = r.Bones["hand_l"].position;
            Vector3 mark = FighterIK.StrikeMark(Vector3.zero, him.Root.transform.position, 1f, FighterIK.ShoulderHeight, FighterIK.KnuckleSkin);
            float off = FlatAngle(wr - sh, mark - sh);
            Console.WriteLine("  a hook at a man 0.48 m off the line at 1.11 m: the arm is " + off.ToString("0.0") + " degrees off the line to him (it was "
                + FlatAngle(new Vector3(0f, 0f, 1.344f) - new Vector3(sh.x, 0f, sh.z), mark - sh).ToString("0.0") + " down the facing line)");
            Check(off < 3f, "a punch at a man off the facing line goes to him: the arm within 3 degrees of the line to his front");
        }
        {
            // nobody in the box, a man outside it, and a man past the gate: the row's own line, to a tenth of a millimetre
            // (against his own shoulder: the blow that lands stops the striker's lunge for the hit stop,
            // so his root stands 2.75 cm short of where a miss carries it)
            Func<Rig, Vector3> arm = g => g.Bones["hand_l"].position - g.Bones["upperarm_l"].position;
            Vector3 none = arm(Land("Hook", 1f, Vector3.zero, 0f, out him));
            Vector3 far = arm(Land("Hook", 1f, new Vector3(0f, 0f, 5f), 1f, out him));
            Vector3 wide = arm(Land("Hook", 1f, new Vector3(0.75f, 0f, 0.45f), 1f, out him));
            Vector3 near = arm(Land("Hook", 1f, new Vector3(0.48f, 0f, 1.11f), 1f, out him));
            Check((none - far).magnitude < 1e-4f, "with nobody in the row's box the arm is where the row alone has it");
            Check(FlatAngle(none, wide) < 0.5f && FlatAngle(none, near) > 15f, "a man in the box but more than 55 degrees off the arm's line is not struck round the body ("
                  + FlatAngle(none, wide).ToString("0.00") + " degrees off the row's line; " + FlatAngle(none, near).ToString("0.0") + " for the man it does go to)");
        }
        {
            // the man is kept for the swing that lands on him, and forgotten by the next
            Rig g = Land("Hook", 1f, new Vector3(0.48f, 0f, 1.11f), 1f, out him);
            Vector3 struck = g.Bones["hand_l"].position - g.Bones["upperarm_l"].position;
            him.Root.transform.position = new Vector3(0f, 0f, 30f);            // the blow has sent him away
            Scene.Step(3);
            Vector3 after = g.Bones["hand_l"].position - g.Bones["upperarm_l"].position;
            Check(FlatAngle(struck, after) < 3f, "the limb stays on where it struck him for the rest of the swing, though the blow has sent him away");
            // the next hook is pressed during this one, so it starts on the frame this one ends:
            // the IK never sees him out of a swing between the two
            StrikePad again = g.Root.GetComponent<StrikePad>(); again.Press = "Hook";
            AttackRow hook = GameData.Attack("Hook");
            float clock = g.Fighter.AttackTime; bool second = false;
            for (int i = 0; i < 300; i++) {
                Scene.Step();
                if (g.Fighter.State == FighterState.Attack && g.Fighter.AttackTime < clock) second = true;
                clock = g.Fighter.AttackTime;
                if (second && g.Fighter.AttackTime >= hook.startup) break;
            }
            Vector3 next = g.Bones["hand_l"].position - g.Bones["upperarm_l"].position;
            Check(second && FlatAngle(next, struck) > 15f, "...and a new swing forgets him: with nobody there it goes down the row's own line");
        }
        {
            // Two men in the row's box (2026-11-11): the blow floors or kills the first the sweep takes, and
            // the limb stays on HIM. Only his place was kept, and a man down or dead was passed over: the
            // other man was taken in his stead, and on the contact frame the fist swung 43 degrees (44 cm) to
            // the man it had not hit -- the pose hit stop then held. A hook floors (the stub's Random.value
            // is 0; in the game 45 % of heavy blows); a jab at a man with 5 health kills, and he goes down;
            // a cross blocked by a man with 1 health kills him on his feet.
            float worst = 0f, worstNext = 0f; bool landed = true, nextLanded = true;
            Vector3 first = new Vector3(0.45f, 0f, 1.10f), other = new Vector3(-0.45f, 0f, 1.15f);
            foreach (float leftX in new[] { 1f, -1f })
                foreach (string row in new[] { "Hook", "Jab", "Cross" }) {
                    Rig g = Land(row, 1f, first, 1f, out him, leftX, other, row == "Jab" ? 5f : row == "Cross" ? 1f : 1000f, row == "Cross");
                    Fighter second = ((AimFighter)g.Fighter).Them[1];
                    AttackRow a = GameData.Attack(row);
                    if (him.Fighter.State != (row == "Cross" ? FighterState.Dead : FighterState.Down) || second.Health < 1000f || !g.Fighter.Frozen) landed = false;
                    // the contact frame, the hit stop, and every frame after it the arm is still wholly out
                    string hand = StrikeBone(row), arm = hand == "hand_l" ? "upperarm_l" : "upperarm_r";
                    for (int i = 0; i < 40 && g.Fighter.State == FighterState.Attack && g.Fighter.AttackTime < a.startup + a.active; i++) {
                        Vector3 sh = g.Bones[arm].position, wr = g.Bones[hand].position;
                        Vector3 mark = FighterIK.StrikeMark(g.Root.transform.position, first, 1f, FighterIK.ShoulderHeight, FighterIK.KnuckleSkin);
                        worst = Math.Max(worst, FlatAngle(wr - sh, mark - sh));
                        Scene.Step();
                    }
                    if (row != "Hook") continue;
                    // the next hook, pressed during this one: the man it floored is not kept past his own swing,
                    // and the sweep passes him over -- it lands on the other man, and the arm goes to him
                    g.Root.GetComponent<StrikePad>().Press = "Hook";
                    float clock = g.Fighter.AttackTime; bool began = false;
                    for (int i = 0; i < 300; i++) {
                        Scene.Step();
                        if (g.Fighter.State == FighterState.Attack && g.Fighter.AttackTime < clock) began = true;
                        clock = g.Fighter.AttackTime;
                        if (began && g.Fighter.AttackTime >= a.startup) break;
                    }
                    Vector3 toOther = FighterIK.StrikeMark(g.Root.transform.position, other, 1f, FighterIK.ShoulderHeight, FighterIK.KnuckleSkin) - g.Bones[arm].position;
                    worstNext = Math.Max(worstNext, FlatAngle(g.Bones[hand].position - g.Bones[arm].position, toOther));
                    if (!began || second.State != FighterState.Down) nextLanded = false;
                }
            Console.WriteLine("  two men in the box, the first floored or killed by the blow: the arm is " + worst.ToString("0.0")
                + " degrees at most off the line to where he stood, from the contact frame until it starts back; the next hook is " + worstNext.ToString("0.0") + " off the line to the other man");
            Check(landed && worst < 3f, "with two men in its box a blow that floors or kills the man it lands on stays on him: within 3 degrees of the line to where he stood, on the contact frame, through hit stop and while the arm is out");
            Check(nextLanded && worstNext < 3f, "...and the next swing goes to the next man: the one it floored is kept for his own swing and no longer");
        }
        {
            // sizes: each man throws at his own shoulder height; a punch at a bigger man goes up, at a smaller man down
            float big = Land("Jab", 1.55f, Vector3.zero, 0f, out him).Bones["hand_l"].position.y;
            float small = Land("Jab", 1f, Vector3.zero, 0f, out him).Bones["hand_l"].position.y;
            Check(Math.Abs(big - 1.442f * 1.55f) < 0.02f && Math.Abs(small - 1.442f) < 0.02f, "a man throws at his own shoulder height, whatever his size ("
                  + (big * 100).ToString("0") + " cm for a man of 1.55, " + (small * 100).ToString("0") + " for Ahmed)");
            Rig up = Land("Jab", 0.94f, new Vector3(0f, 0f, 1.2f), 1.55f, out him);
            Rig down = Land("Jab", 1.55f, new Vector3(0f, 0f, 1.2f), 0.94f, out him);
            Check(up.Bones["hand_l"].position.y > up.Bones["upperarm_l"].position.y + 0.15f && down.Bones["hand_l"].position.y < down.Bones["upperarm_l"].position.y - 0.15f,
                  "...a punch at a bigger man goes up to him, at a smaller man down");
        }
    }

    // Two men facing each other on a flat slab, each with a pad and each the other's opponent:
    // `a` at the origin facing +Z (his _r bones on his right), `b` at `at` facing him.
    static Rig Duel(Vector3 at, float sizeA, float sizeB, out Rig b, out StrikePad padA, out StrikePad padB, bool head = false, float leftX = -1f) {
        Scene.Reset(); Scene.DeltaTime = 1f / 60f;
        Slab("Ground", new Vector3(0f, -0.5f, 0f), new Vector3(2000f, 1f, 2000f));
        Rig a = BuildFighter("A", Vector3.zero, sizeA, leftX, true, head);
        padA = a.Root.AddComponent<StrikePad>(); padA.F = a.Fighter; Vitals(a);
        a.Fighter.FaceTowards(new Vector3(0f, 0f, 10f));
        b = BuildFighter("B", at, sizeB, leftX, true);
        padB = b.Root.AddComponent<StrikePad>(); padB.F = b.Fighter; Vitals(b);
        b.Fighter.FaceTowards(Vector3.zero);
        ((AimFighter)a.Fighter).Them.Add(b.Fighter);
        ((AimFighter)b.Fighter).Them.Add(a.Fighter);
        return a;
    }

    // A guard at the origin facing +Z with two men a metre before him, `angB` and `angC` degrees round
    // from his front (negative: his left), both his opponents. B throws rowB; C throws rowC `lag`
    // seconds later. The most either of his hands moves in one frame against his own root over the
    // second that follows, and (frozen) the most either moves between two frames he is frozen on.
    static float TwoSwing(float hz, string rowB, string rowC, float lag, float angB, float angC, out float frozen) {
        int both, lost;
        return TwoSwing(hz, rowB, rowC, lag, angB, angC, out frozen, out both, out lost);
    }
    // ...and (bothShown) the frames on which his debug view holds two meeting points, one hand's and the other's;
    // (lostInStop) the frozen frames on which it holds none though it held one on the frame before
    static float TwoSwing(float hz, string rowB, string rowC, float lag, float angB, float angC, out float frozen, out int bothShown, out int lostInStop) {
        Scene.Reset(); Scene.DeltaTime = 1f / hz;
        Slab("Ground", new Vector3(0f, -0.5f, 0f), new Vector3(2000f, 1f, 2000f));
        Rig a = BuildFighter("A", Vector3.zero, 1f, -1f, true);
        StrikePad padA = a.Root.AddComponent<StrikePad>(); padA.F = a.Fighter; Vitals(a);
        a.Fighter.FaceTowards(new Vector3(0f, 0f, 10f));
        Rig[] them = new Rig[2]; StrikePad[] pads = new StrikePad[2];
        for (int i = 0; i < 2; i++) {
            them[i] = BuildFighter(i == 0 ? "B" : "C", Round(i == 0 ? angB : angC, 1f), 1f, -1f, true);
            pads[i] = them[i].Root.AddComponent<StrikePad>(); pads[i].F = them[i].Fighter; Vitals(them[i]);
            them[i].Fighter.FaceTowards(Vector3.zero);
            ((AimFighter)a.Fighter).Them.Add(them[i].Fighter);
            ((AimFighter)them[i].Fighter).Them.Add(a.Fighter);
        }
        padA.HoldBlock = true;
        Scene.Step((int)Math.Round(hz * 0.7f));
        Vector3 pl = a.Bones["hand_l"].position - a.Root.transform.position, pr = a.Bones["hand_r"].position - a.Root.transform.position;
        float worst = 0f; frozen = 0f; bool was = false, wasOn = false; bothShown = 0; lostInStop = 0;
        System.Reflection.FieldInfo view = typeof(FighterIK).GetField("_view", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
        pads[0].Press = rowB;
        int at = (int)Math.Round(lag * hz);
        for (int i = 0; i < (int)Math.Round(hz); i++) {
            if (i == at) pads[1].Press = rowC;
            Scene.Step();
            Vector3 l = a.Bones["hand_l"].position - a.Root.transform.position, r = a.Bones["hand_r"].position - a.Root.transform.position;
            float d = Math.Max((l - pl).magnitude, (r - pr).magnitude);
            worst = Math.Max(worst, d);
            if (a.Fighter.Frozen && was) frozen = Math.Max(frozen, d);
            was = a.Fighter.Frozen; pl = l; pr = r;
            IKDebug.View v = (IKDebug.View)view.GetValue(a.IK);
            if (v.BlockOn && v.BlockAlsoOn && v.BlockWeight >= v.BlockAlsoWeight && v.BlockAlsoWeight > 0f && (v.BlockMeet - v.BlockAlsoMeet).magnitude > 0.05f) bothShown++;
            if (a.Fighter.Frozen && wasOn && !v.BlockOn) lostInStop++;
            wasOn = v.BlockOn;
        }
        return worst;
    }

    static void Block() {
        Console.WriteLine("\nBLOCK");
        // ---- pure
        Check(FighterIK.BlockWeight(0f, 0.16f, 0.09f) == 0f && FighterIK.BlockWeight(0.16f, 0.16f, 0.09f) == 1f && FighterIK.BlockWeight(0.25f, 0.16f, 0.09f) == 1f
              && FighterIK.BlockWeight(0.25f + FighterIK.BlockLeadOut, 0.16f, 0.09f) == 0f && FighterIK.BlockWeight(0.08f, 0.16f, 0.09f) > 0.4f
              && FighterIK.BlockWeight(0.08f, 0.16f, 0.09f) < 0.6f && FighterIK.BlockWeight(0.29f, 0.16f, 0.09f) > 0.3f,
              "a blow asks for the guard over its whole wind-up, wholly through its live frames, and lets it go over BlockLeadOut");
        Check(FighterIK.ChooseBlow(new[] { 0.2f, 0.9f, 0f }, 3, 0) == 0 && FighterIK.ChooseBlow(new[] { 0f, 0.9f, 0.3f }, 3, 0) == 1
              && FighterIK.ChooseBlow(new[] { 0.2f, 0.9f }, 2, -1) == 1 && FighterIK.ChooseBlow(new[] { 0f, 0f }, 2, 1) == -1 && FighterIK.ChooseBlow(new float[0], 0, -1) == -1,
              "the guard keeps the blow it holds while anything of it shows, then takes the one furthest into its swing; nothing with none showing");
        {
            Vector3 mark = new Vector3(0f, 1.44f, 0.12f), root = new Vector3(0.2f, 1.6f, 1.0f);
            Vector3 meet = FighterIK.BlockMeet(mark, root, 1.5f);
            Vector3 guard = new Vector3(0.11f, 1.5f, 0.26f), low = new Vector3(0f, 0.9f, 0.22f);
            Check(Math.Abs((meet - mark).magnitude - FighterIK.BlockStandOff * 1.5f) < 1e-4f && Vector3.Angle(meet - mark, root - mark) < 0.1f
                  && (FighterIK.BlockMeet(mark, mark + new Vector3(0f, 0f, 0.04f), 1f) - mark).magnitude <= 0.04f + 1e-5f,
                  "the glove meets a blow BlockStandOff before the guard's own front, on the blow's line, grown with the man");
            Check((FighterIK.CoverHand(guard, low, 0f, 1f) - guard).magnitude < 1e-6f && (FighterIK.CoverHand(guard, meet, 1f, 1f) - meet).magnitude < 1e-5f
                  && Math.Abs((FighterIK.CoverHand(guard, low, 1f, 1f) - guard).magnitude - FighterIK.BlockMaxShift) < 1e-4f
                  && Math.Abs((FighterIK.CoverHand(guard, low, 1f, 1.5f) - guard).magnitude - FighterIK.BlockMaxShift * 1.5f) < 1e-4f
                  && Math.Abs((FighterIK.CoverHand(guard, low, 0.5f, 1f) - guard).magnitude - 0.5f * FighterIK.BlockMaxShift) < 1e-4f
                  && Vector3.Angle(FighterIK.CoverHand(guard, low, 1f, 1f) - guard, low - guard) < 0.1f,
                  "the covering hand goes to the meeting point by its share, and never more than BlockMaxShift from the guard");
            Check(FighterIK.CoverRight(false) && !FighterIK.CoverRight(true), "the hand on the blow's side covers: his right is before the guard's left");
            // 2026-11-11: a punch a glove is on stops at the glove
            Vector3 front = new Vector3(0f, 1.44f, 0.12f), from = new Vector3(0.1f, 1.5f, 1.0f);
            Vector3 stop = FighterIK.BlockStop(front, from, 1f);
            Check(Math.Abs((stop - front).magnitude - (FighterIK.BlockStandOff + FighterIK.BlockFaceGap)) < 1e-5f && Vector3.Angle(stop - front, from - front) < 0.1f
                  && Math.Abs((stop - FighterIK.BlockMeet(front, from, 1f)).magnitude - FighterIK.BlockFaceGap) < 1e-5f
                  && Math.Abs((FighterIK.BlockStop(front, from, 1.5f) - front).magnitude - 1.5f * (FighterIK.BlockStandOff + FighterIK.BlockFaceGap)) < 1e-5f
                  && (FighterIK.BlockStop(front, front + new Vector3(0f, 0f, 0.05f), 1f) - front).magnitude <= 0.05f + 1e-5f
                  && FighterIK.BlockFaceGap > 0.03f && FighterIK.BlockFaceGap < 0.15f,
                  "a punch a glove is on stops BlockFaceGap short of the glove's own point, on the blow's own line, grown with the man");
            // a covering hand's share
            float up = 0f, steps = 0f; while (up < 1f && steps < 100f) { up = FighterIK.BlockShare(up, 1f, 1f / 60f); steps++; }
            float down = 1f, stepsDown = 0f; while (down > 0f && stepsDown < 100f) { down = FighterIK.BlockShare(down, 0f, 1f / 60f); stepsDown++; }
            Check(Math.Abs(steps - (float)Math.Ceiling(60f * FighterIK.BlockLeadIn - 1e-3f)) < 0.5f && Math.Abs(stepsDown - (float)Math.Ceiling(60f * FighterIK.BlockLeadOut - 1e-3f)) < 0.5f
                  && FighterIK.BlockShare(0.3f, 0.35f, 1f / 60f) == 0.35f && FighterIK.BlockShare(0.3f, 0.28f, 1f / 60f) == 0.28f && FighterIK.BlockShare(0.4f, 1f, 0f) == 0.4f,
                  "a covering hand's share goes on over BlockLeadIn at the fastest and off over BlockLeadOut, follows a blow that asks for less, and stands still in a frame of no time");
        }

        // ---- through the rig: a guard at the origin, a man a metre before him who throws
        Rig b; StrikePad padA, padB;
        foreach (string row in new[] { "Jab", "Cross", "Kick" }) {
            Rig a = Duel(new Vector3(0f, 0f, 1.0f), 1f, 1f, out b, out padA, out padB);
            padA.HoldBlock = true;
            Scene.Step(40);
            Vector3 guardL = a.Bones["hand_l"].position, guardR = a.Bones["hand_r"].position;
            AttackRow r = GameData.Attack(row);
            bool arm = row != "Kick";
            // the jab comes off his lead (left) hand, which is before the guard's right; the cross and the kick off his right
            string cover = row == "Jab" ? "hand_r" : "hand_l", other = row == "Jab" ? "hand_l" : "hand_r";
            Vector3 guardC = row == "Jab" ? guardR : guardL, guardO = row == "Jab" ? guardL : guardR;
            Vector3 mark = FighterIK.StrikeMark(b.Root.transform.position, Vector3.zero, 1f, arm ? FighterIK.ShoulderHeight : FighterIK.HipHeight, 0f);
            Vector3 meet = FighterIK.BlockMeet(mark, b.Root.transform.position + Vector3.up * (arm ? FighterIK.ShoulderHeight : FighterIK.HipHeight), 1f);
            padB.Press = row;
            // (the hands against his own root: a blocked blow shoves the whole man back)
            Vector3 prev = guardC; float worstStep = 0f, atLand = -1f, otherMoved = 0f, back = 0f; Vector3 landed = guardC;
            // ...and where the blow's own joint is as it lands (2026-11-11): its distance from the covering
            // hand's joint, and how far PAST the glove toward the guard's own middle it has gone
            float fistGap = -1f, fistPast = 0f;
            for (int i = 0; i < 90; i++) {
                Scene.Step();
                Vector3 root = a.Root.transform.position;
                Vector3 q = a.Bones[cover].position - root;
                worstStep = Math.Max(worstStep, (q - prev).magnitude); prev = q;
                otherMoved = Math.Max(otherMoved, (a.Bones[other].position - root - guardO).magnitude);
                if (atLand < 0f && b.Fighter.State == FighterState.Attack && b.Fighter.AttackTime >= r.startup) {
                    atLand = (q - meet).magnitude; landed = q;
                    Vector3 fist = b.Bones[StrikeBone(row)].position - root;
                    fistGap = (q - fist).magnitude; fistPast = q.z - fist.z;
                }
            }
            back = (a.Bones[cover].position - a.Root.transform.position - guardC).magnitude;
            float want = Math.Min((meet - guardC).magnitude, FighterIK.BlockMaxShift);
            // (This measures the HAND against its own meeting point, built here from the code's own formula. It
            // says the hand gets where it is sent, not that the blow comes there: from this metre the fist stops
            // short of the glove -- the arm is 0.6 m, the row lands from 1.3 -- and that is printed. Where the
            // two do meet, and that the fist is never past the glove, is checked against the fist, below.)
            Console.WriteLine("  a guard met by a " + row + ": the covering hand is " + (atLand * 100).ToString("0.0") + " cm from the meeting point as the blow lands ("
                + ((guardC - meet).magnitude * 100).ToString("0.0") + " from it in the plain guard), having moved " + ((landed - guardC).magnitude * 100).ToString("0.0")
                + " cm; its largest frame " + (worstStep * 100).ToString("0.0") + " cm; the other hand moved " + (otherMoved * 100).ToString("0.0") + " cm; the blow's own joint is "
                + (fistGap * 100).ToString("0.0") + " cm from the hand's" + (arm ? ", " + (-fistPast * 100).ToString("0.0") + " cm short of passing it" : ""));
            Check(Math.Abs((landed - guardC).magnitude - want) < 0.02f && atLand < (guardC - meet).magnitude - 0.9f * want + 0.02f,
                  "a guard meets a " + row + " with the hand on its side: there, or BlockMaxShift toward it, as the blow lands");
            Check(otherMoved < 0.01f, "...the other hand keeps the guard (" + row + ")");
            Check(worstStep < 0.09f && back < 0.01f, "...the hand comes onto it and off it over frames, and is back in the guard after (" + row + ")");
        }
        {
            // a kick already part way through when it comes into reach: the hand comes onto it over
            // BlockLeadIn, not in a frame; and one that vanishes on its contact frame is let go of
            // over BlockLeadOut, not dropped
            Rig a = Duel(new Vector3(0f, 0f, 5.0f), 1f, 1f, out b, out padA, out padB);
            padA.HoldBlock = true; Scene.Step(40);
            AttackRow kick = GameData.Attack("Kick");
            padB.Press = "Kick";
            Vector3 prev = a.Bones["hand_l"].position; float onStep = 0f, offStep = 0f; bool came = false, went = false;
            for (int i = 0; i < 60; i++) {
                if (!came && b.Fighter.State == FighterState.Attack && b.Fighter.AttackTime >= 0.3f * kick.startup) { b.Root.transform.position = new Vector3(0f, 0f, 1.0f); came = true; }
                else if (came && !went && b.Fighter.AttackTime >= kick.startup) { b.Root.transform.position = new Vector3(0f, 0f, 30f); went = true; }
                Scene.Step();
                Vector3 q = a.Bones["hand_l"].position; float d = (q - prev).magnitude; prev = q;
                if (came && !went) onStep = Math.Max(onStep, d);
                if (went) offStep = Math.Max(offStep, d);
            }
            float mostOn = FighterIK.BlockMaxShift / (60f * FighterIK.BlockLeadIn), mostOff = FighterIK.BlockMaxShift / (60f * FighterIK.BlockLeadOut);
            Console.WriteLine("  a kick come into reach part way through, then gone at its contact frame: the covering hand's largest frame is "
                + (onStep * 100).ToString("0.0") + " cm coming on, " + (offStep * 100).ToString("0.0") + " cm letting go");
            Check(came && onStep > 0.02f && onStep < mostOn + 0.01f, "a blow caught part way through its swing is come onto over BlockLeadIn, not in a frame");
            Check(went && offStep > 0.02f && offStep < mostOff + 0.01f, "a blow that vanishes is let go of over BlockLeadOut, not dropped");
        }
        {
            // nothing to meet: a blow from behind, a man too far to reach him, and no guard up
            Rig a = Duel(new Vector3(0f, 0f, -1.0f), 1f, 1f, out b, out padA, out padB);
            padA.HoldBlock = true; Scene.Step(40);
            Vector3 gl = a.Bones["hand_l"].position, gr = a.Bones["hand_r"].position; float moved = 0f;
            padB.Press = "Jab";
            for (int i = 0; i < 30; i++) { Scene.Step(); moved = Math.Max(moved, Math.Max((a.Bones["hand_l"].position - gl).magnitude, (a.Bones["hand_r"].position - gr).magnitude)); }
            // (he is struck in the back: his hands are thrown by the blow, not sent to it -- so read before it lands)
            Rig a2 = Duel(new Vector3(0f, 0f, -1.0f), 1f, 1f, out b, out padA, out padB);
            padA.HoldBlock = true; Scene.Step(40);
            gl = a2.Bones["hand_l"].position; gr = a2.Bones["hand_r"].position; float before = 0f;
            padB.Press = "Kick";
            for (int i = 0; i < 8; i++) { Scene.Step(); before = Math.Max(before, Math.Max((a2.Bones["hand_l"].position - gl).magnitude, (a2.Bones["hand_r"].position - gr).magnitude)); }
            Check(before < 1e-3f, "a blow from behind is not met: the guard does not cover his back");
            Rig a3 = Duel(new Vector3(0f, 0f, 5.0f), 1f, 1f, out b, out padA, out padB);
            padA.HoldBlock = true; Scene.Step(40);
            gl = a3.Bones["hand_l"].position; gr = a3.Bones["hand_r"].position; float farMoved = 0f;
            padB.Press = "Jab";
            for (int i = 0; i < 30; i++) { Scene.Step(); farMoved = Math.Max(farMoved, Math.Max((a3.Bones["hand_l"].position - gl).magnitude, (a3.Bones["hand_r"].position - gr).magnitude)); }
            Check(farMoved < 1e-3f, "a swing that cannot reach him is not met");
            Rig a4 = Duel(new Vector3(0f, 0f, 1.0f), 1f, 1f, out b, out padA, out padB);
            Scene.Step(40);
            gl = a4.Bones["hand_l"].position; gr = a4.Bones["hand_r"].position; float downMoved = 0f;
            padB.Press = "Kick";
            for (int i = 0; i < 8; i++) { Scene.Step(); downMoved = Math.Max(downMoved, Math.Max((a4.Bones["hand_l"].position - gl).magnitude, (a4.Bones["hand_r"].position - gr).magnitude)); }
            Check(downMoved < 1e-3f, "with no guard up nothing is met: the hands stay down until he is hit");
        }
        {
            // The glove and the FIST (2026-11-11, the second reading). The glove went BlockStandOff before his
            // front and the blow went to his front whatever the glove did: from 0.66 m a blocked jab ended 8 cm
            // PAST the glove, on his face. The check above never read the striker's hand and could not see it.
            // Jab, cross and hook from 0.66, 0.80 and 0.90 m -- as far as the arm reaches the glove -- at 30, 60
            // and 120 Hz, either layout: on the frame the blow lands, his fist's joint against the covering
            // hand's joint. And on, until the arm is home: the glove lets go BlockLeadOut after the blow's live
            // frames, with the arm still out -- stopped only by as much as the glove was there that frame, a
            // blocked hook went on 6 cm toward his face after it had landed, 1.8 cm past the hand's joint.
            float least = 1f, most = 0f, past = -1f, pastAfter = -1f, wentOn = 0f; bool blocked = true;
            foreach (float leftX in new[] { -1f, 1f })
                foreach (float hz in new[] { 30f, 60f, 120f })
                    foreach (string row in new[] { "Jab", "Cross", "Hook" })
                        foreach (float sep in new[] { 0.66f, 0.80f, 0.90f }) {
                            Rig a = Duel(new Vector3(0f, 0f, sep), 1f, 1f, out b, out padA, out padB, false, leftX);
                            Scene.DeltaTime = 1f / hz;
                            padA.HoldBlock = true; Scene.Step((int)Math.Round(hz * 0.7f));
                            AttackRow r = GameData.Attack(row);
                            float health = a.Fighter.Health;
                            padB.Press = row;
                            for (int i = 0; i < 200 && !(b.Fighter.State == FighterState.Attack && b.Fighter.AttackTime >= r.startup); i++) Scene.Step();
                            // by the names the IK itself goes by: the lead hand's blow comes to the guard's _r hand
                            Vector3 glove = a.Bones[row == "Cross" ? "hand_l" : "hand_r"].position, fist = b.Bones[StrikeBone(row)].position;
                            least = Math.Min(least, (glove - fist).magnitude); most = Math.Max(most, (glove - fist).magnitude);
                            past = Math.Max(past, glove.z - fist.z);
                            if (!(a.Fighter.Health < health) || a.Fighter.State == FighterState.Hit || !a.Fighter.Frozen) blocked = false;
                            // (how far it goes on is read from 0.80 m: nearer, the lunge walks him into the man -- the
                            // harness's controllers do not collide -- and from 0.90 the arm ends short and rides the lunge)
                            float landed = fist.z - a.Root.transform.position.z;
                            for (int i = 0; i < 200; i++) {
                                Scene.Step();
                                if (b.Fighter.State != FighterState.Attack) break;
                                glove = a.Bones[row == "Cross" ? "hand_l" : "hand_r"].position; fist = b.Bones[StrikeBone(row)].position;
                                pastAfter = Math.Max(pastAfter, glove.z - fist.z);
                                if (sep == 0.80f) wentOn = Math.Max(wentOn, landed - (fist.z - a.Root.transform.position.z));
                            }
                        }
            Console.WriteLine("  a punch on a guard from 0.66 to 0.90 m: as it lands the fist is " + (least * 100).ToString("0.0") + " to " + (most * 100).ToString("0.0")
                + " cm from the covering hand's joint, and at the nearest " + (-past * 100).ToString("0.0") + " cm short of passing it (negative: past it); from then until the arm is home, "
                + (-pastAfter * 100).ToString("0.0") + " cm short at the nearest, and from 0.80 m it goes on " + (wentOn * 100).ToString("0.0") + " cm toward him at most");
            Check(blocked && past < 0.005f, "a blocked punch stops at the glove: its fist never nearer the guard's own middle than the covering hand (jab, cross and hook from 0.66, 0.80 and 0.90 m at 30, 60 and 120 Hz, either layout)");
            Check(blocked && least > 0.03f && most < 0.12f, "...and the fist is at the glove: the two joints 3 to 12 cm apart as the blow lands, from as far as the arm reaches it");
            Check(pastAfter < 0.005f && wentOn < 0.01f, "...and it stays stopped until the arm is home: never past the hand as the glove lets go, and no further toward him than it landed (under 1 cm, from 0.80 m)");
            // ...a man with his guard down is struck where he always was: the stop is the glove's, not the fight's
            Rig open = Duel(new Vector3(0f, 0f, 0.66f), 1f, 1f, out b, out padA, out padB);
            Scene.Step(42); padB.Press = "Jab";
            AttackRow jab = GameData.Attack("Jab");
            for (int i = 0; i < 200 && !(b.Fighter.State == FighterState.Attack && b.Fighter.AttackTime >= jab.startup); i++) Scene.Step();
            float short0 = b.Bones["hand_l"].position.z - FighterIK.FrontDepth;       // B stands on +Z facing him: his front is toward B
            Check(Math.Abs(short0 - FighterIK.KnuckleSkin) < 0.01f && open.Fighter.State == FighterState.Hit,
                  "...and a punch at a man with no guard up lands on him as it did: its joint a skin short of his front (" + (short0 * 100).ToString("0.0") + " cm)");
        }
        {
            // Two men swing at once (2026-11-11, the second reading). One share served both hands: when the guard
            // passed from one man's blow to the next the new hand began at the old blow's share and the old hand
            // was dropped at once (22.8 cm in a frame at 60 Hz, 25.0 at 30), and it passed inside his own hit stop
            // (12.7 cm on a frozen frame). B 15 degrees to his left jabs, C 15 degrees to his right kicks 0.03 s
            // later: the jab comes to his right hand, the kick to his left.
            float fz, worstOver = 0f, worstFrozen = 0f; string rates = ""; int shown = 0, shownAlone, lost = 0, lostNow;
            foreach (float hz in new[] { 30f, 60f, 120f }) {
                float most = FighterIK.BlockMaxShift / (hz * FighterIK.BlockLeadIn);
                int both;
                float w = TwoSwing(hz, "Jab", "Kick", 0.03f, -15f, 15f, out fz, out both, out lostNow);
                lost += lostNow;
                if (hz == 60f) shown = both;
                worstOver = Math.Max(worstOver, w - most); worstFrozen = Math.Max(worstFrozen, fz);
                rates += (rates == "" ? "" : " / ") + (w * 100).ToString("0.0");
            }
            // the blow before runs out while he is frozen by the next: a hook, then a kick 0.145 s later
            float stop = TwoSwing(60f, "Hook", "Kick", 0.145f, -15f, 15f, out fz);
            worstFrozen = Math.Max(worstFrozen, fz);
            // (the debug view, read off the rig; and two blows that do not overlap -- a jab, and a cross from
            // the same place 0.30 s later, to his other hand -- show one point at a time)
            TwoSwing(60f, "Jab", "Cross", 0.30f, 0f, 0f, out fz, out shownAlone, out lostNow);
            lost += lostNow;
            Console.WriteLine("  a jab from one man and a kick from another 0.03 s later: a hand's largest frame is " + rates + " cm at 30 / 60 / 120 Hz; a hook then a kick 0.145 s later, "
                + (stop * 100).ToString("0.0") + " cm at 60 Hz; while he is frozen a hand moves " + (worstFrozen * 100).ToString("0.00") + " cm at most; the debug view holds both hands' points on "
                + shown + " frames of the first at 60 Hz");
            Check(worstOver < 0.01f && stop < FighterIK.BlockMaxShift / (60f * FighterIK.BlockLeadIn) + 0.01f,
                  "the guard passes from one man's blow to the next hand by hand: no hand faster than a blow caught late, BlockMaxShift over BlockLeadIn and 1 cm (30, 60 and 120 Hz)");
            Check(worstFrozen < 0.001f, "...and nothing of it passes while he is frozen: through his own hit stop the hands stay where they were");
            Check(shown >= 2 && shown <= 8 && shownAlone == 0, "...and while the one hand lets go and the other comes on the debug view holds both hands' points (" + shown + " frames at 60 Hz)");
            Check(lost == 0, "...and it holds them through his hit stop: the meeting point is not dropped from the view on a frozen frame (" + lost + " such frames)");
            // ...two blows that come to the SAME hand, from 15 and 40 degrees either side: a cross then a kick,
            // a kick then a cross, a jab then a hook, 0 to 0.30 s apart. The hand lets go of the first where it met
            // it before it goes to the second: its point was changed under it, up to 26 cm in a frame.
            float sameFrozen = 0f, sameWorst = 0f;
            foreach (float ang in new[] { 15f, 40f })
                foreach (string[] pair in new[] { new[] { "Cross", "Kick" }, new[] { "Kick", "Cross" }, new[] { "Jab", "Hook" } })
                    for (int k = 0; k <= 30; k += 3) {
                        float w = TwoSwing(60f, pair[0], pair[1], k * 0.01f, -ang, ang, out fz);
                        sameWorst = Math.Max(sameWorst, w); sameFrozen = Math.Max(sameFrozen, fz);
                    }
            Console.WriteLine("  two blows to the same hand, 0 to 0.30 s apart, from 15 and 40 degrees either side: its largest frame is " + (sameWorst * 100).ToString("0.0") + " cm at 60 Hz");
            Check(sameWorst < FighterIK.BlockMaxShift / (60f * FighterIK.BlockLeadIn) + 0.01f && sameFrozen < 0.001f,
                  "...and a hand that two men's blows both come to lets go of the first before it goes to the second: no faster than a blow caught late, and not while he is frozen");
        }
        {
            // ...and one man's two blows to the same hand, a cross and then a kick. In play the first has always
            // been let go of before the second begins; here the guard is held frozen (by the test) on the live
            // cross until the kick is half wound up, so he wakes with all of the cross still on the hand the
            // kick comes to.
            Rig a = Duel(new Vector3(0f, 0f, 1.0f), 1f, 1f, out b, out padA, out padB);
            padA.HoldBlock = true; Scene.Step(40);
            AttackRow cross = GameData.Attack("Cross"), kick = GameData.Attack("Kick");
            padB.Press = "Cross";
            for (int i = 0; i < 60 && !(b.Fighter.State == FighterState.Attack && b.Fighter.AttackTime >= cross.startup + 0.03f); i++) Scene.Step();
            Vector3 onCross = a.Bones["hand_l"].position - a.Root.transform.position;
            a.Fighter.Freeze(cross.TotalTime - b.Fighter.AttackTime + 0.5f * kick.startup);
            padB.Press = "Kick";
            Vector3 prev = onCross; float worst = 0f, heldBy = 0f; bool woke = false, mid = false;
            for (int i = 0; i < 90; i++) {
                Scene.Step();
                Vector3 q = a.Bones["hand_l"].position - a.Root.transform.position;
                if (!woke && !a.Fighter.Frozen) {
                    woke = true; heldBy = (prev - onCross).magnitude;
                    mid = b.Fighter.State == FighterState.Attack && b.Fighter.ActiveAttack == kick && b.Fighter.AttackTime > 0f && b.Fighter.AttackTime < kick.startup;
                }
                worst = Math.Max(worst, (q - prev).magnitude); prev = q;
            }
            Check(woke && mid && heldBy < 1e-4f && worst > 0.02f && worst < FighterIK.BlockMaxShift / (60f * FighterIK.BlockLeadIn) + 0.01f,
                  "...nor is the point changed under a hand for the same man's next blow: it lets go of the one before (" + (worst * 100).ToString("0.0") + " cm in its largest frame)");
        }
        {
            // The stop is the glove's: a guard dropped while the punch is on its way has no glove on it when it
            // lands, and the punch lands on him as any other -- a skin short of his front, and he is hit.
            Rig a = Duel(new Vector3(0f, 0f, 0.66f), 1f, 1f, out b, out padA, out padB);
            padA.HoldBlock = true; Scene.Step(42);
            AttackRow jab = GameData.Attack("Jab");
            padB.Press = "Jab";
            for (int i = 0; i < 200 && !(b.Fighter.State == FighterState.Attack && b.Fighter.AttackTime >= jab.startup); i++) {
                if (b.Fighter.State == FighterState.Attack && b.Fighter.AttackTime >= 0.03f) padA.HoldBlock = false;
                Scene.Step();
            }
            float shortOf = b.Bones["hand_l"].position.z - FighterIK.FrontDepth;
            Check(a.Fighter.State == FighterState.Hit && Math.Abs(shortOf - FighterIK.KnuckleSkin) < 0.03f,
                  "a guard dropped as the punch comes has no glove on it: the punch lands on him, its joint " + (shortOf * 100).ToString("0.0") + " cm short of his front");
        }
        {
            // The stop is one swing's: a jab is blocked, the guard comes down, and the next jab begins in one
            // long frame (a hitch of 0.1 s) -- it has landed on the first frame it is drawn, with no wind-up
            // frame to read the glove in -- and it lands on him, not where the last one was stopped.
            Rig a = Duel(new Vector3(0f, 0f, 0.66f), 1f, 1f, out b, out padA, out padB);
            padA.HoldBlock = true; Scene.Step(42);
            AttackRow jab = GameData.Attack("Jab");
            padB.Press = "Jab";
            bool landed = false; float stopped = 0f;
            for (int i = 0; i < 60; i++) {
                Scene.Step();
                if (!landed && b.Fighter.State == FighterState.Attack && b.Fighter.AttackTime >= jab.startup) { landed = true; stopped = b.Bones["hand_l"].position.z - a.Root.transform.position.z - FighterIK.FrontDepth; }
            }
            padA.HoldBlock = false; Scene.Step(40);
            Scene.DeltaTime = 0.1f;
            padB.Press = "Jab";
            int n = 0;
            for (; n < 4 && !(b.Fighter.State == FighterState.Attack && b.Fighter.AttackTime >= jab.startup); n++) Scene.Step();
            float shortOf = b.Bones["hand_l"].position.z - a.Root.transform.position.z - FighterIK.FrontDepth;
            Check(landed && stopped > 0.12f && n <= 2 && b.Fighter.State == FighterState.Attack && a.Fighter.State == FighterState.Hit && Math.Abs(shortOf - FighterIK.KnuckleSkin) < 0.03f,
                  "a punch begun in one long frame after a blocked one is not stopped where the last one was: it lands on him, its joint " + (shortOf * 100).ToString("0.0")
                  + " cm short of his front (the blocked one stopped " + (stopped * 100).ToString("0.0") + " short)");
            Scene.DeltaTime = 1f / 60f;
        }
        Scene.DeltaTime = 1f / 60f;
    }

    static float Yaw(Rig r, string bone, string marker) {
        Vector3 f = r.Bones[marker].position - r.Bones[bone].position;
        return Mathf.Atan2(f.x, f.z) * Mathf.Rad2Deg;
    }
    static float Pitch(Rig r, string bone, string marker) {
        Vector3 f = r.Bones[marker].position - r.Bones[bone].position;
        return Mathf.Atan2(f.y, Mathf.Sqrt(f.x * f.x + f.z * f.z)) * Mathf.Rad2Deg;
    }

    // The head's yaw against the body AS IT IS DRAWN, off the bones: the nose marker against the
    // shoulder line (the _r bones are on his right in these rigs). + is to his right.
    static float HeadOnBody(Rig r) {
        Vector3 sh = r.Bones["upperarm_r"].position - r.Bones["upperarm_l"].position;
        return FighterIK.WrapDegrees(Yaw(r, "head", "nose") - Mathf.Atan2(-sh.z, sh.x) * Mathf.Rad2Deg);
    }

    // A man with a head at the origin facing +Z, with a pad, and the men he may look at -- standing
    // where `at` says, in his list in that order. Nobody swings in these scenes.
    static Rig Looker(float hz, out StrikePad pad, out Rig[] men, params Vector3[] at) {
        Scene.Reset(); Scene.DeltaTime = 1f / hz;
        Slab("Ground", new Vector3(0f, -0.5f, 0f), new Vector3(4000f, 1f, 4000f));
        Rig a = BuildFighter("A", Vector3.zero, 1f, -1f, true, true);
        pad = a.Root.AddComponent<StrikePad>(); pad.F = a.Fighter; Vitals(a);
        a.Fighter.FaceTowards(new Vector3(0f, 0f, 10f));
        men = new Rig[at.Length];
        for (int i = 0; i < at.Length; i++) {
            men[i] = BuildFighter("B" + i, at[i], 1f, -1f, true);
            Vitals(men[i]); men[i].Fighter.FaceTowards(Vector3.zero);
            ((AimFighter)a.Fighter).Them.Add(men[i].Fighter);
        }
        return a;
    }
    static Vector3 Round(float deg, float dist) {
        return new Vector3(Mathf.Sin(deg * Mathf.Deg2Rad) * dist, 0f, Mathf.Cos(deg * Mathf.Deg2Rad) * dist);
    }
    // A head's yaw followed over frames: how often it goes from one side of the front to the
    // other (past a degree either side), how far it travels, and its largest frame.
    class Sweep {
        public int Crossings, Side; public float Travel, Fastest, Last; bool any;
        public void Add(float yaw) {
            if (any) { float d = Math.Abs(FighterIK.WrapDegrees(yaw - Last)); Travel += d; Fastest = Math.Max(Fastest, d); }
            int s = yaw > 1f ? 1 : yaw < -1f ? -1 : 0;
            if (s != 0) { if (Side != 0 && s != Side) Crossings++; Side = s; }
            Last = yaw; any = true;
        }
    }

    static void Look() {
        Console.WriteLine("\nLOOK");
        // ---- pure
        float y, p;
        Vector3 eye = new Vector3(0f, 1.672f, 0f);
        bool on = FighterIK.LookAngles(eye, Vector3.forward, new Vector3(2f, 1.672f, 2f), out y, out p);
        Check(on && Math.Abs(y - 45f) < 0.01f && Math.Abs(p) < 0.01f, "the look turns to a man 45 degrees to his right by 45 degrees");
        FighterIK.LookAngles(eye, Vector3.forward, new Vector3(-2f, 1.672f, 0.1f), out y, out p);
        float left = y;
        FighterIK.LookAngles(eye, Vector3.forward, new Vector3(0.3f, 1.672f, -2f), out y, out p);
        Check(Math.Abs(left + FighterIK.LookMaxYaw) < 0.01f && Math.Abs(y - FighterIK.LookMaxYaw) < 0.01f,
              "...no further than LookMaxYaw either way: past it the head holds the limit, on the side the man is");
        FighterIK.LookAngles(eye, Vector3.forward, new Vector3(0f, 3.2f, 1f), out y, out p);
        float up = p;
        FighterIK.LookAngles(eye, Vector3.forward, new Vector3(0f, 1.2f, 2f), out y, out p);
        Check(Math.Abs(up - FighterIK.LookMaxPitch) < 0.01f && p < -10f && p > -15f, "...up and down to LookMaxPitch");
        Check(!FighterIK.LookAngles(eye, Vector3.forward, new Vector3(0f, 1.672f, FighterIK.LookReach + 0.5f), out y, out p) && y == 0f && p == 0f
              && !FighterIK.LookAngles(eye, Vector3.forward, new Vector3(0.01f, 1.9f, 0.01f), out y, out p),
              "...at nothing beyond LookReach, and not at a man on top of him");
        FighterIK.LookAngles(eye, new Vector3(1f, 0f, 0f), new Vector3(2f, 1.672f, 2f), out y, out p);
        Check(Math.Abs(y + 45f) < 0.01f, "...measured against the way his body faces");
        {
            float[] at = new float[3]; int n = 0;
            foreach (float hz in new[] { 30f, 60f, 120f }) { float v = 0f; for (int i = 0; i < (int)Math.Round(0.2f * hz); i++) v = FighterIK.LookEase(v, 45f, 1f / hz); at[n++] = v; }
            float end = 0f; for (int i = 0; i < 120; i++) end = FighterIK.LookEase(end, 45f, 1f / 60f);
            Check(Math.Abs(at[0] - at[1]) < 0.01f && Math.Abs(at[2] - at[1]) < 0.01f && at[1] > 35f && at[1] < 42f && Math.Abs(end - 45f) < 0.01f
                  && FighterIK.LookEase(10f, 45f, 0f) == 10f,
                  "the look eases round: the same place at 30, 60 and 120 Hz, most of the way in a fifth of a second, there in the end, nothing in a frame of no time");
        }

        // ---- through the rig
        Rig b; StrikePad padA, padB;
        {
            Rig a = Duel(new Vector3(1.4142f, 0f, 1.4142f), 1f, 1f, out b, out padA, out padB, true);
            Scene.Step();
            float first = Yaw(a, "head", "nose");
            Scene.Step(90);
            float head = Yaw(a, "head", "nose"), neck = Yaw(a, "neck_01", "throat");
            Vector3 eyes = b.Root.transform.position + Vector3.up * FighterIK.EyeHeight - a.Bones["head"].position;
            float line = Mathf.Atan2(eyes.x, eyes.z) * Mathf.Rad2Deg;
            Console.WriteLine("  a man 45 degrees to his right at 2 m: the head turns " + head.ToString("0.0") + " degrees (the line to his eyes " + line.ToString("0.0")
                + "), the neck " + neck.ToString("0.0") + "; " + first.ToString("0.0") + " in the first frame");
            Check(Math.Abs(head - line) < 1f && Math.Abs(Pitch(a, "head", "nose")) < 1f, "the head turns to the nearest opponent's eyes");
            Check(Math.Abs(neck - FighterIK.LookNeckShare * head) < 1f, "...the neck taking LookNeckShare of the turn and the head the rest");
            Check(first > 2f && first < 9f, "...over frames, not in one");
            Vector3 sh = a.Bones["upperarm_l"].position - a.Bones["upperarm_r"].position;
            Check(Math.Abs(sh.z) < 1e-3f, "...and the body does not turn with it");
        }
        {
            Rig a = Duel(new Vector3(0.2f, 0f, -2f), 1f, 1f, out b, out padA, out padB, true);
            Scene.Step(120);
            Check(Math.Abs(Yaw(a, "head", "nose") - FighterIK.LookMaxYaw) < 1f, "a man behind him: the head turns LookMaxYaw toward him and stops");
            Rig c = Duel(new Vector3(0f, 0f, 20f), 1f, 1f, out b, out padA, out padB, true);
            Scene.Step(120);
            Check(Math.Abs(Yaw(c, "head", "nose")) < 0.1f && Math.Abs(Pitch(c, "head", "nose")) < 0.1f, "a man 20 m away is not looked at: he looks where he faces");
            Rig d = Duel(new Vector3(0f, 0f, 1.0f), 1f, 1.55f, out b, out padA, out padB, true);
            Scene.Step(120);
            Check(Math.Abs(Pitch(d, "head", "nose") - FighterIK.LookMaxPitch) < 1f, "a much taller man close to him: he looks up, to LookMaxPitch ("
                  + Pitch(d, "head", "nose").ToString("0.0") + " degrees)");
        }
        {
            // pure: the body drawn round toward a man the head is already on -- the head stays on him
            float look = 70f, most = 0f, least = 999f;
            for (int i = 1; i <= 30; i++) {
                float body = Math.Min(90f, 18f * i);
                look = FighterIK.LookTurn(look, body + Mathf.Clamp(90f - body, -FighterIK.LookMaxYaw, FighterIK.LookMaxYaw), body, 1f / 60f);
                most = Math.Max(most, look); least = Math.Min(least, look);
            }
            Check(most < 90.5f && least > 69.5f && Math.Abs(look - 90f) < 0.5f, "pure: as the body is drawn round to a man, the head's own yaw goes to him and never past him");
            Check(Math.Abs(FighterIK.LookTurn(0f, 170f, 0f, 1f) - FighterIK.LookMaxYaw) < 0.01f && Math.Abs(FighterIK.LookTurn(175f, -175f, 180f, 1f / 60f) - 176.535f) < 0.1f
                  && FighterIK.LookTurn(30f, 60f, 0f, 0f) == 30f,
                  "...held within LookMaxYaw of the body, the shorter way round, nothing in a frame of no time");
        }
        {
            // through the rig: he looks at a man at his right, then turns to face him. The head stays on
            // the man while the body is drawn round under it -- measured against the drawn body, in the world
            Rig a = Duel(new Vector3(2f, 0f, 0f), 1f, 1f, out b, out padA, out padB, true);
            Scene.Step(90);
            float start = Yaw(a, "head", "nose");
            a.Fighter.FaceTowards(new Vector3(10f, 0f, 0f));
            float most = 0f, least = 999f, body = 0f;
            for (int i = 0; i < 30; i++) {
                Scene.Step();
                float h = Yaw(a, "head", "nose");
                most = Math.Max(most, h); least = Math.Min(least, h);
            }
            Vector3 sh = a.Bones["upperarm_r"].position - a.Bones["upperarm_l"].position;       // his right, as drawn
            body = Mathf.Atan2(-sh.z, sh.x) * Mathf.Rad2Deg;
            Console.WriteLine("  on a man at his right (" + start.ToString("0.0") + " degrees), then turned to face him: the head's own yaw runs "
                + least.ToString("0.0") + " to " + most.ToString("0.0") + " while the body is drawn round to " + body.ToString("0.0"));
            Check(Math.Abs(start - FighterIK.LookMaxYaw) < 1f && most < 92f && least > 68f && Math.Abs(body - 90f) < 2f,
                  "turned to face a man he was looking at, the head stays on him while the body comes round: never past him, never back off him");
        }
        {
            // reeling, he does not look; hit stop holds the head where it was
            Rig a = Duel(new Vector3(1.4142f, 0f, 1.4142f), 1f, 1f, out b, out padA, out padB, true);
            Scene.Step(90);
            a.Fighter.ReceiveKnockback(new Vector3(0f, 0f, -0.2f), false, 0.6f);
            Scene.Step(30);
            float reeling = Yaw(a, "head", "nose");
            Scene.Step(90);
            float again = Yaw(a, "head", "nose");
            Check(Math.Abs(reeling) < 3f && again > 35f, "while he reels he does not look (" + reeling.ToString("0.0") + " degrees); after it he looks again");
            a.Fighter.Freeze(0.2f);
            b.Root.transform.position = new Vector3(-1.4142f, 0f, 1.4142f);
            Scene.Step(8);
            Check(Math.Abs(Yaw(a, "head", "nose") - again) < 0.5f, "through hit stop the head stays where it was");
        }

        // ---- 2026-11-11, the second reading: nobody to look at, a man behind him, two men at one distance
        StrikePad pad; Rig[] men;
        {
            // Nobody in reach (a man 20 m off: listed, never looked at): the head rides the body. Its yaw was
            // eased in the WORLD even with no man to hold it on, so it chased the body's yaw from behind: turned
            // on the spot it was left 17 to 70 degrees back, and it hung 33 to the outside of a steered walk.
            float worstTurn = 0f, worstWalk = 0f;
            foreach (float hz in new[] { 30f, 60f, 120f }) {
                foreach (float deg in new[] { 45f, 90f, 135f, 180f, -90f }) {
                    Rig a = Looker(hz, out pad, out men, new Vector3(0f, 0f, 20f));
                    Scene.Step((int)Math.Round(hz * 0.5f));
                    a.Fighter.FaceTowards(Round(deg, 10f));
                    for (int i = 0; i < (int)Math.Round(hz * 1.5f); i++) { Scene.Step(); worstTurn = Math.Max(worstTurn, Math.Abs(HeadOnBody(a))); }
                }
                // walked at his own speed with the stick steered round 360 degrees a second, faced along it every frame as ReadInput faces him
                Rig w = Looker(hz, out pad, out men, new Vector3(0f, 0f, 20f));
                Scene.Step((int)Math.Round(hz * 0.5f));
                pad.Walk = true; pad.Turn = true;
                for (int i = 0; i < (int)Math.Round(hz * 3f); i++) {
                    pad.Way = Round(360f * i / hz, 1f);
                    Scene.Step();
                    worstWalk = Math.Max(worstWalk, Math.Abs(HeadOnBody(w)));
                }
            }
            Console.WriteLine("  nobody within the look's reach: turned on the spot the head is " + worstTurn.ToString("0.0") + " degrees at most off the body as it is drawn; walking a curve of 360 degrees a second, "
                + worstWalk.ToString("0.0"));
            Check(worstTurn < 0.5f, "with nobody to look at the head rides the body through a turn: within half a degree of the shoulders' own facing (45 to 180 degrees round, either way, at 30, 60 and 120 Hz)");
            Check(worstWalk < 0.5f, "...and through a steered walk: within half a degree at 360 degrees a second (30, 60 and 120 Hz)");
        }
        {
            // the man he looks at leaves the look's reach on the frame he is turned right round: the head comes
            // home against the body and never past it (in the world it swung through to 50 degrees on the far side)
            Rig a = Looker(60f, out pad, out men, new Vector3(2f, 0f, 0f));
            Scene.Step(90);
            float from = HeadOnBody(a), least = 999f, back = 0f, was = from, step = 0f, third = 0f;
            men[0].Root.transform.position = new Vector3(20f, 0f, 0f);
            a.Fighter.FaceTowards(new Vector3(0f, 0f, -10f));
            for (int i = 0; i < 90; i++) {
                Scene.Step();
                float h = HeadOnBody(a);
                least = Math.Min(least, h); back = Math.Max(back, h - was); step = Math.Max(step, was - h); was = h;
                if (i == 2) third = h;
            }
            Check(Math.Abs(from - FighterIK.LookMaxYaw) < 1f && least > -0.5f && back < 0.01f && Math.Abs(was) < 0.5f,
                  "a man who leaves the look's reach as he turns: the head comes home against the body, never back out and never past the front (its least " + least.ToString("0.0") + " degrees)");
            Check(step < 12f && third > 30f, "...over frames, as it looks: " + step.ToString("0.0") + " degrees in its largest frame, still " + third.ToString("0.0") + " off the front three frames on");
        }
        {
            // pure: the side held
            float side = 1f;
            bool held = FighterIK.LookHoldSide(179f, ref side) == FighterIK.LookMaxYaw && side == 1f
                     && FighterIK.LookHoldSide(-179f, ref side) == FighterIK.LookMaxYaw && side == 1f
                     && FighterIK.LookHoldSide(-(180f - FighterIK.LookRearBand) - 1f, ref side) == FighterIK.LookMaxYaw && side == 1f;
            bool let = FighterIK.LookHoldSide(-(180f - FighterIK.LookRearBand) + 1f, ref side) == -FighterIK.LookMaxYaw && side == -1f
                    && FighterIK.LookHoldSide(179f, ref side) == -FighterIK.LookMaxYaw && side == -1f;
            bool front = FighterIK.LookHoldSide(30f, ref side) == 30f && side == 1f && FighterIK.LookHoldSide(-30f, ref side) == -30f && side == -1f
                      && FighterIK.LookHoldSide(100f, ref side) == FighterIK.LookMaxYaw && side == 1f;
            float raw;
            bool gives = FighterIK.LookAngles(eye, Vector3.forward, new Vector3(-0.3f, 1.672f, -2f), out y, out p, out raw) && raw < -170f && raw > -173f && y == -FighterIK.LookMaxYaw;
            Check(held, "pure: a man who crosses the line straight behind is held over the shoulder the face is over, until he is LookRearBand past it");
            Check(let && front, "...past the band the face comes across to him; anywhere else it is the limit alone, on the side he is");
            Check(gives && FighterIK.LookRearBand > 5f && FighterIK.LookRearBand < 180f - FighterIK.LookMaxYaw - 30f,
                  "...and the band is a band: a few degrees of sway, not the whole of his back (LookAngles gives the yaw before the limit)");
        }
        {
            // a man 2 m straight behind who sways a centimetre either side of the line: the head stays over one
            // shoulder (it went across the front twelve times in 6 s, 21 degrees in a frame at 60 Hz)
            int crossings = 0; float travel = 0f; bool atLimit = true;
            foreach (float hz in new[] { 30f, 60f, 120f }) {
                Rig a = Looker(hz, out pad, out men, new Vector3(0.01f, 0f, -2f));
                Sweep s = new Sweep();
                for (int i = 0; i < (int)Math.Round(hz * 6f); i++) {
                    men[0].Root.transform.position = new Vector3(0.01f * Mathf.Cos(2f * Mathf.PI * i / hz), 0f, -2f);
                    Scene.Step(); s.Add(HeadOnBody(a));
                }
                crossings += s.Crossings; travel = Math.Max(travel, s.Travel);
                if (Math.Abs(Math.Abs(s.Last) - FighterIK.LookMaxYaw) > 1f) atLimit = false;
            }
            // ...and walking away from a man who follows straight behind, steering a little
            int walkCross = 0;
            {
                Rig a = Looker(60f, out pad, out men, new Vector3(0f, 0f, -1.5f));
                Scene.Step(30);
                pad.Walk = true; pad.Turn = true;
                Sweep s = new Sweep();
                for (int i = 0; i < 540; i++) {
                    pad.Way = Round(2f * Mathf.Sin(2f * Mathf.PI * 0.7f * i / 60f), 1f);
                    Vector3 to = a.Root.transform.position - men[0].Root.transform.position; to.y = 0f;
                    men[0].Root.transform.position = men[0].Root.transform.position + to.normalized * Math.Min(3.408f / 60f, Math.Max(0f, to.magnitude - 1.5f));
                    Scene.Step(); s.Add(HeadOnBody(a));
                }
                walkCross = s.Crossings;
            }
            Console.WriteLine("  a man straight behind who sways 1 cm: the head crosses the front " + crossings + " times in 6 s at 30, 60 and 120 Hz together and travels " + travel.ToString("0") + " degrees at most; followed on a steered walk, " + walkCross + " times in 9 s");
            Check(crossings == 0 && travel < 100f && atLimit, "a man straight behind who sways across the line does not swing the head across the front: it stays over one shoulder, at the limit (30, 60 and 120 Hz)");
            Check(walkCross == 0, "...nor does a man who follows him straight behind as he steers a walk");
        }
        {
            // he faces a man and is turned right round: the head goes to one shoulder and stays there. It went
            // to one shoulder and then, the turn done, swung through the front to the other (192 degrees
            // travelled here) -- unless the man stood 2 cm to the right of the line.
            bool stays = true; float most = 0f;
            foreach (float x in new[] { 0f, -0.02f, 0.02f }) {
                Rig a = Looker(60f, out pad, out men, new Vector3(x, 0f, 2f));
                Scene.Step(60);
                a.Fighter.FaceTowards(new Vector3(0f, 0f, -10f));
                Sweep s = new Sweep();
                for (int i = 0; i < 120; i++) { Scene.Step(); s.Add(HeadOnBody(a)); }
                if (s.Crossings > 0 || Math.Abs(Math.Abs(s.Last) - FighterIK.LookMaxYaw) > 1f) stays = false;
                most = Math.Max(most, s.Travel);
            }
            Check(stays && most < 75f, "turned his back on a man he faced, the head goes to one shoulder and stays: no swing back across the front once the turn is done (" + most.ToString("0") + " degrees travelled at most)");
        }
        {
            // a man walked round his back from one side to the other: the face comes across with him, once,
            // soon after he passes straight behind -- not held over the far shoulder until he is in front again
            Rig a = Looker(60f, out pad, out men, Round(-100f, 2f));
            Scene.Step(60);
            Sweep s = new Sweep(); float cameAt = 999f, bearing = -100f;
            for (int i = 0; i < 260; i++) {
                bearing = Math.Max(-300f, -100f - i);                  // 60 degrees a second, through 180 to +60, and stops there
                men[0].Root.transform.position = Round(bearing, 2f);
                Scene.Step(); float h = HeadOnBody(a); s.Add(h);
                if (cameAt > 900f && h > 1f) cameAt = FighterIK.WrapDegrees(bearing);
            }
            Console.WriteLine("  a man walked round his back at 60 degrees a second: the face comes across the front when he is at " + cameAt.ToString("0") + " degrees, " + s.Crossings + " time(s)");
            Check(s.Crossings == 1 && cameAt > 145f && cameAt <= 180f && Math.Abs(s.Last - 60f) < 2f,
                  "a man who walks round behind him takes the face across with him, once, within LookRearBand and a few frames of straight behind");
        }
        {
            // two men at one distance: the look is kept (the nearest by bare distance traded it 16 times in 10 s
            // for 2 cm, the head 120 degrees across each time), until one of them is clearly the nearer
            Rig a = Looker(60f, out pad, out men, Round(60f, 2f), Round(-60f, 2f));
            Sweep s = new Sweep();
            for (int i = 0; i < 600; i++) {
                float w = 0.02f * Mathf.Sin(2f * Mathf.PI * 0.8f * i / 60f);
                men[0].Root.transform.position = Round(60f, 2f + w); men[1].Root.transform.position = Round(-60f, 2f - w);
                Scene.Step(); s.Add(HeadOnBody(a));
            }
            float kept = s.Last;
            men[1].Root.transform.position = Round(-60f, 1.4f);
            Scene.Step(60);
            float taken = HeadOnBody(a);
            Console.WriteLine("  two men 60 degrees either side at 2 m, each 2 cm nearer in turn: the look changes side " + s.Crossings + " times in 10 s (" + s.Travel.ToString("0") + " degrees travelled)");
            Check(s.Crossings == 0 && Math.Abs(kept - 60f) < 2f, "two men at one distance do not trade the look: it stays on the one it is on");
            Check(Math.Abs(taken + 60f) < 2f, "...until the other is clearly the nearer (inside LookKeepShare of his distance): then it goes to him");
            // ...and a man who takes the look is looked at over his own shoulder, whichever the face was over
            Rig c = Looker(60f, out pad, out men, Round(170f, 2f), Round(-170f, 2.2f));
            Scene.Step(60);
            float first = HeadOnBody(c);
            men[1].Root.transform.position = Round(-170f, 1.2f);
            Scene.Step(60);
            Check(Math.Abs(first - FighterIK.LookMaxYaw) < 1f && Math.Abs(HeadOnBody(c) + FighterIK.LookMaxYaw) < 1f,
                  "...and another man who takes the look is looked at over his own shoulder, though both stand behind him");
        }
        {
            // the man looked at walks out past the look's reach while another stands inside it: the look
            // passes to the other without a frame of looking at nobody (kept without the reach, he held the
            // look from past it: 4.6 degrees back toward the front in that frame)
            Rig a = Looker(60f, out pad, out men, Round(30f, 6f), Round(60f, 8.5f));
            Scene.Step(90);
            float was = HeadOnBody(a), back = 0f, start = was;
            for (int i = 0; i < 300; i++) {
                men[0].Root.transform.position = Round(30f, 6f + 1.5f * i / 60f);
                Scene.Step();
                float h = HeadOnBody(a); back = Math.Max(back, was - h); was = h;
            }
            Check(Math.Abs(start - 30f) < 1f && Math.Abs(was - 60f) < 1f && back < 0.5f,
                  "the man looked at walks out of the look's reach: the look passes to the next man inside it, never a frame back toward the front (" + back.ToString("0.00") + " degrees at most)");
        }
        Scene.DeltaTime = 1f / 60f;
    }

    static void Strikes() {
        Console.WriteLine("\nSTRIKES");
        LoadRows();
        AttackRow jab = GameData.Attack("Jab"), kick = GameData.Attack("Kick");
        Check(jab != null && kick != null && Math.Abs(jab.startup - 0.07f) < 1e-4f && Math.Abs(kick.reach - 1.776f) < 1e-3f,
              "(the rows are attacks.json's: the jab's 0.07 s startup, the kick's 1.776 m reach)");

        // (1) a punch pressed with the guard up leaves from the guard. Until 2026-11-10 the
        // strike blended from the hand's A-pose rest point: the fist went 49 to 66 cm down
        // and back in the first frame it had any weight (64.3 cm for a jab at 120 Hz,
        // against 22.0 for the same jab from hands down).
        float f0, fz, wh;
        bool leaves = true; float worstRatio = 0f;
        foreach (float leftX in new[] { 1f, -1f })
            foreach (string row in new[] { "Jab", "Cross", "Hook" })
                foreach (float hz in new[] { 30f, 60f, 120f }) {
                    float fromRest = Throw(hz, row, false, -1f, out f0, out fz, out wh, leftX);
                    float fromGuard = Throw(hz, row, true, -1f, out f0, out fz, out wh, leftX);
                    worstRatio = Math.Max(worstRatio, fromGuard / fromRest);
                    if (fromGuard > 1.1f * fromRest) leaves = false;
                    if (hz == 120f) Console.WriteLine("  " + row + " at 120 Hz" + (leftX > 0f ? "" : " (the other layout)") + ": the fist's largest frame is "
                        + (fromGuard * 100).ToString("0.0") + " cm out of the guard, " + (fromRest * 100).ToString("0.0") + " cm from hands down");
                }
        Check(leaves, "a punch pressed with the guard up leaves from the guard: no frame of it faster than 1.1 x the same punch from hands down ("
              + worstRatio.ToString("0.00") + " x at worst; jab, cross and hook at 30, 60 and 120 Hz, either layout of the arms)");
        {
            // ...and it lands where it always did
            Vector3[] at = new Vector3[2];
            for (int g = 0; g < 2; g++) {
                StrikePad pad; Rig r = Fighter(60f, out pad);
                if (g == 1) { pad.HoldBlock = true; Scene.Step(30); } else Scene.Step(6);
                pad.Press = "Jab"; Scene.Step(1 + (int)Math.Round(60f * (jab.startup + 0.5f * jab.active)));
                at[g] = r.Bones["hand_l"].position;
            }
            Check((at[0] - at[1]).magnitude < 1e-3f && at[0].z > 0.5f, "...and at its contact frame the fist is where the punch from hands down has it");
        }

        // (2) hit in the middle of his own swing. Until 2026-11-10 the limb was back at the
        // guard or the floor on the frame of the blow (94 cm for a punch, 125 for a kick),
        // and hit stop then held that snapped pose.
        bool held = true, eased = true; float worstShare = 0f;
        foreach (string row in new[] { "Jab", "Cross", "Kick", "Knee" })
            foreach (float hz in new[] { 30f, 60f, 120f }) {
                AttackRow a = GameData.Attack(row);
                float worst = Throw(hz, row, false, a.startup + 0.5f * a.active, out f0, out fz, out wh);
                if (fz > 0.005f) held = false;
                // a smooth step over LetGoSeconds: its steepest frame is 1.5 dt / LetGoSeconds of the way
                if (wh < 0.5f || worst > wh * (1.5f / (hz * FighterIK.LetGoSeconds) + 0.1f)) eased = false;
                worstShare = Math.Max(worstShare, worst / wh);
                if (hz == 60f && (row == "Jab" || row == "Kick"))
                    Console.WriteLine("  hit in his " + row + " at 60 Hz: the limb is " + (wh * 100).ToString("0.0") + " cm from where it ends; through hit stop it moves "
                        + (fz * 100).ToString("0.00") + " cm; its largest frame after is " + (worst * 100).ToString("0.0") + " cm");
            }
        Check(held, "hit in the middle of his own swing, the limb is held where it was struck through hit stop (under 0.5 cm; jab, cross, kick and knee at 30, 60 and 120 Hz)");
        Check(eased, "...and is let go over LetGoSeconds after, never the whole way in a frame (" + (worstShare * 100).ToString("0") + " % of the way in the worst frame, at 30 Hz)");
        Check(FighterIK.LetGo(1f, 1f / 60f, true) == 1f && Math.Abs(FighterIK.LetGo(1f, 0.05f, false) - 0.5f) < 1e-5f && FighterIK.LetGo(0.1f, 1f, false) == 0f,
              "the let-go's share stands through hit stop, runs out in LetGoSeconds, and stops at nothing");

        // (3) a kick pressed out of a walk. Until 2026-11-10 the kicking foot was let go to
        // its rest point on the kick's first frame, the strike's weight still nothing: 33.7 cm.
        bool stays = true;
        foreach (float hz in new[] { 30f, 60f, 120f }) {
            float worstFirst = 0f, sum = 0f;
            for (int k = 0; k < 24; k++) {
                StrikePad pad; Rig r = Fighter(hz, out pad);
                pad.Walk = true;
                Scene.Step((int)Math.Round(hz * (1.0f + k * 0.02f)));
                Vector3 before = r.Bones["foot_r"].position;
                pad.Press = "Kick";
                Scene.Step();
                float d = (r.Bones["foot_r"].position - before).magnitude;
                worstFirst = Math.Max(worstFirst, d); sum += d;
            }
            if (worstFirst > 0.08f) stays = false;
            if (hz == 60f) Console.WriteLine("  a kick out of a 3.408 m/s walk at 60 Hz, 24 moments of the stride: the kicking foot moves "
                + (worstFirst * 100).ToString("0.0") + " cm at most on the kick's first frame, " + (sum / 24f * 100).ToString("0.0") + " on average");
        }
        Check(stays, "a kick pressed out of a walk leaves from where the foot stands: under 8 cm on the kick's first frame, at 30, 60 and 120 Hz");

        // ...and it comes back under him (2026-11-11). The foot's hold stayed where the walk had left it
        // for the whole kick -- up to 34 cm behind -- and the lunge carried him 15 cm further: the kick came
        // back to a point 41 cm behind its hip on a locked leg, and the hips fell 9.7 cm in the one frame
        // the leg stopped striking (13.3 with the stick still held). The same 24 moments, each kick and
        // knee followed through and 0.6 s on, with the stick let go at the press and with it held.
        float worstBehind = 0f, worstFall = 0f, worstFallOn = 0f;
        foreach (string row in new[] { "Kick", "Knee" })
            foreach (float hz in new[] { 30f, 60f, 120f })
                foreach (bool walksOn in new[] { false, true })
                    for (int k = 0; k < 24; k++) {
                        StrikePad pad; Rig r = Fighter(hz, out pad);
                        pad.Walk = true;
                        Scene.Step((int)Math.Round(hz * (1.0f + k * 0.02f)));
                        pad.Press = row;
                        Scene.Step();
                        pad.Walk = walksOn;
                        float hipWas = r.Bones["thigh_r"].position.y, behind = 0f, fall = 0f; int after = 0;
                        for (int i = 0; i < 4 * (int)hz && after < (int)Math.Round(hz * 0.6f); i++) {
                            Scene.Step();
                            Vector3 hip = r.Bones["thigh_r"].position, foot = r.Bones["foot_r"].position;
                            // (the last frame of the swing is the last this is read on)
                            if (r.Fighter.State == FighterState.Attack) behind = (float)Math.Sqrt((foot.x - hip.x) * (foot.x - hip.x) + (foot.z - hip.z) * (foot.z - hip.z));
                            else { fall = Math.Max(fall, hipWas - hip.y); after++; }
                            hipWas = hip.y;
                        }
                        worstBehind = Math.Max(worstBehind, behind);
                        if (walksOn) worstFallOn = Math.Max(worstFallOn, fall); else worstFall = Math.Max(worstFall, fall);
                    }
        Console.WriteLine("  ...followed through, kick and knee at 30, 60 and 120 Hz: on the swing's last frame the kicking ankle is " + (worstBehind * 100).ToString("0.0")
            + " cm at most from under its hip; after it the hips fall " + (worstFall * 100).ToString("0.0") + " cm at most in a frame with the stick let go, "
            + (worstFallOn * 100).ToString("0.0") + " walking on");
        Check(worstBehind < 0.08f, "...and the kick brings the foot back under him: on the swing's last frame the ankle is within 8 cm of under its hip (kick and knee, 30, 60 and 120 Hz)");
        Check(worstFall < 0.01f && worstFallOn < 0.04f, "...so the hips do not fall when the leg stops striking: under 1 cm in a frame with the stick let go at the press, under 4 walking on");

        // (4) a swing that ends into a turn (2026-11-11). The stick held round while he swings turns him on
        // the frame the swing ends (ReadInput: FaceTowards(position + wish), the first frame he is free), and
        // every swing ends through the let-go. Its point was kept in the root's own frame, which that turn
        // snaps, while the body is drawn round after it: at a half turn the hand was thrown 93 cm across the
        // drawn body in that frame (63 cm at 90 degrees, 34 at 45), the arm at full stretch through the chest.
        bool rides = true; float worstOver = 0f, straight60 = 0f, half60 = 0f, an, nearest = 1f;
        foreach (float leftX in new[] { 1f, -1f })
            foreach (float hz in new[] { 30f, 60f, 120f }) {
                foreach (string row in new[] { "Jab", "Cross" }) {
                    float straight = EndsInto(row, 0f, hz, leftX, out an);
                    foreach (float deg in new[] { 45f, 90f, 180f }) {
                        float off = EndsInto(row, deg, hz, leftX, out an);
                        worstOver = Math.Max(worstOver, off - straight);
                        if (off > straight + 0.02f) rides = false;
                        if (row == "Jab" && hz == 60f && leftX > 0f && deg == 180f) { straight60 = straight; half60 = off; }
                    }
                }
                // a kick's foot rode the root's frame too: into a turn it was brought across onto the standing foot
                foreach (string row in new[] { "Kick", "Knee" })
                    foreach (float deg in new[] { 90f, 135f, 180f }) { EndsInto(row, deg, hz, leftX, out an); nearest = Math.Min(nearest, an); }
            }
        Console.WriteLine("  a jab that ends into a half turn at 60 Hz: its hand is " + (half60 * 100).ToString("0.0") + " cm at most from its rest place on the drawn body ("
            + (straight60 * 100).ToString("0.0") + " ended straight on); a kick or knee into a turn: the ankles are " + (nearest * 100).ToString("0.0") + " cm apart at the nearest");
        Check(rides, "a swing that ends into a turn keeps its hand on the body as it is drawn: no further from its rest place there than the same swing ended straight on, plus 2 cm ("
              + (worstOver * 100).ToString("0.0") + " cm over at worst; jab and cross into 45, 90 and 180 degrees at 30, 60 and 120 Hz, either layout)");
        Check(nearest > 0.06f, "...and a kick that ends into a turn keeps its foot off the standing foot: the ankles never nearer than 6 cm (kick and knee into 90, 135 and 180 degrees at 30, 60 and 120 Hz, either layout)");
        {
            // ...and a swing begun with a turn and taken away still holds where it was struck: thrown at a man
            // behind him (faced round and the jab started on that frame, as Punch does) and hit 0.03 s in, with
            // 72 degrees of the body's turn still to come at 60 Hz
            float worstBlow = 0f, worstStop = 0f; bool struck = true;
            foreach (float leftX in new[] { 1f, -1f })
                foreach (float hz in new[] { 30f, 60f, 120f }) {
                    StrikePad pad; Rig r = Fighter(hz, out pad, leftX);
                    Scene.Step((int)Math.Round(hz * 0.1f));
                    pad.Way = new Vector3(0f, 0f, -1f); pad.Turn = true;
                    pad.Press = "Jab"; pad.HitAt = hz < 45f ? 0.04f : 0.03f;       // (a frame of the jab has been drawn before the blow)
                    Vector3 prev = r.Bones["hand_l"].position, atBlow = prev; bool was = false;
                    for (int i = 0; i < 60; i++) {
                        Scene.Step();
                        Vector3 q = r.Bones["hand_l"].position;
                        if (pad.Struck && !was) { worstBlow = Math.Max(worstBlow, (q - prev).magnitude); atBlow = q; was = true; }
                        else if (was && r.Fighter.Frozen) worstStop = Math.Max(worstStop, (q - atBlow).magnitude);
                        else if (was) break;
                        prev = q;
                    }
                    if (!was) struck = false;
                }
            Console.WriteLine("  a jab begun with a half turn and taken away: its hand moves " + (worstBlow * 100).ToString("0.0") + " cm on the frame of the blow, "
                + (worstStop * 100).ToString("0.00") + " through hit stop");
            Check(struck && worstBlow < 0.01f && worstStop < 0.005f, "...and a swing begun with a half turn and taken away is still held where it was struck: under 1 cm on the frame of the blow, under 0.5 through hit stop (30, 60 and 120 Hz, either layout)");
        }
        Scene.DeltaTime = 1f / 60f;

        // ------------------------------------------------- 2026-11-10: the turn
        Console.WriteLine("\nTURN");
        {
            // pure: a half turn is never more than TurnMaxDegrees a second, lands the same at any rate, arrives
            float[] at02 = new float[3]; bool capped = true; int n = 0;
            foreach (float hz in new[] { 30f, 60f, 120f }) {
                float y = 0f, t = 0f;
                while (t < 0.2f - 1e-4f) {
                    float was = y; y = FighterIK.TurnLag(y, 180f, 1f / hz, false); t += 1f / hz;
                    if (Math.Abs(y - was) > FighterIK.TurnMaxDegrees / hz + 1e-3f) capped = false;
                }
                at02[n++] = y;
            }
            Console.WriteLine("  a half turn, 0.2 s on: " + at02[0].ToString("0.0") + " / " + at02[1].ToString("0.0") + " / " + at02[2].ToString("0.0") + " degrees at 30 / 60 / 120 Hz");
            Check(capped, "a half turn is drawn no faster than TurnMaxDegrees a second: 36, 18 and 9 degrees a frame at 30, 60 and 120 Hz");
            Check(Math.Abs(at02[0] - at02[1]) < 6f && Math.Abs(at02[2] - at02[1]) < 3f && at02[1] > 150f, "...and is in about the same place 0.2 s on at any frame rate");
            float end = 0f; for (int i = 0; i < 60; i++) end = FighterIK.TurnLag(end, 180f, 1f / 60f, false);
            float quick = FighterIK.TurnLag(0f, 180f, 1f / 60f, true), slow = FighterIK.TurnLag(0f, 180f, 1f / 60f, false);
            Check(Math.Abs(end - 180f) < 1e-3f && FighterIK.TurnLag(40f, 180f, 0f, false) == 40f, "...it arrives, and a frame of no time turns nothing");
            Check(Math.Abs(quick - 3f * slow) < 1e-3f, "...three times quicker inside an attack");
            float round = FighterIK.TurnLag(170f, -170f, 1f / 60f, false), back = FighterIK.TurnLag(-170f, 170f, 1f / 60f, false);
            Check(round > 170f && round < 190f && back < -170f && back > -190f
                  && Math.Abs(FighterIK.WrapDegrees(370f) - 10f) < 1e-4f && Math.Abs(FighterIK.WrapDegrees(-190f) - 170f) < 1e-4f,
                  "...and it goes the shorter way round, either way");
        }
        foreach (float leftX in new[] { 1f, -1f }) {
            // through the rig: he stands, and is turned on the spot as FaceTowards turns him
            string lay = leftX > 0f ? "" : " (the other layout)";
            foreach (float deg in new[] { 180f, 90f, 45f }) {
                bool crossed = false; float firstTurn = 0f, offL = 0f, offR = 0f, worstRate = 0f, closest = 1f;
                foreach (float hz in new[] { 30f, 60f, 120f }) {
                    StrikePad pad; Rig r = Fighter(hz, out pad, leftX);
                    Scene.Step((int)Math.Round(hz * 0.3f));
                    Vector3 was = r.Bones["upperarm_l"].position - r.Bones["upperarm_r"].position;
                    float rad = deg * Mathf.Deg2Rad;
                    r.Fighter.FaceTowards(new Vector3(10f * Mathf.Sin(rad), 0f, 10f * Mathf.Cos(rad)));
                    int frames = (int)Math.Round(hz);
                    for (int i = 1; i <= frames; i++) {
                        Scene.Step();
                        Vector3 sh = r.Bones["upperarm_l"].position - r.Bones["upperarm_r"].position;
                        float turned = Vector3.Angle(new Vector3(was.x, 0f, was.z), new Vector3(sh.x, 0f, sh.z));
                        worstRate = Math.Max(worstRate, turned * hz);
                        if (i == 1 && hz == 60f) firstTurn = turned;
                        was = sh;
                        // crossed: the left foot on the right of the right foot, across the body as it is drawn
                        Vector3 across = new Vector3(sh.x, 0f, sh.z).normalized;
                        Vector3 apart = r.Bones["foot_l"].position - r.Bones["foot_r"].position; apart.y = 0f;
                        if (Vector3.Dot(apart, across) < -0.02f) crossed = true;
                        closest = Math.Min(closest, apart.magnitude);
                    }
                    if (hz == 60f) {
                        offL = Math.Abs(Vector3.Dot(r.Bones["foot_l"].position - r.Bones["thigh_l"].position, new Vector3(1f, 0f, 0f)))
                             + Math.Abs(Vector3.Dot(r.Bones["foot_l"].position - r.Bones["thigh_l"].position, new Vector3(0f, 0f, 1f)));
                        offR = Math.Abs(Vector3.Dot(r.Bones["foot_r"].position - r.Bones["thigh_r"].position, new Vector3(1f, 0f, 0f)))
                             + Math.Abs(Vector3.Dot(r.Bones["foot_r"].position - r.Bones["thigh_r"].position, new Vector3(0f, 0f, 1f)));
                    }
                }
                Console.WriteLine("  turned " + deg.ToString("0") + " degrees on the spot" + lay + ": the shoulders turn " + firstTurn.ToString("0.0")
                    + " degrees in the first frame at 60 Hz, " + worstRate.ToString("0") + " degrees a second at most; a second on the ankles are "
                    + (offL * 100).ToString("0.0") + " and " + (offR * 100).ToString("0.0") + " cm from under their hips");
                Check(worstRate <= FighterIK.TurnMaxDegrees * 1.02f && firstTurn < 20f,
                      "turned " + deg.ToString("0") + " degrees" + lay + ", the body is drawn round at no more than TurnMaxDegrees a second, under 20 degrees in the first frame at 60 Hz");
                Check(!crossed, "...and his legs never cross" + lay + " (" + deg.ToString("0") + ")");
                Check(closest > 0.06f, "...his feet go round with the body, never through each other" + lay + " (" + deg.ToString("0") + ": "
                      + (closest * 100).ToString("0.0") + " cm apart at the nearest, 16.4 at rest)");
                Check(offL < 0.035f && offR < 0.035f, "...and a second on both feet have stepped back under him" + lay + " (" + deg.ToString("0") + ")");
            }
            {
                // a guard held through a half turn stays in front of the chest as it is drawn
                StrikePad pad; Rig r = Fighter(60f, out pad, leftX);
                pad.HoldBlock = true; Scene.Step(40);
                r.Fighter.FaceTowards(new Vector3(0f, 0f, -10f));
                float least = 1f;
                for (int i = 0; i < 30; i++) {
                    Scene.Step();
                    Vector3 sh = r.Bones["upperarm_l"].position - r.Bones["upperarm_r"].position;
                    // the chest's forward: across the shoulders, turned a quarter; its sign from the first frame (he faced +Z)
                    Vector3 fwd = new Vector3(-sh.z, 0f, sh.x).normalized * (leftX > 0f ? 1f : -1f);
                    Vector3 mid = (r.Bones["upperarm_l"].position + r.Bones["upperarm_r"].position) * 0.5f;
                    foreach (string h in new[] { "hand_l", "hand_r" })
                        least = Math.Min(least, Vector3.Dot(r.Bones[h].position - mid, fwd));
                }
                Check(least > 0.10f, "a guard held through a half turn stays in front of the chest as it is drawn" + lay + " (" + (least * 100).ToString("0.0") + " cm at least)");
            }
            {
                // hit stop holds the turn; put somewhere new, he faces the new way at once
                StrikePad pad; Rig r = Fighter(60f, out pad, leftX);
                Scene.Step(10);
                Vector3 was = r.Bones["upperarm_l"].position - r.Bones["upperarm_r"].position;
                r.Fighter.Freeze(0.1f);
                r.Fighter.FaceTowards(new Vector3(0f, 0f, -10f));
                Scene.Step(4);
                Vector3 now = r.Bones["upperarm_l"].position - r.Bones["upperarm_r"].position;
                Check(Vector3.Angle(was, now) < 0.5f, "through hit stop the body is not drawn round" + lay);
                Scene.Step(60);
                r.Root.transform.position = new Vector3(8f, 0f, 3f);
                r.Fighter.FaceTowards(new Vector3(8f, 0f, 13f));
                Scene.Step();
                now = r.Bones["upperarm_l"].position - r.Bones["upperarm_r"].position;
                Check(Vector3.Angle(was, now) < 0.5f, "put somewhere new and turned, he faces the new way on that frame" + lay);
            }
        }
        Scene.DeltaTime = 1f / 60f;
    }

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

        Strikes();
        Aim();
        Block();
        Look();

        Console.WriteLine(fails == 0 ? "\nall pose checks passed" : "\n" + fails + " FAILURES");
        return fails == 0 ? 0 : 1;
    }
}
