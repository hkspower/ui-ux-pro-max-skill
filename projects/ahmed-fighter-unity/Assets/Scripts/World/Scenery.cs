using System.Collections.Generic;
using UnityEngine;

namespace Ahmed.World
{
    /// <summary>
    /// Puts a district's landmarks in the scene, and keeps only the ones near
    /// enough to matter in it.
    ///
    /// A district is up to 260 m across and carries a few hundred structures
    /// on each of its three floors. Instantiating all of them on the way in
    /// is a stall at every doorway and a scene full of objects nobody can see;
    /// so the field is cut into cells, and a cell's contents exist only while
    /// the player is within <see cref="LoadRadius"/> of it. Cells are let go
    /// again a little further out than they are taken up, so standing on a
    /// boundary does not thrash.
    ///
    /// The work is spread: at most <see cref="BudgetPerTick"/> structures are
    /// built in any one frame, so a cell coming into range is a few frames of
    /// quiet work rather than one long one.
    ///
    /// The cell arithmetic is static and pure, which is how it is checked
    /// without an editor — everything that decides *what should be resident*
    /// can be executed on its own.
    /// </summary>
    public class Scenery
    {
        /// <summary>Metres a side. Small enough that a cell is cheap, big
        /// enough that a district is a hundred-odd cells and not ten
        /// thousand.</summary>
        public const float CellSize = 24f;
        /// <summary>How far from the player a cell is built.</summary>
        public const float LoadRadius = 78f;
        /// <summary>And how far out it is let go again. The difference is the
        /// hysteresis that stops a boundary from thrashing.</summary>
        public const float ReleaseRadius = 96f;
        /// <summary>Structures built per tick, at most.</summary>
        public const int BudgetPerTick = 24;

        private readonly Dictionary<long, List<Placement>> _plan =
            new Dictionary<long, List<Placement>>();
        private readonly Dictionary<long, List<GameObject>> _live =
            new Dictionary<long, List<GameObject>>();
        private readonly List<long> _wanted = new List<long>();
        private readonly List<long> _stale = new List<long>();
        private GameObject _root;

        /// <summary>How many structures the district holds in all.</summary>
        public int Planned { get; private set; }
        /// <summary>How many are in the scene right now.</summary>
        public int Resident { get; private set; }
        /// <summary>Cells with something in them.</summary>
        public int CellCount { get { return _plan.Count; } }

        /// <summary>
        /// Work out what a district is made of and file it by cell. No scene
        /// object is made here: this is the part that can run before the
        /// player has arrived, which is what lets the next district be
        /// prepared while he is still walking towards its door.
        /// </summary>
        public Scenery(District district)
        {
            Dictionary<int, List<Placement>> byLevel = Landmarks.ForAll(district);
            foreach (KeyValuePair<int, List<Placement>> floor in byLevel)
            {
                List<Placement> list = floor.Value;
                for (int i = 0; i < list.Count; i++)
                {
                    long key = CellKey(list[i].Position, floor.Key);
                    List<Placement> cell;
                    if (!_plan.TryGetValue(key, out cell))
                    {
                        cell = new List<Placement>();
                        _plan[key] = cell;
                    }
                    cell.Add(list[i]);
                    Planned++;
                }
            }
        }

        // ------------------------------------------------------- cell arithmetic

        public static int CellIndex(float metres)
        {
            return Mathf.FloorToInt(metres / CellSize);
        }

        /// <summary>A cell's key. The floor is part of it: the cellar's cell
        /// and the street's cell over it are different places.</summary>
        public static long CellKey(int cx, int cz, int level)
        {
            return ((long)(cx + 4096) << 40) | ((long)(cz + 4096) << 16) | (uint)(level + 8);
        }

        public static long CellKey(Vector3 at, int level)
        {
            return CellKey(CellIndex(at.x), CellIndex(at.z), level);
        }

        /// <summary>The nearest point of a cell to somewhere, on the flat.
        /// A cell is wanted by how close it comes, not by how far its middle
        /// is — otherwise a big cell you are standing at the edge of is
        /// further away than one you are not in at all.</summary>
        public static float CellDistance(int cx, int cz, Vector3 from)
        {
            float minX = cx * CellSize, maxX = minX + CellSize;
            float minZ = cz * CellSize, maxZ = minZ + CellSize;
            float dx = from.x < minX ? minX - from.x : (from.x > maxX ? from.x - maxX : 0f);
            float dz = from.z < minZ ? minZ - from.z : (from.z > maxZ ? from.z - maxZ : 0f);
            return Mathf.Sqrt(dx * dx + dz * dz);
        }

