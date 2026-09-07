using System.Collections.Generic;
using UnityEngine;
using Ahmed.Data;

namespace Ahmed.Combat
{
    /// <summary>
    /// Ahmed. The jab-cross-hook chain, the dodge dash, the perfect parry and
    /// the rage finisher.
    ///
    /// Input is the legacy Input Manager on purpose: it needs no package, so
    /// the project opens and plays in a bare Unity install. Swapping it for
    /// the Input System is a change to this one file.
    /// </summary>
    public class PlayerFighter : Fighter
    {
        /// <summary>There is exactly one, and everything else looks for it here
        /// rather than searching the scene every frame.</summary>
        public static PlayerFighter Current { get; private set; }

        public float Mana { get; private set; }
        public float MaxMana { get; private set; }
        public float Rage { get; private set; }
        public bool RageReady { get { return Rage >= Playfield.RageMax; } }

        private PlayerRow _row;
        private int _chainIndex;
        private float _chainWindow;
        private float _dashRemaining;
        private float _dashCooldown;

        private static readonly string[] Chain = { "Jab", "Cross", "Hook" };

        protected override void Awake()
        {
            base.Awake();
            Current = this;

            _row = GameData.Player;
            InitialiseVitals(_row.baseHealth > 0f ? _row.baseHealth : 100f,
                             _row.baseStamina > 0f ? _row.baseStamina : 100f);
            MaxMana = _row.baseMana;
            Mana = _row.baseMana;
            PowerMultiplier = _row.basePower > 0f ? _row.basePower : 1f;
            MoveSpeed = _row.baseMoveSpeed > 0f ? _row.baseMoveSpeed : 3.4f;
        }

        private void OnDestroy()
        {
            if (Current == this) { Current = null; }
        }

        public override void GatherTargets(List<Fighter> into)
        {
            EnemyFighter[] enemies = Object.FindObjectsByType<EnemyFighter>(FindObjectsSortMode.None);
            for (int i = 0; i < enemies.Length; i++)
            {
                if (enemies[i].IsAlive) { into.Add(enemies[i]); }
            }
        }

        protected override void Update()
        {
            base.Update();
            float dt = Time.deltaTime;

            Mana = Mathf.Min(MaxMana, Mana + _row.manaRegenPerSecond * dt);
            _chainWindow = Mathf.Max(0f, _chainWindow - dt);
            _dashCooldown = Mathf.Max(0f, _dashCooldown - dt);
            if (_chainWindow <= 0f) { _chainIndex = 0; }

            if (_dashRemaining > 0f)
            {
                _dashRemaining -= dt;
                AddMovement(Facing, 2.4f);
                if (_dashRemaining <= 0f && State == FighterState.Dash)
                {
                    State = FighterState.Idle;
                }
                return;
            }

            ReadInput(dt);
        }

        private void ReadInput(float dt)
        {
            if (!IsAlive) { return; }

            bool block = Input.GetButton("Fire3") || Input.GetKey(KeyCode.LeftShift);
            if (block && !Blocking && !IsBusy)
            {
                // The window opens the frame the guard goes up: a hit inside
                // it is a parry, not a block. That is the whole skill of it.
                ParryWindowRemaining = Playfield.ParryWindow;
            }
            Blocking = block && !IsBusy;

            float moveX = Input.GetAxisRaw("Horizontal");
            float moveZ = Input.GetAxisRaw("Vertical");

            // Movement is measured against the camera, not the world.
            //
            // On the strip it did not have to be: the camera never turned, so
            // "right" was +X for the whole game. In a district the camera
            // swings, and pushing the stick away from you has to mean away
            // from you on screen or the world becomes unnavigable the first
            // time you turn a corner.
            Vector3 basisF = Vector3.forward, basisR = Vector3.right;
            if (Game.FollowCamera.Current != null)
            {
                basisF = Game.FollowCamera.Current.Forward;
                basisR = Game.FollowCamera.Current.Right;
            }
            Vector3 wish = basisR * moveX + basisF * moveZ;
            if (wish.sqrMagnitude > 1f) { wish = wish.normalized; }

            if (!IsBusy)
            {
                if (Input.GetButtonDown("Fire1")) { Punch(); return; }
                if (Input.GetButtonDown("Fire2")) { Kick(); return; }
                if (Input.GetKeyDown(KeyCode.R) && RageReady) { ReleaseRage(); return; }
                if (Input.GetKeyDown(KeyCode.Space) && _dashCooldown <= 0f
                    && wish.sqrMagnitude > 0.01f)
                {
                    Dash(wish);
                    return;
                }

                if (wish.sqrMagnitude > 0.01f)
                {
                    float scale = Blocking ? 0.45f : 1f;
                    AddMovement(wish, scale);
                    // Face where you are going, unless something is close
                    // enough to be what you actually mean to hit.
                    FaceTowards(transform.position + wish);
                    State = FighterState.Walk;
                }
                else if (State == FighterState.Walk)
                {
                    State = FighterState.Idle;
                }
            }
        }

        /// <summary>
        /// Jab becomes cross becomes hook, if the button comes again inside
        /// the window. Outside it the chain resets to the jab, which is what
        /// stops mashing from being the best strategy.
        /// </summary>
        private void Punch()
        {
            FaceNearestOpponent();
            string row = Chain[Mathf.Clamp(_chainIndex, 0, Chain.Length - 1)];
            if (StartAttack(row))
            {
                _chainIndex = (_chainIndex + 1) % Chain.Length;
                _chainWindow = Playfield.ComboWindow;
            }
        }

        private void Kick()
        {
            FaceNearestOpponent();
            // A knee inside, a roundhouse outside. Throwing a roundhouse from
            // the clinch is a roundhouse that jams.
            bool close = false;
            List<Fighter> targets = new List<Fighter>();
            GatherTargets(targets);
            for (int i = 0; i < targets.Count; i++)
            {
                Vector3 d = targets[i].transform.position - transform.position;
                d.y = 0f;
                if (d.magnitude < 1.0f) { close = true; break; }
            }
            StartAttack(close ? "Knee" : "Kick");
        }

        private void Dash(Vector3 wish)
        {
            State = FighterState.Dash;
            _dashRemaining = 0.18f;
            _dashCooldown = 0.6f;
            InvulnerableRemaining = 0.18f;   // the dodge is the point of it
            SpendStamina(12f);
            FaceTowards(transform.position + wish);
        }

        private void ReleaseRage()
        {
            FaceNearestOpponent();
            if (StartAttack("Special"))
            {
                Rage = 0f;
                InvulnerableRemaining = 0.55f;
            }
        }

        public override float OutgoingDamageMultiplier(AttackRow attack)
        {
            return PowerMultiplier;
        }

        protected override void OnHitLanded(Fighter victim, HitResult hit)
        {
            if (hit.blocked || hit.damage <= 0f) { return; }
            Rage = Mathf.Min(Playfield.RageMax, Rage + hit.damage * 0.6f);
            Mana = Mathf.Min(MaxMana, Mana + _row.manaPerLandedHit);
        }

        protected override void OnParried(Fighter attacker)
        {
            // A parry is worth more than a landed hit: it is the only thing
            // in the game that rewards reading rather than pressing.
            Rage = Mathf.Min(Playfield.RageMax, Rage + 18f);
            if (attacker != null) { attacker.ReceiveKnockback(attacker.Facing * -2.2f, false); }
        }
    }
}
