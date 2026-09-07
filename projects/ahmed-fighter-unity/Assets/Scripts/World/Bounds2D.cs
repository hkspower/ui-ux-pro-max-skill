using UnityEngine;

namespace Ahmed.World
{
    /// <summary>
    /// A rectangle on the ground plane, in metres.
    ///
    /// The strip needed only a min and max along X, with depth fixed for the
    /// whole game. A district is a field, so the space a fighter may stand in
    /// is two ranges rather than one, and it moves with him as he crosses from
    /// one district into the next.
    /// </summary>
    public struct Bounds2D
    {
        public float MinX, MaxX, MinZ, MaxZ;

        public Bounds2D(float minX, float maxX, float minZ, float maxZ)
        {
            MinX = minX; MaxX = maxX; MinZ = minZ; MaxZ = maxZ;
        }

        public static Bounds2D Unbounded
        {
            get
            {
                return new Bounds2D(float.NegativeInfinity, float.PositiveInfinity,
                                    float.NegativeInfinity, float.PositiveInfinity);
            }
        }

        /// <summary>A square of side 2*extent about a centre.</summary>
        public static Bounds2D Square(Vector3 centre, float extent)
        {
            return new Bounds2D(centre.x - extent, centre.x + extent,
                                centre.z - extent, centre.z + extent);
        }

        public Vector3 Centre
        {
            get { return new Vector3((MinX + MaxX) * 0.5f, 0f, (MinZ + MaxZ) * 0.5f); }
        }

        public float Width { get { return MaxX - MinX; } }
        public float Depth { get { return MaxZ - MinZ; } }

        public bool Contains(Vector3 p)
        {
            return p.x >= MinX && p.x <= MaxX && p.z >= MinZ && p.z <= MaxZ;
        }

        public Vector3 Clamp(Vector3 p)
        {
            return new Vector3(Mathf.Clamp(p.x, MinX, MaxX), p.y,
                               Mathf.Clamp(p.z, MinZ, MaxZ));
        }

        /// <summary>Shrunk on every side, for keeping spawns off the fence.</summary>
        public Bounds2D Inset(float by)
        {
            return new Bounds2D(MinX + by, MaxX - by, MinZ + by, MaxZ - by);
        }
    }
}
