"""
Builds Ahmed as a rigged 3D character and exports him for Unreal Engine 5 and
for the Unity port.

Run headless with no Blender install required:

    pip install bpy
    python3 build_ahmed.py            # the hero: 4K colour, 2K normals, 64-sample renders
    python3 build_ahmed.py --fast     # 1K textures and quick renders, for a look
    python3 build_ahmed.py --resume   # reload the nine-minute body and redo the rest
    python3 build_ahmed.py --coarse   # a rough body, to check the later stages

The body is built in `hero/`: lofted cross-sections and limb tubes, unioned by
voxel remesh in two passes, a face sculpted as a displacement field, hair,
eyes, then the tee and the track pants as shells off the body, all painted by
position and baked to textures from the full-resolution surface onto a 60k
triangle game mesh. This file keeps what the pipeline is built on: the joint
table the armature and the anatomy both read, the mannequin skeleton with its
IK, the poses, the studio and the renders.

The rest pose is a standard A-pose and the bones carry Unreal mannequin names
(`pelvis`, `upperarm_l`, `thigh_r`, ...) plus the mannequin's finger bones, so
the mesh retargets onto UE5's mannequin animations without a bone-mapping pass.
"""

import math
import os
import sys

import bpy
import bmesh
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
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
    # The kit the browser build lists for him (assets/ahmed.js): taped fists,
    # a wristwatch on the lead arm, the flag on the chest. Same man.
    "wrap":   (0.807, 0.768, 0.672, 1.0),   # #e8e2d4  hand tape, the browser's tapeCol
    "watch":  (0.030, 0.034, 0.045, 1.0),   # dark steel
    "mouth":  (0.190, 0.062, 0.045, 1.0),   # the lip line inside the beard
    "flag_g": (0.000, 0.201, 0.047, 1.0),   # #007a3d
    "flag_w": (0.887, 0.913, 0.940, 1.0),   # #f3f5f8
    "flag_r": (0.608, 0.008, 0.043, 1.0),   # #c8102e
    "flag_k": (0.004, 0.005, 0.007, 1.0),   # #101216
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
    # The two masses an athlete's shoulder has and a tube does not: the
    # trapezius sloping from the neck out to the shoulder, and the deltoid
    # capping it. Both shaping joints; neither is a mannequin bone.
    ("trap",      Vector((0.062,  0.012, 1.488)),  "spine_03",   0.056),
    ("delt",      Vector((0.200, -0.005, 1.450)),  "clavicle",   0.060),
    ("upperarm",  Vector((0.178, -0.006, 1.442)),  "clavicle",   0.055),
    ("biceps",    Vector((0.285, -0.003, 1.335)),  "upperarm",   0.060),
    # The elbow sits 1.2 cm behind the shoulder-to-wrist line and the knee
    # 1.2 cm in front of the hip-to-ankle line. A perfectly straight limb has
    # no bend direction, and an IK solver asked to shorten one picks a side
    # at random -- sideways, or backwards. The pre-bend is the answer every
    # rig gives: it tells the solver which way the joint goes before it has
    # to decide, and it is far too small to see in the mesh.
    ("lowerarm",  Vector((0.415,  0.012, 1.205)),  "biceps",     0.043),
    ("forearm",   Vector((0.471,  0.000, 1.149)),  "lowerarm",   0.053),
    ("hand",      Vector((0.601,  0.000, 1.019)),  "forearm",    0.032),
    ("hand_end",  Vector((0.654,  0.000, 0.966)),  "hand",       0.042),
    # A fist, not a mitt. Four fingers curl off the knuckle row -- out along
    # the arm to the knuckle, down into the palm, back toward the wrist --
    # and the thumb lies across them. All shaping joints: the mannequin has
    # finger bones but a closed fist never opens in this game, so the mesh
    # carries the fingers and the skeleton stays the 24 that retarget.
    # Palm faces -Y, the way Ahmed faces; the back of the fist is +Y.
    ("knuckle_1", Vector((0.664,  0.000, 0.978)),  "hand_end",   0.0090),
    ("knuckle_2", Vector((0.672,  0.000, 0.960)),  "hand_end",   0.0095),
    ("knuckle_3", Vector((0.664,  0.000, 0.943)),  "hand_end",   0.0090),
    ("knuckle_4", Vector((0.652,  0.000, 0.928)),  "hand_end",   0.0082),
    ("phalanx_1", Vector((0.668, -0.024, 0.982)),  "knuckle_1",  0.0080),
    ("phalanx_2", Vector((0.676, -0.025, 0.963)),  "knuckle_2",  0.0085),
    ("phalanx_3", Vector((0.668, -0.024, 0.946)),  "knuckle_3",  0.0080),
    ("phalanx_4", Vector((0.655, -0.022, 0.931)),  "knuckle_4",  0.0072),
    ("tip_1",     Vector((0.651, -0.026, 0.996)),  "phalanx_1",  0.0068),
    ("tip_2",     Vector((0.658, -0.027, 0.979)),  "phalanx_2",  0.0072),
    ("tip_3",     Vector((0.650, -0.026, 0.963)),  "phalanx_3",  0.0068),
    ("tip_4",     Vector((0.638, -0.024, 0.949)),  "phalanx_4",  0.0062),
    ("thumb_1",   Vector((0.626, -0.024, 1.000)),  "hand",       0.0092),
    ("thumb_2",   Vector((0.648, -0.036, 0.984)),  "thumb_1",    0.0080),
    # Legs taper inward from hip to ankle, the way a person's do. They used to
    # splay -- ankles wider apart than hips -- which reads as bow-legged from
    # the front and is the first thing wrong with a blockout's stance.
    ("thigh",     Vector((0.092,  0.000, 0.952)),  "pelvis",     0.100),
    ("quad",      Vector((0.090,  0.000, 0.776)),  "thigh",      0.090),
    ("calf",      Vector((0.088, -0.012, 0.513)),  "quad",       0.060),
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
_SHAPE_BASES = ("biceps", "forearm", "quad", "calf_belly", "heel", "toe",
                "trap", "delt",
                "knuckle_1", "knuckle_2", "knuckle_3", "knuckle_4",
                "phalanx_1", "phalanx_2", "phalanx_3", "phalanx_4",
                "tip_1", "tip_2", "tip_3", "tip_4", "thumb_1", "thumb_2")
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


