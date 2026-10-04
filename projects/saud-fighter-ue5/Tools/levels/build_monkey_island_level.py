#!/usr/bin/env python3
"""JAZIRAT AL-QIRUD -- the monkey island: the level, L_MonkeyIsland.

Asked 2026-10-02 ("build 3d map island level with monkeys as enemy and big
gorilla as map boss ... full 4k ... full ik"), settled as a NEW LEVEL,
UNREAL ONLY: its own map outside the nine districts, like the prologue, its
own waves of monkeys and the gorilla, its numbers in its own Unreal data.
The browser build and the ring are untouched; the way there is a boat
moored at the stone island (build_world.py, "the boat").

This puts together what the other island tools made:
    the ground       build_monkey_island.py     Content/Landscape/MonkeyIsland
    its maps         island_surfaces.py         Content/Textures/IslandGround
    what stands      build_island_props.py      Content/Models/Island
    the creatures    build_primates.py          Content/Models/{Monkey,Gorilla}.fbx
    their motion     build_primate_motion.py    Content/Animation/Island
    the data         (hand-authored)            Content/Data/DT_IslandFighters.csv,
                                                 Content/Data/DT_MonkeyIsland.json

THE PLAN, worked out here and checked here (no engine):
- a WaveDirector at each of the five clearings and at the temple, on its
  own stage row of DT_MonkeyIsland (bFightAtDirector: the fight wakes when
  he comes within SiteRadius of it and is fought there -- WaveDirector.cpp),
  with DT_IslandFighters for its fighters;
- the temple on the arena's plateau, its gate turned to where the trail
  comes in; the pier from the landing beach out to sea; the boat moored at
  its end; the PlayerStart on the pier's deck facing inland; the way home
  -- an AreaExit by the boat that opens L_AlHalqa_World with
  ?ArriveAt=Resume, back to the stone island;
- the foliage: palms along the beach, the jungle trees over the jungle
  floor, rocks on the rock, each on its own layer and none on the trail,
  in a clearing, on the temple's plateau or by the pier;
- the night (2026-10-03): the world's moon, sky, fog and exposure, and
  fire where it is dark -- the souq's braziers and pyres, by its numbers
  and its rules, along the way from the pier to the temple (THE NIGHT,
  below): 86 of them, checked by check_night(), and held to the souq's
  light budget per what is streamed in round a man by Tools/look/
  lighting.py -- the level is a partitioned world for that.

    python3 build_monkey_island_level.py           plan, check, draw
    python3 build_monkey_island_level.py --bite    each rule broken once
    (in the editor) py Tools/levels/build_monkey_island_level.py

UNVERIFIED -- the editor half has never run. Two parts are the least sure:
the landscape's import from the heightmap (UE 5.4 exposes no stable Python
call for it; build() tries LandscapeEditorSubsystem and, failing that,
prints the exact settings for Landscape mode's Import) and the landscape
material's layer-blend node properties. Both are as remembered. The fires
are spawned by build_souq.spawn_night, as the open world's are, and are as
unverified as theirs. So is the partitioned world: new_level's
is_partitioned_world, the landscape imported into it (Landscape mode splits
an import into streaming proxies there, as remembered), and
is_spatially_loaded on what must stay loaded.
"""

import csv
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import build_monkey_island as M                 # noqa: E402  (the ground's own constants and decoder)
sys.path.insert(0, os.path.join(PROJECT, "Tools", "blender"))
import build_souq as SOUQ                       # noqa: E402  (the night: NIGHT, its fires, its hash, its spawn)

DATA = os.path.join(PROJECT, "Content", "Data")
LAND = os.path.join(PROJECT, "Content", "Landscape", "MonkeyIsland")
PROPS = os.path.join(PROJECT, "Content", "Models", "Island", "Island_props.json")
ANIM = os.path.join(PROJECT, "Content", "Animation", "Island")
MAP = os.path.join(PROJECT, "Docs", "monkey-island-level.png")
LEVEL = "/Game/Maps/L_MonkeyIsland"
WORLD_LEVEL = "L_AlHalqa_World"
HOME_STAGE = "JaziratAlHajar"
SABOTAGE = set()

SITE_RADIUS_M = 9.0          # SaudArena::SiteRadius (900 cm)
DIRECTOR_REACH_M = 64.0      # DistrictExtent(1360) 6000 cm + the 400 cm margin: the round a director answers for
PIER_EDGE_M = 0.8           # the pier starts where the beach comes down to this, seaward of the landing
BOAT_LEN_M, BOAT_BEAM_M, BOAT_DRAFT_M = 14.0, 4.0, 1.2
# the clips the engine asks a creature for: since 2026-10-04 the 360
# locomotion's names (its binding spec, section 1) -- a walk tier and a run
# tier, eight ways each, the three turns on the spot and the run's pivot
LOCO_DIRS = ("Fwd", "FwdLeft", "Left", "BackLeft", "Back", "BackRight", "Right", "FwdRight")
TURN_SECONDS = {"Turn_L90": 0.50, "Turn_R90": 0.50, "Turn_180": 0.70, "Pivot_180": 0.45}   # SaudSteer::TurnSeconds
WALK_SHARE = 0.45                                                                          # SaudSteer::WalkShare
NEED_CLIPS = (("Guard",) + tuple("Walk_" + d for d in LOCO_DIRS) + tuple("Run_" + d for d in LOCO_DIRS)
              + tuple(TURN_SECONDS) + ("Block", "Hit_Light", "Hit_Heavy", "Down", "GetUp", "Death", "Victory"))
FPS = 30
# foliage: the cell a plant stands in (one at most, jittered), its layer and
# the least weight of it, the heights it grows at (m), the steepest ground
# (deg), and how far it keeps from the trail (m)
FOLIAGE = dict(
    Palm=dict(cell=20.0, layers=("Sand", "Grass"), weight=0.45, z=(1.2, 14.0), slope=18, trail=6.0, meshes=("A", "B", "C")),
    Tree=dict(cell=26.0, layers=("Jungle",), weight=0.5, z=(10.0, 170.0), slope=24, trail=11.0, meshes=("A", "B")),
    Rock=dict(cell=24.0, layers=("Rock",), weight=0.35, z=(4.0, 180.0), slope=40, trail=5.0, meshes=("A", "B", "C")),
)
KEEP_CLEAR = dict(site=M.SITE_R_M + 8.0, arena=M.ARENA_R_M + 12.0, pier=25.0)
COUNTS = dict(Palm=(250, 4000), Tree=(1500, 12000), Rock=(100, 3000))

# THE NIGHT (2026-10-03, Riyadh; asked as "scan for all very dark area then
# fix them ... reduce over black areas", settled as more lights where it is
# dark: the trail, the clearings and the temple). Until then the island had
# no light but the moon and the sky, in the engine and in the preview, and
# its views were the darkest in the game. It is lit now as the open world's
# districts are, by build_souq's own night -- its two fires (NIGHT: a
# brazier and a pyre, each its height, its pool, its intensity, its candela
# against WORLD_RIG's moon, which is this island's moon too, its draw
# distance, 1800 K, its shadow and its smoke), so a fire here stands to the
# moon exactly as one in the world -- and by its rules for where fire
# stands, along THE WAY a man walks: from the pier's foot across the beach
# to the landing, then the trail to the temple.
#   - the pier: a brazier at its foot, on the beach, and one at its head, on
#     the deck past the way home -- the island's one way out marked, as the
#     souq marks every one of its doors;
#   - each clearing: a pyre either side of its fight exactly as the souq
#     places a fight's pyres (build_souq.night() 1.): on the way at arc
#     +-(SiteRadius + half + fight_clear_m) from the fight, walked out half
#     a metre at a time until clear, the one before on one verge and the one
#     after on the other;
#   - the way between: a brazier every street_step_m +- step_jitter on a
#     hashed verge, by the souq's own hash with this island's seed (the
#     souq's stream is its stage index; the island is no stage). The souq
#     jitters each about a fixed 30 m lattice, which lets two neighbours
#     drift apart to 45 m; here the jitter is on the step from the light
#     before, so no two lights on the way are ever further apart than
#     street_step_m x (1 + step_jitter), 37.5 m. A spot that is not clear
#     is tried on the other verge, then walked back toward the light before
#     (never nearer it than min_gap_m), so a gap can only shorten;
#   - the temple: a pyre either side of its gate, as the souq lights a way
#     through a wall (night() 3.: the opening's half + its half + door_off_m
#     out from the axis, door_in_m inside), and pyres round its court just
#     off the paving -- the court is the 16 m the temple keeps clear
#     (build_island_props) -- as many as light its fight at its middle as
#     the souq lights every fight (its check 12: the fires out-light the
#     moon there), the gate's two counted: five, where four leave it at
#     0.92 of the moon.
# "The verge" is the souq's off-street kerb on this trail's own bed: a fire
# stands TRAIL_BED_M + its half + off_street_cm from the trail's middle,
# just off what is walked, on the carved shoulder. Every fire stands on the
# heightmap (the deck's one on the deck), no steeper under its foot than the
# trail itself may climb (TRAIL_GRADE across its half), and clear of the
# sea, the walkway, every fight, every plant's and rock's foot, the pier and
# the boat; the temple's columns, walls and throne are held off by the
# preview, against the temple's own mesh (build_map_scenes.check_island).
# WHAT IT COSTS. The souq holds each of its districts to NIGHT's budget --
# 96 lights, 32 of them shadowed, 32 smoke columns (its check 16,
# build_world's 33) -- a district being what is loaded at once. The island
# is no district: its fires are every one the souq's, shadowed and smoking,
# 86 of them over 2.3 km of one level, against the budget's 32. So
# it is held to that budget per what is streamed in round a man -- every
# light within World Partition's loading range of any spot on it, its
# directors, its start, its way home and every fire (Tools/look/lighting.py,
# LOADED_M: 22 lights, 22 shadowed, 22 smoke at the worst) -- and build()
# makes it a partitioned world, so that is what is loaded: a plain level
# would load all 86 smoke columns at once, and a smoke column has no draw
# distance to cull it by (a light does: LIGHT_CULL).
FIRE_SEED = M.SEED                                       # the island's own stream for the souq's hash
FIRE_ON_GROUND_M = SOUQ.STREET_Z_CM / 100.0              # a foot no further off its ground than the souq's flagstones stand off its sand


