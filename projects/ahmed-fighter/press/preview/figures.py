"""AHMED -- the drawings.

Every figure in the preview booklet is a path, not a photograph and not a
render: the booklet is printed and a printed page has no pixels to lose, so
the art is vector the whole way down. That is also the only way this file can
be read and corrected -- a silhouette you can argue with, rather than an image
you can only replace.

The register is Japanese animation: flat cel tones with hard edges, ink
weight that varies along a line, rim light instead of modelling, speed lines
and screentone instead of gradients. Ahmed is drawn the way an anime poster
draws its lead when the sun is behind him -- a black shape, a gold edge, and
one eye. That is a deliberate choice and not a shortcut around anatomy: a
backlit silhouette is what the Halqa looks like from outside the ring.

Coordinates are poster space, 1920 x 1080, origin top left. Nothing here
knows about the booklet; it returns SVG fragments.
"""

import math


# --------------------------------------------------------------- ink helpers

def mix(a, b, t):
    """Step one colour toward another. Used to keep the character's accent
    off everything on a face except the iris: a nose ridge or a lip edge
    wants a desaturated cousin of the rim, not the rim itself."""
    a, b = a.lstrip("#"), b.lstrip("#")
    return "#" + "".join(
        f"{round(int(a[i:i+2], 16) * (1 - t) + int(b[i:i+2], 16) * t):02x}"
        for i in (0, 2, 4))


def poly(pts, **a):
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"
    return path(d, **a)


def path(d, fill="none", stroke="none", w=0, op=None, extra=""):
    s = f'<path d="{d}" fill="{fill}"'
    if stroke != "none":
        s += f' stroke="{stroke}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"'
    if op is not None:
        s += f' opacity="{op}"'
    return s + f' {extra}/>'


def ellipse(cx, cy, rx, ry, rot=0, **a):
    d = (f"M{cx - rx:.1f},{cy:.1f} a{rx:.1f},{ry:.1f} 0 1,0 {2 * rx:.1f},0"
         f" a{rx:.1f},{ry:.1f} 0 1,0 {-2 * rx:.1f},0")
    extra = a.pop("extra", "")
    if rot:
        extra += f' transform="rotate({rot} {cx:.1f} {cy:.1f})"'
    return path(d, extra=extra, **a)


# ------------------------------------------------------------- anime devices

def speed_lines(cx, cy, r0, r1, n=120, seed=7, colour="#e7e4db", op=0.5,
                wmin=1.2, wmax=9.0, spread=math.tau, a0=0.0):
    """The burst behind an impact. Radial, uneven, thicker at the outside.

    Evenness is what makes a computer-drawn burst look computer-drawn, so the
    angle, the inner start and the weight are all jittered from one hash.
    """
    out = []
    for i in range(n):
        h = math.sin((i + 1) * 12.9898 + seed * 78.233) * 43758.5453
        j1 = h - math.floor(h)
        h2 = math.sin((i + 1) * 39.3468 + seed * 11.135) * 24634.6345
        j2 = h2 - math.floor(h2)
        a = a0 + spread * (i + 0.35 * (j1 - 0.5)) / n
        ri = r0 * (0.55 + 0.75 * j2)
        ro = r1 * (0.82 + 0.30 * j1)
        x0, y0 = cx + ri * math.cos(a), cy + ri * math.sin(a)
        x1, y1 = cx + ro * math.cos(a), cy + ro * math.sin(a)
        w = wmin + (wmax - wmin) * j2 * j2
        out.append(f'<path d="M{x0:.1f},{y0:.1f} L{x1:.1f},{y1:.1f}" '
                   f'stroke="{colour}" stroke-width="{w:.2f}" '
                   f'stroke-linecap="round" opacity="{op}" fill="none"/>')
    return "".join(out)


def rain_lines(x, y, w, h, n=70, seed=3, colour="#e7e4db", op=0.35,
               lean=-0.16, lmin=90, lmax=420):
    """Vertical speed lines -- falling, and the page that says so."""
    out = []
    for i in range(n):
        hh = math.sin((i + 1) * 21.31 + seed * 3.77) * 8123.19
        j1 = hh - math.floor(hh)
        hh2 = math.sin((i + 1) * 7.19 + seed * 51.3) * 3971.7
        j2 = hh2 - math.floor(hh2)
        px = x + w * ((i + j1) / n)
        py = y + h * j2 * 0.7
        ln = lmin + (lmax - lmin) * j1
        out.append(f'<path d="M{px:.1f},{py:.1f} L{px + ln * lean:.1f},{py + ln:.1f}" '
                   f'stroke="{colour}" stroke-width="{1 + 2.4 * j2:.2f}" '
                   f'stroke-linecap="round" opacity="{op * (0.4 + 0.6 * j1):.3f}" fill="none"/>')
    return "".join(out)


def screentone(sid, spacing=9, r=2.0, colour="#e7e4db", op=0.5, angle=18):
    """Halftone. The dot is the shading; there is no gradient in a cel."""
    return (f'<pattern id="{sid}" width="{spacing}" height="{spacing}" '
            f'patternUnits="userSpaceOnUse" patternTransform="rotate({angle})">'
            f'<circle cx="{spacing / 2:.2f}" cy="{spacing / 2:.2f}" r="{r}" '
            f'fill="{colour}" opacity="{op}"/></pattern>')


def hatch(sid, spacing=7, w=1.6, colour="#090b0f", op=0.55, angle=-38):
    return (f'<pattern id="{sid}" width="{spacing}" height="{spacing}" '
            f'patternUnits="userSpaceOnUse" patternTransform="rotate({angle})">'
            f'<path d="M0,0 L0,{spacing}" stroke="{colour}" stroke-width="{w}" '
            f'opacity="{op}"/></pattern>')


def impact_star(cx, cy, r, points=14, inner=0.34, seed=5, fill="#efece4", op=1.0):
    """The flash at the contact frame. Jagged, never regular."""
    pts = []
    for i in range(points * 2):
        h = math.sin((i + 1) * 17.77 + seed * 5.13) * 5311.7
        j = h - math.floor(h)
        rr = r * ((0.80 + 0.34 * j) if i % 2 == 0 else inner * (0.7 + 0.7 * j))
        a = math.tau * i / (points * 2) - 0.4
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return poly(pts, fill=fill, op=op)


# ----------------------------------------------------------------- the face

# WHY THERE IS A GRAMMAR HERE AT ALL. Every face in the first booklet was two
# coloured bars on a black oval, and every one of them read as a VISOR rather
# than a face -- goggles on the bosses, a cyclops slit on Ahmed. The cause was
# not the bars. It was that the figure ink (#06080d) and the page ground
# (#05070b) are the same colour to within 1.01:1 contrast, so a head had no
# SURFACE: the only marks a reader could see were the ones that glowed, and a
# glowing mark with nothing around it is hardware, not anatomy.
#
# So a face is built in this order, and the order is the whole trick:
#
#   1. a CEL PLANE -- one hard-edged shape in `tone`, a step above ink, on the
#      side the light comes from. This is the surface. Without it nothing
#      below can be read as sitting ON anything.
#   2. the BROW, the heaviest mark on the face and the one that carries the
#      character's temper. Ink, so it reads as a shadow on the plane.
#   3. the EYE, which is FOUR marks and not one: a socket shadow, a lit sliver
#      of sclera, an iris in the character's own colour, and -- only for the
#      one character who still hopes -- a catchlight. An eye this size cannot
#      be more than about a fifth of the head's width. The old bars were very
#      nearly half, which is exactly the width of a pair of goggles.
#   4. a NOSE tick and a MOUTH line, one stroke each.
#   5. the RIM, which was already there, running the lit contour.
#
# The character's accent colour is allowed on the IRIS and nowhere else on the
# face. Menace in anime is a small bright iris under a heavy brow, never a
# wide bright band -- the band is a welding mask.
#
# Everything is expressed as a fraction of the head's own radii, so the same
# call works on ZAYOS's 62-unit skull and on the falling Ahmed's 42-unit one.

MOODS = {
    # brow angle (+ = inner end low, the set brow), brow weight, lid drop,
    # mouth angle, mouth width
    "set":    (0.13, 1.05, 0.24, -0.01, 0.30),    # young, level, still asking
    "narrow": (0.21, 1.10, 0.46, -0.16, 0.24),    # impatient, done asking
    "heavy":  (0.14, 1.30, 0.34, 0.00, 0.30),     # settled, unbothered
    "dull":   (-0.05, 1.50, 0.56, 0.02, 0.15),    # slow, and only one idea
    "wide":   (-0.14, 0.85, -0.12, 0.00, 0.28),   # falling
}


_FACE_N = [0]


