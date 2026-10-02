/**
 * The runtime IK's arithmetic, executed.
 *
 * SaudIK.h decides where a limb goes over the clips: the two-bone solve, a
 * foot held where it landed and stood on the ground, the hips' drop and
 * carry, the striking point put on the victim's mark, a guard meeting the
 * blow, the body turned after a snapped facing and toward the man that
 * matters, and one clip giving way to the next. This checks each against
 * what it claims -- lengths kept, bends toward the pole, limits held, no
 * jump when anything switches -- at every angle and at 30, 60 and 120 Hz,
 * and checks the strike table against the ones build_motion.py and
 * motion_hits.py wrote.
 */
#include "../HarnessTypes.h"
#include "../../../Source/SaudFighter/Combat/SaudIK.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <functional>
#include <initializer_list>
#include <limits>
#include <map>
#include <string>
#include <vector>

static int Fails = 0;
static void Check(bool Ok, const char* What)
{
    if (!Ok) { ++Fails; std::printf("  FAIL  %s\n", What); }
}
static bool Near(float A, float B, float Eps = 1e-3f) { return std::fabs(A - B) <= Eps; }

using namespace SaudIK;

static const float Pi = 3.14159265f;

static FVector Rotate(const FVector& V, float Radians)
{
    const float C = std::cos(Radians), S = std::sin(Radians);
    return FVector(V.X * C - V.Y * S, V.X * S + V.Y * C, V.Z);
}
static float Flat(const FVector& V) { return std::sqrt(V.X * V.X + V.Y * V.Y); }
static float TiltDeg(const FVector& N) { return std::acos(std::fmax(-1.f, std::fmin(1.f, N.Z / N.Size()))) * 180.f / Pi; }

// ---------------------------------------------------------------- two bone

static void Solve()
{
    std::printf("TWO BONE  (a leg: thigh 44 cm, shank 42 cm)\n");
    const FVector Hip(0.f, 0.f, 90.f), Knee(4.f, 0.f, 46.f), Ankle(0.f, 0.f, 4.f);
    const float A = FVector::Dist(Hip, Knee), B = FVector::Dist(Knee, Ankle);
    const FVector Pole(60.f, 0.f, 50.f);       // the knee bends forward (+X)

    // Reachable: lengths kept, end on target, knee toward the pole.
    FTwoBone R = TwoBone(Hip, Knee, Ankle, FVector(20.f, 0.f, 20.f), Pole);
    Check(R.bReached, "a target inside reach is reached");
    Check(Near(FVector::Dist(Hip, R.Mid), A) && Near(FVector::Dist(R.Mid, R.End), B), "segment lengths kept");
    Check(FVector::Dist(R.End, FVector(20.f, 0.f, 20.f)) < 1e-2f, "end on the target");
    Check(R.Mid.X > 20.f * (R.Mid.Z - 20.f) / 70.f, "knee bent toward the pole");

    // Out of reach: full stretch along the line, never quite straight.
    R = TwoBone(Hip, Knee, Ankle, FVector(0.f, 0.f, -40.f), Pole);
    Check(!R.bReached, "a target past the limb is reported");
    Check(Near(FVector::Dist(Hip, R.End), (A + B) * 0.995f, 1e-2f), "...and the limb stops at 99.5 %");
    Check(Near(FVector::Dist(Hip, R.Mid), A) && Near(FVector::Dist(R.Mid, R.End), B), "...with its lengths");
    Check(R.Mid.X > 0.5f, "...and still bent toward the pole");

    // Rotation invariance: turn everything about Z, the answer turns with it.
    int Bad = 0;
    for (int I = 0; I < 72; ++I)
    {
        const float Ang = I * 5.f * Pi / 180.f;
        const FVector T(23.f, 9.f, 17.f);
        FTwoBone Base = TwoBone(Hip, Knee, Ankle, T, Pole);
        FTwoBone Turned = TwoBone(Rotate(Hip, Ang), Rotate(Knee, Ang), Rotate(Ankle, Ang), Rotate(T, Ang), Rotate(Pole, Ang));
        if (FVector::Dist(Rotate(Base.Mid, Ang), Turned.Mid) > 1e-2f) ++Bad;
        if (FVector::Dist(Rotate(Base.End, Ang), Turned.End) > 1e-2f) ++Bad;
    }
    Check(Bad == 0, "the solve turns with the limb, 72 angles");

    // A pole on the limb's line says nothing: the clip's bend is kept.
    R = TwoBone(Hip, Knee, Ankle, FVector(0.f, 0.f, 10.f), FVector(0.f, 0.f, 40.f));
    Check(R.Mid.X > 0.f && Near(R.Mid.Y, 0.f), "a pole on the line leaves the clip's bend");

    // Target at the root: nothing moves.
    R = TwoBone(Hip, Knee, Ankle, Hip, Pole);
    Check(R.Mid.X == Knee.X && R.End.Z == Ankle.Z, "a target on the root leaves the limb alone");

    // A clip leg at 178 degrees, straighter than MaxStretch: at no share
    // the solve is the clip, so switching it on or off moves nothing.
    {
        const float Bend = 2.f * Pi / 180.f;               // 178 degrees at the knee
        const FVector K2(44.f * std::sin(Bend * 0.5f), 0.f, 90.f - 44.f * std::cos(Bend * 0.5f));
        const FVector A2(0.f, 0.f, K2.Z - 42.f * std::cos(Bend * 0.5f));
        const FVector A3(A2.X - 42.f * std::sin(Bend * 0.5f) * 0.f, 0.f, A2.Z);
        const FTwoBone Z = TwoBone(Hip, K2, A3, A3, K2, 0.f);
        Check(FVector::Dist(Z.End, A3) < 1e-3f && FVector::Dist(Z.Mid, K2) < 1e-3f, "alpha 0 is the clip, however straight its limb");
    }

    // A rigid end carries its tip onto the target.
    {
        const FVector R0(0.f, 0.f, 140.f), M0(30.f, 0.f, 128.f), E0(58.f, 2.f, 139.f), T0(65.f, 0.f, 140.f);
        const FTwoBone To = SolveStrike(R0, M0, T0, FVector(55.f, 25.f, 150.f), 1.f);
        const FVector E1 = RigidEnd(M0, E0, T0, To);
        const FVector T1 = E1 + Swing(T0 - E0, T0 - M0, To.End - To.Mid);
        Check(FVector::Dist(T1, To.End) < 1e-2f && Near(FVector::Dist(E1, To.Mid), FVector::Dist(E0, M0), 1e-2f),
              "a rigid end carries its tip onto the target");
    }
}

// -------------------------------------------------------------------- feet

static void Feet()
{
    std::printf("FEET  (planted under %.0f cm, swinging over %.0f)\n", PlantHeight, PlantFade);
    Check(PlantAlpha(0.f) == 1.f && PlantAlpha(PlantHeight) == 1.f, "on the floor: planted");
    Check(PlantAlpha(PlantFade) == 0.f && PlantAlpha(60.f) == 0.f, "in the air: swinging");
    Check(Near(PlantAlpha((PlantHeight + PlantFade) * 0.5f), 0.5f), "halfway between: half");

    // Settle: frame-rate independent.
    float A = 0.f, B = 0.f;
    for (int I = 0; I < 60; ++I) A = Settle(A, -10.f, FootSettleRate, 1.f / 60.f);
    for (int I = 0; I < 30; ++I) B = Settle(B, -10.f, FootSettleRate, 1.f / 30.f);
    Check(Near(A, B, 0.05f) && A < -9.9f, "settling reaches the same place at 30 and 60 Hz");

    // The engine's way round: FQuat about +Z by +90 takes +X to +Y.
    const FVector V = RotateAbout(FVector(1.f, 0.f, 0.f), FVector::UpVector, Pi * 0.5f);
    Check(Near(V.X, 0.f) && Near(V.Y, 1.f) && Near(V.Z, 0.f), "a turn about up by +90 takes +X to +Y, as FQuat does");

    // The mesh's space, turned 90 degrees, 100 cm along X, at twice the size.
    FBasis M; M.Origin = FVector(100.f, 0.f, 0.f); M.X = FVector(0.f, 1.f, 0.f); M.Y = FVector(-1.f, 0.f, 0.f); M.Scale = 2.f;
    const FVector W = ToWorld(M, FVector(1.f, 0.f, 0.f)), P = ToMesh(M, FVector(100.f, 2.f, 0.f));
    const FVector D = DirToMesh(M, FVector(0.f, 1.f, 0.f)), E = DirToWorld(M, FVector(1.f, 1.f, 0.f));
    Check(FVector::Dist(W, FVector(100.f, 2.f, 0.f)) < 1e-4f && FVector::Dist(P, FVector(1.f, 0.f, 0.f)) < 1e-4f
          && FVector::Dist(D, FVector(1.f, 0.f, 0.f)) < 1e-4f && FVector::Dist(E, FVector(-1.f, 1.f, 0.f)) < 1e-4f,
          "the mesh's space is turned and scaled the engine's way");
}

// ------------------------------------------------------------- feet, held

static FBasis At(const FVector& Origin, float YawDeg)
{
    FBasis B; const float R = YawDeg * Pi / 180.f;
    B.Origin = Origin; B.X = FVector(std::cos(R), std::sin(R), 0.f); B.Y = FVector(-std::sin(R), std::cos(R), 0.f);
    return B;
}

// A man in a guard: lead (left) foot ahead, rear behind. Rest heights 8 / 2.4.
// Each frame traces at last frame's drawn heel and ball, as the engine does.
struct Man
{
    FFeetState St; FFeetIn In;
    std::function<float(float, float)> Height = [](float, float) { return 0.f; };
    std::function<FVector(float, float)> Normal = [](float, float) { return FVector::UpVector; };
    std::function<bool(float, float)> Hit = [](float, float) { return true; };
    FVector LastHeel[2], LastBall[2]; bool bHasLast = false;
    FFeetPlan Plan; FFootPose Pose[2];
    Man()
    {
        In.bWanted = true; In.bHold = true;
        FFootIn& L = In.Foot[0]; FFootIn& R = In.Foot[1];
        L.Hip = FVector(2.f, 10.f, 92.f); L.Ankle = FVector(18.f, 14.f, 8.f); L.Ball = FVector(33.f, 15.f, 2.4f);
        R.Hip = FVector(-2.f, -10.f, 92.f); R.Ankle = FVector(-24.f, -14.f, 8.f); R.Ball = FVector(-9.f, -15.f, 2.4f);
        for (int S = 0; S < 2; ++S)
        {
            In.Foot[S].AnkleRest = 8.f; In.Foot[S].BallRest = 2.4f; In.Foot[S].LegLength = 88.f;
            In.Foot[S].ToeDir = FVector(1.f, 0.f, 0.f); In.Foot[S].FootFwd = FVector(1.f, 0.f, 0.f); In.Foot[S].FootUp = FVector::UpVector;
        }
    }
    void Trace()
    {
        for (int S = 0; S < 2; ++S)
        {
            const FVector H = bHasLast ? LastHeel[S] : ToWorld(In.Mesh, In.Foot[S].Ankle);
            const FVector B = bHasLast ? LastBall[S] : ToWorld(In.Mesh, In.Foot[S].Ball);
            auto Pt = [&](const FVector& Wd, FGroundPoint& G)
            {
                G.bHit = Hit(Wd.X, Wd.Y);
                G.Point = ToMesh(In.Mesh, FVector(Wd.X, Wd.Y, Height(Wd.X, Wd.Y)));
                G.Normal = DirToMesh(In.Mesh, Normal(Wd.X, Wd.Y));
            };
            Pt(H, In.Foot[S].HeelGround); Pt(B, In.Foot[S].BallGround);
        }
    }
    void Step(float Dt)
    {
        Trace();
        Plan = StepFeet(St, In, Dt);
        for (int S = 0; S < 2; ++S)
        {
            const FVector Hip = In.Foot[S].Hip + Plan.Pelvis;
            // as the proxy does: no leg pass at all while the feet are off
            if (Plan.Alpha > 0.f) Pose[S] = FinishFoot(St.Hold[S], Plan.Foot[S], In.Foot[S], Hip, Dt);
            else { Pose[S] = FFootPose(); Pose[S].Ankle = In.Foot[S].Ankle; }
            LastHeel[S] = ToWorld(In.Mesh, Pose[S].Ankle);
            LastBall[S] = ToWorld(In.Mesh, Plan.Foot[S].Ball);
        }
        bHasLast = true;
        In.bTeleported = false;
    }
    void Run(float Seconds, float Hz = 60.f) { const int N = (int)std::lround(Seconds * Hz); for (int I = 0; I < N; ++I) Step(1.f / Hz); }
    FVector BallW(int S) const { return ToWorld(In.Mesh, Plan.Foot[S].Ball); }
    FVector AnkleW(int S) const { return ToWorld(In.Mesh, Pose[S].Ankle); }
    FVector RawW(int S) const { return ToWorld(In.Mesh, In.Foot[S].Ball); }
    FVector RawAnkleW(int S) const { return ToWorld(In.Mesh, In.Foot[S].Ankle); }
};

