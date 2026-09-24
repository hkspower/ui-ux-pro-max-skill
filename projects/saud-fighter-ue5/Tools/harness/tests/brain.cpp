/**
 * The enemy's read of the player, and the crowd's roles, executed.
 *
 * SaudBrain.h turns what an enemy can see into one intent, and a wave into
 * roles round the player. This checks the read against the attack table's
 * own timings (a jab is unreadable, a kick is not; a punish lands inside a
 * recovery or not at all), the fairness rules (one attacker from behind,
 * nobody through a teammate), and that every geometric answer turns with
 * the fight. States are held to EFighterState's order in SaudTypes.h.
 */
#include "../HarnessTypes.h"
#include "../../../Source/SaudFighter/Combat/SaudBrain.h"

#include <cstdio>
#include <cstring>
#include <cmath>
#include <string>
#include <vector>
#include <map>

static int Fails = 0;
static void Check(bool Ok, const char* What)
{
    if (!Ok) { ++Fails; std::printf("  FAIL  %s\n", What); }
}
static bool Near(float A, float B, float Eps = 1e-3f) { return std::fabs(A - B) <= Eps; }

using namespace SaudBrain;

static FVector Rotate(const FVector& V, float Radians)
{
    const float C = std::cos(Radians), S = std::sin(Radians);
    return FVector(V.X * C - V.Y * S, V.X * S + V.Y * C, V.Z);
}

/** DT_Attacks.csv: Name -> (Startup, Active, Recovery, Reach). */
struct FAtk { float Startup, Active, Recovery, Reach; };
static std::map<std::string, FAtk> Attacks;

static void LoadAttacks()
{
    FILE* F = std::fopen("Content/Data/DT_Attacks.csv", "rb");
    Check(F != nullptr, "DT_Attacks.csv found");
    if (!F) return;
    char Line[512];
    if (!std::fgets(Line, sizeof Line, F)) Line[0] = 0;
    while (std::fgets(Line, sizeof Line, F))
    {
        std::vector<std::string> C; std::string Cur;
        for (const char* P = Line; *P; ++P)
        {
            if (*P == ',') { C.push_back(Cur); Cur.clear(); }
            else if (*P != '\n' && *P != '\r') Cur += *P;
        }
        C.push_back(Cur);
        if (C.size() < 7) continue;
        Attacks[C[0]] = FAtk{ std::stof(C[3]), std::stof(C[4]), std::stof(C[5]), std::stof(C[6]) };
    }
    std::fclose(F);
}

// -------------------------------------------------------------------- read

static FSeen Throwing(const char* Name, float Elapsed, bool bInLine, float Distance)
{
    FSeen S;
    S.State = SAttack; S.bAttacking = true;
    S.Startup = Attacks[Name].Startup; S.Active = Attacks[Name].Active; S.Recovery = Attacks[Name].Recovery;
    S.Elapsed = Elapsed; S.bInHisLine = bInLine; S.Distance = Distance;
    return S;
}

static void States()
{
    std::printf("STATES  (SIdle..SDead are EFighterState's order)\n");
    FILE* F = std::fopen("Source/SaudFighter/Combat/SaudTypes.h", "rb");
    std::string Src;
    if (F) { char Buf[4096]; size_t N; while ((N = std::fread(Buf, 1, sizeof Buf, F)) > 0) Src.append(Buf, N); std::fclose(F); }
    const size_t At = Src.find("enum class EFighterState");
    const size_t End = Src.find("};", At);
    const char* Names[] = { "Idle", "Walk", "Attack", "Hit", "Block", "Dash", "Down", "Dead" };
    const int Mine[] = { SIdle, SWalk, SAttack, SHit, SBlock, SDash, SDown, SDead };
    bool Ok = At != std::string::npos && End != std::string::npos;
    size_t Pos = At;
    for (int I = 0; I < 8 && Ok; ++I)
    {
        const size_t Found = Src.find(Names[I], Pos);
        if (Found == std::string::npos || Found > End || Mine[I] != I) Ok = false;
        Pos = Found + std::strlen(Names[I]);
    }
    Check(Ok, "the mirror matches SaudTypes.h");
}

