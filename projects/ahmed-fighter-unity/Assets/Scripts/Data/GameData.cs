using System.Collections.Generic;
using UnityEngine;

namespace Ahmed.Data
{
    /// <summary>
    /// Every table in the game, loaded once and looked up by name.
    ///
    /// The JSON under Assets/Resources/Data is generated from the browser
    /// project and must never be hand-edited -- see AhmedTypes.cs. Loading is
    /// eager and synchronous because the whole payload is a few tens of
    /// kilobytes and a fighter that has to wait for its own numbers is a
    /// fighter that spawns wrong for a frame.
    /// </summary>
    public static class GameData
    {
        public static PlayerRow Player { get; private set; }
        public static IList<StageRow> Stages { get { Load(); return _stages; } }
        public static IList<LevelRow> Levels { get { Load(); return _levels; } }
        public static IList<UpgradeRow> Upgrades { get { Load(); return _upgrades; } }
        public static IList<WorldArea> Areas { get { Load(); return _areas; } }
        /// <summary>Which area the game starts in. Carried on every row by the
        /// exporter because JsonUtility has nowhere else to put a scalar.</summary>
        public static int StartArea
        {
            get { Load(); return _areas.Count > 0 ? _areas[0].startArea : 0; }
        }

        private static readonly Dictionary<string, AttackRow> _attacks =
            new Dictionary<string, AttackRow>();
        private static readonly Dictionary<string, FighterRow> _fighters =
            new Dictionary<string, FighterRow>();
        private static readonly Dictionary<string, StyleRow> _styles =
            new Dictionary<string, StyleRow>();
        private static readonly Dictionary<string, TalentRow> _talents =
            new Dictionary<string, TalentRow>();
        private static List<StageRow> _stages = new List<StageRow>();
        private static List<StratumRow> _strata = new List<StratumRow>();
        private static List<WorldArea> _areas = new List<WorldArea>();
        private static List<LevelRow> _levels = new List<LevelRow>();
        private static List<UpgradeRow> _upgrades = new List<UpgradeRow>();
        private static bool _loaded;

        /// <summary>JsonUtility cannot read a top-level array, so every table
        /// file is an object with one field. This is that field.</summary>
        [System.Serializable]
        private class Table<T> { public T[] items; }

        public static void Load()
        {
            if (_loaded) { return; }
            _loaded = true;   // set first: a parse failure must not loop

            foreach (AttackRow a in Read<AttackRow>("attacks"))
            {
                a.Resolve();
                _attacks[a.name] = a;
            }
            foreach (FighterRow f in Read<FighterRow>("fighters")) { _fighters[f.name] = f; }
            foreach (StyleRow s in Read<StyleRow>("styles"))
            {
                s.Resolve();
                _styles[s.name] = s;
            }
            foreach (TalentRow t in Read<TalentRow>("talents"))
            {
                t.Resolve();
                _talents[t.name] = t;
            }
            foreach (StageRow st in Read<StageRow>("stages"))
            {
                st.Resolve();
                _stages.Add(st);
            }
            foreach (StratumRow st in Read<StratumRow>("strata"))
            {
                st.Resolve();
                _strata.Add(st);
            }
            _levels.AddRange(Read<LevelRow>("levels"));
            foreach (UpgradeRow u in Read<UpgradeRow>("upgrades"))
            {
                u.Resolve();
                _upgrades.Add(u);
            }
            foreach (WorldArea a in Read<WorldArea>("world"))
            {
                a.Resolve();
                _areas.Add(a);
            }

            TextAsset player = Resources.Load<TextAsset>("Data/player");
            if (player == null)
            {
                Debug.LogError("[Ahmed] Data/player.json is missing. "
                    + "Run: node Tools/export/export.mjs");
                Player = new PlayerRow();
            }
            else
            {
                Player = JsonUtility.FromJson<PlayerRow>(player.text);
            }
        }

        /// <summary>What the next level of a track costs, or -1 at the cap.
        /// The price rises with the level, so it is a lookup and not a
        /// formula living in two places.</summary>
        public static int UpgradeCost(UpgradeTrack track, int nextLevel)
        {
            Load();
            for (int i = 0; i < _upgrades.Count; i++)
            {
                if (_upgrades[i].Track == track && _upgrades[i].level == nextLevel)
                {
                    return _upgrades[i].cost;
                }
            }
            return -1;
        }

        /// <summary>A track's row at any level, for its name and blurb.</summary>
        public static UpgradeRow UpgradeInfo(UpgradeTrack track)
        {
            Load();
            for (int i = 0; i < _upgrades.Count; i++)
            {
                if (_upgrades[i].Track == track) { return _upgrades[i]; }
            }
            return null;
        }

        private static T[] Read<T>(string file)
        {
            TextAsset asset = Resources.Load<TextAsset>("Data/" + file);
            if (asset == null)
            {
                Debug.LogError("[Ahmed] Data/" + file + ".json is missing. "
                    + "Run: node Tools/export/export.mjs");
                return new T[0];
            }
            Table<T> table = JsonUtility.FromJson<Table<T>>(asset.text);
            return table != null && table.items != null ? table.items : new T[0];
        }

        /// <summary>
        /// An attack by row name. Returns null and says so rather than
        /// throwing: a missing move should cost one swing, not the run.
        /// </summary>
        public static AttackRow Attack(string row)
        {
            Load();
            AttackRow found;
            if (_attacks.TryGetValue(row, out found)) { return found; }
            Debug.LogWarning("[Ahmed] unknown attack row '" + row + "'");
            return null;
        }

        public static FighterRow Fighter(string row)
        {
            Load();
            FighterRow found;
            if (_fighters.TryGetValue(row, out found)) { return found; }
            Debug.LogWarning("[Ahmed] unknown fighter row '" + row + "'");
            return null;
        }

        /// <summary>A fight style by name, or null -- which leaves the enemy
        /// on its plain close-and-swing AI rather than breaking it.</summary>
        public static StyleRow Style(string row)
        {
            Load();
            if (string.IsNullOrEmpty(row)) { return null; }
            StyleRow found;
            return _styles.TryGetValue(row, out found) ? found : null;
        }

        public static TalentRow Talent(string row)
        {
            Load();
            TalentRow found;
            return _talents.TryGetValue(row, out found) ? found : null;
        }

        public static WorldArea Area(int index)
        {
            Load();
            return index >= 0 && index < _areas.Count ? _areas[index] : null;
        }

        public static StageRow Stage(int index)
        {
            Load();
            return index >= 0 && index < _stages.Count ? _stages[index] : null;
        }

        /// <summary>The extra floors of an area -- under and up -- or an
        /// empty list for an area that has only its street.</summary>
        public static List<StratumRow> Strata(int area)
        {
            Load();
            List<StratumRow> found = new List<StratumRow>();
            for (int i = 0; i < _strata.Count; i++)
            {
                if (_strata[i].area == area) { found.Add(_strata[i]); }
            }
            return found;
        }

        /// <summary>Experience needed to leave this level. Zero at the cap.</summary>
        public static int ExperienceToNext(int level)
        {
            Load();
            for (int i = 0; i < _levels.Count; i++)
            {
                if (_levels[i].level == level) { return _levels[i].experienceToNext; }
            }
            return 0;
        }
    }
}
