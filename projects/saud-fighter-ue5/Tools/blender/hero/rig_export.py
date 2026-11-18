"""Stage 5-6: the skeleton (the mannequin's 24 plus its 30 finger bones,
root and the IK targets), binding, the guard and kick poses, and the two
exports -- then the exported files are imported back into a fresh scene
and counted, which is the only proof available here that what left is
what arrived."""
import bpy, math, os, sys, time
from mathutils import Vector
import build_saud as legacy

FINGERS = [("index", "f0"), ("middle", "f1"), ("ring", "f2"), ("pinky", "f3")]

def add_finger_bones(arm, joints_l):
    """Mannequin finger bones: index_01_l .. pinky_03_l and thumb_01..03,
    from the hand joint table the hand was built from. The right side is
    the mirror. Deforming, parented to hand_<side>."""
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    made = 0
    for side, s in (("l", 1), ("r", -1)):
        hand = eb["hand_" + side]
        def M(v): return Vector((v.x * s, v.y, v.z))
        for mname, key in FINGERS + [("thumb", "thumb")]:
            pts = joints_l[key]
            parent = hand
            for k in range(3):
                b = eb.new("%s_%02d_%s" % (mname, k + 1, side))
                b.head = M(pts[k]); b.tail = M(pts[k + 1])
                b.parent = parent; b.use_connect = (k > 0); b.use_deform = True
                parent = b; made += 1
    bpy.ops.object.mode_set(mode='OBJECT')
    return made

def _smoothstep(t):
    t = max(0.0, min(1.0, t)); return t * t * (3.0 - 2.0 * t)


def pin_crotch(body, x_reach=0.030, z_centre=0.910, z_reach=0.030):
    """The crotch is welded shut (trunk's flat pelvis floor and the two
    thigh tubes overlap with no groin geometry between them -- CLAUDE.md,
    "Known, not fixed"), and bone heat gives an honest answer for welded
    geometry it should not have been asked: measured at the worst vertex,
    pelvis 0.28 / thigh_l 0.34 / thigh_r 0.37, near-equal thirds. A vertex
    that is a third each of two thighs is pulled toward the AVERAGE of
    wherever they end up, and the moment a pose spreads the legs (the
    guard, the kick) that average drags it into a stretched, jaggedly-
    lit membrane between them -- CLAUDE.md's "trousers carry a web...
    the web stretches between them" -- even though the unposed body and
    the trousers built from it read fine standing neutral. Pinning it to
    the pelvis instead removes the stretch (checked: a sample vertex moved
    13 mm under the guard's thigh spread before this, 0 mm after), and
    since the garments take the body's weights by proximity, the trousers'
    own crotch is fixed by fixing the body's, with no second call needed.

    Tapered, not a hard cutoff, so there is no seam where the pin meets
    ordinary thigh weighting: 1.0 at the weld's own centre (x=0, z=0.910,
    where the trunk's bottom row sits), fading to 0 -- unchanged -- 30 mm
    out in x and in z, which is short of where the legs are genuinely
    their own separate volumes again (checked: x < 0.030 covers the fused
    band; by x = 0.030 in the render's own crop the two thighs already
    read as distinct). Returns how many vertices it touched.
    """
    pelvis = body.vertex_groups.get("pelvis")
    if pelvis is None:
        return 0
    n = 0
    for v in body.data.vertices:
        x, z = v.co.x, v.co.z
        if abs(x) >= x_reach or abs(z - z_centre) >= z_reach:
            continue
        t = _smoothstep(1.0 - abs(x) / x_reach) * _smoothstep(1.0 - abs(z - z_centre) / z_reach)
        if t <= 0.001:
            continue
        w = {ge.group: ge.weight for ge in v.groups}
        for gi, wt in list(w.items()):
            if body.vertex_groups[gi] is not pelvis:
                body.vertex_groups[gi].add([v.index], wt * (1.0 - t), "REPLACE")
        pelvis.add([v.index], w.get(pelvis.index, 0.0) * (1.0 - t) + t, "REPLACE")
        n += 1
    return n


# own_the_knee's wedge: degrees above the knee's level as seen from the leg's
# own axis (0 level with the joint, + toward the hip). On the kneecap's side
# the leg is the shin's whole under the first, heat's over the second, a
# smoothstep between. Tuned on the six rig files, 2026-11-11, the knee
# strike (bent 111 degrees) against the guards (20-55): the further up the
# calf owns, the more of a deep bend is kept and the prouder the kneecap
# stands in a guard. A narrower blend, (20, 45), kept as much of the strike
# and stretched the cloth over the kneecap up to 2.9 times in the guards,
# drawing the track trousers' pleats there into streaks (2.4 at most with
# this, as under plain heat).
KNEE_WEDGE = (15.0, 55.0)
KNEE_REACH = (0.35, 0.50)   # of the thigh's length above the joint and the shin's below: whole within the first, nothing past the second
KNEE_EDGE = 0.035           # of the thigh's length: no edge on the front of a knee is left longer (0: the trousers as decimated)
KNEE_FRONT = (0.12, 0.30)   # the front that is cut finer: this much of the shin under the joint, of the thigh over it
KNEE_HELD = 0.75            # join_all: the least of a kneecap vertex the calf may hold (heat alone: 0.36-0.60)
KNEE_VERTS = 30             # join_all: the fewest vertices the two kneecaps may have between them (45-109 cut finer, 8-20 as decimated)


