#!/usr/bin/env python3
"""IRON ARM -- the upgrade's look: Saud's right arm turning to iron, from the
fist up to his sleeve, a fifth of the way per level bought.

    python3 build_iron_arm.py              the maps and the preview renders
    python3 build_iron_arm.py --no-render  the maps only

WHAT IT WRITES, into Content/Textures/Saud/, all in the SKIN's own UV layout
(the same UVs as T_Saud_Skin_*), 2048 square:

    T_Saud_IronArm_Mask       how far up the arm each texel is: 0 at the
                              knuckles, 250/255 where his skin ends under
                              the sleeve; 255 where the skin is not his
                              right arm
    T_Saud_IronArm_BaseColor  forged steel: banded plates, worn edges, rivets
    T_Saud_IronArm_Roughness
    T_Saud_IronArm_Metallic
    T_Saud_IronArm_Normal     tangent space, the same convention as every
                              other normal map this pipeline bakes

and Docs/renders/saud-ironarm-3d.png, the arm at levels 0, 1, 3 and 5.

HOW THE ENGINE USES THEM, and it has not been built -- no engine has ever run
this project. The skin material takes a scalar parameter IronArmLevel, 0 to
1 (bought levels / 5; ASaudCharacter::ApplyUpgrades sets it), and:

    t     = Mask * 255 / 250                 how far up the arm
    iron  = saturate((IronArmLevel - t) / 0.03 + 0.5) * (Mask < 0.99)
    BaseColor = lerp(skin, IronArm_BaseColor, iron)     -- likewise
    Roughness, Normal; Metallic = iron * IronArm_Metallic

which is exactly what preview() below builds in Blender for the renders.

WHICH ARM. The ask was "iron arm", one. His right: his rear hand, the power
hand the cross and the hook are thrown with. It is a choice, and the mask is
built from one side's bones, so the other is one argument away.

WHERE THE ARM IS. Not guessed from distances -- at the armpit the chest is
closer to the upper arm's axis than the arm's own far side is. A skin face is
the arm's when its vertices are mostly weighted to the right arm's own bones
(upper arm, forearm, hand, fingers), the same weights that move it. How far
up the arm it is comes from the bones too: the nearest point on the chain
knuckles -> wrist -> elbow -> shoulder, by arc length.

THE IRON is evaluated in 3D, at each texel's own position, not in UV space,
so it runs straight across the chart seams: plates 45 mm long banded round
the arm with a groove between each, a rivet at four points round every
plate, worn bright edges, hammer marks. Every number here is chosen, not
measured -- there is no reference for an iron arm -- and is written down so
nobody mistakes it for canon.
"""
import os, sys, math
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
TEX = os.path.join(PROJECT, "Content", "Textures", "Saud")
RENDERS = os.path.join(PROJECT, "Docs", "renders")
RIG = os.path.join(HERE, "rigs", "Saud.blend")

SIZE = 2048
SIDE = "r"
ARM_BONES = ["upperarm", "lowerarm", "hand", "hand_end"] + \
            ["%s_%02d" % (f, k) for f in ("index", "middle", "ring", "pinky", "thumb") for k in (1, 2, 3)]
PLATE = 0.045        # m of arm between two plate seams
GROOVE = 0.0020      # m, the seam's half-width
GROOVE_DEPTH = 0.0012
DOME = 0.0006        # each plate bulges this much at its middle
RIVET_R = 0.0035
RIVET_H = 0.0012
RIVETS = 4           # round each plate
FEATHER = 0.03       # the iron's edge, in arm fractions (IronArmLevel units)
MASK_TOP = 250       # the mask's value at the shoulder; 255 is "not the arm"


def load():
    import bpy
    bpy.ops.wm.open_mainfile(filepath=RIG)
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    mesh = next(o for o in bpy.data.objects if o.type == "MESH" and o.parent == rig)
    return rig, mesh


