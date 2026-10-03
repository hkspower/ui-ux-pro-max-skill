#!/usr/bin/env python3
"""JAZIRAT AL-QIRUD -- the monkey island: its ground, as 4K tiling maps.

Asked 2026-10-02 with the island ("make large island full 4k"), settled as
both a 4 km island and 4K textures. build_monkey_island.py paints the
landscape with five layers -- Sand, Grass, Jungle, Rock, Mud -- and this
writes the surface each layer is drawn with: a colour, a normal and a
roughness map, 4096 x 4096, tiling, for every one of them.

    python3 island_surfaces.py               build, check, write, draw
    python3 island_surfaces.py --check       build and check only
    python3 island_surfaces.py --bite        break each rule once
    python3 island_surfaces.py --size 1024   a smaller tile (for a look)

WHAT EACH IS. A tile is 4 m of ground across, so a texel is just under a
millimetre: a grain of sand is a few texels and a leaf a hundred.
- Sand: dry and damp sand in patches, wind ripples, grains, broken shell.
- Grass: blades -- each one drawn, rooted, leaning, curved and tapering,
  green to straw at the tip, darker at the root -- in clumps over soil
  that shows through where they thin.
- Jungle: the floor under the trees, leaf litter: leaves of many sizes and
  ages lying over each other, each with a midrib and a dome, twigs over
  them, the soil in the gaps, the lower leaves in their shade.
- Rock: weathered stone, ridged at every scale, split by cracks, with
  lichen on its tops and moss in its hollows.
- Mud: the trail, trodden wet earth with stones pressed into it and water
  standing in its hollows (flat, dark and glossy).
Every one is drawn as a height in metres and a colour, the normal is the
height's own slope at the texel's real size, and everything a tile draws
wraps at its edges (lattice noise on a periodic lattice, every stamp laid
modulo the tile), so the tile has no seam.

THE COLOURS are Unreal-only -- the browser has no island -- natural
colours of each ground, taken through the world's own weathering curve
(build_souq._worn, the curve every colour of the open world takes), at the
world's chroma for sand, rock and mud and at the cloth chroma for the two
green layers, so the jungle still reads green under the navy night. Every
texel is held between the ink floor (build_souq.ink_hold, one 8-bit step
over the look's floor) and WEATHER["hi"], as the souq's materials are.

THE NORMALS are written the way Unreal reads a normal map by default:
DirectX, green pointing DOWN the image. (Blender bakes the other way; these
are not baked.) The importer settings are surfaces.py's, which claims the
files by their names (T_IslandGround_<Layer>_<Role>.png).

CHECKED, on the 8-bit maps as written, and --bite breaks each: every map
tiles (the step across its wrap no bigger than its steps inside); every
colour between the floor and the ceiling; the five layers' colours apart
from each other, the two green ones green; every normal unit length,
facing out, not flat and in Unreal's convention (tested on a bump); every
roughness inside its material's range, and the mud's water glossy; detail
at the millimetre and at the decimetre, not a flat colour; 4096 square.

NOT VERIFIED: no engine has imported these or drawn a landscape with them.
The landscape material that blends them is the level's job (the next part
of the island), not this file's.
"""

import argparse
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "Tools", "blender"))
import build_souq as S          # noqa: E402  (the world's weathering, the ink floor)

OUT = os.path.join(ROOT, "Content", "Textures", "IslandGround")
SHEET = os.path.join(ROOT, "Docs", "renders", "island-surfaces.png")
SIZE = 4096
TILE_M = 4.0                     # a tile is 4 m of ground across
LAYERS = ("Sand", "Grass", "Jungle", "Rock", "Mud")
SABOTAGE = set()

# Each layer's colours: Unreal-only hexes (the browser has no island), and
# the WEATHER chroma each takes.
PALETTE = {
    "Sand":   dict(chroma="chroma", hex=dict(dry="#c8b38a", damp="#9c8662", pale="#d6c49e", shell="#d8cbb0", dark="#5c544a")),
    "Grass":  dict(chroma="cloth_chroma", hex=dict(green="#4c6a2c", young="#6b8a3a", straw="#a09a5c", soil="#4a3a28")),
    "Jungle": dict(chroma="cloth_chroma", hex=dict(brown="#6a4a2a", tan="#8c6c40", dark="#3e3020", fresh="#40602a",
                                                   soil="#2e2418", twig="#4a3828")),
    "Rock":   dict(chroma="chroma", hex=dict(stone="#6c6860", dark="#4c4a46", pale="#8c877c", lichen="#8a9058", moss="#3c5228")),
    "Mud":    dict(chroma="chroma", hex=dict(mud="#5a4630", wet="#3a2c1e", dry="#76603e", stone="#6e665a", water="#2a2a26")),
}
# roughness: each material's range, and the mud's standing water
ROUGH = dict(Sand=(0.70, 0.97), Grass=(0.55, 0.92), Jungle=(0.45, 0.90), Rock=(0.62, 0.95), Mud=(0.03, 0.85))
WATER_ROUGH = 0.05
# how much of each height's slope the normal takes: a blade or a leaf edge
# is a cliff at a millimetre, and a map of cliffs shades as noise, so the
# litter and the grass are laid back (their mean normal must face out: a
# normal map averages to straight out, surfaces.py holds it, NORMAL_MEAN_Z)
NORMAL_GAIN = dict(Sand=1.0, Grass=0.35, Jungle=0.5, Rock=1.0, Mud=1.0)
# and the height is read over this much ground (metres) before its slope is
# taken, so a blade's edge is a slope a millimetre or two wide whatever the
# texel, and the map is the same at 1K and 4K
NORMAL_BLUR_M = dict(Sand=0.0, Grass=0.003, Jungle=0.0015, Rock=0.0, Mud=0.0)
NORMAL_MEAN_Z = 0.80
NORMAL_Z_MIN = 0.25             # no texel steeper than this (a blade's edge is a cliff at a millimetre)


