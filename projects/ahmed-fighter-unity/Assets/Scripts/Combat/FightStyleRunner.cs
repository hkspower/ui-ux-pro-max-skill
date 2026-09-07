using System.Collections.Generic;
using UnityEngine;
using Ahmed.Data;

namespace Ahmed.Combat
{
    /// <summary>
    /// Makes a fighter fight like something in particular.
    ///
    /// The AI it stands in for does one thing regardless of archetype: hold a
    /// flank, close to a fixed distance, throw a move at random off a list.
    /// Every enemy therefore moves the same and chooses the same, and the only
    /// thing separating a kickboxer from a grappler is how much health each
    /// has. This asks four questions instead, and a style answers all four
    /// differently:
    ///
    ///   WHERE does it want to stand?  Range discipline. A range fighter
    ///     resets to its distance constantly; a pressure fighter walks in.
    ///   HOW does it get there?  Bouncing in and out, circling, or flat-footed
    ///     forward. Most of what a style looks like before anything is thrown.
    ///   WHAT does it throw?  Range-banded and weighted. A kickboxer teeps at
    ///     long and knees in close; a boxer has no answer at long, and that
    ///     absence is what makes him close rather than swing at air.
    ///   WHAT does it do after?  Reset, counter, or press.
    ///
    /// It throws through Fighter.StartAttack, the same door the plain AI uses,
    /// so a style can only ever do what an enemy could already do -- it
    /// decides, it does not add reach or damage or moves.
    /// </summary>
    public class FightStyleRunner : MonoBehaviour
    {
        public StyleRow Style;
        public Fighter Opponent;
        public bool Active = true;

        /// <summary>Multiplies the rhythm without touching the style row, which
        /// is shared by every fighter of the archetype for the whole session.</summary>
        public float Haste = 1f;

        /// <summary>True when this is the thing deciding, which is the signal
        /// for the fighter to leave its own AI alone.</summary>
        public bool IsDriving { get { return Active && Style != null; } }

        public RangeBand CurrentBand { get; private set; }

        /// <summary>Strikes gained beyond the style -- an enraged boss's
        /// finisher. Kept here rather than pushed into the shared style row.</summary>
        private readonly List<StyleStrike> _extra = new List<StyleStrike>();

        private Fighter _self;
        private float _attackCooldown;
        private int _comboRemaining;
        private float _resetRemaining;
        private float _acquireTimer;
        private bool _swingPending;
        private bool _wasAttacking;
        private float _circleDirection = 1f;
        private float _circleTimer;
        private float _bouncePhase;
        private float _guardRoll = 1f;
        private float _guardRollTimer;

        private void Awake()
        {
            _self = GetComponent<Fighter>();
            _circleDirection = Random.value < 0.5f ? 1f : -1f;
            // Stagger the first swing across a wave so five enemies do not
            // all throw on the frame they spawned.
            _attackCooldown = Random.Range(0.15f, 0.8f);
        }

        private void OnEnable()
        {
            if (_self != null) { _self.Damaged += HandleDamaged; }
        }

        private void OnDisable()
        {
            if (_self != null) { _self.Damaged -= HandleDamaged; }
        }

        public void AddStrike(StyleStrike strike)
        {
            if (strike == null || string.IsNullOrEmpty(strike.attackRow)) { return; }
            for (int i = 0; i < _extra.Count; i++)
            {
                if (_extra[i].attackRow == strike.attackRow) { return; }
            }
            _extra.Add(strike);
        }

        private void Update()
        {
            if (!IsDriving || _self == null || !_self.IsAlive) { return; }
            float dt = Time.deltaTime;

            _attackCooldown = Mathf.Max(0f, _attackCooldown - dt);
            _resetRemaining = Mathf.Max(0f, _resetRemaining - dt);
            _acquireTimer = Mathf.Max(0f, _acquireTimer - dt);

            // Runs even while busy: a swing ends during the busy window, and
            // whether it landed is decided there.
            TickSwingResult();

            if (Opponent == null || !Opponent.IsAlive || _acquireTimer <= 0f) { AcquireOpponent(); }
            if (Opponent == null) { return; }

            // Mid-swing, stunned or on the floor: not making decisions.
            // Ticking a style through those states is how AI queues three
            // strikes into a knockdown and throws them all on standing up.
            if (_self.IsBusy) { return; }

            Vector3 to = Opponent.transform.position - _self.transform.position;
            to.y = 0f;
            float distance = to.magnitude;

            CurrentBand = Style.BandFor(distance);
            _self.FaceTowards(Opponent.transform.position);

            TickDefence(dt, distance);
            TickOffence();
            TickFootwork(dt, to, distance);
        }

