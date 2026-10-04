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
#include "../../../Source/SaudFighter/Combat/SaudIK.h"
#include "../../../Source/SaudFighter/Combat/SaudPlants.h"

#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <cmath>
#include <string>
#include <vector>
#include <map>
#include <initializer_list>

static int Fails = 0;
static void Check(bool Ok, const char* What)
{
    if (!Ok) { ++Fails; std::printf("  FAIL  %s\n", What); }
}
static bool Near(float A, float B, float Eps = 1e-4f) { return std::fabs(A - B) <= Eps; }
/** A check that waits on the clips' rebuild (the 360 spec's new clip files,
    by other builders): a FAIL like any other, unless SAUD_CLIPS_PENDING is
    set, when it prints PENDING and does not count -- so the sabotages can
    still be run against the rest before the clips exist. */
static void Pending(bool Ok, const char* What)
{
    if (Ok) return;
    if (std::getenv("SAUD_CLIPS_PENDING")) { std::printf("  PENDING (awaits the clips' rebuild)  %s\n", What); return; }
    Check(false, What);
}

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
    Check(Pick(In) == EClip::Death, "dead holds Death");

    // By the blow (2026-09-27): the row that landed it picks the reaction
    // and the fall -- motion_hits.BLOW's table, the same six rows.
    {
        struct { const char* Row; EClip Hit; EClip Fall; } Rows[] = {
            { "Jab",     EClip::HitHeadStraightLight, EClip::Down },
            { "Cross",   EClip::HitHeadStraight,      EClip::Down },
            { "Hook",    EClip::HitHeadSide,          EClip::DownSide },
            { "Kick",    EClip::HitBodySide,          EClip::Down },
            { "Knee",    EClip::HitBodyFront,         EClip::DownFold },
            { "Special", EClip::HitHeadSide,          EClip::DownSide } };
        int Wrong = 0;
        for (const auto& R : Rows)
        {
            for (bool Heavy : { false, true })       // the blow decides, not the weight
            {
                FMotionInput M; M.LastBlow = BlowOf(R.Row); M.bLastHitHeavy = Heavy;
                M.State = SHit;  if (Pick(M) != R.Hit)  { ++Wrong; std::printf("  %s hit\n", R.Row); }
                M.State = SDown; if (Pick(M) != R.Fall) { ++Wrong; std::printf("  %s down\n", R.Row); }
                M.State = SDead; if (Pick(M) != EClip::Death) { ++Wrong; std::printf("  %s dead\n", R.Row); }
            }
        }
        Check(Wrong == 0, "each blow picks its own reaction and its own fall");
        Check(BlowOf("Rage") == EBlow::None && BlowOf("") == EBlow::None && BlowOf(nullptr) == EBlow::None
              && BlowOf("Ja") == EBlow::None && BlowOf("Jabs") == EBlow::None && BlowOf("None") == EBlow::None,
              "a row it does not know is no blow at all");
        FMotionInput M; M.State = SHit; M.LastBlow = EBlow::None;
        M.bLastHitHeavy = false; const bool L = Pick(M) == EClip::HitLight;
        M.bLastHitHeavy = true;  const bool H = Pick(M) == EClip::HitHeavy;
        M.State = SDown;         const bool D = Pick(M) == EClip::Down;
        Check(L && H && D, "no blow (a parry's stagger, a shove): the old light / heavy hit, and Down");
        Check(Fallback(EClip::HitHeadStraightLight) == EClip::HitLight && Fallback(EClip::HitHeadStraight) == EClip::HitHeavy
              && Fallback(EClip::HitHeadSide) == EClip::HitHeavy && Fallback(EClip::HitBodyFront) == EClip::HitHeavy
              && Fallback(EClip::HitBodySide) == EClip::HitHeavy && Fallback(EClip::DownSide) == EClip::Down
              && Fallback(EClip::DownFold) == EClip::Down && Fallback(EClip::Guard) == EClip::Guard
              && Fallback(EClip::HitLight) == EClip::HitLight,
              "a set without a reaction by blow plays the old hit, or Down");
        // every attack row in the table lands as some blow
        FILE* F = std::fopen("Content/Data/DT_Attacks.csv", "rb");
        int Rows_ = 0, Unknown = 0;
        if (F)
        {
            char Line[512];
            bool First = true;
            while (std::fgets(Line, sizeof Line, F))
            {
                if (First) { First = false; continue; }
                char* Comma = std::strchr(Line, ',');
                if (!Comma) continue;
                *Comma = 0; ++Rows_;
                if (BlowOf(Line) == EBlow::None) { ++Unknown; std::printf("  %s lands as no blow\n", Line); }
            }
            std::fclose(F);
        }
        Check(Rows_ >= 6 && Unknown == 0, "every row of DT_Attacks lands as a blow");
    }

    // The end of a fight (2026-09-28): the killing blow's Down is the dying,
    // Dead holds it; the win plays standing, and moving or guarding ends it.
    {
        FMotionInput M; M.State = SDown; M.bDying = true; M.LastBlow = BlowOf("Hook");
        const bool DyingDown = Pick(M) == EClip::Death;
        M.bDying = false; const bool LivingDown = Pick(M) == EClip::DownSide;
        M = FMotionInput(); M.State = SDead;
        const bool Dead = Pick(M) == EClip::Death;
        Check(DyingDown && LivingDown && Dead, "a killing blow falls into Death, a living one into its fall, and Dead holds Death");
        M = FMotionInput(); M.Victory = 1.f;
        const bool Win = Pick(M) == EClip::Victory;
        M.Speed = 150.f; const bool Walks = Pick(M) == EClip::WalkFwd;
        M.Speed = 0.f; M.bBlocking = true; const bool Blocks = Pick(M) == EClip::Block;
        M.bBlocking = false; M.State = SHit; M.LastBlow = BlowOf("Jab"); const bool Hit = Pick(M) == EClip::HitHeadStraightLight;
        M = FMotionInput(); M.Victory = 1.f; M.State = SAttack; const bool Swing = Pick(M) == EClip::Attack;
        Check(Win && Walks && Blocks && Hit && Swing, "the win plays standing; walking, blocking, a hit or a swing come first");
        Check(Fallback(EClip::Death) == EClip::Down && Fallback(EClip::Victory) == EClip::Guard, "no Death clip plays Down, no Victory the guard");
        Check(!Loops(EClip::Death) && !Loops(EClip::Victory), "death and the win are one-shots that hold");
        // the clip is as long as the engine holds it
        FILE* F = std::fopen("Content/Animation/Saud/DT_SaudMotion.csv", "rb");
        float VicS = -1.f, DeathS = -1.f;
        if (F)
        {
            char Line[512];
            while (std::fgets(Line, sizeof Line, F))
            {
                char* Name = Line; char* C1 = std::strchr(Name, ','); if (!C1) continue; *C1 = 0;
                // Name,Fighter,Attack,File,Seconds
                char* P = C1 + 1; for (int K = 0; K < 3 && P; ++K) { P = std::strchr(P, ','); if (P) ++P; }
                if (!P) continue;
                if (std::strcmp(Name, "A_Saud_Victory") == 0) VicS = static_cast<float>(std::atof(P));
                if (std::strcmp(Name, "A_Saud_Death") == 0) DeathS = static_cast<float>(std::atof(P));
            }
            std::fclose(F);
        }
        Check(std::fabs(VicS - VictorySeconds) < 0.02f, "A_Saud_Victory is VictorySeconds long");
        Check(std::fabs(DeathS - 1.05f) < 0.04f, "A_Saud_Death is the engine's dying Down, 1.05 s");
    }

    In = FMotionInput(); In.GettingUp = 0.3f; In.Speed = 400.f; In.bBlocking = true;
    Check(Pick(In) == EClip::GetUp, "getting up beats blocking and walking");
    In.GettingUp = 0.f;
    Check(Pick(In) == EClip::Block, "blocking beats walking");
    In.bBlocking = false; In.State = SBlock;
    Check(Pick(In) == EClip::Block, "block state blocks");

    // Every angle: the facing and heading turned together give the same clip.
    // The dash is four ways (Quadrant); the walk is eight since 2026-10-04
    // (Loco360 holds those), so here a walk 30 degrees off a quadrant's
    // centre is that quadrant's diagonal neighbour or itself, never another.
    const EClip Dashes[4] = { EClip::DashFwd, EClip::DashBack, EClip::DashLeft, EClip::DashRight };
    const int QuadDir[4] = { 0, 4, 2, 6 };
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
                M.State = SWalk; M.Speed = 150.f;
                const int D = DirOf(Pick(M));
                const int Want = Off > 0.f ? QuadDir[Q] + 1 : Off < 0.f ? QuadDir[Q] + 7 : QuadDir[Q];
                if (D != Want % 8) ++Bad;
                M.State = SDash;
                if (Pick(M) != Dashes[Q]) ++Bad;
                if (Quadrant(M.Facing, M.Heading) != Q) ++Bad;
            }
        }
    }
    std::printf("  72 facings x 4 directions x 3 offsets, the walk's octant and the dash's quadrant\n");
    Check(Bad == 0, "the same heading against the facing picks the same clip at every angle");

    // Names and looping.
    Check(std::strcmp(ClipSuffix(EClip::WalkLeft), "Walk_Left") == 0, "Walk_Left's name");
    Check(std::strcmp(ClipSuffix(EClip::HitHeavy), "Hit_Heavy") == 0, "Hit_Heavy's name");
    Check(ClipSuffix(EClip::Attack)[0] == 0, "attack has no suffix: its row names it");
    Check(Loops(EClip::Guard) && Loops(EClip::WalkBack) && Loops(EClip::Block), "stances loop");
    Check(!Loops(EClip::DashFwd) && !Loops(EClip::HitLight) && !Loops(EClip::Down)
          && !Loops(EClip::GetUp) && !Loops(EClip::Attack), "one-shots do not");
    Check(std::strcmp(ClipSuffix(EClip::HitHeadSide), "Hit_Head_Side") == 0
          && std::strcmp(ClipSuffix(EClip::DownFold), "Down_Fold") == 0, "the reactions' names");
    Check(!Loops(EClip::HitHeadStraight) && !Loops(EClip::HitBodySide) && !Loops(EClip::DownSide),
          "a reaction and a fall are one-shots");

    // The Saud clips the names point at are on disk, and the street men's
    // copy of them (the boxer's guard) that everyone else borrows.
    const EClip All[] = { EClip::Guard, EClip::WalkFwd, EClip::WalkBack, EClip::WalkLeft, EClip::WalkRight,
                          EClip::DashFwd, EClip::DashBack, EClip::DashLeft, EClip::DashRight,
                          EClip::Block, EClip::HitLight, EClip::HitHeavy, EClip::Down, EClip::GetUp,
                          EClip::HitHeadStraightLight, EClip::HitHeadStraight, EClip::HitHeadSide,
                          EClip::HitBodyFront, EClip::HitBodySide, EClip::DownSide, EClip::DownFold,
                          EClip::Death, EClip::Victory };
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


