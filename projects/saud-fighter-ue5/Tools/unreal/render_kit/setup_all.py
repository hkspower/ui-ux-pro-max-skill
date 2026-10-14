"""
SAUD render kit -- setup_all.py. Runs INSIDE the Unreal editor (import
unreal); RENDER_SAUD.bat starts it headless, once:

    UnrealEditor-Cmd.exe SaudFighter.uproject -run=pythonscript
        -script="<this file>" -unattended -nosplash -stdout -FullStdOutLogOutput

It runs the project's own editor tools in the order the maps need them,
each in its own try/except so one failure does not stop the rest, and
writes Saved/RenderKit/setup_report.txt (step, ok/failed, seconds,
traceback) after EVERY step, so a crash part-way still leaves a report.
At the very end it saves everything under /Game and writes
Saved/RenderKit/setup_done.txt, which tells RENDER_SAUD.bat that setup ran
to its end (whatever failed in it) and need not run again.

Asked 2026-10-14 (Riyadh) as "render with unreal engine 5"; settled as a
render kit the author runs on his own Windows PC. Written and dry-run here
against a mock `unreal` module only: no engine has ever run this file.

THE ORDER, AND WHY (each tool called the way its own file says it is run):
   1 data tables    every DT_* in Content/Data into /Game/Data on the row
                    struct its C++ declares (README Setup step 3). Nothing
                    in Tools imports them except build_monkey_island_level
                    (its own two), and every level builder wires its
                    directors to DT_Stages / DT_Fighters / DT_Attacks only
                    if they are already in /Game/Data -- so they go first.
   2 the men        Content/Models/{Saud,Thug,Brawler,Boss,Saqr,Zayos}.fbx
                    into /Game/Models: nothing in Tools imports them
                    (motion_package.py says "import Saud.fbx first"). Saud
                    first, so Saud_Skeleton exists; the rest on his
                    skeleton (CLAUDE.md: one skeleton, the 62 bones). The
                    Monkey and the Gorilla are imported by the island's
                    level builder (step 15), not here.
   3 surfaces.py    build(): every texture under Content/Textures imported
                    and set (sRGB / compression from its role), M_Surface,
                    an MI per set, the MI put on every mesh slot that names
                    its set -- after the men, so their slots get theirs.
                    The souq's, the city's and the island's meshes are
                    imported by their level builders, which run build()
                    again themselves (build_souq.import_meshes,
                    build_world.import_city / import_island).
   4 motion_package import_mocap(): the five mocap clips onto Saud_Skeleton
                    (needs step 2). The --gasp half needs Epic's sample
                    migrated in by hand and is not run.
   5 data assets    build_data_assets.py, run as a script (it builds at
                    import, "__name__ == '__main__' or True").
   6 anime_look.py  build_in_editor(): MPC_Anime, M_Anime_Post, M_Anime_Frame
                    -- the look every still is drawn through.
   7 portal.py      build_in_editor(): M_Portal and its two instances, before
                    the levels that hang portals on their gates (the gates'
                    own import_meshes() would build it too if missing).
   8 camera_fade.py a library with no editor entry of its own: surfaces.build
                    and build_world._world_materials call add_fade(). This
                    step reads its slot from SaudCamera.h and makes sure
                    M_Surface carries the fade (add_fade() is a no-op when
                    it already does).
   9 build_world.py  L_AlHalqa_World, the map the game plays on, run as a
                    script (exec, as its docstring says); it imports the
                    souq's, the city's, the portals' and the boat's meshes
                    itself and calls park_cars.build_in_editor (the cars'
                    FBX are not built -- the Unity tool has never run -- so
                    it logs that and places none).
  10 build_prologue.py   L_Prologue, as a script.
  11 build_levels.py     the nine standalone stage levels, as a script.
  12 build_souq.py       build_in_editor(plan()): furnishes L_SouqAlDawar
                    (step 11's) with the modelled souq -- the level the
                    Blender souq previews show. Its main() is NOT used in
                    the editor: it draws Docs/souq-map.png with PIL and its
                    check() runs build_levels.py in a subprocess through
                    sys.executable, which inside Unreal is the editor itself.
  13 build_island.py     L_JaziratAlHajar_Island, as a script.
  14 build_monkey_island_level.py   L_MonkeyIsland, as a script (main()):
                    imports numpy at the top, so it needs the numpy
                    RENDER_SAUD.bat installs into Saved/RenderKitPython.
  15 save           EditorAssetLibrary.save_directory('/Game') and the dirty
                    maps.
NOT RUN, on purpose: Tools/fab/lay_out_world.py (it lays the game over a Fab
map opened in the editor; build_world.py does not use it); park_cars.py on
its own (build_world runs it); the hand-made clips in Content/Animation/
{Saud,Street,Bosses} (no tool imports them and no still needs them).

UNVERIFIED ENGINE PYTHON APIs used in this file (none could be run here;
what each is assumed to do):
  unreal.Paths.project_dir / project_saved_dir / engine_dir
      -> the project's, its Saved's and the engine's folders, possibly
         relative; unreal.Paths.convert_relative_path_to_full makes them full
  unreal.SystemLibrary.get_engine_version() -> "5.4.x-..." text
  unreal.SystemLibrary.get_command_line() -> this process's command line
         (used only to tell the commandlet from the full editor)
  unreal.SystemLibrary.quit_editor() -> closes the full editor (not called
         in the commandlet)
  unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
  unreal.AssetImportTask with editor properties filename, destination_path,
         destination_name, automated, save, replace_existing, factory,
         options
  unreal.CSVImportFactory, its editor property automated_import_settings
         (a CSVImportSettings struct, read, changed and written back) and
         that struct's import_row_struct; that the same factory imports a
         .json DataTable
  unreal.<RowStruct>.static_struct() -> the ScriptStruct (else
         unreal.load_object(None, "/Script/SaudFighter.<RowStruct>"))
  unreal.DataTableFunctionLibrary.get_data_table_row_names(table) -> names
  unreal.FbxImportUI: import_mesh, import_as_skeletal, import_animations,
         import_materials, import_textures, mesh_type_to_import, skeleton;
         unreal.FBXImportType.FBXIT_SKELETAL_MESH; and that a skeletal FBX
         imported as /Game/Models/Saud makes /Game/Models/Saud_Skeleton
         (motion_package.py assumes the same name)
  unreal.EditorAssetLibrary.does_asset_exist / load_asset / save_directory
         (path, only_if_is_dirty, recursive) / save_loaded_asset
  unreal.EditorLoadingAndSavingUtils.save_dirty_packages(save_map_packages,
         save_content_packages)
  unreal.MaterialEditingLibrary.recompile_material
And, outside the engine's API: that the engine's bundled Python is 3.11
without numpy or PIL (hence the .bat's pip step), and that inside Unreal
sys.executable names UnrealEditor(-Cmd).exe (hence the guard below).
"""

