"""
Builds Saud as a rigged 3D character and exports him for Unreal Engine 5 and
for the Unity port.

Run headless with no Blender install required:

    pip install bpy
    python3 build_saud.py            # the hero: 4K colour, 2K normals, 64-sample renders
    python3 build_saud.py --fast     # 1K textures and quick renders, for a look
    python3 build_saud.py --resume   # reload the nine-minute body and redo the rest
    python3 build_saud.py --coarse   # a rough body, to check the later stages

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
from mathutils import Vector, Matrix, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
# scale by 100 on the way out.
HEIGHT = 1.80

# --------------------------------------------------------------- palette
# Straight from the browser build's `col` table so the two Sauds match.
# Linear values, matching the browser build's `col` table for Saud.
PALETTE = {
    "skin":   (0.888, 0.716, 0.597, 1.0),   # #f0d8c4  fair
    "tee":    (0.029, 0.031, 0.039, 1.0),   # #15171c  fitted black tee
    "pants":  (0.020, 0.021, 0.027, 1.0),   # #0e1014  black trousers
    "shoe":   (0.032, 0.034, 0.040, 1.0),   # trainers, a touch off the trousers
    "band":   (0.608, 0.008, 0.043, 1.0),   # #c8102e  Kuwait red
    "hair":   (0.020, 0.014, 0.009, 1.0),   # #1e150f
    "beard":  (0.026, 0.018, 0.012, 1.0),   # a shade off the hair
    "eye":    (0.012, 0.010, 0.009, 1.0),
    # The kit the browser build lists for him (assets/saud.js): taped fists,
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
# **Saud faces -Y.** Everything that gives him a front -- the toes, the face,
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
    ("clavicle",  Vector((0.052, -0.012, 1.448)),  "spine_03",   0.100),
    # The two masses an athlete's shoulder has and a tube does not: the
    # trapezius sloping from the neck out to the shoulder, and the deltoid
    # capping it. Both shaping joints; neither is a mannequin bone.
    ("trap",      Vector((0.068,  0.012, 1.488)),  "spine_03",   0.056),
    ("delt",      Vector((0.222, -0.005, 1.450)),  "clavicle",   0.060),
    ("upperarm",  Vector((0.200, -0.006, 1.442)),  "clavicle",   0.055),
    ("biceps",    Vector((0.307, -0.003, 1.335)),  "upperarm",   0.060),
    # The elbow sits 1.2 cm behind the shoulder-to-wrist line and the knee
    # 1.2 cm in front of the hip-to-ankle line. A perfectly straight limb has
    # no bend direction, and an IK solver asked to shorten one picks a side
    # at random -- sideways, or backwards. The pre-bend is the answer every
    # rig gives: it tells the solver which way the joint goes before it has
    # to decide, and it is far too small to see in the mesh.
    ("lowerarm",  Vector((0.437,  0.012, 1.205)),  "biceps",     0.043),
    ("forearm",   Vector((0.493,  0.000, 1.149)),  "lowerarm",   0.053),
    ("hand",      Vector((0.623,  0.000, 1.019)),  "forearm",    0.032),
    ("hand_end",  Vector((0.676,  0.000, 0.966)),  "hand",       0.042),
    # A fist, not a mitt. Four fingers curl off the knuckle row -- out along
    # the arm to the knuckle, down into the palm, back toward the wrist --
    # and the thumb lies across them. All shaping joints: the mannequin has
    # finger bones but a closed fist never opens in this game, so the mesh
    # carries the fingers and the skeleton stays the 24 that retarget.
    # Palm faces -Y, the way Saud faces; the back of the fist is +Y.
    ("knuckle_1", Vector((0.686,  0.000, 0.978)),  "hand_end",   0.0090),
    ("knuckle_2", Vector((0.694,  0.000, 0.960)),  "hand_end",   0.0095),
    ("knuckle_3", Vector((0.686,  0.000, 0.943)),  "hand_end",   0.0090),
    ("knuckle_4", Vector((0.674,  0.000, 0.928)),  "hand_end",   0.0082),
    ("phalanx_1", Vector((0.690, -0.024, 0.982)),  "knuckle_1",  0.0080),
    ("phalanx_2", Vector((0.698, -0.025, 0.963)),  "knuckle_2",  0.0085),
    ("phalanx_3", Vector((0.690, -0.024, 0.946)),  "knuckle_3",  0.0080),
    ("phalanx_4", Vector((0.677, -0.022, 0.931)),  "knuckle_4",  0.0072),
    ("tip_1",     Vector((0.673, -0.026, 0.996)),  "phalanx_1",  0.0068),
    ("tip_2",     Vector((0.680, -0.027, 0.979)),  "phalanx_2",  0.0072),
    ("tip_3",     Vector((0.672, -0.026, 0.963)),  "phalanx_3",  0.0068),
    ("tip_4",     Vector((0.660, -0.024, 0.949)),  "phalanx_4",  0.0062),
    ("thumb_1",   Vector((0.648, -0.024, 1.000)),  "hand",       0.0092),
    ("thumb_2",   Vector((0.670, -0.036, 0.984)),  "thumb_1",    0.0080),
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
    arm_data = bpy.data.armatures.new("SaudSkeleton")
    arm = bpy.data.objects.new("Saud_Rig", arm_data)
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


def pose(arm_obj, directions, targets=None, poles=None, drop=0.0):
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
    `drop` lowers the pelvis, and everything it carries, by that much: how
    limb_targets stands a bent-kneed stance on the floor (below).
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
    if drop:
        pel = arm_obj.pose.bones["pelvis"]
        m = pel.matrix.copy(); m.translation.z -= drop; pel.matrix = m
        bpy.context.view_layer.update()

    for name in _hierarchy_order(arm_obj):
        if name not in directions and "twist:" + name not in directions:
            continue
        if targets and name in CHAIN_BONES:
            continue
        if name not in directions:
            # twisted, not aimed: absolute (pose() reset every bone above)
            pbone = arm_obj.pose.bones[name]
            pbone.rotation_quaternion = Quaternion((0, 1, 0), float(directions["twist:" + name]))
            bpy.context.view_layer.update()
            continue
        pbone = arm_obj.pose.bones[name]
        aim = Vector(directions[name]).normalized()
        # the bone's current frame swung onto the aim with no twist about
        # its length: to_track_quat("Y", "Z") re-made the frame with world
        # up as its Z, which turns a bone whose rest Z is world -Y (spine,
        # neck, head) or down (a foot) half a turn about itself -- the chest
        # faced backwards and the soles came up in every posed render
        cur = pbone.matrix.to_3x3()
        y = Vector((cur[0][1], cur[1][1], cur[2][1])).normalized()
        matrix = (y.rotation_difference(aim).to_matrix() @ cur).to_4x4()
        matrix.translation = pbone.matrix.translation
        pbone.matrix = matrix
        bpy.context.view_layer.update()
        tw = directions.get("twist:" + name)      # see rig_full_ik._aim
        if tw:
            pbone.rotation_quaternion = pbone.rotation_quaternion @ Quaternion((0, 1, 0), float(tw))
            bpy.context.view_layer.update()
    total = sum(float(v) for k, v in directions.items() if k.startswith("twist:"))
    if total:
        for nm, share in (("neck_01", 0.40), ("head", 0.60)):
            pbone = arm_obj.pose.bones[nm]
            pbone.rotation_quaternion = pbone.rotation_quaternion @ Quaternion((0, 1, 0), -total * share)
        bpy.context.view_layer.update()
    for side in ("l", "r"):
        if "palm_" + side in directions:
            roll_palm(arm_obj, side, directions["palm_" + side])
    # A stance that asks for level soles (MMA_GUARD's "soles": "level", Saud
    # only, 2026-09-30) has both feet rolled level after the aim: an aim's
    # shortest arc rolled his rear sole 20.4 degrees. Here rather than only
    # in limb_targets, because the hero pipeline poses the man again with
    # limb_targets' answer (pipeline.py: pose(rig, guard, targets, poles,
    # drop)), which would re-aim the feet and lose the roll. Only a dict
    # with the key sees it -- KICK and every other man's stance have none.
    if directions.get("soles") == "level":
        for side in ("l", "r"):
            roll_sole(arm_obj, side)

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


def knee_pole(hip, knee, ankle, ball, twist_deg=15.0, back=False):
    """The pole that puts a PLANTED knee over its toes (2026-09-30, "make
    full suad aligment": Saud's rear foot turns out 35 degrees and the
    straight-forward pole below left its knee 18.7 cm inside the vertical
    plane through the foot's own axis -- a 43 degree twist between shin and
    foot, a tibia no man has). Pure vector maths, no bpy; shared with
    build_motion (planted_pole) so the rig and the clips solve one knee.

    The knee moves on a circle about the hip-to-ankle line: centre M, the
    FK `knee`'s foot on that line, radius its distance from it (a two-bone
    leg's lengths fix the circle; the FK knee only reads it off). The point
    K* on the FORWARD half of that circle (in front of the line along -Y,
    the way he faces) whose shin, seen from above (ankle toward knee), heads
    `twist_deg` INSIDE the foot's own heading (ankle toward ball, z dropped)
    -- the knee over the toes allowing an adult's external tibial torsion of
    15-20 degrees (an orthopaedic norm, from memory; measured on the rig at
    the search's 1-degree step, the rear knee lands 5 cm inside the foot's
    plane where the forward pole had it 18.7). Returned 0.6 m out along the
    bend from M, the way _pole_from puts a pole. `back=True` is the sabotage
    (build_motion --bite "knee"): the same bend mirrored behind the line."""
    e = (ankle - hip).normalized()
    M = hip + e * (knee - hip).dot(e)
    r = (knee - M).length
    fwd = Vector((0.0, -1.0, 0.0))
    u = (fwd - e * e.dot(fwd)).normalized()
    v = e.cross(u).normalized()
    fh = Vector((ball.x - ankle.x, ball.y - ankle.y, 0.0)).normalized()
    # "inside" is toward the other leg: +X for the right foot, -X for the left
    medial = Vector((1.0, 0.0, 0.0)) if ankle.x < 0.0 else Vector((-1.0, 0.0, 0.0))
    want = None
    for sgn in (1.0, -1.0):
        c = Matrix.Rotation(math.radians(sgn * twist_deg), 3, "Z") @ fh
        if want is None or c.dot(medial) > want.dot(medial):
            want = c
    best = None
    for i in range(360):
        t = math.radians(i)
        K = M + (u * math.cos(t) + v * math.sin(t)) * r
        if (K - M).dot(fwd) <= 0.0:
            continue
        sh = Vector((K.x - ankle.x, K.y - ankle.y, 0.0))
        if sh.length < 1e-6:
            continue
        score = sh.normalized().dot(want)
        if best is None or score > best[0]:
            best = (score, K)
    K = best[1]
    d = (K - M).normalized()
    return K - d * 0.6 if back else K + d * 0.6


KNEE_TRACK_IN = 5.0      # degrees a stepping knee points inside its toes


def knee_track_pole(hip, knee, ankle, ball, inside_deg=KNEE_TRACK_IN, back=False):
    """The pole that keeps a STEPPING knee over its toes (2026-10-03, "fix
    legs when walk": in Saud's steps the planted knee swung from 70 degrees
    outside its toes to 73 inside while the foot stood still, and the
    forward step's sat 39 inside). knee_pole() above reads the shin from
    above, which is the guard's question; when the hips travel half a
    metre over a planted foot the leg leans and its shin, seen from above,
    points along the lean whatever the knee does, so the search swung.
    Here the bend is put along the foot's own heading itself, taken across
    the hip-to-ankle line -- the knee over the toes whichever way the leg
    leans -- turned `inside_deg` toward the other leg, an adult's tibial
    twist. Pure vector maths. `back` mirrors it behind the line."""
    e = (ankle - hip).normalized()
    M = hip + e * (knee - hip).dot(e)
    fh = Vector((ball.x - ankle.x, ball.y - ankle.y, 0.0))
    b = fh - e * fh.dot(e)
    if b.length < 1e-6:
        b = Vector((0.0, -1.0, 0.0)) - e * e.y * -1.0
    b.normalize()
    medial = Vector((1.0, 0.0, 0.0)) if ankle.x < 0.0 else Vector((-1.0, 0.0, 0.0))
    best = None
    for sgn in (1.0, -1.0):
        c = Matrix.Rotation(math.radians(sgn * inside_deg), 3, e) @ b
        if best is None or c.dot(medial) > best.dot(medial):
            best = c
    return M - best * 0.6 if back else M + best * 0.6


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
    # A stance that asks for level soles (MMA_GUARD's "soles": "level",
    # Saud only, 2026-09-30) has its feet rolled level by pose() itself
    # after every aim (see there: the pipeline poses again with this
    # function's answer), so every pose below stands on level soles.
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
            if fk.get("knee_pole") == "foot":
                # ...and over its toes (MMA_GUARD, Saud only, 2026-09-30):
                # straight forward whatever the foot's yaw, Saud's rear foot,
                # turned out 35 degrees, had its knee 18.7 cm inside the
                # foot's own line -- knee_pole says the rest
                poles["Pole_Knee_" + side] = knee_pole(hip, knee, ankle, world @ pb["ball_" + side].head)
            elif fk.get("knee_pole") == "track":
                # the bosses' stances (2026-10-03): the bend along the foot
                poles["Pole_Knee_" + side] = knee_track_pole(hip, knee, ankle, world @ pb["ball_" + side].head)
            else:
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
    # The body comes down onto its feet, not the feet down to the floor: a
    # foot pulled down under a hip that stays where it was straightens the
    # knee, and Saud's MMA stance, 38 degrees at each knee, rendered
    # straight-legged that way (2026-09-25). The whole man -- pelvis, every
    # target, every pole -- is lowered until the higher planted foot is on
    # the floor -- the LOWER-reaching foot; the other, under the floor by
    # then, is raised, which bends its knee rather than straightening it.
    pose(arm_obj, fk, targets, poles)
    body = max(0.0, max(_foot_floor(mesh_obj, arm_obj, side) - floor[side] for side in plant))
    for d in (targets, poles):
        for k in d:
            d[k] = d[k] - Vector((0.0, 0.0, body))
    report["body_drop"] = body
    for side in plant:
        for _ in range(3):
            pose(arm_obj, fk, targets, poles, drop=body)
            drop = _foot_floor(mesh_obj, arm_obj, side) - floor[side]
            targets["ik_foot_" + side].z -= drop
            if abs(drop) < 0.0005:
                break
    pose(arm_obj, fk, targets, poles, drop=body)
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


# Saud faces -Y. Both stances are written as one side plus its mirror, then
# the asymmetry that makes it a fighting stance is layered on top.
GUARD = dict(
    _mirror({
        # Elbows down and forward, not hanging straight from the shoulder:
        # upper arm 0.336 m and forearm+hand 0.338 m together cannot reach a
        # chin 0.461 m above a shoulder-drop elbow (checked -- with the old
        # (0.16,-0.10,-0.98) the fist bottomed out at chest height, 1.36-1.40 m
        # against a chin near 1.57-1.67 m). The old numbers also read as
        # correct on paper -- "elbows down, tight to the ribs" is still true
        # of these -- the fix was moving the elbow's drop into -Y, forward,
        # not sideways: a forward elbow still reads as tucked, a sideways one
        # reads as flared (checked -- x .42 got the height but looked like a
        # chicken wing). This puts the fist at 1.51 m, by the jaw.
        # (Superseded 2026-09-24 by the solved guard below: measured, those
        # aims put both fists 15 cm under the head and as wide as the
        # shoulders, the elbows 5 cm OUTSIDE them, the forearms straight up
        # and the thumbs pointing down -- hands up beside the head, not a
        # guard. The arms are set per side after this.)
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
    # Solved 2026-09-26 ("make leg improve position") with the hips bladed
    # 25 degrees: the lead foot flat and pointed at the opponent, the rear
    # foot turned out 40 degrees with its heel up, knees at 22, the weight
    # 5 cm back of the feet's middle. Every stance is solved the same way
    # (STANCES in the scratch solver -> these tables).
    "thigh_l": (0.116, -0.376, -0.919), "calf_l": (0.126, -0.002, -0.992),
    "thigh_r": (-0.123, -0.117, -0.986), "calf_r": (-0.119, 0.264, -0.957),
    "foot_l": (-0.080, -0.960, -0.270), "foot_r": (-0.580, -0.720, -0.380),
    "twist:pelvis": -0.440,
})
# The arms: a boxer's high guard, solved rather than guessed (2026-09-24,
# asked as "the best position for arm and hand"). Each arm is a two-bone
# solve on Saud's own skeleton for where the fist and the elbow should be,
# measured from the base of the skull (the head bone's head, H):
#   rear (right) fist at the jaw   -- 8.5 cm across, 19 cm in front of H,
#                                     10.5 cm under it
#   lead (left) fist at the cheek, further out -- 9.5 cm across, 36 cm in
#                                     front, 10 cm under
#   elbows down in front of the ribs, inside the shoulders (x 0.11-0.14
#                                     against 0.20), at 1.23-1.25 m
#   wrists straight: the knuckles carry on the forearm's line, a little
#                                     further forward (17-20 degrees)
# The forearm here is short against the upper arm (0.263 m to 0.336), so a
# fist at the jaw needs the elbow raised forward and the forearm near
# upright -- which is how a real high guard stands. The lead and rear are
# different, as they are in a fighter: this is not a mirror.
GUARD.update({
    "upperarm_l": (-0.104, -0.802, -0.588), "lowerarm_l": (-0.145, 0.007, 0.989), "hand_l": (-0.139, -0.281, 0.949),
    "upperarm_r": (0.191, -0.753, -0.630), "lowerarm_r": (0.103, -0.044, 0.994), "hand_r": (0.097, -0.326, 0.940),
})
# Which way each palm faces: back at his own face and a little in, so the
# knuckles face the man in front of him. Not a bone: roll_palm() turns the
# hand about its own length to it once the hand is aimed. Without it the
# hand kept whatever roll swinging its A-pose frame onto the aim left it
# with, and that showed the palms -- the fingers' curled fronts -- to the
# opponent.
GUARD.update({"palm_l": (-0.447, 0.894, 0.0), "palm_r": (0.447, 0.894, 0.0)})
PALMS = ("palm_l", "palm_r")

# Saud's own guard: a mixed martial artist's, not a boxer's (2026-09-25,
# asked as "scan any real MMA fight then make Saud the same position", Saud
# only -- every other man keeps GUARD). Nothing was watched: it is the
# stance as published by MMA coaches (Evolve MMA, Drew Dober, Lowkick MMA,
# Apex MMA, Fight Encyclopedia, Dynamic Striking), solved on his own
# skeleton for what they agree on. Against GUARD, measured on the rig:
#   feet about shoulder-width across, one staggered 30-46 cm ahead
#                         -- 42 cm across and 38 ahead (GUARD 38 and 31)
#   knees bent 30-45 degrees, hips low -- both at 38 (GUARD 8 lead, 26 rear)
#   weight about 50/50 -- the pelvis over the middle of the feet (GUARD
#                         carried it 6 cm back, over the rear foot)
#   hands at chin height but further from the face, the lead extended
#                         -- lead fist 44 cm in front of the skull's base,
#                         rear 28 (GUARD 36 and 19), both 10 cm under it
#   elbows slightly out -- 16-17 cm off the middle against shoulders at 20
#                         (GUARD 11-14): out, still inside the shoulders
#   chin tucked, back straight -- the neck and head a little further down
#                         and forward
# Squarer hips than a boxer's comes from that width: the feet are set
# across as well as ahead, not in a line. The rear foot turns 18 degrees
# out, where GUARD pointed it straight ahead.
# That stance as it stood until 2026-09-28 is the table below (its legs
# re-solved 2026-09-26: the rear foot turned out 30 degrees, the hips
# bladed 15). Kept, and used by nothing that builds: build_motion --bite "upright" stands him on it to
# prove the stance check below knows the difference. Measured on the rig
# (rig_full_ik.stance, measure_stance): torso 3.5 degrees forward, neck 8,
# the head pitched 6.8 down with its joint 13.4 cm BEHIND the lead ankle,
# the shoulders 23.3/22.6 cm under the head joint (no shrug), weight 50/50,
# hips bladed 14.9 -- upright and passive, the author's word for it was
# "more aggressive".
MMA_GUARD_2026_09_26 = dict(GUARD)
MMA_GUARD_2026_09_26.update(
    spine_01=(0.000, -0.080, 1.000),
    spine_02=(0.000, -0.100, 1.000),
    spine_03=(0.000, -0.060, 1.000),
    neck_01=(0.000, -0.140, 1.000),
    head=(0.000, -0.120, 1.000),
    thigh_l=(0.127, -0.509, -0.851),
    calf_l=(0.147, 0.129, -0.981),
    thigh_r=(-0.147, -0.132, -0.980),
    calf_r=(-0.128, 0.506, -0.853),
    foot_l=(-0.050, -0.960, -0.270),
    foot_r=(-0.480, -0.820, -0.320),
    upperarm_l=(-0.089, -0.850, -0.519),
    lowerarm_l=(-0.187, -0.314, 0.931),
    hand_l=(-0.166, -0.543, 0.823),
    upperarm_r=(0.085, -0.812, -0.577),
    lowerarm_r=(0.199, -0.175, 0.964),
    hand_r=(0.182, -0.435, 0.882),
    palm_l=(-0.150, 1.000, 0.000),
    **{"twist:pelvis": -0.260},   # the hips bladed 15 degrees; a boxer's are 25
)

# Saud's stance since 2026-09-28 (Unreal build only -- the browser draws its
# own guard and none of these numbers is its): asked as "make Saud more
# aggressive", the same MMA stance hunted forward. The head forward and down
# over the lead foot, the chin tucked, the shoulders shrugged up round the
# jaw and rolled in, more knee, the weight forward, more blade, the rear hand
# at the cheek and the lead long. It is SOLVED, not typed: MMA_SOLVE holds
# the targets and the scratch solver that turned them into the aims below
# did it the way every stance here is solved (the legs by two-bone geometry
# from where the feet stand, the lead knee's bend and where the weight is;
# the spine and neck as forward angles; the arms as a two-bone solve per
# side, on this skeleton, for a fist placed in the head's own frame). The
# clavicles are aimed for the first time in any stance: the shrug and the
# roll, turned into the chest's bladed frame (which also switches on the
# clavicle aims build_motion's Jab, Cross and Hook always carried: aims_at
# blends only the bones a guard names).
#
# Measured on the rig (rig_full_ik.stance), before -> after: head joint
# 1.601 -> 1.580 m, 13.4 cm behind the lead ankle -> 1.1; head 5.6 -> 14.4 cm
# ahead of the pelvis; head pitch 6.8 -> 14.1 degrees down; neck 8 -> 26;
# torso 3.5 -> 7.8; shoulders 23.3/22.6 -> 18.8/17.4 cm under the head joint;
# hips bladed 14.9 -> 20.1; knees 38.0/45.3 -> 42.0/47.5; weight on the lead
# 0.50 -> 0.60; feet 49/40 -> 40/42 cm (across/stagger); fists in the head
# frame lead 44.9 fwd -> 42.0, rear 29.0 -> 18.0; both soles on the floor.
# Two budgets bound it, both from the pairs (build_motion / motion_hits):
# spine_02 no lower than 1.190 m (the Boss Special's chest mark) and the
# pelvis no lower than 0.883, which is what caps the lead knee at 42; the
# head dropped 2.1 cm, which the pairs allow only because punches now land
# on the chin of the man they are thrown at (build_motion.VICTIM_CHIN).
# The stance as it stood 2026-09-28 to 2026-09-30, verbatim, kept the way
# MMA_GUARD_2026_09_26 is kept -- used by nothing that builds. rig_full_ik.py
# --bite's stance cases swap ONE bone group of it at a time into the stance
# below, so each key of MMA_SPEC is proved to read its own bones; build_motion
# --bite "craned" stands Saud on the whole of it. Measured on the rig
# (measure_posture, 2026-09-28): the chest bent 12 degrees at spine_03 with
# the skull 11.9 EXTENDED on a neck bent 26 -- a craned neck with the chin
# poked out, not a tucked chin; the rear wrist bent 16.5; the lead fist 5.8
# cm under the chin; the lead shoulder 1.3 cm under the rear; the soles
# rolled 5.8 (lead) and 20.4 (rear) degrees about the foot's length; the
# rear knee 18.7 cm inside the vertical plane through its foot's axis (a 43
# degree twist between shin and foot). Its MMA_SOLVE: spine (6, 10, 22),
# neck 26, head 14, foot_pitch (15.7, 23.0), clavicle_shrug 0.18 both sides,
# fists l (0.100, -0.06, 0.42), hand_tilt r 0.30.
MMA_GUARD_2026_09_28 = dict(GUARD)
MMA_GUARD_2026_09_28.update(
    spine_01=(0.000, -0.104, 0.995),
    spine_02=(0.000, -0.174, 0.985),
    spine_03=(0.000, -0.375, 0.927),
    neck_01=(0.000, -0.438, 0.899),
    head=(0.000, -0.242, 0.970),
    thigh_l=(0.032, -0.495, -0.868),
    calf_l=(0.069, 0.213, -0.975),
    foot_l=(-0.084, -0.959, -0.271),
    thigh_r=(-0.242, -0.099, -0.965),
    calf_r=(-0.009, 0.551, -0.835),
    foot_r=(-0.528, -0.754, -0.391),
    clavicle_l=(0.859, -0.477, 0.184),
    clavicle_r=(-0.965, 0.189, 0.184),
    upperarm_l=(-0.101, -0.637, -0.764),
    lowerarm_l=(-0.104, -0.491, 0.865),
    hand_l=(-0.098, -0.613, 0.784),
    upperarm_r=(0.260, -0.711, -0.653),
    lowerarm_r=(0.118, -0.112, 0.987),
    hand_r=(0.117, -0.389, 0.914),
    palm_l=(-0.100, 1.000, 0.000),
    palm_r=(0.450, 0.890, 0.000),
    **{"twist:pelvis": -0.350},   # the hips bladed 20 degrees
)

# Saud's stance since 2026-09-30 ("make full suad aligment make body imrove
# steps and Posture body and arm"): the same aggressive MMA stance, aligned
# and posed as the coaches say. Re-solved by the scratch solver
# (saud_align/posture/solve_mma.py, the 09-28 method: the spine, neck and
# head as forward angles; the clavicles in the bladed chest frame; the feet
# from yaw and pitch; the legs by two-bone geometry from where the feet
# stand, the knee over the toes; the arms as a two-bone solve per side for a
# fist placed in the head's own frame; the palms rolled), every target
# measured on the rig through rig_full_ik.stance_check. What moved, and why,
# measured on the rig 09-28 -> 09-30:
#   the chin: the chest bend at spine_03 12 -> 6 degrees (spine 6/10/22 ->
#     8/12/18), the neck 26 -> 15, the head 14 -> 16: the skull on the neck
#     -11.9 (extended: a craned neck, the chin poked out) -> +1.0 (nodded;
#     rest is -9), the face pitched 14.1 -> 16.0 down, the head joint 1.577
#     -> 1.590 m and 3.2 cm behind the lead ankle (was 1.1; the two extra
#     degrees at spine_01/02 keep it forward: at 7/11 it was 4.1 behind).
#     Neck 15, not 14, so the stance bite that puts the 09-28 head (14)
#     under the new neck misses skull_on_neck by a degree, not by the 0.02
#     the blade's counter-turn adds; head 16, not 17, keeps the lead fist
#     41 cm out (at 17 it had to come in to 38.8 to stay at the chin)
#   the rear wrist: hand_tilt r 0.30 -> 0.18, the bend 16.5 -> 10.3 degrees
#   the lead fist: up -0.06 -> +0.03 in the head frame and forward 0.42 ->
#     0.412 (solved to the WORLD chin, CHIN_UNDER_HEAD under the head joint):
#     5.8 cm under the chin -> 1.5 over it, 41.2 cm out (the rear 3.2 over,
#     18 out, unchanged)
#   level shoulders: the shrug split 0.18/0.18 -> 0.242/0.118 (the total
#     kept): a bladed chest pitched forward lowers the lead clavicle's root
#     by sin(blade) x sin(pitch) x its half-spacing, 1.3 cm at 20 and 22
#     degrees -- the lead shoulder joint 1.3 cm under the rear -> 0.7 over
#   the lead foot flat: pitch 15.7 -> 16.33, the rest's own (0.6 degrees
#     toe-up had its heel corner 2.7 mm under the shoe's lowest vertex)
#   the soles level and the knees over the toes are the two switches below
#     ("soles", "knee_pole"), not aims: the sole roll 5.8/20.4 -> 0/0
#     degrees, the rear knee 18.7 cm inside its foot's line -> 5.4 (the shin
#     15 degrees inside the foot's heading, an adult's tibial torsion); the
#     thigh_r/calf_r aims are typed from that solve so the FK and the IK
#     agree (the FK guard used to hover with its rear knee 13 cm further in)
#   with the soles level the rear foot stands 1.5 cm lower than on its
#     rolled corner: the rear knee 47.5 -> 43.6, the rear heel 4.85 -> 3.34
#     cm over the lead (coaches 2-4); the pelvis 0.883, spine_02 1.194 --
#     the pair budgets held; weight 0.60, hips 20, knees 42/43.6, feet 40/42
MMA_SOLVE = dict(
    twist=-0.35,                    # the pelvis, radians (-0.35 is 20 degrees of blade)
    feet_across=0.40, feet_stagger=0.42,          # ball to ball, metres
    foot_yaw=(-5.0, -35.0),         # lead 5 degrees in, rear 35 out
    foot_pitch=(16.33, 23.0),       # lead flat (the rest's own pitch, J foot->ball), rear heel up
    lead_knee=42.0, weight_lead=0.60,
    knee_twist=15.0,                # the shin's heading inside the foot's, degrees (knee_pole; tibial torsion 15-20)
    spine=(8.0, 12.0, 18.0),        # spine_01/02/03, degrees forward: the chest bend 6, no hunch
    neck=15.0, head=16.0,           # the neck near the torso line, the skull nodded 1 on it (skull_on_neck; rest -9)
    clavicle_roll=0.15, clavicle_shrug=(0.242, 0.118),    # in the chest's own (bladed) frame; the shrug per side (l, r), the joints level
    fists={"l": (0.100, 0.03, 0.412), "r": (-0.070, -0.02, 0.18)},  # head frame: across, up, forward (m); the lead solved to +1.5 cm over the chin
    elbow_poles={"l": (0.0, -0.1, -1.0), "r": (-0.2, 0.3, -1.0)},
    hand_tilt={"l": 0.15, "r": 0.18},   # radians the hand tilts forward off the forearm (the wrist bend, under 15 degrees)
    palms=((-0.10, 1.0, 0.0), (0.45, 0.89, 0.0)),
)
MMA_GUARD = dict(GUARD)
MMA_GUARD.update(
    spine_01=(0.000, -0.139, 0.990),
    spine_02=(0.000, -0.208, 0.978),
    spine_03=(0.000, -0.309, 0.951),
    neck_01=(0.000, -0.259, 0.966),
    head=(0.000, -0.276, 0.961),
    thigh_l=(0.024, -0.495, -0.869),
    calf_l=(0.077, 0.212, -0.974),
    foot_l=(-0.084, -0.956, -0.281),
    thigh_r=(-0.421, 0.001, -0.907),
    calf_r=(0.168, 0.452, -0.876),
    foot_r=(-0.528, -0.754, -0.391),
    clavicle_l=(0.852, -0.465, 0.240),
    clavicle_r=(-0.973, 0.197, 0.118),
    upperarm_l=(-0.136, -0.762, -0.633),
    lowerarm_l=(-0.078, -0.306, 0.949),
    hand_l=(-0.073, -0.445, 0.893),
    upperarm_r=(0.308, -0.722, -0.620),
    lowerarm_r=(0.070, -0.027, 0.997),
    hand_r=(0.068, -0.205, 0.976),
    palm_l=(-0.100, 1.000, 0.000),
    palm_r=(0.450, 0.890, 0.000),
    **{"twist:pelvis": -0.350},   # the hips bladed 20 degrees
)
# The two switches that key every Saud-only mechanism in the shared pose
# code (rig_full_ik.stance, limb_targets, build_motion.planted_pole,
# motion_ik.capture_guard). Strings, so nothing sums or slerps them; absent
# from every other stance dict, so every other man's feet and knees are
# posed exactly as before (2026-09-30):
#   "soles": "level"    -- each PLANTED foot is rolled about its own length
#                          until its sole is level (roll_sole) wherever it is
#                          planted, never in the aim; a kicking foot, a foot
#                          in the air and every other man's feet never see it
#   "knee_pole": "foot" -- a planted knee's pole is knee_pole()'s, over the
#                          toes, not the straight-forward one
MMA_GUARD["soles"] = "level"
MMA_GUARD["knee_pole"] = "foot"
# What the stance has to be, held by build_motion.verify on A_Saud_Guard's
# first frame through measure_stance. Each is the INTENT of the stance or
# one of the pair budgets above, as (low, high); None is open. Measured on
# that frame (the clip, not the rig: the clip is struck at his set's stance
# factor, 1.031 wider, and grounded on the balls, which straightens the
# rear knee -- 41.0 in the clip where the rig stands it at 47.5; the old
# stance's clip had 34.8/38.0 where its rig had 38.0/45.3): head -1.1 cm
# over the lead ankle, pitched 14.1, shoulders 18.8/17.4 under the head
# joint, weight 0.60, knees 42.0/41.0, hips 20.1, head 1.577 m, spine_02
# 1.193 m. The old stance's first frame misses eight of these (build_motion
# --bite "upright").
MMA_SPEC = {
    "head_over_lead_ankle": (-6.0, 6.0),     # the head over the lead foot, not behind it
    "head_pitch": (10.0, 20.0),              # the chin tucked, looking out from under the brow
    "sh_l_under_head": (None, 21.0),         # the shoulders shrugged up round the jaw
    "sh_r_under_head": (None, 21.0),
    "weight_lead": (0.55, 0.65),             # forward, not 50/50
    "knee_l": (40.0, None),                  # sat down in the stance
    "knee_r": (40.0, None),
    "hips_blade": (17.0, 23.0),              # bladed more than 15, less than a boxer's 25
    "head_z": (1.56, None),                  # the pair budgets
    "spine02_z": (1.190, None),
    # 2026-09-30, "make full suad aligment ... Posture body and arm" (the
    # coaching cues: chin tucked, back straight, wrists straight, hands at
    # chin height with the lead extended, level shoulders; alignment: the
    # knees over the toes, the soles on the floor). Each measured on the rig
    # first (measure_posture): the 09-28 stance misses every one of them.
    "chest_bend": (None, 8.0),               # was 12: a hunch at the upper back
    "skull_on_neck": (0.0, 15.0),            # was -11.9: the skull extended on a craned neck; 0 is 9 deg of nod from rest
    "wrist_l": (None, 15.0),                 # was 8.4
    "wrist_r": (None, 15.0),                 # was 16.5
    "fist_l_over_chin": (-1.0, 4.0),         # was -5.8 cm: the lead hand at the collar
    "fist_r_over_chin": (1.0, 6.0),          # was +3.5 (the cheek), kept
    "shoulders_level": (-0.5, 2.0),          # was -1.3 cm: the lead shoulder dropped
    "sole_roll_l": (-2.0, 2.0),              # was 5.8 deg: the aim's shortest arc rolled the sole
    "sole_roll_r": (-2.0, 2.0),              # was 20.4
    "knee_off_foot_line_l": (-8.0, 3.0),     # was -1.6 cm (the lead was fine)
    "knee_off_foot_line_r": (-8.0, 3.0),     # was -18.7: the rear knee 18.7 cm inside its foot's line
    "rear_heel": (2.0, 4.5),                 # was rig 4.85 / clip 1.95: a rolled sole grounded on its corner; coaches 2-4
}
MMA_SPEC["knee_r"] = (40.0, 46.0)            # was (40, None): rig 47.5 / clip 41.0, the same rolled sole; coaches 30-45
# Keys of the same shape that the RIG-side stance check (rig_full_ik.
# stance_check, --stance, --bite) applies with MMA_SPEC from day one, and
# that build_motion.verify does not apply to the clip yet: each waits on a
# mechanism of the clip side (the STEPS track's gates G1/G2, 2026-09-30) and
# moves into MMA_SPEC when that mechanism is in. Empty when nothing waits:
# both gates opened the day they were written (build_motion.planted_pole
# calls knee_pole -- G1; motion_ik.capture_guard grounds the sole -- G2), so
# knee_off_foot_line_*, rear_heel and knee_r's upper bound are in MMA_SPEC.
MMA_SPEC_PENDING = {}


# The bosses' own stances (2026-09-25, "posture and stance": how each man
# stands). Each is solved on Saud's skeleton the way MMA_GUARD is -- feet,
# knees, fists and elbows placed, the aims read back -- and every one is
# held to build_motion.hands_check's guard rules when its Guard clip is
# built (fists up in front of the face, elbows inside the shoulders, wrists
# straight, palms in). What each one is comes from the roster: AL-SAQR is
# the Kicker archetype, the fastest man in the game; AL-WAHSH the boxer-
# boss with the best guard chance in the table; ZAYOS the man who only ever
# punches, half again everyone's size and the slowest.
def _stance(**kw):
    g = dict(GUARD); g.update(kw); return g

# a kickboxer's: upright, the weight held back off a light lead leg, the
# lead hand long at brow height, the rear foot turned out
KICKBOXER_GUARD = _stance(
    spine_01=(0.000, -0.040, 1.000),
    spine_02=(0.000, -0.060, 1.000),
    spine_03=(0.000, -0.040, 1.000),
    neck_01=(0.000, -0.120, 1.000),
    head=(0.000, -0.100, 1.000),
    foot_l=(-0.050, -0.950, -0.300),
    foot_r=(-0.550, -0.740, -0.380),
    palm_l=(-0.200, 1.000, 0.000),
    palm_r=(0.447, 0.894, 0.000),
    thigh_l=(0.105, -0.382, -0.918),
    calf_l=(0.114, 0.027, -0.993),
    thigh_r=(-0.112, -0.111, -0.988),
    calf_r=(-0.107, 0.303, -0.947),
    upperarm_l=(-0.127, -0.861, -0.492),
    lowerarm_l=(-0.107, -0.123, 0.987),
    hand_l=(-0.100, -0.392, 0.915),
    upperarm_r=(0.165, -0.820, -0.547),
    lowerarm_r=(0.115, -0.227, 0.967),
    hand_r=(0.104, -0.476, 0.873),
    **{"twist:pelvis": -0.440},
)
# a peek-a-boo crouch: knees at 44 degrees, the torso folded forward, both
# fists tight at the cheekbones with the elbows on the ribs, chin down
PEEKABOO_GUARD = _stance(
    spine_01=(0.000, -0.140, 0.990),
    spine_02=(0.000, -0.220, 0.970),
    spine_03=(0.000, -0.200, 0.980),
    neck_01=(0.000, -0.180, 0.980),
    head=(0.000, -0.160, 0.990),
    foot_l=(-0.080, -0.960, -0.270),
    foot_r=(-0.550, -0.740, -0.380),
    palm_l=(-0.447, 0.894, 0.000),
    palm_r=(0.447, 0.894, 0.000),
    thigh_l=(0.124, -0.520, -0.845),
    calf_l=(0.141, 0.220, -0.965),
    thigh_r=(-0.141, -0.223, -0.965),
    calf_r=(-0.124, 0.516, -0.847),
    upperarm_l=(-0.417, -0.835, -0.359),
    lowerarm_l=(0.135, 0.378, 0.916),
    hand_l=(0.146, 0.084, 0.986),
    upperarm_r=(0.310, -0.785, -0.537),
    lowerarm_r=(0.014, -0.111, 0.994),
    hand_r=(0.013, -0.382, 0.924),
    **{"twist:pelvis": -0.440},
)
# a heavy puncher's: square and wide (feet 50 cm across), knees barely
# bent, the shoulders rolled forward, the fists a hand lower than a boxer
# carries them and the elbows out
HEAVY_GUARD = _stance(
    spine_01=(0.000, -0.050, 1.000),
    spine_02=(0.000, -0.100, 1.000),
    spine_03=(0.000, -0.160, 0.990),
    neck_01=(0.000, -0.140, 1.000),
    head=(0.000, -0.100, 1.000),
    foot_l=(0.000, -0.960, -0.280),
    foot_r=(-0.420, -0.850, -0.320),
    palm_l=(-0.400, 0.900, 0.000),
    palm_r=(0.400, 0.900, 0.000),
    thigh_l=(0.177, -0.311, -0.934),
    calf_l=(0.186, 0.033, -0.982),
    thigh_r=(-0.186, -0.035, -0.982),
    calf_r=(-0.177, 0.309, -0.934),
    upperarm_l=(-0.119, -0.682, -0.721),
    lowerarm_l=(-0.135, -0.116, 0.984),
    hand_l=(-0.125, -0.387, 0.914),
    upperarm_r=(0.124, -0.633, -0.764),
    lowerarm_r=(0.137, -0.225, 0.965),
    hand_r=(0.124, -0.474, 0.872),
    **{"twist:pelvis": -0.200},
)
# The bosses' planted knees over their toes too (2026-10-03, "improve all
# bosses' fight style ik"): straight forward, the turned-out rear foot of
# each boss stance had its knee 31 degrees inside its toes in the guard and
# up to 42 in a step. "track" is knee_track_pole's knee, the bend along the
# foot's own heading across the hip-to-ankle line: knee_pole's (Saud's
# "foot") reads the shin from above, and on ZAYOS's wide stance, whose legs
# slant out, that put the rear knee 49 degrees OUTSIDE its toes. Their
# soles are left as they were.
for _g in (KICKBOXER_GUARD, PEEKABOO_GUARD, HEAVY_GUARD):
    _g["knee_pole"] = "track"
GUARDS = {"boxer": GUARD, "mma": MMA_GUARD, "kickboxer": KICKBOXER_GUARD,
          "peekaboo": PEEKABOO_GUARD, "heavy": HEAVY_GUARD}
STANCE_OF = {"saud": "mma", "saqr": "kickboxer", "boss": "peekaboo", "zayos": "heavy"}


def guard_for(name):
    """The guard a man stands in: his own (STANCE_OF), else the boxer's."""
    return GUARDS[STANCE_OF.get(str(name).lower(), "boxer")]


# The chin: this far under the head joint, which is at the eye line on this
# skeleton. build_motion.CHIN_UNDER_HEAD is the same number (the punches'
# landing height); measure_stance reads it here so the stance check and the
# landings agree on where the chin is.
CHIN_UNDER_HEAD = 0.10


def foot_aim(yaw_deg, pitch_deg):
    """A foot's aim from where it points: `yaw_deg` off straight ahead (-Y),
    + toward his left (+X), and `pitch_deg` down from level. The rest foot
    (J["foot"] to J["ball"]) is pitched 15.7 with the sole flat, so a flat
    foot's aim is foot_aim(yaw, 15.7); MMA_SOLVE's foot_yaw / foot_pitch are
    read through this."""
    p, y = math.radians(pitch_deg), math.radians(yaw_deg)
    return (math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), -math.sin(p))


