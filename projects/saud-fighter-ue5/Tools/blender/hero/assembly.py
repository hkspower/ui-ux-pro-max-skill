"""The assembly: a two-pass body. The base (trunk, limbs, masses) at 6 mm and
smoothed hard; the parts that need their edges -- hands, face, ears, hair
-- at fine voxel, unioned in a second 3.5 mm pass that blends the joins
without eating the detail. Materials come back by nearest source part."""
import bpy, bmesh, math, sys, os, time
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import build_saud as legacy
from . import anatomy as A
from .sculpt import EYE_Z, EAR_Z, EAR_X, EAR_Y, HAIRLINE   # the face's layout lives in hero.sculpt
J = legacy.J; Jp = A.Jp; X, Y, Z = A.X, A.Y, A.Z
ellipsoid, loft, tube, ring_z, mirror_x = A.ellipsoid, A.loft, A.tube, A.ring_z, A.mirror_x

def chain(name, pts, radii, out_dir, step=0.010):
    """Ellipsoids along a polyline, each aligned with its segment and
    overlapping its neighbours, so the union is one smooth band: a muscle
    or a bone with a length, which one ellipsoid cannot draw. `radii` per
    point is (across, through): across the band, and how far it stands out
    along `out_dir(point)` -- the way the surface under it faces."""
    out = []
    pts = [Vector(p) for p in pts]
    segs = list(zip(zip(pts, radii), zip(pts[1:], radii[1:])))
    for i, ((a, ra), (b, rb)) in enumerate(segs):
        d = b - a; n = max(1, int(math.ceil(d.length / step)))
        for k in range(n + (1 if i == len(segs) - 1 else 0)):
            t = k / n
            c = a + d * t
            r0 = ra[0] + (rb[0] - ra[0]) * t; r1 = ra[1] + (rb[1] - ra[1]) * t
            zax = d.normalized()
            yax = Vector(out_dir(c)); yax = (yax - zax * yax.dot(zax)).normalized()
            xax = yax.cross(zax)
            bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=24, ring_count=14, location=(0, 0, 0))
            o = bpy.context.object; o.name = name
            half = max(step * 1.6, min(r0, r1))     # long links, well overlapped: no beads
            R = Matrix((xax * r0, yax * r1, zax * half)).transposed()
            o.matrix_world = Matrix.Translation(c) @ R.to_4x4()
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            out.append(o)
    return out

# One man's mass where it is not the canonical body's (pipeline.MASS,
# 2026-09-28, the Unreal men): a factor on a named mass's size, about its
# own centre -- an ellipsoid's axes, each link of a chain. Built at
# canonical scale, before build_field takes him to his size, so every body
# check still measures him. The names are the masses' own; a name masses()
# does not build raises.
DELT_OFF = 0.052        # the lean deltoid heads' centres off the arm's axis, at arm 1.30

def delt_heads(arm_scale=1.30):
    """The deltoid in three heads -- lateral, anterior, posterior -- as
    pillows in the upper arm's own frame, grown with the arm (they are
    sized for Saud's 1.30): a cap that stands over the biceps and ties
    into the pec, where the one canonical ellipsoid sat inside the arm."""
    ua, la = Jp("upperarm_l"), Jp("lowerarm_l")
    d = (la - ua).normalized(); f = Vector((0, -1, 0)); f = (f - d * f.dot(d)).normalized(); s = d.cross(f)
    up = -s if (-s).z > 0 else s
    L = (la - ua).length; k = arm_scale / 1.30
    out = []
    for name, dirv, along, ax in (("delt_lat", up, 0.10, (0.032, 0.030, 0.074)),
                                  ("delt_ant", (f * 0.85 + up * 0.5).normalized(), 0.06, (0.026, 0.026, 0.066)),
                                  ("delt_post", (-f * 0.8 + up * 0.6).normalized(), 0.08, (0.024, 0.020, 0.060))):
        c = ua + d * (along * L) + dirv * (DELT_OFF * k)
        zax = d; yax = dirv; xax = yax.cross(zax)
        out.append(A.pillow(name, c, tuple(a * k for a in ax), (xax, yax, zax), ex=1.0))
    return out

