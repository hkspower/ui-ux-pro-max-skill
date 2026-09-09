using System; using UnityEngine; using Ahmed.Data; using Ahmed.World;
public static class HubTest {
    static int fails = 0;
    static void Check(bool ok, string w) { if (!ok) { fails++; Console.WriteLine("  FAIL " + w); } }

    public static int Main() {
        // ---------------------------------------------------------- save format
        Console.WriteLine("SAVE");
        WorldState.Reset();
        WorldState.AddExperience(1234);
        WorldState.CurrentArea = 4;
        WorldState.MarkCleared(0, 2); WorldState.MarkCleared(0, 3); WorldState.MarkCleared(7, 1001);
        WorldState.MarkAreaCleared(0); WorldState.MarkAreaCleared(3);
        WorldState.GrantTalent(Ability.Vault); WorldState.GrantTalent(Ability.HawkFist);
        WorldState.SetUpgradeLevel(UpgradeTrack.Box, 3);
        WorldState.SetUpgradeLevel(UpgradeTrack.Stam, 5);
        WorldState.SetCheckpoint(2, new Vector3(-12.5f, 0f, 33.25f), 0.42f);
        string blob = SaveGame.Encode();

        WorldState.Reset();
        Check(WorldState.Experience == 0 && !WorldState.HasCheckpoint, "reset really clears");
        Check(SaveGame.Decode(blob), "a save this build wrote loads");
        Check(WorldState.Experience == 1234, "experience survives");
        Check(WorldState.CurrentArea == 4, "current area survives");
        Check(WorldState.IsCleared(0,2) && WorldState.IsCleared(0,3) && WorldState.IsCleared(7,1001), "cleared sites survive");
        Check(!WorldState.IsCleared(0,4), "a site never cleared stays uncleared");
        Check(WorldState.IsAreaCleared(0) && WorldState.IsAreaCleared(3) && !WorldState.IsAreaCleared(5), "cleared areas survive");
        Check(WorldState.HasTalent(Ability.Vault) && WorldState.HasTalent(Ability.HawkFist), "talents survive");
        Check(!WorldState.HasTalent(Ability.PowerKick), "a talent never found stays unfound");
        Check(WorldState.TalentCount == 2, "exactly the talents that were held");
        Check(WorldState.UpgradeLevel(UpgradeTrack.Box) == 3 && WorldState.UpgradeLevel(UpgradeTrack.Stam) == 5, "bought levels survive");
        Check(WorldState.UpgradeLevel(UpgradeTrack.Spd) == 0, "an untouched track stays at zero");
        Check(WorldState.HasCheckpoint && WorldState.CheckpointArea == 2, "the checkpoint's area survives");
        Check((WorldState.CheckpointPosition - new Vector3(-12.5f,0f,33.25f)).magnitude < 1e-4f, "the checkpoint's position survives to the millimetre");
        Check(Math.Abs(WorldState.CheckpointHealth - 0.42f) < 1e-5f, "the checkpoint's condition survives");
        Check(SaveGame.Encode() == blob, "re-encoding is byte identical");

        // a save with no checkpoint, and the empty case
        WorldState.Reset(); string empty = SaveGame.Encode();
        Check(SaveGame.Decode(empty) && !WorldState.HasCheckpoint && WorldState.Experience == 0, "a fresh world round trips");
        Check(!SaveGame.Decode(null) && !SaveGame.Decode("") && !SaveGame.Decode("garbage"), "junk is refused");
        Check(!SaveGame.Decode("v9\nxp=5\n"), "a version this build does not know is refused");
        WorldState.Reset(); WorldState.AddExperience(77);
        Check(SaveGame.Decode("v1\nxp=9\nnosuchkey=whatever\ntalents=Vault,NotAnAbility\n"), "an unknown key is skipped, not fatal");
        Check(WorldState.Experience == 9 && WorldState.HasTalent(Ability.Vault) && WorldState.TalentCount == 1, "and what it did understand is loaded");
        // storage round trip through the prefs
        WorldState.Reset(); WorldState.AddExperience(500); WorldState.SetUpgradeLevel(UpgradeTrack.Kick, 2);
        SaveGame.Write(); WorldState.Reset();
        Check(SaveGame.Read() && WorldState.Experience == 500 && WorldState.UpgradeLevel(UpgradeTrack.Kick) == 2, "written and read back from storage");
        SaveGame.Erase(); Check(!SaveGame.Read(), "erased means no save");

        // ------------------------------------------------------- the economy
        Console.WriteLine("\nECONOMY");
        Check(!UpgradeStore.CanBuy(0, 5, 120, 119), "one short of the price buys nothing");
        Check(UpgradeStore.CanBuy(0, 5, 120, 120), "exactly the price buys");
        Check(!UpgradeStore.CanBuy(5, 5, 640, 99999), "the cap cannot be passed");
        Check(!UpgradeStore.CanBuy(0, 5, -1, 99999), "a track with no price in the table cannot be bought");
        Check(UpgradeStore.CanBuy(4, 5, 640, 640), "the last level can be bought");
        Check(!UpgradeStore.CanBuy(0, 5, 120, 0), "nothing earned buys nothing");
        // spending never goes negative, and a refused purchase spends nothing
        WorldState.Reset(); WorldState.AddExperience(100);
        Check(!WorldState.SpendExperience(101) && WorldState.Experience == 100, "an unaffordable spend takes nothing");
        Check(WorldState.SpendExperience(100) && WorldState.Experience == 0, "an affordable spend takes exactly the price");
        Check(!WorldState.SpendExperience(-5), "a negative spend is refused");
        // with no table loaded (no Resources here) a buy must refuse, not throw
        WorldState.Reset(); WorldState.AddExperience(99999);
        Check(!UpgradeStore.Buy(UpgradeTrack.Box), "no price table means no purchase");
        Check(WorldState.Experience == 99999 && WorldState.UpgradeLevel(UpgradeTrack.Box) == 0, "and nothing was taken");

        // ------------------------------------------------------------ effects
        Console.WriteLine("\nEFFECTS");
        PlayerRow row = new PlayerRow{ baseHealth=100f, baseStamina=100f, baseMoveSpeed=3.408f,
            healthPerVitality=18f, staminaPerStamina=12f, speedPerSpeed=0.216f, upgradeMaxLevel=5 };
        WorldState.Reset();
        Check(Math.Abs(UpgradeStore.MaxHealth(row) - 100f) < 1e-4f, "no vitality is the base health");
        WorldState.SetUpgradeLevel(UpgradeTrack.Vit, 5);
        Check(Math.Abs(UpgradeStore.MaxHealth(row) - 190f) < 1e-4f, "five vitality is +90 health");
        WorldState.SetUpgradeLevel(UpgradeTrack.Stam, 5);
        Check(Math.Abs(UpgradeStore.MaxStamina(row) - 160f) < 1e-4f, "five stamina is +60 stamina");
        WorldState.SetUpgradeLevel(UpgradeTrack.Spd, 5);
        Check(Math.Abs(UpgradeStore.MoveSpeed(row) - (3.408f + 1.08f)) < 1e-4f, "five speed is +1.08 m/s");
        WorldState.Reset(); WorldState.SetUpgradeLevel(UpgradeTrack.Box, 3);
        Check(Math.Abs(UpgradeStore.DamageMultiplier(AttackFamily.Box) - 1.30f) < 1e-5f, "three boxing is +30% on a punch");
        Check(Math.Abs(UpgradeStore.DamageMultiplier(AttackFamily.Kick) - 1.00f) < 1e-5f, "and nothing on a kick");
        WorldState.SetUpgradeLevel(UpgradeTrack.Kick, 2);
        Check(Math.Abs(UpgradeStore.DamageMultiplier(AttackFamily.Kick) - 1.20f) < 1e-5f, "two kicking is +20% on a kick");

        // ---------------------------------------------------------------- hub
        Console.WriteLine("\nHUB");
        int hubs = 0; Site hub = null;
        for (int i = 0; i < TestData.Areas.Length; i++) {
            District d = District.Build(i, TestData.Areas[i], TestData.Stages[i]);
            foreach (Site s in d.Sites) if (s.Kind == SiteKind.Hub) { hubs++; if (i == 0) hub = s; }
        }
        Check(hubs == 1, "exactly one hub in the whole world (" + hubs + ")");
        Check(hub != null && hub.Position.magnitude < 1e-6f, "and it is at the centre of the starting district");
        District souq = District.Build(0, TestData.Areas[0], TestData.Stages[0]);
        float worst = float.MaxValue;
        foreach (Site s in souq.Sites) {
            if (s.Kind != SiteKind.Encounter) continue;
            worst = Math.Min(worst, s.Position.magnitude - s.Radius - hub.Radius);
        }
        Check(worst > 0f, "nothing wakes while Ahmed stands in the hub (" + worst.ToString("0.0") + " m of clear ground)");
        Console.WriteLine("  quiet ground between the hub's edge and the first ambush: " + worst.ToString("0.0") + " m");

        Console.WriteLine(fails == 0 ? "\nall hub checks passed" : "\n" + fails + " FAILURES");
        return fails == 0 ? 0 : 1;
    }
}
