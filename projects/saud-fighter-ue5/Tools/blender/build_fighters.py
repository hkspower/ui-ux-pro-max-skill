#!/usr/bin/env python3
"""The fighters of the first area -- and the hero -- built, rigged, exported.

    python3 build_fighters.py                  saud, thug, brawler: the lot
    python3 build_fighters.py thug brawler     some of them
    python3 build_fighters.py --fast           1K textures, quick renders
    python3 build_fighters.py --coarse         a rough body, to check the stages
    python3 build_fighters.py --check          the roster and the palette only
    python3 build_fighters.py --hair-check     every cut's geometry checked, and the check bitten
    python3 build_fighters.py --nose-check     every man's nose (FACES, NOSES): profile, widths about its crest, bitten
    python3 build_fighters.py --eye-check      the eye's shape (every man's lids, Saud's hooded) and the open eye on a built head, bitten
    python3 build_fighters.py --head-check     the skull and neck tables, and the check bitten
    python3 build_fighters.py --neck-check     the neck and its join to the shoulders on the built base, bitten
    python3 build_fighters.py --back-check     the lats, the V and the spinal furrow on the built base, bitten
    python3 build_fighters.py --cloth-check    the tee and trousers' drape, folds and clearance, bitten; Saud's
                                               tank and joggers, bitten; the tank men's checkpoints (shoe floor,
                                               holes, tank UVs) through --resume [--checkpoints DIR]
    python3 build_fighters.py --face-check     factor(), every man's real body under check_mien, Saud's scowl,
                                               the --resume guard through the --resume branch, bitten
    python3 build_fighters.py --physique-check every man's real body, Saud's lean physique, and the neck and
                                               back suites on the lean base, bitten
    python3 build_fighters.py --grim-check     the five men's kit, every man's paint, the bodies MASS / LIMBS
                                               make, every jaw, the cauliflower ears, bitten
    python3 build_fighters.py --fabric-check   the cloth's roughness per cut (the jogger, the compression top), bitten
    python3 build_fighters.py --vein-check     every man's forearm veins, Saud's hold, bitten
    python3 build_fighters.py --out DIR        write somewhere else than the project

WHO. SOUQ AL-DAWAR's three waves are thugs and brawlers (DT_Stages.json,
stage 0), and Saud walks into them. Those are the three men here. Every
number that says what one of them looks like is read out of the browser
build's roster -- assets/saud.js, assets/enemies.js -- by hero/roster.py:
the colours, the kit, `sc` and `build`. DT_Fighters.csv carries none of
that (../../CLAUDE.md, "Known, not fixed"), which is why the roster is read
rather than the table.

HOW. One body, every man: hero/pipeline.build_fighter runs the hero
pipeline for a spec, at Saud's coordinates up to the bake, then takes the
finished mesh and its joints to the man's own size through the browser
build's own sc / build mapping (hero/anatomy.scale_to), builds the
mannequin's skeleton on it, the full IK control rig over that, verifies
the rig, saves the animator's .blend, strips the control layer and exports
exactly the mannequin's 62 bones.

ONE PROCESS PER MAN. The hero modules hold module state -- the joint table,
the face layout, the skull rows, and since 2026-09-28 a man's lids,
trunk and paint (pipeline.apply_man: sculpt.set_eye, anatomy.set_physique,
face.set_look) -- and a
man's build mutates the joints. Each fighter is built in its own
interpreter so nothing carries over; a suite that builds several men's
heads or bodies in one process resets the state itself.
"""
import os, sys, json, time, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROSTER = ("saud", "thug", "brawler")


def check(kinds):
    """The roster reads, and Saud's derived palette lands where his hand-typed
    one did -- except the beard, which is now the browser's wash over his
    skin rather than a shade somebody chose, and that is reported."""
    from hero import roster, finish as F
    import numpy as np
    for k in kinds:
        s = roster.spec(k)
        assert s["look"].get("pants"), "%s: this pipeline dresses trousers on every man" % k
        assert s["look"].get("hands") in (None, "bare", "wraps", "gloves"), "%s: no %s hands in this pipeline" % (k, s["look"].get("hands"))
        print("  %-8s %-10s sc %.2f build %.2f  skin %s top %s bottom %s band %s  hands %s  beard %s" % (
            s["name"], s["display"], s["sc"], s["look"].get("build", 1.0), s["col"]["skin"], s["col"]["top"],
            s["col"]["bottom"], s["col"]["band"], s["look"].get("hands"), "yes" if s["look"].get("beard") else "no"))
    new, old = F.palette_for(roster.spec("saud")), F.saud_palette()
    same = [k for k in ("skin", "hair", "tee", "pants", "band", "shoe") if np.allclose(new[k], old[k])]
    assert len(same) == 6, "Saud's palette drifted from what paint() always used: %s" % (set("skin hair tee pants band shoe".split()) - set(same))
    print("  Saud's palette, read from the browser, equals the one that was typed: skin hair tee pants band shoe")
    print("  beard: typed %s -> read %s (the browser's rgba wash over his skin)" % (
        tuple(round(float(v), 4) for v in old["beard"]), tuple(round(float(v), 4) for v in new["beard"])))
    for k in ("tape_on", "patch", "stripe", "watch"):
        assert new[k] == old[k], "Saud's kit drifted: %s" % k


def one(kind, argv):
    """Build one man, in this process."""
    from hero import roster, pipeline
    return pipeline.build_fighter(roster.spec(kind), argv)


def hair_check():
    """--hair-check: every cut through assembly.check_hair, clean, and each
    of its four rules broken once to prove it bites (2026-09-26): a part
    over HAIR_TOP, a shell with no taper (the step at the hairline, the
    rope in every face render), a lock thinner than 2.5 voxels (AL-SAQR's
    shards), and nothing over the crown. bpy as a module, a few seconds."""
    import build_saud as legacy
    from hero import assembly as ASM
    styles = [s for s in ASM.HAIR_STYLES if s not in ("bald", "crop")]
    for style in styles:
        legacy.reset_scene()
        top = ASM.check_hair(ASM.hair_parts(style), style)
        print("  %-8s clean   top %.4f" % (style, top))

    def over(parts):
        for v in parts[0].data.vertices: v.co.z += 0.006     # the whole volume, 6 mm up
        return parts
    def no_taper(parts):
        return [ASM.hair_shell(0.0040, taper=False)] + parts[1:]
    def thin(parts):
        return parts + [ASM.ellipsoid("quiff_lock", (0.0, -0.05, 1.785), (0.008, 0.0025, 0.012))]
    def bald_top(parts):
        # only what stays under 1.790: the crown left bare
        return [o for o in parts if max(v.co.z for v in o.data.vertices) < 1.790]
    bites = [("above the line", over, "above"), ("no taper", no_taper, "step"),
             ("thin lock", thin, "shards"), ("nothing on top", bald_top, "crown")]
    caught = 0
    for label, bite, word in bites:
        legacy.reset_scene()
        parts = bite(ASM.hair_parts("quiff"))
        try:
            ASM.check_hair(parts, "quiff")
            print("  %-15s NOT caught" % label)
        except AssertionError as e:
            ok = word in str(e)
            caught += ok
            print("  %-15s %s  %s" % (label, "caught" if ok else "WRONG CHECK", e))
    print("  %d of %d hair sabotages caught" % (caught, len(bites)))
    if caught != len(bites):
        sys.exit(1)


def nose_check():
    """--nose-check: every man's face amplitudes and his nose (FACES, NOSES)
    through sculpt.check_profile -- the crest on the midline, projection,
    nasion, bridge, tip, alae measured both sides of the nose's own crest,
    no nostril slot -- then each rule broken once (2026-09-26; the knocked
    nose 2026-09-28). Numpy only."""
    from hero import sculpt, pipeline
    # "the rest" is the table as it stands, every factor 1 (no man since
    # 2026-09-28, when every man got a FACES entry)
    for kind in list(pipeline.FACES) + ["the rest"]:
        scale, shift = sculpt.with_nose(pipeline.FACES.get(kind), pipeline.NOSES.get(kind))
        peak, at, nas = sculpt.check_profile(scale, shift=shift)
        w = sculpt._nose_widths(scale, shift=shift)
        hump, _ = sculpt.dorsum_hump(scale, shift=shift)
        print("  %-8s clean   peak %.1f mm at %.4f, nasion %.4f; bridge %.1f tip %.1f alae %.1f, off the midline %.1f, hump %.2f mm" % (
            kind, peak * 1000, at, nas, w["bridge"] * 1000, w["tip"] * 1000, w["alae"] * 1000, w["deviation"] * 1000, hump * 1000))
    # what each broken, aquiline or flattened nose is for (pipeline.NOSE_LOOKS,
    # sculpt.check_nose, 2026-09-28): clean, then each man without his NOSES
    # entry -- the shared straight nose -- must be refused by his own look
    bad = []
    for kind, looks in pipeline.NOSE_LOOKS.items():
        try:
            n = sculpt.check_nose(*sculpt.with_nose(pipeline.FACES.get(kind), pipeline.NOSES.get(kind)), looks=looks)
            print("  %-8s clean   %s: off the midline %.2f mm, hump %.2f mm, dorsum %.1f mm at mid-bridge" % (
                kind, looks["looks"], n["deviation"] * 1000, n["hump"] * 1000, n["dorsum"] * 1000))
        except AssertionError as e:
            bad.append(kind); print("  %-8s CLEAN FAILS  %s" % (kind, e))
    caught, total = sculpt.bite()
    for kind, looks in pipeline.NOSE_LOOKS.items():
        total += 1
        try:
            sculpt.check_nose(*sculpt.with_nose(pipeline.FACES.get(kind), None), looks=looks)
            print("  %-13s NOT caught" % ("%s plain" % kind))
        except AssertionError as e:
            ok = ("not %s" % looks["looks"]) in str(e); caught += ok
            print("  %-13s %s  %s" % ("%s plain" % kind, "caught" if ok else "WRONG CHECK", e))
    # the slot measured out both ways from the crest (2026-09-28): the
    # brawler's broken nose with its base left on the midline has a 3 mm
    # slot on its RIGHT, which the old one-sided measure (his left) missed
    left = {k: v for k, v in pipeline.NOSES["brawler"].items() if k not in ("ala", "alar_crease", "nostril")}
    scale, shift = sculpt.with_nose(pipeline.FACES["brawler"], left)
    total += 1
    try:
        sculpt.check_profile(scale, shift=shift)
        print("  %-13s NOT caught" % "base left")
    except AssertionError as e:
        ok = "slot" in str(e); caught += ok
        print("  %-13s %s  %s" % ("base left", "caught" if ok else "WRONG CHECK", e))
    print("  %d of %d nose sabotages caught" % (caught, total))
    if caught != total or bad:
        sys.exit(1)


