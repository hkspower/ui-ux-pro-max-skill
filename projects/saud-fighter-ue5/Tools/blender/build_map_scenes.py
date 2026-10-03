"""
The maps in 3D: every map the game plays on as a Blender scene, and its
views through the game's look (2026-10-03, Riyadh). Asked as "make 3d view
scene for all maps", settled with the author as Blender scenes you can open
and orbit plus rendered views of them; every playable map -- the open world
whole and each of its nine districts, the prologue's gym and the monkey
island; in the game's look (the night, the dark anime, the System's style).

    python3 Tools/blender/build_map_scenes.py                    build the three scenes, check them, render every view
    python3 Tools/blender/build_map_scenes.py --build world      build one scene (world | prologue | island) and check it
    python3 Tools/blender/build_map_scenes.py --render [scene]   render the saved scenes' views (all, or one scene's;
                                                                 --view A,B for only those)
    python3 Tools/blender/build_map_scenes.py --check            the saved scenes against their plans, no render
    python3 Tools/blender/build_map_scenes.py --bite             each check broken once

WHAT IS IN THEM. Each scene is the level its own builder makes, placed from
that builder's own plan: nothing here decides where anything stands, and
nothing stands in a scene that the level does not put there.

  scenes/World.blend          L_AlHalqa_World, from Tools/levels/build_world.py's
                              plan(): the nine districts and the roads between them,
                              every primitive in its theme's colour (materials_of,
                              the editor's MI_World_<Theme>_<role>), a fire post
                              capped in embers as the editor caps it; the souq's own
                              meshes (Content/Models/Souq) on their rows; the seven
                              city districts' sector meshes (build_city.py) at their
                              districts' middles, the plots' cubes under them left out
                              as the editor hides them; the stone island's ground,
                              rocks, ruins and jetties, its 94 animals part by part
                              (build_island.animal_pieces) and the boom to the monkey
                              island at its jetty; the night -- every fire and lit
                              lantern as a light where spawn_night puts it -- under
                              WORLD_RIG's moon. Its renders: the whole ring and each
                              district.
  scenes/Prologue.blend       L_Prologue, from build_prologue.plan(): the floor, the
                              cage's seven posts, the two stands, its own sun.
  scenes/MonkeyIsland.blend   L_MonkeyIsland, from build_monkey_island_level.plan():
                              the landscape from its 16-bit heightmap, 2 m a vertex,
                              made by Geometry Nodes at load (the file stays small),
                              painted by its five 4K layers through its weightmaps
                              (the editor's M_MonkeyIsland_Ground); the sea; the
                              temple, the pier, the boat; the 9,156 plants, instanced
                              by Geometry Nodes from their plan rows; WORLD_RIG's
                              moon. Its renders: the island whole, the landing, a
                              clearing, the temple.

Every view is a camera saved in its scene (Cam_<view>), rendered by
anime_preview.render_scene and drawn through both anime materials by
anime_preview.look_from: Docs/renders/map-<view>-anime.png, and all of them
on one sheet, Docs/renders/maps-3d.png.

FRAMES. The world's scene is in the plan's own centimetres as metres, as
every Blender scene of it already is (the souq's, the city's): x and y as
the plan gives them, a yaw about +Z. The island's is in its map metres (x
east, y north), as its plan is; the level's ue() turns them into Unreal's.
Each scene's moon is WORLD_RIG's direction in that scene's frame.

THE NIGHT'S LIGHT. A fire's power is 4 pi I times the moon's own light on
the ground (build_souq's NIGHT: I is its pool's intensity), the way the
engine sizes a fire's candela against WORLD_RIG's lux -- so a fire stands to
the moon here as it does in the game. (The souq's own scene sizes its fires
against its 24-degree render moon; WORLD_RIG's is 38 degrees up.) And each
light ends where the engine ends it: spawn_night's attenuation radius,
three pools out, with the engine's window on the falloff (_engine_falloff);
Cycles' own point light never ends. The preview's exposure is the world's:
lit starts at twice the moon on open ground (anime_preview KEY_OVER_MOON,
build_world MOON_TONE), on the island too, which has no fire.

ONE PLANE, ONE TOP. The plan lays its streets in boxes that overlap the
next on one plane; an engine's depth test hides that, Cycles' shadow rays
do not, and the look cut every overlap into a dark ladder. A paving piece
is lifted a millimetre a level, the least no overlapping piece has
(paving_levels, _unshare): render-only.

THE AIR, AND HOW FAR AWAY. The look's air and its line fade are lengths for
the game's camera, which stands FIGHT_VIEW_M from what it frames: drawn as
they are from a map view hundreds of metres up, everything would be fog and
every line faded. A view whose camera stands k times as far from what it
frames as the game's does draws its air and its line fade k times as deep
(and finds the moon's ground k times as far): the picture is the game's
look at the camera's own scale. That is a choice for a map view, and only
here; the game's air is the look's.

CHECKED (--check, on the saved scenes; --bite breaks each once):
  - every piece the plan places is in its scene: per district, the
    primitives, the souq's rows, the city's sectors; the animals and their
    parts; the boat; every fire and lantern light, each ending where the
    engine ends it; the prologue's ten; the island's three props and every
    plant (instance by instance, mesh and place), its ground equal to the
    heightmap at every vertex, the sea;
  - each district's pieces lie round its middle, inside its reach, and no
    two overlapping tops share a plane;
  - every camera has its target inside the middle 80 % of its frame, and
    the first thing it sees along that line is near the target, not
    something in front of it;
  - the rendered views: the frame mostly world, not sky; ink drawn; a
    middle grey neither black nor blown; and a view of a lit district has
    its pools (somewhere on its ground a fire out-lights the moon).

UNVERIFIED, AND WHAT IS NOT THE GAME'S. These are Blender's pictures of the
levels' plans, through the look's numpy mirror; no engine has built any of
the three levels. Seen and not touched, each where the level and the scene
part: the island level's sea is an engine plane with no material of its own
and the open world's animals are engine shapes with none either (the engine
would draw both in its default material; here the sea is the world's water
colour and the animals their species colour through the world's weathering);
the stone island's last beach step tops out at its plateau's own height,
so the engine would z-fight the two over the whole plateau (here the step
is drawn 5 mm under); the prologue's posts are drawn upright, where its
Rotator(0, yaw, 0) would
stand them on their sides (CLAUDE.md, "Known, not fixed"), and its cubes in
a plain grey for the engine's default material; the stone island in the
world has no water surface (its shallows are its seabed, painted as water);
the parked cars are not here (the Unity tool that builds them has never run,
so there is no mesh to place).
"""

import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.normpath(os.path.join(HERE, "..", ".."))
LEVELS = os.path.join(PROJECT, "Tools", "levels")
SCENES = os.path.join(HERE, "scenes")
RENDERS = os.path.join(PROJECT, "Docs", "renders")
MODELS = os.path.join(PROJECT, "Content", "Models")
LAND = os.path.join(PROJECT, "Content", "Landscape", "MonkeyIsland")
GROUND_TEX = os.path.join(PROJECT, "Content", "Textures", "IslandGround")
for _p in (HERE, LEVELS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

BLENDS = dict(world="World.blend", prologue="Prologue.blend", island="MonkeyIsland.blend")
SIZE = (1600, 900)
SAMPLES = 32
SHEET = os.path.join(RENDERS, "maps-3d.png")
FIGHT_VIEW_M = 12.0          # the game's camera from what it frames (SaudCamera.h: a 5.2-11.5 m boom)
MOON_ENERGY = 1.2            # the render moon's strength, build_souq MOON's
ENGINE_SUN_ANGLE = 0.5357    # a directional light's source angle when nothing sets it (the prologue's)
ENGINE_GREY = 0.22           # the engine's default material, as one plain grey (linear)
GN_GROUND_M = 2.0            # the island's ground: a vertex every this many metres
IN_FRAME = 0.10              # a camera's target this far inside every edge of its frame
SEEN = 0.85                  # ... and the first thing along that line no nearer than this share of the way
GROUND_SHARE = 0.30          # a rendered view: at least this much of the frame is world, not sky
GREY_BAND = (0.06, 0.75)     # ... its median display value inside this
INK_SHARE = 0.003            # ... ink on at least this share of it
SABOTAGE = set()


def _bw():
    import build_world as BW
    return BW


def _now():
    return time.strftime("%H:%M:%S", time.gmtime(time.time() + 3 * 3600))      # Riyadh


# ================================================================ helpers
def _fresh():
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.length_unit = "METERS"
    return sc


def _coll(name, parent=None):
    import bpy
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    p = parent or bpy.context.scene.collection
    if c.name not in p.children:
        p.children.link(c)
    return c


def _flat(name, colour, rough, emission=None, strength=0.0, metallic=0.0):
    """A plain surface: a linear colour, a roughness (and what burns)."""
    import bpy
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    m = bpy.data.materials.new(name)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = tuple(colour[:3]) + (1.0,)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    if emission is not None:
        b.inputs["Emission Color"].default_value = tuple(emission[:3]) + (1.0,)
        b.inputs["Emission Strength"].default_value = strength
    m.diffuse_color = tuple(colour[:3]) + (1.0,)
    return m


def _segs(r_m):
    """Sides for a round shape of radius r_m: a post a dozen, a district's
    ground a hundred and more."""
    return int(max(12, min(160, 8 + r_m * 1.2)))


def _shape(bm, shape, centre_m, size_m, yaw_deg, mi):
    """One engine shape into bm: the unit Cube, Cylinder, Sphere or Cone
    (100 cm, pivot at its middle) scaled to size_m, turned by yaw_deg about
    +Z and stood at centre_m -- the way the editor's piece() places one."""
    import bmesh
    from mathutils import Matrix
    M = (Matrix.Translation(centre_m) @ Matrix.Rotation(math.radians(yaw_deg), 4, "Z")
         @ Matrix.Diagonal((size_m[0], size_m[1], size_m[2], 1.0)))
    if shape == "box":
        got = bmesh.ops.create_cube(bm, size=1.0, matrix=M)
    elif shape in ("disc", "post"):
        got = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=_segs(max(size_m[0], size_m[1]) * 0.5),
                                    radius1=0.5, radius2=0.5, depth=1.0, matrix=M)
    elif shape == "sphere":
        got = bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=8, radius=0.5, matrix=M)
    elif shape == "cone":
        got = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=12, radius1=0.5, radius2=0.0,
                                    depth=1.0, matrix=M)
    else:
        raise KeyError(shape)
    faces = {f for v in got["verts"] for f in v.link_faces}
    for f in faces:
        f.material_index = mi
        f.smooth = shape in ("sphere", "cone") or (shape in ("disc", "post") and len(f.verts) == 4)


