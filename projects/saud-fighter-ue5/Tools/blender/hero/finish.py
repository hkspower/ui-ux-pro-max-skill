"""Stage 4-6: decimate to the budget, UVs, colour, bake, rig, export.

The look is painted by position, not by hand: a colour attribute on every
vertex -- skin, beard, brows, lips, nails, the wraps' tape, the trousers'
stripe, the flag patch -- computed from where the vertex is, then baked
through the UVs into the textures. So the textures come out of the same
numbers as the mesh, and re-proportioning him re-paints him."""
import bpy, bmesh, math, os, sys, time
import numpy as np
from mathutils import Vector, Matrix
import build_saud as legacy
from . import anatomy as A
J = legacy.J; Jp = A.Jp

# ------------------------------------------------------------ decimation
def decimate(obj, target_tris, protect, boundary_rings=0):
    """Collapse to the budget, protecting `protect(vertex)` regions (face,
    hands) which keep their density: the budget is spent where it shows.

    `boundary_rings` also protects the mesh's open edges and that many rings
    of vertices inside them. A garment is an open shell, and its hems and
    its collar are its silhouette: the tee went into the collapse at a ratio
    near 0.08 with nothing protected, so a collar of ~135 boundary vertices
    3.5 mm apart came out as about a dozen 4 cm segments -- the neckline in
    every render was a polygon, not a curve. Two rings of a ~135-vertex
    ring is a few hundred triangles."""
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    if tris <= target_tris: return tris
    vg = obj.vertex_groups.new(name="keep")
    keep = [v.index for v in obj.data.vertices if protect(v.co)]
    if boundary_rings:
        bm = bmesh.new(); bm.from_mesh(obj.data)
        ring = {v for v in bm.verts if any(e.is_boundary for e in v.link_edges)}
        seen = set(ring)
        for _ in range(boundary_rings - 1):
            ring = {o for v in ring for e in v.link_edges for o in (e.other_vert(v),) if o not in seen}
            seen |= ring
        keep = sorted(set(keep) | {v.index for v in seen})
        bm.free()
    if keep: vg.add(keep, 1.0, 'REPLACE')
    # The unprotected part must give up enough that the whole lands on target.
    kept_tris = 0
    keepset = set(keep)
    for p in obj.data.polygons:
        if all(i in keepset for i in p.vertices): kept_tris += len(p.vertices) - 2
    rest = max(1, tris - kept_tris)
    ratio = max(0.02, min(1.0, (target_tris - kept_tris * 0.55) / rest))
    d = obj.modifiers.new("Dec", "DECIMATE"); d.ratio = ratio
    d.vertex_group = "keep"; d.invert_vertex_group = True; d.vertex_group_factor = 10.0
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier="Dec")
    # protected zones at half density: a second, gentler pass on them.
    # The modifier's ratio is of the WHOLE mesh, and only the protected
    # vertices may collapse in this pass, so the ratio is the one that takes
    # 45 % of the protected triangles and nothing else. Until 2026-09-23 it
    # was a flat 0.55: 45 % of everything, taken out of the face alone --
    # harmless while the protected share was small, and on ZAYOS (no tee,
    # so a smaller budget, so the face most of what the first pass left)
    # it collapsed his face to 7 vertices in front and left him flat shards.
    if keep:
        g = obj.vertex_groups["keep"].index
        now = sum(len(p.vertices) - 2 for p in obj.data.polygons)
        prot = sum(len(p.vertices) - 2 for p in obj.data.polygons
                   if all(any(e.group == g and e.weight > 0.5 for e in obj.data.vertices[i].groups) for i in p.vertices))
        d2 = obj.modifiers.new("Dec2", "DECIMATE"); d2.ratio = max(0.02, 1.0 - 0.45 * prot / max(1, now))
        d2.vertex_group = "keep"; d2.vertex_group_factor = 10.0
        bpy.ops.object.modifier_apply(modifier="Dec2")
    obj.vertex_groups.remove(obj.vertex_groups["keep"])
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)

# ------------------------------------------------------------------- UVs
def _seg(name):
    a, b = name
    return Jp(a), Jp(b)

CHARTS = {
    # name: (region test on a point, projection, uv rect (u0,v0,u1,v1))
}

def cylinder_uv(p, a, b, front):
    """Angle round the axis a->b, and the fraction along it."""
    d = (b - a); L = d.length; d = d / L
    f = (front - d * front.dot(d)).normalized(); s = d.cross(f)
    q = p - a
    t = q.dot(d) / L
    ang = math.atan2(q.dot(s), q.dot(f))
    return ang, t

def assign_uvs(obj, charts, set_name="UVMap"):
    """charts: list of (test(point)->bool, kind, params, rect). The first
    chart whose test passes owns the face. Cylindrical charts unwrap the
    angle per face so the seam never splits a face."""
    bm = bmesh.new(); bm.from_mesh(obj.data)
    uv = bm.loops.layers.uv.get(set_name) or bm.loops.layers.uv.new(set_name)
    counts = {}
    for f in bm.faces:
        c = f.calc_center_median()
        chart = next((ch for ch in charts if ch[0](c)), charts[-1])
        test, kind, prm, (u0, v0, u1, v1) = chart
        counts[kind + str(prm[:1])] = counts.get(kind + str(prm[:1]), 0) + 1
        if kind == "cyl":
            a, b, front, tmin, tmax = prm
            base = None
            for l in f.loops:
                ang, t = cylinder_uv(l.vert.co, a, b, front)
                if base is None: base = ang
                while ang - base > math.pi: ang -= 2 * math.pi
                while ang - base < -math.pi: ang += 2 * math.pi
                u = (ang + math.pi) / (2 * math.pi)
                v = (t - tmin) / (tmax - tmin)
                l[uv].uv = (u0 + (u1 - u0) * (0.02 + 0.96 * u), v0 + (v1 - v0) * (0.02 + 0.96 * max(0.0, min(1.0, v))))
        else:  # planar: (origin, ax, ay, extent)
            o, ax, ay, ext = prm
            for l in f.loops:
                q = l.vert.co - o
                u = 0.5 + q.dot(ax) / ext; v = 0.5 + q.dot(ay) / ext
                l[uv].uv = (u0 + (u1 - u0) * max(0.0, min(1.0, u)), v0 + (v1 - v0) * max(0.0, min(1.0, v)))
    bm.to_mesh(obj.data); bm.free()
    return counts

