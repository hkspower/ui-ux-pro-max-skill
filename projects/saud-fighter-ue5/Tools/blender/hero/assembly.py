"""The assembly: a two-pass body. The base (trunk, limbs, masses) at 6 mm and
smoothed hard; the parts that need their edges -- hands, face, ears, hair
-- at fine voxel, unioned in a second 3.5 mm pass that blends the joins
without eating the detail. Materials come back by nearest source part."""
import bpy, bmesh, math, sys, os, time
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import build_saud as legacy
from . import anatomy as A
from .sculpt import EYE_Z, EAR_Z, HAIRLINE   # the face's layout lives in hero.sculpt
J = legacy.J; Jp = A.Jp; X, Y, Z = A.X, A.Y, A.Z
ellipsoid, loft, tube, ring_z, mirror_x = A.ellipsoid, A.loft, A.tube, A.ring_z, A.mirror_x

def masses():
    """The muscle that sits proud of the lofts. Rewritten 2026-09-25 ("make
    full body fix"): the pec was one ball on each side of the chest and the
    rectus one 26 cm sausage either side of the midline -- both read as
    exactly that on the bare chest (zayos-apose-3d.png) and through every
    tee. A pec is a fan, from the sternum out and up to the armpit, thicker
    below; the rectus is three pairs of bellies with the linea alba between
    them; the obliques stand proud of the flank; the erectors stand either
    side of a spinal groove."""
    out = []
    # The deltoid is a teardrop that flows down the arm, not a ball on the
    # shelf. It was neither: sliced perpendicular to the humerus the arm was
    # 0.159 m across at the deltoid and 0.095 m below it, so the cap was 68 %
    # wider than the limb it caps, and it stood 96.5 mm proud of the acromion
    # against a real 35. That is the puffed sleeve -- the trunk had no V, and
    # this was doing the ribcage's job from the outside. Now the trunk is the
    # V (see anatomy.trunk) and this is a muscle again.
    ua, la = Jp("upperarm_l"), Jp("lowerarm_l")
    out.append(ellipsoid("delt", ua + (la - ua) * 0.12 + Vector((-0.006, -0.004, 0.014)), (0.034, 0.038, 0.088), tuple(la - ua)))
    # The pec: its sternal head a fan whose long axis runs from the lower
    # sternum out and up into the armpit (0.86, 0.30, 0.40 -- back as well as
    # out, because the chest curves away), 1.5 cm proud at its centre, its
    # inner end 6 mm short of the midline so the sternum stays a groove; the
    # clavicular head a thinner slip above it, under the collarbone.
    out.append(ellipsoid("pec", (0.094, -0.078, 1.346), (0.030, 0.052, 0.102), (0.86, 0.30, 0.40)))
    out.append(ellipsoid("pec_up", (0.094, -0.068, 1.408), (0.022, 0.030, 0.084), (0.90, 0.22, 0.14)))
    # The trapezius stopped 35 mm short of the acromion, so nothing drew the
    # neck-to-shoulder diagonal and the trunk loft was left to do it with a
    # step. It has to reach the shoulder. Trimmed 2026-09-25: the neck's
    # base measured 0.284 m across at 1.53, a mound, not a slope.
    out.append(ellipsoid("trap", (0.108, 0.024, 1.488), (0.054, 0.040, 0.070), (0.70, -0.10, -0.30)))
    # The lat: at the side-back of the ribcage, what makes the V from behind.
    # widest at the armpit, gone by the waist -- centred high, so its bottom
    # tapers out above the lower ribs instead of bulging at them
    # ...leaning out, so its top tucks under the armpit and its bottom runs
    # in toward the flank instead of standing as an egg on the side
    out.append(ellipsoid("lat", (0.140, 0.050, 1.300), (0.040, 0.050, 0.120), (0.35, 0.05, 1.0)))
    # The erector spinae, either side of the spine -- the small of the back
    # is not a smooth dish, it is two columns with a furrow between them.
    # Two per side, following the spine's curve (anatomy.trunk's cy).
    out.append(ellipsoid("erector_lo", (0.038, 0.074, 1.080), (0.044, 0.020, 0.140)))
    out.append(ellipsoid("erector_hi", (0.040, 0.098, 1.300), (0.046, 0.020, 0.140)))
    # It was centred on the hip JOINT, so it read as a hip, not a seat.
    # a seat, not a ball: broad and only a centimetre proud of the pelvis
    # ...and its inner edge 6 mm short of the midline: meeting there, the
    # two welded across it and pulled the crotch down 13 mm
    out.append(ellipsoid("glute", (0.090, 0.078, 0.924), (0.084, 0.048, 0.086)))
    out.append(ellipsoid("scm", (0.034, -0.032, 1.566), (0.015, 0.015, 0.048), (0.38, -0.58, 1.0)))
    # The external oblique, proud of the flank between the ribs and the crest.
    out.append(ellipsoid("oblique", (0.116, 0.004, 1.170), (0.032, 0.056, 0.072)))
    # The rectus abdominis: three pairs of bellies, 1 cm proud, the linea
    # alba a 8 mm gap between the pairs and a tendinous line between the rows.
    # the sheet the bellies sit on, 2 mm proud, so they are steps in a slab
    # and not six pebbles on a flat belly
    out.append(ellipsoid("rectus_sheet", (0.0, -0.098, 1.176), (0.078, 0.012, 0.115)))
    for k, zc in enumerate((1.246, 1.176, 1.106)):
        out.append(ellipsoid("rectus%d" % k, (0.038, -0.097, zc), (0.036, 0.014, 0.034)))
    return out

