using System.Collections.Generic;
using UnityEngine;
using Ahmed.Data;

namespace Ahmed.World
{
    /// <summary>What a placement is made of, until art replaces it.</summary>
    public enum Shape { Box, Post }

    /// <summary>
    /// One thing standing in a district: a stall, a tower, a rock, a length of
    /// street. Position is the centre of the volume, so a primitive can be put
    /// down at it with no further arithmetic, and Size is in metres.
    ///
    /// Kind is the name an artist keys a real mesh off. Nothing in the game
    /// reads it — it exists so that replacing "stall" with a stall is a
    /// lookup rather than a rewrite of this file.
    /// </summary>
    public struct Placement
    {
        public string Kind;
        public Shape Shape;
        public Vector3 Position;
        public Vector3 Size;
        public float Yaw;
        /// <summary>Whether a fighter has to walk around it. Streets are not.</summary>
        public bool Solid;
    }

    /// <summary>
    /// The district's own place, derived the way its layout is.
    ///
    /// A district was a grey square with markers on it. That is the shape of
    /// the world and not the world: you cannot get lost in it, you cannot take
    /// cover behind anything, and every one of the nine looks the same. This
    /// puts a place on top of the shape — a street, the buildings either side
    /// of it, and an edge — and derives all of it from what the district
    /// already knows, so nothing here has to be authored per area and nothing
    /// can drift from the data.
    ///
    /// Three rules hold it together:
    ///
    /// * **The street is the spiral.** <see cref="District.PathPoint"/> is the
    ///   curve the sites were placed along; the street is laid on it, with a
    ///   spur out to each site. So the main way through a district passes
    ///   everything the stage meant you to meet, in order, and a fight is
    ///   always just off it.
    /// * **Nothing stands where something happens.** A placement is dropped if
    ///   it lands inside a site's radius, on the street, or outside the
    ///   bounds. An encounter you cannot reach is a bug you only find by
    ///   walking into it.
    /// * **Deterministic.** Same hash as the layout, so a district looks the
    ///   same every run and a wrong-looking one can be reproduced.
    ///
    /// A floor has its own vocabulary: the street's is its theme's, the cellar
    /// is pillars and rubble whatever is above it, and the roofs are tanks and
    /// aerials. They are different places, not the same place at three
    /// heights.
    /// </summary>
    public static class Landmarks
    {
        /// <summary>Half the width of the way through. Wide enough for a fight
        /// to spill into it.</summary>
        public const float StreetHalfWidth = 3.2f;
        /// <summary>How far a building keeps off the street and off a site.</summary>
        public const float Clearance = 1.6f;
        /// <summary>How many points the spiral is sampled at. At 130 m extent
        /// that is a segment every metre or so.</summary>
        private const int PathSamples = 140;
        /// <summary>The longest a single length of paving gets.</summary>
        private const float PavingStep = 5f;

        /// <summary>
        /// What one floor of a district is built of, in no particular order.
        /// </summary>
        public static List<Placement> For(District d, int level)
        {
            List<Placement> made = new List<Placement>();
            if (d == null) { return made; }
            float height;
            if (!d.Floors.TryGetValue(level, out height)) { return made; }

            Vocabulary v = VocabularyFor(d.Stage != null ? d.Stage.theme : "", level);
            List<Vector3> path = Path(d, level);
            List<Site> sites = d.SitesOn(level);

            Street(d, path, sites, height, v, made);
            Blocks(d, path, sites, height, v, level, made);
            Rim(d, height, v, level, made);
            return made;
        }

        /// <summary>Every floor at once, which is what a district's scenery
        /// is. Keyed by level.</summary>
        public static Dictionary<int, List<Placement>> ForAll(District d)
        {
            Dictionary<int, List<Placement>> all = new Dictionary<int, List<Placement>>();
            if (d == null) { return all; }
            foreach (KeyValuePair<int, float> floor in d.Floors)
            {
                all[floor.Key] = For(d, floor.Key);
            }
            return all;
        }

        // ------------------------------------------------------------ street

        /// <summary>The spiral, sampled. The street runs along it.</summary>
        public static List<Vector3> Path(District d, int level)
        {
            List<Vector3> pts = new List<Vector3>(PathSamples);
            for (int i = 0; i < PathSamples; i++)
            {
                pts.Add(d.PathPoint(i / (float)(PathSamples - 1), level));
            }
            return pts;
        }

