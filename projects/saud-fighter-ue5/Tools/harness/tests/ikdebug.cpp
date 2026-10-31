/**
 * The in-game IK, drawn, executed (SaudIKDebug.h, 2026-10-31).
 *
 * That nothing is drawn for a view with nothing on; that a trace is drawn
 * blue where it hit, with its point and the ground's normal, and red with
 * nothing else where it missed; that a held foot is green with its anchor at
 * the ball's height and a free one yellow with none; that the strike's mark
 * shows only while it is on, no smaller than its skin, and thicker as it
 * comes on; that the block and the look show only while on; that every size
 * grows with the man; that the colours tell the states apart; and that
 * everything at once fits the list, which refuses more than it holds.
 *
 * Every check here has a sabotage in Tools/harness/bites.txt.
 */
#include "../HarnessTypes.h"
#include "../../../Source/SaudFighter/Combat/SaudIKDebug.h"

#include <cmath>
#include <cstdio>
#include <cstdlib>

static int Fails = 0;
static void Check(bool Ok, const char* What)
{
    if (!Ok) { ++Fails; std::printf("  FAIL  %s\n", What); }
}
static bool Near(double A, double B, double Eps) { return std::fabs(A - B) <= Eps; }
static bool Same(const FVector& A, const FVector& B) { return FVector::Dist(A, B) < 1e-3; }

using namespace SaudIKDebug;

static int Count(const FList& L, EColour C, EShape S)
{
    int N = 0;
    for (int I = 0; I < L.Num; ++I) N += L.Prim[I].Colour == C && L.Prim[I].Shape == S;
    return N;
}
static const FPrim* First(const FList& L, EColour C, EShape S)
{
    for (int I = 0; I < L.Num; ++I) if (L.Prim[I].Colour == C && L.Prim[I].Shape == S) return &L.Prim[I];
    return nullptr;
}

static FTraceView Traced(bool bHit, const FVector& At)
{
    FTraceView T;
    T.bTraced = true;
    T.bHit = bHit;
    T.From = At + FVector(0, 0, 60);
    T.To = At - FVector(0, 0, 70);
    T.Point = At;
    T.Normal = FVector(0, 0.2, 1).GetSafeNormal();
    return T;
}

static FView Everything()
{
    FView V;
    for (int S = 0; S < 2; ++S)
    {
        for (int K = 0; K < 2; ++K) V.Trace[S][K] = Traced(true, FVector(S * 20.0, K * 15.0, 0));
        V.Foot[S].bDrawn = true;
        V.Foot[S].Heel = FVector(S * 20.0, 0, 9);
        V.Foot[S].Ball = FVector(S * 20.0, 15, 3);
        V.Foot[S].bHeld = true;
        V.Foot[S].Anchor = FVector(S * 20.0, 15, -500);
    }
    V.bStrike = true; V.StrikeMark = FVector(80, 0, 150); V.StrikeLow = FVector(80, 0, 100); V.StrikeSkin = 2.f; V.StrikeAlpha = 1.f;
    V.bBlock = true; V.BlockMeet = FVector(30, 0, 150); V.BlockAlpha = 1.f;
    V.bLook = true; V.LookFrom = FVector(0, 0, 160); V.LookTo = FVector(200, 0, 165);
    return V;
}

