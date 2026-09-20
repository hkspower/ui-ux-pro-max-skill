#!/usr/bin/env python3
"""SOUQ AL-DAWAR, built: the first area as real meshes, from the tables.

    python3 build_souq.py                plan, check, build the meshes, bake,
                                         place, export, draw the map, render
    python3 build_souq.py --check        the plan and its checks only (no Blender)
    python3 build_souq.py --describe     what it would build, and why
    python3 build_souq.py --bite         break the plan and prove check() notices
    python3 build_souq.py --fast         512 px textures, quick renders
    python3 build_souq.py --no-render    everything but the Cycles renders
    python3 build_souq.py --scene        also the fight: the three fighters
                                         posed in the souq (needs their .blend
                                         in rigs/, from build_fighters.py)
    python3 build_souq.py --out DIR      write somewhere else than the project

WHAT THIS IS. Tools/levels/build_levels.py blocks out L_SouqAlDawar with
engine cubes, and Tools/levels/build_world.py assembles the same district
out of cubes and cylinders as part of the open world -- "every part carries
the slot name an artist would replace it through", because there was no DCC
tool in this repository. There is one now: Tools/blender builds the hero.
This builds the place he lands in, the same way -- in Blender, as modelled
meshes with materials and UVs, exported for Unreal -- and it is the first
piece of the world that is not a primitive.

THE PLACE IS DERIVED, NEVER AUTHORED. Every position here comes through the
same three derivations everything else uses, duplicated here for the reason
every other tool duplicates them (none of them can import another's source
file, and build_levels.py / build_world.py run their whole plan at import):
DistrictExtent for how big the district is, SpiralPoint for the street and
where along it each fight and the gate happen, Hash01 for the lattice of
plots either side. check() then runs build_levels.py's own plan for stage 0
in a subprocess and asserts that every wave, the gate and the three doors
land at the SAME coordinates -- the district and its map cannot disagree.
What stands on the plots is build_world.py's Souq vocabulary, verbatim:
stalls 2.6-5.5 m wide and 2.6-4.2 m high on a 10 m lattice at 72 per cent
density, warehouses 7-10 m at one in eight, a rim wall 2.4-3.2 m gapped at
every way out, flagstone paving on the street.

WHAT THE MESHES LOOK LIKE comes from the browser build's own painting of
the souq (index.html, THEME.souq), which is the canonical art: the arcade
bay of two piers and a low parabolic arch with a coloured banner hung in it
and a lantern at the apex (the mid layer, :2075), mud-brick blocks with a
dome or a crenellated parapet (the far layer), the minaret placed rather
than sprinkled (:2909), worn flagstones on the ground, the cracked wall of a
sealed route (drawGate, :3896), and crates and barrels down the street
(buildProps, :3620), with their colours. Sizes drawn in pixels are taken to
metres through the figure: a standing fighter is drawn 148 px tall for
1.80 m, so a 52 px crate is 63 cm.

NUMBERS THE BROWSER DOES NOT OWN, all of them modelling choices and listed
so nobody mistakes them for canon: a mud brick is 40 x 20 cm and a
flagstone 50 x 50 (the browser's 132 px ground grid is a depth-band
drawing, not a slab); a pier is battered 4 cm; the shop recess behind the
arch is 60 cm deep with a wooden shutter at the back; crenellations are
40 cm wide on a 40 cm gap; the lantern hangs 25 cm; the rim wall is 1.2 m
thick; the ground is sand off the street. The sun for the renders is
build_levels.py's Souq rig (24 degrees up) put where he walks in from.

WHAT LEAVES:
    Content/Models/Souq/SM_Souq_*.fbx      one static mesh per kind, at the
                                           origin, in metres for FBX_SCALE_UNITS
    Content/Models/Souq/SouqAlDawar.gltf   the whole district placed: every
                                           instance as a node sharing its kind's
                                           mesh -- THE 3D model of the area,
                                           openable in any viewer
    Content/Models/Souq/SouqAlDawar_placement.json
                                           every instance (kind, mesh, cm, yaw,
                                           scale) and the gameplay actors it was
                                           checked against
    Content/Textures/Souq/T_Souq_*         the baked, tileable materials
    Docs/souq-map.png                      the plan, drawn, like world-map.png
    Docs/renders/souq-*.png                Cycles, so someone can look at it

RUN INSIDE THE UNREAL EDITOR and it imports the FBXs and puts them into
L_SouqAlDawar, the level build_levels.py made: its Ground cube replaced by
the ground and the street, its AbilityGate carrying the gate wall, every
gameplay actor left where that script put it. Read-reviewed, not run: no
engine has ever built this project.
"""
import os, sys, json, math, time, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(PROJECT, "Content", "Data")
DOCS = os.path.join(PROJECT, "Docs")
LEVELS = os.path.join(PROJECT, "Tools", "levels")
BROWSER = os.path.abspath(os.path.join(PROJECT, "..", "ahmed-fighter"))
STAGE_NAME = "SouqAlDawar"
LEVEL_NAME = "L_SouqAlDawar"
MAPS_DIR = "/Game/Maps"
DATA_DIR = "/Game/Data"
MESH_DIR = "/Game/Models/Souq"
FOLDER = "AHMED"

# ------------------------------------------------- the shared derivations
# Duplicated from Combat/AhmedArena.h and Tools/levels/*.py on purpose: see
# the docstring. check() proves the copies agree.
LENGTH_TO_EXTENT = 1.7
MIN_EXTENT, MAX_EXTENT = 6000.0, 13000.0
EXIT_MARGIN = 200.0
STREET_HALF_WIDTH = 320.0      # cm, build_world.STREET_HALF_WIDTH
STREET_Z_CM = 3.0              # cm, the flagstones stand this proud of the sand; what stands on them stands at it
CLEARANCE = 160.0
SPUR_TUCK = 0.05                # m, how far a spur runs on under the ribbon at its join
PATH_SAMPLES = 140
SITE_RADIUS = 900.0
RIM_SEGMENT = 900.0
RIM_GAP = 1100.0
BEARING = {"West": 180.0, "East": 0.0, "Door": 90.0}
GATE_BOX = (160.0, 60.0, 300.0)   # AbilityGate's cube in build_levels.py: 1.6 x 0.6 x 3.0 m
PX = 2.4                          # cm per browser pixel, the project's constant, for DISTANCES

# build_world.VOCAB["Souq"], centimetres
SOUQ = dict(block="stall", tall="warehouse", rim="wall", paving="flagstone", post=False,
            spacing=1000.0, density=0.72, min_w=260.0, max_w=550.0, min_h=260.0, max_h=420.0,
            tall_chance=0.12, tall_min=700.0, tall_max=1000.0, rim_min=240.0, rim_max=320.0, yaw_jitter=14)

# The browser's souq, index.html THEME.souq and the shapes it calls
BROWSER_ART = dict(
    figure_px=148.0,               # a standing fighter: feet at 0, head top at shY-42 = -148
    bay_w=266.0, pier_w=26.0, pier_h=190.0, arch_peak=229.0, arch_outer=245.0,   # the arcade bay, :2075
    banner_w=60.0, banner_h=92.0, banner_x=40.0, lantern_r=7.0, lantern_x=133.0,
    banners=("#c8102e", "#007a3d", "#e0b34a"),                                    # [i % 3]
    lantern="#ffdc8c",                                                            # rgba(255,220,140,.9)
    brick="#b9784a", brick_dark="#a96a3f", pier="#8e5a33", arch="#a56a3c", skyline="#c98a5c",
    ground=("#a5713f", "#7c5230"), ground_light="#e0b077", ground_dark="#4a2c10",
    wall_gate="#9b8460", crate="#8a6236", crate_edge="#5e4224", barrel="#5d6874",
    crate_px=(52.0, 50.0), barrel_px=(44.0, 56.0),
    minaret_px=280.0, far_building_px=161.0,    # 250-310 tall against roofs of 84-158 + a 40 foot
    dome_chance=0.55,                            # far layer: hashv > 0.55 gets a dome, else crenellations
)
CM_PER_DRAWN_PX = 180.0 / BROWSER_ART["figure_px"]

# modelling choices, see the docstring
BRICK = (0.40, 0.20)
SLAB = 0.50
TILE = 2.0                 # metres of world per texture tile
BATTER = 0.04
RECESS = 0.60
CRENEL = (0.40, 0.40, 0.30)   # width, gap, height
LANTERN_DROP = 0.25
WALL_THICK = 1.20
SUN_PITCH = 24.0           # build_levels RIGS["Souq"].pitch


def extent_of(stage):
    return max(MIN_EXTENT, min(MAX_EXTENT, float(stage["Length"]) * LENGTH_TO_EXTENT))

def spiral(t, extent, phase):
    angle = phase + t * 1.35 * 2.0 * math.pi
    radius = extent * (0.18 + 0.68 * t)
    return (math.cos(angle) * radius, math.sin(angle) * radius)

def hash01(n):
    x = n & 0xFFFFFFFF
    x ^= x >> 16; x = (x * 2246822519) & 0xFFFFFFFF
    x ^= x >> 13; x = (x * 3266489917) & 0xFFFFFFFF
    x ^= x >> 16
    return (x & 0xFFFFFF) / 16777215.0

def hashv(i, seed=0):
    """index.html:hashv, the browser's own scatter."""
    x = math.sin(i * 127.1 + seed * 311.7) * 43758.5453
    return x - math.floor(x)

def lerp(a, b, t): return a + (b - a) * t

def dist_to_path(path, x, y):
    best = 1e18
    for i in range(1, len(path)):
        ax, ay = path[i - 1]; bx, by = path[i]
        abx, aby = bx - ax, by - ay
        len2 = abx * abx + aby * aby
        t = 0.0 if len2 < 1e-9 else max(0.0, min(1.0, ((x - ax) * abx + (y - ay) * aby) / len2))
        best = min(best, math.hypot(x - (ax + abx * t), y - (ay + aby * t)))
    return best

def nearest_on_path(path, x, y):
    return min(path, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)

def _leaves_ribbon(p, u, edge, j, reach=8):
    """Distance along the ray p + u*s at which it first crosses either edge
    of the ribbon, looking only at the edge segments within `reach` samples
    of path vertex j (the spiral's next turn is not this spur's edge). The
    ribbon's own half width if it crosses neither."""
    best = None
    for side in (1, -1):
        E = edge[side]
        for k in range(max(1, j - reach), min(len(E) - 1, j + reach) + 1):
            (x0, y0), (x1, y1) = E[k - 1], E[k]
            dx, dy = x1 - x0, y1 - y0
            den = u[0] * dy - u[1] * dx
            if abs(den) < 1e-9: continue
            tx, ty = x0 - p[0], y0 - p[1]
            sd = (tx * dy - ty * dx) / den; r = (tx * u[1] - ty * u[0]) / den
            if sd > 1e-6 and -1e-6 <= r <= 1.0 + 1e-6 and (best is None or sd < best):
                best = sd
    return best if best is not None else STREET_HALF_WIDTH / 100.0


def banner_of(r, m):
    """A stall's banner as an instance row of its own: the browser's banner
    hung in the arcade bay (THEME.souq), sized to the stall in the stall's
    frame and taken to the world through the stall's yaw and scale ONCE.
    The first version parented it to the stall in Blender and multiplied
    by the scale as well, so 43 of 216 hung in front of the piers -- and it
    was never a row, so the manifest and the editor had no banners at all.
    Centimetres, degrees, and a scale that is the banner's own metres on a
    one-metre quad."""
    A = BROWSER_ART
    w, d, h = m["w"], m["d"], m["h"]
    pier_h = h * A["pier_h"] / A["arch_outer"]
    bw = w * A["banner_w"] / A["bay_w"]; bh = h * A["banner_h"] / A["arch_outer"]
    bx = -w * 0.5 + w * (A["banner_x"] + A["banner_w"] * 0.5) / A["bay_w"]
    bz = pier_h + (h * A["arch_peak"] / A["arch_outer"] - pier_h) * 0.5 - bh * 0.5
    by = -d * 0.5 + RECESS * 100.0 * 0.45
    sx, sy, sz = r["scale"]
    lx, ly, lz = bx * sx, by * sy, bz * sz
    a = math.radians(r["yaw"]); c, s_ = math.cos(a), math.sin(a)
    return dict(slot="Structures", mesh="SM_Souq_Banner%d" % r["banner"], kind="banner",
                x=r["x"] + lx * c - ly * s_, y=r["y"] + lx * s_ + ly * c, z=lz, yaw=r["yaw"],
                scale=(bw / 100.0 * sx, 1.0, bh / 100.0 * sz))


def facing(x, y, tx, ty):
    """Yaw in degrees that points a mesh's front (its local -Y) at (tx, ty)."""
    return math.degrees(math.atan2(tx - x, -(ty - y)))


