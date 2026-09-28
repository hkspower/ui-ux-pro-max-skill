#!/usr/bin/env python3
"""Saud's IK pose sheet: the key poses of his shipped clips, each posed
THROUGH his control rig, rendered in the game's anime look, with the
controls drawn over him (Unreal build only; asked 2026-09-28 as "make
render for Saud IK").

    python3 Tools/blender/ik_sheet.py Saud [--samples 32] [--height 1200] [--out PATH]
                                   Docs/renders/saud-ik-sheet.png: nine
                                   panels, 3 x 3, under a title band
    python3 Tools/blender/ik_sheet.py Saud --bite [--samples 4] [--height 400]
                                   break each check's mechanism and prove
                                   the check notices (the unbroken panels
                                   first, which must pass)

WHAT A PANEL IS. rigs/<Man>.blend is opened and never saved. A clip's FBX
(Content/Animation/<Man>/) is imported beside him and one frame of it is
read as the posed bones' matrices in armature space -- not as deltas from
the importer's rest, which for an armature-only FBX is the clip's own first
frame (a rest-delta transfer was 99-1570 mm wrong) -- and Blender's importer
puts authored frame i at i + 2, as build_motion.readback reads it. He is
posed to it through his controls by rig_full_ik.pose_from (the hips and
root on theirs; the spine, neck, head and collarbones as FK, which is what
the rig's FK controls are; every limb in FK and then handed to IK, the
feet keeping their roll; fists by the slider), measured, rendered in
Cycles and put through anime_look's numpy mirror of the post-process
(anime_preview.render_scene + look_from), and the controls are drawn over
the render through its own camera at its own size: the IK chains thin, the
poles dashed from their joint to CTRL_elbow / CTRL_knee, every control's
own widget (rig_full_ik.widget_edges), and the FK torso as rings at the
evaluated spine, neck and head -- CTRL_chest and CTRL_head are rotation-
only controls that hang off CTRL_hips and do not follow an FK spine, so
they are drawn only if turned, and CTRL_look only when `look` is on. The
lead (L) side is Kuwait's red (build_saud.PALETTE's band), the rear (R)
EMBER, the body BONE, every line on an INK halo -- the look's own colours.

WHAT IT CHECKS, each panel (every one proved to fail by --bite):
  the controls reproduce the shipped frame -- every deform bone's head and
      tail within 3 mm of the clip (clean 0.1-2.2 mm; the pole-less knees
      and a dropped roll are what break it);
  the controls hold the limbs -- every IK end within 0.5 mm of its control,
      and a 5 mm nudge of each hand and foot control moves its end bone at
      least 0.9 of it (a limb left in FK does not move);
  the skin is the posed rig -- every vertex weighted 0.5 or more to a hand
      or a foot is where the bones put it by linear blend, within 0.5 mm
      (the Armature modifier the only one);
  the overlay is registered -- EACH drawn control's centre, as drawn, lies
      within 1 % of the panel's height of its OWN bone (the hand control of
      the wrist, the foot control of the ankle carried back through its
      roll, the hips of the pelvis, each FK ring of its bone, each pole's
      dashed line of its joint): measured by casting the render camera's
      own ray through the drawn pixel (Camera.view_frame, not the
      projection the overlay drew with) and taking its miss past the bone
      in pixels at the bone's depth -- and every body control lands within
      1 % of the height of a fighter pixel of the render's ObjectIndex
      pass, so the drawing sits on the picture and not only on the camera.
      A control drawn at the wrong joint inside the silhouette passes the
      second and fails the first ("wrong_joint").

Nothing here writes to the rig file, the clips or the scene on disk. The
look is the preview's (Cycles through the numpy mirror, its stand-in
exposure), not an engine's.
"""
import os
import sys
import csv
import math
import time
import shutil
import tempfile

import bpy
import numpy as np
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "look"))
import build_saud as L          # noqa: E402
import rig_full_ik as CR        # noqa: E402
import anime_preview as AP      # noqa: E402
import anime_look as AL         # noqa: E402

