"""
The live title, before any engine has run it (2026-10-01, Riyadh): the
souq fight scene rendered from the title's own shot, in the anime look,
with the real Title menu drawn over it.

    python3 Tools/blender/title_preview.py [--out DIR] [--samples 48]

writes, into DIR (default Docs/renders/):
    menu-title-3d.png       1920 x 1080, the front of the sweep (T 0 s)
    menu-title-3d-4x3.png   1600 x 1200, the sweep's end (T 7 s, 38 degrees)

How: Tools/harness/title_dump.cpp prints SaudTitle::Shoot (Combat/SaudTitle.h
-- the function ASaudTitleCamera calls every frame) for Saud's feet and
facing as the scene has them, in the engine's frame; the eye and the view
are carried into Blender's (metres, and Y mirrored: the engine's frame is
left-handed, Blender's right-handed, and the mirror is the one the FBX
round trip makes, so the picture is the same picture); the eye is pulled
in to the first wall between it and him, as ASaudTitleCamera's sweep does;
anime_preview.render_scene + look_from render it and put the look on; and
menu_preview's dump of the Title is rasterised over it with hud_preview's
rasteriser, as menu-title.png is.

Then it measures where he landed: the middle of his pixels across the
screen against SaudTitle's HoldX, and the left of them against the wash's
right edge. The harness already proves the geometry on a box; this proves
the box's numbers were carried into a real render the right way round.

STAND-INS, not the engine's:
  - the other three men are hidden: the scene is a fight in progress, and
    under the title he stands alone where the level put him. Saud keeps
    the scene's pose, his guard, held still -- in the game the guard's
    idle clip plays under the title (on real time, through the pause);
  - the look's key and the lettering are anime_preview's and hud_preview's
    stand-ins (their own notes);
  - the wall test is a ray, not the engine's 12 cm sphere.
"""

import json
import math
import os
import subprocess
import sys
import tempfile

import bpy
import numpy as np
from mathutils import Vector
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "look"))
import anime_preview as AP  # noqa: E402
import hud_preview  # noqa: E402
import menu_preview  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SCENE = os.path.join(HERE, "scenes", "SouqAlDawar_fight.blend")
WALL_PROBE = 0.12          # m: ASaudTitleCamera's WallProbe
AIM_Z = 0.98               # m: SaudTitle::AimZ

SHOTS = (
    ("menu-title-3d.png", 1920, 1080, 0.0),
    ("menu-title-3d-4x3.png", 1600, 1200, 7.0),
)
MENU = dict(screen="title", pad="xbox", focus=0, save=0, clock=0.62, since=1.0)


def arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def build_title_dump(tmp):
    exe = os.path.join(tmp, "title_dump")
    cxx = os.environ.get("CXX", "g++")
    subprocess.check_call([cxx, "-std=c++17", "-O1", "-Wall", "-Wextra", "-Werror", "-DSAUD_HARNESS",
                           "-I" + os.path.join(ROOT, "Tools", "harness"), "-o", exe,
                           os.path.join(ROOT, "Tools", "harness", "title_dump.cpp")])
    return exe


def to_engine(v):
    """A Blender point (m, right-handed) in the engine's frame (cm, left-handed)."""
    return Vector((v.x * 100.0, -v.y * 100.0, v.z * 100.0))


def to_blender(v):
    return Vector((v[0] / 100.0, -v[1] / 100.0, v[2] / 100.0))


def saud_alone():
    """Saud's rig, with every other man hidden from the render."""
    saud, others = AP.scene_rigs()
    gone = set(others)
    for o in bpy.data.objects:
        if o.type == "MESH" and any(m.type == "ARMATURE" and m.object in gone for m in o.modifiers):
            o.hide_render = True
        if o.parent in gone:
            o.hide_render = True
    for r in others:
        r.hide_render = True
    return saud


def feet_and_facing(saud):
    """Where he stands (the rig's origin, on the floor) and which way he
    faces: the rig's forward, which is its local -Y. Checked against the
    guard: his fists are out in front of his pelvis."""
    feet = saud.matrix_world.translation.copy()
    f = saud.matrix_world.to_3x3() @ Vector((0.0, -1.0, 0.0))
    f.z = 0.0
    f.normalize()
    pb = saud.pose.bones
    fists = (saud.matrix_world @ pb["hand_l"].head + saud.matrix_world @ pb["hand_r"].head) * 0.5
    ahead = fists - saud.matrix_world @ pb["pelvis"].head
    ahead.z = 0.0
    assert ahead.normalized().dot(f) > 0.5, "the rig's forward is not where his fists are"
    return feet, f


