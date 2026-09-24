"""
The anime look: one post-process pass that turns the lit frame into a
gritty fight seinen -- Baki, Kengan Ashura, Hajime no Ippo.

Asked 2026-09-24 (Riyadh) as "make all theme game style like adult japanese
anime", settled as the Unreal build, the gritty fight-seinen register, over
the fighters, the backgrounds, the hit effects and the HUD. It replaces the
realistic art direction CLAUDE.md held until that day.

WHY ONE PASS OVER EVERYTHING. The meshes stay as they are -- adult
proportions, real muscle, the measured skin -- because a seinen draws real
bodies; what makes it anime is how the light falls on them and the ink
round them. Both are properties of the picture, not of any one mesh, so
they live in one post-process material that every fighter and every
district passes through, and a man built tomorrow is drawn the same way
without a second material to keep in step.

WHAT IT DOES TO A PIXEL, in order (the HLSL below and `preview()` are the
same steps, line for line):

  1. The light a surface receives is its lit colour over its base colour.
     That is cut into three flat tones -- lit, shadow, deep shadow -- with a
     hard terminator, and a sharp highlight above the lit tone (sweat on a
     shoulder). The pixel's own colour is rescaled to its tone, so the
     light's hue (a neon sign, the rim) and the texture's detail survive.
  2. Deep shadow is hatched: diagonal ink lines in screen space, crossed
     where it is darkest.
  3. Ink: a line where depth jumps (a silhouette) and a finer one where the
     surface folds (a jaw, a muscle's edge, a lip). Fighters -- anything
     that writes custom depth -- get the heavy line; the world a lighter
     one that thins with distance.
  4. The sky is not shaded, it is banded: a painted gradient.
  5. A gritty grade: some saturation out, a dust-warm tint.
  6. Speed lines, radial round the blow, when the game asks for them.
  7. The impact frame: for a frame or two the whole picture goes to ink and
     paper, the lit side paper, the rest ink, and can be flipped.

Steps 1-5 and the impact frame's drawing are M_Anime_Post, before
tonemapping. Step 6 and the impact frame's hard cut are a second material,
M_Anime_Frame, after tonemapping -- after TSR and bloom, which would
otherwise blend a one-frame cut through their history (found by review,
2026-09-24). Steps 6 and 7 are driven by the game through the Material
Parameter Collection MPC_Anime (Combat/SaudAnime.h has the timings and the
names); everything else is a constant from LOOK, written into the HLSL when
the materials are built, so the preview and the engine read one table.

RUN
  python3 Tools/look/anime_look.py            checks: HLSL generated, the
                                             preview's steps on synthetic
                                             input (a lit sphere), sabotage
  (in the editor) py Tools/look/anime_look.py  builds MPC_Anime,
                                             M_Anime_Post and M_Anime_Frame
                                             in /Game/Materials/Anime/
  Tools/blender/anime_preview.py              renders the real men and the
                                             souq through preview()

UNVERIFIED. No engine has built or compiled either material. The Custom
nodes' HLSL is written against UE 5.4's post-process conventions --
SceneTextureLookup(), GetDefaultSceneTextureUV(), GetViewportUV(),
View.BufferSizeAndInvSize -- read, not compiled. The scene colour at
BL_SceneColorAfterDOF is pre-exposed, so nothing multiplies it by the eye
adaptation again. The same steps in numpy have
run on Blender's render passes of the real models; that is the whole proof
of the look.
"""

import math
import os
import sys

# ---------------------------------------------------------------- the table
# Tones are in exposure-normalised light: 1.0 is what a surface facing the
# key light receives once the camera's exposure is applied. KEY is the one
# dial most likely to need tuning in the engine (MPC_Anime.Key).
LOOK = {
    # 1. cel tones: light below T_DEEP is deep shadow, below T_SHADOW shadow
    "T_SHADOW": 0.50,
    "T_DEEP": 0.09,
    "T_HIGHLIGHT": 1.90,     # only real glare: lower, it spotted every face
    "SOFT": 0.020,          # half-width of each terminator, for antialiasing
    "SMOOTH_PX": 3.0,       # the light is averaged this far (1080 lines) first
    "Q_LIT": 1.00,
    "Q_SHADOW": 0.42,
    "Q_DEEP": 0.16,
    "Q_HIGHLIGHT": 1.28,
    "SHADOW_TINT": (0.90, 0.88, 0.98),   # shadows lean cool, as ink wash does
    "TINT_KEEP": 0.6,       # how much of the light's hue the tone keeps
    "EMIT_FROM": 5.0,       # light this many times the key is a lamp, not a surface
    # 2. hatching, in pixels of a 1080-line picture
    "HATCH_PX": 5.0,
    "HATCH_WIDTH": 0.34,    # share of each period that is ink
    "HATCH_ALPHA": 0.55,
    "CROSS_BELOW": 0.06,    # light under this is cross-hatched
    # 3. ink
    "INK": (0.030, 0.026, 0.024),
    "LINE_FIGHTER_PX": 4.2,  # silhouette width round a fighter, at 1080 lines
    "LINE_WORLD_PX": 2.2,
    "DEPTH_EDGE": 0.07,      # a jump of 7 % of the distance is a silhouette
    "NORMAL_EDGE": 0.40,     # 1 - cos between normals that is a fold
    "INNER_ALPHA": 0.85,
    "FADE_NEAR_CM": 1500.0,  # world lines full strength to here...
    "FADE_FAR_CM": 20000.0,  # ...and down to FADE_MIN by here
    "FADE_MIN": 0.50,
    # 4. sky
    "SKY_DEPTH_CM": 1.0e6,
    "SKY_BANDS": 7.0,
    # 5. grade
    "SATURATION": 0.84,
    "GRADE_TINT": (1.03, 1.00, 0.95),
    # 6. speed lines
    "SPEED_COUNT": 90.0,
    "SPEED_INNER": 0.16,     # clear circle round the blow, share of height
    "SPEED_OUTER": 0.62,
    "SPEED_ALPHA": 0.80,
    "SPEED_ON_FIGHTER": 0.0,  # the lines stop at a fighter
    # 7. impact frame
    "PAPER": (0.93, 0.90, 0.84),
    "IMPACT_CUT": 0.45,       # display luminance above which the cut frame is paper
    # the defaults of the game-driven parameters
    "KEY": 1.0,
}

