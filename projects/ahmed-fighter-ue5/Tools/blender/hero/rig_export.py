"""Stage 5-6: the skeleton (the mannequin's 24 plus its 30 finger bones,
root and the IK targets), binding, the guard and kick poses, and the two
exports -- then the exported files are imported back into a fresh scene
and counted, which is the only proof available here that what left is
what arrived."""
import bpy, math, os, sys, time
from mathutils import Vector
import build_ahmed as legacy

FINGERS = [("index", "f0"), ("middle", "f1"), ("ring", "f2"), ("pinky", "f3")]

def add_finger_bones(arm, joints_l):
    """Mannequin finger bones: index_01_l .. pinky_03_l and thumb_01..03,
    from the hand joint table the hand was built from. The right side is
    the mirror. Deforming, parented to hand_<side>."""
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    made = 0
    for side, s in (("l", 1), ("r", -1)):
        hand = eb["hand_" + side]
        def M(v): return Vector((v.x * s, v.y, v.z))
        for mname, key in FINGERS + [("thumb", "thumb")]:
            pts = joints_l[key]
            parent = hand
            for k in range(3):
                b = eb.new("%s_%02d_%s" % (mname, k + 1, side))
                b.head = M(pts[k]); b.tail = M(pts[k + 1])
                b.parent = parent; b.use_connect = (k > 0); b.use_deform = True
                parent = b; made += 1
    bpy.ops.object.mode_set(mode='OBJECT')
    return made

def bind_all(body, garments, arm):
    """Heat on the body; the garments take the body's weights by proximity,
    which is what a shell 5 mm off the skin should do -- heat on a shell
    finds its own answer and it is not the body's."""
    legacy.bind(body, arm)
    for g in garments:
        g.parent = arm
        mod = g.modifiers.new("Skin", "ARMATURE"); mod.object = arm
        dt = g.modifiers.new("Weights", "DATA_TRANSFER"); dt.object = body
        dt.use_vert_data = True; dt.data_types_verts = {'VGROUP_WEIGHTS'}; dt.vert_mapping = 'POLYINTERP_NEAREST'
        dt.layers_vgroup_select_src = 'ALL'; dt.layers_vgroup_select_dst = 'NAME'
        bpy.context.view_layer.objects.active = g
        for vg in body.vertex_groups: 
            if vg.name not in g.vertex_groups: g.vertex_groups.new(name=vg.name)
        bpy.ops.object.datalayout_transfer(modifier="Weights")
        bpy.ops.object.modifier_apply(modifier="Weights")
        # the armature modifier must come first for the join to keep it
        while g.modifiers.find("Skin") > 0: bpy.ops.object.modifier_move_up(modifier="Skin")

def join_all(body, others):
    bpy.ops.object.select_all(action='DESELECT')
    for o in others: o.select_set(True)
    body.select_set(True); bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    return body

def curl_fingers(arm, degrees):
    """Close the fists for the fight poses: every finger joint bends toward
    the palm by the same angle, the thumb by less."""
    for pb in arm.pose.bones:
        n = pb.name
        if any(n.startswith(f + "_") for f, _ in FINGERS):
            pb.rotation_mode = 'XYZ'; pb.rotation_euler = (math.radians(-degrees), 0, 0)
        elif n.startswith("thumb_"):
            pb.rotation_mode = 'XYZ'; pb.rotation_euler = (math.radians(-degrees * 0.5), 0, 0)
    bpy.context.view_layer.update()