# ------------------------------------------------------------------- data
def load():
    with open(os.path.join(DATA, "DT_Stages.json"), encoding="utf-8") as f:
        stages = json.load(f)
    with open(os.path.join(DATA, "DT_World.json"), encoding="utf-8") as f:
        world = json.load(f)
    stage = next(s for s in stages if s["Name"] == STAGE_NAME)
    return stages, world, stage


# ------------------------------------------------------------------- plan
def plan():
    stages, world, stage = load()
    idx = stage["Index"]
    L = max(1.0, float(stage["Length"]))
    E = extent_of(stage)
    phase = hash01(idx * 977 + 13) * 2.0 * math.pi
    v = SOUQ
    path = [spiral(i / float(PATH_SAMPLES - 1), E, phase) for i in range(PATH_SAMPLES)]

    # --- the game's own actors for this level, as build_levels.plan_level places them
    actors = []
    def act(kind, name, x, y, z, **props): actors.append(dict(kind=kind, name=name, x=x, y=y, z=z, props=props))
    act("WaveDirector", "WaveDirector", 0.0, 0.0, 0.0, StageRow=stage["Name"])
    sites = []
    for wi, w in enumerate(stage.get("Waves", [])):
        if w["TriggerDistance"] < 0: continue
        t = min(1.0, max(0.0, w["TriggerDistance"] / L)); sx, sy = spiral(t, E, phase)
        act("WaveMarker", "Wave_%d_trigger" % (wi + 1), sx, sy, 2.0, fighters=len(w["Fighters"]))
        sites.append(dict(kind="wave", i=wi, x=sx, y=sy, r=SITE_RADIUS, t=t, fighters=list(w["Fighters"])))
    gate = None
    for gi, g in enumerate(stage.get("Gates", [])):
        t = min(1.0, max(0.0, g["Distance"] / L)); sx, sy = spiral(t, E, phase + 0.5)
        act("Gate", "Gate_%d_%s" % (gi + 1, g["Type"]), sx, sy, 150.0, GateType=g["Type"], RewardAbility=g["RewardAbility"],
            RewardExperience=g["RewardExperience"], GateId="%s_gate%d" % (stage["Name"], gi + 1))
        sites.append(dict(kind="gate", i=gi, x=sx, y=sy, r=SITE_RADIUS * 0.7, gate=g, t=t))
        nx, ny = nearest_on_path(path, sx, sy)
        gate = dict(x=sx, y=sy, yaw=facing(sx, sy, nx, ny), type=g["Type"])
    area = next((a for a in world["Areas"] if a["Index"] == idx), None)
    doors = {}
    for side, back in (("West", "East"), ("East", "West"), ("Door", "West")):
        link = area.get(side) if area else None
        if not link: continue
        dest = stages[link["To"]]; rad = math.radians(BEARING[side]); r = E - EXIT_MARGIN
        x, y = math.cos(rad) * r, math.sin(rad) * r
        after = stages[link["AfterCleared"]]["Name"] if link["AfterCleared"] >= 0 else ""
        act("Exit", "Exit_%s_to_%s" % (side, dest["Name"]), x, y, 300.0, Side=side, DestinationLevel="L_" + dest["Name"],
            DestinationStage=dest["Name"], RequiredAbility=link["RequiredAbility"], AfterClearedStage=after, ArriveAt=back)
        doors[side] = (x, y)
    sx, sy = doors["West"] if "West" in doors else (300.0, 0.0)
    act("PlayerStart", "PlayerStart", sx, sy, 110.0)

    # --- the street: the spiral and a spur to everything on it, as build_world paves it
    street = [dict(a=path[i - 1], b=path[i], width=STREET_HALF_WIDTH * 2.0) for i in range(1, len(path))]
    for s in sites:
        nx, ny = nearest_on_path(path, s["x"], s["y"])
        if math.hypot(s["x"] - nx, s["y"] - ny) >= 100.0:
            street.append(dict(a=(nx, ny), b=(s["x"], s["y"]), width=STREET_HALF_WIDTH * 1.3))
    for dx, dy in doors.values():
        nx, ny = nearest_on_path(path, dx, dy)
        street.append(dict(a=(nx, ny), b=(dx, dy), width=STREET_HALF_WIDTH * 1.6))

    # --- the plots: build_world.blocks_of, verbatim in its numbers, plus what
    #     this needs of each -- which stall variant, and facing the street
    blocks = []
    inner = E - (v["max_w"] * 0.5 + 300.0)
    ring, r = 0, E * 0.13
    while r < E * 0.99:
        n = max(6, int(round(2.0 * math.pi * r / v["spacing"])))
        for k in range(n):
            salt = idx * 7919 + ring * 131 + k * 17
            wobble = (hash01(salt) - 0.5) * (2.0 * math.pi / n) * 0.8
            angle = k * 2.0 * math.pi / n + wobble
            radius = r + (hash01(salt + 1) - 0.5) * v["spacing"] * 0.35
            x, y = math.cos(angle) * radius, math.sin(angle) * radius
            if hash01(salt + 2) > v["density"]: continue
            if math.hypot(x, y) > inner: continue
            tall = hash01(salt + 3) < v["tall_chance"]
            w = lerp(v["min_w"], v["max_w"], hash01(salt + 4))
            dep = lerp(v["min_w"], v["max_w"], hash01(salt + 5))
            h = (lerp(v["tall_min"], v["tall_max"], hash01(salt + 6)) if tall else lerp(v["min_h"], v["max_h"], hash01(salt + 6)))
            half = max(w, dep) * 0.5
            if dist_to_path(path, x, y) < STREET_HALF_WIDTH + half + CLEARANCE: continue
            if any(math.hypot(s["x"] - x, s["y"] - y) < s["r"] + half + CLEARANCE for s in sites): continue
            nx, ny = nearest_on_path(path, x, y)
            yaw = facing(x, y, nx, ny) + (hash01(salt + 7) - 0.5) * v["yaw_jitter"]
            blocks.append(dict(kind=v["tall"] if tall else v["block"], x=x, y=y, w=w, dep=dep, h=h, yaw=yaw,
                               salt=salt, dome=hash01(salt + 8) > BROWSER_ART["dome_chance"], banner=k % 3))
        r += v["spacing"]; ring += 1

    # --- the minaret: placed, not sprinkled. The first tall plot the lattice
    #     made becomes it; the rest stay warehouses.
    minaret = None
    for b in blocks:
        if b["kind"] == "warehouse":
            minaret = dict(x=b["x"], y=b["y"], salt=b["salt"]); b["kind"] = "minaret"; break

    # --- the rim, gapped at every way out
    rim = []
    e = E - 100.0
    n = max(8, int(round(2.0 * math.pi * e / RIM_SEGMENT)))
    for i in range(n):
        ang = 2.0 * math.pi * i / n
        x, y = math.cos(ang) * e, math.sin(ang) * e
        if any(math.hypot(d[0] - x, d[1] - y) < RIM_GAP for d in doors.values()): continue
        h = lerp(v["rim_min"], v["rim_max"], hash01(idx * 31 + i))
        rim.append(dict(x=x, y=y, yaw=math.degrees(ang), h=h))

    # --- the props: index.html buildProps, in the browser's own pixels and
    #     hash, then along the spiral. "Crates and barrels LINE the streets"
    #     (the browser's own comment on buildProps): its z is the depth of a
    #     flat playfield, 0 at the back wall, 1 at the front, and a crate
    #     anywhere across it is in the fight, because in the browser you
    #     smash it mid-fight. This build has no breakable prop and a static
    #     crate in the lane is a wall, so z picks the SIDE of the street --
    #     back is the left of the way through -- and the crate stands at the
    #     kerb, its own half-width in from the edge.
    props = []
    seed = (idx + 1) * 7
    len_px = L / PX
    x_px = 430.0
    while x_px < len_px - 160.0:
        if hashv(x_px, seed + 31) >= 0.30:
            xj = x_px + hashv(x_px, seed + 32) * 110.0
            z = 0.16 + hashv(x_px, seed + 33) * 0.72
            kind = "crate" if hashv(x_px, seed + 34) < 0.5 else "barrel"
            t = min(1.0, xj / len_px)
            cx, cy = spiral(t, E, phase)
            ax, ay = spiral(min(1.0, t + 0.002), E, phase); dx, dy = ax - cx, ay - cy
            dl = math.hypot(dx, dy) or 1.0; lx, ly = -dy / dl, dx / dl           # the left normal
            side = -1.0 if z < 0.5 else 1.0
            across = side * (STREET_HALF_WIDTH - 40.0)
            props.append(dict(kind=kind, x=cx - lx * across, y=cy - ly * across, z=STREET_Z_CM,
                              yaw=math.degrees(math.atan2(dy, dx)) + (hashv(x_px, seed + 35) - 0.5) * 30.0, t=t))
        x_px += 265.0

    # --- the mesh kinds, and which each plot takes
    meshes = {}
    # A plot is 2.6-5.5 m wide and, independently, 2.6-5.5 m deep (the
    # lattice draws them separately), 2.6-4.2 m high or 7-10 for a warehouse.
    # A variant per (width, depth, height) bucket keeps the residual scale on
    # every axis inside 0.80-1.25, which is what check() holds it to: a
    # brick stretched a quarter reads as a brick, one stretched double does
    # not. Twelve stall variants and twelve warehouse variants.
    WIDTHS, DEPTHS = (300.0, 400.0, 500.0), (300.0, 450.0)
    STALL_H, WARE_H = (300.0, 380.0), 850.0
    def near(vals, x): return min(vals, key=lambda a: abs(a - x))
    def variant(kind, w, dep, h, dome=False):
        vw, vd = near(WIDTHS, w), near(DEPTHS, dep)
        if kind == "stall":
            vh = near(STALL_H, h)
            name = "SM_Souq_Stall_W%dD%dH%d" % (vw / 100, vd / 10, vh / 10)
            meshes.setdefault(name, dict(kind="stall", w=vw, d=vd, h=vh))
            return name, (w / vw, dep / vd, h / vh)
        if kind == "warehouse":
            vh = WARE_H
            name = "SM_Souq_Warehouse_W%dD%d_%s" % (vw / 100, vd / 10, "Dome" if dome else "Crenel")
            meshes.setdefault(name, dict(kind="warehouse", w=vw, d=vd, h=vh, dome=dome))
            return name, (w / vw, dep / vd, h / vh)
        raise KeyError(kind)
    for b in blocks:
        if b["kind"] == "minaret":
            b["mesh"], b["scale"] = "SM_Souq_Minaret", (1.0, 1.0, 1.0)
        else:
            b["mesh"], b["scale"] = variant(b["kind"], b["w"], b["dep"], b["h"], b.get("dome", False))
    for w in rim:
        vh = 240.0 if w["h"] < 280.0 else 320.0
        w["mesh"], w["scale"] = "SM_Souq_Wall_H%d" % (vh / 10), (1.0, 1.0, w["h"] / vh)
        meshes.setdefault(w["mesh"], dict(kind="wall", w=RIM_SEGMENT * 0.92, d=WALL_THICK * 100.0, h=vh))
    tall_mid = 0.5 * (v["tall_min"] + v["tall_max"])
    minaret_h = tall_mid * BROWSER_ART["minaret_px"] / BROWSER_ART["far_building_px"]
    # the browser's minaret(x, y, h) takes h as the SHAFT and draws the cap
    # to 1.16 h and the finial to 1.22 h; the mesh's own height is the whole
    meshes["SM_Souq_Minaret"] = dict(kind="minaret", w=minaret_h * 0.164, d=minaret_h * 0.164, h=minaret_h * 1.22, shaft=minaret_h)
    if minaret: minaret["h"] = minaret_h
    meshes["SM_Souq_GateWall"] = dict(kind="gate", w=GATE_BOX[0], d=GATE_BOX[1], h=GATE_BOX[2])
    cw, ch = (p * CM_PER_DRAWN_PX for p in BROWSER_ART["crate_px"])
    bw, bh = (p * CM_PER_DRAWN_PX for p in BROWSER_ART["barrel_px"])
    meshes["SM_Souq_Crate"] = dict(kind="crate", w=cw, d=cw, h=ch)
    meshes["SM_Souq_Barrel"] = dict(kind="barrel", w=bw, d=bw, h=bh)
    meshes["SM_Souq_Ground"] = dict(kind="ground", w=E * 2, d=E * 2, h=0.0)
    for i in range(3):      # the three banner colours: a one-metre quad each, scaled per stall
        meshes["SM_Souq_Banner%d" % i] = dict(kind="banner", w=100.0, d=0.0, h=100.0)
    meshes["SM_Souq_Street"] = dict(kind="street", w=E * 2, d=E * 2, h=3.0)
    for p in props:
        p["mesh"] = "SM_Souq_Crate" if p["kind"] == "crate" else "SM_Souq_Barrel"; p["scale"] = (1.0, 1.0, 1.0)
    # a crate in a fight is a wall in it: dropped by build_world's own block
    # test (a site's radius plus the thing's half-width), like a plot would be
    props = [p for p in props if all(math.hypot(s["x"] - p["x"], s["y"] - p["y"]) > SITE_RADIUS + max(meshes[p["mesh"]]["w"], meshes[p["mesh"]]["d"]) * 0.5
                                     for s in sites)]
    if gate:
        gate["mesh"], gate["scale"] = "SM_Souq_GateWall", (1.0, 1.0, 1.0)

    return dict(stage=stage, idx=idx, E=E, phase=phase, path=path, sites=sites, doors=doors, actors=actors,
                street=street, blocks=blocks, rim=rim, props=props, gate=gate, minaret=minaret, meshes=meshes, vocab=v)


