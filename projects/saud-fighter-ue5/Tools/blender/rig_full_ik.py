#!/usr/bin/env python3
"""The full IK control rig: what an animator poses a fighter through.

    import rig_full_ik as CR
    CR.build(rig, mesh)            the control layer, on a built fighter
    CR.verify(rig, mesh)           does each control do what it says
    CR.snap_fk_to_ik(rig, "l", "hand")   take over a solved limb in FK, unmoved
    CR.snap_ik_to_fk(rig, "l", "foot")   hand an FK limb back to IK, unmoved
    CR.strip_for_export(rig, mesh) the mannequin's 62 bones and nothing else

    python3 rig_full_ik.py --roundtrip hero/build/Thug.blend
                                   pose him through the controls, bake, export,
                                   read it back, measure the difference
    python3 rig_full_ik.py --bite hero/build/Thug.blend
                                   break each mechanism and prove its check
                                   notices

WHAT WAS THERE. build_saud.add_ik puts an IK constraint on each calf and
each lowerarm (chain of two, target the mannequin's own ik_foot / ik_hand
bone, a pole Empty out along the joint's bend, the pole angle solved so the
rest pose sits still, the hinge limited to the side it bends). That is four
limbs that can be placed. It is not a rig anyone animates through: the
targets are mannequin bones with no handle, the poles are Empties, the
spine, the head and the fingers are aimed bone by bone in code, and a foot
has no roll.

WHAT THIS ADDS, and the rule it keeps. The exported skeleton has to stay
EXACTLY the mannequin's 62 bones -- 24 deforming, root, 7 IK, 30 finger --
or the retarget that makes these models useful breaks and the boss clips in
Content/Animation stop matching. So every bone here is non-deforming, lives
in a bone collection called CTRL or MCH, and is deleted again before the
FBX is written. The deform bones are never re-parented: a control drives a
deform bone through a constraint, and the hierarchy the engine sees is the
one it always saw.

    CTRL_root                 the master
    CTRL_pivot                the body turns about wherever this stands:
        MCH_unpivot             takes the pivot's own move back out, so
                                moving it changes nothing and turning it
                                turns everything below about that point
                                (a spin on the ball of the support foot)
    CTRL_hips                 pelvis follows it (Copy Transforms)
    CTRL_chest                spine_01/02/03 each take a third of its rotation
    CTRL_head, CTRL_look      neck and head split its rotation; `look` (0..1)
                              turns the head at CTRL_look instead
    CTRL_hand_l/r             the IK effector; ik_hand_* copies it, hand_*
                              takes its rotation. Props: fk (0 IK .. 1 FK),
                              fist (0 open .. 1 closed, on every finger)
    CTRL_elbow_l/r            the pole, a bone where the Empty was
    CTRL_foot_l/r             the effector for a reverse foot:
        MCH_heel_l/r            pivot at the heel, turns for roll < 0
        MCH_toe_l/r             pivot on the floor under the BALL, turns for roll > 0
        MCH_ankle_l/r           where the ankle ends up; ik_foot_* copies it
        MCH_toes_l/r            under the heel pivot only, so ball_* stays
                                flat on the ground through a toe roll
                              Props: fk, roll (-1 heel .. +1 toe)
    CTRL_knee_l/r             the pole

Which way a pivot turns is not asserted; it is found by turning it and
looking, the same way build_saud._limit_hinge finds a hinge's side, and
the sign that lifts the ankle is the sign the driver keeps. In FK (fk=1)
the deform bones themselves are the FK controls: they are the mannequin's
bones, in the DEF collection, which is hidden by default (show DEF to pose
them), and an FK layer on top of them would be a second copy of the same
62 names.

Numbers here that nothing else owns, all of them chosen: a heel roll of 35
degrees and a toe roll of 55 at the ends of the slider, the fist's 10
degrees a joint (rig_export.curl_fingers's number, since the mesh is a fist
already), CTRL_look 60 cm in front of the eyes, the widget sizes.

The skeleton this keeps is this project's, the mannequin's names plus
hand_end_l/r: what the hero, the boss clips and every fighter export, and
what has to match between them.

Nothing here is verified by an engine. verify() below measures the rig in
Blender; --roundtrip measures what leaves it.
"""
import os, sys, math
import bpy
from mathutils import Vector, Matrix, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SIDES = ("l", "r")
# where the Empties stood, from build_saud.IK_CHAINS: the pole bone goes
# to the same place, so the solved pole angle still holds
POLES = {"CTRL_elbow": ("lowerarm", "Pole_Elbow", "ik_hand"), "CTRL_knee": ("calf", "Pole_Knee", "ik_foot")}
HEEL_ROLL, TOE_ROLL = math.radians(35.0), math.radians(55.0)
# The mesh is built as a loose fist -- anatomy.hand() curls the fingers
# 72/109/36 degrees and lays the thumb along the index finger -- and at
# fist=1 the slider closes it to build_saud's FIST_CURL / FIST_THUMB, the
# fist found by rendering the hand (2026-09-24). It used to tighten 10
# degrees a joint, which left the claw and the thumb out it started as; 78
# a joint folded the fingers through the palm, which is what the first
# version measured. The thumb turns on two axes, to fold across the front.
FIST = math.radians(10.0)   # kept for the probe's test turn only
CTRL_PREFIX = ("CTRL_", "MCH_")


# ================================================================== helpers
def _pose_mode(rig):
    bpy.context.view_layer.objects.active = rig
    if rig.mode != "POSE":
        bpy.ops.object.mode_set(mode="POSE")

def _edit_mode(rig):
    bpy.context.view_layer.objects.active = rig
    if rig.mode != "EDIT":
        bpy.ops.object.mode_set(mode="EDIT")

def _object_mode(rig):
    bpy.context.view_layer.objects.active = rig
    if rig.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

def _update():
    bpy.context.view_layer.update()

def _world(rig, name):
    return (rig.matrix_world @ rig.pose.bones[name].matrix).translation.copy()

def _driver(target, path, expr, rig, props, index=-1):
    """A driver on `target.path` whose variables are custom properties on
    pose bones: props = {var: (bone, prop)}. Simple expressions only, so
    headless Blender needs no script auto-execution."""
    fc = target.driver_add(path, index) if index >= 0 else target.driver_add(path)
    d = fc.driver; d.type = "SCRIPTED"; d.expression = expr
    for var, (bone, prop) in props.items():
        v = d.variables.new(); v.name = var; v.type = "SINGLE_PROP"
        v.targets[0].id_type = "OBJECT"; v.targets[0].id = rig
        v.targets[0].data_path = 'pose.bones["%s"]["%s"]' % (bone, prop)
    _update()
    assert d.is_valid, "driver %r on %s is not valid" % (expr, path)
    return fc

def _prop(pb, name, default, lo, hi, desc):
    pb[name] = float(default)
    pb.id_properties_ui(name).update(min=lo, max=hi, soft_min=lo, soft_max=hi, description=desc)

def set_prop(rig, bone, name, value):
    """Write a control's property AND tell the depsgraph. A custom property
    written from Python does not tag the armature on its own, so the
    drivers reading it keep their last value: the roll, the look and the
    fist all measured exactly 0.0 until this did the tagging."""
    rig.pose.bones[bone][name] = float(value)
    rig.update_tag()
    _update()

