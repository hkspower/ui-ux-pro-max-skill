// Dump what the stub's maths and the IK solver produce, for an independent
// recomputation in numpy. Fixed seed: the run is reproducible.
using System; using System.Globalization; using System.Text; using UnityEngine; using Ahmed.Combat;
public static class Dump {
    static System.Random R = new System.Random(20260909);
    static float F() { return (float)(R.NextDouble()*2.0 - 1.0); }
    static Vector3 V() { return new Vector3(F(), F(), F()); }
    static Vector3 U() { Vector3 v = V(); while (v.magnitude < 1e-3f) v = V(); return v.normalized; }
    static string S(float f) { return f.ToString("R", CultureInfo.InvariantCulture); }
    static string S(Vector3 v) { return S(v.x)+" "+S(v.y)+" "+S(v.z); }
    static string S(Quaternion q) { return S(q.x)+" "+S(q.y)+" "+S(q.z)+" "+S(q.w); }
    public static int Main() {
        StringBuilder o = new StringBuilder();
        // the anchor: Unity's documented left-handed convention
        o.Append("ANCHOR ").Append(S(Quaternion.AngleAxis(90f, Vector3.up) * Vector3.forward)).Append('\n');
        o.Append("ANCHORCROSS ").Append(S(Vector3.Cross(Vector3.up, Vector3.forward))).Append('\n');
        for (int i = 0; i < 4000; i++) {
            Vector3 axis = U(), v = V(), a = U(), b = U(), fwd = U(), up = U();
            float deg = F() * 180f, t = (float)R.NextDouble();
            Quaternion qa = Quaternion.AngleAxis(F()*180f, U());
            Quaternion qb = Quaternion.AngleAxis(F()*180f, U());
            Quaternion aa = Quaternion.AngleAxis(deg, axis);
            o.Append("AA ").Append(S(deg)).Append(' ').Append(S(axis)).Append(' ').Append(S(aa)).Append('\n');
            o.Append("ROT ").Append(S(aa)).Append(' ').Append(S(v)).Append(' ').Append(S(aa * v)).Append('\n');
            o.Append("MUL ").Append(S(qa)).Append(' ').Append(S(qb)).Append(' ').Append(S(qa*qb)).Append('\n');
            o.Append("INV ").Append(S(qa)).Append(' ').Append(S(Quaternion.Inverse(qa))).Append('\n');
            o.Append("F2R ").Append(S(a)).Append(' ').Append(S(b)).Append(' ').Append(S(Quaternion.FromToRotation(a,b))).Append('\n');
            if (Vector3.Cross(up, fwd).magnitude > 0.15f)
                o.Append("LOOK ").Append(S(fwd)).Append(' ').Append(S(up)).Append(' ').Append(S(Quaternion.LookRotation(fwd, up))).Append('\n');
            o.Append("SLERP ").Append(S(qa)).Append(' ').Append(S(qb)).Append(' ').Append(S(t)).Append(' ').Append(S(Quaternion.Slerp(qa,qb,t))).Append('\n');
            o.Append("CROSS ").Append(S(a)).Append(' ').Append(S(b)).Append(' ').Append(S(Vector3.Cross(a,b))).Append('\n');
            o.Append("PROJ ").Append(S(v)).Append(' ').Append(S(a)).Append(' ').Append(S(Vector3.ProjectOnPlane(v,a))).Append('\n');
            o.Append("ANG ").Append(S(a)).Append(' ').Append(S(b)).Append(' ').Append(S(Vector3.Angle(a,b))).Append('\n');
            // the IK solve itself
            Vector3 root = V()*2f;
            float l1 = 0.2f + (float)R.NextDouble()*0.8f, l2 = 0.2f + (float)R.NextDouble()*0.8f;
            Vector3 mid = root + U()*l1, end = mid + U()*l2;
            Vector3 target = root + U()*((float)R.NextDouble()*(l1+l2)*1.3f), pole = root + U()*2f;
            Vector3 nm, ne; TwoBoneIK.Solve(root, mid, end, target, pole, out nm, out ne);
            o.Append("IK ").Append(S(root)).Append(' ').Append(S(mid)).Append(' ').Append(S(end)).Append(' ')
             .Append(S(target)).Append(' ').Append(S(pole)).Append(' ').Append(S(nm)).Append(' ').Append(S(ne)).Append('\n');
        }
        Console.Write(o.ToString());
        return 0;
    }
}
