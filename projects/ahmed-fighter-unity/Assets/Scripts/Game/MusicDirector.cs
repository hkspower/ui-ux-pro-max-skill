using UnityEngine;

namespace Ahmed.Game
{
    /// <summary>
    /// The music. One cue at a time, crossfaded, looping.
    ///
    /// The world tells it which floor Ahmed is on and whether a title fight
    /// is live; it decides nothing itself. Cues are rows of sounds.json like
    /// every other sound in the game -- `Music_Stage`, `Music_Under`,
    /// `Music_Up`, `Music_Boss` -- so recasting a track is a row and a file.
    /// Two sources rather than one, because a loop that stops dead so the
    /// next can start is the one thing a listener always hears.
    /// </summary>
    public class MusicDirector : MonoBehaviour
    {
        public static MusicDirector Current { get; private set; }

        /// <summary>Seconds one track takes to hand over to the next.</summary>
        public float Crossfade = 1.6f;

        /// <summary>What is playing, by cue name. Empty when nothing is.</summary>
        public string Playing { get; private set; }

        private AudioSource _a, _b;
        private bool _toB;
        private float _targetA, _targetB;

        private void Awake()
        {
            Current = this;
            _a = MakeSource("Music A");
            _b = MakeSource("Music B");
            Playing = "";
        }

        private void OnDestroy()
        {
            if (Current == this) { Current = null; }
        }

        private AudioSource MakeSource(string name)
        {
            GameObject go = new GameObject(name);
            go.transform.SetParent(transform, false);
            AudioSource src = go.AddComponent<AudioSource>();
            src.playOnAwake = false;
            src.loop = true;
            src.spatialBlend = 0f;
            src.volume = 0f;
            return src;
        }

        /// <summary>Hand over to this cue. Asking for the one already playing
        /// does nothing, so the world can say it every frame if it likes.</summary>
        public void Play(string cue)
        {
            if (cue == Playing) { return; }
            AudioClip clip; float volume;
            if (!AudioLibrary.Music(cue, out clip, out volume))
            {
                Stop();
                return;
            }
            Playing = cue;
            _toB = !_toB;
            AudioSource next = _toB ? _b : _a;
            next.clip = clip;
            next.volume = 0f;
            next.Play();
            _targetA = _toB ? 0f : volume;
            _targetB = _toB ? volume : 0f;
        }

        public void Stop()
        {
            Playing = "";
            _targetA = 0f;
            _targetB = 0f;
        }

        private void Update()
        {
            float step = Crossfade > 0f ? Time.deltaTime / Crossfade : 1f;
            _a.volume = Mathf.MoveTowards(_a.volume, _targetA, step);
            _b.volume = Mathf.MoveTowards(_b.volume, _targetB, step);
            if (_a.volume <= 0f && _targetA <= 0f && _a.isPlaying) { _a.Stop(); }
            if (_b.volume <= 0f && _targetB <= 0f && _b.isPlaying) { _b.Stop(); }
        }

        /// <summary>The cue for a floor: the street, the cellar, the roofs.</summary>
        public static string CueForLevel(int level)
        {
            return level < 0 ? "Music_Under" : level > 0 ? "Music_Up" : "Music_Stage";
        }
    }
}