def clear_eye(aim, eye, saud_meshes):
    """The eye pulled in to the first wall on the line from the aim, as
    ASaudTitleCamera does (him ignored)."""
    dg = bpy.context.evaluated_depsgraph_get()
    sc = bpy.context.scene
    d = eye - aim
    full = d.length
    d.normalize()
    start, gone = aim.copy(), 0.0
    while gone < full:
        hit, loc, _, _, obj, _ = sc.ray_cast(dg, start, d, distance=full - gone)
        if not hit:
            return eye, None
        if obj is not None and (obj.name in saud_meshes or obj.hide_render):
            step = (loc - start).length + 1e-3
            start = loc + d * 1e-3
            gone += step
            continue
        at = (loc - aim).length - WALL_PROBE
        return aim + d * max(at, 0.3), obj.name if obj else "?"
    return eye, None


def place_camera(shot, eye):
    cam = bpy.data.objects.get("Cam_title")
    if cam is None:
        data = bpy.data.cameras.new("Cam_title")
        cam = bpy.data.objects.new("Cam_title", data)
        bpy.context.scene.collection.objects.link(cam)
    cam.data.lens_unit = "FOV"
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.angle = math.radians(shot["hfov"])
    cam.data.clip_start = 0.05
    cam.data.clip_end = 2000.0
    fwd = to_blender([c * 100.0 for c in shot["forward"]]).normalized()
    cam.location = eye
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = fwd.to_track_quat("-Z", "Y")
    return cam


def draw_menu(exe, disp, w, h):
    d = menu_preview.dump(exe, w, h, MENU)
    assert not d["overflow"], "the menu's draw list overflowed"
    r = hud_preview.Raster(Image.fromarray(disp), 3 if w <= 2560 else 2)
    done = 0
    for item in d["texts"]:
        for t in d["tris"][done:item["after"]]:
            r.tri(t)
        done = item["after"]
        r.text(item["string"], item)
    for t in d["tris"][done:]:
        r.tri(t)
    return r.image()


def main():
    out_dir = arg("--out", os.path.join(ROOT, "Docs", "renders"))
    samples = int(arg("--samples", "48"))
    os.makedirs(out_dir, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=SCENE)
    saud = saud_alone()
    saud_meshes = {o.name for o in bpy.data.objects
                   if o.type == "MESH" and any(m.type == "ARMATURE" and m.object is saud for m in o.modifiers)}
    feet, facing = feet_and_facing(saud)
    fe, ff = to_engine(feet), to_engine(facing) / 100.0
    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        tdump = build_title_dump(tmp)
        mdump = menu_preview.build_dump(tmp)
        for name, w, h, t in SHOTS:
            shot = json.loads(subprocess.check_output(
                [tdump, str(w), str(h), str(t), "%.4f" % fe.x, "%.4f" % fe.y, "%.4f" % fe.z,
                 "%.6f" % ff.x, "%.6f" % ff.y]))
            eye = to_blender(shot["eye"])
            aim = feet + Vector((0.0, 0.0, AIM_Z))
            eye, wall = clear_eye(aim, eye, saud_meshes)
            cam = place_camera(shot, eye)
            got, exposure = AP.render_scene(camera=cam, size=(w, h), samples=samples)
            disp, m = AP.look_from(got, exposure)
            him = got["ObjectIndex"][..., 0] > 1.5
            xs = np.nonzero(him.any(axis=0))[0]
            ys = np.nonzero(him.any(axis=1))[0]
            mid = 0.5 * (xs.min() + xs.max()) / w
            left = xs.min() / w
            tall = (ys.max() - ys.min()) / h
            img = draw_menu(mdump, disp, w, h)
            path = os.path.join(out_dir, name)
            img.save(path)
            print("%s: %dx%d, T %.1f s, sweep %.1f deg, distance %.0f cm%s" % (
                path, w, h, t, shot["sweep"], shot["dist"],
                ", pulled in by %s" % wall if wall else ""))
            print("   him: x %.3f-%.3f (middle %.3f; the shot holds %.3f), %.0f %% of the height; "
                  "the wash ends at %.3f" % (left, xs.max() / w, mid, shot["hold"], tall * 100.0, shot["free_left"]))
            if left < shot["free_left"]:
                print("   MISS: the menu's wash covers him")
                bad += 1
            if abs(shot["sweep"]) < 1.0 and abs(mid - shot["hold"]) > 0.05:
                print("   MISS: he is not where the shot holds him")
                bad += 1
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
