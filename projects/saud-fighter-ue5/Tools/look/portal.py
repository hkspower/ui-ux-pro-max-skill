"""
The System's portals: every sealed gate and the arena's door drawn as a
rift (2026-10-07, Riyadh; "gates as portals", the third part of "the
System, deeper" -- its STYLE only, none of Solo Leveling's names, logos or
ranks).

    python3 Tools/look/portal.py           the checks
    python3 Tools/look/portal.py --bite    each rule broken once
    python3 Tools/look/portal.py --hlsl    print the Custom node's code
    (in the editor) py Tools/look/portal.py   builds M_Portal and its two
                                              instances in /Game/Materials/Portal

WHAT IT IS. A portal is a flat oval of swirling energy in a thin ringed
frame, set in the gate's own wall (the gate's mesh stays; the portal sits
in it -- Tools/blender/build_gates.py makes the meshes and places them). A
talent gate glows the System's cyan (LOOK["HUD_SYSTEM"], the HUD's own
#46C8FF); the arena's door glows its crimson (LOOK["HUD_DANGER"],
#FF3355): danger. Both read from Tools/look/anime_look.py's table at build
time, never copied. Drawn flat, in two tones, as the look draws
everything: a two-armed spiral over a counter-turning one, cut into ARMS
of the colour -- lamps, whose colour the look keeps -- and the DARK
between them, a light the look reads as a black surface and draws as its
own navy floor (the System's windows are navy under a glowing edge); an
ice core (LOOK["HUD_ICE"]) and a bright lip inside the frame; the frame
two thin bright lines with ticks turning round it between them, the dark
under them.

THE STATES, from ONE per-instance custom primitive data value (slot
SaudPortal::DataIndex in Source/SaudFighter/World/AbilityGate.h), written
by AAbilityGate / AAreaExit every tick it changes:
    0          SEALED    he lacks the talent: dim (SEALED_RATIO of the
                         openable's light), slow, greyed, a lock glyph
    0 .. 1               waking, over SaudPortal::WakeSeconds, when he
                         gains it (two swirls at their own constant rates,
                         crossfaded -- a rate that eased with the state
                         would make the pattern jump)
    1          OPENABLE  he has it: bright, the faster swirl
    1 .. 2     OPENING   struck or used, over SaudPortal::OpenSeconds: a
                         flare toward ice over the first FLARE_T of it,
                         the oval collapsing to its middle from
                         COLLAPSE_FROM and the frame wiping away round
                         itself
    2          gone      nothing drawn; the gate hides the component

THE LIGHT. The node works in KEY UNITS of luminance -- what the anime
look sees with MPC_Anime.Key at 1, the game's picture -- and the material
instance's "Glow" turns them into the emissive the engine wants under the
open world's fixed exposure (build_world.exposure_bias(): the moon on
open ground at half the key; Glow = 1.2 / 2^bias). The look keeps a
surface's own light only where it is 2 x EMIT_FROM over its albedo
(floored at 0.02): 0.2 of the key for a black-based emitter. So an
openable arm is 0.36 (1.8 x that), a sealed arm 0.36 x 0.36 = 0.13 -- a
half lamp, its colour half drawn toward the floor -- and the dark 0.04,
which the look draws as its lit floor (L* 28.6 on its own): never a hole.
Bounded both ways through the look's own numpy mirror: the arms lamps, no
black hole (under L* 12, the dark areas' rule), nothing blown white at
rest and no more than FLARE_WHITE at the flare's peak, the arms' colour
not washed out and their hue the palette colour's own as a lamp.

THE TIME. The swirl turns on the material's Time (View.GameTime): a blow's
freeze (USaudFeelSubsystem::FrozenDilation) stops it with the world, as
the sky's clouds stop. The state's own easing runs on the actor's tick,
in game time too.

CHECKED, without an engine (the numpy mirror below, which the preview in
build_gates.py draws, and the sources): the swirl moves with time and
stops in a freeze; a sealed portal turns slower; SEALED is SEALED_RATIO of
OPENABLE's light, within RATIO_TOL; greyed; the lock only while sealed;
the colour the palette's; the flare brighter, the collapse ending in
nothing; through the look, every state and both colours: the arms lamps
(half lamps sealed), no hole, nothing blown white, the colour kept, the
hue the palette's, SEALED dimmer on the screen too; the C++ writes the slot the material reads, at the timings the
mirror runs, and fires OnAnyGateOpened from Open(); the HLSL has every
number substituted and reads every input the editor wires. --bite breaks
each.

UNVERIFIED. No engine has compiled the node or built the material. As
remembered, not run: the Custom node's float4 output split by
ComponentMask nodes, a ScalarParameter's use_custom_primitive_data /
primitive_data_index, MaterialExpressionTime's ignore_pause, and that a
Default Lit surface with black base colour and no specular writes 0 to the
G-buffer's base colour (what the anime look reads to treat it as a lamp).
"""

import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from anime_look import LOOK, LUMA  # noqa: E402  (plain Python at import)

GATE_H = os.path.join(ROOT, "Source", "SaudFighter", "World", "AbilityGate.h")
GATE_CPP = os.path.join(ROOT, "Source", "SaudFighter", "World", "AbilityGate.cpp")
EXIT_H = os.path.join(ROOT, "Source", "SaudFighter", "World", "AreaExit.h")
EXIT_CPP = os.path.join(ROOT, "Source", "SaudFighter", "World", "AreaExit.cpp")
FEEL_H = os.path.join(ROOT, "Source", "SaudFighter", "Game", "SaudFeelSubsystem.h")

MAT_DIR = "/Game/Materials/Portal"
MATERIAL = MAT_DIR + "/M_Portal"
# the two instances, and the LOOK colour each glows
INSTANCES = {"MI_Portal_System": "HUD_SYSTEM", "MI_Portal_Danger": "HUD_DANGER"}
STATE_PARAM = "PortalState"