def face(cx, cy, rx, ry, ink="#090b0f", tone="#262b3b", rim="#e5b750",
         iris=None, mood="set", lit=1, turn=0.0, catch=False, open_mouth=False,
         plane=True, gaze=(0.0, 0.0), tilt=0.0):
    """One face, built plane-first. Returns SVG.

    cx, cy, rx, ry  the skull this face belongs to.
    lit             +1 if the light is on our right, -1 if on our left.
    turn            -1 full profile away from us, 0 front on, +1 toward us.
                    Shifts and compresses the far eye the way a turned head
                    does, so one function draws front, three-quarter and
                    near-profile without three sets of coordinates.
    iris            the character's accent. None leaves the eye unlit, which
                    is what a face in full shadow actually looks like. It is
                    the ONLY place on a face the accent is allowed; a nose
                    ridge or a lip edge gets a stepped-back cousin of it.
    gaze            (x, y) in eye-widths, ONE value for both eyes. Where a
                    person is looking is a single fact about them; the first
                    draft offset each iris by its own side and they ended up
                    looking in opposite directions.
    tilt            degrees, for a head that is not upright -- AL-SAQR's is
                    drawn at 14 and the crowd's lean up to 11.

    Sizes worth knowing, because they are what stops this becoming a visor
    again: an eye is 0.24 of the head's half-width, the pair plus the gap
    comes to a little over half the face, and the sclera never runs the full
    width of the socket. The bars this replaced were 0.45 each and ran edge
    to edge -- the proportions of goggles, which is what they looked like.
    """
    ba, bw, lid, ma, mw = MOODS[mood]
    g = []
    # a facial mark has to be darker than the head it is on, or it is a hole
    # in the silhouette rather than a shadow on a face
    dark = mix(ink, "#000000", 0.45)
    soft = mix(rim, tone, 0.62)      # the accent, stepped most of the way back
    near = -lit                      # the eye on the shadow side is the near one
    eyey = cy + 0.07 * ry
    # --- 1. the cel plane: a crescent of lit cheek down the outer third of
    #        the face. Wider than this and it reads as a half-mask.
    if plane:
        L = lit
        # an ambient pass over the whole face first. Without it the brow, the
        # nose and the mouth sit on ink at 1.01:1 against the page and simply
        # are not there -- which is the failure this whole grammar exists to
        # undo, reintroduced one layer lower down.
        # Measured: at 0.10 a brow on the SHADOW side of a face sat 2.4 L*
        # from the face under it, which is a just-visible edge on coated
        # stock and nothing at all on uncoated. The sky fills the shadow side
        # of anything standing outdoors, and this is that fill.
        g.append(ellipse(cx, cy + ry * 0.04, rx * 0.96, ry * 0.94,
                         fill=tone, op=0.22))
        g.append(path(
            f"M{cx + L * rx * 0.34:.1f},{cy - ry * 0.82:.1f} "
            f"C{cx + L * rx * 0.92:.1f},{cy - ry * 0.60:.1f} "
            f"{cx + L * rx * 1.00:.1f},{cy - ry * 0.06:.1f} "
            f"{cx + L * rx * 0.86:.1f},{cy + ry * 0.44:.1f} "
            f"C{cx + L * rx * 0.68:.1f},{cy + ry * 0.86:.1f} "
            f"{cx + L * rx * 0.34:.1f},{cy + ry * 1.02:.1f} "
            f"{cx + L * rx * 0.04:.1f},{cy + ry * 1.00:.1f} "
            f"C{cx + L * rx * 0.30:.1f},{cy + ry * 0.66:.1f} "
            f"{cx + L * rx * 0.42:.1f},{cy + ry * 0.12:.1f} "
            f"{cx + L * rx * 0.34:.1f},{cy - ry * 0.82:.1f} Z", fill=tone))
    # --- the eyes. Near eye full size, far eye compressed by the turn.
    for side, wide in ((near, 1.0), (-near, 1.0 - 0.52 * abs(turn))):
        if wide < 0.22:
            continue                                  # turned too far to see
        ex = cx + side * rx * (0.40 - 0.14 * turn * side * lit)
        ew, eh = rx * 0.24 * wide, ry * 0.145
        # 3a. socket shadow -- the eye sits IN the head, not on it, and
        #     everything in the socket is clipped TO the socket so a heavy
        #     lid cannot escape past the brow as a dark lump
        _FACE_N[0] += 1
        eid = f"eye{_FACE_N[0]}"
        g.append(f'<clipPath id="{eid}"><ellipse cx="{ex:.1f}" '
                 f'cy="{eyey + ry * 0.01:.1f}" rx="{ew * 1.30:.1f}" '
                 f'ry="{eh * 1.44:.1f}"/></clipPath>')
        g.append(ellipse(ex, eyey + ry * 0.01, ew * 1.30, eh * 1.44,
                         fill=dark, op=0.92))
        g.append(f'<g clip-path="url(#{eid})">')
        # 3b. the lit sclera, an almond, never the whole socket
        g.append(path(f"M{ex - ew:.1f},{eyey + eh * 0.16:.1f} "
                      f"C{ex - ew * 0.52:.1f},{eyey - eh * 0.96:.1f} "
                      f"{ex + ew * 0.52:.1f},{eyey - eh * 0.96:.1f} "
                      f"{ex + ew:.1f},{eyey + eh * 0.06:.1f} "
                      f"C{ex + ew * 0.5:.1f},{eyey + eh * 0.84:.1f} "
                      f"{ex - ew * 0.5:.1f},{eyey + eh * 0.84:.1f} "
                      f"{ex - ew:.1f},{eyey + eh * 0.16:.1f} Z",
                      fill="#dcd7c9", op=0.72))
        # 3c. the iris, sitting ON the lower lid, the one place the accent
        #     colour is allowed on a face
        ix = ex + max(-0.52, min(0.52, gaze[0])) * ew
        iy = eyey + eh * (0.16 + max(-0.5, min(0.5, gaze[1])) * 0.7)
        g.append(ellipse(ix, iy, ew * 0.34, eh * 0.62, fill=iris or dark))
        g.append(ellipse(ix, iy, ew * 0.18, eh * 0.32, fill=dark))
        if catch:
            g.append(ellipse(ix - ew * 0.18, iy - eh * 0.26,
                             ew * 0.13, eh * 0.20, fill="#efece4"))
        # 3d. the upper lid, dropped by the mood, and heavier than the lower
        if lid > 0.01:
            # the lid IS the socket, slid down over the eye. Drawing it as a
            # capped band instead left a square corner above the brow on the
            # heavier moods, which read as a notch cut out of the head.
            # placed so that at lid=0 its lower edge just grazes the top of
            # the sclera, and at lid=0.46 it has come down to the iris
            g.append(ellipse(ex, eyey - eh * (2.40 - 1.70 * lid),
                             ew * 1.62, eh * 1.44, fill=dark))
        g.append("</g>")
        g.append(path(f"M{ex - ew * 1.06:.1f},{eyey + eh * 0.20:.1f} "
                      f"C{ex - ew * 0.52:.1f},{eyey - eh * (1.02 - lid * 1.7):.1f} "
                      f"{ex + ew * 0.52:.1f},{eyey - eh * (1.02 - lid * 1.7):.1f} "
                      f"{ex + ew * 1.06:.1f},{eyey + eh * 0.06:.1f}",
                      stroke=dark, w=max(1.3, eh * 0.46)))
        # --- 2. the brow, the heaviest thing on the face, and the only mark
        #        with a lit top edge -- a brow ridge is what catches a rim
        by = eyey - ry * 0.30
        rise = -side * ba * ry
        brow = (f"M{ex - ew * 1.34:.1f},{by - rise:.1f} "
                f"C{ex - ew * 0.4:.1f},{by - ry * 0.075 - rise * 0.4:.1f} "
                f"{ex + ew * 0.5:.1f},{by - ry * 0.065 + rise * 0.5:.1f} "
                f"{ex + ew * 1.28:.1f},{by + rise:.1f} "
                f"L{ex + ew * 1.20:.1f},{by + rise + ry * 0.026 * bw:.1f} "
                f"C{ex + ew * 0.4:.1f},{by + ry * 0.015 + rise * 0.5:.1f} "
                f"{ex - ew * 0.4:.1f},{by + ry * 0.005 - rise * 0.4:.1f} "
                f"{ex - ew * 1.28:.1f},{by - rise + ry * 0.095 * bw:.1f} Z")
        g.append(path(brow, fill=dark))
        if side == lit:
            # a brow ridge catches light along its own crest and nowhere
            # else; the first pass swept this arc the width of the face and
            # it read as a scar
            g.append(path(f"M{ex - ew * 0.18:.1f},"
                          f"{by - ry * 0.058 - rise * 0.18:.1f} "
                          f"C{ex + ew * 0.16:.1f},{by - ry * 0.072:.1f} "
                          f"{ex + ew * 0.46:.1f},{by - ry * 0.066 + rise * 0.2:.1f} "
                          f"{ex + ew * 0.70:.1f},{by + rise * 0.34 - ry * 0.030:.1f}",
                          stroke=soft, w=max(1.0, ry * 0.022), op=0.52))
    # --- 4. nose: one short line down the bridge, and the light on its ridge
    nx = cx + lit * rx * 0.05
    g.append(path(f"M{nx:.1f},{cy - ry * 0.10:.1f} "
                  f"C{nx + lit * rx * 0.06:.1f},{cy + ry * 0.14:.1f} "
                  f"{nx + lit * rx * 0.09:.1f},{cy + ry * 0.30:.1f} "
                  f"{nx + lit * rx * 0.07:.1f},{cy + ry * 0.38:.1f} "
                  f"C{nx + lit * rx * 0.05:.1f},{cy + ry * 0.43:.1f} "
                  f"{nx - lit * rx * 0.02:.1f},{cy + ry * 0.44:.1f} "
                  f"{nx - lit * rx * 0.05:.1f},{cy + ry * 0.42:.1f}",
                  stroke=dark, w=max(1.2, ry * 0.040), op=0.85))
    g.append(path(f"M{nx + lit * rx * 0.08:.1f},{cy + ry * 0.22:.1f} "
                  f"C{nx + lit * rx * 0.11:.1f},{cy + ry * 0.31:.1f} "
                  f"{nx + lit * rx * 0.10:.1f},{cy + ry * 0.36:.1f} "
                  f"{nx + lit * rx * 0.06:.1f},{cy + ry * 0.39:.1f}",
                  stroke=soft, w=max(1.0, ry * 0.024), op=0.62))
    # --- 4b. mouth: one thin line, or a jaw opened
    my = cy + ry * 0.64
    mwx = rx * mw
    if open_mouth:
        mouth = (f"M{cx - mwx * 0.66:.1f},{my - ry * 0.02:.1f} "
                 f"C{cx - mwx * 0.28:.1f},{my + ry * 0.22:.1f} "
                 f"{cx + mwx * 0.28:.1f},{my + ry * 0.22:.1f} "
                 f"{cx + mwx * 0.66:.1f},{my - ry * 0.02:.1f} "
                 f"C{cx + mwx * 0.28:.1f},{my + ry * 0.04:.1f} "
                 f"{cx - mwx * 0.28:.1f},{my + ry * 0.04:.1f} "
                 f"{cx - mwx * 0.66:.1f},{my - ry * 0.02:.1f} Z")
        g.append(path(mouth, fill="#1e1a1d"))
        g.append(path(mouth, stroke=dark, w=max(1.2, ry * 0.034)))
        g.append(path(f"M{cx - mwx * 0.40:.1f},{my + ry * 0.175:.1f} "
                      f"C{cx - mwx * 0.14:.1f},{my + ry * 0.225:.1f} "
                      f"{cx + mwx * 0.14:.1f},{my + ry * 0.225:.1f} "
                      f"{cx + mwx * 0.40:.1f},{my + ry * 0.175:.1f}",
                      stroke=soft, w=max(1.0, ry * 0.026), op=0.60))
    else:
        g.append(path(f"M{cx - mwx:.1f},{my - ma * ry:.1f} "
                      f"C{cx - mwx * 0.3:.1f},{my + ry * 0.025:.1f} "
                      f"{cx + mwx * 0.3:.1f},{my + ry * 0.025:.1f} "
                      f"{cx + mwx:.1f},{my + ma * ry:.1f}",
                      stroke=dark, w=max(1.2, ry * 0.038), op=0.95))
    # --- 5. the lit edge of the lower lip. Only on the lit side of the
    #        centreline, and only when the mouth is shut -- run across the
    #        whole mouth it bulges downward under the lip line and every
    #        character in the booklet reads as quietly amused.
    if not open_mouth:
        g.append(path(f"M{cx + lit * mwx * 0.86:.1f},{my + ry * 0.04:.1f} "
                      f"C{cx + lit * mwx * 0.52:.1f},{my + ry * 0.065:.1f} "
                      f"{cx + lit * mwx * 0.26:.1f},{my + ry * 0.065:.1f} "
                      f"{cx + lit * mwx * 0.06:.1f},{my + ry * 0.04:.1f}",
                      stroke=soft, w=max(1.0, ry * 0.026), op=0.46))
    body = "".join(g)
    if tilt:
        return f'<g transform="rotate({tilt} {cx:.1f} {cy:.1f})">{body}</g>'
    return body