def body_charts():
    F = Vector((0, -1, 0)); Z = Vector((0, 0, 1))
    hd = Jp("head"); nk = Jp("neck_01")
    def near(p, a, b, r):
        return A._point_to_segment(p, a, b) < r if hasattr(A, "_point_to_segment") else legacy._point_to_segment(p, a, b) < r
    def mirror(v, s): return Vector((v.x * s, v.y, v.z))
    charts = []
    # head: cylinder about the vertical through the skull, chin to crown
    charts.append((lambda c: c.z > 1.556 and (abs(c.x) < 0.11 or c.z > 1.60), "cyl",
                   (Vector((0, 0.0, 1.545)), Vector((0, 0.0, 1.840)), F, 0.0, 1.0), (0.00, 0.70, 0.50, 1.00)))
    # hands: planar, back and palm halves
    for s, rect_b, rect_p in ((1, (0.50, 0.00, 0.75, 0.25), (0.75, 0.00, 1.00, 0.25)), (-1, (0.50, 0.25, 0.75, 0.50), (0.75, 0.25, 1.00, 0.50))):
        wr = mirror(Jp("hand_l"), s); he = mirror(Jp("hand_end_l"), s); d = (he - wr).normalized()
        w = d.cross(F).normalized()
        o = wr + d * 0.10
        # 0.10, not 0.075: the thumb's outer faces lie up to 0.096 from the
        # segment and were unowned -- half of thumb_02 baked black on every
        # man. The along-axis clause keeps the forearm above the wrist on
        # its cylinder, which the wider radius would otherwise pull onto
        # the planar rect's edge.
        charts.append((lambda c, wr=wr, he=he, d=d: near(c, wr, he + (he - wr).normalized() * 0.12, 0.10) and (c - wr).dot(d) > -0.03 and c.y >= 0, "planar", (o, w, d, 0.26), rect_b))
    # arms: cylinder from the shoulder to the wrist
    for s, rect in ((1, (0.50, 0.50, 0.75, 1.00)), (-1, (0.75, 0.50, 1.00, 1.00))):
        a = mirror(Jp("upperarm_l"), s); b = mirror(Jp("hand_l"), s)
        charts.append((lambda c, a=a, b=b: near(c, a, b, 0.11) and c.z < 1.50, "cyl", (a - (b - a).normalized() * 0.05, b, F, 0.0, 1.0), rect))
    # feet: heel to toe, before the legs. Without a chart of their own the
    # toes fell past the leg cylinder's reach into the trunk's catch-all,
    # whose v clamps to 0 below the hips: every toe face mapped onto one
    # line and the shoe uppers had no texels. The rects overlap the skin's
    # in UV, which is harmless -- the shoe faces bake only into the shoe's
    # own images, and the soles keep their own quadrant (u > 0.5, v < 0.5).
    for s, rect in ((1, (0.00, 0.50, 0.50, 0.75)), (-1, (0.00, 0.75, 0.50, 1.00))):
        charts.append((lambda c, s=s: c.z < 0.14 and c.x * s > 0.02, "cyl",
                       (Vector((s * 0.082, 0.08, 0.06)), Vector((s * 0.082, -0.22, 0.06)), Z, 0.0, 1.0), rect))
    # legs: hip to ankle
    for s, rect in ((1, (0.00, 0.00, 0.25, 0.50)), (-1, (0.25, 0.00, 0.50, 0.50))):
        a = mirror(Jp("thigh_l"), s); b = mirror(Jp("foot_l"), s)
        charts.append((lambda c, a=a, b=b: near(c, a + Vector((0, 0, 0.08)), b - Vector((0, 0, 0.05)), 0.14) and c.z < 1.02, "cyl", (a + Vector((0, 0, 0.08)), b - Vector((0, 0, 0.06)), F, 0.0, 1.0), rect))
    # trunk: the rest above the hips. Mostly under the tee, so the small strip.
    charts.append((lambda c: True, "cyl", (Vector((0, 0.005, 0.86)), Vector((0, 0.005, 1.56)), F, 0.0, 1.0), (0.00, 0.50, 0.50, 0.70)))
    return charts

