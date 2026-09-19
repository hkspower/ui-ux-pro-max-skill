#!/usr/bin/env python3
"""JAZIRAT AL-HAJAR -- the stone island, built, and the animals that live on it.

WHAT THIS BUILDS. `L_JaziratAlHajar_Island`: the sixth district of the ring as
an actual island rather than as a ground disc with a different vocabulary on
it. Sea, shallows you can wade, a tide line, a beach, the stone plateau the
fight happens on, rocks standing off the shore -- and, on and around all of
that, animals.

WHY IT IS A SEPARATE SCRIPT. `build_world.py` lays the whole ring down as
flat discs, because a ring of nine flat discs is what the open world is. One
of those nine is called "the stone island" in its own briefing -- "They fall
back to the stone island ... There is nowhere to run out here" -- and a disc
does not say that. Teaching the world builder about water would put a
seabed under eight districts that do not want one. This builds the one
district that does, as a standalone level, exactly as `build_prologue.py`
builds the one level that is not a district at all.

IT DOES NOT MOVE THE MAP. The island is stage index 5, it is already on the
ring, and its extent, its street, its wave positions and its gate come from
`DT_Stages.json` through the same three derivations everything else uses.
Nothing here adds a tenth place or opens the wheel; the canon in
`../ahmed-fighter/CLAUDE.md` is intact.

THE ANIMALS ARE NEW. There are no animals anywhere else in this game, in any
build, in any table. These were asked for. They are ambient only: they have
no health, no team and no fight, they are not in `DT_Fighters`, and nothing
in the combat code knows they exist. Each one carries a flee radius, which is
a number for a Blueprint that has not been written -- the behaviour is not
here and is not pretended at.

3D MODELLING, in the sense this project has always meant it. There is no DCC
tool in this repository and no mesh library; `build_world.py` assembles a
city out of engine primitives, so a gull is assembled the same way -- a body,
a neck, a head, a beak, two wings and two legs, each one a scaled cube,
sphere or cone, positioned in the animal's own local centimetres. That gives
a level you can walk around today, and every part carries the slot name an
artist would replace it through.

    python3 build_island.py             # check, describe, draw the map
    python3 build_island.py --draw PATH # somewhere else to put the picture

Run it inside the Unreal editor and it builds the level instead.
"""

import argparse
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(PROJECT, "Content", "Data")
DOCS = os.path.join(PROJECT, "Docs")
MAPS_DIR = "/Game/Maps"
DATA_DIR = "/Game/Data"
LEVEL_NAME = "L_JaziratAlHajar_Island"
STAGE_NAME = "JaziratAlHajar"
FOLDER = "AHMED"

# ------------------------------------------------- the shared derivations
# Duplicated from Combat/AhmedArena.h and Tools/fab/lay_out_world.py on
# purpose, exactly as every other tool here duplicates them: nothing in this
# repository imports across a runtime boundary, and three copies that agree
# are cheaper to keep honest than one copy nobody can reach.
LENGTH_TO_EXTENT = 1.7
MIN_EXTENT = 6000.0
MAX_EXTENT = 13000.0
EXIT_MARGIN = 200.0
STREET_HALF_WIDTH = 320.0
SITE_RADIUS = 900.0
SPAWN_RADIUS = 300.0
ACTOR_Z = 110.0


def extent_of(stage):
    """AhmedArena::DistrictExtent, in Python."""
    return max(MIN_EXTENT, min(MAX_EXTENT, float(stage["Length"]) * LENGTH_TO_EXTENT))


def spiral(t, extent, phase):
    """AhmedArena::SpiralPoint, in Python."""
    angle = phase + t * 1.35 * 2.0 * math.pi
    radius = extent * (0.18 + 0.68 * t)
    return (math.cos(angle) * radius, math.sin(angle) * radius)


def hash01(n):
    """District.Hash01, in Python. The same integer hash as everywhere else,
    so the island looks the same every time it is built and the same as it
    looks inside the open world."""
    x = n & 0xFFFFFFFF
    x ^= x >> 16; x = (x * 2246822519) & 0xFFFFFFFF
    x ^= x >> 13; x = (x * 3266489917) & 0xFFFFFFFF
    x ^= x >> 16
    return (x & 0xFFFFFF) / 16777215.0


def lerp(a, b, t):
    return a + (b - a) * t


# --------------------------------------------------------------- the island
# Everything is a fraction of the district's own extent, so the island is the
# right size for its stage rather than a size somebody liked.
PLATEAU = 0.86      # stone you stand on and fight on
WET = 0.94          # to here the tide has been and gone
SURF = 1.00         # the waterline
SHALLOWS = 1.34     # wadeable
SEA = 3.00          # how far the water is drawn before the level ends

# heights, centimetres, Z up. The stone stands 2.4 m out of the water, which
# is what makes it an island and not a sandbank.
SHORE_Z = 0.0
WET_Z = -60.0
SURF_Z = -150.0
SHALLOW_Z = -240.0
SEA_Z = -240.0

# the rings the beach is stepped out of. A slope built from concentric discs
# is what the rest of this project would do; smoothing it is a landscape
# artist's job and is not invented here.
BEACH_STEPS = 4
ROCK_COUNT = 22

# The Failaka vocabulary, from Tools/levels/build_world.py, metres -> cm.
RUIN = dict(block="ruin", tall="stone", spacing=1700.0, density=0.45,
            min_w=300.0, max_w=800.0, min_h=160.0, max_h=450.0,
            tall_chance=0.16, tall_min=500.0, tall_max=800.0, yaw_jitter=26)

RIG = dict(pitch=-32, yaw=-108, sun=(1.00, 0.94, 0.82), lux=7.0,
           sky=1.6, fog=(0.72, 0.80, 0.84), fogd=0.008, expo=1.04)


# --------------------------------------------------------------- the animals

def _part(shape, x, y, z, sx, sy, sz, yaw=0.0, slot=""):
    """One primitive of an animal, in its own local centimetres, z from the
    feet up. `slot` is the name an artist replaces this part through."""
    return dict(shape=shape, x=x, y=y, z=z, sx=sx, sy=sy, sz=sz, yaw=yaw,
                slot=slot)


def _gull():
    p = [_part("sphere", 0, 0, 17, 30, 13, 13, slot="body"),
         _part("sphere", 12, 0, 22, 11, 9, 9, slot="neck"),
         _part("sphere", 16, 0, 25, 8, 7, 7, slot="head"),
         _part("cone", 22, 0, 24, 8, 3, 3, slot="beak"),
         _part("box", -16, 0, 19, 10, 9, 3, slot="tail")]
    for s in (1, -1):
        p.append(_part("box", -2, 7 * s, 18, 24, 3, 9, yaw=6 * s, slot="wing"))
        p.append(_part("post", -2, 4 * s, 5, 2, 2, 11, slot="leg"))
    return p