# (header, clip, which frame: a 0-based index, "c" the contact, "last", or
# "peak" -- the frame the head is furthest from where it started)
PANELS = [("GUARD", "A_{m}_Guard", 0), ("JAB", "A_{m}_Jab", "c"), ("CROSS", "A_{m}_Cross", "c"),
          ("HOOK", "A_{m}_Hook", "c"), ("ROUND KICK", "A_{m}_Kick", "c"), ("KNEE", "A_{m}_Knee", "c"),
          ("BLOCK", "A_{m}_Block", 0), ("HIT", "A_{m}_Hit_Head_Straight", "peak"),
          ("VICTORY", "A_{m}_Victory", "last")]
# one camera for every panel: three-quarters from his front left, a little
# over the hips, long enough a lens that a kick stays in the frame
CAM_AT, CAM_AIM, CAM_LENS = Vector((3.4, -3.9, 1.30)), Vector((0.10, -0.10, 1.02)), 72.0
ASPECT = 0.75                   # a panel is 900 x 1200 at --height 1200
TOL_BONES, TOL_REACH, TOL_DRIVE, TOL_SKIN, TOL_REG = 0.003, 0.0005, 0.9, 0.0005, 0.01
NUDGE = 0.005
# the FK torso, drawn as a ring round each bone: (bone, radius in metres,
# how far along the bone). The head's joint is at the eye line on this
# skeleton, so its ring is taken up round the skull, off the face.
RINGS = (("spine_01", 0.13, 0.0), ("spine_02", 0.14, 0.0), ("spine_03", 0.15, 0.0), ("neck_01", 0.07, 0.0),
         ("head", 0.11, 0.55))


def ring_at(rig, name, along):
    """Where a bone's ring sits, in world space: `along` its length."""
    pb = rig.pose.bones[name]
    return rig.matrix_world @ (pb.head + (pb.tail - pb.head) * along)
# --bite only: each breaks the one mechanism a check guards
SABOTAGE = set()


# ================================================================= render
def _render_scene(camera=None, height=1080, samples=48, fit=False, size=None):
    """anime_preview.render_passes AFTER its open_mainfile: the scene as it
    stands, rendered once with the G-buffer passes the post-process reads.
    Used only while anime_preview has no render_scene of its own; the same
    signature and the same return, (passes, exposure)."""
    sc = bpy.context.scene
    if camera:
        sc.camera = bpy.data.objects[camera] if isinstance(camera, str) else camera
    if fit:
        top = max((o.matrix_world @ Vector(c)).z for o in bpy.data.objects
                  if o.type == "MESH" and any(m.type == "ARMATURE" for m in o.modifiers)
                  for c in o.bound_box)
        k = max(1.0, top / 1.80)
        if k > 1.0:
            cam = sc.camera
            view = cam.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))
            aim = cam.location + view * 3.0
            aim.z *= k
            cam.location = aim - view * 3.0 * k
    if size:
        sc.render.resolution_x, sc.render.resolution_y = int(size[0]), int(size[1])
    else:
        aspect = sc.render.resolution_x / sc.render.resolution_y
        sc.render.resolution_y = height
        sc.render.resolution_x = int(round(height * aspect))
    sc.render.resolution_percentage = 100
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    try:
        sc.cycles.use_denoising = True
    except Exception:
        pass
    vl = sc.view_layers[0]
    vl.use_pass_z = vl.use_pass_normal = vl.use_pass_diffuse_color = vl.use_pass_object_index = True
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.pass_index = 1 if any(m.type == "ARMATURE" for m in o.modifiers) else 0
    out_dir = tempfile.mkdtemp(prefix="anime_")
    # one node group, cleared and rebuilt: this renders the same open scene
    # again and again
    nt = bpy.data.node_groups.get("AnimePasses") or bpy.data.node_groups.new("AnimePasses", "CompositorNodeTree")
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    sc.compositing_node_group = nt
    rl = nt.nodes.new("CompositorNodeRLayers")
    fo = nt.nodes.new("CompositorNodeOutputFile")
    fo.directory = out_dir + "/"
    fo.file_name = "p_"
    fo.format.media_type = "IMAGE"
    fo.format.file_format = "OPEN_EXR"
    fo.format.color_depth = "32"
    for name, kind in AP.PASSES:
        item = fo.file_output_items.new(kind, name.replace(" ", ""))
        nt.links.new(rl.outputs[name], fo.inputs[item.name])
    bpy.ops.render.render(write_still=False)
    got = {}
    for name, _ in AP.PASSES:
        key = name.replace(" ", "")
        path = [f for f in os.listdir(out_dir) if f.startswith("p_" + key)][0]
        img = bpy.data.images.load(os.path.join(out_dir, path))
        w, h = img.size
        a = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(a)
        got[key] = a.reshape(h, w, 4)[::-1].astype(np.float64)     # top row first
        bpy.data.images.remove(img)
    shutil.rmtree(out_dir, ignore_errors=True)
    return got, 2.0 ** sc.view_settings.exposure