def h01(*k):
    x = 0
    for v in k:
        x = (x * 1000003 + int(v) * 7919 + 0x9E3779B1) & 0xFFFFFFFF
    x ^= x >> 15
    x = (x * 0x2C1B3C6D) & 0xFFFFFFFF
    x ^= x >> 12
    return (x & 0xFFFFFF) / float(0xFFFFFF)


def load_ground():
    from PIL import Image
    v = np.asarray(Image.open(os.path.join(LAND, "H_MonkeyIsland.png"))).astype(np.int64)
    h = M.decode_height(v)
    W = {n: np.asarray(Image.open(os.path.join(LAND, "W_MonkeyIsland_%s.png" % n))).astype(np.float32) / 255.0 for n in M.LAYERS}
    plan = json.load(open(os.path.join(LAND, "MonkeyIsland_plan.json")))
    return h, W, plan


def at(a, x, y):
    """Bilinear sample of a landscape-sized array at map metres."""
    n = a.shape[0]
    c = (x + M.HALF_M) / M.CELL_M
    r = (M.HALF_M - y) / M.CELL_M
    c0, r0 = int(np.clip(np.floor(c), 0, n - 2)), int(np.clip(np.floor(r), 0, n - 2))
    fc, fr = c - c0, r - r0
    return float(a[r0, c0] * (1 - fc) * (1 - fr) + a[r0, c0 + 1] * fc * (1 - fr) + a[r0 + 1, c0] * (1 - fc) * fr + a[r0 + 1, c0 + 1] * fc * fr)


def slope_deg(h, x, y):
    gx = (at(h, x + 1, y) - at(h, x - 1, y)) / 2.0
    gy = (at(h, x, y + 1) - at(h, x, y - 1)) / 2.0
    return math.degrees(math.atan(math.hypot(gx, gy)))


def ue(x, y, z):
    """Map metres (x east, y north, z up) to Unreal centimetres (Y south)."""
    return (x * 100.0, -y * 100.0, z * 100.0)


def ue_yaw(bearing_deg):
    """A map bearing (from +x toward +y) as an Unreal yaw."""
    return -bearing_deg


# ----------------------------------------------------------------- the night's helpers
def foot_r(f, props):
    """How far round its foot a plant or a rock is solid, metres, as
    build_island_props builds it: a palm's swollen foot (palm(): r0 0.19 at
    1 + 0.45), a jungle tree's buttress roots (tree(): (0.45 + 0.02 h) at
    1 + 1.6), a boulder's jittered sphere (rock(): half its size at most
    0.72 + 0.28 + 0.10) -- each at its row's scale."""
    m = props["meshes"][f["mesh"]]
    if f["kind"] == "Palm":
        r = 0.19 * 1.45
    elif f["kind"] == "Tree":
        r = (0.45 + 0.02 * m["height"]) * 2.6
    else:
        r = m["size"] * 0.5 * 1.10
    return r * f["scale"]


def way_of(pier, trail):
    """The way a man walks the island, (x, y) metres: from the pier's foot
    across the beach to the landing, where the trail starts, then the trail
    to the temple's middle."""
    return [(pier["x"], pier["y"])] + [(float(x), float(y)) for x, y in trail]


def way_near(W, s_, x, y):
    """From (x, y) to the way (an (n, 2) array, s_ its arc): how far, and the
    arc length of the nearest point on it, metres."""
    a, ab = W[:-1], W[1:] - W[:-1]
    l2 = np.maximum((ab ** 2).sum(1), 1e-12)
    t = np.clip(((x - a[:, 0]) * ab[:, 0] + (y - a[:, 1]) * ab[:, 1]) / l2, 0.0, 1.0)
    d = np.hypot(x - (a[:, 0] + ab[:, 0] * t), y - (a[:, 1] + ab[:, 1] * t))
    k = int(np.argmin(d))
    return float(d[k]), float(s_[k] + t[k] * math.sqrt(l2[k]))


def misfit(h, x, y, z, r):
    """The most the ground under a round foot of radius r stands off z, its
    middle's height, metres: eight points round its rim."""
    return max(abs(at(h, x + r * math.cos(k * math.pi / 4), y + r * math.sin(k * math.pi / 4)) - z) for k in range(8))


def moons(fires, x, y):
    """What the fires give the ground at (x, y) metres, in moons --
    build_souq.ground_light, in its centimetres."""
    return SOUQ.ground_light([dict(x=f["x"] * 100.0, y=f["y"] * 100.0, I=f["I"], h=f["h"]) for f in fires],
                             x * 100.0, y * 100.0)


def pier_frame(pr, x, y):
    """(x, y) in the pier's own frame: metres along it from its foot, and
    across it (positive on the boat's side)."""
    ux, uy = pr["u"]
    dx, dy = x - pr["x"], y - pr["y"]
    return dx * ux + dy * uy, -dx * uy + dy * ux


def read_tables():
    with open(os.path.join(DATA, "DT_IslandFighters.csv"), encoding="utf-8") as f:
        fighters = {r["Name"]: r for r in csv.DictReader(f)}
    stages = {s["Name"]: s for s in json.load(open(os.path.join(DATA, "DT_MonkeyIsland.json"), encoding="utf-8"))}
    with open(os.path.join(DATA, "DT_Attacks.csv")) as f:
        attacks = {r["Name"] for r in csv.DictReader(f)}
    return fighters, stages, attacks


# ======================================================================= plan

