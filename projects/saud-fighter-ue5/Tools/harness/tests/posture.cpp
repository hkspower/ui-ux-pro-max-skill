/**
 * The posture stage of the runtime IK, executed (2026-10-07, Riyadh: "make
 * body Posture and Body Alignment and Straightness", settled as everyone, the
 * in-game IK, "keep stances, fix faults").
 *
 * SaudIK::StepPosture measures a man's pose against his OWN guard
 * (SaudStances.h, measured off each guard clip by measure_stances.py) and
 * turns the pelvis, the trunk, the chest, the neck and the head to take out
 * his faults: hips not level, the trunk tipped sideways, the shoulder line
 * dropped or raised, the head off the spine's line, the eyes not level, the
 * hips twisted against the feet. This poses each man's real guard joints
 * through the IK's own stages -- the hips' drop (StepFeet), the lean
 * (StepLean), the look (TurnStep, ShareTurn, PitchAxes), turned the way the
 * engine turns a bone -- and Saud's motion-capture gaits (stance_clips.h),
 * and checks each rule: a designed stance kept to the hundredth of a
 * degree, each fault taken out, the limits, the gate, the freeze, the frame
 * rate, no drift; then prints every man's faults before and after, case by
 * case: standing, a step and a slope, turning on the spot, walking and
 * running a curve, and Saud's free walk and run.
 */
#include "../HarnessTypes.h"
#include "../../../Source/SaudFighter/Combat/SaudIK.h"
#include "../stance_clips.h"

#include <cmath>
#include <cstdio>
#include <cstring>
#include <vector>

static int Fails = 0;
static void Check(bool Ok, const char* What)
{
    if (!Ok) { ++Fails; std::printf("  FAIL  %s\n", What); }
}

using namespace SaudIK;
using SaudStances::FJoints;
using SaudStances::FStance;

static const float Pi = 3.14159265f;
static const FVector Up(0.0, 0.0, 1.0);

// ------------------------------------------------------- the skeleton

/** A bone of the posture turned the way the engine turns it, written out
    from the mannequin's parents rather than through TurnJoints: a joint
    moves with every bone above it (pelvis > thighs, spine_01 > spine_02 >
    spine_03 > clavicles > upperarms, neck_01 > head), never with its own;
    the head's left-to-right line moves with the head too. */
static void EngineTurn(FJoints& J, EPostureBone Bone, const FVector& Axis, float Degrees)
{
    const int B = (int)Bone;
    const FVector* Pivots[6] = { &J.Pelvis, &J.Spine[0], &J.Spine[1], &J.Spine[2], &J.Neck, &J.Head };
    const FVector Pivot = *Pivots[B];
    const float R = Degrees * Pi / 180.f;
    // depth of each joint's own bone: pelvis 0, thighs 1 (under the pelvis), spine_01 1, ...
    struct FJ { FVector* P; int Own; };
    FJ All[] = { {&J.Hip[0], 1}, {&J.Hip[1], 1}, {&J.Spine[0], 1}, {&J.Spine[1], 2}, {&J.Spine[2], 3},
                 {&J.Neck, 4}, {&J.Head, 5}, {&J.Shoulder[0], 4}, {&J.Shoulder[1], 4} };
    // a joint whose bone hangs below B (its chain index past B) moves; the thighs hang off the pelvis alone
    for (FJ& X : All)
    {
        const bool bThigh = X.P == &J.Hip[0] || X.P == &J.Hip[1];
        const bool bMoves = bThigh ? B == 0 : X.Own > B;
        if (bMoves) *X.P = Pivot + RotateAbout(*X.P - Pivot, Axis, R);
    }
    J.HeadSide = RotateAbout(J.HeadSide, Axis, R);
}

static FJoints ApplyFix(FJoints J, const FPostureFix& F)
{
    for (int I = 0; I < F.Num; ++I) EngineTurn(J, F.Turn[I].Bone, F.Turn[I].Axis, F.Turn[I].Degrees);
    return J;
}

/** The IK's stages 1 and 2 on a pose, the engine's order: the pelvis moved
    (the hips' drop and carry), turned by the lean about its own joint, then
    the chain -- spine_01, spine_02, spine_03, neck_01, head -- each its yaw
    about up and then its nod about its own level axis. */
static FJoints PoseIK(FJoints J, const FVector& Move, const FVector& LeanAxis, float LeanDeg,
                      const FChainTurn* Chain = nullptr, const FVector& Forward = FVector(1.0, 0.0, 0.0))
{
    FVector* Moved[] = { &J.Pelvis, &J.Hip[0], &J.Hip[1], &J.Spine[0], &J.Spine[1], &J.Spine[2], &J.Neck, &J.Head,
                         &J.Shoulder[0], &J.Shoulder[1] };
    for (FVector* P : Moved) *P = *P + Move;
    if (std::fabs(LeanDeg) > 1e-5f) EngineTurn(J, EPostureBone::Pelvis, LeanAxis, LeanDeg);
    if (Chain)
    {
        FVector Axes[ChainBones];
        PitchAxes(*Chain, Forward, Up, Axes);
        for (int I = 0; I < ChainBones; ++I)
        {
            const EPostureBone B = (EPostureBone)(I + 1);
            EngineTurn(J, B, Up, Chain->Yaw[I]);
            EngineTurn(J, B, Axes[I], Chain->Pitch[I]);
        }
    }
    return J;
}