def arm_only(mesh):
    """A copy of the skin faces that belong to his right arm by their weights."""
    import bpy, bmesh
    skin = next(i for i, m in enumerate(mesh.data.materials) if m and m.name.endswith("_Skin"))
    names = {"%s_%s" % (b, SIDE) for b in ARM_BONES}
    arm_groups = {g.index for g in mesh.vertex_groups if g.name in names}
    w = np.zeros(len(mesh.data.vertices))
    for v in mesh.data.vertices:
        w[v.index] = sum(g.weight for g in v.groups if g.group in arm_groups)
    c = mesh.copy(); c.data = mesh.data.copy(); c.modifiers.clear()
    bpy.context.collection.objects.link(c)
    bm = bmesh.new(); bm.from_mesh(c.data)
    drop = [f for f in bm.faces if f.material_index != skin or np.mean([w[v.index] for v in f.verts]) < 0.5]
    bmesh.ops.delete(bm, geom=drop, context="FACES"); bm.to_mesh(c.data); bm.free()
    return c


def chain(rig):
    """Knuckles, wrist, elbow, shoulder -- rest positions of his right arm."""
    b = rig.data.bones
    return np.array([list(b["hand_end_" + SIDE].tail_local), list(b["hand_" + SIDE].head_local),
                     list(b["lowerarm_" + SIDE].head_local), list(b["upperarm_" + SIDE].head_local)])


def along(P, pts):
    """For each point: arc length from the knuckles to its nearest point on
    the chain (m), that length as a fraction of the whole arm, its distance
    from the chain, and its angle round the chain's axis."""
    seg = pts[1:] - pts[:-1]
    lens = np.linalg.norm(seg, axis=1)
    cum = np.concatenate([[0.0], np.cumsum(lens)])
    best_d = np.full(len(P), np.inf); s = np.zeros(len(P)); ang = np.zeros(len(P))
    for i in range(len(seg)):
        a, d, L = pts[i], seg[i] / lens[i], lens[i]
        u = np.clip((P - a) @ d, 0.0, L)
        foot = a + np.outer(u, d)
        q = P - foot
        dist = np.linalg.norm(q, axis=1)
        take = dist < best_d
        ref = np.cross(d, [0.0, 1.0, 0.0]); ref /= np.linalg.norm(ref)
        ref2 = np.cross(d, ref)
        best_d[take] = dist[take]
        s[take] = cum[i] + u[take]
        ang[take] = np.arctan2(q[take] @ ref2, q[take] @ ref)
    return s, s / cum[-1], best_d, ang


def iron(P, s, ang):
    """Height (m), linear albedo, roughness, metallic, for points on the arm."""
    from hero import face as FA
    ramp = FA.ramp
    ph = (s % PLATE) / PLATE                              # where along its plate
    seam = np.minimum(s % PLATE, PLATE - s % PLATE)       # m to the nearest seam
    groove = ramp(seam, GROOVE, 0.0)                      # 1 in the groove
    h = DOME * np.sin(np.pi * ph) - GROOVE_DEPTH * groove
    # rivets: four round each plate, 8 mm up from its lower seam
    radius = 0.035                                        # the arc they sit on
    rv = np.zeros(len(P))
    for k in range(RIVETS):
        a0 = 2 * np.pi * k / RIVETS
        da = np.angle(np.exp(1j * (ang - a0)))
        dx = da * radius
        ds = (s % PLATE) - 0.008
        r = np.hypot(dx, ds)
        rv = np.maximum(rv, np.clip(1.0 - (r / RIVET_R) ** 2, 0.0, 1.0))
    h += RIVET_H * np.sqrt(rv)
    hammer = FA.fbm(P, 180.0, 3, 7.0) - 0.5
    h += 0.0004 * hammer
    # colour: dark forged steel, worn bright on the plates' edges, black in
    # the seams, the rivet heads polished by wear
    tone = 1.0 + 0.5 * (FA.fbm(P, 60.0, 3, 3.0) - 0.5)
    base = np.array([0.055, 0.058, 0.064])
    edge = ramp(seam, 0.0045, 0.0022) * (1.0 - groove)
    col = base[None, :] * tone[:, None]
    col = col * (1 - edge)[:, None] + np.array([0.20, 0.20, 0.21])[None, :] * edge[:, None]
    col = col * (1 - rv)[:, None] + np.array([0.15, 0.15, 0.16])[None, :] * rv[:, None]
    col = col * (1 - groove)[:, None] + np.array([0.02, 0.02, 0.022])[None, :] * groove[:, None]
    rough = 0.42 + 0.15 * (FA.fbm(P, 90.0, 2, 11.0) - 0.5)
    rough = rough * (1 - edge) + 0.30 * edge
    rough = rough * (1 - rv) + 0.33 * rv
    rough = rough * (1 - groove) + 0.75 * groove
    metal = 1.0 - 0.3 * groove
    return h, col, rough, metal


