using UnityEngine;
using Ahmed.Combat;

namespace Ahmed.Game
{
    /// <summary>
    /// The camera. Trails the player on a boom he swings himself, at a pitch
    /// he sets, and comes in close when the boom would put it inside
    /// something.
    ///
    /// It has to turn, and that is the change that makes the district an open
    /// space rather than a wide corridor: on the strip the camera looked one
    /// way for the whole game and "forward" was a world axis. Here forward is
    /// whatever the camera is pointing at, which is why
    /// <see cref="PlayerFighter"/> reads its movement basis off this.
    ///
    /// Once the district had buildings in it, two more things became
    /// necessary. A boom that ignores them spends half of a fight inside a
    /// wall looking at the inside of a stall, so it is swept and pulled in to
    /// the first thing it hits. And a fixed pitch cannot see a man standing
    /// on a roof or down a stair, so the pitch is the player's.
    ///
    /// Mouse and gamepad both: the right stick is <c>Mouse X/Y</c> on the
    /// legacy input manager's default bindings, and Q and E stay for a
    /// keyboard with no mouse look.
    /// </summary>
    public class FollowCamera : MonoBehaviour
    {
        /// <summary>The one the player's input is measured against.</summary>
        public static FollowCamera Current { get; private set; }

        public Transform Target;
        /// <summary>How far back the boom reaches when nothing is in the way.</summary>
        public float Distance = 11f;
        /// <summary>Where on the body the boom is anchored: chest height, so
        /// the camera looks at him rather than over him.</summary>
        public float ShoulderHeight = 1.5f;
        public float TurnSpeed = 150f;
        public float PitchSpeed = 90f;
        public float MinPitch = -4f;
        public float MaxPitch = 62f;
        public float Damping = 9f;
        /// <summary>How far off a wall the camera stops. Less than this and
        /// the near plane clips through it.</summary>
        public float WallMargin = 0.35f;
        public bool InvertPitch;

        private float _yaw;
        private float _pitch = 26f;
        private float _distance = 11f;

        private void Awake()
        {
            Current = this;
            _yaw = 0f;
            _distance = Distance;
        }

        private void OnDestroy()
        {
            if (Current == this) { Current = null; }
        }

        /// <summary>Flat forward and right, for turning stick input into a
        /// direction in the world. Flat on purpose: pitch is what the camera
        /// does, not what walking does.</summary>
        public Vector3 Forward
        {
            get
            {
                float r = _yaw * Mathf.Deg2Rad;
                return new Vector3(Mathf.Sin(r), 0f, Mathf.Cos(r));
            }
        }

        public Vector3 Right
        {
            get
            {
                float r = _yaw * Mathf.Deg2Rad;
                return new Vector3(Mathf.Cos(r), 0f, -Mathf.Sin(r));
            }
        }

        /// <summary>
        /// Where the boom wants to be, and where it may actually go.
        ///
        /// Kept static and free of the scene so the geometry can be executed
        /// and checked without an editor, the way the IK is: give it the
        /// anchor, the angles and how far the sweep says it may reach, and it
        /// answers with the camera's position.
        /// </summary>
        public static Vector3 BoomPosition(Vector3 anchor, float yaw, float pitch, float distance)
        {
            float y = yaw * Mathf.Deg2Rad, p = pitch * Mathf.Deg2Rad;
            float flat = Mathf.Cos(p) * distance;
            return new Vector3(anchor.x - Mathf.Sin(y) * flat,
                               anchor.y + Mathf.Sin(p) * distance,
                               anchor.z - Mathf.Cos(y) * flat);
        }

        /// <summary>How far the boom may reach before it is inside something.
        /// A hit shorter than the margin means the wall is against his back
        /// and the camera goes to the anchor rather than through it.</summary>
        public static float AllowedDistance(float wanted, float hitDistance, float margin)
        {
            if (hitDistance < 0f) { return wanted; }        // nothing hit
            return Mathf.Clamp(hitDistance - margin, 0f, wanted);
        }

        private void LateUpdate()
        {
            if (Target == null)
            {
                if (PlayerFighter.Current == null) { return; }
                Target = PlayerFighter.Current.transform;
            }

            float dt = Time.deltaTime;

            float turn = Input.GetAxis("Mouse X") * TurnSpeed * 0.06f;
            if (Input.GetKey(KeyCode.Q)) { turn -= TurnSpeed * dt; }
            if (Input.GetKey(KeyCode.E)) { turn += TurnSpeed * dt; }
            _yaw += turn;

            float look = Input.GetAxis("Mouse Y") * PitchSpeed * 0.06f;
            _pitch = Mathf.Clamp(_pitch + (InvertPitch ? -look : look), MinPitch, MaxPitch);

            Vector3 anchor = Target.position + Vector3.up * ShoulderHeight;

            // Sweep the boom. What it hits is where the camera stops.
            float wanted = Distance;
            Vector3 back = (BoomPosition(anchor, _yaw, _pitch, 1f) - anchor).normalized;
            RaycastHit hit;
            float hitDistance = Physics.Raycast(anchor, back, out hit, wanted + WallMargin)
                              ? hit.distance : -1f;
            float allowed = AllowedDistance(wanted, hitDistance, WallMargin);

            // Snap in when something gets between, ease out when it clears —
            // a camera that eases inward is a camera that spends a moment
            // inside the wall on the way.
            _distance = allowed < _distance
                      ? allowed
                      : Mathf.Lerp(_distance, allowed, 1f - Mathf.Exp(-4f * dt));

            transform.position = Vector3.Lerp(transform.position,
                BoomPosition(anchor, _yaw, _pitch, _distance),
                1f - Mathf.Exp(-Damping * dt));
            transform.rotation = Quaternion.Euler(_pitch, _yaw, 0f);
        }
    }
}
