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

        /// <summary>True while Ahmed is standing in the hub. The upgrade panel
        /// watches this; nothing else in the world cares.</summary>
        public bool InHub { get; private set; }

        /// <summary>Which floor Ahmed is on: -1 the cellar, 0 the street,
        /// +1 the roofs. Read off his height every frame, so a fall or a
        /// shaft both count.</summary>
        public int CurrentLevel { get; private set; }

        /// <summary>The encounter whose title fight is live, or -1. The music
        /// follows it.</summary>
        private int _bossSite = -1;

        private readonly List<GameObject> _scenery = new List<GameObject>();
        private readonly Dictionary<int, List<EnemyFighter>> _liveBySite =
            new Dictionary<int, List<EnemyFighter>>();
        private readonly HashSet<int> _awake = new HashSet<int>();
        /// <summary>Exits that have already refused the player on this
        /// approach. The refusal sounds once when he reaches the door, not
        /// every cooldown for as long as he stands in it.</summary>
        private readonly HashSet<int> _refusing = new HashSet<int>();
        private float _exitCooldown;
        private bool _respawning;

        private void Awake() { Current = this; }
        private void OnDestroy() { if (Current == this) { Current = null; } }

        // ------------------------------------------------------------ loading

        public void Enter(int areaIndex, Vector3 arriveAt)
        {
            Unload();

            WorldArea area = GameData.Area(areaIndex);
            StageRow stage = GameData.Stage(areaIndex);
            District = District.Build(areaIndex, area, stage, GameData.Strata(areaIndex));
            WorldState.CurrentArea = areaIndex;

            BuildScenery();

            PlayerFighter player = PlayerFighter.Current;
            if (player != null)
            {
                player.Bounds = District.Bounds;
                player.Teleport(District.Bounds.Inset(4f).Clamp(arriveAt));
                CurrentLevel = District.LevelAt(arriveAt.y);
            }
            _exitCooldown = 0.75f;      // do not bounce straight back out again
            _bossSite = -1;
            PlayMusicForFloor();

            Debug.Log("[Ahmed] " + District.DisplayName + " — "
                + (District.Extent * 2f).ToString("0") + " m across, "
                + District.Floors.Count + " floors, "
                + District.Sites.Count + " sites");
        }

        /// <summary>The floor's own loop, unless a title fight is on.</summary>
        private void PlayMusicForFloor()
        {
            Game.MusicDirector music = Game.MusicDirector.Current;
            if (music == null) { return; }
            music.Play(_bossSite >= 0 ? "Music_Boss" : Game.MusicDirector.CueForLevel(CurrentLevel));
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
            _refusing.Clear();
            InHub = false;
            _bossSite = -1;
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

            // One slab per floor. The cellar's and the roofs' are the street's
            // again at their own height; what they look like is district art,
            // which is not here yet, and this is the shape of them.
            foreach (KeyValuePair<int, float> floor in District.Floors)
            {
                GameObject ground = GameObject.CreatePrimitive(PrimitiveType.Cube);
                ground.name = "Ground " + District.Name + " " + floor.Key;
                ground.transform.position = new Vector3(0f, floor.Value - 0.5f, 0f);
                ground.transform.localScale = new Vector3(side, 1f, side);
                _scenery.Add(ground);
            }

            for (int i = 0; i < District.Sites.Count; i++)
            {
                Site s = District.Sites[i];
                GameObject marker = GameObject.CreatePrimitive(
                    s.Kind == SiteKind.Exit ? PrimitiveType.Cube : PrimitiveType.Cylinder);
                marker.name = s.Kind + " " + s.Id;
                marker.transform.position = s.Position + Vector3.up * (s.Kind == SiteKind.Shaft ? 1.5f : 0.6f);
                marker.transform.localScale = s.Kind == SiteKind.Exit
                    ? new Vector3(3.5f, 2.4f, 1f)
                    : s.Kind == SiteKind.Hub
                        ? new Vector3(s.Radius * 2f, 0.1f, s.Radius * 2f)
                    : s.Kind == SiteKind.Shaft
                        ? new Vector3(1.6f, 1.5f, 1.6f)      // a stairhead, tall enough to see
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
            if (player == null) { return; }
            if (!player.IsAlive) { Respawn(player); return; }
            _respawning = false;

            _exitCooldown = Mathf.Max(0f, _exitCooldown - Time.deltaTime);
            Vector3 here = player.transform.position;

            int level = District.LevelAt(here.y);
            if (level != CurrentLevel)
            {
                CurrentLevel = level;
                PlayMusicForFloor();
            }

            for (int i = 0; i < District.Sites.Count; i++)
            {
                Site s = District.Sites[i];
                // A floor is its own field. A fight in the cellar must not
                // wake because Ahmed walked over it on the street, and the
                // distance a site cares about is across its own floor.
                if (s.Level != CurrentLevel)
                {
                    if (s.Kind == SiteKind.Encounter && _awake.Contains(s.Id)) { Sleep(s); }
                    continue;
                }
                Vector3 d = s.Position - here;
                d.y = 0f;
                float distance = d.magnitude;

                switch (s.Kind)
                {
                    case SiteKind.Encounter: TickEncounter(s, distance); break;
                    case SiteKind.Gate: TickGate(s, distance, player); break;
                    case SiteKind.Exit: TickExit(s, distance); break;
                    case SiteKind.Hub: TickHub(s, distance, player); break;
                    case SiteKind.Shaft: TickShaft(s, distance, player); break;
                }
            }
        }

        /// <summary>
        /// The stair or the ladder. Stepping in puts Ahmed on the other floor
        /// at the same spot, a pace off the shaft so he does not come
        /// straight back. A ladder that wants a talent he has not found
        /// refuses him the way a sealed exit does: once per approach.
        /// </summary>
        private void TickShaft(Site s, float distance, PlayerFighter player)
        {
            if (distance > s.Radius) { _refusing.Remove(s.Id); return; }
            if (_exitCooldown > 0f) { return; }

            if (!WorldState.HasTalent(s.NeedsAbility))
            {
                if (_refusing.Add(s.Id)) { Game.AudioLibrary.Play("Exit_Sealed", s.Position); }
                return;
            }

            float height;
            if (!District.Floors.TryGetValue(s.ToLevel, out height)) { return; }
            Vector3 to = new Vector3(s.Position.x, height, s.Position.z);
            // Off the shaft's own radius, back toward the middle of the field.
            Vector3 away = -new Vector3(s.Position.x, 0f, s.Position.z).normalized;
            if (away.sqrMagnitude < 0.5f) { away = Vector3.forward; }
            to += away * (s.Radius + 1.5f);
            to = District.Bounds.Inset(2f).Clamp(to);

            Game.AudioLibrary.PlayUI("Exit_Travel");
            player.Teleport(to);
            CurrentLevel = s.ToLevel;
            _exitCooldown = 0.75f;
            PlayMusicForFloor();
            Debug.Log("[Ahmed] " + (s.ToLevel < 0 ? "down into the cellar of " : s.ToLevel > 0 ? "up onto the roofs of " : "back to the street of ")
                + District.DisplayName);
        }

        /// <summary>Put an encounter back to sleep: its bodies go, and it will
        /// wake again when he comes near. What a fight does when he leaves
        /// it, by walking away or by taking the stairs.</summary>
        private void Sleep(Site s)
        {
            List<EnemyFighter> live;
            if (_liveBySite.TryGetValue(s.Id, out live))
            {
                for (int i = 0; i < live.Count; i++)
                {
                    if (live[i] != null) { Object.Destroy(live[i].gameObject); }
                }
                live.Clear();
            }
            _awake.Remove(s.Id);
            if (_bossSite == s.Id) { _bossSite = -1; PlayMusicForFloor(); }
        }

        /// <summary>
        /// The hub: a save point and a place to spend what you have earned.
        ///
        /// Walking in writes the world down, banks where to come back to, and
        /// puts Ahmed back on his feet. Walking out closes the panel. It fires
        /// on the crossing rather than every frame -- a save point that writes
        /// sixty times a second while you stand on it is a stutter, not a
        /// feature -- and the heal is the reason to come back to it at all.
        /// </summary>
        private void TickHub(Site s, float distance, PlayerFighter player)
        {
            bool inside = distance <= s.Radius;
            if (inside == InHub) { return; }
            InHub = inside;
            if (!inside) { return; }

            WorldState.SetCheckpoint(District.AreaIndex, s.Position, 1f);
            player.Restore();
            SaveGame.Write();
            Game.AudioLibrary.PlayUI("Exp_Cache");
            Debug.Log("[Ahmed] saved at the hub in " + District.DisplayName
                + " — " + WorldState.Experience + " XP unspent.");
        }

        /// <summary>
        /// Ahmed went down. Before this the world simply stopped: the update
        /// returned early for as long as he was dead, so a lost fight was the
        /// end of the session. He comes back at the last save point now, and
        /// the encounter he lost is awake again because it was never cleared.
        /// </summary>
        private void Respawn(PlayerFighter player)
        {
            if (_respawning) { return; }
            _respawning = true;

            int area = WorldState.HasCheckpoint ? WorldState.CheckpointArea : District.AreaIndex;
            Vector3 at = WorldState.HasCheckpoint ? WorldState.CheckpointPosition : Vector3.zero;
            float health = WorldState.HasCheckpoint ? WorldState.CheckpointHealth : 1f;

            player.Revive(health);
            Game.AudioLibrary.PlayUI("Stage_Fail");
            Enter(area, at);
            player.Teleport(at);
            if (AreaChanged != null) { AreaChanged(area, District.DisplayName); }
            Debug.Log("[Ahmed] down. Back at the save point in " + District.DisplayName + ".");
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
                Game.AudioLibrary.PlayUI(_bossSite == s.Id ? "Stage_Clear" : "Wave_Clear");
                if (_bossSite == s.Id) { _bossSite = -1; PlayMusicForFloor(); }
                CheckAreaCleared();
                return;
            }

            // Walked away. The fight goes back to sleep rather than trailing
            // him across the district -- an open world where every encounter
            // you brush past follows you forever is unplayable.
            if (distance > s.Radius * 2.6f) { Sleep(s); }
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
            // A title fight is one with a boss in it: the music changes, and
            // changes back when he is down or when Ahmed leaves.
            if (IsTitleFight(s)) { _bossSite = s.Id; PlayMusicForFloor(); }
        }

        /// <summary>Whether a wave carries a boss archetype. Read off the
        /// roster rather than a flag on the wave, so it cannot disagree with
        /// what the roster says a boss is.</summary>
        public static bool IsTitleFight(Site s)
        {
            if (s == null || s.Wave == null || s.Wave.fighters == null) { return false; }
            for (int i = 0; i < s.Wave.fighters.Length; i++)
            {
                FighterRow row = GameData.Fighter(s.Wave.fighters[i]);
                if (row != null && row.boss) { return true; }
            }
            return false;
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
            at.y = site.Position.y;     // the site's own floor, not the world's

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

        /// <summary>The ring's gates read the street. A district is clear
        /// when its street is, whatever is still standing in its cellar or on
        /// its roofs -- those are inside the wheel, and the map's argument
        /// is made at street level.</summary>
        private void CheckAreaCleared()
        {
            for (int i = 0; i < District.Sites.Count; i++)
            {
                Site s = District.Sites[i];
                if (s.Kind != SiteKind.Encounter || s.Level != 0) { continue; }
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
            if (distance > s.Radius) { _refusing.Remove(s.Id); return; }
            if (_exitCooldown > 0f) { return; }

            WorldLink link = LinkFor(s);
            if (!WorldState.CanUse(link))
            {
                // Sealed. There is no HUD yet, so this is the only thing that
                // tells the player the route refused them rather than that
                // they missed the door. Once per approach: he has to step
                // away and come back to hear it again.
                if (_refusing.Add(s.Id)) { Game.AudioLibrary.Play("Exit_Sealed", s.Position); }
                return;
            }

            // Arrive at the far side of the district you came from, so walking
            // east and then west puts you back where you started.
            District next = District.Build(s.ToArea, GameData.Area(s.ToArea),
                                           GameData.Stage(s.ToArea), null);
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
