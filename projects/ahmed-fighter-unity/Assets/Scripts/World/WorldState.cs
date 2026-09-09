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
    /// It survives quitting now: <see cref="SaveGame"/> is the serialiser over
    /// these sets, and the hub in the first district is where it is written.
    /// </summary>
    public static class WorldState
    {
        /// <summary>Encounters and gates already dealt with, as area:site.</summary>
        private static readonly HashSet<long> Cleared = new HashSet<long>();
        private static readonly HashSet<Ability> Talents = new HashSet<Ability>();
        private static readonly HashSet<int> ClearedAreas = new HashSet<int>();
        /// <summary>Levels bought per track, indexed by UpgradeTrack.</summary>
        private static readonly int[] Upgrades =
            new int[System.Enum.GetValues(typeof(UpgradeTrack)).Length];

        public static int Experience { get; private set; }
        public static int CurrentArea { get; set; }

        // ------------------------------------------------------------- upgrades

        public static int UpgradeLevel(UpgradeTrack track) { return Upgrades[(int)track]; }

        /// <summary>Used by the save; a purchase goes through UpgradeStore.</summary>
        public static void SetUpgradeLevel(UpgradeTrack track, int level)
        {
            Upgrades[(int)track] = UnityEngine.Mathf.Max(0, level);
        }

        /// <summary>Take experience for a purchase. False if it is not there,
        /// and nothing is spent -- the caller must not have to check first.</summary>
        public static bool SpendExperience(int amount)
        {
            if (amount < 0 || Experience < amount) { return false; }
            Experience -= amount;
            return true;
        }

        // ----------------------------------------------------------- checkpoint

        /// <summary>Where the last save point was touched. A death returns
        /// Ahmed here rather than leaving him on the floor, which is what he
        /// did before: nothing in the world reacted to the player dying.</summary>
        public static bool HasCheckpoint { get; private set; }
        public static int CheckpointArea { get; private set; }
        public static UnityEngine.Vector3 CheckpointPosition { get; private set; }
        /// <summary>Condition to come back in, as a fraction of maximum.</summary>
        public static float CheckpointHealth { get; private set; }

        public static void SetCheckpoint(int area, UnityEngine.Vector3 position,
                                         float healthFraction)
        {
            HasCheckpoint = true;
            CheckpointArea = area;
            CheckpointPosition = position;
            CheckpointHealth = UnityEngine.Mathf.Clamp01(healthFraction);
        }

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

        // ---------------------------------------------------- for the save only

        public static IEnumerable<long> ClearedKeys { get { return Cleared; } }
        public static IEnumerable<Ability> HeldTalents { get { return Talents; } }
        public static IEnumerable<int> ClearedAreaList { get { return ClearedAreas; } }
        public static void RestoreClearedKey(long key) { Cleared.Add(key); }
        public static void RestoreExperience(int xp) { Experience = xp < 0 ? 0 : xp; }
        public static void ClearCheckpoint() { HasCheckpoint = false; }

        /// <summary>New game. Also what a test calls between cases.</summary>
        public static void Reset()
        {
            Cleared.Clear();
            Talents.Clear();
            ClearedAreas.Clear();
            for (int i = 0; i < Upgrades.Length; i++) { Upgrades[i] = 0; }
            Experience = 0;
            CurrentArea = 0;
            HasCheckpoint = false;
            CheckpointArea = 0;
            CheckpointPosition = UnityEngine.Vector3.zero;
            CheckpointHealth = 1f;
        }
    }
}
