#!/usr/bin/env python3
"""SAUD -- cut a music render into a seamless loop
==============================================================================
    python3 Tools/audio/loop_cut.py RENDER OUT.wav --bpm 120 [--bars 30]
        [--xfade 1.5] [--lufs -16.0] [--skip 0]
    python3 Tools/audio/loop_cut.py RENDER OUT.wav --whole [--lufs -16.0]
    python3 Tools/audio/loop_cut.py --bite

The four loops in Content/Audio/Music were cut by hand with ffmpeg on
2026-09-10 and the README says the tool for it did not exist. This is it,
written 2026-09-28 (Riyadh) for the title theme and the recast stage loop:
the same cut, measured and checked instead of eyeballed.

What it does, in order, all in numpy over an ffmpeg decode:

  1. Decodes RENDER to 48 kHz stereo float.
  2. Finds the BODY of the render: a 50 ms RMS envelope, and the body starts
     where it first holds 60 % of its 90th percentile -- past any intro the
     model played.
  3. Finds where to OPEN the window: the start, in the four bars after the
     body begins, whose first two bars' onsets (spectral flux) are most like
     the two bars past the window's end -- the seam the check below measures.
  4. Takes a window of --bars bars (bars x 4 x 60 / bpm seconds; 30 bars at
     120 BPM is exactly 60 s) plus --xfade seconds of tail, and crossfades
     the tail into the head with an equal-power curve, so the loop's end runs
     into its own start.
  5. Loudness-normalises to --lufs (ITU BS.1770 via ffmpeg's ebur128 on the
     cut, then a gain), so the Volume column in DT_Sounds sets the level and
     the file carries the same loudness as the other loops.
  6. Writes 48 kHz, stereo, 16-bit PCM.

And it checks, and refuses the file if any check fails:

  * BAR-ALIGNED: the onset pattern over the two bars at the start of the
    window correlates with the pattern two bars past its end (r >= 0.5): the
    loop length is a whole number of bars of THIS render, not of the BPM the
    prompt asked for.
  * SEAMLESS: the sample-to-sample step across the seam (last sample to
    first) is at or below the loop's mean step, the README's own rule.
  * LEVEL: integrated loudness within 0.5 LU of --lufs; true peak under
    -1 dBTP.
  * NO SILENCE: no 500 ms window of the loop under -40 dBFS RMS.

--whole is for a piece with an intro and an ending (the title theme): the
loop is the render trimmed to where it rises out of and sinks back into
silence (-50 dBFS), with 20 ms ramps at the ends and no crossfade -- the
piece plays through and its intro follows after the breath the model
left. Its checks: the seam lies in a fade (the 1.5 s either side under
-25 dBFS RMS), the seam step, the level, and any silence (under -40 dBFS)
is at most 2.5 s and only at the seam.

--bite proves each check fails when the thing it guards is broken (a
window off the bar grid, a hard cut with no crossfade, no level, a gap of
silence) -- on a synthetic render this script makes itself, so the bite
needs no ElevenLabs credit. Nobody here can listen to the result; the
checks are what stands in for that.
"""
import argparse, json, math, os, subprocess, sys, tempfile
import numpy as np

SR = 48000
XFADE = 1.5


def decode(path, sr=SR):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(sr), "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(np.float64)


def encode(path, x, sr=SR):
    pcm = np.clip(x, -1.0, 1.0)
    pcm = (pcm * 32767.0).round().astype("<i2").tobytes()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ac", "2", "-ar", str(sr), "-i", "-", path],
                   input=pcm, check=True)


def rms_env(x, win=0.05, sr=SR):
    m = x.mean(axis=1)
    n = int(win * sr)
    k = len(m) // n
    e = np.sqrt((m[: k * n].reshape(k, n) ** 2).mean(axis=1))
    return e, win


def onsets(x, hop=0.01, sr=SR):
    """Spectral flux: how much each 10 ms frame's spectrum rose over the last."""
    m = x.mean(axis=1)
    n = 2048; h = int(hop * sr)
    win = np.hanning(n)
    frames = (len(m) - n) // h
    prev = None; out = np.zeros(frames)
    for i in range(frames):
        s = np.abs(np.fft.rfft(m[i * h: i * h + n] * win))
        if prev is not None:
            out[i] = np.maximum(s - prev, 0.0).sum()
        prev = s
    return out, hop


def body_start(x):
    e, win = rms_env(x)
    ref = np.percentile(e, 90) * 0.60
    hold = int(1.0 / win)                     # a full second above the line, not a hit
    for i in range(len(e) - hold):
        if (e[i: i + hold] >= ref).all():
            return i * win
    return 0.0


