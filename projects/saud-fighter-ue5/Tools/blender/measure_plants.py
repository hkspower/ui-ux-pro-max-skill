#!/usr/bin/env python3
"""Where every clip's feet are on the floor, measured from the clips
themselves (Unreal build; asked 2026-10-02 as "improve plants ik").

    python3 Tools/blender/measure_plants.py            write Source/SaudFighter/Combat/SaudPlants.h
    python3 Tools/blender/measure_plants.py --check    fail if that file is not what the clips say
    python3 Tools/blender/measure_plants.py --dump NAME [NAME ...] --out FILE.json
                                                       every frame's heel and ball, for the plant sheet

WHY. The runtime IK (Combat/SaudIK.h) holds a planted foot where it was put
down. Until now it guessed which foot was planted from how high the clip had
it, every frame, against thresholds no clip was ever measured against. The
clips are all here, every frame of every one, so this reads them: each of
the 197 FBX files in Content/Animation is imported and every frame's ankle
(foot_l/r) and ball (ball_l/r) is read, in the engine's frame. A foot is
DOWN on a frame when its ball is within BallDown of where that man's ball
sits in his own guard, and FLAT when its ankle is within AnkleDown of where
his ankle sits there too (the heel on the floor). One-frame flickers are
smoothed out (a contact or a lift shorter than two frames is the frames
either side's).

THE REFERENCE. Not the importer's rest pose: for an armature-only FBX that is
the clip's own first frame (ik_sheet.py found this the hard way). Each set's
Guard clip (A_<Set>_Guard) stands still on the floor for its whole loop, and
the lower of its two feet in its first frame is flat (Saud's rear heel is up
in his stance; his lead foot is flat): that foot's ankle and ball heights are
the man's rest, for both feet -- except Saud's motion capture
(A_Saud_Mocap_*), which stands on its own actor's floor: each foot's own
lowest ball and ankle over its loop. A set is the clip name's second word (A_Saud_..., A_Street_...,
A_Boss_..., A_Saqr_..., A_Zayos_...).

WHAT IT WRITES. Source/SaudFighter/Combat/SaudPlants.h, generated, never
hand-edited: per clip its name, seconds, frame count, its own stride speed
(cm/s: how fast a planted ball travels back under a looping walk, which is
how fast the clip expects the man to move -- 0 for anything that does not
walk), and per foot one character a frame:
    '.'  in the air       'b'  down on the ball, heel up
    'f'  flat, heel and ball down
The engine finds a clip by its asset name. Frame f is at f / 30 s
(build_motion.FPS); Blender's importer puts authored frame f at f + 2
(build_motion.readback).

Engine frame: centimetres, X forward, Y right, Z up. Blender's is metres
with the man facing -Y and his left at +X, so engine = (-y, -x, z) x 100.
"""
import csv
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
ANIM = os.path.join(ROOT, "Content", "Animation")
OUT = os.path.join(ROOT, "Source", "SaudFighter", "Combat", "SaudPlants.h")
FPS = 30
FOLDERS = ("Saud", "Street", "Bosses")

# A ball within this of its guard height is on the floor, and an ankle
# within this of its guard height has the heel down. Saud's centimetres,
# grown with the man (his leg over Saud's 88.2 cm): the guard's own breath
# moves an ankle 0.3 cm, a walk's swing lifts a ball 6-10.
BallDown = 1.5
AnkleDown = 1.5
SAUD_LEG = 88.2
MIN_RUN = 2           # frames: a contact or a lift shorter than this is noise


def engine(v):
    """A Blender world point (m) in the engine's mesh frame (cm)."""
    return (-v.y * 100.0, -v.x * 100.0, v.z * 100.0)