int main()
{
    std::printf("THE IK, DRAWN  (Combat/SaudIKDebug.h)\n");
    FList L;

    // nothing on, nothing drawn
    Build(FView(), L);
    Check(L.Num == 0, "nothing is drawn for a view with nothing on");

    // a trace that hit: blue, its point, the ground's normal
    {
        FView V;
        V.Trace[0][1] = Traced(true, FVector(10, 5, 2));
        Build(V, L);
        const FPrim* Tr = First(L, EColour::Hit, EShape::Line);
        const FPrim* Pt = First(L, EColour::Hit, EShape::Sphere);
        const FPrim* Nm = First(L, EColour::Normal, EShape::Line);
        Check(Tr && Same(Tr->A, V.Trace[0][1].From) && Same(Tr->B, V.Trace[0][1].To) && Count(L, EColour::Missed, EShape::Line) == 0,
              "a trace that hit is drawn blue, from where it started to where it ended");
        Check(Pt && Same(Pt->A, FVector(10, 5, 2)) && Near(Pt->Radius, PointCm, 1e-4), "a trace that hit shows its hit point");
        Check(Nm && Same(Nm->A, FVector(10, 5, 2)) && Near(FVector::Dist(Nm->A, Nm->B), NormalCm, 1e-3)
              && FVector::DotProduct((Nm->B - Nm->A).GetSafeNormal(), V.Trace[0][1].Normal) > 0.999,
              "a trace that hit shows the ground's normal, NormalCm long, along it");
    }

    // a trace that missed: red, and nothing else
    {
        FView V;
        V.Trace[1][0] = Traced(false, FVector(-10, 0, 0));
        Build(V, L);
        Check(L.Num == 1 && L.Prim[0].Colour == EColour::Missed && L.Prim[0].Shape == EShape::Line,
              "a trace that missed is drawn red, with no point and no normal");
    }

    // a held foot: green, its anchor at the ball's height
    {
        FView V;
        V.Foot[0].bDrawn = true;
        V.Foot[0].Heel = FVector(0, 0, 9);
        V.Foot[0].Ball = FVector(0, 15, 3);
        V.Foot[0].bHeld = true;
        V.Foot[0].Anchor = FVector(1, 16, -500);   // the IK keeps no Z
        Build(V, L);
        const FPrim* Ft = First(L, EColour::Held, EShape::Line);
        const FPrim* An = First(L, EColour::Held, EShape::Sphere);
        Check(Ft && Same(Ft->A, V.Foot[0].Heel) && Same(Ft->B, V.Foot[0].Ball) && Count(L, EColour::Free, EShape::Line) == 0,
              "a held foot is drawn green, heel to ball");
        Check(An && Same(An->A, FVector(1, 16, 3)), "a held foot's anchor is drawn where it is held, at the ball's height");
    }

    // a free foot: yellow, no anchor
    {
        FView V;
        V.Foot[1].bDrawn = true;
        V.Foot[1].Heel = FVector(0, 0, 30);
        V.Foot[1].Ball = FVector(0, 15, 25);
        Build(V, L);
        Check(Count(L, EColour::Free, EShape::Line) == 1 && Count(L, EColour::Held, EShape::Sphere) == 0 && L.Num == 1,
              "a free foot is drawn yellow, with no anchor");
    }

    // the strike: only while on, no smaller than its skin, thicker as it comes on
    {
        FView V = FView();
        V.bStrike = true; V.StrikeMark = FVector(80, 0, 150); V.StrikeLow = FVector(80, 0, 100); V.StrikeSkin = 5.f; V.StrikeAlpha = 0.f;
        Build(V, L);
        Check(L.Num == 0, "the strike's mark is not drawn while its share is nothing");
        V.StrikeAlpha = 0.25f;
        Build(V, L);
        const FPrim* M = First(L, EColour::Strike, EShape::Sphere);
        const float ThinAt = M ? M->Thickness : 0.f;
        Check(M && Same(M->A, V.StrikeMark) && Near(M->Radius, 5.f, 1e-4), "the strike's mark is drawn on the mark, as big as its skin");
        Check(First(L, EColour::Strike, EShape::Line) && Same(First(L, EColour::Strike, EShape::Line)->B, V.StrikeLow),
              "the strike's mark shows the line down to his belt");
        V.StrikeAlpha = 1.f;
        Build(V, L);
        M = First(L, EColour::Strike, EShape::Sphere);
        Check(M && M->Thickness > ThinAt + 0.5f, "the strike's mark is drawn thicker as its share comes on");
        V.StrikeSkin = 0.5f;
        Build(V, L);
        M = First(L, EColour::Strike, EShape::Sphere);
        Check(M && Near(M->Radius, MarkMinCm, 1e-4), "the strike's mark is never drawn smaller than MarkMinCm");
    }

    // the block and the look: only while on
    {
        FView V;
        V.bBlock = true; V.BlockMeet = FVector(30, 0, 150); V.BlockAlpha = 0.f;
        V.bLook = false; V.LookFrom = FVector(0, 0, 160); V.LookTo = FVector(200, 0, 165);
        Build(V, L);
        Check(L.Num == 0, "the block and the look are not drawn while off");
        V.BlockAlpha = 0.6f; V.bLook = true;
        Build(V, L);
        const FPrim* B = First(L, EColour::Block, EShape::Sphere);
        const FPrim* K = First(L, EColour::Look, EShape::Line);
        Check(B && Same(B->A, V.BlockMeet), "where a block meets the blow is drawn while it is on");
        Check(K && Same(K->A, V.LookFrom) && Same(K->B, V.LookTo), "the look is drawn from his head to the head he is turned to");
    }

    // every size grows with the man
    {
        FView V;
        V.Size = 1.5f;
        V.Trace[0][0] = Traced(true, FVector(0, 0, 0));
        V.Foot[0].bDrawn = true; V.Foot[0].bHeld = true; V.Foot[0].Ball = FVector(0, 15, 3);
        V.bStrike = true; V.StrikeAlpha = 1.f; V.StrikeSkin = 0.f;
        V.bBlock = true; V.BlockAlpha = 1.f;
        Build(V, L);
        const FPrim* Nm = First(L, EColour::Normal, EShape::Line);
        const FPrim* Pt = First(L, EColour::Hit, EShape::Sphere);
        const FPrim* An = First(L, EColour::Held, EShape::Sphere);
        const FPrim* Mk = First(L, EColour::Strike, EShape::Sphere);
        const FPrim* Bk = First(L, EColour::Block, EShape::Sphere);
        Check(Nm && Pt && An && Mk && Bk
              && Near(FVector::Dist(Nm->A, Nm->B), NormalCm * 1.5, 1e-3) && Near(Pt->Radius, PointCm * 1.5, 1e-4)
              && Near(An->Radius, AnchorCm * 1.5, 1e-4) && Near(Mk->Radius, MarkMinCm * 1.5, 1e-4) && Near(Bk->Radius, MeetCm * 1.5, 1e-4),
              "every size grows with the man");
    }

    // the colours tell the states apart
    {
        const EColour All[] = { EColour::Held, EColour::Free, EColour::Hit, EColour::Missed, EColour::Normal, EColour::Strike, EColour::Block, EColour::Look };
        bool Apart = true;
        for (EColour A : All)
            for (EColour B : All)
            {
                if (A == B) continue;
                const FRgb X = Rgb(A), Y = Rgb(B);
                const int D = std::abs(X.R - Y.R) + std::abs(X.G - Y.G) + std::abs(X.B - Y.B);
                Apart = Apart && D >= 90;
            }
        Check(Apart, "every colour is far from every other, so the states are told apart");
    }

    // everything at once fits; the list refuses more than it holds
    {
        Build(Everything(), L);
        Check(L.Num == 20, "everything at once is twenty pieces");
        Check(L.Num <= MaxPrims && MaxPrims >= 20, "everything at once fits the list");
        FList Full;
        int Added = 0;
        for (int I = 0; I < MaxPrims + 5; ++I) Added += Full.Add(FPrim()) ? 1 : 0;
        Check(Added == MaxPrims && Full.Num == MaxPrims, "the list refuses more than it holds");
        Build(FView(), L);
        Check(L.Num == 0, "a fresh build clears what the last one drew");
    }

    if (Fails) { std::printf("%d ik-debug check(s) failed\n", Fails); return 1; }
    std::printf("all ik-debug checks passed\n");
    return 0;
}
