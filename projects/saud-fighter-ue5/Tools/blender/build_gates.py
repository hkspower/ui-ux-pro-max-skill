#!/usr/bin/env python3
"""The System's portals, built: a rift in every sealed gate and in the
arena's door (2026-10-07, Riyadh; "gates as portals", the Unreal build).

    python3 build_gates.py             the plan and its checks (no Blender)
    python3 build_gates.py --bite      break each rule once, prove it is caught
    python3 build_gates.py --build     (bpy) the FBX into Content/Models/Gates/,
                                       read back
    python3 build_gates.py --preview   (bpy) Docs/renders/gate-portals.png: every
                                       gate kind and the door in every state,
                                       through the anime look
    (in the editor) imported by build_levels.py, build_world.py and
    build_souq.py, which put a portal in every gate and the arena's door

WHAT A PORTAL IS. A flat oval of swirling energy in a thin ringed frame,
set in the gate's own wall: the gate's mesh stays (the cube, or the souq's
cracked wall) and the portal stands in it -- a rift THROUGH the gate, its
energy 1.5 cm proud of each face and its frame 3 cm, so it reads from
either side. Its look is Tools/look/portal.py's material (the colour, the
swirl, the three states, the light); this file is the mesh, where it
stands, and the preview.

SIZED FROM THE LEVEL DATA. Every gate kind stands in the same box, the
AbilityGate's cube as build_levels.py and build_world.py place it (1.6 x
0.6 x 3.0 m) and the souq's gate wall (build_souq.GATE_BOX, the same box);
each kind's oval is placed in it as the sealed way it is:
    Wall    the cracked wall (HAYMAKER)    a tall rift along the crack
    Shutter the steel shutter (POWER KICK) the shutter's opening, low and wide
    Ledge   the ledge (VAULT)              high in the wall, where he climbs to
    Gap     the broken ground (DASH LEAP)  low and wide, at the break
    Stash   the locker (nothing)           small, the locker's door
all of them above the souq wall's damp plinth (40 cm) and inside 5 cm of
the box's edges. The arena's door (an AreaExit, its trigger 1.2 x 14 x 6
m) gets a free-standing oval 4.2 x 5.4 m on the floor across the way
through, 10 cm off the ground, a man's capsule through it with room.

THE ARENA'S DOOR is known from the data: the exit whose destination is the
title fight -- DT_Stages' arena row (Theme Arena, a boss stage, not
survival: AL-HALQA, index 8). Only the souq's Door to it qualifies; the
arena's own way back to the souq is a street. The builders set the exit's
bArenaDoor from is_arena_door() and give it SM_Portal_ArenaDoor; nothing is
decided by hand.

CHECKED (check(), and the level builders' own checks call
placement_misses()): every mesh closed (every edge in two faces, opposite
ways) and wound out (its volume positive); inside its gate's box and no
more than PROUD_MAX proud of it, its energy face proud of the plinth and
the crack; the UVs the material reads (UV0 the oval, its edge at 1; UV1 -1
on the energy and 0..1 across the frame, the oval's aspect); under its
triangle budget; the door's oval inside its trigger, its lip under a step,
a man's capsule through it; the portals collide with nothing (the C++);
every gate in a plan wears its kind's portal, the arena's door its own and
no street exit one, the door's portal clear of every fight and every fire
beside it. --bite breaks each.

UNVERIFIED. No engine has imported a portal; the FBX is written by Blender
and read back by Blender. The editor half (import, the material slot, the
portal component's mesh and its lift on the souq wall) is read-reviewed,
not run: the component is reached as the actor's "portal" property, the
lift by set_relative_location, and bArenaDoor as "arena_door", as UE 5.4's
Python names them from memory.
"""
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
LOOK_DIR = os.path.join(PROJECT, "Tools", "look")
MODELS = os.path.join(PROJECT, "Content", "Models", "Gates")
RENDERS = os.path.join(PROJECT, "Docs", "renders")
MESH_DIR = "/Game/Models/Gates"
GATE_CPP = os.path.join(PROJECT, "Source", "SaudFighter", "World", "AbilityGate.cpp")
EXIT_CPP = os.path.join(PROJECT, "Source", "SaudFighter", "World", "AreaExit.cpp")

# the AbilityGate's box, every kind (build_levels' and build_world's cube
# scale, build_souq.GATE_BOX): w along X, d along Y (its faces), h up, cm
GATE_BOX = (160.0, 60.0, 300.0)
GATE_CUBE_SRC = (("Tools/levels/build_levels.py", r"mesh_cube\(actor, \(1\.6, 0\.6, 3\.0\)\)"),
                 ("Tools/levels/build_world.py", r"set_actor_scale3d\(unreal\.Vector\(1\.6, 0\.6, 3\.0\)\)"))
PLINTH_CM = (40.0, 1.2)          # build_souq.PLINTH: the gate wall's damp band, h and proud, cm
CRACK_CM = 0.2                   # build_souq.build_gate: the crack's face, proud of the wall
EDGE_CM = 5.0                    # a portal stays this far inside its box's sides and top
PROUD_E, PROUD_F = 1.5, 3.0      # the energy face, the frame, proud of the gate's face, cm
PROUD_MAX = 4.0                  # nothing further proud than this
FRAME_CM = 6.0                   # the ring's width
SEGMENTS = 48
TRI_BUDGET = 800

