using System; using UnityEngine; using Ahmed.Combat;
// The feet held (FighterIK.HoldFoot, 2026-10-31, after the Unreal build's
// SaudIK feet): planted where it first stands; held there, not sliding, while
// he carries its rest point less than StepDrift; then a step after him that
// lifts in the middle and lands on its rest point, held again; one foot at a
// time unless the standing one is carried ForceDrift; a jump of SnapDrift
// re-plants it at once; hit stop holds a step where it is; the striking leg's
// foot stays where it stood (2026-11-10); every distance grows with the man; and walking, the held foot
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

        // the kicking foot leaves from where it stands (2026-11-10; until then it was let go
        // to its rest point on the kick's first frame, 20 cm in one frame here)
        var d = new FighterIK.FootHold(); FighterIK.HoldFoot(ref d, false, rest, false, false, Dt, 1f, out lift);
        p = FighterIK.HoldFoot(ref d, false, far, true, false, Dt, 1f, out lift);
        Check(d.Held && !d.Stepping && Flat(p, rest) < 1e-6f && lift == 0f, "the striking leg's foot stays where it stood on the kick's first frame");
        // ...through the whole kick, however long, and it does not start a step
        bool stayed = true;
        for (int i = 0; i < 40; i++) {
            p = FighterIK.HoldFoot(ref d, false, far, true, false, Dt, 1f, out lift);
            if (d.Stepping || Flat(p, rest) > 1e-6f) stayed = false;
        }
        Check(stayed, "...and through the kick: it does not step while it strikes");
        // after the kick the ordinary step takes it home
        FighterIK.HoldFoot(ref d, false, far, false, false, Dt, 1f, out lift);
        bool stepsHome = d.Stepping;
        for (int i = 0; i < 20; i++) p = FighterIK.HoldFoot(ref d, false, far, false, false, Dt, 1f, out lift);
        Check(stepsHome && d.Held && Flat(p, far) < 1e-6f, "...and after the kick it steps home");
        // caught mid-step by the kick, it stops where the step had got to
        var d2 = new FighterIK.FootHold(); FighterIK.HoldFoot(ref d2, false, rest, false, false, Dt, 1f, out lift);
        Vector3 mids = rest;
        for (int i = 0; i < 4; i++) mids = FighterIK.HoldFoot(ref d2, false, far, false, false, Dt, 1f, out lift);
        bool wasStepping = d2.Stepping;
        p = FighterIK.HoldFoot(ref d2, false, far, true, false, Dt, 1f, out lift);
        Check(wasStepping && d2.Held && !d2.Stepping && Flat(p, mids) < 0.05f && Flat(p, rest) > 0.01f && Flat(p, far) > 0.01f,
              "a foot caught mid-step by its own kick stops where the step had got to (" + (Flat(p, mids) * 100).ToString("0.0") + " cm on)");
        // a kick thrown by a man put somewhere new is planted there
        var d3 = new FighterIK.FootHold(); FighterIK.HoldFoot(ref d3, false, rest, false, false, Dt, 1f, out lift);
        Vector3 kickPut = new Vector3(6f, 0.07f, -4f);
        p = FighterIK.HoldFoot(ref d3, false, kickPut, true, false, Dt, 1f, out lift);
        Check(d3.Held && Flat(p, kickPut) < 1e-6f, "a striking leg put somewhere new is planted there, not left behind");

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

        // ---- 2026-11-10, the IK reviewed
        // his size, off his own hips (SizeOf)
        Check(Math.Abs(FighterIK.SizeOf(0.952f, true, 0.952f, true) - 1f) < 1e-6f, "Ahmed's hips make a size of one");
        Check(Math.Abs(FighterIK.SizeOf(0.952f * 1.55f, true, 0.952f * 1.55f, true) - 1.55f) < 1e-5f
              && Math.Abs(FighterIK.SizeOf(0.952f * 0.94f, true, 0f, false) - 0.94f) < 1e-5f,
              "a man's size is his hips' height against Ahmed's, from whichever legs he has");
        Check(FighterIK.SizeOf(0f, false, 0f, false) == 1f && FighterIK.SizeOf(0f, true, 0f, true) == 1f
              && FighterIK.SizeOf(-2f, true, -2f, true) == 1f && FighterIK.SizeOf(float.NaN, true, 1f, true) == 1f,
              "no legs, or a height that is not one, is taken as Ahmed's size");

        // the reach's drop (ReachDrop): the leg rests straight, so a foot held away from under the hip needs the hips lower
        const float Span = 0.882f;
        Check(FighterIK.ReachDrop(Span, Span, 0f, 0f) == 0f, "a standing leg needs no drop");
        Check(Math.Abs(FighterIK.ReachDrop(Span, Span, 0.12f, 0f) - (Span - (float)Math.Sqrt(Span * Span - 0.12f * 0.12f))) < 1e-6f
              && FighterIK.ReachDrop(Span, Span, 0.12f, 0f) > 0.008f,
              "a foot held 12 cm from under the hip brings the hips down by what the leg is short");
        Check(Math.Abs(FighterIK.ReachDrop(Span, Span, 0f, 0.20f) - 0.20f) < 1e-6f, "ground 20 cm lower under a foot needs 20 cm, as the ground's own drop has it");
        Check(FighterIK.ReachDrop(Span, Span, 0.95f, 0f) == FighterIK.MaxHipDrop && FighterIK.ReachDrop(Span, Span, 0.5f, 0.3f) == FighterIK.MaxHipDrop,
              "a foot further than the leg is long, or more than the most, asks the most and no more");
        Check(FighterIK.ReachDrop(Span, Span, 0f, -0.30f) == 0f && FighterIK.ReachDrop(0f, 0f, 0.1f, 0f) == 0f,
              "a foot on higher ground never raises the hips, and a leg of no length asks nothing");

        // the hips' step (StepDrop): down at the ground's rate, never less than the reach needs, up slower
        float s60 = 0f, s30 = 0f, s120 = 0f;
        for (int i = 0; i < 12; i++) s60 = FighterIK.StepDrop(s60, 0.20f, 0f, 1f / 60f);
        for (int i = 0; i < 6; i++) s30 = FighterIK.StepDrop(s30, 0.20f, 0f, 1f / 30f);
        for (int i = 0; i < 24; i++) s120 = FighterIK.StepDrop(s120, 0.20f, 0f, 1f / 120f);
        Check(Math.Abs(s60 - d60) < 1e-6f && Math.Abs(s60 - s30) < 1e-5f && Math.Abs(s60 - s120) < 1e-5f,
              "the hips come down to the ground's drop as they did, the same at 30, 60 and 120 Hz");
        Check(FighterIK.StepDrop(0f, 0.05f, 0.05f, Dt) == 0.05f && FighterIK.StepDrop(0.01f, 0.30f, 0.04f, Dt) >= 0.04f
              && FighterIK.StepDrop(0f, 0.9f, 0.9f, Dt) == FighterIK.MaxHipDrop,
              "what a held foot's reach needs is taken at once, and never more than the most");
        float up60 = 0.05f, up30 = 0.05f, down60 = 0f;
        for (int i = 0; i < 6; i++) { up60 = FighterIK.StepDrop(up60, 0f, 0f, 1f / 60f); down60 = FighterIK.StepDrop(down60, 0.05f, 0f, 1f / 60f); }
        for (int i = 0; i < 3; i++) up30 = FighterIK.StepDrop(up30, 0f, 0f, 1f / 30f);
        Check(Math.Abs(up60 - up30) < 1e-6f && (0.05f - up60) < 0.5f * down60 && up60 < 0.05f,
              "the hips rise slower than they drop, the same at 30 and 60 Hz (" + ((0.05f - up60) * 100).ToString("0.00") + " cm up in 0.1 s against " + (down60 * 100).ToString("0.00") + " down)");
        Check(FighterIK.StepDrop(0.07f, 0.02f, 0f, 0f) == 0.07f, "a frame of no time moves nothing");

        // the settle: standing still, a foot left off its place steps back after SettleSeconds
        {
            var f = new FighterIK.FootHold(); FighterIK.HoldFoot(ref f, false, rest, false, false, Dt, 1f, out lift, true, 0f);
            Vector3 off = rest + new Vector3(0f, 0f, 0.08f);          // carried 8 cm: under StepDrift, so no step
            int stepAt = -1; bool early = false;
            for (int i = 0; i < 60; i++)
            {
                p = FighterIK.HoldFoot(ref f, false, off, false, false, Dt, 1f, out lift, true, 0f);
                if (f.Stepping && stepAt < 0) { stepAt = i; }
                if (f.Stepping && (i + 1) * Dt < FighterIK.SettleSeconds - 1e-4f) { early = true; }
            }
            Check(stepAt >= 0 && !early && Math.Abs(stepAt * Dt - FighterIK.SettleSeconds) <= 2f * Dt,
                  "standing still with a foot 8 cm off its place, it steps back after SettleSeconds and not before (" + (stepAt * Dt).ToString("0.000") + " s)");
            Check(f.Held && Flat(p, off) < 1e-6f, "the settle's step lands on its place");

            var n = new FighterIK.FootHold(); FighterIK.HoldFoot(ref n, false, rest, false, false, Dt, 1f, out lift, false, 0f);
            for (int i = 0; i < 60; i++) FighterIK.HoldFoot(ref n, false, off, false, false, Dt, 1f, out lift, false, 0f);
            Check(n.Held && !n.Stepping && Flat(n.Anchor, rest) < 1e-6f, "a man who may not settle (he is attacking) keeps the foot where it is");

            var near = new FighterIK.FootHold(); FighterIK.HoldFoot(ref near, false, rest, false, false, Dt, 1f, out lift, true, 0f);
            for (int i = 0; i < 60; i++) FighterIK.HoldFoot(ref near, false, rest + new Vector3(0f, 0f, 0.02f), false, false, Dt, 1f, out lift, true, 0f);
            Check(near.Held && Flat(near.Anchor, rest) < 1e-6f, "a foot 2 cm off, under SettleDrift, is left where it is");

            var fr = new FighterIK.FootHold(); FighterIK.HoldFoot(ref fr, false, rest, false, false, Dt, 1f, out lift, true, 0f);
            for (int i = 0; i < 60; i++) FighterIK.HoldFoot(ref fr, false, off, false, true, Dt, 1f, out lift, true, 0f);
            Check(fr.Held && !fr.Stepping && fr.Still == 0f, "hit stop is not standing still: the settle does not count through it");
            // ... and a foot already due (it was waiting for the other to land) does not start its step in one
            var due = new FighterIK.FootHold(); FighterIK.HoldFoot(ref due, false, rest, false, false, Dt, 1f, out lift, true, 0f);
            for (int i = 0; i < 30; i++) FighterIK.HoldFoot(ref due, true, off, false, false, Dt, 1f, out lift, true, 0f);
            FighterIK.HoldFoot(ref due, false, off, false, true, Dt, 1f, out lift, true, 0f);
            Check(due.Still >= FighterIK.SettleSeconds && due.Held && !due.Stepping, "frozen, a foot due to settle does not start its step");
            FighterIK.HoldFoot(ref due, false, off, false, false, Dt, 1f, out lift, true, 0f);
            Check(due.Stepping, "...and starts it the frame the hit stop ends");

            // creeping: the rest point never stops, so the settle never fires (the ordinary step does, at StepDrift)
            var cr = new FighterIK.FootHold(); FighterIK.HoldFoot(ref cr, false, rest, false, false, Dt, 1f, out lift, true, 0f);
            bool crept = false;
            for (int i = 1; i <= 50; i++)
            {
                FighterIK.HoldFoot(ref cr, false, rest + new Vector3(0f, 0f, 0.002f * i), false, false, Dt, 1f, out lift, true, 0f);   // 12 cm/s: 10 cm in all
                crept |= cr.Stepping;
            }
            Check(!crept, "a foot still being carried is not standing still: no settle while he moves");

            // two feet off: the further one first, the other when it has landed
            var a2 = new FighterIK.FootHold(); var b2 = new FighterIK.FootHold();
            Vector3 restB = rest + new Vector3(-0.2f, 0f, 0f);
            FighterIK.HoldFoot(ref a2, false, rest, false, false, Dt, 1f, out lift, true, 0f);
            FighterIK.HoldFoot(ref b2, false, restB, false, false, Dt, 1f, out lift, true, 0f);
            Vector3 offA = rest + new Vector3(0f, 0f, 0.05f), offB = restB + new Vector3(0f, 0f, 0.09f);
            int firstA = -1, firstB = -1; bool together = false;
            for (int i = 0; i < 90; i++)
            {
                float dA = a2.Held ? Flat(a2.Anchor, offA) : 0f, dB = b2.Held ? Flat(b2.Anchor, offB) : 0f;
                FighterIK.HoldFoot(ref a2, b2.Stepping, offA, false, false, Dt, 1f, out lift, true, dB);
                FighterIK.HoldFoot(ref b2, a2.Stepping, offB, false, false, Dt, 1f, out lift, true, dA);
                if (a2.Stepping && firstA < 0) firstA = i;
                if (b2.Stepping && firstB < 0) firstB = i;
                together |= a2.Stepping && b2.Stepping;
            }
            Check(firstB >= 0 && firstA > firstB && !together && a2.Held && b2.Held && Flat(a2.Anchor, offA) < 1e-6f && Flat(b2.Anchor, offB) < 1e-6f,
                  "two feet off their places settle one at a time, the further foot first");
        }

        // put somewhere new while a foot is mid-step: planted there at once, not stepped to from where he was
        {
            var m = new FighterIK.FootHold(); FighterIK.HoldFoot(ref m, false, rest, false, false, Dt, 1f, out lift);
            FighterIK.HoldFoot(ref m, false, far, false, false, Dt, 1f, out lift);
            FighterIK.HoldFoot(ref m, false, far, false, false, Dt, 1f, out lift);
            Check(m.Stepping, "(a step is under way)");
            Vector3 gone = new Vector3(6f, 0.07f, -4f);
            p = FighterIK.HoldFoot(ref m, false, gone, false, false, Dt, 1f, out lift);
            Check(m.Held && !m.Stepping && Flat(p, gone) < 1e-6f && lift == 0f, "put somewhere new mid-step, the foot is planted there at once");
            var big = new FighterIK.FootHold(); FighterIK.HoldFoot(ref big, false, rest, false, false, Dt, 1.5f, out lift);
            p = FighterIK.HoldFoot(ref big, false, rest + new Vector3(0f, 0f, 1.2f), false, false, Dt, 1.5f, out lift);
            Check(big.Stepping || Flat(p, rest) < 1e-6f, "a man half again Ahmed's size carried 1.2 m is not put somewhere new (his is 1.5 m)");
        }

        Console.WriteLine(fails == 0 ? "HOLD  all checks passed" : "HOLD  " + fails + " failed");
        return fails == 0 ? 0 : 1;
    }
}