def _mesh_object(name, bm, mats, coll):
    import bpy
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    return o


def _dedupe():
    """One material per name and one image per file: each FBX import makes
    its own copies of what the last one made (M_Souq_Flagstone.001 ...)."""
    import bpy

    def stem(name):
        return name[:-4] if len(name) > 4 and name[-4] == "." and name[-3:].isdigit() else name

    for kind, key in ((bpy.data.images, lambda i: os.path.normpath(bpy.path.abspath(i.filepath)) if i.filepath else i.name),
                      (bpy.data.materials, lambda m: stem(m.name))):
        first = {}
        for idb in sorted(kind, key=lambda i: i.name):
            k = key(idb)
            if k in first:
                idb.user_remap(first[k])
            else:
                first[k] = idb
        for idb in list(kind):
            if idb.users == 0:
                kind.remove(idb)


def _stems():
    """Each material its own name again once its copies are gone
    (M_Souq_Mud.001 -> M_Souq_Mud)."""
    import bpy
    for m in bpy.data.materials:
        n = m.name
        if len(n) > 4 and n[-4] == "." and n[-3:].isdigit() and n[:-4] not in bpy.data.materials:
            m.name = n[:-4]


def _bare_slots():
    """A slot the FBX carries no maps for takes its texture set from disk,
    as the editor's surfaces.py gives every slot that names a set its
    instance -- the world's street is one (its M_Souq_Flagstone is the
    level's flagstone, CLAUDE.md "The game is played on one seamless
    world")."""
    import bpy
    sys.path.insert(0, os.path.join(PROJECT, "Tools", "look"))
    import surfaces as SF
    sets, _ = SF.scan()
    done = []
    for m in bpy.data.materials:
        nt = m.node_tree
        if nt is None or any(n.type == "TEX_IMAGE" for n in nt.nodes) or "Principled BSDF" not in nt.nodes:
            continue
        roles = sets.get(SF.slots_of(m.name))
        if not roles or "BaseColor" not in roles:
            continue
        b = nt.nodes["Principled BSDF"]
        for role, path in roles.items():
            if role not in ("BaseColor", "Normal", "Roughness"):
                continue
            t = nt.nodes.new("ShaderNodeTexImage")
            t.image = bpy.data.images.load(path, check_existing=True)
            t.image.colorspace_settings.name = "sRGB" if role == "BaseColor" else "Non-Color"
            if role == "BaseColor":
                nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
            elif role == "Roughness":
                nt.links.new(t.outputs["Color"], b.inputs["Roughness"])
            else:
                nm = nt.nodes.new("ShaderNodeNormalMap")
                nt.links.new(t.outputs["Color"], nm.inputs["Color"])
                nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
        done.append(m.name)
    return done


def import_mesh(path):
    """An FBX's one mesh, its import transform baked in (metres, Z up) and
    the object it came on removed: the mesh to place linked copies of."""
    import bpy
    from mathutils import Matrix
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    assert len(meshes) == 1, "%s read back as %d meshes" % (os.path.basename(path), len(meshes))
    o = meshes[0]
    me = o.data
    me.transform(o.matrix_world)
    me.name = os.path.splitext(os.path.basename(path))[0]
    for x in new:
        bpy.data.objects.remove(x, do_unlink=True)
    return me


def _place(me, name, loc_m, yaw_deg, scale, coll):
    import bpy
    o = bpy.data.objects.new(name, me)
    o.location = loc_m
    o.rotation_euler = (0.0, 0.0, math.radians(yaw_deg))
    o.scale = scale
    coll.objects.link(o)
    return o


def _directx_to_blender(materials):
    """The island's maps are written DirectX (green down, Unreal's); Blender
    reads a normal map OpenGL. Each Normal Map node fed by one of them gets
    its green turned over on the way in."""
    import bpy
    n = 0
    for m in materials:
        if m is None or m.node_tree is None:
            continue
        nt = m.node_tree
        for node in list(nt.nodes):
            if node.type != "NORMAL_MAP" or not node.inputs["Color"].links:
                continue
            src = node.inputs["Color"].links[0].from_node
            if src.type != "TEX_IMAGE" or src.image is None or "Island" not in bpy.path.abspath(src.image.filepath):
                continue
            sep = nt.nodes.new("ShaderNodeSeparateColor")
            inv = nt.nodes.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0
            comb = nt.nodes.new("ShaderNodeCombineColor")
            nt.links.new(src.outputs["Color"], sep.inputs["Color"])
            nt.links.new(sep.outputs["Red"], comb.inputs["Red"])
            nt.links.new(sep.outputs["Green"], inv.inputs[1])
            nt.links.new(inv.outputs["Value"], comb.inputs["Green"])
            nt.links.new(sep.outputs["Blue"], comb.inputs["Blue"])
            nt.links.new(comb.outputs["Color"], node.inputs["Color"])
            n += 1
    return n


def _sun(name, travel, colour, energy, angle_deg, coll=None):
    """A sun lamp shining along `travel` (a direction in the scene's frame)."""
    import bpy
    from mathutils import Vector
    L = bpy.data.lights.new(name, "SUN")
    L.energy = energy
    L.color = colour
    L.angle = math.radians(angle_deg)
    o = bpy.data.objects.new(name, L)
    o.rotation_euler = (-Vector(travel).normalized()).to_track_quat("Z", "Y").to_euler()
    (coll or bpy.context.scene.collection).objects.link(o)
    return o


def _sky(colour, strength):
    import bpy
    w = bpy.data.worlds.new("Night")
    bpy.context.scene.world = w
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = tuple(colour[:3]) + (1.0,)
    bg.inputs[1].default_value = strength
    return w


def rig_travel(rig, frame="plan"):
    """The way an Unreal directional light at the rig's pitch and yaw
    shines: its forward vector, in Unreal's numbers ("plan" -- the world's
    scene uses them as they are) or in a map's (x east, y north: Unreal's
    y turned over)."""
    p, y = math.radians(rig["pitch"]), math.radians(rig["yaw"])
    v = (math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p))
    return v if frame == "plan" else (v[0], -v[1], v[2])


def moon_ground(rig):
    """The render moon's light on open ground (W/m^2): what every fire's
    power is sized against, as the engine sizes its candela against
    WORLD_RIG's lux times the sine of its elevation."""
    return MOON_ENERGY * math.sin(math.radians(-rig["pitch"]))


def attenuation_pools():
    """How far out spawn_night ends each light, in its own pools -- the
    fire's and the lantern's -- read from its source, so the scene's window
    follows the editor's numbers and cannot drift from them."""
    import inspect
    import re
    src = inspect.getsource(_bw().SOUQ.spawn_night)
    fire = re.search(r'set_attenuation_radius\(f\["pool"\] \* ([\d.]+) \* 100\.0\)', src)
    lan = re.search(r'set_attenuation_radius\(NIGHT\["lantern"\]\["pool_m"\] \* ([\d.]+) \* 100\.0\)', src)
    assert fire and lan, "spawn_night no longer says how far its lights reach"
    return float(fire.group(1)), float(lan.group(1))


def _engine_falloff(L, reach_m):
    """The engine's window on a light's inverse-square falloff over its
    attenuation radius: saturate(1 - (d / R)^4)^2, d the distance from the
    light (a light shader's Ray Length; measured against the formula on a
    plane, 2026-10-03). Cycles' own point light never ends, and summed over
    a district's fires those tails lifted the ground between the pools past
    the lit tone, where the game's lights, ended at three pools
    (spawn_night), would leave it the night's."""
    L["attenuation_m"] = reach_m
    if "no_window" in SABOTAGE:
        return
    L.use_nodes = True
    nt = L.node_tree
    em = nt.nodes["Emission"]
    lp = nt.nodes.new("ShaderNodeLightPath")
    d = nt.nodes.new("ShaderNodeMath"); d.operation = "DIVIDE"; d.inputs[1].default_value = reach_m
    p4 = nt.nodes.new("ShaderNodeMath"); p4.operation = "POWER"; p4.inputs[1].default_value = 4.0
    om = nt.nodes.new("ShaderNodeMath"); om.operation = "SUBTRACT"; om.inputs[0].default_value = 1.0; om.use_clamp = True
    sq = nt.nodes.new("ShaderNodeMath"); sq.operation = "POWER"; sq.inputs[1].default_value = 2.0
    nt.links.new(lp.outputs["Ray Length"], d.inputs[0])
    nt.links.new(d.outputs[0], p4.inputs[0])
    nt.links.new(p4.outputs[0], om.inputs[1])
    nt.links.new(om.outputs[0], sq.inputs[0])
    nt.links.new(sq.outputs[0], em.inputs["Strength"])


