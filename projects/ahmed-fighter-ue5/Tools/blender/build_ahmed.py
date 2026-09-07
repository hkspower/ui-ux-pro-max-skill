"""
Builds Ahmed as a rigged 3D character and exports him for Unreal Engine 5.

Run headless with no Blender install required:

    pip install bpy
    python3 build_ahmed.py

The body is grown from a joint skeleton with Blender's Skin modifier, which is
the same construction the browser build uses on canvas -- there, `tube()` and
`capsule()` draw the fighter as lit cylinders between the same joints. Keeping
one joint table for both means the 3D Ahmed and the 2D Ahmed stay the same man.

The rest pose is a standard A-pose and the bones carry Unreal mannequin names
(`pelvis`, `upperarm_l`, `thigh_r`, ...), so the mesh retargets onto UE5's
mannequin animations without a bone-mapping pass.
"""

import math
import os
import sys

import bpy
import bmesh
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_MODELS = os.path.abspath(os.path.join(HERE, "..", "..", "Content", "Models"))
OUT_RENDER = os.path.abspath(os.path.join(HERE, "..", "..", "Docs", "renders"))
# The Unity port is a sibling project and this is the game's only mesh
# generator, so it writes there too rather than the model being copied by hand
# and drifting. See export_unity() for why it cannot be the same file. It goes
# under Resources because that port has no authored scene -- Bootstrap builds
# everything at runtime, and Resources is the only place it can load a model
# from without an editor.
OUT_UNITY = os.path.abspath(os.path.join(
    HERE, "..", "..", "..", "ahmed-fighter-unity",
    "Assets", "Resources", "Models"))

# Ahmed stands 1.80 m. Unreal works in centimetres, so both exporters below
# scale by 100 on the way out.
HEIGHT = 1.80

# --------------------------------------------------------------- palette
# Straight from the browser build's `col` table so the two Ahmeds match.
# Linear values, matching the browser build's `col` table for Ahmed.
PALETTE = {
    "skin":   (0.888, 0.716, 0.597, 1.0),   # #f0d8c4  fair
    "tee":    (0.029, 0.031, 0.039, 1.0),   # #15171c  fitted black tee
    "pants":  (0.020, 0.021, 0.027, 1.0),   # #0e1014  black trousers
    "shoe":   (0.032, 0.034, 0.040, 1.0),   # trainers, a touch off the trousers
    "band":   (0.608, 0.008, 0.043, 1.0),   # #c8102e  Kuwait red
    "hair":   (0.020, 0.014, 0.009, 1.0),   # #1e150f
    "beard":  (0.026, 0.018, 0.012, 1.0),   # a shade off the hair
    "eye":    (0.012, 0.010, 0.009, 1.0),
}

# ---------------------------------------------------------------- joints
# name -> (position, parent, skin radius). One table, used for both the
# skinned body mesh and the armature.
#
# The heights are skeletal landmarks as fractions of stature, not guesses:
# hip joint 0.530 H, knee 0.285 H, ankle 0.039 H, acromion 0.812 H; upper arm
# 0.186 H, forearm 0.146 H, thigh 0.245 H, shank 0.246 H (Winter, *Biomechanics
# and Motor Control of Human Movement*). At H = 1.80 that puts the crown at
# 1.79 and the chin near 1.57, which is the eight-heads figure this project's
# art direction asks for.
#
# **Ahmed faces -Y.** Everything that gives him a front -- the toes, the face,
# the hair parting, the guard's chin tuck -- points that way, and Blender's
# FBX default (forward -Z, up Y) lands it on Unreal's +X.
J = {
    "pelvis":     (Vector((0.00,  0.000, 0.952)), None,       0.118),
    "spine_01":   (Vector((0.00,  0.000, 1.108)), "pelvis",   0.106),
    "spine_02":   (Vector((0.00,  0.000, 1.264)), "spine_01", 0.124),
    "spine_03":   (Vector((0.00,  0.000, 1.440)), "spine_02", 0.146),
    "neck_01":    (Vector((0.00,  0.000, 1.520)), "spine_03", 0.062),
    # The jaw is a shaping joint, not a bone. Without it the skull's front
    # overhangs the neck by four centimetres with nothing in between, which
    # reads as a shelf under the chin rather than a face.
    "jaw":        (Vector((0.00, -0.030, 1.590)), "neck_01",  0.078),
    "head":       (Vector((0.00, -0.014, 1.672)), "jaw",      0.092),
    "head_end":   (Vector((0.00, -0.006, 1.796)), "head",     0.040),
}