// ------------------------------------------- 360: eight ways, two tiers, turns

static FMotionInput Moving(const FVector& Face, float RelRadians, float Speed, bool bFree, bool bGaits, EClip Current = EClip::Guard)
{
    FMotionInput M;
    M.State = SWalk; M.Speed = Speed; M.bFree = bFree; M.bGaits = bGaits; M.Current = Current;
    M.Facing = Face; M.Heading = Rotate(Face, RelRadians);
    return M;
}

static bool OnDisk(const std::string& P) { FILE* F = std::fopen(P.c_str(), "rb"); if (F) std::fclose(F); return F != nullptr; }

/** The file the motion component would load for a clip name, its way
    (USaudMotionComponent::Find): the set's own, then -- except Saud and the
    Island creatures -- the Street set's, then Saud's. "" for none. */
static std::string OwnPath(const std::string& Set, const std::string& Name)
{
    const bool bCreature = Set == "Monkey" || Set == "Gorilla";
    const std::string Folder = (Set == "Saud" || Set == "Street") ? Set : bCreature ? "Island" : "Bosses";
    return "Content/Animation/" + Folder + "/A_" + Set + "_" + Name + ".fbx";
}

static std::string Resolve(const std::string& Set, const std::string& Name)
{
    const bool bCreature = Set == "Monkey" || Set == "Gorilla";
    const std::string Own = OwnPath(Set, Name);
    if (OnDisk(Own)) return Own;
    if (Set == "Saud" || bCreature) return "";
    if (Set != "Street" && OnDisk("Content/Animation/Street/A_Street_" + Name + ".fbx")) return "Content/Animation/Street/A_Street_" + Name + ".fbx";
    const std::string S = "Content/Animation/Saud/A_Saud_" + Name + ".fbx";
    return OnDisk(S) ? S : "";
}

