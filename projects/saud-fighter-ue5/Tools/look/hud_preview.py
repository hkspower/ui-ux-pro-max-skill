"""
The HUD, drawn without an engine: SaudHud::Build (Combat/SaudAnime.h) at a
screen size, over a render of the souq fight, as SaudHUD.cpp would draw it.

Since 2026-09-28 the HUD's whole picture is one pure function in the
header; Tools/harness/hud_dump.cpp prints its draw list as JSON and this
rasterises that list -- the triangles with their per-vertex colour and
alpha, in order, blended in LINEAR light, and each text item drawn the way
SaudHUD.cpp draws it: eight copies in ink offset by its stroke (N, S, E, W
and the four diagonals at 0.7071), then the fill. So the preview is the
C++'s output, not a second copy of it that could drift.

STAND-INS, not the engine's:
  - the lettering is DejaVu Sans Bold, sized so its line height is the text
    item's height (SaudHUD.cpp scales the engine font by its
    MaxCharHeight); the engine draws its own Roboto;
  - blending is in linear light; if UE's Canvas blends translucent
    triangles in display space, the washes read lighter or darker than
    here;
  - supersampled 3x (2x past 2560 wide) and box-filtered.

RUN
  python3 Tools/look/hud_preview.py [--out DIR] [--bg PNG]
writes hud-1080.png, hud-21x9.png, hud-4x3.png and hud-lowhealth.png into
DIR (default Docs/renders/), over --bg (default
Docs/renders/souq-fight-anime.png, fitted by height and padded with its
own edge colour on the wider and narrower shapes).
"""

import json
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SLOTS = {0: "name", 1: "count", 2: "hits", 3: "boss"}


