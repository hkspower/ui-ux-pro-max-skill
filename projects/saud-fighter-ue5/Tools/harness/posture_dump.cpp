/**
 * The posture stage over real stances and real clips, with no engine, for
 * Tools/look/posture_preview.py (2026-10-07, Riyadh, "make body Posture and
 * Body Alignment and Straightness"). Like plant_dump.cpp: not a test -- it
 * lives beside tests/, not in it, so run.sh does not build it; the preview
 * does.
 *
 *   posture_dump > cases.json
 *
 * Each case is a pose as the IK's earlier stages leave it -- each man's real
 * guard (SaudStances.h) through the hips' drop (StepFeet), the lean
 * (StepLean) and the look (TurnStep / ShareTurn / PitchAxes), turned bone by
 * bone as the engine turns them, or a frame of Saud's motion capture
 * (stance_clips.h) -- and the same pose after SaudIK::StepPosture's turns.
 * Prints JSON: {"cases": [{"name", "why", "view": "back"|"top", "before":
 * {joints}, "after": {joints}, "faults": [[before, after] x 6]}, ...]}, the
 * joints in the mesh's frame (cm, X his facing, Y his right, Z up), the
 * faults as tests/posture.cpp prints them: hips, shoulders, trunk (degrees),
 * head off his spine (cm), eyes (degrees), twist (degrees).
 */
#include "HarnessTypes.h"
#include "../../Source/SaudFighter/Combat/SaudIK.h"
#include "stance_clips.h"

#include <cmath>
#include <cstdio>
#include <string>

using namespace SaudIK;
using SaudStances::FJoints;
using SaudStances::FStance;

static const float Pi = 3.14159265f;
static const FVector Up(0.0, 0.0, 1.0);

static void Turn(FJoints& J, EPostureBone B, const FVector& Axis, float Deg) { TurnJoints(J, B, Axis, Deg); }

static FJoints Apply(FJoints J, const FPostureFix& F)
{
    for (int I = 0; I < F.Num; ++I) Turn(J, F.Turn[I].Bone, F.Turn[I].Axis, F.Turn[I].Degrees);
    return J;
}

static FJoints PoseIK(FJoints J, const FVector& Move, const FVector& LeanAxis, float LeanDeg, const FChainTurn* Chain = nullptr)
{
    FVector* Moved[] = { &J.Pelvis, &J.Hip[0], &J.Hip[1], &J.Spine[0], &J.Spine[1], &J.Spine[2], &J.Neck, &J.Head,
                         &J.Shoulder[0], &J.Shoulder[1] };
    for (FVector* P : Moved) *P = *P + Move;
    if (std::fabs(LeanDeg) > 1e-5f) Turn(J, EPostureBone::Pelvis, LeanAxis, LeanDeg);
    if (Chain)
    {
        FVector Axes[ChainBones];
        PitchAxes(*Chain, FVector(1.0, 0.0, 0.0), Up, Axes);
        for (int I = 0; I < ChainBones; ++I)
        {
            Turn(J, (EPostureBone)(I + 1), Up, Chain->Yaw[I]);
            Turn(J, (EPostureBone)(I + 1), Axes[I], Chain->Pitch[I]);
        }
    }
    return J;
}

static FBasis Facing(float YawDeg)
{
    FBasis B; const float R = YawDeg * Pi / 180.f;
    B.X = FVector(std::cos(R), std::sin(R), 0.0); B.Y = FVector(-std::sin(R), std::cos(R), 0.0);
    return B;
}

static void V(const char* Name, const FVector& P, bool bComma = true)
{
    std::printf("\"%s\": [%.3f, %.3f, %.3f]%s", Name, P.X, P.Y, P.Z, bComma ? ", " : "");
}
static void Joints(const FJoints& J)
{
    std::printf("{");
    V("pelvis", J.Pelvis); V("hip_l", J.Hip[0]); V("hip_r", J.Hip[1]); V("knee_l", J.Knee[0]); V("knee_r", J.Knee[1]);
    V("ankle_l", J.Ankle[0]); V("ankle_r", J.Ankle[1]); V("ball_l", J.Ball[0]); V("ball_r", J.Ball[1]);
    V("spine_01", J.Spine[0]); V("spine_02", J.Spine[1]); V("spine_03", J.Spine[2]); V("neck", J.Neck); V("head", J.Head);
    V("shoulder_l", J.Shoulder[0]); V("shoulder_r", J.Shoulder[1]); V("side", J.HeadSide, false);
    std::printf("}");
}

