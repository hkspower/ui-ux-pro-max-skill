// SAUD -- the street-car tool's checks. The Unity menu refuses to export a
// car that fails any of them, and the Mono harness breaks each one on
// purpose (Tools/cars/run.sh --bite) to prove it catches what it guards.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;

namespace Saud.CarTool
{
    public struct Fault
    {
        public string Rule, Message;
        public Fault(string rule, string message) { Rule = rule; Message = message; }
        public override string ToString() => Rule + ": " + Message;
    }

    public static class CarChecks
    {
        public static readonly string[] SlotNames = { "Paint", "Glass", "Trim", "Chrome", "Tyre", "Rim", "Lamp", "Tail", "Plate", "Sign" };
        public const int MAX_TRIS = 25000;
        public const double MIN_GLASS_M2 = 0.10;

        static string K(V3 p) => Math.Round(p.X * 1e4) + "," + Math.Round(p.Y * 1e4) + "," + Math.Round(p.Z * 1e4);

        public static List<Fault> Run(BuiltCar car, CarSet set, PaintMap paint)
        {
            var f = new List<Fault>();
            var c = car.Spec;
            Action<string, string> fail = (rule, msg) => f.Add(new Fault(rule, c.Name + ": " + msg));

            // closed, wound, outward, degenerate: every part a closed solid, faces out
            foreach (var s in car.Shells)
            {
                var weld = new Dictionary<string, int>();
                var w = new int[s.P.Count];
                for (int i = 0; i < s.P.Count; i++) { string k = K(s.P[i]); if (!weld.TryGetValue(k, out w[i])) weld[k] = w[i] = i; }
                var edges = new Dictionary<long, int>();
                int small = 0;
                for (int t = 0; t < s.Tris; t++)
                {
                    if (s.Normal(t).Length * 0.5 < 1e-7) small++;
                    for (int e = 0; e < 3; e++)
                    {
                        long a = w[s.T[3 * t + e]], b = w[s.T[3 * t + (e + 1) % 3]];
                        long key = a * 1000003L + b;
                        edges[key] = edges.TryGetValue(key, out int n) ? n + 1 : 1;
                    }
                }
                int open = 0, twice = 0;
                foreach (var kv in edges)
                {
                    long a = kv.Key / 1000003L, b = kv.Key % 1000003L;
                    if (kv.Value > 1) twice++;
                    if (!edges.ContainsKey(b * 1000003L + a)) open++;
                }
                if (twice > 0) fail("wound", string.Format("{0} has {1} edges run the same way by two faces: a face turned against its neighbours", s.Name, twice));
                else if (open > 0) fail("closed", string.Format("{0} has {1} open edges: a hole", s.Name, open));
                if (s.Volume() <= 0) fail("outward", string.Format("{0} is inside out (volume {1:F4} m3)", s.Name, s.Volume()));
                if (small > 0) fail("degenerate", string.Format("{0} has {1} faces under 0.1 mm2", s.Name, small));
            }

            // size: bumper to bumper, the body's width, the top
            double minX = 1e9, maxX = -1e9, maxY = 0, maxZ = -1e9, minZ = 1e9, bodyY = 0;
            foreach (var s in car.Shells)
                foreach (var q in s.P)
                {
                    minX = Math.Min(minX, q.X); maxX = Math.Max(maxX, q.X);
                    maxY = Math.Max(maxY, Math.Abs(q.Y)); maxZ = Math.Max(maxZ, q.Z); minZ = Math.Min(minZ, q.Z);
                    if (s.Name == "Body" || s.Name == "Bed") bodyY = Math.Max(bodyY, Math.Abs(q.Y));
                }
            if (Math.Abs((maxX - minX) - c.Length) > 0.02) fail("size", string.Format("{0:F3} m long, the spec {1:F3}", maxX - minX, c.Length));
            if (Math.Abs(2 * bodyY - c.Width) > 0.01) fail("size", string.Format("the body {0:F3} m wide, the spec {1:F3}", 2 * bodyY, c.Width));
            if (2 * maxY > c.Width + 2 * set.MirrorOut + 0.01) fail("size", string.Format("{0:F3} m wide over the mirrors, the footprint {1:F3}", 2 * maxY, c.Width + 2 * set.MirrorOut));
            if (Math.Abs(maxZ - c.TotalHeight) > 0.02) fail("size", string.Format("{0:F3} m tall, the spec {1:F3}", maxZ, c.TotalHeight));

            // ground and tyres: four tyres on the floor at their axles, nothing else near it
            if (Math.Abs(minZ) > 0.002) fail("ground", string.Format("its lowest point is {0:F1} mm off the floor", minZ * 1000));
            var tyres = car.Shells.Where(s => s.Name.StartsWith("Tyre")).ToList();
            if (tyres.Count != 4) fail("tyres", string.Format("{0} tyres", tyres.Count));
            foreach (var s in tyres)
            {
                double lo = s.P.Min(q => q.Z);
                double cx = (s.P.Min(q => q.X) + s.P.Max(q => q.X)) / 2, cy = (s.P.Min(q => q.Y) + s.P.Max(q => q.Y)) / 2;
                if (lo > 0.002) fail("tyres", string.Format("{0} stands {1:F1} mm off the floor", s.Name, lo * 1000));
                if (!c.Wheel.Axles.Any(xa => Math.Abs(xa - cx) < 0.001) || Math.Abs(Math.Abs(cy) - c.Wheel.Track / 2) > 0.001)
                    fail("tyres", string.Format("{0} is off its axle ({1:F3}, {2:F3})", s.Name, cx, cy));
            }
            foreach (var s in car.Shells)
            {
                if (s.Name.StartsWith("Tyre")) continue;
                double lo = s.P.Min(q => q.Z);
                if (lo < c.Clear * 0.5) fail("ground", string.Format("{0} hangs to {1:F0} mm off the floor", s.Name, lo * 1000));
            }

            // arches: the body stands clear over every tyre
            double tIn = c.Wheel.Track / 2 - c.Wheel.Width / 2, tOut = c.Wheel.Track / 2 + c.Wheel.Width / 2, R = c.Wheel.R;
            foreach (var s in car.Shells.Where(s => s.Name == "Body" || s.Name == "Bed"))
            {
                double worst = 1e9;
                foreach (var q in s.P)
                {
                    double ay = Math.Abs(q.Y);
                    if (ay < tIn || ay > tOut) continue;             // over the tyre, not the floor inboard of it
                    foreach (double xa in c.Wheel.Axles)
                    {
                        double dx = q.X - xa;
                        if (Math.Abs(dx) >= R) continue;
                        double top = R + Math.Sqrt(R * R - dx * dx);
                        worst = Math.Min(worst, q.Z - top);
                    }
                }
                if (worst < 0.005) fail("arches", string.Format("{0} comes {1:F0} mm {2} a tyre", s.Name, Math.Abs(worst) * 1000, worst < 0 ? "into" : "over"));
            }

            // glass: a windscreen, a rear screen and windows both sides
            double gf = 0, gr = 0, gl = 0, gs = 0;
            foreach (var s in car.Shells)
                for (int t = 0; t < s.Tris; t++)
                {
                    if (s.Slot[t] != "Glass") continue;
                    var n = s.Normal(t); double area = n.Length * 0.5; var u = n.Unit;
                    if (u.X > 0.3) gf += area; if (u.X < -0.3) gr += area;
                    if (u.Y > 0.5) gl += area; if (u.Y < -0.5) gs += area;
                }
            var panes = new[] { "windscreen", "rear screen", "left windows", "right windows" };
            var areas = new[] { gf, gr, gl, gs };
            for (int i = 0; i < 4; i++)
                if (areas[i] < MIN_GLASS_M2) fail("glass", string.Format("its {0} are {1:F2} m2 of glass", panes[i], areas[i]));

            // symmetry: the left and the right are one another's mirror
            var seen = new HashSet<string>();
            foreach (var s in car.Shells) for (int t = 0; t < s.Tris; t++) for (int e = 0; e < 3; e++) seen.Add(s.Slot[t] + K(s.P[s.T[3 * t + e]]));
            int lonely = 0;
            foreach (var s in car.Shells) for (int t = 0; t < s.Tris; t++) for (int e = 0; e < 3; e++)
            {
                var q = s.P[s.T[3 * t + e]];
                if (!seen.Contains(s.Slot[t] + K(new V3(q.X, -q.Y, q.Z)))) lonely++;
            }
            if (lonely > 0) fail("symmetry", string.Format("{0} corners have no mirror across the centre line", lonely));

            // the finished mesh
            var m = car.Mesh;
            if (m.TriCount > MAX_TRIS) fail("budget", string.Format("{0} triangles, over {1}", m.TriCount, MAX_TRIS));
            foreach (var sl in m.Slots)
                if (!SlotNames.Contains(sl) || (sl != "Paint" && !set.Slots.ContainsKey(sl))) fail("slots", "a material slot '" + sl + "' nothing paints");
            if (!m.Slots.Contains("Paint")) fail("slots", "no paint");
            int bad = m.Uv.Count(uv => uv[0] < -1e-6 || uv[0] > 1 + 1e-6 || uv[1] < -1e-6 || uv[1] > 1 + 1e-6);
            if (bad > 0) fail("uv", string.Format("{0} corners map off the paint", bad));
            int nbad = m.Nrm.Count(n => double.IsNaN(n.X) || Math.Abs(n.Length - 1) > 1e-3);
            if (nbad > 0) fail("normals", string.Format("{0} normals not unit", nbad));

            // the paint, read back from its 8-bit texels
            if (paint != null)
            {
                if (paint.DarkestLuma < set.InkFloor - 1e-4) fail("paint", string.Format("its darkest texel is {0:F4}, under the ink floor {1:F3}", paint.DarkestLuma, set.InkFloor));
                if (paint.PalestLuma > set.PaintHi + 0.004) fail("paint", string.Format("its palest texel is {0:F3}, over {1:F2}", paint.PalestLuma, set.PaintHi));
            }
            return f;
        }

