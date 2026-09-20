#!/usr/bin/env python3
"""Motion for the three bosses -- AL-WAHSH, AL-SAQR and ZAYOS.

    python3 build_motion.py              plan, check, describe, build, export
    python3 build_motion.py --check      the assertions only, no Blender work
    python3 build_motion.py --describe   what it would make, and why
    python3 build_motion.py --sheet      render a contact sheet of every clip
    python3 build_motion.py --out DIR    write somewhere else than the project

WHY THIS EXISTS. The Unreal build has no animation at all. SaudTypes.h says
the montage is "Optional -- the game is fully playable without animation",
and it meant it: there is no AnimSequence, no montage and no animated FBX
anywhere in the project. The art direction asks for "weight, follow-through,
recovery you can read. Contact frames that land." None of that is in the
build, so the three title fights are three men sliding at each other.

WHERE THE NUMBERS COME FROM. Nothing here is invented that the project
already knows:

  WHEN      Content/Data/DT_Attacks.csv -- Startup, Active, Recovery per
            strike, in seconds. A clip is exactly su + ac + rc long and its
            contact frame is exactly at su. These came from the browser
            build's assets/hits.js and are not ours to change.
  WHO       Content/Data/DT_Fighters.csv -- each boss's Moves list, in order,
            plus MoveSpeed and AttackInterval.
  SHAPE     the browser build's own attackPose(), index.html:1347. It draws
            every fighter procedurally, so it IS the canonical motion: which
            limb throws, how far the torso leans, how far the hip drops, how
            far the body shifts, and for the spinning kick how many turns.
            Its numbers are quoted in MOVES below, with the line they came
            from.
  WHO THEY  ../../saud-fighter/CLAUDE.md -- the canon. ZAYOS "only ever
  ARE       punches"; AL-SAQR is "all legs, no patience"; AL-WAHSH is "what
            staying looks like when you are very good at it".

WHAT DOES NOT TRANSFER. The browser draws a fighter as two-bone limbs in a
flat side view -- upper arm 26 px, forearm 25, thigh 34, shank 32. Those are
a 2D stylisation's proportions, and this build's are measured off Winter's
tables. So the LENGTHS do not cross over and are not used. The ANGLES and the
TIMING do, because they are dimensionless, and the torso numbers do, because
lean and hip drop are the same quantity in both.

WHAT IT DOES NOT DO. It does not wire the clips into the game, because there
is nothing to wire them to. The only line in the project that plays a montage
is SaudAttackAbility.cpp:85, on the ability path -- and nothing in C++ ever
calls PressInput, so that path never runs. The bosses strike through
AFighterBase::StartAttack (EnemyFighter.cpp:169, FightStyleComponent.cpp:297),
which fires a sound and a Blueprint event and then advances a float in Tick;
it plays no animation of any kind. On top of that Attack->Montage is a
per-ATTACK pointer (SaudTypes.h:147) and a boss's jab is not Saud's jab, so
one pointer could not name both. Making that seam is an engine job on a
project that has never been compiled. The clips and a manifest are written;
what would read them is left alone and named here instead.
"""
import sys, os, csv, math, json, time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(PROJECT, "Content", "Data")
FPS = 30


# ============================================================ the browser's
# attackPose(), index.html:1347, read off the source and quoted here.
#
#   lean     radians the torso leans forward. The browser's base is 0.06 and
#            each move adds to it; these are the ADDED part, so the sign is
#            the move's own contribution. Negative leans back, which is what
#            a kick does.
#   hip      the browser's p.hipY, in ITS pixels, negative meaning the hip
#            rises. 1 px is 2.4 cm everywhere in this project.
#   shift    p.shift, the body carrying forward into the strike, same pixels.
#   turns    p.spin as a fraction of a full revolution; only the spin kick
#            has one (t * 6.2832 * 1.15).
#   limb     which of the four limbs throws. STRIKE_LIMB, index.html:1383.
#
# `lead` is the left side and `rear` the right: GUARD in build_saud.py puts
# thigh_l forward (y -0.42, and -Y is the way he faces), which is orthodox.
MOVES = {
    #          lean    hip   shift  turns  limb
    "Jab":     (+0.10,   0,     9,   0.0, "lead_arm"),
    "Cross":   (+0.16,   0,    14,   0.0, "rear_arm"),
    "Hook":    (+0.22,   0,    12,   0.0, "rear_arm"),
    "Kick":    (-0.42,  -7,     0,   0.0, "rear_leg"),
    "Knee":    (+0.24, -10,     0,   0.0, "rear_leg"),
    # The browser spins 1.15 turns (t * 6.2832 * 1.15). In a flat side view
    # that reads as "more than all the way round" and the sprite is redrawn
    # from `facing` the moment the attack ends, so the 0.15 costs nothing.
    # In three dimensions it costs everything: the clip would finish with him
    # 54 degrees off his opponent. It turns exactly once here, which is what
    # a spinning back kick does anyway, and the departure is deliberate.
    "Special": (-0.30, -14,     0,  1.00, "rear_leg"),
}

PX = 0.024          # one browser pixel, in metres. The project's constant.

