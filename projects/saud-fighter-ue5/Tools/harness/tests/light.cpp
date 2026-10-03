/**
 * What the night's lights cost, executed (SaudLight.h).
 *
 * That a light is drawn as far as its pool is CullDegrees across and no
 * farther, that only the nearest ShadowBudget shadowed fires cast and none
 * beyond the reach, and that a camera swaying back and forth on its way
 * down a street of fires does not flicker their shadows.
 */
#include "../HarnessTypes.h"
#include "../../../Source/SaudFighter/Combat/SaudLight.h"

#include <cstdio>
#include <cmath>
#include <vector>

static int Fails = 0;
static void Check(bool Ok, const char* What)
{
    if (!Ok) { ++Fails; std::printf("  FAIL  %s\n", What); }
}
static bool Near(float A, float B, float Eps) { return std::fabs(A - B) <= Eps; }

using namespace SaudLight;

static std::vector<bool> Pick(const std::vector<float>& Dist, const std::vector<bool>& Was)
{
    const int N = static_cast<int>(Dist.size());
    bool W[256] = {}, O[256] = {};
    for (int I = 0; I < N; ++I) W[I] = Was[I];
    PickShadows(Dist.data(), W, N, O);
    return std::vector<bool>(O, O + N);
}

static void Drawn()
{
    std::printf("DRAWN  (a pool %.1f degrees across, fading over %.0f %%)\n", CullDegrees, FadeShare * 100.f);
    // build_souq NIGHT: a brazier's pool 4.5 m, a pyre's 9 m, a lantern's 2 m
    Check(Near(DrawDistanceCm(450.f), 10306.f, 5.f), "a brazier's light is drawn out to 103 m");
    Check(Near(DrawDistanceCm(900.f), 20613.f, 10.f), "a pyre's light is drawn out to 206 m");
    Check(Near(DrawDistanceCm(200.f), 4581.f, 3.f), "a lantern's light is drawn out to 46 m");
    Check(Near(FadeRangeCm(450.f), DrawDistanceCm(450.f) * 0.25f, 1.f), "a light fades over the last quarter of its distance");
    std::printf("  a brazier to %.0f m, a pyre to %.0f m, a lantern to %.0f m\n",
                DrawDistanceCm(450.f) / 100.f, DrawDistanceCm(900.f) / 100.f, DrawDistanceCm(200.f) / 100.f);
}

static void Budget()
{
    std::printf("SHADOWED  (the nearest %d within %.0f m)\n", ShadowBudget, ShadowReachCm / 100.f);
    // twenty fires 1 m to 20 m off, the far ones listed first
    std::vector<float> D;
    for (int I = 20; I >= 1; --I) D.push_back(I * 100.f);
    std::vector<bool> None(D.size(), false);
    std::vector<bool> O = Pick(D, None);
    int Cast = 0;
    bool Nearest = true;
    for (size_t I = 0; I < D.size(); ++I)
    {
        Cast += O[I];
        if (O[I] != (D[I] <= 800.f)) Nearest = false;
    }
    Check(Cast == 8, "eight shadowed fires cast at once, however many are near");
    Check(Nearest, "the eight that cast are the eight nearest the camera");

    // three fires, two of them out of reach: one casts, not three
    std::vector<float> Far = {1000.f, 4100.f, 9000.f};
    O = Pick(Far, std::vector<bool>(3, false));
    Check(O[0] && !O[1] && !O[2], "nothing beyond the reach casts, however few are near");

    // nothing to pick from
    Check(Pick({}, {}).empty(), "no lights, nothing cast");
}

static void Keep()
{
    std::printf("KEPT  (a light that casts counts %.2fx nearer)\n", KeepFactor);
    // eight fires at 5 m hold seven places; the eighth is between one that
    // casts at 11 m and a rival at 10 m
    std::vector<float> D(7, 500.f);
    D.push_back(1100.f); D.push_back(1000.f);
    std::vector<bool> Was(7, true);
    Was.push_back(true); Was.push_back(false);
    std::vector<bool> O = Pick(D, Was);
    Check(O[7] && !O[8], "a light that casts keeps its shadow against a rival a little nearer");
    D[8] = 900.f;
    O = Pick(D, Was);
    Check(!O[7] && O[8], "it gives it up to a rival clearly nearer");
    // a light that casts, a little past the reach
    O = Pick({4300.f}, {true});
    Check(O[0], "a light that casts keeps it a little past the reach");
    O = Pick({4300.f}, {false});
    Check(!O[0], "a light that does not, does not start there");
}

static void Walk()
{
    std::printf("WALKED  (forty fires down a street, a camera swaying on its way)\n");
    // fires every 8 m along the street, 4 m off it
    const int N = 40;
    std::vector<bool> Was(N, false);
    std::vector<int> Toggles(N, 0);
    int MostAtOnce = 0;
    for (int Step = 0; Step <= 4000; ++Step)
    {
        const float T = Step * 0.05f;
        // down the street at a walk, swaying a metre back and forth
        const float X = T * 150.f + 100.f * std::sin(T * 3.f);
        std::vector<float> D(N);
        for (int I = 0; I < N; ++I) D[I] = std::hypot(I * 800.f - X, 400.f);
        std::vector<bool> O = Pick(D, Was);
        int Now = 0;
        for (int I = 0; I < N; ++I)
        {
            Toggles[I] += O[I] != Was[I];
            Now += O[I];
            Was[I] = O[I];
        }
        if (Now > MostAtOnce) MostAtOnce = Now;
    }
    int Worst = 0;
    for (int I = 0; I < N; ++I) if (Toggles[I] > Worst) Worst = Toggles[I];
    std::printf("  at most %d cast at once; the most a fire's shadow turned on or off: %d\n", MostAtOnce, Worst);
    Check(MostAtOnce <= ShadowBudget, "never more than the budget at once on the walk");
    Check(Worst <= 2, "no fire's shadow flickers: on once and off once on the way past");
}

int main()
{
    Drawn();
    Budget();
    Keep();
    Walk();
    if (Fails) { std::printf("%d FAILED\n", Fails); return 1; }
    std::printf("all light checks passed\n");
    return 0;
}
