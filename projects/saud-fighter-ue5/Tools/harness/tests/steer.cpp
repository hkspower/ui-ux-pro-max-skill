/**
 * Which way a fighter faces while he moves, executed (SaudSteer.h): the
 * eight ways against his facing, the free/fight test and its band, the turn
 * on the spot and which way it goes, the pivot at a run, and the facing's
 * chase of his heading -- never past it, always arriving, the same at 30
 * and 60 frames a second.
 */
#include "../HarnessTypes.h"
#include "../../../Source/SaudFighter/Combat/SaudSteer.h"
#include "../../../Source/SaudFighter/Combat/SaudFeel.h"

#include <cstdio>
#include <cmath>

static int Fails = 0;
static void Check(bool Ok, const char* What)
{
    if (!Ok) { ++Fails; std::printf("  FAIL  %s\n", What); }
}
static bool Near(float A, float B, float Eps = 1e-3f) { return std::fabs(A - B) <= Eps; }

namespace S = SaudSteer;

static const float Run = 341.f;    // Saud's full speed, Player.json BaseMoveSpeed

static void Names()
{
    std::printf("THE NAMES\n");
    Check(Near(S::TurnSeconds(S::ETurn::L90), 0.50f) && Near(S::TurnSeconds(S::ETurn::R90), 0.50f)
          && Near(S::TurnSeconds(S::ETurn::Back180), 0.70f) && Near(S::TurnSeconds(S::ETurn::Pivot180), 0.45f)
          && S::TurnSeconds(S::ETurn::None) == 0.f,
          "the turn clips' lengths are 0.50 0.50 0.70 0.45 s");
    Check(S::FreeBeyondCm == 1200.f && S::FreeBandCm == 100.f, "free beyond 1200 cm, a 100 cm band");
    Check(S::WalkShare == 0.45f, "the walk tier at 0.45 of his speed");
    Check(S::StandingCm == SaudFeel::WalkThreshold, "standing is the Guard's speed (SaudFeel::WalkThreshold)");
    Check(SaudFeel::FreeBeyondCm == S::FreeBeyondCm, "SaudFeel::FreeBeyondCm is SaudSteer's");
    Check(S::Fwd == 0 && S::FwdLeft == 1 && S::Left == 2 && S::BackLeft == 3 && S::Back == 4
          && S::BackRight == 5 && S::Right == 6 && S::FwdRight == 7 && S::NumDirs == 8,
          "the eight ways in the clips' order");
}

