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

        /// <summary>
        /// Which way this fighter is looking, as a unit vector in the ground
        /// plane. It used to be a sign on X, because the playfield was a strip
        /// and there were only two directions to face. In an open district
        /// there are all of them, and every reach, lunge and knockback below
        /// is measured along this rather than along the world axis.
        /// </summary>
        public Vector3 Facing { get; protected set; }

        public bool IsAlive { get { return State != FighterState.Dead; } }

        /// <summary>The attack being thrown, and how far into it. Read-only,
        /// for whatever draws the pose from the fight rather than the other
        /// way round.</summary>
        public AttackRow ActiveAttack { get { return CurrentAttack; } }
        public float AttackTime { get { return AttackElapsed; } }
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
        /// <summary>The swing's sound, and when in the attack to fire it. The
        /// clip is started early by its own lead so the swish peaks on the
        /// first active frame; a swing that is interrupted first never
        /// sounds, because it never happened.</summary>
        private string _swingCue;
        private float _swingAt;
        private bool _swingFired;
        protected readonly List<Fighter> HitThisSwing = new List<Fighter>();

        protected float HitStunRemaining;
        protected float DownRemaining;
        protected float InvulnerableRemaining;
        protected float ParryWindowRemaining;

        /// <summary>Where this fighter may stand. Set by whatever owns the
        /// space -- a district, or an arena while a wave is live.</summary>
        public Ahmed.World.Bounds2D Bounds = Ahmed.World.Bounds2D.Unbounded;
        private Vector3 _pendingMove;

        protected virtual void Awake()
        {
            Body = GetComponent<CharacterController>();
            Facing = Vector3.right;
            State = FighterState.Idle;
        }

        public void SetArenaBounds(float minX, float maxX)
        {
            Bounds = new Ahmed.World.Bounds2D(minX, maxX,
                                              Playfield.DepthMin, Playfield.DepthMax);
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

            // Bounds are a rectangle now, not a strip with a fixed depth
            // band. A district sets them when the player walks into it.
            Vector3 p = transform.position;
            p.x = Mathf.Clamp(p.x, Bounds.MinX, Bounds.MaxX);
            p.z = Mathf.Clamp(p.z, Bounds.MinZ, Bounds.MaxZ);
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

        /// <summary>Begins an attack if the state allows it. False if refused.
        /// The swing cue defaults to the whoosh for the row's weight; the
        /// finisher passes its own.</summary>
        public bool StartAttack(string row, string swingCue = null)
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

            // The swing is heard before it lands, which is what gives the
            // player something to react to. Heavy and light are separate cues
            // because the wind-up is the tell. The clip is not played here:
            // its swish sits some way into the file, so it is scheduled to
            // start that much before the first active frame and peaks on it.
            _swingCue = swingCue ?? (attack.heavy ? "Whoosh_Heavy" : "Whoosh_Light");
            _swingAt = SwingCueTime(attack.startup, Game.AudioLibrary.Lead(_swingCue));
            _swingFired = false;
            if (_swingAt <= 0f) { FireSwingCue(); }
            return true;
        }

        /// <summary>When into an attack to start its swing clip so the clip's
        /// transient lands on the first active frame. Pure, so it can be
        /// checked without an engine: never negative, and startup minus lead
        /// whenever the lead fits inside the startup.</summary>
        public static float SwingCueTime(float startup, float lead)
        {
            return Mathf.Max(0f, startup - lead);
        }

        private void FireSwingCue()
        {
            if (_swingFired) { return; }
            _swingFired = true;
            Game.AudioLibrary.Play(_swingCue, transform.position);
        }

        protected void TickAttack(float dt)
        {
            if (CurrentAttack == null)
            {
                State = FighterState.Idle;
                return;
            }
            AttackElapsed += dt;
            if (!_swingFired && AttackElapsed >= _swingAt) { FireSwingCue(); }

            float activeStart = CurrentAttack.startup;
            float activeEnd = CurrentAttack.startup + CurrentAttack.active;

            if (AttackElapsed >= activeStart && AttackElapsed < activeEnd)
            {
                // Step into the strike, the way a fighter closes on a
                // committed blow. Without it every attack looks like it is
                // thrown by someone standing still.
                float lunge = CurrentAttack.heavy ? 1.65f : 1.20f;
                _pendingMove += Facing * (lunge * dt);

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
        /// The hitbox.
        ///
        /// A strike reaches forward along the direction the fighter is facing
        /// and tolerates a band either side of that line. On the strip those
        /// were the world's own X and Z, which is why the numbers are called
        /// reach and depth tolerance; here they are the same two numbers taken
        /// along and across the facing vector instead. Someone a metre off
        /// your line still does not get hit, which is the property the whole
        /// game's spacing was tuned around.
        ///
        /// Still an explicit test rather than a physics overlap, for the same
        /// reason as in the other two builds: the results are frame
        /// deterministic, and a beat-'em-up wants forgiving readable hitboxes
        /// rather than physically exact ones.
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

                if (!InHitbox(origin, Facing, target.transform.position,
                              attack.reach, attack.depthTolerance))
                {
                    continue;
                }

                HitThisSwing.Add(target);
                AttackHitFired = true;

                HitResult hit = target.ReceiveHit(this, attack);
                OnHitLanded(target, hit);

                if (!attack.multiHit) { return; }
            }
        }

        /// <summary>
        /// Is a point inside the strike's box? Along the facing line for
        /// reach, across it for tolerance.
        ///
        /// Static and free of the character on purpose: this is the one piece
        /// of the fight that is pure geometry, it is the piece that changed
        /// when the strip became a field, and lifting it out is what lets it
        /// be tested without an engine. The property that has to hold is that
        /// it does not care which way the pair is pointing -- rotate attacker
        /// and target together and the answer must not move, or the fight is
        /// harder facing some directions than others.
        /// </summary>
        public static bool InHitbox(Vector3 origin, Vector3 facing, Vector3 target,
                                    float reach, float lateralTolerance)
        {
            Vector3 delta = target - origin;
            delta.y = 0f;

            // The -0.6 lets a strike still land on someone who has stepped a
            // little past you, which is forgiving on purpose.
            float forward = Vector3.Dot(delta, facing);
            if (forward < -0.6f || forward > reach + 0.6f) { return false; }

            Vector3 lateral = delta - facing * forward;
            return lateral.magnitude <= lateralTolerance;
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
            //
            // You can only block what is in front of you. On the strip that
            // was a sign comparison; in the open it is the front hemisphere,
            // which is what stops a guard from covering your back.
            Vector3 fromAttacker = attacker.transform.position - transform.position;
            fromAttacker.y = 0f;
            bool facingIt = Vector3.Dot(fromAttacker.normalized, Facing) > 0f;
            if (Blocking && facingIt && ParryWindowRemaining > 0f)
            {
                result.parried = true;
                result.blocked = true;
                InvulnerableRemaining = 0.25f;
                Game.AudioLibrary.Play("Parry", result.impactPoint);
                OnParried(attacker);
                if (Damaged != null) { Damaged(this, result); }
                return result;
            }

            float damage = attack.damage * attacker.OutgoingDamageMultiplier(attack);

            if (Blocking && facingIt)
            {
                result.blocked = true;
                result.damage = damage * Playfield.BlockDamageMultiplier;
                Game.AudioLibrary.Play("Block", result.impactPoint);
                Health = Mathf.Max(0f, Health - result.damage);
                Stamina = Mathf.Max(0f, Stamina - 14f);
                if (Damaged != null) { Damaged(this, result); }
                if (Health <= 0f) { Die(); }
                return result;
            }

            result.damage = damage;
            Health = Mathf.Max(0f, Health - damage);

            bool knockdown = attack.multiHit || (attack.heavy && Random.value < 0.45f);
            bool wentDown = knockdown || Health <= 0f;
            // Knockdown, heavy or light -- one sound per blow, and the one
            // that puts a fighter down is its own so the player can hear the
            // difference.
            Game.AudioLibrary.Play(wentDown ? "Hit_Knockdown"
                : attack.heavy ? "Hit_Heavy" : "Hit_Light", result.impactPoint);
            ReceiveKnockback(attacker.Facing * attack.knockback, wentDown);
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

            // Either way the swing this fighter was in is over. A whoosh that
            // has not started yet must not start now for a punch that was
            // never thrown.
            _swingFired = true;

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
            Game.AudioLibrary.Play("KO", transform.position);
            OnDeath();
            if (Defeated != null) { Defeated(this); }
        }

        // ---------------------------------------------------------- facing

        public void FaceTowards(Vector3 worldPosition)
        {
            Vector3 d = worldPosition - transform.position;
            d.y = 0f;
            if (d.sqrMagnitude < 0.0025f) { return; }   // too close to mean anything
            Facing = d.normalized;
            transform.rotation = Quaternion.LookRotation(Facing, Vector3.up);
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
                d.y = 0f;
                // Nearest, but someone already in front counts as nearer than
                // someone the same distance behind: turning round to punch a
                // person at your back is not what the player meant.
                float score = d.magnitude - Vector3.Dot(d.normalized, Facing) * 0.9f;
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
