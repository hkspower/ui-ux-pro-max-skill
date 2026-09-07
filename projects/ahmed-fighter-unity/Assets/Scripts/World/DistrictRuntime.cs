using System.Collections.Generic;
using UnityEngine;
using Ahmed.Combat;
using Ahmed.Data;

namespace Ahmed.World
{
    /// <summary>
    /// Runs one district: builds its ground and its sites, wakes encounters as
    /// the player walks near them, hands out gate rewards, and carries him
    /// across to the next district when he reaches an edge.
    ///
    /// This is what replaces the wave director in open play. The difference is
    /// not the spawning -- that is much the same -- it is *what decides when*.
    /// A stage triggered its waves by how far along a line the player had
    /// walked, and locked him in an arena until each was dead. Here an
    /// encounter wakes because he came near it, does not stop him leaving, and
    /// stays cleared once won. That single change is most of what separates a
    /// world from a level.
    /// </summary>
    public class DistrictRuntime : MonoBehaviour
    {
        public static DistrictRuntime Current { get; private set; }

        public District District { get; private set; }

        [Tooltip("Cloned for every enemy. Needs an EnemyFighter.")]
        public GameObject EnemyPrefab;

        public float EnemyHealthScale = 1f;
        public float EnemyDamageScale = 1f;

        /// <summary>Fires when the player crosses into another area.</summary>
        public event System.Action<int, string> AreaChanged;

        private readonly List<GameObject> _scenery = new List<GameObject>();
        private readonly Dictionary<int, List<EnemyFighter>> _liveBySite =
            new Dictionary<int, List<EnemyFighter>>();
        private readonly HashSet<int> _awake = new HashSet<int>();
        private float _exitCooldown;

        private void Awake() { Current = this; }
        private void OnDestroy() { if (Current == this) { Current = null; } }

        // ------------------------------------------------------------ loading

        public void Enter(int areaIndex, Vector3 arriveAt)
        {
            Unload();

            WorldArea area = GameData.Area(areaIndex);
            StageRow stage = GameData.Stage(areaIndex);
            District = District.Build(areaIndex, area, stage);
            WorldState.CurrentArea = areaIndex;

            BuildScenery();

            PlayerFighter player = PlayerFighter.Current;
            if (player != null)
            {
                player.Bounds = District.Bounds;
                player.transform.position = District.Bounds.Inset(4f).Clamp(arriveAt);
            }
            _exitCooldown = 0.75f;      // do not bounce straight back out again

            Debug.Log("[Ahmed] " + District.DisplayName + " — "
                + (District.Extent * 2f).ToString("0") + " m across, "
                + District.Sites.Count + " sites");
        }

        private void Unload()
        {
            foreach (KeyValuePair<int, List<EnemyFighter>> pair in _liveBySite)
            {
                for (int i = 0; i < pair.Value.Count; i++)
                {
                    if (pair.Value[i] != null) { Object.Destroy(pair.Value[i].gameObject); }
                }
            }
            _liveBySite.Clear();
            _awake.Clear();
            // Bodies that no longer exist must not hold an attack token
            // against the next fight.
            CrowdControl.Clear();

            for (int i = 0; i < _scenery.Count; i++)
            {
                if (_scenery[i] != null) { Object.Destroy(_scenery[i]); }
            }
            _scenery.Clear();
        }

        /// <summary>
        /// Ground, a fence and a marker per site. Primitives on purpose: this
        /// is the shape of the district, not its art, and the art replaces it
        /// piece by piece without any of the logic here changing.
        /// </summary>
        private void BuildScenery()
        {
            float side = District.Extent * 2f;

            GameObject ground = GameObject.CreatePrimitive(PrimitiveType.Cube);
            ground.name = "Ground " + District.Name;
            ground.transform.position = new Vector3(0f, -0.5f, 0f);
            ground.transform.localScale = new Vector3(side, 1f, side);
            _scenery.Add(ground);

            for (int i = 0; i < District.Sites.Count; i++)
            {
                Site s = District.Sites[i];
                GameObject marker = GameObject.CreatePrimitive(
                    s.Kind == SiteKind.Exit ? PrimitiveType.Cube : PrimitiveType.Cylinder);
                marker.name = s.Kind + " " + s.Id;
                marker.transform.position = s.Position + Vector3.up * 0.6f;
                marker.transform.localScale = s.Kind == SiteKind.Exit
                    ? new Vector3(3.5f, 2.4f, 1f)
                    : new Vector3(1.2f, 0.6f, 1.2f);

                Collider c = marker.GetComponent<Collider>();
                if (c != null) { Object.Destroy(c); }   // markers are signposts, not walls
                _scenery.Add(marker);
            }
        }