static void Loco360()
{
    std::printf("360  (eight ways at a walk and a run, the free turns, the fallbacks)\n");
    const float D2R = 3.14159265f / 180.f;

    // ---- the names are the spec's file names, every one
    struct FName_ { EClip C; const char* Name; };
    const FName_ Names[] = {
        {EClip::WalkFwd, "Walk_Fwd"}, {EClip::WalkFwdLeft, "Walk_FwdLeft"}, {EClip::WalkLeft, "Walk_Left"}, {EClip::WalkBackLeft, "Walk_BackLeft"},
        {EClip::WalkBack, "Walk_Back"}, {EClip::WalkBackRight, "Walk_BackRight"}, {EClip::WalkRight, "Walk_Right"}, {EClip::WalkFwdRight, "Walk_FwdRight"},
        {EClip::RunFwd, "Run_Fwd"}, {EClip::RunFwdLeft, "Run_FwdLeft"}, {EClip::RunLeft, "Run_Left"}, {EClip::RunBackLeft, "Run_BackLeft"},
        {EClip::RunBack, "Run_Back"}, {EClip::RunBackRight, "Run_BackRight"}, {EClip::RunRight, "Run_Right"}, {EClip::RunFwdRight, "Run_FwdRight"},
        {EClip::TurnL90, "Turn_L90"}, {EClip::TurnR90, "Turn_R90"}, {EClip::Turn180, "Turn_180"}, {EClip::Pivot180, "Pivot_180"} };
    int BadName = 0;
    for (const FName_& N : Names) if (std::strcmp(ClipSuffix(N.C), N.Name) != 0) { ++BadName; std::printf("  %s named %s\n", N.Name, ClipSuffix(N.C)); }
    Check(BadName == 0, "every 360 clip is named as the spec's file: Walk_<Dir>, Run_<Dir>, Turn_L90, Turn_R90, Turn_180, Pivot_180");
    {
        bool Ok = true;
        for (int D = 0; D < 8; ++D)
        {
            Ok = Ok && DirOf(WalkClip(D)) == D && DirOf(RunClip(D)) == D && TierOf(WalkClip(D)) == 0 && TierOf(RunClip(D)) == 1
                && Loops(WalkClip(D)) && Loops(RunClip(D)) && KindOf(WalkClip(D)) == EKind::Step && KindOf(RunClip(D)) == EKind::Step;
        }
        for (EClip T : { EClip::TurnL90, EClip::TurnR90, EClip::Turn180, EClip::Pivot180 })
            Ok = Ok && !Loops(T) && KindOf(T) == EKind::Turn && IsTurnClip(T) && DirOf(T) < 0 && TierOf(T) < 0;
        Ok = Ok && !IsTurnClip(EClip::Guard) && DirOf(EClip::Guard) < 0 && TierOf(EClip::GaitRun) < 0;
        Check(Ok, "the sixteen walk and run clips loop and are steps, each its own way and tier; the four turns are one-shots of their own kind");
    }
    Check(FreeBeyondCm == SaudSteer::FreeBeyondCm, "SaudFeel::FreeBeyondCm is SaudSteer's distance");

    // ---- the octant against the drawn facing, at 72 facings x 8 ways, both tiers
    {
        int Bad = 0;
        for (int A = 0; A < 72; ++A)
        {
            const FVector Face = Rotate(FVector(1.f, 0.f, 0.f), A * 5.f * D2R);
            for (int D = 0; D < 8; ++D)
                for (float Off : { -21.5f, -10.f, 0.f, 10.f, 21.5f })
                {
                    if (Pick(Moving(Face, (D * 45.f + Off) * D2R, 150.f, false, false)) != WalkClip(D)) ++Bad;
                    if (Pick(Moving(Face, (D * 45.f + Off) * D2R, 341.f, false, true)) != RunClip(D)) ++Bad;
                }
        }
        std::printf("  72 facings x 8 ways x 5 offsets inside each octant, walk and run\n");
        Check(Bad == 0, "fighting, the heading's octant against the drawn facing picks its walk or run strafe at every angle");
        // held across a line: the clip showing until 5 degrees past it
        const FVector F = Rotate(FVector(1.f, 0.f, 0.f), 37.f * D2R);
        const bool Held = Pick(Moving(F, 25.f * D2R, 150.f, false, false, EClip::WalkFwd)) == EClip::WalkFwd
                       && Pick(Moving(F, 25.f * D2R, 150.f, false, false, EClip::Guard)) == EClip::WalkFwdLeft
                       && Pick(Moving(F, 28.5f * D2R, 150.f, false, false, EClip::WalkFwd)) == EClip::WalkFwdLeft
                       && Pick(Moving(F, -69.f * D2R, 341.f, false, false, EClip::RunFwdRight)) == EClip::RunFwdRight
                       && Pick(Moving(F, -69.f * D2R, 341.f, false, false, EClip::Guard)) == EClip::RunRight;
        Check(Held, "a strafe is held 5 degrees past its octant's line, where a fresh pick takes the next");
        int Flips = 0; EClip Cur = EClip::WalkFwd;
        for (int I = 0; I < 200; ++I)
        {
            const EClip N = Pick(Moving(F, (22.5f + 3.f * std::sin(I * 0.7f)) * D2R, 150.f, false, false, Cur));
            Flips += N != Cur; Cur = N;
        }
        Check(Flips <= 1, "a heading held on an octant's line does not flicker between two strafes");
    }

    // ---- the tier by speed: Walk below the geometric mean of WalkShare x run and the run, +-8 %
    {
        const float Line = std::sqrt(SaudSteer::WalkShare * 341.f * 341.f);
        const FVector F(1.f, 0.f, 0.f);
        auto At = [&](float V, EClip Cur, float Run = 341.f) { FMotionInput M = Moving(F, 90.f * D2R, V, false, false, Cur); M.RunSpeed = Run; return Pick(M); };
        std::printf("  the tiers' line at a run of 341 cm/s: %.1f cm/s\n", Line);
        Check(Near(TierLine(341.f), Line, 0.01f) && At(Line * 0.97f, EClip::Guard) == EClip::WalkLeft && At(Line * 1.03f, EClip::Guard) == EClip::RunLeft,
              "under the line between the tiers he walks, over it he runs");
        Check(At(Line * 1.06f, EClip::WalkLeft) == EClip::WalkLeft && At(Line * 1.10f, EClip::WalkLeft) == EClip::RunLeft
              && At(Line * 0.94f, EClip::RunLeft) == EClip::RunLeft && At(Line * 0.90f, EClip::RunLeft) == EClip::WalkLeft,
              "the tier showing is held 8 % past the line, not further");
        Check(At(180.f, EClip::Guard, 288.f) == EClip::WalkLeft && At(200.f, EClip::Guard, 288.f) == EClip::RunLeft
              && At(200.f, EClip::Guard, 446.f) == EClip::WalkLeft,
              "the line is each man's own: a Thug (288) runs at 200 cm/s, AL-SAQR (446) still walks");
        int Flips = 0; EClip Cur = EClip::WalkLeft;
        for (int I = 0; I < 200; ++I) { const EClip N = At(Line * (1.f + 0.05f * std::sin(I * 0.7f)), Cur); Flips += N != Cur; Cur = N; }
        Check(Flips <= 1, "a speed held at the tiers' line does not flicker between walk and run");
        Check(Pick(Moving(F, 0.f, 39.f, false, false)) == EClip::Guard && Pick(Moving(F, 0.f, 39.f, true, true)) == EClip::Guard,
              "under WalkThreshold he stands in his guard, free or fighting");
    }

    // ---- free: straight ahead his own way, off it the strafe of the angle
    {
        const FVector F = Rotate(FVector(1.f, 0.f, 0.f), 123.f * D2R);
        Check(Pick(Moving(F, 25.f * D2R, 341.f, true, true)) == EClip::GaitRun && Pick(Moving(F, -29.f * D2R, 150.f, true, true)) == EClip::GaitWalk,
              "free and going within 30 degrees of his drawn facing, Saud plays his gait");
        Check(Pick(Moving(F, 40.f * D2R, 341.f, true, true)) == EClip::RunFwdLeft && Pick(Moving(F, -90.f * D2R, 150.f, true, true)) == EClip::WalkRight,
              "...past 30 degrees, the walk or run strafe of that angle");
        Check(Pick(Moving(F, 33.f * D2R, 341.f, true, true, EClip::GaitRun)) == EClip::GaitRun
              && Pick(Moving(F, 36.f * D2R, 341.f, true, true, EClip::GaitRun)) == EClip::RunFwdLeft
              && Pick(Moving(F, 33.f * D2R, 341.f, true, true, EClip::RunFwdLeft)) == EClip::RunFwdLeft,
              "...the gait showing held to 35 degrees, a strafe showing until back inside 30");
        Check(Pick(Moving(F, 27.f * D2R, 341.f, true, false)) == EClip::RunFwd && Pick(Moving(F, -27.f * D2R, 150.f, true, false)) == EClip::WalkFwd
              && Pick(Moving(F, 100.f * D2R, 341.f, true, false)) == EClip::RunLeft,
              "free, a man with no gaits runs or walks his Run_Fwd / Walk_Fwd ahead and strafes off it");
        Check(Pick(Moving(F, 0.f, 341.f, false, true)) == EClip::RunFwd && Pick(Moving(F, 0.f, 150.f, false, true)) == EClip::WalkFwd,
              "fighting, Saud too strafes his tiers: no gait with a man near");
    }

    // ---- the turns: picked, held to their end, and only four things take over
    {
        FMotionInput M = Moving(FVector(1.f, 0.f, 0.f), 0.f, 0.f, true, true);
        bool Picked = true;
        const SaudSteer::ETurn T[4] = { SaudSteer::ETurn::L90, SaudSteer::ETurn::R90, SaudSteer::ETurn::Back180, SaudSteer::ETurn::Pivot180 };
        const EClip C[4] = { EClip::TurnL90, EClip::TurnR90, EClip::Turn180, EClip::Pivot180 };
        for (int I = 0; I < 4; ++I)
        {
            M = Moving(FVector(1.f, 0.f, 0.f), 0.f, 0.f, true, true); M.Turn = T[I];
            Picked = Picked && Pick(M) == C[I];
            M.Speed = 300.f; M.bBlocking = true; M.Victory = 1.f;
            Picked = Picked && Pick(M) == C[I];
        }
        Check(Picked, "a turn the steer started plays its own clip, moving or standing, over a block or the win");
        M = Moving(FVector(1.f, 0.f, 0.f), 0.f, 0.f, true, true); M.Turn = SaudSteer::ETurn::L90;
        bool Over = true;
        M.State = SAttack; Over = Over && Pick(M) == EClip::Attack;
        M.State = SHit;    Over = Over && KindOf(Pick(M)) == EKind::Reel;
        M.State = SDown;   Over = Over && KindOf(Pick(M)) == EKind::Fall;
        M.State = SDash;   Over = Over && KindOf(Pick(M)) == EKind::Dash;
        Check(Over, "...and an attack, a hit, a fall or a dash takes over from it");
        bool Held = true;
        for (float Hz : { 30.f, 60.f })
        {
            FTurnHold H;
            Held = Held && !H.Step(SaudSteer::ETurn::None, 0, 1.f / Hz) && H.Turn == SaudSteer::ETurn::None;
            Held = Held && H.Step(SaudSteer::ETurn::L90, 1, 1.f / Hz) && H.Turn == SaudSteer::ETurn::L90;
            float T0 = 0.f;
            while (H.Turn != SaudSteer::ETurn::None && T0 < 2.f) { H.Step(SaudSteer::ETurn::None, 1, 1.f / Hz); T0 += 1.f / Hz; }
            // its clip's own length, to the frame: the steer's turn may end first, the clip does not
            Held = Held && std::fabs(T0 - SaudSteer::TurnSeconds(SaudSteer::ETurn::L90)) <= 1.f / Hz + 1e-4f;
            Held = Held && H.Step(SaudSteer::ETurn::L90, 2, 1.f / Hz) && H.Turn == SaudSteer::ETurn::L90;
            Held = Held && H.Step(SaudSteer::ETurn::L90, 3, 1.f / Hz);          // the same turn again: a new start
            H.Stop(); Held = Held && H.Turn == SaudSteer::ETurn::None && !H.Step(SaudSteer::ETurn::None, 4, 1.f / Hz);
            H.Step(SaudSteer::ETurn::Back180, 5, 1.f / Hz);
            float T1 = 0.f;
            while (H.Turn != SaudSteer::ETurn::None && T1 < 2.f) { H.Step(SaudSteer::ETurn::Back180, 5, 1.f / Hz); T1 += 1.f / Hz; }
            Held = Held && std::fabs(T1 - 0.70f) <= 1.f / Hz + 1e-4f;
        }
        Check(Held, "a turn's clip is held for its own TurnSeconds from a new serial, at 30 and 60 Hz; a new serial starts it again; Stop ends it");
        FCut In = CutBetween(EClip::Guard, EClip::TurnL90, false), Run = CutBetween(EClip::RunFwd, EClip::Pivot180, false);
        Check(Near(In.Seconds, CutIntoTurn) && CutIntoTurn <= 0.07f && !In.bMatchPhase && Near(Run.Seconds, CutIntoTurn) && Restarts(EClip::TurnL90, true),
              "a turn or a pivot cuts in fast (0.06 s), from its first frame, and starts again on a new serial");
        Check(Near(CutBetween(EClip::Pivot180, EClip::RunFwd, false).Seconds, CutStep) && Near(CutBetween(EClip::TurnL90, EClip::Guard, false).Seconds, CutSettle),
              "a pivot steps on into its run; a turn on the spot settles into his guard");
        // the pivot's last frame is a frame of Run_Fwd, by set (the clip builders' measure)
        bool Share = true;
        for (const char* Men : { "Saud", "Street", "Thug", "Brawler", "Boss", "Saqr", "Zayos" })
            Share = Share && Near(PivotRunShare(Men), 13.f / 17.f) && Near(CutBetween(EClip::Pivot180, EClip::RunFwd, false, Men).StartShare, 13.f / 17.f);
        Share = Share && Near(PivotRunShare("Monkey"), 10.f / 12.f) && Near(PivotRunShare("Gorilla"), 15.f / 20.f)
            && Near(CutBetween(EClip::Pivot180, EClip::GaitRun, false, "Saud").StartShare, 13.f / 17.f)
            && Near(CutBetween(EClip::Pivot180, EClip::WalkFwd, false, "Gorilla").StartShare, 0.75f)
            && CutBetween(EClip::Pivot180, EClip::Guard, false, "Saud").StartShare < 0.f
            && CutBetween(EClip::Pivot180, EClip::RunFwd, true, "Saud").StartShare < 0.f
            && CutBetween(EClip::RunFwd, EClip::RunFwdLeft, false, "Saud").StartShare < 0.f;
        Check(Share, "a pivot hands over into Run_Fwd at its set's own phase: the men 13 of 17, the Monkey 10 of 12, the Gorilla 15 of 20");
        Check(Near(CutBetween(EClip::RunFwd, EClip::RunRight, false).ShareShift, 0.5f) && Near(CutBetween(EClip::RunRight, EClip::RunFwdRight, false).ShareShift, -0.5f)
              && Near(CutBetween(EClip::RunFwd, EClip::RunLeft, false).ShareShift, 0.f) && Near(CutBetween(EClip::WalkFwd, EClip::WalkRight, false).ShareShift, 0.f),
              "a phase-matched cut into or out of Run_Right keeps the feet: its right foot lands first, half a cycle off the rest");
        const FCut S1 = CutBetween(EClip::RunLeft, EClip::RunFwdLeft, false), S2 = CutBetween(EClip::WalkBackRight, EClip::RunBackRight, false);
        Check(S1.bMatchPhase && S2.bMatchPhase && Near(S1.Seconds, CutStep) && Near(S2.Seconds, CutStep)
              && CutBetween(EClip::GaitRun, EClip::RunFwdLeft, false).bMatchPhase,
              "strafe to strafe, walk to run and a gait into a strafe keep the phase, as steps do");
    }

    // ---- the fallbacks: the nearer neighbour, a run's walk, a turn's guard
    {
        auto Is = [](const FClipChain& C, std::initializer_list<EClip> L)
        {
            if (C.Num != (int)L.size()) return false;
            int I = 0; for (EClip E : L) if (C.Clip[I++] != E) return false;
            return true;
        };
        Check(Is(FallbackChain(EClip::RunFwdLeft, 30.f), { EClip::RunFwdLeft, EClip::RunFwd, EClip::RunLeft, EClip::WalkFwdLeft, EClip::WalkFwd, EClip::WalkLeft })
              && Is(FallbackChain(EClip::RunFwdLeft, 60.f), { EClip::RunFwdLeft, EClip::RunLeft, EClip::RunFwd, EClip::WalkFwdLeft, EClip::WalkLeft, EClip::WalkFwd })
              && Is(FallbackChain(EClip::WalkBackRight, -150.f), { EClip::WalkBackRight, EClip::WalkBack, EClip::WalkRight })
              && Is(FallbackChain(EClip::WalkBackRight, -120.f), { EClip::WalkBackRight, EClip::WalkRight, EClip::WalkBack }),
              "a missing diagonal falls back to the neighbour nearer the heading, then the other; a run diagonal's walk after its runs");
        Check(Is(FallbackChain(EClip::WalkFwdLeft, 45.f), { EClip::WalkFwdLeft, EClip::WalkFwd, EClip::WalkLeft })
              && Is(FallbackChain(EClip::WalkBackLeft, 135.f), { EClip::WalkBackLeft, EClip::WalkLeft, EClip::WalkBack }),
              "...a heading on the diagonal itself takes the neighbour nearer Fwd");
        Check(Is(FallbackChain(EClip::RunLeft, 90.f), { EClip::RunLeft, EClip::WalkLeft }) && Is(FallbackChain(EClip::RunFwd, 0.f), { EClip::RunFwd, EClip::WalkFwd })
              && Fallback(EClip::RunBack) == EClip::WalkBack && Fallback(EClip::WalkLeft) == EClip::WalkLeft,
              "a run strafe falls back to its walk; a walk's straight four are the floor");
        Check(Is(FallbackChain(EClip::TurnL90, 0.f), { EClip::TurnL90, EClip::Guard }) && Is(FallbackChain(EClip::Pivot180, 0.f), { EClip::Pivot180, EClip::Guard })
              && Fallback(EClip::Turn180) == EClip::Guard && Fallback(EClip::TurnR90) == EClip::Guard,
              "a turn a set lacks stands in his guard");
        Check(Is(FallbackChain(EClip::HitHeadSide, 0.f), { EClip::HitHeadSide, EClip::HitHeavy }) && Is(FallbackChain(EClip::GaitJog, 0.f), { EClip::GaitJog, EClip::WalkFwd }),
              "...and everything else falls back as it did");
    }

    // ---- on disk, every set: what plays now, through the fallbacks; and the spec's own files
    {
        const char* Sets[] = { "Saud", "Street", "Boss", "Saqr", "Zayos", "Monkey", "Gorilla" };
        int Unplayable = 0, Missing = 0, Total = 0;
        for (const char* Set : Sets)
        {
            for (const FName_& N : Names)
            {
                ++Total;
                if (!OnDisk(OwnPath(Set, N.Name))) ++Missing;
                const float Angle = DirOf(N.C) >= 0 ? DirOf(N.C) * 45.f : 0.f;
                const FClipChain C = FallbackChain(N.C, Angle);
                bool Found = false;
                for (int I = 0; I < C.Num && !Found; ++I) Found = !Resolve(Set, ClipSuffix(C.Clip[I])).empty();
                if (!Found) { ++Unplayable; std::printf("  %s: %s plays nothing\n", Set, N.Name); }
            }
        }
        Check(Unplayable == 0, "every 360 clip plays something for every set today, Saud's to the Island's, through its fallbacks");
        std::printf("  the spec's %d clip files x %d sets, each in the set's own folder: %d not on disk yet\n", (int)(sizeof Names / sizeof Names[0]), (int)(sizeof Sets / sizeof Sets[0]), Missing);
        Pending(Missing == 0, "CLIPS AWAITED: every 360 spec clip (Walk_x8, Run_x8, Turn_L90/R90/180, Pivot_180) is on disk in every set's own folder");
        (void)Total;
    }
}

