"""Stage 4-6: decimate to the budget, UVs, colour, bake, rig, export.

The look is painted by position, not by hand: a colour attribute on every
vertex -- skin, beard, brows, lips, nails, the wraps' tape, the trousers'
stripe, the flag patch -- computed from where the vertex is, then baked
through the UVs into the textures. So the textures come out of the same
numbers as the mesh, and re-proportioning him re-paints him."""
import bpy, bmesh, math, os, sys, time
import numpy as np
from mathutils import Vector, Matrix
import build_ahmed as legacy
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
        charts.append((lambda c, wr=wr, he=he, s=s: near(c, wr, he + (he - wr).normalized() * 0.12, 0.075) and c.y >= -0.006 * 0, "planar", (o, w, d, 0.26), rect_b))
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
def paint(obj, kind, joints_l):
    """A colour attribute per vertex, from position. The albedo bake reads it."""
    me = obj.data
    n = len(me.vertices)
    P = np.empty(n * 3); me.vertices.foreach_get("co", P); P = P.reshape(n, 3)
    col = np.zeros((n, 4)); col[:, 3] = 1.0
    def srgb(h): h = h.lstrip('#'); return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])
    def lin(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    skin = lin(srgb('f0d8c4')); hair = lin(srgb('1e150f')); beard = lin(srgb('2a1d13')) * 0.9
    lip = lin(srgb('c98a78')); tape = lin(srgb('e8e2d4')); nail = lin(srgb('f4dccb'))
    tee = lin(srgb('15171c')); pants = lin(srgb('0e1014')); band = lin(srgb('c8102e')); shoe = lin(srgb('101216'))
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    if kind == "skin":
        col[:, :3] = skin
        # The hair is painted, not a material edge: the cap's cut plane
        # (assembly.HAIRLINE) tested per vertex with a 3 mm soft edge, so the
        # hairline is a line in the texture and not a staircase of faces.
        from . import assembly
        z0, z1 = assembly.HAIRLINE
        plane = z0 + (z1 - z0) * (y + 0.09) / 0.18
        hair_w = np.clip((z - plane) / 0.003 + 0.5, 0.0, 1.0) * (z > 1.66)
        col[:, :3] = col[:, :3] * (1 - hair_w[:, None]) + hair[None, :] * hair_w[:, None]
        # warmth: cheeks, nose tip, knuckles a shade redder; the skin is not one colour
        for (cx, cz, r, k) in [(0.05, 1.645, 0.03, 0.18), (-0.05, 1.645, 0.03, 0.18), (0.0, 1.641, 0.02, 0.22)]:
            w = np.exp(-((x - cx) ** 2 + (z - cz) ** 2) / (2 * r * r)) * (y < 0)
            col[:, :3] = col[:, :3] * (1 - k * w[:, None]) + (lin(srgb('d9a08a')) * k)[None, :] * w[:, None]
        # beard: jaw, chin, upper lip, up to the sideburn -- the browser's beard region
        # A beard has no hard edge: its top runs up the cheek toward the ear
        # and fades over 8 mm, its bottom fades out down the neck.
        jaw_z = 1.616 + 0.045 * np.clip(np.abs(x) / 0.072, 0, 1)      # rises toward the ear
        top = np.clip((jaw_z - z) / 0.008, 0, 1)
        bottom = np.clip((z - 1.556) / 0.012, 0, 1)
        side = np.clip((0.088 - np.abs(x)) / 0.006, 0, 1)
        in_beard = top * bottom * side * (y < 0.03)
        moustache = ((z > 1.618) & (z < 1.636) & (np.abs(x) < 0.028) & (y < -0.07)) * np.clip((0.028 - np.abs(x)) / 0.005, 0, 1)
        mouth = (z > 1.603) & (z < 1.622) & (np.abs(x) < 0.024) & (y < -0.08)
        beard_w = np.maximum(in_beard, moustache) * (~mouth)
        # stubble density falls off toward the cheek
        dens = np.clip(1.0 - (np.abs(x) - 0.045) / 0.045, 0.45, 1.0)
        bw = 0.92 * beard_w * dens
        col[:, :3] = col[:, :3] * (1 - bw[:, None]) + beard[None, :] * bw[:, None]
        col[mouth, :3] = col[mouth, :3] * 0.35 + lip * 0.65
        # brows
        for s in (1, -1):
            bw = np.exp(-(((x - 0.031 * s) / 0.026) ** 2 + ((z - 1.694) / 0.006) ** 2) * 0.5) * (y < -0.06)
            col[:, :3] = col[:, :3] * (1 - 0.9 * bw[:, None]) + hair[None, :] * 0.9 * bw[:, None]
        # hand wraps: tape from the wrist over the back of the hand and the knuckles
        for s in (1, -1):
            wr = np.array(Jp("hand_l")) * np.array([s, 1, 1]); he = np.array(Jp("hand_end_l")) * np.array([s, 1, 1])
            d = (he - wr) / np.linalg.norm(he - wr)
            t = (P - wr) @ d; perp = np.linalg.norm((P - wr) - np.outer(t, d), axis=1)
            wrap = (t > -0.045) & (t < 0.118) & (perp < 0.06)
            # the tape is wound: bands along t, with a gap between turns
            turns = ((t + 0.045) / 0.011) % 1.0
            band_on = wrap & ((turns < 0.82) | (t < 0.0))
            col[band_on, :3] = tape
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
        # the red stripe down the outer seam of each leg
        for s in (1, -1):
            th = np.array(Jp("thigh_l")) * np.array([s, 1, 1]); ft = np.array(Jp("foot_l")) * np.array([s, 1, 1])
            d = (ft - th) / np.linalg.norm(ft - th); t = (P - th) @ d
            outer = (x * s > th[0] * s + 0.05) & (t > 0.02) & (t < 0.97) & (np.abs(y - (th[1] + (ft[1] - th[1]) * t)) < 0.016)
            col[outer, :3] = band
    elif kind == "eye":
        # sclera with an iris and a pupil looking forward (-Y)
        c = P.mean(axis=0)
        f = np.array([0, -1, 0]); q = P - c; r = np.linalg.norm(q, axis=1) + 1e-9
        cosang = (q @ f) / r
        col[:, :3] = lin(srgb('f2efe8'))
        iris = cosang > 0.86; pupil = cosang > 0.975
        col[iris, :3] = lin(srgb('3a2a1c')); col[pupil, :3] = lin(srgb('070606'))
        rim = (cosang > 0.84) & (cosang <= 0.86); col[rim, :3] = lin(srgb('1c130c'))
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
def bake_set(obj, mat, size, out_dir, base, maps=("albedo", "normal", "roughness"), source=None, normal_size=None):
    """Bake one material's maps through the object's UVs. With `source` --
    the same surface before decimation, painted -- the colour and the
    normal come from it: the tape's edges, the patch, the sculpted face and
    the folds land in the textures at the source's resolution, not the
    game mesh's.

    `normal_size` bakes the normal map smaller than the colour. The shape
    the sculpt put in is low-frequency and survives it; the pore and weave
    bump is finer than a texel at the colour's resolution, so at full size
    it is stored as per-pixel dither the first mip level averages away --
    17.7 MB of it on the skin alone, against 3.2 MB at half."""
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
        img = bpy.data.images.new("%s_%s" % (base, m), px, px, alpha=False, float_buffer=False)
        img.colorspace_settings.name = 'sRGB' if m == "albedo" else 'Non-Color'
        img.filepath_raw = os.path.join(out_dir, "T_%s_%s.png" % (base, {"albedo": "BaseColor", "normal": "Normal", "roughness": "Roughness"}[m]))
        img.file_format = 'PNG'
        tex.image = img
        for sm, t2 in src_nodes: t2.image = img
        s2a = source is not None
        if m == "albedo": bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, margin=8, use_selected_to_active=s2a, cage_extrusion=0.02, max_ray_distance=0.05)
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
