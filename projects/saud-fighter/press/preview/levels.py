#!/usr/bin/env python3
"""SAUD preview booklet -- black and white levels.

WHY THIS EXISTS. The booklet is printed, and nearly all of it is dark. A page
that is 95% near-black looks fine backlit on a screen and prints as an
undifferentiated slab: everything below about L* 6 plugs into the same ink,
and everything above about L* 96 blows out to bare paper. The visor bug that
started this was the same disease one layer up -- the figure ink and the page
ground were 1.01:1 apart and nothing could be seen against anything.

WHAT IT MEASURES, and why not contrast ratio. WCAG's (L1+0.05)/(L2+0.05) is
built for text on a light ground and goes nearly flat down here: #05070b and
#1b2030 are a visible step apart on paper and WCAG scores them 1.35:1, which
sounds like a failure and is not. The number that matters in the shadows is
CIE L*, the perceptual lightness axis, and the difference between two of
them. Rules of thumb this file is written to:

    dL* < 2     the same ink. Two shapes at this distance are one shape.
    dL* 2-4     a just-visible edge on coated stock, invisible on uncoated.
    dL* 4-8     a step you can see and rely on.
    dL* > 8     a deliberate change of value.

    L* < 6      plugs. Detail here does not survive any press.
    L* > 96     blows. Detail here is bare paper.

    python3 levels.py                 # palette ladder + pair report
    python3 levels.py --pages DIR     # also read rendered pages and
                                      # histogram what actually got printed
"""

import argparse
import os
import re
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------------- colour