def own_the_knee(mesh, arm):
    """The kneecap is the shin's (2026-11-10, the bodies reviewed: B10,
    B23). Heat blends a hinge evenly -- the calf's share goes 0.1 to 0.9
    over 11-21 cm of the leg, half and half at the joint, much the same on
    the kneecap's side as behind -- and a linear blend puts a half-and-half
    vertex on the chord between where its two bones would have it: the
    kneecap stood at cos(half the bend) of its distance from the joint,
    0.50-0.58 in the knee strike (111 degrees), the leg a round pipe bend
    7.6 cm through where it is 13.3 at rest. A vertex one bone owns keeps
    its distance.

    On the JOINED mesh, not on the body before the garments take its
    weights: every knee here is a trouser knee, the trousers take the
    body's weights by interpolation across the decimated body's faces, and
    it is at the cloth's own vertices that this was worked and measured
    (the six rig files' joined meshes; what the transfer would carry of a
    wedge a few centimetres tall was not). Two steps, both on the
    kneecap's half of each knee -- the side the joint's own pre-bend
    points to, in front of the hip-to-ankle line.

    The front is cut finer first (KNEE_EDGE, KNEE_FRONT; UVs and weights
    carried across the cuts). The decimation leaves a trouser front in
    faces up to 8 cm long, and a kneecap that turns with the shin under a
    face whose other end stays with the thigh is a dent, not a knee: with
    KNEE_EDGE at 0 the weights alone left the knee strike's kneecap at
    0.29-0.49 of its rest distance on four of the five men in the track
    cut (0.50-0.57 before), a crease down the middle of the knee.

    Then the weights: from the joint's level up to KNEE_WEDGE[0] degrees
    above it, as seen from the leg's axis, the front is the calf's whole
    (the kneecap block), and its blend into the thigh is taken over the
    degrees up to KNEE_WEDGE[1], just above it. An angle, not a height, so
    the block is as tall as the knee is thick, on a 5 cm knee and on a
    14 cm one. Whole at the kneecap's middle and fading round the leg to
    nothing at its sides (a harder edge there folded the trousers' pleats
    in AL-WAHSH's guard), and along it (KNEE_REACH, of the man's own bone
    lengths); the back half is left to heat, whose wide blend lets the
    hollow behind the knee fold. Only the split between the two bones
    moves: what the pair holds of a vertex is what it held, and the calf's
    share is never lowered.

    A compromise, and with two bones it cannot be more: the further up the
    calf owns, the squarer the deep bend and the prouder the kneecap in a
    shallow one -- the guard, where a knee read 0.90-0.99 and must not
    grow a shelf. On the six rig files, joint to the kneecap's skin along
    the bisector of thigh and shin, over the same at rest: the knee strike
    0.81-0.89 (0.50-0.58), a knee bent 90 degrees 0.94-1.02 (0.62-0.70),
    the guards 1.03-1.13 (0.90-0.99). The elbow is left to heat: tried
    with this pass, the point it gains is a boxed facet on Saud and a spur
    on AL-WAHSH's elbow at 134 degrees. Returns (vertices added, vertices
    whose weights moved)."""
    import bmesh
    lo, hi = KNEE_WEDGE
    knees = []
    for s in ("l", "r"):
        gu, gl = mesh.vertex_groups.get("thigh_" + s), mesh.vertex_groups.get("calf_" + s)
        if gu is None or gl is None: continue
        b = arm.data.bones
        J, top, end = b[gl.name].head_local, b[gu.name].head_local, b[gl.name].tail_local
        ax = (top - end).normalized()
        out = (J - end) - ax * (J - end).dot(ax)
        assert out.length > 1e-4, "%s: the knee lies on the hip-to-ankle line -- no pre-bend to tell the kneecap's side by" % gl.name
        knees.append((gu, gl, J, ax, out.normalized(), ax.cross(out.normalized()), (top - J).length, (end - J).length))
    added = 0
    if KNEE_EDGE > 0.0 and knees:
        bm = bmesh.new(); bm.from_mesh(mesh.data)
        dl = bm.verts.layers.deform.verify()
        before = len(bm.verts)
        for gu, gl, J, ax, out, side, up, low in knees:
            def front(e):
                if e.calc_length() <= KNEE_EDGE * up: return False
                if any(v[dl].get(gu.index, 0.0) + v[dl].get(gl.index, 0.0) < 0.5 for v in e.verts): return False
                q = (e.verts[0].co + e.verts[1].co) * 0.5 - J
                return q.dot(out) > 0.0 and -KNEE_FRONT[0] * low < q.dot(ax) < KNEE_FRONT[1] * up
            for _ in range(4):
                long = [e for e in bm.edges if front(e)]
                if not long: break
                bmesh.ops.subdivide_edges(bm, edges=long, cuts=1)
        added = len(bm.verts) - before
        if added:
            # the cuts' own faces only: the mesh's other n-gons are not this pass's to touch
            cut = {f for v in list(bm.verts)[before:] for f in v.link_faces if len(f.verts) > 4}
            if cut: bmesh.ops.triangulate(bm, faces=list(cut))
            bm.to_mesh(mesh.data); mesh.data.update()
        bm.free()
    moved = 0
    for gu, gl, J, ax, out, side, up, low in knees:
        for v in mesh.data.vertices:
            w = {g.group: g.weight for g in v.groups}
            wu, wl = w.get(gu.index, 0.0), w.get(gl.index, 0.0)
            hold = wu + wl
            if hold < 1e-4: continue
            q = v.co - J
            xf = q.dot(out)
            if xf <= 0.0: continue
            xu, xn = q.dot(ax), q.dot(side)
            rho = math.hypot(xf, xn)
            k = _smoothstep(xf / rho)
            k *= 1.0 - _smoothstep((abs(xu) / (up if xu > 0.0 else low) - KNEE_REACH[0]) / (KNEE_REACH[1] - KNEE_REACH[0]))
            if k <= 0.0: continue
            share = wl / hold
            want = 1.0 - _smoothstep((math.degrees(math.atan2(xu, rho)) - lo) / (hi - lo))
            new = share + k * (max(want, share) - share)
            if new - share < 1e-3: continue
            gl.add([v.index], new * hold, "REPLACE")
            if (1.0 - new) * hold > 1e-4: gu.add([v.index], (1.0 - new) * hold, "REPLACE")
            else: gu.remove([v.index])
            moved += 1
    return added, moved


