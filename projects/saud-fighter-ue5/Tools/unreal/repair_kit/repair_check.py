"""SAUD repair kit: the project's files, checked -- no engine, no packages.

Run by REPAIR_SAUD.bat / REPAIR_SAUD_MAC.command with Unreal's own Python
(any Python 3 will do) before anything is cleaned or rebuilt:

    python repair_check.py <saud-fighter-ue5 folder> <report.txt>
    python repair_check.py --selftest

It reads; it changes nothing. What it looks for is what goes wrong when a
project is copied, downloaded as a zip or half-extracted onto a PC or a Mac:

  ERRORS (the build or the editor will fail on them)
   - SaudFighter.uproject is not valid JSON, is not for 5.4, or names a
     module whose Source/<Name>/<Name>.Build.cs is missing;
   - a Target.cs the build needs is missing (the game's, the editor's);
   - a Config/*.ini the game reads is missing;
   - a Content/Data .json does not parse, or a .csv has a row with a
     different number of columns from its header;
   - a file under Content is empty (a download that stopped), or is a
     Git LFS pointer instead of the file it stands for.
  WARNINGS (it may still work)
   - a path long enough that Windows (260 characters) is likely to refuse
     it once Unreal adds its own folders under it.

Exit code 0 when there is no error, 1 when there is one. The report says
every finding in plain words, and what to do about it.

Written 2026-11-01 (Riyadh). Checked here by --selftest, which breaks each
rule on a scratch copy and must see each one caught; never run on Windows
or a Mac.
"""

import csv
import io
import json
import os
import shutil
import sys
import tempfile

PROJECT_FILE = "SaudFighter.uproject"
ENGINE = "5.4"
TARGETS = ("SaudFighter.Target.cs", "SaudFighterEditor.Target.cs")
CONFIGS = ("DefaultEngine.ini", "DefaultGame.ini", "DefaultInput.ini")
LFS_HEAD = b"version https://git-lfs.github.com/spec/v1"
# Windows refuses a path over 260 characters; Unreal puts up to ~80 more of
# its own under Intermediate and Saved. A project file this long already is
# the one that fails first.
PATH_WARN = 180


def _read_bytes(path, n=None):
    with open(path, "rb") as fh:
        return fh.read() if n is None else fh.read(n)


