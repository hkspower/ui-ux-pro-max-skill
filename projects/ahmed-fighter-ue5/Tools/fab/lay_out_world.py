"""AHMED — Kuwait Fighter :: lay the world over a map from Fab
==============================================================================
Puts the whole of AL-HALQA into ONE map you have imported from Fab -- or from
anywhere -- as a ring of districts around the arena, instead of the nine
separate blockout levels build_levels.py makes. The map is yours: its ground,
its buildings, its sky and its lighting stay exactly as imported. This script
only adds what the game needs to run in it, at positions worked out from
DT_Stages.json and DT_World.json, the same tables the game runs on:

    one WaveDirector per district, at the district's origin
    every sealed route as an AbilityGate, off the way through
    every link in the world graph as a pair of AreaExits that open onto
        each other -- a doorway, not a level load
    a PlayerStart in the souq, where he lands
    a thin marker where each ambush fires, so the map shows the fights

A district is a round place, as wide across as its stage is long, with the
way through it running out from the middle on a spiral -- so "how far along
the stage" becomes "how far around the district" and the pacing the browser
build was tuned in survives. It was a strip 8.4 m deep until 2026-09-16,
because the game was a corridor; the C++ stopped believing that on the same
day (Source/AhmedFighter/Combat/AhmedArena.h) and the map had to stop with
it. The eight ring districts stand on a circle around the arena in
world-graph order -- souq at the top, then clockwise east -- and the arena is
the room at the hub. The circle is as small as the districts allow without
any two of them touching.
Survival (BILA NIHAYA) is not on the ring and is not placed; it is a mode,
not a place.

HOW TO USE IT

  1. In Fab (Epic account, the editor's Fab plugin), add the open-world map
     you have chosen to the project and open it in the editor. Flat or gently
     rolling ground is what a district wants; the script measures the
     ground across each one and warns where it is not.
  2. Import the data tables once (Content/Data ▸ Import, pick the row struct),
     as for build_levels.py.
  3. Set CENTRE below to where on the map the arena should be (a spot with a
     few hundred metres of open ground around it), and GROUND_Z only if the
     script cannot find the ground by tracing for it.
  4. Window ▸ Output Log, switch the prompt to Python:

        exec(open(r"<project>/Tools/fab/lay_out_world.py").read())

     It edits the map that is open. Actors it placed on an earlier run (they
     all sit in the outliner folder AHMED) are removed first, so it can be run
     again after a balance change.

OUTSIDE THE EDITOR it prints the plan -- every district, every actor, every
position -- draws Docs/fab-layout.png, checks that no two districts overlap,
that every door sits on its own rim facing the district it leads to, and that
the way through stays inside its district, and stops. That is how it was checked without an engine.
==============================================================================
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(PROJECT, "Content", "Data")
DOCS = os.path.join(PROJECT, "Docs")
DATA_DIR = "/Game/Data"
FOLDER = "AHMED"

# ------------------------------------------------------------- settings
# Where the arena stands on your map, in world centimetres. Everything else
# is placed around it.
CENTRE = (0.0, 0.0)
# Height of the ground. None: found by tracing down onto the map at each
# actor's spot, which is what you want; a number: used everywhere instead.
GROUND_Z = None
# How much clear ground to keep between neighbouring districts (cm).
GAP = 1600.0
# How uneven a district's ground may be before the script warns (cm).
GROUND_TOLERANCE = 60.0

# A district is a round place, not a strip.
#
# Until 2026-09-16 it was 8.4 m of depth and however long the stage ran,
# because the game was a corridor: X was "along", Y was "depth", and the
# camera never turned. The C++ stopped believing that on the same day
# (Source/AhmedFighter/Combat/AhmedArena.h), so the map had to stop too — a
# strip on the ground under a game that clamps to a circle is a map that
# disagrees with the thing it is a map of.
#
# The extent is the stage's own length, scaled and clamped: the same
# derivation the Unity port uses (District.LengthToExtent), so the two open
# worlds are the same size. Metres there, centimetres here.
LENGTH_TO_EXTENT = 1.7
MIN_EXTENT, MAX_EXTENT = 6000.0, 13000.0
# How far out the rim of a district is placed from its own middle for the
# doors, and how far in the gates sit.
EXIT_MARGIN = 200.0
SPAWN_RADIUS = 300.0
ACTOR_Z = 110.0                     # a capsule's half-height above the ground


# ------------------------------------------------------------------ data
def load():
    with open(os.path.join(DATA, "DT_Stages.json"), encoding="utf-8") as f:
        stages = json.load(f)
    with open(os.path.join(DATA, "DT_World.json"), encoding="utf-8") as f:
        world = json.load(f)
    return stages, world


def ring_order(world):
    """The ring districts in walking order, east from the start: the world
    graph's East links, followed until they come back round."""
    areas = {a["Index"]: a for a in world["Areas"]}
    order = [world["StartArea"]]
    while True:
        east = areas[order[-1]].get("East")
        if not east or east["To"] in order:
            break
        order.append(east["To"])
    assert areas[order[-1]]["East"]["To"] == order[0], "the world graph is not a closed ring"
    return order


