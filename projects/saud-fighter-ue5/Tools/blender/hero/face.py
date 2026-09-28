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
from .sculpt import EYE_Z, BROW_Z, NOSE_Z, MOUTH_Z, EAR_Z, EAR_X, HAIRLINE

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
SAUD_SKIN = '#f0d8c4'    # the skin these were written on (Saud's until 2026-09-24): a reference, used as a ratio
ZONE_BROW = '#efd6b8'     # forehead and temples, yellower
ZONE_MID  = '#eecbb4'     # nose, cheeks, the blood zone
ZONE_JAW  = '#e2c7b4'     # jaw, chin, upper lip -- cooler
BLOOD     = '#d98a76'     # ears, nostril rims, eyelids, the web of a finger
SHADOW    = '#8f6a57'     # what an occluded crease darkens toward
LIP       = '#c07c6c'
LIP_DEEP  = '#8d4f45'
LASH      = '#120c08'
SCAR      = '#caa48f'    # healed scar tissue: paler than the zone it crosses, no blood in it
BROW_BALD = '#17120e'    # a bald man's brows when he has no beard to take them from (pipeline.PAINT)

# ---- one man's paint, 2026-09-28 -----------------------------------------
# "make Saud more aggressive ... make all game like dark anime adult style",
# the Unreal build only: every number here is this build's and NOT the
# browser's, which paints no face at all. The face above is painted from
# one set of numbers for every man; LOOK is where a man's differ -- the
# brows' slant and weight, the scowl's furrow, the lids' crease and lash, a
# thinner harder mouth, the creases of a man past eighteen, the eye's own
# colours, his scars, a strip of tape on a broken nose, the grey in a
# beard, and the body's veins and grooves. Module state, like HAIR: set by
# pipeline.apply_man from pipeline.PAINT (and VEINS) before anything is
# painted, one process per man; a suite that paints several men in one
# process resets it with set_look(). EVERY DEFAULT IS THE NUMBER THAT WAS
# WRITTEN INLINE BEFORE, so a man with no entry paints exactly as before.
LOOK_DEFAULT = dict(
    # the brows (section 5): dropped whole; the inner end dropped against
    # the tail, the scowl; the arch; the bar's thickness (its sigma); where
    # the inner end starts; the colour -- None his hair's, 'beard' his
    # beard's, or a hex (a bald man's brows were painted in his hair
    # colour, which is his skin: AL-WAHSH and ZAYOS had none)
    brow_drop=0.0, brow_slant=0.0, brow_arch=0.0032, brow_thick=0.0042, brow_in=0.0100, brow_colour=None,
    # the glabella's furrow: two short vertical creases between the brows'
    # inner ends, (darken, relief in metres)
    furrow=(0.0, 0.0),
    # the eye: the upper lid's crease (its height over EYE_Z, how dark),
    # the upper lash line (its thickness, how dark), the shadow under it
    lid_fold=(0.0075, 0.34), lash=(0.0007, 0.72), under_eye=0.16,
    # the mouth: the lips' thickness at the middle (upper, lower), how far
    # their line drops to the corners, the cupid's bow, the lips' colour
    # weight and the upper lip's deeper tone, the seam (how dark, how deep),
    # the corners' shadow, and how much glossier than the skin the lips are
    # (finish.repaint_head's roughness)
    lip_up=0.0040, lip_lo=0.0052, lip_drop=0.0024, lip_bow=0.58, lip_k=0.92, lip_deep=0.26,
    lip_seam=(0.80, 0.0012), lip_corner=0.30, lip_gloss=0.26,
    # the nasolabial fold (darken, relief), a shadow under the cheekbone,
    # the moustache's share of the beard
    nasolabial=(0.14, 0.0), hollow_shade=0.0, mous=1.0,
    # the eye itself (finish.repaint_eye): the iris, and the sclera with
    # how much vascular tint it carries toward the corners
    iris='#6d4a2a', sclera=('#f0ece3', 0.10),
    # scar tissue: None is the browser's one brow scar as it was painted
    # (shade(scar=True)); a list is this man's strokes (scar_strokes)
    scars=None,
    # a strip of tape: dict(z=, x=(x0, x1), h= half-height, colour=, rough=)
    nose_tape=None,
    # grey hairs in the beard, 0..1
    beard_grey=0.0,
    # the veins (body_relief): 'worley', the cell-boundary net as it was,
    # or 'contour', lines along the limb; their strength (None: from the
    # man's build, as it was), relief, how much they darken the skin, and
    # the contour's frequency (per metre), line width, stretch along the
    # limb, one or two families of lines, and its seed
    vein_style="worley", vein_k=None, vein_height=0.00035, vein_darken=0.07,
    vein_scale=45.0, vein_width=0.012, vein_stretch=4.0, vein_lines=2, vein_seed=33.0,
    # the body's grooves (sternum, linea alba, the lines between the abs,
    # the spinal furrow) as a multiplier
    cut=1.0,
)
LOOK = dict(LOOK_DEFAULT)

def set_look(**knobs):
    """One man's paint: LOOK_DEFAULT with `knobs` over it. set_look() puts
    every default back. A knob this module does not have raises."""
    bad = set(knobs) - set(LOOK_DEFAULT)
    if bad:
        raise KeyError("no such look knob: %s" % sorted(bad))
    LOOK.clear(); LOOK.update(LOOK_DEFAULT); LOOK.update(knobs)


def brow_rgb(hair, beard):
    """The brows' colour: LOOK['brow_colour'] -- his hair's (None), his
    beard's ('beard') or a hex."""
    c = LOOK["brow_colour"]
    if c is None:
        return np.asarray(hair, dtype=float)
    if c == "beard":
        assert beard is not None, "brows in the beard's colour on a man with no beard"
        return np.asarray(beard, dtype=float)
    return hex_lin(c)


def _seg_dist(u, v, a, b):
    """Distance in a plane from points (u, v) to the segment a-b, and the
    fraction along it (0..1)."""
    du, dv = b[0] - a[0], b[1] - a[1]
    L2 = max(du * du + dv * dv, 1e-12)
    t = np.clip(((u - a[0]) * du + (v - a[1]) * dv) / L2, 0.0, 1.0)
    return np.hypot(u - (a[0] + t * du), v - (a[1] + t * dv)), t


def scar_masks(d, t, w, P, seed=0.0):
    """A healed scar's tissue about its centre line, from each point's
    distance `d` off it and fraction `t` along it: (core, pucker), 0..1.
    The core is the pale ridge, `w` the half-width, tapering to the ends
    and ragged along its edge; the pucker is the darker pulled skin
    either side of it."""
    taper = np.clip(np.sin(np.pi * t), 0.25, 1.0) ** 0.5
    wid = w * taper * (0.92 + 0.12 * np.clip((fbm(P, 380.0, 2, 61.0 + seed) - 0.5) / 0.12, -1.0, 1.0))
    core = ramp(d, wid, 0.40 * wid)
    pucker = np.exp(-0.5 * ((d - (wid + 0.0012)) / 0.0006) ** 2) * (0.35 + 0.65 * taper)
    return core, np.clip(pucker - core, 0.0, 1.0)


def scar_tissue(col, core, pucker, skin):
    """Scar tissue on skin colours `col` (N,3 linear): the core lifted x1.45
    in linear light with a quarter of its chroma out -- healed tissue has
    no blood and less melanin, it is PALER than the skin round it -- and
    the pucker darkened .30 toward the man's own shadow tone."""
    lift = np.clip(col * 1.45, 0.0, 1.0)
    lum = lift @ np.array([0.2126, 0.7152, 0.0722])
    lift = lum[:, None] + 0.75 * (lift - lum[:, None])
    w = 0.90 * np.clip(core, 0, 1)[:, None]
    col = col * (1 - w) + np.clip(lift, 0.0, 1.0) * w
    p = 0.30 * np.clip(pucker, 0, 1)[:, None]
    return col * (1 - p) + _tone(skin, SHADOW)[None, :] * p


SCAR_RELIEF = (0.0008, 0.0002)      # the core proud, the pucker sunk (metres)

# The browser's one scar (`look.scar`: AL-WAHSH, ZAYOS), as a stroke: down
# out of his left brow onto the cheekbone, where shade(scar=True) draws it.
BROW_SCAR = dict(at="face", a=(0.010, BROW_Z + 0.006), b=(0.052, BROW_Z + 0.006 - 0.62 * 0.042), w=0.0017)


