#!/usr/bin/env python3
"""JAZIRAT AL-QIRUD -- the monkey island: the monkey's and the gorilla's motion.

Asked 2026-10-02 with the island ("... monkeys as enemy and big gorilla as
map boss ... full ik"). build_primates.py makes the two creatures; this
moves them: every clip the engine plays on a fighter, posed through IK on
their own skeletons, written to Content/Animation/Island/A_<Set>_<Clip>.fbx
with a manifest, DT_IslandMotion.csv.

    python3 build_primate_motion.py            build, check, export, draw (bpy)
    python3 build_primate_motion.py --bite     each rule broken once (bpy)

THE CLIPS, for each: Guard (a loop), the locomotion (below), Block (a
loop), Hit_Light, Hit_Heavy, Down, GetUp, Death, Victory, and its strikes.

THE LOCOMOTION (2026-10-04, the 360 locomotion's binding spec, section 1):
eight directions against the facing -- Fwd, FwdLeft, Left, BackLeft, Back,
BackRight, Right, FwdRight (0, 45, 90, 135, 180, -135, -90, -45 degrees,
+ toward his left) -- in two tiers, every one a loop in place:
    Walk_<Dir>  the walk tier, struck at WALK_SHARE (0.45) of his PACE: the
                feet alternate, double support, never both off the floor
    Run_<Dir>   the run tier, struck at his PACE (DT_IslandFighters
                MoveSpeed): what the four old Walk_* were; a sideways or
                diagonal run is a gallop, the lead foot first
One cycle length per creature for all sixteen (the monkey quick, 0.40 s;
the gorilla heavy, 0.667 s), so a change of direction or tier keeps the
phase. In no direction do the feet cross: each foot's phase against the
other's is chosen, per direction, as the one nearest an even alternation
that keeps them GAP_WANT apart (a side walk is a step-and-close), and a
sideways foot stands a little wider.
And the turns, in place from the guard, each exactly TURN_SECONDS long:
    Turn_L90, Turn_R90, Turn_180   the body starts turned BACK by the turn
                (Turn_L90 starts facing 90 degrees to his right) and steps
                round, a foot at a time, to face the root, ending in his
                guard (the Guard clip's first frame)
    Pivot_180   from Run_Fwd turned back (frame 0): plant, step round, and
                push off into Run_Fwd (its last frames are Run_Fwd's own)
A planted foot holds its spot and its turn; only a stepping foot moves.

A creature's strike is one of the
attack table's rows, so its timing, reach and damage are the row's
(DT_Attacks: startup, active, recovery) and the clip's contact frame is
where the startup ends; what the strike LOOKS like is the creature's own:
    Monkey   Jab   a quick claw jab at the belly
             Hook  a raking swipe across
             Kick  a two-footed hop-kick off the planted ball
    Gorilla  Cross   an overhead hammer-fist
             Hook    a backhand sweep
             Special the chest-beat and the two-fisted slam into the ground
The engine's other clips (the reactions by blow, the falls by blow) fall
back to Hit_Heavy / Down / Guard within the creature's own set
(SaudFeel::Fallback); dashes are Saud's alone.

HOW. Each frame is a pose: the pelvis moved and turned, the spine, neck,
head and tail bent (FK), and each limb's end -- wrist or ankle -- put at a
target and solved with an analytic two-bone IK toward a pole (knees forward
and out, elbows down and out), every bone swung from its rest direction
with no twist. A planted foot's target does not move, so it does not slide;
a walk's planted foot moves back under the body at the creature's pace
(the clips are in place; the runtime IK plants them). The pose is keyed on
the deform bones directly, so the export is the pose, and each FBX is read
back and compared bone by bone.

CHECKED (each rule broken once by --bite, on the monkey AND the gorilla,
after the unbroken build passes on both): a planted foot stays put; no
foot under the floor; every loop closes; every IK reach inside the limb
(nothing stretched); knees bend forward (along the body's own facing, so
a turned body is measured the way it faces); a strike's fist or foot gets
out in front by the contact frame; each clip as long as its row; Down
ends on the floor; the FBX read back. And the locomotion's: a loop's
planted feet travel at its tier's pace AND the opposite way to its
direction (the mean planted velocity within 8 % of the pace, its heading
within 8 degrees); a walk-tier foot lifts (3 % of his height) and the two
are never off the floor together; in no locomotion clip do the feet
cross (left of right by CROSS_MIN, in the frame of his own hips); one
cycle per tier; a turn lasts TURN_SECONDS to a frame, turns by its angle
within 5 degrees from a body turned back by it, ends within 1 cm of the
guard and never skates a planted foot; the pivot turns 180, starts as
Run_Fwd turned back and ends as Run_Fwd, within 1 cm.

THE n+1 CONVENTION. A loop is keyed with n + 1 frames, the last a copy of
the first (so the engine's sequence is n / 30 s and closes on itself); a
one-shot with n, its last frame its end pose. The manifest's Seconds is
n / 30 for both, Frames what was keyed.

NOT VERIFIED: no engine has imported a clip. The engine looks for a set's
clips in /Game/Animation/<folder>/A_<Set>_<Clip>; the island's folder is
"Island" (SaudMotionComponent, changed with the level).
"""

import csv
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "Content", "Animation", "Island")
RIGS = os.path.join(HERE, "rigs")
SHEET = os.path.join(ROOT, "Docs", "renders", "island-motion.png")
FPS = 30
SABOTAGE = set()

# the creatures' own pace (cm/s): their RUN tier is struck at it, and the
# level's fighter table carries the same number (DT_IslandFighters.csv
# MoveSpeed); the walk tier at WALK_SHARE of it (SaudSteer::WalkShare)
PACE = dict(Monkey=300.0, Gorilla=260.0)
WALK_SHARE = 0.45
# one cycle (s) for every loop of both tiers, so a change of direction or of
# tier can keep the phase: the monkey's quick, the gorilla's heavy
CYCLE = dict(Monkey=0.40, Gorilla=0.66)
# the share of a cycle a foot is down: the run's are the old walks' (a
# flight between steps; the planted travel, pace x cycle x duty, inside the
# leg's reach), the walk's over a half, so a foot is always down
DUTY = dict(Monkey=dict(Walk=0.68, Run=0.40), Gorilla=dict(Walk=0.72, Run=0.45))
LIFT = dict(Monkey=dict(Walk=0.06, Run=0.10), Gorilla=dict(Walk=0.05, Run=0.10))    # x H, the swing's top
WIDEN = dict(Monkey=0.02, Gorilla=0.01)        # x H, each foot out, times the share of the way that is sideways
CROSS_MIN = 0.045                               # x H: left foot left of the right by this (the men's 8 cm on 1.8 m)
GAP_WANT = 1.5 * CROSS_MIN                      # x H: what a direction's phase lag aims to keep
LIFT_MIN = 0.03                                 # x H: a walk-tier foot lifts at least this
PACE_TOL, DIR_TOL = 0.08, 8.0                   # the planted speed: share of the pace, degrees off the way
# the eight directions, + toward his left (he faces -Y, his left is +X)
DIRS = (("Fwd", 0.0), ("FwdLeft", 45.0), ("Left", 90.0), ("BackLeft", 135.0),
        ("Back", 180.0), ("BackRight", -135.0), ("Right", -90.0), ("FwdRight", -45.0))
# the turns: seconds (the game's steering holds the turn this long) and the
# signed angle the body turns through (+ to his left); each starts turned
# back by it relative to the root and ends facing the root
TURN_SECONDS = dict(Turn_L90=0.50, Turn_R90=0.50, Turn_180=0.70, Pivot_180=0.45)
TURN_ANGLE = dict(Turn_L90=90.0, Turn_R90=-90.0, Turn_180=180.0, Pivot_180=-180.0)
TURN_TOL_DEG, GUARD_TOL = 5.0, 0.01
PIVOT_PUSH = 4                                  # the pivot's last frames: Run_Fwd's own, the push off
STRIKES = dict(Monkey=("Jab", "Hook", "Kick"), Gorilla=("Cross", "Hook", "Special"))
ATTACKS = os.path.join(ROOT, "Content", "Data", "DT_Attacks.csv")


def attack_rows():
    with open(ATTACKS) as f:
        return {r["Name"]: r for r in csv.DictReader(f)}


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2


def lerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def keys(t, pts):
    """Piecewise eased interpolation through (time, value) pairs."""
    if t <= pts[0][0]:
        return pts[0][1]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t <= t1:
            k = ease((t - t0) / max(t1 - t0, 1e-9))
            if isinstance(v0, tuple):
                return lerp(v0, v1, k)
            return v0 + (v1 - v0) * k
    return pts[-1][1]


