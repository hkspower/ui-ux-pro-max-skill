"""
What the anime look does to the real models, before any engine has run it.

Renders a .blend -- the souq fight scene, or a man's rig file -- once in
Cycles with the passes the engine's post-process reads from its G-buffer
(lit colour, base colour, world normal, depth, and which pixels are a
fighter), then runs Tools/look/anime_look.py's `look()`, the numpy
mirror of M_Anime_Post's and M_Anime_Frame's HLSL, over them.

    python3 Tools/blender/anime_preview.py scenes/SouqAlDawar_fight.blend \
        --out ../../Docs/renders/souq-fight-anime.png [--camera Cam_souq-fight]
        [--height 1080] [--samples 48] [--blow X Y] [--fire] [--rage] [--pair] [--street] [--sky]
    python3 Tools/blender/anime_preview.py --men Saud Thug Brawler \
        --out ../../Docs/renders/anime-men.png
    python3 Tools/blender/anime_preview.py scenes/SouqAlDawar_fight.blend \
        --night-check [--bite]        the night's light, before the grade
    python3 Tools/blender/anime_preview.py scenes/SouqAlDawar_fight.blend \
        --graded-check [--bite]       the graded night, men and world together

--pair writes the plain render beside it, for judging the change; --men
makes a sheet from the rig files, each man full length over his face;
--fire (2026-09-26) writes HAWK FIST's fire over the same frame: Saud's
lead fist lit as he stands (`-fire.png`), and a burning punch just landed
on the man nearest him (`-fire-hit.png`) -- the fist at its punching heat
and the burst 0.10 s old. The fist, the forearm and the man hit are read
off the scene's rigs and projected through its camera exactly as
USaudLookSubsystem projects them in the engine (Combat/SaudFire.h).

--blow X Y (2026-09-28, the dark seinen) writes the blow's frames AS THE
GAME DRAWS THEM: the impact frame with its speed lines together
(`-impact.png`; before, the two were rendered apart and the 14,944-colour
frame the game really drew was never seen), its flip (`-impact-flipped`),
the frame after with the lines alone (`-speedlines`), a parry's bone frame
(`-impact-parry`), a burning punch's ember frame (`-impact-burning`), the
mark a heavy blow leaves at 1/24 s, on the chin of the man nearest Saud
projected as the engine projects it (`-mark`), and Saud's own wound border
(`-wound`). The brush boils at BOIL, as it does in the game.

--street (2026-09-28, the night) previews the place renders by camera
name -- Cam_souq-street and Cam_souq-gate, the cameras build_souq.py
leaves in the scene -- as `souq-street-anime.png` and `souq-gate-anime.png`
beside --out. --sky (2026-10-02, the painted sky) turns the fight camera to
the moon and tips it up over the roofs: `souq-sky-anime.png` beside --out,
the night the look paints (anime_look.sky_paint) from each pixel's view ray
(view_of: the camera's own frame) and the scene's moon (moon_of: its sun's
bearing at the look's MOON_ELEV_DEG). --night-check measures the night's LIGHT before the grade
(the G-buffer's lit colour over its base colour: the materials drop out and
what is left is the light's level and hue); --graded-check (MERGE,
2026-09-28: men, world and look together) the graded picture at the
engine's key -- the fight camera for the men over the world and the
world's shadow fill over the ink, every place camera for the pools and the
fire's hue, and a camera at the opposing man's eyes for Saud's. Each prints
its numbers and, with --bite, proves every rule by a sabotage; a rule the
unbroken scene itself fails is reported and its sabotage left uncounted,
since a miss already there proves nothing. Read on the fast scene of
2026-09-30 (the old men): the graded night fails three of the six --
contrast 1.30, the gate's pools 1.37 and fire R/B 1.14 -- because the fire
pools survive the grade only as lamp cores; those three were proved to
bite on the street frame, where they pass (impl/preview/prove_graded2.py).

The G-buffer's base colour is the Diffuse Color pass, which since Blender
4.0 carries the subsurface albedo too -- the skin is a full-weight
subsurface material. What writes custom depth in the engine -- the
fighters, SaudAnime.h -- is here every mesh deformed by an armature
(ObjectIndex 1; Saud's own mesh 2, so a check can find him); every *_Eye
material on one of them carries EYE_INDEX in the Material Index pass.

Exposure: the engine's is its eye adaptation, and MPC_Anime.Key is the dial
that sets which light counts as "lit". Here there is no eye adaptation, so
the key is taken from the picture. With fighters in the frame it is the
55th percentile of the light they receive. Without them -- the street and
gate previews of the night -- it is KEY_OVER_MOON times the median light
of the MOON alone on the ground (the scene's lights are rendered in two
light groups, moon and fire, when build_souq.py has marked its fires with
night_fire = 1): the night is the shadow tone, what a fire lights is lit.
Keyed on the world's own median instead (the rule before 2026-09-28),
moonlit and fire-lit ground both landed on the lit tone and the pools
vanished (graded p95/p50 1.4-1.6 in the world survey). Both are
the preview standing in for an engine, and are said so rather than tuned
to look right.
"""

import math
import os
import shutil
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
# ... and without fighters, the night's: "lit" starts this far over the
# moon's own light on the ground (the world spec, 2026-09-28)
KEY_OVER_MOON = 2.0
# MPC_Anime.Boil as the game writes it every tick: a value, not zero, so
# the brush's pressure and the grain are drawn as they are in the game
BOIL = 3.0
# the Material Index every fighter's eye material renders with
EYE_INDEX = 7

PASSES = (("Image", "RGBA"), ("Diffuse Color", "RGBA"),
          ("Normal", "VECTOR"), ("Depth", "FLOAT"), ("Object Index", "FLOAT"),
          ("Material Index", "FLOAT"))
# the night's light groups, when the scene carries night_fire lights
GROUP_PASSES = (("Combined_moon", "RGBA"), ("Combined_fire", "RGBA"))
GROUND_NORMAL_Z = 0.85          # a ground pixel: the normal this near up ...
GROUND_WITHIN_CM = 6000.0       # ... and nearer than this
SITE_R = 0.18                   # the fight site's ground: this share of the height round its centre

