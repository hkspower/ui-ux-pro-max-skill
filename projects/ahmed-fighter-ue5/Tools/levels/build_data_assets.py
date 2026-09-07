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


def describe(attacks, talents):
    print("\n%s/  — %d attacks" % (OUT, len(attacks)))
    for a in attacks:
        print("   %-22s %-28s dmg %-5s reach %-5s %s%s"
              % (a["asset"], a["AttackTag"], a["Damage"], a["Reach"],
                 "HEAVY " if a["bHeavy"] else "", "MULTI" if a["bMultiHit"] else ""))
    print("\n%s/  — %d talents" % (OUT, len(talents)))
    for t in talents:
        engine = "  (engine only)" if t["asset"].endswith(("Jump", "Climb")) else ""
        print("   %-22s %-26s %s%s" % (t["asset"], t["TalentTag"], t["DisplayName"], engine))


def build(attacks, talents):
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

    unreal.log("Built %d attack and %d talent assets into %s"
               % (len(attacks), len(talents), OUT))


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
    try:
        import unreal  # noqa: F401
        build(_attacks, _talents)
    except ImportError:
        describe(_attacks, _talents)
        print("\n%d assets planned. Run inside the Unreal editor to build them."
              % (len(_attacks) + len(_talents)))
