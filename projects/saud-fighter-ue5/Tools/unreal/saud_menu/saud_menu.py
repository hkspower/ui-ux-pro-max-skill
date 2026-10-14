"""The SAUD menu, in the Unreal editor's top bar.

Inside the editor, the same work the render kit's launchers do from outside:
set the project up, rebuild one map, render the 24 views, and look at what
was made. Nothing here is a second copy of a tool -- every item runs the
project's own script, as the kit does, with SAUD_KEEP_EDITOR set so the
script leaves the editor open when it is done.

Loaded by Content/Python/init_unreal.py when the editor starts (it needs the
Python Editor Script Plugin, which SaudFighter.uproject enables). Items run
on demand only; nothing runs at start-up but the menu's own registration.

Written 2026-10-14 (Riyadh). Never run inside Unreal: the ToolMenus calls are
UE 5.4's as remembered; see the notes at the bottom of this file.
"""

import os
import subprocess
import sys

import unreal

OWNER = "SAUDMenuOwner"
MENU = "SAUDMenu"


def _project():
    try:
        return os.path.normpath(unreal.Paths.project_dir()).rstrip(os.sep)
    except Exception:
        return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


PROJECT = _project()
TOOLS = os.path.join(PROJECT, "Tools")
KIT = os.path.join(TOOLS, "unreal", "render_kit")
SAVED_KIT = os.path.join(PROJECT, "Saved", "RenderKit")

# the map builders, in the order the kit runs them (render_kit/setup_all.py)
MAPS = (
    ("L_AlHalqa_World (the open world)", os.path.join(TOOLS, "levels", "build_world.py")),
    ("L_Prologue (the gym)", os.path.join(TOOLS, "levels", "build_prologue.py")),
    ("the nine stage levels", os.path.join(TOOLS, "levels", "build_levels.py")),
    ("L_JaziratAlHajar_Island", os.path.join(TOOLS, "levels", "build_island.py")),
    ("L_MonkeyIsland", os.path.join(TOOLS, "levels", "build_monkey_island_level.py")),
)


def _say(msg):
    unreal.log("[SAUD] %s" % msg)


def _run_script(path, label):
    """Run one of the project's scripts inside this editor, as the kit does,
    with SAUD_KEEP_EDITOR set so it does not quit the editor."""
    if not os.path.exists(path):
        _say("%s: %s is missing; nothing run" % (label, path))
        return False
    _say("%s: running %s" % (label, os.path.relpath(path, PROJECT)))
    globs = {"__name__": "__main__", "__file__": path, "SAUD_KEEP_EDITOR": True}
    try:
        with open(path, encoding="utf-8") as f:
            code = compile(f.read(), path, "exec")
        exec(code, globs)
        _say("%s: finished" % label)
        return True
    except SystemExit as exc:
        _say("%s: stopped with %s (see the log above)" % (label, exc))
        return False
    except Exception as exc:
        _say("%s: FAILED: %s" % (label, exc))
        return False


def _open_path(path):
    if not os.path.exists(path):
        _say("nothing to open at %s yet" % path)
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
    elif sys.platform.startswith("win"):
        os.startfile(path)  # noqa: S606 -- the editor user's own folder
    else:
        subprocess.Popen(["xdg-open", path])


# ----------------------------------------------------------------------------
# the items. Each is a module-level function, called by name from the menu.

def setup_everything():
    """Set the project up: the data tables, the men, the look, the portals,
    the maps, the souq -- render_kit/setup_all.py's 15 steps."""
    _run_script(os.path.join(KIT, "setup_all.py"), "setup")


def render_views():
    """The 24 stills, through the look -- render_kit/render_views.py. It takes
    minutes; the editor's window stays open, and the report is in Saved/RenderKit."""
    _run_script(os.path.join(KIT, "render_views.py"), "render")


def rebuild_map(index):
    label, path = MAPS[int(index)]
    _run_script(path, "map %s" % label)


def open_render_folder():
    _open_path(SAVED_KIT)