def downbeat(x, t0, bar, seconds):
    """Where to open the window: the start, in the four bars after the body
    begins, whose two opening bars are most like the two bars past the
    window's end -- the seam the check measures. The strongest onset was
    tried first and is not it: on the stage render it opened 2.75 bars off
    the best seam (r 0.54 against 0.82 at 30 bars)."""
    o, hop = onsets(x)
    two = int(2 * bar / hop); best = (-2.0, t0)
    for st in np.arange(t0, t0 + 4 * bar, hop):
        s0, s1 = int(st / hop), int((st + seconds) / hop)
        p, q = o[s0: s0 + two], o[s1: s1 + two]
        if len(q) < two: break
        r = float(np.corrcoef(p, q)[0, 1])
        if r > best[0]: best = (r, float(st))
    return best[1]


def edges(x, floor_db=-60.0, win=0.05, sr=SR):
    """The first and last moment the render is above `floor_db`: the model
    pads a piece with digital silence at both ends."""
    e, w = rms_env(x, win)
    db = 20 * np.log10(e + 1e-9)
    on = np.nonzero(db > floor_db)[0]
    return (on[0] * w, (on[-1] + 1) * w) if len(on) else (0.0, len(x) / sr)


def loudness(path):
    p = subprocess.run(["ffmpeg", "-nostats", "-hide_banner", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    tail = p[p.rfind("Integrated loudness"):]
    I = float(tail.split("I:")[1].split("LUFS")[0])
    peak = float(tail.split("Peak:")[1].split("dBFS")[0])
    return I, peak


def cut(x, start, seconds, xfade=XFADE, sr=SR):
    n, f = int(seconds * sr), int(xfade * sr)
    a = int(start * sr)
    body = x[a: a + n].copy()
    tail = x[a + n: a + n + f]
    t = np.linspace(0.0, 1.0, len(tail))[:, None]
    body[: len(tail)] = body[: len(tail)] * np.sin(t * math.pi / 2) + tail * np.cos(t * math.pi / 2)
    return body


def check(loop, x, start, seconds, bar, lufs, path, assert_=True):
    o, hop = onsets(x)
    two = int(2 * bar / hop); s0 = int(start / hop); s1 = int((start + seconds) / hop)
    p, q = o[s0: s0 + two], o[s1: s1 + two]
    r = float(np.corrcoef(p, q)[0, 1]) if len(p) == len(q) and len(p) > 8 else 0.0
    mono = loop.mean(axis=1)
    step = float(np.abs(np.diff(mono)).mean())
    seam = float(abs(mono[0] - mono[-1]))
    I, peak = loudness(path)
    e, win = rms_env(loop, 0.5)
    floor = float(20 * np.log10(max(e.min(), 1e-9)))
    out = dict(bar_corr=r, seam=seam, mean_step=step, lufs=I, peak_dbtp=peak, floor_dbfs=floor)
    if assert_:
        assert r >= 0.5, "not bar-aligned: onsets at the seam correlate %.2f, want 0.5" % r
        assert seam <= step, "seam: the step across it is %.5f against a mean step of %.5f" % (seam, step)
        assert abs(I - lufs) <= 0.5, "level: %.1f LUFS, want %.1f" % (I, lufs)
        assert peak <= -1.0, "peak: %.1f dBTP, want under -1" % peak
        assert floor >= -40.0, "silence: a half second at %.0f dBFS" % floor
    return out


def make(render, out, bpm, bars, xfade, lufs, skip=0.0):
    x = decode(render)
    bar = 4 * 60.0 / bpm
    seconds = bars * bar
    t0 = max(body_start(x), skip)
    start = downbeat(x, t0, bar, seconds)
    need = start + seconds + xfade
    assert need <= len(x) / SR, "the render is %.1f s; the window needs %.1f" % (len(x) / SR, need)
    loop = cut(x, start, seconds, xfade)
    with tempfile.TemporaryDirectory() as d:
        tmp = os.path.join(d, "cut.wav")
        encode(tmp, loop)
        I, _ = loudness(tmp)
        gain = 10 ** ((lufs - I) / 20.0)
        loop = loop * gain
        peak = np.abs(loop).max()
        if peak > 10 ** (-1.0 / 20):                # -1 dBTP: the level backs off, and the check says so
            loop = loop * (10 ** (-1.0 / 20) / peak)
    encode(out, loop)
    info = check(loop, x, start, seconds, bar, lufs, out, assert_=False)
    info.update(start=start, seconds=seconds, bars=bars, bpm=bpm, render_seconds=len(x) / SR)
    return info


def check_whole(loop, lufs, path, edge=1.5, assert_=True):
    """A whole piece played through and restarted: the seam lies in silence
    or a fade -- the last and first `edge` seconds are each under -25 dBFS
    RMS, so nothing musical is cut; the seam step; the level; and any
    silence (under -40 dBFS) is at most 2.5 s and only at the seam, the
    breath between plays."""
    mono = loop.mean(axis=1); f = int(edge * SR)
    head_db = float(20 * np.log10(np.sqrt((mono[:f] ** 2).mean()) + 1e-9))
    tail_db = float(20 * np.log10(np.sqrt((mono[-f:] ** 2).mean()) + 1e-9))
    step = float(np.abs(np.diff(mono)).mean()); seam = float(abs(mono[0] - mono[-1]))
    I, peak = loudness(path)
    e, win = rms_env(loop, 0.5)
    db = 20 * np.log10(e + 1e-9)
    quiet = np.nonzero(db < -40.0)[0]
    n = len(e); away = [i for i in quiet if min(i, n - 1 - i) * win > 3.0]
    out = dict(head_dbfs=head_db, tail_dbfs=tail_db, seam=seam, mean_step=step, lufs=I, peak_dbtp=peak,
               quiet_seconds=len(quiet) * win, quiet_away=len(away) * win)
    if assert_:
        assert max(head_db, tail_db) <= -25.0, "the seam is in the music: %.0f dBFS before it, %.0f after, want a fade under -25" % (tail_db, head_db)
        assert seam <= step, "seam: the step across it is %.5f against a mean step of %.5f" % (seam, step)
        assert abs(I - lufs) <= 0.5, "level: %.1f LUFS, want %.1f" % (I, lufs)
        assert peak <= -1.0, "peak: %.1f dBTP, want under -1" % peak
        assert len(quiet) * win <= 2.5, "silence: %.1f s under -40 dBFS, want 2.5 at most" % (len(quiet) * win)
        assert not away, "silence: %.1f s under -40 dBFS away from the seam" % (len(away) * win)
    return out


def make_whole(render, out, lufs, floor_db=-50.0, ramp=0.02):
    """The whole piece as a loop: trimmed to where it rises out of and sinks
    back into silence (`floor_db`), 20 ms raised-cosine ramps at both ends
    against a click, no crossfade -- the piece ends, and its intro follows
    after the breath the model left (the title theme)."""
    x = decode(render)
    a, b = edges(x, floor_db)
    loop = x[int(a * SR): int(b * SR)].copy()
    r = int(ramp * SR)
    w = 0.5 - 0.5 * np.cos(np.linspace(0.0, math.pi, r))[:, None]
    loop[:r] *= w; loop[-r:] *= w[::-1]
    with tempfile.TemporaryDirectory() as d:
        tmp = os.path.join(d, "cut.wav"); encode(tmp, loop)
        I, _ = loudness(tmp)
        loop = loop * 10 ** ((lufs - I) / 20.0)
        peak = np.abs(loop).max()
        if peak > 10 ** (-1.0 / 20): loop = loop * (10 ** (-1.0 / 20) / peak)
    encode(out, loop)
    info = check_whole(loop, lufs, out, assert_=False)
    info.update(start=a, end=b, seconds=len(loop) / SR, render_seconds=len(x) / SR)
    return info


def synth(path, bpm=120.0, seconds=100.0, intro=6.0):
    """A render to bite on: a bar-marked drum pattern under a drone, with a
    quiet intro, so every check has something real to measure."""
    rng = np.random.default_rng(1)
    t = np.arange(int(seconds * SR)) / SR
    beat = 60.0 / bpm
    x = 0.05 * np.sin(2 * np.pi * 73.42 * t)       # D2 drone (the browser's souq root)
    for k in range(int(seconds / beat)):
        at = k * beat
        if at < intro: continue
        amp = 0.8 if k % 8 == 0 else (0.5 if k % 2 == 0 else 0.25)
        i = int(at * SR); n = int(0.12 * SR)
        env = np.exp(-np.arange(n) / (0.03 * SR)) * np.minimum(np.arange(n) / (0.002 * SR), 1.0)   # a 2 ms attack
        x[i: i + n] += amp * env * np.sin(2 * np.pi * (55 if k % 2 == 0 else 180) * np.arange(n) / SR)
        x[i: i + n] += 0.15 * env * rng.standard_normal(n)
        m = int(0.4 * SR)                                # a bass note under every beat, so the body is loud
        x[i: i + m] += 0.45 * np.sin(2 * np.pi * 73.42 * np.arange(m) / SR) * np.hanning(m)
    tail = t > seconds - 6.0                          # the ending fades over six seconds
    x[tail] *= np.clip((seconds - t[tail]) / 6.0, 0.0, 1.0) ** 2
    x = np.stack([x, x], axis=1)
    encode(path, x * 0.5)


def bite():
    with tempfile.TemporaryDirectory() as d:
        r = os.path.join(d, "render.wav"); synth(r)
        # -24, not the real loops' -16: the synthetic drums are all transient,
        # and -16 LUFS under a -1 dBTP peak is out of their reach
        x = decode(r); bar = 2.0; lufs = -24.0
        cases = []
        def case(label, loop, start, seconds, expect):
            p = os.path.join(d, label.replace(" ", "_") + ".wav"); encode(p, loop)
            try:
                check(loop, x, start, seconds, bar, lufs, p)
                cases.append((label, expect is None, "passes"))
            except AssertionError as e:
                cases.append((label, expect is not None and expect in str(e), str(e)))
        info = make(r, os.path.join(d, "clean.wav"), 120.0, 30, XFADE, lufs)
        assert abs(info["lufs"] - lufs) <= 0.5, "the synthetic clean loop did not reach %.0f LUFS: %.1f" % (lufs, info["lufs"])
        clean = decode(os.path.join(d, "clean.wav"))
        case("clean (must pass)", clean, info["start"], info["seconds"], None)
        s = info["start"]
        off = cut(x, s, info["seconds"] + 0.7, XFADE)     # 0.7 s past the bar: a window off the grid
        off *= np.abs(clean).max() / np.abs(off).max()
        case("bar-aligned", off, s, info["seconds"] + 0.7, "not bar-aligned")
        hard = x[int(s * SR): int((s + info["seconds"]) * SR)].copy()  # no crossfade
        hard *= np.abs(clean).max() / np.abs(hard).max()
        hard[-1] = 0.9; hard[0] = -0.9                    # a hard cut lands on a hot sample
        case("seamless", hard, s, info["seconds"], "seam")
        case("level", clean * 0.3, s, info["seconds"], "level")
        gap = clean.copy(); gap[int(20 * SR): int(21 * SR)] = 0.0
        case("no silence", gap, s, info["seconds"], "silence")
        # the whole piece
        info = make_whole(r, os.path.join(d, "whole.wav"), lufs)
        whole = decode(os.path.join(d, "whole.wav"))
        def wcase(label, loop, expect):
            p = os.path.join(d, label.replace(" ", "_") + ".wav"); encode(p, loop)
            try:
                check_whole(loop, lufs, p)
                cases.append((label, expect is None, "passes"))
            except AssertionError as e:
                cases.append((label, expect is not None and expect in str(e), str(e)))
        wcase("whole clean (must pass)", whole, None)
        mid = x[int(10 * SR): int(70 * SR)].copy()       # the seam dropped into the loud body
        mid *= np.abs(whole).max() / np.abs(mid).max()
        wcase("whole seam in a fade", mid, "in the music")
        gap = whole.copy(); gap[int(30 * SR): int(31 * SR)] = 0.0
        wcase("whole silence at the seam only", gap, "away from the seam")
    print("\n%-20s %s" % ("check", "when the loop is broken -- and when it is not"))
    for label, ok, msg in cases:
        print("  %-18s %s  %s" % (label, "OK     " if ok else "WRONG  ", msg[:90]))
    n = sum(1 for _, ok, _ in cases if ok)
    print("  %d of %d as they should be" % (n, len(cases)))
    return n == len(cases)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("render", nargs="?"); ap.add_argument("out", nargs="?")
    ap.add_argument("--bpm", type=float, default=120.0); ap.add_argument("--bars", type=int, default=30)
    ap.add_argument("--xfade", type=float, default=XFADE); ap.add_argument("--lufs", type=float, default=-16.0)
    ap.add_argument("--skip", type=float, default=0.0, help="start the search for the body no earlier than this")
    ap.add_argument("--whole", action="store_true", help="loop the whole piece, trimmed to its own silence (the title theme)")
    ap.add_argument("--bite", action="store_true")
    a = ap.parse_args()
    if a.bite:
        sys.exit(0 if bite() else 1)
    if a.whole:
        info = make_whole(a.render, a.out, a.lufs)
        print(json.dumps(info, indent=1))
        check_whole(decode(a.out), a.lufs, a.out)
        print("whole ok: %.1f s (%.2f-%.2f s of a %.1f s render); %.1f LUFS, the seam at %.0f / %.0f dBFS, %.1f s quiet at it" % (
            info["seconds"], info["start"], info["end"], info["render_seconds"], info["lufs"], info["tail_dbfs"], info["head_dbfs"], info["quiet_seconds"]))
        return
    info = make(a.render, a.out, a.bpm, a.bars, a.xfade, a.lufs, a.skip)
    print(json.dumps(info, indent=1))
    x = decode(a.render); loop = decode(a.out)
    check(loop, x, info["start"], info["seconds"], 4 * 60.0 / a.bpm, a.lufs, a.out)
    print("loop ok: %d bars at %.0f BPM, %.1f s from %.2f s of a %.1f s render; %.1f LUFS, seam %.5f <= step %.5f, onsets r %.2f" % (
        a.bars, a.bpm, info["seconds"], info["start"], info["render_seconds"], info["lufs"], info["seam"], info["mean_step"], info["bar_corr"]))


if __name__ == "__main__":
    main()
