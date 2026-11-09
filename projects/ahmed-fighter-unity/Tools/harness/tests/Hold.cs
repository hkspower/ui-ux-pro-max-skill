using System; using UnityEngine; using Ahmed.Combat;
// The feet held (FighterIK.HoldFoot, 2026-10-31, after the Unreal build's
// SaudIK feet): planted where it first stands; held there, not sliding, while
// he carries its rest point less than StepDrift; then a step after him that
// lifts in the middle and lands on its rest point, held again; one foot at a
// time unless the standing one is carried ForceDrift; a jump of SnapDrift
// re-plants it at once; hit stop holds a step where it is; the striking leg
// is not held; every distance grows with the man; and walking, the held foot
// never slides and neither foot is ever left far behind.
public static class HoldTest {
    static int fails = 0;
    static void Check(bool ok, string w) { if (!ok) { fails++; Console.WriteLine("  FAIL " + w); } }
    static float Flat(Vector3 a, Vector3 b) { float x = a.x - b.x, z = a.z - b.z; return (float)Math.Sqrt(x * x + z * z); }
    const float Dt = 1f / 60f;

    public static int Main() {
        float lift;
        var h = new FighterIK.FootHold();
        Vector3 rest = new Vector3(0.1f, 0.07f, 0f);
        Vector3 p = FighterIK.HoldFoot(ref h, false, rest, false, false, Dt, 1f, out lift);
        Check(h.Held && Flat(p, rest) < 1e-6f && lift == 0f, "a foot is planted where it first stands");

        // carried under StepDrift: held, not sliding
        Vector3 planted = h.Anchor;
        float worst = 0f;
        for (int i = 1; i <= 6; i++) {
            Vector3 r = rest + new Vector3(0f, 0f, 0.015f * i);   // 9 cm in all
            p = FighterIK.HoldFoot(ref h, false, r, false, false, Dt, 1f, out lift);
            worst = Math.Max(worst, Flat(p, planted));
        }
        Check(h.Held && worst < 1e-6f, "held where it was planted while he carries it less than StepDrift (slid " + (worst * 100).ToString("0.000") + " cm)");

        // past StepDrift: a step after him, lifting in the middle, landing on its rest point
        Vector3 far = rest + new Vector3(0f, 0f, 0.20f);
        p = FighterIK.HoldFoot(ref h, false, far, false, false, Dt, 1f, out lift);
        Check(h.Stepping && !h.Held, "carried past StepDrift, it steps after him");
        float peak = 0f; int frames = 1;
        while (h.Stepping && frames < 100) {
            p = FighterIK.HoldFoot(ref h, false, far, false, false, Dt, 1f, out lift);
            peak = Math.Max(peak, lift); frames++;
        }
        Check(h.Held && Flat(p, far) < 1e-6f && lift == 0f, "the step lands on its rest point, held again, on the ground");
        Check(peak > 0.8f * FighterIK.StepLift && peak <= FighterIK.StepLift + 1e-6f, "the step lifts about StepLift in the middle (" + (peak * 100).ToString("0.0") + " cm)");
        Check(Math.Abs(frames * Dt - FighterIK.StepSeconds) <= 2f * Dt, "the step takes StepSeconds (" + (frames * Dt).ToString("0.000") + " s)");

        // one foot at a time
        var a = new FighterIK.FootHold(); FighterIK.HoldFoot(ref a, false, rest, false, false, Dt, 1f, out lift);
        Vector3 mid = rest + new Vector3(0f, 0f, 0.2f);
        FighterIK.HoldFoot(ref a, true, mid, false, false, Dt, 1f, out lift);
        Check(a.Held && !a.Stepping, "a foot waits while the other steps");
        Vector3 shoved = rest + new Vector3(0f, 0f, 0.35f);
        FighterIK.HoldFoot(ref a, true, shoved, false, false, Dt, 1f, out lift);
        Check(a.Stepping, "unless it is carried ForceDrift: then both step");

        // put somewhere new
        var b = new FighterIK.FootHold(); FighterIK.HoldFoot(ref b, false, rest, false, false, Dt, 1f, out lift);
        Vector3 there = new Vector3(6f, 0.07f, -4f);
        p = FighterIK.HoldFoot(ref b, false, there, false, false, Dt, 1f, out lift);
        Check(b.Held && Flat(p, there) < 1e-6f, "put somewhere new, it is planted there at once");

        // hit stop holds a step where it is, and holds a held foot
        var c = new FighterIK.FootHold(); FighterIK.HoldFoot(ref c, false, rest, false, false, Dt, 1f, out lift);
        FighterIK.HoldFoot(ref c, false, far, false, true, Dt, 1f, out lift);
        Check(c.Held, "frozen, a held foot does not start a step");
        FighterIK.HoldFoot(ref c, false, far, false, false, Dt, 1f, out lift);
        float tBefore = c.T;
        for (int i = 0; i < 10; i++) FighterIK.HoldFoot(ref c, false, far, false, true, Dt, 1f, out lift);
        Check(c.Stepping && Math.Abs(c.T - tBefore) < 1e-6f, "frozen, a step stands where it is");

        // the striking leg is not held
        var d = new FighterIK.FootHold(); FighterIK.HoldFoot(ref d, false, rest, false, false, Dt, 1f, out lift);
        p = FighterIK.HoldFoot(ref d, false, far, true, false, Dt, 1f, out lift);
        Check(!d.Held && !d.Stepping && Flat(p, far) < 1e-6f, "the striking leg is not held");

        // every distance grows with the man
        var e = new FighterIK.FootHold(); FighterIK.HoldFoot(ref e, false, rest, false, false, Dt, 1.5f, out lift);
        FighterIK.HoldFoot(ref e, false, rest + new Vector3(0f, 0f, 0.15f), false, false, Dt, 1.5f, out lift);
        Check(e.Held, "a man half again Ahmed's size holds 15 cm (his StepDrift is 18)");
        var z = new FighterIK.FootHold(); FighterIK.HoldFoot(ref z, false, rest, false, false, Dt, 0f, out lift);
        FighterIK.HoldFoot(ref z, false, rest + new Vector3(0f, 0f, 0.05f), false, false, Dt, 0f, out lift);
        Check(z.Held, "a size of nothing is taken as Ahmed's, not as no StepDrift at all");

        // walking: the held foot never slides, neither foot is left far behind
        foreach (float speed in new[] { 1.0f, 1.5f, 2.5f }) {
            var L = new FighterIK.FootHold(); var R = new FighterIK.FootHold();
            Vector3 root = Vector3.zero, side = new Vector3(0.1f, 0f, 0f);
            float slide = 0f, lag = 0f;
            Vector3 lastL = Vector3.zero, lastR = Vector3.zero; bool known = false;
            for (int i = 0; i < 240; i++) {
                root += new Vector3(0f, 0f, speed * Dt);
                bool wasL = L.Held, wasR = R.Held;
                Vector3 pl = FighterIK.HoldFoot(ref L, R.Stepping, root - side, false, false, Dt, 1f, out lift);
                Vector3 pr = FighterIK.HoldFoot(ref R, L.Stepping, root + side, false, false, Dt, 1f, out lift);
                if (known && wasL && L.Held) slide = Math.Max(slide, Flat(pl, lastL));
                if (known && wasR && R.Held) slide = Math.Max(slide, Flat(pr, lastR));
                lag = Math.Max(lag, Math.Max(Flat(pl, root - side), Flat(pr, root + side)));
                lastL = pl; lastR = pr; known = true;
            }
            Check(slide < 1e-5f, "walking at " + speed + " m/s a held foot never slides (" + (slide * 100).ToString("0.000") + " cm)");
            Check(lag < 0.45f, "walking at " + speed + " m/s neither foot is left more than 45 cm behind (" + (lag * 100).ToString("0.0") + " cm)");
            Console.WriteLine("  " + speed.ToString("0.0") + " m/s: held feet slide " + (slide * 100).ToString("0.000") + " cm, the furthest a foot trails " + (lag * 100).ToString("0.0") + " cm");
        }

        // the hips' drop (FighterIK.HipDrop, 2026-11-09): down to the lower
        // planted foot, never up, no further than MaxHipDrop; a foot over
        // nothing or a striking leg does not count; eased the same at 30 and 60 Hz
        Check(FighterIK.HipDrop(true, 0f, true, 0f) == 0f, "on flat ground the hips do not drop");
        Check(Math.Abs(FighterIK.HipDrop(true, 0f, true, -0.20f) - 0.20f) < 1e-6f, "the hips drop to the lower foot's ground");
        Check(FighterIK.HipDrop(true, 0.15f, true, 0f) == 0f && FighterIK.HipDrop(true, 0.15f, true, 0.10f) == 0f, "a step up under a foot, or both, does not raise the hips");
        Check(Math.Abs(FighterIK.HipDrop(true, -0.90f, true, 0f) - FighterIK.MaxHipDrop) < 1e-6f, "the hips drop no further than MaxHipDrop");
        Check(FighterIK.HipDrop(false, -0.30f, true, 0f) == 0f, "a foot over nothing, or the striking leg, does not pull the hips down");
        float d60 = 0f, d30 = 0f;
        for (int i = 0; i < 12; i++) d60 = FighterIK.EaseDrop(d60, 0.20f, 1f / 60f);
        for (int i = 0; i < 6; i++) d30 = FighterIK.EaseDrop(d30, 0.20f, 1f / 30f);
        Check(Math.Abs(d60 - d30) < 1e-5f && d60 > 0.15f && d60 < 0.20f, "the drop eases in, the same at 30 and 60 Hz (" + (d60 * 100).ToString("0.0") + " cm after 0.2 s)");
        float prev = 0f, biggest = 0f, dd = 0f;
        for (int i = 0; i < 120; i++) { dd = FighterIK.EaseDrop(dd, 0.20f, Dt); biggest = Math.Max(biggest, dd - prev); prev = dd; }
        Check(Math.Abs(dd - 0.20f) < 1e-4f && biggest < 0.045f, "it arrives, and never by more than 4.5 cm in a frame (" + (biggest * 100).ToString("0.0") + " cm)");

        Console.WriteLine(fails == 0 ? "HOLD  all checks passed" : "HOLD  " + fails + " failed");
        return fails == 0 ? 0 : 1;
    }
}
