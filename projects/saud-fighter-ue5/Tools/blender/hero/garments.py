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

def dress(body, tee=True):
    """`tee=False` is ZAYOS (`look.tee: false`): shell() still runs, with
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
    t = shell(body, "Tee", tee_region if tee else (lambda c: False), 0.006, 0.0025, fold=0.0010, fold_size=0.16)
    pants = shell(body, "Pants", pants_region, 0.010, 0.003, fold=0.0012, fold_size=0.20)
    for g, kind in ((t, "tee"), (pants, "pants")):
        info = fit(g, kind, body)
        if info.get("moved"):
            print("cloth     : %-5s draped %d verts (up to %.0f mm), folds to %.1f mm, %d held off the skin"
                  % (kind, info["moved"], info["drape_max"] * 1000, info["fold_max"] * 1000, info["pushed"]))
    if check_cloth_in_dress:
        ck = check_cloth(t, pants, body)
        print("cloth     : " + "  ".join("%s %.4f" % kv for kv in ck.items()))
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
    # smooth the hang over neighbouring slices and angles: a slice's hull
    # jumps, and each vertex taking its own slice's value terraced the
    # cloth into horizontal ridges (the first preview)
    for _ in range(3):
        Hp = np.vstack([H[:1], H, H[-1:]])
        H = 0.25 * Hp[:-2] + 0.5 * Hp[1:-1] + 0.25 * Hp[2:]
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

def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0); return t * t * (3 - 2 * t)

def _noise(P, scale, seed):
    """A cheap smooth value: a few incommensurate sines, enough to break a
    fold's regularity without importing the texture noise."""
    x, y, z = P[:, 0] * scale, P[:, 1] * scale, P[:, 2] * scale
    return (np.sin(1.7 * x + 2.3 * z + seed) + np.sin(2.9 * y - 1.3 * z + 1.7 * seed)
            + np.sin(1.1 * x + 3.7 * y + 0.9 * z + 2.9 * seed)) / 3.0

CLEAR = {"tee": 0.0030, "pants": 0.0045}   # the closest cloth comes to the skin
FOLD_SCALE = 1.0          # the folds' amplitude, for the check's sabotage
PELVIS_Z = 0.93           # the seat's drape stops above the crotch (0.90)
MIN_CLEAR = 0.002         # check_cloth's floor, whatever CLEAR is set to
check_cloth_in_dress = True   # --cloth-check checks each dressing itself

def fit(g, kind, body=None):
    """Drape and fold one garment in place ("tee" or "pants"). Canonical
    positions (before a man's size). See the note above."""
    me = g.data
    n = len(me.vertices)
    if n == 0: return dict(moved=0)
    P = np.empty(n * 3); me.vertices.foreach_get("co", P); P = P.reshape(n, 3)
    D = np.zeros((n, 3))
    X = np.array([1.0, 0, 0]); Y = np.array([0, 1.0, 0]); Z = np.array([0, 0, 1.0])
    if kind == "tee":
        rows = A.TRUNK_ROWS
        zs = [r[0] for r in rows]; rx = np.interp(P[:, 2], zs, [r[2] for r in rows])
        trunk = np.nonzero((np.abs(P[:, 0]) < rx * 0.95) & (P[:, 2] < 1.40))[0]
        out = _drape_region(P, trunk, np.array([0.0, 0.004, 1.40]), -Z, X, Y, 0.006, slope=0.20)
        if len(out):
            grow, dirv = out
            w = 1.0 - _smoothstep(1.30, 1.37, P[trunk, 2])          # none under the arms
            D[trunk] += dirv * (grow * w)[:, None]
        # the sleeves: looser toward the cuff, and hanging off the arm
        for sgn in (1, -1):
            sh = np.array(Jp("upperarm_l")) * np.array([sgn, 1, 1]); el = np.array(Jp("lowerarm_l")) * np.array([sgn, 1, 1])
            d = el - sh; L = np.linalg.norm(d); d /= L
            t = (P - sh) @ d / L
            m = np.nonzero((P[:, 0] * sgn > rx * 0.95) & (t > -0.1) & (t < 0.5))[0]
            c = sh + np.outer(t[m] * L, d); rv = P[m] - c
            rn = rv / np.maximum(np.linalg.norm(rv, axis=1), 1e-9)[:, None]
            along = np.clip(t[m] / 0.40, 0, 1)
            loose = 0.002 + 0.007 * along + 0.004 * along * np.clip(-rn[:, 2], 0, 1)
            D[m] += rn * (loose * _smoothstep(-0.05, 0.10, t[m]))[:, None]
    else:
        # the seat and the hips: one hull a slice, over the cleft
        rows = A.TRUNK_ROWS
        # above the crotch (0.90) only: run below it, the hull spanned both
        # thighs and hung a skirt between the legs (the first preview)
        pel = np.nonzero(P[:, 2] >= PELVIS_Z)[0]
        out = _drape_region(P, pel, np.array([0.0, 0.012, 1.08]), -Z, X, Y, 0.006, slope=0.30, max_grow=0.020)
        wpel = _smoothstep(PELVIS_Z, PELVIS_Z + 0.04, P[pel, 2]) if len(pel) else None
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
            out = _drape_region(P, leg, hip, ax, u, v, 0.010, slope=0.16,
                                taper=lambda f: _smoothstep(0.86, 0.98, f), max_grow=0.025)
            if len(out):
                grow, dirv = out
                w = 1.0 - _smoothstep(0.82, 0.87, P[leg, 2])
                D[leg] += dirv * (grow * w)[:, None]
    P = P + D
    me.vertices.foreach_set("co", P.reshape(-1)); me.update()
    # ---- the folds, along the normals of the draped surface
    Nn = np.empty(n * 3); me.vertices.foreach_get("normal", Nn); Nn = Nn.reshape(n, 3)
    F = np.zeros(n)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    if kind == "tee":
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
        need = CLEAR[kind]
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


def check_cloth(tee, pants, body, assert_=True):
    """The clothes on the body, canonical, 2026-09-27 ("improve clothes"):

    the tee bridges the spinal furrow -- at 1.14 its back is no more than
    1 mm further in over the spine than 30 mm out (skin-tight it followed
    the furrow, 6 mm); it hangs off the waist -- at 1.14 it stands at least
    8 mm off the body's side (9; skin-tight: 6); no cloth closer to the skin
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
    if not assert_:
        return out
    if len(T):
        assert out["tee_furrow"] <= 0.001, "skin-tight: the tee sinks %.1f mm into the spinal furrow" % (out["tee_furrow"] * 1000)
        assert out["tee_hang"] >= 0.008, "skin-tight: the tee stands %.0f mm off the waist, want 8" % (out["tee_hang"] * 1000)
    for kind in ("tee", "pants"):
        if kind in worst:
            assert worst[kind] >= MIN_CLEAR, "the %s goes %.1f mm from the skin (into it below 0), want %.0f" % (kind, worst[kind] * 1000, MIN_CLEAR * 1000)
    assert out["cuff_swing"] >= 0.002, "no folds: the trousers swing %.1f mm above the cuff, want 2" % (out["cuff_swing"] * 1000)
    assert out["crotch_span"] <= 0.015, "a skirt: cloth between the legs %.0f mm off the skin, want 15 at most" % (out["crotch_span"] * 1000)
    return out
