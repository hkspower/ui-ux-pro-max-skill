"""Stage 3: what he wears, as shells off the body. The tee and the track
pants are the body's own surface in their region, pushed out along the
normals and given thickness -- so they fit by construction -- with folds
from a low-frequency noise, and hems as rings. The trainers are the foot
lofts themselves, with a sole slab under each."""
import bpy, bmesh, math, sys, os
from mathutils import Vector
from . import anatomy as A
J = A.J; Jp = A.Jp

def _pt_seg(p, a, b):
    ab = b - a; t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared)); return (p - (a + ab * t)).length

def tee_region(c):
    """Trunk from the hem to the neck opening, and the sleeves."""
    if 1.062 <= c.z <= 1.575 and abs(c.x) < 0.24:
        if c.z > 1.505 and math.hypot(c.x, c.y - 0.004) < 0.074: return False   # neck opening
        if c.z > 1.505 and c.y < -0.03 and math.hypot(c.x, c.y + 0.02) < 0.085: return False  # scoop at the front
        return True
    for side in (1, -1):
        sh = Vector((Jp("upperarm_l").x * side, Jp("upperarm_l").y, Jp("upperarm_l").z))
        el = Vector((Jp("lowerarm_l").x * side, Jp("lowerarm_l").y, Jp("lowerarm_l").z))
        t = (c - sh).dot(el - sh) / (el - sh).length_squared
        if -0.35 < t < 0.40 and _pt_seg(c, sh, el) < 0.095: return True
    return False

def pants_region(c):
    if 0.118 <= c.z <= 1.075 and abs(c.x) < 0.26: return True
    return False


# ---- the sleeveless tops, 2026-09-28 --------------------------------------
# "make Saud more aggressive and more fit look ... make all game like dark
# anime adult style": the Unreal build's own tops, NOT the browser's, which
# draws every man in a tee (`look.tee`). One sleeveless top, cut two ways
# (pipeline.TOPS), each a row of numbers, and one region, one fit, one
# strip rule, one edge paint and one hole check for both:
#
#   compression  Saud's: tight (the fit's hull pulled TANK_TENSION of the
#                way to the skin), the armhole's bottom at the flank near
#                1.28, a strap 132 mm off the midline from 1.48 up; his
#                colours and the Kuwait flag patch as on his tee
#   singlet      the thug's and AL-WAHSH's: a loose vest on the tee's own
#                drape, a deep armhole (an ellipse about (0.205, 1.442),
#                0.075 x 0.115, bottoming at 1.327) and scoops front and
#                back, the strap 64 mm wide on the shoulder shelf
#
# `armhole` is the opening's inner edge as knots (z, |x|): above the first
# knot everything further out than the edge is open. `scoops` are ellipses
# (centre z, half-width, half-height) cut from the front (y < 0) and the
# back. The neck opening is the tee's.
TANKS = {
    "compression": dict(
        armhole=[(1.28, 0.1980), (1.30, 0.1962), (1.32, 0.1911), (1.34, 0.1837), (1.36, 0.1748), (1.38, 0.1650),
                 (1.40, 0.1552), (1.42, 0.1463), (1.44, 0.1389), (1.46, 0.1338), (1.48, 0.1320), (1.70, 0.1320)],
        # a back scoop (2026-09-28, from the fast build's kick render):
        # without it the tank climbed the trapezius behind the neck to
        # 1.561, 30-90 mm off the midline -- a stand-up collar at the nape
        # once the head turned; 1.51-1.55 with it, the straps over the traps
        scoops=(("back", 1.580, 0.085, 0.070),), offset=0.0030, fold=0.0006, binding=0.008),
    "singlet": dict(
        armhole=[(1.3270, 0.2050), (1.3462, 0.1635), (1.3653, 0.1491), (1.3845, 0.1400), (1.4037, 0.1343),
                 (1.4228, 0.1310), (1.4420, 0.1300), (1.4612, 0.1310), (1.4803, 0.1343), (1.4995, 0.1400),
                 (1.5187, 0.1491), (1.5378, 0.1635), (1.5570, 0.2050), (1.5580, 0.3000), (1.7000, 0.3000)],
        scoops=(("front", 1.540, 0.080, 0.130), ("back", 1.560, 0.075, 0.080)), offset=0.0060, fold=0.0010,
        binding=0.006),
}
SLEEVES = {"tee": True, "compression": False, "singlet": False}
TANK_TENSION = 0.55       # how much of the hull's reach the compression top takes (1.0 the tee's drape)


def armhole_x(z, cut):
    """The armhole's inner edge, |x| at height z (np-friendly), for a tank
    cut: 1.0 (nothing open) below its bottom."""
    k = TANKS[cut]["armhole"]
    zs = [a for a, _ in k]; xs = [b for _, b in k]
    return np.where(np.asarray(z) < zs[0], 1.0, np.interp(z, zs, xs))


def tank_region(c, cut, margin=0.0):
    """The tank's trunk, as tee_region's without the sleeves and with its
    cut's armholes and scoops taken out; `margin` shrinks it inward from
    every edge (the strip keeps a band of skin inside every one)."""
    m = margin
    if not (1.062 + m <= c.z <= 1.575 - m and abs(c.x) < 0.24):
        return False
    if c.z > 1.505 - m and math.hypot(c.x, c.y - 0.004) < 0.074 + m: return False       # neck opening
    if c.z > 1.505 - m and c.y < -0.03 and math.hypot(c.x, c.y + 0.02) < 0.085 + m: return False   # scoop at the front
    row = TANKS[cut]
    k = row["armhole"]
    if c.z > k[0][0] - m and abs(c.x) > float(armhole_x(c.z, cut)) - m: return False
    for side, cz, a, b in row["scoops"]:
        if (c.y < 0) == (side == "front") and (c.x / (a + m)) ** 2 + ((c.z - cz) / (b + m)) ** 2 < 1.0: return False
    return True


def top_region(top):
    """The region test for a top ('tee' or a TANKS cut)."""
    return tee_region if top == "tee" else (lambda c: tank_region(c, top))