def weathered(layer):
    """{name: linear RGB} for a layer: each hex through the world's curve."""
    row = PALETTE[layer]
    k = S.WEATHER[row["chroma"]]
    return {n: np.array(S._worn(h, k)[:3], np.float32) for n, h in row["hex"].items()}


# ================================================================ noise

class Tile:
    """One square tile, n texels across TILE_M metres, every draw periodic."""

    def __init__(self, n, seed):
        self.n = n
        self.px_m = n / TILE_M
        self.rng = np.random.default_rng(seed)

    def cells(self, feature_m):
        """How many lattice cells across the tile for features feature_m big."""
        return max(1, int(round(TILE_M / feature_m)))

    def noise(self, feature_m):
        """Value noise, 0..1, periodic over the tile, cells feature_m apart."""
        n, p = self.n, self.cells(feature_m)
        if p >= n:
            return self.rng.random((n, n), dtype=np.float32)
        L = self.rng.random((p, p), dtype=np.float32)
        u = np.arange(n, dtype=np.float32) * (p / n)
        i0 = np.floor(u).astype(np.int32)
        f = u - i0
        i1 = (i0 + 1) % p
        i0 %= p
        s = f * f * f * (f * (f * 6 - 15) + 10)
        top = L[i0[:, None], i0[None, :]] * (1 - s[None, :]) + L[i0[:, None], i1[None, :]] * s[None, :]
        bot = L[i1[:, None], i0[None, :]] * (1 - s[None, :]) + L[i1[:, None], i1[None, :]] * s[None, :]
        return top * (1 - s[:, None]) + bot * s[:, None]

    def fbm(self, feature_m, octaves=5, gain=0.5):
        """Octaves of noise from feature_m down, 0..1 (about), mean 0.5."""
        out = np.zeros((self.n, self.n), np.float32)
        a, tot, f = 1.0, 0.0, feature_m
        for _ in range(octaves):
            out += a * (self.noise(f) - 0.5)
            tot += a
            a *= gain
            f *= 0.5
            if f * self.px_m < 1.0:
                break
        return 0.5 + out / tot

    def worley(self, feature_m):
        """Cellular noise: the distance to the nearest and second-nearest
        point (in cells) and the nearest point's id, periodic."""
        n, c = self.n, self.cells(feature_m)
        P = self.rng.random((c, c, 2)).astype(np.float32)
        u = (np.arange(n, dtype=np.float32) + 0.5) * (c / n)
        ci = np.floor(u).astype(np.int32)
        fu = u - ci
        F1 = np.full((n, n), np.inf, np.float32)
        F2 = np.full((n, n), np.inf, np.float32)
        ID = np.zeros((n, n), np.int32)
        for dy in (-1, 0, 1):
            cy = (ci + dy) % c
            for dx in (-1, 0, 1):
                cx = (ci + dx) % c
                px = P[cy[:, None], cx[None, :], 0] + dx - fu[None, :]
                py = P[cy[:, None], cx[None, :], 1] + dy - fu[:, None]
                d = np.sqrt(px * px + py * py)
                closer = d < F1
                F2 = np.where(closer, F1, np.minimum(F2, d))
                ID = np.where(closer, cy[:, None] * c + cx[None, :], ID)
                F1 = np.where(closer, d, F1)
        return F1, F2, ID

    def blur(self, a, r):
        """A periodic box blur of radius r texels, twice (near a Gaussian)."""
        r = int(r)
        if r < 1:
            return a
        for _ in range(2):
            for ax in (0, 1):
                c = np.cumsum(np.concatenate([np.take(a, range(-r - 1, 0), axis=ax), a, np.take(a, range(0, r), axis=ax)], axis=ax),
                              axis=ax, dtype=np.float64)
                hi = np.take(c, range(2 * r + 1, c.shape[ax]), axis=ax)
                lo = np.take(c, range(0, c.shape[ax] - 2 * r - 1), axis=ax)
                a = ((hi - lo) / (2 * r + 1)).astype(np.float32)
        return a


