// SAUD -- the street-car tool's geometry: closed shells, lofts, lathes,
// boxes, and the finished mesh (normals split at hard edges, UVs projected
// onto the paint's atlas). Engine-free; right-handed, x forward, y left,
// z up, metres. A triangle is wound counter-clockwise seen from outside.
using System;
using System.Collections.Generic;

namespace Saud.CarTool
{
    public struct V3
    {
        public double X, Y, Z;
        public V3(double x, double y, double z) { X = x; Y = y; Z = z; }
        public static V3 operator +(V3 a, V3 b) => new V3(a.X + b.X, a.Y + b.Y, a.Z + b.Z);
        public static V3 operator -(V3 a, V3 b) => new V3(a.X - b.X, a.Y - b.Y, a.Z - b.Z);
        public static V3 operator *(V3 a, double k) => new V3(a.X * k, a.Y * k, a.Z * k);
        public static double Dot(V3 a, V3 b) => a.X * b.X + a.Y * b.Y + a.Z * b.Z;
        public static V3 Cross(V3 a, V3 b) => new V3(a.Y * b.Z - a.Z * b.Y, a.Z * b.X - a.X * b.Z, a.X * b.Y - a.Y * b.X);
        public double Length => Math.Sqrt(X * X + Y * Y + Z * Z);
        public V3 Unit { get { double l = Length; return l > 1e-12 ? this * (1.0 / l) : new V3(0, 0, 0); } }
        public override string ToString() => string.Format("({0:F4}, {1:F4}, {2:F4})", X, Y, Z);
    }

    /// <summary>One closed part of a car. Its triangles index its own points,
    /// so a loft's rings are shared and the part is a manifold by construction.</summary>
    public class Shell
    {
        public string Name;
        public List<V3> P = new List<V3>();
        public List<int> T = new List<int>();          // three per triangle
        public List<string> Slot = new List<string>(); // one per triangle
        public Shell(string name) { Name = name; }
        public int Add(V3 p) { P.Add(p); return P.Count - 1; }
        public void Tri(int a, int b, int c, string slot) { T.Add(a); T.Add(b); T.Add(c); Slot.Add(slot); }
        public void Quad(int a, int b, int c, int d, string slot) { Tri(a, b, c, slot); Tri(a, c, d, slot); }
        public int Tris => Slot.Count;

        public V3 Normal(int t)
        {
            V3 a = P[T[3 * t]], b = P[T[3 * t + 1]], c = P[T[3 * t + 2]];
            return V3.Cross(b - a, c - a);   // twice the area, outward
        }

        /// <summary>Signed volume: positive when every triangle faces out.</summary>
        public double Volume()
        {
            double v = 0;
            for (int t = 0; t < Tris; t++)
                v += V3.Dot(P[T[3 * t]], V3.Cross(P[T[3 * t + 1]], P[T[3 * t + 2]])) / 6.0;
            return v;
        }

        public void Flip()
        {
            for (int t = 0; t < Tris; t++) { int k = T[3 * t + 1]; T[3 * t + 1] = T[3 * t + 2]; T[3 * t + 2] = k; }
        }

        /// <summary>A copy mirrored through y = 0, wound back the right way out.</summary>
        public Shell Mirrored(string name)
        {
            var m = new Shell(name);
            foreach (var p in P) m.P.Add(new V3(p.X, -p.Y, p.Z));
            for (int t = 0; t < Tris; t++) m.Tri(T[3 * t], T[3 * t + 2], T[3 * t + 1], Slot[t]);
            return m;
        }

        public void Move(V3 d) { for (int i = 0; i < P.Count; i++) P[i] = P[i] + d; }
    }

