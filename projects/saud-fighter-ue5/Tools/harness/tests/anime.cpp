/**
 * The anime look's moving parts, executed: which blows get an impact frame
 * and of what shape and tone, the mark where a heavy blow lands and the
 * wound border when it lands on the player, that the picture's state keeps
 * the bigger of two blows and runs out in real time, that the speed lines
 * redraw on twos -- and the HUD, since 2026-09-28 as what SaudHud::Build
 * actually DRAWS, not the rectangles it is laid out from: every vertex
 * inside the title-safe area and nothing in the fight, legible from a
 * couch, bars that read against their troughs, at every screen shape and
 * size a console or PC puts it on.
 *
 * Every check here has a sabotage in Tools/harness/bites.txt that
 * Tools/harness/bite.sh applies to a copy and proves is caught.
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
    Check(Near(Heavy.Impact.Seconds, Frame) && !Heavy.Impact.bInvertFirst, "a heavy hit: one frame, tone-lit");
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

    // 2026-09-28. The tone: a blow's blood, a parry's bone.
    Check(Heavy.Impact.Tone == ETone::Blood && Down.Impact.Tone == ETone::Blood,
          "a heavy hit and a knockdown are cut in blood");
    Check(Parry.Impact.Tone == ETone::Bone, "a parry is cut in bone");
    // The mark: only where a blow lands heavy.
    Check(Heavy.MarkLife > 0.f && Down.MarkLife > 0.f && Light.MarkLife == 0.f && Block.MarkLife == 0.f
              && Parry.MarkLife == 0.f,
          "the mark is only on heavy clean hits and knockdowns");
    // ...standing for the whole of the heavy freeze, the star gone before
    // the drops. (1/24 s is 0.042, under the freeze's 0.075.)
    Check(MarkHold >= SaudFeel::HitStopHeavy - 1e-6f, "the mark stands for the whole heavy freeze");
    Check(MarkHold < MarkSpark && MarkSpark < MarkSeconds, "the star goes before the drops");
    // The wound: only on the player, only when hit heavy or knocked down.
    const bool bWounds = ForBlow(true, false, false, false, true).WoundAmp > 0.f
                      && ForBlow(false, false, false, true, true).WoundAmp > 0.f;
    const bool bSpares = Heavy.WoundAmp == 0.f && Down.WoundAmp == 0.f
                      && ForBlow(false, false, false, false, true).WoundAmp == 0.f
                      && ForBlow(true, true, false, false, true).WoundAmp == 0.f
                      && ForBlow(false, false, true, false, true).WoundAmp == 0.f;
    Check(bWounds && bSpares, "the wound only when the player is hit heavy or knocked down");
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
    float Prev = 2.f, At80 = 1.f;
    bool Mono = true, Held = true;
    const float Total = V.SpeedTotal;
    for (int i = 0; i < 100; ++i)
    {
        const float T = V.SpeedElapsed / Total;
        const float Now = V.SpeedValue();
        if (Now > Prev + 1e-6f) Mono = false;
        if (T <= SpeedHold - 0.01f && !Near(Now, 1.f)) Held = false;
        if (i == 64) At80 = Now;                          // 80 % of their life
        Prev = Now;
        V.Tick(Total / 80.f);
    }
    Check(Mono, "the speed lines only ever thin");
    Check(Held, "they are full for the first share of their life");
    Check(At80 < 0.9f, "and thin before they go, not cut off");
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
    // The brush and the grain boil on the same seed (2026-09-28): the name
    // M_Anime_Post and M_Anime_Frame read it by.
    Check(std::strcmp(Param::Boil, "Boil") == 0, "the boil is written as Boil (anime_look.py checks the other side)");

    // 2026-09-28. A burning punch: OnBurn arrives after OnBlow in the same
    // call, so the frame this blow started is on its first tick, and goes
    // ember; one already running is left alone, and so is a parry's bone.
    FState B;
    B.Add(ForBlow(true, false, false, false));
    B.MarkBurning();
    const bool bEmber = B.Impact.Tone == ETone::Ember && B.ToneValue() == 1.f;
    FState B2;
    B2.Add(ForBlow(false, false, false, true));
    B2.Tick(0.5f * Frame);
    B2.MarkBurning();
    FState B3;
    B3.Add(ForBlow(false, false, true, false));
    B3.MarkBurning();
    Check(bEmber && B2.Impact.Tone == ETone::Blood && B3.Impact.Tone == ETone::Bone && B3.ToneValue() == 2.f,
          "a burning punch's own frame goes ember, and nothing else does");
    FState Idle;
    Idle.MarkBurning();
    Check(Idle.ToneValue() == 0.f && Idle.Impact.Tone == ETone::Blood, "no impact, no tone");

    // The mark: none at rest, from 0 when a heavy blow lands, in real time,
    // gone at 6/24 s (written here, not read from the header); a new one
    // restarts it with a new seed.
    FState M;
    const bool bNone = M.MarkAge() < 0.f;
    M.Add(ForBlow(true, false, false, false));
    const bool bStarts = M.MarkAge() == 0.f;
    const float Seed1 = M.MarkSeed();
    for (int i = 0; i < 3; ++i) M.Tick(1.f / 24.f);
    const bool bRuns = Near(M.MarkAge(), 3.f / 24.f, 1e-5f);
    M.Tick(2.99f / 24.f);
    const bool bLasts = M.MarkAge() > 0.f;
    M.Tick(0.02f / 24.f);
    const bool bGone = M.MarkAge() < 0.f;
    Check(bNone && bStarts && bRuns && bLasts && bGone, "the mark runs in real time and is gone at 6/24 s");
    M.Add(ForBlow(false, false, false, false));          // light: no mark
    const bool bLightNone = M.MarkAge() < 0.f;
    M.Add(ForBlow(false, false, false, true));
    Check(bLightNone && M.MarkAge() == 0.f && M.MarkSeed() != Seed1, "a new mark restarts it, with a new seed");

    // The wound: held for one film frame, then only ever falling, straight,
    // to nothing at 0.30 s.
    FState W;
    W.Add(ForBlow(true, false, false, false, true));
    bool Hold = true, Falls = true, Straight = true;
    float PrevW = 2.f;
    for (int i = 0; i <= 84; ++i)                         // 0.35 s at 240 Hz
    {
        const float Tw = static_cast<float>(i) / 240.f;
        const float Now = W.WoundValue();
        if (Tw < Frame - 1e-4f && !Near(Now, 1.f)) Hold = false;
        if (Now > PrevW + 1e-6f) Falls = false;
        if (i == 36 && !Near(Now, 1.f - (0.15f - Frame) / (0.30f - Frame), 0.02f)) Straight = false;   // 0.15 s
        PrevW = Now;
        W.Tick(1.f / 240.f);
    }
    Check(Hold && Falls && Straight && W.WoundValue() == 0.f,
          "the wound is held one frame, then falls straight to nothing at 0.30 s");
    FState W2;
    W2.Add(ForBlow(true, false, false, false, true));
    for (int i = 0; i < 36; ++i) W2.Tick(1.f / 240.f);
    const float Running = W2.WoundValue();
    W2.Add(ForBlow(false, false, false, false, true));   // light, on the player
    W2.Add(ForBlow(true, false, false, false, false));   // heavy, on someone else
    const bool bKept = Near(W2.WoundValue(), Running);
    W2.Add(ForBlow(false, false, false, true, true));    // knocked down: a new wound
    Check(bKept && W2.WoundValue() == 1.f, "a lighter blow never cuts a running wound short");

    Check(std::strcmp(Param::ImpactTone, "ImpactTone") == 0 && std::strcmp(Param::Wound, "Wound") == 0
              && std::strcmp(Param::MarkAge, "MarkAge") == 0 && std::strcmp(Param::MarkSeed, "MarkSeed") == 0,
          "the tone, wound and mark parameter names (anime_look.py checks the other side)");
}

using namespace SaudHud;

// ------------------------------------------------------------ HUD helpers
static const float Shapes[][2] = {{1920, 1080}, {1280, 720}, {3840, 2160}, {2560, 1080},
                                  {3440, 1440}, {1600, 1200}, {1680, 1050}};
static FDrawList List;

// Title-safe is the broadcast standard, 90 % of each dimension -- written
// here rather than read from the header, so a header that forgot it fails.
static bool InSafe(const FPage& P, float X, float Y)
{
    const float E = 0.5f, MX = 0.05f * P.ScreenW, MY = 0.05f * P.ScreenH;
    return X >= MX - E && Y >= MY - E && X <= P.ScreenW - MX + E && Y <= P.ScreenH - MY + E;
}
static float Cross(const FPoint& A, const FPoint& B, const FPoint& C)
{
    return (B.X - A.X) * (C.Y - A.Y) - (B.Y - A.Y) * (C.X - A.X);
}
/** WCAG 2.1 contrast of two linear colours. */
static float Contrast(const FRgba& A, const FRgba& B)
{
    const float La = 0.2126f * A.R + 0.7152f * A.G + 0.0722f * A.B;
    const float Lb = 0.2126f * B.R + 0.7152f * B.G + 0.0722f * B.B;
    return (std::fmax(La, Lb) + 0.05f) / (std::fmin(La, Lb) + 0.05f);
}
struct FBox { float X0 = 1e9f, Y0 = 1e9f, X1 = -1e9f, Y1 = -1e9f; bool Any = false; };
static void Add(FBox& B, const FPoint& P)
{
    B.X0 = std::fmin(B.X0, P.X); B.Y0 = std::fmin(B.Y0, P.Y);
    B.X1 = std::fmax(B.X1, P.X); B.Y1 = std::fmax(B.Y1, P.Y); B.Any = true;
}
static bool Overlap(const FBox& A, const FBox& B)
{
    return A.Any && B.Any && A.X0 < B.X1 && B.X0 < A.X1 && A.Y0 < B.Y1 && B.Y0 < A.Y1;
}
static FBox GroupBox(EHudGroup G)
{
    FBox B;
    for (int t = 0; t < List.NumTris; ++t)
        if (List.Tris[t].Group == G)
            for (const FHudVert& V : List.Tris[t].V) Add(B, V.P);
    return B;
}
static FBox PartBox(EHudPart Pt)
{
    FBox B;
    for (int t = 0; t < List.NumTris; ++t)
        if (List.Tris[t].Part == Pt)
            for (const FHudVert& V : List.Tris[t].V) Add(B, V.P);
    return B;
}
static int CountPart(EHudPart Pt)
{
    int N = 0;
    for (int t = 0; t < List.NumTris; ++t) N += List.Tris[t].Part == Pt;
    return N;
}
static const FHudText* FindText(EHudText Slot, EHudGroup G = EHudGroup::Street, bool AnyGroup = true)
{
    for (int t = 0; t < List.NumTexts; ++t)
        if (List.Texts[t].Slot == Slot && (AnyGroup || List.Texts[t].Group == G)) return &List.Texts[t];
    return nullptr;
}
/** The worst case the HUD can be in: everything up, low health (danger),
    full rage pulsing, a long count at its punch, an enraged boss. */
