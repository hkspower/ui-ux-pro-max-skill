// SAUD -- the street-car tool, in the Unity editor.
//
// Asked 2026-10-01 (Riyadh): "use unity for build cars instead blender".
// The cars are the Unreal game's (parked street cars, scenery only); this
// Unity project is only where they are built. Everything else in this
// project stays frozen.
//
//   SAUD > Build Street Cars   reads ../saud-fighter-ue5/Content/Models/Cars/cars.json,
//                               builds every car (Core/CarBuilder), refuses any that
//                               fails a check (Core/CarChecks), and writes
//                                 ../saud-fighter-ue5/Content/Models/Cars/SM_Car_<Name>.fbx
//                                 ../saud-fighter-ue5/Content/Textures/Cars/T_Car_<Name>_Paint.png
//                               with a mesh, materials and a prefab of each under
//                               Assets/CarTool/Built/ to look at here.
//   SAUD > Check Street Cars   builds and checks, writes nothing.
//   SAUD > Render Street Cars  builds, checks and renders them in Unity (CarRenderMenu.cs).
//
// Batch, no window:
//   Unity -batchmode -quit -projectPath <ahmed-fighter-unity> -executeMethod Saud.CarTool.CarToolMenu.BuildFromCommandLine
//
// Needs the FBX Exporter package (com.unity.formats.fbx, in Packages/manifest.json).
// NEVER COMPILED IN UNITY: written without an editor; the Core it calls is
// compiled and run under Mono by Tools/cars/run.sh, this file is not.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Formats.Fbx.Exporter;
using UnityEngine;
using UnityEngine.Rendering;

namespace Saud.CarTool
{
    public static class CarToolMenu
    {
        const string BUILT = "Assets/CarTool/Built";