_LIMB = [
    # (base name, position, parent, radius)
    # Arms hang at 45 degrees, the A-pose UE5's mannequin animations retarget
    # from. The elbow sits where a real one does: the upper arm is the longer
    # of the two segments, 0.335 against the forearm's 0.263.
    #
    # `biceps` and `forearm` are shaping joints. A limb drawn as two straight
    # tapers between three joints is a tube, and a tube is what makes a
    # blockout look like a blockout however good its proportions are. Real
    # limbs have a belly and a joint: wide through the muscle, narrow across
    # the elbow, wide again below it, narrow at the wrist.
    ("clavicle",  Vector((0.046, -0.012, 1.448)),  "spine_03",   0.100),
    ("upperarm",  Vector((0.178, -0.006, 1.442)),  "clavicle",   0.055),
    ("biceps",    Vector((0.285, -0.003, 1.335)),  "upperarm",   0.060),
    ("lowerarm",  Vector((0.415,  0.000, 1.205)),  "biceps",     0.043),
    ("forearm",   Vector((0.471,  0.000, 1.149)),  "lowerarm",   0.053),
    ("hand",      Vector((0.601,  0.000, 1.019)),  "forearm",    0.032),
    ("hand_end",  Vector((0.654,  0.000, 0.966)),  "hand",       0.042),
    # Legs taper inward from hip to ankle, the way a person's do. They used to
    # splay -- ankles wider apart than hips -- which reads as bow-legged from
    # the front and is the first thing wrong with a blockout's stance.
    ("thigh",     Vector((0.092,  0.000, 0.952)),  "pelvis",     0.100),
    ("quad",      Vector((0.090,  0.000, 0.776)),  "thigh",      0.090),
    ("calf",      Vector((0.088,  0.000, 0.513)),  "quad",       0.060),
    ("calf_belly",Vector((0.087,  0.000, 0.402)),  "calf",       0.066),
    ("foot",      Vector((0.082,  0.000, 0.070)),  "calf_belly", 0.038),
    # A foot is a heel, an arch and toes. It was an ankle and a stub, which is
    # why he stood on two ellipses a third short of a foot's length.
    ("heel",      Vector((0.082,  0.056, 0.038)),  "foot",       0.038),
    ("ball",      Vector((0.082, -0.156, 0.0243)), "foot",       0.034),
    ("toe",       Vector((0.082, -0.212, 0.021)),  "ball",       0.024),
]

for _name, _pos, _parent, _r in _LIMB:
    for _side, _sign in (("l", 1.0), ("r", -1.0)):
        _p = Vector((_pos.x * _sign, _pos.y, _pos.z))
        _par = _parent if _parent in J else "{}_{}".format(_parent, _side)
        J["{}_{}".format(_name, _side)] = (_p, _par, _r)

ORDER = list(J.keys())

# Joints that shape the mesh but are not bones.
#
# The skeleton has to stay exactly the UE5 mannequin's or the retarget that
# makes this model useful stops working -- so anatomy the mannequin has no
# bone for goes here instead. `build_armature` skips these and parents
# through them, which is why a bulge in the middle of the upper arm does not
# become a bone in the middle of the upper arm.
_SHAPE_BASES = ("biceps", "forearm", "quad", "calf_belly", "heel", "toe")
SHAPE = {"jaw"} | {"{}_{}".format(b, s) for b in _SHAPE_BASES for s in ("l", "r")}


def skeletal_parent(name):
    """The nearest ancestor of a joint that is a real bone."""
    parent = J[name][1]
    while parent is not None and parent in SHAPE:
        parent = J[parent][1]
    return parent


# ===================================================================== setup

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"