static FHudState Worst(int Combo = 99, float Clock = 0.f)
{
    FHudState S;
    S.Health = 0.25f; S.Ghost = 0.5f; S.Stamina = 0.6f; S.Rage = 1.f; S.bRageReady = true;
    S.Combo = Combo; S.SinceCombo = 0.f;
    S.bBoss = true; S.BossHealth = 0.5f; S.BossGhost = 0.7f; S.bBossEnraged = true; S.BossSince = 1.f;
    S.Clock = Clock;
    return S;
}
/** Composited alpha, sampled every Step screen px: what share of the
    screen the HUD darkens, alpha-weighted (1 - the product of (1 - alpha)
    over every triangle a sample is in) -- of its backing shapes, and of
    everything it draws. */
static bool Backing(EHudPart Pt)
{
    return Pt == EHudPart::Panel || Pt == EHudPart::Head || Pt == EHudPart::Glow;
}
static void Coverage(const FPage& P, int Step, float& OutBacking, float& OutAll)
{
    double SumB = 0.0, SumA = 0.0;
    int N = 0;
    for (float Y = 0.5f * static_cast<float>(Step); Y < P.ScreenH; Y += static_cast<float>(Step))
        for (float X = 0.5f * static_cast<float>(Step); X < P.ScreenW; X += static_cast<float>(Step))
        {
            ++N;
            float ClearB = 1.f, ClearA = 1.f;
            for (int t = 0; t < List.NumTris; ++t)
            {
                const FHudTri& T = List.Tris[t];
                const FPoint& A = T.V[0].P; const FPoint& B = T.V[1].P; const FPoint& C = T.V[2].P;
                if (X < std::fmin(A.X, std::fmin(B.X, C.X)) || X > std::fmax(A.X, std::fmax(B.X, C.X))
                    || Y < std::fmin(A.Y, std::fmin(B.Y, C.Y)) || Y > std::fmax(A.Y, std::fmax(B.Y, C.Y)))
                    continue;
                const FPoint Pt = {X, Y};
                const float D = Cross(A, B, C);
                const float L0 = Cross(B, C, Pt) / D, L1 = Cross(C, A, Pt) / D, L2 = 1.f - L0 - L1;
                if (L0 < 0.f || L1 < 0.f || L2 < 0.f) continue;
                const float Alpha = L0 * T.V[0].C.A + L1 * T.V[1].C.A + L2 * T.V[2].C.A;
                ClearA *= 1.f - Alpha;
                if (Backing(T.Part)) ClearB *= 1.f - Alpha;
            }
            SumB += 1.0 - ClearB;
            SumA += 1.0 - ClearA;
        }
    OutBacking = static_cast<float>(SumB / N);
    OutAll = static_cast<float>(SumA / N);
}
static bool SameRgbLoose(const FRgba& A, const FRgba& B)
{
    return std::fabs(A.R - B.R) < 1e-4f && std::fabs(A.G - B.G) < 1e-4f && std::fabs(A.B - B.B) < 1e-4f;
}