# --------------------------------------------------------------------- AHMED

def ahmed_cross(ink="#090b0f", cloth="#21283f", tone="#2d3448", rim="#e5b750",
                cool="#517baf", wrap="#cd1932"):
    """The lead, throwing a cross at the camera. Backlit.

    The pose is the one frame an anime picks for a poster: the arm already
    committed, the fist nearest the lens and out of scale with the rest of
    him, the body still turning after it. He is drawn in layers back to
    front -- rear leg, front leg, body, guard arm, punching arm, fist --
    because a silhouette assembled that way can be corrected a limb at a
    time, and one enormous path cannot.
    """
    g = []

    # --- rear leg (his left). Driving; the punch comes off this foot.
    g.append(path("M1372,742 C1428,758 1470,806 1488,874 "
                  "C1506,944 1518,1010 1524,1080 L1400,1080 "
                  "C1394,1002 1382,938 1362,890 C1344,846 1338,796 1348,752 Z",
                  fill=ink))
    # --- front leg (his right). Bladed, turned over with the hip.
    g.append(path("M1286,752 C1252,796 1230,856 1216,928 "
                  "C1206,984 1200,1032 1198,1080 L1318,1080 "
                  "C1322,1016 1332,958 1350,908 C1368,858 1374,802 1362,758 Z",
                  fill=ink))
    g.append(path("M1362,758 C1374,802 1368,858 1350,908 L1312,904 "
                  "C1330,856 1338,804 1330,760 Z", fill=tone, op=0.55))

    # --- shorts. A waistband is the only straight line below his ribs.
    g.append(path("M1244,752 C1290,774 1360,780 1420,766 "
                  "C1442,808 1456,852 1462,896 "
                  "C1420,916 1360,920 1312,906 C1300,862 1276,806 1244,752 Z",
                  fill=cloth))
    g.append(path("M1420,766 C1442,808 1456,852 1462,896 L1424,906 "
                  "C1420,860 1408,814 1390,774 Z", fill=tone, op=0.9))
    g.append(path("M1248,760 C1296,784 1364,790 1424,774", stroke=rim, w=4, op=0.45))
    g.append(path("M1226,916 C1248,932 1276,936 1300,928", stroke=rim, w=4, op=0.35))

    # --- trunk and head, one silhouette.
    g.append(path(
        "M1300,228 C1358,228 1394,272 1392,326 C1390,366 1374,398 1352,418 "
        "C1344,434 1344,450 1352,462 C1414,480 1462,506 1488,544 "
        "C1512,580 1524,634 1528,694 C1532,748 1528,790 1516,808 "
        "C1470,826 1400,834 1330,826 C1276,820 1236,804 1216,782 "
        "C1204,740 1200,690 1206,640 C1212,582 1228,536 1252,506 "
        "C1272,482 1296,468 1318,460 C1326,448 1326,432 1318,418 "
        "C1292,398 1274,364 1272,322 C1270,270 1290,232 1300,228 Z",
        fill=ink))
    # --- the face. He is the only one in the booklet with a catchlight,
    #     because he is the only one still asking where the hole is.
    g.append('<clipPath id="ahface"><path d="M1300,228 C1358,228 1394,272 '
             '1392,326 C1390,366 1374,398 1352,418 C1340,430 1326,432 '
             '1318,418 C1292,398 1274,364 1272,322 C1270,270 1290,232 '
             '1300,228 Z"/></clipPath>')
    g.append('<g clip-path="url(#ahface)">')
    g.append(face(1318, 320, 47, 68, tone="#2f2a3c", rim=rim, iris="#e0bc63",
                  mood="set", lit=1, turn=0.50, catch=True, gaze=(0.20, 0.0)))
    g.append("</g>")
    g.append(path("M1352,300 C1372,304 1384,318 1388,338", stroke=rim, w=4, op=0.62))

    # --- the vest. Cloth is the one thing on him with a straight edge.
    g.append(path("M1330,462 C1374,472 1416,490 1444,516 "
                  "C1470,556 1484,614 1488,676 C1492,726 1490,768 1482,796 "
                  "C1438,812 1384,816 1332,810 C1288,804 1256,792 1240,776 "
                  "C1230,732 1228,682 1234,632 C1240,578 1254,534 1274,508 "
                  "C1290,488 1310,472 1330,462 Z", fill=cloth))
    g.append(path("M1444,516 C1470,556 1484,614 1488,676 C1492,726 1490,768 1482,796 "
                  "L1430,804 C1442,752 1444,690 1436,628 C1430,578 1420,542 1408,516 Z",
                  fill=tone))
    # the hollow of the sternum, one hard cel edge and nothing else
    g.append(path("M1320,506 C1340,556 1348,626 1344,700 C1342,748 1336,782 1328,806 "
                  "L1300,802 C1310,764 1316,714 1316,660 C1316,592 1308,542 1294,508 Z",
                  fill=ink, op=0.55))

    # --- hair. Swept off the punch, all of it going one way.
    g.append(path("M1266,318 C1254,254 1290,212 1340,212 C1396,212 1424,252 1420,308 "
                  "C1418,332 1410,348 1400,356 C1404,328 1396,308 1380,300 "
                  "C1384,320 1378,334 1366,340 C1360,316 1342,302 1318,302 "
                  "C1298,302 1282,312 1272,330 Z", fill=ink))
    # one swept mass first, then the strands that break its edge
    g.append(path("M1296,244 C1330,196 1400,174 1462,196 C1510,214 1512,272 1486,316 "
                  "C1466,350 1432,368 1400,364 C1412,330 1408,292 1388,268 "
                  "C1364,240 1326,234 1296,244 Z", fill=ink))
    for d in (
        "M1332,206 C1376,172 1442,168 1486,192 C1436,188 1390,198 1356,224 Z",
        "M1396,212 C1444,196 1506,208 1534,244 C1486,222 1438,222 1404,238 Z",
        "M1440,258 C1486,254 1532,282 1544,320 C1512,290 1470,276 1440,276 Z",
        "M1456,318 C1490,332 1512,364 1510,398 C1494,366 1470,346 1444,338 Z",
        "M1292,236 C1276,220 1252,210 1230,212 C1256,222 1274,236 1284,254 Z",
    ):
        g.append(path(d, fill=ink))

    # --- guard arm (his left). The hand is at the jaw and the elbow is out
    #     past his own edge -- both clear of the trunk, or neither reads.
    g.append(path("M1466,494 C1514,520 1548,570 1560,630 "
                  "C1570,680 1560,716 1536,730 C1512,744 1488,728 1480,696 "
                  "C1472,662 1478,618 1492,584 C1502,558 1500,528 1486,506 Z",
                  fill=ink))
    g.append(path("M1536,730 C1508,742 1482,730 1472,702 "
                  "C1458,664 1466,614 1486,572 C1504,534 1508,492 1496,462 "
                  "L1444,452 C1438,494 1426,536 1408,574 "
                  "C1386,622 1388,678 1414,714 C1438,748 1506,754 1536,730 Z",
                  fill=ink))
    g.append(path("M1444,452 C1438,494 1426,536 1408,574 C1386,622 1388,678 1414,714 "
                  "L1442,706 C1420,672 1420,624 1438,578 C1454,538 1466,494 1468,458 Z",
                  fill=tone, op=0.85))
    g.append(ellipse(1452, 428, 58, 50, rot=-20, fill=ink))
    g.append(path("M1410,408 C1432,388 1474,388 1494,410 L1496,432 "
                  "C1468,414 1434,416 1410,434 Z", fill=tone))
    g.append(path("M1408,454 C1438,476 1476,476 1500,456 L1504,484 "
                  "C1470,506 1430,504 1402,480 Z", fill=wrap, op=0.92))
    for d, wdt, o in (("M1496,410 C1514,424 1520,444 1516,462", 5, 0.9),
                      ("M1504,486 C1524,514 1534,548 1532,578", 5, 0.75),
                      ("M1552,600 C1566,644 1568,690 1552,718", 5, 0.85),
                      ("M1410,576 C1390,624 1392,678 1416,714", 4, 0.5)):
        g.append(path(d, stroke=rim, w=wdt, op=o))

    # --- punching arm. A cone that widens toward the lens, not a tube.
    g.append(path("M1236,452 C1180,478 1114,522 1044,572 "
                  "C1000,604 972,632 960,656 L1006,772 "
                  "C1040,766 1086,736 1138,692 C1190,648 1232,606 1258,570 Z",
                  fill=ink))
    g.append(path("M1236,452 C1180,478 1114,522 1044,572 C1016,592 996,610 982,626 "
                  "L1002,672 C1028,644 1072,610 1124,574 C1176,538 1222,512 1254,500 Z",
                  fill=tone, op=0.75))

    # --- the wrist, wrapped. The one colour on him, and it is the flag's red.
    g.append(path("M1004,600 C1030,588 1060,590 1080,606 "
                  "C1092,646 1096,700 1090,754 C1066,772 1034,774 1010,758 "
                  "C998,706 996,648 1004,600 Z", fill=wrap))
    g.append(path("M1080,606 C1092,646 1096,700 1090,754 L1062,766 "
                  "C1072,708 1070,650 1056,602 Z", fill="#951927"))
    for yy in (638, 682, 726):
        g.append(path(f"M1006,{yy} C1034,{yy - 10} 1062,{yy - 8} 1088,{yy + 2}",
                      stroke="#090b0f", w=3.5, op=0.5))

    # --- the fist, nearest the lens and out of scale on purpose.
    g.append(path("M958,548 C884,534 812,566 782,626 C752,688 774,760 836,796 "
                  "C900,832 984,818 1024,764 C1054,724 1058,664 1036,612 "
                  "C1020,574 992,554 958,548 Z", fill=ink))
    # knuckles: four ridges, lit along their top edge only
    for i, (kx, ky, kr, ka) in enumerate(((832, 606, 34, -22), (886, 584, 38, -12),
                                          (944, 582, 37, -4), (996, 602, 32, 6))):
        g.append(ellipse(kx, ky, kr, kr * 0.82, rot=ka, fill=tone, op=0.85))
        g.append(path(f"M{kx - kr * 0.8:.0f},{ky - kr * 0.42:.0f} "
                      f"C{kx - kr * 0.4:.0f},{ky - kr * 0.92:.0f} "
                      f"{kx + kr * 0.4:.0f},{ky - kr * 0.92:.0f} "
                      f"{kx + kr * 0.8:.0f},{ky - kr * 0.40:.0f}",
                      stroke=rim, w=4.5, op=0.85 - 0.08 * i))
    for d in ("M846,636 C844,672 848,704 858,732",
              "M900,616 C898,658 902,696 912,728",
              "M956,614 C956,656 960,692 970,722"):
        g.append(path(d, stroke=tone, w=5, op=0.9))
    # the thumb, laid across the fingers the way a wrapped hand closes
    g.append(path("M964,706 C1006,700 1036,684 1046,660 "
                  "C1054,690 1042,726 1010,748 C980,768 942,768 916,752 "
                  "C932,742 952,726 964,706 Z", fill=tone, op=0.95))
    g.append(path("M1046,660 C1054,690 1042,726 1010,748", stroke=rim, w=4, op=0.6))
    g.append(path("M800,700 C840,742 908,760 974,742 L982,772 "
                  "C906,794 830,772 790,724 Z", fill=ink, op=0.55))

    # --- rim light. The sun is behind him, so it runs the far edge, and it
    #     breaks wherever the form turns away from it.
    for d, wdt, o in (
        ("M1302,230 C1360,230 1394,274 1392,328", 7, 1.00),
        ("M1388,352 C1378,384 1364,404 1350,418", 5, 0.85),
        ("M1356,462 C1416,480 1462,506 1488,544", 8, 1.00),
        ("M1496,558 C1518,594 1528,646 1530,698", 6, 0.92),
        ("M1524,742 C1522,776 1518,798 1512,810", 5, 0.68),
        ("M1500,742 C1520,764 1508,806 1500,832", 4, 0.55),
        ("M1480,874 C1500,942 1514,1012 1522,1080", 6, 0.80),
        ("M1258,470 C1216,494 1190,528 1170,562", 4, 0.50),
        ("M1044,574 C1006,600 982,624 968,646", 4, 0.45),
    ):
        g.append(path(d, stroke=rim, w=wdt, op=o))
    for d, wdt, o in (("M1288,752 C1250,802 1226,870 1212,944", 4, 0.50),
                      ("M1216,782 C1206,740 1202,690 1208,640", 3, 0.38)):
        g.append(path(d, stroke=cool, w=wdt, op=o))



    return "".join(g)


