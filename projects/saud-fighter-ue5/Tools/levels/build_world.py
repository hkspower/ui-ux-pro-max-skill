"""SAUD — Kuwait Fighter :: build the whole open world, ground and all
==============================================================================
Makes AL-HALQA as ONE Unreal map with its own geometry: the ring of eight
districts around the arena at the hub, the ground under all of it, the street
through each district, the blocks either side of that street, the rim around
each district with a gap at every way out, the roads between them -- and the
gameplay actors that make it playable.

WHY THIS EXISTS, NEXT TO Tools/fab/lay_out_world.py

That script lays the game over a map you bought: "The map is yours: its
ground, its buildings, its sky and its lighting stay exactly as imported.
This script only adds what the game needs to run in it." Which is the right
tool when you have a map -- and no map at all when you do not. Until this
file there was no way to get an open world out of this project without
sourcing one from Fab first.

So this builds the place as well as the game in it. The two are deliberately
the same world: districts are placed by the same ring derivation, at the same
DistrictExtent, with content on the same SaudArena::SpiralPoint spiral, so
laying the game over a Fab map and building this one put everything in the
same place. Use whichever you have; a Fab map will always look better than
engine cubes, and this one exists so that "better" is an upgrade rather than
a prerequisite.

THE PLACE IS DERIVED, NOT AUTHORED

Every district already knows its own stage -- how long it is, where its
fights trigger, what gates it holds and what they want -- and that was tuned
by hand in the browser build. None of it is thrown away here. The street IS
the spiral the sites were placed along, so the way through a district passes
everything the stage meant you to meet, in the order it meant you to meet it,
and a fight is always just off the road. What stands either side is a polar
lattice of plots, thinned by a per-theme density, with anything that would
stand on the street, inside a fight, or off the edge dropped.

This is the Unity port's Assets/Scripts/World/Landmarks.cs, in centimetres
instead of metres and placing Unreal actors instead of GameObjects: the same
vocabulary per theme, the same spacing, the same drop rules, the same hash.
A fourth copy of one derivation would be too many, but the alternative is a
Python file importing C#, so the two are kept deliberately identical and the
numbers below are the ones to change in BOTH when they change at all.

WHAT IS NOT HERE: the Unity port's three floors. Its districts have a cellar
and a roof; this build's do not, and inventing them here would be inventing
scope rather than porting it. Street level only, and the vocabulary tables
for the other two floors are left in place, unused, so the port is a small
job rather than a rewrite.

RUN IT INSIDE THE EDITOR, the same way as its siblings:

    exec(open(r"<project>/Tools/levels/build_world.py").read())

OUTSIDE THE EDITOR it prints what it would build, checks it, draws
Docs/world-map.png, and stops. That is how it was checked without an engine.
==============================================================================
"""

import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(PROJECT, "Content", "Data")
DOCS = os.path.join(PROJECT, "Docs")
MAPS_DIR = "/Game/Maps"
DATA_DIR = "/Game/Data"
LEVEL_NAME = "L_AlHalqa_World"
FOLDER = "SAUD"

# ---------------------------------------------------------------- the ring
# Same numbers as Tools/fab/lay_out_world.py, so the world is the same world
# whether it is built here or laid over a map from Fab. See the docstring.
LENGTH_TO_EXTENT = 1.7
MIN_EXTENT, MAX_EXTENT = 6000.0, 13000.0
GAP = 1600.0
EXIT_MARGIN = 200.0
SPAWN_RADIUS = 300.0
ACTOR_Z = 110.0
GROUND_Z = 0.0

# ------------------------------------------------------------- the street
STREET_HALF_WIDTH = 320.0      # Landmarks.StreetHalfWidth, cm
CLEARANCE = 160.0              # Landmarks.Clearance
PATH_SAMPLES = 140
PAVING_STEP = 500.0
RIM_SEGMENT = 900.0
RIM_GAP = 1100.0
SITE_RADIUS = 900.0            # how much room a fight or a gate keeps to itself

# ---------------------------------------------------------- the vocabulary
# Assets/Scripts/World/Landmarks.VocabularyFor, metres -> centimetres.
# block, tall, rim, paving, tall_is_post, spacing, density,
# min_w, max_w, min_h, max_h, tall_chance, tall_min, tall_max,
# rim_min, rim_max, yaw_jitter
def _vocab(block, tall, rim, paving, post, spacing, density,
           min_w, max_w, min_h, max_h, tall_chance, tall_min, tall_max,
           rim_min, rim_max, yaw_jitter):
    m = 100.0
    return dict(block=block, tall=tall, rim=rim, paving=paving, post=post,
                spacing=spacing * m, density=density,
                min_w=min_w * m, max_w=max_w * m, min_h=min_h * m, max_h=max_h * m,
                tall_chance=tall_chance, tall_min=tall_min * m, tall_max=tall_max * m,
                rim_min=rim_min * m, rim_max=rim_max * m, yaw_jitter=yaw_jitter)

VOCAB = {
    "Souq":       _vocab("stall", "warehouse", "wall", "flagstone", False, 10, 0.72, 2.6, 5.5, 2.6, 4.2, 0.12, 7, 10, 2.4, 3.2, 14),
    "Gym":        _vocab("hall", "chimney", "wall", "concrete", True, 15, 0.55, 5, 11, 4, 7, 0.10, 11, 15, 2.6, 3.4, 6),
    "Fishmarket": _vocab("shed", "crane", "quay", "boards", True, 13, 0.60, 3.5, 8, 3, 5, 0.14, 12, 18, 1.2, 1.8, 10),
    "Towers":     _vocab("block", "tower", "hoarding", "concrete", False, 21, 0.50, 7, 15, 6, 12, 0.42, 24, 52, 2.8, 3.6, 4),
    "Marina":     _vocab("front", "mast", "rail", "boards", True, 14, 0.58, 4, 9, 3.5, 6.5, 0.18, 10, 16, 1.0, 1.4, 8),
    "Failaka":    _vocab("ruin", "stone", "shore", "sand", False, 17, 0.45, 3, 8, 1.6, 4.5, 0.16, 5, 8, 1.0, 2.2, 26),
    "Highway":    _vocab("wreck", "pylon", "barrier", "asphalt", True, 18, 0.40, 2.4, 6, 1.6, 3.2, 0.24, 14, 22, 1.0, 1.4, 30),
    "Desert":     _vocab("tent", "rock", "dune", "sand", False, 24, 0.34, 3.5, 7, 2.2, 3.4, 0.30, 4, 9, 1.4, 2.6, 34),
    "Arena":      _vocab("seating", "floodlight", "bowl", "boards", True, 12, 0.66, 4, 9, 2.4, 5, 0.14, 16, 22, 5, 6, 6),
}
DEFAULT_VOCAB = _vocab("block", "tower", "wall", "concrete", False, 16, 0.55, 4, 9, 3, 6, 0.16, 10, 18, 2.4, 3.2, 12)

