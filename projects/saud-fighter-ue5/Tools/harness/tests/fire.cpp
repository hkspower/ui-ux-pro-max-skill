/**
 * HAWK FIST's fire, executed: the numbers are the browser's as exported
 * (DT_Talents.csv, Player.json), the fist is lit only with the talent and
 * the MP, only a punch burns, the flame eases on at the browser's rate and
 * is brightest through a punch, the burst's ring grows to its size in its
 * time and the burst outlives its last spark, and the parameter names are
 * what Tools/look/anime_look.py reads.
 */
#include "../HarnessTypes.h"
#include "../../../Source/SaudFighter/Combat/SaudFire.h"

#include <cstdio>
#include <cmath>
#include <cstring>
#include <string>

static int Fails = 0;
static void Check(bool Ok, const char* What)
{
    if (!Ok) { ++Fails; std::printf("  FAIL  %s\n", What); }
}
static bool Near(float A, float B, float Eps = 1e-4f) { return std::fabs(A - B) <= Eps; }

static std::string Slurp(const char* Path)
{
    std::string S;
    if (FILE* F = std::fopen(Path, "rb"))
    {
        char Buf[4096]; size_t N;
        while ((N = std::fread(Buf, 1, sizeof Buf, F)) > 0) S.append(Buf, N);
        std::fclose(F);
    }
    return S;
}

/** The number after `Key` in a JSON file: "Key": 40 */
static float JsonNumber(const std::string& S, const char* Key, bool& Found)
{
    const std::string K = std::string("\"") + Key + "\":";
    const size_t At = S.find(K);
    Found = At != std::string::npos;
    return Found ? std::strtof(S.c_str() + At + K.size(), nullptr) : 0.f;
}

using namespace SaudFire;

static void Numbers()
{
    std::printf("NUMBERS  (the browser's, as exported)\n");
    // DT_Talents.csv: Name,Ability,DisplayName,DisplayNameArabic,Icon,ManaCost,Description
    const std::string T = Slurp("Content/Data/DT_Talents.csv");
    const size_t Row = T.find("\nHawkFist,");
    Check(Row != std::string::npos, "DT_Talents.csv has HawkFist");
    if (Row != std::string::npos)
    {
        // the sixth field
        size_t P = Row + 1; int Field = 0;
        while (Field < 5 && P < T.size()) { if (T[P] == ',') ++Field; ++P; }
        Check(Near(std::strtof(T.c_str() + P, nullptr), ManaCost), "ManaCost is DT_Talents.csv's (14)");
    }
    const std::string J = Slurp("Content/Data/Player.json");
    bool F1, F2, F3;
    const float Base = JsonNumber(J, "BaseMana", F1);
    const float Regen = JsonNumber(J, "ManaRegenPerSecond", F2);
    const float Landed = JsonNumber(J, "ManaPerLandedHit", F3);
    Check(F1 && F2 && F3, "Player.json has the mana numbers");
    Check(Near(Base, MaxMana) && Near(Regen, ManaRegenPerSecond) && Near(Landed, ManaPerLandedHit),
          "MaxMana, regen and the landed-hit gain are Player.json's (40, 5, 4)");
    Check(Near(ReachCm, 24.f) && Near(PushCm, 216.f), "10 px of reach and 90 px of push through PX_TO_CM 2.4");
    Check(Near(CmPerFigurePx, 180.f / 148.f), "a figure pixel is 1.80 m over 148 px");
    Check(DamageMultiplier > 1.f && HeatSwinging > HeatIdle && HeatIdle > 0.f, "a burning punch hits harder and burns brighter");
}

static void Rules()
{
    std::printf("RULES  (hawkReady, hawkAttack)\n");
    Check(!Lit(false, 100.f), "no talent, no fire");
    Check(!Lit(true, ManaCost - 0.01f), "under the cost, no fire");
    Check(Lit(true, ManaCost), "at the cost, lit");
    Check(Burning(true, true) && !Burning(true, false) && !Burning(false, true), "only a lit punch burns");
    Check(FlameHand(false, 0) == 'l' && FlameHand(false, 'r') == 'l', "standing, the lead fist");
    Check(FlameHand(true, 'r') == 'r' && FlameHand(true, 'l') == 'l', "punching, the fist that punches");
    Check(FlameHand(true, 0) == 'l', "a strike with no arm (a kick) leaves it on the lead fist");
    Check(Near(Heat(1.f, true), HeatSwinging) && Near(Heat(1.f, false), HeatIdle) && Heat(0.f, true) == 0.f,
          "heat is the eased lit-ness times the swing's brightness");

    // The tongues: each narrower and shorter than the last, longer with heat.
    bool Order = true;
    for (int i = 1; i < Tongues; ++i)
        Order = Order && TongueHalfWidthPx(i) < TongueHalfWidthPx(i - 1)
                      && TongueLengthPx(i, 1.f) < TongueLengthPx(i - 1, 1.f);
    Check(Order, "each tongue is narrower and shorter than the one under it");
    Check(Near(TongueLengthPx(0, HeatSwinging), 20.f * HeatSwinging) && TongueLengthPx(0, 0.f) == 0.f,
          "a tongue's length is its heat's");
    Check(std::fabs(Sway(0, 0.f)) < 1e-6f && std::fabs(Sway(0, 0.3f)) <= SwayPx + 1e-6f
          && !Near(Sway(0, 0.3f), Sway(1, 0.3f)), "the tongues sway within their swing, out of phase");
    Check(GlowRadiusPx > TongueLengthPx(0, 1.f), "the glow reaches past the longest tongue");
}

