#!/usr/bin/env python3
"""JAZIRAT AL-QIRUD -- the monkey island: the monkeys and the gorilla.

Asked 2026-10-02 ("build 3d map island level with monkeys as enemy and big
gorilla as map boss ... full 4k ... full ik"), settled as a new Unreal-only
level, its own waves of monkeys and the gorilla. This builds the two
creatures: a rigged mesh each, on the UE mannequin's bone names, with 4K
fur maps.

    python3 build_primates.py --check     the tables' own checks (no bpy)
    python3 build_primates.py --build     build, check, export, render (bpy)
    python3 build_primates.py --bite      each rule broken once (bpy)
    python3 build_primates.py --fast      1K maps, for a look

THE SKELETON is the mannequin's names wherever a primate has the part --
root, pelvis, spine_01-03, neck_01, head, and per side clavicle, upperarm,
lowerarm, hand, hand_end, thigh, calf, foot, ball -- and its seven IK bones,
so the runtime IK (SaudMotionAnimInstance: thigh/calf/foot/ball, upperarm/
lowerarm/hand, hand_end for a fist's knuckles, pelvis, neck_01, head) and
the clip lookup work on them unchanged. The monkey adds a tail, tail_01 to
tail_05. No fingers: a primate's hand here is a mitt with a thumb, and a
closed fist never opens in this game. Each creature is its own skeleton in
the engine (Monkey_Rig, Gorilla_Rig): they share names with the men, not
lengths.

THE CREATURES (Unreal-only; the browser has no island):
- the monkey, a big jungle macaque reared up to fight: 1.1 m, hunched,
  arms that reach its knees, short bowed legs, a 0.7 m tail; olive-brown,
  paler on the belly, a pink-brown bare face.
- the gorilla, the island's boss: a silverback 2.05 m reared to his full
  height, 1.45 times as wide across the arms as he is tall, shoulders
  0.72 m across, a sagittal crest; black, the silver saddle across his
  back, a bare black face and chest.

HOW. Each body is ellipsoids and capsules over its joints, unioned by a
voxel remesh, smoothed and reduced to its budget, unwrapped, and weighted to
its bones by bone heat (anything heat leaves bare takes the nearest bone).
Its fur is painted per texel in numpy: Cycles bakes where every texel of
the 4K atlas sits on the body (object position and normal), the fur's
colour, roughness and a height -- strands combed down and back, gathered in
clumps -- are worked out there, and Cycles bakes the height through a bump
into the tangent-space normal map, which is then written the way Unreal
reads it (DirectX, green down). Material "<Name>_Fur", maps
Content/Textures/<Name>/T_<Name>_Fur_{BaseColor,Normal,Roughness}.png;
model Content/Models/<Name>.fbx (the men's FBX convention); the animator's
file Tools/blender/rigs/<Name>.blend.

CHECKED (--bite breaks each): every bone the IK and the clips need, in the
mannequin's hierarchy, and the tail on the monkey; the creature's height,
feet on the floor, arms reaching the knee; one piece of mesh under its
budget; every vertex weighted, four influences at most, and an arm raised
moves nothing of the other leg; the maps 4K, the atlas covered, no hole
inside a chart, the fur at its colours and over the character floor, the
normal map not flat and facing out; the FBX read back, bone for bone.

NOT VERIFIED: no engine has imported either creature. The fur is a
texture on a solid body; no fur cards or shells are built.
"""

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MODELS = os.path.join(ROOT, "Content", "Models")
TEXTURES = os.path.join(ROOT, "Content", "Textures")
RIGS = os.path.join(HERE, "rigs")
RENDER = os.path.join(ROOT, "Docs", "renders", "island-primates.png")
SABOTAGE = set()

# the mannequin's hierarchy for the bones a primate has (child: parent)
PARENT = {"pelvis": "root", "spine_01": "pelvis", "spine_02": "spine_01", "spine_03": "spine_02",
          "neck_01": "spine_03", "head": "neck_01"}
for _s in ("l", "r"):
    PARENT.update({"clavicle_" + _s: "spine_03", "upperarm_" + _s: "clavicle_" + _s, "lowerarm_" + _s: "upperarm_" + _s,
                   "hand_" + _s: "lowerarm_" + _s, "hand_end_" + _s: "hand_" + _s,
                   "thigh_" + _s: "pelvis", "calf_" + _s: "thigh_" + _s, "foot_" + _s: "calf_" + _s, "ball_" + _s: "foot_" + _s})
IK = [("ik_foot_root", "root", None), ("ik_foot_l", "ik_foot_root", "foot_l"), ("ik_foot_r", "ik_foot_root", "foot_r"),
      ("ik_hand_root", "root", None), ("ik_hand_gun", "ik_hand_root", "hand_r"), ("ik_hand_l", "ik_hand_gun", "hand_l"),
      ("ik_hand_r", "ik_hand_gun", "hand_r")]
TAIL = ["tail_01", "tail_02", "tail_03", "tail_04", "tail_05"]

