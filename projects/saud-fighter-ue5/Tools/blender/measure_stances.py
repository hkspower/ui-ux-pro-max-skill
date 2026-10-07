#!/usr/bin/env python3
"""Each man's designed stance, measured off his own guard clip, for the
runtime posture stage (Unreal build; asked 2026-10-07, Riyadh, as "make body
Posture and Body Alignment and Straightness": keep stances, fix faults).

    python3 Tools/blender/measure_stances.py            write Source/SaudFighter/Combat/SaudStances.h
                                                        and Tools/harness/stance_clips.h
    python3 Tools/blender/measure_stances.py --check    fail if either is not what the clips say

Run with a Python that has bpy (Blender as a module), as measure_plants.py.

WHY. The in-game IK (Combat/SaudIK.h) straightens a man's posture after the
feet, the lean and the look have bent him: his hips level, his trunk not
tipped sideways, his shoulder line level, his head over his spine and his
eyes level, his hips not twisted against his feet. "Level" and "straight"
are his OWN: a peek-a-boo crouch carries its lead shoulder 5 degrees high,
an MMA stance leans its trunk 3 degrees to the lead side, ZAYOS stands
square. So the reference is each set's guard (A_<Set>_Guard, frame 0 --
build_saud.GUARDS by STANCE_OF / build_motion.GUARD_OF), measured here the
way SaudIK::MeasurePosture measures a pose, and the runtime corrects only a
man's departure from it.

WHAT IS MEASURED (mesh frame: cm, X forward, Y his right, Z up; the same
definitions as SaudIK.h's PostureMeasure, which tests/posture.cpp holds to
these numbers):
    HipRoll       the line thigh_l -> thigh_r against level, degrees, + right high
    ShoulderRoll  upperarm_l -> upperarm_r against level, degrees, + right high
    TrunkTilt     spine_01 -> spine_03 tipped toward his right (the shoulder
                  line's level direction), degrees -- the trunk under the
                  chest, so the chest's own roll is the shoulders' alone
    HeadOff       the head joint off the line spine_01 -> neck_01 carried on,
                  toward his right, cm
    EyeRoll       the head's own left-to-right axis against level, degrees
    Twist         the hip line's yaw less the feet's (ball_l -> ball_r), degrees
and the guard's joints themselves, which the harness poses and turns.

stance_clips.h (Tools/harness, test data only -- the engine never includes
it) holds every frame of Saud's motion-capture gaits (A_Saud_Mocap_*), the
one set of clips not built on a guard: the actor's own posture, which the
posture checks and the preview read.

Engine frame: Blender's is metres with the man facing -Y and his left at
+X, so engine = (-y, -x, z) x 100 (measure_plants.py's engine()).
"""
import csv
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
ANIM = os.path.join(ROOT, "Content", "Animation")
OUT = os.path.join(ROOT, "Source", "SaudFighter", "Combat", "SaudStances.h")
CLIPS_OUT = os.path.join(ROOT, "Tools", "harness", "stance_clips.h")

# the men's sets, each on his own guard (build_motion.GUARD_OF; Street the boxer's)
SETS = (("Saud", "Saud", "mma"), ("Street", "Street", "boxer"), ("Boss", "Bosses", "peekaboo"),
        ("Saqr", "Bosses", "kickboxer"), ("Zayos", "Bosses", "heavy"))
GAITS = ("A_Saud_Mocap_Walk_Slow", "A_Saud_Mocap_Walk", "A_Saud_Mocap_Walk_Brisk",
         "A_Saud_Mocap_Jog", "A_Saud_Mocap_Run")

# The joints, in the order SaudStances::FJoints keeps them.
JOINTS = ("pelvis", "thigh_l", "thigh_r", "calf_l", "calf_r", "foot_l", "foot_r", "ball_l", "ball_r",
          "spine_01", "spine_02", "spine_03", "neck_01", "head", "upperarm_l", "upperarm_r")
FIELDS = ("Pelvis", "Hip[0]", "Hip[1]", "Knee[0]", "Knee[1]", "Ankle[0]", "Ankle[1]", "Ball[0]", "Ball[1]",
          "Spine[0]", "Spine[1]", "Spine[2]", "Neck", "Head", "Shoulder[0]", "Shoulder[1]")


def engine(v, k=100.0):
    return (-v.y * k, -v.x * k, v.z * k)


def sample(path, frames):
    """Every frame's joints (cm) and the head's left-to-right axis, engine frame."""
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    pb = rig.pose.bones
    W = rig.matrix_world
    first = int(round(rig.animation_data.action.frame_range[0]))
    out = []
    for f in range(frames):
        bpy.context.scene.frame_set(f + first)
        bpy.context.view_layer.update()
        fr = {n: engine(W @ pb[n].head) for n in JOINTS}
        # the head bone's X is his left on this skeleton (build_motion's rig);
        # its negative is the eyes' line, left to right
        M = (W @ pb["head"].matrix).to_3x3().normalized()
        fr["side"] = engine(-M.col[0], 1.0)
        out.append(fr)
    return out