def instances(P):
    """Everything placed, one row each: what the manifest and the glTF carry."""
    out = [dict(slot="Ground", mesh="SM_Souq_Ground", x=0.0, y=0.0, z=0.0, yaw=0.0, scale=(1, 1, 1)),
           dict(slot="Street", mesh="SM_Souq_Street", x=0.0, y=0.0, z=0.0, yaw=0.0, scale=(1, 1, 1))]
    for b in P["blocks"]:
        out.append(dict(slot="Structures" if b["kind"] != "minaret" else "Landmark", mesh=b["mesh"],
                        x=b["x"], y=b["y"], z=0.0, yaw=b["yaw"], scale=b["scale"], kind=b["kind"], banner=b.get("banner", 0)))
        if b["kind"] == "stall":
            out.append(banner_of(out[-1], P["meshes"][b["mesh"]]))
    for w in P["rim"]:
        out.append(dict(slot="Rim", mesh=w["mesh"], x=w["x"], y=w["y"], z=0.0, yaw=w["yaw"], scale=w["scale"], kind="wall"))
    for p in P["props"]:
        out.append(dict(slot="Props", mesh=p["mesh"], x=p["x"], y=p["y"], z=p["z"], yaw=p["yaw"], scale=p["scale"], kind=p["kind"]))
    if P["gate"]:
        g = P["gate"]
        out.append(dict(slot="Gates", mesh=g["mesh"], x=g["x"], y=g["y"], z=0.0, yaw=g["yaw"], scale=g["scale"], kind="gate"))
    return out


# ------------------------------------------------------------------ check
def _build_levels_stage0():
    """build_levels.py's own plan for this stage, run in a subprocess (the
    module runs its whole plan at import) and read back as JSON."""
    code = ("import sys, json; sys.path.insert(0, %r); import io, contextlib\n"
            "buf = io.StringIO()\n"
            "with contextlib.redirect_stdout(buf):\n"
            "    import build_levels as BL\n"
            "    stages, world = BL.load(); st = next(s for s in stages if s['Name'] == %r)\n"
            "    actors, E, phase = BL.plan_level(st, world, stages)\n"
            "print('@@' + json.dumps(dict(E=E, phase=phase, actors=actors)))\n") % (LEVELS, STAGE_NAME)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=LEVELS)
    line = next((l for l in out.stdout.split("\n") if l.startswith("@@")), None)
    assert line, "build_levels.py did not answer:\n" + out.stderr[-800:]
    return json.loads(line[2:])


def check(P, against_levels=True):
    """Proved to bite, every one -- see bite()."""
    E, path, sites = P["E"], P["path"], P["sites"]
    # 1. the district and its map agree: build_levels' plan for the same stage
    if against_levels:
        theirs = _build_levels_stage0()
        assert abs(theirs["E"] - E) < 1e-6 and abs(theirs["phase"] - P["phase"]) < 1e-9, "extent or phase differs from build_levels.py"
        mine = {a["name"]: (a["x"], a["y"]) for a in P["actors"]}
        for a in theirs["actors"]:
            if a["kind"] in ("WaveMarker", "Gate", "Exit", "PlayerStart"):
                assert a["name"] in mine, "build_levels.py places %s and this plan does not" % a["name"]
                dx = math.hypot(mine[a["name"]][0] - a["x"], mine[a["name"]][1] - a["y"])
                assert dx < 1.0, "%s is %.0f cm from where build_levels.py puts it" % (a["name"], dx)
    # 2. nothing solid on the street, in a fight, or off the edge
    on_street = in_fight = off_edge = 0
    for b in P["blocks"]:
        half = max(b["w"], b["dep"]) * 0.5
        if math.hypot(b["x"], b["y"]) + half > E: off_edge += 1
        if dist_to_path(path, b["x"], b["y"]) < STREET_HALF_WIDTH + half: on_street += 1
        if any(math.hypot(s["x"] - b["x"], s["y"] - b["y"]) < s["r"] + half for s in sites): in_fight += 1
    assert off_edge == 0, "%d blocks stand off the edge" % off_edge
    assert on_street == 0, "%d blocks stand in the street" % on_street
    assert in_fight == 0, "%d blocks stand where a fight happens" % in_fight
    # 3. every way out is a gap in the rim
    for side, (dx, dy) in P["doors"].items():
        near = [w for w in P["rim"] if math.hypot(w["x"] - dx, w["y"] - dy) < 400.0]
        assert not near, "the %s door is walled up" % side
        r = math.hypot(dx, dy); assert abs(r - (E - EXIT_MARGIN)) < 1.0, "the %s door is not on the rim" % side
    # 4. the way through stays inside
    for k in range(101):
        r = math.hypot(*spiral(k / 100.0, E, P["phase"]))
        assert 0.17 * E < r < 0.87 * E, "the way through leaves the district at t=%.2f" % (k / 100.0)
    # 5. the sizes drawn in the browser came through the figure, not the distance constant
    m = P["meshes"]["SM_Souq_Crate"]
    assert abs(m["w"] - BROWSER_ART["crate_px"][0] * CM_PER_DRAWN_PX) < 1e-6, "the crate is not the browser's crate"
    # 6. every prop is at the kerb -- on the street, out of its middle lane, and out of every fight
    for p in P["props"]:
        m = P["meshes"][p["mesh"]]; half = max(m["w"], m["d"]) * 0.5
        for s in sites:
            assert math.hypot(s["x"] - p["x"], s["y"] - p["y"]) > SITE_RADIUS + half, "a %s stands in a fight (%s %d)" % (p["kind"], s["kind"], s.get("i", 0))
        assert p["z"] == STREET_Z_CM, "a %s stands %.0f cm under the street" % (p["kind"], STREET_Z_CM - p["z"])
        d = dist_to_path(path, p["x"], p["y"])
        assert d + half <= STREET_HALF_WIDTH + 1.0, "a %s stands %.0f cm off the street's centre line" % (p["kind"], d)
        assert d - half >= STREET_HALF_WIDTH * 0.5, "a %s stands in the middle of the street, %.0f cm from its centre line" % (p["kind"], d)
        for b in P["blocks"]:
            assert math.hypot(b["x"] - p["x"], b["y"] - p["y"]) > max(b["w"], b["dep"]) * 0.5, "a %s is inside a %s" % (p["kind"], b["kind"])
    # 7. the gate: off the street (a sealed route is beside the road), inside the district, the actor's own box
    if P["gate"]:
        g = P["gate"]; m = P["meshes"][g["mesh"]]
        assert dist_to_path(path, g["x"], g["y"]) > STREET_HALF_WIDTH, "the gate stands in the street"
        assert math.hypot(g["x"], g["y"]) < E, "the gate is off the edge"
        assert (m["w"], m["d"], m["h"]) == GATE_BOX, "the gate wall is not the AbilityGate's box"
    # 8. the minaret is the tallest thing, and there is exactly one
    tallest = max(P["meshes"].items(), key=lambda kv: kv[1]["h"])[0]
    assert tallest == "SM_Souq_Minaret", "the tallest mesh is %s, not the minaret" % tallest
    assert sum(1 for b in P["blocks"] if b["kind"] == "minaret") == 1, "there must be exactly one minaret"
    # 9. a variant is never far from the plot it stands on
    for b in P["blocks"]:
        for sc in b["scale"]:
            assert 0.80 <= sc <= 1.25, "%s at (%.0f, %.0f) is scaled %.2f from its variant" % (b["kind"], b["x"], b["y"], sc)
    print("checked: the plan agrees with build_levels.py to the centimetre, nothing solid stands in")
    print("the street or a fight or off the edge, every door is a gap, the way through stays in,")
    print("every crate is on the street, the gate is beside the road in its actor's box, one minaret.")


def bite():
    """Each check, broken on purpose."""
    cases = []
    def case(label, mutate, expect):
        P = plan(); mutate(P)
        try:
            check(P, against_levels=("levels" in label)); cases.append((label, False, "did not bite"))
        except AssertionError as e:
            cases.append((label, expect in str(e), str(e)[:90]))
    def move_wave(P): a = next(a for a in P["actors"] if a["kind"] == "WaveMarker"); a["x"] += 50.0
    def onto_street(P): b = P["blocks"][0]; nx, ny = nearest_on_path(P["path"], b["x"], b["y"]); b["x"], b["y"] = nx, ny
    def into_fight(P):
        # inside the first wave's circle (r 900) but beside the street, not on
        # it: 650 cm out along the street's normal. On the site itself the
        # street check would fire first and mask this one.
        s = P["sites"][0]; b = P["blocks"][1]
        ax, ay = spiral(max(0.0, s["t"] - 0.002), P["E"], P["phase"]); bx, by = spiral(min(1.0, s["t"] + 0.002), P["E"], P["phase"])
        dx, dy = bx - ax, by - ay; dl = math.hypot(dx, dy) or 1.0
        b["x"], b["y"] = s["x"] - dy / dl * 650.0, s["y"] + dx / dl * 650.0
        b["w"] = b["dep"] = 300.0
    def off_edge(P): b = P["blocks"][2]; b["x"] = P["E"] + 10.0; b["y"] = 0.0
    def wall_door(P): dx, dy = P["doors"]["East"]; P["rim"].append(dict(x=dx, y=dy, yaw=0.0, h=300.0, mesh="SM_Souq_Wall_H32", scale=(1, 1, 1)))
    def crate_off(P): p = P["props"][0]; p["x"] += 900.0
    def crate_in_fight(P): s = next(s for s in P["sites"] if s["kind"] == "wave"); p = P["props"][0]; p["x"], p["y"] = s["x"] + 200.0, s["y"]
    def crate_sunk(P): P["props"][0]["z"] = 0.0
    def crate_in_lane(P): p = P["props"][0]; p["x"], p["y"] = nearest_on_path(P["path"], p["x"], p["y"])
    def gate_on_street(P): g = P["gate"]; nx, ny = nearest_on_path(P["path"], g["x"], g["y"]); g["x"], g["y"] = nx, ny
    def gate_box(P): P["meshes"]["SM_Souq_GateWall"]["w"] = 200.0
    def two_minarets(P): P["blocks"][3]["kind"] = "minaret"
    def short_minaret(P): P["meshes"]["SM_Souq_Minaret"]["h"] = 100.0
    def bad_variant(P): P["blocks"][0]["scale"] = (1.5, 1.0, 1.0)
    def crate_by_distance(P): P["meshes"]["SM_Souq_Crate"]["w"] = BROWSER_ART["crate_px"][0] * PX
    case("agrees with build_levels", move_wave, "from where build_levels")
    case("block on the street", onto_street, "in the street")
    case("block in a fight", into_fight, "fight")
    case("block off the edge", off_edge, "off the edge")
    case("door walled up", wall_door, "walled up")
    case("crate off the street", crate_off, "off the street")
    case("crate in the lane", crate_in_lane, "middle of the street")
    case("gate on the street", gate_on_street, "gate stands in the street")
    case("gate not the actor's box", gate_box, "AbilityGate")
    case("two minarets", two_minarets, "exactly one")
    case("minaret not tallest", short_minaret, "tallest")
    case("variant too far from plot", bad_variant, "scaled")
    case("crate sized by distance", crate_by_distance, "browser's crate")
    case("crate in a fight", crate_in_fight, "in a fight")
    case("crate under the street", crate_sunk, "under the street")
    print("\n%-28s %s" % ("check", "when the plan is broken"))
    for label, ok, msg in cases:
        print("  %-26s %s  %s" % (label, "BITES " if ok else "SILENT", msg))
    n = sum(1 for _, ok, _ in cases if ok); print("  %d of %d bite" % (n, len(cases)))
    return n == len(cases)