# Joints, metres, Z up, facing -Y, the left side +X (mirrored to the right).
# The arms hang forward of the hips and down past the thigh; the legs bowed.
CREATURES = {
    "Monkey": dict(
        height=1.10, budget=24000, voxel=0.007, tex=4096,
        joints=dict(pelvis=(0, 0, 0.56), spine_01=(0, -0.005, 0.62), spine_02=(0, -0.025, 0.72), spine_03=(0, -0.05, 0.81),
                    neck_01=(0, -0.08, 0.89), head=(0, -0.10, 0.96),
                    clavicle=(0.03, -0.06, 0.86), upperarm=(0.15, -0.04, 0.86), lowerarm=(0.34, -0.02, 0.67),
                    hand=(0.51, -0.05, 0.50), hand_end=(0.60, -0.06, 0.41),
                    thigh=(0.08, 0, 0.53), calf=(0.095, -0.045, 0.30), foot=(0.09, 0.0, 0.065), ball=(0.09, -0.09, 0.02),
                    tail_01=(0, 0.08, 0.55), tail_02=(0, 0.20, 0.50), tail_03=(0, 0.33, 0.48), tail_04=(0, 0.45, 0.52),
                    tail_05=(0, 0.56, 0.60), tail_end=(0, 0.64, 0.70)),
        shapes=[("E", (0, 0, 0.60), (0.12, 0.10, 0.10)), ("E", (0, 0.0, 0.535), (0.12, 0.085, 0.06)),
                ("E", (0, -0.025, 0.71), (0.13, 0.11, 0.15)),
                ("E", (0, -0.06, 0.81), (0.14, 0.10, 0.08)), ("E2", (0.11, -0.05, 0.85), (0.07, 0.065, 0.055)),
                ("E", (0, 0.0, 0.82), (0.10, 0.07, 0.07)),
                ("C", "neck_01", "head", 0.05, 0.05),
                ("E", (0, -0.09, 1.01), (0.07, 0.075, 0.08)), ("E", (0, -0.17, 0.975), (0.045, 0.055, 0.042)),
                ("E", (0, -0.155, 1.035), (0.06, 0.02, 0.016)), ("E2", (0.07, -0.08, 1.02), (0.012, 0.02, 0.025)),
                ("E2", (0.05, -0.12, 0.985), (0.03, 0.03, 0.035)),
                ("C2", "upperarm", "lowerarm", 0.054, 0.040), ("C2", "lowerarm", "hand", 0.044, 0.030),
                ("H2", "hand", "hand_end", (0.030, 0.038, 0.076)),
                ("C2", "thigh", "calf", 0.070, 0.045), ("C2", "calf", "foot", 0.040, 0.027),
                ("F2", "foot", "ball", (0.032, 0.07, 0.024)), ("E2", (0.05, 0.05, 0.55), (0.065, 0.055, 0.065)),
                ("T", TAIL + ["tail_end"], 0.028, 0.012)],
        colours=dict(fur="#6a5a40", belly="#9a8a68", dark="#4a3e2c", skin="#8a6e66", iris="#7a5418", pupil="#0a0806"),
        regions=[("skin", (0, -0.155, 0.995), (0.058, 0.05, 0.062)), ("belly", (0, -0.12, 0.69), (0.10, 0.06, 0.15)),
                 ("dark", (0, 0.50, 0.58), (0.06, 0.20, 0.16))],
        eyes=((0.026, -0.158, 1.015), 0.011),
        fur=dict(strand=0.0012, clump=0.006, amp=0.0016, clamp=0.003)),
    "Gorilla": dict(
        height=2.05, budget=36000, voxel=0.011, tex=4096,
        joints=dict(pelvis=(0, 0, 0.84), spine_01=(0, -0.01, 0.96), spine_02=(0, -0.05, 1.18), spine_03=(0, -0.09, 1.42),
                    neck_01=(0, -0.14, 1.62), head=(0, -0.18, 1.72),
                    clavicle=(0.07, -0.11, 1.58), upperarm=(0.38, -0.07, 1.58), lowerarm=(0.70, -0.05, 1.21),
                    hand=(1.00, -0.09, 0.86), hand_end=(1.12, -0.12, 0.72),
                    thigh=(0.19, 0, 0.82), calf=(0.22, -0.07, 0.46), foot=(0.22, 0.0, 0.11), ball=(0.22, -0.18, 0.03)),
        shapes=[("E", (0, -0.03, 0.92), (0.30, 0.25, 0.24)), ("E", (0, -0.05, 1.15), (0.33, 0.27, 0.28)),
                ("C", "pelvis", "spine_03", 0.29, 0.31),
                ("E", (0, -0.12, 1.40), (0.36, 0.24, 0.24)), ("E", (0, 0.04, 1.42), (0.30, 0.20, 0.26)),
                ("E2", (0.25, -0.06, 1.58), (0.22, 0.19, 0.15)),
                ("C", "neck_01", "head", 0.15, 0.13),
                ("E", (0, -0.19, 1.80), (0.15, 0.16, 0.17)), ("E", (0, -0.33, 1.74), (0.12, 0.08, 0.09)),
                ("E", (0, -0.31, 1.86), (0.14, 0.05, 0.04)), ("E", (0, -0.12, 1.94), (0.04, 0.13, 0.08)),
                ("E2", (0.14, -0.17, 1.82), (0.02, 0.03, 0.035)),
                ("E2", (0.38, -0.07, 1.56), (0.17, 0.16, 0.17)),
                ("C2", "upperarm", "lowerarm", 0.16, 0.12), ("C2", "lowerarm", "hand", 0.14, 0.09),
                ("H2", "hand", "hand_end", (0.09, 0.11, 0.13)),
                ("C2", "thigh", "calf", 0.17, 0.13), ("C2", "calf", "foot", 0.12, 0.08),
                ("F2", "foot", "ball", (0.09, 0.17, 0.055)), ("E2", (0.13, 0.10, 0.86), (0.16, 0.14, 0.15))],
        colours=dict(fur="#1e1c1c", belly="#2e2b2a", dark="#141212", skin="#2a2624", saddle="#8a8884", iris="#3a2210", pupil="#060404"),
        regions=[("skin", (0, -0.33, 1.79), (0.12, 0.09, 0.13)), ("belly", (0, -0.30, 1.38), (0.22, 0.06, 0.16)),
                 ("saddle", (0, 0.20, 1.10), (0.32, 0.16, 0.26))],
        eyes=((0.055, -0.325, 1.83), 0.015),
        fur=dict(strand=0.0016, clump=0.009, amp=0.0022, clamp=0.004)),
}
CHAR_FLOOR = 0.025          # the darkest albedo a creature's fur may bake to (the men's kit floor is 0.03)
# arms that would reach the knee standing: shoulder to hand's end at least
# the shoulder's height over the knee (the rest pose is an A-pose, so this is
# a length, not where the hand hangs)
REACH = 0.95


