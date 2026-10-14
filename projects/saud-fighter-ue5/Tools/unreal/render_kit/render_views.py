"""
SAUD render kit -- render_views.py. Runs INSIDE the full Unreal editor, on a
PC with a graphics card; RENDER_SAUD.bat starts it:

    UnrealEditor.exe SaudFighter.uproject -ExecutePythonScript="<this file>"
        -unattended -nosplash

It returns at once and does its work on the editor's own ticks (a Slate
post-tick callback), one view at a time: load the view's map, put the
anime look's post-process over it (USaudLookSubsystem does that only in a
game world, never in the editor's -- so it is done here the way that
subsystem does it), spawn a CineCameraActor at the view, wait for shaders,
streaming and Lumen to settle, take a 1920x1080 high-resolution screenshot
through that camera into Saved/RenderKit/<name>.png, wait for the file, and
go on. A missing map, a failed view or a screenshot that never lands is
written down and skipped. At the end it writes Saved/RenderKit/
render_report.txt and quits the editor; RENDER_SAUD.bat's watchdog kills it
if it does not.

THE VIEWS are the Blender previews' own cameras, so each still can be laid
beside the picture already in Docs/renders/ (the last column):
  - the open world and its nine districts: build_map_scenes.world_cameras,
    read out of Tools/blender/scenes/World.blend;
  - the souq: build_souq.Souq.cameras() on its own plan (fight, street,
    gate, overview) -- in L_SouqAlDawar, which is the souq those previews
    were rendered in, and the fight, street and gate again in the open
    world at the souq district's middle (0, 37000) from build_world.plan(),
    where the souq's sites are the level's to the centimetre;
  - the title: SaudTitle::Shoot (Combat/SaudTitle.h, run through
    Tools/harness/title_dump.cpp) at T 0 on a 1920x1080 screen, for Saud's
    feet and facing in Tools/blender/scenes/SouqAlDawar_fight.blend, as
    title_preview.py takes them (the eye's line to him was ray-cast in that
    scene, 2026-10-14: no wall, so it is not pulled in);
  - the prologue and the monkey island: build_map_scenes.build_prologue /
    island_cameras, read out of Prologue.blend and MonkeyIsland.blend.
How Blender's numbers become Unreal's is the project's own, not invented
here: the world's, the souq's and the prologue's Blender scenes are their
plans' centimetres as metres with the same axes (build_map_scenes.py
"FRAMES"; the editor scripts spawn at the plans' centimetres), so Unreal =
Blender x 100; the island's scene is in map metres, x east, y north, and
build_monkey_island_level.ue() makes (x, y, z) m -> (100x, -100y, 100z) cm.
A Blender lens L on its 36 mm sensor (fit to the 16:9 frame's width) is a
horizontal field of view of 2 atan(18 / L). Cam_World's lens shift has no
Unreal equal; that view is aimed at the shifted frame's middle instead.
Because Unreal's frame is left-handed and Blender's right-handed, a still
of the world, the souq or the prologue (taken over unchanged) is its
Blender picture mirrored left to right (title_preview.py says the same of
its own round trip); the island's, whose ue() turns y over, is not. The numbers were
taken 2026-10-14 by a scratch script from the files named above; re-take
them if those scenes are rebuilt.

UNVERIFIED ENGINE PYTHON APIs used in this file (none could be run here;
what each is assumed to do):
  unreal.register_slate_post_tick_callback(fn) / unregister_... -> fn(dt)
         every editor frame; returns a handle
  unreal.EditorLoadingAndSavingUtils.load_map(path) -> opens a map without
         asking to save the open one (else LevelEditorSubsystem.load_level)
  unreal.EditorAssetLibrary.does_asset_exist / load_asset
  unreal.get_editor_subsystem(cls) -> the editor subsystem of that class
  unreal.Rotator(roll=, pitch=, yaw=) -> keyword arguments, as build_world.py
         and build_souq.py already spell them (the positional order is roll,
         pitch, yaw: CLAUDE.md "Known, not fixed")
  unreal.EditorActorSubsystem.spawn_actor_from_class(cls, loc, rot,
         transient=True) (else without transient) / destroy_actor
  unreal.CineCameraActor .get_cine_camera_component(); the component's
         filmback (sensor_width, sensor_height), current_focal_length,
         focus_settings.focus_method = CameraFocusMethod.DISABLE,
         set_field_of_view(deg)
  unreal.PostProcessVolume editor properties unbound, priority,
         blend_weight, settings; PostProcessSettings: weighted_blendables
         (WeightedBlendables(array=[WeightedBlendable(weight, object)])),
         override_film_slope / film_slope, ..._film_toe, ..._film_shoulder,
         ..._film_black_clip, ..._film_white_clip, ..._blue_correction,
         ..._expand_gamut, ..._tone_curve_amount, ..._vignette_intensity,
         ..._bloom_intensity, ..._film_grain_intensity,
         ..._scene_fringe_intensity
  unreal.SkeletalMeshActor, its skeletal_mesh_component and
         set_skeletal_mesh_asset (else set_skeletal_mesh) -- only for Saud
         in the two title views; and that his imported mesh faces its own
         +Y as the UE mannequin does (so he is turned his facing - 90)
  unreal.WorldPartitionBlueprintLibrary.get_actor_descs() and
         load_actors(guids) -> every actor of a partitioned map loaded in
         the editor (L_MonkeyIsland is one)
  unreal.AutomationLibrary.take_high_res_screenshot(res_x, res_y,
         filename, camera=..., force_game_view=True) -> writes the PNG some
         frames later (searched for under Saved/RenderKit and
         Saved/Screenshots and moved into Saved/RenderKit)
  unreal.UnrealEditorSubsystem.set_level_viewport_camera_info(loc, rot)
         -> the editor viewport looks from there (so streaming, shaders and
         Lumen warm up where the shot is; and the fallback when the
         screenshot through the camera fails: console HighResShot)
  unreal.LevelEditorSubsystem.editor_set_game_view(True) -> no editor icons
  unreal.SystemLibrary.execute_console_command(None, cmd) -> runs
         "r.HighResScreenshotDelay 60" (frames the high-res shot renders
         before it is kept, so Lumen and TSR settle at 1920x1080) and
         "HighResShot 1920x1080 filename=..." (the fallback)
  unreal.get_default_object(unreal.EditorPerformanceSettings) and its
         throttle_cpu_when_not_foreground -> off, so the editor keeps
         rendering behind other windows
  shader / asset compiling: probed by name -- unreal.ShaderCompiler,
         ShaderCompilingManager, AssetCompilingManager with is_compiling /
         get_num_remaining_jobs / get_num_remaining_assets; whichever answers
         is used and named in the report; if none does, the wait is frames
         and seconds only (FIRST_SETTLE_S on a map's first view)
  unreal.SystemLibrary.get_engine_version(), quit_editor()
  unreal.Paths.project_saved_dir / convert_relative_path_to_full
"""

