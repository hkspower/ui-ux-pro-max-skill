// SAUD -- the street-car tool's builder. One car from its spec: the lower
// body lofted along its length with the wheel arches cut out of it, the
// cabin lofted on the belt with its glass, the pickup's open bed, four
// wheels (a tyre and a dished rim with spokes), lamps, a grille, bumpers,
// plates, door mirrors, the SUV's roof rack and the taxi's sign. Every
// part is a closed shell. Engine-free: Unity's menu and the Mono harness
// build the same car from the same numbers.
using System;
using System.Collections.Generic;
using System.Linq;

namespace Saud.CarTool
{
    /// <summary>Faults put in on purpose, one at a time, to prove each check
    /// catches the thing it guards (the harness's --bite).</summary>
    public enum Sabotage
    {
        None, Flip, InsideOut, TightArch, NoGlass, Lopsided, DarkSeam, Hover, Long, Hole, Dense, BadUv, NoTyre,
    }

    /// <summary>The body's lines as functions of x (m): its half-width, the
    /// floor, the sill (cut up round each wheel), the top, the roof. The
    /// builder lofts them and the paint reads them, so seams, rust and dust
    /// land where the metal is.</summary>
    public class Profile
    {
        public readonly CarSpec C;
        public readonly double Xe;          // the body's ends; the bumpers take the last BUMPER_OUT
        public readonly double Yin;         // the inner edge of the sill's step, clear of the tyres
        public double ArchGap;
        public const double BUMPER_OUT = 0.05, TAPER = 0.07, TAPER_RUN = 0.25, NOSE_LIFT = 0.12, NOSE_RUN = 0.45;
        public const double SILL_STEP = 0.04, CABIN_IN = 0.87, CABIN_MIN_H = 0.03;

        public Profile(CarSpec c)
        {
            C = c;
            Xe = c.Length / 2 - BUMPER_OUT;
            Yin = c.Wheel.Track / 2 - c.Wheel.Width / 2 - 0.03;
            ArchGap = c.Wheel.ArchGap;
        }

        /// <summary>Half the body's width: the car's own, rounded off in plan at the ends.</summary>
        public double Hw(double x)
        {
            double t = Math.Max(0.0, (Math.Abs(x) - (Xe - TAPER_RUN)) / TAPER_RUN);
            t = Math.Min(1.0, t);
            return C.Width / 2 * (1.0 - TAPER * (1.0 - Math.Sqrt(Math.Max(0.0, 1.0 - t * t))));
        }

        /// <summary>The underside: the sill's height, lifted toward each end (the approach).</summary>
        public double Zb(double x)
        {
            double t = Math.Max(0.0, (Math.Abs(x) - (Xe - NOSE_RUN)) / NOSE_RUN);
            return C.Clear + NOSE_LIFT * t * t;
        }

        /// <summary>The arch over a wheel at x, or 0 away from one.</summary>
        public double Arch(double x)
        {
            double best = 0;
            foreach (double xa in C.Wheel.Axles)
            {
                double ra = C.Wheel.R + ArchGap, dx = x - xa;
                if (Math.Abs(dx) < ra) best = Math.Max(best, C.Wheel.R + Math.Sqrt(ra * ra - dx * dx));
            }
            return best;
        }

        /// <summary>The outer bottom edge: the sill, or the arch where there is one.</summary>
        public double Zs(double x) => Math.Max(Zb(x) + SILL_STEP, Arch(x));
        public double Zt(double x) => CarSpec.LineAt(C.Body, x);
        public double Zr(double x) => CarSpec.LineAt(C.Roof, x);
        public double RoofX0 => C.Roof[0][0];
        public double RoofX1 => C.Roof[C.Roof.Count - 1][0];
        public double CabinH(double x) => Math.Max(CABIN_MIN_H, Zr(x) - C.Belt);
        public double CabinWb(double x) => Hw(x) * CABIN_IN;
        public double CabinWr(double x) => CabinWb(x) * C.Tumble;
        public double Crown(double h) => Math.Min(0.025, 0.25 * h);
        public double Htot => C.TotalHeight;
    }

    public class BuiltCar
    {
        public CarSpec Spec;
        public Profile Prof;
        public Atlas Atlas;
        public List<Shell> Shells = new List<Shell>();
        public MeshData Mesh;
        public Sabotage Sab;
    }