def eye_check():
    """--eye-check (2026-09-26): the fissure's shape (sculpt.check_eye_shape)
    and each of its rules broken once; then a head built the way the
    pipeline builds one -- the 3.5 mm union, the eye region subdivided, the
    sculpt, the drape, the relax -- through assembly.check_eye_open, clean, with no
    drape (the eye shut behind skin, as it was) and with the lids laid
    behind the globe instead of on it. bpy as a module, about a minute."""
    import build_saud as legacy
    from hero import sculpt, assembly as ASM, anatomy as A
    print("  shape    clean   " + "  ".join("%s %.1f" % (k, v * 1000) for k, v in sculpt.check_eye_shape().items()))
    def with_(**kw):
        old = {k: getattr(sculpt, k) for k in kw}
        for k, v in kw.items(): setattr(sculpt, k, v)
        return old
    # each changes its one thing and keeps the rest: the height the same
    # for staring and asleep, the iris covered right for tall
    shapes = [("wide", dict(X_MED=0.0120), "wide"), ("tall", dict(UP_AT_PUPIL=0.0051, DN_AT_PUPIL=0.0064), "tall"),
              ("staring", dict(UP_AT_PUPIL=0.0058, DN_AT_PUPIL=0.0038), "staring"),
              ("asleep", dict(UP_AT_PUPIL=0.0034, DN_AT_PUPIL=0.0062), "asleep"),
              ("no tilt", dict(Z_LAT=sculpt.EYE_Z - 0.0008), "tilt"), ("a lens", dict(UP_PEAK=0.5, DN_PEAK=0.5), "almond")]
    caught = 0; total = 0
    def bite(label, word, run):
        nonlocal caught, total
        total += 1
        try:
            run(); print("  %-15s NOT caught" % label)
        except AssertionError as e:
            ok = word in str(e); caught += ok
            print("  %-15s %s  %s" % (label, "caught" if ok else "WRONG CHECK", e))
    for label, kw, word in shapes:
        old = with_(**kw)
        try: bite(label, word, sculpt.check_eye_shape)
        finally: with_(**old)

    # One man's lids (pipeline.EYES, 2026-09-28): each through the shape
    # rules clean, Saud's hooded; then the hooded rules broken, and the open
    # rule proved to still hold every man not marked hooded. set_eye() is
    # the shared lids again after each (module state: one process builds
    # several heads here).
    from hero import pipeline
    try:
        for kind, kw in pipeline.EYES.items():
            sculpt.set_eye(**kw)
            print("  %-8s clean   " % kind + ("hooded " if sculpt.HOODED else "open   ")
                  + "  ".join("%s %.2f" % (k, v * 1000) for k, v in sculpt.check_eye_shape().items()))
        saud = {k: v for k, v in pipeline.EYES["saud"].items() if k != "hooded"}
        lids = [("hooded, open", dict(hooded=True), "not hooded"),
                ("on the pupil", dict(saud, hooded=True, UP_AT_PUPIL=0.0029), "pupil"),
                ("a slit", dict(saud, hooded=True, UP_AT_PUPIL=0.00306, DN_AT_PUPIL=0.00486), "tall"),
                ("Saud's lids open", dict(saud, hooded=False), "asleep"),
                ("thug at .0035", dict(pipeline.EYES["thug"], UP_AT_PUPIL=0.0035), "asleep")]
        for label, kw, word in lids:
            sculpt.set_eye(**kw)
            bite(label, word, sculpt.check_eye_shape)
    finally:
        sculpt.set_eye()
    try:
        sculpt.set_eye(lid=0.003); print("  %-15s NOT caught" % "misspelt lid"); total += 1
    except KeyError as e:
        total += 1; caught += "no such eye number" in str(e)
        print("  %-15s caught  %s" % ("misspelt lid", e))

    def head(drape=True, kind=None):
        legacy.reset_scene()
        base = A.union_remesh([A.head(), A.neck()], 0.006, "Base"); A.smooth(base, 0.40, 3)
        body = A.union_remesh([base] + ASM.face_parts() + ASM.ear(1) + ASM.ear(-1) + ASM.hair_parts("quiff"), 0.0035, "Body")
        A.smooth(body, 0.5, 2)
        ASM.subdivide_eyes(body)
        scale, shift = sculpt.with_nose(pipeline.FACES.get(kind), pipeline.NOSES.get(kind)) if kind else (None, None)
        sculpt.sculpt_face(body, A.head_surface_y, scale=scale, shift=shift)
        A.smooth(body, 0.3, 1)
        if drape:
            sculpt.drape_eyes(body, A.head_surface_y)
            ASM.relax_eyes(body)
        return ASM.check_eye_open(body, ASM.eyeballs())
    shown, leak = head()
    print("  built    clean   globe over %.0f %% of the fissure, %.1f %% outside the lids" % (shown * 100, leak * 100))
    bite("no drape", "shut", lambda: head(drape=False))
    old = with_(LID_UPPER=-0.004, LID_LOWER=-0.004)
    try: bite("lids behind", "lids do not close", head)
    finally: with_(**old)
    # every man's own head -- his face, his nose, his lids, his cut, his
    # ears (_head: apply_man) -- open (2026-09-28)
    for kind in ("saud", "thug", "brawler", "saqr", "boss", "zayos"):
        try:
            shown, leak = ASM.check_eye_open(_head(kind), ASM.eyeballs())
            print("  %-8s clean   globe over %.0f %% of the fissure, %.1f %% outside the lids (%s)" % (
                kind, shown * 100, leak * 100, "hooded" if sculpt.HOODED else "open"))
        except AssertionError as e:
            total += 1; print("  %-8s CLEAN FAILS  %s" % (kind, e))
        finally:
            _reset()
    # Saud's own head, his face and his hooded lids: open clean, and still
    # shut without the drape at his narrower fissure
    try:
        sculpt.set_eye(**pipeline.EYES["saud"])
        shown, leak = head(kind="saud")
        print("  saud     clean   globe over %.0f %% of the fissure, %.1f %% outside the lids" % (shown * 100, leak * 100))
        bite("saud, no drape", "shut", lambda: head(drape=False, kind="saud"))
    finally:
        sculpt.set_eye()
    print("  %d of %d eye sabotages caught" % (caught, total))
    if caught != total:
        sys.exit(1)


def head_check():
    """--head-check (2026-09-26): anatomy.check_head on the skull and neck
    tables, and each of its rules broken once. bpy as a module; no build."""
    from hero import anatomy as A
    print("  skull    clean   " + "  ".join("%s %.1f" % (k, v * 1000) if k not in ("breadth_z", "kink") else "%s %.3f" % (k, v)
                                            for k, v in A.check_head().items()))
    caught, total = A.bite_head()
    print("  %d of %d head sabotages caught" % (caught, total))
    if caught != total:
        sys.exit(1)


