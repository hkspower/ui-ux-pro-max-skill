"""The body as lofted cross-sections. A trunk is one tapered form
with an ellipse at every height, a limb is a tube whose radius profile has
a belly, a head is a stack of skull sections; only the masses that really
sit on top of the form -- deltoid, pec, trap, glute -- are separate blobs.
Saud faces -Y; +X is his left; Z up."""
import bpy, bmesh, math, sys, os, time
import numpy as np
from mathutils import Vector, Matrix
import build_saud as legacy
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
    line -- a belly sits forward of the bone, a hamstring behind it.

    shift_front is POSITIVE FORWARD, toward -Y, the way Saud faces. Checked,
    not assumed: for the thigh, the arm and the shank alike the frame comes
    out f = (0, -1, 0) to three decimals. Every profile in this file used to
    carry the opposite sign under a comment saying what it meant -- "biceps
    belly forward" at -0.010, "quads forward" at -0.010, "calf belly, behind
    the bone" at +0.006 -- so the three largest muscles on the body were each
    on the wrong side of their own bone."""
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
    # MEASURED, not guessed, and measured twice. The segment LENGTHS in
    # build_saud.J are right -- they came off Winter's tables and they check
    # out: upper arm 0.336 m against an ideal 0.338, forearm 0.263 against
    # 0.265, thigh 0.439 against 0.445. What was wrong was the WIDTHS.
    #
    # Sliced off the built mesh, the shoulder shelf was 0.352 m across and
    # the iliac row 0.316 -- a ratio of 1.11, where a young athletic male is
    # 1.45-1.55. The V everyone could see in the render was not the ribcage
    # at all: 193 mm of the 545 mm bideltoid breadth came from the deltoid
    # ellipsoid, which was 2.76 times as proud of the acromion as a real
    # deltoid is. A ball on each side of a cylinder, and the tee is a shell
    # off this surface, so the shirt reproduced it as a puffed sleeve.
    #
    # These rows put the V in the bone: biacromial 0.428, bi-iliac 0.292,
    # ratio 1.47; shoulder to waist 1.67.
    #
    # Measured again 2026-09-25 ("make full body fix"): the waist girth was
    # 0.744 m, a 28-inch waist on a 1.80 m fighter (an athletic male is
    # 0.80-0.84), the hips 0.82 against 0.95-1.00, and the pelvis was
    # NARROWER than the thigh tops it sat on -- 0.148 half-width at the hip
    # row over thigh tubes reaching 0.178 -- so the legs stood out from
    # under the trunk as two tubes with a step between (ZAYOS's "recessed
    # pelvis"). And the profile was a slab: cy within 12 mm of zero from the
    # hips to the shoulders, no small of the back, no thoracic curve. The
    # rows now carry the spine's S: the back comes IN 3 cm at the lumbar
    # (1.14) and OUT again over the ribcage (1.34), the front stays plumb.
    rows = [
        (0.900, 0.010, 0.150, 0.106),   # the pelvis floor, between the thighs' tops
        (0.930, 0.010, 0.172, 0.116),   # the trochanters: as wide as the thighs it sits on
        (0.960, 0.008, 0.180, 0.120),   # hips, the widest of the lower body
        (1.020, 0.002, 0.166, 0.114),   # the iliac crest
        (1.080, -0.006, 0.150, 0.104),  # waist
        (1.140, -0.008, 0.144, 0.100),  # the narrow of the V; the small of the back
        (1.200, -0.004, 0.158, 0.106),  # lower ribs
        (1.270, 0.004, 0.178, 0.114),   # ribcage, deepest
        (1.340, 0.010, 0.190, 0.116),   # the thoracic curve carries the back out
        (1.400, 0.012, 0.202, 0.106),   # upper chest
        (1.455, 0.006, 0.212, 0.096),   # a slope for the trapezius to sit on
        (1.478, 0.000, 0.214, 0.090),   # shoulder shelf, the widest bone
        (1.505, 0.000, 0.152, 0.078),
        (1.530, 0.002, 0.078, 0.064),   # into the neck
    ]
    return loft("trunk", [ring_z(z, 0, cy, rx, ry) for z, cy, rx, ry in rows])

def neck():
    # 0.112 m across measured, a 0.36 m circumference: thin for any man and
    # thin to the point of comedy on a fighter, who carries 0.40-0.42.
    # 2026-09-26 ("fix head shape"): the same girth, set back under the jaw.
    # Its front was at y -0.084 at the top, 5 mm behind the chin, so the
    # neck ran straight up into the chin and there was no jawline and no
    # plane under the chin (a man's throat is 45-55 mm behind his chin);
    # and it stood 140 mm deep, a column. Now 124 deep and 138 across,
    # leaning forward as a neck does (its front comes back 20 mm from the
    # base to the top), its back curving up under the skull.
    rows = NECK_ROWS
    return loft("neck", [ring_z(z, 0, cy, rx, ry) for z, cy, rx, ry in rows], segs=32)

NECK_ROWS = [(1.500, 0.008, 0.066, 0.068), (1.530, 0.012, 0.062, 0.062),
            (1.560, 0.014, 0.058, 0.059), (1.590, 0.015, 0.056, 0.057),
            (1.620, 0.016, 0.054, 0.056), (1.645, 0.020, 0.050, 0.055),
            (1.665, 0.024, 0.044, 0.052)]
# it runs on up inside the skull so the nape curves into the occiput:
# stopped at 1.620 its back stood 10 mm proud of the skull there, a ring
# round the back of the head

# The neck's muscles and the collarbones, as polylines with (across,
# through) radii per point and the direction they stand out along
# (2026-09-26, "fix neck"); assembly.masses builds them with
# assembly.chain. Left side (x > 0); masses mirrors them.
def _out_neck(c):
    """Outward from the neck's axis, level."""
    v = Vector((c.x, c.y - 0.012, 0.0))
    return v if v.length > 1e-6 else Vector((1.0, 0.0, 0.0))
def _out_up(c):
    """Up and a little out: the top of the shoulder."""
    return Vector((0.35 * (1 if c.x >= 0 else -1), 0.10, 1.0))
def _out_front(c):
    return Vector((0.25 * (1 if c.x >= 0 else -1), -1.0, 0.25))

def _out_trap(c):
    """Back and out on the neck, turning to up over the shoulder."""
    k = min(1.0, max(0.0, (1.560 - c.z) / 0.040))
    sx = 1 if c.x >= 0 else -1
    back = Vector((0.45 * sx, 1.0, 0.15)).normalized()
    up = Vector((0.30 * sx, 0.15, 1.0)).normalized()
    return back * (1.0 - k) + up * k