def check(proj):
    """Every finding as (level, what, what to do). Level 'ERROR' or 'WARNING'."""
    found = []

    def err(what, todo):
        found.append(("ERROR", what, todo))

    def warn(what, todo):
        found.append(("WARNING", what, todo))

    up = os.path.join(proj, PROJECT_FILE)
    if not os.path.isfile(up):
        err("%s is missing." % PROJECT_FILE, "Point the kit at the saud-fighter-ue5 folder, or download the project again.")
        return found
    try:
        data = json.loads(_read_bytes(up).decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError) as e:
        err("%s is not valid JSON (%s)." % (PROJECT_FILE, e), "Download that one file again from the branch; do not edit it by hand.")
        data = None
    if isinstance(data, dict):
        if str(data.get("EngineAssociation", "")) != ENGINE:
            err("%s is for engine '%s', not %s." % (PROJECT_FILE, data.get("EngineAssociation"), ENGINE),
                "Right-click the .uproject, Switch Unreal Engine version, pick 5.4 -- or download it again.")
        for m in data.get("Modules", []) or []:
            name = m.get("Name", "") if isinstance(m, dict) else ""
            bc = os.path.join(proj, "Source", name, name + ".Build.cs")
            if not name or not os.path.isfile(bc):
                err("The module '%s' has no Source/%s/%s.Build.cs." % (name, name, name),
                    "The Source folder is incomplete: download the project again and extract all of it.")

    for t in TARGETS:
        if not os.path.isfile(os.path.join(proj, "Source", t)):
            err("Source/%s is missing." % t, "The Source folder is incomplete: download the project again and extract all of it.")
    for c in CONFIGS:
        if not os.path.isfile(os.path.join(proj, "Config", c)):
            err("Config/%s is missing." % c, "The Config folder is incomplete: download the project again and extract all of it.")

    data_dir = os.path.join(proj, "Content", "Data")
    if os.path.isdir(data_dir):
        for name in sorted(os.listdir(data_dir)):
            p = os.path.join(data_dir, name)
            if not os.path.isfile(p):
                continue
            if name.lower().endswith(".json"):
                try:
                    json.loads(_read_bytes(p).decode("utf-8-sig"))
                except (ValueError, UnicodeDecodeError) as e:
                    err("Content/Data/%s does not parse (%s)." % (name, e),
                        "Download that file again from the branch; Content/Data is generated and never edited by hand.")
            elif name.lower().endswith(".csv"):
                try:
                    rows = list(csv.reader(io.StringIO(_read_bytes(p).decode("utf-8-sig"))))
                except (csv.Error, UnicodeDecodeError) as e:
                    err("Content/Data/%s cannot be read (%s)." % (name, e), "Download that file again from the branch.")
                    continue
                rows = [r for r in rows if r]
                if rows:
                    width = len(rows[0])
                    bad = [i + 1 for i, r in enumerate(rows) if len(r) != width]
                    if bad:
                        err("Content/Data/%s: row %d has %d columns where the header has %d." % (name, bad[0], len(rows[bad[0] - 1]), width),
                            "Download that file again from the branch; Content/Data is generated and never edited by hand.")
    else:
        err("Content/Data is missing.", "The Content folder is incomplete: download the project again and extract all of it.")

    content = os.path.join(proj, "Content")
    empty, lfs = [], []
    longest, longest_len = "", 0
    for root, _dirs, files in os.walk(proj):
        rel_root = os.path.relpath(root, proj)
        top = rel_root.split(os.sep)[0]
        if top in ("Binaries", "Intermediate", "DerivedDataCache", "Saved", ".vs"):
            continue
        for f in files:
            p = os.path.join(root, f)
            n = len(os.path.abspath(p))
            if n > longest_len:
                longest, longest_len = p, n
            if not p.startswith(content + os.sep):
                continue
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            if size == 0:
                empty.append(os.path.relpath(p, proj))
            elif size < 512 and _read_bytes(p, len(LFS_HEAD)) == LFS_HEAD:
                lfs.append(os.path.relpath(p, proj))
    if empty:
        err("%d file(s) under Content are empty, e.g. %s." % (len(empty), empty[0].replace(os.sep, "/")),
            "The download or the extraction stopped part-way: download the project again and extract all of it.")
    if lfs:
        err("%d file(s) under Content are Git LFS pointers, not the files, e.g. %s." % (len(lfs), lfs[0].replace(os.sep, "/")),
            "Get the project with Git LFS (git lfs pull), not as a plain zip.")
    if longest_len > PATH_WARN:
        warn("The longest path in the project is %d characters (%s)." % (longest_len, os.path.relpath(longest, proj).replace(os.sep, "/")),
             "On Windows move the project to a short folder, e.g. C:\\SAUD\\g\\projects\\saud-fighter-ue5 (see the render kit's README).")
    return found


def report(proj, found, out):
    errors = [f for f in found if f[0] == "ERROR"]
    warns = [f for f in found if f[0] == "WARNING"]
    lines = ["SAUD repair kit - the project's files", "project: %s" % os.path.abspath(proj), ""]
    if not found:
        lines.append("Everything checked is in place.")
    for level, what, todo in found:
        lines.append("%s: %s" % (level, what))
        lines.append("   what to do: %s" % todo)
    lines += ["", "%d error(s), %d warning(s)" % (len(errors), len(warns))]
    text = "\n".join(lines) + "\n"
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
    sys.stdout.write(text)
    return 1 if errors else 0


