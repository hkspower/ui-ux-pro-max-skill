#!/usr/bin/env python3
"""Motion for Saud, the street men and the three bosses -- AL-WAHSH, AL-SAQR and ZAYOS.

    python3 build_motion.py              plan, check, describe, build, export
    python3 build_motion.py --who saud   only Saud (or --who bosses, --who street)
    python3 build_motion.py --check      the assertions only, no Blender work
    python3 build_motion.py --describe   what it would make, and why
    python3 build_motion.py --sheet      render a contact sheet of every clip
    python3 build_motion.py --bite       break each motion check's mechanism
                                         and prove the check notices
    python3 build_motion.py --out DIR    write somewhere else than the project

HOW IT IS POSED, since 2026-09-23: through the control rig, not bone by bone.
motion_ik.py strikes each frame's shape in FK exactly as this file always
did, then hands every limb to rig_full_ik's controls -- planted feet stay
where the guard put them, a jab and a cross travel a straight line, the
spinning kick turns on the ball of the support foot -- and bakes the result
onto the 62 bones. Posed in FK the feet skated: 30-35 cm on every kick and
knee, 44-54 cm on the spin, 9-13 cm under every cross and hook. See
motion_ik.py for the numbers and the method.

SAUD, since the same day. He had a rig and no motion at all. He gets every
strike his row in DT_Fighters.csv lists plus the finisher (Special), his
guard, and the states a fighter spends the rest of a fight in: walking (four
ways, because a facing is not a heading here), dashing (four ways), blocking,
taking a light and a heavy hit, going down and getting up. Their shapes are
the browser's own drawFighter (index.html:1504-1576) and their lengths are
the engine's own timers, read out of the C++ that runs them.

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
# bone's own axis, positive turning his RIGHT shoulder forward (measured on
# the clips 2026-09-26: the cross's +60 degrees brings the right shoulder
# round; the jab's negative twist the left).

SUPPORT_FOOT = (0.05, -0.55, -0.83)     # heel up, weight over the ball


def _strikes(base=None):
    import build_saud as L
    G = dict(L.GUARD if base is None else base)
    if "guard" in SABOTAGE:
        # the guard's arms as they were until 2026-09-24
        for s, x in (("l", 1.0), ("r", -1.0)):
            G["upperarm_" + s] = (0.16 * x, -0.60, -0.80)
            G["lowerarm_" + s] = (-0.20 * x, -0.05, 0.98)
            G["hand_" + s] = (-0.10 * x, -0.05, 0.99)
    if "palms" in SABOTAGE:
        for k in L.PALMS:
            G.pop(k, None)

    def over(**kw):
        d = dict(G); d.update(kw); return d

    S = {}

    # ---- lead hand, straight, almost no body behind it
    S["Jab"] = (over(
        clavicle_l=(0.84, -0.52, 0.14),
        # The punch rises to the chin: aimed 14 degrees DOWN from the shoulder
        # it landed 32 cm under the head joint, at the chest (measured on the
        # shipped clips, 2026-09-26); a straight punch at a man his own size
        # lands at the jaw, a little above the shoulder it leaves.
        upperarm_l=(0.20, -0.96, +0.12),
        lowerarm_l=(0.08, -0.99, +0.08),
        hand_l=(0.04, -1.00, +0.06),
        palm_l=(0.0, 0.0, -1.0),               # the fist turns over: palm down at the end
        # the rear hand stays where the guard has it, at the jaw -- it used
        # to be put back "on the chin" by aims of its own, which were the
        # old guard's hands-beside-the-head
        spine_03=(0, -0.20, 0.98), neck_01=(0, -0.14, 0.99),
    ), {"spine_02": -0.10, "spine_03": -0.16})

    # ---- rear hand, the whole body turning into it
    S["Cross"] = (over(
        clavicle_r=(-0.80, -0.58, 0.14),
        upperarm_r=(-0.18, -0.96, +0.12),
        lowerarm_r=(-0.06, -0.99, +0.08),
        hand_r=(-0.03, -1.00, +0.06),
        palm_r=(0.0, 0.0, -1.0),               # palm down at the end
        # the lead hand stays in the guard, covering
        thigh_r=(-0.22, 0.10, -0.97),          # rear heel turns over
        calf_r=(-0.04, -0.06, -1.00),
        foot_r=(0.34, -0.80, -0.50),
        spine_03=(0, -0.22, 0.97), neck_01=(0, -0.12, 0.99),
    ), {"pelvis": 0.26, "spine_01": 0.22, "spine_02": 0.26, "spine_03": 0.30})

    # ---- rear hand again, but round instead of through
    S["Hook"] = (over(
        clavicle_r=(-0.72, -0.60, 0.34),
        upperarm_r=(-0.74, -0.66, +0.06),      # elbow out, level with the shoulder
        lowerarm_r=(0.16, -0.97, 0.18),        # the fist a little above it, at the jaw
        hand_r=(0.30, -0.94, 0.14),
        palm_r=(0.0, 0.20, -1.0),              # a horizontal fist, palm down
        # the lead hand stays in the guard
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
    if "palms" in SABOTAGE:
        for shape, _tw in S.values():
            for k in L.PALMS:
                shape.pop(k, None)
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

# ================================================================== Saud
SAUD = dict(key="Saud", canon=(
    "The one who fell. Eighteen, and already a professional: every strike "
    "the game gives him, and every state a fight puts him in."))


def saud_character():
    """His size out of his own roster file (assets/saud.js), through the
    same mapping character() gives the bosses."""
    sys.path.insert(0, HERE)
    from hero import roster
    s = roster.spec("saud")
    sc, build = float(s["sc"]), float(s["look"].get("build", 1.0))
    return dict(sc=sc, build=build, amp=1.0 + (sc - 1.0) * 0.32,
                stance=1.0 + (build - 1.0) * 0.26, settle=0.04 + (sc - 1.0) * 0.26)


SOURCE = os.path.join(PROJECT, "Source", "SaudFighter", "Combat")


def engine_timings():
    """How long the engine holds a fighter in each state, read out of the
    C++ that holds him there -- a clip that is longer than its state is
    cut off, and one that is shorter stands still at the end. Parsed, not
    copied, for the reason browser_phase_two() parses the browser."""
    import re
    base = open(os.path.join(SOURCE, "FighterBase.cpp"), encoding="utf-8").read()
    hero = open(os.path.join(SOURCE, "SaudCharacter.cpp"), encoding="utf-8").read()
    def one(pat, src, what):
        m = re.search(pat, src)
        assert m, "the engine no longer says how long %s lasts (%s)" % (what, pat)
        return [float(g) for g in m.groups()]
    heavy, light = one(r"HitStunRemaining\s*=\s*Attack\.bHeavy\s*\?\s*([0-9.]+)f\s*:\s*([0-9.]+)f", base, "a hit")
    death, down = one(r"DownRemaining\s*=\s*Health\s*<=\s*0\.f\s*\?\s*([0-9.]+)f\s*:\s*([0-9.]+)f", base, "a knockdown")
    getup, = one(r"InvulnerableRemaining\s*=\s*([0-9.]+)f;\s*//\s*brief mercy on getting up", base, "getting up")
    leap, dash = one(r"DashRemaining\s*=\s*bLeap\s*\?\s*([0-9.]+)f\s*:\s*([0-9.]+)f", hero, "a dash")
    return dict(hit_light=light, hit_heavy=heavy, down=down, death=death, getup=getup, dash=dash, leap=leap)


# drawFighter, index.html:1515-1522: a moving fighter bobs sin(t*11)*2.2 px
# and swings his legs sin(t*11)*0.42 rad -- one cycle of both legs every
# 2*pi/11 s. That is the walk's length; the stride is then whatever the
# engine's MoveSpeed covers in it, so the planted foot is still on the
# ground it landed on while the capsule moves over it.
WALK_RATE = 11.0
WALK_BOB_PX = 2.2
# Saud faces -Y and +X is his left. A heading is not a facing here, so the
# walk and the dash are four clips each, for a blendspace.
DIRS = {"Fwd": (0.0, -1.0, 0.0), "Back": (0.0, 1.0, 0.0),
        "Left": (1.0, 0.0, 0.0), "Right": (-1.0, 0.0, 0.0)}
# index.html:1506-1507, blocking: lean 0.16 against the guard's 0.06, the
# hip 3 px lower, both arms higher and tighter than the guard's.
BLOCK_LEAN = 0.16 - BASE_LEAN
BLOCK_HIP_PX = 3.0
# index.html:1509-1511, hit: hk = clamp(hitT / 0.28) with hitT counting down
# from 0.22 or 0.34; lean 0.06 - hk*0.5, hip hk*4 px lower, both arms thrown.
HIT_SPAN = 0.28
HIT_LEAN = 0.5
HIT_HIP_PX = 4.0
# index.html:1572-1575, down: the body turns back 1.30 rad over the knock-
# down. The browser also slides the drawing 30 px back, a picture's offset
# with no capsule under it; here he sits down and back half a metre and ends
# with his feet where he stood, which is where he has to get up from.
DOWN_TILT = 1.30


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


FOLDER = {"bosses": "Bosses", "saud": "Saud", "street": "Street"}

# Since 2026-09-25 Saud stands as a mixed martial artist (build_saud.
# MMA_GUARD) and nobody else does. The street men -- the thug, the brawler,
# every man with no clips of his own -- used to play Saud's; they play these
# now: the same twenty clips, struck on the boxer's GUARD, and the engine
# looks here before it looks at Saud's (SaudMotionComponent::Find).
STREET = dict(key="Street", canon=(
    "The street men, and anyone else with no clip of his own: Saud's clips "
    "on the boxer's guard, since Saud alone stands as a mixed martial artist."))
# which guard each set is struck from (build_saud.GUARDS / STANCE_OF)
GUARD_OF = {"Saud": "mma", "Saqr": "kickboxer", "Boss": "peekaboo", "Zayos": "heavy"}


def _strike_clips(key, row, who, moves, attacks, phase_two_ok, folder):
    out, seen = [], []
    for mv in moves:
        if mv in seen:              # Zayos throws hook twice; one clip
            continue
        seen.append(mv)
        a = attacks[mv]
        su, ac, rc = float(a["Startup"]), float(a["Active"]), float(a["Recovery"])
        out.append(dict(
            boss=key, display=row["DisplayName"], arabic=row["DisplayNameArabic"],
            move=mv, kind="strike", state="Attack", su=su, ac=ac, rc=rc, seconds=su + ac + rc,
            frames=max(2, int(round((su + ac + rc) * FPS))),
            contact=int(round(su * FPS)),
            limb=MOVES[mv][4], phase_two=(phase_two_ok and mv == "Special"),
            amp=who["amp"], stance=who["stance"], settle=who["settle"],
            speed=float(row["MoveSpeed"]), interval=float(row["AttackInterval"]),
            name="A_%s_%s" % (key, mv), folder=folder, guard=GUARD_OF.get(key, "boxer")))
    # What he does when he is not throwing anything. The browser bobs a
    # standing fighter at Math.sin(f.anim * 2.4) * 1.1 (index.html:1515)
    # and that 2.4 is a constant -- every fighter in the game breathes at
    # the same rate whatever his speed. Three different cycle lengths
    # here, one per boss, was a number with no source behind it.
    cyc = IDLE_SECONDS
    out.append(dict(boss=key, display=row["DisplayName"], arabic=row["DisplayNameArabic"],
                    move="Guard", kind="guard", state="Idle", su=0.0, ac=0.0, rc=0.0, seconds=cyc,
                    frames=int(round(cyc * FPS)), contact=-1, limb=None,
                    phase_two=False, amp=who["amp"], stance=who["stance"],
                    settle=who["settle"], speed=float(row["MoveSpeed"]),
                    interval=float(row["AttackInterval"]),
                    name="A_%s_Guard" % key, loop=True, folder=folder,
                    guard=GUARD_OF.get(key, "boxer")))
    return out


def plan(who=("bosses", "saud", "street")):
    """Every clip that should exist, and what decides it. Reads the tables;
    invents nothing."""
    attacks = {r["Name"]: r for r in read_csv("DT_Attacks.csv")}
    fighters = {r["Name"]: r for r in read_csv("DT_Fighters.csv")}
    clips = []
    if "bosses" in who:
        for key, meta in BOSSES.items():
            row = fighters[key]
            moves = parse_moves(row["Moves"])
            if key in PHASE_TWO and "Special" not in moves:
                moves = moves + ["Special"]
            clips += _strike_clips(key, row, character(meta["kind"]), moves, attacks, True, FOLDER["bosses"])
    for set_, spec in (("saud", SAUD), ("street", STREET)):
        if set_ in who:
            clips += _hero_clips(spec["key"], FOLDER[set_], fighters, attacks)
    return clips


def _hero_clips(key, folder, fighters, attacks):
    """Saud's clips -- his strikes and every state a fight holds him in --
    for a set: his own, or the street men's copy of them on the boxer's
    guard. Both are Saud's row and Saud's size; only the guard differs."""
    clips = []
    row = fighters[SAUD["key"]]
    me = saud_character()
    # His row's strikes, and the finisher. The player's finisher is
    # Special -- there is no Rage row (CLAUDE.md, "Known, not fixed") --
    # and it is his, not a phase two.
    moves = parse_moves(row["Moves"]) + ["Special"]
    clips += _strike_clips(key, row, me, moves, attacks, False, folder)
    eng = engine_timings()
    speed = float(row["MoveSpeed"])

    def state(name, kind, state_, seconds, loop=False, **kw):
        d = dict(boss=key, display=row["DisplayName"] if key == SAUD["key"] else "Street men",
                 arabic=row["DisplayNameArabic"] if key == SAUD["key"] else "",
                 move=name, kind=kind, state=state_, su=0.0, ac=0.0, rc=0.0, seconds=seconds,
                 frames=int(round(seconds * FPS)), contact=-1, limb=None, phase_two=False,
                 amp=me["amp"], stance=me["stance"], settle=me["settle"], speed=speed,
                 interval=float(row["AttackInterval"]), name="A_%s_%s" % (key, name),
                 loop=loop, folder=folder, guard=GUARD_OF.get(key, "boxer"))
        d.update(kw)
        return d
    for d in DIRS:
        clips.append(state("Walk_%s" % d, "walk", "Walk", 2.0 * math.pi / WALK_RATE, loop=True, dir=d))
    for d in DIRS:
        clips.append(state("Dash_%s" % d, "dash", "Dash", eng["dash"], dir=d))
    clips.append(state("Block", "block", "Block", IDLE_SECONDS, loop=True))
    clips.append(state("Hit_Light", "hit", "Hit", eng["hit_light"], weight=eng["hit_light"]))
    clips.append(state("Hit_Heavy", "hit", "Hit", eng["hit_heavy"], weight=eng["hit_heavy"]))
    clips.append(state("Down", "down", "Down", eng["down"]))
    clips.append(state("GetUp", "getup", "Idle", eng["getup"]))
    return clips


def check(clips):
    """The things that would be wrong and that a render would not tell you.
    Each of these has been made to fail by breaking what it guards."""
    attacks = {r["Name"]: r for r in read_csv("DT_Attacks.csv")}
    fighters = {r["Name"]: r for r in read_csv("DT_Fighters.csv")}
    bosses = any(c["boss"] in BOSSES for c in clips)
    heroes = [k for k in (SAUD["key"], STREET["key"]) if any(c["boss"] == k for c in clips)]

    # 1. every boss in the table that is a boss has clips here
    table_bosses = {r["Name"] for r in fighters.values() if r["bIsBoss"] == "true"}
    assert table_bosses == set(BOSSES), (
        "DT_Fighters marks %s as bosses; this builds %s" % (sorted(table_bosses), sorted(BOSSES)))

    # 2. every move a boss throws has a clip, and nothing else does
    for key in (BOSSES if bosses else ()):
        want = set(parse_moves(fighters[key]["Moves"]))
        if key in PHASE_TWO:
            want.add("Special")
        got = {c["move"] for c in clips if c["boss"] == key and c["move"] != "Guard"}
        assert want == got, "%s throws %s but has clips for %s" % (key, sorted(want), sorted(got))

    # 3. a clip is exactly as long as the attack table says, to within a frame
    for c in clips:
        if c["kind"] != "strike":
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
    assert got2 == (set(PHASE_TWO) if bosses else set()), "phase two clips for %s, expected %s" % (sorted(got2), sorted(PHASE_TWO))

    # 6b. each man's clips are struck from his own stance, the same one the
    #     renders and the souq scene pose him in
    import build_saud as L
    for c in clips:
        want = L.STANCE_OF.get(c["boss"].lower(), "boxer")
        assert c["guard"] == want, "%s is on the %s guard; build_saud stands him on the %s" % (c["name"], c["guard"], want)

    # 7. no two clips share a name
    names = [c["name"] for c in clips]
    assert len(names) == len(set(names)), "duplicate clip names: %s" % sorted(
        n for n in set(names) if names.count(n) > 1)

    for hero in heroes:
        mine = [c for c in clips if c["boss"] == hero]
        # 11. Saud stands in the MMA guard and nobody else does
        want_guard = "mma" if hero == SAUD["key"] else "boxer"
        assert all(c["guard"] == want_guard for c in mine), "%s's clips are not all on the %s guard" % (hero, want_guard)
        # 8. every strike his row lists, and the finisher, and no other
        want = set(parse_moves(fighters[SAUD["key"]]["Moves"])) | {"Special"}
        got = {c["move"] for c in mine if c["kind"] == "strike"}
        assert want == got, "%s throws %s but has strike clips for %s" % (hero, sorted(want), sorted(got))
        # 9. every state the engine puts him in has its clip, as long as the
        #    engine holds him there, to within a frame -- read off the C++
        eng = engine_timings()
        need = {"Hit_Light": eng["hit_light"], "Hit_Heavy": eng["hit_heavy"],
                "Down": eng["down"], "GetUp": eng["getup"]}
        need.update({"Dash_%s" % d: eng["dash"] for d in DIRS})
        for name, secs in need.items():
            c = next((c for c in mine if c["move"] == name), None)
            assert c, "%s has no %s clip" % (hero, name)
            assert abs(c["frames"] / float(FPS) - secs) <= 1.0 / FPS, (
                "%s is %d frames; the engine holds that state %.2fs" % (c["name"], c["frames"], secs))
        # 10. the walk is the browser's cycle, 2*pi/11 s, to within a frame, a
        #     loop, one per heading
        for d in DIRS:
            c = next(c for c in mine if c["move"] == "Walk_%s" % d)
            assert c["loop"] and abs(c["frames"] / float(FPS) - 2 * math.pi / WALK_RATE) <= 1.0 / FPS, (
                "%s is not the browser's walk cycle" % c["name"])
    return True


def describe(clips):
    print("MOTION -- %d clips on the shared 62-bone skeleton, posed through the IK rig\n" % len(clips))
    people = [(k, m["canon"], character(m["kind"])) for k, m in BOSSES.items()] + \
             [(SAUD["key"], SAUD["canon"], saud_character()),
              (STREET["key"], STREET["canon"], saud_character())]
    for key, canon, who in people:
        mine = [c for c in clips if c["boss"] == key]
        if not mine:
            continue
        d = mine[0]
        print("%s / %s  %s" % (d["display"], d["arabic"], "(phase two: special)" if key in PHASE_TWO else ""))
        print("   %s" % canon)
        print("   sc %.2f build %.2f -> amplitude x%.2f  stance x%.2f   speed %.0f  interval %.2fs" % (
            who["sc"], who["build"], who["amp"], who["stance"], d["speed"], d["interval"]))
        for c in mine:
            if c["kind"] == "strike":
                print("      %-20s %5.2fs %3d frames  contact on %2d  (%.2f/%.2f/%.2f)  %s" % (
                    c["name"], c["seconds"], c["frames"], c["contact"], c["su"], c["ac"], c["rc"], c["limb"]))
            else:
                print("      %-20s %5.2fs %3d frames  %s%s" % (
                    c["name"], c["seconds"], c["frames"], c["state"], "  loop" if c.get("loop") else ""))
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


# ================================================================ authoring
# Every clip is posed through the control rig by motion_ik.Author; see that
# file for why and for what it measured on the FK clips this replaced.
SIDES = ("l", "r")
# The straight punches: the fist travels a line from the guard to where the
# FK shape would have put it. Posed in FK it swung on an arc about the
# shoulder, and a jab that arcs is a slap. The hook keeps its arc; it is one.
LINE = ("Jab", "Cross")
# The hand that covers while the other one throws, where the body turns into
# the blow: it turns with the chest rather than holding its world aim. The
# jab has almost no turn in it and keeps its rear hand as it is.
COVER = {"Cross": "l", "Hook": "l"}
# --bite only: each entry breaks one mechanism a motion check guards
SABOTAGE = set()


def aims_at(guard, strike, k, stance):
    """The guard blended toward a strike by k along the sphere, with the
    fighter's own stance width on the legs -- as the FK build always did."""
    import mathutils
    aims = {}
    for name, g in guard.items():
        s = strike.get(name, g)
        aims[name] = slerp_aim(g, s, k) if s != g else g
    if stance != 1.0:
        for side in ("_l", "_r"):
            for base in ("thigh", "calf"):
                nm = base + side
                if nm in aims:
                    v = mathutils.Vector(aims[nm]); v.x *= stance
                    aims[nm] = tuple(v.normalized())
    return aims