def plan():
    h, W, gp = load_ground()
    props = json.load(open(PROPS))
    fighters, stages, attacks = read_tables()
    P = dict(actors=[], foliage=[], ground=gp)
    trail = np.array([[x, y] for x, y, _ in gp["trail"]])
    # the directors: a clearing each, then the temple
    rows = sorted(n for n in stages if n.startswith("Island_Clearing_"))
    for i, (row, site) in enumerate(zip(rows, gp["sites"])):
        x, y, z = site["x"], site["y"], site["z"]
        if "director_off_site" in SABOTAGE and i == 2:
            x += 30.0
        P["actors"].append(dict(kind="WaveDirector", name="Director_%s" % row, x=x, y=y, z=z, row=row))
    ar = gp["arena"]
    P["actors"].append(dict(kind="WaveDirector", name="Director_Island_Temple", x=ar["x"], y=ar["y"], z=ar["z"],
                            row="Island_Temple"))
    # the temple: its gate (local -X) to where the trail comes in
    d = np.hypot(trail[:, 0] - ar["x"], trail[:, 1] - ar["y"])
    k = int(np.nonzero(d <= ar["r"] + 2.0)[0][0])
    gate_bearing = math.degrees(math.atan2(trail[k, 1] - ar["y"], trail[k, 0] - ar["x"]))
    yaw_gate = gate_bearing + (180.0 if "temple_backwards" in SABOTAGE else 0.0)
    P["actors"].append(dict(kind="Prop", name="SM_Island_Temple", mesh="SM_Island_Temple", x=ar["x"], y=ar["y"],
                            z=ar["z"], bearing=yaw_gate + 180.0, gate_bearing=gate_bearing))
    # the pier, out to sea from the landing; the boat at its end; the start
    lx, ly = gp["landing"]["x"], gp["landing"]["y"]
    out = math.degrees(math.atan2(ly, lx))
    if "pier_inland" in SABOTAGE:
        out += 180.0
    ux, uy = math.cos(math.radians(out)), math.sin(math.radians(out))
    tx, ty = -uy, ux
    PIER_OUT_M = props["pier"]["length"]
    for s0 in range(0, 200):                          # out from the landing to the water's edge
        if at(h, lx + ux * s0, ly + uy * s0) <= PIER_EDGE_M:
            break
    lx, ly = lx + ux * s0, ly + uy * s0
    lz = at(h, lx, ly)
    P["actors"].append(dict(kind="Prop", name="SM_Island_Pier", mesh="SM_Island_Pier", x=lx, y=ly, z=lz, bearing=out))
    deck = lz + props["pier"]["deck"]
    side = props["pier"]["width"] / 2 + BOAT_BEAM_M / 2 + 0.3
    bx, by = lx + ux * (PIER_OUT_M - 6.0) + tx * side, ly + uy * (PIER_OUT_M - 6.0) + ty * side
    bz = 0.0 if "boat_aground" not in SABOTAGE else lz
    if "boat_aground" in SABOTAGE:
        bx, by = lx - ux * 20.0, ly - uy * 20.0
    P["actors"].append(dict(kind="Prop", name="SM_Island_Boat", mesh="SM_Island_Boat", x=bx, y=by, z=bz, bearing=out))
    P["actors"].append(dict(kind="PlayerStart", name="PlayerStart", x=lx + ux * 4.0, y=ly + uy * 4.0, z=deck + 1.1,
                            bearing=out + 180.0))
    P["actors"].append(dict(kind="Exit", name="Exit_Boat_Home", x=lx + ux * (PIER_OUT_M - 3.0), y=ly + uy * (PIER_OUT_M - 3.0),
                            z=deck + 1.5, DestinationLevel=WORLD_LEVEL, DestinationStage=HOME_STAGE, ArriveAt="Resume"))
    P["pier"] = dict(x=lx, y=ly, z=lz, deck=deck, bearing=out, u=(ux, uy), length=PIER_OUT_M)
    P["boat"] = dict(x=bx, y=by, z=bz, u=(ux, uy))
    # the foliage
    sites = [(s["x"], s["y"]) for s in gp["sites"]]
    for kind, F in FOLIAGE.items():
        c = F["cell"]
        n = int(2 * M.HALF_M / c)
        pts = []
        for i in range(n):
            for j in range(n):
                x = -M.HALF_M + (i + h01(i, j, 1, len(kind))) * c
                y = -M.HALF_M + (j + h01(i, j, 2, len(kind))) * c
                if math.hypot(x, y) > M.COAST_R_M + M.COAST_WARP_M + 50:
                    continue
                pts.append((x, y, i, j))
        if not pts:
            continue
        A = np.array([p[:2] for p in pts])
        dt = np.min(np.hypot(A[:, None, 0] - trail[None, ::2, 0], A[:, None, 1] - trail[None, ::2, 1]), axis=1)
        for (x, y, i, j), dtr in zip(pts, dt):
            z = at(h, x, y)
            if not F["z"][0] <= z <= F["z"][1]:
                continue
            wsum = sum(at(W[l], x, y) for l in F["layers"])
            if wsum < F["weight"] or slope_deg(h, x, y) > F["slope"]:
                continue
            if dtr < F["trail"] and "tree_on_trail" not in SABOTAGE:
                continue
            if any(math.hypot(x - sx, y - sy) < KEEP_CLEAR["site"] for sx, sy in sites):
                continue
            if math.hypot(x - ar["x"], y - ar["y"]) < KEEP_CLEAR["arena"] or math.hypot(x - lx, y - ly) < KEEP_CLEAR["pier"]:
                continue
            v = F["meshes"][int(h01(i, j, 3) * len(F["meshes"])) % len(F["meshes"])]
            P["foliage"].append(dict(kind=kind, mesh="SM_Island_%s_%s" % (kind, v), x=x, y=y, z=z - 0.1,
                                     yaw=h01(i, j, 4) * 360.0, scale=0.85 + 0.3 * h01(i, j, 5), trail=float(dtr)))
    if "tree_on_trail" in SABOTAGE:
        x, y = trail[len(trail) // 3]
        P["foliage"].append(dict(kind="Tree", mesh="SM_Island_Tree_A", x=float(x), y=float(y), z=at(h, x, y), yaw=0, scale=1,
                                 trail=0.0))
    P["h"], P["W"] = h, W
    P["tables"] = (fighters, stages, attacks)
    P["trail"] = trail
    P["props"] = props
    night(P)
    return P


def night(P):
    """The island's fires (see THE NIGHT, at the top): P["fires"], rows of
    build_souq._fire in map metres -- x, y, z the foot, yaw its bearing --
    each with where it stands ("pier", "way", "clearing", "gate", "court")
    and what on ("ground", "deck"); and P["way"], P["way_s"]."""
    N = SOUQ.NIGHT
    h, gp, props = P["h"], P["ground"], P["props"]
    T = props["temple"]
    rig = SOUQ._world_rig()
    margin = N["site_margin_cm"] / 100.0
    pr = P["pier"]
    ar = gp["arena"]
    path = way_of(pr, P["trail"])
    W = np.array(path)
    s_ = SOUQ._arc(path)
    P["way"], P["way_s"] = W, s_
    half = {k: N[k]["half"] / 100.0 for k in SOUQ.FIRE_KINDS}
    plants = np.array([(f["x"], f["y"], foot_r(f, props)) for f in P["foliage"]]).reshape(-1, 3)
    sites = [(s["x"], s["y"]) for s in gp["sites"]]
    fires = []

    def kerb(s, side, hm):
        return _verge(path, s_, s, side, hm)

    def clear(x, y, hm):
        """The souq's clear(), on this island: on land, the ground under its
        foot no steeper than the trail, off the walkway, out of every fight
        and off the temple's plateau, clear of every plant's and rock's foot
        and of the pier, each by the souq's site margin."""
        z = at(h, x, y)
        if z <= M.LAND_MIN_M or misfit(h, x, y, z, hm) > M.TRAIL_GRADE * hm:
            return False
        if way_near(W, s_, x, y)[0] < M.TRAIL_BED_M + hm:
            return False
        if any(math.hypot(sx - x, sy - y) <= SITE_RADIUS_M + hm + margin for sx, sy in sites):
            return False
        if math.hypot(ar["x"] - x, ar["y"] - y) <= ar["r"] + hm + margin:
            return False
        if len(plants) and (np.hypot(plants[:, 0] - x, plants[:, 1] - y) - plants[:, 2] < hm + margin).any():
            return False
        along, across = pier_frame(pr, x, y)
        return not (-hm - margin < along < pr["length"] + hm + margin and abs(across) < props["pier"]["width"] / 2 + hm + margin)

    def fire(kind, x, y, z, yaw, **kw):
        fires.append(SOUQ._fire(kind, x, y, z, yaw, rig, **kw))
        return fires[-1]

    # --- the pier: its foot on the verge where the way starts, on the side
    #     away from the boat (walked inland until clear); its head on the deck
    #     past the way home, as far out as the deck goes
    bx, by = P["boat"]["x"], P["boat"]["y"]
    _, _, tx, ty = SOUQ._at(path, s_, 0.0)
    away = 1 if (-ty) * (bx - pr["x"]) + tx * (by - pr["y"]) < 0 else -1
    s = 0.0
    for _ in range(80):
        x, y, yaw = kerb(s, away, half["brazier"])
        if clear(x, y, half["brazier"]):
            break
        s += 0.5
    fire("brazier", x, y, at(h, x, y), yaw, where="pier", on="ground", s=s, side=away)
    ux, uy = pr["u"]
    out = pr["length"] - half["brazier"] - margin
    fire("brazier", pr["x"] + ux * out, pr["y"] + uy * out, pr["deck"], pr["bearing"], where="pier", on="deck")
    # --- each clearing: a pyre either side of its fight, the souq's way
    hp = half["pyre"]
    for i, (sx, sy) in enumerate(sites):
        if "no_clearing_pyres" in SABOTAGE and i == 2:
            continue
        i0 = int(np.argmin(np.hypot(W[:, 0] - sx, W[:, 1] - sy)))
        for sign in (-1, 1):
            ss = s_[i0] + sign * (SITE_RADIUS_M + hp + N["fight_clear_m"])
            for _ in range(80):
                x, y, yaw = kerb(ss, sign, hp)
                if clear(x, y, hp):
                    break
                ss += sign * 0.5
            else:
                continue
            if 0.0 < ss < s_[-1]:
                fire("pyre", x, y, at(h, x, y), yaw, where="clearing", on="ground", s=ss, side=sign, site=i)
    # --- the temple: a pyre either side of its gate, door_in_m inside it;
    #     then its court's ring, as many as light its fight with the gate's two
    tem = next(a for a in P["actors"] if a.get("mesh") == "SM_Island_Temple")
    gb = math.radians(tem["gate_bearing"])
    g, n_ = (math.cos(gb), math.sin(gb)), (-math.sin(gb), math.cos(gb))
    r_in, off = T["gate_r"] - N["door_in_m"], T["gate_w"] / 2.0 + hp + N["door_off_m"]
    for sg in (-1, 1):
        if "no_gate_pyres" in SABOTAGE:
            continue
        x, y = ar["x"] + g[0] * r_in + n_[0] * off * sg, ar["y"] + g[1] * r_in + n_[1] * off * sg
        fire("pyre", x, y, at(h, x, y), tem["gate_bearing"], where="gate", on="ground", side=sg)
    gate = list(fires[-2:]) if "no_gate_pyres" not in SABOTAGE else []
    n = next(n for n in range(1, 25) if moons(gate + _court_ring(P, n), ar["x"], ar["y"]) >= 1.0)
    fires += _court_ring(P, n - (1 if "court_short" in SABOTAGE else 0))
    P["court_n"] = n
    # --- the way between: a brazier street_step_m (1 +- step_jitter) after
    #     the light before, from the pier's foot to the temple's gate
    s_gate = min(way_near(W, s_, f["x"], f["y"])[1] for f in gate) if gate else s_[-1]
    anchors = sorted([fires[0]["s"]] + [f["s"] for f in fires if f["where"] == "clearing"] + [s_gate])
    step, jit, gap = N["street_step_m"], N["step_jitter"], N["min_gap_m"]
    hb = half["brazier"]
    k = 0
    for a, b in zip(anchors[:-1], anchors[1:]):
        s = a
        while b - s > step * (1.0 + jit):
            seed = FIRE_SEED * 4051 + k * 29
            j = (SOUQ.hash01(seed + 5) - 0.5) * 2.0 * jit
            side = 1 if SOUQ.hash01(seed + 6) < 0.5 else -1
            k += 1
            want, got = min(s + step * (1.0 + j), b - gap), None
            t = want
            while t >= s + gap and got is None:
                for sd in (side, -side):
                    x, y, yaw = kerb(t, sd, hb)
                    if clear(x, y, hb):
                        got = (t, sd, x, y, yaw)
                        break
                t -= 0.5
            if got is None:
                s = want                    # nothing clear back to the light before: check() reports the gap
                continue
            t, sd, x, y, yaw = got
            fire("brazier", x, y, at(h, x, y), yaw, where="way", on="ground", s=t, side=sd)
            s = t
    _night_sabotage(P, fires)
    P["fires"] = fires


def _night_sabotage(P, fires):
    """--bite: each of the night's rules broken once, after the plan."""
    way = [f for f in fires if f["where"] == "way"]
    clearing = [f for f in fires if f["where"] == "clearing"]
    court = [f for f in fires if f["where"] == "court"]
    deck = next(f for f in fires if f["on"] == "deck")
    path, s_, h = [tuple(p) for p in P["way"]], P["way_s"], P["h"]
    pr, bt, ar = P["pier"], P["boat"], P["ground"]["arena"]
    ux, uy = pr["u"]

    def stand(f, x, y, z=None):
        f["x"], f["y"] = x, y
        f["z"] = at(h, x, y) if z is None else z

    def round_court(f, deg):
        """f carried deg round the temple's middle, as far from it as it was."""
        a = math.atan2(f["y"] - ar["y"], f["x"] - ar["x"]) + math.radians(deg)
        r = math.hypot(f["x"] - ar["x"], f["y"] - ar["y"])
        stand(f, ar["x"] + math.cos(a) * r, ar["y"] + math.sin(a) * r)
    # every fire NIGHT's own, each way that can drift: a kind that is not
    # the night's, a number (its height), a flag (its shadow), its watts
    if "bad_kind" in SABOTAGE:
        way[30]["kind"] = "torch"
    if "spec_h_drift" in SABOTAGE:
        clearing[4]["h"] = 3.5
    if "fire_unshadowed" in SABOTAGE:
        way[7]["shadow"] = False
    if "watts_drift" in SABOTAGE:
        way[5]["watts"] *= 1.5
    # the deck's brazier: off the deck to the side away from the boat, and
    # back down the deck into the way home
    if "deck_off" in SABOTAGE:
        stand(deck, deck["x"] + uy * 3.0, deck["y"] - ux * 3.0, deck["z"])
    if "deck_in_way_home" in SABOTAGE:
        stand(deck, pr["x"] + ux * 40.0, pr["y"] + uy * 40.0, deck["z"])
    if "fire_in_boat" in SABOTAGE:
        stand(deck, bt["x"], bt["y"], deck["z"])
    # where a ground fire may not stand: on steeper ground than the trail
    # climbs (the first way brazier with such ground within 30 m square out
    # from the trail, either side, carried onto it -- the trail mostly runs
    # through gentle ground, two of the 67 have any), on the pier, on the
    # temple's court, past its verge, in a clearing's fight
    if "fire_steep" in SABOTAGE:
        def steep():
            for f in way:
                hm = f["half"] / 100.0
                _, _, tx, ty = SOUQ._at(path, s_, f["s"])
                for sd in (f["side"], -f["side"]):
                    for k in range(1, 61):
                        x, y = f["x"] - ty * sd * 0.5 * k, f["y"] + tx * sd * 0.5 * k
                        if at(h, x, y) > M.LAND_MIN_M and misfit(h, x, y, at(h, x, y), hm) > 1.5 * M.TRAIL_GRADE * hm:
                            return f, x, y
        f, x, y = steep()
        stand(f, x, y)
    if "fire_on_pier" in SABOTAGE:
        stand(fires[0], pr["x"] + ux * 2.0, pr["y"] + uy * 2.0)
    if "fire_on_court" in SABOTAGE:
        f = court[2]
        a = math.atan2(f["y"] - ar["y"], f["x"] - ar["x"])
        stand(f, ar["x"] + math.cos(a) * 12.0, ar["y"] + math.sin(a) * 12.0)
    if "way_past_verge" in SABOTAGE:
        f = way[18]
        _, _, tx, ty = SOUQ._at(path, s_, f["s"])
        stand(f, f["x"] - ty * f["side"] * 6.0, f["y"] + tx * f["side"] * 6.0)
    if "fire_in_fight" in SABOTAGE:
        s = P["ground"]["sites"][clearing[2]["site"]]
        stand(clearing[2], s["x"], s["y"])
    # a clearing's pair: one pyre half a walk-out past the souq's arc, one
    # on the other verge, and a clearing's pair walked 15 m further out
    # (still on the arc, whole walk-outs) so its fight is left to the moon
    if "clearing_off_arc" in SABOTAGE:
        f = clearing[6]
        f["s"] += f["side"] * 0.25
        x, y, f["yaw"] = _verge(path, s_, f["s"], f["side"], f["half"] / 100.0)
        stand(f, x, y)
    if "clearing_wrong_verge" in SABOTAGE:
        f = clearing[7]
        f["side"] = -f["side"]
        x, y, f["yaw"] = _verge(path, s_, f["s"], f["side"], f["half"] / 100.0)
        stand(f, x, y)
    if "clearing_dark" in SABOTAGE:
        for f in clearing:
            if f["site"] == 2:
                f["s"] += f["side"] * 15.0
                x, y, f["yaw"] = _verge(path, s_, f["s"], f["side"], f["half"] / 100.0)
                stand(f, x, y)
    # the temple's court: one pyre turned 10 degrees off its place in the
    # ring, and the ring one pyre bigger than its fight needs
    if "court_uneven" in SABOTAGE:
        round_court(court[1], 10.0)
    if "court_extra" in SABOTAGE:
        for f in court:
            fires.remove(f)
        fires += _court_ring(P, P["court_n"] + 1)
    if "trail_gap" in SABOTAGE:
        fires.remove(way[20])
        fires.remove(way[21])
    if "fire_in_sea" in SABOTAGE:
        f = fires[0]
        ux, uy = P["pier"]["u"]
        f["x"], f["y"] = f["x"] + ux * 30.0, f["y"] + uy * 30.0
        f["z"] = at(P["h"], f["x"], f["y"])
    if "fire_floating" in SABOTAGE:
        way[10]["z"] += 0.5
    if "fire_in_walkway" in SABOTAGE:
        f = way[12]
        f["x"], f["y"] = SOUQ._at([tuple(p) for p in P["way"]], P["way_s"], f["s"])[:2]
        f["z"] = at(P["h"], f["x"], f["y"])
    if "fire_in_rock" in SABOTAGE:
        rocks = [p for p in P["foliage"] if p["kind"] == "Rock"]
        f = way[15]
        r = min(rocks, key=lambda p: math.hypot(p["x"] - f["x"], p["y"] - f["y"]))
        f["x"], f["y"] = r["x"], r["y"]
        f["z"] = at(P["h"], f["x"], f["y"])
    if "fire_spec_drift" in SABOTAGE:
        way[5]["cd"] *= 1.5
    if "pier_head_dark" in SABOTAGE:
        fires.remove(next(f for f in fires if f["on"] == "deck"))


# ======================================================================= check

def check(P):
    miss = []
    h, W = P["h"], P["W"]
    fighters, stages, attacks = P["tables"]
    gp = P["ground"]
    trail = P["trail"]
    dirs = [a for a in P["actors"] if a["kind"] == "WaveDirector"]
    # the directors on their sites, on their rows
    want = [(s["x"], s["y"], s["z"]) for s in gp["sites"]] + [(gp["arena"]["x"], gp["arena"]["y"], gp["arena"]["z"])]
    for a, (x, y, z) in zip(dirs, want):
        if math.hypot(a["x"] - x, a["y"] - y) > 1.0 or abs(a["z"] - z) > 0.6:
            miss.append("%s stands %.1f m from its site" % (a["name"], math.hypot(a["x"] - x, a["y"] - y)))
        if a["row"] not in stages:
            miss.append("%s's row %s is not in DT_MonkeyIsland" % (a["name"], a["row"]))
        elif not stages[a["row"]].get("bFightAtDirector"):
            miss.append("%s's row does not fight at its director" % a["name"])
    for i, a in enumerate(dirs):
        for b in dirs[i + 1:]:
            if math.hypot(a["x"] - b["x"], a["y"] - b["y"]) < 2 * DIRECTOR_REACH_M:
                miss.append("%s and %s answer for the same ground" % (a["name"], b["name"]))
    # the data: every fighter known, every move a row, every clip on disk
    # and in the manifest, a turn as long as the game holds it, his
    # MoveSpeed the pace his RUN tier was struck at and his walks at the
    # spec's share of it
    import importlib.util
    spec = importlib.util.spec_from_file_location("bpm", os.path.join(PROJECT, "Tools", "blender", "build_primate_motion.py"))
    bpm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bpm)
    mpath = os.path.join(ANIM, "DT_IslandMotion.csv")
    motion = {}
    if os.path.exists(mpath):
        with open(mpath, newline="", encoding="utf-8") as fh:
            motion = {r["Name"]: r for r in csv.DictReader(fh)}
    for row in stages.values():
        for w in row["Waves"]:
            for f in w["Fighters"]:
                if f not in fighters:
                    miss.append("%s sends %s, who is not in DT_IslandFighters" % (row["Name"], f))
    for name, r in fighters.items():
        moves = [m.strip().strip('"') for m in r["Moves"].strip("()").split(",") if m.strip()]
        for m in moves:
            if m not in attacks:
                miss.append("%s throws %s, which is not an attack row" % (name, m))
        for c in NEED_CLIPS + tuple(moves):
            gone = "clip_missing" in SABOTAGE and name == "Gorilla" and c == "Run_FwdLeft"
            if gone or not os.path.exists(os.path.join(ANIM, "A_%s_%s.fbx" % (name, c))):
                miss.append("%s has no clip %s" % (name, c))
            elif "A_%s_%s" % (name, c) not in motion:
                miss.append("%s's clip %s is not in DT_IslandMotion.csv" % (name, c))
        for c, secs in TURN_SECONDS.items():
            row = motion.get("A_%s_%s" % (name, c))
            if row:
                got = float(row["Seconds"]) + (0.1 if "turn_drift" in SABOTAGE and c == "Turn_180" else 0.0)
                if abs(got - secs) * FPS > 1.0 + 1e-6:
                    miss.append("%s's %s lasts %.3f s, the game holds it %.2f s" % (name, c, got, secs))
        if set(moves) != set(bpm.STRIKES.get(name, ())):
            miss.append("%s's moves %s are not the strikes his clips were struck for %s" % (name, moves, bpm.STRIKES.get(name)))
        speed = float(r["MoveSpeed"]) * (WALK_SHARE if "speed_walk" in SABOTAGE and name == "Monkey" else 1.0)
        if abs(speed - bpm.PACE.get(name, -1)) > 0.5:
            miss.append("%s moves at %.0f cm/s, his runs were struck at %s" % (name, speed, bpm.PACE.get(name)))
        if abs(getattr(bpm, "WALK_SHARE", -1.0) - WALK_SHARE) > 1e-9:
            miss.append("%s's walks were struck at %s of his run, the spec's share is %s" % (name, getattr(bpm, "WALK_SHARE", None), WALK_SHARE))
        mesh = r["Mesh"].split("/")[-1].split(".")[0]
        if not os.path.exists(os.path.join(PROJECT, "Content", "Models", mesh + ".fbx")):
            miss.append("%s wears %s, which is not in Content/Models" % (name, mesh))
        if r["FightStyle"].split(".")[-1] != "DA_Style_%s" % name:
            miss.append("%s's style is %s" % (name, r["FightStyle"]))
    if not any(fighters[f]["bIsBoss"] == "true" for f in stages.get("Island_Temple", {}).get("Waves", [{}])[0].get("Fighters", [])):
        miss.append("the temple's wave has no boss")
    # the temple's gate to the trail
    t = next(a for a in P["actors"] if a.get("mesh") == "SM_Island_Temple")
    gate_dir = t["bearing"] + 180.0                     # its local -X
    off = abs((gate_dir - t["gate_bearing"] + 180) % 360 - 180)
    if off > 5.0:
        miss.append("the temple's gate faces %.0f degrees off the trail" % off)
    # the pier: from the beach out over the water
    pr = P["pier"]
    ux, uy = pr["u"]
    far = at(h, pr["x"] + ux * pr["length"], pr["y"] + uy * pr["length"])
    if not 0.3 <= pr["z"] <= 4.0:
        miss.append("the pier starts %.1f m up, not on the beach" % pr["z"])
    if far > -1.0:
        miss.append("the pier's end stands on ground %.1f m, not over water" % far)
    if pr["deck"] < 0.5:
        miss.append("the pier's deck is under the sea")
    # the boat afloat: deep enough under every corner of its hull
    b = P["boat"]
    ux, uy = b["u"]
    tx, ty = -uy, ux
    worst = max(at(h, b["x"] + ux * s * BOAT_LEN_M / 2 + tx * q * BOAT_BEAM_M / 2,
                   b["y"] + uy * s * BOAT_LEN_M / 2 + ty * q * BOAT_BEAM_M / 2) for s in (-1, 0, 1) for q in (-1, 0, 1))
    if worst > b["z"] - BOAT_DRAFT_M - 0.3 or b["z"] != 0.0:
        miss.append("the boat is aground: the seabed at %.1f m under a keel at %.1f" % (worst, b["z"] - BOAT_DRAFT_M))
    # the start and the way home
    ps = next(a for a in P["actors"] if a["kind"] == "PlayerStart")
    ex = next(a for a in P["actors"] if a["kind"] == "Exit")
    if math.hypot(ps["x"] - ex["x"], ps["y"] - ex["y"]) < 10.0:
        miss.append("he would start in the way home")
    if math.hypot(ex["x"] - b["x"], ex["y"] - b["y"]) > 8.0:
        miss.append("the way home is not by the boat")
    # the foliage: on its layer and its ground, off the trail and the fights
    counts = {}
    bad = dict(trail=0, site=0, layer=0)
    sites = [(s["x"], s["y"]) for s in gp["sites"]]
    ar = gp["arena"]
    for f in P["foliage"]:
        counts[f["kind"]] = counts.get(f["kind"], 0) + 1
        F = FOLIAGE[f["kind"]]
        if f["trail"] < F["trail"]:
            bad["trail"] += 1
        if any(math.hypot(f["x"] - sx, f["y"] - sy) < M.SITE_R_M + 2 for sx, sy in sites) or \
                math.hypot(f["x"] - ar["x"], f["y"] - ar["y"]) < M.ARENA_R_M + 2:
            bad["site"] += 1
        if sum(at(W[l], f["x"], f["y"]) for l in F["layers"]) < F["weight"] - 1e-6:
            bad["layer"] += 1
    if bad["trail"]:
        miss.append("%d plants stand on the trail" % bad["trail"])
    if bad["site"]:
        miss.append("%d plants stand in a fight" % bad["site"])
    if bad["layer"]:
        miss.append("%d plants stand off their ground" % bad["layer"])
    for k, (lo, hi) in COUNTS.items():
        if not lo <= counts.get(k, 0) <= hi:
            miss.append("%d %ss, want %d-%d" % (counts.get(k, 0), k.lower(), lo, hi))
    P["counts"] = counts
    return miss + check_night(P)