def render_scene(**kw):
    """anime_preview's, once it has one (the split of render_passes into
    open + render_scene); this file's copy of the same logic until then."""
    fn = getattr(AP, "render_scene", None) or _render_scene
    return fn(**kw)


# ============================================================ the clips
def clip_frames(fbx, frames, rig):
    """{frame: {bone: armature-space matrix on `rig`}} for a clip's authored
    0-based frames, read as posed (not against the importer's rest), at
    i + 2. The imported armature and its action are removed again."""
    before, acts = set(bpy.data.objects), set(bpy.data.actions)
    bpy.ops.import_scene.fbx(filepath=fbx)
    new = [o for o in bpy.data.objects if o not in before]
    imp = next(o for o in new if o.type == "ARMATURE")
    to_rig = rig.matrix_world.inverted() @ imp.matrix_world
    names = [b.name for b in rig.data.bones if not b.name.startswith(CR.CTRL_PREFIX)]
    out = {}
    for i in frames:
        bpy.context.scene.frame_set(i + 2)
        bpy.context.view_layer.update()
        out[i] = {n: to_rig @ imp.pose.bones[n].matrix for n in names if n in imp.pose.bones}
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    for a in [a for a in bpy.data.actions if a not in acts]:
        bpy.data.actions.remove(a)
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    return out


def frame_of(rows, clip, which, rig, anim):
    r = rows[clip]
    if which == "c":
        return int(r["ContactFrame"])
    if which == "last":
        return int(r["Frames"]) - 1
    if which == "peak":
        n = int(r["Frames"])
        Ts = clip_frames(os.path.join(anim, clip + ".fbx"), list(range(n)), rig)
        h0 = Ts[0]["head"].translation
        return max(range(n), key=lambda i: (Ts[i]["head"].translation - h0).length)
    return int(which)


# ============================================================== posing
def pose(rig, T):
    """Pose him to the frame through his controls (rig_full_ik.pose_from),
    with the sabotages --bite asks for. Returns the switches, as drawn."""
    pb = rig.pose.bones
    if "roll_lost" in SABOTAGE:
        CR.SABOTAGE.add("roll_dropped")          # a plain snap_ik_to_fk
    try:
        props = CR.pose_from(rig, T)
    finally:
        CR.SABOTAGE.discard("roll_dropped")
    if "no_pole" in SABOTAGE:
        for s in CR.SIDES:                        # the knee poles left at rest
            pb["CTRL_knee_" + s].location = (0.0, 0.0, 0.0)
        rig.update_tag(); bpy.context.view_layer.update()
    if "fk_left_on" in SABOTAGE:
        CR.set_prop(rig, "CTRL_hand_l", "fk", 1.0)
    props["look"] = pb["CTRL_head"]["look"]
    props["fk"] = tuple(pb[c]["fk"] for c in ("CTRL_hand_l", "CTRL_hand_r", "CTRL_foot_l", "CTRL_foot_r"))
    props["fist"] = (pb["CTRL_hand_l"]["fist"], pb["CTRL_hand_r"]["fist"])
    return props