# kind: the oval's outer width, height and middle above the gate's foot, cm
PORTALS = {
    "Wall":    dict(w=120.0, h=230.0, zc=165.0, why="a tall rift along the crack"),
    "Shutter": dict(w=150.0, h=190.0, zc=145.0, why="the shutter's opening, low and wide"),
    "Ledge":   dict(w=130.0, h=140.0, zc=215.0, why="high in the wall, where he climbs to"),
    "Gap":     dict(w=150.0, h=110.0, zc=100.0, why="low and wide, at the break"),
    "Stash":   dict(w=90.0, h=120.0, zc=115.0, why="small, the locker's door"),
}
# the arena's door: AreaExit's trigger (its extent in AreaExit.cpp) is the box
DOOR = dict(w=420.0, h=540.0, zc=280.0, frame=10.0, ye=3.0, yf=5.0)
DOOR_MESH = "SM_Portal_ArenaDoor"
CAPSULE = dict(r=34.0, h=176.0)  # ACharacter's default capsule (radius 34, half-height 88), as remembered
STEP_CM = 45.0                   # the movement component's default step height, as remembered
SITE_RADIUS = 900.0              # SaudArena::SiteRadius, the builders' SITE_RADIUS: a fight's room
MATERIAL_OF = {"gate": "M_Portal_System", "door": "M_Portal_Danger"}
INSTANCE_OF = {"M_Portal_System": "MI_Portal_System", "M_Portal_Danger": "MI_Portal_Danger"}

SABOTAGE = set()


def mesh_for(gate_type):
    return "SM_Portal_%s" % gate_type


def kinds():
    """Every portal mesh: name -> (kind, gate type or None)."""
    out = {mesh_for(k): ("gate", k) for k in PORTALS}
    out[DOOR_MESH] = ("door", None)
    return out


# ------------------------------------------------------------ the arena door
def arena_stage(stages):
    """The title fight's row: Theme Arena, a boss stage, not survival."""
    rows = [s for s in stages if s.get("Theme") == "Arena" and s.get("bIsBossStage") and not s.get("bSurvival")]
    assert len(rows) == 1, "DT_Stages has %d title-fight rows (Theme Arena, a boss stage, not survival), want 1" % len(rows)
    return rows[0]["Name"]


def is_arena_door(destination_stage, stages):
    return destination_stage == arena_stage(stages)


# ------------------------------------------------------------- the geometry
def geometry(name):
    """One portal as plain data, in the gate's own frame (cm, Z up, X along
    the gate, its faces -Y and +Y; a gate's origin is its box's middle, the
    door's the floor under its middle): verts, faces (vertex loops), per
    loop UV0 and UV1, and the numbers it was made from."""
    kind, gt = kinds()[name]
    if kind == "gate":
        p = PORTALS[gt]
        W, H, F = p["w"], p["h"], FRAME_CM
        zc = p["zc"] - GATE_BOX[2] * 0.5
        ye, yf = GATE_BOX[1] * 0.5 + PROUD_E, GATE_BOX[1] * 0.5 + PROUD_F
    else:
        W, H, F = DOOR["w"], DOOR["h"], DOOR["frame"]
        zc, ye, yf = DOOR["zc"], DOOR["ye"], DOOR["yf"]
    if "wide_portal" in SABOTAGE and kind == "gate":
        W = GATE_BOX[0] + 10.0
    if "sunk_energy" in SABOTAGE:
        ye = (GATE_BOX[1] * 0.5 if kind == "gate" else 0.0) + 0.5
    if "low_door" in SABOTAGE and kind == "door":
        zc = H * 0.5 + 60.0
    if "proud_far" in SABOTAGE and kind == "gate":
        yf = GATE_BOX[1] * 0.5 + 6.0
    if "small_door" in SABOTAGE and kind == "door":
        W = 110.0
    if "tall_door" in SABOTAGE and kind == "door":
        H, zc = 800.0, 410.0
    A, B = W * 0.5, H * 0.5
    a, b = A - F, B - F
    n = SEGMENTS * (4 if "dense" in SABOTAGE else 1)
    ts = [2.0 * math.pi * i / n for i in range(n)]
    verts = []

    def ring(sa, sb, y):
        base = len(verts)
        for t in ts:
            verts.append((sa * math.cos(t), y, zc + sb * math.sin(t)))
        return base

    c_f = len(verts); verts.append((0.0, -ye, zc))
    rings = [ring(a, b, -ye), ring(a, b, -yf), ring(A, B, -yf), ring(A, B, yf), ring(a, b, yf), ring(a, b, ye)]
    c_b = len(verts); verts.append((0.0, ye, zc))
    aspect = b / a

    def uv0(v):
        x, _y, z = verts[v]
        return (x / (2.0 * a) + 0.5, (z - zc) / (2.0 * b) + 0.5)

    def q_of(v):
        x, _y, z = verts[v]
        r = math.hypot(x / a, (z - zc) / b)
        ro = 1.0 / math.sqrt((math.cos(math.atan2((z - zc) / b, x / a)) * a / A) ** 2
                             + (math.sin(math.atan2((z - zc) / b, x / a)) * b / B) ** 2)
        return min(1.0, max(0.0, (r - 1.0) / max(ro - 1.0, 1e-9)))

    faces, U0, U1 = [], [], []

    def face(loop, energy):
        faces.append(loop)
        U0.append([uv0(v) for v in loop])
        U1.append([(-1.0 if energy else q_of(v), aspect) for v in loop])

    for i in range(n):
        j = (i + 1) % n
        face([c_f, rings[0] + i, rings[0] + j], True)                 # the energy, front (-Y)
    for k in range(len(rings) - 1):
        r0, r1 = rings[k], rings[k + 1]
        for i in range(n):
            j = (i + 1) % n
            face([r0 + j, r0 + i, r1 + i, r1 + j], False)              # the lip, the frame, the side
    for i in range(n):
        j = (i + 1) % n
        face([c_b, rings[-1] + j, rings[-1] + i], True)               # the energy, back (+Y)
    if "open_mesh" in SABOTAGE:
        faces.pop(3); U0.pop(3); U1.pop(3)
    if "wound_in" in SABOTAGE:
        faces = [list(reversed(f)) for f in faces]
        U0 = [list(reversed(u)) for u in U0]; U1 = [list(reversed(u)) for u in U1]
    if "flat_uv" in SABOTAGE:
        U1 = [[(-1.0, aspect) for _ in u] for u in U1]
    return dict(name=name, kind=kind, gate=gt, verts=verts, faces=faces, uv0=U0, uv1=U1,
                w=W, h=H, zc=zc, a=a, b=b, A=A, B=B, ye=ye, yf=yf, material=MATERIAL_OF[kind])