def srgb_to_linear(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hexcol):
    h = hexcol.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (srgb_to_linear(int(h[i:i + 2], 16)) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def lstar(hexcol):
    """CIE L*, 0 = black, 100 = white. The axis the eye actually uses."""
    y = luminance(hexcol)
    return 116 * (y ** (1 / 3)) - 16 if y > 0.008856 else 903.3 * y


def _f(t):
    return t ** (1 / 3) if t > 0.008856 else (7.787 * t + 16 / 116)


def to_lab(hexcol):
    """sRGB -> CIE Lab (D65). L* is the axis a levels move works on; a and b
    carry the hue and the chroma, and a levels move must not touch them."""
    h = hexcol.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (srgb_to_linear(int(h[i:i + 2], 16)) for i in (0, 2, 4))
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = (0.2126 * r + 0.7152 * g + 0.0722 * b)
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    fx, fy, fz = _f(x), _f(y), _f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def from_lab(L, a, bb):
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - bb / 200

    def inv(t):
        return t ** 3 if t ** 3 > 0.008856 else (t - 16 / 116) / 7.787

    x, y, z = inv(fx) * 0.95047, inv(fy), inv(fz) * 1.08883
    r = 3.2406 * x - 1.5372 * y - 0.4986 * z
    g = -0.9689 * x + 1.8758 * y + 0.0415 * z
    b = 0.0557 * x - 0.2040 * y + 1.0570 * z

    def enc(c):
        c = max(0.0, min(1.0, c))
        c = 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
        return max(0, min(255, round(c * 255)))

    return "#%02x%02x%02x" % (enc(r), enc(g), enc(b))


def set_lstar(hexcol, L):
    """Move a colour to a given lightness and leave its hue alone."""
    _, a, b = to_lab(hexcol)
    return from_lab(max(0.0, L), a, b)


def wcag(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# ------------------------------------------------------- what the booklet is

def palette():
    """Every colour the booklet paints with, read out of its own source.

    Not a copy: if a tone moves in figures.py this report moves with it, and
    a value that stops being used stops being reported.
    """
    out = {}
    for fn in ("figures.py", "build_preview.py"):
        src = open(os.path.join(HERE, fn), encoding="utf-8").read()
        for m in re.finditer(r'(\w+)\s*=\s*"(#[0-9a-fA-F]{3,6})"', src):
            out.setdefault(m.group(2).lower(), set()).add(f"{fn}:{m.group(1)}")
        for m in re.finditer(r'fill="(#[0-9a-fA-F]{3,6})"', src):
            out.setdefault(m.group(1).lower(), set()).add(f"{fn}:literal")
    return out


# --------------------------------------------------------------- the move

# THE LADDER. What a value IS decides where it sits, and the rungs are four
# L* apart, which is a step you can see on any stock.
#
# The one rung below the floor is deliberate. Plugging destroys DETAIL, and a
# silhouette has none -- so the deepest ink in the booklet is reserved for
# the things that are solid shapes: the figures, and a hole in the road that
# is supposed to be a hole. Everything that carries detail lives above FLOOR.
RUNGS = {
    "figure": 3.0,    # a silhouette, or a true void. No internal detail.
    "page": 8.5,      # the sheet
    "panel": 13.0,    # a panel or a backdrop laid on the sheet
    "card": 17.5,     # a card on the panel
    "raised": 22.0,   # a control on the card
}

# Everything else is a straight black-point lift: the textbook levels move,
# linear between a new floor and a new ceiling, hue untouched. It costs 6.5%
# of the separation between any two tones and buys back the whole bottom of
# the range, which was 55-80% of every page.
FLOOR, CEIL = 6.5, 95.0


def to_print(hexcol, role=None):
    """Put one authored colour through the booklet's print levels."""
    if hexcol.lower() in ("#000", "#000000"):
        return hexcol                      # a true void stays a true void
    if role in RUNGS:
        return set_lstar(hexcol, RUNGS[role])
    L, a, b = to_lab(hexcol)
    return from_lab(FLOOR + L * (CEIL - FLOOR) / 100.0, a, b)


# Which literals are STRUCTURE rather than paint, per file. The same hex can
# mean different things in different places, and that is the whole bug this
# is fixing: #05070b was the bosses' ink in figures.py AND the sheet in
# build_preview.py, which is why a boss and the paper he was printed on
# measured 0.0 apart. Everything not named here is paint, and paint lifts.
ROLES = {
    "figures.py": {
        "#05070b": "figure",     # the bosses' and the crowd's ink
        "#06080d": "figure",     # Saud's
    },
    "build_preview.py": {
        "#05070b": "page",       # here the same hex is the sheet
        "#101216": "figure",     # the flag's black stripe -- a solid mark
        "#0f1420": "figure",     # the blocks in the street panel -- ditto
        "#0a0e16": "panel",
        "#120f18": "panel",
        "#150f18": "panel",
        "#141a26": "panel",
        "#191420": "panel",
        "#1a0a1e": "panel",
    },
}


# the pairs that have to be told apart, and what each one is for
# Written as roles and authored colours rather than as finished hexes, so the
# report follows the ladder instead of going stale the moment it moves.
PAIRS = [
    (("#05070b", "page"), ("#06080d", "figure"), "the sheet vs a figure on it"),
    (("#05070b", "page"), ("#0a0c11", "panel"), "the sheet vs a panel on it"),
    (("#05070b", "page"), ("#151b28", "card"), "the sheet vs a card on it"),
    (("#0a0c11", "panel"), ("#151b28", "card"), "a panel vs a card on it"),
    (("#151b28", "card"), ("#1e2534", "raised"), "a card vs a control on it"),
    (("#06080d", "figure"), ("#242031", None), "Saud's ink vs his lit cheek"),
    (("#06080d", "figure"), ("#161d33", None), "Saud's ink vs his vest"),
    (("#05070b", "figure"), ("#2e2330", None), "AL-WAHSH's ink vs his cheek"),
    (("#05070b", "figure"), ("#17303c", None), "AL-SAQR's ink vs his cheek"),
    (("#05070b", "figure"), ("#2a2318", None), "ZAYOS's ink vs his cheek"),
    (("#05070b", "figure"), ("#05070b", "page"), "a figure vs the sheet, again"),
]


def report_palette():
    pal = palette()
    rows = sorted(((lstar(c), c, sorted(w)) for c, w in pal.items()))
    print("THE LADDER -- every value the booklet paints with, darkest first")
    print(f"  {'L*':>6}  {'hex':<9} used as")
    prev = None
    for L, c, where in rows:
        gap = "" if prev is None else f"  (+{L - prev:.1f})"
        flag = ""
        if L < 6:
            flag = "  PLUGS"
        elif L > 96:
            flag = "  BLOWS"
        if prev is not None and L - prev < 2.0 and L - prev > 0:
            flag += "  <- same ink as the one above"
        print(f"  {L:6.1f}  {c:<9} {', '.join(where[:3])}{gap}{flag}")
        prev = L

    print("\nTHE PAIRS -- values that have to be told apart on paper")
    print(f"  {'dL*':>6}  {'WCAG':>6}  what")
    bad = 0
    for (ah, ar), (bh, br), what in PAIRS:
        a, b = to_print(ah, ar), to_print(bh, br)
        d = abs(lstar(a) - lstar(b))
        verdict = ("ONE SHAPE" if d < 2 else
                   "marginal" if d < 4 else
                   "ok" if d < 8 else "clear")
        if d < 4:
            bad += 1
        print(f"  {d:6.1f}  {wcag(a, b):5.2f}:1  {what:<42} {verdict}")
    return bad


# --------------------------------------------------------- what got printed

def read_png(path):
    d = open(path, "rb").read()
    pos, idat, w = 8, b"", None
    while pos < len(d):
        ln = struct.unpack(">I", d[pos:pos + 4])[0]
        typ = d[pos + 4:pos + 8]
        if typ == b"IHDR":
            w, h, bd, ct = struct.unpack(">IIBB", d[pos + 8:pos + 18])
        elif typ == b"IDAT":
            idat += d[pos + 8:pos + 8 + ln]
        pos += 12 + ln
    raw = zlib.decompress(idat)
    bpp = {0: 1, 2: 3, 4: 2, 6: 4}[ct]
    stride = w * bpp
    prev, rows = bytearray(stride), []
    for y in range(h):
        f = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        rows.append(bytes(line))
        prev = line
    return w, h, bpp, rows


_L = [lstar(f"#{v:02x}{v:02x}{v:02x}") for v in range(256)]


def report_pages(dirname):
    names = sorted(n for n in os.listdir(dirname) if n.endswith(".png"))
    if not names:
        sys.exit(f"no page PNGs in {dirname}")
    print(f"\nWHAT GOT PRINTED -- {len(names)} pages from {dirname}")
    print(f"  {'page':<12} {'median':>7} {'p5':>6} {'p95':>6} "
          f"{'plugged':>8} {'blown':>6} {'levels':>7}")
    worst = []
    for n in names:
        w, h, bpp, rows = read_png(os.path.join(dirname, n))
        hist = [0] * 256
        step = 3                             # every third pixel is plenty
        for y in range(0, h, step):
            r = rows[y]
            for x in range(0, w, step):
                i = x * bpp
                # the eye's own weighting, then quantised back to a byte
                v = (r[i] * 54 + r[i + 1] * 183 + r[i + 2] * 19) >> 8
                hist[v] += 1
        tot = sum(hist)
        acc, pct = 0, {}
        for v in range(256):
            acc += hist[v]
            for q in (5, 50, 95):
                if q not in pct and acc >= tot * q / 100:
                    pct[q] = v
        plug = sum(hist[v] for v in range(256) if _L[v] < 6) / tot
        blow = sum(hist[v] for v in range(256) if _L[v] > 96) / tot
        used = sum(1 for v in hist if v > tot * 0.0002)
        print(f"  {n[:-4]:<12} {_L[pct[50]]:7.1f} {_L[pct[5]]:6.1f} "
              f"{_L[pct[95]]:6.1f} {plug:7.1%} {blow:5.1%} {used:7d}")
        worst.append((plug, n))
    worst.sort(reverse=True)
    print(f"\n  most plugged: {', '.join(f'{n[:-4]} {p:.0%}' for p, n in worst[:3])}")


TRIPLE_D = chr(34) * 3
TRIPLE_S = chr(39) * 3
QUOTES = chr(34) + chr(39)


def code_spans(text):
    """The parts of a source file that are CODE rather than prose.

    Comments and docstrings in figures.py quote hex values on purpose:
    they record what the colours used to be and why that was wrong. A
    levels move that rewrote those would leave the explanation saying the
    opposite of what happened.
    """
    spans, i, n = [], 0, len(text)
    start, q = 0, None
    while i < n:
        if q:
            if text.startswith(q, i):
                i += len(q)
                if len(q) == 3:
                    start = i
                q = None
                continue
            i += 2 if text[i] == chr(92) else 1
            continue
        if text.startswith(TRIPLE_D, i) or text.startswith(TRIPLE_S, i):
            # An f-triple-quote is a BLOCK OF SVG -- code that happens to be
            # written as text -- and its colours must move. A plain triple
            # quote is a docstring and must not. build_preview.py writes
            # whole pages inside f-strings, so the difference is the whole
            # difference between lifting a page and lifting its explanation.
            k = i
            while k > 0 and text[k - 1] in 'fFrRbBuU':
                k -= 1
            if 'f' in text[k:i].lower():
                i += 3
                q = None
                fence = text[i - 3:i]
                j = text.find(fence, i)
                i = len(text) if j < 0 else j + 3
                continue
            spans.append((start, i))
            q = text[i:i + 3]
            i += 3
            continue
        if text[i] in QUOTES:
            q = text[i]
            i += 1
            continue
        if text[i] == "#":
            spans.append((start, i))
            j = text.find(chr(10), i)
            i = n if j < 0 else j
            start = i
            continue
        i += 1
    spans.append((start, n))
    return spans


def apply_to_source(fn="figures.py", dry=True):
    """Put figures.py's own art colours through the levels move, once.

    The booklet's OWN art colours are rewritten here, once. The values it
    paints grounds with that come out of the game's colors.js are not: the
    game's scheme is not this booklet's to fork, so build_preview.colours()
    puts those through `to_print` as it reads them, which is what a print
    house does to a palette somebody supplies.

    This is NOT idempotent -- running it twice lifts twice.
    """
    path = os.path.join(HERE, fn)
    roles = ROLES.get(fn, {})
    src = open(path, encoding="utf-8").read()
    spans = code_spans(src)

    def in_code(pos):
        return any(a <= pos < b for a, b in spans)

    seen = {}
    for m in re.finditer(r'#[0-9a-fA-F]{6}\b', src):
        if not in_code(m.start()):
            continue
        c = m.group(0).lower()
        if c not in seen:
            seen[c] = to_print(c, roles.get(c))
    print(f"{'old':<9} {'L*':>6}   {'new':<9} {'L*':>6}  role")
    for old, new in sorted(seen.items(), key=lambda kv: lstar(kv[0])):
        role = roles.get(old, "lift")
        print(f"{old:<9} {lstar(old):6.1f} -> {new:<9} {lstar(new):6.1f}  {role}")
    if dry:
        print("\n(dry run -- pass --apply to write)")
        return
    out = re.sub(r'#[0-9a-fA-F]{6}\b',
                 lambda m: (seen[m.group(0).lower()]
                            if in_code(m.start()) and m.group(0).lower() in seen
                            else m.group(0)), src)
    open(path, "w", encoding="utf-8").write(out)
    print(f"\nwrote {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pages", help="directory of rendered page PNGs")
    ap.add_argument("--propose", metavar="FILE", nargs="?", const="figures.py",
                    help="show the levels move for a source file, change nothing")
    ap.add_argument("--apply", metavar="FILE", nargs="?", const="figures.py",
                    help="perform it. Run once per file; it is not idempotent.")
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero if a pair has collapsed")
    a = ap.parse_args()
    if a.propose or a.apply:
        apply_to_source(a.apply or a.propose, dry=not a.apply)
        return
    bad = report_palette()
    if a.pages:
        report_pages(a.pages)
    print(f"\n{bad} of {len(PAIRS)} pairs are under dL* 4 -- at or below the "
          f"edge of what survives print.")
    if a.check:
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
