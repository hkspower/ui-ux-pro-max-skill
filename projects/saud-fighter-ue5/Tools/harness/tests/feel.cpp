/**
 * How a blow feels, and which clip a fighter plays, executed.
 *
 * SaudFeel.h carries the browser's applyHit() numbers into the Unreal build.
 * This checks that each outcome asks for what the browser's does, that the
 * state keeps peaks and runs out in real time, that a shake is the same share
 * of the picture it is in the browser, and that every fighter state picks the
 * clip it should -- at every angle, not just along +X.
 */
#include "../HarnessTypes.h"
#include "../../../Source/SaudFighter/Combat/SaudFeel.h"

#include <cstdio>
#include <cstring>
#include <cmath>
#include <string>

static int Fails = 0;
static void Check(bool Ok, const char* What)
{
    if (!Ok) { ++Fails; std::printf("  FAIL  %s\n", What); }
}
static bool Near(float A, float B, float Eps = 1e-4f) { return std::fabs(A - B) <= Eps; }

using namespace SaudFeel;

// ------------------------------------------------------------ the numbers

static void Blows()
{
    std::printf("BLOWS  (applyHit, saud-fighter/index.html:3362-3440)\n");

    // Clean hits, player landing them.
    FBlowFeel L = ForBlow(false, false, false, false, false, true);
    FBlowFeel H = ForBlow(true, false, false, false, false, true);
    Check(Near(L.HitStop, 0.04f) && Near(H.HitStop, 0.075f), "hitstop 0.04 / 0.075");
    Check(Near(L.ShakePx, 7.f) && Near(H.ShakePx, 13.f), "shake 7 / 13");
    Check(Near(L.Punch, 0.45f) && Near(H.Punch, 1.f), "punch-in 0.45 / 1");
    Check(Near(L.Flash, 0.09f) && Near(H.Flash, 0.09f), "flash 0.09 s either way");
    Check(Near(L.Buzz, 0.010f) && Near(H.Buzz, 0.020f), "landing buzz 10 / 20 ms");

    // The player hit.
    FBlowFeel PL = ForBlow(false, false, false, false, true, false);
    FBlowFeel PH = ForBlow(true, false, false, false, true, false);
    Check(Near(PL.Buzz, 0.024f) && Near(PH.Buzz, 0.048f), "hurt buzz 24 / 48 ms");
    Check(PH.BuzzStrength > H.BuzzStrength, "taking a heavy buzzes harder than landing one");

    // Nobody the player is: no buzz.
    FBlowFeel N = ForBlow(true, false, false, false, false, false);
    Check(N.Buzz == 0.f && N.BuzzStrength == 0.f, "no buzz when the player is not in it");
    Check(Near(N.HitStop, 0.075f), "...but the blow still freezes");

    // Knockdown lifts the shake to 16 and never lowers it.
    FBlowFeel K = ForBlow(false, false, false, true, false, true);
    Check(Near(K.ShakePx, 16.f), "knockdown shake 16");
    Check(Near(K.HitStop, 0.04f), "knockdown keeps the blow's own hitstop");

    // Blocked: a shake of 5, nothing else.
    FBlowFeel B = ForBlow(true, true, false, false, true, false);
    Check(Near(B.ShakePx, 5.f) && B.HitStop == 0.f && B.Punch == 0.f && B.Flash == 0.f
          && B.Buzz == 0.f, "blocked: shake 5 and nothing else");

    // Parried: wins over blocked and over heavy.
    FBlowFeel P = ForBlow(true, true, true, true, true, true);
    Check(Near(P.HitStop, 0.09f) && Near(P.ShakePx, 12.f) && Near(P.Buzz, 0.03f),
          "parry: hitstop 0.09, shake 12, buzz 30 ms");
    Check(P.Punch == 0.f && P.Flash == 0.f, "parry: no punch-in, no flash on the parrier");
}