def _tern():
    """Smaller than a gull, sharper in the wing, and it roosts on the rocks
    rather than walking the tide line."""
    p = [_part("sphere", 0, 0, 14, 25, 10, 10, slot="body"),
         _part("sphere", 10, 0, 18, 9, 7, 7, slot="neck"),
         _part("sphere", 13, 0, 21, 7, 6, 6, slot="head"),
         _part("cone", 19, 0, 20, 9, 2.4, 2.4, slot="beak"),
         _part("box", -14, 0, 16, 11, 7, 2.4, slot="tail")]
    for s in (1, -1):
        p.append(_part("box", -1, 6 * s, 15, 26, 2.6, 7, yaw=9 * s, slot="wing"))
        p.append(_part("post", -1, 3.4 * s, 4, 1.8, 1.8, 9, slot="leg"))
    return p


def _cormorant():
    p = [_part("sphere", 0, 0, 21, 40, 15, 15, slot="body"),
         _part("sphere", 12, 0, 30, 10, 9, 10, slot="neck"),
         _part("sphere", 16, 0, 38, 9, 8, 10, slot="neck"),
         _part("sphere", 19, 0, 44, 8, 7, 8, slot="neck"),
         _part("sphere", 22, 0, 47, 9, 7, 7, slot="head"),
         _part("cone", 30, 0, 46, 11, 3, 3, slot="beak"),
         _part("box", -20, 0, 22, 14, 8, 3, slot="tail")]
    for s in (1, -1):
        # half spread, the way a cormorant stands to dry
        p.append(_part("box", -4, 9 * s, 24, 26, 4, 14, yaw=18 * s, slot="wing"))
        p.append(_part("post", -4, 4 * s, 7, 2, 2, 14, slot="leg"))
    return p


def _heron():
    p = [_part("sphere", 0, 0, 64, 34, 14, 15, slot="body"),
         _part("sphere", 8, 0, 74, 10, 9, 12, slot="neck"),
         _part("sphere", 12, 0, 86, 9, 8, 13, slot="neck"),
         _part("sphere", 9, 0, 96, 8, 7, 10, slot="neck"),
         _part("sphere", 12, 0, 101, 8, 7, 7, slot="head"),
         _part("cone", 23, 0, 100, 16, 3.5, 3.5, slot="beak"),
         _part("box", 4, 0, 105, 9, 1.5, 1.5, slot="crest"),
         _part("box", -20, 0, 62, 16, 9, 3, slot="tail")]
    for s in (1, -1):
        p.append(_part("box", -2, 8 * s, 66, 26, 3, 12, yaw=4 * s, slot="wing"))
        p.append(_part("post", 0, 5 * s, 29, 3, 3, 58, slot="leg"))
    return p


def _cat():
    p = [_part("sphere", 0, 0, 20, 36, 14, 14, slot="body"),
         _part("sphere", 14, 0, 21, 15, 13, 13, slot="chest"),
         _part("sphere", 21, 0, 26, 12, 11, 11, slot="head"),
         _part("sphere", 26, 0, 25, 6, 6, 5, slot="muzzle"),
         _part("box", -20, 0, 22, 10, 4, 4, slot="tail"),
         _part("box", -26, 0, 28, 9, 4, 4, yaw=0, slot="tail"),
         _part("box", -29, 0, 35, 4, 4, 9, slot="tail")]
    for s in (1, -1):
        p.append(_part("cone", 22, 4 * s, 32, 4, 3, 6, slot="ear"))
        p.append(_part("post", 13, 5 * s, 6.5, 3, 3, 13, slot="leg"))
        p.append(_part("post", -13, 5 * s, 6.5, 3, 3, 13, slot="leg"))
    return p


def _goat():
    p = [_part("sphere", 0, 0, 50, 64, 26, 30, slot="body"),
         _part("box", 32, 0, 58, 18, 16, 18, slot="neck"),
         _part("sphere", 44, 0, 62, 22, 13, 14, slot="head"),
         _part("box", 53, 0, 58, 10, 9, 9, slot="muzzle"),
         _part("box", 52, 0, 50, 4, 3, 9, slot="beard"),
         _part("box", -32, 0, 56, 8, 4, 6, slot="tail")]
    for s in (1, -1):
        p.append(_part("cone", 42, 5 * s, 72, 4, 4, 18, yaw=-40 * s, slot="horn"))
        p.append(_part("box", 42, 8 * s, 66, 9, 3, 4, slot="ear"))
        p.append(_part("post", 26, 9 * s, 17, 5, 5, 34, slot="leg"))
        p.append(_part("post", -26, 9 * s, 17, 5, 5, 34, slot="leg"))
    return p


def _crab():
    p = [_part("sphere", 0, 0, 5, 16, 12, 5, slot="shell")]
    for s in (1, -1):
        p.append(_part("box", 9, 7 * s, 4, 8, 5, 4, yaw=-24 * s, slot="claw"))
        p.append(_part("post", 5, 3 * s, 8, 1.5, 1.5, 3, slot="eye"))
        for i, dx in enumerate((3, -1, -5, -9)):
            p.append(_part("box", dx, 8 * s, 3, 9, 1.5, 1.5,
                           yaw=(70 + i * 14) * s, slot="leg"))
    return p


def _animal(arabic, band, flocks, per_flock, spread, height, parts, flee, col):
    return dict(arabic=arabic, band=band, flocks=flocks, per_flock=per_flock,
                spread=spread, height=height, parts=parts, flee=flee, col=col)


# WHAT LIVES HERE, and why each one. Failaka is a stone island in the Gulf
# with a known population of feral cats and grazing goats left behind by the
# people who left; the birds are the ones a Gulf shoreline actually holds.
# Each species is tied to a band of the island rather than scattered over it,
# because that is what makes a place read as a habitat and not as a texture.
ANIMALS = {
    "Gull":      _animal("نورس", "shore", 3, (5, 11), 900, 30,
                         _gull(), 700, (232, 228, 214)),
    "Tern":      _animal("خرشنة", "rock", 2, (3, 6), 420, 26,
                         _tern(), 700, (226, 224, 214)),
    "Cormorant": _animal("غاق", "rock", 2, (1, 3), 260, 48,
                         _cormorant(), 900, (44, 48, 54)),
    "Heron":     _animal("بلشون", "shallows", 2, (1, 1), 0, 108,
                         _heron(), 1500, (188, 192, 186)),
    "Cat":       _animal("قط", "ruins", 4, (1, 2), 520, 28,
                         _cat(), 450, (178, 150, 112)),
    "Goat":      _animal("ماعز", "inland", 2, (4, 7), 1100, 70,
                         _goat(), 1100, (146, 132, 116)),
    "Crab":      _animal("سلطعون", "wetsand", 6, (4, 9), 460, 9,
                         _crab(), 160, (168, 96, 72)),
}

