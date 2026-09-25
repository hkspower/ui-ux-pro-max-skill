"""
The guard and kick documentation renders, struck again from a man's rig file
without rebuilding him.

    python3 pose_renders.py Saud Thug Brawler Saqr Boss Zayos [--samples 64]

The pipeline renders them once, at the end of a build that takes 25-45
minutes a man; a pose change (build_saud.GUARD, KICK, the fist) does not
need the mesh built again. Each rigs/<Man>.blend carries the studio and the
four cameras the pipeline rendered with -- Cam (the guard), Cam.001 (the
kick), Cam.002 (the A-pose), Cam.003 (the face) -- so this poses him
through the control rig, as the souq scene does (rig_full_ik.stance, fists
closed), and renders the first two from where they were rendered before, at
the pipeline's own size and samples. The rig file itself is not saved.

Made 2026-09-24 for "the best position for arm and hand": the guard's arms
were re-solved and the fists closed.
"""
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PROJECT = os.path.normpath(os.path.join(HERE, "..", ".."))
RENDERS = os.path.join(PROJECT, "Docs", "renders")


def render_man(name, samples=64):
    import build_saud as legacy
    import rig_full_ik as CR
    bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, "rigs", name + ".blend"))
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    mesh = next(o for o in bpy.data.objects
                if o.type == "MESH" and any(m.type == "ARMATURE" for m in o.modifiers))
    shots = (("guard", legacy.guard_for(name), ("l", "r"), "Cam"), ("kick", legacy.KICK, ("l",), "Cam.001"))
    for shot, stance, plant, cam in shots:
        CR.stance(rig, stance, mesh, plant=plant)
        for s in ("l", "r"):
            CR.set_prop(rig, "CTRL_hand_%s" % s, "fist", 1.0)
        bpy.context.scene.camera = bpy.data.objects[cam]
        out = os.path.join(RENDERS, "%s-%s-3d.png" % (name.lower(), shot))
        legacy.render(out, samples=samples, res=(1520, 2000))
        print("rendered", out)


if __name__ == "__main__":
    argv = sys.argv[1:]
    samples = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 64
    men = [a for a in argv if not a.startswith("--") and not a.isdigit()]
    for man in men:
        render_man(man, samples)