def extent_of(stage):
    """How far a district reaches from its middle, in centimetres."""
    return max(MIN_EXTENT, min(MAX_EXTENT, float(stage["Length"]) * LENGTH_TO_EXTENT))


def disc(stage, ox, oy):
    """A district as its middle and its reach: (x, y, radius)."""
    return (ox, oy, extent_of(stage))


def overlaps(a, b, gap=0.0):
    return math.hypot(a[0] - b[0], a[1] - b[1]) < a[2] + b[2] + gap


def spiral(t, extent, phase):
    """Where a fraction along the old stage falls in an open district.

    The same curve as AhmedArena::SpiralPoint in the game and District.Spiral
    in the Unity port: an outward spiral of a turn and a third, so walking out
    from the middle meets the stage's content in the order the stage intended
    while leaving every one of them approachable from any direction. Three
    copies of one derivation is two too many, and the C++ one is the one the
    game plays; this is here so the map can be drawn without an engine.
    """
    angle = phase + t * 1.35 * 2.0 * math.pi
    radius = extent * (0.18 + 0.68 * t)
    return (math.cos(angle) * radius, math.sin(angle) * radius)


def hash01(n):
    """The layout's jitter. Same integer hash as District.Hash01, so a
    district is the same place in both open worlds."""
    x = n & 0xFFFFFFFF
    x ^= x >> 16; x = (x * 2246822519) & 0xFFFFFFFF
    x ^= x >> 13; x = (x * 3266489917) & 0xFFFFFFFF
    x ^= x >> 16
    return (x & 0xFFFFFF) / 16777215.0


def place_ring(stages, world):
    """Middles for the ring districts and the arena. Each sits on a circle at
    its slot's angle -- start at the top, clockwise -- and the circle grows
    until no district touches another or the arena."""
    order = ring_order(world)
    arena_idx = next(a["Index"] for a in world["Areas"] if a["Index"] not in order and a.get("West"))
    cx, cy = CENTRE
    origins = {arena_idx: (cx, cy)}         # the arena at the hub, on CENTRE
    n = len(order)
    radius = 0.0
    step = 200.0
    while True:
        radius += step
        trial = dict(origins)
        for slot, idx in enumerate(order):
            ang = math.pi / 2.0 - 2.0 * math.pi * slot / n      # top, then clockwise
            trial[idx] = (cx + radius * math.cos(ang), cy + radius * math.sin(ang))
        discs = {i: disc(stages[i], *o) for i, o in trial.items()}
        keys = list(discs)
        if not any(overlaps(discs[a], discs[b], GAP) for i, a in enumerate(keys) for b in keys[i + 1:]):
            return order, arena_idx, trial, radius