def shell(body, name, region, offset, thickness, fold=0.0, fold_size=0.14):
    """Duplicate the faces in `region`, push them out, thicken, and fold."""
    bm = bmesh.new(); bm.from_mesh(body.data)
    keep = [f for f in bm.faces if region(f.calc_center_median())]
    drop = [f for f in bm.faces if f not in set(keep)]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    # The region's edge is a staircase of voxel faces; a hem is a line.
    # Relax each boundary vertex toward its two boundary neighbours.
    bnd = {v for v in bm.verts if any(e.is_boundary for e in v.link_edges)}
    for _ in range(12):
        new = {}
        for v in bnd:
            nb = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
            if len(nb) == 2: new[v] = (v.co + nb[0].co + nb[1].co) / 3.0
        for v, co in new.items(): v.co = co
    bm.normal_update()
    # push out along the normals; every remaining vert is on the garment
    for v in bm.verts:
        v.co += v.normal * offset
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    g = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(g)
    bpy.context.view_layer.objects.active = g; g.select_set(True)
    if fold > 0.0:
        tex = bpy.data.textures.new(name + "_folds", "CLOUDS"); tex.noise_scale = fold_size; tex.noise_depth = 2
        d = g.modifiers.new("Folds", "DISPLACE"); d.texture = tex; d.strength = fold; d.mid_level = 0.5; d.direction = 'NORMAL'
        bpy.ops.object.modifier_apply(modifier="Folds")
    # Single-sided: a game garment is a surface, and an inner skin would
    # only share the outer one's UVs and fight it in the bake. The engine
    # material is two-sided for the hems.
    sm = g.modifiers.new("S", "SMOOTH"); sm.factor = 0.5; sm.iterations = 2
    bpy.ops.object.modifier_apply(modifier="S")
    bpy.ops.object.shade_smooth()
    return g

def soles():
    out = []
    for side in (1, -1):
        x = Jp("foot_l").x * side
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, -0.082, 0.010))
        o = bpy.context.object; o.name = "sole"; o.scale = (0.098, 0.320, 0.020)
        bpy.ops.object.transform_apply(scale=True)
        bv = o.modifiers.new("Bev", "BEVEL"); bv.width = 0.008; bv.segments = 3
        bpy.ops.object.modifier_apply(modifier="Bev"); bpy.ops.object.shade_smooth()
        out.append(o)
    return out

def dress(body, tee=True, top="tee", bottom="track"):
    """The top (`top`: 'tee', or a TANKS cut) and the trousers (`bottom`:
    'track' or 'jogger', LEG_FIT) on the body, fitted and checked.

    `tee=False` is ZAYOS (`look.tee: false`): shell() still runs, with
    a region that keeps nothing, so the returned object is a real, empty
    Tee -- zero faces, zero vertices -- rather than None. Everything after
    this already copies, decimates, UV-unwraps, paints, binds and joins a
    list of objects that includes "Tee"; an empty one of those is a no-op
    at every one of those stages (checked: decimate short-circuits under
    its own target, and the rest are per-vertex/per-face loops over
    nothing), so building bare-chested does not need a second code path,
    only skipping the (also checked, on the hair precedent) bake of it."""
    # the cloud noise is a millimetre now, only irregularity: the folds are
    # fit()'s, where cloth actually folds, and the fit is fit()'s drape
    assert top in SLEEVES, "no such top: %r (%s)" % (top, ", ".join(SLEEVES))
    assert bottom in LEG_FIT, "no such trousers: %r (%s)" % (bottom, ", ".join(LEG_FIT))
    # (a tank's shell sits closer and folds less: TANKS' offset and fold)
    off, fold = (0.006, 0.0010) if top == "tee" else (TANKS[top]["offset"], TANKS[top]["fold"])
    t = shell(body, "Tee", top_region(top) if tee else (lambda c: False), off, 0.0025, fold=fold, fold_size=0.16)
    pants = shell(body, "Pants", pants_region, 0.010 if bottom == "track" else JOGGER_OFFSET, 0.003, fold=0.0012, fold_size=0.20)
    # fit() is called (g, kind, body) for the tee and the track trousers,
    # as always; the cut goes as a keyword only when it is not those
    for g, kind, cut in ((t, "tee", top), (pants, "pants", bottom)):
        info = fit(g, kind, body) if cut in ("tee", "track") else fit(g, kind, body, cut=cut)
        if info.get("moved"):
            print("cloth     : %-5s draped %d verts (up to %.0f mm), folds to %.1f mm, %d held off the skin"
                  % (cut, info["moved"], info["drape_max"] * 1000, info["fold_max"] * 1000, info["pushed"]))
    if check_cloth_in_dress:
        ck = check_cloth(t, pants, body, top=top, bottom=bottom)
        print("cloth     : " + "  ".join("%s %.4f" % kv for kv in ck.items()))
        if tee and top != "tee":
            cov, of = check_bare(body, t)
            print("cloth     : bare arms: %d of %d outer upper-arm faces under the %s" % (cov, of, top))
    return t, pants, soles()


# ---------------------------------------------------------------- the cloth
# 2026-09-27 ("improve clothes": fit and folds, fabric texture). The tee and
# the trousers were the body's own surface pushed out 6 and 10 mm and given
# a 2.5-4.5 mm cloud noise: skin-tight shells that followed every groove --
# the spinal furrow, the abs, the cleft between the glutes -- and wrapped
# the waist and the calves, with folds that ran no way in particular. Cloth
# does neither. It bridges a hollow (it is stretched across it), it hangs
# from what is above it (off the lats and the chest down to the hem, off
# the seat and the thigh down to the cuff), and it folds where it is short
# of room -- stacked above an elastic cuff, gathered under a waistband,
# creased behind the knee, dragged from the crotch and the armpit.
import numpy as np

def _hull(pts):
    """2-D convex hull, counter-clockwise (Andrew's monotone chain)."""
    p = sorted(map(tuple, pts))
    if len(p) < 3: return np.array(p)
    def cross(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for q in p:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], q) <= 0: lo.pop()
        lo.append(q)
    for q in reversed(p):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], q) <= 0: hi.pop()
        hi.append(q)
    return np.array(lo[:-1] + hi[:-1])

