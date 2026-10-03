#!/usr/bin/env python3
"""SAUD -- master a music cue onto a measured curve, and refuse it if a check fails
==============================================================================
    python3 Tools/audio/master_music.py IN.wav OUT.wav [--lufs -15.7] [--target theme] [--keep DIR]
    python3 Tools/audio/master_music.py --check IN.wav [--ref SRC.wav] [--stage1 EQ.wav] [--target theme] [--lufs -15.7]
    python3 Tools/audio/master_music.py --bite

Written 2026-09-30 (Riyadh) for the title theme. `M_Menu.wav` is an 84 s
whole piece cut by loop_cut.py --whole from a 90 s ElevenLabs Music v2
render that exists only as a 192 kbps MP3, and the author asked for its
low, mid and high to be improved. Nobody here can listen, so "improved" is
against a written target curve (below) and every rule here is a number: the
cut measured 60-120 Hz +6.6 dB and 125 Hz +4.6 over the target (the D2
tonic, 73.4 Hz, piles into the 80 Hz band), 5-16 kHz 3.8-7.5 dB under it,
a 100 Hz-10 kHz density slope of -19.7 dB/decade against M_Boss's -16.2,
and its -20 dB bandwidth point at 12.5 kHz. Three mastering chains were
built and measured against the same script on 2026-09-28/30; this is the
one that won (B "classic", with its low-band ratio 2.0 -> 1.5), ported
whole with the constants the judge measured, nothing grafted on.

The chain, four ffmpeg 6.1 passes of stock filters (all IIR, minimum
phase: no pre-ringing on the taiko hits) and a numpy pass, deterministic
(the same input rebuilds the same file sample for sample on this ffmpeg):

  1. HPF + EQ    highpass 28 Hz; the boom cut with two bells (76 Hz on the
                 tonic, 128 Hz on the drum's body) and the dip their skirts
                 leave at 100 Hz filled; a broad presence lift at 3.5 kHz;
                 a high shelf from 6 kHz and a bell at 12.5 kHz for the dull
                 top -- the bell stays under the MP3's 16 kHz lowpass, and
                 nothing above it is invented.
  2. 3-band      acrossover (Linkwitz-Riley 4th order at 150 Hz and 2.5 kHz,
     compress    the same three bands the crest factors are read in) into
                 three acompressors and back through amix with normalize
                 off: the lows held at the climax (at most 2.1 dB), the
                 mids glued, the highs barely.
  3. widen       extrastereo on the > 2.5 kHz band only, inside the same
                 graph (a second crossover pass cost +0.7 dB of pre-echo):
                 a side gain, so the mono sum is untouched by construction.
  4. limit+level gain to the target loudness, alimiter at a -2 dBFS sample
                 ceiling (no auto-level), a re-trim, the 20 ms raised-cosine
                 ramps of loop_cut.make_whole put back at both ends so the
                 seam samples are 0 again, 16-bit PCM without dither, as the
                 shipped loops were made.

The target ("theme"): 1/3-octave band POWER of the mono sum (Welch PSD,
65536-pt Hann, 50 % overlap, 48 kHz) in dB relative to the mean of the ten
bands 250 Hz-2 kHz -- on this display pink noise reads flat. A bass plateau
+5..+8 dB from 50 to 125 Hz peaking at 63-80 Hz (taiko and the tonic), the
mids within +1.5/-2 of their own mean, -1 dB per 1/3-octave above 2 kHz
(-3 dB/oct band power, -6 dB/oct density) to 10 kHz, steeper above because
the source's MP3 lowpass sits near 16 kHz. It is a model constrained by two
published slopes -- Pestana et al., AES paper 8960 (2013): about -5 dB/oct
density from 100 Hz to 4 kHz in mastered commercial music; ProSoundWeb,
"An Examination Of Bandwidth, Dynamic Range And Normal Operating Levels":
about -6 dB/oct above 1 kHz in classical -- and by the game's own family:
M_Boss, the epic-drums reference, sits inside its tolerance at every scored
band. Both citations were reached as search snippets only (the hosts are
egress-blocked from here), so the curve is not a transcription of a
published orchestral spectrum, and the docstring says so because nothing
else can. Tolerances: +-4 dB at 40-50 Hz, +-3 at 63-200, +-2.5 from 250 Hz
to 10 kHz, +-4 at 12.5 kHz, +-6 at 16 kHz (that band is half outside the
MP3's lowpass). A second named target can be added to TARGETS; only
"theme" exists.

After mastering it measures the output and REFUSES it (OUT is written as
OUT.rejected.wav, exit 1) if any of these fails:

  * LEVEL      integrated loudness (ffmpeg ebur128) within 0.5 LU of --lufs.
  * PEAK       true peak <= -1 dBTP twice over: ebur128's 4x-oversampled
               true peak, and this script's own 4x FFT oversampling.
  * CLEAN      no run of 3+ samples at or over 0.999; no run of 8+ identical
               samples above 0.25 (a clip that was turned down afterwards).
  * WHOLE      loop_cut.check_whole still holds: head and tail (1.5 s) under
               -25 dBFS RMS, the seam step at or under the mean step, level,
               peak, silence under -40 dBFS at most 2.5 s and only at the
               seam.
  * RAMPS      the first and last samples are 0 and the first and last 2 ms
               are under -50 dBFS RMS: the 20 ms ramps are there.
  * CURVE      every scored 1/3-octave band within the target's tolerance.
  * MOVE       no band moved more than 8 dB on the target's display
               (mid-referenced; the absolute move is printed beside it).
  * PUMPING    two probes: the standard deviation of the first difference of
               the momentary (400 ms) loudness series at most 1.4x the
               source's; and, against the chain's own stage-1 file (so the
               EQ's re-weighting of sections is out of it), the 100 ms RMS
               ratio, lag-aligned and median-removed, swings at most 3 dB
               inside any 1 s -- the rule that refused the unfixed chain
               (3.26 dB) and passed this one (2.36).
  * PRE-ECHO   the mean over the 20 strongest onsets of 10 log10(energy in
               the 15 ms before / the 15 ms after) at most the source's
               + 2 dB.
  * MONO       the loudness lost when both channels are replaced by their
               sum (mono-sum loss) within 1 LU of the source's.
  * INTRO      the quietest 500 ms inside the first 15 s lifted at most 6 dB
               over the source's: no noise floor pulled up under the intro.
  * PLR        true peak minus loudness within 2 dB of the source's.
  * SILENCE    the seconds under -40 dBFS (500 ms blocks) within 1 s of the
               source's: the breath the model left at the end is still there.

--check measures a file against the same rules and exits 1 on a failure;
the rules that need the source are n/a unless --ref gives it, and the swing
rule needs the chain's stage-1 file (--stage1, kept by --keep): against the
source it reads the EQ's re-weighting of the sections as well (3.97 dB on
the theme), so with only --ref that number is printed as information.

--bite makes a synthetic mix (noise shaped onto the target curve, drum hits
at 120 BPM, a quiet 8-bar intro, a fade-out and 1.5 s of silence), breaks
one thing at a time -- a boosted band, a hard clip turned back down, a
pumping compressor, pre-echo from a symmetric (linear-phase) FIR, a noise
floor under the intro, a broken end ramp, the end silence filled, the level
off, a widener that cancels in mono -- and shows the check that guards it
fails, and that the unbroken mix passes (10 of 10). The chain itself is
proved on the real file, not in the bite: on material already on the curve
it would only move it off.

numpy + ffmpeg 6.1 only (no scipy). Imports decode/encode/loudness/onsets/
check_whole from loop_cut.py in this folder. The measurement code is the
2026-09-28 measure.py that judged the chains, moved in here so the tool
depends on nothing outside Tools/audio.

Unverified: nobody has heard the result; what "better" means here is the
curve above and the rules above. The MP3's 16 kHz lowpass cannot be undone
and is not attempted. The 6 kHz shelf lifts the MP3's own 4-16 kHz coding
artefacts by the same 4-8 dB as the content, and no probe here can see
that. A different ffmpeg build may not reproduce the file sample for
sample.
"""
import argparse, math, os, shutil, subprocess, sys, tempfile
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loop_cut  # noqa: E402