def _volume(verts, faces):
    v = 0.0
    for f in faces:
        p0 = verts[f[0]]
        for k in range(1, len(f) - 1):
            p1, p2 = verts[f[k]], verts[f[k + 1]]
            v += (p0[0] * (p1[1] * p2[2] - p1[2] * p2[1]) - p0[1] * (p1[0] * p2[2] - p1[2] * p2[0])
                  + p0[2] * (p1[0] * p2[1] - p1[1] * p2[0])) / 6.0
    return v


def mesh_misses(G):
    """One portal's mesh against the rules."""
    out = []
    name, verts, faces = G["name"], G["verts"], G["faces"]
    edges = {}
    for f in faces:
        for k in range(len(f)):
            e = (f[k], f[(k + 1) % len(f)])
            edges[e] = edges.get(e, 0) + 1
    bad = sum(1 for (u, v), c in edges.items() if c != 1 or edges.get((v, u), 0) != 1)
    if bad:
        out.append("%s is not closed: %d edges not in exactly two faces, opposite ways" % (name, bad))
    vol = _volume(verts, faces)
    if vol <= 0.0:
        out.append("%s is wound in (its volume %.0f cm3): a one-sided material would cull its faces" % (name, vol))
    tris = sum(len(f) - 2 for f in faces)
    if tris > TRI_BUDGET:
        out.append("%s is %d tris, over its %d budget" % (name, tris, TRI_BUDGET))
    xs, ys, zs = [p[0] for p in verts], [p[1] for p in verts], [p[2] for p in verts]
    if G["kind"] == "gate":
        w, d, h = GATE_BOX
        if max(map(abs, xs)) > w * 0.5 - EDGE_CM + 1e-6 or max(zs) > h * 0.5 - EDGE_CM + 1e-6 or min(zs) < -h * 0.5:
            out.append("%s stands outside its gate's box (%.0f x %.0f cm in a %.0f x %.0f face, %.0f cm in)"
                       % (name, max(xs) - min(xs), max(zs) - min(zs), w, h, EDGE_CM))
        if max(map(abs, ys)) > d * 0.5 + PROUD_MAX + 1e-6:
            out.append("%s stands %.1f cm proud of its gate (at most %.1f)" % (name, max(map(abs, ys)) - d * 0.5, PROUD_MAX))
        if G["ye"] - d * 0.5 <= max(PLINTH_CM[1], CRACK_CM):
            out.append("%s's energy is %.1f cm proud of the gate's face: under the plinth (%.1f) or the crack it is hidden"
                       % (name, G["ye"] - d * 0.5, PLINTH_CM[1]))
        if G["zc"] - G["B"] + h * 0.5 < PLINTH_CM[0] and G["ye"] - d * 0.5 <= PLINTH_CM[1]:
            out.append("%s reaches into the plinth" % name)
    else:
        ex = trigger_extent()
        if max(map(abs, xs)) > ex[1] or max(map(abs, ys)) > ex[0] or max(zs) > 2.0 * ex[2] or min(zs) < 0.0:
            out.append("%s stands outside the door's trigger" % name)
        lip = G["zc"] - G["b"]
        if lip > STEP_CM:
            out.append("%s's lip is %.0f cm up: a man cannot step through it (a step is %.0f)" % (name, lip, STEP_CM))
        r, hc = CAPSULE["r"], CAPSULE["h"]
        pts = [(sx * r, lip + r + (hc - 2 * r) * k) for sx in (-1, 1) for k in (0.0, 0.5, 1.0)]
        pts += [(0.0, lip), (0.0, lip + hc)]
        out_of = [p for p in pts if (p[0] / G["a"]) ** 2 + ((p[1] - G["zc"]) / G["b"]) ** 2 > 1.0]
        if out_of:
            out.append("%s is too small for a man to walk through: his capsule leaves the oval at %s" % (name, out_of[0]))
    # the UVs the material reads
    for f, u0, u1 in zip(faces, G["uv0"], G["uv1"]):
        for (u, v), (q, asp) in zip(u0, u1):
            r = math.hypot(u * 2.0 - 1.0, v * 2.0 - 1.0)
            if q < 0.0 and r > 1.0 + 1e-6:
                out.append("%s's energy reaches past its oval in UV0 (%.3f)" % (name, r)); break
            if q >= 0.0 and r < 1.0 - 1e-6:
                out.append("%s's frame lies inside its oval in UV0 (%.3f)" % (name, r)); break
            if abs(asp - G["b"] / G["a"]) > 1e-6:
                out.append("%s's UV1 does not carry its aspect" % name); break
        else:
            continue
        break
    q_frame = [q for u1 in G["uv1"] for q, _ in u1 if q >= 0.0]
    if not q_frame or max(q_frame) < 0.99 or min(q_frame) > 0.01:
        out.append("%s's frame does not run 0..1 across in UV1" % name)
    if not any(q < 0.0 for u1 in G["uv1"] for q, _ in u1):
        out.append("%s has no energy in UV1 (-1): the material would draw it all as frame" % name)
    return out


def trigger_extent():
    """AAreaExit's trigger extent (cm), read from AreaExit.cpp."""
    m = re.search(r"Trigger->SetBoxExtent\(FVector\(([0-9.]+)f,\s*([0-9.]+)f,\s*([0-9.]+)f\)\)", open(EXIT_CPP).read())
    return tuple(float(x) for x in m.groups()) if m else (60.0, 700.0, 300.0)


