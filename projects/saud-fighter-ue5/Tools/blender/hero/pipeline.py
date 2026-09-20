"""A fighter, rebuilt: the whole pipeline end to end, for whichever man the
roster names.

    anatomy   the body as lofted cross-sections and lofted limbs
    assembly  the two-pass voxel union, the face sculpt, the hair, the eyes
    garments  the tee and the track pants as shells off the body
    finish    the budget, the UVs, the paint, the bake
    rig_export the skeleton with fingers, the binding, the exports
    rig_full_ik the control rig an animator poses him through

Run through build_saud.py for the hero, build_fighters.py for anyone:

    python3 build_saud.py              the hero: 4K colour, 2K normals, 64-sample renders
    python3 build_saud.py --fast       1K textures, quick renders, for a look
    python3 build_saud.py --resume     skip the nine-minute build, reload it
    python3 build_saud.py --coarse     a rough body, to check the later stages
    python3 build_saud.py --out DIR    write somewhere else than the project

ONE BODY, EVERY MAN. Everything up to the bake runs at Saud's coordinates
-- the one set every absolute constant in hero/ was written for -- and the
finished, painted, baked mesh is then taken to the man's own size through
anatomy.scale_to, the browser build's own sc / build mapping, before the
skeleton is built on it. What differs between two men on that body is his
palette and kit (read from the roster), his hair, his beard, and a few
face amplitudes (FACES below), which are the only numbers in this file the
browser does not own.
"""
import bpy, os, sys, time, math, json
from mathutils import Vector
import build_saud as legacy
from . import anatomy as A, assembly as B, garments as G, finish as F, rig_export as R

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
UNITY = os.path.abspath(os.path.join(PROJECT, "..", "ahmed-fighter-unity"))

# The mannequin's skeleton, which every fighter has to export exactly:
# 24 deforming, root, 7 IK, 30 finger. A control bone in the export would
# break the retarget that makes these models useful, so the export asserts
# this set and nothing else.
MANNEQUIN = {
    "root", "pelvis", "spine_01", "spine_02", "spine_03", "neck_01", "head",
    "ik_foot_root", "ik_foot_l", "ik_foot_r", "ik_hand_root", "ik_hand_gun", "ik_hand_l", "ik_hand_r",
} | {"%s_%s" % (b, s) for s in ("l", "r") for b in
     ("clavicle", "upperarm", "lowerarm", "hand", "hand_end", "thigh", "calf", "foot", "ball")} \
  | {"%s_%02d_%s" % (f, k, s) for s in ("l", "r") for f in ("index", "middle", "ring", "pinky", "thumb") for k in (1, 2, 3)}
assert len(MANNEQUIN) == 62

# How one man's face differs from another's on the same skull: factors on
# the amplitudes in sculpt.FACE. These are the ONE set of numbers here the
# browser build does not own -- it draws every head from one skull and tells
# the men apart by hair, beard and kit (README: "Silhouette does the work")
# -- and they are kept small and few for that reason: a heavier brow and a
# wider jaw on the man the roster calls stocky and bearded, a slighter chin
# on the one it calls the smallest man on screen. Saud is the skull as
# sculpted.
FACES = {
    # tip 1.05, not 1.10: at 1.10 the nose field peaks at 30.1 mm and
    # sculpt.check_profile holds every man to 20-30 (a real male nose)
    "brawler": dict(brow=1.35, glabella=1.20, jaw1=1.30, jaw2=1.30, jaw3=1.30, chin=1.25,
                    masseter=1.50, cheekbone=1.15, tip=1.05, hollow=0.60),
    "thug":    dict(chin=0.85, brow=0.90, cheekbone=0.90, tip=0.95, masseter=0.80),
}


def run(argv=None):
    """The hero, as build_saud.py has always built him."""
    from . import roster
    return build_fighter(roster.spec("saud"), argv)


