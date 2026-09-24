#pragma once

/**
 * What an enemy can see of the man he is fighting, and what a crowd of them
 * does about it -- with no engine in it.
 *
 * Until 2026-09-24 an enemy here read nothing. A style decided where to
 * stand and what to throw from there, and a guard went up on a roll while
 * the player was in the Attack state, whatever the attack or where it was
 * going. He never punished a whiff, never stepped off a line, never noticed
 * a raised guard covers only the front of a man, and a wave of six spread
 * itself by the order it spawned in, not by where the player was looking.
 *
 * Two things live here. The READ: a snapshot of the opponent -- his state,
 * his guard, which phase of which attack he is in and whether it is aimed
 * at me -- turned into one intent. It is honest on purpose: an attack is
 * not seen until it has been going for the style's reaction time, so a
 * 0.07 s jab is a surprise to everyone and a 0.16 s kick is readable by
 * the quick ones, which is exactly the difference a player can learn. And
 * the CROWD: roles by bearing off the player's own facing (one in front,
 * two on the flanks, one behind, two out wide), the attack tokens going to
 * whoever is placed to use one, and a fighter stepping off a teammate's
 * line rather than standing in it.
 *
 * Header of free functions and plain structs like SaudArena.h, so
 * Tools/harness builds it with g++ and checks it. States are ints in
 * EFighterState's order (SaudFeel.h mirrors the same enum; the harness
 * holds both to SaudTypes.h).
 */

#if defined(SAUD_HARNESS)
	#include "HarnessTypes.h"
#else
	#include "CoreMinimal.h"
#endif

namespace SaudBrain
{
	enum : int { SIdle = 0, SWalk, SAttack, SHit, SBlock, SDash, SDown, SDead };

	// ------------------------------------------------------------- the read

	/** What one fighter can see of another this frame. Filled by the
	    component from the opponent's public state; nothing in here is a
	    guess about his input. */
	struct FSeen
	{
		int State = SIdle;
		bool bBlocking = false;
		/** His front covers me: his guard, and his strikes, are aimed my way. */
		bool bFacingMe = true;
		/** He is throwing something, and these are its numbers. */
		bool bAttacking = false;
		float Elapsed = 0.f;
		float Startup = 0.f;
		float Active = 0.f;
		float Recovery = 0.f;
		/** I am inside the strike's box: it will land on me if it runs. */
		bool bInHisLine = false;
		/** Flat distance between us, cm. */
		float Distance = 0.f;
	};

	enum class EPhase : unsigned char { None, WindUp, Active, Recovery };

	inline EPhase PhaseOf(const FSeen& S)
	{
		if (!S.bAttacking) return EPhase::None;
		if (S.Elapsed < S.Startup) return EPhase::WindUp;
		if (S.Elapsed < S.Startup + S.Active) return EPhase::Active;
		return EPhase::Recovery;
	}

	/** Seconds until he can do anything else. Zero when he is not throwing. */
	inline float RecoveryLeft(const FSeen& S)
	{
		if (!S.bAttacking) return 0.f;
		return FMath::Max(0.f, S.Startup + S.Active + S.Recovery - S.Elapsed);
	}

	/** Seconds before his strike goes live. Zero once it has. */
	inline float UntilActive(const FSeen& S)
	{
		if (!S.bAttacking) return 0.f;
		return FMath::Max(0.f, S.Startup - S.Elapsed);
	}

	/** An attack is seen only once it has been going for the reaction
	    time. That is the whole of the fairness: the fastest strikes land on
	    everyone, and the slow ones can be read by the quick. */
	inline bool Noticed(const FSeen& S, float ReactionSeconds)
	{
		return S.bAttacking && S.Elapsed >= ReactionSeconds;
	}

	/** A strike that lands inside his recovery: mine must go live before
	    he is free again, give or take a frame. */
	constexpr float PunishSlack = 0.02f;