static void Phases()
{
    std::printf("PHASES  (the Cross: startup %.2f, active %.2f, recovery %.2f)\n",
                Attacks["Cross"].Startup, Attacks["Cross"].Active, Attacks["Cross"].Recovery);
    Check(PhaseOf(Throwing("Cross", 0.05f, true, 100.f)) == EPhase::WindUp, "winding up");
    Check(PhaseOf(Throwing("Cross", 0.12f, true, 100.f)) == EPhase::Active, "live");
    Check(PhaseOf(Throwing("Cross", 0.20f, true, 100.f)) == EPhase::Recovery, "recovering");
    FSeen Idle; Check(PhaseOf(Idle) == EPhase::None && RecoveryLeft(Idle) == 0.f, "not throwing: no phase, nothing left");
    Check(Near(RecoveryLeft(Throwing("Cross", 0.20f, true, 100.f)), 0.36f - 0.20f), "recovery left is the rest of the swing");
    Check(RecoveryLeft(Throwing("Cross", 0.50f, true, 100.f)) == 0.f, "...never negative");
    Check(Near(UntilActive(Throwing("Cross", 0.04f, true, 100.f)), 0.06f), "until active");
}

static void Reaction()
{
    std::printf("REACTION  (an attack is seen only after the reaction time)\n");
    // A jab's whole startup is 0.07 s: nobody sees it coming, so it is
    // only ever met by the browser's blind guard roll, never a step. A
    // kick's is 0.16: the quick (0.08) see it with time to step, the slow
    // (0.22) never see its wind-up at all.
    FReadDials Quick; Quick.ReactionSeconds = 0.08f; Quick.GuardChance = 1.f; Quick.SlipShare = 1.f;
    FReadDials Slow;  Slow.ReactionSeconds = 0.22f;  Slow.GuardChance = 1.f;  Slow.SlipShare = 1.f;
    const float JabStart = Attacks["Jab"].Startup, KickStart = Attacks["Kick"].Startup;
    Check(JabStart < Quick.ReactionSeconds, "the jab's startup is under everyone's reaction");
    Check(KickStart - SlipNeedsSeconds > Quick.ReactionSeconds && KickStart < Slow.ReactionSeconds,
          "the kick's wind-up is between the quick and the slow");
    Check(Read(Throwing("Jab", JabStart - 0.001f, true, 100.f), Quick, 0.f, 1.f, 0.07f, 130.f, true, 0) == EIntent::Guard,
          "a jab is met by the blind guard (the browser's rule), never a step");
    Check(Read(Throwing("Kick", 0.09f, true, 150.f), Quick, 0.f, 1.f, 0.07f, 130.f, true, 0) == EIntent::Slip,
          "a kick is stepped off by the quick");
    Check(Read(Throwing("Kick", 0.09f, true, 150.f), Slow, 0.f, 1.f, 0.07f, 130.f, true, 0) == EIntent::Guard,
          "...and only guarded by the slow");
    Check(!Noticed(Throwing("Kick", 0.05f, true, 150.f), 0.12f) && Noticed(Throwing("Kick", 0.12f, true, 150.f), 0.12f),
          "noticed at exactly the reaction time");
    // The punish needs the read too: the slow never punish a kick's
    // recovery seen only 0.20 s in... they do, since a kick runs 0.53 s.
    // What they cannot punish is a jab: its whole swing is 0.26 s and the
    // slow see it at 0.22 with 0.04 s left.
    FReadDials SlowP = Slow; SlowP.PunishChance = 1.f;
    Check(Read(Throwing("Jab", 0.23f, false, 100.f), SlowP, 1.f, 0.f, 0.07f, 130.f, true, 0) != EIntent::Punish,
          "the slow cannot punish a jab: by the time they see it, it is over");
    FReadDials QuickP = Quick; QuickP.PunishChance = 1.f;
    Check(Read(Throwing("Jab", 0.14f, false, 100.f), QuickP, 1.f, 0.f, 0.07f, 130.f, true, 0) == EIntent::Punish,
          "the quick can, in the 0.12 s of its recovery");
}