def neck_check(lean=False):
    """--neck-check (2026-09-26): anatomy.check_neck on pass one of the
    build -- the base the pipeline unions at 6 mm -- clean, and each of its
    rules broken once by building the base that breaks it: the old
    trapezius (the shelf), a slumped trapezius (the trunk's own shelf shows), a trapezius
    only over the shoulder (the step), no SCM (no notch), the neck column
    a third thicker. `lean` (--physique-check, 2026-09-28): the same on
    Saud's lean base -- his trunk rows and lats, his masses, his arms.
    bpy as a module, a few seconds a base."""
    import build_saud as legacy
    import numpy as np
    from hero import anatomy as A, assembly as ASM, pipeline as P
    ph = P.PHYSIQUE["saud"] if lean else None
    ar = P.LIMBS["saud"] if lean else 1.0
    A.set_physique(ph)
    def base():
        legacy.reset_scene()
        left = A.arm(ar) + A.leg() + [A.shoe()] + ASM.masses(ph, None, ar)
        b = A.union_remesh([A.trunk(), A.neck(), A.head()] + left + [ASM.mirror_x(o) for o in left], 0.006, "Base")
        A.smooth(b, 0.40, 3)
        return np.array([v.co[:] for v in b.data.vertices])
    print("  neck     clean   " + "  ".join("%s %.3f" % kv for kv in A.check_neck(base()).items()))
    muscles, rows = dict(A.NECK_MUSCLES), list(A.NECK_ROWS)
    def old_trap():
        m = dict(muscles); m["trap"] = ("trap", [(0.108, 0.024, 1.470), (0.108, 0.024, 1.506)],
                                        [(0.054, 0.040), (0.054, 0.040)], lambda c: (0.70, -0.10, -0.30))
        return m
    def slumped():
        # the trapezius pulled down 45 mm over the shoulder: a slumped,
        # sloping shoulder -- the neck itself untouched
        n, pts, radii, f = muscles["trap"]
        return dict(muscles, trap=(n, [(x, y, z - (0.045 if x >= 0.07 else 0.0)) for x, y, z in pts], radii, f))
    def no_scm():
        n, pts, radii, f = muscles["scm"]
        return dict(muscles, scm=(n, [(x, 0.030, z) for x, y, z in pts], [(0.004, 0.004)] * len(pts), f))
    def off_the_neck():
        # the trapezius only over the shoulder, none up the neck: the
        # column stands up out of the slope
        n, pts, radii, f = muscles["trap"]
        return dict(muscles, trap=(n, pts[3:], radii[3:], f))
    bites = [("old trapezius", dict(NECK_MUSCLES=old_trap()), "shelf"),
             ("slumped", dict(NECK_MUSCLES=slumped()), "shelf"),
             ("trap off neck", dict(NECK_MUSCLES=off_the_neck()), "column"),
             ("no SCM", dict(NECK_MUSCLES=no_scm()), "notch"),
             ("thick neck", dict(NECK_ROWS=[(z, cy, rx * 1.35, ry * 1.35) for z, cy, rx, ry in rows]), "round")]
    caught = 0
    for label, patch, word in bites:
        saved = {k: getattr(A, k) for k in patch}
        for k, v in patch.items(): setattr(A, k, v)
        try:
            Pb = base()
            if "--verbose" in sys.argv:
                print("    " + "  ".join("%s %.3f" % kv for kv in A.check_neck(Pb, assert_=False).items()))
            A.check_neck(Pb); print("  %-15s NOT caught" % label)
        except AssertionError as e:
            ok = word in str(e); caught += ok
            print("  %-15s %s  %s" % (label, "caught" if ok else "WRONG CHECK", e))
        finally:
            for k, v in saved.items(): setattr(A, k, v)
    print("  %d of %d neck sabotages caught" % (caught, len(bites)))
    if caught != len(bites):
        sys.exit(1)


LEAN_LATS_OUT = 0.030     # back_check(lean=True)'s 'lats out wide' (the canonical base's is 40 mm)
LATS_PROUD = 0.006


def back_check(lean=False):
    """--back-check (2026-09-27): anatomy.check_back on pass one of the
    build, clean, and each rule broken once by the base that breaks it:
    no back muscles at all, the erectors flattened, no lats, the lats
    pushed out past the flank. `lean` (--physique-check, 2026-09-28): the
    same on Saud's lean base, whose lats are already out wide -- pushed
    out 40 mm more they leave the half-width window and fail as 'no lats';
    30 mm puts the bulge in the V. bpy as a module, a few seconds a base."""
    import build_saud as legacy
    import numpy as np
    from hero import anatomy as A, assembly as ASM, pipeline as P
    ph = P.PHYSIQUE["saud"] if lean else None
    ar = P.LIMBS["saud"] if lean else 1.0
    A.set_physique(ph)
    wide = LEAN_LATS_OUT if lean else 0.040
    def base():
        legacy.reset_scene()
        left = A.arm(ar) + A.leg() + [A.shoe()] + ASM.masses(ph, None, ar)
        b = A.union_remesh([A.trunk(), A.neck(), A.head()] + left + [ASM.mirror_x(o) for o in left], 0.006, "Base")
        A.smooth(b, 0.40, 3)
        return np.array([v.co[:] for v in b.data.vertices])
    print("  back     clean   " + "  ".join("%s %.3f" % kv for kv in A.check_back(base()).items()))
    m = dict(A.BACK_MUSCLES)
    bites = [("no back muscles", {}, "furrow"),
             ("flat erectors", dict(m, erector=[(x, z, 0.0005, a) for x, z, p, a in m["erector"]]), "furrow"),
             ("no lats", dict(erector=m["erector"]), "lats"),
             ("lats out wide", dict(m, lat=[(x + wide, z, p + LATS_PROUD, a) for x, z, p, a in m["lat"]]), "V")]
    caught = 0
    for label, patch, word in bites:
        saved = A.BACK_MUSCLES; A.BACK_MUSCLES = patch
        try:
            Pb = base()
            if "--verbose" in sys.argv:
                print("    " + "  ".join("%s %.3f" % kv for kv in A.check_back(Pb, assert_=False).items()))
            A.check_back(Pb); print("  %-15s NOT caught" % label)
        except AssertionError as e:
            ok = word in str(e); caught += ok
            print("  %-15s %s  %s" % (label, "caught" if ok else "WRONG CHECK", e))
        finally:
            A.BACK_MUSCLES = saved
    print("  %d of %d back sabotages caught" % (caught, len(bites)))
    if caught != len(bites):
        sys.exit(1)


def cloth_check():
    """--cloth-check (2026-09-27): garments.check_cloth on a body built the
    pipeline's way (pass one, the 3.5 mm union), dressed clean, then
    dressed once per rule broken: no fit (skin-tight), no folds, the
    seat's drape run below the crotch (a skirt), no hold-off from the skin.
    bpy as a module; a few minutes, most of it the dressing."""
    import build_saud as legacy
    import bpy
    from hero import anatomy as A, assembly as ASM, garments as G
    legacy.reset_scene()
    left = A.arm(1.0) + A.leg() + [A.shoe()] + ASM.masses()
    base = A.union_remesh([A.trunk(), A.neck(), A.head()] + left + [ASM.mirror_x(o) for o in left], 0.006, "Base")
    A.smooth(base, 0.40, 3)
    body = A.union_remesh([base] + ASM.face_parts(), 0.0035, "Body"); A.smooth(body, 0.5, 2)
    def dressed():
        t, p, soles = G.dress(body)
        out = G.check_cloth(t, p, body, assert_=False)
        try:
            G.check_cloth(t, p, body); err = None
        except AssertionError as e:
            err = str(e)
        for o in [t, p] + soles: bpy.data.objects.remove(o, do_unlink=True)
        return out, err
    fit0 = G.fit
    out, err = None, None
    saved = dict(fit=G.fit, FOLD_SCALE=G.FOLD_SCALE, PELVIS_Z=G.PELVIS_Z, CLEAR=dict(G.CLEAR))
    def restore():
        for k, v in saved.items(): setattr(G, k, v)
    G.check_cloth_in_dress = False
    out, err = dressed()
    print("  cloth    clean   " + "  ".join("%s %.4f" % kv for kv in out.items()))
    assert err is None, err
    bites = [("no fit", dict(fit=lambda g, kind, body=None: {}), "skin-tight"),
             ("no folds", dict(FOLD_SCALE=0.0), "no folds"),
             ("skirt", dict(PELVIS_Z=0.84), "skirt"),
             ("no hold-off", dict(CLEAR={"tee": -1.0, "pants": -1.0}, FOLD_SCALE=3.0), "from the skin")]
    caught = 0
    for label, patch, word in bites:
        for k, v in patch.items(): setattr(G, k, v)
        try:
            out, err = dressed()
        finally:
            restore()
        if "--verbose" in sys.argv:
            print("    " + "  ".join("%s %.4f" % kv for kv in out.items()))
        ok = err is not None and word in err; caught += ok
        print("  %-15s %s  %s" % (label, "caught" if ok else ("WRONG CHECK" if err else "NOT caught"), err or ""))
    # the legs apart at the thug's size (2026-09-28): the clean trousers
    # through his field, then the field with the old fixed taper
    import numpy as np
    from hero import roster
    t, p, soles = G.dress(body)
    co0 = np.empty(len(p.data.vertices) * 3); p.data.vertices.foreach_get("co", co0)
    def legs(keep):
        k0 = (A.NEARER_LIMB, A.MIDLINE_KEEP)
        if not keep: A.NEARER_LIMB, A.MIDLINE_KEEP = False, 0.0
        try:
            sp = roster.spec("thug")
            _h, _l, _t, Fm = A.build_field(sp["sc"], sp["look"]["build"])
            p.data.vertices.foreach_set("co", Fm(co0.reshape(-1, 3)).reshape(-1)); p.data.update()
            cz = float(Fm(np.array([[0.0, 0.0, 0.910]]))[0][2])
            try:
                return G.check_legs_apart(p, cz), None
            except AssertionError as e:
                return G.check_legs_apart(p, cz, assert_=False), str(e)
        finally:
            A.NEARER_LIMB, A.MIDLINE_KEEP = k0
    (n, gap), err = legs(True)
    print("  legs     clean   thug: %d faces across, nearest %.1f mm" % (n, gap * 1000))
    assert err is None, err
    (n, gap), err = legs(False)
    ok = err is not None and "each other" in err; caught += ok
    print("  %-15s %s  %s" % ("old leg field", "caught" if ok else "NOT caught", err or ""))
    for o in [t, p] + soles: bpy.data.objects.remove(o, do_unlink=True)
    print("  %d of %d cloth sabotages caught (the tee and the track)" % (caught, len(bites) + 1))
    # 2026-09-28: the tank and the joggers on Saud's lean body, then the
    # three tank men's own checkpoints through the build's --resume branch
    more = _Bites("tank and jogger")
    _tank_cloth(more)
    D = os.path.abspath(sys.argv[sys.argv.index("--checkpoints") + 1]) if "--checkpoints" in sys.argv else os.path.join(HERE, "hero", "build")
    _checkpoint_bites(more, D)
    print("  %d of %d cloth sabotages caught (the tee and the track)" % (caught, len(bites) + 1))
    if caught != len(bites) + 1:
        more.done()
        sys.exit(1)
    more.done()