def bump(u, a, m, b):
    """0 outside [a, b], up to 1 at m and back down, on the browser's ease."""
    if u <= a or u >= b:
        return 0.0
    return ease((u - a) / (m - a)) if u < m else 1.0 - ease((u - m) / (b - m))


def strike_frame(au, g, aims, lean, twist, planted, lift=(0.0, 0.0, 0.0), hand_at=None, spin=None, carry=()):
    """One frame of a strike: the FK shape, grounded as the FK build
    grounded it (the lowest planted foot on the guard's floor), then the
    legs handed to the rig -- planted feet exactly where the guard stands
    them, turned on the ball and rolled onto it as far as the FK shape
    turned and rolled them -- the hips lowered only if a planted leg cannot
    reach, and the arms handed over last, from the settled torso."""
    import motion_ik as M
    from mathutils import Vector
    au.begin()
    au.fk_body(aims, lean=lean, twist=twist, carry=carry)
    fk = au.read()
    dz = g["ground"] - min(fk["ball_" + s].z for s in planted)
    au.move_hips((lift[0], lift[1], dz + lift[2]))
    fk = au.read()
    if len(planted) == 1 and "plant" not in SABOTAGE:
        # One foot on the floor: the weight goes over it. The FK shape put
        # the support foot where the support leg's aims left it -- 34 cm
        # back under the hips at the full extent of a round kick -- and the
        # FK build let it skate there. The foot is planted now, so the body
        # moves instead, by exactly that much: onto the lead leg, which is
        # what a rear-leg kick does with a man's weight.
        s = planted[0]
        move = g["ball_" + s] - fk["ball_" + s]
        au.move_hips((move.x, move.y, 0.0))
        fk = au.read()
    rolls = {}
    for s in SIDES:
        # A planted knee bends forward, the only way a knee bends -- its
        # pole out in front, as build_saud's own planted stances put it.
        # Read off the FK bend instead, the guard's rear knee was 11 cm
        # BEHIND the line from hip to ankle: 29 degrees of a knee bent the
        # wrong way, in every frame of every FK clip, and 9 more on the
        # kick's support leg. A striking leg keeps its FK chamber.
        if s in planted and "knee" not in SABOTAGE:
            pole = (fk["hip_" + s] + fk["an_" + s]) * 0.5 + Vector((0.0, -0.6, 0.0))
        else:
            pole = M.pole_from(fk["hip_" + s], fk["kn_" + s], fk["an_" + s], Vector((0.0, -1.0, 0.0)))
        if s in planted and "plant" not in SABOTAGE:
            yaw, roll = M.foot_turn(fk["foot_" + s], g["fk"]["foot_" + s])
            au.leg(s, au.planted(s, yaw, g), pole, roll)
            rolls[s] = roll
        else:
            au.leg(s, fk["foot_" + s], pole)
            rolls[s] = 0.0
    drop = au.settle(list(planted))
    fk = au.read()
    for s in SIDES:
        m = fk["hand_" + s].copy()
        if hand_at and s in hand_at:
            m.translation = hand_at[s](fk) if callable(hand_at[s]) else hand_at[s]
        au.arm(s, m, M.pole_from(fk["sh_" + s], fk["el_" + s], fk["wr_" + s], Vector((0.0, 1.0, 0.0))))
    if spin:
        au.pivot(*spin)
    loc, world = au.record()
    return loc, world, rolls, drop, fk