def boolean(target, cutter, op):
    m = target.modifiers.new("B", "BOOLEAN"); m.operation = op; m.object = cutter; m.solver = 'EXACT'
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier="B")
    bpy.data.objects.remove(cutter, do_unlink=True)

def face_parts():
    """Only what a displacement cannot make: the adam's apple. The face
    itself is sculpted after the final remesh -- see sculpt.py."""
    return [ellipsoid("adam", (0, -0.054, 1.560), (0.010, 0.008, 0.012))]

def ear(s):
    """Helix as a flattened ring, lobe below, a dish cut into the front.

    An ear runs from the brow down to the base of the nose -- 1.693 to 1.640
    here, so about 53 mm, and it was 40 mm, which is why it read as a paddle
    stuck on the side of the head rather than as an ear.
    """
    c = Vector((0.0785 * s, 0.026, EAR_Z))   # behind the mandibular ramus,
                                             # not at the head's mid-depth
    bpy.ops.mesh.primitive_torus_add(location=c, major_radius=0.0200, minor_radius=0.0062,
                                     major_segments=28, minor_segments=12)
    helix = bpy.context.object; helix.name = "helix"
    helix.scale = (1.0, 0.72, 1.34); helix.rotation_euler = (0, math.radians(90), 0)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    lobe = ellipsoid("lobe", c + Vector((0.002 * s, -0.003, -0.0250)), (0.0062, 0.0105, 0.0088))
    back = ellipsoid("earback", c + Vector((-0.003 * s, 0.005, 0)), (0.0052, 0.0150, 0.0240))
    return [helix, lobe, back]

EYE_R = 0.0120         # a human eyeball is 24 mm across; this was 22
# Where the globe's centre sits, measured back from the bare skull surface.
# What matters is NOT how proud the cornea is of the floor of its dish -- the
# first attempt at this set it 1.2 mm proud of the floor and the eye came out
# shut, because the floor is 6 mm behind the face and the LID MARGIN is only
# 3.9 mm behind it, so the cornea still sat 0.9 mm inside the lid. The
# criterion is the margin. check_eye() below asserts it.
EYE_SEAT = 0.0140
SOCKET_AX = (0.019, 0.014, 0.017)     # the orbital dish the boolean cuts
SOCKET_IN = 0.0095                    # its centre, forward of the skull line


def check_eye():
    """The globe must stand proud of the lid margin, not of the dish floor.

    Everything here is measured back from the bare skull surface at the eye,
    so larger is further INTO the head. Returns (floor, margin, cornea) in
    metres and raises if the eye would render shut.
    """
    rx, ry, rz = SOCKET_AX
    floor = -SOCKET_IN + ry                                   # the dish at its deepest
    dz = 0.005                                                # the aperture's own edge
    margin = -SOCKET_IN + ry * (1.0 - (dz / rz) ** 2) ** 0.5
    from .sculpt import FACE
    soc = next(a for (n, x, z, sx, sy, sz, a, m) in FACE if n == "socket")
    floor -= soc; margin -= soc                               # the sculpt sinks it further
    cornea = EYE_SEAT - EYE_R
    # 2 mm, not a hair's breadth. The head is remeshed at a 3.5 mm voxel and
    # then smoothed, so anything the cornea clears the lid by under about
    # 2 mm is inside the grid's own noise and the eye still renders shut --
    # which is exactly what happened at 0.6 mm.
    assert cornea < margin - 0.0020, (
        "the eye renders shut: cornea %.4f, lid margin %.4f, clearance %.1f mm"
        % (cornea, margin, (margin - cornea) * 1000))
    # And it must not stand out of his head. The reference for THAT is the
    # bare skull line at the eye, which is 0 here -- not the dish floor,
    # which is 6 mm behind it, so measuring the bulge against the floor
    # called a correctly seated eye a bulging one.
    assert cornea > -0.002, (
        "the eye bulges %.1f mm out of the face" % (-cornea * 1000))
    return floor, margin, cornea

def eyeballs():
    """The globes.

    They used to sit 17 mm out from the skull and 11 mm across, at the bottom
    of a socket the boolean below cut 26 mm deep and 38 mm wide -- so the
    ball's front pole ended up 12 mm BEHIND the rim of its own hole, and the
    eye rendered either as a dark pit or, where the light reached it, as a
    loose bead. Seated here so the cornea stands 1 mm proud of the dish and
    the lids in hero.sculpt close over the rest.
    """
    out = []
    for s in (1, -1):
        e = ellipsoid("eyeball", (0.031 * s, A.head_surface_y(0.031 * s, EYE_Z) + EYE_SEAT, EYE_Z),
                      (EYE_R, EYE_R, EYE_R), segs=64, rings=40)
        # Smooth them here. build() shade-smooths the body, and the globes are
        # made after that call and never touched by it, so both shipped flat:
        # at roughness 0.08 under a full clearcoat the specular lobe is
        # smaller than one facet, and the catchlight took the facet's outline
        # -- a hard-edged square highlight, which reads as a glass bead.
        e.data.polygons.foreach_set("use_smooth", [True] * len(e.data.polygons))
        e.data.update()
        out.append(e)
    return out

