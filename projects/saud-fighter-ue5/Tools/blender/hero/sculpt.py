"""The face as a sculpt: a displacement field over the skull surface.
Each feature is a Gaussian -- a bump or a hollow with a size in each axis
-- and the field is the sum, applied along the vertex normal. A ridge is a
row of them. Because the field is smooth, a brow grows out of the forehead
and a socket sinks into it; nothing sits on the skin as a separate thing."""
import numpy as np          # no Blender here: this module is the face's
                            # layout, and the preview harness reads it too

# The eye line. It is halfway between the chin at 1.572 and the crown at
# 1.796, which is where a human's is; everything about the eye -- the
# socket, the lids, the ball in assembly.eyeballs(), the lash line and the
# lid crease in hero.face -- is measured from here, so it moves as one.
EYE_Z = 1.677

# The rest of the layout, in one place, because four modules key off it: the
# sculpt below, the globes and the hair cut in hero.assembly, and every
# region in hero.face. Measured against adult male proportions -- hairline
# to chin 185 mm, glabella to chin 120, pupil to chin 105, subnasale to chin
# 72, stomion to chin 48 -- with the chin fixed at 1.572 by the head loft.
BROW_Z   = 1.6990      # the ridge, 22 mm above the pupil
NOSE_Z   = 1.6330      # the nostrils
NOSE_TIP = 1.6450
MOUTH_Z  = 1.6202      # the line between the lips
CHIN_Z   = 1.5720
EAR_Z    = 1.6640      # centre; the ear runs brow to nose base
EAR_Y    = 0.026       # behind the mandibular ramus, not at mid-depth
# 6 mm off the skull's side at (EAR_Y, EAR_Z): was 0.0785 on the old skull,
# which was 11 mm wider there; assembly.ear asserts the gap, so a skull that
# moves again takes its ears with it or fails.
EAR_X    = 0.0722
# z of the hairline at the brow (y -0.09) and at the nape (y +0.09). It was
# (1.738, 1.695), which left a 34 mm forehead where the other two thirds of
# the face were 62 and 59 mm, and a correspondingly swollen cranium.
HAIRLINE = (1.7600, 1.7160)

