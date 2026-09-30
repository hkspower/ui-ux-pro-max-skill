// SAUD -- the street-car tool outside Unity: build every car in cars.json
// with the same engine-free core the Unity menu uses, run every check, and
// write each car as OBJ + MTL + its paint PNG for looking at. --bite breaks
// each check once and proves it is caught.
//   Tools/cars/run.sh [--out DIR] [--bite]
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Saud.CarTool;

static class CarRun
{
    static int Main(string[] args)
    {
        string spec = "../saud-fighter-ue5/Content/Models/Cars/cars.json", outDir = null;
        bool bite = false;
        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "--spec") spec = args[++i];
            else if (args[i] == "--out") outDir = args[++i];
            else if (args[i] == "--bite") bite = true;
        }
        var set = CarSet.Parse(File.ReadAllText(spec));
        Console.WriteLine("cars.json: {0} cars, ink floor {1}, hold {2}, paint at most {3}", set.Cars.Count, set.InkFloor, set.InkHold, set.PaintHi);
        int failed = 0;
        foreach (var c in set.Cars)
        {
            var t0 = DateTime.Now;
            var car = CarBuilder.Build(c, set);
            var paint = CarPaint.Paint(car, set);
            var faults = CarChecks.Run(car, set, paint);
            var m = car.Mesh;
            double minX = m.Pos.Min(q => q.X), maxX = m.Pos.Max(q => q.X), maxY = m.Pos.Max(q => Math.Abs(q.Y)), maxZ = m.Pos.Max(q => q.Z);
            Console.WriteLine("  {0,-7} {1,6} tris {2,6} verts  {3} parts  {4:F3} x {5:F3} x {6:F3} m  slots {7}  paint {8:F4}-{9:F4}  ({10:F1} s)",
                c.Name, m.TriCount, m.Pos.Count, car.Shells.Count, maxX - minX, 2 * maxY, maxZ,
                string.Join(",", m.Slots.Select(sl => sl + " " + m.Tris[sl].Count / 3)), paint.DarkestLuma, paint.PalestLuma,
                (DateTime.Now - t0).TotalSeconds);
            foreach (var f in faults) Console.WriteLine("    FAIL " + f);
            failed += faults.Count;
            if (outDir != null)
            {
                Directory.CreateDirectory(outDir);
                CarChecks.WriteObj(car, set, outDir);
                File.WriteAllBytes(Path.Combine(outDir, "T_Car_" + c.Name + "_Paint.png"), Png.Encode(paint.W, paint.H, paint.Rgb));
            }
        }
        if (failed > 0) { Console.WriteLine("CHECKS FAIL: {0}", failed); return 1; }
        Console.WriteLine("checks pass: {0} cars", set.Cars.Count);
        if (!bite) return 0;

        // each check broken once; the unbroken cars above passed first
        var cases = new[]
        {
            new object[] { Sabotage.Flip, "wound", "Sedan" }, new object[] { Sabotage.Hole, "closed", "Sedan" },
            new object[] { Sabotage.InsideOut, "outward", "Sedan" }, new object[] { Sabotage.TightArch, "arches", "SUV" },
            new object[] { Sabotage.NoGlass, "glass", "Pickup" }, new object[] { Sabotage.Lopsided, "symmetry", "Taxi" },
            new object[] { Sabotage.DarkSeam, "paint", "Sedan" }, new object[] { Sabotage.Hover, "ground", "SUV" },
            new object[] { Sabotage.Long, "size", "Pickup" }, new object[] { Sabotage.Dense, "budget", "SUV" },
            new object[] { Sabotage.BadUv, "uv", "Taxi" }, new object[] { Sabotage.NoTyre, "tyres", "Pickup" },
        };
        int caught = 0;
        foreach (var k in cases)
        {
            var sab = (Sabotage)k[0]; string rule = (string)k[1], name = (string)k[2];
            var c = set.Cars.First(x => x.Name == name);
            var car = CarBuilder.Build(c, set, sab);
            var faults = CarChecks.Run(car, set, CarPaint.Paint(car, set));
            bool ok = faults.Any(f => f.Rule == rule);
            caught += ok ? 1 : 0;
            Console.WriteLine("  {0,-10} {1,-6} {2}  ({3})", sab, name, ok ? "caught" : "NOT CAUGHT",
                faults.Count > 0 ? string.Join("; ", faults.Where(f => f.Rule == rule).Take(1).Concat(faults.Take(1)).Distinct()) : "passed");
        }
        Console.WriteLine("  {0} of {1} car-tool sabotages caught", caught, cases.Length);
        return caught == cases.Length ? 0 : 1;
    }
}