def build_fighter(spec, argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    name, low = spec["name"], spec["name"].lower()
    FAST = "--fast" in argv
    TEX = 1024 if FAST else 4096
    BUDGET = 60000
    PORES = {"skin": 0.15, "hair": 0.35}     # bump strength of the pore / hair noise in the normal bake
    pal = F.palette_for(spec)
    assert pal["hair"] is not None, "%s is bald and this pipeline has no bald head yet" % name
    face_scale = FACES.get(spec["kind"])
    hair_style = "quiff" if spec["look"].get("quiff") else "crop"
    if "--out" in argv:
        OUT = os.path.abspath(argv[argv.index("--out") + 1])
        UE5_MODELS = os.path.join(OUT, "ue5", "Models"); UE5_TEX = os.path.join(OUT, "ue5", "Textures", name)
        UNITY_MODELS = os.path.join(OUT, "unity", "Models"); RENDERS = os.path.join(OUT, "renders"); RIGS = OUT
    else:
        # The project itself: the Unreal models and textures, the Unity copy
        # beside its own port, the renders under Docs, the animator's .blend
        # in Tools/blender/rigs. The checkpoint stays out of the tree.
        OUT = os.path.join(HERE, "build")
        UE5_MODELS = os.path.join(PROJECT, "Content", "Models"); UE5_TEX = os.path.join(PROJECT, "Content", "Textures", name)
        UNITY_MODELS = os.path.join(UNITY, "Assets", "Resources", "Models"); RENDERS = os.path.join(PROJECT, "Docs", "renders")
        RIGS = os.path.join(os.path.dirname(HERE), "rigs")
    os.makedirs(RIGS, exist_ok=True)
    # Unreal only unless asked: the Unity port is frozen (see ../../CLAUDE.md),
    # and rebuilding the hero should not drop a second FBX into a tree nobody
    # develops. `--unity` puts it back.
    if "--unity" not in argv:
        UNITY_MODELS = None
    for d in (OUT, UE5_MODELS, UE5_TEX, RENDERS): os.makedirs(d, exist_ok=True)
    if UNITY_MODELS: os.makedirs(UNITY_MODELS, exist_ok=True)

    t0 = time.time()
    def stamp(msg): print("%6.1fs  %s" % (time.time() - t0, msg))
    print("building %s (%s): sc %.2f build %.2f, hair %s, beard %s" % (
        name, spec["display"], spec["sc"], spec["look"].get("build", 1.0), hair_style,
        "yes" if pal["beard"] is not None else "no"))

    # ---- 1-3: the body, the face, the hair, the garments
    # The build is the slow stage (nine minutes); it is checkpointed to a .blend
    # so the stages after it can be re-run with --resume.
    CHECK = os.path.join(OUT, "built.blend" if low == "saud" else "built_%s.blend" % low)
    if "--resume" in argv and os.path.exists(CHECK):
        bpy.ops.wm.open_mainfile(filepath=CHECK)
        O = bpy.data.objects
        body, tee, pants = O["Body"], O["Tee"], O["Pants"]
        soles = [o for o in O if o.name.startswith("sole")]
        eyes = [o for o in O if o.name.startswith("eyeball")]
        jl = {k: [Vector(p) for p in v] for k, v in json.load(open(CHECK + ".json")).items()}
        mats = {k: bpy.data.materials["%s_%s" % (name, k.capitalize())] for k in ("skin", "hair", "shoe", "tee", "pants", "eye")}
        # the checkpoint carries the materials as they were built; the
        # pore bump is the one dial that is tuned after seeing a bake
        for k, strength in PORES.items():
            for n in mats[k].node_tree.nodes:
                if n.type == 'BUMP': n.inputs["Strength"].default_value = strength
        slots = {k: i for i, k in enumerate(("skin", "hair", "shoe"))}
        stamp("resumed from %s" % CHECK)
    else:
        body, trees, eyes, jl = B.build(voxel_scale=3.0 if "--coarse" in argv else 1.0,
                                        face_scale=face_scale, hair_style=hair_style)
        slots = {}
        mats = {"skin": F.shader("%s_Skin" % name, "skin", 0.52, subsurface=0.28, pores=PORES["skin"]),
                # the hair's roughness matches the skin's: the material edge
                # is a staircase of faces, and a roughness step would show it
                "hair": F.shader("%s_Hair" % name, "hair", 0.52, pores=PORES["hair"]),
                "shoe": F.shader("%s_Shoe" % name, "shoe", 0.45, coat=0.2, weave=0.15)}
        for k in ("skin", "hair", "shoe"):
            body.data.materials.append(mats[k]); slots[k] = len(body.data.materials) - 1
        B.assign_by_source(body, trees, slots)
        for p in body.data.polygons:
            if p.center.z < 0.118 and abs(p.center.x) > 0.02: p.material_index = slots["shoe"]
        tee, pants, soles = G.dress(body)
        mats["tee"] = F.shader("%s_Tee" % name, "tee", 0.88, sheen=0.35, weave=0.22)
        mats["pants"] = F.shader("%s_Pants" % name, "pants", 0.82, sheen=0.20, weave=0.16)
        mats["eye"] = F.shader("%s_Eye" % name, "eye", 0.08, coat=1.0)
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
        # to 1.50, not 1.53: the collar ring's lowest point is at 1.507, and a
        # strip that ran to 1.53 left the tee's black inside showing through
        # the 26 mm between the ring and the neck in every face render
        if 1.10 <= c.z <= 1.50 and abs(c.x) < 0.24 and G.tee_region(c): return True
        if 0.16 <= c.z <= 1.04 and G.pants_region(c): return True
        for s in (1, -1):
            sh = Vector((A.Jp("upperarm_l").x * s, A.Jp("upperarm_l").y, A.Jp("upperarm_l").z))
            el = Vector((A.Jp("lowerarm_l").x * s, A.Jp("lowerarm_l").y, A.Jp("lowerarm_l").z))
            t = (c - sh).dot(el - sh) / (el - sh).length_squared
            if -0.25 < t < 0.30 and G._pt_seg(c, sh, el) < 0.095 and c.z > 1.30: return True
        return False
    import bmesh
    def strip_body(body, drop_idx):
        bm = bmesh.new(); bm.from_mesh(body.data); bm.faces.ensure_lookup_table()
        drop = [bm.faces[i] for i in drop_idx]
        bmesh.ops.delete(bm, geom=drop, context='FACES'); bm.to_mesh(body.data); bm.free()
        return len(drop)
    # the stripped share is spent on the face and hands instead
    covered = sum(1 for p in body.data.polygons if under_garments(p.center)) / max(1, len(body.data.polygons))

    # ---- the sources: the surfaces before decimation, kept for the bake
    def keep_copy(o, name_):
        c = o.copy(); c.data = o.data.copy(); c.name = name_; bpy.context.collection.objects.link(c); c.hide_render = True; return c
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
    # The faces under the garments, decided HERE, at the canonical
    # coordinates every region test was written for. They are deleted after
    # the bind (bone heat wants the closed body), by which time the body has
    # been taken to the man's own size and `under_garments` would be asking
    # about a tee that is no longer where its constants say.
    hidden_faces = [p.index for p in body.data.polygons if under_garments(p.center)]

    # ---- UVs and paint
    charts = F.body_charts()
    for o in (body, tee, pants): F.assign_uvs(o, charts)
    for o in soles: F.assign_uvs(o, [(lambda c: True, "planar", (Vector((o.location.x, -0.07, 0.01)), Vector((1, 0, 0)), Vector((0, 1, 0)), 0.32), (0.5, 0.0, 1.0, 0.5))])
    for e in eyes:
        ec = sum((v.co for v in e.data.vertices), Vector()) / len(e.data.vertices)    # the primitive keeps its verts in world space
        F.assign_uvs(e, [(lambda c: True, "cyl", (ec + Vector((0, 0, -0.02)), ec + Vector((0, 0, 0.02)), Vector((0, -1, 0)), 0.0, 1.0), (0, 0, 1, 1))])
    F.paint(body, "skin", jl, pal)
    # the body has three materials but one colour attribute: hair and shoe faces repaint their verts
    hair_verts = set(i for p in body.data.polygons if p.material_index == slots["hair"] for i in p.vertices)
    shoe_verts = set(i for p in body.data.polygons if p.material_index == slots["shoe"] for i in p.vertices)
    import numpy as np
    attr = body.data.color_attributes["Col"]
    n = len(body.data.vertices); col = np.empty(n * 4); attr.data.foreach_get("color", col); col = col.reshape(n, 4)
    tmpb = body.copy(); tmpb.data = body.data.copy()
    F.paint(tmpb, "hair", jl, pal); h = np.empty(n * 4); tmpb.data.color_attributes["Col"].data.foreach_get("color", h); h = h.reshape(n, 4)
    F.paint(tmpb, "shoe", jl, pal); sh = np.empty(n * 4); tmpb.data.color_attributes["Col"].data.foreach_get("color", sh); sh = sh.reshape(n, 4)
    bpy.data.meshes.remove(tmpb.data)
    for i in hair_verts: col[i] = h[i]
    for i in shoe_verts: col[i] = sh[i]
    attr.data.foreach_set("color", col.reshape(-1))
    F.paint(tee, "tee", jl, pal); F.paint(pants, "pants", jl, pal)
    for o in soles: F.paint(o, "shoe", jl, pal)
    for e in eyes: F.paint(e, "eye", jl, pal)
    # the high-resolution sources take the same paint
    def paint_body(b):
        F.paint(b, "skin", jl, pal)
        hv = set(i for p in b.data.polygons if p.material_index == slots["hair"] for i in p.vertices)
        sv = set(i for p in b.data.polygons if p.material_index == slots["shoe"] for i in p.vertices)
        at = b.data.color_attributes["Col"]; nn = len(b.data.vertices)
        c = np.empty(nn * 4); at.data.foreach_get("color", c); c = c.reshape(nn, 4)
        tb = b.copy(); tb.data = b.data.copy()
        F.paint(tb, "hair", jl, pal); hh = np.empty(nn * 4); tb.data.color_attributes["Col"].data.foreach_get("color", hh); hh = hh.reshape(nn, 4)
        F.paint(tb, "shoe", jl, pal); ss = np.empty(nn * 4); tb.data.color_attributes["Col"].data.foreach_get("color", ss); ss = ss.reshape(nn, 4)
        bpy.data.meshes.remove(tb.data)
        for i in hv: c[i] = hh[i]
        for i in sv: c[i] = ss[i]
        at.data.foreach_set("color", c.reshape(-1))
    paint_body(hi["body"]); F.paint(hi["tee"], "tee", jl, pal); F.paint(hi["pants"], "pants", jl, pal)
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
    base_of = {"skin": "%s_Skin" % name, "hair": "%s_Hair" % name, "shoe": "%s_Shoe" % name,
               "tee": "%s_Tee" % name, "pants": "%s_Pants" % name, "eye": "%s_Eye" % name}
    for key, obj, size in (("skin", only(body, slots["skin"]), TEX), ("hair", only(body, slots["hair"]), max(512, TEX // 4)),
                           ("shoe", None, max(512, TEX // 4)), ("tee", tee, TEX), ("pants", pants, TEX), ("eye", eyes[0], 512)):
        if key == "shoe":
            obj = only(body, slots["shoe"])
            # the soles bake into the same images below: same material, own charts
        source = {"skin": hi["body"], "hair": hi["body"], "shoe": hi["body"], "tee": hi["tee"], "pants": hi["pants"]}.get(key)
        baked[key] = F.bake_set(obj, mats[key], size, UE5_TEX, base_of[key],
                                maps=("albedo", "normal", "roughness") if key != "eye" else ("albedo", "roughness"), source=source,
                                # The skin's normal is the only one carrying authored
                                # structure rather than pore dither, and at half size a
                                # face texel is 1.36 x 2.00 mm -- the mouthline is 0.9 mm
                                # and the lash bar 1.6, so both sat at or under one texel
                                # in the direction that matters. Full size for the skin,
                                # half for everything else, where the comment in bake_set
                                # about dither still holds.
                                normal_size=(size if key == "skin" else max(512, size // 2)))
        if key == "shoe":
            # the soles: the same material, their own charts (u > 0.5, v < 0.5),
            # baked into the same three images from their own paint. Without
            # this that quadrant stayed black -- colour black, roughness 0 --
            # and every sole shipped as a mirror.
            for o in soles:
                F.bake_set(o, mats["shoe"], size, UE5_TEX, base_of["shoe"], source=None, images=baked["shoe"],
                           normal_size=max(512, size // 2))
        if key == "eye":
            # Same reason as the face: the iris is 11 mm across and the limbal
            # ring 0.4 mm, against 2.8 degrees between the globe's vertices.
            import numpy as _np
            ctr = _np.array([v.co[:] for v in obj.data.vertices]).mean(axis=0)
            stamp("repainted %d eye texels" % F.repaint_eye(obj, baked[key], size, ctr, B.EYE_R))
        if key == "skin":
            # The bake can only carry what the vertices hold, and the head has
            # 3.1 mm between vertices against a 0.9 mm texel. Repaint the face
            # from hero.face at the texture's own resolution.
            painted, relief = F.repaint_head(obj, baked[key], size, pal)
            assert painted > 0, "the face repaint wrote nothing -- the head chart did not rasterise"
            stamp("repainted %d face texels, relief %.2f coherent levels in the normal" % (painted, relief))
        if obj not in (tee, pants) and obj not in eyes: bpy.data.objects.remove(obj, do_unlink=True)
        stamp("baked %s at %d" % (key, size))
    for k, m in mats.items(): F.wire_textures(m, baked[k])
    for o in hi.values(): bpy.data.objects.remove(o, do_unlink=True)

    # ---- his own size. Everything above ran at Saud's coordinates; from
    # here on the mesh and the joints are the man's.
    factors = A.scale_to([body, tee, pants] + soles + eyes, jl, spec["sc"], spec["look"].get("build", 1.0))

    # ---- rig
    rig = legacy.build_armature()
    rig.name = "%s_Rig" % name
    if low == "saud":
        # The boss clips in Content/Animation/Bosses are keyed to the
        # skeleton build_armature makes from the joint table as it is. Saud
        # goes through the same field as everyone else at factors of one, so
        # his skeleton must come out exactly that one -- checked, not assumed.
        ref = legacy.build_armature(); ref.name = "Reference_Rig"
        worst = max((rig.data.bones[b.name].head_local - b.head_local).length for b in ref.data.bones)
        worst = max(worst, max((rig.data.bones[b.name].tail_local - b.tail_local).length for b in ref.data.bones))
        assert {b.name for b in rig.data.bones} == {b.name for b in ref.data.bones} and worst < 1e-6, \
            "Saud's skeleton drifted %.2e m from the one the boss clips are keyed to" % worst
        bpy.data.objects.remove(ref, do_unlink=True)
        stamp("skeleton identical to the boss clips' (drift %.1e m)" % worst)
    nf = R.add_finger_bones(rig, jl)
    R.bind_all(body, [tee, pants] + soles + eyes, rig)
    stamp("stripped %d body faces under the garments" % strip_body(body, hidden_faces))
    mesh = R.join_all(body, [tee, pants] + soles + eyes); mesh.name = mesh.data.name = name
    legacy.weight_orphans(mesh, rig)
    legacy.add_ik(rig)
    stamp("rigged: %d bones (%d finger)" % (len(rig.data.bones), nf))

    # ---- poses and renders. The poses are always struck (the report they
    # print is a check); --no-render skips the four Cycles renders.
    legacy.build_studio()
    look_z = 0.90 * factors["h"]
    def shot(filename, cam, look_at, lens, res=(760, 1000)):
        if "--no-render" in argv: return
        legacy.add_camera(cam, look_at=Vector(look_at), lens=lens)
        legacy.render(os.path.join(RENDERS, "%s-%s-3d.png" % (low, filename)), samples=24 if FAST else 64, res=res)
    targets, poles, report = legacy.limb_targets(rig, mesh, legacy.GUARD, plant=("l", "r"))
    legacy.print_pose_report("guard", ("l", "r"), report)
    legacy.pose(rig, legacy.GUARD, targets, poles); R.curl_fingers(rig, 10)
    shot("guard", (1.55, -3.35, 1.24), (0, 0, look_z), 62)
    targets, poles, report = legacy.limb_targets(rig, mesh, legacy.KICK, plant=("l",))
    legacy.print_pose_report("kick", ("l",), report)
    legacy.pose(rig, legacy.KICK, targets, poles); R.curl_fingers(rig, 10)
    shot("kick", (3.00, -2.45, 1.22), (0.14, 0, 0.96 * factors["h"]), 58)
    legacy.mute_ik(rig, True); legacy.pose(rig, {}); R.curl_fingers(rig, 0)
    shot("apose", (0.35, -3.60, 1.05), (0, 0, look_z), 58)
    shot("face", (0.62, -1.05, 1.60 * factors["h"]), (0, 0, 1.62 * factors["h"]), 85, res=(760, 760))
    legacy.mute_ik(rig, False)
    stamp("posed" if "--no-render" in argv else "rendered")

    # ---- the control rig, the animator's file, then the verification. The
    # file is saved BEFORE verify() so that a rig that fails its own checks
    # is on disk to be looked at, not gone with the process.
    control = None
    blend = os.path.join(RIGS, "%s.blend" % name)
    if "--no-control-rig" not in argv:
        import rig_full_ik as CR
        control = CR.build(rig, mesh)
        bpy.ops.wm.save_as_mainfile(filepath=blend)
        stamp("saved %s" % blend)
        CR.verify(rig, mesh)
        stamp("control rig: %d control bones, verified" % control["controls"])
    else:
        bpy.ops.wm.save_as_mainfile(filepath=blend)
        stamp("saved %s" % blend)

    # ---- export, then read it back. The control layer never leaves: what
    # ships is the mannequin's skeleton exactly, or the retarget breaks.
    if control:
        CR.strip_for_export(rig, mesh)
    names = {b.name for b in rig.data.bones}
    assert names == MANNEQUIN, "the export skeleton is not the mannequin's: extra %s, missing %s" % (
        sorted(names - MANNEQUIN), sorted(MANNEQUIN - names))
    # One skeleton, one name. An engine keys a shared skeleton on the FBX's
    # armature node as well as its bone names, and the boss clips left as
    # Saud_Rig; every man exports under it, whatever his .blend calls him.
    rig.name = "Saud_Rig"; rig.data.name = "SaudSkeleton"
    total = sum(len(p.vertices) - 2 for p in mesh.data.polygons)
    gltf, fbx, ufbx = R.export_all(rig, mesh, UE5_MODELS, UNITY_MODELS, UE5_TEX, None, name=name)
    summary = dict(name=name, kind=spec["kind"], sc=spec["sc"], build=spec["look"].get("build", 1.0),
                   factors=factors, tris=total, verts=len(mesh.data.vertices), bones=len(rig.data.bones), finger_bones=nf,
                   materials=[m.name for m in mesh.data.materials], textures=sorted(os.listdir(UE5_TEX)),
                   gltf=os.path.getsize(gltf), fbx=os.path.getsize(fbx),
                   unity_fbx=os.path.getsize(ufbx) if ufbx else None,
                   control_rig=control)
    stamp("exported: %d tris, %d bones%s" % (total, summary["bones"],
                                             "" if ufbx else "  (Unreal only; --unity adds the Unity FBX)"))
    summary["roundtrip_gltf"] = R.verify_roundtrip(gltf)
    back = R.gltf_bone_names(gltf)
    assert back == MANNEQUIN, "the glTF's skeleton is not the mannequin's: %s" % sorted(back ^ MANNEQUIN)[:8]
    if ufbx:
        summary["roundtrip_fbx_unity"] = R.verify_roundtrip(ufbx)
    json.dump(summary, open(os.path.join(OUT, "%s_summary.json" % low), "w"), indent=1)
    if low == "saud":
        json.dump(summary, open(os.path.join(OUT, "summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))
    stamp("done")
    return summary
