/**
 * The runtime IK's arithmetic, executed.
 *
 * SaudIK.h decides where a limb goes over the clip: the two-bone solve, a
 * foot's share of the ground and the pelvis's drop, the striking hand's
 * pull to the victim, the head's clamped look. This checks each against
 * what it claims -- lengths kept, bends toward the pole, limits held -- at
 * every angle, and checks the strike-to-limb table against the one
 * build_motion.py wrote into DT_SaudMotion.csv.
 */
#include "../HarnessTypes.h"
#include "../../../Source/SaudFighter/Combat/SaudIK.h"

#include <cstdio>
#include <cstring>
#include <cmath>
#include <string>
#include <vector>

static int Fails = 0;
static void Check(bool Ok, const char* What)
{
    if (!Ok) { ++Fails; std::printf("  FAIL  %s\n", What); }
}
static bool Near(float A, float B, float Eps = 1e-3f) { return std::fabs(A - B) <= Eps; }

using namespace SaudIK;

static FVector Rotate(const FVector& V, float Radians)
{
    const float C = std::cos(Radians), S = std::sin(Radians);
    return FVector(V.X * C - V.Y * S, V.X * S + V.Y * C, V.Z);
}

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
    Check(Near(FVector::Dist(Hip, R.End), (A + B) * MaxStretch, 1e-2f), "...and the limb stops at 99.5 %");
    Check(Near(FVector::Dist(Hip, R.Mid), A) && Near(FVector::Dist(R.Mid, R.End), B), "...with its lengths");
    Check(R.Mid.X > 0.5f, "...and still bent toward the pole");

    // Rotation invariance: turn everything about Z, the answer turns with it.
    int Bad = 0;
    for (int I = 0; I < 72; ++I)
    {
        const float Ang = I * 5.f * 3.14159265f / 180.f;
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
}

// -------------------------------------------------------------------- feet

static void Feet()
{
    std::printf("FEET  (planted under %.0f cm, swinging over %.0f)\n", PlantHeight, PlantFade);
    Check(PlantAlpha(0.f) == 1.f && PlantAlpha(PlantHeight) == 1.f, "on the floor: planted");
    Check(PlantAlpha(PlantFade) == 0.f && PlantAlpha(60.f) == 0.f, "in the air: swinging");
    Check(Near(PlantAlpha((PlantHeight + PlantFade) * 0.5f), 0.5f), "halfway between: half");

    FFootGround L, R;
    L.bHit = R.bHit = true;
    L.GroundDelta = -12.f; R.GroundDelta = -3.f;
    Check(Near(PelvisOffset(L, R), -12.f), "the pelvis goes down to the lower foot");
    Check(Near(FootOffset(L), -12.f) && Near(FootOffset(R), -3.f), "each foot to its own ground");

    R.GroundDelta = +9.f;
    Check(Near(PelvisOffset(L, R), -12.f), "a step up under one foot does not lift the hips");
    L.GroundDelta = +5.f;
    Check(PelvisOffset(L, R) == 0.f, "both feet on higher ground: the hips stay (the capsule rose)");

    L.GroundDelta = -70.f; R.GroundDelta = -70.f;
    Check(Near(PelvisOffset(L, R), -MaxPelvisDrop), "a drop is not reached for");

    L.GroundDelta = -20.f; L.FootHeight = 50.f;       // swinging over a hole
    R.GroundDelta = -2.f; R.FootHeight = 0.f;
    Check(Near(PelvisOffset(L, R), -2.f), "a swinging foot has no say in the hips");
    Check(FootOffset(L) == 0.f, "...and takes none of the ground");
    L.FootHeight = 19.f;
    Check(Near(FootOffset(L), -10.f), "half planted: half the ground");

    FFootGround Miss;                                  // bHit false
    Check(PelvisOffset(Miss, R) == FootOffset(R) && FootOffset(Miss) == 0.f, "a missed trace is flat ground");

    // Tilt: a 20 degree slope tilts the foot 20; a 50 degree one, 30.
    FFootGround S; S.bHit = true; S.FootHeight = 0.f;
    S.Normal = FVector(std::sin(20.f * 3.14159265f / 180.f), 0.f, std::cos(20.f * 3.14159265f / 180.f));
    FVector N = FootNormal(S);
    Check(Near(std::acos(N.Z) * 180.f / 3.14159265f, 20.f, 0.05f), "a 20 degree slope tilts the foot 20");
    Check(N.X > 0.f, "...the slope's way");
    S.Normal = FVector(std::sin(50.f * 3.14159265f / 180.f), 0.f, std::cos(50.f * 3.14159265f / 180.f));
    N = FootNormal(S);
    Check(Near(std::acos(N.Z) * 180.f / 3.14159265f, MaxFootTiltDegrees, 0.05f), "a 50 degree slope tilts it 30");
    S.FootHeight = 60.f;
    Check(Near(FootNormal(S).Z, 1.f), "a swinging foot is not tilted");
    Check(Near(FootNormal(Miss).Z, 1.f), "no ground, no tilt");

    // Settle: frame-rate independent.
    float A = 0.f, B = 0.f;
    for (int I = 0; I < 60; ++I) A = Settle(A, -10.f, FootSettleRate, 1.f / 60.f);
    for (int I = 0; I < 30; ++I) B = Settle(B, -10.f, FootSettleRate, 1.f / 30.f);
    Check(Near(A, B, 0.05f) && A < -9.9f, "settling reaches the same place at 30 and 60 Hz");
}

