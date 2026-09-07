using System.Collections.Generic;
using UnityEngine;
using Ahmed.Data;

namespace Ahmed.Combat
{
    /// <summary>
    /// Everything the player and the enemies share: the attack state machine,
    /// health, stamina, blocking, knockdown and hit resolution.
    ///
    /// Hits are resolved by an explicit facing/reach/depth test against the
    /// other fighters rather than by physics overlaps. That is deliberate and
    /// it is what both of the other builds do: the results are frame
    /// deterministic, and a beat-'em-up wants forgiving readable hitboxes
    /// rather than physically exact ones. A trigger volume would also make
    /// every strike depend on collider setup, which is exactly the kind of
    /// thing that goes wrong silently in a scene.
    /// </summary>
    [RequireComponent(typeof(CharacterController))]
    public abstract class Fighter : MonoBehaviour
    {
        // ------------------------------------------------------------ state

        public FighterState State { get; protected set; }
        public float Health { get; protected set; }
        public float MaxHealth { get; protected set; }
        public float Stamina { get; protected set; }
        public float MaxStamina { get; protected set; }

        public float PowerMultiplier = 1f;
        public float MoveSpeed = 3.4f;
        public bool Blocking;
        /// <summary>Bosses shrug most knockdowns off so they cannot be stunlocked.</summary>
        public bool ResistsKnockdown;

        /// <summary>+1 facing along +X, -1 facing back along it.</summary>
        public float FacingSign { get; protected set; }

        public bool IsAlive { get { return State != FighterState.Dead; } }
        public float HealthFraction { get { return MaxHealth > 0f ? Health / MaxHealth : 0f; } }

        /// <summary>Mid-swing, stunned, floored or dead: taking no new orders.</summary>
        public bool IsBusy
        {
            get
            {
                return State == FighterState.Attack || State == FighterState.Hit
                    || State == FighterState.Down || State == FighterState.Dead;
            }
        }

        public event System.Action<Fighter, HitResult> Damaged;
        public event System.Action<Fighter> Defeated;

        // --------------------------------------------------------- internals

        protected CharacterController Body;
        protected AttackRow CurrentAttack;
        protected float AttackElapsed;
        protected bool AttackHitFired;
        protected readonly List<Fighter> HitThisSwing = new List<Fighter>();

        protected float HitStunRemaining;
        protected float DownRemaining;
        protected float InvulnerableRemaining;
        protected float ParryWindowRemaining;

        private float _minX = float.NegativeInfinity;
        private float _maxX = float.PositiveInfinity;
        private Vector3 _pendingMove;

        protected virtual void Awake()
        {
            Body = GetComponent<CharacterController>();
            FacingSign = 1f;
            State = FighterState.Idle;
        }

        public void SetArenaBounds(float minX, float maxX)
        {
            _minX = minX;
            _maxX = maxX;
        }

        /// <summary>Travel carries condition across, so an area change does not heal.</summary>
        public void SetCondition(float health, float stamina)
        {
            Health = Mathf.Clamp(health, 1f, MaxHealth);
            Stamina = Mathf.Clamp(stamina, 0f, MaxStamina);
        }

        protected void InitialiseVitals(float maxHealth, float maxStamina)
        {
            MaxHealth = maxHealth;
            Health = maxHealth;
            MaxStamina = maxStamina;
            Stamina = maxStamina;
        }

        // ------------------------------------------------------------- tick

        protected virtual void Update()
        {
            float dt = Time.deltaTime;

            TickTimers(dt);
            if (State == FighterState.Attack) { TickAttack(dt); }

            // Blocking drains stamina; everything else refills it.
            float regen = Blocking ? -13f : Playfield.StaminaRegenPerSecond;
            Stamina = Mathf.Clamp(Stamina + regen * dt, 0f, MaxStamina);
        }

        /// <summary>
        /// Movement is accumulated during Update and applied once here.
        ///
        /// CharacterController.Move is not additive -- calling it twice in a
        /// frame runs two separate sweeps and the second one starts from where
        /// the first left off, which quietly doubles diagonal speed. The AI
        /// asks for its along-stage and depth motion separately, so it has to
        /// be summed before it is spent.
        /// </summary>
        protected virtual void LateUpdate()
        {
            if (Body == null) { return; }

            Vector3 step = _pendingMove;
            _pendingMove = Vector3.zero;
            step.y = Body.isGrounded ? -0.5f * Time.deltaTime : -9.81f * Time.deltaTime;
            Body.Move(step);

            Vector3 p = transform.position;
            p.x = Mathf.Clamp(p.x, _minX, _maxX);
            p.z = Mathf.Clamp(p.z, Playfield.DepthMin, Playfield.DepthMax);
            transform.position = p;
        }

