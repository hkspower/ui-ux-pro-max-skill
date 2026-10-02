/**
 * The runtime feet over a real clip, with no engine, for Tools/look/
 * plant_preview.py (2026-10-02, "improve plants ik"). Like menu_dump.cpp: not a
 * test -- it lives beside tests/, not in it, so run.sh does not build it; the
 * preview does.
 *
 *   plant_dump CLIP.txt mode=before|after speed=CM_S turn=DEG_S seconds=S
 *              [hz=60] [way=fwd|left] [attack=0|1] [strikeleg=-1|0|1]
 *
 * CLIP.txt is one clip sampled by measure_plants.py: a header (name, loop,
 * seconds, frames, the man's rest ankle and ball heights) and a line a frame
 * of both legs' ankle, ball, hip and knee in the mesh's frame (cm, X forward).
 * The man is moved across flat ground at `speed` -- forward, or to his left
 * for a side walk -- and turned at `turn`, at `hz`, for `seconds`, after a
 * quarter of a second standing still that is not printed: in the game a man
 * standing has his feet on already (they come on over FeetOnSeconds).
 *
 *   before   the clip as the game drew it until now: its clock at its own
 *            rate and its feet where it puts them, wherever the man goes.
 *   after    SaudIK's feet, the way USaudMotionAnimInstance runs them: the
 *            walk's clock at the man's pace (StrideRateMeasured), the clip's
 *            measured plants (SaudPlants.h) deciding which foot is down, held
 *            balls, steps, the hips' carry.
 *
 * Prints JSON: {"name", "mode", "ticks": [[t, cliptime, lx, ly, lz, rx, ry,
 * rz, heldL, heldR, stepL, stepR, downL, downR, ox, oy], ...]} -- each ball's
 * drawn world position, whether it is held or stepping, whether the clip has
 * it down, and the man's origin.
 */
#include "HarnessTypes.h"
#include "../../Source/SaudFighter/Combat/SaudIK.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

using namespace SaudIK;

struct FSample { FVector Ankle[2], Ball[2], Hip[2], Knee[2]; };

static bool ReadClip(const char* Path, std::string& Name, bool& bLoop, float& Seconds, float& AnkleRest, float& BallRest,
                     std::vector<FSample>& Frames)
{
    FILE* F = std::fopen(Path, "r");
    if (!F) return false;
    char Buf[128];
    int Loop = 0, N = 0;
    if (std::fscanf(F, "clip %127s loop %d seconds %f frames %d rest %f %f", Buf, &Loop, &Seconds, &N, &AnkleRest, &BallRest) != 6)
    {
        std::fclose(F);
        return false;
    }
    Name = Buf;
    bLoop = Loop != 0;
    Frames.resize(N);
    for (int I = 0; I < N; ++I)
    {
        FSample& S = Frames[I];
        for (int L = 0; L < 2; ++L)
        {
            FVector* P[4] = { &S.Ankle[L], &S.Ball[L], &S.Hip[L], &S.Knee[L] };
            for (FVector* V : P)
            {
                if (std::fscanf(F, "%f %f %f", &V->X, &V->Y, &V->Z) != 3) { std::fclose(F); return false; }
            }
        }
    }
    std::fclose(F);
    return true;
}

static FVector Lerp(const FVector& A, const FVector& B, float T) { return A + (B - A) * T; }

/** The clip at a time, between its frames (frame f at f / 30 s). */
static FSample At(const std::vector<FSample>& Fr, float Time, bool bLoop)
{
    const int N = static_cast<int>(Fr.size());
    float F = Time * SaudPlants::Fps;
    if (bLoop) F = std::fmod(F, static_cast<float>(N));
    else F = std::fmin(std::fmax(F, 0.f), static_cast<float>(N - 1));
    const int A = static_cast<int>(F);
    const int B = bLoop ? (A + 1) % N : std::min(A + 1, N - 1);
    const float T = F - A;
    FSample S;
    for (int L = 0; L < 2; ++L)
    {
        S.Ankle[L] = Lerp(Fr[A].Ankle[L], Fr[B].Ankle[L], T);
        S.Ball[L] = Lerp(Fr[A].Ball[L], Fr[B].Ball[L], T);
        S.Hip[L] = Lerp(Fr[A].Hip[L], Fr[B].Hip[L], T);
        S.Knee[L] = Lerp(Fr[A].Knee[L], Fr[B].Knee[L], T);
    }
    return S;
}