# --------------------------------------------------------------- colour
def srgb(h): h = h.lstrip('#'); return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])
def lin(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

# What was typed in paint() for Saud, before the roster read it out of the
# browser build instead: kept as the record of where the derived palette
# has to land for him (see palette_for and the test in build_fighters.py).
# band c8102e -> ff1a3c 2026-09-20, with assets/saud.js: the record moves with him.
# skin f0d8c4 -> bd9278 2026-09-24, with assets/saud.js: measured skin, not a
# Northern European's. face.SAUD_SKIN stays #f0d8c4 -- it is the skin the
# face's tones were WRITTEN on, and every tone is used as a ratio to it
# (face.shade's tone()), so it is a reference, not his colour.
_SAUD_PAINT = dict(skin='bd9278', hair='1e150f', tee='15171c', pants='0e1014', band='ff1a3c', shoe='101216')
from . import face as FA
assert FA.SAUD_SKIN == '#f0d8c4', "face.py's tones are ratios to the skin they were written on; change them together"

def palette_for(spec):
    """Linear colours and the kit for one fighter, from his roster entry.

    The browser build draws the beard as a translucent wash over the skin
    (`beard: 'rgba(24,17,12,.94)'`); a bake wants one colour, so it is
    composited over the skin here. The shoe is a touch off the trousers,
    as build_saud.PALETTE had it. Nothing in here is a colour somebody
    chose: it is the roster, read.
    """
    from . import roster
    c, look = spec["col"], spec["look"]
    beard = look.get("beard")
    # The wash's alpha, kept beside the composited colour: the colour is
    # what a .30 wash lands on the skin, but the shadow a beard casts and
    # the relief it adds are painted separately in hero.face, and at full
    # strength they gave light stubble a full beard's darkness under it --
    # a pencil moustache and a goatee on a man drawn with a shadow of growth.
    beard_k = roster.rgba_alpha(beard) if beard else 1.0
    # Bald and bearded are not opposites -- AL-WAHSH is both -- so a shaved
    # head does not, on its own, mean a shaved face. Only "no beard colour
    # given" means no beard.
    if beard:
        beard = roster.rgba_over(beard, c["skin"])
    else:
        beard = None
    hair = None if look.get("bald") else look.get("hair", "#1e150f")
    return dict(
        skin=lin(srgb(c["skin"])), hair=lin(srgb(hair)) if hair else None,
        beard=lin(srgb(beard)) if beard else None, beard_k=beard_k,
        tee=lin(srgb(c["top"])), pants=lin(srgb(c["bottom"])), band=lin(srgb(c["band"])),
        shoe=lin(srgb('101216')),
        lip=lin(srgb('c98a78')), tape=lin(srgb('e8e2d4')), nail=lin(srgb('f4dccb')),
        # the kit: what the browser lists for him and nothing it does not
        tape_on=(look.get("hands") == "wraps"), patch=bool(look.get("patch")),
        stripe=bool(look.get("stripe")), watch=bool(look.get("watch")),
        scar=bool(look.get("scar")), gloves=(look.get("hands") == "gloves"),
        bald=bool(look.get("bald")), no_tee=not look.get("tee", True),
        name=spec["name"])

def saud_palette():
    """Today's Saud, exactly as paint() used to spell him."""
    return dict(skin=lin(srgb(_SAUD_PAINT['skin'])), hair=lin(srgb(_SAUD_PAINT['hair'])),
                beard=lin(srgb('2a1d13')) * 0.9, beard_k=1.0,
                tee=lin(srgb(_SAUD_PAINT['tee'])), pants=lin(srgb(_SAUD_PAINT['pants'])),
                band=lin(srgb(_SAUD_PAINT['band'])), shoe=lin(srgb(_SAUD_PAINT['shoe'])),
                lip=lin(srgb('c98a78')), tape=lin(srgb('e8e2d4')), nail=lin(srgb('f4dccb')),
                tape_on=True, patch=True, stripe=True, watch=True, name="Saud")

# The kit's edges. Every mask below used to be a hard boolean on the
# vertices -- `col[inpatch] = green` -- and the bake interpolates vertex
# colour across each triangle, so a 48 x 30 mm flag patch, a 32 mm stripe,
# a wrap's turns and a collar rib all had edges that wandered by up to a
# vertex, 3 mm, and read as steps. The head never had this: hero.face is
# evaluated per TEXEL after the bake. This is the same move for the kit --
# one description of where the colour is, as smooth ramps a fraction of a
# texel wide, evaluated per vertex by paint() for the bake to start from and
# per texel by repaint_kit() for the edges. 0.6 mm is about a texel: the
# charts are cylinders, so a texel is not square -- the tee's v-texel is
# 0.85 mm and the pants' 0.43 (u 0.55 for both) -- and 0.6 lands an edge as
# one to two texels of blend either way. It is nothing at all at 3 mm
# between vertices.
KIT_FEATHER = 0.0006

def kit_colour(P, kind, pal, joints_l, base=None, parts=None):
    """Colour for positions P (N,3) of one material, linear, and how much of
    it is kit rather than the base (N,), 0..1. `base` is what to start from
    for the skin (the shaded body); the garments start from their own colour.
    Returns (rgb (N,3), kit (N,)). `parts`, a dict, gets the skin's tape
    and nail weights apart ("tape", "nail"), for the roughness."""
    from . import face as FA
    ramp = FA.ramp; f = KIT_FEATHER
    n = len(P)
    skin = pal["skin"]; hair = pal["hair"] if pal["hair"] is not None else skin
    tape = pal["tape"]; nail = pal["nail"]
    tee = pal["tee"]; pants = pal["pants"]; band = pal["band"]; shoe = pal["shoe"]
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    kit = np.zeros(n)
    if base is not None:
        col = np.array(base, dtype=float).reshape(n, 3).copy()
    else:
        col = np.tile(np.asarray({"skin": skin, "hair": hair, "shoe": shoe, "tee": tee, "pants": pants, "glove": band}[kind], dtype=float), (n, 1))

    def over(w, rgb):
        w = np.clip(w, 0.0, 1.0)
        col[:] = col * (1 - w)[:, None] + np.asarray(rgb, dtype=float)[None, :] * w[:, None]
        np.maximum(kit, w, out=kit)

    if kind == "skin":
        # hand wraps: tape from the wrist over the back of the hand and the knuckles
        for s in ((1, -1) if pal["tape_on"] else ()):
            wr = np.array(Jp("hand_l")) * np.array([s, 1, 1]); he = np.array(Jp("hand_end_l")) * np.array([s, 1, 1])
            d = (he - wr) / np.linalg.norm(he - wr)
            t = (P - wr) @ d; perp = np.linalg.norm((P - wr) - np.outer(t, d), axis=1)
            wrap = ramp(t, -0.045 - f, -0.045 + f) * ramp(t, 0.118 + f, 0.118 - f) * ramp(perp, 0.06 + f, 0.06 - f)
            # the tape is wound: bands along t, with a gap between turns
            turns = ((t + 0.045) / 0.011) % 1.0
            on = np.maximum(ramp(turns, 0.82 + f / 0.011, 0.82 - f / 0.011), ramp(t, f, -f))
            over(wrap * on, tape)
            if parts is not None:
                parts["tape"] = np.maximum(parts.get("tape", np.zeros(n)), np.clip(wrap * on, 0, 1))
        for s in (1, -1):
            # nails: the last 9 mm of each fingertip, the back side
            for fi, r in [("f%d" % i, 0.0085) for i in range(4)] + [("thumb", 0.0095)]:
                tip = np.array(joints_l[fi][-1]) * np.array([s, 1, 1])
                nw = ramp(np.linalg.norm(P - tip, axis=1), r + f, r - f) * ramp(y, tip[1] + 0.002 - f, tip[1] + 0.002 + f)
                over(nw, nail)
                if parts is not None:
                    parts["nail"] = np.maximum(parts.get("nail", np.zeros(n)), np.clip(nw, 0, 1))
    elif kind == "hair":
        # his colour (grey at the temples) in the cut's own texture, then
        # the fade -- skin showing through, face.hair_fade, shared with the
        # hairline band painted on the skin -- and a hard part if he has one
        col[:] = FA.hair_colour(P, hair) * FA.hair_texture(P)[:, None]
        over(FA.hair_fade(P), skin)
        over(FA.hair_part(P), skin)
        kit[:] = 1.0
    elif kind == "shoe":
        over(ramp(z, 0.022 + f, 0.022 - f), lin(srgb('2a2c30')))                       # the sole, a step lighter
        bars = ramp(z, 0.030 - f, 0.030 + f) * ramp(z, 0.050 + f, 0.050 - f) * ramp(y, -0.04 + f, -0.04 - f) * ramp(y, -0.16 - f, -0.16 + f)
        over(bars, lin(srgb('c9ccd2')))                                                  # the three bars
        kit[:] = 1.0
    elif kind == "tee":
        # the flag patch on the left breast, 48 x 30 mm, four bands
        px, pz, w, h = 0.044, 1.352, 0.048, 0.030
        if pal["patch"]:
            inpatch = ramp(np.abs(x - px), w / 2 + f, w / 2 - f) * ramp(np.abs(z - pz), h / 2 + f, h / 2 - f) * ramp(y, -0.06 + f, -0.06 - f)
            hoist = ramp(x, px + w / 2 - w * 0.27 - f, px + w / 2 - w * 0.27 + f)
            top = ramp(z, pz + h / 6 - f, pz + h / 6 + f); bot = ramp(z, pz - h / 6 + f, pz - h / 6 - f)
            over(inpatch * (1 - hoist) * top, lin(srgb('007a3d')))
            over(inpatch * (1 - hoist) * (1 - top) * (1 - bot), lin(srgb('f3f5f8')))
            over(inpatch * (1 - hoist) * bot, lin(srgb('c8102e')))
            over(inpatch * hoist, lin(srgb('101216')))
        # collar rib and hems a shade lighter, the stitching line
        over(ramp(z, 1.548 - f, 1.548 + f) * ramp(np.hypot(x, y - 0.004), 0.095 + f, 0.095 - f), np.asarray(tee) * 1.6)
        kit[:] = 1.0
    elif kind == "pants":
        over(ramp(z, 1.050 - f, 1.050 + f) * ramp(z, 1.076 + f, 1.076 - f), band)      # waistband
        # the stripe down the outer seam of each leg: track pants, not jeans
        for s in ((1, -1) if pal["stripe"] else ()):
            th = np.array(Jp("thigh_l")) * np.array([s, 1, 1]); ft = np.array(Jp("foot_l")) * np.array([s, 1, 1])
            d = (ft - th) / np.linalg.norm(ft - th); t = (P - th) @ d
            outer = (ramp(x * s, th[0] * s + 0.05 - f, th[0] * s + 0.05 + f) * ramp(t, 0.02 - f, 0.02 + f) * ramp(t, 0.97 + f, 0.97 - f)
                     * ramp(np.abs(y - (th[1] + (ft[1] - th[1]) * t)), 0.016 + f, 0.016 - f))
            over(outer, band)
        kit[:] = 1.0
    elif kind == "glove":
        # ZAYOS (`look.hands: 'gloves'`): a solid fill in his own accent
        # colour -- there is no dedicated glove-colour roster field, and
        # `band` is already the colour every other kit accent (waistband,
        # stripe, wraps) reads for a man, so a glove is no different.
        kit[:] = 1.0
    return col, kit


def paint(obj, kind, joints_l, pal=None):
    """A colour attribute per vertex, from position. The albedo bake reads it.
    `pal` is palette_for(spec); None is Saud as he was always painted."""
    pal = pal or saud_palette()
    me = obj.data
    n = len(me.vertices)
    P = np.empty(n * 3); me.vertices.foreach_get("co", P); P = P.reshape(n, 3)
    col = np.zeros((n, 4)); col[:, 3] = 1.0
    skin = pal["skin"]; hair = pal["hair"] if pal["hair"] is not None else skin; beard = pal["beard"]
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    if kind == "skin":
        col[:, :3] = skin
        # The head is painted by hero.face, which is also what repaint_head
        # evaluates per texel after the bake. One description, two
        # resolutions: this is the base the bake starts from, and at 3.1 mm
        # between vertices it can only carry the broad shapes -- the hairline,
        # the beard, the zones. The features finer than that arrive later.
        #
        # What this replaced was a set of masks that did not select what they
        # named. `|x| < 0.088` never bit at all, because the skull is 0.079
        # wide, so the beard ran round the back of his head; the two brow
        # Gaussians had sigma 26 mm at x = +-31 mm and summed to 0.96 at the
        # midline, so they were one bar across the forehead; and the
        # moustache was a hard rectangle reaching z = 1.636, which is over
        # the nostrils. See hero/face.py.
        from . import face as FA
        col[:, :3] = FA.body_grain(P, col[:, :3], skin=skin, joints_l=joints_l)
        col[:, :3], _rel, _on = FA.shade(P, skin, hair, beard, base_rgb=col[:, :3], beard_k=pal.get("beard_k", 1.0), scar=pal.get("scar", False))
        col[:, :3], _kit = kit_colour(P, "skin", pal, joints_l, base=col[:, :3])     # wraps, nails
    elif kind in ("hair", "shoe", "tee", "pants", "glove"):
        col[:, :3], _kit = kit_colour(P, kind, pal, joints_l)
    elif kind == "eye":
        # The broad strokes only. The iris is 11 mm across and the limbal ring
        # is 0.4 mm; the globe has 64 x 40 vertices, which is 2.8 by 4.5 deg,
        # so per vertex the pupil is about nine points and the limbus cannot
        # close into a ring at all. repaint_eye() does it in texels, the same
        # way the face is done. This is the base that bake starts from.
        c = P.mean(axis=0)
        f = np.array([0, -1, 0]); q = P - c; r = np.linalg.norm(q, axis=1) + 1e-9
        cosang = (q @ f) / r
        col[:, :3] = lin(srgb('f2efe8'))
        iris = cosang > 0.86; pupil = cosang > 0.975
        col[iris, :3] = lin(srgb('6d4a2a')); col[pupil, :3] = lin(srgb('050405'))
    attr = me.color_attributes.get("Col") or me.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
    attr.data.foreach_set("color", col.reshape(-1))
    return col

# --------------------------------------------------------------- shaders
# How far light travels under skin before it comes back out, per channel:
# Jensen, Marschner, Levoy & Hanrahan (2001), "A Practical Model for
# Subsurface Light Transport", skin 1, diffuse mean free path 3.67 / 1.37 /
# 0.68 mm in red / green / blue. The shader had (1.0, 0.25, 0.10) x 12 mm --
# red travelling 12 mm, three times as far as it does in a person -- which
# spread the red rim light across a third of his cheek as a pink glow and
# made the whole surface translucent wax. Skin's index is ~1.4 (dielectric
# F0 0.028), not the default 1.5. Renders only: the engine's importer makes
# its own material, and a Subsurface Profile there is still to be built.
SKIN_SCATTER_MM = (3.67, 1.37, 0.68)
SKIN_IOR = 1.40


def skin_scatter(mat, weight):
    """Measured scattering on a Principled BSDF, `weight` of the diffuse."""
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    red = SKIN_SCATTER_MM[0]
    bsdf.inputs["Subsurface Weight"].default_value = weight
    bsdf.inputs["Subsurface Radius"].default_value = tuple(c / red for c in SKIN_SCATTER_MM)
    bsdf.inputs["Subsurface Scale"].default_value = red / 1000.0
    if "IOR" in bsdf.inputs:
        bsdf.inputs["IOR"].default_value = SKIN_IOR


def shader(name, kind, roughness, sheen=0.0, metallic=0.0, subsurface=0.0, pores=0.0, weave=0.0, coat=0.0):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    nt = mat.node_tree; bsdf = nt.nodes["Principled BSDF"]
    attr = nt.nodes.new("ShaderNodeAttribute"); attr.attribute_name = "Col"
    nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if "Sheen Weight" in bsdf.inputs: bsdf.inputs["Sheen Weight"].default_value = sheen
    if subsurface and "Subsurface Weight" in bsdf.inputs:
        skin_scatter(mat, subsurface)
    if coat and "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = coat; bsdf.inputs["Coat Roughness"].default_value = 0.06
    if pores or weave:
        # The pore / weave bump, in METRES and above the texel. Unlinked,
        # a noise texture runs in Generated (bounding-box) coordinates, so
        # Scale 1400 over a 1.51 x 0.38 x 1.80 m body was a 1.08 x 0.27 x
        # 1.29 mm lattice -- anisotropic, and with Detail 6 its octaves ran
        # down to 0.02 mm against a 0.35 mm skin texel: the bake sampled it
        # once per texel and every normal map shipped as 66-82 % per-texel
        # white noise, which mips average to nothing. The body had no relief
        # at all. Object coordinates (the hi-res sources sit at the origin at
        # scale 1, so Object == metres), a 2.0 mm / 2.9 mm base period and
        # two octaves keep the second octave at 3.7 / 2.6 texels; Distance
        # up so the slope a coherent bump gives is the ~1.5 deg the old
        # dither's amplitude implied. Measured on a plane bake: lag-1
        # autocorrelation 0.008 -> 0.60 on the skin, -0.04 -> 0.35 on cloth.
        tc = nt.nodes.new("ShaderNodeTexCoord")
        noise = nt.nodes.new("ShaderNodeTexNoise")
        nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
        noise.inputs["Scale"].default_value = 500.0 if pores else 350.0
        noise.inputs["Detail"].default_value = 1.0
        noise.inputs["Roughness"].default_value = 0.5
        bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = pores or weave
        bump.inputs["Distance"].default_value = 0.0008
        nt.links.new(noise.outputs["Fac"], bump.inputs["Height"]); nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat

# ------------------------------------------------------------------ bake
def bake_set(obj, mat, size, out_dir, base, maps=("albedo", "normal", "roughness"), source=None, normal_size=None, images=None):
    """Bake one material's maps through the object's UVs. With `source` --
    the same surface before decimation, painted -- the colour and the
    normal come from it: the tape's edges, the patch, the sculpted face and
    the folds land in the textures at the source's resolution, not the
    game mesh's.

    `normal_size` bakes the normal map smaller than the colour. The shape
    the sculpt put in is low-frequency and survives it; the pore and weave
    bump is finer than a texel at the colour's resolution, so at full size
    it is stored as per-pixel dither the first mip level averages away --
    17.7 MB of it on the skin alone, against 3.2 MB at half.

    `images` -- the maps an earlier call of this made -- bakes INTO them
    without clearing, so a second object of the same material lands in its
    own charts of the same textures: the soles, which were painted and
    never baked, and shipped as black mirrors."""
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage"); nt.nodes.active = tex
    # the image node must be active in every material the bake touches
    src_nodes = []
    if source is not None:
        for sm in source.data.materials:
            if sm and sm is not mat:
                t2 = sm.node_tree.nodes.new("ShaderNodeTexImage"); sm.node_tree.nodes.active = t2; src_nodes.append((sm, t2))
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 1
    sc.render.bake.use_selected_to_active = source is not None
    # Baking INTO images an earlier call made (the soles into the shoe's)
    # must not clear them first. It did: use_clear defaults on, so each
    # sole's bake wiped the uppers, and the shoe uppers shipped with no
    # texels at all -- black colour, roughness 0, a mirror.
    sc.render.bake.use_clear = images is None
    sc.render.bake.use_cage = False
    sc.render.bake.cage_extrusion = 0.02
    sc.render.bake.max_ray_distance = 0.05
    sc.render.bake.margin = 8
    bpy.ops.object.select_all(action='DESELECT')
    if source is not None: source.select_set(True); source.hide_render = False
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    # only this material's faces bake into this image: hide the others by
    # making them unbake-able is not an option, so the image is shared and
    # each material's faces land in their own charts -- charts do not overlap
    # across materials because every material gets its own image.
    written = {}
    for m in maps:
        px = normal_size if (m == "normal" and normal_size) else size
        if images is not None:
            img = images[m]
        else:
            img = bpy.data.images.new("%s_%s" % (base, m), px, px, alpha=False, float_buffer=False)
            img.colorspace_settings.name = 'sRGB' if m == "albedo" else 'Non-Color'
            img.filepath_raw = os.path.join(out_dir, "T_%s_%s.png" % (base, {"albedo": "BaseColor", "normal": "Normal", "roughness": "Roughness"}[m]))
            img.file_format = 'PNG'
        tex.image = img
        for sm, t2 in src_nodes: t2.image = img
        s2a = source is not None
        if m == "albedo":
            # Cycles' diffuse colour pass includes the sheen closure's
            # albedo, which lifted every dark roster colour: Saud's tee
            # #15171c baked as (32,33,37) -- more than double in linear
            # light. The sheen is off for this one pass and put back.
            sheen = [(n, n.inputs["Sheen Weight"].default_value) for t in [nt] + [sm.node_tree for sm, _ in src_nodes]
                     for n in t.nodes if n.type == "BSDF_PRINCIPLED"]
            for n, _ in sheen: n.inputs["Sheen Weight"].default_value = 0.0
            bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, margin=8, use_selected_to_active=s2a, cage_extrusion=0.02, max_ray_distance=0.05)
            for n, v in sheen: n.inputs["Sheen Weight"].default_value = v
        elif m == "normal": bpy.ops.object.bake(type='NORMAL', margin=8, use_selected_to_active=s2a, cage_extrusion=0.02, max_ray_distance=0.05)
        else: bpy.ops.object.bake(type='ROUGHNESS', margin=8, use_selected_to_active=s2a, cage_extrusion=0.02, max_ray_distance=0.05)
        img.save()
        written[m] = img
    nt.nodes.remove(tex)
    for sm, t2 in src_nodes: sm.node_tree.nodes.remove(t2)
    return written