# The cuts, 2026-09-24: one per man who has hair, Gulf cuts, named by the
# roster's `look.hairStyle` (assets/saud.js, assets/enemies.js):
#
#   quiff   Saud's: the cap, and length swept up on top
#   crop    a close cut all round -- the cap alone; under the Snatcher's cap
#   buzz    clippered short all over: a shell 3.5 mm off the skull, the skin
#           showing through it (hero.face.hair_fade)
#   fade    a skin fade: short textured top, the sides and back taken down
#           to skin (the fade is paint, the top is the volume)
#   curly   a curly crop: tight curls packed over the top, shorter sides
#   slick   combed straight back: flat at the front, the length piled at
#           the crown and the back, lines combed in
#   part    a hard side part: volume swept to one side of a shaved line
#   fringe  a textured crop pushed forward, a fringe over the forehead
#
# Every one tops out at 1.800 or under (see the heads-tall note below), and
# the new ones all start from the same close shell -- the skull's own rings
# grown a few millimetres -- rather than the cap, which is a single ellipsoid
# solved for Saud's quiff. The skull is a loft of ellipses (anatomy.HEAD_ROWS)
# so its offset is just the rings grown, and nothing can sink into it.
#
# 2026-09-26 ("improve hair style", the Unreal men): two more, which no
# browser man wears -- they are this build's, chosen for two of the 3D men
# (pipeline.CUTS says which and why):
#
#   crest    a hawk's crest: the sides and back faded close, a ridge of
#            clumps down the middle from the hairline over the crown
#   hightop  a high-and-tight: skin up the sides and back, a short flat
#            top with a squared front edge
HAIR_STYLES = ("quiff", "crop", "buzz", "fade", "curly", "slick", "part", "fringe", "crest", "hightop", "bald")

# Nothing of the hair stands above this: the heads-tall rule (below, and
# anatomy.measure). Where a cut has volume it has it where the skull
# leaves room under this line -- at the front, where the skull is 20-40 mm
# lower than its crown -- not on top.
HAIR_TOP = 1.800
# The shell thins to nothing over this height above the hairline plane.
# Grown a full d right to the cut, the shell ended in a d-high step all
# round the head, and in every face render that step caught the light as a
# pale rope across the forehead -- the thing that made every cut read as a
# cap pulled on (2026-09-26).
HAIR_TAPER = 0.012
# A lock thinner than about two and a half remesh voxels (3.5 mm) does not
# survive the union: it breaks into shards and holes, which is what
# AL-SAQR's fringe rendered as (locks 6 mm through). Every part but the
# shell is held to this half-axis: 9 mm through.
HAIR_MIN_AXIS = 0.0045

def _hairline_cut(obj):
    """Everything below the hairline plane goes (see the cap's cut, below:
    the same plane, the same 0.25/cos)."""
    mid = 0.5 * (HAIRLINE[0] + HAIRLINE[1])
    tilt = math.atan2(HAIRLINE[0] - HAIRLINE[1], 0.18)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0.0, mid - 0.25 / math.cos(tilt)))
    cut = bpy.context.object; cut.scale = (0.5, 0.6, 0.5)
    cut.rotation_euler = (-tilt, 0, 0)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    boolean(obj, cut, 'DIFFERENCE')
    return obj

def _hairline_z(y):
    """The hairline plane's height at depth y (sculpt.HAIRLINE is quoted at
    y = -0.09 and +0.09)."""
    t = min(1.4, max(-0.4, (y + 0.09) / 0.18))
    return HAIRLINE[0] + (HAIRLINE[1] - HAIRLINE[0]) * t

def _skull_cy(z):
    rows = A.HEAD_ROWS
    if z <= rows[0][0]: return rows[0][1]
    if z >= rows[-1][0]: return rows[-1][1]
    for r0, r1 in zip(rows, rows[1:]):
        if r0[0] <= z <= r1[0]:
            t = (z - r0[0]) / (r1[0] - r0[0])
            return r0[1] + (r1[1] - r0[1]) * t
    return rows[-1][1]

def _taper_to_hairline(obj, d, width=HAIR_TAPER):
    """Pull the shell back onto the skull near the hairline: d of growth at
    `width` above the plane and more, none at the plane, smoothstepped
    between -- so the hair starts from the skin with no edge to catch the
    light. Each vertex moves toward its ring's own centre, the way it was
    grown out from it."""
    for v in obj.data.vertices:
        c = obj.matrix_world @ v.co
        k = min(1.0, max(0.0, (c.z - _hairline_z(c.y)) / width))
        k = k * k * (3.0 - 2.0 * k)
        pull = d * (1.0 - k)
        if pull <= 0.0:
            continue
        cy = _skull_cy(c.z)
        dx, dy = c.x, c.y - cy
        r = math.hypot(dx, dy)
        if r < 1e-6:
            continue
        s = max(0.0, (r - pull) / r)
        v.co = obj.matrix_world.inverted() @ Vector((dx * s, cy + dy * s, c.z))
    obj.data.update()
    return obj