static void Defence()
{
    std::printf("DEFENCE  (guard, slip, or eat it)\n");
    FReadDials D; D.ReactionSeconds = 0.08f; D.GuardChance = 0.40f; D.SlipShare = 0.5f;
    const FSeen Kick = Throwing("Kick", 0.11f, true, 150.f);    // 0.05 s of wind-up left
    Check(Read(Kick, D, 0.39f, 1.f, 0.07f, 130.f, true, 0) == EIntent::Guard, "roll under the guard chance: guards");
    Check(Read(Kick, D, 0.41f, 1.f, 0.07f, 130.f, true, 0) == EIntent::Free, "roll over it: eats it (the browser's rule)");
    // Slip: takes the low half of the guard rolls, only with 60 ms of wind-up left.
    const FSeen Early = Throwing("Kick", 0.09f, true, 150.f);   // 0.07 s left
    Check(Read(Early, D, 0.10f, 1.f, 0.07f, 130.f, true, 0) == EIntent::Slip, "low roll with time: slips");
    Check(Read(Early, D, 0.30f, 1.f, 0.07f, 130.f, true, 0) == EIntent::Guard, "higher roll with time: guards");
    Check(Read(Kick, D, 0.10f, 1.f, 0.07f, 130.f, true, 0) == EIntent::Guard, "low roll, no time: guards, never slips late");
    const FSeen Last = Throwing("Kick", Attacks["Kick"].Startup - 0.03f, true, 150.f);
    Check(Read(Last, D, 0.10f, 1.f, 0.07f, 130.f, true, 0) == EIntent::Guard, "30 ms of wind-up left: no time to step");
    FReadDials Heavy = D; Heavy.SlipShare = 0.f;
    Check(Read(Early, Heavy, 0.0f, 1.f, 0.07f, 130.f, true, 0) == EIntent::Guard, "heavy feet never slip");
    // Not in his line: nothing to guard.
    const FSeen Wide = Throwing("Kick", 0.11f, false, 150.f);
    Check(Read(Wide, D, 0.f, 1.f, 0.07f, 130.f, true, 0) != EIntent::Guard, "a strike not aimed at me is not guarded");
    // Slip direction: across his facing, to my own side.
    const FVector HisFacing(1.f, 0.f, 0.f);
    FVector Step = SlipDirection(HisFacing, FVector(100.f, 15.f, 0.f));
    Check(Near(Step.Y, 1.f) && Near(Step.X, 0.f), "I am a little to his left: slip further left");
    Step = SlipDirection(HisFacing, FVector(100.f, -15.f, 0.f));
    Check(Near(Step.Y, -1.f), "a little to his right: slip right");
}

static void Punish()
{
    std::printf("PUNISH  (land inside his recovery, or not at all)\n");
    FReadDials D; D.ReactionSeconds = 0.10f; D.PunishChance = 1.f;
    // A kick at 0.30 s in: 0.23 s of recovery left. A jab (0.07) punishes; a
    // kick (0.16) punishes; nothing punishes with 0.05 left.
    const float KickTotal = Attacks["Kick"].Startup + Attacks["Kick"].Active + Attacks["Kick"].Recovery;
    FSeen Late = Throwing("Kick", 0.30f, false, 120.f);
    Check(Near(RecoveryLeft(Late), KickTotal - 0.30f), "recovery left");
    Check(Read(Late, D, 1.f, 0.f, Attacks["Jab"].Startup, 130.f, true, 0) == EIntent::Punish, "a jab punishes a kick's recovery");
    Check(Read(Late, D, 1.f, 0.f, Attacks["Kick"].Startup, 178.f, true, 0) == EIntent::Punish, "so does a kick, just");
    FSeen Nearly = Throwing("Kick", KickTotal - 0.03f, false, 120.f);
    Check(Read(Nearly, D, 1.f, 0.f, Attacks["Jab"].Startup, 130.f, true, 0) != EIntent::Punish, "30 ms left: too late even for a jab");
    FSeen Just = Throwing("Kick", KickTotal - 0.06f, false, 120.f);
    Check(Read(Just, D, 1.f, 0.f, Attacks["Jab"].Startup, 130.f, true, 0) == EIntent::Punish, "60 ms left: a jab still lands in it");
    Check(CanPunish(0.10f, 0.07f, 120.f, 130.f) && !CanPunish(0.10f, 0.16f, 120.f, 178.f), "the window is startup against recovery left");
    Check(!CanPunish(0.20f, 0.07f, 300.f, 130.f), "out of reach: no punish");
    Check(!CanPunish(0.f, 0.07f, 100.f, 130.f), "nothing to punish when he is free");
    // A whiff: he is live and I am not in his line -- the window opens at once.
    FSeen Whiff = Throwing("Kick", 0.18f, false, 120.f);
    Check(Read(Whiff, D, 1.f, 0.f, Attacks["Jab"].Startup, 130.f, true, 0) == EIntent::Punish, "a whiff is punished while he is still swinging");
    FSeen Live = Throwing("Kick", 0.18f, true, 120.f);
    Check(Read(Live, D, 1.f, 0.f, Attacks["Jab"].Startup, 130.f, true, 0) != EIntent::Punish, "...but not a strike that is landing on me");
    Check(Read(Late, D, 1.f, 0.f, Attacks["Jab"].Startup, 130.f, false, 0) != EIntent::Punish, "nothing legal from here: no punish");
    D.PunishChance = 0.3f;
    Check(Read(Late, D, 1.f, 0.5f, Attacks["Jab"].Startup, 130.f, true, 0) == EIntent::Free, "the punish chance is a chance");
}

