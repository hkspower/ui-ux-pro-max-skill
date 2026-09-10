"""The face as a sculpt: a displacement field over the skull surface.
Each feature is a Gaussian -- a bump or a hollow with a size in each axis
-- and the field is the sum, applied along the vertex normal. A ridge is a
row of them. Because the field is smooth, a brow grows out of the forehead
and a socket sinks into it; nothing sits on the skin as a separate thing."""
import numpy as np
from mathutils import Vector

# (x, y, z, sx, sy, sz, amplitude in metres). y is measured off the skull
# surface by the caller, so features are given at the surface (y=0 here
# means "at the skin"). Mirrored features are listed once with x>0.
FACE = [
    # brow ridge and the glabella between the brows
    ("brow",      0.030, 1.694, 0.028, 0.016, 0.0080, +0.0055, True),
    ("glabella",  0.000, 1.684, 0.011, 0.014, 0.011,  +0.0030, False),
    ("temple",    0.070, 1.702, 0.014, 0.024, 0.024,  -0.0030, True),
    # eyes: the socket hollow; the lids are rings, below
    ("socket",    0.031, 1.666, 0.020, 0.018, 0.014,  -0.0080, True),
    # nose: a ridge from the glabella to the tip, the tip, the alae, the nostrils
    ("bridge1",   0.000, 1.677, 0.0080, 0.016, 0.010, +0.0070, False),
    ("bridge2",   0.000, 1.665, 0.0085, 0.016, 0.010, +0.0105, False),
    ("bridge3",   0.000, 1.653, 0.0095, 0.016, 0.010, +0.0150, False),
    ("tip",       0.000, 1.641, 0.0125, 0.016, 0.011, +0.0215, False),
    ("ala",       0.015, 1.636, 0.0095, 0.012, 0.0085, +0.0120, True),
    ("nostril",   0.0075, 1.629, 0.0045, 0.008, 0.0045, -0.0065, True),
    # cheeks
    ("cheekbone", 0.050, 1.650, 0.022, 0.020, 0.016,  +0.0062, True),
    ("hollow",    0.046, 1.622, 0.017, 0.020, 0.014,  -0.0028, True),
    # mouth
    ("lip_upper", 0.000, 1.6195, 0.024, 0.012, 0.0055, +0.0045, False),
    ("lip_lower", 0.000, 1.607, 0.020, 0.012, 0.0065, +0.0055, False),
    ("mouthline", 0.000, 1.6132, 0.022, 0.012, 0.0022, -0.0045, False),
    ("philtrum",  0.000, 1.629, 0.0035, 0.010, 0.009, -0.0020, False),
    ("corner",    0.025, 1.613, 0.005, 0.010, 0.005,  -0.0018, True),
    ("mentolab",  0.000, 1.597, 0.014, 0.012, 0.005,  -0.0028, False),
    ("chin",      0.000, 1.583, 0.019, 0.016, 0.014,  +0.0062, False),
    # jaw: a ridge from the chin back to the angle under the ear
    ("jaw1",      0.032, 1.586, 0.014, 0.016, 0.008,  +0.0030, True),
    ("jaw2",      0.052, 1.594, 0.014, 0.018, 0.009,  +0.0038, True),
    ("jaw3",      0.068, 1.608, 0.013, 0.020, 0.012,  +0.0045, True),
]

def lids(P, eye, r0=0.0145, sx=0.0060, up=0.0048, down=0.0026):
    """Eyelid rings around an eye centre: bump on a circle of radius r0 in
    the xz plane, heavier above the eye than below."""
    dx = P[:, 0] - eye[0]; dz = P[:, 2] - eye[2]
    r = np.sqrt(dx * dx + dz * dz)
    ring = np.exp(-((r - r0) ** 2) / (2 * sx * sx))
    amp = np.where(dz > 0, up, down)
    # only near the face surface in y
    fy = np.exp(-((P[:, 1] - eye[1]) ** 2) / (2 * 0.014 ** 2))
    return ring * amp * fy

def sculpt_face(body, surface_y, z_min=1.556):
    """Displace the head's vertices by the feature field."""
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
        D += add(x, z, sx, sy, sz, amp)
        if mirror: D += add(-x, z, sx, sy, sz, amp)
    for s in (1, -1):
        eye = (0.031 * s, surface_y(0.031 * s, 1.666), 1.666)
        D += lids(Ph, eye)
    # Apply along the normal, then only where the face is (front hemisphere
    # of the head): features must not leak onto the back of the skull.
    front = np.clip((-N[idx, 1] + 0.35) / 0.9, 0.0, 1.0)
    P[idx] += N[idx] * (D * front)[:, None]
    me.vertices.foreach_set("co", P.reshape(-1))
    me.update()
    return float(np.abs(D).max()), int((np.abs(D) > 0.0005).sum())