# --------------------------------------------- the measures, as SaudIK.h's
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def scale(a, k): return (a[0] * k, a[1] * k, a[2] * k)
def norm(a):
    n = math.sqrt(dot(a, a))
    return scale(a, 1.0 / n) if n > 1e-9 else (0.0, 0.0, 0.0)
def flat(a, up):  # a with its part along up taken out
    return sub(a, scale(up, dot(a, up)))
def elev(a, up):
    return math.degrees(math.asin(max(-1.0, min(1.0, dot(norm(a), up)))))
def yaw(a):
    return math.degrees(math.atan2(-a[0], a[1]))   # a left-to-right line along +Y is 0


def measures(fr, up=(0.0, 0.0, 1.0)):
    side = norm(flat(sub(fr["upperarm_r"], fr["upperarm_l"]), up))
    spine = norm(sub(fr["neck_01"], fr["spine_01"]))
    lat = norm(flat(side, spine))
    head = sub(fr["head"], fr["neck_01"])
    tw = yaw(sub(fr["thigh_r"], fr["thigh_l"])) - yaw(sub(fr["ball_r"], fr["ball_l"]))
    tw = (tw + 180.0) % 360.0 - 180.0
    return dict(HipRoll=elev(sub(fr["thigh_r"], fr["thigh_l"]), up),
                ShoulderRoll=elev(sub(fr["upperarm_r"], fr["upperarm_l"]), up),
                TrunkTilt=math.degrees(math.asin(max(-1.0, min(1.0, dot(norm(sub(fr["spine_03"], fr["spine_01"])), side))))),
                HeadOff=dot(head, lat),
                EyeRoll=elev(fr["side"], up),
                Twist=tw)


def vec(v):
    return "FVector(%.3f, %.3f, %.3f)" % v


def joints_init(fr):
    return "{ " + ", ".join(vec(fr[n]) for n in JOINTS) + ", " + vec(fr["side"]) + " }"