def plan(stages, world):
    order, arena_idx, origins, radius = place_ring(stages, world)
    areas = {a["Index"]: a for a in world["Areas"]}
    actors = []

    def add(kind, name, x, y, **props):
        actors.append(dict(kind=kind, name=name, x=x, y=y, props=props))

    placed = [arena_idx] + order
    for idx in placed:
        stage = stages[idx]
        ox, oy = origins[idx]
        L = max(1.0, float(stage["Length"]))
        E = extent_of(stage)
        # Each district turns its own spiral, so the nine do not all lay out
        # with their first fight in the same corner.
        phase = hash01(idx * 977 + 13) * 2.0 * math.pi

        add("WaveDirector", "Director_%s" % stage["Name"], ox, oy,
            StageRow=stage["Name"], Length=L, Extent=E)
        if idx == world["StartArea"]:
            # He lands in the middle, which is where the spiral begins and
            # where the hub is. On the strip he started at one end of it.
            add("PlayerStart", "PlayerStart", ox + SPAWN_RADIUS, oy)

        # "How far along the stage" becomes "how far around the district".
        for wi, w in enumerate(stage.get("Waves", [])):
            if w["TriggerDistance"] < 0:
                continue
            t = min(1.0, max(0.0, w["TriggerDistance"] / L))
            sx, sy = spiral(t, E, phase)
            add("WaveMarker", "%s_wave%d" % (stage["Name"], wi + 1), ox + sx, oy + sy,
                fighters=len(w["Fighters"]))
        for gi, g in enumerate(stage.get("Gates", [])):
            t = min(1.0, max(0.0, g["Distance"] / L))
            # A half turn off the way through: a sealed route is beside the
            # road and never standing on it, which is the rule every version
            # of this game has kept.
            sx, sy = spiral(t, E, phase + 0.5)
            add("Gate", "%s_gate%d_%s" % (stage["Name"], gi + 1, g["Type"]), ox + sx, oy + sy,
                GateType=g["Type"], RewardAbility=g["RewardAbility"],
                RewardExperience=g["RewardExperience"], GateId="%s_gate%d" % (stage["Name"], gi + 1))

        # A door is on the rim, facing the district it leads to, so walking
        # towards somewhere is walking towards its door.
        area = areas[idx]
        for side, key in (("West", "West"), ("East", "East"), ("Door", "Door")):
            link = area.get(key)
            if not link or link["To"] not in origins:
                continue
            dest = stages[link["To"]]
            tx, ty = origins[link["To"]]
            bearing = math.atan2(ty - oy, tx - ox)
            r = E - EXIT_MARGIN
            after = stages[link["AfterCleared"]]["Name"] if link["AfterCleared"] >= 0 else ""
            add("Exit", "Exit_%s_%s_to_%s" % (stage["Name"], side, dest["Name"]),
                ox + math.cos(bearing) * r, oy + math.sin(bearing) * r,
                Side=side, From=idx, To=link["To"], DestinationStage=dest["Name"],
                RequiredAbility=link["RequiredAbility"], AfterClearedStage=after,
                Bearing=math.degrees(bearing))

    # Pair every exit with the one it opens onto: the far side's link back.
    exits = [a for a in actors if a["kind"] == "Exit"]
    for e in exits:
        back = [o for o in exits if o["props"]["From"] == e["props"]["To"] and o["props"]["To"] == e["props"]["From"]]
        assert len(back) == 1, "link %s has no single way back" % e["name"]
        e["props"]["DestinationExit"] = back[0]["name"]
    return dict(order=order, arena=arena_idx, origins=origins, radius=radius, actors=actors)