# Every number the node and its mirror draw with. Light in KEY UNITS of
# luminance (see THE LIGHT): the look keeps a surface's own light only from
# T = its light over its albedo (floored at 0.02) past 2 x EMIT_FROM, so a
# black-based emitter is a lamp from 0.2 of the key; under EMIT_FROM it is
# drawn as a black surface -- the look's own navy floor.
PORTAL = dict(
    # the swirl: a two-armed spiral over a three-armed one turning the
    # other way, cut into two flat tones -- the arms, lamps in the colour,
    # and between them the dark, the look's lit floor (its navy, as the
    # System's own panels are navy under a glowing edge)
    ARMS=2.0, TWIST=7.0,
    ARMS2=3.0, TWIST2=-4.0, MIX2=0.40,
    SPIN_OPEN=0.45,                 # turns a second, openable
    SPIN_SEALED=0.12,               # ... and sealed: a slow, held breath
    CUT_OPEN=0.50,                  # the swirl's value an arm starts at, openable
    CUT_SEALED=0.62,                # ... sealed: thinner arms
    AA=0.035,                       # the tones' edge, in swirl value
    DARK=0.04,                      # the dark between the arms: T 2, the look's lit floor, never a hole
    ARM=0.36,                       # an openable arm's light (key units of luminance)
    LIP_W=0.10,                     # the bright lip inside the frame, a share of the radius
    CORE_R=0.16, CORE_MIX=0.85,     # the ice core
    # the frame: two thin lines, ticks turning between them, the dark under
    LINE=0.22, FRAME_AA=0.05,       # each line a share of the frame's width
    TICKS=24.0, TICK_W=0.18, TICK_SPIN=0.05,
    # the states
    SEALED_ARM=0.36,                # a sealed arm's light, a share of the openable's: half a lamp
    SEALED_RATIO=0.37,              # SEALED is this share of OPENABLE's light, measured ...
    RATIO_TOL=0.03,                 # ... held to this
    SEALED_SAT=0.35,                # ... and keeps this share of its colour
    FLARE_T=0.35, FLARE_GAIN=0.45, FLARE_ICE=0.35,
    COLLAPSE_FROM=0.25, FRAME_FROM=0.30,
    # the timings (SaudPortal in AbilityGate.h is held to these)
    WAKE_S=0.60, OPEN_S=0.90,
)
# what the look must make of it
HOLE_L = 12.0          # build_map_scenes.HOLE_L: a surface drawn under this L* is a black hole ...
HOLE_SHARE = 0.01      # ... and at most this much of a portal may be one (a view may have 5 %)
WHITE = 0.98           # a pixel with every channel over this after the levels is blown white ...
FLARE_WHITE = 0.20     # ... none of a portal at rest is, and at most this much at the flare's peak
LAMP_FROM = 1.2        # an openable's arms are lamps by this much over the look's threshold (2 x EMIT_FROM);
                       # a sealed one's are this much over EMIT_FROM -- half lamps, dimmed toward the floor ...
HALF_SHARE = 0.15      # ... and no more than this of an openable one is neither lamp nor floor (the tones' edges)
SCREEN_DIM = 0.85      # a sealed portal's brightest tenth at most this of an openable one's, in its
                       # brightest channel on the screen (HSV's value: L* ranks a saturated red under a grey)
SAT_KEEP = 0.50        # an openable's arms keep this much of the colour its palette has as a lamp at the threshold
HUE_DEG = 6.0          # the arms' hue on the screen within this of the palette colour's own as a lamp

_FLAGS = set()          # sabotages (bite)


# ------------------------------------------------------------------ the C++
def cpp_numbers(texts=None):
    """SaudPortal's constants from AbilityGate.h, and the freeze's dilation."""
    T = texts or {}
    read = lambda p: T[p] if p in T else open(p, encoding="utf-8").read()
    h = read(GATE_H)
    got = {}
    for name in ("DataIndex", "WakeSeconds", "OpenSeconds"):
        m = re.search(r"constexpr\s+(?:int32|float)\s+%s\s*=\s*([0-9.]+)f?\s*;" % name, h)
        got[name] = float(m.group(1)) if m else None
    m = re.search(r"FrozenDilation\s*=\s*([0-9.]+)f?\s*;", read(FEEL_H))
    got["FrozenDilation"] = float(m.group(1)) if m else None
    return got


def data_index():
    v = cpp_numbers()["DataIndex"]
    return None if v is None else int(v)


# ----------------------------------------------------------------- the HLSL
def _f(v):
    return "%.6f" % v


CODE = r"""
// M_Portal (Tools/look/portal.py): the System's rift. Key units out; the
// instance's Glow takes them to the emissive the world's exposure wants.
// Inputs: UV0 the oval (its edge at length 1), UV1 (x: -1 on the energy,
// 0..1 across the frame; y: the oval's height over its width), Time
// (View.GameTime: a freeze holds it), State (custom primitive data),
// Colour, Ice, Glow.
float3 Y3 = float3(LUMA_R, LUMA_G, LUMA_B);
float2 P = UV0 * 2.0 - 1.0;
float Q = UV1.x;
float Aspect = max(UV1.y, 0.0001);
float S = clamp(State, 0.0, 2.0);
float Wake = saturate(S);
float Open = saturate(S - 1.0);
float Flare = sin(3.14159265 * saturate(Open / FLARE_T)) * step(0.000001, Open);
float Size = max(1.0 - smoothstep(COLLAPSE_FROM, 1.0, Open), 0.0001);
float R = length(P);
float Ang = atan2(P.y, P.x);
float Rc = R / Size;
float Tau = 6.28318531;
// the colour and the ice at a luminance of one, greyed while sealed
float Sat = lerp(SEALED_SAT, 1.0, Wake);
float3 Hue = lerp(float3(1.0, 1.0, 1.0), Colour / max(dot(Colour, Y3), 0.0001), Sat);
float3 IceHue = lerp(float3(1.0, 1.0, 1.0), Ice / max(dot(Ice, Y3), 0.0001), Sat);
float ArmL = ARM * lerp(SEALED_ARM, 1.0, Wake) * (1.0 + FLARE_GAIN * Flare);
// 1. the swirl: two constant rates crossfaded by the state (a rate eased
//    with the state would make the pattern jump), cut into two tones
float E1s = 0.5 + 0.5 * cos(ARMS * Ang + TWIST * Rc - Tau * SPIN_SEALED * Time);
float E2s = 0.5 + 0.5 * cos(ARMS2 * Ang + TWIST2 * Rc + Tau * SPIN_SEALED * 0.6 * Time);
float E1o = 0.5 + 0.5 * cos(ARMS * Ang + TWIST * Rc - Tau * SPIN_OPEN * Time);
float E2o = 0.5 + 0.5 * cos(ARMS2 * Ang + TWIST2 * Rc + Tau * SPIN_OPEN * 0.6 * Time);
float Ev = lerp(lerp(E1s, E2s, MIX2), lerp(E1o, E2o, MIX2), Wake);
float Cut = lerp(CUT_SEALED, CUT_OPEN, Wake);
float Arm = smoothstep(Cut - AA, Cut + AA, Ev);
Arm = max(Arm, smoothstep(1.0 - LIP_W - AA, 1.0 - LIP_W + AA, Rc));
float Core = (1.0 - smoothstep(CORE_R - AA, CORE_R + AA, Rc)) * CORE_MIX;
float3 Energy = lerp(Hue * DARK, Hue * ArmL, Arm);
Energy = lerp(Energy, IceHue * ArmL, Core);
// 2. the lock, while sealed: in units of the oval's smaller half-axis
float K = min(1.0, Aspect);
float2 G = float2(P.x, P.y * Aspect) / K;
float Body = max(abs(G.x) - 0.30, max(G.y - 0.04, -0.36 - G.y));
float Shackle = max(abs(length(G - float2(0.0, 0.04)) - 0.19) - 0.035, 0.04 - G.y);
float Hole = min(length(G - float2(0.0, -0.12)) - 0.065, max(abs(G.x) - 0.025, max(G.y + 0.12, -0.28 - G.y)));
float Lock = (1.0 - smoothstep(-0.012, 0.012, max(min(Body, Shackle), -Hole))) * (1.0 - Wake);
Energy = lerp(Energy, IceHue * ArmL, Lock);
// 3. the frame: two thin lines, ticks turning between them, the dark under
float Line = 1.0 - smoothstep(LINE - FRAME_AA, LINE + FRAME_AA, min(Q, 1.0 - Q));
float Tk = abs(frac(Ang / Tau * TICKS - TICK_SPIN * Time) - 0.5) * 2.0;
float Tick = 1.0 - smoothstep(TICK_W - FRAME_AA, TICK_W + FRAME_AA, Tk);
float3 Frame = Hue * lerp(DARK, ArmL, max(Line, Tick));
float OnFrame = step(0.0, Q);
float3 C = lerp(Energy, Frame, OnFrame);
// 4. the flare toward ice
C = lerp(C, IceHue * ArmL, Flare * FLARE_ICE);
// 5. the mask: the oval collapsing, the frame wiping round itself
float Wipe = smoothstep(FRAME_FROM, 1.0, Open);
float MaskE = 1.0 - smoothstep(0.98, 1.0, Rc);
float MaskF = step(Wipe, frac(Ang / Tau + 0.25) * 0.999 + 0.0005);
float Mask = lerp(MaskE, MaskF, OnFrame) * step(S, 1.9999);
return float4(C * Glow, Mask);
"""


