#!/usr/bin/env python3
"""Real motion capture on Saud: the CMU library, retargeted through his rig.

    python3 mocap.py                 fetch (if needed), retarget, check, export
    python3 mocap.py --check         the source files and the cycles only (no bpy)
    python3 mocap.py --describe      what it would make, from where
    python3 mocap.py --sheet         also a contact sheet of every clip
    python3 mocap.py --bite          break each check's mechanism once
    python3 mocap.py --out DIR       write somewhere else than the project

Asked 2026-10-03 (Riyadh) as "use unreal engine motions package install
here", settled as both: free motion capture retargeted here, and editor
scripts for Epic's Game Animation Sample (Tools/unreal/gasp_retarget.py --
that one needs the sample, which only an Epic account can download, and is
not run). This is the first half.

THE SOURCE. The Carnegie Mellon University Graphics Lab Motion Capture
Database (mocap.cs.cmu.edu), in Bruce Hahne's 2010 BVH conversion, from the
copy at github.com/una-dinosauria/cmu-mocap. CMU: "This data is free for use
in research and commercial projects worldwide"; Hahne adds no restriction.
CMU asks for this acknowledgement, kept in the manifest's Source column and
in CLAUDE.md: "The data used in this project was obtained from
mocap.cs.cmu.edu. The database was created with funding from NSF
EIA-0196217." The BVH files used are committed beside this script
(Tools/blender/mocap/cmu/), each pinned by its SHA-256, so the build never
needs the network again and a changed file is refused.

WHAT IS TAKEN. Locomotion: the five speeds a man moves at, each a real
person's whole stride (CLIPS). They are captured at 120 frames a second,
every one walking straight along +Z with a T-pose added as its first frame.

HOW. Per clip:
  1. CYCLE: the stretch of two steps whose last frame is most like its
     first (every joint's position about the hips, and the hips' height and
     speed), searched over the clip; over its last stretch the cycle is
     crossfaded into the frames that led into its first, so the last frame
     runs into the first with its pose and its speed. The clip is in place:
     the hips' average travel is taken out and kept as the clip's speed.
  2. RETARGET: every one of Saud's bones takes the turn its joint in the
     capture made from the T-pose (that joint's world rotation now, against
     the T-pose's), after a fixed turn that lays his rest bone along the
     T-pose's -- so his own lengths, proportions and rest pose carry the
     actor's motion. The hips' path is scaled by his leg length over the
     actor's. Resampled to 30 frames a second.
  3. FEET: through the control rig (motion_ik), the legs in IK. Where the
     capture has a foot on the ground (low and still, measured on the
     capture itself), the foot is held: no skating, and the sole on the
     floor. A planted foot of an in-place clip slides back at exactly the
     clip's speed; that is what the game's movement cancels.
  4. EXPORT: baked to the 62 bones, one FBX a clip, in Content/Animation/
     Mocap, with DT_SaudMocap.csv: each clip's seconds, frames, loop, speed
     (cm/s), and its source.
"""
import os, sys, math, csv, json, time, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC_DIR = os.path.join(HERE, "mocap", "cmu")
# Beside Saud's own clips (since 2026-10-03, "do #92": the walk and the run
# picked by speed), where the game looks for every clip of his
# (USaudMotionComponent::Find: /Game/Animation/Saud/A_Saud_<Clip>) and
# where measure_plants.py measures them
OUT_DIR = os.path.join(PROJECT, "Content", "Animation", "Saud")
SOURCE_URL = "https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/master/data/{subject:03d}/{take}.bvh"
CREDIT = ("CMU Graphics Lab Motion Capture Database, mocap.cs.cmu.edu (funded by NSF EIA-0196217); "
          "BVH by B. Hahne")
FPS = 30

# The library: the five speeds a man moves at. `take` is the CMU subject_trial;
# `sha` pins the committed file; `steps` how many steps make the cycle (two:
# left and right); `what` is CMU's own index entry. The Run was 09_01
# first: too short a take (149 frames) to hold a cycle that closes after
# its T-pose, its seam hitched 4 cm; 35_18 closes, and runs at Saud's own
# game speed (3.2 m/s at his size against BaseMoveSpeed's 3.41).
CLIPS = [
    dict(name="Walk_Slow", take="07_04", what="slow walk", steps=2,
         sha="320fceb9f8269b8d44f5142385e98e236eccc24cee3728d8227a4933abb82564"),
    dict(name="Walk", take="07_01", what="walk", steps=2,
         sha="f8d82ea6ed1aab0cb7d9ee680f476b65471e2322e1da84add8a8527a2cb0b9a2"),
    dict(name="Walk_Brisk", take="08_01", what="walk", steps=2,
         sha="4e6cc1e0aa8b6b112be25b6aab5db8f176094181280b2c8ebcf903ede66e6e98"),
    dict(name="Jog", take="02_03", what="run/jog", steps=2,
         sha="6f4d38b92b041221030de2e1058903e0f7a8fa08f9c6c9efabf7df9a128011ac"),
    dict(name="Run", take="35_18", what="run/jog", steps=2,
         sha="e0a8b366b4cf33b6b97668541f5c8c6bbcaa9a99e14472e195c0939611737989"),
]

