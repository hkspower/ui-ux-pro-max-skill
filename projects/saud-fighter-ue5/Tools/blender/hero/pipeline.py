"""A fighter, rebuilt: the whole pipeline end to end, for whichever man the
roster names.

    anatomy   the body as lofted cross-sections and lofted limbs
    assembly  the two-pass voxel union, the face sculpt, the hair, the eyes
    garments  the tee and the track pants as shells off the body
    finish    the budget, the UVs, the paint, the bake
    rig_export the skeleton with fingers, the binding, the exports
    rig_full_ik the control rig an animator poses him through

Run through build_saud.py for the hero, build_fighters.py for anyone:

    python3 build_saud.py              the hero: 4K colour, 2K normals, 64-sample renders
    python3 build_saud.py --fast       1K textures, quick renders, for a look
    python3 build_saud.py --resume     skip the nine-minute build, reload it
    python3 build_saud.py --coarse     a rough body, to check the later stages
    python3 build_saud.py --out DIR    write somewhere else than the project

ONE BODY, EVERY MAN. Everything up to the bake runs at Saud's coordinates
-- the one set every absolute constant in hero/ was written for -- and the
finished, painted, baked mesh is then taken to the man's own size through
anatomy.scale_to, the browser build's own sc / build mapping, before the
skeleton is built on it. What differs between two men on that body is his
palette and kit (read from the roster), his hair, his beard -- and, the
Unreal build's own and labelled so (the browser owns none of them): his
cut where it is not the browser's (CUTS), his face (FACES, NOSES, EYES),
his body (PHYSIQUE, MASS, LIMBS), his ears (EARS), the checks his face is
held to (HOLDS), and, from 2026-09-28, his paint and kit (PAINT, TOPS,
BOTTOMS, KIT, VEINS). apply_man(kind) sets all of it that is module state.
"""
import bpy, os, sys, time, math, json
from mathutils import Vector
import build_saud as legacy
from . import anatomy as A, assembly as B, garments as G, finish as F, rig_export as R

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
UNITY = os.path.abspath(os.path.join(PROJECT, "..", "ahmed-fighter-unity"))

# The mannequin's skeleton, which every fighter has to export exactly:
# 24 deforming, root, 7 IK, 30 finger. A control bone in the export would
# break the retarget that makes these models useful, so the export asserts
# this set and nothing else.
MANNEQUIN = {
    "root", "pelvis", "spine_01", "spine_02", "spine_03", "neck_01", "head",
    "ik_foot_root", "ik_foot_l", "ik_foot_r", "ik_hand_root", "ik_hand_gun", "ik_hand_l", "ik_hand_r",
} | {"%s_%s" % (b, s) for s in ("l", "r") for b in
     ("clavicle", "upperarm", "lowerarm", "hand", "hand_end", "thigh", "calf", "foot", "ball")} \
  | {"%s_%02d_%s" % (f, k, s) for s in ("l", "r") for f in ("index", "middle", "ring", "pinky", "thumb") for k in (1, 2, 3)}
assert len(MANNEQUIN) == 62

# The Unreal men's own cuts, where they are not the browser's
# (2026-09-26, "improve hair style": the Unreal build, new cuts among what
# was asked). Like FACES, numbers -- names -- the browser does not own, and
# labelled so: the browser's drawing of these men keeps `look.hairStyle`.
# AL-SAQR, "the falcon", the fastest man in the game, wears a hawk's crest
# where the browser gives him a fringe (whose 3D locks, 6 mm through, broke
# into shards at the 3.5 mm remesh); the thug a high-and-tight where the
# browser gives him a buzz, which in 3D was the skull in a brown helmet.
CUTS = {"saqr": "crest", "thug": "hightop"}

# ---- the Unreal men's own numbers --------------------------------------
# Everything below is this build's and NOT the browser's: the browser draws
# every man from one figure and one skull and tells them apart by hair,
# beard and kit (README: "Silhouette does the work"), and its numbers
# (roster.py reads them) do not move for any of it. Keyed by the roster's
# kind, Saud ("saud") included. A man a table does not list takes the
# shared number. What is built before the checkpoint is stamped beside it
# (PRE_CHECKPOINT, man_stamp) and a --resume onto a checkpoint built with
# other numbers is refused.
#
# 2026-09-28 (Riyadh), asked as "make Saud more aggressive and more fit
# look; make full redesign, make all game like dark anime adult style":
# every man's face grim -- a seinen fight manga's, not a mannequin's --
# Saud's lean and his scowl hooded, the other five men's archetypes in
# their faces, noses and bodies.

# How one man's face differs from another's on the same skull: factors on
# the amplitudes in sculpt.FACE (a name the entry leaves out is 1.0, or 0
# for sculpt.OPTIONAL's rows).
FACES = {
    # Saud: the seinen scowl -- the brow ridge pulled down over the eye
    # (brow_low, corrugator: the crest 6.2 mm in front of the upper lid at
    # the pupil, it was 1.25), a lean cheek under a hard cheekbone edge
    # (hollow 1.9, cheek_fat .30, zygoma: the hollow 5.6 mm deep, it was
    # 3.0), a squarer jaw and chin (gonion, chin_sq) with the masseter kept
    # at .65 so it does not grow into the brawler's, and a thinner mouth
    # set hard (the lips down, the line and the corners deeper). Supersedes
    # "Saud is eighteen" (2026-09-20: brow .75, glabella .80, jaw .85, chin
    # .85, masseter .65, hollow .85).
    "saud":    dict(brow=0.70, glabella=1.00, temple=1.35, cheekbone=0.85, cheek_fat=0.30, hollow=1.90,
                    masseter=0.65, jaw1=1.00, jaw2=1.00, jaw3=0.95, chin=0.90,
                    lip_upper=0.70, lip_lower=0.72, mouthline=1.25, corner=1.80, mentolab=1.30,
                    brow_low=1.0, corrugator=1.0, zygoma=1.0, gonion=1.0, chin_sq=1.0),
    # the thug: gaunt and wiry -- a heavy brow, a hard cheekbone over a
    # sunken cheek, thin lips (was chin .85, brow .90, cheekbone .90, tip
    # .95, masseter .80: the smallest man on screen)
    "thug":    dict(chin=0.90, brow=1.15, glabella=1.10, cheekbone=1.25, cheek_fat=0.45, hollow=2.2,
                    masseter=1.0, tip=0.95, lip_upper=0.80, lip_lower=0.80),
    # the brawler: as he was, stocky and bearded (tip 1.05, not 1.10: at
    # 1.10 the old, broad nose field peaked at 30.1 mm and check_profile
    # holds every man to 20-30; on the narrowed nose 1.05 peaks at 24.3)
    "brawler": dict(brow=1.35, glabella=1.20, jaw1=1.30, jaw2=1.30, jaw3=1.30, chin=1.25,
                    masseter=1.50, cheekbone=1.15, tip=1.05, hollow=0.60),
    # AL-SAQR, the falcon: a hawk's hard lean face
    "saqr":    dict(brow=1.25, glabella=1.15, cheekbone=1.30, cheek_fat=0.60, hollow=1.8,
                    jaw1=1.10, jaw2=1.10, jaw3=1.10, chin=1.10, masseter=1.10, lip_upper=0.85, lip_lower=0.85),
    # AL-WAHSH, the veteran champion: heavy bone, deep-set eyes
    "boss":    dict(brow=1.45, glabella=1.30, jaw1=1.35, jaw2=1.35, jaw3=1.35, chin=1.30,
                    masseter=1.60, cheekbone=1.20, socket=1.40, lip_upper=0.90, lip_lower=0.90),
    # ZAYOS, the giant: heavier again
    "zayos":   dict(brow=1.60, glabella=1.40, jaw1=1.45, jaw2=1.45, jaw3=1.45, chin=1.35,
                    masseter=1.70, cheekbone=1.25, socket=1.50, lip_upper=0.85, lip_lower=0.85),
}