def _widget(name, kind, size=1.0):
    """A mesh for a control to be drawn as, in a hidden collection."""
    coll = bpy.data.collections.get("WGT")
    if coll is None:
        coll = bpy.data.collections.new("WGT"); bpy.context.scene.collection.children.link(coll)
        coll.hide_viewport = True; coll.hide_render = True
    if name in bpy.data.objects:
        return bpy.data.objects[name]
    me = bpy.data.meshes.new(name)
    if kind == "circle":
        n = 32; verts = [(math.cos(2 * math.pi * i / n) * size, math.sin(2 * math.pi * i / n) * size, 0.0) for i in range(n)]
        edges = [(i, (i + 1) % n) for i in range(n)]; me.from_pydata(verts, edges, [])
    elif kind == "cube":
        s = size * 0.5
        verts = [(x, y, z) for x in (-s, s) for y in (-s, s) for z in (-s, s)]
        edges = [(a, b) for a in range(8) for b in range(a + 1, 8) if bin(a ^ b).count("1") == 1]
        me.from_pydata(verts, edges, [])
    elif kind == "sphere":
        n = 24; verts, edges = [], []
        for ring, axes in enumerate(((0, 1), (0, 2), (1, 2))):
            base = len(verts)
            for i in range(n):
                v = [0.0, 0.0, 0.0]; a = 2 * math.pi * i / n
                v[axes[0]] = math.cos(a) * size; v[axes[1]] = math.sin(a) * size; verts.append(tuple(v))
            edges += [(base + i, base + (i + 1) % n) for i in range(n)]
        me.from_pydata(verts, edges, [])
    elif kind == "arrow":      # along +Y
        verts = [(0, 0, 0), (0, size, 0), (-0.2 * size, 0.7 * size, 0), (0.2 * size, 0.7 * size, 0)]
        me.from_pydata(verts, [(0, 1), (1, 2), (1, 3)], [])
    o = bpy.data.objects.new(name, me); coll.objects.link(o)
    return o