def scar_strokes(P, strokes):
    """(core, pucker) of a man's scars at P, 0..1 -- every stroke in
    `strokes` that this point can carry, the strongest of each. A stroke is
    a dict: `at` 'face' (on the head, in (x, z), x signed: + his left),
    'front' or 'back' (on the trunk, in (x, z), gated to its side), or a
    limb -- 'upperarm_l', 'lowerarm_r', ... -- with `t` (t0, t1) along it
    from its joint, `side` ('outer', 'inner', 'flexor' or 'back') and
    `across` (a slash across the limb rather than a cut along it). `w` is
    the half-width; `stitches` adds the dots a stitched wound leaves either
    side of its line (every 7 mm, 4 mm out, 1 mm across)."""
    n = len(P)
    core = np.zeros(n); puck = np.zeros(n)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    for k, s in enumerate(strokes):
        at = s.get("at", "face")
        if at in ("face", "front", "back"):
            a, b = np.asarray(s["a"], float), np.asarray(s["b"], float)
            d, t = _seg_dist(x, z, a, b)
            gate = np.ones(n) if at == "face" else (ramp(y, 0.000, -0.020) if at == "front" else ramp(y, 0.000, 0.020))
            L = float(np.hypot(*(b - a)))
            along = t * L
            dirn = (b - a) / max(L, 1e-9); nrm = np.array([-dirn[1], dirn[0]])
            side_off = (x - a[0]) * nrm[0] + (z - a[1]) * nrm[1]
        else:
            from .anatomy import Jp
            limb, lr = at.rsplit("_", 1)
            sg = 1.0 if lr == "l" else -1.0
            m = np.array([sg, 1.0, 1.0])
            j0 = {"upperarm": "upperarm_l", "lowerarm": "lowerarm_l"}[limb]
            j1 = {"upperarm": "lowerarm_l", "lowerarm": "hand_l"}[limb]
            p0, p1 = np.array(Jp(j0)) * m, np.array(Jp(j1)) * m
            tt, r, fr, sd = _seg_frame(P, p0, p1)
            Llimb = float(np.linalg.norm(p1 - p0))
            # the angle round the limb, 0 at the side the stroke is on: out
            # (away from the trunk, +x on his left), in, the front (the
            # flexor side of a forearm in the A-pose) or the back
            ang = np.arctan2(sd, fr)
            outward = np.arctan2(-sg * 1.0, 0.0)          # sd points in toward the trunk on his left
            centre = {"outer": outward, "inner": outward + np.pi, "flexor": 0.0, "back": np.pi}[s.get("side", "outer")]
            da = (ang - centre + np.pi) % (2 * np.pi) - np.pi
            arc = da * np.maximum(r, 1e-6)
            t0, t1 = s["t"]
            if s.get("across"):
                a = np.array([t0 * Llimb, -0.022]); b = np.array([t1 * Llimb, 0.022])
            else:
                a = np.array([t0 * Llimb, 0.0]); b = np.array([t1 * Llimb, 0.0])
            d, t = _seg_dist(tt * Llimb, arc, a, b)
            gate = (r < 0.09).astype(float) * (np.abs(da) < 1.6)
            L = float(np.hypot(*(b - a))); along = t * L
            dirn = (b - a) / max(L, 1e-9); nrm = np.array([-dirn[1], dirn[0]])
            side_off = (tt * Llimb - a[0]) * nrm[0] + (arc - a[1]) * nrm[1]
        c, p = scar_masks(d, t, s["w"], P, seed=float(k))
        if s.get("stitches"):
            # a dot either side of the line every 7 mm, 4 mm out
            ph = (along / 0.007) % 1.0
            dot = np.exp(-0.5 * (((ph - 0.5) * 0.007) ** 2 + (np.abs(side_off) - 0.004) ** 2) / 0.0010 ** 2)
            dot = dot * (t > 0.02) * (t < 0.98)
            c = np.maximum(c, 0.85 * dot)
        core = np.maximum(core, c * gate); puck = np.maximum(puck, p * gate)
    return core, np.clip(puck - core, 0.0, 1.0)


