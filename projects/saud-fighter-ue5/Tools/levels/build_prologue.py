"""SAUD — Kuwait Fighter :: build L_Prologue
==============================================================================
The one level that is not one of the nine. Saud's life before he fell: a
title bout, then a short walk to the hole in the street. It is never on the
ring map and it is never revisited -- ASaudPrologueGameMode sends a player
who has already seen it straight to L_SouqAlDawar, where every version of
this game has always begun.

This is deliberately a SEPARATE script from build_levels.py rather than one
more row it plans. Three reasons:

  * build_levels.py generates from DT_Stages.json / DT_World.json, both
    exported from the browser build. This level answers to neither -- it has
    no row on the ring, no exits graph, no DisplayName the map screen will
    ever show -- and does not belong in a table the browser project owns.
  * build_levels.py's own blockout is still written to the strip this game
    stopped being on 2026-09-16: DEPTH_MIN/DEPTH_MAX, a back wall gates are
    set into, exits called West/East. None of that has been true of a fight
    since SaudArena.h. This script is written to the model that replaced
    it -- a circular arena wherever the wave wakes, SaudGameplay::ArenaRadius
    -- rather than inheriting a strip layout for a level that never had one.
    build_levels.py itself has not been brought up to date; that is a real
    gap, and fixing it is a separate job from this one.
  * The fight in it is one wave, one archetype, no gates and no crowd slots
    -- CrowdSlot/PushApart exist for a wave arriving from every direction,
    and a title bout is one man across the cage, not a wave.

RUN IT INSIDE THE EDITOR, the same way as build_levels.py:

    exec(open(r"<path to project>/Tools/levels/build_prologue.py").read())

OUTSIDE THE EDITOR it prints the plan and exits, which is how it was checked
without one.
==============================================================================
"""

MAPS_DIR = "/Game/Maps"
DATA_DIR = "/Game/Data"
LEVEL_NAME = "L_Prologue"
GAME_MODE_PATH = "/Script/SaudFighter.SaudPrologueGameMode"

# Saud's own gym, not one of the nine districts, so it takes its own rig
# rather than reaching into RIGS in build_levels.py -- cooler and dimmer than
# any street theme, an indoor cage under work lights.
RIG = dict(pitch=-78, yaw=-100, sun=(0.91, 0.94, 1.00), lux=4.5,
           sky=0.7, fog=(0.47, 0.59, 0.75), fogd=0.008, expo=0.98)

FLOOR_TOP_Z = 0.0
SPAWN_X = 300.0
# Where the wave locks -- BeginWave centres the arena on the player, not on a
# fixed point, so this is only where he is standing when the level opens.
CAGE_CENTRE = (SPAWN_X, 0.0)
CAGE_RADIUS = 1150.0   # just outside SaudGameplay::ArenaRadius (1100 cm)
STAND_Y = 1500.0
# The stage's own Length in DT_Prologue.json: how far he has to walk past the
# cage before AWaveDirector calls it cleared, and the roam circle's radius
# while the arena is not locked. Keep both in view of the exit below.
STAGE_LENGTH = 2800.0
# AWaveDirector calls the stage cleared once the player has walked past
# Length-360 from the DIRECTOR's own location -- which build_levels.py, and
# this script, place at the district origin, not at spawn. The exit itself
# sits further out still, at Length-EXIT_MARGIN, so "stage cleared" (and its
# Stage_Clear cue) fires before he ever reaches it -- the same relationship
# every one of the nine real stages keeps between those two numbers.
EXIT_MARGIN = 60.0
EXIT_X = STAGE_LENGTH - EXIT_MARGIN
FLOOR_MARGIN = 400.0   # clearance past the furthest thing standing on it
FLOOR_MIN_X = CAGE_CENTRE[0] - CAGE_RADIUS - FLOOR_MARGIN
FLOOR_MAX_X = EXIT_X + FLOOR_MARGIN
FLOOR_MIN_Y = -STAND_Y - FLOOR_MARGIN
FLOOR_MAX_Y = STAND_Y + FLOOR_MARGIN


