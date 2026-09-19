"""The roster: who the fighters are, read out of the browser build.

The browser is the source of truth for every number in this project, and
the two files that say what a man looks like -- assets/ahmed.js for the
hero, assets/enemies.js for the eleven archetypes -- are JavaScript object
literals: unquoted keys, single-quoted strings, comments, a trailing comma
here and there. None of it is JSON, so this parses it as what it is rather
than copying the numbers across by hand, which is how a copy goes stale.

    spec("thug")     -> dict(name, display, ar, sc, col{...}, look{...})
    spec("ahmed")    -> the same shape for the hero

`sc` is what the ports scale the body by, and `look.build` the limb
thickness (index.html:1379 and :1567). DT_Fighters.csv carries neither,
which is why this reads the browser directly, exactly as build_motion.py
does for the bosses.

No Blender in here: the preview harness and the tests read it too.
"""
import os
import re
import json

HERE = os.path.dirname(os.path.abspath(__file__))
BROWSER = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "ahmed-fighter"))
ENEMIES = os.path.join(BROWSER, "assets", "enemies.js")
AHMED = os.path.join(BROWSER, "assets", "ahmed.js")


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


def ahmed():
    return _load(AHMED, "window.ASSET_AHMED")


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


def spec(kind):
    """One fighter, in one shape, whoever he is."""
    if kind == "ahmed":
        a = ahmed()
        look = dict(a["look"])
        return dict(kind="ahmed", name="Ahmed", display=a["name"], ar=a["ar"],
                    sc=float(a["spawn"]["sc"]), col=dict(a["col"]), look=look, reach=float(a["base"]["reach"]))
    e = enemies()[kind]
    return dict(kind=kind, name=kind.capitalize(), display=e["name"], ar=e["ar"],
                sc=float(e["sc"]), col=dict(e["col"]), look=dict(e["look"]), reach=float(e["reach"]))


if __name__ == "__main__":
    import sys
    for k in sys.argv[1:] or ("ahmed", "thug", "brawler"):
        s = spec(k)
        print("%-8s %-10s sc %.2f build %.2f  col %s  look %s" % (
            s["name"], s["display"], s["sc"], s["look"].get("build", 1.0), s["col"],
            {k2: v for k2, v in s["look"].items() if k2 != "build"}))