# --night-check, on the LIGHT (lit/base): the world spec's numbers. Read on
# the fast fight scene of 2026-09-30: pools 8.39, R/B 60, moon B/R 1.82,
# the fire 0.61 of the light at the fight site (0.00 with the fires out).
NIGHT = dict(pools=2.5, warm_rb=2.0, moon_br=1.4, fire_share=0.5)
# --graded-check, on the graded picture (MERGE, 2026-09-28)
GRADED = dict(contrast=1.5, shadow_over_ink=2.0, pools=2.0, fire_rb=1.4,
              eye_share=0.5,          # of Saud's iris px drawn lit or shadow (not deep, ink, a dot)
              eye_min=0.0005)         # iris px seen, as a share of the face camera's frame (0.148 % facing his man; 0.005 % looking at the floor)

# --bite only: each breaks the one mechanism a check guards
SABOTAGE = set()
NIGHT_BITES = {"no_fires": "pools", "warm_moon": "moon"}
GRADED_BITES = {"flat_world": "contrast", "sooted_world": "shadow tone", "flat_pools": "pools",
                "grey_fire": "fire", "chin_down": "eyes", "deep_eyes": "eyes"}


def _arg(name, default=None, n=1):
    if name not in sys.argv:
        return default
    i = sys.argv.index(name)
    v = sys.argv[i + 1:i + 1 + n]
    return v[0] if n == 1 else v


# ================================================================= render
def _night_lights():
    return [o for o in bpy.data.objects if o.type == "LIGHT" and o.get("night_fire")]


def render_scene(camera=None, height=1080, samples=48, fit=False, size=None, groups=None):
    """The open scene as it stands, rendered once in Cycles with the passes
    the post-process reads; returns (passes, exposure). `camera` an object
    or its name; `size` (w, h) overrides `height` and the scene's aspect;
    the scene's resolution is left at the rendered size (ik_sheet projects
    through it afterwards). `groups`: the moon and fire light groups
    (Combined_moon, Combined_fire), by default whenever the scene has
    night_fire lights. Safe to call again and again on one open scene:
    the compositor group is reused, the loaded images removed."""
    from mathutils import Vector
    sc = bpy.context.scene
    if camera:
        sc.camera = bpy.data.objects[camera] if isinstance(camera, str) else camera
    if fit:
        # The rig files' cameras are framed for a man of Saud's 1.80 m; a
        # boss half again his size loses his head. Pull the camera back
        # along its own view, and up with him, by his height over 1.80.
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
    # One sample of depth, normal and index per pixel would alias the lines;
    # Cycles filters them over the pixel like the colour, which is closer to
    # an engine's TAA-resolved G-buffer than point samples would be.
    vl = sc.view_layers[0]
    vl.use_pass_z = True
    vl.use_pass_normal = True
    vl.use_pass_diffuse_color = True
    vl.use_pass_object_index = True
    vl.use_pass_material_index = True
    for o in bpy.data.objects:
        if o.type == "MESH":
            deformed = any(m.type == "ARMATURE" for m in o.modifiers)
            o.pass_index = (2 if o.name.startswith("Saud") else 1) if deformed else 0
            for s in o.material_slots:
                if s.material is not None:
                    s.material.pass_index = EYE_INDEX if deformed and "eye" in s.material.name.lower() else 0
    # the night's two light groups: every night_fire light is fire, every
    # other light and the sky are the moon
    fires = _night_lights()
    if groups is None:
        groups = bool(fires)
    if groups:
        have = {g.name for g in vl.lightgroups}
        for name in ("moon", "fire"):
            if name not in have:
                vl.lightgroups.add(name=name)
        for o in bpy.data.objects:
            if o.type == "LIGHT":
                o.lightgroup = "fire" if o.get("night_fire") else "moon"
        if sc.world is not None:
            sc.world.lightgroup = "moon"
    passes = PASSES + (GROUP_PASSES if groups else ())

    out_dir = tempfile.mkdtemp(prefix="anime_")
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
    for name, kind in passes:
        item = fo.file_output_items.new(kind, name.replace(" ", ""))
        nt.links.new(rl.outputs[name], fo.inputs[item.name])
    bpy.ops.render.render(write_still=False)

    got = {}
    for name, _ in passes:
        key = name.replace(" ", "")
        path = [f for f in os.listdir(out_dir) if f.startswith("p_" + key)][0]
        img = bpy.data.images.load(os.path.join(out_dir, path))
        w, h = img.size
        a = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(a)
        # Blender's rows run bottom up; a screen UV's top down.
        got[key] = a.reshape(h, w, 4)[::-1].astype(np.float64)
        bpy.data.images.remove(img)
    exposure = 2.0 ** sc.view_settings.exposure
    shutil.rmtree(out_dir, ignore_errors=True)
    got["View"] = view_of(got)          # this camera's, while it is the scene's
    return got, exposure


def render_passes(blend, camera=None, height=1080, samples=48, fit=False, groups=None):
    """Open the .blend, then render_scene."""
    bpy.ops.wm.open_mainfile(filepath=blend)
    return render_scene(camera=camera, height=height, samples=samples, fit=fit, groups=groups)


def project(world, cam=None):
    """A world point as the fire parameters want it: viewport fraction (Y
    down), scene depth in cm, and one of the browser's figure pixels there
    as a share of the viewport's height -- USaudLookSubsystem::Project."""
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    sc = bpy.context.scene
    cam = cam or sc.camera
    cm_per_px = AL.FIRE["FIGURE_CM"] / AL.FIRE["FIGURE_PX"]
    p = world_to_camera_view(sc, cam, Vector(world))
    q = world_to_camera_view(sc, cam, Vector(world) + Vector((0.0, 0.0, cm_per_px / 100.0)))
    aspect = sc.render.resolution_x / sc.render.resolution_y
    scale = ((q.x - p.x) ** 2 * aspect * aspect + (q.y - p.y) ** 2) ** 0.5
    return p.x, 1.0 - p.y, p.z * 100.0, scale


def fire_of(saud, hand="hand_l", forearm="lowerarm_l", heat=None, time=0.3):
    """The flame's parameters for a rig object's fist: where it is, which
    way the forearm points on the screen, how deep, how big."""
    sc = bpy.context.scene
    aspect = sc.render.resolution_x / sc.render.resolution_y
    fist = saud.matrix_world @ saud.pose.bones[hand].head
    elbow = saud.matrix_world @ saud.pose.bones[forearm].head
    x, y, depth, scale = project(fist)
    ex, ey, _, _ = project(elbow)
    dx, dy = (x - ex) * aspect, y - ey
    n = (dx * dx + dy * dy) ** 0.5
    dx, dy = (dx / n, dy / n) if n > 1e-6 else (0.0, -1.0)
    return dict(heat=heat, x=x, y=y, dir=(dx, dy), depth=depth, scale=scale, time=time)


