// SAUD -- the street-car tool's spec: what saud-fighter-ue5's
// Tools/levels/park_cars.py --json writes into Content/Models/Cars/cars.json.
// That file is the only thing this tool reads. Engine-free: the Unity menu
// and the Mono harness (Tools/cars/run.sh) both build from it.
//
// Metres. x forward (the nose is +x), y left, z up; the origin on the
// ground under the middle of the car. Colours are linear RGB albedo,
// already weathered and held at the look's ink floor by the Python side.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace Saud.CarTool
{
    /// <summary>A small JSON reader: objects, arrays, numbers, strings,
    /// true / false / null. Enough for cars.json, and nothing else needs it.</summary>
    public static class Json
    {
        public static object Parse(string s)
        {
            int i = 0;
            object v = Value(s, ref i);
            Skip(s, ref i);
            if (i != s.Length) throw new FormatException("cars.json: text after the end at " + i);
            return v;
        }

        static void Skip(string s, ref int i)
        {
            while (i < s.Length && char.IsWhiteSpace(s[i])) i++;
        }

        static object Value(string s, ref int i)
        {
            Skip(s, ref i);
            if (i >= s.Length) throw new FormatException("cars.json: ends early");
            char c = s[i];
            if (c == '{')
            {
                var o = new Dictionary<string, object>();
                i++; Skip(s, ref i);
                if (s[i] == '}') { i++; return o; }
                while (true)
                {
                    Skip(s, ref i);
                    string k = Str(s, ref i);
                    Skip(s, ref i);
                    if (s[i] != ':') throw new FormatException("cars.json: ':' wanted at " + i);
                    i++;
                    o[k] = Value(s, ref i);
                    Skip(s, ref i);
                    if (s[i] == ',') { i++; continue; }
                    if (s[i] == '}') { i++; return o; }
                    throw new FormatException("cars.json: ',' or '}' wanted at " + i);
                }
            }
            if (c == '[')
            {
                var a = new List<object>();
                i++; Skip(s, ref i);
                if (s[i] == ']') { i++; return a; }
                while (true)
                {
                    a.Add(Value(s, ref i));
                    Skip(s, ref i);
                    if (s[i] == ',') { i++; continue; }
                    if (s[i] == ']') { i++; return a; }
                    throw new FormatException("cars.json: ',' or ']' wanted at " + i);
                }
            }
            if (c == '"') return Str(s, ref i);
            if (s.Substring(i).StartsWith("true")) { i += 4; return true; }
            if (s.Substring(i).StartsWith("false")) { i += 5; return false; }
            if (s.Substring(i).StartsWith("null")) { i += 4; return null; }
            int j = i;
            while (j < s.Length && "+-0123456789.eE".IndexOf(s[j]) >= 0) j++;
            if (j == i) throw new FormatException("cars.json: a value wanted at " + i);
            double d = double.Parse(s.Substring(i, j - i), NumberStyles.Float, CultureInfo.InvariantCulture);
            i = j;
            return d;
        }

        static string Str(string s, ref int i)
        {
            if (s[i] != '"') throw new FormatException("cars.json: a string wanted at " + i);
            i++;
            var b = new StringBuilder();
            while (s[i] != '"')
            {
                if (s[i] == '\\')
                {
                    i++;
                    char e = s[i];
                    if (e == 'n') b.Append('\n');
                    else if (e == 't') b.Append('\t');
                    else if (e == 'u') { b.Append((char)Convert.ToInt32(s.Substring(i + 1, 4), 16)); i += 4; }
                    else b.Append(e);
                }
                else b.Append(s[i]);
                i++;
            }
            i++;
            return b.ToString();
        }
    }

    public struct Rgb
    {
        public double R, G, B;
        public Rgb(double r, double g, double b) { R = r; G = g; B = b; }
        /// <summary>Rec. 709 luminance of a linear colour -- build_souq._luma's.</summary>
        public double Luma => 0.2126 * R + 0.7152 * G + 0.0722 * B;
        public Rgb Scale(double k) => new Rgb(R * k, G * k, B * k);
        public static Rgb Lerp(Rgb a, Rgb b, double t) =>
            new Rgb(a.R + (b.R - a.R) * t, a.G + (b.G - a.G) * t, a.B + (b.B - a.B) * t);
    }

    public class SlotSpec { public Rgb Albedo; public double Rough; }

    public class WheelSpec
    {
        public double R, Width, RimR, Track, ArchGap;
        public double[] Axles;
    }

    public class BedSpec { public double Tail, Front, Floor, Wall; }
    public class SignSpec { public double X; public double[] Size; }   // size: along x, across y, up z
    public class BandSpec { public Rgb Albedo; public double Z0, Z1; }

    public class CarSpec
    {
        public string Name;
        public double Length, Width, Clear, Belt, Tumble, Hood, TotalHeight;
        public double? Deck;
        public List<double[]> Body, Roof, GlassSide;
        public double[] GlassFront, GlassRear, Seams;
        public WheelSpec Wheel;
        public SlotSpec Paint;
        public bool Rack;
        public BedSpec Bed;
        public SignSpec Sign;
        public BandSpec Band;

        /// <summary>A line (tail to nose, (x, z) points) at x, flat past its ends.</summary>
        public static double LineAt(List<double[]> line, double x)
        {
            if (x <= line[0][0]) return line[0][1];
            for (int i = 1; i < line.Count; i++)
            {
                if (x <= line[i][0])
                {
                    double x0 = line[i - 1][0], x1 = line[i][0];
                    double t = x1 > x0 ? (x - x0) / (x1 - x0) : 0.0;
                    return line[i - 1][1] + (line[i][1] - line[i - 1][1]) * t;
                }
            }
            return line[line.Count - 1][1];
        }
    }

    public class CarSet
    {
        public double InkFloor, InkHold, PaintHi, MirrorOut, RackTop;
        public Rgb Dust, Rust;
        public Dictionary<string, SlotSpec> Slots = new Dictionary<string, SlotSpec>();
        public List<CarSpec> Cars = new List<CarSpec>();

        static double D(object o) => Convert.ToDouble(o, CultureInfo.InvariantCulture);
        static Dictionary<string, object> O(object o) => (Dictionary<string, object>)o;
        static List<object> A(object o) => (List<object>)o;
        static double[] Ds(object o) { var a = A(o); var r = new double[a.Count]; for (int i = 0; i < a.Count; i++) r[i] = D(a[i]); return r; }
        static Rgb C(object o) { var a = Ds(o); return new Rgb(a[0], a[1], a[2]); }
        static List<double[]> Pts(object o) { var r = new List<double[]>(); foreach (var p in A(o)) r.Add(Ds(p)); return r; }
        static bool Has(Dictionary<string, object> d, string k) => d.ContainsKey(k) && d[k] != null;

        public static CarSet Parse(string text)
        {
            var j = O(Json.Parse(text));
            var s = new CarSet
            {
                InkFloor = D(j["ink_floor"]), InkHold = D(j["ink_hold"]), PaintHi = D(j["paint_hi"]),
                MirrorOut = D(j["mirror_out"]), RackTop = D(j["rack_top"]),
            };
            var g = O(j["grime"]);
            s.Dust = C(g["dust"]); s.Rust = C(g["rust"]);
            foreach (var kv in O(j["slots"]))
            {
                var v = O(kv.Value);
                s.Slots[kv.Key] = new SlotSpec { Albedo = C(v["albedo"]), Rough = D(v["rough"]) };
            }
            foreach (var co in A(j["cars"]))
            {
                var c = O(co);
                var w = O(c["wheel"]);
                var gl = O(c["glass"]);
                var p = O(c["paint"]);
                var car = new CarSpec
                {
                    Name = (string)c["name"], Length = D(c["length"]), Width = D(c["width"]), Clear = D(c["clear"]),
                    Belt = D(c["belt"]), Tumble = D(c["tumble"]), Hood = D(c["hood"]),
                    Deck = Has(c, "deck") ? D(c["deck"]) : (double?)null, TotalHeight = D(c["total_height"]),
                    Body = Pts(c["body"]), Roof = Pts(c["roof"]), GlassSide = Pts(gl["side"]),
                    GlassFront = Ds(gl["front"]), GlassRear = Ds(gl["rear"]), Seams = Ds(c["seams"]),
                    Wheel = new WheelSpec
                    {
                        R = D(w["r"]), Width = D(w["width"]), RimR = D(w["rim_r"]), Track = D(w["track"]),
                        ArchGap = D(w["arch_gap"]), Axles = Ds(w["axles"]),
                    },
                    Paint = new SlotSpec { Albedo = C(p["albedo"]), Rough = D(p["rough"]) },
                    Rack = Has(c, "rack") && (bool)c["rack"],
                };
                if (Has(c, "bed"))
                {
                    var b = O(c["bed"]);
                    car.Bed = new BedSpec { Tail = D(b["tail"]), Front = D(b["front"]), Floor = D(b["floor"]), Wall = D(b["wall"]) };
                }
                if (Has(c, "sign"))
                {
                    var sg = O(c["sign"]);
                    car.Sign = new SignSpec { X = D(sg["x"]), Size = Ds(sg["size"]) };
                }
                if (Has(c, "band"))
                {
                    var bd = O(c["band"]);
                    var z = Ds(bd["z"]);
                    car.Band = new BandSpec { Albedo = C(bd["albedo"]), Z0 = z[0], Z1 = z[1] };
                }
                s.Cars.Add(car);
            }
            return s;
        }
    }
}