static void Pad()
{
    std::printf("PAD  (a motor needs %.0f ms)\n", BuzzFloor * 1000.f);
    Check(PadBuzzSeconds(0.f) == 0.f, "no buzz sends nothing");
    Check(Near(PadBuzzSeconds(0.010f), BuzzFloor), "10 ms is raised to the floor");
    Check(Near(PadBuzzSeconds(0.048f), BuzzFloor), "48 ms is raised to the floor");
    Check(Near(PadBuzzSeconds(0.2f), 0.2f), "longer than the floor passes through");
    // Order is kept where it survives the floor.
    Check(PadBuzzSeconds(0.08f) < PadBuzzSeconds(0.1f), "longer stays longer");
}

static void State()
{
    std::printf("STATE  (peaks kept, real-time decay)\n");
    FState S;
    Check(!S.Frozen(), "starts unfrozen");
    S.Add(ForBlow(true, false, false, false, false, true));
    S.Add(ForBlow(false, false, false, false, false, true));
    Check(Near(S.HitStop, 0.075f) && Near(S.ShakePx, 13.f) && Near(S.Punch, 1.f),
          "a jab after a heavy never cuts the heavy short");
    Check(S.Frozen(), "frozen after a clean hit");

    // 0.075 s of freeze in 60 Hz real frames: frozen for 4 frames, not 5.
    int Frames = 0;
    while (S.Frozen() && Frames < 100) { S.Tick(1.f / 60.f); ++Frames; }
    Check(Frames == 5, "heavy hitstop ends on the fifth 60 Hz frame");

    // The shake fades at 46 px/s: 13 px is gone in 0.283 s.
    FState T; T.Add(ForBlow(true, false, false, false, false, true));
    T.Tick(0.28f);
    Check(T.ShakePx > 0.f && T.ShakePx < 0.2f, "13 px of shake is nearly gone at 0.28 s");
    T.Tick(0.01f);
    Check(T.ShakePx == 0.f, "...and gone at 0.29 s, never negative");
    // The punch fades at 3.4/s: 1 is gone in 0.294 s.
    Check(T.Punch > 0.f, "a full punch-in is still there at 0.29 s");
    T.Tick(0.01f);
    Check(T.Punch == 0.f, "...and has run out by 0.30 s");

    FState Z; Z.Tick(1.f);
    Check(Z.HitStop == 0.f && Z.ShakePx == 0.f && Z.Punch == 0.f, "idle state stays at zero");
}

static void Camera()
{
    std::printf("CAMERA  (the browser's share of the picture)\n");
    // 13 px of 720 is 1.8 % of the frame: at a 60 degree vertical FOV that
    // is 1.083 degrees.
    Check(Near(ShakeDegrees(13.f, 60.f), 13.f / 720.f * 60.f), "13 px at 60 deg");
    Check(Near(ShakeDegrees(720.f, 47.f), 47.f), "the whole canvas is the whole FOV");
    Check(ShakeDegrees(0.f, 90.f) == 0.f, "no shake, no degrees");

    // The wave stays inside -1..1 for ten seconds at 1 kHz.
    float Lo = 0.f, Hi = 0.f;
    for (int I = 0; I < 10000; ++I)
    {
        float P, Y; ShakeWave(I * 0.001f, P, Y);
        Lo = std::fmin(Lo, std::fmin(P, Y)); Hi = std::fmax(Hi, std::fmax(P, Y));
    }
    Check(Lo >= -1.f && Hi <= 1.f, "shake wave inside -1..1");
    Check(Hi > 0.8f && Lo < -0.8f, "...and uses most of it");

    // Ease: the browser's, endpoints and the middle.
    Check(Ease(0.f) == 0.f && Near(Ease(1.f), 1.f) && Near(Ease(0.5f), 0.5f), "ease 0, 0.5, 1");
    Check(Ease(-3.f) == 0.f && Near(Ease(7.f), 1.f), "ease clamps");
    // Punch-in: a full one narrows the FOV by 1.045, none leaves it alone.
    Check(Near(PunchFov(90.f, 0.f), 90.f), "no punch, no zoom");
    Check(Near(PunchFov(90.f, 1.f), 90.f / 1.045f), "full punch narrows by 1.045");
    Check(PunchFov(90.f, 0.45f) < 90.f && PunchFov(90.f, 0.45f) > PunchFov(90.f, 1.f),
          "a light punch is between");
}

