"""
Every colour the Unreal tools take from the browser game, held to the
browser's data (2026-10-03, Riyadh; asked as "improve colors accuracy",
settled as: the data colours match).

    python3 Tools/look/data_colours.py           the check
    python3 Tools/look/data_colours.py --bite    each copy broken once
    python3 Tools/look/data_colours.py --baked [--bite]   the men's baked
                                             maps against their colours

The browser owns every colour that is not marked Unreal-only, and
Content/Data/DT_Colors.csv is its export (Tools/export/export.mjs, 255 rows
since 2026-10-02). Three things in the Unreal tools carry the browser's
colours, and each is held to that table here:

  - the men (Tools/blender/hero/roster.py reads assets/saud.js and
    assets/enemies.js for the 3D pipeline): every fighter's skin, top,
    bottom, band, hair, beard and cap against Kit_<Fighter>_*, all twelve
    -- a hex as a hex, a wash (the browser's rgba beard) by its colour and
    its alpha;
  - the open world's ground (Tools/levels/build_world.py THEME_GROUND,
    also its own check 27) against Theme_<Place>_Ground0/1, all nine;
  - the souq's ground (Tools/blender/build_souq.py BROWSER_ART["ground"])
    against Theme_Souq_Ground0/1.

What the Unreal build changes ON PURPOSE is not a copy and is not checked
here: the dark kits drawn up to a fabric's floor (hero/finish.fabric), the
weathering of the souq (build_souq._worn), the look's own palette (LOOK,
SaudHud::Colour, the fire's embers) and the cars -- each is labelled
Unreal-only where it lives. Everything else the souq draws (BROWSER_ART's
brick, lantern, crate ...) comes from the browser's DRAWING in index.html,
which is not in the data and so has no row to be held to.
"""

import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
COLORS_CSV = os.path.join(ROOT, "Content", "Data", "DT_Colors.csv")
sys.path.insert(0, os.path.join(ROOT, "Tools", "blender"))
sys.path.insert(0, os.path.join(ROOT, "Tools", "levels"))

KIT_SLOTS = (("skin", "col"), ("top", "col"), ("bottom", "col"), ("band", "col"),
             ("hair", "look"), ("beard", "look"), ("cap", "look"))


def _rgba(text):
    """A CSS colour as (r, g, b, a), 0-255 and 0-1."""
    text = text.strip().lower()
    if text.startswith("#"):
        h = text[1:]
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (1.0,)
    m = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+))?\s*\)", text)
    assert m, "not a colour: %s" % text
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), float(m.group(4)) if m.group(4) else 1.0)


def table():
    return {r["Name"]: r for r in csv.DictReader(open(COLORS_CSV, encoding="utf-8"))}


def copies(sabotage=None):
    """(what, the copy's colour text, the row it must equal)."""
    from hero import roster
    import build_souq
    import build_world
    out = []
    kinds = ["saud"] + sorted(roster.enemies())
    for kind in kinds:
        s = roster.spec(kind)
        for slot, where in KIT_SLOTS:
            v = s[where].get(slot)
            if isinstance(v, str):
                if sabotage == "kit" and kind == "thug" and slot == "top":
                    v = "#8a9098"
                out.append(("%s's %s (roster)" % (s["name"], slot), v, "Kit_%s_%s" % (s["name"], slot.capitalize())))
    grounds = dict(build_world.THEME_GROUND)
    if sabotage == "world":
        grounds["Desert"] = ("#c2a275", grounds["Desert"][1])
    for place, pair in grounds.items():
        for i, h in enumerate(pair):
            out.append(("%s ground %d (build_world)" % (place, i), h, "Theme_%s_Ground%d" % (place, i)))
    souq = list(build_souq.BROWSER_ART["ground"])
    if sabotage == "souq":
        souq[1] = "#7c5231"
    for i, h in enumerate(souq):
        out.append(("souq ground %d (build_souq)" % i, h, "Theme_Souq_Ground%d" % i))
    return out


def check(sabotage=None):
    rows = table()
    if sabotage == "row":
        rows["Kit_Zayos_Skin"] = dict(rows["Kit_Zayos_Skin"], Css="#79503c")
    miss = []
    seen = 0
    for what, text, row in copies(sabotage):
        if row not in rows:
            miss.append("%s: DT_Colors.csv has no %s" % (what, row))
            continue
        a, b = _rgba(text), _rgba(rows[row]["Css"])
        if a[:3] != b[:3] or abs(a[3] - b[3]) > 1e-6:
            miss.append("%s is %s, the data's %s is %s" % (what, text, row, rows[row]["Css"]))
        seen += 1
    return miss, seen