# A man's nose where it is not the shared one: {feature: dict(dx=, dz=,
# k=)} -- k on its amplitude (after FACES), dx / dz moving it (metres, +x
# his left): sculpt.with_nose. check_profile measures the widths about the
# nose's own crest and holds the crest within 4 mm of the midline.
NOSES = {
    # broken, knocked to his left: the crest 2.75 mm off the midline, a
    # dorsal hump 2.84 mm over the nasion-tip chord (1.61 plain), the tip
    # 18.75 mm wide. The nose's base (the alae, their creases, the
    # nostrils) goes with it, 2.5 mm: left where it was, the columella
    # knocked away from the right nostril left a 3.0 mm slot on that side.
    "brawler": dict(bridge2=dict(dx=0.0012, k=1.30), bridge3=dict(dx=0.0022, k=1.05),
                    tip=dict(dx=0.0030, k=0.98), columella=dict(dx=0.0020),
                    ala=dict(dx=0.0025), alar_crease=dict(dx=0.0025), nostril=dict(dx=0.0025)),
    # aquiline: the hump 4.16 mm, the tip hooked down 1.2 mm
    "saqr":    dict(bridge2=dict(k=1.28), bridge3=dict(k=1.08), tip=dict(dz=-0.0012, k=0.96)),
    # flattened, and knocked to his right: the dorsum 0.84 mm, the alae 43 mm
    "boss":    dict(bridge1=dict(k=0.80), bridge2=dict(k=0.82, dx=-0.0010), bridge3=dict(k=0.90, dx=-0.0015),
                    tip=dict(k=1.02, dx=-0.0012), ala=dict(k=1.08)),
    # flattened: the dorsum 0.87 mm
    "zayos":   dict(bridge1=dict(k=0.78), bridge2=dict(k=0.80), bridge3=dict(k=0.88), tip=dict(k=0.98),
                    ala=dict(k=1.08)),
}

# A man's lids: sculpt.set_eye's numbers. Saud's HOODED -- a lid set low
# over an eye that stays open (the fissure 9.6 -> 8.25 mm, the upper lid
# over 2.40 mm of the iris, 1.2 mm of iris still over the pupil), which
# check_eye_shape holds to its own rules; the five men's heavier but open
# (the upper lid over 1.65-1.85 mm of the iris, 1.25 before; the open rule
# allows 2).
EYES = {
    "saud":    dict(hooded=True, UP_AT_PUPIL=0.00325, DN_AT_PUPIL=0.0050, UP_ROUND=0.80, UP_PEAK=0.40),
    "thug":    dict(UP_AT_PUPIL=0.0039),
    "brawler": dict(UP_AT_PUPIL=0.0040),
    "saqr":    dict(UP_AT_PUPIL=0.0038),
    "boss":    dict(UP_AT_PUPIL=0.0039),
    "zayos":   dict(UP_AT_PUPIL=0.0040),
}

# What a man's built face is held to beyond everyone's (assembly.check_mien;
# brow_slant is face.check_brows'). Saud's: the brow at least 4.5 mm over
# the lid, the hollow at least 4.5 mm, and his jaw at most 128.5 mm across
# its angles so the brawler (129.7) keeps the widest.
HOLDS = {
    "saud": dict(brow_over=0.0045, hollow=0.0045, jaw_max=0.1285, brow_slant=0.0025),
}

# A man's trunk (anatomy.PHYSIQUES, set by anatomy.set_physique): Saud lean
# -- a narrower waist, a stronger V, defined abs, obliques and serratus, a
# deltoid cap grown with his arm and tied into the pec.
PHYSIQUE = {
    "saud": "lean",
}

# How much of each muscle mass a man carries against the canonical body's:
# factors on assembly.masses by name. The trapezius stays at 1.0 on every
# man: 1.08-1.20 took check_neck's girth to 0.465-0.475 (its band is
# 0.40-0.46), and ZAYOS's lat at 1.10 broke the V (a 3 mm bulge).
MASS = {
    # wiry: a little less chest and shoulder
    "thug":    dict(delt=0.95, pec=0.92, pec_up=0.92, oblique=0.90),
    # the heavy man, heavier than Saud's frame at last: shoulders, chest
    # and a thick waist
    "brawler": dict(delt=1.18, pec=1.12, pec_up=1.12, oblique=1.35, rectus_sheet=1.30, lat=1.05),
    # the lean V of a kicker
    "saqr":    dict(delt=1.08, pec=0.95, oblique=0.70, rectus0=1.15, rectus1=1.15, rectus2=1.15, lat=0.95),
    "boss":    dict(delt=1.15, pec=1.10, pec_up=1.10, oblique=1.20),
    "zayos":   dict(delt=1.15, pec=1.10, pec_up=1.10),
}

# How thick a man's arm muscle reads, against anatomy.arm's own numbers --
# the biceps and forearm flexor mass, not the elbow or wrist (see arm()'s
# own per-ring weights, which is where a change here actually lands).
# Saud: requested 2026-09-20, alongside his face -- eighteen and still a
# working pro fighter's arms, not a stripped-down teenager's; 1.18 -> 1.30
# on 2026-09-24, asked as "make arm stronger" (biceps girth 0.442 -> 0.470
# m, measured on the build): a heavyweight's arms, the register the anime
# look's seinen fighters are drawn in, with the elbow and wrist still the
# joint's own width (arm()'s ring weights). The others 2026-09-28: the
# thug's arms at his l 0.804 were twigs, and the brawler, the "heavy" man,
# had Saud's frame with thinner arms. ZAYOS is unlisted: his build is
# already 1.60.
LIMBS = {
    "saud":    1.30,
    "thug":    1.20,
    "brawler": 1.40,
    "saqr":    1.10,
    "boss":    1.10,
}