def knee_held(mesh, arm):
    """The least share of the two leg bones' hold that the calf has on any
    vertex of a kneecap -- the front of the knee within 30 degrees of its
    middle, from 15 degrees under the joint's level to 10 over, as seen
    from the leg's axis -- and how many vertices that is over. 1.0: the
    kneecap turns with the shin and keeps its distance from the joint.
    Rest positions, the mesh's own space (the rig's, as it is bound)."""
    least, count = 1.0, 0
    for s in ("l", "r"):
        gu, gl = mesh.vertex_groups.get("thigh_" + s), mesh.vertex_groups.get("calf_" + s)
        if gu is None or gl is None: continue
        b = arm.data.bones
        J, top, end = b[gl.name].head_local, b[gu.name].head_local, b[gl.name].tail_local
        ax = (top - end).normalized()
        out = ((J - end) - ax * (J - end).dot(ax)).normalized(); side = ax.cross(out)
        for v in mesh.data.vertices:
            w = {g.group: g.weight for g in v.groups}
            wu, wl = w.get(gu.index, 0.0), w.get(gl.index, 0.0)
            if wu + wl < 0.5: continue
            q = v.co - J
            xf, xu, xn = q.dot(out), q.dot(ax), q.dot(side)
            if xf <= 0.0 or abs(math.degrees(math.atan2(xn, xf))) > 30.0: continue
            if not -15.0 <= math.degrees(math.atan2(xu, math.hypot(xf, xn))) <= 10.0: continue
            least = min(least, wl / (wu + wl)); count += 1
    return least, count



# The seat and the side of the hip (own_the_seat). Heights are fractions of
# the man's own thigh (hip joint to knee joint: 0.439 m on Saud) down the
# thigh bone from his hip joint, negative above it; the flank is the cosine
# of the angle round the thigh bone from straight behind (1 behind, 0
# beside, -1 straight ahead).
SEAT_BLEND = (-0.14, 0.38)      # behind and beside the hip a thigh holds nothing from the first up (6 cm over the
                                # joint on Saud) and heat's own share from the second down (17 cm under it)
SEAT_GROIN = (-0.30, 0.20)      # in front, from 13 cm over the joint to 9 under it: heat's crease where heat put
                                # it, its top taken off the waistband
SEAT_FLANK = (-0.90, 0.00)      # the front's window gives way to the back's from 26 degrees off straight ahead
                                # round to the hip's side
SEAT_KNEE = (-0.16, -0.86, 0.48)    # build_motion's knee strike: the raised (right) thigh's aim, the hip flexed 119 degrees
# the most seat_held's numbers may be (check_seat). The review's: B09's 0.10 at the waistband's back and 0.35 on
# the buttock, B15's 0.5 on the hip's outer line. ring (B15's 1.5 cm in the guard, as a share) and travel (B09's
# 6 cm x h in the knee strike, which is 0.14 of a thigh) stand between what the pass leaves on the six men
# (0.06-0.18 and 0.10-0.14) and the least bone heat gave them (0.59 and 0.29)
SEAT_HOLD = dict(above=0.10, seat=0.35, side=0.50, ring=0.30, travel=0.18)


def _seat_frame(arm):
    """Back, across (his right to his left), the midline's point and, for
    each leg, (side, sign, hip joint, the thigh's unit axis, its length),
    off the skeleton as it is bound."""
    b = arm.data.bones
    up = (b["spine_01"].head_local - b["pelvis"].head_local).normalized()
    across = (b["thigh_l"].head_local - b["thigh_r"].head_local).normalized()
    legs = []
    for s, sign in (("l", 1.0), ("r", -1.0)):
        hip, knee = b["thigh_" + s].head_local, b["calf_" + s].head_local
        legs.append((s, sign, hip.copy(), (knee - hip).normalized(), (knee - hip).length))
    return up.cross(across).normalized(), across, b["pelvis"].head_local.copy(), legs


def own_the_seat(body, arm):
    """The buttock and the side of the hip are the pelvis's (2026-11-11, the
    bodies reviewed: B09, B15). Bone heat gives them to the thigh bone:
    measured on the six rigs' trousers, the buttock's rearmost patch at the
    hip joint's height 0.53-0.68 thigh, the hip's outer line there 0.95-0.99
    and still 0.60-0.80 at the waistband, 9 cm above the joint. So a raised
    leg took the seat with it -- in the knee strike that patch went 15-20 cm
    under the pelvis and the waistband's back after it -- and in every guard
    the cloth above the joint turned 3-5 cm with its thigh.

    Each thigh's share of a vertex is capped by where the vertex is on that
    thigh. Behind and beside the hip: nothing above SEAT_BLEND[0] of a
    thigh's length over the joint, rising (a smoothstep) to all of it
    SEAT_BLEND[1] down the thigh -- under a fifth at the joint's height,
    half at the gluteal fold: the long blend a seat stretches over when the
    hip flexes. In front the window is SEAT_GROIN's: the groin keeps the
    crease heat gave it, and the thigh lets go of the waistband (heat's
    0.3-0.5 there, 0.5-0.8 at the front corner of the hip). Round the flank
    one window gives way to the other (SEAT_FLANK). What a cap takes goes
    to the pelvis; where heat already gave the thigh less (the cleft, the
    inside of the thigh, the weld pin_crotch has pinned) nothing changes.
    The garments take the body's weights afterwards (bind_all), so the
    trousers' seat is set by setting the body's.

    Held on the mesh that leaves (check_seat, in join_all). Returns how many
    vertices moved."""
    pelvis = body.vertex_groups.get("pelvis")
    if pelvis is None or body.vertex_groups.get("thigh_l") is None or body.vertex_groups.get("thigh_r") is None:
        return 0
    back, _across, _mid, legs = _seat_frame(arm)
    groups = [(body.vertex_groups["thigh_" + s], hip, axis, L) for s, _sign, hip, axis, L in legs]
    moved = 0
    for v in body.data.vertices:
        w = {ge.group: ge.weight for ge in v.groups}
        tot = sum(w.values())
        freed = 0.0
        for g, hip, axis, L in groups:
            wt = w.get(g.index, 0.0)
            if wt <= 0.0: continue
            q = v.co - hip
            d = q.dot(axis) / L
            if d >= max(SEAT_BLEND[1], SEAT_GROIN[1]): continue
            r = q - axis * (d * L)
            behind = _smoothstep((d - SEAT_BLEND[0]) / (SEAT_BLEND[1] - SEAT_BLEND[0]))
            front = _smoothstep((d - SEAT_GROIN[0]) / (SEAT_GROIN[1] - SEAT_GROIN[0]))
            flank = _smoothstep((r.dot(back) / max(r.length, 1e-9) - SEAT_FLANK[0]) / (SEAT_FLANK[1] - SEAT_FLANK[0]))
            take = wt - tot * (front + flank * (behind - front))
            if take <= 1e-6: continue
            if wt - take > 1e-4: g.add([v.index], wt - take, "REPLACE")
            else: g.remove([v.index]); take = wt
            freed += take
        if freed > 0.0:
            pelvis.add([v.index], freed, "ADD"); moved += 1
    return moved


