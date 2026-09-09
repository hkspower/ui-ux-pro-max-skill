using System; using UnityEngine;
public static class QuatCheck {
    static int fails=0; static void Check(bool ok, string w){ if(!ok){fails++; Console.WriteLine("  FAIL "+w);} }
    static bool Near(Vector3 a, Vector3 b){ return (a-b).magnitude < 1e-4f; }
    public static int Main(){
        Check(Near(Quaternion.AngleAxis(90f, Vector3.up)*Vector3.forward, Vector3.right), "AngleAxis(90,up)*forward == right (left-handed)");
        Vector3 a=new Vector3(0.3f,-0.7f,0.2f).normalized, b=new Vector3(-0.5f,0.1f,0.9f).normalized;
        Check(Near(Quaternion.FromToRotation(a,b)*a, b), "FromToRotation(a,b)*a == b");
        Quaternion q=Quaternion.AngleAxis(37f,new Vector3(1,2,3)); Check(Near((Quaternion.Inverse(q)*q)*a, a), "Inverse(q)*q == identity");
        Quaternion l=Quaternion.LookRotation(new Vector3(1,0,1), Vector3.up); Check(Near(l*Vector3.forward, new Vector3(1,0,1).normalized), "LookRotation forward");
        Check(Near(l*Vector3.up, Vector3.up), "LookRotation up");
        Check(Near(Quaternion.Euler(0,90,0)*Vector3.forward, Vector3.right), "Euler(0,90,0)*forward == right");
        Check(Near((Quaternion.AngleAxis(30f,Vector3.up)*Quaternion.AngleAxis(60f,Vector3.up))*Vector3.forward, Quaternion.AngleAxis(90f,Vector3.up)*Vector3.forward), "compose");
        Console.WriteLine(fails==0?"quaternion stub: real":"quaternion stub: "+fails+" FAILURES"); return fails;
    }
}
