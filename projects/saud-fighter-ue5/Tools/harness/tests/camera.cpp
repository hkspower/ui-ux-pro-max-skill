/**
 * Saud's camera, executed (SaudCamera.h): scripted scenes run at 60 frames a
 * second and the view judged as a player would see it.
 *
 *   camera            the checks
 *   camera --dump F   also every scene's views, one line a frame, to F
 *                     (Tools/harness/camera_paths.py draws them)
 */
#include "../HarnessTypes.h"
#include "../../../Source/SaudFighter/Combat/SaudCamera.h"

#include <cstdio>
#include <cstring>
#include <cmath>
#include <vector>
#include <string>

static int Fails = 0;
static void Check(bool Ok, const char* What)
{
    if (!Ok) { ++Fails; std::printf("  FAIL  %s\n", What); }
}

using namespace SaudCamera;

static FILE* Dump = nullptr;
static const float Dt = 1.f / 60.f;

struct FScene
{
    const char* Name;
    FState S;
    FView V;
    std::vector<FVector> Opp;
    FVector Saud, Vel;
    float LookX = 0.f, LookY = 0.f;
    float T = 0.f;
    explicit FScene(const char* N) : Name(N) {}
    FView Step()
    {
        FInputs In;
        In.Dt = Dt; In.Saud = Saud; In.Velocity = Vel; In.LookX = LookX; In.LookY = LookY;
        In.Opponents = Opp.empty() ? nullptr : Opp.data();
        In.NumOpponents = static_cast<int>(Opp.size());
        V = S.Tick(In);
        T += Dt;
        if (Dump)
        {
            const FVector E = EyeOf(V.Focus, V.Yaw, V.Pitch, V.Arm);
            std::fprintf(Dump, "%s %.4f %.1f %.1f %.1f %.1f %.2f %.2f %.1f %.2f %.1f %.1f %d", Name, T,
                         Saud.X, Saud.Y, E.X, E.Y, V.Yaw, V.Pitch, V.Arm, V.Roll, V.Focus.X, V.Focus.Y,
                         static_cast<int>(Opp.size()));
            for (const FVector& O : Opp) std::fprintf(Dump, " %.1f %.1f", O.X, O.Y);
            std::fprintf(Dump, "\n");
        }
        return V;
    }
    void Run(float Seconds) { for (int I = 0; I < static_cast<int>(Seconds / Dt + 0.5f); ++I) Step(); }
    /** Every man near Saud, and Saud, inside the horizontal picture. */
    float WorstOffAxis() const
    {
        const FVector E = EyeOf(V.Focus, V.Yaw, V.Pitch, V.Arm);
        float W = OffAxisDeg(E, V.Yaw, Saud);
        for (const FVector& O : Opp)
            if (Flat(O - Saud) <= EngageCm) { const float A = OffAxisDeg(E, V.Yaw, O); if (A > W) W = A; }
        return W;
    }
};

static void Alone()
{
    std::printf("ALONE\n");
    FScene A("standing");
    A.S.View.Yaw = 40.f;
    A.Run(3.f);
    Check(std::fabs(Wrap180(A.V.Yaw - 40.f)) < 0.01f, "standing still, the camera stays where it was");
    Check(std::fabs(A.V.Arm - IdleArmCm) < 1.f, "standing still, the boom is the idle length");

    FScene R("run");
    R.S.View.Yaw = 90.f;                 // looking +Y; he runs along +X
    R.Vel = FVector(RunSpeedCm, 0.0, 0.0);
    float Settled = -1.f;
    for (int I = 0; I < 240; ++I)
    {
        R.Saud = R.Saud + R.Vel * Dt;
        R.Step();
        if (Settled < 0.f && std::fabs(Wrap180(R.V.Yaw)) < 5.f) Settled = R.T;
    }
    std::printf("  a run: behind him in %.2f s, the boom %.0f cm, looking %.0f cm ahead\n",
                Settled, R.V.Arm, R.V.Focus.X - R.Saud.X);
    Check(Settled > 0.f && Settled < 1.5f, "running, the camera comes round behind him within 1.5 s");
    Check(R.V.Arm > RunArmCm - 10.f, "running, the boom is out at the run length");
    Check(R.V.Focus.X - R.Saud.X > 60.f, "running, it looks ahead of him");
    R.Vel = FVector(0.0, 0.0, 0.0);
    R.Run(2.f);
    Check(std::fabs(R.V.Arm - IdleArmCm) < 5.f, "stopped, the boom comes back in");
    Check(std::fabs(R.V.Focus.X - R.Saud.X) < 2.f, "stopped, it looks at him again");
}