# ------------------------------------------------------- the rest of the cast

def ahmed_falling(x, y, s=1.0, rot=24, ink="#090b0f", rim="#e5b750", wrap="#cd1932"):
    """Him, going down the hole. Limbs out, nothing to hold.

    Drawn small and tumbling: the page it sits on is mostly empty air, and a
    figure that filled it would stop the fall reading as a fall.
    """
    g = [f'<g transform="translate({x},{y}) scale({s}) rotate({rot})">']
    g.append(path("M-30,-160 C-10,-196 46,-194 64,-160 C40,-172 4,-174 -20,-162 Z", fill=ink))
    g.append(path("M-34,-84 C-6,-96 28,-94 50,-80 C64,-30 66,34 52,84 "
                  "C20,96 -14,94 -38,82 C-48,30 -48,-34 -34,-84 Z", fill=ink))
    # the head goes on AFTER the trunk: tumbling, he comes at us face
    # first, and drawn the other way round his own chest covered his mouth
    g.append(ellipse(0, -120, 42, 46, fill=ink))
    g.append('<clipPath id="flface"><ellipse cx="0" cy="-120" rx="42" ry="46"/>'
             '</clipPath>')
    g.append('<g clip-path="url(#flface)">')
    # his eyes are turned back up toward the light he is falling away from.
    # He is looking at the hole. That is the whole page.
    g.append(face(0, -118, 42, 46, tone="#282e41", rim=rim, iris="#e0bc63",
                  mood="wide", lit=1, turn=0.12, catch=True, open_mouth=True,
                  gaze=(0.0, -0.46)))
    g.append("</g>")
    g.append(path("M-34,-78 C-78,-52 -124,-4 -152,52 L-118,78 "
                  "C-92,26 -54,-14 -22,-38 Z", fill=ink))
    g.append(ellipse(-140, 70, 26, 24, rot=20, fill=ink))
    g.append(path("M50,-76 C96,-96 150,-96 190,-76 L184,-40 "
                  "C146,-56 100,-54 60,-38 Z", fill=ink))
    g.append(ellipse(196, -60, 26, 24, rot=-14, fill=ink))
    g.append(path("M-36,78 C-64,120 -80,172 -84,222 L-42,230 "
                  "C-34,186 -20,146 -2,116 Z", fill=ink))
    g.append(path("M40,84 C72,122 96,172 106,224 L66,238 "
                  "C50,190 28,150 6,120 Z", fill=ink))
    g.append(path("M-134,60 C-118,50 -100,52 -90,62 L-96,84 "
                  "C-110,74 -126,74 -140,82 Z", fill=wrap, op=0.9))
    g.append(path("M182,-72 C194,-80 210,-78 218,-68 L212,-48 "
                  "C202,-58 188,-58 176,-50 Z", fill=wrap, op=0.9))
    for d, w in (("M-30,-160 C-10,-192 44,-192 62,-160", 5),
                 ("M50,-80 C64,-30 66,34 52,84", 4),
                 ("M52,-74 C96,-94 148,-94 186,-76", 4),
                 ("M40,86 C72,124 94,172 104,222", 4)):
        g.append(path(d, stroke=rim, w=w, op=0.75))
    g.append("</g>")
    return "".join(g)


