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
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_MODELS = os.path.abspath(os.path.join(HERE, "..", "..", "Content", "Models"))
OUT_RENDER = os.path.abspath(os.path.join(HERE, "..", "..", "Docs", "renders"))

# Ahmed stands 1.80 m. Unreal works in centimetres, so both exporters below
# scale by 100 on the way out.
HEIGHT = 1.80

# --------------------------------------------------------------- palette
# Straight from the browser build's `col` table so the two Ahmeds match.
PALETTE = {
    "skin":   (0.729, 0.412, 0.208, 1.0),   # #d9a274
    "tee":    (0.031, 0.035, 0.047, 1.0),   # #17191e
    "shorts": (0.016, 0.019, 0.027, 1.0),   # #101216
    "band":   (0.608, 0.008, 0.043, 1.0),   # #c8102e  Kuwait red
    "hair":   (0.020, 0.013, 0.007, 1.0),   # #241a12
    "beard":  (0.026, 0.017, 0.010, 1.0),   # a shade off the hair
    "eye":    (0.012, 0.010, 0.009, 1.0),
}

# ---------------------------------------------------------------- joints
# name -> (position, parent, skin radius). One table, used for both the
# skinned body mesh and the armature.
J = {
    "pelvis":     (Vector((0.00,  0.00, 0.98)), None,        0.118),
    "spine_01":   (Vector((0.00,  0.00, 1.14)), "pelvis",    0.106),
    "spine_02":   (Vector((0.00,  0.00, 1.29)), "spine_01",  0.124),
    "spine_03":   (Vector((0.00,  0.00, 1.44)), "spine_02",  0.146),
    "neck_01":    (Vector((0.00,  0.00, 1.55)), "spine_03",  0.064),
    "head":       (Vector((0.00,  0.012, 1.66)), "neck_01",  0.092),
    "head_end":   (Vector((0.00,  0.00, 1.755)), "head",     0.040),
}

_LIMB = [
    # (base name, position, parent, radius)
    ("clavicle", Vector((0.050, 0.00, 1.455)), "spine_03", 0.098),
    ("upperarm", Vector((0.200, 0.00, 1.450)), "clavicle", 0.070),
    ("lowerarm", Vector((0.420, 0.00, 1.235)), "upperarm", 0.054),
    ("hand",     Vector((0.610, 0.00, 1.030)), "lowerarm", 0.044),
    ("hand_end", Vector((0.665, 0.00, 0.975)), "hand",     0.036),
    ("thigh",    Vector((0.100, 0.00, 0.950)), "pelvis",   0.094),
    ("calf",     Vector((0.112, 0.00, 0.500)), "thigh",    0.070),
    ("foot",     Vector((0.112, 0.00, 0.085)), "calf",     0.050),
    ("ball",     Vector((0.112, -0.155, 0.045)), "foot",   0.040),
]

for _name, _pos, _parent, _r in _LIMB:
    for _side, _sign in (("l", 1.0), ("r", -1.0)):
        _p = Vector((_pos.x * _sign, _pos.y, _pos.z))
        _par = _parent if _parent in J else "{}_{}".format(_parent, _side)
        J["{}_{}".format(_name, _side)] = (_p, _par, _r)

ORDER = list(J.keys())


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

    # The torso reads as a slab unless it is wider than it is deep, and the
    # head wants to be an egg rather than a ball.
    for name, (rx, ry) in {
        "spine_01": (0.142, 0.100),   # waist: narrower than both ends
        "spine_02": (0.176, 0.106),   # ribcage
        "spine_03": (0.205, 0.112),   # the shoulder shelf
        "clavicle": (0.108, 0.100),   # deltoid, not a coat hanger
        "pelvis":   (0.145, 0.112),
        "head":     (0.090, 0.100),
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
        ("tee",    make_material("Ahmed_Tee", PALETTE["tee"], 0.78, sheen=0.25)),
        ("shorts", make_material("Ahmed_Shorts", PALETTE["shorts"], 0.74, sheen=0.2)),
        ("band",   make_material("Ahmed_Band", PALETTE["band"], 0.66)),
        ("hair",   make_material("Ahmed_Hair", PALETTE["hair"], 0.42)),
        ("beard",  make_material("Ahmed_Beard", PALETTE["beard"], 0.50)),
        ("eye",    make_material("Ahmed_Eye", PALETTE["eye"], 0.18)),
    ]
    for _, mat in mats:
        obj.data.materials.append(mat)
    return {key: i for i, (key, _) in enumerate(mats)}