LUMA = (0.2126, 0.7152, 0.0722)

# The Material Parameter Collection the game writes. The names are
# SaudAnime::Param in Combat/SaudAnime.h; check() holds the two together.
MPC_PATH = "/Game/Materials/Anime/MPC_Anime"
MATERIAL_PATH = "/Game/Materials/Anime/M_Anime_Post"
FRAME_PATH = "/Game/Materials/Anime/M_Anime_Frame"
MPC_SCALARS = (
    ("Impact", 0.0),        # 0..1, the impact frame
    ("ImpactInvert", 0.0),  # 0 paper-lit, 1 flipped
    ("Speed", 0.0),         # 0..1, the speed lines
    ("SpeedCentreX", 0.5),  # the blow on screen, 0..1 of the viewport
    ("SpeedCentreY", 0.5),
    ("SpeedSeed", 0.0),     # changes every other frame: the lines flicker
    ("Key", LOOK["KEY"]),
)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))


def _f(v):
    return "%.6f" % v


def _f3(v):
    return "float3(%s, %s, %s)" % tuple(_f(x) for x in v)


# --------------------------------------------------------------------- HLSL
def _sub(code):
    """LOOK's numbers into a shader body, longest names first so no name is
    eaten by a shorter one it starts with."""
    L = LOOK
    pairs = {
        "SKY_DEPTH": _f(L["SKY_DEPTH_CM"]), "SKY_BANDS": _f(L["SKY_BANDS"]),
        "T_DEEP": _f(L["T_DEEP"]), "T_SHADOW": _f(L["T_SHADOW"]), "T_HIGH": _f(L["T_HIGHLIGHT"]),
        "SOFT": _f(L["SOFT"]), "SMOOTH_PX": _f(L["SMOOTH_PX"]), "Q_LIT": _f(L["Q_LIT"]), "Q_HIGH": _f(L["Q_HIGHLIGHT"]),
        "Q_SHADOW": _f(L["Q_SHADOW"]), "Q_DEEP": _f(L["Q_DEEP"]),
        "SHADOW_TINT": _f3(L["SHADOW_TINT"]), "TINT_KEEP": _f(L["TINT_KEEP"]),
        "EMIT_FROM": _f(L["EMIT_FROM"]), "HATCH_PX": _f(L["HATCH_PX"]), "HATCH_W": _f(L["HATCH_WIDTH"]),
        "HATCH_A": _f(L["HATCH_ALPHA"]), "CROSS_BELOW": _f(L["CROSS_BELOW"]),
        "INK_D": _f3(display(L["INK"])), "PAPER_D": _f3(display(L["PAPER"])),
        "INK": _f3(L["INK"]), "PAPER": _f3(L["PAPER"]),
        "LINE_FIGHTER": _f(L["LINE_FIGHTER_PX"]), "LINE_WORLD": _f(L["LINE_WORLD_PX"]),
        "DEPTH_EDGE": _f(L["DEPTH_EDGE"]), "NORMAL_EDGE": _f(L["NORMAL_EDGE"]),
        "INNER_A": _f(L["INNER_ALPHA"]), "FADE_NEAR": _f(L["FADE_NEAR_CM"]),
        "FADE_FAR": _f(L["FADE_FAR_CM"]), "FADE_MIN": _f(L["FADE_MIN"]),
        "SATURATION": _f(L["SATURATION"]), "GRADE_TINT": _f3(L["GRADE_TINT"]),
        "SPEED_COUNT": _f(L["SPEED_COUNT"]), "SPEED_INNER": _f(L["SPEED_INNER"]),
        "SPEED_OUTER": _f(L["SPEED_OUTER"]), "SPEED_ON_FIGHTER": _f(L["SPEED_ON_FIGHTER"]),
        "SPEED_A": _f(L["SPEED_ALPHA"]), "IMPACT_CUT": _f(L["IMPACT_CUT"]),
    }
    import re
    names = sorted(pairs, key=len, reverse=True)
    return re.sub(r"\b(%s)\b" % "|".join(names), lambda m: pairs[m.group(1)], code)