def measure(rig, mesh, T):
    """The three checks that need no picture."""
    pb = rig.pose.bones
    bpy.context.view_layer.update()
    # the controls reproduce the clip: every deform bone, head and tail
    worst, who = 0.0, None
    for n, m in T.items():
        b = rig.data.bones.get(n)
        if b is None or not b.use_deform:
            continue
        for end, got, want in (("head", pb[n].head, m.translation), ("tail", pb[n].tail, m @ Vector((0.0, b.length, 0.0)))):
            e = (got - want).length
            if e > worst:
                worst, who = e, "%s.%s" % (n, end)
    # every IK end on its control
    reach = 0.0
    for s in CR.SIDES:
        reach = max(reach, (pb["lowerarm_" + s].tail - pb["CTRL_hand_" + s].head).length,
                    (pb["calf_" + s].tail - pb["MCH_ankle_" + s].head).length)
    # each control drives its limb: 5 mm along each axis, its end bone follows
    drive, weak = 1e9, None
    for s in CR.SIDES:
        for ctrl, end in (("CTRL_hand_" + s, "hand_" + s), ("CTRL_foot_" + s, "foot_" + s)):
            m0, e0 = pb[ctrl].matrix.copy(), pb[end].head.copy()
            for axis in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
                m = m0.copy(); m.translation = m0.translation + Vector(axis) * NUDGE
                pb[ctrl].matrix = m; bpy.context.view_layer.update()
                k = (pb[end].head - e0).length / NUDGE
                if k < drive:
                    drive, weak = k, ctrl
                pb[ctrl].matrix = m0; bpy.context.view_layer.update()
    return dict(bones_mm=worst * 1000.0, worst=who, reach_mm=reach * 1000.0, drive=drive, weak=weak,
                skin_mm=skin_error(rig, mesh) * 1000.0)


def skin_error(rig, mesh):
    """How far the rendered skin of the hands and feet (every vertex 0.5 or
    more on hand_l/r or foot_l/r) is from where the bones put it by linear
    blend -- the armature modifier's own sum, normalised by the weight."""
    assert [m.type for m in mesh.modifiers] == ["ARMATURE"], \
        "%s carries %s: the linear blend is not the whole story" % (mesh.name, [m.type for m in mesh.modifiers])
    pb = rig.pose.bones
    ev = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    groups = {g.index: g.name for g in mesh.vertex_groups}
    to_arm = rig.matrix_world.inverted() @ mesh.matrix_world
    back = to_arm.inverted()
    defm = {n: pb[n].matrix @ rig.data.bones[n].matrix_local.inverted()
            for n in set(groups.values()) if n in pb and rig.data.bones[n].use_deform}
    ends = {mesh.vertex_groups[n].index for n in ("hand_l", "hand_r", "foot_l", "foot_r")}
    worst = 0.0
    for v in mesh.data.vertices:
        if not any(g.group in ends and g.weight >= 0.5 for g in v.groups):
            continue
        co = to_arm @ v.co
        acc, tw = Vector(), 0.0
        for g in v.groups:
            n = groups[g.group]
            if n in defm and g.weight > 0.0:
                acc += (defm[n] @ co) * g.weight
                tw += g.weight
        want = back @ (acc / tw)
        worst = max(worst, (ev.data.vertices[v.index].co - want).length)
    return worst


# ============================================================ the overlay
def colours():
    """The look's own, as displayed -- read when drawn, so the sheet is in
    whatever the look is now."""
    def rgb(c):
        return tuple(int(round(255 * max(0.0, min(1.0, v)))) for v in AL.display(c))
    return dict(ink=rgb(AL.LOOK["INK"]), bone=rgb(AL.LOOK["BONE"]), ember=rgb(AL.LOOK["EMBER"]),
                red=rgb(L.PALETTE["band"][:3]))


def projector(cam, size):
    """World -> panel pixels (x right, y DOWN), as the overlay draws."""
    from bpy_extras.object_utils import world_to_camera_view
    sc = bpy.context.scene

    def P(v):
        p = world_to_camera_view(sc, cam, Vector(v))
        y = p.y if "flip_y" in SABOTAGE else 1.0 - p.y
        return (p.x * size[0], y * size[1])
    return P


def turned(pbone):
    return pbone.location.length > 1e-6 or pbone.rotation_quaternion.angle > 1e-4


