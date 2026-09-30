// SAUD -- the street-car tool's paint: one texture per car, laid out on the
// Atlas the builder's UVs use (sides left, tops lower right, ends upper
// right). The car's weathered paint, road dust up from the sills and over
// the roof, rust at the arches and sills, soot streaks under the windows,
// scratches, and the door and bonnet seams held one 8-bit step over the ink
// floor -- dark, never the ink. Nothing in it is darker than the floor or
// paler than paint_hi, and the check reads the 8-bit texels back to prove it.
using System;
using System.IO;
using System.IO.Compression;

namespace Saud.CarTool
{
    public class PaintMap
    {
        public int W, H;
        public byte[] Rgb;          // row 0 is the top of the image (v = 1)
        public double DarkestLuma, PalestLuma;
    }

    public static class CarPaint
    {
        public const int SIZE_W = 1024, SIZE_H = 512;
        const double SEAM_HALF = 0.0035;       // m, half a seam's width

        static double Hash(int x, int y, int s)
        {
            unchecked
            {
                uint h = (uint)(x * 374761393 + y * 668265263 + s * 2246822519);
                h = (h ^ (h >> 13)) * 1274126177u;
                h ^= h >> 16;
                return (h & 0xFFFFFF) / (double)0x1000000;
            }
        }

        static double Noise(double x, double y, int s)
        {
            int xi = (int)Math.Floor(x), yi = (int)Math.Floor(y);
            double fx = x - xi, fy = y - yi;
            fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy);
            double a = Hash(xi, yi, s), b = Hash(xi + 1, yi, s), c = Hash(xi, yi + 1, s), d = Hash(xi + 1, yi + 1, s);
            return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
        }

        static double Fbm(double x, double y, int s)
        {
            return 0.55 * Noise(x, y, s) + 0.30 * Noise(x * 2.1, y * 2.1, s + 7) + 0.15 * Noise(x * 4.3, y * 4.3, s + 13);
        }

        static double Clamp01(double v) => v < 0 ? 0 : v > 1 ? 1 : v;

        static Rgb AtLuma(Rgb c, double y)
        {
            double l = c.Luma;
            return l > 1e-9 ? c.Scale(y / l) : new Rgb(y, y, y);
        }

        public static double ToSrgb(double v)
        {
            v = Clamp01(v);
            return v <= 0.0031308 ? 12.92 * v : 1.055 * Math.Pow(v, 1.0 / 2.4) - 0.055;
        }

        public static double FromSrgb(double s) => s <= 0.04045 ? s / 12.92 : Math.Pow((s + 0.055) / 1.055, 2.4);