# Saud's bones and the capture's: each of his bones takes the turn of the
# joint it names; the second name is the joint (or "end", the end site) its
# T-pose direction is measured to -- the next one that is not at the same
# place (CMU's Neck sits on Spine1, its FingerBase on the Hand).
MAP = {
    "pelvis": ("Hips", None),
    "spine_01": ("LowerBack", "Spine"), "spine_02": ("Spine", "Spine1"), "spine_03": ("Spine1", "Neck1"),
    "neck_01": ("Neck", "Head"), "head": ("Head", "end"),
}
for _s, _S in (("l", "Left"), ("r", "Right")):
    MAP.update({
        "clavicle_" + _s: (_S + "Shoulder", _S + "Arm"), "upperarm_" + _s: (_S + "Arm", _S + "ForeArm"),
        "lowerarm_" + _s: (_S + "ForeArm", _S + "Hand"), "hand_" + _s: (_S + "Hand", _S + "HandIndex1"),
        "thigh_" + _s: (_S + "UpLeg", _S + "Leg"), "calf_" + _s: (_S + "Leg", _S + "Foot"),
        "foot_" + _s: (_S + "Foot", _S + "ToeBase"), "ball_" + _s: (_S + "ToeBase", "end"),
    })
SIDES = ("l", "r")
SIDE_NAME = {"l": "Left", "r": "Right"}
# What the retarget is held to: each of Saud's segments (bone head to bone
# head) against the capture's, in direction, every frame; the legs looser,
# because the held feet and the floor move them on purpose.
# (The spine and neck are three bones on his side and more on the actor's,
# so their chords differ by proportion, not by retarget: not held here.)
SEGMENTS = []
for _s, _S in (("l", "Left"), ("r", "Right")):
    SEGMENTS += [("upperarm_" + _s, "lowerarm_" + _s, _S + "Arm", _S + "ForeArm", 3.0),
                 ("lowerarm_" + _s, "hand_" + _s, _S + "ForeArm", _S + "Hand", 3.0),
                 ("thigh_" + _s, "calf_" + _s, _S + "UpLeg", _S + "Leg", 15.0),
                 ("calf_" + _s, "foot_" + _s, _S + "Leg", _S + "Foot", 15.0)]
# The capture's Y-up, +Z-forward frame to Blender's Z-up, -Y-forward one
# (a proper rotation: the man's left is +X in both).
C = ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0))

# A foot is on the ground where, in the capture, its ankle or its toe is
# within CONTACT_H of that joint's lowest over the cycle and moving slower
# than CONTACT_V of the clip's own speed; a contact shorter than CONTACT_MIN
# frames is noise, not a step.
CONTACT_H = 0.035          # m, at Saud's size
CONTACT_V = 0.30
CONTACT_MIN = 3
EASE = 3                   # frames a hold eases in and out over
# what the checks hold the built clips to
SKATE_MM = 5.0             # a held foot's ball off its plant, at most
FLOOR_MM = 3.0             # the lowest sole corner through the floor, at most
SEAM_MM = 5.0              # the hitch at the loop's seam, over the cycle's own, at most
SPEED_OFF = 0.02           # the clip's speed against the capture's, scaled

SABOTAGE = set()


# ================================================================ the source
def source_path(clip):
    return os.path.join(SRC_DIR, clip["take"] + ".bvh")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(clip):
    """The committed file, or (once, if it is missing) the mirror's; either
    way held to its pinned SHA-256."""
    path = source_path(clip)
    if not os.path.exists(path):
        import urllib.request
        os.makedirs(SRC_DIR, exist_ok=True)
        subject = int(clip["take"].split("_")[0])
        url = SOURCE_URL.format(subject=subject, take=clip["take"])
        with urllib.request.urlopen(url, timeout=60) as r, open(path, "wb") as fh:
            fh.write(r.read())
    got = sha256(path)
    assert got == clip["sha"], "%s is not the file this build was made from (sha256 %s)" % (path, got)
    return path


# ================================================================ BVH
def _np():
    import numpy as np
    return np


def _rot(axis, deg):
    np = _np()
    a = np.radians(deg); c, s = np.cos(a), np.sin(a)
    R = np.zeros((len(a), 3, 3))
    i, j = {"X": (1, 2), "Y": (2, 0), "Z": (0, 1)}[axis]
    k = 3 - i - j
    R[:, k, k] = 1.0
    R[:, i, i] = c; R[:, i, j] = -s; R[:, j, i] = s; R[:, j, j] = c
    return R


def parse(path):
    """The hierarchy and the frames: [joint dicts], seconds a frame, values."""
    np = _np()
    tok = open(path).read().split()
    i, joints, stack = 0, [], []
    while tok[i] != "MOTION":
        t = tok[i]
        if t in ("ROOT", "JOINT"):
            joints.append(dict(name=tok[i + 1], parent=stack[-1] if stack else -1, ch=[], end=None, off=None))
            i += 2
        elif t == "End":
            assert tok[i + 2] == "{" and tok[i + 3] == "OFFSET"
            joints[stack[-1]]["end"] = np.array([float(v) for v in tok[i + 4:i + 7]])
            assert tok[i + 7] == "}"
            i += 8
        elif t == "{":
            stack.append(len(joints) - 1); i += 1
        elif t == "}":
            stack.pop(); i += 1
        elif t == "OFFSET":
            joints[stack[-1]]["off"] = np.array([float(v) for v in tok[i + 1:i + 4]]); i += 4
        elif t == "CHANNELS":
            n = int(tok[i + 1]); joints[stack[-1]]["ch"] = tok[i + 2:i + 2 + n]; i += 2 + n
        else:
            i += 1
    assert tok[i + 1] == "Frames:" and tok[i + 3] == "Frame" and tok[i + 4] == "Time:"
    n, dt = int(tok[i + 2]), float(tok[i + 5])
    data = np.array([float(v) for v in tok[i + 6:]]).reshape(n, -1)
    assert data.shape[1] == sum(len(j["ch"]) for j in joints), "%s: the frames do not fit the channels" % path
    return joints, dt, data