def overlay(pic, rig, cam, size, props, header, footer):
    """Draw the controls over the render. Returns the picture and, for
    every drawn control, the centre of what was drawn (its registration)."""
    from PIL import Image, ImageDraw, ImageFont
    C = colours()
    side_col = {"l": C["red"], "r": C["ember"], "": C["bone"]}
    W, pb = rig.matrix_world, rig.pose.bones
    P = projector(cam, size)
    im = Image.fromarray(pic).convert("RGB")
    d = ImageDraw.Draw(im)
    k = size[1] / 1200.0
    lw = max(2, int(round(3 * k)))
    thin = max(1, lw - 1)
    drawn = {}

    def seg(a, b, col, w):
        d.line([a, b], fill=C["ink"], width=w + 4)          # the 2 px ink halo
        d.line([a, b], fill=col, width=w)

    def line(a, b, col, w, dash=False):
        a, b = P(a), P(b)
        if not dash:
            seg(a, b, col, w)
            return a
        n = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / (10.0 * k)))
        for i in range(0, n, 2):
            p0 = (a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n)
            p1 = (a[0] + (b[0] - a[0]) * (i + 1) / n, a[1] + (b[1] - a[1]) * (i + 1) / n)
            seg(p0, p1, col, w)
        return a

    def centre(points):
        pts = {(round(x, 3), round(y, 3)) for x, y in points}
        return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))

    # the IK chains, thin: shoulder-elbow-wrist and hip-knee-ankle
    for s in CR.SIDES:
        for a, b in (("upperarm", "lowerarm"), ("lowerarm", "hand"), ("thigh", "calf"), ("calf", "foot")):
            line(W @ pb["%s_%s" % (a, s)].head, W @ pb["%s_%s" % (b, s)].head, side_col[s], thin)
    # the FK torso: a ring round each bone at its head, where it is evaluated
    for n, r, along in RINGS:
        m = W @ pb[n].matrix @ Matrix.Translation((0.0, pb[n].length * along, 0.0))
        pts = [m @ Vector((r * math.cos(2 * math.pi * i / 36), 0.0, r * math.sin(2 * math.pi * i / 36))) for i in range(36)]
        for i in range(36):
            line(pts[i], pts[(i + 1) % 36], C["bone"], thin)
        drawn["ring:" + n] = centre([P(p) for p in pts])
    # the poles: dashed, from the joint they pin to their control
    for s in CR.SIDES:
        drawn["pole:lowerarm_" + s] = line(W @ pb["lowerarm_" + s].head, W @ pb["CTRL_elbow_" + s].head,
                                           side_col[s], thin, dash=True)
        drawn["pole:calf_" + s] = line(W @ pb["calf_" + s].head, W @ pb["CTRL_knee_" + s].head,
                                       side_col[s], thin, dash=True)
    # every control's own widget
    for b in pb:
        name = b.name
        if not name.startswith("CTRL_") or b.custom_shape is None:
            continue
        if name == "CTRL_look" and props.get("look", 0.0) <= 0.0:
            continue
        if name in ("CTRL_chest", "CTRL_head") and not turned(b):
            continue
        side = name[-1] if name[-2] == "_" else ""
        edges = CR.widget_edges(rig, name)
        if name == "CTRL_hand_l" and "wrong_joint" in SABOTAGE:
            off = W @ pb["lowerarm_l"].head - W @ pb["CTRL_hand_l"].head       # drawn at the elbow
            edges = [(a + off, c + off) for a, c in edges]
        big = name.startswith(("CTRL_hand", "CTRL_foot"))
        pts = []
        for a, c in edges:
            line(a, c, side_col[side], lw if big else thin)
            pts += [P(a), P(c)]
        drawn[name] = centre(pts)
    if props.get("look", 0.0) > 0.0:
        line(W @ pb["head"].head, W @ pb["CTRL_look"].head, C["bone"], thin, dash=True)
    # the header (the move) and the footer (what the controls hold)
    try:
        big_f = ImageFont.truetype("DejaVuSans-Bold.ttf", max(10, int(40 * k)))
        small_f = ImageFont.truetype("DejaVuSansMono.ttf", max(8, int(19 * k)))
    except Exception:
        big_f = small_f = ImageFont.load_default()
    band = int(58 * k)
    d.rectangle([0, 0, size[0], band], fill=C["ink"])
    d.line([0, band, size[0], band], fill=C["red"], width=max(2, int(3 * k)))
    d.text((int(18 * k), int(8 * k)), header, font=big_f, fill=C["bone"])
    foot = int(36 * k)
    d.rectangle([0, size[1] - foot, size[0], size[1]], fill=C["ink"])
    d.text((int(14 * k), size[1] - foot + int(7 * k)), footer, font=small_f, fill=C["bone"])
    return np.asarray(im), drawn