static void Held()
{
    std::printf("FEET, HELD  (where a planted ball is kept, and when it lets go)\n");

    // ---- the feet's share comes all the way on, frame on frame (bug a)
    {
        bool Ok = true;
        for (float Hz : {30.f, 60.f, 120.f})
        {
            Man M; M.Run(0.2f, Hz);
            if (M.Plan.Alpha < 0.97f) Ok = false;
        }
        Check(Ok, "the feet come all the way on: 97 % within 0.2 s, at 30, 60 and 120 Hz");
    }

    // ---- standing, then the man slides 5 cm and turns 8 degrees under his planted feet
    {
        Man M; M.Run(0.5f);
        const FVector B0 = M.BallW(0), B1 = M.BallW(1);
        float Worst = 0.f;
        for (int I = 1; I <= 30; ++I)
        {
            const float T = I / 30.f;
            M.In.Mesh = At(FVector(4.f * T, 3.f * T, 0.f), 8.f * T);
            M.Step(1.f / 60.f);
            Worst = std::fmax(Worst, std::fmax(Flat(M.BallW(0) - B0), Flat(M.BallW(1) - B1)));
        }
        Check(Worst < 0.05f, "a held ball stays where it was planted while the man moves and turns over it");
        Check(M.St.Hold[0].bHeld && M.St.Hold[1].bHeld, "...and neither foot let go under 12 cm");
    }

    // ---- the man slides forward at 100 cm/s with his guard's feet still
    {
        bool StepAt = true, Lift = true, NoJump = true, Heel = true;
        for (float Hz : {30.f, 60.f, 120.f})
        {
            Man M; M.Run(0.5f, Hz);
            float FirstDrift = -1.f, MaxLift = 0.f, Pop = 0.f, HeelPop = 0.f;
            FVector Prev[2] = { M.BallW(0), M.BallW(1) }, PrevRaw[2] = { M.RawW(0), M.RawW(1) };
            FVector PrevAnkle[2] = { M.AnkleW(0), M.AnkleW(1) };
            const int N = (int)(0.6f * Hz);
            for (int I = 1; I <= N; ++I)
            {
                M.In.Mesh = At(FVector(100.f * I / Hz, 0.f, 0.f), 0.f);
                const float D0 = Flat(M.St.Hold[0].Anchor - M.RawW(0)), D1 = Flat(M.St.Hold[1].Anchor - M.RawW(1));
                const bool H0 = M.St.Hold[0].bHeld, H1 = M.St.Hold[1].bHeld;
                M.Step(1.f / Hz);
                if (FirstDrift < 0.f && ((H0 && !M.St.Hold[0].bHeld) || (H1 && !M.St.Hold[1].bHeld))) FirstDrift = std::fmax(D0, D1);
                MaxLift = std::fmax(MaxLift, M.Plan.Foot[0].Ball.Z - M.In.Foot[0].Ball.Z);
                for (int S = 0; S < 2; ++S)
                {
                    const float Move = Flat(M.BallW(S) - Prev[S]);
                    Pop = std::fmax(Pop, Move - Flat(M.RawW(S) - PrevRaw[S]));
                    HeelPop = std::fmax(HeelPop, FVector::Dist(M.AnkleW(S), PrevAnkle[S]) - FVector::Dist(M.BallW(S), Prev[S]));
                    Prev[S] = M.BallW(S); PrevRaw[S] = M.RawW(S); PrevAnkle[S] = M.AnkleW(S);
                }
            }
            std::printf("  %.0f Hz: first step at %.2f cm of drift, lift %.2f, worst extra ball move %.2f, heel over ball %.2f\n",
                        Hz, FirstDrift, MaxLift, Pop, HeelPop);
            if (!(FirstDrift >= 12.f - 100.f / Hz && FirstDrift <= 12.f + 100.f / Hz + 0.01f)) StepAt = false;
            if (!(MaxLift > 3.5f && MaxLift < 4.5f)) Lift = false;
            if (Hz == 60.f && !(Pop < 1.6f * 30.f / 0.14f / Hz + 1.67f)) NoJump = false;
            if (Hz == 60.f && !(HeelPop < 1.5f)) Heel = false;
        }
        Check(StepAt, "a held foot steps once the clip has carried it 12 cm off");
        Check(Lift, "a step lifts the foot 4 cm at its middle");
        Check(NoJump, "a hand-back has no jump");
        Check(Heel, "a foot that steps does not drop its heel");
    }
    {
        Man M; M.Run(0.5f);
        int Both = 0;
        for (int I = 1; I <= 30; ++I)
        {
            M.In.Mesh = At(FVector(80.f * I / 60.f, 0.f, 0.f), 0.f);
            M.Step(1.f / 60.f);
            const bool S0 = !M.St.Hold[0].bHeld && M.St.Hold[0].Progress < 1.f, S1 = !M.St.Hold[1].bHeld && M.St.Hold[1].Progress < 1.f;
            if (S0 && S1) ++Both;
        }
        Check(Both == 0, "only one foot steps at a time");
    }
    {
        // the rear 20 cm off its hold, the lead 14: the rear steps first
        Man M; M.Run(0.5f);
        M.In.Foot[0].Ball.X += 14.f; M.In.Foot[0].Ankle.X += 14.f;
        M.In.Foot[1].Ball.X += 20.f; M.In.Foot[1].Ankle.X += 20.f;
        M.Step(1.f / 60.f);
        Check(!M.St.Hold[1].bHeld && M.St.Hold[0].bHeld, "the foot further off its hold steps first");
    }
    {
        // a man twice the size steps at 24 cm of drift, not 12
        Man M; for (int S = 0; S < 2; ++S) M.In.Foot[S].LegLength = 176.4f;
        M.Run(0.5f);
        float FirstDrift = -1.f;
        for (int I = 1; I <= 30 && FirstDrift < 0.f; ++I)
        {
            M.In.Mesh = At(FVector(100.f * I / 60.f, 0.f, 0.f), 0.f);
            const float D0 = Flat(M.St.Hold[0].Anchor - M.RawW(0));
            const bool H0 = M.St.Hold[0].bHeld, H1 = M.St.Hold[1].bHeld;
            M.Step(1.f / 60.f);
            if ((H0 && !M.St.Hold[0].bHeld) || (H1 && !M.St.Hold[1].bHeld)) FirstDrift = D0;
        }
        Check(FirstDrift > 22.3f && FirstDrift < 25.7f, "a man twice Saud's size steps at twice the drift");
    }

    // ---- planted again mid-hand-back: held where it is drawn
    {
        Man M; M.Run(0.5f);
        for (int I = 1; I <= 9; ++I) { M.In.Mesh = At(FVector((float)I, 0.f, 0.f), 0.f); M.Step(1.f / 60.f); }
        FVector Prev = M.BallW(0); float Worst = 0.f;
        for (int I = 1; I <= 12; ++I)
        {
            M.In.Foot[0].Ball.Z = (I == 2 || I == 3) ? 2.4f + 2.f : 2.4f;
            M.Step(1.f / 60.f);
            Worst = std::fmax(Worst, Flat(M.BallW(0) - Prev));
            Prev = M.BallW(0);
        }
        Check(Worst < 2.5f && M.St.Hold[0].bHeld, "a foot planted again mid-hand-back is held where it is drawn");
    }

    // ---- which balls are on the floor
    {
        Man M; M.Run(0.5f);
        int HeldAbove = 0;
        for (int I = 0; I <= 22; ++I)
        {
            const float U = I / 22.f; const float Lift = 10.f * std::sin(Pi * U);
            M.In.Foot[0].Ball.Z = 2.4f + Lift; M.In.Foot[0].Ankle.Z = 8.f + Lift;
            M.In.Foot[0].Ball.X = 33.f + 60.f * U; M.In.Foot[0].Ankle.X = 18.f + 60.f * U;
            M.Step(1.f / 60.f);
            if (M.St.Hold[0].bHeld && Lift > 1.5f) ++HeldAbove;
        }
        Check(HeldAbove == 0, "a street man's 10 cm swing is never held");
        Man H; H.Run(0.5f);
        H.In.Foot[0].Ball.Z = 2.4f + 1.2f; H.Step(1.f / 60.f);
        Check(H.St.Hold[0].bHeld, "a held ball 1.2 cm up stays held");
        H.In.Foot[0].Ball.Z = 2.4f + 6.f; H.Step(1.f / 60.f); H.In.Foot[0].Ball.Z = 2.4f + 1.2f; H.Run(0.2f);
        Check(!H.St.Hold[0].bHeld, "...and a free one 1.2 cm up is not taken");
        Man R; for (int S = 0; S < 2; ++S) R.In.Foot[S].BallRest = 2.4f - 3.f;   // his clip plants the balls 3 cm over his rest
        R.Run(0.5f);
        Check(R.St.Hold[0].bHeld && R.St.Hold[1].bHeld, "a clip retargeted 3 cm off a man's rest still plants his feet");
    }

    // ---- a jump, a dash, a block walked
    {
        Man M; M.Run(0.5f);
        M.In.Mesh = At(FVector(500.f, 0.f, 0.f), 0.f); M.Step(1.f / 60.f);
        Check(Flat(M.BallW(0) - M.RawW(0)) < 0.01f, "a jump of the man drops the hold at once, no glide");
    }
    {
        Man M; M.Run(0.5f);
        M.In.bWanted = false;
        float Prev = 1e9f; bool Ok = true;
        for (int I = 1; I <= 8; ++I)
        {
            M.In.Mesh = At(FVector(25.f * I, 0.f, 0.f), 0.f);
            M.Step(1.f / 60.f);
            const FVector Off = M.Plan.Foot[1].Ball - M.In.Foot[1].Ball;
            const float Behind = Flat(Off);
            if (Behind > Prev + 1e-3f) Ok = false;
            Prev = Behind;
        }
        Check(Ok, "a foot let go never falls further behind the clip, however fast the man goes");
        M.Run(0.2f);
        Check(!M.St.Hold[0].bHeld && M.St.Hold[0].Weight == 0.f && !M.St.Hold[1].bHeld && M.St.Hold[1].Weight == 0.f,
              "the feet let go when they are not wanted");
    }
    {
        // the Block clip walked at 130 cm/s: its feet do not step, so they are not held
        Man M; M.In.bHold = HoldsFeet(false, false, FStrideMeter(), 0);
        int Steps = 0;
        for (int I = 1; I <= 60; ++I)
        {
            M.In.Mesh = At(FVector(130.f * I / 60.f, 0.f, 0.f), 0.f);
            M.Step(1.f / 60.f);
            for (int S = 0; S < 2; ++S) if (M.St.Hold[S].bStep && M.St.Hold[S].Progress < 1.f) ++Steps;
        }
        Check(Steps == 0 && !M.St.Hold[0].bHeld, "a block walked across the floor does not tap-dance");
        FStrideMeter Walk; Walk.Clip = 4; Walk.bValid = true; Walk.Speed = 341.f;
        Check(HoldsFeet(true, false, FStrideMeter(), 4) && HoldsFeet(false, true, FStrideMeter(), 4)
              && HoldsFeet(false, false, Walk, 4) && !HoldsFeet(false, false, Walk, 5),
              "an attack, a man standing, or a clip whose feet step holds its feet; nothing else");
    }

    // ---- the strike's leg: never held, never jumps on the way in or out
    {
        bool Ok = true;
        for (float Dip : {0.f, -12.f})
        {
            Man M; M.Height = [Dip](float, float) { return Dip; };
            M.Run(1.f);
            for (int I = 1; I <= 20; ++I) { M.In.Mesh = At(FVector(9.f * I / 20.f, 0.f, 0.f), 10.f * I / 20.f); M.Step(1.f / 60.f); }
            float Worst = 0.f;
            FVector Prev = M.AnkleW(1), PrevRaw = M.RawAnkleW(1);
            for (int I = 0; I < 60; ++I)
            {
                M.In.Foot[1].bStrike = I < 24;
                M.Step(1.f / 60.f);
                Worst = std::fmax(Worst, FVector::Dist(M.AnkleW(1), Prev) - FVector::Dist(M.RawAnkleW(1), PrevRaw));
                Prev = M.AnkleW(1); PrevRaw = M.RawAnkleW(1);
                if (I == 18 && (M.St.Hold[1].bHeld || M.St.Hold[1].Weight != 0.f)) Ok = false;
            }
            std::printf("  strike leg on %.0f cm: worst move past the clip's %.2f cm\n", Dip, Worst);
            if (Worst >= 3.5f) Worst = -1.f;
            if (Worst < 0.f) Ok = Ok && false;
            if (Dip == 0.f) Check(Worst >= 0.f, "a kick's leg leaves the ground and comes back with no jump");
            else Check(Worst >= 0.f, "a kick's leg leaves the ground and comes back with no jump, over a dip");
        }
        Check(Ok, "the strike's leg is never held");
    }

    // ---- the heel rolls onto the ball when the leg is short
    {
        FFootHold H; H.bHeld = true; H.Weight = 1.f;
        FFootPlan P; P.Ball = FVector(-9.f, -15.f, 2.4f); P.Tilt = FVector::UpVector; P.ToeShare = 1.f;
        FFootIn F; F.Ankle = FVector(-24.f, -14.f, 8.f); F.Ball = FVector(-9.f, -15.f, 2.4f); F.LegLength = 88.f;
        const FVector Hip(10.f, -10.f, 92.f);   // ankle to hip: about 90.7 on an 88 cm leg
        FFootPose R;
        for (int K = 0; K < 60; ++K) R = FinishFoot(H, P, F, Hip, 1.f / 60.f);
        std::printf("  heel roll %.2f degrees, ankle to hip %.2f\n", R.Roll * 180.f / Pi, FVector::Dist(R.Ankle, Hip));
        Check(R.Roll > 0.f && R.Roll <= 30.f * Pi / 180.f + 1e-4f && FVector::Dist(R.Ankle, Hip) <= 88.f * 0.985f + 0.05f,
              "the roll brings the ankle back inside 98.5 % of the leg, under 30 degrees");
        Check(std::fabs(R.Toe.Z) < 0.01f && R.Toe.X > 0.99f, "toes bend up to lie flat when the heel rolls");
        FFootHold Fresh; Fresh.bHeld = true; Fresh.Weight = 1.f;
        const FFootPose One = FinishFoot(Fresh, P, F, Hip, 1.f / 60.f);
        Check(One.Roll * 180.f / Pi < 10.f, "a foot rolls onto its ball over frames, never in one");
        FFootHold Back; Back.bHeld = false; Back.Weight = 0.5f; Back.Progress = 0.5f;
        FFootPose Handing;
        for (int K = 0; K < 30; ++K) Handing = FinishFoot(Back, P, F, Hip, 1.f / 60.f);
        Check(Handing.Roll * 180.f / Pi > 10.f, "a foot handed back keeps its heel up until it is the clip's");
    }

    // ---- a man standing still brings a foot left off its spot back under
    // the clip, one foot at a time; in a swing nothing settles
    {
        auto Turned = [](bool bSettle, int& Both)
        {
            Man M; M.In.bSettle = bSettle; M.Run(0.5f);
            const float R = 25.f * Pi / 180.f;                    // a 25 degree snap
            M.In.Mesh.X = FVector(std::cos(R), std::sin(R), 0.f);
            M.In.Mesh.Y = FVector(-std::sin(R), std::cos(R), 0.f);
            Both = 0;
            for (int K = 0; K < 90; ++K)
            {
                M.Step(1.f / 60.f);
                const bool A = M.St.Hold[0].bStep && M.St.Hold[0].Progress < 1.f;
                const bool B = M.St.Hold[1].bStep && M.St.Hold[1].Progress < 1.f;
                Both += A && B;
            }
            float Worst = 0.f;
            for (int S = 0; S < 2; ++S) Worst = std::fmax(Worst, Flat(M.BallW(S) - M.RawW(S)));
            return Worst;
        };
        int BothSettle = 0, BothSwing = 0;
        const float Settled = Turned(true, BothSettle), Kept = Turned(false, BothSwing);
        std::printf("  a 25 degree snap, standing: a foot %.1f cm off its spot after 1.5 s settled, %.1f in a swing\n", Settled, Kept);
        Check(Settled < 3.f && BothSettle == 0, "a man standing still steps a foot left off its spot back under him, one foot at a time");
        Check(Kept > 5.f, "...but not in a swing: the strike keeps its feet where they are");
    }

    // ---- a mesh drawn at twice its size steps after twice the world's drift
    {
        Man M; M.In.Mesh.Scale = 2.f; M.Run(0.5f);
        bool bStepped = false;
        for (int K = 0; K < 9; ++K)
        {
            M.In.Mesh.Origin.X += 2.f;                     // 18 cm in all: 1.5 times Saud's 12, under twice it
            M.Step(1.f / 60.f);
            for (int S = 0; S < 2; ++S) bStepped = bStepped || !M.St.Hold[S].bHeld;
        }
        Check(!bStepped, "a man drawn at twice the scale keeps his feet through 18 cm of the world's drift");
    }

    // ---- the roll goes with the feet: none left when they switch off, none
    // brought back when they come on (the proxy skips the leg pass at 0)
    {
        Man M; M.Run(0.5f);
        for (int K = 0; K < 12; ++K) { M.In.Mesh.Origin.X += 8.f / 12.f; M.Step(1.f / 60.f); }   // slid 8 cm over his feet
        float Rolled = 0.f;
        for (int S = 0; S < 2; ++S) Rolled = std::fmax(Rolled, M.Pose[S].Roll);
        M.In.bWanted = false;
        float LastOn = 0.f;
        for (int K = 0; K < 30; ++K)
        {
            M.Step(1.f / 60.f);
            if (M.Plan.Alpha > 0.f) LastOn = std::fmax(M.Pose[0].Roll, M.Pose[1].Roll);
        }
        M.In.bWanted = true;
        M.Step(1.f / 60.f);
        const float FirstBack = std::fmax(M.Pose[0].Roll, M.Pose[1].Roll);
        std::printf("  rolled %.1f degrees; drawn on the feet's last frame %.3f, on their first back %.3f\n",
                    Rolled * 180.f / Pi, LastOn * 180.f / Pi, FirstBack * 180.f / Pi);
        Check(Rolled * 180.f / Pi > 3.f && LastOn * 180.f / Pi < 0.25f && FirstBack * 180.f / Pi < 0.25f,
              "the heel's roll fades with the feet: nothing left as they go, nothing brought back");
    }
}