def fk(joints, data):
    """Every joint's world rotation (n, J, 3, 3) and position (n, J, 3), in
    the capture's own frame and units; each channel turns in the order the
    file lists it."""
    np = _np()
    n, col, G, P = len(data), 0, [], []
    for j in joints:
        R = np.repeat(np.eye(3)[None], n, 0)
        T = np.repeat(j["off"][None], n, 0).copy()
        for c in j["ch"]:
            v = data[:, col]; col += 1
            if c.endswith("position"):
                T[:, "XYZ".index(c[0])] += v
            else:
                R = R @ _rot(c[0], v)
        if j["parent"] < 0:
            G.append(R); P.append(T)
        else:
            p = j["parent"]
            G.append(G[p] @ R); P.append(P[p] + np.einsum("nij,nj->ni", G[p], T))
    return np.stack(G, 1), np.stack(P, 1)


def end_of(joints, P, name, frame=0):
    """Where a joint's segment ends at `frame`: its child's joint, or its
    end site."""
    np = _np()
    ix = {j["name"]: i for i, j in enumerate(joints)}
    return P[frame, ix[name]]


# ================================================================ the capture
class Capture:
    """One BVH, read, in Blender's frame at Saud's size: `scale` is his leg
    over the actor's. Rotations are the turn each joint made from the
    T-pose (frame 0), so a bone at rest in the T-pose has none."""

    def __init__(self, path, saud_leg):
        np = _np()
        self.joints, self.dt, data = parse(path)
        G, P = fk(self.joints, data)
        self.ix = {j["name"]: i for i, j in enumerate(self.joints)}
        Cm = np.array(C)
        ix = self.ix
        leg = (np.linalg.norm(P[0, ix["LeftUpLeg"]] - P[0, ix["LeftLeg"]])
               + np.linalg.norm(P[0, ix["LeftLeg"]] - P[0, ix["LeftFoot"]]))
        self.scale = saud_leg / leg
        self.P = np.einsum("ij,nkj->nki", Cm, P) * self.scale            # (n, J, 3), metres
        Gb = np.einsum("ij,nkjl,ml->nkim", Cm, G, Cm)                    # C G C^T
        self.D = np.einsum("nkij,klj->nkil", Gb, Gb[0])                  # G(f) G(0)^T
        self.rest_dir = {}
        for j in self.joints:
            i = ix[j["name"]]
            if j["end"] is not None:
                tip = P[0, i] + G[0, i] @ j["end"]
                self.rest_dir[j["name"] + ":end"] = Cm @ (tip - P[0, i])
        self.T0 = self.P[0]

    def direction0(self, joint, to):
        np = _np()
        if to == "end":
            v = self.rest_dir[joint + ":end"]
        else:
            v = self.T0[self.ix[to]] - self.T0[self.ix[joint]]
        return v / np.linalg.norm(v)


def _features(cap, frames):
    """Per frame: every joint about the hips (horizontal travel out) and
    how it is moving, the hips' height, and the hips' horizontal speed --
    what the seam is judged on."""
    np = _np()
    P = cap.P[frames]
    hips = P[:, cap.ix["Hips"]]
    rel = P - hips[:, None, :]
    v = np.gradient(cap.P[:, cap.ix["Hips"], :2], axis=0)[frames] / cap.dt
    # how every joint is moving about the hips, as its travel over a tenth
    # of a second: two poses alike but moving differently join with a jolt
    # (a run's swinging leg covers 10 cm a frame; matched on pose alone its
    # loop hitched 4 cm)
    allrel = cap.P - cap.P[:, cap.ix["Hips"]][:, None, :]
    rv = np.gradient(allrel, axis=0)[frames] / cap.dt * 0.1
    return np.concatenate([rel.reshape(len(frames), -1), hips[:, 2:3], v * 0.25,
                           rv.reshape(len(frames), -1)], axis=1)


def find_cycle(cap, steps=2, broken=False):
    """(start, length) in capture frames: the two-step stretch whose end is
    most like its start, between 0.35 s and 2.4 s long, never in the
    T-pose's first tenth of a second nor the clip's last."""
    np = _np()
    n = len(cap.P)
    skip = max(int(0.25 / cap.dt), int(n * 0.12))
    F = _features(cap, np.arange(n))
    best = None
    lo, hi = int(0.35 / cap.dt), int(2.4 / cap.dt)
    for s in range(skip, n - skip - lo):
        for L in range(lo, min(hi, n - skip - s)):
            d = float(np.linalg.norm(F[s] - F[s + L]))
            # the shortest close match is one stride; a longer one is two
            if best is None or d < best[0] - 1e-9:
                best = (d, s, L)
    d, s, L = best
    if broken:
        L = int(L * 0.8)
        d = float(np.linalg.norm(F[s] - F[s + L]))
    return s, L, d


def contacts(cap, s, L):
    """Per side, a bool per capture frame of the cycle: the foot is down.
    Measured on the capture at Saud's size, in the world (not in place), so
    a planted foot is still."""
    np = _np()
    out = {}
    hips = cap.P[s:s + L + 1, cap.ix["Hips"]]
    speed = np.linalg.norm(hips[-1, :2] - hips[0, :2]) / (L * cap.dt)
    for sd in SIDES:
        down = np.zeros(L, bool)
        for jn in (SIDE_NAME[sd] + "Foot", SIDE_NAME[sd] + "ToeBase"):
            p = cap.P[s:s + L, cap.ix[jn]]
            v = np.linalg.norm(np.gradient(cap.P[:, cap.ix[jn], :2], axis=0)[s:s + L], axis=1) / cap.dt
            low = p[:, 2] <= p[:, 2].min() + CONTACT_H
            down |= low & (v <= CONTACT_V * speed)
        # a gap of two frames or less (at 30 fps) inside a step -- the heel
        # up before the toe is still -- is the same step
        gap = int(round(2.0 / (cap.dt * FPS)))
        idx = [i for i in range(L) if down[i]]
        for a, b in zip(idx, idx[1:]):
            if 1 < b - a <= gap + 1:
                down[a:b] = True
        # runs shorter than CONTACT_MIN frames (at 30 fps) are noise
        keep = down.copy()
        i = 0
        while i < L:
            if down[i]:
                j = i
                while j < L and down[j]:
                    j += 1
                if (j - i) * cap.dt * FPS < CONTACT_MIN:
                    keep[i:j] = False
                i = j
            else:
                i += 1
        out[sd] = keep
    return out, speed


