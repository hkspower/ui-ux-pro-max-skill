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
    void Update() {
        F.Blocking = HoldBlock && !F.IsBusy;
        if (!F.IsBusy) {
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
    static Rig BuildFighter(string name, Vector3 at, float size, float leftX, bool aims = false) {
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

    static void Vitals(Rig r) {
        typeof(Fighter).GetMethod("InitialiseVitals", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)
            .Invoke(r.Fighter, new object[] { 1000f, 9999f });
    }

    // A striker of his own size at the origin facing +Z, and (hisSize > 0) a man standing at `at`.
    // The row is thrown and the scene stepped to its first active frame: the frame the blow lands.
    static Rig Land(string row, float mySize, Vector3 at, float hisSize, out Rig him) {
        Scene.Reset(); Scene.DeltaTime = 1f / 60f;
        Slab("Ground", new Vector3(0f, -0.5f, 0f), new Vector3(2000f, 1f, 2000f));
        Rig r = BuildFighter("Striker", Vector3.zero, mySize, 1f, true);
        StrikePad pad = r.Root.AddComponent<StrikePad>(); pad.F = r.Fighter;
        Vitals(r);
        r.Fighter.FaceTowards(new Vector3(0f, 0f, 10f));
        him = null;
        if (hisSize > 0f) {
            him = BuildFighter("Him", at, hisSize);
            Vitals(him);
            ((AimFighter)r.Fighter).Them.Add(him.Fighter);
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
                    Transform mesh = r.Root.transform.Find("Mesh");
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

        Console.WriteLine(fails == 0 ? "\nall pose checks passed" : "\n" + fails + " FAILURES");
        return fails == 0 ? 0 : 1;
    }
}