def shade(P, skin, hair, beard, base_rgb=None, beard_k=1.0, scar=False, out=None):
    """Colour and relief for points on the head.

    P        (N,3) positions, metres, in the build's frame
    skin     the base skin colour, linear -- the browser build's number
    hair     hair colour, linear
    beard    beard colour, linear -- or None for a clean-shaven man, which
             skips the beard, the moustache and the sideburns together
    beard_k  how much beard there is, 0..1: the alpha of the browser's wash.
             The colour already carries it (it is composited over the skin
             before it gets here); this scales the shadow the beard casts
             and the relief it adds, which the colour cannot carry.
    scar     a boxer's brow scar (`look.scar`) -- AL-WAHSH and ZAYOS.
    base_rgb (N,3) colour to start from, or None to start from `skin`
    out      a dict, or None: given one, shade() leaves the beard's own
             weight in out["beard"] (N,) for the roughness to read

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
    over(blob(P, EAR_X, EAR_Z, 0.013, 0.024), tone(BLOOD), 0.30)     # the ear
    over(blob(P, 0.0125, NOSE_Z + 0.0045, 0.0055, 0.0050), tone(BLOOD), 0.26)  # the ala
    over(blob(P, 0.031, EYE_Z - 0.0060, 0.016, 0.005), tone(BLOOD), 0.18)  # lower lid
    over(blob(P, 0.000, 1.586, 0.020, 0.012, mirror=False), tone(ZONE_MID), 0.20)  # chin

    # ---- 3. the creases: where light does not reach -------------------
    # A face is read by its shadows more than its colours. None of these
    # existed before, which is the other half of why he looked like wax.
    # (The weights and places are LOOK's since 2026-09-28; the defaults are
    # the numbers written here before.)
    M = LOOK
    darken(blob(P, 0.031, EYE_Z + M["lid_fold"][0], 0.020, 0.0055), M["lid_fold"][1])   # upper lid fold
    darken(blob(P, 0.033, EYE_Z - 0.0115, 0.017, 0.0045), M["under_eye"])       # under the eye
    darken(blob(P, 0.011, EYE_Z - 0.002, 0.005, 0.012), 0.22)                   # side of the nose root
    darken(blob(P, 0.0205, NOSE_Z + 0.0065, 0.0028, 0.0060), 0.20)              # the alar crease
    nasolabial = bar(P, 0.0195, 0.040, lambda u: NOSE_Z + 0.009 - 0.62 * (u - 0.0195), 0.0038)
    darken(nasolabial, M["nasolabial"][0])                              # faint at his age (0.14)
    if M["nasolabial"][1]:
        rel -= nasolabial * M["nasolabial"][1]
    if M["hollow_shade"]:
        darken(blob(P, 0.047, 1.6300, 0.012, 0.0085), M["hollow_shade"])   # under the cheekbone
    darken(blob(P, 0.000, MOUTH_Z - 0.0133, 0.016, 0.0040, mirror=False), 0.26)   # under the lower lip
    # the mouth corners, following the lips' line down to them (lip_drop)
    darken(blob(P, 0.026, MOUTH_Z - 0.0004 - (M["lip_drop"] - 0.0024), 0.005, 0.0055), M["lip_corner"])
    # under the jaw: along its lower border, which rises from the chin to
    # the angle since the skull was redrawn (2026-09-26) -- it was a level
    # band at the old chin line
    darken(bar(P, 0.000, 0.060, lambda u: 1.5705 + 0.47 * u, 0.0055), 0.30)
    darken(blob(P, EAR_X - 0.009, EAR_Z, 0.006, 0.026), 0.28)           # where the ear meets

    # ---- 4. the hairline, feathered -----------------------------------
    hw = hairline_weight(P)
    # his own hair colour, grey at the temples where he is going grey, in
    # the cut's strands and clumps -- the same ones the hair material
    # wears above the seam (hair_strands), so the two meet
    st_rel, st_shade, _st_rough = hair_strands(P)
    w_h = (np.clip(hw, 0, 1) * on_face)[:, None]
    col[:] = col * (1 - w_h) + hair_colour(P, hair) * st_shade[:, None] * w_h
    # the fade, the same one the hair material itself wears
    # (finish.kit_colour): the material boundary sits above the hairline on
    # the front and the sides (assembly.HAIR_MARGIN), so the band between
    # is this paint, and it must match the hair above it
    over(hw * hair_fade(P), skin, 1.0)
    # Not a 1 mm step of relief across the hairline any more: that, with
    # the shell's own step (assembly.HAIR_TAPER), was the pale rope across
    # every forehead. The hair's own strands, where there is hair.
    rel += hw * st_rel
    darken(hw * (1.0 - hw) * 4.0 * 0.10, 0.30)                          # a little shade at the edge

    # ---- 5. the brows: two of them ------------------------------------
    # They were one Gaussian a side with sigma 26 mm at x = +-31 mm, which
    # overlap to 0.96 weight at the midline: a single bar straight across
    # the forehead. A brow is ~40 mm long and the gap between them is ~18 mm.
    # Since 2026-09-28 its line, weight and colour are LOOK's: dropped, the
    # inner end pulled down against the tail (the scowl), the arch; with
    # the defaults, the brow as it was.
    b0 = M["brow_in"]
    if (M["brow_drop"], M["brow_slant"]) == (0.0, 0.0):
        zline = BROW_Z - 0.0022
    else:
        zline = lambda u: (BROW_Z - 0.0022 - M["brow_drop"]
                           - M["brow_slant"] * np.clip(1.0 - (u - b0) / (0.050 - b0), 0.0, 1.0) ** 1.5)
    brow = bar(P, b0, 0.050, zline, M["brow_thick"], feather=0.0022, arch=M["brow_arch"])
    brow = brow * ramp(ax, b0 - 0.0015, b0 + 0.0035)                    # keep the glabella clear
    brow = brow * (0.72 + 0.56 * fbm(P, 900.0, 2, 11.0))                # hairs, not paint
    brow = np.clip(brow, 0, 1) * ramp(fwd, 0.25, 0.55)
    # scar tissue grows no hair: a brow a scar crosses is split by it
    strokes = [s for s in (M["scars"] or ()) if s.get("at", "face") == "face"]
    sc_core = sc_puck = None
    if strokes:
        sc_core, sc_puck = scar_strokes(P, strokes)
        brow = brow * (1.0 - np.clip(1.6 * sc_core, 0.0, 1.0))
    over(brow, brow_rgb(hair, beard), 0.94)
    rel += brow * 0.0009
    if out is not None:
        out["brow"] = brow * on_face

    # the glabella's furrow -- the scowl: two short vertical creases
    # between the brows' inner ends, 5 mm off the midline, 12 mm long
    if M["furrow"][0] or M["furrow"][1]:
        fur = (np.exp(-0.5 * ((ax - 0.0050) / 0.0007) ** 2) * ramp(z, BROW_Z - 0.0105, BROW_Z - 0.0070)
               * ramp(z, BROW_Z + 0.0015, BROW_Z - 0.0020)) * ramp(fwd, 0.40, 0.70)
        darken(np.clip(fur, 0, 1), M["furrow"][0])
        rel -= np.clip(fur, 0, 1) * M["furrow"][1]
        if out is not None:
            out["furrow"] = np.clip(fur, 0, 1) * on_face

    # ---- 5b. a boxer's scar --------------------------------------------
    # One side only -- a real scar is not symmetric -- running down out of
    # the brow onto the cheekbone, the classic cut-man's cut. Paler than
    # the skin it crosses (SCAR, no blood in healed tissue) and a shallow
    # RIDGE, not a groove: scar tissue sits slightly proud, it does not sink.
    # That is the browser's `look.scar` as it was painted. SCAR as a tone
    # (the ratio of #caa48f to Saud's #f0d8c4) lands DARKER on a dark man
    # -- 5.2 L* darker on AL-WAHSH -- and 3.4 mm wide under 0.4 mm of relief
    # it never showed; a man with LOOK['scars'] is painted as tissue
    # instead: lifted, a pucker either side, 0.8 mm proud (scar_tissue).
    if M["scars"] is None:
        if scar:
            line = bar(P, 0.010, 0.052, lambda u: BROW_Z + 0.006 - 0.62 * (u - 0.010), 0.0017, feather=0.0022)
            side = ramp(x, -0.006, 0.006)          # his left (+x) only
            mask = line * side
            over(mask, tone(SCAR), 0.60)
            rel += mask * 0.0004
    elif sc_core is not None:
        w_c = sc_core * on_face; w_p = sc_puck * on_face
        col[:] = scar_tissue(col, w_c, w_p, skin)
        rel += w_c * SCAR_RELIEF[0] - w_p * SCAR_RELIEF[1]
        if out is not None:
            out["scar"] = w_c; out["pucker"] = w_p

    # ---- 6. the eyes: lash line and lid crease ------------------------
    # The lash lines ride the lid margins sculpt.drape_eyes cuts -- the
    # fissure of sculpt.aperture, corner to corner, the upper crest inside
    # the pupil and the outer corner 2 mm up -- just outside the margin on
    # the lid's own skin. Since 2026-09-26: they followed an arch over the
    # old Gaussian lids, which were closed over most of the globe.
    from .sculpt import aperture, X_MED, X_LAT, Z_MED
    lash = bar(P, X_MED, X_LAT, lambda u: aperture(u)[0] + 0.0004, M["lash"][0], feather=0.0016)
    over(lash * ramp(fwd, 0.30, 0.60), hex_lin(LASH), M["lash"][1])
    rel -= lash * 0.0003
    lower_lash = bar(P, X_MED + 0.002, X_LAT, lambda u: aperture(u)[1] - 0.0003, 0.0005, feather=0.0016)
    over(lower_lash * ramp(fwd, 0.30, 0.60), hex_lin(LASH), 0.32)
    # the caruncle: the pink of the inner corner, which the fissure opens on
    # (the globe's white stops 4 mm short of it)
    over(blob(P, X_MED + 0.0022, Z_MED + 0.0003, 0.0017, 0.0015), tone(BLOOD), 0.75)
    # the lid's own fold, a millimetre over its painted crease (lid_fold)
    fold_z = EYE_Z + 0.0085 if M["lid_fold"][0] == 0.0075 else EYE_Z + M["lid_fold"][0] + 0.0010
    rel += blob(P, 0.031, fold_z, 0.019, 0.0040) * 0.0011

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
    # (LOOK's since 2026-09-28: the drop to the corners, the bow, the lips'
    # thickness and weight, the seam; the defaults are the numbers before)
    mid = MOUTH_Z - M["lip_drop"] * u * u                                 # the lips' line drops at the corners
    bow = M["lip_bow"] * np.exp(-(((u - 0.27) / 0.24) ** 2)) - 0.34 * np.exp(-((u / 0.16) ** 2))
    t_up = M["lip_up"] * taper ** 0.55 * (1.0 + bow)
    t_lo = M["lip_lo"] * taper ** 0.50
    f = 0.0007
    upper = ramp(z, mid - f, mid + f) * ramp(z, mid + t_up + f, mid + t_up - f)
    lower = ramp(z, mid - t_lo - f, mid - t_lo + f) * ramp(z, mid + f, mid - f)
    lips = np.clip((upper + lower) * ramp(u, 1.02, 0.93), 0, 1) * ramp(fwd, 0.35, 0.65)
    over(lips, tone(LIP), M["lip_k"])
    over(np.clip(upper, 0, 1) * lips, tone(LIP_DEEP), M["lip_deep"])  # the upper lip reads darker
    rel += (upper * 0.0007 + lower * 0.0012) * np.clip(taper, 0, 1)
    mouthline = ramp(z, mid - 0.0009, mid) * ramp(z, mid + 0.0009, mid) * ramp(u, 1.00, 0.90)
    over(mouthline * ramp(fwd, 0.35, 0.65), tone(LIP_DEEP), M["lip_seam"][0])
    rel -= mouthline * M["lip_seam"][1]
    if out is not None:
        out["mouthline"] = mouthline * ramp(fwd, 0.35, 0.65) * on_face
    # philtrum: two ridges and the groove between them
    rel += (bar(P, 0.0035, 0.0085, 1.6265, 0.0055) * 0.0007
            - blob(P, 0.000, 1.6265, 0.0028, 0.0055, mirror=False) * 0.0008)

    # ---- 8. the nostrils ----------------------------------------------
    # Two small ovals under the tip, each side of the columella (sculpt's
    # nostril hollow, 7 mm out), not the 7 mm-wide dark pair 16 mm apart
    # that, with the old sculpt's 8 mm hollows, read as one slot across the
    # front of the nose (2026-09-26).
    nose_hole = blob(P, 0.0068, NOSE_Z + 0.0012, 0.0024, 0.0017)
    over(nose_hole * ramp(fwd, 0.55, 0.85), hex_lin('#3a2119'), 0.70)
    rel -= nose_hole * 0.0012
    rel += blob(P, 0.0135, NOSE_Z + 0.0050, 0.0045, 0.0040) * 0.0009             # the ala's rim

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
        col[:] = np.clip(col * (1.0 + (0.20 * blotch + 0.10 * pore) * on_face)[:, None], 0.0, 1.0)
        rel += (0.00010 * pore + 0.00022 * blotch) * on_face
        _nose_tape(P, fwd, on_face, col, rel, out)
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
    beard_w = np.clip(np.maximum(beard_w, M["mous"] * mous * ramp(fwd, 0.45, 0.75)), 0, 1)
    beard_w = beard_w * (1.0 - 0.96 * np.clip(lips + mouthline, 0, 1))
    # stubble: the cut ends of hairs, crisp, a follicle a cell -- gappier
    # where a beard really is thinner. It was a smooth noise at 0.8 mm
    # (fbm at 1250), and a smooth noise under a wash is a soft brown blur:
    # in every face render the stubble read as a smear of dirt round the
    # mouth. Beard density is 20-50 hairs a square centimetre, 1.4-2.2 mm
    # apart; 1.1 mm cells with 0.45 mm dots measure 38 a square centimetre
    # on a flat patch of jaw (10 % cover) -- two to three texels of the face
    # chart each, sharp-edged, over a thinner even shadow.
    foll = follicles(P, 0.0011, 0.00045, 5.0)
    # The even shadow under the dots follows how much beard there is. On
    # Saud's light stubble (beard_k .30) it is 0.60 of the old wash and the
    # dots carry the rest; on AL-WAHSH's full beard (.92) it is back to the
    # old wash's 1.02, dots on top -- a flat 0.60 on him read as a day's
    # stubble on a man the browser draws with a beard.
    shadow = 0.60 + 0.42 * smooth(np.clip((beard_k - 0.30) / 0.62, 0.0, 1.0))
    grain = np.clip(shadow + 1.00 * foll + 0.25 * (fbm(P, 400.0, 2, 5.0) - 0.5), 0, 1.5)
    dens = np.clip(1.06 - 0.72 * smooth(np.clip((lat - 0.30) / 0.60, 0, 1)), 0.34, 1.0)
    dens = dens * np.clip(0.70 + 0.55 * ramp(z, MOUTH_Z - 0.010, MOUTH_Z - 0.044), 0, 1.0)  # fullest on the chin
    bw = np.clip(beard_w * dens * grain, 0, 1)
    # A wash, not a fill. over() lerps toward the beard's own colour, and
    # where the beard is dense that REPLACED what the creases above had
    # painted -- measured on the shipped albedo, under the full beard about
    # 20 % of the under-jaw shadow survived. The browser draws the beard as
    # rgba over whatever is beneath it, so this multiplies: beard/skin is
    # the wash's tint (beard is rgba_over(beard, skin), so it is <= 1 per
    # channel), and on plain skin the result is exactly the old lerp.
    # The wash's tint is the browser's beard-over-skin, cooled: shaved
    # stubble under skin reads blue-grey, not brown -- a brown tint on a
    # light face is the other half of why it read as dirt. Half of it goes
    # to its own luminance and the blue is lifted 6 %; on the dark skin of
    # a man with a full beard the tint is near-neutral already and barely
    # moves.
    tint = np.asarray(beard) / np.asarray(skin)
    lum = float(np.dot(tint, [0.2126, 0.7152, 0.0722]))
    tint = 0.5 * tint + 0.5 * lum * np.array([0.98, 1.00, 1.06])
    def wash(mask, k):
        w = (np.clip(mask, 0, 1) * k * on_face)[:, None]
        col[:] = np.clip(col * (1.0 - w + w * tint[None, :]), 0.0, 1.0)
    wash(bw, 0.90)
    rel += bw * 0.0006 * beard_k
    if M["beard_grey"]:
        # grey coming in through the beard: a sparser set of cut ends in
        # the temples' grey (GREY_HAIR), over the dark ones
        gf = follicles(P, 0.0016, 0.00045, 29.0)
        over(np.clip(beard_w * dens, 0, 1) * gf, hex_lin(GREY_HAIR), M["beard_grey"])
    if out is not None:
        out["beard"] = np.clip(beard_w * dens, 0, 1) * on_face
    darken(np.clip(beard_w * dens, 0, 1) * 0.5, 0.20 * beard_k)           # the shadow a beard casts on skin
    # a sideburn running down in front of the ear, joining the hair
    # (in by however far the ear moved in with the narrower skull of
    # 2026-09-26: it was drawn for an ear at 0.0785, and left there it lay
    # on the ear)
    ds = EAR_X - 0.0785
    side = bar(P, 0.058 + ds, 0.075 + ds, lambda t: HAIRLINE[0] - 0.062 - 1.55 * (t - 0.058 - ds), 0.0060, feather=0.0035)
    wash(np.clip(side * ramp(fwd, 0.10, 0.40) * grain, 0, 1), 0.72)

    # ---- 10. the grain of the skin itself ------------------------------
    # 2.4 % and 1.4 % of spread (fbm spreads 0.12 about its mean; the old
    # 0.085 and 0.030 were 1 % and 0.4 %)
    pore = fbm(P, 1100.0, 3, 23.0) - 0.5
    blotch = fbm(P, 90.0, 3, 41.0) - 0.5
    col[:] = np.clip(col * (1.0 + (0.20 * blotch + 0.10 * pore) * on_face)[:, None], 0.0, 1.0)
    rel += (0.00010 * pore + 0.00022 * blotch) * on_face
    _nose_tape(P, fwd, on_face, col, rel, out)

    rel *= on_face
    return col, rel, on_face


def _nose_tape(P, fwd, on_face, col, rel, out=None):
    """LOOK['nose_tape']: a strip of tape across the bridge of a broken
    nose (the brawler's), over everything else -- tape has no pores and no
    beard -- standing 0.3 mm proud. Its roughness is repaint_head's."""
    T = LOOK["nose_tape"]
    if not T:
        return
    x, z = P[:, 0], P[:, 2]
    f = 0.0006
    x0, x1 = T["x"]; h = T["h"]
    tape = (ramp(x, x0 - f, x0 + f) * ramp(x, x1 + f, x1 - f) * ramp(np.abs(z - T["z"]), h + f, h - f)
            * ramp(fwd, 0.55, 0.75)) * on_face
    w = np.clip(tape, 0, 1)[:, None]
    col[:] = col * (1 - w) + hex_lin(T["colour"])[None, :] * w
    rel += tape * 0.0003
    if out is not None:
        out["nose_tape"] = tape


# The body is skin too. shade() only describes a head, so without this every
# other square centimetre of him -- arms, neck, hands -- bakes out as one
# flat constant, which is the other half of the wax. Quieter than the face:
# no zones, no creases, just the variation that stops a surface reading as
# paint.
def hairline_weight(P):
    """How much hair is painted on the skin at P: 0 below the hairline, 1
    above it, feathered +-3.5 mm about the cut plane and jittered, with the
    temple recession cut into it. On its own because finish.repaint_head's
    roughness reads it too: the skin material's band above the hairline
    (assembly.HAIR_MARGIN) must be as matt as the hair material it meets."""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    fwd = forwardness(P); lat = lateral(P)
    z0, z1 = HAIRLINE
    # HAIRLINE is quoted at y = -0.09 and y = +0.09, so the divisor is 0.18:
    # anything else puts the painted line off the cap's cut by a millimetre
    # or two all the way round.
    plane = z0 + (z1 - z0) * np.clip((y + 0.09) / 0.18, -0.4, 1.4)
    # 2026-09-26: the edge is no longer a jittered ramp (fbm at 260 / m, a
    # beaded rope when it was lit on the shell's step) but what a real
    # hairline is -- the hair thinning out to single hairs below a soft
    # line: a core that is full hair from 4 mm above the plane, and below
    # it hairs growing sparser (follicle dots, kept where a patchy density
    # is under a probability falling to nothing 4 mm below the plane).
    edge = fbm(P, 140.0, 2, 3.0) - 0.5
    h = z - plane - 0.0030 * edge
    core = ramp(h, 0.0004, 0.0040)
    dots = follicles(P, cell=0.0016, radius=0.00055, seed=17.0)
    patch = np.clip((fbm(P, 650.0, 2, 23.0) - 0.30) / 0.40, 0.0, 1.0)
    prob = ramp(h, -0.0040, 0.0008)
    # only where the probability is above nothing: ramp(prob - patch)
    # alone gave half-strength dots over the whole forehead wherever the
    # patchiness was 0 (the first fast build, speckled like freckles)
    stray = dots * ramp(prob - patch, 0.0, 0.08) * (prob > 0.0)
    hw = np.maximum(core, 0.85 * stray)
    # a temple recession, which every young man has and a swim cap does not.
    # Bounded to the band under plane + 7.5 mm: the hair MATERIAL starts at
    # plane + 8 (assembly.HAIR_MARGIN), and the paint must have reached full
    # hair by then or the recession's corner shows as a step at the seam.
    temple = (ramp(lat, 0.52, 0.86) * ramp(z, HAIRLINE[0] - 0.052, HAIRLINE[0] - 0.004) * ramp(fwd, 0.10, 0.34)
              * ramp(z - plane, 0.0075, 0.0035))
    hw = np.clip(hw - 0.75 * temple, 0.0, 1.0)
    if HAIR["style"] == "fringe":
        # The fringe is paint over the forehead, with the locks
        # (assembly.hair_parts) for lift: at a 3.5 mm remesh a lock of hair
        # is a bump, and the ragged edge that says "fringe" is finer than
        # that. Longest in the middle, pointed locks, gone by the temples.
        u = np.clip(np.abs(x) / 0.058, 0.0, 1.0)
        # a tip every 8.5 mm, each lock a little longer or shorter
        k = np.floor(x / 0.0085 + 0.5)
        tip = (1.0 - np.abs(np.sin(np.pi * x / 0.0085))) ** 1.3
        length = 0.7 + 0.6 * (np.sin(k * 12.9898) * 43758.5453 % 1.0)
        lower = plane - 0.008 - (0.004 + 0.012 * tip * length) * (1.0 - u * u)
        fringe = (ramp(z, lower - 0.0010, lower + 0.0010) * ramp(np.abs(x), 0.058, 0.044)
                  * ramp(fwd, 0.10, 0.30))
        hw = np.maximum(hw, fringe)
    return hw

# ---- the cut, 2026-09-24 ---------------------------------------------------
# Which cut this man wears and how grey he is at the temples: module state,
# like the rest of this module's per-man layout (one process per man --
# build_fighters.py), set by pipeline.build_fighter from the roster's
# `look.hairStyle` and `look.grey`. The geometry of each cut is in
# assembly.hair_parts; this is its paint, used twice -- on the hair material
# (finish.kit_colour) and on the band of skin painted as hair above the
# hairline (shade(), step 4) -- so the two meet.
HAIR = {"style": "quiff", "grey": 0.0}
# grey as it comes in at a Gulf man's temples: silver over the dark, not white
GREY_HAIR = '#9d978f'

def set_hair(style, grey=0.0):
    HAIR["style"] = style
    HAIR["grey"] = float(grey)

def hair_fade(P):
    """How much skin shows through the hair at P, 0..1 -- the fade. One
    formula for the hair material's own paint and for the hairline band
    painted on the skin, so they meet.

    crop / quiff / part / fringe: the faded sides of a short crop (the
    number every build had, 0.55 low on the sides). slick and curly: longer
    at the sides, so less. fade: a skin fade -- skin up to 1.72 on the sides
    and the back, hair from 1.765, the top untouched. buzz: clippered, the
    scalp showing through everywhere, more low on the sides, in the grain of
    the follicles."""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    ax = np.abs(x)
    crop = np.clip((0.070 - (1.76 - z)) / 0.05, 0, 1) * np.clip((ax - 0.045) / 0.03, 0, 1)
    style = HAIR["style"]
    # the sides and the back of the head, by which way the skull faces --
    # not by distance from the midline, which at 3-4 cm is already most of
    # the top of the head (the first fast build of 2026-09-26 faded the
    # whole top of the quiff and the crest to skin that way)
    Qn = P - HEAD_C
    Qn = Qn / np.maximum(np.linalg.norm(Qn, axis=1, keepdims=True), 1e-9)
    sides = np.maximum(ramp(np.abs(Qn[:, 0]), 0.50, 0.80), ramp(Qn[:, 1], 0.40, 0.70))
    if style == "fade":
        where = np.maximum(ramp(ax, 0.040, 0.060), ramp(y, 0.020, 0.050))
        return where * ramp(z, 1.765, 1.722)
    if style == "buzz":
        # Dense on top, thinner low on the sides: black hair cut to a few
        # millimetres still reads dark (at 0.30 on top, 2026-09-24's first
        # build, it read as a brown scalp).
        base = 0.14 + 0.30 * ramp(z, 1.780, 1.730) * ramp(ax, 0.035, 0.060)
        grain = fbm(P, 900.0, 2, 71.0)
        return np.clip(base + 0.24 * (grain - 0.5), 0.0, 0.70)
    if style == "crest":
        # 2026-09-26: the crest's sides and back clippered close -- the scalp
        # through dark stubble on the sides, skin low down -- and the ridge
        # down the middle (40 mm across, assembly.hair_parts) full
        off = ramp(ax, 0.020, 0.034)
        return off * (0.22 + 0.60 * sides * ramp(z, 1.770, 1.725))
    if style == "hightop":
        # a high-and-tight: skin up the sides and the back to 1.745, the
        # short top from 1.778, a hard line between
        return sides * ramp(z, 1.778, 1.745) * 0.95
    if style == "slick":
        return 0.30 * crop
    if style == "curly":
        return 0.45 * crop
    if style == "quiff":
        # 2026-09-26: a faded quiff -- the sides taken lower, so the length
        # on top reads against them (0.55 * crop before, the same as a crop)
        return 0.80 * sides * ramp(z, 1.772, 1.735)
    return 0.55 * crop

def hair_grey(P):
    """How grey the hair is at P: the temples and the sides above the ear,
    in strands, scaled by the man's `look.grey`."""
    if HAIR["grey"] <= 0.0:
        return np.zeros(len(P))
    z = P[:, 2]
    temple = (ramp(lateral(P), 0.55, 0.85) * ramp(z, 1.700, 1.720) * ramp(z, 1.790, 1.765)
              * ramp(forwardness(P), -0.45, 0.05))
    strands = 0.55 + 0.9 * fbm(P * np.array([1.0, 0.35, 1.0]), 700.0, 2, 5.0)
    return np.clip(HAIR["grey"] * temple * strands, 0.0, 1.0)

def hair_colour(P, hair):
    """The hair's colour at P: his own, going grey at the temples."""
    g = hair_grey(P)[:, None]
    rgb = np.tile(np.asarray(hair, dtype=float), (len(P), 1))
    return rgb * (1.0 - g) + hex_lin(GREY_HAIR)[None, :] * g

def hair_part(P):
    """The hard part: a shaved line 1.5 mm wide on his right (x = -0.022),
    from the front hairline back to the crown. Zero for every other cut."""
    if HAIR["style"] != "part":
        return np.zeros(len(P))
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    return (ramp(np.abs(x + 0.022), 0.0013, 0.0005) * ramp(y, 0.040, 0.015)
            * ramp(z, 1.745, 1.755))

HEAD_C = np.array([0.0, 0.010, 1.700])     # about the skull's centre, for the flow's normal

def _proj(v, n):
    """v made tangent to the surface of normal n, unit."""
    t = v - np.sum(v * n, axis=1, keepdims=True) * n
    return t / np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)