# drawFighter, index.html:1517-1520: the hip sits at -62 and the shoulder at
# -106, so the torso is 44 px, and the shoulder is carried forward by
#     shX = p.shift + lean * 22
# Both of those move the SHOULDER, not the feet -- the browser draws the legs
# from the hip at a fixed x. Mapping `shift` to the root instead, as the
# first version of this did, walks the whole man forward 34 cm on a cross,
# feet and all, which is a lunge and not a punch.
TORSO_PX = 44.0
LEAN_PX = 22.0
BASE_LEAN = 0.06    # P_GUARD.lean, index.html:1345
# index.html:1515, verbatim:  Math.sin(t*2.4)*1.1  -- standing. (Moving it
# is sin(t*11)*2.2, which is a walk cycle and not what a guard clip is.)
IDLE_RATE = 2.4
IDLE_PX = 1.1
IDLE_SECONDS = 2.0 * math.pi / IDLE_RATE


def inclination(move):
    """How far the torso tips into a strike, in radians, from the browser's
    own shoulder offset. One number replaces its `lean` and `shift`, because
    in the browser they are one number by the time they are drawn."""
    lean, _hip, shift, _turns, _limb = MOVES[move]
    return math.atan2(shift + (BASE_LEAN + lean) * LEAN_PX, TORSO_PX) - \
        math.atan2(BASE_LEAN * LEAN_PX, TORSO_PX)


# ====================================================== the strike poses
# Written the way build_saud.GUARD and KICK are: a dict of world-space aims,
# one entry per bone, read as "where does this limb point". Each is the pose
# at full extension; the clip blends GUARD -> here -> GUARD on the browser's
# own curve. Saud faces -Y, +X is his left, Z is up.
#
# TWIST is the one thing an aim cannot say. Aiming a bone leaves its roll to
# to_track_quat, so a torso cannot be rotated about its own length -- and a
# cross with no hip in it is a cartoon. Each entry is extra radians about the
# bone's own axis, positive turning his left shoulder forward.

SUPPORT_FOOT = (0.05, -0.55, -0.83)     # heel up, weight over the ball


def _strikes():
    import build_saud as L
    G = L.GUARD

    def over(**kw):
        d = dict(G); d.update(kw); return d

    S = {}

    # ---- lead hand, straight, almost no body behind it
    S["Jab"] = (over(
        clavicle_l=(0.84, -0.52, 0.14),
        upperarm_l=(0.20, -0.95, -0.24),
        lowerarm_l=(0.08, -0.99, -0.06),
        hand_l=(0.04, -1.00, -0.02),
        upperarm_r=(-0.14, -0.12, -0.98),      # rear hand stays on the chin
        lowerarm_r=(0.22, -0.34, 0.91),
        spine_03=(0, -0.20, 0.98), neck_01=(0, -0.14, 0.99),
    ), {"spine_02": -0.10, "spine_03": -0.16})

    # ---- rear hand, the whole body turning into it
    S["Cross"] = (over(
        clavicle_r=(-0.80, -0.58, 0.14),
        upperarm_r=(-0.18, -0.95, -0.22),
        lowerarm_r=(-0.06, -0.99, -0.06),
        hand_r=(-0.03, -1.00, -0.02),
        upperarm_l=(0.26, -0.06, -0.96),       # lead hand comes back to guard
        lowerarm_l=(-0.30, -0.28, 0.91),
        thigh_r=(-0.22, 0.10, -0.97),          # rear heel turns over
        calf_r=(-0.04, -0.06, -1.00),
        foot_r=(0.34, -0.80, -0.50),
        spine_03=(0, -0.22, 0.97), neck_01=(0, -0.12, 0.99),
    ), {"pelvis": 0.26, "spine_01": 0.22, "spine_02": 0.26, "spine_03": 0.30})

    # ---- rear hand again, but round instead of through
    S["Hook"] = (over(
        clavicle_r=(-0.72, -0.60, 0.34),
        upperarm_r=(-0.74, -0.66, -0.12),      # elbow out, level with the fist
        lowerarm_r=(0.16, -0.98, 0.10),
        hand_r=(0.30, -0.95, 0.06),
        upperarm_l=(0.28, -0.04, -0.96),
        lowerarm_l=(-0.34, -0.26, 0.90),
        thigh_r=(-0.24, 0.08, -0.97),
        foot_r=(0.40, -0.76, -0.51),
        spine_03=(0.10, -0.22, 0.97),
    ), {"pelvis": 0.34, "spine_01": 0.30, "spine_02": 0.36, "spine_03": 0.42})

    # ---- the round kick build_saud already had, kept verbatim
    # The support foot pivots onto its ball, heel up, which is what a kicker
    # does and which is also the only honest way the hip gets any height: the
    # legs cannot be longer than straight, so a flat-footed support leg buys
    # 4.8 cm and this buys 10.2. The browser cheats it by lifting hipY and
    # drawing the feet from the hip; a skeleton has to earn it.
    S["Kick"] = (dict(L.KICK, foot_l=SUPPORT_FOOT),
                 {"pelvis": 0.30, "spine_01": 0.26, "spine_02": 0.22})

    # ---- rear knee, straight up the middle, both hands pulling down
    S["Knee"] = (over(
        thigh_r=(-0.16, -0.86, 0.48),
        calf_r=(-0.10, -0.12, -0.99),
        foot_r=(-0.06, -0.40, -0.91),
        thigh_l=(0.10, 0.04, -0.99),           # support leg straightens
        calf_l=(0.02, -0.02, -1.00),
        foot_l=SUPPORT_FOOT,
        upperarm_l=(0.34, -0.50, -0.79),       # hands pull the head down
        lowerarm_l=(0.10, -0.80, -0.59),
        upperarm_r=(-0.34, -0.50, -0.79),
        lowerarm_r=(-0.10, -0.80, -0.59),
        spine_02=(0, -0.30, 0.95), spine_03=(0, -0.34, 0.94),
        neck_01=(0, -0.24, 0.97),
    ), {})

    # ---- the spinning kick. The turn itself is carried by the root, below.
    S["Special"] = (over(
        thigh_r=(-0.52, -0.80, 0.30),
        calf_r=(-0.28, -0.94, 0.20),
        foot_r=(-0.20, -0.96, 0.18),
        thigh_l=(0.08, 0.16, -0.98),
        calf_l=(0.02, 0.00, -1.00),
        foot_l=SUPPORT_FOOT,
        upperarm_l=(0.62, -0.42, -0.66),       # arms in, the way a turn needs
        lowerarm_l=(0.20, -0.56, 0.80),
        upperarm_r=(-0.70, 0.30, -0.65),
        lowerarm_r=(-0.24, -0.40, 0.88),
        spine_02=(0.16, -0.16, 0.97), spine_03=(0.10, -0.10, 0.99),
    ), {"pelvis": 0.20})

    # ---- and the one that is not a strike: what he does between them
    S["Guard"] = (dict(G), {})
    return S