def burn_of(victim, age=0.10, seed=3.0):
    """The burst's parameters on a rig object: at the actor's location, half
    his figure up -- his pelvis, near enough."""
    at = victim.matrix_world @ victim.pose.bones["pelvis"].head
    x, y, depth, scale = project(at)
    return dict(age=age, x=x, y=y, depth=depth, scale=scale, seed=seed)


CHIN_UNDER_HEAD_M = 0.10        # the chin, where the punches land (build_motion's VICTIM_CHIN), under the head joint


def mark_of(victim, age=1.0 / 24.0, seed=3.0):
    """The mark's parameters on a rig object: a heavy blow's impact point,
    which the engine keeps as an offset from the victim (MarkOffset) and
    projects each tick -- here his chin."""
    from mathutils import Vector
    at = victim.matrix_world @ victim.pose.bones["head"].head - Vector((0.0, 0.0, CHIN_UNDER_HEAD_M))
    x, y, depth, scale = project(at)
    return dict(age=age, x=x, y=y, depth=depth, scale=scale, seed=seed)


EYE_FORWARD_M = 0.09     # SaudAnime::Power::EyeForwardCm
EYE_APART_M = 0.064      # SaudAnime::Power::EyeApartCm


def aura_of(saud, level=0.55, time=0.4):
    """Saud's power-up as USaudLookSubsystem::WritePower writes it, from his
    rig: his middle (the pelvis) projected, and his eyes from the head joint
    -- at the eye line -- forward along his facing (the rig's -Y) and apart
    across it."""
    from mathutils import Vector
    M = saud.matrix_world
    pelvis = M @ saud.pose.bones["pelvis"].head
    head = M @ saud.pose.bones["head"].head
    fwd = (M.to_3x3() @ Vector((0.0, -1.0, 0.0))).normalized()
    right = (M.to_3x3() @ Vector((-1.0, 0.0, 0.0))).normalized()
    x, y, depth, scale = project(pelvis)
    mid = head + fwd * EYE_FORWARD_M
    e0, e1 = project(mid - right * (EYE_APART_M / 2)), project(mid + right * (EYE_APART_M / 2))
    return dict(level=level, x=x, y=y, depth=depth, scale=scale, time=time,
                eyes=((e0[0], e0[1]), (e1[0], e1[1])), eye_depth=min(e0[2], e1[2]),
                eye_scale=0.5 * (e0[3] + e1[3]))


def saud_of(got):
    """His outline: the custom stencil's stand-in, the object index pass
    (render_scene gives Saud's meshes 2, every other fighter 1)."""
    return got["ObjectIndex"][..., 0] > 1.5


def scene_rigs():
    """The scene's fighters' rigs: Saud's and the others, the nearest first."""
    rigs = [o for o in bpy.data.objects if o.type == "ARMATURE" and "pelvis" in o.pose.bones]
    saud = [o for o in rigs if o.name.startswith("Saud")]
    if not saud:
        return None, []
    saud = saud[0]
    others = sorted((o for o in rigs if o is not saud),
                    key=lambda o: (o.matrix_world.translation - saud.matrix_world.translation).length)
    return saud, others


# =================================================================== light
def unpack(got, exposure):
    """The passes as the look wants them: pre-exposed lit colour, base
    colour, normals, depth in cm (the sky at 1e10), the fighter mask."""
    C = got["Image"][..., :3] * exposure
    A = got["DiffuseColor"][..., :3]
    N = got["Normal"][..., :3]
    D = got["Depth"][..., 0] * 100.0            # metres to the engine's cm
    D = np.where(D > 1e8, 1e10, D)               # nothing hit: the sky
    fighter = got["ObjectIndex"][..., 0] > 0.5
    return C, A, N, D, fighter


def ground_of(got):
    """Ground pixels: the normal up, near, not a fighter, not unlit black."""
    _, A, N, D, fighter = unpack(got, 1.0)
    return (N[..., 2] > GROUND_NORMAL_Z) & ~fighter & (D < GROUND_WITHIN_CM) & (A @ np.array(AL.LUMA) > 0.004)


def light_of(got, key="Image"):
    """The light a pixel receives, per channel: its lit colour over its
    base colour (the materials drop out). `key` Image, or a light group."""
    return got[key][..., :3] / np.maximum(got["DiffuseColor"][..., :3], 0.004)


def key_of(got, exposure):
    """MPC_Anime.Key's stand-in: the fighters' light at KEY_PERCENTILE, or
    without fighters KEY_OVER_MOON x the moon's median on the ground.
    Returns (key, the rule's name)."""
    C, A, N, D, fighter = unpack(got, exposure)
    luma = np.array(AL.LUMA)
    T = (C @ luma) / np.maximum(A @ luma, 0.02)
    if fighter.any():
        return float(np.percentile(T[fighter], KEY_PERCENTILE)), "fighters p%d" % KEY_PERCENTILE
    ground = ground_of(got)
    if "Combined_moon" in got and ground.any():
        Tm = (got["Combined_moon"][..., :3] * exposure @ luma) / np.maximum(A @ luma, 0.02)
        return KEY_OVER_MOON * float(np.median(Tm[ground])), "%.1fx the moon" % KEY_OVER_MOON
    body = D < 1e8
    return (float(np.percentile(T[body], KEY_PERCENTILE)) if body.any() else 1.0), "world p%d" % KEY_PERCENTILE


def view_of(got, cam=None):
    """The view ray of every pixel of a render (H,W,3, Blender's world, Z
    up) -- the engine's CameraVector turned round, which the painted sky
    is drawn from. Through the camera's own frame, so its sensor fit and
    shift are the render's."""
    from mathutils import Vector
    sc = bpy.context.scene
    cam = cam or sc.camera
    H, W = got["Image"].shape[:2]
    tr, br, bl, tl = [Vector(c) for c in cam.data.view_frame(scene=sc)]
    u = (np.arange(W) + 0.5) / W
    v = (np.arange(H) + 0.5) / H
    top = np.array(tl)[None, :] + (np.array(tr) - np.array(tl))[None, :] * u[:, None]       # (W,3)
    bot = np.array(bl)[None, :] + (np.array(br) - np.array(bl))[None, :] * u[:, None]
    d = top[None, :, :] + (bot - top)[None, :, :] * v[:, None, None]                       # (H,W,3), row 0 the top
    R = np.array(cam.matrix_world.to_3x3())
    d = d @ R.T
    return d / np.linalg.norm(d, axis=-1, keepdims=True)