def _camera(name, eye, target, lens, view, air_m=None, coll=None):
    import bpy
    from mathutils import Vector
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    d = (Vector(target) - Vector(eye)).length
    cd.clip_start = max(0.1, d * 0.002)
    cd.clip_end = max(2000.0, d * 6.0)
    o = bpy.data.objects.new(name, cd)
    o.location = eye
    o.rotation_euler = (Vector(target) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
    o["target"] = tuple(target)
    o["view"] = view
    o["air_m"] = float(air_m if air_m is not None else d)
    (coll or bpy.context.scene.collection).objects.link(o)
    return o


def _fit(eye_dir, target, points, lens, margin=0.06, elev=None):
    """How far back along eye_dir (a unit vector from the target to the eye)
    a camera of this lens must stand for every point to land inside its
    16:9 frame with `margin` to spare: bisection on the projection."""
    from mathutils import Vector, Matrix
    t = Vector(target)
    back = Vector(eye_dir).normalized()
    fwd = -back
    rot = fwd.to_track_quat("-Z", "Y").to_matrix()
    th = math.atan(18.0 / lens)                       # half the horizontal field (36 mm sensor, fit to width)
    tv = math.atan(math.tan(th) * SIZE[1] / SIZE[0])
    lim_h, lim_v = math.tan(th) * (1 - 2 * margin), math.tan(tv) * (1 - 2 * margin)

    def fits(dist):
        eye = t + back * dist
        inv = rot.transposed()
        for p in points:
            q = inv @ (Vector(p) - eye)
            if q.z >= -0.01:
                return False
            if abs(q.x / -q.z) > lim_h or abs(q.y / -q.z) > lim_v:
                return False
        return True

    lo, hi = 1.0, 1.0
    while not fits(hi):
        hi *= 1.6
        if hi > 1e6:
            raise AssertionError("no distance frames these points")
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        lo, hi = (lo, mid) if fits(mid) else (mid, hi)
    return tuple(t + back * hi)


def _fit_centred(eye_dir, target, points, lens, margin=0.04):
    """As _fit, and then the frame centred on what it holds by the lens's
    shift (the camera keeps its direction): a view looking down on a ring
    sees its near side large and its far side small, so a frame aimed at
    the ring's middle leaves sky above it. Returns (eye, shift_x, shift_y),
    Blender's shift in frame widths."""
    from mathutils import Vector
    t = Vector(target)
    back = Vector(eye_dir).normalized()
    rot = (-back).to_track_quat("-Z", "Y").to_matrix()
    inv = rot.transposed()
    th = math.atan(18.0 / lens)
    tv = math.atan(math.tan(th) * SIZE[1] / SIZE[0])
    dist = (Vector(_fit(eye_dir, target, points, lens, margin)) - t).length
    sx = sy = 0.0
    for _ in range(8):
        eye = t + back * dist
        q = [inv @ (Vector(p) - eye) for p in points]
        u = [v.x / -v.z / math.tan(th) for v in q]          # -1..1 across the frame's width
        w = [v.y / -v.z / math.tan(tv) for v in q]          # -1..1 up its height
        cu, cw = 0.5 * (min(u) + max(u)), 0.5 * (min(w) + max(w))
        half = max((max(u) - min(u)) * 0.5, (max(w) - min(w)) * 0.5)
        sx, sy = cu * 0.5, cw * 0.5 * SIZE[1] / SIZE[0]
        dist *= half / (1.0 - 2.0 * margin)
    return tuple(t + back * dist), sx, sy


def _dir(az_deg, elev_deg):
    a, e = math.radians(az_deg), math.radians(elev_deg)
    return (math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e))


def _ring(x, y, r, z0=0.0, z1=0.0, n=16):
    out = []
    for k in range(n):
        a = 2 * math.pi * k / n
        for z in (z0, z1):
            out.append((x + r * math.cos(a), y + r * math.sin(a), z))
    return out


def _save_to(out, scene):
    """None: the scene's own file; False: kept in memory only (a bite)."""
    if out is False:
        return "(not saved)"
    return save(out or os.path.join(SCENES, BLENDS[scene]))


def save(path):
    import bpy
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    for b in (path + "1",):
        if os.path.exists(b):
            os.remove(b)
    return path


# ================================================================ the world
def _group_of(p, P):
    if p.get("district") is not None:
        return P["districts"][p["district"]]["stage"]["Name"]
    return "Roads"


def paving_levels(P, covered, BW):
    """A level (1, 2, ...) for every paving piece the scene draws: the least
    that no paving piece overlapping it already has, so no two overlapping
    tops share a plane. Overlap is judged by each piece's round reach (half
    its diagonal), which errs toward more levels, never fewer."""
    cell = 2000.0
    grid, out = {}, {}
    for i, p in enumerate(P["scenery"]):
        if p.get("mesh") or i in covered or BW.ROLE_OF_KIND.get(p["kind"]) != "paving":
            continue
        r = 0.5 * math.hypot(p["sx"], p["sy"])
        cx, cy = int(math.floor(p["x"] / cell)), int(math.floor(p["y"] / cell))
        taken = {lv for gx in (cx - 1, cx, cx + 1) for gy in (cy - 1, cy, cy + 1)
                 for x, y, rr, lv in grid.get((gx, gy), ()) if math.hypot(p["x"] - x, p["y"] - y) < r + rr}
        lv = next(k for k in range(1, 1000) if k not in taken)
        out[i] = lv
        grid.setdefault((cx, cy), []).append((p["x"], p["y"], r, lv))
    return out


def _unshare(i, p, role, levels):
    """Centimetres to lift a piece by so that no two overlapping tops share
    a plane. The plan lays a street in boxes each half a street's width
    longer than its step, so every box overlaps the next on the same plane
    (build_world.paving), a spur overlaps its street and a road the spur at
    its door, and a road's ground overlaps the district discs it joins; an
    engine's depth test hides that, but a ray tracer's shadow rays catch
    each overlap, and the look cut them into a dark ladder down every
    street (the first renders, 2026-10-03). A paving piece goes up a
    millimetre a level (paving_levels), a road's ground 5 mm down:
    render-only, under a pixel at any distance a view stands. And the stone
    island's last beach step tops out at the plateau's own height (both at
    0 cm, build_island.terrain), so in the engine the stone and the beach
    would z-fight over the whole plateau; here the step goes 5 mm under and
    the stone, which is what is fought on, is drawn."""
    if "shared_planes" in SABOTAGE:
        return 0.0
    if role == "paving":
        return 0.1 * levels[i]
    if role == "ground" and p.get("road"):
        return -0.5
    if p["kind"] == "beach" and abs(p["z"] + p["sz"] * 0.5 - _bw().ISL.SHORE_Z) < 0.01:
        return -0.5
    return 0.0


def world_plan():
    BW = _bw()
    stages, world = BW.load()
    P = BW.plan(stages, world)
    city = json.load(open(os.path.join(MODELS, "City", "City_placement.json"), encoding="utf-8"))
    covered = {c["row"] for c in city["plots"]}
    return BW, P, city, covered