import glob
import math
import os
import re
import shutil
import sys
import time
import traceback

import unreal

# name, map (/Game/Maps/...), camera location (cm), rotation (pitch, yaw,
# roll in degrees), horizontal field of view (degrees), the Blender preview
# in Docs/renders it compares with, where the numbers come from, extras.
VIEWS = (
    ("world_ring",             "L_AlHalqa_World", (-16795.0,  95249.3, 70270.3), (-41.064,  -81.247, 0.0), 54.432, "map-World-anime.png",
     "build_map_scenes.world_cameras Cam_World (its lens shift 0.0160/-0.0863 re-aimed)", {}),
    ("world_SouqAlDawar",      "L_AlHalqa_World", (      0.0,  66912.7, 23370.4), (-38.000,  -90.000, 0.0), 54.432, "map-SouqAlDawar-anime.png",
     "build_map_scenes.world_cameras Cam_SouqAlDawar", {}),
    ("world_BaytAlDarb",       "L_AlHalqa_World", (  44494.2,  44494.2, 20254.3), (-38.000, -135.000, 0.0), 54.432, "map-BaytAlDarb-anime.png",
     "build_map_scenes.world_cameras Cam_BaytAlDarb", {}),
    ("world_MarsaAlFajr",      "L_AlHalqa_World", (  68770.0,      0.0, 24821.4), (-38.000,  180.000, 0.0), 54.432, "map-MarsaAlFajr-anime.png",
     "build_map_scenes.world_cameras Cam_MarsaAlFajr", {}),
    ("world_AbrajAlMalih",     "L_AlHalqa_World", (  45904.3, -45904.3, 21812.3), (-38.000,  135.000, 0.0), 54.432, "map-AbrajAlMalih-anime.png",
     "build_map_scenes.world_cameras Cam_AbrajAlMalih", {}),
    ("world_AlHilal",          "L_AlHalqa_World", (      0.0, -58936.0, 17138.3), (-38.000,   90.000, 0.0), 54.432, "map-AlHilal-anime.png",
     "build_map_scenes.world_cameras Cam_AlHilal", {}),
    ("world_JaziratAlHajar",   "L_AlHalqa_World", ( -49782.1, -49782.1, 26096.9), (-38.000,   45.000, 0.0), 54.432, "map-JaziratAlHajar-anime.png",
     "build_map_scenes.world_cameras Cam_JaziratAlHajar", {}),
    ("world_AlTariqAlMasdud",  "L_AlHalqa_World", ( -68770.0,      0.0, 24821.4), (-38.000,    0.000, 0.0), 54.432, "map-AlTariqAlMasdud-anime.png",
     "build_map_scenes.world_cameras Cam_AlTariqAlMasdud", {}),
    ("world_MukhayyamAlNiran", "L_AlHalqa_World", ( -47314.4,  47314.4, 23370.3), (-38.000,  -45.000, 0.0), 54.432, "map-MukhayyamAlNiran-anime.png",
     "build_map_scenes.world_cameras Cam_MukhayyamAlNiran", {}),
    ("world_AlHalqa",          "L_AlHalqa_World", (  -2728.2,  15472.4, 12274.8), (-38.000,  -80.000, 0.0), 54.432, "map-AlHalqa-anime.png",
     "build_map_scenes.world_cameras Cam_AlHalqa", {}),
    ("world_souq_fight",       "L_AlHalqa_World", (   5143.7,  37515.8,   170.0), ( -5.947,   24.781, 0.0), 48.455, "souq-fight-anime.png",
     "build_souq.Souq.cameras souq-fight.png + the souq's middle in build_world.plan()", {}),
    ("world_souq_street",      "L_AlHalqa_World", (   5624.2,  37766.4,   165.0), ( -0.979,   95.348, 0.0), 69.390, "souq-street-anime.png",
     "build_souq.Souq.cameras souq-street.png + the souq's middle in build_world.plan()", {}),
    ("world_souq_gate",        "L_AlHalqa_World", (   5823.4,  39131.8,   160.0), ( -1.418, -158.624, 0.0), 58.716, "souq-gate-anime.png",
     "build_souq.Souq.cameras souq-gate.png + the souq's middle in build_world.plan()", {}),
    ("world_title",            "L_AlHalqa_World", (   5621.6,  38297.1,   153.0), ( -5.305, -102.704, 0.0), 54.022, "menu-title-3d.png",
     "SaudTitle::Shoot(T 0, 1920x1080) for Saud's feet in SouqAlDawar_fight.blend, + the souq's middle",
     {"saud_feet": (5623.1, 37737.1, 3.0), "saud_yaw": 90.158}),
    ("souq_overview",          "L_SouqAlDawar",   (  11016.0, -13464.0,  9180.0), (-27.821,  129.289, 0.0), 65.470, "souq-overview.png",
     "build_souq.Souq.cameras souq-overview.png", {}),
    ("souq_fight",             "L_SouqAlDawar",   (   5143.7,    515.8,   170.0), ( -5.947,   24.781, 0.0), 48.455, "souq-fight-anime.png",
     "build_souq.Souq.cameras souq-fight.png (= Cam_souq-fight in SouqAlDawar_fight.blend)", {}),
    ("souq_street",            "L_SouqAlDawar",   (   5624.2,    766.4,   165.0), ( -0.979,   95.348, 0.0), 69.390, "souq-street-anime.png",
     "build_souq.Souq.cameras souq-street.png", {}),
    ("souq_gate",              "L_SouqAlDawar",   (   5823.4,   2131.8,   160.0), ( -1.418, -158.624, 0.0), 58.716, "souq-gate-anime.png",
     "build_souq.Souq.cameras souq-gate.png", {}),
    ("souq_title",             "L_SouqAlDawar",   (   5621.6,   1297.1,   153.0), ( -5.305, -102.704, 0.0), 54.022, "menu-title-3d.png",
     "SaudTitle::Shoot(T 0, 1920x1080) for Saud's feet in SouqAlDawar_fight.blend (title_dump.cpp)",
     {"saud_feet": (5623.1, 737.1, 3.0), "saud_yaw": 90.158}),
    ("prologue",               "L_Prologue",      (   2155.5,  -3489.6,  2665.8), (-34.000,  118.000, 0.0), 61.928, "map-Prologue-anime.png",
     "build_map_scenes.build_prologue Cam_Prologue", {}),
    ("island",                 "L_MonkeyIsland",  (-302161.5, -109977.8, 104479.1), (-18.000,  20.000, 0.0), 61.928, "map-MonkeyIsland-anime.png",
     "build_map_scenes.island_cameras Cam_MonkeyIsland, through ue()", {}),
    ("island_landing",         "L_MonkeyIsland",  (-176635.2,  10671.0,  2800.0), (-10.211,  -22.875, 0.0), 61.928, "map-MonkeyIsland-Landing-anime.png",
     "build_map_scenes.island_cameras Cam_MonkeyIsland_Landing, through ue()", {}),
    ("island_clearing",        "L_MonkeyIsland",  ( -61949.0,  25600.0,  7264.8), (-21.996,    0.000, 0.0), 69.390, "map-MonkeyIsland-Clearing-anime.png",
     "build_map_scenes.island_cameras Cam_MonkeyIsland_Clearing, through ue()", {}),
    ("island_temple",          "L_MonkeyIsland",  (  48539.1,  26599.6,  8600.0), (-17.542,   61.599, 0.0), 65.470, "map-MonkeyIsland-Temple-anime.png",
     "build_map_scenes.island_cameras Cam_MonkeyIsland_Temple, through ue()", {}),
)