def author_strike(au, c, S):
    strike, twist = S[c["move"]]
    guard, _ = S["Guard"]
    lean, hip, shift, turns, limb = MOVES.get(c["move"], (0, 0, 0, 0.0, None))
    tip = inclination(c["move"]) if c["move"] in MOVES else 0.0
    g = au.capture_guard(aims_at(guard, guard, 0.0, c["stance"]))
    planted = [s for s in SIDES if not (limb == "rear_leg" and s == "r")]
    striker = {"lead_arm": "l", "rear_arm": "r"}.get(limb)
    cs = COVER.get(c["move"]) if "cover" not in SABOTAGE else None
    cover = tuple(b + "_" + cs for b in ("clavicle", "upperarm", "lowerarm", "hand", "palm")) if cs else ()
    # The covering fist tucks to the cheek as the body turns into the blow:
    # a fixed place in the HEAD's frame, from wherever the guard holds it
    # (an MMA lead hand is 44 cm out) to 15 cm in front of the cheekbone
    # at contact. Carried with the chest alone (COVER's aims), a 60 degree
    # turn swung it 40 cm out to the side of a head that -- since
    # 2026-09-26 -- keeps looking at the opponent.
    # --bite "tuck": the fist is carried with the chest (COVER) and never
    # tucked, so a cross's turn swings it 40 cm out to the side of the face.
    # ("cover" alone no longer breaks anything measurable: with the head
    # kept on the opponent, a fist left at the guard's world spot sits 11 cm
    # in front of the face, which is a cover.)
    tuck = None
    if cs and "tuck" not in SABOTAGE:
        from mathutils import Vector
        hm0 = g["fk"]["head_m"]
        g_local = hm0.inverted() @ g["fk"]["hand_" + cs].translation
        tuck_local = Vector(((1.0 if cs == "l" else -1.0) * 0.09, -0.07, 0.15))
        tuck = (cs, g_local, tuck_local)

    def pose(k, lift=(0.0, 0.0, 0.0), hand_at=None, spin=None):
        return strike_frame(au, g, aims_at(guard, strike, k, c["stance"]), tip * k,
                            {nm: amt * k for nm, amt in twist.items()}, planted, lift, hand_at, spin,
                            carry=cover)

    ends = None
    if c["move"] in LINE and "line" not in SABOTAGE:
        ends = (pose(0.0)[4]["hand_" + striker].translation.copy(),
                pose(c["amp"])[4]["hand_" + striker].translation.copy())
    frames, plant, drops = [], {s: {} for s in planted}, []
    for f in range(c["frames"]):
        t = f / float(FPS)
        lift = (0.0, 0.0, 0.0)
        if c["kind"] == "guard":
            # He breathes and shifts his weight. The browser bobs at
            # sin(t*2.4)*1.1 px standing; the sway is a quarter-cycle behind
            # it, so the weight goes round in a loop that closes -- the FK
            # build swayed a half sine, to one side and back and never to
            # the other. It moves the hips now, not the root: the root moved
            # the feet with it, 2.2 cm side to side under a standing man.
            # The breath sinks from the stance rather than rising above it:
            # the guard's legs are all but straight, and a hip that rises
            # 2.6 cm over planted feet has nowhere to go -- measured, the top
            # of every breath was cut flat at 0.7. The browser's height, one
            # amplitude lower -- and starting at the top, so the loop's first
            # frame is the neutral guard every other state starts and ends on.
            k = 0.0
            ph = 2.0 * math.pi * t / c["seconds"]
            lift = (math.sin(ph) * 0.9 * PX, 0.0, (math.cos(ph) - 1.0) * IDLE_PX * PX)
        else:
            k = blend_k(t, c["su"], c["ac"], c["rc"]) * c["amp"]
        hand_at = {striker: ends[0].lerp(ends[1], k / c["amp"])} if ends else {}
        if tuck:
            cs_, gl, tl = tuck
            w = min(1.0, k / c["amp"])
            hand_at[cs_] = (lambda fk, w=w: fk["head_m"] @ gl.lerp(tl, w))
        hand_at = hand_at or None
        spin = (g["ball_l"], turns * 2.0 * math.pi * (t / c["seconds"])) if turns else None
        loc, world, rolls, drop, _fk = pose(k, lift, hand_at, spin)
        frames.append((loc, world))
        drops.append(drop)
        for s in planted:
            plant[s][f] = (g["ball_" + s].copy(), rolls[s])
    c["plant"] = plant
    c["drop_cm"] = max(drops) * 100.0
    c["line"] = (striker, ends) if ends else None
    return frames


