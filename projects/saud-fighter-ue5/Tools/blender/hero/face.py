"""The face as a field in texture space, not in vertices.

The head's mesh has 3.1 mm between vertices and the skin texture has 0.9 mm
between texels. Everything that says "young man" rather than "mannequin" is
smaller than 3.1 mm -- the vermilion border of a lip, the rim of a nostril,
the edge of a brow, the lash line, the crease of an upper lid. Painted per
vertex those features have nowhere to live: they are averaged away before
the bake ever sees them, which is why the old face read as a smudge with a
dark blob over the mouth.

So the face is described here once, as functions of position, and evaluated
twice: per vertex for the colour attribute the bake starts from, and per
texel afterwards, where it actually resolves. Each feature returns both a
colour and a relief in metres; the relief becomes a normal map, so a lip has
an edge that catches light without costing a single triangle.

Coordinates are the build's: Saud faces -Y, +X is his left, Z up, metres.
Every height comes from hero.sculpt, which holds the face's layout in one
place: chin 1.572, mouth 1.620, nostrils 1.633, eyes 1.677, brow 1.693,
hairline 1.760, crown 1.796.
"""
import numpy as np
from . import anatomy as A
from .sculpt import EYE_Z, BROW_Z, NOSE_Z, MOUTH_Z, EAR_Z, HAIRLINE

# ------------------------------------------------------------- where am I
def forwardness(P):
    """+1 on the front pole of the skull, 0 at the ear, -1 at the nape.

    The old masks asked `y < 0.03` and `|x| < 0.088` and called that the
    face. Neither bites: the head is only 0.079 wide, so the |x| bound is
    always true, and a fifth of the BACK of the skull is forward of y=0.03.
    That is how the beard came to be painted round the back of his head.
    This asks the question the masks meant to ask.
    """
    zs = [r[0] for r in A.HEAD_ROWS]
    cy = np.interp(P[:, 2], zs, [r[1] for r in A.HEAD_ROWS])
    ry = np.interp(P[:, 2], zs, [r[3] for r in A.HEAD_ROWS])
    return np.clip((cy - P[:, 1]) / np.maximum(ry, 1e-6), -1.6, 1.6)

def lateral(P):
    """0 on the midline, 1 at the widest part of the skull at that height."""
    zs = [r[0] for r in A.HEAD_ROWS]
    rx = np.interp(P[:, 2], zs, [r[2] for r in A.HEAD_ROWS])
    return np.abs(P[:, 0]) / np.maximum(rx, 1e-6)

def smooth(t):
    """Smoothstep, so no feature has a stair-step edge in a 0.9 mm texel."""
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)

def ramp(v, a, b):
    """0 below a, 1 above b, smooth between. b < a reverses it. The bounds
    may themselves be arrays -- a lip's edge follows the cupid's bow."""
    d = np.asarray(b, dtype=float) - np.asarray(a, dtype=float)
    d = np.where(np.abs(d) < 1e-12, 1e-12, d)
    return smooth((v - a) / d)

def blob(P, x0, z0, sx, sz, mirror=True):
    """A Gaussian on the face plane. Mirrored features are measured on |x|."""
    x = np.abs(P[:, 0]) if mirror else P[:, 0]
    return np.exp(-0.5 * (((x - x0) / sx) ** 2 + ((P[:, 2] - z0) / sz) ** 2))

def bar(P, x0, x1, z_at, thick, feather=0.0016, arch=0.0):
    """A feathered bar running out from x0 to x1 on |x|, centred on the
    height z_at (a callable of |x| if the feature arches), `thick` tall."""
    x = np.abs(P[:, 0]); z = P[:, 2]
    zc = z_at(x) if callable(z_at) else z_at
    if arch:
        u = np.clip((x - x0) / max(x1 - x0, 1e-6), 0.0, 1.0)
        zc = zc + arch * np.clip(1.0 - (2.0 * u - 1.0) ** 2, 0.0, 1.0)
    along = ramp(x, x0 - feather, x0 + feather) * ramp(x, x1 + feather, x1 - feather)
    across = np.exp(-0.5 * ((z - zc) / max(thick, 1e-6)) ** 2)
    return along * across

# --------------------------------------------------------------- the grain
# The head sits at z about 1.7 m, so at a 1150-per-metre lattice the indices
# run to ~2000. The usual sin(dot(p, k)) * 43758.5 hash loses its low bits at
# that magnitude and lays down a diagonal corduroy instead of noise -- it
# showed up on the beard as ribbing. This hashes the integer lattice instead,
# which does not care how far from the origin the head is.
_ORIGIN = np.array([0.0, 0.0, 1.70])