def cycle_frames(cap, s, L):
    """The cycle resampled to FPS: [(capture frame as a float)], the last
    frame one step short of the first again."""
    n = max(4, int(round(L * cap.dt * FPS)))
    return [s + L * k / n for k in range(n)]


def summary(clip, saud_leg=0.93):
    """The pure part of a clip, for --check and --describe: its cycle, its
    speed and its steps."""
    np = _np()
    cap = Capture(fetch(clip), saud_leg)
    s, L, d = find_cycle(cap, clip["steps"], broken="cycle" in SABOTAGE and clip["name"] == "Walk")
    down, speed = contacts(cap, s, L)
    return dict(cap=cap, start=s, length=L, seam=d, speed=speed, down=down,
                seconds=L * cap.dt, frames=len(cycle_frames(cap, s, L)))


def check_source():
    """No bpy: every file is the pinned one, every clip finds a cycle with a
    small seam and a step on each foot, and the speeds rise in order."""
    fails, rows = [], []
    for clip in CLIPS:
        try:
            r = summary(clip)
        except AssertionError as e:
            fails.append(str(e)); continue
        steps = {sd: _runs(r["down"][sd]) for sd in SIDES}
        rows.append((clip, r))
        if r["seam"] > 0.35:
            fails.append("%s: no cycle closes (seam %.2f)" % (clip["name"], r["seam"]))
        for sd in SIDES:
            if steps[sd] < 1:
                fails.append("%s: the %s foot never touches the ground in the cycle" % (clip["name"], SIDE_NAME[sd].lower()))
    speeds = [r["speed"] for _c, r in rows]
    if speeds != sorted(speeds):
        fails.append("the clips are not in order of speed: %s" % ", ".join("%.2f" % v for v in speeds))
    return fails, rows


def _runs(b):
    n, prev = 0, False
    for v in list(b) + [False]:
        if v and not prev:
            n += 1
        prev = v
    # a run that wraps round the seam is one step, not two
    if len(b) and b[0] and b[-1]:
        n -= 1
    return n


# ================================================================ in Blender
def retarget(au, clip, r):
    """The cycle, frame by frame, on Saud's control rig: [(loc, world)]
    and what the checks need."""
    import bpy
    import motion_ik as M
    import build_saud as Lg
    from mathutils import Matrix, Vector, Quaternion
    np = _np()
    rig, pb = au.rig, au.pb
    cap, s, L = r["cap"], r["start"], r["length"]
    frames = cycle_frames(cap, s, L)
    # ---- each bone's fixed turn: his rest direction onto the T-pose's
    rest = {n: rig.data.bones[n].matrix_local.to_3x3() for n in MAP}
    align = {}
    for n, (jn, to) in MAP.items():
        if to is None:
            align[n] = Matrix.Identity(3)
            continue
        mine = (rest[n] @ Vector((0.0, 1.0, 0.0))).normalized()
        theirs = Vector(cap.direction0(jn, to))
        align[n] = mine.rotation_difference(theirs).to_matrix()
    order = [n for n in Lg._hierarchy_order(rig) if n in MAP and n != "pelvis"]
    jmap = dict((n, v[0]) for n, v in MAP.items())
    if "mirror" in SABOTAGE:
        # the arms read off the wrong side of the actor
        for n in list(jmap):
            if n.startswith(("upperarm", "lowerarm")):
                jmap[n] = jmap[n].replace("Left", "@").replace("Right", "Left").replace("@", "Right")
    hips_i = cap.ix["Hips"]
    # ---- the seam, crossfaded: over the cycle's last XF the capture is
    # blended into the same moment one cycle earlier -- the frames that led
    # into the cycle's first -- so the end runs into the start with its pose
    # AND its speed. (A linear spread of the end's offset matched the pose
    # only: the run's hips turned at the seam twice as fast as anywhere
    # else, and its knee hitched 21 mm.)
    XF = 0.0 if "seam" in SABOTAGE else max(0.0, min(0.3, (s - 2.0) / L))
    def blend(u):
        if XF <= 0.0 or u <= 1.0 - XF:
            return 0.0
        t = (u - (1.0 - XF)) / XF
        return t * t * (3.0 - 2.0 * t)
    def turn(jn, f):
        i0 = int(math.floor(f)); u = f - i0
        a = Quaternion(Matrix(cap.D[i0, cap.ix[jn]].tolist()).to_quaternion())
        b = Quaternion(Matrix(cap.D[min(i0 + 1, len(cap.D) - 1), cap.ix[jn]].tolist()).to_quaternion())
        if a.dot(b) < 0:
            b.negate()
        return a.slerp(b, u)
    def turned(jn, f, u):
        a, b = turn(jn, f), turn(jn, f - L)
        if a.dot(b) < 0:
            b.negate()
        return a.slerp(b, blend(u))
    def hips_at(f):
        i0 = int(math.floor(f)); u = f - i0
        return cap.P[i0, hips_i] * (1 - u) + cap.P[min(i0 + 1, len(cap.P) - 1), hips_i] * u
    h0, h1 = hips_at(s), hips_at(s + L)
    travel = h1 - h0          # its height's drift too
    speed = float(np.linalg.norm(travel[:2])) / (L * cap.dt)
    # the whole clip turned so the travel is his forward, -Y
    Y = Matrix.Rotation(math.atan2(travel[0], -travel[1]), 3, "Z").inverted()
    rest_pelvis = rig.data.bones["pelvis"].head_local.copy()
    hips_rest = Vector(cap.T0[hips_i])
    mean = Vector(np.mean([hips_at(f) - (f - s) / L * travel for f in frames], axis=0).tolist())
    hips_off = pb["CTRL_hips"].bone.matrix_local.inverted() @ rig.data.bones["pelvis"].matrix_local
    out = []
    feet = {sd: [] for sd in SIDES}
    for k, f in enumerate(frames):
        u = (f - s) / L
        au.begin()
        # the hips: the capture's path in place, about his own rest
        w = blend(u)
        here = hips_at(f) - u * travel
        then = hips_at(f - L) - (u - 1.0) * travel
        h = here * (1.0 - w) + then * w
        p = Y @ (Vector(h.tolist()) - mean)
        p.z = h[2] - hips_rest.z
        want_pelvis = (Y @ turned("Hips", f, u).to_matrix() @ align["pelvis"] @ rest["pelvis"])
        m = want_pelvis.to_4x4()
        m.translation = rest_pelvis + Vector((p.x, p.y, p.z))
        pb["CTRL_hips"].matrix = m @ hips_off.inverted()
        M.upd()
        for n in order:
            jn = jmap[n]
            q = turned(jn, f, u)
            w = (Y @ q.to_matrix() @ align[n] @ rest[n]).to_4x4()
            w.translation = pb[n].matrix.translation
            pb[n].matrix = w
            M.upd()
        fkr = au.read()
        for sd in SIDES:
            feet[sd].append(dict(foot=fkr["foot_" + sd].copy(), knee=fkr["kn_" + sd].copy(),
                                 hip=fkr["hip_" + sd].copy(), ankle=fkr["an_" + sd].copy(),
                                 ball=fkr["ball_" + sd].copy()))
        def at(jn):
            i0 = int(math.floor(f)); w = f - i0
            v = cap.P[i0, cap.ix[jn]] * (1 - w) + cap.P[min(i0 + 1, len(cap.P) - 1), cap.ix[jn]] * w
            return Vector(v.tolist())
        dirs = {(a, b): (Y @ (at(cb) - at(ca))).normalized() for a, b, ca, cb, _t in SEGMENTS}
        # the crossfade turns a bone off the actor by as much as the two
        # moments it blends differ, as far as it has blended: that is allowed
        allow = {}
        for a, b, _ca, _cb, _t in SEGMENTS:
            q0, q1 = turn(jmap[a], f), turn(jmap[a], f - L)
            allow[(a, b)] = blend(u) * math.degrees(q0.rotation_difference(q1).angle)
        out.append(dict(hips=pb["CTRL_hips"].matrix.copy(), body={n: pb[n].matrix.copy() for n in order},
                        dirs=dirs, allow=allow))
    return out, feet, speed, Y


