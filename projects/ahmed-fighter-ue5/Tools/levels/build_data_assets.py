"""AHMED — Kuwait Fighter :: tables -> Data Assets
==============================================================================
The gameplay layer runs on Data Assets, because an asset can hold a gameplay
tag, an ability class and a montage reference, and a DataTable row cannot.
The NUMBERS still come from the browser project, though, and they always will
— so this generates the assets from Content/Data rather than asking anyone to
type them twice.

    assets/*.js  ──(export.mjs)──>  Content/Data/*.csv  ──(this)──>  /Game/Data/DA_*

Editing a generated asset by hand works until the next run overwrites it. If a
number is wrong, it is wrong in the browser project; fix it there, re-export,
re-run this.

What it decides that the CSV cannot:

  The tag. DT_Attacks says an attack's family is "Box"; the asset carries
  Ahmed.Attack.Box.Jab, which is a family AND an identity in one value, and
  is why a cracked wall can ask for any punch.

  The cue tags. Which impact a strike plays is a property of the strike, and
  is derived here from whether it is heavy rather than authored per row.

  The fight styles. DT_Fighters says an archetype's reach, rhythm and move
  list; a style says what it does with them -- where it stands, how it moves
  while it waits, and which of its moves is worth throwing from where it is.
  That is derived here from the same row rather than authored, so the styles
  cannot drift away from the numbers they came from.

RUN IT INSIDE THE EDITOR, same as build_levels.py:

    exec(open(r"<project>/Tools/levels/build_data_assets.py").read())

Outside the editor it prints what it would make and exits, which is how it was
checked without an engine.
==============================================================================
"""

import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(PROJECT, "Content", "Data")
OUT = "/Game/Data/Generated"

# The browser's attack keys against the tags the gameplay layer dispatches on.
# An attack here with no entry is a hard stop rather than an untagged asset:
# an untagged attack is one no gate will ever accept, and that failure is
# invisible until someone cannot break a wall.
ATTACK_TAGS = {
    "Jab":     "Ahmed.Attack.Box.Jab",
    "Cross":   "Ahmed.Attack.Box.Cross",
    "Hook":    "Ahmed.Attack.Box.Hook",
    "Kick":    "Ahmed.Attack.Kick.Roundhouse",
    "Knee":    "Ahmed.Attack.Kick.Knee",
    "Special": "Ahmed.Attack.Rage",
}
TALENT_TAGS = {
    "Vault":     "Ahmed.Talent.Vault",
    "DashLeap":  "Ahmed.Talent.DashLeap",
    "PowerKick": "Ahmed.Talent.PowerKick",
    "Haymaker":  "Ahmed.Talent.Haymaker",
    "HawkFist":  "Ahmed.Talent.HawkFist",
    # Not in the browser build's talents.js: these two exist only in the
    # engine port so far, and are declared here so the assets can be made.
    "Jump":      "Ahmed.Talent.Jump",
    "Climb":     "Ahmed.Talent.Climb",
}
# Talents the engine adds. Kept beside the table rather than in it, because
# the table is generated from the browser project and this is not.
ENGINE_ONLY_TALENTS = [
    dict(Name="Jump", DisplayName="JUMP", DisplayNameArabic="قفزة عالية",
         Icon="⤒", ManaCost=0,
         Description="Get over things. Until you find it, your feet stay on the floor."),
    dict(Name="Climb", DisplayName="CLIMB", DisplayNameArabic="تسلق",
         Icon="⇡", ManaCost=0,
         Description="Pull up onto any ledge, not only the ones someone left for you."),
]


def read(name):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        raise SystemExit("missing %s — run: node Tools/export/export.mjs --api" % path)
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(row, key, default=0.0):
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def truthy(v):
    return str(v).strip().lower() in ("true", "1", "yes")