def hair_flow(P):
    """Which way the hair lies at P, a unit tangent (N,3): the combing of
    each cut. The sides of every cut are combed down and back; the top by
    the cut -- a quiff brushed forward to its front and up it, a crest in
    toward the middle and back, a slick-back straight back, a part away
    from the line, a fringe forward and down."""
    style = HAIR["style"]
    Q = P - HEAD_C
    n = Q / np.maximum(np.linalg.norm(Q, axis=1, keepdims=True), 1e-9)
    x = P[:, 0]
    one = np.ones(len(P))
    side = _proj(np.stack([0 * one, 0.6 * one, -one], 1), n)
    if style == "quiff":
        top = _proj(np.stack([0 * one, -one, 0.6 * one], 1), n)
    elif style == "crest":
        top = _proj(np.stack([-np.tanh(x / 0.012), 0.5 * one, one], 1), n)
    elif style == "slick":
        top = _proj(np.stack([0 * one, one, 0 * one], 1), n)
    elif style == "part":
        top = _proj(np.stack([np.tanh((x + 0.022) / 0.006), 0.3 * one, 0 * one], 1), n)
    elif style == "fringe":
        top = _proj(np.stack([0 * one, -one, -0.5 * one], 1), n)
    else:
        top = _proj(np.stack([0 * one, -0.4 * one, one], 1), n)
    w = ramp(np.abs(n[:, 0]), 0.45, 0.80)[:, None]
    f = top * (1 - w) + side * w
    return f / np.maximum(np.linalg.norm(f, axis=1, keepdims=True), 1e-9)

