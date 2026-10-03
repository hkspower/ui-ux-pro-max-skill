#!/usr/bin/env python3
"""JAZIRAT AL-QIRUD -- the monkey island: the terrain.

Asked 2026-10-02 as "build 3d map island level with monkeys as enemy and big
gorilla as map boss, make large island full 4k ... full ik", settled with the
author as: built in Blender and Python here (3ds Max cannot run on this
machine), both a 4 km island AND 4K textures, and a NEW LEVEL, UNREAL ONLY --
its own map outside the nine districts, like the prologue, its own waves of
monkeys and the gorilla, its numbers in its own Unreal data. The browser
build and the ring are untouched.

This script is the ground: an Unreal landscape heightmap and its paint
layers, worked out here and checked here, written as the files the
landscape importer reads.

THE ISLAND. 4,033 x 4,033 vertices a metre apart -- 4.03 km on a side, the
size Unreal's landscape takes as 63 x 63 components of 64 quads (4033 is
its own recommended size). The sea is 0 m. The coast is a circle of
1,650 m warped by low-frequency noise, so it has bays and headlands, and the
ground climbs from a beach through jungle hills to one peak on the
north-east, about 160 m. Beyond the coast the sea floor falls to -30 m, and
nothing within 120 m of the edge of the landscape is land, so the sea is
the edge of the world, not a wall.

THE WAY THROUGH. The boat lands on the west beach. A trail is found from
there to the gorilla's ground -- a ruined temple on a plateau 60 m up on the
east side -- by a least-cost search over a 16 m grid, costed by steepness,
then smoothed and CARVED: its height along its length is held to a grade a
man can run (at most 18 %), it is cut level across (a 4 m bed and a 6 m
shoulder), and five clearings along it are flattened for the monkey waves.
The temple plateau is flattened to 45 m across with a ramp of ground round
it. Every number the level needs about these -- where the boat lands, the
sites, the arena, the trail -- is written to MonkeyIsland_plan.json, and
the level script (Tools/levels/build_monkey_island_level.py) reads it
rather than working it out again.

THE LAYERS. Five weightmaps, 8-bit, summing to 255 at every vertex: Sand
(the beach and the sea floor), Grass (open ground), Jungle (the floor under
the trees, most of the island), Rock (anything steep, and the bare summit)
and Mud (the trail and the clearings).

THE HEIGHT ENCODING. Unreal reads a 16-bit heightmap as
height_cm = (value - 32768) * ZScale / 128 with the landscape's Z scale in
cm; at Z scale 100 a value step is 1/128 m and the range is +-256 m. The
writer and a decoder share the constants and a check holds the round trip.

    python3 build_monkey_island.py            # build, check, write, draw
    python3 build_monkey_island.py --check    # build and check only
    python3 build_monkey_island.py --bite     # break each rule once

Not verified: no engine has imported the heightmap or the layers. The
importer's 16-bit convention, and the landscape's scale and location
below, are as remembered for UE 5.4.
"""

import argparse
import heapq
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(PROJECT, "Content", "Landscape", "MonkeyIsland")
DOCS = os.path.join(PROJECT, "Docs")

# ------------------------------------------------------------------ the grid
N = 4033                       # vertices a side: 63 components of 64 quads, + 1
CELL_M = 1.0                   # metres between vertices (landscape X/Y scale 100)
HALF_M = (N - 1) * CELL_M / 2  # 2016 m: the landscape runs -2016..+2016 on X and Y
Z_SCALE_CM = 100.0             # the landscape actor's Z scale
Z_STEP_M = Z_SCALE_CM / 128.0 / 100.0   # metres per 16-bit step: 1/128 m
SEED = 977

# ------------------------------------------------------------------ the island
COAST_R_M = 1650.0             # the coast's mean radius
COAST_WARP_M = 190.0           # bays and headlands
BEACH_M = 2.5                  # the beach rises to this
BEACH_BAND = 0.06              # of the radius: the beach's width inland (about 100 m)
INLAND_M = 38.0                # the ground behind the beach climbs to about this
HILLS_M = 42.0                 # jungle hills, fBm, fading in from the beach
PEAK = (620.0, 560.0, 125.0, 330.0)   # x, y, height over the ground there, sigma (m)
SEA_FLOOR_M = -30.0
SEA_EDGE_M = 120.0             # no land within this of the landscape's edge
LAND_MIN_M = 0.5               # "on land": higher than this