# (x, y, z, sx, sy, sz, amplitude in metres). y is measured off the skull
# surface by the caller, so features are given at the surface (y=0 here
# means "at the skin"). Mirrored features are listed once with x>0.
FACE = [
    # Laid out to the measured proportions of an adult male head, which the
    # old table was not: the chin is at 1.572 and the crown at 1.796, so the
    # eye line belongs at the halfway mark, 1.677, and it was at 1.666 -- the
    # eyes sat low in an over-tall cranium, which is the single thing that
    # makes a head read as a puppet. Glabella to chin 120 mm, pupil to chin
    # 105 mm, subnasale to chin 72 mm, stomion to chin 48 mm.
    # brow ridge and the glabella between the brows
    ("brow",      0.030, 1.6990, 0.028, 0.016, 0.0080, +0.0048, True),
    ("glabella",  0.000, 1.6900, 0.011, 0.014, 0.011,  +0.0026, False),
    ("temple",    0.068, 1.7080, 0.014, 0.024, 0.024,  -0.0030, True),
    # eyes: the socket hollow; the lids are covers, below
    ("socket",    0.031, 1.6770, 0.020, 0.018, 0.014,  -0.0015, True),
    # nose: a ridge from the glabella to the tip, the tip, the columella
    # under it, the alae, the crease behind them, the nostrils. The four
    # ridge Gaussians are 12 mm apart with a 10 mm sigma, so each gives its
    # neighbours half its amplitude and they pile up: the old amplitudes
    # summed to 35 mm on the midline and measured 27 mm of projection on the
    # built mesh, against 19-22 mm on a real male nose.
    # Narrowed 2026-09-26 ("fix nose shape"): every width was about double a
    # real man's. Measured off the field, the bridge was 21 mm across at
    # half height (a real dorsum is 10-15), the tip lobule 38 (about 20),
    # the alae spread 69 mm (the alar base is 32-36), and two 8 mm-deep
    # nostril hollows 16 mm apart cut one dark slot across the front with a
    # notch under the tip in profile. Now: a 6 mm-sigma dorsum, a 7 mm tip
    # lobule, the alae in at 13.5 mm with a crease behind each, a columella
    # carrying the tip down to the lip, and nostrils a small hollow under
    # the tip -- their dark is paint (hero.face), not a hole. check_profile
    # holds all of it.
    # The radix -- the dip between the brow and the bridge. Without it the
    # midline runs in one unbroken convex ramp from the hairline to the nose
    # tip, which is the shop-dummy profile and the most legible "not a
    # person" line on the whole head. It has to be a local MINIMUM, so it is
    # a hollow cut into the ridge, not a smaller bump.
    ("radix",     0.000, 1.6870, 0.013, 0.014, 0.0078, -0.0060, False),
    ("bridge1",   0.000, 1.6810, 0.0055, 0.016, 0.010, +0.0046, False),
    ("bridge2",   0.000, 1.6690, 0.0058, 0.016, 0.010, +0.0072, False),
    ("bridge3",   0.000, 1.6570, 0.0062, 0.016, 0.010, +0.0094, False),
    ("tip",       0.000, 1.6455, 0.0070, 0.016, 0.0078, +0.0150, False),
    ("ala",       0.0135, 1.6385, 0.0060, 0.012, 0.0066, +0.0060, True),
    ("nostril",   0.0070, 1.6345, 0.0030, 0.008, 0.0026, -0.0026, True),
    ("columella", 0.000, 1.6385, 0.0042, 0.012, 0.0045, +0.0030, False),
    ("alar_crease", 0.0205, 1.6395, 0.0030, 0.012, 0.0080, -0.0018, True),
    # cheeks. A young man carries fat over the cheekbone, not a hollow under
    # it: the hollow is what read as middle-aged, so it is halved and a
    # malar pad put in above it.
    ("cheekbone", 0.0465, 1.6560, 0.022, 0.020, 0.016,  +0.0062, True),
    ("cheek_fat", 0.0400, 1.6400, 0.025, 0.020, 0.017,  +0.0036, True),
    ("hollow",    0.0428, 1.6260, 0.017, 0.020, 0.014,  -0.0014, True),
    ("masseter",  0.0557, 1.6040, 0.016, 0.018, 0.016,  +0.0032, True),
    # mouth
    ("lip_upper", 0.000, 1.6265, 0.024, 0.012, 0.0055, +0.0052, False),
    ("lip_lower", 0.000, 1.6140, 0.020, 0.012, 0.0065, +0.0068, False),
    ("mouthline", 0.000, 1.6202, 0.022, 0.012, 0.0022, -0.0045, False),
    ("philtrum",  0.000, 1.6340, 0.0038, 0.010, 0.008, -0.0020, False),
    ("corner",    0.025, 1.6200, 0.005, 0.010, 0.005,  -0.0018, True),
    ("mentolab",  0.000, 1.6020, 0.014, 0.012, 0.005,  -0.0028, False),
    ("chin",      0.000, 1.5860, 0.019, 0.016, 0.014,  +0.0062, False),
    # jaw: a ridge from the chin back to the angle under the ear. The side
    # features' x (temple to jaw3) went in 2026-09-26 with the narrower face
    # of anatomy.HEAD_PROFILE, each by the new half-width over the old at
    # its own height, so each sits where it sat on the face.
    ("jaw1",      0.032, 1.5880, 0.014, 0.016, 0.008,  +0.0030, True),
    ("jaw2",      0.0507, 1.5960, 0.014, 0.018, 0.009,  +0.0036, True),
    ("jaw3",      0.0626, 1.6100, 0.013, 0.020, 0.012,  +0.0038, True),
    # ---- OPTIONAL (2026-09-28, "make Saud more aggressive", the Unreal
    # men): forms the shared rows cannot make by scaling, at factor 0 on
    # every man whose pipeline.FACES entry does not name them (factor()).
    # Narrower sigmas than the cheekbone (22/16 mm) and the chin (19/14),
    # which is why they are rows of their own and not factors on those.
    # the brow ridge pulled down over the upper lid -- the seinen scowl's
    # overhang (the eye sits under it, in the brow's shadow)
    ("brow_low",  0.0270, 1.6940, 0.019, 0.014, 0.0058, +0.0050, True),
    # the corrugator, bunched at the inner end of the brow
    ("corrugator", 0.0145, 1.6950, 0.0065, 0.010, 0.0050, +0.0018, True),
    # the cheekbone's lower edge, a hard edge over a lean cheek
    ("zygoma",    0.0505, 1.6520, 0.013, 0.014, 0.0070, +0.0028, True),
    # the jaw's angle, marked
    ("gonion",    0.0600, 1.5985, 0.009, 0.014, 0.0070, +0.0022, True),
    # two mental tubercles: a square chin
    ("chin_sq",   0.0115, 1.5850, 0.008, 0.012, 0.0090, +0.0016, True),
]
OPTIONAL = {"brow_low", "corrugator", "zygoma", "gonion", "chin_sq"}
FEATURES = {r[0] for r in FACE}

def factor(scale, name):
    """A man's factor on one row: what his FACES entry says, else 1.0 --
    and 0.0 for an OPTIONAL row he does not name, so the forms added for
    one man's face are not on everyone else's."""
    return (scale or {}).get(name, 0.0 if name in OPTIONAL else 1.0)