// ------------------------------------------------------------ the cuts

static const EClip EveryClip[] = { EClip::Guard, EClip::WalkFwd, EClip::WalkBack, EClip::WalkLeft, EClip::WalkRight,
    EClip::DashFwd, EClip::DashBack, EClip::DashLeft, EClip::DashRight, EClip::Block, EClip::HitLight, EClip::HitHeavy,
    EClip::Down, EClip::GetUp, EClip::Attack, EClip::HitHeadStraightLight, EClip::HitHeadStraight, EClip::HitHeadSide,
    EClip::HitBodyFront, EClip::HitBodySide, EClip::DownSide, EClip::DownFold, EClip::Death, EClip::Victory,
    EClip::GaitWalkSlow, EClip::GaitWalk, EClip::GaitWalkBrisk, EClip::GaitJog, EClip::GaitRun,
    EClip::WalkFwdLeft, EClip::WalkBackLeft, EClip::WalkBackRight, EClip::WalkFwdRight,
    EClip::RunFwd, EClip::RunFwdLeft, EClip::RunLeft, EClip::RunBackLeft, EClip::RunBack, EClip::RunBackRight, EClip::RunRight, EClip::RunFwdRight,
    EClip::TurnL90, EClip::TurnR90, EClip::Turn180, EClip::Pivot180 };