def check_night(P):
    """The night's rules (THE NIGHT, at the top), each held on the plan's
    own rows: every fire NIGHT's own; on its ground, out of the sea, the
    walkway, every fight and every plant's foot; the pier's two; each
    clearing's pair at the souq's arc and its fight lit; no gap on the way
    longer than street_step_m x (1 + step_jitter); the temple's gate pair
    and its court, as many as light its fight and no more."""
    miss = []
    N = SOUQ.NIGHT
    h, gp, props, fires = P["h"], P["ground"], P["props"], P["fires"]
    T = props["temple"]
    W, s_ = P["way"], P["way_s"]
    path = [tuple(p) for p in W]
    pr, ar = P["pier"], gp["arena"]
    rig = SOUQ._world_rig()
    mu, mb = SOUQ.moon_ue(rig), SOUQ.moon_blender()
    plants = [(f, foot_r(f, props)) for f in P["foliage"]]
    PL = np.array([(f["x"], f["y"], r) for f, r in plants]).reshape(-1, 3)
    # every fire NIGHT's own: its kind's mesh, height, foot, intensity, pool,
    # 1800 K, shadow and smoke, and its pool back from its UE candela and its
    # Blender watts (the souq's check 17)
    for f in fires:
        if f["kind"] not in SOUQ.FIRE_KINDS:
            miss.append("a fire of kind %s, not one of the night's %s" % (f["kind"], SOUQ.FIRE_KINDS))
            continue
        own = SOUQ._fire(f["kind"], 0.0, 0.0, 0.0, 0.0, rig)
        for key in ("mesh", "h", "half", "I", "pool", "temp", "shadow", "smoke"):
            same = abs(f[key] - own[key]) <= 1e-9 * max(1.0, abs(own[key])) if isinstance(own[key], float) else f[key] == own[key]
            if not same:
                miss.append("a %s's %s is %s, the night's is %s" % (f["kind"], key, f[key], own[key]))
        want = N[f["kind"]].get("pool_m") or SOUQ.pool_of(SOUQ.intensity(f["kind"]), f["h"])
        for what, I in (("UE candela", f["cd"] / mu), ("Blender watts", f["watts"] / (4.0 * math.pi * mb))):
            got = SOUQ.pool_of(I, f["h"])
            if abs(got / want - 1.0) > 0.01:
                miss.append("a %s's %s make a %.1f m pool, not %.1f m" % (f["kind"], what, got, want))
    # on what it stands on, out of the sea and the walkway, clear of every
    # fight, plant, rock, the pier and the boat; the way's fires on its verge
    ex = next(a for a in P["actors"] if a["kind"] == "Exit")
    bt = P["boat"]
    for f in fires:
        hm = f["half"] / 100.0
        what = "the %s %s" % (f["where"], f["kind"])
        if f["on"] == "deck":
            along, across = pier_frame(pr, f["x"], f["y"])
            if abs(f["z"] - pr["deck"]) > FIRE_ON_GROUND_M or not hm <= along <= pr["length"] - hm \
                    or abs(across) > props["pier"]["width"] / 2.0 - hm:
                miss.append("%s is not on the pier's deck (%.1f m along, %.1f across, %.2f m up)" % (what, along, across, f["z"]))
            if along < pier_frame(pr, ex["x"], ex["y"])[0] + hm:
                miss.append("%s stands in the way home, not past it" % what)
        else:
            g = at(h, f["x"], f["y"])
            if g <= M.LAND_MIN_M:
                miss.append("%s stands in the sea (the ground %.1f m)" % (what, g))
            if abs(f["z"] - g) > FIRE_ON_GROUND_M:
                miss.append("%s stands %.0f cm off the ground" % (what, (f["z"] - g) * 100.0))
            fit = misfit(h, f["x"], f["y"], g, hm)
            if fit > M.TRAIL_GRADE * hm:
                miss.append("%s stands on ground steeper than the trail: %.0f cm off it at its rim" % (what, fit * 100.0))
            along, across = pier_frame(pr, f["x"], f["y"])
            if -hm < along < pr["length"] + hm and abs(across) < props["pier"]["width"] / 2.0 + hm:
                miss.append("%s stands on the pier" % what)
            if math.hypot(f["x"] - ar["x"], f["y"] - ar["y"]) < T["clear_r"] + hm:
                miss.append("%s stands on the temple's court, the %.0f m it keeps clear" % (what, T["clear_r"]))
        d, _ = way_near(W, s_, f["x"], f["y"])
        if f["on"] == "ground" and d < M.TRAIL_BED_M + hm:
            miss.append("%s stands in the walkway, %.1f m off the trail's middle" % (what, d))
        if f["where"] in ("pier", "way", "clearing") and f["on"] == "ground" and d > M.TRAIL_BED_M + M.TRAIL_SHOULDER_M:
            miss.append("%s stands %.1f m off the way, past its verge" % (what, d))
        into = (PL[:, 2] + hm) - np.hypot(PL[:, 0] - f["x"], PL[:, 1] - f["y"]) if len(PL) else np.zeros(0)
        if len(into) and into.max() > 0.0:
            k = int(np.argmax(into))
            miss.append("%s stands in a %s (%s), %.1f m into its foot" % (what, plants[k][0]["kind"].lower(), plants[k][0]["mesh"],
                                                                        into[k]))
        for s in gp["sites"]:
            if math.hypot(f["x"] - s["x"], f["y"] - s["y"]) <= SITE_RADIUS_M + hm:
                miss.append("%s stands in a clearing's fight" % what)
        bu, bv = bt["u"]
        dx, dy = f["x"] - bt["x"], f["y"] - bt["y"]
        if abs(dx * bu + dy * bv) < BOAT_LEN_M / 2.0 + hm and abs(-dx * bv + dy * bu) < BOAT_BEAM_M / 2.0 + hm:
            miss.append("%s stands in the boat" % what)
    # the pier's two: its foot on the beach, its head on the deck
    foot = [f for f in fires if f["on"] == "ground" and f["kind"] == "brazier"
            and math.hypot(f["x"] - pr["x"], f["y"] - pr["y"]) <= M.TRAIL_BED_M + M.TRAIL_SHOULDER_M]
    head = [f for f in fires if f["on"] == "deck" and f["kind"] == "brazier"]
    if len(foot) != 1 or len(head) != 1:
        miss.append("the pier has %d brazier at its foot and %d at its head, want one each" % (len(foot), len(head)))
    # each clearing: its pyre pair at the souq's arc, the one before on one
    # verge and the one after on the other; its fight lit
    hp = N["pyre"]["half"] / 100.0
    for i, s in enumerate(gp["sites"]):
        i0 = int(np.argmin(np.hypot(W[:, 0] - s["x"], W[:, 1] - s["y"])))
        arc = SITE_RADIUS_M + hp + N["fight_clear_m"]
        pair = {}
        for f in fires:
            if f["kind"] != "pyre" or "s" not in f or abs(f["s"] - s_[i0]) > arc + 80 * 0.5:
                continue
            sign = 1 if f["s"] > s_[i0] else -1
            walked = (abs(f["s"] - s_[i0]) - arc) / 0.5
            x, y, _ = _verge(path, s_, f["s"], sign, hp)
            if walked < -1e-6 or abs(walked - round(walked)) > 1e-6 or f.get("side") != sign or \
                    math.hypot(x - f["x"], y - f["y"]) > 0.01:
                miss.append("clearing %d: a pyre %.2f m along the way from its fight, on verge %s -- not the souq's arc"
                            % (i + 1, f["s"] - s_[i0], f.get("side")))
            pair.setdefault(sign, []).append(f)
        if sorted(pair) != [-1, 1] or any(len(v) != 1 for v in pair.values()):
            miss.append("clearing %d has %s of its pyre pair, want one either side of its fight"
                        % (i + 1, {k: len(v) for k, v in sorted(pair.items())} or "none"))
        e = moons(fires, s["x"], s["y"])
        if e < 1.0:
            miss.append("clearing %d is fought by moonlight alone (%.2f of the moon)" % (i + 1, e))
    # the way, from the pier's foot to the court: no gap longer than a step
    # and its jitter, and none at all where the way runs
    ax, ay = ar["x"], ar["y"]
    s_court = next(s_[k] for k in range(len(W)) if math.hypot(W[k, 0] - ax, W[k, 1] - ay) <= T["court_r"])
    on_way = sorted(sa for d, sa in (way_near(W, s_, f["x"], f["y"]) for f in fires if f["on"] == "ground")
                    if d <= M.TRAIL_BED_M + M.TRAIL_SHOULDER_M and sa <= s_court)
    most = N["street_step_m"] * (1.0 + N["step_jitter"])
    stops = [0.0] + on_way + [s_court]
    for a, b in zip(stops[:-1], stops[1:]):
        if b - a > most + 1e-6:
            miss.append("the way has a %.1f m gap between lights at %.0f m along it, want %.1f or less" % (b - a, a, most))
    # the temple: a pyre either side of its gate, door_in_m inside it; its
    # court's ring just off the paving, as many as light its fight with the
    # gate's two and no more, none on the way in
    gb = math.radians(next(a for a in P["actors"] if a.get("mesh") == "SM_Island_Temple")["gate_bearing"])
    r_in, off = T["gate_r"] - N["door_in_m"], T["gate_w"] / 2.0 + hp + N["door_off_m"]
    gate = [f for f in fires if f["kind"] == "pyre" and any(
        math.hypot(f["x"] - (ax + math.cos(gb) * r_in - math.sin(gb) * off * sg),
                   f["y"] - (ay + math.sin(gb) * r_in + math.cos(gb) * off * sg)) <= 0.01 for sg in (-1, 1))]
    if len(gate) != 2:
        miss.append("the temple's gate has %d of its two pyres" % len(gate))
    rc = T["court_r"] + hp + N["site_margin_cm"] / 100.0
    court = [f for f in fires if f["kind"] == "pyre" and abs(math.hypot(f["x"] - ax, f["y"] - ay) - rc) <= 0.01]
    n = len(court)
    for f in court:
        a = (math.degrees(math.atan2(f["y"] - ay, f["x"] - ax) - gb)) % 360.0
        k = a / (360.0 / max(n, 1)) - 0.5
        if abs(k - round(k)) > 1e-3:
            miss.append("a court pyre stands %.0f degrees round from the gate, not evenly round the court" % a)
    e = moons(fires, ax, ay)
    if e < 1.0:
        miss.append("the temple is fought by moonlight alone (%.2f of the moon)" % e)
    elif n and moons(gate + _court_ring(P, n - 1), ax, ay) >= 1.0:
        miss.append("the temple's court has %d pyres where %d light its fight" % (n, n - 1))
    return miss