    public static class Parts
    {
        /// <summary>Ear-clipping of a simple polygon given counter-clockwise
        /// in (u, v); returns triangles as index triples into it, counter-clockwise.</summary>
        public static List<int[]> EarClip(IList<double[]> poly)
        {
            var idx = new List<int>();
            for (int i = 0; i < poly.Count; i++) idx.Add(i);
            var tris = new List<int[]>();
            int guard = 0;
            while (idx.Count > 3 && guard++ < 10000)
            {
                bool cut = false;
                for (int k = 0; k < idx.Count; k++)
                {
                    int ia = idx[(k + idx.Count - 1) % idx.Count], ib = idx[k], ic = idx[(k + 1) % idx.Count];
                    double[] a = poly[ia], b = poly[ib], c = poly[ic];
                    double cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
                    if (cross <= 1e-12) continue;                       // reflex or flat: not an ear
                    bool inside = false;
                    foreach (int ip in idx)
                    {
                        if (ip == ia || ip == ib || ip == ic) continue;
                        if (InTri(poly[ip], a, b, c)) { inside = true; break; }
                    }
                    if (inside) continue;
                    tris.Add(new[] { ia, ib, ic });
                    idx.RemoveAt(k);
                    cut = true;
                    break;
                }
                if (!cut) throw new InvalidOperationException("ear clipping found no ear: the outline crosses itself");
            }
            if (idx.Count == 3) tris.Add(new[] { idx[0], idx[1], idx[2] });
            return tris;
        }

        static List<int[]> Cap(string name, double x, double[][] ring)
        {
            try { return EarClip(ring); }
            catch (InvalidOperationException e)
            {
                var pts = new System.Text.StringBuilder();
                foreach (var q in ring) pts.AppendFormat(" ({0:F4},{1:F4})", q[0], q[1]);
                throw new InvalidOperationException(name + " at x " + x.ToString("F3") + ": " + e.Message + ":" + pts);
            }
        }

