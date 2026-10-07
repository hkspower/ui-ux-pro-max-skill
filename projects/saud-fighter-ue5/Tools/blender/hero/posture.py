"""The rest pose's posture: plumb, level, straight and mirrored (2026-10-07).

Asked as "make body Posture and Body Alignment and Straightness", settled as
every man the pipeline builds (Saud, the thug, the brawler, AL-SAQR,
AL-WAHSH, ZAYOS), in the BODY MESH REST POSE -- the A-pose the engine
retargets from -- keeping each man's proportions, build and character and
holding only the faults: a spine off plumb in side view, a sideways tilt,
the shoulder or hip line not level, the mirrored joints not mirrored, the
head off the spine's line or pitched / rolled, the pelvis twisted, the feet
not parallel or not level, the A-pose arms not symmetric.

Measured first (2026-10-07, every man's Content/Models export, the FBX and
the glTF identical to 0.00 mm, and the generator's joint table through
anatomy.build_field identical to both): every man was already straight on
every rule -- the joint table is built mirrored on a vertical spine
(build_saud._LIMB) and the size field has no rotation in it -- so nothing
was changed and nothing rebuilt. These rules hold that.

A man here is a dict:
    name, h        -- his stature over Saud's (anatomy.build_field's h);
                      every length tolerance grows with it
    joints         -- name -> (x, y, z) metres, Z up, he faces -Y: the
                      generator's joint table through his field, plus the
                      export's finger bones
    eyes           -- (left, right) globe centres, from the export's eye mesh
    ears           -- {"lobe": (l, r), "centre": (l, r)}: assembly.ear's own
                      points (sculpt.EAR_*) through his field
    soles          -- {"l": V, "r": V}: the export's shoe vertices per side
No Blender in here except generator(), which reads build_saud's table.
"""
import json
import math
import os

import numpy as np

from . import sculpt as SC

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "Content", "Models"))
MEN = (("saud", "Saud"), ("thug", "Thug"), ("brawler", "Brawler"),
       ("saqr", "Saqr"), ("boss", "Boss"), ("zayos", "Zayos"))

SPINE = ("pelvis", "spine_01", "spine_02", "spine_03", "neck_01")
COLUMN = SPINE + ("head",)

# The tolerances. Lengths are metres at Saud's size and grow with h; angles
# are degrees. What each man measured on 2026-10-07 is in the comment.
TOL = dict(
    # side view: the spine's joints over the vertical through the ankles
    # (the joint chain carries no curve: 0.0 cm on every man), and the
    # plumb line's landmarks -- ear lobe, shoulder, hip, knee (Kendall's
    # line). The lobe stands 2.3 cm behind the ankles on every man (h-scaled),
    # the shoulder 0.6 in front, the knee 1.2 in front (the IK's pre-bend).
    spine=0.020, plumb=0.030,
    # front view: the column's joints, the eyes' and the lobes' midpoints
    # off the midline (0.0 mm every man)
    tilt=0.003,
    # the shoulder (clavicle, upperarm) and hip (thigh) joints' heights,
    # left against right (0.0 mm)
    level=0.003,
    # every other mirrored joint, left against right mirrored (0.0 mm)
    mirror=0.002,
    # the head: rolled (the eyes' line, 0.1 mm over 62: 0.09 deg; the head
    # bone's lean, 0.0), turned (0.0), pitched (the eye-ear line, an
    # approximation of the Frankfurt plane: the orbit's floor one globe
    # radius under the eye's centre to the ear's centre, +0.5 deg on every
    # man -- his head scales about the neck with no turn in it) and forward
    # of the chest's joint (1.4 cm, h-scaled: the neck's 5 deg)
    head_roll=1.0, head_yaw=1.0, head_pitch=6.0, head_fwd=0.025,
    # the hip line turned about the vertical (0.0 deg)
    twist=1.0,
    # the feet: ankle and ball heights (0.0 mm), the two feet's headings
    # apart and their pitch apart (0.0 deg), the soles' slope across and
    # along (0.00 deg: both halves of every sole on the floor) and lowest
    # point (0.0 mm), the shoes' long axes
    # apart (0.1-0.2)
    feet_level=0.002, feet_angle=2.0, feet_pitch=1.0, sole_slope=1.0, sole_floor=0.002,
    # the A-pose arms: each segment's heading and length, left against
    # right mirrored (0.03 deg and 0.0 mm)
    arm_angle=1.0, arm_len=0.002,
)
RULES = ("plumb", "tilt", "shoulder line", "hip line", "mirror", "head", "twist", "feet", "arms")

