"""Hits, for build_motion.py: the blow a man takes, the blows that land in a
row, the ones that put him down, and both men of one exchange together.

    build_motion.py plans, authors, checks and exports these with the rest;
    nothing here runs on its own. build_motion binds itself as `B`.

WHAT IT ADDS, per motion set (Saud, the street men, AL-WAHSH, AL-SAQR, ZAYOS):

  REACTIONS  one per kind of blow, not one per weight. Until now a man had
             Hit_Light and Hit_Heavy: the head thrown straight back, the
             same for a jab, a hook to the jaw and a knee to the belly.
             Hit_Head_Straight(_Light)  a jab or a cross: the head snaps back
             Hit_Head_Side              a hook on his left jaw: the face turned
                                        to his right, the body after it
             Hit_Body_Front             a knee: he folds over it, hands to the belly
             Hit_Body_Side              a kick to the left ribs: he curls round
                                        it, the left elbow comes down on them
             Each is as long as the engine holds the hit (0.34 s, 0.22 light),
             rises in 40 ms and falls back into the guard it started in.
  FALLS      Down_Side (a spin kick or a hook puts him down turning) and
             Down_Fold (a knee: folded first, then back). Both END exactly
             where Down does, so GetUp follows either. The bosses get Down
             and GetUp too; they had none.
  COMBOS     A_<Set>_Combo_<A>_<B>..: the set's own strikes chained, each
             starting as the one before is a third of the way back, so every
             one lands at the reach it has alone.
  PAIRS      A_<Victim>_Pair_<Attacker>_<Move>: the victim's side of one
             exchange, frame for frame against the attacker's clip -- guard,
             then each blow's reaction at its contact frame, a finisher's fall.
             Where he stands is solved from the contacts and written to
             Content/Animation/DT_Pairs.csv.

WHAT IT DOES NOT DO. The engine picks a reaction by the blow (SaudFeel::
BlowOf / Pick) and falls back to Hit_Light / Hit_Heavy / Down where a clip is
missing. Combos and pairs are not wired: the game has no montage or
synchronised-playback system to hand them to; they are written, checked and
named in the manifests for the day it does.
"""
import math, os

B = None        # build_motion, bound by it (it runs as __main__)

# which reaction each attack row lands as; the finisher puts him down
BLOW = {"Jab": "Head_Straight_Light", "Cross": "Head_Straight", "Hook": "Head_Side",
        "Kick": "Body_Side", "Knee": "Body_Front", "Special": "Down_Side"}
REACTS = ("Head_Straight_Light", "Head_Straight", "Head_Side", "Body_Front", "Body_Side")
FALLS = ("Down_Side", "Down_Fold")

# A reaction at its peak, as numbers that add: two blows landing on top of
# each other are their sum. Saud faces -Y, +X is his left.
#   lean      the spine, + forward            hx hy hz  the hips, metres
#   side      the hips tipped, + to his left  twist     the spine, + right shoulder forward
#   pitch     the head, + back                roll      the head, + to his left
#   head_turn the face, + to his left         throw     the arms flung (browser's hit arms)
#   belly     both fists to the belly         ribs      the left elbow down on the ribs
KEYS = ("lean", "hx", "hy", "hz", "side", "twist", "pitch", "roll", "head_turn", "throw", "belly", "ribs")
REACT = {
    # index.html:1509-1511 is this one: back, the hip down, the arms thrown
    "Head_Straight": dict(lean=-0.32, hy=0.035, hz=-0.025, pitch=0.50, throw=0.55),
    # struck on his left jaw by a hook from a man facing him: the face goes
    # round to his right and down that side, the shoulders a little after it
    "Head_Side": dict(lean=-0.08, hx=-0.035, hy=0.010, hz=-0.020, side=-0.16, twist=-0.30,
                      pitch=0.10, roll=-0.45, head_turn=-0.65, throw=0.30),
    # a knee in the belly: folded over it, the hips back, both fists down
    "Body_Front": dict(lean=0.50, hy=0.060, hz=-0.060, pitch=-0.30, belly=1.0),
    # a round kick in the left ribs: he curls round it toward the blow, the
    # hips pushed away from it, the left elbow down to cover
    "Body_Side": dict(lean=0.16, hx=-0.045, hy=0.010, hz=-0.040, side=0.22, twist=-0.12,
                      pitch=-0.08, roll=0.28, ribs=1.0),
}
# clip -> (shape, peak, heavy)
PEAK = {"Head_Straight_Light": ("Head_Straight", 0.6, False), "Head_Straight": ("Head_Straight", 1.0, True),
        "Head_Side": ("Head_Side", 1.0, True), "Body_Front": ("Body_Front", 1.0, True),
        "Body_Side": ("Body_Side", 1.0, True)}
RISE, HOLD = 0.04, 0.06
# the browser's thrown arms (build_motion.HIT_AIMS), arms only
THROWN = ("upperarm_l", "lowerarm_l", "hand_l", "upperarm_r", "lowerarm_r", "hand_r")

# What each set chains. Only a set's own strikes, in orders a fighter of
# that style throws them; ZAYOS still only punches.
COMBOS = {
    "Saud":   (("Jab", "Cross"), ("Jab", "Cross", "Hook"), ("Jab", "Cross", "Kick")),
    "Street": (("Jab", "Cross"), ("Jab", "Cross", "Hook")),
    "Boss":   (("Jab", "Cross", "Hook"), ("Jab", "Cross", "Knee")),
    "Saqr":   (("Jab", "Kick"), ("Jab", "Cross", "Kick")),
    "Zayos":  (("Jab", "Cross", "Hook"), ("Hook", "Cross")),
}
# the next strike leaves when the one before is this far back into its guard
CHAIN = 0.35
# Combos are paired only when every blow is a punch. The round kick lands 40
# degrees off to the kicker's left (the Kick shape as build_saud has it) and
# 30 cm further out than a punch, the knee 28 cm shorter: from one spot the
# victim cannot be where a punch and either of those both land, and the
# clips have no step to close it. Those combos are built; they are not paired.
PUNCHES = ("Jab", "Cross", "Hook")
# who is paired with whom: every one of the attacker's strikes and combos,
# landed on the victim
PAIRS = (("Saud", "Street"), ("Street", "Saud"), ("Boss", "Saud"), ("Saqr", "Saud"),
         ("Zayos", "Saud"), ("Saud", "Boss"), ("Saud", "Saqr"), ("Saud", "Zayos"))