def moon_of():
    """The moon the sky draws: on the bearing the scene's moon (its
    strongest sun lamp that is not a fire) shines from, at the look's
    MOON_ELEV_DEG -- the engine's MOON_DIR, from WORLD_RIG, the same way.
    The look's own when the scene has no sun."""
    suns = [o for o in bpy.data.objects if o.type == "LIGHT" and o.data.type == "SUN" and not o.get("night_fire")]
    if not suns:
        return AL.moon_dir()
    sun = max(suns, key=lambda o: o.data.energy)
    to = np.array(sun.matrix_world.to_3x3())[:, 2]           # a sun shines down its -Z: the moon is up its +Z
    az, el = math.atan2(to[1], to[0]), math.radians(AL.LOOK["MOON_ELEV_DEG"])
    return (math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))


def look_from(got, exposure, **kw):
    """Both anime materials over one render's passes; returns 8-bit display
    values and M_Anime_Post's masks. The engine's buffer is pre-exposed, so
    the lit colour goes in with the exposure already on it. The brush boils
    at BOIL unless told otherwise; the sky is painted from the scene
    camera's rays and the scene's moon."""
    C, A, N, D, fighter = unpack(got, exposure)
    key, rule = key_of(got, exposure)
    kw.setdefault("boil", BOIL)
    if "V" not in kw:
        kw["V"] = got["View"] if "View" in got else view_of(got)
    kw.setdefault("moon", moon_of())
    disp, m = AL.look(C, A, N, D, fighter, key=key, **kw)
    m["key"] = key
    m["key_rule"] = rule
    m["fighter"] = fighter
    return AL.to_8bit(disp), m


def plain_from(got, exposure):
    return AL.to_8bit(AL.to_display(got["Image"][..., :3] * exposure))


def terminator(m):
    """The lit/shadow terminator's length on the fighters, in pixels: where
    the shadow mask changes between neighbours (across or down), counted
    on fighter pixels. Long, and a face is breaking into blotches."""
    s = m["shadow"] > 0.5
    f = m["fighter"]
    across = (s[:, 1:] != s[:, :-1]) & f[:, 1:] & f[:, :-1]
    down = (s[1:, :] != s[:-1, :]) & f[1:, :] & f[:-1, :]
    return int(across.sum() + down.sum())


def fighter_stats(m):
    """Per 1000 fighter pixels: rim, screentone, terminator -- the numbers
    the look's tuning tracks (the face's blotchiness above all)."""
    n = max(1, int(m["fighter"].sum())) / 1000.0
    return dict(rim=float((m["rim"] > 0.5).sum() / n), screentone=float((m["screentone"] > 0.5).sum() / n),
                terminator=terminator(m) / n)


def describe(out, m):
    st = fighter_stats(m)
    print("anime preview: %s  key %.3f (%s)  fighters %.1f %% of the frame  ink %.1f %%  deep shadow %.1f %%  "
          "| per 1000 fighter px: rim %.1f  screentone %.1f  terminator %.1f"
          % (out, m["key"], m["key_rule"], 100 * m["fighter"].mean(), 100 * (m["ink"] > 0.5).mean(),
             100 * (m["deep"] > 0.5).mean(), st["rim"], st["screentone"], st["terminator"]))


# ================================================================ --street
PLACE_CAMERAS = ("souq-street", "souq-gate")     # build_souq.render names its camera Cam_<render name>


def street(out_dir, height, samples):
    """The place renders in the look, by camera name; the scene is open."""
    from PIL import Image
    done = []
    for name in PLACE_CAMERAS:
        cam = "Cam_" + name
        if cam not in bpy.data.objects:
            print("  --street: no camera %s in the scene (build_souq.py leaves one); skipped" % cam)
            continue
        got, e = render_scene(camera=cam, height=height, samples=samples)
        pic, m = look_from(got, e)
        path = os.path.join(out_dir, name + "-anime.png")
        Image.fromarray(pic).save(path)
        g = ground_of(got)
        Y = (pic.astype(float) / 255.0) @ np.array(AL.LUMA)
        print("  %s: key %.3f (%s), ground %.0f %% of the frame, graded ground p95/p50 %.2f, %.0f %% of it the shadow tone"
              % (path, m["key"], m["key_rule"], 100 * g.mean(),
                 np.percentile(Y[g], 95) / max(np.percentile(Y[g], 50), 1e-6), 100 * ((m["shadow"] > 0.5) & g).sum() / max(1, g.sum())))
        done.append(path)
    return done


# ================================================================== --sky
def sky_camera():
    """Cam_souq-sky (2026-10-02): the fight camera turned to the moon's
    bearing and tipped up until the moon stands in the upper part of the
    frame over the roofs -- the painted sky the fight camera, looking
    down the street, has behind it. Made in the open scene, never saved."""
    from mathutils import Vector
    fight = bpy.data.objects["Cam_souq-fight"]
    mo = moon_of()
    az = math.atan2(mo[1], mo[0])
    el = math.radians(AL.LOOK["MOON_ELEV_DEG"] - 8.0)
    d = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))
    cam = bpy.data.objects.get("Cam_souq-sky")
    if cam is None:
        cam = bpy.data.objects.new("Cam_souq-sky", fight.data.copy())
        bpy.context.scene.collection.objects.link(cam)
    cam.location = fight.location.copy()
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return cam


def sky_preview(out_dir, height, samples):
    """souq-sky-anime.png: the night over the souq toward the moon."""
    from PIL import Image
    cam = sky_camera()
    got, e = render_scene(camera=cam, height=height, samples=samples)
    pic, m = look_from(got, e)
    path = os.path.join(out_dir, "souq-sky-anime.png")
    Image.fromarray(pic).save(path)
    D = unpack(got, e)[3]
    print("  --sky: %s (the sky %.0f %% of the frame, key %.3f by %s)" % (
        path, 100.0 * (D > AL.LOOK["SKY_DEPTH_CM"]).mean(), m["key"], m["key_rule"]))