def s2l(c):
    c = np.asarray(c, np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def l2s(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def build_dump(out_dir):
    """Compile hud_dump.cpp with the harness's flags; the binary's path."""
    exe = os.path.join(out_dir, "hud_dump")
    cxx = os.environ.get("CXX", "g++")
    subprocess.check_call([cxx, "-std=c++17", "-O1", "-Wall", "-Wextra", "-Werror", "-DSAUD_HARNESS",
                           "-I" + os.path.join(ROOT, "Tools", "harness"), "-o", exe,
                           os.path.join(ROOT, "Tools", "harness", "hud_dump.cpp")])
    return exe


def dump(exe, w, h, state):
    args = [exe, str(w), str(h)]
    for k, v in state.items():
        if k == "street":
            args += ["street=%g:%g:%g:%g" % tuple(b) for b in v]
        elif k != "boss_name":
            args.append("%s=%g" % (k, float(v)))
    return json.loads(subprocess.check_output(args))


def background(path, w, h):
    img = Image.open(path).convert("RGB")
    if img.size == (w, h):
        return img
    k = h / img.size[1]
    fit = img.resize((max(1, int(round(img.size[0] * k))), h), Image.LANCZOS)
    edge = tuple(int(v) for v in np.asarray(fit)[:, :4].reshape(-1, 3).mean(axis=0))
    canvas = Image.new("RGB", (w, h), edge)
    canvas.paste(fit, ((w - fit.size[0]) // 2, 0))
    return canvas


class Raster:
    """A supersampled linear-light buffer the draw list is composited into."""

    def __init__(self, img, ss):
        self.ss = ss
        self.w, self.h = img.size
        big = img.resize((self.w * ss, self.h * ss), Image.NEAREST)
        self.lin = s2l(np.asarray(big, np.float32) / 255.0)

    def tri(self, t):
        ss = self.ss
        p = np.array([[t[0], t[1]], [t[6], t[7]], [t[12], t[13]]], np.float64) * ss
        c = np.array([t[2:6], t[8:12], t[14:18]], np.float64)
        x0 = max(int(np.floor(p[:, 0].min())), 0); x1 = min(int(np.ceil(p[:, 0].max())), self.lin.shape[1] - 1)
        y0 = max(int(np.floor(p[:, 1].min())), 0); y1 = min(int(np.ceil(p[:, 1].max())), self.lin.shape[0] - 1)
        if x1 < x0 or y1 < y0:
            return
        yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1].astype(np.float64) + 0.5
        (ax, ay), (bx, by), (cx, cy) = p
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-9:
            return
        l0 = ((by - cy) * (xx - cx) + (cx - bx) * (yy - cy)) / den
        l1 = ((cy - ay) * (xx - cx) + (ax - cx) * (yy - cy)) / den
        l2 = 1.0 - l0 - l1
        inside = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
        if not inside.any():
            return
        col = l0[..., None] * c[0] + l1[..., None] * c[1] + l2[..., None] * c[2]
        a = np.where(inside, col[..., 3], 0.0)[..., None]
        sub = self.lin[y0:y1 + 1, x0:x1 + 1]
        self.lin[y0:y1 + 1, x0:x1 + 1] = sub * (1 - a) + col[..., :3] * a

    def text(self, s, item):
        ss = self.ss
        h = item["h"] * ss
        ref = ImageFont.truetype(FONT, 100)
        asc, desc = ref.getmetrics()
        font = ImageFont.truetype(FONT, max(4, int(round(100 * h / (asc + desc)))))
        width = ImageDraw.Draw(Image.new("L", (1, 1))).textlength(s, font=font)
        x = item["x"] * ss - (0.5 * width if item["centre"] else 0.0)
        y = item["y"] * ss
        st = item["stroke"] * ss
        mask = Image.new("L", (self.lin.shape[1], self.lin.shape[0]), 0)
        d = ImageDraw.Draw(mask)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (.7071, .7071), (-.7071, .7071), (.7071, -.7071),
                       (-.7071, -.7071)):
            d.text((x + dx * st, y + dy * st), s, font=font, fill=255)
        # the ink is full under a text at half its opacity or more, and fades
        # with a text fading in below that (SaudHUD.cpp's DrawText)
        m = np.asarray(mask, np.float32)[..., None] / 255.0 * min(1.0, 2.0 * item["rgba"][3])
        self.lin = self.lin * (1 - m) + np.array([0.0022, 0.0019, 0.0017], np.float32) * m   # Colour::Ink
        fill = Image.new("L", mask.size, 0)
        ImageDraw.Draw(fill).text((x, y), s, font=font, fill=255)
        f = np.asarray(fill, np.float32)[..., None] / 255.0 * item["rgba"][3]
        self.lin = self.lin * (1 - f) + np.array(item["rgba"][:3], np.float32) * f

    def image(self):
        ss = self.ss
        small = self.lin.reshape(self.h, ss, self.w, ss, 3).mean(axis=(1, 3))
        return Image.fromarray((l2s(small) * 255.0 + 0.5).astype(np.uint8))


def draw(exe, bg, w, h, state, out):
    d = dump(exe, w, h, state)
    assert not d["overflow"], "the draw list overflowed"
    r = Raster(background(bg, w, h), 3 if w <= 2560 else 2)
    names = {"name": "SAUD", "hits": "HITS", "boss": state.get("boss_name", "AL-WAHSH")}
    done = 0
    for item in d["texts"]:
        for t in d["tris"][done:item["after"]]:
            r.tri(t)
        done = item["after"]
        slot = SLOTS[item["slot"]]
        r.text(str(item["value"]) if slot == "count" else names[slot], item)
    for t in d["tris"][done:]:
        r.tri(t)
    r.image().save(out)
    return len(d["tris"])


# The four the docs show: a fight in progress at 1080p, the same page on an
# ultrawide and on 4:3, and low health (the drips) with a boss being met
# (the banner half open).
SHOTS = (
    ("hud-1080.png", 1920, 1080,
     dict(health=0.62, ghost=0.80, stamina=0.70, rage=0.80, combo=7, since=0.5, boss=1, boss_health=0.55,
          boss_ghost=0.70, boss_since=2.0, clock=0.62, street=[(660, 280, 0.45, 0.70)], boss_name="AL-WAHSH")),
    ("hud-21x9.png", 3440, 1440,
     dict(health=0.90, ghost=0.90, stamina=1.0, rage=0.30, combo=2, since=0.02, boss=1, boss_health=0.80,
          boss_ghost=0.95, boss_since=2.0, boss_name="AL-SAQR")),
    ("hud-4x3.png", 1600, 1200,
     dict(health=0.62, ghost=0.80, stamina=0.40, rage=1.0, ready=1, combo=23, since=0.05, boss=1,
          boss_health=0.30, boss_ghost=0.30, enraged=1, boss_since=2.0, clock=0.30, boss_name="ZAYOS")),
    ("hud-lowhealth.png", 1920, 1080,
     dict(health=0.24, ghost=0.42, stamina=0.25, rage=0.55, combo=12, since=0.0, boss=1, boss_health=0.95,
          boss_ghost=0.95, boss_since=0.25, clock=0.62, boss_name="AL-WAHSH")),
)


def main():
    out_dir = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(ROOT, "Docs", "renders")
    bg = sys.argv[sys.argv.index("--bg") + 1] if "--bg" in sys.argv else os.path.join(
        ROOT, "Docs", "renders", "souq-fight-anime.png")
    os.makedirs(out_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        exe = build_dump(tmp)
        for name, w, h, state in SHOTS:
            n = draw(exe, bg, w, h, state, os.path.join(out_dir, name))
            print("%s: %dx%d, %d triangles" % (os.path.join(out_dir, name), w, h, n))


if __name__ == "__main__":
    main()