def make_material(name, rgba, roughness=0.62, sheen=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = roughness
    if "Sheen Weight" in bsdf.inputs:
        bsdf.inputs["Sheen Weight"].default_value = sheen
    return mat


# ====================================================================== body

def build_body():
    """Grows the body mesh out of the joint graph with a Skin modifier."""
    index = {name: i for i, name in enumerate(ORDER)}
    verts = [J[name][0] for name in ORDER]
    edges = [
        (index[name], index[J[name][1]])
        for name in ORDER
        if J[name][1] is not None
    ]

    mesh = bpy.data.meshes.new("AhmedBody")
    mesh.from_pydata([tuple(v) for v in verts], edges, [])
    mesh.update()

    obj = bpy.data.objects.new("Ahmed", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    skin = obj.modifiers.new("Skin", "SKIN")
    skin.use_smooth_shade = True
    skin.branch_smoothing = 0.60

    layer = mesh.skin_vertices[0].data
    for name in ORDER:
        i = index[name]
        r = J[name][2]
        layer[i].radius = (r, r)
    layer[index["pelvis"]].use_root = True

    # Nothing on a person has a round cross-section. The torso is a flattened
    # oval, the head is an egg, the jaw is wider than it is deep, and a limb
    # is slightly flattened front to back. Left round, the ribcage came out
    # 0.134 m deep against a person's 0.225 -- a plank with arms.
    for name, (rx, ry) in {
        "pelvis":     (0.170, 0.140),   # hips carry the width low
        "spine_01":   (0.150, 0.128),   # waist: the narrow of the V-taper
        "spine_02":   (0.196, 0.164),   # ribcage, the deepest part of him
        "spine_03":   (0.228, 0.168),   # the shoulder shelf
        "clavicle":   (0.112, 0.124),   # deltoid, not a coat hanger
        "neck_01":    (0.062, 0.070),   # necks are deeper than they are wide
        "jaw":        (0.078, 0.090),
        "head":       (0.087, 0.107),
        "biceps":     (0.060, 0.056),
        "forearm":    (0.053, 0.048),
        "hand_end":   (0.042, 0.034),   # a fist is a slab, not a ball
        "quad":       (0.090, 0.086),
        "calf_belly": (0.066, 0.060),
        "heel":       (0.036, 0.042),
        "ball":       (0.038, 0.030),
        "toe":        (0.026, 0.020),
    }.items():
        # A bare limb name means both sides.
        targets = [name] if name in index else [name + "_l", name + "_r"]
        for target in targets:
            layer[index[target]].radius = (rx, ry)

    sub = obj.modifiers.new("Subdivision", "SUBSURF")
    sub.levels = 2
    sub.render_levels = 2

    bpy.ops.object.modifier_apply(modifier="Skin")
    return obj


def subdivide(obj):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier="Subdivision")
    bpy.ops.object.shade_smooth()


def add_material_slots(obj):
    """Five slots plus a beard, in a fixed order the two passes index into."""
    mats = [
        ("skin",   make_material("Ahmed_Skin", PALETTE["skin"], 0.58)),
        ("tee",    make_material("Ahmed_Tee", PALETTE["tee"], 0.72, sheen=0.30)),
        ("pants",  make_material("Ahmed_Pants", PALETTE["pants"], 0.78, sheen=0.18)),
        ("shoe",   make_material("Ahmed_Shoe", PALETTE["shoe"], 0.46)),
        ("band",   make_material("Ahmed_Band", PALETTE["band"], 0.66)),
        ("hair",   make_material("Ahmed_Hair", PALETTE["hair"], 0.42)),
        ("beard",  make_material("Ahmed_Beard", PALETTE["beard"], 0.50)),
        ("eye",    make_material("Ahmed_Eye", PALETTE["eye"], 0.18)),
    ]
    for _, mat in mats:
        obj.data.materials.append(mat)
    return {key: i for i, (key, _) in enumerate(mats)}


def assign_kit(obj, idx):
    """Kit, painted before subdivision so every seam lands on an edge loop.

    Seams on a limb are measured as distance from the joint they hang off,
    not as a box in x and z. A box cuts a 45-degree arm diagonally, which is
    where the notch in the old sleeve came from; a distance cuts it square
    however the arm is posed.
    """
    shoulder = J["upperarm_l"][0]
    waist_z = 1.082
    for poly in obj.data.polygons:
        c = poly.center
        z, ax = c.z, abs(c.x)
        # Distance from whichever shoulder is on this side, and from the
        # neck's own axis -- the second is the collar. A tee covers the
        # trapezius right up to the neck; cutting it on height alone left a
        # bare patch of shoulder on each side of his collar.
        from_shoulder = (c - Vector((math.copysign(shoulder.x, c.x),
                                     shoulder.y, shoulder.z))).length
        from_neck = math.hypot(c.x, c.y)

        if ax < 0.24 and z < 0.118:                    # trainers
            poly.material_index = idx["shoe"]
        elif ax < 0.24 and z <= waist_z:               # long trousers
            poly.material_index = idx["pants"]
        elif waist_z < z <= 1.552 and ax < 0.26 and from_neck > 0.058:
            poly.material_index = idx["tee"]           # tee body and collar
        elif from_shoulder < 0.175 and ax >= 0.13:     # fitted short sleeve
            poly.material_index = idx["tee"]
        else:
            poly.material_index = idx["skin"]


def assign_detail(obj, idx):
    """Trouser stripe, hair and beard -- after subdivision, where polys are fine.

    The waistband is *not* here. It is geometry, added by `add_waistband`,
    because no face selection can draw a clean belt at that height: the legs
    branch off the pelvis right there, so the Skin modifier leaves almost no
    vertices between z 0.99 and 1.05 and the polygons that do cross it are
    ten centimetres tall. Painting them gave a ragged red block; painting
    only the ones whose centre landed inside gave a zigzag of diamonds.
    """
    head = J["head"][0]
    leg_seam = min(J["thigh_l"][0].x, J["calf_l"][0].x)

    for poly in obj.data.polygons:
        c = poly.center

        # Sportswear stripe down the outer seam of each trouser leg: only the
        # faces that look straight out to the side, so it stays a narrow line.
        # The width test comes off the joint table rather than being a number
        # typed here -- the outer face of a leg is always further out than its
        # joint and the inner face always closer, whatever the legs measure,
        # so re-proportioning him cannot quietly delete the stripe.
        if (poly.material_index == idx["pants"] and 0.13 < c.z < 1.02
                and abs(poly.normal.x) > 0.965 and abs(c.x) > leg_seam):
            poly.material_index = idx["band"]
            continue
        if c.z < head.z - 0.105:
            continue
        # Ahmed faces -Y: the face is at -y, the back of the skull at +y.
        d = c - head
        cheek = min(1.0, abs(d.x) / 0.072)

        # Where these two sit is the whole difference between a face and a
        # mask. The head runs chin 1.575 to crown 1.806, and the thirds fall
        # nose base / brow / hairline -- so the hairline belongs ABOVE the
        # brow. It was 15 mm below it, which is why the hair came down over
        # his eyes like a helmet and left a slot for a bandit mask.
        # Neither edge is straight, either: a hairline is lower in the middle
        # than at the temples, a beard runs the other way, up to the sideburn.
        hair_z = head.z + 0.066 + 0.020 * cheek
        beard_z = head.z - 0.032 + 0.050 * cheek

        if c.z > hair_z or d.y > 0.050:                # crown and back
            poly.material_index = idx["hair"]
        elif c.z < beard_z and d.y < 0.020:            # jaw, chin, sideburns
            poly.material_index = idx["beard"]


def add_waistband(obj, idx, z_centre=1.062, height=0.026):
    """The waistband, as a ring of geometry hugging the body.

    Sized from the mesh it is going onto rather than from a number typed
    here, so it stays a belt if he is ever re-proportioned.
    """
    # Torso only. In the A-pose the hands hang to just below the waist, so a
    # scan on height alone measures the arm span and produces a red rod
    # through the body and out the wrists.
    near = [v.co for v in obj.data.vertices
            if abs(v.co.z - z_centre) < 0.045 and abs(v.co.x) < 0.30]
    if not near:
        return
    hx = max(abs(v.x) for v in near)
    hy = max(abs(v.y) for v in near)

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=32, radius=1.0, depth=height, location=(0.0, 0.0, z_centre))
    band = bpy.context.object
    band.scale = (hx + 0.003, hy + 0.003, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.shade_smooth()
    _join_into(obj, band, obj.data.materials[idx["band"]])


def _join_into(obj, part, material):
    """Give a part the body's own material datablock, then merge it in."""
    part.data.materials.append(material)
    for poly in part.data.polygons:
        poly.material_index = 0
    bpy.ops.object.select_all(action="DESELECT")
    part.select_set(True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.join()


def add_hair(obj, idx):
    """Grows hair off the skull's own faces rather than dropping a ball on it.

    A separate sphere has to be guessed into place and, guessed slightly wrong,
    swallows the face. Duplicating the scalp polygons and pushing them out
    along their normals cannot: the hair covers exactly the faces selected and
    hugs the head by construction. The extra push toward the front-top gives
    the swept quiff the 2D Ahmed wears.
    """
    head = J["head"][0]
    thickness, quiff_lift = 0.013, 0.026

    mesh = bmesh.new()
    mesh.from_mesh(obj.data)
    mesh.faces.ensure_lookup_table()

    scalp = []
    for face in mesh.faces:
        d = face.calc_center_median() - head
        if d.z < -0.075:                       # below the jaw is not head at all
            continue
        # A hairline, not a helmet: high across the brow, low around the back.
        # The same hairline `assign_detail` paints, so the geometry and the
        # colour agree -- otherwise the hair grows off one edge and is
        # coloured to another, and the join shows as a rim of dark skin.
        cheek = min(1.0, abs(d.x) / 0.072)
        limit = (0.066 + 0.020 * cheek) if d.y < 0.015 else -0.030
        if d.z > limit:
            scalp.append(face)

    if not scalp:
        mesh.free()
        return

    dup = bmesh.ops.duplicate(mesh, geom=scalp)
    new_faces = [g for g in dup["geom"] if isinstance(g, bmesh.types.BMFace)]
    new_verts = [g for g in dup["geom"] if isinstance(g, bmesh.types.BMVert)]

    for vert in new_verts:
        d = vert.co - head
        lift = 0.0
        if d.y < 0.0 and d.z > 0.030:          # front of the crown: the quiff
            lift = quiff_lift * min(1.0, -d.y / 0.055) * min(1.0, (d.z - 0.030) / 0.045)
        vert.co += vert.normal * (thickness + lift)

    for face in new_faces:
        face.material_index = idx["hair"]
        face.smooth = True

    mesh.to_mesh(obj.data)
    mesh.free()
    obj.data.update()


def add_face(obj, idx):
    """A nose and two brows.

    A head with eyes and nothing else does not read as a face -- it reads as
    a mask. These are the two features that carry the most for the least: the
    nose gives the profile a centre line, and the brows give the eyes a top
    edge, which is most of what makes a face look like it is looking at you.
    Both are crude on purpose; this is a blockout, not a hero head.
    """
    head = J["head"][0]

    # Nose: a wedge set into the face at the nose-base third, tall and narrow
    # rather than a ball. Big enough to catch the light down one side, small
    # enough not to read as a snout.
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=0.016, segments=14, ring_count=10,
        location=(head.x, head.y - 0.080, head.z - 0.026),
    )
    nose = bpy.context.object
    nose.scale = (0.62, 1.20, 1.15)
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.shade_smooth()
    _join_into(obj, nose, obj.data.materials[idx["skin"]])

    # Brows: flattened bars on the brow third, in the hair colour.
    for sign in (1, -1):
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=0.017, segments=12, ring_count=8,
            location=(head.x + 0.032 * sign, head.y - 0.086, head.z + 0.016),
        )
        brow = bpy.context.object
        brow.scale = (1.50, 0.40, 0.30)
        bpy.ops.object.transform_apply(scale=True)
        bpy.ops.object.shade_smooth()
        _join_into(obj, brow, obj.data.materials[idx["hair"]])