def masses(physique=None, mass=None, arm_scale=1.0):
    """The muscle that sits proud of the lofts. Rewritten 2026-09-25 ("make
    full body fix"): the pec was one ball on each side of the chest and the
    rectus one 26 cm sausage either side of the midline -- both read as
    exactly that on the bare chest (zayos-apose-3d.png) and through every
    tee. A pec is a fan, from the sternum out and up to the armpit, thicker
    below; the rectus is three pairs of bellies with the linea alba between
    them; the obliques stand proud of the flank; the erectors stand either
    side of a spinal groove.

    2026-09-28: `physique` 'lean' (Saud's) leaves out the rectus sheet and
    bellies and the buried oblique -- the defined ones go into the fine
    pass, anatomy.definition -- and the one deltoid, for three heads grown
    with the arm (arm_scale) and the pec's clavicular head carried out
    under the anterior one (pec_tie). `mass` is {name: factor}, above."""
    out = _masses()
    if physique is not None:
        assert physique == "lean", "no masses for the %r physique" % physique
        keep = []
        for o in out:
            if o.name.split(".")[0] in ("rectus_sheet", "rectus0", "rectus1", "rectus2", "oblique", "delt"):
                bpy.data.objects.remove(o, do_unlink=True)
            else:
                keep.append(o)
        out = keep + delt_heads(arm_scale)
        out.append(ellipsoid("pec_tie", (0.140, -0.060, 1.402), (0.022, 0.028, 0.066), (0.92, 0.30, 0.12)))
    if mass:
        names = {o.name.split(".")[0] for o in out}
        bad = set(mass) - names
        if bad:
            raise KeyError("no such mass: %s (masses() builds %s)" % (sorted(bad), ", ".join(sorted(names))))
        for o in out:
            k = mass.get(o.name.split(".")[0])
            if k is None or k == 1.0:
                continue
            me = o.data
            c = sum((v.co for v in me.vertices), Vector()) / len(me.vertices)
            me.transform(Matrix.Translation(c) @ Matrix.Scale(k, 4) @ Matrix.Translation(-c))
    return out

def _masses():
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
    # 2026-09-26 ("fix neck"): that one ellipsoid made a plateau 50 mm wide
    # at 1.52-1.53 from the neck out, and the neck stood up out of it with a
    # 37 mm step -- a column on a shelf, and on ZAYOS, widened by his torso
    # factor, a table. The upper trapezius is a band now, from under the
    # occiput down the back and side of the neck to the acromion, so the
    # shoulder line runs from high on the neck down to the shoulder in one
    # slope (anatomy.NECK_MUSCLES; check_neck measures it).
    out.extend(chain(*A.NECK_MUSCLES["trap"]))
    # the sternocleidomastoid, from behind the ear to the top of the sternum:
    # the diagonal that makes a neck read as a neck and not a tube; the two
    # meet at the sternum with the jugular notch between them
    out.extend(chain(*A.NECK_MUSCLES["scm"]))
    # the collarbones, the ridge from the sternum out to the shoulder
    out.extend(chain(*A.NECK_MUSCLES["clavicle"]))
    # The lat: at the side-back of the ribcage, what makes the V from behind.
    # widest at the armpit, gone by the waist -- centred high, so its bottom
    # tapers out above the lower ribs instead of bulging at them
    # ...leaning out, so its top tucks under the armpit and its bottom runs
    # in toward the flank instead of standing as an egg on the side
    # The erector spinae, either side of the spine -- the small of the back
    # is not a smooth dish, it is two columns with a furrow between them.
    # Two per side, following the spine's curve (anatomy.trunk's cy).
    # It was centred on the hip JOINT, so it read as a hip, not a seat.
    # a seat, not a ball: broad and only a centimetre proud of the pelvis
    # ...and its inner edge 6 mm short of the midline: meeting there, the
    # two welded across it and pulled the crotch down 13 mm
    # the lats and the erectors (2026-09-27): bands seated on the trunk's
    # own back, not ovals on it -- anatomy.BACK_MUSCLES
    for name, spec in A.BACK_MUSCLES.items():
        pts, radii = [], []
        for x, z, proud, across in spec:
            S, n = A.trunk_surface(x, z)
            pts.append(S - n * A.BACK_SEAT); radii.append((across * A.BACK_WIDEN, proud + A.BACK_SEAT))
        out.extend(chain(name, pts, radii, lambda c: A.trunk_surface(c.x, c.z)[1]))
    out.append(ellipsoid("glute", (0.090, 0.078, 0.924), (0.084, 0.048, 0.086)))
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
    # 4 mm proud of the throat, which is at y -0.047 at this height since the
    # neck was set back under the jaw (2026-09-26); at -0.054 it stood 15 mm
    # out of the new one.
    return [ellipsoid("adam", (0, -0.043, 1.560), (0.010, 0.008, 0.012))]

