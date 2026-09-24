/**
 * The fight's geometry, executed.
 *
 * This is the first thing in the Unreal build that has ever run. It does not
 * prove the project compiles against an engine — nothing here can — but the
 * arithmetic that decides where a punch reaches, which way a fighter faces,
 * where a stick points and where an arena ends is now checked rather than
 * asserted, and it is checked the way the Unity port's is: by properties over
 * every angle, not by a handful of examples pointing along +X.
 */
#include "../HarnessTypes.h"
#include "../../../Source/SaudFighter/Combat/SaudArena.h"

#include <cstdio>
#include <cmath>

static int Fails = 0;
static void Check(bool Ok, const char* What)
{
    if (!Ok) { ++Fails; std::printf("  FAIL  %s\n", What); }
}

static FVector Rotate(const FVector& V, float Radians)
{
    const float C = std::cos(Radians), S = std::sin(Radians);
    return FVector(V.X * C - V.Y * S, V.X * S + V.Y * C, V.Z);
}

// ----------------------------------------------------------------- hitbox

static void Hitbox()
{
    std::printf("HITBOX  (the Jab: reach 130 cm, lateral tolerance 55 cm)\n");
    const float Reach = 129.6f, Lateral = 55.f;
    const FVector O(0.f, 0.f, 0.f), F(1.f, 0.f, 0.f);

    Check(SaudArena::InHitbox(O, F, FVector(100.f, 0.f, 0.f), Reach, Lateral),
          "in front, in reach");
    Check(!SaudArena::InHitbox(O, F, FVector(300.f, 0.f, 0.f), Reach, Lateral),
          "in front, too far");
    Check(!SaudArena::InHitbox(O, F, FVector(-140.f, 0.f, 0.f), Reach, Lateral),
          "behind");
    Check(SaudArena::InHitbox(O, F, FVector(100.f, 40.f, 0.f), Reach, Lateral),
          "in front, just off the line");
    Check(!SaudArena::InHitbox(O, F, FVector(100.f, 140.f, 0.f), Reach, Lateral),
          "in front, well off the line");
    Check(SaudArena::InHitbox(O, F, FVector(100.f, 0.f, 500.f), Reach, Lateral),
          "height is ignored");

    // The property the strip could never have: turn the pair together and
    // nothing about the strike changes.
    std::printf("  rotation invariance, 72 angles x 500 sample points\n");
    int Mismatches = 0, Hits = 0;
    unsigned Seed = 7u;
    auto Rand = [&Seed]() {
        Seed = Seed * 1664525u + 1013904223u;
        return (float)((Seed >> 8) & 0xFFFF) / 65535.f;
    };
    for (int P = 0; P < 500; ++P)
    {
        const FVector Local((Rand() * 2.f - 1.f) * 400.f, (Rand() * 2.f - 1.f) * 400.f, 0.f);
        const bool Baseline = SaudArena::InHitbox(O, F, Local, Reach, Lateral);
        if (Baseline) { ++Hits; }
        for (int A = 1; A < 72; ++A)
        {
            const float Th = A * 2.f * 3.14159265358979f / 72.f;
            const FVector RF = Rotate(F, Th);
            const FVector RO(1700.f, -900.f, 0.f);      // and not anchored to the origin
            const FVector RP = RO + Rotate(Local, Th);
            if (SaudArena::InHitbox(RO, RF, RP, Reach, Lateral) != Baseline) { ++Mismatches; }
        }
    }
    std::printf("  %d of 500 sample points land inside the box\n", Hits);
    Check(Mismatches == 0, "rotation invariant");
    Check(Hits > 20, "and the box is not empty");
}

// ------------------------------------------------------------------ guard