def _hull_radius(uv, bins):
    """The hull of a slice's points (local 2-D, the axis at the origin) as
    a radius per angle bin: what cloth stretched round the slice spans."""
    h = _hull(uv)
    if len(h) < 3: return None
    th = np.arctan2(h[:, 0], h[:, 1]); r = np.hypot(h[:, 0], h[:, 1])
    o = np.argsort(th); th, r = th[o], r[o]
    th = np.concatenate([th - 2 * np.pi, th, th + 2 * np.pi]); r = np.concatenate([r, r, r])
    return np.interp(bins, th, r)

def _drape_region(P, idx, centre, ax, u, v, dz, slope, hang_down=True, taper=None, max_grow=0.030):
    """Drape the vertices `idx` of P about an axis: in slices of `dz` along
    `ax` (from `centre`), each slice's hull; then, going down the axis,
    no slice narrower than the one above less `slope` a unit of fall.
    `taper(t)` (0..1, t the fraction down the region) pulls the result
    back toward the hull where an elastic cuff gathers it. Moves points
    outward only. Returns the displacement lengths."""
    if len(idx) < 50: return np.zeros(0)
    Q = P[idx] - centre
    s = Q @ ax
    a = Q @ u; b = Q @ v
    th = np.arctan2(a, b); r = np.hypot(a, b)
    nb = 96; bins = np.linspace(-np.pi, np.pi, nb, endpoint=False)
    k = np.floor((s - s.min()) / dz).astype(int); nk = k.max() + 1
    R = np.full((nk, nb), np.nan)
    for i in range(nk):
        m = k == i
        if m.sum() >= 8:
            hr = _hull_radius(np.stack([a[m], b[m]], 1), bins)
            if hr is not None: R[i] = hr
    # fill empty slices from their neighbours
    for i in range(nk):
        if np.isnan(R[i]).all():
            j = i - 1 if i > 0 and not np.isnan(R[i - 1]).all() else min(i + 1, nk - 1)
            R[i] = R[j]
    H = R.copy()
    order = range(1, nk) if hang_down else range(nk - 2, -1, -1)
    for i in order:
        prev = i - 1 if hang_down else i + 1
        H[i] = np.maximum(R[i], H[prev] - slope * dz)
    if taper is not None:
        for i in range(nk):
            w = taper(i / max(nk - 1, 1)); H[i] = H[i] * (1 - w) + R[i] * w
    # stretched round the body again: the hang is taken angle by angle, and
    # where one angle hangs from a bulge above (a lat) and its neighbour
    # does not, the slice had a concave corner -- a crease down the flank
    # from the armpit to the hem (seen on the full build). Cloth pulled
    # round a body has none; each slice is its own hull again.
    ca, sa = np.cos(bins), np.sin(bins)
    for i in range(nk):
        hr = _hull_radius(np.stack([H[i] * sa, H[i] * ca], 1), bins)
        if hr is not None: H[i] = np.maximum(H[i], hr)
    # smooth the hang over neighbouring slices and angles: a slice's hull
    # jumps, and each vertex taking its own slice's value terraced the
    # cloth into horizontal ridges (the first preview)
    for _ in range(3):
        Hp = np.vstack([H[:1], H, H[-1:]])
        H = 0.25 * Hp[:-2] + 0.5 * Hp[1:-1] + 0.25 * Hp[2:]
    # and round its corners: a hull is a polygon, sharp at the outermost
    # point of a bulge (the lat), and the hang carried that corner down the
    # flank as a ridge that caught the rim light (the full build of Saud)
    for _ in range(ANGLE_SMOOTH):
        H = 0.25 * np.roll(H, 1, 1) + 0.5 * H + 0.25 * np.roll(H, -1, 1)
    # per vertex: the hang radius, interpolated between slices (at slice
    # centres) and between angle bins (which wrap)
    sf = (s - s.min()) / dz - 0.5
    k0 = np.clip(np.floor(sf).astype(int), 0, nk - 1); k1 = np.clip(k0 + 1, 0, nk - 1)
    fk = np.clip(sf - np.floor(sf), 0.0, 1.0)
    bi = (th + np.pi) / (2 * np.pi) * nb
    b0 = np.floor(bi).astype(int) % nb; b1 = (b0 + 1) % nb; f = bi - np.floor(bi)
    def at(kk): return H[kk, b0] * (1 - f) + H[kk, b1] * f
    want = at(k0) * (1 - fk) + at(k1) * fk
    grow = np.clip(want - r, 0.0, max_grow)
    dirv = (np.outer(a / np.maximum(r, 1e-9), u) + np.outer(b / np.maximum(r, 1e-9), v))
    return grow, dirv

def _face_normals(P, ls, lt, lv):
    """Each polygon's normal (unnormalised): the cross of its diagonals, or
    of two sides for a triangle."""
    a = P[lv[ls]]; b = P[lv[ls + 1]]; c = P[lv[ls + 2]]
    d = np.where((lt >= 4)[:, None], P[lv[ls + np.minimum(3, lt - 1)]], a)
    return np.where((lt >= 4)[:, None], np.cross(c - a, d - b), np.cross(b - a, c - a))