SR = 48000

# ------------------------------------------------------------------ targets
TARGETS = {
    "theme": dict(
        lufs=-15.7,              # the cut's own level and the other loops' (-15.2..-16.0)
        curve={                  # 1/3-octave band power, dB rel. the 250 Hz-2 kHz mean; None = no requirement
            25: None, 31.5: None,
            40: 1.0, 50: 5.0, 63: 7.0, 80: 8.0, 100: 6.0, 125: 5.0, 160: 4.0, 200: 2.5,
            250: 1.5, 315: 1.5, 400: 1.0, 500: 0.5, 630: 0.0, 800: 0.0, 1000: 0.0, 1250: -1.0, 1600: -1.5, 2000: -2.0,
            2500: -3.0, 3150: -4.0, 4000: -5.0, 5000: -6.0, 6300: -7.0, 8000: -8.5, 10000: -10.0, 12500: -13.0, 16000: -20.0,
            20000: None},
        tolerance={
            40: 4.0, 50: 4.0, 63: 3.0, 80: 3.0, 100: 3.0, 125: 3.0, 160: 3.0, 200: 3.0,
            250: 2.5, 315: 2.5, 400: 2.5, 500: 2.5, 630: 2.5, 800: 2.5, 1000: 2.5, 1250: 2.5, 1600: 2.5, 2000: 2.5,
            2500: 2.5, 3150: 2.5, 4000: 2.5, 5000: 2.5, 6300: 2.5, 8000: 2.5, 10000: 2.5, 12500: 4.0, 16000: 6.0},
        what="epic orchestral / taiko title theme from a 192 kbps MP3 render; a model curve on two published slopes "
             "(-5 dB/oct density 100 Hz-4 kHz, -6 dB/oct above 1 kHz) that M_Boss lies inside at every band; 2026-09-28"),
}

# ------------------------------------------------------------------ the chain (the judged constants, 2026-09-30)
TP_CEILING_DBTP = -1.0        # check_whole's and the target's true-peak rule
LIMIT_DBFS = -2.0             # alimiter sample ceiling: 1 dB under the rule for inter-sample peaks and the re-trim; keeps PLR near the cut's 12.6 (rule: within 2 dB)
RAMP_S = 0.020                # loop_cut.make_whole's 20 ms raised-cosine ends, put back after the chain (an IIR tail lands on the last sample)
# stage 1: HPF + EQ
HPF_HZ = 28.0                 # 2-pole high-pass: nothing musical under the 40 Hz band; 25 and 31.5 Hz are unscored
BOOM1_HZ, BOOM1_Q, BOOM1_DB = 76.0, 3.2, -6.0    # the D2 tonic (73.4 Hz) piles into the 80 Hz band: +6.6 dB over target in the cut
BOOM2_HZ, BOOM2_Q, BOOM2_DB = 128.0, 3.5, -4.0   # the 125 Hz band, +4.6 over target
FILL_HZ, FILL_Q, FILL_DB = 100.0, 4.0, 2.5       # the two cuts' skirts meet in the 100 Hz band (-0.4 in the cut, -3.2 after them alone): put back
PRES_HZ, PRES_Q, PRES_DB = 3500.0, 0.8, 1.5      # presence: 4 kHz was -2.2, 5 kHz -4.0
SHELF_HZ, SHELF_Q, SHELF_DB = 6000.0, 0.6, 4.5   # the dull top: 5-10 kHz were -4.0..-5.4 under target
AIR_HZ, AIR_Q, AIR_DB = 12500.0, 1.2, 3.0        # 12.5 kHz -7.5 and 16 kHz -7.0; the bell stays under the MP3's 16 kHz lowpass
# stage 2: 3-band compression
XOVER = "150 2500"            # the three bands the crest factors are read in (<150, 150-2.5k, >2.5k)
LOW_THR_DBFS, LOW_RATIO, LOW_ATT_MS, LOW_REL_MS = -19.0, 1.5, 30.0, 300.0     # p90 of the low band's 400 ms RMS after EQ (-19.2): only the climax is held; 1.5 not 2.0 -- at 2.0 the low band swung 3.26 dB in 1 s after the taiko entries, at 1.5 2.36
MID_THR_DBFS, MID_RATIO, MID_ATT_MS, MID_REL_MS = -19.0, 1.6, 15.0, 200.0     # p90 of the mid band: glue, not control
HIGH_THR_DBFS, HIGH_RATIO, HIGH_ATT_MS, HIGH_REL_MS = -23.0, 1.3, 10.0, 120.0  # p97 of the high band: the loudest cymbal swells only; a 10 ms attack lets the hit through
KNEE = 4.0                    # ffmpeg's knee is a ratio: 4 = a 12 dB soft knee around the threshold
# stage 3: widening
WIDEN_M = 1.1                 # extrastereo side x1.1 above 2.5 kHz only; x1.2 read -2.20 LU of mono-sum loss against the rule's -2.30 floor
# stage 4: limiter
LIM_ATT_MS, LIM_REL_MS = 5.0, 60.0   # alimiter lookahead attack / release; a safety, not a sound

# ------------------------------------------------------------------ the rules' margins
LEVEL_LU = 0.5                # |LUFS - target|
FULL_SCALE = 0.999            # a sample at or over this is full scale
FLAT_TOP = 0.25               # 8+ identical samples above this: a clip turned down afterwards
RAMP_EDGE_DBFS = -50.0        # the first / last 2 ms
MOVE_DB = 8.0                 # no 1/3-octave band moved more than this on the target's display
PUMP_X = 1.4                  # momentary-loudness pumping std, x the source's
SWING_DB = 3.0                # 100 ms RMS ratio vs stage 1, max swing inside 1 s
PRE_ECHO_DB = 2.0             # over the source's
MONO_LU = 1.0                 # mono-sum loss under the source's
INTRO_DB = 6.0                # the quietest 500 ms of the first 15 s, over the source's
PLR_DB = 2.0                  # |PLR - source's|
PLR_FOLLOW = 1.0              # --loop-file: the limiter's ceiling at most this over the source's PLR
SILENCE_S = 1.0               # |quiet seconds - source's|

# ------------------------------------------------------------------ measurement constants (measure.py, 2026-09-28)
NFFT = 65536
THIRDS = [25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800,
          1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000]
COARSE = [(20, 60), (60, 120), (120, 250), (250, 500), (500, 1000), (1000, 2000), (2000, 4000),
          (4000, 8000), (8000, 12000), (12000, 16000), (16000, 20000)]
SPLIT = {"low": (0.0, 150.0), "mid": (150.0, 2500.0), "high": (2500.0, SR / 2)}
MID_REF = [250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000]
GATE = -50.0                  # LUFS: momentary samples under this are the silence
INTRO_S = 15.0                # where the intro ends for the quietest-window probe
PRE_MS = 0.015


def db(x):
    return 10.0 * math.log10(max(float(x), 1e-30))


def db2lin(x):
    return 10 ** (x / 20.0)


# ------------------------------------------------------------------ the chain

def ffmpeg(src, args, dst):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src] + args + ["-c:a", "pcm_f32le", dst], check=True)


def stage1_filter():
    return ",".join([
        "highpass=f=%g:p=2" % HPF_HZ,
        "equalizer=f=%g:t=q:w=%g:g=%g" % (BOOM1_HZ, BOOM1_Q, BOOM1_DB),
        "equalizer=f=%g:t=q:w=%g:g=%g" % (BOOM2_HZ, BOOM2_Q, BOOM2_DB),
        "equalizer=f=%g:t=q:w=%g:g=%g" % (FILL_HZ, FILL_Q, FILL_DB),
        "equalizer=f=%g:t=q:w=%g:g=%g" % (PRES_HZ, PRES_Q, PRES_DB),
        "highshelf=f=%g:t=q:w=%g:g=%g" % (SHELF_HZ, SHELF_Q, SHELF_DB),
        "equalizer=f=%g:t=q:w=%g:g=%g" % (AIR_HZ, AIR_Q, AIR_DB),
    ])