        internal static string UnrealRoot => Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "saud-fighter-ue5"));
        internal static string SpecPath => Path.Combine(UnrealRoot, "Content", "Models", "Cars", "cars.json");

        [MenuItem("SAUD/Build Street Cars")]
        public static void BuildMenu() { Run(true, true); }

        [MenuItem("SAUD/Check Street Cars")]
        public static void CheckMenu() { Run(false, true); }

        public static void BuildFromCommandLine()
        {
            bool ok = Run(true, false);
            EditorApplication.Exit(ok ? 0 : 1);
        }

        static bool Run(bool write, bool dialogs)
        {
            if (!File.Exists(SpecPath))
            {
                Fail("cars.json is not there: " + SpecPath + "\nWrite it with: python3 Tools/levels/park_cars.py --json (in saud-fighter-ue5).", dialogs);
                return false;
            }
            CarSet set;
            try { set = CarSet.Parse(File.ReadAllText(SpecPath)); }
            catch (Exception e) { Fail("cars.json could not be read: " + e.Message, dialogs); return false; }

            // every car built and checked before any is written: all or none
            var built = new List<BuiltCar>();
            var paints = new List<PaintMap>();
            var faults = new List<Fault>();
            try
            {
                for (int i = 0; i < set.Cars.Count; i++)
                {
                    if (dialogs) EditorUtility.DisplayProgressBar("SAUD street cars", "Building " + set.Cars[i].Name, i / (float)set.Cars.Count);
                    var car = CarBuilder.Build(set.Cars[i], set);
                    var paint = CarPaint.Paint(car, set);
                    faults.AddRange(CarChecks.Run(car, set, paint));
                    built.Add(car); paints.Add(paint);
                }
            }
            finally { if (dialogs) EditorUtility.ClearProgressBar(); }
            if (faults.Count > 0)
            {
                Fail("The street cars fail their checks; nothing was written.\n" + string.Join("\n", faults.Select(f => f.ToString())), dialogs);
                return false;
            }
            if (!write)
            {
                Debug.Log("SAUD street cars: all " + built.Count + " pass their checks.");
                if (dialogs) EditorUtility.DisplayDialog("SAUD street cars", "All " + built.Count + " cars pass their checks.", "OK");
                return true;
            }

            string models = Path.Combine(UnrealRoot, "Content", "Models", "Cars");
            string textures = Path.Combine(UnrealRoot, "Content", "Textures", "Cars");
            Directory.CreateDirectory(models);
            Directory.CreateDirectory(textures);
            if (!AssetDatabase.IsValidFolder(BUILT)) AssetDatabase.CreateFolder("Assets/CarTool", "Built");

            var report = new List<string>();
            for (int i = 0; i < built.Count; i++)
            {
                var car = built[i]; string n = car.Spec.Name;
                if (dialogs) EditorUtility.DisplayProgressBar("SAUD street cars", "Exporting " + n, i / (float)built.Count);
                byte[] png = Png.Encode(paints[i].W, paints[i].H, paints[i].Rgb);
                File.WriteAllBytes(Path.Combine(textures, "T_Car_" + n + "_Paint.png"), png);

                // the paint, here, for the materials
                string texAsset = BUILT + "/T_Car_" + n + "_Paint.png";
                File.WriteAllBytes(Path.GetFullPath(texAsset), png);
                AssetDatabase.ImportAsset(texAsset, ImportAssetOptions.ForceUpdate);
                var ti = (TextureImporter)AssetImporter.GetAtPath(texAsset);
                ti.sRGBTexture = true; ti.wrapMode = TextureWrapMode.Clamp; ti.mipmapEnabled = true;
                ti.SaveAndReimport();
                var tex = AssetDatabase.LoadAssetAtPath<Texture2D>(texAsset);

                var mesh = ToMesh(car);
                string meshAsset = BUILT + "/SM_Car_" + n + ".asset";
                AssetDatabase.DeleteAsset(meshAsset);
                AssetDatabase.CreateAsset(mesh, meshAsset);

                // one material per slot, named M_Car_<Name>_<Slot>: Unreal's
                // import (park_cars.build_in_editor) finds each slot by that name
                var mats = MakeMaterials(car, set, tex);
                foreach (var m in mats)
                {
                    string matAsset = BUILT + "/" + m.name + ".mat";
                    AssetDatabase.DeleteAsset(matAsset);
                    AssetDatabase.CreateAsset(m, matAsset);
                }

                var go = new GameObject("SM_Car_" + n);
                try
                {
                    go.AddComponent<MeshFilter>().sharedMesh = mesh;
                    go.AddComponent<MeshRenderer>().sharedMaterials = mats;
                    PrefabUtility.SaveAsPrefabAsset(go, BUILT + "/SM_Car_" + n + ".prefab");
                    string fbx = Path.Combine(models, "SM_Car_" + n + ".fbx");
                    string got = ModelExporter.ExportObject(fbx, go);
                    if (string.IsNullOrEmpty(got) || !File.Exists(fbx))
                    {
                        Fail("The FBX Exporter wrote nothing for " + n + " (" + fbx + ").", dialogs);
                        return false;
                    }
                }
                finally { UnityEngine.Object.DestroyImmediate(go); }
                report.Add(string.Format("{0}: {1} triangles, {2} vertices, {3} materials", n, car.Mesh.TriCount, car.Mesh.Pos.Count, mats.Length));
            }
            if (dialogs) EditorUtility.ClearProgressBar();
            AssetDatabase.SaveAssets();
            string msg = "SAUD street cars written to " + models + ":\n" + string.Join("\n", report);
            Debug.Log(msg);
            if (dialogs) EditorUtility.DisplayDialog("SAUD street cars", msg, "OK");
            return true;
        }

        /// <summary>A Standard material per slot, in the slot order of the mesh:
        /// the paint textured, every other slot its flat weathered colour.</summary>
        internal static Material[] MakeMaterials(BuiltCar car, CarSet set, Texture2D tex)
        {
            var mats = new Material[car.Mesh.Slots.Count];
            for (int s = 0; s < mats.Length; s++)
            {
                string slot = car.Mesh.Slots[s];
                var spec = slot == "Paint" ? car.Spec.Paint : set.Slots[slot];
                var m = new Material(Shader.Find("Standard")) { name = "M_Car_" + car.Spec.Name + "_" + slot };
                m.SetColor("_Color", slot == "Paint" ? Color.white : Gamma(spec.Albedo));
                m.SetFloat("_Glossiness", (float)(1.0 - spec.Rough));
                if (slot == "Paint") m.SetTexture("_MainTex", tex);
                mats[s] = m;
            }
            return mats;
        }

        /// <summary>The core's right-handed, z-up metres to Unity's left-handed,
        /// y-up metres: (x forward, y left, z up) -> (-y, z, x), the same car
        /// in the same place. Seen from outside, a face the core winds
        /// counter-clockwise still looks counter-clockwise on the screen, and
        /// Unity draws clockwise faces: every triangle is reversed.</summary>
        internal static Mesh ToMesh(BuiltCar car)
        {
            var d = car.Mesh;
            var mesh = new Mesh { name = "SM_Car_" + car.Spec.Name };
            if (d.Pos.Count > 65535) mesh.indexFormat = IndexFormat.UInt32;
            mesh.SetVertices(d.Pos.Select(p => new Vector3((float)-p.Y, (float)p.Z, (float)p.X)).ToList());
            mesh.SetNormals(d.Nrm.Select(p => new Vector3((float)-p.Y, (float)p.Z, (float)p.X)).ToList());
            mesh.SetUVs(0, d.Uv.Select(uv => new Vector2((float)uv[0], (float)uv[1])).ToList());
            mesh.subMeshCount = d.Slots.Count;
            for (int s = 0; s < d.Slots.Count; s++)
            {
                var t = new List<int>(d.Tris[d.Slots[s]]);
                for (int i = 0; i < t.Count; i += 3) { int k = t[i + 1]; t[i + 1] = t[i + 2]; t[i + 2] = k; }
                mesh.SetTriangles(t, s);
            }
            mesh.RecalculateBounds();
            mesh.RecalculateTangents();
            return mesh;
        }

        /// <summary>A linear albedo as the gamma-space Color a Unity material takes.</summary>
        static Color Gamma(Rgb c) => new Color(Mathf.LinearToGammaSpace((float)c.R), Mathf.LinearToGammaSpace((float)c.G),
                                               Mathf.LinearToGammaSpace((float)c.B), 1f);

        static void Fail(string msg, bool dialogs)
        {
            if (dialogs) EditorUtility.ClearProgressBar();
            Debug.LogError("SAUD street cars: " + msg);
            if (dialogs) EditorUtility.DisplayDialog("SAUD street cars", msg, "OK");
        }
    }
}
