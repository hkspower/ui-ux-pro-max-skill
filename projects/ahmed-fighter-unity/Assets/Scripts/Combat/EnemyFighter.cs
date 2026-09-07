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
        private float _arenaMinX = float.NegativeInfinity;
        private float _arenaMaxX = float.PositiveInfinity;

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
            _arenaMinX = minX;
            _arenaMaxX = maxX;
            SetArenaBounds(minX, maxX);
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
                       && Mathf.Abs(delta.x) < 2.4f && _guardRoll < _guardChance;

            bool inRange = Mathf.Abs(delta.x) < _preferredRange * 0.95f
                           && Mathf.Abs(delta.z) < 0.7f;

            if (inRange && _attackCooldown <= 0f && _moves.Length > 0
                && player.State != FighterState.Down)
            {
                if (World.WaveDirector.Active != null
                    && !World.WaveDirector.Active.TryClaimAttackToken(this))
                {
                    return;
                }
                if (StartAttack(_moves[Random.Range(0, _moves.Length)]))
                {
                    _attackCooldown = _attackInterval * Random.Range(0.75f, 1.45f);
                    if (_hitAndRun) { _retreatRemaining = Random.Range(0.7f, 1.2f); }
                }
                return;
            }

            float desiredX = target.x + FlankSide * (_preferredRange * 0.70f + LaneOffset);
            if (_retreatRemaining > 0f) { desiredX = target.x + FlankSide * 6.6f; }

            // Never try to stand where the arena will not let you -- flip sides.
            if (desiredX < _arenaMinX + 0.5f || desiredX > _arenaMaxX - 0.5f)
            {
                FlankSide = -FlankSide;
                desiredX = target.x + FlankSide * (_preferredRange * 0.70f + LaneOffset);
            }
            if (Mathf.Abs(delta.x) > 9.5f) { desiredX = target.x; }

            float desiredZ = Mathf.Clamp(target.z + DepthOffset,
                                         Playfield.DepthMin, Playfield.DepthMax);
            Vector3 toDesired = new Vector3(desiredX - self.x, 0f, desiredZ - self.z);

            if (toDesired.magnitude > 0.2f)
            {
                Vector3 dir = toDesired.normalized;
                float scale = Blocking ? 0.4f : 1f;
                AddMovement(new Vector3(dir.x, 0f, dir.z), scale);
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
            if (World.WaveDirector.Active != null)
            {
                World.WaveDirector.Active.ReleaseAttackToken(this);
            }
        }

        protected override void OnDeath()
        {
            if (World.WaveDirector.Active != null)
            {
                World.WaveDirector.Active.ReleaseAttackToken(this);
            }
        }
    }
}