# ----------------------------------------------------------- the states
def body_frame(au, g, aims, feet, lean=0.0, hips=(0.0, 0.0, 0.0), tilt=0.0, side_tilt=0.0,
               post_aims=None, hands=None, hand_poles=None, settle=()):
    """One frame of anything that is not a strike: the guard's body shape,
    the hips moved and tipped (tilt + is back, side_tilt + toward his
    left), the feet put where `feet` says, the arms from the body or from
    `hands`. Values in `feet`, `hands` and `hand_poles` may be functions of
    the FK read, for anything that has to follow the moved body."""
    import motion_ik as M
    import rig_full_ik as CR
    from mathutils import Vector
    au.begin()
    au.fk_body(aims, lean=lean)
    au.move_hips((hips[0], hips[1], hips[2] + g["dz"]))
    if tilt:
        au.tilt_hips(-tilt, "X")         # about +X a turn carries up toward -Y, his front
    if side_tilt:
        au.tilt_hips(side_tilt, "Y")     # about +Y a turn carries up toward +X, his left
    if post_aims:
        CR._aim(au.rig, post_aims)
    fk = au.read()
    for s, (m, pole, roll) in feet.items():
        au.leg(s, m(fk) if callable(m) else m, pole(fk) if callable(pole) else pole, roll)
    drop = au.settle(settle) if settle else 0.0
    fk = au.read()
    for s in SIDES:
        h = (hands or {}).get(s)
        m = h(fk) if callable(h) else (h if h is not None else fk["hand_" + s])
        p = (hand_poles or {}).get(s)
        p = p(fk) if callable(p) else p
        if p is None:
            p = M.pole_from(fk["sh_" + s], fk["el_" + s], fk["wr_" + s], Vector((0.0, 1.0, 0.0)))
        au.arm(s, m, p)
    loc, world = au.record()
    return loc, world, fk, drop


def knee_forward(s, up=0.0):
    from mathutils import Vector
    return lambda fk, s=s: (fk["hip_" + s] + fk["an_" + s]) * 0.5 + Vector((0.0, -0.6, up))


def planted_feet(g):
    return {s: (g["ctrl_foot_" + s], knee_forward(s), 0.0) for s in SIDES}


def walk_offset(us, beta, amp):
    """Where a foot is along the heading, at its own phase `us`: on the
    ground for the first `beta` of the cycle, carried back under him at the
    speed he moves (so in the world it is still), then swung forward."""
    if us < beta:
        return amp * (0.5 - us / beta), 0.0, True
    w = (us - beta) / (1.0 - beta)
    return -amp * 0.5 + amp * ease(w), math.sin(math.pi * w), False


def walk_gait(stride, w, lateral, heading):
    """The duty factor and each foot's phase. Forward and back: the feet
    half a cycle apart and on the ground 35 % of it each -- a run, which is
    what 341 cm/s at the browser's 11 rad/s is. Sideways the feet must never
    cross, so the foot on the side he is going leads and the other chases
    it, and the duty and lag are the pair that keep them furthest apart."""
    if not lateral:
        return 0.35, {"l": 0.0, "r": 0.5}
    lead = "l" if heading == "Left" else "r"
    trail = "r" if lead == "l" else "l"
    if "cross" in SABOTAGE:
        return 0.35, {lead: 0.0, trail: 0.5}
    best = None
    for beta in (0.45, 0.40, 0.35, 0.30, 0.25, 0.20):
        amp = stride * beta
        for i in range(2, 21):
            phi = i / 40.0
            sep = min(w + walk_offset(u / 60.0, beta, amp)[0] - walk_offset((u / 60.0 - phi) % 1.0, beta, amp)[0]
                      for u in range(60))
            if best is None or sep > best[0] + 1e-4:
                best = (sep, beta, phi)
    _sep, beta, phi = best
    return beta, {lead: 0.0, trail: (-phi) % 1.0}


def author_walk(au, c, S):
    from mathutils import Vector, Matrix
    guard, _ = S["Guard"]
    aims = aims_at(guard, guard, 0.0, c["stance"])
    g = au.capture_guard(aims)
    d = Vector(DIRS[c["dir"]])
    N = c["frames"]
    T = N / float(FPS)
    v = c["speed"] / 100.0
    lateral = abs(d.x) > 0.5
    w = abs(g["ball_l"].x - g["ball_r"].x)
    beta, phase = walk_gait(v * T, w, lateral, c["dir"])
    amp = v * T * beta
    clear = 0.10        # a foot that swings at 7 cm read as a shuffle
    # each foot swings about a centre: under the hips along the heading (a
    # runner's foot lands under him, not where the bladed guard had it), and
    # where the guard has it across the heading
    centre = {s: ((g["pelvis"].translation - g["ball_" + s]).dot(d) if not lateral else 0.0) for s in SIDES}
    frames, plant = [], {s: {} for s in SIDES}
    for f in range(N):
        u = f / float(N)
        feet = {}
        for s in SIDES:
            off, lift, down = walk_offset((u + phase[s]) % 1.0, beta, amp)
            shift = d * (centre[s] + off) + Vector((0.0, 0.0, clear * lift))
            feet[s] = (Matrix.Translation(shift) @ g["ctrl_foot_" + s], knee_forward(s), 0.0)
            if down:
                plant[s][f] = (g["ball_" + s] + d * (centre[s] + off), 0.0)
        # the browser's moving bob, 2.2 px, at its lowest under each foot's
        # mid-stance and highest in the air -- twice a cycle, as a running
        # body does -- and sinking from the stance, not rising over it, for
        # the reason the guard's breath does. 2.2 px from top to bottom, not
        # either way: the browser's bob is once a cycle, and doubled into
        # two a cycle at its full height it ran him in a squat over knees
        # the guard already bends (judged on the contact sheet).
        bob = -WALK_BOB_PX * PX * 0.5 * (1.0 + math.cos(4.0 * math.pi * (u - beta / 2.0)))
        loc, world, _fk, _d = body_frame(au, g, aims, feet, hips=(0.0, 0.0, bob), settle=SIDES)
        frames.append((loc, world))
    c["plant"] = plant
    c["gait"] = dict(duty=beta, lag=phase, stride_cm=amp * 100.0)
    return frames


def author_dash(au, c, S):
    """The engine launches him along the stick and holds the state 0.24 s;
    the clip is the body doing it on the spot: a dip to load, both feet off
    the floor with the leading one reaching and the other trailing, the
    body leaning into the heading, and the catch back into the guard."""
    from mathutils import Vector, Matrix
    guard, _ = S["Guard"]
    aims = aims_at(guard, guard, 0.0, c["stance"])
    g = au.capture_guard(aims)
    d = Vector(DIRS[c["dir"]])
    lead = {"Fwd": "l", "Back": "r", "Left": "l", "Right": "r"}[c["dir"]]
    N = c["frames"]
    frames, plant = [], {s: {} for s in SIDES}
    for f in range(N):
        u = f / float(N - 1)
        load, air, land = bump(u, 0.0, 0.22, 0.45), bump(u, 0.22, 0.52, 0.82), bump(u, 0.70, 0.86, 1.0)
        hips = d * (0.05 * air) + Vector((0.0, 0.0, -0.05 * load + 0.025 * air - 0.035 * land))
        into = 0.14 * bump(u, 0.0, 0.40, 1.0)
        lean = into * -d.y                 # forward (-Y) leans in, back leans away
        side = into * d.x                  # toward his left leans left
        feet = {}
        for s in SIDES:
            reach = 0.10 if s == lead else -0.07
            up = 0.07 if s == lead else 0.05
            shift = d * (reach * air) + Vector((0.0, 0.0, up * air))
            feet[s] = (Matrix.Translation(shift) @ g["ctrl_foot_" + s], knee_forward(s), 0.0)
            if air < 1e-6:
                plant[s][f] = (g["ball_" + s].copy(), 0.0)
        loc, world, _fk, _d = body_frame(au, g, aims, feet, lean=lean, side_tilt=side,
                                         hips=tuple(hips), settle=[s for s in SIDES if air < 1e-6])
        frames.append((loc, world))
    c["plant"] = plant
    return frames


