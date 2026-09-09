// A small UnityEngine, enough to RUN the port's logic without an editor.
//
// It started as a compile-check stub. It is more than that now: transforms
// compose through their parents, colliders answer raycasts, and MonoBehaviours
// get Awake/Start/Update/LateUpdate driven in script order. That is what lets
// the parts of the game that are not pure -- a bone rotated through a
// hierarchy, a foot ray in a crowd -- be executed and measured rather than
// only reasoned about.
//
// It is NOT Unity, and everything it does is an assertion about Unity that a
// person believed. The conventions it commits to are checked against an
// independent implementation by xcheck/, and the members it does not have are
// the members the port does not use. Rendering, animation, the real physics
// solver and the real frame loop are all absent.
//
// It lives under Tools/ and not Assets/ on purpose: inside Assets/ Unity would
// compile it and every type here would collide with the real engine's.
using System;
using System.Collections.Generic;

namespace UnityEngine
{
    public class Object {
        protected string _name = "";
        // A Component's name is its GameObject's, which is what makes
        // transform.Find(child) work at all.
        public virtual string name { get { return _name; } set { _name = value; } }
        public static T[] FindObjectsByType<T>(FindObjectsSortMode s) where T : Object { return new T[0]; }
        public static T Instantiate<T>(T o, Vector3 p, Quaternion r) where T : Object { return o; }
        public static T Instantiate<T>(T o) where T : Object { return o; }
        public static void Destroy(Object o) { GameObject g = o as GameObject; if (g != null) g.SetActive(false); }
        public static void DontDestroyOnLoad(Object o) { }
        public static implicit operator bool(Object o) { return !ReferenceEquals(o, null); }
    }
    public enum FindObjectsSortMode { None, InstanceID }
    public class Component : Object {
        internal GameObject _go;
        public override string name {
            get { return _go != null ? _go.name : _name; }
            set { if (_go != null) _go.name = value; else _name = value; }
        }
        public GameObject gameObject { get { return _go; } }
        public virtual Transform transform { get { return _go != null ? _go.transform : null; } }
        public T GetComponent<T>() where T : class { return _go != null ? _go.GetComponent<T>() : null; }
        public T GetComponentInParent<T>() where T : class {
            Transform t = transform;
            while (t != null) { T c = t.gameObject.GetComponent<T>(); if (c != null) return c; t = t.parent; }
            return null;
        }
    }
    public class Behaviour : Component { public bool enabled; }
    public class MonoBehaviour : Behaviour { }
    public class ScriptableObject : Object { }
    public class GameObject : Object {
        readonly List<Component> _components = new List<Component>();
        readonly Transform _t;
        public bool activeSelf = true;
        public GameObject() : this("GameObject") { }
        public GameObject(string n) {
            name = n; _t = new Transform(); _t._go = this; _components.Add(_t);
            Scene.Register(this);
        }
        public static GameObject CreatePrimitive(PrimitiveType t) {
            GameObject g = new GameObject(t.ToString());
            g.AddComponent<BoxCollider>();
            return g;
        }
        public void SetActive(bool v) { activeSelf = v; }
        public Transform transform { get { return _t; } }
        public T GetComponent<T>() where T : class {
            for (int i = 0; i < _components.Count; i++) { T c = _components[i] as T; if (c != null) return c; }
            return null;
        }
        public T AddComponent<T>() where T : Component {
            T c = (T)Activator.CreateInstance(typeof(T));
            c._go = this; _components.Add(c);
            Scene.Added(c);
            return c;
        }
        public IList<Component> Components { get { return _components; } }
    }
    public enum PrimitiveType { Sphere, Capsule, Cylinder, Cube, Plane, Quad }
    // Colliders are boxes and upright capsules, which is all the port makes:
    // a ground slab, site markers, and a controller per fighter.
    public abstract class Collider : Component {
        public bool enabled = true;
        /// <summary>Distance along a straight-down ray from `from` at which
        /// this is hit, or -1. Down only -- every ray the port casts is down.</summary>
        public abstract float RaycastDown(Vector3 from, float maxDistance, out Vector3 point);
    }
    public class BoxCollider : Collider {
        /// <summary>Half extents in world units, taken from localScale.</summary>
        public override float RaycastDown(Vector3 from, float maxDistance, out Vector3 point) {
            point = Vector3.zero;
            Vector3 c = transform.position, s = transform.localScale;
            float hx = Mathf.Abs(s.x) * 0.5f, hy = Mathf.Abs(s.y) * 0.5f, hz = Mathf.Abs(s.z) * 0.5f;
            if (from.x < c.x - hx || from.x > c.x + hx) return -1f;
            if (from.z < c.z - hz || from.z > c.z + hz) return -1f;
            float top = c.y + hy;
            if (from.y < top) return -1f;              // a ray starting inside does not hit
            float d = from.y - top;
            if (d > maxDistance) return -1f;
            point = new Vector3(from.x, top, from.z);
            return d;
        }
    }
    /// <summary>An upright capsule, the shape a CharacterController is.</summary>
    public class CapsuleCollider : Collider {
        public float radius = 0.5f, height = 2f;
        public Vector3 center = Vector3.zero;
        public override float RaycastDown(Vector3 from, float maxDistance, out Vector3 point) {
            point = Vector3.zero;
            Vector3 c = transform.position + center;
            float dx = from.x - c.x, dz = from.z - c.z;
            if (dx*dx + dz*dz > radius*radius) return -1f;
            float top = c.y + Mathf.Max(0f, height * 0.5f);
            if (from.y < top) return -1f;
            float d = from.y - top;
            if (d > maxDistance) return -1f;
            point = new Vector3(from.x, top, from.z);
            return d;
        }
    }
    public class AudioClip : Object { public float length { get { return 0f; } } }
    public class AudioSource : Behaviour {
        public AudioClip clip;
        public float volume, pitch, spatialBlend, minDistance, maxDistance;
        public bool playOnAwake, loop;
        public bool isPlaying { get { return false; } }
        public void Play() { } public void Stop() { }
        public void PlayOneShot(AudioClip c, float v) { }
    }
    public class Camera : Behaviour { public float fieldOfView, farClipPlane, nearClipPlane;
        public static Camera main { get { return null; } } }
    public enum LightType { Spot, Directional, Point, Area }
    public class Light : Behaviour { public LightType type; public float intensity; }
    // A transform that composes through its parents, which is the whole point:
    // rotating a thigh has to carry the shin and the foot with it, or an IK
    // solver that rotates bones cannot be tested at all. Local is the stored
    // state; world is derived. Scale is stored but not composed -- nothing in
    // the port puts a scaled object above a bone.
    public class Transform : Component {
        Vector3 _localPosition = Vector3.zero;
        Quaternion _localRotation = Quaternion.identity;
        Transform _parent;
        readonly List<Transform> _children = new List<Transform>();

