"""
Every texture the game imports, set the way its data was written, and the
surfaces that sample them (2026-10-03, Riyadh; asked as "improve colors
accuracy", settled as: the textures import right).

    python3 Tools/look/surfaces.py            the checks, on the files
    python3 Tools/look/surfaces.py --bite     each rule broken once
    (in the editor) py Tools/look/surfaces.py  imports every texture, sets
                                             it, builds M_Surface and an
                                             instance per set, and puts them
                                             on every mesh slot they belong to

WHAT WAS WRONG. Blender writes a colour map in sRGB and every other map --
normal, roughness, metallic, mask -- as plain data (Non-Color, finish.py,
build_souq.py, build_iron_arm.py). Unreal imports a PNG as sRGB colour unless
told otherwise, and nothing here told it: the 51 roughness maps would have
read through the sRGB curve (a stored 0.5 read as 0.21, every surface far
shinier than it was painted), the metallic and the mask likewise. And the
materials were left to the FBX importer, which builds a sampler of its own
choosing for what it recognises and nothing for what it does not; which of a
Principled roughness link it recognises is not known from here.

WHAT IT DOES. One table, ROLES, says what each kind of map is: its sRGB, its
compression and the sampler that reads it. Every PNG under Content/Textures
is named T_<Set>_<Part>_<Role>.png and is imported once to
/Game/Textures/<folder>/ and set from its role. One material, M_Surface,
samples a colour map as colour, a normal map as a normal and a roughness map
as linear data (the sampler and the texture agree by construction, so the
material cannot fail to compile on them), with a metallic and an emissive
the place's own; MI_<Set>_<Part> sets it per texture set; and every mesh
slot that names a set -- a man's "<Man>_<Part>", the souq's
"M_Souq_<Part>" -- takes its instance. The souq's constants (the iron's
metal, the ember's and the lantern glass's light) are read from
build_souq.py's own tables, not copied. Saud_IronArm is a LAYER over his
skin, not a surface (its blend is the skin material's, still not built --
"IRON ARM", CLAUDE.md); its maps are imported and set like any other.

CHECKED, without an engine: every texture file has a role; what is in each
file is what its role says (a normal map is one, a data map is grey); every
surface set has its colour and roughness; every data role imports linear,
every normal compresses as one and every sampler agrees with its texture;
and, read back through Blender's FBX importer, every man's and the souq's
material slots are exactly the sets on disk and each slot's maps were linked
to the inputs their names say. --bite breaks each.

UNVERIFIED. No editor has run build(). The asset paths and property names
(srgb, compression_settings, sampler_type, the MaterialEditingLibrary
calls, a SkeletalMesh's `materials` array, /Engine/EngineMaterials/
FlatNormal) are UE 5.4's as remembered, not run.
"""

import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
TEXTURES = os.path.join(ROOT, "Content", "Textures")
MODELS = os.path.join(ROOT, "Content", "Models")
GAME_TEXTURES = "/Game/Textures"
SURFACE_DIR = "/Game/Materials/Surface"
SURFACE = SURFACE_DIR + "/M_Surface"

# what each kind of map is: how it was written (srgb), how Unreal stores it,
# which sampler reads it, and the M_Surface parameter it fills (None: imported
# and set, sampled by nothing built here)
ROLES = {
    "BaseColor": dict(srgb=True, compression="TC_DEFAULT", sampler="SAMPLERTYPE_COLOR", param="BaseColor", data=False),
    "Paint": dict(srgb=True, compression="TC_DEFAULT", sampler="SAMPLERTYPE_COLOR", param=None, data=False),
    "Normal": dict(srgb=False, compression="TC_NORMALMAP", sampler="SAMPLERTYPE_NORMAL", param="Normal", data=True),
    "Roughness": dict(srgb=False, compression="TC_MASKS", sampler="SAMPLERTYPE_MASKS", param="Roughness", data=True),
    "Metallic": dict(srgb=False, compression="TC_MASKS", sampler="SAMPLERTYPE_MASKS", param=None, data=True),
    "Mask": dict(srgb=False, compression="TC_MASKS", sampler="SAMPLERTYPE_MASKS", param=None, data=True),
}
LAYERS = {"Saud_IronArm"}            # a layer over a surface, not a surface
NAME = re.compile(r"^T_(?P<set>[A-Za-z0-9]+_[A-Za-z0-9]+)_(?P<role>[A-Za-z]+)\.png$")
# the Blender input each role's map was linked to, read back from an FBX
LINKED = {"BaseColor": "Base Color", "Roughness": "Roughness", "Normal": "Normal"}

_FLAGS = set()