static void Burst()
{
    std::printf("BURST  (applyHit's ring and sparks)\n");
    Check(Near(RingRadiusPx(0.f), RingFromPx) && Near(RingRadiusPx(RingSeconds * 0.5f), 0.5f * (RingFromPx + RingToPx)),
          "the ring grows from 8 px");
    Check(RingRadiusPx(RingSeconds) < 0.f && RingRadiusPx(-0.1f) < 0.f, "and is gone at 0.28 s, or before a hit");
    bool Grows = true; float Prev = -1.f;
    for (int i = 0; i < 27; ++i) { const float R = RingRadiusPx(i * 0.01f); Grows = Grows && R > Prev; Prev = R; }
    Check(Grows, "monotonically");
    Check(Near(BurstSeconds, SparkLifeMax) && BurstSeconds > RingSeconds, "the burst outlives its ring, to the last spark");
    Check(SparksHot + SparksPale == 22 && SparkSpeedHotPx > SparkSpeedPalePx, "14 hot sparks fly further than 8 pale ones");
    Check(Near(SparkDragPerSecond, -60.f * std::log(0.96f), 1e-3f), "the drag is the browser's 0.96 a frame at 60 Hz, as a rate");
    Check(Near(BurstUpPx / FigurePx, 0.5f), "the burst is at half the figure: the actor's own location");
}

static void State()
{
    std::printf("STATE  (the flame eases, the burst runs in game time)\n");
    FState S;
    Check(S.Lit01 == 0.f && !S.Bursting(), "cold at rest");
    S.Tick(0.1f, true);
    Check(Near(S.Lit01, 0.45f), "lit: 0.45 after 0.1 s (approach at 4.5 a second)");
    S.Tick(0.1f, true); S.Tick(0.1f, true);
    Check(Near(S.Lit01, 1.f), "full in under a quarter second");
    S.Tick(1.f, true);
    Check(Near(S.Lit01, 1.f), "and held, never over 1");
    S.Tick(0.1f, false);
    Check(Near(S.Lit01, 0.55f), "goes out at the same rate");
    // The same lit-ness at any frame rate: real time, not frames.
    FState A, B;
    for (int i = 0; i < 30; ++i) A.Tick(1.f / 30.f, true);
    for (int i = 0; i < 240; ++i) B.Tick(1.f / 240.f, true);
    Check(Near(A.Lit01, B.Lit01, 1e-3f), "the same flame at 30 and 240 Hz");

    FState F;
    F.Tick(0.5f, true);
    F.Burn();
    const float Seed0 = F.BurstSeed;
    Check(F.Bursting() && Near(F.BurstAge, 0.f), "a burning hit starts the burst");
    F.Tick(0.1f, true);
    Check(Near(F.BurstAge, 0.1f) && F.Bursting(), "the burst ages with the game's clock");
    F.Tick(0.f, true);
    Check(Near(F.BurstAge, 0.1f), "and stands still through a freeze (no game time passes)");
    F.Tick(BurstSeconds, true);
    Check(!F.Bursting() && F.BurstAge < 0.f, "and is gone after the last spark");
    F.Burn();
    Check(F.BurstSeed != Seed0, "a second burst throws different sparks");
    Check(F.Clock > 0.6f, "the sway's clock runs");

    Check(std::strcmp(Param::FireHeat, "FireHeat") == 0 && std::strcmp(Param::BurnSeed, "BurnSeed") == 0,
          "parameter names (anime_look.py checks the other side)");
}

int main()
{
    Numbers(); Rules(); Burst(); State();
    if (Fails) { std::printf("%d fire check(s) failed\n", Fails); return 1; }
    std::printf("all fire checks passed\n");
    return 0;
}
