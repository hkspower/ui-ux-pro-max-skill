using System.Collections.Generic;
using UnityEngine;
using Ahmed.Data;

namespace Ahmed.World
{
    /// <summary>One thing worth walking to in a district.</summary>
    public enum SiteKind { Encounter, Gate, Exit }

    public class Site
    {
        public SiteKind Kind;
        /// <summary>Stable within a district, so WorldState can remember it.</summary>
        public int Id;
        public Vector3 Position;
        /// <summary>How close the player has to get before it wakes up.</summary>
        public float Radius;

        // Encounters
        public WaveRow Wave;
        public int Tier;

        // Gates
        public GateRow Gate;

        // Exits
        public int ToArea = -1;
        public Ability NeedsAbility = Ability.None;
        public string ExitLabel = "";
    }

    /// <summary>
    /// A district: one of the nine areas, laid out as a field rather than a
    /// corridor.
    ///
    /// The layout is *derived*, not authored. Every area already carries a
    /// stage -- its length, its waves and where along it each one triggers,
    /// its gates and what they want -- and all of that was tuned by hand in
    /// the browser build. Throwing it away and hand-placing new content would
    /// mean re-tuning the pacing of the whole game, so instead the one number
    /// that stops meaning anything in an open field, "distance along the
    /// stage", is reinterpreted as "how far around the district".
    ///
    /// Sites are placed on an outward spiral by that fraction, jittered by a
    /// hash of the area and the site index. So the order you meet things in,
    /// if you walk out from the middle, is the order the stage intended -- but
    /// you can approach any of them from any direction, ignore them, or come
    /// back later, which is the part that makes it a world rather than a
    /// queue.
    ///
    /// Deterministic on purpose: the same area lays out identically every run,
    /// so a player can learn it and a bug can be reproduced.
    /// </summary>
    public class District
    {
        public int AreaIndex;
        public string Name = "";
        public string DisplayName = "";
        public StageRow Stage;
        public Bounds2D Bounds;
        public float Extent;
        public readonly List<Site> Sites = new List<Site>();

        /// <summary>
        /// How much bigger a district is than the corridor it came from.
        ///
        /// The stages run 36 to 77 metres end to end. Multiplying by this and
        /// clamping gives fields of 120 to 260 metres a side -- a couple of
        /// minutes to cross at Ahmed's 3.4 m/s, which is the scale at which
        /// walking somewhere is a decision rather than a load screen. It is
        /// the one number here that is a judgement rather than a derivation,
        /// which is why it is named and alone.
        /// </summary>
        public const float LengthToExtent = 1.7f;
        public const float MinExtent = 60f;
        public const float MaxExtent = 130f;

        public static District Build(int areaIndex, WorldArea area, StageRow stage)
        {
            District d = new District();
            d.AreaIndex = areaIndex;
            d.Stage = stage;
            d.Name = area != null ? area.name : ("AREA" + areaIndex);
            d.DisplayName = stage != null ? stage.displayName : d.Name;

            float length = stage != null && stage.length > 0f ? stage.length : 40f;
            d.Extent = Mathf.Clamp(length * LengthToExtent, MinExtent, MaxExtent);
            d.Bounds = Bounds2D.Square(Vector3.zero, d.Extent);

            d.PlaceSites(stage);
            d.PlaceExits(area);
            return d;
        }

        private void PlaceSites(StageRow stage)
        {
            if (stage == null) { return; }
            float length = Mathf.Max(1f, stage.length);
            int id = 0;

            if (stage.waves != null)
            {
                for (int i = 0; i < stage.waves.Length; i++)
                {
                    WaveRow w = stage.waves[i];
                    float t = w.triggerDistance < 0f ? 0f : Mathf.Clamp01(w.triggerDistance / length);
                    Site s = new Site();
                    s.Kind = SiteKind.Encounter;
                    s.Id = id++;
                    s.Position = Spiral(t, i * 2 + 1);
                    s.Radius = 16f;
                    s.Wave = w;
                    s.Tier = w.tierOverride >= 0 ? w.tierOverride : stage.tier;
                    Sites.Add(s);
                }
            }
            if (stage.gates != null)
            {
                for (int i = 0; i < stage.gates.Length; i++)
                {
                    GateRow g = stage.gates[i];
                    float t = Mathf.Clamp01(g.distance / length);
                    Site s = new Site();
                    s.Kind = SiteKind.Gate;
                    s.Id = id++;
                    s.Position = Spiral(t, i * 2 + 2);
                    s.Radius = 3.5f;
                    s.Gate = g;
                    Sites.Add(s);
                }
            }
        }

        /// <summary>
        /// Exits sit on the district's edges: west on -X, east on +X, and the
        /// door -- which the world graph uses for the one link that is not a
        /// street, the Arena -- on +Z.
        /// </summary>
        private void PlaceExits(WorldArea area)
        {
            if (area == null) { return; }
            int id = 1000;
            AddExit(area.west, new Vector3(-Extent + 2f, 0f, 0f), "WEST", ref id);
            AddExit(area.east, new Vector3(Extent - 2f, 0f, 0f), "EAST", ref id);
            AddExit(area.door, new Vector3(0f, 0f, Extent - 2f), "DOOR", ref id);
        }

        private void AddExit(WorldLink link, Vector3 where, string label, ref int id)
        {
            if (link == null || link.to < 0) { return; }
            Site s = new Site();
            s.Kind = SiteKind.Exit;
            s.Id = id++;
            s.Position = where;
            s.Radius = 6f;
            s.ToArea = link.to;
            s.NeedsAbility = link.RequiredAbility;
            s.ExitLabel = label;
            Sites.Add(s);
        }

        /// <summary>
        /// Where a fraction along the old stage lands in the open field.
        ///
        /// An outward spiral of a turn and a third: far enough round that
        /// consecutive sites are not in a line, not so far that walking the
        /// whole stage means orbiting the district three times. The jitter is
        /// a hash rather than a random number so the world is the same every
        /// run -- a player can learn a district, and a bug in one is
        /// reproducible.
        /// </summary>
        private Vector3 Spiral(float t, int salt)
        {
            const float turns = 1.35f;
            float phase = Hash01(AreaIndex * 977 + 13) * Mathf.PI * 2f;
            float angle = phase + t * turns * Mathf.PI * 2f;
            float radius = Extent * (0.18f + 0.68f * t);

            float jitterA = (Hash01(AreaIndex * 131 + salt * 17) - 0.5f) * 0.55f;
            float jitterR = (Hash01(AreaIndex * 419 + salt * 53) - 0.5f) * 0.22f * Extent;

            angle += jitterA;
            radius = Mathf.Clamp(radius + jitterR, Extent * 0.10f, Extent * 0.92f);
            return new Vector3(Mathf.Cos(angle) * radius, 0f, Mathf.Sin(angle) * radius);
        }

        /// <summary>A cheap integer hash in 0..1. Deterministic everywhere,
        /// unlike Random, which depends on when it was last seeded.</summary>
        private static float Hash01(int n)
        {
            uint x = (uint)n;
            x ^= x >> 16; x *= 2246822519u;
            x ^= x >> 13; x *= 3266489917u;
            x ^= x >> 16;
            return (x & 0xFFFFFF) / 16777215f;
        }

        public Site SiteById(int id)
        {
            for (int i = 0; i < Sites.Count; i++)
            {
                if (Sites[i].Id == id) { return Sites[i]; }
            }
            return null;
        }
    }
}
