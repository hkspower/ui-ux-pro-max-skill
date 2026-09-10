using System;
using System.Collections.Generic;
using UnityEngine;
using Ahmed.Data;
using Ahmed.Game;
using Ahmed.World;

/// <summary>
/// The place a district is, and the streaming that keeps it in the scene.
///
/// Everything here is executed rather than asserted: the districts are built
/// from the real exported tables, the structures are laid out for every theme
/// and every floor, and the properties that make a district playable — you
/// can reach every fight, the street is not walled off, nothing stands
/// outside the world — are checked against all nine.
/// </summary>
public static class Program
{
    static int fails = 0;
    static void Check(bool ok, string what)
    {
        if (!ok) { fails++; Console.WriteLine("  FAIL  " + what); }
    }

    public static int Main()
    {
        Places();
        Reachable();
        Deterministic();
        Floors();
        Streaming();
        Boom();
        Console.WriteLine(fails == 0 ? "\nall checks passed" : "\n" + fails + " FAILURES");
        return fails == 0 ? 0 : 1;
    }

    static District Build(int i)
    {
        return District.Build(i, TestData.Areas[i], TestData.Stages[i], TestData.StrataOf(i));
    }

    // ------------------------------------------------------------------ places

    static void Places()
    {
        Console.WriteLine("PLACES  (the street floor of each district)");
        Console.WriteLine("  area                theme        street  solid   tallest  per 1000 m2");
        for (int i = 0; i < TestData.Stages.Length && i < TestData.Areas.Length; i++)
        {
            District d = Build(i);
            List<Placement> made = Landmarks.For(d, 0);
            List<Vector3> path = Landmarks.Path(d, 0);
            List<Site> sites = d.SitesOn(0);

            int street = 0, solid = 0;
            float tallest = 0f;
            int outside = 0, onStreet = 0, onSite = 0;
            Bounds2D bounds = d.Bounds;
            for (int k = 0; k < made.Count; k++)
            {
                Placement p = made[k];
                if (!p.Solid) { street++; continue; }
                solid++;
                tallest = Mathf.Max(tallest, p.Size.y);

                float half = Mathf.Max(p.Size.x, p.Size.z) * 0.5f;
                Vector3 flat = new Vector3(p.Position.x, 0f, p.Position.z);
                if (!bounds.Contains(flat)) { outside++; }
                // The rim is the edge and is meant to stand on the street's
                // last metre; everything else keeps off the way through.
                if (p.Kind != Landmarks.VocabularyFor(TestData.Stages[i].theme, 0).Rim
                    && Landmarks.DistanceToPath(path, flat) < Landmarks.StreetHalfWidth + half)
                {
                    onStreet++;
                }
                for (int s = 0; s < sites.Count; s++)
                {
                    Vector3 delta = new Vector3(sites[s].Position.x - flat.x, 0f,
                                                sites[s].Position.z - flat.z);
                    if (delta.magnitude < sites[s].Radius + half) { onSite++; break; }
                }
            }

            float area = d.Extent * 2f * d.Extent * 2f;
            Console.WriteLine(string.Format(
                "  {0,-18} {1,-12} {2,6} {3,6} {4,8:0.0} m {5,8:0.0}",
                d.DisplayName, TestData.Stages[i].theme, street, solid, tallest,
                solid * 1000f / area));

            Check(street > 0, d.Name + " has a street");
            Check(solid > 40, d.Name + " has something standing in it (" + solid + ")");
            Check(outside == 0, d.Name + ": " + outside + " structures outside the bounds");
            Check(onStreet == 0, d.Name + ": " + onStreet + " structures standing in the street");
            Check(onSite == 0, d.Name + ": " + onSite + " structures standing on a site");
        }

        // Two themes must not produce the same place, or the vocabulary is
        // decoration rather than data.
        District souq = Build(0), towers = Build(3);
        float hSouq = Tallest(Landmarks.For(souq, 0)), hTowers = Tallest(Landmarks.For(towers, 0));
        Check(hTowers > hSouq * 2f,
              "the salt towers stand taller than the souq (" + hTowers.ToString("0.0")
              + " m vs " + hSouq.ToString("0.0") + " m)");
    }

    static float Tallest(List<Placement> made)
    {
        float t = 0f;
        for (int i = 0; i < made.Count; i++)
        {
            if (made[i].Solid) { t = Mathf.Max(t, made[i].Size.y); }
        }
        return t;
    }

    // --------------------------------------------------------------- reachable