def wire_textures(mat, imgs):
    """Replace the procedural inputs with the baked maps, so the exported
    material is what an engine reads: colour, roughness, normal."""
    nt = mat.node_tree; bsdf = nt.nodes["Principled BSDF"]
    for l in list(nt.links):
        if l.to_node == bsdf and l.to_socket.name in ("Base Color", "Roughness", "Normal"): nt.links.remove(l)
    for n in [n for n in nt.nodes if n.type in ("ATTRIBUTE", "TEX_NOISE", "BUMP")]: nt.nodes.remove(n)
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = imgs["albedo"]; nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
    if "roughness" in imgs:
        r = nt.nodes.new("ShaderNodeTexImage"); r.image = imgs["roughness"]; nt.links.new(r.outputs["Color"], bsdf.inputs["Roughness"])
    if "normal" in imgs:
        nrm = nt.nodes.new("ShaderNodeTexImage"); nrm.image = imgs["normal"]
        nm = nt.nodes.new("ShaderNodeNormalMap"); nt.links.new(nrm.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])


# ------------------------------------------------- the face, in texel space
def rasterise(obj, size, keep):
    """Where every texel of `obj`'s chart sits in space.

    The bake carries a vertex colour through the UVs, so the finest thing it
    can express is the distance between two vertices -- 3.1 mm on the head,
    against a 0.9 mm texel. Rasterising the chart ourselves gives the texel's
    own position, and the face can then be painted at the texture's
    resolution instead of the mesh's.

    Returns (pos[size, size, 3], covered[size, size]) in Blender's row order,
    so row 0 is v = 0, matching image.pixels.
    """
    me = obj.data
    me.calc_loop_triangles()
    uvl = me.uv_layers.active.data
    nv = len(me.vertices)
    V = np.empty(nv * 3); me.vertices.foreach_get("co", V); V = V.reshape(nv, 3)
    pos = np.zeros((size, size, 3)); cov = np.zeros((size, size), dtype=bool)
    for tri in me.loop_triangles:
        vi = tri.vertices; li = tri.loops
        p = V[list(vi)]
        if not keep(p.mean(axis=0)):
            continue
        uv = np.array([uvl[i].uv[:] for i in li]) * size
        x0 = max(0, int(np.floor(uv[:, 0].min())) - 1); x1 = min(size, int(np.ceil(uv[:, 0].max())) + 2)
        y0 = max(0, int(np.floor(uv[:, 1].min())) - 1); y1 = min(size, int(np.ceil(uv[:, 1].max())) + 2)
        if x1 <= x0 or y1 <= y0:
            continue
        ys, xs = np.mgrid[y0:y1, x0:x1]
        px = xs + 0.5; py = ys + 0.5
        (ax, ay), (bx, by), (cx, cy) = uv
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        w0 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / den
        w1 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / den
        w2 = 1.0 - w0 - w1
        inside = (w0 >= 0.0) & (w1 >= 0.0) & (w2 >= 0.0)
        if not inside.any():
            continue
        q = (w0[..., None] * p[0] + w1[..., None] * p[1] + w2[..., None] * p[2])
        sel = inside & ~cov[y0:y1, x0:x1]
        blk = pos[y0:y1, x0:x1]; blk[sel] = q[sel]
        cov[y0:y1, x0:x1] |= inside
    return pos, cov