static std::vector<std::vector<std::string>> CsvRows(const char* Path)
{
    std::vector<std::vector<std::string>> Rows;
    FILE* F = std::fopen(Path, "rb");
    if (!F) return Rows;
    char Line[512];
    while (std::fgets(Line, sizeof Line, F))
    {
        std::vector<std::string> Col; std::string Cur;
        for (const char* P = Line; *P; ++P) { if (*P == ',') { Col.push_back(Cur); Cur.clear(); } else if (*P != '\n' && *P != '\r') Cur += *P; }
        Col.push_back(Cur); Rows.push_back(Col);
    }
    std::fclose(F);
    return Rows;
}

static void Cuts()
{
    std::printf("CUTS  (how one clip gives way to the next)\n");
    int Hard = 0, PhaseWrong = 0;
    for (EClip A : EveryClip) for (EClip B : EveryClip) for (bool R : { false, true })
    {
        const FCut C = CutBetween(A, B, R);
        if (C.Seconds < 1.f / 60.f) ++Hard;
        const bool Walks = KindOf(A) == EKind::Step && KindOf(B) == EKind::Step;
        const bool Breath = (A == EClip::Guard && B == EClip::Block) || (A == EClip::Block && B == EClip::Guard);
        if (C.bMatchPhase && (R || !Loops(B) || !(Walks || Breath))) ++PhaseWrong;
        if (!C.bMatchPhase && !R && (Walks || Breath)) ++PhaseWrong;
    }
    Check(Hard == 0, "no clip cuts to another in under one 60 Hz frame: every change is a crossfade");
    Check(PhaseWrong == 0, "only walk to walk, and the guard to the block and back, keep the cycle; a one-shot and a restart start on their first frame");
    {
        int Rows = 0, Late = 0;
        for (const auto& Col : CsvRows("Content/Data/DT_Attacks.csv"))
        {
            if (Col.size() < 4 || Col[0] == "Name") continue;
            ++Rows;
            const float Startup = static_cast<float>(std::atof(Col[3].c_str()));
            for (EClip A : EveryClip) for (bool R : { false, true })
                if (CutBetween(A, EClip::Attack, R).Seconds >= Startup) ++Late;
        }
        Check(Rows >= 6 && Late == 0, "every strike in DT_Attacks is whole before its first active frame, from any clip");
    }
    {
        int Slow = 0;
        for (EClip A : EveryClip) for (EClip B : EveryClip) for (bool R : { false, true })
            if (KindOf(B) == EKind::Reel && CutBetween(A, B, R).Seconds >= 0.040f) ++Slow;
        Check(Slow == 0, "a hit reaction cuts in faster than its 40 ms rise");
    }
    {
        int Slow = 0;
        for (EClip A : EveryClip) if (CutBetween(A, EClip::Block, false).Seconds > 0.10f) ++Slow;
        Check(Slow == 0, "a block is up inside the first half of the 0.20 s parry window");
        Check(CutBetween(EClip::WalkFwd, EClip::WalkLeft, false).Seconds <= 0.571f / 3.f, "walk to walk crossfades inside a third of its 0.571 s stride");
    }
    {
        int Rows = 0, Long = 0;
        for (const auto& Col : CsvRows("Content/Animation/Saud/DT_SaudMotion.csv"))
        {
            if (Col.size() < 11 || Col[0] == "Name" || Col[8] == "true") continue;
            const std::string& N = Col[0];
            if (N.find("_Pair_") != std::string::npos || N.find("_Combo_") != std::string::npos) continue;
            const float Len = static_cast<float>(std::atof(Col[4].c_str()));
            EClip To = EClip::Guard; bool Known = false;
            if (!Col[2].empty()) { To = EClip::Attack; Known = true; }
            else for (EClip C : EveryClip) if (ClipSuffix(C)[0] && N == std::string("A_Saud_") + ClipSuffix(C)) { To = C; Known = true; }
            if (!Known) continue;
            ++Rows;
            for (EClip A : EveryClip) for (bool R : { false, true })
                if (CutBetween(A, To, R).Seconds > 0.25f * Len) { ++Long; std::printf("  %s: %.2f s cut into %.2f s\n", N.c_str(), CutBetween(A, To, R).Seconds, Len); }
        }
        Check(Rows >= 20 && Long == 0, "no cut takes more than a quarter of the clip it cuts into");
    }
    Check(KeepsClip(EClip::DashLeft, EClip::DashFwd, false) && !KeepsClip(EClip::DashLeft, EClip::DashFwd, true)
          && !KeepsClip(EClip::DashLeft, EClip::Guard, false) && !KeepsClip(EClip::WalkLeft, EClip::WalkFwd, false),
          "one dash keeps its clip while the body comes round; a new dash, or leaving it, picks again");
    Check(Restarts(EClip::HitLight, true) && Restarts(EClip::Attack, true) && Restarts(EClip::DashFwd, true) && Restarts(EClip::Victory, true)
          && !Restarts(EClip::Attack, false) && !Restarts(EClip::Guard, true) && !Restarts(EClip::WalkFwd, true) && !Restarts(EClip::Block, true),
          "a second hit, jab, dash or win starts from its first frame; a loop never restarts");
}