static void Fight()
{
    std::printf("THE FIGHT\n");
    FScene F("one man");
    F.S.View.Yaw = 0.f;
    F.Opp.push_back(FVector(0.0, 300.0, 0.0));     // a man to his left
    F.Run(2.5f);
    const float Axis = 90.f;
    const float Off = std::fabs(Wrap180(F.V.Yaw - Axis));
    std::printf("  one man 3 m off: the camera %.0f deg off the line between them, boom %.0f cm, worst %.0f deg off-axis\n",
                Off, F.V.Arm, F.WorstOffAxis());
    Check(std::fabs(Off - SideDeg) < 2.f, "a fight: the camera looks across the line between them, SideDeg off it");
    Check(F.WorstOffAxis() < HFovDeg * 0.5f * 0.95f, "a fight: both men in the picture");
    Check(F.V.bFighting, "a man 3 m off is a fight");

    FScene M("three men");
    M.Opp = {FVector(400.0, 300.0, 0.0), FVector(-350.0, 450.0, 0.0), FVector(600.0, -500.0, 0.0)};
    M.Run(3.f);
    std::printf("  three men round him: boom %.0f cm, worst %.0f deg off-axis\n", M.V.Arm, M.WorstOffAxis());
    Check(M.WorstOffAxis() < HFovDeg * 0.5f, "three men round him: all of them and Saud in the picture");
    Check(M.V.Arm > F.V.Arm, "more men, further spread: the boom pulls back");

    FScene Far("far");
    Far.Opp.push_back(FVector(EngageCm + 200.0, 0.0, 0.0));
    Far.Run(1.f);
    Check(!Far.V.bFighting, "a man beyond EngageCm is not a fight");

    // a man circling him slowly: the side does not flip back and forth
    FScene C("circling");
    int Flips = 0, Last = 0;
    for (int I = 0; I < 60 * 12; ++I)
    {
        const float A = 0.5f * C.T;                       // radians: once round in 12.6 s
        C.Opp = {FVector(320.0 * std::cos(A), 320.0 * std::sin(A), 0.0)};
        C.Step();
        if (Last != 0 && C.S.Side != Last) ++Flips;
        Last = C.S.Side;
    }
    std::printf("  a man circling him once: the camera changed sides %d times\n", Flips);
    // a man feinting: stepping 40 degrees round him and back, again and
    // again -- enough that the other side is nearer each time, not by much
    FScene X("feinting");
    int XFlips = 0, XLast = 0;
    for (int I = 0; I < 60 * 6; ++I)
    {
        const float A = (static_cast<int>(X.T / 0.6f) % 2) ? 0.698f : 0.f;
        X.Opp = {FVector(320.0 * std::cos(A), 320.0 * std::sin(A), 0.0)};
        X.Step();
        if (XLast != 0 && X.S.Side != XLast) ++XFlips;
        XLast = X.S.Side;
    }
    std::printf("  a man feinting 40 degrees round him ten times: the camera changed sides %d times\n", XFlips);
    Check(Flips <= 1 && XFlips <= 1, "a man circling or feinting: the camera does not flip sides back and forth");
}

static void Stick()
{
    std::printf("THE STICK\n");
    FScene S("stick");
    S.Opp.push_back(FVector(300.0, 0.0, 0.0));
    S.Run(2.f);
    const float Framed = S.V.Yaw;
    S.LookX = 1.f;
    S.Run(0.5f);
    const float Turned = S.V.Yaw;
    Check(std::fabs(Wrap180(Turned - Framed)) > 60.f, "the stick turns the camera at its old rate");
    S.LookX = 0.f;
    S.Run(1.0f);
    Check(std::fabs(Wrap180(S.V.Yaw - Turned)) < 1.f, "after a turn the framing waits");
    S.Run(2.5f);
    Check(std::fabs(Wrap180(S.V.Yaw - Framed)) < 5.f || std::fabs(Wrap180(S.V.Yaw - Framed + 2 * SideDeg)) < 5.f
          || std::fabs(Wrap180(S.V.Yaw - Framed - 2 * SideDeg)) < 5.f,
          "...and then takes the fight back");
}