# ==================================================================== build
def build(rig, mesh):
    """The control layer on a fighter built by hero.pipeline: the rig from
    build_saud.build_armature with add_ik applied, the mesh bound to it."""
    assert rig.matrix_world == Matrix.Identity(4), "the rig is expected at the origin, unrotated"
    for side in SIDES:
        for ctrl, (bone, empty, _) in POLES.items():
            assert "%s_%s" % (empty, side) in bpy.data.objects, "add_ik has not run: no %s_%s" % (empty, side)
    import build_saud as legacy
    _object_mode(rig)
    arm = rig.data
    # ---- the precondition: at rest, with the IK live and the poles where
    # add_ik solved them, nothing moves. Put the Empties back there first
    # (a render stage may have moved them) and measure.
    for bone_name, target, pole_name, offset in legacy.IK_CHAINS:
        bpy.data.objects[pole_name].location = rig.pose.bones[bone_name].bone.head_local + offset
    legacy.mute_ik(rig, False); legacy.pose(rig, {})
    worst, who = _rest_deviation(rig)
    assert worst < 2e-3, "before any control is added the rig does not sit still at rest: %s off by %.4f" % (who, worst)
    # ---- bone collections. DEF is what ships; CTRL is what an animator
    # touches; MCH is the mechanism between them.
    colls = {}
    for name, visible in (("DEF", False), ("MCH", False), ("CTRL", True)):
        c = arm.collections.get(name) or arm.collections.new(name)
        c.is_visible = visible; colls[name] = c
    for b in arm.bones:
        colls["DEF"].assign(b)

    # ---- the bones, in edit mode. A control that drives a deform bone
    # through Copy Transforms / Copy Rotation must share that bone's rest
    # (head, tail, roll): the constraint copies a whole transform, and a
    # control at a different rest would carry its difference into the bone.
    _edit_mode(rig)
    eb = arm.edit_bones
    def copy_of(name, src, parent, deform=False):
        b = eb.new(name); b.head = eb[src].head.copy(); b.tail = eb[src].tail.copy(); b.roll = eb[src].roll
        b.use_deform = deform; b.parent = eb[parent] if parent else None; b.use_connect = False
        return b
    def at(name, head, tail, parent):
        b = eb.new(name); b.head = Vector(head); b.tail = Vector(tail); b.roll = 0.0
        b.use_deform = False; b.parent = eb[parent] if parent else None; b.use_connect = False
        return b
    # Where the poles go: the REST positions add_ik solved the pole angles
    # for, recomputed from IK_CHAINS -- not wherever the Empties happen to be.
    # The render stage's KICK pose moves them and build_saud.pose(rig, {})
    # never moves them back, so reading their current location put the
    # elbow's pole where the kick had it and the rest pose twisted 1.47 out.
    poles = {}
    for bone_name, target, pole_name, offset in legacy.IK_CHAINS:
        side = bone_name[-1]
        ctrl = "CTRL_elbow" if bone_name.startswith("lowerarm") else "CTRL_knee"
        poles["%s_%s" % (ctrl, side)] = eb[bone_name].head.copy() + offset
    ankle = {s: eb["foot_%s" % s].head.copy() for s in SIDES}
    ball = {s: eb["ball_%s" % s].head.copy() for s in SIDES}
    heel = {s: Vector(legacy.J["heel_%s" % s][0]) for s in SIDES}
    toe = {s: Vector(legacy.J["toe_%s" % s][0]) for s in SIDES}
    eye_z = eb["head"].head.z + 0.005

    # The master shares root's rest (it points up, from the origin): root
    # follows it by Copy Transforms, and a master lying along +Y would turn
    # the whole hierarchy under root through 90 degrees -- the first version
    # did, and the mannequin's ik_hand_gun went with it. The circle widget
    # is turned flat instead.
    root = copy_of("CTRL_root", "root", None)
    # The pivot: the whole body turns about wherever CTRL_pivot stands, not
    # about the origin. Moving it changes nothing (MCH_unpivot takes the
    # move straight back out: T(p) R T(-p) with R the identity); turning it
    # turns the body about that point. A spinning kick turns on the ball of
    # the support foot -- turned about the origin instead, the FK boss
    # clips skated that foot 44-54 cm round a circle. The two bones share
    # one rest (up from the origin, root's own direction), which is what
    # makes MCH_unpivot's local-space inverse exactly the pivot's.
    at("CTRL_pivot", (0, 0, 0), (0, 0, 0.25), "CTRL_root")
    at("MCH_unpivot", (0, 0, 0), (0, 0, 0.25), "CTRL_pivot")
    BODY = "MCH_unpivot"
    copy_of("CTRL_hips", "pelvis", BODY)
    copy_of("CTRL_chest", "spine_03", "CTRL_hips")
    copy_of("CTRL_head", "head", "CTRL_chest")
    at("CTRL_look", (0, -0.60, eye_z), (0, -0.50, eye_z), BODY)
    for s in SIDES:
        copy_of("CTRL_hand_%s" % s, "hand_%s" % s, BODY)
        p = poles["CTRL_elbow_%s" % s]; at("CTRL_elbow_%s" % s, p, p + Vector((0, 0.06, 0)), BODY)
        p = poles["CTRL_knee_%s" % s]; at("CTRL_knee_%s" % s, p, p + Vector((0, -0.06, 0)), BODY)
        # the reverse foot: control at the ankle, heel pivot on the floor
        # under the heel, toe pivot on the floor at the toe tip, and the
        # ankle hung from the toe pivot so a toe roll lifts it
        # The foot control shares foot_*'s rest orientation, like the hand's
        # and the hips': a control whose frame differed from the bone it
        # drives would carry that difference into the bone -- MCH_ankle hangs
        # under it, and foot_* copies MCH_ankle's rotation.
        copy_of("CTRL_foot_%s" % s, "foot_%s" % s, BODY)
        a = ankle[s]
        # The heel pivot is on the floor under the heel joint. The toe pivot
        # is on the floor under the BALL, not the toe tip: a foot rolls up
        # onto the ball of the foot, and the toes stay flat on the floor
        # beyond it. Put at the tip, the first version lifted the ball joint
        # 4.6 cm on a full roll and the toes went with it.
        h = Vector((heel[s].x, heel[s].y, 0.0))
        at("MCH_heel_%s" % s, h, h + Vector((0, -0.10, 0)), "CTRL_foot_%s" % s)
        t = Vector((ball[s].x, ball[s].y, 0.0))
        at("MCH_toe_%s" % s, t, t + Vector((0, 0.10, 0)), "MCH_heel_%s" % s)
        copy_of("MCH_ankle_%s" % s, "foot_%s" % s, "MCH_toe_%s" % s)
        copy_of("MCH_toes_%s" % s, "ball_%s" % s, "MCH_heel_%s" % s)
    _object_mode(rig)

    for b in arm.bones:
        if b.name.startswith("CTRL_"):
            colls["CTRL"].assign(b); colls["DEF"].unassign(b)
        elif b.name.startswith("MCH_"):
            colls["MCH"].assign(b); colls["DEF"].unassign(b)

    # ---- the constraints, and the properties that drive them
    _pose_mode(rig)
    pb = rig.pose.bones
    def con(bone, kind, target, **kw):
        c = pb[bone].constraints.new(kind); c.target = rig; c.subtarget = target
        for k, v in kw.items(): setattr(c, k, v)
        return c
    con("root", "COPY_TRANSFORMS", "CTRL_root", name="CTRL")
    con("MCH_unpivot", "COPY_LOCATION", "CTRL_pivot", name="UNPIVOT", owner_space="LOCAL", target_space="LOCAL",
        invert_x=True, invert_y=True, invert_z=True)
    con("pelvis", "COPY_TRANSFORMS", "CTRL_hips", name="CTRL")
    for i, sp in enumerate(("spine_01", "spine_02", "spine_03")):
        con(sp, "COPY_ROTATION", "CTRL_chest", name="CTRL", owner_space="LOCAL", target_space="LOCAL",
            mix_mode="AFTER", influence=1.0 / 3.0)
    con("neck_01", "COPY_ROTATION", "CTRL_head", name="CTRL", owner_space="LOCAL", target_space="LOCAL", mix_mode="AFTER", influence=0.5)
    con("head", "COPY_ROTATION", "CTRL_head", name="CTRL", owner_space="LOCAL", target_space="LOCAL", mix_mode="AFTER", influence=0.5)
    _prop(pb["CTRL_head"], "look", 0.0, 0.0, 1.0, "0: the head goes where CTRL_head turns it; 1: it looks at CTRL_look")
    # the head bone points up; its forward is its own Z (root and spine are
    # the same: local Z is world -Y, the way he faces -- see build_motion.py)
    look = con("head", "DAMPED_TRACK", "CTRL_look", name="LOOK", track_axis="TRACK_Z")
    _driver(look, "influence", "look", rig, {"look": ("CTRL_head", "look")})

    fingers = ("index", "middle", "ring", "pinky")
    for s in SIDES:
        hand, foot = "CTRL_hand_%s" % s, "CTRL_foot_%s" % s
        _prop(pb[hand], "fk", 0.0, 0.0, 1.0, "0: the arm reaches for this control (IK); 1: the arm bones are posed directly (FK)")
        _prop(pb[hand], "fist", 0.0, 0.0, 1.0, "0: fingers as built; 1: a closed fist")
        _prop(pb[foot], "fk", 0.0, 0.0, 1.0, "0: the leg reaches for this control (IK); 1: the leg bones are posed directly (FK)")
        _prop(pb[foot], "roll", 0.0, -1.0, 1.0, "-1: back on the heel; +1: up on the toes")
        # the IK constraints add_ik made: pole to the bone, influence to the
        # switch. Retargeted FIRST: while the solver still reaches for
        # ik_hand_*, the Copy Transforms below (ik_hand_* following hand_*)
        # closes a cycle through the arm, and the depsgraph said so fourteen
        # times per build until the order was this.
        for ctrl, (bone, empty, target) in POLES.items():
            ik = pb["%s_%s" % (bone, s)].constraints["IK"]
            # the solver reaches for the control (the reverse foot's ankle
            # for a leg), not for the mannequin's ik bone, which now follows
            ik.subtarget = hand if ctrl == "CTRL_elbow" else "MCH_ankle_%s" % s
            ik.pole_target = rig; ik.pole_subtarget = "%s_%s" % (ctrl, s)
            _driver(ik, "influence", "1 - fk", rig, {"fk": (hand if ctrl == "CTRL_elbow" else foot, "fk")})
            bpy.data.objects.remove(bpy.data.objects["%s_%s" % (empty, s)], do_unlink=True)
        # The mannequin's own IK bones carry where the hand and the foot ARE,
        # in the export and in either mode -- that is the convention an
        # engine's IK retargeting reads them by. They follow the deform
        # bones, not the controls: in FK the control is not where the hand is.
        con("ik_hand_%s" % s, "COPY_TRANSFORMS", "hand_%s" % s, name="CTRL")
        con("ik_foot_%s" % s, "COPY_TRANSFORMS", "foot_%s" % s, name="CTRL")
        c = con("hand_%s" % s, "COPY_ROTATION", hand, name="CTRL")
        _driver(c, "influence", "1 - fk", rig, {"fk": (hand, "fk")})
        c = con("foot_%s" % s, "COPY_ROTATION", "MCH_ankle_%s" % s, name="CTRL")
        _driver(c, "influence", "1 - fk", rig, {"fk": (foot, "fk")})
        c = con("ball_%s" % s, "COPY_ROTATION", "MCH_toes_%s" % s, name="CTRL")
        _driver(c, "influence", "1 - fk", rig, {"fk": (foot, "fk")})
        # the fist: every finger bone curls with the slider; the thumb half.
        # Which sign closes the hand is found by turning the index finger
        # and measuring, as the roll signs are: it depends on the bones'
        # roll, and on this rig the sign curl_fingers assumed opened it.
        for f in fingers + ("thumb",):
            for k in (1, 2, 3):
                pb["%s_%02d_%s" % (f, k, s)].rotation_mode = "XYZ"
        sign = _probe_curl(rig, s)
        for f in fingers:
            for k in (1, 2, 3):
                b = pb["%s_%02d_%s" % (f, k, s)]
                _driver(b, "rotation_euler", "%s * fist * %.4f" % (sign, math.radians(legacy.FIST_CURL[k - 1])), rig,
                        {"fist": (hand, "fist")}, index=0)
        for k in (1, 2, 3):
            b = pb["thumb_%02d_%s" % (k, s)]
            for axis in (0, 2):
                amount = legacy.FIST_THUMB[k - 1][axis]
                # the fold across the palm (z) mirrors between the hands
                # (_probe_curl's sign is the expression's own text, "-1" or "1")
                axsign = sign if (axis == 0 or s == "l") else (
                    str(sign)[1:] if str(sign).startswith("-") else "-" + str(sign))
                if amount:
                    _driver(b, "rotation_euler", "%s * fist * %.4f" % (axsign, math.radians(amount)), rig,
                            {"fist": (hand, "fist")}, index=axis)
        # the foot roll: which sign lifts the ankle is found by asking
        for mch, amount, which in (("MCH_heel_%s" % s, HEEL_ROLL, "heel"), ("MCH_toe_%s" % s, TOE_ROLL, "toe")):
            pb[mch].rotation_mode = "XYZ"
            sign = _probe_roll(rig, mch, which, s)
            expr = "%s * max(-roll, 0) * %.4f" % (sign, HEEL_ROLL) if which == "heel" else "%s * max(roll, 0) * %.4f" % (sign, TOE_ROLL)
            _driver(pb[mch], "rotation_euler", expr, rig, {"roll": (foot, "roll")}, index=0)
    _update()

    # ---- the rest must still be the rest: every control at zero gives the
    # pose add_ik was tuned to sit still in
    worst, who = _rest_deviation(rig)
    assert worst < 2e-3, "the control rig at rest moves %s by %.4f" % (who, worst)

    # ---- what the animator sees
    shapes = {"CTRL_root": ("circle", 0.55), "CTRL_hips": ("cube", 0.34), "CTRL_chest": ("cube", 0.30),
              "CTRL_head": ("circle", 0.16), "CTRL_look": ("sphere", 0.05), "CTRL_pivot": ("circle", 0.12)}
    for s in SIDES:
        shapes.update({"CTRL_hand_%s" % s: ("cube", 0.11), "CTRL_foot_%s" % s: ("cube", 0.16),
                       "CTRL_elbow_%s" % s: ("sphere", 0.04), "CTRL_knee_%s" % s: ("sphere", 0.04)})
    for name, (kind, size) in shapes.items():
        b = pb[name]; b.custom_shape = _widget("WGT_" + kind, kind); b.custom_shape_scale_xyz = (size, size, size)
        b.use_custom_shape_bone_size = False      # the size IS the metres above, not a multiple of a 6 cm bone
        if name in ("CTRL_root", "CTRL_pivot"):
            b.custom_shape_rotation_euler = (math.radians(90.0), 0.0, 0.0)     # the bone points up; the circle lies flat
        b.color.palette = "THEME01" if name.endswith("_l") else ("THEME04" if name.endswith("_r") else "THEME09")
    for b in pb:
        if b.name.startswith("MCH_"):
            b.color.palette = "THEME10"
    _object_mode(rig)
    n = sum(1 for b in arm.bones if b.name.startswith("CTRL_"))
    print("control rig: %d control bones, %d mechanism bones, rest deviation %.1e" % (
        n, sum(1 for b in arm.bones if b.name.startswith("MCH_")), worst))
    return dict(controls=n, mechanism=sum(1 for b in arm.bones if b.name.startswith("MCH_")), rest_deviation=worst)


