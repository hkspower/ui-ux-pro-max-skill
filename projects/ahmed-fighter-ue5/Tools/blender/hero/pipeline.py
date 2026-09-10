"""Ahmed, rebuilt: the whole pipeline end to end.

    anatomy   the body as lofted cross-sections and lofted limbs
    assembly  the two-pass voxel union, the face sculpt, the hair, the eyes
    garments  the tee and the track pants as shells off the body
    finish    the budget, the UVs, the paint, the bake
    rig_export the skeleton with fingers, the binding, the exports

Run through build_ahmed.py:

    python3 build_ahmed.py              the hero: 4K colour, 2K normals, 64-sample renders
    python3 build_ahmed.py --fast       1K textures, quick renders, for a look
    python3 build_ahmed.py --resume     skip the nine-minute build, reload it
    python3 build_ahmed.py --coarse     a rough body, to check the later stages
    python3 build_ahmed.py --out DIR    write somewhere else than the project
"""
import bpy, os, sys, time, math, json
from mathutils import Vector
import build_ahmed as legacy
from . import anatomy as A, assembly as B, garments as G, finish as F, rig_export as R

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
UNITY = os.path.abspath(os.path.join(PROJECT, "..", "ahmed-fighter-unity"))


def run(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    FAST = "--fast" in argv
    TEX = 1024 if FAST else 4096
    BUDGET = 60000
    PORES = {"skin": 0.15, "hair": 0.35}     # bump strength of the pore / hair noise in the normal bake
    if "--out" in argv:
        OUT = os.path.abspath(argv[argv.index("--out") + 1])
        UE5_MODELS = os.path.join(OUT, "ue5", "Models"); UE5_TEX = os.path.join(OUT, "ue5", "Textures", "Ahmed")
        UNITY_MODELS = os.path.join(OUT, "unity", "Models"); RENDERS = os.path.join(OUT, "renders")
    else:
        # The project itself: the Unreal models and textures, the Unity copy
        # beside its own port, the renders under Docs. The checkpoint stays
        # out of the tree.
        OUT = os.path.join(HERE, "build")
        UE5_MODELS = os.path.join(PROJECT, "Content", "Models"); UE5_TEX = os.path.join(PROJECT, "Content", "Textures", "Ahmed")
        UNITY_MODELS = os.path.join(UNITY, "Assets", "Resources", "Models"); RENDERS = os.path.join(PROJECT, "Docs", "renders")
    for d in (OUT, UE5_MODELS, UE5_TEX, UNITY_MODELS, RENDERS): os.makedirs(d, exist_ok=True)

    t0 = time.time()
    def stamp(msg): print("%6.1fs  %s" % (time.time() - t0, msg))

    # ---- 1-3: the body, the face, the hair, the garments
    # The build is the slow stage (nine minutes); it is checkpointed to a .blend
    # so the stages after it can be re-run with --resume.
    CHECK = os.path.join(OUT, "built.blend")
    if "--resume" in argv and os.path.exists(CHECK):
        bpy.ops.wm.open_mainfile(filepath=CHECK)
        O = bpy.data.objects
        body, tee, pants = O["Body"], O["Tee"], O["Pants"]
        soles = [o for o in O if o.name.startswith("sole")]
        eyes = [o for o in O if o.name.startswith("eyeball")]
        jl = {k: [Vector(p) for p in v] for k, v in json.load(open(CHECK + ".json")).items()}
        mats = {k: bpy.data.materials["Ahmed_" + k.capitalize()] for k in ("skin", "hair", "shoe", "tee", "pants", "eye")}
        # the checkpoint carries the materials as they were built; the
        # pore bump is the one dial that is tuned after seeing a bake
        for k, strength in PORES.items():
            for n in mats[k].node_tree.nodes:
                if n.type == 'BUMP': n.inputs["Strength"].default_value = strength
        slots = {k: i for i, k in enumerate(("skin", "hair", "shoe"))}
        stamp("resumed from %s" % CHECK)
    else:
        body, trees, eyes, jl = B.build(voxel_scale=3.0 if "--coarse" in argv else 1.0)
        slots = {}
        mats = {"skin": F.shader("Ahmed_Skin", "skin", 0.52, subsurface=0.28, pores=PORES["skin"]),
                # the hair's roughness matches the skin's: the material edge
                # is a staircase of faces, and a roughness step would show it
                "hair": F.shader("Ahmed_Hair", "hair", 0.52, pores=PORES["hair"]),
                "shoe": F.shader("Ahmed_Shoe", "shoe", 0.45, coat=0.2, weave=0.15)}
        for k in ("skin", "hair", "shoe"):
            body.data.materials.append(mats[k]); slots[k] = len(body.data.materials) - 1
        B.assign_by_source(body, trees, slots)
        for p in body.data.polygons:
            if p.center.z < 0.118 and abs(p.center.x) > 0.02: p.material_index = slots["shoe"]
        tee, pants, soles = G.dress(body)
        mats["tee"] = F.shader("Ahmed_Tee", "tee", 0.88, sheen=0.35, weave=0.22)
        mats["pants"] = F.shader("Ahmed_Pants", "pants", 0.82, sheen=0.20, weave=0.16)
        mats["eye"] = F.shader("Ahmed_Eye", "eye", 0.08, coat=1.0)
        tee.data.materials.append(mats["tee"]); pants.data.materials.append(mats["pants"])
        for o in soles: o.data.materials.append(mats["shoe"])
        for e in eyes: e.data.materials.append(mats["eye"])
        stamp("built: body %d tris, tee %d, pants %d" % (sum(len(p.vertices) - 2 for p in body.data.polygons),
              len(tee.data.polygons), len(pants.data.polygons)))
        json.dump({k: [list(p) for p in v] for k, v in jl.items()}, open(CHECK + ".json", "w"))
        bpy.ops.wm.save_as_mainfile(filepath=CHECK)

    # ---- the body under the garments is never seen and pokes through after
    # decimation, so it goes; a band is kept inside every hem.
    def under_garments(c):
        if 1.10 <= c.z <= 1.53 and abs(c.x) < 0.24 and G.tee_region(c): return True
        if 0.16 <= c.z <= 1.04 and G.pants_region(c): return True
        for s in (1, -1):
            sh = Vector((A.Jp("upperarm_l").x * s, A.Jp("upperarm_l").y, A.Jp("upperarm_l").z))
            el = Vector((A.Jp("lowerarm_l").x * s, A.Jp("lowerarm_l").y, A.Jp("lowerarm_l").z))
            t = (c - sh).dot(el - sh) / (el - sh).length_squared
            if -0.25 < t < 0.30 and G._pt_seg(c, sh, el) < 0.095 and c.z > 1.30: return True
        return False
    import bmesh
    def strip_body(body):
        bm = bmesh.new(); bm.from_mesh(body.data)
        drop = [f for f in bm.faces if under_garments(f.calc_center_median())]
        bmesh.ops.delete(bm, geom=drop, context='FACES'); bm.to_mesh(body.data); bm.free()
        return len(drop)
    # the stripped share is spent on the face and hands instead
    covered = sum(1 for p in body.data.polygons if under_garments(p.center)) / max(1, len(body.data.polygons))

    # ---- the sources: the surfaces before decimation, kept for the bake
    def keep_copy(o, name):
        c = o.copy(); c.data = o.data.copy(); c.name = name; bpy.context.collection.objects.link(c); c.hide_render = True; return c
    hi = {"body": keep_copy(body, "Body_hi"), "tee": keep_copy(tee, "Tee_hi"), "pants": keep_copy(pants, "Pants_hi")}

    # ---- 4: the budget. Face and hands keep their density.
    def precious(co):
        if co.z > 1.556 and co.y < 0.03: return True                      # the face
        for s in (1, -1):
            wr = Vector((A.Jp("hand_l").x * s, A.Jp("hand_l").y, A.Jp("hand_l").z))
            if (co - wr).length < 0.22 and co.z < 1.10: return True         # the hands
        return False
    budget = {"body": int(BUDGET * 0.66 / max(0.3, 1.0 - covered)), "tee": int(BUDGET * 0.16), "pants": int(BUDGET * 0.14)}
    tris = {}
    tris["body"] = F.decimate(body, budget["body"], precious)
    tris["tee"] = F.decimate(tee, budget["tee"], lambda c: False)
    tris["pants"] = F.decimate(pants, budget["pants"], lambda c: False)
    for o in soles + eyes: tris[o.name] = sum(len(p.vertices) - 2 for p in o.data.polygons)
    stamp("decimated: " + "  ".join("%s %d" % kv for kv in tris.items()))

    # ---- UVs and paint
    charts = F.body_charts()
    for o in (body, tee, pants): F.assign_uvs(o, charts)
    for o in soles: F.assign_uvs(o, [(lambda c: True, "planar", (Vector((o.location.x, -0.07, 0.01)), Vector((1, 0, 0)), Vector((0, 1, 0)), 0.32), (0.5, 0.0, 1.0, 0.5))])
    for e in eyes:
        ec = sum((v.co for v in e.data.vertices), Vector()) / len(e.data.vertices)    # the primitive keeps its verts in world space
        F.assign_uvs(e, [(lambda c: True, "cyl", (ec + Vector((0, 0, -0.02)), ec + Vector((0, 0, 0.02)), Vector((0, -1, 0)), 0.0, 1.0), (0, 0, 1, 1))])
    F.paint(body, "skin", jl)
    # the body has three materials but one colour attribute: hair and shoe faces repaint their verts
    hair_verts = set(i for p in body.data.polygons if p.material_index == slots["hair"] for i in p.vertices)
    shoe_verts = set(i for p in body.data.polygons if p.material_index == slots["shoe"] for i in p.vertices)
    import numpy as np
    attr = body.data.color_attributes["Col"]
    n = len(body.data.vertices); col = np.empty(n * 4); attr.data.foreach_get("color", col); col = col.reshape(n, 4)
    tmpb = body.copy(); tmpb.data = body.data.copy()
    F.paint(tmpb, "hair", jl); h = np.empty(n * 4); tmpb.data.color_attributes["Col"].data.foreach_get("color", h); h = h.reshape(n, 4)
    F.paint(tmpb, "shoe", jl); sh = np.empty(n * 4); tmpb.data.color_attributes["Col"].data.foreach_get("color", sh); sh = sh.reshape(n, 4)
    bpy.data.meshes.remove(tmpb.data)
    for i in hair_verts: col[i] = h[i]
    for i in shoe_verts: col[i] = sh[i]
    attr.data.foreach_set("color", col.reshape(-1))
    F.paint(tee, "tee", jl); F.paint(pants, "pants", jl)
    for o in soles: F.paint(o, "shoe", jl)
    for e in eyes: F.paint(e, "eye", jl)
    # the high-resolution sources take the same paint
    def paint_body(b):
        F.paint(b, "skin", jl)
        hv = set(i for p in b.data.polygons if p.material_index == slots["hair"] for i in p.vertices)
        sv = set(i for p in b.data.polygons if p.material_index == slots["shoe"] for i in p.vertices)
        at = b.data.color_attributes["Col"]; nn = len(b.data.vertices)
        c = np.empty(nn * 4); at.data.foreach_get("color", c); c = c.reshape(nn, 4)
        tb = b.copy(); tb.data = b.data.copy()
        F.paint(tb, "hair", jl); hh = np.empty(nn * 4); tb.data.color_attributes["Col"].data.foreach_get("color", hh); hh = hh.reshape(nn, 4)
        F.paint(tb, "shoe", jl); ss = np.empty(nn * 4); tb.data.color_attributes["Col"].data.foreach_get("color", ss); ss = ss.reshape(nn, 4)
        bpy.data.meshes.remove(tb.data)
        for i in hv: c[i] = hh[i]
        for i in sv: c[i] = ss[i]
        at.data.foreach_set("color", c.reshape(-1))
    paint_body(hi["body"]); F.paint(hi["tee"], "tee", jl); F.paint(hi["pants"], "pants", jl)
    stamp("painted and unwrapped")

    # ---- bake: one image set per material, through each object's own UVs.
    # The body carries three materials whose charts overlap in UV space (each
    # is its own island layout), so each material bakes from a copy of the body
    # holding only its faces.
    def only(obj, slot):
        c = obj.copy(); c.data = obj.data.copy(); bpy.context.collection.objects.link(c)
        import bmesh
        bm = bmesh.new(); bm.from_mesh(c.data)
        drop = [f for f in bm.faces if f.material_index != slot]
        bmesh.ops.delete(bm, geom=drop, context='FACES'); bm.to_mesh(c.data); bm.free()
        return c
    baked = {}
    for key, obj, size in (("skin", only(body, slots["skin"]), TEX), ("hair", only(body, slots["hair"]), max(512, TEX // 4)),
                           ("shoe", None, max(512, TEX // 4)), ("tee", tee, TEX), ("pants", pants, TEX), ("eye", eyes[0], 512)):
        if key == "shoe":
            obj = only(body, slots["shoe"])
            # the soles bake into the same image afterwards: same material, own charts
        source = {"skin": hi["body"], "hair": hi["body"], "shoe": hi["body"], "tee": hi["tee"], "pants": hi["pants"]}.get(key)
        baked[key] = F.bake_set(obj, mats[key], size, UE5_TEX, {"skin": "Ahmed_Skin", "hair": "Ahmed_Hair", "shoe": "Ahmed_Shoe", "tee": "Ahmed_Tee", "pants": "Ahmed_Pants", "eye": "Ahmed_Eye"}[key],
                                maps=("albedo", "normal", "roughness") if key != "eye" else ("albedo",), source=source,
                                normal_size=max(512, size // 2))
        if obj not in (tee, pants) and obj not in eyes: bpy.data.objects.remove(obj, do_unlink=True)
        stamp("baked %s at %d" % (key, size))
    for k, m in mats.items(): F.wire_textures(m, baked[k])
    for o in hi.values(): bpy.data.objects.remove(o, do_unlink=True)

    # ---- rig
    rig = legacy.build_armature()
    nf = R.add_finger_bones(rig, jl)
    R.bind_all(body, [tee, pants] + soles + eyes, rig)
    stamp("stripped %d body faces under the garments" % strip_body(body))
    mesh = R.join_all(body, [tee, pants] + soles + eyes); mesh.name = mesh.data.name = "Ahmed"
    legacy.weight_orphans(mesh, rig)
    legacy.add_ik(rig)
    stamp("rigged: %d bones (%d finger)" % (len(rig.data.bones), nf))

    # ---- poses and renders
    legacy.build_studio()
    targets, poles, report = legacy.limb_targets(rig, mesh, legacy.GUARD, plant=("l", "r"))
    legacy.print_pose_report("guard", ("l", "r"), report)
    legacy.pose(rig, legacy.GUARD, targets, poles); R.curl_fingers(rig, 78)
    legacy.add_camera((1.55, -3.35, 1.24), look_at=Vector((0, 0, 0.90)), lens=62)
    legacy.render(os.path.join(RENDERS, "ahmed-guard-3d.png"), samples=24 if FAST else 64)
    targets, poles, report = legacy.limb_targets(rig, mesh, legacy.KICK, plant=("l",))
    legacy.print_pose_report("kick", ("l",), report)
    legacy.pose(rig, legacy.KICK, targets, poles); R.curl_fingers(rig, 78)
    legacy.add_camera((3.00, -2.45, 1.22), look_at=Vector((0.14, 0, 0.96)), lens=58)
    legacy.render(os.path.join(RENDERS, "ahmed-kick-3d.png"), samples=24 if FAST else 64)
    legacy.mute_ik(rig, True); legacy.pose(rig, {}); R.curl_fingers(rig, 0)
    legacy.add_camera((0.35, -3.60, 1.05), look_at=Vector((0, 0, 0.90)), lens=58)
    legacy.render(os.path.join(RENDERS, "ahmed-apose-3d.png"), samples=24 if FAST else 64)
    legacy.add_camera((0.62, -1.05, 1.60), look_at=Vector((0, 0, 1.62)), lens=85)
    legacy.render(os.path.join(RENDERS, "ahmed-face-3d.png"), samples=24 if FAST else 64, res=(760, 760))
    stamp("rendered")

    # ---- export, then read it back
    total = sum(len(p.vertices) - 2 for p in mesh.data.polygons)
    gltf, fbx, ufbx = R.export_all(rig, mesh, UE5_MODELS, UNITY_MODELS, UE5_TEX, None)
    summary = dict(tris=total, verts=len(mesh.data.vertices), bones=len(rig.data.bones), finger_bones=nf,
                   materials=[m.name for m in mesh.data.materials], textures=sorted(os.listdir(UE5_TEX)),
                   gltf=os.path.getsize(gltf), fbx=os.path.getsize(fbx), unity_fbx=os.path.getsize(ufbx))
    stamp("exported: %d tris, %d bones" % (total, summary["bones"]))
    summary["roundtrip_gltf"] = R.verify_roundtrip(gltf)
    summary["roundtrip_fbx_unity"] = R.verify_roundtrip(ufbx)
    json.dump(summary, open(os.path.join(OUT, "summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))
    stamp("done")