        private static void Street(District d, List<Vector3> path, List<Site> sites,
                                   float height, Vocabulary v, List<Placement> into)
        {
            for (int i = 1; i < path.Count; i++)
            {
                Paving(path[i - 1], path[i], StreetHalfWidth * 2f, height, v.Paving, into);
            }
            // A spur from the way to each thing worth walking to, so a fight
            // is off the street rather than out in a field somewhere.
            for (int i = 0; i < sites.Count; i++)
            {
                Site s = sites[i];
                if (s.Kind == SiteKind.Exit) { continue; }   // the rim's gap is its road
                Vector3 flat = new Vector3(s.Position.x, 0f, s.Position.z);
                Vector3 near = Nearest(path, flat);
                Vector3 delta = flat - near; delta.y = 0f;
                if (delta.magnitude < 1f) { continue; }
                Paving(near, flat, StreetHalfWidth * 1.3f, height, v.Paving, into);
            }
        }

        /// <summary>
        /// Paving from a to b, in lengths of at most <see cref="PavingStep"/>.
        ///
        /// It is cut up rather than laid as one long slab because a spur out
        /// to a fight can be thirty metres, and a thirty-metre slab is one
        /// object that streams as a unit, sits in one cell, and lies flat
        /// across ground that is not. Short lengths follow the district.
        /// </summary>
        private static void Paving(Vector3 a, Vector3 b, float width, float height,
                                   string kind, List<Placement> into)
        {
            Vector3 delta = b - a; delta.y = 0f;
            float length = delta.magnitude;
            if (length < 0.05f) { return; }
            int steps = Mathf.Max(1, Mathf.RoundToInt(length / PavingStep));
            float yaw = Mathf.Atan2(delta.x, delta.z) * Mathf.Rad2Deg;
            for (int i = 0; i < steps; i++)
            {
                Vector3 from = a + delta * (i / (float)steps);
                Vector3 to = a + delta * ((i + 1) / (float)steps);
                Placement p = new Placement();
                p.Kind = kind;
                p.Shape = Shape.Box;
                p.Position = new Vector3((from.x + to.x) * 0.5f, height + 0.03f,
                                         (from.z + to.z) * 0.5f);
                p.Size = new Vector3(width, 0.06f, length / steps + width * 0.5f);
                p.Yaw = yaw;
                p.Solid = false;
                into.Add(p);
            }
        }

        private static Vector3 Nearest(List<Vector3> path, Vector3 to)
        {
            Vector3 best = path[0]; float bestD = float.MaxValue;
            for (int i = 0; i < path.Count; i++)
            {
                Vector3 delta = path[i] - to; delta.y = 0f;
                float dd = delta.sqrMagnitude;
                if (dd < bestD) { bestD = dd; best = path[i]; }
            }
            return best;
        }

        /// <summary>How far a point is from the street's centre line.</summary>
        public static float DistanceToPath(List<Vector3> path, Vector3 p)
        {
            float best = float.MaxValue;
            for (int i = 1; i < path.Count; i++)
            {
                best = Mathf.Min(best, ToSegment(p, path[i - 1], path[i]));
            }
            return best;
        }

        private static float ToSegment(Vector3 p, Vector3 a, Vector3 b)
        {
            Vector3 ab = b - a; ab.y = 0f;
            Vector3 ap = p - a; ap.y = 0f;
            float len2 = ab.sqrMagnitude;
            float t = len2 < 1e-6f ? 0f : Mathf.Clamp01(Vector3.Dot(ap, ab) / len2);
            Vector3 on = a + ab * t;
            Vector3 delta = p - on; delta.y = 0f;
            return delta.magnitude;
        }

        // ------------------------------------------------------------ blocks