def add_eyes(obj, idx):
    """Two spheres set into the skull -- enough for the head to read as a face."""
    head = J["head"][0]
    for sign in (1, -1):
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=0.0145, segments=14, ring_count=10,
            location=(head.x + 0.032 * sign, head.y - 0.086, head.z - 0.006),
        )
        eye = bpy.context.object
        eye.scale = (1.0, 0.72, 1.0)
        bpy.ops.object.transform_apply(scale=True)
        bpy.ops.object.shade_smooth()
        # Share the body's material datablock so the join merges the slots
        # instead of leaving an empty one behind.
        _join_into(obj, eye, obj.data.materials[idx["eye"]])


# ==================================================================== rigging

def build_armature():
    arm_data = bpy.data.armatures.new("AhmedSkeleton")
    arm = bpy.data.objects.new("Ahmed_Rig", arm_data)
    bpy.context.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")

    made = {}
    # `*_end` joints only give the last real bone somewhere to point, and
    # SHAPE joints are mesh, not skeleton -- neither becomes a bone, and a
    # bone never points its tail at one. Miss the second half and the upper
    # arm bone ends at the biceps instead of the elbow.
    for name in ORDER:
        if name.endswith("_end") or name in SHAPE:
            continue
        pos = J[name][0]

        children = [n for n in ORDER
                    if n not in SHAPE and skeletal_parent(n) == name]
        if children:
            tail = J[children[0]][0]
        else:
            tail = pos + Vector((0, 0, 0.06))

        bone = arm_data.edit_bones.new(name)
        bone.head = pos
        bone.tail = tail
        made[name] = bone

    for name, bone in made.items():
        parent = J[name][1]
        while parent is not None and parent not in made:
            parent = J[parent][1]
        if parent:
            bone.parent = made[parent]
            bone.use_connect = (bone.head - made[parent].tail).length < 1e-5

    bpy.ops.object.mode_set(mode="OBJECT")
    return arm