# ------------------------------------------------------------------ the way through
LANDING_DEG = 182.0            # the boat lands on the west beach, this bearing from the middle
ARENA = (520.0, -330.0)        # the temple plateau, the gorilla's ground
ARENA_R_M = 22.5               # 45 m across, flat
ARENA_RAMP_M = 30.0            # its ground blends out over this
ARENA_H_M = 60.0               # its height
GRID_M = 16.0                  # the search grid
TRAIL_BED_M = 2.0              # half-width of the level bed
TRAIL_SHOULDER_M = 6.0         # blended back into the slope over this
TRAIL_GRADE = 0.18             # at most this rise per metre along it
SITE_FRACTIONS = (0.14, 0.32, 0.50, 0.68, 0.84)   # where the monkey waves wake, along the trail
SITE_R_M = 14.0                # each clearing, flat
SITE_RAMP_M = 10.0
FLAT_DEG = 6.0                 # a clearing, the arena, the landing: no steeper than this
CROSS_DEG = 10.0               # the trail's bed across its width

LAYERS = ("Sand", "Grass", "Jungle", "Rock", "Mud")

SABOTAGE = set()


# ================================================================== noise and filters

def _rng(k):
    return np.random.default_rng(SEED * 7919 + k)


def value_noise(n, cells, k):
    """Smooth value noise over an n x n grid with `cells` lattice cells a side,
    -1..1, interpolated with a smoothstep -- one octave."""
    g = _rng(k).uniform(-1.0, 1.0, (cells + 2, cells + 2))
    t = np.linspace(0.0, cells, n, endpoint=False) + 0.5
    i = np.floor(t).astype(np.int64)
    f = t - i
    f = f * f * (3.0 - 2.0 * f)
    out = np.empty((n, n), np.float32)
    # rows then columns, in blocks to bound memory
    for r0 in range(0, n, 512):
        r = slice(r0, min(n, r0 + 512))
        iy, fy = i[r][:, None], f[r][:, None]
        ix, fx = i[None, :], f[None, :]
        a = g[iy, ix] * (1 - fx) + g[iy, ix + 1] * fx
        b = g[iy + 1, ix] * (1 - fx) + g[iy + 1, ix + 1] * fx
        out[r] = a * (1 - fy) + b * fy
    return out