# Who owns which pair, so a broken joint fails ONE rule: the shoulder and
# hip lines own their joints' heights, the twist the hips' depth, the arms
# and feet their chains whole; the mirror the rest.
MIRROR_AXES = {"clavicle": (0, 1), "upperarm": (0, 1), "thigh": (0,), "calf": (0, 1, 2)}
ARM = [("upperarm", "lowerarm"), ("lowerarm", "hand")]
FINGERS = [("hand", f + "_01") for f in ("index", "middle", "ring", "pinky", "thumb")] + \
          [(f + "_0%d" % k, f + "_0%d" % (k + 1)) for f in ("index", "middle", "ring", "pinky", "thumb") for k in (1, 2)]


# ------------------------------------------------------------------ reading

_CT = {5121: np.uint8, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
_NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
_GL_TO_Z_UP = np.array([[1.0, 0, 0], [0, 0, -1.0], [0, 1.0, 0]])     # glTF Y up -> Blender Z up


def read_export(name, models=MODELS, with_faces=False):
    """The rest pose a build shipped: Content/Models/<name>.gltf (written
    with the FBX in the same call, rig_export.export_all): the skin's joints
    at bind, the eye globes, the shoes. Numpy only."""
    path = os.path.join(models, name + ".gltf")
    g = json.load(open(path))
    buf = open(os.path.join(models, g["buffers"][0]["uri"]), "rb").read()

    def acc(i):
        a = g["accessors"][i]; v = g["bufferViews"][a["bufferView"]]
        n = a["count"] * _NC[a["type"]]
        arr = np.frombuffer(buf, dtype=_CT[a["componentType"]], count=n,
                            offset=v.get("byteOffset", 0) + a.get("byteOffset", 0))
        return arr.reshape(a["count"], _NC[a["type"]])
    skin = g["skins"][0]
    ibm = acc(skin["inverseBindMatrices"]).reshape(-1, 4, 4)
    joints = {}
    for k, ji in enumerate(skin["joints"]):
        M = np.linalg.inv(ibm[k].astype(float).T)        # column-major
        joints[g["nodes"][ji]["name"]] = _GL_TO_Z_UP @ M[:3, 3]
    parts = {}
    key_of = lambda p: g["materials"][p["material"]]["name"].split("_", 1)[1]
    for p in g["meshes"][0]["primitives"]:
        V = acc(p["attributes"]["POSITION"]).astype(float) @ _GL_TO_Z_UP.T
        key = key_of(p)
        parts[key] = np.concatenate([parts[key], V]) if key in parts else V
    eye = parts["Eye"]
    eyes = (eye[eye[:, 0] > 0].mean(0), eye[eye[:, 0] < 0].mean(0))
    shoe = parts["Shoe"]
    soles = {"l": shoe[shoe[:, 0] > 0], "r": shoe[shoe[:, 0] < 0]}
    if with_faces:
        tris = [(key_of(p), acc(p["attributes"]["POSITION"]).astype(float) @ _GL_TO_Z_UP.T,
                 acc(p["indices"]).reshape(-1, 3).astype(int)) for p in g["meshes"][0]["primitives"]]
        return dict(joints=joints, eyes=eyes, soles=soles, tris=tris)
    return dict(joints=joints, eyes=eyes, soles=soles)


def ear_points():
    """assembly.ear's own points at Saud's size: the ring's centre and the
    lobe's (left; the right is the mirror)."""
    c = np.array([SC.EAR_X, SC.EAR_Y, SC.EAR_Z])
    return dict(centre=c, lobe=c + np.array([0.002, -0.003, -0.0250]))


def generator(kind):
    """The generator's own rest pose for one man: build_saud's joint table
    through his field (anatomy.build_field, what scale_to applies), and the
    ears through the same field. Reads bpy-backed modules."""
    import build_saud as L
    from . import anatomy as A, roster
    spec = roster.spec(kind)
    h, _l, _t, F = A.build_field(spec["sc"], spec["look"].get("build", 1.0))
    names = list(L.ORDER)
    Q = F(np.array([list(L.J[n][0]) for n in names]))
    joints = {n: q.copy() for n, q in zip(names, Q)}
    e = ear_points()
    pts = F(np.array([e["centre"], e["centre"] * [-1, 1, 1], e["lobe"], e["lobe"] * [-1, 1, 1]]))
    return dict(h=h, joints=joints, ears=dict(centre=(pts[0], pts[1]), lobe=(pts[2], pts[3])))


def man(kind, name, models=MODELS, agree=0.0005):
    """One man as built: the generator's table, held to the export's skin
    joints within `agree` (else the export is not the generator's and
    measuring one says nothing of the other), plus the export's fingers,
    eyes and shoes."""
    gen = generator(kind)
    ex = read_export(name, models)
    worst, at = 0.0, None
    for n, p in ex["joints"].items():
        if n in gen["joints"]:
            d = float(np.linalg.norm(gen["joints"][n] - p))
            if d > worst: worst, at = d, n
    assert worst <= agree, "export: %s's %s is %.1f mm from the generator's joint table -- rebuild him" % (name, at, worst * 1000)
    joints = dict(gen["joints"])
    for n, p in ex["joints"].items():
        joints.setdefault(n, p.copy())
    return dict(name=name, kind=kind, h=gen["h"], joints=joints, ears=gen["ears"], eyes=ex["eyes"], soles=ex["soles"],
                agree=worst)


# ---------------------------------------------------------------- measuring

def _deg(a): return math.degrees(a)


def _pair(P, base):
    return P[base + "_l"], P[base + "_r"]


def _heading(v):
    """A horizontal direction's angle, degrees."""
    return _deg(math.atan2(v[0], -v[1]))


def _sole(V):
    """Lowest point; the slope across (+ = the outer edge low) and along
    (+ = the heel low), each from the lowest point of either half of the
    shoe -- inner / outer, front / back -- to the other's (degrees); its
    long axis' heading."""
    mid = V.mean(0)
    def slope(axis):
        a, b = V[V[:, axis] > mid[axis]], V[V[:, axis] <= mid[axis]]
        pa, pb = a[np.argmin(a[:, 2])], b[np.argmin(b[:, 2])]
        return _deg(math.atan2(pb[2] - pa[2], pa[axis] - pb[axis]))
    across = slope(0) * (1 if mid[0] > 0 else -1)
    c = V[:, :2] - V[:, :2].mean(0)
    w, vv = np.linalg.eigh(c.T @ c); ax = vv[:, 1]
    if ax[1] > 0: ax = -ax
    return float(V[:, 2].min()), across, slope(1), _heading(ax)


def measure(m):
    """Every rule's numbers for one man: {rule: [(what, value, limit, unit)]}.
    A value over its limit (absolute) is a miss."""
    P, h = m["joints"], m["h"]
    cm, mm = 100.0, 1000.0
    out = {r: [] for r in RULES}
    ank = (P["foot_l"] + P["foot_r"]) / 2.0
    # plumb (side view)
    for n in SPINE:
        out["plumb"].append(("%s fwd of the ankles" % n, -(P[n][1] - ank[1]) * cm, TOL["spine"] * h * cm, "cm"))
    lobe = (m["ears"]["lobe"][0] + m["ears"]["lobe"][1]) / 2.0
    for what, p in (("ear lobe", lobe), ("shoulder", sum(_pair(P, "upperarm")) / 2), ("hip", sum(_pair(P, "thigh")) / 2),
                    ("knee", sum(_pair(P, "calf")) / 2)):
        out["plumb"].append(("%s fwd of the ankles" % what, -(p[1] - ank[1]) * cm, TOL["plumb"] * h * cm, "cm"))
    # tilt (front view)
    for n in COLUMN:
        out["tilt"].append(("%s off the midline" % n, P[n][0] * mm, TOL["tilt"] * h * mm, "mm"))
    if m.get("eyes") is not None:
        out["tilt"].append(("eyes' middle off the midline", (m["eyes"][0][0] + m["eyes"][1][0]) / 2 * mm, TOL["tilt"] * h * mm, "mm"))
    out["tilt"].append(("ear lobes' middle off the midline", lobe[0] * mm, TOL["tilt"] * h * mm, "mm"))
    # the shoulder and hip lines
    for b in ("clavicle", "upperarm"):
        l, r = _pair(P, b)
        out["shoulder line"].append(("%s left over right" % b, (l[2] - r[2]) * mm, TOL["level"] * h * mm, "mm"))
    l, r = _pair(P, "thigh")
    out["hip line"].append(("hip joint left over right", (l[2] - r[2]) * mm, TOL["level"] * h * mm, "mm"))
    # mirror
    for b, axes in MIRROR_AXES.items():
        l, r = _pair(P, b)
        d = np.array([l[0] + r[0], l[1] - r[1], l[2] - r[2]])
        worst = max(axes, key=lambda a: abs(d[a]))
        out["mirror"].append(("%s left against right (%s)" % (b, "xyz"[worst]), d[worst] * mm, TOL["mirror"] * h * mm, "mm"))
    # head
    if m.get("eyes") is not None:
        el, er = m["eyes"]; d = el - er
        out["head"].append(("rolled (the eyes' line)", _deg(math.atan2(d[2], d[0])), TOL["head_roll"], "deg"))
        out["head"].append(("turned (the eyes' line)", _deg(math.atan2(d[1], d[0])), TOL["head_yaw"], "deg"))
        eye = (el + er) / 2.0
        k = m["h"] ** 0.65                       # the head's own scale (anatomy.build_field)
        orb = eye - np.array([0, 0, SC.EYE_R * k])
        por = (m["ears"]["centre"][0] + m["ears"]["centre"][1]) / 2.0
        out["head"].append(("pitched up (eye-ear line)", _deg(math.atan2(orb[2] - por[2], por[1] - orb[1])), TOL["head_pitch"], "deg"))
    if "head_end" in P:
        v = P["head_end"] - P["head"]
        out["head"].append(("rolled (the head bone)", _deg(math.atan2(v[0], v[2])), TOL["head_roll"], "deg"))
    out["head"].append(("forward of spine_03", -(P["head"][1] - P["spine_03"][1]) * cm, TOL["head_fwd"] * h * cm, "cm"))
    # twist
    l, r = _pair(P, "thigh")
    out["twist"].append(("hip line turned", _deg(math.atan2(l[1] - r[1], l[0] - r[0])), TOL["twist"], "deg"))
    # feet
    for b in ("foot", "ball"):
        l, r = _pair(P, b)
        out["feet"].append(("%s left over right" % b, (l[2] - r[2]) * mm, TOL["feet_level"] * h * mm, "mm"))
    dl, dr = P["ball_l"] - P["foot_l"], P["ball_r"] - P["foot_r"]
    out["feet"].append(("headings apart", _heading(dl) - _heading(dr), TOL["feet_angle"], "deg"))
    pitch = lambda v: _deg(math.atan2(-v[2], math.hypot(v[0], v[1])))
    out["feet"].append(("pitch left over right", pitch(dl) - pitch(dr), TOL["feet_pitch"], "deg"))
    if m.get("soles") is not None:
        sl, sr = _sole(m["soles"]["l"]), _sole(m["soles"]["r"])
        for side, s in (("left", sl), ("right", sr)):
            out["feet"].append(("%s sole's slope across" % side, s[1], TOL["sole_slope"], "deg"))
            out["feet"].append(("%s sole's slope along" % side, s[2], TOL["sole_slope"], "deg"))
        out["feet"].append(("soles' lowest left over right", (sl[0] - sr[0]) * mm, TOL["sole_floor"] * h * mm, "mm"))
        out["feet"].append(("shoes' long axes apart", sl[3] - sr[3], TOL["feet_angle"], "deg"))
    # the A-pose arms
    for a, b in ARM + FINGERS:
        if a + "_l" not in P or b + "_l" not in P: continue
        vl = P[b + "_l"] - P[a + "_l"]; vr = (P[b + "_r"] - P[a + "_r"]) * np.array([-1, 1, 1])
        ang = _deg(math.acos(max(-1.0, min(1.0, float(vl @ vr) / (np.linalg.norm(vl) * np.linalg.norm(vr))))))
        out["arms"].append(("%s->%s left against right" % (a, b), ang, TOL["arm_angle"], "deg"))
        out["arms"].append(("%s->%s length left over right" % (a, b), (np.linalg.norm(vl) - np.linalg.norm(vr)) * mm,
                            TOL["arm_len"] * h * mm, "mm"))
    return out


def misses(m):
    """One message per broken rule (its worst item), each starting with
    the rule's own name."""
    out = []
    for rule, rows in measure(m).items():
        bad = [r for r in rows if abs(r[1]) > r[2]]
        if bad:
            w = max(bad, key=lambda r: abs(r[1]) / r[2])
            out.append("%s: %s's %s %+.2f %s, at most %.2f" % (rule, m["name"], w[0], w[1], w[3], w[2]))
    return out


def worst(m):
    """{rule: (what, value, limit, unit)} -- each rule's nearest item to its
    limit, for the table."""
    return {rule: max(rows, key=lambda r: abs(r[1]) / r[2]) for rule, rows in measure(m).items() if rows}


def check(men=MEN, models=MODELS, verbose=True):
    """Every man's rest pose against every rule; asserts on a miss."""
    built, bad = [], []
    for kind, name in men:
        m = man(kind, name, models)
        built.append(m)
        if verbose:
            print("  %-8s h %.3f  (export = generator within %.3f mm)" % (name, m["h"], m["agree"] * 1000))
            for rule, (what, v, lim, unit) in worst(m).items():
                print("    %-13s %-44s %+8.2f %-3s (at most %.2f)" % (rule, what, v, unit, lim))
        bad += misses(m)
    assert not bad, "posture: " + "; ".join(bad)
    return built


# ---------------------------------------------------------------- sabotage

def _rot(axis, deg):
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    x, y, z = axis
    return np.array([[c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
                     [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
                     [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)]])


def _copy(m):
    c = dict(m)
    c["joints"] = {k: np.array(v, dtype=float) for k, v in m["joints"].items()}
    c["eyes"] = tuple(np.array(e) for e in m["eyes"])
    c["ears"] = {k: tuple(np.array(p) for p in v) for k, v in m["ears"].items()}
    c["soles"] = {k: np.array(v) for k, v in m["soles"].items()}
    return c


def _left_arm(P):
    return [n for n in P if n.endswith("_l") and n.split("_")[0] in
            ("clavicle", "upperarm", "lowerarm", "hand", "index", "middle", "ring", "pinky", "thumb")
            and not n.startswith("ik_")]


def sabotages():
    """(name, rule, breaker): each breaker breaks one rule of a man's rest
    pose and nothing else, in place on a copy."""
    def hunch(m):           # the chest, neck and head 5 cm forward, the arms left behind
        for n in ("spine_03", "neck_01", "jaw", "head", "head_end"): m["joints"][n][1] -= 0.05

    def lean(m):            # the column 2 cm to his left, the limbs where they were
        for n in COLUMN + ("jaw", "head_end"): m["joints"][n][0] += 0.02

    def shrug(m):           # the left shoulder and the arm under it 2 cm up
        for n in _left_arm(m["joints"]): m["joints"][n][2] += 0.02

    def hike(m):            # the left hip joint 1.5 cm up
        m["joints"]["thigh_l"][2] += 0.015

    def knock(m):           # the left knee 1.5 cm in
        m["joints"]["calf_l"][0] -= 0.015

    def roll_head(m):       # the head (bone, eyes, ears) rolled 3 deg about its own joint
        P = m["joints"]; o = P["head"].copy(); R = _rot((0, 1, 0), 3.0)
        for n in ("head_end", "jaw"): P[n] = o + R @ (P[n] - o)
        m["eyes"] = tuple(o + R @ (e - o) for e in m["eyes"])
        m["ears"] = {k: tuple(o + R @ (p - o) for p in v) for k, v in m["ears"].items()}

    def twist(m):           # the hip line turned 7 deg: left hip forward, right back
        m["joints"]["thigh_l"][1] -= 0.012; m["joints"]["thigh_r"][1] += 0.012

    def toe_out(m):         # the left foot turned out 6 deg about its ankle
        P = m["joints"]; o = P["foot_l"].copy(); R = _rot((0, 0, 1), 6.0)
        for n in ("ball_l", "toe_l", "heel_l"):
            if n in P: P[n] = o + R @ (P[n] - o)

    def sole(m):            # the left shoe rolled 3 deg onto its outer edge
        V = m["soles"]["l"]; o = V.mean(0); R = _rot((0, 1, 0), 3.0)
        m["soles"]["l"] = (V - o) @ R.T + o

    def wing(m):            # the left forearm and hand swung 5 deg out about the elbow
        P = m["joints"]; o = P["lowerarm_l"].copy(); R = _rot((0, 1, 0), -5.0)
        for n in _left_arm(P):
            if n.split("_")[0] not in ("clavicle", "upperarm", "lowerarm"): P[n] = o + R @ (P[n] - o)

    return [("hunched", "plumb", hunch), ("leaning", "tilt", lean), ("shrugged", "shoulder line", shrug),
            ("hip hiked", "hip line", hike), ("knock-kneed", "mirror", knock), ("head rolled", "head", roll_head),
            ("pelvis twisted", "twist", twist), ("toe out", "feet", toe_out), ("sole rolled", "feet", sole),
            ("arm winged", "arms", wing)]


def broken(m, breaker):
    c = _copy(m); breaker(c); return c


# -------------------------------------------------------------------- sheet

_CLAY = {"Skin": (196, 160, 136), "Hair": (60, 52, 46), "Eye": (230, 230, 226), "Shoe": (70, 72, 78),
         "Glove": (150, 40, 40), "Tee": (120, 124, 132), "Pants": (96, 100, 110)}


def _draw_view(img, tris, view, ox, oy, ppm, light):
    """Flat-shaded triangles, far to near (painter's), at ppm pixels a metre.
    view "front": seen from in front of him (screen right = +X, depth +Y);
    "side": from his left (screen right = +Y, depth -X)."""
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    polys = []
    for key, V, F in tris:
        if view == "front": S = np.c_[V[:, 0], V[:, 2]]; depth = V[:, 1]
        else: S = np.c_[V[:, 1], V[:, 2]]; depth = -V[:, 0]
        T = V[F]; n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        lam = np.clip(np.abs(n @ light), 0, 1) * 0.75 + 0.25
        base = np.array(_CLAY.get(key, (150, 150, 150)), float)
        P = np.stack([ox + S[F][..., 0] * ppm, oy - S[F][..., 1] * ppm], -1)
        for k in range(len(F)):
            polys.append((depth[F[k]].mean(), P[k], tuple(int(c) for c in base * lam[k])))
    polys.sort(key=lambda t: -t[0])
    for _z, P, col in polys:
        d.polygon([tuple(p) for p in P], fill=col)


def sheet(out, before=MODELS, after=MODELS, men=MEN, ppm=230):
    """The rest pose of every man, front and side, with the plumb line (the
    midline in front, the vertical through the ankles in side view), the
    shoulder line (upperarm joints) and the hip line (thigh joints) drawn,
    and his worst numbers under him. `before` and `after` are two
    Content/Models folders; when every man's mesh and joints are the same
    in both, he is drawn once and the sheet says so."""
    from PIL import Image, ImageDraw, ImageFont
    font = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", s)
    f_big, f_mid, f_small = font(30), font(19), font(15)
    light = np.array([0.35, -0.8, 0.5]); light /= np.linalg.norm(light)
    cols = []
    for kind, name in men:
        a = read_export(name, after, with_faces=True)
        b = read_export(name, before, with_faces=True)
        same = all(np.array_equal(x[1], y[1]) for x, y in zip(a["tris"], b["tris"])) and \
            all(np.array_equal(a["joints"][k], b["joints"][k]) for k in a["joints"])
        cols.append((kind, name, [("after" if not same else "before = after", a)] + ([] if same else [("before", b)])))
    H = max(np.concatenate([t[1] for t in s[1]["tris"]])[:, 2].max() for c in cols for s in c[2])
    top, foot = 110, 230
    height = int(top + H * ppm + 40 + foot)
    panels = []
    for kind, name, states in cols:
        for label, s in states:
            V = np.concatenate([t[1] for t in s["tris"]])
            wf = (V[:, 0].max() - V[:, 0].min()) * ppm + 40
            ws = (V[:, 1].max() - V[:, 1].min()) * ppm + 120
            panels.append((kind, name, label, s, V, wf, ws))
    width = int(sum(p[5] + p[6] + 30 for p in panels) + 40)
    img = Image.new("RGB", (width, height), (246, 245, 241))
    d = ImageDraw.Draw(img)
    states = {p[2] for p in panels}
    d.text((30, 24), "Rest pose (the A-pose the engine retargets from): posture and alignment, every man", font=f_big, fill=(20, 20, 24))
    d.text((30, 66), "plumb line: red   shoulder line: blue   hip line: green   joints of the spine: black dots   ear lobe: orange   "
           + ("before = after: no man's rest pose changed (measured 2026-10-07, nothing rebuilt)" if states == {"before = after"}
              else "before and after side by side"), font=f_mid, fill=(60, 60, 66))
    x = 40
    ground = top + H * ppm + 20
    for kind, name, label, s, V, wf, ws in panels:
        m = man(kind, name, after if label != "before" else before) if label != "before" or before == after else None
        P = s["joints"]
        h = generator(kind)["h"]
        ears = generator(kind)["ears"]
        # front
        ox = x + 20 - V[:, 0].min() * ppm
        _draw_view(img, s["tris"], "front", ox, ground, ppm, light)
        X = lambda p: ox + p[0] * ppm; Z = lambda p: ground - p[2] * ppm
        d.line([(ox, ground - V[:, 2].max() * ppm - 25), (ox, ground + 8)], fill=(210, 30, 30), width=2)
        for b_, col in (("upperarm", (30, 80, 220)), ("thigh", (20, 150, 60))):
            l, r = P[b_ + "_l"], P[b_ + "_r"]
            d.line([(X(r) - 60, Z(r)), (X(l) + 60, Z(l))], fill=col, width=2)
        for n in COLUMN:
            d.ellipse([X(P[n]) - 4, Z(P[n]) - 4, X(P[n]) + 4, Z(P[n]) + 4], fill=(0, 0, 0))
        # side, seen from his left: his front to the left
        sx = x + wf + 40 - V[:, 1].min() * ppm
        _draw_view(img, s["tris"], "side", sx, ground, ppm, light)
        Y = lambda p: sx + p[1] * ppm
        ank = (P["foot_l"] + P["foot_r"]) / 2
        d.line([(Y(ank), ground - V[:, 2].max() * ppm - 25), (Y(ank), ground + 8)], fill=(210, 30, 30), width=2)
        for n in COLUMN:
            d.ellipse([Y(P[n]) - 4, Z(P[n]) - 4, Y(P[n]) + 4, Z(P[n]) + 4], fill=(0, 0, 0))
        lobe = ears["lobe"][0]
        d.ellipse([Y(lobe) - 5, Z(lobe) - 5, Y(lobe) + 5, Z(lobe) + 5], fill=(240, 140, 20))
        for b_, col in (("upperarm", (30, 80, 220)), ("thigh", (20, 150, 60))):
            p = P[b_ + "_l"]
            d.line([(Y(p) - 45, Z(p)), (Y(p) + 45, Z(p))], fill=col, width=2)
        d.line([(x, ground), (x + wf + ws + 20, ground)], fill=(120, 120, 120), width=1)
        # the words
        ty = ground + 18
        d.text((x + 10, ty), "%s  (h %.2f)  %s" % (name, h, label), font=f_mid, fill=(20, 20, 24)); ty += 28
        if m is not None:
            W = measure(m)
            def get(rule, key):
                return next(r for r in W[rule] if r[0].startswith(key))
            lines = ["plumb: spine %.1f cm, ear lobe %+.1f, knee %+.1f (fwd +)" % (
                         max(abs(r[1]) for r in W["plumb"][:len(SPINE)]), get("plumb", "ear lobe")[1], get("plumb", "knee")[1]),
                     "tilt %.1f mm   shoulders %.1f mm   hips %.1f mm" % (
                         max(abs(r[1]) for r in W["tilt"]), max(abs(r[1]) for r in W["shoulder line"]), abs(W["hip line"][0][1])),
                     "mirror %.1f mm   pelvis twist %.1f deg   arms %.2f deg" % (
                         max(abs(r[1]) for r in W["mirror"]), abs(W["twist"][0][1]),
                         max(abs(r[1]) for r in W["arms"] if r[3] == "deg")),
                     "head: roll %.2f, pitch %+.1f deg, %+.1f cm fwd" % (
                         get("head", "rolled (the eyes")[1], get("head", "pitched")[1], get("head", "forward")[1]),
                     "feet: apart %.1f deg, sole slope %.1f deg" % (
                         abs(get("feet", "headings")[1]), max(abs(r[1]) for r in W["feet"] if "slope" in r[0])),
                     "misses: %s" % (", ".join(r.split(":")[0] for r in misses(m)) or "none")]
            for ln in lines:
                d.text((x + 10, ty), ln, font=f_small, fill=(50, 50, 56)); ty += 21
        x += wf + ws + 30
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    img.save(out, optimize=True)
    return os.path.abspath(out)