class Stamps:
    """Shapes laid over each other on the tile: each a set of points in its
    own frame (s along, r across, both -1..1), on a lattice fine enough that
    no texel inside a shape is missed, wrapped modulo the tile. Whichever
    shape stands highest at a texel owns it: a z-buffer of (height, id)."""

    ID_BITS = 22

    def __init__(self, tile):
        self.t = tile
        self.key = np.zeros(tile.n * tile.n, np.int64)
        self.next_id = 1
        self.z_scale = 1e6          # metres to the key's integer height (a micrometre)

    def lay(self, cx, cy, ang, a, b, zfun, bend=None):
        """Shapes centred (cx, cy) px, turned ang, half-length a and
        half-width b px; zfun(s, r, i) -> (inside, z metres) for the local
        points of shape i (arrays). bend: px the shape's tip curves aside.
        Returns the ids given, in order."""
        n = self.t.n
        ids = np.arange(self.next_id, self.next_id + len(cx))
        self.next_id += len(cx)
        assert self.next_id < (1 << self.ID_BITS)
        step = 0.6
        # shapes binned by size so each bin shares one lattice
        bins = np.unique(np.ceil(np.log2(np.maximum(a, 1.0)) * 2.0))
        sz = np.ceil(np.log2(np.maximum(a, 1.0)) * 2.0)
        for bn in bins:
            sel = np.nonzero(sz == bn)[0]
            amax = float(a[sel].max())
            bmax = float(b[sel].max())
            ns = int(math.ceil(2 * amax / step)) + 1
            nr = int(math.ceil(2 * bmax / step)) + 1
            S_ = np.linspace(-1, 1, ns, dtype=np.float32)
            R_ = np.linspace(-1, 1, nr, dtype=np.float32)
            gs, gr = np.meshgrid(S_, R_, indexing="ij")
            gs, gr = gs.ravel(), gr.ravel()
            chunk = max(1, int(4e6 // max(1, gs.size)))
            for k0 in range(0, len(sel), chunk):
                idx = sel[k0:k0 + chunk]
                sa = gs[None, :] * (amax / a[idx, None])         # local s in the shape's own -1..1
                ra = gr[None, :] * (bmax / b[idx, None])
                inside, z = zfun(sa, ra, idx)
                inside &= (np.abs(sa) <= 1) & (np.abs(ra) <= 1)
                ca, sn = np.cos(ang[idx])[:, None], np.sin(ang[idx])[:, None]
                along = sa * a[idx, None]
                across = ra * b[idx, None]
                if bend is not None:
                    across = across + bend[idx, None] * ((sa + 1) * 0.5) ** 2
                x = cx[idx, None] + along * ca - across * sn
                y = cy[idx, None] + along * sn + across * ca
                xi = np.floor(x[inside]).astype(np.int64) % n
                yi = np.floor(y[inside]).astype(np.int64) % n
                zq = np.clip(z[inside] * self.z_scale, 0, (1 << 40) - 1).astype(np.int64)
                kk = (zq << self.ID_BITS) | np.broadcast_to(ids[idx, None], inside.shape)[inside]
                np.maximum.at(self.key, yi * n + xi, kk)
        return ids

    def read(self):
        """(id, z metres) per texel; id 0 where nothing was laid."""
        n = self.t.n
        idv = (self.key & ((1 << self.ID_BITS) - 1)).reshape(n, n).astype(np.int32)
        z = (self.key >> self.ID_BITS).reshape(n, n).astype(np.float32) / self.z_scale
        return idv, z


# ================================================================ helpers

def luma(c):
    return 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]


def mix(a, b, t):
    t = np.asarray(t, np.float32)[..., None]
    return a * (1 - t) + b * t


def held(rgb):
    """Every texel between the ink floor (one 8-bit step over it) and the
    world's ceiling, at its own hue."""
    if "under_floor" in SABOTAGE:
        return np.clip(rgb * 0.35, 0, 1)
    y = luma(rgb)
    lo, hi = S.ink_hold(), S.WEATHER["hi"]
    s = np.where(y < lo, lo / np.maximum(y, 1e-6), np.where(y > hi, hi / np.maximum(y, 1e-6), 1.0))
    return rgb * s[..., None]


def normals(tile, h, gain=1.0, blur_m=0.0):
    """The height's slope at the texel's real size, as a DirectX normal map
    (green DOWN the image, Unreal's default): returns n (x right, y down
    the image, z out), float."""
    if "flat_normal" in SABOTAGE:
        h = h * 0.0
    if blur_m > 0:
        h = tile.blur(h, max(1, int(round(blur_m * tile.px_m))))
    d = 1.0 / tile.px_m
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / (2 * d)
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) / (2 * d)     # d h / d(row), row DOWN the image
    nx, ny, nz = -gx * gain, -gy * gain, np.ones_like(h)
    L = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / L, ny / L, nz / L
    # no texel steeper than NORMAL_Z_MIN: lay the tilt back, keep its way
    t = np.sqrt(np.maximum(1e-12, nx * nx + ny * ny))
    cap = math.sqrt(1 - NORMAL_Z_MIN ** 2)
    k = np.where(t > cap, cap / t, 1.0)
    nx, ny = nx * k, ny * k
    nz = np.sqrt(np.maximum(0.0, 1 - nx * nx - ny * ny))
    if "opengl" in SABOTAGE:
        ny = -ny
    return np.stack([nx, ny, nz], -1).astype(np.float32)


# ================================================================ layers