NECK_MUSCLES = {
    # the upper trapezius: a sheet, not a cord -- from the midline under the
    # occiput, down the back and side of the neck, over the top of the
    # shoulder to the acromion. Wide and thin at the neck (the two sides
    # meet over the spine), thickest over the top of the shoulder.
    "trap": ("trap",
             [(0.012, 0.058, 1.612), (0.026, 0.056, 1.580), (0.044, 0.050, 1.550),
              (0.078, 0.036, 1.524), (0.118, 0.026, 1.505), (0.160, 0.018, 1.489)],
             [(0.024, 0.006), (0.030, 0.008), (0.034, 0.011), (0.034, 0.013), (0.030, 0.012), (0.022, 0.008)],
             _out_trap),
    # the sternocleidomastoid: the mastoid, behind the ear, to the sternum
    "scm": ("scm",
            # the lower two on the chest's top, not the neck loft's: the
            # trunk stands in front of the neck there, and buried in it the
            # tendons were gone after the 6 mm remesh (no notch at all)
            [(0.049, 0.018, 1.626), (0.043, -0.010, 1.590), (0.034, -0.040, 1.548),
             (0.024, -0.071, 1.506), (0.017, -0.089, 1.478)],
            [(0.010, 0.008), (0.011, 0.010), (0.011, 0.010), (0.009, 0.009), (0.007, 0.008)],
            _out_neck),
    # the clavicle, the sternal end to the acromion, bowed forward in its
    # inner two thirds: a low ridge, not a bar
    "clavicle": ("clavicle",
                 # centres set off the chest's own front (measured on the trunk
                 # loft at each point) so each stands 3.5-5 mm proud of it: the
                 # sternal ends and the SCM's tendons either side of the
                 # jugular notch, the shaft a low ridge out to the shoulder
                 [(0.024, -0.0874, 1.470), (0.060, -0.0846, 1.474), (0.100, -0.0773, 1.480),
                  (0.140, -0.0610, 1.485), (0.170, -0.0460, 1.486)],
                 [(0.008, 0.007), (0.009, 0.007), (0.009, 0.007), (0.009, 0.0065), (0.008, 0.005)],
                 _out_front),
}

def _pchip(xs, ys, x):
    """Monotone cubic through (xs, ys) -- a curve that never overshoots its
    points, so a profile drawn through measurements stays between them."""
    xs = np.asarray(xs, float); ys = np.asarray(ys, float)
    h = np.diff(xs); d = np.diff(ys) / h
    m = np.zeros_like(ys)
    for i in range(1, len(xs) - 1):
        if d[i - 1] * d[i] > 0:
            w1 = 2 * h[i] + h[i - 1]; w2 = h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    m[0] = d[0]; m[-1] = 0.0
    i = np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2)
    t = (x - xs[i]) / h[i]
    h00 = 2 * t ** 3 - 3 * t ** 2 + 1; h10 = t ** 3 - 2 * t ** 2 + t
    h01 = -2 * t ** 3 + 3 * t ** 2; h11 = t ** 3 - t ** 2
    return h00 * ys[i] + h10 * h[i] * m[i] + h01 * ys[i + 1] + h11 * h[i] * m[i + 1]

# The skull, drawn from its profiles (2026-09-26, "fix head shape"). It was
# ten hand-set ellipses joined by straight segments, and measured on the
# built head: 210 mm long (a man is about 197), widest at the brow (a man's
# skull is widest behind it, above the ears), 153 mm across the cheekbones
# (about 141), 128 across the angles of the jaw (about 115) with a jaw as
# wide as the cranium above it -- a brick from the front -- and a top that
# ran out to a plateau 100 mm across and closed on a flat 36 x 48 mm cap,
# the flat patch that caught the light on every bald man. Now:
#
#   the cranium above HEAD_DOME_Z is a dome -- a superellipse (exponent
#   2.15, a shade fuller than an ellipse, as a skull is) from the forehead,
#   the widest point and the occiput to the crown, 1.796 as before;
#   below it, the midline front (the face, before the sculpt adds a
#   feature to it), the back (the occiput, then the underside of the jaw
#   running back from the chin to the angle) and the half-width are each a
#   smooth curve through the points in HEAD_PROFILE.
#
# HEAD_ROWS is still (z, cy, rx, ry) ellipses, every 3 mm and closer near
# the crown, because everything downstream reads the skull that way.
HEAD_DOME_Z = 1.718
HEAD_CROWN = (1.796, 0.004)                       # z of the vertex, and its y
HEAD_DOME = (0.103, 0.089, 0.0770, 2.15)          # front, back, half-width, exponent
HEAD_PROFILE = [
    # z       front     back     half-width
    (1.572, -0.0840, -0.0660, 0.0260),   # the chin's underside
    (1.575, -0.0880, -0.0480, 0.0340),
    (1.580, -0.0910, -0.0250, 0.0430),   # the jaw's lower border running back
    (1.588, -0.0940, +0.0000, 0.0510),
    (1.598, -0.0965, +0.0250, 0.0575),   # the angle of the jaw
    (1.608, -0.0990, +0.0450, 0.0610),
    (1.620, -0.1015, +0.0620, 0.0640),   # the mouth
    (1.635, -0.1035, +0.0740, 0.0670),
    (1.650, -0.1040, +0.0820, 0.0695),   # the cheekbones
    (1.668, -0.1030, +0.0870, 0.0715),
    (1.685, -0.1020, +0.0900, 0.0740),
    (1.700, -0.1005, +0.0915, 0.0760),   # the brow
]

def _dome(z):
    zc, (zt, yv) = HEAD_DOME_Z, HEAD_CROWN
    fa, ba, w, n = HEAD_DOME
    s = np.clip((z - zc) / (zt - zc), 0.0, 1.0)
    sin_t = s ** (n / 2.0)
    k = np.clip(1.0 - sin_t ** 2, 0.0, 1.0) ** 0.5
    k = k ** (2.0 / n)
    return yv - fa * k, yv + ba * k, w * k

def _head_rows():
    zs = list(np.arange(1.572, 1.7595, 0.003)) + list(np.arange(1.760, 1.7905, 0.0015)) \
        + [1.791, 1.792, 1.793, 1.794, 1.7948, 1.7954, 1.7958, 1.79595]
    pz = [p[0] for p in HEAD_PROFILE]
    df, db, dw = _dome(HEAD_DOME_Z)
    # the profile runs into the dome with the dome's own (zero) slope
    pz = pz + [HEAD_DOME_Z]
    pf = [p[1] for p in HEAD_PROFILE] + [df]
    pb = [p[2] for p in HEAD_PROFILE] + [db]
    pw = [p[3] for p in HEAD_PROFILE] + [dw]
    rows = []
    for z in zs:
        if z <= HEAD_DOME_Z:
            f, b, w = _pchip(pz, pf, z), _pchip(pz, pb, z), _pchip(pz, pw, z)
        else:
            f, b, w = _dome(z)
        rows.append((round(float(z), 5), float((f + b) / 2), float(w), float((b - f) / 2)))
    return rows