def make_material(name, rgba, roughness=0.62, sheen=0.0, metallic=0.0,
                  subsurface=0.0, weave=0.0, coat=0.0):
    """A Principled BSDF that answers to the light the way the surface does.

    Base colour, roughness and metallic are the three that survive export --
    glTF carries them and Unreal reads them on import. Subsurface (skin),
    the coat (an eye's wet surface, a trainer's synthetic) and the weave (a
    procedural bump that gives cloth a fibre) exist for the renders in
    Docs/renders and do not travel: those want a baked texture and this mesh
    has no UVs. What the engine gets is the right colour at the right
    roughness; what it does not get yet is written in the README.
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if "Sheen Weight" in bsdf.inputs:
        bsdf.inputs["Sheen Weight"].default_value = sheen
    if subsurface > 0.0 and "Subsurface Weight" in bsdf.inputs:
        bsdf.inputs["Subsurface Weight"].default_value = subsurface
        # Red goes deepest in skin; the scale is centimetres of scatter.
        bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.25, 0.10)
        bsdf.inputs["Subsurface Scale"].default_value = 0.012
    if coat > 0.0 and "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = coat
        bsdf.inputs["Coat Roughness"].default_value = 0.08
    if weave > 0.0:
        # Fibre: a fine noise driven through a bump, so cloth is not a
        # painted colour. Procedural rather than a texture because there
        # are no UVs; it is what makes the tee read as jersey in the render.
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 900.0
        noise.inputs["Detail"].default_value = 4.0
        noise.inputs["Roughness"].default_value = 0.7
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = weave
        bump.inputs["Distance"].default_value = 0.0006
        links = mat.node_tree.links
        links.new(noise.outputs["Fac"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat

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

    add_ik_bones(arm_data, made)

    # A knee and an elbow are hinges, and a hinge has an axis. The IK below
    # locks each to rotation about its bone's X, so X has to lie across the
    # bend: roll the four chain bones on each side so their Z points the way
    # the joint bends -- forward for the leg, back for the arm -- and X falls
    # perpendicular to that plane. Left at roll zero the elbow's hinge faced
    # 40 degrees off its own pre-bend and the solver split the difference.
    for side in ("l", "r"):
        for base in ("thigh", "calf"):
            made["{}_{}".format(base, side)].align_roll(Vector((0, -1, 0)))
        for base in ("upperarm", "lowerarm"):
            made["{}_{}".format(base, side)].align_roll(Vector((0, 1, 0)))

    bpy.ops.object.mode_set(mode="OBJECT")
    return arm


# The UE5 mannequin's IK bones, and the root they hang from. They are real
# bones in the export so both engines see the mannequin's full hierarchy, but
# they move no vertex: use_deform is off, so bone heat never weights to them
# and the mesh never knows they exist. Each IK bone copies the bone it
# stands in for -- ik_foot_l is foot_l's head and tail -- so a retarget sees
# the same axes on both.
IK_BONES = [
    # (name, parent, copy-of)
    ("ik_foot_root", "root",         None),
    ("ik_foot_l",    "ik_foot_root", "foot_l"),
    ("ik_foot_r",    "ik_foot_root", "foot_r"),
    ("ik_hand_root", "root",         None),
    ("ik_hand_gun",  "ik_hand_root", "hand_r"),
    ("ik_hand_l",    "ik_hand_gun",  "hand_l"),
    ("ik_hand_r",    "ik_hand_gun",  "hand_r"),
]


def add_ik_bones(arm_data, made):
    """root above the pelvis, then the IK targets under root.

    root sits at the origin because the IK targets need a parent that does
    not move with the hips: a foot target that followed the pelvis would
    follow the body off the floor it is meant to be holding the foot to.
    """
    root = arm_data.edit_bones.new("root")
    root.head = Vector((0, 0, 0))
    root.tail = Vector((0, 0, 0.06))
    root.use_deform = False
    made["pelvis"].parent = root
    made["root"] = root

    for name, parent, like in IK_BONES:
        bone = arm_data.edit_bones.new(name)
        if like:
            bone.head = made[like].head.copy()
            bone.tail = made[like].tail.copy()
        else:
            bone.head = Vector((0, 0, 0))
            bone.tail = Vector((0, 0, 0.06))
        bone.use_deform = False
        bone.parent = made[parent]
        made[name] = bone


# ================================================================== IK setup

# The chains the solver drives: the bone that carries the constraint, the
# target it reaches for, and the pole that says which way the joint bends.
# Two bones per chain because the shaping joints are not bones -- thigh then
# calf, upperarm then lowerarm -- so the solve is the clean two-bone case.
IK_CHAINS = [
    # (constrained bone, target bone, pole empty, rest pole offset from the joint)
    ("calf_l",     "ik_foot_l", "Pole_Knee_l",  Vector((0.0, -0.6,  0.0))),
    ("calf_r",     "ik_foot_r", "Pole_Knee_r",  Vector((0.0, -0.6,  0.0))),
    # Each rest pole sits out along its joint's pre-bend, because that is the
    # plane the hinge bends in: knees forward, elbows back.
    ("lowerarm_l", "ik_hand_l", "Pole_Elbow_l", Vector((0.0,  0.6,  0.0))),
    ("lowerarm_r", "ik_hand_r", "Pole_Elbow_r", Vector((0.0,  0.6,  0.0))),
]


def add_ik(arm_obj):
    """IK constraints on the four limbs, with pole angles measured, not guessed.

    The knee and elbow poles are Empties rather than bones so they are never
    exported (the exporters take armatures and meshes only). Each pole angle
    is then found by search: with every target at its rest position the
    solved pose must be the rest pose, and the angle that makes it so is the
    one the constraint keeps. On a limb this straight the wrong angle does
    not bend the knee, it twists the whole leg about its own axis, and the
    foot goes with it.
    """
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="POSE")
    for bone_name, target, pole_name, offset in IK_CHAINS:
        joint = arm_obj.pose.bones[bone_name].bone.head_local
        pole = bpy.data.objects.new(pole_name, None)
        pole.empty_display_size = 0.05
        pole.location = joint + offset
        bpy.context.collection.objects.link(pole)

        c = arm_obj.pose.bones[bone_name].constraints.new("IK")
        c.name = "IK"
        c.target = arm_obj
        c.subtarget = target
        c.pole_target = pole
        c.chain_count = 2
        c.use_tail = True

        # A knee and an elbow are hinges. Left free on all three axes the
        # solver bends them sideways as happily as forwards.
        pb = arm_obj.pose.bones[bone_name]
        pb.lock_ik_y = True
        pb.lock_ik_z = True
    bpy.ops.object.mode_set(mode="OBJECT")

    pose(arm_obj, {})
    for bone_name, _, _, _ in IK_CHAINS:
        _tune_pole_angle(arm_obj, bone_name)
    for chain in IK_CHAINS:
        _limit_hinge(arm_obj, chain)


def _limit_hinge(arm_obj, chain):
    """Let the hinge bend one way only, and find out which way by asking.

    Which sign of rotation about the bone's X is the knee bending forwards
    depends on the bone's roll, and the roll came from a head and a tail, so
    rather than assert a convention the chain is solved once to a target
    that has to bend it, with the pole on the anatomical side, and the sign
    that produced is the sign that is allowed from then on. The pre-bend in
    the joint table is what makes that probe land on the right side.
    """
    bone_name, target, pole_name, offset = chain
    pb = arm_obj.pose.bones[bone_name]
    root = pb.parent
    joint = pb.bone.head_local.copy()
    tail = pb.bone.tail_local.copy()
    towards_root = (root.bone.head_local - tail).normalized()
    pose(arm_obj, {}, {target: tail + towards_root * 0.15}, {pole_name: joint + offset})

    rest = root.bone.matrix_local.inverted() @ pb.bone.matrix_local
    now = root.matrix.inverted() @ pb.matrix
    bent = math.degrees((rest.inverted() @ now).to_euler("XYZ").x)
    mid = (root.head + pb.tail) * 0.5
    towards_pole = (pb.head - mid).normalized().dot((Vector(joint + offset) - mid).normalized())
    assert abs(bent) > 20.0 and towards_pole > 0.9, \
        "hinge probe on {} did not bend towards its pole ({:.1f} deg, dot {:.2f})".format(
            bone_name, bent, towards_pole)

    pb.use_ik_limit_x = True
    if bent < 0.0:
        pb.ik_min_x, pb.ik_max_x = math.radians(-160.0), 0.0
    else:
        pb.ik_min_x, pb.ik_max_x = 0.0, math.radians(160.0)
    print("hinge       : {:<11} bends {:+.1f} deg towards its pole (dot {:.3f}); "
          "limited to that side".format(bone_name, bent, towards_pole))
    pose(arm_obj, {})


def _chain_deviation(arm_obj, bone_name):
    """How far the two chain bones sit from their rest matrices, in metres
    and in matrix terms -- zero means the solve reproduces the rest pose."""
    worst = 0.0
    pb = arm_obj.pose.bones[bone_name]
    for bone in (pb, pb.parent):
        delta = bone.matrix - bone.bone.matrix_local
        for row in delta:
            for v in row:
                worst = max(worst, abs(v))
    return worst


def _tune_pole_angle(arm_obj, bone_name):
    c = arm_obj.pose.bones[bone_name].constraints["IK"]

    def deviation(deg):
        c.pole_angle = math.radians(deg)
        bpy.context.view_layer.update()
        return _chain_deviation(arm_obj, bone_name)

    best = min(range(-180, 180, 2), key=deviation)
    best = min((best + k * 0.1 for k in range(-20, 21)), key=deviation)
    best = min((best + k * 0.005 for k in range(-20, 21)), key=deviation)
    final = deviation(best)
    print("pole angle  : {:<11} {:8.1f} deg   rest deviation {:.2e}".format(
        bone_name, best, final))
    assert final < 1e-3, "IK will not sit still at rest on " + bone_name


def mute_ik(arm_obj, muted):
    for bone_name, _, _, _ in IK_CHAINS:
        arm_obj.pose.bones[bone_name].constraints["IK"].mute = muted
    bpy.context.view_layer.update()


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


def pose(arm_obj, directions, targets=None, poles=None):
    """A pose is where each limb points, in world space -- not Euler angles --
    plus, for the four limbs, where the foot or the fist is.

    Aiming bones is how you would describe a stance out loud ("lead hand up by
    the chin, rear leg back"), and unlike per-bone Euler triples it does not
    silently mirror wrong: the left and right sides take the same numbers with
    x negated, and both land where they should. The limbs go a step further:
    the aims say roughly where a leg or an arm goes, and then the IK targets
    say exactly where it ends, so a planted foot is planted and a fist on the
    chin is on the chin whatever the rest of the body did.

    `targets` are world positions for ik_foot_l/r and ik_hand_l/r; `poles`
    are world positions for the four pole Empties. With neither given every
    target sits at rest and the IK reproduces the FK pose to the millimetre.
    """
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="POSE")

    for bone in arm_obj.pose.bones:
        bone.rotation_mode = "QUATERNION"
        bone.rotation_quaternion = (1, 0, 0, 0)
        bone.location = (0, 0, 0)
    bpy.context.view_layer.update()

    # Targets and poles first, aims second. An aim is a world-space matrix
    # written against the bone's parent as it is evaluated at that moment,
    # so a foot aimed before its calf has been solved is aimed against the
    # wrong calf and ends up tilted by however far the solver moved it.
    for name, where in (poles or {}).items():
        bpy.data.objects[name].location = Vector(where)
    for name, where in (targets or {}).items():
        pbone = arm_obj.pose.bones[name]
        matrix = pbone.matrix.copy()
        matrix.translation = Vector(where)
        pbone.matrix = matrix
    bpy.context.view_layer.update()

    for name in _hierarchy_order(arm_obj):
        if name not in directions:
            continue
        if targets and name in CHAIN_BONES:
            continue
        pbone = arm_obj.pose.bones[name]
        aim = Vector(directions[name]).normalized()
        matrix = aim.to_track_quat("Y", "Z").to_matrix().to_4x4()
        matrix.translation = pbone.matrix.translation
        pbone.matrix = matrix
        bpy.context.view_layer.update()

    bpy.ops.object.mode_set(mode="OBJECT")


# The bones the solver owns. When a pose gives IK targets these are not
# aimed: an aim written before the solve only tells the solver where to start
# looking, and started on the wrong side of a hinge it finds the wrong
# solution and stays there.
CHAIN_BONES = {"{}_{}".format(base, side)
               for base in ("thigh", "calf", "upperarm", "lowerarm")
               for side in ("l", "r")}


def _pole_from(a, b, c, fallback):
    """Where a joint's pole goes so the IK bends the way the FK did: out
    along the bend, from the joint. A straight limb has no bend to read, so
    it takes the fallback direction instead."""
    bend = b - (a + c) * 0.5
    if bend.length < 0.01:
        bend = fallback
    return b + bend.normalized() * 0.6


def _foot_floor(mesh_obj, arm_obj, side):
    """The lowest point of the mesh that this foot carries, in world z."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = mesh_obj.evaluated_get(depsgraph)
    groups = {g.index for g in mesh_obj.vertex_groups
              if g.name in ("foot_" + side, "ball_" + side)}
    lowest = None
    for vert, evaluated_vert in zip(mesh_obj.data.vertices, evaluated.data.vertices):
        if any(g.group in groups and g.weight > 0.3 for g in vert.groups):
            z = (evaluated.matrix_world @ evaluated_vert.co).z
            lowest = z if lowest is None else min(lowest, z)
    return lowest


def limb_targets(arm_obj, mesh_obj, fk, plant):
    """Turn an FK stance into IK targets, then put the planted feet down.

    The FK stance is posed once with the IK muted and the ankles, wrists,
    knees and elbows read off it: the targets are the ankles and wrists, the
    poles sit out along each joint's bend. That reproduces the stance
    exactly, which is the point -- the look was tuned by aiming bones and
    should not change because the solver did. Then each planted foot's
    target is lowered until the foot's sole is where it is in the rest pose,
    which is the floor. Returns (targets, poles, report).
    """
    mute_ik(arm_obj, True)
    pose(arm_obj, fk)
    pb = arm_obj.pose.bones
    world = arm_obj.matrix_world
    targets, poles = {}, {}
    for side in ("l", "r"):
        hip, knee, ankle = (world @ pb["thigh_" + side].head, world @ pb["calf_" + side].head,
                            world @ pb["calf_" + side].tail)
        targets["ik_foot_" + side] = ankle.copy()
        if side in plant:
            # A standing knee bends forward, whatever the aims said. The FK
            # guard had the rear knee ten centimetres behind the hip-to-ankle
            # line, which is a knee bent the wrong way, and a solver that
            # copied it would only be reproducing the mistake with more
            # precision.
            poles["Pole_Knee_" + side] = knee + Vector((0, -0.6, 0))
        else:
            poles["Pole_Knee_" + side] = _pole_from(hip, knee, ankle, Vector((0, -1, 0)))
        shoulder, elbow, wrist = (world @ pb["upperarm_" + side].head,
                                  world @ pb["lowerarm_" + side].head,
                                  world @ pb["lowerarm_" + side].tail)
        targets["ik_hand_" + side] = wrist.copy()
        poles["Pole_Elbow_" + side] = _pole_from(shoulder, elbow, wrist, Vector((0, 1, 0)))
    mute_ik(arm_obj, False)

    pose(arm_obj, {})
    floor = {side: _foot_floor(mesh_obj, arm_obj, side) for side in ("l", "r")}

    report = {}
    for side in plant:
        for _ in range(3):
            pose(arm_obj, fk, targets, poles)
            drop = _foot_floor(mesh_obj, arm_obj, side) - floor[side]
            targets["ik_foot_" + side].z -= drop
            if abs(drop) < 0.0005:
                break
    pose(arm_obj, fk, targets, poles)
    for side in ("l", "r"):
        report["foot_" + side] = _foot_floor(mesh_obj, arm_obj, side) - floor[side]
        report["hand_" + side] = ((world @ pb["lowerarm_" + side].tail)
                                  - targets["ik_hand_" + side]).length
        hip, knee, ankle = (world @ pb["thigh_" + side].head, world @ pb["calf_" + side].head,
                            world @ pb["calf_" + side].tail)
        report["knee_" + side] = (knee - (hip + ankle) * 0.5).y   # forward is -y
    return targets, poles, report


def print_pose_report(name, plant, report):
    print("pose {:<6}: ".format(name)
          + "  ".join("{} {:+.4f}".format(k, v) for k, v in sorted(report.items())))
    for side in plant:
        assert abs(report["foot_" + side]) < 0.003, "foot_{} is not on the floor".format(side)
    for side in ("l", "r"):
        assert report["hand_" + side] < 0.01, "hand_{} missed its target".format(side)
    for side in plant:
        assert report["knee_" + side] <= 0.0005, "knee_{} bends backwards".format(side)


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


# ====================================================================== main

def main():
    from hero import pipeline
    pipeline.run()


if __name__ == "__main__":
    main()
