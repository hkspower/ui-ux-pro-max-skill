"""
The night's light: what it costs and how bright it is, held to its rules
(2026-10-03, Riyadh; asked as "make light and brightness optimization",
settled as both: faster lighting and better brightness).

    python3 Tools/look/lighting.py          the check, and what it measures
    python3 Tools/look/lighting.py --bite   each rule broken once

THE COST. Measured on the open world's plan before: 220 night lights, 181
of them shadowed fires with a smoke volume each, every one drawn as long as
its district was streamed in -- around one spot up to 92 lights, 57 of them
shadowed point lights, at once. Now:
  - every light is drawn while its pool is CullDegrees across from the eye
    and fades over the last FadeShare of that (Source/SaudFighter/Combat/
    SaudLight.h; build_souq.LIGHT_CULL and spawn_night() set each light's
    MaxDrawDistance and MaxDistanceFadeRange): measured here, at every fight,
    gate, start and fire in the world;
  - of the shadowed fires (tagged SaudLight::ShadowTag), the game lets only
    the ShadowBudget nearest the camera cast (USaudLightSubsystem; the
    harness's tests/light.cpp runs the choice);
  - every night light is Movable, so its shadow can be switched, and the
    project allows no static lighting (Config/DefaultEngine.ini): nothing
    in it is ever baked.

THE BRIGHTNESS. The open world -- the only map the game plays on -- had no
exposure of its own: no post-process volume, so the engine's default
exposure decided how bright a 2 lux moon was, and nothing tied it to
MPC_Anime.Key, the dial the look cuts light into tones by. build_world.py
now spawns a fixed exposure that puts the moon on open ground at MOON_TONE
of Key, the preview's own rule (anime_preview.KEY_OVER_MOON), so the
measured previews are the game's picture. The stage levels and the
prologue set a manual exposure bias too, but left the physical camera on:
held here to have it off, or the bias is not the exposure.

THE ISLAND (2026-10-03). L_MonkeyIsland had no light but the moon; it has
the souq's fires now (build_monkey_island_level.py, THE NIGHT), and is held
here to the same rules as the world: its fires spawned by spawn_night() (so
every one is Movable, drawn by its pool and tagged), every planned row of
them; its exposure the world's, and loaded wherever he is; and at most
DRAWN_CAP lights drawn around any spot on it -- its directors, its start,
its way home and every fire. And to the souq's own budget (NIGHT["budget"],
which the souq and the world hold per district): the island is one level
2.3 km long, 86 fires against the budget's 32, so it is held per what is
streamed in round a man -- every light within LOADED_M of any of those
spots -- and its level must be a partitioned world, or that is not what is
loaded.

Read from the sources, not run: no engine has opened this project.
"""

import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "Tools", "blender"))
sys.path.insert(0, os.path.join(ROOT, "Tools", "levels"))

FILES = dict(
    header="Source/SaudFighter/Combat/SaudLight.h",
    subsystem="Source/SaudFighter/Game/SaudLightSubsystem.cpp",
    souq="Tools/blender/build_souq.py",
    world="Tools/levels/build_world.py",
    levels="Tools/levels/build_levels.py",
    prologue="Tools/levels/build_prologue.py",
    preview="Tools/blender/anime_preview.py",
    engine="Config/DefaultEngine.ini",
    island="Tools/levels/build_monkey_island_level.py",
)
# At most this many night lights drawn around any one spot (34 measured
# with the cull, 92 before it)
DRAWN_CAP = 40
# What was drawn before the cull: every light streamed in, taken as within
# World Partition's default loading range, 256 m (as remembered)
LOADED_M = 256.0
PHYSICAL_OFF = '"auto_exposure_apply_physical_camera_exposure", False'
PHYSICAL_OVERRIDE = '"override_auto_exposure_apply_physical_camera_exposure", True'


def texts():
    return {k: open(os.path.join(ROOT, v), encoding="utf-8").read() for k, v in FILES.items()}


def _world():
    import importlib.util
    argv, sys.argv = sys.argv, ["build_world"]
    try:
        spec = importlib.util.spec_from_file_location("build_world", os.path.join(ROOT, FILES["world"]))
        W = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(W)
    finally:
        sys.argv = argv
    return W


