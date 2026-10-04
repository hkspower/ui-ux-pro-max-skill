#pragma once

/**
 * Which way a fighter faces while he moves, and when he is free to -- with
 * no engine in it.
 *
 * Asked 2026-10-04 as "make 360 motion move walk and run", settled with the
 * author as both modes for everyone (Saud, the street men, the bosses, the
 * creatures):
 *
 *   FIGHTING  he faces his man (the nearest living opponent, flat) and moves
 *             along his wish without turning to it: a strafe, 8 ways.
 *   FREE      no living opponent within FreeBeyondCm: he turns his body
 *             toward where he is going at a rate, never a snap -- a turn on
 *             the spot from standing (Turn_L90 / Turn_R90 / Turn_180, the
 *             clip carrying the turn while his movement is held), a
 *             Pivot_180 for a reversal at a run, and otherwise his facing
 *             chasing his heading at FreeTurnRate.
 *
 * Until this, every fighter's facing snapped in one frame
 * (AFighterBase::FaceTowards) and Saud's followed his stick in a fight too,
 * so he never strafed. The facing is still combat state -- the hitbox, the
 * guard's cover, the lunge and the knockback are measured along it -- so a
 * strike and a dash keep snapping it as they did; the rate here is only for
 * a free man walking.
 *
 * The C++ that drives it is AFighterBase (the free test, the turn's timer),
 * ASaudCharacter::Tick and the enemies' footwork; the clips that show it are
 * SaudFeel's Pick, which reads AFighterBase::IsMovingFree / GetLocoTurn.
 * Header of free functions and plain structs, like SaudArena.h, so
 * Tools/harness builds it with g++ and checks it (tests/steer.cpp).
 *
 * Angles are degrees, Unreal's yaw (0 looks down +X, positive turns toward
 * +Y), which is a turn to the fighter's LEFT: "+ = his left" throughout.
 */

#if defined(SAUD_HARNESS)
	#include "HarnessTypes.h"
#else
	#include "CoreMinimal.h"
#endif

#include <cmath>

namespace SaudSteer
{
	// ------------------------------------------------------------ the names
	/** The turn clip playing, if any. L90 / R90 / Back180 are from standing
	    (Turn_L90, Turn_R90, Turn_180); Pivot180 is the reversal at a run.
	    unsigned char is the engine's uint8. */
	enum class ETurn : unsigned char { None, L90, R90, Back180, Pivot180 };

	/** How long each turn holds his movement -- the clip's own length, which
	    Tools/blender's builders author to the frame at 30 fps. */
	constexpr float TurnSeconds(ETurn Turn)
	{
		return Turn == ETurn::L90 ? 0.50f
			: Turn == ETurn::R90 ? 0.50f
			: Turn == ETurn::Back180 ? 0.70f
			: Turn == ETurn::Pivot180 ? 0.45f
			: 0.f;
	}

	/** Free when no living opponent is within FreeBeyondCm; fighting again
	    inside FreeBeyondCm - FreeBandCm. Between the two, as he was: a man
	    standing on the line does not flick him between his guard and his
	    walk. (The camera's own SaudCamera::EngageCm, 15 m, is its own.) */
	constexpr float FreeBeyondCm = 1200.f;
	constexpr float FreeBandCm = 100.f;

	/** The walk tier is struck at this share of his full speed; the run tier
	    at his full speed. */
	constexpr float WalkShare = 0.45f;

	/** The eight ways, against his facing, + = his left: index = the clip's
	    direction (Fwd, FwdLeft, Left, BackLeft, Back, BackRight, Right,
	    FwdRight), the octant's centre at index x 45 degrees. */
	enum EDir : int { Fwd = 0, FwdLeft, Left, BackLeft, Back, BackRight, Right, FwdRight, NumDirs };
	/** Each octant is its centre +- this; a line between two goes to the one
	    nearer Fwd (as SaudFeel::Quadrant gives forward the tie). */
	constexpr float OctantHalfDeg = 22.5f;
	/** The octant showing is kept until the heading is this far past its
	    line, so a heading held on a line does not flick two clips. */
	constexpr float OctantHoldDeg = 5.f;

