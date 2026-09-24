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
    out = []
    # The deltoid is a teardrop that flows down the arm, not a ball on the
    # shelf. It was neither: sliced perpendicular to the humerus the arm was
    # 0.159 m across at the deltoid and 0.095 m below it, so the cap was 68 %
    # wider than the limb it caps, and it stood 96.5 mm proud of the acromion
    # against a real 35. That is the puffed sleeve -- the trunk had no V, and
    # this was doing the ribcage's job from the outside. Now the trunk is the
    # V (see anatomy.trunk) and this is a muscle again.
    ua, la = Jp("upperarm_l"), Jp("lowerarm_l")
    out.append(ellipsoid("delt", ua + (la - ua) * 0.12 + Vector((-0.006, -0.004, 0.014)), (0.032, 0.036, 0.086), tuple(la - ua)))
    # Sunk into the trunk: only the front third of the pec is proud of the chest.
    out.append(ellipsoid("pec", (0.086, -0.062, 1.356), (0.094, 0.042, 0.062)))
    # The trapezius stopped 35 mm short of the acromion, so nothing drew the
    # neck-to-shoulder diagonal and the trunk loft was left to do it with a
    # step. It has to reach the shoulder.
    out.append(ellipsoid("trap", (0.112, 0.022, 1.492), (0.062, 0.046, 0.066), (0.70, -0.10, -0.30)))
    # Buried 16 mm inside the trunk at every height, so it showed nowhere.
    out.append(ellipsoid("lat", (0.145, 0.048, 1.300), (0.042, 0.046, 0.100)))
    # It was centred on the hip JOINT, so it read as a hip, not a seat.
    out.append(ellipsoid("glute", (0.078, 0.076, 0.918), (0.072, 0.070, 0.064)))
    out.append(ellipsoid("scm", (0.034, -0.032, 1.566), (0.015, 0.015, 0.048), (0.38, -0.58, 1.0)))
    # Nothing at all lived between the ribcage and the pelvis: no oblique,
    # no rectus, so the waist was a smooth taper with no muscle in it.
    out.append(ellipsoid("oblique", (0.094, 0.006, 1.160), (0.040, 0.058, 0.066)))
    out.append(ellipsoid("rectus", (0.032, -0.086, 1.180), (0.038, 0.020, 0.130)))
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
HAIR_STYLES = ("quiff", "crop", "buzz", "fade", "curly", "slick", "part", "fringe", "bald")

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

def hair_shell(d):
    """The skull's rings grown by d, from under the hairline to the crown,
    closed over the top at crown + d, and cut at the hairline: a close cut
    that follows the head exactly d off it all round."""
    rows = [r for r in A.HEAD_ROWS if r[0] >= 1.668]
    rings = [ring_z(z, 0, cy, rx + d, ry + d) for z, cy, rx, ry in rows]
    top = rows[-1]
    rings.append(ring_z(top[0] + d, 0, top[1], 0.010, 0.012))
    shell = loft("hairshell", rings, segs=64)
    return _hairline_cut(shell)

def _hash01(n):
    """The integer hash the level builders place things with (hash01 in
    Tools/levels), so a man's curls come out the same every build."""
    x = n & 0xFFFFFFFF
    x ^= x >> 16; x = (x * 2246822519) & 0xFFFFFFFF
    x ^= x >> 13; x = (x * 3266489917) & 0xFFFFFFFF
    x ^= x >> 16
    return (x & 0xFFFFFF) / 16777215.0

def _curls(d, r=0.0060, spacing=0.0085, zmin=1.745):
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
        rx = r0[2] + (r1[2] - r0[2]) * t + d; ry = r0[3] + (r1[3] - r0[3]) * t + d
        per = max(1, int(2 * math.pi * math.sqrt(0.5 * (rx * rx + ry * ry)) / spacing))
        for i in range(per):
            h = [_hash01(k * 7919 + i * 104729 + j * 31) for j in range(4)]
            a = 2 * math.pi * (i + 0.5 * (k % 2) + (h[0] - 0.5) * 0.7) / per
            zz = z + (h[1] - 0.5) * spacing * 0.6
            rr = r * (0.75 + 0.5 * h[2])
            c = Vector((rx * math.cos(a), cy + ry * math.sin(a), zz))
            n = Vector((math.cos(a) / rx, math.sin(a) / ry, 0.0)).normalized()
            c = c + n * (rr * (0.15 + 0.35 * h[3]))
            if not above_hairline(c, 0.004):
                continue
            c.z = min(c.z, 1.800 - rr)
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
        return [hair_shell(0.0040)] + _curls(0.0040)
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
        # a textured top pushed forward, and a fringe over the forehead. The
        # fringe hangs below the hairline plane, so it goes to the body as
        # its own source group (assign_by_source keeps it hair).
        # One sheet from the crown forward and down over the brow, not a
        # separate roll laid on the forehead: the fringe overlaps the top
        # by half its height, so the union makes them one mass.
        fy = A.head_surface_y(0.0, 1.760) + 0.0035
        return [hair_shell(0.0040),
                ellipsoid("fringetop", (0, -0.016, 1.7710), (0.0620, 0.0780, 0.0220), (0, -0.20, 1.0),
                          segs=48, rings=28),
                ellipsoid("fringe", (0, fy, 1.7625), (0.0580, 0.0130, 0.0150), (0, -0.40, 1.0),
                          segs=40, rings=24)]
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
    if style != "quiff":
        return [cap]
    crown = ellipsoid("crownhair", (0, -0.004, 1.7680), (0.0680, 0.0800, 0.0260),
                      (0, -0.14, 1.0), segs=48, rings=32)
    return [cap, crown]

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