static float Abs(float V) { return std::fabs(V); }
static float Most(const FPostureFaults& F, bool bTwist = true)
{
    float M = std::fmax(std::fmax(Abs(F.HipRoll), Abs(F.ShoulderRoll)), std::fmax(Abs(F.TrunkTilt), Abs(F.EyeRoll)));
    return bTwist ? std::fmax(M, Abs(F.Twist)) : M;
}
static const FStance& Stance(const char* Set) { return *SaudStances::Find(Set); }

/** The test's own reference, from the table and not from StanceRef: his
    stance's numbers, or straight for motion capture (bGait). */
static FPostureFaults TableRef(const FStance& S, bool bGait)
{
    FPostureFaults R;
    if (!bGait) { R.HipRoll = S.HipRoll; R.ShoulderRoll = S.ShoulderRoll; R.TrunkTilt = S.TrunkTilt; R.HeadOff = S.HeadOff; R.EyeRoll = S.EyeRoll; }
    R.Twist = S.Twist;
    return R;
}
static FPostureFaults Less(const FPostureFaults& M, const FPostureFaults& R)
{
    FPostureFaults D;
    D.HipRoll = M.HipRoll - R.HipRoll; D.ShoulderRoll = M.ShoulderRoll - R.ShoulderRoll; D.TrunkTilt = M.TrunkTilt - R.TrunkTilt;
    D.HeadOff = M.HeadOff - R.HeadOff; D.EyeRoll = M.EyeRoll - R.EyeRoll;
    D.Twist = M.Twist - R.Twist; while (D.Twist > 180.f) D.Twist -= 360.f; while (D.Twist <= -180.f) D.Twist += 360.f;
    return D;
}
/** His faults as the pose stands (Was), and as the engine leaves it -- the
    fix's turns put on the bones one by one (Left): measured, less the table. */
static FPostureFaults Was(const FJoints& J, const FStance& S, const FVector& BodyUp = Up, bool bGait = false)
{
    return Less(MeasurePosture(J, BodyUp, Up), TableRef(S, bGait));
}
static FPostureFaults Left(const FJoints& J, const FPostureFix& F, const FStance& S, const FVector& BodyUp = Up, bool bGait = false)
{
    return Less(MeasurePosture(ApplyFix(J, F), BodyUp, Up), TableRef(S, bGait));
}
static FPostureState On() { FPostureState S; S.Share.Lin = 1.f; S.Twist.Lin = 1.f; return S; }
static FPostureIn Standing(bool bTwist = true)
{
    FPostureIn In; In.bOn = true; In.bTwist = bTwist; In.FeetShare = 1.f; return In;
}
/** The roll of a line against level, degrees, + right high. */
static float Roll(const FVector& L, const FVector& U = Up) { return AsinDegrees((float)FVector::DotProduct(L.GetSafeNormal(), U)); }
/** How far the trunk leans forward: spine_01 -> spine_03 against up, toward his facing. */
static float Crouch(const FJoints& J)
{
    const FVector T = (J.Spine[2] - J.Spine[0]).GetSafeNormal();
    return AsinDegrees((float)T.X);
}
static float YawOf(const FVector& L) { return std::atan2(-(float)L.X, (float)L.Y) * 180.f / Pi; }

// ------------------------------------------------- 1. his stance is his

static void Stances()
{
    std::printf("STANCES  (each man's guard, measured as SaudStances.h has it)\n");
    const char* Sets[] = { "Saud", "Street", "Boss", "Saqr", "Zayos" };
    float Worst = 0.f, Moved = 0.f;
    for (const char* Set : Sets)
    {
        const FStance& S = Stance(Set);
        const FPostureFaults M = MeasurePosture(S.Joints, Up, Up);
        Worst = std::fmax(Worst, std::fmax(std::fmax(Abs(M.HipRoll - S.HipRoll), Abs(M.ShoulderRoll - S.ShoulderRoll)),
                                           std::fmax(std::fmax(Abs(M.TrunkTilt - S.TrunkTilt), Abs(M.HeadOff - S.HeadOff)),
                                                     std::fmax(Abs(M.EyeRoll - S.EyeRoll), Abs(M.Twist - S.Twist)))));
        FPostureState St = On();
        const FPostureFix F = StepPosture(St, Standing(), S.Joints, S, 1.f / 60.f);
        for (int I = 0; I < F.Num; ++I) Moved = std::fmax(Moved, Abs(F.Turn[I].Degrees));
        std::printf("  %-6s %-9s hips %+5.2f  shoulders %+5.2f  trunk %+5.2f  head %+5.2f cm  eyes %+5.2f  twist %+6.1f\n",
                    Set, S.Guard, S.HipRoll, S.ShoulderRoll, S.TrunkTilt, S.HeadOff, S.EyeRoll, S.Twist);
    }
    Check(SaudStances::NumStances == 5 && SaudStances::Find("Monkey") == nullptr && SaudStances::Find("Gorilla") == nullptr,
          "posture: the five men's sets have a stance and the Island's creatures none");
    Check(Worst < 0.01f, "posture: each guard measures as its stance");
    std::printf("  the guard measured against its own table: %.4f at worst; the stage on a guard turns %.5f degrees at most\n", Worst, Moved);
    Check(Moved < 0.05f, "posture: a man in his own guard is left as he stands");
    // AL-WAHSH's high lead shoulder: kept, not levelled -- his chest put out
    // of true by 3 degrees, the stage gives him back his 4.9, not level
    {
        const FStance& B = Stance("Boss");
        FJoints J = B.Joints; EngineTurn(J, EPostureBone::Spine03, FVector(1.0, 0.0, 0.0), 3.f);
        FPostureState St = On();
        const FJoints A = ApplyFix(J, StepPosture(St, Standing(), J, B, 1.f / 60.f));
        const float Kept = Roll(A.Shoulder[1] - A.Shoulder[0]);
        std::printf("  AL-WAHSH's chest put 3 degrees out: his shoulder line %+.2f -> %+.2f (his stance %+.2f)\n",
                    Roll(J.Shoulder[1] - J.Shoulder[0]), Kept, B.ShoulderRoll);
        Check(B.ShoulderRoll > 4.f && std::fabs(Kept - B.ShoulderRoll) < 0.05f, "posture: AL-WAHSH's peek-a-boo keeps its shoulder line");
    }
}