def _hash3(ix, iy, iz, seed):
    h = (ix.astype(np.int64) * np.int64(73856093)) ^ (iy.astype(np.int64) * np.int64(19349663)) \
        ^ (iz.astype(np.int64) * np.int64(83492791)) ^ np.int64(int(seed * 7919) & 0x7FFFFFFF)
    h &= np.int64(0x7FFFFFFF)
    h = (h ^ (h >> np.int64(13))) * np.int64(1274126177)
    h &= np.int64(0x7FFFFFFF)
    return (h ^ (h >> np.int64(16))).astype(np.float64) / 2147483647.0

def noise(P, scale, seed=0.0):
    """Value noise on a lattice. Skin is not one colour and not one height;
    without this the cheeks bake out as flat paint, which is most of what
    reads as wax."""
    Q = (P - _ORIGIN) * scale
    i = np.floor(Q); f = Q - i
    f = f * f * (3.0 - 2.0 * f)
    ix, iy, iz = i[:, 0], i[:, 1], i[:, 2]
    c = {}
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                c[(dx, dy, dz)] = _hash3(ix + dx, iy + dy, iz + dz, seed)
    def mix(a, b, t): return a + (b - a) * t
    x00 = mix(c[(0, 0, 0)], c[(1, 0, 0)], f[:, 0]); x10 = mix(c[(0, 1, 0)], c[(1, 1, 0)], f[:, 0])
    x01 = mix(c[(0, 0, 1)], c[(1, 0, 1)], f[:, 0]); x11 = mix(c[(0, 1, 1)], c[(1, 1, 1)], f[:, 0])
    return mix(mix(x00, x10, f[:, 1]), mix(x01, x11, f[:, 1]), f[:, 2])

def fbm(P, scale, octaves=3, seed=0.0):
    out = np.zeros(len(P)); amp = 1.0; tot = 0.0; s = scale
    for o in range(octaves):
        out += amp * noise(P, s, seed + o * 17.0); tot += amp
        amp *= 0.5; s *= 2.03
    return out / tot

# ------------------------------------------------------------- the palette
def _srgb(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])

def _lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

def hex_lin(h): return _lin(_srgb(h))

# The three tonal zones of a face, which every portrait painter is taught and
# no flat fill has: the forehead runs yellow, the middle of the face runs red
# because the blood is closest there, and the jaw runs cool even clean-shaven
# because the beard is under the skin. These are the SAME skin, moved in hue
# and value, so the face still averages to the browser build's #f0d8c4 -- that
# number belongs to saud-fighter/assets/saud.js and is not ours to change.
#
# They are written as the colours they come to on Saud's skin, and they are
# applied to any other man as that same move on HIS skin: shade() carries
# each one as its ratio to SAUD_SKIN in linear light. The thug's face was
# Saud's face on a brown neck until it did -- the zones were laid over his
# #b8794c at 0.85 as the absolute #efd6b8 / #eecbb4 / #e2c7b4 they are here.
# On Saud the ratio is one and the number is the number.
SAUD_SKIN = '#f0d8c4'    # assets/saud.js col.skin, the skin these were written on
ZONE_BROW = '#efd6b8'     # forehead and temples, yellower
ZONE_MID  = '#eecbb4'     # nose, cheeks, the blood zone
ZONE_JAW  = '#e2c7b4'     # jaw, chin, upper lip -- cooler
BLOOD     = '#d98a76'     # ears, nostril rims, eyelids, the web of a finger
SHADOW    = '#8f6a57'     # what an occluded crease darkens toward
LIP       = '#c07c6c'
LIP_DEEP  = '#8d4f45'
LASH      = '#120c08'