def display(c):
    """A linear colour as the tonemapped, display-encoded value the second
    material works in (sRGB encoding; the tonemapper's curve is the
    engine's and is not modelled)."""
    return tuple(12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055 for v in c)


def hlsl():
    """M_Anime_Post's Custom node: steps 1-5 and the impact frame's
    drawing, before tonemapping. Inputs, by name: Impact, ImpactInvert,
    Key, and Scene -- the PostProcessInput0 SceneTexture, wired in only so
    the lookup functions are compiled into the material. Returns float3.

    The scene colour here is already PRE-EXPOSED (UE applies the eye
    adaptation to the buffer), so the light ratio is taken on it as it is
    and nothing is multiplied by EyeAdaptationLookup(): 1.0 is a surface
    lit to what the camera exposes for, and Key moves that."""
    return _sub(r"""
// ---- anime look (tones), generated by Tools/look/anime_look.py -- do not hand-edit
const float3 LUMA = float3(0.2126, 0.7152, 0.0722);
float2 UVc = GetDefaultSceneTextureUV(Parameters, 14);   // the colour input
float2 UV = GetDefaultSceneTextureUV(Parameters, 1);     // the G-buffer and depth
float2 Px = View.BufferSizeAndInvSize.zw;
float Lines = View.ViewSizeAndInvSize.y / 1080.0;

float3 C = SceneTextureLookup(UVc, 14, false).rgb;      // lit colour, pre-exposed
float3 A = SceneTextureLookup(UV, 5, false).rgb;        // base colour
float3 N = normalize(SceneTextureLookup(UV, 8, false).rgb);
float D = SceneTextureLookup(UV, 1, false).r;           // cm
float CD = SceneTextureLookup(UV, 13, false).r;         // custom depth
bool Sky = D > SKY_DEPTH;
bool Fighter = CD < D + 2.0;
const float2 Dir[8] = { float2(1,0), float2(-1,0), float2(0,1), float2(0,-1),
                        float2(0.7071,0.7071), float2(-0.7071,0.7071),
                        float2(0.7071,-0.7071), float2(-0.7071,-0.7071) };

// The light, averaged over a few pixels of the same surface (summed lit
// colour over summed base colour), so the base colour's own fine detail
// does not push single pixels across a terminator. Not across a depth jump.
float SC = dot(C, LUMA), SA = dot(A, LUMA);
float Rs = SMOOTH_PX * Lines;
for (int j = 0; j < 8; j++)
{
    float2 O = Dir[j] * Rs * Px;
    float Dn = SceneTextureLookup(UV + O, 1, false).r;
    float Same = abs(Dn - D) <= 0.02 * max(D, 1.0) ? 1.0 : 0.0;
    SC += Same * dot(SceneTextureLookup(UVc + O, 14, false).rgb, LUMA);
    SA += Same * dot(SceneTextureLookup(UV + O, 5, false).rgb, LUMA);
}
float T = SC / max(SA, 0.02) / max(Key, 0.001);

// 1. tones
float Deep = 1.0 - smoothstep(T_DEEP - SOFT, T_DEEP + SOFT, T);
float Shad = 1.0 - smoothstep(T_SHADOW - SOFT, T_SHADOW + SOFT, T);
float High = smoothstep(T_HIGH - SOFT, T_HIGH + SOFT, T);
float Q = lerp(lerp(lerp(Q_LIT, Q_HIGH, High), Q_SHADOW, Shad), Q_DEEP, Deep);
// The tone is laid on the BASE colour, in the light's own hue: a neon
// sign still colours what it lights, but a glint of white specular does
// not bleach the skin under it. Far brighter than any lit surface can be
// is a light itself (a lantern, a sign): it keeps its own colour.
float3 Hue = C / max(A, 0.02);
Hue = clamp(lerp(float3(1, 1, 1), Hue / max(dot(Hue, LUMA), 0.0001), TINT_KEEP), 0.0, 2.0);
float3 Out = A * (Q * Key) * Hue;
Out *= lerp(float3(1, 1, 1), SHADOW_TINT, Shad);
Out = lerp(Out, C, smoothstep(EMIT_FROM, 2.0 * EMIT_FROM, T));

// 2. hatching, in pixels of a 1080-line view, fixed to the view
float2 Sp = GetViewportUV(Parameters) * View.ViewSizeAndInvSize.xy / Lines;
float H1 = step(frac((Sp.x + Sp.y) / HATCH_PX), HATCH_W);
float H2 = step(frac((Sp.x - Sp.y) / HATCH_PX), HATCH_W);
float Cross = 1.0 - smoothstep(CROSS_BELOW - SOFT, CROSS_BELOW + SOFT, T);
float Hatch = saturate(H1 + H2 * Cross) * Deep * HATCH_A;
Out = lerp(Out, INK, Hatch * (Sky ? 0.0 : 1.0));

// 3. ink
float R = (Fighter ? LINE_FIGHTER : LINE_WORLD) * 0.5 * Lines;
float Silh = 0.0, Fold = 0.0;
for (int i = 0; i < 8; i++)
{
    float2 U = UV + Dir[i] * R * Px;
    float Dn = SceneTextureLookup(U, 1, false).r;
    float3 Nn = normalize(SceneTextureLookup(U, 8, false).rgb);
    Silh = max(Silh, step(DEPTH_EDGE, (Dn - D) / max(D, 1.0)));
    Fold = max(Fold, step(NORMAL_EDGE, 1.0 - dot(N, Nn)) * (Dn < SKY_DEPTH ? 1.0 : 0.0));
}
float Fade = Fighter ? 1.0 : lerp(1.0, FADE_MIN, saturate((D - FADE_NEAR) / (FADE_FAR - FADE_NEAR)));
float Ink = max(Silh, Fold * INNER_A) * Fade * (Sky ? 0.0 : 1.0);
Out = lerp(Out, INK, Ink);

// 4. sky
if (Sky)
{
    float Ls = dot(C, LUMA);
    float Lb = (floor(Ls * SKY_BANDS) + 0.5) / SKY_BANDS;
    Out = C * (Lb / max(Ls, 0.0001));
}

// 5. grade
Out = lerp(dot(Out, LUMA).xxx, Out, SATURATION) * GRADE_TINT;

// 7a. the impact frame, drawn: the lit side paper, the rest ink. It passes
// through TSR, bloom and the tonemapper after this, which soften it;
// M_Anime_Frame cuts it back to two exact colours.
float Paper = Sky ? 1.0 : (1.0 - Shad) * (1.0 - Ink);
Paper = lerp(Paper, 1.0 - Paper, ImpactInvert);
Out = lerp(Out, lerp(INK, PAPER, Paper), Impact);
return Out;
""")