// ------------------------------------------- 2. each fault comes out

static void Faults()
{
    std::printf("FAULTS  (each put into Saud's guard and taken out again)\n");
    const FStance& S = Stance("Saud");
    const FJoints G = S.Joints;
    auto Run = [&](const FJoints& J, FPostureIn In = Standing()) { FPostureState St = On(); return StepPosture(St, In, J, S, 1.f / 60.f); };
    const FVector Fwd(1.0, 0.0, 0.0);

    { // the hips tipped 5 degrees
        FJoints J = G; EngineTurn(J, EPostureBone::Pelvis, Fwd, 5.f);
        const FPostureFix F = Run(J);
        const FPostureFaults B = Was(J, S), A = Left(J, F, S);
        std::printf("  hips tipped 5:      hips %+.2f -> %+.3f\n", B.HipRoll, A.HipRoll);
        Check(Abs(B.HipRoll) > 4.f && Abs(A.HipRoll) < 0.05f, "posture: the hips are levelled");
    }
    { // the trunk tipped 5 degrees sideways at spine_01 (square to his chest); the crouch kept
        const FVector Chest = FVector::CrossProduct(LevelOf(G.Shoulder[1] - G.Shoulder[0], Up), Up).GetSafeNormal();
        FJoints J = G; EngineTurn(J, EPostureBone::Spine01, Chest, 5.f);
        const FPostureFix F = Run(J);
        const FJoints A = ApplyFix(J, F);
        std::printf("  trunk tipped 5:     trunk %+.2f -> %+.3f, its forward lean %.2f -> %.2f (guard %.2f)\n",
                    Was(J, S).TrunkTilt, Left(J, F, S).TrunkTilt, Crouch(J), Crouch(A), Crouch(G));
        Check(Abs(Was(J, S).TrunkTilt) > 3.f && Abs(Left(J, F, S).TrunkTilt) < 0.05f,
              "posture: the trunk is stood up sideways");
        Check(Abs(Crouch(A) - Crouch(G)) < 0.5f, "posture: the trunk's forward lean is his own");
    }
    { // the shoulder line dropped 4 degrees at spine_03
        FJoints J = G; EngineTurn(J, EPostureBone::Spine03, Fwd, -4.f);
        const FPostureFix F = Run(J);
        std::printf("  shoulders off 4:    shoulders %+.2f -> %+.3f\n", Was(J, S).ShoulderRoll, Left(J, F, S).ShoulderRoll);
        Check(Abs(Was(J, S).ShoulderRoll) > 3.f && Abs(Left(J, F, S).ShoulderRoll) < 0.05f, "posture: the shoulder line is levelled");
    }
    { // the head off the spine: neck_01 tipped 8 degrees
        FJoints J = G; EngineTurn(J, EPostureBone::Neck, Fwd, 8.f);
        const FPostureFix F = Run(J);
        std::printf("  neck tipped 8:      head off %+.2f -> %+.3f cm\n", Was(J, S).HeadOff, Left(J, F, S).HeadOff);
        Check(Abs(Was(J, S).HeadOff) > 1.5f && Abs(Left(J, F, S).HeadOff) < 0.05f, "posture: the head is put back over the spine");
    }
    { // the eyes rolled 8 degrees at the head
        FJoints J = G; EngineTurn(J, EPostureBone::Head, Fwd, 8.f);
        const FPostureFix F = Run(J);
        std::printf("  head rolled 8:      eyes %+.2f -> %+.3f\n", Was(J, S).EyeRoll, Left(J, F, S).EyeRoll);
        Check(Abs(Was(J, S).EyeRoll) > 7.f && Abs(Left(J, F, S).EyeRoll) < 0.05f, "posture: the eyes are levelled");
    }
    { // the hips turned 6 degrees against the feet (the body on; the feet held)
        FJoints J = G; EngineTurn(J, EPostureBone::Pelvis, Up, 6.f);
        const float Chest = YawOf(J.Shoulder[1] - J.Shoulder[0]);
        const FPostureFix F = Run(J);
        const FJoints A = ApplyFix(J, F);
        std::printf("  hips turned 6:      twist %+.2f -> %+.3f, the chest's facing %+.2f -> %+.2f\n",
                    Was(J, S).Twist, Left(J, F, S).Twist, Chest, YawOf(A.Shoulder[1] - A.Shoulder[0]));
        Check(Abs(Was(J, S).Twist) > 5.f && Abs(Left(J, F, S).Twist) < 0.05f, "posture: the hips are kept to the stance's angle to the feet");
        Check(Abs(YawOf(A.Shoulder[1] - A.Shoulder[0]) - Chest) < 0.1f, "posture: the chest faces where it faced");
        FPostureState Ramp; FPostureIn In = Standing(false);
        for (int I = 0; I < 60; ++I) StepPosture(Ramp, In, J, S, 1.f / 60.f);
        const FPostureFix W2 = StepPosture(Ramp, In, J, S, 1.f / 60.f);
        Check(Abs(Left(J, W2, S).Twist - Was(J, S).Twist) < 1e-3f,
              "posture: the twist is only straightened standing");
    }
    { // every fault at once, in the order the engine turns them
        FJoints J = G;
        EngineTurn(J, EPostureBone::Pelvis, Up, 6.f); EngineTurn(J, EPostureBone::Pelvis, Fwd, 3.f);
        EngineTurn(J, EPostureBone::Spine02, Fwd, -4.f); EngineTurn(J, EPostureBone::Spine03, Fwd, 3.f);
        EngineTurn(J, EPostureBone::Neck, Fwd, -4.f); EngineTurn(J, EPostureBone::Head, Fwd, 3.f);
        const FPostureFix F = Run(J);
        const FPostureFaults A = Left(J, F, S);
        std::printf("  all six at once:    worst %.2f -> %.3f degrees (as measured %.3f), head %+.2f -> %+.3f cm (hips %.3f shoulders %.3f trunk %.3f eyes %.3f twist %.3f)\n",
                    Most(F.Before), Most(A), Most(F.After), F.Before.HeadOff, A.HeadOff, A.HipRoll, A.ShoulderRoll, A.TrunkTilt, A.EyeRoll, A.Twist);
        const bool bSame = Abs(A.HipRoll - F.After.HipRoll) < 1e-3f && Abs(A.ShoulderRoll - F.After.ShoulderRoll) < 1e-3f
            && Abs(A.TrunkTilt - F.After.TrunkTilt) < 1e-3f && Abs(A.HeadOff - F.After.HeadOff) < 1e-3f
            && Abs(A.EyeRoll - F.After.EyeRoll) < 1e-3f && Abs(A.Twist - F.After.Twist) < 1e-3f;
        Check(bSame, "posture: the engine's turns, bone by bone, give the pose it measured");
        Check(Most(A) < 0.1f && Abs(A.HeadOff) < 0.05f, "posture: every fault at once is taken out");
    }
    { // the hips' part waits for the feet: no legs solved, no pelvis turned
        FJoints J = G; EngineTurn(J, EPostureBone::Pelvis, Fwd, 5.f); EngineTurn(J, EPostureBone::Pelvis, Up, 8.f);
        FPostureIn In = Standing(); In.FeetShare = 0.f;
        const FPostureFix F = Run(J, In);
        bool bPelvis = false;
        for (int I = 0; I < F.Num; ++I) bPelvis = bPelvis || F.Turn[I].Bone == EPostureBone::Pelvis;
        Check(!bPelvis, "posture: the hips are turned only with the feet on");
    }
}