def joints(name, scale=1.0):
    """{bone: (x, y, z)} with the sides mirrored."""
    J = {}
    for k, p in CREATURES[name]["joints"].items():
        p = tuple(c * scale for c in p)
        if k in ("clavicle", "upperarm", "lowerarm", "hand", "hand_end", "thigh", "calf", "foot", "ball"):
            J[k + "_l"] = p
            J[k + "_r"] = (-p[0], p[1], p[2])
        else:
            J[k] = p
    return J


def bone_list(name):
    """(bone, parent) for every deforming bone, in a creation order."""
    out = [(b, p) for b, p in PARENT.items()]
    if name == "Monkey":
        prev = "pelvis"
        for t in TAIL:
            out.append((t, prev))
            prev = t
    return out


def arm_reach(J):
    """Shoulder to hand's end, over the shoulder's height above the knee."""
    def d(a, b):
        return math.dist(J[a], J[b])
    L = d("upperarm_l", "lowerarm_l") + d("lowerarm_l", "hand_l") + d("hand_l", "hand_end_l")
    return L / max(1e-6, J["upperarm_l"][2] - J["calf_l"][2])


def table_check():
    """What the tables must hold before anything is built."""
    miss = []
    for name, C in CREATURES.items():
        J = joints(name)
        for b, p in bone_list(name):
            if b not in J:
                miss.append("%s has no joint for %s" % (name, b))
        if arm_reach(J) < REACH:
            miss.append("%s's arms are %.2f of the shoulder's height over the knee, want %.2f" % (name, arm_reach(J), REACH))
        if J["ball_l"][1] >= J["foot_l"][1]:
            miss.append("%s's feet point backwards" % name)
    return miss


# ======================================================================= noise (numpy)

def _hash3(ix, iy, iz):
    h = (ix.astype(np.int64) * 73856093) ^ (iy.astype(np.int64) * 19349663) ^ (iz.astype(np.int64) * 83492791)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h ^ (h >> 16)) & 0xFFFFFF).astype(np.float32) / float(0xFFFFFF)


def vnoise3(P):
    """Value noise in 3D, 0..1, at points P (N, 3)."""
    i = np.floor(P)
    f = (P - i).astype(np.float32)
    u = f * f * (3 - 2 * f)
    i = i.astype(np.int64)
    out = np.zeros(len(P), np.float32)
    for dx in (0, 1):
        wx = u[:, 0] if dx else 1 - u[:, 0]
        for dy in (0, 1):
            wy = u[:, 1] if dy else 1 - u[:, 1]
            for dz in (0, 1):
                wz = u[:, 2] if dz else 1 - u[:, 2]
                out += wx * wy * wz * _hash3(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz)
    return out


def aniso(P, F, along_m, across_m):
    """Noise long along the unit directions F and fine across them."""
    d = (P * F).sum(1, keepdims=True)
    across = (P - d * F) / across_m
    return vnoise3(across + d * F / along_m)


def _srgb_lin(h):
    h = h.lstrip("#")
    c = np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _ell(P, c, r):
    """0 at the ellipsoid's centre, 1 on its surface."""
    return np.sqrt((((P - np.array(c, np.float32)) / np.array(r, np.float32)) ** 2).sum(1))


def _smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def paint(name, P, N):
    """Per texel, from where it sits on the body (P, N object space): the
    linear colour (n, 3), roughness (n,) and height in metres (n,)."""
    C = CREATURES[name]
    col = {k: _srgb_lin(v) for k, v in C["colours"].items()}
    fp = C["fur"]
    # the comb: down and back, laid into the surface
    comb = np.array([0.0, 0.35, -1.0], np.float32)
    comb /= np.linalg.norm(comb)
    F = comb[None, :] - (N * comb[None, :]).sum(1, keepdims=True) * N
    Fl = np.linalg.norm(F, axis=1, keepdims=True)
    side = np.cross(N, np.array([0, 0, 1.0], np.float32)[None, :])
    F = np.where(Fl > 0.15, F / np.maximum(Fl, 1e-6), side / np.maximum(np.linalg.norm(side, axis=1, keepdims=True), 1e-6))
    strand = aniso(P, F, fp["strand"] * 14, fp["strand"])
    clump = aniso(P + 3.1, F, fp["clump"] * 5, fp["clump"])
    lowf = vnoise3(P / 0.08 + 7.0)
    h = fp["amp"] * (strand - 0.5) + fp["clamp"] * (clump - 0.5)
    if "flat_fur" in SABOTAGE:
        h = h * 0.0
    c = np.repeat(col["fur"][None, :], len(P), 0)
    c = c * (0.80 + 0.40 * lowf)[:, None]
    c = c + (col["dark"] - c) * (np.clip(0.5 - clump, 0, 0.5) * 1.2)[:, None]     # the gaps between clumps
    c = c * (0.85 + 0.30 * strand)[:, None]
    skin = np.zeros(len(P), np.float32)
    for kind, cen, rad in C["regions"]:
        m = 1 - _smooth(0.75, 1.0, _ell(P, cen, rad))
        if kind == "saddle":
            m = m * _smooth(-0.1, 0.4, N[:, 1])                       # only on the back
        if kind == "skin":
            skin = np.maximum(skin, m)
        c = c + (col[kind] * (0.9 + 0.2 * lowf)[:, None] - c) * m[:, None]
    # skin: no strands, a fine pore
    pore = vnoise3(P / 0.0007)
    h = h * (1 - skin) + skin * (pore - 0.5) * 0.0003
    # the eyes: an iris and its pupil, glossy
    (ex, ey, ez), er = C["eyes"]
    eye = np.zeros(len(P), np.float32)
    for sx in (1, -1):
        d = _ell(P, (sx * ex, ey, ez), (er, er, er))
        e = 1 - _smooth(0.85, 1.0, d)
        pu = 1 - _smooth(0.40, 0.55, d)
        c = c + (col["iris"] - c) * e[:, None]
        c = c + (col["pupil"] - c) * pu[:, None]
        eye = np.maximum(eye, e)
    h = h * (1 - eye)
    rough = 0.82 - 0.10 * (strand - 0.5) - 0.25 * skin * 0.5 - 0.70 * eye
    # the character floor, soft: each tone lifted by floor x exp(-y / floor),
    # so nothing is under the floor and the darkest fur keeps its strands (a
    # hard clamp put the gorilla's whole coat on one tone); its hue kept
    y = 0.2126 * c[:, 0] + 0.7152 * c[:, 1] + 0.0722 * c[:, 2]
    if "under_floor" not in SABOTAGE:
        y2 = y + CHAR_FLOOR * np.exp(-y / CHAR_FLOOR)
        c = c * (y2 / np.maximum(y, 1e-6))[:, None]
    else:
        c = c * 0.2
    return np.clip(c, 0, 1), np.clip(rough, 0.05, 1), h.astype(np.float32)