        /// <summary>The linear albedo at an atlas coordinate (u, v, v up).</summary>
        public static Rgb At(BuiltCar car, CarSet set, double u, double v)
        {
            var c = car.Spec; var p = car.Prof; var a = car.Atlas;
            int seed = 0; foreach (char ch in c.Name) seed = (seed * 31 + ch) & 0xFFFF;   // stable: string.GetHashCode is not, across runtimes
            Rgb paint = c.Paint.Albedo, col;
            double hold = set.InkHold * (car.Sab == Sabotage.DarkSeam ? 0.3 : 1.0);
            if (u < 0.5)
            {
                // the sides: x along, z up
                double x = (u / 0.5 - 0.5) * a.L, z = v * a.H;
                col = paint;
                if (c.Band != null && z >= c.Band.Z0 && z <= c.Band.Z1) col = c.Band.Albedo;
                double zs = p.Zs(x);
                // dust thickest at the sill and thinning up the door, patchy
                double dust = 0.08 + 0.55 * Math.Pow(Clamp01((0.62 - z) / 0.50), 1.5);
                dust *= 0.65 + 0.7 * Fbm(x * 3.0, z * 6.0, seed);
                // soot run down from the window line
                double below = c.Belt - z;
                if (below > 0 && below < 0.40)
                {
                    double run = Math.Pow(Noise(x * 26.0, 0.5, seed + 3), 6.0) * (1.0 - below / 0.40);
                    col = Rgb.Lerp(col, col.Scale(0.55), run * 0.6);
                }
                col = Rgb.Lerp(col, set.Dust, Clamp01(dust));
                // rust where the paint has gone: round the arches and along the sill
                double nearArch = 1.0;
                foreach (double xa in c.Wheel.Axles)
                {
                    double ra = c.Wheel.R + p.ArchGap;
                    double dx = x - xa, dz = z - c.Wheel.R;
                    nearArch = Math.Min(nearArch, Math.Abs(Math.Sqrt(dx * dx + dz * dz) - ra));
                }
                double rustZone = Math.Max(Clamp01(1.0 - nearArch / 0.07), Clamp01(1.0 - (z - zs) / 0.10));
                if (Fbm(x * 9.0, z * 9.0, seed + 5) * rustZone > 0.42) col = Rgb.Lerp(col, set.Rust, 0.85);
                // scratches: a few fine lines of bare primer
                for (int k = 0; k < 6; k++)
                {
                    double x0 = (Hash(k, 1, seed) - 0.5) * a.L * 0.8, z0 = 0.45 + Hash(k, 2, seed) * 0.45;
                    double len = 0.2 + Hash(k, 3, seed) * 0.5, ang = (Hash(k, 4, seed) - 0.5) * 0.5;
                    double tx = Math.Cos(ang), tz = Math.Sin(ang);
                    double along = (x - x0) * tx + (z - z0) * tz, across = -(x - x0) * tz + (z - z0) * tx;
                    if (along > 0 && along < len && Math.Abs(across) < 0.0018) col = Rgb.Lerp(col, new Rgb(0.20, 0.20, 0.20), 0.5);
                }
                // the door seams, from the sill to the window
                foreach (double sx in c.Seams)
                    if (Math.Abs(x - sx) < SEAM_HALF && z > zs + 0.05 && z < c.Belt - 0.01) col = AtLuma(paint, hold);
            }
            else if (v < 0.5)
            {
                // the tops: x along, y across
                double x = ((u - 0.5) / 0.5 - 0.5) * a.L, y = (v / 0.5 - 0.5) * a.W;
                col = paint;
                double dust = (0.20 + 0.18 * Fbm(x * 2.0, y * 2.0, seed + 11));
                col = Rgb.Lerp(col, set.Dust, Clamp01(dust));
                if (Fbm(x * 11.0, y * 11.0, seed + 17) > 0.80) col = Rgb.Lerp(col, set.Rust, 0.5);   // a few spots where the lacquer has gone
                double lim = p.Hw(x) * 0.85;
                if (Math.Abs(x - c.Hood) < SEAM_HALF && Math.Abs(y) < lim) col = AtLuma(paint, hold);
                if (c.Deck.HasValue && Math.Abs(x - c.Deck.Value) < SEAM_HALF && Math.Abs(y) < lim) col = AtLuma(paint, hold);
            }
            else
            {
                // the ends: y across, z up
                double y = ((u - 0.5) / 0.5 - 0.5) * a.W, z = ((v - 0.5) / 0.5) * a.H;
                col = paint;
                if (c.Band != null && z >= c.Band.Z0 && z <= c.Band.Z1) col = c.Band.Albedo;
                double dust = 0.10 + 0.55 * Math.Pow(Clamp01((0.70 - z) / 0.50), 1.5);
                dust *= 0.65 + 0.7 * Fbm(y * 3.0, z * 6.0, seed + 19);
                col = Rgb.Lerp(col, set.Dust, Clamp01(dust));
            }
            // the floor and the ceiling of the soot band
            double l = col.Luma;
            if (l < hold) col = AtLuma(col, hold);
            if (col.Luma > set.PaintHi) col = AtLuma(col, set.PaintHi);
            return col;
        }