// ----------------------------------------------- 3. limits and smoothness

static void Limits()
{
    std::printf("LIMITS  (the whole fault to %.0f %% of a limit, then easing toward it)\n", PostureKnee * 100.f);
    const float Maxes[] = { PostureTwistMaxDeg, PostureHipMaxDeg, PostureTrunkMaxDeg, PostureChestMaxDeg, PostureNeckMaxDeg, PostureEyesMaxDeg };
    bool bBound = true, bWhole = true, bSmooth = true, bMono = true;
    for (float M : Maxes)
    {
        float Last = 0.f, LastSlope = 1.f;
        for (int I = 1; I <= 4000; ++I)
        {
            const float D = I * 0.025f;                    // to 100 degrees
            const float C = PostureLimit(D, M);
            if (C > M || C < 0.f) bBound = false;
            if (D <= PostureKnee * M && std::fabs(C - D) > 1e-5f) bWhole = false;
            const float Slope = (C - Last) / 0.025f;
            if (Slope > 1.f + 1e-3f || Slope < -1e-4f) bMono = false;
            if (std::fabs(Slope - LastSlope) > 0.02f) bSmooth = false;    // no kink: the slope changes a little a step
            if (std::fabs(PostureLimit(-D, M) + C) > 1e-6f) bMono = false;
            Last = C; LastSlope = Slope;
        }
    }
    Check(bBound, "posture: no correction passes its limit");
    Check(bWhole && bMono, "posture: a fault under the knee is corrected whole, and more never less");
    Check(bSmooth, "posture: the limit eases in with no kink");
    // a big fault: corrected by most of the limit, never past it
    {
        const FStance& S = Stance("Saud");
        FJoints J = S.Joints; EngineTurn(J, EPostureBone::Head, FVector(1.0, 0.0, 0.0), 40.f);
        FPostureState St = On();
        const FPostureFix F = StepPosture(St, Standing(), J, S, 1.f / 60.f);
        float Head = 0.f;
        for (int I = 0; I < F.Num; ++I) if (F.Turn[I].Bone == EPostureBone::Head) Head += F.Turn[I].Degrees;
        std::printf("  a head rolled 40: turned back %.2f of the %.0f-degree limit\n", Abs(Head), PostureEyesMaxDeg);
        Check(Abs(Head) < PostureEyesMaxDeg && Abs(Head) > 0.9f * PostureEyesMaxDeg, "posture: a fault past the limit is corrected by the limit's most");
    }
}