# which radii each band occupies, as fractions of the extent, and what the
# ground is under it
BANDS = {
    "inland":   (0.16, 0.68, SHORE_Z),
    "ruins":    (0.38, 0.82, SHORE_Z),
    "wetsand":  (0.88, 0.98, WET_Z),
    "shore":    (0.90, 0.99, WET_Z),
    "shallows": (1.04, 1.26, SHALLOW_Z),
    "rock":     (1.04, 1.30, None),      # None: stands on a rock, not the bed
}

# a few of the gulls are not standing on anything
AIRBORNE = 7
AIR_LOW, AIR_HIGH = 600.0, 1700.0


# ------------------------------------------------------------------ data
def load():
    with open(os.path.join(DATA, "DT_Stages.json"), encoding="utf-8") as f:
        stages = json.load(f)
    stage = next(s for s in stages if s["Name"] == STAGE_NAME)
    with open(os.path.join(DATA, "DT_World.json"), encoding="utf-8") as f:
        world = json.load(f)
    area = next(a for a in world["Areas"] if a["Index"] == stage["Index"])
    return stage, stages, area


# The bearings are fixed by role, exactly as in build_levels.py and for the
# same reason: a standalone level has no neighbours to aim a door at.
BEARING = {"West": 180.0, "East": 0.0, "Door": 90.0}
PATH_SAMPLES = 160


def path_of(extent, phase):
    return [spiral(i / (PATH_SAMPLES - 1.0), extent, phase)
            for i in range(PATH_SAMPLES)]


def dist_to_path(path, x, y):
    best = 1e18
    for i in range(len(path) - 1):
        ax, ay = path[i]
        bx, by = path[i + 1]
        dx, dy = bx - ax, by - ay
        n = dx * dx + dy * dy
        t = 0.0 if n <= 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / n))
        best = min(best, math.hypot(x - (ax + dx * t), y - (ay + dy * t)))
    return best


def sites_of(stage, extent, phase):
    """Where a fight or a gate happens, and how much room it keeps. The
    animals are placed around these, never in them."""
    L = float(stage["Length"])
    out = []
    for w in stage["Waves"]:
        x, y = spiral(min(1.0, w["TriggerDistance"] / L), extent, phase)
        out.append(dict(x=x, y=y, r=SITE_RADIUS, what="wave"))
    for gt in stage["Gates"]:
        x, y = spiral(min(1.0, gt["Distance"] / L), extent, phase)
        out.append(dict(x=x, y=y, r=SITE_RADIUS * 0.7, what="gate"))
    return out


def ground_z_at(r, E):
    """The height of whatever you are standing on, at radius r from the
    island's middle. The beach is built from concentric discs, so this
    returns a STEP height and not a smooth slope -- and check() holds every
    animal to the same function, which is the point of having it."""
    if r <= PLATEAU * E:
        return SHORE_Z
    if r > SURF * E:
        return SHALLOW_Z
    d = (SURF - PLATEAU) * E / BEACH_STEPS
    k = int((SURF * E - r) / d)
    k = max(0, min(BEACH_STEPS - 1, k))
    return lerp(SURF_Z, SHORE_Z, (k + 1.0) / BEACH_STEPS)