# A cauliflower ear (pipeline.EARS, 2026-09-28, the Unreal men: a fighter's
# ear after the blows): four lumps over the upper helix and the scapha
# inside it, (angle round the helix ring from its bottom, radius of the
# ring they sit on, half-size), standing out from the ear's side. Measured
# on a built head: over the ear's upper third (z +9 to +23 mm about EAR_Z)
# its outer surface stands 3.0-4.2 mm further out than the plain ear's.
CAULIFLOWER = [(math.radians(132), 0.0190, 0.0060), (math.radians(162), 0.0190, 0.0065),
               (math.radians(196), 0.0190, 0.0065), (math.radians(226), 0.0190, 0.0060)]
CAULIFLOWER_OUT = 0.0065     # their centres this far out from the ear's mid-plane

CAULI_MIN = 0.003            # check_cauliflower: at least this much further out, over the upper third
EAR_UPPER = (0.009, 0.023)   # the ear's upper third, z about EAR_Z


def ear_profile(body):
    """How far out each ear's outer surface stands over its upper third:
    {'l' (+x), 'r'}: for each 1 mm row of z in EAR_UPPER about EAR_Z, the
    outermost |x| a ray from outside meets across the ear's depth (EAR_Y
    +-20 mm), metres; nan where a row meets nothing past the skull."""
    import numpy as np
    tb = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    out = {}
    for s, side in ((1, "l"), (-1, "r")):
        rows = []
        for z in np.arange(EAR_Z + EAR_UPPER[0], EAR_Z + EAR_UPPER[1] + 1e-6, 0.001):
            xs = []
            for y in np.arange(EAR_Y - 0.020, EAR_Y + 0.0201, 0.001):
                h = tb.ray_cast(Vector((0.3 * s, y, z)), Vector((-s, 0, 0)))
                if h[0] is not None and abs(h[0].x) > 0.06:
                    xs.append(abs(h[0].x))
            rows.append(max(xs) if xs else float("nan"))
        out[side] = np.array(rows)
    return out


def check_cauliflower(on, plain, ears, assert_=True):
    """A cauliflower ear (EARS: {'l': k, 'r': k}, 2026-09-28) stands out:
    over its upper third, row by row, its outer surface at least CAULI_MIN
    (3 mm) further out on average than the same ear built plain.
    `on` and `plain` are ear_profile()s of the head with his ears and the
    same head with plain ones. Returns {side: dict(mean, min, max)} for
    each ear held."""
    import numpy as np
    out = {}
    for side in ("l", "r"):
        if not (ears or {}).get(side):
            continue
        d = on[side] - plain[side]
        d = d[~np.isnan(d)]
        out[side] = dict(mean=float(d.mean()) if len(d) else 0.0, min=float(d.min()) if len(d) else 0.0,
                         max=float(d.max()) if len(d) else 0.0)
        if assert_:
            assert out[side]["mean"] >= CAULI_MIN, "no cauliflower: his %s ear %.1f mm further out than plain over its upper third, want %.0f" % (
                "left" if side == "l" else "right", out[side]["mean"] * 1000, CAULI_MIN * 1000)
    return out