class Rig:
    """The creature's armature, read once: rest matrices, hierarchy, the
    limbs' lengths. Poses it frame by frame."""

    FK_ORDER = ["root", "pelvis", "spine_01", "spine_02", "spine_03", "neck_01", "head",
                "clavicle_l", "clavicle_r"]

    def __init__(self, name):
        import bpy
        from mathutils import Vector
        self.bpy = bpy
        self.name = name
        bpy.ops.wm.open_mainfile(filepath=os.path.join(RIGS, name + ".blend"))
        self.arm = bpy.data.objects[name + "_Rig"]
        self.bones = self.arm.data.bones
        self.rest = {b.name: b.matrix_local.copy() for b in self.bones}
        self.parent = {b.name: (b.parent.name if b.parent else None) for b in self.bones}
        self.tails = [b.name for b in self.bones if b.name.startswith("tail_")]
        self.deform = [b.name for b in self.bones if b.use_deform]
        self.head = {b.name: b.head_local.copy() for b in self.bones}
        H = max(v.co.z for o in bpy.data.objects if o.type == "MESH" for v in o.data.vertices)
        self.H = H
        self.L = {}
        for s in ("l", "r"):
            self.L["arm_" + s] = ((self.head["lowerarm_" + s] - self.head["upperarm_" + s]).length,
                                  (self.head["hand_" + s] - self.head["lowerarm_" + s]).length)
            self.L["leg_" + s] = ((self.head["calf_" + s] - self.head["thigh_" + s]).length,
                                  (self.head["foot_" + s] - self.head["calf_" + s]).length)
        self.order = self._order()
        for pb in self.arm.pose.bones:
            pb.rotation_mode = "QUATERNION"
        self.mesh = [o for o in bpy.data.objects if o.type == "MESH"]
        Vector  # noqa

    def _order(self):
        out, seen = [], set()

        def visit(b):
            if b in seen:
                return
            p = self.parent[b]
            if p:
                visit(p)
            seen.add(b)
            out.append(b)
        for b in self.parent:
            visit(b)
        return out

    @staticmethod
    def two_bone(S, W, a, b, pole):
        """The middle joint for a chain S-(a)-M-(b)-W bending toward pole;
        returns (M, W reached, stretched?)."""
        d_vec = W - S
        d = d_vec.length
        stretched = d > (a + b) * 0.999 + 1e-5
        d = min(max(d, abs(a - b) + 1e-4), (a + b) * 0.999)
        u = d_vec.normalized()
        W2 = S + u * d
        v = pole - u * pole.dot(u)
        if v.length < 1e-6:
            v = u.orthogonal()
        v.normalize()
        ca = (a * a + d * d - b * b) / (2 * a * d)
        ca = min(max(ca, -1.0), 1.0)
        sa = math.sqrt(max(0.0, 1 - ca * ca))
        return S + (u * ca + v * sa) * a, W2, stretched

    def pose(self, P):
        """Armature-space matrices for every bone, from a pose dict:
            pelvis: (dx, dy, dz) metres, pelvis_rot: (pitch, roll, yaw) deg,
            spine: [pitch deg for spine_01..03], twist: deg about Z (shared),
            neck, head: pitch deg; head_yaw: deg;
            hand_l/r: wrist target (world), elbow_l/r: pole direction,
            foot_l/r: ankle target (world), knee_l/r: pole direction,
            foot_rot_l/r: (pitch, roll, yaw) deg of the foot,
            hand_rot_l/r: extra pitch deg on the hand, tail: [(pitch, yaw)]"""
        from mathutils import Matrix, Vector, Euler, Quaternion
        M = {}
        Q = {}
        stretched = []

        def rest_rot(b):
            return self.rest[b].to_quaternion()

        def place(b, head, q_world):
            Q[b] = q_world
            M[b] = Matrix.Translation(head) @ (q_world @ rest_rot(b)).to_matrix().to_4x4()

        def child_head(b):
            p = self.parent[b]
            return M[p] @ (self.rest[p].inverted() @ self.head[b])

        def eul(p, r, y):
            return Euler((math.radians(p), math.radians(r), math.radians(y)), "XYZ").to_quaternion()

        # the body's turn about the vertical: a limb's swing is taken in the
        # turned body's frame, so a pose turned whole (rotate_pose) comes out
        # turned whole, twist and all; with no turn it is the plain swing
        yq = Euler((0.0, 0.0, math.radians(P.get("pelvis_rot", (0, 0, 0))[2])), "XYZ").to_quaternion()
        yqi = yq.inverted()

        def swing(b, head, target):
            """b's rest direction swung onto head->target, no twist (in the body's turn)."""
            rest_dir = (self.rest[b].to_3x3() @ Vector((0, 1, 0))).normalized()
            q = yq @ rest_dir.rotation_difference(yqi @ (target - head).normalized())
            place(b, head, q)
            return q
        tw = P.get("twist", 0.0)
        for b in self.order:
            if b == "root":
                place(b, self.head[b], Quaternion())
            elif b == "pelvis":
                place(b, self.head[b] + Vector(P.get("pelvis", (0, 0, 0))), eul(*P.get("pelvis_rot", (0, 0, 0))))
            elif b.startswith("spine_"):
                k = int(b[-1]) - 1
                sp = P.get("spine", (0, 0, 0))
                place(b, child_head(b), Q[self.parent[b]] @ eul(sp[k], 0, tw / 3.0))
            elif b == "neck_01":
                place(b, child_head(b), Q["spine_03"] @ eul(P.get("neck", 0), 0, P.get("head_yaw", 0) * 0.4))
            elif b == "head":
                place(b, child_head(b), Q["neck_01"] @ eul(P.get("head", 0), 0, P.get("head_yaw", 0) * 0.6))
            elif b.startswith("clavicle"):
                place(b, child_head(b), Q["spine_03"])
            elif b.startswith("upperarm"):
                s = b[-1]
                S = child_head(b)
                a, bb = self.L["arm_" + s]
                Wt = Vector(P["hand_" + s])
                E, W, st = self.two_bone(S, Wt, a, bb, Vector(P.get("elbow_" + s, (0.6 if s == "l" else -0.6, 0.4, -0.7))))
                if st:
                    stretched.append(b)
                swing(b, S, E)
                self._w = getattr(self, "_w", {})
                self._w[s] = (E, W)
            elif b.startswith("lowerarm"):
                s = b[-1]
                E, W = self._w[s]
                swing(b, E, W)
            elif b.startswith("hand_end"):
                place(b, child_head(b), Q[self.parent[b]])
            elif b.startswith("hand"):
                s = b[-1]
                place(b, child_head(b), Q["lowerarm_" + s] @ eul(P.get("hand_rot_" + s, 0), 0, 0))
            elif b.startswith("thigh"):
                s = b[-1]
                Hh = child_head(b)
                a, bb = self.L["leg_" + s]
                At = Vector(P["foot_" + s])
                K, A, st = self.two_bone(Hh, At, a, bb, Vector(P.get("knee_" + s, (0.15 if s == "l" else -0.15, -1.0, 0.1))))
                if st:
                    stretched.append(b)
                swing(b, Hh, K)
                self._k = getattr(self, "_k", {})
                self._k[s] = (K, A)
            elif b.startswith("calf"):
                s = b[-1]
                K, A = self._k[s]
                swing(b, K, A)
            elif b.startswith("foot"):
                s = b[-1]
                place(b, child_head(b), eul(*P.get("foot_rot_" + s, (0, 0, 0))))
            elif b.startswith("ball"):
                place(b, child_head(b), Q["foot_" + b[-1]])
            elif b.startswith("tail_"):
                k = int(b[-1]) - 1
                tl = P.get("tail", [])
                p, y = tl[k] if k < len(tl) else (0, 0)
                place(b, child_head(b), Q[self.parent[b]] @ eul(p, 0, y))
            else:                                   # the IK bones: copies of what they stand for
                like = {"ik_foot_l": "foot_l", "ik_foot_r": "foot_r", "ik_hand_gun": "hand_r",
                        "ik_hand_l": "hand_l", "ik_hand_r": "hand_r"}.get(b)
                if like and like in M:
                    M[b] = M[like].copy()
                else:
                    M[b] = self.rest[b].copy()
        return M, stretched

    def key(self, M, frame):
        """Key every bone's basis so its armature-space matrix is M[b]."""
        for b in self.order:
            pb = self.arm.pose.bones[b]
            p = self.parent[b]
            if p:
                base = M[p] @ (self.rest[p].inverted() @ self.rest[b])
            else:
                base = self.rest[b]
            L = base.inverted() @ M[b]
            loc, rot, _ = L.decompose()
            pb.location = loc
            pb.rotation_quaternion = rot
            pb.keyframe_insert("location", frame=frame)
            pb.keyframe_insert("rotation_quaternion", frame=frame)


# ======================================================================= the clips