def plant(feet, down, speed, frames, cap, s, L, rig):
    """Each foot's control for every frame: where the capture has it down,
    held -- its ball on one point of the floor, carried back at the clip's
    speed (in place) -- and eased back to the capture's over EASE frames
    either side. The point is the one the capture's ball stays nearest
    through the whole contact (its mean, less the floor's travel), so the
    hold takes the least it can from the capture at either end: anchored
    on the contact's first frame instead, a run's push-off left the foot
    9 cm off its own swing, and the release popped."""
    from mathutils import Vector
    n = len(frames)
    back = Vector((0.0, speed / FPS, 0.0))            # forward is -Y: the floor slides +Y
    targets = {}
    for sd in SIDES:
        d = down[sd]
        idx = [min(len(d) - 1, int(round(f - s))) for f in frames]
        on = [bool(d[i]) for i in idx]
        if "skate" in SABOTAGE:
            on = [False] * n
        # the contacts as runs of frames, one that wraps round the seam whole
        runs, k0 = [], next((k for k in range(n) if not on[k]), None)
        if k0 is not None:
            cur = []
            for step in range(1, n + 1):
                k = (k0 + step) % n
                if on[k]:
                    cur.append(k)
                elif cur:
                    runs.append(cur); cur = []
            if cur:
                runs.append(cur)
        else:
            runs = [list(range(n))]
        held = [None] * n
        for run in runs:
            ages = range(len(run))
            pts = [feet[sd][k]["ball"] - back * a for k, a in zip(run, ages)]
            anchor = sum(pts, Vector()) / len(pts)
            for k, a in zip(run, ages):
                sh = anchor + back * a - feet[sd][k]["ball"]
                held[k] = Vector((sh.x, sh.y, 0.0))
        eased = []
        for k in range(n):
            if held[k] is not None:
                eased.append(held[k]); continue
            got = Vector()
            for dk in range(1, EASE + 1):
                w = 1.0 - dk / (EASE + 1.0)
                w = w * w * (3.0 - 2.0 * w)
                for kk in ((k - dk) % n, (k + dk) % n):
                    if held[kk] is not None and got.length == 0.0:
                        got = held[kk] * w
            eased.append(got)
        mats = [x["foot"].copy() for x in feet[sd]]
        for k in range(n):
            mats[k].translation = mats[k].translation + eased[k]
        targets[sd] = (mats, on)
    return targets