def dilate(img, mask, steps=12):
    """Push each chart's edge texels out into the gutter, steps times."""
    img = img.copy()
    m = mask.copy()
    for _ in range(steps):
        acc = np.zeros_like(img, dtype=np.float32)
        cnt = np.zeros(m.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sm = np.roll(m, (dy, dx), (0, 1))
            si = np.roll(img, (dy, dx), (0, 1))
            acc += si * (sm[..., None] if img.ndim == 3 else sm)
            cnt += sm
        new = (~m) & (cnt > 0)
        if img.ndim == 3:
            img[new] = acc[new] / cnt[new][:, None]
        else:
            img[new] = acc[new] / cnt[new]
        m = m | new
    return img


# ======================================================================= Blender

class Primate:
    def __init__(self, name, tex=None):
        import bpy
        self.bpy = bpy
        self.name = name
        self.C = CREATURES[name]
        self.tex = tex or self.C["tex"]
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        sc.unit_settings.system = "METRIC"
        sc.unit_settings.length_unit = "METERS"
        self.J = joints(name)
        self.out_tex = os.path.join(TEXTURES, name)

    # ---------------------------------------------------------------- skeleton
    def armature(self):
        bpy = self.bpy
        from mathutils import Vector
        data = bpy.data.armatures.new(self.name + "Skeleton")
        arm = bpy.data.objects.new(self.name + "_Rig", data)
        bpy.context.scene.collection.objects.link(arm)
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode="EDIT")
        J = {k: Vector(v) for k, v in self.J.items()}
        made = {}
        root = data.edit_bones.new("root")
        root.head, root.tail = Vector((0, 0, 0)), Vector((0, 0, 0.06))
        root.use_deform = False
        made["root"] = root
        bones = bone_list(self.name)
        if "missing_bone" in SABOTAGE:
            bones = [(b, p) for b, p in bones if b != "calf_l"]
        children = {}
        for b, p in bones:
            children.setdefault(p, []).append(b)
        for b, p in bones:
            eb = data.edit_bones.new(b)
            eb.head = J[b]
            kids = [k for k in children.get(b, []) if k.startswith("tail") == b.startswith("tail")]
            if b == "pelvis":
                tail = J["spine_01"]
            elif b == "tail_05":
                tail = J["tail_end"]
            elif kids:
                tail = J[kids[0]]
            elif b.startswith("hand_end"):
                tail = J[b] + (J[b] - J[b.replace("hand_end", "hand")]).normalized() * 0.04
            elif b.startswith("ball"):
                tail = J[b] + Vector((0, -0.04, 0))
            elif b == "head":
                tail = J[b] + Vector((0, 0, 0.12 * self.C["height"] / 1.8))
            else:
                tail = J[b] + Vector((0, 0, 0.05))
            if (tail - eb.head).length < 1e-4:
                tail = eb.head + Vector((0, 0, 0.05))
            eb.tail = tail
            made[b] = eb
        for b, p in bones:
            par = p
            while par not in made:
                par = PARENT.get(par, "root")
            made[b].parent = made[par]
            made[b].use_connect = False
        for name_, parent, like in IK:
            eb = data.edit_bones.new(name_)
            if like and like in made:
                eb.head, eb.tail = made[like].head.copy(), made[like].tail.copy()
            else:
                eb.head, eb.tail = Vector((0, 0, 0)), Vector((0, 0, 0.06))
            eb.use_deform = False
            eb.parent = made[parent]
            made[name_] = eb
        for s in ("l", "r"):
            for b in ("thigh", "calf"):
                if b + "_" + s in made:
                    made[b + "_" + s].align_roll(Vector((0, -1, 0)))
            for b in ("upperarm", "lowerarm"):
                made[b + "_" + s].align_roll(Vector((0, 1, 0)))
        bpy.ops.object.mode_set(mode="OBJECT")
        self.arm = arm
        return arm

    # ---------------------------------------------------------------- body
    def _ellipsoid(self, c, r, rot=None):
        bpy = self.bpy
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0, location=c)
        o = bpy.context.object
        o.scale = r
        if rot is not None:
            o.rotation_mode = "QUATERNION"
            o.rotation_quaternion = rot
        return o

    def _capsule(self, a, b, r1, r2):
        bpy = self.bpy
        from mathutils import Vector
        a, b = Vector(a), Vector(b)
        d = b - a
        bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=r1, radius2=r2, depth=d.length, location=(a + b) / 2)
        o = bpy.context.object
        o.rotation_mode = "QUATERNION"
        o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
        return [o, self._ellipsoid(a, (r1, r1, r1)), self._ellipsoid(b, (r2, r2, r2))]

    def body(self):
        bpy = self.bpy
        from mathutils import Vector
        J = self.J
        parts = []
        for sh in self.C["shapes"]:
            k = sh[0]
            both = k.endswith("2")
            for sx in ((1, -1) if both else (1,)):
                def m(p):
                    return (p[0] * sx, p[1], p[2])

                def j(name):
                    return J[name + ("_l" if sx > 0 else "_r")] if both else J[name]
                if k[0] == "E":
                    parts.append(self._ellipsoid(m(sh[1]), sh[2]))
                elif k[0] == "C":
                    parts += self._capsule(j(sh[1]), j(sh[2]), sh[3], sh[4])
                elif k[0] in "HF":
                    a, b = Vector(j(sh[1])), Vector(j(sh[2]))
                    mid = (a + b) / 2 if k[0] == "H" else a + (b - a) * 0.5 + Vector((0, 0, -0.01))
                    rot = Vector((0, 0, 1)).rotation_difference((b - a).normalized()) if k[0] == "H" else None
                    rr = sh[3]
                    parts.append(self._ellipsoid(mid, rr, rot))
                elif k == "T":
                    names, r0, r1 = sh[1], sh[2], sh[3]
                    for i in range(len(names) - 1):
                        t0, t1 = i / (len(names) - 1), (i + 1) / (len(names) - 1)
                        parts += self._capsule(J[names[i]], J[names[i + 1]], r0 + (r1 - r0) * t0, r0 + (r1 - r0) * t1)
        bpy.ops.object.select_all(action="DESELECT")
        for o in parts:
            o.select_set(True)
        bpy.context.view_layer.objects.active = parts[0]
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        bpy.ops.object.join()
        body = bpy.context.object
        body.name = self.name
        rm = body.modifiers.new("remesh", "REMESH")
        rm.mode = "VOXEL"
        rm.voxel_size = self.C["voxel"]
        sm = body.modifiers.new("smooth", "SMOOTH")
        sm.factor = 0.8
        sm.iterations = 12
        for md in list(body.modifiers):
            bpy.ops.object.modifier_apply(modifier=md.name)
        # feet on the floor: the lowest point at z 0
        zmin = min(v.co.z for v in body.data.vertices)
        for v in body.data.vertices:
            v.co.z -= zmin
            if "short" in SABOTAGE:
                v.co.z *= 0.85
        tris = sum(len(p.vertices) - 2 for p in body.data.polygons)
        dec = body.modifiers.new("dec", "DECIMATE")
        dec.ratio = min(1.0, self.C["budget"] * 0.97 / max(tris, 1))
        bpy.ops.object.modifier_apply(modifier="dec")
        bpy.ops.object.shade_smooth()
        self.obj = body
        return body

    def unwrap(self):
        bpy = self.bpy
        bpy.context.view_layer.objects.active = self.obj
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(55), island_margin=0.004, scale_to_bounds=True)
        bpy.ops.object.mode_set(mode="OBJECT")

    def weight(self):
        bpy = self.bpy
        bpy.ops.object.select_all(action="DESELECT")
        self.obj.select_set(True)
        self.arm.select_set(True)
        bpy.context.view_layer.objects.active = self.arm
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
        o = self.obj
        deform = [b.name for b in self.arm.data.bones if b.use_deform]
        for b in deform:
            if b not in o.vertex_groups:
                o.vertex_groups.new(name=b)
        # anything heat left bare takes the nearest bone (to its segment)
        from mathutils import Vector
        segs = {b.name: (self.arm.matrix_world @ b.head_local, self.arm.matrix_world @ b.tail_local)
                for b in self.arm.data.bones if b.use_deform}
        bare = 0
        for v in o.data.vertices:
            if sum(g.weight for g in v.groups) < 1e-3:
                best, bd = None, 1e9
                for n, (a, b) in segs.items():
                    ab = b - a
                    t = max(0.0, min(1.0, (v.co - a).dot(ab) / max(ab.length_squared, 1e-12)))
                    d = (v.co - (a + ab * t)).length
                    if d < bd:
                        best, bd = n, d
                o.vertex_groups[best].add([v.index], 1.0, "REPLACE")
                bare += 1
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.vertex_group_limit_total(group_select_mode="ALL", limit=4)
        bpy.ops.object.vertex_group_normalize_all(group_select_mode="ALL", lock_active=False)
        if "unweighted" in SABOTAGE:
            for g in o.vertex_groups:
                g.remove(list(range(0, 60)))
        if "leak" in SABOTAGE:
            right_leg = [v.index for v in o.data.vertices if v.co.x < -0.05 and v.co.z < self.J["calf_r"][2]]
            o.vertex_groups["upperarm_l"].add(right_leg[:40], 0.5, "REPLACE")
        self.bare = bare

    # ---------------------------------------------------------------- textures
    def _bake_emit(self, socket, name):
        """Bake one Texture Coordinate output (Object position or Normal) to
        a float image, every texel's value in object space, alpha 1 where a
        chart is."""
        bpy = self.bpy
        n = self.tex
        img = bpy.data.images.new(name, n, n, alpha=True, float_buffer=True)
        img.colorspace_settings.name = "Non-Color"
        mat = bpy.data.materials.new(name + "_mat")
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        tc = nt.nodes.new("ShaderNodeTexCoord")
        em = nt.nodes.new("ShaderNodeEmission")
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(tc.outputs[socket], em.inputs["Color"])
        nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        nt.nodes.active = node
        self.obj.data.materials.clear()
        self.obj.data.materials.append(mat)
        sc = bpy.context.scene
        sc.render.engine = "CYCLES"
        sc.cycles.samples = 1
        sc.cycles.device = "CPU"
        bpy.ops.object.select_all(action="DESELECT")
        self.obj.select_set(True)
        bpy.context.view_layer.objects.active = self.obj
        bpy.ops.object.bake(type="EMIT", margin=0, use_clear=True)
        a = np.empty(n * n * 4, np.float32)
        img.pixels.foreach_get(a)
        return a.reshape(n, n, 4)

    def textures(self):
        """Paint the fur per texel and bake its normal; write the three maps."""
        bpy = self.bpy
        from PIL import Image
        n = self.tex
        pos = self._bake_emit("Object", "pos")
        nrm = self._bake_emit("Normal", "nrm")
        mask = pos[..., 3] > 0.5
        P = pos[..., :3][mask]
        Nn = nrm[..., :3][mask]
        Nn = Nn / np.maximum(np.linalg.norm(Nn, axis=1, keepdims=True), 1e-6)
        colour = np.zeros((n, n, 3), np.float32)
        rough = np.zeros((n, n), np.float32)
        height = np.zeros((n, n), np.float32)
        idx = np.nonzero(mask.ravel())[0]
        step = 2_000_000
        for k in range(0, len(idx), step):
            c, r, h = paint(self.name, P[k:k + step], Nn[k:k + step])
            sl = idx[k:k + step]
            colour.reshape(-1, 3)[sl] = c
            rough.reshape(-1)[sl] = r
            height.reshape(-1)[sl] = h
        if "holes" not in SABOTAGE:
            colour = dilate(colour, mask, 16)
            rough = dilate(rough, mask, 16)
            height = dilate(height, mask, 16)
        else:
            ys, xs = np.nonzero(mask)
            cy, cx = ys[len(ys) // 2], xs[len(xs) // 2]
            colour[max(0, cy - 20):cy + 20, max(0, cx - 20):cx + 20] = 0
        # the normal: the height through a bump, baked in tangent space
        himg = bpy.data.images.new("height", n, n, alpha=False, float_buffer=True)
        himg.colorspace_settings.name = "Non-Color"
        hp = np.zeros((n, n, 4), np.float32)
        hp[..., 0] = hp[..., 1] = hp[..., 2] = height
        hp[..., 3] = 1
        himg.pixels.foreach_set(hp.ravel())
        nimg = bpy.data.images.new("normal", n, n, alpha=False, float_buffer=True)
        nimg.colorspace_settings.name = "Non-Color"
        mat = bpy.data.materials.new("bumpbake")
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes["Principled BSDF"]
        ht = nt.nodes.new("ShaderNodeTexImage")
        ht.image = himg
        ht.interpolation = "Linear"
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 1.0
        bump.inputs["Distance"].default_value = 1.0
        nt.links.new(ht.outputs["Color"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        tgt = nt.nodes.new("ShaderNodeTexImage")
        tgt.image = nimg
        nt.nodes.active = tgt
        self.obj.data.materials.clear()
        self.obj.data.materials.append(mat)
        bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", margin=16, use_clear=True)
        nb = np.empty(n * n * 4, np.float32)
        nimg.pixels.foreach_get(nb)
        nb = nb.reshape(n, n, 4)[..., :3]
        nb[..., 1] = 1.0 - nb[..., 1]                 # OpenGL (Blender) to DirectX (Unreal): green down
        os.makedirs(self.out_tex, exist_ok=True)

        def srgb(c):
            return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.maximum(c, 1e-9), 1 / 2.4) - 0.055)
        maps = dict(BaseColor=np.clip(np.round(srgb(colour) * 255), 0, 255).astype(np.uint8),
                    Normal=np.clip(np.round(nb * 255), 0, 255).astype(np.uint8),
                    Roughness=np.clip(np.round(rough * 255), 0, 255).astype(np.uint8))
        self.paths = {}
        for role, a in maps.items():
            p = os.path.join(self.out_tex, "T_%s_Fur_%s.png" % (self.name, role))
            Image.fromarray(np.flipud(a)).save(p, optimize=True)
            self.paths[role] = p
        self.maps = maps
        self.mask = np.flipud(mask)
        # the creature's own material, on its maps
        mat = bpy.data.materials.new(self.name + "_Fur")
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes["Principled BSDF"]
        for role, p in self.paths.items():
            node = nt.nodes.new("ShaderNodeTexImage")
            node.image = bpy.data.images.load(p)
            node.image.colorspace_settings.name = "sRGB" if role == "BaseColor" else "Non-Color"
            if role == "BaseColor":
                nt.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
            elif role == "Roughness":
                nt.links.new(node.outputs["Color"], bsdf.inputs["Roughness"])
            else:
                nm = nt.nodes.new("ShaderNodeNormalMap")
                nt.links.new(node.outputs["Color"], nm.inputs["Color"])
                nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
        self.obj.data.materials.clear()
        self.obj.data.materials.append(mat)

    def build(self):
        self.armature()
        self.body()
        self.unwrap()
        self.weight()
        self.textures()
        return self


# ======================================================================= checks

def check(pr):
    miss = []
    name, C = pr.name, pr.C
    arm, o = pr.arm, pr.obj
    bones = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones}
    for b, p in bone_list(name):
        if b not in bones:
            miss.append("%s has no bone %s" % (name, b))
        elif bones[b] != p:
            miss.append("%s's %s hangs from %s, not %s" % (name, b, bones[b], p))
    for b, p, _ in IK:
        if b not in bones:
            miss.append("%s has no %s" % (name, b))
    zs = [v.co.z for v in o.data.vertices]
    top, low = max(zs), min(zs)
    if not C["height"] * 0.96 <= top - low <= C["height"] * 1.04:
        miss.append("%s stands %.2f m, want %.2f" % (name, top - low, C["height"]))
    if abs(low) > 0.005:
        miss.append("%s's feet are %.3f m off the floor" % (name, low))
    tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
    if tris > C["budget"]:
        miss.append("%s is %d triangles, over its %d" % (name, tris, C["budget"]))
    # one piece
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.verts.ensure_lookup_table()
    seen, stack = set(), [bm.verts[0]]
    while stack:
        v = stack.pop()
        if v.index in seen:
            continue
        seen.add(v.index)
        stack.extend(e.other_vert(v) for e in v.link_edges if e.other_vert(v).index not in seen)
    if len(seen) < len(bm.verts):
        miss.append("%s is in pieces: %d of %d vertices joined to the first" % (name, len(seen), len(bm.verts)))
    bm.free()
    # weights
    bad = sum(1 for v in o.data.vertices if abs(sum(g.weight for g in v.groups) - 1.0) > 0.02)
    many = sum(1 for v in o.data.vertices if len([g for g in v.groups if g.weight > 1e-4]) > 4)
    if bad:
        miss.append("%s: %d vertices not weighted to one" % (name, bad))
    if many:
        miss.append("%s: %d vertices on more than four bones" % (name, many))
    # an arm raised moves nothing of the other leg
    bpy = pr.bpy
    pb = arm.pose.bones["upperarm_l"]
    pb.rotation_mode = "XYZ"
    rest = [v.co.copy() for v in o.data.vertices]
    pb.rotation_euler = (math.radians(80), 0, 0)
    bpy.context.view_layer.update()
    ev = o.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    knee = pr.J["calf_r"][2]
    moved = max(((ev.vertices[i].co - rest[i]).length for i in range(len(rest)) if rest[i].x < -0.05 and rest[i].z < knee), default=0.0)
    o.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()
    pb.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()
    if moved > 0.001:
        miss.append("%s's left arm moves the right leg %.1f mm" % (name, moved * 1000))
    # arms reach the knee
    if arm_reach(pr.J) < REACH:
        miss.append("%s's arms do not reach the knee" % name)
    # textures
    m = pr.maps
    if m["BaseColor"].shape[:2] != (pr.tex, pr.tex):
        miss.append("%s's maps are %s, want %d" % (name, m["BaseColor"].shape[:2], pr.tex))
    cover = pr.mask.mean()
    if cover < 0.45:
        miss.append("%s's atlas is %.0f %% covered, want 45" % (name, cover * 100))
    lin = np.where(m["BaseColor"] / 255.0 <= 0.04045, m["BaseColor"] / 255.0 / 12.92, ((m["BaseColor"] / 255.0 + 0.055) / 1.055) ** 2.4)
    y = 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]
    inside = y[pr.mask]
    if (inside < 0.004).mean() > 0.0005:
        miss.append("%s has holes inside its charts: %.2f %% black" % (name, (inside < 0.004).mean() * 100))
    if np.percentile(inside, 1) < CHAR_FLOOR * 0.85:
        miss.append("%s's fur goes under the character floor: %.4f" % (name, np.percentile(inside, 1)))
    want = _srgb_lin(C["colours"]["fur"])
    got = np.median(lin[pr.mask], axis=0)
    if np.abs(got - np.maximum(want, CHAR_FLOOR)).max() > 0.08:
        miss.append("%s's fur is %s, want about %s" % (name, np.round(got, 3), np.round(want, 3)))
    nn = m["Normal"].astype(np.float32)[pr.mask] / 255 * 2 - 1
    if nn[:, 2].mean() < 0.8:
        miss.append("%s's normal map faces in: mean z %.2f" % (name, nn[:, 2].mean()))
    tilt = np.sqrt(nn[:, 0] ** 2 + nn[:, 1] ** 2).mean()
    if tilt < 0.03:
        miss.append("%s's fur is flat: mean tilt %.3f, want 0.03" % (name, tilt))
    return miss