        /// <summary>
        /// What stands either side of the way. A polar lattice out from the
        /// middle — rings spaced by the theme, each ring holding as many
        /// plots as its circumference allows — with everything that would
        /// stand on the street, in a fight, or off the edge dropped.
        /// </summary>
        private static void Blocks(District d, List<Vector3> path, List<Site> sites,
                                   float height, Vocabulary v, int level, List<Placement> into)
        {
            Bounds2D inner = d.Bounds.Inset(v.Depth * 0.5f + 3f);
            int ring = 0;
            for (float r = d.Extent * 0.13f; r < d.Extent * 0.99f; r += v.Spacing, ring++)
            {
                int n = Mathf.Max(6, Mathf.RoundToInt(2f * Mathf.PI * r / v.Spacing));
                for (int k = 0; k < n; k++)
                {
                    int salt = d.AreaIndex * 7919 + level * 613 + ring * 131 + k * 17;
                    float wobble = (District.Hash01(salt) - 0.5f) * (2f * Mathf.PI / n) * 0.8f;
                    float angle = k * 2f * Mathf.PI / n + wobble;
                    float radius = r + (District.Hash01(salt + 1) - 0.5f) * v.Spacing * 0.35f;
                    Vector3 at = new Vector3(Mathf.Cos(angle) * radius, height,
                                             Mathf.Sin(angle) * radius);

                    if (District.Hash01(salt + 2) > v.Density) { continue; }
                    if (!inner.Contains(at)) { continue; }

                    bool tall = District.Hash01(salt + 3) < v.TallChance;
                    float w = Lerp(v.MinWidth, v.MaxWidth, District.Hash01(salt + 4));
                    float dep = Lerp(v.MinWidth, v.MaxWidth, District.Hash01(salt + 5));
                    float h = tall ? Lerp(v.TallMin, v.TallMax, District.Hash01(salt + 6))
                                   : Lerp(v.MinHeight, v.MaxHeight, District.Hash01(salt + 6));
                    float half = Mathf.Max(w, dep) * 0.5f;

                    if (DistanceToPath(path, at) < StreetHalfWidth + half + Clearance) { continue; }
                    if (NearSite(sites, at, half + Clearance)) { continue; }

                    Placement p = new Placement();
                    p.Kind = tall ? v.Tall : v.Block;
                    p.Shape = tall && v.TallIsPost ? Shape.Post : Shape.Box;
                    p.Size = p.Shape == Shape.Post
                           ? new Vector3(w * 0.5f, h, w * 0.5f)
                           : new Vector3(w, h, dep);
                    p.Position = new Vector3(at.x, height + h * 0.5f, at.z);
                    // Face the middle, so a frontage looks onto the way in.
                    p.Yaw = Mathf.Atan2(-at.x, -at.z) * Mathf.Rad2Deg
                          + (District.Hash01(salt + 7) - 0.5f) * v.YawJitter;
                    p.Solid = true;
                    into.Add(p);
                }
            }
        }

        private static bool NearSite(List<Site> sites, Vector3 at, float margin)
        {
            for (int i = 0; i < sites.Count; i++)
            {
                Site s = sites[i];
                Vector3 delta = new Vector3(s.Position.x - at.x, 0f, s.Position.z - at.z);
                if (delta.magnitude < s.Radius + margin) { return true; }
            }
            return false;
        }

        // --------------------------------------------------------------- rim

        /// <summary>
        /// The district's edge, so the field ends in something rather than
        /// stopping. It is gapped at every exit — the way out is a gap in the
        /// wall, which is what makes it findable from inside.
        /// </summary>
        private static void Rim(District d, float height, Vocabulary v, int level,
                                List<Placement> into)
        {
            const float segment = 9f, gap = 11f;
            float e = d.Extent - 1f;
            List<Site> exits = new List<Site>();
            List<Site> all = d.SitesOn(0);          // exits live on the street
            for (int i = 0; i < all.Count; i++)
            {
                if (all[i].Kind == SiteKind.Exit) { exits.Add(all[i]); }
            }

            for (int side = 0; side < 4; side++)
            {
                int n = Mathf.Max(2, Mathf.RoundToInt(2f * e / segment));
                for (int i = 0; i < n; i++)
                {
                    float along = -e + (i + 0.5f) * (2f * e / n);
                    Vector3 at;
                    float yaw;
                    if (side == 0) { at = new Vector3(along, 0f, e); yaw = 0f; }
                    else if (side == 1) { at = new Vector3(along, 0f, -e); yaw = 0f; }
                    else if (side == 2) { at = new Vector3(e, 0f, along); yaw = 90f; }
                    else { at = new Vector3(-e, 0f, along); yaw = 90f; }

                    bool doorway = false;
                    for (int k = 0; k < exits.Count; k++)
                    {
                        Vector3 delta = new Vector3(exits[k].Position.x - at.x, 0f,
                                                    exits[k].Position.z - at.z);
                        if (delta.magnitude < gap) { doorway = true; break; }
                    }
                    if (doorway) { continue; }

                    int salt = d.AreaIndex * 5527 + level * 331 + side * 97 + i;
                    float h = Lerp(v.RimMin, v.RimMax, District.Hash01(salt));
                    Placement p = new Placement();
                    p.Kind = v.Rim;
                    p.Shape = Shape.Box;
                    p.Size = new Vector3(2f * e / n + 0.4f, h, 1.2f);
                    p.Position = new Vector3(at.x, height + h * 0.5f, at.z);
                    p.Yaw = yaw;
                    p.Solid = true;
                    into.Add(p);
                }
            }
        }

        // -------------------------------------------------------- vocabulary

        /// <summary>What one kind of place is built of.</summary>
        public struct Vocabulary
        {
            public string Block, Tall, Rim, Paving;
            public bool TallIsPost;
            /// <summary>Metres between plots. Small is a crowded place.</summary>
            public float Spacing;
            /// <summary>Share of plots that are built on at all, 0..1.</summary>
            public float Density;
            public float MinWidth, MaxWidth, MinHeight, MaxHeight;
            public float TallChance, TallMin, TallMax;
            public float RimMin, RimMax, YawJitter;
            /// <summary>The deepest a plot gets, for keeping the rim clear.</summary>
            public float Depth { get { return MaxWidth; } }
        }