# --fit (2026-10-03): stage 1 fitted to the file rather than the theme's own
# measured faults. The source is first set to the target loudness (so the
# compressors' thresholds below mean what they meant on the theme), then a
# third-octave bell on every scored band up to 12.5 kHz that is more than
# FIT_DEADBAND off the target, at FIT_SHARE of its deviation, re-measured and
# corrected FIT_PASSES times. Bells only (IIR, minimum phase), each held to
# FIT_CUT_DB / FIT_BOOST_DB, so no band can be dug out or blown up.
FIT_DEADBAND = 0.75           # dB off the target before a band gets a bell
FIT_SHARE = 0.8               # of the deviation a bell takes back each pass
FIT_PASSES = 3
FIT_Q = 4.32                  # a third of an octave
FIT_CUT_DB, FIT_BOOST_DB = -8.0, 6.0
FIT_TOP_HZ = 12500            # nothing above: an MP3's lowpass is not a band to boost


def fitted_stage1(src, target, lufs, work, notes):
    """The fitted stage-1 filter for `src`, and the bells it chose."""
    I, _ = loop_cut.loudness(src)
    pre = lufs - I
    bands = [b for b in scored(target) if b <= FIT_TOP_HZ]
    gains = {b: 0.0 for b in bands}

    def chain():
        parts = ["volume=%.4fdB" % pre, "highpass=f=%g:p=2" % HPF_HZ]
        parts += ["equalizer=f=%g:t=q:w=%g:g=%.3f" % (b, FIT_Q, g) for b, g in gains.items() if abs(g) >= 0.05]
        return ",".join(parts)
    probe = os.path.join(work, "fit_probe.wav")
    for k in range(FIT_PASSES + 1):
        ffmpeg(src, ["-af", chain()], probe)
        rel = spectrum(loop_cut.decode(probe).mean(axis=1))["thirds_rel"]
        devs = {b: rel[b] - target["curve"][b] for b in bands}
        if k == FIT_PASSES:
            break
        for b, d in devs.items():
            if abs(d) > FIT_DEADBAND or abs(gains[b]) > 0.0:
                gains[b] = max(FIT_CUT_DB, min(FIT_BOOST_DB, gains[b] - FIT_SHARE * d))
    os.remove(probe)
    notes.append("stage 1 fitted: pre-gain %+.2f dB to %.1f LUFS; bells " % (pre, lufs) + " ".join(
        "%g:%+.1f" % (b, g) for b, g in gains.items() if abs(g) >= 0.05))
    return chain()


def comp(thr_dbfs, ratio, att, rel):
    return "acompressor=threshold=%.6f:ratio=%g:attack=%g:release=%g:knee=%g:detection=rms:makeup=1" % (
        db2lin(thr_dbfs), ratio, att, rel, KNEE)


def stage23_filter(widen=WIDEN_M):
    """Stages 2 and 3 are one graph: the crossover, three compressors, the
    widener on the top band, and the sum."""
    return ("[0:a]acrossover=split=%s:order=4th[l][m][h];"
            "[l]%s[l2];[m]%s[m2];[h]%s,extrastereo=m=%g:c=0[h2];"
            "[l2][m2][h2]amix=inputs=3:normalize=0" % (
                XOVER, comp(LOW_THR_DBFS, LOW_RATIO, LOW_ATT_MS, LOW_REL_MS),
                comp(MID_THR_DBFS, MID_RATIO, MID_ATT_MS, MID_REL_MS),
                comp(HIGH_THR_DBFS, HIGH_RATIO, HIGH_ATT_MS, HIGH_REL_MS), widen))


def ramps(x, ramp=RAMP_S):
    r = int(ramp * SR)
    w = 0.5 - 0.5 * np.cos(np.linspace(0.0, math.pi, r))[:, None]
    x[:r] *= w; x[-r:] *= w[::-1]
    return x


def stage4(src, dst, lufs, notes, ramp=True, limit_dbfs=LIMIT_DBFS):
    I, _ = loop_cut.loudness(src)
    gain = lufs - I
    tmp = dst + ".limited.wav"
    ffmpeg(src, ["-af", "volume=%.4fdB,alimiter=limit=%.6f:attack=%g:release=%g:level=0" % (
        gain, db2lin(limit_dbfs), LIM_ATT_MS, LIM_REL_MS)], tmp)
    x = loop_cut.decode(tmp)
    I2, tp2 = loop_cut.loudness(tmp)
    trim = lufs - I2
    x *= db2lin(trim)
    if ramp:
        x = ramps(x)
    loop_cut.encode(dst, x)
    I3, tp3 = loop_cut.loudness(dst)
    if tp3 > TP_CEILING_DBTP:                     # the ceiling is a rule: the level backs off and says so
        x *= db2lin(TP_CEILING_DBTP - tp3)
        loop_cut.encode(dst, x)
        I3, tp3 = loop_cut.loudness(dst)
        notes.append("true peak %.2f dBTP after the trim: scaled down to the ceiling, %.1f LUFS" % (tp3, I3))
    notes.append("stage 4: gain %+.2f dB (%.1f -> %.1f LUFS), limiter left %.1f LUFS / %.2f dBTP, re-trim %+.2f dB, final %.1f LUFS / %.2f dBTP, sample peak %.4f" % (
        gain, I, lufs, I2, tp2, trim, I3, tp3, abs(x).max()))
    os.remove(tmp)
    return x


def run_chain(src, dst, lufs, workdir, fit=None, ramp=True, limit_dbfs=LIMIT_DBFS):
    """The four stages; returns the final float array, the stage-1 array
    (the pumping probe's reference) and the notes. `fit` is the target to fit
    stage 1 to (--fit); None is the theme's own judged EQ."""
    s1 = os.path.join(workdir, "stage1_eq.wav")
    s3 = os.path.join(workdir, "stage3_mbcomp_widen.wav")
    notes = []
    ffmpeg(src, ["-af", fitted_stage1(src, fit, lufs, workdir, notes) if fit else stage1_filter()], s1)
    ffmpeg(s1, ["-filter_complex", stage23_filter()], s3)
    x = stage4(s3, dst, lufs, notes, ramp, limit_dbfs)
    return x, loop_cut.decode(s1), notes


# ------------------------------------------------------------------ measurement (measure.py, 2026-09-28)