# ------------------------------------------------------------- the place
def terrain(stage, E, phase, doors, into):
    def put(kind, shape, x, y, z, sx, sy, sz, yaw=0.0, solid=True):
        into.append(dict(kind=kind, shape=shape, x=x, y=y, z=z,
                         sx=sx, sy=sy, sz=sz, yaw=yaw, solid=solid))

    # --- the sea, then the shallows, then the beach, then the stone. Drawn
    #     outside in and bottom up, so each ring sits on the one before it.
    put("sea", "disc", 0, 0, SEA_Z, SEA * E * 2, SEA * E * 2, 20, solid=False)
    put("shallows", "disc", 0, 0, SHALLOW_Z,
        SHALLOWS * E * 2, SHALLOWS * E * 2, 30, solid=False)
    d = (SURF - PLATEAU) * E / BEACH_STEPS
    for k in range(BEACH_STEPS):
        r = SURF * E - k * d
        z = lerp(SURF_Z, SHORE_Z, (k + 1.0) / BEACH_STEPS)
        put("beach", "disc", 0, 0, z, r * 2, r * 2, 40)
    put("plateau", "disc", 0, 0, SHORE_Z, PLATEAU * E * 2, PLATEAU * E * 2, 60)

    # --- rocks standing off the shore. They are the only thing out there a
    #     bird can stand on, so they are placed before the birds are and the
    #     birds are put on top of named ones.
    rocks = []
    for i in range(ROCK_COUNT):
        a = hash01(i * 7919 + 11) * 2.0 * math.pi
        rr = lerp(SHALLOWS * 0.80, SHALLOWS * 0.99, hash01(i * 104729 + 3)) * E
        w = lerp(220.0, 620.0, hash01(i * 31337 + 7))
        h = lerp(180.0, 520.0, hash01(i * 15485863 + 19))
        x, y = math.cos(a) * rr, math.sin(a) * rr
        # a rock is drawn from the seabed up, so its top is what matters
        put("rock", "box", x, y, SHALLOW_Z + h * 0.5, w, w * 0.82, h,
            yaw=hash01(i * 65537 + 5) * 360.0)
        rocks.append(dict(x=x, y=y, r=w * 0.5, top=SHALLOW_Z + h, i=i))

    # --- a jetty per way out. The exit trigger stays on the district rim at
    #     E - EXIT_MARGIN, where AAhmedGameMode::PlaceArrivingPlayer and
    #     AWaveDirector both expect it; the jetty is what you walk along to
    #     reach it, and check() proves it is continuous.
    for dx, dy, side, *_ in doors:
        a = math.atan2(dy, dx)
        r0, r1 = PLATEAU * E - 200.0, E - EXIT_MARGIN + 260.0
        n = max(2, int((r1 - r0) / 420.0))
        for j in range(n + 1):
            rr = lerp(r0, r1, j / float(n))
            put("jetty", "box", math.cos(a) * rr, math.sin(a) * rr,
                SHORE_Z - 30.0, 460.0, 620.0, 60.0,
                yaw=math.degrees(a))

    # --- the street, on the spiral the fights are already strung along
    path = path_of(E, phase)
    for i in range(len(path) - 1):
        ax, ay = path[i]
        bx, by = path[i + 1]
        mx, my = (ax + bx) * 0.5, (ay + by) * 0.5
        seg = math.hypot(bx - ax, by - ay)
        put("paving", "box", mx, my, SHORE_Z + 6.0, seg + 40.0,
            STREET_HALF_WIDTH * 2, 12.0,
            yaw=math.degrees(math.atan2(by - ay, bx - ax)), solid=False)

    # --- the ruins. The same polar lattice the open world thins with a
    #     per-theme density, so the island's stone stands where it would
    #     stand if you built the whole ring.
    sites = sites_of(stage, E, phase)
    ring = 0
    rr = RUIN["spacing"]
    while rr < PLATEAU * E - 400.0:
        count = max(6, int(2.0 * math.pi * rr / RUIN["spacing"]))
        for c in range(count):
            n = ring * 1000 + c
            if hash01(n * 2654435761 + 17) > RUIN["density"]:
                continue
            a = (c / float(count)) * 2.0 * math.pi + hash01(n + 91) * 0.35
            x, y = math.cos(a) * rr, math.sin(a) * rr
            tall = hash01(n * 40503 + 23) < RUIN["tall_chance"]
            if tall:
                w = lerp(220.0, 360.0, hash01(n * 7 + 3))
                h = lerp(RUIN["tall_min"], RUIN["tall_max"], hash01(n * 11 + 5))
                kind = RUIN["tall"]
            else:
                w = lerp(RUIN["min_w"], RUIN["max_w"], hash01(n * 13 + 7))
                h = lerp(RUIN["min_h"], RUIN["max_h"], hash01(n * 17 + 11))
                kind = RUIN["block"]
            half = w * 0.5
            if dist_to_path(path, x, y) < STREET_HALF_WIDTH + half:
                continue
            if any(math.hypot(s["x"] - x, s["y"] - y) < s["r"] + half for s in sites):
                continue
            if math.hypot(x, y) + half > PLATEAU * E:
                continue
            if any(math.hypot(x - dxx, y - dyy) < 900.0
                   for dxx, dyy, *_ in doors):
                continue
            put(kind, "box", x, y, SHORE_Z + h * 0.5, w, w * 0.78, h,
                yaw=hash01(n * 19 + 13) * RUIN["yaw_jitter"])
        ring += 1
        rr += RUIN["spacing"]
    return rocks, path, sites


# ------------------------------------------------------------ the animals
def fauna(E, phase, path, sites, doors, rocks, solids):
    """Where every animal stands, derived rather than placed by hand.

    A species belongs to a band of the island, not to the island; a flock has
    a centre and a spread; and a candidate position is thrown away and drawn
    again if it lands on the street, in a fight, in a doorway, inside a ruin,
    or on top of another animal. That is the same rejection the open world
    uses for its blocks, and it is what stops a herd of goats standing in the
    middle of the road."""
    out, placed = [], []

    def clear(x, y, rad, band):
        r = math.hypot(x, y)
        lo, hi, _ = BANDS[band]
        if not (lo * E <= r <= hi * E):
            return False
        if any(math.hypot(x - d[0], y - d[1]) < 700.0 for d in doors):
            return False
        if any(math.hypot(x - p[0], y - p[1]) < rad + p[2] for p in placed):
            return False
        if band in ("inland", "ruins"):
            if dist_to_path(path, x, y) < STREET_HALF_WIDTH + 90.0:
                return False
            if any(math.hypot(s["x"] - x, s["y"] - y) < s["r"] + rad
                   for s in sites):
                return False
            if any(math.hypot(x - s[0], y - s[1]) < s[2] + rad for s in solids):
                return False
        return True

    seed = 0

    def h():
        nonlocal seed
        seed += 1
        return hash01(seed * 2654435761 + 1013904223)

    for name in sorted(ANIMALS):
        A = ANIMALS[name]
        lo, hi, _ = BANDS[A["band"]]
        rad = max(60.0, A["height"] * 0.7)
        for f in range(A["flocks"]):
            n = A["per_flock"][0] + int(h() * (A["per_flock"][1] -
                                               A["per_flock"][0] + 1))
            if A["band"] == "rock":
                rock = rocks[int(h() * len(rocks)) % len(rocks)]
                for _ in range(n):
                    for _try in range(24):
                        a, rr = h() * 2 * math.pi, h() * rock["r"] * 0.55
                        x = rock["x"] + math.cos(a) * rr
                        y = rock["y"] + math.sin(a) * rr
                        if any(math.hypot(x - p[0], y - p[1]) < rad + p[2]
                               for p in placed):
                            continue
                        placed.append((x, y, rad))
                        out.append(dict(species=name, x=x, y=y, z=rock["top"],
                                        yaw=h() * 360.0, on="rock%d" % rock["i"],
                                        airborne=False))
                        break
                continue
            ca = h() * 2 * math.pi
            cr = lerp(lo, hi, h()) * E
            cx, cy = math.cos(ca) * cr, math.sin(ca) * cr
            for _ in range(n):
                for _try in range(40):
                    a, rr = h() * 2 * math.pi, h() * A["spread"]
                    x, y = cx + math.cos(a) * rr, cy + math.sin(a) * rr
                    if not clear(x, y, rad, A["band"]):
                        continue
                    placed.append((x, y, rad))
                    out.append(dict(species=name, x=x, y=y,
                                    z=ground_z_at(math.hypot(x, y), E),
                                    yaw=h() * 360.0, on=A["band"],
                                    airborne=False))
                    break

    # a few of the gulls are over the water rather than on it
    for i in range(AIRBORNE):
        a = h() * 2 * math.pi
        rr = lerp(0.5, 1.25, h()) * E
        out.append(dict(species="Gull", x=math.cos(a) * rr, y=math.sin(a) * rr,
                        z=lerp(AIR_LOW, AIR_HIGH, h()), yaw=h() * 360.0,
                        on="air", airborne=True))
    return out