	// ------------------------------------------------------ the free steer
	/** Standing: under this flat speed (SaudFeel::WalkThreshold, the speed
	    under which the clip is his Guard; steer.cpp holds the two equal). */
	constexpr float StandingCm = 40.f;
	/** The stick counts as pushed past this squared length (Saud's old
	    facing gate: 0.03, a push of about 0.17). */
	constexpr float PushedSq = 0.03f;
	/** Standing, a wish more than this off his facing is a turn on the spot
	    first; up to BackAboveDeg it is a quarter turn, past it Turn_180. */
	constexpr float TurnAboveDeg = 45.f;
	constexpr float BackAboveDeg = 135.f;
	/** Moving, a reversal past PivotAboveDeg at over PivotShare of his run
	    speed is a Pivot_180. */
	constexpr float PivotAboveDeg = 135.f;
	constexpr float PivotShare = 0.6f;
	/** How fast his facing chases his heading: TurnRateWalk at his walk
	    tier's speed (WalkShare of his run) and under, TurnRateRun at his full
	    speed and over, straight between. A runner turns wider. */
	constexpr float TurnRateWalk = 540.f;
	constexpr float TurnRateRun = 360.f;

	// -------------------------------------------------------------- angles
	/** Any angle into (-180, 180]. */
	inline float Wrap180(float Deg)
	{
		float A = std::fmod(Deg, 360.f);
		if (A > 180.f) A -= 360.f;
		if (A <= -180.f) A += 360.f;
		return A;
	}

	/** A flat direction's yaw, degrees. */
	inline float YawOf(const FVector& V)
	{
		return FMath::RadiansToDegrees(FMath::Atan2(static_cast<float>(V.Y), static_cast<float>(V.X)));
	}

	/** The flat unit direction of a yaw. */
	inline FVector DirOf(float YawDeg)
	{
		const float R = FMath::DegreesToRadians(YawDeg);
		return FVector(FMath::Cos(R), FMath::Sin(R), 0.f);
	}

	/** How far the heading is turned from the facing, + to his left,
	    (-180, 180]; 0 when either is nothing. */
	inline float ErrorDeg(const FVector& Facing, const FVector& Heading)
	{
		const float Fwd = static_cast<float>(Facing.X * Heading.X + Facing.Y * Heading.Y);
		const float Side = static_cast<float>(Facing.X * Heading.Y - Facing.Y * Heading.X);
		if (Fwd * Fwd + Side * Side < 1e-12f) return 0.f;
		return Wrap180(FMath::RadiansToDegrees(FMath::Atan2(Side, Fwd)));
	}

	// ------------------------------------------------------------ the octant
	/** Which of the eight ways the heading is, against the facing: 0..7 in
	    EDir's order, + = his left. Current (-1 for none) is kept while the
	    heading is within OctantHalfDeg + OctantHoldDeg of its centre.
	    Nothing to go by (a zero heading or facing) keeps Current, or Fwd. */
	inline int Octant(const FVector& Facing, const FVector& Heading, int Current)
	{
		const bool bHas = (Facing.X * Facing.X + Facing.Y * Facing.Y) > 1e-8
			&& (Heading.X * Heading.X + Heading.Y * Heading.Y) > 1e-8;
		if (!bHas) return (Current >= 0 && Current < NumDirs) ? Current : Fwd;
		const float A = ErrorDeg(Facing, Heading);
		if (Current >= 0 && Current < NumDirs)
		{
			const float Off = FMath::Abs(Wrap180(A - Current * 45.f));
			if (Off <= OctantHalfDeg + OctantHoldDeg) return Current;
		}
		// The nearest centre by |angle|; a line exactly between two goes to
		// the one nearer Fwd (the floor).
		const float N = FMath::Abs(A) / 45.f;
		const float Floor = std::floor(N);
		const int K = static_cast<int>(N - Floor <= 0.5f ? Floor : Floor + 1.f);
		return A >= 0.f ? K : (NumDirs - K) % NumDirs;
	}

	// --------------------------------------------------- free, or fighting
	/** The free/fight test, held: NearestCm is the flat distance to his
	    nearest living opponent (anything huge for none), bWasFree what he
	    was last frame. Free once no one is within FreeBeyondCm; fighting
	    again once someone is inside FreeBeyondCm - FreeBandCm. */
	inline bool FreeHeld(float NearestCm, bool bWasFree)
	{
		return bWasFree ? NearestCm >= FreeBeyondCm - FreeBandCm : NearestCm > FreeBeyondCm;
	}

	/** Degrees a second his facing may turn toward his heading while free. */
	inline float FreeTurnRate(float Speed, float RunSpeed)
	{
		if (RunSpeed <= 1.f) return TurnRateWalk;
		const float Walk = WalkShare * RunSpeed;
		const float T = FMath::Clamp((Speed - Walk) / (RunSpeed - Walk), 0.f, 1.f);
		return TurnRateWalk + (TurnRateRun - TurnRateWalk) * T;
	}