def _island():
    """The island level's builder, loaded fresh (a sabotage may change it)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_monkey_island_level", os.path.join(ROOT, FILES["island"]))
    I = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(I)
    return I


def _header(text):
    def num(name):
        m = re.search(r"constexpr (?:float|int) %s = ([\d.]+)f?;" % name, text)
        return float(m.group(1)) if m else None
    m = re.search(r'constexpr const char\* ShadowTag = "([^"]+)";', text)
    return dict(degrees=num("CullDegrees"), fade=num("FadeShare"), budget=num("ShadowBudget"),
                tag=m.group(1) if m else None)


def _between(text, start, end):
    i = text.find(start)
    if i < 0:
        return ""
    j = text.find(end, i + len(start))
    return text[i:j if j > 0 else len(text)]


def lights_of(W, cull=None):
    """Every night light in the world: (x, y) cm, pool m, shadowed."""
    S = W.SOUQ
    out = []
    P = W.plan(*W.load())
    for d in P["districts"].values():
        Q = d.get("night") or (S.night_of(d["souq"]) if "souq" in d else None)
        if Q is None:
            continue
        for f in Q["fires"] + Q["door_fires"]:
            out.append((d["ox"] + f["x"], d["oy"] + f["y"], f["pool"], bool(f["shadow"])))
        for l in Q["lanterns"]:
            out.append((d["ox"] + l["x"], d["oy"] + l["y"], S.NIGHT["lantern"]["pool_m"], False))
    spots = [(a["x"], a["y"]) for a in P["actors"] if a["kind"] in ("WaveDirector", "Gate", "PlayerStart")]
    return out, spots + [(x, y) for x, y, _, _ in out]


def island_lights_of(I):
    """The island's fires and spots, as lights_of() gives the world's: (x, y)
    cm, pool m, shadowed, and smoking (a fifth the world's rows do not
    carry); its directors, its start, its way home and every fire. The plan
    is made once per loaded builder."""
    if not hasattr(I, "_lit_plan"):
        I._lit_plan = I.plan()
    P = I._lit_plan
    out = [(f["x"] * 100.0, f["y"] * 100.0, f["pool"], bool(f["shadow"]), bool(f.get("smoke"))) for f in P["fires"]]
    spots = [(a["x"] * 100.0, a["y"] * 100.0) for a in P["actors"] if a["kind"] in ("WaveDirector", "PlayerStart", "Exit")]
    return out, spots + [(l[0], l[1]) for l in out]


def island_budget(I, loaded_m=LOADED_M):
    """The souq's budget as the island streams: the most lights, the most
    shadowed and the most smoke volumes within loaded_m of any spot on it,
    nothing culled -- what is loaded round a man in a partitioned world."""
    lights, spots = island_lights_of(I)
    most = [0, 0, 0]
    for x, y in spots:
        near = [l for l in lights if math.hypot(l[0] - x, l[1] - y) <= loaded_m * 100.0]
        most = [max(most[0], len(near)), max(most[1], sum(1 for l in near if l[3])), max(most[2], sum(1 for l in near if l[4]))]
    return most


def measure(W, cull=None, loaded_m=None, I=None):
    """Around every spot: (most drawn, most of those shadowed). With
    loaded_m, nothing culled: every light within that many metres. With I,
    the island level's (its own map) instead of the world's."""
    S = W.SOUQ
    cull = cull or S.LIGHT_CULL
    far = (lambda pool: loaded_m * 100.0) if loaded_m else \
        (lambda pool: pool * 100.0 / math.tan(math.radians(cull["degrees"])))
    lights, spots = lights_of(W) if I is None else island_lights_of(I)
    most = [0, 0]
    for x, y in spots:
        near = [l for l in lights if math.hypot(l[0] - x, l[1] - y) <= far(l[2])]
        most = [max(most[0], len(near)), max(most[1], sum(1 for l in near if l[3]))]
    return most, len(lights), sum(1 for l in lights if l[3]), len(spots)


def check(T=None, W=None, cull=None, I=None):
    T = T or texts()
    W = W or _world()
    I = I or _island()
    S = W.SOUQ
    cull = cull or S.LIGHT_CULL
    miss = []
    # 1. the header and the builder's copy
    h = _header(T["header"])
    for k in ("degrees", "fade", "tag"):
        if h[k] != cull[k]:
            miss.append("SaudLight.h's %s is %s, build_souq.LIGHT_CULL's %s" % (k, h[k], cull[k]))
    if "SaudLight::ShadowTag" not in T["subsystem"] or "SaudLight::PickShadows" not in T["subsystem"]:
        miss.append("USaudLightSubsystem does not pick the shadows by SaudLight.h's tag and rule")
    # 2. what spawn_night() sets on every light
    night = _between(T["souq"], "def spawn_night(", "\ndef ")
    fires, lanterns = _between(night, "for i, f in enumerate(fires):", "col = _lin("), \
        _between(night, "for i, l in enumerate(lanterns):", "return lights")
    for what, part, pool in (("fire", fires, 'f["pool"]'), ("lantern", lanterns, 'NIGHT["lantern"]["pool_m"]')):
        if "unreal.ComponentMobility.MOVABLE" not in part:
            miss.append("spawn_night() leaves a %s light Stationary: its shadow cannot be switched" % what)
        if "draw_distance_cm(%s)" % pool not in part or '"max_draw_distance", far' not in part:
            miss.append("spawn_night() draws a %s light as far as its district is loaded" % what)
        if '"max_distance_fade_range", far * LIGHT_CULL["fade"]' not in part:
            miss.append("spawn_night() cuts a %s light off at its distance instead of fading it" % what)
    if not re.search(r'if f\["shadow"\]:\s*\n\s*a\.set_editor_property\("tags", \[unreal\.Name\(LIGHT_CULL\["tag"\]\)\]\)', fires):
        miss.append("spawn_night() does not tag a shadowed fire, so the game never limits its shadow")
    # 2b. the island's fires spawned by spawn_night(), every one of its rows:
    #     the call, fed straight from a list made of the whole of P["fires"]
    #     on the line before it -- no filter, no slice, nothing between
    build = _between(T["island"], "def build(P):", "\ndef ")
    if not re.search(r'SOUQ\.spawn_night\(spawn_at, rows,', build):
        miss.append("the island's build spawns its fires some other way than spawn_night(): not culled, not tagged")
    elif not re.search(r'\n(\s*)rows = \[[^\n]* for f in P\["fires"\]\]\n\1lights, smoke = SOUQ\.spawn_night\(spawn_at, rows,', build):
        miss.append("the island's build hands spawn_night() other rows than every planned fire")
    # 3. the world's exposure: the volume, and the rule
    vol = _between(T["world"], 'spawn(unreal.PostProcessVolume, "Exposure"', 'post.set_editor_property("settings", pp)')
    if not vol:
        miss.append("the world spawns no exposure: the engine's default decides how bright the moon is")
    else:
        for want, why in (('"unbound", True', "it is not unbound"), ("AEM_MANUAL", "it is not manual"),
                          (PHYSICAL_OVERRIDE, "it leaves the physical camera to the engine"),
                          (PHYSICAL_OFF, "the physical camera is on, so the bias is not the exposure"),
                          ('"auto_exposure_bias", exposure_bias()', "its bias is not exposure_bias()")):
            if want not in vol:
                miss.append("the world's exposure: %s" % why)
    m = re.search(r"^KEY_OVER_MOON = ([\d.]+)", T["preview"], re.M)
    if not m:
        miss.append("anime_preview.py has no KEY_OVER_MOON to hold the exposure to")
    else:
        r = W.WORLD_RIG
        ground = r["lux"] * math.sin(math.radians(-r["pitch"]))
        got = 2.0 ** W.exposure_bias() / 1.2 * ground / math.pi
        want = W.LOOK["KEY"] / float(m.group(1))
        if abs(got / want - 1.0) > 0.01:
            miss.append("the moon on open ground lands at %.3f of Key, the preview's night at %.3f "
                        "(1 / KEY_OVER_MOON)" % (got / W.LOOK["KEY"], want / W.LOOK["KEY"]))
    # 3b. the island's exposure: the world's volume and bias
    vol = _between(T["island"], 'spawn(unreal.PostProcessVolume, "Exposure"', 'ppv.set_editor_property("settings", s)')
    if not vol:
        miss.append("the island spawns no exposure: the engine's default decides how bright its moon is")
    else:
        for want, why in (('"unbound", True', "it is not unbound"), ("AEM_MANUAL", "it is not manual"),
                          (PHYSICAL_OVERRIDE, "it leaves the physical camera to the engine"),
                          (PHYSICAL_OFF, "the physical camera is on, so the bias is not the exposure"),
                          ('"auto_exposure_bias", BW.exposure_bias()', "its bias is not the world's exposure_bias()")):
            if want not in vol:
                miss.append("the island's exposure: %s" % why)
        # the volume stands at the island's middle, 1.6 km from the pier: in
        # its partitioned world (3c) it must not be streamed with the ground
        if 'ppv = pin(spawn(unreal.PostProcessVolume, "Exposure"' not in T["island"]:
            miss.append("the island's exposure is streamed with the ground at its middle: at the pier there is none")
    # 3c. the island's level a partitioned world, so that what its budget is
    #     held to (6b) is what is loaded
    if "les.new_level(LEVEL, is_partitioned_world=True)" not in build:
        miss.append("the island's level is not partitioned: every fire and every smoke column on it is loaded at once")
    # 4. the stage levels' and the prologue's manual exposure: the physical camera off
    for k in ("levels", "prologue"):
        part = _between(T[k], "AEM_MANUAL", "auto_exposure_bias")
        if PHYSICAL_OFF not in part or PHYSICAL_OVERRIDE not in part:
            miss.append("%s sets a manual exposure bias with the physical camera left on" % FILES[k])
    # 5. nothing baked
    if not re.search(r"^r\.AllowStaticLighting=False\s*$", T["engine"], re.M):
        miss.append("DefaultEngine.ini allows static lighting, and nothing in this game is ever baked")
    # 6. measured: drawn around any one spot
    (drawn, shadowed), _, _, _ = measure(W, cull)
    if drawn > DRAWN_CAP:
        miss.append("%d night lights drawn around one spot, more than %d" % (drawn, DRAWN_CAP))
    (drawn, shadowed), _, _, _ = measure(W, cull, I=I)
    if drawn > DRAWN_CAP:
        miss.append("%d night lights drawn around one spot on the island, more than %d" % (drawn, DRAWN_CAP))
    # 6b. the island within the souq's budget, per what is streamed in round
    #     a man (the souq and the world hold it per district)
    B = S.NIGHT["budget"]
    lights, shadowed, smoke = island_budget(I)
    if lights > B["lights"] or shadowed > B["shadowed"] or smoke > B["smoke"]:
        miss.append("%d lights, %d shadowed, %d smoke volumes within %.0f m of one spot on the island: over the budget "
                    "%d / %d / %d" % (lights, shadowed, smoke, LOADED_M, B["lights"], B["shadowed"], B["smoke"]))
    return miss


def _bites():
    def text(key, old, new, count=1):
        def f(T, W, cull, I):
            assert old in T[key], "sabotage did not apply: %s" % old
            T[key] = T[key].replace(old, new, count)
        return f

    def setw(name, value):
        def f(T, W, cull, I):
            setattr(W, name, value)
        return f

    def cull_to(k, v, header=None):
        def f(T, W, cull, I):
            cull[k] = v
            if header:
                T["header"] = T["header"].replace(*header)
        return f

    def island_crowded(T, W, cull, I):
        """Four fires where the island's plan puts one (build_world's 31
        sabotage, on the island)."""
        plan = I.plan

        def crowded():
            P = plan()
            P["fires"] = [dict(f) for f in P["fires"] for _ in range(4)]
            return P
        I.plan = crowded

    def island_over_budget(T, W, cull, I):
        """Two fires where the island's plan puts one: still inside
        DRAWN_CAP round every spot (32 at the worst), over the budget
        within LOADED_M (44 at the worst) -- caught by 6b alone."""
        plan = I.plan

        def doubled():
            P = plan()
            P["fires"] = [dict(f) for f in P["fires"] for _ in range(2)]
            return P
        I.plan = doubled

    return {
        "header_drift": cull_to("degrees", 3.0),
        "tag_drift": text("header", 'ShadowTag = "SaudShadow"', 'ShadowTag = "SaudShadows"'),
        "no_budget": text("subsystem", "SaudLight::PickShadows(", "PickNothing("),
        "fire_stationary": text("souq", "        c.set_mobility(unreal.ComponentMobility.MOVABLE)\n", ""),
        "lantern_endless": text("souq", 'far = draw_distance_cm(NIGHT["lantern"]["pool_m"])', "far = 0.0"),
        "fire_no_fade": text("souq", '"max_distance_fade_range", far * LIGHT_CULL["fade"]',
                             '"max_distance_fade_range", 0.0'),
        "untagged": text("souq", '            a.set_editor_property("tags", [unreal.Name(LIGHT_CULL["tag"])])\n',
                         "            pass\n"),
        "no_exposure": text("world", 'spawn(unreal.PostProcessVolume, "Exposure"', 'spawn(unreal.PostProcessVolume, "Grade"'),
        "world_physical": text("world", PHYSICAL_OFF, PHYSICAL_OFF.replace("False", "True")),
        "moon_tone": setw("MOON_TONE", 1.0),
        "key_drift": text("preview", "KEY_OVER_MOON = 2.0", "KEY_OVER_MOON = 3.0"),
        "levels_physical": text("levels", PHYSICAL_OFF, PHYSICAL_OFF.replace("False", "True")),
        "prologue_physical": text("prologue", PHYSICAL_OFF, PHYSICAL_OFF.replace("False", "True")),
        "static_lighting": text("engine", "r.AllowStaticLighting=False", "r.AllowStaticLighting=True"),
        "cull_far": cull_to("degrees", 1.0, ("CullDegrees = 2.5f;", "CullDegrees = 1.0f;")),
        "island_unlit": text("island", "SOUQ.spawn_night(spawn_at, rows,", "SOUQ.spawn_lights(spawn_at, rows,"),
        "island_physical": text("island", PHYSICAL_OFF, PHYSICAL_OFF.replace("False", "True")),
        "island_crowded": island_crowded,
        "island_filtered": text("island", 'for f in P["fires"]]\n', 'for f in P["fires"] if f["kind"] == "pyre"]\n'),
        "island_exposure_out": text("island", 'ppv = pin(spawn(unreal.PostProcessVolume, "Exposure"',
                                    'ppv = (spawn(unreal.PostProcessVolume, "Exposure"'),
        "island_unpartitioned": text("island", "les.new_level(LEVEL, is_partitioned_world=True)", "les.new_level(LEVEL)"),
        "island_over_budget": island_over_budget,
    }


def main():
    W = _world()
    I = _island()
    if "--bite" in sys.argv:
        clean = check(W=W, I=I)
        if clean:
            print("the unbroken sources fail their own rules, so no sabotage can be counted:")
            for m in clean:
                print("  " + m)
            sys.exit(1)
        caught, bites = 0, _bites()
        for name, breaks in bites.items():
            T, W2, cull = texts(), _world(), None
            I2 = _island() if name.startswith("island") else I
            cull = dict(W2.SOUQ.LIGHT_CULL)
            breaks(T, W2, cull, I2)
            miss = check(T, W2, cull, I2)
            caught += bool(miss)
            print("  %-18s %s" % (name, ("caught: " + miss[0]) if miss else "NOT caught"))
        print("%d of %d sabotages caught" % (caught, len(bites)))
        sys.exit(0 if caught == len(bites) else 1)
    miss = check(W=W, I=I)
    (drawn, shadowed), n, ns, spots = measure(W)
    (d0, s0), _, _, _ = measure(W, loaded_m=LOADED_M)
    print("the night: %d lights, %d of them shadowed fires; around the worst of %d spots" % (n, ns, spots))
    print("  drawn:    %d lights, %d shadowed (with no cull, all within %.0f m: %d, %d)"
          % (drawn, shadowed, LOADED_M, d0, s0))
    (drawn, shadowed), n, ns, spots = measure(W, I=I)
    (d0, s0), _, _, _ = measure(W, loaded_m=LOADED_M, I=I)
    print("  the island: %d lights, %d shadowed; around the worst of its %d spots %d drawn, %d shadowed "
          "(with no cull: %d, %d)" % (n, ns, spots, drawn, shadowed, d0, s0))
    B = W.SOUQ.NIGHT["budget"]
    print("  the island's budget, within %.0f m of any spot (it streams): %d lights, %d shadowed, %d smoke "
          "(at most %d / %d / %d)" % ((LOADED_M,) + tuple(island_budget(I)) + (B["lights"], B["shadowed"], B["smoke"])))
    print("  casting:  at most %d (SaudLight::ShadowBudget, the nearest)" % _header(texts()["header"])["budget"])
    print("  exposure: bias %+.2f EV, the moon on open ground at %.2f of Key" % (W.exposure_bias(), W.MOON_TONE))
    for m in miss:
        print("MISS " + m)
    print("lighting: %s" % ("every rule held" if not miss else "%d broken" % len(miss)))
    sys.exit(1 if miss else 0)


if __name__ == "__main__":
    main()