# ----------------------------------------------------------------- plan
def plan(stage, stages, area):
    E = extent_of(stage)
    phase = hash01(stage["Index"] * 977 + 13) * 2.0 * math.pi
    L = float(stage["Length"])

    doors, actors = [], []
    for side in ("West", "East", "Door"):
        link = area.get(side)
        if not link:
            continue
        rad = math.radians(BEARING[side])
        r = E - EXIT_MARGIN
        doors.append((math.cos(rad) * r, math.sin(rad) * r, side, link))

    scenery = []
    rocks, path, sites = terrain(stage, E, phase, doors, scenery)
    solids = [(p["x"], p["y"], max(p["sx"], p["sy"]) * 0.5) for p in scenery
              if p["solid"] and p["kind"] in (RUIN["block"], RUIN["tall"])]
    animals = fauna(E, phase, path, sites, doors, rocks, solids)

    def act(kind, name, x, y, z=ACTOR_Z, **props):
        actors.append(dict(kind=kind, name=name, x=x, y=y, z=z, props=props))

    act("WaveDirector", "WaveDirector_%s" % stage["Name"], 0, 0,
        StageRow=stage["Name"])
    for i, w in enumerate(stage["Waves"]):
        x, y = spiral(min(1.0, w["TriggerDistance"] / L), E, phase)
        act("WaveMarker", "Wave_%d" % i, x, y, SHORE_Z + 10.0)
    for i, gt in enumerate(stage["Gates"]):
        x, y = spiral(min(1.0, gt["Distance"] / L), E, phase)
        act("Gate", "Gate_%d" % i, x, y, GateType=gt["Type"],
            RewardAbility=gt["RewardAbility"],
            RewardExperience=gt["RewardExperience"],
            GateId="%s_Gate_%d" % (stage["Name"], i))
    for dx, dy, side, link in doors:
        dest = stages[link["To"]]
        act("Exit", "Exit_%s" % side, dx, dy, Side=side,
            DestinationStage=dest["Name"],
            RequiredAbility=link.get("RequiredAbility", "None"),
            AfterClearedStage=(stages[link["AfterCleared"]]["Name"]
                               if link.get("AfterCleared", -1) >= 0 else ""))
    west = next((d for d in doors if d[2] == "West"), None)
    if west:
        a = math.atan2(west[1], west[0])
        act("PlayerStart", "PlayerStart", math.cos(a) * (E - EXIT_MARGIN - 500.0),
            math.sin(a) * (E - EXIT_MARGIN - 500.0))
    else:
        act("PlayerStart", "PlayerStart", -SPAWN_RADIUS, 0.0)

    return dict(stage=stage, extent=E, phase=phase, path=path, sites=sites,
                doors=doors, rocks=rocks, scenery=scenery, animals=animals,
                actors=actors)


# ---------------------------------------------------------------- checks
def check(P):
    """What can be proved without an engine. Same discipline as
    Tools/fab/lay_out_world.py and Tools/levels/build_world.py, plus the
    things only an island can get wrong: something standing on water,
    something standing under it, and a way out you cannot walk to."""
    E = P["extent"]
    S = P["scenery"]

    plateau = next(p for p in S if p["kind"] == "plateau")
    assert plateau["z"] > SEA_Z, "the island is under the sea"
    assert plateau["sx"] * 0.5 < E, "the stone reaches past its own district"

    # --- nothing solid stands in the street, in a fight, or off the stone
    on_street = in_fight = off_stone = 0
    for p in S:
        if p["kind"] not in (RUIN["block"], RUIN["tall"]):
            continue
        half = max(p["sx"], p["sy"]) * 0.5
        if math.hypot(p["x"], p["y"]) + half > PLATEAU * E + 1.0:
            off_stone += 1
        if dist_to_path(P["path"], p["x"], p["y"]) < STREET_HALF_WIDTH + half:
            on_street += 1
        if any(math.hypot(s["x"] - p["x"], s["y"] - p["y"]) < s["r"] + half
               for s in P["sites"]):
            in_fight += 1
    assert off_stone == 0, "%d ruins stand off the stone" % off_stone
    assert on_street == 0, "%d ruins stand in the street" % on_street
    assert in_fight == 0, "%d ruins stand where a fight happens" % in_fight

    # --- every way out can be walked to. A jetty is a line of boards from
    #     the stone to the rim; if any two neighbours do not overlap there is
    #     a hole in it, and this is the check that caught the roads in
    #     build_world.py being paved across nothing.
    for dx, dy, side, _link in P["doors"]:
        a = math.atan2(dy, dx)
        boards = sorted((p for p in S if p["kind"] == "jetty"
                         and abs(((math.degrees(math.atan2(p["y"], p["x"]))
                                   - math.degrees(a) + 180) % 360) - 180) < 1.0),
                        key=lambda p: math.hypot(p["x"], p["y"]))
        assert boards, "the %s way out has no jetty" % side
        rs = [math.hypot(p["x"], p["y"]) for p in boards]
        assert rs[0] - boards[0]["sx"] * 0.5 <= PLATEAU * E + 1.0, \
            "the %s jetty does not reach the stone" % side
        assert rs[-1] + boards[-1]["sx"] * 0.5 >= E - EXIT_MARGIN, \
            "the %s jetty stops short of its exit" % side
        for i in range(len(rs) - 1):
            gap = (rs[i + 1] - boards[i + 1]["sx"] * 0.5) - \
                  (rs[i] + boards[i]["sx"] * 0.5)
            assert gap <= 0.0, \
                "the %s jetty has a %.0f cm hole in it" % (side, gap)

    # --- exits sit where the game expects them: on the rim, at the bearing
    #     their role fixes. AAhmedGameMode::PlaceArrivingPlayer computes the
    #     same point, and if these two ever disagree a player arrives inside
    #     the sea.
    for act in P["actors"]:
        if act["kind"] != "Exit":
            continue
        r = math.hypot(act["x"], act["y"])
        assert abs(r - (E - EXIT_MARGIN)) < 1.0, \
            "exit %s is not on the rim" % act["name"]
        want = BEARING[act["props"]["Side"]] % 360.0
        got = math.degrees(math.atan2(act["y"], act["x"])) % 360.0
        assert abs(((got - want + 180) % 360) - 180) < 0.5, \
            "exit %s is at the wrong bearing" % act["name"]

    # --- the animals
    rocks = {"rock%d" % r["i"]: r for r in P["rocks"]}
    floating = sunk = strayed = trespass = crowded = 0
    for i, an in enumerate(P["animals"]):
        A = ANIMALS[an["species"]]
        r = math.hypot(an["x"], an["y"])
        if an["airborne"]:
            assert AIR_LOW - 1 <= an["z"] <= AIR_HIGH + 1, \
                "%s is flying outside the sky" % an["species"]
            assert r <= SHALLOWS * E, "%s is flying off the map" % an["species"]
            continue
        if an["on"].startswith("rock"):
            rock = rocks.get(an["on"])
            assert rock, "%s stands on a rock that is not there" % an["species"]
            if math.hypot(an["x"] - rock["x"], an["y"] - rock["y"]) > rock["r"]:
                strayed += 1
            if abs(an["z"] - rock["top"]) > 1.0:
                floating += 1
            continue
        lo, hi, _ = BANDS[A["band"]]
        if not (lo * E - 1.0 <= r <= hi * E + 1.0):
            strayed += 1
        want = ground_z_at(r, E)
        if abs(an["z"] - want) > 1.0:
            floating += 1
        if an["z"] < SEA_Z - 1.0:
            sunk += 1
        if A["band"] in ("inland", "ruins"):
            if dist_to_path(P["path"], an["x"], an["y"]) < STREET_HALF_WIDTH:
                trespass += 1
            if any(math.hypot(s["x"] - an["x"], s["y"] - an["y"]) < s["r"]
                   for s in P["sites"]):
                trespass += 1
        for j, other in enumerate(P["animals"]):
            if j <= i or other["airborne"]:
                continue
            need = (max(60.0, A["height"] * 0.7) +
                    max(60.0, ANIMALS[other["species"]]["height"] * 0.7)) * 0.5
            if math.hypot(an["x"] - other["x"], an["y"] - other["y"]) < need:
                crowded += 1
    assert floating == 0, "%d animals stand off the ground they are on" % floating
    assert sunk == 0, "%d animals are under the sea" % sunk
    assert strayed == 0, "%d animals are outside the band they belong to" % strayed
    assert trespass == 0, "%d animals stand in the road or in a fight" % trespass
    assert crowded == 0, "%d animals stand inside each other" % crowded

    # --- and no animal is a fighter. Nothing here may ever end up in the
    #     table the combat code reads.
    with open(os.path.join(DATA, "DT_Fighters.csv"), encoding="utf-8") as f:
        rows = f.read()
    for name in ANIMALS:
        assert ("\n%s," % name) not in rows, \
            "%s has found its way into DT_Fighters" % name