# =========================================================== --night-check
def site_ground(got, cam=None):
    """The fight site's ground in a fight camera's frame: the camera aims
    at the site's centre (build_souq.cameras: (cx, cy, 1.15)); the ground
    under that point, SITE_R of the height round it."""
    from mathutils import Vector
    import build_souq as BS
    sc = bpy.context.scene
    cam = cam or sc.camera
    M = cam.matrix_world
    o, d = M.translation, M.to_quaternion() @ Vector((0.0, 0.0, -1.0))
    t = (1.15 - o.z) / d.z
    at = o + d * t
    x, y, _, _ = project((at.x, at.y, BS.STREET_Z_CM / 100.0), cam)
    H, W = got["Depth"].shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    return ground_of(got) & (np.hypot((xx + 0.5) / H - x * W / H, (yy + 0.5) / H - y) < SITE_R)


def night_measure(street_got, fight_got):
    """The night's light, read off the G-buffer (lit / base, the materials
    dropped out): the street's pools, its warmth, the moon's colour, the
    fire's share at the fight site (the fight camera aims at it)."""
    luma = np.array(AL.LUMA)
    r = {}
    g = ground_of(street_got)
    L = light_of(street_got)
    lum = L @ luma
    gl = lum[g]
    r["pools"] = float(np.percentile(gl, 95) / max(np.percentile(gl, 50), 1e-9))
    top = g & (lum >= np.percentile(gl, 95))
    r["warm_rb"] = float(np.median(L[top][:, 0] / np.maximum(L[top][:, 2], 1e-6)))
    # The light-group passes are not denoised, and a point light's is
    # sparse per pixel at these samples (a median of per-pixel ratios read
    # the fire as nothing where its sum is half the light), so a group's
    # share and its colour are ratios of SUMS over the region.
    Lm = light_of(street_got, "Combined_moon")[g]
    r["moon_br"] = float(Lm[:, 2].sum() / max(Lm[:, 0].sum(), 1e-9))
    if fight_got is not None:
        s = site_ground(fight_got)
        Lf, Lt = light_of(fight_got, "Combined_fire") @ luma, light_of(fight_got) @ luma
        r["fire_share"] = float(Lf[s].sum() / max(Lt[s].sum(), 1e-9)) if s.any() else 0.0
        r["site_px"] = int(s.sum())
    return r


def night_misses(r):
    """What falls outside NIGHT. Each line names its rule."""
    miss = []
    if r["pools"] < NIGHT["pools"]:
        miss.append("the street has no pools: light p95/p50 %.2f, wanted %.1f" % (r["pools"], NIGHT["pools"]))
    if r["warm_rb"] < NIGHT["warm_rb"]:
        miss.append("the brightest light is not the fires': top-5 %% R/B %.2f, wanted %.1f" % (r["warm_rb"], NIGHT["warm_rb"]))
    if r["moon_br"] < NIGHT["moon_br"]:
        miss.append("the moon is not cold: moon-group B/R %.2f, wanted %.1f" % (r["moon_br"], NIGHT["moon_br"]))
    if "fire_share" in r and r["fire_share"] < NIGHT["fire_share"]:
        miss.append("the fight site is not fire-lit: the fire %.2f of the light on its ground, wanted %.2f" % (r["fire_share"], NIGHT["fire_share"]))
    return miss


def night_report(r):
    return ("street pools p95/p50 %.2f, brightest-5 %% light R/B %.2f, moon B/R %.2f"
            % (r["pools"], r["warm_rb"], r["moon_br"])
            + (", the fire %.2f of the light at the fight site (%d px)" % (r["fire_share"], r["site_px"]) if "fire_share" in r else ""))


def _sabotage_night(which):
    """On the open scene."""
    if which == "no_fires":
        for o in _night_lights():
            o.data.energy = 0.0
    elif which == "warm_moon":
        for o in bpy.data.objects:
            if o.type == "LIGHT" and o.data.type == "SUN":
                o.data.color = (1.0, 0.85, 0.63)
    else:
        raise SystemExit("no such sabotage: %s (%s)" % (which, ", ".join(NIGHT_BITES)))


def night_render(blend, height, samples, sabotage=None):
    bpy.ops.wm.open_mainfile(filepath=blend)
    assert _night_lights(), "%s has no night_fire lights: build_souq.py --scene since 2026-09-28 leaves them" % blend
    if sabotage:
        _sabotage_night(sabotage)
    assert "Cam_souq-street" in bpy.data.objects, "no Cam_souq-street in %s" % blend
    s, _ = render_scene(camera="Cam_souq-street", height=height, samples=samples, groups=True)
    f = None
    if "Cam_souq-fight" in bpy.data.objects:
        f, _ = render_scene(camera="Cam_souq-fight", height=height, samples=samples, groups=True)
    return night_measure(s, f)


def night_check(blend, height, samples, bite=False):
    r = night_render(blend, height, samples)
    miss = night_misses(r)
    print("night check: " + night_report(r))
    for m in miss:
        print("  MISS " + m)
    if not bite:
        assert not miss, "the night fails its own rules"
        print("NIGHT CHECK PASSES")
        return True
    assert not miss, "the unbroken night fails its own checks, so no sabotage can be counted"
    print("  (unbroken) passes")
    caught = 0
    for which, word in NIGHT_BITES.items():
        r = night_render(blend, height, samples, sabotage=which)
        miss = night_misses(r)
        hit = any(word in m for m in miss)
        caught += hit
        print("  %-10s %s: %s" % (which, "caught" if hit else "MISSED", "; ".join(miss) or night_report(r)))
    print("%d of %d night sabotages caught" % (caught, len(NIGHT_BITES)))
    return caught == len(NIGHT_BITES)


# ========================================================== --graded-check
def graded_picture(got, exposure, over=None):
    """The graded picture AT THE ENGINE'S KEY: the buffer over the
    preview's stand-in key, looked at with key 1.0 -- MPC_Anime.Key's value
    in the game (never written). The previews keep the stand-in level; a
    measure against an absolute (INK is 0.0022 whatever the light; the
    display encoding bends a ratio by its level) has to be taken where
    the engine draws. Returns linear out, the masks, the display picture
    and the key."""
    C, A, N, D, fighter = unpack(got, exposure)
    if "sooted_world" in SABOTAGE:
        # the world painted a quarter as dark, under the same light
        w = ~fighter[..., None]
        A, C = np.where(w, A * 0.25, A), np.where(w, C * 0.25, C)
    key, rule = key_of(got, exposure)
    with _look_over(**(over or {})):
        lin, m = AL.preview(C / key, A, N, D, fighter, key=1.0, boil=BOIL, V=got["View"] if "View" in got else view_of(got),
                            moon=moon_of())
        disp = AL.frame(AL.to_display(lin), fighter, D=D, boil=BOIL)
    m["emit"] = AL._smooth(AL.LOOK["EMIT_FROM"], 2.0 * AL.LOOK["EMIT_FROM"], m["T"])
    m["fighter"], m["key"], m["key_rule"], m["A"], m["D"] = fighter, key, rule, A, D
    return lin, m, disp