# ================================================================ the bosses
# Everything here is read from DT_Fighters.csv at run time except the reading
# of the canon, which is a sentence each and is what the amplitude and the
# stance are FOR. `amp` scales how far a strike travels past the guard: a man
# half again the size does not throw a tidier punch, he throws a bigger one.
BOSSES = {
    "Boss": dict(kind="boss", canon=(
        "What staying looks like when you are very good at it. The complete "
        "fighter: hands and legs, and the most power in the game.")),
    "Saqr": dict(kind="saqr", canon=(
        "All legs, no patience. He fell too, years back, and gave up asking "
        "about it -- which is where the impatience comes from.")),
    "Zayos": dict(kind="zayos", canon=(
        "A boxing monster: gloves, a body half again the size of any man in "
        "the Halqa, long arms, slow. He only ever punches.")),
}

ENEMIES = os.path.abspath(os.path.join(PROJECT, "..", "saud-fighter", "assets", "enemies.js"))


def browser_build(kind):
    """`sc` and `look.build` for one archetype, out of the browser's roster.

    They are read from there and not written here because the UE5 export
    DROPS them: DT_Fighters.csv carries health, power, speed, range, interval,
    guard and the move list, and no column for how big the man is. All three
    bosses ride Saud's one rig at Saud's proportions, so ZAYOS being "half
    again the size" is actor scale in the engine -- but it is still the only
    number that says his strike should travel further past the guard than
    AL-SAQR's, so it comes from the source of truth rather than from a
    constant typed in here.
    """
    import re
    src = open(ENEMIES, encoding="utf-8").read()
    m = re.search(r"^\s*%s\s*:\s*\{" % kind, src, re.M)
    assert m, "no %s in %s" % (kind, ENEMIES)
    # brace-count to the end of the entry: `col:{...}` and `look:{...}` are
    # nested inside it, so a non-greedy match stops at the first of them.
    i = src.index("{", m.start())
    depth, j = 0, i
    while j < len(src):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    body = src[i:j + 1]
    sc = re.search(r"\bsc\s*:\s*([0-9.]+)", body)
    bd = re.search(r"\bbuild\s*:\s*([0-9.]+)", body)
    assert sc and bd, "%s has no sc/build in %s" % (kind, ENEMIES)
    return float(sc.group(1)), float(bd.group(1))


def character(kind):
    """How big he is, turned into how he throws.

    Amplitude is how far past the guard a strike goes and stance is how wide
    he stands. A third of the size difference, not all of it: the rig is the
    same rig, so the limbs are the same length, and what a bigger man
    actually does differently is commit further -- he does not grow an arm.
    """
    sc, build = browser_build(kind)
    return dict(sc=sc, build=build,
                amp=1.0 + (sc - 1.0) * 0.32,
                stance=1.0 + (build - 1.0) * 0.26,
                settle=0.04 + (sc - 1.0) * 0.26)

# Phase two. At half health the browser turns two of the three ENRAGED --
# index.html:3553, `isBoss = (e.kind === 'boss' || e.kind === 'saqr')`, so
# ZAYOS is deliberately not in it -- and gives them `special` plus spd x1.20
# and rate x0.70. The clip that changes is the one that appears: the spin
# kick. The speed-up is an interval between strikes, not a faster strike, so
# it changes no clip's length.
PHASE_TWO = ("Boss", "Saqr")