def describe(P):
    from collections import Counter
    E = P["extent"]
    st = P["stage"]
    print("%s -- %s / %s" % (LEVEL_NAME, st["DisplayName"],
                             st["DisplayNameArabic"]))
    print("  stone  %.0f m across, standing %.0f cm out of the water"
          % (PLATEAU * E * 2 / 100.0, SHORE_Z - SEA_Z))
    print("  reach  %.0f m to the rim, %.0f m of shallows beyond the surf"
          % (E / 100.0, (SHALLOWS - SURF) * E / 100.0))
    k = Counter(p["kind"] for p in P["scenery"])
    print("  ground " + ", ".join("%s x%d" % (a, b) for a, b in sorted(k.items())))
    print("  ways out " + ", ".join("%s -> %s" % (d[2], d[3]["To"])
                                    for d in P["doors"]))
    c = Counter(a["species"] for a in P["animals"])
    print("  %d animals, %d parts each side of them:" % (len(P["animals"]),
          sum(len(ANIMALS[a["species"]]["parts"]) for a in P["animals"])))
    for name in sorted(c):
        A = ANIMALS[name]
        print("    %-10s %-10s x%-3d  %-9s %3d cm  flees at %4d cm  %d parts"
              % (name, A["arabic"], c[name], A["band"], A["height"],
                 A["flee"], len(A["parts"])))
    air = sum(1 for a in P["animals"] if a["airborne"])
    print("    (%d of the gulls are in the air)" % air)