        public override Transform transform { get { return this; } }
        public Vector3 localScale { get; set; }
        public Vector3 localPosition { get { return _localPosition; } set { _localPosition = value; } }
        public Quaternion localRotation { get { return _localRotation; } set { _localRotation = value; } }
        public Transform parent { get { return _parent; } }
        public int childCount { get { return _children.Count; } }
        public Transform GetChild(int i) { return _children[i]; }
        public Transform Find(string n) { foreach (var c in _children) if (c.name == n) return c; return null; }

        public Vector3 position {
            get { return _parent == null ? _localPosition : _parent.TransformPoint(_localPosition); }
            set { _localPosition = _parent == null ? value : _parent.InverseTransformPoint(value); }
        }
        public Quaternion rotation {
            get { return _parent == null ? _localRotation : _parent.rotation * _localRotation; }
            set { _localRotation = _parent == null ? value : Quaternion.Inverse(_parent.rotation) * value; }
        }

        public void SetParent(Transform p) { SetParent(p, true); }
        public void SetParent(Transform p, bool worldPositionStays) {
            Vector3 wp = position; Quaternion wr = rotation;
            if (_parent != null) _parent._children.Remove(this);
            _parent = p;
            if (p != null) p._children.Add(this);
            if (worldPositionStays) { position = wp; rotation = wr; }
        }
        public Vector3 forward { get { return rotation * Vector3.forward; } }
        public Vector3 up { get { return rotation * Vector3.up; } }
        public Vector3 right { get { return rotation * Vector3.right; } }
        public Vector3 TransformPoint(Vector3 p) { return position + rotation * p; }
        public Vector3 InverseTransformPoint(Vector3 p) { return Quaternion.Inverse(rotation) * (p - position); }
        public Vector3 TransformDirection(Vector3 d) { return rotation * d; }
    }
    public struct RaycastHit { public Vector3 point, normal; public float distance; public Collider collider; }
    public static class Physics {
        public static bool Raycast(Vector3 origin, Vector3 direction, out RaycastHit hit, float maxDistance) {
            RaycastHit[] one = new RaycastHit[16];
            int n = RaycastNonAlloc(origin, direction, one, maxDistance);
            hit = new RaycastHit(); float best = float.MaxValue;
            for (int i = 0; i < n; i++) if (one[i].distance < best) { best = one[i].distance; hit = one[i]; }
            return n > 0;
        }
        /// <summary>Straight down only. Every ray the port casts is down, and
        /// pretending to a general solver would be pretending.</summary>
        public static int RaycastNonAlloc(Vector3 origin, Vector3 direction, RaycastHit[] results, float maxDistance) {
            if (Vector3.Dot(direction.normalized, Vector3.down) < 0.999f)
                throw new NotSupportedException("the harness only casts straight down");
            int n = 0;
            foreach (Collider c in Scene.Colliders) {
                if (!c.enabled || n >= results.Length) continue;
                Vector3 p; float d = c.RaycastDown(origin, maxDistance, out p);
                if (d < 0f) continue;
                results[n].point = p; results[n].distance = d; results[n].collider = c;
                results[n].normal = Vector3.up; n++;
            }
            return n;
        }
    }