RES = (1920, 1080)
SENSOR_MM = (36.0, 20.25)         # Blender's 36 mm, fit to the width; 16:9
MAPS = "/Game/Maps"
LOOK_POST = "/Game/Materials/Anime/M_Anime_Post"
LOOK_FRAME = "/Game/Materials/Anime/M_Anime_Frame"
LOOK_MPC = "/Game/Materials/Anime/MPC_Anime"
SAUD_MESH = "/Game/Models/Saud"
FIRST_SETTLE_S = 60.0             # a map's first view: at least this long after it opens
SETTLE_S = 8.0                    # every other view
SETTLE_FRAMES = 120               # and this many frames after everything says it is idle
MAX_SETTLE_S = 20 * 60.0          # never wait longer than this on compiling for one view
SHOT_WAIT_S = 180.0               # how long a screenshot may take to land
BUDGET_S = 85 * 60.0              # stop, report and quit before RENDER_SAUD.bat's watchdog (90 min)
HIGHRES_DELAY_FRAMES = 60


# ------------------------------------------------------------------ paths
def _full(p):
    try:
        return os.path.normpath(unreal.Paths.convert_relative_path_to_full(p))
    except Exception:
        return os.path.normpath(os.path.abspath(p))


def _project():
    f = globals().get("__file__")
    if f and os.path.exists(f):
        p = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(f)), "..", "..", ".."))
        if os.path.exists(os.path.join(p, "SaudFighter.uproject")):
            return p
    return _full(unreal.Paths.project_dir())


