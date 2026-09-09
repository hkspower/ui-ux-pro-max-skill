"""Recompute every line of the dump independently in numpy, by a different
formulation than the C# uses: rotations go through 3x3 matrices rather than
the vector-form quaternion product, and the two-bone IK is solved from
scratch. Agreement means the two implementations agree; it is not Unity."""
import numpy as np, sys, collections
np.seterr(all='ignore')

def q2m(q):
    """Quaternion (x,y,z,w) to a rotation matrix. The standard matrix form --
    a different code path from the stub's u*(2u.v) + v(s^2-u.u) + 2s(u x v)."""
    x,y,z,w = q
    n = x*x+y*y+z*z+w*w
    if n < 1e-12: return np.eye(3)
    s = 2.0/n
    return np.array([
        [1-s*(y*y+z*z),   s*(x*y-z*w),   s*(x*z+y*w)],
        [  s*(x*y+z*w), 1-s*(x*x+z*z),   s*(y*z-x*w)],
        [  s*(x*z-y*w),   s*(y*z+x*w), 1-s*(x*x+y*y)]])

def axis_angle(deg, axis):
    """Rodrigues, with the LEFT-HANDED sign the anchor line pins down:
    Unity's AngleAxis(90, up) sends forward(+Z) to right(+X)."""
    a = np.array(axis, float); a /= np.linalg.norm(a)
    th = np.radians(deg)
    K = np.array([[0,-a[2],a[1]],[a[2],0,-a[0]],[-a[1],a[0],0]])
    return np.eye(3) + np.sin(th)*K + (1-np.cos(th))*(K@K)

worst = collections.defaultdict(float)
count = collections.Counter()
def note(kind, err):
    worst[kind] = max(worst[kind], float(err)); count[kind] += 1

def nums(parts): return [float(p) for p in parts]