def with_nose(scale=None, noses=None):
    """One man's FACES factors and his pipeline.NOSES entry, {feature:
    dict(dx=, dz=, k=)}, as the (scale, shift) sculpt_face and
    check_profile take: k multiplies the feature's factor, dx / dz move it
    (metres; +x is his left). Unknown features or keys raise."""
    sc = dict(scale or {}); shift = {}
    for name, n in (noses or {}).items():
        if name not in FEATURES:
            raise KeyError("no such face feature for a nose: %r" % name)
        bad = set(n) - {"dx", "dz", "k"}
        if bad:
            raise KeyError("no such nose number %s on %r (dx, dz, k)" % (sorted(bad), name))
        if "k" in n:
            sc[name] = factor(sc, name) * n["k"]
        if n.get("dx", 0.0) or n.get("dz", 0.0):
            shift[name] = (float(n.get("dx", 0.0)), float(n.get("dz", 0.0)))
    return sc, shift

def _rows(table=None, scale=None, shift=None):
    """The table as the rows a man's face is built from: (x, z, sx, sy, sz,
    amp) each, his factors on the amplitudes, a mirrored feature listed
    twice -- and a feature with a shift moved off the midline, a mirrored
    one as two rows at +x+dx and -x+dx (a knocked nose is not symmetric)."""
    shift = shift or {}
    out = []
    for name, x, z, sx, sy, sz, amp, mirror in (table or FACE):
        a = amp * factor(scale, name)
        dx, dz = shift.get(name, (0.0, 0.0))
        for sgn in ((1, -1) if mirror else (1,)):
            out.append((name, sgn * x + dx, z + dz, sx, sy, sz, a))
    return out

# ---- the eye ------------------------------------------------------------
# The globe: 24 mm across, its centre EYE_SEAT behind the bare skull line at
# (EYE_X, EYE_Z), so its cornea is on that line (it was 2 mm behind it, set
# for a skin the globe had to poke through; with the lids draped round it,
# 2 mm deeper only sank the whole eye into the face). assembly.eyeballs
# builds it here and drape_eyes() fits the lids to it, so both read these.
EYE_X = 0.031
EYE_R = 0.0120
EYE_SEAT = 0.0120

# The palpebral fissure -- the opening between the lids -- measured to an
# adult male's (2026-09-26, "fix the eyes shape"): inner corners 32 mm apart
# and outer corners 89 mm, so 28.5 mm wide; 9.6 mm tall at the pupil, the
# upper lid resting 1.2 mm over the top of the iris and the lower at its
# bottom edge; the outer corner 2 mm above the inner (a 4 degree canthal
# tilt); the upper lid highest just inside the pupil, the lower lowest just
# outside it, which is what makes it an almond and not a lens.
X_MED, X_LAT = 0.0160, 0.0445            # the inner and outer canthus, |x|
Z_MED, Z_LAT = EYE_Z - 0.0008, EYE_Z + 0.0012
UP_AT_PUPIL, DN_AT_PUPIL = 0.0044, 0.0052
UP_PEAK, DN_PEAK = 0.42, 0.58            # along the fissure, inner 0 to outer 1
UP_ROUND, DN_ROUND = 0.90, 1.00          # under 1: fuller in the middle

def _arc(u, peak, k):
    a = np.log(0.5) / np.log(peak)       # u ** a is a half at the peak
    return np.sin(np.pi * np.clip(u, 0.0, 1.0) ** a) ** k

_UP_P = (EYE_X - X_MED) / (X_LAT - X_MED)

def aperture(ax):
    """The lid margins at |x| = ax: (z of the upper, z of the lower). They
    meet at each canthus and are closed (equal) outside the fissure."""
    ax = np.asarray(ax, dtype=float)
    u = np.clip((ax - X_MED) / (X_LAT - X_MED), 0.0, 1.0)
    base = Z_MED + (Z_LAT - Z_MED) * u
    bp = Z_MED + (Z_LAT - Z_MED) * _UP_P
    hu = (EYE_Z + UP_AT_PUPIL - bp) / _arc(_UP_P, UP_PEAK, UP_ROUND)
    hd = (bp - (EYE_Z - DN_AT_PUPIL)) / _arc(_UP_P, DN_PEAK, DN_ROUND)
    return base + hu * _arc(u, UP_PEAK, UP_ROUND), base - hd * _arc(u, DN_PEAK, DN_ROUND)