def _verge(path, s_, s, side, hm):
    """night()'s kerb, for check(): where a fire hm across stands at arc s
    on one verge, and the way's bearing there."""
    x, y, tx, ty = SOUQ._at(path, s_, s)
    across = side * (M.TRAIL_BED_M + hm + SOUQ.NIGHT["off_street_cm"] / 100.0)
    return x - ty * across, y + tx * across, math.degrees(math.atan2(ty, tx))


def _court_ring(P, n):
    """n pyres evenly round the temple's court, half a step off its gate."""
    N, T, ar = SOUQ.NIGHT, P["props"]["temple"], P["ground"]["arena"]
    gb = math.radians(next(a for a in P["actors"] if a.get("mesh") == "SM_Island_Temple")["gate_bearing"])
    rc = T["court_r"] + N["pyre"]["half"] / 100.0 + N["site_margin_cm"] / 100.0
    rig = SOUQ._world_rig()
    out = []
    for k in range(n):
        a = gb + math.radians((k + 0.5) * 360.0 / n)
        x, y = ar["x"] + math.cos(a) * rc, ar["y"] + math.sin(a) * rc
        out.append(SOUQ._fire("pyre", x, y, at(P["h"], x, y), math.degrees(a), rig, where="court", on="ground"))
    return out


def describe_night(P):
    """The night in a line: its fires by where they stand, and the way's gaps."""
    F = P["fires"]
    W, s_ = P["way"], P["way_s"]
    on_way = sorted(way_near(W, s_, f["x"], f["y"])[1] for f in F if f["where"] in ("pier", "way", "clearing")
                    and f["on"] == "ground")
    gaps = np.diff(on_way)
    n = {w: sum(1 for f in F if f["where"] == w) for w in ("pier", "way", "clearing", "gate", "court")}
    return ("%d fires -- %d braziers at the pier, %d on the way, %d pyres at the clearings, %d at the temple's gate, %d round "
            "its court; a light every %.1f-%.1f m (mean %.1f) along %.0f m of the way; each %.0f cd (brazier) / %.0f cd (pyre), "
            "drawn to %.0f / %.0f m" % (
                len(F), n["pier"], n["way"], n["clearing"], n["gate"], n["court"], gaps.min(), gaps.max(), gaps.mean(),
                s_[-1], SOUQ.candela(SOUQ.intensity("brazier"), SOUQ._world_rig()),
                SOUQ.candela(SOUQ.intensity("pyre"), SOUQ._world_rig()),
                SOUQ.draw_distance_cm(SOUQ.NIGHT["brazier"]["pool_m"]) / 100.0,
                SOUQ.draw_distance_cm(SOUQ.pool_of(SOUQ.intensity("pyre"), SOUQ.NIGHT["pyre"]["h"])) / 100.0))