def rows():
    out = {}
    for folder in ("Saud", "Street", "Bosses"):
        names = ["DT_%sMotion.csv" % ("Boss" if folder == "Bosses" else folder)] + (["DT_SaudMocap.csv"] if folder == "Saud" else [])
        for n in names:
            with open(os.path.join(ANIM, folder, n), newline="", encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    out[r["Name"]] = dict(path=os.path.join(ANIM, folder, r["File"]), frames=int(r["Frames"]),
                                          seconds=float(r["Seconds"]))
    return out


def stances_header(stances):
    L = []
    w = L.append
    w("#pragma once")
    w("")
    w("/**")
    w(" * GENERATED by Tools/blender/measure_stances.py from each set's guard clip")
    w(" * (Content/Animation, A_<Set>_Guard, frame 0) -- never hand-edit; run the tool")
    w(" * again when a guard changes (--check says when).")
    w(" *")
    w(" * Each man's designed stance, measured the way SaudIK::MeasurePosture measures")
    w(" * a pose: the line of his hips and of his shoulders against level (degrees, +")
    w(" * his right side high), his trunk (spine_01 to spine_03) tipped toward his right,")
    w(" * his head joint off his spine's line toward his right (cm), his eyes' line")
    w(" * against level, and his hips' yaw less his feet's (degrees). The runtime")
    w(" * straightens only what departs from these. The joints are the guard's own,")
    w(" * mesh frame (cm, X forward, Y his right, Z up), for the harness.")
    w(" */")
    w("")
    w("#if defined(SAUD_HARNESS)")
    w("\t#include \"HarnessTypes.h\"")
    w("#else")
    w("\t#include \"CoreMinimal.h\"")
    w("#endif")
    w("")
    w("namespace SaudStances")
    w("{")
    w("\t/** A pose's joints, mesh frame, and the head's left-to-right axis. */")
    w("\tstruct FJoints")
    w("\t{")
    w("\t\tFVector Pelvis, Hip[2], Knee[2], Ankle[2], Ball[2], Spine[3], Neck, Head, Shoulder[2];")
    w("\t\tFVector HeadSide;")
    w("\t};")
    w("")
    w("\tstruct FStance")
    w("\t{")
    w("\t\tconst char* Set;          // the motion set, A_<Set>_*")
    w("\t\tconst char* Guard;        // build_saud.GUARDS' name")
    w("\t\tfloat HipRoll;            // degrees, + right high")
    w("\t\tfloat ShoulderRoll;       // degrees, + right high")
    w("\t\tfloat TrunkTilt;          // degrees toward his right")
    w("\t\tfloat HeadOff;            // cm toward his right")
    w("\t\tfloat EyeRoll;            // degrees, + right high")
    w("\t\tfloat Twist;              // degrees, hips' yaw less feet's")
    w("\t\tFJoints Joints;           // frame 0 of his guard")
    w("\t};")
    w("")
    w("\tconstexpr int NumStances = %d;" % len(stances))
    w("")
    w("\tinline const FStance Stances[NumStances] = {")
    for s in stances:
        m = s["m"]
        w('\t\t{ "%s", "%s", %.3ff, %.3ff, %.3ff, %.3ff, %.3ff, %.3ff,' % (
            s["set"], s["guard"], m["HipRoll"], m["ShoulderRoll"], m["TrunkTilt"], m["HeadOff"], m["EyeRoll"], m["Twist"]))
        w("\t\t  %s }," % joints_init(s["fr"]))
    w("\t};")
    w("")
    w("\t/** The stance of a motion set by name, or null (the Island's creatures have none). */")
    w("\tinline const FStance* Find(const char* Set)")
    w("\t{")
    w("\t\tif (!Set) return nullptr;")
    w("\t\tfor (const FStance& S : Stances)")
    w("\t\t{")
    w("\t\t\tconst char* A = S.Set;")
    w("\t\t\tconst char* B = Set;")
    w("\t\t\twhile (*A && *A == *B) { ++A; ++B; }")
    w("\t\t\tif (*A == 0 && *B == 0) return &S;")
    w("\t\t}")
    w("\t\treturn nullptr;")
    w("\t}")
    w("}")
    return "\n".join(L) + "\n"


def clips_header(gaits):
    L = []
    w = L.append
    w("#pragma once")
    w("")
    w("/**")
    w(" * GENERATED by Tools/blender/measure_stances.py -- test data, never included by")
    w(" * the game. Every frame of Saud's motion-capture gaits (A_Saud_Mocap_*), the")
    w(" * clips not built on a guard: the joints as SaudStances::FJoints keeps them.")
    w(" */")
    w("")
    w("#include \"../../Source/SaudFighter/Combat/SaudStances.h\"")
    w("")
    w("namespace StanceClips")
    w("{")
    w("\tstruct FClip { const char* Name; float Seconds; int Frames; const SaudStances::FJoints* Frame; };")
    w("")
    for g in gaits:
        w("\tinline const SaudStances::FJoints %s[%d] = {" % (g["name"], len(g["fr"])))
        for fr in g["fr"]:
            w("\t\t%s," % joints_init(fr))
        w("\t};")
    w("")
    w("\tconstexpr int NumClips = %d;" % len(gaits))
    w("\tinline const FClip Clips[NumClips] = {")
    for g in gaits:
        w('\t\t{ "%s", %.3ff, %d, %s },' % (g["name"], g["seconds"], len(g["fr"]), g["name"]))
    w("\t};")
    w("}")
    return "\n".join(L) + "\n"


def main():
    args = sys.argv[1:]
    R = rows()
    stances = []
    for st, _folder, guard in SETS:
        r = R["A_%s_Guard" % st]
        fr = sample(r["path"], 1)[0]
        # measured as written: the header's joints to the thousandth of a cm
        fr = {k: tuple(round(c, 3) for c in v) for k, v in fr.items()}
        m = measures(fr)
        stances.append(dict(set=st, guard=guard, fr=fr, m=m))
        print("  %-7s %-10s hips %+5.1f  shoulders %+5.1f  trunk %+5.1f  head %+5.2f cm  eyes %+5.1f  twist %+6.1f" % (
            st, guard, m["HipRoll"], m["ShoulderRoll"], m["TrunkTilt"], m["HeadOff"], m["EyeRoll"], m["Twist"]))
    gaits = []
    for name in GAITS:
        r = R[name]
        gaits.append(dict(name=name, seconds=r["seconds"], fr=sample(r["path"], r["frames"])))
    texts = {OUT: stances_header(stances), CLIPS_OUT: clips_header(gaits)}
    if "--check" in args:
        bad = [p for p, t in texts.items() if not os.path.exists(p) or open(p).read() != t]
        for p in bad:
            print("%s is not what the clips say: run Tools/blender/measure_stances.py" % os.path.relpath(p, ROOT))
        if bad:
            sys.exit(1)
        print("SaudStances.h and stance_clips.h match the %d guards and %d gaits" % (len(stances), len(gaits)))
        return
    for p, t in texts.items():
        with open(p, "w") as fh:
            fh.write(t)
        print("wrote %s" % os.path.relpath(p, ROOT))


if __name__ == "__main__":
    main()
