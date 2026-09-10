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
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, -0.070, 0.010))
        o = bpy.context.object; o.name = "sole"; o.scale = (0.098, 0.300, 0.020)
        bpy.ops.object.transform_apply(scale=True)
        bv = o.modifiers.new("Bev", "BEVEL"); bv.width = 0.008; bv.segments = 3
        bpy.ops.object.modifier_apply(modifier="Bev"); bpy.ops.object.shade_smooth()
        out.append(o)
    return out

def dress(body):
    tee = shell(body, "Tee", tee_region, 0.006, 0.0025, fold=0.0025, fold_size=0.16)
    pants = shell(body, "Pants", pants_region, 0.010, 0.003, fold=0.0045, fold_size=0.20)
    return tee, pants, soles()