def plan():
    """Every actor the level needs, as plain data -- the same shape
    build_levels.py plans in, so a reader of one can read the other."""
    actors = []

    def add(kind, name, x=0.0, y=0.0, z=0.0, **props):
        actors.append(dict(kind=kind, name=name, x=x, y=y, z=z, props=props))

    # Ground: covers the cage behind spawn, the walk out, and the stands
    # either side, with FLOOR_MARGIN of clearance past all three -- checked
    # below rather than eyeballed, the same discipline lay_out_world.py
    # holds its own layout to.
    width  = FLOOR_MAX_X - FLOOR_MIN_X
    depth  = FLOOR_MAX_Y - FLOOR_MIN_Y
    centre_x = (FLOOR_MIN_X + FLOOR_MAX_X) / 2
    add("Floor", "Ground", x=centre_x, y=0, z=FLOOR_TOP_Z - 50,
        scale=(width / 100, depth / 100, 1.0))

    add("PlayerStart", "PlayerStart", x=SPAWN_X, y=0, z=FLOOR_TOP_Z + 110)

    # The cage: seven low wall posts on an octagon just outside the fight
    # circle, dressing only -- ASaudCharacter::SetArenaCircle is what
    # actually holds anyone inside it, the same as every other stage's
    # locked arena. The eighth post, on +X, is left out: the gap it would
    # have stood in is the cage door, and it faces the exit.
    import math
    posts = 8
    for i in range(posts):
        angle = 2 * math.pi * i / posts
        if abs(math.degrees(angle)) < 1e-6:
            continue
        x = CAGE_CENTRE[0] + CAGE_RADIUS * math.cos(angle)
        y = CAGE_CENTRE[1] + CAGE_RADIUS * math.sin(angle)
        add("Wall", "CagePost_%d" % i, x=x, y=y, z=FLOOR_TOP_Z + 60,
            scale=(0.5, 0.5, 1.2), rotationYaw=math.degrees(angle))

    # A stand either side, implying the crowd a title bout draws without
    # needing a single one of them modelled.
    add("Wall", "Stand_Near", x=CAGE_CENTRE[0], y=-STAND_Y, z=FLOOR_TOP_Z + 150,
        scale=(14.0, 3.0, 3.0))
    add("Wall", "Stand_Far", x=CAGE_CENTRE[0], y=STAND_Y, z=FLOOR_TOP_Z + 150,
        scale=(14.0, 3.0, 3.0))

    # At the district origin, not at spawn -- matches build_levels.py, and is
    # what LocalX()/the stage-cleared distance in DT_Prologue.json's Length
    # are measured from. The fight itself still locks around wherever the
    # player is actually standing; only the roam circle and "reached the far
    # end" are measured from here.
    add("WaveDirector", "WaveDirector", x=0.0, y=0, z=FLOOR_TOP_Z,
        StageRow="Prologue", StageTable="DT_Prologue")

    # The hole in the street. Side=East so AAreaExit checks the director's
    # arena lock before it opens -- the door off the cage he cannot use until
    # the bout is won, for free, because that check already exists.
    add("Exit", "Exit_TheHole", x=EXIT_X, y=0, z=FLOOR_TOP_Z + 300,
        Side="East", DestinationLevel="L_SouqAlDawar", DestinationStage="SouqAlDawar",
        RequiredAbility="None", AfterClearedStage="", ArriveAt="West")

    add("Sun", "Sun", x=STAGE_LENGTH / 2, y=0, z=1500,
        pitch=RIG["pitch"], yaw=RIG["yaw"], color=RIG["sun"], lux=RIG["lux"])
    add("SkyLight", "SkyLight", x=STAGE_LENGTH / 2, y=0, z=1200, intensity=RIG["sky"])
    add("SkyAtmosphere", "Sky", x=STAGE_LENGTH / 2, y=0, z=0)
    add("Fog", "Fog", x=STAGE_LENGTH / 2, y=0, z=0, color=RIG["fog"], density=RIG["fogd"])
    add("PostProcess", "Post", x=STAGE_LENGTH / 2, y=0, z=0, exposure=RIG["expo"])
    return actors