// ------------------------------------------------------------------- hands

static void Hands()
{
    std::printf("HANDS  (the striking limb, and where it lands)\n");

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
    Check(ContactAlpha(0.13f, 0.07f, 0.06f) == 1.f, "full on the last");
    Check(Near(ContactAlpha(0.18f, 0.07f, 0.06f), 0.5f), "half at 50 ms into the recovery");
    Check(ContactAlpha(0.30f, 0.07f, 0.06f) == 0.f, "gone by 100 ms into it");
    Check(Near(ContactAlpha(0.04f, 0.07f, 0.06f), 0.5f), "half at 30 ms before the first active frame");
    // Monotone in, flat, monotone out.
    float Prev = -1.f; bool Ok = true; bool Falling = false;
    for (int I = 0; I <= 30; ++I)
    {
        const float A = ContactAlpha(I * 0.01f, 0.07f, 0.06f);
        if (Falling && A > Prev + 1e-6f) Ok = false;
        if (A < Prev - 1e-6f) Falling = true;
        Prev = A;
    }
    Check(Ok, "rises once and falls once");

    // The fist lands on the capsule's surface at the clip's height, on the
    // line from the shoulder to the man.
    const FVector Shoulder(0.f, 20.f, 140.f), Fist(90.f, 20.f, 135.f);
    const FVector Man(80.f, 30.f, 0.f);       // 81 cm off the shoulder, inside a 62 cm arm + 34 cm capsule
    const float Radius = 34.f, Arm = 62.f;
    FVector T = ContactTarget(Shoulder, Fist, Man, Radius, Arm);
    Check(Near(T.Z, 135.f), "the clip decides the height");
    {
        FVector D = T - Man; D.Z = 0.f;
        Check(Near(D.Size(), Radius, 0.05f), "the fist is on the capsule's surface");
        FVector ToMan = Man - Shoulder; ToMan.Z = 0.f;
        FVector ToT = T - Shoulder; ToT.Z = 0.f;
        Check(FVector::CrossProduct(ToMan.GetSafeNormal(), ToT.GetSafeNormal()).Size() < 1e-3f, "...on the line to him");
    }
    // Out of reach: the arm's full stretch, his way.
    T = ContactTarget(Shoulder, Fist, FVector(300.f, 30.f, 0.f), Radius, Arm);
    {
        FVector ToT = T - Shoulder; ToT.Z = 0.f;
        Check(Near(ToT.Size(), Arm * MaxStretch, 0.05f), "a man out of reach: full stretch");
    }
    // Inside the capsule already: the target is at the root, not behind it.
    T = ContactTarget(Shoulder, Fist, FVector(10.f, 20.f, 0.f), Radius, Arm);
    {
        FVector ToT = T - Shoulder; ToT.Z = 0.f;
        Check(ToT.Size() < 1e-3f, "a man on top of you: the fist stays at the shoulder, never behind");
    }
    // Every angle.
    int Bad = 0;
    for (int I = 0; I < 72; ++I)
    {
        const float Ang = I * 5.f * 3.14159265f / 180.f;
        FVector A = ContactTarget(Shoulder, Fist, Man, Radius, Arm);
        FVector B = ContactTarget(Rotate(Shoulder, Ang), Rotate(Fist, Ang), Rotate(Man, Ang), Radius, Arm);
        if (FVector::Dist(Rotate(A, Ang), B) > 1e-2f) ++Bad;
    }
    Check(Bad == 0, "the contact turns with the fight, 72 angles");
}