SET_OF = {"Saud": "saud", "Street": "street", "Boss": "bosses", "Saqr": "bosses", "Zayos": "bosses"}
# where on the victim each blow lands, from a bone of his, in his own frame,
# and which of the attacker's bones lands it. The head joint is at the eye
# line on this skeleton (1.672 at rest, the chin 1.572), so the chin is 10 cm
# under it and 10 in front.
# The last number is how big the mark is: a blow lands if it arrives within
# it -- the chin and the jaw are a fist across, the ribs and the chest a
# hand's length up and down.
TARGET = {"Jab": ("head", (0.0, -0.10, -0.10), 0.08), "Cross": ("head", (0.0, -0.10, -0.10), 0.08),
          "Hook": ("head", (0.05, -0.06, -0.09), 0.08),              # the point of his left jaw
          "Kick": ("spine_03", (0.13, -0.02, -0.06), 0.12),          # his left ribs, under the arm
          "Knee": ("spine_02", (0.0, -0.14, 0.02), 0.12),            # the solar plexus
          "Special": ("spine_02", (0.0, -0.14, 0.08), 0.13)}         # the chest, low
TIP = {"Jab": "hand_end_l", "Cross": "hand_end_r", "Hook": "hand_end_r", "Kick": "ball_r",
       "Knee": "calf_r", "Special": "ball_r"}
MISS_MORE = 0.02        # a later blow of a combo may land this much wider:
                        # the man it lands on is already reeling
CHESTS = 0.35           # two chests never closer than this


def FPS():
    return B.FPS


# ======================================================================= plan
def _from(base, **kw):
    d = dict(base)
    d.update(su=0.0, ac=0.0, rc=0.0, contact=-1, limb=None, phase_two=False, loop=False)
    d.pop("dir", None)
    d.update(kw)
    d["frames"] = int(round(d["seconds"] * FPS()))
    d["name"] = "A_%s_%s" % (d["boss"], d["move"])
    return d


def combo_seq(moves, attacks):
    seq, t = [], 0.0
    for mv in moves:
        a = attacks[mv]
        su, ac, rc = float(a["Startup"]), float(a["Active"]), float(a["Recovery"])
        seq.append(dict(move=mv, start=t, su=su, ac=ac, rc=rc))
        t += su + ac + CHAIN * rc
    return seq


def plan(clips, who):
    """Everything this adds, from the clips build_motion already planned."""
    attacks = {r["Name"]: r for r in B.read_csv("DT_Attacks.csv")}
    eng = B.engine_timings()
    out = []
    guards = {c["boss"]: c for c in clips if c["kind"] == "guard"}
    for key, gc in guards.items():
        for r in REACTS:
            _shape, _peak, heavy = PEAK[r]
            secs = eng["hit_heavy"] if heavy else eng["hit_light"]
            out.append(_from(gc, move="Hit_" + r, kind="react", state="Hit", seconds=secs, blow=r))
        if key in B.BOSSES:
            out.append(_from(gc, move="Down", kind="down", state="Down", seconds=eng["down"]))
            out.append(_from(gc, move="GetUp", kind="getup", state="Idle", seconds=eng["getup"]))
        for r in FALLS:
            out.append(_from(gc, move=r, kind="fall", state="Down", seconds=eng["down"], blow=r))
        # the end of a fight, one way or the other (2026-09-28)
        out.append(_from(gc, move="Death", kind="death", state="Dead", seconds=eng["death"]))
        out.append(_from(gc, move="Victory", kind="victory", state="Idle", seconds=VICTORY_SECONDS))
        for moves in COMBOS[key]:
            seq = combo_seq(moves, attacks)
            end = seq[-1]["start"] + seq[-1]["su"] + seq[-1]["ac"] + seq[-1]["rc"]
            contacts = [int(round((m["start"] + m["su"]) * FPS())) for m in seq]
            out.append(_from(gc, move="Combo_" + "_".join(moves), kind="combo", state="Attack",
                             seconds=end, seq=seq, contacts=contacts, contact=contacts[0],
                             su=seq[0]["su"], moves=list(moves)))
    # the pairs, where both men's sets are in this build
    allc = clips + out
    by = {(c["boss"], c["move"]): c for c in allc}
    for att, vic in PAIRS:
        if att not in guards or vic not in guards:
            continue
        for ac in [c for c in allc if c["boss"] == att and (c["kind"] == "strike" or (
                c["kind"] == "combo" and all(m in PUNCHES for m in c["moves"])))]:
            if ac["kind"] == "strike":
                blows = [(ac["contact"], ac["move"])]
            else:
                blows = list(zip(ac["contacts"], ac["moves"]))
            knock = None
            if blows[-1][1] == "Special":
                knock = (blows[-1][0], "Down_Side")
            elif ac["kind"] == "combo" and blows[-1][1] == "Knee":
                knock = (blows[-1][0], "Down_Fold")
            n = ac["frames"]
            for f, mv in blows:
                if knock and f == knock[0]:
                    n = max(n, f + by[(vic, knock[1])]["frames"])
                else:
                    r = BLOW[mv]
                    n = max(n, f + by[(vic, "Hit_" + r)]["frames"])
            d = _from(guards[vic], move="Pair_%s_%s" % (att, ac["move"]), kind="pair", state="Hit",
                      seconds=n / float(FPS()), attacker=att, attack=ac["move"], att_name=ac["name"],
                      blows=blows, knock=knock, contacts=[f for f, _m in blows])
            d["frames"] = n
            d["contact"] = blows[0][0]
            d["su"] = blows[0][0] / float(FPS())       # "startup": the first blow's arrival
            out.append(d)
    return out