def _tank_cloth(bites):
    """--cloth-check's tank and joggers (2026-09-28), on Saud's lean
    pass-two body built the physique way: his compression tank and his
    joggers dressed clean -- check_cloth with his cut (the tank's furrow
    cap 3 mm, its hang off the waist 6 mm at most; the joggers 10 / 9 mm
    off the knee and calf at most), check_bare (his arms bare), and the
    strip's hole rule (check_holes) on the dressed body -- then broken,
    one garment dressed each (the other an empty object), each by its own
    rule: the tank on the tee's drape ('not compression'), the tank as a
    skin-tight shell ('skin-tight'), the tee's region with its sleeves as
    his top ('sleeves'), the tank 1 mm off with no hold-off ('from the
    skin'), the joggers cut as the track trousers ('not fitted'), and the
    tee's arm strip left on under the tank ('holes'). About an hour."""
    import bpy, time
    from hero import garments as G, pipeline as P
    top, bottom = P.TOPS["saud"], P.BOTTOMS["saud"]
    t0 = time.time()
    _Pb, body = _physique_body("saud")
    G.check_cloth_in_dress = False
    def empty(name):
        me = bpy.data.meshes.new(name); o = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(o); return o
    def gone(*objs):
        for o in objs: bpy.data.objects.remove(o, do_unlink=True)
    t, p, soles = _quiet(G.dress, body, top=top, bottom=bottom)
    out = bites.clean("tank clean", lambda: G.check_cloth(t, p, body, top=top, bottom=bottom))
    if out:
        print("  %-8s clean   %s  (%.0f s)" % ("tank", "  ".join("%s %.4f" % kv for kv in out.items()), time.time() - t0))
    cov = bites.clean("tank bare", lambda: G.check_bare(body, t))
    if cov:
        print("  %-8s clean   the tank over %d of %d outer upper-arm faces" % ("bare", *cov))
    idx = [q.index for q in body.data.polygons if G.stripped(q.center, top)]
    ex = bites.clean("tank holes", lambda: G.check_holes(body, idx, [t, p]))
    if ex:
        print("  %-8s clean   %d of %d stripped faces with no garment or skin within %.0f mm" % ("holes", ex[0], ex[1], G.HOLE_REACH * 1000))
    arm = [q.index for q in body.data.polygons if G.stripped(q.center, "tee") and not G.stripped(q.center, top)
           and not (1.10 <= q.center.z <= 1.50 and abs(q.center.x) < 0.24 and G.tee_region(q.center))]
    bites.run("the tee's arm strip", "holes", lambda: G.check_holes(body, sorted(set(idx) | set(arm)), [t, p]))
    gone(t, p, *soles)
    row = G.TANKS[top]
    def tank(region=None, off=None, fit=None):
        tt = G.shell(body, "Tee", region or G.top_region(top), row["offset"] if off is None else off, 0.0025,
                     fold=row["fold"], fold_size=0.16)
        if fit: fit(tt)
        return tt
    def top_bite(label, word, make, check=None):
        t0 = time.time()
        tt = _quiet(make); pp = empty("Pants")
        try:
            bites.run(label, word, check and (lambda: check(tt)) or (lambda: G.check_cloth(tt, pp, body, top=top)))
        finally:
            gone(tt, pp)
        print("    (%.0f s)" % (time.time() - t0))
    top_bite("tank on the tee's drape", "not compression", lambda: tank(fit=lambda g: G.fit(g, "tee", body, cut="singlet")))
    top_bite("tank skin-tight", "skin-tight", lambda: tank())
    top_bite("the tee's region", "sleeves",
             lambda: G.shell(body, "Tee", G.tee_region, 0.006, 0.0025, fold=0.0010, fold_size=0.16),
             check=lambda g: (G.fit(g, "tee", body), G.check_bare(body, g)))
    clear0 = dict(G.CLEAR)
    G.CLEAR["compression"] = -1.0
    try:
        top_bite("tank 1 mm, no hold-off", "from the skin",
                 lambda: tank(off=0.001, fit=lambda g: G.fit(g, "tee", body, cut="compression")))
    finally:
        G.CLEAR.clear(); G.CLEAR.update(clear0)
    t0 = time.time()
    tt = empty("Tee")
    pp = _quiet(G.shell, body, "Pants", G.pants_region, 0.010, 0.003, fold=0.0012, fold_size=0.20)
    _quiet(G.fit, pp, "pants", body)            # the track's own drape
    try:
        bites.run("joggers cut as track", "not fitted", lambda: G.check_cloth(tt, pp, body, bottom=bottom))
    finally:
        gone(tt, pp)
    print("    (%.0f s)" % (time.time() - t0))


def _checkpoint_bites(bites, D):
    """--cloth-check's last part (2026-09-28): each tank man's own
    checkpoint in D (the one a build writes: `--checkpoints DIR`, default
    hero/build), run through build_fighter's --resume branch up to the
    paint and stopped there -- the budget (SHARES), the decimation, the
    shoe floor (at least SHOE_FLOOR shoe faces after it), the strip's hole
    rule on the body before the collapse, the tank's UVs (check_uv_flat)
    -- clean; then the tee's shares on a tank (the shoes collapse), for
    Saud the body's share at 0.76 (53 shoe faces: the floor itself), the
    tee's arm strip left on under the tank, and the tank's chart started
    above its hem at 1.10. About a minute a run."""
    import io, contextlib, re
    from hero import pipeline as P, finish as F, garments as G, roster
    class Stop(Exception):
        pass
    for kind in P.TOPS:
        spec = roster.spec(kind)
        chk = os.path.join(D, "built.blend" if kind == "saud" else "built_%s.blend" % kind)
        if not os.path.exists(chk):
            bites.clean("checkpoint " + kind, lambda chk=chk: (_ for _ in ()).throw(AssertionError(
                "no checkpoint %s: build him first (python3 build_fighters.py %s --fast --out DIR, then --checkpoints DIR)" % (chk, kind))))
            continue
        def run(shares=None, strip=None, chart=None, kind=kind, spec=spec):
            saved = (dict(P.SHARES), G.stripped, F.TANK_CHART, F.paint, G.check_holes, F.check_uv_flat)
            seen = {}
            def stop(*a, **k): raise Stop()
            def holes(*a, **k):
                seen["holes"] = saved[4](*a, **dict(k, assert_=False)); return saved[4](*a, **k)
            def flat(*a, **k):
                seen["flat"] = saved[5](*a, **dict(k, assert_=False)); return saved[5](*a, **k)
            F.paint = stop; G.check_holes = holes; F.check_uv_flat = flat
            if shares: P.SHARES["tank"] = shares
            if strip: G.stripped = strip
            if chart: F.TANK_CHART = chart
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    P.build_fighter(spec, ["--resume", "--out", D, "--fast", "--no-render", "--no-control-rig"])
                raise RuntimeError("ran past the paint")
            except Stop:
                m = re.search(r"shoe faces (\d+)", buf.getvalue())
                return dict(seen, shoes=int(m.group(1)) if m else None)
            finally:
                P.SHARES.clear(); P.SHARES.update(saved[0])
                G.stripped, F.TANK_CHART, F.paint, G.check_holes, F.check_uv_flat = saved[1:]
                _reset()
        r = bites.clean("checkpoint " + kind, run)
        if r:
            print("  %-8s clean   shoe faces %d (floor %d); holes %d of %d before the collapse; tank UVs %d of %d flat" % (
                kind, r["shoes"], P.SHOE_FLOOR, r["holes"][0], r["holes"][1], r["flat"][0], r["flat"][1]))
        bites.run("%s: the tee's shares" % kind, "shoe faces", lambda run=run: run(shares=P.SHARES["tee"]))
        if kind == "saud":
            bites.run("saud: body share 0.76", "want %d" % P.SHOE_FLOOR,
                      lambda run=run: run(shares=(0.76,) + tuple(P.SHARES["tank"][1:])))
        real = G.stripped
        def arm_left(c, top="tee", no_tee=False, seen=True, real=real):
            if real(c, top, no_tee, seen):
                return True
            # the tee's arm branch (as under a tee) left on under a tank
            return (top != "tee" and real(c, "tee", no_tee, seen)
                    and not (1.10 <= c.z <= 1.50 and abs(c.x) < 0.24 and G.tee_region(c)))
        bites.run("%s: the tee's arm strip" % kind, "holes", lambda run=run: run(strip=arm_left))
        bites.run("%s: chart from 1.10" % kind, "flat UVs", lambda run=run: run(chart=(1.10, 1.60)))


# ---------------------------------------------------------------- 2026-09-28
# The redesign's suites ("make Saud more aggressive and more fit look; make
# full redesign, make all game like dark anime adult style"): every rule
# the per-man tables (hero/pipeline.py) are held to, each run clean and
# then broken once by the sabotage that names it, the way the suites above
# are. A suite that builds several men in one process resets the module
# state (apply_man's) itself.

class _Bites:
    """One suite's sabotages: each must fail, and with its own rule's word."""
    def __init__(self, what):
        self.what, self.caught, self.total, self.clean_failed = what, 0, 0, []

    def run(self, label, word, fn):
        """fn() must raise AssertionError (or KeyError) naming `word`
        (a string, or a function of the message)."""
        self.total += 1
        try:
            fn()
        except (AssertionError, KeyError) as e:
            err = str(e)
            ok = word(err) if callable(word) else word in err
            self.caught += ok
            print("  %-26s %s  %s" % (label, "caught" if ok else "WRONG CHECK", err[:300]))
        else:
            print("  %-26s NOT caught" % label)
        sys.stdout.flush()

    def clean(self, label, fn):
        """fn() must pass; returns what it returns (None on a failure)."""
        try:
            return fn()
        except AssertionError as e:
            print("  %-26s CLEAN FAILS  %s" % (label, e))
            self.clean_failed.append(label)
            return None
        finally:
            sys.stdout.flush()

    def done(self):
        print("  %d of %d %s sabotages caught%s" % (self.caught, self.total, self.what,
              "" if not self.clean_failed else "; CLEAN FAILED: %s" % ", ".join(self.clean_failed)))
        if self.caught != self.total or self.clean_failed:
            sys.exit(1)


