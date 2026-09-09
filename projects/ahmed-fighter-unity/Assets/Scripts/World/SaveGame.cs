using System.Collections.Generic;
using System.Globalization;
using System.Text;
using UnityEngine;
using Ahmed.Data;

namespace Ahmed.World
{
    /// <summary>
    /// Writing the world down, and reading it back.
    ///
    /// <see cref="Encode"/> and <see cref="Decode"/> are pure -- a string in,
    /// a string out, no storage and no scene -- so a round trip can be
    /// executed and checked without an editor, which matters more here than
    /// almost anywhere: a save format that loses a talent loses a player's
    /// run, and it does it silently.
    ///
    /// The format is lines of key=value, versioned on the first line, and it
    /// is hand-rolled rather than JsonUtility because what has to be stored is
    /// three sets and an array and JsonUtility serialises none of those. An
    /// unknown key is skipped rather than fatal, so a save written by a later
    /// build loads what it can instead of refusing.
    /// </summary>
    public static class SaveGame
    {
        public const string Key = "ahmed.halqa.save.v1";
        private const string Version = "v1";

        public static string Encode()
        {
            StringBuilder b = new StringBuilder();
            b.Append(Version).Append('\n');
            b.Append("xp=").Append(WorldState.Experience).Append('\n');
            b.Append("area=").Append(WorldState.CurrentArea).Append('\n');

            b.Append("cleared=");
            bool first = true;
            foreach (long k in WorldState.ClearedKeys)
            {
                if (!first) { b.Append(','); }
                b.Append(k.ToString(CultureInfo.InvariantCulture));
                first = false;
            }
            b.Append('\n');

            b.Append("areas=");
            first = true;
            foreach (int a in WorldState.ClearedAreaList)
            {
                if (!first) { b.Append(','); }
                b.Append(a);
                first = false;
            }
            b.Append('\n');

            b.Append("talents=");
            first = true;
            foreach (Ability t in WorldState.HeldTalents)
            {
                if (!first) { b.Append(','); }
                b.Append(t.ToString());
                first = false;
            }
            b.Append('\n');

            b.Append("up=");
            string[] tracks = System.Enum.GetNames(typeof(UpgradeTrack));
            for (int i = 0; i < tracks.Length; i++)
            {
                if (i > 0) { b.Append(','); }
                b.Append(tracks[i]).Append(':')
                 .Append(WorldState.UpgradeLevel((UpgradeTrack)i));
            }
            b.Append('\n');

            if (WorldState.HasCheckpoint)
            {
                Vector3 p = WorldState.CheckpointPosition;
                b.Append("cp=").Append(WorldState.CheckpointArea).Append('|')
                 .Append(F(p.x)).Append('|').Append(F(p.y)).Append('|').Append(F(p.z))
                 .Append('|').Append(F(WorldState.CheckpointHealth)).Append('\n');
            }
            return b.ToString();
        }

        /// <summary>Replaces the world with what the text says. False if the
        /// text is not a save this build understands, and in that case
        /// nothing is changed -- a corrupt string must not half-load.</summary>
        public static bool Decode(string text)
        {
            if (string.IsNullOrEmpty(text)) { return false; }
            string[] lines = text.Split('\n');
            if (lines.Length == 0 || lines[0].Trim() != Version) { return false; }

            WorldState.Reset();
            for (int i = 1; i < lines.Length; i++)
            {
                string line = lines[i].Trim();
                if (line.Length == 0) { continue; }
                int eq = line.IndexOf('=');
                if (eq <= 0) { continue; }
                string key = line.Substring(0, eq);
                string val = line.Substring(eq + 1);

                if (key == "xp") { WorldState.RestoreExperience(ParseInt(val, 0)); }
                else if (key == "area") { WorldState.CurrentArea = ParseInt(val, 0); }
                else if (key == "cleared")
                {
                    foreach (string s in Split(val))
                    {
                        long k;
                        if (long.TryParse(s, NumberStyles.Integer, CultureInfo.InvariantCulture, out k))
                        {
                            WorldState.RestoreClearedKey(k);
                        }
                    }
                }
                else if (key == "areas")
                {
                    foreach (string s in Split(val)) { WorldState.MarkAreaCleared(ParseInt(s, -1)); }
                }
                else if (key == "talents")
                {
                    foreach (string s in Split(val))
                    {
                        Ability a;
                        if (TryAbility(s, out a)) { WorldState.GrantTalent(a); }
                    }
                }
                else if (key == "up")
                {
                    foreach (string s in Split(val))
                    {
                        int colon = s.IndexOf(':');
                        if (colon <= 0) { continue; }
                        UpgradeTrack t;
                        if (TryTrack(s.Substring(0, colon), out t))
                        {
                            WorldState.SetUpgradeLevel(t, ParseInt(s.Substring(colon + 1), 0));
                        }
                    }
                }
                else if (key == "cp")
                {
                    string[] parts = val.Split('|');
                    if (parts.Length == 5)
                    {
                        WorldState.SetCheckpoint(ParseInt(parts[0], 0),
                            new Vector3(ParseFloat(parts[1]), ParseFloat(parts[2]),
                                        ParseFloat(parts[3])),
                            ParseFloat(parts[4]));
                    }
                }
            }
            return true;
        }

        // --------------------------------------------------------- the storage

        /// <summary>PlayerPrefs rather than a file: it is the one store that
        /// works the same on a desktop build and in a browser, and a save this
        /// small has no business owning a file handle.</summary>
        public static void Write()
        {
            PlayerPrefs.SetString(Key, Encode());
            PlayerPrefs.Save();
        }

        public static bool Read()
        {
            if (!PlayerPrefs.HasKey(Key)) { return false; }
            return Decode(PlayerPrefs.GetString(Key));
        }

        public static void Erase() { PlayerPrefs.DeleteKey(Key); }

        // ----------------------------------------------------------- utilities

        private static string F(float v)
        {
            return v.ToString("R", CultureInfo.InvariantCulture);
        }

        private static IEnumerable<string> Split(string v)
        {
            if (string.IsNullOrEmpty(v)) { yield break; }
            string[] parts = v.Split(',');
            for (int i = 0; i < parts.Length; i++)
            {
                if (parts[i].Length > 0) { yield return parts[i]; }
            }
        }

        private static int ParseInt(string s, int fallback)
        {
            int v;
            return int.TryParse(s, NumberStyles.Integer, CultureInfo.InvariantCulture, out v)
                ? v : fallback;
        }

        private static float ParseFloat(string s)
        {
            float v;
            return float.TryParse(s, NumberStyles.Float, CultureInfo.InvariantCulture, out v)
                ? v : 0f;
        }

        /// <summary>Enum.TryParse is not in the .NET profile this port targets,
        /// so the names are matched by hand. A name that is gone from a later
        /// build is skipped, not thrown.</summary>
        private static bool TryAbility(string s, out Ability a)
        {
            string[] names = System.Enum.GetNames(typeof(Ability));
            for (int i = 0; i < names.Length; i++)
            {
                if (names[i] == s) { a = (Ability)System.Enum.GetValues(typeof(Ability)).GetValue(i); return true; }
            }
            a = Ability.None;
            return false;
        }

        private static bool TryTrack(string s, out UpgradeTrack t)
        {
            string[] names = System.Enum.GetNames(typeof(UpgradeTrack));
            for (int i = 0; i < names.Length; i++)
            {
                if (names[i] == s) { t = (UpgradeTrack)i; return true; }
            }
            t = UpgradeTrack.Box;
            return false;
        }
    }
}