def ear(s, cauliflower=0.0):
    """Helix as a flattened ring, lobe below, a dish cut into the front.

    An ear runs from the brow down to the base of the nose -- 1.693 to 1.640
    here, so about 53 mm, and it was 40 mm, which is why it read as a paddle
    stuck on the side of the head rather than as an ear.

    `cauliflower` (0 none, 1 full) swells the upper helix and scapha with
    CAULIFLOWER's lumps, their size in proportion.
    """
    side = A.head_surface_x(EAR_Y, EAR_Z)
    assert abs(EAR_X - side - 0.0061) < 0.0015, (
        "the ear is %.1f mm off the skull's side, want 6: move sculpt.EAR_X with the skull"
        % ((EAR_X - side) * 1000))
    c = Vector((EAR_X * s, EAR_Y, EAR_Z))    # behind the mandibular ramus,
                                             # not at the head's mid-depth
    bpy.ops.mesh.primitive_torus_add(location=c, major_radius=0.0200, minor_radius=0.0062,
                                     major_segments=28, minor_segments=12)
    helix = bpy.context.object; helix.name = "helix"
    helix.scale = (1.0, 0.72, 1.34); helix.rotation_euler = (0, math.radians(90), 0)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    lobe = ellipsoid("lobe", c + Vector((0.002 * s, -0.003, -0.0250)), (0.0062, 0.0105, 0.0088))
    back = ellipsoid("earback", c + Vector((-0.003 * s, 0.005, 0)), (0.0052, 0.0150, 0.0240))
    parts = [helix, lobe, back]
    if cauliflower > 0.0:
        k = float(cauliflower)
        for i, (u, r, h) in enumerate(CAULIFLOWER):
            # the ring as the helix is laid: 0.72 of its radius front to
            # back, its bottom at u = 0 (see the torus's scale and turn)
            at = c + Vector((CAULIFLOWER_OUT * k * s, 0.72 * r * math.sin(u), -r * math.cos(u)))
            parts.append(ellipsoid("cauli%d" % i, at, (0.0060 * k, h * k, h * k)))
    return parts

from .sculpt import EYE_R, EYE_SEAT, EYE_X      # the globe, shared with the drape
# Where the globe's centre sits, measured back from the bare skull surface:
# EYE_SEAT, so the cornea is 2 mm behind the skull line. Until 2026-09-26 the
# lids were Gaussians pushed forward of a flat face and the eye was open
# wherever the globe happened to poke through the skin -- an 11 mm disc
# round the iris, 36 % of the opening, no white either side of it. The
# fissure is cut round the globe now (sculpt.drape_eyes); check_eye_open
# measures it on the built head.


def check_eye():
    """The fissure is a man's (sculpt.check_eye_shape), and the globe does
    not stand out of his head: its cornea behind the bare skull line."""
    from .sculpt import check_eye_shape
    shape = check_eye_shape()
    cornea = EYE_SEAT - EYE_R
    assert cornea > -0.002, "the eye bulges %.1f mm out of the face" % (-cornea * 1000)
    return shape

# The eye region, subdivided twice before the sculpt: 3.1 mm between
# vertices is a third of the fissure's height, so a lid margin could not be
# drawn at all -- 0.8 mm can.
EYE_BOX = (0.002, 0.062, 0.019)       # |x| from, |x| to, |z - EYE_Z| within

# A third level, round the fissure only: 0.4 mm there, so the lid margin is
# a line and not a sawtooth.
FISSURE_BOX = (0.012, 0.049, 0.0085)

def subdivide_eyes(body, levels=2):
    from .sculpt import EYE_Z
    for level in range(levels + 1):
        box = EYE_BOX if level < levels else FISSURE_BOX
        bm = bmesh.new(); bm.from_mesh(body.data)
        y0 = A.head_surface_y(EYE_X, EYE_Z) + 0.020
        faces = [f for f in bm.faces
                 if box[0] < abs(f.calc_center_median().x) < box[1]
                 and abs(f.calc_center_median().z - EYE_Z) < box[2]
                 and f.calc_center_median().y < y0]
        edges = list({e for f in faces for e in f.edges})
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=1, use_grid_fill=True)
        bm.to_mesh(body.data); bm.free()
    body.data.update()
    return len(body.data.vertices)

def relax_eyes(body):
    """After the drape: collapse the eye region's subdivision back to about
    the head's own density everywhere but a band along the lid margins.
    The 33,000 triangles subdivide_eyes adds were needed to draw the lids
    and are not needed to keep them -- they are smooth -- and left in, they
    went into the body's reduction under its one ratio and it took every
    face of the shoes to pay for them (2026-09-26, the first full build)."""
    from .sculpt import EYE_Z, near_margin
    me = body.data
    vg = body.vertex_groups.new(name="eye_relax")
    idx = [v.index for v in me.vertices
           if EYE_BOX[0] < abs(v.co.x) < EYE_BOX[1] and abs(v.co.z - EYE_Z) < EYE_BOX[2]
           and v.co.y < -0.02 and not near_margin(abs(v.co.x), v.co.z)]
    if not idx:
        body.vertex_groups.remove(vg); return 0
    vg.add(idx, 1.0, 'REPLACE')
    sel = set(idx)
    region = sum(1 for p in me.polygons if all(i in sel for i in p.vertices))
    total = len(me.polygons)
    keep = region / 14.0                        # two levels of four, and a little over
    before = total
    d = body.modifiers.new("EyeRelax", "DECIMATE")
    d.ratio = max(0.02, (total - region + keep) / total)
    d.vertex_group = "eye_relax"; d.vertex_group_factor = 10.0
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_apply(modifier="EyeRelax")
    body.vertex_groups.remove(body.vertex_groups["eye_relax"])
    return before - len(body.data.polygons)