def graded_fight(got, exposure, over=None):
    """The fight camera: the men over the world, the world's shadow fill
    over the ink."""
    luma = np.array(AL.LUMA)
    lin, m, disp = graded_picture(got, exposure, over)
    fighter, D = m["fighter"], m["D"]
    Y = disp @ luma
    sky = D > AL.LOOK["SKY_DEPTH_CM"]
    world = ~fighter & ~sky
    r = dict(contrast=float(np.median(Y[fighter]) / max(np.median(Y[world]), 1e-6)),
             fighter_y=float(np.median(Y[fighter])), world_y=float(np.median(Y[world])))
    # the shadow FILL: the flat tone between the lines, no antialiased
    # edge of ink, dot or hatch in it, and no deep
    fill = (world & (m["shadow"] > 0.98) & (m["deep"] < 0.02) & (m["ink"] < 0.02)
            & (m["screentone"] < 0.02) & (m["hatch"] < 0.02))
    r["shadow_tone"] = float(np.percentile((lin @ luma)[fill], 5)) if fill.any() else 0.0
    r["fill_px"] = int(fill.sum())
    r["ink"] = float(np.dot(AL.LOOK["INK"], luma))
    return r, disp


def graded_place(got, exposure, over=None):
    """A place camera: the pools and the fire's hue on the graded ground.
    The hue is read on the pool's BODY -- lit ground that is not a lamp
    core (EMIT_FROM: a core keeps its raw light and would make the
    measure trivial) -- its brightest 5 %. A pool is ground the fire
    out-lights the moon on (build_souq NIGHT's own definition: the light
    groups' fire over moon). Until 2026-10-03 the body was any lit ground,
    and at the gate 78 % of its brightest 5 % lay outside every pool --
    moonlit pale flagstone, whose hue no grade can make the fire's."""
    luma = np.array(AL.LUMA)
    lin, m, disp = graded_picture(got, exposure, over)
    g = ground_of(got)
    Y = disp @ luma
    gl = Y[g]
    r = dict(key=m["key"], key_rule=m["key_rule"], fighters=int(m["fighter"].sum()),
             pools=float(np.percentile(gl, 95) / max(np.percentile(gl, 50), 1e-6)),
             shadow_share=float(((m["shadow"] > 0.5) & g).sum() / max(1, g.sum())),
             core_share=float(((m["emit"] > 0.5) & g).sum() / max(1, g.sum())))
    body = g & (m["shadow"] < 0.5) & (m["emit"] < 0.5)
    if "Combined_fire" in got:
        body = body & (got["Combined_fire"][..., :3] @ luma > got["Combined_moon"][..., :3] @ luma)
    if body.any():
        top = body & (Y >= np.percentile(Y[body], 95))
        rgb = disp[top]
        r["fire_rb"] = float(np.median(rgb[:, 0] / np.maximum(rgb[:, 2], 1.0 / 255.0)))
    else:
        r["fire_rb"] = 0.0
    return r, disp


def graded_eyes(got, exposure, over=None):
    """The face camera: Saud's iris and pupil (his eye material's darker
    albedo; the sclera is its pale) drawn lit or shadow, not deep, ink or
    a screentone dot."""
    luma = np.array(AL.LUMA)
    lin, m, disp = graded_picture(got, exposure, over)
    saud = got["ObjectIndex"][..., 0] > 1.5
    eye = saud & (got["MaterialIndex"][..., 0] > 0.5 * EYE_INDEX)     # the index is filtered over the pixel
    al = m["A"] @ luma
    iris = eye & (al < 0.5 * (al[eye].max() if eye.any() else 1.0))
    seen = iris & (m["deep"] < 0.5) & (m["ink"] < 0.5) & (m["screentone"] < 0.5)
    return dict(iris_px=int(iris.sum()), iris_seen=int(seen.sum()), eye_px=int(eye.sum()),
                seen_share=float(seen.sum()) / seen.size), disp


def graded_misses(r):
    """What falls outside GRADED. Each line names its rule."""
    miss = []
    if r["contrast"] < GRADED["contrast"]:
        miss.append("the men do not stand off the world: fighter/world contrast %.2f (display medians %.3f / %.3f), wanted %.1f"
                    % (r["contrast"], r["fighter_y"], r["world_y"], GRADED["contrast"]))
    if r["shadow_tone"] < GRADED["shadow_over_ink"] * r["ink"]:
        miss.append("the world's shadow tone sinks into the ink: fill p5 %.4f = %.2fx lum(INK), wanted %.0fx"
                    % (r["shadow_tone"], r["shadow_tone"] / r["ink"], GRADED["shadow_over_ink"]))
    for name, p in r["places"].items():
        if p["pools"] < GRADED["pools"]:
            miss.append("the grade flattens the pools at %s: graded ground p95/p50 %.2f, wanted %.1f" % (name, p["pools"], GRADED["pools"]))
        if p["fire_rb"] < GRADED["fire_rb"]:
            miss.append("the grade greys the fire at %s: pool body top-5 %% R/B %.2f, wanted %.1f" % (name, p["fire_rb"], GRADED["fire_rb"]))
    e = r["eyes"]
    if e["seen_share"] < GRADED["eye_min"]:
        miss.append("Saud's eyes are lost: %d iris px seen, %.3f %% of the face frame, wanted %.2f %% (are they turned to the man in front?)"
                    % (e["iris_seen"], 100 * e["seen_share"], 100 * GRADED["eye_min"]))
    elif e["iris_seen"] < GRADED["eye_share"] * e["iris_px"]:
        miss.append("Saud's eyes are lost: %d of %d iris px drawn lit or shadow, wanted %.0f %%"
                    % (e["iris_seen"], e["iris_px"], 100 * GRADED["eye_share"]))
    return miss


