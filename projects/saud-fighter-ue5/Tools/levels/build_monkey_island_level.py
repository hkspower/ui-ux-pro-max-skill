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
  in a clearing, on the temple's plateau or by the pier.

    python3 build_monkey_island_level.py           plan, check, draw
    python3 build_monkey_island_level.py --bite    each rule broken once
    (in the editor) py Tools/levels/build_monkey_island_level.py

UNVERIFIED -- the editor half has never run. Two parts are the least sure:
the landscape's import from the heightmap (UE 5.4 exposes no stable Python
call for it; build() tries LandscapeEditorSubsystem and, failing that,
prints the exact settings for Landscape mode's Import) and the landscape
material's layer-blend node properties. Both are as remembered.
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
NEED_CLIPS = ("Guard", "Walk_Fwd", "Walk_Back", "Walk_Left", "Walk_Right", "Block", "Hit_Light", "Hit_Heavy",
              "Down", "GetUp", "Death", "Victory")
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
    return P


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
    # the data: every fighter known, every move a row, every clip on disk, the pace the walks were struck at
    import importlib.util
    spec = importlib.util.spec_from_file_location("bpm", os.path.join(PROJECT, "Tools", "blender", "build_primate_motion.py"))
    bpm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bpm)
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
            if not os.path.exists(os.path.join(ANIM, "A_%s_%s.fbx" % (name, c))):
                miss.append("%s has no clip %s" % (name, c))
        if set(moves) != set(bpm.STRIKES.get(name, ())):
            miss.append("%s's moves %s are not the strikes his clips were struck for %s" % (name, moves, bpm.STRIKES.get(name)))
        if abs(float(r["MoveSpeed"]) - bpm.PACE.get(name, -1)) > 0.5:
            miss.append("%s moves at %s cm/s, his walks were struck at %s" % (name, r["MoveSpeed"], bpm.PACE.get(name)))
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
    return miss


def draw(P, path=MAP):
    """The island map with the level on it: plants, directors, the pier,
    the boat and the temple."""
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
    c = P["counts"]
    g.text((12, 30), "L_MonkeyIsland: %d palms, %d jungle trees, %d rocks; white: the directors; yellow: the way home"
           % (c.get("Palm", 0), c.get("Tree", 0), c.get("Rock", 0)), fill=(255, 255, 255))
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
    sys.path.insert(0, os.path.join(PROJECT, "Tools", "look"))
    import surfaces                                   # noqa: E402  (every texture set right, M_Surface on every slot)
    surfaces.build()

    # the level
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    les.new_level(LEVEL)
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
    sea = spawn(unreal.StaticMeshActor, "Sea", (0.0, 0.0, 0.0), folder="Island/Sea")
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
            act = spawn(unreal.WaveDirector, a["name"], ue(a["x"], a["y"], a["z"]), folder="Island/Directors")
            act.set_editor_property("stage_row", unreal.Name(a["row"]))
            act.set_editor_property("stage_table", tabs["DT_MonkeyIsland"])
            act.set_editor_property("fighter_table", tabs["DT_IslandFighters"])
            act.set_editor_property("attack_table", tabs["DT_Attacks"])
        elif a["kind"] == "PlayerStart":
            spawn(unreal.PlayerStart, a["name"], ue(a["x"], a["y"], a["z"]), ue_yaw(a["bearing"]), folder="Island/Directors")
        elif a["kind"] == "Exit":
            act = spawn(unreal.AreaExit, a["name"], ue(a["x"], a["y"], a["z"]), folder="Island/Boat")
            act.set_editor_property("destination_level", unreal.Name(a["DestinationLevel"]))
            act.set_editor_property("destination_stage", unreal.Name(a["DestinationStage"]))
            act.set_editor_property("arrive_at", unreal.AreaSide.RESUME)
    # the night: the world's moon, sky, fog and exposure (build_world's)
    import build_world as BW                          # noqa: E402
    r = BW.WORLD_RIG
    moon = spawn(unreal.DirectionalLight, "Moon", (0.0, 0.0, 30000.0), folder="Lighting")
    moon.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=r["pitch"], yaw=r["yaw"]), False)
    lc = moon.get_component_by_class(unreal.DirectionalLightComponent)
    lc.set_intensity(r["lux"])
    lc.set_light_color(unreal.LinearColor(*r["sun"]))
    lc.set_editor_property("atmosphere_sun_light", True)
    sky = spawn(unreal.SkyLight, "SkyLight", (0.0, 0.0, 25000.0), folder="Lighting")
    sky.get_component_by_class(unreal.SkyLightComponent).set_intensity(r["sky"])
    spawn(unreal.SkyAtmosphere, "Sky", (0.0, 0.0, 0.0), folder="Lighting")
    spawn(unreal.ExponentialHeightFog, "Fog", (0.0, 0.0, 0.0), folder="Lighting")
    ppv = spawn(unreal.PostProcessVolume, "Exposure", (0.0, 0.0, 0.0), folder="Lighting")
    ppv.set_editor_property("unbound", True)
    s = ppv.get_editor_property("settings")
    s.set_editor_property("override_auto_exposure_method", True)
    s.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
    s.set_editor_property("override_auto_exposure_apply_physical_camera_exposure", True)
    s.set_editor_property("auto_exposure_apply_physical_camera_exposure", False)
    s.set_editor_property("override_auto_exposure_bias", True)
    s.set_editor_property("auto_exposure_bias", BW.exposure_bias())
    ppv.set_editor_property("settings", s)
    les.save_current_level()
    unreal.log("Built %s: %d actors, %d plants" % (LEVEL, len(P["actors"]), len(P["foliage"])))


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
]


def main():
    args = sys.argv[1:]
    if "--bite" in args:
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
    try:
        import unreal  # noqa: F401
        build(P)
    except ImportError:
        draw(P)
        print("Run inside the Unreal editor to build %s." % LEVEL)


if __name__ == "__main__":
    main()