def check(clips):
    """The plan's own rules for what this adds."""
    eng = B.engine_timings()
    sets = {c["boss"] for c in clips if c["kind"] == "guard"}
    names = {c["name"] for c in clips}
    for key in sets:
        for r in REACTS:
            assert "A_%s_Hit_%s" % (key, r) in names, "%s has no %s reaction" % (key, r)
        for r in FALLS + ("Down", "GetUp", "Death", "Victory"):
            assert "A_%s_%s" % (key, r) in names, "%s has no %s" % (key, r)
        mine = {c["move"] for c in clips if c["boss"] == key and c["kind"] == "strike"}
        for moves in COMBOS[key]:
            assert set(moves) <= mine, "%s chains %s and does not throw %s" % (key, moves, sorted(set(moves) - mine))
    for c in clips:
        if c["kind"] == "react":
            want = eng["hit_heavy"] if PEAK[c["blow"]][2] else eng["hit_light"]
            assert abs(c["frames"] / float(FPS()) - want) <= 1.0 / FPS(), "%s is not the engine's hit" % c["name"]
        if c["kind"] == "fall":
            assert abs(c["frames"] / float(FPS()) - eng["down"]) <= 1.0 / FPS(), "%s is not the engine's Down" % c["name"]
        if c["kind"] == "death":
            assert abs(c["frames"] / float(FPS()) - eng["death"]) <= 1.0 / FPS(), "%s is not the engine's dying Down" % c["name"]
        if c["kind"] == "victory":
            assert abs(c["frames"] / float(FPS()) - VICTORY_SECONDS) <= 1.0 / FPS(), "%s is not %.1fs" % (c["name"], VICTORY_SECONDS)
        if c["kind"] in ("combo", "pair"):
            cs = c["contacts"]
            assert cs == sorted(cs) and len(set(cs)) == len(cs), "%s: contacts out of order %s" % (c["name"], cs)
            assert 0 <= cs[0] and cs[-1] < c["frames"], "%s: a contact outside the clip" % c["name"]
        if c["kind"] == "combo":
            for m, f in zip(c["seq"], c["contacts"]):
                assert abs(f / float(FPS()) - (m["start"] + m["su"])) <= 1.0 / FPS(), "%s: %s off its startup" % (c["name"], m["move"])
        if c["kind"] == "pair":
            assert "A_%s_%s" % (c["attacker"], c["attack"]) in names, "%s pairs a clip that is not built" % c["name"]
    return True


# ============================================================ authoring
def ease(t):
    return B.ease(t)


def env(t, T):
    """A reaction's weight at t seconds after the blow, over a clip whose
    last frame is T: up in RISE, held to HOLD, back to nothing at T."""
    if t < 0.0 or t > T:
        return 0.0
    rise = ease(min(1.0, t / RISE))
    fall = 1.0 - ease(max(0.0, (t - HOLD) / max(1e-6, T - HOLD)))
    return rise * fall


def react_len(blow, eng):
    return int(round((eng["hit_heavy"] if PEAK[blow][2] else eng["hit_light"]) * FPS()))


def weights(blows, t, eng):
    """Every reaction under way at t, summed: [(frame, blow)] -> params."""
    P = {k: 0.0 for k in KEYS}
    for f, blow in blows:
        shape, peak, _h = PEAK[blow]
        T = (react_len(blow, eng) - 1) / float(FPS())
        w = peak * env(t - f / float(FPS()), T)
        if w <= 0.0:
            continue
        for k, v in REACT[shape].items():
            P[k] += v * w
    return P


def _signed(P):
    """--bite react_sign: every reaction thrown the wrong way."""
    if "react_sign" not in B.SABOTAGE:
        return P
    Q = dict(P)
    for k in ("lean", "hx", "hy", "side", "twist", "pitch", "roll", "head_turn"):
        Q[k] = -Q[k]
    return Q


def react_extra(aims_g, P):
    """The reaction as build_motion.body_frame / floor_frame take it."""
    import mathutils
    from mathutils import Vector, Matrix
    P = _signed(P)
    aims = dict(aims_g)
    # the head: back (+pitch) is about -X, to his left (+roll) about +Y
    R = Matrix.Rotation(P["roll"], 3, "Y") @ Matrix.Rotation(-P["pitch"], 3, "X")
    Rn = Matrix.Rotation(P["roll"] * 0.4, 3, "Y") @ Matrix.Rotation(-P["pitch"] * 0.4, 3, "X")
    for nm, r in (("neck_01", Rn), ("head", R)):
        if nm in aims:
            aims[nm] = tuple((r @ Vector(aims[nm])).normalized())
    if P["throw"] > 0.0:
        thrown = {k: v for k, v in B.HIT_AIMS.items() if k in THROWN}
        aims = B.aims_at(aims, thrown, min(1.0, P["throw"]), 1.0)
    side = {"l": 1.0, "r": -1.0}

    def hand(s):
        def at(fk, m, s=s):
            m = m.copy()
            p = m.translation
            if P["belly"] > 0.0:
                p = p.lerp(fk["sh_" + s] + Vector((-0.10 * side[s], -0.22, -0.40)), min(1.0, P["belly"]))
            if P["ribs"] > 0.0 and s == "l":
                p = p.lerp(fk["sh_" + s] + Vector((-0.04, -0.15, -0.24)), min(1.0, P["ribs"]))
            m.translation = p
            return m
        return at
    tw = P["twist"]
    return dict(aims=aims, lean=P["lean"], hx=P["hx"], hy=P["hy"], hz=P["hz"], side=P["side"],
                twist={"spine_01": tw * 0.30, "spine_02": tw * 0.35, "spine_03": tw * 0.35} if tw else None,
                head_turn=P["head_turn"], hands={s: hand(s) for s in B.SIDES})


def stand_frame(au, g, aims_g, P):
    x = react_extra(aims_g, P)
    hands = {s: (lambda fk, s=s: x["hands"][s](fk, fk["hand_" + s])) for s in B.SIDES}
    loc, world, _fk, _d = B.body_frame(au, g, x["aims"], B.planted_feet(g), lean=x["lean"],
                                       hips=(x["hx"], x["hy"], x["hz"]), side_tilt=x["side"],
                                       twist=x["twist"], head_turn=x["head_turn"],
                                       hands=hands, settle=B.SIDES)
    return loc, world


def _norm(keys):
    return [(u, dict(dict(side=0.0, turn=0.0, fold=0.0), **p)) for u, p in keys]


def side_keys(g):
    """Down_Side: a hook or a spin kick takes him round to his right as he
    goes, onto that hip, and he ends where Down ends."""
    end = dict(B.down_keys(g)[-1][1])
    gz = g["pelvis"].translation.z + g["dz"]
    last = dict(end, side=(0.30 if "fall_end" in B.SABOTAGE else 0.0))
    return _norm([(0.00, dict(pz=gz, py=0.00, tilt=0.00, rear=0.0, hand=0.0, look=0.0)),
                  (0.16, dict(pz=gz - 0.05, py=0.02, tilt=0.10, rear=0.0, hand=0.0, look=0.1, side=-0.30, turn=-0.35)),
                  (0.42, dict(pz=0.36, py=0.24, tilt=0.45, rear=1.0, hand=0.25, look=0.5, side=-0.38, turn=-0.45)),
                  (0.72, dict(pz=0.15, py=0.44, tilt=1.05, rear=1.0, hand=0.9, look=1.0, side=-0.12, turn=-0.15)),
                  (1.00, last)])


