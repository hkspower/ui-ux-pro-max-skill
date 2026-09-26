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
     one that thins with distance. Since 2026-09-25 ("improve all enemy
     and Saud borders"): a fighter's silhouette is centred on his edge,
     half of it drawn over what is behind him, and unbroken wherever he
     ends (his custom depth says so, whatever the depth behind); a limb
     over his own body is outlined where the depth breaks, not only where
     it jumps 7 %; a fold is read only across one surface and only with
     two sides, so noisy normals leave no specks and no ghost line lands
     on the wall beside him; every line's edge is antialiased; and the
     ink is near black, darker than his blackest kit.
  4. The sky is not shaded, it is banded: a painted gradient.
  5. A gritty grade: some saturation out, a dust-warm tint.
  6. Speed lines, radial round the blow, when the game asks for them.
  7. The impact frame: for a frame or two the whole picture goes to ink and
     ember, the lit side ember, the rest ink, and can be flipped.
  8. HAWK FIST's fire (since 2026-09-26, "build flame fire hit for Saud"):
     the flame on Saud's fist while the talent is lit, and the burst on
     the man a burning punch hit. They are the browser's own drawings --
     handFlame()'s three tongues on a shared wobble over a glow, applyHit()'s
     ring and sparks -- in the browser's figure pixels, scaled to the
     fist's own distance from the camera (Combat/SaudFire.h has every
     number and where it comes from), and made the look's: the glow banded,
     an ink line round the flame, and the flame drawn BEHIND the hand so
     the knuckles stay legible, which is the browser's own note on it.

Steps 1-5 and the impact frame's drawing are M_Anime_Post, before
tonemapping. Steps 6 and 8 and the impact frame's hard cut are a second
material, M_Anime_Frame, after tonemapping -- after TSR and bloom, which
would otherwise blend a one-frame cut through their history (found by
review, 2026-09-24); the fire is drawn before the cut, so on an impact
frame it is cut to paper and ink with everything else. Steps 6, 7 and 8
are driven by the game through the Material Parameter Collection MPC_Anime
(Combat/SaudAnime.h and Combat/SaudFire.h have the timings and the names);
everything else is a constant from LOOK, written into the HLSL when the
materials are built, so the preview and the engine read one table.

THE DARK, since 2026-09-26 ("use darker theme style like Demon's Souls",
settled as: darken the anime, not replace it -- the ink, the flat tones and
the impact frames stay, and the picture goes grim). What changed, all in
LOOK: the tones a long step down (lit 0.84, shadow 0.22, deep 0.05, and
more of the picture falls into shadow and deep shadow); the split toning
cold -- slate-blue shadows under an ashen, barely warm light; the WORLD
held darker and greyer than the fighters (WORLD_LEVEL, WORLD_SATURATION)
so a man stands out of the murk; the air a dark, cold fog that starts
close (HAZE); the sky a dim overcast (SKY_LEVEL, SKY_TINT); a vignette
(M_Anime_Frame); and warm light only from what burns -- a lamp, a lantern,
HAWK FIST -- which keeps its colour (EMIT_FROM) while everything round it
goes grey. The hit effects go with it: the impact frame is ink and EMBER,
not ink and paper; more of the speed lines are blood; the fire is embers
(FIRE's colours, not its shapes). The HUD's bone lettering is BONE.

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
    # 2026-09-26, the dark: more of the picture in shadow (0.50 / 0.09
    # before) and every tone a long step down, so the lit side is a slice
    # of light out of the murk rather than the picture's default
    "T_SHADOW": 0.56,
    "T_DEEP": 0.14,
    "T_HIGHLIGHT": 1.90,     # only real glare: lower, it spotted every face
    "SOFT": 0.020,          # half-width of each terminator, for antialiasing
    "SMOOTH_PX": 3.0,       # the light is averaged this far (1080 lines) first
    # 2026-09-25, "improve colours": shadow 0.42 -> 0.38, deep 0.16 -> 0.13.
    # 2026-09-26, the dark: lit 1.00 -> 0.84, shadow -> 0.22, deep -> 0.05
    # (near black: the shadow side of a Souls knight), the glint 1.28 ->
    # 1.10 so sweat catches without lighting the face
    "Q_LIT": 0.84,
    "Q_SHADOW": 0.22,
    "Q_DEEP": 0.05,
    "Q_HIGHLIGHT": 1.10,
    # Split toning: shadows lean to a cool slate, the lit side to dust-warm,
    # so light and shade differ in hue as well as value -- the depth a
    # painted cel has. Until 2026-09-25 one warm tint lay over everything
    # and the shadows' faint cool was cancelled by it.
    # 2026-09-26, the dark: colder -- slate-blue shadows, an ashen light
    # that is barely warm; the warmth is left to what burns
    "SHADOW_TINT": (0.78, 0.88, 1.04),
    "LIT_TINT": (1.02, 1.00, 0.94),
    "TINT_KEEP": 0.6,       # how much of the light's hue the tone keeps
    "EMIT_FROM": 5.0,       # light this many times the key is a lamp, not a surface
    # 2. hatching, in pixels of a 1080-line picture
    "HATCH_PX": 5.0,
    "HATCH_WIDTH": 0.34,    # share of each period that is ink
    "HATCH_ALPHA": 0.55,
    "CROSS_BELOW": 0.06,    # light under this is cross-hatched
    # 3. ink
    # Ink is the darkest thing in the picture. It was 0.030 linear -- a
    # mid-grey once exposed, lighter than a black tee, so round dark kit the
    # outline read as a pale halo (anime-men.png, 2026-09-24).
    # 2026-09-26: darker still (0.004 before), so it stays under a black
    # tee lit at the darker Q_LIT
    "INK": (0.0022, 0.0019, 0.0017),
    # The silhouette round a fighter is centred on his edge: OUTER_SHARE of
    # it outside him, over whatever is behind (found by his custom depth).
    # Until 2026-09-25 only the inside was drawn, at half this width.
    "LINE_FIGHTER_PX": 4.2,  # silhouette width round a fighter, at 1080 lines
    "OUTER_SHARE": 0.5,
    "LINE_WORLD_PX": 2.2,
    "LINE_AA_PX": 1.0,       # each line's edge is ramped over this many pixels
    "DEPTH_EDGE": 0.07,      # a jump of 7 % of the distance is a silhouette
    # On a fighter, a limb over his own body is a silhouette too: 7 % of 4 m
    # is 28 cm, and an arm across a chest is less. There the line is where
    # the depth BREAKS -- the jump to the far side less the slope on the near
    # side, so a surface seen edge-on draws nothing -- by this many cm.
    "FIGHTER_EDGE_CM": 5.0,
    "NORMAL_EDGE": 0.40,     # 1 - cos between normals that is a fold
    # A fold has two sides: of the eight neighbours, some differ and some do
    # not. One pixel of noise in the normals differs from all eight, and its
    # neighbours from one each -- specks, not a line.
    "FOLD_MIN": 2,
    "FOLD_MAX": 5,
    "INNER_ALPHA": 0.85,
    "FADE_NEAR_CM": 1500.0,  # world lines full strength to here...
    "FADE_FAR_CM": 20000.0,  # ...and down to FADE_MIN by here
    "FADE_MIN": 0.50,
    # 4. sky
    "SKY_DEPTH_CM": 1.0e6,
    "SKY_BANDS": 7.0,
    # 5. grade. Colour is held a little under what the surfaces are (the
    # grit), except the two things the art direction lets shout: the
    # blood-red (Kuwait's red on Saud, a boss's band) and a lamp's own
    # light, which keep all of theirs and a touch more.
    # 2026-09-26, the dark: 0.88 -> 0.66 on a fighter, and the world
    # further: held darker (WORLD_LEVEL) and greyer (WORLD_SATURATION) than
    # the men in it, so a fighter stands out of the murk as a Souls knight
    # does out of Boletaria's grey. A lamp keeps its own light (EMIT_FROM).
    "SATURATION": 0.66,
    "WORLD_SATURATION": 0.42,
    "WORLD_LEVEL": 0.62,
    "ACCENT_FROM": 0.80,     # a red this pure -- (r - max(g, b)) / r -- starts to count
    "ACCENT_FULL": 0.92,     # ...and is all accent here: #c8102e is 0.95, a rust tee 0.74
    "ACCENT_SAT": 1.06,
    # Air: the world, not a fighter, goes toward a dusty dusk as it recedes
    # -- a painted background's depth, the souq's far walls behind the fight
    # softer and warmer than the stall beside it. Albedo-like, times Key.
    # 2026-09-26, the dark: a cold, dark fog that starts close and eats
    # the distance (a dusty dusk from 15 m to 250 m, 0.35, before)
    "HAZE": (0.13, 0.145, 0.15),
    "HAZE_NEAR_CM": 600.0,
    "HAZE_FAR_CM": 9000.0,
    "HAZE_MAX": 0.62,
    # the sky: a dim overcast, cold, still banded
    "SKY_LEVEL": 0.30,
    "SKY_TINT": (0.86, 0.93, 1.00),
    # the vignette, in M_Anime_Frame on display values: the corners down
    # by VIGNETTE, from VIGNETTE_FROM of the way out (1 is a corner)
    "VIGNETTE": 0.50,
    "VIGNETTE_FROM": 0.45,
    "VIGNETTE_TO": 1.05,
    # 6. speed lines
    "SPEED_COUNT": 90.0,
    "SPEED_INNER": 0.16,     # clear circle round the blow, share of height
    "SPEED_OUTER": 0.62,
    "SPEED_ALPHA": 0.80,
    "SPEED_ON_FIGHTER": 0.0,  # the lines stop at a fighter
    # A share of the streaks is drawn in blood rather than ink: a two-tone
    # panel, the red the HUD gives an enemy's health (#8e1420). Linear.
    "BLOOD": (0.2705, 0.0070, 0.0144),
    "SPEED_RED": 0.27,      # 2026-09-26: 0.22 -> 0.27, more of it blood
    # 7. impact frame. 2026-09-26, the dark: its light half is an EMBER --
    # a blood-orange, the colour of what burns -- where it was paper
    # (a warm newsprint, 0.93 0.88 0.78). BONE is the HUD's lettering, dim
    # parchment on dark panels; SaudHUD.cpp draws in INK and BONE, checked
    # below.
    "EMBER": (0.80, 0.26, 0.07),
    "BONE": (0.56, 0.52, 0.44),
    "IMPACT_CUT": 0.45,       # display luminance above which the cut frame is ember
    # 8. HAWK FIST's fire: what the look adds to the browser's drawing
    # (the drawing itself is FIRE, below). The flame is drawn only on
    # pixels this far BEHIND the fist's centre, so the hand itself covers
    # it; the burst only on pixels not this far in front of the man hit,
    # so he wears it and a man between him and the camera hides it.
    "FIRE_BEHIND_CM": 3.0,
    "BURST_BEHIND_CM": 40.0,
    "FIRE_INK_PX": 2.2,       # the ink line round the flame, at 1080 lines (the world's)
    "GLOW_STEPS": 3,          # the glow's gradient cut to this many flat rings
    # the defaults of the game-driven parameters
    "KEY": 1.0,
}