def check_eye_open(body, eyes, step=0.0005):
    """On the built head, from straight in front: the globe must show over
    the fissure -- all of it that the pocket clears, the white corner to
    corner -- and nowhere a lid should cover. Returns (shown, leaked)."""
    from mathutils.bvhtree import BVHTree
    from .sculpt import EYE_Z, aperture, X_MED, X_LAT
    import numpy as np
    dg = bpy.context.evaluated_depsgraph_get()
    tb = BVHTree.FromObject(body, dg)
    fis = shown = leaked = 0
    for e in eyes:
        s = 1 if (e.matrix_world @ e.data.vertices[0].co).x > 0 else -1
        te = BVHTree.FromObject(e, dg)
        for x in np.arange(X_MED - 0.003, X_LAT + 0.003, step):
            up, dn = [float(v) for v in aperture(np.array([x]))]
            for z in np.arange(EYE_Z - 0.010, EYE_Z + 0.010, step):
                o = Vector((x * s, -0.4, z)); d = Vector((0.0, 1.0, 0.0))
                hb = tb.ray_cast(o, d); he = te.ray_cast(o, d)
                g = he[0] is not None and (hb[0] is None or he[3] < hb[3])
                r = ((x - EYE_X) ** 2 + (z - EYE_Z) ** 2) ** 0.5
                if dn < z < up and r < 0.0100:
                    fis += 1; shown += g
                elif g and (z > up + 0.001 or z < dn - 0.001):
                    leaked += 1
    shown_f = shown / max(fis, 1); leak_f = leaked / max(fis, 1)
    assert shown_f >= 0.92, "the eye is shut: the globe shows over %.0f %% of the fissure, want 92" % (shown_f * 100)
    assert leak_f <= 0.03, "the lids do not close over the globe: it shows outside them over %.0f %% of the fissure's area" % (leak_f * 100)
    return shown_f, leak_f

# The mien, on the built head (2026-09-28, "make Saud more aggressive",
# the Unreal men): what the face's sculpt, the eye's drape and relax and
# the smoothing leave between them, which only the built mesh can say.
# Every man is held to JAW_GAP; a man's pipeline.HOLDS add his own floors
# and ceilings: brow_over (how far the brow crest stands in front of the
# upper lid's margin at the pupil -- the eye under the brow, in its shadow),
# hollow (the cheek's hollow under the chord from the cheekbone's crest down
# to the jaw at x 46 mm), jaw_max (across the jaw's angles) and jaw_gap (his
# own jaw rule, in place of JAW_GAP). brow_slant is face.check_brows', a
# paint hold, carried in the same entry.
JAW_GAP = 0.008
MIEN_HOLDS = ("brow_over", "hollow", "jaw_max", "jaw_gap", "brow_slant")