	inline bool CanPunish(float HisRecoveryLeft, float MyStartup, float Distance, float MyReach)
	{
		return HisRecoveryLeft > 0.f
			&& MyStartup <= HisRecoveryLeft + PunishSlack
			&& Distance <= MyReach + 40.f;      // InHitbox's own slack past the reach
	}

	/** The style's dials for reading. Defaults are what a style asset built
	    before these existed gets. */
	struct FReadDials
	{
		float ReactionSeconds = 0.18f;
		float GuardChance = 0.12f;
		/** Of the guards it would put up, the share that are a step off the
		    line instead. Light feet slip; heavy feet block. */
		float SlipShare = 0.f;
		float PunishChance = 0.5f;
		/** How much a guard facing it puts it off swinging into that guard:
		    the chance it goes round instead. */
		float GuardRespect = 0.5f;
	};

	/** A guard that has stopped this fighter's last few strikes earns more
	    respect: three in a row and almost nobody keeps swinging into it. */
	inline float GuardRespectNow(float Base, int BlockedInARow)
	{
		return FMath::Min(0.95f, Base + 0.22f * static_cast<float>(BlockedInARow));
	}

	/** A step off the line needs this much wind-up still to come; later
	    than that the foot is not down before the strike is. */
	constexpr float SlipNeedsSeconds = 0.06f;

	enum class EIntent : unsigned char
	{
		Free,     // nothing read: the style's own rhythm
		Guard,    // his strike is coming my way: block it
		Slip,     // his strike is coming my way: step off its line
		Punish,   // he is recovering and I can land one before he is free
		Press,    // he is stunned: keep it going
		Flank,    // his guard faces me: get round it
		Wait      // nothing to be done to him right now (dashing, down)
	};

	/** Read him. RollDefence and RollOffence are 0..1, rolled a few times a
	    second rather than every frame (a guard that re-decides sixty times a
	    second flickers). FastestStartup is the quickest strike legal from
	    here; MyReach its reach; bICanReach whether anything is legal. */
	inline EIntent Read(const FSeen& S, const FReadDials& D, float RollDefence, float RollOffence,
	                    float FastestStartup, float MyReach, bool bICanReach, int BlockedInARow)
	{
		if (S.State == SDead) return EIntent::Free;
		if (S.State == SDown || S.State == SDash) return EIntent::Wait;

		const EPhase P = PhaseOf(S);
		if ((P == EPhase::WindUp || P == EPhase::Active) && S.bInHisLine)
		{
			// Something is coming. Whether it is answered at all is the
			// browser's own guard roll (updateEnemy: guardRoll < guard while
			// the player attacks in range), which does not wait to see the
			// strike -- those are the numbers the game was tuned on. Of the
			// answers, the light-footed step off the line instead of
			// blocking, and only when the strike has been seen with time
			// left to get there.
			if (RollDefence < D.GuardChance)
			{
				const bool bTime = P == EPhase::WindUp && UntilActive(S) >= SlipNeedsSeconds;
				if (bTime && Noticed(S, D.ReactionSeconds) && RollDefence < D.GuardChance * D.SlipShare)
				{
					return EIntent::Slip;
				}
				return EIntent::Guard;
			}
			return EIntent::Free;
		}
		// He is recovering, or swinging at air: the window. Seen only once
		// the strike has been going for the reaction time.
		if (Noticed(S, D.ReactionSeconds) && (P == EPhase::Recovery || (P == EPhase::Active && !S.bInHisLine)))
		{
			if (bICanReach && RollOffence < D.PunishChance
				&& CanPunish(RecoveryLeft(S), FastestStartup, S.Distance, MyReach))
			{
				return EIntent::Punish;
			}
		}

		if (S.State == SHit && bICanReach) return EIntent::Press;

		if (S.bBlocking && S.bFacingMe)
		{
			return RollOffence < GuardRespectNow(D.GuardRespect, BlockedInARow) ? EIntent::Flank : EIntent::Free;
		}
		return EIntent::Free;
	}