import importlib.util
import os
import runpy
import sys
import time
import traceback

import unreal

STARTED = time.time()


# ------------------------------------------------------------------ paths
def _full(p):
    try:
        return os.path.normpath(unreal.Paths.convert_relative_path_to_full(p))
    except Exception:
        return os.path.normpath(os.path.abspath(p))


def _kit_dir():
    f = globals().get("__file__")
    if f and os.path.exists(f):
        return os.path.dirname(os.path.abspath(f))
    return os.path.join(_full(unreal.Paths.project_dir()), "Tools", "unreal", "render_kit")


KIT = _kit_dir()
PROJECT = os.path.normpath(os.path.join(KIT, "..", "..", ".."))
if not os.path.exists(os.path.join(PROJECT, "SaudFighter.uproject")):
    PROJECT = _full(unreal.Paths.project_dir())
try:
    SAVED = _full(unreal.Paths.project_saved_dir())
except Exception:
    SAVED = os.path.join(PROJECT, "Saved")
OUT = os.path.join(SAVED, "RenderKit")
REPORT = os.path.join(OUT, "setup_report.txt")
DONE = os.path.join(OUT, "setup_done.txt")
PY_EXTRA = os.path.join(SAVED, "RenderKitPython")      # numpy, pillow: RENDER_SAUD.bat / RENDER_SAUD_MAC.command install them here
TOOLS = os.path.join(PROJECT, "Tools")
DATA = os.path.join(PROJECT, "Content", "Data")
MODELS = os.path.join(PROJECT, "Content", "Models")