static void GroundTwo()
{
    std::printf("FEET, GROUND  (a heel and a ball on steps, kerbs and ramps)\n");
    auto Settled = [](Man& M) { M.Run(1.5f); };
    {
        Man M; M.Height = [](float X, float) { return X > 25.f ? 15.f : 0.f; }; Settled(M);
        const FFootPlan& P = M.Plan.Foot[0];
        Check(TiltDeg(P.Tilt) < 0.5f && Near(P.Ball.Z - 2.4f, 15.f, 0.1f) && M.Pose[0].Ankle.Z - 8.f >= 14.9f,
              "across a kerb the foot stands level on the higher");
    }
    {
        Man M; M.Height = [](float X, float) { return X < 25.f ? 15.f : 0.f; }; Settled(M);
        const float Heel = M.Pose[0].Ankle.Z - 8.f;
        Check(TiltDeg(M.Plan.Foot[0].Tilt) < 0.5f && Heel >= 14.9f && Heel < 15.1f, "...heel on the kerb, toes over the road: level on the kerb");
    }
    {
        Man M; M.Height = [](float X, float) { return X > 25.f ? -15.f : 0.f; }; Settled(M);
        Check(M.Plan.Pelvis.Z > -0.5f, "across an edge the hips do not drop for the lower");
    }
    {
        Man M; M.Height = [](float X, float) { return X > 25.f ? 15.f : 0.f; };
        M.Normal = [](float X, float) { return X > 25.f ? FVector(-0.7071f, 0.f, 0.7071f) : FVector::UpVector; }; Settled(M);
        Check(TiltDeg(M.Plan.Foot[0].Tilt) < 0.5f && Near(M.Plan.Foot[0].Ball.Z - 2.4f, 15.f, 0.1f), "across a bevelled kerb the foot stands level on the higher");
        Check(std::fabs(M.Pose[0].Toe.Z) < 0.02f, "on a bevelled kerb the toes lie flat");
    }
    {
        // a heel and ball 6.5 degrees apart from their normals' slope
        FFootIn F; F.Ankle = FVector(0.f, 0.f, 8.f); F.Ball = FVector(20.f, 0.f, 2.4f); F.AnkleRest = 8.f; F.BallRest = 2.4f;
        F.HeelGround.bHit = F.BallGround.bHit = true;
        F.HeelGround.Point = FVector(0.f, 0.f, 0.f); F.BallGround.Point = FVector(20.f, 0.f, 20.f * std::tan(6.5f * Pi / 180.f));
        bool Across = true; PlaceFoot(F, true, 0.f, Across);
        bool Not = false; PlaceFoot(F, true, 0.f, Not);
        Check(Across && !Not, "an edge, once across, stays across until the heel and ball agree within 5 degrees");
    }
    {
        const float A = 20.f * Pi / 180.f;
        Man M; M.Height = [A](float X, float) { return X * std::tan(A); };
        M.Normal = [A](float, float) { return FVector(-std::sin(A), 0.f, std::cos(A)); }; Settled(M);
        const FFootPlan& P = M.Plan.Foot[0];
        const FVector BallW = M.BallW(0), AnkleW = M.AnkleW(0);
        const FVector BallSole = BallW - P.Tilt * 2.4f, HeelSole = AnkleW - P.Tilt * 8.f;
        Check(Near(TiltDeg(P.Tilt), 20.f, 0.5f), "on a 20 degree ramp the foot tilts 20");
        Check(std::fabs(BallSole.Z - M.Height(BallSole.X, 0)) < 0.5f && std::fabs(HeelSole.Z - M.Height(HeelSole.X, 0)) < 0.7f,
              "on a ramp the ball stays on its ground and the heel comes onto it");
        // the man turns 90 degrees on the spot: his soles stay on the ramp
        M.In.Mesh = At(FVector(0.f, 0.f, 0.f), 90.f); M.Step(1.f / 60.f);
        const FVector SoleW = DirToWorld(M.In.Mesh, M.Plan.Foot[0].Tilt);
        const FVector Ramp(-std::sin(A), 0.f, std::cos(A));
        Check(std::acos(std::fmin(1.f, FVector::DotProduct(SoleW, Ramp))) * 180.f / Pi < 2.f, "a sole on a ramp stays on it while the man turns on the spot");
        Man E; E.Run(0.5f);
        E.Height = [A](float X, float) { return X * std::tan(A); };
        E.Normal = [A](float, float) { return FVector(-std::sin(A), 0.f, std::cos(A)); };
        E.Step(1.f / 60.f);
        const float T1 = TiltDeg(E.Plan.Foot[0].Tilt);
        Check(T1 > 3.f && T1 < 10.f, "the sole eases onto a ramp");
        Man O; O.Height = E.Height; O.Normal = E.Normal; Settled(O);
        O.In.bWanted = false;
        for (int I = 0; I < 4; ++I) O.Step(1.f / 60.f);
        std::printf("  four frames after the feet are let go on a ramp: tilt %.2f\n", TiltDeg(O.Plan.Foot[0].Tilt));
        Check(TiltDeg(O.Plan.Foot[0].Tilt) < 4.f, "the soles fade with the feet");
    }
    {
        Man M; M.Normal = [](float X, float) { return X > 25.f ? FVector(1.f, 0.f, 0.f) : FVector::UpVector; };
        M.Hit = [](float X, float) { return X > 25.f; }; Settled(M);
        Check(TiltDeg(M.Plan.Foot[0].Tilt) < 0.5f, "the face of a step gives its height, not its slope");
    }
    {
        const float A = 40.f * Pi / 180.f;
        Man M; M.Height = [A](float X, float) { return X * std::tan(A); };
        M.Normal = [A](float, float) { return FVector(-std::sin(A), 0.f, std::cos(A)); }; Settled(M);
        const FVector N(-std::sin(A), 0.f, std::cos(A));
        Check(Near(TiltDeg(M.Plan.Foot[0].Tilt), 30.f, 0.5f), "a 40 degree ramp tilts the foot 30");
        Check(std::fabs(FVector::DotProduct(M.Pose[0].Toe, N)) < 0.02f, "the toes lie flat on a 40 degree slope the foot can only tilt 30 on");
        Man S; S.Height = M.Height; S.Normal = M.Normal;
        S.In.Foot[0].Ball.Z = 12.4f; S.In.Foot[0].Ankle.Z = 18.f; Settled(S);
        Check(FVector::Dist(S.Pose[0].Toe, FVector(1.f, 0.f, 0.f)) < 0.01f, "a foot in the air keeps its toes");
    }
    {
        Man M; M.Height = [](float X, float) { return X > 25.f ? 35.f : 0.f; };
        M.In.Foot[0].Ankle.Z = 38.f; M.In.Foot[0].Ball.Z = 32.4f; Settled(M);
        Check(M.Plan.Foot[0].Ball.Z - 2.4f >= 34.9f, "a swinging foot never goes through a step, ball first");
        Man K; K.Height = [](float X, float) { return X < 25.f ? 35.f : 0.f; };
        K.In.Foot[0].Ankle.Z = 38.f; K.In.Foot[0].Ball.Z = 32.4f; Settled(K);
        Check(K.Pose[0].Ankle.Z - 8.f >= 34.9f, "a swinging foot never goes through a step, heel first");
        Man D; D.Height = [](float X, float) { return X > 10.f ? -10.f : 0.f; };
        D.In.Foot[0].Ankle.Z = 38.f; D.In.Foot[0].Ball.Z = 32.4f; Settled(D);
        Check(Near(D.Plan.Foot[0].Ball.Z, 32.4f, 0.01f), "...and is not pulled down into a dip");
    }
    {
        Man M; M.Run(0.5f);
        M.Height = [](float X, float) { return X > 25.f ? 15.f : 0.f; };
        for (int I = 0; I < 5; ++I) M.Step(1.f / 60.f);   // one frame of trace lag and four
        Check(M.Plan.Foot[0].Ball.Z - 2.4f >= 0.9f * 15.f, "a foot meets a step up within four frames");
    }

    // ---- the hips
    {
        Man M; M.Height = [](float X, float) { return X > 10.f ? -12.f : -3.f; }; Settled(M);
        Check(Near(M.Plan.Pelvis.Z, -12.f, 0.1f), "the pelvis goes down to the lower foot");
        Man U; U.Height = [](float X, float) { return X > 10.f ? 9.f : 5.f; }; Settled(U);
        Check(Near(U.Plan.Pelvis.Z, 0.f, 0.01f), "a step up under the feet never lifts the hips");
        Man D; D.Height = [](float, float) { return -60.f; }; Settled(D);
        Check(D.Plan.Pelvis.Z >= -40.05f, "a drop is not reached for, by the feet");
    }
    {
        // the lead lifted through the top of the ground's share, over a 20 cm dip
        float Z[2];
        for (int K = 0; K < 2; ++K)
        {
            Man M; M.Height = [](float X, float) { return X > 10.f ? -20.f : 0.f; };
            const float Lift = K ? 6.05f : 5.95f;
            M.In.Foot[0].Ball.Z = 2.4f + Lift; M.In.Foot[0].Ankle.Z = 8.f + Lift;
            Settled(M);
            Z[K] = M.Plan.Pelvis.Z;
        }
        Check(std::fabs(Z[0] - Z[1]) < 0.5f, "the hips do not lurch as a foot lifts out of the ground's share");
    }
    {
        Man M; M.Height = [](float, float) { return -12.f; }; Settled(M);
        M.In.bWanted = false; M.Run(0.15f);
        Check(std::fabs(M.Plan.Pelvis.Z) < 0.5f, "the hips fade with the feet");
        Man T; T.Height = [](float, float) { return -12.f; }; Settled(T);
        T.In.bTeleported = true; T.Step(1.f / 60.f);
        Check(T.Plan.Pelvis.Z > -5.f, "a man put somewhere new starts his feet afresh");
    }
    {
        // a street man's 10 cm swing carries the lead over a 20 cm ditch; the rear stands on the road
        Man M; M.Height = [](float X, float) { return X > 45.f && X < 75.f ? -20.f : 0.f; };
        M.Run(0.5f);
        float Low = 0.f;
        for (int I = 0; I <= 22; ++I)
        {
            const float U = I / 22.f; const float Lift = 10.f * std::sin(Pi * U);
            M.In.Foot[0].Ball.Z = 2.4f + Lift; M.In.Foot[0].Ankle.Z = 8.f + Lift;
            M.In.Foot[0].Ball.X = 33.f + 60.f * U; M.In.Foot[0].Ankle.X = 18.f + 60.f * U;
            M.Step(1.f / 60.f);
            Low = std::fmin(Low, M.Plan.Pelvis.Z);
        }
        std::printf("  a street swing over a ditch: the hips at most %.2f\n", Low);
        Check(Low > -1.f, "a street man's swing over a ditch leaves the hips");
    }
    {
        // the capsule steps up a 15 cm kerb in one frame
        Man M; M.Height = [](float X, float) { return X > 0.f ? 15.f : 0.f; };
        M.Height = [](float, float) { return 0.f; };
        M.Run(0.5f);
        const float Before = M.In.Mesh.Origin.Z + M.Plan.Pelvis.Z;
        M.Height = [](float X, float) { return X > 25.f ? 15.f : 0.f; };
        M.In.Mesh.Origin.Z += 15.f; M.Step(1.f / 60.f);
        const float After = M.In.Mesh.Origin.Z + M.Plan.Pelvis.Z;
        Check(std::fabs(After - Before) < 1.f, "a kerb the capsule steps up in one frame does not lift the body that frame");
        Check(!SteppedCapsule(FVector(5.7f, 0.f, 2.07f)) && SteppedCapsule(FVector(0.f, 0.f, 15.f))
              && SteppedCapsule(FVector(11.4f, 0.f, 15.f)) && !SteppedCapsule(FVector(0.f, 0.f, 0.5f)),
              "a walk up a walkable ramp is not a step; a kerb climbed in a frame is");
    }
    {
        // the weight: a start from standing to 341 cm/s over four frames
        Man M; M.Run(0.5f);
        float Most = 0.f;
        for (int I = 1; I <= 60; ++I)
        {
            M.In.Velocity = FVector(341.f * std::fmin(1.f, I / 4.f), 0.f, 0.f);
            M.Step(1.f / 60.f);
            Most = std::fmin(Most, M.Plan.Pelvis.X);
            if (I == 24) Check(std::fabs(M.Plan.Pelvis.X) < 0.5f, "...and home within 0.4 s");
        }
        std::printf("  a start throws the hips back %.2f cm\n", -Most);
        Check(Most <= -3.f && Most >= -8.f, "the hips carry a start: back 3-8 cm");
        Man C; C.In.Velocity = FVector(341.f, 0.f, 0.f); C.Run(1.f);
        Check(std::fabs(C.Plan.Pelvis.X) < 0.01f, "a steady speed carries no lag");
        Man L; L.Run(0.5f);
        float Big = 0.f;
        L.In.Velocity = FVector(-1032.f, 0.f, 0.f);
        for (int I = 0; I < 30; ++I) { L.Step(1.f / 60.f); Big = std::fmax(Big, std::fabs(L.Plan.Pelvis.X)); }
        Check(Big <= 8.001f, "a launch is held to 8 cm");
        Man F; F.Run(0.5f);
        F.In.Velocity = FVector(-648.f, 0.f, 0.f);
        for (int I = 0; I < 5; ++I) F.Step(0.015f * 0.001f);
        Check(std::fabs(F.Plan.Pelvis.X) < 0.05f, "the freeze holds the hips");
    }
}

static void Stride()
{
    std::printf("STRIDE  (a walk kept to the ground)\n");
    FStrideMeter M; const float Down[2] = { 0.f, 20.f };
    for (int I = 0; I < 20; ++I)
    {
        const float T = I * 1.5f / 60.f;
        const FVector B[2] = { FVector(30.f - 341.f * T, 15.f, 2.4f), FVector(0.f, 0.f, 20.f) };
        MeasureStride(M, 7, T, B, Down);
    }
    Check(Near(M.Speed, 341.f, 0.5f), "the stride meter reads the clip's own 341 cm/s whatever rate it plays at");
    Check(Near(StrideRate(511.f, M, 1.f), 511.f / 341.f, 0.01f) && Near(StrideRate(341.f, M, 1.f), 1.f, 0.01f), "a walk is played at the speed the man moves");
    Check(Near(StrideRate(800.f, M, 1.f), 1.6f, 1e-4f) && Near(StrideRate(60.f, M, 1.f), 0.5f, 1e-4f), "...within half and 1.6 times its own");
    Check(Near(StrideRate(682.f, M, 2.f), 1.f, 0.01f), "a man drawn twice the size walks his own clip at twice the speed");
    FStrideMeter G;
    for (int I = 0; I < 20; ++I) { const FVector B[2] = { FVector(30.f + 0.02f * I, 15.f, 2.4f), FVector(0.f, 0.f, 2.4f) }; const float L[2] = { 0.f, 0.f }; MeasureStride(G, 3, I / 60.f, B, L); }
    Check(StrideRate(300.f, G, 1.f) == 1.f, "a guard keeps its clock");
    Man W; W.In.bBlending = true;
    for (int I = 0; I < 20; ++I) { W.In.ClipTime = I / 60.f; W.In.Foot[0].Ball.X = 33.f - 5.7f * I; W.Step(1.f / 60.f); }
    Check(!W.St.Stride.bValid, "the stride meter waits out a crossfade");
}

// ------------------------------------------------------------------- hands

static std::string Slurp(const char* Path)
{
    std::string S;
    FILE* F = std::fopen(Path, "rb");
    if (!F) return S;
    char B[4096];
    size_t N;
    while ((N = std::fread(B, 1, sizeof B, F)) > 0) S.append(B, N);
    std::fclose(F);
    return S;
}

static void Hands()
{
    std::printf("HANDS  (the striking limb, and when it is drawn)\n");

    // The limb table against the motion table build_motion.py wrote.
    {
        FILE* F = std::fopen("Content/Animation/Saud/DT_SaudMotion.csv", "rb");
        Check(F != nullptr, "DT_SaudMotion.csv found");
        int Rows = 0, Wrong = 0;
        if (F)
        {
            char Line[512];
            if (!std::fgets(Line, sizeof Line, F)) Line[0] = 0;     // header
            while (std::fgets(Line, sizeof Line, F))
            {
                std::vector<std::string> Col;
                std::string Cur;
                for (const char* P = Line; *P; ++P)
                {
                    if (*P == ',') { Col.push_back(Cur); Cur.clear(); }
                    else if (*P != '\n' && *P != '\r') Cur += *P;
                }
                Col.push_back(Cur);
                if (Col.size() < 8 || Col[2].empty()) continue;     // not an attack
                ++Rows;
                char Side = 0;
                const ELimb Limb = StrikingLimb(Col[2].c_str(), Side);
                const std::string& Want = Col[7];
                const bool Ok = (Want == "lead_arm" && Limb == ELimb::Arm && Side == 'l')
                             || (Want == "rear_arm" && Limb == ELimb::Arm && Side == 'r')
                             || (Want == "rear_leg" && Limb == ELimb::Leg && Side == 'r');
                if (!Ok) { ++Wrong; std::printf("  %s: table says %s\n", Col[2].c_str(), Want.c_str()); }
            }
            std::fclose(F);
        }
        std::printf("  %d attack rows in the motion table\n", Rows);
        Check(Rows == 6 && Wrong == 0, "StrikingLimb agrees with DT_SaudMotion's Limb for every attack");
    }
    char S = 'x';
    Check(StrikingLimb("Rage", S) == ELimb::None && S == 0, "an unknown row strikes with nothing");

    // Alpha over the Jab: startup 0.07, active 0.06.
    Check(ContactAlpha(0.f, 0.07f, 0.06f) == 0.f, "nothing at the start of the wind-up");
    Check(ContactAlpha(0.07f, 0.07f, 0.06f) == 1.f, "full on the first active frame");
    Check(Near(ContactAlpha(0.04f, 0.07f, 0.06f), 0.5f), "half at 30 ms before the first active frame");
    Check(Near(ContactAlpha(0.11f, 0.07f, 0.06f), 0.5f) && Near(ContactAlpha(0.40f, 0.18f, 0.26f, ContactLeadIn, true), 1.f),
          "a strike lets go from its first active frame; a multi-hit holds through its live frames");
    Check(ContactAlpha(0.30f, 0.07f, 0.06f) == 0.f, "gone by 100 ms into it");
    float Prev = -1.f; bool Ok = true; bool Falling = false;
    for (int I = 0; I <= 30; ++I)
    {
        const float A = ContactAlpha(I * 0.01f, 0.07f, 0.06f);
        if (Falling && A > Prev + 1e-6f) Ok = false;
        if (A < Prev - 1e-6f) Falling = true;
        Prev = A;
    }
    Check(Ok, "rises once and falls once");
    const float e = 0.001f;
    Check(ContactAlpha(0.01f + e, 0.07f, 0.06f) < 0.005f && ContactAlpha(0.07f - e, 0.07f, 0.06f) > 0.995f,
          "contact eases in: no kink at either end of its ramp");
    Check(ContactAlpha(0.07f + e, 0.07f, 0.06f) > 0.995f && ContactAlpha(0.15f - e, 0.07f, 0.06f) < 0.005f,
          "contact eases out: no kink at either end of its ramp");
    Check(ContactAlpha(0.f, 0.16f, 0.09f, 0.16f, true) == 0.f && Near(ContactAlpha(0.08f, 0.16f, 0.09f, 0.16f, true), 0.5f)
          && ContactAlpha(0.06f, 0.16f, 0.09f, 0.16f, true) > 0.1f && ContactAlpha(0.16f, 0.16f, 0.09f, 0.16f, true) == 1.f
          && ContactAlpha(0.25f, 0.16f, 0.09f, 0.16f, true) == 1.f,
          "a block rises over the striker's whole wind-up, there through every live frame");
    {
        const std::string Csv = Slurp("Content/Data/DT_Attacks.csv");
        int Rows = 0, Bad = 0;
        size_t I = Csv.find('\n');
        while (I != std::string::npos && I + 1 < Csv.size())
        {
            const size_t J = Csv.find('\n', I + 1);
            const std::string Line = Csv.substr(I + 1, (J == std::string::npos ? Csv.size() : J) - I - 1);
            I = J;
            char Name[64] = {0}, Fam[64] = {0};
            float Dmg = 0.f, Su = 0.f, Ac = 0.f, Rc = 0.f;
            if (std::sscanf(Line.c_str(), "%63[^,],%63[^,],%f,%f,%f,%f", Name, Fam, &Dmg, &Su, &Ac, &Rc) != 6) continue;
            ++Rows;
            const bool bMulti = Line.find("true", Line.size() - 6) != std::string::npos;
            if (ContactAlpha(Su + Ac + Rc - 1e-4f, Su, Ac, ContactLeadIn, bMulti) > 0.f) { ++Bad; std::printf("  %s still pulls as it ends\n", Name); }
        }
        Check(Rows == 6 && Bad == 0, "every strike's pull is gone before its recovery ends");
    }
}