// ------------------------------------------------------- 4. the gate

static void Gate()
{
    std::printf("GATE  (on over %.2f s, off in %.2f s; the freeze holds it)\n", PostureOnSeconds, PostureOffSeconds);
    const FStance& S = Stance("Saud");
    FJoints Reel = S.Joints;      // a reel's pose: the head thrown 10 degrees, the trunk 6
    EngineTurn(Reel, EPostureBone::Spine01, FVector(1.0, 0.0, 0.0), 6.f);
    EngineTurn(Reel, EPostureBone::Head, FVector(1.0, 0.0, 0.0), 10.f);
    // a strike, a reel, a fall: once the gate is shut nothing is turned
    {
        FPostureState St = On();
        FPostureIn In = Standing(); In.bOn = false;
        FPostureFix F;
        int Frames = 0;
        for (int I = 0; I < 30; ++I) { F = StepPosture(St, In, Reel, S, 1.f / 60.f); if (F.Num > 0) Frames = I + 1; }
        std::printf("  a reel: the posture lets go after %d frames at 60 Hz, then turns nothing\n", Frames);
        Check(F.Num == 0 && F.Share == 0.f && Frames <= (int)std::ceil(PostureOffSeconds * 60.f),
              "posture: a strike, a reel or a fall is left as it moves");
    }
    // on: it climbs over its seconds, never in a frame
    {
        FPostureState St;
        float Last = 0.f, Jump = 0.f;
        float Head[3] = { 0.f, 0.f, 0.f };
        const float Hz[3] = { 30.f, 60.f, 120.f };
        for (int H = 0; H < 3; ++H)
        {
            FPostureState R;
            const int N = (int)std::lround(0.2f * Hz[H]);
            FPostureFix F;
            for (int I = 0; I < N; ++I) F = StepPosture(R, Standing(), Reel, S, 1.f / Hz[H]);
            for (int I = 0; I < F.Num; ++I) if (F.Turn[I].Bone == EPostureBone::Head) Head[H] += F.Turn[I].Degrees;
        }
        for (int I = 0; I < 30; ++I)
        {
            const FPostureFix F = StepPosture(St, Standing(), Reel, S, 1.f / 60.f);
            Jump = std::fmax(Jump, F.Share - Last);
            Last = F.Share;
        }
        std::printf("  on: at most %.3f of the share a frame at 60 Hz; the head's turn 0.2 s in: %.3f / %.3f / %.3f (30 / 60 / 120 Hz)\n",
                    Jump, Head[0], Head[1], Head[2]);
        Check(Jump < 0.12f && Last == 1.f, "posture: the gate eases on, never in a frame");
        Check(std::fabs(Head[0] - Head[1]) < 0.01f && std::fabs(Head[2] - Head[1]) < 0.01f, "posture: the same at 30, 60 and 120 Hz");
    }
    // the freeze: world time stopped, the gate where it was
    {
        FPostureState St;
        for (int I = 0; I < 6; ++I) StepPosture(St, Standing(), Reel, S, 1.f / 60.f);
        const float Before = St.Share.Lin;
        FPostureIn Off = Standing(); Off.bOn = false;
        for (int I = 0; I < 30; ++I) StepPosture(St, Off, Reel, S, 0.f);
        Check(St.Share.Lin == Before && Before > 0.f, "posture: the freeze holds it");
    }
    // no drift: corrections are the pose's own each frame, none kept after the fault goes
    {
        FPostureState St = On();
        for (int I = 0; I < 120; ++I) StepPosture(St, Standing(), Reel, S, 1.f / 60.f);
        const FPostureFix F = StepPosture(St, Standing(), S.Joints, S, 1.f / 60.f);
        float Left = 0.f;
        for (int I = 0; I < F.Num; ++I) Left = std::fmax(Left, Abs(F.Turn[I].Degrees));
        Check(Left < 0.05f, "posture: nothing is kept once the fault has gone");
    }
}

// ------------------------------------------------------ 5. the cases

/** A case's worst fault of each kind, before and after, and its wobble: the
    root mean square of each angle's change from one frame to the next,
    degrees (the hips, shoulders, trunk, eyes and, standing, the twist). */