        // --------------------------------------------------------------- tick

        private void Update()
        {
            if (District == null) { return; }
            PlayerFighter player = PlayerFighter.Current;
            if (player == null || !player.IsAlive) { return; }

            _exitCooldown = Mathf.Max(0f, _exitCooldown - Time.deltaTime);
            Vector3 here = player.transform.position;

            for (int i = 0; i < District.Sites.Count; i++)
            {
                Site s = District.Sites[i];
                Vector3 d = s.Position - here;
                d.y = 0f;
                float distance = d.magnitude;

                switch (s.Kind)
                {
                    case SiteKind.Encounter: TickEncounter(s, distance); break;
                    case SiteKind.Gate: TickGate(s, distance, player); break;
                    case SiteKind.Exit: TickExit(s, distance); break;
                }
            }
        }

        private void TickEncounter(Site s, float distance)
        {
            if (WorldState.IsCleared(District.AreaIndex, s.Id)) { return; }

            if (!_awake.Contains(s.Id))
            {
                if (distance <= s.Radius) { Wake(s); }
                return;
            }

            List<EnemyFighter> live = _liveBySite[s.Id];
            int standing = 0;
            for (int i = live.Count - 1; i >= 0; i--)
            {
                EnemyFighter e = live[i];
                if (e == null) { live.RemoveAt(i); continue; }
                if (e.IsAlive) { standing++; }
            }

            if (standing == 0)
            {
                WorldState.MarkCleared(District.AreaIndex, s.Id);
                _awake.Remove(s.Id);
                Game.AudioLibrary.PlayUI("Wave_Clear");
                CheckAreaCleared();
                return;
            }

            // Walked away. The fight goes back to sleep rather than trailing
            // him across the district -- an open world where every encounter
            // you brush past follows you forever is unplayable.
            if (distance > s.Radius * 2.6f)
            {
                for (int i = 0; i < live.Count; i++)
                {
                    if (live[i] != null) { Object.Destroy(live[i].gameObject); }
                }
                live.Clear();
                _awake.Remove(s.Id);
            }
        }

        private void Wake(Site s)
        {
            _awake.Add(s.Id);
            Game.AudioLibrary.PlayUI("Wave_Start");
            List<EnemyFighter> live = new List<EnemyFighter>();
            _liveBySite[s.Id] = live;

            if (s.Wave == null || s.Wave.fighters == null || EnemyPrefab == null) { return; }
            for (int i = 0; i < s.Wave.fighters.Length; i++)
            {
                EnemyFighter e = Spawn(s, s.Wave.fighters[i], i);
                if (e != null) { live.Add(e); }
            }
        }

        private EnemyFighter Spawn(Site site, string row, int indexInWave)
        {
            FighterRow def = GameData.Fighter(row);
            if (def == null) { return null; }

            // Around the site rather than in from one side: in the open there
            // is no "side" to come in from, and a ring reads as an ambush the
            // way a queue never did.
            float angle = (indexInWave / 6f) * Mathf.PI * 2f + Random.Range(-0.3f, 0.3f);
            float radius = site.Radius * Random.Range(0.45f, 0.8f);
            Vector3 at = site.Position + new Vector3(Mathf.Cos(angle) * radius, 0f,
                                                     Mathf.Sin(angle) * radius);
            at = District.Bounds.Inset(2f).Clamp(at);
            at.y = transform.position.y;

            GameObject go = Object.Instantiate(EnemyPrefab, at, Quaternion.identity);
            go.SetActive(true);
            EnemyFighter enemy = go.GetComponent<EnemyFighter>();
            if (enemy == null)
            {
                Debug.LogError("[Ahmed] EnemyPrefab has no EnemyFighter");
                Object.Destroy(go);
                return null;
            }

            enemy.ConfigureFrom(def, site.Tier, EnemyHealthScale, EnemyDamageScale);
            enemy.Bounds = District.Bounds;
            enemy.Leash(site.Position, site.Radius * 2.2f);
            enemy.FlankSide = (indexInWave % 2 == 0) ? 1f : -1f;
            enemy.LaneOffset = (indexInWave / 2) * 0.6f;
            enemy.Defeated += HandleDefeated;
            return enemy;
        }

