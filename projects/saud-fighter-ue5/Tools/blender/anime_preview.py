"""
What the anime look does to the real models, before any engine has run it.

Renders a .blend -- the souq fight scene, or a man's rig file -- once in
Cycles with the passes the engine's post-process reads from its G-buffer
(lit colour, base colour, world normal, depth, and which pixels are a
fighter), then runs Tools/look/anime_look.py's `preview()`, the numpy
mirror of M_Anime_Post's HLSL, over them.

    python3 Tools/blender/anime_preview.py scenes/SouqAlDawar_fight.blend \
        --out ../../Docs/renders/souq-fight-anime.png [--camera Cam.019]
        [--height 1080] [--samples 48] [--blow X Y] [--pair]
    python3 Tools/blender/anime_preview.py --men Saud Thug Brawler \
        --out ../../Docs/renders/anime-men.png

--pair writes the plain render beside it, for judging the change; --blow
also writes the impact frame, its flipped half and the speed lines round a
blow at (X, Y) of the screen; --men makes a sheet from the rig files, each
man full length over his face.

The G-buffer's base colour is the Diffuse Color pass, which since Blender
4.0 carries the subsurface albedo too -- the skin is a full-weight
subsurface material. What writes custom depth in the engine -- the
fighters, SaudAnime.h -- is here every mesh deformed by an armature.

Exposure: the engine's is its eye adaptation, and MPC_Anime.Key is the dial
that sets which light counts as "lit". Here there is no eye adaptation, so
the key is taken from the picture: the 55th percentile of the light the
fighters receive. That is the preview standing in for an engine, and it is
said so rather than tuned to look right.
"""

import os
import sys
import tempfile

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "look"))
import anime_look as AL  # noqa: E402

# The preview's stand-in for eye adaptation: the light the fighters receive,
# at this percentile, counts as "lit". Tuned by eye on the souq fight scene.
KEY_PERCENTILE = 55

PASSES = (("Image", "RGBA"), ("Diffuse Color", "RGBA"),
          ("Normal", "VECTOR"), ("Depth", "FLOAT"), ("Object Index", "FLOAT"))


def _arg(name, default=None, n=1):
    if name not in sys.argv:
        return default
    i = sys.argv.index(name)
    v = sys.argv[i + 1:i + 1 + n]
    return v[0] if n == 1 else v


def render_passes(blend, camera=None, height=1080, samples=48):
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    if camera:
        sc.camera = bpy.data.objects[camera]
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
    # One sample of depth, normal and index per pixel would alias the lines;
    # Cycles filters them over the pixel like the colour, which is closer to
    # an engine's TAA-resolved G-buffer than point samples would be.
    vl = sc.view_layers[0]
    vl.use_pass_z = True
    vl.use_pass_normal = True
    vl.use_pass_diffuse_color = True
    vl.use_pass_object_index = True
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.pass_index = 1 if any(m.type == "ARMATURE" for m in o.modifiers) else 0

    out_dir = tempfile.mkdtemp(prefix="anime_")
    nt = bpy.data.node_groups.new("AnimePasses", "CompositorNodeTree")
    sc.compositing_node_group = nt
    rl = nt.nodes.new("CompositorNodeRLayers")
    fo = nt.nodes.new("CompositorNodeOutputFile")
    fo.directory = out_dir + "/"
    fo.file_name = "p_"
    fo.format.media_type = "IMAGE"
    fo.format.file_format = "OPEN_EXR"
    fo.format.color_depth = "32"
    for name, kind in PASSES:
        item = fo.file_output_items.new(kind, name.replace(" ", ""))
        nt.links.new(rl.outputs[name], fo.inputs[item.name])
    bpy.ops.render.render(write_still=False)

    got = {}
    import shutil
    for name, _ in PASSES:
        key = name.replace(" ", "")
        path = [f for f in os.listdir(out_dir) if f.startswith("p_" + key)][0]
        img = bpy.data.images.load(os.path.join(out_dir, path))
        w, h = img.size
        a = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(a)
        # Blender's rows run bottom up; a screen UV's top down.
        got[key] = a.reshape(h, w, 4)[::-1].astype(np.float64)
    exposure = 2.0 ** sc.view_settings.exposure
    for img in [i for i in bpy.data.images if i.filepath.startswith(out_dir)]:
        bpy.data.images.remove(img)
    shutil.rmtree(out_dir, ignore_errors=True)
    return got, exposure