def check(actors):
    """Nothing placed stands off the edge of the ground it needs -- the same
    kind of assertion lay_out_world.py runs over its own layout, because a
    blockout that floats a wall over nothing is a bug whether or not anyone
    ever opens it in an editor to see."""
    ground = next(a for a in actors if a["name"] == "Ground")
    hw = ground["props"]["scale"][0] * 100 / 2
    hd = ground["props"]["scale"][1] * 100 / 2
    gx0, gx1 = ground["x"] - hw, ground["x"] + hw
    gy0, gy1 = ground["y"] - hd, ground["y"] + hd
    for a in actors:
        if a["kind"] in ("Sun", "SkyLight", "SkyAtmosphere", "Fog", "PostProcess", "Floor"):
            continue   # not things that stand on the ground
        assert gx0 <= a["x"] <= gx1, "%s at x=%.0f is off the ground (ground is [%.0f, %.0f])" % (a["name"], a["x"], gx0, gx1)
        assert gy0 <= a["y"] <= gy1, "%s at y=%.0f is off the ground (ground is [%.0f, %.0f])" % (a["name"], a["y"], gy0, gy1)
    # The exit has to be outside the fight circle, or the cage door would open
    # onto the exit before the bout starts.
    exit_a = next(a for a in actors if a["name"] == "Exit_TheHole")
    dist = ((exit_a["x"] - CAGE_CENTRE[0]) ** 2 + (exit_a["y"] - CAGE_CENTRE[1]) ** 2) ** 0.5
    assert dist > CAGE_RADIUS, "the exit sits inside the fight circle"
    # AWaveDirector's "stage cleared" fires at Director.X + Length - 360; the
    # exit must sit past that, or the level ends with him standing on the
    # exit before the Stage_Clear cue -- or worse than a cue out of order,
    # AAreaExit whisks him to L_SouqAlDawar before it can ever fire at all.
    director = next(a for a in actors if a["kind"] == "WaveDirector")
    clear_x = director["x"] + STAGE_LENGTH - 360.0
    assert exit_a["x"] >= clear_x, (
        "the exit at x=%.0f sits before the clear threshold at x=%.0f -- "
        "AWaveDirector will never call this stage cleared" % (exit_a["x"], clear_x))
    print("checked: everything placed stands on the ground, the exit is outside the cage,")
    print("and stage-clear fires before he can reach it.")


def describe(actors):
    print("\n%s  (Saud's life before he fell, %d cm, never on the ring map)" %
          (LEVEL_NAME, STAGE_LENGTH))
    for a in actors:
        extra = ", ".join("%s=%s" % (k, v) for k, v in a["props"].items()
                          if k in ("StageRow", "StageTable", "DestinationLevel",
                                   "RequiredAbility", "Side", "ArriveAt"))
        print("   %-12s %-16s x=%7.0f y=%6.0f z=%5.0f  %s" %
              (a["kind"], a["name"], a["x"], a["y"], a["z"], extra))
    print("\nWaveDirector reads Prologue from Content/Data/DT_Prologue.json,")
    print("a hand-authored table -- like DT_Sounds.csv, it is not exported")
    print("from the browser build and Tools/export/export.mjs never touches it.")


