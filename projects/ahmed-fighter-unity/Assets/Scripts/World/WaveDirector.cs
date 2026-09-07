using System.Collections.Generic;
using UnityEngine;
using Ahmed.Combat;
using Ahmed.Data;

namespace Ahmed.World
{
    /// <summary>
    /// Runs a stage: triggers waves as the player walks, locks the arena while
    /// one is live, spawns the bodies, and lets go when the last one drops.
    ///
    /// It also holds the attack tokens. At most a couple of enemies may be
    /// swinging at once and the rest circle, which is the single rule that
    /// makes a crowd fair rather than a pile-on.
    /// </summary>
    public class WaveDirector : MonoBehaviour
    {
        /// <summary>The one running the current stage. Enemies ask it for a
        /// token, and searching the scene for it every frame would cost more
        /// than the token is worth.</summary>
        public static WaveDirector Active { get; private set; }

        [Tooltip("Index into stages.json.")]
        public int StageIndex;

        [Tooltip("Prefab spawned for every enemy. Needs an EnemyFighter.")]
        public GameObject EnemyPrefab;

        public float EnemyHealthScale = 1f;
        public float EnemyDamageScale = 1f;

        public event System.Action<int> WaveStarted;
        public event System.Action<int> WaveCleared;
        public event System.Action StageCleared;

        public StageRow Stage { get; private set; }
        public int WaveIndex { get; private set; }
        public int EnemiesDefeated { get; private set; }
        public int ExperienceEarned { get; private set; }
        public bool ArenaLocked { get; private set; }
        public bool Finished { get; private set; }

        private readonly List<EnemyFighter> _live = new List<EnemyFighter>();
        private float _arenaOriginX;
        private int _survivalWave;

        private void OnEnable() { Active = this; }
        private void OnDisable() { if (Active == this) { Active = null; } }

        private void Start()
        {
            Stage = GameData.Stage(StageIndex);
            if (Stage == null)
            {
                Debug.LogError("[Ahmed] no stage at index " + StageIndex
                    + ". Run: node Tools/export/export.mjs");
                enabled = false;
                return;
            }
            ApplyArenaBounds();
        }

        private void Update()
        {
            if (Stage == null || Finished) { return; }
            PlayerFighter player = PlayerFighter.Current;
            if (player == null || !player.IsAlive) { return; }

            PruneDead();

            if (!ArenaLocked && WaveIndex < WaveCount())
            {
                WaveRow next = WaveAt(WaveIndex);
                if (next != null && (next.triggerDistance < 0f
                                     || player.transform.position.x >= next.triggerDistance))
                {
                    StartWave(next, player);
                }
            }

            if (ArenaLocked && CountLiving() == 0)
            {
                ArenaLocked = false;
                CrowdControl.Clear();
                Game.AudioLibrary.PlayUI("Wave_Clear");
                if (WaveCleared != null) { WaveCleared(WaveIndex); }
                WaveIndex++;

                if (Stage.survival)
                {
                    _survivalWave++;
                    // Endless: the next wave is generated rather than authored.
                    StartWave(MakeSurvivalWave(_survivalWave), player);
                }
                ApplyArenaBounds();
            }

            if (!Stage.survival && WaveIndex >= WaveCount()
                && player.transform.position.x >= Stage.length - 3.6f)
            {
                Finished = true;
                Game.AudioLibrary.PlayUI("Stage_Clear");
                if (StageCleared != null) { StageCleared(); }
            }
        }

        private int WaveCount() { return Stage.waves != null ? Stage.waves.Length : 0; }

        private WaveRow WaveAt(int i)
        {
            return Stage.waves != null && i >= 0 && i < Stage.waves.Length ? Stage.waves[i] : null;
        }

        private void StartWave(WaveRow wave, PlayerFighter player)
        {
            if (wave == null || wave.fighters == null) { return; }

            ArenaLocked = true;
            _arenaOriginX = player.transform.position.x - 2f;
            ApplyArenaBounds();

            int tier = wave.tierOverride >= 0 ? wave.tierOverride : Stage.tier;
            for (int i = 0; i < wave.fighters.Length; i++)
            {
                SpawnFighter(wave.fighters[i], tier, i);
            }
            Game.AudioLibrary.PlayUI("Wave_Start");
            if (WaveStarted != null) { WaveStarted(WaveIndex); }
        }