        /// <summary>A Wavefront OBJ of the finished mesh (Y up, as OBJ readers
        /// expect), with an MTL naming the paint -- for looking at, only.</summary>
        public static void WriteObj(BuiltCar car, CarSet set, string dir)
        {
            var ci = CultureInfo.InvariantCulture;
            var m = car.Mesh; string n = "SM_Car_" + car.Spec.Name;
            var o = new StringBuilder();
            o.AppendLine("mtllib " + n + ".mtl");
            foreach (var q in m.Pos) o.AppendLine(string.Format(ci, "v {0:F5} {1:F5} {2:F5}", q.X, q.Z, -q.Y));
            foreach (var uv in m.Uv) o.AppendLine(string.Format(ci, "vt {0:F5} {1:F5}", uv[0], uv[1]));
            foreach (var q in m.Nrm) o.AppendLine(string.Format(ci, "vn {0:F4} {1:F4} {2:F4}", q.X, q.Z, -q.Y));
            foreach (var sl in m.Slots)
            {
                o.AppendLine("usemtl M_Car_" + car.Spec.Name + "_" + sl);
                var t = m.Tris[sl];
                for (int i = 0; i < t.Count; i += 3)
                    o.AppendLine(string.Format("f {0}/{0}/{0} {1}/{1}/{1} {2}/{2}/{2}", t[i] + 1, t[i + 1] + 1, t[i + 2] + 1));
            }
            File.WriteAllText(Path.Combine(dir, n + ".obj"), o.ToString());
            var mt = new StringBuilder();
            foreach (var sl in m.Slots)
            {
                mt.AppendLine("newmtl M_Car_" + car.Spec.Name + "_" + sl);
                var a = sl == "Paint" ? car.Spec.Paint : set.Slots[sl];
                mt.AppendLine(string.Format(ci, "Kd {0:F5} {1:F5} {2:F5}", a.Albedo.R, a.Albedo.G, a.Albedo.B));
                mt.AppendLine(string.Format(ci, "Ns {0:F1}", (1 - a.Rough) * 500));
                if (sl == "Paint") mt.AppendLine("map_Kd T_Car_" + car.Spec.Name + "_Paint.png");
            }
            File.WriteAllText(Path.Combine(dir, n + ".mtl"), mt.ToString());
        }
    }
}