def _reset():
    """Every per-man module state back to the shared numbers."""
    from hero import sculpt as SC, anatomy as A, face as FA
    SC.set_eye(); A.set_physique(None); FA.set_look()


def _quiet(fn, *a, **k):
    """Run fn with its prints kept back (a build prints forty lines); on an
    exception, the last lines are shown before it goes on up."""
    import io, contextlib
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            return fn(*a, **k)
    except Exception:
        if "--verbose" in sys.argv:
            print("\n".join("    | " + l for l in buf.getvalue().split("\n")[-12:]))
        raise


def _pts(o):
    import numpy as np
    n = len(o.data.vertices); X = np.empty(n * 3); o.data.vertices.foreach_get("co", X)
    return X.reshape(n, 3)


def _real_body(kind, faces=None, holds=None):
    """The pipeline's own pass-two body for one man (hero/pipeline
    .build_fighter's B.build call, his tables through apply_man): the one
    every build ships, before the dress. Every in-build check runs in it
    and asserts. `faces` / `holds` replace his FACES / HOLDS entries.
    About 25 s."""
    from hero import pipeline as P, assembly as B, finish as F, roster
    spec = roster.spec(kind)
    man = P.apply_man(kind, spec)
    pal = F.palette_for(spec, P.KIT.get(kind), P.TOPS.get(kind, "tee"), P.BOTTOMS.get(kind, "track"))
    body, _trees, _eyes, _jl = _quiet(
        B.build, voxel_scale=1.0, face_scale=P.FACES.get(kind) if faces is None else faces, hair_style=man["hair"],
        arm_scale=P.LIMBS.get(kind, 1.0), gloves=pal["gloves"], physique=P.PHYSIQUE.get(kind), mass=P.MASS.get(kind),
        noses=P.NOSES.get(kind), ears=P.EARS.get(kind), holds=P.HOLDS.get(kind) if holds is None else holds)
    return body


def _head(kind, faces=None, noses="table", ears="table", drape=True):
    """One man's head built the way --eye-check builds one (the 3.5 mm
    union, the eye region subdivided, his sculpt, the drape, the relax),
    with his tables (apply_man: his lids), his ears and his cut. A few
    seconds."""
    import build_saud as legacy
    from hero import sculpt, assembly as ASM, anatomy as A, pipeline as P, roster
    man = P.apply_man(kind, roster.spec(kind))
    legacy.reset_scene()
    base = A.union_remesh([A.head(), A.neck()], 0.006, "Base"); A.smooth(base, 0.40, 3)
    e = P.EARS.get(kind, {}) if ears == "table" else (ears or {})
    body = A.union_remesh([base] + ASM.face_parts() + ASM.ear(1, e.get("l", 0.0)) + ASM.ear(-1, e.get("r", 0.0))
                          + ASM.hair_parts(man["hair"]), 0.0035, "Body")
    A.smooth(body, 0.5, 2)
    ASM.subdivide_eyes(body)
    scale, shift = sculpt.with_nose(P.FACES.get(kind) if faces is None else faces,
                                    P.NOSES.get(kind) if noses == "table" else noses)
    _quiet(sculpt.sculpt_face, body, A.head_surface_y, scale=scale, shift=shift)
    A.smooth(body, 0.3, 1)
    if drape:
        sculpt.drape_eyes(body, A.head_surface_y)
        ASM.relax_eyes(body)
    return body


def _physique_body(kind, physique="table", mass="table", arm="table"):
    """One man's body built the physique way: pass one (the 6 mm base,
    what check_neck and check_back read) and pass two (3.5 mm, the face
    parts and his physique's definition; no hands, hair or face sculpt),
    with his PHYSIQUE, MASS and LIMBS -- or the values given. Returns
    (base points, pass-two body). About 8 s."""
    import build_saud as legacy
    from hero import anatomy as A, assembly as ASM, pipeline as P
    P.apply_man(kind)
    ph = P.PHYSIQUE.get(kind) if physique == "table" else physique
    ms = P.MASS.get(kind) if mass == "table" else mass
    ar = P.LIMBS.get(kind, 1.0) if arm == "table" else arm
    A.set_physique(ph)
    legacy.reset_scene()
    left = A.arm(ar) + A.leg() + [A.shoe()] + ASM.masses(ph, ms, ar)
    base = A.union_remesh([A.trunk(), A.neck(), A.head()] + left + [A.mirror_x(o) for o in left], 0.006, "Base")
    A.smooth(base, 0.40, 3)
    Pb = _pts(base)
    defn = A.definition(ph); defn = defn + [A.mirror_x(o) for o in defn]
    body = A.union_remesh([base] + ASM.face_parts() + defn, 0.0035, "Body"); A.smooth(body, 0.5, 2)
    return Pb, body


def _resume_bites(bites, kind="saud"):
    """The --resume guard, bitten through build_fighter's own --resume
    branch (MERGE: not the guard function alone): a checkpoint is put
    where the branch looks, stamped, and build_fighter is run with
    --resume. The guard is wrapped so that once it has PASSED the run
    stops ('past the guard') before anything is opened; a checkpoint built
    with other numbers must be refused by the guard itself with 'without
    --resume'. A branch that stopped calling the guard would fail the
    clean case (it would go on to open the empty file) and let every
    sabotage through."""
    import tempfile, shutil
    from hero import pipeline as P, roster
    spec = roster.spec(kind)
    hair = P.hair_style_of(spec)
    D = tempfile.mkdtemp(prefix="saud_resume_")
    chk = os.path.join(D, "built.blend" if kind == "saud" else "built_%s.blend" % kind)

    class Past(Exception):
        pass
    real = P.check_resume

    def guard(*a, **k):
        real(*a, **k)
        raise Past("past the guard")

    def run(stamp=None, hair_file=None, faces=None):
        shutil.rmtree(D, ignore_errors=True); os.makedirs(D)
        open(chk, "w").close()          # the branch only asks that a checkpoint exist
        if stamp is not None:
            json.dump(stamp, open(chk + ".man", "w"))
        if hair_file is not None:
            open(chk + ".hair", "w").write(hair_file + "\n")
        saved = dict(P.FACES)
        if faces is not None:
            P.FACES[kind] = faces
        P.check_resume = guard
        try:
            _quiet(P.build_fighter, spec, ["--resume", "--out", D, "--fast", "--no-render", "--no-control-rig"])
            raise RuntimeError("build_fighter ran on past a checkpoint that is an empty file")
        except Past:
            return "past the guard"
        finally:
            P.check_resume = real
            P.FACES.clear(); P.FACES.update(saved)
            _reset()

    try:
        clean = P.man_stamp(kind, hair)
        print("  %-26s %s" % ("resume, the stamp it wrote", bites.clean("resume clean", lambda: run(clean))))

        def st(**over):
            s = json.loads(json.dumps(clean)); s.update(over); return s
        cases = [("resume: the old face", dict(stamp=st(FACES=P._LEGACY["FACES"].get(kind)))),
                 ("resume: open lids", dict(stamp=st(EYES=None))),
                 ("resume: canonical body", dict(stamp=st(PHYSIQUE=None))),
                 ("resume: in a tee", dict(stamp=st(TOPS=None))),
                 ("resume: before the stamp", dict(hair_file=hair)),
                 ("resume: FACES since", dict(stamp=clean, faces=dict(P.FACES[kind], brow_low=0.8)))]
        for label, kw in cases:
            bites.run(label, "without --resume", lambda kw=kw: run(**kw))
    finally:
        shutil.rmtree(D, ignore_errors=True)


