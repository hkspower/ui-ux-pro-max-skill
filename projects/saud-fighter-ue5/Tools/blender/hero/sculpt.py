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
    # nose: a ridge from the glabella to the tip, the tip, the alae, the
    # nostrils. The four ridge Gaussians are 12 mm apart with a 10 mm sigma,
    # so each gives its neighbours half its amplitude and they pile up: the
    # old amplitudes summed to 35 mm on the midline and measured 27 mm of
    # projection on the built mesh, against 19-22 mm on a real male nose.
    # Scaled to 0.765 and moved 4 mm up with the rest of the layout.
    # The radix -- the dip between the brow and the bridge. Without it the
    # midline runs in one unbroken convex ramp from the hairline to the nose
    # tip, which is the shop-dummy profile and the most legible "not a
    # person" line on the whole head. It has to be a local MINIMUM, so it is
    # a hollow cut into the ridge, not a smaller bump.
    ("radix",     0.000, 1.6870, 0.013, 0.014, 0.0078, -0.0064, False),
    ("bridge1",   0.000, 1.6810, 0.0080, 0.016, 0.010, +0.0054, False),
    ("bridge2",   0.000, 1.6690, 0.0085, 0.016, 0.010, +0.0080, False),
    ("bridge3",   0.000, 1.6570, 0.0095, 0.016, 0.010, +0.0100, False),
    ("tip",       0.000, 1.6450, 0.0125, 0.016, 0.011, +0.0175, False),
    ("ala",       0.016, 1.6400, 0.0098, 0.012, 0.0085, +0.0092, True),
    ("nostril",   0.0078, 1.6330, 0.0045, 0.008, 0.0045, -0.0080, True),
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
    ("philtrum",  0.000, 1.6360, 0.0038, 0.010, 0.009, -0.0034, False),
    ("corner",    0.025, 1.6200, 0.005, 0.010, 0.005,  -0.0018, True),
    ("mentolab",  0.000, 1.6020, 0.014, 0.012, 0.005,  -0.0028, False),
    ("chin",      0.000, 1.5860, 0.019, 0.016, 0.014,  +0.0062, False),
    # jaw: a ridge from the chin back to the angle under the ear
    ("jaw1",      0.032, 1.5880, 0.014, 0.016, 0.008,  +0.0030, True),
    ("jaw2",      0.052, 1.5960, 0.014, 0.018, 0.009,  +0.0036, True),
    ("jaw3",      0.068, 1.6100, 0.013, 0.020, 0.012,  +0.0038, True),
]

def lids(P, eye, orbit=(0.0158, 0.0128), up_margin=0.0038, dn_margin=0.0048,
         up=0.0042, down=0.0031):
    """The eyelids: two covers over the eye, not a ring around it.

    The eyeball is a 24 mm ball seated in a shallow dish. Left bare it reads
    as a bead stuck on a face, because a human eye is not a visible sphere --
    it is an almond aperture about 30 mm by 10 mm, and the rest of the ball
    is under skin. So the skin above `up_margin` and below `dn_margin` is
    pushed forward past the ball's front pole and closes over it; what is
    left between the two margins is the aperture.

    The old version bumped a ring of radius 14.5 mm evenly all the way round,
    which is a washer, not a pair of lids.
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

def midline(lo=1.590, hi=1.740, step=0.001, scale=None):
    """The face's profile down the midline, as the field would build it."""
    scale = scale or {}
    zs = np.arange(lo, hi, step)
    d = np.zeros_like(zs)
    for name, fx, fz, sx, sy, sz, amp, mirror in FACE:
        amp = amp * scale.get(name, 1.0)
        for sgn in ((1, -1) if mirror else (1,)):
            d += amp * np.exp(-0.5 * (((0.0 - sgn * fx) / sx) ** 2 + ((zs - fz) / sz) ** 2))
    return zs, d

def check_profile(scale=None):
    """The two things about the profile that a render will not tell you
    until it is too late, and that both went wrong before:

    the nose must not run away (the four ridge Gaussians sit 12 mm apart
    with a 10 mm sigma, so each gives its neighbours half its amplitude and
    the sum once reached 35 mm, which measured 27 mm of projection against
    19-22 on a real male nose); and there must be a nasion -- a local
    minimum between the glabella and the bridge. Without one the midline is
    a single convex ramp from the hairline to the tip.
    """
    zs, d = midline(scale=scale)
    peak = float(d.max()); at = float(zs[int(d.argmax())])
    assert 0.020 <= peak <= 0.030, "nose field peak %.1f mm, want 20-30" % (peak * 1000)
    assert abs(at - NOSE_TIP) < 0.008, "nose peaks at %.3f, not at the tip %.3f" % (at, NOSE_TIP)
    win = (zs > NOSE_TIP + 0.015) & (zs < BROW_Z + 0.012)
    zw, dw = zs[win], d[win]
    turns = np.nonzero(np.diff(np.sign(np.diff(dw))))[0] + 1
    assert len(turns) >= 2, "no nasion: the midline from brow to nose tip has no dip"
    nas = float(zw[turns[0]])           # the dip, then the glabella above it
    assert dw[turns[0]] < dw[turns[1]], "the turn below the glabella is a bump, not a dip"
    return peak, at, nas