/** motion_hits.py's TARGET (bone, offset in Blender metres) and TIP, by attack. */
struct FHitRow { std::string Bone, Tip; float X = 0.f, Y = 0.f, Z = 0.f; };

static std::string DictBody(const std::string& Src, const char* Head)
{
    const size_t A = Src.find(Head);
    if (A == std::string::npos) return "";
    const size_t B = Src.find('}', A);
    return B == std::string::npos ? "" : Src.substr(A + std::strlen(Head), B - A - std::strlen(Head));
}

static bool ReadHitTable(std::map<std::string, FHitRow>& Out)
{
    const std::string Src = Slurp("Tools/blender/motion_hits.py");
    const std::string T = DictBody(Src, "TARGET = {"), P = DictBody(Src, "TIP = {");
    if (T.empty() || P.empty()) return false;
    size_t I = 0;
    while ((I = T.find('"', I)) != std::string::npos)          // "Name": ("bone", (x, y, z), size)
    {
        const size_t J = T.find('"', I + 1);
        const size_t K = T.find("(\"", J), L = T.find('"', K + 2), M = T.find('(', L);
        if (J == std::string::npos || K == std::string::npos || L == std::string::npos || M == std::string::npos) return false;
        FHitRow H;
        H.Bone = T.substr(K + 2, L - K - 2);
        if (std::sscanf(T.c_str() + M + 1, "%f , %f , %f", &H.X, &H.Y, &H.Z) != 3) return false;
        Out[T.substr(I + 1, J - I - 1)] = H;
        I = T.find(')', T.find(')', M) + 1) + 1;
    }
    I = 0;
    while ((I = P.find('"', I)) != std::string::npos)          // "Name": "bone"
    {
        const size_t J = P.find('"', I + 1), K = P.find('"', J + 1), L = P.find('"', K + 1);
        if (L == std::string::npos) return false;
        const std::string Name = P.substr(I + 1, J - I - 1);
        if (!Out.count(Name)) return false;
        Out[Name].Tip = P.substr(K + 1, L - K - 1);
        I = L + 1;
    }
    return true;
}

static void Contact()
{
    std::printf("CONTACT  (the mark on the man, the point that lands, the guard that meets it)\n");

    // ---- the table against motion_hits.py, read from the file
    std::map<std::string, FHitRow> Hits;
    Check(ReadHitTable(Hits) && Hits.size() == 6, "motion_hits.py's TARGET and TIP read, six strikes");
    int BadMark = 0, BadTip = 0, BadCover = 0;
    for (const auto& It : Hits)
    {
        const FStrike K = StrikeOf(It.first.c_str());
        const FHitRow& H = It.second;
        const FVector Want(-H.Y * 100.f, -H.X * 100.f, H.Z * 100.f);   // Blender: facing -Y, +X his left, metres
        const bool BoneOk = (H.Bone == "head" && K.Bone == EMarkBone::Head)
                         || (H.Bone == "spine_02" && K.Bone == EMarkBone::Spine02)
                         || (H.Bone == "spine_03" && K.Bone == EMarkBone::Spine03);
        if (!BoneOk || FVector::Dist(K.Mark, Want) > 0.01f) { ++BadMark; std::printf("  %s: mark off motion_hits\n", It.first.c_str()); }
        const char Sd = H.Tip.empty() ? 0 : H.Tip.back();
        const bool TipOk = K.Side == Sd && (
            (H.Tip.rfind("hand_end_", 0) == 0 && K.Tip == ETip::Knuckles && K.Limb == ELimb::Arm)
         || (H.Tip.rfind("ball_", 0) == 0 && K.Tip == ETip::Ball && K.Limb == ELimb::Leg)
         || (H.Tip.rfind("calf_", 0) == 0 && K.Tip == ETip::Knee && K.Limb == ELimb::Leg));   // the calf's joint is the knee
        if (!TipOk) { ++BadTip; std::printf("  %s: tip off motion_hits (%s)\n", It.first.c_str(), H.Tip.c_str()); }
        if (H.X > 0.01f && CoverSide(K.Side) != 'l') ++BadCover;
        if (H.X < -0.01f && CoverSide(K.Side) != 'r') ++BadCover;
    }
    Check(BadMark == 0, "every strike's mark is motion_hits.py's TARGET, in the engine's frame");
    Check(BadTip == 0, "every strike lands the point motion_hits.py's TIP names, on its side");
    Check(BadCover == 0 && CoverSide('l') == 'r' && CoverSide('r') == 'l' && CoverSide(0) == 0,
          "a blow is met by the arm on the side it lands");
    Check(Near(StrikeOf("Jab").Skin, 2.f) && Near(StrikeOf("Hook").Skin, 2.f) && Near(StrikeOf("Kick").Skin, 2.5f)
          && Near(StrikeOf("Special").Skin, 2.5f) && Near(StrikeOf("Knee").Skin, 5.f),
          "a blow lands its skin on the mark: the joint stops 2 cm short for the knuckles, 2.5 the ball, 5 the knee");
    {
        Check(Near(SkinOf(StrikeOf("Jab"), 1.5f), 3.f, 1e-4f) && Near(SkinOf(StrikeOf("Knee"), 1.48f), 7.4f, 1e-3f),
              "...grown with the man who throws it");
        // the knee: its joint stops its skin short of the mark where the
        // line down his front comes within a thigh and a skin of the hip
        const FVector Hip(0.f, 0.f, 95.f), Knee(20.f, 0.f, 56.f);          // a 43.8 cm thigh
        const FVector Plexus(61.f, 0.f, 125.f), Belt(40.f, 0.f, 95.f);     // 68 cm off, the belt 40
        const FVector K = KneeSwing(Hip, Knee, KneeAim(Hip, Knee, Plexus, Belt, 5.f), 1.f);
        const FVector Landed = ReachableMark(Hip, (float)FVector::Dist(Hip, Knee) + 5.f, Plexus, Belt, (float)Knee.Z);
        Check(Near((float)FVector::Dist(K, Landed), 5.f, 0.05f) && Near((float)FVector::Dist(K, Hip), (float)FVector::Dist(Knee, Hip), 1e-3f),
              "a knee lands its skin on the mark: the joint 5 cm short of it, the thigh its own length");
    }

    // ---- the mark on the man. In Unreal (X forward, Z up) a man facing +X has his left at -Y.
    {
        const FVector Him(0.f, 0.f, 0.f), Head(0.f, 0.f, 160.f), Striker(100.f, 0.f, 0.f), Fwd(1.f, 0.f, 0.f);
        FVector Mk = MarkPoint(Head, Him, Striker, StrikeOf("Hook").Mark, 1.f, Fwd);
        Check(Mk.Y < -1.f && Mk.X > 1.f && Mk.Z < 160.f, "the hook's mark is on his left jaw, in front and under the eye line");
        Mk = MarkPoint(Head, Him, FVector(-100.f, 0.f, 0.f), StrikeOf("Jab").Mark, 1.f, Fwd);
        Check(Mk.X < -5.f, "struck from behind, the mark is on the back of him, not round the far side");
        Mk = MarkPoint(Head, Him, Striker, StrikeOf("Jab").Mark, 1.5f, Fwd);
        Check(Near(FVector::Dist(Mk, Head), 1.5f * std::sqrt(200.f), 0.01f), "the mark grows with the man");
        Check(Near(BodyScale(167.2f * 1.48f), 1.48f, 1e-3f) && Near(BodyScale(167.2f), 1.f, 1e-4f),
              "a man's size is his reference head over Saud's 167.2 cm");
        int Bad = 0;
        const FVector H2(42.f, -20.f, 160.f), Him2(40.f, -20.f, 0.f), St2(140.f, 10.f, 0.f);
        for (int I = 0; I < 72; ++I)
        {
            const float Ang = I * 5.f * Pi / 180.f;
            const FVector A = MarkPoint(H2, Him2, St2, StrikeOf("Hook").Mark, 1.2f, Fwd);
            const FVector B = MarkPoint(Rotate(H2, Ang), Rotate(Him2, Ang), Rotate(St2, Ang), StrikeOf("Hook").Mark, 1.2f, Rotate(Fwd, Ang));
            if (FVector::Dist(Rotate(A, Ang), B) > 1e-2f) ++Bad;
        }
        Check(Bad == 0, "the mark turns with the fight, 72 angles");
    }

    // ---- out of reach: Saud's shoulder at 140 with 67 cm to his knuckles
    {
        const FVector Sh(0.f, 0.f, 140.f);
        FVector T = ReachableMark(Sh, 67.f, FVector(60.f, 0.f, 230.f), FVector(60.f, 0.f, 100.f), 140.f);
        Check(Near(FVector::Dist(T, Sh), 67.f, 0.05f) && Near(T.X, 60.f, 0.01f)
              && Near(T.Z, 140.f + std::sqrt(67.f * 67.f - 60.f * 60.f), 0.05f),
              "a mark out of reach slides down his front to where the limb first reaches");
        T = ReachableMark(Sh, 67.f, FVector(50.f, 10.f, 150.f), FVector(50.f, 10.f, 100.f), 140.f);
        Check(FVector::Dist(T, FVector(50.f, 10.f, 150.f)) < 1e-3f, "a mark in reach is the mark");
        // a kick from the hip at a man 170 cm away: the leg aims at his ribs' height, not his belt
        T = ReachableMark(FVector(8.f, 9.f, 95.f), 105.f, FVector(168.f, 13.f, 138.f), FVector(158.f, 0.f, 95.f), 138.f);
        Check(Near(T.Z, 138.f, 0.5f), "nothing of him in reach: the blow keeps the height the clip throws it at");
    }

    // ---- the swing gate, by degrees off the clip's line
    {
        auto GateAt = [](float Deg, bool bArm)
        {
            const float R = Deg * Pi / 180.f;
            return SwingGate(FVector(0.f, 0.f, 0.f), FVector(100.f, 0.f, 0.f), FVector(100.f * std::cos(R), 100.f * std::sin(R), 0.f), bArm);
        };
        Check(GateAt(0.f, true) > 0.9999f && GateAt(29.9f, true) > 0.9999f && GateAt(55.5f, true) == 0.f
              && GateAt(42.5f, true) > 0.45f && GateAt(42.5f, true) < 0.55f,
              "an arm takes its whole pull within 30 degrees of its line and none past 55");
        Check(GateAt(45.f, false) > 0.9999f && GateAt(59.9f, false) > 0.9999f && GateAt(90.5f, false) == 0.f
              && GateAt(179.f, false) == 0.f && GateAt(75.f, false) > 0.45f && GateAt(75.f, false) < 0.55f,
              "a leg takes its whole pull within 60 degrees and none past 90: never through the body");
        float G = 1.f; G = StepGate(G, 0.f, 1.f / 60.f);
        const float One = G;
        for (int I = 0; I < 3; ++I) G = StepGate(G, 0.f, 1.f / 60.f);
        Check(One > 0.7f && G == 0.f, "the gate moves at most its whole way in 0.06 s");
    {
        FGate G;
        const float First = G.Step(0.f, 1.f / 60.f);       // a man the gate shuts out, on the swing's first frame
        const float Next = G.Step(1.f, 1.f / 60.f);        // then one it lets in
        G.Reset();
        Check(First == 0.f && Next > 0.f && Next < 0.5f && G.Step(0.4f, 1.f / 60.f) == 0.4f,
              "a swing's first frame takes the gate as it stands: no flick toward a man it shuts out");
    }
    }

    // ---- the strike's solve: a lead arm, the elbow under the line, the knuckles at shoulder height
    {
        const FVector R0(0.f, 0.f, 140.f), M0(30.f, 0.f, 128.f), T0(65.f, 0.f, 140.f);
        const float A0 = FVector::Dist(R0, M0), B0 = FVector::Dist(M0, T0);
        const FVector Tg(55.f, 25.f, 150.f);
        FTwoBone St = SolveStrike(R0, M0, T0, Tg, 1.f);
        Check(FVector::Dist(St.End, Tg) < 0.01f && Near(FVector::Dist(R0, St.Mid), A0, 1e-2f) && Near(FVector::Dist(St.Mid, St.End), B0, 1e-2f),
              "a strike in reach puts its tip on the target, each segment its own length");
        St = SolveStrike(R0, M0, T0, Tg, 0.f);
        Check(FVector::Dist(St.Mid, M0) < 1e-3f && FVector::Dist(St.End, T0) < 1e-3f, "at no share, the clip's own limb");
        const float Yaw = 60.f * Pi / 180.f;
        St = SolveStrike(R0, M0, T0, R0 + Rotate(T0 - R0, Yaw), 1.f);
        Check(FVector::Dist(St.Mid, R0 + Rotate(M0 - R0, Yaw)) < 0.05f && FVector::Dist(St.End, R0 + Rotate(T0 - R0, Yaw)) < 0.05f,
              "a strike swung to a target at its own reach turns as one piece");
        St = SolveStrike(R0, M0, T0, R0 + Rotate(T0 - R0, Pi * 0.5f), 0.5f);
        Check(Near(FVector::Dist(St.End, R0), FVector::Dist(T0, R0), 0.05f), "the tip swings on the arc about the root, never in toward it");
        int Bad = 0;
        for (int I = 0; I < 72; ++I)
        {
            const float Ang = I * 5.f * Pi / 180.f;
            const FTwoBone A = SolveStrike(R0, M0, T0, Tg, 0.7f);
            const FTwoBone B = SolveStrike(Rotate(R0, Ang), Rotate(M0, Ang), Rotate(T0, Ang), Rotate(Tg, Ang), 0.7f);
            if (FVector::Dist(Rotate(A.Mid, Ang), B.Mid) > 1e-2f || FVector::Dist(Rotate(A.End, Ang), B.End) > 1e-2f) ++Bad;
        }
        Check(Bad == 0, "the strike turns with the fight, 72 angles");
        // a clip arm at 171 degrees: switched on at a hair of a share it does not move
        const FVector S1(0.f, 0.f, 140.f), E1(33.f, 0.f, 137.4f), T1(66.f, 0.f, 140.f);
        const FTwoBone Z = SolveStrike(S1, E1, T1, FVector(66.f, 20.f, 150.f), 1e-4f);
        Check(FVector::Dist(Z.Mid, E1) < 0.01f && FVector::Dist(Z.End, T1) < 0.05f, "a straight clip arm is left alone at no share");
    }

    // ---- the knee strike lands the knee
    {
        const FVector Hip(0.f, 0.f, 90.f), Knee(30.f, 0.f, 115.f), Plexus(60.f, 10.f, 128.f);
        const FVector K1 = KneeSwing(Hip, Knee, Plexus, 1.f);
        Check(Near(FVector::Dist(K1, Hip), FVector::Dist(Knee, Hip), 1e-2f), "the knee swings on the thigh: a thigh's length from the hip");
        Check(FVector::CrossProduct((K1 - Hip).GetSafeNormal(), (Plexus - Hip).GetSafeNormal()).Size() < 1e-3f
              && FVector::DotProduct(K1 - Hip, Plexus - Hip) > 0.f, "...pointed at the mark");
        Check(FVector::Dist(KneeSwing(Hip, Knee, Plexus, 0.f), Knee) < 1e-3f, "at no share, the clip's knee");
    }

    // ---- the guard meets a blow: his left arm in the Block, the glove at the forehead
    {
        const FVector Up = FVector::UpVector;
        const FVector Sh(0.f, -20.f, 140.f), El(20.f, -22.f, 118.f), Ha(22.f, -12.f, 160.f), Other(22.f, 30.f, 160.f);
        const float A = FVector::Dist(Sh, El), B = FVector::Dist(El, Ha);
        const FVector MeetHigh(25.f, -42.f, 152.f);          // a hook's, out by his left jaw, 30 cm across
        FTwoBone Cv = Cover(Sh, El, Ha, MeetHigh, true, 1.f, Up, Other, 1.f);
        const FVector Moved = Cv.End - Ha;
        Check(Moved.Size() <= 15.01f && Moved.Size() > 14.f && FVector::DotProduct(Moved, MeetHigh - Ha) > 0.f,
              "a guard moves at most a hand's breadth (15 cm) to meet a blow, toward it");
        Check(Near(Cv.End.Z, Ha.Z, 0.01f), "a head blow is met by the glove at the height the clip holds it");
        Check(Near(FVector::Dist(Sh, Cv.Mid), A, 1e-2f) && Near(FVector::Dist(Cv.Mid, Cv.End), B, 1e-2f), "...the arm its own length");
        // a jab down the middle, the other glove 15 cm across: the glove stops a fist's width from it
        const FVector Lg(22.f, -7.5f, 160.f), Rg(22.f, 7.5f, 160.f);
        Cv = Cover(Sh, El, Lg, FVector(25.f, 7.f, 152.f), true, 1.f, Up, Rg, 1.f);
        Check(Flat(Cv.End - Rg) >= 8.99f && Flat(Cv.End - Lg) > 5.f, "a blow down the middle never drives one glove into the other");
        const FVector MeetLow(6.f, -40.f, 118.f);           // a kick's, low in front of his left ribs
        Cv = Cover(Sh, El, Ha, MeetLow, false, 1.f, Up, Other, 1.f);
        Check(FVector::Dist(Cv.End, Ha) < 1e-2f && FVector::Dist(Cv.Mid, MeetLow) < FVector::Dist(El, MeetLow) - 1.f
              && FVector::Dist(Cv.Mid, El) <= 15.01f && Near(FVector::Dist(Sh, Cv.Mid), A, 1e-2f),
              "a body blow is met by the elbow on its circle, the fist kept up");
        Cv = Cover(Sh, El, Ha, MeetLow, false, 0.f, Up, Other, 1.f);
        const FTwoBone Cv2 = Cover(Sh, El, Ha, MeetHigh, true, 0.f, Up, Other, 1.f);
        Check(FVector::Dist(Cv.Mid, El) < 1e-3f && FVector::Dist(Cv2.End, Ha) < 1e-3f, "at no share, the clip's guard");
        const FVector Chin(10.f, 0.f, 150.f), Root(95.f, 15.f, 145.f);
        const FVector G = MeetPoint(Chin, Root, BlockStandOff), Stop = MeetPoint(Chin, Root, BlockStandOff + BlockFaceGap);
        Check(Near(FVector::Dist(G, Chin), 9.f, 0.01f), "the guard meets a blow 9 cm in front of its mark, on its line");
        Check(FVector::Dist(Stop, Chin) >= FVector::Dist(G, Chin) + 5.f
              && FVector::CrossProduct((Stop - Chin).GetSafeNormal(), (Root - Chin).GetSafeNormal()).Size() < 1e-3f,
              "a blocked blow stops in front of the guard, never through it");
        Check(FVector::Dist(MeetPoint(Chin, Root, 500.f), Root) < 1e-3f, "...and never past the striker");
    }

    // ---- the ramps everything rides
    {
        FRamp Rp;
        Rp.Lin = 0.01f; const float Lo = Rp.Value();
        Rp.Lin = 0.99f; const float Hi = Rp.Value();
        Rp.Lin = 0.5f;
        Check(Lo < 0.001f && Hi > 0.999f && Near(Rp.Value(), 0.5f), "a ramp starts and stops at rest");
        FRamp R30, R60, R120;
        for (int I = 0; I < 3; ++I) R30.Step(true, 1.f / 30.f, 0.2f, 0.1f);
        for (int I = 0; I < 6; ++I) R60.Step(true, 1.f / 60.f, 0.2f, 0.1f);
        for (int I = 0; I < 12; ++I) R120.Step(true, 1.f / 120.f, 0.2f, 0.1f);
        Check(Near(R30.Lin, 0.5f, 1e-4f) && Near(R60.Lin, 0.5f, 1e-4f) && Near(R120.Lin, 0.5f, 1e-4f), "a ramp is the same at 30, 60 and 120 Hz");
        for (int I = 0; I < 3; ++I) R30.Step(false, 1.f / 30.f, 0.2f, 0.1f);
        Check(R30.Value() == 0.f, "...and lets go over its own time");
    }

    // ---- the guard fist, carried with the head's yaw about the neck
    {
        const FVector Neck(0.f, 0.f, 152.f), Fist(25.f, -8.f, 150.f), Up = FVector::UpVector;
        FCarry C = Carry(Fist, Neck, Up, 20.f);
        Check(FVector::Dist(C.Fist, Neck + Rotate(Fist - Neck, 20.f * Pi / 180.f)) < 0.01f && Near(C.Share, 1.f),
              "a guard fist is carried with the head's own turn, about the neck");
        C = Carry(Fist, Neck, Up, 70.f);
        const float Whole = FVector::Dist(Neck + Rotate(Fist - Neck, 70.f * Pi / 180.f), Fist);
        Check(Near(FVector::Dist(C.Fist, Fist), 12.f, 0.01f), "a guard fist follows the head at most 12 cm");
        Check(Near(C.Share * Whole, 12.f, 0.01f), "...and its knuckles turn only as far as it was carried");
        Check(FVector::Dist(Carry(Fist, Neck, Up, 0.f).Fist, Fist) < 1e-4f, "no turn, no carry");
    }

    // ---- the box a blow is looked for in
    Check(InBlowBox(FVector(0.f, 0.f, 0.f), FVector(1.f, 0.f, 0.f), FVector(220.f, 0.f, 0.f), 130.f, 80.f)
          && !InBlowBox(FVector(0.f, 0.f, 0.f), FVector(1.f, 0.f, 0.f), FVector(240.f, 0.f, 0.f), 130.f, 80.f),
          "a man 30 cm past a blow's own box is in the box it is looked for in; 50 past is not");

    // ---- one swing's hold on one man
    {
        bool Ok = true;
        for (float Hz : {30.f, 60.f, 144.f})
        {
            FStrikeTrack T; float Best = 0.f, BestT = 1e9f;
            for (int I = 0; I * (1.f / Hz) < 0.26f; ++I)
            {
                const float Clock = I / Hz;
                T.Step(true, 0, Clock, 0.07f, 0.06f, false, true, false, 1.f / Hz);
                if (std::fabs(Clock - 0.07f) < BestT) { BestT = std::fabs(Clock - 0.07f); Best = T.Alpha(); }
            }
            if (Best < 0.98f) Ok = false;
        }
        Check(Ok, "a strike is whole at the frame nearest its first active frame, at 30, 60 and 144 Hz");
        FStrikeTrack T;
        T.Step(true, 0, 1.f / 60.f, 0.07f, 0.06f, false, true, false, 1.f / 60.f);
        for (int I = 0; I < 14; ++I) T.Step(false, 0, 0.f, 0.07f, 0.06f, false, false, false, 1.f / 60.f);
        Check(T.NewSwing(true, 0, 1.f / 60.f), "a swing interrupted on its first frame and thrown again is a new swing");
        FStrikeTrack L; float Clock = 0.f;
        for (; Clock < 0.04f; Clock += 1.f / 60.f) L.Step(true, 0, Clock, 0.10f, 0.07f, false, true, false, 1.f / 60.f);
        bool Gone = false, Back = false;
        for (int I = 0; I < 12; ++I, Clock += 1.f / 60.f)
        {
            L.Step(true, 0, Clock, 0.10f, 0.07f, false, I > 6, I == 0, 1.f / 60.f);
            if (I == 5 && L.Alpha() == 0.f) Gone = true;
            if (I > 6 && L.Alpha() > 0.f) Back = true;
        }
        Check(Gone && !Back, "a man lost before the blow lands is let go, and nobody takes his place");
        FStrikeTrack D; Clock = 0.f;
        for (; Clock < 0.075f; Clock += 1.f / 60.f) D.Step(true, 0, Clock, 0.07f, 0.06f, false, true, false, 1.f / 60.f);
        const float Before = D.Schedule;
        D.Step(true, 0, Clock, 0.07f, 0.06f, false, false, true, 1.f / 60.f);
        Check(D.Hold.Value() == 1.f && D.Alpha() > 0.f && Before > 0.f, "a landed blow keeps its pull when the man is thrown clear");
        Check(!D.FreshMark(), "the mark is held from the first active frame");
        FStrikeTrack K; Clock = 0.f;
        for (; Clock < 0.09f; Clock += 1.f / 60.f) K.Step(true, 1, Clock, 0.10f, 0.07f, false, true, false, 1.f / 60.f);
        K.Step(false, 1, 0.f, 0.10f, 0.07f, false, false, false, 1.f / 60.f);
        const float After1 = K.Alpha();
        K.Step(false, 1, 0.f, 0.10f, 0.07f, false, false, false, 1.f / 60.f);
        K.Step(false, 1, 0.f, 0.10f, 0.07f, false, false, false, 1.f / 60.f);
        Check(After1 > 0.f && K.Alpha() == 0.f, "a swing taken away lets go in 0.05 s");
    }

    // ---- the blow a guard holds
    {
        // a jab 0 to 0.26, a cross (0.10 / 0.07) from 0.28: the guard meets the cross as it lands
        // as the engine does: the blow held while its swing lasts; another taken only when the guard is free
        FBlockTrack B; float AtCross = 0.f; int Held = -1;
        for (int I = 0; I <= 30; ++I)
        {
            const float T = I / 60.f;
            float S = -1.f; int Cur = -1;
            if (T < 0.26f) { S = ContactAlpha(T, 0.07f, 0.06f, 0.07f, true); Cur = 0; }
            else if (T >= 0.28f) { S = ContactAlpha(T - 0.28f, 0.10f, 0.07f, 0.10f, true); Cur = 1; }
            if (Cur >= 0 && Cur == Held) B.Step(true, S, 1.f / 60.f);
            else if (Cur >= 0 && B.Free()) { Held = Cur; B.Take(S); B.Step(true, S, 1.f / 60.f); }
            else B.Step(false, 0.f, 1.f / 60.f);
            if (I == 23) AtCross = B.Alpha();
        }
        std::printf("  the guard at the cross's first active frame: %.3f\n", AtCross);
        Check(AtCross >= 0.99f, "a combo's second blow is met as it lands");
        FBlockTrack C; C.Take(0.f); for (int I = 0; I < 12; ++I) C.Step(true, 1.f, 1.f / 60.f);
        C.Step(false, 0.f, 1.f / 60.f);
        Check(C.Alpha() > 0.5f, "a blow that vanishes is let go of, not dropped");
        for (int I = 0; I < 5; ++I) C.Step(false, 0.f, 1.f / 60.f);
        Check(C.Alpha() == 0.f && C.Free(), "...over 0.08 s, and then the guard is free");
        FBlockTrack M; M.Take(0.f); for (int I = 0; I < 12; ++I) M.Step(true, 0.f, 1.f / 60.f);
        M.Take(0.6f);
        Check(M.Alpha() == 0.f, "a guard caught mid-swing eases in from nothing");
    }
}