def _numbers():
    """PORTAL, with a sabotage's change in it."""
    K = dict(PORTAL)
    if "slow_open" in _FLAGS:
        K["SPIN_OPEN"] = K["SPIN_SEALED"]
    if "bright_sealed" in _FLAGS:
        K["SEALED_ARM"], K["CUT_SEALED"] = 0.95, K["CUT_OPEN"]
    if "hot_flare" in _FLAGS:
        K["FLARE_GAIN"], K["FLARE_ICE"] = 2.0, 0.9
    if "hot_open" in _FLAGS:
        K["ARM"] = 1.6
    if "dim_portal" in _FLAGS:
        K["ARM"], K["DARK"] = 0.08, 0.0
    if "grey_sealed" in _FLAGS:
        K["SEALED_SAT"] = 1.0
    if "no_collapse" in _FLAGS:
        K["COLLAPSE_FROM"] = 2.0
    return K


def hlsl():
    """The Custom node's body, PORTAL's and LUMA's numbers in it."""
    pairs = {k: _f(v) for k, v in _numbers().items()}
    pairs.update(LUMA_R=_f(LUMA[0]), LUMA_G=_f(LUMA[1]), LUMA_B=_f(LUMA[2]))
    names = sorted(pairs, key=len, reverse=True)
    code = re.sub(r"\b(%s)\b" % "|".join(names), lambda m: pairs[m.group(1)], CODE)
    if "real_time" in _FLAGS:
        code = code.replace("Time)", "RealTime)").replace("Time;", "RealTime;")
    return code


# Every input the node reads, and what the editor wires into it.
INPUTS = ("UV0", "UV1", "Time", "State", "Colour", "Ice", "Glow")


