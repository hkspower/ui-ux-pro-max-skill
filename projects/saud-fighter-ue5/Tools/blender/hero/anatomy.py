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

def smooth_rows(profile, per=4):
    """A limb profile resampled `per` rings to a span through a Catmull-Rom
    curve (every column, t included): the loft bridges its rings with
    straight lines, so a belly drawn with six rings had a kink at each
    (2026-10-01, "more fitted muscle": 4.5 mm on Saud's shoulder, 2.7 on
    his biceps' front). The given rings are kept exactly."""
    rows = [tuple(r) for r in profile]
    out = []
    for i in range(len(rows) - 1):
        p0 = rows[max(i - 1, 0)]; p1 = rows[i]; p2 = rows[i + 1]; p3 = rows[min(i + 2, len(rows) - 1)]
        for k in range(per):
            u = k / per
            out.append(tuple(0.5 * ((2 * b) + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u * u
                                    + (-a + 3 * b - 3 * c + d) * u ** 3)
                             for a, b, c, d in zip(p0, p1, p2, p3)))
    out.append(rows[-1])
    return out

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
TRUNK_ROWS = [
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

def trunk_surface(x, z, back=True):
    """The trunk loft's surface at (x, z) -- back or front -- and its
    outward normal there: the loft's own ellipse, rows interpolated
    straight as the loft bridges them. For seating the back's muscles on
    the surface they lie on (2026-09-27)."""
    r = TRUNK_ROWS
    z = min(max(z, r[0][0]), r[-1][0])
    for r0, r1 in zip(r, r[1:]):
        if r0[0] <= z <= r1[0]: break
    t = (z - r0[0]) / (r1[0] - r0[0])
    cy, rx, ry = [a + (b - a) * t for a, b in zip(r0[1:], r1[1:])]
    k = max(0.0, 1.0 - (x / rx) ** 2) ** 0.5
    y = cy + ry * k if back else cy - ry * k
    n = Vector((x / rx ** 2, (y - cy) / ry ** 2, 0.0)).normalized()
    return Vector((x, y, z)), n

# The back's muscles (2026-09-27, "fix back body": the lats and the V, the
# spine and the lower back), as (x, z, how far it stands proud of the
# trunk loft, half-width across) along each, left side; assembly.masses
# seats each point on trunk_surface and builds the band with
# assembly.chain. They were two eggs a side on the flank for the lats and
# two more up the spine for the erectors -- four vertical ovals on a flat
# back, and nothing that ran from the armpit down into the waist.
BACK_MUSCLES = {
    # latissimus dorsi: from the armpit's back fold, sweeping down and in
    # to the lumbar fascia -- the V, drawn by a muscle, thickest at the
    # armpit and thinning to nothing over the small of the back
    "lat": [(0.166, 1.345, 0.010, 0.040), (0.156, 1.290, 0.010, 0.060), (0.136, 1.228, 0.008, 0.065),
            (0.106, 1.168, 0.005, 0.055), (0.072, 1.118, 0.002, 0.040)],
    # erector spinae: two columns either side of the spine from the sacrum
    # to the middle of the back, thickest over the lumbar, the furrow
    # between them the length of the back. Broad and soft: at a 22 mm
    # half-width they read as two rods
    "erector": [(0.030, 0.975, 0.004, 0.024), (0.034, 1.040, 0.008, 0.029), (0.035, 1.110, 0.009, 0.030),
                (0.036, 1.180, 0.008, 0.029), (0.037, 1.260, 0.006, 0.026), (0.038, 1.340, 0.003, 0.022)],
}
# each link's centre this far under the surface: deep, so a band rises out
# of the back at a shallow angle and blends -- seated 6 mm under, its edges
# met the skin steeply and read as creases, the columns as rods
BACK_SEAT = 0.015
BACK_WIDEN = 1.25          # the across radii, for the part a deeper seat hides

# ------------------------------------------------------------- physiques
# One man's trunk where it is not the canonical one (2026-09-28, "make Saud
# more aggressive and more fit look", the Unreal build only: these numbers
# are not the browser's, which draws every man from one figure). The body
# above IS Saud's and the Brawler's (the same sc and build), and through
# build_field everyone else's, so a leaner Saud cannot be a change to the
# canonical rows: it is a physique, swapped in as module state before
# anything is built -- pipeline.apply_man, from pipeline.PHYSIQUE, like
# face.set_hair -- and set_physique(None) puts the canonical rows back.
# One process per man (build_fighters); a suite that builds several bodies
# in one process resets it.
CANON_TRUNK_ROWS = list(TRUNK_ROWS)
CANON_BACK_MUSCLES = dict(BACK_MUSCLES)
PHYSIQUES = {
    # Lean: the waist narrower (the front 8 mm flatter, the sides 11 mm in
    # at 1.14) and the V's widest point carried up under the arm; the rows
    # from the hips (2 mm in) to the shoulder shelf (2 mm out) move, and the
    # pelvis floor, the trochanters and the neck -- the crotch at 0.899,
    # the neck's girth -- are the canon's.
    # The lat wider and prouder at the armpit and gone sooner (its lower
    # point at 8 mm proud left the lat rule 6.7 against its 6).
    "lean": dict(
        TRUNK_ROWS=[
            (0.900, 0.010, 0.150, 0.106),
            (0.930, 0.010, 0.172, 0.116),
            (0.960, 0.008, 0.178, 0.118),
            (1.020, 0.003, 0.160, 0.108),
            (1.080, -0.003, 0.140, 0.097),
            (1.140, -0.005, 0.133, 0.093),
            (1.200, -0.002, 0.150, 0.101),
            (1.270, 0.005, 0.180, 0.112),
            (1.340, 0.010, 0.196, 0.116),
            (1.400, 0.012, 0.206, 0.106),
            (1.455, 0.006, 0.214, 0.096),
            (1.478, 0.000, 0.216, 0.090),
            (1.505, 0.000, 0.152, 0.078),
            (1.530, 0.002, 0.078, 0.064),
        ],
        BACK_MUSCLES={
            "lat": [(0.176, 1.345, 0.014, 0.042), (0.166, 1.290, 0.013, 0.058), (0.140, 1.228, 0.011, 0.060),
                    (0.104, 1.172, 0.004, 0.046), (0.068, 1.124, 0.001, 0.034)],
            "erector": CANON_BACK_MUSCLES["erector"],
        },
        # its own proportions, held instead of the canonical band where it
        # names one (bands()): a lean fighter's waist, and the V
        BANDS={"waist": (0.74, 0.79), "chest": (1.02, 1.12), "hips": (0.90, 1.00), "v": (1.45, 1.70)},
    ),
}
PHYSIQUE = None

def set_physique(name=None):
    """Swap in one man's trunk rows and back muscles (PHYSIQUES), or the
    canonical ones for None. Unknown names raise."""
    global TRUNK_ROWS, BACK_MUSCLES, PHYSIQUE
    if name is None:
        TRUNK_ROWS, BACK_MUSCLES, PHYSIQUE = list(CANON_TRUNK_ROWS), dict(CANON_BACK_MUSCLES), None
        return
    if name not in PHYSIQUES:
        raise KeyError("no such physique: %r (%s)" % (name, ", ".join(sorted(PHYSIQUES))))
    p = PHYSIQUES[name]
    TRUNK_ROWS, BACK_MUSCLES, PHYSIQUE = list(p["TRUNK_ROWS"]), dict(p["BACK_MUSCLES"]), name

def trunk_at(ang, z, rows=None):
    """The trunk loft at angle `ang` round its section (0 straight forward,
    -Y; +pi/2 his left, +X) and height z: the point and its outward
    normal, rows interpolated straight as the loft bridges them."""
    r = rows or TRUNK_ROWS
    zz = min(max(z, r[0][0]), r[-1][0])
    for r0, r1 in zip(r, r[1:]):
        if r0[0] <= zz <= r1[0]: break
    t = (zz - r0[0]) / (r1[0] - r0[0])
    cy, rx, ry = [a + (b - a) * t for a, b in zip(r0[1:], r1[1:])]
    p = Vector((rx * math.sin(ang), cy - ry * math.cos(ang), z))
    n = Vector((math.sin(ang) / rx, -math.cos(ang) / ry, 0.0)).normalized()
    return p, n

def pillow(name, centre, axes, frame=None, ex=0.62):
    """A belly with a flat top and steep edges -- not a pebble: a UV sphere
    whose across and long coordinates are pushed toward a square, |u| ** ex
    (ex 1.0 is the ellipsoid), its proud axis left round. `frame` is the
    (across, proud, long) directions; axes the half-sizes along them."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=32, ring_count=20, location=(0, 0, 0))
    o = bpy.context.object; o.name = name
    for v in o.data.vertices:
        x, y, z = v.co
        v.co = (math.copysign(abs(x) ** ex, x), y, math.copysign(abs(z) ** ex, z))
    X_, Y_, Z_ = frame or (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
    R = Matrix((Vector(X_) * axes[0], Vector(Y_) * axes[1], Vector(Z_) * axes[2])).transposed()
    o.matrix_world = Matrix.Translation(Vector(centre)) @ R.to_4x4()
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return o

def seated(name, ang, z, axes, along, sink):
    """An ellipsoid seated on the trunk loft: its centre `sink` under the
    surface at (ang, z), axes (across, proud, long), the long axis along
    `along` laid into the surface and the proud one its normal."""
    p, n = trunk_at(ang, z)
    c = p - n * sink
    zax = Vector(along); zax = (zax - n * zax.dot(n)).normalized()
    yax = n; xax = yax.cross(zax)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=24, ring_count=14, location=(0, 0, 0))
    o = bpy.context.object; o.name = name
    R = Matrix((xax * axes[0], yax * axes[1], zax * axes[2])).transposed()
    o.matrix_world = Matrix.Translation(c) @ R.to_4x4()
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return o

# The lean physique's definition, built into the 3.5 mm pass (assembly.build)
# rather than the 6 mm base, whose smoothing (0.40 x 3) blurred 2 mm bellies
# away: the canonical rectus measured six 2 mm pebbles, rows 2.6 mm over
# the grooves and a 0.4 mm linea alba; its oblique lay inside the loft
# (-0.1 mm at its angle) and there was no serratus at all.
# The rectus: three rows of flat-topped bellies, (z centre, half-height,
# half-width, how far proud of the loft's front), their centres RECTUS_X
# off the midline -- a 12 mm linea alba between them.
# 2026-10-01 ("more fitted muscle"): the rows were six pebbles, 22 mm of
# flat belly between them -- a lean fighter's rectus is a strap, its rows
# parted by narrow tendinous lines. Taller rows now, the lines between
# them narrow, a little less proud, flatter on top, over a strap
# (RECTUS_STRAP) that carries the lower belly down toward the pubis.
RECTUS = [(1.246, 0.0325, 0.028, 0.0066), (1.177, 0.0335, 0.029, 0.0070), (1.107, 0.0345, 0.029, 0.0070)]
RECTUS_X = 0.034
RECTUS_EX = 0.62
# the strap under the rows, (z top, z bottom, half-width, how proud): its
# edge is the linea semilunaris, the line down the side of the abs
RECTUS_STRAP = (1.275, 0.990, 0.027, 0.0022)
# the external oblique, a band down and forward on the flank, (angle, z):
# slanted, it reads as the oblique line; beads read as a column of bumps and
# a vertical chain as a bar
OBLIQUE = [(1.36, 1.225), (1.28, 1.170), (1.18, 1.115), (1.08, 1.070)]
# 2026-10-01: the chain's links, 10 mm apart and as long as they were
# thick, read as a ribbed sausage on the flank. Now the band follows the
# same line with links 3 mm apart, each seated on the loft at its own
# height (the waist curves in at 1.14 and out again: one straight belly
# stood proud only at the narrowest), (across, crown) along it.
OBLIQUE_STEP = 0.003
OBLIQUE_BAND = (0.034, 0.0065)
OBLIQUE_SEAT = 0.012
OBLIQUE_FADE = []           # per OBLIQUE point (across, proud) factors; [] is the full band throughout
SERRATUS_PROUD = 0.0045
# the serratus, four slips on the ribs under the pec's edge, (angle, z),
# finger-like and interleaved with the oblique's top
SERRATUS = [(0.92, 1.318), (0.97, 1.292), (1.02, 1.266), (1.07, 1.240)]

def definition(physique=None):
    """The fine-pass parts of a physique, left side only (the caller
    mirrors them): nothing for the canonical body."""
    if physique is None:
        return []
    assert physique == "lean", "no definition for the %r physique" % physique
    from .assembly import chain
    out = []
    if RECTUS_STRAP and RECTUS:
        z0, z1, hw, pr = RECTUS_STRAP
        zc, hz = 0.5 * (z0 + z1), 0.5 * (z0 - z1)
        y = trunk_surface(RECTUS_X, zc, back=False)[0].y
        out.append(pillow("rectus_strap", (RECTUS_X, y + 0.008 - pr, zc), (hw, 0.008, hz), ex=0.55))
    for k, (zc, hz, hx, pr) in enumerate(RECTUS):
        y = trunk_surface(RECTUS_X, zc, back=False)[0].y
        out.append(pillow("rectus%d" % k, (RECTUS_X, y + 0.010 - pr, zc), (hx, 0.010, hz), ex=RECTUS_EX))
    if len(OBLIQUE) >= 2:
        pts, radii = [], []
        fade = OBLIQUE_FADE if len(OBLIQUE_FADE) == len(OBLIQUE) else [(1.0, 1.0)] * len(OBLIQUE)
        for (ang, z), (fa, fp) in zip(OBLIQUE, fade):
            p, n = trunk_at(ang, z); pts.append(p - n * OBLIQUE_SEAT)
            radii.append((OBLIQUE_BAND[0] * fa, OBLIQUE_SEAT + OBLIQUE_BAND[1] * fp))
        out.extend(chain("oblique", pts, radii, lambda c: trunk_at(math.atan2(c.x, -(c.y + 0.004)), c.z)[1],
                         step=OBLIQUE_STEP))
    for k, (ang, z) in enumerate(SERRATUS):
        out.append(seated("serratus%d" % k, ang, z, (0.014, 0.013, 0.030), (0.0, -0.8, -0.6), 0.013 - SERRATUS_PROUD))
    return out

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
    rows = TRUNK_ROWS
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

def check_back(P, assert_=True):
    """The back on the built base (pass one, canonical), 2026-09-27 ("fix
    back body"). P is (N,3) vertex positions.

    the spine is a furrow between two columns the length of the lower and
    middle back -- at every height from 1.02 to 1.22 the erector (x 30 mm)
    stands at least 3 mm behind the midline (the old back had eggs at two
    heights and nothing between: -2 mm at 1.10), 2.5 mm; the lats cover
    the flank -- 120 mm out at 1.22 and 150 mm out at 1.29 the back stands
    at least 6 mm proud of the trunk loft (9 mm; with no lats the remesh's
    own swell gives 3); and the
    V: seen from behind the trunk narrows from under the arms to the waist
    without a bulge (no rise of more than 2 mm going down, 1.30 to 1.14).
    Returns the numbers."""
    P = np.asarray(P)
    def back_y(x, z):
        b = P[(np.abs(np.abs(P[:, 0]) - x) < 0.004) & (np.abs(P[:, 2] - z) < 0.004) & (P[:, 1] > 0)]
        return float(b[:, 1].max())
    def half(z):
        b = P[(np.abs(P[:, 2] - z) < 0.004) & (P[:, 1] > 0.0) & (np.abs(P[:, 0]) < 0.19)]
        return float(np.abs(b[:, 0]).max())
    furrow = min(back_y(0.030, z) - back_y(0.0, z) for z in np.arange(1.02, 1.221, 0.02))
    lat = min(back_y(x, z) - trunk_surface(x, z)[0].y for x, z in ((0.120, 1.22), (0.150, 1.29)))
    hw = [half(z) for z in np.arange(1.30, 1.139, -0.02)]
    bulge = max(0.0, max(b - a for a, b in zip(hw, hw[1:])))
    out = dict(furrow=furrow, lat=lat, bulge=bulge, v=hw[0] / hw[-1])
    if not assert_:
        return out
    assert furrow >= 0.0025, "no spinal furrow: at its shallowest the erector stands %.1f mm behind the midline, want 2.5" % (furrow * 1000)
    assert bulge <= 0.002, "no V: the back bulges %.0f mm going down from the arms to the waist" % (bulge * 1000)
    assert lat >= 0.006, "no lats: the flank stands %.1f mm off the trunk loft, want 6" % (lat * 1000)
    return out

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
# The lean physique's limbs (2026-10-01, "improve body to be more fitted
# muscle", Saud only: the lean MMA fighter the author chose, defined and
# dry, no extra bulk). Measured on the body built before: his upper arm was
# one tube 100 mm from its axis to the front of the biceps and 65 to the
# back, round, so it read as a swollen sleeve; the deltoid three pads with a
# 4.5 mm step down onto the arm; every ring of every limb a kink; the outer
# thigh a straight taper, no quadriceps at all. Now a slimmer core, its
# rings (t, rx, ry, shift front, shift side, belly weight -- arm()'s) on a
# smooth curve, and the muscles laid on it as bellies (LIMB_BELLIES) that
# meet in grooves: the biceps and the triceps' two heads apart on the
# outside of the arm, the brachioradialis over the forearm's radial side,
# the quadriceps' sweep and the teardrop over the knee, the calf's heads.
LEAN_UPPER = [
    (-0.05, 0.047, 0.049, 0.000, 0.0, 0.50),
    (0.15, 0.050, 0.053, +0.003, 0.0, 0.80),
    (0.40, 0.053, 0.057, +0.004, 0.0, 1.00),
    (0.62, 0.049, 0.053, +0.003, 0.0, 0.80),
    (0.84, 0.039, 0.042, +0.001, 0.0, 0.35),
    (1.02, 0.043, 0.037, 0.000, 0.0, 0.05),
]
LEAN_FORE = [
    (-0.02, 0.043, 0.037, 0.000, 0.0, 0.25),
    (0.25, 0.043, 0.045, +0.002, -0.004, 1.00),
    (0.55, 0.037, 0.038, +0.002, 0.002, 0.60),
    (0.80, 0.031, 0.029, 0.000, 0.0, 0.25),
    (1.00, 0.030, 0.023, 0.000, 0.0, 0.0),
    (1.05, 0.029, 0.022, 0.000, 0.0, 0.0),
]
LEAN_THIGH = [
    (-0.06, 0.082, 0.096, +0.004, -0.010),
    (0.16, 0.082, 0.097, +0.007, -0.008),
    (0.40, 0.077, 0.089, +0.011, -0.002),
    (0.62, 0.069, 0.078, +0.009, 0.0),
    (0.82, 0.060, 0.064, +0.004, 0.0),
    (0.92, 0.061, 0.059, +0.002, +0.004),
    (1.02, 0.063, 0.056, 0.000, 0.0),
    (1.07, 0.057, 0.054, 0.000, 0.0),     # into the shank's top, no ring at the knee
]
LEAN_SHANK = [
    (-0.07, 0.061, 0.056, 0.000, 0.0),    # up under the thigh's end
    (-0.02, 0.058, 0.056, 0.000, 0.0),
    (0.16, 0.056, 0.070, -0.012, 0.003),
    (0.32, 0.053, 0.065, -0.009, -0.002),
    (0.58, 0.044, 0.049, -0.004, 0.0),
    (0.82, 0.035, 0.038, -0.001, 0.0),
    (0.98, 0.032, 0.040, 0.000, 0.0),
    (1.04, 0.031, 0.039, 0.000, 0.0),
]
# A belly: (name, segment, t along it, angle round it in degrees -- 0 the
# front, +90 toward the body's midline, -90 away from it, 180 behind --
# half-sizes (across, deep, long), how far its top stands off the core,
# whether it grows with the arm). Each is a broad ellipsoid seated deep, so
# only its crown shows and its edge meets the limb at a shallow angle: a
# narrow flat-topped belly (the first try) stood on the limb as a strip.
# On the arm and the leg alike +90 is s = d x f, toward the midline.
LIMB_BELLIES = [
    # the biceps: a long crown on the front, fullest past the middle
    ("biceps", "upper", 0.54, 6.0, (0.036, 0.030, 0.100), 0.008, True),
    # the brachialis, showing on the outside between biceps and triceps low down
    ("brachialis", "upper", 0.72, -70.0, (0.022, 0.018, 0.050), 0.004, True),
    # the triceps: the lateral head high on the outside-back, the long head
    # behind and in; the groove between them and the biceps down the outside
    ("tri_lat", "upper", 0.38, -135.0, (0.030, 0.026, 0.085), 0.007, True),
    ("tri_long", "upper", 0.46, 168.0, (0.034, 0.028, 0.100), 0.006, True),
    # the forearm: the brachioradialis over the radial side (away from the
    # body, arm()'s own note), the flexors front-inside, the extensors behind
    ("brachiorad", "fore", 0.20, -55.0, (0.028, 0.024, 0.090), 0.007, True),
    ("flexors", "fore", 0.27, 50.0, (0.030, 0.024, 0.085), 0.005, True),
    ("extensors", "fore", 0.30, -140.0, (0.026, 0.022, 0.085), 0.004, True),
    # the thigh: the vastus lateralis' sweep on the outside, the rectus
    # femoris down the front, the teardrop (vastus medialis) over the knee
    # on the inside, the hamstrings behind
    ("vastus_lat", "thigh", 0.45, -80.0, (0.050, 0.040, 0.170), 0.010, False),
    ("rectus_fem", "thigh", 0.40, -5.0, (0.042, 0.034, 0.160), 0.006, False),
    ("vmo", "thigh", 0.84, 60.0, (0.034, 0.028, 0.060), 0.008, False),
    ("hamstring", "thigh", 0.46, 178.0, (0.048, 0.036, 0.150), 0.004, False),
    # the calf's two heads, the inner higher and bigger; the shin's muscle
    ("gastroc_in", "shank", 0.27, 145.0, (0.036, 0.030, 0.080), 0.008, False),
    ("gastroc_out", "shank", 0.31, -145.0, (0.032, 0.026, 0.070), 0.006, False),
    ("tibialis", "shank", 0.30, -25.0, (0.022, 0.018, 0.095), 0.003, False),
]
BELLY_EX = 1.0             # round: a crown, not a plateau

def _core_radius(profile, t, ang):
    """The core tube's radius at t in the direction `ang` (arm()'s frame):
    its ellipse there, and the section's shift off the bone along it."""
    rows = profile
    for r0, r1 in zip(rows, rows[1:]):
        if r0[0] <= t <= r1[0]: break
    u = (t - r0[0]) / max(r1[0] - r0[0], 1e-9)
    rx, ry, sf, ss = [a + (b - a) * u for a, b in zip(r0[1:5], r1[1:5])]
    c, s_ = math.cos(ang), math.sin(ang)
    return 1.0 / math.sqrt((c / ry) ** 2 + (s_ / rx) ** 2) + sf * c + ss * s_

def limb_bellies(scale=1.0):
    """The lean physique's limb muscles, left side (the caller mirrors
    them): LIMB_BELLIES laid on the core of LEAN_UPPER / LEAN_FORE /
    LEAN_THIGH / LEAN_SHANK, each seated so it stands its own distance off
    that core; the arm's grown with `scale` as arm()'s bellies are."""
    segs = {"upper": ("upperarm_l", "lowerarm_l", LEAN_UPPER), "fore": ("lowerarm_l", "hand_l", LEAN_FORE),
            "thigh": ("thigh_l", "calf_l", LEAN_THIGH), "shank": ("calf_l", "foot_l", LEAN_SHANK)}
    out = []
    for name, seg, t, deg, axes, proud, grows in LIMB_BELLIES:
        ja, jb, prof = segs[seg]
        a, b = Jp(ja), Jp(jb)
        d = (b - a).normalized(); front = Vector((0, -1, 0))
        f = (front - d * front.dot(d)).normalized(); s_ = d.cross(f).normalized()
        k = 1.0 + (scale - 1.0) if grows else 1.0
        ang = math.radians(deg)
        rows = [(r[0], r[1] * (k if grows else 1.0), r[2] * (k if grows else 1.0), r[3], r[4]) for r in prof]
        R = _core_radius(rows, t, ang)
        dirv = (f * math.cos(ang) + s_ * math.sin(ang)).normalized()
        ax = tuple(v * k for v in axes)
        c = a + (b - a) * t + dirv * (R + proud * k - ax[1])
        across = d.cross(dirv).normalized()
        out.append(pillow("belly_" + name, c, ax, (across, dirv, d), ex=BELLY_EX))
    return out

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
    if PHYSIQUE == "lean":
        # Saud's (2026-10-01, "more fitted muscle", a lean MMA fighter's):
        # a slimmer core with the bellies laid on it as muscles
        # (limb_bellies) rather than one round tube fattest at the biceps,
        # and the rings through a smooth curve (smooth_rows) so the loft
        # has no kink at each ring.
        upper = tube("upperarm", ua, la, smooth_rows([(t,) + bulk(*r) for t, *r in LEAN_UPPER]), segs=48)
        lower = tube("forearm", la, hd, smooth_rows([(t,) + bulk(*r) for t, *r in LEAN_FORE]), segs=48)
        return [upper, lower]
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
    if PHYSIQUE == "lean":
        # Saud's: the canonical rings through a smooth curve, a little
        # leaner at the core; the quadriceps' sweep, the teardrop over the
        # knee and the calf's two heads are limb_bellies'
        return [tube("thigh", th, cf, smooth_rows(LEAN_THIGH), segs=48),
                tube("shank", cf, ft, smooth_rows(LEAN_SHANK), segs=48)]
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
    print("body      : " + "  ".join("%s %.3f" % (k, v) for k, v in g.items() if k in bands() or k == "v"))
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

def bands():
    """The proportions this body is held to: PROPORTIONS, with a physique's
    own bands where it names them (2026-09-28). The V ('v', proportions())
    is held only for a physique that names it -- the lean one: measured, the
    canonical body is 1.39 and the brawler's heavier waist lower still, and
    the band is the lean man's point, not every man's."""
    out = dict(PROPORTIONS)
    if PHYSIQUE is not None:
        out.update(PHYSIQUES[PHYSIQUE].get("BANDS", {}))
    return out


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
    # the V (2026-09-28): the trunk's half-width at its widest over 1.14-1.34
    # over its narrowest over 1.08-1.16, the arms left out
    T = P[_trunk_mask(P)]
    def trunk_half(z0):
        b = T[(np.abs(T[:, 2] - z0) < 0.003) & (np.abs(T[:, 0]) < 0.30)]
        return float(np.abs(b[:, 0]).max()) if len(b) else float("nan")
    hw = {round(float(zz), 2): trunk_half(zz) for zz in np.arange(1.40, 1.04, -0.02)}
    wide = max(hw[k] for k in hw if 1.14 <= k <= 1.34)
    narrow = min(hw[k] for k in hw if 1.08 <= k <= 1.16)
    out["v"] = wide / max(narrow, 1e-6)
    return out


def _trunk_mask(P):
    """The points not on the arms: farther from the upper arm's axis than
    0.112 m and from the forearm's than 0.075 (past the shoulder joint)."""
    keep = np.ones(len(P), bool)
    for s in (1, -1):
        m = np.array([s, 1, 1])
        sh, el, wr = (np.array(Jp(k)) * m for k in ("upperarm_l", "lowerarm_l", "hand_l"))
        for a, b, R in ((sh, el, 0.112), (el, wr, 0.075)):
            d = b - a; L = np.linalg.norm(d); d = d / L
            t = np.clip((P - a) @ d, 0.0, L)
            dist = np.linalg.norm(P - (a + np.outer(t, d)), axis=1)
            keep &= ~((dist < R) & ((P - a) @ d > 0.0))
    return keep


def check_proportions(g):
    bad = ["%s %.3f (%.2f-%.2f)" % (k, g.get(k, 0.0), lo, hi) for k, (lo, hi) in bands().items()
           if not (lo <= g.get(k, 0.0) <= hi)]
    assert not bad, "the body is off an athletic male's proportions: " + ", ".join(bad)


def physique_numbers(P):
    """The definition of a body's trunk and shoulder, on the fine body
    (pass two) at canonical coordinates, 2026-09-28. In mm:

    abs      the rectus rows over the tendinous grooves between them (at
             x 36 mm, grooves at 1.210 and 1.141), the lesser of the two
    linea    the linea alba: the midline behind the bellies (x 30 mm)
    oblique  the flank over the trunk loft at angle 1.20 (z 1.08-1.17)
    serratus the ripple along angle 1.00 over the ribs (z 1.225-1.330),
             its run taken out
    delt     the deltoid's cap: the upper arm's up-and-out radius at t
             0.05-0.25 over its radius at the insertion (t 0.45) -- a cap,
             not a tube fattest at the biceps
    tie      the dip across the front at z 1.40 from the pec into the
             anterior deltoid, under the chord between the two
    """
    P = np.asarray(P)
    T = P[_trunk_mask(P)]
    out = {}
    def front_y(x, z, bx=0.003, bz=0.003):
        b = P[(np.abs(np.abs(P[:, 0]) - x) < bx) & (np.abs(P[:, 2] - z) < bz) & (P[:, 1] < 0)]
        return float(b[:, 1].min()) if len(b) else float("nan")
    col = {round(float(z), 3): front_y(0.036, z) for z in np.arange(1.290, 1.060, -0.004)}
    rows = [1.244, 1.176, 1.106]; grooves = [1.210, 1.141]
    cap = [min(col[k] for k in col if abs(k - r) < 0.010) for r in rows]
    grv = [max(col[k] for k in col if abs(k - g_) < 0.008) for g_ in grooves]
    out["abs"] = min(g_ - max(c1, c2) for g_, c1, c2 in zip(grv, cap[:-1], cap[1:]))
    out["linea"] = min(front_y(0.0, r) - front_y(0.030, r) for r in rows)
    obl = []
    for z in (1.08, 1.11, 1.14, 1.17):
        p, n = trunk_at(1.20, z)
        q = T[np.abs(T[:, 2] - z) < 0.003]
        rel = (q - np.array(p))[:, :2]
        nn = np.array(n[:2]); tang = np.array([-nn[1], nn[0]])
        near = np.abs(rel @ tang) < 0.006
        obl.append(float((rel[near] @ nn).max()) if near.any() else float("nan"))
    out["oblique"] = min(obl)
    line = []
    for z in np.arange(1.330, 1.225, -0.003):
        p, n = trunk_at(1.00, z)
        q = P[np.abs(P[:, 2] - z) < 0.002]
        r2 = (q - np.array(p))[:, :2]; n2 = np.array(n[:2])
        q = q[np.linalg.norm(r2 - np.outer(r2 @ n2, n2), axis=1) < 0.004]
        line.append(float(((q - np.array(p))[:, :2] @ n2).max()) if len(q) else np.nan)
    line = np.array(line)
    good = ~np.isnan(line)
    tr = np.convolve(np.where(good, line, np.nanmean(line)), np.ones(9) / 9, mode="same")
    out["serratus"] = float(np.nanmax((line - tr)[4:-4]) - np.nanmin((line - tr)[4:-4]))
    ua, la = np.array(Jp("upperarm_l")), np.array(Jp("lowerarm_l"))
    d = la - ua; L = np.linalg.norm(d); d = d / L
    f = np.array([0.0, -1.0, 0.0]); f = f - d * (f @ d); f = f / np.linalg.norm(f); s_ = np.cross(d, f)
    up = -s_ if (-s_)[2] > 0 else s_
    q = P - ua; t = q @ d / L; r = q - np.outer(q @ d, d)
    rad = np.linalg.norm(r, axis=1); dirn = r / np.maximum(rad, 1e-9)[:, None]
    side = (dirn @ up) > 0.85
    def R(t0):
        m = side & (np.abs(t - t0) < 0.02) & (rad < 0.14) & (P[:, 0] > 0.15)
        return float(rad[m].max()) if m.any() else float("nan")
    out["delt"] = max(R(x) for x in (0.05, 0.10, 0.15, 0.20, 0.25)) - R(0.45)
    xs = np.arange(0.08, 0.25, 0.005)
    ys = []
    for x in xs:
        b = P[(np.abs(P[:, 0] - x) < 0.003) & (np.abs(P[:, 2] - 1.40) < 0.004) & (P[:, 1] < 0.0)]
        ys.append(float(b[:, 1].min()) if len(b) else np.nan)
    ys = -np.array(ys)
    i0 = int(np.nanargmax(ys[:6])); i1 = len(xs) - 8 + int(np.nanargmax(ys[-8:]))
    chord = ys[i0] + (ys[i1] - ys[i0]) * (np.arange(len(xs)) - i0) / max(i1 - i0, 1)
    out["tie"] = float(np.nanmax((chord - ys)[i0:i1 + 1]))
    out.update(limb_numbers(P))
    return out


def _seg(a, b):
    a, b = np.array(Jp(a)), np.array(Jp(b))
    d = b - a; L = np.linalg.norm(d); d = d / L
    f = np.array([0.0, -1.0, 0.0]); f = f - d * (f @ d); f = f / np.linalg.norm(f)
    return a, d, f, np.cross(d, f), L


def _seg_radius(Q, seg, t0, dirv, band=0.012, cone=0.97, rmax=0.13):
    """The farthest surface point of Q from a segment's axis at t0 (a share
    of its length), within a narrow cone about the direction dirv."""
    a, d, f, s_, L = seg
    q = Q - a; t = q @ d / L; r = q - np.outer(q @ d, d); rad = np.linalg.norm(r, axis=1)
    m = (np.abs(t - t0) < band) & (rad < rmax) & (rad > 1e-6)
    if not m.any():
        return float("nan")
    k = (r[m] / rad[m][:, None]) @ dirv > cone
    return float(rad[m][k].max()) if k.any() else float("nan")


def _hull2(pts):
    """The convex hull of 2D points, counter-clockwise (monotone chain)."""
    p = sorted(set(map(tuple, np.round(pts, 6))))
    if len(p) < 3:
        return np.array(p)
    def half(seq):
        h = []
        for q in seq:
            while len(h) >= 2 and (h[-1][0] - h[-2][0]) * (q[1] - h[-2][1]) - (h[-1][1] - h[-2][1]) * (q[0] - h[-2][0]) <= 0:
                h.pop()
            h.append(q)
        return h
    lo, hi = half(p), half(p[::-1])
    return np.array(lo[:-1] + hi[:-1])


def limb_numbers(P):
    """What makes the lean physique's limbs read as muscle, on the fine body
    at canonical coordinates (2026-10-01, "more fitted muscle"). In mm:

    arm_sep    the groove down the outside of the upper arm between the
               biceps and the triceps: across t 0.45-0.60, the deepest the
               section's outside lies inside its own convex hull (a round
               tube, however thick: 0)
    arm_round  the upper arm's front over its back at t 0.45, from the
               bone's axis: a ratio, not mm (measured 1.55 on the body
               before, the biceps a swelling 101 mm out in front and 65
               behind -- a sleeve, not an arm)
    quad       the vastus lateralis' sweep: the outer thigh's profile over
               t 0.08-0.92 standing out of the straight line between its
               ends
    abs_groove the width of the tendinous lines between the rectus rows at
               x 36 mm: where each lies deeper than half its own depth
               under the line between the rows either side (pebbles parted
               by flat belly: wide)
    """
    P = np.asarray(P)
    out = {}
    arm = P[P[:, 0] > 0.17]
    up, fo = _seg("upperarm_l", "lowerarm_l"), _seg("lowerarm_l", "hand_l")
    sep = 0.0
    for t0 in np.arange(0.45, 0.601, 0.05):
        a, d, f, s_, L = up
        q = arm - a; t = q @ d / L; r = q - np.outer(q @ d, d)
        m = (np.abs(t - t0) < 0.010) & (np.linalg.norm(r, axis=1) < 0.13)
        if m.sum() < 12:
            continue
        uv = np.stack([r[m] @ f, r[m] @ s_], axis=1)        # (front, toward the body)
        h = _hull2(uv)
        e = np.roll(h, -1, axis=0) - h
        nrm = np.stack([e[:, 1], -e[:, 0]], axis=1); nrm /= np.linalg.norm(nrm, axis=1)[:, None]
        depth = np.min(np.einsum("ijk,jk->ij", h[None, :, :] - uv[:, None, :], nrm), axis=1)
        # the outside of the arm, away from the body, between front and back
        outer = uv[:, 1] < -0.64 * np.linalg.norm(uv, axis=1)
        if outer.any():
            sep = max(sep, float(depth[outer].max()))
    out["arm_sep"] = sep
    out["arm_round"] = _seg_radius(arm, up, 0.45, up[2]) / max(_seg_radius(arm, up, 0.45, -up[2]), 1e-6)
    leg = P[P[:, 0] > 0.02]
    th = _seg("thigh_l", "calf_l")
    ts = np.arange(0.08, 0.921, 0.02)
    r = np.array([_seg_radius(leg, th, t, -th[3]) for t in ts])
    good = np.isfinite(r)
    if good.sum() > 4:
        line = np.interp(ts, [ts[good][0], ts[good][-1]], [r[good][0], r[good][-1]])
        out["quad"] = float(np.nanmax(r - line))
    else:
        out["quad"] = float("nan")
    def fy(z):
        b = P[(np.abs(np.abs(P[:, 0]) - 0.036) < 0.003) & (np.abs(P[:, 2] - z) < 0.0015) & (P[:, 1] < 0)]
        return -float(b[:, 1].min()) if len(b) else float("nan")
    zs = np.arange(1.290, 1.060, -0.002)
    col = np.array([fy(z) for z in zs])
    widths = []
    for (zr0, zg, zr1) in ((1.244, 1.210, 1.176), (1.176, 1.141, 1.106)):
        i0 = int(np.nanargmax(np.where(np.abs(zs - zr0) < 0.012, col, np.nan)))
        i1 = int(np.nanargmax(np.where(np.abs(zs - zr1) < 0.012, col, np.nan)))
        seg_ = np.arange(i0, i1 + 1)
        chord = col[i0] + (col[i1] - col[i0]) * (seg_ - i0) / max(i1 - i0, 1)
        dep = chord - col[seg_]
        if not np.isfinite(dep).any() or np.nanmax(dep) <= 0:
            widths.append(float("nan")); continue
        widths.append(float(np.sum(dep > 0.5 * np.nanmax(dep)) * 0.002))
    out["abs_groove"] = max(widths)
    return out


# What the lean physique is held to (check_physique), each floor 1-2 mm
# under the prototype's clean number and each bitten by the body built
# without the thing it guards (2026-09-28): abs 4.5 (none: -1.7), linea 4.0
# (the bellies at 20 mm, met: 1.3), oblique 5.3 (none: 0.0), serratus 5.1
# (none: 0.8), deltoid cap +2.6 (the canonical one deltoid: -5.2), the
# pec-to-deltoid dip 23.8 (no tie-in: 31.7).
PHYSIQUE_RULES = (("abs", ">=", 0.0035, "no abs: the rectus rows %.1f mm over the grooves, want 3.5"),
                  ("linea", ">=", 0.0025, "no linea alba: the midline %.1f mm behind the bellies, want 2.5"),
                  ("oblique", ">=", 0.0030, "no oblique: the flank %.1f mm over the loft at its angle, want 3"),
                  ("serratus", ">=", 0.0030, "no serratus: the ribs' ripple %.1f mm, want 3"),
                  # (before the deltoid's cap: an arm swollen in front also
                  # sinks the cap's measure, and is named for what it is)
                  ("arm_round", "<=", 1.25, "a sleeve, not an arm: the upper arm %.2f times as far out in front as behind, want 1.25 or less", 1.0),
                  ("delt", ">=", 0.0010, "no deltoid cap: the shoulder %.1f mm over the biceps' radius, want 1"),
                  ("tie", "<=", 0.027, "the pec and the deltoid apart: a %.1f mm dip between them, want 27 or less"),
                  # 2026-10-01 ("more fitted muscle"), limb_numbers: each
                  # floor between the body before (arm_sep 1.07, arm_round
                  # 1.54, quad 4.4, abs_groove 26) and after (1.9, 1.10,
                  # 13.6, 14), and each bitten by --physique-check
                  ("arm_sep", ">=", 0.0015, "no groove down the outside of the arm: %.1f mm between biceps and triceps, want 1.5"),
                  ("quad", ">=", 0.009, "no quadriceps sweep: the outer thigh %.1f mm out of its line, want 9"),
                  ("abs_groove", "<=", 0.018, "pebbles, not a strap: the lines between the ab rows %.0f mm wide, want 18 or less"))

def check_physique(P, assert_=True):
    """The lean physique's definition on the fine body (physique_numbers):
    held for a man built lean, reported for everyone else (the canonical
    body measured abs 2.6, linea 0.4, oblique -0.1, serratus 1.6, delt
    -5.2, tie 31.7 on the prototype). Returns the numbers."""
    out = physique_numbers(P)
    if assert_:
        for k, op, lim, msg, *unit in PHYSIQUE_RULES:
            ok = out[k] >= lim if op == ">=" else out[k] <= lim
            assert ok, msg % (out[k] * (unit[0] if unit else 1000))
    return out

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

NEARER_LIMB = True    # a point two limbs hold is the nearer one's (see build_field)
MIDLINE_KEEP = 0.5    # below the crotch no point ends nearer the midline than this share of its own distance

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
            #
            # Between the thighs both legs hold a point, and "strongest"
            # was decided in the fourth decimal: the thigh's axis slants, so
            # the foot of the perpendicular -- and the ramp-in weight with
            # it -- came out a hair higher on the far leg (0.7400 against
            # 0.7398 for a point 3 mm left of the midline at 0.70). The inner
            # thigh was thinned toward the OTHER leg's axis and carried
            # through the midline: on the thug (limbs x0.80) 155 trouser
            # faces crossed it, a web every clip stretched up to 63x (the
            # scan, 2026-09-28). A point belongs to the nearest limb that
            # holds it.
            best_w = np.zeros(len(P)); best_d = np.full(len(P), np.inf); best_foot = P0.copy()
            for pts, R, (u0, u1), ramp in limbs:
                d, u, foot = along(P0, pts)
                w = _smooth((u - u0) / ramp) * (1.0 - _smooth((u - u1) / 0.07))
                w = w * (1.0 - _smooth((d - R * 0.75) / (R * 0.25)))
                take = ((w > 0) & (d < best_d)) if NEARER_LIMB else (w > best_w)
                best_w[take] = w[take]; best_d[take] = d[take]; best_foot[take] = foot[take]
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
        if MIDLINE_KEEP and (abs(l - 1.0) > 1e-9 or abs(t - 1.0) > 1e-9):
            # The legs stay two legs. Between the thighs the trousers hang
            # 2-12 mm off the midline, and neither rule above knows the
            # other leg is there: thinned and carried in (the thug) or
            # thickened about their own axes (AL-WAHSH, ZAYOS), the inner
            # thighs met and passed through each other -- 155 trouser faces
            # across the midline on the thug, a web every clip stretched up
            # to 63x (the scan, 2026-09-28). Below the crotch a point near
            # the midline keeps at least half its distance to it (a smooth
            # maximum, so nothing creases where the floor takes over).
            x0, z0 = P0[:, 0], P0[:, 2]
            sx = np.where(x0 >= 0.0, 1.0, -1.0)
            own = P[:, 0] * sx
            floor = MIDLINE_KEEP * np.abs(x0)
            e = 0.002
            soft = 0.5 * (own + floor + np.sqrt((own - floor) ** 2 + e * e))
            wm = (1.0 - _smooth((z0 - 0.88) / 0.02)) * (1.0 - _smooth((np.abs(x0) - 0.04) / 0.03))
            P[:, 0] = sx * (own + (soft - own) * wm)
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