def bind(mesh_obj, arm_obj):
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    try:
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    except RuntimeError:
        # Bone heat weighting gives up on awkward topology; envelopes are
        # coarser but always solve, and UE can re-skin from there.
        bpy.ops.object.parent_set(type="ARMATURE_ENVELOPE")
    bpy.ops.object.select_all(action="DESELECT")
    weight_orphans(mesh_obj, arm_obj)


def weight_orphans(mesh_obj, arm_obj):
    """Bone heat skips disconnected islands -- the eyes come out unweighted.

    Left alone they would sit still while the head turns, and the glTF
    exporter would invent a `neutral_bone` to hang them off. Give every
    orphan the nearest bone at full weight instead.
    """
    groups = {g.name: g for g in mesh_obj.vertex_groups}
    bones = [b for b in arm_obj.data.bones if b.name in groups]
    if not bones:
        return

    orphans = 0
    for vert in mesh_obj.data.vertices:
        if any(g.weight > 0.0 for g in vert.groups):
            continue
        nearest = min(
            bones,
            key=lambda b: _point_to_segment(vert.co, b.head_local, b.tail_local),
        )
        groups[nearest.name].add([vert.index], 1.0, "REPLACE")
        orphans += 1
    if orphans:
        print("re-weighted {} orphan verts".format(orphans))