def fbm(n, base_cells, octaves, k, gain=0.5):
    out = np.zeros((n, n), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        out += amp * value_noise(n, base_cells * (2 ** o), k * 31 + o)
        tot += amp
        amp *= gain
    return out / tot


def box_blur(a, r):
    """Separable box blur of radius r (cells), edges clamped."""
    if r < 1:
        return a
    def one(x, axis):
        p = np.pad(x, [(r + 1, r)] if x.ndim == 1 else ([(r + 1, r), (0, 0)] if axis == 0 else [(0, 0), (r + 1, r)]), mode="edge")
        c = np.cumsum(p, axis=axis, dtype=np.float64)
        if axis == 0:
            return ((c[2 * r + 1:] - c[:-2 * r - 1]) / (2 * r + 1)).astype(np.float32)
        return ((c[:, 2 * r + 1:] - c[:, :-2 * r - 1]) / (2 * r + 1)).astype(np.float32)
    return one(one(a, 0), 1)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ================================================================== the grid in metres

def axis_m():
    return (np.arange(N, dtype=np.float32) - (N - 1) / 2.0) * CELL_M


def to_index(x, y):
    """Metres (x east, y north) -> (row, col). Row 0 is north (+y)."""
    c = int(round(x / CELL_M + (N - 1) / 2.0))
    r = int(round((N - 1) / 2.0 - y / CELL_M))
    return r, c


def to_metres(r, c):
    return (c - (N - 1) / 2.0) * CELL_M, ((N - 1) / 2.0 - r) * CELL_M


# ================================================================== the ground

def base_terrain():
    a = axis_m()
    X = a[None, :]
    Y = a[::-1][:, None]
    R = np.sqrt(X * X + Y * Y)
    TH = np.arctan2(Y, X)
    # the coast's radius, warped by low-frequency noise sampled on the circle
    warp = fbm(N, 3, 3, 1)
    coast = COAST_R_M + COAST_WARP_M * warp
    d = R / coast                                 # 1 at the coast
    inland = smoothstep(1.0, 1.0 - BEACH_BAND, d)
    deep = smoothstep(1.0, 1.0 + BEACH_BAND * 4, d)
    hills = fbm(N, 6, 6, 2)
    ground = (BEACH_M * smoothstep(1.02, 1.0 - BEACH_BAND * 0.5, d)
              + INLAND_M * (inland ** 1.3) * np.clip(1.15 - d, 0.0, 1.0)
              + HILLS_M * inland * (0.5 + 0.5 * hills) * smoothstep(1.0 - BEACH_BAND, 0.6, d))
    px, py, ph, ps = PEAK
    ground += ph * np.exp(-((X - px) ** 2 + (Y - py) ** 2) / (2 * ps * ps)) * inland
    sea = SEA_FLOOR_M * deep
    h = np.where(d < 1.0, ground, sea + BEACH_M * smoothstep(1.02, 1.0, d))
    # the very edge is always sea
    edge = (np.abs(X) > HALF_M - SEA_EDGE_M) | (np.abs(Y) > HALF_M - SEA_EDGE_M)
    h = np.where(edge & (h > SEA_FLOOR_M * 0.5), SEA_FLOOR_M * 0.5, h)
    if "too_big" in SABOTAGE:
        h = np.where(R < HALF_M * 0.995, np.maximum(h, 2.0), h)
    return h.astype(np.float32), coast


def landing_point(coast):
    """On the west beach: along the bearing, the first point inland of the
    coast whose height is between 0.8 and 2 m."""
    th = math.radians(LANDING_DEG)
    r0, c0 = to_index(0.0, 0.0)
    for rad in np.arange(COAST_R_M + 3 * COAST_WARP_M, 0.0, -1.0):
        x, y = rad * math.cos(th), rad * math.sin(th)
        r, c = to_index(x, y)
        if coast[r, c] * 0.99 > rad:
            return x, y
    return -COAST_R_M * 0.9, 0.0


# ================================================================== the trail

def find_trail(h, start, goal):
    """Least-cost path on the GRID_M grid from start to goal (metres)."""
    step = int(GRID_M / CELL_M)
    hs = h[::step, ::step]
    n = hs.shape[0]
    def gi(p):
        r, c = to_index(*p)
        return r // step, c // step
    s, g = gi(start), gi(goal)
    dist = np.full((n, n), np.inf)
    prev = -np.ones((n, n, 2), np.int64)
    dist[s] = 0.0
    q = [(0.0, s)]
    nbr = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
    while q:
        dcur, (r, c) = heapq.heappop(q)
        if (r, c) == g:
            break
        if dcur > dist[r, c]:
            continue
        for dr, dc in nbr:
            rr, cc = r + dr, c + dc
            if not (0 <= rr < n and 0 <= cc < n):
                continue
            if hs[rr, cc] < LAND_MIN_M + 0.3:
                continue
            run = GRID_M * math.hypot(dr, dc)
            grade = abs(float(hs[rr, cc] - hs[r, c])) / run
            if "steep_trail" in SABOTAGE:
                grade = 0.0         # --bite: a straight walk, whatever the hill
            if grade > 0.45:
                continue
            cost = run * (1.0 + (grade / TRAIL_GRADE) ** 4)
            nd = dcur + cost
            if nd < dist[rr, cc]:
                dist[rr, cc] = nd
                prev[rr, cc] = (r, c)
                heapq.heappush(q, (nd, (rr, cc)))
    assert np.isfinite(dist[g]), "no trail from the landing to the arena on this island"
    path = [g]
    while path[-1] != s:
        path.append(tuple(prev[path[-1]]))
    path.reverse()
    pts = [to_metres(r * step, c * step) for r, c in path]
    pts[0], pts[-1] = start, goal
    # Chaikin, three rounds, then resample every metre
    P = np.array(pts, np.float64)
    for _ in range(3):
        Q = [P[0]]
        for a, b in zip(P[:-1], P[1:]):
            Q += [0.75 * a + 0.25 * b, 0.25 * a + 0.75 * b]
        Q.append(P[-1])
        P = np.array(Q)
    seg = np.r_[0.0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
    s_ = np.arange(0.0, seg[-1], 1.0)
    return np.c_[np.interp(s_, seg, P[:, 0]), np.interp(s_, seg, P[:, 1])]


def sample(h, x, y):
    r, c = to_index(x, y)
    r = min(max(r, 0), N - 1); c = min(max(c, 0), N - 1)
    return float(h[r, c])


def trail_grade():
    """The grade the trail is held to (--bite "steep_trail": none -- the
    search walks straight over the hills and the trail takes the raw ground
    under it, unsmoothed and unheld)."""
    return 1e9 if "steep_trail" in SABOTAGE else TRAIL_GRADE


def trail_profile(h, P):
    """The trail's height along its length: the ground under it smoothed over
    40 m, then held to TRAIL_GRADE forward and back (so it neither climbs nor
    drops faster than that), and never under LAND_MIN_M + 0.5."""
    g = np.array([sample(h, x, y) for x, y in P])
    if "steep_trail" in SABOTAGE:
        return np.maximum(g, LAND_MIN_M + 0.5)
    k = 20
    gp = np.pad(g, k, mode="edge")
    z = np.convolve(gp, np.ones(2 * k + 1) / (2 * k + 1), mode="valid")
    grade = trail_grade()
    for i in range(1, len(z)):
        z[i] = min(max(z[i], z[i - 1] - grade), z[i - 1] + grade)
    for i in range(len(z) - 2, -1, -1):
        z[i] = min(max(z[i], z[i + 1] - grade), z[i + 1] + grade)
    return np.maximum(z, LAND_MIN_M + 0.5)


def carve_disc(h, x, y, z, r_flat, r_ramp):
    """Flatten a disc to height z and blend it out over r_ramp."""
    rr = int(r_flat + r_ramp + 2)
    r0, c0 = to_index(x, y)
    rs, cs = slice(max(0, r0 - rr), min(N, r0 + rr + 1)), slice(max(0, c0 - rr), min(N, c0 + rr + 1))
    a = axis_m()
    X = a[cs][None, :] - x
    Y = a[::-1][rs][:, None] - y
    D = np.sqrt(X * X + Y * Y)
    w = 1.0 - smoothstep(r_flat, r_flat + r_ramp, D)
    h[rs, cs] = h[rs, cs] * (1 - w) + z * w


def carve_trail(h, P, Z):
    """Level the trail across: the distance to the trail and the trail's own
    height at the nearest point, per cell, in the trail's bounding box."""
    rr = TRAIL_BED_M + TRAIL_SHOULDER_M + 2
    x0, y0 = P.min(axis=0) - rr; x1, y1 = P.max(axis=0) + rr
    ra, ca = to_index(x0, y1); rb, cb = to_index(x1, y0)
    ra, ca = max(0, ra), max(0, ca); rb, cb = min(N - 1, rb), min(N - 1, cb)
    a = axis_m()
    xs = a[ca: cb + 1]; ys = a[::-1][ra: rb + 1]
    best = np.full((len(ys), len(xs)), np.inf, np.float32)
    zat = np.zeros_like(best)
    for i in range(0, len(P), 2):                    # every 2 m is plenty for a 4 m bed
        x, y = P[i]
        cx = slice(max(0, int(x - xs[0] - rr)), min(len(xs), int(x - xs[0] + rr) + 1))
        cy = slice(max(0, int(ys[0] - y - rr)), min(len(ys), int(ys[0] - y + rr) + 1))
        D = np.sqrt((xs[cx][None, :] - x) ** 2 + (ys[cy][:, None] - y) ** 2).astype(np.float32)
        sub = best[cy, cx]
        m = D < sub
        sub[m] = D[m]
        zs = zat[cy, cx]; zs[m] = Z[i]
    w = 1.0 - smoothstep(TRAIL_BED_M, TRAIL_BED_M + TRAIL_SHOULDER_M, best)
    w[~np.isfinite(best)] = 0.0
    block = h[ra: rb + 1, ca: cb + 1]
    h[ra: rb + 1, ca: cb + 1] = block * (1 - w) + zat * w
    return best, (ra, ca)


# ================================================================== the layers

def slope_deg(h):
    gy, gx = np.gradient(h, CELL_M)
    return np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)


def paint(h, trail_dist, sites, arena):
    s = slope_deg(h)
    n = 0.5 + 0.5 * fbm(N, 24, 3, 5)
    sand = smoothstep(BEACH_M + 1.5, BEACH_M - 0.5, h) * (1 - smoothstep(20, 30, s))
    rock = np.maximum(smoothstep(28, 40, s), smoothstep(150, 170, h))
    mud = np.zeros_like(h)
    if trail_dist is not None:
        (dist, (ra, ca)) = trail_dist
        m = 1.0 - smoothstep(TRAIL_BED_M + 0.5, TRAIL_BED_M + 2.5, dist)
        m[~np.isfinite(dist)] = 0.0
        mud[ra: ra + m.shape[0], ca: ca + m.shape[1]] = np.maximum(mud[ra: ra + m.shape[0], ca: ca + m.shape[1]], m)
    a = axis_m()
    for (x, y, r) in [(sx, sy, SITE_R_M) for sx, sy, _z in sites] + [(arena[0], arena[1], ARENA_R_M)]:
        rr = int(r + 6)
        r0, c0 = to_index(x, y)
        rs, cs = slice(r0 - rr, r0 + rr + 1), slice(c0 - rr, c0 + rr + 1)
        D = np.sqrt((a[cs][None, :] - x) ** 2 + (a[::-1][rs][:, None] - y) ** 2)
        mud[rs, cs] = np.maximum(mud[rs, cs], 1.0 - smoothstep(r - 2, r + 4, D))
    rest = np.clip(1.0 - sand - rock - mud, 0.0, None)
    jungle = rest * smoothstep(0.35, 0.6, n) * smoothstep(BEACH_M + 1, BEACH_M + 8, h)
    grass = rest - jungle
    W = np.stack([sand, grass, jungle, rock, mud]).astype(np.float32)
    W = np.clip(W, 0.0, None)
    tot = W.sum(axis=0)
    tot[tot <= 1e-6] = 1.0
    W /= tot
    # to 8 bits summing to 255: floor, then give the remainder to the largest
    Q = np.floor(W * 255.0).astype(np.int16)
    rem = 255 - Q.sum(axis=0)
    big = np.argmax(W, axis=0)
    if "unnormalised" not in SABOTAGE:
        np.add.at(Q, (big, *np.indices(big.shape)), 0)          # shape check
        for k in range(len(LAYERS)):
            Q[k] += np.where(big == k, rem, 0).astype(np.int16)
    return Q.astype(np.uint8), s


# ================================================================== encode

def encode_height(h):
    step = Z_STEP_M * (2.0 if "bad_scale" in SABOTAGE else 1.0)
    v = np.round(32768.0 + h / step)
    return np.clip(v, 0, 65535).astype(np.uint16)


def decode_height(v):
    return (v.astype(np.float32) - 32768.0) * Z_STEP_M


# ================================================================== build

def build():
    t0 = time.time()
    h, coast = base_terrain()
    lx, ly = landing_point(coast)
    ax, ay = ARENA
    # the arena first, so the search walks up to its ramp
    if "no_arena" not in SABOTAGE:
        carve_disc(h, ax, ay, ARENA_H_M, ARENA_R_M, ARENA_RAMP_M)
    carve_disc(h, lx, ly, max(sample(h, lx, ly), 1.2), 8.0, 12.0)
    P = find_trail(h, (lx, ly), (ax, ay))
    Z = trail_profile(h, P)
    L = len(P)
    sites = []
    for f in SITE_FRACTIONS:
        i = int(f * (L - 1))
        sites.append((float(P[i, 0]), float(P[i, 1]), float(Z[i])))
        # the trail runs level through its clearing (it is cut across it
        # after), then the grade limit eases it in and out of the level
        near = np.hypot(P[:, 0] - P[i, 0], P[:, 1] - P[i, 1]) <= SITE_R_M + 4.0
        Z[near] = Z[i]
    g = trail_grade()
    for i in range(1, L):
        Z[i] = min(max(Z[i], Z[i - 1] - g), Z[i - 1] + g)
    for i in range(L - 2, -1, -1):
        Z[i] = min(max(Z[i], Z[i + 1] - g), Z[i + 1] + g)
    if "no_trail" not in SABOTAGE:
        trail = carve_trail(h, P, Z)
    else:
        trail = None
    if "no_sites" not in SABOTAGE:
        for x, y, z in sites:
            carve_disc(h, x, y, z, SITE_R_M, SITE_RAMP_M)
    # the trail again over the clearings' ramps, so their blend does not tilt it
    if trail is not None:
        trail = carve_trail(h, P, Z)
    if "no_arena" not in SABOTAGE:
        carve_disc(h, ax, ay, ARENA_H_M, ARENA_R_M, ARENA_RAMP_M * 0.4)
    W, s = paint(h, trail, sites, ARENA)
    plan = dict(
        name="MonkeyIsland", vertices=N, cell_m=CELL_M, half_m=HALF_M, z_scale_cm=Z_SCALE_CM,
        z_step_m=Z_STEP_M, sea_level_m=0.0,
        landscape=dict(location_cm=[-HALF_M * 100.0, -HALF_M * 100.0, 0.0], scale=[CELL_M * 100.0, CELL_M * 100.0, Z_SCALE_CM],
                       note="Unreal X east = +x here; Unreal Y = -y here (Unreal is left-handed: +Y is south on this map's north-up drawing)."),
        landing=dict(x=lx, y=ly, z=sample(h, lx, ly)),
        arena=dict(x=ax, y=ay, z=ARENA_H_M, r=ARENA_R_M),
        sites=[dict(x=x, y=y, z=z, r=SITE_R_M, fraction=f) for (x, y, z), f in zip(sites, SITE_FRACTIONS)],
        trail=[[round(float(x), 2), round(float(y), 2), round(float(z), 2)] for (x, y), z in zip(P[::4], Z[::4])],
        trail_length_m=float(L), peak_m=float(h.max()), layers=list(LAYERS))
    print("%6.1fs  built: island %.0f m to the peak, trail %.0f m, %d sites" % (time.time() - t0, h.max(), L, len(sites)))
    return h, W, s, P, Z, plan


# ================================================================== checks

def check(h, W, s, P, Z, plan):
    fails = []
    a = axis_m()
    # 1. the sea all round
    band = int(SEA_EDGE_M / CELL_M)
    edge = np.concatenate([h[:band].ravel(), h[-band:].ravel(), h[:, :band].ravel(), h[:, -band:].ravel()])
    if edge.max() > -1.0:
        fails.append("land at the edge of the world: %.1f m within %.0f m of it" % (edge.max(), SEA_EDGE_M))
    land = float((h > LAND_MIN_M).mean())
    if not 0.35 <= land <= 0.70:
        fails.append("the island is %.0f %% of the landscape, want 35-70" % (land * 100))
    if not 120.0 <= h.max() <= 220.0:
        fails.append("the peak is %.0f m, want 120-220" % h.max())
    # 2. the landing
    lx, ly = plan["landing"]["x"], plan["landing"]["y"]
    def flat_at(x, y, r):
        r0, c0 = to_index(x, y); k = int(r)
        sub = s[r0 - k: r0 + k + 1, c0 - k: c0 + k + 1]
        D = np.sqrt((a[c0 - k: c0 + k + 1][None, :] - x) ** 2 + (a[::-1][r0 - k: r0 + k + 1][:, None] - y) ** 2)
        return float(sub[D <= r * 0.85].max())
    lz = sample(h, lx, ly)
    if not (0.5 <= lz <= 4.0) or flat_at(lx, ly, 6) > FLAT_DEG + 2:
        fails.append("the landing is %.1f m up and %.1f deg steep, want 0.5-4 m and under %.0f" % (lz, flat_at(lx, ly, 6), FLAT_DEG + 2))
    # 3. the trail
    zs = np.array([sample(h, x, y) for x, y in P])
    if zs.min() < LAND_MIN_M:
        fails.append("the trail goes under the sea: %.1f m" % zs.min())
    k = 10
    grades = np.abs(zs[k:] - zs[:-k]) / k
    if grades.max() > TRAIL_GRADE + 0.03:
        i = int(np.argmax(grades))
        fails.append("the trail climbs %.0f %% over 10 m at %.0f m along it, want %.0f or less" % (
            grades.max() * 100, i, TRAIL_GRADE * 100))
    # across: the bed's slope, sampled each 25 m along the trail
    cross = []
    for i in range(5, len(P) - 5, 25):
        d = P[i + 5] - P[i - 5]
        nrm = np.array([-d[1], d[0]]) / max(1e-6, np.hypot(*d))
        za = sample(h, *(P[i] + nrm * TRAIL_BED_M)); zb = sample(h, *(P[i] - nrm * TRAIL_BED_M))
        cross.append(math.degrees(math.atan(abs(za - zb) / (2 * TRAIL_BED_M))))
    if max(cross) > CROSS_DEG:
        fails.append("the trail's bed tilts %.0f deg across, want %.0f or less" % (max(cross), CROSS_DEG))
    # 4. the clearings and the arena
    for st in plan["sites"]:
        f = flat_at(st["x"], st["y"], SITE_R_M)
        if f > FLAT_DEG:
            fails.append("a clearing at %.0f %% of the trail is %.1f deg steep, want %.0f or less" % (st["fraction"] * 100, f, FLAT_DEG))
        if sample(h, st["x"], st["y"]) < 2.0:
            fails.append("a clearing is %.1f m up, want 2" % sample(h, st["x"], st["y"]))
    ar = plan["arena"]
    f = flat_at(ar["x"], ar["y"], ARENA_R_M)
    az = sample(h, ar["x"], ar["y"])
    if f > FLAT_DEG or abs(az - ARENA_H_M) > 1.0:
        fails.append("the arena is %.1f deg steep at %.1f m, want %.0f or less at %.0f" % (f, az, FLAT_DEG, ARENA_H_M))
    end = P[-1]
    if math.hypot(end[0] - ar["x"], end[1] - ar["y"]) > 5.0:
        fails.append("the trail ends %.0f m from the arena" % math.hypot(end[0] - ar["x"], end[1] - ar["y"]))
    # 5. the layers
    tot = W.astype(np.int32).sum(axis=0)
    if tot.min() != 255 or tot.max() != 255:
        fails.append("the layers sum to %d-%d, want 255 everywhere" % (tot.min(), tot.max()))
    mud = W[LAYERS.index("Mud")]
    on = np.array([mud[to_index(x, y)] for x, y in P[::10]])
    if on.min() < 128:
        fails.append("the trail is not painted as mud: %d of 255 at its barest" % on.min())
    # 6. the encoding
    back = decode_height(encode_height(h))
    err = float(np.abs(back - np.clip(h, -256.0, 255.99)).max())
    if err > Z_STEP_M * 0.51:
        fails.append("the heightmap does not decode back: %.3f m off" % err)
    return fails


# ================================================================== write and draw

def write(h, W, plan, out=OUT):
    from PIL import Image
    os.makedirs(out, exist_ok=True)
    v = encode_height(h)
    Image.fromarray(v.astype(np.uint16)).save(os.path.join(out, "H_MonkeyIsland.png"), optimize=True)
    for k, name in enumerate(LAYERS):
        Image.fromarray(W[k].astype(np.uint8)).save(os.path.join(out, "W_MonkeyIsland_%s.png" % name), optimize=True)
    with open(os.path.join(out, "MonkeyIsland_plan.json"), "w") as f:
        json.dump(plan, f, indent=1)
    print("wrote %s" % out)


def draw(h, W, P, plan, path):
    from PIL import Image, ImageDraw
    D = 1344                                     # one pixel a 3 m cell
    step = (N - 1) // D
    hs = h[::step, ::step][:D, :D]
    gy, gx = np.gradient(hs, step * CELL_M)
    light = np.clip(0.5 + (-gx * 0.6 + gy * 0.6) * 1.8, 0.0, 1.0)
    rgb = np.zeros(hs.shape + (3,), np.float32)
    cols = {"Sand": (0.78, 0.70, 0.52), "Grass": (0.45, 0.55, 0.30), "Jungle": (0.18, 0.34, 0.16),
            "Rock": (0.50, 0.48, 0.45), "Mud": (0.45, 0.32, 0.20)}
    for k, name in enumerate(LAYERS):
        rgb += W[k][::step, ::step][:D, :D, None] / 255.0 * np.array(cols[name], np.float32)
    rgb *= (0.55 + 0.6 * light)[..., None]
    water = hs < 0.0
    depth = np.clip(-hs / 30.0, 0.0, 1.0)[..., None]
    rgb = np.where(water[..., None], (1 - depth) * np.array([0.16, 0.42, 0.50]) + depth * np.array([0.05, 0.14, 0.26]), rgb)
    img = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    def px(x, y):
        r, c = to_index(x, y)
        return c / step, r / step
    d.line([px(x, y) for x, y in P[::8]], fill=(240, 220, 120), width=3)
    for st in plan["sites"]:
        x, y = px(st["x"], st["y"]); r = SITE_R_M / (step * CELL_M) + 3
        d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 120, 60), width=3)
    ar = plan["arena"]
    x, y = px(ar["x"], ar["y"]); r = ARENA_R_M / (step * CELL_M) + 3
    d.ellipse([x - r, y - r, x + r, y + r], outline=(220, 40, 40), width=4)
    x, y = px(plan["landing"]["x"], plan["landing"]["y"])
    d.rectangle([x - 6, y - 6, x + 6, y + 6], outline=(255, 255, 255), width=3)
    d.text((12, 12), "JAZIRAT AL-QIRUD  4.03 km   trail %.0f m   peak %.0f m   (square: the boat; circles: the monkeys' clearings; red: the gorilla's temple)" % (
        plan["trail_length_m"], plan["peak_m"]), fill=(255, 255, 255))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    print("drew %s" % path)