        private void AcquireOpponent()
        {
            _acquireTimer = 0.5f;
            List<Fighter> targets = new List<Fighter>();
            _self.GatherTargets(targets);

            float best = float.MaxValue;
            Fighter nearest = null;
            Vector3 origin = _self.transform.position;
            for (int i = 0; i < targets.Count; i++)
            {
                if (targets[i] == null || !targets[i].IsAlive) { continue; }
                Vector3 d = targets[i].transform.position - origin;
                d.y = 0f;
                float score = d.magnitude;
                if (score < best) { best = score; nearest = targets[i]; }
            }
            Opponent = nearest;
        }

        /// <summary>
        /// Footwork: hold the style's distance, circle rather than walk
        /// straight in, and bounce in and out if the style bounces. The bounce
        /// is what makes a points fighter look like one before he has thrown
        /// anything.
        /// </summary>
        private void TickFootwork(float dt, Vector3 to, float distance)
        {
            // Committed to a swing -- TickOffence may have started one a
            // moment ago in this same frame. Feet stay where they are: sliding
            // during startup is the single most common thing that makes a
            // fight look weightless.
            if (_self.State == FighterState.Attack) { return; }

            if (to.sqrMagnitude < 0.0001f) { return; }
            Vector3 towards = to.normalized;
            // Perpendicular in the ground plane: this is the circle.
            Vector3 around = new Vector3(-towards.z, 0f, towards.x);

            float wanted = Style.preferredRange;
            if (_resetRemaining > 0f && Style.resetDistance > 0f)
            {
                wanted = Style.resetDistance;           // backing off after committing
            }
            if (Style.bounceRate > 0f)
            {
                _bouncePhase += dt * Style.bounceRate * 2f * Mathf.PI;
                wanted += Mathf.Sin(_bouncePhase) * Style.bounceAmplitude;
            }

            // Close or back off, scaled by how much this style cares. A
            // pressure fighter barely corrects; a range fighter constantly.
            float error = distance - wanted;
            float urgency = Mathf.Lerp(0.35f, 1f, Style.rangeDiscipline);
            float forward = 0f;
            if (Mathf.Abs(error) > 0.18f)
            {
                forward = Mathf.Clamp(error / 1.2f, -1f, 1f) * urgency;
            }

            _circleTimer -= dt;
            if (_circleTimer <= 0f)
            {
                _circleTimer = Style.circleSwitchTime * Random.Range(0.6f, 1.5f);
                _circleDirection = Random.value < 0.5f ? 1f : -1f;
            }
            float sideways = Style.circleTendency * _circleDirection;

            // On the strip, circling was a step in depth and the walls were
            // two lines. In the open it is an orbit, and turning at the fence
            // means reversing the orbit rather than bouncing off a wall.
            Vector3 step = towards * forward + around * sideways;
            Vector3 ahead = _self.transform.position + step * 1.5f;
            if (!_self.Bounds.Inset(1.0f).Contains(ahead))
            {
                _circleDirection = -_circleDirection;
                sideways = -sideways;
                step = towards * forward + around * sideways;
            }

            float scale = _self.Blocking ? 0.45f : 1f;
            if (step.sqrMagnitude > 0.0001f)
            {
                _self.AddMovement(step.normalized, Mathf.Min(1f, step.magnitude) * scale);
            }
        }