def _untangle(me, P, D, passes):
    """Smooth the displacement D over the mesh, but only round faces that
    D turns over (their normal more than ~80 degrees from where it was),
    two rings out, until none are left or `passes` runs out."""
    n = len(P)
    E = np.empty(len(me.edges) * 2, dtype=np.int64); me.edges.foreach_get("vertices", E); E = E.reshape(-1, 2)
    deg = np.maximum(np.bincount(E.ravel(), minlength=n), 1).astype(float)[:, None]
    m = len(me.polygons)
    ls = np.empty(m, dtype=np.int64); me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(m, dtype=np.int64); me.polygons.foreach_get("loop_total", lt)
    lv = np.empty(len(me.loops), dtype=np.int64); me.loops.foreach_get("vertex_index", lv)
    n0 = _face_normals(P, ls, lt, lv)
    n0 /= np.maximum(np.linalg.norm(n0, axis=1), 1e-12)[:, None]
    for _ in range(passes):
        n1 = _face_normals(P + D, ls, lt, lv)
        n1 /= np.maximum(np.linalg.norm(n1, axis=1), 1e-12)[:, None]
        bad = np.nonzero((n0 * n1).sum(1) < 0.2)[0]
        if not len(bad): break
        sel = np.zeros(n, bool)
        for k in range(4): sel[lv[ls[bad] + np.minimum(k, lt[bad] - 1)]] = True
        for _r in range(2):
            grow = sel.copy(); grow[E[sel[E[:, 0]], 1]] = True; grow[E[sel[E[:, 1]], 0]] = True; sel = grow
        acc = np.zeros((n, 3))
        np.add.at(acc, E[:, 0], D[E[:, 1]]); np.add.at(acc, E[:, 1], D[E[:, 0]])
        D = np.where(sel[:, None], 0.5 * D + 0.5 * acc / deg, D)
    return D

def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0); return t * t * (3 - 2 * t)

def _noise(P, scale, seed):
    """A cheap smooth value: a few incommensurate sines, enough to break a
    fold's regularity without importing the texture noise."""
    x, y, z = P[:, 0] * scale, P[:, 1] * scale, P[:, 2] * scale
    return (np.sin(1.7 * x + 2.3 * z + seed) + np.sin(2.9 * y - 1.3 * z + 1.7 * seed)
            + np.sin(1.1 * x + 3.7 * y + 0.9 * z + 2.9 * seed)) / 3.0

CLEAR = {"tee": 0.0030, "pants": 0.0045,   # the closest cloth comes to the skin
         "compression": 0.0022}             # (a cut CLEAR does not name takes its kind's)
# The trouser legs' drape, per cut: (slope, taper (from, to) as a fraction
# down the leg, max_grow). 'track' as it was; 'jogger' (Saud, 2026-09-28)
# narrows faster under the thigh and gathers from the lower shin: 7-8 mm
# off the leg where the track stands 10-12 (slope 0.10 made the knee worse,
# 14.3 mm).
LEG_FIT = {"track": (0.16, (0.86, 0.98), 0.025), "jogger": (0.30, (0.78, 0.96), 0.016)}
JOGGER_OFFSET = 0.007     # the jogger's shell off the skin (the track's 0.010)
# The seat and hips' drape per cut, (slope, max_grow). The jogger's was the
# track's, 20 mm of hang from the hips: on Saud it stood the cloth off his
# hips as a box and ended at the crotch in a ledge across the front
# (2026-10-03, "fix core shape" -- the joggers' waist bulge); a jogger is
# cut close and its elastic pulls it to him.
SEAT_FIT = {"track": (0.30, 0.020, None),             # (slope, max_grow, front fade y from-to)
            "jogger": (0.30, 0.012, (-0.06, -0.01))}   # behind only: the front 17 mm off him at 0.97 before
FOLD_SCALE = 1.0          # the folds' amplitude, for the check's sabotage
TEE_SLOPE = 0.35          # how fast the tee may narrow under what it hangs from (0.20 tented it off the lats)
ANGLE_SMOOTH = 10         # passes rounding each slice's hang across angles (was 3)
ARM_CLEAR = (0.11, 0.15)  # the tee's drape keeps this far off the upper arm's axis
SLEEVE_LOOSE = (0.001, 0.004, 0.003)  # the sleeve off the arm: at the shoulder, more to the cuff, more below
DRAPE_SMOOTH = 60         # at most, smoothing the drape where it turns faces over
PELVIS_Z = 0.93           # the seat's drape stops above the crotch (0.90)
MIN_CLEAR = 0.002         # check_cloth's floor, whatever CLEAR is set to
check_cloth_in_dress = True   # --cloth-check checks each dressing itself