def fold_keys(g):
    """Down_Fold: a knee folds him over it first, and then he goes back."""
    end = dict(B.down_keys(g)[-1][1])
    gz = g["pelvis"].translation.z + g["dz"]
    last = dict(end, fold=(0.30 if "fall_end" in B.SABOTAGE else 0.0))
    return _norm([(0.00, dict(pz=gz, py=0.00, tilt=0.00, rear=0.0, hand=0.0, look=0.0)),
                  (0.18, dict(pz=gz - 0.10, py=0.05, tilt=-0.25, rear=0.0, hand=0.0, look=0.0, fold=0.35)),
                  (0.45, dict(pz=0.40, py=0.16, tilt=-0.05, rear=1.0, hand=0.1, look=0.2, fold=0.25)),
                  (0.74, dict(pz=0.15, py=0.44, tilt=1.00, rear=1.0, hand=0.9, look=1.0)),
                  (1.00, last)])


FALL_KEYS = {"Down_Side": side_keys, "Down_Fold": fold_keys}


# ======================================================== death and victory
# 2026-09-28, "full suite motions ik". A killing blow puts a man in Down for
# the engine's 1.05 s (FighterBase: DownRemaining = Health <= 0 ? 1.05 : 0.85)
# and then Dead, which holds the last frame; he used to play Down there and
# stay propped on his hands. Death is its own fall: back and flat, arms down
# by his sides, the head let go. Victory is the win: straightening up, the
# chin up, a fist raised -- whose, by the man -- held.
VICTORY_SECONDS = 2.0          # SaudFeel::VictorySeconds is this, and the harness holds it to the clip
VICTORY_ARMS = {"Saud": ("r",), "Street": ("r",), "Boss": ("l", "r"), "Saqr": ("l",), "Zayos": ("l", "r")}
RAISE = 0.52                   # the raised wrist above its shoulder, metres


def death_keys(g):
    """Back and down past where Down stops, onto the floor flat; the pelvis
    goes back as far as the planted feet let the legs reach (0.62: at 0.78
    the leg could not, and the settle sank him through the floor)."""
    gz = g["pelvis"].translation.z + g["dz"]
    if "death_sit" in B.SABOTAGE:
        end = dict(pz=0.30, py=0.45, tilt=1.00, rear=1.0, hand=1.0, look=0.4)
    else:
        end = dict(pz=0.11, py=0.62, tilt=1.52, rear=1.0, hand=1.0, look=0.15)
    return _norm([(0.00, dict(pz=gz, py=0.00, tilt=0.00, rear=0.0, hand=0.0, look=0.0)),
                  (0.14, dict(pz=gz - 0.07, py=0.03, tilt=0.18, rear=0.0, hand=0.0, look=0.1)),
                  (0.40, dict(pz=0.42, py=0.26, tilt=0.62, rear=1.0, hand=0.3, look=0.2)),
                  (0.66, dict(pz=0.17, py=0.50, tilt=1.20, rear=1.0, hand=0.85, look=0.2)),
                  (0.86, end), (1.00, dict(end))])


def author_death(au, c, S):
    aims, g = _guard(au, c, S)
    keys = death_keys(g)
    N = c["frames"]
    frames, plant = [], {s: {} for s in B.SIDES}
    for f in range(N):
        (loc, world, moving), p = _fall_at(au, g, aims, keys, f / float(N - 1), 1.0 / (N - 1), None)
        frames.append((loc, world))
        plant["l"][f] = (g["ball_l"].copy(), 0.0)
        if not moving:
            plant["r"][f] = (g["ball_r"] + B.floor_beside(g) * p["rear"], 0.0)
    c["plant"] = plant
    return frames


def author_victory(au, c, S):
    """From the guard: up out of the stance, the chin up, the raised fist
    (or both) straight up over its shoulder, the other to the chest; in
    0.45 s on the browser's ease, then held, breathing."""
    from mathutils import Vector
    aims, g = _guard(au, c, S)
    up = VICTORY_ARMS.get(c["boss"], ("r",))
    lift = RAISE * (0.2 if "victory_low" in B.SABOTAGE else 1.0)
    side = {"l": 1.0, "r": -1.0}
    raise_aims = {}
    for s in up:
        x = side[s]
        raise_aims.update({"upperarm_" + s: (0.15 * x, -0.05, 0.99), "lowerarm_" + s: (0.05 * x, -0.08, 0.99),
                           "hand_" + s: (0.0, -0.10, 0.99)})
    frames, plant = [], {s: {} for s in B.SIDES}
    for f in range(c["frames"]):
        t = f / float(FPS())
        w = ease(min(1.0, t / 0.45))
        breath = (math.cos(2.0 * math.pi * max(0.0, t - 0.45) / 1.2) - 1.0) * 0.004 * w
        a = B.aims_at(aims, raise_aims, w, 1.0)
        P = {k: 0.0 for k in KEYS}; P["pitch"] = 0.22 * w
        x_ = react_extra(a, P)

        def hand(s, w=w):
            def at(fk, s=s, w=w):
                m = fk["hand_" + s].copy()
                if s in up:
                    want = fk["sh_" + s] + Vector((0.07 * side[s], -0.04, lift))
                else:
                    want = fk["sh_" + s] + Vector((-0.12 * side[s], -0.20, -0.20))
                m.translation = m.translation.lerp(want, w)
                return m
            return at

        def pole(s):
            if s in up:
                return lambda fk, s=s: fk["sh_" + s] + Vector((0.45 * side[s], 0.05, 0.15))
            return None
        loc, world, _fk, _d = B.body_frame(au, g, x_["aims"], B.planted_feet(g), lean=-0.10 * w,
                                           hips=(0.0, 0.0, breath), hands={s: hand(s) for s in B.SIDES},
                                           hand_poles={s: pole(s) for s in B.SIDES if pole(s)}, settle=B.SIDES)
        frames.append((loc, world))
        for s in B.SIDES:
            plant[s][f] = (g["ball_" + s].copy(), 0.0)
    c["plant"] = plant
    c["raised"] = up
    return frames


def _guard(au, c, S):
    guard, _ = S["Guard"]
    aims = B.aims_at(guard, guard, 0.0, c["stance"])
    return aims, au.capture_guard(aims)