def sand(t):
    P = weathered("Sand")
    n = t.n
    damp = t.fbm(1.6, 4)
    damp = np.clip((damp - 0.46) / 0.12, 0, 1)
    # ripples: a periodic wave, its wavevector whole numbers of the tile so
    # it wraps, warped by low noise so its crests wander
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) / n
    warp = (t.fbm(1.0, 3) - 0.5) * 2.2 + (t.fbm(0.4, 2) - 0.5) * 0.6
    kx, ky = 9, 31                               # 4 m / |(9,31)| = 12.4 cm between crests
    ph = 2 * math.pi * (kx * xx + ky * yy) + warp * 2 * math.pi
    rip = np.sin(ph) + 0.35 * np.sin(2 * ph + 1.3)
    rip_amp = 0.006 * (1 - 0.6 * damp) * (0.6 + 0.8 * t.fbm(0.8, 2))
    grain = t.noise(0.0008) - 0.5
    grain2 = t.blur(t.noise(0.0008), 1) - 0.5
    h = rip * rip_amp + grain * 0.00025 + grain2 * 0.0004
    # broken shell: small pale flakes lying on the surface
    st = Stamps(t)
    m = int(110 * TILE_M ** 2)
    cx, cy = t.rng.random(m) * n, t.rng.random(m) * n
    a = (t.rng.uniform(0.002, 0.008, m) * t.px_m).astype(np.float32)
    b = a * t.rng.uniform(0.4, 0.8, m)
    ang = t.rng.random(m) * 2 * math.pi
    def flake(s, r, i):
        rr = s * s + r * r
        return rr <= 1, 0.0004 + 0.0006 * (1 - rr)
    st.lay(cx, cy, ang, np.maximum(a, 1.0), np.maximum(b, 1.0), flake)
    sid, sz = st.read()
    shell = sid > 0
    h = np.where(shell, np.maximum(h, sz + h.min()), h)
    # colour: dry and pale toward the crests, damp darker, dark heavy grains
    # gathered in the troughs, a speckle of single dark and pale grains
    crest = np.clip(rip * 0.5 + 0.5, 0, 1)
    c = mix(P["dry"], P["pale"], crest * 0.55 * (1 - damp))
    c = mix(c, P["damp"], damp * 0.85)
    trough = np.clip(-rip - 0.4, 0, 1) * (1 - damp)
    c = mix(c, P["dark"], trough * 0.35)
    sp = t.noise(0.0008)
    c = mix(c, P["dark"], (sp > 0.93) * 0.55)
    c = mix(c, P["pale"], (sp < 0.05) * 0.6)
    c = np.where(shell[..., None], mix(P["shell"], P["pale"], 0.3), c)
    rough = 0.94 - 0.20 * damp + (t.noise(0.003) - 0.5) * 0.04
    rough = np.where(shell, 0.75, rough)
    return c, h, rough


def grass(t):
    P = weathered("Grass")
    n = t.n
    soil_h = (t.fbm(0.3, 4) - 0.5) * 0.004
    clump = t.fbm(0.35, 3)
    # blades: rooted where the clumps are dense, thinned where they are not
    want = int(14000 * TILE_M ** 2)
    cand = int(want * 2.2)
    rx, ry = t.rng.random(cand) * n, t.rng.random(cand) * n
    dens = clump[ry.astype(int) % n, rx.astype(int) % n]
    keep = t.rng.random(cand) < np.clip((dens - 0.24) / 0.22, 0, 1)
    rx, ry = rx[keep][:want], ry[keep][:want]
    m = len(rx)
    lean = t.fbm(0.6, 2)[ry.astype(int) % n, rx.astype(int) % n] * 4 * math.pi
    ang = (lean + t.rng.normal(0, 0.55, m)).astype(np.float32)
    L = t.rng.uniform(0.030, 0.085, m) * t.px_m                       # 3-8.5 cm seen from above
    a = (L * 0.5).astype(np.float32)
    w = (t.rng.uniform(0.0016, 0.0032, m) * t.px_m).astype(np.float32)
    bend = (t.rng.normal(0, 0.18, m) * L).astype(np.float32)
    root = t.rng.uniform(0.0, 0.004, m).astype(np.float32)
    rise = (L / t.px_m * t.rng.uniform(0.35, 0.8, m)).astype(np.float32)
    # the blade centred on its middle: s -1 the root, +1 the tip
    cx = rx + a * np.cos(ang)
    cy = ry + a * np.sin(ang)
    def blade(s, r, i):
        tt = (s + 1) * 0.5
        width = (1 - np.clip(tt, 0, 1)) ** 0.6
        inside = np.abs(r) <= np.maximum(width, 0.12)
        z = 0.01 + root[i, None] + rise[i, None] * tt + 0.0006 * (1 - r * r) * width
        return inside, z
    st = Stamps(t)
    ids = st.lay(cx, cy, ang, a, np.maximum(w * 0.5, 0.6), blade, bend=bend)
    bid, bz = st.read()
    on = bid > 0
    k = np.clip(bid - ids[0], 0, m - 1)
    tip = np.where(on, np.clip((bz - 0.01 - root[k]) / np.maximum(rise[k], 1e-4), 0, 1), 0)
    # each blade its own green, some drying to straw; the root in the
    # grass's own shade
    gk = t.rng.random(m).astype(np.float32)
    dry = (t.rng.random(m) < 0.18).astype(np.float32)
    base = mix(P["green"], P["young"], gk[k])
    col_b = mix(base, P["straw"], np.clip(dry[k] * (0.4 + 0.6 * tip) + tip * 0.25, 0, 1))
    shade = 0.55 + 0.45 * tip
    col_b = col_b * shade[..., None]
    soil = mix(P["soil"], P["straw"], np.clip(t.fbm(0.05, 3) - 0.35, 0, 1) * 0.6) * 0.8
    c = np.where(on[..., None], col_b, soil)
    h = np.where(on, bz, soil_h)
    rough = np.where(on, 0.62 + 0.18 * dry[k] + 0.08 * (1 - tip), 0.90)
    return c, h, rough


