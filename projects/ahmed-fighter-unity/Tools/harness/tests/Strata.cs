using System;
using System.Collections.Generic;
using UnityEngine;
using Ahmed.Data;
using Ahmed.World;
using Ahmed.Game;

/* The three floors of every district, and ZAYOS. Everything here runs on the
   exported tables (TestData is generated from them), so a change to
   strata.js that breaks the world is caught by `Tools/harness/run.sh`. */
public static class StrataTest
{
    static int fails = 0;
    static void Check(bool ok, string w) { if (!ok) { fails++; Console.WriteLine("  FAIL " + w); } }

    public static int Main()
    {
        Console.WriteLine("FLOORS");
        Console.WriteLine("  area                  floors   street  under   up    shafts   ground m^2");
        float streetGround = 0f, allGround = 0f;
        int zayosSites = 0, zayosArea = -1, zayosLevel = 0; Site zayos = null; District zayosDistrict = null;
        for (int i = 0; i < TestData.Areas.Length; i++)
        {
            List<StratumRow> strata = TestData.StrataOf(i);
            District d = District.Build(i, TestData.Areas[i], TestData.Stages[i], strata);
            District street = District.Build(i, TestData.Areas[i], TestData.Stages[i]);

            Check(d.Floors.Count == 3, "area " + i + " has three floors (" + d.Floors.Count + ")");
            Check(d.Floors.ContainsKey(-1) && d.Floors[-1] < -5f, "area " + i + " has a cellar well below the street");
            Check(d.Floors.ContainsKey(1) && d.Floors[1] > 5f, "area " + i + " has roofs well above the street");

            // The street is untouched by the floors: same sites, same places.
            List<Site> s0 = d.SitesOn(0);
            Check(s0.Count == street.Sites.Count + 2, "area " + i + " street keeps every site and gains two stairheads (" + s0.Count + " vs " + street.Sites.Count + ")");
            for (int k = 0; k < street.Sites.Count; k++)
            {
                Site was = street.Sites[k], now = d.SiteById(was.Id);
                Check(now != null && (now.Position - was.Position).magnitude < 1e-5f && now.Level == 0,
                      "area " + i + " street site " + was.Id + " is where it was");
            }

            int under = 0, up = 0, shafts = 0;
            foreach (Site s in d.Sites)
            {
                Check(d.Bounds.Contains(s.Position), "area " + i + " site " + s.Id + " inside the bounds");
                Check(Math.Abs(s.Position.y - d.Floors[s.Level]) < 1e-5f, "area " + i + " site " + s.Id + " stands on its own floor");
                if (s.Kind == SiteKind.Shaft) shafts++;
                else if (s.Level < 0) under++;
                else if (s.Level > 0) up++;
                if (s.Kind == SiteKind.Encounter && s.Wave != null)
                    foreach (string f in s.Wave.fighters)
                    {
                        Check(TestData.Fighter(f) != null, "area " + i + " site " + s.Id + " spawns a fighter the roster has (" + f + ")");
                        if (f == "Zayos") { zayosSites++; zayosArea = i; zayosLevel = s.Level; zayos = s; zayosDistrict = d; }
                    }
            }
            foreach (StratumRow r in strata)
            {
                int enc = 0, gate = 0;
                foreach (Site s in d.SitesOn(r.offset)) { if (s.Kind == SiteKind.Encounter) enc++; if (s.Kind == SiteKind.Gate) gate++; }
                Check(enc == r.waves.Length, "area " + i + " " + r.level + " kept every wave");
                Check(gate == r.gates.Length, "area " + i + " " + r.level + " kept every gate");
                Check(enc >= 1, "area " + i + " " + r.level + " has something in it");
                foreach (Site s in d.SitesOn(r.offset))
                    Check(s.Kind != SiteKind.Exit && s.Kind != SiteKind.Hub, "area " + i + " " + r.level + " has no exit and no hub: the floors are inside the wheel");
            }

            // Shafts come in pairs: one end on the street, one on the floor,
            // same x and z, and the way back is never sealed.
            Check(shafts == 4, "area " + i + " has two stairs with two ends each (" + shafts + ")");
            foreach (Site s in d.Sites)
            {
                if (s.Kind != SiteKind.Shaft || s.Level != 0) continue;
                Site far = null;
                foreach (Site t in d.Sites) if (t.Kind == SiteKind.Shaft && t.Level == s.ToLevel && t.ToLevel == 0) far = t;
                Check(far != null, "area " + i + " shaft to level " + s.ToLevel + " has a far end");
                if (far == null) continue;
                Check(Math.Abs(far.Position.x - s.Position.x) < 1e-5f && Math.Abs(far.Position.z - s.Position.z) < 1e-5f,
                      "area " + i + " shaft ends share x and z");
                Check(far.NeedsAbility == Ability.None, "area " + i + " the way back up/down wants nothing");
                // Landing at the far end must not drop him into a fight.
                foreach (Site e in d.SitesOn(far.Level))
                {
                    if (e.Kind != SiteKind.Encounter) continue;
                    Vector3 dd = e.Position - far.Position; dd.y = 0f;
                    Check(dd.magnitude > e.Radius + far.Radius + 1.5f,
                          "area " + i + " level " + far.Level + ": the stair lands clear of encounter " + e.Id + " (" + dd.magnitude.ToString("0.0") + " m)");
                }
            }

            // Floors are separate fields: a cellar fight directly under a
            // street fight is allowed, so the runtime must never measure
            // across floors. LevelAt is what it relies on.
            Check(d.LevelAt(0f) == 0 && d.LevelAt(d.Floors[-1] + 0.3f) == -1 && d.LevelAt(d.Floors[1] - 0.3f) == 1, "area " + i + " LevelAt picks the nearest floor");

            // Determinism across floors.
            District again = District.Build(i, TestData.Areas[i], TestData.Stages[i], strata);
            bool same = again.Sites.Count == d.Sites.Count;
            for (int k = 0; same && k < d.Sites.Count; k++) same = (again.Sites[k].Position - d.Sites[k].Position).magnitude < 1e-6f && again.Sites[k].Id == d.Sites[k].Id;
            Check(same, "area " + i + " lays out identically every build, floors included");

            // The cellar is not the street traced onto a lower slab.
            int coincident = 0;
            foreach (Site a in d.SitesOn(0)) foreach (Site b in d.SitesOn(-1))
            {
                if (a.Kind != SiteKind.Encounter || b.Kind != SiteKind.Encounter) continue;
                Vector3 dd = a.Position - b.Position; dd.y = 0f;
                if (dd.magnitude < 2f) coincident++;
            }
            Check(coincident == 0, "area " + i + " cellar fights are not directly under the street's");

            float side = d.Extent * 2f;
            streetGround += side * side; allGround += side * side * d.Floors.Count;
            Console.WriteLine("  " + d.Name.PadRight(20) + d.Floors.Count.ToString().PadLeft(6) + (s0.Count - 2).ToString().PadLeft(9)
                + under.ToString().PadLeft(7) + up.ToString().PadLeft(6) + shafts.ToString().PadLeft(8) + (side * side * d.Floors.Count / 1000f).ToString("0.0").PadLeft(11) + "k");
        }
        Console.WriteLine("  ground you can stand on: " + (streetGround / 1000f).ToString("0.0") + " thousand m^2 on the street, "
            + (allGround / 1000f).ToString("0.0") + " thousand m^2 on all three floors");
        Check(allGround > streetGround * 2.9f, "three floors is three times the ground");

        // ------------------------------------------------------------- ZAYOS
        Console.WriteLine("\nZAYOS");
        FighterRow z = TestData.Fighter("Zayos");
        Check(z != null, "ZAYOS is in the roster");
        if (z != null)
        {
            Check(z.boss, "he is a boss");
            Check(z.scale > 1.4f, "and a big body (" + z.scale.ToString("0.00") + " of a man)");
            bool kicks = false; foreach (string mv in z.moves) if (mv == "Kick" || mv == "Knee") kicks = true;
            Check(!kicks, "a boxer: he only punches");
        }
        Check(zayosSites == 1, "exactly one fight in the world has him in it (" + zayosSites + ")");
        Check(zayosArea == 1 && zayosLevel == -1, "and it is in the cellar under the striking house (area " + zayosArea + ", level " + zayosLevel + ")");
        if (zayos != null)
        {
            // He is the last thing in the cellar, not the first.
            float r = new Vector3(zayos.Position.x, 0f, zayos.Position.z).magnitude;
            foreach (Site s in zayosDistrict.SitesOn(-1))
            {
                if (s.Kind != SiteKind.Encounter || s == zayos) continue;
                Check(new Vector3(s.Position.x, 0f, s.Position.z).magnitude < r, "the cellar's other fights come before him");
            }
            // Before AL-SAQR: area 1 is reachable with no talent, and the cellar stair wants nothing.
            Site stair = null;
            foreach (Site s in zayosDistrict.Sites) if (s.Kind == SiteKind.Shaft && s.Level == 0 && s.ToLevel == -1) stair = s;
            Check(stair != null && stair.NeedsAbility == Ability.None, "the stairs down to him want no talent");
            WorldState.Reset();
            Check(WorldState.CanUse(Resolved(TestData.Areas[0].east)) && TestData.Areas[0].east.to == 1, "the striking house is one open street from the souq");
            Check(!WorldState.CanUse(Resolved(TestData.Areas[3].east)), "while the crescent, where AL-SAQR is, still wants DASH LEAP");
        }
        // The roofs want VAULT; the cellars do not. Which is the whole pacing of the floors.
        int upSealed = 0, underSealed = 0, upCount = 0, underCount = 0;
        for (int i = 0; i < TestData.Areas.Length; i++)
        {
            District d = District.Build(i, TestData.Areas[i], TestData.Stages[i], TestData.StrataOf(i));
            foreach (Site s in d.Sites)
            {
                if (s.Kind != SiteKind.Shaft || s.Level != 0) continue;
                if (s.ToLevel > 0) { upCount++; if (s.NeedsAbility == Ability.Vault) upSealed++; }
                else { underCount++; if (s.NeedsAbility != Ability.None) underSealed++; }
            }
        }
        Check(upCount == 9 && upSealed == 9, "every ladder up wants VAULT (" + upSealed + "/" + upCount + ")");
        Check(underCount == 9 && underSealed == 0, "every stair down is open (" + (underCount - underSealed) + "/" + underCount + ")");

        // ------------------------------------------------------------- MUSIC
        Console.WriteLine("\nMUSIC");
        Check(MusicDirector.CueForLevel(-1) == "Music_Under" && MusicDirector.CueForLevel(0) == "Music_Stage" && MusicDirector.CueForLevel(1) == "Music_Up", "one cue per floor");
        GameObject go = new GameObject("music");
        MusicDirector md = go.AddComponent<MusicDirector>();
        Scene.Step();
        md.Play("Music_Stage");
        Check(md.Playing == "", "with no clips loadable (no Resources here) the director stays quiet rather than failing");
        md.Stop();
        Check(md.Playing == "", "and stops cleanly");

        Console.WriteLine(fails == 0 ? "\nall strata checks passed" : "\n" + fails + " FAILURES");
        return fails == 0 ? 0 : 1;
    }

    static WorldLink Resolved(WorldLink l) { l.Resolve(); return l; }
}