def _fall_at(au, g, aims, keys, u, du, extra):
    p = B.keyed(keys, u)
    prev = B.keyed(keys, max(0.0, u - du))
    return B.floor_frame(au, g, aims, p, prev, extra), p


def author_react(au, c, S):
    aims, g = _guard(au, c, S)
    eng = B.engine_timings()
    frames, plant = [], {s: {} for s in B.SIDES}
    for f in range(c["frames"]):
        P = weights([(0, c["blow"])], f / float(FPS()), eng)
        frames.append(stand_frame(au, g, aims, P))
        for s in B.SIDES:
            plant[s][f] = (g["ball_" + s].copy(), 0.0)
    c["plant"] = plant
    return frames


def author_fall(au, c, S):
    aims, g = _guard(au, c, S)
    keys = FALL_KEYS[c["blow"]](g)
    N = c["frames"]
    frames, plant = [], {s: {} for s in B.SIDES}
    for f in range(N):
        (loc, world, moving), p = _fall_at(au, g, aims, keys, f / float(N - 1), 1.0 / (N - 1), None)
        frames.append((loc, world))
        plant["l"][f] = (g["ball_l"].copy(), 0.0)
        if not moving:
            plant["r"][f] = (g["ball_r"] + B.floor_beside(g) * p["rear"], 0.0)
    c["plant"] = plant
    return frames


def author_pair(au, c, S):
    """The victim's side: his guard, each blow's reaction from its contact
    frame, summed where they overlap; a finisher's fall from its contact
    with what is left of the reactions before it laid over the start."""
    aims, g = _guard(au, c, S)
    eng = B.engine_timings()
    knock = c["knock"]
    blows = [(f, BLOW[mv]) for f, mv in c["blows"] if not (knock and f == knock[0])]
    fall_n = int(round(eng["down"] * FPS()))
    keys = FALL_KEYS[knock[1]](g) if knock else None
    frames, plant = [], {s: {} for s in B.SIDES}
    for f in range(c["frames"]):
        P = weights(blows, f / float(FPS()), eng)
        if knock and f >= knock[0]:
            u = min(1.0, (f - knock[0]) / float(fall_n - 1))
            (loc, world, moving), p = _fall_at(au, g, aims, keys, u, 1.0 / (fall_n - 1), react_extra(aims, P))
            frames.append((loc, world))
            plant["l"][f] = (g["ball_l"].copy(), 0.0)
            if not moving:
                plant["r"][f] = (g["ball_r"] + B.floor_beside(g) * p["rear"], 0.0)
        else:
            frames.append(stand_frame(au, g, aims, P))
            for s in B.SIDES:
                plant[s][f] = (g["ball_" + s].copy(), 0.0)
    c["plant"] = plant
    return frames


def author_combo(au, c, S):
    """The set's strikes in a row, on one body: every strike's own shape,
    lean and twist blended in at its own k, each from where the last one
    has got to; the fists of a jab and a cross down their straight lines;
    the covering fist tucked while a cross or a hook is out; and the rear
    foot handed from the floor to the kick and back as the kick comes and
    goes, never snapped."""
    import motion_ik as M
    from mathutils import Vector
    guard, _ = S["Guard"]
    G = B.aims_at(guard, guard, 0.0, c["stance"])
    g = au.capture_guard(G)
    seq = c["seq"]
    amp = c["amp"] * (0.5 if "combo_short" in B.SABOTAGE else 1.0)
    shapes = []
    for m in seq:
        strike, twist = S[m["move"]]
        delta = {b: v for b, v in strike.items() if guard.get(b) != v}
        lean, _hip, _shift, _turns, limb = B.MOVES[m["move"]]
        shapes.append(dict(delta=delta, twist=twist, tip=B.inclination(m["move"]), limb=limb))
    # the covering fist is placed by the tuck below; carried with the chest
    # as a lone cross carries it, it bent the jab thrown before it (18 cm
    # lower and 18 across at its contact)
    cover_sides = {B.COVER[m["move"]] for m in seq if m["move"] in B.COVER}
    tucks = {}
    for cs in cover_sides:
        hm0 = g["fk"]["head_m"]
        tucks[cs] = (hm0.inverted() @ g["fk"]["hand_" + cs].translation,
                     Vector(((1.0 if cs == "l" else -1.0) * 0.09, -0.07, 0.15)))

    def ks(t):
        return [B.blend_k(t - m["start"], m["su"], m["ac"], m["rc"]) * amp for m in seq]

    def kick_w(t, k):
        """How far the rear foot belongs to a kick or a knee: 0 on the
        floor, 1 once it is a fifth of the way out."""
        w = 0.0
        for m, sh, kk in zip(seq, shapes, k):
            if sh["limb"] == "rear_leg":
                w = max(w, min(1.0, (kk / amp) / 0.2))
        return ease(w)

    def frame(t, hand_fn=None):
        k = ks(t)
        aims = dict(G)
        lean, twist = 0.0, {}
        for sh, kk in zip(shapes, k):
            if kk <= 0.0:
                continue
            aims = B.aims_at(aims, sh["delta"], kk, 1.0)
            lean += sh["tip"] * kk
            for nm, a in sh["twist"].items():
                twist[nm] = twist.get(nm, 0.0) + a * kk
        aims = B.aims_at(aims, {}, 0.0, c["stance"])
        w = kick_w(t, k)
        au.begin()
        au.fk_body(aims, lean=lean, twist=twist)
        fk = au.read()
        # grounded on both feet, and on the support foot alone as the kick
        # takes the other -- blended, so the body does not hop when it does
        zb = min(fk["ball_l"].z, fk["ball_r"].z)
        dz = g["ground"] - (zb + (fk["ball_l"].z - zb) * w)
        au.move_hips((0.0, 0.0, dz))
        fk = au.read()
        if w > 0.0:
            move = g["ball_l"] - fk["ball_l"]
            au.move_hips((move.x * w, move.y * w, 0.0))
            fk = au.read()
        rolls = {}
        for s in B.SIDES:
            pole = (fk["hip_" + s] + fk["an_" + s]) * 0.5 + Vector((0.0, -0.6, 0.0))
            yaw, roll = M.foot_turn(fk["foot_" + s], g["fk"]["foot_" + s])
            floor_m = au.planted(s, yaw, g)
            if s == "r" and w > 0.0:
                free_pole = M.pole_from(fk["hip_r"], fk["kn_r"], fk["an_r"], Vector((0.0, -1.0, 0.0)))
                l0, q0, _s0 = floor_m.decompose()
                l1, q1, _s1 = fk["foot_r"].decompose()
                from mathutils import Matrix
                mm = Matrix.Translation(l0.lerp(l1, w)) @ q0.slerp(q1, w).to_matrix().to_4x4()
                au.leg(s, mm, pole.lerp(free_pole, w), roll * (1.0 - w))
                rolls[s] = None
            else:
                au.leg(s, floor_m, pole, roll)
                rolls[s] = roll
        drop = au.settle(["l"] if w > 0.0 else list(B.SIDES))
        fk = au.read()
        targets = hand_fn(t, k, fk) if hand_fn else {}
        for s in B.SIDES:
            m = fk["hand_" + s].copy()
            if s in targets:
                m.translation = targets[s]
            au.arm(s, m, M.pole_from(fk["sh_" + s], fk["el_" + s], fk["wr_" + s], Vector((0.0, 1.0, 0.0))))
        loc, world = au.record()
        return loc, world, rolls, drop, fk, k

    # a straight punch's line: from where its fist is when it leaves to
    # where it is at the full of its own strike, over the combo so far
    lines, bends = {}, {}
    for i, (m, sh) in enumerate(zip(seq, shapes)):
        if m["move"] in B.LINE:
            s = {"lead_arm": "l", "rear_arm": "r"}[sh["limb"]]
            a = frame(m["start"])[4]["hand_" + s].translation.copy()
            full = frame(m["start"] + m["su"])[4]
            b = full["hand_" + s].translation + B.landing(au, g, m["move"], full, s)
            lines[i] = (s, a, b)
        elif m["move"] in B.LAND_X:
            bends[i] = ("r", B.landing(au, g, m["move"], frame(m["start"] + m["su"])[4], "r"))

    def hands(t, k, fk):
        out = {}
        for i, (s, d) in bends.items():
            if k[i] > 0.0:
                out[s] = fk["hand_" + s].translation + d * min(1.0, k[i] / amp)
        for cs, (gl, tl) in tucks.items():
            wt = max([kk / amp for m, kk in zip(seq, k) if B.COVER.get(m["move"]) == cs] + [0.0])
            tuck = fk["head_m"] @ gl.lerp(tl, min(1.0, wt))
            out[cs] = fk["hand_" + cs].translation.lerp(tuck, min(1.0, 3.0 * wt))
        for i, (s, a, b) in lines.items():
            m = seq[i]
            kk = k[i] / amp
            if kk <= 0.0:
                continue
            pt = a.lerp(b, min(1.0, kk))
            base = out.get(s, fk["hand_" + s].translation)
            out_stroke = (t - m["start"]) <= m["su"] + m["ac"]
            out[s] = pt if out_stroke else base.lerp(pt, kk)
        return out

    frames, plant, drops = [], {s: {} for s in B.SIDES}, []
    for f in range(c["frames"]):
        loc, world, rolls, drop, _fk, _k = frame(f / float(FPS()), hands)
        frames.append((loc, world))
        drops.append(drop)
        for s in B.SIDES:
            if rolls[s] is not None:
                plant[s][f] = (g["ball_" + s].copy(), rolls[s])
    c["plant"] = plant
    c["drop_cm"] = max(drops) * 100.0
    return frames


