using System; using UnityEngine; using Ahmed.Combat; using Ahmed.Data;
public static class IKTest {
    static int fails = 0;
    static void Check(bool ok, string w) { if (!ok) { fails++; Console.WriteLine("  FAIL " + w); } }
    public static int Main() {
        var rng = new System.Random(1234);
        Func<float, float, float> R = (a, b) => (float)(a + rng.NextDouble() * (b - a));
        // A leg: hip at 0.952, knee 0.439 down, ankle 0.443 further, as the joint table has it.
        Vector3 hip = new Vector3(0.092f, 0.952f, 0f), knee = new Vector3(0.088f, 0.513f, -0.012f), ankle = new Vector3(0.082f, 0.070f, 0f);
        float upper = (knee - hip).magnitude, lower = (ankle - knee).magnitude, reach = upper + lower;
        int reachable = 0, unreachable = 0; float worstEnd = 0, worstLen = 0, worstPole = 1f;
        for (int i = 0; i < 10000; i++) {
            Vector3 dir = new Vector3(R(-1,1), R(-1,1), R(-1,1)).normalized;
            float dist = R(0.05f, reach * 1.3f);
            Vector3 target = hip + dir * dist;
            Vector3 pole = hip + new Vector3(R(-1,1), R(-1,1), R(-1,1)).normalized * 0.6f;
            Vector3 m, e; TwoBoneIK.Solve(hip, knee, ankle, target, pole, out m, out e);
            worstLen = Math.Max(worstLen, Math.Max(Math.Abs((m - hip).magnitude - upper), Math.Abs((e - m).magnitude - lower)));
            if (dist <= reach - 1e-4f && dist >= Math.Abs(upper - lower) + 1e-4f) {
                reachable++; worstEnd = Math.Max(worstEnd, (e - target).magnitude);
                // the joint must be on the pole's side of the hip-target line
                Vector3 axis = (target - hip).normalized;
                Vector3 bend = m - hip; bend -= axis * Vector3.Dot(bend, axis);
                Vector3 pv = pole - hip; pv -= axis * Vector3.Dot(pv, axis);
                if (pv.magnitude > 1e-3f && bend.magnitude > 1e-3f) worstPole = Math.Min(worstPole, Vector3.Dot(bend.normalized, pv.normalized));
            } else if (dist > reach) {
                unreachable++;
                Vector3 axis = (target - hip).normalized;
                Check(Vector3.Dot((e - hip).normalized, axis) > 0.99999f, "unreachable: limb points at the target");
                Check(Math.Abs((e - hip).magnitude - reach) < 1e-4f, "unreachable: limb is straight at full reach");
            }
        }
        Console.WriteLine("SOLVER  " + reachable + " reachable targets, worst end error " + (worstEnd*1000).ToString("0.000") + " mm, worst length drift " + (worstLen*1000).ToString("0.000") + " mm, worst pole-side dot " + worstPole.ToString("0.000") + "; " + unreachable + " unreachable, all straight and aimed");
        Check(worstEnd < 1e-3f, "end within 1 mm"); Check(worstLen < 1e-4f, "bone lengths kept"); Check(worstPole > 0.999f, "joint on the pole side");
        // adversarial cases
        Vector3 m2, e2;
        TwoBoneIK.Solve(hip, knee, ankle, hip, hip + Vector3.forward, out m2, out e2); Check(!float.IsNaN(m2.x) && !float.IsNaN(e2.x), "target at the root: no NaN");
        // The fold radius. Inside |a-b| of the root nothing is reachable, and
        // the law of cosines has no answer there: x runs away as d goes to
        // zero. This used to send the joint hundreds of metres off with no
        // NaN and no exception, so "no NaN" was never the check that mattered
        // -- the limb has to stay attached and stay its own length.
        {
            Vector3 sh = new Vector3(0.178f, 1.442f, 0f);
            Vector3 el = sh + new Vector3(0.335f, 0f, 0f);      // uneven bones, so the
            Vector3 wr = el + new Vector3(0f, -0.263f, 0f);     // dead sphere is real
            float u = (el-sh).magnitude, l = (wr-el).magnitude, fold = Math.Abs(u-l);
            float worstAttach = 0f, foldLen = 0f, worstReach = 0f;
            for (int i = 0; i < 2000; i++) {
                float f = (float)rng.NextDouble() * fold * 1.2f;     // straddle the radius
                Vector3 dir = new Vector3((float)rng.NextDouble()*2-1,(float)rng.NextDouble()*2-1,(float)rng.NextDouble()*2-1);
                if (dir.magnitude < 1e-4f) continue;
                Vector3 tgt = sh + dir.normalized * f;
                Vector3 mm, ee; TwoBoneIK.Solve(sh, el, wr, tgt, sh + Vector3.forward, out mm, out ee);
                Check(!float.IsNaN(mm.x) && !float.IsInfinity(mm.x) && !float.IsNaN(ee.x), "fold: finite");
                worstAttach = Math.Max(worstAttach, Math.Abs((mm-sh).magnitude - u));
                foldLen = Math.Max(foldLen, Math.Abs((ee-mm).magnitude - l));
                worstReach = Math.Max(worstReach, Math.Max(0f, fold - (ee-sh).magnitude - 1e-3f));
            }
            Check(worstAttach < 1e-3f, "fold: the upper bone keeps its length (" + worstAttach.ToString("0.000000") + ")");
            Check(foldLen < 1e-3f, "fold: the lower bone keeps its length (" + foldLen.ToString("0.000000") + ")");
            Check(worstReach < 1e-3f, "fold: the end never lands inside the dead sphere");
            Console.WriteLine("  fold radius " + fold.ToString("0.000") + " m, 2000 targets inside it: joint stays attached to "
                + worstAttach.ToString("0.000000") + " m");
        }
        TwoBoneIK.Solve(hip, knee, ankle, hip + Vector3.down * reach, hip + Vector3.down, out m2, out e2); Check(!float.IsNaN(m2.x), "pole on the line: no NaN");
        TwoBoneIK.Solve(hip, knee, ankle, hip + Vector3.down * (reach - 1e-6f), hip + Vector3.forward, out m2, out e2); Check(Math.Abs((e2-hip).magnitude - reach) < 1e-3f, "target exactly at reach");
        Vector3 t = new Vector3(0,0,0), tm = new Vector3(0,0,0.001f), te = new Vector3(0,0,0.002f);
        TwoBoneIK.Solve(t, tm, te, new Vector3(0,0,0.0015f), new Vector3(0,1,0), out m2, out e2); Check(Math.Abs((e2 - new Vector3(0,0,0.0015f)).magnitude) < 1e-5f, "millimetre limb");
        // the strike timeline for every attack row at 60 Hz
        // The six rows as attacks.json has them today (startup, active, recovery, reach).
        var rows = new AttackRow[] {
            new AttackRow{name="Jab",startup=0.07f,active=0.06f,recovery=0.13f,reach=1.296f},
            new AttackRow{name="Cross",startup=0.10f,active=0.07f,recovery=0.19f,reach=1.44f},
            new AttackRow{name="Hook",startup=0.14f,active=0.08f,recovery=0.26f,reach=1.344f},
            new AttackRow{name="Kick",startup=0.16f,active=0.09f,recovery=0.28f,reach=1.776f},
            new AttackRow{name="Knee",startup=0.13f,active=0.08f,recovery=0.26f,reach=1.008f},
            new AttackRow{name="Special",startup=0.18f,active=0.26f,recovery=0.34f,reach=2.112f} };
        foreach (AttackRow a in rows) {
            string row = a.name; bool arm, rear; Check(FighterIK.StrikeLimb(row, out arm, out rear), row + " has a limb");
            bool right = FighterIK.IsRightSide(rear, false);
            float total = a.startup + a.active + a.recovery; bool ok = true; float maxW = 0;
            for (float tt = 0; tt <= total + 0.05f; tt += 1f/60f) {
                float w = FighterIK.StrikeWeight(tt, a.startup, a.active, a.recovery); maxW = Math.Max(maxW, w);
                if (tt >= a.startup && tt < a.startup + a.active && w < 0.9999f) ok = false;
                if (tt >= total && w > 0f) ok = false;
                if (w < 0f || w > 1f) ok = false;
            }
            Check(FighterIK.StrikeWeight(0f, a.startup, a.active, a.recovery) == 0f, row + " weight 0 at the start");
            Check(ok, row + ": full reach across the active window, back to rest by the end of recovery");
            Vector3 full = FighterIK.StrikeTarget(Vector3.zero, Vector3.right, a.reach, arm ? FighterIK.ShoulderHeight : FighterIK.HipHeight);
            Check(Math.Abs(full.x - a.reach) < 1e-6f, row + " lands at its reach");
            Console.WriteLine("TIMELINE " + row.PadRight(8) + (arm ? (right ? "right hand" : "left hand ") : "right leg ") + "  startup " + a.startup.ToString("0.000") + " active " + a.active.ToString("0.000") + " recovery " + a.recovery.ToString("0.000") + "  reach " + a.reach.ToString("0.00") + " m  ok");
        }
        // ---- stance: orthodox must be exactly what shipped before, southpaw its mirror
        Console.WriteLine("\nSTANCE");
        var wasRight = new System.Collections.Generic.Dictionary<string,bool>{
            {"Jab",false},{"Hook",false},{"Cross",true},{"Special",true},{"Knee",true},{"Kick",true}};
        foreach (var kv in wasRight) {
            bool arm2, rear2; FighterIK.StrikeLimb(kv.Key, out arm2, out rear2);
            Check(FighterIK.IsRightSide(rear2, false) == kv.Value, kv.Key + ": orthodox unchanged");
            Check(FighterIK.IsRightSide(rear2, true) == !kv.Value, kv.Key + ": southpaw mirrors it");
        }
        Check(!FighterIK.Southpaw(null) && !FighterIK.Southpaw(""), "no archetype means orthodox (Ahmed)");
        string[] roster = {"Thug","Brawler","Kicker","Grappler","Champ","Runner","Bouncer","Capo","Boss","Saqr"};
        int south = 0; var line = "";
        foreach (string r in roster) {
            bool sp = FighterIK.Southpaw(r);
            Check(sp == FighterIK.Southpaw(r), r + ": stance is stable");
            if (sp) south++;
            line += r + (sp ? ":southpaw  " : ":orthodox  ");
        }
        Console.WriteLine("  " + line);
        Check(south > 0 && south < roster.Length, "the roster is not all one stance (" + south + " of " + roster.Length + " southpaw)");

        // ---- guard: reachable, in front, at the chin, and symmetric
        Console.WriteLine("\nGUARD");
        Vector3 fwd = new Vector3(0,0,1), sideR = Vector3.Cross(Vector3.up, fwd);
        Check(Math.Abs(sideR.x - 1f) < 1e-6f, "cross(up, forward) is the fighter's right");
        Vector3 gR = FighterIK.GuardTarget(Vector3.zero, fwd, sideR);
        Vector3 gL = FighterIK.GuardTarget(Vector3.zero, fwd, -sideR);
        Check(Math.Abs(gR.y - FighterIK.GuardHeight) < 1e-6f && gR.y > FighterIK.ShoulderHeight, "guard sits above the shoulder");
        Check(gR.z > 0.1f, "guard is in front of the fighter");
        Check(Math.Abs(gR.x + gL.x) < 1e-6f && Math.Abs(gR.x) > 0.05f, "hands are either side and symmetric");
        // the arm has to be able to get there: shoulder and wrist from the joint table
        Vector3 shoulderR = new Vector3(0.178f, 1.442f, 0f);
        Vector3 elbowR = new Vector3(0.415f, 1.205f, 0f), wristR = new Vector3(0.601f, 1.019f, 0f);
        float armReach = (elbowR-shoulderR).magnitude + (wristR-elbowR).magnitude;
        float need = (gR - shoulderR).magnitude;
        Check(need < armReach * 0.95f, "guard is inside arm reach (" + need.ToString("0.000") + " m of " + armReach.ToString("0.000") + ")");
        Vector3 gm, ge;
        TwoBoneIK.Solve(shoulderR, elbowR, wristR, gR, (shoulderR+gR)*0.5f - Vector3.up*0.6f, out gm, out ge);
        Check((ge - gR).magnitude < 1e-3f, "the solver puts the fist on the guard target");
        Check(Math.Abs((gm-shoulderR).magnitude - (elbowR-shoulderR).magnitude) < 1e-4f, "guard keeps the upper arm's length");
        Console.WriteLine("  guard target " + gR + "  reach used " + (need/armReach*100f).ToString("0") + "% of the arm");

        Console.WriteLine(fails == 0 ? "\nall IK checks passed" : "\n" + fails + " FAILURES");
        return fails == 0 ? 0 : 1;
    }
}