def source_misses(texts=None):
    """The box is the levels' cube and the souq's wall; the portals collide
    with nothing and cast no shadow (the C++)."""
    T = texts or {}
    read = lambda rel: T[rel] if rel in T else open(os.path.join(PROJECT, rel), encoding="utf-8").read()
    out = []
    for rel, pat in GATE_CUBE_SRC:
        if not re.search(pat, read(rel)):
            out.append("%s's gate cube is not GATE_BOX %s: the portals are sized for another box" % (rel, GATE_BOX))
    m = re.search(r"^GATE_BOX = \(([0-9.]+), ([0-9.]+), ([0-9.]+)\)", read("Tools/blender/build_souq.py"), re.M)
    if not m or tuple(float(x) for x in m.groups()) != GATE_BOX:
        out.append("build_souq.GATE_BOX is not GATE_BOX %s" % (GATE_BOX,))
    m = re.search(r"^PLINTH = dict\(h=([0-9.]+), proud=([0-9.]+)\)", read("Tools/blender/build_souq.py"), re.M)
    if not m or (float(m.group(1)) * 100.0, float(m.group(2)) * 100.0) != PLINTH_CM:
        out.append("build_souq.PLINTH is not PLINTH_CM %s" % (PLINTH_CM,))
    for rel in ("Source/SaudFighter/World/AbilityGate.cpp", "Source/SaudFighter/World/AreaExit.cpp"):
        src = read(rel)
        if "Portal->SetCollisionEnabled(ECollisionEnabled::NoCollision)" not in src:
            out.append("%s's portal collides: a portal is never in the street or a fight as a thing to walk into" % rel)
        if "Portal->SetUsingAbsoluteScale(true)" not in src:
            out.append("%s's portal takes its parent's scale: the gate's cube is scaled 1.6 x 0.6 x 3.0" % rel)
    return out


# ------------------------------------------------------------- the placement
def placement_misses(actors, stages, middle=None, fights=None, solids=None, expect_doors=None, where=""):
    """A level plan's gates and exits against the portals: every Gate
    wears its kind's portal, the arena's door its own (bArenaDoor) and no
    other exit one; the door's portal, across its way through, clear of
    every fight and every fire. `middle(a)` the district's middle an exit
    stands in, `fights(a)` [(x, y, r)] and `solids(a)` [(x, y, half)] in
    the same frame as the actors."""
    out = []
    arena = arena_stage(stages)
    doors = 0
    for a in actors:
        p = a["props"]
        if a["kind"] == "Gate":
            want = mesh_for(p["GateType"])
            if p.get("GateType") not in PORTALS:
                out.append("%s%s is a %s, a gate kind with no portal" % (where, a["name"], p.get("GateType")))
            elif not p.get("Portal"):
                out.append("%s%s has no portal" % (where, a["name"]))
            elif p["Portal"] != want:
                out.append("%s%s wears %s, not its kind's %s" % (where, a["name"], p["Portal"], want))
        elif a["kind"] == "Exit":
            if p.get("DestinationStage") == arena:
                doors += 1
                if not p.get("ArenaDoor") or p.get("Portal") != DOOR_MESH:
                    out.append("%sthe arena's door %s has no portal (ArenaDoor %s, Portal %s)"
                               % (where, a["name"], p.get("ArenaDoor"), p.get("Portal")))
                    continue
                if middle is not None:
                    ox, oy = middle(a)
                    ix, iy = ox - a["x"], oy - a["y"]
                    il = math.hypot(ix, iy) or 1.0
                    tx, ty = -iy / il, ix / il                     # along the rim: the portal's face
                    half = DOOR["w"] * 0.5
                    def seg_dist(x, y):
                        u = max(-half, min(half, (x - a["x"]) * tx + (y - a["y"]) * ty))
                        return math.hypot(x - a["x"] - u * tx, y - a["y"] - u * ty)
                    for (fx, fy, r) in (fights(a) if fights else ()):
                        if seg_dist(fx, fy) < r:
                            out.append("%sthe arena door's portal stands in a fight (%.0f cm from its middle, its room %.0f)"
                                       % (where, seg_dist(fx, fy), r))
                    for (sx, sy, h) in (solids(a) if solids else ()):
                        if seg_dist(sx, sy) < h + DOOR["yf"]:
                            out.append("%sthe arena door's portal stands through a fire beside the door (%.0f cm off it)"
                                       % (where, seg_dist(sx, sy)))
            elif p.get("ArenaDoor") or p.get("Portal"):
                out.append("%sthe street exit %s wears the arena's portal" % (where, a["name"]))
    if expect_doors is not None and doors != expect_doors:
        out.append("%s%d arena doors, want %d" % (where, doors, expect_doors))
    return out


def gate_props(gate_type):
    """What a planned Gate carries for its portal."""
    return dict(Portal=mesh_for(gate_type))


def exit_props(destination_stage, stages):
    """What a planned Exit carries: the arena's door its portal, the rest nothing."""
    if is_arena_door(destination_stage, stages):
        return dict(ArenaDoor=True, Portal=DOOR_MESH)
    return dict(ArenaDoor=False, Portal="")


# ------------------------------------------------------------------ check
def check(verbose=True):
    out = []
    for name in kinds():
        out.extend(mesh_misses(geometry(name)))
    out.extend(source_misses())
    if verbose:
        for m in out:
            print("MISS " + m)
        if not out:
            rows = []
            for name in kinds():
                G = geometry(name)
                rows.append("%s %.0fx%.0f cm, %d tris" % (name[10:], G["w"], G["h"], sum(len(f) - 2 for f in G["faces"])))
            print("checked: every portal closed and wound out, in its gate's box (%s) and %.0f cm proud at most,"
                  % ("x".join("%.0f" % v for v in GATE_BOX), PROUD_MAX))
            print("its energy proud of the plinth, its UVs the material's; the door's in its trigger, a man through it;")
            print("none of them collides. " + "; ".join(rows))
    return out