# HAWK FIST's drawing, the browser's (saud-fighter/index.html handFlame()
# :1206, burst() :775, ring() :765, drawFx() :807, applyHit() :3538). Sizes
# are the browser's FIGURE pixels -- a standing fighter is 148 px tall for
# 180 cm -- and Combat/SaudFire.h quotes the same numbers for the game;
# _check_names() holds this table to that header. The shapes and timings
# are the browser's; the COLOURS are the dark theme's since 2026-09-26 --
# the browser's pale yellow flame and sparks read as a torch in daylight,
# so they are embers here: an orange tongue over a deep red one with a
# pale-hot core, a glow going to blood, ember sparks. (The browser's were
# tongues 255,196,72 / 255,124,32 / 255,238,196, glow 255,238,190 ->
# 255,150,44 -> 200,40,10, ring #ffb04a, sparks 255,168,52 / 255,238,190.)
FIRE = {
    "FIGURE_PX": 148.0,
    "FIGURE_CM": 180.0,
    "TONGUE_ROOT_PX": 3.0,                       # a tongue starts 3 px behind the fist
    "TONGUE_W": tuple(5.2 - 1.1 * i for i in range(3)),        # half-widths
    "TONGUE_LEN": tuple(20.0 - 4.5 * i for i in range(3)),     # times the heat
    "TONGUE_COL": ((255, 120, 32, 0.92), (214, 54, 14, 0.88), (255, 196, 120, 0.95)),
    "SWAY_RATE": 11.0, "SWAY_PHASE": 2.1, "SWAY_PX": 3.2,
    "GLOW_CX": 2.0, "GLOW_R": 26.0,              # radius times the heat
    "GLOW_MID": 0.45,                            # the gradient's middle stop
    "GLOW_COL": ((255, 170, 90, 0.80), (210, 70, 16, 0.42), (120, 14, 4, 0.0)),
    "RING_FROM": 8.0, "RING_TO": 74.0, "RING_S": 0.28, "RING_A": 0.85, "RING_W": 6.0, "RING_SQUASH": 0.62,
    "RING_COL": (230, 92, 28, 1.0),
    "SPARKS_HOT": 14, "SPARKS_PALE": 8,
    "SPARK_SPD": (300.0, 190.0), "SPARK_SHARE_MIN": 0.3,
    "SPARK_LIFT": 40.0, "SPARK_G": 460.0, "SPARK_DRAG": 2.4493,
    "SPARK_LIFE": (0.25, 0.55), "SPARK_R": (2.0, 5.0),
    "SPARK_COL": ((255, 110, 30, 0.95), (255, 190, 110, 0.95)),
}


def _rgb(c):
    """A browser rgba's colour as display values (0..1)."""
    return tuple(v / 255.0 for v in c[:3])

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
    # HAWK FIST (Combat/SaudFire.h, Param): the fist on screen and the man hit
    ("FireHeat", 0.0),      # 0: no flame; the browser's 0.78 standing, 1.25 through a punch
    ("FireX", 0.5), ("FireY", 0.5),          # the fist, 0..1 of the viewport, Y down
    ("FireDirX", 0.0), ("FireDirY", -1.0),   # along the forearm, unit, aspect applied
    ("FireDepth", 0.0),     # scene depth of the fist, cm
    ("FireScale", 0.0),     # one figure pixel there, as a share of the viewport's height
    ("FireTime", 0.0),      # game seconds, for the sway
    ("BurnAge", -1.0),      # seconds since a burning punch landed; < 0: none
    ("BurnX", 0.5), ("BurnY", 0.5),
    ("BurnDepth", 0.0),
    ("BurnScale", 0.0),
    ("BurnSeed", 0.0),      # a new set of sparks every burst
)
FIRE_PARAMS = ("FireHeat", "FireX", "FireY", "FireDirX", "FireDirY", "FireDepth", "FireScale", "FireTime",
               "BurnAge", "BurnX", "BurnY", "BurnDepth", "BurnScale", "BurnSeed")

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
        "INK_D": _f3(display(L["INK"])), "EMBER_D": _f3(display(L["EMBER"])),
        "INK": _f3(L["INK"]), "EMBER": _f3(L["EMBER"]),
        "WORLD_SATURATION": _f(L["WORLD_SATURATION"]), "WORLD_LEVEL": _f(L["WORLD_LEVEL"]),
        "SKY_LEVEL": _f(L["SKY_LEVEL"]), "SKY_TINT": _f3(L["SKY_TINT"]),
        "VIGNETTE_FROM": _f(L["VIGNETTE_FROM"]), "VIGNETTE_TO": _f(L["VIGNETTE_TO"]), "VIGNETTE": _f(L["VIGNETTE"]),
        "LINE_FIGHTER": _f(L["LINE_FIGHTER_PX"]), "LINE_WORLD": _f(L["LINE_WORLD_PX"]),
        "DEPTH_EDGE": _f(L["DEPTH_EDGE"]), "NORMAL_EDGE": _f(L["NORMAL_EDGE"]),
        "FIGHTER_EDGE": _f(L["FIGHTER_EDGE_CM"]), "FOLD_MIN": _f(L["FOLD_MIN"]), "FOLD_MAX": _f(L["FOLD_MAX"]),
        "OUTER_SHARE": _f(L["OUTER_SHARE"]), "LINE_AA": _f(L["LINE_AA_PX"]),
        "INNER_A": _f(L["INNER_ALPHA"]), "FADE_NEAR": _f(L["FADE_NEAR_CM"]),
        "FADE_FAR": _f(L["FADE_FAR_CM"]), "FADE_MIN": _f(L["FADE_MIN"]),
        "SATURATION": _f(L["SATURATION"]), "LIT_TINT": _f3(L["LIT_TINT"]),
        "ACCENT_FROM": _f(L["ACCENT_FROM"]), "ACCENT_FULL": _f(L["ACCENT_FULL"]), "ACCENT_SAT": _f(L["ACCENT_SAT"]),
        "HAZE_NEAR": _f(L["HAZE_NEAR_CM"]), "HAZE_FAR": _f(L["HAZE_FAR_CM"]), "HAZE_MAX": _f(L["HAZE_MAX"]),
        "HAZE": _f3(L["HAZE"]),
        "BLOOD_D": _f3(display(L["BLOOD"])), "SPEED_RED": _f(L["SPEED_RED"]),
        "SPEED_COUNT": _f(L["SPEED_COUNT"]), "SPEED_INNER": _f(L["SPEED_INNER"]),
        "SPEED_OUTER": _f(L["SPEED_OUTER"]), "SPEED_ON_FIGHTER": _f(L["SPEED_ON_FIGHTER"]),
        "SPEED_A": _f(L["SPEED_ALPHA"]), "IMPACT_CUT": _f(L["IMPACT_CUT"]),
        "FIRE_BEHIND": _f(L["FIRE_BEHIND_CM"]), "BURST_BEHIND": _f(L["BURST_BEHIND_CM"]),
        "FIRE_INK": _f(L["FIRE_INK_PX"]), "GLOW_STEPS": _f(L["GLOW_STEPS"]),
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
Out *= lerp(LIT_TINT, SHADOW_TINT, Shad);
float Emit = smoothstep(EMIT_FROM, 2.0 * EMIT_FROM, T);
Out = lerp(Out, C, Emit);

// 2. hatching, in pixels of a 1080-line view, fixed to the view
float2 Sp = GetViewportUV(Parameters) * View.ViewSizeAndInvSize.xy / Lines;
float H1 = step(frac((Sp.x + Sp.y) / HATCH_PX), HATCH_W);
float H2 = step(frac((Sp.x - Sp.y) / HATCH_PX), HATCH_W);
float Cross = 1.0 - smoothstep(CROSS_BELOW - SOFT, CROSS_BELOW + SOFT, T);
float Hatch = saturate(H1 + H2 * Cross) * Deep * HATCH_A;
Out = lerp(Out, INK, Hatch * (Sky ? 0.0 : 1.0));