def author_block(au, c, S):
    """index.html:1506: arms higher and tighter, lean 0.16, the hip 3 px
    lower. The browser draws the arms up; the rig can say exactly where:
    both fists at the forehead, a hand's width apart, elbows down in front
    of the ribs -- the guard a hook or a straight meets."""
    from mathutils import Vector
    guard, _ = S["Guard"]
    aims = aims_at(guard, guard, 0.0, c["stance"])
    g = au.capture_guard(aims)
    # The wrists straight -- the knuckles on up the forearm's line, which
    # leans back toward the forehead here (measured, the guard's hand aims
    # left each wrist bent 40 degrees in the block) -- and the palms to the
    # face, the backs of the hands to the blow.
    tuck = dict(aims, neck_01=(0.0, -0.16, 0.99), head=(0.0, -0.22, 0.975),
                hand_l=(-0.07, 0.55, 0.83), hand_r=(0.07, 0.55, 0.83),
                palm_l=(-0.30, 0.95, 0.0), palm_r=(0.30, 0.95, 0.0))
    N = c["frames"]
    frames, plant = [], {s: {} for s in SIDES}
    side = {"l": 1.0, "r": -1.0}

    def fist(s):
        def at(fk, s=s):
            m = fk["hand_" + s].copy()
            m.translation = fk["head"] + Vector((0.075 * side[s], -0.11, 0.03))
            return m
        return at

    def elbow(s):
        return lambda fk, s=s: fk["sh_" + s] + Vector((0.10 * side[s], -0.30, -0.60))
    for f in range(N):
        ph = 2.0 * math.pi * f / float(N)
        hips = (math.cos(ph) * 0.6 * PX, 0.0, -BLOCK_HIP_PX * PX + (math.sin(ph) - 1.0) * IDLE_PX * PX)
        loc, world, _fk, _d = body_frame(au, g, tuck, planted_feet(g), lean=BLOCK_LEAN, hips=hips,
                                         hands={s: fist(s) for s in SIDES},
                                         hand_poles={s: elbow(s) for s in SIDES}, settle=SIDES)
        frames.append((loc, world))
        for s in SIDES:
            plant[s][f] = (g["ball_" + s].copy(), 0.0)
    c["plant"] = plant
    return frames


# index.html:1511: the arms thrown, [-0.5,-0.5] and [-0.9,-0.4] against the
# guard's folded-up pair -- back and down, loose. And the head goes back
# further than the chest does.
HIT_AIMS = dict(upperarm_l=(0.46, 0.20, -0.86), lowerarm_l=(0.30, -0.30, -0.90), hand_l=(0.25, -0.35, -0.90),
                upperarm_r=(-0.46, 0.20, -0.86), lowerarm_r=(-0.30, -0.30, -0.90), hand_r=(-0.25, -0.35, -0.90),
                neck_01=(0.0, 0.10, 0.99), head=(0.0, 0.22, 0.975))


def author_hit(au, c, S):
    """index.html:1509-1511, exactly: hk = clamp(hitT / 0.28) with hitT
    counting down from the state's own length, so a light hit starts at
    0.79 of the recoil and a heavy one at all of it; lean back hk * 0.5,
    the hip hk * 4 px lower. The browser snaps to it; here it takes the
    first 50 ms, because a head that teleports is not a head that was hit.
    The feet stay: the engine's knockback moves the man."""
    guard, _ = S["Guard"]
    aims_g = aims_at(guard, guard, 0.0, c["stance"])
    g = au.capture_guard(aims_g)
    dur = c["seconds"]
    frames, plant = [], {s: {} for s in SIDES}
    for f in range(c["frames"]):
        t = f / float(FPS)
        hk = min(1.0, max(0.0, (dur - t) / HIT_SPAN)) * ease(min(1.0, t / 0.05))
        aims = aims_at(aims_g, HIT_AIMS, hk, 1.0)
        loc, world, _fk, _d = body_frame(au, g, aims, planted_feet(g), lean=-HIT_LEAN * hk,
                                         hips=(0.0, 0.03 * hk, -HIT_HIP_PX * PX * hk), settle=SIDES)
        frames.append((loc, world))
        for s in SIDES:
            plant[s][f] = (g["ball_" + s].copy(), 0.0)
    c["plant"] = plant
    return frames


def down_keys(g):
    """Down: he sits down and back onto the floor and ends propped on his
    hands, the torso back DOWN_TILT from upright -- the browser's end angle.
    The lead foot stays where it stood; the rear one slides in beside it,
    because a man who sits straight back cannot leave a foot behind him.
    Heights are the pelvis's own above the floor; gz is where the guard
    stands it once grounded."""
    gz = g["pelvis"].translation.z + g["dz"]
    return [(0.00, dict(pz=gz, py=0.00, tilt=0.00, rear=0.0, hand=0.0, look=0.0)),
            (0.20, dict(pz=gz - 0.10, py=0.06, tilt=0.30, rear=0.0, hand=0.0, look=0.3)),
            (0.45, dict(pz=0.32, py=0.30, tilt=0.55, rear=1.0, hand=0.3, look=0.6)),
            (0.72, dict(pz=0.14, py=0.46, tilt=1.10, rear=1.0, hand=0.9, look=1.0)),
            (1.00, dict(pz=(0.02 if "sink" in SABOTAGE else 0.12), py=0.50, tilt=DOWN_TILT,
                        rear=1.0, hand=1.0, look=1.0))]


def getup_keys(g):
    """GetUp: from exactly where Down left him -- sit up, pull the rear foot
    back under the hips on the hands' push, rise leaning forward over the
    feet, and stand into the guard. 0.6 s, because that is the mercy the
    engine gives a man getting up (FighterBase.cpp: "brief mercy on getting
    up"); after it he can be hit, so after it he is standing."""
    end = dict(down_keys(g)[-1][1])
    if "getup" in SABOTAGE:
        end["tilt"] += 0.3
    gz = g["pelvis"].translation.z + g["dz"]
    return [(0.00, end),
            (0.30, dict(pz=0.16, py=0.42, tilt=0.45, rear=1.0, hand=1.0, look=0.8)),
            (0.62, dict(pz=0.55, py=0.14, tilt=-0.30, rear=0.0, hand=0.2, look=0.3)),
            (1.00, dict(pz=gz, py=0.00, tilt=0.00, rear=0.0, hand=0.0, look=0.0))]


def keyed(keys, u):
    for (u0, p0), (u1, p1) in zip(keys, keys[1:]):
        if u <= u1 or u1 == keys[-1][0]:
            w = ease((u - u0) / (u1 - u0)) if u1 > u0 else 1.0
            w = max(0.0, min(1.0, w))
            return {k: p0[k] + (p1[k] - p0[k]) * w for k in p0}
    return dict(keys[-1][1])


def author_floor(au, c, S, keys_of):
    """Down and GetUp, one mechanism: keyed hips (height, how far back, how
    far tipped), the lead foot planted where it stood, the rear foot slid
    between its guard spot and the lead's side, the hands pressed to two
    fixed points on the floor behind the hips, and the head brought back
    to looking forward as the torso goes back."""
    import mathutils
    from mathutils import Vector, Matrix
    guard, _ = S["Guard"]
    aims = aims_at(guard, guard, 0.0, c["stance"])
    g = au.capture_guard(aims)
    keys = keys_of(g)
    gp = g["pelvis"].translation
    side = {"l": 1.0, "r": -1.0}
    beside = Vector((0.0, g["ball_l"].y + 0.05 - g["ball_r"].y, 0.0))      # rear foot's slide
    floor = {s: Vector((0.28 * side[s], gp.y + 0.72, 0.05)) for s in SIDES}
    ahead = {"neck_01": (0.0, -0.45, 0.89), "head": (0.0, -0.35, 0.94)}
    N = c["frames"]
    frames, plant = [], {s: {} for s in SIDES}
    for f in range(N):
        u = f / float(N - 1)
        p = keyed(keys, u)
        prev = keyed(keys, max(0.0, u - 1.0 / (N - 1)))
        moving_rear = abs(p["rear"] - prev["rear"]) > 1e-4
        rear_shift = beside * p["rear"] + Vector((0.0, 0.0, 0.025 if moving_rear else 0.0))
        feet = {"l": (g["ctrl_foot_l"], knee_forward("l", up=0.5 * min(1.0, p["tilt"] + 0.2)), 0.0),
                "r": (Matrix.Translation(rear_shift) @ g["ctrl_foot_r"],
                      knee_forward("r", up=0.5 * min(1.0, p["tilt"] + 0.2)), 0.0)}
        # the head: its guard aim turned back with the torso, then brought
        # round toward looking forward by `look`
        turn = mathutils.Matrix.Rotation(-p["tilt"], 3, "X")
        post = {}
        for nm, want in ahead.items():
            now = (turn @ mathutils.Vector(aims[nm])).normalized()
            post[nm] = tuple(slerp_aim(tuple(now), want, p["look"]))

        def hand(s, w=p["hand"]):
            def at(fk, s=s, w=w):
                m = fk["hand_" + s].copy()
                m.translation = fk["hand_" + s].translation.lerp(floor[s], w)
                return m
            return at

        def elbow(s):
            return lambda fk, s=s: fk["sh_" + s] + Vector((0.45 * side[s], 0.25, -0.10))
        loc, world, _fk, _d = body_frame(
            # pz is the pelvis's height: body_frame adds the guard's grounding
            # (dz) to what it is given, so it is taken out here -- it used
            # to sit every fall lower by it, 1.6 cm on the boxer's straight
            # legs and 5.6 on Saud's bent ones, through the floor
            au, g, aims, feet, hips=(0.0, p["py"], p["pz"] - gp.z - g["dz"]), tilt=p["tilt"], post_aims=post,
            hands={s: hand(s) for s in SIDES}, hand_poles={s: elbow(s) for s in SIDES} if p["hand"] > 0.05 else None,
            settle=["l"])
        frames.append((loc, world))
        plant["l"][f] = (g["ball_l"].copy(), 0.0)
        if not moving_rear:
            plant["r"][f] = (g["ball_r"] + beside * p["rear"], 0.0)
    c["plant"] = plant
    return frames