def scan(root=TEXTURES):
    """{set: {role: path}} for every texture file, and the files no role
    claims."""
    sets, stray = {}, []
    for path in sorted(glob.glob(os.path.join(root, "*", "*.png"))):
        m = NAME.match(os.path.basename(path))
        if not m or m.group("role") not in ROLES:
            stray.append(path)
            continue
        sets.setdefault(m.group("set"), {})[m.group("role")] = path
    return sets, stray


def constants():
    """The souq's surfaces' metal and light, from build_souq.py's own
    tables: {set: dict(metallic, emissive=(r, g, b) linear)}."""
    sys.path.insert(0, os.path.join(ROOT, "Tools", "blender"))
    import build_souq as B
    lantern = B._lin(B._hex(B.BROWSER_ART["lantern"]))[:3]
    return {
        "Souq_Iron": dict(metallic=B.ROUGH["metallic"], emissive=(0.0, 0.0, 0.0)),
        "Souq_Ember": dict(metallic=0.0, emissive=tuple(c * B.EMBER["strength"] for c in B.EMBER["emission"])),
        "Souq_Glass": dict(metallic=0.0, emissive=tuple(c * 3.0 for c in lantern)),
        # the city's (Tools/blender/build_city.py, 2026-10-03): its metal,
        # its glass, its lit windows and its floodlights
        "City_Steel": dict(metallic=B.ROUGH["metallic"], emissive=(0.0, 0.0, 0.0)),
        "City_Corrugated": dict(metallic=B.ROUGH["metallic"], emissive=(0.0, 0.0, 0.0)),
        "City_Glass": dict(metallic=0.3, emissive=(0.0, 0.0, 0.0)),
        "City_Lit": dict(metallic=0.0, emissive=tuple(c * 4.0 for c in B._lin(B._hex("#ffcf8a"))[:3])),
        "City_Lamp": dict(metallic=0.0, emissive=tuple(c * 12.0 for c in B._lin(B._hex("#fff2d6"))[:3])),
    }


def slots_of(name):
    """The texture set a mesh's material slot stands for: a man's
    "<Man>_<Part>", the souq's "M_Souq_<Part>" (Blender's ".001" ignored)."""
    name = name.split(".")[0]
    return name[2:] if name.startswith("M_") else name


def _content_misses(sets):
    """What is in the files against what their roles say."""
    import numpy as np
    from PIL import Image
    miss = []
    for s, roles in sets.items():
        for role, path in roles.items():
            a = np.asarray(Image.open(path).convert("RGB"), float) / 255.0
            if "normal_as_masks_content" in _FLAGS and role == "Roughness":
                role = "Normal"
            if role == "Normal":
                m = a.reshape(-1, 3).mean(0)
                if not (m[2] >= 0.75 and abs(m[0] - 0.5) <= 0.1 and abs(m[1] - 0.5) <= 0.1):
                    miss.append("%s is not a normal map (mean %s)" % (os.path.basename(path), np.round(m, 3)))
            elif ROLES[role]["data"]:
                spread = max(np.abs(a[..., 0] - a[..., 1]).max(), np.abs(a[..., 1] - a[..., 2]).max())
                if spread > 2.5 / 255.0:
                    miss.append("%s is a data map but not grey (channels apart by %.3f)" % (os.path.basename(path), spread))
    return miss


def _fbx_misses(sets):
    """Every man's and the souq's material slots, read back through
    Blender's FBX importer, against the sets on disk -- and each slot's maps
    linked to the inputs their names say. Empty (and says so) without bpy."""
    try:
        import bpy
    except ImportError:
        return None
    miss = []
    files = (sorted(glob.glob(os.path.join(MODELS, "*.fbx"))) + sorted(glob.glob(os.path.join(MODELS, "Souq", "*.fbx")))
             + sorted(glob.glob(os.path.join(MODELS, "City", "*.fbx"))))
    seen = set()
    for f in files:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=f)
        for mat in bpy.data.materials:
            links = {}
            for n in (mat.node_tree.nodes if mat.node_tree else []):
                if n.type == "TEX_IMAGE" and n.image:
                    to = [l.to_node.type if l.to_node.type == "NORMAL_MAP" else l.to_socket.name
                          for o in n.outputs for l in o.links]
                    links[os.path.basename(n.image.filepath)] = to
            if not links:
                continue                  # a slot the FBX carries no maps for (the world street's own)
            s = slots_of(mat.name)
            seen.add(s)
            if s not in sets or s in LAYERS:
                miss.append("%s: slot %s has no surface set" % (os.path.basename(f), mat.name))
                continue
            for role, want in LINKED.items():
                path = sets[s].get(role)
                if not path:
                    continue
                got = links.get(os.path.basename(path), [])
                ok = ("NORMAL_MAP" in got) if role == "Normal" else (want in got)
                if "swap_links" in _FLAGS and role == "Roughness":
                    ok = "Base Color" in got
                if not ok:
                    miss.append("%s: %s's %s map is linked to %s" % (os.path.basename(f), s, role, got))
    for s in sets:
        if s not in LAYERS and s not in seen:
            miss.append("set %s is on disk and in no FBX's slots" % s)
    return miss


