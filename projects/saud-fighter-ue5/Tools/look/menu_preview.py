"""
The menu, drawn without an engine: SaudMenu::Build (Combat/SaudMenu.h) at
a screen size, as SaudHUD.cpp will draw it -- the Title, the Pause, the
Settings and the Controls screen on an Xbox pad and on a PlayStation pad.

Tools/harness/menu_dump.cpp prints the menu's draw list as JSON and this
rasterises it with hud_preview.py's own rasteriser (imported, not copied):
the triangles with their per-vertex colour and alpha, in order, blended in
LINEAR light, supersampled 3x (2x past 2560 wide) and box-filtered; each
text item drawn the way SaudHUD.cpp draws it -- eight copies in ink offset
by its stroke (N, S, E, W and the four diagonals at 0.7071), then the fill.
A prompt glyph's letter ("A", "L1") is a text item like any other and is
drawn the same way. The word for each item comes with the dump ("string"),
resolved from the headers' own slot tables by menu_dump.cpp, so this file
holds no copy of them.

STAND-INS, not the engine's:
  - the Title, the Settings and the Controls screen are drawn over a plain
    plate of the palette's Trough black. In the game the Title stands over
    the level itself -- since 2026-10-01 Saud live in his guard, framed by
    ASaudTitleCamera, drawn over the souq by Tools/blender/title_preview.py
    (menu-title-3d*.png) -- and a page opened from the Title stands over
    the same; here a dark plate stands in for it. Whatever the level looks like, the wash,
    the plates and the scrim are what the eye is being asked about;
  - the Pause is drawn over Docs/renders/souq-fight-anime.png, the same
    render hud_preview.py uses, since a pause stands over a stopped fight
    and the scrim is meant to be seen doing its work over one;
  - the lettering is DejaVu Sans Bold sized so its line height is the
    item's height; the engine draws its own Roboto (hud_preview's note);
  - blending is in linear light, as hud_preview's is.

RUN
  python3 Tools/look/menu_preview.py [--out DIR] [--bg PNG]
writes menu-title.png, menu-pause.png, menu-settings.png,
menu-controls-xbox.png, menu-controls-ps5.png (1920x1080) and
menu-title-21x9.png (2560x1080) into DIR (default Docs/renders/).
"""

import json
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hud_preview  # noqa: E402  (the rasteriser: Raster, background, ROOT)

ROOT = hud_preview.ROOT
TROUGH = (0.006, 0.006, 0.008)   # SaudHud::Colour::Trough, linear


def build_dump(out_dir):
    """Compile menu_dump.cpp with the harness's flags; the binary's path."""
    exe = os.path.join(out_dir, "menu_dump")
    cxx = os.environ.get("CXX", "g++")
    subprocess.check_call([cxx, "-std=c++17", "-O1", "-Wall", "-Wextra", "-Werror", "-DSAUD_HARNESS",
                           "-I" + os.path.join(ROOT, "Tools", "harness"), "-o", exe,
                           os.path.join(ROOT, "Tools", "harness", "menu_dump.cpp")])
    return exe


def dump(exe, w, h, state):
    args = [exe, str(w), str(h)] + ["%s=%s" % (k, v) for k, v in state.items()]
    return json.loads(subprocess.check_output(args))


def plate(w, h):
    """A Trough-black plate: the stand-in for the level under the Title."""
    return Image.new("RGB", (w, h), (0, 0, 0))


def draw(exe, bg, w, h, state, out):
    d = dump(exe, w, h, state)
    assert not d["overflow"], "the menu's draw list overflowed"
    over_fight = state["screen"] == "pause"
    r = hud_preview.Raster(hud_preview.background(bg, w, h) if over_fight else plate(w, h), 3 if w <= 2560 else 2)
    if not over_fight:
        r.lin[:] = np.array(TROUGH, np.float32)   # exact linear Trough, not a rounded sRGB byte
    done = 0
    for item in d["texts"]:
        for t in d["tris"][done:item["after"]]:
            r.tri(t)
        done = item["after"]
        r.text(item["string"], item)
    for t in d["tris"][done:]:
        r.tri(t)
    r.image().save(out)
    return len(d["tris"]), len(d["texts"])


# The six the docs show. clock=0.62 puts the focus pulse near its top;
# since=1 has the slash fully wiped open (SlashRevealSeconds is 0.4).
SHOTS = (
    ("menu-title.png", 1920, 1080,
     dict(screen="title", pad="xbox", focus=0, save=0, clock=0.62, since=1.0)),
    ("menu-pause.png", 1920, 1080,
     dict(screen="pause", pad="xbox", focus=0, save=1, clock=0.62, since=1.0)),
    ("menu-settings.png", 1920, 1080,
     dict(screen="settings", pad="xbox", focus=1, save=0, clock=0.62, since=1.0)),
    ("menu-controls-xbox.png", 1920, 1080,
     dict(screen="controls", pad="xbox", shown="xbox", focus=0, save=0, clock=0.62, since=1.0)),
    ("menu-controls-ps5.png", 1920, 1080,
     dict(screen="controls", pad="ps", shown="ps", focus=0, save=0, clock=0.62, since=1.0)),
    ("menu-title-21x9.png", 2560, 1080,
     dict(screen="title", pad="ps", focus=0, save=1, clock=0.62, since=1.0)),
)


def main():
    out_dir = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(ROOT, "Docs", "renders")
    bg = sys.argv[sys.argv.index("--bg") + 1] if "--bg" in sys.argv else os.path.join(
        ROOT, "Docs", "renders", "souq-fight-anime.png")
    os.makedirs(out_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        exe = build_dump(tmp)
        for name, w, h, state in SHOTS:
            n, m = draw(exe, bg, w, h, state, os.path.join(out_dir, name))
            print("%s: %dx%d, %d triangles, %d texts" % (os.path.join(out_dir, name), w, h, n, m))


if __name__ == "__main__":
    main()