static bool First = true;
static void Case(const char* Name, const char* Why, const char* View, const FJoints& Before, const FPostureFix& F,
                 float RefTwist = 0.f)
{
    const FJoints After = Apply(Before, F);
    // the faults against his reference, as the stage measured the pose before and the pose it left
    const FPostureFaults B = F.Before, A = F.After;
    std::printf("%s\n  {\"name\": \"%s\", \"why\": \"%s\", \"view\": \"%s\", \"before\": ", First ? "" : ",", Name, Why, View);
    Joints(Before);
    std::printf(", \"after\": ");
    Joints(After);
    std::printf(", \"faults\": [[%.2f, %.2f], [%.2f, %.2f], [%.2f, %.2f], [%.2f, %.2f], [%.2f, %.2f], [%.2f, %.2f]], \"ref_twist\": %.3f}",
                B.HipRoll, A.HipRoll, B.ShoulderRoll, A.ShoulderRoll, B.TrunkTilt, A.TrunkTilt, B.HeadOff, A.HeadOff,
                B.EyeRoll, A.EyeRoll, B.Twist, A.Twist, RefTwist);
    First = false;
}

static FPostureIn Standing(bool bTwist)
{
    FPostureIn In; In.bOn = true; In.bTwist = bTwist; In.FeetShare = 1.f; return In;
}