static void Guard()
{
    std::printf("\nGUARD\n");
    const FVector F(1.f, 0.f, 0.f);
    Check(SaudArena::Covers(F, FVector(200.f, 0.f, 0.f)), "a blow from the front is covered");
    Check(!SaudArena::Covers(F, FVector(-200.f, 0.f, 0.f)), "one from behind is not");
    Check(SaudArena::Covers(F, FVector(10.f, 300.f, 0.f)), "one from the front quarter is");
    Check(!SaudArena::Covers(F, FVector(-10.f, 300.f, 0.f)), "one from behind the shoulder is not");

    // Over the whole circle: covered exactly where the attacker is in front.
    int Wrong = 0;
    for (int A = 0; A < 360; ++A)
    {
        const float Th = A * 3.14159265358979f / 180.f;
        const FVector To(std::cos(Th) * 250.f, std::sin(Th) * 250.f, 0.f);
        const bool Front = std::cos(Th) > 0.f;
        if (SaudArena::Covers(F, To) != Front) { ++Wrong; }
    }
    Check(Wrong <= 2, "the guard is exactly the front hemisphere");
}

// ----------------------------------------------------------------- camera

static void Camera()
{
    std::printf("\nSTICK  (pushed away from you, with the camera turned)\n");
    // Camera looking down +X: forward on the stick is +X.
    FVector W = SaudArena::CameraRelative(0.f, 1.f, 0.f);
    Check(W.X > 0.99f && FMath::Abs(W.Y) < 0.01f, "camera at 0 deg: forward is +X");
    W = SaudArena::CameraRelative(1.f, 0.f, 0.f);
    Check(W.Y > 0.99f && FMath::Abs(W.X) < 0.01f, "camera at 0 deg: right is +Y");

    // Turn the camera a quarter and forward turns with it.
    W = SaudArena::CameraRelative(0.f, 1.f, 90.f);
    Check(W.Y > 0.99f, "camera at 90 deg: forward is +Y");
    W = SaudArena::CameraRelative(0.f, 1.f, 180.f);
    Check(W.X < -0.99f, "camera at 180 deg: forward is -X");

    // Whatever the camera is doing, full stick is full speed and no more:
    // the diagonal must not be faster than the cardinal.
    int TooFast = 0, TooSlow = 0;
    for (int Yaw = 0; Yaw < 360; Yaw += 7)
    {
        const FVector Diag = SaudArena::CameraRelative(1.f, 1.f, (float)Yaw);
        const FVector Card = SaudArena::CameraRelative(0.f, 1.f, (float)Yaw);
        if (Diag.Size2D() > 1.0001f) { ++TooFast; }
        if (FMath::Abs(Card.Size2D() - 1.f) > 1e-3f) { ++TooSlow; }
    }
    Check(TooFast == 0, "a diagonal is never faster than a cardinal");
    Check(TooSlow == 0, "and a cardinal is always full speed");

    // Half a stick stays half: walking slowly has to be possible.
    const FVector Half = SaudArena::CameraRelative(0.f, 0.5f, 33.f);
    Check(FMath::Abs(Half.Size2D() - 0.5f) < 1e-3f, "half a stick is half speed");
}

// ------------------------------------------------------------------ arena

static void Arena()
{
    std::printf("\nARENA  (a circle, not a strip)\n");
    const FVector C(400.f, -250.f, 0.f);
    const float R = 1100.f;

    Check(SaudArena::InCircle(C, C, R), "the middle is inside");
    Check(!SaudArena::InCircle(FVector(C.X + R + 10.f, C.Y, 0.f), C, R), "past the rim is not");

    // Clamping never moves someone who is already inside, always lands
    // someone outside exactly on the rim, and never changes their height.
    int Moved = 0, OffRim = 0, Lifted = 0;
    unsigned Seed = 11u;
    auto Rand = [&Seed]() {
        Seed = Seed * 1664525u + 1013904223u;
        return (float)((Seed >> 8) & 0xFFFF) / 65535.f;
    };
    for (int I = 0; I < 4000; ++I)
    {
        const FVector P(C.X + (Rand() * 2.f - 1.f) * 2000.f,
                        C.Y + (Rand() * 2.f - 1.f) * 2000.f,
                        Rand() * 300.f);
        const FVector Q = SaudArena::ClampToCircle(P, C, R);
        const bool WasInside = SaudArena::InCircle(P, C, R);
        if (WasInside && (Q - P).Size2D() > 1e-3f) { ++Moved; }
        if (!WasInside && FMath::Abs((Q - C).Size2D() - R) > 1e-2f) { ++OffRim; }
        if (FMath::Abs(Q.Z - P.Z) > 1e-4f) { ++Lifted; }
    }
    std::printf("  4000 points around a %.0f m arena\n", R / 100.f);
    Check(Moved == 0, "anyone already inside is left where he is");
    Check(OffRim == 0, "anyone outside lands on the rim");
    Check(Lifted == 0, "and nobody is lifted off his floor");
}