def manifests():
    rows = []
    for folder in FOLDERS:
        path = os.path.join(ANIM, folder, "DT_%sMotion.csv" % ("Boss" if folder == "Bosses" else folder))
        # and Saud's motion capture (Tools/blender/mocap.py, its own manifest
        # beside his, since 2026-10-03: his walk and run picked by speed)
        extra = [os.path.join(ANIM, folder, "DT_SaudMocap.csv")] if folder == "Saud" else []
        for p in [path] + [e for e in extra if os.path.exists(e)]:
            with open(p, newline="", encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    r["folder"] = folder
                    rows.append(r)
    return rows


def set_of(name):
    return name.split("_")[1]


def sample(path, frames):
    """Every frame's ankle, ball, hip and knee for both legs, engine frame, cm."""
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    pb = rig.pose.bones
    W = rig.matrix_world
    out = []
    for f in range(frames):
        bpy.context.scene.frame_set(f + 2)
        bpy.context.view_layer.update()
        fr = {}
        for s in ("l", "r"):
            fr["ankle_" + s] = engine(W @ pb["foot_" + s].head)
            fr["ball_" + s] = engine(W @ pb["ball_" + s].head)
            fr["hip_" + s] = engine(W @ pb["thigh_" + s].head)
            fr["knee_" + s] = engine(W @ pb["calf_" + s].head)
        out.append(fr)
    return out


def leg_length(fr):
    """Hip to ankle along the leg in a guard frame, both sides averaged: the
    man's size against Saud's. (Straight-line, so a bent guard reads a little
    short; it is only used to scale the thresholds.)"""
    d = [math.dist(fr["hip_" + s], fr["ankle_" + s]) for s in ("l", "r")]
    return 0.5 * (d[0] + d[1])


def debounce(flags):
    """Runs shorter than MIN_RUN frames take their neighbours' value."""
    n = len(flags)
    out = list(flags)
    i = 0
    while i < n:
        j = i
        while j < n and out[j] == out[i]:
            j += 1
        if j - i < MIN_RUN and 0 < i and j < n and out[i - 1] == out[j]:
            for k in range(i, j):
                out[k] = out[i - 1]
        i = j
    return out


def classify(frames, rest, scale):
    """Per foot, one character a frame: '.', 'b' or 'f'."""
    marks = {}
    for s in ("l", "r"):
        down = debounce([fr["ball_" + s][2] - rest["ball_" + s] <= BallDown * scale for fr in frames])
        flat = debounce([fr["ankle_" + s][2] - rest["ankle_" + s] <= AnkleDown * scale for fr in frames])
        marks[s] = "".join("f" if d and h else ("b" if d else ".") for d, h in zip(down, flat))
    return marks


def stride_speed(frames, marks, seconds, loop):
    """How fast a planted ball travels back under a looping walk: the clip's
    own ground speed, cm/s, along whichever way it travels. Zero for a clip
    that does not loop, or whose planted balls do not travel (a guard)."""
    if not loop:
        return 0.0
    dt = 1.0 / FPS
    v = []
    n = len(frames)
    for s in ("l", "r"):
        for f in range(n):
            g = (f + 1) % n
            if marks[s][f] != "." and marks[s][g] != ".":
                a, b = frames[f]["ball_" + s], frames[g]["ball_" + s]
                v.append((b[0] - a[0], b[1] - a[1]))
    if not v:
        return 0.0
    mx = sum(p[0] for p in v) / len(v) / dt
    my = sum(p[1] for p in v) / len(v) / dt
    speed = math.hypot(mx, my)
    return speed if speed > 20.0 else 0.0   # a guard's sway is not a walk


def measure(rows):
    by_set = {}
    for r in rows:
        by_set.setdefault(set_of(r["Name"]), []).append(r)
    clips = []
    for st, rs in sorted(by_set.items()):
        guard = next((r for r in rs if r["Name"] == "A_%s_Guard" % st), None)
        assert guard, "set %s has no guard to measure its floor from" % st
        g = sample(os.path.join(ANIM, guard["folder"], guard["File"]), 1)[0]
        # the lower of his two feet in the guard is his floor, for both: Saud's
        # rear heel stands 2.7 cm up in his stance, and that foot is on its ball
        ankle = min(g["ankle_l"][2], g["ankle_r"][2])
        ball = min(g["ball_l"][2], g["ball_r"][2])
        rest = {"ankle_l": ankle, "ankle_r": ankle, "ball_l": ball, "ball_r": ball}
        scale = leg_length(g) / SAUD_LEG
        for r in rs:
            n = int(r["Frames"])
            fr = sample(os.path.join(ANIM, r["folder"], r["File"]), n)
            here = rest
            if "_Mocap_" in r["Name"]:
                # motion capture (mocap.py) stands on its actor's floor, not
                # the guard's: each foot's own lowest ball and ankle over the
                # loop are where it is down. Against the guard's floor the
                # run's forefoot strike stood 1.5 cm proud and its right foot
                # was never seen down (2026-10-03, "improve gloss ik")
                here = {k: min(f[k][2] for f in fr) for k in ("ankle_l", "ankle_r", "ball_l", "ball_r")}
            marks = classify(fr, here, scale)
            loop = r["bLoop"].strip().lower() == "true"
            clips.append(dict(name=r["Name"], seconds=float(r["Seconds"]), frames=n, loop=loop,
                              stride=stride_speed(fr, marks, float(r["Seconds"]), loop),
                              l=marks["l"], r=marks["r"], scale=scale))
            print("  %-44s %3d  L %s" % (r["Name"], n, marks["l"]))
            print("  %-44s      R %s%s" % ("", marks["r"],
                                            "   stride %.0f cm/s" % clips[-1]["stride"] if clips[-1]["stride"] else ""))
    return clips


def header(clips):
    clips = sorted(clips, key=lambda c: c["name"])
    L = []
    w = L.append
    w("#pragma once")
    w("")
    w("/**")
    w(" * GENERATED by Tools/blender/measure_plants.py from Content/Animation -- never")
    w(" * hand-edit; run the tool again when a clip changes (--check says when).")
    w(" *")
    w(" * Where each clip's feet are on the floor, frame by frame, measured from the")
    w(" * clips themselves: '.' in the air, 'b' down on the ball with the heel up,")
    w(" * 'f' flat. Frame f is at f / 30 s. Stride is the clip's own ground speed in")
    w(" * cm/s for a looping walk (how fast its planted ball travels back), else 0.")
    w(" * Thresholds: a ball within %.1f cm and an ankle within %.1f cm of where that" % (BallDown, AnkleDown))
    w(" * man's stand in his own guard, grown with his leg over Saud's %.1f cm." % SAUD_LEG)
    w(" */")
    w("")
    w("namespace SaudPlants")
    w("{")
    w("\tstruct FClip")
    w("\t{")
    w("\t\tconst char* Name;")
    w("\t\tfloat Seconds;")
    w("\t\tint Frames;")
    w("\t\tfloat Stride;            // cm/s, a looping walk's own ground speed; 0 if it does not walk")
    w("\t\tconst char* Foot[2];     // left, right: one character a frame")
    w("\t};")
    w("")
    w("\tconstexpr float Fps = %d.f;" % FPS)
    w("\tconstexpr int NumClips = %d;" % len(clips))
    w("")
    w("\t/** By name, sorted, so a lookup can halve. */")
    w("\tinline constexpr FClip Clips[NumClips] = {")
    for c in clips:
        w('\t\t{ "%s", %.3ff, %d, %.1ff, { "%s", "%s" } },' % (c["name"], c["seconds"], c["frames"], c["stride"], c["l"], c["r"]))
    w("\t};")
    w("")
    w("\t/** The clip by its asset name, or null. */")
    w("\tinline const FClip* Find(const char* Name)")
    w("\t{")
    w("\t\tint Lo = 0, Hi = NumClips - 1;")
    w("\t\twhile (Lo <= Hi)")
    w("\t\t{")
    w("\t\t\tconst int Mid = (Lo + Hi) / 2;")
    w("\t\t\tconst char* A = Clips[Mid].Name;")
    w("\t\t\tconst char* B = Name;")
    w("\t\t\twhile (*A && *A == *B) { ++A; ++B; }")
    w("\t\t\tconst int Cmp = static_cast<int>(static_cast<unsigned char>(*A)) - static_cast<int>(static_cast<unsigned char>(*B));")
    w("\t\t\tif (Cmp == 0) return &Clips[Mid];")
    w("\t\t\tif (Cmp < 0) Lo = Mid + 1; else Hi = Mid - 1;")
    w("\t\t}")
    w("\t\treturn nullptr;")
    w("\t}")
    w("}")
    return "\n".join(L) + "\n"


def main():
    args = sys.argv[1:]
    rows = manifests()
    if "--dump" in args:
        names = args[args.index("--dump") + 1:]
        out = args[args.index("--out") + 1] if "--out" in args else None
        names = [n for n in names if not n.startswith("--") and n != out]
        want = [r for r in rows if r["Name"] in names]
        assert len(want) == len(names), "unknown clip(s): %s" % sorted(set(names) - {r["Name"] for r in want})
        data = {}
        for r in want:
            fr = sample(os.path.join(ANIM, r["folder"], r["File"]), int(r["Frames"]))
            data[r["Name"]] = dict(seconds=float(r["Seconds"]), loop=r["bLoop"].strip().lower() == "true", frames=fr)
        with open(out, "w") as fh:
            json.dump(data, fh)
        print("wrote %d clips to %s" % (len(data), out))
        return
    clips = measure(rows)
    text = header(clips)
    if "--check" in args:
        have = open(OUT).read() if os.path.exists(OUT) else ""
        if have != text:
            print("SaudPlants.h is not what the clips say: run Tools/blender/measure_plants.py")
            sys.exit(1)
        print("SaudPlants.h matches the %d clips" % len(clips))
        return
    with open(OUT, "w") as fh:
        fh.write(text)
    print("wrote %s: %d clips" % (os.path.relpath(OUT, ROOT), len(clips)))


if __name__ == "__main__":
    main()