def face_check():
    """--face-check (2026-09-28, Saud's scowl and every man's grim face):

    factor() -- the field with the OPTIONAL rows equals the field without
    them for every man whose FACES entry does not name them, on a 1 mm
    grid over the face (x +-70 mm, z 1.57-1.75), and the misspelt knob,
    eye number and hold are refused; each man's REAL pass-two body (the
    pipeline's own assembly.build, every in-build check asserting) and
    assembly.check_mien's numbers on it -- every man's jaw 8 mm inside his
    cheekbones, Saud's brow over the lid, his hollow and his jaw; Saud's
    scowl in the paint (face.check_brows); and the --resume guard. Then
    each broken: the OPTIONAL rows leaking onto every man, Saud with no
    scowl ridge, soft cheeks, the brawler's jaw, the thug's jaw a brick
    (each on the real body), a unibrow, no scowl, the paint never set,
    and six checkpoints the guard must refuse. bpy as a module; about six
    minutes."""
    import numpy as np
    from hero import sculpt as SC, pipeline as P, assembly as ASM, face as FA, finish as F, roster
    bites = _Bites("face")
    # ---- factor(): the OPTIONAL rows on no man who does not name them
    xs = np.arange(-0.070, 0.0700001, 0.001); zs = np.arange(1.570, 1.7500001, 0.001)
    X, Z = np.meshgrid(xs, zs)
    plain = [r for r in SC.FACE if r[0] not in SC.OPTIONAL]
    def moved(kind):
        scale, shift = SC.with_nose(P.FACES.get(kind), P.NOSES.get(kind)) if kind != "the rest" else (None, None)
        return float(np.abs(SC._field(X, Z, scale, SC.FACE, shift=shift) - SC._field(X, Z, scale, plain, shift=shift)).max())
    others = [k for k in P.FACES if not SC.OPTIONAL & set(P.FACES[k])] + ["the rest"]
    def unchanged():
        for kind in others:
            d = moved(kind)
            assert d == 0.0, "the OPTIONAL rows moved %s's face %.2f mm, want 0" % (kind, d * 1000)
    bites.clean("factor", unchanged)
    print("  factor   clean   the OPTIONAL rows move nobody who does not name them (%s): 0.00 mm; Saud's own %.2f mm" % (
        ", ".join(others), moved("saud") * 1000))
    f0 = SC.factor
    SC.factor = lambda scale, name: (scale or {}).get(name, 1.0)
    try:
        bites.run("optional leaks", "moved", unchanged)
    finally:
        SC.factor = f0
    bites.run("misspelt look knob", "no such look knob", lambda: FA.set_look(lip_glos=0.1))
    bites.run("misspelt eye number", "no such eye number", lambda: SC.set_eye(lid=0.003))
    _reset()

    # ---- every man's real pass-two body, and check_mien on it
    import time
    for kind in ("saud", "thug", "brawler", "saqr", "boss", "zayos"):
        t = time.time()
        def one(kind=kind):
            body = _real_body(kind)
            return ASM.check_mien(body, P.HOLDS.get(kind))
        m = bites.clean("mien " + kind, one)
        if m:
            print("  %-8s clean   jaw %.1f  cheekbones %.1f  gap %.2f  hollow %.2f  brow over %.2f mm   (the real body, %.0f s)" % (
                kind, m["jaw"] * 1000, m["cheek"] * 1000, m["gap"] * 1000, m["hollow"] * 1000, m["brow_over"] * 1000, time.time() - t))
        _reset()
    bites.run("misspelt hold", "no such mien hold", lambda: ASM.check_mien(None, dict(brow_ovr=0.004)))
    S, T = dict(P.FACES["saud"]), dict(P.FACES["thug"])
    for label, kind, faces, word in (
            ("no scowl ridge", "saud", dict(S, brow_low=0.0, corrugator=0.0), "no brow over"),
            ("soft cheeks", "saud", dict(S, hollow=0.85, cheek_fat=1.0, zygoma=0.0), "no hollow"),
            ("the brawler's jaw", "saud", dict(S, jaw2=1.30, jaw3=1.30, masseter=1.50), "too wide"),
            ("a brick", "thug", dict(T, jaw2=2.2, jaw3=2.6, masseter=2.6), "brick")):
        try:
            bites.run(label, word, lambda kind=kind, faces=faces: _real_body(kind, faces=faces))
        finally:
            _reset()

    # ---- Saud's scowl in the paint (face.check_brows through paint_checks)
    spec = roster.spec("saud")
    def paint(patch=None):
        try:
            P.apply_man("saud", spec)
            if patch: FA.LOOK.update(patch)
            pal = F.palette_for(spec, P.KIT.get("saud"), P.TOPS.get("saud", "tee"), P.BOTTOMS.get("saud", "track"))
            return P.paint_checks("saud", pal)
        finally:
            _reset()
    r = bites.clean("saud's paint", paint)
    if r:
        b = r["brows"]
        print("  saud     clean   two brows (%.2f of their weight within 5 mm of the midline), the inner end %.1f mm under the tail" % (
            b["gap"], b["slant"] * 1000))
    veins = {k: v for k, v in P.VEINS["saud"].items() if k != "hold"}
    bites.run("unibrow (brow_in 3.5 mm)", "one brow", lambda: paint(dict(brow_in=0.0035)))
    bites.run("no scowl (slant 0)", "no scowl", lambda: paint(dict(brow_slant=0.0)))
    bites.run("the paint never set", "no scowl", lambda: paint(dict(FA.LOOK_DEFAULT, **veins)))

    # ---- the one pre-checkpoint stamp, through the --resume branch
    _resume_bites(bites)
    _reset()
    bites.done()


def physique_check():
    """--physique-check (2026-09-28, Saud's lean body): each man's REAL
    pass-two body (the pipeline's assembly.build, every in-build check
    asserting) -- the proportions against bands() (the lean waist, chest,
    hips and V for Saud) and anatomy.check_physique (held for Saud,
    reported for the rest); then Saud's built with each thing the lean
    physique is broken once, each on the real body and each caught by its
    own rule: the canonical trunk ('waist'), the lats tucked in ('v'),
    no rectus ('abs'), the rectus pair met ('linea'), no oblique, no
    serratus, the canonical one deltoid ('deltoid cap'), no pec tie-in
    ('apart'); and the neck and back suites run again on the lean base,
    every sabotage still biting. bpy as a module; about eight minutes."""
    import time, bpy
    from hero import anatomy as A, assembly as ASM, pipeline as P
    bites = _Bites("physique")
    for kind in ("saud", "thug", "brawler", "saqr", "boss", "zayos"):
        t = time.time()
        def one(kind=kind):
            body = _real_body(kind)
            X = _pts(body)
            g = A.girths(body); g.update(A.proportions(X))
            return g, A.check_physique(X, assert_=False)
        r = bites.clean("body " + kind, one)
        if r:
            g, ph = r
            print("  %-8s clean   %s   waist %.3f chest %.3f hips %.3f v %.3f biceps %.3f | abs %.1f linea %.1f oblique %.1f serratus %.1f delt %+.1f tie %.1f mm  (%.0f s)" % (
                kind, P.PHYSIQUE.get(kind) or "canonical", g["waist"], g["chest"], g["hips"], g["v"], g["biceps"],
                *(ph[k] * 1000 for k in ("abs", "linea", "oblique", "serratus", "delt", "tie")), time.time() - t))
        _reset()

    lean = A.PHYSIQUES["lean"]
    rows = lean["TRUNK_ROWS"]
    # the lats tucked in 25 mm, no flare under the arm: only the V moves
    # (v 1.413, the waist 0.765 and the lats' own rule still passing on
    # the base). The body spec's own sabotage -- the ribcage in 22 mm and
    # no lat band -- trips check_back's lat rule on pass one first, and
    # narrowing the ribcage alone moves the V by 0.02-0.09 at most (the
    # lean lats carry the width) or takes the lat rule with it (5.5 mm).
    tucked = dict(lean["BACK_MUSCLES"], lat=[(x - 0.025, z, p, a) for x, z, p, a in lean["BACK_MUSCLES"]["lat"]])
    masses0 = ASM.masses
    def canon_delt(physique=None, mass=None, arm_scale=1.0):
        out = []
        for o in masses0(physique, mass, arm_scale):
            if o.name.split(".")[0] in ("delt_lat", "delt_ant", "delt_post"): bpy.data.objects.remove(o, do_unlink=True)
            else: out.append(o)
        for o in masses0(None, None):
            if o.name.split(".")[0] == "delt": out.append(o)
            else: bpy.data.objects.remove(o, do_unlink=True)
        return out
    def no_tie(physique=None, mass=None, arm_scale=1.0):
        out = []
        for o in masses0(physique, mass, arm_scale):
            if o.name.split(".")[0] == "pec_tie": bpy.data.objects.remove(o, do_unlink=True)
            else: out.append(o)
        return out
    def band(name):
        # check_proportions names every measure off its band after the colon
        return lambda e: "proportions" in e and name in [s.split()[0] for s in e.split(": ", 1)[1].split(", ")]
    cases = [("canonical trunk", dict(rows=A.CANON_TRUNK_ROWS), band("waist")),
             ("lats tucked in", dict(back=tucked), band("v")),
             ("no rectus", dict(A=dict(RECTUS=[])), "no abs"),
             ("rectus met (20 mm)", dict(A=dict(RECTUS_X=0.020)), "no linea"),
             ("no oblique", dict(A=dict(OBLIQUE=[])), "no oblique"),
             ("no serratus", dict(A=dict(SERRATUS=[])), "no serratus"),
             ("canonical deltoid", dict(masses=canon_delt), "no deltoid cap"),
             ("no tie-in", dict(masses=no_tie), "apart")]
    for label, patch, word in cases:
        saved = {k: getattr(A, k) for k in patch.get("A", {})}
        lean0 = dict(lean)
        def run(patch=patch):
            for k, v in patch.get("A", {}).items(): setattr(A, k, v)
            if "masses" in patch: ASM.masses = patch["masses"]
            if "rows" in patch: lean["TRUNK_ROWS"] = patch["rows"]
            if "back" in patch: lean["BACK_MUSCLES"] = patch["back"]
            _real_body("saud")
        try:
            bites.run(label, word, run)
        finally:
            for k, v in saved.items(): setattr(A, k, v)
            ASM.masses = masses0; lean.clear(); lean.update(lean0)
            _reset()

    # the neck and back suites on the lean base (Saud's trunk, his masses,
    # his arms): the clean base passes and every sabotage still bites
    for name, suite in (("neck", neck_check), ("back", back_check)):
        print("  -- --%s-check on the lean base" % name)
        try:
            suite(lean=True)
            bites.total += 1; bites.caught += 1
        except SystemExit:
            bites.total += 1
            print("  the %s suite FAILED on the lean base" % name)
        finally:
            _reset()
    bites.done()


