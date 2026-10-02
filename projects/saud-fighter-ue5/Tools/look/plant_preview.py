"""
The feet on the ground, before and after the runtime IK, on real clips
(2026-10-02, Riyadh; asked as "improve plants ik": "show it working").

    python3 Tools/look/plant_preview.py [--out DIR]

writes DIR/plants-ik.png (default Docs/renders/): one row per case, BEFORE on
the left -- the clip's feet as the game drew them until now, its clock at its
own rate wherever the man goes -- and AFTER on the right, SaudIK's feet as
USaudMotionAnimInstance runs them. Seen from above: the man's path a thin
line, each ball a trail of dots, left in bone and right in blood, big where
the clip has that foot down (its measured plants, SaudPlants.h); after, a
ring round a held ball and a gold tick where a foot takes a step of its own.
Under each panel, the number that matters: how far a ball slides across the
ground while its clip has it down, in cm for every second it is down.

How: Tools/blender/measure_plants.py --dump samples each clip's ankles,
balls, hips and knees from its FBX, and Tools/harness/plant_dump.cpp runs
SaudIK.h's feet over them (the same header the engine compiles) with the man
moving and turning as each case says. Flat ground: the ground's own part of
the IK (kerbs, ramps) is the harness's to check, not this sheet's.

STAND-INS: the man moves at a constant speed and turns at a constant rate;
the game's capsule accelerates. The ground is flat. No pose is drawn, only
the balls.
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
sys.path.insert(0, os.path.join(ROOT, "Tools", "blender"))

# name, clip, speed cm/s, turn deg/s, seconds, way, attack, strike leg, the one-line why
CASES = (
    ("walk at his own pace", "A_Saud_Walk_Fwd", 336.0, 0.0, 1.2, "fwd", 0, -1,
     "Saud's walk, at the 336 cm/s it was made for"),
    ("walk faster than the clip", "A_Saud_Walk_Fwd", 504.0, 0.0, 1.2, "fwd", 0, -1,
     "the street runner's 504 cm/s on a 336 cm/s walk"),
    ("walk slower than the clip", "A_Saud_Walk_Fwd", 120.0, 0.0, 1.6, "fwd", 0, -1,
     "an approach at 120 cm/s: under half the walk's own pace"),
    ("turn on the spot", "A_Saud_Guard", 0.0, 150.0, 1.2, "fwd", 0, -1,
     "the guard while the facing swings 150 degrees a second"),
    ("ZAYOS walks", "A_Zayos_Walk_Fwd", 259.0, 40.0, 1.4, "fwd", 0, -1,
     "ZAYOS at his own 259 cm/s, curving 40 degrees a second"),
    ("a side walk", "A_Saud_Walk_Left", 336.0, 0.0, 1.2, "left", 0, -1,
     "to his left at his pace; the clip hops, both feet together"),
    ("a kick", "A_Saud_Kick", 0.0, 0.0, 0.53, "fwd", 1, 1,
     "the left foot stands; the right leg is the strike's"),
    ("a block walked", "A_Saud_Block", 200.0, 0.0, 1.2, "left", 0, -1,
     "pushed 200 cm/s sideways; a block does not step, it glides"),
)

W, ROW_H, PAD = 1800, 300, 18
PANEL_W = (W - 3 * PAD) // 2
INK = (12, 12, 14)
PAPER = (28, 28, 32)
GRID = (44, 44, 50)
BONE = (226, 218, 200)
BLOOD = (192, 26, 31)
GOLD = (210, 170, 70)
DIM = (130, 126, 118)


def font(size):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def build(tmp):
    exe = os.path.join(tmp, "plant_dump")
    subprocess.check_call([os.environ.get("CXX", "g++"), "-std=c++17", "-O1", "-Wall", "-Wextra", "-Werror", "-DSAUD_HARNESS",
                           "-I" + os.path.join(ROOT, "Tools", "harness"), "-o", exe,
                           os.path.join(ROOT, "Tools", "harness", "plant_dump.cpp")])
    return exe


def sample_clips(names, tmp):
    """measure_plants' own sampler, in a Blender of its own (it empties the scene)."""
    out = os.path.join(tmp, "clips.json")
    subprocess.check_call([sys.executable, os.path.join(ROOT, "Tools", "blender", "measure_plants.py"),
                           "--dump", *names, "--out", out], stdout=subprocess.DEVNULL)
    with open(out) as fh:
        return json.load(fh)


def rest_of(clips_json, name):
    """The man's rest: the lower foot of his own guard's first frame (measure_plants' rule)."""
    g = clips_json["A_%s_Guard" % name.split("_")[1]]["frames"][0]
    return min(g["ankle_l"][2], g["ankle_r"][2]), min(g["ball_l"][2], g["ball_r"][2])


def write_clip(path, name, c, rest):
    with open(path, "w") as fh:
        fh.write("clip %s loop %d seconds %.4f frames %d rest %.4f %.4f\n" % (
            name, 1 if c["loop"] else 0, c["seconds"], len(c["frames"]), rest[0], rest[1]))
        for fr in c["frames"]:
            vals = []
            for s in ("l", "r"):
                for k in ("ankle_", "ball_", "hip_", "knee_"):
                    vals.extend(fr[k + s])
            fh.write(" ".join("%.4f" % v for v in vals) + "\n")


def run(exe, clip_txt, mode, case):
    _, _, speed, turn, secs, way, attack, leg, _ = case
    out = subprocess.check_output([exe, clip_txt, "mode=" + mode, "speed=%g" % speed, "turn=%g" % turn,
                                   "seconds=%g" % secs, "way=" + way, "attack=%d" % attack, "strikeleg=%d" % leg])
    return json.loads(out)