# Every table in Content/Data, the row struct its C++ declares
# (USTRUCT ... : public FTableRowBase; the Python name drops the F), and where.
TABLES = (
    ("DT_Attacks.csv", "AttackDef", "Combat/SaudTypes.h"),
    ("DT_Fighters.csv", "FighterDef", "Combat/SaudTypes.h"),
    ("DT_Stages.json", "StageDef", "Combat/SaudTypes.h"),
    ("DT_Talents.csv", "TalentDef", "Combat/SaudTypes.h"),
    ("DT_GateKinds.csv", "GateKindDef", "Combat/SaudTypes.h"),
    ("DT_Upgrades.csv", "UpgradeDef", "Combat/SaudTypes.h"),
    ("DT_Levels.csv", "LevelDef", "Combat/SaudTypes.h"),
    ("DT_Colors.csv", "ColorDef", "Combat/SaudTypes.h"),
    ("DT_LookColors.csv", "ColorDef", "Combat/SaudTypes.h"),
    ("DT_Weapons.csv", "WeaponDef", "Combat/SaudTypes.h"),
    ("DT_Prologue.json", "StageDef", "Combat/SaudTypes.h (build_prologue wires it as the director's stage table)"),
    ("DT_IslandFighters.csv", "FighterDef", "Combat/SaudTypes.h"),
    ("DT_MonkeyIsland.json", "StageDef", "Combat/SaudTypes.h"),
    ("DT_Sounds.csv", "SoundCueDef", "Game/SaudAudioSubsystem.h"),
    ("DT_SystemLines.json", "SaudSystemLine", "Game/SaudSystemSubsystem.h"),
)
NOT_TABLES = {
    "DT_World.json": "one object (StartArea, Areas), not rows; the level builders read it from disk",
}
MEN = ("Saud", "Thug", "Brawler", "Boss", "Saqr", "Zayos")

RESULTS = []          # dict(n, name, ok, seconds, tool, entry, notes, error)


# ----------------------------------------------------------------- helpers
def riyadh(t=None):
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime((time.time() if t is None else t) + 3 * 3600))


def say(msg):
    print("[render kit] " + msg)
    sys.stdout.flush()