// -------------------------------------------------------------------- head

static void Head()
{
    std::printf("HEAD  (yaw to 100, pitch to 30, within 900 cm)\n");
    const FVector Me(0.f, 0.f, 0.f), Eyes(0.f, 0.f, 165.f), F(1.f, 0.f, 0.f);
    float Y = 0.f, P = 0.f;
    LookAngles(Me, Eyes, F, FVector(200.f, 0.f, 0.f), FVector(200.f, 0.f, 165.f), Y, P);
    Check(Near(Y, 0.f) && Near(P, 0.f), "straight ahead: ahead");
    LookAngles(Me, Eyes, F, FVector(100.f, 100.f, 0.f), FVector(100.f, 100.f, 165.f), Y, P);
    Check(Near(Y, 45.f, 0.05f), "a man at +Y of +X: the yaw is + (the way FQuat turns +X to +Y)");
    float Side = 1.f;
    LookAngles(Me, Eyes, F, FVector(-100.f, 10.f, 0.f), FVector(-100.f, 10.f, 165.f), Y, P);
    Check(Near(HoldSide(Y, Side), 100.f, 0.05f), "behind on his +Y side: held at the limit, that side");
    Side = -1.f;
    LookAngles(Me, Eyes, F, FVector(-100.f, -10.f, 0.f), FVector(-100.f, -10.f, 165.f), Y, P);
    Check(Near(HoldSide(Y, Side), -100.f, 0.05f), "behind on his -Y side: held at the limit, that side");
    LookAngles(Me, Eyes, F, FVector(100.f, 0.f, 0.f), FVector(100.f, 0.f, 265.f), Y, P);
    Check(Near(P, 30.f, 0.05f), "45 up is held at 30");
    LookAngles(Me, Eyes, F, FVector(100.f, 0.f, 0.f), FVector(100.f, 0.f, 145.f), Y, P);
    Check(Near(P, -std::atan2(20.f, 100.f) * 180.f / Pi, 0.05f), "a little down is a little down");
    LookAngles(Me, Eyes, F, FVector(100.f, 0.f, 0.f), FVector(5.f, 5.f, 165.f), Y, P);
    Check(Near(Y, 0.f, 1.f), "the yaw is the line between the men's middles, not to his head a hand off my eyes");
    int Bad = 0;
    for (int I = 0; I < 72; ++I)
    {
        const float Ang = I * 5.f * Pi / 180.f;
        const FVector T(60.f, 140.f, 0.f), TE(60.f, 140.f, 190.f);
        float Y0, P0, Y1, P1;
        LookAngles(Me, Eyes, F, T, TE, Y0, P0);
        LookAngles(Me, Eyes, Rotate(F, Ang), Rotate(T, Ang), Rotate(TE, Ang), Y1, P1);
        if (!Near(Y0, Y1, 1e-2f) || !Near(P0, P1, 1e-2f)) ++Bad;
    }
    Check(Bad == 0, "the look turns with the facing, 72 angles");
}

// ------------------------------------------------------------ body and look

static float YawOf(const FVector& V) { return std::atan2(V.Y, V.X) * 180.f / Pi; }
static float PitchOf(const FVector& V) { return std::asin(std::fmax(-1.f, std::fmin(1.f, V.Z / V.Size()))) * 180.f / Pi; }

// The proxy's application, done with RotateAbout (which turns as FQuat
// does): the root about up by the hips' yaw, then each of the five, root
// first, yaw about up and pitch about its axis, every bone above it
// carried along. Where the chest (spine_03) and the face (head) end up.
static void Apply(const FChainTurn& T, const FVector& Forward, const FVector& Up, FVector& Chest, FVector& Face)
{
    FVector Axis[ChainBones];
    PitchAxes(T, Forward, Up, Axis);
    FVector Dir[ChainBones];
    for (int I = 0; I < ChainBones; ++I) Dir[I] = RotateAbout(Forward, Up, T.Hips * Pi / 180.f);
    for (int I = 0; I < ChainBones; ++I)
        for (int J = I; J < ChainBones; ++J)
        {
            Dir[J] = RotateAbout(Dir[J], Up, T.Yaw[I] * Pi / 180.f);
            Dir[J] = RotateAbout(Dir[J], Axis[I], T.Pitch[I] * Pi / 180.f);
        }
    Chest = Dir[2];
    Face = Dir[4];
}

static FTurn Whole() { FTurn S; S.Weight.Lin = 1.f; return S; }

// One fighter's turn over a stretch of frames, the actor's yaw snapped once
// at the start: the visible hips, chest and face, off the NEW facing.
struct FTrace { std::vector<float> Hips, Chest, Face; };
static FTrace Run(float Snap, float LookYaw, bool bStriking, float Hz, float Seconds, FTurn S = Whole())
{
    FTrace Out;
    const int N = (int)(Seconds * Hz + 0.5f);
    for (int I = 0; I < N; ++I)
    {
        TurnStep(S, I == 0 ? Snap : 0.f, LookYaw, 0.f, true, false, bStriking, false, 1.f / Hz);
        const FChainTurn T = ShareTurn(S);
        FVector C, F;
        Apply(T, FVector(1.f, 0.f, 0.f), FVector::UpVector, C, F);
        Out.Hips.push_back(T.Hips);
        Out.Chest.push_back(YawOf(C));
        Out.Face.push_back(YawOf(F));
    }
    return Out;
}

static float MostStep(const std::vector<float>& V, float From)
{
    float Worst = std::fabs(WrapDegrees(V[0] - From));
    for (size_t I = 1; I < V.size(); ++I) Worst = std::fmax(Worst, std::fabs(WrapDegrees(V[I] - V[I - 1])));
    return Worst;
}