def measure_stance(arm_obj):
    """What a stance IS, read off the posed bones alone (no mesh), so the
    rig file posed through rig_full_ik.stance, the pipeline's limb_targets
    and a baked clip frame are all measured the same way. The man faces -Y
    and +X is his left; lengths are cm unless named _z (metres), angles
    degrees. Fists, elbows and wrists are measured the way build_motion.
    hands_check measures them: in the head bone's own frame (its X across,
    its Y up the neck, its Z the way the face looks)."""
    import rig_full_ik as CR
    pb, W = arm_obj.pose.bones, arm_obj.matrix_world

    def P(n, tail=False):
        return W @ (pb[n].tail if tail else pb[n].head)

    def yaw_of(a, b):
        d = P(a) - P(b)
        return math.degrees(math.atan2(-d.y, d.x))

    o = {}
    ball = {s: P("ball_" + s) for s in "lr"}
    ank = {s: P("foot_" + s) for s in "lr"}
    pel, h = P("pelvis"), P("head")
    o["pelvis_z"], o["spine02_z"], o["head_z"] = pel.z, P("spine_02").z, h.z
    o["feet_across"] = (ball["l"].x - ball["r"].x) * 100.0
    o["feet_stagger"] = (ball["r"].y - ball["l"].y) * 100.0
    ab = (ank["l"] - ank["r"]).to_2d()
    # 0 all on the rear foot, 1 all on the lead: the pelvis between the ankles
    o["weight_lead"] = (pel - ank["r"]).to_2d().dot(ab) / ab.length_squared
    for s in "lr":
        th = P("calf_" + s) - P("thigh_" + s)
        ca = P("foot_" + s) - P("calf_" + s)
        o["knee_" + s] = math.degrees(th.angle(ca))
        f = ball[s] - ank[s]
        o["footyaw_" + s] = math.degrees(math.atan2(f.x, -f.y))
        o["heel_" + s] = CR._toe_and_heel(arm_obj, None, s)[1] * 100.0
    o["rear_heel"] = o["heel_r"] - o["heel_l"]
    v = P("neck_01") - pel
    o["torso_fwd"] = math.degrees(math.atan2(-v.y, v.z))
    v = h - P("neck_01")
    o["neck_fwd"] = math.degrees(math.atan2(-v.y, v.z))
    # The chin (2026-09-30): each bone's own forward pitch (its Y, in
    # armature space), and the bends between them. The stance of 09-28 bent
    # the chest 12 degrees at the spine_03 joint with the skull 11.9
    # EXTENDED on a neck bent 26 -- a craned neck with the chin poked out,
    # the eyes on the opponent only because the face pitched 14 down. A
    # tucked chin is the other way about: the neck near the torso line and
    # the skull nodded on it (skull_on_neck at rest is -9.0: the face looks
    # 3.7 up; 0 here is 9 degrees of nod from rest).
    def pitch(n):
        d = P(n, tail=True) - P(n)
        return math.degrees(math.atan2(-d.y, d.z))
    o["chest_bend"] = pitch("spine_03") - pitch("spine_02")
    o["skull_on_neck"] = pitch("head") - pitch("neck_01")
    # level shoulders: the lead (left) shoulder joint's height over the rear's
    o["shoulders_level"] = (P("upperarm_l").z - P("upperarm_r").z) * 100.0
    for s in "lr":
        H, K, A, B = P("thigh_" + s), P("calf_" + s), ank[s], ball[s]
        # the knee against the vertical plane through the foot's own axis
        # (ankle toward ball, seen from above): its signed distance, + away
        # from the other foot; and the shin's heading against the foot's.
        # An adult's tibia turns out 15-20 degrees, no more (knee_pole).
        a = Vector((B.x - A.x, B.y - A.y, 0.0)).normalized()
        n = Vector((-a.y, a.x, 0.0))
        other = ank["r" if s == "l" else "l"]
        if (other - A).dot(n) > 0.0:
            n = -n
        o["knee_off_foot_line_" + s] = (K - A).dot(n) * 100.0
        sh = Vector((K.x - A.x, K.y - A.y, 0.0))
        o["shin_twist_" + s] = math.degrees(sh.angle(a)) if sh.length > 1e-6 else 0.0
        # the sole's roll about the foot's length: the foot's rest-up (the
        # sole's normal at rest) as the posed bone carries it, against world
        # up, both projected off the foot's axis (the alignment scout's
        # decomposition); an aim's shortest arc left the rear sole 20.4
        # degrees over (2026-09-28)
        fb = pb["foot_" + s]
        up = (W @ fb.matrix).to_3x3() @ (fb.bone.matrix_local.to_3x3().inverted() @ Vector((0.0, 0.0, 1.0)))
        ax = (B - A).normalized()
        nn = up - ax * up.dot(ax); v = Vector((0.0, 0.0, 1.0)) - ax * ax.z
        roll = 0.0
        if nn.length > 1e-9 and v.length > 1e-9:
            nn.normalize(); v.normalize()
            roll = math.degrees(math.atan2(ax.dot(v.cross(nn)), v.dot(nn)))
        o["sole_roll_" + s] = roll
    hm = (W @ pb["head"].matrix).to_3x3()
    fwd = Vector((hm[0][2], hm[1][2], hm[2][2])).normalized()
    o["head_pitch"] = math.degrees(math.asin(max(-1.0, min(1.0, -fwd.z))))     # + looks down
    o["head_yaw"] = math.degrees(math.atan2(fwd.x, -fwd.y))
    o["head_over_lead_ankle"] = -(h.y - ank["l"].y) * 100.0                    # + ahead of it
    o["head_ahead_pelvis"] = -(h.y - pel.y) * 100.0
    o["hips_blade"] = yaw_of("thigh_l", "thigh_r")
    o["shoulders_blade"] = yaw_of("upperarm_l", "upperarm_r")
    Hm = (W @ pb["head"].matrix).inverted()
    for s in "lr":
        o["sh_%s_under_head" % s] = (h.z - P("upperarm_" + s).z) * 100.0
        fist = P("hand_" + s, tail=True)
        loc = Hm @ fist
        o["fist_%s_fwd" % s], o["fist_%s_across" % s], o["fist_%s_up" % s] = loc.z * 100.0, abs(loc.x) * 100.0, loc.y * 100.0
        # ...and in the WORLD, over the chin -- the chin build_motion lands
        # punches on, CHIN_UNDER_HEAD under the head joint (the eye line).
        # A head-frame height is not a chin height: the 09-28 lead fist at
        # -6 "up" in a head pitched 14 down sat 5.8 cm under the chin.
        o["fist_%s_over_chin" % s] = (fist.z - (h.z - CHIN_UNDER_HEAD)) * 100.0
        el, sh = P("lowerarm_" + s), P("upperarm_" + s)
        o["elbow_%s_margin" % s] = (abs((Hm @ sh).x) - abs((Hm @ el).x)) * 100.0
        fa = (P("lowerarm_" + s, True) - el).normalized()
        hd = (fist - P("hand_" + s)).normalized()
        o["wrist_" + s] = math.degrees(fa.angle(hd))
        m = (W @ pb["hand_" + s].matrix).to_3x3()
        o["palm_" + s] = (m @ palm_local(arm_obj, s)).normalized().y
    return o


