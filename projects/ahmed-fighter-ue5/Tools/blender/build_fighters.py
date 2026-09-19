#!/usr/bin/env python3
"""The fighters of the first area -- and the hero -- built, rigged, exported.

    python3 build_fighters.py                  ahmed, thug, brawler: the lot
    python3 build_fighters.py thug brawler     some of them
    python3 build_fighters.py --fast           1K textures, quick renders
    python3 build_fighters.py --coarse         a rough body, to check the stages
    python3 build_fighters.py --check          the roster and the palette only
    python3 build_fighters.py --out DIR        write somewhere else than the project

WHO. SOUQ AL-DAWAR's three waves are thugs and brawlers (DT_Stages.json,
stage 0), and Ahmed walks into them. Those are the three men here. Every
number that says what one of them looks like is read out of the browser
build's roster -- assets/ahmed.js, assets/enemies.js -- by hero/roster.py:
the colours, the kit, `sc` and `build`. DT_Fighters.csv carries none of
that (../../CLAUDE.md, "Known, not fixed"), which is why the roster is read
rather than the table.

HOW. One body, every man: hero/pipeline.build_fighter runs the hero
pipeline for a spec, at Ahmed's coordinates up to the bake, then takes the
finished mesh and its joints to the man's own size through the browser
build's own sc / build mapping (hero/anatomy.scale_to), builds the
mannequin's skeleton on it, the full IK control rig over that, verifies
the rig, saves the animator's .blend, strips the control layer and exports
exactly the mannequin's 62 bones.

ONE PROCESS PER MAN. The hero modules hold module state -- the joint table,
the face layout, the skull rows -- and a man's build mutates the joints.
Each fighter is built in its own interpreter so nothing carries over.
"""
import os, sys, json, time, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROSTER = ("ahmed", "thug", "brawler")


def check(kinds):
    """The roster reads, and Ahmed's derived palette lands where his hand-typed
    one did -- except the beard, which is now the browser's wash over his
    skin rather than a shade somebody chose, and that is reported."""
    from hero import roster, finish as F
    import numpy as np
    for k in kinds:
        s = roster.spec(k)
        assert s["look"].get("tee") and s["look"].get("pants"), "%s: this pipeline dresses a tee and trousers" % k
        assert not s["look"].get("bald"), "%s: no bald head in this pipeline yet" % k
        print("  %-8s %-10s sc %.2f build %.2f  skin %s top %s bottom %s band %s  hands %s  beard %s" % (
            s["name"], s["display"], s["sc"], s["look"].get("build", 1.0), s["col"]["skin"], s["col"]["top"],
            s["col"]["bottom"], s["col"]["band"], s["look"].get("hands"), "yes" if s["look"].get("beard") else "no"))
    new, old = F.palette_for(roster.spec("ahmed")), F.ahmed_palette()
    same = [k for k in ("skin", "hair", "tee", "pants", "band", "shoe") if np.allclose(new[k], old[k])]
    assert len(same) == 6, "Ahmed's palette drifted from what paint() always used: %s" % (set("skin hair tee pants band shoe".split()) - set(same))
    print("  Ahmed's palette, read from the browser, equals the one that was typed: skin hair tee pants band shoe")
    print("  beard: typed %s -> read %s (the browser's rgba wash over his skin)" % (
        tuple(round(float(v), 4) for v in old["beard"]), tuple(round(float(v), 4) for v in new["beard"])))
    for k in ("tape_on", "patch", "stripe", "watch"):
        assert new[k] == old[k], "Ahmed's kit drifted: %s" % k


def one(kind, argv):
    """Build one man, in this process."""
    from hero import roster, pipeline
    return pipeline.build_fighter(roster.spec(kind), argv)


def main():
    argv = sys.argv[1:]
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