def graded_report(r):
    places = "; ".join("%s key %.3f (%s) pools %.2f, %.0f %% shadow tone, %.1f %% cores, fire R/B %.2f"
                       % (n, p["key"], p["key_rule"], p["pools"], 100 * p["shadow_share"], 100 * p["core_share"], p["fire_rb"])
                       for n, p in r["places"].items())
    return ("fighter/world contrast %.2f; world shadow fill p5 %.4f = %.2fx lum(INK) (%d px); %s; Saud's iris %d of %d px seen (%d eye px)"
            % (r["contrast"], r["shadow_tone"], r["shadow_tone"] / r["ink"], r["fill_px"], places,
               r["eyes"]["iris_seen"], r["eyes"]["iris_px"], r["eyes"]["eye_px"]))


class _look_over:
    """LOOK entries changed for one sabotage, put back after."""
    def __init__(self, **over):
        self.over = over

    def __enter__(self):
        self.was = {k: AL.LOOK[k] for k in self.over}
        AL.LOOK.update(self.over)

    def __exit__(self, *a):
        AL.LOOK.update(self.was)


FACE_LENS = 85.0


def face_camera():
    """Cam_saud-face: at the nearest other man's eyes, looking into
    Saud's -- what the man in front of him sees, in the fight's light.
    Made in the open scene, never saved."""
    saud, others = scene_rigs()
    assert saud is not None and others, "no Saud and another man in the scene"
    eye_of = lambda r: r.matrix_world @ r.pose.bones["head"].head
    at, to = eye_of(others[0]), eye_of(saud)
    cam = bpy.data.objects.get("Cam_saud-face")
    if cam is None:
        cd = bpy.data.cameras.new("Cam_saud-face")
        cam = bpy.data.objects.new("Cam_saud-face", cd)
        bpy.context.scene.collection.objects.link(cam)
    cam.data.lens = FACE_LENS
    cam.location = at
    cam.rotation_euler = (to - at).to_track_quat("-Z", "Y").to_euler()
    return cam


def _chin_down():
    """Saud made to look at the ground (CTRL_look at the other man's feet):
    the head pitches down and the brow overhangs the eyes."""
    import rig_full_ik as CR
    saud, others = scene_rigs()
    CR.set_world_translation(saud, "CTRL_look", others[0].matrix_world.translation.copy())
    bpy.context.view_layer.update()


def graded_render(blend, height, samples, out=None):
    """Open the scene and render what the graded check reads: the fight
    camera, every place camera present, the face camera."""
    bpy.ops.wm.open_mainfile(filepath=blend)
    assert "Cam_souq-fight" in bpy.data.objects, "no Cam_souq-fight in %s (build_souq.py --scene leaves its cameras)" % blend
    assert _night_lights(), "%s has no night_fire lights" % blend
    fight = render_scene(camera="Cam_souq-fight", height=height, samples=samples, groups=True)
    places = {}
    for name in PLACE_CAMERAS:
        if "Cam_" + name in bpy.data.objects:
            places[name] = render_scene(camera="Cam_" + name, height=height, samples=samples, groups=True)
    assert places, "no place camera (%s) in %s" % (", ".join("Cam_" + n for n in PLACE_CAMERAS), blend)
    face_camera()
    face = render_scene(camera="Cam_saud-face", samples=samples, size=(height, height), groups=True)
    return fight, places, face


def graded_measure(fight, places, face, over=None, out=None, tag=""):
    r, pic = graded_fight(*fight, over=over)
    r["places"] = {}
    pics = {"fight": pic}
    for name, got in places.items():
        r["places"][name], pics[name] = graded_place(*got, over=over)
    r["eyes"], pics["face"] = graded_eyes(*face, over=over)
    if out:
        from PIL import Image
        for name, p in pics.items():
            Image.fromarray(AL.to_8bit(p)).save(os.path.join(out, "graded-%s%s.png" % (name, tag)))
    return r


def graded_check(blend, height, samples, bite=False, out=None):
    if out:
        os.makedirs(out, exist_ok=True)
    fight, places, face = graded_render(blend, height, samples)
    r = graded_measure(fight, places, face, out=out)
    miss = graded_misses(r)
    print("graded check (at the engine's key): " + graded_report(r))
    for m in miss:
        print("  MISS " + m)
    if not bite:
        assert not miss, "the graded night fails its own rules"
        print("GRADED CHECK PASSES")
        return True
    clean_words = {w for w in GRADED_BITES.values() if any(w in m for m in miss)}
    print("  (unbroken) %s" % ("passes" if not miss else "FAILS %d of %d rules -- their sabotages cannot be counted" % (len(clean_words), len(GRADED_BITES))))
    caught = unproved = 0
    for which, word in GRADED_BITES.items():
        SABOTAGE.clear()
        SABOTAGE.add(which)
        # (since 2026-10-03: flat_world puts the men at the world's level
        # too -- they are lifted by their own now, and with the world's
        # alone at 1 the contrast held 1.58; sooted_world takes the black
        # ladder's floors with the soot, which hold the fill over the ink
        # whatever the paint; flat_pools takes the pool's steps, which make
        # the pools -- with the lamps put out instead, the street's pools
        # still read 2.02.)
        over = {"flat_world": dict(WORLD_LEVEL=1.0, FIGHTER_LEVEL=1.0), "grey_fire": dict(WORLD_SATURATION=0.10, POOL_SAT=0.10),
                "sooted_world": dict(BLACK_DEEP=0.0, BLACK_SHADOW=0.0, BLACK_LIT=0.0),
                "flat_pools": dict(POOL_DIM=1.0, POOL_BRIGHT=1.0), "deep_eyes": dict(T_DEEP=2.0)}.get(which, {})
        face2 = face
        if which == "chin_down":
            _chin_down()
            face2 = render_scene(camera="Cam_saud-face", samples=samples, size=(height, height), groups=True)
        r2 = graded_measure(fight, places, face2, over=over, out=out, tag="-" + which)
        miss2 = [m for m in graded_misses(r2) if word in m]
        if word in clean_words:
            unproved += 1
            print("  %-13s not proved (the unbroken already fails this rule): %s" % (which, "; ".join(miss2) or graded_report(r2)))
        else:
            caught += bool(miss2)
            print("  %-13s %s: %s" % (which, "caught" if miss2 else "MISSED", "; ".join(miss2) or graded_report(r2)))
    SABOTAGE.clear()
    print("%d of %d graded sabotages caught%s" % (caught, len(GRADED_BITES), ", %d not provable on this scene" % unproved if unproved else ""))
    return caught == len(GRADED_BITES) and not miss