struct FCase
{
    float Before[6]; float After[6]; float WobbleBefore = 0.f, WobbleAfter = 0.f;
    float LastB[6], LastA[6]; double SumB = 0.0, SumA = 0.0; int N = 0; bool bLast = false;
};
static void Track(FCase& C, const FJoints& J, const FPostureFix& F, const FStance& S, bool bTwist,
                  const FVector& BodyUp = Up, bool bGait = false)
{
    const FPostureFaults Wb = Was(J, S, BodyUp, bGait), La = Left(J, F, S, BodyUp, bGait);
    const float B[6] = { Wb.HipRoll, Wb.ShoulderRoll, Wb.TrunkTilt, Wb.HeadOff, Wb.EyeRoll, bTwist ? Wb.Twist : 0.f };
    const float A[6] = { La.HipRoll, La.ShoulderRoll, La.TrunkTilt, La.HeadOff, La.EyeRoll, bTwist ? La.Twist : 0.f };
    for (int I = 0; I < 6; ++I) { C.Before[I] = std::fmax(C.Before[I], Abs(B[I])); C.After[I] = std::fmax(C.After[I], Abs(A[I])); }
    if (C.bLast)
    {
        for (int I = 0; I < 6; ++I)
        {
            if (I == 3) continue;
            C.SumB += (B[I] - C.LastB[I]) * (B[I] - C.LastB[I]); C.SumA += (A[I] - C.LastA[I]) * (A[I] - C.LastA[I]);
        }
        ++C.N;
        C.WobbleBefore = (float)std::sqrt(C.SumB / (5.0 * C.N)); C.WobbleAfter = (float)std::sqrt(C.SumA / (5.0 * C.N));
    }
    for (int I = 0; I < 6; ++I) { C.LastB[I] = B[I]; C.LastA[I] = A[I]; }
    C.bLast = true;
}
static FCase Fresh() { FCase C; for (int I = 0; I < 6; ++I) C.Before[I] = C.After[I] = 0.f; return C; }
static void Print(const char* Man, const char* What, const FCase& C, bool bWobble = false)
{
    std::printf("  %-6s %-22s hips %4.1f>%-4.1f shoulders %4.1f>%-4.1f trunk %4.1f>%-4.1f head %4.1f>%-4.1f cm eyes %4.1f>%-4.1f twist %4.1f>%-4.1f",
                Man, What, C.Before[0], C.After[0], C.Before[1], C.After[1], C.Before[2], C.After[2], C.Before[3], C.After[3],
                C.Before[4], C.After[4], C.Before[5], C.After[5]);
    if (bWobble) std::printf("  wobble %.2f>%.2f", C.WobbleBefore, C.WobbleAfter);
    std::printf("\n");
}
static float WorstAfter(const FCase& C) { float W = 0.f; for (int I = 0; I < 6; ++I) if (I != 3) W = std::fmax(W, C.After[I]); return W; }
static float WorstBefore(const FCase& C) { float W = 0.f; for (int I = 0; I < 6; ++I) if (I != 3) W = std::fmax(W, C.Before[I]); return W; }

/** A man's guard feet for SaudIK::StepFeet, from his guard joints. */
static FFeetIn FeetOf(const FJoints& G)
{
    FFeetIn In;
    In.bWanted = true; In.bHold = true; In.bSettle = true;
    const float AnkleRest = (float)std::fmin(G.Ankle[0].Z, G.Ankle[1].Z), BallRest = (float)std::fmin(G.Ball[0].Z, G.Ball[1].Z);
    for (int S = 0; S < 2; ++S)
    {
        FFootIn& F = In.Foot[S];
        F.Hip = G.Hip[S]; F.Ankle = G.Ankle[S]; F.Ball = G.Ball[S];
        F.LegLength = (float)(FVector::Dist(G.Hip[S], G.Knee[S]) + FVector::Dist(G.Knee[S], G.Ankle[S]));
        F.AnkleRest = AnkleRest; F.BallRest = BallRest;
    }
    return In;
}
static FBasis Facing(float YawDeg)
{
    FBasis B; const float R = YawDeg * Pi / 180.f;
    B.X = FVector(std::cos(R), std::sin(R), 0.0); B.Y = FVector(-std::sin(R), std::cos(R), 0.0);
    return B;
}
static void Ground(FFeetIn& In, float (*Height)(float, float), FVector (*Normal)(float, float))
{
    for (int S = 0; S < 2; ++S)
    {
        const FVector Pts[2] = { ToWorld(In.Mesh, In.Foot[S].Ankle), ToWorld(In.Mesh, In.Foot[S].Ball) };
        for (int K = 0; K < 2; ++K)
        {
            FGroundPoint& G = K ? In.Foot[S].BallGround : In.Foot[S].HeelGround;
            G.bHit = true;
            G.Point = ToMesh(In.Mesh, FVector(Pts[K].X, Pts[K].Y, Height((float)Pts[K].X, (float)Pts[K].Y)));
            G.Normal = DirToMesh(In.Mesh, Normal((float)Pts[K].X, (float)Pts[K].Y));
        }
    }
}