// 3. ink. Each ring is tested at half a pixel either side of its radius and
// the two averaged, so a line's edge is antialiased rather than stepped.
float R = (Fighter ? LINE_FIGHTER * (1.0 - OUTER_SHARE) : LINE_WORLD * 0.5) * Lines;
float Ro = LINE_FIGHTER * OUTER_SHARE * Lines;
float Silh = 0.0, Outer = 0.0, Fold = 0.0, Folds = 0.0;
for (int k = 0; k < 2; k++)
{
    float Rk = max(R + (k == 0 ? -0.5 : 0.5) * LINE_AA, 0.0);
    float Rok = max(Ro + (k == 0 ? -0.5 : 0.5) * LINE_AA, 0.0);
    float S = 0.0, O = 0.0;
    for (int i = 0; i < 8; i++)
    {
        float2 U = UV + Dir[i] * Rk * Px;
        float Dn = SceneTextureLookup(U, 1, false).r;
        float Do = SceneTextureLookup(UV - Dir[i] * Rk * Px, 1, false).r;
        float CDn = SceneTextureLookup(U, 13, false).r;
        bool Fn = CDn < Dn + 2.0;
        // the depth jumps away from here, or (on a fighter) breaks
        float Jump = step(DEPTH_EDGE, (Dn - D) / max(D, 1.0));
        float Break = (Fighter && Dn - D >= 0.5 * FIGHTER_EDGE && Dn + Do - 2.0 * D >= FIGHTER_EDGE) ? 1.0 : 0.0;
        // a fighter's own edge: he ends here, whatever is behind him
        float Leave = (Fighter && !Fn && Dn > D) ? 1.0 : 0.0;
        S = max(S, max(Jump, max(Break, Leave)));
        // the outside half of a fighter's line, on what is behind him
        float2 Uo = UV + Dir[i] * Rok * Px;
        float Dno = SceneTextureLookup(Uo, 1, false).r;
        float CDo = SceneTextureLookup(Uo, 13, false).r;
        O = max(O, (!Fighter && Ro > 0.0 && CDo < Dno + 2.0 && Dno < D) ? 1.0 : 0.0);
        if (k == 1)
        {
            float3 Nn = normalize(SceneTextureLookup(U, 8, false).rgb);
            // only across the same surface: a fold read across a depth jump
            // was a ghost line on the wall beside every fighter
            float Same = abs(Dn - D) < (Fighter ? FIGHTER_EDGE : DEPTH_EDGE * max(D, 1.0)) ? 1.0 : 0.0;
            Folds += step(NORMAL_EDGE, 1.0 - dot(N, Nn)) * (Dn < SKY_DEPTH ? 1.0 : 0.0) * Same;
        }
    }
    Silh += 0.5 * S;
    Outer += 0.5 * O;
}
Fold = (Folds >= FOLD_MIN && Folds <= FOLD_MAX) ? 1.0 : 0.0;
float Fade = Fighter ? 1.0 : lerp(1.0, FADE_MIN, saturate((D - FADE_NEAR) / (FADE_FAR - FADE_NEAR)));
float Ink = max(max(Silh, Fold * INNER_A) * Fade, Outer) * (Sky && Outer <= 0.0 ? 0.0 : 1.0);
Out = lerp(Out, INK, Ink);

// 4. sky: banded, and a dim cold overcast
if (Sky)
{
    float Ls = dot(C, LUMA);
    float Lb = (floor(Ls * SKY_BANDS) + 0.5) / SKY_BANDS;
    Out = lerp(C * (Lb / max(Ls, 0.0001)) * SKY_LEVEL * SKY_TINT, INK, Outer);   // a fighter's line over the sky
}

// 5. grade: the world held down under the men in it (not a lamp), the
// air over it, then colour held under except the accents -- and the
// world greyer than a fighter
if (!Fighter && !Sky)
{
    Out *= lerp(WORLD_LEVEL, 1.0, Emit);
    float Air = HAZE_MAX * smoothstep(HAZE_NEAR, HAZE_FAR, D);
    Out = lerp(Out, HAZE * Key, Air);
}
float Red = (Out.r - max(Out.g, Out.b)) / max(Out.r, 0.0001);
float Accent = max(smoothstep(ACCENT_FROM, ACCENT_FULL, Red), Sky ? 0.0 : Emit);   // the sky has no base colour: not a lamp
float SatBase = Fighter ? SATURATION : WORLD_SATURATION;
Out = lerp(dot(Out, LUMA).xxx, Out, lerp(SatBase, ACCENT_SAT, Accent));

// 7a. the impact frame, drawn: the lit side ember, the rest ink. It passes
// through TSR, bloom and the tonemapper after this, which soften it;
// M_Anime_Frame cuts it back to two exact colours.
float Paper = Sky ? 1.0 : (1.0 - Shad) * (1.0 - Ink);
Paper = lerp(Paper, 1.0 - Paper, ImpactInvert);
Out = lerp(Out, lerp(INK, EMBER, Paper), Impact);
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
       history, bloom or the tonemapper did to M_Anime_Post's ember and
       ink, a pixel brighter than IMPACT_CUT is ember and the rest ink, so
       one film frame is one hard cut.
    And first, the vignette (2026-09-26, the dark): the picture's corners
    taken down by VIGNETTE, before the fire (a flame is light) and the
    cut."""
    return _sub(r"""
// ---- anime look (frame), generated by Tools/look/anime_look.py -- do not hand-edit
const float3 LUMA = float3(0.2126, 0.7152, 0.0722);
float3 S = SceneTextureLookup(GetDefaultSceneTextureUV(Parameters, 14), 14, false).rgb;
float2 UV = GetDefaultSceneTextureUV(Parameters, 1);
float D = SceneTextureLookup(UV, 1, false).r;
float CD = SceneTextureLookup(UV, 13, false).r;
bool Fighter = CD < D + 2.0;

// the vignette: the corners into the dark (1 is a corner, whatever the aspect)
float2 VUV = GetViewportUV(Parameters);
float Aspect = View.ViewSizeAndInvSize.x * View.ViewSizeAndInvSize.w;
float Vr = length((VUV - 0.5) * float2(Aspect, 1.0)) / (0.5 * sqrt(Aspect * Aspect + 1.0));
float3 Out = S * (1.0 - VIGNETTE * smoothstep(VIGNETTE_FROM, VIGNETTE_TO, Vr));
""") + hlsl_fire() + _sub(r"""
// 7b. the cut (the fire is cut with everything else)
Out = lerp(Out, dot(Out, LUMA) > IMPACT_CUT ? EMBER_D : INK_D, step(0.5, Impact));

