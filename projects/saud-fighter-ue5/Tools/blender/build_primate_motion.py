#!/usr/bin/env python3
"""JAZIRAT AL-QIRUD -- the monkey island: the monkey's and the gorilla's motion.

Asked 2026-10-02 with the island ("... monkeys as enemy and big gorilla as
map boss ... full ik"). build_primates.py makes the two creatures; this
moves them: every clip the engine plays on a fighter, posed through IK on
their own skeletons, written to Content/Animation/Island/A_<Set>_<Clip>.fbx
with a manifest, DT_IslandMotion.csv.

    python3 build_primate_motion.py            build, check, export, draw (bpy)
    python3 build_primate_motion.py --bite     each rule broken once (bpy)

THE CLIPS, for each: Guard (a loop), Walk_Fwd / Back / Left / Right (loops,
at the creature's own pace), Block (a loop), Hit_Light, Hit_Heavy, Down,
GetUp, Death, Victory, and its strikes. A creature's strike is one of the
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

CHECKED (each rule broken once by --bite): a planted foot stays put
(a walk's moves at the pace); no foot under the floor; every loop closes;
every IK reach inside the limb (nothing stretched); knees bend forward; a
strike's fist or foot gets out in front by the contact frame; each clip as
long as its row; Down ends on the floor; the FBX read back.

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

# the creatures' own pace (cm/s): their walks are struck at it, and the
# level's fighter table carries the same number (DT_IslandFighters.csv)
PACE = dict(Monkey=300.0, Gorilla=260.0)
# a cycle's length (s) and the share of it a foot is down: a run's, so the
# planted foot's travel (pace x cycle x duty) stays inside the leg's reach
GAIT = dict(Monkey=(0.40, 0.40), Gorilla=(0.66, 0.45))
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

        def swing(b, head, target):
            """b's rest direction swung onto head->target, no twist."""
            rest_dir = (self.rest[b].to_3x3() @ Vector((0, 1, 0))).normalized()
            q = rest_dir.rotation_difference((target - head).normalized())
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
    # Walks: in place, the planted foot travels back under the body at the pace
    pace = PACE[name] / 100.0
    T, duty = GAIT[name]
    T = round(T * FPS) / FPS
    travel = pace * T * duty                           # metres a planted foot goes back
    for dname, dvec in (("Fwd", (0, -1)), ("Back", (0, 1)), ("Left", (1, 0)), ("Right", (-1, 0))):
        def walk(f, dvec=dvec):
            t = (f / FPS) / T
            p = dict(G)
            p["pelvis"] = (G["pelvis"][0], 0.0, G["pelvis"][2] - 0.03 * H - 0.012 * H * abs(math.sin(2 * math.pi * t)))
            for s, ph in (("l", 0.0), ("r", 0.5)):
                u = (t + ph) % 1.0
                fx, fy, fz = G["foot_" + s]
                fy = R.head["foot_" + s].y                 # stepping from under the hips, not from the guard's stagger
                if u < duty:                            # stance: carried back at the pace
                    k = u / duty
                    off, lift = travel * (0.5 - k), 0.0
                else:                                   # swing: forward again, lifted
                    k = (u - duty) / (1 - duty)
                    off, lift = travel * (-0.5 + ease(k)), 0.10 * H * math.sin(math.pi * k)
                p["foot_" + s] = (fx + dvec[0] * off, fy + dvec[1] * off, fz + lift)
                sw = math.sin(2 * math.pi * (t + ph + 0.5)) * 0.10 * H
                hx, hy, hz = G["hand_" + s]
                p["hand_" + s] = (hx + dvec[0] * sw * 0.5, hy + dvec[1] * sw, hz)
            if tail_wave:
                p["tail"] = [(a, 14 * math.sin(2 * math.pi * t + i * 0.8)) for i, (a, _) in enumerate(G["tail"])]
            return p
        out.append(("Walk_" + dname, round(T * FPS), walk, dict(loop=True, state="Walk", dir=dname, pace=PACE[name], stance=duty)))
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
    """Build every clip for one creature; returns (records, misses)."""
    import bpy
    from mathutils import Vector
    R = Rig(name)
    rows = attack_rows()
    recs = []
    miss = []
    for cname, n, fn, meta in clips(R, name, rows):
        frames = n + 1 if meta.get("loop") else n
        act = bpy.data.actions.new("A_%s_%s" % (name, cname))
        R.arm.animation_data_create()
        R.arm.animation_data.action = act
        world = []
        for f in range(frames):
            P = fn(f)
            M, st = R.pose(P)
            R.key(M, f)
            W = joints_world(R, M, [b for b in R.order])
            world.append(W)
            if st:
                miss.append("%s %s: %s reaches past its limb at frame %d" % (name, cname, ", ".join(st), f))
        rec = dict(name="A_%s_%s" % (name, cname), clip=cname, fighter=name, frames=frames, seconds=n / FPS,
                   contact=meta.get("contact", ""), limb=meta.get("limb", ""), loop=bool(meta.get("loop")),
                   state=meta["state"], dir=meta.get("dir", ""), attack=meta.get("attack", ""), world=world, meta=meta, action=act)
        miss += check_clip(R, rec, rows)
        recs.append(rec)
    if export:
        miss += export_all(R, recs)
    return R, recs, miss