static void Cases()
{
    std::printf("CASES  (each man's worst fault over the case, before > after: degrees, the head in cm)\n");
    const char* Sets[] = { "Saud", "Street", "Boss", "Saqr", "Zayos" };
    float Stand = 0.f, StandBefore = 0.f, Slope = 0.f, TurnB = 0.f, TurnA = 0.f, CurveEyes = 0.f, CurveBody = 0.f, Kept = 1e9f;
    float LookYaw = 0.f, TurnWobB = 0.f, TurnWobA = 0.f, Pivot = 0.f;
    for (const char* Set : Sets)
    {
        const FStance& S = Stance(Set);
        const FJoints G = S.Joints;

        // standing, looking at a man 60 degrees to his left and 25 up (the look's chest share and nod)
        {
            FCase C = Fresh();
            FTurn T; T.Weight.Lin = 1.f;
            for (int I = 0; I < 120; ++I) TurnStep(T, 0.f, 60.f, 25.f, true, false, false, false, 1.f / 60.f);
            const FChainTurn Ch = ShareTurn(T);
            const FJoints J = PoseIK(G, FVector::ZeroVector, FVector(1.0, 0.0, 0.0), 0.f, &Ch);
            FPostureState St = On();
            const FPostureFix F = StepPosture(St, Standing(), J, S, 1.f / 60.f);
            Track(C, J, F, S, true);
            const FJoints A = ApplyFix(J, F);
            LookYaw = std::fmax(LookYaw, Abs(YawOf(A.Shoulder[1] - A.Shoulder[0]) - YawOf(J.Shoulder[1] - J.Shoulder[0])));
            Print(Set, "standing, looking", C);
            Stand = std::fmax(Stand, WorstAfter(C)); StandBefore = std::fmax(StandBefore, WorstBefore(C));
        }
        // a kerb: his lead foot 12 cm down, then a 20-degree slope across him: the hips' drop
        {
            FCase C = Fresh();
            for (int K = 0; K < 2; ++K)
            {
                FFeetIn In = FeetOf(G);
                FFeetState St;
                FPostureState P;
                FFeetPlan Plan;
                for (int I = 0; I < 90; ++I)
                {
                    if (K == 0) Ground(In, [](float, float Y) { return Y < 0.f ? -12.f : 0.f; }, [](float, float) { return FVector::UpVector; });
                    else Ground(In, [](float, float Y) { return -std::tan(20.f * 3.14159265f / 180.f) * Y; },
                                [](float, float) { const float T = 20.f * 3.14159265f / 180.f; return FVector(0.0, std::sin(T), std::cos(T)); });
                    Plan = StepFeet(St, In, 1.f / 60.f);
                    FJoints J = PoseIK(G, Plan.Pelvis, FVector(1.0, 0.0, 0.0), 0.f);
                    for (int Sd = 0; Sd < 2; ++Sd) J.Ball[Sd] = Plan.Foot[Sd].Ball;
                    FPostureIn PIn = Standing(); PIn.FeetShare = Plan.Alpha;
                    const FPostureFix F = StepPosture(P, PIn, J, S, 1.f / 60.f);
                    if (I > 45) Track(C, J, F, S, true);
                }
                if (K == 0) Check(Plan.Pelvis.Z < -10.f, "posture: (the kerb drops his hips)");
            }
            Print(Set, "a kerb, a 20-deg slope", C);
            Slope = std::fmax(Slope, std::fmax(WorstAfter(C), WorstBefore(C)));
        }
        // turning on the spot, his feet held and stepping after him: 90 deg/s for 4 s, then a whole turn at 180
        {
            FCase C = Fresh();
            for (int K = 0; K < 2; ++K)
            {
                const float Rate = K == 0 ? 90.f : 180.f, Secs = K == 0 ? 4.f : 2.f;
                FFeetIn In = FeetOf(G);
                FFeetState St;
                FPostureState P;
                const int N = (int)std::lround(Secs * 60.f);
                for (int I = 0; I <= N; ++I)
                {
                    In.Mesh = Facing(Rate * I / 60.f);
                    Ground(In, [](float, float) { return 0.f; }, [](float, float) { return FVector::UpVector; });
                    const FFeetPlan Plan = StepFeet(St, In, 1.f / 60.f);
                    FJoints J = PoseIK(G, Plan.Pelvis, FVector(1.0, 0.0, 0.0), 0.f);
                    for (int Sd = 0; Sd < 2; ++Sd) J.Ball[Sd] = Plan.Foot[Sd].Ball;
                    FPostureIn PIn = Standing(); PIn.FeetShare = Plan.Alpha;
                    const FPostureFix F = StepPosture(P, PIn, J, S, 1.f / 60.f);
                    if (I > 30) Track(C, J, F, S, true);
                }
            }
            Print(Set, "turning on the spot", C, true);
            TurnWobB = std::fmax(TurnWobB, C.WobbleBefore); TurnWobA = std::fmax(TurnWobA, C.WobbleAfter);
            TurnB = std::fmax(TurnB, C.Before[5]); TurnA = std::fmax(TurnA, C.After[5]);
        }
        // walking a curve (his walk tier round 2 m) and running one (his run round 3 m): the lean
        {
            FCase C = Fresh();
            const float V[2] = { 153.f, 341.f }, R[2] = { 200.f, 300.f };
            for (int K = 0; K < 2; ++K)
            {
                FLean L;
                FPostureState P;
                const float W = V[K] / R[K];
                for (int I = 0; I <= 120; ++I)
                {
                    const float Th = W * I / 60.f;
                    const FVector Vel = FVector(-std::sin(Th), std::cos(Th), 0.0) * V[K];
                    StepLean(L, Vel, 0.45f * 341.f, 341.f, true, 1.f / 60.f);
                    FVector Axis; float Deg = 0.f;
                    LeanAxisAngle(L, Axis, Deg);
                    const FBasis M = Facing(Th * 180.f / Pi + 90.f);   // he faces his way
                    const FVector AxisM = DirToMesh(M, Axis);
                    const FJoints J = PoseIK(G, FVector::ZeroVector, AxisM, Deg);
                    FPostureIn PIn = Standing(false);
                    PIn.BodyUp = RotateAbout(Up, AxisM, Deg * Pi / 180.f);
                    const FPostureFix F = StepPosture(P, PIn, J, S, 1.f / 60.f);
                    if (I > 30) Track(C, J, F, S, false, PIn.BodyUp);
                    if (I == 120)
                    {
                        // the lean is kept: his shoulders and hips still tip with it against the world
                        const FJoints A = ApplyFix(J, F);
                        const float Tip = Roll(A.Hip[1] - A.Hip[0]) - Roll(G.Hip[1] - G.Hip[0]);
                        const float Want = Roll(J.Hip[1] - J.Hip[0]) - Roll(G.Hip[1] - G.Hip[0]);
                        if (Abs(Want) > 1.f) Kept = std::fmin(Kept, Tip / Want);
                        CurveEyes = std::fmax(CurveEyes, Abs(Left(J, F, S, PIn.BodyUp).EyeRoll));
                    }
                }
            }
            Print(Set, "walking, running a curve", C);
            CurveBody = std::fmax(CurveBody, std::fmax(C.After[0], std::fmax(C.After[1], C.After[2])));
        }
        // at a run, a start, a pivot (his way reversed in 0.45 s, the turn clip's own) and a stop: the lean's pitch
        {
            FCase C = Fresh();
            FLean L;
            FPostureState P;
            for (int I = 0; I <= 150; ++I)
            {
                const float T = I / 60.f;
                float V = T < 0.3f ? 341.f * T / 0.3f : T < 1.f ? 341.f : T < 1.45f ? 341.f * std::cos(Pi * (T - 1.f) / 0.45f) : T < 2.f ? -341.f : -341.f * std::fmax(0.f, 1.f - (T - 2.f) / 0.3f);
                StepLean(L, FVector(V, 0.0, 0.0), 0.45f * 341.f, 341.f, true, 1.f / 60.f);
                FVector Axis; float Deg = 0.f;
                LeanAxisAngle(L, Axis, Deg);
                const FBasis M = Facing(T < 1.225f ? 0.f : 180.f);
                const FVector AxisM = DirToMesh(M, Axis);
                const FJoints J = PoseIK(G, FVector::ZeroVector, AxisM, Deg);
                FPostureIn PIn = Standing(false);
                PIn.BodyUp = RotateAbout(Up, AxisM, Deg * Pi / 180.f);
                Track(C, J, StepPosture(P, PIn, J, S, 1.f / 60.f), S, false, PIn.BodyUp);
            }
            Print(Set, "start, pivot, stop", C);
            Pivot = std::fmax(Pivot, std::fmax(WorstAfter(C), WorstBefore(C)));
        }
    }
    std::printf("  standing: worst %.2f -> %.3f; the chest's look turned by the posture %.3f degrees at most\n", StandBefore, Stand, LookYaw);
    Check(Stand < 0.1f, "posture: standing and looking, he stands as his stance");
    Check(LookYaw < 0.5f, "posture: the look's turn is the look's");
    Check(Slope < 0.1f, "posture: a step or a slope under his feet leaves him level");
    std::printf("  turning: the hips against the feet %.1f -> %.1f degrees at worst; wobble %.2f -> %.2f a frame\n", TurnB, TurnA, TurnWobB, TurnWobA);
    std::printf("  a start, a pivot and a stop at a run: %.2f degrees off his stance at worst\n", Pivot);
    Check(Pivot < 0.1f, "posture: a pivot's or a stop's lean leaves him as his stance");
    Check(TurnWobA < 0.6f * TurnWobB, "posture: turning, no wobble frame to frame");
    Check(TurnB > 10.f && TurnA < 0.4f * TurnB, "posture: turning on the spot keeps his hips to his feet");
    std::printf("  curves: the eyes %.2f off level after; the hips' lean kept %.3f of itself; hips, shoulders, trunk %.3f off the lean's\n", CurveEyes, Kept, CurveBody);
    Check(CurveEyes < 1.5f, "posture: running a curve, his eyes are level");
    Check(Kept > 0.99f && CurveBody < 0.05f, "posture: the lean is his, and kept");
}