def wahsh(x, y, s=1.0, ink="#090b0f", tone="#2d252d", rim="#de5aee"):
    """AL-WAHSH. Not a monster -- what staying looks like when you are
    very good at it. Read as mass: the shoulders arrive before the head."""
    g = [f'<g transform="translate({x},{y}) scale({s})">']
    g.append(path("M-250,520 C-260,380 -232,262 -176,182 "
                  "C-136,126 -86,96 -46,88 C-30,116 30,116 46,88 "
                  "C86,96 136,126 176,182 C232,262 260,380 250,520 Z", fill=ink))
    g.append(ellipse(0, 16, 72, 80, fill=ink))
    g.append('<clipPath id="whface"><ellipse cx="0" cy="16" rx="72" ry="80"/>'
             '</clipPath>')
    g.append('<g clip-path="url(#whface)">')
    # he is not a monster -- the brow is heavy and the eyes are half shut
    # because he is unbothered, not because he is snarling
    g.append(face(0, 24, 60, 66, tone="#382d3a", rim=rim, iris="#ea88fa",
                  mood="heavy", lit=1, turn=0.0, gaze=(0.0, 0.0)))
    g.append("</g>")
    g.append(path("M-84,-4 C-76,-86 -40,-132 0,-132 C40,-132 76,-86 84,-4 "
                  "C62,-42 34,-60 0,-60 C-34,-60 -62,-42 -84,-4 Z", fill=ink))
    g.append(path("M-46,88 C-30,116 30,116 46,88 C22,100 -22,100 -46,88 Z",
                  fill=tone, op=0.9))
    g.append(path("M-190,168 C-246,214 -286,300 -300,404 L-232,424 "
                  "C-218,340 -190,272 -152,228 Z", fill=ink))
    g.append(path("M190,168 C246,214 286,300 300,404 L232,424 "
                  "C218,340 190,272 152,228 Z", fill=ink))
    g.append(ellipse(-272, 452, 62, 56, rot=14, fill=ink))
    g.append(ellipse(272, 452, 62, 56, rot=-14, fill=ink))
    g.append(path("M-120,190 C-60,224 60,224 120,190 C142,290 148,404 140,520 L-140,520 "
                  "C-148,404 -142,290 -120,190 Z", fill=tone, op=0.85))

    for d, w, o in (("M88,-2 C80,-82 42,-126 0,-126", 7, 0.9),
                    ("M176,182 C232,262 258,376 250,510", 8, 0.95),
                    ("M194,172 C248,216 286,300 300,400", 6, 0.8),
                    ("M-176,182 C-226,254 -252,352 -250,470", 5, 0.45)):
        g.append(path(d, stroke=rim, w=w, op=o))
    g.append("</g>")
    return "".join(g)


def saqr(x, y, s=1.0, ink="#090b0f", tone="#192f3b", rim="#53b1fa"):
    """AL-SAQR. All legs, no patience -- so he is caught at the top of a head
    kick, where the leg is the whole drawing.

    The leg goes up on the far side from the head and the trunk lays back
    away from it. Drawn the other way round the two merge into one shape and
    the kick stops being a kick. Origin is the standing foot."""
    g = [f'<g transform="translate({x},{y}) scale({s})">']

    # standing leg, straight under him
    g.append(path("M-34,0 C-40,-70 -36,-150 -20,-214 L44,-204 "
                  "C34,-146 34,-70 38,0 Z", fill=ink))
    g.append(path("M-52,0 C-24,-14 26,-14 56,0 L58,26 L-56,26 Z", fill=ink))

    # hips and trunk, laid back away from the kick
    g.append(path("M-26,-206 C10,-222 56,-216 76,-192 "
                  "C104,-158 124,-104 134,-44 "
                  "C120,-16 62,-6 30,-22 C6,-84 -14,-150 -26,-206 Z", fill=ink))
    g.append(path("M76,-192 C104,-158 124,-104 134,-44 L98,-30 "
                  "C88,-92 70,-146 46,-186 Z", fill=tone, op=0.85))
    g.append(path("M24,-330 C60,-350 104,-336 116,-298 "
                  "C130,-254 132,-210 122,-178 C94,-166 58,-172 40,-192 "
                  "C26,-240 22,-292 24,-330 Z", fill=ink))
    g.append(ellipse(96, -392, 44, 50, rot=14, fill=ink))
    g.append('<clipPath id="sqface"><ellipse cx="96" cy="-392" rx="44" ry="50" '
             'transform="rotate(14 96 -392)"/></clipPath>')
    g.append('<g clip-path="url(#sqface)">')
    # he looks down the line of the kick, at the target, never at us
    g.append(face(86, -390, 40, 50, tone="#213a46", rim=rim, iris="#77c8f7",
                  mood="narrow", lit=1, turn=0.52, gaze=(-0.42, 0.22),
                  tilt=14))
    g.append("</g>")
    g.append(path("M52,-420 C78,-456 142,-456 162,-418 "
                  "C134,-434 96,-436 64,-424 Z", fill=ink))
    for d in ("M150,-450 C184,-462 218,-450 232,-426 C204,-440 178,-442 156,-436 Z",
              "M158,-422 C192,-422 220,-404 230,-380 C208,-394 184,-400 162,-400 Z",
              "M154,-392 C182,-382 200,-360 202,-338 C188,-356 170,-366 152,-370 Z"):
        g.append(path(d, fill=ink))

    # the kicking leg -- hip, knee, shin, foot, all clear of the trunk
    g.append(path("M-18,-214 C-84,-236 -152,-262 -206,-292 "
                  "C-230,-306 -238,-330 -224,-350 C-210,-370 -184,-372 -162,-358 "
                  "C-116,-330 -58,-306 -6,-292 Z", fill=ink))
    g.append(path("M-224,-350 C-250,-386 -272,-430 -284,-474 "
                  "C-290,-500 -276,-522 -252,-528 C-228,-534 -206,-520 -200,-494 "
                  "C-190,-456 -174,-420 -154,-392 Z", fill=ink))
    g.append(path("M-284,-474 C-300,-498 -326,-512 -356,-510 "
                  "C-378,-508 -390,-492 -386,-474 C-382,-452 -358,-442 -330,-446 "
                  "C-306,-450 -288,-460 -280,-472 Z", fill=ink))
    g.append(path("M-368,-504 C-344,-510 -316,-502 -298,-484 L-308,-464 "
                  "C-324,-480 -348,-488 -372,-484 Z", fill=rim, op=0.9))
    g.append(path("M-162,-358 C-116,-330 -58,-306 -6,-292 L-14,-262 "
                  "C-70,-278 -128,-302 -176,-330 Z", fill=tone, op=0.8))

    # trailing arm, thrown back behind the kick for the counterweight
    g.append(path("M50,-330 C96,-330 146,-312 182,-282 "
                  "C204,-264 206,-238 188,-224 C170,-210 146,-216 132,-234 "
                  "C110,-260 78,-276 44,-282 Z", fill=ink))
    g.append(ellipse(196, -216, 30, 27, rot=-18, fill=ink))
    g.append(path("M172,-236 C186,-246 208,-244 218,-232 L214,-214 "
                  "C204,-226 186,-228 170,-220 Z", fill="#cd1932", op=0.9))
    # near arm, tucked across the ribs
    g.append(path("M42,-300 C14,-282 -2,-252 -4,-220 "
                  "C-6,-196 8,-180 28,-182 C46,-184 56,-200 54,-222 "
                  "C52,-244 62,-264 82,-276 Z", fill=ink))

    for d, w, o in (("M116,-298 C130,-254 132,-210 122,-178", 6, 0.95),
                    ("M52,-418 C78,-452 140,-452 160,-418", 5, 0.85),
                    ("M-224,-350 C-250,-386 -272,-430 -284,-474", 6, 0.9),
                    ("M-206,-292 C-152,-262 -84,-236 -18,-214", 5, 0.75),
                    ("M44,-204 C34,-146 34,-70 38,0", 5, 0.8),
                    ("M182,-282 C204,-264 206,-238 188,-224", 4, 0.7)):
        g.append(path(d, stroke=rim, w=w, op=o))
    # half-lidded and turned almost away: he stopped asking years ago

    g.append("</g>")
    return "".join(g)