def _rest_deviation(rig):
    """How far the deform bones (and the mannequin's IK bones) sit from their
    rest matrices, and which one is worst. Translation in metres; the
    rotation part's entries are dimensionless and a flipped bone shows as 2."""
    _update()
    worst, who = 0.0, None
    for b in rig.pose.bones:
        if not (b.bone.use_deform or b.name.startswith("ik_")):
            continue
        d = b.matrix - b.bone.matrix_local
        e = max(abs(v) for row in d for v in row)
        if e > worst:
            worst, who = e, b.name
    return worst, who


def _probe_curl(rig, side):
    """Turn the index finger's three bones FIST each way and see which way
    brings the fingertip toward the wrist: that is the sign that tightens
    the fist. Returns it and leaves the finger as built."""
    _update()
    pb = rig.pose.bones
    def grip():
        return (rig.matrix_world @ pb["index_03_%s" % side].tail - _world(rig, "hand_%s" % side)).length
    def turned(sign):
        for k in (1, 2, 3):
            pb["index_%02d_%s" % (k, side)].rotation_euler = (sign * FIST, 0.0, 0.0)
        _update(); g = grip()
        for k in (1, 2, 3):
            pb["index_%02d_%s" % (k, side)].rotation_euler = (0.0, 0.0, 0.0)
        _update(); return g
    g0 = grip(); plus, minus = turned(1.0), turned(-1.0)
    sign = "1" if plus < minus else "-1"
    print("curl probe  : index_%s tip-to-wrist %.1f mm; +%d deg a joint -> %.1f, -%d -> %.1f; tightens with sign %s" % (
        side, g0 * 1000, round(math.degrees(FIST)), plus * 1000, round(math.degrees(FIST)), minus * 1000, sign))
    assert min(plus, minus) < g0 - 0.002, "neither way of turning the index finger brings its tip toward the wrist"
    return sign


def _probe_roll(rig, mch, which, side):
    """Turn the pivot by +10 degrees about its X and see what the ankle does.
    A toe pivot that lifts the ankle is turning the right way; a heel pivot
    that drops the ankle behind the heel (tips the foot back) is. Returns
    the sign as a string for the driver, and leaves the bone at zero."""
    _update()
    pb = rig.pose.bones
    before = _world(rig, "MCH_ankle_%s" % side)
    pb[mch].rotation_euler = (math.radians(10.0), 0.0, 0.0); _update()
    after = _world(rig, "MCH_ankle_%s" % side)
    pb[mch].rotation_euler = (0.0, 0.0, 0.0); _update()
    d = after - before
    if which == "toe":
        ok = d.z > 0.002                     # the ankle rises off the toe pivot
    else:
        ok = d.y > 0.002 and d.z > -0.001    # the ankle goes back over the heel, not into the floor
    print("roll probe  : %-11s +10 deg moved the ankle (%+.4f, %+.4f, %+.4f) -> sign %s" % (mch, d.x, d.y, d.z, "+1" if ok else "-1"))
    return "1" if ok else "-1"


# =================================================================== posing
def set_translation(rig, name, where):
    """Put a bone at `where` in the ARMATURE's own space, PoseBone.matrix's."""
    pb = rig.pose.bones[name]
    m = pb.matrix.copy(); m.translation = Vector(where); pb.matrix = m; _update()

def set_world_translation(rig, name, where):
    """Put a bone at `where` in WORLD space. The first version wrote the
    world position straight into PoseBone.matrix, which is armature space;
    the two agree only with the rig at the origin, where every render of
    the pipeline had it, and the first man to stand 56 m from the origin in
    the souq reached 56 m back for his own hands."""
    set_translation(rig, name, rig.matrix_world.inverted() @ Vector(where))

def reset(rig):
    """Every control home, every switch at its default."""
    _pose_mode(rig)
    for b in rig.pose.bones:
        b.location = (0, 0, 0); b.rotation_quaternion = (1, 0, 0, 0); b.rotation_euler = (0, 0, 0); b.scale = (1, 1, 1)
        for k in ("fk", "fist", "roll", "look"):
            if k in b.keys():
                b[k] = 0.0
    rig.update_tag()
    _update()

# limb -> (control, pole, upper, lower, end, extra end bones carried in FK)
LIMBS = {"hand": ("CTRL_hand", "CTRL_elbow", "upperarm", "lowerarm", "hand", ()),
         "foot": ("CTRL_foot", "CTRL_knee", "thigh", "calf", "foot", ("ball",))}

def _chain(limb, side):
    ctrl, pole, upper, lower, end, extra = LIMBS[limb]
    return ("%s_%s" % (ctrl, side), "%s_%s" % (pole, side),
            ["%s_%s" % (b, side) for b in (upper, lower, end) + extra])

def snap_fk_to_ik(rig, side, limb):
    """Hand a limb from IK to FK without it moving: the solved bones'
    matrices are read, the switch goes to FK, and the same matrices are
    written onto the bones themselves, parents first. Exact by construction
    -- verify() holds it to half a millimetre -- and it is the move an
    animator makes to take over a limb the solver placed."""
    ctrl, _pole, bones = _chain(limb, side)
    pb = rig.pose.bones
    _pose_mode(rig); _update()
    held = [(n, pb[n].matrix.copy()) for n in bones]
    set_prop(rig, ctrl, "fk", 1.0)
    for n, m in held:
        pb[n].matrix = m; _update()

def snap_ik_to_fk(rig, side, limb):
    """Hand a limb from FK to IK without it moving: the control goes where
    the end bone is (they share a rest, so the matrix copies straight
    across), the pole goes out along the limb's present bend, any foot roll
    is zeroed, and the switch goes to IK. The pole is placed from the bend
    rather than left where it was, because a pole left behind turns the
    whole limb about its own line the moment the solver takes over."""
    import build_saud as legacy
    ctrl, pole, bones = _chain(limb, side)
    pb = rig.pose.bones
    _pose_mode(rig); _update()
    upper, lower, end = bones[0], bones[1], bones[2]
    a, b, c = pb[upper].head.copy(), pb[lower].head.copy(), pb[lower].tail.copy()
    end_m = pb[end].matrix.copy()
    fallback = Vector((0, 1, 0)) if limb == "hand" else Vector((0, -1, 0))
    if "roll" in pb[ctrl].keys():
        set_prop(rig, ctrl, "roll", 0.0)
    pb[ctrl].matrix = end_m; _update()
    set_translation(rig, pole, legacy._pole_from(a, b, c, fallback))
    set_prop(rig, ctrl, "fk", 0.0)

def _aim(rig, directions):
    """build_saud.pose()'s aiming -- each named bone's Y put on a world
    direction, parents first -- without the rest of it: pose() also resets
    every bone's rotation mode to quaternion, which silences the euler
    drivers on the fingers and the foot pivots, and moves pole Empties this
    rig no longer has."""
    import build_saud as legacy
    _pose_mode(rig)
    for name in legacy._hierarchy_order(rig):
        if name not in directions:
            continue
        pbone = rig.pose.bones[name]
        aim = Vector(directions[name]).normalized()
        # the bone's CURRENT frame swung onto the aim, no twist about its
        # length. to_track_quat("Y", "Z") built a frame whose Z is world up
        # projected, which for a bone whose rest Z is world -Y (the spine,
        # the neck, the head) or straight down (a foot) is a 180 degree turn
        # about the bone: every stance had the chest facing backwards, the
        # nose behind the head, the soles up and the reverse foot's pivots
        # 20 cm in the air, and the tee "pinched at the waist" between the
        # unturned pelvis and the turned spine.
        cur = pbone.matrix.to_3x3()
        y = Vector((cur[0][1], cur[1][1], cur[2][1])).normalized()
        m = (y.rotation_difference(aim).to_matrix() @ cur).to_4x4()
        m.translation = pbone.matrix.translation
        pbone.matrix = m
        _update()
    # which way the palms face (build_saud.GUARD's palm_l/palm_r): the hand
    # turned about its own length, once it is aimed
    for side in SIDES:
        if "palm_" + side in directions:
            legacy.roll_palm(rig, side, directions["palm_" + side])
            _update()