def hair_strands(P):
    """The hair's own surface, per texel, 2026-09-26: (relief in metres,
    colour shade about 1, roughness). Until then the hair material carried
    the bake's pore noise and the skin's one roughness, 0.52 -- a smooth,
    even sheen, which is a helmet's. Now, for a cut with length: strands
    lying along hair_flow (noise squeezed 16 to 1 along the flow, 1.1 mm
    across -- two texels of the hair's map) gathered into clumps about
    5 mm across, their crowns lighter and a little glossier, the gaps
    between them darker and matt. For a clippered cut (buzz, hightop,
    fade, crop): the cut ends of hairs, follicle dots, and no flow. Curly:
    coils, the rims of cells about 4 mm across."""
    style = HAIR["style"]
    n = len(P)
    if style in ("buzz", "hightop", "fade", "crop", "bald"):
        dots = follicles(P, cell=0.0011, radius=0.00040, seed=41.0)
        grain = fbm(P, 380.0, 2, 43.0)
        rel = 0.00006 * (dots - 0.5) + 0.00008 * (grain - 0.5)
        shade = 0.92 + 0.16 * dots * (0.6 + 0.8 * grain)
        rough = 0.72 - 0.05 * dots
        if style == "hightop":
            # the short top a little longer than the sides: a brushed grain
            t = hair_flow(P)
            Q = P - HEAD_C
            Qs = Q - 0.90 * np.sum(Q * t, axis=1, keepdims=True) * t
            brush = fbm(Qs + HEAD_C, 700.0, 2, 47.0)
            top = ramp(P[:, 2], 1.772, 1.782)
            rel += top * 0.00010 * (brush - 0.5)
            shade *= 1.0 + top * 0.20 * (brush - 0.5)
        return rel, shade, rough
    if style == "curly":
        rim = ramp(worley_gap(P, 0.0042, 53.0), 0.30, 0.06)          # the coil's edge
        body = fbm(P, 900.0, 2, 59.0)
        rel = 0.00030 * (rim - 0.5) + 0.00006 * (body - 0.5)
        shade = 0.80 + 0.40 * rim * (0.7 + 0.6 * body)
        rough = 0.74 - 0.14 * rim
        return rel, shade, rough
    t = hair_flow(P)
    Q = P - HEAD_C
    Qs = Q - 0.94 * np.sum(Q * t, axis=1, keepdims=True) * t
    fine = fbm(Qs + HEAD_C, 900.0, 2, 61.0)
    clump = fbm(Qs + HEAD_C, 200.0, 2, 67.0)
    cl = smooth(np.clip((clump - 0.30) / 0.40, 0.0, 1.0))
    rel = 0.00032 * (cl - 0.5) + 0.00008 * (fine - 0.5)
    shade = 0.76 + 0.48 * cl + 0.14 * (fine - 0.5)
    rough = 0.70 - 0.20 * (cl - 0.5) - 0.04 * (fine - 0.5)
    return rel, shade, rough

def hair_texture(P):
    """The hair's own light and dark, a multiplier about 1: comb lines
    running front to back on a slick-back (the combed direction is y), a
    coarse clump on a textured top (fade, fringe, curly), nothing on the
    others -- their look is the geometry and the fade."""
    style = HAIR["style"]
    if style == "slick":
        lines = fbm(P * np.array([1.0, 0.08, 0.35]), 1500.0, 2, 13.0)
        return 0.82 + 0.36 * lines
    if style in ("fade", "fringe", "curly"):
        return 0.86 + 0.28 * fbm(P, 520.0, 2, 29.0)
    return np.ones(len(P))

# ---- the body's skin, 2026-09-23 ------------------------------------------
# Until then the body varied in VALUE only: one multiplicative mottle, so every
# square centimetre of him was the same hue at a slightly different brightness
# -- measured on the shipped albedo, ZAYOS's skin spread 2-4 levels in 255 and
# not a degree of hue -- and a surface that only changes brightness reads as
# painted plastic. Real skin changes HUE: blood reddens it where it is thin or
# flushed (knuckles, elbows, the tops of the shoulders, the fingertips), and
# melanin browns it in broad soft patches. Both are written as moves on this
# man's own skin, the way shade()'s zones are (tone()), so a dark man gets the
# same flush a light one does rather than a pink stain.
AREOLA = '#b58070'      # on Saud's skin; the same move on any other man's
NIPPLE = '#9c6758'
# 20 cm apart at the fourth rib, on the front of the lower pec: measured on the
# canonical body, the surface there is y -0.101 and faces forward (normal
# -0.98 in y). Everyone but ZAYOS wears a tee over it and has that skin
# stripped (pipeline.under_garments); on him it is the difference between a
# bare chest and a mannequin's.
AREOLA_AT = (0.098, -0.101, 1.335)
AREOLA_R, NIPPLE_R = 0.0135, 0.0042


def _tone(skin, h):
    return np.asarray(skin, dtype=float) * (hex_lin(h) / hex_lin(SAUD_SKIN))


def _near(P, c, r, feather):
    return ramp(np.linalg.norm(P - np.asarray(c, dtype=float)[None, :], axis=1), r + feather, r - feather)


def body_flush(P, joints_l=None):
    """Where blood shows through on a body, 0..1: the elbow's point, the
    knuckles, the fingertips, the tops of the shoulders. `joints_l` are the
    hand's own joints (anatomy.hand); without them the hand is skipped."""
    from .anatomy import Jp
    w = np.zeros(len(P))
    for s in (1, -1):
        m = np.array([s, 1.0, 1.0])
        el = np.array(Jp("lowerarm_l")) * m
        # the olecranon: behind the joint, where the skin is thin and creased
        w = np.maximum(w, _near(P, el + np.array([0.0, 0.028, 0.0]), 0.020, 0.018) * 0.9)
        sh = np.array(Jp("upperarm_l")) * m
        w = np.maximum(w, _near(P, sh + np.array([0.0, 0.0, 0.050]), 0.045, 0.035) * 0.45)
        if joints_l:
            for fi in ("f0", "f1", "f2", "f3", "thumb"):
                pts = joints_l.get(fi)
                if not pts: continue
                knuckle = np.array(pts[0]) * m; tip = np.array(pts[-1]) * m
                w = np.maximum(w, _near(P, knuckle, 0.008, 0.008) * 0.8)
                w = np.maximum(w, _near(P, tip, 0.009, 0.007) * 0.6)
    return np.clip(w, 0.0, 1.0)