def plan_attacks():
    out = []
    for row in read("DT_Attacks.csv"):
        name = row["Name"]
        tag = ATTACK_TAGS.get(name)
        if not tag:
            raise SystemExit(
                "attack '%s' has no gameplay tag. Add it to ATTACK_TAGS here and to\n"
                "AhmedGameplayTags.h, then re-run." % name)
        heavy = truthy(row.get("bHeavy"))
        out.append(dict(
            asset="DA_Attack_%s" % name,
            AttackTag=tag,
            DisplayName=name,
            Startup=num(row, "Startup"), Active=num(row, "Active"),
            Recovery=num(row, "Recovery"),
            Damage=num(row, "Damage"), Reach=num(row, "Reach"),
            DepthTolerance=num(row, "DepthTolerance", 80),
            Knockback=num(row, "Knockback"),
            StaminaCost=num(row, "StaminaCost"),
            ManaCost=0.0,
            bHeavy=heavy,
            bMultiHit=truthy(row.get("bMultiHit")),
            # Bosses shrug most knockdowns off; the chance lives on the strike
            # and the resistance on the fighter, so neither has to know the other.
            KnockdownChance=0.45 if heavy else 0.0,
            WhooshCue="Ahmed.Cue.Whoosh.Heavy" if heavy else "Ahmed.Cue.Whoosh.Light",
            ImpactCue="Ahmed.Cue.Hit.Heavy" if heavy else "Ahmed.Cue.Hit.Light",
            MotionWarpDistance=num(row, "Reach") * 0.6,
        ))
    return out


def plan_talents():
    rows = read("DT_Talents.csv")
    rows = rows + [dict(r) for r in ENGINE_ONLY_TALENTS]
    out = []
    for row in rows:
        name = row["Name"]
        tag = TALENT_TAGS.get(name)
        if not tag:
            raise SystemExit("talent '%s' has no gameplay tag." % name)
        out.append(dict(
            asset="DA_Talent_%s" % name,
            TalentTag=tag,
            DisplayName=row.get("DisplayName", name),
            DisplayNameArabic=row.get("DisplayNameArabic", ""),
            Icon=row.get("Icon", ""),
            Description=row.get("Description", ""),
            ManaCost=num(row, "ManaCost"),
        ))
    return out


# ---------------------------------------------------------------- styles
#
# Where each move is worth throwing from, and how likely it is to be the
# start of something rather than the whole of it.
#
# Bands are the move's own property, not the archetype's: a knee is a close-
# range strike whoever throws it, and an archetype that only knows knees is an
# archetype that has to get inside to do anything at all. That is what makes
# a grappler read as a grappler.
STRIKE_BANDS = {
    #          bands it can be thrown from       weight  opener chance
    "Jab":     (["Mid", "Close"],                  1.6,   0.75),
    "Cross":   (["Mid"],                           1.1,   0.35),
    "Hook":    (["Mid", "Close"],                  0.9,   0.20),
    "Kick":    (["Long", "Mid"],                   1.0,   0.15),
    "Knee":    (["Close"],                         1.2,   0.30),
    "Special": (["Mid", "Close"],                  0.5,   0.00),
    "Rage":    (["Mid", "Close"],                  0.5,   0.00),
}


