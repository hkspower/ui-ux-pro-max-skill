"""
The camera's fade, in a world material (2026-10-03, Riyadh; part of "make
it 3d dynamic view", settled as: smarter walls -- a wall between the camera
and Saud fades).

ASaudCharacter::UpdateCameraFades writes how far each surface between the
camera and Saud is faded (0..SaudCamera::FadeMax) into custom primitive data
slot SaudCamera::FadeDataIndex. A material reads it with this: a scalar
parameter bound to that slot (0 by default, so every other surface is
untouched), one minus it, dithered (DitherTemporalAA) into the opacity
mask, the material Masked. A dither and not translucency: the surface keeps
writing depth, so the anime look's ink lines and the world's shadows stay
whole, and the pattern resolves under TAA.

    add_fade(material)   inside the editor, once per material; returns
                         True if it added the nodes, False if they were there
    python3 Tools/look/camera_fade.py [--bite]   the check outside it

Used by Tools/look/surfaces.py (M_Surface, the souq's meshes) and
Tools/levels/build_world.py (M_World_Prim and M_World_Ember, the open
world's). check() below holds both callers, and the slot, to it -- outside
the editor, from the sources.

Read-reviewed, not run: the expression and property names are UE 5.4's as
remembered (a ScalarParameter's use_custom_primitive_data and
primitive_data_index; DitherTemporalAA's "Alpha Threshold" input).
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
PARAM = "CameraFade"
CAMERA_H = os.path.join(ROOT, "Source", "SaudFighter", "Combat", "SaudCamera.h")


def slot():
    """SaudCamera::FadeDataIndex, read from the header."""
    m = re.search(r"constexpr int FadeDataIndex = (\d+);", open(CAMERA_H).read())
    return int(m.group(1)) if m else None


def add_fade(material):
    import unreal  # noqa: E402  (only importable inside the editor)
    MEL = unreal.MaterialEditingLibrary
    for e in MEL.get_material_expressions(material) if hasattr(MEL, "get_material_expressions") else []:
        if isinstance(e, unreal.MaterialExpressionScalarParameter) and str(e.get_editor_property("parameter_name")) == PARAM:
            return False
    fade = MEL.create_material_expression(material, unreal.MaterialExpressionScalarParameter, -900, 900)
    fade.set_editor_property("parameter_name", PARAM)
    fade.set_editor_property("default_value", 0.0)
    fade.set_editor_property("use_custom_primitive_data", True)
    fade.set_editor_property("primitive_data_index", slot())
    keep = MEL.create_material_expression(material, unreal.MaterialExpressionOneMinus, -700, 900)
    MEL.connect_material_expressions(fade, "", keep, "")
    dither = MEL.create_material_expression(material, unreal.MaterialExpressionDitherTemporalAA, -500, 900)
    MEL.connect_material_expressions(keep, "", dither, "Alpha Threshold")
    MEL.connect_material_property(dither, "", unreal.MaterialProperty.MP_OPACITY_MASK)
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    material.set_editor_property("opacity_mask_clip_value", 0.5)
    return True


def check(texts=None):
    """Outside the editor: the slot is set, and every world material builder
    adds the fade -- including to a material that already existed."""
    T = texts or {}
    read = lambda rel: T.get(rel) if rel in T else open(os.path.join(ROOT, rel)).read()
    fails = []
    if not re.search(r"constexpr int FadeDataIndex = (\d+);", read("Source/SaudFighter/Combat/SaudCamera.h")):
        fails.append("SaudCamera.h has no FadeDataIndex for the materials to read")
    for rel, names in (("Tools/look/surfaces.py", ("surface",)),
                       ("Tools/levels/build_world.py", ("prim", "ember"))):
        src = read(rel)
        for n in names:
            if not re.search(r"camera_fade\.add_fade\(%s\)" % n, src):
                fails.append("%s does not fade %s when the camera looks through it" % (rel, n))
    src = read("Source/SaudFighter/Combat/SaudCharacter.cpp")
    if "SetCustomPrimitiveDataFloat(SaudCamera::FadeDataIndex" not in src:
        fails.append("ASaudCharacter does not write the fade into the slot the materials read")
    return fails


def bite():
    def broken(rel, old, new):
        t = open(os.path.join(ROOT, rel)).read()
        assert old in t, "sabotage did not apply: %s" % old
        return {rel: t.replace(old, new)}
    cases = {
        "no slot": broken("Source/SaudFighter/Combat/SaudCamera.h", "constexpr int FadeDataIndex", "constexpr int FadeSlot"),
        "souq unfaded": broken("Tools/look/surfaces.py", "camera_fade.add_fade(surface)", "False"),
        "ember unfaded": broken("Tools/levels/build_world.py", "camera_fade.add_fade(ember)", "False"),
        "never written": broken("Source/SaudFighter/Combat/SaudCharacter.cpp",
                                "SetCustomPrimitiveDataFloat(SaudCamera::FadeDataIndex", "SetCustomPrimitiveDataFloat(1"),
    }
    caught = 0
    for name, T in cases.items():
        m = check(T)
        caught += bool(m)
        print("  %-14s %s" % (name, ("caught: " + m[0]) if m else "NOT caught"))
    print("%d of %d sabotages caught" % (caught, len(cases)))
    return caught == len(cases) and not check()


if __name__ == "__main__":
    if "--bite" in sys.argv:
        sys.exit(0 if bite() else 1)
    miss = check()
    for m in miss:
        print("MISS " + m)
    print("camera fade: %s" % ("every world material reads slot %s" % slot() if not miss else "%d broken" % len(miss)))
    sys.exit(1 if miss else 0)