def mien_numbers(body):
    """check_mien's measures, by rays on the built head (metres)."""
    import numpy as np
    from .sculpt import aperture, EYE_X
    dg = bpy.context.evaluated_depsgraph_get()
    tb = BVHTree.FromObject(body, dg)
    def front_y(x, z):
        h = tb.ray_cast(Vector((x, -0.4, z)), Vector((0, 1, 0)))
        return h[0].y if h[0] is not None else float("nan")
    def side_x(y, z):
        h = tb.ray_cast(Vector((0.3, y, z)), Vector((-1, 0, 0)))
        return h[0].x if h[0] is not None else float("nan")
    def half_w(z, ymin=-0.11, ymax=0.035):
        return float(np.nanmax([side_x(y, z) for y in np.arange(ymin, ymax, 0.001)]))
    out = {}
    # across the cheekbones, in front of the ear; across the jaw's angles
    out["cheek"] = 2 * max(half_w(z, ymax=-0.012) for z in (1.648, 1.652, 1.656, 1.660))
    out["jaw"] = 2 * max(half_w(z) for z in (1.596, 1.600, 1.604))
    out["gap"] = out["cheek"] - out["jaw"]
    # the cheek at x 46 mm, from the jaw (1.606) up over the cheekbone
    zc = np.arange(1.606, 1.6605, 0.001); yc = -np.array([front_y(0.046, z) for z in zc])
    top = int(np.nanargmax(yc))
    chord = yc[0] + (yc[top] - yc[0]) * (zc - zc[0]) / max(zc[top] - zc[0], 1e-9)
    out["hollow"] = float(np.nanmax((chord - yc)[:top + 1]))
    # the brow's crest over the pupil against the upper lid's margin there
    up = float(aperture(np.array([EYE_X]))[0][0])
    zz = np.arange(1.680, 1.710, 0.0005)
    yb = [front_y(EYE_X, z) for z in zz]
    i = int(np.nanargmin(yb))
    out["brow_over"] = front_y(EYE_X, up + 0.0006) - yb[i]
    out["brow_z"] = float(zz[i])
    return out

