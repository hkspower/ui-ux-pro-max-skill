using System.Collections.Generic;
using UnityEngine;
using Ahmed.Data;

namespace Ahmed.Combat
{
    /// <summary>
    /// Who is allowed to swing right now.
    ///
    /// At most a couple of enemies may be attacking at once and the rest
    /// circle. That single rule is what makes a crowd fair rather than a
    /// pile-on, and it is the reason a fight against six people is readable.
    ///
    /// It used to live on the wave director, which meant an enemy had to know
    /// about the thing running the stage in order to throw a punch. In an open
    /// world there is no single director -- encounters come and go across nine
    /// districts -- so the pool lives here instead, and the fighters ask it
    /// directly.
    /// </summary>
    public static class CrowdControl
    {
        private static readonly List<Fighter> Holders = new List<Fighter>();

        /// <summary>
        /// Claim the right to swing. Holders no longer mid-attack are pruned
        /// on every call, so a token cannot be leaked by someone interrupted
        /// or killed halfway through a swing -- which would otherwise quietly
        /// reduce the crowd to one attacker for the rest of the fight.
        /// </summary>
        public static bool TryClaim(Fighter claimant)
        {
            if (claimant == null) { return false; }

            for (int i = Holders.Count - 1; i >= 0; i--)
            {
                Fighter f = Holders[i];
                if (f == null || !f.IsAlive || f.State != FighterState.Attack)
                {
                    Holders.RemoveAt(i);
                }
            }
            if (Holders.Contains(claimant)) { return true; }
            if (Holders.Count >= Playfield.MaxSimultaneousAttackers) { return false; }
            Holders.Add(claimant);
            return true;
        }

        public static void Release(Fighter claimant)
        {
            Holders.Remove(claimant);
        }

        /// <summary>Wipe the pool. Called when a district unloads, so bodies
        /// that no longer exist cannot hold a token against the next fight.</summary>
        public static void Clear()
        {
            Holders.Clear();
        }

        public static int Attacking { get { return Holders.Count; } }
    }
}