// ------------------------------------------- Saud's free walk and run

static EClip GaitAt(float Speed, EClip Current, bool bFree = true)
{
    FMotionInput In;
    In.State = SWalk;
    In.Speed = Speed;
    In.bFree = bFree;
    In.bGaits = true;          // Saud's set
    In.Current = Current;
    return Pick(In);
}

static void FreeGaits()
{
    std::printf("GAITS  (Saud's walk and run, picked by speed when no man is near)\n");
    // the speeds are the clips' own, as the motion capture measured them
    const auto Rows = CsvRows("Content/Animation/Saud/DT_SaudMocap.csv");
    int Matched = 0;
    for (int I = 0; I < NumGaits; ++I)
    {
        const std::string Name = std::string("A_Saud_") + ClipSuffix(Gaits[I].Clip);
        for (const auto& R : Rows)
            if (R.size() > 5 && R[0] == Name && std::fabs(std::atof(R[5].c_str()) - Gaits[I].SpeedCm) < 0.5f) ++Matched;
        const std::string P = "Content/Animation/Saud/" + Name + ".fbx";
        FILE* F = std::fopen(P.c_str(), "rb");
        Check(F != nullptr, ("the gait's clip is on disk: " + P).c_str());
        if (F) std::fclose(F);
    }
    Check(Matched == NumGaits, "every gait's speed is its clip's own (DT_SaudMocap.csv)");
    bool Rising = true;
    for (int I = 1; I < NumGaits; ++I) Rising = Rising && Gaits[I].SpeedCm > Gaits[I - 1].SpeedCm;
    Check(Rising, "the gaits rise in speed: slow walk, walk, brisk walk, jog, run");

    // picked by speed, nearest by ratio
    Check(GaitAt(60.f, EClip::Guard) == EClip::GaitWalkSlow, "a stroll is the slow walk");
    Check(GaitAt(150.f, EClip::Guard) == EClip::GaitWalk, "1.5 m/s is the walk");
    Check(GaitAt(200.f, EClip::Guard) == EClip::GaitWalkBrisk, "2 m/s is the brisk walk");
    Check(GaitAt(270.f, EClip::Guard) == EClip::GaitJog, "2.7 m/s is the jog");
    Check(GaitAt(341.f, EClip::Guard) == EClip::GaitRun, "his full speed (341 cm/s, Player.json) is the run");
    Check(GaitAt(30.f, EClip::Guard) == EClip::Guard, "under WalkThreshold he stands");

    // held across a line, not flickering
    const float Line = std::sqrt(Gaits[2].SpeedCm * Gaits[3].SpeedCm);
    Check(GaitAt(Line * 1.04f, EClip::GaitWalkBrisk) == EClip::GaitWalkBrisk, "a brisk walk is held a little past the line to the jog");
    Check(GaitAt(Line * 1.04f, EClip::Guard) == EClip::GaitJog, "...where coming fresh, it is the jog");
    Check(GaitAt(Line * 1.12f, EClip::GaitWalkBrisk) == EClip::GaitJog, "...and well past it, the jog");
    int Flips = 0;
    EClip Cur = EClip::GaitWalkBrisk;
    for (int I = 0; I < 200; ++I)
    {
        const EClip N = GaitAt(Line * (1.f + 0.03f * std::sin(I * 0.7f)), Cur);
        Flips += N != Cur;
        Cur = N;
    }
    Check(Flips <= 1, "a stick held at a line does not flicker between two gaits");

    // only when free, and never over what a fight asks
    Check(GaitAt(341.f, EClip::Guard, false) == EClip::RunFwd && GaitAt(150.f, EClip::Guard, false) == EClip::WalkFwd,
          "with a man near, he steps on his guard: his run and walk tiers, not the gaits");
    {
        FMotionInput In; In.State = SBlock; In.Speed = 300.f; In.bFree = true;
        Check(Pick(In) == EClip::Block, "free or not, a block is a block");
        In.State = SAttack;
        Check(Pick(In) == EClip::Attack, "...and a strike a strike");
    }

    // they loop, step into each other on the phase, and stand in for the
    // guard's step forward when they are not imported
    bool Loop = true, Step = true;
    for (int I = 0; I < NumGaits; ++I)
    {
        Loop = Loop && Loops(Gaits[I].Clip);
        Step = Step && KindOf(Gaits[I].Clip) == EKind::Step && Fallback(Gaits[I].Clip) == EClip::WalkFwd;
    }
    Check(Loop && Step, "every gait loops, is a step, and falls back to the guard's step forward");
    const FCut C = CutBetween(EClip::GaitWalk, EClip::GaitRun, false);
    Check(C.bMatchPhase, "a walk into a run keeps the phase: foot on foot");

    // every speed from the slow walk's own to his fastest (five Vitality
    // levels faster) plays its gait inside the stride's rate band, by the
    // stride the runtime measured
    const float Top = 341.f + 5.f * 22.f;
    float Worst = 1.f, Lowest = 9.f;
    for (float V = Gaits[0].SpeedCm; V <= Top; V += 5.f)
    {
        const EClip G = GaitAt(V, EClip::Guard);
        const SaudPlants::FClip* P = SaudPlants::Find((std::string("A_Saud_") + ClipSuffix(G)).c_str());
        if (!P) { Worst = 99.f; break; }
        const float Rate = V / P->Stride;
        if (Rate > Worst) Worst = Rate;
        if (Rate < Lowest) Lowest = Rate;
    }
    std::printf("  from %.0f to %.0f cm/s the gaits play at %.2f to %.2f of their own pace\n", Gaits[0].SpeedCm, Top, Lowest, Worst);
    Check(Lowest >= SaudIK::StrideRateMin && Worst <= SaudIK::StrideRateMax,
          "from the slow walk to his fastest, every gait plays inside the stride's rate band");
    bool Held = true;
    for (int I = 0; I < NumGaits; ++I)
    {
        const SaudPlants::FClip* P = SaudPlants::Find((std::string("A_Saud_") + ClipSuffix(Gaits[I].Clip)).c_str());
        Held = Held && P && SaudIK::HoldsFeetMeasured(false, false, P->Stride);
    }
    Check(Held, "every gait's measured stride is a walk's: the runtime holds its feet and sets its pace");
}