def bite():
    """Every rule broken once: the mesh (by SABOTAGE) and the sources."""
    if check(verbose=False):
        print("the unbroken portals fail their own checks:"); check(); return False
    print("  %-18s passes" % "(unbroken)")
    cases = [("open_mesh", "is not closed"), ("wound_in", "is wound in"), ("wide_portal", "outside its gate's box"),
             ("sunk_energy", "hidden"), ("dense", "over its"), ("flat_uv", "frame does not run"),
             ("low_door", "cannot step through"), ("proud_far", "proud of its gate"),
             ("small_door", "too small for a man"), ("tall_door", "outside the door's trigger")]
    caught = 0
    for flag, want in cases:
        SABOTAGE.clear(); SABOTAGE.add(flag)
        try:
            miss = check(verbose=False)
        finally:
            SABOTAGE.clear()
        hit = [m for m in miss if want in m]
        caught += bool(hit)
        print("  %-18s %s" % (flag, ("caught: " + hit[0]) if hit else "NOT caught (%s)" % (miss[:1] or "passes")))

    def broken(rel, old, new):
        t = open(os.path.join(PROJECT, rel), encoding="utf-8").read()
        assert old in t, "sabotage did not apply: %s" % old
        return {rel: t.replace(old, new, 1)}
    src = [("cube drift", broken("Tools/levels/build_world.py", "unreal.Vector(1.6, 0.6, 3.0)", "unreal.Vector(1.6, 0.8, 3.0)"), "sized for another box"),
           ("portal collides", broken("Source/SaudFighter/World/AbilityGate.cpp", "Portal->SetCollisionEnabled(ECollisionEnabled::NoCollision)",
                                      "Portal->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics)"), "collides"),
           ("door scaled", broken("Source/SaudFighter/World/AreaExit.cpp", "Portal->SetUsingAbsoluteScale(true)", "Portal->SetUsingAbsoluteScale(false)"), "parent's scale")]
    for name, T, want in src:
        hit = [m for m in source_misses(T) if want in m]
        caught += bool(hit)
        print("  %-18s %s" % (name, ("caught: " + hit[0]) if hit else "NOT caught"))
    # the placement rules, on a small plan of their own
    stages = _stages()
    arena = arena_stage(stages)
    def plan():
        return [dict(kind="Gate", name="G", x=0.0, y=0.0, z=150.0, props=dict(GateType="Wall", **gate_props("Wall"))),
                dict(kind="Exit", name="D", x=0.0, y=1000.0, z=300.0, props=dict(DestinationStage=arena, **exit_props(arena, stages))),
                dict(kind="Exit", name="E", x=1000.0, y=0.0, z=300.0, props=dict(DestinationStage="BaytAlDarb", **exit_props("BaytAlDarb", stages)))]
    mid = lambda a: (0.0, 0.0)
    base = placement_misses(plan(), stages, middle=mid, fights=lambda a: [(500.0, -500.0, SITE_RADIUS)], expect_doors=1)
    if base:
        print("  the unbroken placement fails: %s" % base[0]); return False
    pcases = []
    P = plan(); P[0]["props"].pop("Portal"); pcases.append(("gate bare", P, {}, "has no portal"))
    P = plan(); P[0]["props"]["Portal"] = mesh_for("Ledge"); pcases.append(("wrong kind", P, {}, "not its kind's"))
    P = plan(); P[1]["props"]["ArenaDoor"] = False; pcases.append(("door bare", P, {}, "the arena's door"))
    P = plan(); P[2]["props"].update(ArenaDoor=True, Portal=DOOR_MESH); pcases.append(("street portal", P, {}, "street exit"))
    pcases.append(("door in a fight", plan(), dict(fights=lambda a: [(150.0, 1000.0, SITE_RADIUS)]), "stands in a fight"))
    pcases.append(("door through fire", plan(), dict(solids=lambda a: [(120.0, 1000.0, 30.0)]), "through a fire"))
    for name, P, kw, want in pcases:
        miss = placement_misses(P, stages, middle=mid, expect_doors=1, **kw)
        hit = [m for m in miss if want in m]
        caught += bool(hit)
        print("  %-18s %s" % (name, ("caught: " + hit[0]) if hit else "NOT caught (%s)" % (miss[:1] or "passes")))
    total = len(cases) + len(src) + len(pcases)
    print("  %d of %d bite" % (caught, total))
    return caught == total