static void Octants()
{
    std::printf("THE EIGHT WAYS\n");
    bool bCentre = true, bHeld = true, bInside = true, bPast = true, bLeft = true, bLine = true, bAny = true, bZero = true;
    for (int F = 0; F < 72; ++F)
    {
        const float Yaw = F * 5.f;
        const FVector Facing = S::DirOf(Yaw);
        for (int D = 0; D < 8; ++D)
        {
            const float C = D * 45.f;
            // the centre, from nothing and from every octant showing
            if (S::Octant(Facing, S::DirOf(Yaw + C), -1) != D) bCentre = false;
            for (int Cur = 0; Cur < 8; ++Cur)
            {
                if (S::Octant(Facing, S::DirOf(Yaw + C), Cur) != D && Cur != D) bAny = false;
            }
            // a heading a length of 3 or 0.2 is a heading
            if (S::Octant(Facing * 3.0, S::DirOf(Yaw + C) * 0.2, -1) != D) bCentre = false;
            for (int Sign = -1; Sign <= 1; Sign += 2)
            {
                const int Next = (D + Sign + 8) % 8;
                // inside the wedge: this octant, from nothing
                if (S::Octant(Facing, S::DirOf(Yaw + C + Sign * 20.f), -1) != D) bInside = false;
                // past the line by 3 degrees: the neighbour from nothing, held from this one
                if (S::Octant(Facing, S::DirOf(Yaw + C + Sign * 25.5f), -1) != Next) bLine = false;
                if (S::Octant(Facing, S::DirOf(Yaw + C + Sign * 25.5f), D) != D) bHeld = false;
                // past the line by more than 5: the neighbour, held or not
                if (S::Octant(Facing, S::DirOf(Yaw + C + Sign * 28.f), D) != Next) bPast = false;
            }
        }
        // + = his left: a heading 90 degrees toward +yaw is Left, -90 Right
        if (S::Octant(Facing, S::DirOf(Yaw + 90.f), -1) != S::Left
            || S::Octant(Facing, S::DirOf(Yaw - 90.f), -1) != S::Right
            || S::Octant(Facing, S::DirOf(Yaw + 135.f), -1) != S::BackLeft
            || S::Octant(Facing, S::DirOf(Yaw - 45.f), -1) != S::FwdRight) bLeft = false;
        // no heading: what showed, or forward
        if (S::Octant(Facing, FVector(0.0, 0.0, 0.0), 5) != 5 || S::Octant(Facing, FVector(0.0, 0.0, 0.0), -1) != 0) bZero = false;
    }
    Check(bCentre, "each octant's centre is that octant, at 72 facings x 8 headings");
    Check(bAny, "an octant's centre is that octant whichever showed");
    Check(bInside, "inside a wedge, that octant");
    Check(bLeft, "+ is his left: Left at +90, Right at -90, BackLeft at +135, FwdRight at -45");
    Check(bLine, "3 degrees past a line is the neighbour, from nothing");
    Check(bHeld, "an octant is held 5 degrees past its line");
    Check(bPast, "past the hold, the neighbour");
    Check(bZero, "no heading keeps what showed, or Fwd");
    // the line itself goes to the octant nearer Fwd (from +X; exact angles)
    const FVector X(1.0, 0.0, 0.0);
    const double R = std::sqrt(2.0 - std::sqrt(2.0)) / 2.0, Q = std::sqrt(2.0 + std::sqrt(2.0)) / 2.0;  // sin, cos 22.5
    Check(S::Octant(X, FVector(Q, R, 0.0), -1) == S::Fwd && S::Octant(X, FVector(Q, -R, 0.0), -1) == S::Fwd
          && S::Octant(X, FVector(-Q, R, 0.0), -1) == S::BackLeft && S::Octant(X, FVector(-Q, -R, 0.0), -1) == S::BackRight,
          "a line goes to the octant nearer Fwd");
    // a heading wandering 3 degrees either side of a line flicks nothing
    int Changes = 0, Cur = -1, Last = -1;
    for (int I = 0; I < 200; ++I)
    {
        Cur = S::Octant(X, S::DirOf(67.5f + 3.f * std::sin(I * 0.7f)), Cur);
        if (Last >= 0 && Cur != Last) ++Changes;
        Last = Cur;
    }
    Check(Changes == 0, "a heading held on a line does not flick two clips");
}

static void FreeTest()
{
    std::printf("FREE OR FIGHTING\n");
    Check(!S::FreeHeld(1200.f, false) && S::FreeHeld(1200.5f, false), "free once no one is within 1200 cm");
    Check(S::FreeHeld(1100.f, true) && !S::FreeHeld(1099.5f, true), "fighting again inside 1100 cm");
    Check(S::FreeHeld(1e9f, false), "no one at all: free");
    bool bBand = true;
    for (float D = 1100.f; D <= 1200.f; D += 5.f)
    {
        if (S::FreeHeld(D, true) != true || S::FreeHeld(D, false) != false) bBand = false;
    }
    Check(bBand, "the free test holds through its band");
    // a man walking out to 20 m and back: one change each way, at the lines
    bool bFree = false; int Out = 0, In = 0; float OutAt = 0.f, InAt = 0.f;
    for (int I = 0; I <= 4000; ++I)
    {
        const float D = I <= 2000 ? static_cast<float>(I) : static_cast<float>(4000 - I);
        const bool Now = S::FreeHeld(D, bFree);
        if (Now && !bFree) { ++Out; OutAt = D; }
        if (!Now && bFree) { ++In; InAt = D; }
        bFree = Now;
    }
    Check(Out == 1 && In == 1 && Near(OutAt, 1201.f) && Near(InAt, 1099.f), "out past 1200, back in at 1100, once each");
    // a man standing on the line, shifting 40 cm either way: at most one change
    int Flips = 0; bFree = false;
    for (int I = 0; I < 600; ++I)
    {
        const bool Now = S::FreeHeld(1200.f + 40.f * std::sin(I * 0.3f), bFree);
        if (Now != bFree) ++Flips;
        bFree = Now;
    }
    Check(Flips == 1, "a man shifting on the line flips him once, not every step");
}