def stance(rig, fk, mesh=None, plant=("l", "r")):
    """An FK stance from build_saud (GUARD, KICK), applied THROUGH the
    controls: the body aims are set on the deform bones with the limbs in
    FK, the wrists and ankles are read off, and the hand and foot controls
    are put there with the poles out along each bend -- then the limbs go
    back to IK and reach for them. Planted feet are then lowered until the
    sole is where it is at rest, as build_saud.limb_targets does."""
    import build_saud as legacy
    reset(rig)
    pb = rig.pose.bones
    for s in SIDES:
        set_prop(rig, "CTRL_hand_%s" % s, "fk", 1.0); set_prop(rig, "CTRL_foot_%s" % s, "fk", 1.0)
    _aim(rig, fk)
    # Everything here is in the armature's own space: the man faces his
    # own -Y, the poles go out along his own bends, and PoseBone.matrix is
    # read and written in that space -- so the stance is his wherever and
    # however he stands. The first version read these through
    # rig.matrix_world and wrote them back as if that were the same space,
    # which it is only at the origin.
    targets, poles = {}, {}
    for s in SIDES:
        hip, knee, ankle = pb["thigh_" + s].head.copy(), pb["calf_" + s].head.copy(), pb["calf_" + s].tail.copy()
        shoulder, elbow, wrist = pb["upperarm_" + s].head.copy(), pb["lowerarm_" + s].head.copy(), pb["lowerarm_" + s].tail.copy()
        targets["CTRL_foot_" + s] = (ankle.copy(), pb["foot_" + s].matrix.copy())
        targets["CTRL_hand_" + s] = (wrist.copy(), pb["hand_" + s].matrix.copy())
        poles["CTRL_knee_" + s] = knee + Vector((0, -0.6, 0)) if s in plant else legacy._pole_from(hip, knee, ankle, Vector((0, -1, 0)))
        poles["CTRL_elbow_" + s] = legacy._pole_from(shoulder, elbow, wrist, Vector((0, 1, 0)))
    for s in SIDES:
        set_prop(rig, "CTRL_hand_%s" % s, "fk", 0.0); set_prop(rig, "CTRL_foot_%s" % s, "fk", 0.0)
    for name, (where, mat) in targets.items():
        m = mat.copy(); m.translation = where; pb[name].matrix = m; _update()
    for name, where in poles.items():
        set_translation(rig, name, where)
    if mesh is not None:
        rest = {s: legacy._foot_floor(mesh, rig, s) for s in SIDES}
        # rest was measured in THIS pose; measure the true rest first
        cur = {name: pb[name].matrix.copy() for name in targets}
        reset(rig); floor = {s: legacy._foot_floor(mesh, rig, s) for s in SIDES}
        for s in SIDES:
            set_prop(rig, "CTRL_hand_%s" % s, "fk", 1.0); set_prop(rig, "CTRL_foot_%s" % s, "fk", 1.0)
        _aim(rig, fk)
        for s in SIDES:
            set_prop(rig, "CTRL_hand_%s" % s, "fk", 0.0); set_prop(rig, "CTRL_foot_%s" % s, "fk", 0.0)
        for name, m in cur.items():
            pb[name].matrix = m; _update()
        for name, where in poles.items():
            set_translation(rig, name, where)
        # The body comes down onto its feet (build_saud.limb_targets says
        # why): hips, hand and foot controls and poles all lowered until the
        # higher planted foot is on the floor, the knees' bend kept.
        body = max(0.0, min(legacy._foot_floor(mesh, rig, s) - floor[s] for s in plant))
        if body:
            for name in ["CTRL_hips"] + list(cur):
                m = pb[name].matrix.copy(); m.translation.z -= body; pb[name].matrix = m; _update()
            for name, where in poles.items():
                set_translation(rig, name, where - Vector((0.0, 0.0, body)))
        for s in plant:
            for _ in range(3):
                drop = legacy._foot_floor(mesh, rig, s) - floor[s]
                m = pb["CTRL_foot_" + s].matrix.copy(); m.translation.z -= drop; pb["CTRL_foot_" + s].matrix = m; _update()
                if abs(drop) < 0.0005:
                    break
    far = max((pb[n].matrix.translation.length, n) for n in list(targets) + list(poles))
    assert far[0] < 3.0, "stance: %s ended up %.1f m from the man -- a world position written in armature space" % (far[1], far[0])
    _object_mode(rig)


# =================================================================== verify
def _toe_and_heel(rig, mesh, side):
    """The toe tip and the heel, as the bones carry them: the joint table's
    toe_* and heel_* points expressed in ball_* and foot_*'s rest frames and
    moved by those bones' current matrices. Reading them off the mesh's
    lowest vertices was ambiguous -- the sole is its own island and its
    weights are whatever heat gave it."""
    import build_saud as legacy
    pb = rig.pose.bones
    def carried(bone, point):
        b = pb[bone]
        return (rig.matrix_world @ b.matrix @ b.bone.matrix_local.inverted() @ Vector(point)).z
    toe = carried("ball_" + side, legacy.J["toe_" + side][0])
    heel = carried("foot_" + side, legacy.J["heel_" + side][0])
    return toe, heel