        /// <summary>
        /// The nine themes, and the two floors that are the same everywhere.
        ///
        /// A cellar is a cellar under a souq and under a tower block: pillars
        /// holding up what is above, and what has fallen off it. The roofs are
        /// tanks and aerials for the same reason. Only the street wears the
        /// district's own face.
        /// </summary>
        public static Vocabulary VocabularyFor(string theme, int level)
        {
            if (level < 0)
            {
                return Make("pillar", "column", "rock", "flagstone", true, 13f, 0.62f,
                            1.0f, 2.2f, 3.4f, 4.2f, 0.30f, 4.4f, 5.0f, 2.6f, 3.4f, 8f);
            }
            if (level > 0)
            {
                return Make("tank", "aerial", "parapet", "felt", true, 12f, 0.5f,
                            1.6f, 3.4f, 1.2f, 2.6f, 0.22f, 4f, 7f, 1.0f, 1.4f, 20f);
            }

            switch (theme)
            {
                case "Souq":
                    // A market is the densest place in the game and the lowest.
                    return Make("stall", "warehouse", "wall", "flagstone", false, 10f, 0.72f,
                                2.6f, 5.5f, 2.6f, 4.2f, 0.12f, 7f, 10f, 2.4f, 3.2f, 14f);
                case "Gym":
                    return Make("hall", "chimney", "wall", "concrete", true, 15f, 0.55f,
                                5f, 11f, 4f, 7f, 0.10f, 11f, 15f, 2.6f, 3.4f, 6f);
                case "Fishmarket":
                    return Make("shed", "crane", "quay", "boards", true, 13f, 0.6f,
                                3.5f, 8f, 3f, 5f, 0.14f, 12f, 18f, 1.2f, 1.8f, 10f);
                case "Towers":
                    // The one place with a skyline. Sparse plots, tall things.
                    return Make("block", "tower", "hoarding", "concrete", false, 21f, 0.5f,
                                7f, 15f, 6f, 12f, 0.42f, 24f, 52f, 2.8f, 3.6f, 4f);
                case "Marina":
                    return Make("front", "mast", "rail", "boards", true, 14f, 0.58f,
                                4f, 9f, 3.5f, 6.5f, 0.18f, 10f, 16f, 1.0f, 1.4f, 8f);
                case "Failaka":
                    return Make("ruin", "stone", "shore", "sand", false, 17f, 0.45f,
                                3f, 8f, 1.6f, 4.5f, 0.16f, 5f, 8f, 1.0f, 2.2f, 26f);
                case "Highway":
                    return Make("wreck", "pylon", "barrier", "asphalt", true, 18f, 0.4f,
                                2.4f, 6f, 1.6f, 3.2f, 0.24f, 14f, 22f, 1.0f, 1.4f, 30f);
                case "Desert":
                    // Almost nothing, a long way apart. Crossing it is the point.
                    return Make("tent", "rock", "dune", "sand", false, 24f, 0.34f,
                                3.5f, 7f, 2.2f, 3.4f, 0.30f, 4f, 9f, 1.4f, 2.6f, 34f);
                case "Arena":
                    return Make("seating", "floodlight", "bowl", "boards", true, 12f, 0.66f,
                                4f, 9f, 2.4f, 5f, 0.14f, 16f, 22f, 5f, 6f, 6f);
                default:
                    return Make("block", "tower", "wall", "concrete", false, 16f, 0.55f,
                                4f, 9f, 3f, 6f, 0.16f, 10f, 18f, 2.4f, 3.2f, 12f);
            }
        }

        private static Vocabulary Make(string block, string tall, string rim, string paving,
                                       bool tallIsPost, float spacing, float density,
                                       float minW, float maxW, float minH, float maxH,
                                       float tallChance, float tallMin, float tallMax,
                                       float rimMin, float rimMax, float yawJitter)
        {
            Vocabulary v = new Vocabulary();
            v.Block = block; v.Tall = tall; v.Rim = rim; v.Paving = paving;
            v.TallIsPost = tallIsPost;
            v.Spacing = spacing; v.Density = density;
            v.MinWidth = minW; v.MaxWidth = maxW;
            v.MinHeight = minH; v.MaxHeight = maxH;
            v.TallChance = tallChance; v.TallMin = tallMin; v.TallMax = tallMax;
            v.RimMin = rimMin; v.RimMax = rimMax; v.YawJitter = yawJitter;
            return v;
        }

        private static float Lerp(float a, float b, float t) { return a + (b - a) * t; }
    }
}