def guard_base(R, name):
    """The creature's guard, as a pose dict, and the facts the clips build on."""
    from mathutils import Vector
    H = R.H
    g = {}
    if name == "Monkey":
        drop, lean, sp = 0.07 * H, 6, (14, 8, -4)
        hand = lambda s: Vector((0.07 * s, -0.24, 0.72)) * (H / 1.1)
        feet = {"l": (0.035, -0.055), "r": (-0.03, 0.06)}
    else:
        drop, lean, sp = 0.07 * H, 8, (10, 8, 0)
        hand = lambda s: Vector((0.30 * s, -0.42, 1.30)) * (H / 2.05)
        feet = {"l": (0.06, -0.08), "r": (-0.04, 0.10)}
    g["pelvis"] = (0, 0.01 * H, -drop)
    g["pelvis_rot"] = (lean, 0, 0)
    g["spine"] = sp
    g["neck"] = -sum(sp) * 0.5 - lean * 0.5
    g["head"] = -sum(sp) * 0.4 - lean * 0.4
    for s, sx in (("l", 1), ("r", -1)):
        a = R.head["foot_" + s]
        dx, dy = feet[s]
        g["foot_" + s] = (a.x + dx * sx * sx, a.y + dy, a.z)
        g["hand_" + s] = tuple(hand(sx))
        g["elbow_" + s] = (0.6 * sx, 0.35, -0.75)
        g["knee_" + s] = (0.25 * sx, -1.0, 0.0)
    if name == "Monkey":
        g["tail"] = [(-12, 0), (-10, 0), (8, 0), (14, 0), (14, 0)]
    return g


def blend(a, b, t):
    """Pose a toward pose b by t (every key in both)."""
    out = dict(a)
    for k, v in b.items():
        if k in a:
            av = a[k]
            if isinstance(v, (tuple, list)) and v and isinstance(v[0], (tuple, list)):
                out[k] = [tuple(x + (y - x) * t for x, y in zip(p, q)) for p, q in zip(av, v)]
            elif isinstance(v, (tuple, list)):
                out[k] = tuple(x + (y - x) * t for x, y in zip(av, v))
            else:
                out[k] = av + (v - av) * t
        else:
            out[k] = v
    return out


def add(p, k, d):
    """Pose p with d added to its key k."""
    q = dict(p)
    v = q[k]
    if isinstance(v, (tuple, list)) and v and isinstance(v[0], (tuple, list)):
        q[k] = [tuple(x + y for x, y in zip(a, b)) for a, b in zip(v, d)]
    elif isinstance(v, (tuple, list)):
        q[k] = tuple(x + y for x, y in zip(v, d))
    else:
        q[k] = v + d
    return q


def clips(R, name, rows):
    """[(clip name, frames, fn(frame) -> pose, meta)]."""
    from mathutils import Vector
    H = R.H
    G = guard_base(R, name)
    out = []
    tail_wave = name == "Monkey"

    def breathe(t, T):
        w = 2 * math.pi * t / T
        p = add(G, "pelvis", (0, 0, -0.008 * H * (0.5 - 0.5 * math.cos(w))))
        for s in ("l", "r"):
            p = add(p, "hand_" + s, (0, 0, 0.006 * H * math.sin(w)))
        if tail_wave:
            p["tail"] = [(a, b + 10 * math.sin(w + i * 0.7)) for i, (a, b) in enumerate(G["tail"])]
        return p
    # Guard, a loop of the browser's breath (2.618 s, as every guard here)
    Tg = round(2.618 * FPS) / FPS                     # a whole number of frames, so the loop closes
    out.append(("Guard", round(Tg * FPS), lambda f: breathe(f / FPS, Tg), dict(loop=True, state="Guard")))
    # Block: arms crossed in front of the face, the head ducked
    def block(f):
        p = breathe(f / FPS, Tg)
        top = R.head["head"]
        for s, sx in (("l", 1), ("r", -1)):
            p["hand_" + s] = tuple(Vector((0.05 * sx * (H / 1.1), top.y - 0.20 * H / 1.1, top.z - 0.02 * H)))
            p["elbow_" + s] = (0.7 * sx, 0.0, -0.7)
        p["head"] = p["head"] + 12
        return p
    out.append(("Block", round(Tg * FPS), block, dict(loop=True, state="Block")))
    # the locomotion: two tiers x eight directions, loops in place (the
    # planted foot travels back under the body at the tier's pace), then the
    # turns and the pivot
    G0 = breathe(0.0, Tg)                              # the Guard clip's first frame: where a turn ends
    plans = {}
    for tier in ("Walk", "Run"):
        for dname, hdg in DIRS:
            pl = gait_plan(R, name, G, tier, dname, hdg)
            plans[(tier, dname)] = pl
            out.append(("%s_%s" % (tier, dname), pl["n"], (lambda f, pl=pl: loop_pose(R, name, G, pl, f / pl["n"])),
                        dict(loop=True, state=tier, dir=dname, heading=hdg, tier=tier, pace=pl["pace"] * 100.0,
                             stance=pl["duty"], lag=pl["lag"], cycle=pl["n"])))
    for cname in ("Turn_L90", "Turn_R90", "Turn_180"):
        n, fn = turn_clip(R, name, G0, cname)
        out.append((cname, n, fn, dict(state="Turn", turn=TURN_ANGLE[cname], turn_seconds=TURN_SECONDS[cname])))
    n, fn, join = pivot_clip(R, name, G, plans[("Run", "Fwd")])
    out.append(("Pivot_180", n, fn, dict(state="Pivot", turn=TURN_ANGLE["Pivot_180"], turn_seconds=TURN_SECONDS["Pivot_180"],
                                         join=join, push_from=n - PIVOT_PUSH)))
    # Hits: thrown back and back again
    for hname, secs, amt in (("Hit_Light", 0.22, 0.5), ("Hit_Heavy", 0.34, 1.0)):
        def hit(f, secs=secs, amt=amt):
            t = f / FPS
            k = keys(t, [(0, 0.0), (0.04, 1.0), (secs, 0.0)])
            p = add(G, "pelvis", (0, 0.05 * H * k * amt, 0))
            p = add(p, "pelvis_rot", (-14 * k * amt, 0, 0))
            p["head"] = G["head"] - 30 * k * amt
            for s in ("l", "r"):
                p = add(p, "hand_" + s, (0, 0.10 * H * k * amt, 0.06 * H * k * amt))
            return p
        out.append((hname, round(secs * FPS), hit, dict(state="Hit")))
    # Down / Death / GetUp
    lie = dict(G)
    lie["pelvis"] = (0, 0.30 * H, 0.10 * H - R.head["pelvis"].z)
    lie["pelvis_rot"] = (-80, 0, 0)
    lie["spine"] = (-4, -2, 0)
    lie["neck"] = 10
    lie["head"] = 10
    for s, sx in (("l", 1), ("r", -1)):
        fx, fy, fz = G["foot_" + s]
        lie["foot_" + s] = (fx + 0.03 * sx, 0.30 * H - 0.85 * sum(R.L["leg_" + s]), fz)
        lie["hand_" + s] = (0.38 * sx * H, 0.55 * H, 0.06 * H)
        lie["elbow_" + s] = (0.3 * sx, 0.0, -1.0)
        lie["knee_" + s] = (0.2 * sx, 0.0, 1.0)
    dead = dict(lie)
    dead["pelvis"] = (0, 0.34 * H, 0.08 * H - R.head["pelvis"].z)
    dead["pelvis_rot"] = (-86, 0, 0)
    dead["head"] = 22
    for s, sx in (("l", 1), ("r", -1)):
        dead["hand_" + s] = (0.30 * sx * H, 0.70 * H, 0.05 * H)
        dead["foot_" + s] = (lie["foot_" + s][0], 0.34 * H - 0.85 * sum(R.L["leg_" + s]), lie["foot_" + s][2])
    out.append(("Down", round(0.85 * FPS), lambda f: blend(G, lie, keys(f / FPS, [(0, 0.0), (0.70, 1.0)])),
                dict(state="Down", lies=True)))
    out.append(("Death", round(1.05 * FPS), lambda f: blend(G, dead, keys(f / FPS, [(0, 0.0), (0.85, 1.0)])),
                dict(state="Dead", lies=True)))
    out.append(("GetUp", round(0.60 * FPS), lambda f: blend(lie, G, keys(f / FPS, [(0, 0.0), (0.58, 1.0)])),
                dict(state="GetUp")))
    # Victory: the monkey hops with its arms up; the gorilla beats his chest
    def victory(f):
        t = f / FPS
        p = dict(G)
        if name == "Monkey":
            hop = max(0.0, math.sin(2 * math.pi * t / 0.5)) * 0.04 * H
            p = add(p, "pelvis", (0, 0, hop * 0.5))
            for s, sx in (("l", 1), ("r", -1)):
                p["hand_" + s] = (0.20 * sx * H, -0.05 * H, 1.15 * H)
                p["elbow_" + s] = (0.8 * sx, 0.3, 0.2)
            p["head"] = G["head"] - 15
            p["tail"] = [(-30, 0)] + [(25, 20 * math.sin(2 * math.pi * t + i)) for i in range(4)]
        else:
            chest = R.head["spine_03"]
            for s, sx in (("l", 1), ("r", -1)):
                beat = max(0.0, math.sin(2 * math.pi * (t / 0.36) + (0 if s == "l" else math.pi)))
                p["hand_" + s] = (0.10 * sx * H, chest.y - 0.16 * H - 0.08 * H * beat, chest.z + 0.03 * H)
                p["elbow_" + s] = (0.9 * sx, 0.2, -0.2)
            p["head"] = G["head"] - 20
            p = add(p, "pelvis", (0, 0, 0.03 * H))
        return p
    out.append(("Victory", round(2.0 * FPS), victory, dict(state="Victory")))
    # the strikes
    for move in STRIKES[name]:
        r = rows[move]
        su, ac, rc = float(r["Startup"]), float(r["Active"]), float(r["Recovery"])
        total = su + ac + rc
        if "wrong_length" in SABOTAGE and move == STRIKES[name][0]:
            total *= 1.4
        n = round(total * FPS)
        out.append((move, n, strike(R, name, G, move, su, ac, total), dict(state="Attack", attack=move, contact=round(su * FPS),
                                                                       limb=LIMB[(name, move)])))
    return out


