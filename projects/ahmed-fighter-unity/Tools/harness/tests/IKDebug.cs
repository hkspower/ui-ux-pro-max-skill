using System; using System.Collections.Generic; using UnityEngine; using Ahmed.Combat;
// The computed pose, drawn (Assets/Scripts/Combat/IKDebug.cs, 2026-10-31):
// nothing for an empty view; a ray drawn blue with its hit and the ankle's
// target where it found ground, red alone where it found nothing; the guard's
// two fists only while it is up; the strike's cross only while it is on and
// growing with it; the colours apart; the toggle cycling off, all, Ahmed; and
// Draw putting every piece on the screen.
public static class IKDebugTest {
    static int fails = 0;
    static void Check(bool ok, string w) { if (!ok) { fails++; Console.WriteLine("  FAIL " + w); } }
    static int Count(List<IKDebug.Prim> l, IKDebug.Colour c, IKDebug.Shape s) {
        int n = 0; foreach (var p in l) if (p.Colour == c && p.Shape == s) n++; return n;
    }
    static bool Same(Vector3 a, Vector3 b) { return (a - b).magnitude < 1e-5f; }
    static IKDebug.FootView Ray(bool hit, Vector3 at) {
        var f = new IKDebug.FootView();
        f.Cast = true; f.Hit = hit; f.From = at + Vector3.up * 0.6f; f.To = at - Vector3.up * 1.0f;
        f.Point = at; f.Ankle = at + Vector3.up * FighterIK.AnkleHeight; f.Held = hit;
        return f;
    }
    public static int Main() {
        var l = new List<IKDebug.Prim>();
        IKDebug.Build(new IKDebug.View(), l);
        Check(l.Count == 0, "nothing is drawn for an empty view");

        var v = new IKDebug.View(); v.FootL = Ray(true, new Vector3(0.1f, 0f, 0.2f));
        IKDebug.Build(v, l);
        Check(Count(l, IKDebug.Colour.Hit, IKDebug.Shape.Line) == 1 && Count(l, IKDebug.Colour.Missed, IKDebug.Shape.Line) == 0,
              "a ray that found ground is drawn blue");
        Check(Count(l, IKDebug.Colour.Hit, IKDebug.Shape.Cross) == 1 && Count(l, IKDebug.Colour.Ankle, IKDebug.Shape.Cross) == 1,
              "a ray that found ground shows where it hit and where the ankle goes");
        bool ankleAt = false; foreach (var p in l) if (p.Colour == IKDebug.Colour.Ankle) ankleAt = Same(p.A, v.FootL.Ankle);
        Check(ankleAt, "the ankle's cross is on the ankle's target");
        v.FootL.Held = false; IKDebug.Build(v, l);
        Check(Count(l, IKDebug.Colour.Free, IKDebug.Shape.Cross) == 1 && Count(l, IKDebug.Colour.Ankle, IKDebug.Shape.Cross) == 0,
              "a foot stepping after him is drawn yellow, a held one green");

        v = new IKDebug.View(); v.FootR = Ray(false, new Vector3(-0.1f, 0f, 0f));
        IKDebug.Build(v, l);
        Check(l.Count == 1 && l[0].Colour == IKDebug.Colour.Missed && l[0].Shape == IKDebug.Shape.Line,
              "a ray that found nothing is drawn red, alone");

        v = new IKDebug.View(); v.GuardL = new Vector3(-0.1f, 1.5f, 0.26f); v.GuardR = new Vector3(0.1f, 1.5f, 0.26f);
        IKDebug.Build(v, l);
        Check(l.Count == 0, "the guard is not drawn while it is down");
        v.GuardOn = true; IKDebug.Build(v, l);
        Check(Count(l, IKDebug.Colour.Guard, IKDebug.Shape.Cross) == 2, "the guard's two fist targets are drawn while it is up");

        v = new IKDebug.View(); v.HipsFrom = new Vector3(0f, 0.952f, 0f); v.HipsTo = new Vector3(0f, 0.752f, 0f);
        IKDebug.Build(v, l);
        Check(l.Count == 0, "the hips' drop is not drawn while there is none");
        v.HipsOn = true; IKDebug.Build(v, l);
        Check(l.Count == 1 && l[0].Colour == IKDebug.Colour.Hips && l[0].Shape == IKDebug.Shape.Line && Same(l[0].A, v.HipsFrom) && Same(l[0].B, v.HipsTo),
              "the hips' drop is drawn from where they rest to where they are");

        v = new IKDebug.View(); v.StrikeOn = true; v.StrikeTarget = new Vector3(0f, 1.44f, 0.8f); v.StrikeWeight = 0f;
        IKDebug.Build(v, l);
        Check(l.Count == 0, "the strike is not drawn at no weight");
        v.StrikeWeight = 0.3f; IKDebug.Build(v, l);
        float small = l.Count == 1 ? l[0].Size : 0f;
        v.StrikeWeight = 1f; IKDebug.Build(v, l);
        float big = l.Count == 1 ? l[0].Size : 0f;
        Check(small > 0f && big > small && Math.Abs(big - IKDebug.StrikeMax) < 1e-5f && l.Count == 1 && Same(l[0].A, v.StrikeTarget),
              "the strike's cross is on its target and grows as it comes on");

        var all = new[] { IKDebug.Colour.Hit, IKDebug.Colour.Missed, IKDebug.Colour.Ankle, IKDebug.Colour.Free, IKDebug.Colour.Guard, IKDebug.Colour.Strike, IKDebug.Colour.Hips };
        bool apart = true;
        foreach (var a in all) foreach (var b in all) {
            if (a == b) continue;
            Color x = IKDebug.ColourOf(a), y = IKDebug.ColourOf(b);
            apart &= Math.Abs(x.r - y.r) + Math.Abs(x.g - y.g) + Math.Abs(x.b - y.b) >= 0.35f;
        }
        Check(apart, "every colour is far from every other");

        Check(IKDebug.Next(0) == 1 && IKDebug.Next(1) == 2 && IKDebug.Next(2) == 0, "F8 cycles off, every fighter, Ahmed only");
        Check(!IKDebug.Draws(0, true) && IKDebug.Draws(1, false) && IKDebug.Draws(2, true) && !IKDebug.Draws(2, false),
              "the view draws every fighter at 1 and only Ahmed at 2");

        v = new IKDebug.View(); v.FootL = Ray(true, Vector3.zero); v.FootR = Ray(false, Vector3.zero); v.GuardOn = true;
        v.StrikeOn = true; v.StrikeWeight = 1f;
        IKDebug.Build(v, l);
        int lines = 0; foreach (var p in l) lines += p.Shape == IKDebug.Shape.Line ? 1 : 3;
        Debug.Lines = 0; IKDebug.Draw(l);
        Check(Debug.Lines == lines && lines > 0, "Draw puts every piece on the screen, a cross as three lines");

        Console.WriteLine(fails == 0 ? "IKDEBUG  all checks passed" : "IKDEBUG  " + fails + " failed");
        return fails == 0 ? 0 : 1;
    }
}