def describe(P):
    st = P["stage"]
    kinds = {}
    for b in P["blocks"]: kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
    print("\n%s (%s): %d cm long, a district %.0f m across, phase %.3f rad" % (
        st["DisplayName"], st["Name"], st["Length"], P["E"] * 2 / 100.0, P["phase"]))
    print("  the way through: %d samples of the spiral, %d spurs" % (PATH_SAMPLES, len(P["street"]) - PATH_SAMPLES + 1))
    for s in P["sites"]:
        print("  %-5s t=%.3f at (%6.0f, %6.0f)  %s" % (s["kind"], s.get("t", 0), s["x"], s["y"],
              " ".join(s.get("fighters", [])) if s["kind"] == "wave" else s["gate"]["Type"]))
    for side, (x, y) in P["doors"].items():
        print("  door %-5s at (%6.0f, %6.0f), bearing %.0f" % (side, x, y, BEARING[side]))
    print("  plots: " + ", ".join("%s %d" % kv for kv in sorted(kinds.items())) + "; rim %d segments; props %d (%d crates, %d barrels)" % (
        len(P["rim"]), len(P["props"]), sum(1 for p in P["props"] if p["kind"] == "crate"), sum(1 for p in P["props"] if p["kind"] == "barrel")))
    if P["minaret"]:
        print("  minaret at (%.0f, %.0f), %.1f m" % (P["minaret"]["x"], P["minaret"]["y"], P["minaret"]["h"] / 100.0))
    if P["gate"]:
        print("  gate %s at (%.0f, %.0f), facing the street" % (P["gate"]["type"], P["gate"]["x"], P["gate"]["y"]))
    print("  mesh kinds (%d):" % len(P["meshes"]))
    use = {}
    for i in instances(P): use[i["mesh"]] = use.get(i["mesh"], 0) + 1
    for name, m in sorted(P["meshes"].items()):
        print("    %-26s %-9s %6.2f x %6.2f x %5.2f m  x%d" % (name, m["kind"], m["w"] / 100, m["d"] / 100, m["h"] / 100, use.get(name, 0)))


def draw(P, path):
    """A top-down picture of the plan, like Docs/world-map.png."""
    from PIL import Image, ImageDraw
    E = P["E"]; W = 1600; sc = W / (2.0 * E + 800.0)
    im = Image.new("RGB", (W, W), (16, 15, 14)); g = ImageDraw.Draw(im)
    def to(x, y): return (W / 2 + x * sc, W / 2 - y * sc)
    g.ellipse([to(-E, E), to(E, -E)], fill=(52, 42, 30), outline=(90, 74, 52))
    for s in P["street"]:
        g.line([to(*s["a"]), to(*s["b"])], fill=(150, 120, 80), width=max(1, int(s["width"] * sc)))
    for w in P["rim"]:
        g.ellipse([to(w["x"] - 60, w["y"] + 60), to(w["x"] + 60, w["y"] - 60)], fill=(120, 104, 84))
    for b in P["blocks"]:
        col = {"stall": (176, 132, 88), "warehouse": (196, 154, 84), "minaret": (255, 230, 150)}[b["kind"]]
        a = math.radians(b["yaw"]); hw, hd = b["w"] * 0.5, b["dep"] * 0.5
        pts = [to(b["x"] + cx * math.cos(a) - cy * math.sin(a), b["y"] + cx * math.sin(a) + cy * math.cos(a))
               for cx, cy in ((-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd))]
        g.polygon(pts, fill=col)
        if b["kind"] == "minaret":
            g.ellipse([to(b["x"] - 500, b["y"] + 500), to(b["x"] + 500, b["y"] - 500)], outline=(255, 230, 150))
    for p in P["props"]:
        x, y = to(p["x"], p["y"]); g.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(220, 190, 120) if p["kind"] == "crate" else (150, 170, 190))
    for s in P["sites"]:
        x, y = to(s["x"], s["y"]); r = s["r"] * sc
        g.ellipse([x - r, y - r, x + r, y + r], outline=(250, 170, 90) if s["kind"] == "wave" else (90, 200, 255))
    if P["gate"]:
        x, y = to(P["gate"]["x"], P["gate"]["y"]); g.rectangle([x - 4, y - 4, x + 4, y + 4], fill=(90, 200, 255))
    for side, (dx, dy) in P["doors"].items():
        x, y = to(dx, dy); g.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(120, 255, 120)); g.text((x + 8, y - 6), side, fill=(200, 255, 200))
    g.text((16, 16), "SOUQ AL-DAWAR, built: the street on the spiral, stalls and warehouses either side, the rim gapped", fill=(220, 220, 220))
    g.text((16, 32), "at every way out, crates down the street, the cracked wall beside the road, one minaret.", fill=(220, 220, 220))
    os.makedirs(os.path.dirname(path), exist_ok=True); im.save(path); print("drew", path)


# ================================================================== Blender
def _hex(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)) + (1.0,)

def _lin(rgba):
    return tuple((c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4) for c in rgba[:3]) + (1.0,)