def fit(g, kind, body=None, cut=None):
    """Drape and fold one garment in place ("tee" or "pants"). Canonical
    positions (before a man's size). See the note above. `cut` is the
    top's (None the tee, or a TANKS cut) or the trousers' (None 'track',
    or a LEG_FIT cut)."""
    me = g.data
    n = len(me.vertices)
    if n == 0: return dict(moved=0)
    P = np.empty(n * 3); me.vertices.foreach_get("co", P); P = P.reshape(n, 3)
    D = np.zeros((n, 3))
    X = np.array([1.0, 0, 0]); Y = np.array([0, 1.0, 0]); Z = np.array([0, 0, 1.0])
    cut = cut or ("tee" if kind == "tee" else "track")
    if cut == "compression":
        # A compression top hugs: each slice's hull (it bridges the spinal
        # furrow and the hollows between the abs) with no hang from what is
        # above it, and only TANK_TENSION of that reach -- the waist and the
        # abs show through it. Faded out over the chest, where the straps
        # lie on the trapezius as the shell does. No waist or armpit folds.
        up = np.nonzero(P[:, 2] < 1.46)[0]
        out = _drape_region(P, up, np.array([0.0, 0.004, 1.46]), -Z, X, Y, 0.006, slope=4.0, max_grow=0.010)
        if len(out):
            grow, dirv = out
            w = TANK_TENSION * (1.0 - _smoothstep(1.40, 1.46, P[up, 2]))
            D[up] += dirv * (grow * w)[:, None]
    elif kind == "tee":
        rows = A.TRUNK_ROWS
        zs = [r[0] for r in rows]; rx = np.interp(P[:, 2], zs, [r[2] for r in rows])
        # The trunk: everything inside the sides, and below the armpit the
        # sides too. Taken inside 95 % of the half-width only (the sleeves
        # start outside it), the tee's own side strip stayed on the skin
        # while the front and back hung out up to 3 cm: a vertical step down
        # each flank, armpit to hem (seen on the full build of Saud).
        # Nor the sleeve and the web of the armpit, which reach down to 1.26
        # on Saud's arms (x 1.30): taken in, the tee hung from them and stood
        # 36 mm off his waist. Kept out by their distance from the upper arm.
        ax_ = np.abs(P[:, 0])
        arm_d = np.full(n, np.inf)
        for sgn in (1, -1):
            sh = np.array(Jp("upperarm_l")) * np.array([sgn, 1, 1]); el = np.array(Jp("lowerarm_l")) * np.array([sgn, 1, 1])
            d = el - sh; L = np.linalg.norm(d); d /= L
            tt = np.clip((P - sh) @ d / L, 0.0, 1.0)
            arm_d = np.minimum(arm_d, np.linalg.norm(P - (sh + np.outer(tt * L, d)), axis=1))
        trunk = np.nonzero((P[:, 2] < 1.40) & ((ax_ < rx * 0.95) | ((P[:, 2] < 1.30) & (arm_d > ARM_CLEAR[0]))))[0]
        out = _drape_region(P, trunk, np.array([0.0, 0.004, 1.40]), -Z, X, Y, 0.006, slope=TEE_SLOPE)
        if len(out):
            grow, dirv = out
            # none under the arms: from 1.30 up in the middle, and at the
            # sides from 1.22 up (the side strip above 1.30 is not taken at
            # all) and near the arm, the two blended across the side so
            # nothing steps
            side = _smoothstep(0.80, 0.95, ax_[trunk] / rx[trunk])
            w = (1.0 - _smoothstep(1.30, 1.37, P[trunk, 2])) * (1.0 - side) \
                + (1.0 - _smoothstep(1.22, 1.30, P[trunk, 2])) * _smoothstep(ARM_CLEAR[0], ARM_CLEAR[1], arm_d[trunk]) * side
            D[trunk] += dirv * (grow * w)[:, None]
        # the sleeves: looser toward the cuff, and hanging off the arm (a
        # singlet has none: run on it, this pushed the armhole's side 1-8 mm
        # off the arm)
        for sgn in ((1, -1) if SLEEVES[cut] else ()):
            sh = np.array(Jp("upperarm_l")) * np.array([sgn, 1, 1]); el = np.array(Jp("lowerarm_l")) * np.array([sgn, 1, 1])
            d = el - sh; L = np.linalg.norm(d); d /= L
            t = (P - sh) @ d / L
            m = np.nonzero((P[:, 0] * sgn > rx * 0.95) & (t > -0.1) & (t < 0.5))[0]
            c = sh + np.outer(t[m] * L, d); rv = P[m] - c
            rn = rv / np.maximum(np.linalg.norm(rv, axis=1), 1e-9)[:, None]
            along = np.clip(t[m] / 0.40, 0, 1)
            # (the scan, 2026-09-28: at 0.002 + 0.007 + 0.004 the sleeve stood
            # 13 mm out from the 6 mm shell at the cuff, 19 off the arm, and
            # read as a box; a jersey sleeve on a fighter's arm lies closer)
            loose = SLEEVE_LOOSE[0] + SLEEVE_LOOSE[1] * along + SLEEVE_LOOSE[2] * along * np.clip(-rn[:, 2], 0, 1)
            D[m] += rn * (loose * _smoothstep(-0.05, 0.10, t[m]))[:, None]
    else:
        # the seat and the hips: one hull a slice, over the cleft
        rows = A.TRUNK_ROWS
        # above the crotch (0.90) only: run below it, the hull spanned both
        # thighs and hung a skirt between the legs (the first preview)
        pel = np.nonzero(P[:, 2] >= PELVIS_Z)[0]
        s_slope, s_grow, s_front = SEAT_FIT[cut]
        out = _drape_region(P, pel, np.array([0.0, 0.012, 1.08]), -Z, X, Y, 0.006, slope=s_slope, max_grow=s_grow)
        wpel = _smoothstep(PELVIS_Z, PELVIS_Z + 0.04, P[pel, 2]) if len(pel) else None
        if s_front and len(pel):
            # only behind, over the seat's cleft: fading out toward the front
            wpel = wpel * _smoothstep(s_front[0], s_front[1], P[pel, 1])
        if len(out):
            grow, dirv = out; D[pel] += dirv * (grow * wpel)[:, None]
        # each leg: hangs from the seat and the thigh, gathered at the cuff
        for sgn in (1, -1):
            hip = np.array(Jp("thigh_l")) * np.array([sgn, 1, 1]); ank = np.array(Jp("foot_l")) * np.array([sgn, 1, 1])
            ax = ank - hip; L = np.linalg.norm(ax); ax /= L
            u = np.cross(ax, Y); u /= np.linalg.norm(u); v = np.cross(u, ax)
            # below the crotch only: reaching up into the pelvis, a slice's
            # hull took in the seat and pushed the inner thigh's cloth 68 mm
            # into the other leg (the first preview)
            leg = np.nonzero((P[:, 0] * sgn > 0.004) & (P[:, 2] < 0.87))[0]
            slope, (ta, tb), mg = LEG_FIT[cut]
            out = _drape_region(P, leg, hip, ax, u, v, 0.010, slope=slope,
                                taper=lambda f, ta=ta, tb=tb: _smoothstep(ta, tb, f), max_grow=mg)
            if len(out):
                grow, dirv = out
                w = 1.0 - _smoothstep(0.82, 0.87, P[leg, 2])
                D[leg] += dirv * (grow * w)[:, None]
    # The drape pushes each vertex straight out from the axis, and where the
    # surface curls round a bulge (the flank round the lat) two neighbours
    # were pushed across each other: 339 faces down the tee's sides turned
    # over, a ragged crease from the armpit to the hem (25 on the shell
    # before it). Where a face turns over, the drape is smoothed over the
    # garment's surface round it until it does not -- only there: smoothed
    # everywhere, it lost the bridging of the small hollows (the abs showed
    # through again).
    if DRAPE_SMOOTH:
        D = _untangle(me, P, D, DRAPE_SMOOTH)
    P = P + D
    me.vertices.foreach_set("co", P.reshape(-1)); me.update()
    # ---- the folds, along the normals of the draped surface
    Nn = np.empty(n * 3); me.vertices.foreach_get("normal", Nn); Nn = Nn.reshape(n, 3)
    F = np.zeros(n)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    if cut == "compression":
        pass
    elif kind == "tee":
        # slack above the hem, round the waist: soft horizontal folds
        env = _smoothstep(1.070, 1.095, z) * (1 - _smoothstep(1.17, 1.22, z))
        F += 0.0015 * env * (0.6 + 0.4 * _noise(P, 30.0, 11.0)) * np.sin(2 * np.pi * (z - 1.07) / 0.034 + 1.8 * _noise(P, 18.0, 1.0))
        # drag from each armpit toward the middle of the chest and back
        for sgn in (1, -1):
            ap = np.array([0.165 * sgn, 0.0, 1.345])
            q = P - ap; rho = np.hypot(q[:, 0], q[:, 2]); ang = np.arctan2(q[:, 2], -q[:, 0] * sgn)
            env = _smoothstep(0.025, 0.05, rho) * (1 - _smoothstep(0.09, 0.14, rho)) * (np.abs(x) < 0.17)
            F += 0.0015 * env * np.sin(9.0 * ang + 1.5 * _noise(P, 14.0, 2.0 + sgn))
    else:
        for sgn in (1, -1):
            hip = np.array(Jp("thigh_l")) * np.array([sgn, 1, 1]); ank = np.array(Jp("foot_l")) * np.array([sgn, 1, 1])
            ax = ank - hip; L = np.linalg.norm(ax); ax /= L
            t = (P - hip) @ ax / L
            side = (x * sgn > 0.004).astype(float)
            # stacked above the elastic cuff
            env = _smoothstep(0.82, 0.87, t) * (1 - _smoothstep(0.95, 0.985, t)) * side
            ang = np.arctan2(x - hip[0], y - hip[1])
            F += (0.0035 * env * (0.65 + 0.35 * _noise(P, 35.0, 4.0 + sgn))
                  * np.sin(2 * np.pi * t * L / 0.030 + 1.6 * np.sin(2 * ang + sgn) + 2.2 * _noise(P, 20.0, 3.0 + sgn)))
            # creased behind the knee
            back = _smoothstep(0.0, 0.03, y - (hip[1] + ax[1] * t * L))
            env = np.exp(-((t - 0.52) / 0.045) ** 2) * back * side
            F += 0.0030 * env * np.sin(2 * np.pi * t * L / 0.022 + 1.2 * _noise(P, 25.0, 5.0 + sgn))
            # drag from the crotch down the inside of the thigh, in front
            cr = np.array([0.0, -0.02, 0.890])
            q = P - cr; rho = np.hypot(q[:, 0], q[:, 2]); ang = np.arctan2(-q[:, 2], q[:, 0] * sgn)
            front = _smoothstep(0.0, 0.03, -(y - 0.0))
            env = _smoothstep(0.03, 0.06, rho) * (1 - _smoothstep(0.13, 0.20, rho)) * front * side * (z < 0.89)
            F += 0.0020 * env * np.sin(7.0 * ang + 1.4 * _noise(P, 16.0, 7.0 + sgn))
        # gathered under the elastic waistband
        th = np.arctan2(x, y - 0.012)
        env = _smoothstep(0.985, 1.005, z) * (1 - _smoothstep(1.045, 1.060, z))
        F += 0.0015 * env * np.sin(th * 26.0 + 0.8 * _noise(P, 30.0, 9.0))
    P = P + Nn * (F * FOLD_SCALE)[:, None]
    # never closer to the skin than CLEAR: a fold's trough over a bulge, or
    # a drape direction that is not the surface's, could otherwise sink it
    pushed = 0
    if body is not None:
        from mathutils.bvhtree import BVHTree
        tb = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
        need = CLEAR.get(cut, CLEAR[kind])
        for i in range(n):
            loc, nrm, _, d = tb.find_nearest(Vector(P[i]))
            if loc is None: continue
            q = Vector(P[i]) - loc
            sd = d if q.dot(nrm) > 0 else -d
            if sd < need:
                P[i] = np.array(loc + nrm * need); pushed += 1
    me.vertices.foreach_set("co", P.reshape(-1)); me.update()
    return dict(pushed=pushed, moved=int((np.linalg.norm(D, axis=1) > 0.001).sum()), drape_max=float(np.linalg.norm(D, axis=1).max()),
                fold_max=float(np.abs(F).max()))


