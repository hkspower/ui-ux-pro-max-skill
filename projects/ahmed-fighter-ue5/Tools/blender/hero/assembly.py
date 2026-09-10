"""The assembly: a two-pass body. The base (trunk, limbs, masses) at 6 mm and
smoothed hard; the parts that need their edges -- hands, face, ears, hair
-- at fine voxel, unioned in a second 3.5 mm pass that blends the joins
without eating the detail. Materials come back by nearest source part."""
import bpy, bmesh, math, sys, os, time
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import build_ahmed as legacy
from . import anatomy as A
J = legacy.J; Jp = A.Jp; X, Y, Z = A.X, A.Y, A.Z
ellipsoid, loft, tube, ring_z, mirror_x = A.ellipsoid, A.loft, A.tube, A.ring_z, A.mirror_x

def masses():
    out = []
    # The deltoid is a teardrop that flows down the arm, not a ball on the
    # shelf: its long axis is the humerus, and it is narrower than the arm's
    # own top section so the smoothing blends it in rather than rounding it.
    ua, la = Jp("upperarm_l"), Jp("lowerarm_l")
    out.append(ellipsoid("delt", ua + (la - ua) * 0.16 + Vector((0.012, -0.004, 0.030)), (0.040, 0.044, 0.078), tuple(la - ua)))
    # Sunk into the trunk: only the front third of the pec is proud of the chest.
    out.append(ellipsoid("pec", (0.082, -0.060, 1.368), (0.092, 0.042, 0.066)))
    out.append(ellipsoid("trap", (0.096, 0.024, 1.488), (0.044, 0.044, 0.070), (0.62, -0.10, -0.32)))
    out.append(ellipsoid("lat", (0.104, 0.046, 1.300), (0.052, 0.056, 0.110)))
    out.append(ellipsoid("glute", (0.078, 0.078, 0.962), (0.068, 0.072, 0.082)))
    out.append(ellipsoid("scm", (0.030, -0.030, 1.560), (0.014, 0.014, 0.045), (0.35, -0.55, 1.0)))
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
    """Helix as a flattened ring, lobe below, a dish cut into the front."""
    c = Vector((0.079 * s, 0.002, 1.668))
    bpy.ops.mesh.primitive_torus_add(location=c, major_radius=0.016, minor_radius=0.0065, major_segments=24, minor_segments=12)
    helix = bpy.context.object; helix.name = "helix"
    helix.scale = (1.0, 0.75, 1.25); helix.rotation_euler = (0, math.radians(90), 0)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    lobe = ellipsoid("lobe", c + Vector((0.002 * s, -0.002, -0.020)), (0.006, 0.010, 0.008))
    back = ellipsoid("earback", c + Vector((-0.003 * s, 0.004, 0)), (0.005, 0.014, 0.020))
    return [helix, lobe, back]

def eyeballs():
    out = []
    for s in (1, -1):
        e = ellipsoid("eyeball", (0.031 * s, A.head_surface_y(0.031 * s, 1.666) + 0.0170, 1.666), (0.0110, 0.0110, 0.0110))
        out.append(e)
    return out

def hair_parts():
    """A cap over the skull cut at the hairline, and the quiff on top."""
    cap = ellipsoid("haircap", (0, 0.004, 1.708), (0.085, 0.104, 0.098), segs=64, rings=40)
    # Everything below the hairline plane goes. The plane passes through
    # z 1.738 at the brow (y -0.09) and 1.695 at the nape (y +0.09): the
    # box's top face is that plane, so its centre sits half a box below.
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0.0, 1.7165 - 0.25))
    cut = bpy.context.object; cut.scale = (0.5, 0.6, 0.5)
    cut.rotation_euler = (math.radians(-13.4), 0, 0)     # front edge up
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    boolean(cap, cut, 'DIFFERENCE')
    quiff = ellipsoid("quiff", (0, -0.046, 1.786), (0.050, 0.054, 0.028), (0, -0.40, 1.0), segs=48, rings=32)
    return [cap, quiff]

def union_remesh(parts, voxel, name):
    return A.union_remesh(parts, voxel, name)

def build(voxel_scale=1.0):
    """voxel_scale > 1 is a coarse, quick body for checking the stages after this one."""
    vs = voxel_scale
    t = time.time()
    legacy.reset_scene()
    # ---- pass one: the base at 6 mm, smoothed hard
    base_parts = [A.trunk(), A.neck(), A.head()]
    left = A.arm() + A.leg() + [A.shoe()] + masses()
    right = [mirror_x(o) for o in left]
    base = union_remesh(base_parts + left + right, 0.006 * vs, "Base")
    A.smooth(base, 0.7, 8)
    print("base      : %d verts  %.1fs" % (len(base.data.vertices), time.time() - t))
    # eye sockets into the smoothed base, so the lids have somewhere to sit
    for s in (1, -1):
        sock = ellipsoid("socket", (0.031 * s, A.head_surface_y(0.031 * s, 1.666) + 0.010, 1.666), (0.019, 0.016, 0.013))
        boolean(base, sock, 'DIFFERENCE')
    # ---- pass two: fine parts, then one remesh at 3.5 mm to blend the joins
    hl, jl = A.hand(); hr = [mirror_x(o) for o in hl]
    hands = union_remesh(hl + hr, 0.0025 * vs, "Hands"); A.smooth(hands, 0.5, 3)
    face = face_parts() + ear(1) + ear(-1)
    hair = hair_parts()
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
    peak, moved = sculpt.sculpt_face(body, A.head_surface_y)
    A.smooth(body, 0.3, 1)
    bpy.ops.object.shade_smooth()
    print("body      : %d verts  %.1fs   face sculpt peak %.1f mm over %d verts" % (len(body.data.vertices), time.time() - t, peak * 1000, moved))
    eyes = eyeballs()
    return body, trees, eyes, jl

HAIRLINE = (1.738, 1.695)     # z at the brow (y -0.09) and at the nape (y +0.09)
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