def stance_misses(measured, spec):
    """Each (name, value, lo, hi) of `measured` outside `spec`'s range."""
    out = []
    for k, (lo, hi) in spec.items():
        v = measured[k]
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            out.append((k, v, lo, hi))
    return out

# The fist. The mesh is built as a loose fist (anatomy.hand: 72/109/36
# degrees) with the thumb laid along the index finger, and a hand posed at
# that rest reads as a claw with the thumb out -- in every render and every
# clip until 2026-09-24, because nothing ever closed it (the clips never
# posed a finger; the renders tightened it 10 degrees a joint). Closed is
# these, found by rendering the hand from three sides: each finger's three
# joints turned this much further toward the palm, and the thumb's three
# folded across the front of the fingers -- (x, y, z) closing magnitudes in
# each bone's own frame, applied with the side's closing sign.
FIST_CURL = (30.0, 30.0, 22.0)
FIST_THUMB = ((25.0, 0.0, 30.0), (45.0, 0.0, 10.0), (30.0, 0.0, 0.0))
FINGERS = ("index", "middle", "ring", "pinky")


def palm_local(arm_obj, side):
    """The palm's direction in the hand bone's own rest frame: from the
    middle of the hand to the middle finger's second joint, across the
    hand's length. Read once off the rest, so it does not move with the
    fingers."""
    bones = arm_obj.data.bones
    h = bones["hand_" + side]
    p = bones["middle_02_" + side].head_local - (h.head_local + h.tail_local) * 0.5
    ax = (h.tail_local - h.head_local).normalized()
    p = (p - ax * p.dot(ax)).normalized()
    return h.matrix_local.to_3x3().inverted() @ p