def jungle(t):
    P = weathered("Jungle")
    n = t.n
    soil_h = (t.fbm(0.4, 4) - 0.5) * 0.006
    m = int(1400 * TILE_M ** 2)
    cx, cy = t.rng.random(m) * n, t.rng.random(m) * n
    L = t.rng.lognormal(math.log(0.075), 0.35, m).clip(0.03, 0.22)        # leaves 3-22 cm
    a = (L * 0.5 * t.px_m).astype(np.float32)
    b = (a * t.rng.uniform(0.28, 0.48, m)).astype(np.float32)
    ang = (t.rng.random(m) * 2 * math.pi).astype(np.float32)
    layer = t.rng.random(m).astype(np.float32)                        # which leaf lies on which
    curl = t.rng.uniform(0.0, 0.004, m).astype(np.float32)
    bend = (t.rng.normal(0, 0.12, m) * a).astype(np.float32)
    def leaf(s, r, i):
        # a leaf: pointed at both ends, broadest a third from its stalk
        sh = np.sqrt(np.clip(1 - s * s, 0, 1)) * (1 - 0.25 * s)
        inside = np.abs(r) <= sh
        z = 0.005 + layer[i, None] * 0.02 + curl[i, None] * (r * r) + 0.0008 * (1 - s * s) \
            - 0.0005 * np.exp(-(r / 0.08) ** 2)
        return inside, z
    st = Stamps(t)
    ids = st.lay(cx, cy, ang, a, b, leaf, bend=bend)
    # twigs over the leaves
    tw = int(60 * TILE_M ** 2)
    tcx, tcy = t.rng.random(tw) * n, t.rng.random(tw) * n
    ta = (t.rng.uniform(0.05, 0.25, tw) * 0.5 * t.px_m).astype(np.float32)
    tb = (t.rng.uniform(0.002, 0.005, tw) * t.px_m).astype(np.float32)
    tang = (t.rng.random(tw) * 2 * math.pi).astype(np.float32)
    def twig(s, r, i):
        return np.abs(r) <= 1, 0.03 + 0.002 * (1 - r * r)
    tid0 = st.next_id
    st.lay(tcx, tcy, tang, ta, np.maximum(tb, 1.0), twig, bend=(t.rng.normal(0, 0.1, tw) * ta).astype(np.float32))
    lid, lz = st.read()
    on = lid > 0
    is_twig = lid >= tid0
    k = np.clip(lid - ids[0], 0, m - 1)
    age = t.rng.random(m).astype(np.float32)
    fresh = (t.rng.random(m) < 0.14).astype(np.float32)
    leafc = mix(mix(P["tan"], P["brown"], age[k]), P["dark"], np.clip(age[k] - 0.7, 0, 1) * 2)
    leafc = mix(leafc, P["fresh"], fresh[k])
    # the midrib and the veins a shade darker; the lower leaves in shade
    shade = 0.55 + 0.45 * np.clip((lz - 0.005) / 0.02, 0, 1)
    c = leafc * shade[..., None]
    c = np.where(is_twig[..., None], P["twig"][None, None, :] * 0.9, c)
    soil = mix(P["soil"], P["dark"], t.fbm(0.06, 3)) * 0.85
    c = np.where(on[..., None], c, soil)
    h = np.where(on, lz, soil_h)
    vein = t.blur(np.abs(np.roll(h, 1, 1) - np.roll(h, -1, 1)) + np.abs(np.roll(h, 1, 0) - np.roll(h, -1, 0)), 1)
    c = c * (1 - np.clip(vein * 600, 0, 0.25))[..., None]
    rough = np.where(on, 0.70 - 0.22 * fresh[k] + 0.12 * age[k], 0.88)
    rough = np.where(is_twig, 0.80, rough)
    return c, h, rough