def check_seat(mesh, arm=None):
    """seat_held against SEAT_HOLD on the mesh that leaves (join_all: the
    skin left under the garments, and the trousers with the weights they
    took from it): the build stops if the seat still swings with a thigh
    or a thigh still owns the side of the hip -- own_the_seat skipped or
    undone, or the garments not taking the body's weights. `arm`: the
    armature the mesh is bound to, found if not given. Returns seat_held's
    numbers."""
    arm = arm or mesh.find_armature()
    assert arm is not None, "check_seat: %s is bound to no armature" % mesh.name
    held = seat_held(mesh, arm)
    assert held["above"] <= SEAT_HOLD["above"] and held["seat"] <= SEAT_HOLD["seat"] and held["travel"] <= SEAT_HOLD["travel"], \
        "the seat swings with the thigh: the thighs hold %.2f of the waistband's back (want %.2f at most) and %.2f of the " \
        "buttock's rearmost patch (%.2f), which a knee strike carries %.2f of a thigh's length under the pelvis (%.2f)" % (
            held["above"], SEAT_HOLD["above"], held["seat"], SEAT_HOLD["seat"], held["travel"], SEAT_HOLD["travel"])
    assert held["side"] <= SEAT_HOLD["side"] and held["ring"] <= SEAT_HOLD["ring"], \
        "the thigh owns the side of the hip: %.2f of its outer line at the joint's height (want %.2f at most) and %.2f of " \
        "the cloth above the joint all the way round (%.2f) -- the top of the trouser leg turns with the thigh" % (
            held["side"], SEAT_HOLD["side"], held["ring"], SEAT_HOLD["ring"])
    return held


def seat_held(mesh, arm):
    """What the thighs hold of the seat and the side of the hip on a bound
    mesh at rest (a man's joined mesh, or his body alone) -- shares of a
    vertex's whole weight, the worse leg of the two:
      above   the largest share the thighs have of any vertex behind or
              beside a hip from 0.20 of a thigh over its joint up (the
              waistband's back and side)
      seat    its own thigh's mean share of the buttock's rearmost patch at
              the hip joint's height (eight vertices, within 0.03 of a thigh
              of that height and 0.15 of straight behind the joint)
      side    the same on the hip's outermost patch at that height
      ring    their mean share of everything from 0.045 to 0.20 of a thigh
              over the joint, all the way round (what turns with the thigh
              in a guard)
      travel  how far the rearmost patch goes, in the pelvis's frame, when
              its thigh is raised to the knee strike (SEAT_KNEE, mirrored
              for the left), in thigh lengths
    Every number is 1.0 on a mesh with no such patch to read.
    """
    back, across, mid, legs = _seat_frame(arm)
    thighs = {g.index for g in mesh.vertex_groups if g.name in ("thigh_l", "thigh_r")}
    out = dict(above=0.0, seat=0.0, side=0.0, ring=0.0, travel=0.0)
    for s, sign, hip, axis, L in legs:
        own = mesh.vertex_groups["thigh_" + s].index if "thigh_" + s in mesh.vertex_groups else -1
        patch, band = [], []
        for v in mesh.data.vertices:
            q = v.co - hip
            d = q.dot(axis) / L
            if d > 0.03 or d < -0.5 or (v.co - mid).dot(across) * sign <= 0.0: continue
            r = q - axis * (d * L)
            if r.length > 0.6 * L: continue
            tot = sum(ge.weight for ge in v.groups) or 1.0
            share = sum(ge.weight for ge in v.groups if ge.group in thighs) / tot
            if d >= -0.03:
                patch.append((r.dot(back), r.dot(across) * sign, sum(ge.weight for ge in v.groups if ge.group == own) / tot, q))
            elif d <= -0.20:
                if r.dot(back) >= 0.0: out["above"] = max(out["above"], share)
            elif d <= -0.045:
                band.append(share)
        rear = sorted((t for t in patch if abs(t[1]) <= 0.15 * L), key=lambda t: -t[0])[:8]
        side = sorted((t for t in patch if abs(t[0]) <= 0.08 * L), key=lambda t: -t[1])[:8]
        if not (band and rear and side):
            # a mesh with no hip to read is not vouched for: every number its worst
            return dict(above=1.0, seat=1.0, side=1.0, ring=1.0, travel=1.0)
        out["ring"] = max(out["ring"], sum(band) / len(band))
        out["seat"] = max(out["seat"], sum(t[2] for t in rear) / len(rear))
        out["side"] = max(out["side"], sum(t[2] for t in side) / len(side))
        turn = axis.rotation_difference(Vector((SEAT_KNEE[0] * -sign, SEAT_KNEE[1], SEAT_KNEE[2])).normalized()).to_matrix()
        out["travel"] = max(out["travel"], sum(t[2] * (turn @ t[3] - t[3]).length for t in rear) / len(rear) / L)
    return out


