"""
Posture and alignment, before and after the runtime IK's posture stage, on
the men's real stances and Saud's real clips (2026-10-07, Riyadh; asked as
"make body Posture and Body Alignment and Straightness": keep stances, fix
faults).

    python3 Tools/look/posture_preview.py [--out DIR]

writes DIR/posture-ik.png (default Docs/renders/): one panel a case, BEFORE on
the left -- the pose as the clips, the hips' drop, the lean and the look leave
it -- and AFTER on the right, once SaudIK::StepPosture has turned his pelvis,
trunk, chest, neck and head. Seen from behind (his right to the right) or,
for turning on the spot, from above (his facing up). Drawn: the spine
(pelvis, spine_01-03, neck_01, head), the hip and shoulder lines, the head
with its eye line, the spine's line carried on past the neck (dashed: the
head belongs on it), the world's level through the eyes (thin), the legs as
lines from the hips to the balls of the feet (the engine solves them to the
feet after the posture); from above, the hip line, the shoulder line and the
feet's line. Under each figure his faults against his own stance: hips,
shoulders, trunk, eyes (degrees), the head off his spine (cm), and standing
the twist of his hips on his feet (degrees).

How: Tools/harness/posture_dump.cpp runs SaudIK.h's posture over each man's
guard joints (SaudStances.h) and Saud's motion-capture frames
(stance_clips.h), the same header the engine compiles, and prints the joints
before and after.

STAND-INS: stick figures, not the mesh; the legs are not solved here, only
drawn to the feet; the man turning on the spot turns at a constant rate.
"""

import json
import math
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))

INK = (16, 17, 22)
PAPER = (30, 32, 40)
BONE = (232, 224, 207)
RED = (200, 16, 46)        # the lead (left) side
EMBER = (232, 132, 52)     # the rear (right) side
DIM = (120, 118, 128)
GOLD = (222, 184, 92)

W, H = 1800, 1500
COLS, ROWS = 3, 2


def font(size):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def dump():
    exe = os.path.join(tempfile.mkdtemp(), "posture_dump")
    subprocess.run(["g++", "-std=c++17", "-O1", "-DSAUD_HARNESS", "-I" + os.path.join(ROOT, "Tools", "harness"),
                    "-o", exe, os.path.join(ROOT, "Tools", "harness", "posture_dump.cpp")], check=True)
    out = subprocess.run([exe], check=True, capture_output=True, text=True).stdout
    return json.loads(out)["cases"]


def dashed(d, a, b, col, w=2, dash=8):
    L = math.dist(a, b)
    if L < 1e-6:
        return
    n = int(L / dash)
    for i in range(0, n, 2):
        t0, t1 = i / n, min(1.0, (i + 1) / n)
        d.line([(a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0),
                (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)], fill=col, width=w)


def figure(d, J, view, cx, cy, k, faint):
    """One pose at (cx, cy), k pixels a cm."""
    if view == "back":
        P = lambda p: (cx + p[1] * k, cy - p[2] * k)
    else:
        P = lambda p: (cx + p[1] * k, cy - p[0] * k)
    body = DIM if faint else BONE
    w = 3 if faint else 4
    j = {n: P(J[n]) for n in J if n != "side"}
    if view == "back":
        # the legs to the feet, thin
        for s, col in (("l", RED), ("r", EMBER)):
            d.line([j["hip_" + s], j["ball_" + s]], fill=col if not faint else DIM, width=2)
        # the spine's line carried on past the neck: the head belongs on it
        a, b = J["spine_01"], J["neck"]
        t = 1.0 + math.dist(J["neck"], J["head"]) / max(1e-6, math.dist(a, b)) * 1.6
        far = [a[i] + (b[i] - a[i]) * t for i in range(3)]
        dashed(d, j["spine_01"], P(far), GOLD if not faint else DIM, 2)
        # the world's level through the eyes
        d.line([(j["head"][0] - 32 * k, j["head"][1]), (j["head"][0] + 32 * k, j["head"][1])], fill=(70, 72, 84), width=1)
    chain = ["pelvis", "spine_01", "spine_02", "spine_03", "neck", "head"]
    d.line([j[n] for n in chain], fill=body, width=w, joint="curve")
    d.line([j["hip_l"], j["pelvis"], j["hip_r"]], fill=body, width=w)
    d.line([j["shoulder_l"], j["spine_03"], j["shoulder_r"]], fill=body, width=w)
    for s, col in (("l", RED), ("r", EMBER)):
        for n in ("hip_", "shoulder_"):
            x, y = j[n + s]
            r = 5
            d.ellipse([x - r, y - r, x + r, y + r], fill=col if not faint else DIM)
    if view == "back":
        hx, hy = j["head"]
        R = 10.5 * k
        d.ellipse([hx - R, hy - R * 1.25, hx + R, hy + R * 0.75], outline=body, width=w)
        sd = J["side"]
        e0 = P([J["head"][i] - sd[i] * 8.0 for i in range(3)])
        e1 = P([J["head"][i] + sd[i] * 8.0 for i in range(3)])
        d.line([e0, e1], fill=GOLD if not faint else DIM, width=3)
    else:
        # the feet's line, the stance the hips are kept to
        d.line([j["ball_l"], j["ball_r"]], fill=GOLD if not faint else DIM, width=3)
        for s, col in (("l", RED), ("r", EMBER)):
            x, y = j["ball_" + s]
            d.ellipse([x - 7, y - 7, x + 7, y + 7], outline=col if not faint else DIM, width=3)
        hx, hy = j["head"]
        d.ellipse([hx - 9 * k, hy - 9 * k, hx + 9 * k, hy + 9 * k], outline=body, width=w)