def check(stages, P):
    discs = {i: disc(stages[i], *o) for i, o in P["origins"].items()}
    keys = list(discs)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            assert not overlaps(discs[a], discs[b]), "districts %s and %s overlap" % (a, b)

    for a in P["actors"]:
        # Every actor stands inside some district, none out on the map alone.
        assert any(math.hypot(a["x"] - d[0], a["y"] - d[1]) <= d[2] + 1.0
                   for d in discs.values()), a["name"]

    # A door is on its own district's rim and points at the one it leads to:
    # walking towards somewhere has to be walking towards its door.
    for e in [a for a in P["actors"] if a["kind"] == "Exit"]:
        d = discs[e["props"]["From"]]
        out = math.hypot(e["x"] - d[0], e["y"] - d[1])
        assert abs(out - (d[2] - EXIT_MARGIN)) < 1.0, "%s is not on the rim" % e["name"]
        far = discs[e["props"]["To"]]
        towards = math.atan2(far[1] - d[1], far[0] - d[0])
        here = math.atan2(e["y"] - d[1], e["x"] - d[0])
        off = abs(math.degrees(towards - here))
        assert off < 1.0 or abs(off - 360.0) < 1.0, "%s faces the wrong way" % e["name"]

    # The way through a district stays inside it, and clear of the middle
    # where the hub is and the rim where the doors are.
    for idx, d in discs.items():
        E = d[2]
        phase = hash01(idx * 977 + 13) * 2.0 * math.pi
        for k in range(0, 101):
            r = math.hypot(*spiral(k / 100.0, E, phase))
            assert 0.17 * E < r < 0.87 * E, "the way through %d leaves the district" % idx

    exits = [a for a in P["actors"] if a["kind"] == "Exit"]
    names = {a["name"] for a in exits}
    for e in exits:
        assert e["props"]["DestinationExit"] in names
    return discs


def describe(stages, P, discs):
    print("Ring of %d districts round the arena, radius %.0f m; %d actors\n"
          % (len(P["order"]), P["radius"] / 100.0, len(P["actors"])))
    print("  district            middle                across   the way through")
    for idx in [P["arena"]] + P["order"]:
        s = stages[idx]; ox, oy = P["origins"][idx]; d = discs[idx]
        phase = hash01(idx * 977 + 13) * 2.0 * math.pi
        walk = sum(math.dist(spiral(k / 100.0, d[2], phase), spiral((k + 1) / 100.0, d[2], phase))
                   for k in range(100))
        print("  %-18s (%7.0f, %7.0f) %8.0f m %10.0f m"
              % (s["Name"], ox, oy, d[2] * 2.0 / 100.0, walk / 100.0))
    print()
    for a in P["actors"]:
        extra = ", ".join("%s=%s" % (k, v) for k, v in a["props"].items()
                          if k in ("StageRow", "GateType", "RewardAbility", "RequiredAbility", "AfterClearedStage", "DestinationExit", "fighters"))
        print("   %-12s %-34s x=%8.0f y=%8.0f  %s" % (a["kind"], a["name"], a["x"], a["y"], extra))