// ------------------------------------------------------------------ crowd

static void Crowd()
{
    std::printf("\nCROWD  (where a wave stands around him)\n");
    const FVector Player(0.f, 0.f, 0.f);
    const float Range = 200.f;

    // The worst case first: a whole wave arriving from the same direction,
    // which is what a crowd chasing him down a street actually is. Then a
    // wave spread around him. Neither may put two fighters on one spot.
    for (int Spread = 0; Spread < 2; ++Spread)
    {
        float MinGap = 1e9f, MinFromPlayer = 1e9f;
        FVector Spots[6];
        for (int I = 0; I < 6; ++I)
        {
            const float Th = Spread ? I * 2.f * 3.14159265358979f / 6.f : 0.9f;
            const FVector From(std::cos(Th) * 900.f, std::sin(Th) * 900.f, 0.f);
            float Bearing, Lane;
            SaudArena::CrowdSlot(I, Bearing, Lane);
            Spots[I] = SaudArena::FlankSpot(Player, From, Bearing, Range, Lane);
            MinFromPlayer = FMath::Min(MinFromPlayer, (Spots[I] - Player).Size2D());
        }
        for (int I = 0; I < 6; ++I)
        {
            for (int J = I + 1; J < 6; ++J)
            {
                MinGap = FMath::Min(MinGap, (Spots[I] - Spots[J]).Size2D());
            }
        }
        std::printf("  six enemies %s: wanted spots %.0f cm apart at the nearest,"
                    " nearest to him %.0f cm\n",
                    Spread ? "from all round " : "from one side  ", MinGap, MinFromPlayer);
        Check(MinFromPlayer > Range * 0.9f, "nobody stands on top of him");
        if (!Spread)
        {
            Check(MinGap > 90.f, "a wave from one direction does not stack on itself");
        }

        // Where two of them do want the same ground, the crowd pushes off
        // itself. Four rounds is four frames of it.
        const float Gap = 140.f;
        for (int Round = 0; Round < 4; ++Round)
        {
            for (int I = 0; I < 6; ++I)
            {
                for (int J = 0; J < 6; ++J)
                {
                    if (I != J) { Spots[I] = SaudArena::PushApart(Spots[I], Spots[J], Gap); }
                }
            }
        }
        float Relaxed = 1e9f;
        for (int I = 0; I < 6; ++I)
        {
            for (int J = I + 1; J < 6; ++J)
            {
                Relaxed = FMath::Min(Relaxed, (Spots[I] - Spots[J]).Size2D());
            }
        }
        std::printf("                   after four frames of pushing off each other: %.0f cm\n",
                    Relaxed);
        Check(Relaxed > Gap * 0.85f, "the crowd relaxes into a ring rather than a heap");
        Check(Relaxed >= MinGap - 1e-3f, "and pushing apart never makes it worse");
    }

    // A fighter standing exactly on another still steps off, rather than
    // dividing by a zero-length direction.
    const FVector Same(10.f, 20.f, 0.f);
    const FVector Stepped = SaudArena::PushApart(Same, Same, 100.f);
    Check((Stepped - Same).Size2D() > 40.f, "two in exactly the same place still separate");
    Check(SaudArena::PushApart(FVector(500.f, 0.f, 0.f), Same, 100.f).X == 500.f,
          "and anyone already clear is left alone");

    // A spot is always the range out, whatever the bearing, and the bearing
    // is measured off the line he is already on -- so an enemy behind the
    // player stays behind him rather than teleporting to one side.
    int WrongRange = 0, Crossed = 0;
    for (int A = 0; A < 360; A += 5)
    {
        const float Th = A * 3.14159265358979f / 180.f;
        const FVector From(std::cos(Th) * 700.f, std::sin(Th) * 700.f, 0.f);
        const FVector S = SaudArena::FlankSpot(Player, From, 40.f, Range, 0.f);
        if (FMath::Abs((S - Player).Size2D() - Range) > 1e-2f) { ++WrongRange; }
        // Within the bearing of where he came from: 40 degrees, no more.
        const float Was = std::atan2(From.Y, From.X);
        const float Now = std::atan2(S.Y - Player.Y, S.X - Player.X);
        float D = Now - Was;
        while (D > 3.14159265f) { D -= 2.f * 3.14159265f; }
        while (D < -3.14159265f) { D += 2.f * 3.14159265f; }
        if (FMath::Abs(FMath::RadiansToDegrees(D) - 40.f) > 0.5f) { ++Crossed; }
    }
    Check(WrongRange == 0, "a flank spot is its range from him at every bearing");
    Check(Crossed == 0, "and it is that bearing off where the enemy already was");
}