def _roll_about(pbone, local_vec, want, target=None):
    """Turn `pbone` (or `target`, a control that carries its frame) about
    pbone's own length until `local_vec` -- a direction in pbone's REST
    frame, carried by its current matrix -- faces `want` as nearly as that
    length allows. Armature space, like every aim here. Returns the angle
    turned (radians). The one roll every hand and foot here is levelled
    with: roll_palm (the palm to the opponent, 2026-09-24) and roll_sole
    (the sole to the floor, 2026-09-30) are two calls to it."""
    m = pbone.matrix.to_3x3()
    ax = Vector((m[0][1], m[1][1], m[2][1])).normalized()
    cur = m @ Vector(local_vec)
    w = Vector(want)
    cur = cur - ax * cur.dot(ax)
    w = w - ax * w.dot(ax)
    if cur.length < 1e-6 or w.length < 1e-6:
        return 0.0
    cur.normalize(); w.normalize()
    ang = cur.angle(w)
    if ax.dot(cur.cross(w)) < 0.0:
        ang = -ang
    target = target or pbone
    tm = target.matrix.copy(); at = tm.translation.copy()
    target.matrix = Matrix.Translation(at) @ Matrix.Rotation(ang, 4, ax) @ Matrix.Translation(-at) @ tm
    bpy.context.view_layer.update()
    return ang