def draw(stages, P, discs, path):
    """A top-down picture of the layout, to check it by eye."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("(PIL not available; no picture)"); return
    xs = [v for d in discs.values() for v in (d[0] - d[2], d[0] + d[2])]
    ys = [v for d in discs.values() for v in (d[1] - d[2], d[1] + d[2])]
    pad = 3000.0
    x0, x1, y0, y1 = min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad
    W = 1400; scale = W / (x1 - x0); H = int((y1 - y0) * scale)
    im = Image.new("RGB", (W, H), (24, 22, 20)); d = ImageDraw.Draw(im)
    def to(x, y): return ((x - x0) * scale, H - (y - y0) * scale)     # +Y up on the page
    cx, cy = CENTRE
    d.ellipse([to(cx - P["radius"], cy + P["radius"]), to(cx + P["radius"], cy - P["radius"])],
              outline=(70, 60, 50))

    for idx, disc_ in discs.items():
        ox, oy, E = disc_
        col = (200, 60, 50) if idx == P["arena"] else (214, 178, 96)
        d.ellipse([to(ox - E, oy + E), to(ox + E, oy - E)], outline=col)
        # The way through: the spiral the sites are placed along.
        phase = hash01(idx * 977 + 13) * 2.0 * math.pi
        pts = [to(ox + sx, oy + sy) for sx, sy in
               (spiral(k / 120.0, E, phase) for k in range(121))]
        d.line(pts, fill=(col[0] // 2, col[1] // 2, col[2] // 2), width=2)
        d.text(to(ox - E, oy + E + 1400), "%d %s" % (idx, stages[idx]["Name"]),
               fill=(235, 230, 220))

    for a in P["actors"]:
        x, y = to(a["x"], a["y"])
        c = {"WaveDirector": (255, 255, 255), "Gate": (90, 200, 255), "Exit": (120, 255, 120),
             "PlayerStart": (255, 120, 255), "WaveMarker": (250, 170, 90)}[a["kind"]]
        r = 5 if a["kind"] in ("Exit", "PlayerStart") else 4
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)
    for e in [a for a in P["actors"] if a["kind"] == "Exit"]:
        far = next(o for o in P["actors"] if o["name"] == e["props"]["DestinationExit"])
        d.line([to(e["x"], e["y"]), to(far["x"], far["y"])], fill=(60, 120, 60), width=1)
    d.text((16, 16), "AHMED on a Fab map: nine round districts, souq at the top, clockwise east; "
                     "arena at the hub. The line through each is the way through it \u2014 "
                     "white director, orange ambush, blue gate, green door, pink where he lands",
           fill=(200, 200, 200))
    os.makedirs(os.path.dirname(path), exist_ok=True); im.save(path); print("drew", path)


# ----------------------------------------------------------------- editor
def build(stages, P):
    import unreal  # noqa: E402  (only importable inside the editor)

    ELL = unreal.EditorLevelLibrary
    EAL = unreal.EditorAssetLibrary
    world = ELL.get_editor_world()
    cube = unreal.load_asset("/Engine/BasicShapes/Cube")

    tables = {}
    for t in ("DT_Stages", "DT_Fighters", "DT_Attacks"):
        path = "%s/%s" % (DATA_DIR, t)
        tables[t] = unreal.load_asset(path) if EAL.does_asset_exist(path) else None
        if not tables[t]:
            unreal.log_warning("%s is not imported yet; the directors will be placed without it." % t)

    # a previous run's actors go first, so this is repeatable
    for a in ELL.get_all_level_actors():
        if str(a.get_folder_path()).split("/")[0] == FOLDER:
            ELL.destroy_actor(a)

    def ground(x, y):
        if GROUND_Z is not None:
            return float(GROUND_Z)
        hit = unreal.SystemLibrary.line_trace_single(
            world, unreal.Vector(x, y, 100000.0), unreal.Vector(x, y, -100000.0),
            unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [], unreal.DrawDebugTrace.NONE, True)
        if hit and hit.to_tuple()[0]:
            return float(hit.to_tuple()[4].z)     # impact point
        unreal.log_warning("no ground under (%.0f, %.0f); using 0. Set GROUND_Z if the map has none to hit." % (x, y))
        return 0.0

    def spawn(cls, a, z):
        actor = ELL.spawn_actor_from_class(cls, unreal.Vector(a["x"], a["y"], z), unreal.Rotator(0, 0, 0))
        actor.set_actor_label(a["name"])
        actor.set_folder_path("%s/%s" % (FOLDER, a["kind"]))
        # World Partition streams actors out by distance; the directors and
        # doorways have to exist wherever the player is.
        try:
            actor.set_editor_property("is_spatially_loaded", False)
        except Exception:
            pass
        return actor

    # The ground under each district, sampled along the way through it and
    # out to the rim: the warning that tells you the map is not flat enough
    # where a district is.
    for idx, (ox, oy) in P["origins"].items():
        E = extent_of(stages[idx])
        phase = hash01(idx * 977 + 13) * 2.0 * math.pi
        zs = [ground(ox + sx, oy + sy)
              for sx, sy in (spiral(k / 8.0, E, phase) for k in range(9))]
        zs += [ground(ox + math.cos(a) * E * 0.9, oy + math.sin(a) * E * 0.9)
               for a in (k * math.pi / 4.0 for k in range(8))]
        if max(zs) - min(zs) > GROUND_TOLERANCE:
            unreal.log_warning("%s: ground varies %.0f cm across the district "
                               "(%.0f..%.0f). Flatten it or move CENTRE."
                               % (stages[idx]["Name"], max(zs) - min(zs), min(zs), max(zs)))

    made = {}
    for a in P["actors"]:
        k, p = a["kind"], a["props"]
        z = ground(a["x"], a["y"])
        if k == "WaveDirector":
            actor = spawn(unreal.WaveDirector, a, z)
            actor.set_editor_property("stage_row", unreal.Name(p["StageRow"]))
            if tables["DT_Stages"]:   actor.set_editor_property("stage_table", tables["DT_Stages"])
            if tables["DT_Fighters"]: actor.set_editor_property("fighter_table", tables["DT_Fighters"])
            if tables["DT_Attacks"]:  actor.set_editor_property("attack_table", tables["DT_Attacks"])
        elif k == "PlayerStart":
            spawn(unreal.PlayerStart, a, z + ACTOR_Z)
        elif k == "WaveMarker":
            actor = spawn(unreal.StaticMeshActor, a, z + 2.0)
            actor.get_component_by_class(unreal.StaticMeshComponent).set_static_mesh(cube)
            actor.set_actor_scale3d(unreal.Vector(1.2, 1.2, 0.04))
        elif k == "Gate":
            actor = spawn(unreal.AbilityGate, a, z + 150.0)
            actor.get_component_by_class(unreal.StaticMeshComponent).set_static_mesh(cube)
            actor.set_actor_scale3d(unreal.Vector(1.6, 0.6, 3.0))
            actor.set_editor_property("gate_type", getattr(unreal.GateType, p["GateType"].upper()))
            actor.set_editor_property("reward_ability", getattr(unreal.Ability, _enum_name(p["RewardAbility"])))
            actor.set_editor_property("reward_experience", int(p["RewardExperience"]))
            actor.set_editor_property("gate_id", unreal.Name(p["GateId"]))
        elif k == "Exit":
            actor = spawn(unreal.AreaExit, a, z + 300.0)
            actor.set_editor_property("side", getattr(unreal.AreaSide, p["Side"].upper()))
            actor.set_editor_property("destination_stage", unreal.Name(p["DestinationStage"]))
            actor.set_editor_property("required_ability", getattr(unreal.Ability, _enum_name(p["RequiredAbility"])))
            actor.set_editor_property("after_cleared_stage", unreal.Name(p["AfterClearedStage"]))
            made[a["name"]] = actor
    # the doorways open onto each other, now that both halves exist
    for a in P["actors"]:
        if a["kind"] == "Exit":
            made[a["name"]].set_editor_property("destination_exit", made[a["props"]["DestinationExit"]])

    if not ELL.save_current_level():
        unreal.log_error("Could not save the level")
    else:
        unreal.log("Laid out %d actors in folder %s; radius %.0f m" % (len(P["actors"]), FOLDER, P["radius"] / 100.0))


def _enum_name(s):
    out = ""
    for i, c in enumerate(s):
        if c.isupper() and i and not s[i - 1].isupper():
            out += "_"
        out += c.upper()
    return out


# ------------------------------------------------------------------- main
if __name__ == "__main__" or True:
    _stages, _world = load()
    _plan = plan(_stages, _world)
    _rects = check(_stages, _plan)
    try:
        import unreal  # noqa: F401
        _in_editor = True
    except ImportError:
        _in_editor = False
    if _in_editor:
        build(_stages, _plan)
    else:
        describe(_stages, _plan, _rects)
        draw(_stages, _plan, _rects, os.path.join(DOCS, "fab-layout.png"))
        print("\nRun this inside the Unreal editor, with the Fab map open, to lay it out.")
