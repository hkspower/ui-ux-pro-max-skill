/**
 * The anime look's moving parts, executed: which blows get an impact frame
 * and of what shape, that the picture's state keeps the bigger of two blows
 * and runs out in real time, that the speed lines redraw on twos, and that
 * the manga HUD stays inside the title-safe area and legible from a couch
 * at every screen shape and size a console or PC puts it on.
 */
#include "../HarnessTypes.h"
#include "../../../Source/SaudFighter/Combat/SaudFeel.h"
#include "../../../Source/SaudFighter/Combat/SaudAnime.h"

#include <cstdio>
#include <cmath>
#include <cstring>
#include <initializer_list>

static int Fails = 0;
static void Check(bool Ok, const char* What)
{
    if (!Ok) { ++Fails; std::printf("  FAIL  %s\n", What); }
}
static bool Near(float A, float B, float Eps = 1e-4f) { return std::fabs(A - B) <= Eps; }

using namespace SaudAnime;

static void Blows()
{
    std::printf("BLOWS\n");
    const FBlowLook Light = ForBlow(false, false, false, false);
    const FBlowLook Heavy = ForBlow(true, false, false, false);
    const FBlowLook Down = ForBlow(false, false, false, true);
    const FBlowLook Block = ForBlow(true, true, false, false);
    const FBlowLook Parry = ForBlow(false, false, true, false);

    Check(Light.Impact.Seconds == 0.f && Light.SpeedSeconds == 0.f, "a light hit gets no impact frame");
    Check(Block.Impact.Seconds == 0.f && Block.SpeedSeconds == 0.f, "a block gets none");
    Check(Near(Heavy.Impact.Seconds, Frame) && !Heavy.Impact.bInvertFirst, "a heavy hit: one frame, paper-lit");
    Check(Near(Down.Impact.Seconds, 2.f * Frame) && !Down.Impact.bInvertFirst && Down.Impact.bInvertSecond,
          "a knockdown: two frames, the second flipped");
    Check(Near(Parry.Impact.Seconds, 2.f * Frame) && Parry.Impact.bInvertFirst && !Parry.Impact.bInvertSecond,
          "a parry: two frames, the first flipped");
    Check(Down.SpeedSeconds > Heavy.SpeedSeconds, "a knockdown's speed lines outlast a heavy's");

    // The heavy's one frame is drawn inside its own freeze: the frame the
    // player sees stand still IS the ink frame.
    const SaudFeel::FBlowFeel HF = SaudFeel::ForBlow(true, false, false, false, false, true);
    Check(Heavy.Impact.Seconds <= HF.HitStop, "the heavy's impact frame fits inside its hitstop");
    // A knockdown with a knockdown's (heavy) hitstop overlaps its first frame.
    const SaudFeel::FBlowFeel DF = SaudFeel::ForBlow(true, false, false, true, false, true);
    Check(Frame <= DF.HitStop, "a knockdown's first impact frame is inside the freeze");
}