# How the lids are draped (drape_eyes): the pocket inside the fissure sits
# POCKET_CLEAR behind the globe, so the white shows from corner to corner;
# the lids lie on the globe LID_UPPER / LID_LOWER thick at the margin, as a
# lid does, and go back to the face's own surface by LID_REACH above and
# below; nothing is taken deeper than POCKET_CAP behind the corneal pole
# (inner corner, outer corner), which leaves a corner of skin at each end --
# the lateral canthal angle, and the caruncle painted pink in hero.face.
POCKET_CLEAR = 0.0008
LID_UPPER, LID_LOWER = 0.0018, 0.0015
POCKET_CAP = (0.0050, 0.0090)
# Past the globe's own edge a lid does not fall back to its equator: it lies
# on the orbit's fat, a broader shell than the ball. Draped on the globe
# alone the lids above and beside it were pulled 10-15 mm back into a box
# with walls (the first preview). The shell's half-width and half-height.
SHELL = (0.0170, 0.0190)
# The drape's reach: full inside this ellipse about the fissure's centre
# (half-width toward the ear, half-width toward the nose, half-height above,
# half-height below), fading to nothing by DRAPE_FADE times it -- an
# ellipse, not a rectangle, so it has no corners. Toward the nose it is
# full to the inner corner and fades out by the bridge (x = 5 mm): the
# side of the nose, sloping from the bridge down to the canthus as a real
# one does -- faded over 4 mm it was a cliff.
DRAPE_ZONE = (0.0155, 0.0142, 0.0098, 0.0095)
DRAPE_FADE = (1.75, 1.75)

def globe_centre(surface_y, s):
    return np.array([EYE_X * s, surface_y(EYE_X * s, EYE_Z) + EYE_SEAT, EYE_Z])

def drape_target(x, z, gy):
    """Where the skin at (x, z) belongs, as y, and how strongly (0..1), for
    the eye whose globe centre is at depth gy. Pure numpy, so the checks
    and the preview read the same thing the build does."""
    ax = np.abs(x)
    dx = ax - EYE_X; dz = z - EYE_Z
    front = gy - np.sqrt(np.clip(EYE_R ** 2 - dx * dx - dz * dz, 0.0, None))    # the globe, or its equator
    apex = gy - EYE_R
    u = np.clip((ax - X_MED) / (X_LAT - X_MED), 0.0, 1.0)
    cap = apex + POCKET_CAP[0] + (POCKET_CAP[1] - POCKET_CAP[0]) * u
    up, dn = aperture(ax)
    inside = np.minimum(z - dn, up - z)                  # > 0 in the fissure
    step = lambda t: (lambda c: c * c * (3.0 - 2.0 * c))(np.clip(t, 0.0, 1.0))
    over = z > 0.5 * (up + dn)
    lid_t = np.where(over, LID_UPPER, LID_LOWER)
    # The shell is an ellipsoid near the pole and carries on straight past
    # q = 0.64 at the slope it had there, and meets the cap through a soft
    # minimum: an ellipsoid's own edge is vertical, and where it met the
    # cap it left a crease down the outside of every eye.
    q = (dx / SHELL[0]) ** 2 + (dz / SHELL[1]) ** 2
    sq = np.sqrt(np.clip(1.0 - q, 0.36, None))
    sink = np.where(q < 0.64, 1.0 - sq, 0.4 + (q - 0.64) / 1.2)
    shell = gy - (EYE_R + lid_t) + (EYE_R + lid_t) * sink
    def softmin(a, b, k=0.0012):
        m = np.minimum(a, b)
        return m - k * np.log(np.exp((m - a) / k) + np.exp((m - b) / k))
    pocket = np.minimum(front + POCKET_CLEAR, cap)
    lid = softmin(shell, cap)
    # the margin: 0.6 mm, and none at all once the lids have met -- at half
    # strength along the closed line it ran on past each corner as a groove
    k = step(inside / 0.0006 + 0.5) * step((up - dn) / 0.0012)
    target = lid + (pocket - lid) * k
    cx = 0.5 * (X_MED + X_LAT)
    med = ax < cx
    hx = np.where(med, DRAPE_ZONE[1], DRAPE_ZONE[0])
    hz = np.where(z > EYE_Z, DRAPE_ZONE[2], DRAPE_ZONE[3])
    fade = np.where(med, DRAPE_FADE[1], DRAPE_FADE[0])
    rho = np.sqrt(((ax - cx) / hx) ** 2 + (dz / hz) ** 2)
    w = 1.0 - step((rho - 1.0) / (fade - 1.0))
    w = np.maximum(w, (inside > 0).astype(float))        # the fissure is always cut
    return target, np.clip(w, 0.0, 1.0), inside

def near_margin(ax, z, band=0.0012):
    """Within `band` of either lid margin, corner to corner: the part of the
    eye that needs its density kept -- the edge of a lid. Not the inside of
    the fissure, which is the pocket behind the globe and never seen."""
    if not (X_MED - band < ax < X_LAT + band):
        return False
    up, dn = aperture(np.array([ax]))
    return bool(min(abs(z - up[0]), abs(z - dn[0])) < band)