# ======================================================== registration
def own_points(rig):
    """Each drawn control's own bone, in world space: where it has to be
    drawn. The foot control is the ankle carried back through its roll
    (MCH_ankle's offset under CTRL_foot, which only the roll sets), so a
    control drawn on the rolled foot itself is caught too."""
    W, pb = rig.matrix_world, rig.pose.bones
    out = {"CTRL_hips": W @ pb["pelvis"].head, "CTRL_root": W @ pb["root"].head,
           "CTRL_pivot": W @ pb["root"].head, "CTRL_chest": W @ pb["spine_03"].head,
           "CTRL_head": W @ pb["head"].head}
    for s in CR.SIDES:
        out["CTRL_hand_" + s] = W @ pb["hand_" + s].head
        rel = pb["CTRL_foot_" + s].matrix.inverted() @ pb["MCH_ankle_" + s].matrix
        out["CTRL_foot_" + s] = W @ (pb["foot_" + s].matrix @ rel.inverted()).translation
        out["pole:lowerarm_" + s] = W @ pb["lowerarm_" + s].head
        out["pole:calf_" + s] = W @ pb["calf_" + s].head
    for n, _r, along in RINGS:
        out["ring:" + n] = ring_at(rig, n, along)
    return out


def ray_miss_px(cam, size, xy, point):
    """How far, in pixels at the point's own depth, the render camera's ray
    through pixel `xy` (x right, y down) passes from `point`. The ray is
    built from Camera.view_frame -- the frame the render is taken through --
    not from the projection the overlay drew with."""
    sc = bpy.context.scene
    fr = [Vector(v) for v in cam.data.view_frame(scene=sc)]
    xs, ys = sorted(v.x for v in fr), sorted(v.y for v in fr)
    left, right, bottom, top, z = xs[0], xs[-1], ys[0], ys[-1], fr[0].z
    local = Vector((left + (right - left) * xy[0] / size[0], top - (top - bottom) * xy[1] / size[1], z))
    M = cam.matrix_world
    o = M.translation
    d = (M.to_3x3() @ local).normalized()
    w = Vector(point) - o
    miss = (w - d * w.dot(d)).length
    depth = -(M.inverted() @ Vector(point)).z
    per_px = (top - bottom) * depth / abs(z) / size[1]
    return miss / per_px


def registration(rig, cam, size, drawn, fighter):
    """Each drawn control against its own bone (the ray), and each body
    control on the fighter's pixels (the render). Returns the worst of
    each, in pixels, and what missed."""
    own = own_points(rig)
    ys, xs = np.nonzero(fighter)
    tol = TOL_REG * size[1]
    worst_own, worst_pix, miss = 0.0, 0.0, []
    for name, xy in drawn.items():
        if name not in own:
            continue
        e = ray_miss_px(cam, size, xy, own[name])
        worst_own = max(worst_own, e)
        if e > tol:
            miss.append("%s drawn %.0f px from its own bone" % (name, e))
        if name in ("CTRL_root", "CTRL_pivot"):
            continue                              # on the floor, between his feet
        dist = float(np.min(np.hypot(xs + 0.5 - xy[0], ys + 0.5 - xy[1]))) if len(xs) else 1e9
        worst_pix = max(worst_pix, dist)
        if dist > tol:
            miss.append("%s drawn %.0f px off him" % (name, dist))
    return worst_own, worst_pix, miss


# ================================================================ panels
def open_man(man):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, "rigs", man + ".blend"))
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    mesh = next(o for o in bpy.data.objects if o.type == "MESH" and o.parent == rig
                and any(m.type == "ARMATURE" for m in o.modifiers))
    cam = bpy.data.objects.new("IKSheetCam", bpy.data.cameras.new("IKSheetCam"))
    cam.data.lens = CAM_LENS
    bpy.context.scene.collection.objects.link(cam)
    cam.location = CAM_AT
    cam.rotation_euler = (CAM_AIM - CAM_AT).to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()
    return rig, mesh, cam