static void Other()
{
    std::printf("PRESS, FLANK, WAIT\n");
    FReadDials D; D.GuardRespect = 0.5f;
    FSeen S;
    S.State = SHit; S.Distance = 100.f;
    Check(Read(S, D, 1.f, 1.f, 0.07f, 130.f, true, 0) == EIntent::Press, "he is stunned: press");
    Check(Read(S, D, 1.f, 1.f, 0.07f, 130.f, false, 0) == EIntent::Free, "...if anything is legal from here");
    S = FSeen(); S.State = SDash;
    Check(Read(S, D, 0.f, 0.f, 0.07f, 130.f, true, 0) == EIntent::Wait, "he is dashing: wait");
    S.State = SDown;
    Check(Read(S, D, 0.f, 0.f, 0.07f, 130.f, true, 0) == EIntent::Wait, "he is down: wait");
    S.State = SDead;
    Check(Read(S, D, 0.f, 0.f, 0.07f, 130.f, true, 0) == EIntent::Free, "he is dead: nothing");
    S = FSeen(); S.State = SBlock; S.bBlocking = true; S.bFacingMe = true;
    Check(Read(S, D, 1.f, 0.4f, 0.07f, 130.f, true, 0) == EIntent::Flank, "his guard faces me: go round it");
    Check(Read(S, D, 1.f, 0.6f, 0.07f, 130.f, true, 0) == EIntent::Free, "...or not, on the roll");
    S.bFacingMe = false;
    Check(Read(S, D, 1.f, 0.4f, 0.07f, 130.f, true, 0) == EIntent::Free, "his guard is turned away: it covers nothing of mine");
    // Respect grows with every strike the guard has stopped.
    Check(Near(GuardRespectNow(0.5f, 0), 0.5f) && Near(GuardRespectNow(0.5f, 2), 0.94f) && GuardRespectNow(0.5f, 5) <= 0.95f,
          "a guard that keeps stopping me earns respect, to a cap");
    S.bFacingMe = true;
    Check(Read(S, D, 1.f, 0.9f, 0.07f, 130.f, true, 3) == EIntent::Flank, "three blocked in a row: almost always round it");
    // Reading beats the guard rule: a raised guard does not stop a punish.
    // (A blocking man is not attacking, so this is the press case.)
    S = FSeen(); S.State = SHit; S.bBlocking = true; S.bFacingMe = true;
    Check(Read(S, D, 1.f, 0.f, 0.07f, 130.f, true, 0) == EIntent::Press, "stunned beats guarding");
}

// ------------------------------------------------------------------- crowd