def drape_eyes(body, surface_y):
    """Fit the skin round each globe: the fissure opened behind it and the
    lids laid on it. After sculpt_face and its smoothing, on the mesh that
    assembly.subdivide_eyes made dense enough to carry a lid margin."""
    me = body.data
    n = len(me.vertices)
    P = np.empty(n * 3); me.vertices.foreach_get("co", P); P = P.reshape(n, 3)
    N = np.empty(n * 3); me.vertices.foreach_get("normal", N); N = N.reshape(n, 3)
    moved = 0
    for s in (1, -1):
        gy = globe_centre(surface_y, s)[1]
        # every vertex of the zone, whichever way it faces or however far
        # back it is: one left out while its neighbours move is a spike, and
        # asking for "in front of the globe's centre" cut a 4 mm step down
        # the side of the head where the surface passes that depth. The
        # front half of the head is the only limit (the zone's weight is
        # nothing long before the back of the skull).
        sel = ((P[:, 0] * s > 0.0) & (P[:, 0] * s < X_LAT + 0.016)
               & (np.abs(P[:, 2] - EYE_Z) < 0.018) & (P[:, 1] < 0.0))
        idx = np.nonzero(sel)[0]
        t, w, _ = drape_target(P[idx, 0], P[idx, 2], gy)
        P[idx, 1] += w * (t - P[idx, 1])
        moved += int((w > 0.01).sum())
    me.vertices.foreach_set("co", P.reshape(-1))
    me.update()
    return moved

# One man's lids (2026-09-28, the Unreal men): pipeline.EYES, set through
# set_eye by pipeline.apply_man before anything is built or painted --
# aperture(), drape_eyes, near_margin / relax_eyes, check_eye_open and the
# lash paint all read these module numbers at call time, so one call moves
# them together. One process per man (build_fighters), like face.set_hair;
# a suite that builds several heads in one process resets with set_eye().
# HOODED: the lid set low on purpose (Saud's scowl), which check_eye_shape
# holds to its own rules instead of the open eye's.
HOODED = False
_EYE_DEFAULT = dict(UP_AT_PUPIL=UP_AT_PUPIL, DN_AT_PUPIL=DN_AT_PUPIL, UP_ROUND=UP_ROUND, UP_PEAK=UP_PEAK)
PUPIL_R = 0.00205        # finish.PUPIL_R: the painted pupil's radius

def set_eye(hooded=False, **kw):
    """Reset the lids to the shared numbers, then apply one man's: any of
    UP_AT_PUPIL, DN_AT_PUPIL, UP_ROUND, UP_PEAK. Unknown keys raise."""
    global HOODED
    bad = set(kw) - set(_EYE_DEFAULT)
    if bad:
        raise KeyError("no such eye number: %s (%s)" % (sorted(bad), ", ".join(sorted(_EYE_DEFAULT))))
    g = globals()
    g.update(_EYE_DEFAULT); g.update({k: float(v) for k, v in kw.items()})
    HOODED = bool(hooded)

def check_eye_shape(ap=None, hooded=None):
    """The fissure as a man's (numpy): 26-31 mm wide, 8.5-11 mm tall at the
    pupil, the upper lid over 0.5-2 mm of the iris (under it he stares, over
    it he is asleep), the lower within 0.8 mm of the iris's bottom, the outer
    corner 1-4 mm above the inner, the upper lid's crest inside the pupil
    and the lower's low point outside it. Returns the numbers.

    A HOODED eye (set_eye(hooded=True), 2026-09-28) is held instead to: the
    upper lid over at least 2 mm of the iris ('not hooded' under it), at
    least 1 mm of iris still showing over the pupil (the lid is never on
    the pupil: still open), and 8.0-11 mm tall. `hooded` defaults to the
    module's HOODED; the other rules are everyone's."""
    ap = ap or aperture
    hooded = HOODED if hooded is None else bool(hooded)
    xs = np.linspace(X_MED - 0.004, X_LAT + 0.004, 2001)
    up, dn = ap(xs)
    open_ = up - dn > 1e-5
    width = float(xs[open_].max() - xs[open_].min())
    u_p, d_p = [float(v) for v in ap(np.array([EYE_X]))]
    iris = 0.00565
    cover = (EYE_Z + iris) - u_p
    under = (EYE_Z - iris) - d_p
    lo, hi = xs[open_].min(), xs[open_].max()
    ends = ap(np.array([lo, hi]))
    tilt = float(ends[0][1] - ends[0][0])
    crest = float(xs[np.argmax(up)]); low = float(xs[np.argmin(dn)])
    clear = u_p - (EYE_Z + PUPIL_R)              # iris showing over the pupil
    assert 0.026 <= width <= 0.031, "eye fissure %.1f mm wide, want 26-31" % (width * 1000)
    if hooded:
        assert cover >= 0.002, "not hooded: the upper lid over %.1f mm of the iris, want 2 or more" % (cover * 1000)
        assert clear >= 0.001, "the lid on the pupil: %.1f mm of iris over it, want 1 or more" % (clear * 1000)
    else:
        assert 0.0005 <= cover <= 0.002, "upper lid over %.1f mm of the iris, want 0.5-2 (staring or asleep)" % (cover * 1000)
    assert abs(under) <= 0.0008, "lower lid %.1f mm off the iris's bottom, want within 0.8" % (under * 1000)
    tall = 0.0080 if hooded else 0.0085
    assert tall <= u_p - d_p <= 0.011, "eye fissure %.1f mm tall, want %.1f-11" % ((u_p - d_p) * 1000, tall * 1000)
    assert 0.001 <= tilt <= 0.004, "canthal tilt %.1f mm, want the outer corner 1-4 above the inner" % (tilt * 1000)
    assert crest < EYE_X < low, "no almond: upper crest at %.1f, lower low at %.1f mm, pupil %.1f" % (crest * 1000, low * 1000, EYE_X * 1000)
    return dict(width=width, height=u_p - d_p, cover=cover, under=under, tilt=tilt, clear=clear)

