"""Motion authored THROUGH the control rig, then baked to the 62 bones.

    import motion_ik as M
    rig = M.make_rig()                   the mannequin, add_ik, the control layer
    au = M.Author(rig)
    au.begin(); au.fk_body(aims, ...)    a body shape, aimed bone by bone (FK)
    au.leg(s, matrix, pole, roll)        a foot put somewhere, and the leg solved
    au.settle(planted)                   the hips lowered only as far as a
                                         planted leg needs to reach its foot
    au.arm(s, matrix, pole)              a hand put somewhere, the arm solved
    au.pivot(point, angle)               the body turned about a floor point
    loc, world = au.record()             the deform bones, as the engine will get them
    M.to_actions(rig, authored)          strip the controls; one action a clip

WHY. build_motion.py used to pose every clip in FK and plant the feet
afterwards by sliding the whole man up or down until his lowest foot was on
the floor. Up and down is all that fixed. Measured on the seventeen boss
clips it wrote: the support foot skated 30-35 cm across the floor on every
kick and knee, 44-54 cm round a circle on the spinning kick (it turned about
the origin, not the ball of the foot it stands on), the rear foot 9-13 cm on
every cross and hook (the hips' turn swung both legs with them), and the
guard idle's sway carried both feet 2.2 cm side to side. Here a planted foot
is an IK target that does not move, so it cannot slide: the hips and the
knees do what a real man's do to keep it there.

WHAT IS KEPT. Every strike's SHAPE is still build_motion's: its aims, its
torso lean and twist, the browser's timing and ease. The FK pose is struck
first, exactly as before, and read -- then each limb is handed to the rig
at the place and bend the FK pose gave it. What changes is where the feet
are allowed to be, and, for a jab and a cross, that the fist travels a
straight line to where the FK pose would have put it, instead of the arc a
swinging shoulder draws: a jab that arcs is a slap.

WHAT LEAVES. to_actions() strips the whole control layer (rig_full_ik's own
strip_for_export) and writes each frame's recorded local transforms onto the
mannequin's 62 bones. bake_error() replays every frame and measures every
bone against what the rig had, so what ships is proved to be what was
authored.
"""
import os, sys, math
import bpy
from mathutils import Vector, Matrix, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SIDES = ("l", "r")
# build_motion's --bite breaks the hands through this (it cannot reach the
# rig's own state any other way): "fists" leaves them open
SABOTAGE_HANDS = set()
LIMB_CHAIN = ["clavicle_l", "upperarm_l", "lowerarm_l", "hand_l",
              "clavicle_r", "upperarm_r", "lowerarm_r", "hand_r",
              "thigh_l", "calf_l", "foot_l", "thigh_r", "calf_r", "foot_r"]
# build_motion's lean shares, the browser's one lean spread up the spine
LEAN_SHARES = (("spine_01", 0.30), ("spine_02", 0.36), ("spine_03", 0.34))


def upd():
    bpy.context.view_layer.update()


def make_rig():
    """The rig every clip is authored on: the joint table's own skeleton,
    fingers, add_ik, and rig_full_ik's control layer over it. No mesh --
    nothing here is judged on a mesh, and the controls do not need one."""
    import build_saud as L
    import rig_full_ik as CR
    from hero import anatomy as A, rig_export as R
    L.reset_scene()
    _, jl = A.hand()
    rig = L.build_armature()
    R.add_finger_bones(rig, jl)
    L.add_ik(rig)
    CR.build(rig, None)
    return rig


def pole_from(a, b, c, fallback):
    import build_saud as L
    return L._pole_from(a, b, c, fallback)


def foot_turn(now, guard):
    """How a foot the FK pose turned differs from the guard's: its yaw about
    the vertical (a cross turns the rear heel out) and how far its heel came
    up, as the rig's toe-roll fraction. Both are then applied to a PLANTED
    foot about the ball, which is what a real foot does."""
    import rig_full_ik as CR
    yn = now.col[1].xyz.normalized(); yg = guard.col[1].xyz.normalized()
    hn = Vector((yn.x, yn.y, 0.0)); hg = Vector((yg.x, yg.y, 0.0))
    yaw = 0.0
    if hn.length > 1e-6 and hg.length > 1e-6:
        hn.normalize(); hg.normalize()
        yaw = math.atan2(hg.cross(hn).z, hg.dot(hn))
    pitch_n = math.asin(max(-1.0, min(1.0, -yn.z)))
    pitch_g = math.asin(max(-1.0, min(1.0, -yg.z)))
    roll = max(0.0, pitch_n - pitch_g) / CR.TOE_ROLL
    return yaw, min(1.0, roll)


