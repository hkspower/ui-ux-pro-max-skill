"""SAUD — Kuwait Fighter :: build the stage maps
==============================================================================
Makes the nine levels (ten with survival) from Content/Data/DT_Stages.json and
DT_World.json, so the maps are generated from the same tables the game runs on
rather than placed by hand and left to drift. Every actor a level needs to be
playable is put down: the ground, the player start, the wave director, every
sealed route, every exit to a neighbouring area, and a lighting rig matched to
the browser build's per-stage rig.

Since 2026-09-19 this is a ROUND blockout, not a strip. Until then this file
put down 8.4 m of depth either side of a corridor along X, a back wall gates
sat into, and exits at the two ends -- because the game was a corridor and the
camera never turned. Both stopped being true on 2026-09-16
(Source/SaudFighter/Combat/SaudArena.h): a locked fight became a circle, and
Tools/fab/lay_out_world.py started laying the open-world map out as a ring of
round districts to match. This file did not follow it for three years of
in-game time and one real day: `WaveDirector::Contains()` and
`ApplyArenaBounds()` were still clamping a player to a circle of radius
Stage->Length -- an unscaled strip measurement -- while the open-world map
built its districts to DistrictExtent(Length), a bigger, differently-scaled
number, which meant even the ALREADY-SHIPPED open world was clamping players
tighter than the ground they were standing on. That is fixed alongside this
file, in the same commit: SaudArena::DistrictExtent is now the one place the
1.7x-clamped-to-60-130m derivation lives, `Contains()`/`ApplyArenaBounds()`
read it, and this script and Tools/fab/lay_out_world.py both duplicate it
rather than share it, for the same reason SaudArena::SpiralPoint already is
duplicated across languages: three runtimes, and none of them can include
another's source file.

A LEVEL HERE IS ONE DISTRICT, ALONE.

Tools/fab/lay_out_world.py works out a door's bearing from where its
destination district actually sits on the shared map -- it can, because every
district coexists in that one map. A level here never coexists with its
neighbours; there is no real position to point a bearing at. So this script
fixes them by role instead, the same three for every stage: West at 180
degrees (the way back the way he came), East at 0 (the way on), Door at 90
(the one link that is not a street -- see ../saud-fighter/CLAUDE.md). Every
level uses the same three, which is fine precisely because no two levels are
ever open at once to disagree with each other.

Everything else follows Tools/fab/lay_out_world.py's model directly: a
district is a disc of DistrictExtent(Length), "how far along the stage"
becomes "how far around the district" via SaudArena::SpiralPoint (Waves on
the spiral itself, Gates a half-turn off it, both duplicated from that file
verbatim), and a door sits on the rim at DistrictExtent(Length)-EXIT_MARGIN.
PlayerStart stands at the West door -- where he would have walked in from --
so ASaudGameMode::PlaceArrivingPlayer only has work to do for an East or
Door arrival, exactly the two doors PlayerStart is not already standing at.

It is a blockout. Geometry is engine cubes; the art pass that replaces them is
described in CLAUDE.md. The old strip had one flat wall, "something for the
light to fall on" rather than a boundary the code enforced -- nothing here
enforces a boundary either, ASaudCharacter::SetArenaCircle already does that,
so this round version has no wall at all rather than a ring of them standing
in for one, which was not asked for. What is NOT a blockout is the data:
distances, gates, exits and their requirements are exact, and regenerating
after a balance change keeps them exact.

RUN IT INSIDE THE EDITOR (it needs the editor's world to make maps):

    Edit ▸ Plugins: enable "Python Editor Script Plugin" and
                    "Editor Scripting Utilities" (both ship with the engine;
                    the .uproject already asks for them), restart.
    Window ▸ Output Log, switch the command line to Python, then:

        exec(open(r"<path to project>/Tools/levels/build_levels.py").read())

    or from a terminal on the Mac, with the editor closed:

        "/Users/Shared/Epic Games/UE_5.4/Engine/Binaries/Mac/UnrealEditor-Cmd" \
            SaudFighter.uproject -run=pythonscript \
            -script="Tools/levels/build_levels.py"

Existing maps of the same name are overwritten: this script owns them.

OUTSIDE THE EDITOR it prints the plan -- every level and every actor it would
place, with positions -- and checks it: every actor stands on the floor it was
given, every door sits on its own district's rim at its role's bearing, and
the way through (the spiral) stays clear of the middle and the rim, the same
three things Tools/fab/lay_out_world.py checks about its own layout. That is
how it was checked without an engine.
==============================================================================
"""

