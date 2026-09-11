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
        /// once, and the one to lose is the furthest away.</summary>
        private const int Voices = 24;

        /// <summary>
        /// How sound carries. Inside <see cref="NearDistance"/> a cue is at
        /// its own volume — that is a fight, and a fight should be at full
        /// strength. Past <see cref="FarDistance"/> it is not played at all:
        /// a district is 260 m across and a punch thrown at the far rim of it
        /// is not something you can hear, let alone act on.
        ///
        /// Unity's own defaults are 1 m and 500 m, which in a field this size
        /// means every fight in the district arrives at once, all of it
        /// roughly as loud as the one you are in.
        /// </summary>
        public const float NearDistance = 6f;
        public const float FarDistance = 70f;

        /// <summary>Where the ears are. Set by whatever owns the camera; a
        /// zero listener just means everything is measured from the origin,
        /// which is wrong rather than broken.</summary>
        public static Transform Listener;

        private static Vector3 ListenerAt
        {
            get { return Listener != null ? Listener.position : Vector3.zero; }
        }

        [System.Serializable]
        private class Table { public SoundRow[] items; }

        private static readonly Dictionary<string, SoundRow> Rows =
            new Dictionary<string, SoundRow>();
        private static readonly Dictionary<string, AudioClip> Clips =
            new Dictionary<string, AudioClip>();
        /// <summary>When a cue last played, and how far from the ears it was.
        /// Both, because a cooldown that only knows the time silences the
        /// punch landing on your face for one thrown across the district.</summary>
        private static readonly Dictionary<string, float> LastPlayed =
            new Dictionary<string, float>();
        private static readonly Dictionary<string, float> LastDistance =
            new Dictionary<string, float>();
        private static readonly HashSet<string> Warned = new HashSet<string>();

        private static AudioSource[] _pool;
        private static AudioLowPassFilter[] _lowPass = new AudioLowPassFilter[Voices];
        private static AudioReverbFilter[] _reverb = new AudioReverbFilter[Voices];
        private static readonly float[] _playingAt = new float[Voices];
        private static int _space;
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
                src.rolloffMode = AudioRolloffMode.Logarithmic;
                src.minDistance = NearDistance;
                src.maxDistance = FarDistance;
                // No doppler. A whoosh is a fighter's arm, not a passing car,
                // and pitching it by closing speed makes every exchange warble.
                src.dopplerLevel = 0f;
                src.spread = 25f;
                _pool[i] = src;
                _lowPass[i] = voice.AddComponent<AudioLowPassFilter>();
                _reverb[i] = voice.AddComponent<AudioReverbFilter>();
            }
            SetSpace(0);
        }

        /// <summary>
        /// What the place does to a sound. A cellar is not a street: the same
        /// punch under a district is duller and rings, and on the roofs it is
        /// dry and open. The world calls this when Ahmed changes floor, and
        /// the sound changes with the place rather than the place being a
        /// change of scenery with the same audio over it.
        /// </summary>
        public static void SetSpace(int level)
        {
            Load();
            if (_pool == null) { return; }
            float cutoff = level < 0 ? 3200f : level > 0 ? 22000f : 12000f;
            AudioReverbPreset preset = level < 0 ? AudioReverbPreset.StoneRoom
                                     : level > 0 ? AudioReverbPreset.Plain
                                                 : AudioReverbPreset.City;
            for (int i = 0; i < _pool.Length; i++)
            {
                if (_lowPass[i] != null) { _lowPass[i].cutoffFrequency = cutoff; }
                if (_reverb[i] != null) { _reverb[i].reverbPreset = preset; }
            }
            _space = level;
        }

        /// <summary>The floor the sound is currently coloured for.</summary>
        public static int Space { get { return _space; } }

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

        /// <summary>A music row's clip and level, for the director. False
        /// and null for a cue with no row or no file -- the director goes
        /// quiet rather than the game going wrong.</summary>
        public static bool Music(string cue, out AudioClip clip, out float volume)
        {
            Load();
            clip = null; volume = 0f;
            SoundRow row;
            if (string.IsNullOrEmpty(cue) || !Rows.TryGetValue(cue, out row))
            {
                WarnOnce(cue ?? "(null)", "no row in sounds.json");
                return false;
            }
            clip = Resolve(row);
            volume = row.volume;
            return clip != null;
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

            bool spatial = positioned && row.spatial;
            float distance = spatial ? Flat(at, ListenerAt) : 0f;

            // Too far to hear. Not "played quietly" -- not played, so it does
            // not take a voice off a fight that is actually happening.
            if (spatial && distance > FarDistance) { return; }

            if (!Claims(cue, row.cooldown, distance)) { return; }

            AudioClip clip = Resolve(row);
            if (clip == null) { return; }

            LastPlayed[cue] = Time.time;
            LastDistance[cue] = distance;

            AudioSource src = Voice(distance);
            if (src == null) { return; }

            src.Stop();
            src.clip = clip;
            src.volume = row.volume;
            // Pitch drift is why one recording per cue is enough: a walk cycle
            // never sounds like the same footstep twice.
            src.pitch = row.pitchMin >= row.pitchMax
                ? row.pitchMin
                : Random.Range(row.pitchMin, row.pitchMax);
            src.spatialBlend = spatial ? 1f : 0f;
            // Nearer is more important, and a voice is stolen by priority.
            src.priority = spatial ? Mathf.Clamp(64 + Mathf.RoundToInt(distance), 0, 255) : 32;
            src.transform.position = at;
            src.Play();
            _playingAt[System.Array.IndexOf(_pool, src)] = spatial ? distance : 0f;
        }

        /// <summary>Distance on the ground plane. Height is not how far away
        /// a thing sounds in a game where a fighter is two metres tall and a
        /// district is two hundred across.</summary>
        private static float Flat(Vector3 a, Vector3 b)
        {
            float dx = a.x - b.x, dz = a.z - b.z;
            return Mathf.Sqrt(dx * dx + dz * dz);
        }

        /// <summary>
        /// Whether a cue may sound, given how recently it last did and from
        /// how far away.
        ///
        /// The cooldown is what stops a six-enemy fight turning every punch
        /// into one continuous noise. On its own, though, it hands the cue to
        /// whichever fighter happened to swing first — so a blow landing on
        /// Ahmed goes silent because something across the district connected
        /// forty milliseconds earlier. A closer instance takes the cue off a
        /// further one; an equally distant one waits its turn.
        ///
        /// Pure, so the rule can be checked without a scene.
        /// </summary>
        public static bool MayPlay(float sinceLast, float cooldown,
                                   float distance, float lastDistance)
        {
            if (cooldown <= 0f || sinceLast >= cooldown) { return true; }
            return distance < lastDistance - NearDistance;
        }

        private static bool Claims(string cue, float cooldown, float distance)
        {
            float last, lastDistance;
            if (!LastPlayed.TryGetValue(cue, out last)) { return true; }
            if (!LastDistance.TryGetValue(cue, out lastDistance)) { lastDistance = 0f; }
            return MayPlay(Time.time - last, cooldown, distance, lastDistance);
        }

        /// <summary>
        /// A voice for a sound this far off. A free one first; failing that
        /// the one carrying the most distant sound, and only if this one is
        /// nearer than that. Round-robin stealing cut whatever was oldest,
        /// which in a crowd is reliably the blow you are standing next to.
        /// </summary>
        private static AudioSource Voice(float distance)
        {
            int furthest = -1;
            float worst = distance;
            for (int i = 0; i < _pool.Length; i++)
            {
                if (!_pool[i].isPlaying) { return _pool[i]; }
                if (_playingAt[i] > worst) { worst = _playingAt[i]; furthest = i; }
            }
            return furthest >= 0 ? _pool[furthest] : null;
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