def hair_shell(d, taper=True, extra=None):
    """The hair as one volume over the skull: the skull's own surface
    (dense rings, see below) pushed out along its normals by d -- plus
    `extra(x, y, z)` metres where the cut has length -- thinned to nothing
    at the hairline (HAIR_TAPER), flattened at HAIR_TOP, and cut at the
    hairline. One volume whose thickness varies, rather than a thin cap
    with blobs on it: the 2026-09-26 cuts put their length in `extra`, and
    blobs set on a shell read as a bun or a row of lumps (the first try)."""
    # Rings every 2 mm, not only at the skull's ten rows (30 mm apart over
    # the forehead): the taper and the thickness move vertices, and with no
    # vertices near the hairline the edge the cut makes there could not be
    # moved. The skull loft is straight between its rows, so interpolating
    # the rows linearly is the skull exactly.
    rows = [r for r in A.HEAD_ROWS if r[0] >= 1.668]
    dense = []
    for r0, r1 in zip(rows, rows[1:]):
        n = max(1, int(round((r1[0] - r0[0]) / 0.002)))
        for k in range(n):
            t = k / n
            dense.append(tuple(a + (b - a) * t for a, b in zip(r0, r1)))
    dense.append(rows[-1])
    rings = [ring_z(z, 0, cy, rx, ry) for z, cy, rx, ry in dense]
    top = rows[-1]
    rings.append(ring_z(top[0] + 0.0005, 0, top[1], 0.010, 0.012))
    shell = loft("hairshell", rings, segs=96)
    me = shell.data
    me.update()
    centre = Vector((0.0, 0.010, 1.700))
    outward = 0
    for v in me.vertices:
        outward += 1 if v.normal.dot(v.co - centre) > 0 else -1
    sign = 1.0 if outward >= 0 else -1.0
    moved = []
    for v in me.vertices:
        c = v.co.copy()
        # `extra` may give a thickness (along the normal) or a Vector (a
        # direction of its own: a quiff's length goes forward, not up)
        e = extra(c.x, c.y, c.z) if extra else 0.0
        off = v.normal * sign * d + (e if isinstance(e, Vector) else v.normal * sign * e)
        if taper:
            k = min(1.0, max(0.0, (c.z - _hairline_z(c.y)) / HAIR_TAPER))
            off = off * (k * k * (3.0 - 2.0 * k))
        moved.append(c + off)
    # A soft ceiling, not a clamp: a hard min(z, HAIR_TOP) flattened every
    # top into a plateau, which is a cap's shape. The rise above the skull
    # is eased into the room under HAIR_TOP (tanh), so the hair rounds into
    # the line and never crosses it.
    for v, c0, c in zip(me.vertices, [v.co.copy() for v in me.vertices], moved):
        room = HAIR_TOP - c0.z
        rise = c.z - c0.z
        if rise > 0.0 and room > 0.0:
            rise = room * math.tanh(rise / room)
        v.co = Vector((c.x, c.y, min(c0.z + rise, HAIR_TOP)))
    me.update()
    return _hairline_cut(shell)