def _load(path, name):
    """A tool as a module, without running a __main__ block."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _as_script(path):
    """A tool run the way its docstring says -- exec'd as a script -- with
    its own __file__ and a clean argv, so no flag of ours reaches it."""
    argv = sys.argv[:]
    sys.argv = [path]
    try:
        runpy.run_path(path, run_name="__main__")
    finally:
        sys.argv = argv


def _guard_executable():
    """Inside Unreal sys.executable is the editor, so a tool that starts
    `sys.executable -c ...` would start a second editor. Point it at the
    engine's own Python when that exists (Win64/python.exe on Windows,
    Mac/bin/python3 on a Mac, Linux/bin/python3 on Linux)."""
    exe = sys.executable or ""
    if not os.path.basename(exe).lower().startswith("unreal"):
        return "sys.executable is %s" % exe
    if sys.platform.startswith("win"):
        rel = ("Win64", "python.exe")
    elif sys.platform == "darwin":
        rel = ("Mac", "bin", "python3")
    else:
        rel = ("Linux", "bin", "python3")
    try:
        py = os.path.join(_full(unreal.Paths.engine_dir()), "Binaries", "ThirdParty", "Python3", *rel)
    except Exception:
        py = ""
    if py and os.path.exists(py):
        sys.executable = py
        return "sys.executable was the editor; now %s" % py
    return "sys.executable is the editor (%s) and no Python was found beside the engine" % exe


def _in_commandlet():
    try:
        return "-run=pythonscript" in str(unreal.SystemLibrary.get_command_line()).lower()
    except Exception:
        return True          # the .bat runs setup as a commandlet; do not try to quit anything


def write_report(final=False):
    os.makedirs(OUT, exist_ok=True)
    lines = ["SAUD render kit -- setup report",
             "started %s Riyadh, %s %s" % (riyadh(STARTED), "finished" if final else "so far", riyadh()),
             "project: %s" % PROJECT]
    try:
        lines.append("engine: %s" % unreal.SystemLibrary.get_engine_version())
    except Exception:
        lines.append("engine: (version not readable)")
    lines.append("python: %s" % sys.version.split()[0])
    for mod in ("numpy", "PIL"):
        try:
            __import__(mod)
            lines.append("%s: present" % mod)
        except Exception:
            lines.append("%s: MISSING (the monkey island's level builder needs numpy)" % mod if mod == "numpy"
                         else "%s: missing (not needed by any step run here)" % mod)
    lines.append("")
    lines.append("%-3s %-30s %-7s %8s  %s" % ("#", "step", "result", "seconds", "tool : entry"))
    for r in RESULTS:
        lines.append("%-3d %-30s %-7s %8.1f  %s : %s" % (r["n"], r["name"], "ok" if r["ok"] else "FAILED",
                                                         r["seconds"], r["tool"], r["entry"]))
    failed = [r for r in RESULTS if not r["ok"]]
    lines.append("")
    lines.append("%d of %d steps ok%s" % (len(RESULTS) - len(failed), len(RESULTS),
                                          "" if final else " (still running)"))
    lines.append("'ok' means the step raised nothing; what a tool only logged (unreal.log_error) is in the editor log.")
    for r in RESULTS:
        if r["notes"] or r["error"]:
            lines.append("")
            lines.append("--- %d %s" % (r["n"], r["name"]))
            for n in r["notes"]:
                lines.append("    " + n)
            if r["error"]:
                lines.append(r["error"].rstrip())
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def run_step(n, name, tool, entry, fn):
    say("STEP %d: %s (%s : %s)" % (n, name, tool, entry))
    r = dict(n=n, name=name, tool=tool, entry=entry, ok=False, seconds=0.0, notes=[], error="")
    t0 = time.time()
    try:
        out = fn(r["notes"])
        r["ok"] = out is not False
    except BaseException:          # SystemExit too: some tools sys.exit() on a failed check
        r["error"] = traceback.format_exc()
        say("step %d FAILED, carrying on:\n%s" % (n, r["error"]))
    r["seconds"] = time.time() - t0
    RESULTS.append(r)
    say("step %d %s in %.0f s" % (n, "ok" if r["ok"] else "FAILED", r["seconds"]))
    write_report()
    return r["ok"]


# ------------------------------------------------------------------- steps
def _struct(name):
    py = getattr(unreal, name, None)
    if py is not None and hasattr(py, "static_struct"):
        return py.static_struct()
    obj = unreal.load_object(None, "/Script/SaudFighter.%s" % name)
    if obj is None:
        raise RuntimeError("row struct F%s is not in the SaudFighter module (did the C++ build?)" % name)
    return obj


def step_tables(notes):
    AT = unreal.AssetToolsHelpers.get_asset_tools()
    EAL = unreal.EditorAssetLibrary
    known = {t[0] for t in TABLES} | set(NOT_TABLES)
    for f in sorted(os.listdir(DATA)):
        if f.startswith("DT_") and f not in known:
            notes.append("%s: no row struct known for it, NOT imported" % f)
    for f, why in NOT_TABLES.items():
        notes.append("%s: not imported -- %s" % (f, why))
    bad = 0
    for f, struct_name, where in TABLES:
        asset = os.path.splitext(f)[0]
        try:
            struct = _struct(struct_name)
            t = unreal.AssetImportTask()
            t.set_editor_property("filename", os.path.join(DATA, f))
            t.set_editor_property("destination_path", "/Game/Data")
            t.set_editor_property("destination_name", asset)
            t.set_editor_property("automated", True)
            t.set_editor_property("save", True)
            t.set_editor_property("replace_existing", True)
            fac = unreal.CSVImportFactory()
            s = fac.get_editor_property("automated_import_settings")
            s.set_editor_property("import_row_struct", struct)
            fac.set_editor_property("automated_import_settings", s)
            t.set_editor_property("factory", fac)
            AT.import_asset_tasks([t])
            path = "/Game/Data/%s" % asset
            if not EAL.does_asset_exist(path):
                raise RuntimeError("the import made no %s" % path)
            rows = "?"
            try:
                rows = len(unreal.DataTableFunctionLibrary.get_data_table_row_names(unreal.load_asset(path)))
            except Exception:
                pass
            notes.append("%s -> %s on F%s (%s): %s rows" % (f, path, struct_name, where, rows))
            if rows == 0:
                bad += 1
                notes.append("    ^ no rows: the columns did not match F%s -- see the editor log" % struct_name)
        except Exception:
            bad += 1
            notes.append("%s on F%s FAILED: %s" % (f, struct_name, traceback.format_exc().strip().splitlines()[-1]))
    if bad:
        raise RuntimeError("%d of %d tables did not import cleanly (each above)" % (bad, len(TABLES)))


def _fbx_task(path, dest, skeleton=None):
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", True)
    ui.set_editor_property("import_animations", False)
    ui.set_editor_property("import_materials", True)       # the slots keep their names; surfaces.build sets them
    ui.set_editor_property("import_textures", False)       # surfaces.build imports every texture, set from its role
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    if skeleton is not None:
        ui.set_editor_property("skeleton", skeleton)
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", path)
    t.set_editor_property("destination_path", dest)
    t.set_editor_property("automated", True)
    t.set_editor_property("save", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("options", ui)
    return t


def step_men(notes):
    AT = unreal.AssetToolsHelpers.get_asset_tools()
    EAL = unreal.EditorAssetLibrary
    AT.import_asset_tasks([_fbx_task(os.path.join(MODELS, "Saud.fbx"), "/Game/Models")])
    if not EAL.does_asset_exist("/Game/Models/Saud"):
        raise RuntimeError("Saud.fbx did not import to /Game/Models/Saud")
    skel_path = "/Game/Models/Saud_Skeleton"
    skel = unreal.load_asset(skel_path) if EAL.does_asset_exist(skel_path) else None
    notes.append("Saud -> /Game/Models/Saud, skeleton %s" % (skel_path if skel else "NOT FOUND at " + skel_path))
    missing = []
    for man in MEN[1:]:
        AT.import_asset_tasks([_fbx_task(os.path.join(MODELS, man + ".fbx"), "/Game/Models", skeleton=skel)])
        ok = EAL.does_asset_exist("/Game/Models/%s" % man)
        notes.append("%s -> /Game/Models/%s%s" % (man, man, "" if ok else "  NOT IMPORTED"))
        if not ok:
            missing.append(man)
    if missing or skel is None:
        raise RuntimeError("not imported: %s" % ", ".join(missing + ([] if skel else ["Saud_Skeleton"])))


def step_surfaces(notes):
    _load(os.path.join(TOOLS, "look", "surfaces.py"), "surfaces").build()


def step_mocap(notes):
    got = _load(os.path.join(TOOLS, "unreal", "motion_package.py"), "motion_package").import_mocap()
    notes.append("clips in /Game/Animation/Saud: %s" % ", ".join(got or ["none"]))
    if not got:
        raise RuntimeError("no mocap clip imported")


def step_data_assets(notes):
    _as_script(os.path.join(TOOLS, "levels", "build_data_assets.py"))


def step_anime_look(notes):
    _load(os.path.join(TOOLS, "look", "anime_look.py"), "anime_look").build_in_editor()


def step_portal(notes):
    look = os.path.join(TOOLS, "look")
    if look not in sys.path:
        sys.path.insert(0, look)
    _load(os.path.join(look, "portal.py"), "portal").build_in_editor()


def step_camera_fade(notes):
    CF = _load(os.path.join(TOOLS, "look", "camera_fade.py"), "camera_fade")
    slot = CF.slot()
    if slot is None:
        raise RuntimeError("camera_fade.slot() found no FadeDataIndex in SaudCamera.h")
    notes.append("the fade reads custom primitive data slot %d (SaudCamera.h)" % slot)
    path = "/Game/Materials/Surface/M_Surface"
    if not unreal.EditorAssetLibrary.does_asset_exist(path):
        raise RuntimeError("%s is not built (step 3), so there is nothing to fade" % path)
    m = unreal.load_asset(path)
    if CF.add_fade(m):
        unreal.MaterialEditingLibrary.recompile_material(m)
        unreal.EditorAssetLibrary.save_loaded_asset(m)
        notes.append("M_Surface did not have the fade; added")
    else:
        notes.append("M_Surface already has the fade (surfaces.build added it)")


def _map_step(script, level):
    def fn(notes):
        _as_script(os.path.join(TOOLS, *script))
        if not unreal.EditorAssetLibrary.does_asset_exist(level):
            raise RuntimeError("the script ran but %s does not exist" % level)
        notes.append("%s exists" % level)
    return fn


def step_souq(notes):
    B = _load(os.path.join(TOOLS, "blender", "build_souq.py"), "build_souq")
    B.build_in_editor(B.plan())
    notes.append("furnished /Game/Maps/L_SouqAlDawar with the modelled souq")


def step_save(notes):
    EAL = unreal.EditorAssetLibrary
    ok = EAL.save_directory("/Game", only_if_is_dirty=True, recursive=True)
    notes.append("save_directory('/Game'): %s" % ok)
    try:
        notes.append("save_dirty_packages: %s" % unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True))
    except Exception:
        notes.append("save_dirty_packages: %s" % traceback.format_exc().strip().splitlines()[-1])
    return bool(ok)


STEPS = (
    ("data tables", "render_kit/setup_all.py", "step_tables (CSVImportFactory, README Setup 3)", step_tables),
    ("the men (FBX)", "render_kit/setup_all.py", "step_men (Content/Models/*.fbx)", step_men),
    ("textures and surfaces", "Tools/look/surfaces.py", "build()", step_surfaces),
    ("mocap clips", "Tools/unreal/motion_package.py", "import_mocap()", step_mocap),
    ("data assets", "Tools/levels/build_data_assets.py", "run as a script", step_data_assets),
    ("the anime look", "Tools/look/anime_look.py", "build_in_editor()", step_anime_look),
    ("the portals", "Tools/look/portal.py", "build_in_editor()", step_portal),
    ("the camera fade", "Tools/look/camera_fade.py", "slot(), add_fade(M_Surface)", step_camera_fade),
    ("L_AlHalqa_World", "Tools/levels/build_world.py", "run as a script",
     _map_step(("levels", "build_world.py"), "/Game/Maps/L_AlHalqa_World")),
    ("L_Prologue", "Tools/levels/build_prologue.py", "run as a script",
     _map_step(("levels", "build_prologue.py"), "/Game/Maps/L_Prologue")),
    ("the nine stage levels", "Tools/levels/build_levels.py", "run as a script",
     _map_step(("levels", "build_levels.py"), "/Game/Maps/L_SouqAlDawar")),
    ("the souq furnished", "Tools/blender/build_souq.py", "build_in_editor(plan())", step_souq),
    ("L_JaziratAlHajar_Island", "Tools/levels/build_island.py", "run as a script",
     _map_step(("levels", "build_island.py"), "/Game/Maps/L_JaziratAlHajar_Island")),
    ("L_MonkeyIsland", "Tools/levels/build_monkey_island_level.py", "run as a script (main())",
     _map_step(("levels", "build_monkey_island_level.py"), "/Game/Maps/L_MonkeyIsland")),
    ("save everything", "render_kit/setup_all.py", "save_directory('/Game')", step_save),
)


def main():
    os.makedirs(OUT, exist_ok=True)
    if os.path.exists(DONE):
        os.remove(DONE)
    if os.path.isdir(PY_EXTRA) and PY_EXTRA not in sys.path:
        sys.path.insert(0, PY_EXTRA)
    say("setup_all.py, %s Riyadh; project %s" % (riyadh(), PROJECT))
    say(_guard_executable())
    write_report()
    for n, (name, tool, entry, fn) in enumerate(STEPS, 1):
        run_step(n, name, tool, entry, fn)
    write_report(final=True)
    failed = [r["name"] for r in RESULTS if not r["ok"]]
    with open(DONE, "w", encoding="utf-8") as f:
        f.write("setup ran to its end %s Riyadh; %d of %d steps failed%s\n" % (
            riyadh(), len(failed), len(RESULTS), (": " + ", ".join(failed)) if failed else ""))
    say("setup done: %d of %d steps ok; report %s" % (len(RESULTS) - len(failed), len(RESULTS), REPORT))
    if not _in_commandlet():
        unreal.SystemLibrary.quit_editor()


main()