def _stages():
    with open(os.path.join(PROJECT, "Content", "Data", "DT_Stages.json"), encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------ the build (bpy)
def _object(bpy, G, link=True):
    """A Blender object of one portal, in metres (the souq's convention)."""
    import bmesh
    me = bpy.data.meshes.new(G["name"])
    bm = bmesh.new()
    vs = [bm.verts.new((x / 100.0, y / 100.0, z / 100.0)) for x, y, z in G["verts"]]
    uv0 = bm.loops.layers.uv.new("UVMap")
    uv1 = bm.loops.layers.uv.new("UVPortal")
    for f, u0, u1 in zip(G["faces"], G["uv0"], G["uv1"]):
        face = bm.faces.new([vs[i] for i in f])
        for loop, a, b in zip(face.loops, u0, u1):
            loop[uv0].uv = a
            loop[uv1].uv = b
    bm.to_mesh(me); bm.free(); me.update()
    mat = bpy.data.materials.get(G["material"]) or bpy.data.materials.new(G["material"])
    me.materials.append(mat)
    o = bpy.data.objects.new(G["name"], me)
    if link:
        bpy.context.scene.collection.objects.link(o)
    return o


def build():
    """Every portal's FBX into Content/Models/Gates/, as the souq exports
    its kinds (centimetres and Z-up-to-Y-up baked into the vertices, FBX
    scale 1.0), and one read back to its size and vertex count."""
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(MODELS, exist_ok=True)
    made = {}
    for name in kinds():
        G = geometry(name)
        miss = mesh_misses(G)
        assert not miss, miss[0]
        o = _object(bpy, G)
        bpy.ops.object.select_all(action="DESELECT"); o.select_set(True); bpy.context.view_layer.objects.active = o
        path = os.path.join(MODELS, name + ".fbx")
        bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH"}, apply_unit_scale=True, global_scale=1.0,
                                 apply_scale_options="FBX_SCALE_NONE", bake_space_transform=True, mesh_smooth_type="FACE",
                                 use_mesh_modifiers=True, path_mode="RELATIVE", embed_textures=False, bake_anim=False)
        made[name] = (path, len(G["verts"]), G)
        bpy.data.objects.remove(o, do_unlink=True)
    # read back: every one, its size and its vertices, both UV layers
    for name, (path, nv, G) in made.items():
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=path)
        back = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
        assert len(back) == 1, "%s read back as %d meshes" % (name, len(back))
        o = back[0]
        ws = [o.matrix_world @ v.co for v in o.data.vertices]
        w = (max(v.x for v in ws) - min(v.x for v in ws)) * 100.0
        h = (max(v.z for v in ws) - min(v.z for v in ws)) * 100.0
        assert abs(w - G["w"]) < 0.5 and abs(h - G["h"]) < 0.5, "%s reads back %.1f x %.1f cm, not %.0f x %.0f" % (name, w, h, G["w"], G["h"])
        assert len(o.data.vertices) == nv, "%s reads back with %d vertices, not %d" % (name, len(o.data.vertices), nv)
        layers = [l.name for l in o.data.uv_layers]
        assert len(layers) == 2, "%s reads back with UV layers %s: the material reads two" % (name, layers)
        print("  %s.fbx  %.0f x %.0f cm, %d vertices, UV %s  (read back)" % (name, w, h, nv, ", ".join(layers)))
        for ob in back:
            bpy.data.objects.remove(ob, do_unlink=True)
    with open(os.path.join(MODELS, "Gates_portals.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(units="centimetres, Z up; a gate portal's origin is its gate box's middle, the door's the floor under it; "
                             "faces along +-Y; UV0 the oval, UV1 (-1 energy / 0..1 frame, the oval's aspect)",
                       box=GATE_BOX, proud=dict(energy=PROUD_E, frame=PROUD_F), frame=FRAME_CM,
                       portals={n: dict(w=geometry(n)["w"], h=geometry(n)["h"], material=geometry(n)["material"],
                                        why=PORTALS[kinds()[n][1]]["why"] if kinds()[n][0] == "gate" else "the arena's door")
                                for n in kinds()}), fh, indent=1)
    return made


# ---------------------------------------------------------- the preview (bpy)
STATES = (("SEALED", 0.0), ("OPENABLE", 1.0), ("OPENING: the flare", 1.175), ("OPENING: the collapse", 1.6))
PREVIEW_T = 2.0          # game seconds the swirl is shown at


def _texture(bpy, G, state, colour, n=384):
    """The material's mirror (portal.emission) over this portal's UV0 space,
    as a float image (RGB key units, A the mask), and its UV0 range."""
    import numpy as np
    sys.path.insert(0, LOOK_DIR)
    import portal as PT
    a, b, A, B = G["a"], G["b"], G["A"], G["B"]
    pm = max(A / a, B / b) * 1.02
    u = (np.arange(n) + 0.5) / n * 2.0 * pm - pm
    X, Z = np.meshgrid(u, u)                        # row 0 the bottom, as a Blender image
    P = np.stack([X, Z], -1)
    R = np.hypot(X, Z)
    th = np.arctan2(Z, X)
    ro = 1.0 / np.sqrt((np.cos(th) * a / A) ** 2 + (np.sin(th) * b / B) ** 2)
    Q = np.where(R < 1.0, -1.0, np.clip((R - 1.0) / np.maximum(ro - 1.0, 1e-9), 0.0, 1.0))
    rgb, mask, _lock = PT.emission(P, Q, b / a, state, PREVIEW_T, colour)
    mask = np.where(R <= ro, mask, 0.0)
    img = bpy.data.images.new("%s_%.3f" % (G["name"], state), n, n, alpha=True, float_buffer=True)
    px = np.concatenate([rgb, mask[..., None]], -1).astype(np.float32)
    img.pixels.foreach_set(px.ravel())
    return img, pm