def _point_to_segment(point, a, b):
    ab = b - a
    length_sq = ab.length_squared
    if length_sq == 0.0:
        return (point - a).length
    t = max(0.0, min(1.0, (point - a).dot(ab) / length_sq))
    return (point - (a + ab * t)).length


# ====================================================================== poses

def _hierarchy_order(arm_obj):
    """Parents before children, so a posed parent carries its chain with it."""
    out, seen = [], set()

    def walk(bone):
        if bone.name in seen:
            return
        seen.add(bone.name)
        out.append(bone.name)
        for child in bone.children:
            walk(child)

    for bone in arm_obj.data.bones:
        if bone.parent is None:
            walk(bone)
    return out


def pose(arm_obj, directions):
    """A pose is where each limb points, in world space -- not Euler angles.

    Aiming bones is how you would describe a stance out loud ("lead hand up by
    the chin, rear leg back"), and unlike per-bone Euler triples it does not
    silently mirror wrong: the left and right sides take the same numbers with
    x negated, and both land where they should.
    """
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="POSE")

    for bone in arm_obj.pose.bones:
        bone.rotation_mode = "QUATERNION"
        bone.rotation_quaternion = (1, 0, 0, 0)
        bone.location = (0, 0, 0)
    bpy.context.view_layer.update()

    for name in _hierarchy_order(arm_obj):
        if name not in directions:
            continue
        pbone = arm_obj.pose.bones[name]
        aim = Vector(directions[name]).normalized()
        matrix = aim.to_track_quat("Y", "Z").to_matrix().to_4x4()
        matrix.translation = pbone.matrix.translation
        pbone.matrix = matrix
        bpy.context.view_layer.update()

    bpy.ops.object.mode_set(mode="OBJECT")