def check(roles=None, root=TEXTURES):
    """Every rule; returns the misses."""
    R = ROLES if roles is None else roles
    sets, stray = scan(root)
    if "stray_file" in _FLAGS:
        stray = stray + [os.path.join(root, "Souq", "T_Souq_Wood_Gloss.png")]
    if "drop_set" in _FLAGS:
        sets = {k: v for k, v in sets.items() if k != "Souq_Wood"}
    miss = ["no role claims %s" % os.path.relpath(p, ROOT) for p in stray]
    for s, roles in sets.items():
        if s in LAYERS:
            continue
        for need in ("BaseColor", "Roughness"):
            if need not in roles:
                miss.append("set %s has no %s map" % (s, need))
    for role, r in R.items():
        if r["data"] and r["srgb"]:
            miss.append("%s is data and imports as sRGB colour" % role)
        if not r["data"] and not r["srgb"]:
            miss.append("%s is colour and imports linear" % role)
        if (role == "Normal") != (r["compression"] == "TC_NORMALMAP"):
            miss.append("%s compresses as %s" % (role, r["compression"]))
        if (r["sampler"] == "SAMPLERTYPE_COLOR") != r["srgb"] or (r["sampler"] == "SAMPLERTYPE_NORMAL") != (role == "Normal"):
            miss.append("%s's sampler %s disagrees with its texture (sRGB %s)" % (role, r["sampler"], r["srgb"]))
    miss += _content_misses(sets)
    fbx = _fbx_misses(sets)
    if fbx is None:
        print("  (no bpy: the FBX slots were not read)")
    else:
        miss += fbx
    return miss


BITES = {
    "roughness_srgb": lambda R: R["Roughness"].update(srgb=True),
    "normal_as_masks": lambda R: R["Normal"].update(compression="TC_MASKS"),
    "colour_sampler_on_data": lambda R: R["Roughness"].update(sampler="SAMPLERTYPE_COLOR"),
    "stray_file": None, "drop_set": None, "normal_as_masks_content": None, "swap_links": None,
}


