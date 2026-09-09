using System.Collections.Generic;
using UnityEngine;
using Ahmed.Data;

namespace Ahmed.World
{
    /// <summary>One thing worth walking to in a district.</summary>
    public enum SiteKind { Encounter, Gate, Exit, Hub, Shaft }

    public class Site
    {
        public SiteKind Kind;
        /// <summary>Stable within a district, so WorldState can remember it.</summary>
        public int Id;
        /// <summary>Which floor it is on: -1 under the street, 0 the street,
        /// +1 the roofs. Position.y is that floor's height.</summary>
        public int Level;
        public Vector3 Position;
        /// <summary>How close the player has to get before it wakes up.</summary>
        public float Radius;

        // Shafts: the stair or ladder to another floor
        public int ToLevel;
        public Ability NeedsAbility = Ability.None;

        // Encounters
        public WaveRow Wave;
        public int Tier;

        // Gates
        public GateRow Gate;

        // Exits
        public int ToArea = -1;
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
        /// <summary>The floors this district has, by level: -1, 0, +1. The
        /// street is always there; the others come from strata.json.</summary>
        public readonly Dictionary<int, float> Floors = new Dictionary<int, float>();
        /// <summary>The floor's own text, by level. The street's is the stage's.</summary>
        public readonly Dictionary<int, string> FloorNames = new Dictionary<int, string>();

        /// <summary>Site ids are partitioned by floor so WorldState's
        /// area:site key stays unique across all three of them.</summary>
        public const int UnderIdBase = 3000;
        public const int UpIdBase = 4000;
        public const int ShaftIdBase = 5000;

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
            return Build(areaIndex, area, stage, null);
        }

        /// <summary>
        /// A district with its floors. `strata` is the area's under and up
        /// rows from strata.json; null or empty builds the street alone,
        /// which is what the tests that predate the floors still do.
        /// </summary>
        public static District Build(int areaIndex, WorldArea area, StageRow stage,
                                     IList<StratumRow> strata)
        {
            District d = new District();
            d.AreaIndex = areaIndex;
            d.Stage = stage;
            d.Name = area != null ? area.name : ("AREA" + areaIndex);
            d.DisplayName = stage != null ? stage.displayName : d.Name;

            float length = stage != null && stage.length > 0f ? stage.length : 40f;
            d.Extent = Mathf.Clamp(length * LengthToExtent, MinExtent, MaxExtent);
            d.Bounds = Bounds2D.Square(Vector3.zero, d.Extent);

            d.Floors[0] = 0f;
            d.FloorNames[0] = d.DisplayName;
            d.PlaceSites(stage != null ? stage.waves : null, stage != null ? stage.gates : null,
                         length, stage != null ? stage.tier : 0, 0, 0f, 0);
            d.PlaceExits(area);
            d.PlaceHub(area);
            if (strata != null)
            {
                for (int i = 0; i < strata.Count; i++) { d.PlaceFloor(strata[i], length); }
            }
            return d;
        }

        /// <summary>
        /// Another floor of the same district: the same spiral, at a height,
        /// with its own phase so the cellar is not the street traced onto a
        /// lower slab. Its sites take ids from that floor's own block, and
        /// the shaft that joins it to the street is placed at both ends --
        /// one site on each floor, same x and z -- so the stair you went down
        /// is the stair you come back up.
        /// </summary>
        private void PlaceFloor(StratumRow row, float length)
        {
            if (row == null || row.offset == 0 || Floors.ContainsKey(row.offset)) { return; }
            int level = row.offset;
            int idBase = level < 0 ? UnderIdBase : UpIdBase;
            Floors[level] = row.height;
            FloorNames[level] = row.level;

            int tier = Stage != null ? Stage.tier : 0;
            PlaceSites(row.waves, row.gates, length, tier, idBase, row.height, level);

            float t = Mathf.Clamp01(row.shaftDistance / Mathf.Max(1f, length));
            Vector3 foot = ShaftFoot(t, level);

            Site down = new Site();
            down.Kind = SiteKind.Shaft;
            down.Id = ShaftIdBase + (level < 0 ? 0 : 10);
            down.Level = 0;
            down.Position = foot;
            down.Radius = 3f;
            down.ToLevel = level;
            down.NeedsAbility = row.ShaftAbility;
            Sites.Add(down);

            Site back = new Site();
            back.Kind = SiteKind.Shaft;
            back.Id = down.Id + 1;
            back.Level = level;
            back.Position = new Vector3(foot.x, row.height, foot.z);
            back.Radius = 3f;
            back.ToLevel = 0;
            back.NeedsAbility = Ability.None;   // the way back is never sealed
            Sites.Add(back);
        }

