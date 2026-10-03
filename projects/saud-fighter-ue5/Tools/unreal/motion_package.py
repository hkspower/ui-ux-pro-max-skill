"""
The motion package, in the editor: the CMU clips imported onto Saud's
skeleton, and Epic's Game Animation Sample retargeted onto him.

Asked 2026-10-03 (Riyadh) as "use unreal engine motions package install
here", settled as both: free motion capture retargeted here (Tools/blender/
mocap.py -- Content/Animation/Mocap, five clips, built and checked), and
editor scripts for Epic's Game Animation Sample. This is the editor half.

Run inside the Unreal editor (Output Log, Python):

    py "Tools/unreal/motion_package.py" --mocap
        the five mocap clips -> /Game/Animation/Mocap, on Saud's skeleton
    py "Tools/unreal/motion_package.py" --gasp [--source /Game/...] [--only Walk,Run]
        the Game Animation Sample's clips -> /Game/Animation/GASP, retargeted

and outside it, the tables only:

    python3 Tools/unreal/motion_package.py --check     [--bite]

THE GAME ANIMATION SAMPLE is Epic's free project (Fab, UE 5.4 and later):
some 500 motion-captured clips -- walks, jogs, runs, starts, stops, pivots,
turns -- on the UEFN mannequin, built for Motion Matching. It cannot be
fetched from here (it needs an Epic account and the launcher), so it is
added by hand first:

  1. In the Epic launcher, Fab: "Game Animation Sample Project", create a
     project from it (5.4 or 5.5), and from that project migrate
     /Game/Characters/UEFN_Mannequin (right-click, Asset Actions, Migrate)
     into this project's Content.
  2. Import Saud (Content/Models/Saud.fbx) if he is not in yet, so his
     skeletal mesh exists -- SAUD_MESH below, or --mesh.
  3. Run --gasp. It makes Saud's IK Rig (IK_Saud, the mannequin's chains on
     his bone names, which ARE the mannequin's), finds the sample's own IK
     Rig for the UEFN mannequin, makes the retargeter between them
     (RTG_GASP_to_Saud) with every chain mapped by name, and batch-retargets
     the sample's locomotion onto him, prefixed A_Saud_GASP_.

NOT RUN. No engine has opened this project and the sample is not here.
Everything below is UE 5.4's Python API as remembered -- IKRigController,
IKRetargeterController, IKRetargetBatchOperation -- and the sample's folder
as remembered; each step checks what it found and says so in the log
rather than guessing on. What a man walking on this skeleton looks like is
proved only for the mocap clips (Tools/blender/mocap.py's checks and its
read-back); the sample's clips are Epic's and will only be seen in the
editor.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MOCAP_DIR = os.path.join(ROOT, "Content", "Animation", "Mocap")
MOCAP_CSV = os.path.join(MOCAP_DIR, "DT_SaudMocap.csv")

# Where things go, and where Saud is (Content/Models/Saud.fbx imported to
# /Game/Models names its skeleton Saud_Skeleton)
SAUD_MESH = "/Game/Models/Saud"
SAUD_SKELETON = "/Game/Models/Saud_Skeleton"
MOCAP_DEST = "/Game/Animation/Mocap"
GASP_DEST = "/Game/Animation/GASP"
GASP_SOURCE = "/Game/Characters/UEFN_Mannequin"
PREFIX = "A_Saud_GASP_"

# The sample's clips worth having on a fighter's street: its locomotion. A
# clip is taken when its name holds one of these and none of SKIP.
TAKE = ("Walk", "Jog", "Run", "Sprint", "Idle", "Start", "Stop", "Pivot", "Turn")
SKIP = ("Crouch", "Jump", "Fall", "Land", "Traversal", "Vault", "Mantle", "Hurdle")

# Saud's IK Rig: the UE5 mannequin's retarget chains, on his bones (the
# mannequin's own names -- Tools/blender/hero/pipeline.py MANNEQUIN). Used
# when the editor's own auto-generated definition is not available.
CHAINS = [
    ("Spine", "spine_01", "spine_03", ""),
    ("Neck", "neck_01", "neck_01", ""),
    ("Head", "head", "head", ""),
    ("LeftClavicle", "clavicle_l", "clavicle_l", ""),
    ("LeftArm", "upperarm_l", "hand_l", "hand_l_goal"),
    ("RightClavicle", "clavicle_r", "clavicle_r", ""),
    ("RightArm", "upperarm_r", "hand_r", "hand_r_goal"),
    ("LeftLeg", "thigh_l", "ball_l", "foot_l_goal"),
    ("RightLeg", "thigh_r", "ball_r", "foot_r_goal"),
    ("LeftThumb", "thumb_01_l", "thumb_03_l", ""),
    ("LeftIndex", "index_01_l", "index_03_l", ""),
    ("LeftMiddle", "middle_01_l", "middle_03_l", ""),
    ("LeftRing", "ring_01_l", "ring_03_l", ""),
    ("LeftPinky", "pinky_01_l", "pinky_03_l", ""),
    ("RightThumb", "thumb_01_r", "thumb_03_r", ""),
    ("RightIndex", "index_01_r", "index_03_r", ""),
    ("RightMiddle", "middle_01_r", "middle_03_r", ""),
    ("RightRing", "ring_01_r", "ring_03_r", ""),
    ("RightPinky", "pinky_01_r", "pinky_03_r", ""),
]
ROOT_BONE = "pelvis"


def _arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def mocap_rows():
    import csv
    return list(csv.DictReader(open(MOCAP_CSV, encoding="utf-8")))


def check(chains=None, rows=None):
    """Outside the editor: the chains name bones the skeleton has, and the
    mocap clips the manifest lists are on disk."""
    sys.path.insert(0, os.path.join(ROOT, "Tools", "blender"))
    from hero.pipeline import MANNEQUIN
    fails = []
    for name, a, b, _goal in (CHAINS if chains is None else chains):
        for bone in (a, b):
            if bone not in MANNEQUIN:
                fails.append("chain %s names %s, which Saud's skeleton does not have" % (name, bone))
    if ROOT_BONE not in MANNEQUIN:
        fails.append("the retarget root %s is not one of Saud's bones" % ROOT_BONE)
    rows = mocap_rows() if rows is None else rows
    for r in rows:
        if not os.path.exists(os.path.join(MOCAP_DIR, r["File"])):
            fails.append("%s is listed in DT_SaudMocap.csv and not on disk" % r["File"])
    return fails, len(rows)


# ================================================================ the editor
def _ue():
    import unreal  # noqa: E402  (only importable inside the editor)
    return unreal


def import_mocap():
    """Content/Animation/Mocap/*.fbx -> MOCAP_DEST, animation only, onto
    Saud's skeleton, at the frame rate the clips were baked at."""
    unreal = _ue()
    EAL = unreal.EditorAssetLibrary
    skel_path = _arg("--skeleton", SAUD_SKELETON)
    assert EAL.does_asset_exist(skel_path), \
        "%s is not imported: import Content/Models/Saud.fbx first (or pass --skeleton)" % skel_path
    skeleton = unreal.load_asset(skel_path)
    tasks = []
    for r in mocap_rows():
        ui = unreal.FbxImportUI()
        ui.import_mesh = False
        ui.import_animations = True
        ui.import_materials = False
        ui.import_textures = False
        ui.skeleton = skeleton
        ui.mesh_type_to_import = unreal.FBXImportType.FBXIT_ANIMATION
        ui.anim_sequence_import_data.set_editor_property("import_uniform_scale", 1.0)
        ui.anim_sequence_import_data.set_editor_property("use_default_sample_rate", False)
        ui.anim_sequence_import_data.set_editor_property("custom_sample_rate", 30)
        t = unreal.AssetImportTask()
        t.filename = os.path.join(MOCAP_DIR, r["File"])
        t.destination_path = MOCAP_DEST
        t.destination_name = r["Name"]
        t.automated = True
        t.replace_existing = True
        t.save = True
        t.options = ui
        tasks.append(t)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    got = [r["Name"] for r in mocap_rows() if EAL.does_asset_exist("%s/%s" % (MOCAP_DEST, r["Name"]))]
    unreal.log("motion package: %d of %d mocap clips in %s" % (len(got), len(tasks), MOCAP_DEST))
    return got


def _saud_rig(unreal, mesh):
    """IK_Saud: his retarget root and chains -- the editor's own mannequin
    template if it offers one, CHAINS otherwise."""
    EAL = unreal.EditorAssetLibrary
    AT = unreal.AssetToolsHelpers.get_asset_tools()
    path = "%s/IK_Saud" % GASP_DEST
    rig = unreal.load_asset(path) if EAL.does_asset_exist(path) else AT.create_asset(
        "IK_Saud", GASP_DEST, unreal.IKRigDefinition, unreal.IKRigDefinitionFactory())
    c = unreal.IKRigController.get_controller(rig)
    c.set_skeletal_mesh(mesh)
    auto = getattr(c, "apply_auto_generated_retarget_definition", None)
    if auto and auto():
        unreal.log("motion package: IK_Saud from the editor's own mannequin template")
    else:
        c.set_retarget_root(ROOT_BONE)
        for name, a, b, goal in CHAINS:
            c.add_retarget_chain(name, a, b, goal)
        unreal.log("motion package: IK_Saud from CHAINS (%d chains)" % len(CHAINS))
    EAL.save_loaded_asset(rig)
    return rig


def _source_rig(unreal, root):
    """The sample's own IK Rig for its mannequin: the first IKRigDefinition
    under `root`."""
    AR = unreal.AssetRegistryHelpers.get_asset_registry()
    for a in AR.get_assets_by_path(root, recursive=True):
        if str(a.asset_class_path.asset_name) == "IKRigDefinition":
            return unreal.load_asset(str(a.package_name))
    return None


def _sample_clips(unreal, root, only):
    AR = unreal.AssetRegistryHelpers.get_asset_registry()
    out = []
    for a in AR.get_assets_by_path(root, recursive=True):
        if str(a.asset_class_path.asset_name) != "AnimSequence":
            continue
        name = str(a.asset_name)
        want = only or TAKE
        if any(w.lower() in name.lower() for w in want) and not any(k.lower() in name.lower() for k in SKIP):
            out.append(a)
    return out


def retarget_gasp():
    unreal = _ue()
    EAL = unreal.EditorAssetLibrary
    root = _arg("--source", GASP_SOURCE)
    only = tuple(x for x in (_arg("--only", "") or "").split(",") if x)
    mesh_path = _arg("--mesh", SAUD_MESH)
    assert EAL.does_directory_exist(root), \
        "%s is not here: migrate the Game Animation Sample's UEFN_Mannequin folder in first (see the top of this file)" % root
    assert EAL.does_asset_exist(mesh_path), "%s is not imported: import Content/Models/Saud.fbx first" % mesh_path
    mesh = unreal.load_asset(mesh_path)
    src_rig = _source_rig(unreal, root)
    assert src_rig is not None, "no IK Rig under %s: the sample's own rig was expected there" % root
    tgt_rig = _saud_rig(unreal, mesh)
    AT = unreal.AssetToolsHelpers.get_asset_tools()
    path = "%s/RTG_GASP_to_Saud" % GASP_DEST
    rtg = unreal.load_asset(path) if EAL.does_asset_exist(path) else AT.create_asset(
        "RTG_GASP_to_Saud", GASP_DEST, unreal.IKRetargeter, unreal.IKRetargetFactory())
    rc = unreal.IKRetargeterController.get_controller(rtg)
    rc.set_ik_rig(unreal.RetargetSourceOrTarget.SOURCE, src_rig)
    rc.set_ik_rig(unreal.RetargetSourceOrTarget.TARGET, tgt_rig)
    rc.auto_map_chains(unreal.AutoMapChainType.FUZZY, True)
    # his rest pose is not the sample's: line his bones up with theirs
    # before anything is copied, where the editor offers it
    align = getattr(rc, "auto_align_all_bones", None)
    if align:
        align(unreal.RetargetSourceOrTarget.TARGET)
    EAL.save_loaded_asset(rtg)
    clips = _sample_clips(unreal, root, only)
    unreal.log("motion package: %d of the sample's clips to retarget" % len(clips))
    src_mesh = src_rig.get_preview_mesh()
    made = unreal.IKRetargetBatchOperation.duplicate_and_retarget(
        clips, src_mesh, mesh, rtg, "", "", PREFIX, "", False)
    for a in made:
        p = str(a.package_name)
        EAL.rename_asset(p, "%s/%s" % (GASP_DEST, p.split("/")[-1]))
    unreal.log("motion package: %d clips retargeted onto Saud in %s" % (len(made), GASP_DEST))
    return made


def main():
    try:
        import unreal  # noqa: F401
        in_editor = True
    except ImportError:
        in_editor = False
    if "--bite" in sys.argv:
        clean, _ = check()
        cases = {"a chain on a bone he lacks": dict(chains=CHAINS[:-1] + [("RightPinky", "pinky_01_r", "pinky_04_r", "")]),
                 "a clip not on disk": dict(rows=mocap_rows() + [dict(File="A_Saud_Mocap_Crawl.fbx")])}
        caught = 0
        for name, kw in cases.items():
            m, _ = check(**kw)
            caught += bool(m) and not clean
            print("  %-26s %s" % (name, ("caught: " + m[0]) if m else "NOT caught"))
        print("%d of %d sabotages caught" % (caught, len(cases)))
        sys.exit(0 if caught == len(cases) else 1)
    if not in_editor or "--check" in sys.argv:
        fails, n = check()
        for f in fails:
            print("MISS " + f)
        print("motion package: %d retarget chains on Saud's bones, %d mocap clips on disk -- %s"
              % (len(CHAINS), n, "ready for the editor" if not fails else "NOT ready"))
        if not in_editor:
            print("Run inside the Unreal editor with --mocap and/or --gasp.")
        sys.exit(1 if fails else 0)
    if "--mocap" in sys.argv:
        import_mocap()
    if "--gasp" in sys.argv:
        retarget_gasp()


if __name__ == "__main__":
    main()