def draw(P, path=MAP):
    """The island map with the level on it: plants, directors, the pier,
    the boat, the temple and the night's fires."""
    from PIL import Image, ImageDraw
    base = Image.open(os.path.join(PROJECT, "Docs", "monkey-island-map.png")).convert("RGB")
    D = base.size[0]
    step = (M.N - 1) // D

    def px(x, y):
        r, c = M.to_index(x, y)
        return c / step, r / step
    g = ImageDraw.Draw(base)
    col = dict(Palm=(150, 200, 90), Tree=(40, 110, 40), Rock=(170, 170, 170))
    for f in P["foliage"]:
        x, y = px(f["x"], f["y"])
        g.point((x, y), fill=col[f["kind"]])
    for a in P["actors"]:
        x, y = px(a["x"], a["y"])
        if a["kind"] == "WaveDirector":
            g.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(255, 255, 255))
        elif a["kind"] in ("PlayerStart", "Exit"):
            g.rectangle([x - 3, y - 3, x + 3, y + 3], fill=(255, 120, 255) if a["kind"] == "PlayerStart" else (255, 230, 80))
        elif a.get("mesh") == "SM_Island_Boat":
            g.ellipse([x - 5, y - 3, x + 5, y + 3], outline=(240, 220, 160), width=2)
    for f in P["fires"]:
        x, y = px(f["x"], f["y"])
        r = 2 if f["kind"] == "brazier" else 3
        g.ellipse([x - r, y - r, x + r, y + r], fill=(255, 140, 30))
    c = P["counts"]
    g.text((12, 30), "L_MonkeyIsland: %d palms, %d jungle trees, %d rocks; white: the directors; yellow: the way home; "
           "orange: the night's %d fires" % (c.get("Palm", 0), c.get("Tree", 0), c.get("Rock", 0), len(P["fires"])),
           fill=(255, 255, 255))
    base.save(path)
    print("drew %s" % path)


# ======================================================================= the editor