def grim_check():
    """--grim-check (2026-09-28, the five men grim): the kit (finish
    .check_kit: dark, muted, one accent, worn tape, the tops apart and
    none of them his skin), the paint (pipeline.paint_checks for every
    man: brows, furrow, frown, scars paler than the skin with a pucker,
    the brawler's tape, the body scars), the body his MASS and LIMBS were
    for (pipeline.check_body_looks, against the same body built plain),
    every man's jaw inside his cheekbones (check_mien's every-man rule,
    measured on all six heads before it asserts in every build: MERGE 6)
    and the cauliflower ears (assembly.check_cauliflower) -- clean, then
    each broken: the browser's pastel tee, AL-SAQR's loud blue, the
    brawler's Kuwait red undeclared, a second accent, the boss in the
    thug's top, the brawler's rust tee, bone tape, a grey accent; the
    brows in his skin, no furrow, the old frown, the old scar tone, scar
    tissue in the old tone, no pucker, no tape, no body scars; each man
    built plain, ZAYOS's trapezius grown; a brick jaw; plain ears. bpy
    as a module; about four minutes."""
    import numpy as np, time
    from hero import pipeline as P, finish as F, face as FA, roster, anatomy as A, assembly as ASM
    bites = _Bites("grim")
    five = [k for k in ("thug", "brawler", "saqr", "boss", "zayos") if k in P.KIT]

    # ---- the kit
    def pals(**over):
        out = {}
        for k in five:
            kit = dict(P.KIT.get(k, {}), **over.get(k, {}))
            out[k] = F.palette_for(roster.spec(k), kit, P.TOPS.get(k, "tee"), P.BOTTOMS.get(k, "track"))
        return out
    r = bites.clean("kit", lambda: F.check_kit(pals()))
    if r:
        for k, v in r.items():
            print("  %-8s clean   " % k + "  ".join("%s L* %.1f C* %.1f pur %.2f" % (s, *n) if s != "tape" else "tape L* %.1f" % n[0]
                                                    for s, n in v.items()))
    ev = [(ka, kb, float(np.linalg.norm(F._lab(pa["tee"]) - F._lab(pb["tee"]))))
          for i, (ka, pa) in enumerate(pals().items()) for kb, pb in list(pals().items())[i + 1:]
          if not pa["no_tee"] and not pb["no_tee"]]
    print("  tops     clean   apart by " + "  ".join("%s-%s %.1f" % e for e in ev))
    kit_bites = [("thug in the browser's grey", dict(thug=dict(top="#8a9099")), "pastel"),
                 # (the browser's own blue, #2c4a8a, is L* 34.03 after fabric:
                 # over the dark rule by a hair, so it is not the one used)
                 ("saqr in a loud dark blue", dict(saqr=dict(top="#1f2d6b")), "shouts"),
                 ("brawler's band Kuwait red", dict(brawler=dict(band="#c8102e")), "undeclared accent"),
                 ("a second accent on the boss", dict(boss=dict(accent=("band", "top"))), "one accent"),
                 ("the boss in the thug's top", dict(boss=dict(top=P.KIT["thug"]["top"])), "the same kit"),
                 ("the brawler's rust tee", dict(brawler=dict(top="#8c4a34")), "pastel"),
                 # dark and muted enough to pass every slot rule, and his skin's
                 # own hue: Delta E 19.1 from it
                 ("the brawler in skin brown", dict(brawler=dict(top="#5c473b")), "as skin"),
                 ("bone tape on the boss", dict(boss=dict(tape="#e8e2d4")), "bone tape"),
                 ("saqr's accent grey", dict(saqr=dict(band="#3b3833")), "weak accent")]
    for label, over, word in kit_bites:
        bites.run(label, word, lambda over=over: F.check_kit(pals(**over)))

    # ---- the paint, every man (paint_checks, as every build runs it)
    def paint(kind, look=None, tables=None, face=None):
        spec = roster.spec(kind)
        saved_t = {k: dict(getattr(P, k)) for k in ("PAINT", "VEINS")}
        saved_f = {k: getattr(FA, k) for k in (face or {})}
        try:
            for t, (k, v) in (tables or {}).items():
                getattr(P, t)[k] = v
            P.apply_man(kind, spec)
            if look: FA.LOOK.update(look)
            for k, v in (face or {}).items(): setattr(FA, k, v)
            pal = F.palette_for(spec, P.KIT.get(kind), P.TOPS.get(kind, "tee"), P.BOTTOMS.get(kind, "track"))
            return P.paint_checks(kind, pal)
        finally:
            for k, v in saved_t.items():
                getattr(P, k).clear(); getattr(P, k).update(v)
            for k, v in saved_f.items(): setattr(FA, k, v)
            _reset()
    for kind in ("saud", "thug", "brawler", "saqr", "boss", "zayos"):
        r = bites.clean("paint " + kind, lambda kind=kind: paint(kind))
        if r:
            pn = r["paint"]
            print("  %-8s clean   brows %.1f L*  furrow %.1f L*  frown %.1f mm%s  scars %s  body scars %s" % (
                kind, pn["brow"], pn["furrow"], pn["frown"] * 1000, "  tape %.2f" % pn["tape"] if "tape" in pn else "",
                ["%+.1f/%s" % (q["centre"], "-" if q["pucker"] is None else "%+.1f" % q["pucker"]) for q in pn["scars"]] or "-",
                ["%+.1f" % q for q in r["body_scars"]] or "-"))
    old_tissue = lambda col, core, pucker, skin, _t=FA.scar_tissue: (
        _t(col, np.zeros(len(col)), pucker, skin) * (1 - 0.6 * core[:, None])
        + (skin * (FA.hex_lin(FA.SCAR) / FA.hex_lin(FA.SAUD_SKIN)))[None, :] * 0.6 * core[:, None])
    paint_bites = [
        ("zayos: brows in his skin", "zayos", dict(look=dict(brow_colour=None)), "no brows"),
        ("thug: no furrow", "thug", dict(look=dict(furrow=(0.0, 0.0))), "no furrow"),
        ("thug: the old frown", "thug", dict(look=dict(lip_drop=0.0024)), "no frown"),
        ("boss: the old scar tone", "boss", dict(look=dict(scars=None)), "a dark scar"),
        ("boss: tissue in old SCAR", "boss", dict(face=dict(scar_tissue=old_tissue)), "a dark scar"),
        ("saqr: no pucker", "saqr", dict(face=dict(SCAR_PUCKER=0.0)), "no pucker"),
        ("brawler: no tape", "brawler", dict(look=dict(nose_tape=None)), "no tape"),
        ("zayos: no body scars", "zayos",
         dict(look=dict(scars=[q for q in P.PAINT["zayos"]["scars"] if q.get("at", "face") == "face"])), "no body scar")]
    for label, kind, kw, word in paint_bites:
        bites.run(label, word, lambda kind=kind, kw=kw: paint(kind, **kw))

    # ---- the bodies their MASS and LIMBS were for, against themselves plain
    def measures(kind, **kw):
        Pb, body = _physique_body(kind, **kw)
        g = A.girths(body)
        return dict(chest=g["chest"], waist=g["waist"], biceps=g["biceps"], v=A.check_back(Pb, assert_=False)["v"]), Pb
    for kind in five:
        t = time.time()
        (man, _pb), (plain, _pp) = measures(kind), measures(kind, mass=None, arm=1.0)
        d = bites.clean("body " + kind, lambda kind=kind, man=man, plain=plain: P.check_body_looks(kind, man, plain))
        if d is not None:
            print("  %-8s clean   chest %+.0f  waist %+.0f  biceps %+.0f mm over plain (%.3f / %.3f / %.3f), V %.3f (plain %.3f)  %.0f s" % (
                kind, d["chest"] * 1000, d["waist"] * 1000, d["biceps"] * 1000, man["chest"], man["waist"], man["biceps"],
                man["v"], plain["v"], time.time() - t))
        word = {"thug": "no arms", "brawler": "no mass on the waist", "saqr": "kicker's V", "boss": "no mass on the chest",
                "zayos": "no mass on the chest"}[kind]
        bites.run("%s built plain" % kind, word, lambda kind=kind, plain=plain: P.check_body_looks(kind, plain, plain))
        _reset()
    def trap_zayos():
        Pb, _body = _physique_body("zayos", mass=dict(P.MASS.get("zayos", {}), trap=1.20))
        A.check_neck(Pb)
    try:
        bites.run("zayos trapezius x1.20", "round", trap_zayos)
    finally:
        _reset()

    # ---- every man's jaw inside his cheekbones, on all six heads
    for kind in ("saud", "thug", "brawler", "saqr", "boss", "zayos"):
        def jaw(kind=kind):
            m = ASM.mien_numbers(_head(kind))
            ASM.check_mien(None, None, numbers=m)
            return m
        m = bites.clean("jaw " + kind, jaw)
        if m:
            print("  %-8s clean   jaw %.1f  cheekbones %.1f  gap %.2f mm (rule %.0f: %.2f to spare)" % (
                kind, m["jaw"] * 1000, m["cheek"] * 1000, m["gap"] * 1000, ASM.JAW_GAP * 1000, (m["gap"] - ASM.JAW_GAP) * 1000))
        _reset()
    T = dict(P.FACES["thug"])
    try:
        bites.run("a brick (thug's head)", "brick",
                  lambda: ASM.check_mien(None, None, numbers=ASM.mien_numbers(_head("thug", faces=dict(T, jaw2=2.2, jaw3=2.6, masseter=2.6)))))
    finally:
        _reset()

    # ---- the cauliflower ears, against the same head with plain ears
    for kind, ears in P.EARS.items():
        def cauli(kind=kind, ears=ears, plain=False):
            # his head with his EARS (or, the sabotage, built with plain
            # ears), against the same head with plain ones
            on = ASM.ear_profile(_head(kind, ears={} if plain else "table"))
            off = ASM.ear_profile(_head(kind, ears={}))
            return ASM.check_cauliflower(on, off, ears)
        r = bites.clean("ears " + kind, cauli)
        if r:
            print("  %-8s clean   " % kind + "  ".join("%s ear %.1f mm further out over its upper third (%.1f-%.1f)" % (
                s, v["mean"] * 1000, v["min"] * 1000, v["max"] * 1000) for s, v in r.items()))
        _reset()
        bites.run("%s's ears plain" % kind, "no cauliflower", lambda cauli=cauli: cauli(plain=True))
        _reset()
    bites.done()