// ------------------------------------------------------------------ music

/** DT_Sounds.csv: cue -> the asset path's file under Content/. */
static std::map<std::string, std::string> SoundFiles()
{
    std::map<std::string, std::string> Out;
    FILE* F = std::fopen("Content/Data/DT_Sounds.csv", "rb");
    if (!F) return Out;
    char Line[1024];
    while (std::fgets(Line, sizeof Line, F))
    {
        std::string L(Line);
        const size_t A = L.find(','), B = L.find(',', A + 1);
        if (A == std::string::npos || B == std::string::npos) continue;
        std::string Path = L.substr(A + 1, B - A - 1);            // /Game/Audio/Music/M_X.M_X
        const size_t Dot = Path.rfind('.');
        if (Path.rfind("/Game/", 0) != 0 || Dot == std::string::npos) continue;
        Out[L.substr(0, A)] = "Content/" + Path.substr(6, Dot - 6) + ".wav";
    }
    std::fclose(F);
    return Out;
}

static void BossThemes()
{
    std::printf("BOSS MUSIC\n");
    const auto Files = SoundFiles();
    Check(!Files.empty(), "DT_Sounds.csv read");
    auto OnDisk = [](const std::string& P) { FILE* F = std::fopen(P.c_str(), "rb"); if (F) std::fclose(F); return F != nullptr; };
    for (const char* Cue : { SaudFeel::BossMusic, SaudFeel::StageMusic })
    {
        const auto It = Files.find(Cue);
        Check(It != Files.end() && OnDisk(It->second), (std::string(Cue) + " has a row and a file").c_str());
    }
    FILE* F = std::fopen("Content/Data/DT_Fighters.csv", "rb");
    Check(F != nullptr, "DT_Fighters.csv found");
    int Bosses = 0;
    std::vector<std::string> Themes;
    if (F)
    {
        char Line[1024];
        if (!std::fgets(Line, sizeof Line, F)) Line[0] = 0;
        while (std::fgets(Line, sizeof Line, F))
        {
            std::vector<std::string> C; std::string Cur; bool Q = false;
            for (const char* P = Line; *P && *P != '\n' && *P != '\r'; ++P)
            {
                if (*P == '"') Q = !Q;
                else if (*P == ',' && !Q) { C.push_back(Cur); Cur.clear(); }
                else Cur += *P;
            }
            C.push_back(Cur);
            if (C.size() < 11) continue;
            const char* Theme = SaudFeel::BossTheme(C[0].c_str());
            if (C[10] != "true")
            {
                Check(Theme == nullptr, (C[0] + " is no boss and has no boss theme").c_str());
                continue;
            }
            ++Bosses;
            Check(Theme != nullptr, (C[0] + " fights to a theme of his own").c_str());
            if (!Theme) continue;
            // A theme's row is added with its file: a row with no file would
            // stop the music at the boss (PlayMusic finds no sound), where no
            // row falls back to Music_Boss (AWaveDirector::BeginWave).
            const auto It = Files.find(Theme);
            Check(It == Files.end() || OnDisk(It->second), (std::string(Theme) + " has a row only with its file on disk").c_str());
            for (const auto& T : Themes) Check(T != Theme, (C[0] + "'s theme is his alone").c_str());
            Themes.push_back(Theme);
        }
        std::fclose(F);
    }
    Check(Bosses == 3, "three boss rows");
    Check(!SaudFeel::BossTheme(nullptr) && !SaudFeel::BossTheme("Bos") && !SaudFeel::BossTheme("Bosses"),
          "a row is matched whole");
}

int main()
{
    Blows(); Pad(); State(); Camera(); Flash(); Clips(); Loco360(); Cuts(); FreeGaits(); BossThemes();
    std::printf(Fails ? "\n%d FAILED\n" : "\nall feel checks passed\n", Fails);
    return Fails ? 1 : 0;
}