def hlsl_frame():
    """M_Anime_Frame's Custom node: after tonemapping, so after TSR and
    bloom, in display values. Inputs: Impact, Speed, SpeedCentreX,
    SpeedCentreY, SpeedSeed, Scene. Returns float3.

    6. The speed lines, in the VIEWPORT's own UV -- the centre the game
       projects is a fraction of the viewport, which is not the buffer's
       UV under dynamic resolution or a screen percentage.
    7b. The impact frame cut to exactly two colours: whatever TSR's
       history, bloom or the tonemapper did to M_Anime_Post's paper and
       ink, a pixel brighter than IMPACT_CUT is paper and the rest ink, so
       one film frame is one hard cut."""
    return _sub(r"""
// ---- anime look (frame), generated by Tools/look/anime_look.py -- do not hand-edit
const float3 LUMA = float3(0.2126, 0.7152, 0.0722);
float3 S = SceneTextureLookup(GetDefaultSceneTextureUV(Parameters, 14), 14, false).rgb;
float2 UV = GetDefaultSceneTextureUV(Parameters, 1);
float D = SceneTextureLookup(UV, 1, false).r;
float CD = SceneTextureLookup(UV, 13, false).r;
bool Fighter = CD < D + 2.0;

// 7b. the cut
float3 Out = lerp(S, dot(S, LUMA) > IMPACT_CUT ? PAPER_D : INK_D, step(0.5, Impact));

// 6. speed lines, behind the figures as a panel draws them
float2 VUV = GetViewportUV(Parameters);
float Aspect = View.ViewSizeAndInvSize.x * View.ViewSizeAndInvSize.w;
float2 V = (VUV - float2(SpeedCentreX, SpeedCentreY)) * float2(Aspect, 1.0);
float Rad = length(V);
float Ang = (atan2(V.y, V.x) / 6.2831853 + 0.5) * SPEED_COUNT;
float Cell = floor(Ang);
float Rnd = frac(sin(Cell * 12.9898 + SpeedSeed * 78.233) * 43758.5453);
float Streak = step(frac(Ang), 0.12 + 0.30 * Rnd) * step(0.45, Rnd);
float Reach = smoothstep(SPEED_INNER + 0.25 * Rnd * SPEED_INNER, SPEED_OUTER, Rad);
Out = lerp(Out, INK_D, Streak * Reach * Speed * SPEED_A * (Fighter ? SPEED_ON_FIGHTER : 1.0));
return Out;
""")


