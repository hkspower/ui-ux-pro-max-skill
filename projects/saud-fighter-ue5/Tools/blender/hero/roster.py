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
# One line per colour, (man, slot) -> hex. Every hex is an ALBEDO: the sRGB
# base colour the pipeline paints, as given, with no fabric floor under it
# (finish.fabric lifts a browser colour; these were solved against the look
# already, and a dark plum or wine lifted to L* 19 reads as grey-mauve).
# The colour it should look on screen, lit through the look, is the comment.
# They are the lead's to refine once the look is final: change a line here and
# nothing else (`--check` and `--grim-check` hold what is held, and the
# browser's value for the slot is still in spec()['browser_col']).
#
#   given     the lead's solved albedo (top, bottom, band, gloves)
#   x0.30     the man's bottom: his top's colour at 0.30 of its linear light
#   estimate  not given; a first guess to be solved the same way
#
# ZAYOS wears no top (his chest is bare): his `band` is what his gloves and
# his waistband are painted in. The flag patch on Saud's chest is not in here:
# it is Kuwait's flag and keeps its true colours (finish.kit_colour).
UNREAL_KIT = {
    ("saud", "top"):       "#A3A09C",   # given     shows #F0E8DE cream
    ("saud", "bottom"):    "#240910",   # given     shows #6B2A3A madder wine
    ("saud", "band"):      "#FD2C67",   # given     shows #F42A63 cerise (was Kuwait red #ff1a3c)
    ("thug", "top"):       "#73687F",   # given     shows #B7A7C9 ash-lilac
    ("thug", "bottom"):    "#403947",   # x0.30     the lilac, dark
    ("thug", "band"):      "#625C68",   # estimate  a muted lilac: L* 40, C* 8, the top's hue
    ("brawler", "top"):    "#1B4E46",   # given     shows #138C7C jade
    ("brawler", "bottom"): "#0B2A25",   # x0.30     the jade, dark
    ("brawler", "band"):   "#8A0F20",   # given     shows #B4142E blood (was Kuwait red #c8102e)
    ("saqr", "top"):       "#936E10",   # given     shows #E8B020 saffron
    ("saqr", "bottom"):    "#533D05",   # x0.30     the saffron, dark
    ("saqr", "band"):      "#A39D96",   # estimate  bone-cream (the palette's #F3E4D0) at the cream top's ratios
    ("boss", "top"):       "#381C4E",   # given     shows #6E2A9C violet (AL-WAHSH)
    ("boss", "bottom"):    "#1C0B2A",   # x0.30     the violet, dark
    ("boss", "band"):      "#8A0F20",   # given     blood, as the brawler's (was Kuwait red #c8102e)
    ("zayos", "bottom"):   "#181019",   # estimate  near-black plum: shows #201826; L* 5.7, a plum
    ("zayos", "band"):     "#27508D",   # given     shows #4A8EF2 azure: his gloves and his band (were red #c8102e)
}
KIT_SLOTS = ("top", "bottom", "band")


def check_kit_table(men=None):
    """The table is well formed: each key a (man, slot) of KIT_SLOTS, each
    value a #rrggbb, and, given the men the browser has (`men`, the roster's
    kinds), no man it does not have."""
    for (kind, slot), hexv in UNREAL_KIT.items():
        assert slot in KIT_SLOTS, "UNREAL_KIT: %s has no %r slot (%s)" % (kind, slot, ", ".join(KIT_SLOTS))
        assert re.fullmatch(r"#[0-9A-Fa-f]{6}", hexv), "UNREAL_KIT: %s's %s is %r, want #rrggbb" % (kind, slot, hexv)
    if men is not None:
        bad = sorted({k for k, _ in UNREAL_KIT} - set(men))
        assert not bad, "UNREAL_KIT names no man in the roster: %s" % bad


check_kit_table()


def _unreal_kit(kind):
    """{slot: hex} this build gives `kind`."""
    return {slot: hexv for (k, slot), hexv in UNREAL_KIT.items() if k == kind}


def spec(kind):
    """One fighter, in one shape, whoever he is. `col` is what the 3D man is
    painted in: the browser's with UNREAL_KIT over it; `browser_col` is the
    browser's own and `albedo` the slots UNREAL_KIT gave (those are final
    albedo; the rest are the browser's flat colours)."""
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