// 6. speed lines, behind the figures as a panel draws them
float2 V = (VUV - float2(SpeedCentreX, SpeedCentreY)) * float2(Aspect, 1.0);
float Rad = length(V);
float Ang = (atan2(V.y, V.x) / 6.2831853 + 0.5) * SPEED_COUNT;
float Cell = floor(Ang);
float Rnd = frac(sin(Cell * 12.9898 + SpeedSeed * 78.233) * 43758.5453);
float Streak = step(frac(Ang), 0.12 + 0.30 * Rnd) * step(0.45, Rnd);
float Reach = smoothstep(SPEED_INNER + 0.25 * Rnd * SPEED_INNER, SPEED_OUTER, Rad);
float3 LineC = Rnd > 1.0 - SPEED_RED ? BLOOD_D : INK_D;
Out = lerp(Out, LineC, Streak * Reach * Speed * SPEED_A * (Fighter ? SPEED_ON_FIGHTER : 1.0));
return Out;
""")


def hlsl_fire():
    """Step 8 of M_Anime_Frame: the flame and the burst, in display values,
    before the impact frame's cut. Inputs: the FIRE_PARAMS, plus D (scene
    depth), VUV and Aspect already in scope. The browser's shapes with the
    browser's numbers (FIRE), in figure pixels about the fist or the man
    hit, scaled by the game's FireScale / BurnScale; the tongues' edges
    are the browser's two quadratic curves sampled along the tongue."""
    F = FIRE
    L = LOOK
    tc = F["TONGUE_COL"]; gc = F["GLOW_COL"]; sc = F["SPARK_COL"]
    d = {
        "ROOT": _f(F["TONGUE_ROOT_PX"]),
        "TW": ", ".join(_f(w) for w in F["TONGUE_W"]),
        "TL": ", ".join(_f(l) for l in F["TONGUE_LEN"]),
        "TC": ", ".join(_f3(_rgb(c)) for c in tc),
        "TA": ", ".join(_f(c[3]) for c in tc),
        "SWAY_RATE": _f(F["SWAY_RATE"]), "SWAY_PHASE": _f(F["SWAY_PHASE"]), "SWAY_PX": _f(F["SWAY_PX"]),
        "GLOW_CX": _f(F["GLOW_CX"]), "GLOW_R": _f(F["GLOW_R"]), "GLOW_MID": _f(F["GLOW_MID"]),
        "GC0": _f3(_rgb(gc[0])), "GC1": _f3(_rgb(gc[1])), "GC2": _f3(_rgb(gc[2])),
        "GA0": _f(gc[0][3]), "GA1": _f(gc[1][3]),
        "RING_FROM": _f(F["RING_FROM"]), "RING_TO": _f(F["RING_TO"]), "RING_S": _f(F["RING_S"]),
        "RING_A": _f(F["RING_A"]), "RING_W": _f(F["RING_W"]), "RING_SQUASH": _f(F["RING_SQUASH"]),
        "RING_C": _f3(_rgb(F["RING_COL"])),
        "SPARKS": str(F["SPARKS_HOT"] + F["SPARKS_PALE"]), "SPARKS_HOT": str(F["SPARKS_HOT"]),
        "SPD_HOT": _f(F["SPARK_SPD"][0]), "SPD_PALE": _f(F["SPARK_SPD"][1]), "SHARE_MIN": _f(F["SPARK_SHARE_MIN"]),
        "LIFT": _f(F["SPARK_LIFT"]), "GRAV": _f(F["SPARK_G"]), "DRAG": _f(F["SPARK_DRAG"]),
        "LIFE_MIN": _f(F["SPARK_LIFE"][0]), "LIFE_MAX": _f(F["SPARK_LIFE"][1]),
        "R_MIN": _f(F["SPARK_R"][0]), "R_MAX": _f(F["SPARK_R"][1]),
        "SC_HOT": _f3(_rgb(sc[0])), "SC_PALE": _f3(_rgb(sc[1])), "SA": _f(sc[0][3]),
        "FIRE_BEHIND": _f(L["FIRE_BEHIND_CM"]), "BURST_BEHIND": _f(L["BURST_BEHIND_CM"]),
        "FIRE_INK": _f(L["FIRE_INK_PX"]), "GLOW_STEPS": _f(L["GLOW_STEPS"]), "INK_D": _f3(display(L["INK"])),
    }
    return r"""
// 8. HAWK FIST (Combat/SaudFire.h): the flame on Saud's fist, and the
//    burst on the man his burning punch hit -- the browser's handFlame()
//    and applyHit(), in its figure pixels about the fist, scaled to the
//    fist's own distance; the glow banded, an ink line round the flame,
//    and the flame drawn behind the hand so the knuckles stay legible.
const float2 Dir8[8] = { float2(1,0), float2(-1,0), float2(0,1), float2(0,-1),
                         float2(0.7071,0.7071), float2(-0.7071,0.7071),
                         float2(0.7071,-0.7071), float2(-0.7071,-0.7071) };
if (FireHeat > 0.0)
{
    float2 Fd = float2(FireDirX, FireDirY);
    float2 Fv = (VUV - float2(FireX, FireY)) * float2(Aspect, 1.0);
    float2 P = float2(dot(Fv, Fd), dot(Fv, float2(-Fd.y, Fd.x))) / max(FireScale, 1e-6);   // figure px: along, across
    float Behind = D > FireDepth + %(FIRE_BEHIND)s ? 1.0 : 0.0;
    // the glow: the browser's gradient, its stops kept, cut into rings
    float G = length(P - float2(%(GLOW_CX)s, 0.0)) / (%(GLOW_R)s * FireHeat);
    G = (floor(G * %(GLOW_STEPS)s) + 0.5) / %(GLOW_STEPS)s;
    float Ga = G < %(GLOW_MID)s ? lerp(%(GA0)s, %(GA1)s, G / %(GLOW_MID)s)
                                : lerp(%(GA1)s, 0.0, saturate((G - %(GLOW_MID)s) / (1.0 - %(GLOW_MID)s)));
    float3 Gc = G < %(GLOW_MID)s ? lerp(%(GC0)s, %(GC1)s, G / %(GLOW_MID)s)
                                 : lerp(%(GC1)s, %(GC2)s, saturate((G - %(GLOW_MID)s) / (1.0 - %(GLOW_MID)s)));
    Out = lerp(Out, Gc, (G < 1.0 ? Ga : 0.0) * Behind);
    // three tongues, widest first and the pale core last, tested here and
    // at eight neighbours the ink line's width away: a pixel outside every
    // tongue with one beside it is the line
    const float TW[3] = { %(TW)s };
    const float TL[3] = { %(TL)s };
    const float3 TC[3] = { %(TC)s };
    const float TA[3] = { %(TA)s };
    float Rf = %(FIRE_INK)s / 1080.0 / max(FireScale, 1e-6);
    float3 Fc = Out;
    float Inside = 0.0, Beside = 0.0;
    for (int k = 0; k < 9; k++)
    {
        float2 Pk = k == 0 ? P : P + Dir8[k - 1] * Rf;
        for (int i = 0; i < 3; i++)
        {
            float Len = TL[i] * FireHeat;
            float Sw = sin(FireTime * %(SWAY_RATE)s + i * %(SWAY_PHASE)s) * %(SWAY_PX)s;
            float u = (Pk.x + %(ROOT)s) / (Len + %(ROOT)s);
            float Top = (1.0 - u) * (1.0 - u) * -TW[i] + 2.0 * u * (1.0 - u) * (-0.8 * TW[i] + Sw) + u * u * 0.5 * Sw;
            float Bot = (1.0 - u) * (1.0 - u) * TW[i] + 2.0 * u * (1.0 - u) * (0.8 * TW[i] + Sw) + u * u * 0.5 * Sw;
            bool In = u >= 0.0 && u <= 1.0 && Pk.y >= Top && Pk.y <= Bot;
            if (k == 0 && In) { Fc = lerp(Fc, TC[i], TA[i]); Inside = 1.0; }
            if (k > 0 && In) { Beside = 1.0; }
        }
    }
    Out = lerp(Out, Fc, Behind);
    Out = lerp(Out, %(INK_D)s, Beside * (1.0 - Inside) * Behind);
}
if (BurnAge >= 0.0)
{
    float2 Bv = (VUV - float2(BurnX, BurnY)) * float2(Aspect, 1.0) / max(BurnScale, 1e-6);   // figure px, y down
    float Bb = D > BurnDepth - %(BURST_BEHIND)s ? 1.0 : 0.0;
    // the ring: an ellipse squashed to the browser's, its stroke thinning
    float k = BurnAge / %(RING_S)s;
    if (k < 1.0)
    {
        float Rr = lerp(%(RING_FROM)s, %(RING_TO)s, k);
        float E = length(Bv * float2(1.0, 1.0 / %(RING_SQUASH)s));
        float Wd = %(RING_W)s * (1.0 - k) + 1.0;
        Out = lerp(Out, %(RING_C)s, (abs(E - Rr) <= 0.5 * Wd ? 1.0 : 0.0) * (1.0 - k) * %(RING_A)s * Bb);
    }
    // the sparks: hot ones then pale, each thrown its own way by the seed,
    // lifted, dragged and falling as the browser's are, fading with life
    for (int i = 0; i < %(SPARKS)s; i++)
    {
        bool Pale = i >= %(SPARKS_HOT)s;
        float H1 = frac(sin(i * 12.9898 + BurnSeed * 78.233 + 1.0 * 37.719) * 43758.5453);
        float H2 = frac(sin(i * 12.9898 + BurnSeed * 78.233 + 2.0 * 37.719) * 43758.5453);
        float H3 = frac(sin(i * 12.9898 + BurnSeed * 78.233 + 3.0 * 37.719) * 43758.5453);
        float H4 = frac(sin(i * 12.9898 + BurnSeed * 78.233 + 4.0 * 37.719) * 43758.5453);
        float A = 6.2831853 * H1;
        float Sp = (Pale ? %(SPD_PALE)s : %(SPD_HOT)s) * lerp(%(SHARE_MIN)s, 1.0, H2);
        float Life = lerp(%(LIFE_MIN)s, %(LIFE_MAX)s, H3);
        float Rad = lerp(%(R_MIN)s, %(R_MAX)s, H4);
        if (BurnAge < Life)
        {
            float2 At = float2(cos(A) * Sp * (1.0 - exp(-%(DRAG)s * BurnAge)) / %(DRAG)s,
                               (sin(A) * Sp - %(LIFT)s) * BurnAge + 0.5 * %(GRAV)s * BurnAge * BurnAge);
            float Hit = length(Bv - At) <= Rad ? 1.0 : 0.0;
            Out = lerp(Out, Pale ? %(SC_PALE)s : %(SC_HOT)s, Hit * saturate((Life - BurnAge) / %(LIFE_MAX)s) * %(SA)s * Bb);
        }
    }
}
""" % d


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
    out = out * lerp(np.array(L["LIT_TINT"]), np.array(L["SHADOW_TINT"]), shad[..., None])
    emit = _smooth(L["EMIT_FROM"], 2.0 * L["EMIT_FROM"], T)
    out = lerp(out, C, emit[..., None])

    # 2. hatching, in pixels of a 1080-line picture (pixel centres, as UV)
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    sx, sy = (xx + 0.5) / lines, (yy + 0.5) / lines
    h1 = (fr((sx + sy) / L["HATCH_PX"]) <= L["HATCH_WIDTH"]).astype(float)
    h2 = (fr((sx - sy) / L["HATCH_PX"]) <= L["HATCH_WIDTH"]).astype(float)
    cross = 1.0 - _smooth(L["CROSS_BELOW"] - s, L["CROSS_BELOW"] + s, T)
    hatch = np.clip(h1 + h2 * cross, 0, 1) * deep * L["HATCH_ALPHA"] * (~sky)
    ink = np.array(L["INK"])
    out = lerp(out, ink, hatch[..., None])

    # 3. ink, eight neighbours at the line's half width, each ring tested
    # half a pixel either side of its radius and the two averaged (the edge
    # of the line antialiased). `fighter` is what writes custom depth: a
    # pixel of him, or one behind him, is where the fighter's own lines go.
    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1),
            (.7071, .7071), (-.7071, .7071), (.7071, -.7071), (-.7071, -.7071))
    silh = np.zeros((H, W)); outer = np.zeros((H, W)); folds = np.zeros((H, W))
    Ro = L["LINE_FIGHTER_PX"] * L["OUTER_SHARE"] * lines
    edge_f, aa = L["FIGHTER_EDGE_CM"], L["LINE_AA_PX"]
    for R, mask in ((L["LINE_FIGHTER_PX"] * (1.0 - L["OUTER_SHARE"]) * lines, fighter),
                    (L["LINE_WORLD_PX"] * 0.5 * lines, ~fighter)):
        for k in (0, 1):
            Rk = max(R + (-0.5 if k == 0 else 0.5) * aa, 0.0)
            Rok = max(Ro + (-0.5 if k == 0 else 0.5) * aa, 0.0)
            S = np.zeros((H, W)); O = np.zeros((H, W))
            for dx, dy in dirs:
                Dn = _shift(D, dx * Rk, dy * Rk, 1e10)
                Do = _shift(D, -dx * Rk, -dy * Rk, 1e10)
                Fn = _shift(fighter, dx * Rk, dy * Rk, False)
                jump = (Dn - D) / np.maximum(D, 1.0) >= L["DEPTH_EDGE"]
                brk = fighter & (Dn - D >= 0.5 * edge_f) & (Dn + Do - 2.0 * D >= edge_f)
                leave = fighter & ~Fn & (Dn > D)
                S = np.maximum(S, (jump | brk | leave).astype(float))
                Dno = _shift(D, dx * Rok, dy * Rok, 1e10)
                Fo = _shift(fighter, dx * Rok, dy * Rok, False)
                O = np.maximum(O, (~fighter & Fo & (Dno < D) & (Ro > 0)).astype(float))
                if k == 1:
                    Nn = _shift(N, dx * Rk, dy * Rk, 0.0)
                    same = np.abs(Dn - D) < np.where(fighter, edge_f, L["DEPTH_EDGE"] * np.maximum(D, 1.0))
                    f = ((1.0 - np.sum(N * Nn, axis=2)) >= L["NORMAL_EDGE"]) & (Dn < L["SKY_DEPTH_CM"]) & same
                    folds = np.where(mask, folds + f, folds)
            silh = np.where(mask, silh + 0.5 * S, silh)
            outer = np.where(mask, outer + 0.5 * O, outer)
    fold = ((folds >= L["FOLD_MIN"]) & (folds <= L["FOLD_MAX"])).astype(float)
    fade = np.where(fighter, 1.0, lerp(1.0, L["FADE_MIN"],
                    np.clip((D - L["FADE_NEAR_CM"]) / (L["FADE_FAR_CM"] - L["FADE_NEAR_CM"]), 0, 1)))
    inkw = np.maximum(np.maximum(silh, fold * L["INNER_ALPHA"]) * fade, outer) * (~sky | (outer > 0))
    out = lerp(out, ink, inkw[..., None])

    # 4. sky: banded, and a dim cold overcast
    Ls = C @ luma
    Lb = (np.floor(Ls * L["SKY_BANDS"]) + 0.5) / L["SKY_BANDS"]
    skyc = C * (Lb / np.maximum(Ls, 1e-4))[..., None] * L["SKY_LEVEL"] * np.array(L["SKY_TINT"])
    out = np.where(sky[..., None], lerp(skyc, ink, outer[..., None]), out)

    # 5. grade: the world held down (not a lamp), the air over it, then
    # colour held under except the accents, the world greyer than a man
    world = ~fighter & ~sky
    out = out * np.where(world, lerp(L["WORLD_LEVEL"], 1.0, emit), 1.0)[..., None]
    air = np.where(world, L["HAZE_MAX"] * _smooth(L["HAZE_NEAR_CM"], L["HAZE_FAR_CM"], D), 0.0)
    out = lerp(out, np.array(L["HAZE"]) * key, air[..., None])
    red = (out[..., 0] - np.maximum(out[..., 1], out[..., 2])) / np.maximum(out[..., 0], 1e-4)
    accent = np.maximum(_smooth(L["ACCENT_FROM"], L["ACCENT_FULL"], red), np.where(sky, 0.0, emit))
    sat = lerp(np.where(fighter, L["SATURATION"], L["WORLD_SATURATION"]), L["ACCENT_SAT"], accent)
    out = lerp((out @ luma)[..., None], out, sat[..., None])

    # 7a. the impact frame, drawn: the lit side ember, the rest ink
    if impact > 0.0:
        paper = np.where(sky, 1.0, (1.0 - shad) * (1.0 - inkw))
        paper = lerp(paper, 1.0 - paper, invert)
        out = lerp(out, lerp(ink, np.array(L["EMBER"]), paper[..., None]), impact)
    return out, {"T": T, "deep": deep, "shadow": shad, "ink": inkw, "hatch": hatch}


