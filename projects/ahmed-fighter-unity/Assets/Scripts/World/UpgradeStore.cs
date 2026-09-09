using Ahmed.Data;

namespace Ahmed.World
{
    /// <summary>
    /// What experience buys, and what it is worth once bought.
    ///
    /// The tables were exported and never read: experience accumulated in
    /// WorldState and there was nothing to spend it on, so half of what the
    /// story says the game is -- "upgrades are him choosing what kind of
    /// fighter he becomes here" -- had no mechanism behind it. This is that
    /// mechanism, and it is deliberately free of the scene so the economy can
    /// be executed and checked without an editor.
    ///
    /// The numbers are the browser build's, through the exporter: the price
    /// of a level comes from upgrades.json and the effects come from the
    /// player row, so nothing here decides a balance figure.
    /// </summary>
    public static class UpgradeStore
    {
        /// <summary>Ten per cent a level on the matching attack family, which
        /// is the one effect the player row has no field for because the
        /// browser build spells it at the damage site too.</summary>
        public const float DamagePerLevel = 0.10f;

        public static int MaxLevel
        {
            get
            {
                PlayerRow row = GameData.Player;
                return row != null && row.upgradeMaxLevel > 0 ? row.upgradeMaxLevel : 5;
            }
        }

        /// <summary>What the next level of this track costs, or -1 if it is
        /// already at the cap.</summary>
        public static int NextCost(UpgradeTrack track)
        {
            int next = WorldState.UpgradeLevel(track) + 1;
            if (next > MaxLevel) { return -1; }
            return GameData.UpgradeCost(track, next);
        }

        public static bool CanAfford(UpgradeTrack track)
        {
            int cost = NextCost(track);
            return cost >= 0 && WorldState.Experience >= cost;
        }

        /// <summary>
        /// Whether a purchase is allowed, as arithmetic: at the cap, no; no
        /// price in the table, no; not enough earned, no. Pure and separate
        /// from the world so the rule can be executed and checked, the same
        /// split the solver and the save format use.
        /// </summary>
        public static bool CanBuy(int level, int maxLevel, int cost, int experience)
        {
            return level < maxLevel && cost >= 0 && experience >= cost;
        }

        /// <summary>
        /// Buy one level. False and nothing spent if the track is capped, the
        /// price is missing, or the experience is not there -- a caller that
        /// forgot to check must not be able to take the money anyway.
        /// </summary>
        public static bool Buy(UpgradeTrack track)
        {
            int level = WorldState.UpgradeLevel(track);
            int cost = NextCost(track);
            if (!CanBuy(level, MaxLevel, cost, WorldState.Experience)) { return false; }
            if (!WorldState.SpendExperience(cost)) { return false; }
            WorldState.SetUpgradeLevel(track, level + 1);
            return true;
        }

        // ------------------------------------------------------------- effects

        /// <summary>Multiplier on a strike of this family.</summary>
        public static float DamageMultiplier(AttackFamily family)
        {
            UpgradeTrack track = family == AttackFamily.Kick
                ? UpgradeTrack.Kick : UpgradeTrack.Box;
            return 1f + WorldState.UpgradeLevel(track) * DamagePerLevel;
        }

        public static float MaxHealth(PlayerRow row)
        {
            return Base(row != null ? row.baseHealth : 100f)
                 + WorldState.UpgradeLevel(UpgradeTrack.Vit)
                   * (row != null ? row.healthPerVitality : 0f);
        }

        public static float MaxStamina(PlayerRow row)
        {
            return Base(row != null ? row.baseStamina : 100f)
                 + WorldState.UpgradeLevel(UpgradeTrack.Stam)
                   * (row != null ? row.staminaPerStamina : 0f);
        }

        public static float MoveSpeed(PlayerRow row)
        {
            float basis = row != null && row.baseMoveSpeed > 0f ? row.baseMoveSpeed : 3.4f;
            return basis + WorldState.UpgradeLevel(UpgradeTrack.Spd)
                         * (row != null ? row.speedPerSpeed : 0f);
        }

        private static float Base(float v) { return v > 0f ? v : 100f; }
    }
}