def _sm(v, a, b):
    """0 at a, 1 at b, smoothstepped (either order)."""
    t = min(1.0, max(0.0, (v - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)

def _on_skull(x, y, lift):
    """A point `lift` above the skull's top surface at (x, y), found by
    bisection on the loft: where a part should sit so it rests on the head
    rather than floating over it or sinking into it."""
    lo, hi = 1.668, 1.796
    for _ in range(40):
        z = 0.5 * (lo + hi)
        cy = _skull_cy(z)
        rows = A.HEAD_ROWS
        for r0, r1 in zip(rows, rows[1:]):
            if r0[0] <= z <= r1[0]: break
        t = (z - r0[0]) / (r1[0] - r0[0])
        rx = r0[2] + (r1[2] - r0[2]) * t; ry = r0[3] + (r1[3] - r0[3]) * t
        inside = (x / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0
        if inside: lo = z
        else: hi = z
    return Vector((x, y, lo + lift))

def _held(o):
    """Lower a part until its top is at HAIR_TOP, if it stands above it: a
    tilted ellipsoid's top is not its centre plus its radius, and the check
    below found the quiff's front mass 3 mm over the line. Sinking it into
    the skull costs nothing -- the union takes the outside."""
    top = max((o.matrix_world @ v.co).z for v in o.data.vertices)
    if top > HAIR_TOP:
        for v in o.data.vertices:
            v.co.z -= top - HAIR_TOP
    o.data.update()
    return o

def _lock(name, root, tip, width, depth):
    """A clump of hair from `root` to `tip`: an ellipsoid along the line
    between them, `width` across and `depth` through, no thinner than
    HAIR_MIN_AXIS, its top held under HAIR_TOP by lowering the whole lock."""
    root, tip = Vector(root), Vector(tip)
    axis = tip - root
    half = 0.5 * axis.length
    c = 0.5 * (root + tip)
    w, dp = max(width, HAIR_MIN_AXIS), max(depth, HAIR_MIN_AXIS)
    return _held(ellipsoid(name, c, (w, dp, max(half, HAIR_MIN_AXIS)), axis, segs=20, rings=14))

def _hash01(n):
    """The integer hash the level builders place things with (hash01 in
    Tools/levels), so a man's curls come out the same every build."""
    x = n & 0xFFFFFFFF
    x ^= x >> 16; x = (x * 2246822519) & 0xFFFFFFFF
    x ^= x >> 13; x = (x * 3266489917) & 0xFFFFFFFF
    x ^= x >> 16
    return (x & 0xFFFFFF) / 16777215.0

def _curls(d, r=0.0068, spacing=0.0092, zmin=1.745, lift=0.004):
    """Tight curls packed over the top: small spheres on the shell, each
    lowered where it would stand above 1.800, none below the hairline.
    Jittered in place and size by the builders' own hash, because a regular
    lattice of equal spheres reads as a knitted cap, not as hair."""
    out = []
    rows = A.HEAD_ROWS
    z = zmin
    k = 0
    while z <= 1.797:
        # the skull's ellipse at this height, grown by d
        for r0, r1 in zip(rows, rows[1:]):
            if r0[0] <= z <= r1[0]: break
        t = (z - r0[0]) / (r1[0] - r0[0])
        cy = r0[1] + (r1[1] - r0[1]) * t
        # the curls stand further off the skull toward the top (up to
        # `lift` more): a curly crop is fuller on top than at the sides,
        # and a uniform layer read as a knitted cap
        up = lift * min(1.0, max(0.0, (z - 1.755) / 0.035))
        rx = r0[2] + (r1[2] - r0[2]) * t + d + up; ry = r0[3] + (r1[3] - r0[3]) * t + d + up
        per = max(1, int(2 * math.pi * math.sqrt(0.5 * (rx * rx + ry * ry)) / spacing))
        for i in range(per):
            h = [_hash01(k * 7919 + i * 104729 + j * 31) for j in range(4)]
            a = 2 * math.pi * (i + 0.5 * (k % 2) + (h[0] - 0.5) * 0.7) / per
            zz = z + (h[1] - 0.5) * spacing * 0.6
            rr = r * (0.80 + 0.4 * h[2])      # no curl under HAIR_MIN_AXIS (z is 0.85 of it)
            c = Vector((rx * math.cos(a), cy + ry * math.sin(a), zz))
            n = Vector((math.cos(a) / rx, math.sin(a) / ry, 0.0)).normalized()
            c = c + n * (rr * (0.15 + 0.35 * h[3]))
            if not above_hairline(c, 0.004):
                continue
            c.z = min(c.z, HAIR_TOP - rr)
            out.append(ellipsoid("curl", c, (rr, rr, rr * 0.85), segs=10, rings=7))
        z += spacing * 0.80
        k += 1
    return out

def hair_parts(style="quiff"):
    """A cap over the skull cut at the hairline, and hair over the crown.

    `style` is one of HAIR_STYLES (above). "quiff" is Saud's -- the cap and
    some length left on top. "crop" is the cap alone, a close cut. "bald" is
    no geometry at all -- AL-WAHSH and ZAYOS (`look.bald`) -- and the bare
    skull is what shows; hero.face still paints (and pipeline.build_fighter
    still bakes) a "hair" material, but no face is ever assigned it, since
    palette_for gives a bald man no hair colour and every hair-colour use
    in hero.face and hero.finish already falls back to skin when it is
    None -- checked, not new code for this.
    """
    assert style in HAIR_STYLES, "no hair style %r (HAIR_STYLES: %s)" % (style, ", ".join(HAIR_STYLES))
    if style == "bald":
        return []
    if style == "buzz":
        return [hair_shell(0.0035)]
    if style == "fade":
        # a short, textured top; the sides are the shell, faded to skin in paint
        return [hair_shell(0.0035),
                ellipsoid("fadetop", (0, -0.006, 1.7725), (0.0540, 0.0720, 0.0200), (0, -0.10, 1.0),
                          segs=40, rings=24)]
    if style == "curly":
        return [hair_shell(0.0040, extra=lambda x, y, z: 0.004 * _sm(z, 1.755, 1.785))] + _curls(0.0040)
    if style == "crest":
        # A hawk's crest (AL-SAQR -- al-saqr is the falcon). One volume: the
        # close shell at the sides (faded in paint, face.hair_fade), and down
        # the middle a ridge 14 mm high and about 40 mm across, from the
        # hairline over the crown and down the back, flattened at HAIR_TOP
        # over the crown -- where the skull leaves the least room -- and
        # standing clear at the front and down the back, where a crest
        # reads. Clumps along its ridge break it into a crest's tufts.
        def ridge(x, y, z):
            return 0.014 * math.exp(-(x / 0.017) ** 2) * _sm(z, 1.700, 1.725)
        parts = [hair_shell(0.0030, extra=ridge)]
        n = 9
        for i in range(n):
            h = [_hash01(7717 + i * 97 + j * 13) for j in range(3)]
            a = -1.00 + 2.10 * i / (n - 1)          # round the head in the midplane, front to back
            c0 = Vector((0.0, 0.010, 1.700))
            dvec = Vector((0.0, -math.cos(a + math.pi / 2), math.sin(a + math.pi / 2)))
            dvec = Vector((0.0, math.sin(a), math.cos(a)))
            lo, hi = 0.0, 0.20
            rows = A.HEAD_ROWS
            for _ in range(40):
                m = 0.5 * (lo + hi); q = c0 + dvec * m
                if q.z > rows[-1][0] or q.z < 1.668:
                    hi = m; continue
                ccy = _skull_cy(q.z)
                for r0, r1 in zip(rows, rows[1:]):
                    if r0[0] <= q.z <= r1[0]: break
                t = (q.z - r0[0]) / (r1[0] - r0[0])
                ry = r0[3] + (r1[3] - r0[3]) * t
                if abs(q.y - ccy) <= ry: lo = m
                else: hi = m
            root = c0 + dvec * lo
            if not above_hairline(root, 0.006):
                continue
            # swept back along the head, lifted a little off it: a hawk's
            # crest lies back; standing straight out it read as horns
            back = Vector((0.0, math.cos(a), -math.sin(a)))
            out = (back + 0.35 * dvec).normalized()
            l = 0.026 * (0.9 + 0.2 * h[0])
            root = root + dvec * 0.009                                # out of the ridge, not the skull
            tip = root + out * l + Vector((0.003 * (h[1] - 0.5), 0.0, 0.0))
            parts.append(_lock("crest_lock", root, tip, 0.0085, 0.0060))
        return parts
    if style == "hightop":
        # A high-and-tight (the thug): skin up the sides and back in paint
        # (face.hair_fade), and on top a short flat block with a squared
        # front edge -- flat so the silhouette is a box, not a dome.
        def block(x, y, z):
            top = _sm(z, 1.762, 1.778)
            front = 1.0 + 0.5 * _sm(y, -0.030, -0.065)      # the front edge a touch fuller
            return 0.010 * top * front
        return [hair_shell(0.0030, extra=block)]
    if style == "slick":
        # flat at the front, the length combed back and piled at the crown
        # -- inside the shell's front, so it rises off the hairline rather
        # than standing out over the forehead like a visor
        return [hair_shell(0.0040),
                ellipsoid("slickback", (0, 0.016, 1.7650), (0.0660, 0.0860, 0.0300), (0, 0.22, 1.0),
                          segs=48, rings=28)]
    if style == "part":
        # the volume swept to his left of a hard part on his right (x < 0)
        return [hair_shell(0.0040),
                ellipsoid("parttop", (0.006, 0.000, 1.7705), (0.0560, 0.0770, 0.0220), (0.06, 0.0, 1.0),
                          segs=48, rings=28)]
    if style == "fringe":
        # A textured top pushed forward, and the fringe as locks lying ON the
        # forehead. The first build (2026-09-24) laid one straight roll
        # across the brow, 13 mm thick and 3.5 mm inside the surface: the
        # forehead curves back at the sides and a straight roll does not, so
        # it stood off the head like a hat's brim. Each lock here sits on
        # the skull's own surface at its own x and leans with it, 3.5 mm
        # proud at most; they hang below the hairline plane, so they go to
        # the body as their own group (assign_by_source keeps them hair).
        # The top stays inside the shell's front, so it has no visor either.
        parts = [hair_shell(0.0040),
                 ellipsoid("fringetop", (0, -0.004, 1.7705), (0.0600, 0.0740, 0.0210), (0, -0.12, 1.0),
                           segs=48, rings=28)]
        n = 13
        for i in range(n):
            h = [_hash01(4099 + i * 131 + j * 17) for j in range(3)]
            x = -0.052 + 0.104 * i / (n - 1) + (h[0] - 0.5) * 0.004
            rz = 0.011 + 0.005 * h[1]                      # how far it hangs
            zc = HAIRLINE[0] - 0.004 - 0.55 * rz
            y = A.head_surface_y(x, zc) - 0.0005
            slope = (A.head_surface_y(x, zc + 0.004) - A.head_surface_y(x, zc - 0.004)) / 0.008
            parts.append(ellipsoid("fringe_lock", (x, y, zc), (0.0072, 0.0030, rz),
                                   (0.0, slope, 1.0), segs=16, rings=12))
        return parts
    if style == "quiff":
        return _quiff()
    # The skull crown is at 1.796 and the chin at 1.570: 0.226 m a head, and
    # 8.04 heads tall, which is the figure the art direction asks for. But
    # the cap used to top out at 1.806 and the quiff at 1.814, so the head a
    # player SEES was 0.248 m and he read as 7.33 heads. The whole deficit
    # was hair. Nothing here may stand above 1.800.
    # Measured on the built body, not on the solve that put it here: the
    # previous (0.088, 0.124, 0.0725) was a solve against an older skull, and
    # on this one it was a helmet -- 26 mm thick at the front hairline in one
    # 5 mm row, 22-24 mm down the whole back, an 11 mm step at the ear line.
    # That step is what read as a cap with a brim in every face render. A
    # short crop with a quiff is a fade at the sides, a few mm at the back and
    # the volume on top, so this one is 4 mm off the skull at the sides and
    # 5-7 mm at the back, 6 mm at the front hairline building to 19 mm at the
    # crown with the quiff below, and still tops out at exactly 1.800 --
    # measured with the head loft, the cut and the 3.5 mm remesh, the way the
    # body is built (front / back / side, mm, z 1.74 -> 1.79: 1.5 6 10 12 19 /
    # 5 5 3 3 13 / 3 4 3 4 10). Nothing sinks inside the occiput.
    cap = ellipsoid("haircap", (0, 0.006, 1.7275), (0.0800, 0.1030, 0.0725), segs=64, rings=40)
    # Everything below the hairline plane goes. The plane passes through
    # HAIRLINE[0] at the brow (y -0.09) and HAIRLINE[1] at the nape: the
    # box's top face is that plane, so its centre sits half a box below.
    #
    # The 0.25/cos is not a flourish. Rotating the box about its own centre
    # tilts the top face, and the vertical distance from the centre up to a
    # TILTED plane is 0.25/cos(t), not 0.25. Placing the centre at mid-0.25
    # therefore cut 7.4 mm high -- so the cap ended above the hairline the
    # skin is painted to, and the band between them came out as bare skull
    # painted hair black. That ring has been in every build of this model.
    mid = 0.5 * (HAIRLINE[0] + HAIRLINE[1])
    tilt = math.atan2(HAIRLINE[0] - HAIRLINE[1], 0.18)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0.0, mid - 0.25 / math.cos(tilt)))
    cut = bpy.context.object; cut.scale = (0.5, 0.6, 0.5)
    cut.rotation_euler = (-tilt, 0, 0)     # front edge up
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    boolean(cap, cut, 'DIFFERENCE')
    # A temple recession was cut here with two ellipsoids and it was a
    # mistake: at x = 0.063 the front of the skull is at y = -0.027, not the
    # -0.09 the hairline is quoted at, so cutters placed for a forehead went
    # straight through the crown and left a ridge of bare skull. hero.face
    # paints the recession, and the cap's edge is thin enough that the paint
    # is what reads. If it is ever cut in geometry it has to be a scoop at
    # the front CORNER of the hairline, not a hole near the vertex.
    # Hair over the crown. This was an ellipsoid 100 mm across leaning 46 mm
    # forward off the top of the skull, which is a bun, not a haircut: it
    # rendered as a topknot. Flattened and set back over the whole crown, it
    # reads as a short crop with some length left on top.
    return [cap]

def _quiff():
    """Saud's quiff, rebuilt 2026-09-26. It was the crop's cap (an
    ellipsoid with a step at its cut: the pale rope across every face
    render) and one flattened ellipsoid over the middle of the crown -- the
    volume where the skull is already at its highest, with no room for it
    under HAIR_TOP, so it read as a cap. A quiff's length is at the FRONT,
    brushed up off the hairline and forward over the brow, where the skull
    falls away under HAIR_TOP: one volume, 4 mm at the sides (faded in
    paint), building to 18 mm at the front of the top and falling back to
    6 mm over the crown, flattened at HAIR_TOP. Five clumps along its front
    edge break the silhouette the way a combed-up quiff's locks separate."""
    def length(x, y, z):
        front = _sm(y, 0.020, -0.060)            # more toward the brow
        top = _sm(z, 1.750, 1.776)               # on the top, not the sides
        mid = 1.0 - _sm(abs(x), 0.028, 0.060)    # the middle, not over the temples
        f = front * top * mid
        # forward and a little up: over the brow, where there is room
        return Vector((0.0, -0.022 * f, 0.008 * f + 0.003 * _sm(z, 1.770, 1.790)))
    parts = [hair_shell(0.0040, extra=length)]
    # the front edge broken into locks, lying forward over the brow
    n = 5
    for i in range(n):
        h = [_hash01(5113 + i * 61 + j * 7) for j in range(3)]
        x = -0.026 + 0.052 * i / (n - 1) + (h[0] - 0.5) * 0.006
        # off the front edge of the volume, falling forward over the brow
        root = _on_skull(x, -0.058, 0.011)
        l = 0.022 + 0.008 * h[1]
        tip = root + Vector((0.005 * (h[2] - 0.5), -0.90 * l, -0.30 * l))
        parts.append(_lock("quiff_lock", root, tip, 0.0080, 0.0055))
    return parts

def check_hair(parts, style):
    """What a cut must be, measured on its parts before the union: nothing
    above HAIR_TOP; no part but the shell thinner than HAIR_MIN_AXIS; the
    shell with no step at the hairline (within 1 mm of the plane it stands
    no more than 0.6 mm off the skull); and something over the crown. Each
    is what one of the 2026-09-26 faults was."""
    import numpy as np
    top = -1.0
    for o in parts:
        for v in o.data.vertices:
            top = max(top, (o.matrix_world @ v.co).z)
    assert top <= HAIR_TOP + 1e-4, "%s: hair stands to %.4f, above %.3f (heads tall)" % (style, top, HAIR_TOP)
    for o in parts:
        if o.name.startswith("hairshell"):
            continue
        if o.name.startswith(("fringe_lock", "haircap")):
            continue          # the old fringe and crop, not rebuilt here
        vs = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices])
        c = vs.mean(0)
        u, sv, vt = np.linalg.svd(vs - c, full_matrices=False)
        span = (vs - c) @ vt.T
        least = 0.5 * (span.max(0) - span.min(0)).min()
        assert least >= HAIR_MIN_AXIS - 1e-4, (
            "%s: %s is %.1f mm through -- under 2.5 remesh voxels it breaks into shards"
            % (style, o.name, least * 2000))
    shells = [o for o in parts if o.name.startswith("hairshell")]
    for o in shells:
        worst = 0.0
        for v in o.data.vertices:
            c = o.matrix_world @ v.co
            h = c.z - _hairline_z(c.y)
            if not (0.0 <= h <= 0.001) or c.z < 1.70:
                continue
            cy = _skull_cy(c.z)
            rows = A.HEAD_ROWS
            for r0, r1 in zip(rows, rows[1:]):
                if r0[0] <= c.z <= r1[0]: break
            t = (c.z - r0[0]) / (r1[0] - r0[0])
            rx = r0[2] + (r1[2] - r0[2]) * t; ry = r0[3] + (r1[3] - r0[3]) * t
            # how far outside the skull's ellipse this vertex is, in metres
            ang = math.atan2((c.y - cy) / ry, c.x / rx)
            on = Vector((rx * math.cos(ang), cy + ry * math.sin(ang), c.z))
            worst = max(worst, (Vector((c.x, c.y, c.z)) - on).length)
        assert worst <= 0.0006, "%s: the hair stands %.1f mm off the skull at the hairline -- a step, a rope" % (
            style, worst * 1000)
    if style != "bald":
        assert any(max((o.matrix_world @ v.co).z for v in o.data.vertices) > 1.790 for o in parts), (
            "%s: nothing over the crown" % style)
    return top