def _mirror(spec):
    """Same numbers, x negated -- the other side of the same stance."""
    out = {}
    for name, (x, y, z) in spec.items():
        out["{}_l".format(name)] = (x, y, z)
        out["{}_r".format(name)] = (-x, y, z)
    return out


# Ahmed faces -Y. Both stances are written as one side plus its mirror, then
# the asymmetry that makes it a fighting stance is layered on top.
GUARD = dict(
    _mirror({
        "upperarm": (0.16, -0.10, -0.98),   # elbows down, tight to the ribs
        "lowerarm": (-0.20, -0.26, 0.94),   # forearms up, fists to the chin
        "hand":     (-0.14, -0.20, 0.97),
        "thigh":    (0.16, 0.00, -0.98),
        "calf":     (0.02, 0.00, -1.00),
        "foot":     (0.05, -0.90, -0.42),
    }),
    spine_01=(0, -0.06, 1.0), spine_02=(0, -0.10, 1.0), spine_03=(0, -0.05, 1.0),
    # Chin tucked down and forward behind the guard, not lifted for it.
    neck_01=(0, -0.10, 1.0), head=(0, -0.06, 1.0),
)
# Bladed stance: lead leg forward, rear leg loaded.
GUARD.update({
    "thigh_l": (0.20, -0.42, -0.89), "calf_l": (0.02, -0.06, -1.0),
    "thigh_r": (-0.20, 0.34, -0.92), "calf_r": (-0.02, -0.12, -0.99),
})

# Right round kick, thrown across the body toward the camera's left.
KICK = dict(
    GUARD,
    thigh_r=(0.42, -0.86, 0.30),
    calf_r=(0.88, -0.44, 0.22),
    foot_r=(0.94, -0.30, 0.14),
    thigh_l=(-0.06, 0.10, -0.99),
    calf_l=(0.00, -0.04, -1.00),
    foot_l=(0.10, -0.86, -0.50),
    upperarm_r=(-0.46, 0.44, -0.77),      # rear arm swings back to counter
    lowerarm_r=(-0.66, 0.24, -0.71),
    upperarm_l=(0.30, -0.34, -0.89),      # lead hand stays up
    lowerarm_l=(-0.12, -0.34, 0.93),
    spine_02=(0.22, -0.10, 0.97),
    spine_03=(0.14, -0.06, 0.99),
    head=(-0.10, -0.30, 0.95),
)


# ==================================================================== staging

def build_studio():
    """Three-point rig matching the game's key light, over a dark floor."""
    world = bpy.data.worlds.new("AhmedWorld")
    bpy.context.scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.016, 0.019, 0.031, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.35

    bpy.ops.mesh.primitive_plane_add(size=14, location=(0, 0, 0))
    floor = bpy.context.object
    floor.name = "Floor"
    floor.data.materials.append(make_material("Floor", (0.020, 0.022, 0.030, 1), 0.55))

    def lamp(name, loc, energy, size, color):
        light = bpy.data.lights.new(name, type="AREA")
        light.energy = energy
        light.size = size
        light.color = color
        obj = bpy.data.objects.new(name, light)
        obj.location = loc
        bpy.context.collection.objects.link(obj)
        direction = Vector((0, 0, 1.1)) - Vector(loc)
        obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        return obj

    # The browser build's LIGHT vector is up and to the left; so is this key.
    lamp("Key",  (-2.2,  -3.4, 2.9), 150, 2.6, (1.00, 0.86, 0.66))
    lamp("Rim",  ( 3.1,   2.1, 2.5), 320, 1.6, (0.96, 0.28, 0.34))
    lamp("Fill", ( 1.9,  -3.4, 1.6),  70, 4.0, (0.62, 0.72, 1.00))