class Author:
    """One frame at a time, on the control rig. Everything is armature
    space; the rig stands at the origin, so that is world space too."""

    def __init__(self, rig):
        import build_saud as L
        from hero.pipeline import MANNEQUIN
        self.rig = rig
        self.pb = rig.pose.bones
        self.order = [n for n in L._hierarchy_order(rig) if n in MANNEQUIN]
        self.guard = None

    # ------------------------------------------------------------ switches
    def _fk(self, value, limbs=("hand", "foot")):
        for s in SIDES:
            for limb in limbs:
                self.pb["CTRL_%s_%s" % (limb, s)]["fk"] = float(value)
        self.rig.update_tag(); upd()

    def begin(self):
        """Every control home, every limb in FK: a clean page for the frame."""
        import rig_full_ik as CR
        CR.reset(self.rig)
        # every clip is thrown with closed fists (build_saud.FIST_*); until
        # 2026-09-24 none set it, and every clip carried the built claw
        if "fists" not in SABOTAGE_HANDS:
            for s in SIDES:
                self.pb["CTRL_hand_%s" % s]["fist"] = 1.0
        self._fk(1.0)

    # ---------------------------------------------------------------- body
    def fk_body(self, aims, lean=0.0, twist=None, carry=()):
        """The body shape, bone by bone, as build_motion always struck it:
        aimed, then the torso leaned and twisted, then the limbs put back on
        their aims over the moved torso. The pelvis follows CTRL_hips (Copy
        Transforms), so a twist asked of the pelvis is given to CTRL_hips.

        `carry` names aims that ride the chest instead of holding their world
        direction: turned by whatever the lean and twist turned spine_03. The
        covering hand of a cross or a hook is one -- held to the world, the
        shoulders turned 60 degrees out from under it and left the fist
        behind the face (2026-09-25)."""
        import rig_full_ik as CR
        pb = self.pb
        CR._aim(self.rig, aims)
        chest0 = pb["spine_03"].matrix.to_quaternion()
        if lean:
            for nm, share in LEAN_SHARES:
                pb[nm].rotation_quaternion = pb[nm].rotation_quaternion @ Quaternion((1, 0, 0), lean * share)
        for nm, amt in (twist or {}).items():
            tgt = "CTRL_hips" if nm == "pelvis" else nm
            pb[tgt].rotation_quaternion = pb[tgt].rotation_quaternion @ Quaternion((0, 1, 0), amt)
        if twist:
            # The eyes stay on the man he is hitting: every twist below the
            # neck carried the head round with it, so at a cross's contact
            # he looked 60 degrees off his opponent (measured 2026-09-26).
            # The neck takes back 40 % of the turn and the head the rest.
            total = sum(twist.values())
            for nm, share in (("neck_01", 0.40), ("head", 0.60)):
                pb[nm].rotation_quaternion = pb[nm].rotation_quaternion @ Quaternion((0, 1, 0), -total * share)
        upd()
        if lean or twist:
            turn = pb["spine_03"].matrix.to_quaternion() @ chest0.inverted()
            back = {n: aims[n] for n in LIMB_CHAIN + ["palm_l", "palm_r"] if n in aims}
            for n in carry:
                if n in back:
                    back[n] = tuple(turn @ Vector(back[n]))
            CR._aim(self.rig, back)

    def move_hips(self, delta):
        m = self.pb["CTRL_hips"].matrix.copy()
        m.translation = m.translation + Vector(delta)
        self.pb["CTRL_hips"].matrix = m; upd()

    def tilt_hips(self, angle, axis="X"):
        """Turn the hips -- and everything above them -- about a world axis
        through the pelvis joint. The legs are IK and do not come with it."""
        m = self.pb["CTRL_hips"].matrix.copy()
        at = m.translation.copy()
        r = Matrix.Translation(at) @ Matrix.Rotation(angle, 4, axis) @ Matrix.Translation(-at)
        self.pb["CTRL_hips"].matrix = r @ m; upd()

    def read(self):
        """Where the FK pose put everything: the end bones' matrices and the
        three joints of each limb."""
        pb, out = self.pb, {}
        for s in SIDES:
            out["hand_" + s] = pb["hand_" + s].matrix.copy()
            out["foot_" + s] = pb["foot_" + s].matrix.copy()
            out["ball_" + s] = pb["ball_" + s].head.copy()
            out["sh_" + s], out["el_" + s], out["wr_" + s] = (
                pb["upperarm_" + s].head.copy(), pb["lowerarm_" + s].head.copy(), pb["lowerarm_" + s].tail.copy())
            out["hip_" + s], out["kn_" + s], out["an_" + s] = (
                pb["thigh_" + s].head.copy(), pb["calf_" + s].head.copy(), pb["calf_" + s].tail.copy())
        out["pelvis"] = pb["pelvis"].matrix.copy()
        out["head"] = pb["head"].head.copy()
        out["head_tail"] = pb["head"].tail.copy()
        out["head_m"] = pb["head"].matrix.copy()
        return out

    # --------------------------------------------------------------- limbs
    def leg(self, s, matrix, pole, roll=0.0):
        """The foot control to `matrix` (the foot bone's own frame: they
        share a rest), the knee's pole to `pole`, the toe roll to `roll`,
        and the leg to IK."""
        import rig_full_ik as CR
        c = self.pb["CTRL_foot_" + s]
        c["roll"] = float(roll)
        c.matrix = matrix.copy(); upd()
        CR.set_translation(self.rig, "CTRL_knee_" + s, pole)
        c["fk"] = 0.0
        self.rig.update_tag(); upd()

    def arm(self, s, matrix, pole):
        import rig_full_ik as CR
        c = self.pb["CTRL_hand_" + s]
        c.matrix = matrix.copy(); upd()
        CR.set_translation(self.rig, "CTRL_elbow_" + s, pole)
        c["fk"] = 0.0
        self.rig.update_tag(); upd()

    def planted(self, s, yaw=0.0, guard=None):
        """The guard's own foot control, turned `yaw` about the ball -- a
        foot that pivots on the spot and does not travel."""
        g = guard or self.guard
        m = g["ctrl_foot_" + s]
        b = g["ball_" + s]
        r = Matrix.Translation(b) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Translation(-b)
        return r @ m

    def settle(self, planted, limit=0.40):
        """Lower the hips until every planted leg reaches its foot. A leg is
        not longer than straight: an FK shape whose hips were high enough
        for a foot that has since stopped sliding has to come down to meet
        it. Measured, not solved: the gap between the ankle the solver
        reached and the one it was asked for is how far to drop. Returns the
        total drop, which build_motion reports."""
        drop = 0.0
        for _ in range(12):
            upd()
            gap = 0.0
            for s in planted:
                want = self.pb["MCH_ankle_" + s].head
                got = self.pb["calf_" + s].tail
                gap = max(gap, (got - want).length)
            if gap < 0.0003:
                break
            step = gap * 1.05 + 0.0002
            self.move_hips((0.0, 0.0, -step))
            drop += step
            assert drop < limit, "settle: the hips came down %.0f cm and a planted leg still cannot reach" % (drop * 100)
        return drop

    def reach_gap(self, sides, which="leg"):
        """How far each IK end missed its control, for the checks."""
        gap = 0.0
        for s in sides:
            if which == "leg":
                gap = max(gap, (self.pb["calf_" + s].tail - self.pb["MCH_ankle_" + s].head).length)
            else:
                gap = max(gap, (self.pb["lowerarm_" + s].tail - self.pb["CTRL_hand_" + s].head).length)
        return gap

    def pivot(self, point, angle):
        """The whole body turned `angle` about the vertical through `point`.
        Last, after every control is placed: the controls hang under the
        pivot, and a control placed after it had turned would be placed in
        the turned frame."""
        pb = self.pb["CTRL_pivot"]
        p = Vector((point[0], point[1], 0.0))
        pb.matrix = Matrix.Translation(p) @ Matrix.Rotation(angle, 4, "Z") @ pb.bone.matrix_local
        upd()

    # ------------------------------------------------------------- output
    def record(self):
        """Every shipping bone's local transform -- what the channels have
        to hold for the bone to land where the rig put it -- and every
        shipping bone's head, for bake_error() and the checks."""
        rig, pb = self.rig, self.pb
        upd()
        loc = {}
        for n in self.order:
            m = rig.convert_space(pose_bone=pb[n], matrix=pb[n].matrix, from_space="POSE", to_space="LOCAL")
            l, q, _s = m.decompose()
            loc[n] = (l.copy(), q.copy())
        world = {n: (rig.matrix_world @ pb[n].matrix).translation.copy() for n in self.order}
        return loc, world

    # ------------------------------------------------------ the guard itself
    def capture_guard(self, aims, lean=0.0):
        """The guard as the reference every clip of that stance plants on:
        the FK guard, its feet handed to IK where they stand, its hands
        where the FK put them. Returns the dict `planted()` reads."""
        self.begin()
        self.fk_body(aims, lean=lean)
        fk = self.read()
        # The floor: where the ball joint sits when he stands at rest with
        # his soles on z = 0 -- 2.4 cm. The FK guard never stood on it: its
        # lead ball is 5.2 cm up and its rear 4.0, and the FK build only
        # ever brought his feet down to "ground", which it took to be the
        # guard's own lowest ball -- so every clip it wrote hovered 1.6 cm
        # with the lead foot another 1.2 above that. Both feet go on the
        # floor here.
        floor = self.pb["ball_l"].bone.head_local.z
        # dz: how far the FK guard's body comes down to stand on that floor,
        # the same grounding a strike frame gives it, so every clip's
        # neutral pose is one pose
        g = {"fk": fk, "ground": floor, "dz": floor - min(fk["ball_l"].z, fk["ball_r"].z)}
        for s in SIDES:
            down = Matrix.Translation((0.0, 0.0, floor - fk["ball_" + s].z))
            g["ctrl_foot_" + s] = down @ fk["foot_" + s]
            g["ball_" + s] = down @ fk["ball_" + s]
            g["hand_" + s] = fk["hand_" + s].copy()
            g["hip_" + s] = fk["hip_" + s].copy()
        g["pelvis"] = fk["pelvis"].copy()
        g["head"] = fk["head"].copy()
        self.guard = g
        return g