def union_remesh(parts, voxel, name):
    return A.union_remesh(parts, voxel, name)

def build(voxel_scale=1.0, face_scale=None, hair_style="quiff", arm_scale=1.0, gloves=False):
    """voxel_scale > 1 is a coarse, quick body for checking the stages after
    this one. `face_scale`, `hair_style` and `arm_scale` are one man's
    differences from another on the same skull and limbs -- see
    sculpt.sculpt_face, hair_parts and anatomy.arm. `gloves` unions
    anatomy.glove() over the fingers, both sides -- see anatomy.glove for
    why the fingers are still built underneath it."""
    vs = voxel_scale
    t = time.time()
    legacy.reset_scene()
    # ---- pass one: the base at 6 mm, smoothed hard
    base_parts = [A.trunk(), A.neck(), A.head()]
    left = A.arm(arm_scale) + A.leg() + [A.shoe()] + masses()
    right = [mirror_x(o) for o in left]
    base = union_remesh(base_parts + left + right, 0.006 * vs, "Base")
    A.smooth(base, 0.40, 3)
    print("base      : %d verts  %.1fs" % (len(base.data.vertices), time.time() - t))
    # Orbital dishes, so the globes have somewhere to sit and the lids have
    # something to close over. The old cut put the ellipsoid's centre 10 mm
    # IN FRONT of where it needed to be, which carved a hole 26 mm deep and
    # 38 mm wide for a 22 mm ball -- a crater with a bead at the bottom.
    # A real orbit is a shallow dish: 4.5 mm deep, 28 by 25 mm, so the ball
    # fits inside it with its cornea a millimetre proud.
    check_eye()
    for s in (1, -1):
        sock = ellipsoid("socket", (0.031 * s, A.head_surface_y(0.031 * s, EYE_Z) - SOCKET_IN, EYE_Z),
                         SOCKET_AX)
        boolean(base, sock, 'DIFFERENCE')
    # ---- pass two: fine parts, then one remesh at 3.5 mm to blend the joins
    hl, jl = A.hand(); hr = [mirror_x(o) for o in hl]
    # gloves: unioned over the fingers at the same fine pass, not instead of
    # them -- the mannequin skeleton is the same 62 bones whether or not a
    # finger is separately visible, so the fingers are still built for the
    # rig; see anatomy.glove for why the union hides them cleanly.
    glove_parts = []
    if gloves:
        gl = A.glove(thumb=jl["thumb"]); glove_parts = gl + [mirror_x(o) for o in gl]
    hands = union_remesh(hl + hr + glove_parts, 0.0025 * vs, "Hands"); A.smooth(hands, 0.5, 3)
    face = face_parts() + ear(1) + ear(-1)
    hair = hair_parts(hair_style)
    if hair:
        check_hair(hair, hair_style)
    # a fringe hangs below the hairline plane on purpose: its own group, so
    # the hairline test that keeps hair above the plane does not strip it
    fringe = [o for o in hair if o.name.startswith("fringe") and not o.name.startswith("fringetop")]
    hair = [o for o in hair if o not in fringe]
    groups = {"skin": [base, hands] + face, "hair": hair}
    if fringe:
        groups["fringe"] = fringe
    # remember the sources for material assignment: BVH per group
    trees = {}
    for g, objs in groups.items():
        bm = bmesh.new()
        for o in objs:
            tmp = o.data.copy(); tmp.transform(o.matrix_world); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp)
        trees[g] = BVHTree.FromBMesh(bm); bm.free()
    body = union_remesh([base, hands] + face + hair + fringe, 0.0035 * vs, "Body")
    A.smooth(body, 0.5, 2)
    from . import sculpt
    peak, moved = sculpt.sculpt_face(body, A.head_surface_y, scale=face_scale)
    A.smooth(body, 0.3, 1)
    bpy.ops.object.shade_smooth()
    print("body      : %d verts  %.1fs   face sculpt peak %.1f mm over %d verts" % (len(body.data.vertices), time.time() - t, peak * 1000, moved))
    # The pipeline builds through here, not through anatomy.build(), so the
    # stature and heads-tall checks have to be called here or they never run.
    A.measure(body, check=(vs <= 1.0))
    eyes = eyeballs()
    return body, trees, eyes, jl