# ==================================================================== main
def main():
    from PIL import Image
    out = os.path.abspath(_arg("--out", "anime_preview.png"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    height, samples = int(_arg("--height", 1080)), int(_arg("--samples", 48))

    if "--men" in sys.argv:
        # A sheet: each man full length (Cam.002) over his face (Cam.003),
        # from his rig file.
        i = sys.argv.index("--men")
        men = []
        for a in sys.argv[i + 1:]:          # the names, up to the next option
            if a.startswith("--"):
                break
            men.append(a)
        cols = []
        for man in men:
            blend = os.path.join(HERE, "rigs", man + ".blend")
            body, e = render_passes(blend, "Cam.002", height, samples, fit=True)
            b, mb = look_from(body, e)
            face, e = render_passes(blend, "Cam.003", height // 2, samples)
            f, mf = look_from(face, e)
            sb, sf = fighter_stats(mb), fighter_stats(mf)
            print("  %s: per 1000 fighter px, body rim %.1f screentone %.1f terminator %.1f; face rim %.1f screentone %.1f terminator %.1f"
                  % (man, sb["rim"], sb["screentone"], sb["terminator"], sf["rim"], sf["screentone"], sf["terminator"]))
            w = b.shape[1] // 2                  # the middle half of a square frame
            b = b[:, w // 2: w // 2 + w]
            f = np.asarray(Image.fromarray(f).resize((w, w)))
            cols.append(np.vstack([b, f]))
        Image.fromarray(np.hstack(cols)).save(out)
        print("anime preview: %s  (%s)" % (out, ", ".join(men)))
        return

    blend = os.path.abspath(sys.argv[1])
    if "--night-check" in sys.argv:
        ok = night_check(blend, int(_arg("--height", 540)), int(_arg("--samples", 16)), bite="--bite" in sys.argv)
        sys.exit(0 if ok else 1)
    if "--graded-check" in sys.argv:
        ok = graded_check(blend, int(_arg("--height", 540)), int(_arg("--samples", 16)), bite="--bite" in sys.argv,
                          out=_arg("--out"))
        sys.exit(0 if ok else 1)

    got, exposure = render_passes(blend, _arg("--camera"), height, samples)
    pic, m = look_from(got, exposure)
    stem = os.path.splitext(out)[0]
    saud, others = scene_rigs()

    # --fire: HAWK FIST on Saud, from the scene's own rigs, still open.
    if "--fire" in sys.argv:
        nearest = others[0]
        # Combat/SaudFire.h: 0.78 standing, 1.25 through a punch
        standing = fire_of(saud, heat=0.78)
        punching = fire_of(saud, heat=1.25, time=0.42)
        lit, _ = look_from(got, exposure, fist=standing)
        hit, _ = look_from(got, exposure, fist=punching, burn=burn_of(nearest))
        Image.fromarray(lit).save(stem + "-fire.png")
        Image.fromarray(hit).save(stem + "-fire-hit.png")
        print("  HAWK FIST: %s-fire.png (lit, %s's lead fist at %.2f %.2f, %.0f cm, a figure px %.4f of the height) "
              "and %s-fire-hit.png (burning, burst on %s)"
              % (stem, saud.name, standing["x"], standing["y"], standing["depth"], standing["scale"], stem, nearest.name))
    if "--pair" in sys.argv:
        pic = np.hstack([plain_from(got, exposure), pic])
    Image.fromarray(pic).save(out)
    describe(out, m)

    # --blow X Y: the same frame on a blow at (X, Y) of the screen, as the
    # game draws it: the impact frame WITH its speed lines, its flip, the
    # frame after with the lines alone; then the HUD's tones, the mark and
    # the wound.
    blow = _arg("--blow", None, 2)
    if blow:
        c = tuple(float(v) for v in blow)
        lines = dict(speed=1.0, centre=c, seed=3.0)
        # (a heavy blow's tone is the System's cyan since 2026-10-03: 3)
        frames = {"impact": dict(impact=1.0, tone=3.0, **lines),
                  "impact-flipped": dict(impact=1.0, invert=1.0, tone=3.0, **lines),
                  "speedlines": lines,
                  "impact-parry": dict(impact=1.0, tone=2.0, **lines),
                  "impact-burning": dict(impact=1.0, tone=1.0, **lines),
                  "wound": dict(wound=1.0)}
        if others:
            mk = mark_of(others[0])
            frames["mark"] = dict(mark=mk, **lines)
        for name, kw in frames.items():
            img, _ = look_from(got, exposure, **kw)
            Image.fromarray(img).save("%s-%s.png" % (stem, name))
        # the two-colour count the look promises, measured as its check
        # measures it, with the grain and the paper (drawn last) off
        with _look_over(GRAIN=0.0, PAPER=0.0):
            imp, _ = look_from(got, exposure, **frames["impact"])
        colours = len(np.unique(imp.reshape(-1, 3), axis=0))
        print("  and %s-{%s}.png: the impact frame with its lines is %d colours before the grain%s"
              % (stem, ",".join(frames), colours,
                 "; the mark on %s's chin at %.2f %.2f, %.0f cm" % (others[0].name, mk["x"], mk["y"], mk["depth"]) if others else ""))
    # --rage: Saud's power-up, his rage full (0.55) and through the finisher (1)
    if "--rage" in sys.argv and saud is not None:
        mask = saud_of(got)
        for name, level in (("rage", 0.55), ("finisher", 1.0)):
            a = aura_of(saud, level=level)
            img, _ = look_from(got, exposure, aura=a, saud=mask)
            Image.fromarray(img).save("%s-%s.png" % (stem, name))
        print("  and %s-{rage,finisher}.png: Saud's aura round %d px of him, his eyes at %.3f %.3f and %.3f %.3f"
              % (stem, int(mask.sum()), a["eyes"][0][0], a["eyes"][0][1], a["eyes"][1][0], a["eyes"][1][1]))
    if "--street" in sys.argv:
        street(os.path.dirname(out), height, samples)
    if "--sky" in sys.argv:
        sky_preview(os.path.dirname(out), height, samples)


if __name__ == "__main__":
    main()