# ------------------------------------------------------------- the picture
def draw(P, path):
    """A plan and a section, to check it by eye.

    The section is the half that matters here. A top-down map of an island
    cannot show whether the stone is above the water, whether the beach
    steps down to it, or whether a heron is standing on the seabed with its
    body in the air -- and those are the three things an island gets wrong.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("(PIL not available; no picture)")
        return
    E = P["extent"]
    W, H = 1500, 1900
    PLAN_H = 1500
    reach = SHALLOWS * E * 1.06
    sc = W / (reach * 2.0)
    im = Image.new("RGB", (W, H), (10, 14, 18))
    g = ImageDraw.Draw(im)

    def to(x, y):
        return (W / 2 + x * sc, PLAN_H / 2 - y * sc)

    def disc(r, col, outline=None):
        g.ellipse([to(-r, r), to(r, -r)], fill=col, outline=outline)

    disc(SHALLOWS * E, (24, 52, 68))
    disc(SURF * E, (38, 74, 86))
    d = (SURF - PLATEAU) * E / BEACH_STEPS
    for k in range(BEACH_STEPS - 1, -1, -1):
        disc(SURF * E - k * d, (116 - k * 8, 104 - k * 8, 82 - k * 6))
    disc(PLATEAU * E, (74, 70, 62), outline=(122, 114, 96))

    for p in P["scenery"]:
        if p["kind"] == "jetty":
            x, y = to(p["x"], p["y"])
            r = max(1.5, p["sx"] * sc * 0.5)
            g.rectangle([x - r, y - r, x + r, y + r], fill=(96, 78, 54))
        elif p["kind"] == "paving":
            g.point(to(p["x"], p["y"]), fill=(150, 138, 110))
        elif p["kind"] == "rock":
            x, y = to(p["x"], p["y"])
            r = max(2.0, p["sx"] * sc * 0.5)
            g.ellipse([x - r, y - r, x + r, y + r], fill=(58, 60, 58))
        elif p["kind"] in (RUIN["block"], RUIN["tall"]):
            x, y = to(p["x"], p["y"])
            r = max(1.5, p["sx"] * sc * 0.5)
            col = (188, 172, 132) if p["kind"] == RUIN["tall"] else (126, 120, 106)
            g.ellipse([x - r, y - r, x + r, y + r], fill=col)

    for s in P["sites"]:
        x, y = to(s["x"], s["y"])
        r = s["r"] * sc
        g.ellipse([x - r, y - r, x + r, y + r], outline=(200, 90, 70))

    for an in P["animals"]:
        x, y = to(an["x"], an["y"])
        col = ANIMALS[an["species"]]["col"]
        r = 3.0 if not an["airborne"] else 2.0
        if an["airborne"]:
            g.line([x - 5, y, x + 5, y], fill=col)
            g.line([x, y - 3, x, y + 3], fill=col)
        else:
            g.ellipse([x - r, y - r, x + r, y + r], fill=col)

    for a in P["actors"]:
        x, y = to(a["x"], a["y"])
        col = {"WaveDirector": (255, 255, 255), "Gate": (90, 200, 255),
               "Exit": (120, 255, 120), "PlayerStart": (255, 120, 255),
               "WaveMarker": (250, 170, 90)}[a["kind"]]
        g.ellipse([x - 4, y - 4, x + 4, y + 4], fill=col)

    # ------------------------------------------------------- the section
    SY, SH = PLAN_H + 40, H - PLAN_H - 60
    zmid = SY + SH * 0.62
    # The island is 204 m across and stands 2.4 m out of the water. At one
    # to one the whole section is seven pixels of relief, so height is
    # exaggerated hard -- and said so on the picture, because an unlabelled
    # exaggerated section is a lie.
    zs = 5.0
    g.rectangle([0, SY, W, H], fill=(8, 11, 15))

    def sto(x, z):
        return (W / 2 + x * sc, zmid - z * sc * zs)

    g.rectangle([sto(-reach, SEA_Z)[0], sto(0, SEA_Z)[1],
                 sto(reach, SEA_Z)[0], H], fill=(24, 52, 68))
    for k in range(BEACH_STEPS - 1, -1, -1):
        r = SURF * E - k * d
        z = lerp(SURF_Z, SHORE_Z, (k + 1.0) / BEACH_STEPS)
        g.rectangle([sto(-r, z)[0], sto(0, z)[1], sto(r, z)[0], H],
                    fill=(116 - k * 8, 104 - k * 8, 82 - k * 6))
    g.rectangle([sto(-PLATEAU * E, SHORE_Z)[0], sto(0, SHORE_Z)[1],
                 sto(PLATEAU * E, SHORE_Z)[0], H], fill=(74, 70, 62))
    g.line([sto(-reach, SEA_Z), sto(reach, SEA_Z)], fill=(120, 190, 210))

    SLICE = 2400.0                              # the section is a slice, and
                                                # scenery and animals have to
                                                # be cut from the same one or
                                                # a bird appears to stand on
                                                # a rock that was cut away
    for p in P["scenery"]:
        if abs(p["y"]) > SLICE:
            continue
        if p["kind"] == "rock":
            x0, _ = sto(p["x"] - p["sx"] * 0.5, 0)
            x1, _ = sto(p["x"] + p["sx"] * 0.5, 0)
            g.rectangle([x0, sto(0, p["z"] + p["sz"] * 0.5)[1],
                         x1, sto(0, p["z"] - p["sz"] * 0.5)[1]], fill=(58, 60, 58))
        elif p["kind"] in (RUIN["block"], RUIN["tall"]):
            x0, _ = sto(p["x"] - p["sx"] * 0.5, 0)
            x1, _ = sto(p["x"] + p["sx"] * 0.5, 0)
            col = (188, 172, 132) if p["kind"] == RUIN["tall"] else (126, 120, 106)
            g.rectangle([x0, sto(0, p["z"] + p["sz"] * 0.5)[1],
                         x1, sto(0, p["z"] - p["sz"] * 0.5)[1]], fill=col)
    for an in P["animals"]:
        if abs(an["y"]) > SLICE:
            continue
        A = ANIMALS[an["species"]]
        x, y0 = sto(an["x"], an["z"])
        _, y1 = sto(an["x"], an["z"] + A["height"])
        g.line([x, y0, x, y1], fill=A["col"], width=2)
        g.ellipse([x - 2, y1 - 2, x + 2, y1 + 2], fill=A["col"])

    g.text((16, 16), "JAZIRAT AL-HAJAR -- the stone island. Plan above; "
                     "section below through a %.0f m slice, height "
                     "exaggerated %.0fx." % (SLICE * 2 / 100.0, zs),
           fill=(210, 206, 198))
    g.text((16, SY + 8), "sea %d, shallows %d, surf %d, stone %d cm"
           % (SEA_Z, SHALLOW_Z, SURF_Z, SHORE_Z), fill=(150, 170, 180))
    x = 16
    for name in sorted(ANIMALS):
        g.ellipse([x, 62, x + 8, 70], fill=ANIMALS[name]["col"])
        g.text((x + 12, 60), name, fill=(200, 200, 196))
        x += 16 + 7 * len(name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path)
    print("drew", path)


# ----------------------------------------------------------------- editor
MESHES = {"box": "Cube", "post": "Cylinder", "disc": "Cylinder",
          "sphere": "Sphere", "cone": "Cone"}


def build(P):
    import unreal  # noqa: E402  (only importable inside the editor)

    ELL = unreal.EditorLevelLibrary
    EAL = unreal.EditorAssetLibrary
    mesh = {k: unreal.load_asset("/Engine/BasicShapes/%s" % v)
            for k, v in MESHES.items()}

    tables = {}
    for t in ("DT_Stages", "DT_Fighters", "DT_Attacks"):
        p = "%s/%s" % (DATA_DIR, t)
        tables[t] = unreal.load_asset(p) if EAL.does_asset_exist(p) else None
        if not tables[t]:
            unreal.log_warning("%s is not imported yet; the director will be "
                               "placed without it." % t)

    path = "%s/%s" % (MAPS_DIR, LEVEL_NAME)
    unreal.log("Building %s" % path)
    ELL.new_level(path)

    def spawn(cls, name, x, y, z, yaw=0.0, folder="Island"):
        a = ELL.spawn_actor_from_class(cls, unreal.Vector(x, y, z),
                                       unreal.Rotator(0, yaw, 0))
        a.set_actor_label(name)
        a.set_folder_path("%s/%s" % (FOLDER, folder))
        return a

    def piece(name, shape, x, y, z, sx, sy, sz, yaw, solid, folder):
        a = spawn(unreal.StaticMeshActor, name, x, y, z, yaw, folder)
        c = a.get_component_by_class(unreal.StaticMeshComponent)
        c.set_static_mesh(mesh[shape])
        a.set_actor_scale3d(unreal.Vector(sx / 100.0, sy / 100.0, sz / 100.0))
        a.set_mobility(unreal.ComponentMobility.STATIC)
        if not solid:
            c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        return a

    # --- the island itself
    for i, p in enumerate(P["scenery"]):
        folder = {"sea": "Water", "shallows": "Water", "beach": "Ground",
                  "plateau": "Ground", "rock": "Rocks", "jetty": "Ways",
                  "paving": "Street"}.get(p["kind"], "Ruins")
        piece("%s_%d" % (p["kind"], i), p["shape"], p["x"], p["y"], p["z"],
              p["sx"], p["sy"], p["sz"], p.get("yaw", 0.0), p["solid"], folder)

    # --- the animals. One empty actor per animal with its parts attached to
    #     it, so an artist replaces a gull by deleting seven cubes and
    #     dropping a mesh on the parent, and so a Blueprint that learns to
    #     make them flee has one thing to move.
    for i, an in enumerate(P["animals"]):
        A = ANIMALS[an["species"]]
        label = "%s_%02d" % (an["species"], i)
        root = spawn(unreal.Actor, label, an["x"], an["y"], an["z"],
                     an["yaw"], folder="Animals/%s" % an["species"])
        try:
            root.set_actor_tag(0, unreal.Name("Ambient"))
        except Exception:
            pass                       # tags are set differently across versions
        ca = math.cos(math.radians(an["yaw"]))
        sa = math.sin(math.radians(an["yaw"]))
        for j, part in enumerate(A["parts"]):
            wx = an["x"] + part["x"] * ca - part["y"] * sa
            wy = an["y"] + part["x"] * sa + part["y"] * ca
            bit = piece("%s_%s%d" % (label, part["slot"], j), part["shape"],
                        wx, wy, an["z"] + part["z"],
                        part["sx"], part["sy"], part["sz"],
                        an["yaw"] + part["yaw"], False,
                        "Animals/%s" % an["species"])
            bit.attach_to_actor(root, "", unreal.AttachmentRule.KEEP_WORLD,
                                unreal.AttachmentRule.KEEP_WORLD,
                                unreal.AttachmentRule.KEEP_WORLD, False)

    # --- the game in it
    for a in P["actors"]:
        k, pr = a["kind"], a["props"]
        if k == "WaveDirector":
            act = spawn(unreal.WaveDirector, a["name"], a["x"], a["y"], a["z"],
                        folder="Directors")
            act.set_editor_property("stage_row", unreal.Name(pr["StageRow"]))
            for t, prop in (("DT_Stages", "stage_table"),
                            ("DT_Fighters", "fighter_table"),
                            ("DT_Attacks", "attack_table")):
                if tables[t]:
                    act.set_editor_property(prop, tables[t])
        elif k == "PlayerStart":
            spawn(unreal.PlayerStart, a["name"], a["x"], a["y"], a["z"],
                  folder="Directors")
        elif k == "WaveMarker":
            piece(a["name"], "box", a["x"], a["y"], a["z"], 120, 120, 4, 0.0,
                  False, "Markers")
        elif k == "Gate":
            act = spawn(unreal.AbilityGate, a["name"], a["x"], a["y"], a["z"],
                        folder="Gates")
            act.get_component_by_class(unreal.StaticMeshComponent).set_static_mesh(mesh["box"])
            act.set_actor_scale3d(unreal.Vector(1.6, 0.6, 3.0))
            act.set_editor_property("gate_type",
                                    getattr(unreal.GateType, pr["GateType"].upper()))
            act.set_editor_property("reward_ability",
                                    getattr(unreal.Ability, _enum_name(pr["RewardAbility"])))
            act.set_editor_property("reward_experience", int(pr["RewardExperience"]))
            act.set_editor_property("gate_id", unreal.Name(pr["GateId"]))
        elif k == "Exit":
            act = spawn(unreal.AreaExit, a["name"], a["x"], a["y"], a["z"],
                        folder="Exits")
            act.set_editor_property("side", getattr(unreal.AreaSide,
                                                    pr["Side"].upper()))
            act.set_editor_property("destination_stage",
                                    unreal.Name(pr["DestinationStage"]))
            act.set_editor_property("required_ability",
                                    getattr(unreal.Ability,
                                            _enum_name(pr["RequiredAbility"])))
            act.set_editor_property("after_cleared_stage",
                                    unreal.Name(pr["AfterClearedStage"]))

    # --- one sun, warmer and lower than the ring's, because this one is out
    #     on the water with nothing to shade it
    r = RIG
    sun = spawn(unreal.DirectionalLight, "Sun", 0, 0, 22000,
                folder="Lighting")
    sun.set_actor_rotation(unreal.Rotator(r["pitch"], r["yaw"], 0), False)
    sc = sun.get_component_by_class(unreal.DirectionalLightComponent)
    sc.set_intensity(r["lux"])
    sun.set_light_color(unreal.LinearColor(*r["sun"]))
    sc.set_editor_property("atmosphere_sun_light", True)
    sky = spawn(unreal.SkyLight, "SkyLight", 0, 0, 20000, folder="Lighting")
    skc = sky.get_component_by_class(unreal.SkyLightComponent)
    skc.set_intensity(r["sky"])
    skc.set_editor_property("real_time_capture", True)
    spawn(unreal.SkyAtmosphere, "Sky", 0, 0, 0, folder="Lighting")
    fog = spawn(unreal.ExponentialHeightFog, "Fog", 0, 0, 0, folder="Lighting")
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    fc.set_editor_property("fog_density", r["fogd"])
    fc.set_editor_property("fog_inscattering_luminance",
                           unreal.LinearColor(*r["fog"]))

    if not ELL.save_current_level():
        unreal.log_error("Could not save %s" % path)
    else:
        unreal.log("Saved %s: %d ground pieces, %d animals (%d parts), %d actors"
                   % (path, len(P["scenery"]), len(P["animals"]),
                      sum(len(ANIMALS[a["species"]]["parts"])
                          for a in P["animals"]), len(P["actors"])))


def _enum_name(s):
    out = ""
    for i, c in enumerate(s):
        if c.isupper() and i and not s[i - 1].isupper():
            out += "_"
        out += c.upper()
    return out


# ------------------------------------------------------------------- main
if __name__ == "__main__" or True:
    _ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    _ap.add_argument("--draw", default=os.path.join(DOCS, "island-map.png"))
    try:
        _args, _ = _ap.parse_known_args()
    except SystemExit:
        _args = _ap.parse_args([])

    _stage, _stages, _area = load()
    _plan = plan(_stage, _stages, _area)
    check(_plan)

    try:
        import unreal  # noqa: F401
        _in_editor = True
    except ImportError:
        _in_editor = False

    if _in_editor:
        build(_plan)
    else:
        describe(_plan)
        draw(_plan, _args.draw)
        print("\nRun this inside the Unreal editor to build %s." % LEVEL_NAME)