        /// <summary>Ask for movement this frame. Scale is -1..1 per axis.</summary>
        public void AddMovement(Vector3 direction, float scale)
        {
            _pendingMove += direction.normalized * (MoveSpeed * scale * Time.deltaTime);
        }

        protected void TickTimers(float dt)
        {
            InvulnerableRemaining = Mathf.Max(0f, InvulnerableRemaining - dt);
            ParryWindowRemaining = Mathf.Max(0f, ParryWindowRemaining - dt);

            if (State == FighterState.Hit)
            {
                HitStunRemaining -= dt;
                if (HitStunRemaining <= 0f) { State = FighterState.Idle; }
            }
            else if (State == FighterState.Down)
            {
                DownRemaining -= dt;
                if (DownRemaining <= 0f)
                {
                    if (Health <= 0f)
                    {
                        Die();
                    }
                    else
                    {
                        State = FighterState.Idle;
                        InvulnerableRemaining = 0.6f;   // brief mercy on getting up
                    }
                }
            }
        }

        // ----------------------------------------------------------- attacks

        /// <summary>Begins an attack if the state allows it. False if refused.</summary>
        public bool StartAttack(string row)
        {
            if (IsBusy || State == FighterState.Dash) { return false; }

            AttackRow attack = GameData.Attack(row);
            if (attack == null) { return false; }
            if (Stamina < attack.staminaCost) { return false; }

            Stamina -= attack.staminaCost;
            CurrentAttack = attack;
            AttackElapsed = 0f;
            AttackHitFired = false;
            Blocking = false;
            HitThisSwing.Clear();
            State = FighterState.Attack;
            OnAttackStarted(attack);
            return true;
        }

        protected void TickAttack(float dt)
        {
            if (CurrentAttack == null)
            {
                State = FighterState.Idle;
                return;
            }
            AttackElapsed += dt;

            float activeStart = CurrentAttack.startup;
            float activeEnd = CurrentAttack.startup + CurrentAttack.active;

            if (AttackElapsed >= activeStart && AttackElapsed < activeEnd)
            {
                // Step into the strike, the way a fighter closes on a
                // committed blow. Without it every attack looks like it is
                // thrown by someone standing still.
                float lunge = CurrentAttack.heavy ? 1.65f : 1.20f;
                _pendingMove += new Vector3(FacingSign, 0f, 0f) * (lunge * dt);

                if (!AttackHitFired || CurrentAttack.multiHit)
                {
                    ResolveHits(CurrentAttack);
                }
            }

            if (AttackElapsed >= CurrentAttack.TotalTime)
            {
                CurrentAttack = null;
                State = FighterState.Idle;
            }
        }

        /// <summary>
        /// The hitbox. The playfield is a strip: X runs along the stage and Z
        /// is depth, so a strike reaches forward along X and tolerates a band
        /// in Z -- which is why two fighters a metre apart in depth do not
        /// trade blows.
        /// </summary>
        protected virtual void ResolveHits(AttackRow attack)
        {
            List<Fighter> targets = new List<Fighter>();
            GatherTargets(targets);

            Vector3 origin = transform.position;
            for (int i = 0; i < targets.Count; i++)
            {
                Fighter target = targets[i];
                if (target == null || !target.IsAlive) { continue; }
                if (target.State == FighterState.Down) { continue; }
                if (target.InvulnerableRemaining > 0f) { continue; }
                if (HitThisSwing.Contains(target)) { continue; }

                Vector3 delta = target.transform.position - origin;

                // In front of the attacker, within reach, and on the same
                // depth line. The -0.6 lets a strike still land on someone who
                // has walked a little past you, which is forgiving on purpose.
                float forward = delta.x * FacingSign;
                if (forward < -0.6f || forward > attack.reach + 0.6f) { continue; }
                if (Mathf.Abs(delta.z) > attack.depthTolerance) { continue; }

                HitThisSwing.Add(target);
                AttackHitFired = true;

                HitResult hit = target.ReceiveHit(this, attack);
                OnHitLanded(target, hit);

                if (!attack.multiHit) { return; }
            }
        }

        /// <summary>Damage this fighter deals, before the victim's defences.</summary>
        public virtual float OutgoingDamageMultiplier(AttackRow attack)
        {
            return PowerMultiplier;
        }