static void Body()
{
    std::printf("BODY AND LOOK  (the hips' lag, the chain, the look)\n");

    Check(Near(WrapDegrees(190.f), -170.f) && Near(WrapDegrees(-190.f), 170.f) && Near(WrapDegrees(540.f), 180.f)
          && Near(WrapDegrees(-180.f), 180.f), "a yaw is wrapped to (-180, 180]");
    Check(WrapDegrees(std::numeric_limits<float>::quiet_NaN()) == 0.f && WrapDegrees(std::numeric_limits<float>::infinity()) == 0.f
          && WrapDegrees(-std::numeric_limits<float>::infinity()) == 0.f,
          "a yaw that is no number of turns is none, and does not hang");

    // ---- the hips: they keep their place when the facing snaps, then follow
    {
        FTurn S = Whole();
        TurnStep(S, 90.f, 0.f, 0.f, true, false, false, false, 0.f);
        Check(Near(S.Hips, -90.f), "a facing snapped 90: the hips stay where they were in the world");
        FTurn A = S, B = S;
        TurnStep(A, 0.f, 0.f, 0.f, true, false, false, false, 1.f / 60.f);
        const float First = A.Hips;
        for (int I = 1; I < 30; ++I) TurnStep(A, 0.f, 0.f, 0.f, true, false, false, false, 1.f / 60.f);
        for (int I = 0; I < 15; ++I) TurnStep(B, 0.f, 0.f, 0.f, true, false, false, false, 1.f / 30.f);
        Check(First <= -70.f && std::fabs(A.Hips) < 1.f, "...and come round within half a second, not at once");
        Check(Near(A.Hips, B.Hips, 1.f), "...the same at 30 and 60 Hz");
    }
    {
        const FTrace T = Run(180.f, 0.f, false, 60.f, 0.8f);
        Check(MostStep(T.Hips, 180.f) <= 18.01f && MostStep(T.Chest, 180.f) <= 24.01f && MostStep(T.Face, 180.f) <= 30.01f,
              "no part turns faster than its cap: 18, 24 and 30 degrees a frame at 60 Hz");
        bool Leads = true, Ahead = false;
        for (size_t I = 0; I < T.Hips.size(); ++I)
        {
            const float H = std::fabs(T.Hips[I]), C = std::fabs(WrapDegrees(T.Chest[I])), F = std::fabs(WrapDegrees(T.Face[I]));
            if (C > H + 0.01f || F > C + 0.01f) Leads = false;
            if (H - C > 10.f) Ahead = true;
        }
        Check(Leads && Ahead, "coming round, the face leads the chest and the chest leads the hips");
        float Twist = 0.f;
        for (size_t I = 0; I < T.Hips.size(); ++I) Twist = std::fmax(Twist, std::fabs(WrapDegrees(T.Chest[I] - T.Hips[I])));
        Check(Twist <= 35.01f && Twist > 30.f, "...and the trunk twists over the hips up to 35 degrees, never past");
    }
    {
        // a strike: the jab is live 70 ms after it starts
        const FTrace T = Run(180.f, 0.f, true, 60.f, 0.067f);
        std::printf("  a half turn into a jab, at its first live frame: hips %.1f, face %.1f\n", T.Hips.back(), T.Face.back());
        Check(std::fabs(T.Hips.back()) < 20.f && std::fabs(WrapDegrees(T.Face.back())) < 3.f,
              "a half turn into a jab: by its first live frame the face is on the line and the hips nearly");
        const FTrace U = Run(180.f, 0.f, true, 60.f, 0.3f);
        bool With = true;
        for (size_t I = 0; I < U.Hips.size(); ++I) if (std::fabs(WrapDegrees(U.Chest[I] - U.Hips[I])) > 5.f) With = false;
        Check(With, "in a strike the chest goes with the hips");
        Check(MostStep(U.Hips, 180.f) <= 54.01f && MostStep(U.Face, 180.f) <= 90.01f, "...three times as fast, and no faster");
    }
    {
        bool Ok = true;
        for (float Hz : {60.f, 30.f})
        {
            FTurn S = Whole();
            for (int I = 0; I < (int)(2.f * Hz); ++I) TurnStep(S, 180.f / Hz, 0.f, 0.f, true, false, false, false, 1.f / Hz);
            const FChainTurn T = ShareTurn(S);
            FVector C, F; Apply(T, FVector(1.f, 0.f, 0.f), FVector::UpVector, C, F);
            std::printf("  circling at %.0f Hz: hips %.1f, face %.1f\n", Hz, S.Hips, YawOf(F));
            if (!(S.Hips < -5.f && S.Hips > -15.f && std::fabs(YawOf(F)) < 12.f)) Ok = false;
        }
        Check(Ok, "circling at 180 degrees a second the hips trail 5-15 behind and the face stays within 12, at 30 and 60 Hz");
    }
    {
        FTurn S = Whole(); S.Hips = 120.f; S.Chest = -30.f; S.Head = -90.f;
        TurnStep(S, 0.f, 0.f, 0.f, true, false, false, true, 1.f / 60.f);
        Check(S.Hips == 0.f && S.Chest == 0.f && S.Head == 0.f, "a man put through a door does not spin round after");
        Check(!Teleported(FVector(500.f, -300.f, 0.f), FVector(615.f, -300.f, 0.f)) && !Teleported(FVector(0.f, 0.f, 0.f), FVector(150.f, 0.f, 0.f)),
              "a dash at 10 frames a second is not a teleport");
        Check(Teleported(FVector(500.f, -300.f, 0.f), FVector(500.f, 100.f, 0.f)), "a man moved 4 m in a frame was put there");
    }
    {
        // a stick flick of 175 that settles 30 more on the next frame
        FTurn S = Whole();
        float Actor = 0.f, Prev = 0.f; bool Fwd = true;
        for (int I = 0; I < 40; ++I)
        {
            const float Turned = I == 0 ? 175.f : I == 1 ? 30.f : 0.f;
            Actor += Turned;
            TurnStep(S, Turned, 0.f, 0.f, true, false, false, false, 1.f / 60.f);
            const float World = Actor + S.Hips;
            if (World < Prev - 0.01f) Fwd = false;
            Prev = World;
        }
        Check(Fwd, "a second snap the same way does not reverse the turn");
    }

    // ---- the weight
    {
        bool Ok = true;
        for (float Hz : {60.f, 120.f})
        {
            FTurn A;
            for (int I = 0; I < (int)std::lround(0.15f * Hz); ++I) TurnStep(A, 0.f, 0.f, 0.f, true, false, false, false, 1.f / Hz);
            const float Half = A.Weight.Value();
            for (int I = 0; I < (int)std::lround(0.15f * Hz); ++I) TurnStep(A, 0.f, 0.f, 0.f, true, false, false, false, 1.f / Hz);
            if (!Near(Half, 0.5f, 0.01f) || !Near(A.Weight.Value(), 1.f, 1e-3f)) Ok = false;
        }
        Check(Ok, "the look's weight builds frame on frame: half at 0.15 s, whole at 0.3, at 60 Hz as at 120");
        FTurn D = Whole();
        for (int I = 0; I < 4; ++I) TurnStep(D, 0.f, 0.f, 0.f, false, true, false, false, 1.f / 60.f);
        Check(D.Weight.Value() == 0.f, "a man knocked down lets go of the look in 0.06 s");
    }
    {
        FTurn S; S.Hips = 40.f; S.Chest = -30.f; S.Head = -60.f; S.Pitch = 10.f;
        const FChainTurn T = ShareTurn(S);
        float Sum = 0.f;
        for (int I = 0; I < ChainBones; ++I) Sum += std::fabs(T.Yaw[I]) + std::fabs(T.Pitch[I]);
        Check(Sum == 0.f, "the look off: the clip's own chest and head");
        Check(Near(T.Hips, 40.f), "...and the hips' lag still shown, so nothing snaps");
    }
    {
        FTurn S = Whole(); S.Hips = 60.f;
        for (int I = 0; I < 60; ++I) TurnStep(S, 0.f, 0.f, 0.f, false, true, false, false, 1.f / 60.f);
        Check(Near(S.Hips, 60.f), "on the floor the lag holds");
        // a man 90 degrees to the side; a blow lands 6 frames into the turn
        FTurn R = Whole(); float Prev = 0.f; bool Ok = true;
        for (int I = 0; I < 30; ++I)
        {
            TurnStep(R, I == 0 ? 0.f : 0.f, 90.f, 0.f, I < 6, false, false, false, 1.f / 60.f);
            FVector C, F; Apply(ShareTurn(R), FVector(1.f, 0.f, 0.f), FVector::UpVector, C, F);
            const float Off = std::fabs(YawOf(F));
            if (I > 6 && Off > Prev + 1e-3f) Ok = false;
            Prev = Off;
        }
        Check(Ok, "a blow mid-turn never turns the face further from the facing");
    }

    // ---- the chain: the face on the look, the chest a share, the limits
    {
        FTurn S = Whole();
        for (int I = 0; I < 120; ++I) TurnStep(S, 0.f, 70.f, 0.f, true, false, false, false, 1.f / 60.f);
        const FChainTurn T = ShareTurn(S);
        FVector C, F; Apply(T, FVector(1.f, 0.f, 0.f), FVector::UpVector, C, F);
        Check(Near(YawOf(F), 70.f, 0.2f), "a man 70 degrees to the side: the face ends on him");
        Check(YawOf(C) > 15.f && YawOf(C) < 35.f, "...the chest turns toward him too, a share, not the whole");
        Check(Near(T.Hips, 0.f, 0.01f), "...and the hips stay on the facing");
    }
    {
        int Bad = 0;
        for (int Look = -100; Look <= 100; Look += 5)
            for (int Hips = -180; Hips <= 180; Hips += 15)
                for (int Twist = -150; Twist <= 150; Twist += 50)
                {
                    FTurn S = Whole(); S.Hips = (float)Hips; S.Chest = (float)Twist; S.Head = (float)(Look - Hips);
                    const FChainTurn T = ShareTurn(S);
                    for (int I = 0; I < 3; ++I) if (std::fabs(T.Yaw[I]) > 16.f) ++Bad;
                    for (int I = 3; I < 5; ++I) if (std::fabs(T.Yaw[I]) > 50.f) ++Bad;
                    if (std::fabs(T.Yaw[0] + T.Yaw[1] + T.Yaw[2]) > 35.01f) ++Bad;
                    if (std::fabs(T.Yaw[3] + T.Yaw[4]) > 75.01f) ++Bad;
                }
        Check(Bad == 0, "no trunk bone turns over 16 degrees nor neck bone over 50; the trunk 35 at most, the neck 75");
    }
    {
        float Yaw = 0.f, Pitch = 0.f;
        LookAngles(FVector(0.f, 0.f, 0.f), FVector(0.f, 0.f, 160.f), FVector(1.f, 0.f, 0.f), FVector(150.f, 0.f, 0.f), FVector(150.f, 0.f, 260.f), Yaw, Pitch);
        Check(Near(Pitch, 30.f, 0.05f) && Near(Yaw, 0.f, 0.05f), "a man a metre taller at 150 cm: the face up 30, no more");
        FTurn S = Whole();
        for (int I = 0; I < 120; ++I) TurnStep(S, 0.f, Yaw, Pitch, true, false, false, false, 1.f / 60.f);
        const FChainTurn T = ShareTurn(S);
        FVector C, F; Apply(T, FVector(1.f, 0.f, 0.f), FVector::UpVector, C, F);
        Check(Near(PitchOf(F), 30.f, 0.3f), "...the face ends up 30");
        Check(PitchOf(C) > 0.5f && PitchOf(C) < 6.f, "...the chest a little, the neck and head the rest");
    }
    {
        FTurn S = Whole();
        for (int I = 0; I < 120; ++I) TurnStep(S, 0.f, 100.f, 0.f, true, false, false, false, 1.f / 60.f);
        bool Front = true;
        for (int I = 0; I < 120; ++I)
        {
            TurnStep(S, 0.f, -100.f, 0.f, true, false, false, false, 1.f / 60.f);
            if (std::fabs(S.Hips + S.Head) > 100.5f) Front = false;
        }
        Check(Front, "a look swung from one side to the other goes round the front, never behind");
    }
    {
        // a man straight behind, swaying a centimetre either side
        FTurn S = Whole(); float Prev = 0.f; bool Ok = true; float Sign = 0.f;
        for (int I = 0; I < 40; ++I)
        {
            TurnStep(S, 0.f, (I % 2) ? 179.f : -179.f, 0.f, true, false, false, false, 1.f / 60.f);
            FVector C, F; Apply(ShareTurn(S), FVector(1.f, 0.f, 0.f), FVector::UpVector, C, F);
            const float Face = YawOf(F);
            if (I > 20 && std::fabs(Face - Prev) > 1.f) Ok = false;
            if (I > 3) { if (Sign == 0.f) Sign = Face > 0.f ? 1.f : -1.f; else if (Face * Sign < 0.f) Ok = false; }
            Prev = Face;
        }
        Check(Ok, "a man straight behind: the face keeps one shoulder");
        float Side = 1.f;
        const float Held = HoldSide(-120.f, Side);
        const float Then = HoldSide(-99.f, Side);
        Check(Near(Held, 100.f) && Near(Then, -99.f) && Side < 0.f, "...and changes it when he comes within the limit on the other side");
    }
    {
        int Bad = 0;
        for (int I = 0; I < 72; ++I)
        {
            const float A = I * 5.f * Pi / 180.f;
            const FVector Fwd(std::cos(A), std::sin(A), 0.f);
            FTurn S = Whole(); S.Hips = 20.f; S.Chest = -10.f; S.Head = 30.f; S.Pitch = 12.f;
            const FChainTurn T = ShareTurn(S);
            FVector C, F; Apply(T, Fwd, FVector::UpVector, C, F);
            if (!Near(WrapDegrees(YawOf(F) - I * 5.f), 50.f, 0.2f) || !Near(PitchOf(F), 12.f, 0.2f)) ++Bad;
            if (!Near(WrapDegrees(YawOf(C) - I * 5.f), 10.f, 0.2f)) ++Bad;
        }
        Check(Bad == 0, "the chain turns with the facing, 72 angles: chest at hips + twist, face at hips + turn, pitch kept");
    }

    // ---- who he looks at
    {
        Check(Threatens(0.02f, 0.07f, 0.06f) && Threatens(0.10f, 0.07f, 0.06f), "a strike in its wind-up or live threatens");
        Check(!Threatens(0.14f, 0.07f, 0.06f), "a man in his recovery is no threat");
        const FVector Me(0.f, 0.f, 0.f), F(1.f, 0.f, 0.f);
        FLookCandidate C[3];
        C[0].Centre = FVector(150.f, 0.f, 0.f);
        C[1].Centre = FVector(0.f, 300.f, 0.f); C[1].bThreat = true;
        Check(ChooseLook(C, 2, Me, F) == 1, "a man swinging at me takes the look from a nearer man");
        C[0].bVictim = true;
        Check(ChooseLook(C, 2, Me, F) == 0, "my own victim keeps the look from a man swinging at me");
        C[0].bVictim = false; C[1].bThreat = false; C[1].bVictim = true;
        Check(ChooseLook(C, 2, Me, F) == 1, "the man my strike is drawn to takes it from a nearer bystander");
        C[1].bVictim = false;
        C[0].Centre = FVector(200.f, 0.f, 0.f);
        C[1].Centre = FVector(-150.f, 0.f, 0.f);
        Check(ChooseLook(C, 2, Me, F) == 0, "nobody swinging: a man behind counts double the one in front");
        C[0].Centre = FVector(1000.f, 0.f, 0.f);
        Check(ChooseLook(C, 1, Me, F) == -1, "nobody in reach: nobody");
        int Cur = -1, Flicks = 0;
        for (int I = 0; I < 40; ++I)
        {
            const float E = (I % 2) ? 1.f : -1.f;
            C[0].Centre = FVector(200.f + E, 60.f, 0.f);
            C[1].Centre = FVector(200.f - E, -60.f, 0.f);
            C[0].bCurrent = Cur == 0; C[1].bCurrent = Cur == 1;
            const int P = ChooseLook(C, 2, Me, F);
            if (Cur >= 0 && P != Cur) ++Flicks;
            Cur = P;
        }
        Check(Cur >= 0 && Flicks == 0, "two men a hair apart trading places: the look never flicks");
        C[0].Centre = FVector(200.f, 60.f, 0.f); C[0].bCurrent = true;
        C[1].Centre = FVector(130.f, -40.f, 0.f); C[1].bCurrent = false;
        Check(ChooseLook(C, 2, Me, F) == 1, "...but a man a third nearer takes it");
        // a threat whose box's edge flickers across me keeps the look while his swing lasts
        FLookCandidate D[2];
        D[0].Centre = FVector(120.f, 0.f, 0.f);
        D[1].Centre = FVector(0.f, 250.f, 0.f);
        int Was = -1; Flicks = 0;
        for (int I = 0; I < 40; ++I)
        {
            D[1].bThreat = (I % 2) == 0;
            D[0].bCurrent = Was == 0; D[1].bCurrent = Was == 1;
            D[1].bWasThreat = Was == 1;
            const int P = ChooseLook(D, 2, Me, F);
            if (I > 0 && P != Was) ++Flicks;
            Was = P;
        }
        Check(Was == 1 && Flicks == 0, "a man swinging at me keeps the look though his box's edge flickers");
        int BadT = 0;
        const FVector Off(500.f, -300.f, 0.f);
        for (int I = 0; I < 72; ++I)
        {
            const float A = I * 5.f * Pi / 180.f;
            FLookCandidate R[2];
            R[0].Centre = Rotate(FVector(150.f, 0.f, 0.f), A) + Off;
            R[1].Centre = Rotate(FVector(0.f, 300.f, 0.f), A) + Off; R[1].bThreat = true;
            if (ChooseLook(R, 2, Me + Off, Rotate(F, A)) != 1) ++BadT;
            R[1].bThreat = false; R[1].Centre = Rotate(FVector(-150.f, 0.f, 0.f), A) + Off;
            R[0].Centre = Rotate(FVector(200.f, 0.f, 0.f), A) + Off;
            if (ChooseLook(R, 2, Me + Off, Rotate(F, A)) != 0) ++BadT;
            R[0].Centre = Rotate(FVector(200.f, 60.f, 0.f), A) + Off; R[0].bCurrent = true;
            R[1].Centre = Rotate(FVector(130.f, -40.f, 0.f), A) + Off;
            if (ChooseLook(R, 2, Me + Off, Rotate(F, A)) != 1) ++BadT;
        }
        Check(BadT == 0, "the choice turns and moves with the fight, 72 angles, 5 m off the origin");
    }
}