    /// <summary>
    /// Every fight, gate, stair and the hub has street to it, and no solid
    /// thing is standing in the doorway out of the district. An unreachable
    /// encounter is a run that cannot be finished, and it is exactly the bug
    /// a generated place is prone to.
    /// </summary>
    static void Reachable()
    {
        Console.WriteLine("\nREACHABLE");
        int checkedSites = 0, stranded = 0, blockedDoors = 0;
        for (int i = 0; i < TestData.Areas.Length; i++)
        {
            District d = Build(i);
            foreach (KeyValuePair<int, float> floor in d.Floors)
            {
                List<Placement> made = Landmarks.For(d, floor.Key);
                List<Site> sites = d.SitesOn(floor.Key);
                for (int s = 0; s < sites.Count; s++)
                {
                    Site site = sites[s];
                    if (site.Kind == SiteKind.Exit)
                    {
                        // A way out must have a gap in the rim: nothing solid
                        // within a stride of it.
                        for (int k = 0; k < made.Count; k++)
                        {
                            if (!made[k].Solid) { continue; }
                            Vector3 delta = new Vector3(made[k].Position.x - site.Position.x, 0f,
                                                        made[k].Position.z - site.Position.z);
                            float half = Mathf.Max(made[k].Size.x, made[k].Size.z) * 0.5f;
                            if (delta.magnitude < site.Radius + half) { blockedDoors++; break; }
                        }
                        continue;
                    }
                    checkedSites++;
                    float best = float.MaxValue;
                    for (int k = 0; k < made.Count; k++)
                    {
                        if (made[k].Solid) { continue; }        // paving only
                        Vector3 delta = new Vector3(made[k].Position.x - site.Position.x, 0f,
                                                    made[k].Position.z - site.Position.z);
                        best = Mathf.Min(best, delta.magnitude);
                    }
                    if (best > site.Radius + 6f) { stranded++; }
                }
            }
        }
        Console.WriteLine("  " + checkedSites + " sites across nine districts and their floors");
        Check(stranded == 0, stranded + " sites with no street to them");
        Check(blockedDoors == 0, blockedDoors + " doorways with something standing in them");
    }

    // ------------------------------------------------------------ determinism

    static void Deterministic()
    {
        Console.WriteLine("\nDETERMINISM");
        int drift = 0;
        for (int i = 0; i < TestData.Areas.Length; i++)
        {
            List<Placement> a = Landmarks.For(Build(i), 0);
            List<Placement> b = Landmarks.For(Build(i), 0);
            if (a.Count != b.Count) { drift++; continue; }
            for (int k = 0; k < a.Count; k++)
            {
                if (a[k].Kind != b[k].Kind
                    || (a[k].Position - b[k].Position).magnitude > 1e-5f
                    || (a[k].Size - b[k].Size).magnitude > 1e-5f
                    || Mathf.Abs(a[k].Yaw - b[k].Yaw) > 1e-4f) { drift++; break; }
            }
        }
        Check(drift == 0, "a district builds the same twice (" + drift + " differ)");
    }

    // ----------------------------------------------------------------- floors

    static void Floors()
    {
        Console.WriteLine("\nFLOORS  (the cellar and the roofs are their own places)");
        int sameAsStreet = 0, floorsSeen = 0;
        for (int i = 0; i < TestData.Areas.Length; i++)
        {
            District d = Build(i);
            List<Placement> street = Landmarks.For(d, 0);
            foreach (KeyValuePair<int, float> floor in d.Floors)
            {
                if (floor.Key == 0) { continue; }
                floorsSeen++;
                List<Placement> other = Landmarks.For(d, floor.Key);
                Check(other.Count > 0, d.Name + " floor " + floor.Key + " is built");

                // On its own height, and not a copy of the street.
                int wrongHeight = 0;
                for (int k = 0; k < other.Count; k++)
                {
                    if (other[k].Position.y < floor.Value - 1f) { wrongHeight++; }
                }
                Check(wrongHeight == 0, d.Name + " floor " + floor.Key + " stands on its own slab");
                if (other.Count == street.Count && other.Count > 0
                    && Mathf.Abs(other[0].Position.x - street[0].Position.x) < 1e-4f)
                {
                    sameAsStreet++;
                }
            }
        }
        Console.WriteLine("  " + floorsSeen + " floors under and over the nine streets");
        Check(sameAsStreet == 0, "no floor is the street traced at another height");
    }

    // -------------------------------------------------------------- streaming