def export_all(arm, mesh, out_ue5, out_unity, textures_ue5, textures_unity):
    os.makedirs(out_ue5, exist_ok=True); os.makedirs(out_unity, exist_ok=True)
    # Only the rig and the mesh leave. The IK pole targets are children of
    # the rig and glTF takes a selected object's children along, so they go
    # first -- the constraints are muted for export and do not travel anyway.
    for o in [o for o in bpy.data.objects if o.type == 'MESH' and o is not mesh]:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True); mesh.select_set(True)
    bpy.context.view_layer.objects.active = arm
    # Nothing embeds its textures. The bake has just written them next door
    # into Content/Textures/Ahmed and both engines import a PNG as an asset
    # of their own anyway, so an embedded copy is a second and a third 34 MB
    # of the same sixteen files -- inside a container, where git cannot even
    # see that they are the same. Both formats reference them instead.
    gltf = os.path.join(out_ue5, "Ahmed.gltf")
    bpy.ops.export_scene.gltf(filepath=gltf, export_format="GLTF_SEPARATE", use_selection=True,
                              export_yup=True, export_apply=True, export_keep_originals=True)
    fbx = os.path.join(out_ue5, "Ahmed.fbx")
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, apply_unit_scale=True, global_scale=1.0,
                             apply_scale_options="FBX_SCALE_UNITS", add_leaf_bones=False,
                             primary_bone_axis="Y", secondary_bone_axis="X", object_types={"ARMATURE", "MESH"},
                             mesh_smooth_type="FACE", bake_space_transform=False,
                             path_mode='RELATIVE', embed_textures=False)
    ufbx = os.path.join(out_unity, "Ahmed.fbx")
    bpy.ops.export_scene.fbx(filepath=ufbx, use_selection=True, apply_unit_scale=True, global_scale=1.0,
                             apply_scale_options="FBX_SCALE_NONE", add_leaf_bones=False,
                             primary_bone_axis="Y", secondary_bone_axis="X", object_types={"ARMATURE", "MESH"},
                             mesh_smooth_type="FACE", axis_forward="-Z", axis_up="Y", bake_space_transform=True,
                             path_mode='COPY', embed_textures=False)
    return gltf, fbx, ufbx

def verify_gltf(path):
    """Read the glTF's own JSON: what an engine's importer sees, with no
    Blender importer in between (Blender's adds a bone-shape mesh of its
    own). Every image must resolve to a file that is really there, which is
    the thing that can go wrong once they are not embedded."""
    import json
    j = json.load(open(path))
    missing = [i.get("uri") for i in j.get("images", [])
               if "uri" not in i or not os.path.exists(os.path.join(os.path.dirname(path), i["uri"]))]
    assert not missing, "the glTF points at textures that are not there: %s" % missing
    acc = j["accessors"]
    tris = sum(acc[p["indices"]]["count"] // 3 for m in j["meshes"] for p in m["primitives"] if "indices" in p)
    zs = [(acc[p["attributes"]["POSITION"]]["min"][1], acc[p["attributes"]["POSITION"]]["max"][1])
          for m in j["meshes"] for p in m["primitives"]]        # glTF is Y-up
    return dict(armatures=len(j.get("skins", [])), bones=sum(len(s["joints"]) for s in j.get("skins", [])),
                meshes=[m["name"] for m in j["meshes"]], tris=tris, materials=len(j.get("materials", [])),
                images=len(j.get("images", [])), images_resolve=True,
                height=max(z[1] for z in zs) - min(z[0] for z in zs))

def verify_roundtrip(path):
    """Import into a fresh scene and count what came back."""
    if path.endswith((".gltf", ".glb")): return verify_gltf(path)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    bones = sum(len(a.data.bones) for a in arms)
    tris = sum(sum(len(p.vertices) - 2 for p in m.data.polygons) for m in meshes)
    mats = set(); imgs = set()
    for m in meshes:
        for slot in m.material_slots:
            if slot.material:
                mats.add(slot.material.name)
                if slot.material.node_tree:
                    for n in slot.material.node_tree.nodes:
                        if n.type == 'TEX_IMAGE' and n.image: imgs.add((n.image.name, n.image.size[0]))
    zs = [ (m.matrix_world @ v.co).z for m in meshes for v in m.data.vertices ]
    return dict(armatures=len(arms), bones=bones, meshes=[m.name for m in meshes], tris=tris, materials=len(mats), images=sorted(imgs),
                height=(max(zs) - min(zs)) if zs else 0)