# A cauliflower ear, {'l': k, 'r': k} on his left (+x) and right ear
# (assembly.ear): the brawler's left, both of AL-WAHSH's.
EARS = {
    "brawler": dict(l=1.0),
    "boss":    dict(l=1.0, r=1.0),
}

# Paint and kit, all of it after the checkpoint (2026-09-28; filled by the
# face, body and five-men paint): face.set_look's knobs (PAINT), the top
# and trousers' cut (TOPS, BOTTOMS -- built before the checkpoint, so
# stamped), the kit's colours and pieces (KIT), the veins (VEINS). Empty:
# every man paints and dresses as he did.
PAINT = {}
TOPS = {}
BOTTOMS = {}
KIT = {}
VEINS = {}

# The tables built before the checkpoint, and so stamped beside it: a
# --resume onto a checkpoint built with any other entry would paint this
# man's lash line on another man's lids, his tank over another's body.
PRE_CHECKPOINT = ("FACES", "NOSES", "EYES", "PHYSIQUE", "MASS", "LIMBS", "EARS", "TOPS", "BOTTOMS")

# What the tables said before 2026-09-28, which is what every checkpoint
# without a .man stamp was built with (read with its .hair, as before).
_LEGACY = dict(
    FACES={"brawler": dict(brow=1.35, glabella=1.20, jaw1=1.30, jaw2=1.30, jaw3=1.30, chin=1.25,
                           masseter=1.50, cheekbone=1.15, tip=1.05, hollow=0.60),
           "thug": dict(chin=0.85, brow=0.90, cheekbone=0.90, tip=0.95, masseter=0.80),
           "saud": dict(brow=0.75, glabella=0.80, jaw1=0.85, jaw2=0.85, jaw3=0.85, chin=0.85,
                        masseter=0.65, hollow=0.85)},
    LIMBS={"saud": 1.30},
)


def hair_style_of(spec):
    """The cut: pipeline.CUTS, else the roster's `look.hairStyle`
    (assembly.HAIR_STYLES); `quiff: true` is the name Saud's cut had before
    there was more than one."""
    bald = bool(spec["look"].get("bald"))
    return "bald" if bald else CUTS.get(spec["kind"]) or spec["look"].get("hairStyle") or (
        "quiff" if spec["look"].get("quiff") else "crop")


def man_stamp(kind, hair_style):
    """What of this man is built before the checkpoint: every
    PRE_CHECKPOINT table's entry (None where he has none) and the cut, as
    JSON would write it."""
    g = globals()
    out = {t: g[t].get(kind) for t in PRE_CHECKPOINT}
    out["hair"] = hair_style
    return json.loads(json.dumps(out, sort_keys=True))


def legacy_stamp(kind, hair_style):
    """man_stamp for a checkpoint written before the .man stamp existed:
    the tables as they were, and the cut its .hair says."""
    out = {t: _LEGACY.get(t, {}).get(kind) for t in PRE_CHECKPOINT}
    out["hair"] = hair_style
    return json.loads(json.dumps(out, sort_keys=True))


def check_resume(check, kind, name, hair_style, bald=False):
    """The --resume guard: the checkpoint at `check` must have been built
    with this man's pre-checkpoint numbers (its .man stamp; before the
    stamp, its .hair and the tables as they were). Refuses with 'rebuild
    him without --resume'."""
    want = man_stamp(kind, hair_style)
    if os.path.exists(check + ".man"):
        built = json.load(open(check + ".man"))
    else:
        # a checkpoint older than the stamp: the cut from its .hair (read as
        # quiff for Saud, bald for the bald and crop for the rest before
        # that), everything else as the tables were
        cut = open(check + ".hair").read().strip() if os.path.exists(check + ".hair") else (
            "quiff" if kind == "saud" else ("bald" if bald else "crop"))
        built = legacy_stamp(kind, cut)
    diff = sorted(k for k in set(want) | set(built) if want.get(k) != built.get(k))
    assert not diff, "%s's checkpoint was built with other %s (%s): rebuild him without --resume" % (
        name, "/".join(diff), "; ".join("%s %s -> %s" % (k, json.dumps(built.get(k)), json.dumps(want.get(k))) for k in diff))
    return want


def apply_man(kind, spec=None):
    """Set every per-man number that is module state, before anything is
    built, resumed or painted: the lids (sculpt.set_eye), the trunk
    (anatomy.set_physique), the cut and the grey (face.set_hair), and the
    paint (face.set_look, once PAINT has entries). Everything the tables
    say that is passed as an argument instead (FACES, NOSES, MASS, LIMBS,
    EARS, HOLDS) is B.build's. Returns the man's stamp."""
    from . import roster, sculpt as SC, face as FA
    spec = spec or roster.spec(kind)
    men = {"saud"} | set(roster.enemies())
    for t in ("CUTS", "FACES", "NOSES", "EYES", "HOLDS", "PHYSIQUE", "MASS", "LIMBS", "EARS",
              "PAINT", "TOPS", "BOTTOMS", "KIT", "VEINS"):
        bad = set(globals()[t]) - men
        assert not bad, "pipeline.%s names no man in the roster: %s" % (t, sorted(bad))
    hair_style = hair_style_of(spec)
    assert hair_style in B.HAIR_STYLES, "%s: no hair style %r" % (spec["name"], hair_style)
    SC.set_eye(**EYES.get(kind, {}))
    A.set_physique(PHYSIQUE.get(kind))
    FA.set_hair(hair_style, spec["look"].get("grey", 0.0))
    if PAINT.get(kind) or hasattr(FA, "set_look"):
        FA.set_look(**PAINT.get(kind, {}))
    return man_stamp(kind, hair_style)


def run(argv=None):
    """The hero, as build_saud.py has always built him."""
    from . import roster
    return build_fighter(roster.spec("saud"), argv)