# ------------------------------------------------------------------ editor
def build():
    """Inside the editor: import and set every texture, build M_Surface and
    an instance per set, and put them on every mesh slot that names a set.
    Read-reviewed, not run."""
    import unreal  # noqa: E402  (only importable inside the editor)
    EAL = unreal.EditorAssetLibrary
    MEL = unreal.MaterialEditingLibrary
    AT = unreal.AssetToolsHelpers.get_asset_tools()
    sets, _stray = scan()
    consts = constants()

    # 1. every texture, imported and set from its role
    tasks, where = [], {}
    for s, roles in sets.items():
        for role, path in roles.items():
            folder = "%s/%s" % (GAME_TEXTURES, os.path.basename(os.path.dirname(path)))
            t = unreal.AssetImportTask()
            t.filename = path; t.destination_path = folder
            t.automated = True; t.save = False; t.replace_existing = True
            tasks.append(t)
            where[(s, role)] = "%s/%s" % (folder, os.path.splitext(os.path.basename(path))[0])
    AT.import_asset_tasks(tasks)
    tex = {}
    for (s, role), asset in where.items():
        t = unreal.load_asset(asset)
        if t is None:
            unreal.log_error("surfaces: %s did not import" % asset)
            continue
        r = ROLES[role]
        t.set_editor_property("srgb", r["srgb"])
        t.set_editor_property("compression_settings", getattr(unreal.TextureCompressionSettings, r["compression"]))
        EAL.save_loaded_asset(t)
        tex[(s, role)] = t

    # 2. M_Surface: each map read by the sampler its texture wants
    if EAL.does_asset_exist(SURFACE):
        surface = unreal.load_asset(SURFACE)
    else:
        surface = AT.create_asset("M_Surface", SURFACE_DIR, unreal.Material, unreal.MaterialFactoryNew())
        first = lambda role: next(t for (s, r), t in tex.items() if r == role)
        y = 0
        samplers = {}
        for role in ("BaseColor", "Normal", "Roughness"):
            e = MEL.create_material_expression(surface, unreal.MaterialExpressionTextureSampleParameter2D, -600, y)
            e.set_editor_property("parameter_name", role)
            e.set_editor_property("sampler_type", getattr(unreal.MaterialSamplerType, ROLES[role]["sampler"]))
            e.set_editor_property("texture", unreal.load_asset("/Engine/EngineMaterials/FlatNormal")
                                  if role == "Normal" else first(role))
            samplers[role] = e
            y += 260
        MEL.connect_material_property(samplers["BaseColor"], "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
        MEL.connect_material_property(samplers["Normal"], "RGB", unreal.MaterialProperty.MP_NORMAL)
        MEL.connect_material_property(samplers["Roughness"], "R", unreal.MaterialProperty.MP_ROUGHNESS)
        metal = MEL.create_material_expression(surface, unreal.MaterialExpressionScalarParameter, -600, y)
        metal.set_editor_property("parameter_name", "Metallic"); metal.set_editor_property("default_value", 0.0)
        MEL.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)
        glow = MEL.create_material_expression(surface, unreal.MaterialExpressionVectorParameter, -600, y + 160)
        glow.set_editor_property("parameter_name", "Emissive")
        glow.set_editor_property("default_value", unreal.LinearColor(0.0, 0.0, 0.0, 1.0))
        MEL.connect_material_property(glow, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        MEL.recompile_material(surface)
        EAL.save_loaded_asset(surface)
    # the camera's fade (Tools/look/camera_fade.py), on a new M_Surface or one
    # built before it existed
    import camera_fade
    if camera_fade.add_fade(surface):
        MEL.recompile_material(surface)
        EAL.save_loaded_asset(surface)

    # 3. an instance per surface set
    mis = {}
    for s, roles in sets.items():
        if s in LAYERS:
            continue
        path = "%s/MI_%s" % (SURFACE_DIR, s)
        mi = unreal.load_asset(path) if EAL.does_asset_exist(path) else AT.create_asset(
            "MI_" + s, SURFACE_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mi, surface)
        for role in roles:
            if ROLES[role]["param"] and (s, role) in tex:
                MEL.set_material_instance_texture_parameter_value(mi, ROLES[role]["param"], tex[(s, role)])
        c = consts.get(s, dict(metallic=0.0, emissive=(0.0, 0.0, 0.0)))
        MEL.set_material_instance_scalar_parameter_value(mi, "Metallic", c["metallic"])
        MEL.set_material_instance_vector_parameter_value(mi, "Emissive", unreal.LinearColor(*c["emissive"], 1.0))
        EAL.save_loaded_asset(mi)
        mis[s] = mi

    # 4. every mesh slot that names a set takes its instance
    placed = 0
    for asset in EAL.list_assets("/Game", recursive=True, include_folder=False):
        data = EAL.find_asset_data(asset)
        cls = str(data.asset_class_path.asset_name) if hasattr(data, "asset_class_path") else str(data.asset_class)
        if cls not in ("StaticMesh", "SkeletalMesh"):
            continue
        mesh = unreal.load_asset(asset)
        changed = False
        if cls == "StaticMesh":
            for i, sm in enumerate(mesh.get_editor_property("static_materials")):
                s = slots_of(str(sm.get_editor_property("material_slot_name")))
                if s in mis:
                    mesh.set_material(i, mis[s]); changed = True; placed += 1
        else:
            mats = mesh.get_editor_property("materials")
            for m in mats:
                s = slots_of(str(m.get_editor_property("material_slot_name")))
                if s in mis:
                    m.set_editor_property("material_interface", mis[s]); changed = True; placed += 1
            if changed:
                mesh.set_editor_property("materials", mats)
        if changed:
            EAL.save_loaded_asset(mesh)
    unreal.log("surfaces: %d textures set, %d instances, %d mesh slots" % (len(tex), len(mis), placed))


def main():
    if "--bite" in sys.argv:
        clean = check()
        if clean:
            print("the unbroken files fail their own rules, so no sabotage can be counted:")
            for m in clean:
                print("  " + m)
            sys.exit(1)
        caught = 0
        for name, breaks in BITES.items():
            R = {k: dict(v) for k, v in ROLES.items()}
            _FLAGS.clear()
            if breaks:
                breaks(R)
            else:
                _FLAGS.add(name)
            miss = check(R)
            _FLAGS.clear()
            caught += bool(miss)
            print("  %-26s %s" % (name, ("caught: " + miss[0]) if miss else "NOT caught"))
        print("%d of %d sabotages caught" % (caught, len(BITES)))
        sys.exit(0 if caught == len(BITES) else 1)
    miss = check()
    sets, _ = scan()
    for m in miss:
        print("MISS " + m)
    print("surfaces: %d texture sets (%d files), every one %s" % (
        len(sets), sum(len(v) for v in sets.values()), "set right" if not miss else "NOT right"))
    sys.exit(1 if miss else 0)


if __name__ == "__main__":
    try:
        import unreal  # noqa: F401
        IN_EDITOR = True
    except ImportError:
        IN_EDITOR = False
    if IN_EDITOR:
        build()
    else:
        main()