def zayos(x, y, s=1.0, ink="#090b0f", tone="#272521", rim="#f99537"):
    """ZAYOS, in the cellar. A boxing monster: gloves, long arms, slow, and
    a body half again the size of any man in the Halqa. He only punches."""
    g = [f'<g transform="translate({x},{y}) scale({s})">']
    g.append(path("M-276,480 C-292,336 -256,220 -190,148 C-126,78 -44,44 0,44 "
                  "C44,44 126,78 190,148 C256,220 292,336 276,480 Z", fill=ink))
    g.append(path("M-74,-10 C-74,-68 -40,-106 0,-106 C40,-106 74,-68 74,-10 "
                  "C74,32 70,60 58,76 C36,92 -36,92 -58,76 "
                  "C-70,60 -74,32 -74,-10 Z", fill=ink))
    g.append('<clipPath id="zyface"><path d="M-74,-10 C-74,-68 -40,-106 0,-106 '
             'C40,-106 74,-68 74,-10 C74,32 70,60 58,76 C36,92 -36,92 -58,76 '
             'C-70,60 -74,32 -74,-10 Z"/></clipPath>')
    g.append('<g clip-path="url(#zyface)">')
    # the heaviest brow in the booklet and the smallest eyes under it: he is
    # enormous, he is slow, and he only punches. Straight ahead and slightly
    # through the reader -- a man with one idea.
    g.append(face(0, 16, 62, 64, tone="#352d22", rim=rim, iris="#f7b170",
                  mood="dull", lit=1, turn=0.0, gaze=(0.0, 0.10)))
    g.append("</g>")
    g.append(path("M-82,-4 C-76,-74 -40,-116 0,-116 C40,-116 76,-74 82,-4 "
                  "C58,-38 30,-54 0,-54 C-30,-54 -58,-38 -82,-4 Z", fill=ink))
    # arms long enough to be the point of him
    g.append(path("M-156,150 C-236,190 -304,286 -332,404 L-268,430 "
                  "C-244,330 -190,244 -130,206 Z", fill=ink))
    g.append(path("M156,150 C236,190 304,286 332,404 L268,430 "
                  "C244,330 190,244 130,206 Z", fill=ink))
    g.append(ellipse(-306, 470, 86, 78, rot=16, fill=ink))
    g.append(ellipse(306, 470, 86, 78, rot=-16, fill=ink))
    g.append(path("M-372,448 C-334,404 -262,406 -230,452 L-238,486 "
                  "C-268,448 -330,446 -364,482 Z", fill=tone))
    g.append(path("M372,448 C334,404 262,406 230,452 L238,486 "
                  "C268,448 330,446 364,482 Z", fill=tone))
    g.append(path("M-124,168 C-62,202 62,202 124,168 C148,264 152,376 146,480 L-146,480 "
                  "C-152,376 -148,264 -124,168 Z", fill=tone, op=0.8))

    for d, w, o in (("M72,0 C66,-62 36,-98 0,-98", 6, 0.85),
                    ("M190,148 C256,220 288,336 276,470", 7, 0.9),
                    ("M162,156 C238,196 304,288 332,402", 6, 0.8),
                    ("M-346,436 C-310,400 -252,404 -226,444", 6, 0.85)):
        g.append(path(d, stroke=rim, w=w, op=o))
    g.append("</g>")
    return "".join(g)


def crowd(x, y, w, n=26, seed=11, ink="#090b0f", rim=None, op=1.0, h=90):
    """The ring of onlookers that closes around a fight in a marketplace.
    Halqa means that too, so the crowd is never decoration on this page.

    No faces, on purpose -- they are backlit and behind the fight, and a ring
    of tiny expressions would pull the eye off the one face that matters.
    What they DO need is to stop being identical: the first draft was a row
    of perfect circles on perfect domes, which reads as balloons on a stick
    rather than as people. Each one now gets its own head shape, a tilt, a
    neck, shoulders that are not a mirror of themselves, and one head in
    three turned to the side with the nose and chin that implies.
    """
    g = [f'<g opacity="{op}">']
    for i in range(n):
        def hash01(a, b):
            v = math.sin((i + 1) * a + seed * b) * 6112.3
            return v - math.floor(v)
        j, j2 = hash01(13.7, 9.1), hash01(4.31, 27.7)
        j3, j4 = hash01(27.13, 3.77), hash01(9.77, 17.31)
        px = x + w * (i + 0.5 * j) / n
        sc = 0.72 + 0.6 * j2
        hd = 17 * sc
        py = y - 4 * j
        tilt = (j3 - 0.5) * 22                      # nobody stands square on
        facing = -1 if j3 < 0.5 else 1   # its own hash: gating this
                                         # on j4, which also decides
                                         # WHO turns, made every
                                         # turned head face right
        hy = py - h * sc - hd * 0.92

        # neck first, so the head sits on top of it rather than beside it
        g.append(path(f"M{px - 7 * sc:.1f},{hy + hd * 0.7:.1f} "
                      f"L{px + 7 * sc:.1f},{hy + hd * 0.7:.1f} "
                      f"L{px + 10 * sc:.1f},{py - h * sc + 6 * sc:.1f} "
                      f"L{px - 10 * sc:.1f},{py - h * sc + 6 * sc:.1f} Z", fill=ink))
        # the skull: taller than wide, and never the same ratio twice
        g.append(ellipse(px, hy, hd * (0.90 + 0.14 * j3), hd * (1.02 + 0.16 * j4),
                         rot=tilt, fill=ink))
        if j4 > 0.62:                               # turned away: nose and chin
            g.append(path(f"M{px + facing * hd * 0.80:.1f},{hy - hd * 0.10:.1f} "
                          f"L{px + facing * hd * 1.24:.1f},{hy + hd * 0.16:.1f} "
                          f"L{px + facing * hd * 0.86:.1f},{hy + hd * 0.40:.1f} Z",
                          fill=ink))
        # shoulders, leaning the way the head is turned
        lw, rw = 46 * sc * (1.0 + 0.16 * j3), 46 * sc * (1.0 - 0.12 * j3)
        drop = h * sc * (0.86 + 0.10 * j)
        g.append(path(f"M{px - lw:.1f},{py} "
                      f"C{px - lw * 0.96:.1f},{py - drop * 0.80:.1f} "
                      f"{px - lw * 0.44:.1f},{py - h * sc:.1f} "
                      f"{px + facing * 3 * sc:.1f},{py - h * sc:.1f} "
                      f"C{px + rw * 0.46:.1f},{py - h * sc:.1f} "
                      f"{px + rw * 0.94:.1f},{py - drop * 0.84:.1f} "
                      f"{px + rw:.1f},{py} Z", fill=ink))
        if rim and j > 0.58:
            # the rim hugs the skull it is on; a light that bulges off the
            # head reads as a stray mark, which is what the first pass did
            rx, ry = hd * (0.90 + 0.14 * j3), hd * (1.02 + 0.16 * j4)
            g.append(path(f"M{px + rx * 0.30:.1f},{hy - ry * 0.94:.1f} "
                          f"C{px + rx * 0.80:.1f},{hy - ry * 0.74:.1f} "
                          f"{px + rx:.1f},{hy - ry * 0.28:.1f} "
                          f"{px + rx * 0.94:.1f},{hy + ry * 0.24:.1f}",
                          stroke=rim, w=2.2 * sc, op=0.50))
            g.append(path(f"M{px + rw * 0.58:.1f},{py - h * sc * 0.90:.1f} "
                          f"C{px + rw * 0.90:.1f},{py - drop * 0.70:.1f} "
                          f"{px + rw * 0.99:.1f},{py - drop * 0.28:.1f} "
                          f"{px + rw:.1f},{py:.1f}",
                          stroke=rim, w=2.4 * sc, op=0.40))
    g.append("</g>")
    return "".join(g)