def panel(img, case, x0, y0, pw, ph):
    d = ImageDraw.Draw(img)
    d.rectangle([x0 + 6, y0 + 6, x0 + pw - 6, y0 + ph - 6], fill=PAPER)
    f1, f2, f3 = font(26), font(17), font(19)
    d.text((x0 + 22, y0 + 18), case["name"], fill=BONE, font=f1)
    d.text((x0 + 22, y0 + 52), case["why"], fill=DIM, font=f2)
    view = case["view"]
    k = 2.45 if view == "back" else 3.6
    base = y0 + ph - 118 if view == "back" else y0 + ph * 0.52
    for i, (key, label) in enumerate((("before", "BEFORE"), ("after", "AFTER"))):
        cx = x0 + pw * (0.27 + 0.46 * i)
        figure(d, case[key], view, cx, base, k, faint=(i == 0))
        d.text((cx - 40, y0 + 80), label, fill=BONE if i else DIM, font=f3)
        if view == "top" and "ref_twist" in case:
            # the stance's own hips on these feet: the feet's line turned by his designed twist
            J = case[key]
            fl = (J["ball_r"][0] - J["ball_l"][0], J["ball_r"][1] - J["ball_l"][1])
            a = math.atan2(-fl[0], fl[1]) + math.radians(case["ref_twist"])
            dx, dy = -math.sin(a) * 14.0, math.cos(a) * 14.0       # a +Y line turned by a, cm
            P = lambda x, y: (cx + y * k, base - x * k)
            c = J["pelvis"]
            dashed(d, P(c[0] - dx, c[1] - dy), P(c[0] + dx, c[1] + dy), GOLD, 2, 6)
    F = case["faults"]
    standing = view == "top" or "standing" in case["name"]
    names = ["hips", "shoulders", "trunk", "head cm", "eyes", "twist"]
    f4 = font(15)
    for i in range(2):
        cx = x0 + pw * (0.08 + 0.46 * i)
        parts = []
        for n, (b, a) in zip(names, F):
            if n == "twist" and not standing:
                continue
            v = b if i == 0 else a
            parts.append("%s %+.1f" % (n, v))
        col = DIM if i == 0 else BONE
        for r in range(3):
            d.text((cx, y0 + ph - 86 + 22 * r), "   ".join(parts[2 * r:2 * r + 2]), fill=col, font=f4)


def main():
    out_dir = os.path.join(ROOT, "Docs", "renders")
    if "--out" in sys.argv:
        out_dir = sys.argv[sys.argv.index("--out") + 1]
    cases = dump()
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)
    d.text((24, 16), "SAUD -- posture and alignment in the runtime IK: before and after (faults against each man's own guard)",
           fill=BONE, font=font(28))
    d.text((24, 56), "his designed lean and guard kept; only the faults out -- hips level, trunk upright sideways, shoulder line, "
           "head over the spine, eyes level, hips kept to the feet", fill=DIM, font=font(18))
    top = 92
    pw, ph = W // COLS, (H - top) // ROWS
    for i, c in enumerate(cases[:COLS * ROWS]):
        panel(img, c, (i % COLS) * pw, top + (i // COLS) * ph, pw, ph)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "posture-ik.png")
    img.save(path)
    print("wrote %s: %d cases" % (os.path.relpath(path, ROOT), len(cases)))
    for c in cases:
        F = c["faults"]
        print("  %-28s %s" % (c["name"], "  ".join("%s %+.2f>%+.2f" % (n, b, a) for n, (b, a) in
                                                    zip(("hips", "shoulders", "trunk", "head", "eyes", "twist"), F))))


if __name__ == "__main__":
    main()