AUTHOR = {"strike": author_strike, "guard": author_strike, "walk": author_walk, "dash": author_dash,
          "block": author_block, "hit": author_hit,
          "down": lambda au, c, S: author_floor(au, c, S, down_keys),
          "getup": lambda au, c, S: author_floor(au, c, S, getup_keys)}


def author_all(clips):
    """Every clip, on one control rig, then baked to the 62 bones. Returns
    the rig (stripped) and [(clip, action, recorded frames)]."""
    import motion_ik as M
    t0 = time.time()
    rig = M.make_rig()
    if "knee" in SABOTAGE:
        for s in SIDES:
            rig.pose.bones["calf_" + s].use_ik_limit_x = False
    au = M.Author(rig)
    print("%6.1fs  rig: %d bones, control layer on" % (time.time() - t0, len(rig.data.bones)))
    import build_saud as L
    S = {name: _strikes(g) for name, g in L.GUARDS.items()}
    authored = []
    for c in clips:
        authored.append((c, AUTHOR[c["kind"]](au, c, S[c["guard"]])))
    print("%6.1fs  authored %d clips through the IK rig" % (time.time() - t0, len(authored)))
    made = M.to_actions(rig, authored)
    err, where = M.bake_error(rig, made)
    print("%6.1fs  baked to the 62 bones: worst bone %.3f mm off the rig (%s)" % (time.time() - t0, err * 1000, where))
    assert err < 0.0005, "the bake does not reproduce the rig: %.2f mm at %s" % (err * 1000, where)
    return rig, made


def build(clips, out_root, sheet=False):
    import bpy
    t0 = time.time()
    rig, made = author_all(clips)
    verify(rig, made)
    # ---- export, one FBX a clip, armature only: UE5 imports animation onto
    # a skeleton it already has, and the mesh is Saud's and already there.
    by_folder = {}
    for item in made:
        by_folder.setdefault(item[0]["folder"], []).append(item)
    for folder, items in by_folder.items():
        out_dir = os.path.join(out_root, folder)
        os.makedirs(out_dir, exist_ok=True)
        for c, act, _frames in items:
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
                # every key kept: the exporter's default simplify (1.0) drops
                # keys it judges close enough, and on a planted foot "close
                # enough" measured 8 mm of slide in the file that was not in
                # the rig -- the read-back below is what found it
                bake_anim_simplify_factor=0.0,
                primary_bone_axis="Y", secondary_bone_axis="X",
                apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS")
            rig.animation_data.action = None
        manifest = os.path.join(out_dir, "DT_%sMotion.csv" % ("Boss" if folder == "Bosses" else folder))
        with open(manifest, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["Name", "Fighter", "Attack", "File", "Seconds", "Frames",
                        "ContactFrame", "Limb", "bLoop", "bPhaseTwo", "State", "Direction"])
            for c, _a, _f in items:
                w.writerow([c["name"], c["boss"], c["move"] if c["kind"] == "strike" else "",
                            c["name"] + ".fbx", "%.3f" % c["seconds"], c["frames"],
                            c["contact"], c["limb"] or "", str(c.get("loop", False)).lower(),
                            str(c["phase_two"]).lower(), c["state"], c.get("dir", "")])
        print("%6.1fs  %s: exported %d fbx + %s" % (time.time() - t0, folder, len(items), os.path.basename(manifest)))
        if sheet:
            contact_sheet(rig, items, out_dir, "%s-motion.png" % ("boss" if folder == "Bosses" else folder.lower()))
    readback(made, out_root)
    return made


def readback(made, out_root):
    """Every exported file read back into an empty scene and every bone of
    every frame measured against what the rig had. Blender's importer puts
    the keys one frame later than they were written (its convention, not
    the file's), so authored frame f is read at f + 2. Last, because it
    empties the scene the rig lives in."""
    import bpy
    worst, where = 0.0, None
    for c, _act, frames in made:
        path = os.path.join(out_root, c["folder"], c["name"] + ".fbx")
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=path)
        rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
        for f, (_loc, world) in enumerate(frames):
            bpy.context.scene.frame_set(f + 2)
            bpy.context.view_layer.update()
            for n, w in world.items():
                e = ((rig.matrix_world @ rig.pose.bones[n].matrix).translation - w).length
                if e > worst:
                    worst, where = e, "%s frame %d %s" % (c["name"], f + 1, n)
    print("        read back %d fbx: worst bone %.2f mm off what was authored (%s)" % (len(made), worst * 1000, where))
    assert worst < 0.001, "an exported clip does not play back what was authored: %.1f mm at %s" % (worst * 1000, where)


TIP = {"lead_arm": "hand_end_l", "rear_arm": "hand_end_r", "rear_leg": "ball_r"}


def hands_check(c, rig, fails):
    """The hand checks verify() runs on each clip. Distances are the
    skeleton's own, taken from its hand bone's length (0.075 m on Saud), so
    a boss half again his size is held to the same shape."""
    import bpy
    import build_saud as L
    from mathutils import Vector
    pb = rig.pose.bones
    W = rig.matrix_world
    hand_len = rig.data.bones["hand_l"].length
    k = hand_len / 0.075
    N = c["frames"]

    def go(f):
        bpy.context.scene.frame_set(f); bpy.context.view_layer.update()

    def closed(s):
        tip = (W @ pb["index_03_" + s].tail - W @ pb["hand_" + s].tail).length
        thumb = (W @ pb["thumb_03_" + s].tail - W @ pb["middle_02_" + s].head).length
        return tip / hand_len, thumb / hand_len

    def guard_hand(s, strict=True):
        """Why this hand is not in a guard, or None."""
        H = W @ pb["head"].head
        fist = W @ pb["hand_" + s].tail
        el, sh = W @ pb["lowerarm_" + s].head, W @ pb["upperarm_" + s].head
        # in the head's own frame -- its Y is up the neck, its Z the way the
        # face looks, its X across -- so a hook that turns the whole man is
        # measured against where he is facing, not against the world's axes
        # (a boss's hook carried the covering fist 17-20 cm across the
        # WORLD's X while it stayed in front of his own face)
        loc = (W @ pb["head"].matrix).inverted() @ fist
        fwd, across, dz = loc.z, abs(loc.x), loc.y
        # a strike's other hand only has to stay up and in front: the lean
        # carries the head out over it (10 cm in front of the face at a
        # jab's contact). 5 cm, since the covering hand turns with the chest
        # (COVER): held to the world, a cross left it 2 cm in front of the
        # face and a hook 1 cm behind it, 19-23 cm low
        lo_fwd, hi_across, lo_dz = (0.08, 0.13, -0.20) if strict else (0.05, 0.16, -0.25)
        if fwd < lo_fwd * k or across > hi_across * k or not (lo_dz * k <= dz <= 0.05 * k):
            return "the %s fist is not up in front of the face (%.0f cm forward, %.0f across, %+.0f up)" % (
                s, fwd * 100, across * 100, dz * 100)
        if not strict:
            # ...and tucked: the covering fist is at the cheek by contact
            # (author_strike's tuck, 15 cm out). Left at the guard's spot
            # while the shoulder goes back, a boxer's lead hand hangs 36 cm
            # out in front of the face at the end of a stiff arm.
            if fwd > 0.26 * k:
                return "the %s fist hangs out in front of the face (%.0f cm forward) instead of tucking" % (s, fwd * 100)
            return None
        hm = (W @ pb["head"].matrix).inverted()
        if abs((hm @ el).x) > abs((hm @ sh).x) - 0.02 * k:
            return "the %s elbow flares: %.0f cm out against a shoulder at %.0f" % (
                s, abs((hm @ el).x) * 100, abs((hm @ sh).x) * 100)
        fa = (W @ pb["lowerarm_" + s].tail - el).normalized()
        hd = (fist - W @ pb["hand_" + s].head).normalized()
        bend = math.degrees(fa.angle(hd))
        if bend > 28.0:
            return "the %s wrist is bent %.0f degrees" % (s, bend)
        m = (W @ pb["hand_" + s].matrix).to_3x3()
        palm = (m @ L.palm_local(rig, s)).normalized()
        # rolled, the palms face 0.80-0.89 toward him; left at the roll the
        # aim alone gives them they are 28 and 51 degrees off it
        if palm.y < 0.72:
            return "the %s palm faces the opponent (%.2f toward him)" % (s, palm.y)
        return None

    for f in range(1, N + 1, 3):
        go(f)
        for s in SIDES:
            tip, thumb = closed(s)
            if tip > 0.30 or thumb > 0.90:
                fails.append("%s: the %s hand is open on frame %d (index tip %.2f, thumb %.2f hand lengths)" % (
                    c["name"], s, f, tip, thumb))
                return
    if c["kind"] in ("guard", "walk", "dash"):
        for f in range(1, N + 1, 3):
            go(f)
            for s in SIDES:
                why = guard_hand(s)
                if why:
                    fails.append("%s: %s on frame %d" % (c["name"], why, f))
                    return
    elif c["limb"] in ("lead_arm", "rear_arm"):
        other = "r" if c["limb"] == "lead_arm" else "l"
        go(c["contact"] + 1)
        why = guard_hand(other, strict=False)
        if why:
            fails.append("%s: the hand not punching drops -- %s at contact" % (c["name"], why))