def sculpt_face(body, surface_y, z_min=1.556, scale=None, shift=None):
    """Displace the head's vertices by the feature field.

    `scale` is {feature name: factor} on the amplitudes -- how one man's
    face differs from another's on the same skull: a heavier brow, a wider
    jaw, a smaller chin. The layout (where the features ARE) is shared; it
    is the eight-heads layout every face here is drawn to, and the browser
    build draws every fighter's head from the one skull too. The one
    exception is `shift`, {feature: (dx, dz)} (with_nose), a man's broken
    nose knocked off the midline (2026-09-28, the Unreal men).
    """
    me = body.data
    n = len(me.vertices)
    P = np.empty(n * 3); me.vertices.foreach_get("co", P); P = P.reshape(n, 3)
    N = np.empty(n * 3); me.vertices.foreach_get("normal", N); N = N.reshape(n, 3)
    head = (P[:, 2] > z_min) & (P[:, 1] < 0.06)
    idx = np.nonzero(head)[0]
    Ph = P[idx]
    D = np.zeros(len(idx))
    def add(x, z, sx, sy, sz, amp):
        y = surface_y(x, z) 
        d = ((Ph[:, 0] - x) / sx) ** 2 + ((Ph[:, 1] - y) / sy) ** 2 + ((Ph[:, 2] - z) / sz) ** 2
        return amp * np.exp(-0.5 * d)
    for name, x, z, sx, sy, sz, amp in _rows(FACE, scale, shift):
        if amp != 0.0:                  # an OPTIONAL row he does not name
            D += add(x, z, sx, sy, sz, amp)
    # Apply along the normal, then only where the face is (front hemisphere
    # of the head): features must not leak onto the back of the skull.
    front = np.clip((-N[idx, 1] + 0.55) / 0.9, 0.0, 1.0)
    P[idx] += N[idx] * (D * front)[:, None]
    me.vertices.foreach_set("co", P.reshape(-1))
    me.update()
    check_profile(scale, shift=shift)
    return float(np.abs(D).max()), int((np.abs(D) > 0.0005).sum())

# The features that make the nose, for check_profile's widths: the rest of
# the face (cheeks, lip) rises off the midline too and would read as nose.
NOSE_PARTS = ("radix", "bridge1", "bridge2", "bridge3", "tip", "columella",
              "ala", "alar_crease", "nostril")

def _field(x, z, scale=None, table=None, only=None, shift=None):
    """The displacement the table would build at (x, z), x and z arrays."""
    d = np.zeros(np.broadcast(x, z).shape)
    for name, fx, fz, sx, sy, sz, amp in _rows(table, scale, shift):
        if only and name not in only: continue
        if amp != 0.0:
            d = d + amp * np.exp(-0.5 * (((x - fx) / sx) ** 2 + ((z - fz) / sz) ** 2))
    return d

def midline(lo=1.590, hi=1.740, step=0.001, scale=None, table=None, shift=None):
    """The face's profile down the midline, as the field would build it."""
    zs = np.arange(lo, hi, step)
    return zs, _field(0.0, zs, scale, table, shift=shift)

def _nose_widths(scale=None, table=None, shift=None, xs=None):
    """The nose's widths about its own crest, both sides (2026-09-28): the
    full width at half the crest's height across the bridge (24 mm above
    the tip) and across the tip, the alae's spread where the field is over
    1 mm, and how far the crest is off the midline. Measured from the
    midline out one side and doubled, as it was, the brawler's broken nose
    (2.75 mm off) read 26 mm across the tip, over the 24 allowed, when it
    is 18.75 about its own crest."""
    xs = np.arange(-0.040, 0.0400001, 0.00025) if xs is None else xs
    def across(z):
        return _field(xs, z, scale, table, NOSE_PARTS, shift)
    def width(z):
        g = across(z); i = int(np.argmax(g)); half = g[i] / 2.0
        r = i
        while r < len(g) - 1 and g[r] >= half: r += 1
        l = i
        while l > 0 and g[l] >= half: l -= 1
        return float(xs[r] - xs[l]), float(xs[i])
    bridge, bridge_x = width(NOSE_TIP + 0.024)
    tip, tip_x = width(NOSE_TIP)
    g = across(NOSE_TIP - 0.007); on = xs[g > 0.001]
    alae = float(on.max() - on.min()) if len(on) else 0.0
    return dict(bridge=bridge, tip=tip, alae=alae, bridge_x=bridge_x, tip_x=tip_x,
                deviation=max(abs(bridge_x), abs(tip_x)))