static void Rates()
{
    std::printf("THE TURN RATE\n");
    Check(Near(S::FreeTurnRate(0.f, Run), 540.f) && Near(S::FreeTurnRate(S::WalkShare * Run, Run), 540.f),
          "540 deg/s walking");
    Check(Near(S::FreeTurnRate(Run, Run), 360.f) && Near(S::FreeTurnRate(2.f * Run, Run), 360.f),
          "a runner turns slower: 360 deg/s at his full speed");
    bool bMono = true; float Prev = 1e9f;
    for (float V = 0.f; V <= 1.2f * Run; V += 5.f)
    {
        const float R = S::FreeTurnRate(V, Run);
        if (R > Prev + 1e-3f || R < 360.f - 1e-3f || R > 540.f + 1e-3f) bMono = false;
        Prev = R;
    }
    Check(bMono, "the rate falls with speed, inside 360..540");
    Check(Near(S::FreeTurnRate(100.f, 0.f), 540.f), "no run speed: the walking rate");
}

static void Spot()
{
    std::printf("THE TURN ON THE SPOT\n");
    // every 5 degrees, at every facing: none to 45, a quarter turn to that
    // side to 135, Turn_180 past it
    bool bChoice = true, bLeftL = true, bRightR = true, bNone = true, bBack = true, bSnap = true, bSerial = true;
    for (int F = 0; F < 72; ++F)
    {
        const float Yaw = F * 5.f - 180.f;
        for (int E = -36; E <= 36; ++E)
        {
            const float Err = E * 5.f;
            const S::ETurn T = S::TurnOnSpot(Err);
            const float A = std::fabs(Err);
            S::ETurn Want = S::ETurn::None;
            if (A > 135.f) Want = S::ETurn::Back180;
            else if (A > 45.f) Want = Err > 0.f ? S::ETurn::L90 : S::ETurn::R90;
            if (T != Want) bChoice = false;
            if (Err > 45.f && Err <= 135.f && T != S::ETurn::L90) bLeftL = false;
            if (Err < -45.f && Err >= -135.f && T != S::ETurn::R90) bRightR = false;
            if (A <= 45.f && T != S::ETurn::None) bNone = false;
            if (A > 135.f && T != S::ETurn::Back180) bBack = false;
            // through a whole frame: standing, pushed (a hundredth of a
            // degree inside each line, so the trig's rounding is not judged)
            const float Off = Err > 0.f ? Err - 0.01f : (Err < 0.f ? Err + 0.01f : 0.f);
            S::FTurnState St;
            St.Serial = 7;
            S::FFreeIn In; In.Dt = 1.f / 60.f; In.FacingYaw = Yaw; In.Wish = S::DirOf(Yaw + Off) * 0.8;
            In.bPushed = true; In.Speed = 0.f; In.RunSpeed = Run;
            const S::FFreeOut O = S::StepFree(St, In);
            if (St.Turn != Want) bChoice = false;
            if (Want != S::ETurn::None)
            {
                if (!O.bStarted || O.MoveShare != 0.f || !Near(S::Wrap180(O.FacingYaw - (Yaw + Off)), 0.f, 1e-2f)) bSnap = false;
                if (St.Serial != 8 || !Near(St.Left, S::TurnSeconds(Want))) bSerial = false;
            }
            else if (O.bStarted || O.MoveShare != 1.f || St.Serial != 7) bSnap = false;
        }
    }
    Check(bChoice, "the turn chosen at every 5 degrees, at every facing");
    Check(bLeftL, "a quarter turn to his left is Turn_L90");
    Check(bRightR, "a quarter turn to his right is Turn_R90");
    Check(bNone, "no turn on the spot within 45 degrees");
    Check(bBack, "past 135 degrees it is Turn_180");
    Check(bSnap, "the facing snaps to the wish as a turn starts, his movement held");
    Check(bSerial, "every new turn moves the serial and sets its time");

    // walking (over the standing speed) the same wish is a chase, not a turn
    {
        S::FTurnState St;
        S::FFreeIn In; In.Dt = 1.f / 60.f; In.FacingYaw = 0.f; In.Wish = S::DirOf(90.f); In.bPushed = true;
        In.Speed = 60.f; In.RunSpeed = Run;
        const S::FFreeOut O = S::StepFree(St, In);
        Check(St.Turn == S::ETurn::None && O.MoveShare == 1.f && Near(O.FacingYaw, 9.f, 1e-2f),
              "standing, a turn on the spot; walking, a chase at 540 deg/s");
        S::FTurnState St2; In.bPushed = false; In.Speed = 0.f;
        const S::FFreeOut O2 = S::StepFree(St2, In);
        Check(St2.Turn == S::ETurn::None && O2.FacingYaw == 0.f, "a stick not pushed turns nothing");
    }

    // the hold: movement held for exactly the clip's length, at 30 and 60 Hz
    const S::ETurn Kinds[3] = {S::ETurn::L90, S::ETurn::R90, S::ETurn::Back180};
    const float Errs[3] = {90.f, -90.f, 180.f};
    bool bHold = true, bNoTurn = true;
    for (int K = 0; K < 3; ++K)
    {
        for (int Hz = 30; Hz <= 60; Hz += 30)
        {
            const float Dt = 1.f / Hz;
            S::FTurnState St;
            float Yaw = 10.f, Held = 0.f;
            bool bMoved = false;
            for (int I = 0; I < Hz * 2 && !bMoved; ++I)
            {
                S::TickTurn(St, Dt);
                S::FFreeIn In; In.Dt = Dt; In.FacingYaw = Yaw; In.Wish = S::DirOf(10.f + Errs[K]); In.bPushed = true;
                In.Speed = 0.f; In.RunSpeed = Run;
                const S::FFreeOut O = S::StepFree(St, In);
                if (I == 0 && St.Turn != Kinds[K]) bHold = false;
                Yaw = O.FacingYaw;
                if (O.MoveShare == 0.f) Held += Dt; else bMoved = true;
                if (I > 0 && O.bStarted) bNoTurn = false;
            }
            // at least its length, and less than a frame over (a frame is the clock's grain)
            if (!bMoved || Held < S::TurnSeconds(Kinds[K]) - 1e-4f || Held >= S::TurnSeconds(Kinds[K]) + Dt - 1e-4f) bHold = false;
        }
    }
    Check(bHold, "a turn holds his movement for its own length, at 30 and 60 Hz");
    Check(bNoTurn, "facing the wish after the turn, no second turn");
    // a turn interrupted: nothing held after
    {
        S::FTurnState St;
        S::FFreeIn In; In.Dt = 1.f / 60.f; In.FacingYaw = 0.f; In.Wish = S::DirOf(180.f); In.bPushed = true; In.RunSpeed = Run;
        S::StepFree(St, In);
        S::CancelTurn(St);
        In.FacingYaw = 180.f;
        const S::FFreeOut O = S::StepFree(St, In);
        Check(St.Turn == S::ETurn::None && O.MoveShare == 1.f, "a strike, a blow or a dash ends the turn");
    }
}