def look_from(got, exposure, **kw):
    """The anime look over one render's passes; returns 8-bit sRGB and the
    preview's masks."""
    C = got["Image"][..., :3]
    A = got["DiffuseColor"][..., :3]
    N = got["Normal"][..., :3]
    D = got["Depth"][..., 0] * 100.0            # metres to the engine's cm
    D = np.where(D > 1e8, 1e10, D)               # nothing hit: the sky
    fighter = got["ObjectIndex"][..., 0] > 0.5
    luma = np.array(AL.LUMA)
    T = (C * exposure @ luma) / np.maximum(A @ luma, 0.02)
    body = fighter if fighter.any() else (D < 1e8)
    key = float(np.percentile(T[body], KEY_PERCENTILE)) if body.any() else 1.0
    look, m = AL.preview(C, A, N, D, fighter, exposure=exposure, key=key, **kw)
    m["key"] = key
    m["fighter"] = fighter
    return AL.to_srgb8(look * exposure), m


def plain_from(got, exposure):
    return AL.to_srgb8(got["Image"][..., :3] * exposure)


def main():
    from PIL import Image
    out = os.path.abspath(_arg("--out", "anime_preview.png"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    height, samples = int(_arg("--height", 1080)), int(_arg("--samples", 48))

    if "--men" in sys.argv:
        # A sheet: each man full length (Cam.002) over his face (Cam.003),
        # from his rig file.
        i = sys.argv.index("--men")
        men = [a for a in sys.argv[i + 1:] if not a.startswith("--")]
        men = men[:men.index(out)] if out in men else men
        cols = []
        for man in men:
            blend = os.path.join(HERE, "rigs", man + ".blend")
            body, e = render_passes(blend, "Cam.002", height, samples)
            b, _ = look_from(body, e)
            face, e = render_passes(blend, "Cam.003", height // 2, samples)
            f, _ = look_from(face, e)
            w = b.shape[1] // 2                  # the middle half of a square frame
            b = b[:, w // 2: w // 2 + w]
            f = np.asarray(Image.fromarray(f).resize((w, w)))
            cols.append(np.vstack([b, f]))
        Image.fromarray(np.hstack(cols)).save(out)
        print("anime preview: %s  (%s)" % (out, ", ".join(men)))
        return

    got, exposure = render_passes(os.path.abspath(sys.argv[1]), _arg("--camera"), height, samples)
    pic, m = look_from(got, exposure)
    if "--pair" in sys.argv:
        pic = np.hstack([plain_from(got, exposure), pic])
    Image.fromarray(pic).save(out)
    print("anime preview: %s  key %.3f  fighters %.1f %% of the frame  ink %.1f %%  deep shadow %.1f %%"
          % (out, m["key"], 100 * m["fighter"].mean(), 100 * (m["ink"] > 0.5).mean(),
             100 * (m["deep"] > 0.5).mean()))

    # --blow X Y: the same frame on a blow at (X, Y) of the screen -- the
    # impact frame, and the frame after it with the speed lines.
    blow = _arg("--blow", None, 2)
    if blow:
        c = tuple(float(v) for v in blow)
        stem = os.path.splitext(out)[0]
        imp, _ = look_from(got, exposure, impact=1.0)
        inv, _ = look_from(got, exposure, impact=1.0, invert=1.0)
        spd, _ = look_from(got, exposure, speed=1.0, centre=c, seed=3.0)
        Image.fromarray(imp).save(stem + "-impact.png")
        Image.fromarray(inv).save(stem + "-impact-flipped.png")
        Image.fromarray(spd).save(stem + "-speedlines.png")
        print("  and %s-{impact,impact-flipped,speedlines}.png" % stem)


if __name__ == "__main__":
    main()