# --------------------------------------------------------------- the places

def vignette(theme, x, y, w, h, gold="#e5b750", ink="#090b0f", cream="#e7e4db"):
    """One district, in the smallest number of shapes that still says which.

    Nine themes, nine skylines. Each is the one thing the stage's own
    briefing is about -- the awnings, the ropes, the wet stone at dawn --
    and nothing else, because at this size a second idea is a smudge.
    """
    def R(a, b, c, d, f, o=1.0):
        return (f'<rect x="{a:.0f}" y="{b:.0f}" width="{c:.0f}" height="{d:.0f}" '
                f'fill="{f}" opacity="{o}"/>')

    g = [f'<clipPath id="vg{abs(hash((theme, x, y))) % 99999}">'
         f'<rect x="{x}" y="{y}" width="{w}" height="{h}"/></clipPath>']
    cid = g[0][g[0].index('id="') + 4:g[0].index('">')]
    g.append(f'<g clip-path="url(#{cid})">')
    gy = y + h                                       # the ground line

    if theme == "Souq":
        g.append(R(x, y, w, h, "#2f251f"))
        g.append(f'<circle cx="{x + w * .74:.0f}" cy="{y + h * .34:.0f}" '
                 f'r="{h * .30:.0f}" fill="#e1ae56" opacity="0.8"/>')
        for i in range(5):
            ax = x + 12 + i * (w - 24) / 5
            aw = (w - 24) / 5 - 8
            g.append(f'<path d="M{ax:.0f},{gy} L{ax:.0f},{gy - h * .40:.0f} '
                     f'a{aw / 2:.0f},{aw / 2:.0f} 0 0,1 {aw:.0f},0 '
                     f'L{ax + aw:.0f},{gy} Z" fill="{ink}"/>')
        for i in range(4):
            sx = x + 16 + i * (w - 32) / 4
            sw = (w - 32) / 4 - 6
            g.append(f'<path d="M{sx:.0f},{gy - h * .40:.0f} l{sw:.0f},0 '
                     f'l-10,{h * .11:.0f} l{-(sw - 20):.0f},0 Z" '
                     f'fill="{"#cd1932" if i % 2 else gold}" opacity="0.85"/>')
            g.append(f'<path d="M{sx:.0f},{gy - h * .40:.0f} l{sw:.0f},0" '
                     f'stroke="{ink}" stroke-width="3"/>')
        for i in range(3):
            lx = x + w * (0.18 + 0.30 * i)
            g.append(f'<path d="M{lx:.0f},{gy - h * .40:.0f} L{lx:.0f},'
                     f'{gy - h * .30:.0f}" stroke="{gold}" stroke-width="2" '
                     f'opacity="0.7"/>')
            g.append(f'<circle cx="{lx:.0f}" cy="{gy - h * .27:.0f}" r="7" '
                     f'fill="{gold}"/>')
        g.append(crowd(x - 10, gy, w + 20, n=7, seed=5, h=h * 0.24, ink=ink,
                       rim=gold))

    elif theme == "Gym":
        g.append(R(x, y, w, h, "#25212c"))
        g.append(R(x, gy - h * .18, w, h * .18, "#1b1a1d"))
        for i, ry in enumerate((.34, .46, .58)):
            g.append(f'<path d="M{x + 10},{gy - h * ry:.0f} L{x + w - 10},'
                     f'{gy - h * ry:.0f}" stroke="{cream}" stroke-width="4" '
                     f'opacity="{0.75 - i * 0.18}"/>')
        for px in (x + 14, x + w - 14):
            g.append(f'<rect x="{px - 5:.0f}" y="{gy - h * .66:.0f}" width="10" '
                     f'height="{h * .66:.0f}" fill="{ink}"/>')
        g.append(f'<rect x="{x + w * .50:.0f}" y="{y + 6}" width="6" '
                 f'height="{h * .26:.0f}" fill="{ink}"/>')
        g.append(f'<rect x="{x + w * .44:.0f}" y="{y + h * .26:.0f}" width="34" '
                 f'height="{h * .34:.0f}" rx="14" fill="{ink}"/>')
        g.append(f'<rect x="{x + w * .44:.0f}" y="{y + h * .26:.0f}" width="34" '
                 f'height="{h * .34:.0f}" rx="14" fill="none" stroke="{gold}" '
                 f'stroke-width="3" opacity="0.7"/>')

    elif theme == "Fishmarket":
        g.append(R(x, y, w, h, "#212b37"))
        g.append(f'<circle cx="{x + w * .30:.0f}" cy="{gy - h * .40:.0f}" '
                 f'r="{h * .22:.0f}" fill="#e9ae56" opacity="0.85"/>')
        g.append(R(x, gy - h * .40, w, h * .40, "#19212c"))
        for i in range(6):
            g.append(f'<path d="M{x},{gy - h * (0.34 - i * 0.05):.0f} '
                     f'L{x + w},{gy - h * (0.34 - i * 0.05):.0f}" stroke="#e9ae56" '
                     f'stroke-width="3" opacity="{0.30 - i * 0.04}"/>')
        g.append(f'<path d="M{x + w * .66:.0f},{gy - h * .40:.0f} '
                 f'L{x + w * .66:.0f},{y + h * .10:.0f}" stroke="{ink}" '
                 f'stroke-width="6"/>')
        g.append(f'<path d="M{x + w * .66:.0f},{y + h * .14:.0f} '
                 f'L{x + w * .90:.0f},{gy - h * .42:.0f} '
                 f'L{x + w * .66:.0f},{gy - h * .42:.0f} Z" fill="{cream}" '
                 f'opacity="0.80"/>')
        g.append(f'<path d="M{x + w * .52:.0f},{gy - h * .38:.0f} '
                 f'L{x + w * .92:.0f},{gy - h * .38:.0f} '
                 f'L{x + w * .84:.0f},{gy - h * .26:.0f} '
                 f'L{x + w * .58:.0f},{gy - h * .26:.0f} Z" fill="{ink}"/>')

    elif theme == "Towers":
        g.append(R(x, y, w, h, "#191d2c"))
        for i in range(22):
            sx = x + ((i * 97) % int(w))
            sy = y + ((i * 53) % int(h * 0.6))
            g.append(f'<circle cx="{sx}" cy="{sy}" r="1.8" fill="{cream}" '
                     f'opacity="{0.2 + 0.5 * ((i % 5) / 5)}"/>')
        for i, (fx, fh, fr) in enumerate(((.26, .62, 26), (.50, .82, 34),
                                          (.74, .52, 22))):
            tx = x + w * fx
            g.append(f'<rect x="{tx - 7:.0f}" y="{gy - h * fh:.0f}" width="14" '
                     f'height="{h * fh:.0f}" fill="{ink}"/>')
            g.append(f'<ellipse cx="{tx:.0f}" cy="{gy - h * fh + 10:.0f}" '
                     f'rx="{fr}" ry="{fr * 0.52:.0f}" fill="{ink}"/>')
            g.append(f'<ellipse cx="{tx:.0f}" cy="{gy - h * fh + 10:.0f}" '
                     f'rx="{fr}" ry="{fr * 0.52:.0f}" fill="none" stroke="{gold}" '
                     f'stroke-width="2.5" opacity="0.8"/>')
        g.append(R(x, gy - h * .12, w, h * .12, "#181a20"))

    elif theme == "Marina":
        g.append(R(x, y, w, h, "#171d2c"))
        mcx, mcy, mr = x + w * .50, y + h * .44, min(w, h) * .30
        g.append(f'<circle cx="{mcx:.0f}" cy="{mcy:.0f}" r="{mr:.0f}" '
                 f'fill="#53b1fa" opacity="0.95"/>')
        g.append(f'<circle cx="{mcx + mr * .46:.0f}" cy="{mcy - mr * .26:.0f}" '
                 f'r="{mr * .88:.0f}" fill="#171d2c"/>')
        g.append(f'<circle cx="{mcx:.0f}" cy="{mcy:.0f}" r="{mr * 1.22:.0f}" '
                 f'fill="#53b1fa" opacity="0.10"/>')
        g.append(R(x, gy - h * .32, w, h * .32, "#161a24"))
        for i in range(9):
            lx = x + 12 + i * (w - 24) / 9
            g.append(f'<rect x="{lx:.0f}" y="{gy - h * .30:.0f}" width="5" '
                     f'height="{h * (0.06 + 0.04 * (i % 3)):.0f}" '
                     f'fill="{"#f99537" if i % 2 else "#53b1fa"}" opacity="0.8"/>')

    elif theme == "Failaka":
        g.append(R(x, y, w, h, "#1e252b"))
        g.append(R(x, gy - h * .30, w, h * .30, "#181e24"))
        for i, (bx, bw2, bh2) in enumerate(((.10, .16, .30), (.30, .10, .46),
                                            (.46, .20, .24), (.70, .12, .40),
                                            (.86, .14, .20))):
            g.append(R(x + w * bx, gy - h * (.30 + bh2), w * bw2, h * bh2, ink))
            g.append(f'<path d="M{x + w * bx:.0f},{gy - h * (.30 + bh2):.0f} '
                     f'L{x + w * (bx + bw2):.0f},{gy - h * (.30 + bh2):.0f}" '
                     f'stroke="{gold}" stroke-width="3" opacity="0.5"/>')
        for i in range(4):
            g.append(f'<path d="M{x},{gy - h * (0.24 - i * 0.06):.0f} '
                     f'L{x + w},{gy - h * (0.24 - i * 0.06):.0f}" stroke="#53b1fa" '
                     f'stroke-width="2" opacity="{0.22 - i * 0.04}"/>')

    elif theme == "Highway":
        g.append(R(x, y, w, h, "#352720"))
        g.append(f'<circle cx="{x + w * .50:.0f}" cy="{gy - h * .40:.0f}" '
                 f'r="{h * .26:.0f}" fill="#e16f39" opacity="0.85"/>')
        g.append(R(x, gy - h * .40, w, h * .40, "#1d1a1f"))
        for i in range(5):
            g.append(f'<rect x="{x + 8 + i * (w - 16) / 5:.0f}" '
                     f'y="{gy - h * .10:.0f}" width="{(w - 16) / 5 - 20:.0f}" '
                     f'height="6" fill="{cream}" opacity="0.32"/>')
        for i, (tx, tw) in enumerate(((.06, .34), (.44, .30), (.78, .26))):
            g.append(R(x + w * tx, gy - h * (.34 + 0.06 * (i % 2)), w * tw,
                       h * (.22 + 0.06 * (i % 2)), ink))
            g.append(f'<path d="M{x + w * tx:.0f},{gy - h * .34:.0f} '
                     f'L{x + w * (tx + tw):.0f},{gy - h * .34:.0f}" stroke="{gold}" '
                     f'stroke-width="3" opacity="0.55"/>')

    elif theme == "Desert":
        g.append(R(x, y, w, h, "#271f2c"))
        for i in range(18):
            sx = x + ((i * 131) % int(w))
            g.append(f'<circle cx="{sx}" cy="{y + ((i * 61) % int(h * .5))}" '
                     f'r="1.6" fill="{cream}" opacity="0.35"/>')
        g.append(f'<path d="M{x},{gy} L{x},{gy - h * .22:.0f} '
                 f'Q{x + w * .3:.0f},{gy - h * .40:.0f} {x + w * .58:.0f},'
                 f'{gy - h * .20:.0f} Q{x + w * .82:.0f},{gy - h * .04:.0f} '
                 f'{x + w:.0f},{gy - h * .26:.0f} L{x + w:.0f},{gy} Z" fill="#2f2621"/>')
        for i, (fx, fs) in enumerate(((.20, 1.0), (.46, 1.4), (.74, 0.8))):
            fx2 = x + w * fx
            fy = gy - h * (.14 + 0.03 * i)
            g.append(f'<path d="M{fx2:.0f},{fy:.0f} '
                     f'C{fx2 - 14 * fs:.0f},{fy - 22 * fs:.0f} '
                     f'{fx2 + 6 * fs:.0f},{fy - 30 * fs:.0f} '
                     f'{fx2 + 2 * fs:.0f},{fy - 52 * fs:.0f} '
                     f'C{fx2 + 20 * fs:.0f},{fy - 30 * fs:.0f} '
                     f'{fx2 + 18 * fs:.0f},{fy - 12 * fs:.0f} '
                     f'{fx2:.0f},{fy:.0f} Z" fill="#f99537" opacity="0.9"/>')
            g.append(f'<ellipse cx="{fx2 + 2:.0f}" cy="{fy + 3:.0f}" '
                     f'rx="{22 * fs:.0f}" ry="{6 * fs:.0f}" fill="{gold}" '
                     f'opacity="0.22"/>')

    else:                                                        # Arena
        g.append(R(x, y, w, h, "#201c28"))
        g.append(f'<path d="M{x + w * .5:.0f},{y - 20} L{x - 40},{gy} '
                 f'L{x + w + 40:.0f},{gy} Z" fill="#de5aee" opacity="0.13"/>')
        g.append(f'<ellipse cx="{x + w * .5:.0f}" cy="{gy - h * .12:.0f}" '
                 f'rx="{w * .40:.0f}" ry="{h * .12:.0f}" fill="none" '
                 f'stroke="#de5aee" stroke-width="4" opacity="0.8"/>')
        g.append(crowd(x - 20, gy, w + 40, n=9, seed=23, h=h * 0.34, ink=ink,
                       rim=gold))
    g.append("</g>")
    return "".join(g)