// ------------------------------------------------------------- crossfade

static float Sum(const FCrossfade& C) { float S = 0.f; for (int I = 0; I < C.Num; ++I) S += C.Layers[I].Weight; return S; }
static float WeightOf(const FCrossfade& C, int Clip) { float S = 0.f; for (int I = 0; I < C.Num; ++I) if (C.Layers[I].Clip == Clip) S += C.Layers[I].Weight; return S; }
static const FLayer* Find(const FCrossfade& C, int Clip) { for (int I = 0; I < C.Num; ++I) if (C.Layers[I].Clip == Clip) return &C.Layers[I]; return nullptr; }

static void Crossfade()
{
    std::printf("CROSSFADE  (clips give way to each other)\n");
    const float Dt = 1.f / 60.f;
    enum { Guard = 0, Walk = 1, WalkL = 2, Jab = 3, Hit = 4, Down = 5 };

    FCrossfade C;
    C.Play(Guard, 2.618f, true, false, 0.2f, false);
    C.Advance(Dt);
    Check(C.Num == 1 && Near(C.Layers[0].Weight, 1.f), "the first clip is on at once, alone");
    for (int I = 0; I < 30; ++I) C.Advance(Dt);
    C.Play(Walk, 0.571f, true, false, 0.2f, false);
    Check(Near(WeightOf(C, Guard), 1.f, 1e-6f) && Near(WeightOf(C, Walk), 0.f, 1e-6f), "a cut moves no weight at the instant it starts");
    C.Advance(0.002f);
    Check(WeightOf(C, Walk) < 0.001f, "the incoming clip eases in, with no speed at the start");
    for (int I = 0; I < 98; ++I) C.Advance(0.196f / 98.f);
    Check(WeightOf(C, Walk) > 0.999f && WeightOf(C, Walk) < 1.f, "...and eases out, with no speed at the end");
    C.Advance(0.01f);
    Check(C.Num == 1 && Near(WeightOf(C, Walk), 1.f, 1e-6f), "the cut over, the old clip is gone and the new one whole");
    {
        FCrossfade X;
        X.Play(Jab, 0.26f, false, false, 0.f, false);
        for (int I = 0; I < 12; ++I) X.Advance(Dt);
        const float T0 = X.Layers[0].Time;
        X.Play(Guard, 2.618f, true, false, 0.2f, false);
        X.Advance(Dt);
        const FLayer* J = Find(X, Jab);
        Check(J && Near(J->Time, T0 + Dt, 1e-5f), "the outgoing strike plays on under the guard at its own time");
        for (int I = 0; I < 6; ++I) X.Advance(Dt);
        J = Find(X, Jab);
        Check(J && Near(J->Time, 0.26f, 1e-5f), "...and holds its last frame when it runs out");
        FCrossfade Y;
        Y.Play(Guard, 2.618f, true, false, 0.f, false);
        for (int I = 0; I < 200; ++I) Y.Advance(Dt);
        const float G0 = Y.Layers[0].Time;
        Y.Play(Jab, 0.26f, false, false, 0.05f, false);
        Y.Advance(Dt);
        const FLayer* G = Find(Y, Guard);
        Check(G && Near(G->Time, std::fmod(G0 + Dt, 2.618f), 1e-4f), "an outgoing loop runs on");
        FCrossfade Z;
        Z.Play(Walk, 0.571f, true, false, 0.f, false);
        Z.Play(Guard, 2.618f, true, false, 0.2f, false);
        Z.Advance(Dt, 1.5f);
        Check(Near(Z.Layers[0].Time, 1.5f * Dt, 1e-6f) && Near(Find(Z, Walk)->Time, Dt, 1e-6f), "only the newest clip's clock runs at the stride's rate");
    }
    {
        FCrossfade X;
        const int S0 = X.Serial;
        X.Play(Guard, 2.618f, true, false, 0.f, false);
        const int S1 = X.Serial;
        X.Play(Guard, 2.618f, true, false, 0.f, false);
        const int S2 = X.Serial;
        X.Play(Guard, 2.618f, true, true, 0.f, false);
        Check(S1 != S0 && S2 == S1 && X.Serial != S2, "a new or restarted clip moves the serial; one left alone does not");
    }
    {
        FCrossfade X;
        unsigned Seed = 12345u;
        auto Rand = [&Seed]() { Seed = Seed * 1664525u + 1013904223u; return (Seed >> 8) & 0xFFFF; };
        float Worst = 0.f;
        for (int I = 0; I < 20000; ++I)
        {
            if (Rand() % 4 == 0)
            {
                const int Clip = Rand() % 6;
                X.Play(Clip, 0.3f + 0.1f * Clip, Clip < 3, Rand() % 5 == 0, 0.02f * (Rand() % 10), Rand() % 2 == 0);
            }
            X.Advance(Dt * (Rand() % 3));
            Worst = std::fmax(Worst, std::fabs(Sum(X) - 1.f));
            for (int K = 0; K < X.Num; ++K) if (X.Layers[K].Weight < -1e-6f || X.Layers[K].Weight > 1.f + 1e-6f) Worst = 1.f;
        }
        Check(Worst < 1e-4f, "the weights always sum to one, each between 0 and 1");
    }
    {
        FCrossfade X;
        X.Play(Guard, 2.618f, true, false, 0.f, false);
        X.Advance(Dt);
        X.Play(Walk, 0.571f, true, false, 0.2f, false);
        for (int I = 0; I < 6; ++I) X.Advance(Dt);
        const float G = WeightOf(X, Guard), W = WeightOf(X, Walk);
        X.Play(Jab, 0.26f, false, false, 0.05f, false);
        X.Advance(1e-4f);
        Check(std::fabs(WeightOf(X, Guard) - G) < 1e-3f && std::fabs(WeightOf(X, Walk) - W) < 1e-3f && WeightOf(X, Jab) < 1e-3f,
              "a cut started mid-cut takes every clip on from the weight it had");
    }
    {
        FCrossfade X;
        X.Play(Walk, 0.571f, true, false, 0.f, false);
        for (int I = 0; I < 10; ++I) X.Advance(Dt);
        X.Play(WalkL, 0.571f, true, false, 0.15f, true);
        for (int I = 0; I < 3; ++I) X.Advance(Dt);
        const float W = WeightOf(X, Walk), T = Find(X, Walk)->Time;
        X.Play(Walk, 0.571f, true, false, 0.15f, true);
        Check(X.Num == 2 && Near(WeightOf(X, Walk), W, 1e-6f) && Near(Find(X, Walk)->Time, T, 1e-6f),
              "a clip asked for again mid-cut comes back from its own weight and time, not from nothing");
    }
    {
        FCrossfade X;
        X.Play(Walk, 0.571f, true, false, 0.f, false);
        for (int I = 0; I < 13; ++I) X.Advance(Dt);
        const float Phase = X.Layers[0].Time / 0.571f;
        X.Play(WalkL, 0.571f, true, false, 0.15f, true);
        Check(Near(X.Layers[0].Time / 0.571f, Phase, 1e-5f), "a walk into a walk starts at the same share of the stride");
        X.Play(Jab, 0.26f, false, false, 0.05f, true);
        Check(Near(X.Layers[0].Time, 0.f), "a one-shot always starts on its first frame");
    }
    {
        FCrossfade X;
        X.Play(Hit, 0.22f, false, false, 0.f, false);
        for (int I = 0; I < 6; ++I) X.Advance(Dt);
        X.Play(Guard, 2.618f, true, false, 0.2f, false);
        X.Advance(Dt);
        X.Play(Hit, 0.22f, false, true, 0.03f, false);
        Check(X.Num == 3 && X.Layers[0].Clip == Hit && Near(X.Layers[0].Time, 0.f) && Near(X.Layers[0].Weight, 0.f),
              "a second hit while the first still fades starts a fresh one from its first frame");
    }
    {
        FCrossfade X; int MaxNum = 0;
        unsigned Seed = 99u;
        auto Rand = [&Seed]() { Seed = Seed * 1664525u + 1013904223u; return (Seed >> 8) & 0xFFFF; };
        for (int I = 0; I < 600; ++I)
        {
            const int Clip = Rand() % 3;
            X.Play(Clip, Clip == Guard ? 2.618f : 0.571f, true, false, Clip == Guard ? 0.2f : 0.15f, Clip != Guard);
            X.Advance(Dt);
            if (X.Num > MaxNum) MaxNum = X.Num;
        }
        Check(MaxNum <= 3, "three clips flicking every frame never need a fourth layer");
    }
    {
        FCrossfade X;
        X.Play(0, 1.f, false, false, 0.f, false);
        for (int Clip = 1; Clip <= 4; ++Clip) { X.Play(Clip, 1.f, false, false, 0.5f, false); X.Advance(0.05f); }
        float Min = 2.f; int MinClip = -1;
        for (int I = 0; I < X.Num; ++I) if (X.Layers[I].Weight < Min) { Min = X.Layers[I].Weight; MinClip = X.Layers[I].Clip; }
        X.Play(5, 1.f, false, false, 0.5f, false);
        Check(X.Num == MaxLayers && !Find(X, MinClip) && Near(Sum(X), 1.f, 1e-5f), "a fifth clip inside one cut drops the lightest");
    }
    {
        FCrossfade X;
        X.Play(0, 2.f, true, false, 0.f, false); X.Advance(Dt);
        X.Play(1, 2.f, true, false, 0.3f, false); X.Advance(0.1f);
        X.Play(2, 2.f, true, false, 0.3f, false); X.Advance(0.05f);
        X.Play(3, 2.f, true, false, 0.3f, false); X.Advance(0.02f);
        const float Value[4] = { 10.f, -4.f, 7.f, 1.f };
        float Want = 0.f; for (int I = 0; I < X.Num; ++I) Want += X.Layers[I].Weight * Value[X.Layers[I].Clip];
        float Mix = Value[X.Layers[X.Num - 1].Clip], Under = X.Layers[X.Num - 1].Weight;
        for (int I = X.Num - 2; I >= 0; --I)
        {
            const float Share = FoldShare(Under, X.Layers[I].Weight);
            Mix = Value[X.Layers[I].Clip] * Share + Mix * (1.f - Share);
            Under += X.Layers[I].Weight;
        }
        Check(X.Num == 4 && Near(Mix, Want, 1e-4f), "the proxy's fold gives every clip exactly its weight");
    }
    {
        FCrossfade X;
        X.Play(Guard, 2.618f, true, false, 0.f, false);
        X.Advance(Dt);
        X.Play(Hit, 0.34f, false, false, 0.03f, false);
        for (int I = 0; I < 5; ++I) X.Advance(0.015f * 0.001f);
        Check(WeightOf(X, Hit) < 0.001f && X.Layers[0].Time < 1e-4f, "a 75 ms freeze holds a cut and its clips");
        (void)Down;
    }
    {
        FEase E; E.X = 1.f;
        E.To(0.f, 40.f, 0.f);
        Check(E.X == 1.f && E.V == 0.f, "the freeze holds a spring where it is");
        FEase A, B; A.X = B.X = 1.f;
        for (int I = 0; I < 18; ++I) A.To(0.f, 14.f, 1.f / 60.f);
        for (int I = 0; I < 9; ++I) B.To(0.f, 14.f, 1.f / 30.f);
        Check(Near(A.X, B.X, 1e-4f) && A.X > 0.f, "a spring lands in the same place at 30 and 60 Hz, never past");
    }
}

// ------------------------------------------------------------------ plants

/** One CSV line into fields, quotes honoured (DT_Fighters' Moves column). */
static std::vector<std::string> CsvFields(const std::string& Line)
{
    std::vector<std::string> Out(1);
    bool bQuoted = false;
    for (size_t I = 0; I < Line.size(); ++I)
    {
        const char C = Line[I];
        if (C == '"') { if (bQuoted && I + 1 < Line.size() && Line[I + 1] == '"') { Out.back() += '"'; ++I; } else bQuoted = !bQuoted; }
        else if (C == ',' && !bQuoted) Out.emplace_back();
        else if (C != '\r' && C != '\n') Out.back() += C;
    }
    return Out;
}

/** A CSV as rows of name -> field. */
static std::vector<std::map<std::string, std::string>> ReadCsv(const char* Path)
{
    std::vector<std::map<std::string, std::string>> Rows;
    const std::string All = Slurp(Path);
    std::vector<std::string> Head;
    size_t At = 0;
    while (At < All.size())
    {
        size_t End = All.find('\n', At);
        if (End == std::string::npos) End = All.size();
        const std::string Line = All.substr(At, End - At);
        At = End + 1;
        if (Line.empty() || Line == "\r") continue;
        const std::vector<std::string> F = CsvFields(Line);
        if (Head.empty()) { Head = F; continue; }
        std::map<std::string, std::string> R;
        for (size_t I = 0; I < Head.size() && I < F.size(); ++I) R[Head[I]] = F[I];
        Rows.push_back(R);
    }
    return Rows;
}

/** How many runs of down (or of air) a foot's frames make, round the loop. */
static int Runs(const char* Foot, int N, bool bDown)
{
    int R = 0;
    for (int I = 0; I < N; ++I)
    {
        const bool Here = (Foot[I] != '.') == bDown, Before = (Foot[(I + N - 1) % N] != '.') == bDown;
        if (Here && !Before) ++R;
    }
    return R;
}

/** The longest run of down (or of air) round the loop, in frames. */
static int Longest(const char* Foot, int N, bool bDown)
{
    int Best = 0;
    for (int I = 0; I < N; ++I)
    {
        int L = 0;
        while (L < N && ((Foot[(I + L) % N] != '.') == bDown)) ++L;
        Best = L > Best ? L : Best;
    }
    return Best;
}

/** The middle of the one run of down round the loop, as a share of it. */
static float MiddleOfDown(const char* Foot, int N)
{
    int Start = -1;
    for (int I = 0; I < N; ++I) if (Foot[I] != '.' && Foot[(I + N - 1) % N] == '.') { Start = I; break; }
    if (Start < 0) return 0.f;
    int L = 0;
    while (L < N && Foot[(Start + L) % N] != '.') ++L;
    return std::fmod((Start + 0.5f * (L - 1)) / N, 1.f);
}

static bool EndsWith(const std::string& S, const char* Tail)
{
    const size_t T = std::strlen(Tail);
    return S.size() >= T && S.compare(S.size() - T, T, Tail) == 0;
}

