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
    ("temple",    0.070, 1.7080, 0.014, 0.024, 0.024,  -0.0030, True),
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
    ("cheekbone", 0.050, 1.6560, 0.022, 0.020, 0.016,  +0.0062, True),
    ("cheek_fat", 0.044, 1.6400, 0.025, 0.020, 0.017,  +0.0036, True),
    ("hollow",    0.046, 1.6260, 0.017, 0.020, 0.014,  -0.0014, True),
    ("masseter",  0.058, 1.6040, 0.016, 0.018, 0.016,  +0.0032, True),
    # mouth
    ("lip_upper", 0.000, 1.6265, 0.024, 0.012, 0.0055, +0.0052, False),
    ("lip_lower", 0.000, 1.6140, 0.020, 0.012, 0.0065, +0.0068, False),
    ("mouthline", 0.000, 1.6202, 0.022, 0.012, 0.0022, -0.0045, False),
    ("philtrum",  0.000, 1.6340, 0.0038, 0.010, 0.008, -0.0020, False),
    ("corner",    0.025, 1.6200, 0.005, 0.010, 0.005,  -0.0018, True),
    ("mentolab",  0.000, 1.6020, 0.014, 0.012, 0.005,  -0.0028, False),
    ("chin",      0.000, 1.5860, 0.019, 0.016, 0.014,  +0.0062, False),
    # jaw: a ridge from the chin back to the angle under the ear
    ("jaw1",      0.032, 1.5880, 0.014, 0.016, 0.008,  +0.0030, True),
    ("jaw2",      0.052, 1.5960, 0.014, 0.018, 0.009,  +0.0036, True),
    ("jaw3",      0.068, 1.6100, 0.013, 0.020, 0.012,  +0.0038, True),
]

# The lids' layout, at module level because hero.face draws the lash lines
# along these margins: the aperture's half-width and half-height, and how
# far above and below the eye's centre the upper and lower lid margins sit
# at its middle (they taper to the canthi as 1 - t*t over LID_ORBIT[0]).
LID_ORBIT = (0.0158, 0.0128)
LID_UP = 0.0048
LID_DOWN = 0.0052

def lid_close(ax):
    """How much of the margin's height is left at |x|: 1 at the eye's
    middle, 0 at each canthus. The same taper lids() uses."""
    t = np.clip(np.abs(ax - 0.031) / LID_ORBIT[0], 0.0, 1.0)
    return 1.0 - t * t

def lids(P, eye, orbit=LID_ORBIT, up_margin=LID_UP, dn_margin=LID_DOWN,
         up=0.0042, down=0.0031):
    """The eyelids: two covers over the eye, not a ring around it.

    The eyeball is a 24 mm ball seated in a shallow dish. Left bare it reads
    as a bead stuck on a face, because a human eye is not a visible sphere --
    it is an almond aperture about 30 mm by 10 mm, and the rest of the ball
    is under skin. So the skin above `up_margin` and below `dn_margin` is
    pushed forward past the ball's front pole and closes over it; what is
    left between the two margins is the aperture.

    The old version bumped a ring of radius 14.5 mm evenly all the way round,
    which is a washer, not a pair of lids. The margins were then 3.8 + 4.8 =
    8.6 mm against the 10 mm quoted above, and after the 3.5 mm remesh and
    the smoothing the eye rendered as a slit; 4.8 + 5.2 is the 10 mm, and it
    is also the 5 mm half-aperture assembly.check_eye already assumes.
    """
    dx = (P[:, 0] - eye[0]) / orbit[0]
    dz = P[:, 2] - eye[2]
    within = np.clip(1.0 - (dx * dx + (dz / orbit[1]) ** 2), 0.0, 1.0) ** 0.5
    fy = np.exp(-((P[:, 1] - eye[1]) ** 2) / (2 * 0.020 ** 2))
    def step(t):
        t = np.clip(t, 0.0, 1.0); return t * t * (3.0 - 2.0 * t)
    # Both margins taper to dz = 0 at the orbit's edge, so they meet at a
    # point at each canthus. Gated on dz alone they were two horizontal bars
    # that simply stopped dead, and along the eye's own midline there was no
    # lid at all -- the ends of the aperture were wherever the globe's
    # silhouette happened to fall.
    t = np.clip(np.abs(dx), 0.0, 1.0)
    close = 1.0 - t * t
    hi = step((dz - up_margin * close) / 0.0034) * close
    lo = step((-dz - dn_margin * close) / 0.0030) * close
    return within * fy * (up * hi + down * lo)

