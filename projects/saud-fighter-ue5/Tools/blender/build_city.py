"""
The open world's seven city districts, as real 3D (2026-10-03, Riyadh).

Asked as "make the game full 3d map not 2d", settled with the author as the
Unreal build and "a richer 3D world": real 3D buildings, height and detail.
The souq (build_souq.py) and the stone island (build_island.py) were already
modelled; the other seven districts of L_AlHalqa_World -- the gym, the fish
market, the towers, the marina, the highway, the desert camp and the two
arenas -- were engine cubes and cylinders, one per plot, in their theme's
colour.

WHAT THIS BUILDS. Nothing is moved. build_world.plan() still decides every
plot -- where, how big, which way, what kind -- and every check it holds
the world to still holds, because every piece built here stands inside its
own plot's box (check() below). What changes is what stands on a plot: a
tower block is floors and slabs, a window grid (some lit), balconies, a
parapet, water tanks and plant on the roof; a high-rise a glass curtain on
a mullion grid with a crown and a mast; a gym hall brick with pilasters, a
roller door, high windows and a sawtooth roof; a fish shed posts and a
pitched iron roof over crates; a dock crane a lattice tower, a cab and a
jib; and so on for all 21 kinds the seven themes use (KINDS).

HOW. Every builder is pure Python: it returns primitives -- boxes, prisms,
cylinders, rocks, mounds -- in the plot's own frame, centimetres, and
check() runs on those without Blender. Inside Blender (`--build`), each
district's primitives are merged, by sector (SECTORS round its middle, so
the engine can cull them), into one static mesh per sector with a material
slot per surface, baked with the souq's procedural materials (its
weathering, its ink floor) and written as Content/Models/City/
SM_City_<Stage>_<k>.fbx with Content/Textures/City/, plus a manifest
(City_placement.json). build_world.py, in the editor, places each sector
mesh at its district's middle and turns the old cubes into invisible
collision: the game still collides with exactly what it did.

    python3 Tools/blender/build_city.py --check       the plan's checks (no Blender)
    python3 Tools/blender/build_city.py --bite        each check broken once
    python3 Tools/blender/build_city.py --build [--fast]   meshes, materials, FBX, scenes/City.blend
    python3 Tools/blender/build_city.py --render [--samples 32]   each district through the anime look

Unverified, like the rest of the editor half: no engine has imported a
sector mesh. The colours are Unreal-only (the browser draws no buildings
like these) and go through the souq's one weathering, held at the ink floor.
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(PROJECT, "Tools", "levels"))

import build_souq as BS   # noqa: E402
import build_world as BW  # noqa: E402

MODELS = os.path.join(PROJECT, "Content", "Models", "City")
TEXTURES = os.path.join(PROJECT, "Content", "Textures", "City")
RENDERS = os.path.join(PROJECT, "Docs", "renders")
SECTORS = 8
SLACK_CM = 2.0                  # a piece may stand this far outside its plot (rounding)
FLOOR_CM = 320.0                # one storey
BAY_CM = 300.0                  # one window bay
LIT_SHARE = (0.12, 0.40)        # of a block's windows, how many burn at night

# ------------------------------------------------------------- the surfaces
# The city's materials, the souq's material kinds over Unreal-only colours
# (the browser draws no such buildings), weathered by build_souq._worn and
# held at the ink floor like every other surface in the world.
CITY = {
    "M_City_Concrete":  ("plaster", dict(hex=("#8d8a83", "#6f6c66"), soot=True)),
    "M_City_Brick":     ("brick", dict(hex=("#7a3e2b", "#5e2f22", "#8a8378"), soot=True)),
    "M_City_Plaster":   ("plaster", dict(hex=("#b9b6ac", "#9c988c"), soot=True)),
    "M_City_Steel":     ("iron", dict(hex=("#4f5660", "#7a4a2a"))),
    "M_City_Corrugated": ("iron", dict(hex=("#5d7476", "#7a4a2a"))),
    "M_City_Glass":     ("window", dict(hex=("#1d2a3d", "#26364c"))),
    "M_City_Lit":       ("lit", dict(hex=("#ffcf8a",))),
    "M_City_Canvas":    ("cloth0", dict(hex=("#2c2622",))),
    "M_City_Stone":     ("mud", dict(hex=("#8b7a63", "#6c5d4b"), soot=False)),
    "M_City_Sand":      ("sand", dict(hex=(BW.THEME_GROUND["Desert"][0], BW.THEME_GROUND["Desert"][1], "#d1b386", "#7c6342"))),
    "M_City_Seat":      ("plaster", dict(hex=("#3f4f73", "#34425f"), soot=False)),
    "M_City_Lamp":      ("lamp", dict(hex=("#fff2d6",))),
    "M_City_Wood":      ("wood", dict(hex=("#6b4f36", "#4e3826"))),
}
MATS = tuple(CITY)

_souq_tones = BS.tones


def city_tones(name):
    """build_souq.tones, with what the souq's material kinds read and only
    its own rows carry: a mortar (the third colour, or the souq's MORTAR
    of the second) and a soot (the souq's SOOT dark of the first)."""
    out = _souq_tones(name)
    if name in CITY:
        cols = BS.palette(name)
        out.setdefault("mortar", cols[2] if len(cols) > 2 else BS._toward(cols[min(1, len(cols) - 1)], BS.MORTAR))
        out.setdefault("soot", BS._toward(cols[0], BS.SOOT["dark"]))
    return out


BS.tones = city_tones
EMISSIVE = ("M_City_Lit", "M_City_Lamp")          # what burns at night: exempt from the floor


# ------------------------------------------------------------- primitives
def box(lx, ly, z0, w, d, h, m, yaw=0.0, batter=0.0):
    return dict(t="box", lx=lx, ly=ly, z0=z0, w=w, d=d, h=h, m=m, yaw=yaw, batter=batter)


def prism(lx, ly, z0, w, d, h, m, yaw=0.0, ridge=0.5):
    """A gable along local X: w along the ridge, d across, h to the ridge;
    `ridge` 0..1 where across the ridge stands (0.5 a gable, 1 a lean-to)."""
    return dict(t="prism", lx=lx, ly=ly, z0=z0, w=w, d=d, h=h, m=m, yaw=yaw, ridge=ridge)


def cyl(lx, ly, z0, r, h, m, r_top=None, segs=16):
    return dict(t="cyl", lx=lx, ly=ly, z0=z0, r=r, h=h, m=m, r_top=r if r_top is None else r_top, segs=segs)


def rock(lx, ly, z0, rx, ry, rz, m, seed):
    return dict(t="rock", lx=lx, ly=ly, z0=z0, rx=rx, ry=ry, rz=rz, m=m, seed=seed)


def mound(lx, ly, z0, rx, ry, h, m, yaw=0.0):
    return dict(t="mound", lx=lx, ly=ly, z0=z0, rx=rx, ry=ry, h=h, m=m, yaw=yaw)


def bar(a, b, r, m):
    """A thin straight member from point a to point b (x, y, z, local cm):
    a crane's lattice, a stay, a pole."""
    return dict(t="bar", a=a, b=b, r=r, m=m)


def h01(*k):
    return BW.hash01(int(sum((i + 1) * 7919 * v for i, v in enumerate(k))) % 2147483647)


# ------------------------------------------------------------- the kinds
# Each builder: (W, D, H, seed) in cm, the plot's own frame -- X along its
# width, Y along its depth, Z up from the ground, the middle at (0, 0) --
# and returns its primitives. `post` kinds get W = D = the post's diameter.

def _facade(W, D, H, floors_from, floor_h, wall, seed, lit=True, inset=8.0, sides=(0, 1, 2, 3), balcony=0.0):
    """A window grid on every side asked: per storey, per bay, a dark pane
    proud of the wall, some lit; slab bands between storeys."""
    out = []
    n_fl = int((H - floors_from) // floor_h)        # whole storeys only: none if there is no room for one
    for side in sides:
        along = W if side in (0, 2) else D
        n_bay = max(1, int(along // BAY_CM))
        bay = along / n_bay
        for f in range(n_fl):
            z = floors_from + f * floor_h
            out.append(_on_side(side, W, D, 0.0, along, 18.0, z - 10.0, 20.0, wall, proud=10.0))   # the slab band
            for b in range(n_bay):
                u = -along / 2 + bay * (b + 0.5)
                lit_here = lit and h01(seed, side, f, b) < 0.27
                m = "M_City_Lit" if lit_here else "M_City_Glass"
                out.append(_on_side(side, W, D, u, bay * 0.62, 6.0, z + 70.0, floor_h * 0.52, m, proud=3.0))
                if balcony and h01(seed, side, f, b, 9) < balcony and f > 0:
                    out.append(_on_side(side, W, D, u, bay * 0.8, 110.0, z, 14.0, wall, proud=110.0))
                    out.append(_on_side(side, W, D, u, bay * 0.8, 6.0, z + 14.0, 90.0, "M_City_Steel", proud=110.0))
    return out


def _on_side(side, W, D, u, length, depth, z0, h, m, proud):
    """A slab on one face of a W x D footprint: `u` along the face, standing
    `proud` out from the wall but never past the plot (it is cut back in
    by the same amount: the wall itself steps in)."""
    hw, hd = W / 2.0, D / 2.0
    off = -proud + depth / 2.0
    if side == 0:   return box(u, -hd - off, z0, length, depth, h, m)
    if side == 2:   return box(u, hd + off, z0, length, depth, h, m)
    if side == 1:   return box(hw + off, u, z0, depth, length, h, m)
    return box(-hw - off, u, z0, depth, length, h, m)


def k_block(W, D, H, s):
    """A tower block: the body stepped in to leave room for balconies, a
    window grid, slab bands, a parapet, water tanks and plant on the roof."""
    inset = 120.0
    bw, bd = W - 2 * inset, D - 2 * inset
    roof = H - 160.0
    out = [box(0, 0, 0, bw, bd, roof, "M_City_Concrete")]
    out += _facade(bw, bd, roof, 40.0, FLOOR_CM, "M_City_Concrete", s, balcony=0.35)
    out += [box(0, 0, roof, bw, bd, 110.0, "M_City_Concrete")]          # parapet ring as a cap
    out += [box(0, 0, roof + 110.0, bw - 60.0, bd - 60.0, 10.0, "M_City_Steel")]
    for i in range(2):
        out.append(cyl((i - 0.5) * bw * 0.4, bd * 0.15, roof + 120.0, 70.0, 40.0 if H < 300 else 150.0 - 110.0, "M_City_Steel"))
    out.append(box(-bw * 0.25, -bd * 0.2, roof + 120.0, 140.0, 90.0, 40.0, "M_City_Steel"))
    return out


def k_tower(W, D, H, s):
    """A high-rise: a glass curtain on a grid of mullions and spandrels, a
    stepped crown, a mast."""
    w, d = W * 0.86, D * 0.86
    crown = H * 0.90
    out = [box(0, 0, 0, w, d, crown, "M_City_Glass")]
    # spandrels every storey, mullions every bay, proud of the glass
    n_fl = int(crown // 360.0)
    for f in range(1, n_fl):
        out.append(box(0, 0, f * 360.0 - 12.0, w + 16.0, d + 16.0, 24.0, "M_City_Steel"))
    for side in range(4):
        along = w if side in (0, 2) else d
        n = max(2, int(along // 150.0))
        for k in range(1, n):
            u = -along / 2 + along * k / n
            out.append(_on_side(side, w + 16.0, d + 16.0, u, 10.0, 10.0, 0.0, crown, "M_City_Steel", proud=0.0))
    # lit floors, a few whole bands of them
    for f in range(1, n_fl):
        if h01(s, f) < 0.18:
            out.append(box(0, 0, f * 360.0 + 60.0, w + 4.0, d + 4.0, 200.0, "M_City_Lit"))
    out.append(box(0, 0, crown, w * 0.7, d * 0.7, (H - crown) * 0.55, "M_City_Concrete"))
    out.append(box(0, 0, crown + (H - crown) * 0.55, w * 0.4, d * 0.4, (H - crown) * 0.25, "M_City_Steel"))
    out.append(cyl(0, 0, crown + (H - crown) * 0.8, 12.0, (H - crown) * 0.2, "M_City_Steel", r_top=4.0, segs=8))
    return out


def k_hoarding(W, D, H, s):
    """A building site's hoarding: posts and long panels, a top rail."""
    out = []
    n = max(2, int(W // 240.0))
    for i in range(n + 1):
        out.append(box(-W / 2 + 6 + (W - 12) * i / n, 0, 0, 12.0, 12.0, H, "M_City_Wood"))
    for i in range(n):
        x = -W / 2 + (i + 0.5) * W / n
        out.append(box(x, D * 0.2, 10.0, W / n - 8.0, 4.0, H - 40.0, "M_City_Corrugated" if h01(s, i) < 0.5 else "M_City_Wood"))
    out.append(box(0, 0, H - 10.0, W, 10.0, 10.0, "M_City_Steel"))
    return out


def k_hall(W, D, H, s):
    """A gym hall: brick walls between pilasters, a roller door and a man
    door on the front (local -Y), a band of high windows, a sawtooth roof."""
    eaves = H * 0.72
    out = [box(0, 0, 0, W - 40.0, D - 40.0, eaves, "M_City_Brick")]
    n = max(2, int(W // 400.0))
    for i in range(n + 1):
        x = -W / 2 + 25 + (W - 50) * i / n
        out += [box(x, -D / 2 + 20, 0, 50.0, 40.0, eaves, "M_City_Brick"),
                box(x, D / 2 - 20, 0, 50.0, 40.0, eaves, "M_City_Brick")]
    out.append(_on_side(0, W - 40, D - 40, 0.0, min(420.0, W * 0.35), 12.0, 0.0, min(380.0, eaves * 0.7), "M_City_Corrugated", proud=12.0))
    out.append(_on_side(0, W - 40, D - 40, W * 0.3, 100.0, 8.0, 0.0, 220.0, "M_City_Steel", proud=8.0))
    for side in (0, 1, 2, 3):
        along = (W if side in (0, 2) else D) - 40
        k = max(2, int(along // 260.0))
        for i in range(k):
            u = -along / 2 + along * (i + 0.5) / k
            m = "M_City_Lit" if h01(s, side, i) < 0.22 else "M_City_Glass"
            out.append(_on_side(side, W - 40, D - 40, u, along / k * 0.7, 6.0, eaves - 170.0, 110.0, m, proud=4.0))
    teeth = max(2, int(D // 500.0))
    for i in range(teeth):
        y = -D / 2 + 20 + (D - 40) * (i + 0.5) / teeth
        out.append(prism(0, y, eaves, W - 40.0, (D - 40) / teeth, H - eaves, "M_City_Corrugated", yaw=0.0, ridge=1.0))
    return out


def k_chimney(W, D, H, s):
    """A works chimney: a tapering brick stack, steel bands, a cap."""
    r = W / 2.0
    out = [cyl(0, 0, 0, r, H - 40.0, "M_City_Brick", r_top=r * 0.7, segs=20)]
    for z in range(400, int(H - 200), 500):
        rr = r - (r - r * 0.7) * z / (H - 40)
        out.append(cyl(0, 0, float(z), rr + 4.0, 20.0, "M_City_Steel", segs=20))
    out.append(cyl(0, 0, H - 40.0, r * 0.74, 40.0, "M_City_Concrete", segs=20))
    return out


def k_wall(W, D, H, s):
    """A yard wall: brick between piers, a concrete coping."""
    out = [box(0, 0, 0, W, D * 0.6, H - 20.0, "M_City_Brick")]
    n = max(2, int(W // 300.0))
    for i in range(n + 1):
        out.append(box(-W / 2 + 25 + (W - 50) * i / n, 0, 0, 50.0, D, H - 20.0, "M_City_Brick"))
    out.append(box(0, 0, H - 20.0, W, D, 20.0, "M_City_Concrete"))
    return out


def k_shed(W, D, H, s):
    """A fish-market shed: posts, an open front, a back wall, a pitched
    corrugated roof, crates and a counter under it."""
    eaves = H * 0.68
    out = []
    for ix in (-1, 1):
        for iy in (-1, 1):
            out.append(box(ix * (W / 2 - 15), iy * (D / 2 - 15), 0, 20.0, 20.0, eaves, "M_City_Steel"))
    out.append(box(0, D / 2 - 15, 0, W - 30.0, 12.0, eaves, "M_City_Corrugated"))
    out.append(prism(0, 0, eaves, W, D, H - eaves, "M_City_Corrugated"))
    out.append(box(0, -D * 0.15, 0, W * 0.7, 70.0, 95.0, "M_City_Wood"))
    for i in range(3):
        if h01(s, i) < 0.7:
            out.append(box(-W * 0.35 + i * W * 0.3, D * 0.25, 0, 60.0, 50.0, 45.0 + 45.0 * h01(s, i, 2), "M_City_Wood"))
    return out


def k_crane(W, D, H, s):
    """A dock crane on its plot's post: four legs of a lattice tower, its
    braces, a cab, a jib out over the quay and a counterweight."""
    r = W / 2.0 - 10.0
    out = []
    corners = [(-r, -r), (r, -r), (r, r), (-r, r)]
    top = H * 0.78
    for x, y in corners:
        out.append(bar((x, y, 0.0), (x * 0.6, y * 0.6, top), 9.0, "M_City_Steel"))
    for k in range(6):
        z0, z1 = max(top * k / 6, 8.0), top * (k + 1) / 6     # the lowest brace clear of the ground
        f0, f1 = 1.0 - 0.4 * k / 6, 1.0 - 0.4 * (k + 1) / 6
        for i in range(4):
            a, b = corners[i], corners[(i + 1) % 4]
            out.append(bar((a[0] * f0, a[1] * f0, z0), (b[0] * f1, b[1] * f1, z1), 5.0, "M_City_Steel"))
    out.append(box(0, 0, top, r * 1.4, r * 1.4, 180.0, "M_City_Corrugated"))
    out.append(box(0, 0, top + 180.0, r * 1.5, r * 1.5, 12.0, "M_City_Steel"))
    span = r * 0.95
    out.append(bar((-span, 0.0, top + 200.0), (span, 0.0, top + 200.0), 14.0, "M_City_Steel"))
    out.append(bar((0.0, 0.0, H - 20.0), (span, 0.0, top + 200.0), 6.0, "M_City_Steel"))
    out.append(bar((0.0, 0.0, H - 20.0), (-span, 0.0, top + 200.0), 6.0, "M_City_Steel"))
    out.append(box(-span + 40.0, 0, top + 150.0, 70.0, 70.0, 60.0, "M_City_Concrete"))
    return out


def k_quay(W, D, H, s):
    """A quay edge: a concrete wall, a timber fender, bollards."""
    out = [box(0, 0, 0, W, D, H - 10.0, "M_City_Concrete"),
           box(0, 0, H - 10.0, W, D, 10.0, "M_City_Steel"),
           box(0, -D / 2 + 6, 20.0, W, 12.0, H * 0.5, "M_City_Wood")]
    for i in range(max(1, int(W // 450.0))):
        out.append(cyl(-W / 2 + 120 + i * 450.0, 0, H, 14.0, 0.0 + min(45.0, 0.0 + 45.0), "M_City_Steel", segs=10))
    return [p for p in out if p["t"] != "cyl" or abs(p["lx"]) < W / 2 - 14]


def k_front(W, D, H, s):
    """A marina front: a glazed ground floor behind piers, an awning, a
    plaster upper floor with windows, a sign band, a roof rail."""
    gf = min(380.0, H * 0.5)
    out = [box(0, 20, 0, W - 20.0, D - 60.0, H - 60.0, "M_City_Plaster")]
    n = max(2, int(W // 320.0))
    for i in range(n):
        x = -W / 2 + 10 + (W - 20) * (i + 0.5) / n
        m = "M_City_Lit" if h01(s, i) < 0.45 else "M_City_Glass"
        out.append(box(x, -D / 2 + 34, 20.0, (W - 20) / n * 0.8, 8.0, gf - 60.0, m))
    out.append(box(0, -D / 2 + 30, gf - 30.0, W - 20.0, 60.0, 50.0, "M_City_Steel"))     # the sign band
    out.append(box(0, -D / 2 + 30, gf - 70.0, W - 40.0, 60.0, 10.0, "M_City_Canvas"))   # the awning
    out += _facade(W - 20.0, D - 60.0, H - 60.0, gf + 20.0, FLOOR_CM, "M_City_Plaster", s, sides=(0,))
    out.append(box(0, 20, H - 60.0, W - 20.0, D - 60.0, 50.0, "M_City_Steel"))
    # the door, between two panes, and the plant on the roof
    out.append(box(W * 0.12, -D / 2 + 33, 0.0, 110.0, 10.0, min(230.0, gf - 70.0), "M_City_Steel"))
    out.append(box(-W * 0.2, D * 0.1, H - 10.0, min(140.0, W * 0.3), 80.0, 10.0, "M_City_Steel"))
    return out


def k_mast(W, D, H, s):
    """A yacht's mast standing on the quay: the stick, its spreaders, the
    stays to the deck, the boom."""
    out = [cyl(0, 0, 0, 9.0, H, "M_City_Steel", r_top=5.0, segs=10)]
    r = W / 2.0 - 4.0
    out.append(bar((-r * 0.7, 0.0, H * 0.62), (r * 0.7, 0.0, H * 0.62), 3.0, "M_City_Steel"))
    for x in (-r, r):
        out.append(bar((x, 0.0, 30.0), (0.0, 0.0, H - 10.0), 1.2, "M_City_Steel"))
    out.append(bar((0.0, 0.0, 180.0), (0.0, r, 190.0), 5.0, "M_City_Steel"))
    return out


def k_rail(W, D, H, s):
    """A quayside rail: posts, a top rail, two mid wires."""
    out = []
    n = max(2, int(W // 200.0))
    for i in range(n + 1):
        out.append(box(-W / 2 + 4 + (W - 8) * i / n, 0, 0, 8.0, 8.0, H, "M_City_Steel"))
    for z, t in ((H - 6.0, 6.0), (H * 0.6, 2.0), (H * 0.3, 2.0)):
        out.append(box(0, 0, z, W, t, t, "M_City_Steel"))
    return out


def k_wreck(W, D, H, s):
    """A burnt-out car on the highway: the shell, a caved cabin, no glass,
    the wheels gone to rims."""
    L, Wd = W, D * 0.55
    body = min(H * 0.55, 90.0)
    out = [box(0, 0, 25.0, L * 0.92, Wd, body - 25.0, "M_City_Steel"),
           box(-L * 0.05, 0, body, L * 0.45, Wd * 0.88, min(H - body, 60.0), "M_City_Steel", batter=8.0)]
    for ix in (-1, 1):
        for iy in (-1, 1):
            out.append(box(ix * L * 0.3, iy * (Wd / 2 - 6), 0, 50.0, 14.0, 40.0, "M_City_Steel"))
    return out


def k_pylon(W, D, H, s):
    """A transmission pylon: four legs tapering to a waist, cross-arms."""
    r = W / 2.0 - 6.0
    out = []
    corners = [(-r, -r), (r, -r), (r, r), (-r, r)]
    for x, y in corners:
        out.append(bar((x, y, 0.0), (x * 0.2, y * 0.2, H * 0.92), 6.0, "M_City_Steel"))
    for k in range(5):
        z = H * 0.92 * (k + 1) / 6
        f = 1.0 - 0.8 * (k + 1) / 6
        for i in range(4):
            a, b = corners[i], corners[(i + 1) % 4]
            out.append(bar((a[0] * f, a[1] * f, z), (b[0] * f, b[1] * f, z), 3.0, "M_City_Steel"))
    for z in (H * 0.7, H * 0.85):
        out.append(bar((-r, 0.0, z), (r, 0.0, z), 5.0, "M_City_Steel"))
    out.append(bar((0.0, 0.0, H * 0.92), (0.0, 0.0, H), 4.0, "M_City_Steel"))
    return out


def k_barrier(W, D, H, s):
    """A jersey barrier run: a wide foot, a tall stem, the joins."""
    out = []
    n = max(1, int(W // 300.0))
    for i in range(n):
        x = -W / 2 + (i + 0.5) * W / n
        out.append(box(x, 0, 0, W / n - 6.0, D, H * 0.25, "M_City_Concrete"))
        out.append(box(x, 0, H * 0.25, W / n - 6.0, D * 0.45, H * 0.75, "M_City_Concrete", batter=4.0))
    return out


def k_tent(W, D, H, s):
    """A Bedouin tent: poles, the ridge, a black canvas sloped to the
    ground at the back and open at the front, the guy ropes."""
    out = [prism(0, D * 0.05, 0.0, W * 0.94, D * 0.9, H * 0.96, "M_City_Canvas", ridge=0.42)]
    for i in range(3):
        out.append(cyl(-W * 0.35 + i * W * 0.35, -D * 0.05, 0.0, 5.0, H, "M_City_Wood", segs=8))
    out.append(box(0, -D * 0.05, H - 8.0, W * 0.8, 8.0, 8.0, "M_City_Wood"))
    return out


def k_rock(W, D, H, s):
    """A desert outcrop: two or three weathered stones."""
    # squat, as a weathered outcrop is: no taller than it is wide
    H = min(H, 0.8 * min(W, D))
    out = [rock(0, 0, 0.0, W * 0.42, D * 0.38, H, "M_City_Stone", s)]
    if h01(s, 1) < 0.7:
        out.append(rock(W * 0.22, -D * 0.18, 0.0, W * 0.2, D * 0.18, H * 0.5, "M_City_Stone", s + 1))
    return out


def k_dune(W, D, H, s):
    """A drift of sand against the camp's edge."""
    return [mound(0, 0, 0.0, W / 2.0, D / 2.0, H, "M_City_Sand")]


def k_seating(W, D, H, s):
    """Arena stands: tiers stepping up away from the floor (local -Y),
    seat rows on each, a back wall, aisle stairs."""
    tiers = max(3, int(H // 60.0))
    out = []
    for t in range(tiers):
        y = -D / 2 + (t + 0.5) * D / tiers
        z = H * t / tiers
        out.append(box(0, y, 0.0, W, D / tiers, z + H / tiers * 0.6, "M_City_Concrete"))
        out.append(box(0, y - D / tiers * 0.15, z + H / tiers * 0.6, W - 20.0, D / tiers * 0.35,
                       min(30.0, 0.35 * H / tiers), "M_City_Seat"))
    out.append(box(0, D / 2 - 10, 0, W, 20.0, H, "M_City_Concrete"))
    out.append(box(0, 0, 0, 80.0, D, H * 0.55, "M_City_Concrete"))
    return out


def k_floodlight(W, D, H, s):
    """A floodlight mast: the column, a platform, the bank of lamps facing
    the floor (local -Y)."""
    r = W / 2.0
    out = [cyl(0, 0, 0, r * 0.35, H - 160.0, "M_City_Steel", r_top=r * 0.22, segs=12),
           box(0, 0, H - 170.0, r * 1.6, r * 1.2, 12.0, "M_City_Steel"),
           box(0, -r * 0.1, H - 160.0, r * 1.7, 30.0, 150.0, "M_City_Steel")]
    for i in range(3):
        for j in range(2):
            out.append(box(-r * 0.55 + i * r * 0.55, -r * 0.1 - 18.0, H - 140.0 + j * 65.0, r * 0.45, 8.0, 50.0, "M_City_Lamp"))
    return out


def k_bowl(W, D, H, s):
    """A segment of the arena's bowl: an outer wall with ribs, the top
    tier's lip, a lit band of the concourse."""
    out = [box(0, 0, 0, W, D * 0.5, H - 40.0, "M_City_Concrete")]
    n = max(2, int(W // 300.0))
    for i in range(n + 1):
        out.append(box(-W / 2 + 20 + (W - 40) * i / n, 0, 0, 40.0, D, H - 40.0, "M_City_Concrete"))
    out.append(box(0, 0, H - 40.0, W, D, 40.0, "M_City_Steel"))
    out.append(box(0, -D * 0.25 - 2.0, H * 0.45, W - 40.0, 4.0, 40.0, "M_City_Lit"))
    return out


KINDS = dict(block=k_block, tower=k_tower, hoarding=k_hoarding, hall=k_hall, chimney=k_chimney, wall=k_wall,
             shed=k_shed, crane=k_crane, quay=k_quay, front=k_front, mast=k_mast, rail=k_rail,
             wreck=k_wreck, pylon=k_pylon, barrier=k_barrier, tent=k_tent, rock=k_rock, dune=k_dune,
             seating=k_seating, floodlight=k_floodlight, bowl=k_bowl)
THEMES = ("Gym", "Fishmarket", "Towers", "Marina", "Highway", "Desert", "Arena")
# the least each kind is made of: one box is a cube, which is what this replaces
DETAIL = dict(block=16, tower=20, hoarding=6, hall=14, chimney=3, wall=4, shed=7, crane=20, quay=3, front=8,
              mast=4, rail=5, wreck=5, pylon=20, barrier=2, tent=4, rock=1, dune=1, seating=8, floodlight=6, bowl=4)


# ------------------------------------------------------------- the plan
_SAB = set()


def pieces_of(row):
    """A plot's primitives, in its own frame (cm)."""
    post = row["shape"] == "post"
    W, D, H = (row["sx"], row["sx"], row["sz"]) if post else (row["sx"], row["sy"], row["sz"])
    s = int(abs(row["x"]) * 3 + abs(row["y"]) * 7) % 100003
    out = KINDS[row["kind"]](W, D, H, s)
    if "one_box" in _SAB:
        out = [box(0, 0, 0, W, D, H, out[0]["m"])]
    if "overhang" in _SAB and row["kind"] == "block":
        out.append(box(W * 0.6, 0, 0, W * 0.5, D, H * 0.5, "M_City_Concrete"))
    if "sunk" in _SAB and row["kind"] == "hall":
        out = [dict(p, z0=p["z0"] - 120.0) if "z0" in p else p for p in out]
    if "floating" in _SAB and row["kind"] == "shed":
        out = [dict(p, z0=p["z0"] + 80.0) if "z0" in p else p for p in out]
    if "unknown_mat" in _SAB and row["kind"] == "tower":
        out.append(box(0, 0, 0, 10, 10, 10, "M_City_Gold"))
    if "dark_city" in _SAB:
        out = [dict(p, m="M_City_Glass") if p["m"] == "M_City_Lit" else p for p in out]
    return out


def _extent(p):
    """A primitive's local bounds: (x0, x1, y0, y1, z0, z1)."""
    t = p["t"]
    if t == "bar":
        # a cylinder round the line a-b: its radius reaches out square to
        # the axis, so along an axis it reaches r * sqrt(1 - (that axis's
        # share of the line)^2) -- nothing below the foot of an upright leg
        (ax, ay, az), (bx, by, bz), r = p["a"], p["b"], p["r"]
        L = max(math.dist(p["a"], p["b"]), 1e-9)
        ex, ey, ez = (r * math.sqrt(max(0.0, 1.0 - (q / L) ** 2)) for q in (bx - ax, by - ay, bz - az))
        return min(ax, bx) - ex, max(ax, bx) + ex, min(ay, by) - ey, max(ay, by) + ey, min(az, bz) - ez, max(az, bz) + ez
    if t == "cyl":
        R = max(p["r"], p["r_top"])
        return p["lx"] - R, p["lx"] + R, p["ly"] - R, p["ly"] + R, p["z0"], p["z0"] + p["h"]
    if t in ("rock", "mound"):
        rx, ry = p["rx"], p["ry"]
        hz = p["rz"] if t == "rock" else p["h"]
        if t == "mound" and p.get("yaw"):
            rx = ry = max(rx, ry)
        return p["lx"] - rx, p["lx"] + rx, p["ly"] - ry, p["ly"] + ry, p["z0"], p["z0"] + hz
    a = math.radians(p.get("yaw", 0.0))
    c, s = abs(math.cos(a)), abs(math.sin(a))
    hw = p["w"] / 2 * c + p["d"] / 2 * s
    hd = p["w"] / 2 * s + p["d"] / 2 * c
    return p["lx"] - hw, p["lx"] + hw, p["ly"] - hd, p["ly"] + hd, p["z0"], p["z0"] + p["h"]


def city_rows(P):
    """The plots this builds on: every solid piece of the seven city
    districts whose kind is a building's, with its district."""
    rows = []
    for i, p in enumerate(P["scenery"]):
        d = p.get("district")
        if d is None or not p.get("solid") or p["kind"] not in KINDS:
            continue
        D = P["districts"][d]
        if D["stage"]["Theme"] not in THEMES:
            continue
        rows.append(dict(p, row=i))
    return rows


def plan():
    stages, world = BW.load()
    P = BW.plan(stages, world)
    rows = city_rows(P)
    out = dict(P=P, rows=rows, districts={})
    for r in rows:
        D = P["districts"][r["district"]]
        key = D["stage"]["Name"]
        dd = out["districts"].setdefault(key, dict(name=key, theme=D["stage"]["Theme"], ox=D["ox"], oy=D["oy"],
                                                    extent=D["extent"], rows=[]))
        # its sector round the district's middle
        ang = math.atan2(r["y"] - D["oy"], r["x"] - D["ox"]) % (2 * math.pi)
        r["sector"] = int(ang / (2 * math.pi) * SECTORS) % SECTORS
        r["pieces"] = pieces_of(r)
        dd["rows"].append(r)
    return out


# ------------------------------------------------------------- the checks
def check(C=None):
    """What a city plot must be: built of its kind's pieces, inside its own
    box, on the ground, of known surfaces, more than a cube, lit in part at
    night; and every kind the seven themes use has a builder."""
    C = C or plan()
    fails = []
    used = {(D["stage"]["Theme"], p["kind"]) for p in C["P"]["scenery"]
            if p.get("district") is not None and p.get("solid")
            for D in [C["P"]["districts"][p["district"]]]}
    for th in THEMES:
        v = BW.VOCAB[th]
        for role in ("block", "tall", "rim"):
            k = v[role]
            if (th, k) in used and k not in KINDS:
                fails.append("%s's %s (%s) has no builder: it would stay a cube" % (th, role, k))
    if not C["rows"]:
        fails.append("no city plots found")
    lit_rooms = glass = 0
    for r in C["rows"]:
        post = r["shape"] == "post"
        W, D, H = (r["sx"], r["sx"], r["sz"]) if post else (r["sx"], r["sy"], r["sz"])
        ps = r["pieces"]
        if len(ps) < DETAIL[r["kind"]]:
            fails.append("a %s is %d pieces, under the %d that make it more than a cube" % (r["kind"], len(ps), DETAIL[r["kind"]]))
        lo_z = min(_extent(p)[4] for p in ps)
        if abs(lo_z) > SLACK_CM:
            fails.append("a %s stands %s the ground by %.0f cm" % (r["kind"], "under" if lo_z < 0 else "over", abs(lo_z)))
        for p in ps:
            x0, x1, y0, y1, z0, z1 = _extent(p)
            if post:
                if max(math.hypot(x, y) for x in (x0, x1) for y in (y0, y1)) > W / 2 * math.sqrt(2) + SLACK_CM:
                    fails.append("a %s reaches out of its post's plot" % r["kind"])
                    break
            elif x0 < -W / 2 - SLACK_CM or x1 > W / 2 + SLACK_CM or y0 < -D / 2 - SLACK_CM or y1 > D / 2 + SLACK_CM:
                fails.append("a %s's piece stands out of its plot (%.0f..%.0f x %.0f..%.0f in %.0f x %.0f)"
                             % (r["kind"], x0, x1, y0, y1, W, D))
                break
            if z0 < -SLACK_CM or z1 > H + SLACK_CM:
                fails.append("a %s's piece is taller than its plot (%.0f..%.0f of %.0f)" % (r["kind"], z0, z1, H))
                break
            if p["m"] not in CITY:
                fails.append("a %s is made of %s, which is no city surface" % (r["kind"], p["m"]))
                break
        if r["kind"] in ("block", "hall", "front", "tower"):
            lit_rooms += sum(p["m"] == "M_City_Lit" for p in ps)
            glass += sum(p["m"] in ("M_City_Lit", "M_City_Glass") for p in ps)
    share = lit_rooms / max(glass, 1)
    if not (LIT_SHARE[0] <= share <= LIT_SHARE[1]):
        fails.append("%.2f of the windows burn at night, outside %.2f-%.2f" % (share, LIT_SHARE[0], LIT_SHARE[1]))
    # every surface's colours held at the ink floor (the emissive excepted)
    floor = BS.ink_floor()
    for name, (kind, row) in CITY.items():
        if name in EMISSIVE:
            continue
        for c in [BS._worn(h) for h in row["hex"]]:
            if BS._luma(c) < floor - 1e-6:
                fails.append("%s weathers to %.4f, under the ink floor %.3f" % (name, BS._luma(c), floor))
    # the built meshes are this plan's: a world re-planned since the last
    # --build would leave buildings on plots that have moved
    man = os.path.join(MODELS, "City_placement.json")
    if os.path.exists(man) and "skip_manifest" not in _SAB:
        built = {(c["row"], c["kind"]) for c in json.load(open(man))["plots"]}
        planned = {(r["row"], r["kind"]) for r in C["rows"]}
        if "moved_plot" in _SAB:
            planned = set(list(planned)[1:]) | {(10 ** 6, "block")}
        if built != planned:
            fails.append("Content/Models/City was built for another plan (%d plots differ): run --build"
                         % len(built ^ planned))
    if "dark_floor" in _SAB:
        fails += [] if BS._luma(BS._worn("#000000")) >= floor else ["(sabotage) a black surface"]
    return fails


def bite():
    cases = ["one_box", "overhang", "sunk", "floating", "unknown_mat", "dark_city", "no_builder"]
    if os.path.exists(os.path.join(MODELS, "City_placement.json")):
        cases.append("moved_plot")
    caught = 0
    for b in cases:
        _SAB.clear()
        _SAB.add(b)
        keep = KINDS.pop("crane") if b == "no_builder" else None
        try:
            f = check()
        finally:
            if keep:
                KINDS["crane"] = keep
            _SAB.clear()
        caught += bool(f)
        print("  %-12s %s" % (b, ("caught: " + f[0]) if f else "NOT caught"))
    clean = check()
    print("%d of %d sabotages caught; the clean plan %s" % (caught, len(cases), "passes" if not clean else "FAILS: " + clean[0]))
    return caught == len(cases) and not clean


def describe(C):
    n = sum(len(r["pieces"]) for r in C["rows"])
    print("city: %d plots in %d districts, %d pieces" % (len(C["rows"]), len(C["districts"]), n))
    from collections import Counter
    for name, d in sorted(C["districts"].items()):
        k = Counter(r["kind"] for r in d["rows"])
        print("  %-18s %-10s %s" % (name, d["theme"], ", ".join("%s %d" % kv for kv in sorted(k.items()))))


# ------------------------------------------------------------- Blender
class City(BS.Souq):
    """The souq's Blender half -- its materials, its bake, its export -- with
    the city's own surfaces and meshes."""

    def __init__(self, C, fast=False):
        import bpy
        self.bpy = bpy; self.C = C; self.fast = fast
        self.models, self.textures, self.renders = MODELS, TEXTURES, RENDERS
        for d in (self.models, self.textures, self.renders): os.makedirs(d, exist_ok=True)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene; sc.unit_settings.system = "METRIC"; sc.unit_settings.length_unit = "METERS"
        self.mats = {}; self.kinds = {}; self.placed = []; self.baked_floor = {}
        for name, (kind, row) in CITY.items():
            BS.PALETTE[name] = row
        self.P = dict(street_mesh="")

    def material(self, name, kind):
        bpy = self.bpy
        if kind in ("window", "lit", "lamp"):
            mat = bpy.data.materials.new(name); mat.use_nodes = True
            b = mat.node_tree.nodes["Principled BSDF"]
            cols = BS.palette(name)
            if kind == "window":
                # dark glass: the souq's weathering on a navy, glossy
                b.inputs["Base Color"].default_value = cols[0]; b.inputs["Roughness"].default_value = 0.12
                b.inputs["Metallic"].default_value = 0.3
            else:
                c = BS._lin(BS._hex(CITY[name][1]["hex"][0]))
                b.inputs["Base Color"].default_value = c; b.inputs["Roughness"].default_value = 0.4
                if "Emission Color" in b.inputs:
                    b.inputs["Emission Color"].default_value = c
                    b.inputs["Emission Strength"].default_value = 4.0 if kind == "lit" else 12.0
            self.mats[name] = mat
            return mat
        return BS.Souq.material(self, name, kind)

    BAKE_EXEMPT = EMISSIVE

    def _prim(self, bm, p, ox, oy, yaw, mi):
        """One primitive into bm, at the plot (ox, oy, yaw), metres."""
        import bmesh
        from mathutils import Matrix, Vector
        before = set(bm.verts)
        m = mi[p["m"]]
        t = p["t"]
        cm = 0.01
        if t == "box":
            self._box(bm, 0, 0, p["z0"] * cm, p["w"] * cm, p["d"] * cm, p["h"] * cm, m, batter=p["batter"] * cm, yaw=p["yaw"])
            lx, ly = p["lx"], p["ly"]
        elif t == "prism":
            w, d, h = p["w"] * cm, p["d"] * cm, p["h"] * cm
            z0, rk = p["z0"] * cm, p["ridge"]
            yr = -d / 2 + d * rk
            vs = [bm.verts.new(v) for v in ((-w / 2, -d / 2, z0), (-w / 2, d / 2, z0), (-w / 2, yr, z0 + h),
                                            (w / 2, -d / 2, z0), (w / 2, d / 2, z0), (w / 2, yr, z0 + h))]
            for f in ((0, 2, 1), (3, 4, 5), (0, 3, 5, 2), (1, 2, 5, 4), (0, 1, 4, 3)):
                bm.faces.new([vs[i] for i in f]).material_index = m
            lx, ly = p["lx"], p["ly"]
            if p["yaw"]:
                bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(p["yaw"]), 3, "Z"))
        elif t == "cyl":
            self._cyl(bm, 0, 0, p["z0"] * cm, p["r"] * cm, p["h"] * cm, m, segs=p["segs"], r_top=p["r_top"] * cm)
            lx, ly = p["lx"], p["ly"]
        elif t == "bar":
            a, b = Vector(p["a"]) * cm, Vector(p["b"]) * cm
            L = (b - a).length
            self._cyl(bm, 0, 0, 0.0, p["r"] * cm, L, m, segs=6)
            new = [v for v in bm.verts if v not in before]
            rot = Vector((0, 0, 1)).rotation_difference((b - a).normalized()).to_matrix().to_4x4()
            bmesh.ops.transform(bm, matrix=Matrix.Translation(a) @ rot, verts=new)
            lx = ly = 0.0
        elif t in ("rock", "mound"):
            segs, rings = (10, 6) if t == "rock" else (16, 6)
            rx, ry = p["rx"] * cm, p["ry"] * cm
            hz = (p["rz"] if t == "rock" else p["h"]) * cm
            self._dome(bm, 0, 0, p["z0"] * cm, 1.0, m, segs=segs, rings=rings)
            new = [v for v in bm.verts if v not in before]
            for v in new:
                k = 1.0
                if t == "rock":
                    k = 0.78 + 0.22 * BW.hash01(int((v.co.x * 97 + v.co.y * 57 + v.co.z * 31 + p["seed"]) * 1000) % 99991)
                v.co.x *= rx * k; v.co.y *= ry * k
                v.co.z = p["z0"] * cm + (v.co.z - p["z0"] * cm) * hz
            lx, ly = p["lx"], p["ly"]
        else:
            raise KeyError(t)
        new = [v for v in bm.verts if v not in before]
        M = (Matrix.Translation((ox, oy, 0.0)) @ Matrix.Rotation(math.radians(yaw), 4, "Z")
             @ Matrix.Translation((lx * cm, ly * cm, 0.0)))
        bmesh.ops.transform(bm, matrix=M, verts=new)

    def build_sectors(self):
        import bmesh
        for name, (kind, _) in CITY.items():
            self.material(name, kind)
        out = {}
        for dname, d in sorted(self.C["districts"].items()):
            for k in range(SECTORS):
                rows = [r for r in d["rows"] if r["sector"] == k]
                if not rows:
                    continue
                used = sorted({p["m"] for r in rows for p in r["pieces"]})
                mi = {m: i for i, m in enumerate(used)}
                bm = bmesh.new()
                for r in rows:
                    for p in r["pieces"]:
                        self._prim(bm, p, (r["x"] - d["ox"]) / 100.0, (r["y"] - d["oy"]) / 100.0, r["yaw"], mi)
                bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
                mesh_name = "SM_City_%s_%d" % (dname, k)
                o = self._new(mesh_name, bm, [self.mats[m] for m in used])
                self.kinds[mesh_name] = o
                out[mesh_name] = dict(district=dname, sector=k, plots=len(rows), tris=sum(len(f.vertices) - 2 for f in o.data.polygons),
                                      materials=used)
        return out

    def export_all(self, sectors):
        written = {}
        for name in self.kinds:
            o = self.kinds[name]
            written[name] = os.path.getsize(self.export_kind(name))
            o.hide_viewport = False; o.hide_render = False
        # one read back whole: its height and vertex count
        bpy = self.bpy
        name = max(sectors, key=lambda n: sectors[n]["tris"])
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=os.path.join(self.models, name + ".fbx"))
        back = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
        assert len(back) == 1, "%s read back as %d meshes" % (name, len(back))
        got = len(back[0].data.vertices); want = len(self.kinds[name].data.vertices)
        zs = [v.co.z for v in self.kinds[name].data.vertices]
        for o in back: bpy.data.objects.remove(o, do_unlink=True)
        assert got == want, "%s reads back with %d vertices, not %d" % (name, got, want)
        man = dict(units="centimetres, Z up; each sector mesh's origin is its district's middle",
                   districts={k: dict(theme=d["theme"], x=d["ox"], y=d["oy"], extent=d["extent"])
                              for k, d in self.C["districts"].items()},
                   sectors=sectors, plots=[dict(row=r["row"], kind=r["kind"], district=r["district"], sector=r["sector"])
                                          for r in self.C["rows"]],
                   readback=dict(mesh=name, verts=got, height_m=max(zs) - min(zs)))
        with open(os.path.join(self.models, "City_placement.json"), "w", encoding="utf-8") as fh:
            json.dump(man, fh, indent=1)
        return written

    def render_district(self, dname, out, cam_from=(-0.62, -0.55, 0.16), aim=(0.0, 0.0, 0.05), lens=28, res=(1600, 900)):
        """A plain Cycles view of one district's sectors, under the moon and
        a sky -- what the anime preview reads its passes from."""
        bpy = self.bpy
        d = self.C["districts"][dname]
        for name, o in self.kinds.items():
            vis = name.startswith("SM_City_%s_" % dname)
            o.hide_render = not vis; o.hide_viewport = not vis
            o.location = (0, 0, 0)
        E = d["extent"] / 100.0
        if "CityGround" not in bpy.data.objects:
            bpy.ops.mesh.primitive_circle_add(vertices=64, radius=1.0, fill_type="NGON")
            g = bpy.context.object; g.name = "CityGround"
            g.data.materials.append(self.mats.get("M_City_Concrete"))
        g = bpy.data.objects["CityGround"]; g.scale = (E, E, 1.0)
        if dname.startswith("Mukhayyam"):
            g.data.materials[0] = self.mats["M_City_Sand"]
        else:
            g.data.materials[0] = self.mats["M_City_Concrete"]
        sc = bpy.context.scene
        cam = bpy.data.objects.get("CityCam")
        if cam is None:
            cam = bpy.data.objects.new("CityCam", bpy.data.cameras.new("CityCam")); sc.collection.objects.link(cam)
        cam.data.lens = lens
        from mathutils import Vector
        cam.location = Vector(cam_from) * E
        cam.rotation_euler = (Vector(aim) * E - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.clip_end = E * 4
        sc.camera = cam
        if "CityMoon" not in bpy.data.objects:
            moon = bpy.data.objects.new("CityMoon", bpy.data.lights.new("CityMoon", "SUN")); sc.collection.objects.link(moon)
            moon.data.energy = 1.2; moon.data.color = (0.58, 0.68, 0.95); moon.data.angle = math.radians(0.55)
            moon.rotation_euler = (math.radians(52), 0, math.radians(-125))
        if sc.world is None:
            sc.world = bpy.data.worlds.new("CityWorld")
        sc.world.use_nodes = True
        sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.02, 0.03, 0.06, 1)
        sc.world.node_tree.nodes["Background"].inputs[1].default_value = 0.3
        sc.render.engine = "CYCLES"; sc.cycles.samples = 16 if self.fast else 64
        sc.render.resolution_x, sc.render.resolution_y = res
        sc.render.filepath = out
        bpy.ops.render.render(write_still=True)
        return out


def render(samples=32, height=720):
    """Each district from the saved scene (scenes/City.blend), through the
    anime look (anime_preview.render_scene and look_from), and a sheet of
    all seven: Docs/renders/city-<District>-anime.png, city-districts.png."""
    import bpy
    import numpy as np
    from PIL import Image
    import anime_preview as AP
    import build_map_scenes as MS
    from mathutils import Vector
    bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, "scenes", "City.blend"))
    C = plan()
    sc = bpy.context.scene
    tiles = []
    for dname, d in sorted(C["districts"].items()):
        for o in bpy.data.objects:
            if o.name.startswith("SM_City_"):
                vis = o.name.startswith("SM_City_%s_" % dname)
                o.hide_render = not vis; o.hide_viewport = not vis
        E = d["extent"] / 100.0
        g = bpy.data.objects.get("CityGround")
        if g is None:
            bpy.ops.mesh.primitive_circle_add(vertices=96, radius=1.0, fill_type="NGON")
            g = bpy.context.object; g.name = "CityGround"
        g.scale = (E, E, 1.0)
        g.data.materials.clear()
        want = "M_City_Sand" if d["theme"] == "Desert" else "M_City_Concrete"
        # the baked material (the bake renames; Blender may have suffixed it)
        g.data.materials.append(next(m for m in bpy.data.materials
                                     if m.name.split(".")[0] == want and "procedural" not in m.name))
        cam = bpy.data.objects.get("CityCam") or bpy.data.objects.new("CityCam", bpy.data.cameras.new("CityCam"))
        if cam.name not in sc.collection.objects:
            sc.collection.objects.link(cam)
        # the district's biggest building, seen from the street side at a
        # man's height and a little over: where the eye goes first
        big = [r for r in d["rows"] if BW.ROLE_OF_KIND.get(r["kind"]) == "block"]
        sub = max(big, key=lambda r: r["sz"] * r["sx"] * r["sy"])
        sx_, sy_ = (sub["x"] - d["ox"]) / 100.0, (sub["y"] - d["oy"]) / 100.0
        to_mid = Vector((-sx_, -sy_, 0.0)).normalized()
        side = Vector((-to_mid.y, to_mid.x, 0.0))
        dist = max(14.0, 2.4 * max(sub["sx"], sub["sy"]) / 100.0, 0.9 * sub["sz"] / 100.0)
        cam.data.lens = 26
        cam.location = Vector((sx_, sy_, 0.0)) + to_mid * dist + side * dist * 0.45 + Vector((0, 0, 4.0))
        aim = Vector((sx_, sy_, 0.3 * sub["sz"] / 100.0))
        cam.rotation_euler = (aim - cam.location).to_track_quat("-Z", "Y").to_euler()
        # the night, the world's own (build_map_scenes): WORLD_RIG's moon --
        # its bearing, colour and disc -- the world preview's sky, and each of
        # the district's fires sized against that moon on open ground (4 pi I
        # E_moon, as the engine sizes its candela against the rig's lux) and
        # ended where spawn_night ends it. Until 2026-10-04 the moon here
        # stood 90 degrees off the rig's bearing, there was no sky, and the
        # fires were the souq's, sized for its 24-degree render moon.
        for o in [o for o in bpy.data.objects if o.get("night_fire")]:
            bpy.data.objects.remove(o, do_unlink=True)
        E_moon = MS.moon_ground(BW.WORLD_RIG)
        fire_pools = MS.attenuation_pools()[0]
        for i, p in enumerate(q for q in C["P"]["scenery"] if q.get("fire") and q["district"] is not None
                              and C["P"]["districts"][q["district"]]["stage"]["Name"] == dname):
            f = p["fire"]
            L = bpy.data.lights.new("Fire_%02d" % i, "POINT")
            L.energy = 4.0 * math.pi * f["I"] * E_moon
            L.shadow_soft_size = 0.15
            L.use_temperature = True; L.temperature = f["temp"]
            MS._engine_falloff(L, f["pool"] * fire_pools)
            o = bpy.data.objects.new("Fire_%02d" % i, L)
            o.location = ((p["x"] - d["ox"]) / 100.0, (p["y"] - d["oy"]) / 100.0, f["z"] / 100.0 + f["h"])
            o["night_fire"] = 1; sc.collection.objects.link(o)
        cam.data.clip_end = E * 4
        sc.camera = cam
        for o in [o for o in bpy.data.objects if o.type == "LIGHT" and o.data.type == "SUN"]:
            bpy.data.objects.remove(o, do_unlink=True)
        MS._sun("CityMoon", MS.rig_travel(BW.WORLD_RIG), BW.WORLD_RIG["sun"], MS.MOON_ENERGY, BW.WORLD_RIG["angle"])
        MS._sky(BS._lin(BS._hex(BS.MOON["sky"])), BS.MOON["sky_strength"])
        sc.render.resolution_x, sc.render.resolution_y = int(height * 16 / 9), height
        got, exposure = AP.render_scene(camera=cam, height=height, samples=samples)
        pic, m = AP.look_from(got, exposure)
        out = os.path.join(RENDERS, "city-%s-anime.png" % dname)
        Image.fromarray(pic).save(out)
        print("  %s (%s): %s, key %.3f (%s)" % (dname, d["theme"], out, m["key"], m["key_rule"]))
        tiles.append(np.asarray(Image.fromarray(pic).resize((640, 360))))
    while len(tiles) % 2:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[i:i + 2]) for i in range(0, len(tiles), 2)]
    sheet = os.path.join(RENDERS, "city-districts.png")
    Image.fromarray(np.vstack(rows)).save(sheet)
    print("city: %s" % sheet)


def build(fast=False):
    C = plan()
    fails = check(C)
    assert not fails, "the city plan fails its own checks: %s" % fails[0]
    city = City(C, fast=fast)
    sectors = city.build_sectors()
    city.bake_tiles()
    city.check_bake()
    written = city.export_all(sectors)
    scene = os.path.join(HERE, "scenes", "City.blend")
    city.bpy.ops.wm.save_as_mainfile(filepath=scene)
    tris = sum(s["tris"] for s in sectors.values())
    print("city: %d sector meshes, %d triangles, %d materials; %s" % (len(sectors), tris, len(city.mats), scene))
    return city


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if "--bite" in args:
        sys.exit(0 if bite() else 1)
    if "--render" in args:
        render(samples=int(args[args.index("--samples") + 1]) if "--samples" in args else 32)
        sys.exit(0)
    if "--build" in args:
        try:
            import bpy  # noqa: F401
        except ImportError:
            print("--build runs inside Blender's Python (bpy)")
            sys.exit(2)
        build(fast="--fast" in args)
        sys.exit(0)
    C = plan()
    describe(C)
    f = check(C)
    for m in f[:20]:
        print("MISS " + m)
    print("city plan: %s" % ("every plot built of its kind, inside its own box, on the ground" if not f else "%d broken" % len(f)))
    sys.exit(1 if f else 0)