import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(PROJECT, "Content", "Data")
MAPS_DIR = "/Game/Maps"
DATA_DIR = "/Game/Data"

FLOOR_TOP_Z = 0.0

# The same derivation as SaudArena::DistrictExtent and
# Tools/fab/lay_out_world.py's extent_of() -- duplicated on purpose, see the
# docstring above.
LENGTH_TO_EXTENT = 1.7
MIN_EXTENT, MAX_EXTENT = 6000.0, 13000.0
# Matches SaudGameplay::ExitMargin. A door stands this far in from the rim
# DistrictExtent draws, so it is never standing exactly on the edge.
EXIT_MARGIN = 200.0
# Clearance the floor keeps past the furthest door, so nothing built here
# stands over empty ground.
FLOOR_MARGIN = 600.0
SPAWN_RADIUS = 300.0     # fallback for the one stage with no West door

# Fixed by role, not by geometry -- see "A LEVEL HERE IS ONE DISTRICT, ALONE"
# above. Degrees, standard math convention: 0 is +X, 90 is +Y.
BEARING = {"West": 180.0, "East": 0.0, "Door": 90.0}

# --------------------------------------------------------------- lighting
# One rig per theme, carried across from the browser build's THEME[x].rig.
# Rotation is the sun: pitch is elevation (negative = above the horizon), yaw
# is where it comes from. Colours are the key; the sky light fills.
RIGS = {
    "Souq":       dict(pitch=-24, yaw=-150, sun=(1.00, 0.85, 0.63), lux=9.0,  sky=1.6, fog=(0.94, 0.75, 0.51), fogd=0.020, expo=1.05),
    "Gym":        dict(pitch=-78, yaw=-100, sun=(0.91, 0.94, 1.00), lux=4.5,  sky=0.7, fog=(0.47, 0.59, 0.75), fogd=0.008, expo=0.98),
    "Fishmarket": dict(pitch=-40, yaw=-110, sun=(0.95, 0.97, 0.98), lux=5.0,  sky=2.4, fog=(0.78, 0.88, 0.92), fogd=0.024, expo=1.02),
    "Towers":     dict(pitch=-32, yaw=-140, sun=(0.72, 0.81, 1.00), lux=1.4,  sky=0.9, fog=(0.35, 0.55, 0.86), fogd=0.016, expo=0.94),
    "Marina":     dict(pitch=-35, yaw=-125, sun=(0.62, 0.50, 0.83), lux=1.1,  sky=0.8, fog=(0.63, 0.35, 0.86), fogd=0.018, expo=0.92),
    "Failaka":    dict(pitch=-12, yaw=40,   sun=(1.00, 0.72, 0.47), lux=8.0,  sky=1.4, fog=(1.00, 0.67, 0.47), fogd=0.028, expo=1.06),
    "Highway":    dict(pitch=-16, yaw=-145, sun=(1.00, 0.69, 0.44), lux=7.0,  sky=1.2, fog=(1.00, 0.63, 0.43), fogd=0.026, expo=1.00),
    "Desert":     dict(pitch=-55, yaw=-120, sun=(0.78, 0.83, 1.00), lux=0.9,  sky=0.6, fog=(0.47, 0.43, 0.71), fogd=0.014, expo=0.92),
    "Arena":      dict(pitch=-84, yaw=-95,  sun=(1.00, 1.00, 1.00), lux=12.0, sky=0.5, fog=(0.71, 0.42, 0.88), fogd=0.006, expo=1.05),
}