# ======================================================================= export, render

def export(pr):
    bpy = pr.bpy
    os.makedirs(MODELS, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    pr.obj.select_set(True)
    pr.arm.select_set(True)
    bpy.context.view_layer.objects.active = pr.arm
    path = os.path.join(MODELS, pr.name + ".fbx")
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_unit_scale=True, global_scale=1.0,
                             apply_scale_options="FBX_SCALE_UNITS", add_leaf_bones=False,
                             primary_bone_axis="Y", secondary_bone_axis="X", object_types={"ARMATURE", "MESH"},
                             mesh_smooth_type="FACE", bake_space_transform=False, path_mode="RELATIVE", embed_textures=False)
    want = sorted(b.name for b in pr.arm.data.bones)
    nverts = len(pr.obj.data.vertices)
    os.makedirs(RIGS, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(RIGS, pr.name + ".blend"))
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    arms = [o for o in new if o.type == "ARMATURE"]
    meshes = [o for o in new if o.type == "MESH"]
    got = sorted(b.name for b in arms[0].data.bones) if arms else []
    gv = sum(len(o.data.vertices) for o in meshes)
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    miss = []
    if got != want:
        miss.append("%s.fbx reads back with bones %s" % (pr.name, sorted(set(want) ^ set(got))))
    if gv != nverts:
        miss.append("%s.fbx reads back with %d vertices, not %d" % (pr.name, gv, nverts))
    return path, miss