def lin2srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def normals(h, pos, cov):
    """Tangent-space normals from a height field painted per texel. The UV
    axes are the tangent and the bitangent, so the slope across a texel in
    x is the height difference over that texel's own width in metres."""
    n = np.zeros(pos.shape); n[..., 2] = 1.0
    def slope(axis):
        hp, hm = np.roll(h, -1, axis), np.roll(h, 1, axis)
        pp, pm = np.roll(pos, -1, axis), np.roll(pos, 1, axis)
        cp, cm = np.roll(cov, -1, axis), np.roll(cov, 1, axis)
        both = cov & cp & cm
        dist = np.linalg.norm(pp - pm, axis=-1)
        out = np.zeros(h.shape)
        ok = both & (dist > 1e-7)
        out[ok] = (hp[ok] - hm[ok]) / dist[ok]
        return out
    n[..., 0] = -slope(1)
    n[..., 1] = -slope(0)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n


def save_png(path, a, mode):
    from PIL import Image
    Image.fromarray(np.flipud(a), mode).save(path)    # Blender row 0 is v = 0; a PNG's is the top


def build_maps(rig, mesh):
    from hero import finish as F
    arm = arm_only(mesh)
    pos, cov = F.rasterise(arm, SIZE, lambda c: True)
    assert cov.sum() > 20000, "the arm rasterised to %d texels -- no arm found" % cov.sum()
    P = pos[cov]
    s, _t, d, ang = along(P, chain(rig))
    # a fifth of the SEEN arm per level: the tee's sleeve covers the top of
    # it (the skin under a garment is stripped), and measured against the
    # whole chain the skin ends at 0.90 -- level 5 would have finished early
    t = s / s.max()
    h, col, rough, metal = iron(P, s, ang)
    H = np.zeros((SIZE, SIZE)); H[cov] = h
    N = normals(H, pos, cov)

    def full(vals, fill):
        a = np.full((SIZE, SIZE) + np.shape(fill), fill, dtype=float)
        a[cov] = vals
        return F._dilate(a, cov, 4)
    mask = np.full((SIZE, SIZE), 255.0); mask[cov] = np.round(t * MASK_TOP)
    mask = F._dilate(mask, cov, 2)
    alb = full(lin2srgb(col), (0.0, 0.0, 0.0))
    rgh = full(rough, 0.5)
    met = full(metal, 0.0)
    nrm = F._dilate(np.where(cov[..., None], N * 0.5 + 0.5, np.array([0.5, 0.5, 1.0])), cov, 4)
    os.makedirs(TEX, exist_ok=True)
    out = {}
    for name, arr, mode in (("Mask", mask.astype(np.uint8), "L"),
                            ("BaseColor", (alb * 255 + 0.5).astype(np.uint8), "RGB"),
                            ("Roughness", (rgh * 255 + 0.5).astype(np.uint8), "L"),
                            ("Metallic", (met * 255 + 0.5).astype(np.uint8), "L"),
                            ("Normal", (np.clip(nrm, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB")):
        path = os.path.join(TEX, "T_Saud_IronArm_%s.png" % name)
        save_png(path, arr, mode)
        out[name] = path
    import bpy
    bpy.data.objects.remove(arm, do_unlink=True)
    print("iron arm   : %d texels of his right arm, %.2f m knuckles to shoulder; maps %s" % (
        cov.sum(), float(np.max(s)), ", ".join(sorted(out))))
    return out, dict(texels=int(cov.sum()), length=float(np.max(s)), t_max=float(np.max(t)))


def check(maps, info):
    """What would be wrong and a render might not show."""
    from PIL import Image
    m = np.array(Image.open(maps["Mask"]))
    arm = m < 255
    # the arm is there, and it is this arm and nothing else: every masked
    # texel inside his right arm's or right hand's own chart, as
    # finish.body_charts lays them out -- the right hand's two halves at
    # u 0.5-1.0, v 0.25-0.5, the right arm's cylinder at u 0.75-1.0, v 0.5-1.0
    rows, cols = np.nonzero(arm)
    u = (cols + 0.5) / m.shape[1]; v = 1.0 - (rows + 0.5) / m.shape[0]      # PNG row 0 is v = 1
    inside = ((u >= 0.5) & (v >= 0.25) & (v <= 0.5)) | ((u >= 0.75) & (v >= 0.5))
    stray = 1.0 - inside.mean()
    assert arm.sum() > 20000, "the mask is nearly empty (%d texels)" % arm.sum()
    assert stray < 0.005, "%.1f %% of the mask lies outside his right arm's charts" % (stray * 100)
    # it runs the whole way from the knuckles to the shoulder
    assert m[arm].min() <= 8 and m[arm].max() >= MASK_TOP - 12, (
        "the mask runs %d..%d, not knuckles (0) to shoulder (%d)" % (m[arm].min(), m[arm].max(), MASK_TOP))
    # every level covers more than the one below it
    cover = [float((arm & (m / float(MASK_TOP) < lvl / 5.0)).mean()) for lvl in range(6)]
    assert all(b > a for a, b in zip(cover, cover[1:])), "a level covers no more than the one below: %s" % cover
    # the normal map is a normal map: unit length, pointing out of the surface
    n = np.array(Image.open(maps["Normal"])).astype(float) / 255.0 * 2.0 - 1.0
    ln = np.linalg.norm(n[arm], axis=1)
    assert abs(ln.mean() - 1.0) < 0.05 and n[arm][:, 2].min() > 0.2, "the normal map is not unit and outward"
    print("iron arm   : checks pass -- %s of the arm's skin iron at levels 1-5" % (
        " / ".join("%.0f%%" % (100 * c / cover[-1]) for c in cover[1:])))


def preview(maps, levels=(0, 1, 3, 5)):
    """The arm in the guard at each level, through the same blend the engine
    material is asked to make."""
    import bpy
    from PIL import Image
    import build_saud as legacy
    import rig_full_ik as CR
    frames = []
    for lvl in levels:
        rig, mesh = load()
        CR.stance(rig, legacy.GUARD, mesh)
        mat = next(m for m in mesh.data.materials if m and m.name.endswith("_Skin"))
        nt = mat.node_tree; bsdf = nt.nodes["Principled BSDF"]
        def img(name, color):
            n = nt.nodes.new("ShaderNodeTexImage"); n.image = bpy.data.images.load(maps[name])
            n.image.colorspace_settings.name = "sRGB" if color else "Non-Color"
            return n
        mask, alb, rgh, met, nrm = img("Mask", False), img("BaseColor", True), img("Roughness", False), \
            img("Metallic", False), img("Normal", False)
        # iron = saturate((L - t) / FEATHER + 0.5) * (mask < 0.99), t = mask * 255 / 250
        t = nt.nodes.new("ShaderNodeMath"); t.operation = "MULTIPLY"; t.inputs[1].default_value = 255.0 / MASK_TOP
        nt.links.new(mask.outputs["Color"], t.inputs[0])
        sub = nt.nodes.new("ShaderNodeMath"); sub.operation = "SUBTRACT"; sub.inputs[0].default_value = lvl / 5.0
        nt.links.new(t.outputs[0], sub.inputs[1])
        f = nt.nodes.new("ShaderNodeMath"); f.operation = "MULTIPLY_ADD"; f.use_clamp = True
        f.inputs[1].default_value = 1.0 / FEATHER; f.inputs[2].default_value = 0.5
        nt.links.new(sub.outputs[0], f.inputs[0])
        on = nt.nodes.new("ShaderNodeMath"); on.operation = "LESS_THAN"; on.inputs[1].default_value = 0.99
        nt.links.new(mask.outputs["Color"], on.inputs[0])
        k = nt.nodes.new("ShaderNodeMath"); k.operation = "MULTIPLY"
        nt.links.new(f.outputs[0], k.inputs[0]); nt.links.new(on.outputs[0], k.inputs[1])
        def mix(dtype, a_sock, b_sock, to):
            m = nt.nodes.new("ShaderNodeMix"); m.data_type = dtype
            nt.links.new(k.outputs[0], m.inputs["Factor"])
            key = {"RGBA": ("A", "B"), "FLOAT": ("A", "B"), "VECTOR": ("A", "B")}[dtype]
            ins = [s for s in m.inputs if s.name in key and s.enabled]
            nt.links.new(a_sock, ins[0]); nt.links.new(b_sock, ins[1])
            out = next(s for s in m.outputs if s.enabled)
            nt.links.new(out, to)
        old = {s: (l.from_socket if l else None) for s in ("Base Color", "Roughness", "Normal")
               for l in [next((l for l in nt.links if l.to_node == bsdf and l.to_socket.name == s), None)]}
        mix("RGBA", old["Base Color"], alb.outputs["Color"], bsdf.inputs["Base Color"])
        mix("FLOAT", old["Roughness"], rgh.outputs["Color"], bsdf.inputs["Roughness"])
        inm = nt.nodes.new("ShaderNodeNormalMap"); nt.links.new(nrm.outputs["Color"], inm.inputs["Color"])
        if old["Normal"] is not None:
            mix("VECTOR", old["Normal"], inm.outputs["Normal"], bsdf.inputs["Normal"])
        mm = nt.nodes.new("ShaderNodeMath"); mm.operation = "MULTIPLY"
        nt.links.new(k.outputs[0], mm.inputs[0]); nt.links.new(met.outputs["Color"], mm.inputs[1])
        nt.links.new(mm.outputs[0], bsdf.inputs["Metallic"])
        legacy.build_studio()
        from mathutils import Vector
        cam = legacy.add_camera(Vector((-1.25, -1.55, 1.42)), Vector((-0.17, -0.12, 1.28)), 62)
        bpy.context.scene.camera = cam
        path = os.path.join(RENDERS, "_ironarm_%d.png" % lvl)
        legacy.render(path, samples=40, res=(560, 760))
        frames.append((lvl, path))
    ims = [Image.open(p) for _, p in frames]
    w, h = ims[0].size
    sheet = Image.new("RGB", (w * len(ims), h + 34), (9, 10, 14))
    from PIL import ImageDraw
    d = ImageDraw.Draw(sheet)
    for i, ((lvl, p), im) in enumerate(zip(frames, ims)):
        sheet.paste(im, (i * w, 34))
        d.text((i * w + 12, 10), "IRON ARM  level %d" % lvl, fill=(232, 186, 88))
        os.remove(p)
    out = os.path.join(RENDERS, "saud-ironarm-3d.png")
    sheet.save(out)
    print("iron arm   : preview %s" % out)
    return out


def main():
    rig, mesh = load()
    maps, info = build_maps(rig, mesh)
    check(maps, info)
    if "--no-render" not in sys.argv:
        preview(maps)


if __name__ == "__main__":
    main()