def plan_styles():
    """One style per enemy archetype, derived from its own row.

    Nothing here is a hand-tuned personality. Each dial is read off numbers
    the browser project already carries -- reach, rhythm, guard, hit-and-run,
    speed, boss -- because a style that disagrees with the numbers is a style
    that makes the fighter feel broken rather than distinct.
    """
    out = []
    for row in read("DT_Fighters.csv"):
        name = row["Name"]
        if name == "Ahmed":
            continue                    # the player is not driven by a style

        moves = [m.strip().strip('"') for m in
                 row.get("Moves", "").strip("()").split(",") if m.strip()]
        # A move listed twice is the browser project's way of saying "throw
        # this one more often". Collapsing the repeat into the weight says
        # the same thing where the selection can see it.
        strikes = []
        for m in moves:
            if m not in STRIKE_BANDS:
                raise SystemExit(
                    "move '%s' (fighter %s) has no range bands. Add it to\n"
                    "STRIKE_BANDS here and re-run." % (m, name))
            existing = next((k for k in strikes if k["AttackRow"] == m), None)
            if existing:
                existing["Weight"] = round(existing["Weight"] + STRIKE_BANDS[m][1], 2)
                continue
            bands, weight, opener = STRIKE_BANDS[m]
            strikes.append(dict(AttackRow=m, Bands=list(bands),
                                Weight=weight, OpensCombination=opener))
        if not strikes:
            raise SystemExit("fighter '%s' has no moves to build a style from" % name)

        reach = num(row, "PreferredRange", 130)
        rate = num(row, "AttackInterval", 1.55)
        speed = num(row, "MoveSpeed", 240)
        hit_run = truthy(row.get("bHitAndRun"))
        boss = truthy(row.get("bIsBoss"))
        health = num(row, "MaxHealth", 46)

        # A fighter that strikes and leaves holds its distance and bounces;
        # one that does not walks in and stands there. That single flag is
        # most of the difference between a runner and a bouncer.
        discipline = 0.9 if hit_run else max(0.15, min(0.85, 1.0 - health / 300.0))
        has_long = any("Long" in st["Bands"] for st in strikes)

        out.append(dict(
            asset="DA_Style_%s" % name,
            DisplayName=row.get("DisplayName", name),
            # Kickers stand a little further out than their reach suggests,
            # because a kick thrown from punching distance is a kick that
            # jams -- which is the mistake the old uniform AI made all night.
            PreferredRange=round(reach * (1.12 if has_long else 0.95), 1),
            RangeDiscipline=round(discipline, 2),
            ResetDistance=round(reach * 2.6, 1) if hit_run else 0.0,
            # Light and fast bounces; heavy and slow plants its feet.
            BounceRate=round(min(2.2, speed / 260.0), 2) if speed > 260 else 0.0,
            BounceAmplitude=round(reach * 0.22, 1) if speed > 260 else 0.0,
            # Faster feet circle more; a wall of a fighter barely does.
            CircleTendency=round(max(0.05, min(0.8, (speed - 200) / 260.0)), 2),
            CircleSwitchTime=round(max(0.8, 4.0 - speed / 130.0), 2),
            Strikes=strikes,
            AttackInterval=rate if rate > 0 else 1.55,
            # A slow archetype telegraphs; the jitter is what stops the fast
            # ones from reading as a metronome.
            RhythmJitter=round(max(0.15, min(0.45, 0.55 - rate * 0.12)), 2),
            MaxComboLength=3 if boss else (2 if len(strikes) > 2 else 1),
            GuardChance=num(row, "GuardChance", 0.12),
            # Anything that closes behind a guard rather than waiting behind
            # one: the heavies, and the bosses.
            bGuardsWhileAdvancing=bool(boss or health >= 90),
            # Answering back straight away is the brawler's habit, not the
            # careful fighter's -- so it falls as guard rises.
            CounterChance=round(max(0.05, min(0.55,
                0.40 - num(row, "GuardChance", 0.12) * 0.5)), 2),
            Notes="Generated from DT_Fighters row '%s'. Edit the browser "
                  "project, re-export, re-run." % name,
        ))
    return out


def describe(attacks, talents, styles):
    print("\n%s/  — %d attacks" % (OUT, len(attacks)))
    for a in attacks:
        print("   %-22s %-28s dmg %-5s reach %-5s %s%s"
              % (a["asset"], a["AttackTag"], a["Damage"], a["Reach"],
                 "HEAVY " if a["bHeavy"] else "", "MULTI" if a["bMultiHit"] else ""))
    print("\n%s/  — %d talents" % (OUT, len(talents)))
    for t in talents:
        engine = "  (engine only)" if t["asset"].endswith(("Jump", "Climb")) else ""
        print("   %-22s %-26s %s%s" % (t["asset"], t["TalentTag"], t["DisplayName"], engine))

    print("\n%s/  — %d fight styles" % (OUT, len(styles)))
    for st in styles:
        print("   %-22s range %-6s discipline %-5s bounce %-5s circle %-5s combo %d"
              % (st["asset"], st["PreferredRange"], st["RangeDiscipline"],
                 st["BounceRate"], st["CircleTendency"], st["MaxComboLength"]))
        for k in st["Strikes"]:
            print("        %-10s %-22s w %-5s opener %s"
                  % (k["AttackRow"], "/".join(k["Bands"]), k["Weight"],
                     k["OpensCombination"]))