# ------------------------------------------------------------------ data
def load():
    with open(os.path.join(DATA, "DT_Stages.json"), encoding="utf-8") as f:
        stages = json.load(f)
    with open(os.path.join(DATA, "DT_World.json"), encoding="utf-8") as f:
        world = json.load(f)
    return stages, world


def level_name(stage):
    return "L_" + stage["Name"]


def extent_of(stage):
    """How far a district reaches from its middle, in centimetres. Must agree
    with SaudArena::DistrictExtent -- see the module docstring."""
    return max(MIN_EXTENT, min(MAX_EXTENT, float(stage["Length"]) * LENGTH_TO_EXTENT))


def spiral(t, extent, phase):
    """Where a fraction along the old stage falls in a round district. Copied
    verbatim from Tools/fab/lay_out_world.py, which copied it from
    SaudArena::SpiralPoint -- one derivation, in three places because none of
    them can include another's source file."""
    angle = phase + t * 1.35 * 2.0 * math.pi
    radius = extent * (0.18 + 0.68 * t)
    return (math.cos(angle) * radius, math.sin(angle) * radius)


def hash01(n):
    """The layout's jitter. Same integer hash as Tools/fab/lay_out_world.py's,
    so a given stage's phase agrees whether it is standing alone or merged
    into the open world."""
    x = n & 0xFFFFFFFF
    x ^= x >> 16; x = (x * 2246822519) & 0xFFFFFFFF
    x ^= x >> 13; x = (x * 3266489917) & 0xFFFFFFFF
    x ^= x >> 16
    return (x & 0xFFFFFF) / 16777215.0


def plan_level(stage, world, stages):
    """Everything one level needs, as plain data. The editor half of this file
    only walks the list; the plan is what gets read and checked."""
    L = max(1.0, float(stage["Length"]))
    E = extent_of(stage)
    idx = stage.get("Index", -1)
    phase = hash01(idx * 977 + 13) * 2.0 * math.pi
    rig = RIGS.get(stage["Theme"], RIGS["Souq"])
    actors = []

    def add(kind, name, x=0.0, y=0.0, z=0.0, **props):
        actors.append(dict(kind=kind, name=name, x=x, y=y, z=z, props=props))

    add("WaveDirector", "WaveDirector", x=0.0, y=0.0, z=FLOOR_TOP_Z, StageRow=stage["Name"])

    # "How far along the stage" becomes "how far around the district".
    for wi, w in enumerate(stage.get("Waves", [])):
        if w["TriggerDistance"] < 0:
            continue                      # fires on the previous clear; no place
        t = min(1.0, max(0.0, w["TriggerDistance"] / L))
        sx, sy = spiral(t, E, phase)
        add("WaveMarker", "Wave_%d_trigger" % (wi + 1), x=sx, y=sy, z=FLOOR_TOP_Z + 2,
            fighters=len(w["Fighters"]))

    for gi, g in enumerate(stage.get("Gates", [])):
        t = min(1.0, max(0.0, g["Distance"] / L))
        # A half turn off the way through: a sealed route is beside the road
        # and never standing on it, the rule every version of this game keeps.
        sx, sy = spiral(t, E, phase + 0.5)
        add("Gate", "Gate_%d_%s" % (gi + 1, g["Type"]), x=sx, y=sy, z=FLOOR_TOP_Z + 150,
            GateType=g["Type"], RewardAbility=g["RewardAbility"],
            RewardExperience=g["RewardExperience"],
            GateId="%s_gate%d" % (stage["Name"], gi + 1))

    # Doors, on the rim at each role's fixed bearing -- see the module
    # docstring for why a bearing is fixed here rather than aimed at anything.
    area = next((a for a in world["Areas"] if a["Index"] == idx), None)
    exits_by_side = {}
    if area:
        for side, key, back in (("West", "West", "East"), ("East", "East", "West"), ("Door", "Door", "West")):
            link = area.get(key)
            if not link:
                continue
            dest = stages[link["To"]]
            rad = math.radians(BEARING[side])
            r = E - EXIT_MARGIN
            x, y = math.cos(rad) * r, math.sin(rad) * r
            after = stages[link["AfterCleared"]]["Name"] if link["AfterCleared"] >= 0 else ""
            exits_by_side[side] = dict(
                name="Exit_%s_to_%s" % (side, dest["Name"]), x=x, y=y,
                Side=side, DestinationLevel=level_name(dest), DestinationStage=dest["Name"],
                RequiredAbility=link["RequiredAbility"], AfterClearedStage=after, ArriveAt=back)

    for side, e in exits_by_side.items():
        add("Exit", e["name"], x=e["x"], y=e["y"], z=FLOOR_TOP_Z + 300,
            Side=e["Side"], DestinationLevel=e["DestinationLevel"], DestinationStage=e["DestinationStage"],
            RequiredAbility=e["RequiredAbility"], AfterClearedStage=e["AfterClearedStage"], ArriveAt=e["ArriveAt"])

    # PlayerStart stands at the West door: the common case, coming from the
    # previous area, needs no repositioning at all on arrival -- see
    # ASaudGameMode::PlaceArrivingPlayer. The one stage with no West door at
    # all (BilaNihaya, survival, not on the ring) falls back to a step out
    # from the middle instead.
    if "West" in exits_by_side:
        sx, sy = exits_by_side["West"]["x"], exits_by_side["West"]["y"]
    else:
        sx, sy = SPAWN_RADIUS, 0.0
    add("PlayerStart", "PlayerStart", x=sx, y=sy, z=FLOOR_TOP_Z + 110)

    # Ground: a square big enough to hold the whole disc plus every door,
    # with FLOOR_MARGIN to spare -- checked below, not eyeballed.
    half = E + FLOOR_MARGIN
    add("Floor", "Ground", x=0.0, y=0.0, z=FLOOR_TOP_Z - 50,
        scale=(half * 2.0 / 100.0, half * 2.0 / 100.0, 1.0))

    add("Sun", "Sun", x=0.0, y=0.0, z=1500, pitch=rig["pitch"], yaw=rig["yaw"], color=rig["sun"], lux=rig["lux"])
    add("SkyLight", "SkyLight", x=0.0, y=0.0, z=1200, intensity=rig["sky"])
    add("SkyAtmosphere", "Sky", x=0.0, y=0.0, z=0)
    add("Fog", "Fog", x=0.0, y=0.0, z=0, color=rig["fog"], density=rig["fogd"])
    add("PostProcess", "Post", x=0.0, y=0.0, z=0, exposure=rig["expo"])
    return actors, E, phase