# ------------------------------------------------------------ numpy mirror
def _smooth(e0, e1, x):
    import numpy as np
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _shift(a, dx, dy, fill):
    """a[y + dy, x + dx], edges filled -- a texture lookup `(dx, dy)` pixels
    away, rounded to whole pixels as a point-sampled lookup is."""
    import numpy as np
    dx, dy = int(round(dx)), int(round(dy))
    out = np.empty_like(a)
    out[...] = fill
    H, W = a.shape[:2]
    ys = slice(max(0, -dy), min(H, H - dy))
    yd = slice(max(0, dy), min(H, H + dy))
    xs = slice(max(0, -dx), min(W, W - dx))
    xd = slice(max(0, dx), min(W, W + dx))
    out[ys, xs] = a[yd, xd]
    return out


def preview(C, A, N, D, fighter, key=None, impact=0.0, invert=0.0):
    """M_Anime_Post's steps on arrays: C the pre-exposed lit colour and A
    the base colour (H,W,3 linear), N world normals (H,W,3), D depth in cm
    (H,W), fighter a mask (H,W bool) of what writes custom depth. Row 0 is
    the TOP of the picture, as a screen UV has it. Returns linear RGB in
    the buffer's own units, and the masks."""
    import numpy as np
    L = LOOK
    key = L["KEY"] if key is None else key
    H, W = D.shape
    lines = H / 1080.0
    luma = np.array(LUMA)
    sky = D > L["SKY_DEPTH_CM"]
    lerp = lambda a, b, t: a + (b - a) * t
    fr = lambda v: v - np.floor(v)

    # The light, averaged over a few pixels of the same surface: the ratio
    # of summed lit colour to summed base colour, so the base colour's own
    # fine detail (pores, stubble, weave) does not push single pixels back
    # and forth across a terminator -- that is what breaks a face into
    # blotches. Neighbours across a depth jump do not count.
    lc, la = C @ luma, A @ luma
    sc, sa = lc.copy(), la.copy()
    r = L["SMOOTH_PX"] * lines
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                   (.7071, .7071), (-.7071, .7071), (.7071, -.7071), (-.7071, -.7071)):
        Dn = _shift(D, dx * r, dy * r, 1e10)
        same = np.abs(Dn - D) <= 0.02 * np.maximum(D, 1.0)
        sc += np.where(same, _shift(lc, dx * r, dy * r, 0.0), 0.0)
        sa += np.where(same, _shift(la, dx * r, dy * r, 0.0), 0.0)
    T = sc / np.maximum(sa, 0.02) / max(key, 0.001)
    s = L["SOFT"]
    deep = 1.0 - _smooth(L["T_DEEP"] - s, L["T_DEEP"] + s, T)
    shad = 1.0 - _smooth(L["T_SHADOW"] - s, L["T_SHADOW"] + s, T)
    high = _smooth(L["T_HIGHLIGHT"] - s, L["T_HIGHLIGHT"] + s, T)
    Q = lerp(lerp(lerp(L["Q_LIT"], L["Q_HIGHLIGHT"], high), L["Q_SHADOW"], shad), L["Q_DEEP"], deep)
    hue = C / np.maximum(A, 0.02)
    hue = np.clip(lerp(np.ones(3), hue / np.maximum(hue @ luma, 1e-4)[..., None], L["TINT_KEEP"]), 0.0, 2.0)
    out = A * (Q * key)[..., None] * hue
    out = out * lerp(np.ones(3), np.array(L["SHADOW_TINT"]), shad[..., None])
    out = lerp(out, C, _smooth(L["EMIT_FROM"], 2.0 * L["EMIT_FROM"], T)[..., None])

    # 2. hatching, in pixels of a 1080-line picture (pixel centres, as UV)
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    sx, sy = (xx + 0.5) / lines, (yy + 0.5) / lines
    h1 = (fr((sx + sy) / L["HATCH_PX"]) <= L["HATCH_WIDTH"]).astype(float)
    h2 = (fr((sx - sy) / L["HATCH_PX"]) <= L["HATCH_WIDTH"]).astype(float)
    cross = 1.0 - _smooth(L["CROSS_BELOW"] - s, L["CROSS_BELOW"] + s, T)
    hatch = np.clip(h1 + h2 * cross, 0, 1) * deep * L["HATCH_ALPHA"] * (~sky)
    ink = np.array(L["INK"])
    out = lerp(out, ink, hatch[..., None])

    # 3. ink, eight neighbours at the line's half width
    silh = np.zeros((H, W)); fold = np.zeros((H, W))
    for R, mask in ((L["LINE_FIGHTER_PX"] * 0.5 * lines, fighter),
                    (L["LINE_WORLD_PX"] * 0.5 * lines, ~fighter)):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                       (.7071, .7071), (-.7071, .7071), (.7071, -.7071), (-.7071, -.7071)):
            Dn = _shift(D, dx * R, dy * R, 1e10)
            Nn = _shift(N, dx * R, dy * R, 0.0)
            e = ((Dn - D) / np.maximum(D, 1.0) >= L["DEPTH_EDGE"]).astype(float)
            f = ((1.0 - np.sum(N * Nn, axis=2)) >= L["NORMAL_EDGE"]).astype(float) * (Dn < L["SKY_DEPTH_CM"])
            silh = np.where(mask, np.maximum(silh, e), silh)
            fold = np.where(mask, np.maximum(fold, f), fold)
    fade = np.where(fighter, 1.0, lerp(1.0, L["FADE_MIN"],
                    np.clip((D - L["FADE_NEAR_CM"]) / (L["FADE_FAR_CM"] - L["FADE_NEAR_CM"]), 0, 1)))
    inkw = np.maximum(silh, fold * L["INNER_ALPHA"]) * fade * (~sky)
    out = lerp(out, ink, inkw[..., None])

    # 4. sky
    Ls = C @ luma
    Lb = (np.floor(Ls * L["SKY_BANDS"]) + 0.5) / L["SKY_BANDS"]
    out = np.where(sky[..., None], C * (Lb / np.maximum(Ls, 1e-4))[..., None], out)

    # 5. grade
    out = lerp((out @ luma)[..., None], out, L["SATURATION"]) * np.array(L["GRADE_TINT"])

    # 7a. the impact frame, drawn
    if impact > 0.0:
        paper = np.where(sky, 1.0, (1.0 - shad) * (1.0 - inkw))
        paper = lerp(paper, 1.0 - paper, invert)
        out = lerp(out, lerp(ink, np.array(L["PAPER"]), paper[..., None]), impact)
    return out, {"T": T, "deep": deep, "shadow": shad, "ink": inkw, "hatch": hatch}