    /// <summary>
    /// The frame loop. Unity calls Awake, Start, Update and LateUpdate by name
    /// whether or not they are public, so this does the same by reflection --
    /// which means the port's real private methods run, not stand-ins written
    /// for the test. DefaultExecutionOrder is honoured, because FighterIK
    /// depends on running after the fighter has moved.
    /// </summary>
    public static class Scene {
        static readonly List<GameObject> Objects = new List<GameObject>();
        static readonly List<Component> Fresh = new List<Component>();
        static readonly HashSet<Component> Started = new HashSet<Component>();
        public static float DeltaTime = 1f / 60f;

        internal static void Register(GameObject g) { Objects.Add(g); }
        internal static void Added(Component c) { Fresh.Add(c); Call(c, "Awake"); }

        public static void Reset() { Objects.Clear(); Fresh.Clear(); Started.Clear(); Time._t = 0f; }

        public static IEnumerable<Collider> Colliders {
            get {
                foreach (GameObject g in Objects) {
                    if (!g.activeSelf) continue;
                    foreach (Component c in g.Components) { Collider col = c as Collider; if (col != null) yield return col; }
                }
            }
        }

        static int Order(Component c) {
            foreach (object a in c.GetType().GetCustomAttributes(typeof(DefaultExecutionOrder), true))
                return ((DefaultExecutionOrder)a).Value;
            return 0;
        }

