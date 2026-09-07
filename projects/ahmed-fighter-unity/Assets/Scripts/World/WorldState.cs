using System.Collections.Generic;
using Ahmed.Data;

namespace Ahmed.World
{
    /// <summary>
    /// What the world remembers.
    ///
    /// This is the difference between an open world and a set of levels. A
    /// fight you won stays won, a gate you opened stays open, and a talent you
    /// found stays found — so walking back through a district you cleared an
    /// hour ago is quiet, and the route you could not take then is open now.
    /// Without it, backtracking is just the same fights again and the map
    /// stops being a place.
    ///
    /// In memory only so far: nothing here survives quitting. Saving it is
    /// the next job and is a serialiser over these three sets, not a redesign.
    /// </summary>
    public static class WorldState
    {
        /// <summary>Encounters and gates already dealt with, as area:site.</summary>
        private static readonly HashSet<long> Cleared = new HashSet<long>();
        private static readonly HashSet<Ability> Talents = new HashSet<Ability>();
        private static readonly HashSet<int> ClearedAreas = new HashSet<int>();

        public static int Experience { get; private set; }
        public static int CurrentArea { get; set; }

        private static long Key(int area, int site) { return ((long)area << 32) | (uint)site; }

        public static bool IsCleared(int area, int site) { return Cleared.Contains(Key(area, site)); }

        public static void MarkCleared(int area, int site) { Cleared.Add(Key(area, site)); }

        /// <summary>True once every encounter in the district has been won.</summary>
        public static bool IsAreaCleared(int area) { return ClearedAreas.Contains(area); }

        public static void MarkAreaCleared(int area) { ClearedAreas.Add(area); }

        public static void GrantTalent(Ability talent)
        {
            if (talent != Ability.None) { Talents.Add(talent); }
        }

        public static bool HasTalent(Ability talent)
        {
            return talent == Ability.None || Talents.Contains(talent);
        }

        public static int TalentCount { get { return Talents.Count; } }

        public static void AddExperience(int amount)
        {
            if (amount > 0) { Experience += amount; }
        }

        /// <summary>Can the player use this way out yet? A link may want a
        /// talent, another district cleared, or both.</summary>
        public static bool CanUse(WorldLink link)
        {
            if (link == null || link.to < 0) { return false; }
            if (!HasTalent(link.RequiredAbility)) { return false; }
            if (link.afterCleared >= 0 && !IsAreaCleared(link.afterCleared)) { return false; }
            return true;
        }

        /// <summary>New game. Also what a test calls between cases.</summary>
        public static void Reset()
        {
            Cleared.Clear();
            Talents.Clear();
            ClearedAreas.Clear();
            Experience = 0;
            CurrentArea = 0;
        }
    }
}
