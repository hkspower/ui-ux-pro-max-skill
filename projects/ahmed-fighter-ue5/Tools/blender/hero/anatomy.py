"""The body as lofted cross-sections. A trunk is one tapered form
with an ellipse at every height, a limb is a tube whose radius profile has
a belly, a head is a stack of skull sections; only the masses that really
sit on top of the form -- deltoid, pec, trap, glute -- are separate blobs.
Ahmed faces -Y; +X is his left; Z up."""
import bpy, bmesh, math, sys, os, time
from mathutils import Vector, Matrix
import build_ahmed as legacy
J = legacy.J
def Jp(n): return J[n][0]

# ------------------------------------------------------------- primitives
def loft(name, rings, segs=48, cap=True):
    """rings: list of (centre Vector, ux Vector, uy Vector) -- an ellipse is
    centre + cos(a)*ux + sin(a)*uy. Bridged into a closed tube."""
    bm = bmesh.new()
    rows = []
    for c, ux, uy in rings:
        row = [bm.verts.new(c + ux * math.cos(a) + uy * math.sin(a))
               for a in (2 * math.pi * i / segs for i in range(segs))]
        rows.append(row)
    for r0, r1 in zip(rows, rows[1:]):
        for i in range(segs):
            bm.faces.new((r0[i], r0[(i + 1) % segs], r1[(i + 1) % segs], r1[i]))
    if cap:
        bm.faces.new(list(reversed(rows[0])))
        bm.faces.new(rows[-1])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(o)
    return o

def tube(name, a, b, profile, front=Vector((0, -1, 0)), segs=40):
    """A limb: from a to b, profile = [(t, rx, ry, shift_front, shift_side)]
    rx across, ry front-to-back, shifts move the section off the bone
    line -- a belly sits forward of the bone, a hamstring behind it."""
    a, b = Vector(a), Vector(b); d = (b - a).normalized()
    f = (front - d * front.dot(d)).normalized()       # front, orthogonal to the bone
    s = d.cross(f).normalized()                        # side
    rings = []
    for t, rx, ry, sf, ss in profile:
        c = a + (b - a) * t + f * sf + s * ss
        rings.append((c, s * rx, f * ry))
    return loft(name, rings, segs)

def ellipsoid(name, centre, axes, axis=(0, 0, 1), segs=32, rings=20):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=segs, ring_count=rings, location=centre)
    o = bpy.context.object; o.name = name; o.scale = axes
    o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = Vector(axis).normalized().to_track_quat('Z', 'Y')
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    return o

def mirror_x(o):
    """A mirrored copy for the other side."""
    m = o.copy(); m.data = o.data.copy(); bpy.context.collection.objects.link(m)
    for v in m.data.vertices: v.co.x = -v.co.x
    m.data.flip_normals()
    m.name = o.name + "_r"; return m

X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
def ring_z(z, cx, cy, rx, ry): return (Vector((cx, cy, z)), X * rx, Y * ry)

# ------------------------------------------------------------------ trunk
def trunk():
    # (z, cy, rx, ry): half-width across, half-depth; cy shifts the section
    # forward/back. Hips wide and low, waist the narrow of the V, ribcage the
    # deepest part, the shoulder shelf the widest.
    rows = [
        (0.900, 0.010, 0.150, 0.100),   # below the hips, into the thighs
        (0.960, 0.012, 0.172, 0.114),   # hips
        (1.020, 0.012, 0.168, 0.112),
        (1.080, 0.006, 0.150, 0.104),   # waist
        (1.140, 0.002, 0.142, 0.100),
        (1.200, 0.004, 0.150, 0.106),   # lower ribs
        (1.270, 0.006, 0.160, 0.112),   # ribcage, deepest
        (1.340, 0.004, 0.166, 0.110),
        (1.400, 0.000, 0.172, 0.100),   # upper chest
        (1.445, -0.004, 0.176, 0.090),  # shoulder shelf
        (1.480, -0.002, 0.150, 0.078),  # into the neck
        (1.515, 0.002, 0.070, 0.062),
    ]
    return loft("trunk", [ring_z(z, 0, cy, rx, ry) for z, cy, rx, ry in rows])

def neck():
    rows = [(1.500, 0.006, 0.062, 0.062), (1.545, 0.004, 0.056, 0.060), (1.590, -0.004, 0.054, 0.064), (1.620, -0.010, 0.056, 0.068)]
    return loft("neck", [ring_z(z, 0, cy, rx, ry) for z, cy, rx, ry in rows], segs=32)