# A skull in cross-sections, from the chin up: (z, cy, rx, ry). cy is the
# section's centre front/back -- the face is -Y. The crown is at 1.796.
# This is module state, not something head() fills in, because the stages
# after the build read it too: --resume never calls head(), and hero.face
# asks it where the front of the skull is at a given height.
HEAD_ROWS = _head_rows()

def _at(rows, z):
    z = min(max(z, rows[0][0]), rows[-1][0])
    for r0, r1 in zip(rows, rows[1:]):
        if r0[0] <= z <= r1[0]:
            t = 0.0 if r1[0] == r0[0] else (z - r0[0]) / (r1[0] - r0[0])
            return tuple(a + (b - a) * t for a, b in zip(r0, r1))
    return rows[-1]

def check_head(rows=None, neck=None):
    """The skull and neck tables as a man's (2026-09-26), before anything is
    built -- the sculpt adds to them, so these are the bone's numbers:

    long 190-205 mm and broad 146-160, and broadest ABOVE the brow; the
    face narrower than the skull (the cheekbone row at least 8 mm under
    the breadth) and the jaw's angle narrower than the cheekbones; a
    rounded top (3 mm under the crown no more than 52 mm across, and no
    cap wider than 20); no kink down the face or over the dome (the
    midline profile turns no more than 0.12 rad in any 3 mm of it, a
    25 mm radius);
    and a neck set back under the jaw -- its front at least 30 mm behind
    the chin's at the chin's height -- and inside the skull at its top.
    Returns the numbers."""
    rows = rows or HEAD_ROWS; neck = neck or NECK_ROWS
    front = lambda z: _at(rows, z)[1] - _at(rows, z)[3]
    back = lambda z: _at(rows, z)[1] + _at(rows, z)[3]
    width = lambda z: 2.0 * _at(rows, z)[2]
    zs = np.arange(rows[0][0], rows[-1][0], 0.001)
    length = max(back(z) - front(z) for z in zs)
    wz = [width(z) for z in zs]; breadth = max(wz); bz = float(zs[int(np.argmax(wz))])
    cheek = width(1.656); gonion = width(1.600)
    top = width(rows[-1][0] - 0.003); cap = 2.0 * rows[-1][2]
    # the midline profile, front and back over the top, resampled every
    # 3 mm along its own length: how far it turns from one step to the
    # next is its curvature, fair on the face and over the dome alike
    fz = np.arange(1.585, rows[-1][0], 0.0005)
    line = np.array([(front(z), z) for z in fz] + [(back(z), z) for z in fz[::-1]])
    seg = np.linalg.norm(np.diff(line, axis=0), axis=1)
    arc = np.concatenate([[0.0], np.cumsum(seg)])
    t = np.arange(0.0, arc[-1], 0.003)
    pts = np.stack([np.interp(t, arc, line[:, 0]), np.interp(t, arc, line[:, 1])], axis=1)
    ang = np.unwrap(np.arctan2(np.diff(pts[:, 1]), np.diff(pts[:, 0])))
    kink = float(np.abs(np.diff(ang)).max())
    chin_z = 1.580
    nf = _at(neck, chin_z)[1] - _at(neck, chin_z)[3]
    set_back = nf - front(chin_z)
    ntop = neck[-1]
    inside = (ntop[1] + ntop[3] < back(ntop[0])) and (ntop[2] < width(ntop[0]) / 2)
    assert 0.190 <= length <= 0.205, "head %.0f mm long, want 190-205" % (length * 1000)
    assert 0.146 <= breadth <= 0.160, "head %.0f mm broad, want 146-160" % (breadth * 1000)
    assert bz > 1.705, "the head is broadest at %.3f, at the brow, not above it behind the brow" % bz
    assert cheek <= breadth - 0.008, "a brick: the face %.0f mm across the cheekbones against a skull %.0f" % (cheek * 1000, breadth * 1000)
    assert gonion < cheek - 0.010, "a brick: the jaw %.0f mm across at its angle, the cheekbones %.0f" % (gonion * 1000, cheek * 1000)
    assert top <= 0.052 and cap <= 0.020, "a flat top: %.0f mm across 3 mm under the crown, a %.0f mm cap" % (top * 1000, cap * 1000)
    assert kink <= 0.12, "a kink in the face or the dome: the profile turns %.2f rad in 3 mm" % kink
    assert set_back >= 0.030, "the neck runs into the chin: its front %.0f mm behind the chin's, want 30" % (set_back * 1000)
    assert inside, "the neck's top stands out of the skull: a ring round the back of the head"
    return dict(length=length, breadth=breadth, breadth_z=bz, cheek=cheek, gonion=gonion,
                top=top, cap=cap, kink=kink, set_back=set_back)

def check_neck(P, assert_=True):
    """The neck on the built base (pass one, canonical), 2026-09-26 ("fix
    neck"). P is (N,3) vertex positions. The shoulder line is the top of the
    surface seen from the front, at each |x|:

    no plateau -- it falls at least 0.35 (19 degrees) on average from the
    neck's side (x 80 mm) to 130 mm out (the old trapezius was a shelf there,
    -0.05 to 0.2); the trapezius climbs the neck -- 12 mm out from the neck
    column the line is at 1.545 or higher (the neck stood up out of a shelf
    at 1.533, a column on a table); the neck 0.40-0.46 m
    round at 1.55, a fighter's, with the muscles on it; and the SCM's
    tendons stand at least 2 mm proud of the midline at the base of the
    throat, so there is a jugular notch between them. Returns the numbers."""
    P = np.asarray(P)
    def top(x):
        b = P[(np.abs(np.abs(P[:, 0]) - x) < 0.003) & (P[:, 2] < 1.62) & (P[:, 2] > 1.35)
              & (np.abs(P[:, 1] - 0.02) < 0.06)]
        return float(b[:, 2].max())
    xs = np.arange(0.070, 0.2001, 0.010)
    line = np.array([top(x) for x in xs])
    i08, i13, i20 = [int(round((v - 0.070) / 0.010)) for v in (0.080, 0.130, 0.200)]
    # (the fall from the neck to the acromion is reported, not held: no
    # sabotage moved it without tripping the shelf rule first)
    plateau = (line[i08] - line[i13]) / 0.050
    # how high the trapezius climbs the neck: the shoulder line 12 mm out
    # from the neck column (its half-width just under the chin)
    wn = _at(NECK_ROWS, 1.575)[2]
    climb = top(wn + 0.012)
    fall = float(line[i08] - line[i20])
    girth = _girth_of(P, np.array([0.0, 0.012, 1.55]), np.array([0.0, 0.0, 1.0]), 0.095)
    def front(x, z):
        b = P[(np.abs(np.abs(P[:, 0]) - x) < 0.004) & (np.abs(P[:, 2] - z) < 0.005) & (P[:, 1] < 0)]
        return float(b[:, 1].min())
    notch = front(0.0, 1.488) - min(front(x, 1.488) for x in (0.014, 0.018, 0.022))
    if not assert_:
        return dict(plateau=plateau, climb=climb, fall=fall, girth=girth, notch=notch)
    assert 0.40 <= girth <= 0.46, "the neck %.3f m round at 1.55, want 0.40-0.46" % girth
    assert notch >= 0.002, "no jugular notch: the SCM's tendons %.1f mm proud of the midline, want 2" % (notch * 1000)
    assert plateau >= 0.35, "a shelf: the shoulder line falls only %.2f from the neck to 130 mm out, want 0.35" % plateau
    assert climb >= 1.545, "a column on the shoulders: the trapezius reaches only %.3f up the side of the neck, want 1.545" % climb
    return dict(plateau=plateau, climb=climb, fall=fall, girth=girth, notch=notch)