def build_world(out=None):
    import bpy
    import bmesh
    from mathutils import Vector
    t0 = time.time()
    BW, P, city, covered = world_plan()
    sc = _fresh()
    SOUQ, ISL = BW.SOUQ, BW.ISL
    rig = BW.WORLD_RIG

    # --- the primitives: one object per district (and the roads), a slot
    #     per (theme, role) the editor makes a material instance of
    mats = {key: _flat("MI_World_%s_%s" % key, col, rough) for key, (col, rough) in BW.materials_of(P).items()}
    e = SOUQ.EMBER
    ember = _flat("M_World_Ember", e["base"], 0.6, emission=e["emission"], strength=e["strength"])
    prims = _coll("Primitives")
    groups = {}
    levels = paving_levels(P, covered, BW)
    for i, p in enumerate(P["scenery"]):
        if p.get("mesh") or i in covered:
            continue
        groups.setdefault(_group_of(p, P), []).append((i, p))
    for g, rows in sorted(groups.items()):
        pieces = [p for _, p in rows]
        keys = sorted({(BW.theme_of(p, P), BW.ROLE_OF_KIND[p["kind"]]) for p in pieces}, key=str)
        slot = {k: i for i, k in enumerate(keys)}
        used = [mats[k] for k in keys]
        if any(p.get("fire") for p in pieces):
            slot["ember"] = len(used); used.append(ember)
        bm = bmesh.new()
        embers = 0
        for i, p in rows:
            k = (BW.theme_of(p, P), BW.ROLE_OF_KIND[p["kind"]])
            _shape(bm, p["shape"], (p["x"] / 100, p["y"] / 100, (p["z"] + _unshare(i, p, k[1], levels)) / 100),
                   (p["sx"] / 100, p["sy"] / 100, p["sz"] / 100), p.get("yaw", 0.0), slot[k])
            if p.get("fire"):
                # the editor's ember bed on the post's cap
                _shape(bm, "disc", (p["x"] / 100, p["y"] / 100, (p["z"] + p["sz"] * 0.5 + 1.0) / 100),
                       (p["sx"] * 0.009, p["sy"] * 0.009, 0.02), 0.0, slot["ember"])
                embers += 1
        o = _mesh_object("Prim_%s" % g, bm, used, prims)
        o["district"] = g
        o["pieces"] = len(pieces)
        o["embers"] = embers

    # --- the souq's own meshes, on its rows
    souq = _coll("SouqAlDawar")
    kinds = {}
    for i, p in enumerate(P["scenery"]):
        if not p.get("mesh"):
            continue
        if p["mesh"] not in kinds:
            kinds[p["mesh"]] = import_mesh(os.path.join(MODELS, "Souq", p["mesh"] + ".fbx"))
        o = _place(kinds[p["mesh"]], "%s_%04d" % (p["mesh"], i), (p["x"] / 100, p["y"] / 100, p["z"] / 100),
                   p["yaw"], tuple(p["scale"]), souq)
        o["district"] = _group_of(p, P)
        o["row"] = i
    _dedupe()

    # --- the city's sector meshes, each at its district's middle
    cityc = _coll("City")
    for name, sec in sorted(city["sectors"].items()):
        d = city["districts"][sec["district"]]
        o = _place(import_mesh(os.path.join(MODELS, "City", name + ".fbx")), name,
                   (d["x"] / 100, d["y"] / 100, BW.GROUND_Z / 100), 0.0, (1, 1, 1), cityc)
        o["district"] = sec["district"]
        o["sector"] = name
    _dedupe()
    _stems()
    _bare_slots()

    # --- the stone island's animals, part by part, in their species' colour
    an_mats = {}
    for sp, A in sorted(ISL.ANIMALS.items()):
        hexc = "#%02x%02x%02x" % tuple(int(c) for c in A["col"])
        an_mats[sp] = _flat("M_Animal_%s" % sp, SOUQ._worn(hexc)[:3], 0.85)
    species = sorted(an_mats)
    bm = bmesh.new()
    parts = 0
    for an in P["animals"]:
        for part in ISL.animal_pieces(an):
            _shape(bm, part["shape"], (part["x"] / 100, part["y"] / 100, part["z"] / 100),
                   (part["sx"] / 100, part["sy"] / 100, part["sz"] / 100), part["yaw"], species.index(an["species"]))
            parts += 1
    island_c = _coll("Island")
    o = _mesh_object("Animals", bm, [an_mats[s] for s in species], island_c)
    o["animals"] = len(P["animals"])
    o["parts"] = parts
    o["district"] = next(d["stage"]["Name"] for d in P["districts"].values() if "island" in d)

    # --- the boat to the monkey island
    for a in P["actors"]:
        if a["kind"] == "Boat":
            me = import_mesh(os.path.join(MODELS, "Island", a["props"]["Mesh"] + ".fbx"))
            o = _place(me, a["name"], (a["x"] / 100, a["y"] / 100, a["z"] / 100), a["props"]["Yaw"], (1, 1, 1), island_c)
            o["boat"] = a["props"]["Mesh"]
            o["district"] = island_c.objects["Animals"]["district"]
    _directx_to_blender([m for m in bpy.data.materials if "Island" in m.name or "Wood" in m.name])

    # --- the night: every fire and lit lantern where spawn_night puts it
    night = _coll("Night")
    E_moon = moon_ground(rig)
    fire_pools, lantern_pools = attenuation_pools()
    lan = SOUQ._lin(SOUQ._hex(SOUQ.NIGHT["lantern_hex"]))[:3]
    for d in P["districts"].values():
        Q = d.get("night") or (SOUQ.night_of(d["souq"]) if "souq" in d else None)
        if Q is None:
            continue
        name = d["stage"]["Name"]
        for i, f in enumerate(Q["fires"] + Q["door_fires"]):
            L = bpy.data.lights.new("Fire_%s_%02d" % (name, i), "POINT")
            L.energy = 4.0 * math.pi * f["I"] * E_moon
            L.shadow_soft_size = 0.15
            L.use_temperature = True
            L.temperature = f["temp"]
            _engine_falloff(L, f["pool"] * fire_pools)
            o = bpy.data.objects.new(L.name, L)
            o.location = ((d["ox"] + f["x"]) / 100, (d["oy"] + f["y"]) / 100, f["z"] / 100 + f["h"])
            o["night_fire"] = 1; o["district"] = name; o["kind"] = f["kind"]
            night.objects.link(o)
        for i, l in enumerate(Q["lanterns"]):
            L = bpy.data.lights.new("Lantern_%s_%02d" % (name, i), "SPOT")
            L.energy = 4.0 * math.pi * l["I"] * E_moon
            L.color = lan
            L.spot_size = math.radians(2.0 * l["cone"]); L.spot_blend = 0.4; L.shadow_soft_size = 0.05
            _engine_falloff(L, SOUQ.NIGHT["lantern"]["pool_m"] * lantern_pools)
            o = bpy.data.objects.new(L.name, L)
            o.location = ((d["ox"] + l["x"]) / 100, (d["oy"] + l["y"]) / 100, l["z"] / 100)
            ya, pa = math.radians(l["yaw"]), math.radians(l["pitch"])
            aim = Vector((math.sin(ya) * math.cos(pa), -math.cos(ya) * math.cos(pa), math.sin(pa)))
            o.rotation_euler = aim.to_track_quat("-Z", "Y").to_euler()
            o["night_fire"] = 1; o["district"] = name; o["kind"] = "lantern"
            night.objects.link(o)

    # --- the moon and the sky over the ring
    _sun("Moon", rig_travel(rig), rig["sun"], MOON_ENERGY, rig["angle"])
    _sky(SOUQ._lin(SOUQ._hex(SOUQ.MOON["sky"])), SOUQ.MOON["sky_strength"])

    # --- the views
    world_cameras(BW, P)
    out = _save_to(out, "world")
    print("world: %s in %.0f s (%s Riyadh)" % (out, time.time() - t0, _now()))
    return out


def _reach_cm(BW, d):
    return BW.reach_of(d["stage"])


def world_cameras(BW, P):
    """The ring whole, from over the souq's side; each district from over
    its own outside edge, looking in across it toward the ring's middle."""
    import bpy
    cams = _coll("Cameras")
    lens = 35.0
    pts = []
    for d in P["districts"].values():
        R = _reach_cm(BW, d) / 100
        pts += _ring(d["ox"] / 100, d["oy"] / 100, R, 0.0, 12.0)
    eye, sx, sy = _fit_centred(_dir(100.0, 36.0), (0, 0, 0), pts, lens)
    cam = _camera("Cam_World", eye, (0, 0, 0), lens, "World", coll=cams)
    cam.data.shift_x, cam.data.shift_y = sx, sy
    for d in P["districts"].values():
        R = _reach_cm(BW, d) / 100
        x, y = d["ox"] / 100, d["oy"] / 100
        az = math.degrees(math.atan2(y, x)) if math.hypot(x, y) > 1.0 else 100.0
        tgt = (x, y, 0.0)
        eye = _fit(_dir(az, 38.0), tgt, _ring(x, y, R, 0.0, 10.0), lens, margin=0.04)
        _camera("Cam_%s" % d["stage"]["Name"], eye, tgt, lens, d["stage"]["Name"], coll=cams)


# ============================================================ the prologue
def build_prologue(out=None):
    import bpy
    import bmesh
    import build_prologue as BP
    t0 = time.time()
    _fresh()
    acts = BP.plan()
    grey = _flat("M_EngineDefault", (ENGINE_GREY,) * 3, 0.5)
    coll = _coll("L_Prologue")
    n = 0
    for a in acts:
        if a["kind"] not in ("Floor", "Wall"):
            continue
        s = a["props"]["scale"]
        bm = bmesh.new()
        # the yaw the plan means, about +Z: the level's Rotator(0, yaw, 0)
        # puts it in the pitch instead (CLAUDE.md, "Known, not fixed")
        _shape(bm, "box", (a["x"] / 100, a["y"] / 100, a["z"] / 100), (s[0], s[1], s[2]), a["props"].get("rotationYaw", 0.0), 0)
        o = _mesh_object(a["name"], bm, [grey], coll)
        o["actor"] = a["kind"]
        n += 1
    sun = next(a for a in acts if a["kind"] == "Sun")
    rig = dict(pitch=sun["props"]["pitch"], yaw=sun["props"]["yaw"])
    _sun("Sun", rig_travel(rig), sun["props"]["color"], MOON_ENERGY * sun["props"]["lux"] / _bw().WORLD_RIG["lux"],
         ENGINE_SUN_ANGLE)
    sky = next(a for a in acts if a["kind"] == "SkyLight")["props"]["intensity"]
    fog = next(a for a in acts if a["kind"] == "Fog")["props"]["color"]
    BW = _bw()
    _sky(fog, BW.SOUQ.MOON["sky_strength"] * sky / BW.WORLD_RIG["sky"])
    # the view: the cage between its stands, from over the near stand's
    # corner -- what stands on the floor framed, the floor's bare margin out
    pts = []
    for a in acts:
        if a["kind"] == "Wall":
            sx, sy, sz = (v * 50.0 for v in a["props"]["scale"])
            pts += [((a["x"] + i * sx) / 100, (a["y"] + j * sy) / 100, (a["z"] + k * sz) / 100)
                    for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)]
    tgt = (BP.CAGE_CENTRE[0] / 100, 0.0, 0.0)
    eye = _fit(_dir(-62.0, 34.0), tgt, pts, 30.0, margin=0.05)
    _camera("Cam_Prologue", eye, tgt, 30.0, "Prologue", coll=_coll("Cameras"))
    out = _save_to(out, "prologue")
    print("prologue: %s, %d pieces, %.0f s (%s Riyadh)" % (out, n, time.time() - t0, _now()))
    return out


# ======================================================= the monkey island
def island_plan():
    import build_monkey_island_level as BML
    return BML, BML.plan()