# --------------------------------------------------------------- the mirror
def _smooth(e0, e1, x):
    import numpy as np
    t = np.clip((np.asarray(x, float) - e0) / max(e1 - e0, 1e-9), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def emission(P, Q, aspect, state, time, colour, ice=None, glow=1.0):
    """The node, line for line, on arrays: P (...,2) the oval's coordinate
    (UV0 * 2 - 1), Q (...) UV1.x (-1 the energy, 0..1 the frame), aspect
    UV1.y, the state, game seconds, the colour and the ice (linear).
    Returns (rgb in key units, the mask, the lock's coverage)."""
    import numpy as np
    K = _numbers()
    colour = np.asarray(colour, float)
    if "white_portal" in _FLAGS:
        colour = np.array(LOOK["HUD_ICE"])
    ice = np.asarray(LOOK["HUD_ICE"] if ice is None else ice, float)
    Y3 = np.array(LUMA)
    lerp = lambda a, b, t: a + (b - a) * t
    S = float(np.clip(state, 0.0, 2.0))
    wake = min(S, 1.0)
    opn = min(max(S - 1.0, 0.0), 1.0)
    flare = math.sin(math.pi * min(opn / K["FLARE_T"], 1.0)) * (1.0 if opn > 1e-6 else 0.0)
    size = max(1.0 - float(_smooth(K["COLLAPSE_FROM"], 1.0, opn)), 1e-4)
    R = np.hypot(P[..., 0], P[..., 1])
    ang = np.arctan2(P[..., 1], P[..., 0])
    Rc = R / size
    tau = 2.0 * math.pi
    sat = lerp(K["SEALED_SAT"], 1.0, wake)
    hue = lerp(np.ones(3), colour / max(colour @ Y3, 1e-4), sat)
    ice_hue = lerp(np.ones(3), ice / max(ice @ Y3, 1e-4), sat)
    arm_l = K["ARM"] * lerp(K["SEALED_ARM"], 1.0, wake) * (1.0 + K["FLARE_GAIN"] * flare)
    c = np.cos
    e1s = 0.5 + 0.5 * c(K["ARMS"] * ang + K["TWIST"] * Rc - tau * K["SPIN_SEALED"] * time)
    e2s = 0.5 + 0.5 * c(K["ARMS2"] * ang + K["TWIST2"] * Rc + tau * K["SPIN_SEALED"] * 0.6 * time)
    e1o = 0.5 + 0.5 * c(K["ARMS"] * ang + K["TWIST"] * Rc - tau * K["SPIN_OPEN"] * time)
    e2o = 0.5 + 0.5 * c(K["ARMS2"] * ang + K["TWIST2"] * Rc + tau * K["SPIN_OPEN"] * 0.6 * time)
    ev = lerp(lerp(e1s, e2s, K["MIX2"]), lerp(e1o, e2o, K["MIX2"]), wake)
    cut = lerp(K["CUT_SEALED"], K["CUT_OPEN"], wake)
    aa = K["AA"]
    arm = _smooth(cut - aa, cut + aa, ev)
    arm = np.maximum(arm, _smooth(1.0 - K["LIP_W"] - aa, 1.0 - K["LIP_W"] + aa, Rc))
    core = (1.0 - _smooth(K["CORE_R"] - aa, K["CORE_R"] + aa, Rc)) * K["CORE_MIX"]
    energy = lerp(hue * K["DARK"], hue * arm_l, arm[..., None])
    energy = lerp(energy, ice_hue * arm_l, core[..., None])
    # the lock
    if "stretched_lock" in _FLAGS:
        aspect = 1.0
    k = min(1.0, aspect)
    gx, gy = P[..., 0] / k, P[..., 1] * aspect / k
    body = np.maximum(np.abs(gx) - 0.30, np.maximum(gy - 0.04, -0.36 - gy))
    shackle = np.maximum(np.abs(np.hypot(gx, gy - 0.04) - 0.19) - 0.035, 0.04 - gy)
    hole = np.minimum(np.hypot(gx, gy + 0.12) - 0.065, np.maximum(np.abs(gx) - 0.025, np.maximum(gy + 0.12, -0.28 - gy)))
    lock = (1.0 - _smooth(-0.012, 0.012, np.maximum(np.minimum(body, shackle), -hole))) * (1.0 - wake)
    if "no_lock" in _FLAGS:
        lock = lock * 0.0
    energy = lerp(energy, ice_hue * arm_l, lock[..., None])
    # the frame
    fa = K["FRAME_AA"]
    line = 1.0 - _smooth(K["LINE"] - fa, K["LINE"] + fa, np.minimum(Q, 1.0 - Q))
    tk = np.abs((ang / tau * K["TICKS"] - K["TICK_SPIN"] * time) % 1.0 - 0.5) * 2.0
    tick = 1.0 - _smooth(K["TICK_W"] - fa, K["TICK_W"] + fa, tk)
    frame = hue * lerp(K["DARK"], arm_l, np.maximum(line, tick))[..., None]
    on_frame = Q >= 0.0
    C = np.where(on_frame[..., None], frame, energy)
    C = lerp(C, ice_hue * arm_l, flare * K["FLARE_ICE"])
    wipe = float(_smooth(K["FRAME_FROM"], 1.0, opn))
    mask_e = 1.0 - _smooth(0.98, 1.0, Rc)
    mask_f = (wipe <= ((ang / tau + 0.25) % 1.0) * 0.999 + 0.0005).astype(float)
    mask = np.where(on_frame, mask_f, mask_e) * (1.0 if S < 1.9999 else 0.0)
    return C * glow, mask, np.where(on_frame, 0.0, lock)


def card(n=240, aspect=1.0, frame_w=0.14):
    """A portal laid flat for the checks: n x n texels over its oval and
    frame, the frame frame_w of the oval's radius wide. Returns P, Q and
    where the portal is (inside the frame's outer edge)."""
    import numpy as np
    pm = 1.0 + frame_w * 1.6
    u = (np.arange(n) + 0.5) / n * 2.0 * pm - pm
    X, Z = np.meshgrid(u, -u)
    P = np.stack([X, Z], -1)
    R = np.hypot(X, Z)
    inside = R <= 1.0 + frame_w
    Q = np.where(inside & (R >= 1.0), np.minimum((R - 1.0) / frame_w, 1.0), -1.0)
    return P, Q, inside


# ------------------------------------------------------------- the states
def step_state(state, target, opening, dt):
    """AAbilityGate::TickPortal's easing, mirrored: toward the target (0
    sealed, 1 openable) at one per WAKE_S while not opening; from 1 to 2
    over OPEN_S once opened."""
    if opening:
        return min(2.0, max(state, 1.0) + dt / PORTAL["OPEN_S"])
    if state > target:
        return max(target, state - dt / PORTAL["WAKE_S"])
    return min(target, state + dt / PORTAL["WAKE_S"])


# --------------------------------------------------------------- the checks
def _lstar(disp):
    import numpy as np
    d = np.clip(disp, 0.0, 1.0)
    lin = np.where(d <= 0.04045, d / 12.92, ((d + 0.055) / 1.055) ** 2.4)
    y = lin @ np.array(LUMA)
    return np.where(y > 216 / 24389, 116 * np.cbrt(y) - 16, y * 24389 / 27)


def _hue(rgb):
    import numpy as np
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return np.degrees(np.arctan2(math.sqrt(3.0) * (g - b), 2.0 * r - g - b))


def _hue_off(a, b):
    d = abs(float(a) - float(b)) % 360.0
    return min(d, 360.0 - d)


def through_look(rgb, mask, wall=0.10):
    """The portal over a flat soot wall at 9 m in the moon (half the key),
    through both of the look's materials at key 1 (the game's picture):
    display values, the look's masks and where the portal is. Its
    G-buffer base colour is 0 (black, no specular), its lit colour its
    emission."""
    import numpy as np
    import anime_look as AL
    H, W = mask.shape
    C, A, N, D, fighter = AL._flat(W, wall, lit=AL.LOOK["KEY"] * 0.5, h=H)
    on = mask >= 0.5
    if "lit_portal" in _FLAGS:
        A = np.where(on[..., None], 0.30, A)          # a base colour: the look tones it as a surface
        C = np.where(on[..., None], 0.30 * 0.5 + rgb, C)
    else:
        A = np.where(on[..., None], 0.0, A)
        C = np.where(on[..., None], rgb, C)
    D = np.where(on, 900.0 - 3.0, D)
    disp, m = AL.look(C, A, N, D, fighter, key=1.0)
    return disp, m, on, C, A


def lamp_disp(colour, luma):
    """The palette colour drawn by the look as a lamp of this light."""
    import numpy as np
    c = np.asarray(colour, float)
    c = c / max(c @ np.array(LUMA), 1e-9) * luma
    disp, _m, _on, _C, _A = through_look(np.broadcast_to(c, (8, 8, 3)).copy(), np.ones((8, 8), float))
    return disp[2:6, 2:6].mean((0, 1))


def lamp_hue(colour, luma):
    """The palette colour as the look draws a lamp of it at this light:
    the hue the portal's arms must keep on the screen."""
    import numpy as np
    import anime_look as AL
    c = np.asarray(colour, float)
    c = c / max(c @ np.array(LUMA), 1e-9) * luma
    m = np.ones((8, 8), float)
    disp, _m, _on, _C, _A = through_look(np.broadcast_to(c, (8, 8, 3)).copy(), m)
    return float(_hue(disp[2:6, 2:6].mean((0, 1))))


def check():
    """Every rule; returns the misses (an empty list passes)."""
    import numpy as np
    out = []
    cpp = cpp_numbers()
    frozen = cpp["FrozenDilation"]
    K = _numbers()
    P, Q, inside = card(200, aspect=1.0)
    sysc, danger, ice = (np.array(LOOK[k]) for k in ("HUD_SYSTEM", "HUD_DANGER", "HUD_ICE"))
    energy = inside & (Q < 0)
    luma = np.array(LUMA)
    lamp_t = 2.0 * LOOK["EMIT_FROM"]

    def em(state, t, colour=sysc, aspect=1.0):
        return emission(P, Q, aspect, state, t, colour, ice)

    # 1. the swirl moves with time and stops in a freeze; sealed, slower
    frame_s = 1.0 / 24.0
    for name, s in (("openable", 1.0), ("sealed", 0.0)):
        a, _, _ = em(s, 3.0)
        b, _, _ = em(s, 3.0 + frame_s)
        moved = float(np.abs(a - b)[energy].max())
        if moved < 0.02:
            out.append("the %s swirl does not move with time (%.4f in a frame)" % (name, moved))
        fz = 3.0 + frame_s * (frozen if frozen is not None else 1.0)
        if "time_in_real" in _FLAGS:
            fz = 3.0 + frame_s       # a freeze that does not hold it: the real frame
        c, _, _ = em(s, fz)
        held = float(np.abs(a - c)[energy].max())
        if held > 1.0 / 255.0:
            out.append("the %s swirl moves in a freeze (%.4f in a frozen frame): it must run on game time" % (name, held))

    def change(s):
        # a frame's change over the state's own light, so a dimmer portal
        # is not counted slower for being dim
        a, _, _ = em(s, 3.0); b, _, _ = em(s, 3.0 + frame_s)
        return float(np.abs(a - b)[energy].mean() / max(a[energy].mean(), 1e-9))
    if change(0.0) >= 0.4 * change(1.0):
        out.append("a sealed portal turns as fast as an openable one (%.3f against %.3f of its light a frame)" % (change(0.0), change(1.0)))

    # 2. SEALED is SEALED_RATIO of OPENABLE's light, greyed, and only it locked
    lum, chroma = {}, {}
    for s in (0.0, 1.0):
        ys, cs = [], []
        for t in np.linspace(0.0, 4.0, 9):
            rgb, mask, lock = em(s, t)
            keep = inside & (mask >= 0.5) & (lock < 0.01)
            ys.append(float((rgb @ luma)[keep].mean()))
            cs.append(float(((rgb.max(-1) - rgb.min(-1)) / np.maximum(rgb @ luma, 1e-6))[keep].mean()))
        lum[s], chroma[s] = float(np.mean(ys)), float(np.mean(cs))
    ratio = lum[0.0] / max(lum[1.0], 1e-9)
    if abs(ratio - K["SEALED_RATIO"]) > K["RATIO_TOL"]:
        out.append("SEALED is %.3f of OPENABLE's light, not %.2f +- %.2f" % (ratio, K["SEALED_RATIO"], K["RATIO_TOL"]))
    sat = chroma[0.0] / max(chroma[1.0], 1e-9)
    if sat > PORTAL["SEALED_SAT"] + 0.10:
        out.append("a sealed portal is not greyed: %.2f of the openable's colour (at most %.2f)" % (sat, PORTAL["SEALED_SAT"] + 0.10))
    for aspect in (0.5, 1.0, 1.9):
        _, _, lock0 = emission(P, Q, aspect, 0.0, 1.0, sysc, ice)
        _, _, lock1 = emission(P, Q, aspect, 1.0, 1.0, sysc, ice)
        share0 = float((lock0 > 0.5)[energy].mean())
        if share0 < 0.04:
            out.append("a sealed portal shows no lock (%.1f %% of its oval at aspect %.1f)" % (share0 * 100, aspect))
        if float((lock1 > 0.5)[energy].mean()) > 0.0:
            out.append("an openable portal still shows the lock")
        on = lock0 > 0.5
        if on.any():
            gx = np.abs(P[..., 0])[on] / min(1.0, aspect)
            gy = np.abs(P[..., 1])[on] * aspect / min(1.0, aspect)
            if gx.max() > 0.4 or gy.max() > 0.5:
                out.append("the lock is stretched with the oval (aspect %.1f)" % aspect)

    # 3. the colour is the palette's: an openable arm (core and lip aside)
    #    is the palette colour's chromaticity, both kinds
    Rr = np.hypot(P[..., 0], P[..., 1])
    band = energy & (Rr > K["CORE_R"] + 0.1) & (Rr < 1.0 - K["LIP_W"] - 0.1)
    for name, colour in (("cyan", sysc), ("crimson", danger)):
        rgb, mask, _ = em(1.0, 2.0, colour)
        arms = band & (rgb @ luma > 0.9 * K["ARM"])
        got = rgb[arms].mean(0)
        got, want = got / got.sum(), colour / colour.sum()
        if not arms.any() or np.abs(got - want).max() > 0.01:
            out.append("the %s portal's colour is not the palette's: chromaticity %s against %s"
                       % (name, np.round(got, 3), np.round(want, 3)))

    # 4. the opening: a flare brighter than openable, then nothing
    peak = 1.0 + K["FLARE_T"] * 0.5
    a, _, _ = em(1.0, 2.0); b, _, _ = em(peak, 2.0)
    la, lb = float((a @ luma)[energy].mean()), float((b @ luma)[energy].mean())
    if lb < 1.3 * la:
        out.append("the opening does not flare (%.3f against the openable's %.3f)" % (lb, la))
    areas = []
    for s in np.linspace(1.0, 2.0, 11):
        _, mask, _ = em(float(s), 2.0)
        areas.append(float((mask >= 0.5)[inside].mean()))
    if any(b_ > a_ + 1e-9 for a_, b_ in zip(areas, areas[1:])):
        out.append("the opening grows somewhere on its way out: %s" % np.round(areas, 3))
    if areas[-2] > 0.05 or areas[-1] > 0.0:
        out.append("the opened portal does not collapse to nothing (%.3f left at 0.9, %.3f at the end)" % (areas[-2], areas[-1]))

    # 5. the light, through the look: an openable portal's arms lamps (the
    #    look keeps their colour), a sealed one's half lamps (dimmed toward
    #    the floor); the dark the look's floor and never a hole; nothing
    #    blown white at rest and little at the flare's peak; the arms' hue
    #    the palette's; SEALED dimmer on the screen too
    screen = {}
    for name, colour in (("cyan", sysc), ("crimson", danger)):
        for sname, s in (("sealed", 0.0), ("openable", 1.0), ("flaring", peak), ("collapsing", 1.6)):
            worst = dict(hole=0.0, white=0.0, half=0.0, lamp=9.0)
            Ls = []
            need = LOOK["EMIT_FROM"] if s < 0.5 else lamp_t
            for t in (0.5, 2.0):
                rgb, mask, lock = em(s, t, colour)
                disp, m, on, C, A = through_look(rgb, mask)
                on = on & inside
                if not on.any():
                    continue
                Lst = _lstar(disp)
                ink = (m["ink"] > 0.5) | (m["hatch"] > 0.5) | (m["screentone"] > 0.5)
                worst["hole"] = max(worst["hole"], float(((Lst < HOLE_L) & ~ink)[on].mean()))
                worst["white"] = max(worst["white"], float((disp.min(-1) >= WHITE)[on].mean()))
                T = (C @ luma) / np.maximum(A @ luma, 0.02)
                worst["half"] = max(worst["half"], float(((T > LOOK["EMIT_FROM"]) & (T < lamp_t))[on].mean()))
                arms = on & (rgb @ luma >= 0.9 * K["ARM"] * (K["SEALED_ARM"] if s < 0.5 else 1.0))
                if arms.any():
                    worst["lamp"] = min(worst["lamp"], float(np.percentile(T[arms], 5)) / need)
                Ls.append(float(np.percentile(disp.max(-1)[on & (lock < 0.01)], 90)))
                if sname == "openable" and t == 2.0:
                    sel = band & arms & ~ink
                    if sel.any():
                        sat_got = float(np.median(1.0 - disp[sel].min(-1) / np.maximum(disp[sel].max(-1), 1e-6)))
                        ref = lamp_disp(colour, lamp_t * 0.02)
                        sat_ref = 1.0 - ref.min() / max(ref.max(), 1e-6)
                        if sat_got < SAT_KEEP * sat_ref:
                            out.append("the %s portal's arms are washed out on the screen: %.2f of the colour, the palette's lamp %.2f (at least %.2f of it)"
                                       % (name, sat_got, sat_ref, SAT_KEEP))
                        want = lamp_hue(colour, K["ARM"])
                        dh = _hue_off(_hue(disp[sel].mean(0)), want)
                        if dh > HUE_DEG:
                            out.append("the %s portal's arms read %.0f degrees off its colour on the screen" % (name, dh))
            screen[(name, sname)] = float(np.mean(Ls)) if Ls else 0.0
            if worst["hole"] > HOLE_SHARE:
                out.append("a %s %s portal is %.1f %% black hole through the look (under L* %.0f; at most %.0f %%)"
                           % (sname, name, worst["hole"] * 100, HOLE_L, HOLE_SHARE * 100))
            cap = FLARE_WHITE if sname == "flaring" else 0.0
            if worst["white"] > cap:
                out.append("a %s %s portal is blown white through the look's levels on %.1f %% of it (at most %.0f %%)"
                           % (sname, name, worst["white"] * 100, cap * 100))
            if worst["lamp"] < LAMP_FROM:
                out.append("a %s %s portal's arms are %.2f of the look's %s threshold (at least %.1f): the look "
                           "would draw them as a black surface" % (sname, name, worst["lamp"],
                                                                    "half-lamp" if s < 0.5 else "lamp", LAMP_FROM))
            if s >= 0.5 and worst["half"] > HALF_SHARE:
                out.append("a %s %s portal is %.0f %% neither lamp nor floor (at most %.0f %%): its tones smear"
                           % (sname, name, worst["half"] * 100, HALF_SHARE * 100))
        if screen[(name, "sealed")] > SCREEN_DIM * screen[(name, "openable")]:
            out.append("a sealed %s portal reads as bright as an openable one on the screen (its brightest %.2f against %.2f, at most %.2f of it)"
                       % (name, screen[(name, "sealed")], screen[(name, "openable")], SCREEN_DIM))

    # 6. the states' timing: the mirror's easing takes WAKE_S (the C++'s
    #    constants are held to the mirror's in source_misses)
    s, t = 0.0, 0.0
    while s < 1.0 and t < 5.0:
        s = step_state(s, 1.0, False, 1.0 / 60.0); t += 1.0 / 60.0
    if abs(t - PORTAL["WAKE_S"]) > 2.0 / 60.0:
        out.append("waking takes %.2f s, not WAKE_S %.2f" % (t, PORTAL["WAKE_S"]))
    out.extend(source_misses())
    # 7. the node: every number in it, every input it reads wired
    code = hlsl()
    left = [k for k in PORTAL if re.search(r"\b%s\b" % k, code)] + re.findall(r"\bLUMA_[RGB]\b", code)
    if left:
        out.append("the node keeps names it was never given numbers for: %s" % ", ".join(sorted(set(left))))
    for name in INPUTS:
        if not re.search(r"\b%s\b" % name, code):
            out.append("the node never reads its %s input" % name)
    if re.search(r"\bRealTime\b", code):
        out.append("the node turns on real time: a freeze would not hold it")
    return out


def measure():
    """The numbers the report quotes."""
    import numpy as np
    P, Q, inside = card(200)
    luma = np.array(LUMA)
    out = {}
    for name, key in (("cyan", "HUD_SYSTEM"), ("crimson", "HUD_DANGER")):
        for sname, s in (("sealed", 0.0), ("openable", 1.0), ("flaring", 1.0 + PORTAL["FLARE_T"] * 0.5)):
            rgb, mask, lock = emission(P, Q, 1.0, s, 2.0, LOOK[key])
            disp, m, on, C, A = through_look(rgb, mask)
            on = on & inside
            Lst = _lstar(disp)
            out[(name, sname)] = dict(emit=float((rgb @ luma)[on].mean()), L=float(Lst[on].mean()),
                                      Lmin=float(np.percentile(Lst[on], 1)), Lmax=float(Lst[on].max()))
    return out


def source_misses(texts=None):
    """The C++ and the editor half, read from the sources."""
    T = texts or {}
    read = lambda p: T[p] if p in T else open(p, encoding="utf-8").read()
    out = []
    cpp = cpp_numbers(T)
    if cpp["DataIndex"] is None:
        out.append("AbilityGate.h has no SaudPortal::DataIndex for the material to read")
    else:
        try:
            from camera_fade import slot as fade_slot
            if fade_slot() is not None and int(cpp["DataIndex"]) == fade_slot():
                out.append("the portal's state shares slot %d with the camera's fade" % fade_slot())
        except Exception:
            pass
    for name, key in (("WakeSeconds", "WAKE_S"), ("OpenSeconds", "OPEN_S")):
        if cpp[name] is None:
            out.append("AbilityGate.h has no SaudPortal::%s" % name)
        elif abs(cpp[name] - PORTAL[key]) > 1e-6:
            out.append("SaudPortal::%s is %.2f, the mirror's %s %.2f" % (name, cpp[name], key, PORTAL[key]))
    h, c = read(GATE_H), read(GATE_CPP)
    eh, ec = read(EXIT_H), read(EXIT_CPP)
    if not re.search(r"DECLARE_MULTICAST_DELEGATE_TwoParams\(\s*FOnGateOpenedNative\s*,\s*FName\s*,\s*AAbilityGate\s*\*\s*\)", h) \
            or not re.search(r"static\s+FOnGateOpenedNative\s+OnAnyGateOpened\s*;", h):
        out.append("AbilityGate.h does not declare static FOnGateOpenedNative OnAnyGateOpened (FName, AAbilityGate*)")
    body = re.search(r"void AAbilityGate::Open\(\)\s*\{(.*?)\n\}", c, re.S)
    if not body or "OnAnyGateOpened.Broadcast(GateId, this)" not in body.group(1):
        out.append("AAbilityGate::Open() does not fire OnAnyGateOpened")
    if not re.search(r"FOnGateOpenedNative\s+AAbilityGate::OnAnyGateOpened\s*;", c):
        out.append("AbilityGate.cpp never defines AAbilityGate::OnAnyGateOpened")
    for name, src in (("AAbilityGate", c), ("AAreaExit", ec)):
        if "SetCustomPrimitiveDataFloat(SaudPortal::DataIndex" not in src:
            out.append("%s never writes the portal's state into the slot the material reads" % name)
    if not re.search(r"bOpening\s*=\s*true", body.group(1) if body else ""):
        out.append("AAbilityGate::Open() does not start the portal's flare")
    tick = re.search(r"void AAbilityGate::TickPortal\(float DeltaSeconds\)\s*\{(.*?)\n\}", c, re.S)
    if not tick or "HasAbility" not in c or "IsGateOpen(GateId)" not in tick.group(1):
        out.append("AAbilityGate::TickPortal does not read the game instance (HasAbility via CanBeOpened, IsGateOpen)")
    if not re.search(r"bArenaDoor", eh) or "bArenaDoor" not in ec:
        out.append("AAreaExit has no bArenaDoor: the arena's door cannot be told from the others")
    src = open(os.path.abspath(__file__), encoding="utf-8").read() if "portal.py" not in T else T["portal.py"]
    if not re.search(r'set_editor_property\("ignore_pause", False\)', src):
        out.append("the editor wires a Time that ignores pause: a freeze would not hold the swirl")
    if not re.search(r'"primitive_data_index", data_index\(\)', src):
        out.append("the editor binds the state to another slot than SaudPortal::DataIndex")
    return out


# ------------------------------------------------------------------ bite
BITES = {
    # flag sabotages: each breaks the mirror (and so the rule) one way
    "slow_open": "turns as fast",
    "bright_sealed": "SEALED is",
    "no_lock": "shows no lock",
    "hot_flare": "blown white",
    "hot_open": "washed out",
    "dim_portal": "black hole",
    "no_collapse": "does not collapse",
    "white_portal": "not the palette's",
    "time_in_real": "moves in a freeze",
    "lit_portal": "black surface",
    "real_time": "turns on real time",
    "grey_sealed": "not greyed",
    "stretched_lock": "stretched with the oval",
}


def _source_bites():
    def broken(path, old, new):
        t = open(path, encoding="utf-8").read()
        assert old in t, "sabotage did not apply: %s" % old
        return {path: t.replace(old, new, 1)}
    me = os.path.abspath(__file__)
    return {
        "no slot": (broken(GATE_H, "constexpr int32 DataIndex", "constexpr int32 StateSlot"), "no SaudPortal::DataIndex"),
        "fade's slot": (broken(GATE_H, "constexpr int32 DataIndex = 1;", "constexpr int32 DataIndex = 0;"), "shares slot"),
        "never fired": (broken(GATE_CPP, "OnAnyGateOpened.Broadcast(GateId, this);", "OnGateOpened.Broadcast();"), "does not fire OnAnyGateOpened"),
        "no flare": (broken(GATE_CPP, "bOpening = true;", "bOpening = false;"), "does not start the portal's flare"),
        "gate unwritten": (broken(GATE_CPP, "SetCustomPrimitiveDataFloat(SaudPortal::DataIndex", "SetCustomPrimitiveDataFloat(0"), "AAbilityGate never writes"),
        "door unwritten": (broken(EXIT_CPP, "SetCustomPrimitiveDataFloat(SaudPortal::DataIndex", "SetCustomPrimitiveDataFloat(0"), "AAreaExit never writes"),
        "wake drift": (broken(GATE_H, "constexpr float WakeSeconds = 0.6f;", "constexpr float WakeSeconds = 1.6f;"), "SaudPortal::WakeSeconds is"),
        "open drift": (broken(GATE_H, "constexpr float OpenSeconds = 0.9f;", "constexpr float OpenSeconds = 0.3f;"), "SaudPortal::OpenSeconds is"),
        "no open state": (broken(GATE_CPP, "(bOpen || (GI && GI->IsGateOpen(GateId)))", "(bOpen)"), "does not read the game instance"),
        "pause ignored": ({"portal.py": open(me, encoding="utf-8").read().replace(
            'set_editor_property("ignore_pause", False)', 'set_editor_property("ignore_pause", True)')}, "ignores pause"),
    }


def bite():
    if check():
        print("the unbroken portal fails its own checks, so no sabotage can be counted:")
        for m in check():
            print("  " + m)
        return False
    print("  %-16s passes" % "(unbroken)")
    caught = total = 0
    for flag, want in BITES.items():
        _FLAGS.clear(); _FLAGS.add(flag)
        try:
            miss = check()
        finally:
            _FLAGS.clear()
        hit = [m for m in miss if want in m]
        total += 1; caught += bool(hit)
        print("  %-16s %s" % (flag, ("caught: " + hit[0]) if hit else "NOT caught (%s)" % (miss[:1] or "passes")))
    for name, (T, want) in _source_bites().items():
        miss = source_misses(T)
        hit = [m for m in miss if want in m]
        total += 1; caught += bool(hit)
        print("  %-16s %s" % (name, ("caught: " + hit[0]) if hit else "NOT caught (%s)" % (miss[:1] or "passes")))
    print("%d of %d sabotages caught" % (caught, total))
    return caught == total


# ----------------------------------------------------------------- editor
def glow_units():
    """Key units to the emissive the engine wants: one over the open
    world's exposure scale (build_world.exposure_bias(): 2^bias / 1.2, the
    moon on open ground at half the key). Read from build_world, never
    copied."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_world", os.path.join(ROOT, "Tools", "levels", "build_world.py"))
    W = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(W)
    return 1.2 / (2.0 ** W.exposure_bias())


def build_in_editor():
    """M_Portal and MI_Portal_System / MI_Portal_Danger in MAT_DIR.
    Read-reviewed, not run: no editor has executed this."""
    import unreal
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    EAL = unreal.EditorAssetLibrary
    MEL = unreal.MaterialEditingLibrary
    for name in tuple(INSTANCES) + ("M_Portal",):        # the instances reference it: they go first
        path = "%s/%s" % (MAT_DIR, name)
        if EAL.does_asset_exist(path) and not EAL.delete_asset(path):
            raise RuntimeError("could not delete %s -- close anything using it and run again" % path)
    mat = tools.create_asset("M_Portal", MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    mat.set_editor_property("opacity_mask_clip_value", 0.5)
    mat.set_editor_property("two_sided", False)
    custom = MEL.create_material_expression(mat, unreal.MaterialExpressionCustom, -400, 0)
    custom.set_editor_property("code", hlsl())
    custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT4)
    custom.set_editor_property("description", "M_Portal (Tools/look/portal.py)")
    inputs = []
    for name in INPUTS:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", name)
        inputs.append(ci)
    custom.set_editor_property("inputs", inputs)
    y = -400
    for name in INPUTS:
        if name in ("UV0", "UV1"):
            e = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -900, y)
            e.set_editor_property("coordinate_index", 0 if name == "UV0" else 1)
        elif name == "Time":
            e = MEL.create_material_expression(mat, unreal.MaterialExpressionTime, -900, y)
            e.set_editor_property("ignore_pause", False)        # View.GameTime: a freeze holds it
        elif name == "State":
            e = MEL.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -900, y)
            e.set_editor_property("parameter_name", STATE_PARAM)
            e.set_editor_property("default_value", 0.0)
            e.set_editor_property("use_custom_primitive_data", True)
            e.set_editor_property("primitive_data_index", data_index())
        elif name == "Glow":
            e = MEL.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -900, y)
            e.set_editor_property("parameter_name", "Glow")
            e.set_editor_property("default_value", glow_units())
        else:
            e = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -900, y)
            e.set_editor_property("parameter_name", name)
            e.set_editor_property("default_value", unreal.LinearColor(*LOOK["HUD_SYSTEM" if name == "Colour" else "HUD_ICE"], 1.0))
        MEL.connect_material_expressions(e, "", custom, name)
        y += 110
    rgb = MEL.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -150, -60)
    for ch, on in (("r", True), ("g", True), ("b", True), ("a", False)):
        rgb.set_editor_property(ch, on)
    alpha = MEL.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -150, 80)
    for ch, on in (("r", False), ("g", False), ("b", False), ("a", True)):
        alpha.set_editor_property(ch, on)
    MEL.connect_material_expressions(custom, "", rgb, "")
    MEL.connect_material_expressions(custom, "", alpha, "")
    MEL.connect_material_property(rgb, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(alpha, "", unreal.MaterialProperty.MP_OPACITY_MASK)
    # black, no specular, rough: the G-buffer's base colour 0, so the anime
    # look reads it as a lamp and keeps its colour
    for prop, v in ((unreal.MaterialProperty.MP_BASE_COLOR, None), (unreal.MaterialProperty.MP_SPECULAR, 0.0),
                    (unreal.MaterialProperty.MP_ROUGHNESS, 1.0)):
        if v is None:
            k = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -150, 220)
            k.set_editor_property("constant", unreal.LinearColor(0.0, 0.0, 0.0, 1.0))
        else:
            k = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -150, 300 if v else 260)
            k.set_editor_property("r", v)
        MEL.connect_material_property(k, "", prop)
    MEL.recompile_material(mat)
    EAL.save_loaded_asset(mat)
    for name, key in INSTANCES.items():
        mi = tools.create_asset(name, MAT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mi, mat)
        MEL.set_material_instance_vector_parameter_value(mi, "Colour", unreal.LinearColor(*LOOK[key], 1.0))
        MEL.set_material_instance_vector_parameter_value(mi, "Ice", unreal.LinearColor(*LOOK["HUD_ICE"], 1.0))
        EAL.save_loaded_asset(mi)
    unreal.log("Built %s and %s" % (MATERIAL, ", ".join(INSTANCES)))


if __name__ == "__main__":
    try:
        import unreal  # noqa: F401
        IN_EDITOR = True
    except ImportError:
        IN_EDITOR = False
    if IN_EDITOR:
        build_in_editor()
    elif "--hlsl" in sys.argv:
        print(hlsl())
    elif "--bite" in sys.argv:
        sys.exit(0 if bite() else 1)
    else:
        miss = check()
        for m in miss:
            print("MISS " + m)
        print("portal: %s" % ("every rule holds (the node %d lines, slot %s)" % (hlsl().count("\n"), data_index())
                              if not miss else "%d broken" % len(miss)))
        sys.exit(1 if miss else 0)