static void Blows()
{
    std::printf("BLOWS\n");
    FScene K("kick");
    K.Opp.push_back(FVector(250.0, 0.0, 0.0));
    K.Run(2.f);
    const float Arm0 = K.V.Arm;
    K.S.Kick(1.f, 1.f);
    float Peak = 0.f, Short = 0.f;
    for (int I = 0; I < 30; ++I)
    {
        K.Step();
        if (std::fabs(K.V.Roll) > Peak) Peak = std::fabs(K.V.Roll);
        if (Arm0 - K.V.Arm > Short) Short = Arm0 - K.V.Arm;
    }
    K.Run(0.3f);
    std::printf("  a heavy blow: tips %.1f deg, pushes in %.0f cm, %.2f deg left after 0.8 s\n", Peak, Short, K.V.Roll);
    Check(Peak > 2.f && Peak <= KickRollDeg + 0.01f, "a heavy blow tips the picture, a few degrees");
    Check(Short > 20.f, "a heavy blow pushes the camera in");
    Check(std::fabs(K.V.Roll) < 0.1f, "...and it springs back");

    FScene O("finisher");
    O.Opp.push_back(FVector(250.0, 0.0, 0.0));
    O.Run(2.f);
    const float Yaw0 = O.V.Yaw, ArmF = O.V.Arm;
    O.S.StartOrbit(EOrbit::Finisher);
    float Sweep = 0.f, Closest = 1e9f;
    for (int I = 0; I < 90; ++I)
    {
        O.Step();
        const float D = std::fabs(Wrap180(O.V.Yaw - Yaw0));
        if (D > Sweep) Sweep = D;
        if (O.V.Arm < Closest) Closest = O.V.Arm;
    }
    O.Run(1.5f);
    std::printf("  the finisher: swings %.0f deg round him, in to %.0f%% of the boom, back to %.1f deg after\n",
                Sweep, 100.f * Closest / ArmF, std::fabs(Wrap180(O.V.Yaw - Yaw0)));
    Check(Sweep > 50.f && Sweep <= FinisherOrbit.SweepDeg + 1.f, "the finisher swings the camera round him");
    Check(Closest < ArmF * 0.85f, "...and in");
    Check(std::fabs(Wrap180(O.V.Yaw - Yaw0)) < 3.f, "...and hands it back to the fight");
    O.S.StartOrbit(EOrbit::Finisher);
    O.Run(0.3f);
    O.S.StartOrbit(EOrbit::Knockout);
    Check(O.S.Orbit == EOrbit::Finisher, "a knockout does not cut the finisher's swing short");
}

static void Walls()
{
    std::printf("WALLS\n");
    FState S;
    // open, then a wall 300 cm behind the focus, then gone again
    float Arm = 0.f, MaxJump = 0.f, Prev = -1.f;
    bool Through = false;
    for (int I = 0; I < 600; ++I)
    {
        const float T = I * Dt;
        const bool Wall = T > 2.f && T < 6.f;
        const float Hard = Wall ? 300.f : 1e6f;
        const float Soft = Wall ? 300.f : 600.f + SoftMarginCm;
        Arm = S.WallStep(600.f, Soft, Hard, Dt);
        if (Arm > Hard + 0.01f) Through = true;
        if (Prev >= 0.f && T > 6.f && Arm - Prev > MaxJump) MaxJump = Arm - Prev;
        Prev = Arm;
    }
    Check(!Through, "the boom is never longer than the wall allows");
    Check(MaxJump < 10.f, "after a wall, the boom eases back out (no jump)");
    Check(Arm > 590.f, "...all the way");
    // a wall that comes in slowly: the boom comes in before it touches
    FState W;
    float Gap = 1e9f;
    for (int I = 0; I < 300; ++I)
    {
        const float WallAt = 900.f - I * 2.f;                 // a wall closing in, 2 cm a frame
        const float A = W.WallStep(600.f, WallAt, WallAt, Dt);
        if (WallAt - A < Gap) Gap = WallAt - A;
    }
    std::printf("  a wall closing in: the camera kept at least %.0f cm clear of it\n", Gap);
    Check(Gap > SoftMarginCm * 0.5f, "a wall closing in: the boom comes in before the wall reaches it");
    // the fade
    float F = 0.f;
    for (int I = 0; I < 12; ++I) F = FadeStep(F, true, Dt);
    Check(F >= FadeMax - 0.01f, "a wall between them fades within 0.2 s");
    Check(F <= FadeMax, "...never all the way");
    for (int I = 0; I < 24; ++I) F = FadeStep(F, false, Dt);
    Check(F == 0.f, "...and comes back when it is not");
}

static void Frozen()
{
    std::printf("A FREEZE\n");
    FScene Z("freeze");
    Z.Opp.push_back(FVector(250.0, 0.0, 0.0));
    Z.Run(2.f);
    const FView Before = Z.V;
    FInputs In; In.Dt = 0.f; In.Saud = Z.Saud; In.Opponents = Z.Opp.data(); In.NumOpponents = 1;
    const FView After = Z.S.Tick(In);
    Check(std::fabs(After.Yaw - Before.Yaw) < 1e-3f && std::fabs(After.Arm - Before.Arm) < 1e-2f,
          "a tick of no time moves nothing");
}

int main(int argc, char** argv)
{
    if (argc > 2 && std::strcmp(argv[1], "--dump") == 0) Dump = std::fopen(argv[2], "w");
    Alone();
    Fight();
    Stick();
    Blows();
    Walls();
    Frozen();
    if (Dump) std::fclose(Dump);
    if (Fails) { std::printf("%d FAILED\n", Fails); return 1; }
    std::printf("all camera checks passed\n");
    return 0;
}