# ======================================================================= the locomotion

def heading_vec(hdg):
    """The way a heading points on the floor: 0 is his facing (-Y), + toward his left (+X)."""
    a = math.radians(hdg)
    return (math.sin(a), -math.cos(a))


def rot2(v, yaw):
    """A point or a direction turned by yaw degrees about the vertical (+ toward his left)."""
    a = math.radians(yaw)
    c, s = math.cos(a), math.sin(a)
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c) + tuple(v[2:])


def rotate_pose(P, yaw):
    """The whole pose turned by yaw about the vertical through the root: the
    pelvis's place and turn, every hand and foot target, every pole, every
    foot's turn. What hangs off the pelvis (the spine, the head, the tail)
    turns with it."""
    q = dict(P)
    q["pelvis"] = rot2(P.get("pelvis", (0, 0, 0)), yaw)
    pr = P.get("pelvis_rot", (0, 0, 0))
    q["pelvis_rot"] = (pr[0], pr[1], pr[2] + yaw)
    for s in ("l", "r"):
        for k in ("hand_", "foot_", "elbow_", "knee_"):
            if k + s in P:
                q[k + s] = rot2(P[k + s], yaw)
        fr = P.get("foot_rot_" + s, (0, 0, 0))
        q["foot_rot_" + s] = (fr[0], fr[1], fr[2] + yaw)
    return q


def stride_offset(u, d):
    """Where a foot is along its stride at phase u (share of the planted
    travel, + ahead of its centre along the way he goes), and its swing's
    progress k (None while it is down): down for u < d, carried back
    evenly; then swung forward on the browser's ease."""
    if u < d:
        return 0.5 - u / d, None
    k = (u - d) / (1 - d)
    return -0.5 + ease(k), k


def gait_plan(R, name, G, tier, dname, hdg):
    """One loop's numbers: frames, the pace, the share a foot is down, each
    foot's centre, the planted travel, and the right foot's phase against
    the left's -- the one nearest an even alternation (0.5) that keeps the
    feet GAP_WANT apart across his hips the whole cycle (a walk's from
    1 - duty to duty, so a foot is always down), else the one keeping them
    furthest apart. Sideways, each foot stands a little wider."""
    H = R.H
    n = round(CYCLE[name] * FPS)
    if "tier_cycle" in SABOTAGE and tier == "Run" and dname == "BackLeft":
        n += 2
    share = WALK_SHARE if tier == "Walk" else 1.0
    if "walk_tier_pace" in SABOTAGE and tier == "Walk" and dname == "Fwd":
        share = 0.60
    pace = PACE[name] / 100.0 * share
    d = DUTY[name][tier]
    if "walk_flight" in SABOTAGE and tier == "Walk" and dname == "Fwd":
        d = 0.40
    dv = heading_vec(hdg)
    w = WIDEN[name] * H * abs(dv[0])
    if "run_cross" in SABOTAGE and tier == "Run" and dname == "Left":
        w = 0.0
    c = {"l": (G["foot_l"][0] + w, R.head["foot_l"].y), "r": (G["foot_r"][0] - w, R.head["foot_r"].y)}
    T = n / FPS
    travel = pace * T * d
    lo, hi = (1.0 - d, d) if tier == "Walk" else (0.05, 0.95)
    samples = 16 * n
    found = []
    for i in range(201):
        lag = lo + (hi - lo) * i / 200.0
        gap = min((c["l"][0] + dv[0] * travel * stride_offset((j / samples) % 1.0, d)[0])
                  - (c["r"][0] + dv[0] * travel * stride_offset((j / samples + lag) % 1.0, d)[0])
                  for j in range(samples))
        found.append((gap, lag))
    ok = [lag for gap, lag in found if gap >= GAP_WANT * H]
    lag = min(ok, key=lambda x: abs(x - 0.5)) if ok else max(found)[1]
    if "run_cross" in SABOTAGE and tier == "Run" and dname == "Left":
        lag = 0.5
    return dict(tier=tier, dname=dname, n=n, pace=pace, duty=d, dv=dv, c=c, travel=travel, lag=lag)


def loop_pose(R, name, G, pl, t):
    """A locomotion loop's pose at phase t (0..1 a cycle). The RUN tier is
    the old full-pace walks' authoring as it was (the hips down and bobbing
    twice a cycle, the arms swinging along the way he goes, the tail
    waving), only turned to any heading, with the right foot's phase and
    the sideways widening of gait_plan -- so Run_Fwd and Run_Back are the
    old Walk_Fwd and Walk_Back to the bone. The WALK tier is its own: the
    monkey low and hunched, quick; the gorilla rolling heavily over the
    foot that is down; both leaning a little into the way they go, the
    shoulders turning against the legs, the face kept forward."""
    H = R.H
    tier, d, dv = pl["tier"], pl["duty"], pl["dv"]
    mon = name == "Monkey"
    p = dict(G)
    if tier == "Run":
        p["pelvis"] = (G["pelvis"][0], 0.0, G["pelvis"][2] - 0.03 * H - 0.012 * H * abs(math.sin(2 * math.pi * t)))
        arm = 0.10 * H
    else:
        crouch = 0.025 * H + (0.015 * H if mon else 0.0)
        bob = (0.006 if mon else 0.010) * H * (0.5 - 0.5 * math.cos(4 * math.pi * t))
        over = math.cos(2 * math.pi * (t - d / 2))         # + while the left foot is down
        sway = 0.0 if mon else 0.012 * H * over
        roll = 0.0 if mon else 4.0 * over
        lean, twist = (3.0, 5.0) if mon else (2.0, 8.0)
        p["pelvis"] = (G["pelvis"][0] + sway, 0.0, G["pelvis"][2] - crouch - bob)
        pr = G["pelvis_rot"]
        p["pelvis_rot"] = (pr[0] + lean * (-dv[1]), pr[1] + roll, pr[2])
        p["twist"] = twist * math.cos(2 * math.pi * t) * (-dv[1])
        p["head_yaw"] = -0.8 * p["twist"]
        arm = (0.06 if mon else 0.07) * H
    way = dv
    if "wrong_way" in SABOTAGE and pl["tier"] == "Walk" and pl["dname"] == "Fwd":
        way = (-dv[0], -dv[1])
    for s, ph in (("l", 0.0), ("r", pl["lag"])):
        u = (t + ph) % 1.0
        o, k = stride_offset(u, d)
        off = pl["travel"] * o
        lift = 0.0 if k is None else LIFT[name][tier] * H * math.sin(math.pi * k)
        if "walk_no_lift" in SABOTAGE and tier == "Walk" and pl["dname"] == "Back" and s == "r":
            lift = 0.0
        cx, cy = pl["c"][s]
        fz = G["foot_" + s][2]
        p["foot_" + s] = (cx + way[0] * off, cy + way[1] * off, fz + lift)
        sw = math.sin(2 * math.pi * (t + ph + 0.5)) * arm
        hx, hy, hz = G["hand_" + s]
        p["hand_" + s] = (hx + dv[0] * sw * 0.5, hy + dv[1] * sw, hz)
    if mon:
        amp = 14 if tier == "Run" else 10
        p["tail"] = [(a, amp * math.sin(2 * math.pi * t + i * 0.8)) for i, (a, _) in enumerate(G["tail"])]
    return p


