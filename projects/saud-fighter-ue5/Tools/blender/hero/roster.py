"""The roster: who the fighters are, read out of the browser build.

The browser is the source of truth for every number in this project, and
the two files that say what a man looks like -- assets/saud.js for the
hero, assets/enemies.js for the eleven archetypes -- are JavaScript object
literals: unquoted keys, single-quoted strings, comments, a trailing comma
here and there. None of it is JSON, so this parses it as what it is rather
than copying the numbers across by hand, which is how a copy goes stale.

    spec("thug")     -> dict(name, display, ar, sc, col{...}, look{...},
                             browser_col{...}, albedo(...))
    spec("saud")    -> the same shape for the hero

`sc` is what the ports scale the body by, and `look.build` the limb
thickness (index.html:1379 and :1567). DT_Fighters.csv carries neither,
which is why this reads the browser directly, exactly as build_motion.py
does for the bosses.

THE ONE THING IN HERE THAT IS NOT THE BROWSER'S is UNREAL_KIT, below: the
Unreal build's own top, trousers and band for each of the six men it builds
in 3D (2026-11-19, the palette "Sodium Afterglow"). spec()'s `col` is the
browser's with that table laid over it -- what the 3D man is painted in --
`browser_col` is the browser's own, untouched (the data check holds it to
DT_Colors.csv), and `albedo` names the slots that came from the table.

No Blender in here: the preview harness and the tests read it too.
"""
import os
import re
import json

HERE = os.path.dirname(os.path.abspath(__file__))
BROWSER = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "saud-fighter"))
ENEMIES = os.path.join(BROWSER, "assets", "enemies.js")
SAUD = os.path.join(BROWSER, "assets", "saud.js")