def fire(out, D, fire=None, burn=None):
    """Step 8 on a display-valued picture `out` (H,W,3), with the scene
    depth D (H,W, cm). `fire` is the fist: heat, x, y (viewport, y down),
    dir (unit, aspect applied), depth (cm), scale (a figure px as a share
    of the height), time (s). `burn` is the man hit: age (s), x, y, depth,
    scale, seed. Either None draws nothing. The same arithmetic as
    hlsl_fire(), line for line."""
    import numpy as np
    L, F = LOOK, FIRE
    H, W = out.shape[:2]
    lerp = lambda a, b, t: a + (b - a) * t
    fr = lambda v: v - np.floor(v)
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    vuv = np.stack([(xx + 0.5) / W, (yy + 0.5) / H], axis=-1)
    aspect = W / H
    ink = np.array(display(L["INK"]))
    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1),
            (.7071, .7071), (-.7071, .7071), (.7071, -.7071), (-.7071, -.7071))
    if fire is not None and fire["heat"] > 0.0:
        heat = fire["heat"]
        fd = np.array(fire["dir"], float); fd /= np.linalg.norm(fd)
        fv = (vuv - np.array([fire["x"], fire["y"]])) * np.array([aspect, 1.0])
        P = np.stack([fv @ fd, fv @ np.array([-fd[1], fd[0]])], axis=-1) / max(fire["scale"], 1e-6)
        behind = (D > fire["depth"] + L["FIRE_BEHIND_CM"]).astype(float)
        gc = [np.array(_rgb(c)) for c in F["GLOW_COL"]]
        ga0, ga1, mid, steps = F["GLOW_COL"][0][3], F["GLOW_COL"][1][3], F["GLOW_MID"], L["GLOW_STEPS"]
        G = np.hypot(P[..., 0] - F["GLOW_CX"], P[..., 1]) / (F["GLOW_R"] * heat)
        G = (np.floor(G * steps) + 0.5) / steps
        lo = G < mid
        t1 = np.clip(G / mid, 0, 1); t2 = np.clip((G - mid) / (1.0 - mid), 0, 1)
        Ga = np.where(lo, lerp(ga0, ga1, t1), lerp(ga1, 0.0, t2))
        Gc = np.where(lo[..., None], lerp(gc[0], gc[1], t1[..., None]), lerp(gc[1], gc[2], t2[..., None]))
        out = lerp(out, Gc, (np.where(G < 1.0, Ga, 0.0) * behind)[..., None])
        Rf = L["FIRE_INK_PX"] / 1080.0 / max(fire["scale"], 1e-6)
        fc = out.copy()
        inside = np.zeros((H, W), bool); beside = np.zeros((H, W), bool)
        for k in range(9):
            Pk = P if k == 0 else P + np.array(dirs[k - 1]) * Rf
            for i in range(3):
                w, ln = F["TONGUE_W"][i], F["TONGUE_LEN"][i] * heat
                sw = math.sin(fire["time"] * F["SWAY_RATE"] + i * F["SWAY_PHASE"]) * F["SWAY_PX"]
                root = F["TONGUE_ROOT_PX"]
                u = (Pk[..., 0] + root) / (ln + root)
                top = (1 - u) ** 2 * -w + 2 * u * (1 - u) * (-0.8 * w + sw) + u * u * 0.5 * sw
                bot = (1 - u) ** 2 * w + 2 * u * (1 - u) * (0.8 * w + sw) + u * u * 0.5 * sw
                In = (u >= 0) & (u <= 1) & (Pk[..., 1] >= top) & (Pk[..., 1] <= bot)
                if k == 0:
                    c = F["TONGUE_COL"][i]
                    fc = np.where(In[..., None], lerp(fc, np.array(_rgb(c)), c[3]), fc)
                    inside |= In
                else:
                    beside |= In
        out = lerp(out, fc, behind[..., None])
        out = lerp(out, ink, (beside & ~inside)[..., None] * behind[..., None])
    if burn is not None and burn["age"] >= 0.0:
        age = burn["age"]
        bv = (vuv - np.array([burn["x"], burn["y"]])) * np.array([aspect, 1.0]) / max(burn["scale"], 1e-6)
        bb = (D > burn["depth"] - L["BURST_BEHIND_CM"]).astype(float)
        k = age / F["RING_S"]
        if k < 1.0:
            rr = lerp(F["RING_FROM"], F["RING_TO"], k)
            E = np.hypot(bv[..., 0], bv[..., 1] / F["RING_SQUASH"])
            wd = F["RING_W"] * (1.0 - k) + 1.0
            a = (np.abs(E - rr) <= 0.5 * wd) * (1.0 - k) * F["RING_A"] * bb
            out = lerp(out, np.array(_rgb(F["RING_COL"])), a[..., None])
        n_hot, n_all = F["SPARKS_HOT"], F["SPARKS_HOT"] + F["SPARKS_PALE"]
        for i in range(n_all):
            pale = i >= n_hot
            h = [fr(math.sin(i * 12.9898 + burn["seed"] * 78.233 + kk * 37.719) * 43758.5453) for kk in (1, 2, 3, 4)]
            A = 2 * math.pi * h[0]
            sp = F["SPARK_SPD"][1 if pale else 0] * lerp(F["SPARK_SHARE_MIN"], 1.0, h[1])
            life = lerp(F["SPARK_LIFE"][0], F["SPARK_LIFE"][1], h[2])
            rad = lerp(F["SPARK_R"][0], F["SPARK_R"][1], h[3])
            if age < life:
                drag = F["SPARK_DRAG"]
                at = (math.cos(A) * sp * (1.0 - math.exp(-drag * age)) / drag,
                      (math.sin(A) * sp - F["SPARK_LIFT"]) * age + 0.5 * F["SPARK_G"] * age * age)
                hit = np.hypot(bv[..., 0] - at[0], bv[..., 1] - at[1]) <= rad
                c = F["SPARK_COL"][1 if pale else 0]
                a = hit * min(1.0, (life - age) / F["SPARK_LIFE"][1]) * c[3] * bb
                out = lerp(out, np.array(_rgb(c)), a[..., None])
    return out