static void Flash()
{
    std::printf("FLASH  (held for half, falling away over half)\n");
    Check(FlashAmount(0.f) == 0.f && FlashAmount(-1.f) == 0.f, "run out is zero");
    Check(FlashAmount(FlashSeconds) == 1.f, "full at the blow");
    Check(FlashAmount(FlashSeconds * 0.5f) == 1.f, "still full halfway");
    Check(Near(FlashAmount(FlashSeconds * 0.25f), 0.5f), "half at three quarters");
    float Prev = 1.f; bool Mono = true;
    for (int I = 0; I <= 90; ++I)
    {
        const float A = FlashAmount(FlashSeconds * (1.f - I / 90.f));
        if (A > Prev + 1e-6f) Mono = false;
        Prev = A;
    }
    Check(Mono, "never brightens as it runs out");
}

// -------------------------------------------------------------- the clips

static FVector Rotate(const FVector& V, float Radians)
{
    const float C = std::cos(Radians), S = std::sin(Radians);
    return FVector(V.X * C - V.Y * S, V.X * S + V.Y * C, V.Z);
}

static void Clips()
{
    std::printf("CLIPS  (state to clip, at every angle)\n");

    // The mirror of EFighterState must match the real one, in order.
    {
        FILE* F = std::fopen("Source/SaudFighter/Combat/SaudTypes.h", "rb");
        std::string Src;
        if (F) { char Buf[4096]; size_t N; while ((N = std::fread(Buf, 1, sizeof Buf, F)) > 0) Src.append(Buf, N); std::fclose(F); }
        const size_t At = Src.find("enum class EFighterState");
        const size_t End = Src.find("};", At);
        Check(At != std::string::npos && End != std::string::npos, "EFighterState found in SaudTypes.h");
        const char* Names[] = { "Idle", "Walk", "Attack", "Hit", "Block", "Dash", "Down", "Dead" };
        const int Mine[] = { SIdle, SWalk, SAttack, SHit, SBlock, SDash, SDown, SDead };
        size_t Pos = At;
        bool InOrder = At != std::string::npos;
        for (int I = 0; I < 8 && InOrder; ++I)
        {
            const size_t Found = Src.find(Names[I], Pos);
            if (Found == std::string::npos || Found > End || Mine[I] != I) InOrder = false;
            Pos = Found + std::strlen(Names[I]);
        }
        Check(InOrder, "SIdle..SDead are EFighterState's order");
    }

    FMotionInput In;
    In.State = SIdle;
    Check(Pick(In) == EClip::Guard, "idle, standing: guard");
    In.Speed = WalkThreshold - 1.f;
    Check(Pick(In) == EClip::Guard, "drifting under the threshold is still standing");
    In.State = SWalk; In.Speed = 0.f;
    Check(Pick(In) == EClip::Guard, "walk state with no speed: guard");

    In = FMotionInput(); In.State = SAttack; In.Speed = 400.f; In.bBlocking = true;
    Check(Pick(In) == EClip::Attack, "attack beats moving and blocking");
    In.State = SHit; In.bLastHitHeavy = false;
    Check(Pick(In) == EClip::HitLight, "hit: light");
    In.bLastHitHeavy = true;
    Check(Pick(In) == EClip::HitHeavy, "hit: heavy");
    In.State = SDown;
    Check(Pick(In) == EClip::Down, "down");
    In.State = SDead;
    Check(Pick(In) == EClip::Down, "dead holds down");

    In = FMotionInput(); In.GettingUp = 0.3f; In.Speed = 400.f; In.bBlocking = true;
    Check(Pick(In) == EClip::GetUp, "getting up beats blocking and walking");
    In.GettingUp = 0.f;
    Check(Pick(In) == EClip::Block, "blocking beats walking");
    In.bBlocking = false; In.State = SBlock;
    Check(Pick(In) == EClip::Block, "block state blocks");

    // Every angle: the facing and heading turned together give the same clip.
    const EClip Walks[4] = { EClip::WalkFwd, EClip::WalkBack, EClip::WalkLeft, EClip::WalkRight };
    const EClip Dashes[4] = { EClip::DashFwd, EClip::DashBack, EClip::DashLeft, EClip::DashRight };
    const float Rel[4] = { 0.f, 3.14159265f, 1.5707963f, -1.5707963f };   // fwd, back, left (+Y of +X), right
    int Bad = 0;
    for (int A = 0; A < 72; ++A)
    {
        const float Ang = A * 5.f * 3.14159265f / 180.f;
        const FVector Face = Rotate(FVector(1.f, 0.f, 0.f), Ang);
        for (int Q = 0; Q < 4; ++Q)
        {
            // Off the pure direction by 30 degrees either side: still that quadrant.
            for (float Off : { -0.52f, 0.f, 0.52f })
            {
                FMotionInput M;
                M.Facing = Face;
                M.Heading = Rotate(Face, Rel[Q] + Off);
                M.State = SWalk; M.Speed = 250.f;
                if (Pick(M) != Walks[Q]) ++Bad;
                M.State = SDash;
                if (Pick(M) != Dashes[Q]) ++Bad;
                if (Quadrant(M.Facing, M.Heading) != Q) ++Bad;
            }
        }
    }
    std::printf("  72 facings x 4 directions x 3 offsets, walk and dash\n");
    Check(Bad == 0, "the same heading against the facing picks the same clip at every angle");

    // Names and looping.
    Check(std::strcmp(ClipSuffix(EClip::WalkLeft), "Walk_Left") == 0, "Walk_Left's name");
    Check(std::strcmp(ClipSuffix(EClip::HitHeavy), "Hit_Heavy") == 0, "Hit_Heavy's name");
    Check(ClipSuffix(EClip::Attack)[0] == 0, "attack has no suffix: its row names it");
    Check(Loops(EClip::Guard) && Loops(EClip::WalkBack) && Loops(EClip::Block), "stances loop");
    Check(!Loops(EClip::DashFwd) && !Loops(EClip::HitLight) && !Loops(EClip::Down)
          && !Loops(EClip::GetUp) && !Loops(EClip::Attack), "one-shots do not");

    // The Saud clips the names point at are on disk, and the street men's
    // copy of them (the boxer's guard) that everyone else borrows.
    const EClip All[] = { EClip::Guard, EClip::WalkFwd, EClip::WalkBack, EClip::WalkLeft, EClip::WalkRight,
                          EClip::DashFwd, EClip::DashBack, EClip::DashLeft, EClip::DashRight,
                          EClip::Block, EClip::HitLight, EClip::HitHeavy, EClip::Down, EClip::GetUp };
    int Missing = 0;
    for (const char* Set : { "Saud", "Street" })
    {
        for (EClip C : All)
        {
            const std::string P = std::string("Content/Animation/") + Set + "/A_" + Set + "_" + ClipSuffix(C) + ".fbx";
            FILE* F = std::fopen(P.c_str(), "rb");
            if (!F) { ++Missing; std::printf("  missing %s\n", P.c_str()); } else std::fclose(F);
        }
    }
    Check(Missing == 0, "every named clip exists in Content/Animation/Saud and Street");
}

int main()
{
    Blows(); Pad(); State(); Camera(); Flash(); Clips();
    std::printf(Fails ? "\n%d FAILED\n" : "\nall feel checks passed\n", Fails);
    return Fails ? 1 : 0;
}