def turn_clip(R, name, G0, cname):
    """A turn on the spot: the guard turned back by the turn's angle, then
    stepped round, a foot at a time -- the foot on the turn's side first --
    each step lifting the foot from where it stands turned to where it
    stands one step further round (a 90 in two steps, a 180 in four); a
    planted foot keeps its place and its turn; the body faces between its
    feet, the head looking ahead into the turn; it ends on the guard's own
    first frame. Returns (frames, fn)."""
    H = R.H
    A = TURN_ANGLE[cname]
    secs = TURN_SECONDS[cname]
    if "turn_long" in SABOTAGE and cname == "Turn_180":
        secs = 0.80
    if "turn_short" in SABOTAGE and cname == "Turn_L90":
        A = 70.0
    n = round(secs * FPS)
    lead = "l" if A > 0 else "r"
    trail = "r" if lead == "l" else "l"
    y0 = -A
    if abs(A) > 135:
        steps = [(lead, y0, y0 / 2, 0.04, 0.24), (trail, y0, y0 / 2, 0.26, 0.46),
                 (lead, y0 / 2, 0.0, 0.50, 0.70), (trail, y0 / 2, 0.0, 0.72, 0.90)]
    else:
        steps = [(lead, y0, 0.0, 0.06, 0.44), (trail, y0, 0.0, 0.50, 0.88)]
    mon = name == "Monkey"
    arc, dip = (0.05 if mon else 0.04) * H, (0.015 if mon else 0.025) * H

    def foot_at(s, x):
        yaw, k = y0, None
        pos = rot2(G0["foot_" + s], y0)
        for fs, ya, yb, a, b in steps:
            if fs != s:
                continue
            if x >= b:
                yaw, pos = yb, rot2(G0["foot_" + s], yb)
                continue
            if x > a:
                k = (x - a) / (b - a)
                e = ease(k)
                pa, pb = rot2(G0["foot_" + s], ya), rot2(G0["foot_" + s], yb)
                pos = (pa[0] + (pb[0] - pa[0]) * e, pa[1] + (pb[1] - pa[1]) * e, pa[2] + arc * math.sin(math.pi * k))
                yaw = ya + (yb - ya) * e
            break
        return pos, yaw, k

    def fn(f):
        x = f / (n - 1)
        feet = {s: foot_at(s, x) for s in ("l", "r")}
        th = 0.5 * (feet["l"][1] + feet["r"][1])
        p = rotate_pose(G0, th)
        down = 0.0
        for s, (pos, yaw, k) in feet.items():
            if "turn_skate" in SABOTAGE and cname == "Turn_180" and s == trail and x < 0.26:
                pos = (pos[0] + 0.04 * x / 0.26, pos[1], pos[2])
            p["foot_" + s] = pos
            fr = G0.get("foot_rot_" + s, (0, 0, 0))
            p["foot_rot_" + s] = (fr[0], fr[1], fr[2] + yaw)
            p["knee_" + s] = rot2(G0["knee_" + s], 0.5 * (yaw + th))
            if k is not None:
                down += dip * math.sin(math.pi * k)
        pv = p["pelvis"]
        p["pelvis"] = (pv[0], pv[1], pv[2] - down)
        p["head_yaw"] = max(-35.0, min(35.0, -0.6 * th)) * min(1.0, x / 0.15)
        if "turn_off_guard" in SABOTAGE and cname == "Turn_R90":
            p["hand_l"] = (p["hand_l"][0], p["hand_l"][1], p["hand_l"][2] + 0.03 * x)
        return p
    return n, fn


def pivot_clip(R, name, G, plf):
    """The run's 180: from Run_Fwd turned back, at the frame its left foot
    is half way through its stance (under him; the right swinging through),
    the left foot plants and swivels on its ball, the heel coming up, an
    eighth of a turn, while the right swings round to where Run_Fwd has it
    a quarter into its stance (just ahead of him); the body turns over his
    right (away from the planted foot, so the feet never cross), facing
    between his feet, dipping and leaning back into the brake; then the
    left steps round into its swing, and the last PIVOT_PUSH frames are
    Run_Fwd's own from there on -- the push off, the right foot driving back.
    Returns (frames, fn, (the Run_Fwd frame it starts on, the one it ends on))."""
    from mathutils import Euler, Vector
    H = R.H
    n = round(TURN_SECONDS["Pivot_180"] * FPS)
    nr = plf["n"]
    fp = n - PIVOT_PUSH
    d = plf["duty"]
    u_s = round(0.5 * d * nr) / nr                      # the left at mid-stance
    u_p = 0.5 + round(0.25 * d * nr) / nr               # the right a quarter into its stance
    y0 = -TURN_ANGLE["Pivot_180"]
    if "pivot_short" in SABOTAGE:
        y0 = 150.0
    shift = 2.0 / nr if "pivot_off_phase" in SABOTAGE else 0.0
    mon = name == "Monkey"
    arc, dip, heel = (0.06 if mon else 0.05) * H, (0.035 if mon else 0.045) * H, 22.0

    def RF(u):
        return loop_pose(R, name, G, plf, u % 1.0)
    S, E = RF(u_s), RF(u_p)
    L0, R0 = rot2(S["foot_l"], y0), rot2(S["foot_r"], y0)
    LP, R1 = E["foot_l"], E["foot_r"]
    toe = R.head["ball_l"] - R.head["foot_l"]            # the ball from the ankle, in the rest foot
    ball0 = Vector(L0) + Euler((0.0, 0.0, math.radians(y0)), "XYZ").to_quaternion() @ toe
    join = (round(u_s * nr), round((u_p + (PIVOT_PUSH - 1) / nr) * nr) % nr)

    def left_on_ball(yaw, pitch):
        """The left ankle with its ball held where it came down, the foot
        turned by yaw and pitched heel-up by pitch."""
        q = Euler((math.radians(pitch), 0.0, math.radians(yaw)), "XYZ").to_quaternion()
        return tuple(ball0 - q @ toe)

    swivel = 0.75 * y0

    def fn(f):
        if f >= fp:
            return RF(u_p + (f - fp) / nr + shift)
        s = f / fp
        kr = min(s / 0.4, 1.0)
        er = ease(kr)
        yaw_r = y0 * (1.0 - er)
        ks = min(max((s - 0.05) / 0.45, 0.0), 1.0)          # the swivel, on the ball:
        kh = ease(min(ks * 2.5, 1.0))                       # the heel up first,
        ky = ease(min(max((ks - 0.25) / 0.75, 0.0), 1.0))   # then the turn
        kl = min(max((s - 0.5) / 0.5, 0.0), 1.0)            # then the step
        el = ease(kl)
        yaw_l = (y0 + (swivel - y0) * ky) * (1.0 - el)
        pitch_l = heel * kh * (1.0 - el)
        th = 0.5 * (yaw_l + yaw_r)
        p = rotate_pose(blend(S, E, ease(s)), th)
        p["foot_r"] = (R0[0] + (R1[0] - R0[0]) * er, R0[1] + (R1[1] - R0[1]) * er,
                       R0[2] + (R1[2] - R0[2]) * kr + arc * math.sin(math.pi * kr))
        Ls = left_on_ball(y0 + (swivel - y0) * ky, heel * kh)
        p["foot_l"] = (Ls[0] + (LP[0] - Ls[0]) * el, Ls[1] + (LP[1] - Ls[1]) * el,
                       Ls[2] + (LP[2] - Ls[2]) * kl + arc * math.sin(math.pi * kl))
        p["foot_rot_l"] = (pitch_l, 0.0, yaw_l)
        p["foot_rot_r"] = (0.0, 0.0, yaw_r)
        for sd, yaw in (("l", yaw_l), ("r", yaw_r)):
            p["knee_" + sd] = rot2(G["knee_" + sd], 0.5 * (yaw + th))
        pv = p["pelvis"]
        p["pelvis"] = (pv[0], pv[1], pv[2] - dip * math.sin(math.pi * s))
        pr = p["pelvis_rot"]
        p["pelvis_rot"] = (pr[0] - 6.0 * math.sin(math.pi * s), pr[1], pr[2])
        p["head_yaw"] = p.get("head_yaw", 0.0) + max(-40.0, min(40.0, -0.5 * th)) * math.sin(math.pi * s)
        return p
    return n, fn, join


LIMB = {("Monkey", "Jab"): "hand_r", ("Monkey", "Hook"): "hand_l", ("Monkey", "Kick"): "foot_r",
        ("Gorilla", "Cross"): "hand_r", ("Gorilla", "Hook"): "hand_l", ("Gorilla", "Special"): "hand_r"}