def bite_head():
    """check_head broken once per rule (numpy). Returns (caught, total)."""
    def rows_with(**kw):
        g = dict(globals())
        saved = {k: g[k] for k in kw}
        globals().update(kw)
        try: return _head_rows()
        finally: globals().update(saved)
    old_rows = [                        # the skull as it was until 2026-09-26
        (1.572, -0.050, 0.030, 0.032), (1.590, -0.036, 0.054, 0.062), (1.615, -0.022, 0.070, 0.084),
        (1.640, -0.014, 0.075, 0.092), (1.668, -0.008, 0.078, 0.098), (1.700, -0.002, 0.079, 0.100),
        (1.735, 0.006, 0.077, 0.098), (1.765, 0.010, 0.068, 0.086), (1.786, 0.012, 0.050, 0.062),
        (1.796, 0.012, 0.018, 0.024)]
    wide_jaw = [(z, f, b, max(w, 0.066) if z < 1.63 else w) for z, f, b, w in HEAD_PROFILE]
    brow_wide = [(z, f, b, 0.0800 if z >= 1.690 else w) for z, f, b, w in HEAD_PROFILE]
    kinked = [(z, f - (0.006 if z == 1.635 else 0.0), b, w) for z, f, b, w in HEAD_PROFILE]
    fwd_neck = [(z, cy - 0.030, rx, ry) for z, cy, rx, ry in NECK_ROWS]
    short_neck = NECK_ROWS[:5]
    bites = [
        ("the old skull", dict(rows=old_rows), "broadest"),
        ("flat top", dict(rows=rows_with(HEAD_DOME=(0.103, 0.089, 0.0770, 4.0))), "flat top"),
        ("wide jaw", dict(rows=rows_with(HEAD_PROFILE=wide_jaw)), "brick"),
        ("broad at brow", dict(rows=rows_with(HEAD_PROFILE=brow_wide)), "broadest"),
        ("kinked face", dict(rows=rows_with(HEAD_PROFILE=kinked)), "kink"),
        ("neck in chin", dict(neck=fwd_neck), "into the chin"),
        ("nape ring", dict(neck=short_neck), "ring"),
    ]
    caught = 0
    for label, kw, word in bites:
        try:
            check_head(**kw); print("  %-15s NOT caught" % label)
        except AssertionError as e:
            ok = word in str(e); caught += ok
            print("  %-15s %s  %s" % (label, "caught" if ok else "WRONG CHECK", e))
    return caught, len(bites)

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

def head_surface_x(y, z):
    """The skull's half-width at depth y and height z: the loft's ellipse."""
    rows = HEAD_ROWS
    if z <= rows[0][0]: r0 = r1 = rows[0]
    elif z >= rows[-1][0]: r0 = r1 = rows[-1]
    else:
        for r0, r1 in zip(rows, rows[1:]):
            if r0[0] <= z <= r1[0]: break
    t = 0.0 if r1[0] == r0[0] else (z - r0[0]) / (r1[0] - r0[0])
    cy = r0[1] + (r1[1] - r0[1]) * t; rx = r0[2] + (r1[2] - r0[2]) * t; ry = r0[3] + (r1[3] - r0[3]) * t
    return rx * max(0.0, 1.0 - ((y - cy) / ry) ** 2) ** 0.5

def head():
    rows = HEAD_ROWS
    return loft("head", [ring_z(z, 0, cy, rx, ry) for z, cy, rx, ry in rows], segs=48)

# ------------------------------------------------------------------ limbs
def arm(scale=1.0):
    """scale > 1 thickens the muscle bellies -- the biceps, the forearm's
    flexor mass -- and leaves the elbow and wrist close to their own width,
    since those read as bone and tendon under the skin and do not grow with
    the muscle around them. Weighted per ring, 1.0 at a belly fading to
    near 0 at a joint, not a flat multiply of the whole limb."""
    ua, la, hd = Jp("upperarm_l"), Jp("lowerarm_l"), Jp("hand_l")
    def bulk(rx, ry, sf, ss, w):
        k = 1.0 + (scale - 1.0) * w
        return (rx * k, ry * k, sf * k, ss * k)
    # radius profile: (t, rx across, ry front-back, shift front, shift side)
    # The old profile fell from 0.055 at the shoulder to 0.037 at the elbow
    # without a single rise: measured across, the arm had no biceps at all in
    # the view the game is played from, and the elbow was the narrowest point
    # of the whole limb. A joint is a local MAXIMUM across and a minimum in
    # depth -- that is what makes it read as bone under skin.
    upper = tube("upperarm", ua, la, [
        (-0.05,) + bulk(0.048, 0.050, 0.000, 0.0, 0.50),  # tapers IN under the deltoid
        (0.18,) + bulk(0.052, 0.058, +0.006, 0.0, 0.85),
        (0.42,) + bulk(0.055, 0.065, +0.014, 0.0, 1.00),  # biceps belly forward, triceps back
        (0.64,) + bulk(0.049, 0.058, +0.009, 0.0, 0.80),
        (0.86,) + bulk(0.039, 0.044, +0.002, 0.0, 0.35),  # the narrowing above the elbow
        (1.02,) + bulk(0.044, 0.038, 0.000, 0.0, 0.05),   # elbow: wide across, shallow through
    ])
    lower = tube("forearm", la, hd, [
        (-0.02,) + bulk(0.044, 0.038, 0.000, 0.0, 0.25),
        # the brachioradialis and the extensors, the forearm's big belly, sit
        # on the RADIAL (thumb) side: with the palm forward in the A-pose that
        # is the side away from the body, which is -s here (s = d x f points
        # in toward the body). It was +0.009, on the ulnar side.
        (0.30,) + bulk(0.046, 0.052, +0.005, -0.009, 1.00),
        (0.55,) + bulk(0.039, 0.043, +0.003, 0.004, 0.60),
        (0.80,) + bulk(0.031, 0.030, 0.000, 0.0, 0.25),
        (1.00,) + bulk(0.030, 0.023, 0.000, 0.0, 0.0),      # wrist, a flattened oval (0.17 m round)
        (1.05,) + bulk(0.029, 0.022, 0.000, 0.0, 0.0),
    ])
    return [upper, lower]