def check_clip(R, rec, rows):
    miss = []
    W = rec["world"]
    nm = "%s %s" % (rec["fighter"], rec["clip"])
    H = R.H
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
    if st == "Walk":
        pace = rec["meta"]["pace"] / 100.0
        for s in ("l", "r"):
            vs = []
            for i in range(1, len(W)):
                if W[i]["foot_" + s].z - R.head["foot_" + s].z < 0.002 and W[i - 1]["foot_" + s].z - R.head["foot_" + s].z < 0.002:
                    vs.append((W[i]["foot_" + s] - W[i - 1]["foot_" + s]).length * FPS)
            if not vs or abs(sum(vs) / len(vs) - pace) > 0.08 * pace:
                miss.append("%s's planted %s foot moves at %.0f cm/s, not the pace %.0f" % (nm, s, (sum(vs) / len(vs) if vs else 0) * 100, pace * 100))
    # knees forward of the hip-ankle line (standing clips)
    if st not in ("Down", "Dead", "GetUp"):
        for s in ("l", "r"):
            worst = 0.0
            for w in W:
                h, k, a = w["thigh_" + s], w["calf_" + s], w["foot_" + s]
                u = (a - h).normalized()
                off = (k - h) - u * (k - h).dot(u)
                worst = max(worst, off.y)               # +Y is behind him
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
    # read back two clips a creature, frame for frame
    for rec in (recs[0], [r for r in recs if r["state"] == "Attack"][0]):
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
    """Every clip as its skeleton from the side, six frames across."""
    from PIL import Image, ImageDraw
    cols, cw, ch = 6, 120, 120
    rows = len(all_recs)
    img = Image.new("RGB", (cw * cols + 170, ch * rows + 10), (14, 16, 22))
    dr = ImageDraw.Draw(img)
    for i, rec in enumerate(all_recs):
        y0 = 5 + i * ch
        dr.text((6, y0 + ch // 2 - 6), rec["name"][2:], fill=(220, 230, 240))
        H = 2.2 if rec["fighter"] == "Gorilla" else 1.25
        n = len(rec["world"])
        for j in range(cols):
            f = round(j * (n - 1) / (cols - 1))
            W = rec["world"][f]
            x0 = 170 + j * cw
            dr.line([(x0, y0 + ch - 12), (x0 + cw - 8, y0 + ch - 12)], fill=(60, 70, 90))

            def pt(v):
                return (x0 + cw / 2 - v.y / H * (ch - 20), y0 + ch - 12 - v.z / H * (ch - 20))
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
]


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    try:
        import bpy  # noqa: F401
    except ImportError:
        print("runs with bpy (pip install bpy)")
        sys.exit(2)
    if "--bite" in args:
        caught = 0
        for what, sab, want in BITES:
            SABOTAGE.clear()
            SABOTAGE.add(sab)
            _, _, f = run("Monkey", export=False)
            hit = [x for x in f if want in x]
            caught += bool(hit)
            print("  %-24s %s  %s" % (what, "caught" if hit else "MISSED", (hit or f or ["(passed)"])[0]))
        SABOTAGE.clear()
        print("%d of %d caught" % (caught, len(BITES)))
        sys.exit(0 if caught == len(BITES) else 1)
    all_recs, allmiss = [], []
    for name in ("Monkey", "Gorilla"):
        R, recs, miss = run(name)
        RIG_PARENTS[name] = dict(R.parent)
        all_recs += recs
        allmiss += miss
        print("  %-8s %d clips, %d frames" % (name, len(recs), sum(r["frames"] for r in recs)))
    if allmiss:
        print("FAILED:\n  " + "\n  ".join(allmiss[:30]))
        sys.exit(1)
    m = manifest(all_recs)
    draw(all_recs)
    print("checks pass: planted feet, the floor, loops, reach, knees, strikes out by contact, lengths, Down on the floor; "
          "read back %s mm worst; %s" % (max(r.get("readback_mm", 0) for r in all_recs), os.path.relpath(m, ROOT)))


if __name__ == "__main__":
    main()
