"""AHMED — Kuwait Fighter :: master the sound effects
==============================================================================
The recordings were fine and their preparation was not.

Every clip is 48 kHz, 16-bit and unclipped, which is the right format. But
they came out of generation at whatever level they came out at, and nothing
ever levelled them: peaks ran from 0.002 to 0.85, a factor of four hundred.
Six cues were effectively silent — UI_Tap at -54 dBFS, the sound a menu makes
when you press it; Weapon_Hit, Dash_Leap, Land, Exit_Travel, UI_Denied. A KO,
the loudest moment in a fight, peaked 14 dB under a footstep.

The `Lead` column is *not* a defect, and this tool was written believing it
was. It is the one number in the sound table the *game* depends on rather
than the mix: `AFighterBase::StartAttack` schedules a swing at
`startup - lead` so the swish peaks on the first active frame. A first pass
here measured lead as the first sample reaching a tenth of the peak and
concluded that twenty-six of forty rows were wrong by up to 489 ms. They were
not. A tenth of the peak finds where a whoosh's *wind-up* begins, and the
column holds where the sound *lands* — measured, as `Content/Audio/README.md`
says, off a 5 ms RMS envelope. Measured that way the committed values agree to
within two or three milliseconds nearly everywhere. Writing the onsets back
would have set `Whoosh_Heavy` to 0.001 s and landed every heavy swing's swish
99 ms after the punch.

So this measures Lead the way the table does, reports any row that disagrees,
and **does not write the table at all**. Retiming the swings is not what
"master the audio" means, and a tool that rewrites a data table as a side
effect is one truncation away from taking rows out of it — which this one did,
on its first run, to the four music rows.

So it does three things, all of them to the audio and none of them to the
data:

  * takes the DC offset out of each channel, which is free headroom and a
    click on playback;
  * peak-normalises each clip to -1 dBFS, so the *file* carries the headroom
    and the *table* carries the mix — a cue's loudness is now the Volume
    column and nothing else;
  * fades 2 ms in and 8 ms out where a clip starts or ends on a hot sample,
    which is a click on every play.

None of those moves a transient: gain is uniform, so where a clip peaks is
where it peaked, and the `Lead` values stay true across a mastering pass. The
fades touch 2 and 8 ms of the ends, which is why the check re-measures Lead
afterwards rather than assuming it.

Order matters and cost a bug: fading after levelling pulls the peak back down
whenever the loudest sample sits inside the ramp, so the level is set, the
edges are faded, and then the level is set again exactly. Levels and onsets
are read off the loudest channel per frame, not off a mono downmix — a
downmix of a stereo clip whose sides differ reads quieter than the file is,
which is what made a first run report a dozen clips as unmastered when they
were already at -1 dBFS.

It does not touch the music. Those four loops were cut to measured seams and
levelled against each other, and peak-normalising a loop is the wrong
operation on one anyway.

It cannot make a recording *sound* better. Nobody here has heard any of these
— there is no audio output in the environment they were made in — so what is
improved is what can be measured, and that is said plainly rather than dressed
up as a remaster. Note that levelling is gain and gain is not free: a clip
lifted 50 dB brings whatever was under it up 50 dB too, and the `gain` column
says exactly how far each one was moved.

RUN IT from the Unreal project root:

    python3 Tools/audio/master.py              # master the clips in place
    python3 Tools/audio/master.py --check      # measure only; fails if unmastered
    python3 Tools/audio/master.py --quiet      # no table, just the verdict

Both ports get the same files: the clips are mirrored into the Unity port's
Resources, because the two builds must not disagree about what a punch sounds
like. `DT_Sounds.csv` is hand-authored and stays that way; nothing here
writes it.
==============================================================================
"""

import csv
import glob
import math
import os
import struct
import sys
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
UNITY = os.path.abspath(os.path.join(PROJECT, "..", "ahmed-fighter-unity",
                                     "Assets", "Resources", "Audio"))
AUDIO = os.path.join(PROJECT, "Content", "Audio")
TABLE = os.path.join(PROJECT, "Content", "Data", "DT_Sounds.csv")

# -1 dBFS. Not 0: a sample at full scale can still overshoot once an engine
# resamples or encodes it, and a fighting game plays a lot of these at once.
TARGET_PEAK = 0.891
# Where a clip's transient is: the middle of its loudest 5 ms, which is how
# the clips were cut on 2026-09-09 and therefore what the Lead column already
# holds. Not the first sample over a threshold -- that finds where a whoosh
# starts winding up, and a swing scheduled off it lands late by the length of
# its own wind-up.
TRANSIENT_WINDOW = 0.005
# Lead is quoted to the millisecond and two measurements of the same clip sit
# a millisecond or two apart, so only a bigger gap than this is worth a word.
LEAD_TOLERANCE = 0.010
# Edges that are not silent click. These are short enough to be inaudible on
# anything but the click itself.
FADE_IN = 0.002
FADE_OUT = 0.008
HOT_EDGE = 0.01


