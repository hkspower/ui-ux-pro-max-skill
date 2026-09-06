"""AHMED — Kuwait Fighter :: build the stage maps
==============================================================================
Makes the nine levels (ten with survival) from Content/Data/DT_Stages.json and
DT_World.json, so the maps are generated from the same tables the game runs on
rather than placed by hand and left to drift. Every actor a level needs to be
playable is put down: the ground, the back wall, the player start, the wave
director, every sealed route, every exit to a neighbouring area, and a
lighting rig matched to the browser build's per-stage rig.

It is a blockout. Geometry is engine cubes; the art pass that replaces them is
described in CLAUDE.md. What is NOT a blockout is the data: distances, gates,
exits and their requirements are exact, and regenerating after a balance
change keeps them exact.

RUN IT INSIDE THE EDITOR (it needs the editor's world to make maps):

    Edit ▸ Plugins: enable "Python Editor Script Plugin" and
                    "Editor Scripting Utilities" (both ship with the engine;
                    the .uproject already asks for them), restart.
    Window ▸ Output Log, switch the command line to Python, then:

        exec(open(r"<path to project>/Tools/levels/build_levels.py").read())

    or from a terminal on the Mac, with the editor closed:

        "/Users/Shared/Epic Games/UE_5.4/Engine/Binaries/Mac/UnrealEditor-Cmd" \
            AhmedFighter.uproject -run=pythonscript \
            -script="Tools/levels/build_levels.py"

Existing maps of the same name are overwritten: this script owns them.

OUTSIDE THE EDITOR it prints the plan -- every level and every actor it would
place, with positions -- and exits. That is how it was checked without an
engine, and it is the quickest way to read what a data change does to a map
before opening anything.
==============================================================================
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(PROJECT, "Content", "Data")
MAPS_DIR = "/Game/Maps"
DATA_DIR = "/Game/Data"

# The playfield strip, from AhmedTypes.h. X runs along the stage, Y is depth,
# the camera sits at -Y looking toward +Y, so +Y is the back wall.
DEPTH_MIN, DEPTH_MAX = -420.0, 420.0
FLOOR_TOP_Z = 0.0
# Gates sit into the back wall, past the walkable strip, so they never block
# the critical path -- the rule every version of this game has kept.
GATE_Y = DEPTH_MAX + 360.0
WALL_Y = DEPTH_MAX + 620.0
EXIT_MARGIN = 60.0
SPAWN_X = 300.0

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


def plan_level(stage, world, stages):
    """Everything one level needs, as plain data. The editor half of this file
    only walks the list; the plan is what gets read and checked."""
    L = float(stage["Length"])
    rig = RIGS.get(stage["Theme"], RIGS["Souq"])
    actors = []

    def add(kind, name, x=0.0, y=0.0, z=0.0, **props):
        actors.append(dict(kind=kind, name=name, x=x, y=y, z=z, props=props))

    # ground: covers the strip with a margin either end so an exit is never
    # standing over nothing
    add("Floor", "Ground", x=L / 2, y=0, z=FLOOR_TOP_Z - 50,
        scale=((L + 2400) / 100, (DEPTH_MAX - DEPTH_MIN + 2000) / 100, 1.0))
    # back wall the gates are set into, and something for the light to fall on
    add("Wall", "BackWall", x=L / 2, y=WALL_Y, z=300,
        scale=((L + 2400) / 100, 1.2, 7.0))

    add("PlayerStart", "PlayerStart", x=SPAWN_X, y=0, z=FLOOR_TOP_Z + 110)
    add("WaveDirector", "WaveDirector", x=0, y=0, z=FLOOR_TOP_Z, StageRow=stage["Name"])

    for wi, w in enumerate(stage.get("Waves", [])):
        if w["TriggerDistance"] < 0:
            continue                      # fires on the previous clear; no place
        add("WaveMarker", "Wave_%d_trigger" % (wi + 1), x=w["TriggerDistance"], y=0, z=FLOOR_TOP_Z + 2,
            fighters=len(w["Fighters"]))

    for gi, g in enumerate(stage.get("Gates", [])):
        add("Gate", "Gate_%d_%s" % (gi + 1, g["Type"]), x=g["Distance"], y=GATE_Y, z=FLOOR_TOP_Z + 150,
            GateType=g["Type"], RewardAbility=g["RewardAbility"],
            RewardExperience=g["RewardExperience"],
            GateId="%s_gate%d" % (stage["Name"], gi + 1))

    # exits, from the world graph
    area = next((a for a in world["Areas"] if a["Index"] == stage.get("Index", -1)), None)
    if area:
        for side, key, back in (("West", "West", "East"), ("East", "East", "West"), ("Door", "Door", "West")):
            link = area.get(key)
            if not link:
                continue
            dest = stages[link["To"]]
            x = {"West": EXIT_MARGIN, "East": L - EXIT_MARGIN}.get(side, float(link["Distance"]))
            after = stages[link["AfterCleared"]]["Name"] if link["AfterCleared"] >= 0 else ""
            add("Exit", "Exit_%s_to_%s" % (side, dest["Name"]), x=x, y=0, z=FLOOR_TOP_Z + 300,
                Side=side, DestinationLevel=level_name(dest), DestinationStage=dest["Name"],
                RequiredAbility=link["RequiredAbility"], AfterClearedStage=after, ArriveAt=back)

    add("Sun", "Sun", x=L / 2, y=0, z=1500, pitch=rig["pitch"], yaw=rig["yaw"], color=rig["sun"], lux=rig["lux"])
    add("SkyLight", "SkyLight", x=L / 2, y=0, z=1200, intensity=rig["sky"])
    add("SkyAtmosphere", "Sky", x=L / 2, y=0, z=0)
    add("Fog", "Fog", x=L / 2, y=0, z=0, color=rig["fog"], density=rig["fogd"])
    add("PostProcess", "Post", x=L / 2, y=0, z=0, exposure=rig["expo"])
    return actors


def plan(stages, world):
    return [(level_name(s), s, plan_level(s, world, stages)) for s in stages]


def describe(levels):
    for name, stage, actors in levels:
        print("\n%s  (%s, %d cm, theme %s)" % (name, stage["DisplayName"], stage["Length"], stage["Theme"]))
        for a in actors:
            extra = ", ".join("%s=%s" % (k, v) for k, v in a["props"].items()
                              if k in ("StageRow", "GateType", "RewardAbility", "RewardExperience",
                                       "DestinationLevel", "RequiredAbility", "AfterClearedStage", "fighters"))
            print("   %-12s %-28s x=%7.0f y=%6.0f z=%5.0f  %s" % (a["kind"], a["name"], a["x"], a["y"], a["z"], extra))


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

    for name, stage, actors in levels:
        path = "%s/%s" % (MAPS_DIR, name)
        unreal.log("Building %s" % path)
        ELL.new_level(path)

        for a in actors:
            k, p = a["kind"], a["props"]
            if k in ("Floor", "Wall"):
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
                # A thin line across the strip where the ambush fires. The
                # director triggers on X, not on this; it is here so the map
                # shows where the fights are.
                actor = spawn(unreal.StaticMeshActor, a)
                mesh_cube(actor, (0.06, (DEPTH_MAX - DEPTH_MIN) / 100, 0.04))
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