def body_grain(P, col, skin=None, joints_l=None):
    """The body's skin colour at P, from `col` (N,3 linear). With `skin` --
    the man's base colour, linear -- it also carries the hue: blood and
    melanin mottling, the flush at the thin places, and the areolae. Without
    it, the old value-only grain (kept for callers that have no palette)."""
    blotch = fbm(P, 55.0, 3, 91.0) - 0.5
    pore = fbm(P, 950.0, 2, 107.0) - 0.5
    if skin is None:
        return np.clip(col * (1.0 + 0.055 * blotch + 0.022 * pore)[:, None], 0.0, 1.0)
    # Amplitudes are written as the spread they give: fbm's own spread about
    # its mean is 0.12 (3 octaves) to 0.14 (2), measured over the body, so
    # the old 0.055 and 0.022 were a 0.7 % and 0.3 % mottle -- 0.8 levels in
    # 255 on Saud's shipped arm, which is nothing. Now 3 % and 1.5 %.
    col = np.clip(col * (1.0 + 0.25 * blotch + 0.11 * pore)[:, None], 0.0, 1.0)
    blood = _tone(skin, BLOOD)
    # haemoglobin: 2-5 cm patches, the rosy/sallow drift across any body --
    # a lerp toward the blood tone of 0.08 +- 0.06, and 0.30 more where the
    # skin is thin and flushed
    hb = fbm(P, 24.0, 3, 131.0) - 0.5
    w = np.clip(0.08 + 0.50 * hb, 0.0, 0.25) + 0.30 * body_flush(P, joints_l)
    col = col * (1.0 - w[:, None]) + blood[None, :] * w[:, None]
    # melanin: broad (10 cm) and soft, 4 % either way, and it browns -- blue
    # drops fastest -- never greys
    mel = fbm(P, 9.0, 2, 151.0) - 0.5
    col = col * (1.0 - 0.30 * mel[:, None] * np.array([0.80, 1.00, 1.25])[None, :])
    # the areolae and nipples
    for s in (1, -1):
        c = np.array(AREOLA_AT) * np.array([s, 1.0, 1.0])
        front = ramp(P[:, 1], -0.080, -0.090)
        a = _near(P, c, AREOLA_R, 0.0030) * front
        col = col * (1.0 - 0.85 * a[:, None]) + _tone(skin, AREOLA)[None, :] * (0.85 * a[:, None])
        nip = _near(P, c, NIPPLE_R, 0.0012) * front
        col = col * (1.0 - 0.8 * nip[:, None]) + _tone(skin, NIPPLE)[None, :] * (0.8 * nip[:, None])
    return np.clip(col, 0.0, 1.0)


def body_roughness(P, joints_l=None):
    """How matt the body's skin is at P. It was one number, 0.52, over every
    square centimetre below the face -- a single even sheen is the plastic
    look. Skin is oiliest where the sebaceous glands are densest (the middle
    of the chest and the upper back), driest and roughest where it is thick
    and creased (elbows, knuckles), and it drifts between the two over a few
    centimetres everywhere, with pore-scale variation on top."""
    x, z = P[:, 0], P[:, 2]
    r = np.full(len(P), 0.58)
    r -= 0.07 * ramp(z, 1.22, 1.34) * ramp(z, 1.52, 1.44) * ramp(np.abs(x), 0.15, 0.09)   # sternum and upper back
    r += 0.10 * body_flush(P, joints_l)                                                    # the thick, creased places
    r += 0.42 * (fbm(P, 40.0, 3, 171.0) - 0.5)      # +-0.05 over a few centimetres
    r += 0.18 * (fbm(P, 700.0, 2, 181.0) - 0.5)     # +-0.025 at the pores
    return np.clip(r, 0.30, 0.85)


def worley_gap(P, cell, seed=0.0):
    """F2 - F1 of a jittered cell noise, in cell units: small along the
    boundaries between cells, so `ramp` on it draws a network of lines --
    which is what a vein pattern is at the scale the skin shows it."""
    q = P / cell
    base = np.floor(q)
    f1 = np.full(len(P), 9.0); f2 = np.full(len(P), 9.0)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = base + np.array([dx, dy, dz])
                ix, iy, iz = c[:, 0].astype(np.int64), c[:, 1].astype(np.int64), c[:, 2].astype(np.int64)
                jit = np.stack([_hash3(ix, iy, iz, seed + k) for k in (1.0, 2.0, 3.0)], axis=1)
                d = np.linalg.norm(q - (c + jit), axis=1)
                closer = d < f1
                f2 = np.where(closer, f1, np.minimum(f2, d)); f1 = np.where(closer, d, f1)
    return f2 - f1