PROJECT = _project()
try:
    SAVED = _full(unreal.Paths.project_saved_dir())
except Exception:
    SAVED = os.path.join(PROJECT, "Saved")
OUT = os.path.join(SAVED, "RenderKit")
REPORT = os.path.join(OUT, "render_report.txt")
PROGRESS = os.path.join(OUT, "render_progress.txt")
SHOT_DIRS = (OUT, os.path.join(SAVED, "Screenshots"))


def riyadh(t=None):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime((time.time() if t is None else t) + 3 * 3600))


def say(msg):
    print("[render kit] " + msg)
    sys.stdout.flush()


def last_line(exc_text):
    return exc_text.strip().splitlines()[-1] if exc_text.strip() else ""


# ------------------------------------------------------------- the engine
def _film():
    """SaudAnime::Film, read from the header the look subsystem pins it from
    (as camera_fade.py reads SaudCamera.h), not copied."""
    path = os.path.join(PROJECT, "Source", "SaudFighter", "Combat", "SaudAnime.h")
    text = open(path, encoding="utf-8").read()
    m = re.search(r"namespace Film\s*\{(.*?)\}", text, re.S)
    if not m:
        raise RuntimeError("no namespace Film in %s" % path)
    return {k: float(v) for k, v in re.findall(r"constexpr float (\w+) = ([-0-9.]+)f;", m.group(1))}