    public static class CarBuilder
    {
        const double C1 = 0.035;        // the sill's chamfer
        const double WINDOW_BOW = 0.004;

        static List<double> Stations(Profile p, double x0, double x1, double step, IEnumerable<double> extra)
        {
            var xs = new List<double>();
            for (double x = x0; x < x1 - 1e-6; x += step) xs.Add(x);
            xs.Add(x1);
            foreach (double xa in p.C.Wheel.Axles)
            {
                double ra = p.C.Wheel.R + p.ArchGap;
                for (double x = xa - ra - 0.05; x <= xa + ra + 0.05; x += 0.025) xs.Add(x);
                xs.Add(xa - ra); xs.Add(xa + ra);
            }
            for (double x = x0; x < x0 + 0.3; x += 0.04) xs.Add(x);
            for (double x = x1; x > x1 - 0.3; x -= 0.04) xs.Add(x);
            foreach (var pt in p.C.Body) xs.Add(pt[0]);
            foreach (double e in extra) xs.Add(e);
            var r = xs.Where(x => x >= x0 - 1e-9 && x <= x1 + 1e-9).OrderBy(x => x).ToList();
            var u = new List<double>();
            foreach (double x in r) if (u.Count == 0 || x - u[u.Count - 1] > 0.004) u.Add(x);
            if (Math.Abs(u[u.Count - 1] - x1) > 1e-9) { if (x1 - u[u.Count - 1] < 0.004) u[u.Count - 1] = x1; else u.Add(x1); }
            u[0] = x0;
            return u;
        }

        static double[][] Ring(List<double[]> half, double yCentreBottom, double zBottom, double zTop)
        {
            // bottom centre, the +y side upward, the top centre, the -y side downward
            var ring = new List<double[]> { new[] { 0.0, zBottom } };
            foreach (var h in half) ring.Add(new[] { h[0], h[1] });
            ring.Add(new[] { 0.0, zTop });
            for (int i = half.Count - 1; i >= 0; i--) ring.Add(new[] { -half[i][0], half[i][1] });
            return ring.ToArray();
        }

        static double[][] BodyRing(Profile p, double x)
        {
            double w = p.Hw(x), zb = p.Zb(x), zs = p.Zs(x), zt = p.Zt(x);
            double z4 = zs + C1, z6 = zt - 0.07;
            var half = new List<double[]>
            {
                new[] { p.Yin, zb }, new[] { p.Yin, zs }, new[] { w - C1, zs }, new[] { w, z4 },
                new[] { w, (z4 + z6) / 2 }, new[] { w * 0.985, z6 }, new[] { w * 0.95, zt - 0.02 }, new[] { w * 0.87, zt },
            };
            return Ring(half, 0, zb, zt);
        }

        static double[][] BedRing(Profile p, double x)
        {
            double w = p.Hw(x), zb = p.Zb(x), zs = p.Zs(x), zt = p.Zt(x), t = p.C.Bed.Wall, zf = p.C.Bed.Floor;
            double z4 = zs + C1, z6 = zt - 0.02;
            var half = new List<double[]>
            {
                new[] { p.Yin, zb }, new[] { p.Yin, zs }, new[] { w - C1, zs }, new[] { w, z4 },
                new[] { w, (z4 + z6) / 2 }, new[] { w, z6 }, new[] { w - 0.012, zt }, new[] { w - t, zt }, new[] { w - t, zf },
            };
            return Ring(half, 0, zb, zf);
        }

        static double[][] CabinRing(Profile p, double x)
        {
            double wb = p.CabinWb(x), wr = p.CabinWr(x), h = p.CabinH(x), belt = p.C.Belt, top = belt + h, cr = p.Crown(h);
            double[] q1 = { wb, belt }, q4 = { wr, top - cr };
            // the window line bowed 4 mm out, so the side is curved glass and no
            // three points of a ring are ever on one line (a thin end ring would not cap)
            Func<double, double[]> along = f => new[] { q1[0] + (q4[0] - q1[0]) * f + WINDOW_BOW, q1[1] + (q4[1] - q1[1]) * f };
            var half = new List<double[]> { q1, along(0.10), along(0.88), q4, new[] { wr * 0.8, top - cr * 0.35 } };
            return Ring(half, 0, belt, top);
        }