def own_the_head(body, arm):
    """The skull is one bone. Bone heat splits the head at its joint, and
    the head joint is at the eye line: the scan of 2026-09-28 read the
    eyes at 43-56 % head, the scalp 50-88 %, the hair 81-97 %, the rest
    on neck_01 -- so every nod or turn bent the skull at the eyes, the
    globes sliding in their lids. Until then this only repaired a face
    heat had given to the neck entirely (ZAYOS, 2026-09-23).

    Now, on every man: everything from the skull's lower edge up is the
    head's alone (the jaw, the ears, the whole skull); below that, inside
    the neck's column, the skin blends from neck_01 into the head, fading
    into heat's own answer at the column's edge (the trapezius, the
    collar) and at its foot. Returns how many vertices it set.

    2026-11-11 (the bodies reviewed: B22). That edge was level, 0.60 of a
    neck-length under the head joint all round, the blend under it 0.35
    long and the column 0.60 wide: the nape swung rigid with the skull
    about a joint at the eye line, the skull's whole turn was taken in
    3 cm, and a big man's neck, wider than the column, was left to heat.
    On the six built men a head turned 85 degrees folded 80-470 cm of
    the neck's edges sharp, the kick's tilt 18-67. The edge slopes now
    (_skull_edge: the nape is the neck's), the head's share climbs from
    HEAD_BLEND[0] to it -- the whole column behind -- the column fades
    over half a neck-length, not a tenth of one, and the chest hands over
    to neck_01 across NECK_FOOT, down the trapezius. Every length is the
    man's own neck's. check_neck holds it."""
    gh, gn = body.vertex_groups.get("head"), body.vertex_groups.get("neck_01")
    if gh is None or gn is None:
        return 0
    b = arm.data.bones
    ph, pn = b["head"].head_local, b["neck_01"].head_local
    L = ph.z - pn.z
    n = 0
    for v in body.data.vertices:
        d = (ph.z - v.co.z) / L                     # neck-lengths under the head joint
        if d >= NECK_FOOT[0]: continue
        ax = pn + (ph - pn) * min(1.0, max(0.0, 1.0 - d))
        r = math.hypot(v.co.x - ax.x, v.co.y - ax.y) / L
        edge = _skull_edge((v.co.y - ax.y) / L)
        rw = max(1.0 - _smoothstep((r - 0.50) / 0.50), _smoothstep((edge + 0.15 - d) / 0.15))
        rw *= _smoothstep((NECK_FOOT[0] - d) / (NECK_FOOT[0] - NECK_FOOT[1]))
        if rw <= 0.0: continue
        th = _smoothstep((HEAD_BLEND[0] - d) / (HEAD_BLEND[0] - edge))
        heat = {g.group: g.weight for g in v.groups}
        tot = sum(heat.values()) or 1.0
        new = {gi: w / tot * (1.0 - rw) for gi, w in heat.items()}
        new[gh.index] = new.get(gh.index, 0.0) + rw * th
        new[gn.index] = new.get(gn.index, 0.0) + rw * (1.0 - th)
        for gi in heat:
            body.vertex_groups[gi].remove([v.index])
        for gi, w in new.items():
            if w > 1e-4: body.vertex_groups[gi].add([v.index], w, "REPLACE")
        n += 1
    return n


# Fractions of a neck-length under the head joint. The neck blends into the
# head from HEAD_BLEND[0] up to the skull's lower edge: [1] under the jaw,
# [2] behind, at the occiput. The chest hands over to the neck from
# NECK_FOOT[0] up to [1] (the neck joint is 1.0).
HEAD_BLEND = (0.95, 0.60, 0.25)
NECK_FOOT = (1.20, 0.80)


def _skull_edge(back):
    """How far under the head joint the skull ends and the neck begins, in
    neck-lengths, `back` neck-lengths behind the neck's axis: HEAD_BLEND[1]
    under the jaw and forward of it, rising behind the jaw's angle, under
    the ear, to HEAD_BLEND[2] at the occiput. The nape is the neck's."""
    return HEAD_BLEND[1] + (HEAD_BLEND[2] - HEAD_BLEND[1]) * _smoothstep((back + 0.15) / 0.70)


def head_held(mesh, arm):
    """The least share any vertex of the skull -- everything from its lower
    edge up (_skull_edge) -- gives the head bone (1.0: the skull is rigid),
    and how many vertices that is over. Rest positions, in the skeleton's
    own frame."""
    b = arm.data.bones
    ph, pn = b["head"].head_local, b["neck_01"].head_local
    L = ph.z - pn.z
    g = mesh.vertex_groups.get("head")
    if g is None:
        return 0.0, 0
    own = arm.matrix_world.inverted() @ mesh.matrix_world
    least, count = 1.0, 0
    for v in mesh.data.vertices:
        co = own @ v.co
        d = (ph.z - co.z) / L
        if d > max(HEAD_BLEND[1:]): continue
        ax = pn + (ph - pn) * min(1.0, max(0.0, 1.0 - d))
        if d > _skull_edge((co.y - ax.y) / L): continue
        tot = sum(x.weight for x in v.groups) or 1.0
        w = sum(x.weight for x in v.groups if x.group == g.index) / tot
        least = min(least, w); count += 1
    return least, count