class Souq:
    """The Blender half: materials, meshes, placement, export, renders."""

    def __init__(self, P, out=None, fast=False):
        import bpy
        self.bpy = bpy; self.P = P; self.fast = fast
        self.models = os.path.join(out, "Models", "Souq") if out else os.path.join(PROJECT, "Content", "Models", "Souq")
        self.textures = os.path.join(out, "Textures", "Souq") if out else os.path.join(PROJECT, "Content", "Textures", "Souq")
        self.renders = os.path.join(out, "renders") if out else os.path.join(DOCS, "renders")
        self.docs = out or DOCS
        for d in (self.models, self.textures, self.renders): os.makedirs(d, exist_ok=True)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene; sc.unit_settings.system = "METRIC"; sc.unit_settings.length_unit = "METERS"
        self.mats = {}; self.kinds = {}; self.placed = []

    # ------------------------------------------------------------ materials
    def _periodic(self, nt, uv_out):
        """UV (0..1) -> a point on a 4-torus, so a noise texture sampled there
        repeats exactly across the tile. Returns (vector, w) sockets."""
        sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(uv_out, sep.inputs[0])
        outs = []
        for i in (0, 1):
            m = nt.nodes.new("ShaderNodeMath"); m.operation = "MULTIPLY"; m.inputs[1].default_value = 2.0 * math.pi
            nt.links.new(sep.outputs[i], m.inputs[0])
            c = nt.nodes.new("ShaderNodeMath"); c.operation = "COSINE"; nt.links.new(m.outputs[0], c.inputs[0])
            s = nt.nodes.new("ShaderNodeMath"); s.operation = "SINE"; nt.links.new(m.outputs[0], s.inputs[0])
            outs.append((c.outputs[0], s.outputs[0]))
        comb = nt.nodes.new("ShaderNodeCombineXYZ")
        nt.links.new(outs[0][0], comb.inputs[0]); nt.links.new(outs[0][1], comb.inputs[1]); nt.links.new(outs[1][0], comb.inputs[2])
        return comb.outputs[0], outs[1][1]

    def _noise(self, nt, uv_out, scale, detail=3.0):
        vec, w = self._periodic(nt, uv_out)
        n = nt.nodes.new("ShaderNodeTexNoise"); n.noise_dimensions = "4D"
        n.inputs["Scale"].default_value = scale; n.inputs["Detail"].default_value = detail
        nt.links.new(vec, n.inputs["Vector"]); nt.links.new(w, n.inputs["W"])
        return n.outputs["Fac"]

    def material(self, name, kind):
        """A procedural material in tile space: UV * TILE is metres."""
        bpy = self.bpy
        if name in self.mats: return self.mats[name]
        mat = bpy.data.materials.new(name); mat.use_nodes = True
        nt = mat.node_tree; bsdf = nt.nodes["Principled BSDF"]
        uv = nt.nodes.new("ShaderNodeUVMap"); uv.uv_map = "UVMap"
        metres = nt.nodes.new("ShaderNodeVectorMath"); metres.operation = "SCALE"; metres.inputs["Scale"].default_value = TILE
        nt.links.new(uv.outputs["UV"], metres.inputs[0])
        A = BROWSER_ART
        def mix(a, b, fac):
            m = nt.nodes.new("ShaderNodeMix"); m.data_type = "RGBA"
            m.inputs["A"].default_value = a; m.inputs["B"].default_value = b
            nt.links.new(fac, m.inputs["Factor"]); return m.outputs["Result"]
        def bump(height, strength, dist=0.004):
            b = nt.nodes.new("ShaderNodeBump"); b.inputs["Strength"].default_value = strength; b.inputs["Distance"].default_value = dist
            nt.links.new(height, b.inputs["Height"]); nt.links.new(b.outputs["Normal"], bsdf.inputs["Normal"])
        if kind in ("brick", "flagstone"):
            br = nt.nodes.new("ShaderNodeTexBrick")
            nt.links.new(metres.outputs[0], br.inputs["Vector"])
            br.inputs["Scale"].default_value = 1.0
            if kind == "brick":
                br.inputs["Brick Width"].default_value = BRICK[0]; br.inputs["Row Height"].default_value = BRICK[1]
                br.inputs["Mortar Size"].default_value = 0.012; br.offset = 0.5; br.offset_frequency = 2
                c1, c2, mortar = _lin(_hex(A["brick"])), _lin(_hex(A["brick_dark"])), _lin(_hex(A["pier"]))
            else:
                br.inputs["Brick Width"].default_value = SLAB; br.inputs["Row Height"].default_value = SLAB
                br.inputs["Mortar Size"].default_value = 0.016; br.offset = 0.0; br.offset_frequency = 2
                c1, c2, mortar = _lin(_hex(A["ground"][0])), _lin(_hex(A["ground"][1])), _lin(_hex(A["ground_dark"]))
            br.inputs["Color1"].default_value = c1; br.inputs["Color2"].default_value = c2; br.inputs["Mortar"].default_value = mortar
            br.inputs["Bias"].default_value = 0.0; br.inputs["Brick Width"].default_value = br.inputs["Brick Width"].default_value
            grime = self._noise(nt, uv.outputs["UV"], 6.0)
            # wear: darken by a periodic noise
            dark = nt.nodes.new("ShaderNodeMix"); dark.data_type = "RGBA"; dark.blend_type = "MULTIPLY"
            dark.inputs["Factor"].default_value = 0.35 if kind == "flagstone" else 0.25
            nt.links.new(br.outputs["Color"], dark.inputs["A"])
            ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.elements[0].color = (0.55, 0.5, 0.45, 1); ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
            nt.links.new(grime, ramp.inputs["Fac"]); nt.links.new(ramp.outputs["Color"], dark.inputs["B"])
            nt.links.new(dark.outputs["Result"], bsdf.inputs["Base Color"])
            bsdf.inputs["Roughness"].default_value = 0.88 if kind == "brick" else 0.80
            # the mortar is recessed; the grime is bumpy
            add = nt.nodes.new("ShaderNodeMath"); add.operation = "ADD"; nt.links.new(br.outputs["Fac"], add.inputs[0])
            fine = self._noise(nt, uv.outputs["UV"], 40.0, 2.0); sc = nt.nodes.new("ShaderNodeMath"); sc.operation = "MULTIPLY"; sc.inputs[1].default_value = 0.15
            nt.links.new(fine, sc.inputs[0]); nt.links.new(sc.outputs[0], add.inputs[1])
            inv = nt.nodes.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0; nt.links.new(add.outputs[0], inv.inputs[1])
            bump(inv.outputs[0], 0.9, 0.006)
        elif kind == "mud":
            n = self._noise(nt, uv.outputs["UV"], 5.0)
            nt.links.new(mix(_lin(_hex(A["brick"])), _lin(_hex(A["brick_dark"])), n), bsdf.inputs["Base Color"])
            bsdf.inputs["Roughness"].default_value = 0.92
            # a rendered wall: coarse trowel marks and a fine grit
            coarse = self._noise(nt, uv.outputs["UV"], 14.0, 2.0); fine = self._noise(nt, uv.outputs["UV"], 90.0, 2.0)
            mixh = nt.nodes.new("ShaderNodeMath"); mixh.operation = "ADD"; nt.links.new(coarse, mixh.inputs[0])
            sc = nt.nodes.new("ShaderNodeMath"); sc.operation = "MULTIPLY"; sc.inputs[1].default_value = 0.35
            nt.links.new(fine, sc.inputs[0]); nt.links.new(sc.outputs[0], mixh.inputs[1])
            bump(mixh.outputs[0], 0.45, 0.004)
        elif kind == "plaster":
            n = self._noise(nt, uv.outputs["UV"], 9.0)
            nt.links.new(mix(_lin(_hex(A["skyline"])), _lin(_hex(A["brick"])), n), bsdf.inputs["Base Color"])
            bsdf.inputs["Roughness"].default_value = 0.85; bump(self._noise(nt, uv.outputs["UV"], 30.0, 2.0), 0.35, 0.003)
        elif kind == "sand":
            # THEME.souq.floor: sun-bleached stones (#e0b077) and trodden dark
            # patches (#4a2c10) over the ground colour, as two blotch layers
            n = self._noise(nt, uv.outputs["UV"], 4.0)
            base = mix(_lin(_hex(A["ground"][0])), _lin(_hex(A["ground"][1])), n)
            light = self._noise(nt, uv.outputs["UV"], 2.5); lr = nt.nodes.new("ShaderNodeMath"); lr.operation = "GREATER_THAN"; lr.inputs[1].default_value = 0.62
            nt.links.new(light, lr.inputs[0])
            dark = self._noise(nt, uv.outputs["UV"], 3.5); dr = nt.nodes.new("ShaderNodeMath"); dr.operation = "GREATER_THAN"; dr.inputs[1].default_value = 0.66
            nt.links.new(dark, dr.inputs[0])
            m1 = nt.nodes.new("ShaderNodeMix"); m1.data_type = "RGBA"; m1.inputs["B"].default_value = _lin(_hex(A["ground_light"]))
            nt.links.new(base, m1.inputs["A"]); nt.links.new(lr.outputs[0], m1.inputs["Factor"])
            m2 = nt.nodes.new("ShaderNodeMix"); m2.data_type = "RGBA"; m2.inputs["B"].default_value = _lin(_hex(A["ground_dark"]))
            nt.links.new(m1.outputs["Result"], m2.inputs["A"]); nt.links.new(dr.outputs[0], m2.inputs["Factor"])
            nt.links.new(m2.outputs["Result"], bsdf.inputs["Base Color"])
            bsdf.inputs["Roughness"].default_value = 0.95; bump(self._noise(nt, uv.outputs["UV"], 60.0, 2.0), 0.25, 0.002)
        elif kind.startswith("cloth"):
            col = A["banners"][int(kind[-1])]
            wave = nt.nodes.new("ShaderNodeTexWave"); wave.wave_type = "BANDS"; wave.bands_direction = "X"
            wave.inputs["Scale"].default_value = 240.0 / TILE; nt.links.new(uv.outputs["UV"], wave.inputs["Vector"])
            wave2 = nt.nodes.new("ShaderNodeTexWave"); wave2.wave_type = "BANDS"; wave2.bands_direction = "Y"
            wave2.inputs["Scale"].default_value = 240.0 / TILE; nt.links.new(uv.outputs["UV"], wave2.inputs["Vector"])
            weave = nt.nodes.new("ShaderNodeMath"); weave.operation = "MULTIPLY"
            nt.links.new(wave.outputs["Fac"], weave.inputs[0]); nt.links.new(wave2.outputs["Fac"], weave.inputs[1])
            bsdf.inputs["Base Color"].default_value = _lin(_hex(col)); bsdf.inputs["Roughness"].default_value = 0.72
            if "Sheen Weight" in bsdf.inputs: bsdf.inputs["Sheen Weight"].default_value = 0.4
            bump(weave.outputs[0], 0.25, 0.0008)
        elif kind == "wood":
            wave = nt.nodes.new("ShaderNodeTexWave"); wave.wave_type = "BANDS"; wave.bands_direction = "Y"
            wave.inputs["Scale"].default_value = 18.0 / TILE; wave.inputs["Distortion"].default_value = 1.4; wave.inputs["Detail"].default_value = 2.0
            nt.links.new(uv.outputs["UV"], wave.inputs["Vector"])
            nt.links.new(mix(_lin(_hex(A["crate"])), _lin(_hex(A["crate_edge"])), wave.outputs["Fac"]), bsdf.inputs["Base Color"])
            bsdf.inputs["Roughness"].default_value = 0.62; bump(wave.outputs["Fac"], 0.3, 0.0015)
        elif kind == "iron":
            bsdf.inputs["Base Color"].default_value = _lin(_hex(A["barrel"])); bsdf.inputs["Metallic"].default_value = 0.85
            bsdf.inputs["Roughness"].default_value = 0.45
        elif kind == "glass":
            bsdf.inputs["Base Color"].default_value = _lin(_hex(A["lantern"])); bsdf.inputs["Roughness"].default_value = 0.2
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = _lin(_hex(A["lantern"])); bsdf.inputs["Emission Strength"].default_value = 3.0
        elif kind == "gatewall":
            # the browser's cracked wall is a paler mud than the arcade: #9b8460
            br = nt.nodes.new("ShaderNodeTexBrick"); nt.links.new(metres.outputs[0], br.inputs["Vector"])
            br.inputs["Scale"].default_value = 1.0; br.inputs["Brick Width"].default_value = BRICK[0]; br.inputs["Row Height"].default_value = BRICK[1]
            br.inputs["Mortar Size"].default_value = 0.012; br.offset = 0.5; br.offset_frequency = 2
            br.inputs["Color1"].default_value = _lin(_hex(A["wall_gate"])); br.inputs["Color2"].default_value = _lin(_hex("#8c7656"))
            br.inputs["Mortar"].default_value = _lin(_hex("#6d5c44"))
            nt.links.new(br.outputs["Color"], bsdf.inputs["Base Color"]); bsdf.inputs["Roughness"].default_value = 0.9
            inv = nt.nodes.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0; nt.links.new(br.outputs["Fac"], inv.inputs[1])
            bump(inv.outputs[0], 0.9, 0.006)
        elif kind == "crack":
            bsdf.inputs["Base Color"].default_value = _lin(_hex("#140e0a")); bsdf.inputs["Roughness"].default_value = 1.0
        self.mats[name] = mat
        return mat

    def bake_tiles(self):
        """Every material baked once, on a tile, to textures that repeat --
        the noise is sampled on a torus, the bricks fit the tile whole -- so
        one 1K tile is 2 mm per texel on every wall in the district."""
        bpy = self.bpy
        size = 512 if self.fast else 1024
        bpy.ops.mesh.primitive_plane_add(size=1.0); tile = bpy.context.object; tile.name = "BakeTile"
        # a plane's default UVs run 0..1 across it, which is exactly the tile
        sc = bpy.context.scene; sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 1
        sc.render.bake.margin = 4; sc.render.bake.use_selected_to_active = False
        out = {}
        for name, mat in list(self.mats.items()):
            tile.data.materials.clear(); tile.data.materials.append(mat)
            nt = mat.node_tree; bsdf = nt.nodes["Principled BSDF"]
            tex = nt.nodes.new("ShaderNodeTexImage"); nt.nodes.active = tex
            imgs = {}
            for m, suffix in (("albedo", "BaseColor"), ("normal", "Normal"), ("roughness", "Roughness")):
                img = bpy.data.images.new("%s_%s" % (name, m), size, size, alpha=False, float_buffer=False)
                img.colorspace_settings.name = "sRGB" if m == "albedo" else "Non-Color"
                img.filepath_raw = os.path.join(self.textures, "T_%s_%s.png" % (name.replace("M_", ""), suffix)); img.file_format = "PNG"
                tex.image = img
                bpy.ops.object.select_all(action="DESELECT"); tile.select_set(True); bpy.context.view_layer.objects.active = tile
                if m == "albedo":
                    # emission would bake into the colour; the lantern's glow is the engine's to make
                    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=4)
                elif m == "normal":
                    bpy.ops.object.bake(type="NORMAL", margin=4)
                else:
                    bpy.ops.object.bake(type="ROUGHNESS", margin=4)
                img.save(); imgs[m] = img
            nt.nodes.remove(tex)
            # the shipped material: the three maps, on the mesh's own UVs
            baked = bpy.data.materials.new(name + "_baked"); baked.use_nodes = True
            bn = baked.node_tree; bb = bn.nodes["Principled BSDF"]
            uvn = bn.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
            for m, sock in (("albedo", "Base Color"), ("roughness", "Roughness")):
                t = bn.nodes.new("ShaderNodeTexImage"); t.image = imgs[m]; t.extension = "REPEAT"
                bn.links.new(uvn.outputs["UV"], t.inputs["Vector"]); bn.links.new(t.outputs["Color"], bb.inputs[sock])
            t = bn.nodes.new("ShaderNodeTexImage"); t.image = imgs["normal"]; t.extension = "REPEAT"
            nm = bn.nodes.new("ShaderNodeNormalMap"); bn.links.new(uvn.outputs["UV"], t.inputs["Vector"])
            bn.links.new(t.outputs["Color"], nm.inputs["Color"]); bn.links.new(nm.outputs["Normal"], bb.inputs["Normal"])
            bb.inputs["Metallic"].default_value = bsdf.inputs["Metallic"].default_value
            if "Emission Strength" in bsdf.inputs and bsdf.inputs["Emission Strength"].default_value > 0:
                bb.inputs["Emission Color"].default_value = bsdf.inputs["Emission Color"].default_value
                bb.inputs["Emission Strength"].default_value = bsdf.inputs["Emission Strength"].default_value
            baked.name = name          # the procedural one keeps its node tree under another name
            mat.name = name + "_procedural"
            out[name] = baked
        bpy.data.objects.remove(tile, do_unlink=True)
        # every mesh built so far swaps to the baked material
        for o in bpy.data.objects:
            if o.type == "MESH":
                for slot in o.material_slots:
                    if slot.material and slot.material.name.endswith("_procedural"):
                        slot.material = out[slot.material.name.replace("_procedural", "")]
        self.mats = out
        return out

    # --------------------------------------------------------------- meshes
    def _new(self, name, bm, materials, uv_tile=TILE, smooth=False):
        """A mesh object from a bmesh, with box-projected UVs in metres/tile
        and its material slots. Faces carry `mat` as an int layer index."""
        import bmesh
        bpy = self.bpy
        uv = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")
        bm.normal_update()
        for f in bm.faces:
            n = f.normal; ax = max(range(3), key=lambda i: abs(n[i]))
            for l in f.loops:
                p = l.vert.co
                if ax == 2:   u, w = p.x, p.y
                elif ax == 0: u, w = p.y, p.z
                else:         u, w = p.x, p.z
                l[uv].uv = (u / uv_tile, w / uv_tile)
        me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.update()
        for m in materials: me.materials.append(m)
        if smooth:
            me.polygons.foreach_set("use_smooth", [True] * len(me.polygons)); me.update()
        o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o)
        return o

    def _box(self, bm, cx, cy, z0, w, d, h, mat, batter=0.0, yaw=0.0):
        """A box on the floor at (cx, cy), `batter` insets the top on every side."""
        import bmesh
        from mathutils import Vector, Matrix
        hw, hd = w * 0.5, d * 0.5
        verts = [bm.verts.new((sx * hw, sy * hd, z0)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        verts += [bm.verts.new((sx * (hw - batter), sy * (hd - batter), z0 + h)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        made = []
        for f in faces:
            face = bm.faces.new([verts[i] for i in f]); face.material_index = mat; made.append(face)
        if yaw or cx or cy:
            M = Matrix.Translation((cx, cy, 0)) @ Matrix.Rotation(math.radians(yaw), 4, "Z")
            bmesh.ops.transform(bm, matrix=M, verts=verts)
        return made

    def _slat(self, bm, centre, size, mat, deg_about_y):
        """A thin box centred at `centre`, turned about its own Y (the face
        normal) by `deg_about_y`: a crate's diagonal brace."""
        import bmesh
        from mathutils import Matrix
        w, d, h = size
        faces = self._box(bm, 0, 0, -h * 0.5, w, d, h, mat)
        verts = list({v for f in faces for v in f.verts})
        M = Matrix.Translation(centre) @ Matrix.Rotation(math.radians(deg_about_y), 4, "Y")
        bmesh.ops.transform(bm, matrix=M, verts=verts)

    def _cyl(self, bm, cx, cy, z0, r, h, mat, segs=24, r_top=None):
        import bmesh
        r_top = r if r_top is None else r_top
        lo = [bm.verts.new((cx + math.cos(2 * math.pi * i / segs) * r, cy + math.sin(2 * math.pi * i / segs) * r, z0)) for i in range(segs)]
        hi = [bm.verts.new((cx + math.cos(2 * math.pi * i / segs) * r_top, cy + math.sin(2 * math.pi * i / segs) * r_top, z0 + h)) for i in range(segs)]
        for i in range(segs):
            f = bm.faces.new((lo[i], lo[(i + 1) % segs], hi[(i + 1) % segs], hi[i])); f.material_index = mat
        if r > 1e-6:
            f = bm.faces.new(list(reversed(lo))); f.material_index = mat
        if r_top > 1e-6:
            f = bm.faces.new(hi); f.material_index = mat

    def _dome(self, bm, cx, cy, z0, r, mat, segs=24, rings=8, squash=1.0):
        prev = None
        for j in range(rings + 1):
            phi = (math.pi / 2) * j / rings
            rr, zz = r * math.cos(phi), z0 + r * math.sin(phi) * squash
            ring = [bm.verts.new((cx + math.cos(2 * math.pi * i / segs) * rr, cy + math.sin(2 * math.pi * i / segs) * rr, zz)) for i in range(segs)] if j < rings else None
            if prev is not None:
                for i in range(segs):
                    if ring is None:
                        apex = bm.verts.new((cx, cy, zz)) if i == 0 else apex
                        f = bm.faces.new((prev[i], prev[(i + 1) % segs], apex))
                    else:
                        f = bm.faces.new((prev[i], prev[(i + 1) % segs], ring[(i + 1) % segs], ring[i]))
                    f.material_index = mat
            prev = ring

    def _crenels(self, bm, w, d, z0, mat, batter):
        cw, gap, ch = CRENEL
        hw, hd = w * 0.5 - batter, d * 0.5 - batter
        for x in self._steps(-hw, hw, cw, gap):
            self._box(bm, x, -hd + 0.15, z0, cw, 0.30, ch, mat); self._box(bm, x, hd - 0.15, z0, cw, 0.30, ch, mat)
        for y in self._steps(-hd + cw, hd - cw, cw, gap):
            self._box(bm, -hw + 0.15, y, z0, 0.30, cw, ch, mat); self._box(bm, hw - 0.15, y, z0, 0.30, cw, ch, mat)

    @staticmethod
    def _steps(a, b, w, gap):
        n = max(1, int((b - a + gap) // (w + gap)))
        span = n * w + (n - 1) * gap; start = (a + b) * 0.5 - span * 0.5 + w * 0.5
        return [start + i * (w + gap) for i in range(n)]

    def _arch_profile(self, w, h):
        """The browser's arcade bay: two piers and a low parabolic arch,
        normalised to a stall (w, h). Returns pier width, pier height, and
        the arch's inner curve as (x, z) points from left pier top to right."""
        A = BROWSER_ART
        pier_w = w * A["pier_w"] / A["bay_w"]
        pier_h = h * A["pier_h"] / A["arch_outer"]
        peak = h * A["arch_peak"] / A["arch_outer"]
        pts = []
        for i in range(13):
            u = i / 12.0; x = -w * 0.5 + pier_w + u * (w - 2 * pier_w)
            z = pier_h + (peak - pier_h) * 4.0 * u * (1.0 - u)          # a parabola, as quadraticCurveTo draws
            pts.append((x, z))
        return pier_w, pier_h, pts

    def build_stall(self, name, w, d, h):
        """The arcade bay in front of a mud block: piers, the arch, a recess
        with a wooden shutter, the banner hung in it, the lantern at the apex."""
        import bmesh
        bpy = self.bpy
        # The browser paints a souq building as one flat mud colour (#b9784a,
        # the far layer) with no courses drawn: rendered mud, not fired
        # brick. Brick shows only where the browser draws courses -- the
        # cracked wall -- and on the rim.
        mud = self.material("M_Souq_Mud", "mud"); plaster = self.material("M_Souq_Plaster", "plaster")
        wood = self.material("M_Souq_Wood", "wood"); iron = self.material("M_Souq_Iron", "iron"); glass = self.material("M_Souq_Glass", "glass")
        mats = [mud, plaster, wood, iron, glass]
        bm = bmesh.new()
        pier_w, pier_h, arch = self._arch_profile(w, h)
        # the body, its front pulled back by the recess; the parapet lip on top
        self._box(bm, 0, RECESS * 0.5, 0.0, w, d - RECESS, h, 0, batter=BATTER)
        self._box(bm, 0, 0, h, w + 0.10, d + 0.10, 0.12, 1)
        # the piers, full depth of the recess, in front of the body
        for sx in (-1, 1):
            self._box(bm, sx * (w * 0.5 - pier_w * 0.5), -d * 0.5 + RECESS * 0.5, 0.0, pier_w, RECESS, pier_h, 0, batter=BATTER * 0.5)
        # the arch: a solid above the parabola, from pier top to the parapet, the recess deep
        yf, yb = -d * 0.5, -d * 0.5 + RECESS
        top = h
        left = bm.verts.new((-w * 0.5 + pier_w, yf, pier_h)); right = bm.verts.new((w * 0.5 - pier_w, yf, pier_h))
        curve_f = [bm.verts.new((x, yf, z)) for x, z in arch]
        curve_b = [bm.verts.new((x, yb, z)) for x, z in arch]
        tl_f, tr_f = bm.verts.new((-w * 0.5 + pier_w, yf, top)), bm.verts.new((w * 0.5 - pier_w, yf, top))
        tl_b, tr_b = bm.verts.new((-w * 0.5 + pier_w, yb, top)), bm.verts.new((w * 0.5 - pier_w, yb, top))
        f = bm.faces.new([tl_f] + curve_f + [tr_f]); f.material_index = 0            # the front spandrel
        f = bm.faces.new(list(reversed([tl_b] + curve_b + [tr_b]))); f.material_index = 0
        for i in range(len(arch) - 1):                                                # the soffit
            f = bm.faces.new((curve_f[i], curve_b[i], curve_b[i + 1], curve_f[i + 1])); f.material_index = 0
        f = bm.faces.new((tl_f, tl_b, curve_b[0], curve_f[0])); f.material_index = 0
        f = bm.faces.new((tr_f, curve_f[-1], curve_b[-1], tr_b)); f.material_index = 0
        f = bm.faces.new((tl_f, tr_f, tr_b, tl_b)); f.material_index = 0
        bm.verts.remove(left); bm.verts.remove(right)
        # the shutter at the back of the recess: wood, a hand's width in from the arch
        self._box(bm, 0, yb - 0.04, 0.02, w - 2 * pier_w - 0.10, 0.06, pier_h - 0.04, 2)
        # the banner is placed with the stall as its own mesh, coloured by the
        # plot's index, so a stall variant is not tripled for a rectangle of
        # cloth. The lantern at the apex, on a short rod, is here.
        A = BROWSER_ART; yb2 = yf + RECESS * 0.45
        lx = -w * 0.5 + w * A["lantern_x"] / A["bay_w"]; lr = A["lantern_r"] * CM_PER_DRAWN_PX / 100.0
        apex = h * A["arch_peak"] / A["arch_outer"]
        self._cyl(bm, lx, yb2, apex - LANTERN_DROP, 0.008, LANTERN_DROP, 3, segs=8)
        self._cyl(bm, lx, yb2, apex - LANTERN_DROP - lr * 2.2, lr * 0.75, lr * 2.2, 4, segs=12, r_top=lr)
        self._cyl(bm, lx, yb2, apex - LANTERN_DROP - lr * 2.2 - 0.02, lr * 0.5, 0.02, 3, segs=12)
        o = self._new(name, bm, mats)
        self.kinds[name] = o
        return o

    def build_warehouse(self, name, w, d, h, dome):
        import bmesh
        mud = self.material("M_Souq_Mud", "mud"); plaster = self.material("M_Souq_Plaster", "plaster"); wood = self.material("M_Souq_Wood", "wood")
        bm = bmesh.new()
        self._box(bm, 0, 0, 0.0, w, d, h, 0, batter=BATTER * 1.5)
        if dome:
            drum = min(w, d) * 0.28
            self._cyl(bm, 0, 0, h, drum, 0.5, 1, segs=32)
            self._dome(bm, 0, 0, h + 0.5, drum, 1, segs=32, rings=10, squash=1.34)   # the browser's dome is 1.34 r tall
            self._cyl(bm, 0, 0, h + 0.5 + drum * 1.34, drum * 0.05, drum * 0.30, 1, segs=8)
        else:
            self._crenels(bm, w, d, h, 0, BATTER * 1.5)
        # a door on the front
        self._box(bm, 0, -d * 0.5 + 0.03, 0.02, 1.2, 0.08, 2.2, 2)
        o = self._new(name, bm, [mud, plaster, wood]); self.kinds[name] = o; return o

    def build_wall(self, name, L, thick, h):
        import bmesh
        brick = self.material("M_Souq_MudBrick", "brick")
        bm = bmesh.new()
        self._box(bm, 0, 0, 0.0, L, thick, h, 0, batter=0.06)
        self._crenels(bm, L, thick, h, 0, 0.06)
        o = self._new(name, bm, [brick]); self.kinds[name] = o; return o

    def build_minaret(self, name, h):
        """index.html:minaret(): a shaft 0.096 h wide, a balcony at 0.72 h,
        a cap to 1.16 h, a finial to 1.22 h."""
        import bmesh
        mud = self.material("M_Souq_Mud", "mud"); plaster = self.material("M_Souq_Plaster", "plaster")
        bm = bmesh.new()
        r = 0.048 * h
        self._box(bm, 0, 0, 0.0, r * 2.6, r * 2.6, 0.6, 0)
        self._cyl(bm, 0, 0, 0.6, r, h - 0.6, 0, segs=32)
        self._cyl(bm, 0, 0, 0.72 * h, 0.082 * h, 0.045 * h, 1, segs=32)
        self._dome(bm, 0, 0, h, 0.075 * h, 1, segs=32, rings=10, squash=0.16 * h / (0.075 * h))
        self._cyl(bm, 0, 0, 1.16 * h - 0.02, 0.012 * h, 0.06 * h + 0.02, 1, segs=8)
        o = self._new(name, bm, [mud, plaster], smooth=True); self.kinds[name] = o; return o

    def build_gate(self, name, w, d, h):
        """drawGate 'wall': mud brick with a crack running down it, the
        browser's polyline scaled to the AbilityGate's box."""
        import bmesh
        wall = self.material("M_Souq_GateWall", "gatewall"); crack = self.material("M_Souq_Crack", "crack")
        bm = bmesh.new()
        self._box(bm, 0, 0, 0.0, w, d, h, 0)
        # (-4,-74) (3,-54) (-6,-34) (4,-14) (-2,0) in a 60 x 76 box, from the top down
        pts = [(-4, -74), (3, -54), (-6, -34), (4, -14), (-2, 0)]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            ax, az = x0 / 60.0 * w, (76 + y0) / 76.0 * h; bx, bz = x1 / 60.0 * w, (76 + y1) / 76.0 * h
            L = math.hypot(bx - ax, bz - az); ang = math.degrees(math.atan2(bz - az, bx - ax))
            cx, cz = (ax + bx) * 0.5, (az + bz) * 0.5
            from mathutils import Matrix
            verts = []
            for sx, sz in ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)):
                verts.append((sx * L, sz * 0.03))
            face_pts = [bm.verts.new((cx + vx * math.cos(math.radians(ang)) - vz * math.sin(math.radians(ang)), -d * 0.5 - 0.002,
                                      cz + vx * math.sin(math.radians(ang)) + vz * math.cos(math.radians(ang)))) for vx, vz in verts]
            f = bm.faces.new(face_pts); f.material_index = 1          # wound to -Y, the wall's front; reversed() faced into the wall
        o = self._new(name, bm, [wall, crack]); self.kinds[name] = o; return o

    def build_crate(self, name, s, h):
        import bmesh
        wood = self.material("M_Souq_Wood", "wood")
        bm = bmesh.new()
        self._box(bm, 0, 0, 0.0, s, s, h, 0)
        e = 0.06
        for sy in (-1, 1):
            y = sy * (s * 0.5 + 0.01)
            for x in (-s * 0.5 + e * 0.5, s * 0.5 - e * 0.5):
                self._box(bm, x, y, 0.0, e, 0.02, h, 0)
            self._box(bm, 0, y, h - e, s, 0.02, e, 0); self._box(bm, 0, y, 0.0, s, 0.02, e, 0)
            for ang in (45.0, -45.0):
                self._slat(bm, (0, y, h * 0.5), (math.hypot(s, h) - 2 * e, 0.02, e), 0, ang)
        o = self._new(name, bm, [wood], uv_tile=TILE); self.kinds[name] = o; return o

    def build_barrel(self, name, dia, h):
        import bmesh
        wood = self.material("M_Souq_Wood", "wood"); iron = self.material("M_Souq_Iron", "iron")
        bm = bmesh.new()
        r = dia * 0.5
        self._cyl(bm, 0, 0, 0.0, r * 0.94, h, 0, segs=20)
        for z in (h * 0.14, h * 0.5, h * 0.86):
            self._cyl(bm, 0, 0, z - 0.02, r, 0.04, 1, segs=20)
        o = self._new(name, bm, [wood, iron], smooth=True); self.kinds[name] = o; return o

    def build_ground(self, name, E):
        import bmesh
        sand = self.material("M_Souq_Sand", "sand")
        bm = bmesh.new()
        segs = 96
        c = bm.verts.new((0, 0, 0)); ring = [bm.verts.new((math.cos(2 * math.pi * i / segs) * E, math.sin(2 * math.pi * i / segs) * E, 0)) for i in range(segs)]
        for i in range(segs):
            bm.faces.new((c, ring[i], ring[(i + 1) % segs]))
        o = self._new(name, bm, [sand]); self.kinds[name] = o; return o

    def build_street(self, name, P):
        """The way through, as a ribbon on the spiral, plus a spur to every
        site and door -- the same segments build_world paves, as one mesh.

        A spur starts at the ribbon's EDGE, not on the path. The first
        version began every spur on the centre line, so half of each lay on
        the ribbon, coplanar with it, and where two faces lie on each other a
        renderer's shadow ray off one strikes the other at zero distance:
        the overlap rendered black under any light (and would z-fight in the
        engine). Each spur is now cut where its two sides cross the ribbon's
        edge, tucked SPUR_TUCK under it and 1 mm lower so the join is covered
        and nothing lies on anything; a spur that never leaves the ribbon is
        not built."""
        import bmesh
        flag = self.material("M_Souq_Flagstone", "flagstone")
        bm = bmesh.new()
        z = STREET_Z_CM / 100.0
        # the spiral as one strip, so its edges are continuous
        pts = [(x / 100.0, y / 100.0) for x, y in P["path"]]
        hw = STREET_HALF_WIDTH / 100.0
        left, right, edge = [], [], {1: [], -1: []}
        for i, (x, y) in enumerate(pts):
            x0, y0 = pts[max(0, i - 1)]; x1, y1 = pts[min(len(pts) - 1, i + 1)]
            dx, dy = x1 - x0, y1 - y0; dl = math.hypot(dx, dy) or 1.0; nx, ny = -dy / dl, dx / dl
            edge[1].append((x + nx * hw, y + ny * hw)); edge[-1].append((x - nx * hw, y - ny * hw))
            left.append(bm.verts.new((edge[1][-1][0], edge[1][-1][1], z))); right.append(bm.verts.new((edge[-1][-1][0], edge[-1][-1][1], z)))
        for i in range(1, len(pts)):
            bm.faces.new((left[i - 1], right[i - 1], right[i], left[i]))
        # the spurs
        self.spurs = dict(built=0, inside=0)
        for s in P["street"][PATH_SAMPLES - 1:]:
            (ax, ay), (bx, by) = s["a"], s["b"]; ax, ay, bx, by = ax / 100.0, ay / 100.0, bx / 100.0, by / 100.0
            dx, dy = bx - ax, by - ay; dl = math.hypot(dx, dy) or 1.0; ux, uy = dx / dl, dy / dl; nx, ny = -uy, ux; w = s["width"] / 200.0
            j = min(range(len(pts)), key=lambda k: (pts[k][0] - ax) ** 2 + (pts[k][1] - ay) ** 2)
            near = []
            for sgn in (1, -1):
                px, py = ax + nx * w * sgn, ay + ny * w * sgn
                s0 = _leaves_ribbon((px, py), (ux, uy), edge, j)
                near.append((px + ux * (s0 - SPUR_TUCK), py + uy * (s0 - SPUR_TUCK), s0))
            if min(n[2] for n in near) - SPUR_TUCK >= dl:
                self.spurs["inside"] += 1; continue     # the site sits on the street already
            zs = z - 0.001
            vs = [bm.verts.new((near[0][0], near[0][1], zs)), bm.verts.new((near[1][0], near[1][1], zs)),
                  bm.verts.new((bx - nx * w, by - ny * w, zs)), bm.verts.new((bx + nx * w, by + ny * w, zs))]
            bm.faces.new(vs); self.spurs["built"] += 1
        o = self._new(name, bm, [flag]); self.kinds[name] = o; return o

    def build_banner(self, name, i):
        """A one-metre quad of cloth, its front -Y like every kind, scaled to
        the banner's size per stall by its row. Wound so its normal is -Y:
        the first version faced the shutter."""
        import bmesh
        cloth = self.material("M_Souq_Cloth%d" % i, "cloth%d" % i)
        bm = bmesh.new()
        vs = [bm.verts.new((-0.5, 0, -0.5)), bm.verts.new((0.5, 0, -0.5)), bm.verts.new((0.5, 0, 0.5)), bm.verts.new((-0.5, 0, 0.5))]
        bm.faces.new(vs)
        o = self._new(name, bm, [cloth]); self.kinds[name] = o; return o

    def build_kinds(self):
        P = self.P
        for name, m in P["meshes"].items():
            w, d, h = m["w"] / 100.0, m["d"] / 100.0, m["h"] / 100.0
            k = m["kind"]
            if k == "stall":       self.build_stall(name, w, d, h)
            elif k == "warehouse": self.build_warehouse(name, w, d, h, m["dome"])
            elif k == "wall":      self.build_wall(name, w, d, h)
            elif k == "minaret":   self.build_minaret(name, m["shaft"] / 100.0)
            elif k == "gate":      self.build_gate(name, w, d, h)
            elif k == "crate":     self.build_crate(name, w, h)
            elif k == "barrel":    self.build_barrel(name, w, h)
            elif k == "ground":    self.build_ground(name, P["E"] / 100.0)
            elif k == "street":    self.build_street(name, P)
            elif k == "banner":    self.build_banner(name, int(name[-1]))
        return self.kinds

    # ------------------------------------------------------------ placement
    def place(self):
        """Every instance as a linked duplicate of its kind, in metres."""
        bpy = self.bpy
        coll = bpy.data.collections.new("SouqAlDawar"); bpy.context.scene.collection.children.link(coll)
        rows = instances(self.P)
        for i, r in enumerate(rows):
            src = self.kinds[r["mesh"]]
            if r["mesh"] in ("SM_Souq_Ground", "SM_Souq_Street"):
                o = src; bpy.context.scene.collection.objects.unlink(o); coll.objects.link(o)
            else:
                o = bpy.data.objects.new("%s_%03d" % (r["mesh"], i), src.data); coll.objects.link(o)
            o.location = (r["x"] / 100.0, r["y"] / 100.0, r["z"] / 100.0)
            o.rotation_euler = (0, 0, math.radians(r["yaw"])); o.scale = tuple(r["scale"])
            r["object"] = o.name; self.placed.append(o)
        # the kinds themselves stay at the origin, out of the way and hidden
        for name, o in self.kinds.items():
            if o.name not in coll.objects:
                o.hide_render = True; o.hide_viewport = True; o.location = (0, 0, -50.0)
        return rows

    # --------------------------------------------------------------- export
    def export(self):
        bpy = self.bpy
        written = {}
        for name, o in self.kinds.items():
            o.hide_viewport = False; o.hide_render = False; loc = tuple(o.location); o.location = (0, 0, 0)
            bpy.ops.object.select_all(action="DESELECT"); o.select_set(True); bpy.context.view_layer.objects.active = o
            path = os.path.join(self.models, name + ".fbx")
            # Centimetres and the Z-up-to-Y-up change baked into the vertex
            # data, FBX scale 1.0: a file every importer reads the same. The
            # hero and the clips keep FBX_SCALE_UNITS (metres, scale 100) on
            # a shared skeleton, and a rigged mesh cannot bake its transform;
            # a static one can, and then nothing depends on how an importer
            # treats UnitScaleFactor. The read-back below holds it to that.
            bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH"}, apply_unit_scale=True, global_scale=1.0,
                                     apply_scale_options="FBX_SCALE_NONE", bake_space_transform=True, mesh_smooth_type="FACE",
                                     use_mesh_modifiers=True, path_mode="RELATIVE", embed_textures=False, bake_anim=False)
            written[name] = os.path.getsize(path)
            o.location = loc
            if name not in ("SM_Souq_Ground", "SM_Souq_Street"):
                o.hide_viewport = True; o.hide_render = True
        # one of them read back: the minaret comes in at its own height
        # and vertex count, or the export is not what it says
        before = set(bpy.data.objects); tall = self.P["meshes"]["SM_Souq_Minaret"]
        bpy.ops.import_scene.fbx(filepath=os.path.join(self.models, "SM_Souq_Minaret.fbx"))
        back = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
        assert len(back) == 1, "the minaret's FBX read back as %d meshes" % len(back)
        zs = [(back[0].matrix_world @ v.co).z for v in back[0].data.vertices]
        got_h, got_n = max(zs) - min(zs), len(back[0].data.vertices)
        want_n = len(self.kinds["SM_Souq_Minaret"].data.vertices)
        for o in back: bpy.data.objects.remove(o, do_unlink=True)
        assert abs(got_h - tall["h"] / 100.0) < 0.01, "the minaret's FBX reads back %.2f m tall, not %.2f" % (got_h, tall["h"] / 100.0)
        assert got_n == want_n, "the minaret's FBX reads back with %d vertices, not %d" % (got_n, want_n)
        self.fbx_readback = dict(height_m=got_h, verts=got_n)
        # the whole district, placed, as one glTF
        bpy.ops.object.select_all(action="DESELECT")
        for o in self.placed: o.select_set(True)
        gltf = os.path.join(self.models, "SouqAlDawar.gltf")
        bpy.ops.export_scene.gltf(filepath=gltf, export_format="GLTF_SEPARATE", use_selection=True, export_yup=True,
                                  export_apply=False, export_keep_originals=True)
        written["SouqAlDawar.gltf"] = os.path.getsize(gltf)
        # the manifest
        rows = instances(self.P)
        man = dict(stage=self.P["stage"]["Name"], level=LEVEL_NAME, extent_cm=self.P["E"], phase=self.P["phase"],
                   units="centimetres, Z up, origin at the district's middle; yaw in degrees about Z; the mesh's front is its local -Y",
                   meshes={k: dict(kind=m["kind"], w_cm=m["w"], d_cm=m["d"], h_cm=m["h"], fbx="SM_%s.fbx" % k[3:] if not k.startswith("SM_") else k + ".fbx")
                           for k, m in self.P["meshes"].items()},
                   instances=[{k: v for k, v in r.items() if k != "object"} for r in rows],
                   actors=self.P["actors"])
        with open(os.path.join(self.models, "SouqAlDawar_placement.json"), "w", encoding="utf-8") as fh:
            json.dump(man, fh, indent=1)
        return written, gltf

    def verify_gltf(self, gltf):
        j = json.load(open(gltf))
        base = os.path.dirname(gltf)
        missing = [i.get("uri") for i in j.get("images", []) if "uri" not in i or not os.path.exists(os.path.join(base, i["uri"]))]
        assert not missing, "the glTF points at textures that are not there: %s" % missing[:4]
        acc = j["accessors"]
        tris = sum(acc[p["indices"]]["count"] // 3 for m in j["meshes"] for p in m["primitives"] if "indices" in p)
        nodes = [n for n in j["nodes"] if "mesh" in n]
        ys = [acc[p["attributes"]["POSITION"]]["max"][1] for m in j["meshes"] for p in m["primitives"]]
        return dict(meshes=len(j["meshes"]), nodes=len(nodes), tris=tris, images=len(j.get("images", [])), tallest_m=max(ys))

    def check_meshes(self):
        """What a mesh has to be to leave: UVs, a material, a footprint that
        is its plot's, a triangle count under budget, no loose geometry."""
        import bmesh
        budget = {"ground": 400, "street": 2000, "stall": 6000, "warehouse": 6000, "wall": 1500, "minaret": 4000, "banner": 2,
                  "gate": 200, "crate": 400, "barrel": 600}
        report = {}
        for name, m in self.P["meshes"].items():
            o = self.kinds[name]; me = o.data
            assert me.uv_layers, "%s has no UVs" % name
            assert me.materials, "%s has no material" % name
            tris = sum(len(p.vertices) - 2 for p in me.polygons)
            assert tris <= budget[m["kind"]], "%s is %d tris, over its %d budget" % (name, tris, budget[m["kind"]])
            xs = [v.co.x for v in me.vertices]; ys = [v.co.y for v in me.vertices]; zs = [v.co.z for v in me.vertices]
            w, d, h = max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)
            if m["kind"] not in ("ground", "street"):
                tol = 0.20 if m["kind"] in ("stall", "warehouse") else 0.12
                assert abs(w - m["w"] / 100.0) <= tol + 0.35 * (m["kind"] == "stall"), "%s is %.2f m wide, its plot %.2f" % (name, w, m["w"] / 100.0)
                assert h >= m["h"] / 100.0 - 0.01, "%s is %.2f m tall, its plot %.2f" % (name, h, m["h"] / 100.0)
            loose = sum(1 for v in me.vertices if not any(v.index in p.vertices for p in me.polygons))
            assert loose == 0, "%s has %d loose vertices" % (name, loose)
            report[name] = dict(tris=tris, w=round(w, 2), d=round(d, 2), h=round(h, 2))
        return report

    # -------------------------------------------------------------- renders
    def sun(self):
        """build_levels' Souq rig: 24 degrees up, warm; from where he walks in
        (the West door), down the length of the market as the browser has it."""
        bpy = self.bpy
        from mathutils import Vector
        light = bpy.data.lights.new("Sun", type="SUN"); light.energy = 5.0; light.color = (1.00, 0.85, 0.63); light.angle = math.radians(1.5)
        o = bpy.data.objects.new("Sun", light); bpy.context.scene.collection.objects.link(o)
        wx, wy = self.P["doors"].get("West", (-1.0, 0.0)); az = math.atan2(wy, wx)
        el = math.radians(SUN_PITCH)
        d = Vector((-math.cos(az) * math.cos(el), -math.sin(az) * math.cos(el), -math.sin(el)))   # the light travels from the door inward
        o.rotation_euler = (-d).to_track_quat("Z", "Y").to_euler()
        world = bpy.data.worlds.new("Souq"); bpy.context.scene.world = world; world.use_nodes = True
        bg = world.node_tree.nodes["Background"]; bg.inputs[0].default_value = _lin(_hex("#e79a5c")); bg.inputs[1].default_value = 0.55
        return o

    def render(self, name, cam_loc, look_at, lens=35, res=(1600, 900), samples=None):
        bpy = self.bpy
        from mathutils import Vector
        cam_data = bpy.data.cameras.new("Cam"); cam_data.lens = lens; cam_data.clip_end = 2000.0
        cam = bpy.data.objects.new("Cam", cam_data); cam.location = cam_loc
        cam.rotation_euler = (Vector(look_at) - Vector(cam_loc)).to_track_quat("-Z", "Y").to_euler()
        bpy.context.scene.collection.objects.link(cam); bpy.context.scene.camera = cam
        sc = bpy.context.scene; sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"
        sc.cycles.samples = samples or (16 if self.fast else 48); sc.cycles.use_denoising = True
        sc.render.resolution_x, sc.render.resolution_y = res; sc.render.image_settings.file_format = "PNG"
        sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"
        sc.render.filepath = os.path.join(self.renders, name); bpy.ops.render.render(write_still=True)
        return sc.render.filepath           # the camera stays: the .blend is opened and rendered from

    def renders_of_the_place(self):
        P = self.P; E = P["E"] / 100.0
        out = []
        out.append(self.render("souq-overview.png", (E * 0.9, -E * 1.1, E * 0.75), (0, 0, 0), lens=28))
        s = next(s for s in P["sites"] if s["kind"] == "wave" and s["i"] == 1)
        nx, ny = nearest_on_path(P["path"], s["x"], s["y"]); ax, ay = spiral(min(1.0, s["t"] + 0.03), E * 100, P["phase"])
        out.append(self.render("souq-street.png", (nx / 100.0, ny / 100.0, 1.65), (ax / 100.0, ay / 100.0, 1.4), lens=26))
        if P["gate"]:
            g = P["gate"]; a = math.radians(g["yaw"])
            out.append(self.render("souq-gate.png", (g["x"] / 100.0 + math.sin(a) * 7.5 + math.cos(a) * 3.0, g["y"] / 100.0 - math.cos(a) * 7.5 + math.sin(a) * 3.0, 1.6),
                                   (g["x"] / 100.0, g["y"] / 100.0, 1.4), lens=32))
        return out

    # ---------------------------------------------------------------- scene
    def scene(self, fighters_dir, blend_out, render_name="souq-fight.png"):
        """The fight at wave 2: Ahmed and the wave's men, posed through their
        control rigs, in the built souq."""
        bpy = self.bpy
        from mathutils import Vector
        import build_ahmed as legacy, rig_full_ik as CR
        P = self.P
        site = next(s for s in P["sites"] if s["kind"] == "wave" and s["i"] == 1)
        cx, cy = site["x"] / 100.0, site["y"] / 100.0
        ax, ay = spiral(min(1.0, site["t"] + 0.01), P["E"], P["phase"]); dx, dy = ax / 100.0 - cx, ay / 100.0 - cy
        dl = math.hypot(dx, dy) or 1.0; fx, fy = dx / dl, dy / dl; lx, ly = -fy, fx
        # The browser's own formation, index.html:3597 and :3998-3999: enemy
        # j stands at his own reach * 0.70 plus a lane of (j >> 1) * 30 px from
        # Ahmed, in front of him for even j and behind for odd, in browser
        # pixels taken to centimetres by PX. Ahmed is at the wave. Nothing
        # here is chosen.
        from hero import roster
        men = [("Ahmed", (0.0, 0.0))]
        for j, kind in enumerate(site["fighters"]):
            d = (roster.spec(kind.lower())["reach"] * 0.70 + (j >> 1) * 30.0) * PX / 100.0
            men.append((kind, (d if j % 2 == 0 else -d, 0.0)))
        rigs = []
        for i, (kind, (fwd, side)) in enumerate(men):
            blend = os.path.join(fighters_dir, "%s.blend" % kind)
            assert os.path.exists(blend), "no %s -- run build_fighters.py first" % blend
            with bpy.data.libraries.load(blend, link=False) as (src, dst):
                dst.objects = list(src.objects)
            objs = [o for o in dst.objects if o is not None]
            rig = next(o for o in objs if o.type == "ARMATURE"); mesh = next(o for o in objs if o.type == "MESH" and o.parent == rig)
            for o in objs:
                if o.name.startswith("WGT_"):
                    wc = bpy.data.collections.get("WGT") or bpy.data.collections.new("WGT")
                    if wc.name not in bpy.context.scene.collection.children: bpy.context.scene.collection.children.link(wc); wc.hide_viewport = True; wc.hide_render = True
                    if o.name not in wc.objects: wc.objects.link(o)
                elif o in (rig, mesh):
                    bpy.context.scene.collection.objects.link(o)
            rig.name = "%s_%d_Rig" % (kind, i); mesh.name = "%s_%d" % (kind, i)
            x, y = cx + fx * fwd + lx * side, cy + fy * fwd + ly * side
            # every man squares up to Ahmed; Ahmed squares up to the first of them
            f0 = men[1][1][0]
            face_x, face_y = (cx + fx * f0, cy + fy * f0) if kind == "Ahmed" else (cx, cy)
            rig.location = (x, y, STREET_Z_CM / 100.0); rig.rotation_euler = (0, 0, math.radians(facing(x, y, face_x, face_y)))
            bpy.context.view_layer.update()
            CR.stance(rig, legacy.GUARD, mesh)
            for s in ("l", "r"):
                CR.set_prop(rig, "CTRL_hand_%s" % s, "fist", 1.0)
            rigs.append((kind, rig, mesh))
        # everyone looks at the man in front of him
        heads = {r.name: (r.matrix_world @ r.pose.bones["head"].matrix).translation.copy() for _, r, _ in rigs}
        for kind, rig, mesh in rigs:
            other = next(r for k, r, _ in rigs if (k == "Ahmed") != (kind == "Ahmed"))
            CR.set_world_translation(rig, "CTRL_look", heads[other.name])
            CR.set_prop(rig, "CTRL_head", "look", 1.0)
        # every man stands ON the street: his lowest evaluated vertex at the
        # flagstones, not in them
        dg = bpy.context.evaluated_depsgraph_get()
        for kind, rig, mesh in rigs:
            ev = mesh.evaluated_get(dg)
            low = min((mesh.matrix_world @ v.co).z for v in ev.data.vertices)
            assert low >= STREET_Z_CM / 100.0 - 0.001, "%s stands %.0f mm into the street" % (kind, (STREET_Z_CM / 100.0 - low) * 1000)
        cam = (cx - fx * 2.2 + lx * 4.8, cy - fy * 2.2 + ly * 4.8, 1.7)
        out = self.render(render_name, cam, (cx, cy, 1.15), lens=40, res=(1600, 900), samples=24 if self.fast else 96)
        os.makedirs(os.path.dirname(blend_out), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=blend_out)     # after the render, so the camera it framed is in the file
        return out, blend_out


# =================================================================== editor
def build_in_editor(P):
    """Inside the editor: the meshes go into L_SouqAlDawar, the level
    Tools/levels/build_levels.py made for this stage. Its Ground cube goes
    and the built ground and street stand where it stood; its AbilityGate
    keeps its class, its rows and its trigger and carries the gate wall
    instead of a cube; every other actor -- the directors, the exits, the
    player start, the lights, the fog, the post volume -- is left exactly
    as that script placed it. check() has already proved this plan puts the
    waves, the gate and the doors where that level has them, so nothing is
    spawned twice and nothing moves."""
    import unreal  # noqa: E402  (only importable inside the editor)
    # the subsystems: EditorLevelLibrary is deprecated since 5.0 and the
    # other level scripts' calls to it are theirs to change, not this one's
    EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    LES = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    EAL = unreal.EditorAssetLibrary
    models = os.path.join(PROJECT, "Content", "Models", "Souq")
    # --- import every kind once
    tasks = []
    for name in P["meshes"]:
        t = unreal.AssetImportTask()
        t.filename = os.path.join(models, name + ".fbx"); t.destination_path = MESH_DIR
        t.automated = True; t.save = True; t.replace_existing = True
        ui = unreal.FbxImportUI(); ui.import_mesh = True; ui.import_materials = True; ui.import_textures = True
        ui.import_as_skeletal = False; ui.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
        t.options = ui; tasks.append(t)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    mesh = {name: unreal.load_asset("%s/%s" % (MESH_DIR, name)) for name in P["meshes"]}
    # --- the level build_levels.py made, as it left it
    path = "%s/%s" % (MAPS_DIR, LEVEL_NAME)
    assert EAL.does_asset_exist(path), "%s is not built: run Tools/levels/build_levels.py in the editor first" % path
    unreal.log("Furnishing %s" % path); LES.load_level(path)
    have = EAS.get_all_level_actors()
    ground = next((a for a in have if a.get_actor_label() == "Ground"), None)
    if ground is not None:
        EAS.destroy_actor(ground)          # the engine cube; the sand disc and the street replace it
    # unreal.Rotator's positional order is (roll, pitch, yaw); named, so a
    # yaw cannot land in the pitch
    def spawn(cls, name, x, y, z, yaw=0.0, folder="World"):
        a = EAS.spawn_actor_from_class(cls, unreal.Vector(x, y, z), unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
        a.set_actor_label(name); a.set_folder_path("%s/%s" % (FOLDER, folder)); return a
    for i, r in enumerate(instances(P)):
        if r["slot"] == "Gates":
            continue                        # the AbilityGate below carries the wall
        a = spawn(unreal.StaticMeshActor, "%s_%03d" % (r["mesh"], i), r["x"], r["y"], r["z"], r["yaw"], folder=r["slot"])
        c = a.get_component_by_class(unreal.StaticMeshComponent); c.set_static_mesh(mesh[r["mesh"]])
        a.set_actor_scale3d(unreal.Vector(*r["scale"])); a.set_mobility(unreal.ComponentMobility.STATIC)
        if r["slot"] in ("Street", "Ground"): c.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    if P["gate"]:
        g = P["gate"]
        gate = next((a for a in have if isinstance(a, unreal.AbilityGate)), None)
        assert gate is not None, "%s has no AbilityGate for the wall to stand on" % path
        gate.set_actor_location(unreal.Vector(g["x"], g["y"], 0.0), False, False)   # the wall's origin is its foot, the cube's was its centre
        gate.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=g["yaw"]), False)
        gate.set_actor_scale3d(unreal.Vector(*g["scale"]))
        gate.get_component_by_class(unreal.StaticMeshComponent).set_static_mesh(mesh["SM_Souq_GateWall"])
    if not LES.save_current_level():
        unreal.log_error("Could not save %s" % path)


# ===================================================================== main
def main():
    a = sys.argv[1:]
    P = plan()
    if "--bite" in a:
        sys.exit(0 if bite() else 1)
    check(P)
    if "--check" in a:
        return
    describe(P)
    if "--describe" in a:
        return
    out = os.path.abspath(a[a.index("--out") + 1]) if "--out" in a else None
    draw(P, os.path.join(out or DOCS, "souq-map.png"))
    try:
        import unreal  # noqa: F401
        in_editor = True
    except ImportError:
        in_editor = False
    if in_editor:
        build_in_editor(P); return
    t0 = time.time()
    def stamp(msg): print("%6.1fs  %s" % (time.time() - t0, msg))
    S = Souq(P, out=out, fast="--fast" in a)
    S.build_kinds(); stamp("built %d mesh kinds" % len(S.kinds))
    S.bake_tiles(); stamp("baked %d materials to tiles" % len(S.mats))
    rep = S.check_meshes(); stamp("checked the meshes: " + ", ".join("%s %d" % (k.replace("SM_Souq_", ""), v["tris"]) for k, v in rep.items()))
    S.place(); stamp("placed %d instances" % len(S.placed))
    S.sun()
    written, gltf = S.export(); stamp("exported %d files, %.1f MB" % (len(written), sum(written.values()) / 1e6))
    rt = S.verify_gltf(gltf); stamp("glTF read back: %d meshes, %d nodes, %d tris, %d images, tallest %.1f m" % (
        rt["meshes"], rt["nodes"], rt["tris"], rt["images"], rt["tallest_m"]))
    assert rt["nodes"] == len(S.placed), "the glTF has %d nodes for %d placed objects" % (rt["nodes"], len(S.placed))
    assert rt["meshes"] == len({o.data.name for o in S.placed}), "the glTF has %d meshes for %d kinds placed" % (rt["meshes"], len({o.data.name for o in S.placed}))
    stamp("the minaret's FBX read back: %.2f m, %d vertices" % (S.fbx_readback["height_m"], S.fbx_readback["verts"]))
    if "--no-render" not in a:
        for r in S.renders_of_the_place(): stamp("rendered %s" % os.path.basename(r))
    if "--scene" in a:
        fighters = os.path.join(HERE, "rigs")
        blend_out = os.path.join(out or os.path.join(HERE, "scenes"), "SouqAlDawar_fight.blend")
        r, b = S.scene(fighters, blend_out); stamp("the fight: %s, %s" % (os.path.basename(r), b))
    stamp("done")


if __name__ == "__main__":
    main()