def roll_palm(arm_obj, side, want, pbone=None):
    """Turn the hand (or `pbone`, a control that carries its frame) about
    the hand's own length until its palm faces `want` as nearly as that
    length allows. Armature space, like every aim here."""
    hb = arm_obj.pose.bones["hand_" + side]
    return _roll_about(hb, palm_local(arm_obj, side), want, target=pbone)


def roll_sole(arm_obj, side):
    """Roll foot_<side> about its own length until the sole is level: the
    foot's rest-up (world +Z in the rest, where the sole lies on z = 0),
    carried by the posed bone, is turned back onto world +Z as far as the
    foot's length allows; ball_<side> follows as its child, and the ankle
    and ball joints lie on the axis and do not move. Returns the angle
    (radians). An aim swings a foot onto its direction by the shortest arc
    (pose / rig_full_ik._aim), which for Saud's rear foot -- 35 degrees of
    yaw and 7 of pitch -- rolled the sole 20.4 degrees, the lead's 5.8, in
    the guard and every clip that stands in it (2026-09-28); nothing
    levelled a foot the way roll_palm levels a hand. Called by whoever
    PLANTS a foot (rig_full_ik.stance, limb_targets, motion_ik.
    capture_guard) when the stance asks for "soles": "level", never by
    the aim itself, so a kicking foot keeps its shape. Does nothing when
    "rolled_sole" is in rig_full_ik.SABOTAGE (the sole_roll bites)."""
    import rig_full_ik as CR
    if "rolled_sole" in CR.SABOTAGE:
        return 0.0
    fb = arm_obj.pose.bones["foot_" + side]
    local_up = fb.bone.matrix_local.to_3x3().inverted() @ Vector((0.0, 0.0, 1.0))
    return _roll_about(fb, local_up, Vector((0.0, 0.0, 1.0)))