def neck_posed(mesh, arm, turn=0.0, tilt=0.0):
    """The neck with the head turned `turn` degrees about the bones' own
    lengths and tilted `tilt` to its side, the neck taking 0.40 of each and
    the head the rest as the clips split it (rig_full_ik._aim, motion_ik
    .fk_body), by the mesh's own weights -- linear blend, as the armature
    deforms it; nothing in the scene is posed. Over the faces within 1.6
    neck-lengths of the neck's axis from 0.45 under its joint to the head
    joint -- but not the chin and the front of the jaw, 0.45 forward of the
    axis, which are the face's and so finely meshed that they would be
    most of any percentile -- returns (metres of new sharp fold: edges
    whose two faces stand 70 degrees or more to each other and 45 more
    than at rest, slivers under 1.3 % of a neck-length high left out; the
    stretch of the edge at the 99.9th percentile)."""
    import numpy as np
    from mathutils import Matrix
    b = arm.data.bones
    ph, pn = np.array(b["head"].head_local), np.array(b["neck_01"].head_local)
    L = ph[2] - pn[2]
    own = np.array(arm.matrix_world.inverted() @ mesh.matrix_world)
    me = mesh.data
    V = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3) @ own[:3, :3].T + own[:3, 3]
    k = (V[:, 2] - pn[2]) / L
    ax = pn + (ph - pn) * np.clip(k, 0.0, 1.0)[:, None]
    near = (k > -0.45) & (k < 1.0) & (np.hypot(V[:, 0] - ax[:, 0], V[:, 1] - ax[:, 1]) < 1.6 * L)
    near &= ~((k > 0.25) & (V[:, 1] - ax[:, 1] < -0.45 * L))
    gi = {g.name: g.index for g in mesh.vertex_groups}
    wn, wh = np.zeros(len(V)), np.zeros(len(V))
    for i in np.where(near)[0]:
        ws = {x.group: x.weight for x in me.vertices[int(i)].groups}
        tot = sum(ws.values()) or 1.0
        wn[i], wh[i] = ws.get(gi["neck_01"], 0.0) / tot, ws.get(gi["head"], 0.0) / tot
    def rot(bone, share):
        axis = (b[bone].tail_local - b[bone].head_local).normalized()
        return np.array(Matrix.Rotation(math.radians(tilt * share), 3, (0, 1, 0)) @ Matrix.Rotation(math.radians(turn * share), 3, axis))
    Rn, Rh = rot("neck_01", 0.40), rot("head", 0.60)
    Pn = (V - pn) @ Rn.T + pn                       # carried by the neck
    Ph = ((V - ph) @ Rh.T + ph - pn) @ Rn.T + pn    # by the head, on the neck
    P = V + wn[:, None] * (Pn - V) + wh[:, None] * (Ph - V)
    tris = [(p.vertices[0], p.vertices[j], p.vertices[j + 1]) for p in me.polygons
            if all(near[i] for i in p.vertices) for j in range(1, len(p.vertices) - 1)]
    if not tris:
        return 0.0, 1.0
    T = np.array(tris)
    pair = {}
    for f, t in enumerate(tris):
        for a, c in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            pair.setdefault((min(a, c), max(a, c)), []).append(f)
    E = np.array([(a, c, f[0], f[1]) for (a, c), f in pair.items() if len(f) == 2])
    def normals(X):
        n = np.cross(X[T[:, 1]] - X[T[:, 0]], X[T[:, 2]] - X[T[:, 0]])
        return n, n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-18)
    def between(N):
        return np.degrees(np.arccos(np.clip((N[E[:, 2]] * N[E[:, 3]]).sum(1), -1.0, 1.0)))
    (A0, N0), (_A1, N1) = normals(V), normals(P)
    l0 = np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1)
    l1 = np.linalg.norm(P[E[:, 0]] - P[E[:, 1]], axis=1)
    high = np.minimum(np.linalg.norm(A0[E[:, 2]], axis=1), np.linalg.norm(A0[E[:, 3]], axis=1)) / np.maximum(l0, 1e-12)
    d0, d1 = between(N0), between(N1)
    sharp = (d1 >= 70.0) & (d1 - d0 >= 45.0) & (high >= 0.013 * L)
    return float(l1[sharp].sum()), float(np.percentile(l1 / np.maximum(l0, 1e-12), 99.9))


def check_neck(mesh, arm):
    """What own_the_head leaves, held (2026-11-11, the bodies reviewed:
    B22): the skull rigid, and the neck in the three poses the clips ask
    most of it -- the kick's frame 8 (the head tilted 25 degrees and turned
    24 on the chest), a head half turned (45) and the hook's and cross's
    full turn (85: neck 34 + head 51). The limits are the man's own
    neck-lengths. Measured 2026-11-11 on the six men's real bodies bound
    with heat, the level edge and the 3 cm blend against this: the kick
    1.2-4.9 neck-lengths of new sharp fold -> 0-0.14; 45 degrees 1.6-4.9
    -> 0-0.06; at 85 the 99.9th percentile edge stretched 2.9-6.8 times ->
    1.7-2.0 (and its new sharp folds 6.5-23.6 neck-lengths -> 0.8-2.2:
    the nape and the neck's root are decimated to edges 5-12 cm long, and
    one edge cannot carry a turn of 85 degrees smoothly -- not held).
    Returns the three measures."""
    least, count = head_held(mesh, arm)
    assert count and least >= 0.98, "head: a vertex of the skull is only %.0f %% on the head bone (of %d)" % (least * 100, count)
    b = arm.data.bones
    L = b["head"].head_local.z - b["neck_01"].head_local.z
    kick, _ = neck_posed(mesh, arm, turn=24.0, tilt=25.0)
    assert kick <= 0.5 * L, ("neck: the head tilted 25 degrees and turned 24 (the kick's frame 8) folds %.1f cm of the neck sharp, "
                             "over half a neck-length: the nape is swinging with the skull (HEAD_BLEND, _skull_edge)" % (kick * 100))
    half, _ = neck_posed(mesh, arm, turn=45.0)
    assert half <= 0.8 * L, ("neck: the head turned 45 degrees folds %.1f cm of the neck sharp, over 0.8 of a neck-length: "
                             "the skull's turn is taken in a few centimetres (HEAD_BLEND, NECK_FOOT)" % (half * 100))
    _, full = neck_posed(mesh, arm, turn=85.0)
    assert full <= 2.5, ("neck: the head turned 85 degrees (the hook) stretches one edge in a thousand %.2f times, over 2.5: "
                         "the neck shears into a flap (HEAD_BLEND, NECK_FOOT, the column in own_the_head)" % full)
    return kick, half, full


def stiffen_gloves(body):
    """A boxing glove does not bend with the fingers inside it (2026-11-10,
    the bodies reviewed: B06). Heat puts a glove's surface on the finger
    and thumb bones under it, and every clip closes the fist: ZAYOS's
    gloves crumpled. Every vertex of a glove's faces (the material the
    pipeline names <Man>_Glove) gives what its finger and thumb bones hold
    to the hand bone of its side; the hand's own blend into the forearm at
    the cuff is heat's and is left. Returns how many vertices moved."""
    slots = [i for i, m in enumerate(body.data.materials) if m is not None and m.name.endswith("_Glove")]
    if not slots: return 0
    on = set()
    for p in body.data.polygons:
        if p.material_index in slots: on.update(p.vertices)
    moved = 0
    for side in ("l", "r"):
        hand = body.vertex_groups.get("hand_" + side)
        if hand is None: continue
        fingers = {g.index: g for g in body.vertex_groups
                   if g.name.endswith("_" + side) and g.name.split("_")[0] in ("index", "middle", "ring", "pinky", "thumb")}
        for vi in on:
            v = body.data.vertices[vi]
            held = [(g.group, g.weight) for g in v.groups if g.group in fingers and g.weight > 0.0]
            if not held: continue
            hand.add([vi], sum(w for _, w in held), "ADD")
            for gi, _ in held: fingers[gi].remove([vi])
            moved += 1
    return moved