def build(P):
    """Inside the editor. Read-reviewed, never run."""
    import unreal
    ELL = unreal.EditorLevelLibrary
    EAL = unreal.EditorAssetLibrary
    AT = unreal.AssetToolsHelpers.get_asset_tools()
    MEL = unreal.MaterialEditingLibrary

    def import_tasks(files, dest, skeletal=False, skeleton=None, anim=False):
        tasks = []
        for f in files:
            t = unreal.AssetImportTask()
            t.filename = f
            t.destination_path = dest
            t.automated, t.save, t.replace_existing = True, True, True
            ui = unreal.FbxImportUI()
            ui.import_mesh = not anim
            ui.import_animations = anim
            ui.import_materials = not anim
            ui.import_textures = False
            ui.import_as_skeletal = skeletal or anim
            ui.mesh_type_to_import = (unreal.FBXImportType.FBXIT_ANIMATION if anim else
                                      unreal.FBXImportType.FBXIT_SKELETAL_MESH if skeletal else unreal.FBXImportType.FBXIT_STATIC_MESH)
            if skeleton is not None:
                ui.skeleton = skeleton
            if not skeletal and not anim:
                ui.static_mesh_import_data.set_editor_property("build_nanite", True)
            t.options = ui
            tasks.append(t)
        AT.import_asset_tasks(tasks)

    # the data: the island's two tables, on their row structs
    for name, struct, ext in (("DT_IslandFighters", unreal.FighterDef, "csv"), ("DT_MonkeyIsland", unreal.StageDef, "json")):
        t = unreal.AssetImportTask()
        t.filename = os.path.join(DATA, "%s.%s" % (name, ext))
        t.destination_path, t.destination_name = "/Game/Data", name
        t.automated, t.save, t.replace_existing = True, True, True
        fac = unreal.CSVImportFactory()
        fac.automated_import_settings.import_row_struct = struct
        t.factory = fac
        AT.import_asset_tasks([t])
    # the props, the creatures and their clips
    models = os.path.join(PROJECT, "Content", "Models")
    import_tasks([os.path.join(models, "Island", f) for f in sorted(os.listdir(os.path.join(models, "Island"))) if f.endswith(".fbx")],
                 "/Game/Models/Island")
    for c in ("Monkey", "Gorilla"):
        import_tasks([os.path.join(models, c + ".fbx")], "/Game/Models", skeletal=True)
        mesh = unreal.load_asset("/Game/Models/%s" % c)
        skel = mesh.get_editor_property("skeleton") if mesh else None
        import_tasks([os.path.join(ANIM, f) for f in sorted(os.listdir(ANIM)) if f.startswith("A_%s_" % c) and f.endswith(".fbx")],
                     "/Game/Animation/Island", anim=True, skeleton=skel)
    # the night's two fire meshes, the souq's own (SM_Souq_Brazier, _Cresset),
    # imported as the souq and the world import them: build_souq's import ends
    # with Tools/look/surfaces.build() -- every texture set right and M_Surface
    # on every slot under Content, this island's included -- so it is not run
    # a second time here
    fire_mesh = SOUQ.import_meshes(sorted({f["mesh"] for f in P["fires"]}))

    # the level, a partitioned world: the night is held to the souq's light
    # budget per what is streamed in round a man (THE NIGHT, WHAT IT COSTS),
    # and only a partitioned world streams -- a plain level would load all
    # 86 fires and their 86 smoke columns at once. As remembered, not run:
    # UE 5.1+'s NewLevel(AssetPath, bIsPartitionedWorld).
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    les.new_level(LEVEL, is_partitioned_world=True)
    world = ELL.get_editor_world()
    settings = world.get_world_settings()
    gm = unreal.load_class(None, "/Script/SaudFighter.SaudGameMode")
    if gm:
        settings.set_editor_property("default_game_mode", gm)

    def spawn(cls, label, xyz, yaw=0.0, folder="Island"):
        a = ELL.spawn_actor_from_class(cls, unreal.Vector(*xyz), unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
        a.set_actor_label(label)
        a.set_folder_path("SAUD/%s" % folder)
        return a

    def pin(a):
        """Loaded wherever he is, never streamed out: build_world.build()'s
        own rule for the game's actors (its directors, start, gates and
        exits), here theirs; and the sea's, the moon's, the sky's, the fog's
        and the exposure's, which stand at the island's middle, 1.6 km from
        the pier he lands on."""
        try:
            a.set_editor_property("is_spatially_loaded", False)
        except Exception:
            pass
        return a

    # the ground: the landscape from its heightmap, painted by its layers
    gp = P["ground"]
    ls = gp["landscape"]
    mat = _landscape_material(unreal, MEL, AT, EAL)
    made = False
    try:
        sub = unreal.get_editor_subsystem(unreal.LandscapeEditorSubsystem)
        made = bool(sub.import_heightmap(os.path.join(LAND, "H_MonkeyIsland.png"), unreal.Vector(*ls["location_cm"]),
                                         unreal.Vector(*ls["scale"]), mat))
    except Exception as e:                            # the call this file is least sure of
        unreal.log_warning("landscape import by Python failed (%s)" % e)
    if not made:
        unreal.log_warning(
            "Import the landscape by hand: Landscape mode > Manage > Import from File, heightmap %s, "
            "location %s cm, scale %s, 63 x 63 components of 64 quads (4033 square), material %s, "
            "and the layers %s from W_MonkeyIsland_<Layer>.png in the same folder."
            % (os.path.join(LAND, "H_MonkeyIsland.png"), ls["location_cm"], ls["scale"],
               "/Game/Materials/Island/M_MonkeyIsland_Ground", ", ".join(M.LAYERS)))
    # the sea
    sea = pin(spawn(unreal.StaticMeshActor, "Sea", (0.0, 0.0, 0.0), folder="Island/Sea"))
    sea.get_component_by_class(unreal.StaticMeshComponent).set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Plane"))
    sea.set_actor_scale3d(unreal.Vector(4600.0, 4600.0, 1.0))
    # the props, the plants
    for a in P["actors"]:
        if a["kind"] == "Prop":
            act = spawn(unreal.StaticMeshActor, a["name"], ue(a["x"], a["y"], a["z"]), ue_yaw(a["bearing"]), folder="Island/Props")
            act.get_component_by_class(unreal.StaticMeshComponent).set_static_mesh(unreal.load_asset("/Game/Models/Island/%s" % a["mesh"]))
    by_mesh = {}
    for f in P["foliage"]:
        by_mesh.setdefault(f["mesh"], []).append(f)
    for mesh, fs in by_mesh.items():
        holder = spawn(unreal.Actor, "Foliage_%s" % mesh, (0.0, 0.0, 0.0), folder="Island/Foliage")
        comp = unreal.InstancedStaticMeshComponent(holder, "Instances")
        holder.set_editor_property("root_component", comp)
        comp.set_static_mesh(unreal.load_asset("/Game/Models/Island/%s" % mesh))
        comp.set_editor_property("instance_end_cull_distance", 60000)
        for f in fs:
            comp.add_instance(unreal.Transform(unreal.Vector(*ue(f["x"], f["y"], f["z"])),
                                               unreal.Rotator(roll=0.0, pitch=0.0, yaw=ue_yaw(f["yaw"])),
                                               unreal.Vector(f["scale"], f["scale"], f["scale"])))
    # the directors, the start, the way home
    tabs = {n: unreal.load_asset("/Game/Data/%s" % n) for n in ("DT_MonkeyIsland", "DT_IslandFighters", "DT_Attacks")}
    for a in P["actors"]:
        if a["kind"] == "WaveDirector":
            act = pin(spawn(unreal.WaveDirector, a["name"], ue(a["x"], a["y"], a["z"]), folder="Island/Directors"))
            act.set_editor_property("stage_row", unreal.Name(a["row"]))
            act.set_editor_property("stage_table", tabs["DT_MonkeyIsland"])
            act.set_editor_property("fighter_table", tabs["DT_IslandFighters"])
            act.set_editor_property("attack_table", tabs["DT_Attacks"])
        elif a["kind"] == "PlayerStart":
            pin(spawn(unreal.PlayerStart, a["name"], ue(a["x"], a["y"], a["z"]), ue_yaw(a["bearing"]), folder="Island/Directors"))
        elif a["kind"] == "Exit":
            act = pin(spawn(unreal.AreaExit, a["name"], ue(a["x"], a["y"], a["z"]), folder="Island/Boat"))
            act.set_editor_property("destination_level", unreal.Name(a["DestinationLevel"]))
            act.set_editor_property("destination_stage", unreal.Name(a["DestinationStage"]))
            act.set_editor_property("arrive_at", unreal.AreaSide.RESUME)
    # the night: the world's moon, sky, fog and exposure (build_world's).
    # Until 2026-10-03 this rig silently differed from the world's it was
    # meant to be: the moon kept the engine's own source angle, the sky light
    # never captured the sky it lit, and the fog took the engine's defaults
    # for every number. Each is set now exactly as build_world.build() sets
    # its own, from WORLD_RIG and AIR: the moon's 0.55-degree disc (hard
    # shadows), a sky light that captures in real time, and the look's air --
    # its density, colour, start and fall-off -- volumetric, with the thin low
    # mist under it. One difference the island makes by being an island: the
    # fog stands at sea level and thins with height (fog_falloff), so the
    # hills and the temple's plateau, 60 m up, stand in less of it than the
    # beach; the world is flat and has none of that.
    import build_world as BW                          # noqa: E402
    r = BW.WORLD_RIG
    moon = pin(spawn(unreal.DirectionalLight, "Moon", (0.0, 0.0, 30000.0), folder="Lighting"))
    moon.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=r["pitch"], yaw=r["yaw"]), False)
    lc = moon.get_component_by_class(unreal.DirectionalLightComponent)
    lc.set_intensity(r["lux"])
    lc.set_light_color(unreal.LinearColor(*r["sun"]))
    lc.set_editor_property("light_source_angle", r["angle"])    # the moon's disc: hard shadows
    lc.set_editor_property("atmosphere_sun_light", True)
    sky = pin(spawn(unreal.SkyLight, "SkyLight", (0.0, 0.0, 25000.0), folder="Lighting"))
    slc = sky.get_component_by_class(unreal.SkyLightComponent)
    slc.set_intensity(r["sky"])
    slc.set_editor_property("real_time_capture", True)
    pin(spawn(unreal.SkyAtmosphere, "Sky", (0.0, 0.0, 0.0), folder="Lighting"))
    fog = pin(spawn(unreal.ExponentialHeightFog, "Fog", (0.0, 0.0, 0.0), folder="Lighting"))
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    fc.set_editor_property("fog_density", r["fogd"])
    fc.set_editor_property("fog_inscattering_luminance", unreal.LinearColor(*r["fog"]))
    fc.set_editor_property("start_distance", r["fog_start"])
    fc.set_editor_property("fog_height_falloff", r["fog_falloff"])
    air = BW.AIR
    fc.set_editor_property("enable_volumetric_fog", air["volumetric"])
    fc.set_editor_property("volumetric_fog_scattering_distribution", air["scattering"])
    fc.set_editor_property("volumetric_fog_albedo", unreal.Color(r=air["albedo"][0], g=air["albedo"][1], b=air["albedo"][2], a=255))
    fc.set_editor_property("volumetric_fog_extinction_scale", air["extinction"])
    fc.set_editor_property("volumetric_fog_start_distance", air["start_cm"])
    fc.set_editor_property("volumetric_fog_distance", air["view_m"] * 100.0)
    mist = fc.get_editor_property("second_fog_data")
    mist.set_editor_property("fog_density", air["mist"]["density"])
    mist.set_editor_property("fog_height_falloff", air["mist"]["falloff"])
    mist.set_editor_property("fog_height_offset", air["mist"]["offset"])
    fc.set_editor_property("second_fog_data", mist)
    ppv = pin(spawn(unreal.PostProcessVolume, "Exposure", (0.0, 0.0, 0.0), folder="Lighting"))
    ppv.set_editor_property("unbound", True)
    s = ppv.get_editor_property("settings")
    s.set_editor_property("override_auto_exposure_method", True)
    s.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
    s.set_editor_property("override_auto_exposure_apply_physical_camera_exposure", True)
    s.set_editor_property("auto_exposure_apply_physical_camera_exposure", False)
    s.set_editor_property("override_auto_exposure_bias", True)
    s.set_editor_property("auto_exposure_bias", BW.exposure_bias())
    ppv.set_editor_property("settings", s)
    # the night's fires, the rows check_night() proved: the souq's mesh at
    # each fire's foot, static as the souq stands its own; then its light,
    # its shadow tag and its smoke by build_souq.spawn_night -- the world's
    # own call, so every one is Movable, drawn and faded by its pool
    # (LIGHT_CULL) and tagged for the game's shadow budget exactly as the
    # world's are. spawn_night places by spawn(cls, label, x, y, z,
    # folder=...) in Unreal centimetres; this file's spawn takes the place
    # as one tuple, so it goes through an adapter, and the rows go to
    # Unreal's centimetres through ue() (the map's y turned over)
    def spawn_at(cls, label, x, y, z, yaw=0.0, folder="Island"):
        return spawn(cls, label, (x, y, z), yaw, folder)
    for i, f in enumerate(P["fires"]):
        act = spawn(unreal.StaticMeshActor, "%s_%02d" % (f["mesh"], i), ue(f["x"], f["y"], f["z"]), ue_yaw(f["yaw"]),
                    folder="Island/Night")
        act.get_component_by_class(unreal.StaticMeshComponent).set_static_mesh(fire_mesh[f["mesh"]])
        act.set_mobility(unreal.ComponentMobility.STATIC)
    rows = [dict(f, **dict(zip(("x", "y", "z"), ue(f["x"], f["y"], f["z"])))) for f in P["fires"]]
    lights, smoke = SOUQ.spawn_night(spawn_at, rows, [], rig=r, folder="Island/Night")
    les.save_current_level()
    unreal.log("Built %s: %d actors, %d plants, %d night lights, %d smoke volumes"
               % (LEVEL, len(P["actors"]), len(P["foliage"]), lights, smoke))