static void Hud()
{
    std::printf("HUD  (what Build draws)\n");
    bool AllIn = true, TextIn = true, Apart = true, Clear = true, Legible = true, Stroked = true, Wound = true;
    bool Edged = true, NoNaN = true;
    int Worst99 = 0;
    for (const auto& Sh : Shapes)
    {
        const FPage P = FPage::For(Sh[0], Sh[1]);
        // every count the splat can carry, at its punch, with the drips at
        // every point of their cycle: nothing any of them draws leaves
        // title-safe (the street bars follow the men, as before)
        for (int Combo = 2; Combo <= 99; ++Combo)
        {
            Build(P, Worst(Combo, 0.05f * static_cast<float>(Combo % 28)), List);
            for (int t = 0; t < List.NumTris; ++t)
            {
                const FHudTri& T = List.Tris[t];
                for (const FHudVert& V : T.V)
                {
                    if (!(V.P.X == V.P.X) || !(V.P.Y == V.P.Y)) NoNaN = false;
                    if (T.Group != EHudGroup::Street && !InSafe(P, V.P.X, V.P.Y)) AllIn = false;
                }
                // inverted or degenerate (screen winding: every shape is
                // wound the same way round)
                if (!(Cross(T.V[0].P, T.V[1].P, T.V[2].P) > 1e-3f)) Wound = false;
            }
            for (int t = 0; t < List.NumTexts; ++t)
            {
                const FHudText& X = List.Texts[t];
                TextIn = TextIn && InSafe(P, X.At.X, X.At.Y) && InSafe(P, X.At.X, X.At.Y + X.Height);
                // on its own backing: its anchor inside its group's shapes
                const FBox B = GroupBox(X.Group);
                TextIn = TextIn && X.At.X >= B.X0 && X.At.X <= B.X1 && X.At.Y >= B.Y0 && X.At.Y + X.Height <= B.Y1 + 0.5f;
                Legible = Legible && X.Height >= MinTextShare * P.ScreenH - 0.01f;
                // every letter stroked in ink; a heading (cyan, or danger's
                // crimson) at least 4.5:1 against it, the rest 7:1
                Stroked = Stroked && X.Stroke >= 2.f * P.ScreenH / 720.f - 0.01f
                                  && Contrast(X.Colour, Colour::Ink) >= (X.Slot == EHudText::Title ? 4.5f : 7.f);
            }
            // the three groups apart, and nothing in the fight (the middle
            // 40 % across, 60 % down)
            const FBox Pl = GroupBox(EHudGroup::Player), Co = GroupBox(EHudGroup::Combo), Bo = GroupBox(EHudGroup::Boss);
            Apart = Apart && Pl.Any && Co.Any && Bo.Any && !Overlap(Pl, Co) && !Overlap(Pl, Bo) && !Overlap(Co, Bo);
            FBox Fight;
            Fight.X0 = 0.30f * P.ScreenW; Fight.X1 = 0.70f * P.ScreenW;
            Fight.Y0 = 0.20f * P.ScreenH; Fight.Y1 = 0.80f * P.ScreenH; Fight.Any = true;
            for (int t = 0; t < List.NumTris; ++t)
            {
                if (List.Tris[t].Group == EHudGroup::Street) continue;
                FBox T;
                for (const FHudVert& V : List.Tris[t].V) Add(T, V.P);
                if (Overlap(T, Fight)) Clear = false;
            }
            if (Combo == 99) Worst99 = List.NumTris;
        }
        // a count at rest draws smaller than at its punch: legible there too
        FHudState Rest = Worst(99);
        Rest.SinceCombo = 10.f;
        Build(P, Rest, List);
        for (int t = 0; t < List.NumTexts; ++t) Legible = Legible && List.Texts[t].Height >= MinTextShare * P.ScreenH - 0.01f;

        // every window: a solid edge at least 2 screen px at 720 lines, and
        // a glow fading out from it to nothing
        for (EHudGroup G : {EHudGroup::Player, EHudGroup::Combo, EHudGroup::Boss})
        {
            int Edges = 0, Glows = 0;
            bool Fades = true;
            for (int t = 0; t < List.NumTris; ++t)
            {
                const FHudTri& T = List.Tris[t];
                if (T.Group != G) continue;
                if (T.Part == EHudPart::Edge)
                {
                    ++Edges;
                    for (const FHudVert& V : T.V) Edged = Edged && V.C.A >= 0.999f;
                }
                if (T.Part == EHudPart::Glow)
                {
                    ++Glows;
                    float Lo = 1.f, Hi = 0.f;
                    for (const FHudVert& V : T.V) { Lo = std::fmin(Lo, V.C.A); Hi = std::fmax(Hi, V.C.A); }
                    Fades = Fades && Lo <= 1e-4f && Hi > 0.05f;
                }
            }
            Edged = Edged && Edges >= 12 && Glows >= 12 && Fades;
        }
        Edged = Edged && EdgePx * P.ScreenH / PageH >= 1.33f * P.ScreenH / 1080.f - 0.01f;
    }
    Check(NoNaN, "the HUD's shapes are numbers");
    Check(AllIn, "every vertex the HUD draws is inside the title-safe area, at every screen shape");
    Check(TextIn, "every text is inside title-safe, on its own backing");
    Check(Apart, "the player's corner, the combo and the boss's banner never overlap");
    Check(Clear, "nothing is drawn in the fight (the middle 40 % across, 60 % down)");
    Check(Legible, "no text the player reads is under 1/36 of the screen");
    Check(Stroked, "every text has an ink stroke of 2 screen px at 720 lines, 7:1 against its fill");
    Check(Wound, "no triangle is inverted or degenerate");
    Check(Edged, "every window has a solid edge and a glow fading out from it to nothing");

    // the ice corner marks: two at each window's uncut corners, standing
    // outside its panel
    {
        const FPage P = FPage::For(1920, 1080);
        Build(P, Worst(99, 0.5f), List);
        const FBox Br = PartBox(EHudPart::Bracket), Pn = PartBox(EHudPart::Panel);
        Check(CountPart(EHudPart::Bracket) == 3 * 8 && Br.Any && Pn.Any
              && Br.X0 < Pn.X0 && Br.X1 > Pn.X1 && Br.Y0 < Pn.Y0 && Br.Y1 > Pn.Y1,
              "every window carries its corner marks, outside its panel");
    }

    // how much of the screen it takes: the washes, the band and the splat,
    // alpha-weighted, at most 10.5 % of a 1080p screen (the dark fantasy's
    // plates and seal were 8.8 %)
    {
        const FPage P = FPage::For(1920, 1080);
        Build(P, Worst(99, 0.5f), List);
        float Back = 0.f, All = 0.f;
        Coverage(P, 3, Back, All);
        std::printf("  coverage at 1080p, alpha-weighted: %.1f %% the backing, %.1f %% everything\n",
                    100.f * Back, 100.f * All);
        Check(Back <= 0.105f, "the HUD's backing takes at most 10.5 % of the screen");
    }

    // every bar reads against its trough (WCAG 2.1 1.4.11, 3:1), and the
    // trail against the blood it drains to
    const float CHealth = Contrast(Colour::Danger, Colour::Trough), CStam = Contrast(Colour::System, Colour::Trough);
    const float CRage = Contrast(Colour::Shadow, Colour::Trough), CTrail = Contrast(Colour::Ice, Colour::Danger);
    std::printf("  contrast: health %.2f, stamina %.2f, rage %.2f against the trough; the trail %.2f against the health\n",
                CHealth, CStam, CRage, CTrail);
    Check(CHealth >= 3.f && CStam >= 3.f && CRage >= 3.f && CTrail >= 3.f,
          "every bar is 3:1 against its trough, and the trail against the health");

    // capacity: the worst case, twelve street bars on top, fits with room
    {
        const FPage P = FPage::For(3840, 2160);
        FHudState S = Worst(99, 0.5f);
        S.NumStreet = MaxStreetBars;
        for (int i = 0; i < MaxStreetBars; ++i) S.Street[i] = {400.f + 250.f * static_cast<float>(i), 900.f, 0.4f, 0.8f};
        Build(P, S, List);
        std::printf("  worst case: %d triangles (%d without the street bars), capacity %d\n",
                    List.NumTris, Worst99, MaxTris);
        Check(!List.bOverflow && List.NumTris * 4 <= MaxTris * 3, "the worst case fits the draw list with room to spare");
    }

    // danger: at 30 % health or under the player's window is edged in
    // danger's crimson, and pulses; above, in the System's cyan
    {
        const FPage P = FPage::For(1920, 1080);
        auto EdgeOf = [](EHudGroup G, FRgba& Out) {
            for (int t = 0; t < List.NumTris; ++t)
                if (List.Tris[t].Group == G && List.Tris[t].Part == EHudPart::Edge) { Out = List.Tris[t].V[0].C; return true; }
            return false;
        };
        auto GlowOf = [](EHudGroup G) {
            float A = 0.f;
            for (int t = 0; t < List.NumTris; ++t)
                if (List.Tris[t].Group == G && List.Tris[t].Part == EHudPart::Glow)
                    for (const FHudVert& V : List.Tris[t].V) A = std::fmax(A, V.C.A);
            return A;
        };
        bool Calm = true, Warns = true, Pulses = false;
        float Lo = 1e9f, Hi = 0.f;
        for (int k = 0; k < 40; ++k)
        {
            FHudState S = Worst(0, 0.05f * static_cast<float>(k));
            S.bBoss = false;
            FRgba E;
            S.Health = 0.31f;
            Build(P, S, List);
            Calm = Calm && EdgeOf(EHudGroup::Player, E) && SameRgbLoose(E, Colour::System);
            S.Health = 0.30f;
            Build(P, S, List);
            Warns = Warns && EdgeOf(EHudGroup::Player, E) && SameRgbLoose(E, Colour::Danger);
            const float G = GlowOf(EHudGroup::Player);
            Lo = std::fmin(Lo, G); Hi = std::fmax(Hi, G);
        }
        Pulses = Hi - Lo > 0.1f;
        Check(Calm && Warns, "at 30 % health or under the player's window is edged in danger; above, in the System's cyan");
        Check(Pulses, "...and its glow pulses");
    }

    // the boss's banner: it wipes open over 0.40 s and never closes, his
    // name and the slash cut in at 0.20 s, and the bar is clipped by it,
    // never squeezed into it: what shows of the bar is his true health
    {
        const FPage P = FPage::For(1920, 1080);
        const FLayout L = Lay(P);
        float Was = -1.f, At10 = 0.f, At40 = 0.f;
        bool Grows = true, Cut = true, Honest = true;
        for (int k = 0; k <= 50; ++k)
        {
            const float Tb = 0.01f * static_cast<float>(k);
            FHudState S = Worst(0, 0.f);
            S.BossSince = Tb;
            Build(P, S, List);
            FBox B;
            for (int t = 0; t < List.NumTris; ++t)
                if (List.Tris[t].Group == EHudGroup::Boss && List.Tris[t].Part == EHudPart::Panel)
                    for (const FHudVert& V : List.Tris[t].V) Add(B, V.P);
            const float Wd = B.Any ? B.X1 - L.Boss.X : 0.f;
            Grows = Grows && Wd >= Was - 1e-3f;
            Was = Wd;
            if (k == 10) At10 = Wd;
            if (k == 40) At40 = Wd;
            const FHudText* Heading = FindText(EHudText::Title, EHudGroup::Boss, false);
            const bool bShown = FindText(EHudText::BossName) && Heading;
            const bool bHidden = !FindText(EHudText::BossName) && !Heading;
            // (0.20 s written here, not read from the header)
            Cut = Cut && (Tb < 0.20f - 1e-4f ? bHidden : (Tb > 0.20f + 1e-4f ? bShown : true));
            // the fill ends where his health does, or where the band has
            // opened to, whichever is first
            const float S0 = 0.f, End = L.BossBar.X + L.BossBar.W * S.BossHealth;
            const float Want = std::fmin(End, L.Boss.X + Wd - P.Px(PadPx));
            float Drawn = -1.f;
            for (int t = 0; t < List.NumTris; ++t)
                if (List.Tris[t].Group == EHudGroup::Boss && List.Tris[t].Part == EHudPart::Fill)
                    for (const FHudVert& V : List.Tris[t].V) Drawn = std::fmax(Drawn, V.P.X);
            if (Drawn >= 0.f) Honest = Honest && std::fabs(Drawn - Want) <= 0.5f;
            else Honest = Honest && Want <= L.BossBar.X + S0 + 1.5f;
        }
        Check(Grows && At10 < 0.9f * L.Boss.W && At40 >= L.Boss.W - 0.5f,
              "the boss's WARNING window wipes open over 0.40 s and never closes");
        Check(Cut, "his name and its heading cut in at 0.20 s");
        Check(Honest, "the boss's bar is clipped as the window opens, never squeezed");
    }

    // A bar's quad: full width at 1, a line at 0, square like the System's.
    FPoint Q[4];
    const FRect R = {100, 50, 400, 40};
    BarQuad(R, 1.f, Q);
    Check(Near(Q[2].X, R.X + R.W) && Near(Q[1].X, Q[0].X), "a full bar reaches its end, square");
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
        const float Rg = static_cast<float>(k) / 50.f;
        float Sum = 0.f;
        for (int i = 0; i < RageBlocks; ++i)
        {
            Sum += RageBlock(Rg, i);
            if (i && RageBlock(Rg, i) > 0.f && RageBlock(Rg, i - 1) < 1.f) InOrder = false;
        }
        Sums = Sums && Near(Sum / RageBlocks, Rg, 1e-5f);
    }
    Check(Sums && InOrder, "the rage blocks are the rage, filled left to right");

    // The COMBO window: only from two hits, and the count between its
    // heading and HITS, at its punch too
    {
        const FPage P = FPage::For(1920, 1080);
        const FLayout L = Lay(P);
        FHudState S = Worst(1, 0.f);
        Build(P, S, List);
        bool Only = GroupBox(EHudGroup::Combo).Any == false;
        bool Between = true;
        for (float Since : {0.f, 0.05f, 1.f})
        {
            S = Worst(99, 0.f);
            S.SinceCombo = Since;
            Build(P, S, List);
            const FHudText* N = FindText(EHudText::Count);
            const FHudText* H = FindText(EHudText::Hits);
            Between = Between && N && H && N->At.Y >= L.Combo.Y + P.Px(HeadH) - 0.5f && N->At.Y + N->Height <= H->At.Y + 0.5f;
        }
        Check(Only && Between, "the COMBO window shows from two hits, its count between its heading and HITS");
    }
    Check(Near(ComboPunch(0.f), 1.35f) && ComboPunch(1.f) < 1.001f, "the count punches and settles");
}