        static void Call(Component c, string method) {
            // No DeclaredOnly: Unity calls an inherited LateUpdate too, and
            // Fighter declares one that EnemyFighter does not override.
            Type t = c.GetType();
            while (t != null && t != typeof(MonoBehaviour)) {
                var m = t.GetMethod(method,
                    System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Public
                    | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.DeclaredOnly);
                if (m != null && m.GetParameters().Length == 0) { m.Invoke(c, null); return; }
                t = t.BaseType;
            }
        }

        static List<Component> Live() {
            List<Component> live = new List<Component>();
            foreach (GameObject g in Objects) {
                if (!g.activeSelf) continue;
                foreach (Component c in g.Components) if (c is MonoBehaviour) live.Add(c);
            }
            live.Sort((a, b) => Order(a).CompareTo(Order(b)));
            return live;
        }

        /// <summary>One frame: Start on anything new, then Update, then
        /// LateUpdate, each pass in script order.</summary>
        public static void Step() {
            List<Component> live = Live();
            foreach (Component c in live) if (Started.Add(c)) Call(c, "Start");
            foreach (Component c in live) Call(c, "Update");
            foreach (Component c in live) Call(c, "LateUpdate");
            Time._t += DeltaTime;
        }
        public static void Step(int frames) { for (int i = 0; i < frames; i++) Step(); }
    }
    [AttributeUsage(AttributeTargets.Class)] public class DefaultExecutionOrder : Attribute {
        public int Value; public DefaultExecutionOrder(int order) { Value = order; } }
    // A CharacterController is a Collider in Unity, which is exactly why a
    // foot ray can hit another fighter.
    public class CharacterController : CapsuleCollider {
        public bool isGrounded { get { return true; } }
        /// <summary>Moves, then stands on whatever is under it. Not a sweep and
        /// not a solver -- it stops a fighter falling through the floor so a
        /// pose can be measured, and nothing more.</summary>
        public void Move(Vector3 motion) {
            Vector3 p = transform.position + motion;
            Vector3 from = new Vector3(p.x, p.y + 5f, p.z);
            float ground = float.MinValue;
            foreach (Collider c in Scene.Colliders) {
                if (ReferenceEquals(c, this) || !c.enabled) continue;
                Vector3 pt; float d = c.RaycastDown(from, 100f, out pt);
                if (d >= 0f && pt.y > ground && pt.y <= p.y + 0.5f) ground = pt.y;
            }
            if (ground > float.MinValue && p.y < ground) p = new Vector3(p.x, ground, p.z);
            transform.position = p;
        }
    }
    public class TextAsset : Object { public string text { get { return ""; } } }
    public static class Resources { public static T Load<T>(string p) where T : Object { return null; } }
    // A real dictionary, so a save round trip through Write/Read is testable
    // even though the real PlayerPrefs is a platform store.
    public static class PlayerPrefs {
        static readonly System.Collections.Generic.Dictionary<string,string> S = new System.Collections.Generic.Dictionary<string,string>();
        public static void SetString(string k, string v) { S[k] = v; }
        public static string GetString(string k) { string v; return S.TryGetValue(k, out v) ? v : ""; }
        public static string GetString(string k, string d) { string v; return S.TryGetValue(k, out v) ? v : d; }
        public static bool HasKey(string k) { return S.ContainsKey(k); }
        public static void DeleteKey(string k) { S.Remove(k); }
        public static void Save() { }
    }
    public struct Rect {
        public float x, y, width, height;
        public Rect(float x, float y, float w, float h) { this.x=x; this.y=y; width=w; height=h; }
    }
    public class GUIStyle { public int fontSize; public FontStyle fontStyle; }
    public enum FontStyle { Normal, Bold, Italic, BoldAndItalic }
    public static class GUI {
        public static Color color { get; set; }
        public static void Box(Rect r, string text) { }
        public static void Label(Rect r, string text) { }
    }
    public struct Color {
        public float r, g, b, a;
        public Color(float r, float g, float b, float a) { this.r=r; this.g=g; this.b=b; this.a=a; }
        public static Color white { get { return new Color(1,1,1,1); } }
        public static Color gray { get { return new Color(.5f,.5f,.5f,1); } }
    }
    public static class JsonUtility { public static T FromJson<T>(string j) { return default(T); } }
    public static class Time {
        internal static float _t;
        public static float deltaTime { get { return Scene.DeltaTime; } }
        public static float time { get { return _t; } }
    }
    public static class Debug {
        public static void Log(object m) { } public static void LogWarning(object m) { }
        public static void LogError(object m) { }
    }
    public static class Random {
        public static float value { get { return 0f; } }
        public static float Range(float a, float b) { return a; }
        public static int Range(int a, int b) { return a; }
    }
    public static class Input {
        public static bool GetButton(string n) { return false; }
        public static bool GetButtonDown(string n) { return false; }
        public static bool GetKey(KeyCode k) { return false; }
        public static bool GetKeyDown(KeyCode k) { return false; }
        public static float GetAxisRaw(string n) { return 0f; }
    }
    public enum KeyCode { None, Space, LeftShift, Q, E, R, Alpha1, Alpha2, Alpha3, Alpha4, Alpha5 }
    // Real implementations. A stub whose maths lies turns every behavioural
    // test into a test of the stub.
    public static class Mathf {
        public const float PI = 3.14159274f;
        public const float Deg2Rad = 0.0174532924f;
        public const float Rad2Deg = 57.29578f;
        public static float Clamp(float v, float a, float b) { return v < a ? a : (v > b ? b : v); }
        public static int Clamp(int v, int a, int b) { return v < a ? a : (v > b ? b : v); }
        public static float Clamp01(float v) { return Clamp(v, 0f, 1f); }
        public static float Max(float a, float b) { return a > b ? a : b; }
        public static int Max(int a, int b) { return a > b ? a : b; }
        public static float Min(float a, float b) { return a < b ? a : b; }
        public static int Min(int a, int b) { return a < b ? a : b; }
        public static float Abs(float v) { return v < 0f ? -v : v; }
        public static int Abs(int v) { return v < 0 ? -v : v; }
        public static float Sign(float v) { return v >= 0f ? 1f : -1f; }
        public static float Round(float v) { return (float)System.Math.Round((double)v, System.MidpointRounding.AwayFromZero); }
        public static int RoundToInt(float v) { return (int)Round(v); }
        public static int FloorToInt(float v) { return (int)System.Math.Floor(v); }
        public static float Lerp(float a, float b, float t) { return a + (b - a) * Clamp01(t); }
        public static float Sin(float v) { return (float)System.Math.Sin(v); }
        public static float Cos(float v) { return (float)System.Math.Cos(v); }
        public static float Sqrt(float v) { return (float)System.Math.Sqrt(v); }
        public static float Atan2(float a, float b) { return (float)System.Math.Atan2(a, b); }
        public static float Exp(float v) { return (float)System.Math.Exp(v); }
        public static bool Approximately(float a, float b) { return Abs(b - a) < 1e-6f; }
    }
    public struct Vector3 {
        public float x, y, z;
        public Vector3(float x, float y, float z) { this.x = x; this.y = y; this.z = z; }
        public static Vector3 zero { get { return new Vector3(0,0,0); } }
        public static Vector3 right { get { return new Vector3(1,0,0); } }
        public static Vector3 up { get { return new Vector3(0,1,0); } }
        public static Vector3 forward { get { return new Vector3(0,0,1); } }
        public Vector3 normalized { get { float m=(float)System.Math.Sqrt(x*x+y*y+z*z); return m<1e-6f?new Vector3(0,0,0):new Vector3(x/m,y/m,z/m); } }
        public float magnitude { get { return (float)System.Math.Sqrt(x*x+y*y+z*z); } }
        public float sqrMagnitude { get { return x*x+y*y+z*z; } }
        public void Normalize() { Vector3 n=normalized; x=n.x; y=n.y; z=n.z; }
        public static float Dot(Vector3 a, Vector3 b) { return a.x*b.x+a.y*b.y+a.z*b.z; }
        public static float Distance(Vector3 a, Vector3 b) { return (a-b).magnitude; }
        public static Vector3 Lerp(Vector3 a, Vector3 b, float t) { return new Vector3(a.x+(b.x-a.x)*t, a.y+(b.y-a.y)*t, a.z+(b.z-a.z)*t); }
        public static Vector3 operator +(Vector3 a, Vector3 b) { return new Vector3(a.x+b.x,a.y+b.y,a.z+b.z); }
        public static Vector3 operator -(Vector3 a, Vector3 b) { return new Vector3(a.x-b.x,a.y-b.y,a.z-b.z); }
        public static Vector3 operator -(Vector3 a) { return new Vector3(-a.x,-a.y,-a.z); }
        public static Vector3 operator *(Vector3 a, float f) { return new Vector3(a.x*f,a.y*f,a.z*f); }
        public static Vector3 operator *(float f, Vector3 a) { return a*f; }
        public static Vector3 operator /(Vector3 a, float f) { return new Vector3(a.x/f,a.y/f,a.z/f); }
        public static Vector3 Cross(Vector3 a, Vector3 b) { return new Vector3(a.y*b.z-a.z*b.y, a.z*b.x-a.x*b.z, a.x*b.y-a.y*b.x); }
        public static float Angle(Vector3 a, Vector3 b) { float d=Dot(a.normalized,b.normalized); d=d<-1f?-1f:(d>1f?1f:d); return (float)System.Math.Acos(d)*Mathf.Rad2Deg; }
        public static Vector3 ProjectOnPlane(Vector3 v, Vector3 n) { float nn=Dot(n,n); if (nn<1e-12f) return v; return v - n*(Dot(v,n)/nn); }
        public static Vector3 down { get { return new Vector3(0,-1,0); } }
        public override string ToString() { return "("+x+", "+y+", "+z+")"; }
    }
    // Real quaternion maths, Unity's conventions: (x,y,z,w), left-handed
    // frame, rotations compose right to left, Euler is Z then X then Y.
    public struct Quaternion {
        public float x, y, z, w;
        public Quaternion(float x, float y, float z, float w) { this.x=x; this.y=y; this.z=z; this.w=w; }
        public static Quaternion identity { get { return new Quaternion(0,0,0,1); } }
        public static Quaternion AngleAxis(float deg, Vector3 axis) {
            axis = axis.normalized; float h = deg*Mathf.Deg2Rad*0.5f; float s=(float)System.Math.Sin(h);
            return new Quaternion(axis.x*s, axis.y*s, axis.z*s, (float)System.Math.Cos(h));
        }
        public static Quaternion FromToRotation(Vector3 a, Vector3 b) {
            a = a.normalized; b = b.normalized; float d = Vector3.Dot(a,b);
            if (d > 1f - 1e-6f) return identity;
            if (d < -1f + 1e-6f) { Vector3 ax = Vector3.Cross(a, Vector3.right); if (ax.sqrMagnitude < 1e-8f) ax = Vector3.Cross(a, Vector3.up); return AngleAxis(180f, ax); }
            Vector3 c = Vector3.Cross(a,b); float s=(float)System.Math.Sqrt((1f+d)*2f);
            return new Quaternion(c.x/s, c.y/s, c.z/s, s*0.5f);
        }
        public static Quaternion LookRotation(Vector3 f, Vector3 u) {
            f = f.normalized; Vector3 r = Vector3.Cross(u, f).normalized; if (r.sqrMagnitude < 1e-8f) r = Vector3.right; u = Vector3.Cross(f, r);
            float m00=r.x,m01=u.x,m02=f.x, m10=r.y,m11=u.y,m12=f.y, m20=r.z,m21=u.z,m22=f.z;
            float t=m00+m11+m22; Quaternion q;
            if (t>0f){ float s=(float)System.Math.Sqrt(t+1f)*2f; q=new Quaternion((m21-m12)/s,(m02-m20)/s,(m10-m01)/s,0.25f*s); }
            else if (m00>m11&&m00>m22){ float s=(float)System.Math.Sqrt(1f+m00-m11-m22)*2f; q=new Quaternion(0.25f*s,(m01+m10)/s,(m02+m20)/s,(m21-m12)/s); }
            else if (m11>m22){ float s=(float)System.Math.Sqrt(1f+m11-m00-m22)*2f; q=new Quaternion((m01+m10)/s,0.25f*s,(m12+m21)/s,(m02-m20)/s); }
            else { float s=(float)System.Math.Sqrt(1f+m22-m00-m11)*2f; q=new Quaternion((m02+m20)/s,(m12+m21)/s,0.25f*s,(m10-m01)/s); }
            return q;
        }
        public static Quaternion Euler(float x, float y, float z) { return AngleAxis(y, Vector3.up) * AngleAxis(x, Vector3.right) * AngleAxis(z, Vector3.forward); }
        public static Quaternion Inverse(Quaternion q) { return new Quaternion(-q.x,-q.y,-q.z,q.w); }
        public static Quaternion operator *(Quaternion a, Quaternion b) {
            return new Quaternion(a.w*b.x+a.x*b.w+a.y*b.z-a.z*b.y, a.w*b.y-a.x*b.z+a.y*b.w+a.z*b.x, a.w*b.z+a.x*b.y-a.y*b.x+a.z*b.w, a.w*b.w-a.x*b.x-a.y*b.y-a.z*b.z);
        }
        public static Vector3 operator *(Quaternion q, Vector3 v) {
            Vector3 u = new Vector3(q.x,q.y,q.z); float s=q.w;
            return u*(2f*Vector3.Dot(u,v)) + v*(s*s-Vector3.Dot(u,u)) + Vector3.Cross(u,v)*(2f*s);
        }
        public static float Angle(Quaternion a, Quaternion b) { float d=System.Math.Abs(a.x*b.x+a.y*b.y+a.z*b.z+a.w*b.w); d=d>1f?1f:d; return (float)System.Math.Acos(d)*2f*Mathf.Rad2Deg; }
        public static Quaternion Slerp(Quaternion a, Quaternion b, float t) {
            t = Mathf.Clamp01(t); float d=a.x*b.x+a.y*b.y+a.z*b.z+a.w*b.w; if (d<0f){ b=new Quaternion(-b.x,-b.y,-b.z,-b.w); d=-d; }
            if (d>0.9995f){ Quaternion r=new Quaternion(a.x+(b.x-a.x)*t,a.y+(b.y-a.y)*t,a.z+(b.z-a.z)*t,a.w+(b.w-a.w)*t); float n=(float)System.Math.Sqrt(r.x*r.x+r.y*r.y+r.z*r.z+r.w*r.w); return new Quaternion(r.x/n,r.y/n,r.z/n,r.w/n); }
            float th=(float)System.Math.Acos(d), s=(float)System.Math.Sin(th), wa=(float)System.Math.Sin((1f-t)*th)/s, wb=(float)System.Math.Sin(t*th)/s;
            return new Quaternion(a.x*wa+b.x*wb,a.y*wa+b.y*wb,a.z*wa+b.z*wb,a.w*wa+b.w*wb);
        }
    }
    [AttributeUsage(AttributeTargets.Class)] public class RequireComponent : Attribute {
        public RequireComponent(Type t) { }
    }
    [AttributeUsage(AttributeTargets.Field)] public class TooltipAttribute : Attribute {
        public TooltipAttribute(string t) { }
    }
    [AttributeUsage(AttributeTargets.Field)] public class SerializeField : Attribute { }
}