def _landscape_material(unreal, MEL, AT, EAL):
    """M_MonkeyIsland_Ground: the five layers blended by weight, each its
    BaseColor, Normal and Roughness at 4 m a tile. As remembered: the
    LandscapeLayerBlend's `layers` array of LayerBlendInput."""
    path = "/Game/Materials/Island/M_MonkeyIsland_Ground"
    if EAL.does_asset_exist(path):
        return unreal.load_asset(path)
    mat = AT.create_asset("M_MonkeyIsland_Ground", "/Game/Materials/Island", unreal.Material, unreal.MaterialFactoryNew())
    coords = MEL.create_material_expression(mat, unreal.MaterialExpressionLandscapeLayerCoords, -1400, 0)
    coords.set_editor_property("mapping_scale", 400.0)
    blends = {}
    for i, (role, prop) in enumerate((("BaseColor", unreal.MaterialProperty.MP_BASE_COLOR),
                                      ("Normal", unreal.MaterialProperty.MP_NORMAL),
                                      ("Roughness", unreal.MaterialProperty.MP_ROUGHNESS))):
        lb = MEL.create_material_expression(mat, unreal.MaterialExpressionLandscapeLayerBlend, -300, i * 400)
        layers = []
        for layer in M.LAYERS:
            inp = unreal.LayerBlendInput()
            inp.set_editor_property("layer_name", layer)
            inp.set_editor_property("blend_type", unreal.LandscapeLayerBlendType.LB_WEIGHT_BLEND)
            layers.append(inp)
        lb.set_editor_property("layers", layers)
        for j, layer in enumerate(M.LAYERS):
            ts = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -900, i * 400 + j * 70)
            ts.texture = unreal.load_asset("/Game/Textures/IslandGround/T_IslandGround_%s_%s" % (layer, role))
            ts.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR if role == "BaseColor" else
                                   unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL if role == "Normal" else
                                   unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
            MEL.connect_material_expressions(coords, "", ts, "UVs")
            MEL.connect_material_expressions(ts, "RGB" if role != "Roughness" else "R", lb, "Layer %s" % layer)
        MEL.connect_material_property(lb, "", prop)
        blends[role] = lb
    MEL.recompile_material(mat)
    EAL.save_asset(path)
    return mat


# ======================================================================= main

BITES = [
    ("a director on its site", "director_off_site", "from its site"),
    ("the temple's gate to the trail", "temple_backwards", "off the trail"),
    ("the pier out to sea", "pier_inland", "not over water"),
    ("the boat afloat", "boat_aground", "aground"),
    ("no plant on the trail", "tree_on_trail", "on the trail"),
    # the night
    ("each clearing's pyre pair", "no_clearing_pyres", "clearing 3 has"),
    ("no gap on the way", "trail_gap", "gap between lights"),
    ("no fire in the sea", "fire_in_sea", "in the sea"),
    ("every fire on its ground", "fire_floating", "off the ground"),
    ("no fire in the walkway", "fire_in_walkway", "in the walkway"),
    ("no fire in a rock", "fire_in_rock", "stands in a rock"),
    ("every fire NIGHT's own", "fire_spec_drift", "UE candela make"),
    ("... in its Blender watts", "watts_drift", "Blender watts make"),
    ("... one of NIGHT's kinds", "bad_kind", "a fire of kind torch"),
    ("... its height NIGHT's", "spec_h_drift", "pyre's h is 3.5"),
    ("... its shadow NIGHT's", "fire_unshadowed", "brazier's shadow is False"),
    ("the pier's two", "pier_head_dark", "the pier has"),
    ("the deck's brazier on the deck", "deck_off", "not on the pier's deck"),
    ("... past the way home", "deck_in_way_home", "in the way home"),
    ("no fire in the boat", "fire_in_boat", "stands in the boat"),
    ("no fire on steep ground", "fire_steep", "steeper than the trail"),
    ("no ground fire on the pier", "fire_on_pier", "stands on the pier"),
    ("no fire on the temple's court", "fire_on_court", "on the temple's court"),
    ("every way fire on its verge", "way_past_verge", "past its verge"),
    ("no fire in a clearing's fight", "fire_in_fight", "in a clearing's fight"),
    ("a clearing's pyre on its arc", "clearing_off_arc", "not the souq's arc"),
    ("... and on its verge", "clearing_wrong_verge", "not the souq's arc"),
    ("each clearing's fight lit", "clearing_dark", "clearing 3 is fought by moonlight"),
    ("the temple's gate pair", "no_gate_pyres", "gate has 0"),
    ("the temple's fight lit", "court_short", "temple is fought by moonlight"),
    ("the court evenly round", "court_uneven", "not evenly round"),
    ("no court pyre it can spare", "court_extra", "court has 6 pyres where 5"),
    # the creatures' clips (2026-10-04, the 360 locomotion)
    ("every clip on disk", "clip_missing", "has no clip Run_FwdLeft"),
    ("a turn as long as the game's", "turn_drift", "Turn_180 lasts"),
    ("MoveSpeed the run's pace", "speed_walk", "his runs were struck at"),
]


def main():
    args = sys.argv[1:]
    if "--bite" in args:
        SABOTAGE.clear()
        clean = check(plan())
        if clean:
            print("the unbroken plan fails its own checks, so no sabotage can be counted:\n  " + "\n  ".join(clean))
            sys.exit(1)
        print("  %-30s passes" % "unbroken")
        caught = 0
        for what, sab, want in BITES:
            SABOTAGE.clear()
            SABOTAGE.add(sab)
            f = check(plan())
            hit = [x for x in f if want in x]
            caught += bool(hit)
            print("  %-30s %s  %s" % (what, "caught" if hit else "MISSED", (hit or f or ["(passed)"])[0]))
        SABOTAGE.clear()
        print("%d of %d caught" % (caught, len(BITES)))
        sys.exit(0 if caught == len(BITES) else 1)
    P = plan()
    f = check(P)
    if f:
        print("FAILED:\n  " + "\n  ".join(f))
        sys.exit(1)
    c = P["counts"]
    print("checks pass: the directors on their sites and rows, the data (fighters, moves, clips, pace, meshes, styles), "
          "the temple's gate, the pier, the boat afloat, the start and the way home, %d palms, %d trees, %d rocks off the "
          "trail and the fights" % (c.get("Palm", 0), c.get("Tree", 0), c.get("Rock", 0)))
    print("  the night: %s" % describe_night(P))
    try:
        import unreal  # noqa: F401
        build(P)
    except ImportError:
        draw(P)
        print("Run inside the Unreal editor to build %s." % LEVEL)


if __name__ == "__main__":
    main()