    /// <summary>
    /// Walk the length of a district and watch what is in the scene. What
    /// matters: the resident set stays bounded however far he walks, every
    /// structure is filed in exactly one cell, and leaving takes all of it
    /// with him.
    /// </summary>
    static void Streaming()
    {
        Console.WriteLine("\nSTREAMING");
        District d = Build(0);
        Scenery scenery = new Scenery(d);
        Console.WriteLine("  " + d.DisplayName + ": " + scenery.Planned
            + " structures in " + scenery.CellCount + " cells across "
            + d.Floors.Count + " floors");
        Check(scenery.Planned > 200, "a district is a few hundred structures");
        Check(scenery.CellCount > 20, "and they are spread over the field");

        // Every structure is in exactly one cell: the counts must agree.
        int inCells = 0;
        List<long> everything = scenery.CellsWithin(Vector3.zero, 0, 10000f);
        foreach (KeyValuePair<int, float> floor in d.Floors)
        {
            List<long> cells = scenery.CellsWithin(Vector3.zero, floor.Key, 10000f);
            inCells += cells.Count;
        }
        Check(everything.Count > 0, "cells are found from the middle");
        Check(inCells >= scenery.CellCount,
              "every cell is reachable from a wide enough search (" + inCells
              + " vs " + scenery.CellCount + ")");

        int peak = 0, ticks = 0;
        float extent = d.Extent;
        for (float x = -extent; x <= extent; x += 4f)
        {
            Vector3 at = new Vector3(x, 0f, 0f);
            // Several ticks a step, because the build is budgeted.
            for (int t = 0; t < 6; t++) { scenery.Update(at, 0); ticks++; }
            peak = Mathf.Max(peak, scenery.Resident);
            Check(scenery.Resident <= scenery.Planned, "never more resident than planned");
        }
        Console.WriteLine("  walked " + (extent * 2f).ToString("0") + " m in " + ticks
            + " ticks; at most " + peak + " structures in the scene at once");
        Check(peak > 0, "structures come into the scene as he walks");
        Check(peak < scenery.Planned,
              "and the whole district is never resident at once (" + peak
              + " of " + scenery.Planned + ")");

        // A cell taken up does not go again on a step back: the release
        // radius is wider than the load radius, and that is the hysteresis.
        Check(Scenery.ReleaseRadius > Scenery.LoadRadius + Scenery.CellSize * 0.5f,
              "release radius clears the load radius by more than half a cell");

        scenery.Clear();
        Check(scenery.Resident == 0, "leaving a district takes all of it with him");
    }

    // ----------------------------------------------------------------- camera

    /// <summary>The boom's geometry, which decides whether the camera is
    /// behind him or inside a wall.</summary>
    static void Boom()
    {
        Console.WriteLine("\nCAMERA");
        Vector3 anchor = new Vector3(3f, 1.5f, -7f);

        // Level, looking north: the camera is straight behind, at the anchor's
        // own height.
        Vector3 p = FollowCamera.BoomPosition(anchor, 0f, 0f, 10f);
        Check(Mathf.Abs(p.z - (anchor.z - 10f)) < 1e-3f, "level boom sits behind by its length");
        Check(Mathf.Abs(p.y - anchor.y) < 1e-3f, "level boom is at the anchor's height");

        // Pitched down at the man: higher, and closer on the flat.
        p = FollowCamera.BoomPosition(anchor, 0f, 30f, 10f);
        Check(p.y > anchor.y + 4.9f, "a pitched boom rises");
        Check(Mathf.Abs(p.z - anchor.z) < 8.7f, "and comes in on the flat");

        // Its length is its length, whatever the angles.
        int wrong = 0;
        for (int yaw = 0; yaw < 360; yaw += 13)
        {
            for (int pitch = -4; pitch < 62; pitch += 7)
            {
                Vector3 q = FollowCamera.BoomPosition(anchor, yaw, pitch, 9.5f);
                if (Mathf.Abs((q - anchor).magnitude - 9.5f) > 1e-2f) { wrong++; }
            }
        }
        Check(wrong == 0, "the boom is its own length at every angle (" + wrong + " wrong)");

        Check(Mathf.Abs(FollowCamera.AllowedDistance(11f, -1f, 0.35f) - 11f) < 1e-4f,
              "nothing in the way and the boom reaches");
        Check(Mathf.Abs(FollowCamera.AllowedDistance(11f, 4f, 0.35f) - 3.65f) < 1e-4f,
              "a wall at 4 m stops it short of the wall");
        Check(FollowCamera.AllowedDistance(11f, 0.2f, 0.35f) == 0f,
              "a wall against his back puts the camera on him, not through it");
    }
}