HEAD_ROWS = []
def head_surface_y(x, z, front=True):
    """Where the skull's surface is at (x, z): the loft's own ellipse."""
    rows = HEAD_ROWS
    if z <= rows[0][0]: r0 = r1 = rows[0]
    elif z >= rows[-1][0]: r0 = r1 = rows[-1]
    else:
        for r0, r1 in zip(rows, rows[1:]):
            if r0[0] <= z <= r1[0]: break
    t = 0.0 if r1[0] == r0[0] else (z - r0[0]) / (r1[0] - r0[0])
    cy = r0[1] + (r1[1] - r0[1]) * t; rx = r0[2] + (r1[2] - r0[2]) * t; ry = r0[3] + (r1[3] - r0[3]) * t
    k = max(0.0, 1.0 - (x / rx) ** 2) ** 0.5
    return cy - ry * k if front else cy + ry * k

def head():
    # A skull in cross-sections: from the chin up. cy is the section's
    # centre front/back (face is -Y). The crown is at 1.796.
    rows = [
        (1.572, -0.050, 0.030, 0.032),   # chin
        (1.590, -0.036, 0.054, 0.062),   # jaw
        (1.615, -0.022, 0.070, 0.084),   # jaw angle to the mouth
        (1.640, -0.014, 0.075, 0.092),   # cheek / nose base
        (1.668, -0.008, 0.078, 0.098),   # cheekbones, eyes
        (1.700, -0.002, 0.079, 0.100),   # brow / temples
        (1.735, 0.006, 0.077, 0.098),    # forehead, occiput fullest
        (1.765, 0.010, 0.068, 0.086),
        (1.786, 0.012, 0.050, 0.062),
        (1.796, 0.012, 0.018, 0.024),    # crown
    ]
    HEAD_ROWS[:] = rows
    return loft("head", [ring_z(z, 0, cy, rx, ry) for z, cy, rx, ry in rows], segs=48)

# ------------------------------------------------------------------ limbs
def arm():
    ua, la, hd = Jp("upperarm_l"), Jp("lowerarm_l"), Jp("hand_l")
    # radius profile: (t, rx across, ry front-back, shift front, shift side)
    upper = tube("upperarm", ua, la, [
        (-0.05, 0.055, 0.055, 0.000, 0.0),  # under the deltoid
        (0.15, 0.052, 0.054, -0.004, 0.0),
        (0.40, 0.050, 0.056, -0.010, 0.0),  # biceps belly forward, triceps back
        (0.60, 0.047, 0.050, -0.006, 0.0),
        (0.85, 0.040, 0.040, 0.000, 0.0),
        (1.02, 0.037, 0.038, 0.002, 0.0),   # elbow
    ])
    lower = tube("forearm", la, hd, [
        (-0.02, 0.037, 0.038, 0.000, 0.0),
        (0.20, 0.047, 0.043, -0.004, 0.002),  # flexor mass
        (0.45, 0.041, 0.037, -0.002, 0.0),
        (0.75, 0.032, 0.028, 0.000, 0.0),
        (1.00, 0.028, 0.020, 0.000, 0.0),     # wrist, a flattened oval
        (1.05, 0.027, 0.019, 0.000, 0.0),
    ])
    return [upper, lower]

def leg():
    th, cf, ft = Jp("thigh_l"), Jp("calf_l"), Jp("foot_l")
    thigh = tube("thigh", th, cf, [
        (-0.06, 0.084, 0.088, 0.004, 0.0),   # into the hip
        (0.15, 0.080, 0.086, -0.004, 0.0),
        (0.40, 0.074, 0.084, -0.010, 0.0),   # quads forward
        (0.65, 0.066, 0.076, -0.008, 0.0),
        (0.88, 0.056, 0.060, -0.002, 0.0),
        (1.02, 0.052, 0.056, 0.000, 0.0),    # knee
    ])
    shank = tube("shank", cf, ft, [
        (-0.02, 0.052, 0.056, 0.000, 0.0),
        (0.20, 0.054, 0.062, 0.006, 0.0),    # calf belly, behind the bone
        (0.45, 0.046, 0.052, 0.004, 0.0),
        (0.75, 0.036, 0.040, 0.000, 0.0),
        (0.98, 0.032, 0.038, 0.000, 0.0),    # ankle
        (1.04, 0.031, 0.037, 0.000, 0.0),
    ])
    return [thigh, shank]