static bool SameRgb(const FRgba& A, const FRgba& B)
{
    return Near(A.R, B.R, 1e-5f) && Near(A.G, B.G, 1e-5f) && Near(A.B, B.B, 1e-5f);
}

// The HUD draws the LIVE palette, the one the game fills from
// DT_LookColors.csv (2026-10-03): a colour set through PaletteSlot is the
// colour drawn, every one of the seven has a slot, and the defaults are
// what the palette starts as.
static void Palette()
{
    static FDrawList L;
    const FPage P = FPage::For(1920, 1080);
    const char* Names[] = {"Ink", "Bone", "Blood", "Ember", "Trough", "Ash", "Gold", "System", "Panel", "Shadow", "Danger", "Ice"};
    bool bSlots = true;
    for (const char* N : Names) bSlots = bSlots && PaletteSlot(N) != nullptr;
    Check(bSlots && PaletteSlot("Pink") == nullptr, "every palette colour has a slot by its data name, and nothing else does");
    Check(SameRgb(LivePalette().Blood, Defaults::Blood) && SameRgb(Colour::Bone, Defaults::Bone),
          "the palette starts as the defaults");
    const FRgba Saved = *PaletteSlot("Danger");
    const FRgba Green{0.0f, 0.4f, 0.1f, 1.f};
    *PaletteSlot("Danger") = Green;
    Build(P, Worst(99, 0.5f), L);
    bool bGreen = false, bOld = false;
    for (int t = 0; t < L.NumTris; ++t)
        for (const FHudVert& V : L.Tris[t].V)
        {
            bGreen = bGreen || SameRgb(V.C, Green);
            bOld = bOld || SameRgb(V.C, Defaults::Danger);
        }
    *PaletteSlot("Danger") = Saved;
    Check(bGreen && !bOld, "a danger set in the live palette is the danger the HUD draws");
    Check(SameRgb(Colour::Danger, Defaults::Danger), "and the palette put back is the default again");
    std::printf("  the live palette: 12 slots; a danger set through it drawn\n");
}

int main()
{
    Blows();
    State();
    Hud();
    Palette();
    if (Fails) { std::printf("%d anime check(s) failed\n", Fails); return 1; }
    std::printf("all anime checks passed\n");
    return 0;
}