def frame(S, fighter, impact=0.0, speed=0.0, centre=(0.5, 0.5), seed=0.0, D=None, fist=None, burn=None):
    """M_Anime_Frame's steps on a display-valued picture S (H,W,3, 0..1):
    the fire (needs D, the depth), the impact frame's cut, the speed lines."""
    import numpy as np
    L = LOOK
    H, W = S.shape[:2]
    luma = np.array(LUMA)
    lerp = lambda a, b, t: a + (b - a) * t
    fr = lambda v: v - np.floor(v)
    # the vignette, first: the corners into the dark
    yv, xv = np.mgrid[0:H, 0:W].astype(float)
    asp = W / H
    vr = np.hypot(((xv + 0.5) / W - 0.5) * asp, (yv + 0.5) / H - 0.5) / (0.5 * math.sqrt(asp * asp + 1.0))
    out = S * (1.0 - L["VIGNETTE"] * _smooth(L["VIGNETTE_FROM"], L["VIGNETTE_TO"], vr))[..., None]
    if (fist is not None or burn is not None) and D is not None:
        out = fire(out, D, fist, burn)
    if impact >= 0.5:
        cut = (out @ luma > L["IMPACT_CUT"])[..., None]
        out = np.where(cut, np.array(display(L["EMBER"])), np.array(display(L["INK"])))
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
        line = np.where((rnd > 1.0 - L["SPEED_RED"])[..., None], np.array(display(L["BLOOD"])),
                        np.array(display(L["INK"])))
        out = lerp(out, line, a[..., None])
    return out


def to_display(lin):
    """Linear to display values with a plain clip -- the preview's
    stand-in for the engine's tonemapper. The look's tones are flat by
    construction, so there is little highlight roll-off to lose."""
    import numpy as np
    c = np.clip(lin, 0.0, 1.0)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def look(C, A, N, D, fighter, key=None, impact=0.0, invert=0.0, speed=0.0,
         centre=(0.5, 0.5), seed=0.0, fist=None, burn=None):
    """Both materials, in the engine's order: M_Anime_Post, the
    tonemapper's stand-in, M_Anime_Frame. Returns display values (0..1)
    and M_Anime_Post's masks. `fist` and `burn` are HAWK FIST's (fire())."""
    out, m = preview(C, A, N, D, fighter, key=key, impact=impact, invert=invert)
    return frame(to_display(out), fighter, impact=impact, speed=speed, centre=centre, seed=seed,
                 D=D, fist=fist, burn=burn), m


