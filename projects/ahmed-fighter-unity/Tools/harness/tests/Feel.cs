using System;
using UnityEngine;
using Ahmed.Combat;
using Ahmed.Game;

/// <summary>
/// What a blow feels like, and what the ears do with it.
///
/// All of it is arithmetic that decides feel — how long a hit freezes the
/// pair, how long it holds the one who took it, how far a limb draws back
/// before it is thrown, when a sound may take a cue off another — so all of
/// it can be executed here rather than looked at in an editor nobody has.
/// </summary>
public static class Program
{
    static int fails = 0;
    static void Check(bool ok, string what)
    {
        if (!ok) { fails++; Console.WriteLine("  FAIL  " + what); }
    }

    public static int Main()
    {
        HitStop();
        Stun();
        WindUp();
        Flinch();
        Hearing();
        Console.WriteLine(fails == 0 ? "\nall checks passed" : "\n" + fails + " FAILURES");
        return fails == 0 ? 0 : 1;
    }

    // --------------------------------------------------------------- hit stop

    static void HitStop()
    {
        Console.WriteLine("HIT STOP  (seconds both fighters hang on the contact frame)");
        float blocked = Fighter.HitStopFor(false, false, true);
        float light = Fighter.HitStopFor(false, false, false);
        float heavy = Fighter.HitStopFor(true, false, false);
        float down = Fighter.HitStopFor(true, true, false);
        Console.WriteLine(string.Format(
            "  blocked {0:0.000}   light {1:0.000}   heavy {2:0.000}   knockdown {3:0.000}"
            + "   ({4:0.0}, {5:0.0}, {6:0.0}, {7:0.0} frames at 60 Hz)",
            blocked, light, heavy, down,
            blocked * 60f, light * 60f, heavy * 60f, down * 60f));

        Check(blocked < light, "a blocked blow stops less than a landed one");
        Check(light < heavy, "a heavy stops longer than a light");
        Check(heavy < down, "and a knockdown longest of all");
        Check(down <= 0.1f, "nothing stops for more than a tenth of a second");
        Check(blocked > 0f, "even a block stops a little — it has to read as contact");
    }

    // ------------------------------------------------------------------- stun

    static void Stun()
    {
        Console.WriteLine("\nSTUN  (how long the one who took it is held)");
        // A jab and a haymaker against a 46 hp thug and a 430 hp boss.
        Console.WriteLine("  damage  of max   light    heavy");
        float[] damages = { 4f, 9f, 18f, 40f };
        float previousLight = -1f;
        foreach (float d in damages)
        {
            float l = Fighter.HitStunFor(d, 46f, false);
            float h = Fighter.HitStunFor(d, 46f, true);
            Console.WriteLine(string.Format("  {0,6:0.0}  {1,6:0%}  {2,6:0.000}  {3,6:0.000}",
                d, d / 46f, l, h));
            Check(l > previousLight, "a bigger blow stuns longer (" + d + ")");
            // Above the cap both land on it, which is the cap doing its job.
            Check(h >= l, "and a heavy stuns at least as long as a light of the same damage");
            Check(h > l || h >= 0.55f - 1e-5f,
                  "strictly longer, until both are held by the no-stunlock cap");
            previousLight = l;
        }
        Check(Fighter.HitStunFor(500f, 46f, true) <= 0.55f, "stun is capped — no stunlock");
        Check(Fighter.HitStunFor(0f, 46f, false) >= 0.12f, "and floored — a hit always registers");
        // A boss takes the same blow as a fraction of much more health, so it
        // holds him for less. That is what having 430 hp should feel like.
        Check(Fighter.HitStunFor(18f, 430f, false) < Fighter.HitStunFor(18f, 46f, false),
              "the same blow holds a boss for less time than a thug");
    }

    // ---------------------------------------------------------------- wind-up

