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

def hair_parts(style="quiff"):
    """A cap over the skull cut at the hairline, and hair over the crown.

    `style`: "quiff" is Saud's -- the cap and some length left on top
    (assets/saud.js: `quiff: true`). "crop" is the cap alone, a close cut,
    for a man the roster gives a hair colour and nothing else.
    """
    # The skull crown is at 1.796 and the chin at 1.570: 0.226 m a head, and
    # 8.04 heads tall, which is the figure the art direction asks for. But
    # the cap used to top out at 1.806 and the quiff at 1.814, so the head a
    # player SEES was 0.248 m and he read as 7.33 heads. The whole deficit
    # was hair. Nothing here may stand above 1.800.
    # Solved, not guessed: the smallest ellipsoid that clears the skull by
    # 2.4 to 11.4 mm everywhere above the hairline AND tops out at exactly
    # 1.800. The previous shapes either topped out at 1.806-1.814 -- which is
    # the whole heads-tall deficit, see the note above -- or sank INSIDE the
    # occiput, where the skull bulges further back than a cap centred over
    # the crown can follow, so the hair vanished at the back of his head.
    cap = ellipsoid("haircap", (0, 0.002, 1.7275), (0.0880, 0.1240, 0.0725), segs=64, rings=40)
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

def build(voxel_scale=1.0, face_scale=None, hair_style="quiff"):
    """voxel_scale > 1 is a coarse, quick body for checking the stages after
    this one. `face_scale` and `hair_style` are one man's differences from
    another on the same skull -- see sculpt.sculpt_face and hair_parts."""
    vs = voxel_scale
    t = time.time()
    legacy.reset_scene()
    # ---- pass one: the base at 6 mm, smoothed hard
    base_parts = [A.trunk(), A.neck(), A.head()]
    left = A.arm() + A.leg() + [A.shoe()] + masses()
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
    hands = union_remesh(hl + hr, 0.0025 * vs, "Hands"); A.smooth(hands, 0.5, 3)
    face = face_parts() + ear(1) + ear(-1)
    hair = hair_parts(hair_style)
    groups = {"skin": [base, hands] + face, "hair": hair}
    # remember the sources for material assignment: BVH per group
    trees = {}
    for g, objs in groups.items():
        bm = bmesh.new()
        for o in objs:
            tmp = o.data.copy(); tmp.transform(o.matrix_world); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp)
        trees[g] = BVHTree.FromBMesh(bm); bm.free()
    body = union_remesh([base, hands] + face + hair, 0.0035 * vs, "Body")
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

def above_hairline(c):
    t = (c.y + 0.09) / 0.18
    return c.z > HAIRLINE[0] + (HAIRLINE[1] - HAIRLINE[0]) * t

def assign_by_source(body, trees, slots):
    """Each face takes the material of the nearest source part group. Hair
    is the exception: nearest-source frays along the cap's cut edge, so the
    hairline is the plane the cap was cut with, tested on the face centre."""
    for poly in body.data.polygons:
        c = poly.center
        best, bestd = "skin", 1e9
        for g, tree in trees.items():
            hit = tree.find_nearest(c)
            if hit and hit[3] < bestd: best, bestd = g, hit[3]
        if best == "hair" and not above_hairline(c): best = "skin"
        if best == "skin" and "hair" in slots and above_hairline(c) and c.z > 1.70 and trees["hair"].find_nearest(c)[3] < 0.004: best = "hair"
        poly.material_index = slots[best]