# --------------------------------------------------------------------------
def _fixture(root):
    """A small project that passes every rule."""
    os.makedirs(os.path.join(root, "Source", "SaudFighter"))
    os.makedirs(os.path.join(root, "Config"))
    os.makedirs(os.path.join(root, "Content", "Data"))
    with open(os.path.join(root, PROJECT_FILE), "w") as fh:
        json.dump({"EngineAssociation": ENGINE, "Modules": [{"Name": "SaudFighter"}]}, fh)
    open(os.path.join(root, "Source", "SaudFighter", "SaudFighter.Build.cs"), "w").write("// build\n")
    for t in TARGETS:
        open(os.path.join(root, "Source", t), "w").write("// target\n")
    for c in CONFIGS:
        open(os.path.join(root, "Config", c), "w").write("[x]\n")
    open(os.path.join(root, "Content", "Data", "DT_A.json"), "w").write('[{"Name": "a"}]\n')
    open(os.path.join(root, "Content", "Data", "DT_B.csv"), "w").write('Name,"A, quoted",C\nx,"1, 2",3\n')
    open(os.path.join(root, "Content", "M.fbx"), "wb").write(b"\x00" * 600)


def selftest():
    breaks = [
        ("no uproject", lambda r: os.remove(os.path.join(r, PROJECT_FILE)), "is missing"),
        ("bad uproject", lambda r: open(os.path.join(r, PROJECT_FILE), "w").write("{nope"), "is not valid JSON"),
        ("wrong engine", lambda r: open(os.path.join(r, PROJECT_FILE), "w").write('{"EngineAssociation": "5.3", "Modules": []}'), "not 5.4"),
        ("no Build.cs", lambda r: os.remove(os.path.join(r, "Source", "SaudFighter", "SaudFighter.Build.cs")), "has no Source/"),
        ("no editor target", lambda r: os.remove(os.path.join(r, "Source", TARGETS[1])), "SaudFighterEditor.Target.cs is missing"),
        ("no ini", lambda r: os.remove(os.path.join(r, "Config", CONFIGS[0])), "DefaultEngine.ini is missing"),
        ("bad json", lambda r: open(os.path.join(r, "Content", "Data", "DT_A.json"), "w").write("[{"), "DT_A.json does not parse"),
        ("ragged csv", lambda r: open(os.path.join(r, "Content", "Data", "DT_B.csv"), "a").write("y,1\n"), "row 3 has 2 columns"),
        ("empty file", lambda r: open(os.path.join(r, "Content", "M.fbx"), "wb").close(), "are empty"),
        ("lfs pointer", lambda r: open(os.path.join(r, "Content", "M.fbx"), "wb").write(LFS_HEAD + b"\noid sha256:00\nsize 9\n"), "Git LFS pointers"),
        ("long path", lambda r: os.makedirs(os.path.join(r, "Content", "x" * 120, "y" * 60)) or open(os.path.join(r, "Content", "x" * 120, "y" * 60, "z.txt"), "w").write("z"), "The longest path"),
    ]
    caught = 0
    base = tempfile.mkdtemp(prefix="saud_repair_")
    try:
        clean = os.path.join(base, "clean")
        _fixture(clean)
        if check(clean):
            print("the unbroken fixture fails its own checks: %s" % check(clean))
            return 1
        print("  (unbroken)           passes")
        for name, brk, want in breaks:
            r = os.path.join(base, name.replace(" ", "_"))
            _fixture(r)
            brk(r)
            hits = [f for f in check(r) if want in f[1]]
            ok = bool(hits)
            caught += ok
            print("  %-20s %s" % (name, "caught" if ok else "NOT caught"))
    finally:
        shutil.rmtree(base, ignore_errors=True)
    print("%d of %d sabotages caught" % (caught, len(breaks)))
    return 0 if caught == len(breaks) else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        sys.exit(selftest())
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    project = sys.argv[1]
    sys.exit(report(project, check(project), sys.argv[2] if len(sys.argv) > 2 else None))