# The sole's corners, as the shoe has them, measured against the shoe's own
# lowest vertex on Saud's rig with the rest foot pitched and rolled
# (saud_align/posture/sole_probe.py, 2026-09-30): each corner is a joint
# table point (toe_*, heel_*) moved this far FORWARD along the rest foot
# (-Y) and dropped by its height over the floor at rest, where the sole lies
# on z = 0 (the toe point is 2.1 cm up, the heel 3.8). The sole's front edge
# is 2.3 cm past the toe point (its bevel; at J["toe"] itself the model sat
# 3.8 mm high at 10 degrees toe-down, 7.9 at 20 -- 2.3 cm x sin), its heel is
# rounded and meets the floor 1.2 cm ahead of J["heel"] when the heel drops
# (at J["heel"] the model was 2.3 mm low at 10 degrees, 3.6 at 20), and its
# half-width is 4.2 cm (4.5 was 0.6 mm low at 10 degrees of roll, 0.7 at
# 20). With these the model is within 1 mm of the shoe at 10 degrees of
# pitch either way and 20 of roll; rig_full_ik.stance_check holds it
# within 3 on the guard (its "sole model" bite drops the toe's thickness).
SOLE_MODEL = {"toe": (0.023, 0.021), "heel": (0.012, 0.038)}     # (forward, thickness), metres
SOLE_THICK = {k: v[1] for k, v in SOLE_MODEL.items()}            # what the bite sabotages
SOLE_HALF_WIDTH = 0.042