        static bool InTri(double[] p, double[] a, double[] b, double[] c)
        {
            double d1 = (p[0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (p[1] - b[1]);
            double d2 = (p[0] - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (p[1] - c[1]);
            double d3 = (p[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (p[1] - a[1]);
            bool neg = d1 < 0 || d2 < 0 || d3 < 0, pos = d1 > 0 || d2 > 0 || d3 > 0;
            return !(neg && pos);
        }

        /// <summary>A loft through rings standing at increasing x. Each ring is
        /// (y, z) points counter-clockwise seen from the front (+x), the same
        /// count in every ring. slot(i, j) names the quad between ring i and
        /// i + 1 from point j to j + 1. Both ends are capped.</summary>
        public static Shell Loft(string name, double[] xs, List<double[][]> rings, Func<int, int, string> slot,
                                 string capTail, string capNose)
        {
            var s = new Shell(name);
            int n = rings[0].Length;
            var id = new int[xs.Length, n];
            for (int i = 0; i < xs.Length; i++)
            {
                if (rings[i].Length != n) throw new ArgumentException(name + ": ring " + i + " has " + rings[i].Length + " points, not " + n);
                for (int j = 0; j < n; j++) id[i, j] = s.Add(new V3(xs[i], rings[i][j][0], rings[i][j][1]));
            }
            for (int i = 0; i + 1 < xs.Length; i++)
                for (int j = 0; j < n; j++)
                {
                    int j1 = (j + 1) % n;
                    s.Quad(id[i, j], id[i, j1], id[i + 1, j1], id[i + 1, j], slot(i, j));
                }
            int last = xs.Length - 1;
            foreach (var t in Cap(name, xs[0], rings[0])) s.Tri(id[0, t[0]], id[0, t[2]], id[0, t[1]], capTail);     // faces -x
            foreach (var t in Cap(name, xs[last], rings[last])) s.Tri(id[last, t[0]], id[last, t[1]], id[last, t[2]], capNose);
            return s;
        }

        /// <summary>A solid of revolution about the axis through c along +y: the
        /// profile is (radius, offset along y) points, closed; a point on the axis
        /// (radius 0) is one vertex. Turned the right way out by its volume.</summary>
        public static Shell Lathe(string name, V3 c, IList<double[]> profile, int segs, string slot)
        {
            var s = new Shell(name);
            int n = profile.Count;
            var id = new int[n, segs];
            for (int j = 0; j < n; j++)
            {
                double r = profile[j][0], dy = profile[j][1];
                if (r < 1e-9)
                {
                    int a = s.Add(new V3(c.X, c.Y + dy, c.Z));
                    for (int k = 0; k < segs; k++) id[j, k] = a;
                    continue;
                }
                for (int k = 0; k < segs; k++)
                {
                    double t = 2.0 * Math.PI * k / segs - Math.PI / 2.0;      // k = 0 is straight down
                    id[j, k] = s.Add(new V3(c.X + r * Math.Cos(t), c.Y + dy, c.Z + r * Math.Sin(t)));
                }
            }
            for (int j = 0; j < n; j++)
            {
                int j1 = (j + 1) % n;
                for (int k = 0; k < segs; k++)
                {
                    int k1 = (k + 1) % segs;
                    int a = id[j, k], b = id[j, k1], cc = id[j1, k1], d = id[j1, k];
                    if (a == b && cc == d) continue;
                    if (a == b) s.Tri(a, cc, d, slot);
                    else if (cc == d) s.Tri(a, b, cc, slot);
                    else s.Quad(a, b, cc, d, slot);
                }
            }
            if (s.Volume() < 0) s.Flip();
            return s;
        }

        /// <summary>A box, centre c, half-sizes h, turned yaw radians about z.</summary>
        public static Shell Box(string name, V3 c, V3 h, string slot, double yaw = 0.0)
        {
            var s = new Shell(name);
            double cy = Math.Cos(yaw), sy = Math.Sin(yaw);
            int[] v = new int[8];
            for (int i = 0; i < 8; i++)
            {
                double x = ((i & 1) != 0 ? 1 : -1) * h.X, y = ((i & 2) != 0 ? 1 : -1) * h.Y, z = ((i & 4) != 0 ? 1 : -1) * h.Z;
                v[i] = s.Add(new V3(c.X + x * cy - y * sy, c.Y + x * sy + y * cy, c.Z + z));
            }
            // -x, +x, -y, +y, -z, +z, each counter-clockwise from outside
            s.Quad(v[0], v[4], v[6], v[2], slot);
            s.Quad(v[1], v[3], v[7], v[5], slot);
            s.Quad(v[0], v[1], v[5], v[4], slot);
            s.Quad(v[2], v[6], v[7], v[3], slot);
            s.Quad(v[0], v[2], v[3], v[1], slot);
            s.Quad(v[4], v[5], v[7], v[6], slot);
            return s;
        }
    }

    /// <summary>The finished mesh: one vertex list, triangles per material slot.</summary>
    public class MeshData
    {
        public List<V3> Pos = new List<V3>(), Nrm = new List<V3>();
        public List<double[]> Uv = new List<double[]>();
        public List<string> Slots = new List<string>();
        public Dictionary<string, List<int>> Tris = new Dictionary<string, List<int>>();
        public int TriCount { get { int n = 0; foreach (var l in Tris.Values) n += l.Count / 3; return n; } }
    }

    /// <summary>Where a surface lands on the paint's atlas: the sides in the
    /// left half (x along, z up), the tops in the lower right quarter (x, y),
    /// the ends in the upper right (y, z). The paint (CarPaint) reads the
    /// same frame, so the two cannot disagree.</summary>
    public class Atlas
    {
        public double L, W, H;
        public Atlas(double length, double width, double height) { L = length; W = width; H = height; }
        public const int Side = 0, Top = 1, End = 2;

        public static int RegionOf(V3 n)
        {
            double ax = Math.Abs(n.X), ay = Math.Abs(n.Y), az = Math.Abs(n.Z);
            if (ay >= ax && ay >= az) return Side;
            if (az >= ax) return Top;
            return End;
        }

        public double[] Uv(V3 p, int region)
        {
            switch (region)
            {
                case Side: return new[] { 0.5 * (p.X / L + 0.5), p.Z / H };
                case Top: return new[] { 0.5 + 0.5 * (p.X / L + 0.5), 0.5 * (p.Y / W + 0.5) };
                default: return new[] { 0.5 + 0.5 * (p.Y / W + 0.5), 0.5 + 0.5 * (p.Z / H) };
            }
        }
    }

    public static class Finish
    {
        /// <summary>Normals averaged over the faces round a point that turn less
        /// than `crease` from this one (a hard edge splits); UVs by the face's
        /// own direction; identical corners merged.</summary>
        public static MeshData Make(IList<Shell> shells, Atlas atlas, double creaseDeg = 40.0)
        {
            var m = new MeshData();
            var key = new Dictionary<string, int>();
            double cos = Math.Cos(creaseDeg * Math.PI / 180.0);
            foreach (var s in shells)
            {
                var fn = new V3[s.Tris];
                var byPoint = new Dictionary<int, List<int>>();
                // weld coincident points inside a shell (a lathe's seam, a cap's ring)
                var weld = new Dictionary<string, int>();
                var w = new int[s.P.Count];
                for (int i = 0; i < s.P.Count; i++)
                {
                    var p = s.P[i];
                    string k = Math.Round(p.X * 1e5) + "," + Math.Round(p.Y * 1e5) + "," + Math.Round(p.Z * 1e5);
                    if (!weld.TryGetValue(k, out w[i])) { weld[k] = i; w[i] = i; }
                }
                for (int t = 0; t < s.Tris; t++)
                {
                    fn[t] = s.Normal(t);
                    for (int c = 0; c < 3; c++)
                    {
                        int pi = w[s.T[3 * t + c]];
                        if (!byPoint.TryGetValue(pi, out var l)) byPoint[pi] = l = new List<int>();
                        l.Add(t);
                    }
                }
                for (int t = 0; t < s.Tris; t++)
                {
                    V3 nf = fn[t].Unit;
                    int region = Atlas.RegionOf(nf);
                    string slot = s.Slot[t];
                    if (!m.Tris.TryGetValue(slot, out var list)) { m.Tris[slot] = list = new List<int>(); m.Slots.Add(slot); }
                    for (int c = 0; c < 3; c++)
                    {
                        int pi = s.T[3 * t + c];
                        V3 sum = new V3(0, 0, 0);
                        foreach (int o in byPoint[w[pi]])
                            if (V3.Dot(fn[o].Unit, nf) >= cos) sum = sum + fn[o];
                        V3 n = sum.Length > 1e-12 ? sum.Unit : nf;
                        V3 p = s.P[pi];
                        double[] uv = atlas.Uv(p, region);
                        if (slot != "Paint")                        // only the paint is textured
                        {
                            uv[0] = Math.Min(1, Math.Max(0, uv[0])); uv[1] = Math.Min(1, Math.Max(0, uv[1]));
                        }
                        string k = string.Format("{0},{1},{2},{3},{4},{5},{6},{7}",
                            Math.Round(p.X * 1e5), Math.Round(p.Y * 1e5), Math.Round(p.Z * 1e5),
                            Math.Round(n.X * 1e4), Math.Round(n.Y * 1e4), Math.Round(n.Z * 1e4),
                            Math.Round(uv[0] * 1e5), Math.Round(uv[1] * 1e5));
                        if (!key.TryGetValue(k, out int vi))
                        {
                            vi = m.Pos.Count; key[k] = vi;
                            m.Pos.Add(p); m.Nrm.Add(n); m.Uv.Add(uv);
                        }
                        list.Add(vi);
                    }
                }
            }
            return m;
        }
    }
}