def shoe():
    """The trainer, lofted along the foot: heel, arch, ball, toe."""
    x = Jp("foot_l").x
    rows = [  # (y, z-centre, half-width, half-height)
        (0.070, 0.038, 0.036, 0.036),    # heel back
        (0.040, 0.040, 0.041, 0.040),
        (-0.020, 0.040, 0.043, 0.040),
        (-0.080, 0.036, 0.046, 0.036),   # arch to ball
        (-0.140, 0.030, 0.048, 0.030),   # ball
        (-0.190, 0.024, 0.044, 0.024),
        (-0.220, 0.018, 0.030, 0.016),   # toe
    ]
    rings = [(Vector((x, y, zc)), X * rx, Z * rz) for y, zc, rx, rz in rows]
    return loft("shoe", rings, segs=32)

def hand():
    hd, he = Jp("hand_l"), Jp("hand_end_l")
    d = (he - hd).normalized(); n = Vector((0, -1, 0)); w = d.cross(n).normalized()
    parts = []
    # The palm: a slab lofted from the wrist to the knuckle row, wider at the
    # knuckles, thicker at the heel of the hand.
    rows = []
    for t, hw, hth, sf in [(0.0, 0.028, 0.018, 0.0), (0.30, 0.036, 0.020, -0.002),
                           (0.65, 0.041, 0.018, -0.003), (1.0, 0.043, 0.015, -0.004), (1.08, 0.040, 0.013, -0.004)]:
        c = hd + d * (0.108 * t) + n * sf
        rows.append((c, w * hw, n * hth))
    parts.append(loft("palm", rows, segs=28))
    fingers = [(0.031, (0.046, 0.028, 0.022), 0.0092),
               (0.010, (0.050, 0.031, 0.024), 0.0096),
               (-0.011, (0.046, 0.029, 0.023), 0.0090),
               (-0.031, (0.036, 0.024, 0.020), 0.0080)]
    joints = {}
    for i, (across, lens, r) in enumerate(fingers):
        reach = 0.108 - 0.012 * abs(across - 0.006) / 0.03
        cur = hd + d * reach + w * across - n * 0.003; dirv = d; pts = [cur.copy()]
        for k, L in enumerate(lens):
            rot = Matrix.Rotation(math.radians(-24.0), 4, w)
            dirv = (rot @ dirv).normalized()
            nxt = cur + dirv * L
            rr = r * (1.0 - 0.07 * k)
            parts.append(tube("f%d_%d" % (i, k), cur - dirv * rr * 0.9, nxt + dirv * rr * 0.5,
                              [(0.0, rr * 0.92, rr * 0.80, 0, 0), (0.5, rr, rr * 0.86, 0, 0), (1.0, rr * 0.90, rr * 0.78, 0, 0)],
                              front=n, segs=16))
            cur = nxt; pts.append(cur.copy())
        joints["f%d" % i] = pts
    # Thumb off the heel of the hand, angled out and forward.
    t0 = hd + d * 0.026 + w * 0.030 - n * 0.008
    t1 = t0 + (w * 0.62 + d * 0.50 - n * 0.40).normalized() * 0.044
    t2 = t1 + (w * 0.36 + d * 0.72 - n * 0.58).normalized() * 0.033
    t3 = t2 + (w * 0.18 + d * 0.78 - n * 0.60).normalized() * 0.027
    for k, (p, q, r) in enumerate([(t0, t1, 0.0150), (t1, t2, 0.0125), (t2, t3, 0.0105)]):
        parts.append(tube("thumb_%d" % k, p - (q - p).normalized() * r * 0.8, q + (q - p).normalized() * r * 0.5,
                          [(0.0, r * 0.9, r * 0.82, 0, 0), (0.5, r, r * 0.86, 0, 0), (1.0, r * 0.9, r * 0.8, 0, 0)], front=n, segs=16))
    parts.append(ellipsoid("thenar", hd + d * 0.048 + w * 0.030 - n * 0.004, (0.026, 0.017, 0.040), d))
    parts.append(ellipsoid("hypothenar", hd + d * 0.050 - w * 0.028 + n * 0.000, (0.016, 0.014, 0.040), d))
    joints["thumb"] = [t0, t1, t2, t3]
    return parts, joints