def _portal_material(bpy, name, img, pm, strength):
    """Emission of the mirror's light, cut by its mask: no base colour, as
    the game's portal writes none to the G-buffer."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    uv = nt.nodes.new("ShaderNodeUVMap"); uv.uv_map = "UVMap"
    sub = nt.nodes.new("ShaderNodeVectorMath"); sub.operation = "SUBTRACT"; sub.inputs[1].default_value = (0.5, 0.5, 0.0)
    sc = nt.nodes.new("ShaderNodeVectorMath"); sc.operation = "SCALE"; sc.inputs["Scale"].default_value = 1.0 / pm
    add = nt.nodes.new("ShaderNodeVectorMath"); add.operation = "ADD"; add.inputs[1].default_value = (0.5, 0.5, 0.0)
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img; tex.extension = "CLIP"; tex.interpolation = "Closest"
    emit = nt.nodes.new("ShaderNodeEmission"); emit.inputs["Strength"].default_value = strength
    cut = nt.nodes.new("ShaderNodeMath"); cut.operation = "GREATER_THAN"; cut.inputs[1].default_value = 0.5
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    L = nt.links.new
    L(uv.outputs["UV"], sub.inputs[0]); L(sub.outputs["Vector"], sc.inputs[0]); L(sc.outputs["Vector"], add.inputs[0])
    L(add.outputs["Vector"], tex.inputs["Vector"]); L(tex.outputs["Color"], emit.inputs["Color"])
    L(tex.outputs["Alpha"], cut.inputs[0]); L(cut.outputs["Value"], mix.inputs["Fac"])
    L(clear.outputs[0], mix.inputs[1]); L(emit.outputs[0], mix.inputs[2]); L(mix.outputs[0], out.inputs["Surface"])
    return m


def _flat_material(bpy, name, rgb, rough=0.9):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = tuple(rgb) + (1.0,)
    bsdf.inputs["Roughness"].default_value = rough
    return m


def _row_scene(kind_name):
    """One row of the sheet: four of this portal in its gate, one a state,
    on soot flagstone under the souq's moon and one pyre in front."""
    import bpy
    import numpy as np
    sys.path.insert(0, HERE)
    import build_souq as BS
    sys.path.insert(0, LOOK_DIR)
    from anime_look import LOOK
    import anime_preview as AP
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    G = geometry(kind_name)
    door = G["kind"] == "door"
    gap = 5.6 if door else 2.7
    xs = [(i - 1.5) * gap for i in range(len(STATES))]
    # the ground: the souq flagstone's soot
    flag = BS.palette("M_Souq_Flagstone")
    ground_col = tuple((np.array(BS._lin(flag[0])[:3]) + np.array(BS._lin(flag[1])[:3])) * 0.5)
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.0, 4.0, 0.0))
    gnd = bpy.context.object; gnd.scale = (60.0, 40.0, 1.0); gnd.data.materials.append(_flat_material(bpy, "Ground", ground_col))
    # the moon: the souq's, from the camera's left, 24 degrees up; the sky
    light = bpy.data.lights.new("Moon", "SUN"); light.energy = BS.MOON["energy"]; light.color = BS.MOON["colour"]
    light.angle = math.radians(BS.MOON["angle"])
    moon = bpy.data.objects.new("Moon", light); sc.collection.objects.link(moon)
    from mathutils import Vector
    el, az = math.radians(BS.NIGHT["moon_pitch"]), math.radians(235.0)
    to_moon = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))
    moon.rotation_euler = to_moon.to_track_quat("Z", "Y").to_euler()
    world = bpy.data.worlds.new("Night"); sc.world = world; world.use_nodes = True
    bg = world.node_tree.nodes["Background"]; bg.inputs[0].default_value = BS._lin(BS._hex(BS.MOON["sky"])); bg.inputs[1].default_value = BS.MOON["sky_strength"]
    # a pyre either side of the row, out in front at the souq's own distance
    at = BS.NIGHT["pyre"]["at_m"]
    for k, fx in enumerate((-at * 0.75, at * 0.75)):
        L = bpy.data.lights.new("Fire_%d" % k, "POINT"); L.energy = BS.watts(BS.intensity("pyre"))
        L.use_temperature = True; L.temperature = BS.NIGHT["temp_k"]; L.shadow_soft_size = 0.15
        f = bpy.data.objects.new("Fire_%d" % k, L); f.location = (fx, -at * 0.75, BS.NIGHT["pyre"]["h"]); f["night_fire"] = 1
        sc.collection.objects.link(f)
    bpy.context.view_layer.update()                 # the moon's matrix, which moon_open reads
    key = AP.KEY_OVER_MOON * AP.moon_open()         # the buffer's key: the portal's key units into Blender's
    colour = LOOK["HUD_DANGER" if door else "HUD_SYSTEM"]
    # the gates: the souq's own cracked wall for a Wall, the engine cube the
    # world's other gates are (the default material: ENGINE_GREY)
    wall_fbx = os.path.join(PROJECT, "Content", "Models", "Souq", "SM_Souq_GateWall.fbx")
    for i, (label, s) in enumerate(STATES):
        x = xs[i]
        if not door:
            if G["gate"] == "Wall" and os.path.exists(wall_fbx):
                before = set(bpy.data.objects)
                bpy.ops.import_scene.fbx(filepath=wall_fbx)
                for o in set(bpy.data.objects) - before:
                    o.location = (x, 0.0, 0.0)
            else:
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, 0.0, GATE_BOX[2] / 200.0))
                c = bpy.context.object; c.scale = (GATE_BOX[0] / 100.0, GATE_BOX[1] / 100.0, GATE_BOX[2] / 100.0)
                c.data.materials.append(bpy.data.materials.get("EngineGrey") or _flat_material(bpy, "EngineGrey", (0.22, 0.22, 0.22), 0.5))
        img, pm = _texture(bpy, G, s, colour)
        o = _object(bpy, G)
        o.data.materials.clear(); o.data.materials.append(_portal_material(bpy, "Portal_%d" % i, img, pm, key))
        o.location = (x, 0.0, 0.0 if door else GATE_BOX[2] / 200.0)
    # the camera: in front of the row, a man's eye a little up
    span = gap * (len(STATES) - 1) + G["w"] / 100.0
    cam_d = bpy.data.cameras.new("Cam"); cam_d.lens = 35.0
    cam = bpy.data.objects.new("Cam", cam_d); sc.collection.objects.link(cam); sc.camera = cam
    dist = span * 1.05 + 1.0
    at = Vector((0.0, 0.0, (G["zc"] / 100.0) if door else 1.55))
    cam.location = (0.0, -dist, 1.7 if not door else 2.6)
    cam.rotation_euler = (at - Vector(cam.location)).to_track_quat("-Z", "Y").to_euler()
    sc.render.resolution_x, sc.render.resolution_y = 1280, 400
    return G


