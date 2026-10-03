#!/usr/bin/env python3
"""
Saud's camera, drawn from above: the harness's scripted scenes (tests/
camera.cpp --dump), one panel each -- where he was, where the men were, where
the camera stood and which way it looked, every sixth of a second, with its
field of view drawn at the end of the scene.

    python3 Tools/harness/camera_paths.py      -> Docs/renders/camera-paths.png

Needs g++ and Pillow. The picture is SaudCamera.h's own maths run, not a
render of the game: no engine has run the camera.
"""
import math
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "Docs", "renders", "camera-paths.png")
SCENES = [("run", "a run: in behind him, looking ahead, out at the run"),
          ("one man", "one man: across the line between them, both in shot"),
          ("three men", "three men: pulled back to hold them all"),
          ("circling", "a man circling: it follows, never flips"),
          ("feinting", "a man feinting: one side, held"),
          ("finisher", "the finisher: round him and back")]
HFOV = 90.0


def dump():
    tmp = tempfile.mkdtemp()
    exe, path = os.path.join(tmp, "camera"), os.path.join(tmp, "camera.txt")
    subprocess.run(["g++", "-std=c++17", "-O1", "-DSAUD_HARNESS", "-I" + HERE, "-o", exe,
                    os.path.join(HERE, "tests", "camera.cpp")], check=True)
    subprocess.run([exe, "--dump", path], check=True, stdout=subprocess.DEVNULL)
    rows = {}
    for line in open(path):
        p = line.split()
        # the scene's name may have a space in it: the numbers are the last fields
        n_opp = None
        for cut in range(1, 3):
            name, nums = " ".join(p[:cut]), p[cut:]
            try:
                vals = [float(v) for v in nums]
            except ValueError:
                continue
            n_opp = int(vals[11])
            if len(vals) == 12 + 2 * n_opp:
                break
        rows.setdefault(name, []).append(vals)
    return rows


def draw(rows):
    from PIL import Image, ImageDraw
    W, H, PAD = 520, 520, 12
    cols = 3
    sheet = Image.new("RGB", (cols * W, 2 * (H + 40)), (12, 14, 20))
    for i, (name, caption) in enumerate(SCENES):
        data = rows.get(name)
        if not data:
            continue
        px, py = (i % cols) * W, (i // cols) * (H + 40)
        panel = Image.new("RGB", (W, H + 40), (12, 14, 20))
        ox, oy = 0, 0
        pts = [(r[1], r[2]) for r in data] + [(r[3], r[4]) for r in data]
        for r in data:
            n = int(r[11])
            pts += [(r[12 + 2 * k], r[13 + 2 * k]) for k in range(n)]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        span = max(max(xs) - min(xs), max(ys) - min(ys), 800.0) * 1.15
        sc = (W - 2 * PAD) / span

        def to(x, y):
            # Unreal +X right, +Y down the picture is a mirror: draw +Y up
            return (ox + W / 2 + (x - cx) * sc, oy + H / 2 - (y - cy) * sc)
        g = ImageDraw.Draw(panel)
        g.rectangle([ox + 4, oy + 4, ox + W - 4, oy + H - 4], outline=(40, 44, 56))
        # his path
        g.line([to(r[1], r[2]) for r in data], fill=(200, 60, 60), width=2)
        # the men, where they ended (and their path, faint)
        last = data[-1]
        for k in range(int(last[11])):
            trail = [to(r[12 + 2 * k], r[13 + 2 * k]) for r in data if int(r[11]) > k]
            if len(trail) > 1:
                g.line(trail, fill=(90, 90, 110), width=1)
            x, y = to(last[12 + 2 * k], last[13 + 2 * k])
            g.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(170, 170, 190))
        # the camera, every tenth frame: where it stood, a tick toward its look
        for j, r in enumerate(data):
            if j % 10:
                continue
            ex, ey = to(r[3], r[4])
            yaw = math.radians(r[5])
            g.line([(ex, ey), (ex + 14 * math.cos(yaw), ey - 14 * math.sin(yaw))], fill=(80, 170, 255), width=1)
            g.ellipse([ex - 2, ey - 2, ex + 2, ey + 2], fill=(80, 170, 255))
        # the field of view at the end
        ex, ey = to(last[3], last[4])
        yaw = math.radians(last[5])
        reach = last[7] * 1.6 * sc
        for s in (-1, 1):
            a = yaw + s * math.radians(HFOV / 2)
            g.line([(ex, ey), (ex + reach * math.cos(a), ey - reach * math.sin(a))], fill=(80, 170, 255), width=1)
        sx, sy = to(last[1], last[2])
        g.ellipse([sx - 7, sy - 7, sx + 7, sy + 7], fill=(220, 50, 50))
        g.rectangle([0, H - 2, W, H + 40], fill=(12, 14, 20))
        g.text((ox + 10, oy + H + 6), caption, fill=(220, 220, 225))
        g.text((ox + 10, oy + H + 22), "boom %.0f cm at the end, %.1f s" % (last[7], last[0]), fill=(150, 150, 160))
        sheet.paste(panel, (px, py))
    sheet.save(OUT)
    return OUT


if __name__ == "__main__":
    print("drew", draw(dump()))