def slide(ticks, leg=-1):
    """cm a ball slides across the ground per second the clip has it down:
    both feet, but not the strike's leg (it is the blow's, not the ground's),
    and not while the IK is taking a step of its own (a step is meant to
    move the foot; the slide is what moves it without one)."""
    moved, down = 0.0, 0.0
    for a, b in zip(ticks, ticks[1:]):
        dt = b[0] - a[0]
        for s, (ix, iy, istp, idown) in enumerate(((2, 3, 10, 12), (5, 6, 11, 13))):
            if s == leg or a[istp] or b[istp]:
                continue
            if a[idown] and b[idown]:
                moved += math.hypot(b[ix] - a[ix], b[iy] - a[iy])
                down += dt
    return moved / down if down > 0 else 0.0


def steps(ticks):
    n = 0
    for a, b in zip(ticks, ticks[1:]):
        for i in (10, 11):
            if b[i] and not a[i]:
                n += 1
    return n


def draw_panel(img, box, d, title, sub, bounds):
    x0, y0, x1, y1 = box
    dr = ImageDraw.Draw(img)
    dr.rectangle(box, fill=PAPER)
    (mx0, my0, mx1, my1) = bounds
    scale = min((x1 - x0 - 40) / max(mx1 - mx0, 1.0), (y1 - y0 - 80) / max(my1 - my0, 1.0))
    cx, cy = (mx0 + mx1) / 2, (my0 + my1) / 2

    def P(x, y):    # world X right, world Y up the page
        return (x0 + (x1 - x0) / 2 + (x - cx) * scale, y0 + 30 + (y1 - y0 - 80) / 2 - (y - cy) * scale)
    # a 50 cm grid
    g0 = math.floor(mx0 / 50) * 50
    while g0 <= mx1:
        dr.line([P(g0, my0), P(g0, my1)], fill=GRID)
        g0 += 50
    g0 = math.floor(my0 / 50) * 50
    while g0 <= my1:
        dr.line([P(mx0, g0), P(mx1, g0)], fill=GRID)
        g0 += 50
    t = d["ticks"]
    dr.line([P(k[14], k[15]) for k in t], fill=DIM, width=1)
    for k in t:
        for s, (ix, iy, ih, istp, idn) in enumerate(((2, 3, 8, 10, 12), (5, 6, 9, 11, 13))):
            col = BONE if s == 0 else BLOOD
            px, py = P(k[ix], k[iy])
            r = 3.2 if k[idn] else 1.4
            dr.ellipse([px - r, py - r, px + r, py + r], fill=col)
            if k[ih]:
                dr.ellipse([px - 6, py - 6, px + 6, py + 6], outline=col, width=1)
            if k[istp]:
                dr.line([px, py - 9, px, py - 15], fill=GOLD, width=2)
    dr.text((x0 + 12, y0 + 6), title, font=font(20), fill=BONE)
    dr.text((x0 + 12, y1 - 30), sub, font=font(17), fill=GOLD)


def main():
    out_dir = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(ROOT, "Docs", "renders")
    os.makedirs(out_dir, exist_ok=True)
    names = sorted({c[1] for c in CASES} | {"A_%s_Guard" % c[1].split("_")[1] for c in CASES})
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        exe = build(tmp)
        clips = sample_clips(names, tmp)
        for case in CASES:
            name = case[1]
            txt = os.path.join(tmp, name + ".txt")
            write_clip(txt, name, clips[name], rest_of(clips, name))
            before, after = run(exe, txt, "before", case), run(exe, txt, "after", case)
            rows.append((case, before, after))
            print("%-28s slides while down: before %6.1f cm/s, after %5.1f cm/s; %d steps of its own" % (
                case[0], slide(before["ticks"], case[7]), slide(after["ticks"], case[7]), steps(after["ticks"])))

    H = PAD + len(rows) * (ROW_H + PAD) + 70
    img = Image.new("RGB", (W, H), INK)
    dr = ImageDraw.Draw(img)
    dr.text((PAD, 14), "THE FEET ON THE GROUND  --  before (the clip as drawn until now)   |   after (the runtime IK, measured plants)",
            font=font(24), fill=BONE)
    dr.text((PAD, 44), "from above, 50 cm grid; left ball bone, right ball blood, big dots where the clip has it down, "
                       "rings where it is held, gold ticks where it steps", font=font(16), fill=DIM)
    for i, (case, before, after) in enumerate(rows):
        y = 70 + PAD + i * (ROW_H + PAD)
        pts = [(k[a], k[b]) for d in (before, after) for k in d["ticks"] for a, b in ((2, 3), (5, 6), (14, 15))]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        bounds = (min(xs) - 20, min(ys) - 20, max(xs) + 20, max(ys) + 20)
        sb, sa = slide(before["ticks"], case[7]), slide(after["ticks"], case[7])
        draw_panel(img, (PAD, y, PAD + PANEL_W, y + ROW_H), before, "BEFORE  " + case[0],
                   "slides %.1f cm/s while down" % sb, bounds)
        draw_panel(img, (2 * PAD + PANEL_W, y, W - PAD, y + ROW_H), after, "AFTER  " + case[0],
                   "slides %.1f cm/s while down  -  %d steps of its own" % (sa, steps(after["ticks"])), bounds)
        ImageDraw.Draw(img).text((PAD + 12, y + 32), case[8], font=font(15), fill=DIM)
    path = os.path.join(out_dir, "plants-ik.png")
    img.save(path)
    print(path)


if __name__ == "__main__":
    main()