# SaudLookSubsystem.cpp's FPostProcessSettings fields -> their Python names
FILM_FIELDS = (("Slope", "film_slope"), ("Toe", "film_toe"), ("Shoulder", "film_shoulder"),
               ("BlackClip", "film_black_clip"), ("WhiteClip", "film_white_clip"),
               ("BlueCorrection", "blue_correction"), ("ExpandGamut", "expand_gamut"),
               ("ToneCurveAmount", "tone_curve_amount"), ("Vignette", "vignette_intensity"),
               ("Bloom", "bloom_intensity"), ("Grain", "film_grain_intensity"),
               ("Fringe", "scene_fringe_intensity"))


class Kit:
    def __init__(self):
        self.EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        self.EAL = unreal.EditorAssetLibrary
        self.t0 = time.time()
        self.rows = []                # one per view, for the report
        self.notes = []               # the run's own findings
        self.i = 0
        self.phase = "start"
        self.map = None
        self.first_in_map = True
        self.spawned = []
        self.look = None
        self.handle = None
        self.wait_from = 0.0
        self.frames = 0
        self.idle_frames = 0
        self.probe = None             # (label, fn) that says whether anything is compiling
        self.shot_at = 0.0
        self.shot_file = None
        self.shot_method = ""
        self.row = None
        self.done = False
        self.film = None
        self.cam = None

    # ---- set up once
    def start(self):
        os.makedirs(OUT, exist_ok=True)
        for f in glob.glob(os.path.join(OUT, "*.png")):
            os.remove(f)                # a still from an earlier run must not pass for this one's
        for f in (REPORT, PROGRESS):
            if os.path.exists(f):
                os.remove(f)
        self.note("started %s Riyadh; project %s" % (riyadh(self.t0), PROJECT))
        try:
            self.note("engine %s" % unreal.SystemLibrary.get_engine_version())
        except Exception:
            pass
        self.probe = self._find_probe()
        self.note("settling waits on: %s" % (self.probe[0] if self.probe else
                                             "frames and seconds only (no compile probe answered)"))
        try:
            self.film = _film()
            self.note("SaudAnime::Film read: %s" % ", ".join("%s %g" % kv for kv in sorted(self.film.items())))
        except Exception:
            self.note("SaudAnime::Film NOT read: %s" % last_line(traceback.format_exc()))
        for what, fn in (("editor keeps rendering in the background", self._no_throttle),
                         ("editor game view (no icons)", self._game_view),
                         ("r.HighResScreenshotDelay %d" % HIGHRES_DELAY_FRAMES,
                          lambda: self._console("r.HighResScreenshotDelay %d" % HIGHRES_DELAY_FRAMES))):
            try:
                fn()
                self.note("%s: set" % what)
            except Exception:
                self.note("%s: NOT set (%s)" % (what, last_line(traceback.format_exc())))
        for asset in (LOOK_POST, LOOK_FRAME, LOOK_MPC):
            if not self.EAL.does_asset_exist(asset):
                self.note("%s is not built: the stills are WITHOUT the anime look (setup's anime_look step)" % asset)

    def _find_probe(self):
        for cls in ("ShaderCompiler", "ShaderCompilingManager", "AssetCompilingManager"):
            obj = getattr(unreal, cls, None)
            if obj is None:
                continue
            for meth, busy in (("is_compiling", lambda v: bool(v)),
                               ("get_num_remaining_jobs", lambda v: int(v) > 0),
                               ("get_num_remaining_assets", lambda v: int(v) > 0)):
                f = getattr(obj, meth, None)
                if f is None:
                    continue
                try:
                    busy(f())
                    return ("unreal.%s.%s()" % (cls, meth), lambda f=f, busy=busy: busy(f()))
                except Exception:
                    continue
        return None

    def _no_throttle(self):
        s = unreal.get_default_object(unreal.EditorPerformanceSettings)
        s.set_editor_property("throttle_cpu_when_not_foreground", False)

    def _game_view(self):
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_set_game_view(True)

    def _console(self, cmd):
        unreal.SystemLibrary.execute_console_command(None, cmd)

    def note(self, msg):
        self.notes.append(msg)
        say(msg)

    # ---- per map
    def open_map(self, name):
        path = "%s/%s" % (MAPS, name)
        if not self.EAL.does_asset_exist(path):
            raise LookupError("%s is not built (setup did not make it)" % path)
        try:
            unreal.EditorLoadingAndSavingUtils.load_map(path)
        except Exception:
            unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(path)
        self.map = name
        self.first_in_map = True
        self.look = None
        loaded = self._load_partitioned()
        if loaded:
            self.note("%s: %s" % (name, loaded))
        self._game_view_quiet()

    def _game_view_quiet(self):
        try:
            self._game_view()
        except Exception:
            pass

    def _load_partitioned(self):
        WP = getattr(unreal, "WorldPartitionBlueprintLibrary", None)
        if WP is None:
            return ""
        try:
            descs = WP.get_actor_descs()
        except Exception:
            return ""                   # not a partitioned map
        try:
            guids = [d.get_editor_property("guid") for d in descs]
            WP.load_actors(guids)
            return "partitioned: %d actors loaded" % len(guids)
        except Exception:
            return "partitioned, but loading its actors failed: %s" % last_line(traceback.format_exc())

    def _spawn(self, cls, loc, rot):
        v = unreal.Vector(*loc)
        r = unreal.Rotator(roll=rot[2], pitch=rot[0], yaw=rot[1])
        try:
            a = self.EAS.spawn_actor_from_class(cls, v, r, transient=True)
        except TypeError:
            a = self.EAS.spawn_actor_from_class(cls, v, r)
        if a is None:
            raise RuntimeError("could not spawn %s" % cls)
        self.spawned.append(a)
        return a

    def put_look(self):
        """USaudLookSubsystem::OnWorldBeginPlay, by hand: one unbound volume,
        priority 10, the two materials as blendables, the engine's own
        post-process pinned to SaudAnime::Film. A level's exposure volume
        stays under it, as in the game."""
        post, frame = (unreal.load_asset(p) if self.EAL.does_asset_exist(p) else None for p in (LOOK_POST, LOOK_FRAME))
        if post is None or frame is None:
            return "no look (its materials are not built)"
        vol = self._spawn(unreal.PostProcessVolume, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        vol.set_editor_property("unbound", True)
        vol.set_editor_property("priority", 10.0)
        vol.set_editor_property("blend_weight", 1.0)
        s = vol.get_editor_property("settings")
        s.set_editor_property("weighted_blendables", unreal.WeightedBlendables(array=[
            unreal.WeightedBlendable(weight=1.0, object=post), unreal.WeightedBlendable(weight=1.0, object=frame)]))
        missed = []
        for key, field in FILM_FIELDS:
            if not self.film or key not in self.film:
                missed.append(field)
                continue
            try:
                s.set_editor_property("override_" + field, True)
                s.set_editor_property(field, self.film[key])
            except Exception:
                missed.append(field)
        vol.set_editor_property("settings", s)
        self.look = vol
        return "look on" + (" (not pinned: %s)" % ", ".join(missed) if missed else "")

    def put_camera(self, v):
        name, _map, loc, rot, hfov = v[0], v[1], v[2], v[3], v[4]
        cam = self._spawn(unreal.CineCameraActor, loc, rot)
        c = cam.get_cine_camera_component()
        fb = c.get_editor_property("filmback")
        fb.set_editor_property("sensor_width", SENSOR_MM[0])
        fb.set_editor_property("sensor_height", SENSOR_MM[1])
        c.set_editor_property("filmback", fb)
        c.set_editor_property("current_focal_length", 0.5 * SENSOR_MM[0] / math.tan(math.radians(hfov) * 0.5))
        try:
            fs = c.get_editor_property("focus_settings")
            fs.set_editor_property("focus_method", unreal.CameraFocusMethod.DISABLE)
            c.set_editor_property("focus_settings", fs)
        except Exception:
            self.row["notes"].append("depth of field not turned off: %s" % last_line(traceback.format_exc()))
        try:
            c.set_field_of_view(hfov)
        except Exception:
            pass
        try:
            ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
            ues.set_level_viewport_camera_info(unreal.Vector(*loc), unreal.Rotator(roll=rot[2], pitch=rot[0], yaw=rot[1]))
        except Exception:
            self.row["notes"].append("the editor viewport was not moved to the view: %s" % last_line(traceback.format_exc()))
        return cam

    def put_saud(self, extra):
        if not self.EAL.does_asset_exist(SAUD_MESH):
            return "Saud is not imported (%s): the shot is of where he would stand" % SAUD_MESH
        mesh = unreal.load_asset(SAUD_MESH)
        a = self._spawn(unreal.SkeletalMeshActor, extra["saud_feet"], (0.0, extra["saud_yaw"] - 90.0, 0.0))
        comp = a.get_editor_property("skeletal_mesh_component")
        try:
            comp.set_skeletal_mesh_asset(mesh)
        except Exception:
            comp.set_skeletal_mesh(mesh)
        return "Saud's mesh stood at his feet, in his bind pose (no clip plays in the editor)"

    def clear(self):
        for a in self.spawned:
            try:
                self.EAS.destroy_actor(a)
            except Exception:
                pass
        self.spawned = []
        self.look = None

    # ---- the shot
    def compiling(self):
        if not self.probe:
            return False
        try:
            return self.probe[1]()
        except Exception:
            return False

    def shoot(self, v, cam):
        name = v[0]
        path = os.path.join(OUT, name + ".png")
        self.shot_file = path
        self.shot_at = time.time()
        try:
            res = unreal.AutomationLibrary.take_high_res_screenshot(RES[0], RES[1], path, camera=cam, force_game_view=True)
            self.shot_method = "take_high_res_screenshot(camera)"
        except TypeError:
            res = unreal.AutomationLibrary.take_high_res_screenshot(RES[0], RES[1], path, camera=cam)
            self.shot_method = "take_high_res_screenshot(camera)"
        except Exception:
            self.row["notes"].append("take_high_res_screenshot failed (%s); HighResShot from the viewport instead"
                                     % last_line(traceback.format_exc()))
            self._console('HighResShot %dx%d filename="%s"' % (RES[0], RES[1], path))
            self.shot_method = "HighResShot (viewport, its own field of view)"
            res = True
        if res is False:
            raise RuntimeError("take_high_res_screenshot refused the request")

    def landed(self):
        """The screenshot, wherever the engine put it, moved to OUT."""
        name = os.path.splitext(os.path.basename(self.shot_file))[0]
        mine = re.compile(re.escape(name) + r"([_-]?\d+)?\.png$", re.I)
        for d in SHOT_DIRS:
            for f in glob.glob(os.path.join(d, "**", name + "*.png"), recursive=True):
                if not mine.match(os.path.basename(f)):
                    continue            # island_landing.png is not island's
                if os.path.getmtime(f) >= self.shot_at - 1.0 and os.path.getsize(f) > 0:
                    size = os.path.getsize(f)
                    time.sleep(0.2)
                    if os.path.getsize(f) != size:
                        return False            # still being written
                    if os.path.normpath(f) != os.path.normpath(self.shot_file):
                        shutil.move(f, self.shot_file)
                    return True
        return False

    # ---- the report
    def progress(self):
        with open(PROGRESS, "w", encoding="utf-8") as f:
            f.write("%s Riyadh: %d of %d views tried\n" % (riyadh(), len(self.rows), len(VIEWS)))
            for r in self.rows:
                f.write("%-24s %-8s %s\n" % (r["name"], r["result"], "; ".join(r["notes"])))

    def report(self, why):
        lines = ["SAUD render kit -- render report",
                 "started %s Riyadh, ended %s Riyadh (%s)" % (riyadh(self.t0), riyadh(), why),
                 "project: %s" % PROJECT, ""]
        lines += ["run: " + n for n in self.notes]
        lines.append("")
        shot = [r for r in self.rows if r["result"] == "ok"]
        lines.append("%d of %d views rendered to %s (1920x1080)" % (len(shot), len(VIEWS), OUT))
        lines.append("")
        lines.append("%-24s %-16s %-8s %7s  %-36s %s" % ("view", "map", "result", "seconds", "compare with Docs/renders/", "notes"))
        tried = {r["name"] for r in self.rows}
        for r in self.rows:
            lines.append("%-24s %-16s %-8s %7.0f  %-36s %s" % (r["name"], r["map"], r["result"], r["seconds"],
                                                              r["compare"], "; ".join(r["notes"])))
        for v in VIEWS:
            if v[0] not in tried:
                lines.append("%-24s %-16s %-8s %7s  %-36s %s" % (v[0], v[1], "not-run", "-", v[5], "out of time"))
        lines.append("")
        lines.append("Where each camera comes from:")
        for v in VIEWS:
            lines.append("  %-24s %s" % (v[0], v[6]))
        with open(REPORT, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        say("report: %s" % REPORT)

    # ---- the editor's tick
    def tick(self, dt):
        if self.done:
            return
        try:
            self._tick()
        except Exception:
            # a fault in the machine itself, not in one view: report and go
            self.note("the render loop broke: %s" % traceback.format_exc())
            self.finish("the render loop broke")

    def _view(self):
        return VIEWS[self.i]

    def _next(self, result, note=None):
        if note:
            self.row["notes"].append(note)
        self.row["result"] = result
        self.row["seconds"] = time.time() - self.row["t0"]
        self.rows.append(self.row)
        say("%s: %s %s" % (self.row["name"], result, "; ".join(self.row["notes"])))
        self.progress()
        self.clear()
        self.i += 1
        self.phase = "view"

    def _tick(self):
        now = time.time()
        if self.phase == "start":
            self.start()
            self.phase = "view"
            return
        if now - self.t0 > BUDGET_S and self.phase != "wait_file":
            self.finish("out of time after %.0f minutes" % ((now - self.t0) / 60.0))
            return
        if self.phase == "view":
            if self.i >= len(VIEWS):
                self.finish("every view tried")
                return
            v = self._view()
            self.row = dict(name=v[0], map=v[1], compare=v[5], result="?", seconds=0.0, notes=[], t0=now)
            try:
                if self.map != v[1]:
                    self.clear()
                    self.open_map(v[1])
                self.row["notes"].append(self.put_look())
                self.cam = self.put_camera(v)
                if v[7].get("saud_feet"):
                    self.row["notes"].append(self.put_saud(v[7]))
            except LookupError as e:
                self._next("no-map", str(e))
                return
            except Exception:
                self._next("failed", "setting the view up: %s" % last_line(traceback.format_exc()))
                return
            self.phase = "settle"
            self.wait_from = now
            self.frames = 0
            self.idle_frames = 0
            return
        if self.phase == "settle":
            self.frames += 1
            floor = FIRST_SETTLE_S if self.first_in_map else SETTLE_S
            waited = now - self.wait_from
            busy = self.compiling()
            if waited > MAX_SETTLE_S:
                self.row["notes"].append("still compiling after %.0f min; shot anyway" % (MAX_SETTLE_S / 60))
                busy = False
                self.idle_frames = SETTLE_FRAMES
            if waited < floor or busy:
                self.idle_frames = 0
                return
            self.idle_frames += 1
            if self.idle_frames < SETTLE_FRAMES:
                return
            self.row["notes"].append("settled %.0f s, %d frames" % (waited, self.frames))
            self.first_in_map = False
            try:
                self.shoot(self._view(), self.cam)
            except Exception:
                self._next("failed", "the screenshot: %s" % last_line(traceback.format_exc()))
                return
            self.phase = "wait_file"
            return
        if self.phase == "wait_file":
            if self.landed():
                self._next("ok", "%s -> %s" % (self.shot_method, os.path.basename(self.shot_file)))
            elif now - self.shot_at > SHOT_WAIT_S:
                self._next("failed", "%s: no file after %.0f s" % (self.shot_method, SHOT_WAIT_S))
            return

    def finish(self, why):
        if self.done:
            return
        self.done = True
        try:
            self.clear()
        except Exception:
            pass
        try:
            self.report(why)
        except Exception:
            say("could not write the report: %s" % traceback.format_exc())
        try:
            if self.handle is not None:
                unreal.unregister_slate_post_tick_callback(self.handle)
        except Exception:
            pass
        say("done (%s); quitting the editor" % why)
        unreal.SystemLibrary.quit_editor()


KIT = Kit()
KIT.handle = unreal.register_slate_post_tick_callback(KIT.tick)
say("render_views.py: %d views queued; the editor's ticks do the rest" % len(VIEWS))