def frame(S, fighter, impact=0.0, speed=0.0, centre=(0.5, 0.5), seed=0.0):
    """M_Anime_Frame's steps on a display-valued picture S (H,W,3, 0..1)."""
    import numpy as np
    L = LOOK
    H, W = S.shape[:2]
    luma = np.array(LUMA)
    lerp = lambda a, b, t: a + (b - a) * t
    fr = lambda v: v - np.floor(v)
    out = S.copy()
    if impact >= 0.5:
        cut = (S @ luma > L["IMPACT_CUT"])[..., None]
        out = np.where(cut, np.array(display(L["PAPER"])), np.array(display(L["INK"])))
    if speed > 0.0:
        yy, xx = np.mgrid[0:H, 0:W].astype(float)
        vx = ((xx + 0.5) / W - centre[0]) * (W / H)
        vy = (yy + 0.5) / H - centre[1]
        rad = np.hypot(vx, vy)
        ang = (np.arctan2(vy, vx) / (2 * math.pi) + 0.5) * L["SPEED_COUNT"]
        rnd = fr(np.sin(np.floor(ang) * 12.9898 + seed * 78.233) * 43758.5453)
        streak = (fr(ang) <= 0.12 + 0.30 * rnd) * (rnd >= 0.45)
        reach = _smooth(L["SPEED_INNER"] + 0.25 * rnd * L["SPEED_INNER"], L["SPEED_OUTER"], rad)
        a = streak * reach * speed * L["SPEED_ALPHA"] * np.where(fighter, L["SPEED_ON_FIGHTER"], 1.0)
        out = lerp(out, np.array(display(L["INK"])), a[..., None])
    return out


def to_display(lin):
    """Linear to display values with a plain clip -- the preview's
    stand-in for the engine's tonemapper. The look's tones are flat by
    construction, so there is little highlight roll-off to lose."""
    import numpy as np
    c = np.clip(lin, 0.0, 1.0)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def look(C, A, N, D, fighter, key=None, impact=0.0, invert=0.0, speed=0.0,
         centre=(0.5, 0.5), seed=0.0):
    """Both materials, in the engine's order: M_Anime_Post, the
    tonemapper's stand-in, M_Anime_Frame. Returns display values (0..1)
    and M_Anime_Post's masks."""
    out, m = preview(C, A, N, D, fighter, key=key, impact=impact, invert=invert)
    return frame(to_display(out), fighter, impact=impact, speed=speed, centre=centre, seed=seed), m