FURROW_MAX = {"tee": 0.001, "singlet": 0.001, "compression": 0.003}   # how far a top may follow the spinal furrow
TANK_HANG = 0.006         # a compression top stands at most this far off the waist at 1.14
JOGGER_FIT = ((0.52, 0.010), (0.70, 0.009))   # the jogger's median off the leg at the knee and the calf, at most


def check_cloth(tee, pants, body, assert_=True, top="tee", bottom="track"):
    """The clothes on the body, canonical, 2026-09-27 ("improve clothes"):

    the tee bridges the spinal furrow -- at 1.14 its back is no more than
    1 mm further in over the spine than 30 mm out (skin-tight it followed
    the furrow, 6 mm); how far it hangs off the waist at 1.14 is reported,
    not held -- 9.3 mm draped, 8.6 unfitted, too close to tell apart; no cloth closer to the skin
    than MIN_CLEAR (2 mm) anywhere; the trousers stack above the cuff
    -- down the front of each shin from 80 to 96 % of the leg, the cloth's
    distance off the bone line swings 2 mm or more (a tube: under 1); and
    no skirt -- in front of the crotch near the midline, from 0.80 to 0.90,
    no cloth more than 15 mm off the skin (10 clean; the drape run below the
    crotch hung a sheet across there, 29). Returns the numbers."""
    from mathutils.bvhtree import BVHTree
    def pts(o): return np.array([v.co[:] for v in o.data.vertices]) if o and len(o.data.vertices) else np.zeros((0, 3))
    T, Pn, Bd = pts(tee), pts(pants), pts(body)
    def back_y(Q, x, z):
        b = Q[(np.abs(np.abs(Q[:, 0]) - x) < 0.005) & (np.abs(Q[:, 2] - z) < 0.005) & (Q[:, 1] > 0)]
        return float(b[:, 1].max()) if len(b) else float("nan")
    def half(Q, z):
        b = Q[(np.abs(Q[:, 2] - z) < 0.004) & (np.abs(Q[:, 0]) < 0.20)]
        return float(np.abs(b[:, 0]).max()) if len(b) else float("nan")
    out = {}
    if len(T):
        out["tee_furrow"] = back_y(T, 0.030, 1.14) - back_y(T, 0.0, 1.14)
        out["tee_hang"] = half(T, 1.14) - half(Bd, 1.14)
    tb = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    worst = {}
    for kind, Q in (("tee", T), ("pants", Pn)):
        w = 1.0
        for q in Q[::3]:
            loc, nrm, _, d = tb.find_nearest(Vector(q))
            if loc is None: continue
            w = min(w, d if (Vector(q) - loc).dot(nrm) > 0 else -d)
        worst[kind] = w
    out["clear_tee"] = worst.get("tee", 1.0); out["clear_pants"] = worst["pants"]
    swing = []
    for sgn in (1, -1):
        hip = np.array(Jp("thigh_l")) * np.array([sgn, 1, 1]); ank = np.array(Jp("foot_l")) * np.array([sgn, 1, 1])
        ax = ank - hip; L = np.linalg.norm(ax); ax /= L
        t = (Pn - hip) @ ax / L
        c = hip + np.outer(t * L, ax); rv = Pn - c
        front = (rv[:, 1] < -0.02) & (np.abs(rv[:, 0]) < 0.012) & (t > 0.80) & (t < 0.96)
        if front.sum() < 10: swing.append(0.0); continue
        order = np.argsort(t[front]); r = np.linalg.norm(rv[front], axis=1)[order]; tt = t[front][order]
        bins = np.arange(0.80, 0.961, 0.004); prof = np.array([r[(tt >= a) & (tt < a + 0.004)].max() if ((tt >= a) & (tt < a + 0.004)).any() else np.nan for a in bins])
        prof = prof[~np.isnan(prof)]
        trend = np.convolve(prof, np.ones(9) / 9, mode="same")
        swing.append(float(np.max(prof[4:-4] - trend[4:-4]) - np.min(prof[4:-4] - trend[4:-4])) if len(prof) > 12 else 0.0)
    out["cuff_swing"] = min(swing)
    # a skirt is cloth spanning in front of the crotch between the thighs,
    # far off the skin (28.7 mm, the sabotage); behind, cloth hanging from
    # the seat rightly bridges the fold under it (23 mm, clean), and the
    # inner thighs nearly touch, so cloth near the midline is normal
    mid = Pn[(np.abs(Pn[:, 0]) < 0.010) & (Pn[:, 2] > 0.80) & (Pn[:, 2] < 0.90) & (Pn[:, 1] < -0.02)]
    span = 0.0
    for q in mid:
        loc, nrm, _, d = tb.find_nearest(Vector(q))
        if loc is not None: span = max(span, d)
    out["crotch_span"] = span
    # the jogger (2026-09-28): how far each leg stands off the skin at the
    # knee and the calf, the median over a ring of the leg
    if bottom == "jogger":
        for tq, _most in JOGGER_FIT:
            ds = []
            for sgn in (1, -1):
                hip = np.array(Jp("thigh_l")) * np.array([sgn, 1, 1]); ank = np.array(Jp("foot_l")) * np.array([sgn, 1, 1])
                ax = ank - hip; L = np.linalg.norm(ax); ax /= L
                t = (Pn - hip) @ ax / L
                for q in Pn[(np.abs(t - tq) < 0.015) & (Pn[:, 0] * sgn > 0.004)]:
                    loc, nrm, _, d = tb.find_nearest(Vector(q))
                    if loc is not None: ds.append(d)
            out["leg_off_%02d" % round(tq * 100)] = float(np.median(ds)) if ds else 1.0
    if not assert_:
        return out
    if len(T):
        fmax = FURROW_MAX[top]
        assert out["tee_furrow"] <= fmax, "skin-tight: the %s sinks %.1f mm into the spinal furrow, want %.0f at most" % (
            top, out["tee_furrow"] * 1000, fmax * 1000)
        if top == "compression":
            assert out["tee_hang"] <= TANK_HANG, "not compression: the tank stands %.1f mm off the waist, want %.0f at most" % (
                out["tee_hang"] * 1000, TANK_HANG * 1000)
    for kind in ("tee", "pants"):
        if kind in worst:
            assert worst[kind] >= MIN_CLEAR, "the %s goes %.1f mm from the skin (into it below 0), want %.0f" % (kind, worst[kind] * 1000, MIN_CLEAR * 1000)
    assert out["cuff_swing"] >= 0.002, "no folds: the trousers swing %.1f mm above the cuff, want 2" % (out["cuff_swing"] * 1000)
    assert out["crotch_span"] <= 0.015, "a skirt: cloth between the legs %.0f mm off the skin, want 15 at most" % (out["crotch_span"] * 1000)
    if bottom == "jogger":
        for tq, most in JOGGER_FIT:
            v = out["leg_off_%02d" % round(tq * 100)]
            assert v <= most, "not fitted: the joggers stand %.1f mm off the leg at %.0f %% of it, want %.0f at most" % (
                v * 1000, tq * 100, most * 1000)
    return out