def build(attacks, talents, styles):
    import unreal  # noqa: E402

    EAL = unreal.EditorAssetLibrary
    AT = unreal.AssetToolsHelpers.get_asset_tools()

    def make(asset_name, cls):
        path = "%s/%s" % (OUT, asset_name)
        if EAL.does_asset_exist(path):
            EAL.delete_asset(path)      # generated: this script owns them
        factory = unreal.DataAssetFactory()
        factory.set_editor_property("data_asset_class", cls)
        return AT.create_asset(asset_name, OUT, cls, factory)

    for a in attacks:
        asset = make(a["asset"], unreal.AhmedAttackData)
        asset.set_editor_property("attack_tag", unreal.GameplayTag(a["AttackTag"]))
        asset.set_editor_property("display_name", unreal.Text(a["DisplayName"]))
        for key in ("Startup", "Active", "Recovery", "Damage", "Reach",
                    "DepthTolerance", "Knockback", "StaminaCost", "ManaCost",
                    "KnockdownChance", "MotionWarpDistance"):
            asset.set_editor_property(_snake(key), float(a[key]))
        asset.set_editor_property("b_heavy", bool(a["bHeavy"]))
        asset.set_editor_property("b_multi_hit", bool(a["bMultiHit"]))
        asset.set_editor_property("whoosh_cue", unreal.GameplayTag(a["WhooshCue"]))
        asset.set_editor_property("impact_cue", unreal.GameplayTag(a["ImpactCue"]))
        EAL.save_asset("%s/%s" % (OUT, a["asset"]))

    for t in talents:
        asset = make(t["asset"], unreal.AhmedTalentData)
        asset.set_editor_property("talent_tag", unreal.GameplayTag(t["TalentTag"]))
        asset.set_editor_property("display_name", unreal.Text(t["DisplayName"]))
        asset.set_editor_property("display_name_arabic", unreal.Text(t["DisplayNameArabic"]))
        asset.set_editor_property("icon", t["Icon"])
        asset.set_editor_property("description", unreal.Text(t["Description"]))
        asset.set_editor_property("mana_cost", float(t["ManaCost"]))
        EAL.save_asset("%s/%s" % (OUT, t["asset"]))

    BAND = dict(Out=unreal.RangeBand.OUT, Long=unreal.RangeBand.LONG,
                Mid=unreal.RangeBand.MID, Close=unreal.RangeBand.CLOSE)

    for st in styles:
        asset = make(st["asset"], unreal.AhmedFightStyleData)
        asset.set_editor_property("display_name", unreal.Text(st["DisplayName"]))
        asset.set_editor_property("notes", st["Notes"])
        for key in ("PreferredRange", "RangeDiscipline", "ResetDistance",
                    "BounceRate", "BounceAmplitude", "CircleTendency",
                    "CircleSwitchTime", "AttackInterval", "RhythmJitter",
                    "GuardChance", "CounterChance"):
            asset.set_editor_property(_snake(key), float(st[key]))
        asset.set_editor_property("max_combo_length", int(st["MaxComboLength"]))
        asset.set_editor_property("b_guards_while_advancing",
                                  bool(st["bGuardsWhileAdvancing"]))

        strikes = []
        for k in st["Strikes"]:
            strike = unreal.StyleStrike()
            strike.set_editor_property("attack_row", unreal.Name(k["AttackRow"]))
            strike.set_editor_property("bands", [BAND[b] for b in k["Bands"]])
            strike.set_editor_property("weight", float(k["Weight"]))
            strike.set_editor_property("opens_combination", float(k["OpensCombination"]))
            strikes.append(strike)
        asset.set_editor_property("strikes", strikes)
        EAL.save_asset("%s/%s" % (OUT, st["asset"]))

    unreal.log("Built %d attack, %d talent and %d style assets into %s"
               % (len(attacks), len(talents), len(styles), OUT))


def _snake(name):
    out = ""
    for i, c in enumerate(name):
        if c.isupper() and i and not name[i - 1].isupper():
            out += "_"
        out += c.lower()
    return out


if __name__ == "__main__" or True:
    _attacks = plan_attacks()
    _talents = plan_talents()
    _styles = plan_styles()
    try:
        import unreal  # noqa: F401
        build(_attacks, _talents, _styles)
    except ImportError:
        describe(_attacks, _talents, _styles)
        print("\n%d assets planned. Run inside the Unreal editor to build them."
              % (len(_attacks) + len(_talents) + len(_styles)))