def bite():
    cases = [("the sea all round", "too_big", "edge of the world"),
             ("the trail's grade", "steep_trail", "the trail climbs"),
             ("the trail carved", "no_trail", "trail"),
             ("the clearings flat", "no_sites", "a clearing"),
             ("the arena flat", "no_arena", "the arena"),
             ("the layers sum", "unnormalised", "the layers sum"),
             ("the encoding", "bad_scale", "does not decode back")]
    ok = 0
    for label, sab, want in cases:
        SABOTAGE.clear(); SABOTAGE.add(sab)
        try:
            fails = check(*build())
        except AssertionError as e:
            fails = [str(e)]
        hit = [f for f in fails if want in f]
        print("  %-20s %s  %s" % (label, "caught" if hit else "MISSED", (hit or fails or ["passes"])[0][:110]))
        ok += bool(hit)
    SABOTAGE.clear()
    print("%d of %d caught" % (ok, len(cases)))
    return ok == len(cases)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--bite", action="store_true")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    if a.bite:
        sys.exit(0 if bite() else 1)
    h, W, s, P, Z, plan = build()
    fails = check(h, W, s, P, Z, plan)
    if fails:
        print("FAILS:\n  " + "\n  ".join(fails))
        sys.exit(1)
    print("checks pass: the sea all round, the landing, the trail (grade, across, above the sea, mud), "
          "%d clearings and the arena flat, the layers, the encoding" % len(plan["sites"]))
    if a.check:
        return
    write(h, W, plan, a.out)
    draw(h, W, P, plan, os.path.join(DOCS, "monkey-island-map.png"))


if __name__ == "__main__":
    main()