def check_legs_apart(pants, crotch_z, assert_=True):
    """The trouser legs are two legs, on the man at his own size (the scan,
    2026-09-28): below the crotch no face of the trousers straddles the
    midline. The thug's size field once carried his legs inward through
    each other -- 155 faces across it, a web between his thighs that every
    clip stretched up to 63x. Returns (faces across, the nearest any
    trouser vertex below the crotch comes to the midline)."""
    me = pants.data
    if not len(me.polygons):
        return 0, 1.0
    below = crotch_z - 0.03 * crotch_z / 0.910     # 3 cm under the crotch, at the man's own size
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    across, where = 0, []
    for p in me.polygons:
        q = co[list(p.vertices)]
        if q[:, 2].mean() < below and q[:, 0].max() > 0.0005 and q[:, 0].min() < -0.0005:
            across += 1; where.append(q[:, 2].mean())
    low = co[co[:, 2] < below]
    gap = float(np.abs(low[:, 0]).min()) if len(low) else 1.0
    if assert_:
        assert across == 0, "the trouser legs run through each other: %d faces across the midline below the crotch (z %.3f-%.3f, the crotch at %.3f)" % (
            across, min(where), max(where), crotch_z)
    return across, gap


BARE_MOST = 0.02          # check_bare: the share of the outer upper arm a sleeveless top may cover