def _seg_frame(P, a, b):
    """For points P against the segment a->b: the fraction along it, the
    distance off its axis, and the unit sideways vectors (front, side)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a; L = np.linalg.norm(d); d = d / L
    q = P - a; t = (q @ d) / L
    off = q - np.outer(q @ d, d)
    r = np.linalg.norm(off, axis=1)
    f = np.array([0.0, -1.0, 0.0]); f = f - d * (f @ d); f /= np.linalg.norm(f); sd = np.cross(d, f)
    return t, r, off @ f, off @ sd


def vein_line(P, d, s=1):
    """LOOK's 'contour' veins at P on a limb segment along the unit `d`,
    0..1 (2026-09-28): iso-lines of a two-octave value noise whose
    coordinates are squeezed `vein_stretch` times along the limb, so the
    lines run with it the way the veins of a forearm do -- one family, or
    two (the second at 0.8). `s` is the side (+1 his left), which seeds the
    other arm apart from this one."""
    V = LOOK
    d = np.asarray(d, dtype=float)
    Q = P - (1.0 - 1.0 / V["vein_stretch"]) * np.outer(P @ d, d)
    lw = V["vein_width"]
    seed = V["vein_seed"] + s
    line = ramp(np.abs(fbm(Q, V["vein_scale"], 2, seed) - 0.5), lw, lw * 0.35)
    if V["vein_lines"] > 1:
        n2 = fbm(Q, V["vein_scale"], 2, seed + 38.0)
        line = np.maximum(line, 0.8 * ramp(np.abs(n2 - 0.5), lw * 0.8, lw * 0.28))
    return line


def vein_numbers(side=1, r=0.038, build=1.0, step=0.0005):
    """The veins on one forearm (numpy, no mesh), 2026-09-28: a cylinder of
    radius `r` round the elbow-to-wrist axis over t 0.10-0.86, unrolled at
    `step`. Returns

      cover     the lines' share of the unrolled forearm (the raw line,
                before where-weights), 0..1
      aniso     their 6 mm autocorrelation along the limb over across it
                (a net the same every way is about 1)
      crossings how many veins (runs of the weighted mask over 0.5) a ring
                crosses in the 96 mm of arc centred on the flexor side,
                averaged along the forearm
      width     their median width there, metres
      peak      the relief's highest point there, metres
    """
    from .anatomy import Jp
    m = np.array([side, 1.0, 1.0])
    el, wr = np.array(Jp("lowerarm_l")) * m, np.array(Jp("hand_l")) * m
    d = wr - el; L = float(np.linalg.norm(d)); d /= L
    f = np.array([0.0, -1.0, 0.0]); f = f - d * (f @ d); f /= np.linalg.norm(f); sd = np.cross(d, f)
    ts = np.arange(0.10, 0.86, step / L)
    na = int(round(2 * np.pi * r / step))
    angs = np.linspace(-np.pi, np.pi, na, endpoint=False)
    T, AN = np.meshgrid(ts, angs)
    P = el[None, :] + np.outer(T.ravel() * L, d) + r * (np.outer(np.cos(AN.ravel()), f) + np.outer(np.sin(AN.ravel()), sd))
    rel, vein = body_relief(P, None, build=build)
    Vw = vein.reshape(T.shape)
    if LOOK["vein_style"] == "worley":
        raw = ramp(worley_gap(P, 0.021, seed=17.0 + side), 0.17, 0.06).reshape(T.shape)
    else:
        raw = vein_line(P, d, side).reshape(T.shape)
    def corr(a, axis, lag):
        b = np.roll(a, lag, axis=axis)
        return float(np.corrcoef(a.ravel(), b.ravel())[0, 1])
    lag = int(round(0.006 / step))
    along, across = corr(raw, 1, lag), corr(raw, 0, lag)
    mid = na // 2; half = int(round(0.048 / step))
    arc = Vw[mid - half: mid + half, :] > 0.5
    runs = (arc[1:] & ~arc[:-1]).sum(0) + arc[0]
    widths = []
    for j in range(0, arc.shape[1], 8):
        k = 0
        for v in arc[:, j]:
            if v: k += 1
            elif k: widths.append(k * step); k = 0
    peak = float((LOOK["vein_height"] * Vw[mid - half: mid + half, :]).max())
    return dict(cover=float(raw.mean()), aniso=along / max(across, 1e-3), crossings=float(runs.mean()),
                width=float(np.median(widths)) if widths else 0.0, peak=peak)


VEIN_RULES = dict(cover=0.15, aniso=3.0)     # every man on 'contour': lines under 15 % of the arm, 3x longer than wide


def check_veins(hold=None, build=1.0, assert_=True):
    """The veins on both forearms (vein_numbers): lines, not a net -- at
    most 15 % of the forearm, their 6 mm autocorrelation along the limb at
    least 3 times that across it; and for a man whose VEINS name a hold
    (`hold`: dict(crossings=(lo, hi), peak=m)), that many veins across the
    flexor side and that bold. Returns {side: numbers}."""
    out = {s: vein_numbers(s, build=build) for s in (1, -1)}
    if not assert_:
        return out
    for s, v in out.items():
        arm = "left" if s > 0 else "right"
        assert v["cover"] <= VEIN_RULES["cover"], "a net: the veins cover %.0f %% of his %s forearm, want %.0f at most" % (
            v["cover"] * 100, arm, VEIN_RULES["cover"] * 100)
        assert v["aniso"] >= VEIN_RULES["aniso"], "scales, not veins: along/across %.1f on his %s forearm, want %.1f" % (
            v["aniso"], arm, VEIN_RULES["aniso"])
        if hold:
            lo, hi = hold["crossings"]
            assert lo <= v["crossings"] <= hi, "%.1f veins across the flexor side of his %s forearm, want %.0f-%.0f" % (
                v["crossings"], arm, lo, hi)
            assert v["peak"] >= hold["peak"], "faint veins: %.2f mm of relief on his %s forearm, want %.2f" % (
                v["peak"] * 1000, arm, hold["peak"] * 1000)
    return out


def body_relief(P, joints_l=None, build=1.0, tape=None):
    """The skin's own relief below the face, in metres (+ is proud), and
    the vein mask, 0..1 -- 2026-09-25, "skin: surface detail". Everything
    here is finer than the 3.5 mm the mesh carries and lands in the normal
    map, the way the face's relief does:

      veins       a network of raised lines on the forearms (flexor side
                  most), the inner upper arm and the backs of the hands,
                  denser on the heavier build (a fighter's vascularity)
      knuckles    the metacarpal heads proud, and a crease across each
                  finger joint
      elbow       fine wrinkles over the olecranon
      clavicles   the collarbone's ridge with the hollow above it, and the
                  notch between them at the throat
      sternum, linea alba, the tendinous lines between the abs, the
      spinal furrow -- grooves
    Under tape (`tape`, 0..1 per point) the skin's relief is the tape's,
    so it is left flat there."""
    from .anatomy import Jp
    n = len(P)
    rel = np.zeros(n); vein = np.zeros(n)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    V = LOOK
    assert V["vein_style"] in ("worley", "contour"), "no such vein style: %r" % V["vein_style"]
    vk = float(np.clip(0.55 + 0.6 * (build - 1.0), 0.35, 1.0)) if V["vein_k"] is None else float(V["vein_k"])
    for s in (1, -1):
        m = np.array([s, 1.0, 1.0])
        sh, el, wr, he = (np.array(Jp(k)) * m for k in ("upperarm_l", "lowerarm_l", "hand_l", "hand_end_l"))
        # ---- veins: where they are (a weight per limb segment), then the lines
        w = np.zeros(n)
        t, r, fr, sd = _seg_frame(P, el, wr)
        band = smooth(np.clip((t - 0.04) / 0.10, 0, 1)) * (1.0 - smooth(np.clip((t - 0.86) / 0.10, 0, 1)))
        side = 0.55 + 0.45 * np.clip(fr / np.maximum(r, 1e-6), -1.0, 1.0)      # the flexor (front) side most
        w_fore = band * side * (r < 0.09)
        w = np.maximum(w, w_fore)
        t, r, fr, sd = _seg_frame(P, sh, el)
        band = smooth(np.clip((t - 0.30) / 0.15, 0, 1)) * (1.0 - smooth(np.clip((t - 0.88) / 0.10, 0, 1)))
        inner = np.clip(sd / np.maximum(r, 1e-6), 0.0, 1.0)                     # toward the body
        w_up = 0.55 * band * inner * (r < 0.09)
        w = np.maximum(w, w_up)
        t, r, fr, sd = _seg_frame(P, wr, he)
        back = np.clip(-fr / np.maximum(r, 1e-6), 0.0, 1.0)                     # the back of the hand (+Y)
        w_hand = 0.8 * (t > -0.1) * (t < 1.1) * back * (r < 0.06)
        w = np.maximum(w, w_hand)
        if w.max() > 0 and V["vein_style"] == "worley":
            # a cell-boundary net, the same every way -- as it was until
            # 2026-09-28; on the big men's forearms it read as reptile scales
            sel = w > 0.02
            gap = worley_gap(P[sel], 0.021, seed=17.0 + s)
            line = ramp(gap, 0.17, 0.06)
            vein[sel] = np.maximum(vein[sel], line * w[sel] * vk)
        elif w.max() > 0:
            # 'contour': lines running along the limb, each segment its own
            # (vein_line), so none is seamed at the elbow or the wrist
            for (a, b), ws in (((el, wr), w_fore), ((sh, el), w_up), ((wr, he), w_hand)):
                sel = ws > 0.02
                if sel.any():
                    line = vein_line(P[sel], (b - a) / np.linalg.norm(b - a), s)
                    vein[sel] = np.maximum(vein[sel], line * ws[sel] * vk)
        # ---- knuckles and creases
        if joints_l:
            for fi in ("f0", "f1", "f2", "f3", "thumb"):
                pts = joints_l.get(fi)
                if not pts: continue
                pts = [np.array(p) * m for p in pts]
                k0 = pts[0]
                rel += 0.0006 * np.exp(-((np.linalg.norm(P - k0, axis=1)) / 0.0075) ** 2)
                for k in (1, 2):
                    c = pts[k]; d = pts[k] - pts[k - 1]; d /= np.linalg.norm(d)
                    along = (P - c) @ d; near = np.linalg.norm(P - c, axis=1) < 0.014
                    rel -= 0.00035 * ramp(np.abs(along), 0.0018, 0.0006) * near
        # ---- the elbow's wrinkles
        ol = el + np.array([0.0, 0.028, 0.0])
        wr_m = _near(P, ol, 0.022, 0.016)
        rel += 0.00025 * (fbm(P, 260.0, 2, 199.0) - 0.5) * 2.0 * wr_m
    # ---- the collarbones: a ridge rising 12 mm from the sternal end to the
    # acromial, the supraclavicular hollow above it, the notch at the throat
    ax = np.abs(x)
    front = ramp(y, -0.020, -0.045)
    zc = 1.470 + 0.012 * np.clip(ax / 0.19, 0.0, 1.0)
    span = ramp(ax, 0.026, 0.040) * ramp(ax, 0.200, 0.180)
    rel += 0.0009 * np.exp(-((z - zc) / 0.0055) ** 2) * span * front
    rel -= 0.0012 * np.exp(-((z - zc - 0.022) / 0.011) ** 2) * ramp(ax, 0.060, 0.080) * ramp(ax, 0.180, 0.160) * front
    rel -= 0.0015 * np.exp(-(((x) / 0.014) ** 2 + ((z - 1.474) / 0.011) ** 2)) * front
    # ---- the sternum and the linea alba, the lines between the abs (all
    # four grooves times LOOK['cut'], a man's definition: 1.0 as they were)
    cut = float(V["cut"])
    mid = np.exp(-(x / 0.005) ** 2) * ramp(y, -0.050, -0.070)
    rel -= (0.0008 * cut) * mid * ramp(z, 1.220, 1.240) * ramp(z, 1.430, 1.410)
    rel -= (0.0006 * cut) * mid * ramp(z, 1.075, 1.095) * ramp(z, 1.235, 1.215)
    for zg in (1.211, 1.141):
        rel -= (0.0005 * cut) * np.exp(-((z - zg) / 0.004) ** 2) * ramp(ax, 0.070, 0.055) * ramp(y, -0.060, -0.080)
    # ---- the spinal furrow
    rel -= (0.0010 * cut) * np.exp(-(x / 0.009) ** 2) * ramp(y, 0.050, 0.075) * ramp(z, 1.02, 1.06) * ramp(z, 1.46, 1.42)
    rel += V["vein_height"] * vein
    if tape is not None:
        rel = rel * (1.0 - tape); vein = vein * (1.0 - tape)
    return rel, vein


def follicles(P, cell=0.0011, radius=0.00032, seed=0.0):
    """Stubble: one hair's cut end per jittered cell of `cell` metres, as a
    crisp dot of `radius` -- Worley F1 over the 27 neighbouring cells, so the
    dots are sharp-edged and a cell apart, not a soft noise. 0..1."""
    q = P / cell
    base = np.floor(q)
    best = np.full(len(P), 9.0)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = base + np.array([dx, dy, dz])
                ix, iy, iz = c[:, 0].astype(np.int64), c[:, 1].astype(np.int64), c[:, 2].astype(np.int64)
                jit = np.stack([_hash3(ix, iy, iz, seed + k) for k in (1.0, 2.0, 3.0)], axis=1)
                d = np.linalg.norm(q - (c + jit), axis=1)
                np.minimum(best, d, out=best)
    rr = radius / cell
    return ramp(best, rr, rr * 0.45)


# ---- a man's marks on the body, and the paint's checks, 2026-09-28 ---------
def body_scars(P, col, skin, tape=None):
    """LOOK['scars'] below the face -- on the trunk and the limbs -- painted
    as scar tissue over the body's colours `col` (N,3 linear), as
    finish.repaint_kit paints the skin. Returns (colour, relief in metres,
    the core's weight)."""
    strokes = [s for s in (LOOK["scars"] or ()) if s.get("at", "face") != "face"]
    n = len(P)
    if not strokes:
        return col, np.zeros(n), np.zeros(n)
    core, puck = scar_strokes(P, strokes)
    if tape is not None:
        core = core * (1.0 - tape); puck = puck * (1.0 - tape)
    return scar_tissue(col, core, puck, skin), core * SCAR_RELIEF[0] - puck * SCAR_RELIEF[1], core


def lstar(rgb):
    """CIE L* of linear colours (N,3)."""
    Y = np.asarray(rgb, dtype=float) @ np.array([0.2126, 0.7152, 0.0722])
    f = np.where(Y > 216 / 24389, np.cbrt(np.maximum(Y, 0.0)), (24389 / 27 * Y + 16) / 116)
    return 116 * f - 16


def _face_grid(step=0.0005, x=(-0.070, 0.070), z=(1.560, 1.790)):
    """Points on the skull's front surface, a regular grid in (x, z)."""
    xs = np.arange(x[0], x[1] + 1e-9, step); zs = np.arange(z[0], z[1] + 1e-9, step)
    X, Z = np.meshgrid(xs, zs)
    Y = np.array([A.head_surface_y(a, b) for a, b in zip(X.ravel(), Z.ravel())])
    return np.stack([X.ravel(), Y, Z.ravel()], 1), X, Z


def check_brows(slant_min=0.0, assert_=True):
    """The brows as painted (numpy, on the skull's own surface): two of
    them, not a bar -- under 5 % brow weight within 5 mm of the midline;
    and for a man held to a scowl (HOLDS' brow_slant), the brow's inner end
    at least `slant_min` under its TAIL (against its peak, the default
    arch alone passed). Returns the numbers."""
    xs = np.arange(0.0, 0.056, 0.0005); zs = np.arange(BROW_Z - 0.016, BROW_Z + 0.012, 0.0002)
    X, Z = np.meshgrid(xs, zs)
    Y = np.array([[A.head_surface_y(x, z) for x in xs] for z in zs])
    P = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
    out = {}
    shade(P, np.array([0.5, 0.35, 0.28]), np.array([0.02, 0.015, 0.01]), None, out=out)
    b = out["brow"].reshape(Z.shape)
    gap = float(b[:, xs < 0.005].max())
    live = [j for j in range(len(xs)) if b[:, j].max() > 0.5]
    zc = [float((b[:, j] * zs).sum() / max(b[:, j].sum(), 1e-9)) for j in live]
    inner, tail = zc[0], zc[-1]
    res = dict(gap=gap, slant=tail - inner, inner_x=float(xs[live[0]]))
    if assert_:
        assert gap < 0.05, "one brow, not two: %.2f weight within 5 mm of the midline" % gap
        assert not slant_min or tail - inner >= slant_min, "no scowl: the brow's inner end %.1f mm under its tail, want %.1f" % (
            (tail - inner) * 1e3, slant_min * 1e3)
    return res


PAINT_RULES = dict(brow=-15.0, furrow=-4.0, frown=0.003, scar=6.0, pucker=-3.0, tape=0.90)


def paint_numbers(skin, hair, beard, beard_k=1.0, scar=False, strokes=None):
    """The face as LOOK paints it on this man's colours (linear), measured
    on the skull's surface (numpy): the brows' L* against the skin round
    them, the glabella furrow's against the midline between, how far the
    lips' line drops from the middle to the corners, each face scar's
    centre and pucker against the skin 5-9 mm off it (`strokes`: the scars
    to look for -- this man's, whatever LOOK now paints; by default LOOK's,
    or the browser's brow scar), and the nose tape's weight at its middle."""
    P, X, Z = _face_grid()
    out = {}
    rgb, _rel, on = shade(P, skin, hair, beard, beard_k=beard_k, scar=scar, out=out)
    L = lstar(rgb)
    ax = np.abs(P[:, 0])
    res = {}
    brow = out["brow"]
    near = (ax > 0.012) & (ax < 0.048) & (np.abs(P[:, 2] - (BROW_Z - 0.002)) < 0.010)
    core = near & (brow > 0.5); zone = near & (brow < 0.05) & (out.get("scar", np.zeros(len(P))) < 0.05)
    res["brow"] = float(L[core].mean() - L[zone].mean()) if core.any() and zone.any() else 0.0
    if "furrow" in out:
        band = np.abs(P[:, 2] - (BROW_Z - 0.0045)) < 0.004
        f = band & (out["furrow"] > 0.5); z0 = band & (ax < 0.0015)
        res["furrow"] = float(L[f].mean() - L[z0].mean()) if f.any() and z0.any() else 0.0
    else:
        res["furrow"] = 0.0
    ml = out["mouthline"].reshape(X.shape)
    xs = X[0]; zs = Z[:, 0]
    def line_z(x0):
        j = int(np.argmin(np.abs(xs - x0)))
        col = ml[:, j]
        return float((col * zs).sum() / max(col.sum(), 1e-9)) if col.max() > 0.3 else float("nan")
    res["frown"] = line_z(0.0) - 0.5 * (line_z(0.0216) + line_z(-0.0216))
    if strokes is None:
        strokes = [s for s in (LOOK["scars"] or ()) if s.get("at", "face") == "face"] if LOOK["scars"] is not None else (
            [BROW_SCAR] if scar else [])
    res["scars"] = []
    for s in strokes:
        if s.get("at", "face") != "face":
            continue
        d, t = _seg_dist(P[:, 0], P[:, 2], np.asarray(s["a"], float), np.asarray(s["b"], float))
        mid = (t > 0.3) & (t < 0.7) & (on > 0.9)
        c = mid & (d < 0.3 * s["w"]); zn = mid & (d > 0.005) & (d < 0.009)
        pk = mid & (np.abs(d - (s["w"] + 0.0012)) < 0.0004)
        res["scars"].append(dict(centre=float(L[c].mean() - L[zn].mean()) if c.any() and zn.any() else 0.0,
                                 pucker=float(L[pk].mean() - L[zn].mean()) if pk.any() and zn.any() else 0.0))
    T = LOOK["nose_tape"]
    if T and "nose_tape" in out:
        at = (np.abs(P[:, 0] - 0.5 * (T["x"][0] + T["x"][1])) < 0.002) & (np.abs(P[:, 2] - T["z"]) < 0.001)
        res["tape"] = float(out["nose_tape"][at].mean()) if at.any() else 0.0
    return res


def check_paint(skin, hair, beard, beard_k=1.0, scar=False, strokes=None, grim=False, tape=False, assert_=True):
    """paint_numbers held to the grim face (2026-09-28): every man's brows at
    least 15 L* darker than the skin round them (a bald man's, painted in
    his skin, were 0.3 lighter); and for a man with a grim entry
    (`grim`), the glabella furrow at least 4 L* dark and the mouth's
    corners at least 3 mm under its middle (a frown, not a smile); every
    scar looked for (`strokes`, see paint_numbers) at least 6 L* PALER than
    the skin round it with a pucker at least 3 darker; the tape where a man
    wears it (`tape`). Returns the numbers."""
    r = paint_numbers(skin, hair, beard, beard_k, scar, strokes)
    if not assert_:
        return r
    R = PAINT_RULES
    assert r["brow"] <= R["brow"], "no brows: %.1f L* against the skin round them, want %.0f or darker" % (r["brow"], R["brow"])
    if grim:
        assert r["furrow"] <= R["furrow"], "no furrow: the glabella %.1f L* against the midline, want %.0f" % (r["furrow"], R["furrow"])
        assert r["frown"] >= R["frown"], "no frown: the mouth's corners %.1f mm under its middle, want %.0f" % (
            r["frown"] * 1000, R["frown"] * 1000)
    for k, s in enumerate(r["scars"]):
        assert s["centre"] >= R["scar"], "a dark scar: scar %d's centre %.1f L* against the skin round it, want +%.0f (paler)" % (
            k, s["centre"], R["scar"])
        assert s["pucker"] <= R["pucker"], "no pucker: scar %d's edge %.1f L*, want %.0f" % (k, s["pucker"], R["pucker"])
    if tape:
        assert r.get("tape", 0.0) >= R["tape"], "no tape: %.2f over the bridge, want %.2f" % (r.get("tape", 0.0), R["tape"])
    return r


def check_body_scars(strokes, skin, assert_=True):
    """Each of `strokes` below the face -- a man's body scars, as his table
    has them -- painted by body_scars (as finish.repaint_kit paints the
    skin, with whatever LOOK now holds) at least 6 L* paler than the skin
    8-12 mm off its centre line. Returns each stroke's lift."""
    out = []
    for s in strokes:
        if s.get("at", "face") == "face":
            continue
        # points on and beside the stroke, generated in its own frame
        P = _stroke_points(s)
        col = np.tile(np.asarray(skin, float), (len(P), 1))
        rgb, _rel, _c = body_scars(P, col, skin)
        L = lstar(rgb)
        d = _stroke_points(s, offsets=True)
        c = np.abs(d) < 0.3 * s["w"]; zn = (np.abs(d) > 0.008) & (np.abs(d) < 0.012)
        out.append(float(L[c].mean() - L[zn].mean()))
    if assert_:
        for k, v in enumerate(out):
            assert v >= PAINT_RULES["scar"], "no body scar: stroke %d %.1f L* against the skin round it, want +%.0f" % (
                k, v, PAINT_RULES["scar"])
    return out


def _stroke_points(s, offsets=False, n=60):
    """Points across a body stroke's middle third (and, with `offsets`,
    each point's signed distance off its line), in the stroke's own frame
    -- on the trunk's plane for 'front'/'back', on the limb's cylinder."""
    offs = np.linspace(-0.014, 0.014, 57)
    ts = np.linspace(0.35, 0.65, n)
    at = s.get("at")
    if at in ("front", "back"):
        a, b = np.asarray(s["a"], float), np.asarray(s["b"], float)
        dv = (b - a) / np.linalg.norm(b - a); nv = np.array([-dv[1], dv[0]])
        T, O = np.meshgrid(ts, offs)
        xz = a[None, :] + np.outer(T.ravel() * np.linalg.norm(b - a), dv) + np.outer(O.ravel(), nv)
        yv = -0.10 if at == "front" else 0.10
        P = np.stack([xz[:, 0], np.full(len(xz), yv), xz[:, 1]], 1)
        return O.ravel() if offsets else P
    from .anatomy import Jp
    limb, lr = at.rsplit("_", 1)
    sg = 1.0 if lr == "l" else -1.0
    m = np.array([sg, 1.0, 1.0])
    p0 = np.array(Jp({"upperarm": "upperarm_l", "lowerarm": "lowerarm_l"}[limb])) * m
    p1 = np.array(Jp({"upperarm": "lowerarm_l", "lowerarm": "hand_l"}[limb])) * m
    d = p1 - p0; L = np.linalg.norm(d); d /= L
    f = np.array([0.0, -1.0, 0.0]); f = f - d * (f @ d); f /= np.linalg.norm(f); sd = np.cross(d, f)
    outward = np.arctan2(-sg, 0.0)
    centre = {"outer": outward, "inner": outward + np.pi, "flexor": 0.0, "back": np.pi}[s.get("side", "outer")]
    r = 0.045
    t0, t1 = s["t"]
    T, O = np.meshgrid(ts, offs)
    tt = t0 + (t1 - t0) * T.ravel()
    if s.get("across"):
        # the line runs from (t0, -22 mm of arc) to (t1, +22): offsets are
        # taken perpendicular to it in the unrolled plane
        a = np.array([t0 * L, -0.022]); b = np.array([t1 * L, 0.022])
        dv = (b - a) / np.linalg.norm(b - a); nv = np.array([-dv[1], dv[0]])
        uv = a[None, :] + np.outer(T.ravel() * np.linalg.norm(b - a), dv) + np.outer(O.ravel(), nv)
        tt, arc = uv[:, 0] / L, uv[:, 1]
    else:
        arc = O.ravel()
    ang = centre + arc / r
    P = p0[None, :] + np.outer(tt * L, d) + r * (np.outer(np.cos(ang), f) + np.outer(np.sin(ang), sd))
    return O.ravel() if offsets else P