def build_fighter(spec, argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    name, low = spec["name"], spec["name"].lower()
    FAST = "--fast" in argv
    TEX = 1024 if FAST else 4096
    BUDGET = 60000
    # bump strength of the pore / hair noise in the normal bake. Hair 0.35
    # -> 0.25 with the noise now coherent (finish.shader): the old strength
    # was tuned on per-texel dither that averaged itself away.
    PORES = {"skin": 0.15, "hair": 0.25}
    # all of the skin's diffuse light scatters under it (finish.SKIN_SCATTER_MM
    # says how far); 0.28 was a part-diffuse compromise for a radius three
    # times too long
    SKIN_SSS = 1.0
    pal = F.palette_for(spec)
    bald = bool(spec["look"].get("bald"))
    no_tee = not spec["look"].get("tee", True)
    gloves = spec["look"].get("hands") == "gloves"
    assert bald or pal["hair"] is not None, "%s is not bald and has no hair colour" % name
    kind = spec["kind"]
    face_scale = FACES.get(kind)
    arm_scale = LIMBS.get(kind, 1.0)
    # every per-man number that is module state -- the lids, the trunk, the
    # cut (the roster's `look.hairStyle` or CUTS) and how grey he is at the
    # temples (`look.grey`), the paint -- set here, before the resume branch,
    # so a resumed man is painted on his own lids and trunk
    man = apply_man(kind, spec)
    hair_style = man["hair"]
    if "--out" in argv:
        OUT = os.path.abspath(argv[argv.index("--out") + 1])
        UE5_MODELS = os.path.join(OUT, "ue5", "Models"); UE5_TEX = os.path.join(OUT, "ue5", "Textures", name)
        UNITY_MODELS = os.path.join(OUT, "unity", "Models"); RENDERS = os.path.join(OUT, "renders"); RIGS = OUT
    else:
        # The project itself: the Unreal models and textures, the Unity copy
        # beside its own port, the renders under Docs, the animator's .blend
        # in Tools/blender/rigs. The checkpoint stays out of the tree.
        OUT = os.path.join(HERE, "build")
        UE5_MODELS = os.path.join(PROJECT, "Content", "Models"); UE5_TEX = os.path.join(PROJECT, "Content", "Textures", name)
        UNITY_MODELS = os.path.join(UNITY, "Assets", "Resources", "Models"); RENDERS = os.path.join(PROJECT, "Docs", "renders")
        RIGS = os.path.join(os.path.dirname(HERE), "rigs")
    os.makedirs(RIGS, exist_ok=True)
    # Unreal only unless asked: the Unity port is frozen (see ../../CLAUDE.md),
    # and rebuilding the hero should not drop a second FBX into a tree nobody
    # develops. `--unity` puts it back.
    if "--unity" not in argv:
        UNITY_MODELS = None
    for d in (OUT, UE5_MODELS, UE5_TEX, RENDERS): os.makedirs(d, exist_ok=True)
    if UNITY_MODELS: os.makedirs(UNITY_MODELS, exist_ok=True)

    t0 = time.time()
    def stamp(msg): print("%6.1fs  %s" % (time.time() - t0, msg))
    print("building %s (%s): sc %.2f build %.2f, hair %s, beard %s" % (
        name, spec["display"], spec["sc"], spec["look"].get("build", 1.0), hair_style,
        "yes" if pal["beard"] is not None else "no"))

    # ---- 1-3: the body, the face, the hair, the garments
    # The build is the slow stage (nine minutes); it is checkpointed to a .blend
    # so the stages after it can be re-run with --resume.
    CHECK = os.path.join(OUT, "built.blend" if low == "saud" else "built_%s.blend" % low)
    if "--resume" in argv and os.path.exists(CHECK):
        # The cut, the face, the lids, the trunk, the masses, the arms, the
        # ears and the garments' cut are geometry, built before the
        # checkpoint: resuming one built with other numbers would paint
        # this man onto that one (his lash line on another man's lids).
        check_resume(CHECK, kind, name, hair_style, bald)
        bpy.ops.wm.open_mainfile(filepath=CHECK)
        O = bpy.data.objects
        body, tee, pants = O["Body"], O["Tee"], O["Pants"]
        soles = [o for o in O if o.name.startswith("sole")]
        eyes = [o for o in O if o.name.startswith("eyeball")]
        jl = {k: [Vector(p) for p in v] for k, v in json.load(open(CHECK + ".json")).items()}
        body_kinds = ("skin", "hair", "shoe") + (("glove",) if gloves else ())
        mats = {k: bpy.data.materials["%s_%s" % (name, k.capitalize())] for k in body_kinds + ("tee", "pants", "eye")}
        # the checkpoint carries the materials as they were built; the
        # pore bump is the one dial that is tuned after seeing a bake
        # ...and the skin's scattering, which is tuned after seeing a render
        F.skin_scatter(mats["skin"], SKIN_SSS)
        for k, strength in PORES.items():
            for n in mats[k].node_tree.nodes:
                if n.type == 'BUMP': n.inputs["Strength"].default_value = strength
        slots = {k: i for i, k in enumerate(body_kinds)}
        stamp("resumed from %s" % CHECK)
    else:
        body, trees, eyes, jl = B.build(voxel_scale=3.0 if "--coarse" in argv else 1.0,
                                        face_scale=face_scale, hair_style=hair_style, arm_scale=arm_scale,
                                        gloves=gloves, physique=PHYSIQUE.get(kind), mass=MASS.get(kind),
                                        noses=NOSES.get(kind), ears=EARS.get(kind), holds=HOLDS.get(kind))
        slots = {}
        mats = {"skin": F.shader("%s_Skin" % name, "skin", 0.52, subsurface=SKIN_SSS, pores=PORES["skin"]),
                # the hair's roughness matches the skin's: the material edge
                # is a staircase of faces, and a roughness step would show it
                "hair": F.shader("%s_Hair" % name, "hair", 0.52, pores=PORES["hair"]),
                "shoe": F.shader("%s_Shoe" % name, "shoe", 0.45, coat=0.2, weave=0.15)}
        if gloves:
            # ZAYOS: leather/vinyl, not skin or fabric -- a step glossier
            # than the shoe's own coat, no weave (a boxing glove has no weft).
            mats["glove"] = F.shader("%s_Glove" % name, "glove", 0.40, coat=0.25)
        body_kinds = ("skin", "hair", "shoe") + (("glove",) if gloves else ())
        for k in body_kinds:
            body.data.materials.append(mats[k]); slots[k] = len(body.data.materials) - 1
        B.assign_by_source(body, trees, slots)
        for p in body.data.polygons:
            if p.center.z < 0.118 and abs(p.center.x) > 0.02: p.material_index = slots["shoe"]
        if gloves:
            # The glove is unioned over the fist at the hand's own fine
            # pass (assembly.build), so it and the fingers it hides already
            # share the body mesh; assign_by_source only knows "skin" and
            # "hair" and puts all of it in "skin". Reassign by the same
            # (d, n, w) hand frame anatomy.glove() was built in: a cylinder
            # around the hd->he segment, wide enough for the glove's own
            # widest row (0.060 m half-width at t=0.42) plus the thumb lobe,
            # a little past the cuff (t=-0.38) and the closed tip (t=0.96).
            L = 0.135
            for s in (1, -1):
                hd = Vector((A.Jp("hand_l").x * s, A.Jp("hand_l").y, A.Jp("hand_l").z))
                he = Vector((A.Jp("hand_end_l").x * s, A.Jp("hand_end_l").y, A.Jp("hand_end_l").z))
                d = (he - hd).normalized()
                lo = hd + d * (-0.42 * L); hi_ = hd + d * (1.02 * L)
                # ...and the sleeve over the thumb (anatomy.glove), which
                # reaches past that cylinder: its tip is 0.100 off the axis
                th = [Vector((q.x * s, q.y, q.z)) for q in jl["thumb"]]
                reach = 0.0150 + A.GLOVE_THUMB_PAD + 0.012
                for p in body.data.polygons:
                    if G._pt_seg(p.center, lo, hi_) < 0.075 or \
                       any(G._pt_seg(p.center, a, b) < reach for a, b in zip(th[:-1], th[1:])):
                        p.material_index = slots["glove"]
        tee, pants, soles = G.dress(body, tee=not no_tee)
        mats["tee"] = F.shader("%s_Tee" % name, "tee", 0.88, sheen=0.35, weave=0.22)
        mats["pants"] = F.shader("%s_Pants" % name, "pants", 0.82, sheen=0.20, weave=0.16)
        mats["eye"] = F.shader("%s_Eye" % name, "eye", 0.08, coat=1.0)
        tee.data.materials.append(mats["tee"]); pants.data.materials.append(mats["pants"])
        for o in soles: o.data.materials.append(mats["shoe"])
        for e in eyes: e.data.materials.append(mats["eye"])
        stamp("built: body %d tris, tee %d, pants %d" % (sum(len(p.vertices) - 2 for p in body.data.polygons),
              len(tee.data.polygons), len(pants.data.polygons)))
        json.dump({k: [list(p) for p in v] for k, v in jl.items()}, open(CHECK + ".json", "w"))
        # the one pre-checkpoint stamp (check_resume); .hair is still written
        # for a checkpoint read by a pipeline older than the stamp
        json.dump(man, open(CHECK + ".man", "w"), indent=1, sort_keys=True)
        open(CHECK + ".hair", "w").write(hair_style + "\n")
        bpy.ops.wm.save_as_mainfile(filepath=CHECK)

    # ---- the body under the garments is never seen and pokes through after
    # decimation, so it goes; a band is kept inside every hem.
    def under_garments(c, seen=True):
        # to 1.50, not 1.53: the collar ring's lowest point is at 1.507, and a
        # strip that ran to 1.53 left the tee's black inside showing through
        # the 26 mm between the ring and the neck in every face render.
        # ZAYOS (no_tee) has no tee at all -- bare-chested and bare-armed --
        # so none of this strips: the skin there is what is seen.
        #
        # The scan of 2026-09-28 looked up the sleeves and in at the collar:
        # the fit hangs both off the body now, and where they stand off it
        # the stripped edge of the skin showed -- a hole into the tee's dark
        # inside. The skin is kept for 12 cm round the neck above 1.45 and
        # down the upper arm from a tenth of its length (0.30 before); what
        # is stripped is what nothing can see.
        if no_tee: return 0.16 <= c.z <= 1.04 and G.pants_region(c)
        if (1.10 <= c.z <= 1.50 and abs(c.x) < 0.24 and G.tee_region(c)
                and not (seen and c.z > 1.45 and math.hypot(c.x, c.y - 0.004) < 0.12)): return True
        if 0.16 <= c.z <= 1.04 and G.pants_region(c): return True
        for s in (1, -1):
            sh = Vector((A.Jp("upperarm_l").x * s, A.Jp("upperarm_l").y, A.Jp("upperarm_l").z))
            el = Vector((A.Jp("lowerarm_l").x * s, A.Jp("lowerarm_l").y, A.Jp("lowerarm_l").z))
            t = (c - sh).dot(el - sh) / (el - sh).length_squared
            if -0.25 < t < (0.10 if seen else 0.30) and G._pt_seg(c, sh, el) < 0.095 and c.z > 1.30: return True
        return False
    import bmesh
    def strip_body(body, drop_idx):
        bm = bmesh.new(); bm.from_mesh(body.data); bm.faces.ensure_lookup_table()
        drop = [bm.faces[i] for i in drop_idx]
        bmesh.ops.delete(bm, geom=drop, context='FACES'); bm.to_mesh(body.data); bm.free()
        return len(drop)
    # the stripped share is spent on the face and hands instead
    # ...counted as the strip ran before the collar and sleeve skin was kept
    # (seen=False): the few hundred triangles that kept cost nothing, and
    # the smaller budget they made took every shoe face -- the collapse
    # takes the shoes first and all at once (the scan's rebuild, 2026-09-28)
    covered = sum(1 for p in body.data.polygons if under_garments(p.center, seen=False)) / max(1, len(body.data.polygons))

    # ---- the sources: the surfaces before decimation, kept for the bake
    def keep_copy(o, name_):
        c = o.copy(); c.data = o.data.copy(); c.name = name_; bpy.context.collection.objects.link(c); c.hide_render = True; return c
    hi = {"body": keep_copy(body, "Body_hi"), "tee": keep_copy(tee, "Tee_hi"), "pants": keep_copy(pants, "Pants_hi")}

    # ---- 4: the budget. Face and hands keep their density.
    from . import sculpt as SC
    def precious(co):
        if co.z > 1.556 and co.y < 0.03:                                  # the face
            # but not the eye region's subdivision (assembly.subdivide_eyes)
            # away from the lid margins: 33,000 protected triangles of
            # smooth lid and orbit starved the rest of the body until the
            # shoes collapsed to nothing. The lid margins keep their 0.4 mm;
            # assembly.relax_eyes has already collapsed the rest.
            ax = abs(co.x)
            if (B.EYE_BOX[0] < ax < B.EYE_BOX[1] and abs(co.z - SC.EYE_Z) < B.EYE_BOX[2]
                    and not SC.near_margin(ax, co.z)):
                return False
            return True
        # A glove is a smooth pad and needs none of a hand's density. Kept
        # anyway, ZAYOS's two gloves were 62,720 triangles of the 469,576,
        # the rest of him went into the collapse at 3 % to pay for them, and
        # at 3 % both shoes collapsed to no faces at all.
        if gloves: return False
        for s in (1, -1):
            wr = Vector((A.Jp("hand_l").x * s, A.Jp("hand_l").y, A.Jp("hand_l").z))
            if (co - wr).length < 0.22 and co.z < 1.10: return True         # the hands
        return False
    budget = {"body": int(BUDGET * 0.66 / max(0.3, 1.0 - covered)), "tee": int(BUDGET * 0.16), "pants": int(BUDGET * 0.14)}
    tris = {}
    tris["body"] = F.decimate(body, budget["body"], precious)
    tris["tee"] = F.decimate(tee, budget["tee"], lambda c: False, boundary_rings=2)      # the collar and the hems stay curves
    tris["pants"] = F.decimate(pants, budget["pants"], lambda c: False, boundary_rings=2)
    for o in soles + eyes: tris[o.name] = sum(len(p.vertices) - 2 for p in o.data.polygons)
    stamp("decimated: " + "  ".join("%s %d" % kv for kv in tris.items())
          + "  (shoe faces %d)" % sum(1 for p in body.data.polygons if p.material_index == slots["shoe"]))
    # the eyes again, on what the collapse left: a lid it thinned must still
    # close over the globe and the fissure must still be open
    shown, leak = B.check_eye_open(body, eyes)
    stamp("eyes after decimation: globe over %.0f %% of the fissure, %.1f %% outside the lids" % (shown * 100, leak * 100))
    # every material the body carries still has faces to bake -- said here,
    # rather than as a bake that finds nothing ten minutes later
    left = {k: sum(1 for p in body.data.polygons if p.material_index == i) for k, i in slots.items()}
    empty = [k for k, n in left.items() if n == 0 and not (k == "hair" and bald)]
    assert not empty, "decimation left no %s faces on %s (%s)" % ("/".join(empty), name, left)
    # The faces under the garments, decided HERE, at the canonical
    # coordinates every region test was written for. They are deleted after
    # the bind (bone heat wants the closed body), by which time the body has
    # been taken to the man's own size and `under_garments` would be asking
    # about a tee that is no longer where its constants say.
    hidden_faces = [p.index for p in body.data.polygons if under_garments(p.center)]

    # ---- UVs and paint
    charts = F.body_charts()
    for o in (body, tee): F.assign_uvs(o, charts)
    F.assign_uvs(pants, F.pants_charts())
    # The hair's faces sit on the head cylinder's chart, a strip across the
    # top of it, and bake into their OWN image: measured, 527 x 87 texels of
    # a 1024 map -- 4.4 % of it, 1.2 mm a texel, 2.3 in the normal. The
    # crown read as 2-3 mm lumps. Stretch the hair's loops over its whole
    # image (the same 0.02 / 0.96 inset assign_uvs leaves for the margin).
    # Done here, before the per-material copies below, so the hair-only
    # bake object and the exported mesh carry the same UVs.
    uvl = body.data.uv_layers.active.data
    hl = [li for p in body.data.polygons if p.material_index == slots["hair"] for li in p.loop_indices]
    if hl:
        us = [uvl[li].uv.x for li in hl]; vs = [uvl[li].uv.y for li in hl]
        u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)
        for li in hl:
            u, v = uvl[li].uv
            uvl[li].uv = (0.02 + 0.96 * (u - u0) / max(u1 - u0, 1e-9), 0.02 + 0.96 * (v - v0) / max(v1 - v0, 1e-9))
    for o in soles:
        # the tread and the top top-down; the rim -- vertical, so a top-down
        # projection flattened each of its faces to a line (124 faces, the
        # scan, 2026-09-28) -- round the sole in a strip of its own
        zs = [v.co.z for v in o.data.vertices]; zlo, zhi = min(zs), max(zs)
        ctr = sum((v.co for v in o.data.vertices), Vector()) / len(o.data.vertices)
        F.assign_uvs(o, [(lambda c, zlo=zlo, zhi=zhi: zlo + 0.25 * (zhi - zlo) < c.z < zhi - 0.25 * (zhi - zlo), "cyl",
                          (Vector((ctr.x, ctr.y, zlo)), Vector((ctr.x, ctr.y, zhi)), Vector((0, -1, 0)), 0.0, 1.0),
                          (0.5, 0.40, 0.75, 0.5) if ctr.x > 0 else (0.75, 0.40, 1.0, 0.5)),
                         (lambda c: True, "planar", (Vector((o.location.x, -0.07, 0.01)), Vector((1, 0, 0)), Vector((0, 1, 0)), 0.32), (0.5, 0.0, 1.0, 0.40))])
    for e in eyes:
        ec = sum((v.co for v in e.data.vertices), Vector()) / len(e.data.vertices)    # the primitive keeps its verts in world space
        F.assign_uvs(e, [(lambda c: True, "cyl", (ec + Vector((0, 0, -0.02)), ec + Vector((0, 0, 0.02)), Vector((0, -1, 0)), 0.0, 1.0), (0, 0, 1, 1))])
    F.paint(body, "skin", jl, pal)
    # the body has three materials but one colour attribute: hair and shoe faces repaint their verts
    # (a fourth, glove, when ZAYOS)
    over_kinds = ("hair", "shoe") + (("glove",) if gloves else ())
    over_verts = {k: set(i for p in body.data.polygons if p.material_index == slots[k] for i in p.vertices) for k in over_kinds}
    import numpy as np
    attr = body.data.color_attributes["Col"]
    n = len(body.data.vertices); col = np.empty(n * 4); attr.data.foreach_get("color", col); col = col.reshape(n, 4)
    tmpb = body.copy(); tmpb.data = body.data.copy()
    for k in over_kinds:
        F.paint(tmpb, k, jl, pal)
        c = np.empty(n * 4); tmpb.data.color_attributes["Col"].data.foreach_get("color", c); c = c.reshape(n, 4)
        for i in over_verts[k]: col[i] = c[i]
    bpy.data.meshes.remove(tmpb.data)
    attr.data.foreach_set("color", col.reshape(-1))
    F.paint(tee, "tee", jl, pal); F.paint(pants, "pants", jl, pal)
    for o in soles: F.paint(o, "shoe", jl, pal)
    for e in eyes: F.paint(e, "eye", jl, pal)
    # the high-resolution sources take the same paint
    def paint_body(b):
        F.paint(b, "skin", jl, pal)
        ov = {k: set(i for p in b.data.polygons if p.material_index == slots[k] for i in p.vertices) for k in over_kinds}
        at = b.data.color_attributes["Col"]; nn = len(b.data.vertices)
        c = np.empty(nn * 4); at.data.foreach_get("color", c); c = c.reshape(nn, 4)
        tb = b.copy(); tb.data = b.data.copy()
        for k in over_kinds:
            F.paint(tb, k, jl, pal)
            cc = np.empty(nn * 4); tb.data.color_attributes["Col"].data.foreach_get("color", cc); cc = cc.reshape(nn, 4)
            for i in ov[k]: c[i] = cc[i]
        bpy.data.meshes.remove(tb.data)
        at.data.foreach_set("color", c.reshape(-1))
    paint_body(hi["body"]); F.paint(hi["tee"], "tee", jl, pal); F.paint(hi["pants"], "pants", jl, pal)
    stamp("painted and unwrapped")

    # ---- bake: one image set per material, through each object's own UVs.
    # The body carries three materials whose charts overlap in UV space (each
    # is its own island layout), so each material bakes from a copy of the body
    # holding only its faces.
    def only(obj, slot):
        c = obj.copy(); c.data = obj.data.copy(); bpy.context.collection.objects.link(c)
        import bmesh
        bm = bmesh.new(); bm.from_mesh(c.data)
        drop = [f for f in bm.faces if f.material_index != slot]
        bmesh.ops.delete(bm, geom=drop, context='FACES'); bm.to_mesh(c.data); bm.free()
        return c
    baked = {}
    base_of = {"skin": "%s_Skin" % name, "hair": "%s_Hair" % name, "shoe": "%s_Shoe" % name,
               "tee": "%s_Tee" % name, "pants": "%s_Pants" % name, "eye": "%s_Eye" % name,
               "glove": "%s_Glove" % name}
    # Hair and shoe at half the skin's size, not a quarter: at TEX // 4 the
    # hair's normal map was 512 px over a 0.041 m2 chart -- 2.3 mm a texel,
    # with a pore-scale bump baked into it -- and the crown read as blotches
    # in every render (measured on rigs/Saud.blend: hair 1.16 mm albedo /
    # 2.3 mm normal, shoe 0.96 / 1.9, against the skin's 0.35). Half size
    # puts them at 0.58 / 1.16 and 0.48 / 0.96.
    # bald: no face is ever assigned the hair material (hair_parts returned
    # no geometry), so only(body, slots["hair"]) is empty and baking it
    # would be baking nothing -- skipped, not attempted and ignored.
    bake_list = [("skin", only(body, slots["skin"]), TEX)]
    if not bald:
        bake_list.append(("hair", only(body, slots["hair"]), max(1024, TEX // 2)))
    bake_list += [("shoe", None, max(1024, TEX // 2))]
    # no_tee: the Tee object is real but empty (garments.dress's own case,
    # the same shape as hair above) -- nothing to bake.
    if not no_tee:
        bake_list.append(("tee", tee, TEX))
    bake_list += [("pants", pants, TEX), ("eye", eyes[0], 512)]
    if gloves:
        bake_list.append(("glove", only(body, slots["glove"]), max(1024, TEX // 2)))
    for key, obj, size in bake_list:
        if key == "shoe":
            obj = only(body, slots["shoe"])
            # the soles bake into the same images below: same material, own charts
        source = {"skin": hi["body"], "hair": hi["body"], "shoe": hi["body"], "glove": hi["body"],
                  "tee": hi["tee"], "pants": hi["pants"]}.get(key)
        baked[key] = F.bake_set(obj, mats[key], size, UE5_TEX, base_of[key],
                                maps=("albedo", "normal", "roughness") if key != "eye" else ("albedo", "roughness"), source=source,
                                # The skin's normal is the only one carrying authored
                                # structure rather than pore dither, and at half size a
                                # face texel is 1.36 x 2.00 mm -- the mouthline is 0.9 mm
                                # and the lash bar 1.6, so both sat at or under one texel
                                # in the direction that matters. Full size for the skin,
                                # half for everything else, where the comment in bake_set
                                # about dither still holds.
                                normal_size=(size if key == "skin" else max(512, size // 2)))
        if key == "shoe":
            # the soles: the same material, their own charts (u > 0.5, v < 0.5),
            # baked into the same three images from their own paint. Without
            # this that quadrant stayed black -- colour black, roughness 0 --
            # and every sole shipped as a mirror.
            for o in soles:
                F.bake_set(o, mats["shoe"], size, UE5_TEX, base_of["shoe"], source=None, images=baked["shoe"],
                           normal_size=max(512, size // 2))
        if key == "eye":
            # Same reason as the face: the iris is 11 mm across and the limbal
            # ring 0.4 mm, against 2.8 degrees between the globe's vertices.
            import numpy as _np
            ctr = _np.array([v.co[:] for v in obj.data.vertices]).mean(axis=0)
            stamp("repainted %d eye texels" % F.repaint_eye(obj, baked[key], size, ctr, B.EYE_R))
        if key == "skin":
            # The whole skin first, per texel: the body's grain at the
            # texture's resolution rather than the vertices' (0.35 mm pores,
            # not 3 mm), and the kit on it -- the wraps' turns, the nails --
            # from finish.kit_colour, the edges a texel wide. Then the head
            # over it, so its feather down the neck lands on that grain.
            stamp("repainted %d skin texels (grain, wraps, nails)" % F.repaint_kit(obj, "skin", baked[key], size, pal, jl))
            # The bake can only carry what the vertices hold, and the head has
            # 3.1 mm between vertices against a 0.28 mm texel. Repaint the face
            # from hero.face at the texture's own resolution.
            painted, relief = F.repaint_head(obj, baked[key], size, pal)
            assert painted > 0, "the face repaint wrote nothing -- the head chart did not rasterise"
            stamp("repainted %d face texels, relief %.2f coherent levels in the normal" % (painted, relief))
        if key in ("tee", "pants", "shoe", "glove", "hair"):
            # the garments' edges -- patch, collar, waistband, stripe, the
            # shoe's bars -- per texel, from the same description the vertex
            # paint came from (finish.kit_colour). The glove is a solid
            # fill (kit_colour's kit is 1.0 everywhere for it, same as the
            # other garments), so it rebuilds whole the same way. The hair
            # since 2026-09-26: its strands, clumps, fade, relief and
            # roughness are per texel (face.hair_strands); it had only the
            # vertex paint the bake carried, 3 mm between vertices.
            stamp("repainted %d %s texels" % (F.repaint_kit(obj, key, baked[key], size, pal, jl), key))
        if obj not in (tee, pants) and obj not in eyes: bpy.data.objects.remove(obj, do_unlink=True)
        stamp("baked %s at %d" % (key, size))
    # bald: "hair" was never baked (no faces to bake), so the material
    # keeps its procedural nodes -- harmless, since nothing is assigned it.
    for k, m in mats.items():
        if k in baked: F.wire_textures(m, baked[k])
    for o in hi.values(): bpy.data.objects.remove(o, do_unlink=True)

    # ---- his own size. Everything above ran at Saud's coordinates; from
    # here on the mesh and the joints are the man's.
    across0, gap0 = G.check_legs_apart(pants, 0.910, assert_=False)
    factors = A.scale_to([body, tee, pants] + soles + eyes, jl, spec["sc"], spec["look"].get("build", 1.0))
    print("cloth     : at Saud's size %d faces across, nearest %.1f mm" % (across0, gap0 * 1000))
    across, gap = G.check_legs_apart(pants, factors.get("crotch", {}).get("z_centre", 0.910))
    print("cloth     : trouser legs apart below the crotch (%d faces across, nearest %.1f mm off the midline)" % (across, gap * 1000))

    # ---- rig
    rig = legacy.build_armature()
    rig.name = "%s_Rig" % name
    if low == "saud":
        # The boss clips in Content/Animation/Bosses are keyed to the
        # skeleton build_armature makes from the joint table as it is. Saud
        # goes through the same field as everyone else at factors of one, so
        # his skeleton must come out exactly that one -- checked, not assumed.
        ref = legacy.build_armature(); ref.name = "Reference_Rig"
        worst = max((rig.data.bones[b.name].head_local - b.head_local).length for b in ref.data.bones)
        worst = max(worst, max((rig.data.bones[b.name].tail_local - b.tail_local).length for b in ref.data.bones))
        assert {b.name for b in rig.data.bones} == {b.name for b in ref.data.bones} and worst < 1e-6, \
            "Saud's skeleton drifted %.2e m from the one the boss clips are keyed to" % worst
        bpy.data.objects.remove(ref, do_unlink=True)
        stamp("skeleton identical to the boss clips' (drift %.1e m)" % worst)
    nf = R.add_finger_bones(rig, jl)
    R.bind_all(body, [tee, pants] + soles + eyes, rig, factors.get("crotch"))
    stamp("stripped %d body faces under the garments" % strip_body(body, hidden_faces))
    mesh = R.join_all(body, [tee, pants] + soles + eyes); mesh.name = mesh.data.name = name
    legacy.weight_orphans(mesh, rig)
    legacy.add_ik(rig)
    stamp("rigged: %d bones (%d finger)" % (len(rig.data.bones), nf))

    # ---- poses and renders. The poses are always struck (the report they
    # print is a check); --no-render skips the four Cycles renders.
    legacy.build_studio()
    look_z = 0.90 * factors["h"]
    # The documentation renders were the pixelation a viewer saw: 2.8 mm a
    # pixel on the body shots and 0.68 on the face, over 0.28-0.55 mm
    # texels. Twice the size at full quality (1.1 mm / 0.24 mm a pixel);
    # --fast keeps the old size. About 3.5-4x the render time, ~15 min.
    scale = 1 if FAST else 2
    def shot(filename, cam, look_at, lens, res=(760 * scale, 1000 * scale)):
        if "--no-render" in argv: return
        legacy.add_camera(cam, look_at=Vector(look_at), lens=lens)
        legacy.render(os.path.join(RENDERS, "%s-%s-3d.png" % (low, filename)), samples=24 if FAST else 64, res=res)
    guard = legacy.guard_for(low)          # Saud's is the MMA stance
    targets, poles, report = legacy.limb_targets(rig, mesh, guard, plant=("l", "r"))
    legacy.print_pose_report("guard", ("l", "r"), report)
    legacy.pose(rig, guard, targets, poles, drop=report.get("body_drop", 0.0)); R.close_fists(rig)
    # the camera stands back as far as the man is tall (the scan, 2026-09-28:
    # at Saud's distance ZAYOS's head was out of the top of every body shot)
    hh, hk = factors["h"], factors.get("head", 1.0)
    shot("guard", (1.55 * hh, -3.35 * hh, 1.24 * hh), (0, 0, look_z), 62)
    targets, poles, report = legacy.limb_targets(rig, mesh, legacy.KICK, plant=("l",))
    legacy.print_pose_report("kick", ("l",), report)
    legacy.pose(rig, legacy.KICK, targets, poles, drop=report.get("body_drop", 0.0)); R.close_fists(rig)
    shot("kick", (3.00 * hh, -2.45 * hh, 1.22 * hh), (0.14 * hh, 0, 0.96 * hh), 58)
    legacy.mute_ik(rig, True); legacy.pose(rig, {}); R.close_fists(rig, 0.0)
    shot("apose", (0.35 * hh, -3.60 * hh, 1.05 * hh), (0, 0, look_z), 58)
    # lens 85 -> 120 at the same aim: the head fills 69 % of the frame
    # instead of 49 (the crown's ray at 0.141 * 120 = 16.9 mm stays inside
    # the 18 mm half-sensor), 0.24 mm a pixel at 2x -- under the texel
    shot("face", (0.62 * hk, -1.05 * hk, 1.60 * hh), (0, 0, 1.62 * hh), 120, res=(760 * scale, 760 * scale))
    legacy.mute_ik(rig, False)
    stamp("posed" if "--no-render" in argv else "rendered")

    # ---- the control rig, the animator's file, then the verification. The
    # file is saved BEFORE verify() so that a rig that fails its own checks
    # is on disk to be looked at, not gone with the process.
    control = None
    blend = os.path.join(RIGS, "%s.blend" % name)
    if "--no-control-rig" not in argv:
        import rig_full_ik as CR
        control = CR.build(rig, mesh)
        bpy.ops.wm.save_as_mainfile(filepath=blend)
        stamp("saved %s" % blend)
        CR.verify(rig, mesh, scale=factors["h"])
        stamp("control rig: %d control bones, verified" % control["controls"])
    else:
        bpy.ops.wm.save_as_mainfile(filepath=blend)
        stamp("saved %s" % blend)

    # ---- export, then read it back. The control layer never leaves: what
    # ships is the mannequin's skeleton exactly, or the retarget breaks.
    if control:
        CR.strip_for_export(rig, mesh)
    names = {b.name for b in rig.data.bones}
    assert names == MANNEQUIN, "the export skeleton is not the mannequin's: extra %s, missing %s" % (
        sorted(names - MANNEQUIN), sorted(MANNEQUIN - names))
    # One skeleton, one name. An engine keys a shared skeleton on the FBX's
    # armature node as well as its bone names, and the boss clips left as
    # Saud_Rig; every man exports under it, whatever his .blend calls him.
    rig.name = "Saud_Rig"; rig.data.name = "SaudSkeleton"
    total = sum(len(p.vertices) - 2 for p in mesh.data.polygons)
    gltf, fbx, ufbx = R.export_all(rig, mesh, UE5_MODELS, UNITY_MODELS, UE5_TEX, None, name=name)
    summary = dict(name=name, kind=spec["kind"], sc=spec["sc"], build=spec["look"].get("build", 1.0),
                   factors=factors, tris=total, verts=len(mesh.data.vertices), bones=len(rig.data.bones), finger_bones=nf,
                   materials=[m.name for m in mesh.data.materials], textures=sorted(os.listdir(UE5_TEX)),
                   gltf=os.path.getsize(gltf), fbx=os.path.getsize(fbx),
                   unity_fbx=os.path.getsize(ufbx) if ufbx else None,
                   control_rig=control, man=man)
    stamp("exported: %d tris, %d bones%s" % (total, summary["bones"],
                                             "" if ufbx else "  (Unreal only; --unity adds the Unity FBX)"))
    summary["roundtrip_gltf"] = R.verify_roundtrip(gltf)
    back = R.gltf_bone_names(gltf)
    assert back == MANNEQUIN, "the glTF's skeleton is not the mannequin's: %s" % sorted(back ^ MANNEQUIN)[:8]
    if ufbx:
        summary["roundtrip_fbx_unity"] = R.verify_roundtrip(ufbx)
    json.dump(summary, open(os.path.join(OUT, "%s_summary.json" % low), "w"), indent=1)
    if low == "saud":
        json.dump(summary, open(os.path.join(OUT, "summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))
    stamp("done")
    return summary