def verify(rig, mesh, scale=1.0):
    """Does each control do what it says. Every one of these has been made
    to fail by breaking the piece it tests (see bite()).

    `scale` is the fighter's own height factor (pipeline.build_fighter's
    `factors["h"]`, 1.0 for Saud himself) -- ONE BODY, EVERY MAN means the
    shoe, the toe-to-floor-pivot distance and the roll it produces all grow
    with him, but the tolerances below were measured in millimetres on
    Saud's own build and never scaled. ZAYOS (h 1.476, the biggest man on
    the roster) failed the toe-roll checks at his own true proportions --
    floor clip 15.3 mm against a 15 mm ceiling measured on a man 1.5 times
    smaller -- while AL-SAQR and AL-WAHSH (h close to 1.0) passed the same
    rig code unchanged, which is what pins this on the tolerance rather
    than the geometry. Passing 1.0 (bite()'s own default, checked against
    Saud-scale sabotage) leaves every existing check exactly as it was."""
    fails = []
    pb = rig.pose.bones
    reset(rig)
    # 1 the hand reaches its control, and the elbow bends toward its pole
    # in HIS frame (PoseBone.matrix), like the look probe: forward is his -Y
    # wherever he stands
    tip0 = pb["hand_end_l"].matrix.translation.copy(); wrist0 = pb["CTRL_hand_l"].matrix.translation.copy()
    set_translation(rig, "CTRL_hand_l", wrist0 + Vector((0, -0.20, 0)))
    tip1 = pb["hand_end_l"].matrix.translation.copy()
    reach = (tip0.y - tip1.y)
    if reach < 0.18:
        fails.append("hand IK: CTRL_hand_l went 20 cm forward and hand_end_l went %.1f cm" % (reach * 100))
    # the bend: bring the wrist a third of the way back toward the shoulder,
    # which a straight arm cannot do without an elbow, and see which way the
    # elbow went against the shoulder-to-wrist line. The pole is behind
    # (+Y), so the bend must point that way. Pulling the wrist forward, as
    # above, is the wrong probe for this: a straight arm swings forward
    # from the shoulder and bends almost nothing.
    reset(rig)
    sh = pb["upperarm_l"].matrix.translation.copy(); wr0 = pb["CTRL_hand_l"].matrix.translation.copy()
    set_translation(rig, "CTRL_hand_l", sh + (wr0 - sh) * 0.66)
    el, wr = pb["lowerarm_l"].matrix.translation.copy(), pb["lowerarm_l"].tail.copy()
    bend = el - (sh + wr) * 0.5
    if bend.y < 0.03:
        fails.append("hand IK: the elbow did not bend toward its pole (bend %+.1f cm along Y)" % (bend.y * 100))
    # 2 the switch: in FK the same move does nothing to the arm
    reset(rig); set_prop(rig, "CTRL_hand_l", "fk", 1.0)
    tip0 = _world(rig, "hand_end_l")
    set_translation(rig, "CTRL_hand_l", pb["CTRL_hand_l"].matrix.translation + Vector((0, -0.20, 0)))
    if (_world(rig, "hand_end_l") - tip0).length > 0.001:
        fails.append("fk switch: with fk=1 the hand still followed the control by %.1f mm" % ((_world(rig, "hand_end_l") - tip0).length * 1000))
    # 3 the reverse foot
    import build_saud as legacy
    reset(rig)
    toes0, heel0 = _toe_and_heel(rig, mesh, "l"); ankle0 = _world(rig, "foot_l"); floor0 = legacy._foot_floor(mesh, rig, "l")
    set_prop(rig, "CTRL_foot_l", "roll", 1.0)
    toes1, heel1 = _toe_and_heel(rig, mesh, "l"); ankle1 = _world(rig, "foot_l"); floor1 = legacy._foot_floor(mesh, rig, "l")
    # and the SHOE, evaluated: the bones carried their points but the toe
    # box was weighted to foot_* and went 35 mm through the floor with it
    if floor0 - floor1 > 0.015 * scale:
        fails.append("toe roll: the shoe's lowest vertex went %.1f mm through the floor" % ((floor0 - floor1) * 1000))
    # 1.5 cm: the ball joint sits 2.4 cm above the floor pivot, so a full
    # roll lifts it 2.4 * (1 - cos 55) = 1.0 cm, and the toes with it
    # STAY: not up (they left the floor) and not down (a rigid foot pivoting
    # heel-up about the ball pushes its toes 6 cm through the floor, which
    # is what breaking the flat-toes helper does). Both the 2.4 cm pivot
    # and the toe box it holds up scale with the man, so this ceiling does
    # too -- see `scale` above.
    if abs(toes1 - toes0) > 0.015 * scale:
        fails.append("toe roll: the toes left the floor plane by %+.1f cm" % ((toes1 - toes0) * 100))
    if ankle1.z - ankle0.z < 0.04 * scale:
        fails.append("toe roll: the ankle rose only %.1f cm" % ((ankle1.z - ankle0.z) * 100))
    set_prop(rig, "CTRL_foot_l", "roll", -1.0)
    toes2, heel2 = _toe_and_heel(rig, mesh, "l")
    if abs(heel2 - heel0) > 0.015 * scale:
        fails.append("heel roll: the heel left the floor plane by %+.1f cm" % ((heel2 - heel0) * 100))
    if toes2 - toes0 < 0.03 * scale:
        fails.append("heel roll: the toes rose only %.1f cm" % ((toes2 - toes0) * 100))
    # 4 the look
    reset(rig)
    def yaw():
        m = rig.pose.bones["head"].matrix
        f = Vector((m[0][2], m[1][2], 0.0))          # the head's Z, its forward, flattened
        return math.degrees(math.atan2(f.x, -f.y))   # 0 = straight ahead (-Y)
    y0 = yaw()
    # a metre to HIS left, in his own frame, since yaw() reads his own frame
    set_translation(rig, "CTRL_look", pb["CTRL_look"].matrix.translation + Vector((1.0, 0, 0)))
    y_off = yaw()
    set_prop(rig, "CTRL_head", "look", 1.0)
    y_on = yaw()
    if abs(y_off - y0) > 0.5:
        fails.append("look: with look=0 the head turned %.1f deg toward CTRL_look" % (y_off - y0))
    # signed: the control went to his LEFT (+X), so the yaw must be positive.
    # abs() here passed a head that turned the wrong way, which is what the
    # default TRACK_Y did (-30 degrees, the crown at the target).
    if y_on - y0 < 20.0:
        fails.append("look: with look=1 the head turned only %+.1f deg toward CTRL_look" % (y_on - y0))
    # 5 the fist
    reset(rig)
    def grip():
        # the index tip against the hand's end, where the fingers start: a
        # closed finger folds its tip back onto it. Measured against the
        # wrist, as it was, a finger that curls past the palm reads as
        # opening -- the tip swings on past the nearest point (78 -> 81 mm).
        return (rig.matrix_world @ pb["index_03_l"].tail - rig.matrix_world @ pb["hand_l"].tail).length
    def thumb_in(s="l"):
        # the thumb's tip against the middle finger's second joint: folded
        # across the front of the fingers, it lies on it
        return (rig.matrix_world @ pb["thumb_03_" + s].tail - _world(rig, "middle_02_" + s)).length
    g0 = grip(); t0 = thumb_in(); r0 = thumb_in("r")
    set_prop(rig, "CTRL_hand_l", "fist", 1.0); set_prop(rig, "CTRL_hand_r", "fist", 1.0)
    g1 = grip(); t1 = thumb_in(); r1 = thumb_in("r")
    # both hands: the fold is mirrored, and one sign for both swung the
    # right thumb out (found by the motion checks, 2026-09-24)
    if r0 - r1 < 0.030:
        fails.append("fist: fist=1 brought the right thumb only %.1f mm in across the fingers" % ((r0 - r1) * 1000))
    # closing the built claw to build_saud's fist brings the index tip well
    # in toward the wrist, and the thumb across the fingers
    # measured on Saud: the tip 42 -> 13 mm from the knuckles, the thumb's
    # tip 130 -> 47 mm from the middle finger
    if g0 - g1 < 0.015:
        fails.append("fist: fist=1 closed the index finger by only %.1f mm" % ((g0 - g1) * 1000))
    if t0 - t1 < 0.030:
        fails.append("fist: fist=1 brought the thumb only %.1f mm in across the fingers" % ((t0 - t1) * 1000))
    # 7 the pivot: moving it moves nothing; turning it turns him about it.
    # Stood on the lead foot's ball, a quarter turn must leave that ball
    # where it was and carry the other foot a long way round.
    reset(rig)
    ball = pb["ball_l"].head.copy()
    stand = Vector((ball.x, ball.y, 0.0))
    before = {n: _world(rig, n) for n in ("ball_l", "ball_r", "pelvis")}
    set_translation(rig, "CTRL_pivot", stand)
    drift = max((_world(rig, n) - before[n]).length for n in before)
    if drift > 0.0005:
        fails.append("pivot: moving CTRL_pivot, unturned, moved the body %.1f mm" % (drift * 1000))
    m = pb["CTRL_pivot"].matrix.copy()
    turn = Matrix.Rotation(math.radians(90.0), 4, "Z")
    m = Matrix.Translation(stand) @ turn @ Matrix.Translation(-stand) @ m
    pb["CTRL_pivot"].matrix = m; _update()
    stayed = (_world(rig, "ball_l") - before["ball_l"]).length
    went = (_world(rig, "ball_r") - before["ball_r"]).length
    if stayed > 0.002 * scale:
        fails.append("pivot: a quarter turn about the lead ball moved that ball %.1f mm" % (stayed * 1000))
    if went < 0.15 * scale:
        fails.append("pivot: a quarter turn about the lead ball moved the rear foot only %.1f cm" % (went * 100))
    # 8 the snaps: a limb handed between IK and FK does not move
    for limb, ctrl_side, probe in (("hand", "CTRL_hand_l", Vector((0.05, -0.18, 0.08))),
                                   ("foot", "CTRL_foot_l", Vector((0.04, -0.10, 0.12)))):
        reset(rig)
        set_translation(rig, ctrl_side, pb[ctrl_side].matrix.translation + probe)
        bones = _chain(limb, "l")[2]
        was = {n: pb[n].matrix.copy() for n in bones}
        snap_fk_to_ik(rig, "l", limb)
        off = max(max(abs(v) for row in (pb[n].matrix - was[n]) for v in row) for n in bones)
        if off > 0.0005:
            fails.append("snap: %s IK->FK moved the chain by %.2f (matrix terms)" % (limb, off))
        # now pose it in FK and hand it back to IK
        pb[bones[1]].rotation_mode = "QUATERNION"
        pb[bones[1]].rotation_quaternion = pb[bones[1]].rotation_quaternion @ Quaternion((1, 0, 0), math.radians(-12.0))
        _update()
        was = {n: pb[n].matrix.copy() for n in bones[:3]}
        snap_ik_to_fk(rig, "l", limb)
        off = max(max(abs(v) for row in (pb[n].matrix - was[n]) for v in row) for n in bones[:3])
        if off > 0.002:
            fails.append("snap: %s FK->IK moved the chain by %.3f (matrix terms)" % (limb, off))
    # 9 the pins: the pole swings the joint and leaves the end where it is,
    # and a target out of reach straightens the limb along the line to it
    # instead of stretching or popping sideways
    for ctrl, pole, joint, end, lower, upper in (
            ("CTRL_foot_l", "CTRL_knee_l", "calf_l", "foot_l", "calf_l", "thigh_l"),
            ("CTRL_hand_l", "CTRL_elbow_l", "lowerarm_l", "hand_l", "lowerarm_l", "upperarm_l")):
        reset(rig)
        # bend it first, so there is a joint to swing
        set_translation(rig, ctrl, pb[ctrl].matrix.translation + (pb[upper].head - pb[ctrl].matrix.translation) * 0.30)
        j0, e0 = pb[joint].head.copy(), pb[end].head.copy()
        side_dir = Vector((0.30, 0, 0))
        set_translation(rig, pole, pb[pole].matrix.translation + side_dir)
        j1, e1 = pb[joint].head.copy(), pb[end].head.copy()
        if (e1 - e0).length > 0.001:
            fails.append("pin: moving %s moved %s %.1f mm" % (pole, end, (e1 - e0).length * 1000))
        if (j1 - j0).dot(side_dir.normalized()) < 0.02:
            fails.append("pin: moving %s 30 cm out swung %s only %.1f cm toward it" % (
                pole, joint, (j1 - j0).dot(side_dir.normalized()) * 100))
        reset(rig)
        top = pb[upper].head.copy()
        length = pb[upper].bone.length + pb[lower].bone.length
        target = top + (pb[ctrl].matrix.translation - top).normalized() * (length + 0.40)
        set_translation(rig, ctrl, target)
        reach = (pb[lower].tail - top).length
        line = (pb[lower].tail - top).normalized().angle((target - top).normalized())
        if reach > length + 0.001:
            fails.append("pin: out of reach, %s stretched %.1f mm past its length" % (upper[:-2], (reach - length) * 1000))
        if math.degrees(line) > 2.0:
            fails.append("pin: out of reach, %s pointed %.1f deg off the line to its target" % (upper[:-2], math.degrees(line)))
    # 6 what would ship
    reset(rig)
    from hero.pipeline import MANNEQUIN
    ship = {b.name for b in rig.data.bones if not b.name.startswith(CTRL_PREFIX)}
    if ship != MANNEQUIN:
        fails.append("export set: extra %s, missing %s" % (sorted(ship - MANNEQUIN), sorted(MANNEQUIN - ship)))
    deform = {b.name for b in rig.data.bones if b.use_deform}
    bad = [g.name for g in mesh.vertex_groups if g.name not in deform]
    if bad:
        fails.append("the mesh is weighted to non-deform bones: %s" % bad[:6])
    reset(rig)
    assert not fails, "the control rig does not do what it says:\n  " + "\n  ".join(fails)
    print("control rig verified: hand IK reaches, fk switch, toe and heel roll, look, fist, pivot, "
          "IK/FK snap, pole pins, no stretch, export set")
    return True