int main(int argc, char** argv)
{
    if (argc < 2)
    {
        std::fprintf(stderr, "usage: plant_dump CLIP.txt mode=before|after speed=CM_S turn=DEG_S seconds=S [hz=60] "
                             "[way=fwd|left] [attack=0|1] [strikeleg=-1|0|1]\n");
        return 2;
    }
    std::string Name;
    bool bLoop = false;
    float ClipSeconds = 0.f, AnkleRest = 0.f, BallRest = 0.f;
    std::vector<FSample> Frames;
    if (!ReadClip(argv[1], Name, bLoop, ClipSeconds, AnkleRest, BallRest, Frames) || Frames.empty())
    {
        std::fprintf(stderr, "could not read %s\n", argv[1]);
        return 2;
    }
    bool bAfter = true, bLeft = false, bAttack = false;
    float Speed = 0.f, Turn = 0.f, Seconds = 2.f, Hz = 60.f;
    int StrikeLeg = -1;
    for (int I = 2; I < argc; ++I)
    {
        const char* Eq = std::strchr(argv[I], '=');
        if (!Eq) { std::fprintf(stderr, "not key=value: %s\n", argv[I]); return 2; }
        const std::string K(argv[I], Eq - argv[I]);
        const char* V = Eq + 1;
        if (K == "mode") bAfter = std::strcmp(V, "before") != 0;
        else if (K == "speed") Speed = static_cast<float>(std::atof(V));
        else if (K == "turn") Turn = static_cast<float>(std::atof(V));
        else if (K == "seconds") Seconds = static_cast<float>(std::atof(V));
        else if (K == "hz") Hz = static_cast<float>(std::atof(V));
        else if (K == "way") bLeft = std::strcmp(V, "left") == 0;
        else if (K == "attack") bAttack = std::atoi(V) != 0;
        else if (K == "strikeleg") StrikeLeg = std::atoi(V);
        else { std::fprintf(stderr, "unknown key: %s\n", argv[I]); return 2; }
    }
    const SaudPlants::FClip* Plants = SaudPlants::Find(Name.c_str());

    FFeetState St;
    FFeetIn In;
    FBasis B;
    float Yaw = 0.f, ClipTime = 0.f;
    FVector LastHeel[2], LastBall[2];
    bool bHasLast = false;
    const float Dt = 1.f / Hz;
    const int Warm = static_cast<int>(std::lround(0.25f * Hz));
    const int Ticks = Warm + static_cast<int>(std::lround(Seconds * Hz));

    std::printf("{\"name\": \"%s\", \"mode\": \"%s\", \"measured\": %s, \"stride\": %.1f, \"ticks\": [",
                Name.c_str(), bAfter ? "after" : "before", Plants ? "true" : "false", Plants ? Plants->Stride : 0.f);
    for (int Tick = 0; Tick < Ticks; ++Tick)
    {
        // the man: on along his own forward, or his left, turning as he goes
        const bool bWarm = Tick < Warm;
        const float R = FMath::DegreesToRadians(Yaw);
        B.X = FVector(std::cos(R), std::sin(R), 0.f);
        B.Y = FVector(-std::sin(R), std::cos(R), 0.f);
        const FVector Way = bLeft ? B.Y * -1.f : B.X;     // the clips' left is mesh -Y
        const FVector Velocity = bWarm ? FVector::ZeroVector : Way * Speed;
        B.Origin = B.Origin + Velocity * Dt;
        if (!bWarm) Yaw += Turn * Dt;

        // the clip's clock: its own rate before, the man's pace after
        const float Rate = bAfter && bLoop && Plants ? StrideRateMeasured(bWarm ? 0.f : Speed, Plants->Stride, 1.f) : 1.f;
        ClipTime += bWarm ? 0.f : Dt * Rate;
        if (bLoop) ClipTime = std::fmod(ClipTime, ClipSeconds);
        else ClipTime = std::fmin(ClipTime, ClipSeconds);
        const FSample S = At(Frames, ClipTime, bLoop);

        FVector Drawn[2];
        bool bHeld[2] = { false, false }, bStep[2] = { false, false }, bDown[2] = { false, false };
        for (int L = 0; L < 2; ++L)
        {
            bDown[L] = Plants ? ClipFootDown(*Plants, L, ClipTime, bLoop) : S.Ball[L].Z - BallRest < 1.5f;
            Drawn[L] = ToWorld(B, S.Ball[L]);
        }
        if (bAfter)
        {
            In.Mesh = B;
            In.bWanted = true;
            In.bHold = Plants ? HoldsFeetMeasured(bAttack, bWarm || Speed < 40.f, Plants->Stride) : true;
            In.Velocity = Velocity;
            In.ClipSerial = 1;
            In.ClipTime = ClipTime;
            for (int L = 0; L < 2; ++L)
            {
                FFootIn& F = In.Foot[L];
                F.Hip = S.Hip[L]; F.Ankle = S.Ankle[L]; F.Ball = S.Ball[L];
                FVector Fwd = S.Ball[L] - S.Ankle[L];
                Fwd.Z = 0.f;
                Fwd = Fwd.GetSafeNormal();
                if (Fwd.IsNearlyZero()) Fwd = FVector(1.f, 0.f, 0.f);
                F.ToeDir = Fwd; F.FootFwd = Fwd; F.FootUp = FVector::UpVector;
                F.LegLength = FVector::Dist(S.Hip[L], S.Knee[L]) + FVector::Dist(S.Knee[L], S.Ankle[L]);
                F.AnkleRest = AnkleRest; F.BallRest = BallRest;
                F.bStrike = L == StrikeLeg;
                In.Down[L] = Plants ? (ClipFootDown(*Plants, L, ClipTime, bLoop) ? 1.f : 0.f) : -1.f;
                // flat ground at the man's floor, traced under last tick's drawn heel and ball
                const FVector H = bHasLast ? LastHeel[L] : ToWorld(B, S.Ankle[L]);
                const FVector Bw = bHasLast ? LastBall[L] : ToWorld(B, S.Ball[L]);
                F.HeelGround.bHit = F.BallGround.bHit = true;
                F.HeelGround.Point = ToMesh(B, FVector(H.X, H.Y, 0.f));
                F.BallGround.Point = ToMesh(B, FVector(Bw.X, Bw.Y, 0.f));
                F.HeelGround.Normal = F.BallGround.Normal = FVector::UpVector;
            }
            const FFeetPlan Plan = StepFeet(St, In, Dt);
            for (int L = 0; L < 2; ++L)
            {
                const FFootPose P = FinishFoot(St.Hold[L], Plan.Foot[L], In.Foot[L], In.Foot[L].Hip + Plan.Pelvis, Dt);
                Drawn[L] = ToWorld(B, Plan.Foot[L].Ball);
                LastHeel[L] = ToWorld(B, P.Ankle);
                LastBall[L] = Drawn[L];
                bHeld[L] = St.Hold[L].bHeld;
                bStep[L] = St.Hold[L].bStep && St.Hold[L].Progress < 1.f;
            }
            bHasLast = true;
        }
        if (bWarm) continue;
        std::printf("%s\n[%.4f, %.4f, %.2f, %.2f, %.2f, %.2f, %.2f, %.2f, %d, %d, %d, %d, %d, %d, %.2f, %.2f]",
                    Tick > Warm ? "," : "", (Tick - Warm + 1) * Dt, ClipTime, Drawn[0].X, Drawn[0].Y, Drawn[0].Z, Drawn[1].X, Drawn[1].Y,
                    Drawn[1].Z, bHeld[0], bHeld[1], bStep[0], bStep[1], bDown[0], bDown[1], B.Origin.X, B.Origin.Y);
    }
    std::printf("]}\n");
    return 0;
}
