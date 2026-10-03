#!/usr/bin/env python3
"""JAZIRAT AL-QIRUD -- the monkey island: what stands on it.

Asked 2026-10-02 with the island ("build 3d map island level with monkeys
... make large island full 4k"), settled as a new Unreal-only level built
in Blender here. build_monkey_island.py is the ground and island_surfaces.py
its 4K maps; this builds the props the level puts on it, as static meshes
textured with the 4K prop maps:

    SM_Island_Palm_A/B/C     coconut palms, 9 / 12 / 15 m: a ringed, leaning
                             trunk swelling at its foot, a crown of 14 arching
                             fronds, each a rachis with its pinnae, coconuts
    SM_Island_Tree_A/B       jungle trees, 19 / 24 m: buttress roots, a trunk,
                             limbs and twigs, and clusters of leaves at their ends
    SM_Island_Rock_A/B/C     boulders, 1.2 / 2.6 / 5 m, the ground's own rock
    SM_Island_Temple         the gorilla's ground: a paved court 32 m across on
                             the arena's plateau, twelve columns round it (some
                             standing, most broken, drums fallen), low walls
                             between them, a gate where the trail comes in and a
                             stepped throne opposite it
    SM_Island_Pier           a teak pier 60 m out from the landing beach to water
    SM_Island_Boat           a Kuwaiti boom: a double-ended teak dhow, 14 m, a
                             raked mast and its lateen yard, the rudder -- what
                             brings Saud here from the stone island and back

    python3 build_island_props.py --check    the plans' own checks (no bpy)
    python3 build_island_props.py --build    build, check, export, render (bpy)
    python3 build_island_props.py --bite     each rule broken once (bpy)

Every mesh is centimetres and Z up baked into the vertices, FBX scale 1.0,
the souq's convention (build_souq.export_kind). Origins: a plant or a rock
at its foot on the ground; the temple at the arena's centre on the plateau,
its gate on local -X (the level turns it to the trail's bearing, which the
plan gives: MonkeyIsland_plan.json); the pier at its shore end on the beach,
running out along +X; the boat at its waterline's middle, bow on +X.

Every face carries one of the prop materials, M_IslandProp_<Set> (PalmBark,
Bark, Leaf, Stone, Wood) or the ground's M_IslandGround_Rock, each linked to
its three 4K maps by relative path, so surfaces.py finds every slot's set.
Leaves are drawn on both sides (each quad twice, back to back) so no
two-sided material is needed. Normal maps are DirectX (Unreal's); Blender's
own render of them reads their green the other way, which shows only in
the preview's millimetre shading.

CHECKED (each broken once by --bite): every mesh under its triangle budget;
every face on a known material whose maps are on disk; UVs on every face,
none collapsed; each plant, rock, pier and boat its planned size; the
temple clear of the fight (nothing standing within 16 m of its centre, so
the 11 m fight circle has 5 m of court round it), inside the plateau
(22.5 m), and its gate open 4 m wide; every frond and leaf cluster there;
each FBX read back to its vertex count.

NOT VERIFIED: no engine has imported a mesh. Nothing here has collision
of its own; the importer's generated collision is assumed, as for the souq.
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MODELS = os.path.join(ROOT, "Content", "Models", "Island")
TEX = {"IslandProp": os.path.join(ROOT, "Content", "Textures", "IslandProps"),
       "IslandGround": os.path.join(ROOT, "Content", "Textures", "IslandGround")}
RENDER = os.path.join(ROOT, "Docs", "renders", "island-props.png")
SABOTAGE = set()

MATERIALS = {          # slot name -> (texture prefix, set, tile metres for box/tube UVs)
    "M_IslandProp_PalmBark": ("IslandProp", "PalmBark", 1.0),
    "M_IslandProp_Bark": ("IslandProp", "Bark", 1.0),
    "M_IslandProp_Leaf": ("IslandProp", "Leaf", None),
    "M_IslandProp_Stone": ("IslandProp", "Stone", 2.0),
    "M_IslandProp_Wood": ("IslandProp", "Wood", 2.0),
    "M_IslandGround_Rock": ("IslandGround", "Rock", 4.0),
}
ROLES = ("BaseColor", "Normal", "Roughness")

# the plan: what each mesh is, its size, its budget
PALMS = dict(A=dict(h=9.0, seed=3, lean=0.10), B=dict(h=12.0, seed=5, lean=0.16), C=dict(h=15.0, seed=8, lean=0.22))
FRONDS = 14
TREES = dict(A=dict(h=19.0, seed=11), B=dict(h=24.0, seed=17))
ROCKS = dict(A=dict(size=1.2, seed=21), B=dict(size=2.6, seed=23), C=dict(size=5.0, seed=29))
TEMPLE = dict(court_r=16.0, court_h=0.25, plateau_r=22.5, ring_r=19.5, columns=12, drum_h=0.8, drum_r=0.55,
              wall_r=21.4, gate_r=21.0, gate_w=4.0, gate_h=6.0, fight_r=11.0, clear_r=16.0)
PIER = dict(length=60.0, width=3.0, deck=0.55, post_every=3.0, post_depth=4.0)
BOAT = dict(length=14.0, beam=4.0, draft=1.2, freeboard=1.3, mast=11.0)
BUDGET = dict(Palm=16000, Tree=60000, Rock=4000, Temple=40000, Pier=6000, Boat=12000)


def rng(seed):
    import random
    return random.Random(seed)


# ======================================================================= Blender

class Props:
    def __init__(self):
        import bpy
        self.bpy = bpy
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        sc.unit_settings.system = "METRIC"
        sc.unit_settings.length_unit = "METERS"
        self.mats = {}
        self.objs = {}
        self.meta = {}
        for name in MATERIALS:
            self.material(name)

    # ---------------------------------------------------------------- materials
    def material(self, name):
        bpy = self.bpy
        pre, st, _ = MATERIALS[name]
        if "unknown_material" in SABOTAGE and st == "Wood":
            st = "Teak"
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        b = nt.nodes["Principled BSDF"]
        for role in ROLES:
            path = os.path.join(TEX[pre], "T_%s_%s_%s.png" % (pre, st, role))
            if not os.path.exists(path):
                continue
            img = bpy.data.images.load(path, check_existing=True)
            img.colorspace_settings.name = "sRGB" if role == "BaseColor" else "Non-Color"
            n = nt.nodes.new("ShaderNodeTexImage")
            n.image = img
            if role == "BaseColor":
                nt.links.new(n.outputs["Color"], b.inputs["Base Color"])
            elif role == "Roughness":
                nt.links.new(n.outputs["Color"], b.inputs["Roughness"])
            else:
                nm = nt.nodes.new("ShaderNodeNormalMap")
                nt.links.new(n.outputs["Color"], nm.inputs["Color"])
                nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
        self.mats[name] = mat
        return mat

    # ---------------------------------------------------------------- mesh helpers
    def begin(self):
        import bmesh
        bm = bmesh.new()
        self.uv = bm.loops.layers.uv.new("UVMap")
        self.used = []
        return bm

    def mi(self, name):
        if name not in self.used:
            self.used.append(name)
        return self.used.index(name)

    def face(self, bm, verts, uvs, mat):
        f = bm.faces.new(verts)
        f.material_index = self.mi(mat)
        if "no_uv" not in SABOTAGE:
            for l, uv in zip(f.loops, uvs):
                l[self.uv].uv = uv
        return f

    def finish(self, bm, name, kind, **meta):
        bpy = self.bpy
        me = bpy.data.meshes.new(name)
        bm.normal_update()
        bm.to_mesh(me)
        bm.free()
        for m in self.used:
            me.materials.append(self.mats[m])
        me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
        me.update()
        o = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(o)
        self.objs[name] = o
        self.meta[name] = dict(kind=kind, **meta)
        return o

    def tube(self, bm, path, radius, segs, mat, u_rep=1, v_tile=1.0, cap=True, rfun=None):
        """Rings along a polyline (parallel-transport frames), u round it
        (u_rep whole repeats, so the texture closes on itself), v along it
        in metres / v_tile. radius(t) or rfun(t, angle)."""
        from mathutils import Vector
        P = [Vector(p) for p in path]
        n = len(P)
        T = [(P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized() for i in range(n)]
        ref = Vector((1, 0, 0)) if abs(T[0].x) < 0.9 else Vector((0, 1, 0))
        N = [T[0].cross(ref).normalized()]
        for i in range(1, n):
            v = N[-1] - T[i] * N[-1].dot(T[i])
            N.append(v.normalized() if v.length > 1e-9 else N[-1])
        L = [0.0]
        for i in range(1, n):
            L.append(L[-1] + (P[i] - P[i - 1]).length)
        rings = []
        for i in range(n):
            t = L[i] / max(L[-1], 1e-9)
            B = T[i].cross(N[i])
            ring = []
            for k in range(segs + 1):
                a = 2 * math.pi * k / segs
                r = rfun(t, a) if rfun else radius(t)
                ring.append(bm.verts.new(P[i] + (N[i] * math.cos(a) + B * math.sin(a)) * r) if k < segs else ring[0])
            rings.append(ring)
        for i in range(n - 1):
            for k in range(segs):
                v0, v1 = L[i] / v_tile, L[i + 1] / v_tile
                u0, u1 = u_rep * k / segs, u_rep * (k + 1) / segs
                self.face(bm, [rings[i][k], rings[i][k + 1], rings[i + 1][k + 1], rings[i + 1][k]],
                          [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], mat)
        if cap and radius is not None and (rfun is None):
            top = rings[-1][:segs]
            if radius(1.0) > 1e-4:
                self.face(bm, top, [(0.5 + 0.5 * math.cos(2 * math.pi * k / segs), 0.5 + 0.5 * math.sin(2 * math.pi * k / segs))
                                    for k in range(segs)], mat)
        return rings

    def box(self, bm, c, size, mat, tile=2.0, yaw=0.0, top_scale=1.0):
        """A box centred at c=(x, y, z-bottom), size (w, d, h), turned yaw;
        every face box-mapped in metres / tile."""
        from mathutils import Vector, Matrix
        w, d, h = size
        R = Matrix.Rotation(yaw, 3, "Z")
        o = Vector(c)
        lo = [(-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)]
        pts = [o + R @ Vector((x, y, 0)) for x, y in lo] + [o + R @ Vector((x * top_scale, y * top_scale, h)) for x, y in lo]
        V = [bm.verts.new(p) for p in pts]
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            vs = [V[i] for i in f]
            nrm = (vs[1].co - vs[0].co).cross(vs[2].co - vs[0].co)
            ax = max(range(3), key=lambda i: abs(nrm[i]))
            uvs = []
            for v in vs:
                p = v.co
                uv = (p.x, p.y) if ax == 2 else ((p.y, p.z) if ax == 0 else (p.x, p.z))
                uvs.append((uv[0] / tile, uv[1] / tile))
            self.face(bm, vs, uvs, mat)

    def leaf_quad(self, bm, base, along, across, length, width, mat, diamond=False):
        """One leaf or pinna, both sides: u along it, v across it."""
        from mathutils import Vector
        a, c = along.normalized(), across.normalized()
        if diamond:
            pts = [base, base + a * length * 0.45 - c * width / 2, base + a * length, base + a * length * 0.45 + c * width / 2]
            uvs = [(0, 0.5), (0.45, 0.0), (1, 0.5), (0.45, 1.0)]
        else:
            tipw = width * 0.18
            pts = [base - c * width / 2, base + a * length - c * tipw / 2, base + a * length + c * tipw / 2, base + c * width / 2]
            uvs = [(0, 0), (1, 0.41), (1, 0.59), (0, 1)]
        V = [bm.verts.new(p) for p in pts]
        self.face(bm, V, uvs, mat)
        W = [bm.verts.new(p) for p in pts]
        self.face(bm, list(reversed(W)), list(reversed(uvs)), mat)

    def sphere(self, bm, c, r, mat, segs=10, rings=6, squash=1.0, jitter=None, tile=4.0):
        """A UV sphere, box-mapped (rocks, coconuts); jitter(v) -> scale."""
        from mathutils import Vector
        rows = []
        for j in range(rings + 1):
            phi = math.pi * j / rings - math.pi / 2
            row = []
            for i in range(segs):
                th = 2 * math.pi * i / segs
                d = Vector((math.cos(phi) * math.cos(th), math.cos(phi) * math.sin(th), math.sin(phi) * squash))
                k = jitter(d) if jitter else 1.0
                row.append(bm.verts.new(Vector(c) + d * r * k))
            rows.append(row)
        for j in range(rings):
            for i in range(segs):
                vs = [rows[j][i], rows[j][(i + 1) % segs], rows[j + 1][(i + 1) % segs], rows[j + 1][i]]
                nrm = (vs[2].co - vs[0].co).cross(vs[3].co - vs[1].co)
                ax = max(range(3), key=lambda q: abs(nrm[q]))
                uvs = [((v.co.x, v.co.y) if ax == 2 else ((v.co.y, v.co.z) if ax == 0 else (v.co.x, v.co.z))) for v in vs]
                self.face(bm, vs, [(u / tile, w / tile) for u, w in uvs], mat)

    # ---------------------------------------------------------------- palm
    def palm(self, key, h, seed, lean):
        from mathutils import Vector, Matrix
        R = rng(seed)
        bm = self.begin()
        az = R.uniform(0, 2 * math.pi)
        d = Vector((math.cos(az), math.sin(az), 0))
        n = 40
        path = []
        for i in range(n + 1):
            t = i / n
            path.append(Vector((0, 0, h * t)) + d * (lean * h * t ** 1.7) + d.cross(Vector((0, 0, 1))) * (0.15 * math.sin(t * 3 + seed)))
        r0 = 0.19
        self.tube(bm, path, lambda t: r0 * (1 + 0.45 * math.exp(-t * 14)) * (1 - 0.22 * t), 14, "M_IslandProp_PalmBark",
                  u_rep=1, v_tile=1.0)
        top = path[-1]
        fronds = 0 if "no_crown" in SABOTAGE else FRONDS
        pinnae = 0
        for f in range(fronds):
            a = 2 * math.pi * f / FRONDS + R.uniform(-0.15, 0.15)
            out = Vector((math.cos(a), math.sin(a), 0))
            L = R.uniform(3.4, 4.6)
            elev0 = math.radians(R.uniform(30, 55))
            pts = []
            p = top.copy()
            steps = 16
            for s in range(steps + 1):
                t = s / steps
                el = elev0 - t * math.radians(85)
                pts.append(p.copy())
                p = p + (out * math.cos(el) + Vector((0, 0, math.sin(el)))) * (L / steps)
            self.tube(bm, pts, lambda t: 0.035 * (1 - 0.7 * t), 5, "M_IslandProp_PalmBark", u_rep=1, v_tile=1.0, cap=False)
            side = out.cross(Vector((0, 0, 1))).normalized()
            m = 46
            for k in range(m):
                t = 0.14 + 0.84 * k / (m - 1)
                i = min(int(t * steps), steps - 1)
                ft = t * steps - i
                base = pts[i].lerp(pts[i + 1], ft)
                tang = (pts[i + 1] - pts[i]).normalized()
                plen = (0.55 + 0.35 * math.sin(math.pi * min(1.0, t * 1.15))) * (1 - 0.55 * max(0.0, t - 0.6))
                for sgn in (-1, 1):
                    dirn = (side * sgn * 0.82 + tang * 0.45 + Vector((0, 0, -0.38))).normalized()
                    self.leaf_quad(bm, base, dirn, tang, plen, 0.045, "M_IslandProp_Leaf")
                    pinnae += 1
        for k in range(5):
            a = 2 * math.pi * k / 5 + 0.3
            self.sphere(bm, top + Vector((math.cos(a) * 0.22, math.sin(a) * 0.22, -0.25)), 0.11, "M_IslandProp_PalmBark",
                        segs=8, rings=5, tile=1.0)
        return self.finish(bm, "SM_Island_Palm_%s" % key, "Palm", height=h, fronds=fronds, pinnae=pinnae)

    # ---------------------------------------------------------------- jungle tree
    def tree(self, key, h, seed):
        from mathutils import Vector
        R = rng(seed)
        bm = self.begin()
        trunk_h = h * 0.62
        r0 = 0.45 + 0.02 * h
        phase = R.uniform(0, 6.28)
        n = 30
        path = [Vector((0.1 * math.sin(i * 0.4 + seed), 0.1 * math.cos(i * 0.3), trunk_h * i / n)) for i in range(n + 1)]
        path[0] = Vector((0, 0, -0.4))

        def rfun(t, a):
            z = t * trunk_h
            butt = 1.6 * math.exp(-z / 1.6) * max(0.0, math.cos(5 * a + phase)) ** 3
            return r0 * (1 - 0.35 * t) * (1 + butt)
        self.tube(bm, path, None, 20, "M_IslandProp_Bark", u_rep=2, v_tile=1.0, cap=False, rfun=rfun)
        tips = []

        def limb(start, direction, length, radius, depth):
            pts = []
            p = start.copy()
            d = direction.normalized()
            for s in range(7):
                pts.append(p.copy())
                d = (d + Vector((R.uniform(-.15, .15), R.uniform(-.15, .15), 0.06))).normalized()
                p = p + d * (length / 6)
            self.tube(bm, pts, lambda t: radius * (1 - 0.6 * t), 8 if depth == 0 else 6, "M_IslandProp_Bark",
                      u_rep=1, v_tile=1.0)
            if depth == 0:
                for _ in range(R.randint(3, 4)):
                    j = R.randint(3, 5)
                    nd = (d + Vector((R.uniform(-0.8, 0.8), R.uniform(-0.8, 0.8), R.uniform(0.1, 0.6)))).normalized()
                    limb(pts[j], nd, length * R.uniform(0.45, 0.6), radius * 0.45, 1)
            tips.append(pts[-1])
        nb = R.randint(4, 5)
        for b in range(nb):
            a = 2 * math.pi * b / nb + R.uniform(-0.3, 0.3)
            z = trunk_h * R.uniform(0.62, 0.95)
            limb(Vector((0, 0, z)), Vector((math.cos(a), math.sin(a), R.uniform(0.6, 1.2))), h * R.uniform(0.22, 0.3),
                 r0 * 0.42, 0)
        clusters = 0 if "no_crown" in SABOTAGE else len(tips)
        leaves = 0
        for c in tips[:clusters]:
            cr = R.uniform(2.4, 3.4)
            for _ in range(300):
                u = Vector((R.gauss(0, 1), R.gauss(0, 1), R.gauss(0, 0.6))).normalized() * cr * R.random() ** 0.5
                base = c + u + Vector((0, 0, 0.4))
                along = (u.normalized() + Vector((R.uniform(-.5, .5), R.uniform(-.5, .5), -0.3))).normalized()
                across = along.cross(Vector((0, 0, 1)))
                if across.length < 1e-3:
                    across = Vector((1, 0, 0))
                self.leaf_quad(bm, base, along, across, R.uniform(0.38, 0.58), R.uniform(0.16, 0.24), "M_IslandProp_Leaf",
                               diamond=True)
                leaves += 1
        return self.finish(bm, "SM_Island_Tree_%s" % key, "Tree", height=h, clusters=clusters, leaves=leaves)

    # ---------------------------------------------------------------- rocks
    def rock(self, key, size, seed):
        from mathutils import Vector, noise
        bm = self.begin()
        off = Vector((seed * 1.7, seed * 0.3, seed * 2.1))

        def jit(d):
            return 0.72 + 0.28 * (noise.noise(d * 1.6 + off) + 1) * 0.5 + 0.10 * noise.noise(d * 4.0 + off)
        self.sphere(bm, (0, 0, size * 0.32), size * 0.5, "M_IslandGround_Rock", segs=22, rings=12, squash=0.75,
                    jitter=jit, tile=4.0)
        return self.finish(bm, "SM_Island_Rock_%s" % key, "Rock", size=size)

    # ---------------------------------------------------------------- the temple
    def temple(self):
        from mathutils import Vector
        T = TEMPLE
        R = rng(97)
        bm = self.begin()
        S = "M_IslandProp_Stone"
        # the court: a paved disc a step up off the plateau, its paving UV
        # in plan at 2 m a tile
        segs = 48
        ring_lo = [bm.verts.new((math.cos(2 * math.pi * i / segs) * T["court_r"], math.sin(2 * math.pi * i / segs) * T["court_r"], 0))
                   for i in range(segs)]
        ring_hi = [bm.verts.new((v.co.x, v.co.y, T["court_h"])) for v in ring_lo]
        self.face(bm, ring_hi, [(v.co.x / 2.0, v.co.y / 2.0) for v in ring_hi], S)
        circ = 2 * math.pi * T["court_r"]
        for i in range(segs):
            j = (i + 1) % segs
            u0, u1 = circ * i / segs / 2.0, circ * (i + 1) / segs / 2.0
            self.face(bm, [ring_lo[i], ring_lo[j], ring_hi[j], ring_hi[i]], [(u0, 0), (u1, 0), (u1, T["court_h"] / 2), (u0, T["court_h"] / 2)], S)
        # the columns: a plinth, drums to a broken height, a capital on the
        # whole ones; the gate's bearing (local -X, 180 degrees) left open
        cols = []
        for k in range(T["columns"]):
            a = 2 * math.pi * (k + 0.5) / T["columns"]
            if abs(math.degrees(a) - 180) < 20:
                continue
            x, y = math.cos(a) * T["ring_r"], math.sin(a) * T["ring_r"]
            if "column_in_court" in SABOTAGE and k == 3:
                x, y = math.cos(a) * 10.0, math.sin(a) * 10.0
            self.box(bm, (x, y, 0), (1.5, 1.5, 0.45), S, yaw=a)
            drums = 7 if k % 4 == 1 else R.randint(1, 5)
            z = 0.45
            for dd in range(drums):
                r = T["drum_r"] * (1 - 0.03 * dd)
                path = [Vector((x, y, z)), Vector((x, y, z + T["drum_h"] - 0.02))]
                self.tube(bm, path, lambda t, r=r: r, 16, S, u_rep=2, v_tile=2.0)
                z += T["drum_h"]
            if drums == 7:
                self.box(bm, (x, y, z), (1.4, 1.4, 0.35), S, yaw=a, top_scale=1.1)
                z += 0.35
            cols.append(dict(x=x, y=y, top=z))
            # the drums that fell, lying outward of the column
            for f in range(7 - drums if drums < 7 else 0):
                if R.random() < 0.55:
                    continue
                ra = a + R.uniform(-0.35, 0.35)
                rr = T["ring_r"] + R.uniform(-1.0, 2.2)
                if abs(math.degrees(ra % (2 * math.pi)) - 180) < 16:
                    continue                                    # not across the way in
                fx, fy = math.cos(ra) * rr, math.sin(ra) * rr
                yaw = R.uniform(0, math.pi)
                dvec = Vector((math.cos(yaw), math.sin(yaw), 0)) * (T["drum_h"] / 2)
                c = Vector((fx, fy, T["drum_r"] * 0.92))
                self.tube(bm, [c - dvec, c + dvec], lambda t: T["drum_r"] * 0.95, 16, S, u_rep=2, v_tile=2.0)
        # low walls between the columns, broken, open at the gate
        for k in range(T["columns"]):
            a0 = 2 * math.pi * (k + 0.5) / T["columns"]
            a1 = a0 + 2 * math.pi / T["columns"]
            mid = (a0 + a1) / 2
            if abs(math.degrees(mid % (2 * math.pi)) - 180) < 25 or R.random() < 0.25:
                continue
            length = 2 * T["wall_r"] * math.sin(math.pi / T["columns"]) - 2.2
            hgt = R.uniform(0.7, 2.4)
            self.box(bm, (math.cos(mid) * T["wall_r"], math.sin(mid) * T["wall_r"], 0), (0.6, length * R.uniform(0.45, 0.95), hgt), S,
                     yaw=mid)
        # the gate, on local -X: two pillars and the lintel over the trail
        gx = -T["gate_r"]
        half = T["gate_w"] / 2 + 0.6
        gate_y = half + (0.0 if "gate_blocked" not in SABOTAGE else -2.0)
        for sy in (-1, 1):
            self.box(bm, (gx, sy * gate_y, 0), (1.2, 1.2, T["gate_h"]), S)
        self.box(bm, (gx, 0, T["gate_h"]), (1.3, 2 * gate_y + 1.6, 1.0), S)
        # the throne, opposite the gate: three steps and a seat
        for i, (depth, h) in enumerate(((4.4, 0.5), (3.4, 1.0), (2.4, 1.5))):
            self.box(bm, (22.0 - depth / 2 - 0.1, 0, 0), (depth, 8.0 - i * 1.6, h), S)
        self.box(bm, (21.1, 0, 1.5), (1.2, 2.2, 1.6), S)
        return self.finish(bm, "SM_Island_Temple", "Temple", columns=cols, gate=dict(x=gx, y_inner=gate_y - 0.6, height=T["gate_h"]),
                           court_r=T["court_r"], court_h=T["court_h"])

    # ---------------------------------------------------------------- the pier
    def pier(self):
        from mathutils import Vector
        P = PIER
        bm = self.begin()
        W = "M_IslandProp_Wood"
        L, w, z = P["length"], P["width"], P["deck"]
        # the deck: one slab, its planks running across it (u across, v along)
        top = [bm.verts.new(v) for v in ((0, -w / 2, z), (L, -w / 2, z), (L, w / 2, z), (0, w / 2, z))]
        self.face(bm, top, [(-w / 4, 0), (-w / 4, L / 2), (w / 4, L / 2), (w / 4, 0)], W)
        bot = [bm.verts.new((v.co.x, v.co.y, z - 0.08)) for v in top]
        self.face(bm, list(reversed(bot)), [(0, 0), (0, 1), (1, 1), (1, 0)], W)
        for i in range(4):
            j = (i + 1) % 4
            ln = (top[j].co - top[i].co).length
            self.face(bm, [bot[i], bot[j], top[j], top[i]], [(0, 0), (ln / 2, 0), (ln / 2, 0.04), (0, 0.04)], W)
        # stringers and posts
        for sy in (-1, 1):
            self.box(bm, (L / 2, sy * (w / 2 - 0.15), z - 0.38), (L, 0.18, 0.30), W)
        x = 0.4
        while x < L:
            for sy in (-1, 1):
                self.tube(bm, [Vector((x, sy * (w / 2 - 0.1), -P["post_depth"])), Vector((x, sy * (w / 2 - 0.1), z + 0.9))],
                          lambda t: 0.12, 8, W, u_rep=1, v_tile=2.0)
            x += P["post_every"]
        # the rail
        for sy in (-1, 1):
            self.box(bm, (L / 2 + 0.2, sy * (w / 2 - 0.1), z + 0.85), (L - 0.4, 0.10, 0.10), W)
        return self.finish(bm, "SM_Island_Pier", "Pier", length=L, deck=z)

    # ---------------------------------------------------------------- the boat
    def boat(self):
        from mathutils import Vector
        B = BOAT
        bm = self.begin()
        W = "M_IslandProp_Wood"
        L, half = B["length"], B["beam"] / 2
        st = 28
        ns = 12
        sections = []
        for i in range(st + 1):
            t = i / st
            x = -L / 2 + L * t
            breadth = half * (1 - abs(2 * t - 1) ** 2.2) ** 0.55 + 0.04
            sheer = B["freeboard"] + 0.75 * (2 * t - 1) ** 2 * (1.0 if t > 0.5 else 0.6)
            keel = -B["draft"] * (1 - abs(2 * t - 1) ** 3) ** 0.5 - 0.05
            rake = (t - 0.5) * 0.0
            sec = []
            for k in range(ns + 1):
                phi = math.pi * k / ns                                        # 0 port sheer .. pi starboard sheer
                yy = -math.cos(phi) * breadth
                s = math.sin(phi)
                zz = sheer + (keel - sheer) * s ** 0.6
                sec.append(Vector((x + rake, yy, zz)))
            sections.append(sec)
        V = [[bm.verts.new(p) for p in sec] for sec in sections]
        arc = [0.0]
        for k in range(ns):
            arc.append(arc[-1] + (sections[st // 2][k + 1] - sections[st // 2][k]).length)
        for i in range(st):
            for k in range(ns):
                u0, u1 = sections[i][0].x / 2.0, sections[i + 1][0].x / 2.0
                v0, v1 = arc[k] / 2.0, arc[k + 1] / 2.0
                self.face(bm, [V[i][k], V[i + 1][k], V[i + 1][k + 1], V[i][k + 1]], [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], W)
        # the deck, a little under the sheer, closing the hull
        dz = B["freeboard"] - 0.35
        deck_l, deck_r = [], []
        for i in range(st + 1):
            t = i / st
            x = -L / 2 + L * t
            b = (half * (1 - abs(2 * t - 1) ** 2.2) ** 0.55 + 0.04) * 0.97
            deck_l.append(bm.verts.new((x, -b, dz)))
            deck_r.append(bm.verts.new((x, b, dz)))
        for i in range(st):
            ps = [deck_l[i], deck_l[i + 1], deck_r[i + 1], deck_r[i]]
            self.face(bm, ps, [(p.co.y / 2.0, p.co.x / 2.0) for p in ps], W)
        # the stem post rising past the bow, the stern post, the mast and yard
        self.tube(bm, [Vector((L / 2, 0, -0.3)), Vector((L / 2 + 0.9, 0, B["freeboard"] + 1.5))], lambda t: 0.12, 8, W, v_tile=2.0)
        self.tube(bm, [Vector((-L / 2, 0, -0.3)), Vector((-L / 2 - 0.5, 0, B["freeboard"] + 1.0))], lambda t: 0.11, 8, W, v_tile=2.0)
        mast_base = Vector((1.6, 0, dz))
        mast_top = mast_base + Vector((0.9, 0, B["mast"]))
        self.tube(bm, [mast_base, mast_top], lambda t: 0.16 * (1 - 0.45 * t), 10, W, v_tile=2.0)
        yard_mid = mast_top + Vector((-0.2, 0, -1.2))
        yd = Vector((math.cos(math.radians(28)), 0, math.sin(math.radians(28)))) * 7.0
        self.tube(bm, [yard_mid - yd * 0.9, yard_mid + yd * 0.6], lambda t: 0.09 * (1 - 0.6 * abs(2 * t - 1)), 8, W, v_tile=2.0)
        # the rudder at the stern
        self.box(bm, (-L / 2 - 0.25, 0, -B["draft"] * 0.9), (0.9, 0.12, B["draft"] + 1.2), W)
        return self.finish(bm, "SM_Island_Boat", "Boat", length=L, draft=B["draft"], mast=B["mast"])

    # ---------------------------------------------------------------- all of it
    def build_all(self):
        for k, p in PALMS.items():
            self.palm(k, p["h"], p["seed"], p["lean"])
        for k, p in TREES.items():
            self.tree(k, p["h"], p["seed"])
        for k, p in ROCKS.items():
            self.rock(k, p["size"], p["seed"])
        self.temple()
        self.pier()
        self.boat()


# ======================================================================= checks

def check(pr):
    """Every rule over the built meshes; the misses."""
    from mathutils import Vector
    miss = []
    for name, o in pr.objs.items():
        me = o.data
        meta = pr.meta[name]
        tris = sum(len(p.vertices) - 2 for p in me.polygons)
        if tris > BUDGET[meta["kind"]]:
            miss.append("%s is %d triangles, over its %d" % (name, tris, BUDGET[meta["kind"]]))
        for m in me.materials:
            pre, st, _ = MATERIALS.get(m.name, (None, None, None))
            imgs = [n.image for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image]
            if m.name not in MATERIALS or len(imgs) != 3 or not all(os.path.exists(bpy_abspath(i.filepath)) for i in imgs):
                miss.append("%s: material %s has %d of its 3 maps on disk" % (name, m.name, len(imgs)))
        uv = me.uv_layers.active
        if uv is None:
            miss.append("%s has no UVs" % name)
        else:
            bad = 0
            for p in me.polygons:
                us = [uv.data[i].uv for i in p.loop_indices]
                a = 0.0
                for i in range(1, len(us) - 1):
                    a += abs((us[i] - us[0]).cross(us[i + 1] - us[0]))
                bad += a < 1e-9
            if bad > 0.005 * len(me.polygons):
                miss.append("%s: %d of %d faces have collapsed UVs" % (name, bad, len(me.polygons)))
        zs = [v.co.z for v in me.vertices]
        xs = [v.co.x for v in me.vertices]
        ys = [v.co.y for v in me.vertices]
        k = meta["kind"]
        if k == "Palm":
            top = max(zs)
            if not meta["height"] * 0.95 <= top <= meta["height"] + 3.5:
                miss.append("%s stands %.1f m, want %.0f-%.1f" % (name, top, meta["height"] * 0.95, meta["height"] + 3.5))
            if meta["fronds"] < FRONDS or meta["pinnae"] < FRONDS * 80:
                miss.append("%s has %d fronds and %d pinnae, want %d and %d" % (name, meta["fronds"], meta["pinnae"], FRONDS, FRONDS * 80))
        elif k == "Tree":
            if not meta["height"] * 0.8 <= max(zs) <= meta["height"] * 1.25:
                miss.append("%s stands %.1f m, want about %.0f" % (name, max(zs), meta["height"]))
            if meta["clusters"] < 12 or meta["leaves"] < 4000:
                miss.append("%s has %d leaf clusters and %d leaves, want 12 and 4000" % (name, meta["clusters"], meta["leaves"]))
        elif k == "Rock":
            span = max(max(xs) - min(xs), max(ys) - min(ys))
            if not meta["size"] * 0.75 <= span <= meta["size"] * 1.25:
                miss.append("%s is %.1f m across, want about %.1f" % (name, span, meta["size"]))
        elif k == "Temple":
            T = TEMPLE
            inner = [v.co for v in me.vertices if math.hypot(v.co.x, v.co.y) < T["clear_r"] - 0.05 and v.co.z > T["court_h"] + 0.01]
            if inner:
                miss.append("the temple stands in the court: %d vertices within %.0f m of its centre over the paving" % (len(inner), T["clear_r"]))
            far = max(math.hypot(v.co.x, v.co.y) for v in me.vertices)
            if far > T["plateau_r"] + 0.05:
                miss.append("the temple reaches %.1f m from its centre, past the plateau's %.1f" % (far, T["plateau_r"]))
            gate = [v.co for v in me.vertices if v.co.x < -(T["court_r"] + 0.1) and abs(v.co.y) < T["gate_w"] / 2 - 0.02
                    and v.co.z < T["gate_h"] - 0.05]
            if gate:
                miss.append("the temple's gate is blocked: %d vertices in its %.0f m opening" % (len(gate), T["gate_w"]))
            if T["court_r"] - T["fight_r"] < 4.0:
                miss.append("the court leaves %.1f m round the fight" % (T["court_r"] - T["fight_r"]))
        elif k == "Pier":
            if abs((max(xs) - min(xs)) - PIER["length"]) > 0.6:
                miss.append("the pier is %.1f m long, want %.0f" % (max(xs) - min(xs), PIER["length"]))
        elif k == "Boat":
            hull = max(xs) - min(xs)
            if not BOAT["length"] <= hull <= BOAT["length"] + 1.8 or min(zs) > -BOAT["draft"] * 0.9:
                miss.append("the boat is %.1f m long and draws %.1f m, want %.0f and %.1f" % (hull, -min(zs), BOAT["length"], BOAT["draft"]))
            if max(zs) < BOAT["mast"]:
                miss.append("the boat's mast stands %.1f m, want %.0f" % (max(zs), BOAT["mast"]))
    return miss


def bpy_abspath(p):
    import bpy
    return bpy.path.abspath(p)


# ======================================================================= export, render

def export(pr):
    bpy = pr.bpy
    os.makedirs(MODELS, exist_ok=True)
    out = {}
    for name, o in pr.objs.items():
        loc = tuple(o.location)
        o.location = (0, 0, 0)
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        path = os.path.join(MODELS, name + ".fbx")
        bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH"}, apply_unit_scale=True, global_scale=1.0,
                                 apply_scale_options="FBX_SCALE_NONE", bake_space_transform=True, mesh_smooth_type="FACE",
                                 use_mesh_modifiers=True, path_mode="RELATIVE", embed_textures=False, bake_anim=False)
        o.location = loc
        out[name] = dict(file=os.path.relpath(path, ROOT), tris=sum(len(p.vertices) - 2 for p in o.data.polygons),
                         verts=len(o.data.vertices), **{k: v for k, v in pr.meta[name].items() if k != "columns"})
    # read every one back
    miss = []
    for name in pr.objs:
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=os.path.join(MODELS, name + ".fbx"))
        back = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
        got = sum(len(o.data.vertices) for o in back)
        for o in back:
            bpy.data.objects.remove(o, do_unlink=True)
        if got != out[name]["verts"]:
            miss.append("%s reads back with %d vertices, not %d" % (name, got, out[name]["verts"]))
    man = dict(units="centimetres, Z up, baked into the vertices (FBX scale 1.0)",
               origins=dict(plants_and_rocks="the foot, on the ground", temple="the arena's centre on the plateau; gate on local -X",
                            pier="the shore end on the beach; runs out along +X", boat="the waterline's middle; bow on +X"),
               temple=dict(TEMPLE), pier=dict(PIER), boat=dict(BOAT), meshes=out)
    with open(os.path.join(MODELS, "Island_props.json"), "w") as f:
        json.dump(man, f, indent=1)
    return out, miss


def render(pr, path=RENDER, samples=48):
    """Every prop on a sand floor under a low cold moon and a soft sky,
    in two rows: the plants and rocks, then the temple, pier and boat."""
    bpy = pr.bpy
    from mathutils import Vector
    sc = bpy.context.scene
    lay = {"SM_Island_Palm_A": (-26, 10), "SM_Island_Palm_B": (-20, 12), "SM_Island_Palm_C": (-13, 10),
           "SM_Island_Tree_A": (-2, 14), "SM_Island_Tree_B": (14, 16), "SM_Island_Rock_A": (-24, 3), "SM_Island_Rock_B": (-19, 2),
           "SM_Island_Rock_C": (-11, 1), "SM_Island_Temple": (8, -26), "SM_Island_Pier": (-36, -10), "SM_Island_Boat": (-24, -14)}
    for name, (x, y) in lay.items():
        pr.objs[name].location = (x, y, 0)
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
    g = bpy.context.object
    sand = bpy.data.materials.new("Preview_Sand")
    sand.use_nodes = True
    tex = bpy.data.images.load(os.path.join(TEX["IslandGround"], "T_IslandGround_Sand_BaseColor.png"))
    n = sand.node_tree.nodes.new("ShaderNodeTexImage")
    n.image = tex
    m = sand.node_tree.nodes.new("ShaderNodeMapping")
    m.inputs["Scale"].default_value = (50, 50, 1)
    c = sand.node_tree.nodes.new("ShaderNodeTexCoord")
    sand.node_tree.links.new(c.outputs["UV"], m.inputs["Vector"])
    sand.node_tree.links.new(m.outputs["Vector"], n.inputs["Vector"])
    sand.node_tree.links.new(n.outputs["Color"], sand.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    g.data.materials.append(sand)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    sc.collection.objects.link(cam)
    cam.data.lens = 24
    cam.location = Vector((-4, -82, 22))
    cam.rotation_euler = (Vector((-6, 0, 8)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    sun = bpy.data.objects.new("Moon", bpy.data.lights.new("Moon", "SUN"))
    sc.collection.objects.link(sun)
    sun.data.energy = 3.0
    sun.data.color = (0.80, 0.86, 1.0)
    sun.data.angle = math.radians(2)
    sun.rotation_euler = (math.radians(50), 0, math.radians(-35))
    sc.world = bpy.data.worlds.new("W")
    sc.world.use_nodes = True
    sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.35, 0.42, 0.55, 1)
    sc.world.node_tree.nodes["Background"].inputs[1].default_value = 0.6
    sc.render.engine = "CYCLES"
    sc.cycles.samples = samples
    sc.cycles.device = "CPU"
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    sc.view_settings.view_transform = "Standard"
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("drew %s" % path)


# ======================================================================= main

BITES = [
    ("the court clear", "column_in_court", "stands in the court"),
    ("the gate open", "gate_blocked", "gate is blocked"),
    ("every crown there", "no_crown", "fronds"),
    ("UVs on every face", "no_uv", "collapsed UVs"),
    ("every map on disk", "unknown_material", "of its 3 maps"),
]


def plan_check():
    """What can be held without Blender: the plan's own numbers."""
    miss = []
    T = TEMPLE
    if T["clear_r"] - T["fight_r"] < 4.0:
        miss.append("the court leaves less than 4 m round the fight")
    if T["ring_r"] + 0.75 > T["plateau_r"] or T["wall_r"] + 0.3 > T["plateau_r"]:
        miss.append("the temple's ring stands off the plateau")
    if T["ring_r"] - 0.75 < T["clear_r"]:
        miss.append("the columns stand in the court")
    for k in MATERIALS.values():
        for role in ROLES:
            p = os.path.join(TEX[k[0]], "T_%s_%s_%s.png" % (k[0], k[1], role))
            if not os.path.exists(p):
                miss.append("no %s" % os.path.relpath(p, ROOT))
    return miss


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if "--build" not in args and "--bite" not in args:
        f = plan_check()
        print("\n".join("MISS " + m for m in f) or "island props plan: checks pass")
        sys.exit(1 if f else 0)
    try:
        import bpy  # noqa: F401
    except ImportError:
        print("--build and --bite run with bpy (pip install bpy)")
        sys.exit(2)
    if "--bite" in args:
        caught = 0
        for what, sab, want in BITES:
            SABOTAGE.clear()
            SABOTAGE.add(sab)
            pr = Props()
            pr.build_all()
            f = check(pr)
            hit = [x for x in f if want in x]
            caught += bool(hit)
            print("  %-20s %s  %s" % (what, "caught" if hit else "MISSED", (hit or f or ["(passed)"])[0]))
        SABOTAGE.clear()
        print("%d of %d caught" % (caught, len(BITES)))
        sys.exit(0 if caught == len(BITES) else 1)
    pr = Props()
    pr.build_all()
    f = check(pr) + plan_check()
    for name, o in pr.objs.items():
        print("  %-20s %6d tris" % (name, sum(len(p.vertices) - 2 for p in o.data.polygons)))
    if f:
        print("FAILED:\n  " + "\n  ".join(f))
        sys.exit(1)
    out, miss = export(pr)
    if miss:
        print("FAILED:\n  " + "\n  ".join(miss))
        sys.exit(1)
    print("checks pass: budgets, materials and maps, UVs, sizes, the temple's court and gate, crowns; %d FBX read back" % len(out))
    if "--no-render" not in args:
        render(pr)


if __name__ == "__main__":
    main()