        private void HandleDefeated(Fighter fighter)
        {
            EnemyFighter enemy = fighter as EnemyFighter;
            if (enemy == null) { return; }
            CrowdControl.Release(enemy);
            WorldState.AddExperience(enemy.ExperienceValue);
        }

        private void CheckAreaCleared()
        {
            for (int i = 0; i < District.Sites.Count; i++)
            {
                Site s = District.Sites[i];
                if (s.Kind != SiteKind.Encounter) { continue; }
                if (!WorldState.IsCleared(District.AreaIndex, s.Id)) { return; }
            }
            if (!WorldState.IsAreaCleared(District.AreaIndex))
            {
                WorldState.MarkAreaCleared(District.AreaIndex);
                Debug.Log("[Ahmed] " + District.DisplayName + " is clear.");
            }
        }

        private void TickGate(Site s, float distance, PlayerFighter player)
        {
            if (distance > s.Radius) { return; }
            if (WorldState.IsCleared(District.AreaIndex, s.Id)) { return; }
            if (s.Gate == null) { return; }

            WorldState.MarkCleared(District.AreaIndex, s.Id);
            WorldState.AddExperience(s.Gate.rewardExperience);
            if (s.Gate.RewardAbility != Ability.None)
            {
                WorldState.GrantTalent(s.Gate.RewardAbility);
                // The biggest sound in the game, and only ever this: a cache
                // of XP behind the same kind of gate gets the smaller one.
                Game.AudioLibrary.PlayUI("Talent_Found");
                Debug.Log("[Ahmed] found " + s.Gate.RewardAbility
                    + " — routes that wanted it are open now.");
            }
            else if (s.Gate.rewardExperience > 0)
            {
                Game.AudioLibrary.PlayUI("Exp_Cache");
            }
        }

        private void TickExit(Site s, float distance)
        {
            if (_exitCooldown > 0f || distance > s.Radius) { return; }

            WorldLink link = LinkFor(s);
            if (!WorldState.CanUse(link))
            {
                // Sealed. There is no HUD yet, so this is the only thing that
                // tells the player the route refused them rather than that
                // they missed the door.
                Game.AudioLibrary.Play("Exit_Sealed", s.Position);
                return;
            }

            // Arrive at the far side of the district you came from, so walking
            // east and then west puts you back where you started.
            District next = District.Build(s.ToArea, GameData.Area(s.ToArea),
                                           GameData.Stage(s.ToArea));
            Vector3 arrive;
            if (s.ExitLabel == "WEST") { arrive = new Vector3(next.Extent - 6f, 0f, 0f); }
            else if (s.ExitLabel == "EAST") { arrive = new Vector3(-next.Extent + 6f, 0f, 0f); }
            else { arrive = new Vector3(0f, 0f, -next.Extent + 6f); }

            int to = s.ToArea;
            Game.AudioLibrary.PlayUI("Exit_Travel");
            Enter(to, arrive);
            if (AreaChanged != null) { AreaChanged(to, District.DisplayName); }
        }

        private WorldLink LinkFor(Site s)
        {
            WorldArea area = GameData.Area(District.AreaIndex);
            if (area == null) { return null; }
            if (s.ExitLabel == "WEST") { return area.west; }
            if (s.ExitLabel == "EAST") { return area.east; }
            return area.door;
        }
    }
}