# ===================================================================== data
def read_csv(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def parse_moves(cell):
    """The Moves column is an Unreal array literal: ("Jab","Cross")."""
    return [p.strip().strip('"') for p in cell.strip('()').split(",") if p.strip()]


BROWSER = os.path.abspath(os.path.join(PROJECT, "..", "saud-fighter", "index.html"))


def browser_phase_two():
    """Which fighters the browser turns ENRAGED at half health, read out of
    the browser itself. It is the source of truth for every number in this
    project, and a constant copied out of it is a constant that goes stale
    quietly -- so this parses the line rather than trusting the copy."""
    import re
    with open(BROWSER, encoding="utf-8") as fh:
        for line in fh:
            if "isBoss" in line and "e.kind" in line:
                kinds = re.findall(r"e\.kind\s*===\s*'([a-z]+)'", line)
                return {k.capitalize() for k in kinds}
    raise AssertionError("the browser's isBoss line is gone from %s" % BROWSER)


def plan():
    """Every clip that should exist, and what decides it. Reads the tables;
    invents nothing."""
    attacks = {r["Name"]: r for r in read_csv("DT_Attacks.csv")}
    fighters = {r["Name"]: r for r in read_csv("DT_Fighters.csv")}
    clips = []
    for key, meta in BOSSES.items():
        who = character(meta["kind"])
        row = fighters[key]
        moves = parse_moves(row["Moves"])
        if key in PHASE_TWO and "Special" not in moves:
            moves = moves + ["Special"]
        seen = []
        for mv in moves:
            if mv in seen:              # Zayos throws hook twice; one clip
                continue
            seen.append(mv)
            a = attacks[mv]
            su, ac, rc = float(a["Startup"]), float(a["Active"]), float(a["Recovery"])
            clips.append(dict(
                boss=key, display=row["DisplayName"], arabic=row["DisplayNameArabic"],
                move=mv, su=su, ac=ac, rc=rc, seconds=su + ac + rc,
                frames=max(2, int(round((su + ac + rc) * FPS))),
                contact=int(round(su * FPS)),
                limb=MOVES[mv][4], phase_two=(mv == "Special"),
                amp=who["amp"], stance=who["stance"], settle=who["settle"],
                speed=float(row["MoveSpeed"]), interval=float(row["AttackInterval"]),
                name="A_%s_%s" % (key, mv)))
        # What he does when he is not throwing anything. The browser bobs a
        # standing fighter at Math.sin(f.anim * 2.4) * 1.1 (index.html:1515)
        # and that 2.4 is a constant -- every fighter in the game breathes at
        # the same rate whatever his speed. Three different cycle lengths
        # here, one per boss, was a number with no source behind it.
        cyc = IDLE_SECONDS
        clips.append(dict(boss=key, display=row["DisplayName"], arabic=row["DisplayNameArabic"],
                          move="Guard", su=0.0, ac=0.0, rc=0.0, seconds=cyc,
                          frames=int(round(cyc * FPS)), contact=-1, limb=None,
                          phase_two=False, amp=who["amp"], stance=who["stance"],
                          settle=who["settle"], speed=float(row["MoveSpeed"]),
                          interval=float(row["AttackInterval"]),
                          name="A_%s_Guard" % key, loop=True))
    return clips


def check(clips):
    """The things that would be wrong and that a render would not tell you.
    Each of these has been made to fail by breaking what it guards."""
    attacks = {r["Name"]: r for r in read_csv("DT_Attacks.csv")}
    fighters = {r["Name"]: r for r in read_csv("DT_Fighters.csv")}

    # 1. every boss in the table that is a boss has clips here
    table_bosses = {r["Name"] for r in fighters.values() if r["bIsBoss"] == "true"}
    assert table_bosses == set(BOSSES), (
        "DT_Fighters marks %s as bosses; this builds %s" % (sorted(table_bosses), sorted(BOSSES)))

    # 2. every move a boss throws has a clip, and nothing else does
    for key in BOSSES:
        want = set(parse_moves(fighters[key]["Moves"]))
        if key in PHASE_TWO:
            want.add("Special")
        got = {c["move"] for c in clips if c["boss"] == key and c["move"] != "Guard"}
        assert want == got, "%s throws %s but has clips for %s" % (key, sorted(want), sorted(got))

    # 3. a clip is exactly as long as the attack table says, to within a frame
    for c in clips:
        if c["move"] == "Guard":
            continue
        a = attacks[c["move"]]
        want = float(a["Startup"]) + float(a["Active"]) + float(a["Recovery"])
        assert abs(c["seconds"] - want) < 1e-9, "%s is %.3fs against the table's %.3f" % (c["name"], c["seconds"], want)
        assert abs(c["frames"] / float(FPS) - want) <= 1.0 / FPS, (
            "%s rounds to %d frames, which is %.3fs off %.3f" % (c["name"], c["frames"], c["frames"] / float(FPS), want))

    # 4. the contact frame is inside the clip and is where startup ends
    for c in clips:
        if c["contact"] < 0:
            continue
        assert 0 <= c["contact"] < c["frames"], "%s contacts at frame %d of %d" % (c["name"], c["contact"], c["frames"])
        assert abs(c["contact"] / float(FPS) - c["su"]) <= 1.0 / FPS, (
            "%s contacts at %.3fs, startup ends at %.3f" % (c["name"], c["contact"] / float(FPS), c["su"]))

    # 5. the canon: ZAYOS only ever punches. If a leg clip ever appears for
    #    him, either the roster changed or somebody stopped reading.
    for c in clips:
        if c["boss"] == "Zayos":
            assert c["limb"] in (None, "lead_arm", "rear_arm"), (
                "ZAYOS has a %s clip (%s), and the canon says he only ever punches" % (c["limb"], c["name"]))

    # 6. Phase two is whoever the BROWSER enrages, read off the browser --
    #    not off PHASE_TWO above, which is a copy and which a check that
    #    compares the plan to it can never catch being wrong. The line is
    #    `var isBoss = (e.kind === 'boss' || e.kind === 'saqr');`
    assert set(PHASE_TWO) == browser_phase_two(), (
        "the browser enrages %s; PHASE_TWO says %s" % (sorted(browser_phase_two()), sorted(PHASE_TWO)))
    got2 = {c["boss"] for c in clips if c["phase_two"]}
    assert got2 == set(PHASE_TWO), "phase two clips for %s, expected %s" % (sorted(got2), sorted(PHASE_TWO))

    # 7. no two clips share a name
    names = [c["name"] for c in clips]
    assert len(names) == len(set(names)), "duplicate clip names: %s" % sorted(
        n for n in set(names) if names.count(n) > 1)
    return True


def describe(clips):
    print("BOSS MOTION -- %d clips on the shared 62-bone skeleton\n" % len(clips))
    for key, meta in BOSSES.items():
        who = character(meta["kind"])
        mine = [c for c in clips if c["boss"] == key]
        d = mine[0]
        print("%s / %s  %s" % (d["display"], d["arabic"], "(phase two: special)" if key in PHASE_TWO else ""))
        print("   %s" % meta["canon"])
        print("   sc %.2f build %.2f -> amplitude x%.2f  stance x%.2f   speed %.0f  interval %.2fs" % (
            who["sc"], who["build"], who["amp"], who["stance"], d["speed"], d["interval"]))
        for c in mine:
            if c["move"] == "Guard":
                print("      %-18s %5.2fs %3d frames  loop" % (c["name"], c["seconds"], c["frames"]))
            else:
                print("      %-18s %5.2fs %3d frames  contact on %2d  (%.2f/%.2f/%.2f)  %s" % (
                    c["name"], c["seconds"], c["frames"], c["contact"], c["su"], c["ac"], c["rc"], c["limb"]))
        print()
    total = sum(c["frames"] for c in clips)
    print("%d frames at %d fps -- %.1f seconds of motion" % (total, FPS, total / float(FPS)))


# ================================================================== the build
def ease(t):
    """The browser's own ease, index.html:111 -- easeInOutQuad, verbatim:

        t < .5 ? 2*t*t : 1 - Math.pow(-2*t + 2, 2) / 2

    Not smoothstep, which the first version of this used and which is a
    different curve: they part company by three points of travel at the
    quarters. The strike ramps in over startup on this, holds flat through
    the active window and falls back over recovery, and copying it exactly
    is the reason a clip lands where the hitbox does."""
    t = max(0.0, min(1.0, t))
    return 2.0 * t * t if t < 0.5 else 1.0 - ((-2.0 * t + 2.0) ** 2) / 2.0


def blend_k(t, su, ac, rc):
    """index.html:1495-1500, verbatim in shape."""
    if t < su:
        return ease(t / su) if su > 0 else 1.0
    if t < su + ac:
        return 1.0
    return 1.0 - ease(min(1.0, max(0.0, (t - su - ac) / rc))) if rc > 0 else 0.0


def slerp_aim(a, b, k):
    """Between two directions, along the sphere. A straight lerp would drag
    the limb through the middle and slow it at the ends -- visible on a hook,
    which travels 100 degrees."""
    import mathutils
    va = mathutils.Vector(a).normalized()
    vb = mathutils.Vector(b).normalized()
    d = max(-1.0, min(1.0, va.dot(vb)))
    if d > 0.9995:
        return tuple((va + (vb - va) * k).normalized())
    ang = math.acos(d)
    s = math.sin(ang)
    return tuple((va * (math.sin((1 - k) * ang) / s) + vb * (math.sin(k * ang) / s)).normalized())


# The bones whose world aim has to survive the torso moving under them.
LIMB_CHAIN = ["clavicle_l", "upperarm_l", "lowerarm_l", "hand_l",
              "clavicle_r", "upperarm_r", "lowerarm_r", "hand_r",
              "thigh_l", "calf_l", "foot_l", "thigh_r", "calf_r", "foot_r"]


def reaim(rig, aims, names):
    """Put the named bones back on their world aims, parents first. Same
    thing build_saud.pose() does, applied again after the torso has been
    rotated out from under them."""
    import bpy, mathutils
    for name in names:
        if name not in aims or name not in rig.pose.bones:
            continue
        pbone = rig.pose.bones[name]
        aim = mathutils.Vector(aims[name]).normalized()
        m = aim.to_track_quat("Y", "Z").to_matrix().to_4x4()
        m.translation = pbone.matrix.translation
        pbone.matrix = m
        bpy.context.view_layer.update()


def build(clips, out_dir, sheet=False):
    import bpy, mathutils
    sys.path.insert(0, HERE)
    import build_saud as L
    from hero import anatomy as A, rig_export as R

    t0 = time.time()
    L.reset_scene()
    _, jl = A.hand()
    rig = L.build_armature()
    R.add_finger_bones(rig, jl)
    L.add_ik(rig)
    # FK all the way. The solver is for posing a still; an exported clip wants
    # the curves the engine will actually read.
    L.mute_ik(rig, True)
    print("%6.1fs  rig: %d bones" % (time.time() - t0, len(rig.data.bones)))

    S = _strikes()
    guard, _ = S["Guard"]
    os.makedirs(out_dir, exist_ok=True)
    made = []

    for c in clips:
        strike, twist = S[c["move"]]
        lean, hip, shift, turns, _limb = MOVES.get(c["move"], (0, 0, 0, 0.0, None))
        tip = inclination(c["move"]) if c["move"] in MOVES else 0.0
        act = bpy.data.actions.new(c["name"])
        rig.animation_data_create()
        rig.animation_data.action = act

        ground = None
        for f in range(c["frames"]):
            t = f / float(FPS)
            if c["move"] == "Guard":
                # Not a strike: he breathes, and he shifts his weight. The
                # browser bobs at sin(t*2.4)*1.1 px standing -- that rate and
                # that amplitude, in metres.
                k = 0.0
                ph = 2.0 * math.pi * t / c["seconds"]
                bob = math.sin(ph) * IDLE_PX * PX
                sway = math.sin(ph * 0.5) * 0.9 * PX
            else:
                k = blend_k(t, c["su"], c["ac"], c["rc"]) * c["amp"]
                bob = 0.0
                sway = 0.0

            aims = {}
            for name, g in guard.items():
                s = strike.get(name, g)
                aims[name] = slerp_aim(g, s, k) if s != g else g
            # the stance, which is the boss's own width and not the move's
            for side, sgn in (("_l", 1.0), ("_r", -1.0)):
                for base in ("thigh", "calf"):
                    nm = base + side
                    if nm in aims and c["stance"] != 1.0:
                        v = mathutils.Vector(aims[nm])
                        v.x *= c["stance"]
                        aims[nm] = tuple(v.normalized())

            L.pose(rig, aims)
            if ground is None:      # the height the guard stands at
                bpy.context.view_layer.update()
                ground = min((rig.matrix_world @ rig.pose.bones[b].matrix).translation.z
                             for b in ("ball_l", "ball_r"))

            # ---- the torso, from the browser's own lean / hip / shift
            bpy.context.view_layer.objects.active = rig
            bpy.ops.object.mode_set(mode="POSE")
            pb = rig.pose.bones
            if k or bob or sway:
                # A spine bone's local X runs along world +X, and a positive
                # turn about it carries the chest FORWARD -- checked, +0.5
                # rad carries the head 34 cm ahead of him. Not negated: that
                # was the sign for a spine still carrying the twist _aim()
                # put on every torso bone before it was fixed (see
                # rig_full_ik.py's _aim and CLAUDE.md); on the untwisted
                # frame pose() builds now, the old minus sign leaned a jab
                # 36 cm AWAY from the man it is aimed at. The browser's lean
                # is positive forward, and so is this one now.
                for nm, share in (("spine_01", 0.30), ("spine_02", 0.36), ("spine_03", 0.34)):
                    q = mathutils.Quaternion((1, 0, 0), tip * k * share)
                    pb[nm].rotation_quaternion = pb[nm].rotation_quaternion @ q
                for nm, amt in twist.items():
                    q = mathutils.Quaternion((0, 1, 0), amt * k)
                    pb[nm].rotation_quaternion = pb[nm].rotation_quaternion @ q
                bpy.context.view_layer.update()
                # An aim is a WORLD direction, and the torso has just moved
                # under the arms that were aimed along it -- so a cross that
                # was pointed at the opponent is now pointed wherever the
                # shoulder carried it. Measured: the twist alone cost the
                # cross 24 cm of reach and turned the hook backwards. The
                # limbs are re-aimed on top of the moved torso, which is what
                # a real cross is: the hips turn, the fist still goes there.
                reaim(rig, aims, LIMB_CHAIN)

            # The root bone points UP: its local Y is world +Z and its local
            # Z is world -Y, which is forward. Writing the forward shift into
            # .y drives him into the floor, which is what it did.
            # The root carries only the breathing and the sway. The hip's
            # rise off a kick is NOT written here: the browser lifts hipY and
            # draws the legs from the hip, so its feet come up with it, which
            # is a flat drawing's cheat. Done here it levitated him -- the
            # support foot left the ground by 12 cm on a round kick and 30 on
            # the spinning one. Instead the lowest foot is PLANTED: the root
            # is offset by however much it takes to keep it at the height it
            # stands at in the guard, and the hip rise is then whatever the
            # leg geometry really implies rather than a number imposed on it.
            pb["root"].location = (sway, bob, 0.0)
            bpy.context.view_layer.update()
            low = min((rig.matrix_world @ pb[b].matrix).translation.z
                      for b in ("ball_l", "ball_r"))
            pb["root"].location = (sway, bob + (ground - low), 0.0)
            if turns:
                pb["root"].rotation_quaternion = mathutils.Quaternion(
                    (0, 1, 0), turns * 2.0 * math.pi * (t / c["seconds"]))

            for b in rig.pose.bones:
                b.keyframe_insert("rotation_quaternion", frame=f + 1)
            pb["root"].keyframe_insert("location", frame=f + 1)
            bpy.ops.object.mode_set(mode="OBJECT")

        # a loop has to close: the last frame is the first
        made.append((c, act))
        rig.animation_data.action = None

    print("%6.1fs  authored %d clips" % (time.time() - t0, len(made)))
    verify(rig, made)

    # ---- export, one FBX a clip, armature only: UE5 imports animation onto
    # a skeleton it already has, and the mesh is Saud's and already there.
    for c, act in made:
        rig.animation_data.action = act
        bpy.context.scene.frame_start = 1
        bpy.context.scene.frame_end = c["frames"]
        bpy.ops.object.select_all(action="DESELECT")
        rig.select_set(True)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.export_scene.fbx(
            filepath=os.path.join(out_dir, c["name"] + ".fbx"),
            use_selection=True, object_types={"ARMATURE"}, add_leaf_bones=False,
            bake_anim=True, bake_anim_use_all_actions=False,
            bake_anim_use_nla_strips=False, bake_anim_step=1.0,
            primary_bone_axis="Y", secondary_bone_axis="X",
            apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS")
        rig.animation_data.action = None

    manifest = os.path.join(out_dir, "DT_BossMotion.csv")
    with open(manifest, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Name", "Fighter", "Attack", "File", "Seconds", "Frames",
                    "ContactFrame", "Limb", "bLoop", "bPhaseTwo"])
        for c, _ in made:
            w.writerow([c["name"], c["boss"], "" if c["move"] == "Guard" else c["move"],
                        c["name"] + ".fbx", "%.3f" % c["seconds"], c["frames"],
                        c["contact"], c["limb"] or "", str(c.get("loop", False)).lower(),
                        str(c["phase_two"]).lower()])
    print("%6.1fs  exported %d fbx + %s" % (time.time() - t0, len(made), os.path.basename(manifest)))

    if sheet:
        contact_sheet(rig, made, out_dir)
    return made


TIP = {"lead_arm": "hand_end_l", "rear_arm": "hand_end_r", "rear_leg": "ball_r"}


def verify(rig, made):
    """Does the strike strike?

    A clip can have the right length, the right contact frame and the right
    name and still be a man standing still, and none of the checks above
    would know. This one puts the fist or the foot where the frame says it
    is and measures how far forward of the guard it got. It is not
    decoration: it caught the root bone's axes being wrong -- the root points
    UP, so the forward shift was being written into the vertical and was
    driving him into the floor -- and it caught the torso twist dragging the
    already-aimed arm off target, which turned the hook 10 cm BACKWARDS.
    """
    import bpy, mathutils
    fails = []
    for c, act in made:
        if not c["limb"]:
            continue
        rig.animation_data.action = act
        tip = TIP[c["limb"]]

        def at(frame, bone):
            bpy.context.scene.frame_set(frame)
            bpy.context.view_layer.update()
            return (rig.matrix_world @ rig.pose.bones[bone].matrix).translation.copy()

        guard = at(1, tip)
        contact = at(c["contact"] + 1, tip)
        end = at(c["frames"], tip)
        hip_g = at(1, "pelvis")
        hip_c = at(c["contact"] + 1, "pelvis")
        reach = (guard.y - contact.y) * 100.0       # forward is -Y
        rise = (hip_c.z - hip_g.z) * 100.0
        settle = (end - guard).length * 100.0
        c["reach_cm"], c["rise_cm"], c["settle_cm"] = reach, rise, settle
        # A strike has to travel. 12 cm is not a demanding bar -- it is the
        # bar that separates "he threw it" from "he thought about it".
        if reach < 12.0:
            fails.append("%s reaches only %.1f cm" % (c["name"], reach))
        # and it has to come back, or the next one starts from nowhere
        if settle > 22.0:
            fails.append("%s ends %.1f cm from its own guard" % (c["name"], settle))
        # he does not levitate. The browser can lift a hip and let the feet
        # follow because it is a drawing; a skeleton cannot.
        for f in (1, c["contact"] + 1, c["frames"]):
            lowest = min(at(f, "ball_l").z, at(f, "ball_r").z)
            if lowest > 0.045:
                fails.append("%s has both feet %.0f cm off the ground on frame %d"
                             % (c["name"], lowest * 100, f))
        # a knee and a kick lift the hip; a punch does not. 8 cm, unchanged:
        # the support foot pivoting onto its ball buys the rise back honestly
        # -- it measures 9.9 to 10.7 cm and 3.0 to 3.7 with the foot left
        # flat -- so nothing here had to be relaxed to accommodate planting
        # the feet, and relaxing it would only have hidden the next
        # regression.
        if c["limb"] == "rear_leg" and rise < 8.0:
            fails.append("%s is a leg strike that lifts the hip %.1f cm" % (c["name"], rise))
        # and he leans the way the browser says he leans. A spine bone's
        # local X runs along world +X, so the obvious sign is the wrong one
        # and a jab ends up leaning away from the man it is aimed at.
        lean = inclination(c["move"])
        if abs(lean) > 0.04:
            head_g = at(1, "head")
            head_c = at(c["contact"] + 1, "head")
            went = (head_g.y - head_c.y) * 100.0        # + is forward
            c["lean_cm"] = went
            if lean > 0 and went < 2.0:
                fails.append("%s should lean in and the head went %.1f cm" % (c["name"], went))
            if lean < 0 and went > -2.0:
                fails.append("%s should lean away and the head went %.1f cm" % (c["name"], went))
    rig.animation_data.action = None
    assert not fails, "the motion does not move:\n  " + "\n  ".join(fails)
    worst = min(c["reach_cm"] for c, _ in made if c["limb"])
    print("        every strike travels; the shortest reaches %.0f cm" % worst)


# The bones worth drawing: the figure, not the fingers.
# The deform skeleton is the mannequin's: there is no head_end, no jaw and
# none of the shaping joints -- those live in the joint table but never
# became bones. `head` is the top of the chain and is drawn as its own
# segment, head to tail.
FIGURE = [("pelvis", "spine_01"), ("spine_01", "spine_02"), ("spine_02", "spine_03"),
          ("spine_03", "neck_01"), ("neck_01", "head"),
          ("spine_03", "clavicle_l"), ("clavicle_l", "upperarm_l"),
          ("upperarm_l", "lowerarm_l"), ("lowerarm_l", "hand_l"), ("hand_l", "hand_end_l"),
          ("spine_03", "clavicle_r"), ("clavicle_r", "upperarm_r"),
          ("upperarm_r", "lowerarm_r"), ("lowerarm_r", "hand_r"), ("hand_r", "hand_end_r"),
          ("pelvis", "thigh_l"), ("thigh_l", "calf_l"), ("calf_l", "foot_l"), ("foot_l", "ball_l"),
          ("pelvis", "thigh_r"), ("thigh_r", "calf_r"), ("calf_r", "foot_r"), ("foot_r", "ball_r")]
TERMINAL = ("hand_end_l", "hand_end_r", "ball_l", "ball_r")


def contact_sheet(rig, made, out_dir):
    """A strip per clip, drawn as the skeleton itself.

    An armature does not render, and binding a mesh to judge timing is a
    ten-minute build for something an animator would not look at anyway: you
    read a strike off the rig. Each row is one clip sampled across its whole
    length, seen from his right side -- the view the browser draws him in --
    with the contact frame marked and the striking limb picked out.
    """
    import bpy
    from PIL import Image, ImageDraw
    SH, SW, PAD = 190, 118, 4
    SAMPLES = 9

    def joints(frame):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        out = {}
        for b in rig.pose.bones:
            m = rig.matrix_world @ b.matrix
            out[b.name] = (m.translation.copy(), (m @ __import__("mathutils").Vector((0, b.length, 0))))
        return out

    rows = []
    for c, act in made:
        rig.animation_data.action = act
        cells = []
        for i in range(SAMPLES):
            f = 1 + int(round(i * (c["frames"] - 1) / float(SAMPLES - 1)))
            J = joints(f)
            im = Image.new("RGB", (SW, SH), (14, 16, 22))
            d = ImageDraw.Draw(im)
            # side view: y forward (to the left of frame), z up
            # Three-quarters, not side-on. A pure side view cannot tell a
            # bent torso from a shoulder line turned edge-on, and it fooled
            # me into reading the round kick's counter-rotating arm as a man
            # folded in half. At 35 degrees both read.
            base = J["pelvis"][0]
            ca, sa = math.cos(math.radians(35.0)), math.sin(math.radians(35.0))
            def px(v):
                u = (v.x - base.x) * sa - (v.y - base.y) * ca
                return (SW * 0.5 + u * 150.0, SH - 16 - v.z * 92.0)
            lit = {"lead_arm": ("upperarm_l", "lowerarm_l", "hand_l"),
                   "rear_arm": ("upperarm_r", "lowerarm_r", "hand_r"),
                   "rear_leg": ("thigh_r", "calf_r", "foot_r")}.get(c["limb"], ())
            d.line([(0, SH - 16), (SW, SH - 16)], fill=(34, 38, 50))
            for a, b in FIGURE:
                if a not in J or b not in J:
                    continue
                col = (232, 186, 88) if a in lit else (150, 158, 178)
                w = 3 if a in lit else 2
                d.line([px(J[a][0]), px(J[b][0])], fill=col, width=w)
            if "head" in J:                      # the skull, drawn at its tail
                x, y = px(J["head"][1])
                d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(206, 212, 228))
            for nm in TERMINAL:
                if nm in J:
                    x, y = px(J[nm][0])
                    d.ellipse([x - 3.5, y - 3.5, x + 3.5, y + 3.5], fill=(206, 212, 228))
            if f == c["contact"] + 1 and c["contact"] >= 0:
                d.rectangle([0, 0, SW - 1, SH - 1], outline=(232, 74, 92), width=2)
                d.text((5, 4), "contact", fill=(232, 74, 92))
            else:
                d.text((5, 4), "%d" % f, fill=(96, 104, 124))
            cells.append(im)
        rows.append((c, cells))

    W = PAD + SAMPLES * (SW + PAD)
    H = PAD + len(rows) * (SH + 20 + PAD)
    sheet = Image.new("RGB", (W, H), (9, 10, 14))
    dd = ImageDraw.Draw(sheet)
    for r, (c, cells) in enumerate(rows):
        y = PAD + r * (SH + 20 + PAD)
        label = "%s  %s  %.2fs  %d frames" % (c["name"], c["display"], c["seconds"], c["frames"])
        if c.get("reach_cm") is not None and c["limb"]:
            label += "   reach %.0f cm" % c["reach_cm"]
        dd.text((PAD + 2, y + 4), label, fill=(226, 228, 236))
        for i, im in enumerate(cells):
            sheet.paste(im, (PAD + i * (SW + PAD), y + 18))
    out = os.path.join(out_dir, "boss-motion.png")
    sheet.save(out)
    rig.animation_data.action = None
    print("        contact sheet %s (%dx%d)" % (os.path.basename(out), W, H))
    return out


# ======================================================================= main
def main():
    argv = sys.argv[1:]
    out = os.path.join(PROJECT, "Content", "Animation", "Bosses")
    if "--out" in argv:
        out = os.path.abspath(argv[argv.index("--out") + 1])

    clips = plan()
    check(clips)
    if "--check" in argv:
        print("checks pass: %d clips" % len(clips))
        return
    describe(clips)
    if "--describe" in argv:
        return
    build(clips, out, sheet="--sheet" in argv)


if __name__ == "__main__":
    main()