def _ground_nodes(img, mat, n, half):
    """Geometry Nodes: a grid GN_GROUND_M apart over the heightmap's square,
    each vertex raised to the heightmap's own height there (16-bit,
    (v - 32768) / 128 m, row 0 the north, Non-Color, linear), smooth, the
    tiling UV stored for the ground's maps, the ground's material."""
    import bpy
    ng = bpy.data.node_groups.new("MonkeyIslandGround", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N = ng.nodes
    L = ng.links
    span = 2.0 * half
    verts = int(round(span / GN_GROUND_M)) + 1
    grid = N.new("GeometryNodeMeshGrid")
    grid.inputs["Size X"].default_value = span
    grid.inputs["Size Y"].default_value = span
    grid.inputs["Vertices X"].default_value = verts
    grid.inputs["Vertices Y"].default_value = verts
    pos = N.new("GeometryNodeInputPosition")
    # texel centres: map x = -half + c (1 m a texel) sits at u = (x + half + 0.5) / n
    uv = N.new("ShaderNodeVectorMath"); uv.operation = "MULTIPLY_ADD"
    uv.inputs[1].default_value = (1.0 / n, 1.0 / n, 0.0)
    uv.inputs[2].default_value = ((half + 0.5) / n, (half + 0.5) / n, 0.0)
    L.new(pos.outputs["Position"], uv.inputs[0])
    tex = N.new("GeometryNodeImageTexture")
    tex.inputs["Image"].default_value = img
    tex.interpolation = "Linear"
    tex.extension = "EXTEND"
    L.new(uv.outputs["Vector"], tex.inputs["Vector"])
    z = N.new("ShaderNodeMath"); z.operation = "MULTIPLY_ADD"
    k = 128.0 if "height_scale" not in SABOTAGE else 127.0
    z.inputs[1].default_value = 65535.0 / k
    z.inputs[2].default_value = -32768.0 / k
    sep_c = N.new("FunctionNodeSeparateColor") if "FunctionNodeSeparateColor" in dir(bpy.types) else None
    if sep_c is not None:
        L.new(tex.outputs["Color"], sep_c.inputs["Color"])
        L.new(sep_c.outputs["Red"], z.inputs[0])
    else:
        L.new(tex.outputs["Color"], z.inputs[0])
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(pos.outputs["Position"], sep.inputs["Vector"])
    comb = N.new("ShaderNodeCombineXYZ")
    L.new(sep.outputs["X"], comb.inputs["X"])
    L.new(sep.outputs["Y"], comb.inputs["Y"])
    L.new(z.outputs["Value"], comb.inputs["Z"])
    setp = N.new("GeometryNodeSetPosition")
    L.new(grid.outputs["Mesh"], setp.inputs["Geometry"])
    L.new(comb.outputs["Vector"], setp.inputs["Position"])
    smooth = N.new("GeometryNodeSetShadeSmooth")
    L.new(setp.outputs["Geometry"], smooth.inputs["Mesh"])
    # the ground maps' UV: a tile every TILE_M (island_surfaces), as a UV map
    tile = N.new("ShaderNodeVectorMath"); tile.operation = "SCALE"
    L.new(pos.outputs["Position"], tile.inputs[0])
    tile.inputs["Scale"].default_value = 1.0 / _tile_m()
    store = N.new("GeometryNodeStoreNamedAttribute")
    store.data_type = "FLOAT2"
    store.domain = "CORNER"
    store.inputs["Name"].default_value = "UVMap"
    L.new(smooth.outputs["Mesh"], store.inputs["Geometry"])
    L.new(tile.outputs["Vector"], store.inputs["Value"])
    setm = N.new("GeometryNodeSetMaterial")
    setm.inputs["Material"].default_value = mat
    L.new(store.outputs["Geometry"], setm.inputs["Geometry"])
    out = N.new("NodeGroupOutput")
    L.new(setm.outputs["Geometry"], out.inputs[0])
    return ng


def _tile_m():
    import island_surfaces as IS
    return IS.TILE_M


def _ground_material(n, half, layers):
    """M_MonkeyIsland_Ground as the editor builds it: each layer's
    BaseColor, Normal and Roughness at a tile every TILE_M, blended by the
    layers' weightmaps, normalised -- the landscape's weight blend."""
    import bpy
    m = bpy.data.materials.new("M_MonkeyIsland_Ground")
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    bsdf = N["Principled BSDF"]
    tc = N.new("ShaderNodeTexCoord")
    wuv = N.new("ShaderNodeVectorMath"); wuv.operation = "MULTIPLY_ADD"
    wuv.inputs[1].default_value = (1.0 / n, 1.0 / n, 0.0)
    wuv.inputs[2].default_value = ((half + 0.5) / n, (half + 0.5) / n, 0.0)
    L.new(tc.outputs["Object"], wuv.inputs[0])
    uvm = N.new("ShaderNodeUVMap"); uvm.uv_map = "UVMap"

    def img(path, colour):
        t = N.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(path, check_existing=True)
        t.image.colorspace_settings.name = "sRGB" if colour else "Non-Color"
        t.interpolation = "Linear"
        return t

    acc = {}
    wsum = None
    for layer in layers:
        w = img(os.path.join(LAND, "W_MonkeyIsland_%s.png" % layer), False)
        w.extension = "EXTEND"
        L.new(wuv.outputs["Vector"], w.inputs["Vector"])
        wv = w.outputs["Color"]
        if wsum is None:
            wsum = wv
        else:
            s = N.new("ShaderNodeMath"); s.operation = "ADD"
            L.new(wsum, s.inputs[0]); L.new(wv, s.inputs[1]); wsum = s.outputs["Value"]
        for role in ("BaseColor", "Normal", "Roughness"):
            t = img(os.path.join(GROUND_TEX, "T_IslandGround_%s_%s.png" % (layer, role)), role == "BaseColor")
            L.new(uvm.outputs["UV"], t.inputs["Vector"])
            col = t.outputs["Color"]
            if role == "Normal":
                # DirectX (green down) to Blender's OpenGL
                sep = N.new("ShaderNodeSeparateColor"); inv = N.new("ShaderNodeMath"); inv.operation = "SUBTRACT"
                inv.inputs[0].default_value = 1.0; comb = N.new("ShaderNodeCombineColor")
                L.new(col, sep.inputs["Color"]); L.new(sep.outputs["Red"], comb.inputs["Red"])
                L.new(sep.outputs["Green"], inv.inputs[1]); L.new(inv.outputs["Value"], comb.inputs["Green"])
                L.new(sep.outputs["Blue"], comb.inputs["Blue"]); col = comb.outputs["Color"]
            mul = N.new("ShaderNodeVectorMath"); mul.operation = "SCALE"
            L.new(col, mul.inputs[0]); L.new(wv, mul.inputs["Scale"])
            if role in acc:
                add = N.new("ShaderNodeVectorMath"); add.operation = "ADD"
                L.new(acc[role], add.inputs[0]); L.new(mul.outputs["Vector"], add.inputs[1]); acc[role] = add.outputs["Vector"]
            else:
                acc[role] = mul.outputs["Vector"]
    inv_sum = N.new("ShaderNodeMath"); inv_sum.operation = "DIVIDE"; inv_sum.inputs[0].default_value = 1.0
    eps = N.new("ShaderNodeMath"); eps.operation = "MAXIMUM"; eps.inputs[1].default_value = 1e-3
    L.new(wsum, eps.inputs[0]); L.new(eps.outputs["Value"], inv_sum.inputs[1])
    out = {}
    for role, v in acc.items():
        s = N.new("ShaderNodeVectorMath"); s.operation = "SCALE"
        L.new(v, s.inputs[0]); L.new(inv_sum.outputs["Value"], s.inputs["Scale"]); out[role] = s.outputs["Vector"]
    L.new(out["BaseColor"], bsdf.inputs["Base Color"])
    r = N.new("ShaderNodeSeparateXYZ"); L.new(out["Roughness"], r.inputs["Vector"]); L.new(r.outputs["X"], bsdf.inputs["Roughness"])
    nm = N.new("ShaderNodeNormalMap"); nm.uv_map = "UVMap"
    L.new(out["Normal"], nm.inputs["Color"]); L.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return m


FOLIAGE_KINDS = ("SM_Island_Palm_A", "SM_Island_Palm_B", "SM_Island_Palm_C", "SM_Island_Rock_A", "SM_Island_Rock_B",
                 "SM_Island_Rock_C", "SM_Island_Tree_A", "SM_Island_Tree_B")


def _foliage_nodes(kinds_coll):
    """Geometry Nodes: an instance of each plan row's own mesh on its point,
    turned by its yaw, at its scale -- the kinds picked by their index in
    the collection's children (alphabetical, as Collection Info lists them)."""
    import bpy
    ng = bpy.data.node_groups.new("MonkeyIslandFoliage", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    gin = N.new("NodeGroupInput")
    ci = N.new("GeometryNodeCollectionInfo")
    ci.inputs["Collection"].default_value = kinds_coll
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True
    iop = N.new("GeometryNodeInstanceOnPoints")
    iop.inputs["Pick Instance"].default_value = True

    def attr(name, kind):
        a = N.new("GeometryNodeInputNamedAttribute"); a.data_type = kind; a.inputs["Name"].default_value = name
        return a.outputs["Attribute"]

    L.new(gin.outputs[0], iop.inputs["Points"])
    L.new(ci.outputs["Instances"], iop.inputs["Instance"])
    L.new(attr("kind", "INT"), iop.inputs["Instance Index"])
    yaw = N.new("ShaderNodeCombineXYZ")
    L.new(attr("yaw", "FLOAT"), yaw.inputs["Z"])
    e2r = N.new("FunctionNodeEulerToRotation")
    L.new(yaw.outputs["Vector"], e2r.inputs["Euler"])
    L.new(e2r.outputs["Rotation"], iop.inputs["Rotation"])
    L.new(attr("scale", "FLOAT"), iop.inputs["Scale"])
    gout = N.new("NodeGroupOutput")
    L.new(iop.outputs["Instances"], gout.inputs[0])
    return ng


def build_island(out=None):
    import bpy
    import numpy as np
    t0 = time.time()
    BML, P = island_plan()
    M = BML.M
    gp = P["ground"]
    _fresh()
    n, half = int(gp["vertices"]), float(gp["half_m"])
    # --- the ground
    img = bpy.data.images.load(os.path.join(LAND, "H_MonkeyIsland.png"), check_existing=True)
    img.colorspace_settings.name = "Non-Color"
    mat = _ground_material(n, half, M.LAYERS)
    me = bpy.data.meshes.new("Landscape")
    land = bpy.data.objects.new("Landscape", me)
    _coll("Ground").objects.link(land)
    mod = land.modifiers.new("Heightmap", "NODES")
    mod.node_group = _ground_nodes(img, mat, n, half)
    land["vertices"] = n
    land["half_m"] = half
    # --- the sea: the level's plane, 4600 m square at sea level
    BW = _bw()
    sea_mat = _flat("M_Sea", BW.role_colour(None, "water"), BW.ROLE_ROUGH["water"])
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=2300.0)
    for f in bm.faces:
        f.material_index = 0
    sea = _mesh_object("Sea", bm, [sea_mat], _coll("Sea"))
    sea.location = (0.0, 0.0, gp["sea_level_m"])
    sea["sea"] = 1
    # --- the props
    props = _coll("Props")
    for a in P["actors"]:
        if a["kind"] != "Prop":
            continue
        me = import_mesh(os.path.join(MODELS, "Island", a["mesh"] + ".fbx"))
        o = _place(me, a["name"], (a["x"], a["y"], a["z"]), a["bearing"], (1, 1, 1), props)
        o["prop"] = a["mesh"]
    # --- the plants: their kinds, hidden, and a point per plan row
    kinds = _coll("FoliageKinds")
    for name in FOLIAGE_KINDS:
        me = import_mesh(os.path.join(MODELS, "Island", name + ".fbx"))
        o = bpy.data.objects.new(name, me)
        kinds.objects.link(o)
    _dedupe()
    _stems()
    _directx_to_blender(list(bpy.data.materials))
    rows = P["foliage"]
    if "lost_plants" in SABOTAGE:
        rows = rows[:-25]
    pts = bpy.data.meshes.new("FoliagePoints")
    pts.vertices.add(len(rows))
    pts.vertices.foreach_set("co", np.array([(f["x"], f["y"], f["z"]) for f in rows], np.float32).ravel())
    order = sorted(FOLIAGE_KINDS)
    for name, kind, vals in (("kind", "INT", [order.index(f["mesh"]) for f in rows]),
                             ("yaw", "FLOAT", [math.radians(f["yaw"]) for f in rows]),
                             ("scale", "FLOAT", [f["scale"] for f in rows])):
        at = pts.attributes.new(name, kind, "POINT")
        at.data.foreach_set("value", np.array(vals, np.int32 if kind == "INT" else np.float32))
    fol = bpy.data.objects.new("Foliage", pts)
    _coll("Foliage").objects.link(fol)
    fm = fol.modifiers.new("Plants", "NODES")
    fm.node_group = _foliage_nodes(kinds)
    fol["plants"] = len(P["foliage"])
    # the kinds are drawn only as instances
    vl = bpy.context.view_layer
    vl.layer_collection.children["FoliageKinds"].exclude = True
    # --- the moon over the island, in its map frame
    _sun("Moon", rig_travel(BW.WORLD_RIG, frame="map"), BW.WORLD_RIG["sun"], MOON_ENERGY, BW.WORLD_RIG["angle"])
    _sky(BW.SOUQ._lin(BW.SOUQ._hex(BW.SOUQ.MOON["sky"])), BW.SOUQ.MOON["sky_strength"])
    island_cameras(P, M)
    out = _save_to(out, "island")
    print("island: %s, %d plants, %.0f s (%s Riyadh)" % (out, len(rows), time.time() - t0, _now()))
    return out


def island_cameras(P, M):
    """The island whole, from the south-west over the sea; the landing, from
    off the pier's end; the third clearing, from the trail coming up to it;
    the temple, from the trail's arrival at its gate."""
    import numpy as np
    cams = _coll("Cameras")
    gp = P["ground"]
    # from over the sea off the west-north-west, 18 degrees up, the moon on
    # the island's far side: of the framings tried (eleven, 2026-10-03) the
    # one where most of it reads -- at night its jungle is the deep tone
    # from any side, and only its bare ground and its coast catch the moon
    R = M.COAST_R_M + M.COAST_WARP_M
    eye = _fit(_dir(160.0, 18.0), (0, 0, 0), _ring(0, 0, R * 0.92, 0.0, 120.0), 30.0, margin=0.02)
    _camera("Cam_MonkeyIsland", eye, (0, 0, 0), 30.0, "MonkeyIsland", coll=cams)
    pr = P["pier"]
    ux, uy = pr["u"]
    mid = (pr["x"] + ux * pr["length"] * 0.45, pr["y"] + uy * pr["length"] * 0.45)
    eye = (pr["x"] + ux * (pr["length"] + 55.0) - uy * 45.0, pr["y"] + uy * (pr["length"] + 55.0) + ux * 45.0, 28.0)
    _camera("Cam_MonkeyIsland_Landing", eye, (mid[0] - ux * 30.0, mid[1] - uy * 30.0, pr["deck"] + 4.0), 30.0, "MonkeyIsland-Landing", coll=cams)
    s = P["ground"]["sites"][2]
    tr = P["trail"]
    d = np.hypot(tr[:, 0] - s["x"], tr[:, 1] - s["y"])
    k = int(np.argmin(d))
    j = k
    while j > 0 and math.hypot(tr[j, 0] - s["x"], tr[j, 1] - s["y"]) < 45.0:
        j -= 1
    BML = sys.modules["build_monkey_island_level"]
    ex, ey = float(tr[j, 0]), float(tr[j, 1])
    ez = BML.at(P["h"], ex, ey) + 22.0
    _camera("Cam_MonkeyIsland_Clearing", (ex, ey, ez), (s["x"], s["y"], s["z"] + 1.0), 26.0, "MonkeyIsland-Clearing", coll=cams)
    ar = P["ground"]["arena"]
    tem = next(a for a in P["actors"] if a.get("mesh") == "SM_Island_Temple")
    gb = math.radians(tem["gate_bearing"])
    dist = ar["r"] + 48.0
    ex, ey = ar["x"] + math.cos(gb) * dist + math.sin(gb) * 18.0, ar["y"] + math.sin(gb) * dist - math.cos(gb) * 18.0
    ez = max(BML.at(P["h"], ex, ey), ar["z"]) + 26.0
    _camera("Cam_MonkeyIsland_Temple", (ex, ey, ez), (ar["x"], ar["y"], ar["z"] + 3.0), 28.0, "MonkeyIsland-Temple", coll=cams)


# ================================================================== checks
def _open(scene):
    import bpy
    path = os.path.join(SCENES, BLENDS[scene])
    assert os.path.exists(path), "%s is not built" % path
    bpy.ops.wm.open_mainfile(filepath=path)
    return path


def check_cameras(miss):
    """Every camera's target inside its frame, and seen: the first surface
    along the line to it no nearer than SEEN of the way."""
    import bpy
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    cams = [o for o in bpy.data.objects if o.type == "CAMERA" and "target" in o]
    if not cams:
        miss.append("the scene has no views")
    for cam in cams:
        sc.render.resolution_x, sc.render.resolution_y = SIZE
        t = Vector(cam["target"])
        p = world_to_camera_view(sc, cam, t)
        if not (IN_FRAME <= p.x <= 1 - IN_FRAME and IN_FRAME <= p.y <= 1 - IN_FRAME and p.z > 0):
            miss.append("%s: its target is not in its frame (%.2f, %.2f, %.0f m)" % (cam.name, p.x, p.y, p.z))
            continue
        o = cam.matrix_world.translation
        v = t - o
        hit, loc, *_ = sc.ray_cast(dg, o, v.normalized(), distance=v.length * 1.5)
        if hit and (loc - o).length < SEEN * v.length:
            miss.append("%s: its target is behind something %.0f m short of it (%.0f m away)"
                        % (cam.name, v.length - (loc - o).length, v.length))
    return miss


def _bbox_xy(o):
    from mathutils import Vector
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return min(p.x for p in pts), min(p.y for p in pts), max(p.x for p in pts), max(p.y for p in pts)


def _apart(a, b, tol=0.001):
    """Two convex polygons (lists of (x, y)) apart in plan, by more than
    tol metres along some edge's normal of either (separating axes)."""
    for poly in (a, b):
        n = len(poly)
        for k in range(n):
            (x0, y0), (x1, y1) = poly[k], poly[(k + 1) % n]
            nx, ny = y0 - y1, x1 - x0
            ln = math.hypot(nx, ny)
            if ln < 1e-9:
                continue
            nx, ny = nx / ln, ny / ln
            pa = [x * nx + y * ny for x, y in a]
            pb = [x * nx + y * ny for x, y in b]
            if min(pa) > max(pb) - tol or min(pb) > max(pa) - tol:
                return True
    return False


def shared_planes(objs):
    """Pairs of upward faces, in the scene's primitives, that overlap in
    plan on one plane: what a ray tracer's shadow rays catch (_unshare)."""
    import bpy
    pairs = 0
    tops = {}
    for o in objs:
        me = o.data
        M = o.matrix_world
        for f in me.polygons:
            if f.normal.z < 0.999:
                continue
            vs = [M @ me.vertices[v].co for v in f.vertices]
            z = round(sum(v.z for v in vs) / len(vs), 4)
            poly = [(v.x, v.y) for v in vs]
            box = (min(x for x, _ in poly), min(y for _, y in poly), max(x for x, _ in poly), max(y for _, y in poly))
            tops.setdefault(z, []).append((box, poly))
    for z, faces in tops.items():
        faces.sort(key=lambda t: t[0][0])
        for a in range(len(faces)):
            ba, pa = faces[a]
            for b in range(a + 1, len(faces)):
                bb, pb = faces[b]
                if bb[0] >= ba[2] - 0.001:
                    break
                if bb[1] >= ba[3] - 0.001 or ba[1] >= bb[3] - 0.001:
                    continue
                if not _apart(pa, pb):
                    pairs += 1
    return pairs


def check_world(miss=None):
    import bpy
    miss = [] if miss is None else miss
    bpy.context.view_layer.update()        # every object's matrix as it stands now, not as last evaluated
    BW, P, city, covered = world_plan()
    objs = list(bpy.data.objects)
    # the primitives, district by district
    want = {}
    for i, p in enumerate(P["scenery"]):
        if not p.get("mesh") and i not in covered:
            g = _group_of(p, P)
            want[g] = want.get(g, 0) + 1
    got = {o["district"]: o["pieces"] for o in objs if "pieces" in o}
    for g, n in sorted(want.items()):
        if got.get(g) != n:
            miss.append("%s: %s primitives in the scene, the plan has %d" % (g, got.get(g), n))
    fires = {}
    for i, p in enumerate(P["scenery"]):
        if p.get("fire") and i not in covered:
            fires[_group_of(p, P)] = fires.get(_group_of(p, P), 0) + 1
    for o in objs:
        if "pieces" in o and o.get("embers", 0) != fires.get(o["district"], 0):
            miss.append("%s: %s ember beds, %d fire posts" % (o["district"], o.get("embers"), fires.get(o["district"], 0)))
    # the souq's rows
    rows = sorted(i for i, p in enumerate(P["scenery"]) if p.get("mesh"))
    have = sorted(o["row"] for o in objs if "row" in o)
    if have != rows:
        miss.append("the souq: %d of its %d rows placed" % (len(set(have) & set(rows)), len(rows)))
    for o in objs:
        if "row" in o:
            p = P["scenery"][o["row"]]
            if (o.location.x - p["x"] / 100) ** 2 + (o.location.y - p["y"] / 100) ** 2 > 0.01 ** 2 or o.data.name != p["mesh"]:
                miss.append("the souq: row %d is not its plan's %s where the plan puts it" % (o["row"], p["mesh"]))
                break
    # the city's sectors
    secs = sorted(o["sector"] for o in objs if "sector" in o)
    if secs != sorted(city["sectors"]):
        miss.append("the city: %d of its %d sector meshes" % (len(secs), len(city["sectors"])))
    # the animals and the boat
    an = next((o for o in objs if "animals" in o), None)
    parts = sum(len(BW.ISL.animal_pieces(a)) for a in P["animals"])
    if an is None or an["animals"] != len(P["animals"]) or an["parts"] != parts:
        miss.append("the stone island's animals: %s, the plan has %d (%d parts)"
                    % (None if an is None else "%d (%d parts)" % (an["animals"], an["parts"]), len(P["animals"]), parts))
    boats = [a for a in P["actors"] if a["kind"] == "Boat"]
    boat_objs = [o for o in objs if "boat" in o]
    if len(boat_objs) != len(boats):
        miss.append("the boat: %d in the scene, %d in the plan" % (len(boat_objs), len(boats)))
    # the night
    for d in P["districts"].values():
        Q = d.get("night") or (BW.SOUQ.night_of(d["souq"]) if "souq" in d else None)
        n = 0 if Q is None else len(Q["fires"]) + len(Q["door_fires"]) + len(Q["lanterns"])
        lit = sum(1 for o in objs if o.type == "LIGHT" and o.get("night_fire") and o.get("district") == d["stage"]["Name"])
        if lit != n:
            miss.append("%s: %d night lights in the scene, the plan has %d" % (d["stage"]["Name"], lit, n))
    # every night light ends where spawn_night ends it, with the engine's window
    fire_pools, lantern_pools = attenuation_pools()
    reach = {}
    for d in P["districts"].values():
        Q = d.get("night") or (BW.SOUQ.night_of(d["souq"]) if "souq" in d else None)
        for i, f in enumerate([] if Q is None else Q["fires"] + Q["door_fires"]):
            reach["Fire_%s_%02d" % (d["stage"]["Name"], i)] = f["pool"] * fire_pools
        for i, l in enumerate([] if Q is None else Q["lanterns"]):
            reach["Lantern_%s_%02d" % (d["stage"]["Name"], i)] = BW.SOUQ.NIGHT["lantern"]["pool_m"] * lantern_pools
    wrong = [o.name for o in objs if o.type == "LIGHT" and o.get("night_fire") and
             (abs(o.data.get("attenuation_m", -1.0) - reach.get(o.name, -2.0)) > 1e-6 or o.data.node_tree is None or
              not any(n.type == "LIGHT_PATH" and n.outputs["Ray Length"].links for n in o.data.node_tree.nodes))]
    if wrong:
        miss.append("the night: %d lights without the engine's end (%s ...)" % (len(wrong), wrong[0]))
    # every district's pieces round its middle, inside its reach
    for d in P["districts"].values():
        name = d["stage"]["Name"]
        mine = [o for o in objs if o.get("district") == name and o.type == "MESH"]
        if not mine:
            miss.append("%s: nothing of it is in the scene" % name)
            continue
        R = BW.reach_of(d["stage"]) / 100 + 1.0
        x0 = min(_bbox_xy(o)[0] for o in mine); y0 = min(_bbox_xy(o)[1] for o in mine)
        x1 = max(_bbox_xy(o)[2] for o in mine); y1 = max(_bbox_xy(o)[3] for o in mine)
        ox, oy = d["ox"] / 100, d["oy"] / 100
        if not (x0 <= ox <= x1 and y0 <= oy <= y1):
            miss.append("%s: its pieces do not lie round its middle" % name)
        if max(abs(x0 - ox), abs(x1 - ox), abs(y0 - oy), abs(y1 - oy)) > R + (BW.BOAT["jetty_out"] / 100 + 10 if "island" in d else 0):
            miss.append("%s: its pieces reach past its reach (%.0f m)" % (name, R))
    # no two overlapping tops on one plane (_unshare)
    n = shared_planes([o for o in objs if "pieces" in o])
    if n:
        miss.append("the primitives: %d pairs of overlapping tops share a plane" % n)
    # the moon
    if not any(o.type == "LIGHT" and o.data.type == "SUN" for o in objs):
        miss.append("the world has no moon")
    return check_cameras(miss)


def check_prologue(miss=None):
    import bpy
    import build_prologue as BP
    miss = [] if miss is None else miss
    bpy.context.view_layer.update()        # every object's matrix as it stands now, not as last evaluated
    acts = [a for a in BP.plan() if a["kind"] in ("Floor", "Wall")]
    objs = {o.name: o for o in bpy.data.objects if "actor" in o}
    if sorted(objs) != sorted(a["name"] for a in acts):
        miss.append("the prologue: %s in the scene, the plan has %s" % (sorted(objs), sorted(a["name"] for a in acts)))
    for a in acts:
        o = objs.get(a["name"])
        if o is None:
            continue
        c = sum((o.matrix_world @ v.co for v in o.data.vertices), o.location * 0) / len(o.data.vertices)
        if (c.x - a["x"] / 100) ** 2 + (c.y - a["y"] / 100) ** 2 + (c.z - a["z"] / 100) ** 2 > 0.01 ** 2:
            miss.append("the prologue: %s is not where the plan puts it" % a["name"])
    if not any(o.type == "LIGHT" and o.data.type == "SUN" for o in bpy.data.objects):
        miss.append("the prologue has no sun")
    return check_cameras(miss)


def check_island(miss=None):
    import bpy
    import numpy as np
    miss = [] if miss is None else miss
    bpy.context.view_layer.update()        # every object's matrix as it stands now, not as last evaluated
    BML, P = island_plan()
    dg = bpy.context.evaluated_depsgraph_get()
    land = bpy.data.objects.get("Landscape")
    if land is None:
        miss.append("the island has no ground")
    else:
        me = land.evaluated_get(dg).data
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        h = P["h"]
        n, half = h.shape[0], float(P["ground"]["half_m"])
        c = np.rint(co[:, 0] + half).astype(int)
        r = np.rint(half - co[:, 1]).astype(int)
        inside = (c >= 0) & (c < n) & (r >= 0) & (r < n)
        if not inside.all() or len(co) < (n // int(GN_GROUND_M)) ** 2:
            miss.append("the island's ground does not cover its heightmap (%d vertices)" % len(co))
        else:
            err = np.abs(co[:, 2] - h[r, c])
            if err.max() > 0.02:
                miss.append("the island's ground is not its heightmap: %.2f m off at worst" % err.max())
    sea = bpy.data.objects.get("Sea")
    if sea is None or abs(sea.location.z - P["ground"]["sea_level_m"]) > 1e-3:
        miss.append("the island's sea is not at sea level")
    for a in P["actors"]:
        if a["kind"] != "Prop":
            continue
        o = bpy.data.objects.get(a["name"])
        if o is None or (o.location - type(o.location)((a["x"], a["y"], a["z"]))).length > 0.01 or \
                abs(math.degrees(o.rotation_euler.z) - a["bearing"]) % 360.0 > 0.01 and \
                abs(abs(math.degrees(o.rotation_euler.z) - a["bearing"]) % 360.0 - 360.0) > 0.01:
            miss.append("the island: %s is not where the plan puts it" % a["name"])
    # every plant: its mesh, where its row puts it
    fol = bpy.data.objects.get("Foliage")
    got = {}
    for inst in dg.object_instances:
        if inst.is_instance and inst.parent is not None and inst.parent.original == fol:
            t = inst.matrix_world.translation
            got.setdefault(inst.object.original.data.name, []).append((t.x, t.y, t.z))
    want = {}
    for f in P["foliage"]:
        want.setdefault(f["mesh"], []).append((f["x"], f["y"], f["z"]))
    for mesh in sorted(set(got) | set(want)):
        a, b = np.array(sorted(got.get(mesh, [])), float), np.array(sorted(want.get(mesh, [])), float)
        if a.shape != b.shape:
            miss.append("the island's plants: %d %s in the scene, %d in the plan" % (len(a), mesh, len(b)))
        elif len(a) and np.abs(a - b).max() > 0.01:
            miss.append("the island's plants: a %s %.2f m from where its row puts it" % (mesh, np.abs(a - b).max()))
    return check_cameras(miss)


CHECKS = dict(world=check_world, prologue=check_prologue, island=check_island)


def check(scenes=("world", "prologue", "island")):
    miss = []
    for s in scenes:
        _open(s)
        got = CHECKS[s]([])
        print("%s: %s" % (s, "ok" if not got else "%d misses" % len(got)))
        miss += got
    for m in miss:
        print("  MISS " + m)
    return miss


# ================================================================== render
def views(scene):
    import bpy
    return sorted((o for o in bpy.data.objects if o.type == "CAMERA" and "view" in o), key=lambda o: o.name)


class _air:
    """The look's air, its line fade and the moon's ground drawn k times as
    deep, for a view k times as far from what it frames as the game's
    camera stands (see THE AIR in the docstring)."""
    def __init__(self, k):
        self.k = max(1.0, k)

    def __enter__(self):
        import anime_preview as AP
        L = AP.AL.LOOK
        self.was = AP.GROUND_WITHIN_CM
        AP.GROUND_WITHIN_CM = self.was * self.k
        self.over = AP._look_over(HAZE_NEAR_CM=L["HAZE_NEAR_CM"] * self.k, HAZE_FAR_CM=L["HAZE_FAR_CM"] * self.k,
                                  FADE_NEAR_CM=L["FADE_NEAR_CM"] * self.k, FADE_FAR_CM=L["FADE_FAR_CM"] * self.k)
        self.over.__enter__()

    def __exit__(self, *a):
        import anime_preview as AP
        self.over.__exit__(*a)
        AP.GROUND_WITHIN_CM = self.was


def render_view(cam, size=SIZE, samples=SAMPLES, groups=True):
    """One view through the look: (8-bit picture, the look's masks, the
    passes, the exposure). The masks carry the view's air scale, "air"."""
    import anime_preview as AP
    k = max(1.0, cam["air_m"] / FIGHT_VIEW_M)
    with _air(k):
        got, exposure = AP.render_scene(camera=cam, size=size, samples=samples, groups=groups)
        pic, m = AP.look_from(got, exposure)
    m["air"] = k
    return pic, m, got, exposure


def picture_misses(name, pic, m, got, exposure, lit):
    """A rendered view: mostly world, ink drawn, a middle grey neither black
    nor blown; a lit district's pools (a fire out-lighting the moon)."""
    import numpy as np
    import anime_preview as AP
    out = []
    D = got["Depth"][..., 0]
    world = D < 1e8
    share = float(world.mean())
    if share < GROUND_SHARE:
        out.append("%s: %.0f %% of the frame is world, want %.0f %%" % (name, share * 100, GROUND_SHARE * 100))
    v = pic.astype(float).mean(-1) / 255.0
    med = float(np.median(v[world])) if world.any() else 0.0
    if not GREY_BAND[0] <= med <= GREY_BAND[1]:
        out.append("%s: its middle grey is %.2f, want %.2f-%.2f" % (name, med, GREY_BAND[0], GREY_BAND[1]))
    ink = float((m["ink"] >= 0.5).mean())
    if ink < INK_SHARE:
        out.append("%s: ink on %.2f %% of it, want %.1f %%" % (name, ink * 100, INK_SHARE * 100))
    if lit:
        with _air(m.get("air", 1.0)):
            g = AP.ground_of(got)
        if "Combined_fire" not in got or not g.any():
            out.append("%s: no fire light to measure" % name)
        else:
            luma = np.array(AP.AL.LUMA)
            fire = got["Combined_fire"][..., :3] @ luma
            moon = got["Combined_moon"][..., :3] @ luma
            pools = float(((fire > moon) & g).mean() / max(g.mean(), 1e-9))
            if pools <= 0.0:
                out.append("%s: no pool of firelight on its ground" % name)
    return out


def _lit(scene, cam):
    """Whether a view looks at a district whose night has fires."""
    import bpy
    if scene != "world":
        return False
    v = cam["view"]
    return any(o.type == "LIGHT" and o.get("night_fire") and (v == "World" or o.get("district") == v) for o in bpy.data.objects)


def render(scenes=("world", "prologue", "island"), size=SIZE, samples=SAMPLES, only=None):
    from PIL import Image
    os.makedirs(RENDERS, exist_ok=True)
    miss, made = [], []
    for s in scenes:
        _open(s)
        for cam in views(s):
            if only and cam["view"] not in only:
                continue
            t0 = time.time()
            pic, m, got, exposure = render_view(cam, size, samples, groups=s != "prologue")
            out = os.path.join(RENDERS, "map-%s-anime.png" % cam["view"])
            Image.fromarray(pic).save(out, optimize=True)
            made.append(out)
            bad = picture_misses(cam["view"], pic, m, got, exposure, _lit(s, cam))
            miss += bad
            print("  %s: %s, key %.3f (%s), %.0f s%s" % (cam.name, os.path.relpath(out, PROJECT), m["key"], m["key_rule"],
                                                      time.time() - t0, "" if not bad else "  MISS " + "; ".join(bad)))
    sheet()
    return miss, made


# the order a player meets them: the gym, the ring, its districts by stage, the island
SHEET_ORDER = ("Prologue", "World", "SouqAlDawar", "BaytAlDarb", "MarsaAlFajr", "AbrajAlMalih", "AlHilal", "JaziratAlHajar",
               "AlTariqAlMasdud", "MukhayyamAlNiran", "AlHalqa", "MonkeyIsland", "MonkeyIsland-Landing",
               "MonkeyIsland-Clearing", "MonkeyIsland-Temple")


def sheet(cols=3, tile=(640, 360)):
    """Every view on one page, in the order a player meets them."""
    import numpy as np
    from PIL import Image
    tiles = []
    for v in SHEET_ORDER:
        p = os.path.join(RENDERS, "map-%s-anime.png" % v)
        if os.path.exists(p):
            tiles.append(np.asarray(Image.open(p).convert("RGB").resize(tile, Image.LANCZOS)))
    if not tiles:
        return None
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    Image.fromarray(np.vstack(rows)).save(SHEET, optimize=True)
    print("sheet: %s" % os.path.relpath(SHEET, PROJECT))
    return SHEET


# ==================================================================== bite
def bite():
    """Each check broken once, on the saved scenes: every one must notice."""
    import bpy
    from mathutils import Vector
    caught, cases = 0, 0

    def case(label, scene, mutate, expect, rebuild=None):
        nonlocal caught, cases
        cases += 1
        if rebuild:
            SABOTAGE.add(rebuild)
            try:
                BUILD[scene](out=False)
            finally:
                SABOTAGE.discard(rebuild)
        else:
            _open(scene)
            mutate()
        got = CHECKS[scene]([])
        ok = any(expect in g for g in got)
        caught += ok
        print("  %-34s %s%s" % (label, "caught" if ok else "MISSED", "" if ok else " (%s)" % got[:2]))

    def drop_district():
        for o in [o for o in bpy.data.objects if o.get("district") == "MarsaAlFajr"]:
            bpy.data.objects.remove(o, do_unlink=True)

    def turn_away():
        c = bpy.data.objects["Cam_BaytAlDarb"]
        c.rotation_euler.z += math.pi

    def block():
        c = bpy.data.objects["Cam_AlHilal"]
        t = Vector(c["target"]); o = c.location
        bpy.ops.mesh.primitive_cube_add(size=20.0, location=o + (t - o) * 0.5)

    def lights_off():
        for o in [o for o in bpy.data.objects if o.type == "LIGHT" and o.get("night_fire") and o.get("district") == "BaytAlDarb"]:
            bpy.data.objects.remove(o, do_unlink=True)

    def souq_row_moved():
        o = next(o for o in bpy.data.objects if "row" in o and o.data.name.startswith("SM_Souq_Stall"))
        o.location.x += 3.0

    def no_animals():
        a = next(o for o in bpy.data.objects if "animals" in o)
        bpy.data.objects.remove(a, do_unlink=True)

    def post_moved():
        bpy.data.objects["CagePost_3"].location.z += 1.0

    def prop_moved():
        bpy.data.objects["SM_Island_Temple"].location.x += 5.0

    case("a district missing", "world", drop_district, "MarsaAlFajr")
    case("a camera turned away", "world", turn_away, "not in its frame")
    case("a view blocked", "world", block, "behind something")
    case("a district's fires out", "world", lights_off, "night lights")
    case("a souq row moved", "world", souq_row_moved, "where the plan puts it")
    case("the animals gone", "world", no_animals, "animals")
    case("a cage post moved", "prologue", post_moved, "not where the plan puts it")
    case("a prop moved", "island", prop_moved, "not where the plan puts it")
    case("the streets' tops on one plane", "world", None, "share a plane", rebuild="shared_planes")
    case("the fires never end", "world", None, "engine's end", rebuild="no_window")
    case("the ground's height read wrong", "island", None, "not its heightmap", rebuild="height_scale")
    case("plants lost", "island", None, "plants", rebuild="lost_plants")
    # the rendered view's own rule: a lit district's pools, its fires out
    cases += 1
    _open("world")
    cam = bpy.data.objects["Cam_SouqAlDawar"]
    lights_off_all = [o for o in bpy.data.objects if o.type == "LIGHT" and o.get("night_fire")]
    for o in lights_off_all:
        o.data.energy = 0.0
    pic, m, got, exposure = render_view(cam, size=(320, 180), samples=4)
    bad = picture_misses("SouqAlDawar", pic, m, got, exposure, True)
    ok = any("pool" in b for b in bad)
    caught += ok
    print("  %-34s %s" % ("a view's fires dark", "caught" if ok else "MISSED (%s)" % bad))
    print("bite: %d of %d caught" % (caught, cases))
    return caught, cases


BUILD = dict(world=build_world, prologue=build_prologue, island=build_island)


def main():
    a = sys.argv[1:]
    if "--bite" in a:
        caught, cases = bite()
        sys.exit(0 if caught == cases else 1)
    if "--check" in a:
        sys.exit(1 if check() else 0)
    if "--build" in a:
        s = a[a.index("--build") + 1]
        BUILD[s]()
        sys.exit(1 if check((s,)) else 0)
    if "--render" in a:
        i = a.index("--render")
        which = tuple(x for x in a[i + 1:i + 2] if not x.startswith("--")) or ("world", "prologue", "island")
        only = a[a.index("--view") + 1].split(",") if "--view" in a else None
        miss, made = render(which, only=only)
        for m in miss:
            print("  MISS " + m)
        sys.exit(1 if miss else 0)
    for s in ("world", "prologue", "island"):
        BUILD[s]()
    miss = check()
    rmiss, _ = render()
    sys.exit(1 if miss or rmiss else 0)


if __name__ == "__main__":
    main()
