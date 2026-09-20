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
def decimate(obj, target_tris, protect):
    """Collapse to the budget, protecting `protect(vertex)` regions (face,
    hands) which keep their density: the budget is spent where it shows."""
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    if tris <= target_tris: return tris
    vg = obj.vertex_groups.new(name="keep")
    keep = [v.index for v in obj.data.vertices if protect(v.co)]
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
    # protected zones at half density: a second, gentler pass on them
    if keep:
        d2 = obj.modifiers.new("Dec2", "DECIMATE"); d2.ratio = 0.55; d2.vertex_group = "keep"; d2.vertex_group_factor = 10.0
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
_SAUD_PAINT = dict(skin='f0d8c4', hair='1e150f', tee='15171c', pants='0e1014', band='c8102e', shoe='101216')
from . import face as FA
assert '#' + _SAUD_PAINT['skin'] == FA.SAUD_SKIN, "face.py's tones are written on a skin that is not Saud's"

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
    if beard and not look.get("bald"):
        beard = roster.rgba_over(beard, c["skin"])
    else:
        beard = None
    hair = None if look.get("bald") else look.get("hair", "#1e150f")
    return dict(
        skin=lin(srgb(c["skin"])), hair=lin(srgb(hair)) if hair else None,
        beard=lin(srgb(beard)) if beard else None,
        tee=lin(srgb(c["top"])), pants=lin(srgb(c["bottom"])), band=lin(srgb(c["band"])),
        shoe=lin(srgb('101216')),
        lip=lin(srgb('c98a78')), tape=lin(srgb('e8e2d4')), nail=lin(srgb('f4dccb')),
        # the kit: what the browser lists for him and nothing it does not
        tape_on=(look.get("hands") == "wraps"), patch=bool(look.get("patch")),
        stripe=bool(look.get("stripe")), watch=bool(look.get("watch")),
        name=spec["name"])

def saud_palette():
    """Today's Saud, exactly as paint() used to spell him."""
    return dict(skin=lin(srgb(_SAUD_PAINT['skin'])), hair=lin(srgb(_SAUD_PAINT['hair'])),
                beard=lin(srgb('2a1d13')) * 0.9,
                tee=lin(srgb(_SAUD_PAINT['tee'])), pants=lin(srgb(_SAUD_PAINT['pants'])),
                band=lin(srgb(_SAUD_PAINT['band'])), shoe=lin(srgb(_SAUD_PAINT['shoe'])),
                lip=lin(srgb('c98a78')), tape=lin(srgb('e8e2d4')), nail=lin(srgb('f4dccb')),
                tape_on=True, patch=True, stripe=True, watch=True, name="Saud")