def pitch_clear(au, sd, fm, pole, tries=6):
    """The foot control turned about the ankle, about the foot's own
    across axis, until its lowest sole corner is on the floor (if it was
    under it). Secant steps on the measured height; returns the matrix."""
    import build_saud as Lg
    from mathutils import Matrix
    def low_at(th):
        m = fm.copy()
        at = m.translation.copy()
        axis = (m.to_3x3() @ __import__("mathutils").Vector((1.0, 0.0, 0.0))).normalized()
        r = Matrix.Translation(at) @ Matrix.Rotation(th, 4, axis) @ Matrix.Translation(-at)
        m = r @ m
        au.leg(sd, m, pole)
        return min(p.z for _n, p in Lg.sole_points(au.rig, sd)), m
    l0, m0 = low_at(0.0)
    if l0 >= -0.0002:
        return m0
    a, la = 0.0, l0
    b, lb = 0.05, low_at(0.05)[0]
    if lb < la:                                    # the other way raises the toe
        b, lb = -0.05, low_at(-0.05)[0]
    best = (la, a)
    for _ in range(tries):
        if abs(lb - la) < 1e-7:
            break
        c = b - lb * (b - a) / (lb - la)
        c = max(-0.6, min(0.6, c))
        lc, _m = low_at(c)
        a, la, b, lb = b, lb, c, lc
        if abs(lc) < 0.0003:
            break
    th = b if lb >= -0.0005 else max((x for x in (a, b)), key=lambda x: low_at(x)[0])
    return low_at(th)[1]


def firmness(on):
    """Per frame, how firmly the foot is down: 1 inside a contact, easing to
    0 over its first and last EASE frames, 0 off the ground."""
    n = len(on)
    out = [0.0] * n
    if all(on):
        return [1.0] * n
    k0 = next(k for k in range(n) if not on[k])
    run = []
    for step in range(1, n + 1):
        k = (k0 + step) % n
        if on[k]:
            run.append(k)
            continue
        for i, kk in enumerate(run):
            out[kk] = min(1.0, (i + 1) / (EASE + 1.0), (len(run) - i) / (EASE + 1.0))
        run = []
    return out


def knee_pole(x):
    """Where the knee points: the way the capture bent it, off the hip-to-
    ankle line, and -- so a nearly straight leg (a run's push-off, a heel
    strike) cannot flip it -- always a centimetre forward. (The foot's own
    facing was tried first: a swinging foot points at the floor, and its
    level part turned the knee 6 cm sideways in a frame.)"""
    from mathutils import Vector
    bend = x["knee"] - (x["hip"] + x["ankle"]) * 0.5
    return x["knee"] + (bend + Vector((0.0, -0.01, 0.0))).normalized() * 0.5


def build_clip(au, clip, r):
    """One clip: retargeted, the feet held and grounded through IK, and
    every frame recorded for the bake."""
    import motion_ik as M
    import build_saud as Lg
    from mathutils import Vector, Matrix
    cap, s, L = r["cap"], r["start"], r["length"]
    frames = cycle_frames(cap, s, L)
    body, feet, speed, Y = retarget(au, clip, r)
    targets = plant(feet, r["down"], speed, frames, cap, s, L, au.rig)
    pb = au.pb
    firm = {sd: firmness(targets[sd][1]) for sd in SIDES}
    # ---- the floor: the capture's ground is not his. The lowest sole corner
    # of every held frame, through IK, is brought to z = 0 by moving the
    # hips and the held feet together; found on a first pass.
    recs, drops = [], []
    lift = 0.0
    for attempt in range(2):
        recs, lows = [], []
        for k, f in enumerate(frames):
            au.begin()
            h = body[k]["hips"].copy()
            h.translation.z += lift
            pb["CTRL_hips"].matrix = h
            M.upd()
            for n, m in body[k]["body"].items():
                if n.startswith(("thigh", "calf", "foot", "ball")):
                    continue
                w = m.copy(); w.translation = pb[n].matrix.translation
                pb[n].matrix = w
                M.upd()
            fms, poles = {}, {}
            for sd in SIDES:
                mats, on = targets[sd]
                fm = mats[k].copy()
                fm.translation.z += lift
                pole = knee_pole(feet[sd][k])
                pole.z += lift
                au.leg(sd, fm, pole)
                fms[sd], poles[sd] = fm, pole
            planted = [sd for sd in SIDES if targets[sd][1][k]]
            drop = au.settle(planted, limit=0.25, max_reach=0.995) if planted else 0.0
            # the soles: a held foot's lowest corner ON the floor, a swinging
            # foot's never under it -- the foot moved up or down, its roll
            # kept, and the leg solved again
            if attempt == 1 and "floor" not in SABOTAGE:
                for sd in SIDES:
                    # On the flat of a stance the foot is simply set on the
                    # floor (its ball is held; it must not turn). Anywhere
                    # else, a sole corner under the floor: the foot pitched about
                    # its ankle until it is not -- the leg stays exactly as
                    # the actor's. (Lifted whole instead, a toe-off, whose
                    # toe his longer foot puts 5 cm under the floor, bent
                    # the knee 22 degrees off the actor's.) Only a foot that
                    # cannot pitch clear is lifted.
                    flat = sd in planted and firm[sd][k] >= 1.0
                    if not flat:
                        fms[sd] = pitch_clear(au, sd, fms[sd], poles[sd])
                    low = min(p.z for _n, p in Lg.sole_points(au.rig, sd))
                    # down onto the floor, a held foot, as firmly as it is
                    # down: fully mid-stance, not at all at a heel strike
                    # or a toe-off, where the actor's foot is leaving
                    shift = -low if low < 0.0 else (-low * firm[sd][k] if sd in planted else 0.0)
                    if abs(shift) > 0.0002:
                        fms[sd].translation.z += shift
                        au.leg(sd, fms[sd], poles[sd])
                if planted:
                    drop += au.settle(planted, limit=0.25, max_reach=0.995)
            drops.append(drop)
            for sd in planted:
                lows.append(min(p.z for _n, p in Lg.sole_points(au.rig, sd)))
            loc, world = au.record()
            soles = {sd: [p.copy() for _n, p in Lg.sole_points(au.rig, sd)] for sd in SIDES}
            recs.append((loc, world, soles))
        if not lows:
            break
        import statistics
        low = statistics.median(lows)
        if attempt == 0 and "floor" not in SABOTAGE:
            lift -= low
    return recs, speed, frames, targets, max(drops) if drops else 0.0, body