def render_sheet(paths, out=RENDER):
    """Each creature from the front, three-quarter and side, and in a test
    pose (an arm up, a knee up), side by side on one sheet."""
    from PIL import Image
    tiles = []
    for name in CREATURES:
        tiles.append(Image.open(paths[name]))
    w = sum(t.size[0] for t in tiles)
    h = max(t.size[1] for t in tiles)
    sheet = Image.new("RGB", (w, h), (14, 16, 22))
    x = 0
    for t in tiles:
        sheet.paste(t, (x, 0))
        x += t.size[0]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out)
    print("drew %s" % out)


def render_one(pr, out, samples=32):
    bpy = pr.bpy
    from mathutils import Vector
    sc = bpy.context.scene
    H = pr.C["height"]
    sc.render.engine = "CYCLES"
    sc.cycles.samples = samples
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    sc.view_settings.view_transform = "Standard"
    sc.world = bpy.data.worlds.new("W")
    sc.world.use_nodes = True
    sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.30, 0.34, 0.42, 1)
    sc.world.node_tree.nodes["Background"].inputs[1].default_value = 0.5
    key = bpy.data.objects.new("Key", bpy.data.lights.new("Key", "SUN"))
    sc.collection.objects.link(key)
    key.data.energy = 3.5
    key.rotation_euler = (math.radians(55), 0, math.radians(-30))
    # four copies of the creature: front, three-quarter, side, posed
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    sc.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = H * 6.2
    cam.location = Vector((0, -10 * H, H * 0.55))
    cam.rotation_euler = (math.radians(90), 0, 0)
    sc.camera = cam
    rigs = [pr.arm]
    bodies = [pr.obj]
    for k in range(3):
        a2 = pr.arm.copy()
        a2.data = pr.arm.data
        b2 = pr.obj.copy()
        b2.data = pr.obj.data
        sc.collection.objects.link(a2)
        sc.collection.objects.link(b2)
        b2.parent = a2
        b2.modifiers[0].object = a2
        rigs.append(a2)
        bodies.append(b2)
    for i, (a, yaw) in enumerate(zip(rigs, (0, 40, 90, 20))):
        a.location = ((i - 1.5) * H * 1.5, 0, 0)
        a.rotation_euler = (0, 0, math.radians(yaw))
    posed = rigs[3]
    posed.pose.bones["upperarm_r"].rotation_mode = "XYZ"
    posed.pose.bones["upperarm_r"].rotation_euler = (math.radians(-70), 0, 0)
    posed.pose.bones["lowerarm_r"].rotation_mode = "XYZ"
    posed.pose.bones["lowerarm_r"].rotation_euler = (math.radians(-60), 0, 0)
    posed.pose.bones["thigh_l"].rotation_mode = "XYZ"
    posed.pose.bones["thigh_l"].rotation_euler = (math.radians(-60), 0, 0)
    posed.pose.bones["calf_l"].rotation_mode = "XYZ"
    posed.pose.bones["calf_l"].rotation_euler = (math.radians(70), 0, 0)
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
    # each view its own panel, close: the camera over each copy in turn
    from PIL import Image
    sc.render.resolution_x, sc.render.resolution_y = 700, 1000
    cam.data.ortho_scale = H * 1.55
    panels = []
    for i, a in enumerate(rigs):
        for j, (r2, b2) in enumerate(zip(rigs, bodies)):
            b2.hide_render = (i != j)
        cam.location = Vector((a.location.x, -10 * H, H * 0.52))
        tmp = out + ".%d.png" % i
        sc.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        panels.append(Image.open(tmp).convert("RGB"))
        os.remove(tmp)
    sheet = Image.new("RGB", (700 * len(panels), 1000))
    for i, im in enumerate(panels):
        sheet.paste(im, (700 * i, 0))
    sheet.save(out)
    return out