def leg():
    th, cf, ft = Jp("thigh_l"), Jp("calf_l"), Jp("foot_l")
    # Measured 2026-09-25: the knee was 0.352 m round against a real 0.38-
    # 0.40, and the vastus medialis was shifted OUTWARD -- s = d x f is -X on
    # the left leg, toward the midline, so "inside" is +ss, not -ss. The
    # thigh is fuller through its upper third (a fighter's 0.60 m) and the
    # knee wider across, so the leg reads thigh / knee / calf, not a taper.
    thigh = tube("thigh", th, cf, [
        # The upper thigh is deeper than it is wide and sits OUT from the
        # hip joint (ss < 0 is away from the midline): with hip joints
        # 0.184 m apart, thighs 0.176 wide on the joint touched and welded
        # down to 0.79, a crotch 11 cm under mid-height. Parted, the crotch
        # is the pelvis floor at 0.900.
        (-0.06, 0.082, 0.096, +0.004, -0.010),  # into the hip
        (0.16, 0.084, 0.100, +0.008, -0.008),   # the thigh's fullest
        (0.40, 0.080, 0.092, +0.013, -0.002),   # quadriceps forward, hamstring behind
        (0.62, 0.072, 0.080, +0.010, 0.0),
        (0.82, 0.061, 0.066, +0.005, 0.0),   # the pinch above the knee
        (0.92, 0.062, 0.060, +0.003, +0.005),# vastus medialis, on the inside
        (1.02, 0.064, 0.056, 0.000, 0.0),    # knee: wide across, shallow through
    ])
    # The calf measured 1 mm wider than the knee and 4 mm deeper, and it sat
    # in FRONT of the tibia. It is a mass hanging off the back, its medial
    # head high and its lateral head lower, and it is what makes a shin read
    # as a shin rather than as a dowel.
    shank = tube("shank", cf, ft, [
        (-0.02, 0.056, 0.056, 0.000, 0.0),
        (0.16, 0.058, 0.074, -0.014, 0.004),  # gastrocnemius, behind the bone
        (0.32, 0.055, 0.068, -0.011, -0.003), # the lateral head, lower
        (0.58, 0.044, 0.050, -0.005, 0.0),
        (0.82, 0.035, 0.038, -0.001, 0.0),
        (0.98, 0.032, 0.040, 0.000, 0.0),     # ankle
        (1.04, 0.031, 0.039, 0.000, 0.0),
    ])
    return [thigh, shank]