def dorsum_hump(scale=None, table=None, shift=None):
    """How far the nose's crest stands over the chord from the nasion to
    the tip, and where (for telling a broken, an aquiline and a flattened
    nose apart, 2026-09-28): the crest is the field's highest point across
    x at each height, wherever the nose has been knocked to. Returns
    (height m, z)."""
    zs = np.arange(1.630, 1.700, 0.0005); xs = np.arange(-0.010, 0.010, 0.00025)
    crest = np.array([_field(xs, z, scale, table, shift=shift).max() for z in zs])
    it = int(np.argmax(crest)); ztip = zs[it]
    win = (zs > ztip + 0.005) & (zs < BROW_Z)
    zw, cw = zs[win], crest[win]
    inas = int(np.argmin(cw)); zn, cn = zw[inas], cw[inas]
    seg = (zs >= ztip) & (zs <= zn)
    chord = crest[it] + (cn - crest[it]) * (zs[seg] - ztip) / (zn - ztip)
    k = int(np.argmax(crest[seg] - chord))
    return float((crest[seg] - chord)[k]), float(zs[seg][k])

NOSE_MID = NOSE_TIP + 0.0225   # check_nose's mid-bridge: halfway from the tip to the nasion

def check_nose(scale=None, shift=None, looks=None, assert_=True):
    """A man's nose reads as what his NOSES entry says it is (2026-09-28;
    `looks` is his pipeline.NOSE_LOOKS entry): dict(looks='broken' |
    'aquiline' | 'flattened', and any of deviation=, hump=, dorsum= as
    (lo, hi), metres, None for an open end) -- the crest's distance off
    the midline (_nose_widths), the dorsal hump over the nasion-tip chord
    (dorsum_hump) and the dorsum's height at mid-bridge (NOSE_MID, the
    crest across x: a flattened nose is pushed in there). The shared
    nose: 0 off, a 1.61 mm hump, the dorsum 15.7 mm. A man with no entry
    is not held. Returns dict(deviation, hump, dorsum)."""
    xs = np.arange(-0.010, 0.010, 0.00025)
    out = dict(deviation=_nose_widths(scale, shift=shift)["deviation"], hump=dorsum_hump(scale, shift=shift)[0],
               dorsum=float(_field(xs, NOSE_MID, scale, shift=shift).max()))
    if not assert_ or not looks:
        return out
    bad = set(looks) - {"looks", "deviation", "hump", "dorsum"}
    if bad:
        raise KeyError("no such nose look: %s (looks, deviation, hump, dorsum)" % sorted(bad))
    what = dict(deviation="the crest %.2f mm off the midline", hump="a %.2f mm dorsal hump",
                dorsum="the dorsum %.2f mm high at mid-bridge")
    for key in ("deviation", "hump", "dorsum"):
        if key not in looks:
            continue
        lo, hi = looks[key]; v = out[key]
        ok = (lo is None or v >= lo) and (hi is None or v <= hi)
        want = ("%.1f-%.1f" % (lo * 1000, hi * 1000) if lo is not None and hi is not None else
                "%.1f or more" % (lo * 1000) if lo is not None else "%.1f or less" % (hi * 1000))
        assert ok, ("not %s: " + what[key] + ", want %s") % (looks["looks"], v * 1000, want)
    return out