def sole_points(arm_obj, side):
    """The four corners of that foot's sole in world space, as the bones
    carry them: J["toe_<side>"] on ball_<side> and J["heel_<side>"] on
    foot_<side>, each as its offset from the bone's own joint grown with
    the man (rig_full_ik._toe_and_heel's carry, scaled by the head joint's
    height against Saud's), moved forward to the sole's own edge
    (SOLE_MODEL), pushed +/- SOLE_HALF_WIDTH along the foot's carried
    rest-across (X) and dropped by its rest height above the floor along
    the carried rest-up (Z). At rest all four are at z = 0.000 +/- 0.001. Returns [(name, Vector)] with names toe_in, toe_out, heel_in,
    heel_out ("in" toward the other foot). What the clips ground Saud's
    feet on (motion_ik.capture_guard) and what build_motion's sole_on_floor
    reads."""
    pb = arm_obj.pose.bones
    scale = pb["head"].bone.head_local.z / J["head"][0][2]
    out = []
    for bone, joint in (("ball_" + side, "toe_" + side), ("foot_" + side, "heel_" + side)):
        b = pb[bone]
        carry = arm_obj.matrix_world @ b.matrix @ b.bone.matrix_local.inverted()
        nm = joint.split("_")[0]
        forward, thick = SOLE_MODEL[nm][0] * scale, SOLE_THICK[nm] * scale
        at = b.bone.head_local + (Vector(J[joint][0]) - Vector(J[bone][0]) + Vector((0.0, -forward, 0.0))) * scale
        p = carry @ at
        R = carry.to_3x3()
        across = (R @ Vector((1.0, 0.0, 0.0))).normalized()
        up = (R @ Vector((0.0, 0.0, 1.0))).normalized()
        for tag, sgn in (("in", -1.0 if side == "l" else 1.0), ("out", 1.0 if side == "l" else -1.0)):
            out.append((nm + "_" + tag, p + across * (SOLE_HALF_WIDTH * scale * sgn) - up * thick))
    return out