def plan(stages, world):
    return [(level_name(s), s) + plan_level(s, world, stages) for s in stages]


def check(levels):
    """The same three things Tools/fab/lay_out_world.py asserts about its own
    layout, over each standalone level instead of one shared map."""
    for name, stage, actors, extent, phase in levels:
        ground = next(a for a in actors if a["name"] == "Ground")
        half = ground["props"]["scale"][0] * 100.0 / 2.0
        for a in actors:
            if a["kind"] in ("Sun", "SkyLight", "SkyAtmosphere", "Fog", "PostProcess", "Floor"):
                continue
            assert abs(a["x"]) <= half and abs(a["y"]) <= half, \
                "%s: %s at (%.0f, %.0f) is off the ground (half-extent %.0f)" \
                % (name, a["name"], a["x"], a["y"], half)

        for a in actors:
            if a["kind"] != "Exit":
                continue
            r = math.hypot(a["x"], a["y"])
            assert abs(r - (extent - EXIT_MARGIN)) < 1.0, "%s: %s is not on the rim" % (name, a["name"])
            bearing = math.degrees(math.atan2(a["y"], a["x"])) % 360.0
            wanted = BEARING[a["props"]["Side"]] % 360.0
            off = min(abs(bearing - wanted), 360.0 - abs(bearing - wanted))
            assert off < 1.0, "%s: %s sits at %.0f degrees, not its side's %.0f" \
                % (name, a["name"], bearing, wanted)

        for k in range(0, 101):
            r = math.hypot(*spiral(k / 100.0, extent, phase))
            assert 0.17 * extent < r < 0.87 * extent, \
                "%s: the way through leaves the district at t=%.2f" % (name, k / 100.0)
    print("checked: every actor stands on its ground, every door is on its rim at its own")
    print("bearing, and the way through every district stays clear of the middle and the rim.")


