"""AHMED — Kuwait Fighter :: lay the world over a map from Fab
==============================================================================
Puts the whole of AL-HALQA into ONE map you have imported from Fab -- or from
anywhere -- as a ring of districts around the arena, instead of the nine
separate blockout levels build_levels.py makes. The map is yours: its ground,
its buildings, its sky and its lighting stay exactly as imported. This script
only adds what the game needs to run in it, at positions worked out from
DT_Stages.json and DT_World.json, the same tables the game runs on:

    one WaveDirector per district, at the district's origin
    every sealed route as an AbilityGate, set back off the strip
    every link in the world graph as a pair of AreaExits that open onto
        each other -- a doorway, not a level load
    a PlayerStart in the souq, where he lands
    a thin marker where each ambush fires, so the map shows the fights

A district is a strip along world +X, as long as its stage and 8.4 m deep,
because the fight code measures along X and across Y. The eight ring
districts stand on a circle around the arena in world-graph order -- souq at
the top, then clockwise east -- and the arena is the room at the hub. The
circle is as small as the strips allow without any two of them touching.
Survival (BILA NIHAYA) is not on the ring and is not placed; it is a mode,
not a place.

HOW TO USE IT

  1. In Fab (Epic account, the editor's Fab plugin), add the open-world map
     you have chosen to the project and open it in the editor. Flat or gently
     rolling ground is what the strips want; the script measures the ground
     under every strip and warns where it is not.
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
position -- draws Docs/fab-layout.png, checks that no two strips overlap, and
stops. That is how it was checked without an engine.
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
# How much clear ground to keep between neighbouring strips (cm).
GAP = 1600.0
# How uneven a strip's ground may be before the script warns (cm).
GROUND_TOLERANCE = 60.0

# The playfield strip, from AhmedTypes.h. X runs along the district, Y is
# depth, the camera looks toward +Y, so +Y is the back.
DEPTH_MIN, DEPTH_MAX = -420.0, 420.0
GATE_Y = DEPTH_MAX + 360.0          # off the strip, never on the critical path
STRIP_BACK = DEPTH_MAX + 620.0      # the footprint a strip needs: gates and a wall's worth
STRIP_FRONT = DEPTH_MIN - 200.0
EXIT_MARGIN = 60.0
SPAWN_X = 300.0
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


def strip_rect(stage, ox, oy):
    """Axis-aligned footprint of a district whose origin is (ox, oy)."""
    return (ox - EXIT_MARGIN, oy + STRIP_FRONT, ox + stage["Length"] + EXIT_MARGIN, oy + STRIP_BACK)


def overlaps(a, b, gap=0.0):
    return not (a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1])


def place_ring(stages, world):
    """Origins for the ring districts and the arena. Each district's centre
    sits on a circle at its slot's angle -- start at the top, clockwise --
    and the circle grows until no strip touches another or the arena."""
    order = ring_order(world)
    arena_idx = next(a["Index"] for a in world["Areas"] if a["Index"] not in order and a.get("West"))
    arena = stages[arena_idx]
    cx, cy = CENTRE
    # the arena at the hub, centred on CENTRE
    origins = {arena_idx: (cx - arena["Length"] / 2.0, cy)}
    n = len(order)
    radius = 0.0
    step = 200.0
    while True:
        radius += step
        trial = dict(origins)
        for slot, idx in enumerate(order):
            ang = math.pi / 2.0 - 2.0 * math.pi * slot / n      # top, then clockwise
            mx, my = cx + radius * math.cos(ang), cy + radius * math.sin(ang)
            trial[idx] = (mx - stages[idx]["Length"] / 2.0, my)
        rects = {i: strip_rect(stages[i], *o) for i, o in trial.items()}
        keys = list(rects)
        if not any(overlaps(rects[a], rects[b], GAP) for i, a in enumerate(keys) for b in keys[i + 1:]):
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
        L = float(stage["Length"])
        add("WaveDirector", "Director_%s" % stage["Name"], ox, oy, StageRow=stage["Name"], Length=L)
        if idx == world["StartArea"]:
            add("PlayerStart", "PlayerStart", ox + SPAWN_X, oy)
        for wi, w in enumerate(stage.get("Waves", [])):
            if w["TriggerDistance"] < 0:
                continue
            add("WaveMarker", "%s_wave%d" % (stage["Name"], wi + 1), ox + w["TriggerDistance"], oy,
                fighters=len(w["Fighters"]))
        for gi, g in enumerate(stage.get("Gates", [])):
            add("Gate", "%s_gate%d_%s" % (stage["Name"], gi + 1, g["Type"]), ox + g["Distance"], oy + GATE_Y,
                GateType=g["Type"], RewardAbility=g["RewardAbility"],
                RewardExperience=g["RewardExperience"], GateId="%s_gate%d" % (stage["Name"], gi + 1))
        area = areas[idx]
        for side, key in (("West", "West"), ("East", "East"), ("Door", "Door")):
            link = area.get(key)
            if not link or link["To"] not in origins:
                continue
            dest = stages[link["To"]]
            x = {"West": EXIT_MARGIN, "East": L - EXIT_MARGIN}.get(side, float(link["Distance"]))
            after = stages[link["AfterCleared"]]["Name"] if link["AfterCleared"] >= 0 else ""
            add("Exit", "Exit_%s_%s_to_%s" % (stage["Name"], side, dest["Name"]), ox + x, oy,
                Side=side, From=idx, To=link["To"], DestinationStage=dest["Name"],
                RequiredAbility=link["RequiredAbility"], AfterClearedStage=after)

    # Pair every exit with the one it opens onto: the far side's link back.
    exits = [a for a in actors if a["kind"] == "Exit"]
    for e in exits:
        back = [o for o in exits if o["props"]["From"] == e["props"]["To"] and o["props"]["To"] == e["props"]["From"]]
        assert len(back) == 1, "link %s has no single way back" % e["name"]
        e["props"]["DestinationExit"] = back[0]["name"]
    return dict(order=order, arena=arena_idx, origins=origins, radius=radius, actors=actors)


def check(stages, P):
    rects = {i: strip_rect(stages[i], *o) for i, o in P["origins"].items()}
    keys = list(rects)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            assert not overlaps(rects[a], rects[b]), "strips %s and %s overlap" % (a, b)
    for a in P["actors"]:
        # every actor inside some strip's footprint, none out on the map alone
        assert any(r[0] <= a["x"] <= r[2] and r[1] <= a["y"] <= r[3] for r in rects.values()), a["name"]
    exits = [a for a in P["actors"] if a["kind"] == "Exit"]
    names = {a["name"] for a in exits}
    for e in exits:
        assert e["props"]["DestinationExit"] in names
    return rects


def describe(stages, P, rects):
    print("Ring of %d districts round the arena, radius %.0f m; %d actors\n" % (len(P["order"]), P["radius"] / 100.0, len(P["actors"])))
    for idx in [P["arena"]] + P["order"]:
        s = stages[idx]; ox, oy = P["origins"][idx]; r = rects[idx]
        print("  %-18s origin (%7.0f, %7.0f)  strip x %7.0f..%7.0f  y %7.0f..%7.0f" % (s["Name"], ox, oy, r[0], r[2], r[1], r[3]))
    print()
    for a in P["actors"]:
        extra = ", ".join("%s=%s" % (k, v) for k, v in a["props"].items()
                          if k in ("StageRow", "GateType", "RewardAbility", "RequiredAbility", "AfterClearedStage", "DestinationExit", "fighters"))
        print("   %-12s %-34s x=%8.0f y=%8.0f  %s" % (a["kind"], a["name"], a["x"], a["y"], extra))


def draw(stages, P, rects, path):
    """A top-down picture of the layout, to check it by eye."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("(PIL not available; no picture)"); return
    xs = [v for r in rects.values() for v in (r[0], r[2])]; ys = [v for r in rects.values() for v in (r[1], r[3])]
    pad = 2000.0
    x0, x1, y0, y1 = min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad
    W = 1400; scale = W / (x1 - x0); H = int((y1 - y0) * scale)
    im = Image.new("RGB", (W, H), (24, 22, 20)); d = ImageDraw.Draw(im)
    def to(x, y): return ((x - x0) * scale, H - (y - y0) * scale)     # +Y up on the page
    cx, cy = CENTRE
    d.ellipse([to(cx - P["radius"], cy + P["radius"]), to(cx + P["radius"], cy - P["radius"])], outline=(70, 60, 50))
    for idx, r in rects.items():
        s = stages[idx]; ox, oy = P["origins"][idx]
        col = (200, 60, 50) if idx == P["arena"] else (214, 178, 96)
        d.rectangle([to(r[0], r[3]), to(r[2], r[1])], outline=col)
        d.rectangle([to(ox, oy + DEPTH_MAX), to(ox + s["Length"], oy + DEPTH_MIN)], fill=col)
        d.text(to(ox, oy + STRIP_BACK + 900), "%d %s" % (idx, s["Name"]), fill=(235, 230, 220))
    for a in P["actors"]:
        x, y = to(a["x"], a["y"])
        c = {"WaveDirector": (255, 255, 255), "Gate": (90, 200, 255), "Exit": (120, 255, 120),
             "PlayerStart": (255, 120, 255), "WaveMarker": (40, 30, 25)}[a["kind"]]
        d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=c)
    for e in [a for a in P["actors"] if a["kind"] == "Exit"]:
        far = next(o for o in P["actors"] if o["name"] == e["props"]["DestinationExit"])
        d.line([to(e["x"], e["y"]), to(far["x"], far["y"])], fill=(60, 120, 60), width=1)
    d.text((16, 16), "AHMED on a Fab map: strips along +X, souq at the top, clockwise east; arena at the hub. "
                     "white director, blue gate, green exit (lines pair doorways), pink player start", fill=(200, 200, 200))
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

    # the ground under each strip, sampled along it: the warning that tells
    # you the map is not flat enough where a district is
    for idx, (ox, oy) in P["origins"].items():
        L = stages[idx]["Length"]
        zs = [ground(ox + L * t, oy + y) for t in (0.0, 0.25, 0.5, 0.75, 1.0) for y in (DEPTH_MIN, 0.0, DEPTH_MAX)]
        if max(zs) - min(zs) > GROUND_TOLERANCE:
            unreal.log_warning("%s: ground varies %.0f cm along the strip (%.0f..%.0f). Flatten it or move CENTRE."
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
            actor.set_actor_scale3d(unreal.Vector(0.06, (DEPTH_MAX - DEPTH_MIN) / 100.0, 0.04))
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
