"""
The System's windows, drawn without an engine: SaudSystem::Build
(Combat/SaudSystem.h) over the HUD (SaudHud::Build) over a render of the
souq fight, as SaudHUD.cpp would draw them -- the way hud_preview.py draws
the HUD, whose rasteriser this uses.

Tools/harness/system_dump.cpp prints the System's draw list as JSON for a
model made of the events given (their words read here from
Content/Data/DT_SystemLines.json, formatted by the C++), and this
rasterises it in order over hud_dump's HUD: the triangles with their
per-vertex colour and alpha in LINEAR light, each text stroked eight times
in ink and filled, set left, centred or flush right as the item says.

It also MEASURES: every word the System draws, in the preview's own font
(DejaVu Sans Bold, line height = the item's height, as SaudHUD.cpp scales
the engine's), must stand inside its own window, at every one of the
harness's seven screen shapes, for every line of the table -- the C++'s
width estimate is checked against the real font here. It fails loudly
otherwise.

STAND-INS, as hud_preview.py's: DejaVu for the engine's Roboto; blending
in linear light; supersampled.

RUN
  python3 Tools/look/system_preview.py [--out DIR] [--bg PNG] [--check-only]
writes system-levelup.png, system-skill-hawk.png, system-quest.png and
system-ending.png into DIR (default Docs/renders/).
"""

import json
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hud_preview as hp  # noqa: E402  (the HUD's rasteriser, its background, its dump)

ROOT = hp.ROOT
LINES = os.path.join(ROOT, "Content", "Data", "DT_SystemLines.json")
SHAPES = ((1920, 1080), (1280, 720), (3840, 2160), (2560, 1080), (3440, 1440), (1600, 1200), (1680, 1050))
REF = ImageFont.truetype(hp.FONT, 100)
ASC, DESC = REF.getmetrics()


def build_system_dump(out_dir):
    exe = os.path.join(out_dir, "system_dump")
    cxx = os.environ.get("CXX", "g++")
    subprocess.check_call([cxx, "-std=c++17", "-O1", "-Wall", "-Wextra", "-Werror", "-DSAUD_HARNESS",
                           "-I" + os.path.join(ROOT, "Tools", "harness"), "-o", exe,
                           os.path.join(ROOT, "Tools", "harness", "system_dump.cpp")])
    return exe


def rows():
    return {r["Name"]: r for r in json.load(open(LINES, encoding="utf-8"))}


def event(table, kind, key="", level=0, hp_=0, mp=0, xp=0, rank="", skill="", quest=""):
    r = table.get(kind + ("_" + key if key else "")) or table[kind]
    fields = [kind, key] + [r[f] for f in ("Title", "Head", "Body", "Reward", "Beneath", "Status")]
    fields += [str(level), str(hp_), str(mp), str(xp), rank, skill, quest]
    assert not any("|" in f for f in fields)
    return "event=" + "|".join(fields)


def questline(table):
    q = table["OpenQuest"]
    return "questline=%s|%s|%s" % (q["Title"], q["Head"], q["Status"])


def sysdump(exe, w, h, seconds, args):
    return json.loads(subprocess.check_output([exe, str(w), str(h), "%g" % seconds] + list(args)))


def font_for(h):
    return ImageFont.truetype(hp.FONT, max(4, int(round(100 * h / (ASC + DESC)))))


def text_width(s, h):
    return ImageDraw.Draw(Image.new("L", (1, 1))).textlength(s, font=font_for(h))


def left_of(item):
    w = text_width(item["s"], item["h"])
    a = item["align"]
    return item["x"] - (0.0 if a == 0 else (0.5 * w if a == 1 else w)), w


def misfits(d):
    """Every text the System drew that does not stand inside its own window."""
    bad = []
    for t in d["texts"]:
        box = d["pieces"][t["piece"]]
        x0, w = left_of(t)
        if x0 < box["x"] + 1 or x0 + w > box["x"] + box["w"] - 1 or t["y"] < box["y"] or t["y"] + t["h"] > box["y"] + box["h"] + 0.5:
            bad.append("%r (%.0f..%.0f in %.0f..%.0f)" % (t["s"], x0, x0 + w, box["x"], box["x"] + box["w"]))
    return bad


def draw_text(r, item):
    """Raster.text, set left, centred or flush right."""
    x0, _ = left_of(item)
    it = dict(item, x=x0, centre=False)
    r.text(item["s"], it)