def describe(levels):
    for name, stage, actors, extent, phase in levels:
        print("\n%s  (%s, %d cm long, %.0f m district, theme %s)" %
              (name, stage["DisplayName"], stage["Length"], extent / 100.0, stage["Theme"]))
        for a in actors:
            extra = ", ".join("%s=%s" % (k, v) for k, v in a["props"].items()
                              if k in ("StageRow", "GateType", "RewardAbility", "RewardExperience",
                                       "DestinationLevel", "RequiredAbility", "AfterClearedStage",
                                       "Side", "fighters"))
            print("   %-12s %-28s x=%7.0f y=%7.0f z=%5.0f  %s" % (a["kind"], a["name"], a["x"], a["y"], a["z"], extra))


# ----------------------------------------------------------------- editor
def build(levels):
    import unreal  # noqa: E402  (only importable inside the editor)

    ELL = unreal.EditorLevelLibrary
    EAL = unreal.EditorAssetLibrary
    cube = unreal.load_asset("/Engine/BasicShapes/Cube")

    tables = {}
    for t in ("DT_Stages", "DT_Fighters", "DT_Attacks"):
        path = "%s/%s" % (DATA_DIR, t)
        tables[t] = unreal.load_asset(path) if EAL.does_asset_exist(path) else None
        if not tables[t]:
            unreal.log_warning("%s is not imported yet; the WaveDirector will be placed without it. "
                               "Import Content/Data/%s into %s and set it on the director." % (t, t, DATA_DIR))

    def spawn(cls, a):
        loc = unreal.Vector(a["x"], a["y"], a["z"])
        actor = ELL.spawn_actor_from_class(cls, loc, unreal.Rotator(0, 0, 0))
        actor.set_actor_label(a["name"])
        return actor

    def mesh_cube(actor, scale):
        comp = actor.get_component_by_class(unreal.StaticMeshComponent)
        comp.set_static_mesh(cube)
        actor.set_actor_scale3d(unreal.Vector(*scale))

    for name, stage, actors, extent, phase in levels:
        path = "%s/%s" % (MAPS_DIR, name)
        unreal.log("Building %s" % path)
        ELL.new_level(path)

        for a in actors:
            k, p = a["kind"], a["props"]
            if k == "Floor":
                actor = spawn(unreal.StaticMeshActor, a)
                mesh_cube(actor, p["scale"])
                actor.set_mobility(unreal.ComponentMobility.STATIC)
            elif k == "PlayerStart":
                spawn(unreal.PlayerStart, a)
            elif k == "WaveDirector":
                actor = spawn(unreal.WaveDirector, a)
                actor.set_editor_property("stage_row", unreal.Name(p["StageRow"]))
                if tables["DT_Stages"]:   actor.set_editor_property("stage_table", tables["DT_Stages"])
                if tables["DT_Fighters"]: actor.set_editor_property("fighter_table", tables["DT_Fighters"])
                if tables["DT_Attacks"]:  actor.set_editor_property("attack_table", tables["DT_Attacks"])
            elif k == "WaveMarker":
                # A flat disc where the ambush fires. The director triggers on
                # X, not on this; it is here so the map shows where the fights
                # are.
                actor = spawn(unreal.StaticMeshActor, a)
                mesh_cube(actor, (1.2, 1.2, 0.04))
                actor.set_folder_path("Markers")
            elif k == "Gate":
                actor = spawn(unreal.AbilityGate, a)
                mesh_cube(actor, (1.6, 0.6, 3.0))
                actor.set_editor_property("gate_type", getattr(unreal.GateType, p["GateType"].upper()))
                actor.set_editor_property("reward_ability", getattr(unreal.Ability, _enum_name(p["RewardAbility"])))
                actor.set_editor_property("reward_experience", int(p["RewardExperience"]))
                actor.set_editor_property("gate_id", unreal.Name(p["GateId"]))
                actor.set_folder_path("Gates")
            elif k == "Exit":
                actor = spawn(unreal.AreaExit, a)
                actor.set_editor_property("side", getattr(unreal.AreaSide, p["Side"].upper()))
                actor.set_editor_property("arrive_at", getattr(unreal.AreaSide, p["ArriveAt"].upper()))
                actor.set_editor_property("destination_level", unreal.Name(p["DestinationLevel"]))
                actor.set_editor_property("destination_stage", unreal.Name(p["DestinationStage"]))
                actor.set_editor_property("required_ability", getattr(unreal.Ability, _enum_name(p["RequiredAbility"])))
                actor.set_editor_property("after_cleared_stage", unreal.Name(p["AfterClearedStage"]))
                actor.set_folder_path("Exits")
            elif k == "Sun":
                actor = spawn(unreal.DirectionalLight, a)
                actor.set_actor_rotation(unreal.Rotator(p["pitch"], p["yaw"], 0), False)
                light = actor.get_component_by_class(unreal.DirectionalLightComponent)
                light.set_intensity(p["lux"])
                light.set_light_color(unreal.LinearColor(*p["color"]))
                light.set_editor_property("atmosphere_sun_light", True)
                actor.set_folder_path("Lighting")
            elif k == "SkyLight":
                actor = spawn(unreal.SkyLight, a)
                sl = actor.get_component_by_class(unreal.SkyLightComponent)
                sl.set_intensity(p["intensity"])
                sl.set_editor_property("real_time_capture", True)
                actor.set_folder_path("Lighting")
            elif k == "SkyAtmosphere":
                spawn(unreal.SkyAtmosphere, a).set_folder_path("Lighting")
            elif k == "Fog":
                actor = spawn(unreal.ExponentialHeightFog, a)
                fog = actor.get_component_by_class(unreal.ExponentialHeightFogComponent)
                fog.set_editor_property("fog_density", p["density"])
                fog.set_editor_property("fog_inscattering_luminance", unreal.LinearColor(*p["color"]))
                actor.set_folder_path("Lighting")
            elif k == "PostProcess":
                actor = spawn(unreal.PostProcessVolume, a)
                actor.set_editor_property("unbound", True)
                s = actor.get_editor_property("settings")
                # The browser build's post chain: bloom on, a fixed exposure
                # because the stages are lit deliberately, motion blur off
                # because it reads as lag in a fighting game.
                s.set_editor_property("override_bloom_intensity", True)
                s.set_editor_property("bloom_intensity", 0.45)
                s.set_editor_property("override_auto_exposure_method", True)
                s.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
                s.set_editor_property("override_auto_exposure_bias", True)
                s.set_editor_property("auto_exposure_bias", (p["exposure"] - 1.0) * 2.0)
                s.set_editor_property("override_motion_blur_amount", True)
                s.set_editor_property("motion_blur_amount", 0.0)
                actor.set_editor_property("settings", s)
                actor.set_folder_path("Lighting")

        if not ELL.save_current_level():
            unreal.log_error("Could not save %s" % path)
        else:
            unreal.log("Saved %s with %d actors" % (path, len(actors)))

    unreal.log("Built %d levels into %s" % (len(levels), MAPS_DIR))


def _enum_name(s):
    # "None" -> NONE, "DashLeap" -> DASH_LEAP: the Python API exposes UENUM
    # entries in screaming snake case.
    out = ""
    for i, c in enumerate(s):
        if c.isupper() and i and not s[i - 1].isupper():
            out += "_"
        out += c.upper()
    return out


# ------------------------------------------------------------------- main
if __name__ == "__main__" or True:
    _stages, _world = load()
    _levels = plan(_stages, _world)
    check(_levels)
    try:
        import unreal  # noqa: F401
        _in_editor = True
    except ImportError:
        _in_editor = False

    if _in_editor:
        build(_levels)
    else:
        describe(_levels)
        print("\n%d levels planned. Run this inside the Unreal editor to build them." % len(_levels))