/** Saud's free walk and run (motion capture, no guard built into them):
    straight, as a walk is, every frame; and the wobble frame to frame. */
static void Gaits()
{
    std::printf("GAITS  (Saud's motion capture, every frame: straight, not his crouch)\n");
    const FStance& S = Stance("Saud");
    float Worst = 0.f, Wob = 0.f, WobBefore = 0.f, HeadCm = 0.f;
    for (int C = 0; C < StanceClips::NumClips; ++C)
    {
        const StanceClips::FClip& K = StanceClips::Clips[C];
        FCase X = Fresh();
        FPostureState P; P.Share.Lin = 1.f;      // walking: the twist's gate shut
        FPostureIn In = Standing(false); In.Gait = 1.f;
        for (int F = 0; F <= K.Frames; ++F)
        {
            const FJoints& J = K.Frame[F % K.Frames];
            Track(X, J, StepPosture(P, In, J, S, 1.f / 30.f), S, false, Up, true);
        }
        char Name[64]; std::snprintf(Name, sizeof Name, "%s", K.Name + 7);
        Print("Saud", Name, X, true);
        Worst = std::fmax(Worst, WorstAfter(X)); HeadCm = std::fmax(HeadCm, X.After[3]);
        Wob = std::fmax(Wob, X.WobbleAfter); WobBefore = std::fmax(WobBefore, X.WobbleBefore);
    }
    std::printf("  worst after %.2f degrees, the head %.2f cm off; wobble (rms change a frame) %.2f -> %.2f\n", Worst, HeadCm, WobBefore, Wob);
    Check(Worst < 1.f && HeadCm < 0.5f, "posture: Saud walks and runs free straight");
    Check(Wob < 0.25f * WobBefore, "posture: no wobble frame to frame");
}

int main()
{
    Stances(); Faults(); Limits(); Gate(); Cases(); Gaits();
    std::printf(Fails ? "\n%d FAILED\n" : "\nall posture checks passed\n", Fails);
    return Fails ? 1 : 0;
}