int main()
{
    std::printf("{\"cases\": [");
    // standing, looking at a man 60 degrees to his left and 25 up
    for (const char* Set : { "Saud", "Boss" })
    {
        const FStance& S = *SaudStances::Find(Set);
        FTurn T; T.Weight.Lin = 1.f;
        for (int I = 0; I < 120; ++I) TurnStep(T, 0.f, 60.f, 25.f, true, false, false, false, 1.f / 60.f);
        const FChainTurn Ch = ShareTurn(T);
        const FJoints J = PoseIK(S.Joints, FVector::ZeroVector, FVector(1.0, 0.0, 0.0), 0.f, &Ch);
        FPostureState St; St.Share.Lin = 1.f; St.Twist.Lin = 1.f;
        const FPostureFix F = StepPosture(St, Standing(true), J, S, 1.f / 60.f);
        Case(std::string(Set) == "Saud" ? "Saud standing, looking" : "AL-WAHSH standing, looking",
             "at a man 60 deg to his left, 25 up: the look's chest share and nod", "back", J, F);
    }
    // ZAYOS turning on the spot at 90 deg/s, his feet held and stepping: the worst frame of the hips on the feet
    {
        const FStance& S = *SaudStances::Find("Zayos");
        const FJoints& G = S.Joints;
        FFeetIn In; In.bWanted = true; In.bHold = true; In.bSettle = true;
        const float AnkleRest = (float)std::fmin(G.Ankle[0].Z, G.Ankle[1].Z), BallRest = (float)std::fmin(G.Ball[0].Z, G.Ball[1].Z);
        for (int Sd = 0; Sd < 2; ++Sd)
        {
            FFootIn& Fo = In.Foot[Sd];
            Fo.Hip = G.Hip[Sd]; Fo.Ankle = G.Ankle[Sd]; Fo.Ball = G.Ball[Sd];
            Fo.LegLength = (float)(FVector::Dist(G.Hip[Sd], G.Knee[Sd]) + FVector::Dist(G.Knee[Sd], G.Ankle[Sd]));
            Fo.AnkleRest = AnkleRest; Fo.BallRest = BallRest;
        }
        FFeetState St; FPostureState P;
        FJoints WorstJ = G; FPostureFix WorstF; float Worst = -1.f;
        for (int I = 0; I <= 240; ++I)
        {
            In.Mesh = Facing(90.f * I / 60.f);
            for (int Sd = 0; Sd < 2; ++Sd)
            {
                const FVector Pts[2] = { ToWorld(In.Mesh, In.Foot[Sd].Ankle), ToWorld(In.Mesh, In.Foot[Sd].Ball) };
                for (int K = 0; K < 2; ++K)
                {
                    FGroundPoint& Gp = K ? In.Foot[Sd].BallGround : In.Foot[Sd].HeelGround;
                    Gp.bHit = true; Gp.Point = ToMesh(In.Mesh, FVector(Pts[K].X, Pts[K].Y, 0.0)); Gp.Normal = Up;
                }
            }
            const FFeetPlan Plan = StepFeet(St, In, 1.f / 60.f);
            FJoints J = PoseIK(G, Plan.Pelvis, FVector(1.0, 0.0, 0.0), 0.f);
            for (int Sd = 0; Sd < 2; ++Sd) J.Ball[Sd] = Plan.Foot[Sd].Ball;
            FPostureIn PIn = Standing(true); PIn.FeetShare = Plan.Alpha;
            const FPostureFix F = StepPosture(P, PIn, J, S, 1.f / 60.f);
            if (I > 30 && std::fabs(F.Before.Twist) > Worst) { Worst = std::fabs(F.Before.Twist); WorstJ = J; WorstF = F; }
        }
        Case("ZAYOS turning on the spot", "90 deg/s, feet held, stepping; above; dashed: his stance's hips", "top", WorstJ, WorstF, S.Twist);
    }
    // Saud running a curve: 341 cm/s round 3 m, the lean whole
    {
        const FStance& S = *SaudStances::Find("Saud");
        FLean L; FPostureState P;
        FJoints J = S.Joints; FPostureFix F;
        for (int I = 0; I <= 120; ++I)
        {
            const float W = 341.f / 300.f, Th = W * I / 60.f;
            StepLean(L, FVector(-std::sin(Th), std::cos(Th), 0.0) * 341.f, 0.45f * 341.f, 341.f, true, 1.f / 60.f);
            FVector Axis; float Deg = 0.f;
            LeanAxisAngle(L, Axis, Deg);
            const FVector AxisM = DirToMesh(Facing(Th * 180.f / Pi + 90.f), Axis);
            J = PoseIK(S.Joints, FVector::ZeroVector, AxisM, Deg);
            FPostureIn PIn = Standing(false);
            PIn.BodyUp = RotateAbout(Up, AxisM, Deg * Pi / 180.f);
            F = StepPosture(P, PIn, J, S, 1.f / 60.f);
        }
        Case("Saud running a curve", "341 cm/s round 3 m: the lean kept, the eyes righted", "back", J, F);
    }
    // Saud's motion-capture walk and run: the worst frame of each
    for (int C : { 1, 4 })
    {
        const StanceClips::FClip& K = StanceClips::Clips[C];
        const FStance& S = *SaudStances::Find("Saud");
        FPostureState P; P.Share.Lin = 1.f;
        FPostureIn In = Standing(false); In.Gait = 1.f;
        int Pick = 0; float Worst = -1.f; FPostureFix PickF;
        for (int F = 0; F < K.Frames; ++F)
        {
            const FPostureFix Fx = StepPosture(P, In, K.Frame[F], S, 1.f / 30.f);
            const float M = std::fmax(std::fmax(std::fabs(Fx.Before.EyeRoll), std::fabs(Fx.Before.ShoulderRoll)),
                                      std::fmax(std::fabs(Fx.Before.HipRoll), std::fabs(Fx.Before.HeadOff) * 2.f));
            if (M > Worst) { Worst = M; Pick = F; PickF = Fx; }
        }
        char Name[96], Why[96];
        std::snprintf(Name, sizeof Name, "Saud's free %s", C == 1 ? "walk" : "run");
        std::snprintf(Why, sizeof Why, "%s, its worst frame, %d of %d: straight", K.Name, Pick, K.Frames);
        Case(Name, Why, "back", K.Frame[Pick], PickF);
    }
    std::printf("\n]}\n");
    return 0;
}