def verify(rig, made):
    """Does the motion do what it says, measured on what ships -- the baked
    62 bones, not the rig that posed them.

    The strike checks are the ones this file always had. It puts the fist
    or the foot where the frame says it is and measures how far forward of
    the guard it got. It is not decoration: it caught the root bone's axes
    being wrong -- the root points UP, so the forward shift was being
    written into the vertical and was driving him into the floor -- and it
    caught the torso twist dragging the already-aimed arm off target, which
    turned the hook 10 cm BACKWARDS.

    Added with the move onto the IK rig, and each proved to fail by --bite:
    every planted foot is still where the plan put it (a rolled foot's ball
    may move the 2.4 cm arc its roll about the floor allows, and nothing
    more); a jab and a cross go down a straight line; a loop closes; a walk
    lifts its feet and never crosses them; a dash leaves the floor and comes
    back to the guard; a block puts the fists at the forehead; a hit sends
    the head back, the heavy one further; Down ends on the floor and never
    goes through it; GetUp starts where Down ended and ends in the guard.
    """
    import bpy
    import rig_full_ik as CR
    fails = []

    def at(frame, bone):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        return (rig.matrix_world @ rig.pose.bones[bone].matrix).translation.copy()

    def pose_of(act, frame):
        rig.animation_data.action = act
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        return {b.name: (rig.matrix_world @ b.matrix).translation.copy() for b in rig.pose.bones}

    def apart(a, b):
        return max((a[n] - b[n]).length for n in a)

    by_name = {c["move"] + "@" + c["boss"]: (c, act) for c, act, _f in made}
    for c, act, frames in made:
        rig.animation_data.action = act
        N = c["frames"]
        # ---- planted feet stay planted
        worst = 0.0
        for s, marks in (c.get("plant") or {}).items():
            for f, (want, roll) in marks.items():
                got = at(f + 1, "ball_" + s)
                allow = 0.024 * 2.0 * math.sin(roll * CR.TOE_ROLL / 2.0) + 0.002
                slide = math.hypot(got.x - want.x, got.y - want.y)
                worst = max(worst, slide - allow + 0.002)
                if slide > allow:
                    fails.append("%s: the planted %s foot slides %.1f cm on frame %d" % (c["name"], s, slide * 100, f + 1))
                    break
        c["slide_mm"] = max(0.0, worst) * 1000.0
        # ---- knees bend the way knees bend: each knee's turn against its
        # rest, about its hinge, inside the side add_ik found by bending it
        # (the limits stay on the pose bones when the controls are stripped)
        for s in SIDES:
            calf, thigh = rig.pose.bones["calf_" + s], rig.pose.bones["thigh_" + s]
            rest = thigh.bone.matrix_local.inverted() @ calf.bone.matrix_local
            bad = None
            for f in range(1, N + 1, 2):
                bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
                x = (rest.inverted() @ (thigh.matrix.inverted() @ calf.matrix)).to_euler("XYZ").x
                if x < calf.ik_min_x - 0.02 or x > calf.ik_max_x + 0.02:
                    bad = (f, math.degrees(min(abs(x - calf.ik_min_x), abs(x - calf.ik_max_x))))
                    break
            if bad:
                fails.append("%s: the %s knee bends backwards, %.0f deg past straight on frame %d" % (
                    c["name"], s, bad[1], bad[0]))
        # ---- the hands (2026-09-24, "the best position for arm and hand"):
        # every frame of every clip is thrown with closed fists; in the
        # guard, a walk and a dash both fists are up in front of the face,
        # the elbows inside the shoulders, the wrists straight and the palms
        # toward him; and a strike's other hand stays up, covering.
        hands_check(c, rig, fails)
        # ---- loops close: the step from the last frame to the first is a
        # step like any other
        if c.get("loop"):
            first = pose_of(act, 1); last = pose_of(act, N)
            step = max(apart(pose_of(act, f + 1), pose_of(act, f)) for f in range(1, N))
            wrap = apart(first, last)
            if wrap > 1.5 * step + 0.002:
                fails.append("%s: the loop jumps %.1f cm from its last frame to its first (a step is %.1f)" % (
                    c["name"], wrap * 100, step * 100))
            rig.animation_data.action = act
        if c["kind"] == "strike":
            tip = TIP[c["limb"]]
            guard = at(1, tip)
            contact = at(c["contact"] + 1, tip)
            end = at(N, tip)
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
            for f in (1, c["contact"] + 1, N):
                lowest = min(at(f, "ball_l").z, at(f, "ball_r").z)
                if lowest > 0.045:
                    fails.append("%s has both feet %.0f cm off the ground on frame %d"
                                 % (c["name"], lowest * 100, f))
            # a knee and a kick lift the hip; a punch does not. 8 cm, unchanged
            # since the FK build: the support foot rolling onto its ball buys
            # the rise honestly, and relaxing it would only hide the next
            # regression.
            if c["limb"] == "rear_leg" and rise < 8.0:
                fails.append("%s is a leg strike that lifts the hip %.1f cm" % (c["name"], rise))
            # and he leans the way the browser says he leans. A spine bone's
            # local X runs along world +X, so the obvious sign is the wrong one
            # and a jab ends up leaning away from the man it is aimed at.
            # Measured head against pelvis, not head against the world: since
            # the move onto the IK rig the body travels -- onto the support
            # foot for a kick -- and a man whose hips step forward 30 cm
            # while he leans back has a head that went forward. A spin is
            # turned back out first, about the vertical, by its own angle.
            lean = inclination(c["move"])
            if abs(lean) > 0.04:
                import mathutils
                turns = MOVES[c["move"]][3]
                ang = turns * 2.0 * math.pi * (c["contact"] / float(FPS)) / c["seconds"]
                rel_g = at(1, "head") - at(1, "pelvis")
                rel_c = mathutils.Matrix.Rotation(-ang, 3, "Z") @ (at(c["contact"] + 1, "head") - at(c["contact"] + 1, "pelvis"))
                went = (rel_g.y - rel_c.y) * 100.0          # + is forward
                c["lean_cm"] = went
                if lean > 0 and went < 2.0:
                    fails.append("%s should lean in and the head went %.1f cm" % (c["name"], went))
                if lean < 0 and went > -2.0:
                    fails.append("%s should lean away and the head went %.1f cm" % (c["name"], went))
            # a straight punch is straight: the wrist goes down the line from
            # the guard to the contact, off it by no more than 5 mm
            if c["move"] in LINE:
                s = {"lead_arm": "l", "rear_arm": "r"}[c["limb"]]
                a, b = at(1, "hand_" + s), at(c["contact"] + 1, "hand_" + s)
                off = 0.0
                for f in range(1, c["contact"] + 2):
                    p = at(f, "hand_" + s)
                    ab = b - a
                    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
                    off = max(off, (p - (a + ab * t)).length)
                c["line_mm"] = off * 1000.0
                if off > 0.005:
                    fails.append("%s: the fist runs %.1f cm off the straight line to its target" % (c["name"], off * 100))
        elif c["kind"] == "walk":
            ground = min(at(1, "ball_l").z, at(1, "ball_r").z)
            for s in SIDES:
                high = max(at(f, "ball_" + s).z for f in range(1, N + 1)) - ground
                if high < 0.03:
                    fails.append("%s: the %s foot never lifts past %.1f cm -- it shuffles" % (c["name"], s, high * 100))
            gap = min(at(f, "ball_l").x - at(f, "ball_r").x for f in range(1, N + 1))
            c["gap_cm"] = gap * 100.0
            if gap < 0.08:
                fails.append("%s: the feet cross -- %.1f cm between them at the closest" % (c["name"], gap * 100))
        elif c["kind"] == "dash":
            ground = min(at(1, "ball_l").z, at(1, "ball_r").z)
            air = max(min(at(f, "ball_l").z, at(f, "ball_r").z) - ground for f in range(1, N + 1))
            if air < 0.03:
                fails.append("%s: both feet leave the floor by only %.1f cm" % (c["name"], air * 100))
            back = apart(pose_of(act, 1), pose_of(act, N))
            if back > 0.01:
                fails.append("%s: ends %.1f cm from the guard it started in" % (c["name"], back * 100))
            rig.animation_data.action = act
        elif c["kind"] == "block":
            for f in range(1, N + 1, 6):
                head = at(f, "head")
                for s in SIDES:
                    fist = at(f, "hand_end_" + s)
                    if fist.z < head.z - 0.03 or fist.y > head.y:
                        fails.append("%s: the %s fist is not up at the forehead on frame %d" % (c["name"], s, f))
                        break
        elif c["kind"] == "hit":
            h0 = at(1, "head")
            c["head_back_cm"] = max((at(f, "head").y - h0.y) for f in range(1, N + 1)) * 100.0
            if c["head_back_cm"] < 6.0:
                fails.append("%s: the head goes back only %.1f cm" % (c["name"], c["head_back_cm"]))
        elif c["kind"] in ("down", "getup"):
            for f in range(1, N + 1):
                low = min(at(f, n).z for n in ("spine_01", "spine_02", "spine_03", "neck_01", "head"))
                pel = at(f, "pelvis").z
                if low < 0.06 or pel < 0.08:
                    fails.append("%s: goes through the floor on frame %d (spine %.1f cm, pelvis %.1f cm)" % (
                        c["name"], f, low * 100, pel * 100))
                    break
            if c["kind"] == "down":
                pel, neck = at(N, "pelvis"), at(N, "neck_01")
                back = math.degrees((neck - pel).angle(__import__("mathutils").Vector((0, 0, 1))))
                c["down_deg"] = back
                if pel.z > 0.25 or back < 60.0 or neck.y < pel.y:
                    fails.append("%s: does not end on the floor (pelvis %.0f cm up, torso %.0f deg back)" % (
                        c["name"], pel.z * 100, back))
    # ---- the pairs
    for key in {c["boss"] for c, _a, _f in made}:
        light, heavy = by_name.get("Hit_Light@" + key), by_name.get("Hit_Heavy@" + key)
        if light and heavy and heavy[0]["head_back_cm"] <= light[0]["head_back_cm"]:
            fails.append("a heavy hit sends the head back no further than a light one")
        down, getup, guard = by_name.get("Down@" + key), by_name.get("GetUp@" + key), by_name.get("Guard@" + key)
        if down and getup:
            gap = apart(pose_of(down[1], down[0]["frames"]), pose_of(getup[1], 1))
            if gap > 0.01:
                fails.append("GetUp does not start where Down ends: %.1f cm apart" % (gap * 100))
        if getup and guard:
            gap = apart(pose_of(getup[1], getup[0]["frames"]), pose_of(guard[1], 1))
            if gap > 0.01:
                fails.append("GetUp does not end in the guard: %.1f cm from it" % (gap * 100))
    rig.animation_data.action = None
    assert not fails, "the motion does not move:\n  " + "\n  ".join(fails)
    strikes = [c for c, _a, _f in made if c["kind"] == "strike"]
    if strikes:
        print("        every strike travels; the shortest reaches %.0f cm" % min(c["reach_cm"] for c in strikes))
    print("        planted feet: worst slide past the roll's own arc %.1f mm over %d clips" % (
        max(c.get("slide_mm", 0.0) for c, _a, _f in made), len(made)))
    lines = [c["line_mm"] for c in strikes if c.get("line_mm") is not None]
    if lines:
        print("        straight punches: worst %.1f mm off the line" % max(lines))


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


