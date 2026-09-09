using System;
using System.Collections.Generic;
using UnityEngine;
using Ahmed.Data;
using Ahmed.World;
using Ahmed.Combat;

public static class Program
{
    static int fails = 0;
    static void Check(bool ok, string what)
    {
        if (!ok) { fails++; Console.WriteLine("  FAIL  " + what); }
    }

    public static int Main()
    {
        HitboxGeometry();
        DistrictLayout();
        WorldReachability();
        Console.WriteLine(fails == 0 ? "\nall checks passed" : "\n" + fails + " FAILURES");
        return fails == 0 ? 0 : 1;
    }

    // ---------------------------------------------------------------- hitbox
    static void HitboxGeometry()
    {
        Console.WriteLine("HITBOX  (reach 1.30 m, lateral tolerance 0.80 m -- the Jab)");
        float reach = 1.296f, lat = 0.80f;
        Vector3 o = new Vector3(0, 0, 0), f = new Vector3(1, 0, 0);

        Check(Fighter.InHitbox(o, f, new Vector3(1.0f, 0, 0), reach, lat), "in front, in reach");
        Check(!Fighter.InHitbox(o, f, new Vector3(3.0f, 0, 0), reach, lat), "in front, too far");
        Check(!Fighter.InHitbox(o, f, new Vector3(-1.0f, 0, 0), reach, lat), "behind");
        Check(Fighter.InHitbox(o, f, new Vector3(1.0f, 0, 0.6f), reach, lat), "in front, just off the line");
        Check(!Fighter.InHitbox(o, f, new Vector3(1.0f, 0, 1.4f), reach, lat), "in front, well off the line");
        Check(Fighter.InHitbox(o, f, new Vector3(1.0f, 5f, 0), reach, lat), "height is ignored");

        // The property that matters: rotate the whole pair and nothing moves.
        Console.WriteLine("  rotation invariance, 72 angles x 400 sample points");
        int mismatches = 0, hits = 0;
        var rnd = new System.Random(7);
        for (int p = 0; p < 400; p++)
        {
            Vector3 local = new Vector3((float)(rnd.NextDouble() * 6 - 3), 0,
                                        (float)(rnd.NextDouble() * 6 - 3));
            bool baseline = Fighter.InHitbox(o, f, local, reach, lat);
            if (baseline) { hits++; }
            for (int a = 1; a < 72; a++)
            {
                double th = a * Math.PI * 2 / 72;
                float c = (float)Math.Cos(th), s = (float)Math.Sin(th);
                Vector3 rf = new Vector3(c, 0, s);
                Vector3 rp = new Vector3(local.x * c - local.z * s, 0, local.x * s + local.z * c);
                // also move the origin, to prove it is not anchored to 0,0
                Vector3 ro = new Vector3(17f, 0, -9f);
                if (Fighter.InHitbox(ro, rf, ro + rp, reach, lat) != baseline) { mismatches++; }
            }
        }
        Check(mismatches == 0, "rotation invariant (" + mismatches + " mismatches)");
        Check(hits > 20, "the sample actually covered the hitbox (" + hits + " hits)");
        Console.WriteLine("    " + hits + "/400 sample points inside, " + mismatches + " mismatches over 28800 rotations");
    }