def rock(t):
    P = weathered("Rock")
    n = t.n
    ridged = np.zeros((n, n), np.float32)
    a, f = 1.0, 2.0
    for _ in range(7):
        v = 1 - np.abs(2 * t.noise(f) - 1)
        ridged += a * v * v
        a *= 0.5
        f *= 0.5
        if f * t.px_m < 1:
            break
    ridged /= 2.0
    F1, F2, _ = t.worley(0.45)
    # cracks run only where the stone is split (a noise mask), so they are a
    # few long fissures and not a paving of cells
    split = np.clip((t.fbm(0.9, 3) - 0.50) * 7, 0, 1)
    crack = np.clip(1 - (F2 - F1) / 0.04, 0, 1) ** 2 * split
    F1b, F2b, _ = t.worley(0.12)
    crack2 = np.clip(1 - (F2b - F1b) / 0.04, 0, 1) ** 2 * 0.5 * np.clip((t.fbm(0.5, 3) - 0.55) * 6, 0, 1)
    h = ridged * 0.05 + (t.fbm(1.0, 3) - 0.5) * 0.06 - crack * 0.012 - crack2 * 0.004 + (t.noise(0.001) - 0.5) * 0.0004
    hb = t.blur(h, max(1, int(0.02 * t.px_m)))
    top = np.clip((h - hb) * 400 + 0.5, 0, 1)                         # the tops of the stone, against its hollows
    c = mix(P["stone"], P["pale"], np.clip(t.fbm(0.3, 4) - 0.45, 0, 1) * 1.6)
    c = mix(c, P["dark"], np.clip(t.fbm(0.8, 3) - 0.55, 0, 1) * 2.0)
    lichen = np.clip((t.fbm(0.18, 4) - 0.60) * 8, 0, 1) * top
    moss = np.clip((t.fbm(0.25, 4) - 0.55) * 6, 0, 1) * (1 - top) + crack * 0.4
    c = mix(c, P["lichen"], lichen * 0.85)
    c = mix(c, P["moss"], np.clip(moss, 0, 1) * 0.8)
    c = c * (1 - crack * 0.45)[..., None]
    grit = t.noise(0.0008)
    c = mix(c, P["pale"], np.clip(grit - 0.80, 0, 1) * 2.5)          # quartz and feldspar
    c = mix(c, P["dark"], np.clip(0.25 - grit, 0, 1) * 2.0)          # dark grains
    rough = 0.80 + 0.08 * lichen - 0.10 * np.clip(top - 0.5, 0, 1) + (t.noise(0.004) - 0.5) * 0.05
    return c, h, rough


def mud(t):
    P = weathered("Mud")
    n = t.n
    base = t.fbm(0.9, 5)
    tread = t.blur(t.fbm(0.12, 3), 2)
    h = (base - 0.5) * 0.06 + (tread - 0.5) * 0.012 + (t.noise(0.0015) - 0.5) * 0.0008
    # stones pressed in
    st = Stamps(t)
    m = int(140 * TILE_M ** 2)
    cx, cy = t.rng.random(m) * n, t.rng.random(m) * n
    a = (t.rng.uniform(0.006, 0.03, m) * t.px_m).astype(np.float32)
    b = (a * t.rng.uniform(0.55, 0.95, m)).astype(np.float32)
    ang = (t.rng.random(m) * 2 * math.pi).astype(np.float32)
    def stone(s, r, i):
        rr = s * s + r * r
        return rr <= 1, 0.04 + 0.006 * np.sqrt(np.clip(1 - rr, 0, 1)) * (a[i, None] / t.px_m / 0.02)
    st.lay(cx, cy, ang, np.maximum(a, 1.0), np.maximum(b, 1.0), stone)
    sid, sz = st.read()
    is_stone = sid > 0
    # water stands in the hollows: below its level the surface is the water's
    level = np.quantile(h, 0.16)
    water = h < level
    wet = np.clip((level + 0.008 - h) / 0.008, 0, 1)
    c = mix(P["mud"], P["dry"], np.clip(t.fbm(0.3, 3) - 0.45, 0, 1) * 1.5 * (1 - wet))
    c = mix(c, P["wet"], wet * 0.9)
    grit = t.noise(0.0008)
    c = mix(c, P["dry"], np.clip(grit - 0.78, 0, 1) * 2.0 * (1 - wet))  # grit, dried pale on the tops
    c = mix(c, P["wet"], np.clip(0.25 - grit, 0, 1) * 1.6)
    c = np.where(water[..., None], P["water"][None, None, :], c)
    c = np.where(is_stone[..., None], mix(P["stone"], P["dry"], 0.3) * (0.75 + 0.25 * t.noise(0.01))[..., None], c)
    hs = np.where(water, level, h)
    hs = np.where(is_stone, np.maximum(hs, h + (sz - 0.04)), hs)
    rough = 0.80 - 0.40 * wet
    rough = np.where(water, WATER_ROUGH, rough)
    rough = np.where(is_stone, 0.70, rough)
    return c, hs, rough


DRAW = dict(Sand=sand, Grass=grass, Jungle=jungle, Rock=rock, Mud=mud)
SEED = dict(Sand=11, Grass=23, Jungle=37, Rock=41, Mud=53)


def build(size=SIZE, layers=LAYERS):
    """{layer: dict(colour=uint8 RGB sRGB, normal=uint8 RGB, rough=uint8)}"""
    out = {}
    for name in layers:
        t0 = time.time()
        t = Tile(size, SEED[name])
        if "same_colour" in SABOTAGE and name == "Mud":
            c, h, r = DRAW["Sand"](Tile(size, SEED["Mud"]))
        else:
            c, h, r = DRAW[name](t)
        if "glossy_sand" in SABOTAGE and name == "Sand":
            r = r * 0.3
        if "flat_colour" in SABOTAGE and name == "Rock":
            c = np.broadcast_to(c.reshape(-1, 3).mean(0), c.shape).copy()
        c = held(c.astype(np.float32))
        if "seam" in SABOTAGE and name == "Rock":
            c = c * np.linspace(0.85, 1.15, size, dtype=np.float32)[None, :, None]
            c = held(c)
        srgb = np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.maximum(c, 1e-9), 1 / 2.4) - 0.055)
        nrm = normals(t, h.astype(np.float32), 4.0 if "steep_normal" in SABOTAGE and name == "Grass" else NORMAL_GAIN[name], NORMAL_BLUR_M[name])
        out[name] = dict(
            colour=np.clip(np.round(srgb * 255), 0, 255).astype(np.uint8),
            normal=np.clip(np.round((nrm * 0.5 + 0.5) * 255), 0, 255).astype(np.uint8),
            rough=np.clip(np.round(np.clip(r, 0, 1) * 255), 0, 255).astype(np.uint8))
        print("  %-7s %5.1fs" % (name, time.time() - t0))
    return out