def panel(man, rig, mesh, cam, rows, anim, spec, size, samples):
    label, clip, which = spec[0], spec[1].format(m=man), spec[2]
    f = frame_of(rows, clip, which, rig, anim)
    T = clip_frames(os.path.join(anim, clip + ".fbx"), [f], rig)[f]
    props = pose(rig, T)
    arm = mesh.modifiers[0]
    if "stale_mesh" in SABOTAGE:                  # the skin left at rest for the render
        arm.show_viewport = arm.show_render = False
    try:
        res = measure(rig, mesh, T)
        got, e = render_scene(camera=cam.name, samples=samples, size=size)
        pic, m = AP.look_from(got, e)
        footer = "%s  f%d/%s  fist %.0f/%.0f  fk %s  roll L %.2f R %.2f  look %.0f" % (
            clip, f + 1, rows[clip]["Frames"], props["fist"][0], props["fist"][1],
            " ".join("%.0f" % v for v in props["fk"]), props["roll_l"], props["roll_r"], props["look"])
        pic, drawn = overlay(pic, rig, cam, size, props, label, footer)
        res["reg_own"], res["reg_pix"], miss = registration(rig, cam, size, drawn, m["fighter"])
    finally:
        arm.show_viewport = arm.show_render = True
    fails = []
    if res["bones_mm"] > TOL_BONES * 1000:
        fails.append("%s: the controls pose him %.1f mm off the clip (%s)" % (label, res["bones_mm"], res["worst"]))
    if res["reach_mm"] > TOL_REACH * 1000:
        fails.append("%s: an IK end is %.2f mm from its control" % (label, res["reach_mm"]))
    if res["drive"] < TOL_DRIVE:
        fails.append("%s: a control does not drive its limb (%s moves it %.2f of a %.0f mm nudge)" % (
            label, res["weak"], res["drive"], NUDGE * 1000))
    if res["skin_mm"] > TOL_SKIN * 1000:
        fails.append("%s: the skin is %.1f mm off its bones" % (label, res["skin_mm"]))
    fails += ["%s: %s" % (label, x) for x in miss]
    res.update(label=label, clip=clip, frame=f, roll=(props["roll_l"], props["roll_r"]))
    return pic, res, fails


def run(man, labels, size, samples, anim):
    rig, mesh, cam = open_man(man)
    rows = {r["Name"]: r for r in csv.DictReader(open(os.path.join(anim, "DT_%sMotion.csv" % man), encoding="utf-8"))}
    pics, fails, t0 = [], [], time.time()
    for spec in PANELS:
        if labels and spec[0] not in labels:
            continue
        pic, r, bad = panel(man, rig, mesh, cam, rows, anim, spec, size, samples)
        pics.append(pic)
        fails += bad
        print("%-11s %-27s f%-3d bones %.2f mm (%s)  IK ends %.3f mm  drive %.2f  skin %.4f mm  "
              "overlay %.1f px from its bones, %.1f px off him  roll %.2f/%.2f  %.0fs" % (
                  r["label"], r["clip"], r["frame"], r["bones_mm"], r["worst"], r["reach_mm"], r["drive"],
                  r["skin_mm"], r["reg_own"], r["reg_pix"], r["roll"][0], r["roll"][1], time.time() - t0))
    return pics, fails