def to_8bit(disp):
    import numpy as np
    return (np.clip(disp, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


# -------------------------------------------------------------------- check
def _sphere(n=720):
    """A lit sphere in front of a far wall and a sky: the look's every step
    has somewhere to show. Key light from the upper left."""
    import numpy as np
    yy, xx = np.mgrid[0:n, 0:n].astype(float)
    u, v = (xx + 0.5) / n * 2 - 1, (yy + 0.5) / n * 2 - 1
    r2 = u * u + v * v
    on = r2 < 0.6 ** 2
    z = np.sqrt(np.clip(0.36 - r2, 0, None))
    N = np.zeros((n, n, 3)); N[..., 0] = u / 0.6; N[..., 1] = -v / 0.6; N[..., 2] = z / 0.6
    N[~on] = (0, 0, 1)
    light = np.array([-0.5, 0.6, 0.62]); light /= np.linalg.norm(light)
    ndl = np.clip(N @ light, 0, None)
    A = np.where(on[..., None], np.array([0.45, 0.28, 0.20]), np.array([0.30, 0.30, 0.30]))
    C = A * (ndl * 1.0 + 0.04)[..., None]
    D = np.where(on, 300.0 - z * 100.0, 900.0)
    D[: n // 5] = np.where(on[: n // 5], D[: n // 5], 1e10)  # a strip of sky
    C[: n // 5][~on[: n // 5]] = (0.35, 0.45, 0.65)
    A[: n // 5][~on[: n // 5]] = 0.0
    return C, A, N, D, on


def check(bite=None):
    """What the look promises, on the sphere. `bite` breaks one thing to
    prove the check that guards it fails."""
    import numpy as np
    global LOOK
    saved = dict(LOOK)
    try:
        if bite == "no_terminator":
            LOOK["Q_SHADOW"] = LOOK["Q_LIT"]; LOOK["Q_DEEP"] = LOOK["Q_LIT"]
        if bite == "no_ink":
            LOOK["DEPTH_EDGE"] = 99.0; LOOK["NORMAL_EDGE"] = 99.0
        if bite == "sky_shaded":
            LOOK["SKY_DEPTH_CM"] = 1e12
        if bite == "lines_over_men":
            LOOK["SPEED_ON_FIGHTER"] = 1.0
        if bite == "flat_impact":
            LOOK["PAPER"] = LOOK["INK"]
        if bite == "no_cut":
            LOOK["IMPACT_CUT"] = -1.0
        C, A, N, D, on = _sphere()
        out, m = preview(C, A, N, D, on)
        luma = np.array(LUMA)
        rel = (out @ luma) / np.maximum(A @ luma, 1e-6)
        body = on & (m["ink"] < 0.01) & (m["hatch"] < 0.01)
        # 1. three tones: the body's relative brightness clusters at the tones
        lit = body & (m["T"] > LOOK["T_SHADOW"] + 0.1) & (m["T"] < LOOK["T_HIGHLIGHT"] - 0.1)
        sh = body & (m["T"] < LOOK["T_SHADOW"] - 0.1) & (m["T"] > LOOK["T_DEEP"] + 0.1)
        assert lit.sum() > 500 and sh.sum() > 500, "the sphere has a lit and a shadow side"
        assert np.ptp(rel[lit]) < 0.12 and np.ptp(rel[sh]) < 0.12, "each tone is flat"
        assert np.median(rel[lit]) > 1.6 * np.median(rel[sh]), "the terminator is a step"
        # 3. a silhouette line all round the sphere's edge
        ring = on & (~_shift(on, 1, 0, False) | ~_shift(on, -1, 0, False)
                     | ~_shift(on, 0, 1, False) | ~_shift(on, 0, -1, False))
        assert m["ink"][ring].mean() > 0.6, "the sphere is outlined"
        assert m["ink"][on & ~ring].mean() < 0.05, "no ink inside a smooth sphere"
        # 4. the sky is banded, not shaded: few distinct levels
        sky = D > LOOK["SKY_DEPTH_CM"]
        assert sky.sum() > 1000, "the sky is recognised"
        assert len(np.unique(np.round(out[sky] @ luma, 5))) <= LOOK["SKY_BANDS"] + 1, "the sky is banded"
        # 7. the impact frame is exactly two colours after the cut, and flips
        f0, _ = look(C, A, N, D, on, impact=1.0)
        f1, _ = look(C, A, N, D, on, impact=1.0, invert=1.0)
        colours = np.unique(np.round(f0.reshape(-1, 3), 4), axis=0)
        assert len(colours) == 2, "the impact frame is exactly ink and paper"
        l0, l1 = f0 @ luma, f1 @ luma
        assert np.ptp(l0) > 0.5, "the impact frame is ink and paper"
        assert (l0[lit] > 0.5).mean() > 0.95 and (l1[lit] < 0.3).mean() > 0.95, "and it flips"
        # 6. speed lines: clear at the blow, streaked away from it, not on a fighter
        base, _ = look(C, A, N, D, on)
        sp, _ = look(C, A, N, D, on, speed=1.0, centre=(0.5, 0.5))
        diff = np.abs(sp - base).sum(axis=2) > 0.05
        n = D.shape[0]
        yy, xx = np.mgrid[0:n, 0:n]
        rr = np.hypot((xx + .5) / n - .5, (yy + .5) / n - .5)
        assert diff[rr < LOOK["SPEED_INNER"]].mean() == 0.0, "the blow itself is clear"
        assert 0.1 < diff[rr > LOOK["SPEED_OUTER"]].mean() < 0.7, "streaks, not a fill"
        assert diff[on].mean() == 0.0, "the speed lines stop at a fighter"
    finally:
        LOOK.clear(); LOOK.update(saved)
    return True


def _check_names():
    """MPC_Anime's parameters are the names Combat/SaudAnime.h writes, and
    both materials read the ones they are given."""
    h = open(os.path.join(ROOT, "Source", "SaudFighter", "Combat", "SaudAnime.h")).read()
    for name, _ in MPC_SCALARS:
        assert '"%s"' % name in h, "SaudAnime.h does not write %s" % name
    for path in (MPC_PATH,) + tuple(MATERIALS):
        assert path.rsplit("/", 1)[1] in h, "SaudAnime.h does not load %s" % path
    import re
    for path, (code_of, inputs, _) in MATERIALS.items():
        code = code_of()
        for name in inputs:
            assert re.search(r"\b%s\b" % name, code), "%s does not read %s" % (path, name)
        left = set(re.findall(r"\b[A-Z][A-Z]+_[A-Z_]+\b|\b(?:SOFT|INK|PAPER)\b", code))
        assert not left, "placeholders left in %s: %s" % (path, sorted(left))
        assert "EyeAdaptationLookup" not in code, "the buffer is pre-exposed; do not expose it twice"


# ------------------------------------------------------------------- editor
# path -> (code, the MPC parameters it reads, where it runs)
MATERIALS = {
    MATERIAL_PATH: (hlsl, ("Impact", "ImpactInvert", "Key"), "BL_SCENE_COLOR_AFTER_DOF"),
    FRAME_PATH: (hlsl_frame, ("Impact", "Speed", "SpeedCentreX", "SpeedCentreY", "SpeedSeed"),
                 "BL_SCENE_COLOR_AFTER_TONEMAPPING"),
}


def build_in_editor():
    """MPC_Anime, M_Anime_Post and M_Anime_Frame, in /Game/Materials/Anime/.
    Read-reviewed, not run: no editor has executed this."""
    import unreal
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    EAL = unreal.EditorAssetLibrary
    MEL = unreal.MaterialEditingLibrary
    folder = MPC_PATH.rsplit("/", 1)[0]

    # The materials reference the collection: they go first.
    for path in tuple(MATERIALS) + (MPC_PATH,):
        if EAL.does_asset_exist(path) and not EAL.delete_asset(path):
            raise RuntimeError("could not delete %s -- close anything using it and run again" % path)

    mpc = tools.create_asset("MPC_Anime", folder, unreal.MaterialParameterCollection,
                             unreal.MaterialParameterCollectionFactoryNew())
    scalars = []
    for name, default in MPC_SCALARS:
        p = unreal.CollectionScalarParameter()
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", default)
        scalars.append(p)
    mpc.set_editor_property("scalar_parameters", scalars)
    EAL.save_loaded_asset(mpc)

    for path, (code_of, reads, where) in MATERIALS.items():
        name = path.rsplit("/", 1)[1]
        mat = tools.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
        mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_POST_PROCESS)
        mat.set_editor_property("blendable_location", getattr(unreal.BlendableLocation, where))

        custom = MEL.create_material_expression(mat, unreal.MaterialExpressionCustom, -400, 0)
        custom.set_editor_property("code", code_of())
        custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
        custom.set_editor_property("description", "%s (Tools/look/anime_look.py)" % name)
        inputs = []
        for input_name in reads + ("Scene",):
            ci = unreal.CustomInput()
            ci.set_editor_property("input_name", input_name)
            inputs.append(ci)
        custom.set_editor_property("inputs", inputs)

        y = -300
        for input_name in reads:
            e = MEL.create_material_expression(mat, unreal.MaterialExpressionCollectionParameter, -800, y)
            e.set_editor_property("collection", mpc)
            e.set_editor_property("parameter_name", input_name)
            MEL.connect_material_expressions(e, "", custom, input_name)
            y += 80
        scene = MEL.create_material_expression(mat, unreal.MaterialExpressionSceneTexture, -800, y)
        scene.set_editor_property("scene_texture_id", unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0)
        MEL.connect_material_expressions(scene, "Color", custom, "Scene")
        MEL.connect_material_property(custom, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        MEL.recompile_material(mat)
        EAL.save_loaded_asset(mat)
    unreal.log("Built %s, %s" % (MPC_PATH, ", ".join(MATERIALS)))


if __name__ == "__main__":
    try:
        import unreal  # noqa: F401
        IN_EDITOR = True
    except ImportError:
        IN_EDITOR = False
    if IN_EDITOR:
        build_in_editor()
    elif "--bite" in sys.argv:
        bites = ("no_terminator", "no_ink", "sky_shaded", "flat_impact", "lines_over_men", "no_cut")
        caught = 0
        for b in bites:
            try:
                check(bite=b)
                print("  %-14s NOT caught" % b)
            except AssertionError as e:
                caught += 1
                print("  %-14s caught: %s" % (b, e))
        print("%d of %d sabotages caught" % (caught, len(bites)))
        sys.exit(0 if caught == len(bites) else 1)
    else:
        check()
        _check_names()
        print("anime look: two materials generated (%d + %d lines), preview holds its checks, "
              "MPC names agree with SaudAnime.h" % (hlsl().count("\n"), hlsl_frame().count("\n")))