# One rig per theme, carried across from the browser build, as in
# build_levels.py. The open world is lit once, by the arena's rig, because it
# is one map with one sun -- per-district light comes from the fog and the
# post volume an artist adds later, not from nine suns fighting each other.
#
# 2026-09-26, the dark ("use darker theme style like Demon's Souls", this
# build): the one sun is a dim, cold overcast rather than the arena's warm
# day -- sun (1.00, 0.88, 0.70) at 6 lux -> an ashen blue-grey at 2, its
# disc spread to 8 degrees so shadows go soft as under cloud; the sky light
# 1.4 -> 0.5; the fog a dark cold grey (it was a warm dust, 0.86 0.72
# 0.56) and more than three times as thick. The same direction as before,
# so every shadow still falls the way it did. The anime look's own air
# (Tools/look/anime_look.py HAZE) is tuned to the same grey.
WORLD_RIG = dict(pitch=-38, yaw=-125, sun=(0.72, 0.78, 0.88), lux=2.0, angle=8.0,
                 sky=0.5, fog=(0.20, 0.23, 0.25), fogd=0.040, expo=1.02)


# ------------------------------------------------------------ the island
# JAZIRAT AL-HAJAR is built by Tools/levels/build_island.py -- shallows,
# beach, stone, rocks, jetties and animals -- and the open world uses that
# script's own terrain for its district rather than a second copy of it.
# Loaded under the module name "build_island", the one name that script's
# main block does not run under.
def _load_island():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "build_island", os.path.join(HERE, "build_island.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ISL = _load_island()


# ---------------------------------------------------------------- the souq
# SOUQ AL-DAWAR has real meshes, modelled by Tools/blender/build_souq.py from
# the browser's own drawing of it: arcaded stalls, mud-brick warehouses, the
# minaret, the rim wall, the gate wall, crates and barrels, a flagstone
# street. The world places those, from that script's own plan, instead of
# engine cubes. Its plan is plain Python; only its meshes need Blender.
def _load_souq():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "build_souq", os.path.join(HERE, "..", "blender", "build_souq.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SOUQ = _load_souq()
# The level's street mesh has its spurs out to the level's doors; the world's
# doors are elsewhere, so its street is its own mesh, made by
#     blender -b -P Tools/blender/build_souq.py -- --world
WORLD_STREET = "SM_Souq_Street_World"


def is_souq(stage):
    return stage["Name"] == SOUQ.STAGE_NAME


def is_island(stage):
    return stage["Name"] == ISL.STAGE_NAME


def reach_of(stage):
    """How far a district takes up room from its middle. Its extent, except
    on the island, whose shallows and the rocks standing in them reach past
    the stone the fights are on. The district is still its extent -- that is
    what AWaveDirector bounds and where its doors stand -- but the ring has
    to keep its neighbours off its water."""
    E = extent_of(stage)
    return E * ISL.SHALLOWS if is_island(stage) else E


# ------------------------------------------------------------------- data
def load():
    with open(os.path.join(DATA, "DT_Stages.json"), encoding="utf-8") as f:
        stages = json.load(f)
    with open(os.path.join(DATA, "DT_World.json"), encoding="utf-8") as f:
        world = json.load(f)
    return stages, world


def extent_of(stage):
    """SaudArena::DistrictExtent, in Python. See the docstring."""
    return max(MIN_EXTENT, min(MAX_EXTENT, float(stage["Length"]) * LENGTH_TO_EXTENT))


def spiral(t, extent, phase):
    """SaudArena::SpiralPoint, in Python."""
    angle = phase + t * 1.35 * 2.0 * math.pi
    radius = extent * (0.18 + 0.68 * t)
    return (math.cos(angle) * radius, math.sin(angle) * radius)


def hash01(n):
    """District.Hash01, in Python. Same integer hash, so a district looks the
    same in both open worlds."""
    x = n & 0xFFFFFFFF
    x ^= x >> 16; x = (x * 2246822519) & 0xFFFFFFFF
    x ^= x >> 13; x = (x * 3266489917) & 0xFFFFFFFF
    x ^= x >> 16
    return (x & 0xFFFFFF) / 16777215.0


def lerp(a, b, t):
    return a + (b - a) * t


def ring_order(world):
    areas = {a["Index"]: a for a in world["Areas"]}
    order = [world["StartArea"]]
    while True:
        east = areas[order[-1]].get("East")
        if not east or east["To"] in order:
            break
        order.append(east["To"])
    assert areas[order[-1]]["East"]["To"] == order[0], "the world graph is not a closed ring"
    return order


def place_ring(stages, world):
    """Tools/fab/lay_out_world.py's placement -- the arena on the centre, the
    ring districts on a circle that grows until none of them touch -- with
    one difference: "touch" is measured to the island's water rather than to
    its extent (reach_of). A Fab map brings its own ground and no sea for
    this to keep clear of, so the circle it grows is smaller than this one."""
    order = ring_order(world)
    arena_idx = next(a["Index"] for a in world["Areas"] if a["Index"] not in order and a.get("West"))
    origins = {arena_idx: (0.0, 0.0)}
    n = len(order)
    radius = 0.0
    while True:
        radius += 200.0
        trial = dict(origins)
        for slot, idx in enumerate(order):
            ang = math.pi / 2.0 - 2.0 * math.pi * slot / n
            trial[idx] = (radius * math.cos(ang), radius * math.sin(ang))
        discs = {i: (o[0], o[1], reach_of(stages[i])) for i, o in trial.items()}
        keys = list(discs)
        clash = any(math.hypot(discs[a][0] - discs[b][0], discs[a][1] - discs[b][1])
                    < discs[a][2] + discs[b][2] + GAP
                    for i, a in enumerate(keys) for b in keys[i + 1:])
        if not clash:
            return order, arena_idx, trial, radius


# --------------------------------------------------------------- the place
def path_of(extent, phase):
    """The spiral, sampled. The street runs along it."""
    return [spiral(i / float(PATH_SAMPLES - 1), extent, phase) for i in range(PATH_SAMPLES)]


def dist_to_path(path, x, y):
    """How far a point is from the street's centre line."""
    best = 1e18
    for i in range(1, len(path)):
        ax, ay = path[i - 1]; bx, by = path[i]
        abx, aby = bx - ax, by - ay
        len2 = abx * abx + aby * aby
        t = 0.0 if len2 < 1e-9 else max(0.0, min(1.0, ((x - ax) * abx + (y - ay) * aby) / len2))
        dx, dy = x - (ax + abx * t), y - (ay + aby * t)
        best = min(best, math.hypot(dx, dy))
    return best


def nearest_on_path(path, x, y):
    best, bestd = path[0], 1e18
    for p in path:
        d = (p[0] - x) ** 2 + (p[1] - y) ** 2
        if d < bestd:
            bestd, best = d, p
    return best


def paving(ax, ay, bx, by, width, kind, into):
    """Paving from a to b, in lengths of at most PAVING_STEP -- cut up rather
    than laid as one slab, so a thirty-metre spur follows the ground and
    streams as more than one thing."""
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    if length < 5.0:
        return
    steps = max(1, int(round(length / PAVING_STEP)))
    yaw = math.degrees(math.atan2(dy, dx))
    for i in range(steps):
        fx, fy = ax + dx * (i / steps), ay + dy * (i / steps)
        tx, ty = ax + dx * ((i + 1) / steps), ay + dy * ((i + 1) / steps)
        into.append(dict(kind=kind, shape="box", solid=False,
                         x=(fx + tx) * 0.5, y=(fy + ty) * 0.5, z=GROUND_Z + 3.0,
                         sx=length / steps + width * 0.5, sy=width, sz=6.0, yaw=yaw))


def sites_of(stage, extent, phase, area):
    """Everything in a district worth walking to, at the fraction along the
    stage it was tuned to happen at. The same reinterpretation the Unity port
    makes: 'distance along the stage' becomes 'how far around the district'."""
    L = max(1.0, float(stage["Length"]))
    out = []
    for wi, w in enumerate(stage.get("Waves", [])):
        if w["TriggerDistance"] < 0:
            continue
        t = min(1.0, max(0.0, w["TriggerDistance"] / L))
        sx, sy = spiral(t, extent, phase)
        out.append(dict(kind="wave", i=wi, x=sx, y=sy, r=SITE_RADIUS))
    for gi, g in enumerate(stage.get("Gates", [])):
        t = min(1.0, max(0.0, g["Distance"] / L))
        sx, sy = spiral(t, extent, phase + 0.5)
        out.append(dict(kind="gate", i=gi, x=sx, y=sy, r=SITE_RADIUS * 0.7, gate=g))
    return out


def blocks_of(extent, phase, area_index, path, sites, v, into):
    """What stands either side of the way: a polar lattice out from the
    middle, thinned by the theme's density, with anything standing on the
    street, in a fight, or off the edge dropped."""
    inner = extent - (v["max_w"] * 0.5 + 300.0)
    ring = 0
    r = extent * 0.13
    while r < extent * 0.99:
        n = max(6, int(round(2.0 * math.pi * r / v["spacing"])))
        for k in range(n):
            salt = area_index * 7919 + ring * 131 + k * 17
            wobble = (hash01(salt) - 0.5) * (2.0 * math.pi / n) * 0.8
            angle = k * 2.0 * math.pi / n + wobble
            radius = r + (hash01(salt + 1) - 0.5) * v["spacing"] * 0.35
            x, y = math.cos(angle) * radius, math.sin(angle) * radius

            if hash01(salt + 2) > v["density"]:
                continue
            if math.hypot(x, y) > inner:
                continue

            tall = hash01(salt + 3) < v["tall_chance"]
            w = lerp(v["min_w"], v["max_w"], hash01(salt + 4))
            dep = lerp(v["min_w"], v["max_w"], hash01(salt + 5))
            h = (lerp(v["tall_min"], v["tall_max"], hash01(salt + 6)) if tall
                 else lerp(v["min_h"], v["max_h"], hash01(salt + 6)))
            half = max(w, dep) * 0.5

            if dist_to_path(path, x, y) < STREET_HALF_WIDTH + half + CLEARANCE:
                continue
            if any(math.hypot(s["x"] - x, s["y"] - y) < s["r"] + half + CLEARANCE for s in sites):
                continue

            post = tall and v["post"]
            into.append(dict(
                kind=v["tall"] if tall else v["block"],
                shape="post" if post else "box", solid=True,
                x=x, y=y, z=GROUND_Z + h * 0.5,
                sx=(w * 0.5 if post else w), sy=(w * 0.5 if post else dep), sz=h,
                yaw=math.degrees(math.atan2(-y, -x)) + (hash01(salt + 7) - 0.5) * v["yaw_jitter"]))
        r += v["spacing"]
        ring += 1


def rim_of(extent, doors, v, area_index, into):
    """The district's edge, so the field ends in something rather than
    stopping -- gapped at every way out, because a gap in a wall is what
    makes a road findable from inside it."""
    e = extent - 100.0
    n = max(8, int(round(2.0 * math.pi * e / RIM_SEGMENT)))
    for i in range(n):
        ang = 2.0 * math.pi * i / n
        x, y = math.cos(ang) * e, math.sin(ang) * e
        if any(math.hypot(d[0] - x, d[1] - y) < RIM_GAP for d in doors):
            continue                    # the way out is a gap in the wall
        h = lerp(v["rim_min"], v["rim_max"], hash01(area_index * 31 + i))
        into.append(dict(kind=v["rim"], shape="box", solid=True,
                         x=x, y=y, z=GROUND_Z + h * 0.5,
                         sx=120.0, sy=RIM_SEGMENT * 0.92, sz=h,
                         yaw=math.degrees(ang)))


# ------------------------------------------------------------------- plan
def district_ground(d, idx, scenery):
    """A district of the city: a ground disc, the street along the spiral with
    spurs to its sites and its doors, blocks either side, a rim gapped at
    every way out."""
    ox, oy, E, phase = d["ox"], d["oy"], d["extent"], d["phase"]
    v, path, sites, doors = d["vocab"], d["path"], d["sites"], d["doors"]

    # --- the ground under the district
    scenery.append(dict(kind="ground", shape="disc", solid=True,
                        x=ox, y=oy, z=GROUND_Z - 50.0,
                        sx=E * 2.0, sy=E * 2.0, sz=100.0, yaw=0.0, district=idx))

    here = []
    # --- the street: the spiral, then a spur out to everything on it
    for i in range(1, len(path)):
        paving(ox + path[i - 1][0], oy + path[i - 1][1],
               ox + path[i][0], oy + path[i][1],
               STREET_HALF_WIDTH * 2.0, v["paving"], here)
    for s in sites:
        nx, ny = nearest_on_path(path, s["x"], s["y"])
        if math.hypot(s["x"] - nx, s["y"] - ny) < 100.0:
            continue
        paving(ox + nx, oy + ny, ox + s["x"], oy + s["y"],
               STREET_HALF_WIDTH * 1.3, v["paving"], here)
    # --- and out to each door, so a way out is on the road
    for dx, dy, *_ in doors:
        nx, ny = nearest_on_path(path, dx, dy)
        paving(ox + nx, oy + ny, ox + dx, oy + dy, STREET_HALF_WIDTH * 1.6, v["paving"], here)

    local = []
    blocks_of(E, phase, idx, path, sites, v, local)
    rim_of(E, [(dd[0], dd[1]) for dd in doors], v, idx, local)
    for p in local:
        p["x"] += ox; p["y"] += oy
    here.extend(local)
    for p in here:
        p["district"] = idx
    scenery.extend(here)


def island(d, idx, scenery, animals):
    """JAZIRAT AL-HAJAR as build_island.py builds it -- the same terrain, the
    same rocks, the same animals -- around the doors this world gives it
    rather than the fixed ones its standalone level has.

    Two things differ from that level, both because this is one map: the
    open sea its level draws out to three extents is left out (it would lie
    under the neighbouring districts; the shallows are the water here, and
    reach_of() keeps the ring off them), and the fights and the gate are on
    the island's own spiral, where its ruins and its animals were placed to
    keep clear of them, rather than on the half-turn the city districts put
    their gates on."""
    stage, E, phase = d["stage"], d["extent"], d["phase"]
    ox, oy = d["ox"], d["oy"]
    doors = [(dx, dy, side, link) for dx, dy, side, link, *_ in d["doors"]]

    local = []
    rocks, path, isites = ISL.terrain(stage, E, phase, doors, local)
    local = [p for p in local if p["kind"] != "sea"]
    solids = [(p["x"], p["y"], max(p["sx"], p["sy"]) * 0.5) for p in local
              if p["solid"] and p["kind"] in (ISL.RUIN["block"], ISL.RUIN["tall"])]
    beasts = ISL.fauna(E, phase, path, isites, doors, rocks, solids)

    # The island's sites, in the world's form: waves then gates, as
    # ISL.sites_of lists them, with the same radii.
    L = float(stage["Length"])
    sites = []
    for wi, w in enumerate(stage.get("Waves", [])):
        x, y = ISL.spiral(min(1.0, w["TriggerDistance"] / L), E, phase)
        sites.append(dict(kind="wave", i=wi, x=x, y=y, r=SITE_RADIUS))
    for gi, g in enumerate(stage.get("Gates", [])):
        x, y = ISL.spiral(min(1.0, g["Distance"] / L), E, phase)
        sites.append(dict(kind="gate", i=gi, x=x, y=y, r=SITE_RADIUS * 0.7, gate=g))
    assert [(round(a["x"]), round(a["y"])) for a in sites] == \
           [(round(b["x"]), round(b["y"])) for b in isites], "island sites disagree"

    # What build_island.check() needs to prove this island the way it proves
    # its own level, in the district's local frame.
    d["island"] = dict(
        stage=stage, extent=E, phase=phase, path=path, sites=isites,
        doors=doors, rocks=rocks, scenery=[dict(p) for p in local],
        animals=[dict(a) for a in beasts],
        actors=[dict(kind="Exit", name="Exit_%s" % side, x=dx, y=dy,
                     props=dict(Side=side)) for dx, dy, side, _ in doors],
        bearing={dd[2]: math.degrees(dd[6]) for dd in d["doors"]})
    d["path"], d["sites"] = path, sites
    d["vocab"] = dict(d["vocab"], paving="paving", rim=None)

    for p in local:
        p["x"] += ox; p["y"] += oy; p["district"] = idx
    scenery.extend(local)
    for a in beasts:
        a["x"] += ox; a["y"] += oy; a["district"] = idx
    animals.extend(beasts)


def souq(d, idx, scenery):
    """SOUQ AL-DAWAR as build_souq.py models it, around this world's doors.
    Its stalls, warehouses, minaret, props and gate are exactly the level's
    -- none of them depends on where a door is -- and its rim is re-gapped and
    its street re-spurred for the doors here. Its fights, its gate and its
    ways out must land where this world puts them; souq() holds them to it
    to the centimetre, so nothing the game reads moves."""
    ox, oy = d["ox"], d["oy"]
    bearing = {side: math.degrees(b) for _, _, side, _, _, _, b in d["doors"]}
    SP = SOUQ.plan(bearing=bearing, street_mesh=WORLD_STREET)
    assert abs(SP["E"] - d["extent"]) < 1e-6 and abs(SP["phase"] - d["phase"]) < 1e-9, \
        "the souq's extent or phase differs from the world's"
    for dx, dy, side, *_ in d["doors"]:
        sx, sy = SP["doors"][side]
        assert math.hypot(sx - dx, sy - dy) < 1.0, "the souq's %s door is not the world's" % side
    mine = sorted((s["kind"], s["i"], round(s["x"]), round(s["y"])) for s in SP["sites"])
    ours = sorted((s["kind"], s["i"], round(s["x"]), round(s["y"])) for s in d["sites"])
    assert mine == ours, "the souq's fights and gate are not where the world puts them"
    d["souq"] = SP
    d["vocab"] = dict(d["vocab"], rim="wall")
    M = SP["meshes"]
    for r in SOUQ.instances(SP):
        m = M[r["mesh"]]
        ground = r["slot"] == "Ground"
        scenery.append(dict(
            kind="ground" if ground else ("street" if r["slot"] == "Street" else r.get("kind", r["slot"].lower())),
            shape="disc" if ground else "mesh", mesh=r["mesh"], slot=r["slot"],
            solid=r["slot"] not in ("Street", "Ground") or ground,
            x=ox + r["x"], y=oy + r["y"], z=r["z"], yaw=r["yaw"], scale=tuple(r["scale"]),
            sx=m["w"] * r["scale"][0], sy=max(m["d"], 1.0) * r["scale"][1],
            sz=m["h"] * r["scale"][2], district=idx))


def plan(stages, world):
    order, arena_idx, origins, radius = place_ring(stages, world)
    areas = {a["Index"]: a for a in world["Areas"]}
    districts, actors, scenery, animals = {}, [], [], []

    def act(kind, name, x, y, z=0.0, **props):
        actors.append(dict(kind=kind, name=name, x=x, y=y, z=z, props=props))

    for idx in [arena_idx] + order:
        stage = stages[idx]
        ox, oy = origins[idx]
        E = extent_of(stage)
        phase = hash01(idx * 977 + 13) * 2.0 * math.pi
        v = VOCAB.get(stage["Theme"], DEFAULT_VOCAB)
        path = path_of(E, phase)
        sites = sites_of(stage, E, phase, areas.get(idx))

        # --- the doors, on the rim, facing where they lead
        doors = []
        area = areas.get(idx)
        if area:
            for side, key in (("West", "West"), ("East", "East"), ("Door", "Door")):
                link = area.get(key)
                if not link or link["To"] not in origins:
                    continue
                tx, ty = origins[link["To"]]
                bearing = math.atan2(ty - oy, tx - ox)
                r = E - EXIT_MARGIN
                dx, dy = math.cos(bearing) * r, math.sin(bearing) * r
                dest = stages[link["To"]]
                after = stages[link["AfterCleared"]]["Name"] if link["AfterCleared"] >= 0 else ""
                doors.append((dx, dy, side, link, dest, after, bearing))

        d = districts[idx] = dict(stage=stage, ox=ox, oy=oy, extent=E, phase=phase,
                                  path=path, sites=sites, doors=doors, vocab=v)
        if is_island(stage):
            island(d, idx, scenery, animals)
        elif is_souq(stage):
            souq(d, idx, scenery)
        else:
            district_ground(d, idx, scenery)
        sites = d["sites"]

        # --- the gameplay actors, as Tools/fab/lay_out_world.py places them
        act("WaveDirector", "Director_%s" % stage["Name"], ox, oy, GROUND_Z,
            StageRow=stage["Name"])
        if idx == world["StartArea"]:
            act("PlayerStart", "PlayerStart", ox + SPAWN_RADIUS, oy, GROUND_Z + ACTOR_Z)
        for s in sites:
            if s["kind"] == "wave":
                act("WaveMarker", "%s_wave%d" % (stage["Name"], s["i"] + 1),
                    ox + s["x"], oy + s["y"], GROUND_Z + 2.0)
            else:
                g = s["gate"]
                act("Gate", "%s_gate%d_%s" % (stage["Name"], s["i"] + 1, g["Type"]),
                    ox + s["x"], oy + s["y"], GROUND_Z + 150.0,
                    GateType=g["Type"], RewardAbility=g["RewardAbility"],
                    RewardExperience=g["RewardExperience"],
                    GateId="%s_gate%d" % (stage["Name"], s["i"] + 1))
        for dx, dy, side, link, dest, after, bearing in doors:
            act("Exit", "Exit_%s_%s_to_%s" % (stage["Name"], side, dest["Name"]),
                ox + dx, oy + dy, GROUND_Z + 300.0,
                Side=side, From=idx, To=link["To"], DestinationStage=dest["Name"],
                RequiredAbility=link["RequiredAbility"], AfterClearedStage=after)

    # --- the roads between districts: door to door, across the ring.
    #     With ground under them: a district's own ground is a disc of its own
    #     extent, so the gap between two of them is a hole, and a road laid
    #     across it is paving over nothing. Found by drawing the map and
    #     looking at it; check() asserts it now.
    for idx, d in districts.items():
        for dx, dy, side, link, dest, after, bearing in d["doors"]:
            other = districts.get(link["To"])
            if not other or link["To"] < idx:
                continue                     # one road per pair, not two
            back = next((o for o in other["doors"] if o[3]["To"] == idx), None)
            if not back:
                continue
            v = d["vocab"]
            ax, ay = d["ox"] + dx, d["oy"] + dy
            bx, by = other["ox"] + back[0], other["oy"] + back[1]
            span = math.hypot(bx - ax, by - ay)
            scenery.append(dict(kind="ground", shape="box", solid=True,
                                x=(ax + bx) * 0.5, y=(ay + by) * 0.5, z=GROUND_Z - 50.0,
                                sx=span, sy=STREET_HALF_WIDTH * 5.0, sz=100.0,
                                yaw=math.degrees(math.atan2(by - ay, bx - ax)),
                                district=None, road=(idx, link["To"])))
            paving(ax, ay, bx, by, STREET_HALF_WIDTH * 1.6, v["paving"], scenery)

    # --- every doorway opens onto the one that answers it
    exits = [a for a in actors if a["kind"] == "Exit"]
    for e in exits:
        back = [o for o in exits
                if o["props"]["From"] == e["props"]["To"] and o["props"]["To"] == e["props"]["From"]]
        assert len(back) == 1, "link %s has no single way back" % e["name"]
        e["props"]["DestinationExit"] = back[0]["name"]

    for p in scenery:
        p.setdefault("district", None)
    return dict(order=order, arena=arena_idx, origins=origins, radius=radius,
                districts=districts, actors=actors, scenery=scenery,
                animals=animals, stages=stages)


# ------------------------------------------------------------------ check
def check(P):
    """The same discipline Tools/fab/lay_out_world.py holds its layout to,
    over a world that now has ground under it as well as actors on it."""
    D = P["districts"]
    keys = list(D)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            da, db = D[a], D[b]
            gap = (math.hypot(da["ox"] - db["ox"], da["oy"] - db["oy"])
                   - reach_of(da["stage"]) - reach_of(db["stage"]))
            assert gap > 0, "districts %d and %d overlap" % (a, b)

    # The souq is proven by build_souq.py's own check, over the plan this
    # world made of it (souq() has already held its fights, gate and doors
    # to this world's to the centimetre).
    for idx, d in D.items():
        if "souq" in d:
            SOUQ.check(d["souq"], against_levels=False)

    # The island is proven by the island's own check, in its own frame, with
    # the bearings this world gave its doors: its ruins off the street, off
    # the fights and on the stone; every jetty whole from the stone to its
    # exit; every exit on the rim at its bearing; every animal on the ground
    # it belongs to. And nothing of it stands on a neighbour.
    for idx, d in D.items():
        if "island" not in d:
            continue
        ISL.check(d["island"])
        # Measured from the pieces themselves, water included, and held to
        # the same clear GAP the ring keeps between any two districts.
        for p in P["scenery"]:
            if p["district"] != idx:
                continue
            half = max(p["sx"], p["sy"]) * 0.5
            for j, o in D.items():
                if j != idx:
                    assert math.hypot(p["x"] - o["ox"], p["y"] - o["oy"]) >= \
                        o["extent"] + half + GAP - 1.0, \
                        "the island's %s is not clear of %s" % (p["kind"], o["stage"]["Name"])

    # Nothing solid stands on the street, in a fight, or off its district.
    on_street = in_fight = off_edge = 0
    for p in P["scenery"]:
        if not p["solid"] or p["district"] is None or p["kind"] == "ground":
            continue
        d = D[p["district"]]
        if "island" in d or "souq" in d:
            continue                      # proven above, by that place's own rules
        lx, ly = p["x"] - d["ox"], p["y"] - d["oy"]
        if math.hypot(lx, ly) > d["extent"] + 1.0:
            off_edge += 1
        half = max(p["sx"], p["sy"]) * 0.5
        if p["kind"] != d["vocab"]["rim"]:
            if dist_to_path(d["path"], lx, ly) < STREET_HALF_WIDTH + half:
                on_street += 1
            if any(math.hypot(s["x"] - lx, s["y"] - ly) < s["r"] for s in d["sites"]):
                in_fight += 1
    assert off_edge == 0, "%d things stand off the edge of their district" % off_edge
    assert on_street == 0, "%d things stand in the street" % on_street
    assert in_fight == 0, "%d things stand where a fight happens" % in_fight

    # Every way out is a gap in its own rim, or it cannot be walked through.
    blocked = 0
    for idx, d in D.items():
        for dx, dy, *_ in d["doors"]:
            for p in P["scenery"]:
                if p["district"] != idx or p["kind"] != d["vocab"]["rim"]:
                    continue
                if math.hypot(p["x"] - d["ox"] - dx, p["y"] - d["oy"] - dy) < 400.0:
                    blocked += 1
    assert blocked == 0, "%d ways out are walled up" % blocked

    # Nothing you can walk on is laid over a hole: every piece of paving
    # stands either on a district's own ground disc or on the strip carried
    # under a road between two of them.
    grounds = [p for p in P["scenery"] if p["kind"] == "ground"]
    discs = [(p["x"], p["y"], p["sx"] * 0.5) for p in grounds if p["shape"] == "disc"]
    discs += [(p["x"], p["y"], p["sx"] * 0.5) for p in P["scenery"] if p["kind"] == "plateau"]
    strips = [(p["x"], p["y"], p["sx"] * 0.5, p["sy"] * 0.5, math.radians(p["yaw"]))
              for p in grounds if p["shape"] == "box"]
    floating = 0
    for p in P["scenery"]:
        if p["solid"] or p["kind"] in ("ground", "shallows", "sea"):
            continue                      # paving is the only walkable thing
        if any(math.hypot(p["x"] - cx, p["y"] - cy) <= r for cx, cy, r in discs):
            continue
        on_strip = False
        for sx, sy, half_len, half_wide, ang in strips:
            dx, dy = p["x"] - sx, p["y"] - sy
            along = dx * math.cos(ang) + dy * math.sin(ang)
            across = -dx * math.sin(ang) + dy * math.cos(ang)
            if abs(along) <= half_len and abs(across) <= half_wide:
                on_strip = True
                break
        if not on_strip:
            floating += 1
    assert floating == 0, "%d pieces of paving are laid over nothing" % floating

    # And the doorways pair up.
    names = {a["name"] for a in P["actors"] if a["kind"] == "Exit"}
    for a in P["actors"]:
        if a["kind"] == "Exit":
            assert a["props"]["DestinationExit"] in names, a["name"]

    print("checked: no district overlaps another, nothing solid stands in a street or a")
    print("fight or off an edge, every way out is a gap in its own rim, and every")
    print("doorway opens onto the one that answers it. The island passes its own")
    print("checks at the bearings this world gives it, and stands on no neighbour.")


# --------------------------------------------------------------- describe
def describe(P):
    across = P["radius"] * 2.0 + 2.0 * max(d["extent"] for d in P["districts"].values())
    print("\nAL-HALQA, one map: %d districts round the arena, %.0f m across"
          % (len(P["districts"]), across / 100.0))
    print("%d scenery pieces, %d gameplay actors, %d animals on the island\n"
          % (len(P["scenery"]), len(P["actors"]), len(P["animals"])))
    print("  district            middle                 across   street  blocks   rim")
    for idx in [P["arena"]] + P["order"]:
        d = P["districts"][idx]
        mine = [p for p in P["scenery"] if p["district"] == idx]
        rim = d["vocab"]["rim"]
        paving_n = sum(1 for p in mine if p["kind"] in (d["vocab"]["paving"], "street"))
        rim_n = sum(1 for p in mine if p["kind"] == rim)
        block_n = sum(1 for p in mine if p["solid"] and p["kind"] not in
                      ("ground", rim, "plateau", "beach", "jetty", "banner", "crate", "barrel"))
        print("  %-18s (%8.0f, %8.0f) %7.0f m %7d %7d %5d"
              % (d["stage"]["Name"], d["ox"], d["oy"], d["extent"] * 2.0 / 100.0,
                 paving_n, block_n, rim_n))
    roads = sum(1 for p in P["scenery"] if p.get("road"))
    print("\n  %d roads between districts, each with ground carried under it" % roads)
    kinds = {}
    for p in P["scenery"]:
        kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
    print("\n  what it is made of: " +
          ", ".join("%s %d" % (k, n) for k, n in sorted(kinds.items(), key=lambda kv: -kv[1])))


def draw(P, path):
    """A top-down picture of the world, to check it by eye."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("(PIL not available; no picture)"); return
    D = P["districts"]
    reach = P["radius"] + max(d["extent"] for d in D.values()) + 2000.0
    W = 1600
    scale = W / (reach * 2.0)
    H = W
    im = Image.new("RGB", (W, H), (16, 15, 14))
    g = ImageDraw.Draw(im)
    def to(x, y): return (W / 2 + x * scale, H / 2 - y * scale)

    for p in P["scenery"]:                      # the ground under the roads
        if p["kind"] != "ground" or p["shape"] != "box":
            continue
        ang = math.radians(p["yaw"])
        hx, hy = p["sx"] * 0.5, p["sy"] * 0.5
        corners = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
        pts = [to(p["x"] + cx * math.cos(ang) - cy * math.sin(ang),
                  p["y"] + cx * math.sin(ang) + cy * math.cos(ang)) for cx, cy in corners]
        g.polygon(pts, fill=(26, 25, 22))
    for idx, d in D.items():
        ox, oy, E = d["ox"], d["oy"], d["extent"]
        if "island" in d:
            # water, beach and stone, outside in, as the island draws itself
            for p in sorted((p for p in P["scenery"] if p["district"] == idx
                             and p["shape"] == "disc"), key=lambda p: -p["sx"]):
                r = p["sx"] * 0.5
                col = {"shallows": (24, 52, 68), "beach": (110, 98, 76),
                       "plateau": (74, 70, 62)}[p["kind"]]
                g.ellipse([to(ox - r, oy + r), to(ox + r, oy - r)], fill=col)
            continue
        # ground
        g.ellipse([to(ox - E, oy + E), to(ox + E, oy - E)], fill=(30, 28, 25),
                  outline=(70, 62, 52))
    # scenery
    for d in D.values():                        # the souq's street is one mesh: draw its segments
        if "souq" in d:
            for seg in d["souq"]["street"]:
                (ax, ay), (bx, by) = seg["a"], seg["b"]
                n = max(1, int(math.hypot(bx - ax, by - ay) / PAVING_STEP))
                for k in range(n + 1):
                    g.point(to(d["ox"] + lerp(ax, bx, k / n), d["oy"] + lerp(ay, by, k / n)),
                            fill=(120, 108, 86))
    for p in P["scenery"]:
        if p["kind"] == "ground" or p["shape"] == "disc" or p.get("slot") == "Street":
            continue
        if p.get("slot") == "Rim":              # a wall is a line along its local X, not a blob
            ang = math.radians(p["yaw"])
            h = p["sx"] * 0.5
            g.line([to(p["x"] - math.cos(ang) * h, p["y"] - math.sin(ang) * h),
                    to(p["x"] + math.cos(ang) * h, p["y"] + math.sin(ang) * h)],
                   fill=(96, 92, 84), width=2)
            continue
        x, y = to(p["x"], p["y"])
        if not p["solid"]:
            g.point((x, y), fill=(120, 108, 86))              # paving
        else:
            r = max(1.0, p["sx"] * scale * 0.5)
            tall = p["sz"] > 1200.0
            col = (196, 154, 84) if tall else (96, 92, 84)
            g.ellipse([x - r, y - r, x + r, y + r], fill=col)
    for an in P["animals"]:
        x, y = to(an["x"], an["y"])
        g.point((x, y), fill=ISL.ANIMALS[an["species"]]["col"])
    # actors
    for a in P["actors"]:
        x, y = to(a["x"], a["y"])
        col = {"WaveDirector": (255, 255, 255), "Gate": (90, 200, 255),
               "Exit": (120, 255, 120), "PlayerStart": (255, 120, 255),
               "WaveMarker": (250, 170, 90)}[a["kind"]]
        r = 4 if a["kind"] in ("Exit", "PlayerStart") else 3
        g.ellipse([x - r, y - r, x + r, y + r], fill=col)
    for idx in [P["arena"]] + P["order"]:
        d = D[idx]
        g.text(to(d["ox"] - d["extent"] * 0.6, d["oy"] + d["extent"] + 900.0),
               d["stage"]["Name"], fill=(235, 230, 220))
    g.text((16, 16), "AL-HALQA, built rather than imported: eight districts round the arena, "
                     "street on the spiral, blocks either side, rim gapped at every way out.",
           fill=(200, 200, 200))
    g.text((16, 32), "JAZIRAT AL-HAJAR is build_island.py's island -- shallows, beach, stone, "
                     "rocks, jetties, animals -- round this world's doors.",
           fill=(200, 200, 200))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path)
    print("drew", path)


# ----------------------------------------------------------------- editor
def build(P):
    import unreal  # noqa: E402  (only importable inside the editor)

    ELL = unreal.EditorLevelLibrary
    EAL = unreal.EditorAssetLibrary
    mesh = {k: unreal.load_asset("/Engine/BasicShapes/%s" % v)
            for k, v in ISL.MESHES.items()}
    cube = mesh["box"]

    tables = {}
    for t in ("DT_Stages", "DT_Fighters", "DT_Attacks"):
        p = "%s/%s" % (DATA_DIR, t)
        tables[t] = unreal.load_asset(p) if EAL.does_asset_exist(p) else None
        if not tables[t]:
            unreal.log_warning("%s is not imported yet; the directors will be placed without it." % t)

    path = "%s/%s" % (MAPS_DIR, LEVEL_NAME)
    unreal.log("Building %s" % path)
    ELL.new_level(path)

    def spawn(cls, name, x, y, z, yaw=0.0, folder=None):
        # unreal.Rotator's positional order is (roll, pitch, yaw) -- named, so
        # a yaw cannot land in the pitch. Until 2026-09-23 it was
        # Rotator(0, yaw, 0), which would have tipped every turned block,
        # wall and road of the world onto its side.
        a = ELL.spawn_actor_from_class(cls, unreal.Vector(x, y, z),
                                       unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
        a.set_actor_label(name)
        a.set_folder_path("%s/%s" % (FOLDER, folder or "World"))
        return a

    def piece(name, shape, x, y, z, sx, sy, sz, yaw, solid, folder):
        a = spawn(unreal.StaticMeshActor, name, x, y, z, yaw, folder=folder)
        comp = a.get_component_by_class(unreal.StaticMeshComponent)
        comp.set_static_mesh(mesh[shape])
        a.set_actor_scale3d(unreal.Vector(sx / 100.0, sy / 100.0, sz / 100.0))
        a.set_mobility(unreal.ComponentMobility.STATIC)
        if not solid:
            comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        return a

    island_folder = {"shallows": "Island/Water", "beach": "Island/Ground",
                     "plateau": "Island/Ground", "rock": "Island/Rocks",
                     "jetty": "Island/Ways", "paving": "Island/Street"}

    # --- the souq's own meshes, imported from Content/Models/Souq the way
    #     build_souq.py imports them for its level
    souq_names = sorted({p["mesh"] for p in P["scenery"] if p.get("mesh")})
    if souq_names:
        mesh.update(SOUQ.import_meshes(souq_names))

    # --- the place
    for i, p in enumerate(P["scenery"]):
        if p.get("mesh"):
            if p["slot"] == "Gates":
                continue                # the souq's AbilityGate carries its wall, below
            a = spawn(unreal.StaticMeshActor, "%s_%d" % (p["mesh"], i), p["x"], p["y"], p["z"],
                      p["yaw"], folder="Souq/%s" % p["slot"])
            c = a.get_component_by_class(unreal.StaticMeshComponent)
            c.set_static_mesh(mesh[p["mesh"]])
            a.set_actor_scale3d(unreal.Vector(*p["scale"]))
            a.set_mobility(unreal.ComponentMobility.STATIC)
            if p["slot"] in ("Street", "Ground"):
                c.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
            continue
        if p["district"] is not None and "island" in P["districts"][p["district"]]:
            folder = island_folder.get(p["kind"], "Island/Ruins")
        else:
            folder = ("Ground" if p["kind"] == "ground" else
                      ("Street" if not p["solid"] else "Structures"))
        piece("%s_%d" % (p["kind"], i), p["shape"], p["x"], p["y"], p["z"],
              p["sx"], p["sy"], p["sz"], p.get("yaw", 0.0), p["solid"], folder)

    # --- the island's animals, as build_island.py makes them: one empty
    #     actor per animal with its parts attached, ambient only
    for i, an in enumerate(P["animals"]):
        label = "%s_%02d" % (an["species"], i)
        folder = "Island/Animals/%s" % an["species"]
        root = spawn(unreal.Actor, label, an["x"], an["y"], an["z"], an["yaw"], folder=folder)
        try:
            root.set_actor_tag(0, unreal.Name("Ambient"))
        except Exception:
            pass                       # tags are set differently across versions
        for part in ISL.animal_pieces(an):
            bit = piece("%s_%s" % (label, part["slot"]), part["shape"],
                        part["x"], part["y"], part["z"], part["sx"], part["sy"], part["sz"],
                        part["yaw"], False, folder)
            bit.attach_to_actor(root, "", unreal.AttachmentRule.KEEP_WORLD,
                                unreal.AttachmentRule.KEEP_WORLD,
                                unreal.AttachmentRule.KEEP_WORLD, False)

    souq_gate = {}
    for d in P["districts"].values():
        if "souq" in d and d["souq"]["gate"]:
            g = dict(d["souq"]["gate"])
            g["x"] += d["ox"]; g["y"] += d["oy"]
            souq_gate["%s_gate1" % d["stage"]["Name"]] = g

    # --- the game in it. These must exist wherever the player is, so they
    #     are the one thing here World Partition may not stream out.
    made = {}
    for a in P["actors"]:
        k, pr = a["kind"], a["props"]
        if k == "WaveDirector":
            act = spawn(unreal.WaveDirector, a["name"], a["x"], a["y"], a["z"], folder="Directors")
            act.set_editor_property("stage_row", unreal.Name(pr["StageRow"]))
            if tables["DT_Stages"]:   act.set_editor_property("stage_table", tables["DT_Stages"])
            if tables["DT_Fighters"]: act.set_editor_property("fighter_table", tables["DT_Fighters"])
            if tables["DT_Attacks"]:  act.set_editor_property("attack_table", tables["DT_Attacks"])
        elif k == "PlayerStart":
            act = spawn(unreal.PlayerStart, a["name"], a["x"], a["y"], a["z"], folder="Directors")
        elif k == "WaveMarker":
            act = spawn(unreal.StaticMeshActor, a["name"], a["x"], a["y"], a["z"], folder="Markers")
            act.get_component_by_class(unreal.StaticMeshComponent).set_static_mesh(cube)
            act.set_actor_scale3d(unreal.Vector(1.2, 1.2, 0.04))
        elif k == "Gate":
            act = spawn(unreal.AbilityGate, a["name"], a["x"], a["y"], a["z"], folder="Gates")
            act.get_component_by_class(unreal.StaticMeshComponent).set_static_mesh(cube)
            act.set_actor_scale3d(unreal.Vector(1.6, 0.6, 3.0))
            act.set_editor_property("gate_type", getattr(unreal.GateType, pr["GateType"].upper()))
            act.set_editor_property("reward_ability", getattr(unreal.Ability, _enum_name(pr["RewardAbility"])))
            act.set_editor_property("reward_experience", int(pr["RewardExperience"]))
            act.set_editor_property("gate_id", unreal.Name(pr["GateId"]))
            wall = souq_gate.get(pr["GateId"])
            if wall:
                # the souq's gate is its cracked wall, not a cube: the wall's
                # origin is its foot, where the cube's was its centre
                act.set_actor_location(unreal.Vector(wall["x"], wall["y"], 0.0), False, False)
                act.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=wall["yaw"]), False)
                act.set_actor_scale3d(unreal.Vector(*wall["scale"]))
                act.get_component_by_class(unreal.StaticMeshComponent).set_static_mesh(mesh[wall["mesh"]])
        elif k == "Exit":
            act = spawn(unreal.AreaExit, a["name"], a["x"], a["y"], a["z"], folder="Exits")
            act.set_editor_property("side", getattr(unreal.AreaSide, pr["Side"].upper()))
            act.set_editor_property("destination_stage", unreal.Name(pr["DestinationStage"]))
            act.set_editor_property("required_ability", getattr(unreal.Ability, _enum_name(pr["RequiredAbility"])))
            act.set_editor_property("after_cleared_stage", unreal.Name(pr["AfterClearedStage"]))
            made[a["name"]] = act
        else:
            continue
        if k in ("WaveDirector", "PlayerStart", "Gate", "Exit"):
            try:
                act.set_editor_property("is_spatially_loaded", False)
            except Exception:
                pass

    for a in P["actors"]:
        if a["kind"] == "Exit":
            made[a["name"]].set_editor_property("destination_exit", made[a["props"]["DestinationExit"]])

    # --- one sun over the whole ring
    r = WORLD_RIG
    sun = spawn(unreal.DirectionalLight, "Sun", 0, 0, 20000, folder="Lighting")
    sun.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=r["pitch"], yaw=r["yaw"]), False)
    light = sun.get_component_by_class(unreal.DirectionalLightComponent)
    light.set_intensity(r["lux"])
    light.set_light_color(unreal.LinearColor(*r["sun"]))
    light.set_editor_property("light_source_angle", r["angle"])   # overcast: soft shadows
    light.set_editor_property("atmosphere_sun_light", True)
    sky = spawn(unreal.SkyLight, "SkyLight", 0, 0, 18000, folder="Lighting")
    sl = sky.get_component_by_class(unreal.SkyLightComponent)
    sl.set_intensity(r["sky"])
    sl.set_editor_property("real_time_capture", True)
    spawn(unreal.SkyAtmosphere, "Sky", 0, 0, 0, folder="Lighting")
    fog = spawn(unreal.ExponentialHeightFog, "Fog", 0, 0, 0, folder="Lighting")
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    fc.set_editor_property("fog_density", r["fogd"])
    fc.set_editor_property("fog_inscattering_luminance", unreal.LinearColor(*r["fog"]))

    if not ELL.save_current_level():
        unreal.log_error("Could not save %s" % path)
    else:
        unreal.log("Saved %s: %d scenery, %d animals, %d actors"
                   % (path, len(P["scenery"]), len(P["animals"]), len(P["actors"])))


def _enum_name(s):
    out = ""
    for i, c in enumerate(s):
        if c.isupper() and i and not s[i - 1].isupper():
            out += "_"
        out += c.upper()
    return out


# ------------------------------------------------------------------- main
# Runs when executed -- as a script, or exec()'d inside the editor. Skipped
# only when build_souq.py --world loads this file by its own name to read
# the souq's plan out of it.
if __name__ != "build_world":
    _stages, _world = load()
    _plan = plan(_stages, _world)
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
        draw(_plan, os.path.join(DOCS, "world-map.png"))
        print("\nRun this inside the Unreal editor to build %s." % LEVEL_NAME)