        /// <summary>
        /// Where the stair stands. It has to be clear of every fight on both
        /// of the floors it joins -- the test that found this had three
        /// cellars whose stair came down inside an ambush's wake radius, so
        /// taking the stairs started a fight. The spiral is tried at a run of
        /// salts, deterministically, and the first foot that is clear on both
        /// floors is the one; failing that, the clearest.
        /// </summary>
        private Vector3 ShaftFoot(float t, int level)
        {
            const float shaftRadius = 3f, landing = 4.5f, margin = 2f;
            Vector3 best = Vector3.zero; float bestClear = float.MinValue;
            for (int salt = 90; salt < 90 + 32; salt++)
            {
                Vector3 foot = Spiral(t, salt, 0);
                float clear = float.MaxValue;
                for (int i = 0; i < Sites.Count; i++)
                {
                    Site s = Sites[i];
                    if (s.Level != 0 && s.Level != level) { continue; }
                    if (s.Kind != SiteKind.Encounter && s.Kind != SiteKind.Hub && s.Kind != SiteKind.Shaft) { continue; }
                    Vector3 d = s.Position - foot; d.y = 0f;
                    clear = Mathf.Min(clear, d.magnitude - s.Radius - shaftRadius - landing);
                }
                if (clear > bestClear) { bestClear = clear; best = foot; }
                if (clear >= margin) { break; }
            }
            return best;
        }

        private void PlaceSites(WaveRow[] waves, GateRow[] gates, float length, int tier,
                                int idBase, float height, int level)
        {
            length = Mathf.Max(1f, length);
            int id = idBase;

            if (waves != null)
            {
                for (int i = 0; i < waves.Length; i++)
                {
                    WaveRow w = waves[i];
                    float t = w.triggerDistance < 0f ? 0f : Mathf.Clamp01(w.triggerDistance / length);
                    Site s = new Site();
                    s.Kind = SiteKind.Encounter;
                    s.Id = id++;
                    s.Level = level;
                    s.Position = Spiral(t, i * 2 + 1, level);
                    s.Position.y = height;
                    s.Radius = 16f;
                    s.Wave = w;
                    s.Tier = w.tierOverride >= 0 ? w.tierOverride : tier;
                    Sites.Add(s);
                }
            }
            if (gates != null)
            {
                for (int i = 0; i < gates.Length; i++)
                {
                    GateRow g = gates[i];
                    float t = Mathf.Clamp01(g.distance / length);
                    Site s = new Site();
                    s.Kind = SiteKind.Gate;
                    s.Id = id++;
                    s.Level = level;
                    s.Position = Spiral(t, i * 2 + 2, level);
                    s.Position.y = height;
                    s.Radius = 3.5f;
                    s.Gate = g;
                    Sites.Add(s);
                }
            }
        }

        /// <summary>Everything on one floor, in site order.</summary>
        public List<Site> SitesOn(int level)
        {
            List<Site> found = new List<Site>();
            for (int i = 0; i < Sites.Count; i++)
            {
                if (Sites[i].Level == level) { found.Add(Sites[i]); }
            }
            return found;
        }

        /// <summary>Which floor a height is on: the nearest one.</summary>
        public int LevelAt(float y)
        {
            int best = 0; float bestD = float.MaxValue;
            foreach (KeyValuePair<int, float> f in Floors)
            {
                float d = Mathf.Abs(f.Value - y);
                if (d < bestD) { bestD = d; best = f.Key; }
            }
            return best;
        }

        /// <summary>
        /// The one place in the world that is his.
        ///
        /// It goes at the centre of the starting district and nowhere else.
        /// The centre because that is where the spiral begins and where the
        /// player is put down, so the game opens standing in it; nowhere else
        /// because the canon is explicit that the map is the argument -- the
        /// ring is closed, the arena is the hub of it, and a second safe room
        /// somewhere out on the loop would be a second answer to a question
        /// the world only gets to answer once.
        ///
        /// It is derived, not authored, like everything else here: the centre
        /// of whichever area the world graph says the game starts in.
        /// </summary>
        private void PlaceHub(WorldArea area)
        {
            if (area == null || area.startArea != AreaIndex) { return; }
            Site s = new Site();
            s.Kind = SiteKind.Hub;
            s.Id = 2000;
            s.Position = Vector3.zero;
            s.Radius = 7f;
            Sites.Add(s);
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
        private Vector3 Spiral(float t, int salt, int level)
        {
            const float turns = 1.35f;
            // Each floor turns the spiral by its own phase, so the cellar's
            // fights are not directly under the street's.
            float phase = Hash01(AreaIndex * 977 + 13 + level * 389) * Mathf.PI * 2f;
            float angle = phase + t * turns * Mathf.PI * 2f;
            float radius = Extent * (0.18f + 0.68f * t);

            float jitterA = (Hash01(AreaIndex * 131 + salt * 17 + level * 71) - 0.5f) * 0.55f;
            float jitterR = (Hash01(AreaIndex * 419 + salt * 53 + level * 29) - 0.5f) * 0.22f * Extent;

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