def sheet(pics, size, out, man):
    from PIL import Image, ImageDraw, ImageFont
    C = colours()
    k = size[1] / 1200.0
    cols, gap, title = 3, max(2, int(6 * k)), int(96 * k)
    n = len(pics)
    rows_n = (n + cols - 1) // cols
    Wd = cols * size[0] + (cols + 1) * gap
    Hd = title + rows_n * size[1] + (rows_n + 1) * gap
    im = Image.new("RGB", (Wd, Hd), C["ink"])
    d = ImageDraw.Draw(im)
    try:
        f1 = ImageFont.truetype("DejaVuSans-Bold.ttf", max(12, int(48 * k)))
        f2 = ImageFont.truetype("DejaVuSans.ttf", max(8, int(21 * k)))
    except Exception:
        f1 = f2 = ImageFont.load_default()
    d.text((gap + int(12 * k), int(10 * k)), "%s  --  IK POSE SHEET" % man.upper(), font=f1, fill=C["bone"])
    d.text((gap + int(14 * k), int(64 * k)),
           "posed through rigs/%s.blend's controls at frames of Content/Animation/%s.  red: lead (L)   "
           "ember: rear (R)   bone: the body   dashed: a pole   rings: the FK spine, neck, head" % (man, man),
           font=f2, fill=C["bone"])
    d.line([0, title - 2, Wd, title - 2], fill=C["red"], width=max(2, int(3 * k)))
    for i, p in enumerate(pics):
        r, c = divmod(i, cols)
        im.paste(Image.fromarray(p), (gap + c * (size[0] + gap), title + gap + r * (size[1] + gap)))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    im.save(out)
    print("sheet %s (%dx%d)" % (out, Wd, Hd))


# ================================================================== bite
# The roll is bitten on the kick's support foot, up on its ball at 0.75:
# measured 2026-09-28 on the clips of that day, a dropped roll put its ball
# 42.3 mm off; the cross's rear foot (0.12) only 7.1 mm, against 3.
BITES = [
    ("reproduces the clip", "no_pole", ["GUARD"], "off the clip"),
    ("keeps the roll", "roll_lost", ["ROUND KICK"], "off the clip"),
    ("controls drive", "fk_left_on", ["GUARD"], "does not drive"),
    ("skin is the rig", "stale_mesh", ["GUARD"], "the skin is"),
    ("overlay on the render", "flip_y", ["GUARD"], "drawn"),
    ("each control on its bone", "wrong_joint", ["GUARD"], "CTRL_hand_l drawn"),
]


def bite(man, size, samples, anim):
    """Each check made to fail by breaking what it guards, on the panels it
    shows on -- after the same panels unbroken, which must pass."""
    results = []
    SABOTAGE.clear()
    clean = sorted({p for _l, _s, ps, _e in BITES for p in ps})
    _pics, fails = run(man, clean, size, samples, anim)
    results.append(("clean (must pass)", not fails, fails[0] if fails else "passes"))
    for label, sab, panels, expect in BITES:
        SABOTAGE.clear(); SABOTAGE.add(sab)
        try:
            _pics, fails = run(man, panels, size, samples, anim)
        finally:
            SABOTAGE.clear()
        hit = [f for f in fails if expect in f]
        results.append((label, bool(hit), (hit or fails or ["did not bite"])[0]))
    print("\n%-26s %s" % ("check", "when its mechanism is broken"))
    for label, ok, msg in results:
        print("  %-24s %s  %s" % (label, ("OK    " if msg == "passes" else "BITES ") if ok else "SILENT", msg[:110]))
    n = sum(1 for _l, ok, _m in results if ok)
    print("  %d of %d as they should be" % (n, len(results)))
    return n == len(results)


def main():
    argv = sys.argv[1:]
    man = argv[0] if argv and not argv[0].startswith("--") else "Saud"

    def arg(name, default):
        return type(default)(argv[argv.index(name) + 1]) if name in argv else default
    is_bite = "--bite" in argv
    height = arg("--height", 400 if is_bite else 1200)
    samples = arg("--samples", 4 if is_bite else 32)
    size = (int(round(height * ASPECT)), height)
    anim = os.path.abspath(arg("--anim", os.path.join(PROJECT, "Content", "Animation", man)))
    if is_bite:
        sys.exit(0 if bite(man, size, samples, anim) else 1)
    out = os.path.abspath(arg("--out", os.path.join(PROJECT, "Docs", "renders", "%s-ik-sheet.png" % man.lower())))
    only = arg("--only", "")
    pics, fails = run(man, [s for s in only.split(",") if s] if only else None, size, samples, anim)
    sheet(pics, size, out, man)
    if fails:
        print("CHECKS FAIL\n  " + "\n  ".join(fails))
        sys.exit(1)
    print("CHECKS PASS: %d panels" % len(pics))


if __name__ == "__main__":
    main()