// ----------------------------------------------------------------- spiral

static void Spiral()
{
    std::printf("\nSPIRAL  (how far along the stage becomes how far around the district)\n");
    const float Extent = 9000.f;      // 90 m
    FVector Last = SaudArena::SpiralPoint(0.f, Extent, 0.f);
    float MinR = 1e9f, MaxR = 0.f, Walked = 0.f;
    int Backwards = 0;
    float LastR = Last.Size2D();
    for (int I = 1; I <= 200; ++I)
    {
        const float T = I / 200.f;
        const FVector P = SaudArena::SpiralPoint(T, Extent, 0.f);
        const float R = P.Size2D();
        if (R < LastR - 1e-3f) { ++Backwards; }
        LastR = R;
        MinR = FMath::Min(MinR, R);
        MaxR = FMath::Max(MaxR, R);
        Walked += (P - Last).Size2D();
        Last = P;
    }
    std::printf("  a %.0f m district: the way runs %.0f m, from %.0f m out to %.0f m\n",
                Extent * 2.f / 100.f, Walked / 100.f, MinR / 100.f, MaxR / 100.f);
    Check(Backwards == 0, "the spiral only ever works outward");
    Check(MinR > Extent * 0.17f, "it starts clear of the middle, where the hub is");
    Check(MaxR < Extent * 0.87f, "and stops clear of the rim, where the doors are");
    Check(Walked > Extent * 2.f, "walking it is further than crossing the district");

    // A floor's phase turns the whole thing, so the cellar's content is not
    // directly under the street's.
    const FVector A = SaudArena::SpiralPoint(0.5f, Extent, 0.f);
    const FVector B = SaudArena::SpiralPoint(0.5f, Extent, 2.f);
    Check((A - B).Size2D() > Extent * 0.2f, "another floor's phase moves it somewhere else");
}

// -------------------------------------------------------------- district

static void District()
{
    std::printf("\nDISTRICT EXTENT  (how big a district is, from its stage's Length)\n");
    // The three numbers Tools/fab/lay_out_world.py and the Unity port's
    // District.LengthToExtent both carry too: 1.7x, clamped to 60-130 m.
    Check(FMath::Abs(SaudArena::DistrictExtent(0.f) - 6000.f) < 1e-2f,
          "a stage with no length still gets the floor");
    Check(FMath::Abs(SaudArena::DistrictExtent(100000.f) - 13000.f) < 1e-2f,
          "a very long stage is still capped");
    Check(FMath::Abs(SaudArena::DistrictExtent(6000.f) - 10200.f) < 1e-2f,
          "in between, it is exactly 1.7x");

    // The nine real stage lengths, cross-checked against
    // Tools/fab/lay_out_world.py's extent_of() over the same numbers --
    // the game and the map cannot disagree about how big a place is.
    struct { float Length, Extent; } Stages[] = {
        { 7200.f, 12240.f },   // SouqAlDawar
        { 6240.f, 10608.f },   // BaytAlDarb
        { 8640.f, 13000.f },   // MarsaAlFajr (clamped)
        { 6720.f, 11424.f },   // AbrajAlMalih
        { 5280.f,  8976.f },   // AlHilal
        { 6000.f, 10200.f },   // JaziratAlHajar
        { 8160.f, 13000.f },   // AlTariqAlMasdud (clamped)
        { 7200.f, 12240.f },   // MukhayyamAlNiran
        { 3840.f,  6528.f },   // AlHalqa
    };
    int Mismatches = 0;
    for (const auto& S : Stages)
    {
        if (FMath::Abs(SaudArena::DistrictExtent(S.Length) - S.Extent) > 1.f) { ++Mismatches; }
    }
    Check(Mismatches == 0, "every real stage's extent matches lay_out_world.py's");
}