AUTHOR = {"react": author_react, "fall": author_fall, "pair": author_pair, "combo": author_combo,
          "death": author_death, "victory": author_victory}


# ================================================================ checking
def verify(rig, made, fails):
    """What the hits have to do, measured on the baked bones.

      a reaction goes the way its blow sends it, and back to the guard;
      a light straight is less than a heavy one;
      a fall ends within a centimetre of where Down ends, never under the floor;
      each blow of a combo reaches 85 % of what that strike reaches alone;
      in a pair every blow lands on its mark and the two chests stay apart.
    """
    import bpy
    from mathutils import Vector, Matrix

    def pose(act, frame, bones=None):
        rig.animation_data.action = act
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        return {b.name: (rig.matrix_world @ b.matrix).translation.copy()
                for b in rig.pose.bones if bones is None or b.name in bones}

    def apart(a, b):
        return max((a[n] - b[n]).length for n in a)

    by = {(c["boss"], c["move"]): (c, act) for c, act, _f in made}
    pairs = []
    for c, act, _frames in made:
        N = c["frames"]
        if c["kind"] == "react":
            p0 = pose(act, 1)
            peak = max(range(1, N + 1), key=lambda f: (pose(act, f, ("head",))["head"] - p0["head"]).length)
            pk = pose(act, peak)
            dh = pk["head"] - p0["head"]
            rel = (pk["spine_03"] - pk["pelvis"]) - (p0["spine_03"] - p0["pelvis"])
            dp = pk["pelvis"] - p0["pelvis"]
            shape = PEAK[c["blow"]][0]
            c["react"] = dict(back=dh.y * 100, left=dh.x * 100, down=-dh.z * 100,
                              curl=rel.x * 100, hips_x=dp.x * 100)
            why = None
            if shape == "Head_Straight" and dh.y < 0.05:
                why = "the head goes back %.1f cm, want 5" % (dh.y * 100)
            if shape == "Head_Side" and dh.x > -0.04:
                why = "the head goes %.1f cm to his right, want 4" % (-dh.x * 100)
            if shape == "Body_Front" and (dh.y > -0.04 or dh.z > -0.04):
                why = "he does not fold: the head %.1f cm forward and %.1f down, want 4 and 4" % (-dh.y * 100, -dh.z * 100)
            if shape == "Body_Side" and (rel.x < 0.025 or dp.x > -0.02):
                why = "he does not curl round the ribs: the chest %.1f cm to his left of the hips, the hips %.1f to his right, want 2.5 and 2" % (
                    rel.x * 100, -dp.x * 100)
            if why:
                fails.append("%s: %s" % (c["name"], why))
            back = apart(pose(act, N), p0)
            if back > 0.01:
                fails.append("%s: ends %.1f cm from the guard it started in" % (c["name"], back * 100))
        elif c["kind"] == "fall":
            for f in range(1, N + 1):
                pp = pose(act, f, ("spine_01", "spine_02", "spine_03", "neck_01", "head", "pelvis"))
                low = min(pp[n].z for n in ("spine_01", "spine_02", "spine_03", "neck_01", "head"))
                if low < 0.06 or pp["pelvis"].z < 0.08:
                    fails.append("%s: goes through the floor on frame %d" % (c["name"], f))
                    break
            down = by.get((c["boss"], "Down"))
            if down:
                gap = apart(pose(act, N), pose(down[1], down[0]["frames"]))
                c["end_cm"] = gap * 100
                if gap > 0.01:
                    fails.append("%s: does not end where Down ends: %.1f cm apart, so GetUp cannot follow it" % (
                        c["name"], gap * 100))
        elif c["kind"] == "death":
            for f in range(1, N + 1):
                pp = pose(act, f, ("spine_01", "spine_02", "spine_03", "neck_01", "head", "pelvis"))
                low = min(pp[n].z for n in ("spine_01", "spine_02", "spine_03", "neck_01", "head"))
                if low < 0.06 or pp["pelvis"].z < 0.08:
                    fails.append("%s: goes through the floor on frame %d" % (c["name"], f))
                    break
            pe = pose(act, N)
            back = math.degrees((pe["neck_01"] - pe["pelvis"]).angle(Vector((0, 0, 1))))
            c["death"] = dict(pelvis=pe["pelvis"].z * 100, back=back, head=pe["head"].z * 100)
            if back < 75.0 or pe["pelvis"].z > 0.20 or pe["head"].z > 0.30:
                fails.append("%s: does not lie dead -- the torso %.0f deg back, the pelvis %.0f cm up, the head %.0f" % (
                    c["name"], back, pe["pelvis"].z * 100, pe["head"].z * 100))
        elif c["kind"] == "victory":
            pe = pose(act, N)
            for s in c.get("raised", ()):
                over = pe["hand_end_" + s].z - pe["head"].z
                c.setdefault("over_cm", []).append(over * 100)
                if over < 0.10:
                    fails.append("%s: the %s fist is not raised -- %.0f cm over the head" % (c["name"], s, over * 100))
        elif c["kind"] == "combo":
            p1 = pose(act, 1)
            reach = []
            for m, f in zip(c["seq"], c["contacts"]):
                tip = B.TIP[B.MOVES[m["move"]][4]]
                got = (p1[tip].y - pose(act, f + 1, (tip,))[tip].y) * 100
                alone = by.get((c["boss"], m["move"]))
                want = alone[0].get("reach_cm") if alone else None
                reach.append(got)
                if want and got < 0.85 * want:
                    fails.append("%s: the %s reaches %.0f cm, alone it reaches %.0f" % (c["name"], m["move"], got, want))
            c["reach"] = reach
            settle = (pose(act, N, ("pelvis",))["pelvis"] - p1["pelvis"]).length
            if settle > 0.03:
                fails.append("%s: ends %.1f cm from the guard" % (c["name"], settle * 100))
            for f in (1,) + tuple(x + 1 for x in c["contacts"]) + (N,):
                pp = pose(act, f, ("ball_l", "ball_r"))
                if min(pp["ball_l"].z, pp["ball_r"].z) > 0.045:
                    fails.append("%s has both feet off the ground on frame %d" % (c["name"], f))
        elif c["kind"] == "pair":
            pairs.append((c, act))
    for c, act in pairs:
        ac = by.get((c["attacker"], c["attack"]))
        if not ac:
            continue
        att, att_act = ac
        rows = []
        for f, mv in c["blows"]:
            tip = pose(att_act, f + 1, (TIP[mv],))[TIP[mv]]
            bone, off, _size = TARGET[mv]
            vp = pose(act, f + 1)
            v = vp[bone] + Vector(off)
            rows.append((f, mv, tip, v, vp))
        # Where he stands and which way he faces, in the attacker's frame:
        # facing the attacker, and placed so the blows land on their marks
        # (least squares across the floor; the height is each clip's own).
        # Solved together: the facing turns the marks, the place turns the
        # facing.
        psi, px, py = math.pi, 0.0, -1.0

        def turn(v, psi):
            c_, s_ = math.cos(psi), math.sin(psi)
            return Vector((v.x * c_ - v.y * s_, v.x * s_ + v.y * c_, v.z))
        for _ in range(12):
            px = sum(t.x - turn(v, psi).x for _f, _m, t, v, _vp in rows) / len(rows)
            py = sum(t.y - turn(v, psi).y for _f, _m, t, v, _vp in rows) / len(rows)
            psi = math.atan2(-px, py)          # his -Y onto the line to the attacker
        if "pair_far" in B.SABOTAGE:
            px, py, psi = 0.0, -1.20, math.pi

        def world(v):
            return Vector((px, py, 0.0)) + turn(v, psi)
        miss = []
        for i, (f, mv, t, v, vp) in enumerate(rows):
            d = (world(v) - t).length
            dz = abs(v.z - t.z)
            size = TARGET[mv][2]
            miss.append(d * 100)
            if i == 0 and dz > size:
                fails.append("%s: the %s lands %.0f cm %s its mark" % (c["name"], mv, dz * 100, "above" if t.z > v.z else "below"))
            if d > size + (MISS_MORE if i else 0.0):
                fails.append("%s: the %s misses its mark by %.0f cm" % (c["name"], mv, d * 100))
            ap = pose(att_act, f + 1, ("spine_03",))["spine_03"]
            vc = world(vp["spine_03"])
            gap = math.hypot(ap.x - vc.x, ap.y - vc.y)
            if gap < CHESTS:
                fails.append("%s: the chests are %.0f cm apart at the %s" % (c["name"], gap * 100, mv))
        c["place"] = (px, py, psi)
        c["bearing"] = math.degrees(math.atan2(px, -py))       # off the attacker's facing, + to his left
        c["miss_cm"] = miss
    rig.animation_data.action = None
    reacts = [c for c, _a, _f in made if c.get("react")]
    for key in {c["boss"] for c in reacts}:
        light = next((c for c in reacts if c["boss"] == key and c["blow"] == "Head_Straight_Light"), None)
        heavy = next((c for c in reacts if c["boss"] == key and c["blow"] == "Head_Straight"), None)
        if light and heavy and light["react"]["back"] >= heavy["react"]["back"]:
            fails.append("%s: a light straight sends the head back as far as a heavy one" % key)


