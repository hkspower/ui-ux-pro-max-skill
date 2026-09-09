using System.Collections.Generic;
using UnityEngine;

namespace Ahmed.Game
{
    /// <summary>One row of Assets/Resources/Data/sounds.json.</summary>
    [System.Serializable]
    public class SoundRow
    {
        public string name;
        /// <summary>Resources path, without the extension.</summary>
        public string clip;
        public float volume = 1f;
        public float pitchMin = 1f;
        public float pitchMax = 1f;
        public bool spatial;
        /// <summary>Seconds this cue refuses to retrigger for.</summary>
        public float cooldown;
        /// <summary>Seconds from the start of the clip to its transient.
        /// A swing is fired this much before the blow lands, so the swish
        /// peaks on the first active frame rather than on the button.</summary>
        public float lead;
        public string description;
    }

    /// <summary>
    /// The game's sound, played by cue name.
    ///
    /// Nothing in the game names an audio file. It asks for `Hit_Heavy` and
    /// this decides which clip that is, how loud, how far the pitch may drift
    /// and how often it may retrigger — all of it from a table, so recasting a
    /// sound is a row and a file rather than a code change. That is the same
    /// contract the Unreal build's audio subsystem has, deliberately: the two
    /// ports should not disagree about what a punch sounds like.
    ///
    /// A cue with no clip logs once and stays silent. Missing audio must never
    /// be the thing that stops a build running.
    /// </summary>
    public static class AudioLibrary
    {
        /// <summary>How many sounds may overlap. A crowd fight throws a lot at
        /// once and the oldest voice is the right one to lose.</summary>
        private const int Voices = 24;

        [System.Serializable]
        private class Table { public SoundRow[] items; }

        private static readonly Dictionary<string, SoundRow> Rows =
            new Dictionary<string, SoundRow>();
        private static readonly Dictionary<string, AudioClip> Clips =
            new Dictionary<string, AudioClip>();
        private static readonly Dictionary<string, float> LastPlayed =
            new Dictionary<string, float>();
        private static readonly HashSet<string> Warned = new HashSet<string>();

        private static AudioSource[] _pool;
        private static int _next;
        private static bool _loaded;

        public static void Load()
        {
            if (_loaded) { return; }
            _loaded = true;                 // set first: a parse failure must not loop

            TextAsset asset = Resources.Load<TextAsset>("Data/sounds");
            if (asset == null)
            {
                Debug.LogError("[Ahmed] Data/sounds.json is missing. "
                    + "Run: node Tools/export/export.mjs");
                return;
            }
            Table t = JsonUtility.FromJson<Table>(asset.text);
            if (t != null && t.items != null)
            {
                for (int i = 0; i < t.items.Length; i++) { Rows[t.items[i].name] = t.items[i]; }
            }

            GameObject root = new GameObject("Ahmed Audio");
            Object.DontDestroyOnLoad(root);
            _pool = new AudioSource[Voices];
            for (int i = 0; i < Voices; i++)
            {
                // One object per voice rather than one object carrying all
                // twenty-four: a positioned cue moves the object it sits on,
                // and sources sharing a transform would all be dragged to
                // wherever the last punch landed.
                GameObject voice = new GameObject("Voice " + i);
                voice.transform.SetParent(root.transform, false);
                AudioSource src = voice.AddComponent<AudioSource>();
                src.playOnAwake = false;
                _pool[i] = src;
            }
        }

        /// <summary>A cue at a place in the world.</summary>
        public static void Play(string cue, Vector3 at)
        {
            Fire(cue, at, true);
        }

        /// <summary>A cue with no position — the interface, the stings.</summary>
        public static void PlayUI(string cue)
        {
            Fire(cue, Vector3.zero, false);
        }

        /// <summary>How far into a clip its transient sits, in seconds. Zero
        /// for a cue with no row, so a missing sound never delays a swing.</summary>
        public static float Lead(string cue)
        {
            Load();
            SoundRow row;
            return !string.IsNullOrEmpty(cue) && Rows.TryGetValue(cue, out row) ? row.lead : 0f;
        }

        private static void Fire(string cue, Vector3 at, bool positioned)
        {
            Load();
            if (string.IsNullOrEmpty(cue) || _pool == null) { return; }

            SoundRow row;
            if (!Rows.TryGetValue(cue, out row))
            {
                WarnOnce(cue, "no row in sounds.json");
                return;
            }

            // The cooldown is what stops a six-enemy fight turning every punch
            // into one continuous noise.
            float last;
            if (row.cooldown > 0f && LastPlayed.TryGetValue(cue, out last)
                && Time.time - last < row.cooldown)
            {
                return;
            }

            AudioClip clip = Resolve(row);
            if (clip == null) { return; }

            LastPlayed[cue] = Time.time;

            AudioSource src = _pool[_next];
            _next = (_next + 1) % _pool.Length;

            src.Stop();
            src.clip = clip;
            src.volume = row.volume;
            // Pitch drift is why one recording per cue is enough: a walk cycle
            // never sounds like the same footstep twice.
            src.pitch = row.pitchMin >= row.pitchMax
                ? row.pitchMin
                : Random.Range(row.pitchMin, row.pitchMax);
            src.spatialBlend = (positioned && row.spatial) ? 1f : 0f;
            src.transform.position = at;
            src.Play();
        }

        private static AudioClip Resolve(SoundRow row)
        {
            AudioClip clip;
            if (Clips.TryGetValue(row.name, out clip)) { return clip; }

            clip = Resources.Load<AudioClip>(row.clip);
            Clips[row.name] = clip;         // cache the miss too, so it warns once
            if (clip == null)
            {
                WarnOnce(row.name, "no clip at Resources/" + row.clip);
            }
            return clip;
        }

        private static void WarnOnce(string cue, string why)
        {
            if (Warned.Add(cue))
            {
                Debug.LogWarning("[Ahmed] sound '" + cue + "': " + why + " — staying silent");
            }
        }
    }
}