# =================================================================== export
def strip_for_export(rig, mesh, keep_pose=False):
    """Back to the mannequin: every control gone, every constraint gone,
    the deform bones left exactly where the rest pose has them -- or, with
    `keep_pose`, where a bake just put them. The .blend saved before this
    call is the animator's copy; this is the engine's."""
    if not keep_pose:
        reset(rig)
    _pose_mode(rig)
    for b in rig.pose.bones:
        for c in list(b.constraints):
            try: c.driver_remove("influence")
            except Exception: pass
            b.constraints.remove(c)
        try: b.driver_remove("rotation_euler")
        except Exception: pass
    _edit_mode(rig)
    for b in [b for b in rig.data.edit_bones if b.name.startswith(CTRL_PREFIX)]:
        rig.data.edit_bones.remove(b)
    _object_mode(rig)
    for pbone in rig.pose.bones:
        pbone.custom_shape = None
    if "WGT" in bpy.data.collections:
        coll = bpy.data.collections["WGT"]
        for o in list(coll.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(coll)
    for name in ("CTRL", "MCH"):
        c = rig.data.collections.get(name)
        if c: rig.data.collections.remove(c)
    return {b.name for b in rig.data.bones}


def bake_pose(rig, frame=1):
    """The visual pose written onto every shipping bone's own channels at
    `frame`, its constraints dropped by the bake. nla.bake works on the
    SELECTED bones, and a bone in a hidden collection cannot be selected:
    DEF and MCH are hidden for the animator, so the first version of this
    baked the controls -- which are then stripped -- and nothing else, and
    the deform bones fell back to rest the moment their constraints went."""
    shown = {c.name: c.is_visible for c in rig.data.collections}
    for c in rig.data.collections:
        c.is_visible = True
    _pose_mode(rig)
    bpy.ops.pose.select_all(action="SELECT")
    n = sum(1 for b in rig.pose.bones if b.select)
    assert n == len(rig.pose.bones), "the bake would miss %d bones" % (len(rig.pose.bones) - n)
    bpy.ops.nla.bake(frame_start=frame, frame_end=frame, only_selected=True, visual_keying=True,
                     clear_constraints=True, bake_types={"POSE"})
    _object_mode(rig)
    for c in rig.data.collections:
        c.is_visible = shown[c.name]
    left = sum(len(b.constraints) for b in rig.pose.bones)
    assert left == 0, "the bake left %d constraints in place" % left


def roundtrip(blend, out=None):
    """Pose a fighter through his controls, bake that onto the deform bones,
    strip, export an FBX, read it back into a fresh scene and measure every
    deform bone's world position against what Blender had. This is what
    leaves the tool; nothing else is."""
    import build_saud as legacy
    bpy.ops.wm.open_mainfile(filepath=blend)
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    mesh = next(o for o in bpy.data.objects if o.type == "MESH" and o.parent == rig)
    stance(rig, legacy.GUARD, mesh)
    set_prop(rig, "CTRL_hand_l", "fist", 1.0); set_prop(rig, "CTRL_hand_r", "fist", 1.0)
    set_prop(rig, "CTRL_foot_r", "roll", 0.6)
    want = {b.name: (rig.matrix_world @ b.matrix).translation.copy() for b in rig.pose.bones if b.bone.use_deform}
    bake_pose(rig)
    # the bake wrote the deform bones' own channels; keep them (a reset here
    # zeroed them and the baked action did not put them back)
    strip_for_export(rig, mesh, keep_pose=True)
    bpy.context.scene.frame_set(1); _update()
    baked = {b.name: (rig.matrix_world @ b.matrix).translation.copy() for b in rig.pose.bones if b.bone.use_deform}
    bake_err = max((baked[k] - want[k]).length for k in want)
    # the FBX is evidence, not a deliverable: it goes with the build's
    # checkpoints (hero/build is out of the tree), not beside the rig
    out = out or os.path.join(HERE, "hero", "build", "roundtrip_%s.fbx" % os.path.splitext(os.path.basename(blend))[0])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT"); rig.select_set(True); mesh.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.fbx(filepath=out, use_selection=True, apply_unit_scale=True, global_scale=1.0,
                             apply_scale_options="FBX_SCALE_UNITS", add_leaf_bones=False,
                             primary_bone_axis="Y", secondary_bone_axis="X", object_types={"ARMATURE", "MESH"},
                             bake_anim=True, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False, bake_anim_step=1.0,
                             path_mode="RELATIVE", embed_textures=False)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=out)
    rig2 = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    names = {b.name for b in rig2.data.bones}
    from hero.pipeline import MANNEQUIN
    # Blender's own importer puts the keys one frame later (see the boss
    # motion commit); the posed frame is 2 here
    worst = 0.0; worst_bone = None
    for f in (1, 2):
        bpy.context.scene.frame_set(f); _update()
        got = {b.name: (rig2.matrix_world @ b.matrix).translation.copy() for b in rig2.pose.bones if b.name in want}
        err = max((got[k] - want[k]).length for k in got)
        if worst_bone is None or err < worst:
            worst = err; worst_bone = max(got, key=lambda k: (got[k] - want[k]).length)
    print("roundtrip   : bake error %.2f mm, %d bones in the fbx (%s), posed round-trip error %.2f mm (worst %s)" % (
        bake_err * 1000, len(names), "the mannequin's" if names == MANNEQUIN else "NOT THE MANNEQUIN", worst * 1000, worst_bone))
    assert names == MANNEQUIN, "the exported skeleton is not the mannequin's: %s" % sorted(names ^ MANNEQUIN)[:8]
    assert bake_err < 0.002, "baking the controls onto the deform bones moved them %.1f mm" % (bake_err * 1000)
    assert worst < 0.003, "the posed export came back %.1f mm off on %s" % (worst * 1000, worst_bone)
    return dict(bones=len(names), bake_mm=bake_err * 1000, roundtrip_mm=worst * 1000)