def shoe():
    """The trainer, lofted along the foot: heel, arch, ball, toe."""
    x = Jp("foot_l").x
    # The toe box holds its height to the toes and rounds off in the last
    # two centimetres: the old rows halved it from the ball to the toe, and
    # the topline sloped down to a point (CLAUDE.md, "the trainers read as
    # pointed dress heels" -- fixed 2026-09-25).
    rows = [  # (y, z-centre, half-width, half-height)
        (0.070, 0.038, 0.036, 0.036),    # heel back
        (0.040, 0.040, 0.041, 0.040),
        (-0.020, 0.040, 0.043, 0.040),
        (-0.080, 0.037, 0.046, 0.037),   # arch to ball
        (-0.140, 0.032, 0.048, 0.032),   # ball
        (-0.190, 0.029, 0.046, 0.029),   # the toe box
        (-0.228, 0.024, 0.036, 0.022),
        (-0.245, 0.018, 0.020, 0.014),   # toe
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
    # Three things were wrong with this hand, all of them measurable against
    # the fist the joint table already describes (knuckle_1..4, phalanx_1..4,
    # tip_1..4 in build_saud._LIMB, which are shaping joints nothing reads,
    # so they recorded the intent and the mesh quietly contradicted it):
    #
    #   `w` is d x n and comes out pointing back and DOWN the knuckle row, so
    #   a positive `across` put f0 -- named "index" by rig_export.FINGERS --
    #   where the pinky belongs and the thumb on the outside of the hand.
    #   Pairing the built tips against the table's the other way round fits to
    #   11.7 mm instead of 40.7, which is what said so.
    #
    #   The curl was -24 degrees at each of the three joints: 72 degrees in
    #   total, and in the wrong direction -- the fingers bent toward the BACK
    #   of the hand. Wrist to fingertip measured 0.193 m, which is the
    #   canonical OPEN hand for this stature. A fist is about 0.115.
    #
    #   The three joints do not bend alike. Fitted against the table:
    #   72 at the knuckle, 109 at the middle joint, 36 at the last.
    #
    # `across` is negative toward the index side, so the row is reversed here
    # and the reach arcs about the middle finger's knuckle.
    fingers = [(-0.031, (0.046, 0.028, 0.022), 0.0092),   # index
               (-0.010, (0.050, 0.031, 0.024), 0.0096),   # middle, the longest
               (0.011, (0.046, 0.029, 0.023), 0.0090),    # ring
               (0.031, (0.036, 0.024, 0.020), 0.0080)]    # pinky, the shortest
    CURL = (72.0, 109.0, 36.0)
    joints = {}
    for i, (across, lens, r) in enumerate(fingers):
        reach = 0.108 - 0.012 * abs(across + 0.006) / 0.03
        cur = hd + d * reach + w * across - n * 0.003; dirv = d; pts = [cur.copy()]
        for k, L in enumerate(lens):
            rot = Matrix.Rotation(math.radians(CURL[k]), 4, w)
            dirv = (rot @ dirv).normalized()
            nxt = cur + dirv * L
            rr = r * (1.0 - 0.07 * k)
            parts.append(tube("f%d_%d" % (i, k), cur - dirv * rr * 0.9, nxt + dirv * rr * 0.5,
                              [(0.0, rr * 0.92, rr * 0.80, 0, 0), (0.5, rr, rr * 0.86, 0, 0), (1.0, rr * 0.90, rr * 0.78, 0, 0)],
                              front=n, segs=16))
            cur = nxt; pts.append(cur.copy())
        joints["f%d" % i] = pts
    # Thumb off the heel of the hand, angled out and forward.
    # The thumb lies across the front of the fingers, on the index side --
    # which is -w, not +w, so it used to sit on the outside of the hand.
    t0 = hd + d * 0.026 - w * 0.030 - n * 0.008
    t1 = t0 + (-w * 0.62 + d * 0.50 - n * 0.40).normalized() * 0.044
    t2 = t1 + (-w * 0.36 + d * 0.72 - n * 0.58).normalized() * 0.033
    t3 = t2 + (-w * 0.18 + d * 0.78 - n * 0.60).normalized() * 0.027
    for k, (p, q, r) in enumerate([(t0, t1, 0.0150), (t1, t2, 0.0125), (t2, t3, 0.0105)]):
        parts.append(tube("thumb_%d" % k, p - (q - p).normalized() * r * 0.8, q + (q - p).normalized() * r * 0.5,
                          [(0.0, r * 0.9, r * 0.82, 0, 0), (0.5, r, r * 0.86, 0, 0), (1.0, r * 0.9, r * 0.8, 0, 0)], front=n, segs=16))
    parts.append(ellipsoid("thenar", hd + d * 0.048 - w * 0.030 - n * 0.004, (0.026, 0.017, 0.040), d))
    parts.append(ellipsoid("hypothenar", hd + d * 0.050 + w * 0.028 + n * 0.000, (0.016, 0.014, 0.040), d))
    joints["thumb"] = [t0, t1, t2, t3]
    return parts, joints

# How far a glove's thumb stands off the thumb inside it: the padding. A
# thumb segment is 10.5-15 mm in radius; with this it is 22.5-27.
GLOVE_THUMB_PAD = 0.012


def glove(scale=1.0, thumb=None):
    """A boxing glove, over the fist -- ZAYOS (`look.hands: 'gloves'`).

    Not a padded fist: its own shape, unioned OVER hand()'s fingers rather
    than replacing them, in the same (d, n, w) frame hand() uses. hand()
    still runs and still returns real joints -- the mannequin skeleton is
    the same 62 bones for every fighter, boss included, so ZAYOS gets real
    finger bones whether or not a finger is ever separately visible -- and
    the glove only has to be bigger than the curled fist everywhere along
    its length, so the union's remesh takes the glove's outer envelope and
    the fingers inside it vanish. Checked on the built hand, not assumed:
    the palm's own widest point is 0.043 across and 0.015-0.020 through: a
    glove half-width of 0.050-0.060 and half-thickness of 0.045-0.055 over
    the same span clears a curled finger's ~0.019 diameter folded against
    it with room to spare.

    These numbers are chosen, not measured -- there is no reference for a
    game glove the way there was a Winter's-tables reference for a hand --
    the way `pipeline.FACES`' amplitudes are chosen. `scale` moves the
    whole glove without retyping every row, for a heavier pair later.
    """
    hd, he = Jp("hand_l"), Jp("hand_end_l")
    d = (he - hd).normalized(); n = Vector((0, -1, 0)); w = d.cross(n).normalized()
    L = 0.135
    rows = []
    for t, hw, hth, sf in [
        (-0.38, 0.038, 0.034, 0.000),   # the cuff, flared over the forearm
        (-0.20, 0.032, 0.029, 0.000),   # narrows to the wrist
        (0.00, 0.034, 0.031, 0.000),    # the wrist
        (0.18, 0.050, 0.045, -0.004),   # the padding starts to bulge
        (0.42, 0.060, 0.054, -0.008),   # the fist, at its fattest
        (0.66, 0.057, 0.050, -0.010),   # the punching face
        (0.84, 0.042, 0.036, -0.010),   # rounding off
        (0.96, 0.020, 0.018, -0.008),   # the closed tip
    ]:
        c = hd + d * (L * t * scale) + n * (sf * scale)
        rows.append((c, w * (hw * scale), n * (hth * scale)))
    parts = [loft("glove", rows, segs=32)]
    if thumb is None:
        # the thumb lobe: one rounded pad, not an articulated thumb -- a glove
        # does not have knuckles in it
        ta = (-w * 0.55 + d * 0.62 - n * 0.35).normalized()
        tc = hd + d * (L * 0.14 * scale) - w * (0.055 * scale) - n * (0.006 * scale)
        parts.append(ellipsoid("glovethumb", tc + ta * (0.032 * scale), (0.024 * scale, 0.021 * scale, 0.038 * scale), ta))
        return parts
    # The thumb's sleeve, over the thumb hand() actually built (its joints,
    # `thumb`): a padded tube down each segment and a round cap on the tip.
    # The fixed lobe above was drawn for where a thumb might be, and the
    # hand's thumb is not there -- measured, its middle joint 0.086 and its
    # tip 0.100 off the hand's axis where the lobe ends at 0.103 and misses
    # both (a lobe metric of 2.4 and 5.6, inside is under 1): ZAYOS's bare
    # thumb, nail and all, stood out of the top of both gloves.
    pad = GLOVE_THUMB_PAD * scale
    for k, (a, b, r) in enumerate(zip(thumb[:-1], thumb[1:], (0.0150, 0.0125, 0.0105))):
        R = r + pad
        ax = (b - a).normalized()
        parts.append(tube("glovethumb_%d" % k, a - ax * R * 0.6, b + ax * R * 0.3,
                          [(0.0, R, R * 0.9, 0, 0), (0.5, R, R * 0.9, 0, 0), (1.0, R, R * 0.9, 0, 0)], front=n, segs=20))
    tip = thumb[-1]; ax = (thumb[-1] - thumb[-2]).normalized()
    parts.append(ellipsoid("glovethumbtip", tip, ((0.0105 + pad),) * 2 + ((0.0105 + pad) * 1.1,), ax))
    return parts

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

def measure(body, check=True):
    zs = [v.co.z for v in body.data.vertices]
    stature = max(zs) - min(zs)
    print("stature   : %.3f m (crown %.3f, sole %.4f)" % (stature, max(zs), min(zs)))
    # How tall he is IN HEADS, counted the way a viewer counts it -- from the
    # top of the hair, not the top of the skull. The skull was always right:
    # crown 1.796 over a chin at 1.572 is 8.04 heads, the figure the art
    # direction asks for. But the hair used to stand 22 mm above the skull,
    # and 22 mm of hair on a 226 mm head costs 0.7 of a head: he measured
    # 8.04 and read 7.33, and every judgement of him as stumpy came from
    # that. It is the cheapest number on the model to get wrong and the most
    # expensive to leave wrong, so the build asserts it now.
    from .sculpt import CHIN_Z
    heads = stature / max(max(zs) - CHIN_Z, 1e-6)
    print("heads tall: %.2f  (head %.3f m, crown to chin, hair included)"
          % (heads, max(zs) - CHIN_Z))
    if check:
        assert abs(stature - legacy.HEIGHT) < 0.010, (
            "stature drifted to %.3f m against a declared HEIGHT of %.2f" % (stature, legacy.HEIGHT))
        assert heads >= 7.70, (
            "he reads %.2f heads tall, not eight -- almost always hair standing "
            "proud of the skull (crown %.4f, chin %.4f)" % (heads, max(zs), CHIN_Z))
    g = girths(body)
    print("girths    : " + "  ".join("%s %.3f" % (k, v) for k, v in g.items()))
    print("verts/tris: %d / %d" % (len(body.data.vertices), sum(len(p.vertices) - 2 for p in body.data.polygons)))
    n = len(body.data.vertices); P = np.empty(n * 3); body.data.vertices.foreach_get("co", P)
    for k, v in proportions(P.reshape(n, 3)).items():
        g[k] = v
    print("body      : " + "  ".join("%s %.3f" % (k, v) for k, v in g.items() if k in PROPORTIONS))
    if check:
        check_proportions(g)
    return g


# What an athletic 1.80 m male measures, and the band the canonical body
# is held to (2026-09-25, "make full body fix"). Girths in metres round the
# body; the crotch is the height of the perineum -- mid-height, the
# eight-heads figure's -- and hip_step is the pelvis's half-width just
# above the thigh tops (1.00) over the hips' with them (0.96): 0.82 on the
# old body, whose pelvis was narrower than its own thighs and read as two
# tubes with a step between them; 0.91 now.
PROPORTIONS = {
    "waist": (0.76, 0.88), "hips": (0.92, 1.08), "chest": (1.00, 1.14), "neck": (0.40, 0.46),
    "thigh": (0.56, 0.66), "knee": (0.36, 0.42), "calf": (0.37, 0.43), "crotch": (0.885, 0.915),
    "hip_step": (0.88, 1.05),
}


def _girth_of(P, c, d, R):
    q = P - c; along = q @ d
    ring = (np.abs(along) < 0.004) & (np.linalg.norm(q - np.outer(along, d), axis=1) < R)
    if ring.sum() < 8:
        return 0.0
    f = np.array([0.0, -1.0, 0.0]); f = f - d * (f @ d); f /= np.linalg.norm(f); s = np.cross(d, f)
    u, v = q[ring] @ s, q[ring] @ f
    bins = {}
    for uu, vv in zip(u, v):
        k = int((math.atan2(vv, uu) + math.pi) / (2 * math.pi) * 72) % 72
        bins[k] = max(bins.get(k, 0.0), math.hypot(uu, vv))
    ks = sorted(bins); per = 0.0
    for i, k in enumerate(ks):
        k2 = ks[(i + 1) % len(ks)]; a1 = (k + .5) / 72 * 2 * math.pi; a2 = (k2 + .5) / 72 * 2 * math.pi
        per += math.dist((bins[k] * math.cos(a1), bins[k] * math.sin(a1)), (bins[k2] * math.cos(a2), bins[k2] * math.sin(a2)))
    return per


def proportions(P):
    """The limb girths, the crotch and the hip step of a body's points
    (N,3), at canonical coordinates. Torso girths are girths()'s."""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    out = {}
    m = (np.abs(x) < 0.008) & (np.abs(y) < 0.07) & (z > 0.6) & (z < 1.02)
    out["crotch"] = float(z[m].min()) if m.any() else 0.0
    def leg(a, b, t, R):
        a, b = np.array(Jp(a)), np.array(Jp(b)); d = (b - a) / np.linalg.norm(b - a)
        return _girth_of(P, a + (b - a) * t, d, R)
    out["thigh"] = leg("thigh_l", "calf_l", 0.22, 0.105)
    out["knee"] = leg("thigh_l", "calf_l", 1.0, 0.09)
    out["calf"] = leg("calf_l", "foot_l", 0.18, 0.09)
    def half(z0, xmax):
        mm = (np.abs(z - z0) < 0.003) & (np.abs(x) < xmax); return float(np.abs(x[mm]).max()) if mm.any() else 0.0
    out["hip_step"] = half(1.00, 0.23) / max(half(0.96, 0.23), 1e-6)
    return out


def check_proportions(g):
    bad = ["%s %.3f (%.2f-%.2f)" % (k, g.get(k, 0.0), lo, hi) for k, (lo, hi) in PROPORTIONS.items()
           if not (lo <= g.get(k, 0.0) <= hi)]
    assert not bad, "the body is off an athletic male's proportions: " + ", ".join(bad)

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



# ================================================================== the build
# How one man's body differs from another's, the way the browser build says
# it does. index.html draws every fighter from ONE figure and then scales
# it: `sc` scales the whole sprite (:1379), and `build` -- "limb thickness:
# 1 is lean" (:1567) -- multiplies the limb radii and widens the torso by
# 1 + (build - 1) * 0.7, "widen chest, keep height" (:1600). The head and
# the hands are not touched by `build`. The body this module builds IS
# Saud, whose own entry is sc 1.05, build 1.12 (assets/saud.js), so every
# other man is that body taken through the same three numbers relative to
# his. It is applied to the finished, painted, baked mesh and to the joint
# table together, after the bake and before the armature, so that every
# absolute constant upstream -- EYE_Z, HAIRLINE, the tee's hem, the UV
# charts -- is evaluated once, at the one set of coordinates it was written
# for.

def _smooth(t):
    t = np.clip(t, 0.0, 1.0); return t * t * (3.0 - 2.0 * t)

def build_field(sc, build):
    """The three factors and the field, for a man of (sc, build).

    Returns (h, l, t, F) where F maps (N,3) canonical positions to the
    man's own. h is the uniform stature factor, l the limb-thickness
    factor, t the torso-width factor; all relative to Saud's own entry,
    read from the roster rather than typed here. Everything the field
    needs of the joint table is captured HERE, at canon, so the field is
    the same function whether it is applied to a mesh before the joints
    or after them.
    """
    from . import roster
    a = roster.spec("saud")
    h = sc / a["sc"]
    l = build / a["look"]["build"]
    t = (1.0 + 0.7 * (build - 1.0)) / (1.0 + 0.7 * (a["look"]["build"] - 1.0))
    # The head grows less than the body (2026-09-25, "arrange sizes"): a
    # sprite scaled by sc keeps its proportions, but a man half again as
    # tall is not a scaled-up man -- he is more heads tall. h ** 0.65 puts
    # ZAYOS (h 1.48) at 9.1 heads to Saud's 7.9, AL-WAHSH at 8.4, the thug
    # (h 0.95) at 7.8: giants with small heads and a short man whose head
    # sits big on him, which is how they read apart. About a pivot at the
    # top of the neck, blended over it, so the neck is his and the skull
    # is scaled. The hands stay with the body, as the browser leaves them.
    hk = h ** 0.65
    HEAD_PIVOT = np.array([0.0, 0.0, 1.58])

    def seg(p, q, s):
        return (np.array(Jp(p)) * np.array([s, 1, 1]), np.array(Jp(q)) * np.array([s, 1, 1]))
    limbs = []          # (polyline, radius of influence, end blends as fractions of arc length, ramp in)
    arms = []           # the arm polylines with the hand, for the rigid shift
    for s in (1, -1):
        sh, el = seg("upperarm_l", "lowerarm_l", s); wr = seg("lowerarm_l", "hand_l", s)[1]; tip = seg("hand_l", "hand_end_l", s)[1]
        hip, kn = seg("thigh_l", "calf_l", s); an = seg("calf_l", "foot_l", s)[1]
        limbs.append(([sh, el, wr], 0.115, (0.12, 0.90), 0.10))
        # The thigh comes in over 40 % of the leg, not 10: over 4 cm of
        # thigh, x1.43 on ZAYOS stepped the trouser legs out from under the
        # pelvis as two open-topped tubes, rim and all, the moment there was
        # no tee over the waist to hide it.
        limbs.append(([hip, kn, an], 0.150, (0.02, 0.93), 0.40))
        arms.append(([sh, el, wr, tip + (tip - wr) * 0.6], 0.16))
    shoulder_x = abs(Jp("upperarm_l").x)
    hip_x = abs(Jp("thigh_l").x)

    def along(P, pts):
        """distance to a polyline, the fraction along it, and the foot of the perpendicular"""
        total = sum(np.linalg.norm(pts[i + 1] - pts[i]) for i in range(len(pts) - 1))
        best_d = np.full(len(P), np.inf); best_u = np.zeros(len(P)); best_foot = np.zeros_like(P)
        acc = 0.0
        for i in range(len(pts) - 1):
            a_, b_ = pts[i], pts[i + 1]; ab = b_ - a_; L = np.linalg.norm(ab); d = ab / L
            q = P - a_; tt = np.clip(q @ d, 0.0, L)
            foot = a_ + np.outer(tt, d); dist = np.linalg.norm(P - foot, axis=1)
            closer = dist < best_d
            best_d[closer] = dist[closer]; best_u[closer] = (acc + tt[closer]) / total; best_foot[closer] = foot[closer]
            acc += L
        return best_d, best_u, best_foot

    def F(P):
        P0 = np.array(P, dtype=float).reshape(-1, 3)
        P = P0.copy()
        if abs(l - 1.0) > 1e-9:
            # limb thickness: radial about each limb's own axis, fading to
            # nothing at the joint it hangs from and at the wrist or ankle,
            # so the hands, the feet and the shoulder stay the size they are.
            # Every limb's weight is taken off the ORIGINAL positions and a
            # point belongs to the limb whose field is strongest on it, so
            # the inner thighs are thinned once, the same on both sides.
            best_w = np.zeros(len(P)); best_foot = P0.copy()
            for pts, R, (u0, u1), ramp in limbs:
                d, u, foot = along(P0, pts)
                w = _smooth((u - u0) / ramp) * (1.0 - _smooth((u - u1) / 0.07))
                w = w * (1.0 - _smooth((d - R * 0.75) / (R * 0.25)))
                take = w > best_w
                best_w[take] = w[take]; best_foot[take] = foot[take]
            P = best_foot + (P0 - best_foot) * (1.0 + (l - 1.0) * best_w)[:, None]
        if abs(t - 1.0) > 1e-9:
            # torso width: x scaled about the midline through the trunk, and
            # each arm carried inward, WHOLE and rigidly -- hand included --
            # by the shoulder's own displacement, so the two rules agree at
            # the joint and nothing between the wrist and the knuckles is
            # sheared. An arm point is one within reach of the arm's
            # polyline, wrist to fingertip included; everything else takes
            # the trunk rule, faded out below the hips and at the neck.
            x, z = P0[:, 0], P0[:, 2]
            band = _smooth((z - 0.96) / 0.04) * (1.0 - _smooth((z - 1.49) / 0.03))
            shift = np.sign(x) * np.minimum(np.abs(x), shoulder_x) * (t - 1.0) * band
            arm_w = np.zeros(len(P))
            for pts, R in arms:
                d, u, foot = along(P0, pts)
                arm_w = np.maximum(arm_w, 1.0 - _smooth((d - R * 0.7) / (R * 0.3)))
            # The legs: carried outward WHOLE by the hip joint's own
            # displacement, as the arms are by the shoulder's. Until
            # 2026-09-23 the widening stopped at the hips, so a man whose
            # limbs thicken (ZAYOS: legs x1.43, torso x1.31) kept Saud's leg
            # spacing under legs half again as thick: his knees met (0.2 cm
            # apart where Saud's are 5), bone heat mixed the two legs across
            # the touch, and the trousers tore into spikes between them the
            # moment a pose parted the knees -- and his hips, which neither
            # rule reached, came out pinched between a x1.20 thigh and a
            # x1.31 waist. Tapered to nothing in the last centimetre either
            # side of the midline, where the crotch joins the two.
            below = 1.0 - _smooth((z - 0.96) / 0.04)
            shift = shift + np.sign(x) * hip_x * (t - 1.0) * _smooth(np.abs(x) / 0.012) * below
            rigid = np.sign(x) * shoulder_x * (t - 1.0)
            P[:, 0] = P[:, 0] + shift * (1.0 - arm_w) + rigid * arm_w
        if abs(l - 1.0) > 1e-9:
            # the neck thickens with the build, half as fast as a limb: a
            # heavy man's neck is not a lean man's neck on a wide body
            z = P0[:, 2]
            wn = _smooth((z - 1.49) / 0.04) * (1.0 - _smooth((z - 1.60) / 0.05))
            P[:, 0:2] = P[:, 0:2] * (1.0 + (math.sqrt(l) - 1.0) * wn)[:, None]
        out = P * np.array([h, h, h])
        if abs(hk - h) > 1e-9:
            wh = _smooth((P0[:, 2] - 1.54) / 0.08)
            out = out + (wh * (hk - h))[:, None] * (P0 - HEAD_PIVOT[None, :])
        return out
    return h, l, t, F

def scale_to(objects, joints_l, sc, build):
    """Take the built man to (sc, build): every mesh in `objects`, the joint
    table J and the hand joints `joints_l`, through one field. Returns the
    three factors. Saud's own numbers leave everything exactly as it is."""
    h, l, t, F = build_field(sc, build)
    if abs(h - 1) < 1e-9 and abs(l - 1) < 1e-9 and abs(t - 1) < 1e-9:
        return dict(h=1.0, l=1.0, t=1.0)
    for o in objects:
        me = o.data; n = len(me.vertices)
        P = np.empty(n * 3); me.vertices.foreach_get("co", P)
        me.vertices.foreach_set("co", F(P.reshape(n, 3)).reshape(-1)); me.update()
    # the joints: the same field, so the bones are where the body is
    names = list(J.keys())
    Q = F(np.array([list(J[k][0]) for k in names]))
    for k, q in zip(names, Q):
        J[k][0].x, J[k][0].y, J[k][0].z = float(q[0]), float(q[1]), float(q[2])
    for key, pts in joints_l.items():
        Q = F(np.array([list(p) for p in pts]))
        for p, q in zip(pts, Q):
            p.x, p.y, p.z = float(q[0]), float(q[1]), float(q[2])
    print("build     : h %.3f (stature %.3f m)  limbs x%.3f  torso x%.3f  head x%.3f" % (h, legacy.HEIGHT * h, l, t, h ** 0.65))
    # the crotch weld rig_export.pin_crotch pins, carried through the same
    # field: its canonical 0.910 m is mid-thigh on a man half again the size
    c = F(np.array([[0.0, 0.0, 0.910], [0.030, 0.0, 0.910], [0.0, 0.0, 0.940]]))
    return dict(h=h, l=l, t=t, head=h ** 0.65, crotch=dict(z_centre=float(c[0][2]), x_reach=float(c[1][0] - c[0][0]),
                                           z_reach=float(c[2][2] - c[0][2])))