def fabric_check():
    """--fabric-check (2026-09-28): the per-texel roughness of each man's
    cloth, as repaint_kit lays it (finish.fabric_surface, the fabric picked
    from his TOPS / BOTTOMS as repaint_kit picks it), on points over the
    garments' own surfaces -- the trunk loft 6 mm out from 1.07 to 1.50 and
    a ring round each leg from the hip to the ankle -- held to
    finish.FABRIC_RULES: Saud's joggers p5 >= 0.70, his compression top p50
    0.62-0.74 (the rest reported). Then the old fabrics painted in their
    place: the tricot on the joggers (p5 0.48), the jersey on the tank
    (p50 0.85). Numpy only."""
    import numpy as np, math
    from hero import finish as F, anatomy as A, pipeline as P, roster
    bites = _Bites("fabric")
    angs = np.linspace(-math.pi, math.pi, 181)[:-1]
    trunk = []
    for z in np.arange(1.07, 1.50, 0.004):
        for a in angs:
            p, n = A.trunk_at(a, z)
            trunk.append(np.array(p) + np.array(n) * 0.006)
    trunk = np.array(trunk)
    legs = []
    for s in (1, -1):
        hip = np.array(A.Jp("thigh_l")) * [s, 1, 1]; ank = np.array(A.Jp("foot_l")) * [s, 1, 1]
        d = (ank - hip) / np.linalg.norm(ank - hip)
        u = np.cross(d, [0, 1.0, 0]); u /= np.linalg.norm(u); v = np.cross(d, u)
        for t in np.linspace(0.02, 0.97, 160):
            c = hip + (ank - hip) * t; r = 0.085 - 0.040 * t
            for a in angs[::2]:
                legs.append(c + r * (math.cos(a) * u + math.sin(a) * v))
    legs = np.array(legs)
    def fk_of(pal, kind):
        return (pal.get("top", "tee") if kind == "tee" else
                ("pants" if pal.get("bottom", "track") == "track" else pal["bottom"]))
    def rough(man, kind, surface=None):
        spec = roster.spec(man)
        pal = F.palette_for(spec, P.KIT.get(man), P.TOPS.get(man, "tee"), P.BOTTOMS.get(man, "track"))
        Pt = trunk if kind == "tee" else legs
        parts = {}
        edge = np.full(len(Pt), 0.05) if kind == "tee" and pal["top"] != "tee" else None
        F.kit_colour(Pt, kind, pal, {}, parts=parts, edge=edge)
        fk = fk_of(pal, kind)
        _t, _r, rr = (surface or F.fabric_surface)(Pt, fk, parts, pal)
        return fk, rr, parts
    for man in ("saud", "thug", "brawler", "saqr", "boss", "zayos"):
        row = []
        for kind in ("tee", "pants"):
            if kind == "tee" and not roster.spec(man)["look"].get("tee", True):
                continue
            fk, rr, parts = rough(man, kind)
            held = bites.clean("fabric %s %s" % (man, fk), lambda rr=rr, fk=fk, parts=parts: F.check_fabric(rr, fk, parts=parts))
            row.append("%s p5 %.3f p50 %.3f%s" % (fk, np.percentile(rr, 5), np.percentile(rr, 50),
                                                    " (the cloth, held: %.3f)" % held if held is not None else ""))
        print("  %-8s clean   %s" % (man, "  ".join(row)))
    real = F.fabric_surface
    def old(Pt, fk, parts, pal=None):
        # the fabric he wore before his cut was: the track's tricot at the
        # track's own roughness, the tee's jersey
        if fk == "jogger": return real(Pt, "pants", parts, dict(pal or {}, pants_rough=F.PANTS_ROUGH))
        if fk == "compression": return real(Pt, "tee", parts, pal)
        return real(Pt, fk, parts, pal)
    for label, kind, fk in (("tricot on the joggers", "pants", "jogger"), ("jersey on the tank", "tee", "compression")):
        def bite(kind=kind):
            fk_, rr, parts = rough("saud", kind, old)
            F.check_fabric(rr, fk_, parts=parts)
        bites.run(label, "the %s's roughness" % fk, bite)
    bites.done()


def vein_check():
    """--vein-check (2026-09-28): the veins on both forearms, every man
    (face.check_veins through pipeline.apply_man, as paint_checks runs
    it): lines along the limb, not a net -- at most 15 % of the forearm,
    the 6 mm autocorrelation along it 3x that across -- and Saud's own
    hold, 2-4 veins across the 96 mm of his flexor side, 0.45 mm of
    relief or more. Then: Saud with no VEINS entry (the old Worley net),
    Saud at the five men's strength, faint veins, the lines not stretched
    along the limb (isotropic contours), the thug on the old net. Numpy
    only."""
    from hero import pipeline as P, face as FA, finish as F, roster
    bites = _Bites("vein")
    def veins(kind, entry="table", look=None):
        spec = roster.spec(kind)
        saved = dict(P.VEINS)
        try:
            if entry != "table":
                if entry is None: P.VEINS.pop(kind, None)
                else: P.VEINS[kind] = entry
            P.apply_man(kind, spec)
            if look: FA.LOOK.update(look)
            pal = F.palette_for(spec, P.KIT.get(kind), P.TOPS.get(kind, "tee"), P.BOTTOMS.get(kind, "track"))
            # the hold is the man's (his table's), whatever his knobs are
            return FA.check_veins(saved.get(kind, {}).get("hold"), build=pal["build"])
        finally:
            P.VEINS.clear(); P.VEINS.update(saved)
            _reset()
    for kind in ("saud", "thug", "brawler", "saqr", "boss", "zayos"):
        r = bites.clean("veins " + kind, lambda kind=kind: veins(kind))
        if r:
            print("  %-8s clean   " % kind + "   ".join("%s cover %.1f %% along/across %.1f crossings %.2f peak %.2f mm" % (
                "left " if s > 0 else "right", v["cover"] * 100, v["aniso"], v["crossings"], v["peak"] * 1000) for s, v in r.items()))
    five = dict(vein_style="contour", vein_k=1.0)
    bites.run("saud: no VEINS (old net)", "a net", lambda: veins("saud", entry=None))
    bites.run("saud: the five men's", "veins across", lambda: veins("saud", entry=dict(five)))
    bites.run("saud: faint (0.35 mm)", "faint", lambda: veins("saud", look=dict(vein_height=0.00035)))
    bites.run("saud: not along the limb", "scales", lambda: veins("saud", look=dict(vein_stretch=1.0)))
    bites.run("thug: the old net", "a net", lambda: veins("thug", entry=None))
    bites.done()


def main():
    argv = sys.argv[1:]
    if "--hair-check" in argv:
        hair_check()
        return
    if "--nose-check" in argv:
        nose_check()
        return
    if "--eye-check" in argv:
        eye_check()
        return
    if "--head-check" in argv:
        head_check()
        return
    if "--neck-check" in argv:
        neck_check()
        return
    if "--back-check" in argv:
        back_check()
        return
    if "--cloth-check" in argv:
        cloth_check()
        return
    for flag, suite in (("--face-check", face_check), ("--physique-check", physique_check), ("--grim-check", grim_check),
                        ("--fabric-check", fabric_check), ("--vein-check", vein_check)):
        if flag in argv:
            suite()
            return
    # flags are `--x`, plus the value that follows --out and --one; the rest
    # are the men to build
    taken = set()
    for opt in ("--out", "--one", "--checkpoints"):
        if opt in argv:
            taken.add(argv.index(opt) + 1)
    flags = [a for i, a in enumerate(argv) if a.startswith("--") or i in taken]
    kinds = [a for i, a in enumerate(argv) if not a.startswith("--") and i not in taken]
    kinds = kinds or list(ROSTER)
    if "--one" in flags:
        i = flags.index("--one"); kind = flags[i + 1]
        one(kind, [f for j, f in enumerate(flags) if j not in (i, i + 1)])
        return
    check(kinds)
    if "--check" in flags:
        return
    out = os.path.join(HERE, "hero", "build")
    if "--out" in flags:
        out = os.path.abspath(flags[flags.index("--out") + 1])
    os.makedirs(out, exist_ok=True)
    results = {}
    for kind in kinds:
        t = time.time()
        log = os.path.join(out, "%s.log" % kind)
        print("\n== %s  (log: %s)" % (kind, log)); sys.stdout.flush()
        with open(log, "w") as fh:
            rc = subprocess.call([sys.executable, os.path.abspath(__file__), "--one", kind] + flags,
                                 stdout=fh, stderr=subprocess.STDOUT, cwd=HERE)
        summ = os.path.join(out, "%s_summary.json" % kind)
        ok = rc == 0 and os.path.exists(summ)
        results[kind] = json.load(open(summ)) if ok else None
        print("   %s in %.0fs%s" % ("built" if ok else "FAILED (rc %d)" % rc, time.time() - t,
                                    "" if ok else "  -- see the log"))
        if not ok:
            with open(log) as fh:
                tail = fh.read().split("\n")[-25:]
            print("\n".join("   | " + l for l in tail))
    print("\n%-8s %6s %6s %5s %6s %7s %7s %7s" % ("fighter", "tris", "verts", "bones", "height", "h", "limbs", "torso"))
    for kind, r in results.items():
        if not r:
            print("%-8s FAILED" % kind); continue
        f = r["factors"]
        print("%-8s %6d %6d %5d %6.3f %7.3f %7.3f %7.3f" % (
            r["name"], r["tris"], r["verts"], r["bones"], r["roundtrip_gltf"]["height"], f["h"], f["l"], f["t"]))
    if any(r is None for r in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