        /// <summary>Which of this district's cells should be in the scene with
        /// the player standing there. Pure, so the streaming can be checked
        /// without a scene to check it in.</summary>
        public List<long> CellsWithin(Vector3 player, int level, float radius)
        {
            List<long> keys = new List<long>();
            int reach = Mathf.FloorToInt(radius / CellSize) + 1;
            int px = CellIndex(player.x), pz = CellIndex(player.z);
            for (int cx = px - reach; cx <= px + reach; cx++)
            {
                for (int cz = pz - reach; cz <= pz + reach; cz++)
                {
                    if (CellDistance(cx, cz, player) > radius) { continue; }
                    long key = CellKey(cx, cz, level);
                    if (_plan.ContainsKey(key)) { keys.Add(key); }
                }
            }
            return keys;
        }

        // ------------------------------------------------------------ the scene

        /// <summary>
        /// Bring the cells near the player up, let the far ones go. Called
        /// every frame by the district; does a bounded amount of work.
        /// </summary>
        public void Update(Vector3 player, int level)
        {
            if (_root == null) { _root = new GameObject("Scenery"); }

            _wanted.Clear();
            _wanted.AddRange(CellsWithin(player, level, LoadRadius));

            // Anything resident that has gone out of release range, or is on a
            // floor he has left, goes.
            _stale.Clear();
            foreach (KeyValuePair<long, List<GameObject>> live in _live)
            {
                int cx, cz, lv;
                Decode(live.Key, out cx, out cz, out lv);
                if (lv != level || CellDistance(cx, cz, player) > ReleaseRadius)
                {
                    _stale.Add(live.Key);
                }
            }
            for (int i = 0; i < _stale.Count; i++) { Release(_stale[i]); }

            // A cell part-built last tick is still short of its plan, so it
            // is picked up again here rather than counted as done.
            int budget = BudgetPerTick;
            for (int i = 0; i < _wanted.Count && budget > 0; i++)
            {
                List<GameObject> made;
                if (_live.TryGetValue(_wanted[i], out made)
                    && made.Count >= _plan[_wanted[i]].Count) { continue; }
                budget -= Build(_wanted[i], budget);
            }
        }

        private static void Decode(long key, out int cx, out int cz, out int level)
        {
            cx = (int)((key >> 40) & 0xFFFFFF) - 4096;
            cz = (int)((key >> 16) & 0xFFFFFF) - 4096;
            level = (int)(key & 0xFFFF) - 8;
        }

        /// <summary>Builds up to `budget` of a cell, and returns how many it
        /// made. A cell part-built this frame finishes on the next one.</summary>
        private int Build(long key, int budget)
        {
            List<Placement> plan = _plan[key];
            List<GameObject> made;
            if (!_live.TryGetValue(key, out made)) { made = new List<GameObject>(); }

            int built = 0;
            for (int i = made.Count; i < plan.Count && built < budget; i++, built++)
            {
                made.Add(Raise(plan[i]));
                Resident++;
            }
            _live[key] = made;      // part-built cells finish on the next tick
            return built;
        }

        private GameObject Raise(Placement p)
        {
            GameObject go = GameObject.CreatePrimitive(
                p.Shape == Shape.Post ? PrimitiveType.Cylinder : PrimitiveType.Cube);
            go.name = p.Kind;
            go.transform.SetParent(_root.transform, false);
            go.transform.position = p.Position;
            go.transform.rotation = Quaternion.Euler(0f, p.Yaw, 0f);
            // Unity's cylinder is two units tall and its cube is one, so a
            // post takes half the height it is asked for.
            go.transform.localScale = p.Shape == Shape.Post
                ? new Vector3(p.Size.x, p.Size.y * 0.5f, p.Size.z)
                : p.Size;
            if (!p.Solid)
            {
                Collider c = go.GetComponent<Collider>();
                if (c != null) { Object.Destroy(c); }
            }
            return go;
        }

        private void Release(long key)
        {
            List<GameObject> made;
            if (!_live.TryGetValue(key, out made)) { return; }
            for (int i = 0; i < made.Count; i++)
            {
                if (made[i] != null) { Object.Destroy(made[i]); }
                Resident--;
            }
            _live.Remove(key);
        }

        /// <summary>Everything goes. What leaving a district does.</summary>
        public void Clear()
        {
            List<long> keys = new List<long>(_live.Keys);
            for (int i = 0; i < keys.Count; i++) { Release(keys[i]); }
            if (_root != null) { Object.Destroy(_root); _root = null; }
            Resident = 0;
        }
    }
}
