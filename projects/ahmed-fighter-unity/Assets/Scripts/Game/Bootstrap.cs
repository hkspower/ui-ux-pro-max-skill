using UnityEngine;
using Ahmed.Combat;
using Ahmed.Data;
using Ahmed.World;

namespace Ahmed.Game
{
    /// <summary>
    /// Brings the open world up: Ahmed, a camera that follows him, an enemy
    /// template, and the district runtime that builds whichever of the nine
    /// areas he is standing in.
    ///
    /// It exists because the port has no authored scenes, and a project you
    /// cannot press play on is not a port. Everything it makes is a primitive
    /// -- the real character mesh, materials and district art replace them
    /// piece by piece, and nothing else refers to this class, so deleting it
    /// later costs nothing.
    /// </summary>
    public class Bootstrap : MonoBehaviour
    {
        [Tooltip("Area to start in. -1 uses the world graph's own start.")]
        public int StartArea = -1;

        [Tooltip("Enemy health and damage scaling, as the difficulty would set it.")]
        public float EnemyHealthScale = 1f;
        public float EnemyDamageScale = 1f;

        [Tooltip("Start with every talent, to walk the whole map without earning it.")]
        public bool UnlockEverything;

        [Tooltip("Throw away the save and start the run again.")]
        public bool ClearSaveOnStart;

        private void Awake()
        {
            GameData.Load();
            AudioLibrary.Load();    // up front, so the first punch is not the load

            // A save is the world; loading one replaces it, so this happens
            // before anything reads WorldState. No save means a new run.
            WorldState.Reset();
            bool loaded = !ClearSaveOnStart && SaveGame.Read();
            if (ClearSaveOnStart) { SaveGame.Erase(); }

            if (UnlockEverything)
            {
                // Ten of the eighteen links want a talent. Without this the
                // world is correctly mostly shut, which is right for play and
                // unhelpful for looking at it.
                WorldState.GrantTalent(Ability.Vault);
                WorldState.GrantTalent(Ability.DashLeap);
                WorldState.GrantTalent(Ability.PowerKick);
                WorldState.GrantTalent(Ability.Haymaker);
                WorldState.GrantTalent(Ability.HawkFist);
            }

            BuildLight();
            PlayerFighter player = BuildPlayer();
            BuildCamera(player);

            GameObject template = BuildEnemyTemplate();

            GameObject worldGo = new GameObject("World");
            DistrictRuntime world = worldGo.AddComponent<DistrictRuntime>();
            world.EnemyPrefab = template;
            world.EnemyHealthScale = EnemyHealthScale;
            world.EnemyDamageScale = EnemyDamageScale;
            worldGo.AddComponent<HubPanel>();

            // A saved run resumes where it was saved; a new one opens in the
            // hub at the centre of the starting district, which is the one
            // place in the world that is his.
            int start = StartArea >= 0 ? StartArea
                      : loaded && WorldState.HasCheckpoint ? WorldState.CheckpointArea
                      : GameData.StartArea;
            Vector3 arrive = loaded && WorldState.HasCheckpoint && StartArea < 0
                           ? WorldState.CheckpointPosition : Vector3.zero;
            world.Enter(start, arrive);

            Debug.Log("[Ahmed] " + GameData.Areas.Count + " districts, "
                + (loaded ? "resumed" : "new run") + " in area " + start
                + ", " + WorldState.Experience + " XP"
                + (UnlockEverything ? ", with every talent" : ""));
        }

        private void BuildLight()
        {
            GameObject go = new GameObject("Key Light");
            Light key = go.AddComponent<Light>();
            key.type = LightType.Directional;
            key.intensity = 1.1f;
            go.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
        }

        private void BuildCamera(PlayerFighter player)
        {
            GameObject go = new GameObject("Camera");
            Camera cam = go.AddComponent<Camera>();
            cam.fieldOfView = 46f;
            cam.farClipPlane = 600f;    // a district is 260 m across
            FollowCamera follow = go.AddComponent<FollowCamera>();
            follow.Target = player != null ? player.transform : null;
        }

        private PlayerFighter BuildPlayer()
        {
            GameObject go = MakeBody("Ahmed");
            go.transform.position = new Vector3(0f, 1f, 0f);
            return go.AddComponent<PlayerFighter>();
        }

        private GameObject BuildEnemyTemplate()
        {
            GameObject go = MakeBody("EnemyTemplate");
            go.AddComponent<EnemyFighter>();
            // Inactive so it is a prefab in all but name: the district clones
            // it, and the template itself never fights.
            go.SetActive(false);
            return go;
        }

        private static GameObject MakeBody(string name)
        {
            GameObject go = new GameObject(name);

            // The real mesh when it is there, and the capsule only when it is
            // not. Ahmed is generated by
            // ../ahmed-fighter-ue5/Tools/blender/build_ahmed.py -- the same
            // body the Unreal build uses, exported a second time in metres and
            // Y-up. It sits under Resources because this port has no authored
            // scene to place it in.
            GameObject model = Resources.Load<GameObject>("Models/Ahmed");
            GameObject visual;
            if (model != null)
            {
                visual = Object.Instantiate(model);
            }
            else
            {
                visual = GameObject.CreatePrimitive(PrimitiveType.Capsule);
                visual.transform.localScale = new Vector3(0.6f, 0.9f, 0.6f);
                // A 2 m primitive at 0.9 is 1.8 m, and it is centred on its
                // own origin where the mesh stands on its feet.
                visual.transform.localPosition = new Vector3(0f, 0.9f, 0f);

                // The primitive's own collider fights the CharacterController.
                Collider shape = visual.GetComponent<Collider>();
                if (shape != null) { Object.Destroy(shape); }
            }
            visual.name = "Mesh";
            // False: keep the local placement above rather than the world one
            // it happens to have been made at.
            visual.transform.SetParent(go.transform, false);

            // The real mesh gets its pose computed: feet on the ground,
            // strikes thrown from the attack rows. A capsule has no bones to
            // move, so it gets nothing.
            if (model != null) { go.AddComponent<FighterIK>(); }

            // On the body itself, which is no longer scaled -- the controller
            // takes the transform's scale with it, so a scaled root quietly
            // made every fighter 1.62 m to the collision system while the
            // numbers all said 1.8.
            CharacterController body = go.AddComponent<CharacterController>();
            body.height = 1.8f;
            body.radius = 0.32f;
            body.center = new Vector3(0f, 0.9f, 0f);
            return go;
        }
    }
}