def ebur128(path, mono=False):
    af = "ebur128=peak=true"
    if mono:
        af = "pan=stereo|c0=0.5*c0+0.5*c1|c1=0.5*c0+0.5*c1," + af
    p = subprocess.run(["ffmpeg", "-nostats", "-hide_banner", "-i", path, "-af", af, "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    M = []
    for line in p.splitlines():
        if "TARGET:" in line and " M:" in line and " S:" in line:
            try:
                M.append(float(line.split("M:")[1].split()[0]))
            except (IndexError, ValueError):
                continue
    tail = p[p.rfind("Integrated loudness"):]
    return dict(I=float(tail.split("I:")[1].split("LUFS")[0]), lra=float(tail.split("LRA:")[1].split("LU")[0]),
                tp=float(tail.split("Peak:")[1].split("dBFS")[0]), M=np.array(M))


def true_peak_4x(x, block=1 << 16, pad=512):
    """The sample peak of the signal 4x oversampled by FFT zero-padding, in
    blocks with `pad` samples of context each side: the inter-sample peaks
    ebur128 also estimates, found a second way."""
    n = len(x); peak = 0.0
    for c in range(x.shape[1]):
        for a in range(0, n, block):
            lo, hi = max(0, a - pad), min(n, a + block + pad)
            seg = x[lo:hi, c]; m = len(seg)
            X = np.fft.rfft(seg)
            Y = np.zeros(2 * m + 1, dtype=complex); Y[: len(X)] = X
            up = np.fft.irfft(Y, n=4 * m) * 4.0
            peak = max(peak, float(np.abs(up[4 * (a - lo): 4 * (min(n, a + block) - lo)]).max()))
    return 20 * math.log10(max(peak, 1e-9))


def window_rms(x, seconds, hop=0.1):
    p = (x ** 2).mean(axis=1)
    n, h = int(seconds * SR), int(hop * SR)
    c = np.concatenate([[0.0], np.cumsum(p)])
    starts = np.arange(0, len(p) - n + 1, h)
    return starts / SR, 10 * np.log10(np.maximum((c[starts + n] - c[starts]) / n, 1e-30))


def welch(m):
    w = np.hanning(NFFT); hop = NFFT // 2
    k = (len(m) - NFFT) // hop + 1
    acc = np.zeros(NFFT // 2 + 1)
    for i in range(k):
        acc += np.abs(np.fft.rfft(m[i * hop: i * hop + NFFT] * w)) ** 2
    psd = acc / k * 2.0 / (SR * (w ** 2).sum())
    psd[0] /= 2; psd[-1] /= 2
    return np.fft.rfftfreq(NFFT, 1.0 / SR), psd


def band_power(f, psd, lo, hi):
    sel = (f >= lo) & (f < hi)
    return float(psd[sel].sum() * (f[1] - f[0]))


def spectrum(m):
    f, psd = welch(m)
    thirds, dens = {}, {}
    for n, lab in enumerate(THIRDS):
        fc = 1000.0 * 10 ** ((n - 16) / 10.0)
        lo, hi = fc * 10 ** (-1 / 20.0), min(fc * 10 ** (1 / 20.0), SR / 2)
        p = band_power(f, psd, lo, hi)
        thirds[lab] = db(p); dens[lab] = db(p / (hi - lo))
    mid = float(np.mean([thirds[b] for b in MID_REF]))
    total = band_power(f, psd, 20, 20000)
    xs = np.array([math.log10(1000.0 * 10 ** ((n - 16) / 10.0)) for n, b in enumerate(THIRDS) if 100 <= b <= 10000])
    ys = np.array([dens[b] for b in THIRDS if 100 <= b <= 10000])
    ref12 = float(np.mean([thirds[b] for b in (1000, 1250, 1600, 2000)]))
    return dict(thirds_abs={b: thirds[b] for b in THIRDS}, thirds_rel={b: thirds[b] - mid for b in THIRDS}, mid_ref=mid,
                coarse={"%d-%d" % (lo, hi): db(band_power(f, psd, lo, hi) / total) for lo, hi in COARSE},
                slope=float(np.polyfit(xs, ys, 1)[0]),
                bandwidth=max([b for b in THIRDS if thirds[b] >= ref12 - 20.0], default=THIRDS[0]))


def crest_and_corr(x):
    n = len(x); f = np.fft.rfftfreq(n, 1.0 / SR)
    X = np.fft.rfft(x, axis=0)
    crest, corr = {}, {}
    for name, (lo, hi) in SPLIT.items():
        y = np.fft.irfft(X * (((f >= lo) & (f < hi))[:, None]), n=n, axis=0)
        crest[name] = 20 * math.log10(max(float(np.abs(y).max()), 1e-12) / max(float(np.sqrt((y ** 2).mean())), 1e-12))
        corr[name] = float(np.corrcoef(y[:, 0], y[:, 1])[0, 1]) if y.std() > 0 else 0.0
    return crest, corr


def pumping_std(M):
    M = np.asarray(M); d = np.diff(M)
    ok = (M[1:] > GATE) & (M[:-1] > GATE)
    return float(d[ok].std()) if ok.sum() > 10 else float("nan")


def pre_echo(x, n_onsets=20, min_gap=0.5):
    m = x.mean(axis=1)
    flux, hop = loop_cut.onsets(x)
    h, nwin = int(hop * SR), 2048
    picked = []
    for i in np.argsort(flux)[::-1]:
        t = i * hop
        if all(abs(t - q) >= min_gap for q in picked):
            picked.append(t)
        if len(picked) == n_onsets:
            break
    blk = int(0.001 * SR); pre = int(PRE_MS * SR)
    F = np.fft.rfftfreq(len(m), 1.0 / SR)
    hf = np.fft.irfft(np.fft.rfft(m) * (F >= 2500.0), n=len(m))
    bb, hi = [], []
    for t in picked:
        a = int(t * SR); seg = m[a: a + nwin + h]; k = len(seg) // blk
        if k < 4:
            continue
        e = (seg[: k * blk].reshape(k, blk) ** 2).mean(axis=1)
        on = a + (int(np.argmax(np.diff(e))) + 1) * blk
        if on - pre < 0 or on + pre > len(m):
            continue
        bb.append(db((m[on - pre: on] ** 2).mean()) - db((m[on: on + pre] ** 2).mean()))
        hi.append(db((hf[on - pre: on] ** 2).mean()) - db((hf[on: on + pre] ** 2).mean()))
    return (float(np.mean(bb)) if bb else float("nan")), (float(np.mean(hi)) if hi else float("nan")), len(bb)


def count_runs(mask, n):
    total = 0
    for c in range(mask.shape[1]):
        d = np.diff(np.concatenate([[0], mask[:, c].astype(np.int8), [0]]))
        starts, ends = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
        total += int(((ends - starts) >= n).sum())
    return total


def edge_rms_db(x, seconds):
    n = int(seconds * SR)
    return (db((x[:n] ** 2).mean()), db((x[-n:] ** 2).mean()))


def lag_of(a, b, maxlag=4800):
    ma, mb = a.mean(axis=1), b.mean(axis=1)
    n = 1 << int(math.ceil(math.log2(len(ma) + maxlag)))
    c = np.fft.irfft(np.fft.rfft(ma, n) * np.conj(np.fft.rfft(mb, n)), n)
    c = np.concatenate([c[-maxlag:], c[:maxlag + 1]])
    return int(np.argmax(c)) - maxlag


def gain_swing(cand, ref, win=0.1, hop=0.05, gate=-45.0, span=1.0):
    """The judge's gain-tracking probe: 100 ms RMS of candidate minus
    reference (dB) after aligning them by cross-correlation, the median
    removed over frames where the reference is above `gate`; the largest
    swing inside any 1 s window, and how many windows swing over SWING_DB."""
    L = lag_of(cand, ref)
    a, b = (cand[L:], ref[:len(ref) - L]) if L >= 0 else (cand[:len(cand) + L], ref[-L:])
    n = min(len(a), len(b)); a, b = a[:n], b[:n]
    t, ra = window_rms(a, win, hop); _, rb = window_rms(b, win, hop)
    ok = rb > gate
    if ok.sum() < 40:
        return dict(lag=L, swing=0.0, at=0.0, over=0, windows=0)
    r = ra - rb; r = r - np.median(r[ok])
    w = int(round(span / hop))
    sw = [(float(r[i:i + w].max() - r[i:i + w].min()), float(t[i])) for i in range(0, len(r) - w) if ok[i:i + w].all()]
    if not sw:
        return dict(lag=L, swing=0.0, at=0.0, over=0, windows=0)
    mx = max(sw)
    return dict(lag=L, swing=mx[0], at=mx[1], over=sum(1 for s, _ in sw if s > SWING_DB), windows=len(sw))


def measure(path, lufs, x=None):
    """Everything the rules read, from one decode and three ffmpeg passes."""
    if x is None:
        x = loop_cut.decode(path)
    e = ebur128(path); em = ebur128(path, mono=True)
    t5, r5 = window_rms(x, 0.5)
    intro = r5[t5 + 0.5 <= INTRO_S]
    crest, corr = crest_and_corr(x)
    mid = x.mean(axis=1)
    w = loop_cut.check_whole(x, lufs, path, assert_=False)
    whole_rules = dict(head_tail=max(w["head_dbfs"], w["tail_dbfs"]) <= -25.0, seam=w["seam"] <= w["mean_step"],
                       level=abs(w["lufs"] - lufs) <= 0.5, peak=w["peak_dbtp"] <= -1.0,
                       silence_length=w["quiet_seconds"] <= 2.5, silence_at_seam=w["quiet_away"] == 0.0)
    pe, pe_hf, n_on = pre_echo(x)
    head2, tail2 = edge_rms_db(x, 0.002)
    out = dict(file=os.path.abspath(path), seconds=len(x) / SR, lufs=e["I"], tp=e["tp"], lra=e["lra"],
               tp4x=true_peak_4x(x), plr=e["tp"] - e["I"], sample_peak=float(np.abs(x).max()),
               intro_quietest_500ms=float(intro.min()) if len(intro) else float("nan"),
               crest=crest, corr=corr, corr_all=float(np.corrcoef(x[:, 0], x[:, 1])[0, 1]),
               pumping=pumping_std(e["M"]), mono_loss=em["I"] - e["I"],
               pre_echo=pe, pre_echo_hf=pe_hf, onsets=n_on,
               full_scale_runs=count_runs(np.abs(x) >= FULL_SCALE, 3),
               flat_top_runs=count_runs(np.concatenate([np.zeros((1, 2), bool), np.diff(x, axis=0) == 0.0]) & (np.abs(x) > FLAT_TOP), 7),
               dc=[float(v) for v in x.mean(axis=0)],
               whole=w, whole_rules=whole_rules, whole_pass=all(whole_rules.values()),
               end_samples=(float(abs(x[0]).max()), float(abs(x[-1]).max())), edge2ms=(head2, tail2))
    out.update(spectrum(mid))
    return out


# ------------------------------------------------------------------ the rules

def scored(target):
    return [b for b in THIRDS if 40 <= b <= 16000 and target["curve"].get(b) is not None]


# A loop's rules are a whole piece's less the four that read a whole piece's
# ends (its seam is loop_cut.check's: bar-aligned, seamless, no silence).
WHOLE_ONLY = ("check_whole", "ramps", "intro", "silence")


def rules(r, target, lufs, src=None, swing=None, loop=False):
    """Every rule as (name, ok-or-None, message). None = needs a source and
    none was given. `loop`: a loop, the whole piece's end rules left out."""
    out = []
    def rule(name, ok, msg):
        if not (loop and name in WHOLE_ONLY):
            out.append((name, ok, msg))
    rule("level", abs(r["lufs"] - lufs) <= LEVEL_LU, "%.1f LUFS, want %.1f +-%.1f" % (r["lufs"], lufs, LEVEL_LU))
    rule("peak ebur128", r["tp"] <= TP_CEILING_DBTP, "%.2f dBTP, want <= %.0f" % (r["tp"], TP_CEILING_DBTP))
    rule("peak 4x fft", r["tp4x"] <= TP_CEILING_DBTP, "%.2f dBTP oversampled here, want <= %.0f" % (r["tp4x"], TP_CEILING_DBTP))
    rule("full scale", r["full_scale_runs"] == 0, "%d runs of 3+ samples at or over %.3f" % (r["full_scale_runs"], FULL_SCALE))
    rule("flat tops", r["flat_top_runs"] == 0, "%d runs of 8+ identical samples over %.2f" % (r["flat_top_runs"], FLAT_TOP))
    w = r["whole"]
    rule("check_whole", r["whole_pass"], "head %.1f tail %.1f dBFS, seam %.5f vs step %.5f, quiet %.1f s (%.1f away)%s" % (
        w["head_dbfs"], w["tail_dbfs"], w["seam"], w["mean_step"], w["quiet_seconds"], w["quiet_away"],
        "" if r["whole_pass"] else "; FAILS " + ",".join(k for k, v in r["whole_rules"].items() if not v)))
    h2, t2 = r["edge2ms"]; s0, s1 = r["end_samples"]
    rule("ramps", s0 <= 1e-4 and s1 <= 1e-4 and h2 <= RAMP_EDGE_DBFS and t2 <= RAMP_EDGE_DBFS,
         "first/last sample %.5f/%.5f, first/last 2 ms %.0f/%.0f dBFS, want 0 and <= %.0f" % (s0, s1, h2, t2, RAMP_EDGE_DBFS))
    devs = {b: r["thirds_rel"][b] - target["curve"][b] for b in scored(target)}
    bad = [b for b, d in devs.items() if abs(d) > target["tolerance"][b]]
    worst = max(devs, key=lambda b: abs(devs[b]))
    rms = float(np.sqrt(np.mean([d * d for d in devs.values()])))
    rule("curve", not bad, "RMS %.2f dB over %d bands, worst %g Hz %+.2f of %.1f%s" % (
        rms, len(devs), worst, devs[worst], target["tolerance"][worst],
        "" if not bad else "; out: " + " ".join("%g:%+.1f" % (b, devs[b]) for b in bad)))
    if src is None:
        for name in ("move", "pumping", "swing", "pre-echo", "mono", "intro", "plr", "silence"):
            rule(name, None, "needs the source")
        return out, dict(curve_rms=rms, curve_worst=(worst, devs[worst]), devs=devs)
    mv = {b: r["thirds_rel"][b] - src["thirds_rel"][b] for b in scored(target)}
    mva = {b: r["thirds_abs"][b] - src["thirds_abs"][b] for b in scored(target)}
    bm = max(mv, key=lambda b: abs(mv[b])); bma = max(mva, key=lambda b: abs(mva[b]))
    rule("move", abs(mv[bm]) <= MOVE_DB, "largest %g Hz %+.1f dB on the target's display (absolute: %g Hz %+.1f), want <= %.0f" % (
        bm, mv[bm], bma, mva[bma], MOVE_DB))
    px = r["pumping"] / src["pumping"] if src["pumping"] else float("nan")
    rule("pumping", px <= PUMP_X, "momentary std %.3f LU, x%.2f the source's, want <= x%.1f" % (r["pumping"], px, PUMP_X))
    if swing is not None:
        rule("swing", swing["swing"] <= SWING_DB, "100 ms RMS vs stage 1 (lag %+d): max %.2f dB inside 1 s at %.2f s, %d of %d windows over %.0f, want none" % (
            swing["lag"], swing["swing"], swing["at"], swing["over"], swing["windows"], SWING_DB))
    else:
        rule("swing", None, "needs the chain's stage-1 file (--stage1)")
    rule("pre-echo", r["pre_echo"] <= src["pre_echo"] + PRE_ECHO_DB, "%.2f dB (source %.2f; above 2.5 kHz %.2f vs %.2f) over %d onsets, want <= source + %.0f" % (
        r["pre_echo"], src["pre_echo"], r["pre_echo_hf"], src["pre_echo_hf"], r["onsets"], PRE_ECHO_DB))
    rule("mono", r["mono_loss"] >= src["mono_loss"] - MONO_LU, "mono-sum loss %+.2f LU (source %+.2f), want >= source - %.0f" % (
        r["mono_loss"], src["mono_loss"], MONO_LU))
    lift = r["intro_quietest_500ms"] - src["intro_quietest_500ms"]
    rule("intro", lift <= INTRO_DB, "quietest 500 ms of the first %.0f s %.1f dBFS (source %.1f), lifted %+.1f, want <= %.0f" % (
        INTRO_S, r["intro_quietest_500ms"], src["intro_quietest_500ms"], lift, INTRO_DB))
    rule("plr", abs(r["plr"] - src["plr"]) <= PLR_DB, "PLR %.1f dB (source %.1f), want within %.0f" % (r["plr"], src["plr"], PLR_DB))
    dq = w["quiet_seconds"] - src["whole"]["quiet_seconds"]
    rule("silence", abs(dq) <= SILENCE_S, "%.1f s under -40 dBFS (source %.1f), want within %.0f s" % (
        w["quiet_seconds"], src["whole"]["quiet_seconds"], SILENCE_S))
    return out, dict(curve_rms=rms, curve_worst=(worst, devs[worst]), devs=devs, move=mv, move_abs=mva)


def failed(rs):
    return [name for name, ok, _ in rs if ok is False]


# ------------------------------------------------------------------ printing

def print_rules(rs):
    for name, ok, msg in rs:
        print("  %-13s %s  %s" % (name, "n/a  " if ok is None else ("ok   " if ok else "FAIL "), msg))


def print_measure(r, target, label, devs=None):
    print("%s  %s  (%.2f s)" % (label, r["file"], r["seconds"]))
    c = r["crest"]; k = r["corr"]
    print("  %.1f LUFS  TP %.2f dBTP (4x fft %.2f)  LRA %.1f LU  PLR %.1f dB  crest <150 %.1f  150-2.5k %.1f  >2.5k %.1f dB  pumping std %.3f LU" % (
        r["lufs"], r["tp"], r["tp4x"], r["lra"], r["plr"], c["low"], c["mid"], c["high"], r["pumping"]))
    print("  slope 100 Hz-10 kHz %.1f dB/decade  -20 dB bandwidth %g Hz  corr %.3f (<150 %.3f  150-2.5k %.3f  >2.5k %.3f)  mono-sum loss %+.2f LU  pre-echo %.2f dB (hf %.2f)  intro quietest 500 ms %.1f dBFS" % (
        r["slope"], r["bandwidth"], r["corr_all"], k["low"], k["mid"], k["high"], r["mono_loss"], r["pre_echo"], r["pre_echo_hf"], r["intro_quietest_500ms"]))
    print("  coarse (dB of the 20-20k total): " + "  ".join("%s:%+.1f" % (b, v) for b, v in r["coarse"].items()))
    if devs is None:
        devs = {b: r["thirds_rel"][b] - target["curve"][b] for b in scored(target)}
    print("  1/3-oct vs target (dB, ! = out): " + "  ".join("%g:%+.1f%s" % (b, d, "!" if abs(d) > target["tolerance"][b] else "") for b, d in devs.items()))


# ------------------------------------------------------------------ master / check

def master(src_path, out_path, lufs, target, keep=None, fit=False):
    src_x = loop_cut.decode(src_path)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        work = keep or d
        os.makedirs(work, exist_ok=True)
        tmp_out = os.path.join(work, "mastered.wav")
        x, s1, notes = run_chain(src_path, tmp_out, lufs, work, fit=target if fit else None)
        for n in notes:
            print(n)
        src = measure(src_path, lufs, src_x)
        r = measure(tmp_out, lufs, x)
        sw = gain_swing(x, s1)
        rs, info = rules(r, target, lufs, src, sw)
        print_measure(src, target, "BEFORE")
        print_measure(r, target, "AFTER ", info["devs"])
        print("  moved (dB, target's display): " + "  ".join("%g:%+.1f" % (b, v) for b, v in info["move"].items()))
        print("rules:")
        print_rules(rs)
        bad = failed(rs)
        if bad:
            rej = os.path.splitext(out_path)[0] + ".rejected.wav"
            shutil.move(tmp_out, rej)
            print("REFUSED: %s failed; the file is at %s for measuring, not for shipping" % (", ".join(bad), rej))
            return False
        shutil.move(tmp_out, out_path)
    print("master ok: %s -> %s  %.1f LUFS  %.2f dBTP  curve RMS %.2f dB (worst %g Hz %+.2f)  slope %.1f -> %.1f dB/decade  bandwidth %g -> %g Hz  PLR %.1f -> %.1f  swing %.2f dB  mono-loss %+.2f -> %+.2f LU" % (
        os.path.basename(src_path), out_path, r["lufs"], r["tp"], info["curve_rms"], info["curve_worst"][0], info["curve_worst"][1],
        src["slope"], r["slope"], src["bandwidth"], r["bandwidth"], src["plr"], r["plr"], sw["swing"], src["mono_loss"], r["mono_loss"]))
    print("Nothing here has been listened to: what is improved is what the rules above measure.")
    return True


def master_loop(render, out_path, bpm, bars, lufs, target, keep=None, skip=0.0):
    """A loop (2026-10-03): the whole render through the chain with stage 1
    fitted (--fit), then cut by loop_cut.make, so the crossfade joins two
    mastered stretches of one file and no filter's state lands on the seam.
    The loop is then held to loop_cut.check and to every rule here but the
    whole piece's ends, against the render it was cut from."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        work = keep or d
        os.makedirs(work, exist_ok=True)
        src = os.path.join(work, "render.wav")
        ffmpeg(render, ["-ar", str(SR), "-ac", "2"], src)
        mastered = os.path.join(work, "mastered_render.wav")
        x, s1, notes = run_chain(src, mastered, lufs, work, fit=target, ramp=False)
        for n in notes:
            print(n)
        tmp_out = os.path.join(work, "loop.wav")
        info = loop_cut.make(mastered, tmp_out, bpm, bars, loop_cut.XFADE, lufs, skip)
        lc = loop_cut.check(loop_cut.decode(tmp_out), loop_cut.decode(mastered), info["start"], info["seconds"],
                            4 * 60.0 / bpm, lufs, tmp_out, assert_=False)
        lc_rules = [("bar-aligned", lc["bar_corr"] >= 0.5, "onsets at the seam r %.2f, want 0.5" % lc["bar_corr"]),
                    ("seamless", lc["seam"] <= lc["mean_step"], "step across the seam %.5f, mean step %.5f" % (lc["seam"], lc["mean_step"])),
                    ("no silence", lc["floor_dbfs"] >= -40.0, "quietest half second %.1f dBFS, want >= -40" % lc["floor_dbfs"])]
        # the source the rules compare against: the same window of the raw render
        raw_loop = os.path.join(work, "raw_loop.wav")
        rx = loop_cut.decode(src)
        loop_cut.encode(raw_loop, loop_cut.cut(rx, info["start"], info["seconds"]) *
                        db2lin(lufs - loop_cut.loudness(src)[0]))
        y = loop_cut.decode(tmp_out)
        r = measure(tmp_out, lufs, y)
        srcm = measure(raw_loop, lufs)
        a = int(info["start"] * SR)
        sw = gain_swing(y, s1[a: a + len(y)])
        rs, inf = rules(r, target, lufs, srcm, sw, loop=True)
        rs = lc_rules + rs
        print_measure(srcm, target, "BEFORE")
        print_measure(r, target, "AFTER ", inf["devs"])
        print("loop: %d bars at %g BPM, %.1f s from %.2f s of a %.1f s render" % (
            bars, bpm, info["seconds"], info["start"], info["render_seconds"]))
        print("rules:")
        print_rules(rs)
        bad = failed(rs)
        if bad:
            rej = os.path.splitext(out_path)[0] + ".rejected.wav"
            shutil.move(tmp_out, rej)
            print("REFUSED: %s failed; the file is at %s for measuring, not for shipping" % (", ".join(bad), rej))
            return False
        shutil.move(tmp_out, out_path)
    print("loop master ok: %s -> %s  %.1f LUFS  %.2f dBTP  curve RMS %.2f -> %.2f dB  slope %.1f -> %.1f  bandwidth %g -> %g Hz  PLR %.1f -> %.1f  swing %.2f dB" % (
        os.path.basename(render), out_path, r["lufs"], r["tp"],
        float(np.sqrt(np.mean([(srcm["thirds_rel"][b] - target["curve"][b]) ** 2 for b in scored(target)]))),
        inf["curve_rms"], srcm["slope"], r["slope"], srcm["bandwidth"], r["bandwidth"], srcm["plr"], r["plr"], sw["swing"]))
    print("Nothing here has been listened to: what is improved is what the rules above measure.")
    return True


def master_loop_file(src_path, out_path, lufs, target, keep=None):
    """A loop already cut (2026-10-03: the loops of 2026-09-10/28, whose
    renders the chain cannot be run on again). The loop is tiled three
    times, the chain (stage 1 fitted) runs over all three, and the middle
    copy is kept: every filter has run a whole loop's length into it, so
    its state at the end of the copy is its state at the start, and the
    seam stays as continuous as the file it came from. Held to the seam,
    the level, the peaks and every rule here but the whole piece's ends,
    against the loop as it was."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        work = keep or d
        os.makedirs(work, exist_ok=True)
        x0 = loop_cut.decode(src_path)
        n = len(x0)
        tiled = os.path.join(work, "tiled.wav")
        loop_cut.encode(tiled, np.concatenate([x0, x0, x0]))
        done = os.path.join(work, "tiled_mastered.wav")
        # a loop limited hard keeps about its own peak-to-loudness: the
        # ceiling is the chain's, or PLR_FOLLOW dB over the source's PLR if
        # that is lower (the PLR rule holds it within 2 dB)
        I0, tp0 = loop_cut.loudness(src_path)
        limit = min(LIMIT_DBFS, lufs + (tp0 - I0) + PLR_FOLLOW)
        _x, s1, notes = run_chain(tiled, done, lufs, work, fit=target, ramp=False, limit_dbfs=limit)
        for nt in notes:
            print(nt)
        z = loop_cut.decode(done)
        # the chain delays (the crossover, the limiter's lookahead): the copy
        # kept starts where the middle copy's first sample came out, so the
        # seam falls at the same point of the music as it did
        lag = max(0, lag_of(z[n: 2 * n], x0))
        notes.append("latency %d samples; limiter ceiling %.2f dBFS" % (lag, limit))
        print(notes[-1])
        y = z[n + lag: 2 * n + lag]
        tmp_out = os.path.join(work, "loop.wav")
        loop_cut.encode(tmp_out, y)
        I, tp = loop_cut.loudness(tmp_out)
        y = y * db2lin(lufs - I)
        loop_cut.encode(tmp_out, y)
        I, tp = loop_cut.loudness(tmp_out)
        if tp > TP_CEILING_DBTP:
            y = y * db2lin(TP_CEILING_DBTP - tp - 0.05)
            loop_cut.encode(tmp_out, y)
        y = loop_cut.decode(tmp_out)
        mono = y.mean(axis=1)
        step = float(np.abs(np.diff(mono)).mean()); seam = float(abs(mono[0] - mono[-1]))
        e, _w = loop_cut.rms_env(y, 0.5)
        floor = float(20 * np.log10(max(e.min(), 1e-9)))
        lc_rules = [("seamless", seam <= step, "step across the seam %.5f, mean step %.5f" % (seam, step)),
                    ("no silence", floor >= -40.0, "quietest half second %.1f dBFS, want >= -40" % floor),
                    ("length", len(y) == n, "%d samples, the loop's %d" % (len(y), n))]
        r = measure(tmp_out, lufs, y)
        srcm = measure(src_path, lufs, x0)
        sw = gain_swing(y, s1[n + lag: 2 * n + lag])
        rs, inf = rules(r, target, lufs, srcm, sw, loop=True)
        rs = lc_rules + rs
        print_measure(srcm, target, "BEFORE")
        print_measure(r, target, "AFTER ", inf["devs"])
        print("rules:")
        print_rules(rs)
        bad = failed(rs)
        if bad:
            rej = os.path.splitext(out_path)[0] + ".rejected.wav"
            shutil.move(tmp_out, rej)
            print("REFUSED: %s failed; the file is at %s for measuring, not for shipping" % (", ".join(bad), rej))
            return False
        shutil.move(tmp_out, out_path)
    print("loop file master ok: %s -> %s  %.1f LUFS  %.2f dBTP  curve RMS %.2f -> %.2f dB  slope %.1f -> %.1f  bandwidth %g -> %g Hz  PLR %.1f -> %.1f  swing %.2f dB" % (
        os.path.basename(src_path), out_path, r["lufs"], r["tp"],
        float(np.sqrt(np.mean([(srcm["thirds_rel"][b] - target["curve"][b]) ** 2 for b in scored(target)]))),
        inf["curve_rms"], srcm["slope"], r["slope"], srcm["bandwidth"], r["bandwidth"], srcm["plr"], r["plr"], sw["swing"]))
    print("Nothing here has been listened to: what is improved is what the rules above measure.")
    return True


def check(path, lufs, target, ref=None, stage1=None):
    x = loop_cut.decode(path)
    r = measure(path, lufs, x)
    src = measure(ref, lufs) if ref else None
    sw = gain_swing(x, loop_cut.decode(stage1)) if stage1 else None
    rs, info = rules(r, target, lufs, src, sw)
    if src:
        print_measure(src, target, "REF   ")
    print_measure(r, target, "FILE  ", info["devs"])
    print("rules:")
    print_rules(rs)
    if ref and not stage1:
        g = gain_swing(x, loop_cut.decode(ref))
        print("  (swing vs the source, information: lag %+d, max %.2f dB inside 1 s at %.2f s, %d of %d windows over %.0f -- the EQ's re-weighting of sections is in this number)" % (
            g["lag"], g["swing"], g["at"], g["over"], g["windows"], SWING_DB))
    bad = failed(rs)
    print("%s: %s" % ("FAIL" if bad else "PASS", ", ".join(bad) if bad else "every rule that could be measured holds"))
    return not bad


# ------------------------------------------------------------------ bite

def shaped_noise(n, rng, target):
    """White noise shaped so its 1/3-octave band power follows the target
    (pink = flat on the target's display, so the shaping is 1/sqrt(f) times
    the curve interpolated on log f), rolling off under 40 Hz and over 16 kHz."""
    f = np.fft.rfftfreq(n, 1.0 / SR)
    bands = [b for b in THIRDS if target["curve"].get(b) is not None]
    fc = np.array([1000.0 * 10 ** ((THIRDS.index(b) - 16) / 10.0) for b in bands])
    g = np.array([target["curve"][b] for b in bands])
    lf = np.log10(np.maximum(f, 1.0))
    gain = np.interp(lf, np.log10(fc), g, left=g[0] - 12.0, right=g[-1] - 30.0)
    amp = db2lin(gain) / np.sqrt(np.maximum(f, 20.0))
    amp[f < 20.0] = 0.0
    X = np.fft.rfft(rng.standard_normal(n)) * amp
    y = np.fft.irfft(X, n=n)
    return y / np.sqrt((y ** 2).mean())


def hit(n, decay, attack=0.002, freq=None, noise=None):
    """An exponential burst with a short attack: a sine, a slice of noise, or both."""
    t = np.arange(n) / SR
    env = np.exp(-t / decay) * np.minimum(t / attack, 1.0)
    body = np.zeros(n)
    if freq is not None:
        body += np.sin(2 * np.pi * freq * t)
    if noise is not None:
        body += noise[:n]
    return env * body


def synth(target, bpm=120.0, intro_bars=8, body_bars=12, fade=3.0, silence=1.5):
    """The bite's mix: a bed of noise on the target curve (quiet through the
    intro, up 10 dB for the body), kicks on 1 and 3 (a 60 Hz sine under a
    burst of the same shaped noise, so the hits do not move the curve),
    snares on 2 and 4, a tick on every eighth, a fade 12 dB down, the
    silence, 20 ms ramps."""
    rng = np.random.default_rng(7)
    bar = 4 * 60.0 / bpm; beat = 60.0 / bpm
    intro, body = intro_bars * bar, body_bars * bar
    total = intro + body + fade + silence
    n = int(total * SR); t = np.arange(n) / SR
    c, s1, s2, hn = (shaped_noise(n, rng, target) for _ in range(4))
    F = np.fft.rfftfreq(n, 1.0 / SR)                      # the snares and ticks: the same noise above 300 Hz, so their
    hp = np.fft.irfft(np.fft.rfft(hn) * (F >= 300.0), n=n)  # attack is where the pre-echo probe's 1 ms blocks find it
    L = c + 0.35 * s1; R = c + 0.35 * s2
    level = np.where(t < intro, db2lin(-30.0), db2lin(-20.0))
    e = int(0.5 * SR); i0 = int(intro * SR)             # the body enters over half a second
    level[i0 - e: i0] = db2lin(-30.0) + (db2lin(-20.0) - db2lin(-30.0)) * (0.5 - 0.5 * np.cos(np.linspace(0, math.pi, e)))
    x = np.stack([L, R], axis=1) * level[:, None]
    for k in range(int(total / beat)):
        at = k * beat
        if at < intro or at >= intro + body + fade:
            continue
        i = int(at * SR)
        if k % 2 == 0:
            h = hit(int(0.25 * SR), 0.05, freq=60.0, noise=0.6 * hn[i:]); a = 0.35
        else:
            h = hit(int(0.12 * SR), 0.04, noise=1.5 * hp[i:]); a = 0.25
        x[i: i + len(h)] += a * h[:, None]
        h = hit(int(0.02 * SR), 0.005, attack=0.0005, noise=3.0 * hp[i:])
        x[i: i + len(h)] += 0.06 * h[:, None]
        j = i + int(beat / 2 * SR)
        h = hit(int(0.02 * SR), 0.005, attack=0.0005, noise=3.0 * hp[j:])
        x[j: j + len(h)] += 0.04 * h[:, None]
    fin = int(0.3 * SR)                                   # rises out of nothing over 300 ms
    x[:fin] *= (0.5 - 0.5 * np.cos(np.linspace(0, math.pi, fin)))[:, None]
    f0 = int((intro + body) * SR); f1 = int((intro + body + fade) * SR)
    x[f0:f1] *= np.linspace(1.0, db2lin(-12.0), f1 - f0)[:, None]    # 12 dB down, then the silence: the blocks under -40 dBFS stay at the seam and under 2.5 s
    x[f1:] = 0.0
    return ramps(x)


def bite():
    target = TARGETS["theme"]; lufs = -24.0              # -24, as loop_cut's bite: a noise bed peaks 13 dB over its RMS with the hits on top, and -20 LUFS put the peak at 0 dBTP
    with tempfile.TemporaryDirectory() as d:
        def put(label, x):
            p = os.path.join(d, label.replace(" ", "_") + ".wav"); loop_cut.encode(p, x)
            return p
        def level(x, want=lufs):
            p = put("_level", x); I, _ = loop_cut.loudness(p)
            return x * db2lin(want - I)
        raw = synth(target)
        clean = level(raw)
        src_path = put("clean", clean); clean = loop_cut.decode(src_path)
        src = measure(src_path, lufs, clean)
        cases = []
        def case(label, x, expect):
            p = put(label, x); y = loop_cut.decode(p)
            r = measure(p, lufs, y)
            rs, _ = rules(r, target, lufs, src, gain_swing(y, clean))
            bad = failed(rs)
            if expect is None:
                cases.append((label, not bad, "passes" if not bad else "FAILS " + ", ".join(bad)))
            else:
                msg = next((m for n_, ok, m in rs if n_ == expect), "")
                cases.append((label, expect in bad, ("%s: %s" % (expect, msg)) if expect in bad else "did not fail %s (%s)" % (expect, ", ".join(bad) or "passes")))
        case("clean (must pass)", clean, None)
        n = len(clean); f = np.fft.rfftfreq(n, 1.0 / SR)
        # a band boosted: +10 dB, an octave wide, zero-phase at 1 kHz
        bell = db2lin(10.0 * np.exp(-0.5 * ((np.log2(np.maximum(f, 1.0) / 1000.0)) / 0.5) ** 2))
        case("boosted band", level(np.fft.irfft(np.fft.rfft(clean, axis=0) * bell[:, None], n=n, axis=0)), "curve")
        # a hard clip, turned back down afterwards: flat tops under the level (x3: the tops land near 0.4 after the re-level, over the rule's 0.25)
        case("hard clip", level(np.clip(clean * 3.0, -1.0, 1.0)), "flat tops")
        # a pumping compressor: 1 ms attack, 300 ms release, ratio 4 over -18 dBFS on a 1 ms block envelope
        blk = int(0.001 * SR); k = n // blk
        env = np.sqrt((clean[: k * blk].mean(axis=1).reshape(k, blk) ** 2).mean(axis=1))
        det = np.zeros(k); rel = math.exp(-1.0 / 300.0)
        for i in range(k):
            det[i] = env[i] if env[i] > det[i - 1] * rel else det[i - 1] * rel
        gr = np.maximum(0.0, 20 * np.log10(np.maximum(det, 1e-9)) + 18.0) * (1 - 1 / 4.0)
        g = np.repeat(db2lin(-gr), blk); g = np.concatenate([g, np.full(n - len(g), g[-1])])
        case("pumping", level(clean * g[:, None]), "swing")
        # pre-echo: a symmetric (linear-phase) FIR whose mirror tap puts 35 % of every hit 8 ms early (and 8 ms late)
        s = int(0.008 * SR); pe = clean.copy(); pe[:-s] += 0.35 * clean[s:]; pe[s:] += 0.35 * clean[:-s]
        case("pre-echo", level(ramps(pe)), "pre-echo")
        # a noise floor under the intro: shaped noise at -27 dBFS over the first 16 s (the bed is near -34), 100 ms edges
        rng = np.random.default_rng(11); m = int(16.0 * SR); ed = int(0.1 * SR)
        nz = np.stack([shaped_noise(m, rng, target), shaped_noise(m, rng, target)], axis=1) * db2lin(-27.0)
        nz[:ed] *= (0.5 - 0.5 * np.cos(np.linspace(0, math.pi, ed)))[:, None]; nz[-ed:] *= (0.5 + 0.5 * np.cos(np.linspace(0, math.pi, ed)))[:, None]
        fl = clean.copy(); fl[:m] += nz
        case("noise floor", fl, "intro")
        # a broken end ramp: the last 20 ms are the body, unramped
        r20 = int(RAMP_S * SR); br = clean.copy(); br[-r20:] = clean[int(20.0 * SR): int(20.0 * SR) + r20]
        case("end ramp", br, "ramps")
        # the end silence filled: -30 dBFS noise over the last 1.5 s, ramped at the very end
        q = int(1.5 * SR); sf = clean.copy()
        sf[-q:] = np.stack([shaped_noise(q, rng, target), shaped_noise(q, rng, target)], axis=1) * db2lin(-30.0)
        case("end silence", ramps(sf), "silence")
        case("level", clean * db2lin(-3.0), "level")
        # a widener that cancels in mono: side x4
        M = clean.mean(axis=1); S = (clean[:, 0] - clean[:, 1]) / 2 * 4.0
        case("mono widener", level(np.stack([M + S, M - S], axis=1)), "mono")
    print("\n%-20s %s" % ("check", "when the master is broken -- and when it is not"))
    for label, ok, msg in cases:
        print("  %-18s %s  %s" % (label, "OK     " if ok else "WRONG  ", msg[:110]))
    n = sum(1 for _, ok, _ in cases if ok)
    print("  %d of %d as they should be" % (n, len(cases)))
    return n == len(cases)


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?"); ap.add_argument("out", nargs="?")
    ap.add_argument("--lufs", type=float, default=None, help="target loudness (default: the target's)")
    ap.add_argument("--target", default="theme", choices=sorted(TARGETS))
    ap.add_argument("--keep", help="keep the stage files in this folder")
    ap.add_argument("--check", metavar="FILE", help="measure only; exit 1 if a rule fails")
    ap.add_argument("--ref", help="with --check: the source, for the rules that need one")
    ap.add_argument("--stage1", help="with --check: the chain's stage-1 file (see --keep), for the swing rule")
    ap.add_argument("--bite", action="store_true")
    ap.add_argument("--fit", action="store_true", help="fit stage 1 to this file (default: the theme's own EQ)")
    ap.add_argument("--loop", nargs=2, type=float, metavar=("BPM", "BARS"),
                    help="SRC is a raw render: master it whole (fitted), cut a BARS-bar loop at BPM, check the loop")
    ap.add_argument("--skip", type=float, default=0.0, help="with --loop: open the window no earlier than this")
    ap.add_argument("--loop-file", action="store_true",
                    help="SRC is a loop already cut: master it seamlessly (tiled, fitted), keep its length")
    a = ap.parse_args()
    target = TARGETS[a.target]
    lufs = a.lufs if a.lufs is not None else target["lufs"]
    if a.bite:
        sys.exit(0 if bite() else 1)
    if a.check:
        sys.exit(0 if check(a.check, lufs, target, a.ref, a.stage1) else 1)
    if not (a.src and a.out):
        ap.error("IN.wav OUT.wav, or --check FILE, or --bite")
    if a.loop_file:
        sys.exit(0 if master_loop_file(a.src, a.out, lufs, target, a.keep) else 1)
    if a.loop:
        sys.exit(0 if master_loop(a.src, a.out, a.loop[0], int(a.loop[1]), lufs, target, a.keep, a.skip) else 1)
    sys.exit(0 if master(a.src, a.out, lufs, target, a.keep, a.fit) else 1)


if __name__ == "__main__":
    main()