def preview(out=None, samples=24, height=400):
    """Docs/renders/gate-portals.png: every gate kind and the arena's door,
    each in its four states, through the anime look as the game draws it
    (anime_preview.render_scene + look_from), each row held to the dark
    areas' hole rule on the portals and on the frame."""
    import bpy
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    sys.path.insert(0, HERE)
    import anime_preview as AP
    import build_map_scenes as BMS
    out = out or os.path.join(RENDERS, "gate-portals.png")
    rows, report = [], []
    for name in list(mesh_for(k) for k in ("Wall", "Shutter", "Ledge", "Gap", "Stash")) + [DOOR_MESH]:
        G = _row_scene(name)
        got, exposure = AP.render_scene(size=(1280, height), samples=samples)
        pic, m = AP.look_from(got, exposure)
        holes = BMS.hole_share(pic, m, got)
        portal = (got["DiffuseColor"][..., :3] @ np.array(AP.AL.LUMA) < 1e-4) & (got["Depth"][..., 0] < 1e8)
        d = pic.astype(float) / 255.0
        lin = np.where(d <= 0.04045, d / 12.92, ((d + 0.055) / 1.055) ** 2.4)
        y = lin @ np.array(AP.AL.LUMA)
        Ls = np.where(y > 216 / 24389, 116 * np.cbrt(y) - 16, y * 24389 / 27)
        ink = (m["ink"] > 0.5) | (m["hatch"] > 0.5) | (m["screentone"] > 0.5)
        p_holes = float(((Ls < BMS.HOLE_L) & ~ink)[portal].mean()) if portal.any() else 1.0
        report.append(dict(name=name, key=m["key"], holes=holes, portal_holes=p_holes, portal_share=float(portal.mean()),
                           portal_L=float(np.median(Ls[portal])) if portal.any() else 0.0))
        rows.append((G, pic))
        print("  %-22s key %.3f, holes %.1f %% of the frame, %.2f %% of the portals (%.1f %% of the frame is portal, median L* %.0f)"
              % (name, m["key"], holes * 100, p_holes * 100, portal.mean() * 100, report[-1]["portal_L"]), flush=True)
    W, Hh, lab = 1280, height, 30
    sheet = Image.new("RGB", (W, 54 + len(rows) * (Hh + lab)), (6, 9, 20))
    dr = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 17); big = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
    except Exception:
        font = big = ImageFont.load_default()
    dr.text((14, 14), "THE SYSTEM'S PORTALS -- every sealed gate and the arena's door, as the game draws them", fill=(234, 246, 255), font=big)
    names = {"Wall": "CRACKED WALL (HAYMAKER)", "Shutter": "STEEL SHUTTER (POWER KICK)", "Ledge": "LEDGE (VAULT)",
             "Gap": "BROKEN GROUND (DASH LEAP)", "Stash": "LOCKER (needs nothing: never sealed in the game)"}
    for r, (G, pic) in enumerate(rows):
        y0 = 54 + r * (Hh + lab)
        title = names.get(G["gate"], "THE ARENA'S DOOR (HAWK FIST) -- crimson")
        dr.text((14, y0 + 6), title, fill=(70, 200, 255) if G["kind"] == "gate" else (255, 51, 85), font=font)
        sheet.paste(Image.fromarray(pic), (0, y0 + lab))
        for i, (label, _s) in enumerate(STATES):
            dr.text((W * i // 4 + W // 8 - 70, y0 + lab + Hh - 26), label, fill=(234, 246, 255), font=font)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out)
    print("wrote %s" % out)
    miss = []
    for r in report:
        if r["portal_holes"] > 0.01:
            miss.append("%s: %.1f %% of its portals drawn as black holes" % (r["name"], r["portal_holes"] * 100))
        if r["holes"] > BMS.HOLE_SHARE:
            miss.append("%s: %.1f %% of the frame black holes (at most %.0f %%)" % (r["name"], r["holes"] * 100, BMS.HOLE_SHARE * 100))
    for m_ in miss:
        print("MISS " + m_)
    return report, miss


# ----------------------------------------------------------------- editor
def import_meshes():
    """Inside the editor: the portal material (Tools/look/portal.py) if it
    is not built, every portal FBX into MESH_DIR with its instance on its
    slot, and the meshes back by name. Read-reviewed, not run."""
    import unreal  # noqa: E402  (only importable inside the editor)
    EAL = unreal.EditorAssetLibrary
    if LOOK_DIR not in sys.path:
        sys.path.insert(0, LOOK_DIR)
    import portal as PT  # noqa: E402
    if not all(EAL.does_asset_exist("%s/%s" % (PT.MAT_DIR, n)) for n in PT.INSTANCES):
        PT.build_in_editor()
    tasks = []
    for name in kinds():
        t = unreal.AssetImportTask()
        t.filename = os.path.join(MODELS, name + ".fbx"); t.destination_path = MESH_DIR
        t.automated = True; t.save = True; t.replace_existing = True
        ui = unreal.FbxImportUI(); ui.import_mesh = True; ui.import_materials = False; ui.import_textures = False
        ui.import_as_skeletal = False; ui.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
        t.options = ui; tasks.append(t)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    meshes = {}
    for name, (kind, _gt) in kinds().items():
        mesh = unreal.load_asset("%s/%s" % (MESH_DIR, name))
        mi = unreal.load_asset("%s/%s" % (PT.MAT_DIR, INSTANCE_OF[MATERIAL_OF[kind]]))
        mesh.set_material(0, mi)
        EAL.save_loaded_asset(mesh)
        meshes[name] = mesh
    return meshes


def attach_gate(actor, gate_type, meshes, foot=False):
    """Inside the editor: the gate's portal component wears its kind's
    mesh. `foot`: the gate's origin is its foot (the souq's wall), so the
    portal, whose origin is the box's middle, is lifted half the box."""
    import unreal  # noqa: E402
    comp = actor.get_editor_property("portal")
    comp.set_static_mesh(meshes[mesh_for(gate_type)])
    if foot:
        comp.set_relative_location(unreal.Vector(0.0, 0.0, GATE_BOX[2] * 0.5), False, False)
    return comp


def attach_door(actor, meshes):
    """Inside the editor: the arena's door is marked and wears its portal."""
    actor.set_editor_property("arena_door", True)
    comp = actor.get_editor_property("portal")
    comp.set_static_mesh(meshes[DOOR_MESH])
    return comp


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    if "--bite" in argv:
        sys.exit(0 if bite() else 1)
    miss = check()
    if miss:
        sys.exit(1)
    if "--build" in argv:
        build()
    if "--preview" in argv:
        _r, pm = preview(samples=int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 24)
        sys.exit(1 if pm else 0)