static void Pivot()
{
    std::printf("THE PIVOT\n");
    bool bOnly = true, bFast = true;
    for (int E = -36; E <= 36; ++E)
    {
        const float Err = E * 5.f;
        for (float Share = 0.f; Share <= 1.21f; Share += 0.05f)
        {
            const float V = Share * Run;
            const bool P = S::Pivots(Err, V, Run);
            const bool Want = std::fabs(Err) > 135.f && V > 0.6f * Run;
            if (P != Want) bOnly = false;
            if (std::fabs(Err) > 135.f && Share >= 0.65f && !P) bFast = false;
        }
    }
    Check(bOnly, "a pivot only at speed, only for a reversal past 135");
    Check(bFast, "a reversal at a run is a pivot");
    // through a frame: snapped, held for 0.45 s, then off again
    for (int Hz = 30; Hz <= 60; Hz += 30)
    {
        const float Dt = 1.f / Hz;
        S::FTurnState St;
        S::FFreeIn In; In.Dt = Dt; In.FacingYaw = 30.f; In.Wish = S::DirOf(30.f + 175.f); In.bPushed = true;
        In.Speed = Run; In.RunSpeed = Run;
        const S::FFreeOut O = S::StepFree(St, In);
        Check(St.Turn == S::ETurn::Pivot180 && O.bStarted && O.MoveShare == 0.f && Near(O.FacingYaw, -155.f, 1e-2f),
              "a reversal at a run: Pivot_180, the facing snapped, his speed held");
        // his speed, under UE's braking (4000 cm/s/s) with nothing asked, through the pivot
        float Speed = Run, Held = 0.f, Max = 0.f;
        bool bOff = false;
        for (int I = 1; I < Hz && !bOff; ++I)
        {
            S::TickTurn(St, Dt);
            In.FacingYaw = O.FacingYaw; In.Speed = Speed;
            const S::FFreeOut P = S::StepFree(St, In);
            if (P.MoveShare == 0.f) { Held += Dt; Speed = std::fmax(0.f, Speed - 4000.f * Dt); if (Held > 0.15f) Max = std::fmax(Max, Speed); }
            else bOff = true;
        }
        Check(bOff && Held + Dt >= 0.45f - 1e-4f && Held + Dt < 0.45f + Dt - 1e-4f, "the pivot holds 0.45 s, then he is off");
        Check(Max <= 1.f, "his speed is held near zero through the pivot");
    }
    // a reversal at a walk is a chase at the walking rate, never a pivot
    S::FTurnState St;
    S::FFreeIn In; In.Dt = 1.f / 60.f; In.FacingYaw = 0.f; In.Wish = S::DirOf(170.f); In.bPushed = true;
    In.Speed = 0.5f * Run; In.RunSpeed = Run;
    const S::FFreeOut O = S::StepFree(St, In);
    Check(St.Turn == S::ETurn::None && O.MoveShare == 1.f && O.FacingYaw > 0.f, "at a walk a reversal is a chase");
}