def strike(R, name, G, move, su, ac, total):
    """A strike as a function of frame: wind-up to the startup's end, the
    blow through the active frames, back to the guard by the end."""
    from mathutils import Vector
    H = R.H
    sh = {s: R.head["upperarm_" + s] for s in ("l", "r")}
    reach = {s: sum(R.L["arm_" + s]) for s in ("l", "r")}

    def at(f):
        t = f / FPS
        k_in = keys(t, [(0, 0.0), (su * 0.55, -0.35), (su, 1.0), (su + ac, 1.0), (total, 0.0)])
        k = max(k_in, 0.0)
        wind = max(-k_in, 0.0) / 0.35
        p = dict(G)
        if name == "Monkey" and move == "Jab":
            s = "r"
            tgt = Vector((-0.02 * H, sh[s].y - reach[s] * 0.92, sh[s].z - 0.08 * H))
            p["hand_r"] = tuple(Vector(G["hand_r"]).lerp(tgt, k) + Vector((0, 0.06 * H * wind, 0)))
            p["pelvis_rot"] = (G["pelvis_rot"][0] + 8 * k, 0, 0)
            p["twist"] = 18 * k - 10 * wind
        elif name == "Monkey" and move == "Hook":
            s = "l"
            a = -1.0 + 2.0 * keys(t, [(0, 0.0), (su, 0.15), (su + ac, 0.85), (total, 1.0)])
            arc = Vector((-0.26 * H * a, sh[s].y - 0.42 * H, sh[s].z - 0.05 * H))     # raked from his left across
            p["hand_l"] = tuple(Vector(G["hand_l"]).lerp(arc, k))
            p["twist"] = -26 * k * a
        elif name == "Monkey" and move == "Kick":
            hop = 0.05 * H * k
            p["pelvis"] = (G["pelvis"][0], G["pelvis"][1] + 0.04 * H * k, G["pelvis"][2] + hop * 0.0)
            p["pelvis_rot"] = (G["pelvis_rot"][0] - 22 * k, 0, 0)
            fx, fy, fz = G["foot_r"]
            p["foot_r"] = (fx, fy - 0.42 * H * k, fz + 0.30 * H * k)
            p["foot_rot_r"] = (-60 * k, 0, 0)
            p["knee_r"] = (-0.1, -0.2, 1.0)
            for s in ("l", "r"):
                p = add(p, "hand_" + s, (0, 0.05 * H * k, 0.04 * H * k))
        elif name == "Gorilla" and move == "Cross":
            s = "r"
            top = Vector((-0.05 * H, sh[s].y - 0.10 * H, sh[s].z + 0.30 * H))
            hit = Vector((-0.04 * H, sh[s].y - reach[s] * 0.88, sh[s].z - 0.10 * H))
            pos = Vector(G["hand_r"]).lerp(top, wind) if k == 0 else top.lerp(hit, k)
            if t > su + ac:
                pos = hit.lerp(Vector(G["hand_r"]), keys(t, [(su + ac, 0.0), (total, 1.0)]))
            p["hand_r"] = tuple(pos)
            p["elbow_r"] = (-0.7, 0.4, 0.4)
            p["pelvis_rot"] = (G["pelvis_rot"][0] + 14 * k, 0, 0)
            p["twist"] = 20 * k
        elif name == "Gorilla" and move == "Hook":
            s = "l"
            a = keys(t, [(0, 0.0), (su, 0.15), (su + ac, 0.85), (total, 1.0)])
            arc = Vector(((0.55 - 1.1 * a) * H * 0.5, sh[s].y - 0.30 * H, sh[s].z - 0.12 * H))
            p["hand_l"] = tuple(Vector(G["hand_l"]).lerp(arc, k))
            p["twist"] = -30 * (a - 0.5) * 2 * k
        else:                                           # the gorilla's Special: the slam
            up = keys(t, [(0, 0.0), (su, 1.0), (su + ac * 0.3, 0.0)])
            down = keys(t, [(su, 0.0), (su + ac * 0.3, 1.0), (su + ac, 1.0), (total, 0.0)])
            for s, sx in (("l", 1), ("r", -1)):
                over = Vector((0.12 * sx * H, sh[s].y - 0.05 * H, sh[s].z + 0.30 * H))
                floor = Vector((0.16 * sx * H, sh[s].y - 0.38 * H, 0.26 * H))
                pos = Vector(G["hand_" + s]).lerp(over, up)
                pos = pos.lerp(floor, down)
                p["hand_" + s] = tuple(pos)
                p["elbow_" + s] = (0.8 * sx, 0.4, 0.0)
            p["pelvis"] = (G["pelvis"][0], G["pelvis"][1], G["pelvis"][2] - 0.12 * H * down)
            p["pelvis_rot"] = (G["pelvis_rot"][0] + 30 * down - 8 * up, 0, 0)
            p["spine"] = tuple(x + 6 * down for x in G["spine"])
        if "slide" in SABOTAGE and move == STRIKES[name][0]:
            fx, fy, fz = p["foot_l"]
            p["foot_l"] = (fx, fy - 0.08 * t, fz)
        if "stretch" in SABOTAGE and move == STRIKES[name][0]:
            p["hand_r"] = tuple(Vector(p["hand_r"]) + Vector((0, -0.6 * H * k, 0)))
        if "knee_back" in SABOTAGE:
            p["knee_l"] = (0.1, 1.0, 0.0)
        if "under_floor" in SABOTAGE and move == STRIKES[name][0]:
            fx, fy, fz = p["foot_l"]
            p["foot_l"] = (fx, fy, fz - 0.03)
        if "short_reach" in SABOTAGE and move == STRIKES[name][0]:
            p["hand_r"] = G["hand_r"]
            p["foot_r"] = G["foot_r"]
        return p
    return at


# ======================================================================= build, check, export

def joints_world(R, M, names):
    from mathutils import Vector
    out = {}
    for b in names:
        out[b] = (M[b] @ (R.rest[b].inverted() @ R.head[b])).copy()
    return out


def run(name, export=True):
    """Build every clip for one creature; returns (rig, records, misses).
    Keyed (and exported) only when exporting: a --bite run reads the poses."""
    import bpy
    R = Rig(name)
    rows = attack_rows()
    recs = []
    built = {}
    miss = []
    for cname, n, fn, meta in clips(R, name, rows):
        frames = n + 1 if meta.get("loop") else n
        act = None
        if export:
            act = bpy.data.actions.new("A_%s_%s" % (name, cname))
            R.arm.animation_data_create()
            R.arm.animation_data.action = act
        world = []
        for f in range(frames):
            P = fn(f)
            M, st = R.pose(P)
            if export:
                R.key(M, f)
            world.append(joints_world(R, M, [b for b in R.order]))
            if st:
                miss.append("%s %s: %s reaches past its limb at frame %d" % (name, cname, ", ".join(st), f))
        rec = dict(name="A_%s_%s" % (name, cname), clip=cname, fighter=name, frames=frames, seconds=n / FPS,
                   contact=meta.get("contact", ""), limb=meta.get("limb", ""), loop=bool(meta.get("loop")),
                   state=meta["state"], dir=meta.get("dir", ""), attack=meta.get("attack", ""), world=world, meta=meta, action=act)
        miss += check_clip(R, rec, rows, built)
        recs.append(rec)
        built[cname] = rec
    miss += check_tiers(name, recs)
    if export:
        miss += export_all(R, recs)
    return R, recs, miss


def check_tiers(name, recs):
    """Each tier is all eight directions on one cycle, so a change of
    direction can keep the phase."""
    miss = []
    for tier in ("Walk", "Run"):
        got = {r["dir"]: r["frames"] for r in recs if r["state"] == tier}
        lost = [d for d, _ in DIRS if d not in got]
        if lost:
            miss.append("%s has no %s %s" % (name, tier, ", ".join(lost)))
        if len(set(got.values())) > 1:
            miss.append("%s's %s tier is not one cycle: %s" % (
                name, tier, ", ".join("%s %d" % (d, f) for d, f in sorted(got.items()))))
    return miss


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def hips_axis(w):
    """His left across his hips, flat on the floor (unit), from the thighs."""
    ax = w["thigh_l"] - w["thigh_r"]
    L = math.hypot(ax.x, ax.y)
    return (ax.x / L, ax.y / L)


def facing_yaw(w):
    """Which way his hips face, degrees from the root's facing, + to his left."""
    lx, ly = hips_axis(w)
    return math.degrees(math.atan2(ly, lx))