def sculpt_face(body, surface_y, z_min=1.556, scale=None):
    """Displace the head's vertices by the feature field.

    `scale` is {feature name: factor} on the amplitudes -- how one man's
    face differs from another's on the same skull: a heavier brow, a wider
    jaw, a smaller chin. The layout (where the features ARE) is shared; it
    is the eight-heads layout every face here is drawn to, and the browser
    build draws every fighter's head from the one skull too.
    """
    scale = scale or {}
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
    for name, x, z, sx, sy, sz, amp, mirror in FACE:
        amp = amp * scale.get(name, 1.0)
        D += add(x, z, sx, sy, sz, amp)
        if mirror: D += add(-x, z, sx, sy, sz, amp)
    for s in (1, -1):
        eye = (0.031 * s, surface_y(0.031 * s, EYE_Z), EYE_Z)
        D += lids(Ph, eye)
    # Apply along the normal, then only where the face is (front hemisphere
    # of the head): features must not leak onto the back of the skull.
    front = np.clip((-N[idx, 1] + 0.55) / 0.9, 0.0, 1.0)
    P[idx] += N[idx] * (D * front)[:, None]
    me.vertices.foreach_set("co", P.reshape(-1))
    me.update()
    check_profile(scale)
    return float(np.abs(D).max()), int((np.abs(D) > 0.0005).sum())

# The features that make the nose, for check_profile's widths: the rest of
# the face (cheeks, lip) rises off the midline too and would read as nose.
NOSE_PARTS = ("radix", "bridge1", "bridge2", "bridge3", "tip", "columella",
              "ala", "alar_crease", "nostril")

def _field(x, z, scale=None, table=None, only=None):
    """The displacement the table would build at (x, z), x and z arrays."""
    scale = scale or {}
    d = np.zeros(np.broadcast(x, z).shape)
    for name, fx, fz, sx, sy, sz, amp, mirror in (table or FACE):
        if only and name not in only: continue
        amp = amp * scale.get(name, 1.0)
        for sgn in ((1, -1) if mirror else (1,)):
            d = d + amp * np.exp(-0.5 * (((x - sgn * fx) / sx) ** 2 + ((z - fz) / sz) ** 2))
    return d

def midline(lo=1.590, hi=1.740, step=0.001, scale=None, table=None):
    """The face's profile down the midline, as the field would build it."""
    zs = np.arange(lo, hi, step)
    return zs, _field(0.0, zs, scale, table)

def check_profile(scale=None, table=None):
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
    """
    zs, d = midline(scale=scale, table=table)
    peak = float(d.max()); at = float(zs[int(d.argmax())])
    assert 0.020 <= peak <= 0.030, "nose field peak %.1f mm, want 20-30" % (peak * 1000)
    assert abs(at - NOSE_TIP) < 0.008, "nose peaks at %.3f, not at the tip %.3f" % (at, NOSE_TIP)
    win = (zs > NOSE_TIP + 0.015) & (zs < BROW_Z + 0.012)
    zw, dw = zs[win], d[win]
    turns = np.nonzero(np.diff(np.sign(np.diff(dw))))[0] + 1
    assert len(turns) >= 2, "no nasion: the midline from brow to nose tip has no dip"
    nas = float(zw[turns[0]])           # the dip, then the glabella above it
    assert dw[turns[0]] < dw[turns[1]], "the turn below the glabella is a bump, not a dip"
    xs = np.arange(0.0, 0.040, 0.0005)
    def across(z):
        return _field(xs, z, scale, table, NOSE_PARTS)
    def width(z):                       # full width at half the midline height
        g = across(z)
        return 2.0 * float(xs[np.argmax(g < g[0] / 2)])
    bridge = width(NOSE_TIP + 0.024); tip = width(NOSE_TIP)
    g = across(NOSE_TIP - 0.007); alae = 2.0 * float(xs[g > 0.001].max())
    f = _field(xs[xs <= 0.0165], NOSE_Z + 0.0015, scale, table)
    slot = max(float(f[i:].max() - f[i]) for i in range(len(f)))
    assert bridge <= 0.017, "bridge %.0f mm wide at half height, want <= 17" % (bridge * 1000)
    assert tip <= 0.024, "tip lobule %.0f mm wide, want <= 24" % (tip * 1000)
    assert alae <= 0.048, "alae spread %.0f mm, want <= 48" % (alae * 1000)
    assert slot <= 0.0025, "nostril slot %.1f mm deep across the front, want <= 2.5" % (slot * 1000)
    return peak, at, nas

def bite():
    """check_profile broken once per rule, numpy only (2026-09-26): each
    must be refused, with its own word. Returns (caught, total)."""
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