def bind_all(body, garments, arm, crotch=None, gloved=False):
    """Heat on the body; the garments take the body's weights by proximity,
    which is what a shell 5 mm off the skin should do -- heat on a shell
    finds its own answer and it is not the body's. `crotch` is where the
    weld is on this man (anatomy.scale_to); left out, Saud's own. `gloved`:
    his gloves are made rigid on his hands (stiffen_gloves)."""
    legacy.bind(body, arm)
    n = own_the_head(body, arm)
    print("head: the skull made rigid on the head bone, the neck blended into it (%d vertices)" % n)
    kick, half, full = check_neck(body, arm)
    print("neck: %.1f cm of new sharp fold in the kick's tilt, %.1f with the head turned 45 degrees; turned 85, the 99.9th percentile edge stretched x%.2f" % (kick * 100, half * 100, full))
    print("crotch: %d vertices pinned toward the pelvis (tapered)" % pin_crotch(body, **(crotch or {})))
    # The toe box belongs to ball_*: heat gives everything ahead of the ball
    # joint two thirds to foot_*, so a toe roll pitched the whole shoe with
    # the foot bone and its toe went 35 mm through the floor while the bones
    # said the toes stayed flat. Every vertex ahead of the ball joint that
    # the two bones between them hold takes the foot's share on the ball.
    moved = 0
    for s in ("l", "r"):
        gf, gb = body.vertex_groups.get("foot_" + s), body.vertex_groups.get("ball_" + s)
        ball_y = legacy.J["ball_" + s][0].y
        if gf is None or gb is None: continue
        for v in body.data.vertices:
            if v.co.y >= ball_y: continue
            w = {g.group: g.weight for g in v.groups}
            wf, wb = w.get(gf.index, 0.0), w.get(gb.index, 0.0)
            if wf > 0.0 and wf + wb >= 0.3:
                gb.add([v.index], wf + wb, "REPLACE"); gf.remove([v.index]); moved += 1
    print("toe boxes: %d vertices' foot weight moved onto the ball" % moved)
    print("seat: %d vertices' thigh weight given back to the pelvis (the buttock, the side of the hip)" % own_the_seat(body, arm))
    if gloved:
        n = stiffen_gloves(body)
        assert n > 0, "a gloved man with no glove vertex on a finger bone: the glove material was not found"
        print("gloves: %d vertices' finger weight moved onto the hand" % n)
    for g in garments:
        g.parent = arm
        mod = g.modifiers.new("Skin", "ARMATURE"); mod.object = arm
        dt = g.modifiers.new("Weights", "DATA_TRANSFER"); dt.object = body
        dt.use_vert_data = True; dt.data_types_verts = {'VGROUP_WEIGHTS'}; dt.vert_mapping = 'POLYINTERP_NEAREST'
        dt.layers_vgroup_select_src = 'ALL'; dt.layers_vgroup_select_dst = 'NAME'
        bpy.context.view_layer.objects.active = g
        for vg in body.vertex_groups: 
            if vg.name not in g.vertex_groups: g.vertex_groups.new(name=vg.name)
        bpy.ops.object.datalayout_transfer(modifier="Weights")
        bpy.ops.object.modifier_apply(modifier="Weights")
        # the armature modifier must come first for the join to keep it
        while g.modifiers.find("Skin") > 0: bpy.ops.object.modifier_move_up(modifier="Skin")

def join_all(body, others):
    bpy.ops.object.select_all(action='DESELECT')
    for o in others: o.select_set(True)
    body.select_set(True); bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    # Heat leaves a handful of the body's weights a few thousandths over
    # one (up to 1.011 on Saud at full resolution), and the garments'
    # interpolated weights do the same; the exporters call the mesh invalid
    # for it. Clamped, not normalised, once, on the one mesh that leaves.
    over = 0
    for v in body.data.vertices:
        for ge in v.groups:
            if ge.weight > 1.0:
                body.vertex_groups[ge.group].add([v.index], 1.0, "REPLACE"); over += 1
    if over:
        print("clamped %d weights that heat or the transfer left over 1.0" % over)
    print("seat: on what leaves, the thighs hold %(above).2f of the waistband's back, %(seat).2f of the buttock, "
          "%(side).2f of the hip's outer line" % check_seat(body))
    print("knees: the trouser fronts cut finer (%d vertices added), the kneecap given to the shin (%d vertices)" % own_the_knee(body, body.find_armature()))
    least, n = knee_held(body, body.find_armature())
    assert n >= KNEE_VERTS, (
        "the front of the knees is too coarse to carry a kneecap: %d vertices on the two of them (at least %d) -- a kneecap that "
        "turns with the shin under a long face is a crease down the middle of the bent knee (own_the_knee, KNEE_EDGE)" % (n, KNEE_VERTS))
    assert least >= KNEE_HELD, (
        "the kneecap is shared with the thigh: of %d vertices on the front of the knees the calf holds as little as %.2f of one "
        "(at least %.2f) -- a bent knee pinches like a hose, the kneecap falling toward the joint (own_the_knee)" % (n, least, KNEE_HELD))
    return body

def close_fists(arm, amount=1.0):
    """Both hands to build_saud's fist (0 the built hand, 1 closed): the
    fingers turned in and the thumb folded across them. curl_fingers, below,
    tightened 10 degrees a joint, which left the built claw with its thumb
    out in every guard and kick render until 2026-09-24."""
    import build_saud as legacy
    legacy.close_fists(arm, amount)