	/** Which way to step off his line: across his facing, to whichever side
	    I am already on, so the step is short and away from the strike. */
	inline FVector SlipDirection(const FVector& HisFacing, const FVector& HimToMe)
	{
		const FVector Across(-HisFacing.Y, HisFacing.X, 0.f);
		const float Side = HimToMe.X * Across.X + HimToMe.Y * Across.Y;
		return Side >= 0.f ? Across : FVector(-Across.X, -Across.Y, 0.f);
	}

	constexpr float SlipSeconds = 0.20f;

	// ------------------------------------------------------------ the crowd

	/** Where a crowd stands, as bearings off the player's FACING: the
	    presser in front, a flank either side, one behind, two out wide in
	    front. Six is the biggest wave the tables spawn. Beyond six the
	    pattern repeats further out. */
	constexpr int RoleCount = 6;

	inline float RoleBearing(int Role)
	{
		static const float B[RoleCount] = { 0.f, 110.f, -110.f, 180.f, 50.f, -50.f };
		return B[((Role % RoleCount) + RoleCount) % RoleCount];
	}

	/** Roles past the first six stand a ring further out. */
	inline float RoleLane(int Role)
	{
		return static_cast<float>(Role / RoleCount) * 120.f;
	}

	/** The signed angle from his facing to a point, degrees in (-180, 180]:
	    positive to his left (Z up, X forward: +Y is left). */
	inline float BearingOf(const FVector& HisPos, const FVector& HisFacing, const FVector& P)
	{
		const FVector D(P.X - HisPos.X, P.Y - HisPos.Y, 0.f);
		const float Fwd = D.X * HisFacing.X + D.Y * HisFacing.Y;
		const float Left = D.X * -HisFacing.Y + D.Y * HisFacing.X;
		return FMath::RadiansToDegrees(FMath::Atan2(Left, Fwd));
	}

	inline float WrapDegrees(float A)
	{
		while (A > 180.f) A -= 360.f;
		while (A <= -180.f) A += 360.f;
		return A;
	}

	/** Where a role stands: Range out from him at the role's bearing off
	    his facing, plus the lane. */
	inline FVector RoleSpot(const FVector& HisPos, const FVector& HisFacing, float BearingDeg, float Range, float Lane)
	{
		const float R = FMath::DegreesToRadians(BearingDeg);
		const float C = FMath::Cos(R), S = FMath::Sin(R);
		const FVector Left(-HisFacing.Y, HisFacing.X, 0.f);
		const FVector Dir(HisFacing.X * C + Left.X * S, HisFacing.Y * C + Left.Y * S, 0.f);
		const float D = Range + Lane;
		return FVector(HisPos.X + Dir.X * D, HisPos.Y + Dir.Y * D, HisPos.Z);
	}

	/** Hand out roles: each role in turn (front first, since the presser
	    matters most) goes to the unassigned fighter already nearest that
	    bearing, so nobody crosses the whole ring for a spot someone else is
	    standing next to. OutRole[i] is the role of fighter i. N may exceed
	    RoleCount; later fighters take the same bearings a lane further out. */
	inline void AssignRoles(const FVector& HisPos, const FVector& HisFacing,
	                        const FVector* Positions, int N, int* OutRole)
	{
		for (int I = 0; I < N; ++I) OutRole[I] = -1;
		for (int Role = 0; Role < N; ++Role)
		{
			const float Want = RoleBearing(Role);
			int Best = -1;
			float BestErr = 1e9f;
			for (int I = 0; I < N; ++I)
			{
				if (OutRole[I] >= 0) continue;
				const float Err = FMath::Abs(WrapDegrees(BearingOf(HisPos, HisFacing, Positions[I]) - Want));
				if (Err < BestErr) { BestErr = Err; Best = I; }
			}
			if (Best >= 0) OutRole[Best] = Role;
		}
	}