    static void WindUp()
    {
        Console.WriteLine("\nWIND-UP  (the limb draws back before it is thrown)");
        // The real rows: a jab's startup is a twitch, a heavy's is a tell.
        Console.WriteLine("  row        startup   cocked for   deepest at   deepest draw");
        string[] names = { "Jab", "Cross", "Hook", "Kick", "Special" };
        float[] startups = { 0.06f, 0.09f, 0.14f, 0.16f, 0.18f };
        float previousWindow = -1f;
        for (int i = 0; i < names.Length; i++)
        {
            float startup = startups[i];
            Check(FighterIK.WindUp(0f, startup) == 0f, names[i] + ": nothing drawn at the start");
            Check(FighterIK.WindUp(startup, startup) == 0f,
                  names[i] + ": released by the first active frame");
            Check(FighterIK.WindUp(startup + 0.05f, startup) == 0f,
                  names[i] + ": nothing drawn once it is out");

            float peak = 0f, peakAt = 0f, window = 0f;
            int rises = 0, falls = 0;
            float last = 0f;
            for (float t = 0f; t <= startup + 1e-4f; t += 1f / 600f)
            {
                float w = FighterIK.WindUp(t, startup);
                Check(w >= 0f && w <= 1f, names[i] + ": draw stays within its range");
                if (w > peak) { peak = w; peakAt = t; }
                if (w > 0.2f) { window += 1f / 600f; }
                if (w > last + 1e-6f) { rises++; }
                if (w < last - 1e-6f) { falls++; }
                last = w;
            }
            Console.WriteLine(string.Format(
                "  {0,-9} {1,7:0.000} s {2,10:0.000} s {3,10:0.000} s {4,12:0.0} cm",
                names[i], startup, window, peakAt, peak * FighterIK.WindUpDraw * 100f));
            Check(peak > 0.98f, names[i] + ": the arm comes all the way back");
            Check(rises > 0 && falls > 0, names[i] + ": it draws back and then releases");
            Check(window > previousWindow,
                  names[i] + ": a longer startup is a longer tell (" + window.ToString("0.000") + " s)");
            previousWindow = window;
        }
        Check(FighterIK.WindUp(0.03f, 0f) == 0f, "a row with no startup has no wind-up");
        Console.WriteLine("  so a jab is a twitch and the finisher is a cocked arm you can step out of.");
    }

    // ----------------------------------------------------------------- flinch

    static void Flinch()
    {
        Console.WriteLine("\nFLINCH");
        Check(FighterIK.FlinchOffset(Vector3.zero).magnitude == 0f, "no blow, no flinch");

        Vector3 small = FighterIK.FlinchOffset(new Vector3(2f, 0f, 0f));
        Vector3 big = FighterIK.FlinchOffset(new Vector3(9f, 0f, 0f));
        Check(small.x > 0f, "the hands go the way the blow pushed him");
        Check(big.x > small.x, "a heavier blow throws them further");
        Check(small.y < 0f && big.y < 0f, "and down — the guard is not up while he wears it");

        int unbounded = 0;
        for (float m = 0f; m < 60f; m += 0.5f)
        {
            for (int a = 0; a < 360; a += 15)
            {
                float r = a * Mathf.Deg2Rad;
                Vector3 o = FighterIK.FlinchOffset(new Vector3(Mathf.Cos(r) * m, 0f,
                                                               Mathf.Sin(r) * m));
                if (o.magnitude > 0.30f) { unbounded++; }
            }
        }
        Check(unbounded == 0, "however hard he is hit the hands stay on the body ("
              + unbounded + " over)");

        Console.WriteLine("\nGUARD SAG  (the only thing that says how hurt an enemy is)");
        Console.WriteLine("  health   hands at");
        float previous = 2f;
        float[] fractions = { 1f, 0.75f, 0.5f, 0.25f, 0f };
        foreach (float f in fractions)
        {
            float sag = FighterIK.GuardSag(f);
            Console.WriteLine(string.Format("  {0,6:0%}  {1,9:0%}", f, sag));
            Check(sag <= previous, "hands come down as health does");
            Check(sag > 0f && sag <= 1f, "and stay on the body");
            previous = sag;
        }
        Check(Mathf.Abs(FighterIK.GuardSag(1f) - 1f) < 1e-5f, "a fresh fighter's guard is full");
    }

    // ---------------------------------------------------------------- hearing

    static void Hearing()
    {
        Console.WriteLine("\nHEARING  (which instance of a cue gets to sound)");
        const float cd = 0.08f;

        Check(AudioLibrary.MayPlay(0.001f, 0f, 40f, 2f), "a cue with no cooldown always sounds");
        Check(AudioLibrary.MayPlay(0.2f, cd, 40f, 2f), "past the cooldown it sounds again");
        Check(!AudioLibrary.MayPlay(0.01f, cd, 40f, 2f),
              "inside it, a distant repeat of a near sound is dropped");
        Check(AudioLibrary.MayPlay(0.01f, cd, 1.5f, 40f),
              "but a blow landing on you takes the cue off one across the district");
        Check(!AudioLibrary.MayPlay(0.01f, cd, 20f, 22f),
              "two at much the same distance do not fight over it");

        Console.WriteLine("  near " + AudioLibrary.NearDistance.ToString("0") + " m, far "
            + AudioLibrary.FarDistance.ToString("0") + " m");
        Check(AudioLibrary.FarDistance > AudioLibrary.NearDistance * 4f,
              "there is a long falloff between full volume and silence");
        Check(AudioLibrary.FarDistance < 130f,
              "and a punch at the far rim of a district is not heard at all");

        Console.WriteLine("\nSWING LEAD  (the swish peaks on the first active frame)");
        Check(Fighter.SwingCueTime(0.18f, 0.05f) > 0.12f && Fighter.SwingCueTime(0.18f, 0.05f) < 0.14f,
              "a 0.18 s startup with a 0.05 s lead fires at 0.13 s");
        Check(Fighter.SwingCueTime(0.06f, 0.20f) == 0f,
              "a lead longer than the startup fires at once rather than in the past");
    }
}