	/** The turn on the spot for a wish ErrorDeg off his facing, standing and
	    pushed: none up to TurnAboveDeg, a quarter turn to that side up to
	    BackAboveDeg, Turn_180 past it. */
	inline ETurn TurnOnSpot(float Error)
	{
		const float A = FMath::Abs(Error);
		if (A <= TurnAboveDeg) return ETurn::None;
		if (A > BackAboveDeg) return ETurn::Back180;
		return Error > 0.f ? ETurn::L90 : ETurn::R90;
	}

	/** A reversal at a run: the wish past PivotAboveDeg off his facing at
	    over PivotShare of his run speed. */
	inline bool Pivots(float Error, float Speed, float RunSpeed)
	{
		return FMath::Abs(Error) > PivotAboveDeg && RunSpeed > 0.f && Speed > PivotShare * RunSpeed;
	}

	/** One step of a facing toward a wanted yaw, at most MaxStepDeg, the
	    short way round, never past it. Returns the new yaw, (-180, 180]. */
	inline float StepYaw(float Yaw, float WantYaw, float MaxStepDeg)
	{
		const float Gap = Wrap180(WantYaw - Yaw);
		const float Step = FMath::Max(0.f, MaxStepDeg);
		return Wrap180(FMath::Abs(Gap) <= Step ? WantYaw : Yaw + (Gap > 0.f ? Step : -Step));
	}

	// ------------------------------------------------------- one free frame
	/** A fighter's turn in progress. AFighterBase keeps one and ticks it. */
	struct FTurnState
	{
		ETurn Turn = ETurn::None;
		float Left = 0.f;       // seconds of it still to hold
		int Serial = 0;         // +1 per turn started, so a turn after a turn restarts its clip
	};

	/** The clock, every frame whatever he does: a turn ends when its time
	    is up. */
	inline void TickTurn(FTurnState& S, float Dt)
	{
		if (S.Turn == ETurn::None) return;
		S.Left -= Dt;
		if (S.Left <= 1e-4f) { S.Turn = ETurn::None; S.Left = 0.f; }
	}

	/** A strike, a blow, a fall or a dash takes over from a turn. */
	inline void CancelTurn(FTurnState& S)
	{
		S.Turn = ETurn::None;
		S.Left = 0.f;
	}

	struct FFreeIn
	{
		float Dt = 0.f;
		float FacingYaw = 0.f;    // degrees, where he faces now
		FVector Wish;             // flat, where he asks to go (any length)
		bool bPushed = false;     // the wish counts (Saud: the stick past PushedSq)
		float Speed = 0.f;        // his flat speed now, cm/s
		float RunSpeed = 0.f;     // his full speed now, cm/s
	};

	struct FFreeOut
	{
		float FacingYaw = 0.f;    // where he faces after this frame
		float MoveShare = 1.f;    // share of his movement to apply: 0 while a turn holds it
		bool bStarted = false;    // a turn began this frame (the facing snapped to the wish)
	};

	/**
	 * One frame of a free man's facing: hold through a turn in progress;
	 * standing and pushed past TurnAboveDeg, a turn on the spot (the facing
	 * snaps to the wish, the clip carries the body round, movement held for
	 * TurnSeconds); moving, a reversal past PivotAboveDeg over PivotShare of
	 * his run is a Pivot_180 (the same, his speed brought to nothing through
	 * it); otherwise the facing steps toward the wish at FreeTurnRate.
	 */
	inline FFreeOut StepFree(FTurnState& S, const FFreeIn& In)
	{
		FFreeOut Out;
		Out.FacingYaw = Wrap180(In.FacingYaw);
		if (S.Turn != ETurn::None)
		{
			Out.MoveShare = 0.f;
			return Out;
		}
		if (!In.bPushed || (In.Wish.X * In.Wish.X + In.Wish.Y * In.Wish.Y) < 1e-8)
		{
			return Out;
		}
		const float Want = YawOf(In.Wish);
		const float Error = Wrap180(Want - Out.FacingYaw);
		ETurn Start = ETurn::None;
		if (In.Speed < StandingCm)
		{
			Start = TurnOnSpot(Error);
		}
		else if (Pivots(Error, In.Speed, In.RunSpeed))
		{
			Start = ETurn::Pivot180;
		}
		if (Start != ETurn::None)
		{
			S.Turn = Start;
			S.Left = TurnSeconds(Start);
			++S.Serial;
			Out.FacingYaw = Wrap180(Want);
			Out.MoveShare = 0.f;
			Out.bStarted = true;
			return Out;
		}
		Out.FacingYaw = StepYaw(Out.FacingYaw, Want, FreeTurnRate(In.Speed, In.RunSpeed) * In.Dt);
		return Out;
	}
}