static void Roles()
{
    std::printf("ROLES  (a wave round him, off his facing)\n");
    const FVector Him(0.f, 0.f, 0.f);
    // Bearings: front, flanks, back, wide.
    Check(RoleBearing(0) == 0.f && RoleBearing(3) == 180.f && RoleBearing(1) == -RoleBearing(2), "the six bearings");
    Check(RoleLane(0) == 0.f && RoleLane(6) > 0.f && RoleBearing(6) == RoleBearing(0), "the seventh repeats the first, further out");

    // Bearing: left is positive.
    const FVector F(1.f, 0.f, 0.f);
    Check(Near(BearingOf(Him, F, FVector(100.f, 0.f, 0.f)), 0.f), "ahead is 0");
    Check(Near(BearingOf(Him, F, FVector(0.f, 100.f, 0.f)), 90.f), "his left is +90");
    Check(Near(BearingOf(Him, F, FVector(-100.f, 0.f, 0.f)), 180.f) || Near(BearingOf(Him, F, FVector(-100.f, 0.f, 0.f)), -180.f), "behind is 180");
    Check(Near(WrapDegrees(370.f), 10.f) && Near(WrapDegrees(-190.f), 170.f) && Near(WrapDegrees(180.f), 180.f), "wrap");

    // A spot is at its range and its bearing.
    int Bad = 0;
    for (int A = 0; A < 360; A += 15)
    {
        const FVector Fc = Rotate(F, A * 3.14159265f / 180.f);
        for (int R = 0; R < RoleCount; ++R)
        {
            const FVector S = RoleSpot(Him, Fc, RoleBearing(R), 200.f, 0.f);
            if (!Near((S - Him).Size2D(), 200.f, 1e-2f)) ++Bad;
            if (!Near(FMath::Abs(WrapDegrees(BearingOf(Him, Fc, S) - RoleBearing(R))), 0.f, 0.05f)) ++Bad;
        }
    }
    Check(Bad == 0, "every role spot is its range out at its bearing, at every facing");

    // Six from one side: all six roles given, no two alike, the one already
    // in front gets the front, and the assignment turns with the facing.
    FVector P[6];
    for (int I = 0; I < 6; ++I) P[I] = FVector(600.f + I * 40.f, -200.f + I * 80.f, 0.f);
    int Role[6];
    AssignRoles(Him, F, P, 6, Role);
    bool Distinct = true; int Seen = 0;
    for (int I = 0; I < 6; ++I) { if (Role[I] < 0) Distinct = false; Seen |= 1 << Role[I]; }
    Check(Distinct && Seen == 63, "six fighters, six different roles");
    int FrontI = -1; float BestErr = 1e9f;
    for (int I = 0; I < 6; ++I) { const float E = FMath::Abs(BearingOf(Him, F, P[I])); if (E < BestErr) { BestErr = E; FrontI = I; } }
    Check(Role[FrontI] == 0, "the one nearest his front is the presser");
    Bad = 0;
    for (int A = 0; A < 360; A += 30)
    {
        const float Rad = A * 3.14159265f / 180.f;
        FVector Q[6]; int R2[6];
        for (int I = 0; I < 6; ++I) Q[I] = Rotate(P[I], Rad);
        AssignRoles(Him, Rotate(F, Rad), Q, 6, R2);
        for (int I = 0; I < 6; ++I) if (R2[I] != Role[I]) ++Bad;
    }
    Check(Bad == 0, "the roles turn with the fight");
    // Eight: two take the outer lane.
    FVector P8[8]; int R8[8];
    for (int I = 0; I < 8; ++I) P8[I] = Rotate(FVector(500.f, 0.f, 0.f), I * 0.7f);
    AssignRoles(Him, F, P8, 8, R8);
    int Outer = 0; for (int I = 0; I < 8; ++I) if (R8[I] >= RoleCount) ++Outer;
    Check(Outer == 2, "eight fighters: two on the outer ring");

    // Steering: toward the role, dead band inside 12 degrees.
    Check(RoleSteer(0.f, 5.f) == 0.f, "inside the dead band: the style circles as it likes");
    Check(RoleSteer(0.f, 110.f) == 1.f && RoleSteer(0.f, -110.f) == -1.f, "far off: full steer, to the left for a left bearing");
    Check(RoleSteer(170.f, -170.f) > 0.f, "the short way round the back");
    Check(Near(RoleSteer(0.f, 30.f), 0.5f), "half steer at 30 degrees");
    // A step along RoundHim raises my bearing, at every facing and position.
    Bad = 0;
    for (int A = 0; A < 360; A += 20)
    {
        const FVector Fc = Rotate(F, A * 3.14159265f / 180.f);
        for (int B = -170; B <= 170; B += 40)
        {
            const FVector Me = RoleSpot(Him, Fc, static_cast<float>(B), 250.f, 0.f);
            const FVector T = RoundHim(Him, Me);
            const FVector Me2 = Me + T * 20.f;
            if (WrapDegrees(BearingOf(Him, Fc, Me2) - BearingOf(Him, Fc, Me)) <= 0.f) ++Bad;
            if (!Near(T.Size2D(), 1.f)) ++Bad;
        }
    }
    Check(Bad == 0, "a step round him raises the bearing, everywhere");
}