static void State()
{
    std::printf("STATE\n");
    FState S;
    Check(S.ImpactValue() == 0.f && S.SpeedValue() == 0.f, "nothing at rest");

    S.Add(ForBlow(false, false, false, true));          // knockdown
    Check(S.ImpactValue() == 1.f && S.InvertValue() == 0.f, "knockdown: first frame straight");
    S.Tick(1.1f * Frame);
    Check(S.ImpactValue() == 1.f && S.InvertValue() == 1.f, "knockdown: second frame flipped");
    S.Tick(1.0f * Frame);
    Check(S.ImpactValue() == 0.f && S.InvertValue() == 0.f, "and then gone: a cut, not a fade");

    // Speed lines: full, then thinning, then gone, monotonically.
    FState V;
    V.Add(ForBlow(true, false, false, false));
    float Prev = 2.f;
    bool Mono = true, Held = true;
    const float Total = V.SpeedTotal;
    for (int i = 0; i < 100; ++i)
    {
        const float T = V.SpeedElapsed / Total;
        const float Now = V.SpeedValue();
        if (Now > Prev + 1e-6f) Mono = false;
        if (T <= SpeedHold - 0.01f && !Near(Now, 1.f)) Held = false;
        Prev = Now;
        V.Tick(Total / 80.f);
    }
    Check(Mono, "the speed lines only ever thin");
    Check(Held, "they are full for the first share of their life");
    Check(V.SpeedValue() == 0.f, "and gone at the end");

    // Peaks: a light blow never cuts a running impact short; a new big one
    // restarts it.
    FState P;
    P.Add(ForBlow(false, false, false, true));
    P.Tick(0.5f * Frame);
    P.Add(ForBlow(false, false, false, false));          // light: nothing
    Check(P.ImpactValue() == 1.f && Near(P.ImpactElapsed, 0.5f * Frame), "a light blow leaves the impact alone");
    P.Add(ForBlow(true, false, true, false));            // parry, longer than what is left
    Check(Near(P.ImpactElapsed, 0.f) && P.Impact.bInvertFirst, "a parry replaces it from its start");
    FState Q;
    Q.Add(ForBlow(false, false, false, true));           // 2 frames
    Q.Add(ForBlow(true, false, false, false));           // 1 frame, shorter than the 2 left
    Check(Near(Q.Impact.Seconds, 2.f * Frame), "a shorter impact never replaces a longer one running");

    // On twos.
    FState T;
    int Changes = 0;
    float Last = T.Seed();
    for (int i = 0; i < 240; ++i)
    {
        T.Tick(1.f / 240.f);                             // one second at 240 Hz
        if (T.Seed() != Last) { ++Changes; Last = T.Seed(); }
    }
    Check(Changes >= 11 && Changes <= 12, "the seed changes 12 times a second: on twos");
    // The same at 30 Hz: it is real time, not frames rendered.
    FState T30;
    int C30 = 0;
    float L30 = T30.Seed();
    for (int i = 0; i < 30; ++i)
    {
        T30.Tick(1.f / 30.f);
        if (T30.Seed() != L30) { ++C30; L30 = T30.Seed(); }
    }
    Check(C30 >= 11 && C30 <= 12, "...whatever the frame rate");

    Check(std::strcmp(Param::Impact, "Impact") == 0 && std::strcmp(Param::SpeedSeed, "SpeedSeed") == 0,
          "parameter names (anime_look.py checks the other side)");
}

using namespace SaudHud;

// Title-safe is the broadcast standard, 90 % of each dimension -- written
// here rather than read from the header, so a header that forgot it fails.
static bool Inside(const FPage& P, const FRect& R)
{
    const float E = 0.5f, MX = 0.05f * P.ScreenW, MY = 0.05f * P.ScreenH;
    return R.X >= MX - E && R.Y >= MY - E
        && R.X + R.W <= P.ScreenW - MX + E && R.Y + R.H <= P.ScreenH - MY + E;
}
static bool Overlap(const FRect& A, const FRect& B)
{
    return A.X < B.X + B.W && B.X < A.X + A.W && A.Y < B.Y + B.H && B.Y < A.Y + A.H;
}

