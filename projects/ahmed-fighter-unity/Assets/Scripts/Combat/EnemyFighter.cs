using System.Collections.Generic;
using UnityEngine;
using Ahmed.Data;

namespace Ahmed.Combat
{
    /// <summary>
    /// An enemy. Two rules make crowds fair rather than overwhelming: only a
    /// fixed number may attack at once (an "attack token"), and each holds its
    /// own lane and side so they surround the player instead of stacking.
    ///
    /// How it fights is a <see cref="FightStyleRunner"/> when the archetype
    /// names one. TickAI below is the fallback -- close and swing at random --
    /// and is what every archetype used to do.
    /// </summary>
    public class EnemyFighter : Fighter
    {
        public int ExperienceValue = 14;
        /// <summary>The archetype row this one was built from. Read-only, and
        /// it is what lets the pose tell a kickboxer from a grappler.</summary>
        public string Archetype { get; private set; }
        public bool IsBoss;
        public bool Enraged { get; private set; }

        /// <summary>Which side of the player to occupy: +1 ahead, -1 behind.</summary>
        public float FlankSide = 1f;
        /// <summary>Extra stand-off so several enemies do not share one spot.</summary>
        public float LaneOffset;
        /// <summary>Depth offset, so they spread across the strip.</summary>
        public float DepthOffset;

        public FightStyleRunner Style { get; private set; }

        private string[] _moves = new string[0];
        private float _preferredRange = 1.1f;
        private float _attackInterval = 1.55f;
        private float _guardChance = 0.12f;
        private bool _hitAndRun;

        private float _attackCooldown;
        private float _guardRollTimer;
        private float _guardRoll = 1f;
        private float _retreatRemaining;
        /// <summary>Where this one belongs. It fights around here and walks
        /// back if the player leads it away, so an encounter you brushed past
        /// does not follow you across the district.</summary>
        private Vector3 _home;
        private float _leash = float.PositiveInfinity;
        private bool _leashed;

        protected override void Awake()
        {
            base.Awake();
            // Made here rather than in the prefab so every enemy has one
            // whatever it was spawned from. It stays inert until an archetype
            // hands it a style.
            Style = gameObject.GetComponent<FightStyleRunner>();
            if (Style == null) { Style = gameObject.AddComponent<FightStyleRunner>(); }
        }

        /// <summary>Applies an archetype row plus the stage tier and difficulty.</summary>
        public void ConfigureFrom(FighterRow def, int tier, float difficultyHealth,
                                  float difficultyDamage)
        {
            Archetype = def.name;
            float tierBoost = 1f + tier * 0.10f;

            InitialiseVitals(Mathf.Max(1f, Mathf.Round(def.maxHealth * tierBoost * difficultyHealth)),
                             9999f);   // enemies are not stamina limited -- that is the player's problem

            PowerMultiplier = def.powerMultiplier * tierBoost * difficultyDamage;
            MoveSpeed = def.moveSpeed;
            _preferredRange = def.preferredRange;
            _attackInterval = def.attackInterval;
            _guardChance = def.guardChance;
            _hitAndRun = def.hitAndRun;
            IsBoss = def.boss;
            ResistsKnockdown = def.boss;
            ExperienceValue = def.experienceValue;
            _moves = def.moves != null ? def.moves : new string[0];

            // The style is what makes this archetype fight like itself rather
            // than like every other archetype.
            if (Style != null) { Style.Style = GameData.Style(def.fightStyle); }
        }

        public void SetEnemyArenaBounds(float minX, float maxX)
        {
            SetArenaBounds(minX, maxX);
        }

        /// <summary>Tie this fighter to a spot. Beyond the radius it stops
        /// chasing and walks home.</summary>
        public void Leash(Vector3 home, float radius)
        {
            _home = home;
            _leash = radius;
            _leashed = true;
        }

        /// <summary>Too far from home to keep fighting.</summary>
        public bool OutsideLeash
        {
            get
            {
                if (!_leashed) { return false; }
                Vector3 d = transform.position - _home;
                d.y = 0f;
                return d.magnitude > _leash;
            }
        }

        /// <summary>Walk back. Returns true while it is still doing so.</summary>
        public bool ReturnHome()
        {
            Vector3 d = _home - transform.position;
            d.y = 0f;
            if (d.magnitude < 1.5f) { return false; }
            Blocking = false;
            FaceTowards(_home);
            AddMovement(d.normalized, 0.8f);
            State = FighterState.Walk;
            return true;
        }

        public override void GatherTargets(List<Fighter> into)
        {
            PlayerFighter player = PlayerFighter.Current;
            if (player != null && player.IsAlive) { into.Add(player); }
        }