for line in open(sys.argv[1]):
    p = line.split()
    k = p[0]
    if k == 'ANCHOR':
        v = np.array(nums(p[1:4]))
        note('anchor: AngleAxis(90,up)*forward == +X', np.linalg.norm(v-[1,0,0]))
    elif k == 'ANCHORCROSS':
        v = np.array(nums(p[1:4]))
        note('anchor: cross(up,forward) == +X (left-handed)', np.linalg.norm(v-[1,0,0]))
    elif k == 'AA':
        deg = float(p[1]); axis = nums(p[2:5]); q = nums(p[5:9])
        # compare the ROTATION, not the quaternion: q and -q are the same rotation
        note('AngleAxis vs Rodrigues', np.abs(q2m(q) - axis_angle(deg, axis)).max())
    elif k == 'ROT':
        q = nums(p[1:5]); v = np.array(nums(p[5:8])); got = np.array(nums(p[8:11]))
        note('q*v vs matrix@v', np.linalg.norm(q2m(q)@v - got))
    elif k == 'MUL':
        a = nums(p[1:5]); b = nums(p[5:9]); got = nums(p[9:13])
        note('qa*qb vs Ma@Mb', np.abs(q2m(got) - q2m(a)@q2m(b)).max())
    elif k == 'INV':
        a = nums(p[1:5]); got = nums(p[5:9])
        note('Inverse vs matrix transpose', np.abs(q2m(got) - q2m(a).T).max())
    elif k == 'F2R':
        a = np.array(nums(p[1:4])); b = np.array(nums(p[4:7])); q = nums(p[7:11])
        note('FromToRotation sends a to b', np.linalg.norm(q2m(q)@a - b))
    elif k == 'LOOK':
        f = np.array(nums(p[1:4])); u = np.array(nums(p[4:7])); q = nums(p[7:11])
        M = q2m(q)
        note('LookRotation: forward maps to +Z', np.linalg.norm(M@[0,0,1] - f))
        r = np.cross(u, f); r /= np.linalg.norm(r); up2 = np.cross(f, r)
        note('LookRotation: up is the orthogonalised up', np.linalg.norm(M@[0,1,0] - up2))
        note('LookRotation: orthonormal', np.abs(M@M.T - np.eye(3)).max())
    elif k == 'SLERP':
        a = np.array(nums(p[1:5])); b = np.array(nums(p[5:9])); t = float(p[9]); got = np.array(nums(p[10:14]))
        if np.dot(a,b) < 0: b = -b
        d = np.clip(np.dot(a,b), -1, 1); th = np.arccos(d)
        ref = (a*np.sin((1-t)*th) + b*np.sin(t*th))/np.sin(th) if np.sin(th) > 1e-6 else a
        ref /= np.linalg.norm(ref)
        note('Slerp vs great-circle', min(np.linalg.norm(got-ref), np.linalg.norm(got+ref)))
    elif k == 'CROSS':
        a = np.array(nums(p[1:4])); b = np.array(nums(p[4:7])); got = np.array(nums(p[7:10]))
        note('Vector3.Cross', np.linalg.norm(np.cross(a,b) - got))
    elif k == 'PROJ':
        v = np.array(nums(p[1:4])); n = np.array(nums(p[4:7])); got = np.array(nums(p[7:10]))
        note('ProjectOnPlane', np.linalg.norm(v - n*np.dot(v,n)/np.dot(n,n) - got))
    elif k == 'ANG':
        a = np.array(nums(p[1:4])); b = np.array(nums(p[4:7])); got = float(p[7])
        ref = np.degrees(np.arccos(np.clip(np.dot(a,b)/np.linalg.norm(a)/np.linalg.norm(b),-1,1)))
        note('Vector3.Angle', abs(ref-got))
    elif k == 'IK':
        f = nums(p[1:])
        root, mid, end = np.array(f[0:3]), np.array(f[3:6]), np.array(f[6:9])
        target, pole = np.array(f[9:12]), np.array(f[12:15])
        gm, ge = np.array(f[15:18]), np.array(f[18:21])
        L1, L2 = np.linalg.norm(mid-root), np.linalg.norm(end-mid)
        d = np.linalg.norm(target-root)
        # independent two-bone solve
        if d < 1e-5:
            continue
        ax = (target-root)/d
        bend = pole-root; bend = bend - ax*np.dot(bend,ax)
        if np.linalg.norm(bend) < 1e-5:
            bend = mid-root; bend = bend - ax*np.dot(bend,ax)
        if np.linalg.norm(bend) < 1e-5: continue
        bend /= np.linalg.norm(bend)
        if d >= L1+L2-1e-5:
            rm, re = root+ax*L1, root+ax*(L1+L2)
        else:
            inner = abs(L1-L2)
            if d < inner + 1e-5:
                d = inner + 1e-5
                target = root + ax*d
            x = (L1*L1 - L2*L2 + d*d)/(2*d)
            h = np.sqrt(max(0.0, L1*L1 - x*x))
            rm, re = root+ax*x+bend*h, target
        note('IK mid joint', np.linalg.norm(rm-gm))
        note('IK end', np.linalg.norm(re-ge))
        note('IK upper-arm length kept', abs(np.linalg.norm(gm-root)-L1))
        note('IK forearm length kept', abs(np.linalg.norm(ge-gm)-L2))

bad = 0
print(f"{'check':<46}{'cases':>7}{'worst disagreement':>22}")
for k in sorted(worst):
    tol = 3e-3 if k.startswith('IK') or 'Angle' in k else 3e-4
    flag = '' if worst[k] <= tol else '   <-- MISMATCH'
    if flag: bad += 1
    print(f"  {k:<44}{count[k]:>7}{worst[k]:>22.3e}{flag}")
print("\n" + ("every check agrees with the independent recomputation" if bad == 0
      else f"{bad} CHECKS DISAGREE"))
sys.exit(1 if bad else 0)