static void Plants()
{
    std::printf("PLANTS  (every clip's feet on the floor, measured from the clips: SaudPlants.h)\n");

    // ---- the table is every clip, frame for frame, and sorted for Find
    const char* Manifests[] = { "Content/Animation/Saud/DT_SaudMotion.csv", "Content/Animation/Street/DT_StreetMotion.csv",
                                "Content/Animation/Bosses/DT_BossMotion.csv" };
    std::vector<std::map<std::string, std::string>> Clips;
    for (const char* M : Manifests) { const auto R = ReadCsv(M); Clips.insert(Clips.end(), R.begin(), R.end()); }
    int Missing = 0, WrongFrames = 0;
    for (const auto& R : Clips)
    {
        const SaudPlants::FClip* P = SaudPlants::Find(R.at("Name").c_str());
        if (!P) { ++Missing; std::printf("  %s: not measured\n", R.at("Name").c_str()); continue; }
        const int N = std::atoi(R.at("Frames").c_str());
        if (P->Frames != N || (int)std::strlen(P->Foot[0]) != N || (int)std::strlen(P->Foot[1]) != N) ++WrongFrames;
    }
    std::printf("  %d clips in the manifests, %d measured\n", (int)Clips.size(), SaudPlants::NumClips);
    Check(Clips.size() == 197 && (int)Clips.size() == SaudPlants::NumClips && Missing == 0 && WrongFrames == 0,
          "every clip in Content/Animation is measured, frame for frame");
    bool bSorted = true;
    for (int I = 1; I < SaudPlants::NumClips; ++I) bSorted = bSorted && std::strcmp(SaudPlants::Clips[I - 1].Name, SaudPlants::Clips[I].Name) < 0;
    int Found = 0;
    for (int I = 0; I < SaudPlants::NumClips; ++I) Found += SaudPlants::Find(SaudPlants::Clips[I].Name) == &SaudPlants::Clips[I];
    Check(bSorted && Found == SaudPlants::NumClips && !SaudPlants::Find("A_Saud_Moonwalk"), "...and every one is found by its name");

    // ---- what the measurements say, held to what the clips are
    int Guards = 0, BadGuards = 0, Walks = 0, BadWalks = 0, Legs = 0, BadLegs = 0, Punches = 0, BadPunches = 0, SideWalks = 0;
    float SideApart = 0.f;
    float ShortestSwing = 1e9f, SlowestWalk = 1e9f, FastestStill = 0.f;
    for (const auto& R : Clips)
    {
        const std::string& Name = R.at("Name");
        const SaudPlants::FClip* P = SaudPlants::Find(Name.c_str());
        if (!P) continue;
        const int N = P->Frames;
        const bool bLoop = R.at("bLoop") == "true";
        if (EndsWith(Name, "_Guard") || EndsWith(Name, "_Block"))
        {
            ++Guards;
            if (std::strchr(P->Foot[0], '.') || std::strchr(P->Foot[1], '.')) { ++BadGuards; std::printf("  %s: a foot leaves the floor\n", Name.c_str()); }
        }
        if (Name.find("_Walk_") != std::string::npos)
        {
            ++Walks;
            const bool bOnce = Runs(P->Foot[0], N, true) == 1 && Runs(P->Foot[1], N, true) == 1;
            const float Apart = std::fabs(MiddleOfDown(P->Foot[0], N) - MiddleOfDown(P->Foot[1], N));
            const float Half = std::fmin(Apart, 1.f - Apart);
            // the side walks hop: both feet down together, then up together
            // (the clips' own gait, measured and left as it is -- CLAUDE.md)
            const bool bSide = Name.find("_Walk_Left") != std::string::npos || Name.find("_Walk_Right") != std::string::npos;
            if (bSide) { ++SideWalks; SideApart = std::fmax(SideApart, Half); }
            else if (!bOnce || Half < 0.30f) { ++BadWalks; std::printf("  %s: the feet do not take turns (%.2f of a cycle apart)\n", Name.c_str(), Half); }
            for (int S = 0; S < 2; ++S) ShortestSwing = std::fmin(ShortestSwing, Longest(P->Foot[S], N, false) / SaudPlants::Fps);
            SlowestWalk = std::fmin(SlowestWalk, P->Stride);
        }
        else if (bLoop) FastestStill = std::fmax(FastestStill, P->Stride);
        const std::string& Move = R.at("Attack");
        const int Contact = std::atoi(R.at("ContactFrame").c_str());
        if ((Move == "Kick" || Move == "Knee" || Move == "Special") && Contact >= 0 && Contact < N)
        {
            ++Legs;
            if (P->Foot[1][Contact] != '.' || std::strchr(P->Foot[0], '.')) { ++BadLegs; std::printf("  %s: the strike's leg is not up at contact, or the other leaves the floor\n", Name.c_str()); }
        }
        if ((Move == "Jab" || Move == "Cross" || Move == "Hook") && Contact >= 0 && Contact < N)
        {
            ++Punches;
            if (P->Foot[0][Contact] == '.' || P->Foot[1][Contact] == '.') { ++BadPunches; std::printf("  %s: a foot is off the floor as the punch lands\n", Name.c_str()); }
        }
    }
    std::printf("  %d guards and blocks, %d walks, %d leg strikes, %d punches; shortest walk swing %.2f s, slowest walk %.0f cm/s\n",
                Guards, Walks, Legs, Punches, ShortestSwing, SlowestWalk);
    Check(Guards == 10 && BadGuards == 0, "every guard and block stands on both feet, every frame");
    std::printf("  the %d side walks hop: their feet at most %.2f of a cycle apart (the clips' own gait)\n", SideWalks, SideApart);
    Check(Walks == 20 && SideWalks == 10 && BadWalks == 0, "every walk forward and back puts each foot down once a cycle, the two in turn");
    Check(Legs >= 12 && BadLegs == 0, "every kick and knee has its leg up as it lands, on the other foot");
    Check(Punches >= 12 && BadPunches == 0, "every punch lands with both feet on the floor");

    // ---- the numbers the hold runs on, against the measured clips
    Check(ReleaseSeconds <= ShortestSwing / 3.f, "a foot is handed back inside the first third of the shortest walk swing");
    Check(StepSeconds < ShortestSwing, "a shuffle step is quicker than any walk's own swing");
    Check(FastestStill < StrideMinSpeed && StrideMinSpeed <= SlowestWalk, "every walk strides faster than StrideMinSpeed, and nothing else that loops does");
    {
        // each man's own move speed walks his clips inside the rate band:
        // his own set if he has walks, else the street men's
        int Men = 0, Outside = 0;
        for (const auto& R : ReadCsv("Content/Data/DT_Fighters.csv"))
        {
            const std::string& Name = R.at("Name");
            const SaudPlants::FClip* Own = SaudPlants::Find(("A_" + Name + "_Walk_Fwd").c_str());
            const SaudPlants::FClip* W = Own ? Own : SaudPlants::Find("A_Street_Walk_Fwd");
            if (!W) { ++Outside; continue; }
            ++Men;
            const float Speed = (float)std::atof(R.at("MoveSpeed").c_str());
            const float Rate = Speed / W->Stride;
            if (Rate < StrideRateMin || Rate > StrideRateMax) { ++Outside; std::printf("  %s: %.0f cm/s is %.2f of his walk\n", Name.c_str(), Speed, Rate); }
        }
        Check(Men == 12 && Outside == 0, "every fighter's move speed walks his own clip inside the rate band");
    }

    // ---- the frame for a time: a loop wraps, a one-shot holds its ends
    const SaudPlants::FClip* Walk = SaudPlants::Find("A_Saud_Walk_Fwd");
    const SaudPlants::FClip* Kick = SaudPlants::Find("A_Saud_Kick");
    if (!Walk || !Kick) { Check(false, "A_Saud_Walk_Fwd and A_Saud_Kick are measured"); return; }
    // the walk: left down 0-6, up 7-16; right up 0-8, down 9-14
    Check(ClipFootDown(*Walk, 0, 0.f, true) && !ClipFootDown(*Walk, 0, 10.f / 30.f, true) && ClipFootDown(*Walk, 1, 11.f / 30.f, true),
          "a clip's foot is down or up as its measured frame says");
    Check(ClipFootDown(*Walk, 0, 17.f / 30.f, true) && ClipFootDown(*Walk, 0, (17.f + 3.f) / 30.f, true) && !ClipFootDown(*Walk, 0, (17.f + 10.f) / 30.f, true),
          "a loop's frames wrap round");
    Check(ClipFootDown(*Kick, 1, 99.f, false) && !ClipFootDown(*Kick, 1, 5.f / 30.f, false) && ClipFootDown(*Kick, 1, -1.f, false),
          "a one-shot holds its first and last frames");

    // ---- the mix: the playing clips' plants by their weights
    {
        const SaudPlants::FClip* Plants[3] = { Walk, SaudPlants::Find("A_Saud_Guard"), nullptr };   // clip 2 is not measured
        FCrossfade X;
        X.Num = 2;
        X.Layers[0].Clip = 0; X.Layers[0].Time = 10.f / 30.f; X.Layers[0].bLoop = true; X.Layers[0].Weight = 0.7f;   // the walk: left up
        X.Layers[1].Clip = 1; X.Layers[1].Time = 0.f; X.Layers[1].bLoop = true; X.Layers[1].Weight = 0.3f;           // the guard: both down
        float D[2];
        MixDown(X, Plants, 3, D);
        Check(Near(D[0], 0.3f) && Near(D[1], 1.f), "a crossfade has each foot down by its clips' weights");
        X.Layers[1].Clip = 2;                                     // an unmeasured clip under the walk
        MixDown(X, Plants, 3, D);
        Check(Near(D[0], 0.f) && Near(D[1], 1.f), "...the measured part of the mix decides when most of it is measured");
        X.Layers[0].Weight = 0.3f; X.Layers[1].Weight = 0.7f;
        MixDown(X, Plants, 3, D);
        Check(D[0] == -1.f && D[1] == -1.f, "...and the heights decide when most of it is not");
    }

    // ---- the hold, from the measured plants rather than the heights
    {
        Man M;
        M.In.Down[0] = M.In.Down[1] = 1.f;
        M.Run(0.3f);
        M.In.Foot[0].Ball.Z += 3.f;          // the clip has the ball 3 cm up -- but measured down (a slope, a retarget)
        M.Run(0.1f);
        Check(M.St.Hold[0].bHeld, "a ball the clip says is down stays held, though it sits 3 cm over the other");
        M.In.Foot[0].Ball.Z -= 3.f;          // flat again -- but the clip has lifted it
        M.In.Down[0] = 0.f;
        M.Run(1.f / 60.f);
        Check(!M.St.Hold[0].bHeld, "a ball the clip says is up is let go, though it still touches the floor");
        M.In.Down[0] = 0.5f;                 // half a crossfade: stays up
        M.Run(0.1f);
        const bool bStaysUp = !M.St.Hold[0].bHeld;
        M.In.Down[0] = 1.f; M.Run(0.1f);
        M.In.Down[0] = 0.5f; M.Run(0.1f);    // half a crossfade the other way: stays down
        Check(bStaysUp && M.St.Hold[0].bHeld, "half way through a crossfade a foot keeps what it was: it changes its mind once");
    }

    // ---- the walk's pace and whether it holds, from the measured stride
    Check(Near(StrideRateMeasured(504.f, 336.4f, 1.f), 504.f / 336.4f, 1e-3f) && Near(StrideRateMeasured(336.4f, 336.4f, 1.f), 1.f, 1e-4f),
          "a walk is played at the man's pace from its first frame, by its measured stride");
    Check(Near(StrideRateMeasured(672.8f, 336.4f, 2.f), 1.f, 1e-4f), "...the stride grown with the man drawn twice the size");
    Check(StrideRateMeasured(300.f, 0.f, 1.f) == 1.f, "...and a clip that does not walk keeps its clock");
    Check(HoldsFeetMeasured(false, false, Walk->Stride) && !HoldsFeetMeasured(false, false, 0.f)
          && HoldsFeetMeasured(true, false, 0.f) && HoldsFeetMeasured(false, true, 0.f),
          "a walk holds its feet as the man moves; a block walked glides; a swing or a stand holds");
}

// ------------------------------------------------------------------- edges

/** Every share eased both ways, not only fast enough; every limit reached. */
static void Edges()
{
    std::printf("EDGES  (every share eased both ways; every limit reached)\n");
    const float Dt = 1.f / 60.f;

    // ---- on and off over frames, never in one
    {
        Man M; M.Step(Dt);
        const float On1 = M.Plan.Alpha;
        Man O; O.Run(0.5f); O.In.bWanted = false; O.Step(Dt);
        Check(On1 > 0.f && On1 < 0.1f && O.Plan.Alpha > 0.9f, "the feet ease on and off, never in a frame");
        FTurn D1 = Whole();
        TurnStep(D1, 0.f, 0.f, 0.f, false, true, false, false, Dt);
        Check(D1.Weight.Value() > 0.5f, "knocked down, the look is not dropped in a frame");
        FTurn P = Whole();
        TurnStep(P, 0.f, 0.f, 30.f, true, false, false, false, Dt);
        Check(P.Pitch > 0.f && P.Pitch < 30.f * (1.f - std::exp(-30.f * Dt)) + 0.1f, "the face's pitch eases, never snaps");
    }

    // ---- the heel's roll stops at 30 degrees, however short the leg
    {
        FFootHold H; H.bHeld = true; H.Weight = 1.f;
        FFootPlan P; P.Ball = FVector(-9.f, -15.f, 2.4f); P.Tilt = FVector::UpVector; P.ToeShare = 1.f;
        FFootIn F; F.Ankle = FVector(-24.f, -14.f, 8.f); F.Ball = FVector(-9.f, -15.f, 2.4f); F.LegLength = 88.f;
        const FVector Hip(30.f, -10.f, 92.f);   // past what any roll brings in reach
        FFootPose R;
        for (int K = 0; K < 60; ++K) R = FinishFoot(H, P, F, Hip, Dt);
        Check(Near(R.Roll, 30.f * Pi / 180.f, 1e-3f), "a heel rolls no further than 30 degrees, however short the leg");
    }

    // ---- two balls up together are in the air, by the heights
    {
        FFootHold H[2]; FBasis B;
        const FVector Raw[2] = { FVector(33.f, 15.f, 8.4f), FVector(-9.f, -15.f, 8.4f) };
        const float Lift[2] = { 6.f, 6.f }, Meas[2] = { -1.f, -1.f };
        const bool Al[2] = { true, true };
        StepHolds(H, B, Raw, Lift, Meas, Al, true, false, 1.f, Dt);
        Check(!H[0].bDown && !H[1].bDown, "both balls 6 cm up, level with each other, are in the air: a hop is not a stand");
    }

    // ---- a shove: a held foot far off steps though the other is in the air
    {
        FFootHold H[2]; FBasis B;
        const FVector Raw[2] = { FVector(33.f, 15.f, 2.4f), FVector(-9.f, -15.f, 2.4f) };
        const float Lift[2] = { 0.f, 0.f }, Meas[2] = { 1.f, 1.f };
        const bool Al[2] = { true, true };
        H[0].bHeld = true; H[0].bDown = true; H[0].Weight = 1.f; H[0].Anchor = ToWorld(B, Raw[0]);
        H[1].bStep = true; H[1].Progress = 0.5f; H[1].Weight = 0.5f;          // stepping
        B.Origin = FVector(31.f, 0.f, 0.f);                                   // 31 cm on
        StepHolds(H, B, Raw, Lift, Meas, Al, true, false, 1.f, Dt);
        Check(!H[0].bHeld && H[0].bStep, "a held foot 31 cm off steps though the other is in the air: a shove, not a shuffle");
    }

    // ---- toes bend down no further than 10 degrees
    {
        const float A = 30.f * Pi / 180.f;
        const FVector T = ToeOnGround(FVector(1.f, 0.f, 0.f), FVector(1.f, 0.f, 0.f), FVector::UpVector,
                                      FVector(std::sin(A), 0.f, std::cos(A)), 1.f);   // the ground falls away 30 under the toes
        Check(Near(std::atan2((float)T.Z, (float)T.X) * 180.f / Pi, -10.f, 0.1f), "toes bend down no further than 10 degrees");
    }

    // ---- a kerb stepped down: a step, absorbed, and the foot comes down over frames
    {
        Check(SteppedCapsule(FVector(0.f, 0.f, -15.f)) && SteppedCapsule(FVector(0.f, 0.f, 15.f)) && !SteppedCapsule(FVector(20.f, 0.f, -15.f)),
              "a kerb stepped down in a frame is a step, as one stepped up is; a ramp is not");
        Man M; M.Height = [](float X, float) { return X > 25.f ? 0.f : 15.f; };   // standing on a kerb, his toes over its edge
        M.In.Mesh.Origin.Z = 15.f; M.Run(1.f);
        const float Before = (float)(M.In.Mesh.Origin.Z + M.Plan.Pelvis.Z);
        M.Height = [](float X, float) { return X > 25.f ? 0.f : 0.f; };
        M.In.Mesh.Origin.Z = 0.f; M.Step(Dt);                                    // the capsule drops 15 cm in one frame
        const float After = (float)(M.In.Mesh.Origin.Z + M.Plan.Pelvis.Z);
        Check(std::fabs(After - Before) < 15.f * 0.25f, "a kerb the capsule steps down in one frame does not drop the body that frame");
    }
    {
        Man M; M.Height = [](float X, float) { return X > 25.f ? 15.f : 0.f; }; M.Run(1.f);
        const float Z0 = M.St.FootZ[0];
        M.Height = [](float, float) { return 0.f; };                             // the kerb under his lead foot is gone
        M.Step(Dt);
        const float Z1 = M.St.FootZ[0];
        Check(Z0 > 10.f && (Z0 - Z1) / Z0 <= 1.f - std::exp(-18.f * Dt) + 0.01f, "a foot steps down off a kerb over frames, never in one");
    }

    // ---- the hips carry no change of speed with the feet off the ground
    {
        Man M; M.Run(0.5f); M.In.bWanted = false; M.Run(0.3f);
        M.In.Velocity = FVector(300.f, 0.f, 0.f); M.Step(Dt);
        Check(std::fabs(M.St.Weight[0].X) < 1e-6f && std::fabs(M.St.Weight[0].V) < 1e-6f, "the hips carry no change of speed in the air");
    }

    // ---- the stride meter follows its samples at its rate
    {
        FStrideMeter Mt; Mt.Clip = 1; Mt.Time = 0.f; Mt.Speed = 300.f; Mt.bValid = true;
        Mt.Ball[0] = FVector(10.f, 0.f, 0.f); Mt.Ball[1] = FVector(-10.f, 0.f, 0.f); Mt.bDown[0] = true;
        const FVector Ball[2] = { FVector(10.f + 400.f * Dt, 0.f, 0.f), FVector(-10.f, 0.f, 0.f) };
        const float Lift[2] = { 0.f, 5.f };
        MeasureStride(Mt, 1, Dt, Ball, Lift);
        Check(Near(Mt.Speed, 300.f + 100.f * (1.f - std::exp(-8.f * Dt)), 0.05f), "the stride meter follows its samples at 8 a clip second");
    }

    // ---- a big man's covering glove keeps a big fist's width from the other
    {
        const FVector Sh(0.f, 20.f, 140.f), El(15.f, 25.f, 120.f), Ha(25.f, 10.f, 150.f), Other(25.f, -10.f, 150.f);
        const FTwoBone To = Cover(Sh, El, Ha, FVector(30.f, -6.f, 150.f), true, 1.f, FVector::UpVector, Other, 2.f);
        FVector Gap = To.End - Other; Gap.Z = 0.f;
        Check((float)Gap.Size() >= 17.9f && (float)Gap.Size() < 18.6f, "a big man's covering glove keeps a big fist's width from the other");
    }
}

int main()
{
    Solve(); Feet(); Held(); GroundTwo(); Stride(); Hands(); Contact(); Head(); Body(); Crossfade(); Plants(); Edges();
    std::printf(Fails ? "\n%d FAILED\n" : "\nall IK checks passed\n", Fails);
    return Fails ? 1 : 0;
}