        /// <summary>Applies a landed blow. Called by the attacker, not the victim.</summary>
        public HitResult ReceiveHit(Fighter attacker, AttackRow attack)
        {
            HitResult result = new HitResult();
            result.impactPoint = transform.position + Vector3.up * 1.2f;

            if (!IsAlive || InvulnerableRemaining > 0f || attacker == null) { return result; }

            // A parry is a block inside the window that opened the frame the
            // guard went up. It costs the attacker, not the defender.
            bool facingIt = Mathf.Sign(attacker.transform.position.x - transform.position.x)
                            == Mathf.Sign(FacingSign) || Blocking;
            if (Blocking && facingIt && ParryWindowRemaining > 0f)
            {
                result.parried = true;
                result.blocked = true;
                InvulnerableRemaining = 0.25f;
                OnParried(attacker);
                if (Damaged != null) { Damaged(this, result); }
                return result;
            }

            float damage = attack.damage * attacker.OutgoingDamageMultiplier(attack);

            if (Blocking && facingIt)
            {
                result.blocked = true;
                result.damage = damage * Playfield.BlockDamageMultiplier;
                Health = Mathf.Max(0f, Health - result.damage);
                Stamina = Mathf.Max(0f, Stamina - 14f);
                if (Damaged != null) { Damaged(this, result); }
                if (Health <= 0f) { Die(); }
                return result;
            }

            result.damage = damage;
            Health = Mathf.Max(0f, Health - damage);

            bool knockdown = attack.multiHit || (attack.heavy && Random.value < 0.45f);
            ReceiveKnockback(new Vector3(attacker.FacingSign * attack.knockback, 0f, 0f),
                             knockdown || Health <= 0f);
            result.knockdown = knockdown;
            result.killed = Health <= 0f;

            if (Damaged != null) { Damaged(this, result); }
            return result;
        }

        /// <summary>Take the blow's push, and go down if it was heavy enough.</summary>
        public void ReceiveKnockback(Vector3 impulse, bool knockdown)
        {
            if (!IsAlive) { return; }
            _pendingMove += impulse * Time.deltaTime;

            if (knockdown && (!ResistsKnockdown || Health <= 0f))
            {
                State = FighterState.Down;
                DownRemaining = 0.85f;
                OnKnockedDown();
            }
            else
            {
                State = FighterState.Hit;
                HitStunRemaining = 0.22f;
            }
        }

        public void SpendStamina(float amount)
        {
            Stamina = Mathf.Max(0f, Stamina - amount);
        }

        protected void Die()
        {
            if (State == FighterState.Dead) { return; }
            State = FighterState.Dead;
            Health = 0f;
            OnDeath();
            if (Defeated != null) { Defeated(this); }
        }

        // ---------------------------------------------------------- facing

        public void FaceTowards(Vector3 worldPosition)
        {
            float dx = worldPosition.x - transform.position.x;
            if (Mathf.Abs(dx) > 0.05f) { FacingSign = Mathf.Sign(dx); }
            transform.rotation = Quaternion.Euler(0f, FacingSign > 0f ? 90f : -90f, 0f);
        }

        public void FaceNearestOpponent()
        {
            List<Fighter> targets = new List<Fighter>();
            GatherTargets(targets);

            float best = float.MaxValue;
            Fighter nearest = null;
            Vector3 origin = transform.position;
            for (int i = 0; i < targets.Count; i++)
            {
                if (targets[i] == null || !targets[i].IsAlive) { continue; }
                Vector3 d = targets[i].transform.position - origin;
                // Depth counts double: someone two metres in front is a better
                // guess at the intended target than one beside you in Z.
                float score = Mathf.Abs(d.x) + Mathf.Abs(d.z) * 2f;
                if (score < best) { best = score; nearest = targets[i]; }
            }
            if (nearest != null) { FaceTowards(nearest.transform.position); }
        }

        // -------------------------------------------------------- overrides

        /// <summary>Everyone this fighter is allowed to hit. Subclasses narrow it.</summary>
        public abstract void GatherTargets(List<Fighter> into);

        protected virtual void OnAttackStarted(AttackRow attack) { }
        protected virtual void OnHitLanded(Fighter victim, HitResult hit) { }
        protected virtual void OnParried(Fighter attacker) { }
        protected virtual void OnKnockedDown() { }
        protected virtual void OnDeath() { }
    }
}