def shade(P, skin, hair, beard, base_rgb=None):
    """Colour and relief for points on the head.

    P        (N,3) positions, metres, in the build's frame
    skin     the base skin colour, linear -- the browser build's number
    hair     hair colour, linear
    beard    beard colour, linear -- or None for a clean-shaven man, which
             skips the beard, the moustache and the sideburns together
    base_rgb (N,3) colour to start from, or None to start from `skin`

    returns  (rgb (N,3) linear, relief (N,) metres, on_face (N,) 0..1)
    """
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    ax = np.abs(x)
    fwd = forwardness(P)
    lat = lateral(P)
    col = (np.tile(skin, (len(P), 1)) if base_rgb is None else base_rgb.copy())
    _saud = hex_lin(SAUD_SKIN)
    def tone(h):
        """A tone written for Saud's skin, as the same move on this man's."""
        return np.asarray(skin, dtype=float) * (hex_lin(h) / _saud)
    rel = np.zeros(len(P))

    # Everything below is a head, and nothing may touch the nape. The gate
    # cannot be tight, because an ear stands proud of the skull's ellipse and
    # so reads as BEHIND the widest point -- fwd about -0.13 -- and a gate at
    # -0.10 left it with no paint at all, not even the blood tint written for
    # it. The features that must stay off the sides carry their own fwd gate.
    face_w = ramp(fwd, -0.62, -0.28)
    head_w = ramp(z, 1.545, 1.565) * ramp(z, 1.815, 1.790)
    on_face = face_w * head_w
    if not on_face.any():
        return col, rel, on_face

    def over(mask, rgb, k=1.0):
        w = (np.clip(mask, 0, 1) * k * on_face)[:, None]
        col[:] = col * (1 - w) + np.asarray(rgb)[None, :] * w

    def darken(mask, k):
        w = np.clip(mask, 0, 1) * k * on_face
        col[:] = col * (1 - w[:, None]) + tone(SHADOW)[None, :] * w[:, None]

    # ---- 1. the three zones -------------------------------------------
    zone_w = ramp(fwd, -0.15, 0.25)
    brow_zone = ramp(z, BROW_Z - 0.009, BROW_Z + 0.031) * zone_w
    jaw_zone = ramp(z, MOUTH_Z + 0.032, MOUTH_Z - 0.016) * zone_w
    mid_zone = np.clip(zone_w - brow_zone - jaw_zone, 0.0, 1.0)
    over(brow_zone, tone(ZONE_BROW), 0.85)
    over(mid_zone, tone(ZONE_MID), 0.85)
    over(jaw_zone, tone(ZONE_JAW), 0.85)

    # ---- 2. blood at the thin places ----------------------------------
    over(blob(P, 0.0785, EAR_Z, 0.013, 0.024), tone(BLOOD), 0.30)    # the ear
    over(blob(P, 0.014, NOSE_Z + 0.001, 0.007, 0.006), tone(BLOOD), 0.26)  # nostril rim
    over(blob(P, 0.031, EYE_Z - 0.0060, 0.016, 0.005), tone(BLOOD), 0.18)  # lower lid
    over(blob(P, 0.000, 1.586, 0.020, 0.012, mirror=False), tone(ZONE_MID), 0.20)  # chin

    # ---- 3. the creases: where light does not reach -------------------
    # A face is read by its shadows more than its colours. None of these
    # existed before, which is the other half of why he looked like wax.
    darken(blob(P, 0.031, EYE_Z + 0.0075, 0.020, 0.0055), 0.34)                 # upper lid fold
    darken(blob(P, 0.033, EYE_Z - 0.0115, 0.017, 0.0045), 0.16)                 # under the eye
    darken(blob(P, 0.014, EYE_Z - 0.002, 0.006, 0.012), 0.22)                   # side of the nose root
    nasolabial = bar(P, 0.016, 0.040, lambda u: NOSE_Z + 0.011 - 0.62 * (u - 0.016), 0.0038)
    darken(nasolabial, 0.14)                                            # faint at his age
    darken(blob(P, 0.000, MOUTH_Z - 0.0133, 0.016, 0.0040, mirror=False), 0.26)   # under the lower lip
    darken(blob(P, 0.026, MOUTH_Z - 0.0004, 0.005, 0.0055), 0.30)                 # mouth corners
    darken(bar(P, 0.000, 0.062, 1.5695, 0.0055), 0.30)                  # under the jaw
    darken(blob(P, 0.0695, EAR_Z, 0.006, 0.026), 0.28)                   # where the ear meets

    # ---- 4. the hairline, feathered -----------------------------------
    z0, z1 = HAIRLINE
    # HAIRLINE is quoted at y = -0.09 and y = +0.09, so the divisor is 0.18:
    # anything else puts the painted line off the cap's cut by a millimetre
    # or two all the way round.
    plane = z0 + (z1 - z0) * np.clip((y + 0.09) / 0.18, -0.4, 1.4)
    edge = fbm(P, 260.0, 2, 3.0) - 0.5
    hw = ramp(z - plane - 0.0045 * edge, -0.0035, 0.0035)
    # a temple recession, which every young man has and a swim cap does not
    temple = ramp(lat, 0.52, 0.86) * ramp(z, HAIRLINE[0] - 0.052, HAIRLINE[0] - 0.004) * ramp(fwd, 0.10, 0.34)
    hw = np.clip(hw - 0.75 * temple, 0.0, 1.0)
    over(hw, hair, 1.0)
    rel += hw * 0.0010
    darken(hw * (1.0 - hw) * 4.0 * 0.25, 0.30)                          # shadow under the fringe

    # ---- 5. the brows: two of them ------------------------------------
    # They were one Gaussian a side with sigma 26 mm at x = +-31 mm, which
    # overlap to 0.96 weight at the midline: a single bar straight across
    # the forehead. A brow is ~40 mm long and the gap between them is ~18 mm.
    brow = bar(P, 0.010, 0.050, BROW_Z - 0.0022, 0.0042, feather=0.0022, arch=0.0032)
    brow = brow * ramp(ax, 0.0085, 0.0135)                              # keep the glabella clear
    brow = brow * (0.72 + 0.56 * fbm(P, 900.0, 2, 11.0))                # hairs, not paint
    brow = np.clip(brow, 0, 1) * ramp(fwd, 0.25, 0.55)
    over(brow, hair, 0.94)
    rel += brow * 0.0009

    # ---- 6. the eyes: lash line and lid crease ------------------------
    lash = bar(P, 0.013, 0.048, lambda u: EYE_Z + 0.0038 - 0.10 * (u - 0.013), 0.0016, feather=0.0012)
    over(lash * ramp(fwd, 0.30, 0.60), hex_lin(LASH), 0.85)
    rel -= lash * 0.0004
    lower_lash = bar(P, 0.016, 0.044, lambda u: EYE_Z - 0.0050 + 0.06 * (u - 0.016), 0.0011, feather=0.0012)
    over(lower_lash * ramp(fwd, 0.30, 0.60), hex_lin(LASH), 0.35)
    rel += blob(P, 0.031, EYE_Z + 0.0085, 0.019, 0.0040) * 0.0011               # the lid's own fold

    # ---- 7. the mouth -------------------------------------------------
    # A mouth is not a rectangle. Built from the line between the lips
    # outward: each lip's half-thickness falls to nothing at the corner, so
    # the two edges meet there instead of stopping at a vertical cut, and the
    # upper lip's top edge carries a cupid's bow -- two peaks with the
    # philtrum's notch between them. Half-width 24 mm, so 48 mm corner to
    # corner, against a 30 mm nose: the proportion a face is drawn to.
    HW = 0.0240
    u = np.clip(ax / HW, 0.0, 1.35)
    taper = np.clip(1.0 - u * u, 0.0, 1.0)
    mid = MOUTH_Z - 0.0024 * u * u                                        # the lips' line drops at the corners
    bow = 0.58 * np.exp(-(((u - 0.27) / 0.24) ** 2)) - 0.34 * np.exp(-((u / 0.16) ** 2))
    t_up = 0.0040 * taper ** 0.55 * (1.0 + bow)
    t_lo = 0.0052 * taper ** 0.50
    f = 0.0007
    upper = ramp(z, mid - f, mid + f) * ramp(z, mid + t_up + f, mid + t_up - f)
    lower = ramp(z, mid - t_lo - f, mid - t_lo + f) * ramp(z, mid + f, mid - f)
    lips = np.clip((upper + lower) * ramp(u, 1.02, 0.93), 0, 1) * ramp(fwd, 0.35, 0.65)
    over(lips, tone(LIP), 0.92)
    over(np.clip(upper, 0, 1) * lips, tone(LIP_DEEP), 0.26)           # the upper lip reads darker
    rel += (upper * 0.0007 + lower * 0.0012) * np.clip(taper, 0, 1)
    mouthline = ramp(z, mid - 0.0009, mid) * ramp(z, mid + 0.0009, mid) * ramp(u, 1.00, 0.90)
    over(mouthline * ramp(fwd, 0.35, 0.65), tone(LIP_DEEP), 0.80)
    rel -= mouthline * 0.0012
    # philtrum: two ridges and the groove between them
    rel += (bar(P, 0.0035, 0.0085, 1.6265, 0.0055) * 0.0007
            - blob(P, 0.000, 1.6265, 0.0028, 0.0055, mirror=False) * 0.0008)

    # ---- 8. the nostrils ----------------------------------------------
    nose_hole = blob(P, 0.0078, NOSE_Z, 0.0034, 0.0027)
    over(nose_hole * ramp(fwd, 0.55, 0.85), hex_lin('#3a2119'), 0.80)
    rel -= nose_hole * 0.0022
    rel += blob(P, 0.0150, NOSE_Z + 0.0045, 0.0050, 0.0044) * 0.0009             # the ala's rim

    # ---- 9. the beard -------------------------------------------------
    # Front and sides of the jaw only. `fwd` is what keeps it off the back
    # of the skull; the old `|x| < 0.088` never bit, because the skull is
    # 0.079 wide, so 28 % of the beard was painted behind his ears.
    # A trimmed beard follows the jaw. Its top edge is a line from the corner
    # of the mouth back to the ear, not a band filling the cheek -- the cheek
    # above it is bare, which is what makes it read as kept rather than as
    # dirt on the face.
    if beard is None:
        # ---- 10, early: the grain, and out. No beard on this man.
        pore = fbm(P, 1100.0, 3, 23.0) - 0.5
        blotch = fbm(P, 90.0, 3, 41.0) - 0.5
        col[:] = np.clip(col * (1.0 + (0.085 * blotch + 0.030 * pore) * on_face)[:, None], 0.0, 1.0)
        rel += (0.00010 * pore + 0.00022 * blotch) * on_face
        rel *= on_face
        return col, rel, on_face
    jaw_top = MOUTH_Z - 0.0117 + 0.052 * smooth(np.clip((lat - 0.18) / 0.72, 0, 1)) ** 1.35
    top = ramp(z, jaw_top + 0.0045, jaw_top - 0.0045)
    bottom = ramp(z, 1.5560, 1.5660)
    beard_w = top * bottom * ramp(fwd, 0.04, 0.26)
    # A moustache sits BELOW the nostrils and is narrower than the nose.
    # The old one was a hard rectangle up to z=1.636 -- over the nostrils at
    # 1.629 and the alae at 1.636 -- and 56 mm wide against a 34 mm nose.
    lip_top = mid + t_up
    mous = ramp(z, NOSE_Z - 0.0022, NOSE_Z - 0.0052) * ramp(z, lip_top - 0.0008, lip_top + 0.0014) * ramp(ax, 0.0230, 0.0180)
    beard_w = np.clip(np.maximum(beard_w, mous * ramp(fwd, 0.45, 0.75)), 0, 1)
    beard_w = beard_w * (1.0 - 0.96 * np.clip(lips + mouthline, 0, 1))
    # stubble: fine, and gappier where a beard really is thinner
    grain = np.clip(0.30 + 1.45 * fbm(P, 1250.0, 2, 5.0), 0, 1.5)
    dens = np.clip(1.06 - 0.72 * smooth(np.clip((lat - 0.30) / 0.60, 0, 1)), 0.34, 1.0)
    dens = dens * np.clip(0.70 + 0.55 * ramp(z, MOUTH_Z - 0.010, MOUTH_Z - 0.044), 0, 1.0)  # fullest on the chin
    bw = np.clip(beard_w * dens * grain, 0, 1)
    over(bw, beard, 0.90)
    rel += bw * 0.0006
    darken(np.clip(beard_w * dens, 0, 1) * 0.5, 0.20)                     # the shadow a beard casts on skin
    # a sideburn running down in front of the ear, joining the hair
    side = bar(P, 0.058, 0.075, lambda t: HAIRLINE[0] - 0.062 - 1.55 * (t - 0.058), 0.0060, feather=0.0035)
    over(np.clip(side * ramp(fwd, 0.10, 0.40) * grain, 0, 1), beard, 0.72)

    # ---- 10. the grain of the skin itself ------------------------------
    pore = fbm(P, 1100.0, 3, 23.0) - 0.5
    blotch = fbm(P, 90.0, 3, 41.0) - 0.5
    col[:] = np.clip(col * (1.0 + (0.085 * blotch + 0.030 * pore) * on_face)[:, None], 0.0, 1.0)
    rel += (0.00010 * pore + 0.00022 * blotch) * on_face

    rel *= on_face
    return col, rel, on_face


# The body is skin too. shade() only describes a head, so without this every
# other square centimetre of him -- arms, neck, hands -- bakes out as one
# flat constant, which is the other half of the wax. Quieter than the face:
# no zones, no creases, just the variation that stops a surface reading as
# paint.
def body_grain(P, col):
    blotch = fbm(P, 55.0, 3, 91.0) - 0.5
    pore = fbm(P, 950.0, 2, 107.0) - 0.5
    return np.clip(col * (1.0 + 0.055 * blotch + 0.022 * pore)[:, None], 0.0, 1.0)