def check_clip(R, rec, rows, built):
    miss = []
    W = rec["world"]
    nm = "%s %s" % (rec["fighter"], rec["clip"])
    H = R.H
    meta = rec["meta"]
    rest = {s: R.head["foot_" + s].z for s in ("l", "r")}

    def up(w, s):
        """How far a foot (its ankle) is off the floor it stands on."""
        return w["foot_" + s].z - rest[s]
    # no foot under the floor
    low = min(min(w["ball_l"].z, w["ball_r"].z, w["foot_l"].z - R.head["foot_l"].z, w["foot_r"].z - R.head["foot_r"].z) for w in W)
    if low < -0.004:
        miss.append("%s puts a foot %.1f cm under the floor" % (nm, -low * 100))
    # loops close
    if rec["loop"]:
        gap = max((W[0][b] - W[-1][b]).length for b in W[0])
        if gap > 0.002:
            miss.append("%s does not close: %.1f mm between its ends" % (nm, gap * 1000))
    # planted feet: still, unless walking (then at the pace)
    st = rec["state"]
    if st in ("Guard", "Block", "Attack", "Hit", "Victory"):
        for s in ("l", "r"):
            if rec["clip"] == "Kick" and s == "r":
                continue
            moved = max((W[i]["foot_" + s] - W[0]["foot_" + s]).length for i in range(len(W)))
            if moved > 0.002 and not (rec["fighter"] == "Monkey" and rec["clip"] == "Victory"):
                miss.append("%s slides its %s foot %.1f cm" % (nm, s, moved * 100))
    # a loop's planted feet go back under him at its tier's pace, the opposite
    # way to its direction (the in-place convention): the mean planted
    # velocity within PACE_TOL of the pace and DIR_TOL degrees of the way
    if st in ("Walk", "Run"):
        pace = PACE[rec["fighter"]] / 100.0 * (WALK_SHARE if st == "Walk" else 1.0)
        dv = heading_vec(dict(DIRS)[rec["dir"]])
        want = (-dv[0], -dv[1])
        for s in ("l", "r"):
            vs = []
            for i in range(1, len(W)):
                if up(W[i], s) < 0.002 and up(W[i - 1], s) < 0.002:
                    d = W[i]["foot_" + s] - W[i - 1]["foot_" + s]
                    vs.append((d.x * FPS, d.y * FPS))
            vx = sum(v[0] for v in vs) / len(vs) if vs else 0.0
            vy = sum(v[1] for v in vs) / len(vs) if vs else 0.0
            speed = math.hypot(vx, vy)
            if not vs or abs(speed - pace) > PACE_TOL * pace:
                miss.append("%s's planted %s foot moves at %.0f cm/s, not the %s pace %.0f" % (nm, s, speed * 100, st.lower(), pace * 100))
            if speed > 1e-6:
                off = math.degrees(math.acos(max(-1.0, min(1.0, (vx * want[0] + vy * want[1]) / speed))))
                if off > DIR_TOL:
                    miss.append("%s's planted %s foot goes %.0f deg off its way (%s)" % (nm, s, off, rec["dir"]))
    # the walk tier: each foot lifts, and never both off the floor at once
    if st == "Walk":
        for s in ("l", "r"):
            top = max(up(w, s) for w in W)
            if top < LIFT_MIN * H:
                miss.append("%s never lifts its %s foot (%.1f cm, want %.1f)" % (nm, s, top * 100, LIFT_MIN * H * 100))
        both = [i for i, w in enumerate(W) if up(w, "l") > 0.002 and up(w, "r") > 0.002]
        if both:
            miss.append("%s has both feet off the floor at frame %d (%d frames)" % (nm, both[0], len(both)))
    # in no locomotion clip do the feet cross: the left foot (ankle and ball)
    # left of the right by CROSS_MIN, across his own hips
    if st in ("Walk", "Run", "Turn", "Pivot"):
        worst, at = 1e9, 0
        for i, w in enumerate(W):
            lx, ly = hips_axis(w)
            for j in ("foot_", "ball_"):
                g = (w[j + "l"].x - w[j + "r"].x) * lx + (w[j + "l"].y - w[j + "r"].y) * ly
                if g < worst:
                    worst, at = g, i
        if worst < CROSS_MIN * H:
            miss.append("%s crosses its feet: the left %.1f cm left of the right at frame %d, want %.1f" % (
                nm, worst * 100, at, CROSS_MIN * H * 100))
    # a turn: as long as the game holds it, by its angle from a body turned
    # back by it, no planted foot skating, and ending in the guard (a turn)
    # or joining Run_Fwd at both ends (the pivot)
    if st in ("Turn", "Pivot"):
        want_s = meta["turn_seconds"]
        if abs(rec["frames"] - want_s * FPS) > 1.0 + 1e-6:
            miss.append("%s lasts %d frames (%.3f s), not %.2f s to a frame" % (nm, rec["frames"], rec["seconds"], want_s))
        A = meta["turn"]
        ys = [facing_yaw(w) for w in W]
        total = sum(wrap(ys[i] - ys[i - 1]) for i in range(1, len(ys)))
        y_start, y_end = wrap(ys[0] - (-A)), wrap(ys[-1])
        if abs(total - A) > TURN_TOL_DEG or abs(y_start) > TURN_TOL_DEG or abs(y_end) > TURN_TOL_DEG:
            miss.append("%s turns %.0f deg, from %.0f to %.0f, not %.0f from %.0f to 0" % (
                nm, total, ys[0], ys[-1], A, wrap(-A)))
        # never skating: a point of a foot (the ankle over the heel, the
        # ball) on the floor in two frames running has not slid (a foot may
        # swivel on its ball, heel up); the pivot's push off is Run_Fwd's
        last = meta.get("push_from", len(W))
        floor = {j + s: R.head[j + s].z for j in ("foot_", "ball_") for s in ("l", "r")}
        for s in ("l", "r"):
            for i in range(1, min(last + 1, len(W))):
                d = max([(W[i][j + s] - W[i - 1][j + s]).length for j in ("foot_", "ball_")
                         if W[i][j + s].z - floor[j + s] < 0.002 and W[i - 1][j + s].z - floor[j + s] < 0.002] or [0.0])
                if d > 0.002:
                    miss.append("%s skates its planted %s foot %.1f cm at frame %d" % (nm, s, d * 100, i))
                    break
    if st == "Turn":
        g0 = built["Guard"]["world"][0]
        off = max((W[-1][b] - g0[b]).length for b in g0)
        if off > GUARD_TOL:
            miss.append("%s ends %.1f cm from the guard" % (nm, off * 100))
    if st == "Pivot":
        rf = built["Run_Fwd"]["world"]
        from mathutils import Vector
        js, je = meta["join"]
        start = max((W[0][b] - Vector((-rf[js][b].x, -rf[js][b].y, rf[js][b].z))).length for b in W[0])
        end = max((W[-1][b] - rf[je][b]).length for b in W[-1])
        if max(start, end) > GUARD_TOL:
            miss.append("%s does not join Run_Fwd: it starts %.1f cm off its frame %d turned back, ends %.1f cm off its frame %d" % (
                nm, start * 100, js, end * 100, je))
    # knees forward of the hip-ankle line (standing clips), along the way
    # his hips face (a turned body's knee is ahead of HIS line, not the world's)
    if st not in ("Down", "Dead", "GetUp"):
        for s in ("l", "r"):
            worst = 0.0
            for w in W:
                h, k, a = w["thigh_" + s], w["calf_" + s], w["foot_" + s]
                u = (a - h).normalized()
                off = (k - h) - u * (k - h).dot(u)
                lx, ly = hips_axis(w)
                worst = max(worst, off.x * (-ly) + off.y * lx)        # behind him: his facing is (ly, -lx)
            if worst > 0.01:
                miss.append("%s bends its %s knee backwards (%.1f cm)" % (nm, s, worst * 100))
    # a strike gets out in front
    if st == "Attack":
        r = rows[rec["attack"]]
        want = round((float(r["Startup"]) + float(r["Active"]) + float(r["Recovery"])) * FPS)
        if rec["frames"] != want:
            miss.append("%s is %d frames, its row %d" % (nm, rec["frames"], want))
        c = rec["contact"]
        limb = rec["limb"]
        tip = limb.replace("hand", "hand_end") if limb.startswith("hand") else limb.replace("foot", "ball")
        root = "upperarm_" + limb[-1] if limb.startswith("hand") else "thigh_" + limb[-1]
        L = sum(R.L[("arm_" if limb.startswith("hand") else "leg_") + limb[-1]])
        w0, wc = W[0], W[min(c, len(W) - 1)]
        out_front = (w0[tip].y - wc[tip].y)
        if rec["clip"] == "Special":
            out_front = (w0[tip].y - wc[tip].y) + 0.0
            ok = wc[tip].z < 0.40 * H or out_front > 0.15 * L
            if not ok and c + int(0.3 * float(r["Active"]) * FPS) < len(W):
                wc = W[c + int(0.3 * float(r["Active"]) * FPS)]
                ok = wc[tip].z < 0.40 * H
        else:
            ok = out_front > 0.30 * L
        if not ok:
            miss.append("%s's %s gets %.0f cm out by the contact frame, want %.0f" % (nm, tip, out_front * 100, 0.30 * L * 100))
    # Down ends on the floor
    if rec["meta"].get("lies"):
        w = W[-1]
        if w["spine_02"].z > 0.25 * H or min(w[b].z for b in ("pelvis", "spine_01", "spine_02", "spine_03", "head")) < -0.01:
            miss.append("%s does not end lying on the floor (spine at %.2f m)" % (nm, w["spine_02"].z))
    return miss