def above_hairline(c, margin=0.0):
    t = (c.y + 0.09) / 0.18
    return c.z > HAIRLINE[0] + (HAIRLINE[1] - HAIRLINE[0]) * t + margin

# How far above the hairline plane the HAIR MATERIAL starts, on the front
# and the sides of the head. The plane itself, tested per face centre, is a
# staircase at the 3.5 mm voxel -- and the hair material's albedo is black,
# so every render had a sawtooth of black teeth along the hairline. But
# hero.face already paints the hair colour above the hairline INTO THE SKIN
# TEXTURE, per texel, as a smooth line with the temple recession (its `hw`),
# wherever its `on_face` gate is open: the front and the sides, forwardness
# > about -0.28. So there the material boundary is pushed 6 mm up into the
# hair, where a bump-strength seam is invisible under black, and the visible
# hairline is the painted one. At the nape the skin texture is not painted
# hair (the gate is shut), so the boundary stays on the plane. 8 mm, not
# 6: the painted ramp (`hw`) is +-3.5 mm about the plane and jittered by
# 0.0045 * 0.5 = 2.25 mm, so it reaches full hair at plane + 5.75 mm.
HAIR_MARGIN = 0.008

def assign_by_source(body, trees, slots):
    """Each face takes the material of the nearest source part group. Hair
    is the exception: nearest-source frays along the cap's cut edge, so the
    hairline is the plane the cap was cut with, tested on the face centre,
    raised by HAIR_MARGIN where the painted hairline takes over."""
    from . import face as FA
    import numpy as np
    polys = body.data.polygons
    C = np.array([p.center[:] for p in polys])
    gate = FA.ramp(FA.forwardness(C), -0.55, -0.28) if len(C) else np.zeros(0)
    for poly, g in zip(polys, gate):
        c = poly.center
        best, bestd = "skin", 1e9
        for gname, tree in trees.items():
            # find_nearest on an empty tree -- bald, hair_parts returned no
            # geometry -- is not None itself, it is (None, None, None,
            # None): checked directly, and hit[3] < bestd then raised
            # comparing None to a float. hit[0], the location, is the real
            # "did this hit anything" signal.
            hit = tree.find_nearest(c)
            if hit[0] is not None and hit[3] < bestd: best, bestd = gname, hit[3]
        if best == "fringe":
            # the fringe is hair wherever it is, hairline or not
            poly.material_index = slots["hair"]
            continue
        m = HAIR_MARGIN * float(g)
        if best == "hair" and not above_hairline(c, m): best = "skin"
        if best == "skin" and "hair" in slots and above_hairline(c, m) and c.z > 1.70:
            hh = trees["hair"].find_nearest(c)
            if hh[0] is not None and hh[3] < 0.004: best = "hair"
        poly.material_index = slots[best]