        protected override void Update()
        {
            base.Update();

            if (IsBoss && !Enraged && Health <= MaxHealth * 0.5f && IsAlive) { EnterPhaseTwo(); }

            // One or the other decides, never both: a styled fighter would
            // otherwise be pulled toward its flank spot by the plain AI while
            // the style tried to hold its range, and the two would cancel out
            // into a shuffle.
            if (IsAlive && !IsBusy && OutsideLeash && ReturnHome()) { return; }

            if (Style == null || !Style.IsDriving)
            {
                PlayerFighter player = PlayerFighter.Current;
                if (player != null && player.IsAlive && IsAlive && !IsBusy)
                {
                    TickAI(Time.deltaTime, player);
                }
            }
        }

        private void EnterPhaseTwo()
        {
            Enraged = true;
            PowerMultiplier *= 1.28f;
            _attackInterval *= 0.70f;
            MoveSpeed *= 1.20f;
            InvulnerableRemaining = 0.7f;
            Game.AudioLibrary.Play("Boss_Enrage", transform.position);

            // Phase two earns the finisher, and hurries whichever brain is
            // driving. The row is "Special": there has never been a "Rage" row
            // in the attack table.
            AddMove("Special");
            if (Style != null)
            {
                StyleStrike finisher = new StyleStrike();
                finisher.attackRow = "Special";
                finisher.bands = new string[] { "Mid", "Close" };
                finisher.weight = 0.8f;
                finisher.Resolve();
                Style.AddStrike(finisher);
                Style.Haste = 1f / 0.70f;
            }
        }

        private void AddMove(string row)
        {
            for (int i = 0; i < _moves.Length; i++)
            {
                if (_moves[i] == row) { return; }
            }
            string[] grown = new string[_moves.Length + 1];
            _moves.CopyTo(grown, 0);
            grown[_moves.Length] = row;
            _moves = grown;
        }

        /// <summary>The plain AI: hold a flank, close, swing at random. Used
        /// only by archetypes with no fight style.</summary>
        private void TickAI(float dt, PlayerFighter player)
        {
            _attackCooldown = Mathf.Max(0f, _attackCooldown - dt);
            _retreatRemaining = Mathf.Max(0f, _retreatRemaining - dt);

            _guardRollTimer -= dt;
            if (_guardRollTimer <= 0f)
            {
                _guardRollTimer = Random.Range(0.4f, 1.1f);
                _guardRoll = Random.value;
            }

            Vector3 self = transform.position;
            Vector3 target = player.transform.position;
            Vector3 delta = target - self;

            FaceTowards(target);

            Blocking = player.State == FighterState.Attack
                       && new Vector3(delta.x, 0f, delta.z).magnitude < 2.4f
                       && _guardRoll < _guardChance;

            Vector3 flat = new Vector3(delta.x, 0f, delta.z);
            bool inRange = flat.magnitude < _preferredRange * 0.95f;

            if (inRange && _attackCooldown <= 0f && _moves.Length > 0
                && player.State != FighterState.Down)
            {
                if (!CrowdControl.TryClaim(this)) { return; }
                if (StartAttack(_moves[Random.Range(0, _moves.Length)]))
                {
                    _attackCooldown = _attackInterval * Random.Range(0.75f, 1.45f);
                    if (_hitAndRun) { _retreatRemaining = Random.Range(0.7f, 1.2f); }
                }
                return;
            }

            // Hold a spot on the ring around the player rather than a point on
            // a line. FlankSide was which side of him to stand on when there
            // were only two; it is now which way round the ring to go, and the
            // lane offset spreads several enemies along it so they surround
            // rather than stack.
            Vector3 fromPlayer = self - target;
            fromPlayer.y = 0f;
            if (fromPlayer.sqrMagnitude < 0.01f) { fromPlayer = new Vector3(1f, 0f, 0f); }

            float ring = _preferredRange * 0.80f;
            if (_retreatRemaining > 0f) { ring = _preferredRange * 4.0f; }

            float baseAngle = Mathf.Atan2(fromPlayer.z, fromPlayer.x);
            float spread = FlankSide * (0.45f + LaneOffset * 0.35f);
            float angle = baseAngle + spread;
            Vector3 stand = target + new Vector3(Mathf.Cos(angle), 0f, Mathf.Sin(angle)) * ring;
            stand = Bounds.Inset(1.5f).Clamp(stand);

            Vector3 toDesired = stand - self;
            toDesired.y = 0f;

            if (toDesired.magnitude > 0.35f)
            {
                float scale = Blocking ? 0.4f : 1f;
                AddMovement(toDesired.normalized, scale);
                State = FighterState.Walk;
            }
            else if (State == FighterState.Walk)
            {
                State = FighterState.Idle;
            }
        }

        protected override void OnHitLanded(Fighter victim, HitResult hit)
        {
            // Whether the swing connected is the difference between pressing
            // the combination and paying for a miss, and only the hit
            // resolution knows.
            if (Style != null) { Style.NotifyHitLanded(); }
        }

        protected override void OnKnockedDown()
        {
            // Drop the token at once so someone else can press the attack.
            CrowdControl.Release(this);
        }

        protected override void OnDeath()
        {
            CrowdControl.Release(this);
        }
    }
}