def masses():
    """The forms that sit on top of the lofts."""
    out = []
    out.append(ellipsoid("delt", (0.204, -0.006, 1.430), (0.066, 0.070, 0.074)))
    out.append(ellipsoid("pec", (0.078, -0.090, 1.372), (0.080, 0.032, 0.062)))
    out.append(ellipsoid("trap", (0.096, 0.022, 1.490), (0.046, 0.046, 0.072), (0.62, -0.10, -0.32)))
    out.append(ellipsoid("lat", (0.106, 0.062, 1.298), (0.058, 0.050, 0.108)))
    out.append(ellipsoid("glute", (0.086, 0.100, 0.958), (0.086, 0.060, 0.076)))
    out.append(ellipsoid("scm", (0.030, -0.030, 1.560), (0.014, 0.014, 0.045), (0.35, -0.55, 1.0)))
    return out

def union_remesh(parts, voxel, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts: o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join(); body = bpy.context.object; body.name = name
    body.data.remesh_voxel_size = voxel; body.data.remesh_voxel_adaptivity = 0.0
    bpy.ops.object.voxel_remesh(); return body

def smooth(obj, factor, iterations):
    m = obj.modifiers.new("S", "SMOOTH"); m.factor = factor; m.iterations = iterations
    bpy.context.view_layer.objects.active = obj; bpy.ops.object.modifier_apply(modifier="S")

def girths(body):
    """Torso circumference at a height: the outline of the section, arms
    excluded by width, walked round by angle from the section's centre."""
    co = [v.co for v in body.data.vertices]
    out = {}
    for label, z, xmax in [("chest", 1.36, 0.19), ("waist", 1.13, 0.17), ("hips", 0.99, 0.19),
                           ("neck", 1.55, 0.09), ("head", 1.700, 0.12), ("biceps", None, None)]:
        if z is None:
            ua, la = Jp("upperarm_l"), Jp("lowerarm_l"); c = ua + (la - ua) * 0.42; d = (la - ua).normalized()
            ring = [p for p in co if abs((p - c).dot(d)) < 0.006 and (p - c).length < 0.09]
            if not ring: out[label] = 0; continue
            f = Vector((0, -1, 0)); f = (f - d * f.dot(d)).normalized(); s = d.cross(f)
            pts = [((p - c).dot(s), (p - c).dot(f)) for p in ring]
        else:
            pts = [(p.x, p.y) for p in co if abs(p.z - z) < 0.005 and abs(p.x) < xmax]
        if len(pts) < 8: out[label] = 0; continue
        cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
        bins = {}
        for x, y in pts:
            a = int((math.atan2(y - cy, x - cx) + math.pi) / (2 * math.pi) * 72) % 72
            r = math.hypot(x - cx, y - cy)
            bins[a] = max(bins.get(a, 0), r)
        keys = sorted(bins)
        per = 0.0
        for i, k in enumerate(keys):
            k2 = keys[(i + 1) % len(keys)]
            a1 = (k + 0.5) / 72 * 2 * math.pi; a2 = (k2 + 0.5) / 72 * 2 * math.pi
            p1 = (bins[k] * math.cos(a1), bins[k] * math.sin(a1)); p2 = (bins[k2] * math.cos(a2), bins[k2] * math.sin(a2))
            per += math.dist(p1, p2)
        out[label] = per
    return out

def measure(body):
    zs = [v.co.z for v in body.data.vertices]
    print("stature   : %.3f m (crown %.3f, sole %.4f)" % (max(zs) - min(zs), max(zs), min(zs)))
    g = girths(body)
    print("girths    : " + "  ".join("%s %.3f" % (k, v) for k, v in g.items()))
    print("verts/tris: %d / %d" % (len(body.data.vertices), sum(len(p.vertices) - 2 for p in body.data.polygons)))
    return g

def build(stage_render=True):
    t = time.time()
    legacy.reset_scene()
    parts = [trunk(), neck(), head()]
    left = arm() + leg() + [shoe()] + masses()
    hl, jl = hand(); left += hl
    right = [mirror_x(o) for o in left]
    parts += left + right
    body = union_remesh(parts, 0.006, "Body")
    print("remesh 6mm: %d verts  %.1fs" % (len(body.data.vertices), time.time() - t))
    smooth(body, 1.0, 12)
    bpy.ops.object.shade_smooth()
    measure(body)
    return body, jl