def to_actions(rig, authored):
    """Strip the control layer and write each clip's recorded frames onto
    the mannequin's bones as keys. `authored` is [(clip, [(loc, world),
    ...]), ...]. Quaternions are kept on one hemisphere frame to frame, or
    a sign flip between two keys interpolates the long way round."""
    import rig_full_ik as CR
    CR.strip_for_export(rig, None)
    for b in rig.pose.bones:
        b.rotation_mode = "QUATERNION"
    made = []
    for c, frames in authored:
        act = bpy.data.actions.new(c["name"])
        rig.animation_data_create()
        rig.animation_data.action = act
        prev = {}
        for f, (loc, _world) in enumerate(frames):
            for n, (l, q) in loc.items():
                q = q.copy()
                if n in prev and prev[n].dot(q) < 0.0:
                    q.negate()
                prev[n] = q
                pb = rig.pose.bones[n]
                pb.location = l
                pb.rotation_quaternion = q
                pb.keyframe_insert("location", frame=f + 1)
                pb.keyframe_insert("rotation_quaternion", frame=f + 1)
        rig.animation_data.action = None
        made.append((c, act, frames))
    return made


def bake_error(rig, made):
    """Replay every frame of every clip on the plain skeleton and measure
    every bone against where the control rig had it. What ships is only
    what was authored if this is zero."""
    worst, where = 0.0, None
    for c, act, frames in made:
        rig.animation_data.action = act
        for f, (_loc, world) in enumerate(frames):
            bpy.context.scene.frame_set(f + 1); upd()
            for n, w in world.items():
                e = ((rig.matrix_world @ rig.pose.bones[n].matrix).translation - w).length
                if e > worst:
                    worst, where = e, "%s frame %d %s" % (c["name"], f + 1, n)
    rig.animation_data.action = None
    return worst, where