def to_8bit(disp):
    import numpy as np
    return (np.clip(disp, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


# -------------------------------------------------------------------- check
def _patches(n=240):
    """Three flat swatches square to the light, all fighter, near: Kuwait's
    red (#c8102e), a rust tee (#8c4a34) and a grey -- what the grade does to
    an accent and to a colour that is not one."""
    import numpy as np
    hexes = ("c8102e", "8c4a34", "8a9099")
    lin = lambda h: np.array([(lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)(
        int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4)])
    A = np.zeros((n, 3 * n, 3))
    for i, h in enumerate(hexes):
        A[:, i * n:(i + 1) * n] = lin(h)
    N = np.zeros_like(A); N[..., 2] = 1.0
    C = A * 1.2
    D = np.full((n, 3 * n), 300.0)
    return C, A, N, D, np.ones((n, 3 * n), bool)


def _sphere(n=720, front=False, noise=False, far=False):
    """A lit sphere in front of a far wall and a sky: the look's every step
    has somewhere to show. Key light from the upper left. `front` puts a
    small ball 10 cm in front of it (a fist over a chest: 4 % of the
    distance, under the world's 7 %); `noise` scatters one-pixel noise
    through the normals over a patch of it, as pores in a normal map do."""
    import numpy as np
    yy, xx = np.mgrid[0:n, 0:n].astype(float)
    u, v = (xx + 0.5) / n * 2 - 1, (yy + 0.5) / n * 2 - 1
    r2 = u * u + v * v
    on = r2 < 0.6 ** 2
    z = np.sqrt(np.clip(0.36 - r2, 0, None))
    N = np.zeros((n, n, 3)); N[..., 0] = u / 0.6; N[..., 1] = -v / 0.6; N[..., 2] = z / 0.6
    N[~on] = (0, 0, 1)
    D = np.where(on, 300.0 - z * 100.0, 25000.0 if far else 900.0)
    if front:
        cu, cv, rb = 0.20, 0.25, 0.15
        r2b = (u - cu) ** 2 + (v - cv) ** 2
        ball = r2b < rb ** 2
        zb = np.sqrt(np.clip(rb * rb - r2b, 0, None))
        N[ball, 0] = ((u - cu) / rb)[ball]; N[ball, 1] = (-(v - cv) / rb)[ball]; N[ball, 2] = (zb / rb)[ball]
        D = np.where(ball, 300.0 - 0.507 * 100.0 - 10.0 - zb * 30.0, D)
    if noise:
        rng = np.random.default_rng(7)
        patch = on & (np.abs(u + 0.12) < 0.15) & (np.abs(v - 0.10) < 0.15)
        spot = patch & (rng.random((n, n)) < 0.02)
        N[spot] = N[spot] + rng.normal(0.0, 0.9, (int(spot.sum()), 3))
        N[spot] /= np.linalg.norm(N[spot], axis=1)[:, None]
    light = np.array([-0.5, 0.6, 0.62]); light /= np.linalg.norm(light)
    ndl = np.clip(N @ light, 0, None)
    A = np.where(on[..., None], np.array([0.45, 0.28, 0.20]), np.array([0.30, 0.30, 0.30]))
    C = A * (ndl * 1.0 + 0.04)[..., None]
    D[: n // 5] = np.where(on[: n // 5], D[: n // 5], 1e10)  # a strip of sky
    C[: n // 5][~on[: n // 5]] = (0.35, 0.45, 0.65)
    A[: n // 5][~on[: n // 5]] = 0.0
    return C, A, N, D, on


def check(bite=None):
    """What the look promises, on the sphere. `bite` breaks one thing to
    prove the check that guards it fails."""
    import numpy as np
    global LOOK, FIRE
    saved = dict(LOOK)
    saved_fire = dict(FIRE)
    lerp = lambda a, b, t: a + (b - a) * t
    try:
        if bite == "no_terminator":
            LOOK["Q_SHADOW"] = LOOK["Q_LIT"]; LOOK["Q_DEEP"] = LOOK["Q_LIT"]
        if bite == "no_ink":
            LOOK["LINE_FIGHTER_PX"] = 0.0; LOOK["LINE_WORLD_PX"] = 0.0; LOOK["NORMAL_EDGE"] = 99.0
        if bite == "grey_ink":
            LOOK["INK"] = (0.030, 0.026, 0.024)
        if bite == "inner_only":
            LOOK["OUTER_SHARE"] = 0.0
        if bite == "limb_gap":
            LOOK["FIGHTER_EDGE_CM"] = 1e9
        if bite == "specks":
            LOOK["FOLD_MIN"] = 1; LOOK["FOLD_MAX"] = 8
        if bite == "stepped":
            LOOK["LINE_AA_PX"] = 0.0
        if bite == "one_tint":
            LOOK["SHADOW_TINT"] = LOOK["LIT_TINT"]
        if bite == "accent_muted":
            LOOK["ACCENT_FROM"] = 1.5; LOOK["ACCENT_FULL"] = 2.0
        if bite == "no_air":
            LOOK["HAZE_MAX"] = 0.0
        if bite == "ink_lines":
            LOOK["SPEED_RED"] = 0.0
        if bite == "sky_shaded":
            LOOK["SKY_DEPTH_CM"] = 1e12
        if bite == "lines_over_men":
            LOOK["SPEED_ON_FIGHTER"] = 1.0
        if bite == "flat_impact":
            LOOK["EMBER"] = LOOK["INK"]
        if bite == "paper_impact":
            LOOK["EMBER"] = (0.93, 0.88, 0.78)
        if bite == "grey_shadows":
            LOOK["Q_SHADOW"] = 0.38; LOOK["Q_DEEP"] = 0.13
        if bite == "world_as_fighter":
            LOOK["WORLD_LEVEL"] = 1.0; LOOK["WORLD_SATURATION"] = LOOK["SATURATION"]
        if bite == "bright_sky":
            LOOK["SKY_LEVEL"] = 1.0
        if bite == "no_vignette":
            LOOK["VIGNETTE"] = 0.0
        if bite == "warm_fog":
            LOOK["HAZE"] = (0.58, 0.47, 0.38)
        if bite == "no_cut":
            LOOK["IMPACT_CUT"] = -1.0
        if bite == "fire_on_hand":
            LOOK["FIRE_BEHIND_CM"] = -1e9
        if bite == "soft_glow":
            LOOK["GLOW_STEPS"] = 64
        if bite == "no_fire_ink":
            LOOK["FIRE_INK_PX"] = 0.0
        if bite == "burst_through_men":
            LOOK["BURST_BEHIND_CM"] = 1e9
        if bite == "still_sparks":
            FIRE["SPARK_SPD"] = (0.0, 0.0); FIRE["SPARK_G"] = 0.0; FIRE["SPARK_LIFT"] = 0.0
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
        # 1a. the dark (2026-09-26): the shadow side is near black, a
        #     quarter of the lit side or less, not a grey
        assert np.median(rel[sh]) < 0.30 and np.median(rel[sh]) < 0.30 * np.median(rel[lit]), \
            "the shadows are dark, not grey"
        # 1b. split toning: the shadow side is cooler than the lit side, in
        #     hue and not only in value
        br = lambda px: np.median(out[px][:, 2] / np.maximum(out[px][:, 0], 1e-6))
        assert br(sh) > 1.15 * br(lit), "the shadows lean cool against a warm light"
        # 5. the grade holds colour under, except the red accent
        Cp, Ap, Np, Dp, onp = _patches()
        op, _mp = preview(Cp, Ap, Np, Dp, onp)
        sat = lambda c: (c.max(axis=-1) - c.min(axis=-1)) / np.maximum(c.max(axis=-1), 1e-6)
        w = Dp.shape[1] // 3
        keep = [np.median(sat(op[:, i * w:(i + 1) * w]) / np.maximum(sat(Ap[:, i * w:(i + 1) * w]), 1e-6))
                for i in range(3)]
        assert keep[0] > keep[1] + 0.05, "Kuwait's red keeps its colour where a rust tee is held under"
        # 5c. the world is held darker and greyer than a fighter of the
        #     same colour under the same light: the men stand out of the murk
        ow, _mw = preview(Cp, Ap, Np, Dp, ~onp)
        lum = lambda c: c @ np.array(LUMA)
        rust = slice(w, 2 * w)
        assert np.median(lum(ow[:, rust])) < 0.8 * np.median(lum(op[:, rust])), "the world is darker than the men"
        assert np.median(sat(ow[:, rust])) < 0.9 * np.median(sat(op[:, rust])), "and greyer"
        # 5a. the sky is held under like everything else: it has no base
        #     colour, so it reads as a lamp, and a lamp keeps its colour --
        #     the first version of the accent lifted the whole sky to full
        #     saturation, loud orange over the souq
        skyp = D > LOOK["SKY_DEPTH_CM"]
        assert np.median(sat(out[skyp])) <= np.median(sat(C[skyp])) + 1e-6, "the sky is not an accent"
        # 4b. the sky is a dim overcast: well under half its own light
        assert np.median(out[skyp] @ np.array(LUMA)) < 0.45 * np.median(C[skyp] @ np.array(LUMA)), \
            "the sky is a dim overcast"
        # 5b. air: the far world recedes toward the dusk, a fighter does not
        Cf, Af, Nf, Df, onf = _sphere(far=True)
        of, _mf = preview(Cf, Af, Nf, Df, onf)
        wall = ~on & (D < LOOK["SKY_DEPTH_CM"])
        wall = wall & ~_shift(on, 8, 0, False) & ~_shift(on, -8, 0, False)
        # (measured as how near the wall comes to the fog's own colour: a
        # dark wall in a dark fog changes little in brightness, and that
        # is the point of it)
        fogc = np.array(LOOK["HAZE"])
        near_d = np.abs(out[wall] - fogc).sum(axis=1).mean()
        far_d = np.abs(of[wall] - fogc).sum(axis=1).mean()
        assert far_d < 0.6 * near_d, "the far world is in the air"
        assert np.abs(of[on] - out[on]).max() < 1e-9, "and a fighter is not"
        # ... and the air is a dark cold fog, not a warm dusk
        hz = np.array(LOOK["HAZE"])
        assert hz @ np.array(LUMA) < 0.2 and hz[2] >= hz[0], "the fog is dark and cold"
        # 3. a silhouette line all round the sphere's edge
        ring = on & (~_shift(on, 1, 0, False) | ~_shift(on, -1, 0, False)
                     | ~_shift(on, 0, 1, False) | ~_shift(on, 0, -1, False))
        assert m["ink"][ring].mean() > 0.6, "the sphere is outlined"
        assert m["ink"][on & ~ring].mean() < 0.05, "no ink inside a smooth sphere"
        # ... and the line is centred on the edge: as much of it outside
        outside = ~on & (_shift(on, 1, 0, False) | _shift(on, -1, 0, False)
                         | _shift(on, 0, 1, False) | _shift(on, 0, -1, False))
        assert m["ink"][outside].mean() > 0.6, "the outline lies on both sides of the edge"
        # ... darker than a black tee lit full (#15171c), or it reads as a halo
        tee = np.array([0.0075, 0.0080, 0.0110]) @ luma
        assert np.array(LOOK["INK"]) @ luma < 0.5 * tee * LOOK["Q_LIT"], "the ink is darker than black kit"
        # ... with a soft edge, not a staircase
        soft = (m["ink"] > 0.2) & (m["ink"] < 0.8)
        assert soft[ring | outside | on].sum() > 0.2 * ring.sum(), "the line's edge is antialiased"
        # a limb over the body is outlined where it crosses, though the
        # depth there jumps 4 % of the distance, under DEPTH_EDGE
        C2, A2, N2, D2, on2 = _sphere(front=True)
        _o2, m2 = preview(C2, A2, N2, D2, on2)
        n = D2.shape[0]
        yy2, xx2 = np.mgrid[0:n, 0:n]
        ball = ((xx2 + 0.5) / n * 2 - 1 - 0.20) ** 2 + ((yy2 + 0.5) / n * 2 - 1 - 0.25) ** 2 < 0.15 ** 2
        rim = ball & ~(_shift(ball, 1, 0, False) & _shift(ball, -1, 0, False)
                       & _shift(ball, 0, 1, False) & _shift(ball, 0, -1, False))
        # at full weight, as a silhouette -- a fold's lighter line alone is
        # what it had before (and a limb read as the body's crease)
        assert (m2["ink"][rim] >= 0.99).mean() > 0.6, "a limb over the body is outlined"
        # noise in the normals does not speckle the skin with ink
        C3, A3, N3, D3, on3 = _sphere(noise=True)
        _o3, m3 = preview(C3, A3, N3, D3, on3)
        n = D3.shape[0]
        yy3, xx3 = np.mgrid[0:n, 0:n]
        u3, v3 = (xx3 + 0.5) / n * 2 - 1, (yy3 + 0.5) / n * 2 - 1
        patch = on3 & (np.abs(u3 + 0.12) < 0.13) & (np.abs(v3 - 0.10) < 0.13)
        assert m3["ink"][patch].mean() < 0.02, "no ink specks from noisy normals"
        # 4. the sky is banded, not shaded: few distinct levels
        sky = D > LOOK["SKY_DEPTH_CM"]
        assert sky.sum() > 1000, "the sky is recognised"
        assert len(np.unique(np.round(out[sky] @ luma, 5))) <= LOOK["SKY_BANDS"] + 1, "the sky is banded"
        # 7. the impact frame is exactly two colours after the cut, and flips
        f0, _ = look(C, A, N, D, on, impact=1.0)
        f1, _ = look(C, A, N, D, on, impact=1.0, invert=1.0)
        colours = np.unique(np.round(f0.reshape(-1, 3), 4), axis=0)
        assert len(colours) == 2, "the impact frame is exactly ink and ember"
        l0, l1 = f0 @ luma, f1 @ luma
        assert np.ptp(l0) > 0.5, "the impact frame is ink and ember"
        em = np.array(LOOK["EMBER"])
        assert em[0] > 2.0 * em[1] and em[1] > em[2], "its light half is an ember, not paper"
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
        reds = diff & (sp[..., 0] > sp[..., 1] + 0.15)
        assert 0.15 < reds.sum() / max(diff.sum(), 1) < 0.7, "a good share of the streaks are blood, the rest ink"
        # the vignette: the corners into the dark, the middle untouched
        plain = to_display(out)
        n = D.shape[0]
        c = 12
        assert np.abs(base[n // 2, n // 2] - plain[n // 2, n // 2]).max() < 1e-9, "the vignette leaves the middle"
        corner = (base[:c, :c] @ luma).mean() / max((plain[:c, :c] @ luma).mean(), 1e-6)
        assert corner < 0.65, "the vignette takes the corners into the dark (%.2f)" % corner
        # 8. HAWK FIST. The flame on the small ball in front of the sphere
        #    (a fist over a chest, 6 figure px across at this scale),
        #    pointing right: it is drawn on what is behind the fist -- the
        #    chest, the wall -- and never on the fist.
        base2, _ = look(C2, A2, N2, D2, on2)
        n = D2.shape[0]
        fx, fy = (0.20 + 1) / 2, (0.25 + 1) / 2                # the ball's centre on the screen
        fdepth = 300.0 - 0.507 * 100.0 - 10.0                  # the ball's centre, behind its surface
        scale = 0.012                                           # a figure px: 1.2 % of the height
        fist = dict(heat=1.0, x=fx, y=fy, dir=(1.0, 0.0), depth=fdepth, scale=scale, time=0.3)
        lit, _ = look(C2, A2, N2, D2, on2, fist=fist)
        cold, _ = look(C2, A2, N2, D2, on2, fist=dict(fist, heat=0.0))
        diff = np.abs(lit - base2).sum(axis=2) > 0.05
        assert np.abs(cold - base2).max() < 1e-9, "no flame on a cold fist"
        yy2, xx2 = np.mgrid[0:n, 0:n]
        u2, v2 = (xx2 + 0.5) / n, (yy2 + 0.5) / n
        hand = ((xx2 + 0.5) / n * 2 - 1 - 0.20) ** 2 + ((yy2 + 0.5) / n * 2 - 1 - 0.25) ** 2 < 0.13 ** 2
        assert diff[hand].mean() == 0.0, "the flame is behind the hand: the knuckles stay legible"
        px = lambda v: v * scale                                # figure px to viewport heights
        ahead = (u2 > fx + px(8)) & (u2 < fx + px(12)) & (np.abs(v2 - fy) < px(1.5))
        assert diff[ahead].mean() > 0.9, "the tongues run out ahead of the fist along the forearm"
        far = (u2 < fx - px(32)) | (u2 > fx + px(32)) | (np.abs(v2 - fy) > px(32))
        assert diff[far].mean() == 0.0, "and nothing further than the glow"
        # flat: on a flat wall the fire adds a handful of colours (the
        # glow's rings, the three tongues, the ink), not a gradient
        Cw = np.full((n, n, 3), 0.30 * 1.2); Aw = np.full((n, n, 3), 0.30)
        Nw = np.zeros((n, n, 3)); Nw[..., 2] = 1.0
        Dw = np.full((n, n), 900.0); onw = np.zeros((n, n), bool)
        # (counted without the vignette, which shades the wall under it a
        # little differently in every ring of pixels)
        vig, LOOK["VIGNETTE"] = LOOK["VIGNETTE"], 0.0
        wall0, _ = look(Cw, Aw, Nw, Dw, onw)
        wall1, _ = look(Cw, Aw, Nw, Dw, onw, fist=dict(fist, x=0.5, y=0.5, depth=200.0))
        LOOK["VIGNETTE"] = vig
        dw = np.abs(wall1 - wall0).sum(axis=2) > 0.05
        # (the glow's three rings, each tongue over each ring it crosses,
        # the ink: at most sixteen; a gradient is hundreds)
        cols = np.unique(np.round(wall1[dw], 3), axis=0)
        assert 4 <= len(cols) <= 16, "the flame is flat tones, %d colours" % len(cols)
        inkd = np.array(display(LOOK["INK"]))
        inked = dw & (np.abs(wall1 - inkd).sum(axis=2) < 0.02)
        assert inked.sum() > 100, "and there is an ink line round it"
        # the burst on the man hit: a ring growing from the point, sparks
        # flying out of it and dying, nothing after the last one; a man
        # nearer the camera hides it
        bx, by, bscale = 0.5, 0.5, 0.004
        burn = dict(age=0.10, x=bx, y=by, depth=240.0, scale=bscale, seed=3.0)
        early, _ = look(C, A, N, D, on, burn=dict(burn, age=0.02))
        mid, _ = look(C, A, N, D, on, burn=burn)
        late, _ = look(C, A, N, D, on, burn=dict(burn, age=0.40))
        over, _ = look(C, A, N, D, on, burn=dict(burn, age=0.60))
        rr2 = np.hypot(u2 - bx, v2 - by) / bscale                  # figure px from the burst
        de = np.abs(early - base).sum(axis=2) > 0.05
        dm = np.abs(mid - base).sum(axis=2) > 0.05
        dl = np.abs(late - base).sum(axis=2) > 0.05
        assert np.abs(over - base).max() < 1e-9, "the burst is over after the last spark"
        assert de.sum() > 0 and dm.sum() > 0 and dl.sum() > 0, "the burst is drawn while it lasts"
        ring_r = lambda age: FIRE["RING_FROM"] + (FIRE["RING_TO"] - FIRE["RING_FROM"]) * age / FIRE["RING_S"]
        ringc = np.array(_rgb(FIRE["RING_COL"]))
        ell = np.hypot(u2 - bx, (v2 - by) / FIRE["RING_SQUASH"]) / bscale
        on_ring = dm & (np.abs(mid - lerp(base, ringc, (1 - 0.10 / FIRE["RING_S"]) * FIRE["RING_A"])).sum(axis=2) < 0.05)
        assert on_ring.sum() > 50 and abs(np.median(ell[on_ring]) - ring_r(0.10)) < 2.0, "the ring is at its radius for its age"
        band = lambda age: np.abs(ell - ring_r(age)) <= 0.5 * (FIRE["RING_W"] * (1 - age / FIRE["RING_S"]) + 1) + 1.0
        se, sl = de & ~band(0.02), dl                             # the ring is gone by 0.40
        assert se.sum() > 0 and sl.sum() > 0, "there are sparks early and late"
        assert np.median(rr2[sl]) > 2.0 * np.median(rr2[se]), "the sparks fly out from the blow"
        hidden, _ = look(C, A, N, D, on, burn=dict(burn, x=0.75, depth=900.0))   # the man hit is behind the sphere
        dh = np.abs(hidden - base).sum(axis=2) > 0.05
        assert dh[on].sum() == 0 and dh[~on].sum() > 0, "a man in front hides the burst on the man behind him"
    finally:
        LOOK.clear(); LOOK.update(saved)
        FIRE.clear(); FIRE.update(saved_fire)
    return True


def _check_names():
    """MPC_Anime's parameters are the names Combat/SaudAnime.h writes, and
    both materials read the ones they are given."""
    h = open(os.path.join(ROOT, "Source", "SaudFighter", "Combat", "SaudAnime.h")).read()
    fh = open(os.path.join(ROOT, "Source", "SaudFighter", "Combat", "SaudFire.h")).read()
    for name, _ in MPC_SCALARS:
        where = fh if name in FIRE_PARAMS else h
        assert '"%s"' % name in where, "%s does not write %s" % ("SaudFire.h" if name in FIRE_PARAMS else "SaudAnime.h", name)
    for path in (MPC_PATH,) + tuple(MATERIALS):
        assert path.rsplit("/", 1)[1] in h, "SaudAnime.h does not load %s" % path
    import re
    # the fire's numbers are the ones SaudFire.h quotes from the browser
    F = FIRE
    shared = {
        "FigurePx": F["FIGURE_PX"], "FigureCm": F["FIGURE_CM"], "TongueRootPx": F["TONGUE_ROOT_PX"],
        "SwayRate": F["SWAY_RATE"], "SwayPhase": F["SWAY_PHASE"], "SwayPx": F["SWAY_PX"],
        "GlowCentrePx": F["GLOW_CX"], "GlowRadiusPx": F["GLOW_R"],
        "RingFromPx": F["RING_FROM"], "RingToPx": F["RING_TO"], "RingSeconds": F["RING_S"],
        "RingAlpha": F["RING_A"], "RingWidthPx": F["RING_W"], "RingSquash": F["RING_SQUASH"],
        "SparksHot": F["SPARKS_HOT"], "SparksPale": F["SPARKS_PALE"],
        "SparkSpeedHotPx": F["SPARK_SPD"][0], "SparkSpeedPalePx": F["SPARK_SPD"][1],
        "SparkSpeedShareMin": F["SPARK_SHARE_MIN"], "SparkLiftPx": F["SPARK_LIFT"],
        "SparkGravityPx": F["SPARK_G"], "SparkDragPerSecond": F["SPARK_DRAG"],
        "SparkLifeMin": F["SPARK_LIFE"][0], "SparkLifeMax": F["SPARK_LIFE"][1],
        "SparkRadiusMin": F["SPARK_R"][0], "SparkRadiusMax": F["SPARK_R"][1],
    }
    for name, want in shared.items():
        m = re.search(r"constexpr (?:float|int) %s = ([0-9.]+)f?;" % name, fh)
        assert m, "SaudFire.h has no %s" % name
        assert abs(float(m.group(1)) - want) < 1e-6, "SaudFire.h's %s is %s, FIRE's is %s" % (name, m.group(1), want)
    for i in range(3):
        assert abs(F["TONGUE_W"][i] - (5.2 - 1.1 * i)) < 1e-9 and abs(F["TONGUE_LEN"][i] - (20.0 - 4.5 * i)) < 1e-9
    assert "5.2f - 1.1f" in fh and "20.f - 4.5f" in fh, "SaudFire.h's tongues are not the browser's"
    for path, (code_of, inputs, _) in MATERIALS.items():
        code = code_of()
        for name in inputs:
            assert re.search(r"\b%s\b" % name, code), "%s does not read %s" % (path, name)
        left = set(re.findall(r"\b[A-Z][A-Z]+_[A-Z_]+\b|\b(?:SOFT|INK|EMBER|VIGNETTE)\b", code))
        assert not left, "placeholders left in %s: %s" % (path, sorted(left))
        assert "EyeAdaptationLookup" not in code, "the buffer is pre-exposed; do not expose it twice"
    # the HUD is drawn in the look's own ink and bone
    hud = open(os.path.join(ROOT, "Source", "SaudFighter", "Game", "SaudHUD.cpp")).read()
    for var, key in (("InkC", "INK"), ("BoneC", "BONE")):
        m = re.search(r"FLinearColor %s\(([0-9.]+)f, ([0-9.]+)f, ([0-9.]+)f" % var, hud)
        assert m, "SaudHUD.cpp has no %s" % var
        got = tuple(float(v) for v in m.groups())
        assert all(abs(a - b) < 1e-6 for a, b in zip(got, LOOK[key])), (
            "SaudHUD.cpp's %s is %s, the look's %s is %s" % (var, got, key, LOOK[key]))


# ------------------------------------------------------------------- editor
# path -> (code, the MPC parameters it reads, where it runs)
MATERIALS = {
    MATERIAL_PATH: (hlsl, ("Impact", "ImpactInvert", "Key"), "BL_SCENE_COLOR_AFTER_DOF"),
    FRAME_PATH: (hlsl_frame, ("Impact", "Speed", "SpeedCentreX", "SpeedCentreY", "SpeedSeed") + FIRE_PARAMS,
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
        bites = ("no_terminator", "no_ink", "grey_ink", "inner_only", "limb_gap", "specks", "stepped",
                 "one_tint", "accent_muted", "no_air", "ink_lines",
                 "sky_shaded", "flat_impact", "lines_over_men", "no_cut",
                 "fire_on_hand", "soft_glow", "no_fire_ink", "burst_through_men", "still_sparks",
                 "paper_impact", "grey_shadows", "world_as_fighter", "bright_sky", "no_vignette", "warm_fog")
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