        public static PaintMap Paint(BuiltCar car, CarSet set)
        {
            var m = new PaintMap { W = SIZE_W, H = SIZE_H, Rgb = new byte[SIZE_W * SIZE_H * 3], DarkestLuma = 1e9, PalestLuma = 0 };
            for (int r = 0; r < SIZE_H; r++)
            {
                double v = 1.0 - (r + 0.5) / SIZE_H;
                for (int cx = 0; cx < SIZE_W; cx++)
                {
                    double u = (cx + 0.5) / SIZE_W;
                    var c = At(car, set, u, v);
                    int i = (r * SIZE_W + cx) * 3;
                    byte br = (byte)Math.Round(ToSrgb(c.R) * 255), bg = (byte)Math.Round(ToSrgb(c.G) * 255), bb = (byte)Math.Round(ToSrgb(c.B) * 255);
                    m.Rgb[i] = br; m.Rgb[i + 1] = bg; m.Rgb[i + 2] = bb;
                    // read back as the engine will: 8-bit sRGB to linear
                    double l = new Rgb(FromSrgb(br / 255.0), FromSrgb(bg / 255.0), FromSrgb(bb / 255.0)).Luma;
                    if (l < m.DarkestLuma) m.DarkestLuma = l;
                    if (l > m.PalestLuma) m.PalestLuma = l;
                }
            }
            return m;
        }
    }

    /// <summary>An 8-bit RGB PNG, no filter, zlib by DeflateStream. Enough
    /// for the paint; Unity and Unreal both import it as sRGB.</summary>
    public static class Png
    {
        static readonly uint[] Crc = MakeCrc();

        static uint[] MakeCrc()
        {
            var t = new uint[256];
            for (uint n = 0; n < 256; n++)
            {
                uint c = n;
                for (int k = 0; k < 8; k++) c = (c & 1) != 0 ? 0xEDB88320u ^ (c >> 1) : c >> 1;
                t[n] = c;
            }
            return t;
        }

        static void Chunk(Stream s, string type, byte[] data)
        {
            var len = BitConverter.GetBytes(data.Length); if (BitConverter.IsLittleEndian) Array.Reverse(len);
            s.Write(len, 0, 4);
            var tb = System.Text.Encoding.ASCII.GetBytes(type);
            uint c = 0xFFFFFFFFu;
            foreach (byte b in tb) c = Crc[(c ^ b) & 0xFF] ^ (c >> 8);
            foreach (byte b in data) c = Crc[(c ^ b) & 0xFF] ^ (c >> 8);
            c ^= 0xFFFFFFFFu;
            s.Write(tb, 0, 4); s.Write(data, 0, data.Length);
            var cb = BitConverter.GetBytes(c); if (BitConverter.IsLittleEndian) Array.Reverse(cb);
            s.Write(cb, 0, 4);
        }

        public static byte[] Encode(int w, int h, byte[] rgb)
        {
            var raw = new byte[h * (w * 3 + 1)];
            for (int r = 0; r < h; r++) Buffer.BlockCopy(rgb, r * w * 3, raw, r * (w * 3 + 1) + 1, w * 3);
            byte[] deflated;
            using (var ms = new MemoryStream())
            {
                using (var ds = new DeflateStream(ms, CompressionLevel.Optimal, true)) ds.Write(raw, 0, raw.Length);
                deflated = ms.ToArray();
            }
            uint a = 1, b = 0;
            foreach (byte x in raw) { a = (a + x) % 65521; b = (b + a) % 65521; }
            var z = new byte[deflated.Length + 6];
            z[0] = 0x78; z[1] = 0x9C;
            Buffer.BlockCopy(deflated, 0, z, 2, deflated.Length);
            uint ad = (b << 16) | a;
            z[z.Length - 4] = (byte)(ad >> 24); z[z.Length - 3] = (byte)(ad >> 16); z[z.Length - 2] = (byte)(ad >> 8); z[z.Length - 1] = (byte)ad;
            using (var o = new MemoryStream())
            {
                o.Write(new byte[] { 137, 80, 78, 71, 13, 10, 26, 10 }, 0, 8);
                var ih = new byte[13];
                ih[0] = (byte)(w >> 24); ih[1] = (byte)(w >> 16); ih[2] = (byte)(w >> 8); ih[3] = (byte)w;
                ih[4] = (byte)(h >> 24); ih[5] = (byte)(h >> 16); ih[6] = (byte)(h >> 8); ih[7] = (byte)h;
                ih[8] = 8; ih[9] = 2; ih[10] = 0; ih[11] = 0; ih[12] = 0;
                Chunk(o, "IHDR", ih);
                Chunk(o, "IDAT", z);
                Chunk(o, "IEND", new byte[0]);
                return o.ToArray();
            }
        }
    }
}