def check_profile(scale=None, table=None, shift=None):
    """What about the nose a render will not tell you until it is too late,
    and all of which went wrong before:

    the nose must not run away (the four ridge Gaussians sit 12 mm apart
    with a 10 mm sigma, so each gives its neighbours half its amplitude and
    the sum once reached 35 mm, which measured 27 mm of projection against
    19-22 on a real male nose); there must be a nasion -- a local minimum
    between the glabella and the bridge. Without one the midline is a single
    convex ramp from the hairline to the tip.

    And, since 2026-09-26, it must be a man's width, measured on the nose's
    own features: the bridge no more than 17 mm across at half its height
    (a dorsum is 10-15; it was 21), the tip lobule no more than 24 (about
    20; it was 38), the alae inside 48 mm (the alar base is 32-36; the
    field spread 69), and no slot -- across the nostril row, no hollow
    deeper than 2.5 mm between the midline and the ala (it was 4.1, the
    dark bar across every face).

    Since 2026-09-28 a man's nose may be knocked off the midline (`shift`,
    pipeline.NOSES: the brawler's is broken), so the widths are measured
    both sides of the nose's own crest (_nose_widths), the slot out both
    ways from the crest across the nostril row (one side only, a nose
    knocked to his left hid a 3 mm slot on its right), and the crest may
    stand at most 4 mm off the midline. The peak and the nasion are still
    the midline's.
    """
    # the deviation first: a nose off the midline also moves the midline's
    # peak, and the rule that names what is wrong is this one
    w = _nose_widths(scale, table, shift)
    assert w["deviation"] <= 0.004, "nose deviation: its crest %.1f mm off the midline, want <= 4" % (w["deviation"] * 1000)
    zs, d = midline(scale=scale, table=table, shift=shift)
    peak = float(d.max()); at = float(zs[int(d.argmax())])
    assert 0.020 <= peak <= 0.030, "nose field peak %.1f mm, want 20-30" % (peak * 1000)
    assert abs(at - NOSE_TIP) < 0.008, "nose peaks at %.3f, not at the tip %.3f" % (at, NOSE_TIP)
    win = (zs > NOSE_TIP + 0.015) & (zs < BROW_Z + 0.012)
    zw, dw = zs[win], d[win]
    turns = np.nonzero(np.diff(np.sign(np.diff(dw))))[0] + 1
    assert len(turns) >= 2, "no nasion: the midline from brow to nose tip has no dip"
    nas = float(zw[turns[0]])           # the dip, then the glabella above it
    assert dw[turns[0]] < dw[turns[1]], "the turn below the glabella is a bump, not a dip"
    # the slot across the nostril row, out both ways from the nose's own
    # crest there (the columella; the midline on a straight nose)
    zr = NOSE_Z + 0.0015
    xc = np.arange(-32, 33) * 0.00025
    x0 = float(xc[int(np.argmax(_field(xc, zr, scale, table, NOSE_PARTS, shift)))])
    xs = np.arange(0.0, 0.0165001, 0.0005)
    def slot_of(sgn):
        f = _field(x0 + sgn * xs, zr, scale, table, shift=shift)
        return max(float(f[i:].max() - f[i]) for i in range(len(f)))
    slot = max(slot_of(1), slot_of(-1))
    assert w["bridge"] <= 0.017, "bridge %.0f mm wide at half height, want <= 17" % (w["bridge"] * 1000)
    assert w["tip"] <= 0.024, "tip lobule %.0f mm wide, want <= 24" % (w["tip"] * 1000)
    assert w["alae"] <= 0.048, "alae spread %.0f mm, want <= 48" % (w["alae"] * 1000)
    assert slot <= 0.0025, "nostril slot %.1f mm deep across the front, want <= 2.5" % (slot * 1000)
    return peak, at, nas

def bite():
    """check_profile broken once per rule, numpy only (2026-09-26; the
    knocked nose 2026-09-28): each must be refused, with its own word.
    Returns (caught, total)."""
    def swap(table, name, **kw):
        keys = ("x", "z", "sx", "sy", "sz", "amp")
        out = []
        for r in table:
            if r[0] == name:
                v = dict(zip(keys, r[1:7]))
                v.update(kw)
                r = (name,) + tuple(v[k] for k in keys) + (r[7],)
            out.append(r)
        return out
    bites = [
        ("runaway nose", swap(FACE, "tip", amp=0.0250), "peak"),
        ("no nasion",    swap(FACE, "radix", amp=0.0), "nasion"),
        ("wide bridge",  swap(swap(swap(FACE, "bridge1", sx=0.0080), "bridge2", sx=0.0085),
                              "bridge3", sx=0.0095), "bridge"),
        ("bulb tip",     swap(FACE, "tip", sx=0.0125), "tip lobule"),
        ("flared alae",  swap(FACE, "ala", x=0.016, sx=0.0098), "alae"),
        ("nostril slot", swap(FACE, "nostril", x=0.0078, sx=0.0045, sz=0.0045, amp=-0.0080), "slot"),
        # 2026-09-28: the plain nose knocked 6 mm off the midline (the
        # bridge, the tip and the columella) -- more than a broken nose
        ("knocked 6 mm", [(r[0], r[1] + (0.006 if r[0] in ("bridge2", "bridge3", "tip", "columella") else 0.0))
                          + tuple(r[2:]) for r in FACE], "deviation"),
    ]
    caught = 0
    for label, table, word in bites:
        try:
            check_profile(table=table)
            print("  %-13s NOT caught" % label)
        except AssertionError as e:
            ok = word in str(e); caught += ok
            print("  %-13s %s  %s" % (label, "caught" if ok else "WRONG CHECK", e))
    return caught, len(bites)