def closing_sign(arm_obj, side):
    """Which way a finger bone's X turns the finger toward the palm: turn the
    index finger's second joint both ways and keep the one that brings its
    tip nearer the wrist. Leaves the finger as it was."""
    pb = arm_obj.pose.bones
    b = pb["index_02_" + side]; b.rotation_mode = "XYZ"
    keep = tuple(b.rotation_euler)
    wrist = pb["hand_" + side].head
    out = {}
    for sgn in (1.0, -1.0):
        b.rotation_euler = (keep[0] + sgn * 0.3, keep[1], keep[2])
        bpy.context.view_layer.update()
        out[sgn] = (pb["index_03_" + side].tail - wrist).length
    b.rotation_euler = keep
    bpy.context.view_layer.update()
    return 1.0 if out[1.0] < out[-1.0] else -1.0


def close_fists(arm_obj, amount=1.0):
    """Both hands closed by `amount` (0 the built hand, 1 the fist), as Euler
    rotations on the finger bones -- for a rig with no fist control, like
    the one the pipeline renders with. The control rig drives the same
    numbers from its `fist` slider (rig_full_ik)."""
    pb = arm_obj.pose.bones
    for side in ("l", "r"):
        sign = closing_sign(arm_obj, side)
        for f in FINGERS:
            for k, deg in enumerate(FIST_CURL):
                b = pb["%s_%02d_%s" % (f, k + 1, side)]; b.rotation_mode = "XYZ"
                b.rotation_euler = (sign * math.radians(deg) * amount, 0.0, 0.0)
        for k, (x, y, z) in enumerate(FIST_THUMB):
            b = pb["thumb_%02d_%s" % (k + 1, side)]; b.rotation_mode = "XYZ"
            # the fold across the palm (z) is a mirror between the hands: the
            # same sign on the right swung that thumb out, 1.14 hand lengths
            # from the fingers against 0.73 folded
            zs = sign if side == "l" else -sign
            b.rotation_euler = (sign * math.radians(x) * amount, math.radians(y) * amount, zs * math.radians(z) * amount)
    bpy.context.view_layer.update()

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
    world = bpy.data.worlds.new("SaudWorld")
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
    #
    # Re-lit 2026-09-22 from measurements on the renders, not by eye. The
    # old rig was three keys: the fill (70 W, 4 m across, at eye height)
    # was one stop under the key and lit the underside of the jaw, the rim
    # (320 W) was twice the key, and the key was 2.6 m across at 4.4 m. The
    # darkest skin pixel on the face was 87/255 and the underside of the jaw
    # was 0.2-0.4 stop under the lit cheek: no shadow side at all, so the
    # sculpted profile and the painted creases read at a fraction of their
    # strength and the face looked flat and waxy. And the fill's colour
    # (0.62, 0.72, 1.00) times his skin is (0.54, 0.50, 0.55) -- achromatic
    # -- so every shadow on him was neutral grey and read as dirt, magenta-
    # grey where the rim landed on it too. Now: key 210 W, 1.2 m, raised to
    # 30 deg; rim 130 W (0.42x the key, its red 0.8x the key's red); fill
    # 35 W (key:fill 4.4:1, two stops) raised so it no longer lights under
    # the jaw, and warmed to (0.80, 0.86, 1.00) so fill x skin is still a
    # skin colour. Renders only; nothing here ships.
    lamp("Key",  (-2.2,  -3.4, 3.5), 210, 1.2, (1.00, 0.86, 0.66))
    # Rim green above its blue: rim x skin with the old (0.96, 0.28, 0.34)
    # had G == B, and where the rim landed on the shadow side it made the
    # jaw angle magenta-grey. Same energy, same red.
    lamp("Rim",  ( 3.1,   2.1, 2.5), 130, 1.0, (0.96, 0.32, 0.28))
    lamp("Fill", ( 1.9,  -3.4, 2.0),  35, 4.0, (0.80, 0.86, 1.00))


def add_camera(location, look_at=Vector((0, 0, 0.98)), lens=70):
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = lens
    cam = bpy.data.objects.new("Cam", cam_data)
    cam.location = location
    cam.rotation_euler = (look_at - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return cam


def view_transform():
    """Khronos PBR Neutral where this Blender has it, else Standard."""
    try:
        bpy.context.scene.view_settings.view_transform = "Khronos PBR Neutral"
        return "Khronos PBR Neutral"
    except TypeError:
        return "Standard"


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
    # arrive as themselves. "Standard" kept them but clipped: under the
    # old rim, R hit 255 on 22 % of the face's skin pixels and the hue
    # collapsed to one flat salmon. Khronos PBR Neutral keeps sRGB colours
    # as themselves below the shoulder and rolls a saturated highlight off
    # instead of clipping one channel.
    scene.view_settings.view_transform = view_transform()
    scene.view_settings.look = "None"
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


# ====================================================================== main

def main():
    from hero import pipeline
    pipeline.run()


if __name__ == "__main__":
    main()
