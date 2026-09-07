using UnityEngine;
using Ahmed.Combat;

namespace Ahmed.Game
{
    /// <summary>
    /// The camera. Trails the player at a fixed pitch, at a yaw the player can
    /// swing round.
    ///
    /// It has to turn now, and that is the change that makes the district an
    /// open space rather than a wide corridor: on the strip the camera looked
    /// one way for the whole game and "forward" was a world axis. Here forward
    /// is whatever the camera is pointing at, which is why
    /// <see cref="PlayerFighter"/> reads its movement basis off this.
    /// </summary>
    public class FollowCamera : MonoBehaviour
    {
        /// <summary>The one the player's input is measured against.</summary>
        public static FollowCamera Current { get; private set; }

        public Transform Target;
        public float Distance = 11f;
        public float Height = 6.2f;
        public float Pitch = 26f;
        public float TurnSpeed = 110f;
        public float Damping = 6f;

        private float _yaw;

        private void Awake()
        {
            Current = this;
            _yaw = 0f;
        }

        private void OnDestroy()
        {
            if (Current == this) { Current = null; }
        }

        /// <summary>Flat forward and right, for turning stick input into a
        /// direction in the world.</summary>
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

        private void LateUpdate()
        {
            if (Target == null)
            {
                if (PlayerFighter.Current == null) { return; }
                Target = PlayerFighter.Current.transform;
            }

            float turn = 0f;
            if (Input.GetKey(KeyCode.Q)) { turn -= 1f; }
            if (Input.GetKey(KeyCode.E)) { turn += 1f; }
            _yaw += turn * TurnSpeed * Time.deltaTime;

            Vector3 wanted = Target.position - Forward * Distance + Vector3.up * Height;
            transform.position = Vector3.Lerp(transform.position, wanted,
                                              1f - Mathf.Exp(-Damping * Time.deltaTime));
            transform.rotation = Quaternion.Euler(Pitch, _yaw, 0f);
        }
    }
}