static void Lines()
{
    std::printf("LINES  (nobody stands in a teammate's)\n");
    const FVector Me(0.f, 0.f, 0.f), Him(300.f, 0.f, 0.f);
    Check(LineBlocked(Me, Him, FVector(150.f, 20.f, 0.f), 60.f), "a man 20 cm off the middle of my line blocks it");
    Check(!LineBlocked(Me, Him, FVector(150.f, 80.f, 0.f), 60.f), "80 cm off: clear");
    Check(!LineBlocked(Me, Him, FVector(-50.f, 0.f, 0.f), 60.f), "behind me: clear");
    Check(!LineBlocked(Me, Him, FVector(350.f, 0.f, 0.f), 60.f), "beyond him: clear");
    Check(!LineBlocked(Me, Me, FVector(0.f, 0.f, 0.f), 60.f), "on top of him: no line");
    FVector Step = ClearLineStep(Me, Him, FVector(150.f, 20.f, 0.f));
    Check(Near(Step.Y, -1.f) && Near(Step.X, 0.f), "he is on my left: step right");
    Step = ClearLineStep(Me, Him, FVector(150.f, -20.f, 0.f));
    Check(Near(Step.Y, 1.f), "on my right: step left");
    int Bad = 0;
    for (int A = 0; A < 360; A += 10)
    {
        const float Rad = A * 3.14159265f / 180.f;
        const FVector O(150.f, 20.f, 0.f);
        if (!LineBlocked(Rotate(Me, Rad), Rotate(Him, Rad), Rotate(O, Rad), 60.f)) ++Bad;
        const FVector S = ClearLineStep(Rotate(Me, Rad), Rotate(Him, Rad), Rotate(O, Rad));
        if (FVector::Dist(S, Rotate(FVector(0.f, -1.f, 0.f), Rad)) > 1e-3f) ++Bad;
    }
    Check(Bad == 0, "blocked lines and the step off them turn with the fight");
}

static void Tokens()
{
    std::printf("TOKENS  (who gets to swing)\n");
    Check(AttackScore(130.f, 130.f, 0.f, true) > AttackScore(200.f, 130.f, 0.f, true), "nearer the range scores higher");
    Check(AttackScore(130.f, 130.f, 0.f, true) > AttackScore(130.f, 130.f, 180.f, true), "the front scores over the back");
    Check(AttackScore(130.f, 130.f, 0.f, false) == 0.f, "a blocked line scores nothing");
    Check(AttackScore(400.f, 130.f, 0.f, true) > 0.f && AttackScore(400.f, 130.f, 180.f, true) == 0.f,
          "well out of range, only the front bonus is left");
    Check(IsBehind(150.f) && IsBehind(-150.f) && !IsBehind(90.f), "behind is past 120 degrees");
    Check(MayAttack(1.f, false, 0, 0, 2), "a free slot: yes");
    Check(!MayAttack(1.f, false, 2, 0, 2), "both taken: no");
    Check(!MayAttack(0.f, false, 0, 0, 2), "unplaced: no");
    Check(MayAttack(1.f, true, 1, 0, 2), "one from behind is allowed");
    Check(!MayAttack(1.f, true, 1, 1, 2), "a second from behind is not");
}

int main()
{
    LoadAttacks();
    States(); Phases(); Reaction(); Defence(); Punish(); Other(); Roles(); Lines(); Tokens();
    std::printf(Fails ? "\n%d FAILED\n" : "\nall brain checks passed\n", Fails);
    return Fails ? 1 : 0;
}