def assign_kit(obj, idx):
    """Kit, painted before subdivision so every seam lands on an edge loop."""
    shoulder_z = J["upperarm_l"][0].z
    for poly in obj.data.polygons:
        c = poly.center
        z, ax = c.z, abs(c.x)

        if 1.02 < z <= 1.50 and ax < 0.26:             # tee body
            poly.material_index = idx["tee"]
        elif 0.24 <= ax < 0.34 and z > shoulder_z - 0.14:
            poly.material_index = idx["tee"]           # short sleeves
        elif 0.58 <= z <= 1.02:                        # fight shorts
            poly.material_index = idx["shorts"]
        else:
            poly.material_index = idx["skin"]


def assign_detail(obj, idx):
    """Waistband, hair and beard -- after subdivision, where polys are fine."""
    head = J["head"][0]
    band_lo, band_hi = 0.995, 1.035
    for poly in obj.data.polygons:
        c = poly.center

        if band_lo <= c.z <= band_hi and abs(c.x) < 0.20 and abs(c.y) < 0.16:
            poly.material_index = idx["band"]
            continue
        if c.z < head.z - 0.09:
            continue
        d = c - head
        if c.z > head.z + 0.048 or d.y < -0.050:       # crown and back
            poly.material_index = idx["hair"]
        elif c.z < head.z - 0.004 and d.y > 0.030:     # jaw and chin
            poly.material_index = idx["beard"]


def add_eyes(obj, idx):
    """Two spheres set into the skull -- enough for the head to read as a face."""
    head = J["head"][0]
    for sign in (1, -1):
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=0.0145, segments=14, ring_count=10,
            location=(head.x + 0.032 * sign, head.y + 0.080, head.z + 0.020),
        )
        eye = bpy.context.object
        eye.scale = (1.0, 0.72, 1.0)
        bpy.ops.object.transform_apply(scale=True)
        bpy.ops.object.shade_smooth()
        # Share the body's material datablock so the join merges the slots
        # instead of leaving an empty one behind.
        eye.data.materials.append(obj.data.materials[idx["eye"]])
        for poly in eye.data.polygons:
            poly.material_index = 0

        bpy.ops.object.select_all(action="DESELECT")
        eye.select_set(True)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.join()


# ==================================================================== rigging

def build_armature():
    arm_data = bpy.data.armatures.new("AhmedSkeleton")
    arm = bpy.data.objects.new("Ahmed_Rig", arm_data)
    bpy.context.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")

    made = {}
    # `*_end` joints only give the last real bone somewhere to point.
    for name in ORDER:
        if name.endswith("_end"):
            continue
        pos, parent, _ = J[name]

        children = [n for n in ORDER if J[n][1] == name]
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
    neck_01=(0, 0.10, 1.0), head=(0, 0.06, 1.0),
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
    lamp("Key",  (-2.8,  -2.6, 3.5), 130, 2.6, (1.00, 0.86, 0.66))
    lamp("Rim",  ( 3.1,   2.1, 2.5), 170, 1.6, (0.96, 0.28, 0.34))
    lamp("Fill", ( 1.9,  -3.4, 1.6),  26, 4.0, (0.62, 0.72, 1.00))


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


# ======================================================================= main

def main():
    reset_scene()

    body = build_body()
    slots = add_material_slots(body)
    assign_kit(body, slots)          # coarse mesh: seams land on edge loops
    subdivide(body)
    assign_detail(body, slots)       # fine mesh: waistband, hair, beard
    add_eyes(body, slots)
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

    tris = sum(len(p.vertices) - 2 for p in body.data.polygons)
    print("verts      :", len(body.data.vertices))
    print("tris       :", tris)
    print("bones      :", len(rig.data.bones))
    print("materials  :", [m.name for m in body.data.materials])
    print("glb        :", glb, os.path.getsize(glb), "bytes")
    print("fbx        :", fbx, os.path.getsize(fbx), "bytes")


if __name__ == "__main__":
    main()