# ------------------------------------------------------------------- audio

def read(path):
    w = wave.open(path, "rb")
    channels, width, rate, frames = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    raw = w.readframes(frames)
    w.close()
    if width != 2:
        raise ValueError("%s is %d-bit; this expects 16" % (path, width * 8))
    samples = list(struct.unpack("<%dh" % (len(raw) // 2), raw))
    return samples, channels, rate


def write(path, samples, channels, rate):
    w = wave.open(path, "wb")
    w.setnchannels(channels)
    w.setsampwidth(2)
    w.setframerate(rate)
    w.writeframes(struct.pack("<%dh" % len(samples), *samples))
    w.close()


def envelope(samples, channels):
    """The loudest channel, frame by frame.

    Not a mono downmix: a sound that is loud on one side and quiet on the
    other reads quiet in a downmix, and the *file* is as loud as its loudest
    sample. Levels, edges and onsets are all properties of the signal, not of
    which side it happens to be louder on."""
    if channels == 1:
        return [abs(x) for x in samples]
    frames = len(samples) // channels
    return [max(abs(samples[f * channels + c]) for c in range(channels))
            for f in range(frames)]


def transient(env, rate):
    """The middle of the loudest 5 ms: where the sound lands.

    A hit's transient and its peak are the same sample, so on those this is
    just the peak. On a whoosh, which ramps in, it is the swish rather than
    the start of the ramp -- which is the whole reason the column is not a
    threshold crossing."""
    span = min(len(env), max(1, int(TRANSIENT_WINDOW * rate)))
    step = max(1, span // 2)
    best, at = -1.0, 0
    for i in range(0, max(1, len(env) - span + 1), step):
        energy = sum(float(x) * x for x in env[i:i + span])
        if energy > best:
            best, at = energy, i
    return (at + span * 0.5) / rate


def measure(samples, channels, rate):
    env = envelope(samples, channels)
    peak = (max(env) / 32768.0) if env else 0.0
    # DC per channel, worst side: removing one number from both sides of a
    # stereo clip leaves each of them off-centre.
    dc = 0.0
    for c in range(channels):
        col = samples[c::channels]
        if col:
            side = sum(col) / len(col) / 32768.0
            if abs(side) > abs(dc):
                dc = side
    if peak <= 0.0:
        return dict(peak=0.0, dc=dc, lead=0.0, first=0.0, last=0.0,
                    secs=len(env) / rate)
    return dict(peak=peak, dc=dc, lead=transient(env, rate),
                first=env[0] / 32768.0, last=env[-1] / 32768.0,
                secs=len(env) / rate)


def master(samples, channels, rate):
    """DC out, level up, edges faded, DC out again, level set again."""
    n = len(samples)
    if n == 0:
        return samples

    # 1. DC offset, one side at a time.
    work = decentre([float(x) for x in samples], channels)

    # 2. Peak to -1 dBFS. Up as readily as down: a clip that came out quiet
    #    is the bug this is here to fix.
    work = level(work)

    # 3. Edges. Only where they are hot, so an attack that starts at full
    #    scale on the first sample -- which a hit legitimately can -- is not
    #    softened for nothing.
    env = envelope(work, channels)
    if env:
        if env[0] / 32768.0 > HOT_EDGE:
            ramp(work, channels, rate, FADE_IN, at_start=True)
        if env[-1] / 32768.0 > HOT_EDGE:
            ramp(work, channels, rate, FADE_OUT, at_start=False)
        # 4. A ramp is a window, and windowing a 90 ms click moves its mean:
        #    UI_Tap came out of step 3 sitting 4.5e-3 off centre having gone
        #    in centred. So centre it again -- the shift is far under the
        #    threshold that made the edge worth fading, so this does not put
        #    the click back -- and then set the level exactly, because a fade
        #    over the loudest sample (a hit whose crack is its first frame)
        #    takes the level back off.
        work = level(decentre(work, channels))

    return [int(max(-32768, min(32767, round(x)))) for x in work]


def decentre(work, channels):
    """Mean off each channel separately. One number taken off both sides of a
    stereo clip leaves each of them off-centre, which is the bug this had."""
    n = len(work)
    for c in range(channels):
        col = work[c::channels]
        offset = sum(col) / float(len(col))
        for i in range(c, n, channels):
            work[i] -= offset
    return work


def level(work):
    peak = max((abs(x) for x in work), default=0.0) or 1.0
    gain = (TARGET_PEAK * 32768.0) / peak
    return [x * gain for x in work]


def ramp(work, channels, rate, seconds, at_start):
    frames = max(1, int(seconds * rate))
    total = len(work) // channels
    frames = min(frames, total)
    for f in range(frames):
        k = (f / frames) if at_start else ((frames - f) / frames)
        index = f if at_start else (total - frames + f)
        for c in range(channels):
            work[index * channels + c] *= k


# ------------------------------------------------------------------- table

def clips():
    """Every sound effect, and where its twin lives in the Unity port. The
    music is deliberately not here."""
    found = []
    for path in sorted(glob.glob(os.path.join(AUDIO, "**", "S_*.wav"), recursive=True)):
        found.append((path, os.path.join(UNITY, os.path.relpath(path, AUDIO))))
    return found


def rows():
    """The table, with one long-standing typo forgiven.

    `Music_Boss`'s description -- "ZAYOS in the cellar, AL-SAQR, AL-WAHSH" --
    was written with its commas and without its quotes, so it parses as
    twelve fields rather than ten and the surplus lands under a `None` key.
    Nobody noticed because Description is the one column no code reads. It
    matters here only because writing the table back with that key in it
    throws, and the first run of this tool threw *after* truncating the file
    and took the four music rows with it. So: put the description back
    together, and let the writer quote it properly on the way out."""
    with open(TABLE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        data = []
        for r in reader:
            spill = r.pop(None, None)
            if spill:
                r["Description"] = ",".join([r["Description"]] + list(spill))
            data.append(r)
        return fields, data


def cue_of(path, data):
    """The row whose clip this is. The table names an engine asset path; the
    file's stem is the last part of it."""
    stem = os.path.splitext(os.path.basename(path))[0]
    for r in data:
        if r["Sound"].split(".")[-1].split("/")[-1] == stem:
            return r
    return None


# -------------------------------------------------------------------- main

def main():
    check = "--check" in sys.argv
    quiet = "--quiet" in sys.argv
    _, data = rows()
    found = clips()

    if not quiet:
        print("%-16s %8s %8s %7s   %9s %9s   %6s %6s" %
              ("cue", "peak", "->", "gain", "dc", "->", "lead", "meas"))
    changed, problems, drifted, most_gain = 0, [], [], 0.0

    for path, twin in found:
        samples, channels, rate = read(path)
        before = measure(samples, channels, rate)
        # Checking means measuring what is on disk. Mastering a clip again and
        # comparing that to the table only ever tells you whether the tool
        # agrees with itself.
        fixed = samples if check else master(samples, channels, rate)
        after = before if check else measure(fixed, channels, rate)

        row = cue_of(path, data)
        name = row["Name"] if row else os.path.basename(path)
        table_lead = float(row["Lead"]) if row else 0.0
        measured = round(after["lead"], 3)
        if abs(table_lead - measured) > LEAD_TOLERANCE:
            drifted.append("%s: Lead says %.3f s, the loudest 5 ms is at %.3f s"
                           % (name, table_lead, measured))

        moved = (abs(before["peak"] - after["peak"]) > 0.005
                 or abs(before["dc"]) > 1e-4)
        if moved:
            changed += 1
        gain_db = (20.0 * math.log10(after["peak"] / before["peak"])
                   if before["peak"] > 0 and after["peak"] > 0 and not check else 0.0)
        most_gain = max(most_gain, gain_db)
        if not quiet and moved:
            print("%-16s %8.3f %8.3f %+6.1f   %9.5f %9.5f   %6.3f %6.3f" %
                  (name, before["peak"], after["peak"], gain_db,
                   before["dc"], after["dc"], table_lead, measured))

        if check:
            if abs(after["peak"] - TARGET_PEAK) > 0.01:
                problems.append("%s peaks at %.3f, not -1 dBFS" % (name, after["peak"]))
            if abs(after["dc"]) > 0.001:
                problems.append("%s sits %.4f off centre" % (name, after["dc"]))
            continue

        write(path, fixed, channels, rate)
        os.makedirs(os.path.dirname(twin), exist_ok=True)
        write(twin, fixed, channels, rate)

    print()
    if drifted:
        print("Lead is not this tool's to set -- these are for a person to look")
        print("at, and two of them are a cue with two bangs in it:")
        for d in drifted:
            print("  " + d)
        print()
    if check:
        for p in problems:
            print("  " + p)
        print("%d clips, %d not mastered" % (len(found), len(problems)))
        return 1 if problems else 0

    print("%d clips mastered to -1 dBFS, DC removed, edges faded; %d moved."
          % (len(found), changed))
    print("Loudest lift %+.0f dB -- whatever was under that clip came up with it." % most_gain)
    print("Both ports written. DT_Sounds.csv untouched: Lead still measures true.")
    print("Nothing here has been listened to: what is fixed is what can be measured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
