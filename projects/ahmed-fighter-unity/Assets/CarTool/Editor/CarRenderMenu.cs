// SAUD -- the street cars, rendered by Unity.
//
// Asked 2026-10-01 (Riyadh): "render cars with unity".
//
//   SAUD > Render Street Cars  builds every car from cars.json exactly as
//                              SAUD > Build Street Cars does, refuses if any
//                              fails a check, stands each on a dark ground
//                              under a cold moon and a fire's warm light, and
//                              renders it from the front three-quarter and the
//                              rear three-quarter. The sheet (four cars, two
//                              views each, 1600 x 1800) is written to
//                              ../saud-fighter-ue5/Docs/renders/street-cars-unity.png.
//                              Nothing is written anywhere else; the scene it
//                              renders in is a new, unsaved one.
//
// Batch (needs a graphics device, so no -nographics):
//   Unity -batchmode -quit -projectPath <ahmed-fighter-unity> -executeMethod Saud.CarTool.CarRenderMenu.RenderFromCommandLine
//
// Built-in render pipeline, Standard shader. The picture is Unity's plain
// lit render, not the Unreal game's anime look (that is a post-process of
// the Unreal build, Tools/look/anime_look.py).
// NEVER COMPILED IN UNITY: type-checked against a stub of the Unity API only.
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace Saud.CarTool
{
    public static class CarRenderMenu
    {
        const int TILE_W = 800, TILE_H = 450;
        // camera spots in Unity's frame (x right, y up, z the car's forward), metres
        static readonly Vector3[] Views = { new Vector3(5.4f, 2.1f, 5.2f), new Vector3(-4.4f, 2.4f, -5.2f) };
        static readonly Vector3 LookAt = new Vector3(0f, 0.8f, 0f);

        static string OutPath => Path.Combine(CarToolMenu.UnrealRoot, "Docs", "renders", "street-cars-unity.png");

        [MenuItem("SAUD/Render Street Cars")]
        public static void RenderMenu()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            bool ok = Render(out string msg);
            if (ok) Debug.Log(msg); else Debug.LogError("SAUD street cars: " + msg);
            EditorUtility.DisplayDialog("SAUD street cars", msg, "OK");
        }

        public static void RenderFromCommandLine()
        {
            bool ok = Render(out string msg);
            if (ok) Debug.Log(msg); else Debug.LogError("SAUD street cars: " + msg);
            EditorApplication.Exit(ok ? 0 : 1);
        }

        static Color Lin(float r, float g, float b) =>
            new Color(Mathf.LinearToGammaSpace(r), Mathf.LinearToGammaSpace(g), Mathf.LinearToGammaSpace(b), 1f);

        static bool Render(out string msg)
        {
            if (!File.Exists(CarToolMenu.SpecPath)) { msg = "cars.json is not there: " + CarToolMenu.SpecPath; return false; }
            var set = CarSet.Parse(File.ReadAllText(CarToolMenu.SpecPath));

            // the same cars the build writes, held to the same checks
            var cars = new List<BuiltCar>();
            var paints = new List<PaintMap>();
            var faults = new List<Fault>();
            foreach (var c in set.Cars)
            {
                var car = CarBuilder.Build(c, set);
                var paint = CarPaint.Paint(car, set);
                faults.AddRange(CarChecks.Run(car, set, paint));
                cars.Add(car); paints.Add(paint);
            }
            if (faults.Count > 0) { msg = "the cars fail their checks, nothing rendered:\n" + string.Join("\n", faults); return false; }

            // a new, unsaved stage: ground, a cold moon, a fire's warm light, a camera
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            RenderSettings.skybox = null;
            RenderSettings.fog = false;
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = Lin(0.10f, 0.11f, 0.13f);

            var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.transform.localScale = new Vector3(4f, 1f, 4f);
            var gm = new Material(Shader.Find("Standard"));
            gm.SetColor("_Color", Lin(0.09f, 0.09f, 0.095f));
            gm.SetFloat("_Glossiness", 0.1f);
            ground.GetComponent<MeshRenderer>().sharedMaterial = gm;

            var moon = new GameObject("Moon").AddComponent<Light>();
            moon.type = LightType.Directional;
            moon.color = new Color(0.80f, 0.86f, 1.0f);
            moon.intensity = 1.1f;
            moon.shadows = LightShadows.Soft;
            moon.transform.rotation = Quaternion.Euler(50f, 225f, 0f);

            var fire = new GameObject("Fire").AddComponent<Light>();
            fire.type = LightType.Point;
            fire.color = new Color(1.0f, 0.55f, 0.25f);
            fire.intensity = 2.0f;
            fire.range = 12f;
            fire.transform.position = new Vector3(-3.5f, 1.5f, 3.0f);

            var cam = new GameObject("Camera").AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = Lin(0.10f, 0.11f, 0.13f);
            cam.fieldOfView = 23f;               // a 50 mm lens on a 36 mm frame, 16:9
            cam.nearClipPlane = 0.1f; cam.farClipPlane = 100f;
            cam.allowMSAA = true;

            var rt = new RenderTexture(TILE_W, TILE_H, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 8 };
            var tile = new Texture2D(TILE_W, TILE_H, TextureFormat.RGB24, false);
            var sheet = new Texture2D(TILE_W * Views.Length, TILE_H * cars.Count, TextureFormat.RGB24, false);
            cam.targetTexture = rt;
            try
            {
                for (int i = 0; i < cars.Count; i++)
                {
                    var car = cars[i];
                    var tex = new Texture2D(2, 2, TextureFormat.RGB24, true);
                    tex.LoadImage(Png.Encode(paints[i].W, paints[i].H, paints[i].Rgb));
                    tex.wrapMode = TextureWrapMode.Clamp;
                    var go = new GameObject("SM_Car_" + car.Spec.Name);
                    go.AddComponent<MeshFilter>().sharedMesh = CarToolMenu.ToMesh(car);
                    go.AddComponent<MeshRenderer>().sharedMaterials = CarToolMenu.MakeMaterials(car, set, tex);
                    for (int v = 0; v < Views.Length; v++)
                    {
                        cam.transform.position = Views[v];
                        cam.transform.LookAt(LookAt);
                        cam.Render();
                        RenderTexture.active = rt;
                        tile.ReadPixels(new Rect(0, 0, TILE_W, TILE_H), 0, 0);
                        tile.Apply();
                        RenderTexture.active = null;
                        // the sheet's first row is the first car: Unity's rows count up from the bottom
                        sheet.SetPixels(v * TILE_W, (cars.Count - 1 - i) * TILE_H, TILE_W, TILE_H, tile.GetPixels());
                    }
                    Object.DestroyImmediate(go);
                    Object.DestroyImmediate(tex);
                }
                sheet.Apply();
                Directory.CreateDirectory(Path.GetDirectoryName(OutPath));
                File.WriteAllBytes(OutPath, sheet.EncodeToPNG());
            }
            finally
            {
                cam.targetTexture = null;
                RenderTexture.active = null;
                rt.Release();
            }
            msg = "SAUD street cars rendered by Unity: " + OutPath;
            return true;
        }
    }
}