        static bool InAny(double x, IEnumerable<double[]> spans) => spans.Any(s => x > s[0] && x < s[1]);

        public static BuiltCar Build(CarSpec c, CarSet set, Sabotage sab = Sabotage.None)
        {
            var p = new Profile(c);
            if (sab == Sabotage.TightArch) p.ArchGap = -0.04;
            var car = new BuiltCar { Spec = c, Prof = p, Sab = sab, Atlas = new Atlas(c.Length, c.Width, c.TotalHeight) };
            var S = car.Shells;
            var extra = new List<double>(c.Seams) { c.Hood };
            if (c.Deck.HasValue) extra.Add(c.Deck.Value);

            // --- the lower body (the pickup's in two: the bed, and the cab and bonnet)
            if (c.Bed != null)
            {
                var xa = Stations(p, -p.Xe, c.Bed.Front, 0.10, extra).ToArray();
                var ra = xa.Select(x => BedRing(p, x)).ToList();
                int n = ra[0].Length;
                // the bed's inside (its walls' inner faces and the floor) is liner, not paint
                S.Add(Parts.Loft("Bed", xa, ra, (i, j) => (j >= n / 2 - 2 && j <= n / 2 + 1) ? "Trim" : "Paint", "Paint", "Paint"));
                var xb = Stations(p, c.Bed.Front + 0.005, p.Xe, 0.10, extra).ToArray();
                S.Add(Parts.Loft("Body", xb, xb.Select(x => BodyRing(p, x)).ToList(), (i, j) => "Paint", "Paint", "Paint"));
            }
            else
            {
                var xs = Stations(p, -p.Xe, p.Xe, 0.10, extra).ToArray();
                S.Add(Parts.Loft("Body", xs, xs.Select(x => BodyRing(p, x)).ToList(), (i, j) => "Paint", "Paint", "Paint"));
            }

            // --- the cabin, on the belt; glass where the spans say
            {
                var ex = new List<double>();
                foreach (var s in c.GlassSide) { ex.Add(s[0]); ex.Add(s[1]); }
                ex.AddRange(c.GlassFront); ex.AddRange(c.GlassRear);
                foreach (var pt in c.Roof) ex.Add(pt[0]);
                var xs = new List<double>();
                for (double x = p.RoofX0; x < p.RoofX1; x += 0.06) xs.Add(x);
                xs.Add(p.RoofX1); xs.AddRange(ex);
                var st = xs.Where(x => x >= p.RoofX0 - 1e-9 && x <= p.RoofX1 + 1e-9).OrderBy(x => x).ToList();
                var u = new List<double>();
                foreach (double x in st) if (u.Count == 0 || x - u[u.Count - 1] > 0.004) u.Add(x);
                u[u.Count - 1] = p.RoofX1;
                var xc = u.ToArray();
                var screens = new List<double[]> { c.GlassFront, c.GlassRear };
                bool glass = sab != Sabotage.NoGlass;
                S.Add(Parts.Loft("Cabin", xc, xc.Select(x => CabinRing(p, x)).ToList(), (i, j) =>
                {
                    double xm = (xc[i] + xc[i + 1]) / 2;
                    if (!glass) return "Paint";
                    if ((j == 2 || j == 9) && InAny(xm, c.GlassSide)) return "Glass";
                    if (j >= 4 && j <= 7 && InAny(xm, screens)) return "Glass";
                    return "Paint";
                }, "Paint", "Paint"));
            }

            // --- the wheels
            var w = c.Wheel;
            int segs = sab == Sabotage.Dense ? 400 : 32;
            double tw = w.Width, R = w.R, rr = w.RimR;
            var tyre = new List<double[]>
            {
                new[] { rr, -tw / 2 }, new[] { R - 0.035, -tw / 2 }, new[] { R - 0.012, -tw / 2 + 0.008 }, new[] { R, -tw / 2 + 0.035 },
                new[] { R, tw / 2 - 0.035 }, new[] { R - 0.012, tw / 2 - 0.008 }, new[] { R - 0.035, tw / 2 }, new[] { rr, tw / 2 },
            };
            double a = tw / 2 - 0.022, b = -tw / 2 + 0.03, lip = rr - 0.004;
            var rim = new List<double[]>
            {
                new[] { 0.0, a }, new[] { rr * 0.30, a }, new[] { rr * 0.36, a - 0.014 }, new[] { rr * 0.90, a - 0.022 },
                new[] { lip, a - 0.006 }, new[] { lip, b }, new[] { 0.0, b },
            };
            var wheels = new List<Shell>();
            foreach (double xa in w.Axles)
            {
                string end = xa > 0 ? "F" : "R";
                var ctr = new V3(xa, w.Track / 2, R);
                if (!(sab == Sabotage.NoTyre && xa > 0)) wheels.Add(Parts.Lathe("Tyre_" + end + "L", ctr, tyre, segs, "Tyre"));
                wheels.Add(Parts.Lathe("Rim_" + end + "L", ctr, rim, segs, "Rim"));
                for (int k = 0; k < 5; k++)
                {
                    double t = 2 * Math.PI * k / 5 + 0.3;
                    var ex_ = new V3(Math.Cos(t), 0, Math.Sin(t));
                    double rm = rr * 0.63;
                    wheels.Add(OBox("Spoke_" + end + "L" + k, ctr + ex_ * rm + new V3(0, a - 0.016, 0), ex_, new V3(0, 1, 0),
                                    rr * 0.27, 0.007, 0.018, "Rim"));
                }
            }
            S.AddRange(wheels);
            foreach (var s in wheels) S.Add(s.Mirrored(s.Name.Replace("L", "R")));

            // --- lamps, grille, bumpers, plates
            double xe = p.Xe, wN = p.Hw(xe), wT = p.Hw(-xe), ztN = p.Zt(xe), ztT = p.Zt(-xe), zbN = p.Zb(xe), zbT = p.Zb(-xe);
            double lampY = wN - 0.06 - 0.15;
            var sided = new List<Shell>
            {
                Parts.Box("HeadLamp_L", new V3(xe + 0.004, lampY, ztN - 0.12), new V3(0.02, 0.15, 0.06), "Lamp"),
                // a pickup's lamps sit under its bed's floor line, on the body, not in the open bed
                Parts.Box("TailLamp_L", new V3(-xe - 0.004, wT - 0.05 - 0.13,
                          c.Bed != null ? Math.Min(ztT - 0.14, c.Bed.Floor - 0.12) : ztT - 0.14), new V3(0.02, 0.13, 0.08), "Tail"),
            };
            if (c.Bed != null)
            {
                // the tailgate closes the bed's open end from the floor to the walls' top
                double zf = c.Bed.Floor - 0.01, zg = ztT - 0.012, wy = wT - c.Bed.Wall;
                S.Add(Parts.Box("Tailgate", new V3(-xe + 0.0185, 0, (zf + zg) / 2), new V3(0.0215, wy, (zg - zf) / 2), "Paint"));   // 3 mm proud of the tail, not in its plane
            }
            S.Add(Parts.Box("Grille", new V3(xe + 0.003, 0, ztN - 0.13), new V3(0.015, Math.Max(0.10, lampY - 0.15 - 0.03), 0.07), "Trim"));
            double bx = (c.Length / 2 - (xe - 0.06)) / 2;
            S.Add(Parts.Box("Bumper_F", new V3(c.Length / 2 - bx, 0, zbN + 0.12), new V3(bx, wN * 0.97, 0.09), "Trim"));
            S.Add(Parts.Box("Bumper_R", new V3(-c.Length / 2 + bx, 0, zbT + 0.12), new V3(bx, wT * 0.97, 0.09), "Trim"));
            S.Add(Parts.Box("Plate_F", new V3(c.Length / 2 + 0.005, 0, zbN + 0.12), new V3(0.005, 0.26, 0.055), "Plate"));
            S.Add(Parts.Box("Plate_R", new V3(-xe - 0.005, 0, zbT + 0.31), new V3(0.005, 0.26, 0.055), "Plate"));

            // --- the door mirrors: their outer edge where the footprint says
            {
                double xm = c.GlassFront[1] - 0.10, zm = c.Belt + 0.12, yOut = c.Width / 2 + set.MirrorOut;
                double yIn = c.Width / 2 + 0.02, y0 = p.Hw(xm) * 0.84;
                sided.Add(Parts.Box("Mirror_L", new V3(xm, (yIn + yOut) / 2, zm), new V3(0.05, (yOut - yIn) / 2, 0.065), "Trim"));
                sided.Add(Parts.Box("MirrorArm_L", new V3(xm, (y0 + yIn) / 2 + 0.005, zm - 0.02), new V3(0.02, (yIn - y0) / 2 + 0.005, 0.015), "Trim"));
            }

            // --- the SUV's roof rack: two rails, three bars, six posts; its top is the spec's
            if (c.Rack)
            {
                double zMax = c.Roof.Max(q => q[1]);
                double x0 = c.Roof.Where(q => q[1] >= zMax - 0.06).Min(q => q[0]) + 0.12;
                double x1 = c.Roof.Where(q => q[1] >= zMax - 0.06).Max(q => q[0]) - 0.12;
                double ry = p.CabinWr((x0 + x1) / 2) * 0.78, zTop = zMax + set.RackTop;
                sided.Add(Parts.Box("Rail_L", new V3((x0 + x1) / 2, ry, zTop - 0.02), new V3((x1 - x0) / 2, 0.02, 0.02), "Trim"));
                foreach (double xp in new[] { x0 + 0.05, (x0 + x1) / 2, x1 - 0.05 })
                {
                    double zb0 = p.Zr(xp) - 0.03, zb1 = zTop - 0.04;
                    sided.Add(Parts.Box("Post_L" + xp.ToString("F2"), new V3(xp, ry, (zb0 + zb1) / 2), new V3(0.025, 0.015, (zb1 - zb0) / 2), "Trim"));
                }
                foreach (double xp in new[] { x0 + 0.35, (x0 + x1) / 2, x1 - 0.35 })
                    S.Add(Parts.Box("Bar" + xp.ToString("F2"), new V3(xp, 0, zTop - 0.03), new V3(0.018, ry - 0.02, 0.012), "Trim"));
            }

            // --- the taxi's sign on the roof
            if (c.Sign != null)
            {
                var z = c.Sign.Size;
                double z0 = p.Zr(c.Sign.X) - 0.008;
                S.Add(Parts.Box("Sign", new V3(c.Sign.X, 0, z0 + z[2] / 2), new V3(z[0] / 2, z[1] / 2, z[2] / 2), "Sign"));
            }

            S.AddRange(sided);
            foreach (var s in sided)
            {
                var m = s.Mirrored(s.Name.Replace("_L", "_R"));
                if (sab == Sabotage.Lopsided && s.Name == "Mirror_L") m.Move(new V3(0.03, 0, 0));
                S.Add(m);
            }

            // --- the sabotages that act on the finished shells
            var body = S.First(s => s.Name == "Body");
            if (sab == Sabotage.Flip) { int k = body.T[3]; body.T[3] = body.T[4]; body.T[4] = k; }
            if (sab == Sabotage.InsideOut) body.Flip();
            if (sab == Sabotage.Hole) { body.T.RemoveRange(body.T.Count - 3, 3); body.Slot.RemoveAt(body.Slot.Count - 1); }
            if (sab == Sabotage.Hover) foreach (var s in S) s.Move(new V3(0, 0, 0.03));
            if (sab == Sabotage.Long) foreach (var s in S) for (int i = 0; i < s.P.Count; i++) s.P[i] = new V3(s.P[i].X * 1.05, s.P[i].Y, s.P[i].Z);

            car.Mesh = Finish.Make(S, car.Atlas);
            if (sab == Sabotage.BadUv) foreach (var uv in car.Mesh.Uv) { uv[0] *= 1.5; uv[1] *= 1.5; }
            return car;
        }

        /// <summary>A box along the axes ex, ey, ex x ey (right-handed), half-sizes hx, hy, hz.</summary>
        public static Shell OBox(string name, V3 c, V3 ex, V3 ey, double hx, double hy, double hz, string slot)
        {
            var ez = V3.Cross(ex, ey);
            var s = Parts.Box(name, new V3(0, 0, 0), new V3(hx, hy, hz), slot);
            for (int i = 0; i < s.P.Count; i++)
            {
                var q = s.P[i];
                s.P[i] = c + ex * q.X + ey * q.Y + ez * q.Z;
            }
            return s;
        }
    }
}