def curl_fingers(arm, degrees):
    """Tighten the fists for the fight poses.

    The MESH is the fist -- anatomy.hand() builds the fingers already curled
    72 / 109 / 36 degrees, fitted to the fist the joint table describes, and
    the finger bones are made from that same chain, so the rest pose is a
    closed hand. This only squeezes it further, so the angle is small: the
    78 degrees a joint it used to take was written for a mesh whose fingers
    were nearly straight, and applied to a hand that is already closed it
    folds them through the palm.
    """
    for pb in arm.pose.bones:
        n = pb.name
        if any(n.startswith(f + "_") for f, _ in FINGERS):
            pb.rotation_mode = 'XYZ'; pb.rotation_euler = (math.radians(-degrees), 0, 0)
        elif n.startswith("thumb_"):
            pb.rotation_mode = 'XYZ'; pb.rotation_euler = (math.radians(-degrees * 0.5), 0, 0)
    bpy.context.view_layer.update()

def export_all(arm, mesh, out_ue5, out_unity, textures_ue5, textures_unity, name="Saud"):
    # out_unity is None when the frozen Unity port is not asked for, which
    # is the default -- see ../../../CLAUDE.md. Making a directory called
    # None is how the pipeline used to end.
    os.makedirs(out_ue5, exist_ok=True)
    if out_unity:
        os.makedirs(out_unity, exist_ok=True)
    # Only the rig and the mesh leave. The IK pole targets are children of
    # the rig and glTF takes a selected object's children along, so they go
    # first -- the constraints are muted for export and do not travel anyway.
    for o in [o for o in bpy.data.objects if o.type == 'MESH' and o is not mesh]:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True); mesh.select_set(True)
    bpy.context.view_layer.objects.active = arm
    # Nothing embeds its textures. The bake has just written them next door
    # into Content/Textures/Saud and both engines import a PNG as an asset
    # of their own anyway, so an embedded copy is a second and a third 34 MB
    # of the same sixteen files -- inside a container, where git cannot even
    # see that they are the same. Both formats reference them instead.
    gltf = os.path.join(out_ue5, name + ".gltf")
    bpy.ops.export_scene.gltf(filepath=gltf, export_format="GLTF_SEPARATE", use_selection=True,
                              export_yup=True, export_apply=True, export_keep_originals=True)
    fbx = os.path.join(out_ue5, name + ".fbx")
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, apply_unit_scale=True, global_scale=1.0,
                             apply_scale_options="FBX_SCALE_UNITS", add_leaf_bones=False,
                             primary_bone_axis="Y", secondary_bone_axis="X", object_types={"ARMATURE", "MESH"},
                             mesh_smooth_type="FACE", bake_space_transform=False,
                             path_mode='RELATIVE', embed_textures=False)
    # Metres, Y up: a Unity export, and a different file from the Unreal one
    # above rather than a copy of it. Skipped when that port is not asked for.
    ufbx = None
    if out_unity:
        ufbx = os.path.join(out_unity, name + ".fbx")
        bpy.ops.export_scene.fbx(filepath=ufbx, use_selection=True, apply_unit_scale=True, global_scale=1.0,
                                 apply_scale_options="FBX_SCALE_NONE", add_leaf_bones=False,
                                 primary_bone_axis="Y", secondary_bone_axis="X", object_types={"ARMATURE", "MESH"},
                                 mesh_smooth_type="FACE", axis_forward="-Z", axis_up="Y", bake_space_transform=True,
                                 path_mode='COPY', embed_textures=False)
    return gltf, fbx, ufbx

def verify_gltf(path):
    """Read the glTF's own JSON: what an engine's importer sees, with no
    Blender importer in between (Blender's adds a bone-shape mesh of its
    own). Every image must resolve to a file that is really there, which is
    the thing that can go wrong once they are not embedded."""
    import json
    j = json.load(open(path))
    missing = [i.get("uri") for i in j.get("images", [])
               if "uri" not in i or not os.path.exists(os.path.join(os.path.dirname(path), i["uri"]))]
    assert not missing, "the glTF points at textures that are not there: %s" % missing
    acc = j["accessors"]
    tris = sum(acc[p["indices"]]["count"] // 3 for m in j["meshes"] for p in m["primitives"] if "indices" in p)
    zs = [(acc[p["attributes"]["POSITION"]]["min"][1], acc[p["attributes"]["POSITION"]]["max"][1])
          for m in j["meshes"] for p in m["primitives"]]        # glTF is Y-up
    return dict(armatures=len(j.get("skins", [])), bones=sum(len(s["joints"]) for s in j.get("skins", [])),
                meshes=[m["name"] for m in j["meshes"]], tris=tris, materials=len(j.get("materials", [])),
                images=len(j.get("images", [])), images_resolve=True,
                height=max(z[1] for z in zs) - min(z[0] for z in zs))

def gltf_bone_names(path):
    """The joint names the glTF's own JSON carries: what an engine reads."""
    import json
    j = json.load(open(path))
    return {j["nodes"][i]["name"] for s in j.get("skins", []) for i in s["joints"]}


def verify_roundtrip(path):
    """Import into a fresh scene and count what came back."""
    if path.endswith((".gltf", ".glb")): return verify_gltf(path)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    bones = sum(len(a.data.bones) for a in arms)
    tris = sum(sum(len(p.vertices) - 2 for p in m.data.polygons) for m in meshes)
    mats = set(); imgs = set()
    for m in meshes:
        for slot in m.material_slots:
            if slot.material:
                mats.add(slot.material.name)
                if slot.material.node_tree:
                    for n in slot.material.node_tree.nodes:
                        if n.type == 'TEX_IMAGE' and n.image: imgs.add((n.image.name, n.image.size[0]))
    zs = [ (m.matrix_world @ v.co).z for m in meshes for v in m.data.vertices ]
    return dict(armatures=len(arms), bones=bones, meshes=[m.name for m in meshes], tris=tris, materials=len(mats), images=sorted(imgs),
                height=(max(zs) - min(zs)) if zs else 0)