	/** The way round him that raises my bearing: the tangent at my position,
	    anticlockwise seen from above. A step along it times RoleSteer's
	    answer moves me toward my role. Unit, on the ground. */
	inline FVector RoundHim(const FVector& HisPos, const FVector& MyPos)
	{
		const FVector Out(MyPos.X - HisPos.X, MyPos.Y - HisPos.Y, 0.f);
		const float Len = FMath::Sqrt(Out.X * Out.X + Out.Y * Out.Y);
		if (Len < 1e-3f) return FVector(0.f, 1.f, 0.f);
		return FVector(-Out.Y / Len, Out.X / Len, 0.f);
	}

	/** Steering toward a role: how hard to move round him (positive raises
	    my bearing, along RoundHim) to get from where I am to the role's
	    bearing. Inside the dead band the style's own circling takes over.
	    Returns -1..1. */
	constexpr float RoleDeadBandDegrees = 12.f;

	inline float RoleSteer(float NowBearing, float WantBearing)
	{
		const float E = WrapDegrees(WantBearing - NowBearing);
		if (FMath::Abs(E) <= RoleDeadBandDegrees) return 0.f;
		return FMath::Clamp(E / 60.f, -1.f, 1.f);
	}

	/** Is another fighter standing on my line to him? Inside Width of the
	    segment between us, and between us along it. */
	inline bool LineBlocked(const FVector& Self, const FVector& Him, const FVector& Other, float Width)
	{
		const FVector L(Him.X - Self.X, Him.Y - Self.Y, 0.f);
		const float Len = FMath::Sqrt(L.X * L.X + L.Y * L.Y);
		if (Len < 1e-3f) return false;
		const FVector Dir(L.X / Len, L.Y / Len, 0.f);
		const FVector D(Other.X - Self.X, Other.Y - Self.Y, 0.f);
		const float Along = D.X * Dir.X + D.Y * Dir.Y;
		if (Along <= 0.f || Along >= Len) return false;
		const float Across = D.X * -Dir.Y + D.Y * Dir.X;
		return FMath::Abs(Across) < Width;
	}

	/** Which way to step to clear a blocked line: across it, away from the
	    side the blocker is on. Unit, on the ground. */
	inline FVector ClearLineStep(const FVector& Self, const FVector& Him, const FVector& Other)
	{
		const FVector L(Him.X - Self.X, Him.Y - Self.Y, 0.f);
		const float Len = FMath::Sqrt(L.X * L.X + L.Y * L.Y);
		if (Len < 1e-3f) return FVector(1.f, 0.f, 0.f);
		const FVector Dir(L.X / Len, L.Y / Len, 0.f);
		const FVector Left(-Dir.Y, Dir.X, 0.f);
		const FVector D(Other.X - Self.X, Other.Y - Self.Y, 0.f);
		const float Side = D.X * Left.X + D.Y * Left.Y;
		return Side > 0.f ? FVector(-Left.X, -Left.Y, 0.f) : Left;
	}

	/** How well placed a fighter is to use an attack token: in his range
	    (1 at the range, 0 at double or half of it), a little better from the
	    front, where the player can see it coming, and nothing at all with a
	    teammate in the way. */
	inline float AttackScore(float Distance, float PreferredRange, float BearingDeg, bool bLineClear)
	{
		if (!bLineClear) return 0.f;
		const float R = FMath::Max(40.f, PreferredRange);
		const float Range = FMath::Max(0.f, 1.f - FMath::Abs(Distance - R) / R);
		const float Front = FMath::Abs(WrapDegrees(BearingDeg)) <= 90.f ? 0.25f : 0.f;
		return Range + Front;
	}

	inline bool IsBehind(float BearingDeg)
	{
		return FMath::Abs(WrapDegrees(BearingDeg)) > 120.f;
	}

	/** Whether one more attacker may join: a slot free, placed at all, and
	    never a second one from behind -- two men hitting a player in the
	    back at once is not a fight he can be expected to read. */
	inline bool MayAttack(float Score, bool bBehind, int Holders, int BehindHolders, int MaxHolders)
	{
		if (Score <= 0.f) return false;
		if (Holders >= MaxHolders) return false;
		if (bBehind && BehindHolders >= 1) return false;
		return true;
	}
}