def verify(clip, recs, speed, r, targets, body):
    """The built clip against its rules: held feet do not skate, no sole
    through the floor, the loop closes, the speed is the capture's."""
    fails = []
    n = len(recs)
    # 1. held feet: the ball's travel against the floor's, frame to frame
    # -- on the flat of each stance (firmness 1): at a heel strike and a
    # toe-off the foot rolls over its heel and its toe, as a real one does
    worst_skate = 0.0
    for sd in SIDES:
        on = [f >= 1.0 for f in firmness(on_flags(r, sd, n))]
        for k in range(n):
            k1 = (k + 1) % n
            if on[k] and on[k1] and k1 != 0:
                a, b = recs[k][1]["ball_" + sd], recs[k1][1]["ball_" + sd]
                want = speed / FPS
                slip = math.hypot(b.x - a.x, (b.y - a.y) - want)
                worst_skate = max(worst_skate, slip)
    if worst_skate * 1000 > SKATE_MM:
        fails.append("%s: a held foot skates %.1f mm in a frame (at most %.0f)" % (clip["name"], worst_skate * 1000, SKATE_MM))
    # 2. the floor: no sole through it, and a foot on the flat of its
    # stance standing on it, not over it
    low = min(min(p.z for p in rec[2][sd]) for rec in recs for sd in SIDES)
    if -low * 1000 > FLOOR_MM:
        fails.append("%s: a sole goes %.1f mm through the floor (at most %.0f)" % (clip["name"], -low * 1000, FLOOR_MM))
    hover = 0.0
    for sd in SIDES:
        firm = firmness(on_flags(r, sd, n))
        for k in range(n):
            if firm[k] >= 1.0:
                hover = max(hover, min(p.z for p in recs[k][2][sd]))
    if hover * 1000 > FLOOR_MM:
        fails.append("%s: a planted foot stands %.1f mm over the floor (at most %.0f)" % (clip["name"], hover * 1000, FLOOR_MM))
    # 3. the seam: no hitch where the last frame runs into the first. A
    # bone's change of step (its second difference) across the seam is held
    # to the largest it makes anywhere else in the cycle -- a swinging
    # foot's own swing -- plus SEAM_MM.
    seam, at = 0.0, None
    W = [rec[1] for rec in recs]
    for nm in W[0]:
        acc = [(W[(k + 1) % n][nm] - W[k][nm] * 2.0 + W[k - 1][nm]).length for k in range(n)]
        inner = max(acc[1:n - 1])
        over = max(acc[0], acc[n - 1]) - inner
        if over > seam:
            seam, at = over, nm
    if seam * 1000 > SEAM_MM:
        fails.append("%s: the loop hitches %.0f mm at %s where it runs back to its start (at most %.0f over its own swing)"
                     % (clip["name"], seam * 1000, at, SEAM_MM))
    # 4. the retarget: every segment along the capture's
    worst, where = 0.0, None
    for k, rec in enumerate(recs):
        w = rec[1]
        for a, b, ca, cb, tol in SEGMENTS:
            got = (w[b] - w[a]).normalized()
            ang = math.degrees(got.angle(body[k]["dirs"][(a, b)]))
            lim = tol + body[k]["allow"][(a, b)]
            if ang - lim > worst:
                worst, where = ang - lim, (a, k + 1, ang, lim)
    if where:
        fails.append("%s: %s points %.0f degrees off the capture at frame %d (at most %.0f)"
                     % (clip["name"], where[0], where[2], where[1], where[3]))
    # 5. the speed
    want = r["speed"]
    if abs(speed / want - 1.0) > SPEED_OFF:
        fails.append("%s: moves at %.2f m/s, the capture at %.2f" % (clip["name"], speed, want))
    return fails, dict(skate=worst_skate, floor=low, seam=seam)


def strike_check(clip, r, n, k0):
    """The loop, turned to start at k0, starts as the left foot strikes."""
    on = on_flags(r, "l", n)
    on = on[k0:] + on[:k0]
    if not (on[0] and not on[-1]):
        return ["%s: the loop does not start as the left foot strikes" % clip["name"]]
    return []


def left_strike(r, n):
    """The frame the left foot comes down: the first of its contact, or 0."""
    on = on_flags(r, "l", n)
    if "phase" in SABOTAGE:
        return 0
    for k in range(n):
        if on[k] and not on[k - 1]:
            return k
    return 0


def on_flags(r, sd, n):
    """Frame by frame (at FPS), whether the capture has that foot down."""
    s, L, d = r["start"], r["length"], r["down"][sd]
    frames = cycle_frames(r["cap"], s, L)
    return [bool(d[min(len(d) - 1, int(round(f - s)))]) for f in frames]