# ===================================================================== bite
def bite(blend):
    """Each verify() check, made to fail by breaking what it guards. A check
    that cannot fail is not a check."""
    def load():
        bpy.ops.wm.open_mainfile(filepath=blend)
        rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
        mesh = next(o for o in bpy.data.objects if o.type == "MESH" and o.parent == rig)
        return rig, mesh
    cases = []
    def case(label, sabotage, expect):
        rig, mesh = load()
        sabotage(rig, mesh)
        try:
            verify(rig, mesh)
            cases.append((label, False, "did not bite"))
        except AssertionError as e:
            msg = str(e)
            cases.append((label, expect in msg, msg.split("\n")[1].strip() if "\n" in msg else msg[:80]))
    def kill_ik(rig, mesh):
        c = rig.pose.bones["lowerarm_l"].constraints["IK"]; c.driver_remove("influence"); c.influence = 0.0
    def kill_switch(rig, mesh):
        c = rig.pose.bones["lowerarm_l"].constraints["IK"]; c.driver_remove("influence"); c.influence = 1.0
    def flip_toe(rig, mesh):
        fc = rig.animation_data.drivers.find('pose.bones["MCH_toe_l"].rotation_euler', index=0)
        fc.driver.expression = fc.driver.expression.replace("1 *", "-1 *", 1) if fc.driver.expression.startswith("1 *") else fc.driver.expression.replace("-1 *", "1 *", 1)
    def toes_follow_toe(rig, mesh):
        # hang the flat-toes helper under the toe pivot: the toes tip with the foot
        _edit_mode(rig); eb = rig.data.edit_bones; eb["MCH_toes_l"].parent = eb["MCH_toe_l"]; _object_mode(rig)
    def kill_look(rig, mesh):
        c = rig.pose.bones["head"].constraints["LOOK"]; c.driver_remove("influence"); c.influence = 0.0
    def look_always(rig, mesh):
        c = rig.pose.bones["head"].constraints["LOOK"]; c.driver_remove("influence"); c.influence = 1.0
    def kill_fist(rig, mesh):
        for k in (1, 2, 3):
            fc = rig.animation_data.drivers.find('pose.bones["index_%02d_l"].rotation_euler' % k, index=0)
            rig.animation_data.drivers.remove(fc)
    def kill_thumb(rig, mesh):
        for k in (1, 2, 3):
            for axis in (0, 2):
                fc = rig.animation_data.drivers.find('pose.bones["thumb_%02d_l"].rotation_euler' % k, index=axis)
                if fc:
                    rig.animation_data.drivers.remove(fc)
    def extra_bone(rig, mesh):
        _edit_mode(rig); b = rig.data.edit_bones.new("jaw"); b.head = (0, 0, 1.6); b.tail = (0, 0, 1.65); b.use_deform = False; _object_mode(rig)
    def bad_weights(rig, mesh):
        mesh.vertex_groups.new(name="CTRL_root")
    def kill_unpivot(rig, mesh):
        rig.pose.bones["MCH_unpivot"].constraints["UNPIVOT"].mute = True
    def twist_pole(rig, mesh):
        c = rig.pose.bones["lowerarm_l"].constraints["IK"]; c.pole_angle += math.radians(90.0)
    def kill_pole(rig, mesh):
        rig.pose.bones["calf_l"].constraints["IK"].pole_target = None
    def let_stretch(rig, mesh):
        for n in ("thigh_l", "calf_l"):
            rig.pose.bones[n].ik_stretch = 0.3
        rig.pose.bones["calf_l"].constraints["IK"].use_stretch = True
    case("hand IK reaches",        kill_ik,        "hand IK")
    case("fk switch",              kill_switch,    "fk switch")
    case("toe roll sign",          flip_toe,       "toe roll")
    case("toes stay flat",         toes_follow_toe, "floor plane")
    case("look on",                kill_look,      "look=1")
    case("look off",               look_always,    "look=0")
    case("fist",                   kill_fist,      "fist")
    case("thumb folds",            kill_thumb,     "thumb")
    case("export set",             extra_bone,     "export set")
    case("deform weights",         bad_weights,    "non-deform")
    case("pivot",                  kill_unpivot,   "pivot: moving")
    case("FK->IK snap",            twist_pole,     "snap: hand FK->IK")
    case("pole pin",               kill_pole,      "pin: moving CTRL_knee_l")
    case("no stretch",             let_stretch,    "stretched")
    print("\n%-22s %s" % ("check", "when its mechanism is broken"))
    for label, ok, msg in cases:
        print("  %-20s %s  %s" % (label, "BITES " if ok else "SILENT", msg[:90]))
    n = sum(1 for _, ok, _ in cases if ok)
    print("  %d of %d bite" % (n, len(cases)))
    return n == len(cases)


def refresh(blend, scale=None):
    """Rebuild the control layer of an animator's file in place, from this
    file as it is now: strip every control, put add_ik's four constraints
    back, build, verify, save. The mesh, its weights and its materials are
    not touched -- the controls never were part of what ships -- so a rig
    improvement reaches every man's file in seconds rather than a twenty-
    minute rebuild each. `scale` is the man's height factor for verify();
    by default it is read off the skeleton against Saud's own."""
    import build_saud as legacy
    bpy.ops.wm.open_mainfile(filepath=blend)
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    mesh = next(o for o in bpy.data.objects if o.type == "MESH" and o.parent == rig)
    strip_for_export(rig, mesh)
    for o in [o for o in bpy.data.objects if o.name.startswith(("Pole_Knee", "Pole_Elbow"))]:
        bpy.data.objects.remove(o, do_unlink=True)
    legacy.add_ik(rig)
    made = build(rig, mesh)
    if scale is None:
        # his head joint's height against Saud's -- the joint table, which
        # in a fresh process is Saud's own (a build mutates it; this does not)
        scale = rig.data.bones["head"].head_local.z / legacy.J["head"][0][2]
    verify(rig, mesh, scale=scale)
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    print("refreshed   : %s (%d controls, scale %.3f)" % (os.path.basename(blend), made["controls"], scale))
    return made


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--refresh" in a:
        for path in a[a.index("--refresh") + 1:]:
            if not path.startswith("--"):
                refresh(os.path.abspath(path))
        sys.exit(0)
    if "--roundtrip" in a:
        print(roundtrip(os.path.abspath(a[a.index("--roundtrip") + 1])))
    elif "--bite" in a:
        sys.exit(0 if bite(os.path.abspath(a[a.index("--bite") + 1])) else 1)
    else:
        print(__doc__)