static void Hud()
{
    std::printf("HUD\n");
    const float Shapes[][2] = {{1920, 1080}, {1280, 720}, {3840, 2160}, {2560, 1080},
                               {3440, 1440}, {1600, 1200}, {1680, 1050}};
    bool AllIn = true, Apart = true, Legible = true, Order = true;
    for (const auto& S : Shapes)
    {
        const FPage P = FPage::For(S[0], S[1]);
        const FLayout L = Lay(P);
        const FRect Combo = {L.Combo.X - L.ComboRadius, L.Combo.Y - L.ComboRadius,
                             2 * L.ComboRadius, 2 * L.ComboRadius};
        const FRect Parts[] = {L.PlayerPanel, L.Health, L.Stamina, L.BossPanel, L.BossHealth, Combo,
                               L.Rage[0], L.Rage[RageBlocks - 1]};
        for (const FRect& R : Parts) AllIn = AllIn && Inside(P, R);
        Apart = Apart && !Overlap(L.PlayerPanel, Combo) && !Overlap(L.PlayerPanel, L.BossPanel)
                      && !Overlap(Combo, L.BossPanel);
        for (float T : {NameText, BossNameText, ComboText})
            Legible = Legible && P.Px(T) >= MinTextShare * S[1] - 0.01f;
        // The bars sit inside their panel and the rage blocks run left to
        // right without touching.
        const FRect& Pn = L.PlayerPanel;
        Order = Order && L.Health.X >= Pn.X && L.Health.X + L.Health.W <= Pn.X + Pn.W
                      && L.Stamina.Y + L.Stamina.H <= Pn.Y + Pn.H
                      && L.BossHealth.X + L.BossHealth.W <= L.BossPanel.X + L.BossPanel.W;
        for (int i = 1; i < RageBlocks; ++i)
            Order = Order && L.Rage[i].X >= L.Rage[i - 1].X + L.Rage[i - 1].W;
        Order = Order && L.Rage[RageBlocks - 1].X + L.Rage[RageBlocks - 1].W <= Pn.X + Pn.W;
    }
    Check(AllIn, "everything is inside the title-safe area, at every screen shape");
    Check(Apart, "the panels never overlap");
    Check(Legible, "no text the player reads is under 1/36 of the screen");
    Check(Order, "bars inside their panels, rage blocks in a row");

    // A bar's quad: full width at 1, a line at 0, leaning right.
    FPoint Q[4];
    const FRect R = {100, 50, 400, 40};
    BarQuad(R, 1.f, Q);
    Check(Near(Q[2].X, R.X + R.W) && Near(Q[1].X - Q[0].X, R.H * Lean), "a full bar reaches its end, leaning");
    BarQuad(R, 0.f, Q);
    Check(Near(Q[3].X, Q[0].X) && Near(Q[2].X, Q[1].X), "an empty bar is a line");
    BarQuad(R, 7.f, Q);
    Check(Near(Q[2].X, R.X + R.W), "fill is clamped");

    // The ghost: holds, then drains to the bar, never under it; heals jump.
    FGhost G;
    G.Tick(1.f, 0.016f);
    G.Tick(0.6f, 0.016f);
    Check(Near(G.Value, 1.f), "the ghost stays where the bar was...");
    for (int i = 0; i < 20; ++i) G.Tick(0.6f, 0.016f);   // 0.32 s
    Check(Near(G.Value, 1.f), "...for the beat");
    bool Never = true;
    for (int i = 0; i < 200; ++i) { G.Tick(0.6f, 0.016f); Never = Never && G.Value >= 0.6f - 1e-6f; }
    Check(Never && Near(G.Value, 0.6f), "then drains down to it and never under");
    G.Tick(0.9f, 0.016f);
    Check(Near(G.Value, 0.9f), "a heal is followed at once");
    G.Tick(0.5f, 0.016f);
    for (int i = 0; i < 10; ++i) G.Tick(0.5f, 0.016f);
    G.Tick(0.3f, 0.016f);                                // a second cut mid-beat
    Check(Near(G.Value, 0.9f) && Near(G.Hold, FGhost::HoldSeconds - 0.016f), "a new cut restarts the beat");

    // Rage blocks add up to the rage, and fill in order.
    bool Sums = true, InOrder = true;
    for (int k = 0; k <= 50; ++k)
    {
        const float Rg = k / 50.f;
        float Sum = 0.f;
        for (int i = 0; i < RageBlocks; ++i)
        {
            Sum += RageBlock(Rg, i);
            if (i && RageBlock(Rg, i) > 0.f && RageBlock(Rg, i - 1) < 1.f) InOrder = false;
        }
        Sums = Sums && Near(Sum / RageBlocks, Rg, 1e-5f);
    }
    Check(Sums && InOrder, "the rage blocks are the rage, filled left to right");

    // The burst alternates out and in, and turns with the count.
    const FPoint C = {0, 0};
    bool Alt = true;
    for (int i = 0; i < 2 * BurstPoints; ++i)
    {
        const FPoint Pt = BurstPoint(C, 100.f, 3, i);
        const float Rr = std::sqrt(Pt.X * Pt.X + Pt.Y * Pt.Y);
        Alt = Alt && Near(Rr, i % 2 ? 100.f * BurstInner : 100.f, 1e-3f);
    }
    Check(Alt, "the starburst alternates its radius");
    Check(!Near(BurstPoint(C, 100, 3, 0).X, BurstPoint(C, 100, 4, 0).X), "and turns as the count rises");
    Check(Near(ComboPunch(0.f), 1.35f) && ComboPunch(1.f) < 1.001f, "the count punches and settles");
}

int main()
{
    Blows();
    State();
    Hud();
    if (Fails) { std::printf("%d anime check(s) failed\n", Fails); return 1; }
    std::printf("all anime checks passed\n");
    return 0;
}