def add_camera(location, look_at=Vector((0, 0, 0.98)), lens=70):
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = lens
    cam = bpy.data.objects.new("Cam", cam_data)
    cam.location = location
    cam.rotation_euler = (look_at - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return cam


def render(path, samples=48, res=(760, 1000)):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    # AgX washes the palette out; these colours are the game's and should
    # arrive as themselves.
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


# ==================================================================== exports

def export(arm_obj, mesh_obj):
    os.makedirs(OUT_MODELS, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    arm_obj.select_set(True)
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj

    glb = os.path.join(OUT_MODELS, "Ahmed.glb")
    bpy.ops.export_scene.gltf(
        filepath=glb,
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=True,
    )

    fbx = os.path.join(OUT_MODELS, "Ahmed.fbx")
    bpy.ops.export_scene.fbx(
        filepath=fbx,
        use_selection=True,
        apply_unit_scale=True,
        global_scale=1.0,
        apply_scale_options="FBX_SCALE_UNITS",   # metres -> Unreal centimetres
        add_leaf_bones=False,
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        object_types={"ARMATURE", "MESH"},
        mesh_smooth_type="FACE",
        bake_space_transform=False,
    )
    return glb, fbx


def export_unity(arm_obj, mesh_obj):
    """The same body again, in Unity's terms.

    It cannot be the same file as the Unreal one. Two settings differ and both
    of them are load-bearing:

      Scale. Unreal works in centimetres, so that export bakes metres into
      centimetres with FBX_SCALE_UNITS. Unity works in metres, so this one
      must not -- FBX_SCALE_NONE. Import the Unreal file into Unity and Ahmed
      is a hundred metres tall.

      Axes. Blender is Z-up and Unity is Y-up, and `bake_space_transform`
      decides whether that rotation is baked into the vertices or left for the
      importer to apply as a -90 degree offset on the root. Baked is what
      keeps a Humanoid avatar's bones pointing where Unity expects.

    Ahmed faces -Y in Blender, and both conventions send Blender's -Y to their
    own forward -- Unreal's +X, Unity's +Z -- so he arrives facing the right
    way in both without any special case.
    """
    os.makedirs(OUT_UNITY, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    arm_obj.select_set(True)
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj

    fbx = os.path.join(OUT_UNITY, "Ahmed.fbx")
    bpy.ops.export_scene.fbx(
        filepath=fbx,
        use_selection=True,
        apply_unit_scale=True,
        global_scale=1.0,
        apply_scale_options="FBX_SCALE_NONE",    # metres stay metres
        add_leaf_bones=False,
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        object_types={"ARMATURE", "MESH"},
        mesh_smooth_type="FACE",
        axis_forward="-Z",
        axis_up="Y",
        bake_space_transform=True,               # Y-up baked, not left as an offset
    )
    return fbx


# ======================================================================= main

def main():
    reset_scene()

    body = build_body()
    slots = add_material_slots(body)
    assign_kit(body, slots)          # coarse mesh: seams land on edge loops
    subdivide(body)
    assign_detail(body, slots)       # fine mesh: waistband, hair, beard
    add_waistband(body, slots)
    add_eyes(body, slots)
    add_face(body, slots)
    add_hair(body, slots)
    rig = build_armature()
    bind(body, rig)

    build_studio()

    os.makedirs(OUT_RENDER, exist_ok=True)

    pose(rig, GUARD)
    add_camera((1.55, -3.35, 1.24), look_at=Vector((0, 0, 0.90)), lens=62)
    render(os.path.join(OUT_RENDER, "ahmed-guard-3d.png"))

    pose(rig, KICK)
    add_camera((3.00, -2.45, 1.22), look_at=Vector((0.14, 0, 0.96)), lens=58)
    render(os.path.join(OUT_RENDER, "ahmed-kick-3d.png"))

    # Ship the model in its A-pose so UE5 can retarget onto it cleanly.
    pose(rig, {})
    add_camera((0.35, -3.60, 1.05), look_at=Vector((0, 0, 0.90)), lens=58)
    render(os.path.join(OUT_RENDER, "ahmed-apose-3d.png"))
    glb, fbx = export(rig, body)
    unity_fbx = export_unity(rig, body)

    tris = sum(len(p.vertices) - 2 for p in body.data.polygons)
    print("verts      :", len(body.data.vertices))
    print("tris       :", tris)
    print("bones      :", len(rig.data.bones))
    print("materials  :", [m.name for m in body.data.materials])
    print("glb        :", glb, os.path.getsize(glb), "bytes")
    print("fbx        :", fbx, os.path.getsize(fbx), "bytes")
    print("unity fbx  :", unity_fbx, os.path.getsize(unity_fbx), "bytes")


if __name__ == "__main__":
    main()