def contact_sheet(rig, made, out_dir, filename):
    """A strip per clip, drawn as the skeleton itself.

    An armature does not render, and binding a mesh to judge timing is a
    ten-minute build for something an animator would not look at anyway: you
    read a strike off the rig. Each row is one clip sampled across its whole
    length, seen three-quarters from his right -- near the view the browser
    draws him in -- with the contact frame marked, the striking limb picked
    out, and every planted foot drawn as a ring where it is meant to be.
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
    for c, act, _frames in made:
        rig.animation_data.action = act
        cells = []
        # framed on the row's mean pelvis, not each frame's, so a man who
        # travels -- onto his support foot, falling, getting up -- is seen
        # to, and stays in the frame while he does
        sampled = [1 + int(round(i * (c["frames"] - 1) / float(SAMPLES - 1))) for i in range(SAMPLES)]
        base = sum((joints(f)["pelvis"][0] for f in sampled), __import__("mathutils").Vector()) / len(sampled)
        for i in range(SAMPLES):
            f = 1 + int(round(i * (c["frames"] - 1) / float(SAMPLES - 1)))
            J = joints(f)
            im = Image.new("RGB", (SW, SH), (14, 16, 22))
            d = ImageDraw.Draw(im)
            # Three-quarters, not side-on. A pure side view cannot tell a
            # bent torso from a shoulder line turned edge-on, and it fooled
            # me into reading the round kick's counter-rotating arm as a man
            # folded in half. At 35 degrees both read.
            ca, sa = math.cos(math.radians(35.0)), math.sin(math.radians(35.0))

            def px(v):
                u = (v.x - base.x) * sa - (v.y - base.y) * ca
                return (SW * 0.5 + u * 150.0, SH - 16 - v.z * 92.0)
            lit = {"lead_arm": ("upperarm_l", "lowerarm_l", "hand_l"),
                   "rear_arm": ("upperarm_r", "lowerarm_r", "hand_r"),
                   "rear_leg": ("thigh_r", "calf_r", "foot_r")}.get(c["limb"], ())
            d.line([(0, SH - 16), (SW, SH - 16)], fill=(34, 38, 50))
            for s, marks in (c.get("plant") or {}).items():
                if f - 1 in marks:
                    x, y = px(marks[f - 1][0])
                    d.ellipse([x - 6, y - 3, x + 6, y + 3], outline=(80, 170, 120))
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
    out = os.path.join(out_dir, filename)
    sheet.save(out)
    rig.animation_data.action = None
    print("        contact sheet %s (%dx%d)" % (os.path.basename(out), W, H))
    return out


# ======================================================================= bite
def bite():
    """Each motion check added with the IK rig, made to fail by breaking the
    one thing it guards -- and the same clips, unbroken, passing. A check
    that cannot fail is not a check."""
    # Two cases break on the boxer's guard: Saud's MMA stance is solved with
    # its knees forward and its lead palm squared, so on it those two
    # mechanisms can fail without showing -- the boxer's cannot.
    every = {c["name"]: c for c in plan(("saud", "street"))}
    cases = [
        ("planted feet",   "plant",  ["A_Saud_Cross", "A_Saud_Kick"],  "slides"),
        ("knees forward",  "knee",   ["A_Street_Guard"],                 "bends backwards"),
        ("straight punch", "line",   ["A_Saud_Jab"],                   "off the straight line"),
        ("feet cross",     "cross",  ["A_Saud_Walk_Left"],             "the feet cross"),
        ("through floor",  "sink",   ["A_Saud_Down"],                  "through the floor"),
        ("getup start",    "getup",  ["A_Saud_Down", "A_Saud_GetUp"],  "does not start where Down ends"),
        ("closed fists",   "fists",  ["A_Saud_Guard"],                 "hand is open"),
        ("guard hands",    "guard",  ["A_Saud_Guard"],                 "not up in front of the face"),
        ("palms in",       "palms",  ["A_Street_Guard"],                 "palm faces the opponent"),
        ("covering hand",  "tuck",   ["A_Street_Cross"],               "not up in front of the face"),
    ]
    results = []
    for label, sab, names, expect in cases:
        for broken in (False, True):
            import motion_ik as M
            SABOTAGE.clear(); M.SABOTAGE_HANDS.clear()
            if broken:
                SABOTAGE.add(sab)
                if sab == "fists":
                    M.SABOTAGE_HANDS.add("fists")
            clips = [dict(every[n]) for n in names]
            rig, made = author_all(clips)
            try:
                verify(rig, made)
                msg = None
            except AssertionError as e:
                msg = str(e)
            if broken:
                results.append((label, msg is not None and expect in msg,
                                (msg or "did not bite").split("\n")[1].strip() if msg and "\n" in msg else (msg or "did not bite")))
            else:
                results.append((label + " (clean)", msg is None, msg.split("\n")[1].strip() if msg else "passes"))
    SABOTAGE.clear()
    import motion_ik as M
    M.SABOTAGE_HANDS.clear()
    print("\n%-26s %s" % ("check", "when its mechanism is broken -- and when it is not"))
    for label, ok, msg in results:
        print("  %-24s %s  %s" % (label, "OK     " if ok else "WRONG  ", msg[:96]))
    n = sum(1 for _, ok, _ in results if ok)
    print("  %d of %d as they should be" % (n, len(results)))
    return n == len(results)


# ======================================================================= main
def main():
    argv = sys.argv[1:]
    root = os.path.join(PROJECT, "Content", "Animation")
    if "--out" in argv:
        root = os.path.abspath(argv[argv.index("--out") + 1])
    who = ("bosses", "saud", "street")
    if "--who" in argv:
        who = (argv[argv.index("--who") + 1],)
        assert who[0] in FOLDER, "--who is one of %s" % sorted(FOLDER)

    clips = plan(who)
    check(clips)
    if "--check" in argv:
        print("checks pass: %d clips" % len(clips))
        return
    if "--bite" in argv:
        sys.exit(0 if bite() else 1)
    describe(clips)
    if "--describe" in argv:
        return
    build(clips, root, sheet="--sheet" in argv)


if __name__ == "__main__":
    main()