        private void SpawnFighter(string row, int tier, int indexInWave)
        {
            FighterRow def = GameData.Fighter(row);
            if (def == null || EnemyPrefab == null) { return; }

            // Alternate the side they walk in from so waves surround rather
            // than queue up on one shoulder.
            bool fromRight = (indexInWave % 3) != 2;
            float x = fromRight
                ? _arenaOriginX + Playfield.ArenaWidth + 2f + indexInWave * 0.9f
                : _arenaOriginX - 2f - indexInWave * 0.7f;
            float z = Random.Range(Playfield.DepthMin * 0.8f, Playfield.DepthMax * 0.8f);

            GameObject go = Object.Instantiate(EnemyPrefab,
                new Vector3(x, transform.position.y, z), Quaternion.identity);
            EnemyFighter enemy = go.GetComponent<EnemyFighter>();
            if (enemy == null)
            {
                Debug.LogError("[Ahmed] EnemyPrefab has no EnemyFighter component");
                Object.Destroy(go);
                return;
            }

            enemy.ConfigureFrom(def, tier, EnemyHealthScale, EnemyDamageScale);
            enemy.FlankSide = (indexInWave % 2 == 0) ? 1f : -1f;
            enemy.LaneOffset = (indexInWave / 2) * 0.6f;
            enemy.DepthOffset = Random.Range(-1.9f, 1.9f);
            enemy.Defeated += HandleEnemyDefeated;

            _live.Add(enemy);
            ApplyArenaBounds();
        }

        private void HandleEnemyDefeated(Fighter fighter)
        {
            EnemyFighter enemy = fighter as EnemyFighter;
            if (enemy == null) { return; }
            ReleaseAttackToken(enemy);
            EnemiesDefeated++;
            ExperienceEarned += enemy.ExperienceValue;
        }

        private void PruneDead()
        {
            for (int i = _live.Count - 1; i >= 0; i--)
            {
                if (_live[i] == null) { _live.RemoveAt(i); }
            }
        }

        private int CountLiving()
        {
            int n = 0;
            for (int i = 0; i < _live.Count; i++)
            {
                if (_live[i] != null && _live[i].IsAlive) { n++; }
            }
            return n;
        }

        private void ApplyArenaBounds()
        {
            float minX = ArenaLocked ? _arenaOriginX : 0f;
            float maxX = ArenaLocked ? _arenaOriginX + Playfield.ArenaWidth
                                     : (Stage != null ? Stage.length : 1000f);

            if (PlayerFighter.Current != null)
            {
                PlayerFighter.Current.SetArenaBounds(minX, maxX);
            }
            for (int i = 0; i < _live.Count; i++)
            {
                if (_live[i] != null) { _live[i].SetEnemyArenaBounds(minX, maxX); }
            }
        }

        // ------------------------------------------------------------ tokens

        /// <summary>Kept so the corridor mode reads the same as it did; the
        /// pool itself moved to CrowdControl when the open world arrived, and
        /// there is no longer one director for everyone to ask.</summary>
        public bool TryClaimAttackToken(EnemyFighter claimant)
        {
            return CrowdControl.TryClaim(claimant);
        }

        public void ReleaseAttackToken(EnemyFighter claimant)
        {
            CrowdControl.Release(claimant);
        }

        // ---------------------------------------------------------- survival

        private WaveRow MakeSurvivalWave(int waveNumber)
        {
            WaveRow wave = new WaveRow();
            wave.triggerDistance = -1f;             // endless waves start at once
            wave.tierOverride = waveNumber / 2;

            List<string> pool = new List<string> { "Thug", "Brawler" };
            if (waveNumber >= 2) { pool.Add("Runner"); }
            if (waveNumber >= 3) { pool.Add("Kicker"); }
            if (waveNumber >= 5) { pool.Add("Grappler"); }
            if (waveNumber >= 6) { pool.Add("Bouncer"); }
            if (waveNumber >= 7) { pool.Add("Capo"); }

            int count = Mathf.Min(6, 2 + waveNumber / 2);
            wave.fighters = new string[count];
            for (int i = 0; i < count; i++)
            {
                wave.fighters[i] = pool[Random.Range(0, pool.Count)];
            }
            return wave;
        }
    }
}