def report(made):
    combos = [c for c, _a, _f in made if c["kind"] == "combo" and c.get("reach")]
    if combos:
        print("        combos: every blow reaches; shortest %.0f cm" % min(min(c["reach"]) for c in combos))
    pairs = [c for c, _a, _f in made if c.get("miss_cm")]
    if pairs:
        worst = max(pairs, key=lambda c: max(c["miss_cm"]))
        print("        pairs: %d, worst miss %.1f cm (%s); widest bearing %.0f deg" % (
            len(pairs), max(worst["miss_cm"]), worst["name"], max(abs(c["bearing"]) for c in pairs)))
    deaths = [c["death"] for c, _a, _f in made if c.get("death")]
    if deaths:
        print("        deaths lie flat: torso %.0f-%.0f deg back, pelvis at most %.0f cm up" % (
            min(d["back"] for d in deaths), max(d["back"] for d in deaths), max(d["pelvis"] for d in deaths)))
    wins = [min(c["over_cm"]) for c, _a, _f in made if c.get("over_cm")]
    if wins:
        print("        victories: every raised fist at least %.0f cm over the head" % min(wins))
    falls = [c for c, _a, _f in made if c.get("end_cm") is not None]
    if falls:
        print("        falls end on Down's last frame, worst %.2f cm off" % max(c["end_cm"] for c in falls))
    reacts = [c for c, _a, _f in made if c.get("react")]
    for c in reacts:
        r = c["react"]
        print("        %-34s back %+5.1f  left %+5.1f  down %+5.1f  curl %+5.1f  hips %+5.1f cm" % (
            c["name"], r["back"], r["left"], r["down"], r["curl"], r["hips_x"]))