def check_bare(body, top, assert_=True):
    """A sleeveless top leaves the arms bare (2026-09-28): the body's faces
    on the outer half of each upper arm, from the shoulder joint to 35 % of
    the way to the elbow and within 0.11 m of its axis -- the deltoid, which
    the tank is there to show -- and a ray from each out along its normal
    must not meet the top within 20 mm; at most BARE_MOST of them may.
    Returns (covered, of)."""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    tb = BVHTree.FromObject(top, dg)
    me = body.data
    covered = of = 0
    for s in (1, -1):
        sh = Vector((Jp("upperarm_l").x * s, Jp("upperarm_l").y, Jp("upperarm_l").z))
        el = Vector((Jp("lowerarm_l").x * s, Jp("lowerarm_l").y, Jp("lowerarm_l").z))
        d = el - sh; L = d.length; d = d / L
        for p in me.polygons:
            c = p.center
            t = (c - sh).dot(d) / L
            if not (0.0 <= t <= 0.35): continue
            r = (c - sh) - d * ((c - sh).dot(d))
            if r.length > 0.11 or r.x * s <= 0.0: continue          # the outer half: away from the trunk
            of += 1
            hit = tb.ray_cast(c + p.normal * 0.0005, p.normal, 0.020)
            if hit[0] is not None: covered += 1
    if assert_:
        assert of and covered <= BARE_MOST * of, "sleeves: the %s covers %d of the %d outer upper-arm faces (%.0f %%), want %.0f %% at most" % (
            top.name, covered, of, 100.0 * covered / max(of, 1), BARE_MOST * 100)
    return covered, of


HOLE_REACH = 0.060        # a stripped face must have a garment (or his own skin) this near along its normal
HOLE_MOST = 0.0005        # ...all but this share of them


def check_holes(body, idx, garments, assert_=True):
    """No holes where the skin is stripped (2026-09-28): the body faces
    `idx` (pipeline.under_garments' strip) are deleted after the bind, and
    one with no garment over it would be a hole into the body. A stripped
    face is exposed unless a ray from it out along its normal meets a
    garment -- or his own skin -- within HOLE_REACH; at most HOLE_MOST
    (0.05 %) of them may be. The one rule for every top, sleeved or not.

    Measured on the fast builds before the reach was set: the rule as
    first written (a garment within 45 mm) failed every man in the track
    trousers and the tee -- AL-WAHSH 173 of 124,423 faces (0.14 %), AL-SAQR
    282 of 136,838 (0.21 %): under the seat, where the trousers bridge the
    fold, the faces looking down meet the cloth 45-58 mm off; in the
    armpit and between the thighs a face looks at his own skin, inside the
    cloth with it. At 60 mm, with his skin counted: AL-SAQR 45 (0.033 %),
    Saud 0; the tee's sleeve strip left on under a tank, 0.9-1.8 %.
    Returns (exposed, of)."""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    trees = [BVHTree.FromObject(g, dg) for g in list(garments) + [body] if len(g.data.polygons)]
    me = body.data
    exposed = 0
    for i in idx:
        p = me.polygons[i]
        o = p.center + p.normal * 0.0002
        if not any(t.ray_cast(o, p.normal, HOLE_REACH)[0] is not None for t in trees):
            exposed += 1
    n = max(len(idx), 1)
    if assert_:
        assert exposed <= HOLE_MOST * n, "holes: %d of the %d stripped body faces (%.3f %%) have no garment or skin within %.0f mm, want %.2f %% at most" % (
            exposed, len(idx), 100.0 * exposed / n, HOLE_REACH * 1000, HOLE_MOST * 100)
    return exposed, len(idx)


def stripped(c, top="tee", no_tee=False, seen=True):
    """Whether the body face at `c` (its centre, canonical coordinates) is
    under the garments and never seen, and so stripped (pipeline's
    under_garments; its history is there). The trousers' region from 0.16
    to 1.04; under a tee its trunk from 1.10 to 1.50 -- but not the skin
    within 12 cm round the neck above 1.45, where the collar stands off it
    -- and the top of each sleeve, the upper arm's first tenth (`seen`
    False: its first 0.30, and the neck with it, which is how the budget
    counts it); under a tank (2026-09-28) the tank's region shrunk 20 mm
    inside every edge, so a band of skin is kept under each, and no arm at
    all: a sleeveless top leaves the arm to be seen. `no_tee` (ZAYOS): the
    trousers only."""
    if no_tee:
        return 0.16 <= c.z <= 1.04 and pants_region(c)
    if 0.16 <= c.z <= 1.04 and pants_region(c):
        return True
    if top != "tee":
        return tank_region(c, top, margin=0.020)
    if (1.10 <= c.z <= 1.50 and abs(c.x) < 0.24 and tee_region(c)
            and not (seen and c.z > 1.45 and math.hypot(c.x, c.y - 0.004) < 0.12)):
        return True
    for s in (1, -1):
        sh = Vector((Jp("upperarm_l").x * s, Jp("upperarm_l").y, Jp("upperarm_l").z))
        el = Vector((Jp("lowerarm_l").x * s, Jp("lowerarm_l").y, Jp("lowerarm_l").z))
        t = (c - sh).dot(el - sh) / (el - sh).length_squared
        if -0.25 < t < (0.10 if seen else 0.30) and _pt_seg(c, sh, el) < 0.095 and c.z > 1.30:
            return True
    return False