def build(actors):
    import unreal  # noqa: E402  (only importable inside the editor)

    ELL = unreal.EditorLevelLibrary
    EAL = unreal.EditorAssetLibrary
    cube = unreal.load_asset("/Engine/BasicShapes/Cube")

    prologue_table_path = "%s/DT_Prologue" % DATA_DIR
    fighter_table_path = "%s/DT_Fighters" % DATA_DIR
    prologue_table = unreal.load_asset(prologue_table_path) if EAL.does_asset_exist(prologue_table_path) else None
    fighter_table = unreal.load_asset(fighter_table_path) if EAL.does_asset_exist(fighter_table_path) else None
    if not prologue_table:
        unreal.log_warning("%s is not imported yet -- import Content/Data/DT_Prologue.json "
                           "into %s before running this, or the director will have no row to read."
                           % (prologue_table_path, DATA_DIR))

    def spawn(cls, a, yaw=0.0):
        loc = unreal.Vector(a["x"], a["y"], a["z"])
        actor = ELL.spawn_actor_from_class(cls, loc, unreal.Rotator(0, yaw, 0))
        actor.set_actor_label(a["name"])
        return actor

    def mesh_cube(actor, scale):
        comp = actor.get_component_by_class(unreal.StaticMeshComponent)
        comp.set_static_mesh(cube)
        actor.set_actor_scale3d(unreal.Vector(*scale))

    path = "%s/%s" % (MAPS_DIR, LEVEL_NAME)
    unreal.log("Building %s" % path)
    ELL.new_level(path)

    for a in actors:
        k, p = a["kind"], a["props"]
        if k in ("Floor", "Wall"):
            actor = spawn(unreal.StaticMeshActor, a, yaw=p.get("rotationYaw", 0.0))
            mesh_cube(actor, p["scale"])
            actor.set_mobility(unreal.ComponentMobility.STATIC)
            if k == "Wall" and a["name"].startswith("CagePost"):
                actor.set_folder_path("Cage")
            elif k == "Wall":
                actor.set_folder_path("Crowd")
        elif k == "PlayerStart":
            spawn(unreal.PlayerStart, a)
        elif k == "WaveDirector":
            actor = spawn(unreal.WaveDirector, a)
            actor.set_editor_property("stage_row", unreal.Name(p["StageRow"]))
            if prologue_table: actor.set_editor_property("stage_table", prologue_table)
            if fighter_table:  actor.set_editor_property("fighter_table", fighter_table)
        elif k == "Exit":
            actor = spawn(unreal.AreaExit, a)
            actor.set_editor_property("side", getattr(unreal.AreaSide, p["Side"].upper()))
            actor.set_editor_property("arrive_at", getattr(unreal.AreaSide, p["ArriveAt"].upper()))
            actor.set_editor_property("destination_level", unreal.Name(p["DestinationLevel"]))
            actor.set_editor_property("destination_stage", unreal.Name(p["DestinationStage"]))
            actor.set_editor_property("required_ability", getattr(unreal.Ability, p["RequiredAbility"].upper()))
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

    # This level's GameMode is ASaudPrologueGameMode, not the project
    # default -- it must not write a stage clear into the same economy the
    # other nine share. This is the one call in this file least likely to be
    # right first try: "Game Mode Override" in World Settings is exposed to
    # Python as AWorldSettings.default_game_mode as of 5.4, but that has
    # moved before and neither this script nor build_levels.py has ever run
    # against a real editor to confirm it.
    world = ELL.get_editor_world()
    settings = world.get_world_settings()
    game_mode_class = unreal.load_class(None, GAME_MODE_PATH)
    if game_mode_class:
        settings.set_editor_property("default_game_mode", game_mode_class)
    else:
        unreal.log_warning("Could not load %s -- set L_Prologue's Game Mode Override "
                           "by hand in World Settings." % GAME_MODE_PATH)

    if not ELL.save_current_level():
        unreal.log_error("Could not save %s" % path)
    else:
        unreal.log("Saved %s with %d actors" % (path, len(actors)))


if __name__ == "__main__" or True:
    _actors = plan()
    check(_actors)
    try:
        import unreal  # noqa: F401
        _in_editor = True
    except ImportError:
        _in_editor = False

    if _in_editor:
        build(_actors)
    else:
        describe(_actors)
        print("\n%d actors planned for %s. Run this inside the Unreal editor to build it." %
              (len(_actors), LEVEL_NAME))