static void Chase()
{
    std::printf("THE CHASE\n");
    // StepYaw: never past, never further, the short way, arriving
    bool bOver = true, bShort = true, bArrive = true, bCap = true;
    for (int A = 0; A < 72; ++A)
    {
        for (int B = 0; B < 72; ++B)
        {
            const float From = A * 5.f - 180.f + 0.3f, To = B * 5.f - 180.f;
            for (float Step = 1.f; Step <= 40.f; Step *= 2.f)
            {
                const float Gap0 = S::Wrap180(To - From);
                const float Y = S::StepYaw(From, To, Step);
                const float Gap1 = S::Wrap180(To - Y);
                const float Moved = S::Wrap180(Y - From);
                if (std::fabs(Gap1) > std::fabs(Gap0) + 1e-3f) bShort = false;
                if (Gap0 * Gap1 < -1e-6f) bOver = false;                         // crossed the wanted yaw
                if (std::fabs(Moved) > Step + 1e-3f) bCap = false;
                if (std::fabs(Gap0) > 1e-3f && Moved * Gap0 < 0.f) bShort = false;  // the long way round
                float Yaw = From; int N = 0;
                while (std::fabs(S::Wrap180(To - Yaw)) > 1e-3f && N < 400) { Yaw = S::StepYaw(Yaw, To, Step); ++N; }
                if (N > static_cast<int>(std::ceil(std::fabs(Gap0) / Step)) + 1) bArrive = false;
            }
        }
    }
    Check(bOver, "the facing never overshoots");
    Check(bShort, "the short way round, never further");
    Check(bCap, "no more than the rate allows in a frame");
    Check(bArrive, "the facing arrives, in the steps the rate needs");
    Check(Near(S::Wrap180(-180.f), 180.f) && Near(S::Wrap180(540.f), 180.f) && Near(S::Wrap180(-541.f), 179.f)
          && Near(S::Wrap180(-179.f), -179.f), "an angle wraps into (-180, 180]");
    Check(Near(S::StepYaw(170.f, -170.f, 5.f), 175.f) && Near(S::StepYaw(-175.f, 175.f, 20.f), 175.f),
          "across 180 the short way round");

    // the same turn at 30 and 60 Hz: walking at a constant pace, running,
    // and speeding up through it -- the facing at every 30th of a second
    // within a degree, and both arriving
    struct FCase { float V0, V1, Err; };
    const FCase Cases[3] = {{0.45f * Run, 0.45f * Run, 120.f}, {Run, Run, -130.f}, {60.f, Run, 125.f}};
    bool bSame = true, bThere = true;
    for (const FCase& C : Cases)
    {
        float Y30 = 0.f, Y60 = 0.f, Worst = 0.f;
        S::FTurnState T30, T60;
        for (int I = 0; I < 60; ++I)          // two seconds
        {
            for (int Sub = 0; Sub < 2; ++Sub)
            {
                const float T = (I * 2 + Sub) / 60.f;
                S::FFreeIn In; In.Dt = 1.f / 60.f; In.FacingYaw = Y60; In.Wish = S::DirOf(C.Err); In.bPushed = true;
                In.Speed = C.V0 + (C.V1 - C.V0) * std::fmin(1.f, T / 0.5f); In.RunSpeed = Run;
                Y60 = S::StepFree(T60, In).FacingYaw;
            }
            S::FFreeIn In; In.Dt = 1.f / 30.f; In.FacingYaw = Y30; In.Wish = S::DirOf(C.Err); In.bPushed = true;
            In.Speed = C.V0 + (C.V1 - C.V0) * std::fmin(1.f, I / 30.f / 0.5f); In.RunSpeed = Run;
            Y30 = S::StepFree(T30, In).FacingYaw;
            Worst = std::fmax(Worst, std::fabs(S::Wrap180(Y30 - Y60)));
            if (T30.Turn != S::ETurn::None || T60.Turn != S::ETurn::None) bSame = false;
        }
        if (Worst > 1.f) bSame = false;
        if (!Near(Y30, C.Err, 1e-2f) || !Near(Y60, C.Err, 1e-2f)) bThere = false;
    }
    Check(bSame, "the same turn at 30 and 60 Hz, within a degree");
    Check(bThere, "the chase arrives at his heading");
    // how long: a 120-degree change at a walk takes 120/540 s, at a run 120/360
    {
        float Yaw = 0.f; int N = 0; S::FTurnState St;
        while (std::fabs(S::Wrap180(120.f - Yaw)) > 1e-3f && N < 600)
        {
            S::FFreeIn In; In.Dt = 1.f / 60.f; In.FacingYaw = Yaw; In.Wish = S::DirOf(120.f); In.bPushed = true;
            In.Speed = Run; In.RunSpeed = Run;
            Yaw = S::StepFree(St, In).FacingYaw; ++N;
        }
        Check(N == 20, "at a run a 120 degree change takes a third of a second");
    }
}

int main()
{
    Names();
    Octants();
    FreeTest();
    Rates();
    Spot();
    Pivot();
    Chase();
    if (Fails) { std::printf("%d FAILED\n", Fails); return 1; }
    std::printf("all steer checks passed\n");
    return 0;
}