# ================================================================ checks

def _lin(u8):
    s = u8.astype(np.float32) / 255.0
    return np.where(s <= 0.04045, s / 12.92, ((s + 0.055) / 1.055) ** 2.4)


def _lab(rgb):
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = rgb @ M.T / np.array([0.9505, 1.0, 1.089])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def _seam(a):
    """The step across the wrap against the steps inside: the wrap's mean
    step over the column (or row) against the largest of the interior's
    (its 99.5th percentile), so a ridge that happens to cross the edge is
    not a seam and a mismatch is. Read on the texels and on the tile
    smoothed a little, where a low-frequency mismatch would hide in the
    per-texel noise. The worst of the four."""
    a = a.astype(np.float32)
    if a.ndim == 3:
        a = a.mean(-1)
    k = max(2, a.shape[0] // 256)
    b = a.reshape(a.shape[0] // k, k, a.shape[1] // k, k).mean((1, 3))
    worst = 0.0
    for m in (a, b):
        for ax in (0, 1):
            inside = np.abs(np.diff(m, axis=ax)).mean(1 - ax)
            wrap = np.abs(np.take(m, 0, axis=ax) - np.take(m, -1, axis=ax)).mean()
            worst = max(worst, wrap / max(np.percentile(inside, 99.5), 1e-6))
    return worst


def bump_test():
    """A dome on a tile, through normals(): on the texels above it (up the
    image) a DirectX normal's green is under the middle."""
    t = Tile(64, 0)
    yy, xx = np.mgrid[0:64, 0:64].astype(np.float32)
    h = 0.3 * np.exp(-((xx - 32) ** 2 + (yy - 32) ** 2) / 60.0)
    nrm = normals(t, h)
    return float(nrm[26, 32, 1]), float(nrm[38, 32, 1])


def check(maps, size=SIZE):
    fails = []
    floor, hi = S.ink_floor(), S.WEATHER["hi"]
    means = {}
    for name, m in maps.items():
        c, nm, r = m["colour"], m["normal"], m["rough"]
        if c.shape[:2] != (size, size):
            fails.append("%s is %s, want %d square" % (name, c.shape[:2], size))
        for what, a in (("colour", c), ("normal", nm), ("roughness", r)):
            s = _seam(a)
            if s > 1.2:
                fails.append("%s's %s does not tile: its wrap steps %.2f x its insides" % (name, what, s))
        lin = _lin(c)
        y = luma(lin)
        if y.min() < floor - 1e-4:
            fails.append("%s's colour goes under the ink floor: %.4f, want %.3f or more" % (name, y.min(), floor))
        if y.max() > hi + 0.004:
            fails.append("%s's colour goes over the ceiling: %.3f, want %.2f or less" % (name, y.max(), hi))
        means[name] = lin.reshape(-1, 3).mean(0)
        # detail: at two millimetres (whatever the texel) and at a decimetre
        st = max(1, int(round(0.002 / (TILE_M / size))))
        fine = np.abs(y[:, st:] - y[:, :-st]).mean() / max(y.mean(), 1e-6)
        k = max(1, int(0.1 / (TILE_M / size)))
        cs = y[: (size // k) * k, : (size // k) * k].reshape(size // k, k, size // k, k).mean((1, 3))
        coarse = cs.std() / max(cs.mean(), 1e-6)
        if fine < 0.02 or coarse < 0.03:
            fails.append("%s's colour is flat: %.3f at 2 mm, %.3f at a decimetre (want 0.02 and 0.03)" % (name, fine, coarse))
        n = nm.astype(np.float32) / 255.0 * 2 - 1
        ln = np.sqrt((n ** 2).sum(-1))
        if np.abs(ln - 1).max() > 0.03:
            fails.append("%s's normals are not unit length: off by %.3f" % (name, np.abs(ln - 1).max()))
        if n[..., 2].min() < NORMAL_Z_MIN - 0.02:
            fails.append("%s's normals face in: z %.2f" % (name, n[..., 2].min()))
        if n[..., 2].mean() < NORMAL_MEAN_Z:
            fails.append("%s's normals are steep on the whole: mean z %.2f, want %.2f" % (name, n[..., 2].mean(), NORMAL_MEAN_Z))
        tilt = np.sqrt(n[..., 0] ** 2 + n[..., 1] ** 2)
        if tilt.mean() < 0.04:
            fails.append("%s's normal map is flat: mean tilt %.3f, want 0.04" % (name, tilt.mean()))
        lo_, hi_ = ROUGH[name]
        rr = r.astype(np.float32) / 255.0
        if rr.min() < lo_ - 0.01 or rr.max() > hi_ + 0.01:
            fails.append("%s's roughness %.2f-%.2f is outside %.2f-%.2f" % (name, rr.min(), rr.max(), lo_, hi_))
        if name == "Mud" and (rr <= WATER_ROUGH + 0.01).mean() < 0.05:
            fails.append("the mud has no standing water: %.1f %% glossy, want 5" % ((rr <= WATER_ROUGH + 0.01).mean() * 100))
    up, down = bump_test()
    if not (up < -0.05 and down > 0.05):
        fails.append("the normals are not DirectX (Unreal's): above a bump green %.2f, below %.2f" % (up, down))
    labs = {k: _lab(v[None, :])[0] for k, v in means.items()}
    names = list(labs)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            d = float(np.sqrt(((labs[names[i]] - labs[names[j]]) ** 2).sum()))
            if d < 3.0:
                fails.append("%s and %s are the same colour: %.1f apart, want 3" % (names[i], names[j], d))
    if "Grass" in labs and labs["Grass"][1] > -1.0:
        fails.append("the grass is not green: a* %.1f, want under -1" % labs["Grass"][1])
    if "Jungle" in labs and "Sand" in labs and labs["Jungle"][0] >= labs["Sand"][0]:
        fails.append("the jungle floor is not darker than the beach: L* %.1f against %.1f" % (labs["Jungle"][0], labs["Sand"][0]))
    return fails


# ================================================================ write, draw

def write(maps, out=OUT):
    from PIL import Image
    os.makedirs(out, exist_ok=True)
    total = 0
    for name, m in maps.items():
        for role, key in (("BaseColor", "colour"), ("Normal", "normal"), ("Roughness", "rough")):
            p = os.path.join(out, "T_IslandGround_%s_%s.png" % (name, role))
            Image.fromarray(m[key]).save(p, optimize=True)
            total += os.path.getsize(p)
    print("wrote %s (%.0f MB)" % (out, total / 1e6))


def draw(maps, path=SHEET):
    """Each layer twice: the tile laid 2 x 2, lit (a seam would show as a
    cross), and 50 cm of it at full size."""
    from PIL import Image, ImageDraw
    cell = 512
    sheet = Image.new("RGB", (cell * 2 + 30, (cell + 28) * len(maps) + 10), (12, 14, 20))
    dr = ImageDraw.Draw(sheet)
    light = np.array([-0.45, -0.55, 0.70], np.float32)
    light /= np.linalg.norm(light)
    for row, (name, m) in enumerate(maps.items()):
        lin = _lin(m["colour"])
        n = m["normal"].astype(np.float32) / 255.0 * 2 - 1
        lit = lin * (0.35 + 1.4 * np.clip((n * light).sum(-1), 0, 1))[..., None]
        disp = np.clip(lit * 1.8, 0, 1) ** (1 / 2.2)
        img = (disp * 255).astype(np.uint8)
        size = img.shape[0]
        whole = Image.fromarray(np.tile(img, (2, 2, 1))).resize((cell, cell), Image.LANCZOS)
        crop_px = max(16, int(0.5 / (TILE_M / size)))
        crop = Image.fromarray(img[:crop_px, :crop_px]).resize((cell, cell), Image.LANCZOS)
        y = 10 + row * (cell + 28)
        dr.text((10, y), "%s   (left: 8 m, the tile 2 x 2;  right: 50 cm)" % name, fill=(220, 230, 240))
        sheet.paste(whole, (10, y + 16))
        sheet.paste(crop, (20 + cell, y + 16))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sheet.save(path)
    print("drew %s" % path)


BITES = [
    ("every map tiles", "seam", "does not tile"),
    ("the ink floor", "under_floor", "under the ink floor"),
    ("the layers apart", "same_colour", "the same colour"),
    ("not a flat colour", "flat_colour", "is flat"),
    ("normals not flat", "flat_normal", "normal map is flat"),
    ("Unreal's normals", "opengl", "not DirectX"),
    ("normals face out", "steep_normal", "steep on the whole"),
    ("the roughness range", "glossy_sand", "roughness"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--bite", action="store_true")
    ap.add_argument("--size", type=int, default=SIZE)
    a = ap.parse_args()
    if a.bite:
        size = min(a.size, 1024)
        caught = 0
        for what, sab, want in BITES:
            SABOTAGE.clear()
            SABOTAGE.add(sab)
            f = check(build(size), size)
            hit = [x for x in f if want in x]
            caught += bool(hit)
            print("  %-20s %s  %s" % (what, "caught" if hit else "MISSED", (hit or f or ["(passed)"])[0]))
        SABOTAGE.clear()
        print("%d of %d caught" % (caught, len(BITES)))
        sys.exit(0 if caught == len(BITES) else 1)
    maps = build(a.size)
    f = check(maps, a.size)
    if f:
        print("FAILED:\n  " + "\n  ".join(f))
        sys.exit(1)
    print("checks pass: every map tiles, the floor and the ceiling, the layers apart, detail, "
          "the normals (unit, out, not flat, DirectX), the roughness")
    if not a.check:
        if a.size == SIZE:
            write(maps)
        draw(maps)


if __name__ == "__main__":
    main()