def _srgb_to_linear(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def _img_array(img):
    a = np.empty(len(img.pixels), dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(img.size[1], img.size[0], 4)


def _img_write(img, a):
    img.pixels.foreach_set(a.astype(np.float32).reshape(-1))
    img.update()
    img.save()


def _dilate(a, cov, rounds=3):
    """Grow the painted region outward, so a texel the rasteriser missed at a
    chart's edge does not show as a hole when the mip levels average it."""
    out = a.copy(); have = cov.copy()
    for _ in range(rounds):
        nxt = have.copy()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sh = np.roll(have, (dy, dx), (0, 1))
            sv = np.roll(out, (dy, dx), (0, 1))
            fill = sh & ~nxt
            out[fill] = sv[fill]; nxt |= sh
        have = nxt
    return out


def repaint_head(obj, imgs, size, pal=None):
    """Repaint the head's texels from hero.face, and turn its relief into
    normal and roughness. Everything below 3 mm -- the lash line, the
    vermilion border, a nostril rim, the edge of a brow -- exists only here.
    `pal` is palette_for(spec); None is Saud.
    """
    from . import face as FA
    pal = pal or saud_palette()
    coherent = 0.0
    pos, cov = rasterise(obj, size, lambda c: c[2] > 1.535)
    if not cov.any():
        return 0, coherent
    P = pos[cov]
    skin = pal["skin"]; hair = pal["hair"] if pal["hair"] is not None else skin
    beard = pal["beard"]
    # ---- albedo
    # A byte image's `pixels` are the stored bytes over 255 -- sRGB-encoded,
    # not linear (checked: writing 0.5 stores 128).
    alb = _img_array(imgs["albedo"])
    lin = _srgb_to_linear(alb[..., :3])
    # Start from what the bake put there rather than from flat skin. Where
    # shade() feathers out -- down the neck, round the back of the head --
    # it lays a fraction of the face over its base, and if that base were
    # flat skin the body's own grain would be wiped out across exactly the
    # band where the head and the body have to meet.
    extra = {}
    rgb, rel, on = FA.shade(P, skin, hair, beard, base_rgb=lin[cov], beard_k=pal.get("beard_k", 1.0), scar=pal.get("scar", False), out=extra)
    live = on > 0.002
    if not live.any():
        return 0, coherent
    buf = np.zeros(pos.shape); buf[cov] = rgb
    m = np.zeros(cov.shape, bool); m[cov] = live
    lin[m] = buf[m]
    alb[..., :3] = _linear_to_srgb(lin)
    _img_write(imgs["albedo"], _dilate(alb, m, 3))

    # ---- relief -> normal, at the normal map's own size
    if "normal" in imgs:
        nsz = imgs["normal"].size[0]
        H = np.zeros(cov.shape); H[cov] = rel
        Hm = np.zeros(cov.shape); Hm[cov] = on
        if nsz != size:
            # Averaged over the COVERED texels only. A plain box mean folds
            # the zeros of uncovered texels into the block, which at a
            # chart's edge drags the position toward the origin and invents
            # a cliff in the normal map.
            k = size // nsz
            w = cov.reshape(nsz, k, nsz, k).astype(np.float64)
            n = w.sum((1, 3))
            safe = np.maximum(n, 1.0)
            H = (H.reshape(nsz, k, nsz, k) * w).sum((1, 3)) / safe
            Hm = (Hm.reshape(nsz, k, nsz, k) * w).sum((1, 3)) / safe
            Pn = (pos.reshape(nsz, k, nsz, k, 3) * w[..., None]).sum((1, 3)) / safe[..., None]
            Cn = n >= (k * k)                 # only blocks that are wholly inside
        else:
            Pn, Cn = pos, cov
        # world metres per texel, from the chart itself
        du = np.gradient(Pn, axis=1); dv = np.gradient(Pn, axis=0)
        su = np.linalg.norm(du, axis=2); sv = np.linalg.norm(dv, axis=2)
        good = Cn & (su > 1e-5) & (sv > 1e-5) & (su < 0.02) & (sv < 0.02)
        dhu = np.gradient(H, axis=1); dhv = np.gradient(H, axis=0)
        slope_u = np.where(good, dhu / np.maximum(su, 1e-6), 0.0)
        slope_v = np.where(good, dhv / np.maximum(sv, 1e-6), 0.0)
        nrm = _img_array(imgs["normal"])
        n0 = nrm[..., :3] * 2.0 - 1.0
        nz = np.where(np.abs(n0[..., 2]) < 1e-3, 1e-3, n0[..., 2])
        s0u = -n0[..., 0] / nz; s0v = -n0[..., 1] / nz
        tu = s0u + np.clip(slope_u, -6.0, 6.0); tv = s0v + np.clip(slope_v, -6.0, 6.0)
        n = np.stack([-tu, -tv, np.ones_like(tu)], axis=-1)
        n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-9)
        use = good & (Hm > 0.002)
        nrm[..., :3] = np.where(use[..., None], n * 0.5 + 0.5, nrm[..., :3])
        _img_write(imgs["normal"], _dilate(nrm, use, 3))
        # Did the relief actually land? Structure finer than a texel averages
        # to noise, and noise and a flat map look the same in a histogram --
        # so measure what SURVIVES a 4x4 box mean. Pure per-texel dither of
        # standard deviation s falls to s/4; anything coherent does not.
        fb = (nrm[..., 1] * 255.0)[use.any(1)][:, use.any(0)]
        if fb.size > 64:
            k = 4; hh, ww = (fb.shape[0] // k) * k, (fb.shape[1] // k) * k
            if hh and ww:
                coherent = float(fb[:hh, :ww].reshape(hh // k, k, ww // k, k).mean((1, 3)).std())

    # ---- roughness: a face is not one finish. The T-zone is oily and the
    # cheeks are not; lips are wetter than either; a brow is matt.
    if "roughness" in imgs:
        rough = _img_array(imgs["roughness"])
        z = P[:, 2]; ax = np.abs(P[:, 0])
        tzone = FA.ramp(z, FA.EYE_Z + 0.003, FA.EYE_Z + 0.041) + FA.blob(P, 0.0, FA.NOSE_Z + 0.016, 0.013, 0.016, mirror=False)
        cheek = FA.blob(P, 0.050, FA.NOSE_Z + 0.019, 0.026, 0.022)
        lipw = FA.ramp(z, FA.MOUTH_Z - 0.0143, FA.MOUTH_Z - 0.0093) * FA.ramp(z, FA.MOUTH_Z + 0.0097, FA.MOUTH_Z + 0.0057) * FA.ramp(ax, 0.028, 0.022)
        r = (0.56
             - 0.16 * np.clip(tzone, 0, 1)
             + 0.07 * np.clip(cheek, 0, 1)
             - 0.26 * np.clip(lipw, 0, 1)
             + 0.05 * (FA.fbm(P, 700.0, 3, 61.0) - 0.5)
             # the band above the hairline that is skin material painted
             # hair (assembly.HAIR_MARGIN): as matt as the hair material
             # it meets, 0.52, not the T-zone's 0.40 -- but only where
             # there is hair to meet: a bald man has no hair material
             # anywhere, and this band would be an unexplained matte
             # horseshoe on an otherwise uniform scalp
             + (0.12 * FA.hairline_weight(P) if pal["hair"] is not None else 0.0)
             # stubble breaks up the skin's sheen: a shaved jaw is never as
             # glossy as the cheek above it
             + 0.12 * extra.get("beard", 0.0))
        r = np.clip(r, 0.18, 0.80)
        buf = np.zeros(cov.shape); buf[cov] = r
        rough[..., :3] = np.where(m[..., None], buf[..., None], rough[..., :3])
        _img_write(imgs["roughness"], _dilate(rough, m, 3))
    return int(m.sum()), coherent


def repaint_kit(obj, kind, imgs, size, pal, joints_l, keep=None):
    """Repaint the kit's texels from kit_colour, the way repaint_head does
    the face: the bake carried the vertex colour across each triangle, so
    the patch, the stripe, the waistband, the wraps' turns and the collar
    rib had edges that stepped by up to a vertex (3 mm). Evaluated per
    texel they are a texel wide. The garments are recoloured whole (their
    kit mask is 1 everywhere, so a texel the bake's rays missed is filled
    too); the skin only where the tape and the nails are. `keep` limits
    the triangles rasterised, e.g. to the hands. Returns texels written."""
    from . import face as FA
    pos, cov = rasterise(obj, size, keep or (lambda c: True))
    if not cov.any():
        return 0
    P = pos[cov]
    alb = _img_array(imgs["albedo"])
    lin_ = _srgb_to_linear(alb[..., :3])
    # Not from the baked image: that carried the per-vertex paint's bleed
    # (3-5 mm ramps either side of every kit edge), and a repaint that
    # starts from it keeps the bleed outside the feathered edge it draws.
    # The garments rebuild whole from their own colour; the skin from its
    # grain, evaluated per texel here as paint() evaluated it per vertex,
    # so the body's pores are 0.35 mm, not 3 mm.
    parts = {}
    if kind == "skin":
        base = FA.body_grain(P, np.tile(np.asarray(pal["skin"], dtype=float), (len(P), 1)),
                             skin=pal["skin"], joints_l=joints_l)
        rgb, kit = kit_colour(P, kind, pal, joints_l, base=base, parts=parts)
        live = np.ones(len(P), bool)
    else:
        rgb, kit = kit_colour(P, kind, pal, joints_l)
        live = kit > 0.002
    if not live.any():
        return 0
    buf = np.zeros(pos.shape); buf[cov] = rgb
    m = np.zeros(cov.shape, bool); m[cov] = live
    lin_[m] = buf[m]
    alb[..., :3] = _linear_to_srgb(lin_)
    _img_write(imgs["albedo"], _dilate(alb, m, 3))
    # The skin's roughness, per texel: it was the shader's one number baked
    # flat over the whole body (FA.body_roughness says why that is the
    # plastic look). Cotton tape is matt and a nail is glossy keratin; both
    # sat at the skin's 0.52. The face is refined over this by repaint_head.
    if kind == "skin" and "roughness" in imgs:
        r = FA.body_roughness(P, joints_l)
        tape_w = parts.get("tape", np.zeros(len(P))); nail_w = parts.get("nail", np.zeros(len(P)))
        r = r * (1 - tape_w) + 0.82 * tape_w
        r = r * (1 - nail_w) + 0.30 * nail_w
        rough = _img_array(imgs["roughness"])
        rb = np.zeros(cov.shape); rb[cov] = r
        rough[..., :3] = np.where(m[..., None], rb[..., None], rough[..., :3])
        _img_write(imgs["roughness"], _dilate(rough, m, 3))
    return int(m.sum())


# --------------------------------------------------------------- the eye
# A brown Gulf iris, its dark limbal ring, and the fibres in it. All of it is
# finer than the globe's vertex grid, so like the face it is painted per
# texel after the bake rather than per vertex before it.
IRIS_R = 0.00565       # 11.3 mm across, which is a human iris
PUPIL_R = 0.00205      # 4.1 mm, an iris-to-pupil ratio of about 2.8
LIMBUS = 0.00042       # the dark ring at the iris's edge

def repaint_eye(obj, imgs, size, centre, radius):
    """Sclera, limbus, iris and pupil, at the texture's resolution."""
    from . import face as FA
    pos, cov = rasterise(obj, size, lambda c: True)
    if not cov.any():
        return 0
    P = pos[cov]
    q = P - np.asarray(centre)
    r = np.maximum(np.linalg.norm(q, axis=1), 1e-9)
    cosang = np.clip((q @ np.array([0.0, -1.0, 0.0])) / r, -1.0, 1.0)
    # distance from the corneal pole, along the sphere, in metres
    d = radius * np.arccos(np.clip(cosang, -1.0, 1.0))
    ang = np.arctan2(q[:, 2], q[:, 0])

    sclera = FA.hex_lin('f0ece3')
    iris_c = FA.hex_lin('6d4a2a')
    iris_hi = FA.hex_lin('9a6c3c')
    limb = FA.hex_lin('2a1c12')
    rgb = np.tile(sclera, (len(P), 1))
    # the sclera is not white: it is warmer and darker toward the corners,
    # and carries a faint vascular tint
    corner = np.clip((d - IRIS_R) / 0.008, 0.0, 1.0)
    rgb *= (1.0 - 0.22 * corner)[:, None]
    rgb = rgb * (1 - (0.10 * corner)[:, None]) + FA.hex_lin('d9b6a6')[None, :] * (0.10 * corner)[:, None]

    # iris: radial fibre, brighter toward the limbus, darker at the pupil
    t = np.clip(d / IRIS_R, 0.0, 1.0)
    fibre = 0.86 + 0.28 * np.cos(17.0 * ang) * (0.35 + 0.65 * t)
    iris = iris_c[None, :] * fibre[:, None] + (iris_hi - iris_c)[None, :] * (t ** 2.2)[:, None] * 0.55
    iris *= (0.55 + 0.45 * FA.smooth((t - 0.16) / 0.22))[:, None]      # dark collarette
    w = FA.ramp(d, IRIS_R + 0.00030, IRIS_R - 0.00030)[:, None]
    rgb = rgb * (1 - w) + np.clip(iris, 0, 1) * w
    # the limbal ring
    lw = (np.exp(-0.5 * ((d - (IRIS_R - LIMBUS * 0.5)) / LIMBUS) ** 2) * 0.85)[:, None]
    rgb = rgb * (1 - lw) + limb[None, :] * lw
    # the pupil, genuinely black so the eye has a direction
    pw = FA.ramp(d, PUPIL_R + 0.00022, PUPIL_R - 0.00022)[:, None]
    rgb = rgb * (1 - pw) + FA.hex_lin('040305')[None, :] * pw

    alb = _img_array(imgs["albedo"])
    buf = np.zeros(pos.shape); buf[cov] = np.clip(rgb, 0.0, 1.0)
    lin_ = _srgb_to_linear(alb[..., :3])
    lin_[cov] = buf[cov]
    alb[..., :3] = _linear_to_srgb(lin_)
    _img_write(imgs["albedo"], _dilate(alb, cov, 3))

    # Only the cornea is wet. The sclera is matt tissue sitting in the upper
    # lid's shadow; one gloss over the whole ball is why it read as a bead.
    if "roughness" in imgs:
        rough = _img_array(imgs["roughness"])
        rr = np.where(d < IRIS_R + 0.0013, 0.05, 0.38)
        buf = np.zeros(cov.shape); buf[cov] = rr
        rough[..., :3] = np.where(cov[..., None], buf[..., None], rough[..., :3])
        _img_write(imgs["roughness"], _dilate(rough, cov, 3))
    return int(cov.sum())