# ------------------------------------------------- the men's baked colours
# Each man's baked colour maps against the colours they were meant to bake
# to (hero.finish.palette_for: the roster, the Unreal-only kit, the dark
# kits' fabric floor), in CIELAB. Measured 2026-10-03 on all six: skin
# 0.8-1.4 (a shade darker -- the mottle, the flush and the stubble are
# painted in), tops and trousers 0.2-0.7, shoes 1.3, gloves 0.1; nothing
# over the 2.3 an eye can just tell apart, so nothing was re-baked. The
# hair is held on the darkest quarter of its texels -- most of a cut's map
# is its faded sides, painted as skin through stubble by design (AL-SAQR's
# crest is a strip down the middle), and the strands paint their gaps
# darker -- at 3.0: 0.0-2.6.
BAKED_DE = 2.3
HAIR_DE = 3.0
MEN = ("saud", "thug", "brawler", "saqr", "boss", "zayos")
PARTS = (("Skin", "skin"), ("Tee", "tee"), ("Pants", "pants"), ("Shoe", "shoe"), ("Glove", "band"), ("Hair", "hair"))


def _lab(c):
    import numpy as np
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    x = (M @ c) / np.array([0.95047, 1.0, 1.08883])
    f = np.where(x > 216 / 24389, np.cbrt(x), (24389 / 27 * x + 16) / 116)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def check_baked(sabotage=None):
    """The baked maps against their palettes; needs bpy (hero.finish)."""
    import numpy as np
    from PIL import Image
    from hero import finish as F, pipeline as PL, roster
    lin = lambda c: np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    miss, rows = [], []
    for kind in MEN:
        spec = roster.spec(kind)
        pal = F.palette_for(spec, PL.KIT.get(kind), PL.TOPS.get(kind, "tee"), PL.BOTTOMS.get(kind, "track"))
        man = spec["name"]
        for part, key in PARTS:
            path = os.path.join(ROOT, "Content", "Textures", man, "T_%s_%s_BaseColor.png" % (man, part))
            if not os.path.exists(path) or pal.get(key) is None:
                continue
            px = lin(np.asarray(Image.open(path).convert("RGB"), float).reshape(-1, 3) / 255.0)
            px = px[px.max(1) > lin(np.array(3 / 255.0))]            # not the gutter
            if part == "Hair":
                Y = px @ np.array([0.2126, 0.7152, 0.0722])
                px = px[Y <= np.percentile(Y, 25)]
            got = np.median(px, axis=0)
            want = np.asarray(pal[key], float)[:3]
            if sabotage == "baked" and kind == "brawler" and part == "Tee":
                want = want * 1.25
            de = float(np.linalg.norm(_lab(got) - _lab(want)))
            limit = HAIR_DE if part == "Hair" else BAKED_DE
            rows.append((man, part, de))
            if de > limit:
                miss.append("%s's %s bakes %.1f off its colour (dE, at most %.1f)" % (man, part, de, limit))
    return miss, rows


def main():
    if "--baked" in sys.argv:
        if "--bite" in sys.argv:
            ok, _ = check_baked()
            m, _ = check_baked("baked")
            print("  baked  %s" % (("caught: " + m[0]) if (m and not ok) else "NOT caught"))
            sys.exit(0 if m and not ok else 1)
        miss, rows = check_baked()
        for man, part, de in rows:
            print("  %-8s %-6s dE %.2f" % (man, part, de))
        for m in miss:
            print("MISS " + m)
        print("baked colours: %d maps, %s" % (len(rows), "every one true" if not miss else "%d off" % len(miss)))
        sys.exit(1 if miss else 0)
    if "--bite" in sys.argv:
        miss, _ = check()
        if miss:
            print("the unbroken copies fail, so no sabotage can be counted: %s" % miss[0])
            sys.exit(1)
        caught = 0
        for b in ("kit", "world", "souq", "row"):
            m, _ = check(b)
            caught += bool(m)
            print("  %-6s %s" % (b, ("caught: " + m[0]) if m else "NOT caught"))
        print("%d of 4 sabotages caught" % caught)
        sys.exit(0 if caught == 4 else 1)
    miss, seen = check()
    for m in miss:
        print("MISS " + m)
    print("data colours: %d copies of the browser's colours, %s" % (seen, "every one the data's" if not miss else "%d off" % len(miss)))
    sys.exit(1 if miss else 0)


if __name__ == "__main__":
    main()