# --------------------------------------------------------------- the talents

def talent_mark(name, colour="#e5b750", size=72):
    """A drawn mark for each talent, not a typed one.

    `DT_Talents.csv` carries a glyph per talent for the in-game HUD, and on a
    screen with the game's own font behind it that glyph is right. On a
    printed sheet it is whatever font happens to have U+270A, which on this
    machine is a scribble -- so the five marks are drawn here instead, and
    each one is the same idea the glyph was: a ledge pulled over, a gap
    crossed, a shutter kicked, a hook that goes through, a hand on fire.

    The two hands are the same hand. HAWK FIST is the fourth mark with fire
    on it, because that is exactly what the story says it is.
    """
    u = size / 72.0

    def P(d, fill="none", stroke=None, w=6):
        st = (f' stroke="{stroke}" stroke-width="{w * u:.2f}" stroke-linecap="round"'
              f' stroke-linejoin="round"') if stroke else ""
        return f'<path d="{d}" fill="{fill}"{st}/>'

    fist = (P("M18,34 C18,25 25,20 34,20 C48,20 60,28 60,42 "
              "C60,55 50,62 37,62 C25,62 18,54 18,44 Z", fill=colour)
            + "".join(P(f"M{22 + i * 10},22 a5,5 0 0,1 10,0", fill=colour)
                      for i in range(4))
            + P("M20,44 L56,41", stroke="#090b0f", w=4)
            + P("M22,53 L54,51", stroke="#090b0f", w=3.4)
            + P("M10,50 C9,40 12,33 18,30 L20,58 C13,58 10,55 10,50 Z",
                fill=colour, stroke=None))

    marks = {
        "Vault": (
            P("M6,66 L28,66 L28,50 L6,50 Z", fill=colour, stroke=None) +
            P("M44,66 L68,66 L68,30 L44,30 Z", fill=colour, stroke=None) +
            P("M16,44 C16,18 38,8 54,16", stroke=colour, w=6.5) +
            P("M42,4 L62,18 L40,26 Z", fill=colour)),
        "DashLeap": (
            P("M6,58 L28,58", stroke=colour, w=7) +
            P("M46,58 L68,58", stroke=colour, w=7) +
            P("M14,46 C22,16 50,14 60,36", stroke=colour, w=6.5) +
            P("M50,28 L66,40 L48,46 Z", fill=colour)),
        "PowerKick": (
            P("M40,4 L16,38 L33,38 L24,68 L56,30 L38,30 L48,4 Z", fill=colour)),
        "Haymaker": fist,
        "HawkFist": (
            P("M34,18 C22,8 32,4 31,-2 C46,6 50,14 44,20 Z", fill=colour) +
            P("M48,16 C42,8 50,6 50,1 C60,9 58,16 54,20 Z", fill=colour,
              stroke=None) +
            fist.replace("M18,34", "M18,38").replace("C18,25 25,20 34,20",
                                                     "C18,29 25,24 34,24")),
    }[name]
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
            f'style="display:inline-block">{marks}</svg>')