def _strip_comments(src):
    """Drop /* */ and // comments, but not inside a string."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c in "'\"":
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == "\\" else 1
            out.append(src[i:j + 1]); i = j + 1
        elif src.startswith("/*", i):
            i = src.index("*/", i) + 2
        elif src.startswith("//", i):
            while i < n and src[i] != "\n":
                i += 1
        else:
            out.append(c); i += 1
    return "".join(out)


def _js_literal_to_json(src):
    """Enough of JavaScript's object syntax to read these two files:
    unquoted keys, single-quoted strings, trailing commas, `true`/`false`."""
    src = _strip_comments(src)
    # single-quoted strings -> double-quoted (none of the values contain a
    # double quote; the Arabic names are plain letters)
    src = re.sub(r"'([^'\\]*)'", lambda m: json.dumps(m.group(1), ensure_ascii=False), src)
    # unquoted keys:  word:  ->  "word":
    src = re.sub(r"([{,]\s*)([A-Za-z_$][\w$]*)\s*:", r'\1"\2":', src)
    # trailing commas
    src = re.sub(r",(\s*[}\]])", r"\1", src)
    # `.80` is a number in JavaScript and not in JSON. Outside strings only:
    # 'rgba(34,24,16,.85)' is a string and stays exactly as written.
    parts = re.split(r'("(?:[^"\\]|\\.)*")', src)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r"(?<![\w.])(-?)\.(\d)", r"\g<1>0.\2", parts[i])
    return "".join(parts)


def _object_after(src, marker):
    """The balanced {...} that follows `marker` in `src`."""
    i = src.index(marker)
    i = src.index("{", i)
    depth, j = 0, i
    while j < len(src):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
        j += 1
    raise ValueError("unbalanced object after %r" % marker)


def _load(path, marker):
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    return json.loads(_js_literal_to_json(_object_after(src, marker)))


def enemies():
    return _load(ENEMIES, "window.ASSET_ENEMIES")


def saud():
    return _load(SAUD, "window.ASSET_SAUD")


def rgba_over(rgba, base_hex):
    """'rgba(r,g,b,a)' composited over a hex colour -> hex. The browser draws
    a beard as a translucent wash over the skin; the bake wants one colour."""
    m = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+))?\s*\)", rgba)
    if not m:
        return rgba
    r, g, b = (int(m.group(i)) for i in (1, 2, 3))
    a = float(m.group(4)) if m.group(4) else 1.0
    h = base_hex.lstrip("#")
    br, bg, bb = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % tuple(int(round(c * a + bc * (1 - a))) for c, bc in ((r, br), (g, bg), (b, bb)))


def rgba_alpha(colour):
    """The alpha of an 'rgba(r,g,b,a)' string; 1.0 for a hex or an rgb()."""
    m = re.match(r"rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*([\d.]+))?\s*\)", colour)
    return float(m.group(1)) if m and m.group(1) else 1.0


# ---- THIS BUILD'S KIT -- Unreal only, NOT the browser's ----------------------
# Asked 2026-11-19 (Riyadh) as "remove all current colours, use new colours":
# the palette "Sodium Afterglow", a dark Gulf dusk with jewel-coloured men.
# The browser draws every man in its own flat colours (assets/saud.js,
# assets/enemies.js) and they do not move; the 3D men are painted from THIS
# table instead, the way pipeline.FACES and CUTS are the 3D men's own.
#
# One line per colour, (man, slot) -> hex, for each of the six men and each of
# KIT_SLOTS: all eighteen are required (check_kit_table, spec()), so a line
# that goes missing is an error and never the browser's old colour quietly
# back. Every hex is an ALBEDO, the sRGB base colour the pipeline paints, as
# given, with no fabric floor under it (finish.fabric lifts a browser colour;
# a dark plum or wine lifted to L* 19 reads as grey-mauve). A line with a
# `shows` -- the palette's colour it must read as on screen, in its comment and
# as data in UNREAL_SHOWS below, which finish.check_kit holds the look's
# picture of the line to -- was SOLVED against the look as it stands
# (2026-11-19, second round): an albedo whose lit patch, drawn by the look
# (finish.shown()), comes within 1 Delta E of the nearest to that colour (a
# hill-climb over sRGB integers from several starts; the second reader's
# search found four of them 0.07-0.56 nearer still, which no eye can see and
# which would bring two bands to 1.4 over the accent floor, so they stay).
# Saud's cream is the nearest that keeps his
# top 21 or more from his skin in a*b* (the skin rule wants 20). Not solved:
# AL-SAQR's top (his saffron is out of the look's reach: the nearest albedo
# found, #FF6D00, is still Delta E 8.6 off and an odd orange as a cloth, so the
# lead's #936E10 stays, with the limit of its own in finish.SHOWS_LIMIT; the
# first rebuild's render decides it), a line with no `shows` (a man's trousers
# but Saud's are only his jewel, dark), and a hex marked "estimate".
# They are the lead's to refine once the look is final: change a line here and
# nothing else (`--check` and `--grim-check` hold what is held, and the
# browser's value for the slot is still in spec()['browser_col']).
#
# ZAYOS wears no top (his chest is bare): his `band` is what his gloves and
# his waistband are painted in, and his `top` line is never drawn; it is there
# so that no colour of the browser's is left in his kit. The flag patch on
# Saud's chest is not in here: it is Kuwait's flag and keeps its true colours
# (finish.kit_colour).
UNREAL_KIT = {
    ("saud", "top"):       "#A0A197",   # shows #F0E8DE cream
    ("saud", "bottom"):    "#210C11",   # shows #6B2A3A madder wine
    ("saud", "band"):      "#AB2949",   # shows #F42A63 cerise (was Kuwait red #ff1a3c)
    ("thug", "top"):       "#6C668C",   # shows #B7A7C9 ash-lilac
    ("thug", "bottom"):    "#100D15",   # the lilac, dark
    ("thug", "band"):      "#5B5260",   # estimate: a muted lilac, the ash-lilac's hue
    ("brawler", "top"):    "#174E44",   # shows #138C7C jade
    ("brawler", "bottom"): "#071E1B",   # the jade, dark
    ("brawler", "band"):   "#612124",   # shows #B4142E blood (was Kuwait red #c8102e)
    ("saqr", "top"):       "#936E10",   # shows #E8B020 saffron: the lead's, kept (not solved: see above)
    ("saqr", "bottom"):    "#292118",   # the saffron, dark
    ("saqr", "band"):      "#A79C85",   # shows #F3E4D0 bone
    ("boss", "top"):       "#2D1E4F",   # shows #6E2A9C violet (AL-WAHSH)
    ("boss", "bottom"):    "#07020E",   # the violet, dark
    ("boss", "band"):      "#612124",   # shows #B4142E blood, as the brawler's (was Kuwait red #c8102e)
    ("zayos", "top"):      "#060408",   # never drawn (he wears none): his bottom's colour
    ("zayos", "bottom"):   "#060408",   # near-black plum
    ("zayos", "band"):     "#2654BD",   # shows #4A8EF2 azure: his gloves and his band (were red #c8102e)
}
KIT_SLOTS = ("top", "bottom", "band")
UNREAL_MEN = ("saud", "thug", "brawler", "saqr", "boss", "zayos")

# The palette's colour each approved line should read as on screen: the
# `shows` of the table, as data. finish.check_kit draws each line's albedo
# through the look and holds it to this (finish.KIT_RULES `shows`).
UNREAL_SHOWS = {
    ("saud", "top"):    "#F0E8DE",
    ("saud", "bottom"): "#6B2A3A",
    ("saud", "band"):   "#F42A63",
    ("thug", "top"):    "#B7A7C9",
    ("brawler", "top"): "#138C7C",
    ("brawler", "band"): "#B4142E",
    ("saqr", "top"):    "#E8B020",
    ("saqr", "band"):   "#F3E4D0",
    ("boss", "top"):    "#6E2A9C",
    ("boss", "band"):   "#B4142E",
    ("zayos", "band"):  "#4A8EF2",
}
# The eleven lines the palette approves a colour for, written out once more so
# that a line dropped from UNREAL_SHOWS is an error and not a rule quietly
# switched off for it (check_kit_table). A line the palette gives no colour
# (a man's trousers but Saud's, the thug's band, ZAYOS's top) is not here.
UNREAL_SHOWS_LINES = (
    ("saud", "top"), ("saud", "bottom"), ("saud", "band"),
    ("thug", "top"),
    ("brawler", "top"), ("brawler", "band"),
    ("saqr", "top"), ("saqr", "band"),
    ("boss", "top"), ("boss", "band"),
    ("zayos", "band"),
)


def check_kit_table(men=None):
    """The table is well formed and COMPLETE: each key a (man, slot) of
    KIT_SLOTS, each value a #rrggbb, every one of the six men's three slots
    present (a missing line would paint the browser's old colour, floored,
    and nothing else would notice), the approved `shows` colours well formed,
    each on a line of the table and one for every one of the eleven approved
    lines (a line dropped from UNREAL_SHOWS would switch its rule off), and,
    given the men the browser has (`men`, the roster's kinds), no man it does
    not have."""
    hexed = lambda h: isinstance(h, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", h)
    for (kind, slot), hexv in UNREAL_KIT.items():
        assert slot in KIT_SLOTS, "UNREAL_KIT: %s has no %r slot (%s)" % (kind, slot, ", ".join(KIT_SLOTS))
        assert hexed(hexv), "UNREAL_KIT: %s's %s is %r, want #rrggbb" % (kind, slot, hexv)
    for kind in UNREAL_MEN:
        missing = _missing(kind)
        assert not missing, "UNREAL_KIT has no %s %s: it would be painted in the browser's own colour" % (
            kind, " or ".join(missing))
    for kind, slot in UNREAL_SHOWS_LINES:
        assert (kind, slot) in UNREAL_SHOWS, "UNREAL_SHOWS has no %s %s: the look's picture of that line would be held to nothing" % (kind, slot)
    for (kind, slot), hexv in UNREAL_SHOWS.items():
        assert (kind, slot) in UNREAL_KIT, "UNREAL_SHOWS: %s's %s is not a line of UNREAL_KIT" % (kind, slot)
        assert hexed(hexv), "UNREAL_SHOWS: %s's %s is %r, want #rrggbb" % (kind, slot, hexv)
    if men is not None:
        bad = sorted({k for k, _ in UNREAL_KIT} - set(men))
        assert not bad, "UNREAL_KIT names no man in the roster: %s" % bad
        gone = sorted(set(UNREAL_MEN) - set(men))
        assert not gone, "the roster has no %s, whom UNREAL_KIT dresses" % gone


def _missing(kind):
    """The slots of KIT_SLOTS the table has no line for, for one of its six
    men (none for a man it does not dress)."""
    return [slot for slot in KIT_SLOTS if kind in UNREAL_MEN and (kind, slot) not in UNREAL_KIT]


check_kit_table()


def _unreal_kit(kind):
    """{slot: hex} this build gives `kind`; one of its six men with a slot
    missing is an error, never the browser's colour for it."""
    missing = _missing(kind)
    assert not missing, "UNREAL_KIT has no %s %s: it would be painted in the browser's own colour" % (
        kind, " or ".join(missing))
    return {slot: hexv for (k, slot), hexv in UNREAL_KIT.items() if k == kind}


def spec(kind):
    """One fighter, in one shape, whoever he is. `col` is what the 3D man is
    painted in: the browser's with UNREAL_KIT over it; `browser_col` is the
    browser's own and `albedo` the slots UNREAL_KIT gave (those are final
    albedo; the rest are the browser's flat colours -- on a man the table
    does not dress, one the 3D build does not make)."""
    if kind == "saud":
        a = saud()
        look = dict(a["look"])
        browser, over = dict(a["col"]), _unreal_kit("saud")
        return dict(kind="saud", name="Saud", display=a["name"], ar=a["ar"],
                    sc=float(a["spawn"]["sc"]), col=dict(browser, **over), browser_col=browser,
                    albedo=tuple(sl for sl in KIT_SLOTS if sl in over), look=look, reach=float(a["base"]["reach"]))
    e = enemies()[kind]
    browser, over = dict(e["col"]), _unreal_kit(kind)
    return dict(kind=kind, name=kind.capitalize(), display=e["name"], ar=e["ar"],
                sc=float(e["sc"]), col=dict(browser, **over), browser_col=browser,
                albedo=tuple(sl for sl in KIT_SLOTS if sl in over), look=dict(e["look"]), reach=float(e["reach"]))


if __name__ == "__main__":
    import sys
    for k in sys.argv[1:] or ("saud", "thug", "brawler"):
        s = spec(k)
        print("%-8s %-10s sc %.2f build %.2f  col %s  look %s" % (
            s["name"], s["display"], s["sc"], s["look"].get("build", 1.0), s["col"],
            {k2: v for k2, v in s["look"].items() if k2 != "build"}))