# ======================================================================= main

BITES = [
    ("every bone there", "missing_bone", "has no bone"),
    ("his height", "short", "stands"),
    ("every vertex weighted", "unweighted", "not weighted"),
    ("an arm moves no leg", "leak", "moves the right leg"),
    ("no holes in the fur", "holes", "holes inside"),
    ("fur not flat", "flat_fur", "fur is flat"),
    ("the floor", "under_floor", "under the character floor"),
]


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if not ({"--build", "--bite", "--fast"} & set(args)):
        f = table_check()
        print("\n".join("MISS " + m for m in f) or "primates' tables: checks pass")
        sys.exit(1 if f else 0)
    try:
        import bpy  # noqa: F401
    except ImportError:
        print("--build runs with bpy (pip install bpy)")
        sys.exit(2)
    if "--bite" in args:
        caught = 0
        for what, sab, want in BITES:
            SABOTAGE.clear()
            SABOTAGE.add(sab)
            pr = Primate("Monkey", tex=512).build()
            f = check(pr)
            hit = [x for x in f if want in x]
            caught += bool(hit)
            print("  %-22s %s  %s" % (what, "caught" if hit else "MISSED", (hit or f or ["(passed)"])[0]))
        SABOTAGE.clear()
        print("%d of %d caught" % (caught, len(BITES)))
        sys.exit(0 if caught == len(BITES) else 1)
    fast = "--fast" in args
    only = [a for a in args if a in CREATURES] or list(CREATURES)
    shots = {}
    stats = {}
    for name in only:
        pr = Primate(name, tex=1024 if fast else None).build()
        f = check(pr) + table_check()
        tris = sum(len(p.vertices) - 2 for p in pr.obj.data.polygons)
        print("  %-8s %d tris, %d bones, %d left bare by heat" % (name, tris, len(pr.arm.data.bones), pr.bare))
        if f:
            print("FAILED:\n  " + "\n  ".join(f))
            sys.exit(1)
        path, miss = export(pr)
        if miss:
            print("FAILED:\n  " + "\n  ".join(miss))
            sys.exit(1)
        stats[name] = dict(tris=tris, bones=len(pr.arm.data.bones), height=pr.C["height"], fbx=os.path.relpath(path, ROOT))
        shots[name] = render_one(pr, os.path.join(ROOT, "Docs", "renders", "%s-3d.png" % name.lower()), samples=16 if fast else 48)
    print("checks pass: the bones, his size, one piece under budget, the weights, an arm moving no leg, the fur maps; FBX read back")
    if len(shots) == len(CREATURES):
        render_sheet(shots)


if __name__ == "__main__":
    main()