def export_all(R, recs):
    import bpy
    os.makedirs(OUT, exist_ok=True)
    miss = []
    for o in bpy.data.objects:
        o.select_set(False)
    R.arm.select_set(True)
    bpy.context.view_layer.objects.active = R.arm
    sc = bpy.context.scene
    sc.render.fps = FPS
    for rec in recs:
        R.arm.animation_data.action = rec["action"]
        sc.frame_start, sc.frame_end = 0, rec["frames"] - 1
        path = os.path.join(OUT, rec["name"] + ".fbx")
        bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"ARMATURE"}, add_leaf_bones=False,
                                 bake_anim=True, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
                                 bake_anim_step=1.0, bake_anim_simplify_factor=0.0,
                                 primary_bone_axis="Y", secondary_bone_axis="X",
                                 apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS")
    # read back clips of every kind, frame for frame: the guard, a strike, a
    # diagonal of each tier, a turn and the pivot
    by = {r["clip"]: r for r in recs}
    for rec in (recs[0], [r for r in recs if r["state"] == "Attack"][0], by["Walk_FwdLeft"], by["Run_BackRight"],
                by["Turn_180"], by["Pivot_180"]):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=os.path.join(OUT, rec["name"] + ".fbx"))
        arm = [o for o in bpy.data.objects if o not in before and o.type == "ARMATURE"][0]
        worst = 0.0
        for f in range(0, rec["frames"], max(1, rec["frames"] // 6)):
            best = 1e9
            for shift in (0, 1):
                sc.frame_set(f + shift)
                d = 0.0
                for b in ("hand_r", "foot_l", "head", "hand_end_l"):
                    got = arm.matrix_world @ arm.pose.bones[b].head
                    d = max(d, (got - rec["world"][f][b]).length)
                best = min(best, d)
            worst = max(worst, best)
        for o in [o for o in bpy.data.objects if o not in before]:
            bpy.data.objects.remove(o, do_unlink=True)
        if worst > 0.001:
            miss.append("%s reads back %.1f mm off" % (rec["name"], worst * 1000))
        rec["readback_mm"] = worst * 1000
    sc.frame_set(0)
    return miss


def manifest(all_recs):
    path = os.path.join(OUT, "DT_IslandMotion.csv")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Name", "Fighter", "Attack", "File", "Seconds", "Frames", "ContactFrame", "Limb", "bLoop", "State", "Direction"])
        for r in all_recs:
            w.writerow([r["name"], r["fighter"], r["attack"], r["name"] + ".fbx", "%.3f" % r["seconds"], r["frames"],
                        r["contact"], r["limb"], str(r["loop"]).lower(), r["state"], r["dir"]])
    return path


def draw(all_recs, path=SHEET):
    """Every clip as its skeleton seen from in front and to his left (a
    three-quarter view, so a sideways or a turning clip reads), six frames
    across, the monkey's clips on the left and the gorilla's on the right;
    a line on the floor marks the root's facing."""
    from PIL import Image, ImageDraw
    cols, cw, ch, lab = 6, 120, 120, 150
    sets = [[r for r in all_recs if r["fighter"] == f] for f in ("Monkey", "Gorilla")]
    rows = max(len(x) for x in sets)
    pw = lab + cw * cols + 10
    img = Image.new("RGB", (pw * len(sets), ch * rows + 10), (14, 16, 22))
    dr = ImageDraw.Draw(img)
    from mathutils import Vector
    for c, recs in enumerate(sets):
        for i, rec in enumerate(recs):
            y0 = 5 + i * ch
            X0 = c * pw
            dr.text((X0 + 6, y0 + ch // 2 - 6), rec["name"][2:], fill=(220, 230, 240))
            H = 2.2 if rec["fighter"] == "Gorilla" else 1.25
            n = len(rec["world"])
            for j in range(cols):
                f = round(j * (n - 1) / (cols - 1))
                W = rec["world"][f]
                x0 = X0 + lab + j * cw

                def pt(v):
                    sx = -v.y * 0.80 + v.x * 0.60
                    sy = v.z + 0.18 * (v.x * 0.80 + v.y * 0.60)
                    return (x0 + cw / 2 + sx / H * (ch - 30), y0 + ch - 22 - sy / H * (ch - 30))
                dr.line([pt(Vector((0, 0, 0))), pt(Vector((0, -0.35 * H, 0)))], fill=(70, 90, 70), width=1)
                for b, p in RIG_PARENTS[rec["fighter"]].items():
                    if p and p in W and b in W and p != "root":
                        side = b.endswith("_l")
                        col = (120, 200, 255) if side else ((255, 140, 120) if b.endswith("_r") else (230, 230, 230))
                        dr.line([pt(W[p]), pt(W[b])], fill=col, width=2)
                if rec["state"] == "Attack" and f >= (rec["contact"] or 0) and j and round((j - 1) * (n - 1) / (cols - 1)) < rec["contact"]:
                    dr.rectangle([x0, y0, x0 + cw - 8, y0 + ch - 8], outline=(255, 210, 80))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    print("drew %s" % path)


RIG_PARENTS = {}

BITES = [
    ("a planted foot stays", "slide", "slides its"),
    ("no foot under the floor", "under_floor", "under the floor"),
    ("nothing stretched", "stretch", "reaches past"),
    ("knees forward", "knee_back", "knee backwards"),
    ("a strike reaches out", "short_reach", "by the contact frame"),
    ("each clip its row", "wrong_length", "its row"),
    # the locomotion (2026-10-04)
    ("a walk at its tier's pace", "walk_tier_pace", "not the walk pace"),
    ("... the way it goes", "wrong_way", "off its way"),
    ("a walk-tier foot lifts", "walk_no_lift", "never lifts its"),
    ("a walk never in the air", "walk_flight", "both feet off the floor"),
    ("no feet crossing", "run_cross", "crosses its feet"),
    ("one cycle a tier", "tier_cycle", "is not one cycle"),
    ("a turn as long as its row", "turn_long", "lasts"),
    ("a turn by its angle", "turn_short", "Turn_L90 turns"),
    ("a turn ends in the guard", "turn_off_guard", "from the guard"),
    ("a turn never skates", "turn_skate", "skates its planted"),
    ("the pivot turns 180", "pivot_short", "Pivot_180 turns"),
    ("the pivot joins Run_Fwd", "pivot_off_phase", "does not join Run_Fwd"),
]
CREATURES = ("Monkey", "Gorilla")


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    try:
        import bpy  # noqa: F401
    except ImportError:
        print("runs with bpy (pip install bpy)")
        sys.exit(2)
    if "--bite" in args:
        only = [a.split("=", 1)[1] for a in args if a.startswith("--only=")]
        SABOTAGE.clear()
        for name in CREATURES:
            _, _, f = run(name, export=False)
            if f:
                print("the unbroken %s fails its own checks, so no sabotage can be counted:\n  %s" % (name, "\n  ".join(f[:20])))
                sys.exit(1)
            print("  %-26s %-8s passes" % ("unbroken", name))
        bites = [b for b in BITES if not only or b[1] in only]
        caught = total = 0
        for what, sab, want in bites:
            for name in CREATURES:
                SABOTAGE.clear()
                SABOTAGE.add(sab)
                _, _, f = run(name, export=False)
                hit = [x for x in f if want in x]
                caught += bool(hit)
                total += 1
                print("  %-26s %-8s %s  %s" % (what, name, "caught" if hit else "MISSED", (hit or f or ["(passed)"])[0]), flush=True)
        SABOTAGE.clear()
        print("%d of %d caught (%d sabotages, each on the monkey and the gorilla)" % (caught, total, len(bites)))
        sys.exit(0 if caught == total else 1)
    all_recs, allmiss = [], []
    for name in CREATURES:
        R, recs, miss = run(name)
        RIG_PARENTS[name] = dict(R.parent)
        all_recs += recs
        allmiss += miss
        print("  %-8s %d clips, %d frames" % (name, len(recs), sum(r["frames"] for r in recs)), flush=True)
        for r in recs:
            if r["state"] in ("Walk", "Run"):
                m = r["meta"]
                print("    %-14s %2d frames %.3f s  pace %3.0f cm/s  duty %.2f  right foot %+.3f of a cycle on the left" % (
                    r["clip"], r["frames"], r["seconds"], m["pace"], m["stance"], m["lag"]))
            elif r["state"] in ("Turn", "Pivot"):
                print("    %-14s %2d frames %.3f s  turns %+.0f deg" % (r["clip"], r["frames"], r["seconds"], r["meta"]["turn"]))
    if allmiss:
        print("FAILED:\n  " + "\n  ".join(allmiss[:40]))
        sys.exit(1)
    m = manifest(all_recs)
    draw(all_recs)
    print("checks pass: planted feet, the floor, loops, reach, knees, strikes out by contact, lengths, Down on the floor; "
          "the locomotion (pace and way, lifts, never both up walking, feet never crossing, one cycle a tier), the turns "
          "(length, angle, no skating, the guard), the pivot (180, Run_Fwd at both ends); "
          "read back %s mm worst; %s" % (max(r.get("readback_mm", 0) for r in all_recs), os.path.relpath(m, ROOT)))


if __name__ == "__main__":
    main()