def write_pairs(made, out_root):
    import csv, os, math
    rows = [c for c, _a, _f in made if c["kind"] == "pair" and c.get("place")]
    if not rows:
        return None
    path = os.path.join(out_root, "DT_Pairs.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        # Forward / Right: where the victim's root stands, in the attacker's
        # own frame, centimetres; he faces the attacker (Yaw 180)
        # Forward / Right: where the victim's root stands, in the attacker's
        # own frame (Unreal's: X forward, Y right), centimetres; Yaw: which
        # way the victim faces in that frame, degrees (180 is straight back
        # at the attacker)
        w.writerow(["Name", "Victim", "Attacker", "AttackerClip", "VictimClip", "ForwardCm", "RightCm",
                    "Yaw", "ContactFrames", "Blows", "Knockdown", "WorstMissCm"])
        for c in rows:
            px, py, psi = c["place"]
            yaw = (-math.degrees(psi) + 180.0) % 360.0 - 180.0
            w.writerow(["%s_%s" % (c["boss"], c["move"]), c["boss"], c["attacker"], c["att_name"], c["name"],
                        "%.1f" % (-py * 100), "%.1f" % (-px * 100), "%.1f" % yaw,
                        " ".join(str(f) for f in c["contacts"]), " ".join(m for _f, m in c["blows"]),
                        c["knock"][1] if c["knock"] else "", "%.1f" % max(c["miss_cm"])])
    return path


def hits_cell(c):
    """The manifest's Hits column: every contact frame, and the blow."""
    if c["kind"] == "combo":
        return " ".join("%d:%s" % (f, m) for f, m in zip(c["contacts"], c["moves"]))
    if c["kind"] == "pair":
        return " ".join("%d:%s" % (f, m) for f, m in c["blows"])
    if c["kind"] in ("react", "fall"):
        return c["blow"]
    if c["kind"] == "victory":
        return "raises " + " ".join(c.get("raised", VICTORY_ARMS.get(c["boss"], ())))
    return ""


def pair_sheet(rig, made, out_path):
    """Both men of every pair, side on: the attacker (warm) from the left,
    facing right, the victim (cool) where DT_Pairs puts him, frames at the
    start, each blow (red) and the end. Drawn as the skeletons, as
    build_motion's contact sheets are."""
    import bpy
    from mathutils import Vector
    from PIL import Image, ImageDraw
    by = {(c["boss"], c["move"]): (c, act) for c, act, _f in made}
    rows = [(c, act) for c, act, _f in made if c["kind"] == "pair" and c.get("place")]
    if not rows:
        return None
    CW, CH, PAD, K = 170, 176, 4, 78.0

    def joints(act, frame):
        rig.animation_data.action = act
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        return {b.name: (rig.matrix_world @ b.matrix).translation.copy() for b in rig.pose.bones}
    strips = []
    for c, act in rows:
        att, att_act = by[(c["attacker"], c["attack"])]
        px, py, psi = c["place"]
        cs, sn = math.cos(psi), math.sin(psi)
        picks = [1] + [f + 1 for f in c["contacts"]]
        picks += [min(c["frames"], f + 5) for f in c["contacts"][-1:]] + [c["frames"]]
        picks = sorted(set(picks))[:8]
        cells = []
        for f in picks:
            A = joints(att_act, min(f, att["frames"]))
            V = joints(act, f)
            V = {n: Vector((px + p.x * cs - p.y * sn, py + p.x * sn + p.y * cs, p.z)) for n, p in V.items()}
            im = Image.new("RGB", (CW, CH), (14, 16, 22))
            d = ImageDraw.Draw(im)

            def xy(p):
                return (22 + (-p.y) * K, CH - 12 - p.z * K)
            d.line([(0, CH - 12), (CW, CH - 12)], fill=(34, 38, 50))
            for J, col in ((V, (120, 170, 232)), (A, (232, 186, 88))):
                for a, b in B.FIGURE:
                    if a in J and b in J:
                        d.line([xy(J[a]), xy(J[b])], fill=col, width=2)
                x, y = xy(J["head"])
                d.ellipse([x - 6, y - 10, x + 6, y + 2], outline=col)
            hit = (f - 1) in c["contacts"]
            if hit:
                d.rectangle([0, 0, CW - 1, CH - 1], outline=(232, 74, 92), width=2)
            d.text((4, 3), "%d" % f, fill=(232, 74, 92) if hit else (96, 104, 124))
            cells.append(im)
        strips.append((c, cells))
    W = PAD + 8 * (CW + PAD)
    H = PAD + len(strips) * (CH + 18 + PAD)
    sheet = Image.new("RGB", (W, H), (9, 10, 14))
    dd = ImageDraw.Draw(sheet)
    for r, (c, cells) in enumerate(strips):
        y = PAD + r * (CH + 18 + PAD)
        dd.text((PAD + 2, y + 3), "%s   %s   worst miss %.0f cm, %+.0f deg off his facing" % (
            c["name"], " ".join(m for _f, m in c["blows"]), max(c["miss_cm"]), c["bearing"]), fill=(226, 228, 236))
        for i, im in enumerate(cells):
            sheet.paste(im, (PAD + i * (CW + PAD), y + 16))
    sheet.save(out_path)
    rig.animation_data.action = None
    print("        pair sheet %s (%dx%d)" % (os.path.basename(out_path), W, H))
    return out_path
