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
    python3 build_fighters.py --cloth-check    the tee and trousers' drape, folds and clearance, bitten
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
the face layout, the skull rows, and since 2026-09-28 a man's lids and
trunk (pipeline.apply_man: sculpt.set_eye, anatomy.set_physique) -- and a
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
    caught, total = sculpt.bite()
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
    if caught != total:
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


def neck_check():
    """--neck-check (2026-09-26): anatomy.check_neck on pass one of the
    build -- the base the pipeline unions at 6 mm -- clean, and each of its
    rules broken once by building the base that breaks it: the old
    trapezius (the shelf), a slumped trapezius (the trunk's own shelf shows), a trapezius
    only over the shoulder (the step), no SCM (no notch), the neck column
    a third thicker.
    bpy as a module, a few seconds a base."""
    import build_saud as legacy
    import numpy as np
    from hero import anatomy as A, assembly as ASM
    def base():
        legacy.reset_scene()
        left = A.arm(1.0) + A.leg() + [A.shoe()] + ASM.masses()
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


def back_check():
    """--back-check (2026-09-27): anatomy.check_back on pass one of the
    build, clean, and each rule broken once by the base that breaks it:
    no back muscles at all, the erectors flattened, no lats, the lats
    pushed out past the flank. bpy as a module, a few seconds a base."""
    import build_saud as legacy
    import numpy as np
    from hero import anatomy as A, assembly as ASM
    def base():
        legacy.reset_scene()
        left = A.arm(1.0) + A.leg() + [A.shoe()] + ASM.masses()
        b = A.union_remesh([A.trunk(), A.neck(), A.head()] + left + [ASM.mirror_x(o) for o in left], 0.006, "Base")
        A.smooth(b, 0.40, 3)
        return np.array([v.co[:] for v in b.data.vertices])
    print("  back     clean   " + "  ".join("%s %.3f" % kv for kv in A.check_back(base()).items()))
    m = dict(A.BACK_MUSCLES)
    bites = [("no back muscles", {}, "furrow"),
             ("flat erectors", dict(m, erector=[(x, z, 0.0005, a) for x, z, p, a in m["erector"]]), "furrow"),
             ("no lats", dict(erector=m["erector"]), "lats"),
             ("lats out wide", dict(m, lat=[(x + 0.040, z, p + 0.006, a) for x, z, p, a in m["lat"]]), "V")]
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
    print("  %d of %d cloth sabotages caught" % (caught, len(bites) + 1))
    if caught != len(bites) + 1:
        sys.exit(1)


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
    # flags are `--x`, plus the value that follows --out and --one; the rest
    # are the men to build
    taken = set()
    for opt in ("--out", "--one"):
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