// ------------------------------------------------------------ the world

static void Sites()
{
    std::printf("\nSITES AND DOORS  (the game agreeing with the map it is played on)\n");

    // The hash the builders place every district with. These are
    // Tools/levels/build_world.py's hash01(i * 977 + 13) for the ten stage
    // indices -- the formula's own values, not the data's, so they only go
    // stale if someone changes the hash on one side and not the other.
    const float Py[10] = { 0.4582448f, 0.7918193f, 0.6924685f, 0.4667328f, 0.3285656f,
                           0.2282923f, 0.1852833f, 0.5928881f, 0.1998035f, 0.8371642f };
    int HashOff = 0;
    for (int I = 0; I < 10; ++I)
    {
        if (FMath::Abs(SaudArena::Hash01(I * 977u + 13u) - Py[I]) > 1e-6f) { ++HashOff; }
        if (FMath::Abs(SaudArena::DistrictPhase(I) - Py[I] * 2.f * 3.14159265f) > 1e-4f) { ++HashOff; }
    }
    Check(HashOff == 0, "Hash01 and DistrictPhase are the builders' hash01, index for index");

    // A wave's site is the spiral at its fraction of the stage, inside the
    // district, and a trigger past the stage's end is its end.
    const float L = 7200.f, Ph = SaudArena::DistrictPhase(0);
    const FVector W = SaudArena::WaveSite(3000.f, L, Ph);
    const FVector Sp = SaudArena::SpiralPoint(3000.f / L, SaudArena::DistrictExtent(L), Ph);
    Check((W - Sp).Size2D() < 1e-3f, "a wave's site is SpiralPoint(TriggerDistance / Length)");
    Check(W.Size2D() < SaudArena::DistrictExtent(L), "...inside its district");
    Check((SaudArena::WaveSite(99999.f, L, Ph) - SaudArena::SpiralPoint(1.f, SaudArena::DistrictExtent(L), Ph)).Size2D() < 1e-3f,
          "a trigger past the end is the end of the street");
    Check((SaudArena::StreetEnd(L, Ph) - SaudArena::SpiralPoint((L - 360.f) / L, SaudArena::DistrictExtent(L), Ph)).Size2D() < 1e-3f,
          "the street's end is the strip's last 360 cm, along the spiral");

    // A door at any bearing on the rim steps the player toward the middle,
    // stays on the ground, and faces in. It was +-240 along X.
    const FVector Mid(37000.f, -26163.f, 0.f);
    const float E = SaudArena::DistrictExtent(6720.f);
    int Out = 0, NotIn = 0;
    for (int A = 0; A < 360; A += 5)
    {
        const float R = A * 3.14159265f / 180.f;
        const FVector Door(Mid.X + std::cos(R) * (E - 200.f), Mid.Y + std::sin(R) * (E - 200.f), 0.f);
        const FVector Land = SaudArena::DoorLanding(Door, Mid, 240.f);
        const float Rd = (Door - Mid).Size2D(), Rl = (Land - Mid).Size2D();
        if (Rl > E || FMath::Abs((Rd - Rl) - 240.f) > 0.5f) { ++Out; }
        const FVector In = SaudArena::DoorInward(Door, Mid);
        const FVector ToMid = SaudArena::Direction(Door, Mid, FVector(1.f, 0.f, 0.f));
        if (In.X * ToMid.X + In.Y * ToMid.Y < 0.9999f) { ++NotIn; }
    }
    Check(Out == 0, "a door step lands 240 cm inside the rim at every bearing");
    Check(NotIn == 0, "...and faces the middle");
}

int main()
{
    Hitbox();
    Guard();
    Camera();
    Arena();
    Crowd();
    Spiral();
    District();
    Sites();
    std::printf(Fails == 0 ? "\nall checks passed\n" : "\n%d FAILURES\n", Fails);
    return Fails == 0 ? 0 : 1;
}
