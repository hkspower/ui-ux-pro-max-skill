using UnityEngine;
using Ahmed.Combat;
using Ahmed.Data;
using Ahmed.World;

namespace Ahmed.Game
{
    /// <summary>
    /// Builds a playable stage at runtime: ground, camera, light, Ahmed, an
    /// enemy template and a wave director.
    ///
    /// It exists because the port has no authored scenes yet, and a project
    /// you cannot press play on is not a port. Drop this on an empty
    /// GameObject in an empty scene and the stage runs. Everything it makes is
    /// a primitive -- the real character mesh, materials and level geometry
    /// replace it piece by piece, and nothing else in the port refers to this
    /// class, so deleting it later costs nothing.
    /// </summary>
    public class Bootstrap : MonoBehaviour
    {
        [Tooltip("Index into stages.json. 0 is Souq Mubarakiya.")]
        public int StageIndex;

        [Tooltip("Enemy health and damage scaling, as the difficulty would set it.")]
        public float EnemyHealthScale = 1f;
        public float EnemyDamageScale = 1f;

        private Transform _camera;
        private PlayerFighter _player;

        private void Awake()
        {
            GameData.Load();
            StageRow stage = GameData.Stage(StageIndex);
            float length = stage != null ? stage.length : 60f;

            BuildGround(length);
            BuildLight();
            _camera = BuildCamera();
            _player = BuildPlayer();

            GameObject template = BuildEnemyTemplate();

            GameObject directorGo = new GameObject("WaveDirector");
            WaveDirector director = directorGo.AddComponent<WaveDirector>();
            director.StageIndex = StageIndex;
            director.EnemyPrefab = template;
            director.EnemyHealthScale = EnemyHealthScale;
            director.EnemyDamageScale = EnemyDamageScale;

            if (stage != null)
            {
                Debug.Log("[Ahmed] " + stage.displayName + " — " + stage.length.ToString("0.0")
                    + " m, " + (stage.waves != null ? stage.waves.Length : 0) + " waves. "
                    + stage.hint);
            }
        }

        private void LateUpdate()
        {
            if (_camera == null || _player == null) { return; }
            // A beat-'em-up camera trails along the strip and never turns.
            // Following in Z as well would fight the depth the fight uses.
            Vector3 p = _camera.position;
            p.x = Mathf.Lerp(p.x, _player.transform.position.x + 2f, 4f * Time.deltaTime);
            _camera.position = p;
        }

        private void BuildGround(float length)
        {
            GameObject ground = GameObject.CreatePrimitive(PrimitiveType.Cube);
            ground.name = "Ground";
            ground.transform.position = new Vector3(length * 0.5f, -0.5f, 0f);
            ground.transform.localScale = new Vector3(length + 40f, 1f, 12f);
        }

        private void BuildLight()
        {
            GameObject go = new GameObject("Key Light");
            Light key = go.AddComponent<Light>();
            key.type = LightType.Directional;
            key.intensity = 1.1f;
            go.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
        }

        private Transform BuildCamera()
        {
            GameObject go = new GameObject("Camera");
            Camera cam = go.AddComponent<Camera>();
            cam.fieldOfView = 42f;
            // Back, up and looking slightly down: the browser build's framing,
            // which is what the stage lengths and reaches were tuned against.
            go.transform.position = new Vector3(0f, 4.2f, -12f);
            go.transform.rotation = Quaternion.Euler(12f, 0f, 0f);
            return go.transform;
        }

        private PlayerFighter BuildPlayer()
        {
            GameObject go = MakeBody("Ahmed");
            go.transform.position = new Vector3(3.4f, 1f, 0f);
            return go.AddComponent<PlayerFighter>();
        }

        private GameObject BuildEnemyTemplate()
        {
            GameObject go = MakeBody("EnemyTemplate");
            go.AddComponent<EnemyFighter>();
            // Inactive so it is a prefab in all but name: the director clones
            // it, and the template itself never fights.
            go.SetActive(false);
            return go;
        }

        private static GameObject MakeBody(string name)
        {
            GameObject go = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            go.name = name;
            go.transform.localScale = new Vector3(0.6f, 0.9f, 0.6f);

            // The primitive's own collider fights the CharacterController.
            Collider shape = go.GetComponent<Collider>();
            if (shape != null) { Object.Destroy(shape); }

            CharacterController body = go.AddComponent<CharacterController>();
            body.height = 1.8f;
            body.radius = 0.32f;
            body.center = new Vector3(0f, 0.9f, 0f);
            return go;
        }
    }
}