def open_setup_report():
    report = os.path.join(SAVED_KIT, "setup_report.txt")
    if os.path.exists(report):
        _open_path(report)
    else:
        _say("no setup report yet: run Set up everything first")


def check_cars_and_gates():
    """The checks that need no engine, run with the Python on this Mac's PATH
    (the editor's own Python cannot be trusted to be python3)."""
    python = "python3"
    for script in (os.path.join(TOOLS, "levels", "park_cars.py"),
                   os.path.join(TOOLS, "blender", "build_gates.py")):
        args = [script, "--check"]
        try:
            out = subprocess.run([python] + args, cwd=PROJECT, capture_output=True, text=True, timeout=600)
            tail = (out.stdout or out.stderr).strip().splitlines()[-1:] or [""]
            _say("%s --check: exit %d: %s" % (os.path.basename(script), out.returncode, tail[0]))
        except Exception as exc:
            _say("%s --check could not run: %s" % (os.path.basename(script), exc))


# ----------------------------------------------------------------------------
# the menu

def _command(entry_name, label, call, tooltip=""):
    entry = unreal.ToolMenuEntry(name=entry_name, type=unreal.MultiBlockType.MENU_ENTRY)
    entry.set_label(label)
    entry.set_tool_tip(tooltip or label)
    entry.set_string_command(unreal.ToolMenuStringCommandType.PYTHON, custom_type="",
                             string="import saud_menu; saud_menu.%s" % call)
    return entry


def register():
    """Add the SAUD menu to the editor's top bar. Safe to call twice."""
    menus = unreal.ToolMenus.get()
    try:
        menus.remove_menu(MENU)
    except Exception:
        pass
    main = menus.find_menu("LevelEditor.MainMenu")
    if main is None:
        _say("the level editor's main menu was not found; no SAUD menu")
        return False
    sub = main.add_sub_menu(OWNER, "", MENU, "SAUD")
    sub.add_menu_entry("Project", _command("SAUD.Setup", "Set up everything (once)", "setup_everything()",
                                           "The data tables, the men, the look, the portals and every map. Run once, and again after a build change."))
    sub.add_menu_entry("Project", _command("SAUD.Render", "Render the 24 views", "render_views()",
                                           "The pictures through the look, into Saved/RenderKit. Takes minutes."))
    sub.add_menu_entry("Project", _command("SAUD.Cars", "Check the cars and the gates", "check_cars_and_gates()",
                                           "The engine-free checks of the street cars and the gate portals, run with python3."))
    maps = sub.add_sub_menu(OWNER, "Project", "SAUDMaps", "Rebuild one map")
    for i, (label, _path) in enumerate(MAPS):
        maps.add_menu_entry("Maps", _command("SAUD.Map%d" % i, label, "rebuild_map(%d)" % i,
                                             "Rebuild %s from its builder." % label))
    sub.add_menu_entry("Look", _command("SAUD.Folder", "Open the render folder", "open_render_folder()"))
    sub.add_menu_entry("Look", _command("SAUD.Report", "Open the setup report", "open_setup_report()"))
    menus.refresh_all_widgets()
    _say("the SAUD menu is in the top bar")
    return True


# ----------------------------------------------------------------------------
# Notes, for whoever first runs this inside Unreal 5.4 (none of it has been):
#  - unreal.ToolMenus.get(), find_menu("LevelEditor.MainMenu"), add_sub_menu(owner,
#    section, name, label), add_menu_entry(section, entry), remove_menu(name),
#    refresh_all_widgets(): as remembered from UE 5.4's Python examples.
#  - unreal.ToolMenuEntry(name=, type=), set_label, set_tool_tip,
#    set_string_command(ToolMenuStringCommandType.PYTHON, custom_type=, string=):
#    the string is run with exec in the editor's Python, so `import saud_menu`
#    needs saud_menu on sys.path -- init_unreal.py puts Tools/unreal/saud_menu there.
#  - unreal.MultiBlockType.MENU_ENTRY, unreal.log, unreal.Paths.project_dir().
#  - Items run the kit's own scripts with SAUD_KEEP_EDITOR set; render_views.py
#    keeps its own tick callback alive after it returns, so the menu returns at once.