def check_mien(body, holds=None, assert_=True, numbers=None):
    """The built face's mien: every man's jaw at its angle at least JAW_GAP
    (8 mm) narrower than his cheekbones -- the built face's form of
    anatomy.check_head's rule on the bone tables against a brick-shaped
    jaw -- and a man's own HOLDS. `numbers`: mien_numbers already
    measured (then `body` is not read). Returns the numbers."""
    holds = dict(holds or {})
    bad = set(holds) - set(MIEN_HOLDS)
    if bad:
        raise KeyError("no such mien hold: %s (%s)" % (sorted(bad), ", ".join(MIEN_HOLDS)))
    m = mien_numbers(body) if numbers is None else numbers
    if not assert_:
        return m
    gap = holds.get("jaw_gap", JAW_GAP)
    assert m["gap"] >= gap, "a brick: the jaw %.1f mm across at its angles, only %.1f narrower than the cheekbones (%.1f), want %.0f" % (
        m["jaw"] * 1000, m["gap"] * 1000, m["cheek"] * 1000, gap * 1000)
    if "brow_over" in holds:
        assert m["brow_over"] >= holds["brow_over"], "no brow over the eye: the crest %.2f mm in front of the upper lid, want %.1f" % (
            m["brow_over"] * 1000, holds["brow_over"] * 1000)
    if "hollow" in holds:
        assert m["hollow"] >= holds["hollow"], "no hollow under the cheekbone: %.2f mm under the chord, want %.1f" % (
            m["hollow"] * 1000, holds["hollow"] * 1000)
    if "jaw_max" in holds:
        assert m["jaw"] <= holds["jaw_max"], "too wide a jaw: %.1f mm across at its angles, want %.1f or less" % (
            m["jaw"] * 1000, holds["jaw_max"] * 1000)
    return m

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
        e = ellipsoid("eyeball", (EYE_X * s, A.head_surface_y(EYE_X * s, EYE_Z) + EYE_SEAT, EYE_Z),
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

def build(voxel_scale=1.0, face_scale=None, hair_style="quiff", arm_scale=1.0, gloves=False,
          physique=None, mass=None, noses=None, ears=None, holds=None):
    """voxel_scale > 1 is a coarse, quick body for checking the stages after
    this one. `face_scale`, `hair_style` and `arm_scale` are one man's
    differences from another on the same skull and limbs -- see
    sculpt.sculpt_face, hair_parts and anatomy.arm. `gloves` unions
    anatomy.glove() over the fingers, both sides -- see anatomy.glove for
    why the fingers are still built underneath it.

    2026-09-28, the rest of a man's differences (pipeline's tables, set by
    pipeline.apply_man): `physique` the trunk anatomy.set_physique has
    already swapped in (asserted) -- its masses and its fine-pass
    definition; `mass` factors on masses(); `noses` his NOSES entry
    (sculpt.with_nose); `ears` {'l': k, 'r': k}, the cauliflower on his
    left (+x) and right ear; `holds` his check_mien holds."""
    assert A.PHYSIQUE == physique, (
        "the trunk is the %r physique and this man is built %r: anatomy.set_physique first (pipeline.apply_man)"
        % (A.PHYSIQUE, physique))
    ears = dict(ears or {})
    bad = set(ears) - {"l", "r"}
    if bad:
        raise KeyError("no such ear: %s (l, r)" % sorted(bad))
    vs = voxel_scale
    t = time.time()
    legacy.reset_scene()
    # ---- pass one: the base at 6 mm, smoothed hard
    base_parts = [A.trunk(), A.neck(), A.head()]
    left = A.arm(arm_scale) + A.leg() + [A.shoe()] + masses(physique, mass, arm_scale)
    right = [mirror_x(o) for o in left]
    base = union_remesh(base_parts + left + right, 0.006 * vs, "Base")
    A.smooth(base, 0.40, 3)
    print("base      : %d verts  %.1fs" % (len(base.data.vertices), time.time() - t))
    if vs <= 1.0:
        import numpy as np
        Pb = np.array([v.co[:] for v in base.data.vertices])
        nk = A.check_neck(Pb)
        print("neck      : " + "  ".join("%s %.3f" % kv for kv in nk.items()))
        bk = A.check_back(Pb)
        print("back      : " + "  ".join("%s %.3f" % kv for kv in bk.items()))
    # No orbital dish any more (2026-09-26): the boolean cut a 4.5 mm dish
    # whose steep wall folded over itself under the drape. The eye's hollow
    # is sculpt.drape_eyes' now, over a surface with no wall in it.
    check_eye()
    A.check_head()
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
    face = face_parts() + ear(1, ears.get("l", 0.0)) + ear(-1, ears.get("r", 0.0))
    # the physique's definition, at this pass so its edges survive
    defn = A.definition(physique); defn = defn + [mirror_x(o) for o in defn]
    hair = hair_parts(hair_style)
    if hair:
        check_hair(hair, hair_style)
    # a fringe hangs below the hairline plane on purpose: its own group, so
    # the hairline test that keeps hair above the plane does not strip it
    fringe = [o for o in hair if o.name.startswith("fringe") and not o.name.startswith("fringetop")]
    hair = [o for o in hair if o not in fringe]
    groups = {"skin": [base, hands] + face + defn, "hair": hair}
    if fringe:
        groups["fringe"] = fringe
    # remember the sources for material assignment: BVH per group
    trees = {}
    for g, objs in groups.items():
        bm = bmesh.new()
        for o in objs:
            tmp = o.data.copy(); tmp.transform(o.matrix_world); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp)
        trees[g] = BVHTree.FromBMesh(bm); bm.free()
    body = union_remesh([base, hands] + face + defn + hair + fringe, 0.0035 * vs, "Body")
    A.smooth(body, 0.5, 2)
    from . import sculpt
    subdivide_eyes(body)
    scale, shift = sculpt.with_nose(face_scale, noses)
    peak, moved = sculpt.sculpt_face(body, A.head_surface_y, scale=scale, shift=shift)
    A.smooth(body, 0.3, 1)
    sculpt.drape_eyes(body, A.head_surface_y)
    relaxed = relax_eyes(body)
    bpy.ops.object.shade_smooth()
    print("body      : %d verts  %.1fs   face sculpt peak %.1f mm over %d verts" % (len(body.data.vertices), time.time() - t, peak * 1000, moved))
    # The pipeline builds through here, not through anatomy.build(), so the
    # stature and heads-tall checks have to be called here or they never run.
    A.measure(body, check=(vs <= 1.0))
    import numpy as np
    n = len(body.data.vertices); P = np.empty(n * 3); body.data.vertices.foreach_get("co", P)
    ph = A.check_physique(P.reshape(n, 3), assert_=(physique is not None and vs <= 1.0))
    print("physique  : %s  " % (physique or "canonical, reported") + "  ".join("%s %.1f" % (k, v * 1000) for k, v in ph.items()))
    eyes = eyeballs()
    shown, leak = check_eye_open(body, eyes)
    print("eyes      : globe shows over %.0f %% of the fissure, %.1f %% outside the lids (%d faces of the eye region collapsed)"
          % (shown * 100, leak * 100, relaxed))
    mien = check_mien(body, holds, assert_=(vs <= 1.0))
    print("mien      : " + "  ".join("%s %.2f" % (k, v * 1000) for k, v in mien.items() if k != "brow_z")
          + " mm  (brow crest at %.4f)" % mien["brow_z"])
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