def compose(hud_exe, sys_exe, bg, w, h, hud_state, seconds, sys_args, out):
    hd = hp.dump(hud_exe, w, h, hud_state)
    sd = sysdump(sys_exe, w, h, seconds, sys_args)
    assert not hd["overflow"] and not sd["overflow"], "a draw list overflowed"
    r = hp.Raster(hp.background(bg, w, h), 3 if w <= 2560 else 2)
    names = {"name": "SAUD", "hits": "HITS", "boss": hud_state.get("boss_name", "AL-WAHSH")}
    done = 0
    for item in hd["texts"]:
        for t in hd["tris"][done:item["after"]]:
            r.tri(t)
        done = item["after"]
        slot = hp.SLOTS[item["slot"]]
        r.text(str(item["value"]) if slot == "count" else hp.TITLES[item["value"]] if slot == "title" else names[slot], item)
    for t in hd["tris"][done:]:
        r.tri(t)
    done = 0
    for item in sd["texts"]:
        for t in sd["tris"][done:item["after"]]:
            r.tri(t)
        done = item["after"]
        draw_text(r, item)
    for t in sd["tris"][done:]:
        r.tri(t)
    r.image().save(out)
    return sd


def check_all(sys_exe, table):
    """Every line of the table, in its own window, at all seven shapes, in
    the real font."""
    longest = max((r["Head"] for r in table.values() if r["Event"] == "StageEntered"), key=len)
    bad = []
    n = 0
    for name, r in table.items():
        ev = r["Event"]
        if ev in ("OpenQuest", "BossWarning"):
            continue
        args = [questline(table), "quest=1",
                event(table, ev, r["Key"], 20, 114, 76, 99999, "CONTENDER", "POWER KICK", longest)]
        if ev != "GateCleared":
            args.append(event(table, "GateCleared", "Experience", xp=99999))
        for w, h in SHAPES:
            d = sysdump(sys_exe, w, h, 1.0, args)
            n += 1
            for m in misfits(d):
                bad.append("%s at %dx%d: %s" % (name, w, h, m))
    return n, bad


# A fight in progress behind the System: the HUD at 1080p.
FIGHT = dict(health=0.72, ghost=0.80, stamina=0.70, rage=0.45, combo=0, since=5.0, clock=0.62,
             street=[(660, 280, 0.45, 0.70)])


def shots(table):
    q = [questline(table), "quest=1"]
    return (
        ("system-levelup.png", FIGHT, 1.0, q + [event(table, "LevelUp", level=7, hp_=6, mp=4)]),
        ("system-skill-hawk.png", dict(FIGHT, rage=1.0, ready=1), 1.0,
         q + [event(table, "SkillAcquired", "HawkFist"), event(table, "GateCleared")]),
        ("system-quest.png", dict(FIGHT, health=1.0, ghost=1.0, stamina=1.0, rage=0.0), 1.0,
         q + [event(table, "StageEntered", "BaytAlDarb")]),
        ("system-ending.png", dict(FIGHT, health=0.38, ghost=0.38, stamina=0.55, rage=0.9), 1.0,
         q + [event(table, "QuestRemoved")]),
    )


def main():
    out_dir = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(ROOT, "Docs", "renders")
    bg = sys.argv[sys.argv.index("--bg") + 1] if "--bg" in sys.argv else os.path.join(
        ROOT, "Docs", "renders", "souq-fight-anime.png")
    table = rows()
    with tempfile.TemporaryDirectory() as tmp:
        sys_exe = build_system_dump(tmp)
        n, bad = check_all(sys_exe, table)
        for b in bad:
            print("DOES NOT FIT  " + b)
        print("%d windows measured in DejaVu Sans Bold at seven shapes: %d words outside their window" % (n, len(bad)))
        if bad:
            sys.exit(1)
        if "--check-only" in sys.argv:
            return
        hud_exe = hp.build_dump(tmp)
        os.makedirs(out_dir, exist_ok=True)
        for name, hud_state, seconds, args in shots(table):
            path = os.path.join(out_dir, name)
            d = compose(hud_exe, sys_exe, bg, 1920, 1080, hud_state, seconds, args, path)
            print("%s: %d triangles, %d words" % (path, len(d["tris"]), len(d["texts"])))


if __name__ == "__main__":
    main()