// -------------------------------------------------------------------- head

static void Head()
{
    std::printf("HEAD  (yaw to %.0f, pitch to %.0f, within %.0f cm)\n", LookMaxYawDegrees, LookMaxPitchDegrees, LookReach);
    const FVector Eyes(0.f, 0.f, 165.f);
    const FVector F(1.f, 0.f, 0.f);
    const float Deg = 180.f / 3.14159265f;

    FVector D = LookDirection(Eyes, F, FVector(200.f, 0.f, 165.f), true);
    Check(Near(D.X, 1.f), "straight ahead: ahead");
    D = LookDirection(Eyes, F, FVector(200.f, 0.f, 165.f), false);
    Check(Near(D.X, 1.f), "no target: ahead");
    D = LookDirection(Eyes, F, FVector(2000.f, 500.f, 165.f), true);
    Check(Near(D.X, 1.f) && Near(D.Y, 0.f), "too far: ahead");

    D = LookDirection(Eyes, F, FVector(100.f, 100.f, 165.f), true);
    Check(Near(std::atan2(D.Y, D.X) * Deg, 45.f, 0.05f), "45 degrees left is 45 degrees left");
    D = LookDirection(Eyes, F, FVector(-100.f, 10.f, 165.f), true);
    Check(Near(std::atan2(D.Y, D.X) * Deg, LookMaxYawDegrees, 0.05f), "behind on the left: held at the limit, left");
    D = LookDirection(Eyes, F, FVector(-100.f, -10.f, 165.f), true);
    Check(Near(std::atan2(D.Y, D.X) * Deg, -LookMaxYawDegrees, 0.05f), "behind on the right: held at the limit, right");
    D = LookDirection(Eyes, F, FVector(100.f, 0.f, 165.f + 100.f), true);
    Check(Near(std::asin(D.Z) * Deg, LookMaxPitchDegrees, 0.05f), "45 up is held at 30");
    D = LookDirection(Eyes, F, FVector(100.f, 0.f, 165.f - 20.f), true);
    Check(Near(std::asin(D.Z) * Deg, -std::atan2(20.f, 100.f) * Deg, 0.05f), "a little down is a little down");
    Check(Near(D.Size(), 1.f), "unit length");

    int Bad = 0;
    for (int I = 0; I < 72; ++I)
    {
        const float Ang = I * 5.f * 3.14159265f / 180.f;
        const FVector T(60.f, 140.f, 190.f);
        FVector A = LookDirection(Eyes, F, T, true);
        FVector B = LookDirection(Eyes, Rotate(F, Ang), Rotate(T, Ang), true);
        if (FVector::Dist(Rotate(A, Ang), B) > 1e-3f) ++Bad;
    }
    Check(Bad == 0, "the look turns with the facing, 72 angles");
}

int main()
{
    Solve(); Feet(); Hands(); Head();
    std::printf(Fails ? "\n%d FAILED\n" : "\nall IK checks passed\n", Fails);
    return Fails ? 1 : 0;
}