def paint(obj, kind, joints_l, pal=None):
    """A colour attribute per vertex, from position. The albedo bake reads it.
    `pal` is palette_for(spec); None is Saud as he was always painted."""
    pal = pal or saud_palette()
    me = obj.data
    n = len(me.vertices)
    P = np.empty(n * 3); me.vertices.foreach_get("co", P); P = P.reshape(n, 3)
    col = np.zeros((n, 4)); col[:, 3] = 1.0
    skin = pal["skin"]; hair = pal["hair"] if pal["hair"] is not None else skin; beard = pal["beard"]
    lip = pal["lip"]; tape = pal["tape"]; nail = pal["nail"]
    tee = pal["tee"]; pants = pal["pants"]; band = pal["band"]; shoe = pal["shoe"]
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
        col[:, :3] = FA.body_grain(P, col[:, :3])
        col[:, :3], _rel, _on = FA.shade(P, skin, hair, beard, base_rgb=col[:, :3])
        # hand wraps: tape from the wrist over the back of the hand and the knuckles
        for s in ((1, -1) if pal["tape_on"] else ()):
            wr = np.array(Jp("hand_l")) * np.array([s, 1, 1]); he = np.array(Jp("hand_end_l")) * np.array([s, 1, 1])
            d = (he - wr) / np.linalg.norm(he - wr)
            t = (P - wr) @ d; perp = np.linalg.norm((P - wr) - np.outer(t, d), axis=1)
            wrap = (t > -0.045) & (t < 0.118) & (perp < 0.06)
            # the tape is wound: bands along t, with a gap between turns
            turns = ((t + 0.045) / 0.011) % 1.0
            band_on = wrap & ((turns < 0.82) | (t < 0.0))
            col[band_on, :3] = tape
        for s in (1, -1):
            # nails: the last 9 mm of each fingertip, the back side
            for fi in range(4):
                tip = np.array(joints_l["f%d" % fi][-1]) * np.array([s, 1, 1])
                nl = (np.linalg.norm(P - tip, axis=1) < 0.0085) & (y > tip[1] + 0.002)
                col[nl, :3] = nail
            tip = np.array(joints_l["thumb"][-1]) * np.array([s, 1, 1])
            nl = (np.linalg.norm(P - tip, axis=1) < 0.0095) & (y > tip[1] + 0.002)
            col[nl, :3] = nail
    elif kind == "hair":
        col[:, :3] = hair
        # faded sides: lighter (skin showing through) low on the sides
        fade = np.clip((0.070 - (1.76 - z)) / 0.05, 0, 1) * np.clip((np.abs(x) - 0.045) / 0.03, 0, 1)
        col[:, :3] = col[:, :3] * (1 - 0.55 * fade[:, None]) + skin[None, :] * 0.55 * fade[:, None]
    elif kind == "shoe":
        col[:, :3] = shoe
        col[(z < 0.022), :3] = lin(srgb('2a2c30'))   # the sole, a step lighter
        stripe = (z > 0.030) & (z < 0.050) & (y < -0.04) & (y > -0.16)
        col[stripe, :3] = lin(srgb('c9ccd2'))          # the three bars
    elif kind == "tee":
        col[:, :3] = tee
        # the flag patch on the left breast, 48 x 30 mm, four bands
        px, pz, w, h = 0.044, 1.352, 0.048, 0.030
        inpatch = (np.abs(x - px) < w / 2) & (np.abs(z - pz) < h / 2) & (y < -0.06)
        if not pal["patch"]: inpatch[:] = False
        hoist = inpatch & (x > px + w / 2 - w * 0.27)
        rest = inpatch & ~hoist
        col[rest & (z > pz + h / 6), :3] = lin(srgb('007a3d'))
        col[rest & (np.abs(z - pz) <= h / 6), :3] = lin(srgb('f3f5f8'))
        col[rest & (z < pz - h / 6), :3] = lin(srgb('c8102e'))
        col[hoist, :3] = lin(srgb('101216'))
        # collar rib and hems a shade lighter, the stitching line
        collar = (z > 1.548) & (np.hypot(x, y - 0.004) < 0.095)
        col[collar, :3] = tee * 1.6
    elif kind == "pants":
        col[:, :3] = pants
        wb = (z > 1.050) & (z < 1.076); col[wb, :3] = band
        # the stripe down the outer seam of each leg: track pants, not jeans
        for s in ((1, -1) if pal["stripe"] else ()):
            th = np.array(Jp("thigh_l")) * np.array([s, 1, 1]); ft = np.array(Jp("foot_l")) * np.array([s, 1, 1])
            d = (ft - th) / np.linalg.norm(ft - th); t = (P - th) @ d
            outer = (x * s > th[0] * s + 0.05) & (t > 0.02) & (t < 0.97) & (np.abs(y - (th[1] + (ft[1] - th[1]) * t)) < 0.016)
            col[outer, :3] = band
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
def shader(name, kind, roughness, sheen=0.0, metallic=0.0, subsurface=0.0, pores=0.0, weave=0.0, coat=0.0):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    nt = mat.node_tree; bsdf = nt.nodes["Principled BSDF"]
    attr = nt.nodes.new("ShaderNodeAttribute"); attr.attribute_name = "Col"
    nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if "Sheen Weight" in bsdf.inputs: bsdf.inputs["Sheen Weight"].default_value = sheen
    if subsurface and "Subsurface Weight" in bsdf.inputs:
        bsdf.inputs["Subsurface Weight"].default_value = subsurface
        bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.25, 0.10); bsdf.inputs["Subsurface Scale"].default_value = 0.012
    if coat and "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = coat; bsdf.inputs["Coat Roughness"].default_value = 0.06
    if pores or weave:
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 1400.0 if pores else 900.0
        noise.inputs["Detail"].default_value = 6.0 if pores else 4.0
        noise.inputs["Roughness"].default_value = 0.65
        bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = pores or weave
        bump.inputs["Distance"].default_value = 0.0004 if pores else 0.0007
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
    rgb, rel, on = FA.shade(P, skin, hair, beard, base_rgb=lin[cov])
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
             + 0.05 * (FA.fbm(P, 700.0, 3, 61.0) - 0.5))
        r = np.clip(r, 0.18, 0.80)
        buf = np.zeros(cov.shape); buf[cov] = r
        rough[..., :3] = np.where(m[..., None], buf[..., None], rough[..., :3])
        _img_write(imgs["roughness"], _dilate(rough, m, 3))
    return int(m.sum()), coherent


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