    // -------------------------------------------------------------- districts
    static void DistrictLayout()
    {
        Console.WriteLine("\nDISTRICTS");
        Console.WriteLine("  area                 across   sites  enc  gate  exit   nearest pair");
        for (int i = 0; i < TestData.Areas.Length; i++)
        {
            District d = District.Build(i, TestData.Areas[i], TestData.Stages[i]);
            int enc = 0, gate = 0, exit = 0;
            float nearest = float.MaxValue;
            foreach (Site s in d.Sites)
            {
                if (s.Kind == SiteKind.Encounter) enc++;
                else if (s.Kind == SiteKind.Gate) gate++;
                else exit++;

                Check(d.Bounds.Contains(s.Position),
                      "area " + i + " site " + s.Id + " inside its own bounds");
                foreach (Site t in d.Sites)
                {
                    if (t == s) continue;
                    float dist = (t.Position - s.Position).magnitude;
                    if (dist < nearest) nearest = dist;
                }
            }
            Check(enc == TestData.Stages[i].waves.Length, "area " + i + " kept every wave");
            Check(gate == TestData.Stages[i].gates.Length, "area " + i + " kept every gate");
            Check(nearest > 4f, "area " + i + " sites are not stacked (nearest " + nearest.ToString("0.0") + ")");

            // No two encounters may wake each other: walking into one must not
            // start two fights.
            foreach (Site a in d.Sites)
            {
                if (a.Kind != SiteKind.Encounter) continue;
                foreach (Site b2 in d.Sites)
                {
                    if (b2 == a || b2.Kind != SiteKind.Encounter) continue;
                    float gap = (b2.Position - a.Position).magnitude;
                    Check(gap > a.Radius + b2.Radius - 0.01f,
                          "area " + i + " encounters " + a.Id + "/" + b2.Id
                          + " overlap (gap " + gap.ToString("0.0")
                          + ", radii " + a.Radius.ToString("0.0") + "+" + b2.Radius.ToString("0.0") + ")");
                }
            }

            Console.WriteLine("  " + d.Name.PadRight(20) + (d.Extent * 2f).ToString("0").PadLeft(5)
                + " m " + d.Sites.Count.ToString().PadLeft(6) + enc.ToString().PadLeft(5)
                + gate.ToString().PadLeft(6) + exit.ToString().PadLeft(6)
                + nearest.ToString("0.0").PadLeft(14) + " m");
        }

        // Determinism: build twice, expect identical placement.
        District a1 = District.Build(3, TestData.Areas[3], TestData.Stages[3]);
        District a2 = District.Build(3, TestData.Areas[3], TestData.Stages[3]);
        bool same = a1.Sites.Count == a2.Sites.Count;
        for (int i = 0; same && i < a1.Sites.Count; i++)
        {
            same = (a1.Sites[i].Position - a2.Sites[i].Position).magnitude < 1e-6f;
        }
        Check(same, "layout is deterministic between builds");

        // Pacing survives: later waves sit further out than earlier ones.
        District p = District.Build(0, TestData.Areas[0], TestData.Stages[0]);
        float lastR = -1f; bool outward = true;
        foreach (Site s in p.Sites)
        {
            if (s.Kind != SiteKind.Encounter) continue;
            float r = s.Position.magnitude;
            if (r < lastR - 8f) { outward = false; }
            lastR = r;
        }
        Check(outward, "waves still run outward in the order the stage intended");

        float total = 0f;
        for (int i = 0; i < TestData.Areas.Length; i++)
        {
            District d = District.Build(i, TestData.Areas[i], TestData.Stages[i]);
            total += (d.Extent * 2f) * (d.Extent * 2f);
        }
        Console.WriteLine("  total ground: " + (total / 1000f).ToString("0.0")
            + " thousand m^2, against 5.4 thousand for the nine corridors");
    }

    // ------------------------------------------------------------ reachability
    static void WorldReachability()
    {
        Console.WriteLine("\nWORLD");
        Ability[] all = { Ability.Vault, Ability.DashLeap, Ability.PowerKick,
                          Ability.Haymaker, Ability.HawkFist };

        WorldState.Reset();
        Console.WriteLine("  with no talents:        " + Reach() + " of 9 districts reachable");
        int bare = Reach();

        WorldState.Reset();
        foreach (Ability a in all) { WorldState.GrantTalent(a); }
        for (int i = 0; i < 9; i++) { WorldState.MarkAreaCleared(i); }
        int full = Reach();
        Console.WriteLine("  with every talent:      " + full + " of 9 districts reachable");

        Check(bare >= 1 && bare < 9, "the world starts mostly shut (" + bare + "/9)");
        Check(full == 9, "every district is reachable once everything is found");
        WorldState.Reset();
    }

    static int Reach()
    {
        var seen = new HashSet<int>();
        var queue = new Queue<int>();
        queue.Enqueue(TestData.Areas[0].startArea);
        seen.Add(TestData.Areas[0].startArea);
        while (queue.Count > 0)
        {
            WorldArea a = TestData.Areas[queue.Dequeue()];
            foreach (WorldLink l in new[] { a.west, a.east, a.door })
            {
                if (l == null || l.to < 0) continue;
                l.Resolve();
                if (!WorldState.CanUse(l)) continue;
                if (seen.Add(l.to)) { queue.Enqueue(l.to); }
            }
        }
        return seen.Count;
    }
}