        /// <summary>
        /// Range decides what is available; the style's weights decide which
        /// of those. If nothing is legal at this distance the fighter throws
        /// nothing and keeps walking.
        /// </summary>
        private void TickOffence()
        {
            if (_attackCooldown > 0f || CurrentBand == RangeBand.Out) { return; }
            if (Opponent == null || !Opponent.IsAlive) { return; }
            // Not while the opponent is on the floor. Hitting someone down is
            // both unfair and, in a crowd, unreadable.
            if (Opponent.State == FighterState.Down) { return; }

            // Mid-combination: keep going without asking the director again,
            // because the token was claimed for the whole combination.
            if (_comboRemaining > 0)
            {
                StyleStrike next = Style.ChooseStrike(CurrentBand, _extra);
                if (next != null && TryThrow(next))
                {
                    _comboRemaining--;
                    _attackCooldown = 0.06f;    // inside a combo the gap is the recovery
                    return;
                }
                _comboRemaining = 0;
            }

            // The crowd rule: only a couple may be swinging at once.
            if (_self is EnemyFighter && !CrowdControl.TryClaim(_self)) { return; }

            StyleStrike strike = Style.ChooseStrike(CurrentBand, _extra);
            if (strike == null)
            {
                _attackCooldown = 0.25f;        // wait a beat, do not re-roll every frame
                return;
            }
            if (!TryThrow(strike))
            {
                _attackCooldown = 0.2f;
                return;
            }

            // Openers start combinations; finishers stand alone.
            _comboRemaining = Random.value < strike.opensCombination
                ? Random.Range(1, Mathf.Max(2, Style.maxComboLength))
                : 0;

            float jitter = Random.Range(1f - Style.rhythmJitter, 1f + Style.rhythmJitter);
            _attackCooldown = Style.attackInterval * jitter / Mathf.Max(0.1f, Haste);

            if (Style.resetDistance > 0f) { _resetRemaining = Random.Range(0.6f, 1.1f); }
        }

        private bool TryThrow(StyleStrike strike)
        {
            if (!_self.StartAttack(strike.attackRow)) { return false; }
            _swingPending = true;
            return true;
        }

        /// <summary>
        /// The guard is rolled a few times a second rather than every frame:
        /// one that re-decides sixty times a second flickers instead of
        /// guarding, which looks like a bug and plays like one.
        /// </summary>
        private void TickDefence(float dt, float distance)
        {
            _guardRollTimer -= dt;
            if (_guardRollTimer <= 0f)
            {
                _guardRollTimer = Random.Range(0.35f, 0.9f);
                _guardRoll = Random.value;
            }

            bool threat = Opponent.State == FighterState.Attack
                          && distance < Style.preferredRange * 2f;

            bool advancing = distance > Style.preferredRange * 1.1f;
            if (advancing && !Style.guardsWhileAdvancing)
            {
                _self.Blocking = false;
                return;
            }
            _self.Blocking = threat && _guardRoll < Style.guardChance;
        }

        // ---------------------------------------------------------- reactions

        /// <summary>
        /// A swing ends whether or not it touched anybody, and the difference
        /// has to cost something. Without this an AI that misses simply throws
        /// again, which is how a fight becomes noise.
        /// </summary>
        private void TickSwingResult()
        {
            bool attacking = _self.State == FighterState.Attack;
            if (_wasAttacking && !attacking && _swingPending) { NotifyWhiffed(); }
            _wasAttacking = attacking;
        }

        private void HandleDamaged(Fighter self, HitResult hit)
        {
            if (Style == null) { return; }
            // Answering back is a decision, not a reflex: a style with a low
            // counter chance resets instead, and that is what makes it feel
            // like it respects the player rather than trading blindly.
            _comboRemaining = 0;
            _swingPending = false;              // interrupted, not missed

            if (Random.value < Style.counterChance)
            {
                _attackCooldown = 0f;           // fire the moment the stun ends
            }
            else
            {
                _attackCooldown = Mathf.Max(_attackCooldown,
                    Style.attackInterval * 0.6f / Mathf.Max(0.1f, Haste));
                _resetRemaining = Style.resetDistance > 0f ? 0.8f : 0f;
            }
        }

        public void NotifyHitLanded()
        {
            _swingPending = false;
            // Landing one earns the rest of the combination -- but a style
            // that hits and resets stops here instead.
            if (Style != null && Style.resetDistance > 0f && _comboRemaining <= 0)
            {
                _resetRemaining = Random.Range(0.6f, 1f);
            }
        }

        public void NotifyWhiffed()
        {
            _swingPending = false;
            _comboRemaining = 0;
            if (Style != null)
            {
                _attackCooldown = Mathf.Max(_attackCooldown,
                    Style.attackInterval * 0.75f / Mathf.Max(0.1f, Haste));
            }
        }
    }
}