def build(out_dir=OUT_DIR, sheet=False):
    import bpy
    import motion_ik as M
    t0 = time.time()
    rig = M.make_rig()
    au = M.Author(rig)
    saud_leg = rig.data.bones["thigh_l"].length + rig.data.bones["calf_l"].length
    authored, rows, fails = [], [], []
    for clip in CLIPS:
        r = summary(clip, saud_leg)
        recs, speed, frames, targets, drop, body = build_clip(au, clip, r)
        f, m = verify(clip, recs, speed, r, targets, body)
        fails += f
        c = dict(name="A_Saud_Mocap_" + clip["name"], frames=len(recs), seconds=len(recs) / FPS,
                 limb=None, contact=-1, display="CMU %s %s, %.2f m/s" % (clip["take"], clip["what"], speed))
        # every loop starts as the left foot strikes, so a walk crossfaded
        # into a run (SaudFeel::CutBetween matches the phase) lands foot on foot
        k0 = left_strike(r, len(recs))
        fails += strike_check(clip, r, len(recs), k0)
        recs = recs[k0:] + recs[:k0]
        authored.append((c, [(lo, w) for lo, w, _s in recs]))
        rows.append((clip, r, c, speed, m, drop))
        print("%6.1fs  %-10s %3d frames, %.2f m/s, skate %.1f mm, floor %+.1f mm, seam %.0f mm, hips settled %.1f cm"
              % (time.time() - t0, clip["name"], len(recs), speed, m["skate"] * 1000, m["floor"] * 1000,
                 m["seam"] * 1000, drop * 100))
    assert not fails, "the mocap clips break their rules:\n  " + "\n  ".join(fails)
    made = M.to_actions(rig, authored)
    err, where = M.bake_error(rig, made)
    assert err < 0.0005, "the bake does not reproduce the rig: %.2f mm at %s" % (err * 1000, where)
    os.makedirs(out_dir, exist_ok=True)
    for c, act, _fr in made:
        rig.animation_data.action = act
        bpy.context.scene.frame_start = 1
        bpy.context.scene.frame_end = c["frames"]
        bpy.ops.object.select_all(action="DESELECT")
        rig.select_set(True)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.export_scene.fbx(
            filepath=os.path.join(out_dir, c["name"] + ".fbx"),
            use_selection=True, object_types={"ARMATURE"}, add_leaf_bones=False,
            bake_anim=True, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
            bake_anim_step=1.0, bake_anim_simplify_factor=0.0,
            primary_bone_axis="Y", secondary_bone_axis="X",
            apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS")
        rig.animation_data.action = None
    with open(os.path.join(out_dir, "DT_SaudMocap.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Name", "File", "Seconds", "Frames", "bLoop", "SpeedCmS", "Take", "What", "Source"])
        for clip, r, c, speed, _m, _d in rows:
            w.writerow([c["name"], c["name"] + ".fbx", "%.3f" % c["seconds"], c["frames"], "true",
                        "%.1f" % (speed * 100.0), clip["take"], clip["what"], CREDIT])
    print("%6.1fs  exported %d clips + DT_SaudMocap.csv to %s" % (time.time() - t0, len(made), os.path.relpath(out_dir, PROJECT)))
    if sheet:
        import build_motion as BM
        BM.contact_sheet(rig, made, out_dir, "saud-mocap.png")
    # every file read back and every bone of every frame measured against
    # the rig (build_motion's own read-back; it empties the scene, so last)
    import build_motion as BM
    for c, _a, _f in made:
        c["folder"] = ""
    BM.readback(made, out_dir)
    return made, rows


BITES = [
    # (name, sabotage, clip, what the failure must say)
    ("no hold", "skate", "Walk", "skates"),
    ("no floor", "floor", "Walk", "over the floor"),
    ("arms mirrored", "mirror", "Walk", "points"),
    ("no crossfade", "seam", "Run", "hitches"),
    ("off the strike", "phase", "Walk", "left foot strikes"),
]


def bite():
    """Each rule broken once, on the clip it would show on, through the
    whole build -- and the file check: a changed source is refused."""
    import motion_ik as M
    rig = M.make_rig()
    au = M.Author(rig)
    leg = rig.data.bones["thigh_l"].length + rig.data.bones["calf_l"].length
    caught = 0
    def run(clip):
        r = summary(clip, leg)
        recs, speed, frames, targets, drop, body = build_clip(au, clip, r)
        return verify(clip, recs, speed, r, targets, body)[0] + strike_check(clip, r, len(recs), left_strike(r, len(recs)))
    clean = [f for c in CLIPS for f in run(c)]
    if clean:
        print("the unbroken clips fail, so no sabotage can be counted: %s" % clean[0])
        return False
    for name, sab, which, says in BITES:
        SABOTAGE.clear(); SABOTAGE.add(sab)
        clip = next(c for c in CLIPS if c["name"] == which)
        try:
            fails = run(clip)
        finally:
            SABOTAGE.clear()
        hit = [f for f in fails if says in f]
        caught += bool(hit)
        print("  %-14s %s" % (name, ("caught: " + hit[0]) if hit else "NOT caught (%s)" % (fails[:1] or "nothing")))
    # a cycle that does not close: the source check, which needs no Blender
    SABOTAGE.add("cycle")
    try:
        fails = [f for f in check_source()[0] if "no cycle closes" in f]
    finally:
        SABOTAGE.clear()
    caught += bool(fails)
    print("  %-14s %s" % ("short cycle", ("caught: " + fails[0]) if fails else "NOT caught"))
    bad = dict(CLIPS[0], sha="0" * 64)
    try:
        fetch(bad)
        print("  %-14s NOT caught" % "changed file")
    except AssertionError as e:
        caught += 1
        print("  %-14s caught: %s" % ("changed file", str(e).split(" (")[0]))
    total = len(BITES) + 2
    print("%d of %d sabotages caught" % (caught, total))
    return caught == total


def main():
    sys.path.insert(0, HERE)
    if "--bite" in sys.argv:
        sys.exit(0 if bite() else 1)
    if "--check" in sys.argv or "--describe" in sys.argv:
        fails, rows = check_source()
        for clip, r in rows:
            print("  %-10s CMU %s (%s): cycle %.2f s from frame %d, seam %.3f, %.2f m/s on a 0.93 m leg, "
                  "%d + %d steps" % (clip["name"], clip["take"], clip["what"], r["seconds"], r["start"], r["seam"],
                                     r["speed"], _runs(r["down"]["l"]), _runs(r["down"]["r"])))
        for f in fails:
            print("MISS " + f)
        sys.exit(1 if fails else 0)
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else OUT_DIR
    build(out, sheet="--sheet" in sys.argv)


if __name__ == "__main__":
    main()
