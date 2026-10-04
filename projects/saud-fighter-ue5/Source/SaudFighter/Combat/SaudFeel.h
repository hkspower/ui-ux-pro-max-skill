#pragma once

/**
 * How a blow feels, and which clip a fighter plays -- with no engine in it.
 *
 * Until 2026-09-23 a clean hit in this build did three things: a sound, a
 * push, a stun. The freeze frame and the camera shake existed, but only in
 * FSaudCueParameters on the ability path, and nothing fires a blow down that
 * path ("Known, not fixed": strikes go through AFighterBase::StartAttack).
 * So a punch landed with no weight at all. And the twenty-one Saud clips and
 * seventeen boss clips had never been played by anything.
 *
 * The browser build is the source of every number here, exactly as it is of
 * every other number in the project. Its hit feel lives in applyHit()
 * (saud-fighter/index.html:3362-3440), not in the assets folder, so the numbers
 * are quoted with their lines rather than exported:
 *
 *   clean hit   hitstop 0.040 / 0.075 s (light / heavy)       :3417
 *               shake 7 / 13 px, fading at 46 px/s             :3416, :802
 *               camera punch-in 0.45 / 1.0, fading at 3.4/s    :3418, :748
 *               the victim flashes white for 0.09 s            :3402
 *               buzz 24 / 48 ms when the player is hit,
 *                    10 / 20 ms when the player lands it       :3415
 *   knockdown   shake 16                                       :3436
 *   blocked     shake 5                                        :3399
 *   parried     hitstop 0.09, shake 12, buzz 30 ms             :3376-3377
 *
 * A browser shake is pixels on a 720-pixel-tall canvas. Here it is the same
 * share of the picture, turned into degrees of the camera's own vertical
 * field of view -- 13 px is 1.8 % of the frame whichever way it is drawn.
 * A browser punch-in scales the frame by 1 + ease(k) * 0.045 (:759); here
 * the field of view narrows by the same factor.
 *
 * Header of free functions and plain structs, like SaudArena.h, so
 * Tools/harness builds it with g++ and checks it.
 */

#if defined(SAUD_HARNESS)
	#include "HarnessTypes.h"
#else
	#include "CoreMinimal.h"
#endif

#include <cmath>
#include "SaudSteer.h"

namespace SaudFeel
{
	// ------------------------------------------------ the browser's numbers
	constexpr float HitStopLight = 0.040f;
	constexpr float HitStopHeavy = 0.075f;
	constexpr float HitStopParry = 0.090f;

	constexpr float ShakeLight = 7.f;          // canvas pixels
	constexpr float ShakeHeavy = 13.f;
	constexpr float ShakeKnockdown = 16.f;
	constexpr float ShakeBlock = 5.f;
	constexpr float ShakeParry = 12.f;
	constexpr float ShakeDecay = 46.f;         // pixels a second
	constexpr float CanvasHeight = 720.f;      // the browser's H

	constexpr float PunchLight = 0.45f;
	constexpr float PunchHeavy = 1.0f;
	constexpr float PunchDecay = 3.4f;         // a second
	constexpr float PunchZoom = 0.045f;        // the frame's scale at a full punch

	constexpr float FlashSeconds = 0.09f;

	constexpr float BuzzHurtLight = 0.024f;    // seconds: the player took it
	constexpr float BuzzHurtHeavy = 0.048f;
	constexpr float BuzzLandLight = 0.010f;    // the player gave it
	constexpr float BuzzLandHeavy = 0.020f;
	constexpr float BuzzParry = 0.030f;
	/** A phone's vibrator starts in a millisecond; a pad's rumble motor takes
	    tens of them to spin up, and a 10 ms pulse is not felt at all. Nothing
	    shorter than this is sent to the pad; the browser's lengths still set
	    which blows buzz longer than which. */
	constexpr float BuzzFloor = 0.060f;

	/** What one blow asks for. Everything is a peak: the state below keeps
	    the larger of what it has and what arrives, as the browser does with
	    Math.max, so a light jab never cuts a heavy blow's freeze short. */
	struct FBlowFeel
	{
		float HitStop = 0.f;       // seconds of frozen time
		float ShakePx = 0.f;       // canvas pixels
		float Punch = 0.f;         // 0..1
		float Flash = 0.f;         // seconds the victim flashes
		float Buzz = 0.f;          // seconds of rumble, 0 for none
		float BuzzStrength = 0.f;  // 0..1
	};

	/** applyHit(), outcome by outcome. `VictimIsPlayer` / `AttackerIsPlayer`
	    decide the buzz: the browser buzzes on a hit either way, harder when it
	    is the player who is hit. */
	inline FBlowFeel ForBlow(bool bHeavy, bool bBlocked, bool bParried, bool bKnockdown,
	                         bool bVictimIsPlayer, bool bAttackerIsPlayer)
	{
		FBlowFeel F;
		if (bParried)
		{
			F.HitStop = HitStopParry;
			F.ShakePx = ShakeParry;
			F.Buzz = BuzzParry;
			F.BuzzStrength = 0.7f;
			return F;
		}
		if (bBlocked)
		{
			F.ShakePx = ShakeBlock;
			return F;
		}
		F.HitStop = bHeavy ? HitStopHeavy : HitStopLight;
		F.ShakePx = bHeavy ? ShakeHeavy : ShakeLight;
		F.Punch = bHeavy ? PunchHeavy : PunchLight;
		F.Flash = FlashSeconds;
		if (bKnockdown)
		{
			F.ShakePx = FMath::Max(F.ShakePx, ShakeKnockdown);
		}
		if (bVictimIsPlayer)
		{
			F.Buzz = bHeavy ? BuzzHurtHeavy : BuzzHurtLight;
			F.BuzzStrength = bHeavy ? 1.0f : 0.6f;
		}
		else if (bAttackerIsPlayer)
		{
			F.Buzz = bHeavy ? BuzzLandHeavy : BuzzLandLight;
			F.BuzzStrength = bHeavy ? 0.5f : 0.3f;
		}
		return F;
	}

	/** Seconds of rumble a pad is actually sent: the browser's length, never
	    under the floor a motor needs, and nothing when there was none. */
	inline float PadBuzzSeconds(float BrowserSeconds)
	{
		return BrowserSeconds > 0.f ? FMath::Max(BrowserSeconds, BuzzFloor) : 0.f;
	}

	/** The camera's feel between frames: hitstop, shake and punch-in, each
	    kept at the larger of what it had and what arrives, each running out
	    in REAL time -- the freeze stops the game's clock, not this one. */
	struct FState
	{
		float HitStop = 0.f;
		float ShakePx = 0.f;
		float Punch = 0.f;

		void Add(const FBlowFeel& F)
		{
			HitStop = FMath::Max(HitStop, F.HitStop);
			ShakePx = FMath::Max(ShakePx, F.ShakePx);
			Punch = FMath::Max(Punch, F.Punch);
		}

		void Tick(float RealSeconds)
		{
			HitStop = FMath::Max(0.f, HitStop - RealSeconds);
			ShakePx = FMath::Max(0.f, ShakePx - ShakeDecay * RealSeconds);
			Punch = FMath::Max(0.f, Punch - PunchDecay * RealSeconds);
		}

		bool Frozen() const { return HitStop > 0.f; }
	};

	/** A shake's size in degrees of this camera's vertical field of view:
	    the same share of the picture it is of the browser's 720 pixels. */
	inline float ShakeDegrees(float ShakePx, float VerticalFovDegrees)
	{
		return ShakePx / CanvasHeight * VerticalFovDegrees;
	}

	/** The browser's shake is a fresh random offset every frame (±shake/2 in
	    x and y). A random offset per frame at 120 Hz is noise, not a jolt, so
	    this is two incommensurate sines per axis instead -- the same size,
	    always inside ±1, and repeatable. Returns pitch and yaw in -1..1. */
	inline void ShakeWave(float Time, float& OutPitch, float& OutYaw)
	{
		OutPitch = 0.5f * (FMath::Sin(Time * 71.f) + FMath::Sin(Time * 113.f + 1.7f));
		OutYaw   = 0.5f * (FMath::Sin(Time * 83.f + 0.6f) + FMath::Sin(Time * 127.f + 2.9f));
	}

	/** The browser's ease(t): quadratic in, quadratic out. */
	inline float Ease(float T)
	{
		T = FMath::Clamp(T, 0.f, 1.f);
		return T < 0.5f ? 2.f * T * T : 1.f - (-2.f * T + 2.f) * (-2.f * T + 2.f) * 0.5f;
	}

	/** A camera's field of view during a punch-in: narrowed by the factor
	    the browser scales its frame by (1 + ease(k) * 0.045). */
	inline float PunchFov(float BaseFov, float Punch)
	{
		return BaseFov / (1.f + Ease(Punch) * PunchZoom);
	}

	/** How bright the victim's flash is at a moment, 1 at the blow and 0 when
	    it has run out. The browser holds pure white for its whole 0.09 s; a
	    lit 3D body snapping to white and back reads as a rendering fault, so
	    it holds for the first half and falls away over the second. */
	inline float FlashAmount(float Remaining)
	{
		if (Remaining <= 0.f) return 0.f;
		const float T = Remaining / FlashSeconds;       // 1 at the blow
		return T >= 0.5f ? 1.f : T * 2.f;
	}

	// ----------------------------------------------------- which clip plays

	enum class EClip : unsigned char
	{
		Guard, WalkFwd, WalkBack, WalkLeft, WalkRight,
		DashFwd, DashBack, DashLeft, DashRight,
		Block, HitLight, HitHeavy, Down, GetUp, Attack,
		// by the blow (2026-09-27): what it hit and how, not only how hard
		HitHeadStraightLight, HitHeadStraight, HitHeadSide, HitBodyFront, HitBodySide,
		DownSide, DownFold,
		// the end of a fight (2026-09-28)
		Death, Victory,
		// Saud's free walk and run (2026-10-03): motion capture, picked by speed
		GaitWalkSlow, GaitWalk, GaitWalkBrisk, GaitJog, GaitRun,
		// 360 locomotion (2026-10-04): the walk tier's diagonals (its four
		// straight ways are WalkFwd..WalkRight above), the run tier's eight,
		// and the turns the free steer starts (SaudSteer::ETurn)
		WalkFwdLeft, WalkBackLeft, WalkBackRight, WalkFwdRight,
		RunFwd, RunFwdLeft, RunLeft, RunBackLeft, RunBack, RunBackRight, RunRight, RunFwdRight,
		TurnL90, TurnR90, Turn180, Pivot180
	};

	// ------------------------------------------------ the eight ways, two tiers
	// The directions are SaudSteer::EDir's order -- Fwd, FwdLeft, Left,
	// BackLeft, Back, BackRight, Right, FwdRight; + = his left -- each the
	// octant centred on index x 45 degrees.

	/** The walk tier's clip for a direction (struck at SaudSteer::WalkShare
	    of his speed), and the run tier's (his full speed). */
	inline EClip WalkClip(int Dir)
	{
		constexpr EClip T[8] = { EClip::WalkFwd, EClip::WalkFwdLeft, EClip::WalkLeft, EClip::WalkBackLeft,
		                         EClip::WalkBack, EClip::WalkBackRight, EClip::WalkRight, EClip::WalkFwdRight };
		return T[((Dir % 8) + 8) % 8];
	}
	inline EClip RunClip(int Dir)
	{
		constexpr EClip T[8] = { EClip::RunFwd, EClip::RunFwdLeft, EClip::RunLeft, EClip::RunBackLeft,
		                         EClip::RunBack, EClip::RunBackRight, EClip::RunRight, EClip::RunFwdRight };
		return T[((Dir % 8) + 8) % 8];
	}

	/** A walk or run clip's direction, 0..7; -1 for anything else. */
	inline int DirOf(EClip C)
	{
		for (int D = 0; D < 8; ++D)
		{
			if (WalkClip(D) == C || RunClip(D) == C) return D;
		}
		return -1;
	}

	/** 0 the walk tier, 1 the run tier, -1 neither. */
	inline int TierOf(EClip C)
	{
		for (int D = 0; D < 8; ++D)
		{
			if (WalkClip(D) == C) return 0;
			if (RunClip(D) == C) return 1;
		}
		return -1;
	}

	inline bool IsTurnClip(EClip C)
	{
		return C == EClip::TurnL90 || C == EClip::TurnR90 || C == EClip::Turn180 || C == EClip::Pivot180;
	}

	/** The clip that carries a turn the steer started. */
	inline EClip TurnClip(SaudSteer::ETurn T)
	{
		switch (T)
		{
		case SaudSteer::ETurn::L90:      return EClip::TurnL90;
		case SaudSteer::ETurn::R90:      return EClip::TurnR90;
		case SaudSteer::ETurn::Back180:  return EClip::Turn180;
		case SaudSteer::ETurn::Pivot180: return EClip::Pivot180;
		default:                         return EClip::Guard;
		}
	}

	/** The clip's name in Content/Animation: A_<Set>_<this>. Attack is the
	    attack row's own name and has none here. */
	inline const char* ClipSuffix(EClip C)
	{
		switch (C)
		{
		case EClip::Guard:     return "Guard";
		case EClip::WalkFwd:   return "Walk_Fwd";
		case EClip::WalkBack:  return "Walk_Back";
		case EClip::WalkLeft:  return "Walk_Left";
		case EClip::WalkRight: return "Walk_Right";
		case EClip::DashFwd:   return "Dash_Fwd";
		case EClip::DashBack:  return "Dash_Back";
		case EClip::DashLeft:  return "Dash_Left";
		case EClip::DashRight: return "Dash_Right";
		case EClip::Block:     return "Block";
		case EClip::HitLight:  return "Hit_Light";
		case EClip::HitHeavy:  return "Hit_Heavy";
		case EClip::Down:      return "Down";
		case EClip::GetUp:     return "GetUp";
		case EClip::HitHeadStraightLight: return "Hit_Head_Straight_Light";
		case EClip::HitHeadStraight:      return "Hit_Head_Straight";
		case EClip::HitHeadSide:          return "Hit_Head_Side";
		case EClip::HitBodyFront:         return "Hit_Body_Front";
		case EClip::HitBodySide:          return "Hit_Body_Side";
		case EClip::DownSide:             return "Down_Side";
		case EClip::DownFold:             return "Down_Fold";
		case EClip::Death:                return "Death";
		case EClip::Victory:              return "Victory";
		case EClip::GaitWalkSlow:         return "Mocap_Walk_Slow";
		case EClip::GaitWalk:             return "Mocap_Walk";
		case EClip::GaitWalkBrisk:        return "Mocap_Walk_Brisk";
		case EClip::GaitJog:              return "Mocap_Jog";
		case EClip::GaitRun:              return "Mocap_Run";
		// the file names of the 360 spec (A_<Set>_<this>.fbx)
		case EClip::WalkFwdLeft:          return "Walk_FwdLeft";
		case EClip::WalkBackLeft:         return "Walk_BackLeft";
		case EClip::WalkBackRight:        return "Walk_BackRight";
		case EClip::WalkFwdRight:         return "Walk_FwdRight";
		case EClip::RunFwd:               return "Run_Fwd";
		case EClip::RunFwdLeft:           return "Run_FwdLeft";
		case EClip::RunLeft:              return "Run_Left";
		case EClip::RunBackLeft:          return "Run_BackLeft";
		case EClip::RunBack:              return "Run_Back";
		case EClip::RunBackRight:         return "Run_BackRight";
		case EClip::RunRight:             return "Run_Right";
		case EClip::RunFwdRight:          return "Run_FwdRight";
		case EClip::TurnL90:              return "Turn_L90";
		case EClip::TurnR90:              return "Turn_R90";
		case EClip::Turn180:              return "Turn_180";
		case EClip::Pivot180:             return "Pivot_180";
		default:               return "";
		}
	}

	inline bool IsGait(EClip C)
	{
		return C == EClip::GaitWalkSlow || C == EClip::GaitWalk || C == EClip::GaitWalkBrisk
			|| C == EClip::GaitJog || C == EClip::GaitRun;
	}

	inline bool Loops(EClip C)
	{
		return C == EClip::Guard || C == EClip::Block
			|| C == EClip::WalkFwd || C == EClip::WalkBack || C == EClip::WalkLeft || C == EClip::WalkRight
			|| TierOf(C) >= 0 || IsGait(C);
	}

	/** Of a diagonal's two neighbours (45 degrees either side), the one
	    nearer the heading AngleDeg (off the facing, + his left); a heading on
	    the diagonal itself goes to the one nearer Fwd -- forward over a side,
	    a side over back, as SaudFeel::Quadrant breaks its ties. */
	inline int NearerNeighbour(int Diag, float AngleDeg)
	{
		const int A = (Diag + 7) % 8, B = (Diag + 1) % 8;
		auto Off = [AngleDeg](int D) { return FMath::Abs(SaudSteer::Wrap180(AngleDeg - D * 45.f)); };
		auto FromFwd = [](int D) { return FMath::Abs(SaudSteer::Wrap180(D * 45.f)); };
		const float OA = Off(A), OB = Off(B);
		if (OA < OB - 1e-3f) return A;
		if (OB < OA - 1e-3f) return B;
		return FromFwd(A) <= FromFwd(B) ? A : B;
	}

	/** The clip that stands in for one a motion set does not have: a
	    reaction by the blow falls back to the old light / heavy hit, a fall
	    by the blow to Down. Anything else is its own. */
	inline EClip Fallback(EClip C)
	{
		switch (C)
		{
		case EClip::HitHeadStraightLight: return EClip::HitLight;
		case EClip::HitHeadStraight:
		case EClip::HitHeadSide:
		case EClip::HitBodyFront:
		case EClip::HitBodySide:          return EClip::HitHeavy;
		case EClip::DownSide:
		case EClip::DownFold:
		case EClip::Death:                return EClip::Down;
		case EClip::Victory:              return EClip::Guard;
		// motion capture not imported yet: the guard's own step forward
		case EClip::GaitWalkSlow: case EClip::GaitWalk: case EClip::GaitWalkBrisk:
		case EClip::GaitJog: case EClip::GaitRun: return EClip::WalkFwd;
		// the 360 clips (2026-10-04): a turn stands in his guard; a run
		// clip is its walk; a diagonal its neighbour nearer Fwd (the heading's
		// own nearer neighbour is FallbackChain's)
		case EClip::TurnL90: case EClip::TurnR90: case EClip::Turn180: case EClip::Pivot180: return EClip::Guard;
		default:
			if (TierOf(C) == 1) return WalkClip(DirOf(C));
			if (TierOf(C) == 0 && DirOf(C) % 2) return WalkClip(NearerNeighbour(DirOf(C), DirOf(C) * 45.f));
			return C;
		}
	}

	/** What to look for, in order, when a set may not have a clip: the clip
	    itself first. A diagonal a set lacks falls back to the nearer of its
	    two neighbours (by the heading's AngleDeg), then the other; a run
	    clip to its walk; a turn or a pivot to the Guard (the facing has
	    snapped, the hips' lag is cleared: his guard at the new facing). The
	    motion component takes the first a set has. */
	struct FClipChain
	{
		EClip Clip[8];
		int Num = 0;
		void Add(EClip C)
		{
			for (int I = 0; I < Num; ++I) if (Clip[I] == C) return;
			if (Num < 8) Clip[Num++] = C;
		}
	};

	inline FClipChain FallbackChain(EClip C, float AngleDeg)
	{
		FClipChain Out;
		Out.Add(C);
		const int Dir = DirOf(C), Tier = TierOf(C);
		if (Dir >= 0)
		{
			auto Ways = [&](EClip (*Of)(int))
			{
				Out.Add(Of(Dir));
				if (Dir % 2)
				{
					const int Near = NearerNeighbour(Dir, AngleDeg);
					const int Far = Near == (Dir + 7) % 8 ? (Dir + 1) % 8 : (Dir + 7) % 8;
					Out.Add(Of(Near));
					Out.Add(Of(Far));
				}
			};
			if (Tier == 1) Ways(RunClip);
			Ways(WalkClip);
			return Out;
		}
		if (IsTurnClip(C)) { Out.Add(EClip::Guard); return Out; }
		const EClip F = Fallback(C);
		Out.Add(F);
		Out.Add(Fallback(F));
		return Out;
	}

	/** What a blow did, read off the attack row that landed it -- the same
	    table build_motion.py's motion_hits.BLOW is: a jab snaps the head
	    back a little, a cross all the way, a hook turns it on the jaw, a
	    kick takes the ribs from the side, a knee folds him, and the
	    finisher spins him down. A row this does not know is None, which
	    plays the old light / heavy hit. */
	enum class EBlow : unsigned char { None, HeadStraightLight, HeadStraight, HeadSide, BodyFront, BodySide, Spin };

	inline EBlow BlowOf(const char* Row)
	{
		if (!Row) return EBlow::None;
		auto Is = [Row](const char* N) { const char* A = Row; while (*A && *N && *A == *N) { ++A; ++N; } return *A == 0 && *N == 0; };
		if (Is("Jab"))     return EBlow::HeadStraightLight;
		if (Is("Cross"))   return EBlow::HeadStraight;
		if (Is("Hook"))    return EBlow::HeadSide;
		if (Is("Kick"))    return EBlow::BodySide;
		if (Is("Knee"))    return EBlow::BodyFront;
		if (Is("Special")) return EBlow::Spin;
		return EBlow::None;
	}

	/** Which way a heading is, against where the fighter faces: the four
	    Walk and Dash clips exist because a heading is not a facing here --
	    the stick decides one and the opponent the other. Forward wins a tie
	    with the side, and a side wins a tie with back. */
	inline int Quadrant(const FVector& Facing, const FVector& Heading)
	{
		const float Fwd = Facing.X * Heading.X + Facing.Y * Heading.Y;
		const float Side = Facing.X * Heading.Y - Facing.Y * Heading.X;   // + is the fighter's left
		if (Fwd >= FMath::Abs(Side)) return 0;               // forward
		if (-Fwd > FMath::Abs(Side)) return 1;               // back
		return Side > 0.f ? 2 : 3;                           // left / right
	}

	/** The fighter's state as the motion driver sees it. The states are
	    AFighterBase's; GetUp is the clip the engine never names -- the 0.6 s
	    of "brief mercy on getting up" after Down runs out. */
	struct FMotionInput
	{
		int State = 0;                 // EFighterState as an int, so no engine header is needed
		bool bBlocking = false;
		bool bLastHitHeavy = false;
		EBlow LastBlow = EBlow::None;  // the blow that put him in Hit or Down
		bool bDying = false;           // no health left: this Down is the last
		float Victory = 0.f;           // seconds left of the win
		float GettingUp = 0.f;         // seconds left of the get-up
		float Speed = 0.f;             // cm/s on the ground
		FVector Facing = FVector(1.f, 0.f, 0.f);
		FVector Heading = FVector(1.f, 0.f, 0.f);
		/** No one to fight (AFighterBase::IsMovingFree, held: no living
		    opponent within FreeBeyondCm): he turns to where he goes and walks
		    and runs as a man does, not on his guard. Every fighter's own. */
		bool bFree = false;
		/** His set has Saud's motion-capture gaits (Saud's set): free and
		    going about where he faces, he plays those rather than Run_Fwd /
		    Walk_Fwd. */
		bool bGaits = false;
		/** His full speed now, cm/s (AFighterBase::GetRunSpeed): the tiers
		    are struck at it and at SaudSteer::WalkShare of it. */
		float RunSpeed = 341.f;
		/** The turn clip playing (FTurnHold): it plays to its end unless an
		    attack, a hit, a fall or a dash takes over. */
		SaudSteer::ETurn Turn = SaudSteer::ETurn::None;
		/** The clip showing, so a gait, a tier and an octant are held
		    through a small change of speed or heading. */
		EClip Current = EClip::Guard;
	};

	// ------------------------------------------- Saud's free walk and run
	// Asked as "improve walk and run for saud", settled 2026-10-01 as a real
	// walk and a run, picked by speed; built 2026-10-03 from the motion
	// capture (Tools/blender/mocap.py, Content/Animation/Saud/
	// DT_SaudMocap.csv, which tests/feel.cpp holds these speeds to). Each
	// loop starts as the left foot strikes, so one gait crossfades into the
	// next foot on foot (CutBetween matches the phase between steps), and
	// the runtime plays each at his ground speed over its own stride
	// (SaudIK::StrideRateMeasured).
	struct FGait { EClip Clip; float SpeedCm; };
	constexpr int NumGaits = 5;
	constexpr FGait Gaits[NumGaits] = {
		{EClip::GaitWalkSlow, 100.3f}, {EClip::GaitWalk, 148.5f}, {EClip::GaitWalkBrisk, 176.0f},
		{EClip::GaitJog, 279.9f}, {EClip::GaitRun, 320.0f},
	};
	/** No living man nearer than this, and Saud walks free; nearer, he is on
	    his guard and steps as a fighter (the camera frames a fight at 15 m:
	    this is inside it, so the guard is up before the men are close).
	    Since 2026-10-04 the test is AFighterBase's (SaudSteer::FreeHeld, with
	    its band); this is its distance, kept under the old name. */
	constexpr float FreeBeyondCm = SaudSteer::FreeBeyondCm;
	/** A gait is kept while the speed is within this share past the line to
	    its neighbour, so a stick held near a line does not flicker between them. */
	constexpr float GaitHysteresis = 0.08f;

	/** The gait for a speed: the one whose own speed is nearest by ratio (the
	    line between two is their geometric mean), the current one kept
	    while within GaitHysteresis of its band. */
	inline EClip PickGait(float Speed, EClip Current)
	{
		auto Line = [](int I) { return std::sqrt(Gaits[I].SpeedCm * Gaits[I + 1].SpeedCm); };
		for (int I = 0; I < NumGaits; ++I)
		{
			if (Gaits[I].Clip != Current) continue;
			const float Lo = I == 0 ? 0.f : Line(I - 1) * (1.f - GaitHysteresis);
			const float Hi = I == NumGaits - 1 ? 1e9f : Line(I) * (1.f + GaitHysteresis);
			if (Speed >= Lo && Speed <= Hi) return Current;
		}
		int Pick = NumGaits - 1;
		for (int I = 0; I < NumGaits - 1; ++I)
		{
			if (Speed < Line(I)) { Pick = I; break; }
		}
		return Gaits[Pick].Clip;
	}

	/** EFighterState's order, mirrored: Idle, Walk, Attack, Hit, Block, Dash,
	    Down, Dead. The harness checks the numbers against this list. */
	enum : int { SIdle = 0, SWalk, SAttack, SHit, SBlock, SDash, SDown, SDead };

	/** Below this a fighter is standing, whatever the state says: the
	    capsule's own drift under a guard is not a step. */
	constexpr float WalkThreshold = 40.f;

	// --------------------------------------------- 360: the tier, the way
	/** The walk tier is struck at SaudSteer::WalkShare of his run speed and
	    the run tier at his run speed; the line between them is their
	    geometric mean (as the gaits' lines are), and the tier showing is
	    kept until the speed is this share past it, so a stick held on the
	    line does not flicker between the two. */
	constexpr float TierHysteresis = 0.08f;

	/** The line between the walk tier and the run tier, cm/s. */
	inline float TierLine(float RunSpeed)
	{
		return std::sqrt(SaudSteer::WalkShare * RunSpeed * RunSpeed);
	}

	/** 0 the walk tier, 1 the run tier, for a speed; Current (-1 none) kept
	    within TierHysteresis of the line. */
	inline int PickTier(float Speed, float RunSpeed, int Current)
	{
		if (RunSpeed <= 1.f) return 1;
		const float Line = TierLine(RunSpeed);
		if (Current == 0 && Speed <= Line * (1.f + TierHysteresis)) return 0;
		if (Current == 1 && Speed >= Line * (1.f - TierHysteresis)) return 1;
		return Speed < Line ? 0 : 1;
	}

	/** Free, he plays his straight-ahead clip (Saud's gaits; anyone else's
	    Run_Fwd / Walk_Fwd) while his heading is within this of his drawn
	    facing, and the strafe of the angle past it; the straight-ahead clip
	    showing is kept to AheadHoldDeg further. */
	constexpr float AheadDeg = 30.f;
	constexpr float AheadHoldDeg = 5.f;

	/** Whether a free man's heading is "straight ahead" of his drawn body. */
	inline bool FreeAhead(const FVector& Facing, const FVector& Heading, EClip Current)
	{
		const float Off = FMath::Abs(SaudSteer::ErrorDeg(Facing, Heading));
		const bool bShowing = IsGait(Current) || Current == EClip::WalkFwd || Current == EClip::RunFwd;
		return Off <= AheadDeg + (bShowing ? AheadHoldDeg : 0.f);
	}

	/** The turn clip's own clock, on the motion component: started when the
	    fighter's turn serial moves with a turn on (GetLocoTurn,
	    GetLocoTurnSerial), held for SaudSteer::TurnSeconds -- the clip plays
	    to its end -- unless Stop() (an attack, a hit, a fall or a dash took
	    over). */
	struct FTurnHold
	{
		SaudSteer::ETurn Turn = SaudSteer::ETurn::None;
		float Left = 0.f;
		int Serial = 0;
		bool bSeen = false;

		/** One frame; true when a turn started this frame (its clip plays
		    from its first frame, even after the same turn). */
		bool Step(SaudSteer::ETurn FighterTurn, int FighterSerial, float Dt)
		{
			if (!bSeen || FighterSerial != Serial)
			{
				bSeen = true;
				Serial = FighterSerial;
				if (FighterTurn != SaudSteer::ETurn::None)
				{
					Turn = FighterTurn;
					Left = SaudSteer::TurnSeconds(Turn);
					return true;
				}
			}
			if (Turn != SaudSteer::ETurn::None)
			{
				Left -= FMath::Max(0.f, Dt);
				if (Left <= 1e-4f) Stop();
			}
			return false;
		}
		void Stop() { Turn = SaudSteer::ETurn::None; Left = 0.f; }
	};

	inline EClip Pick(const FMotionInput& In)
	{
		switch (In.State)
		{
		case SAttack: return EClip::Attack;
		case SHit:
			switch (In.LastBlow)
			{
			case EBlow::HeadStraightLight: return EClip::HitHeadStraightLight;
			case EBlow::HeadStraight:      return EClip::HitHeadStraight;
			case EBlow::HeadSide:          return EClip::HitHeadSide;
			case EBlow::BodyFront:         return EClip::HitBodyFront;
			case EBlow::BodySide:          return EClip::HitBodySide;
			case EBlow::Spin:              return EClip::HitHeadSide;   // a spin that did not put him down
			default: return In.bLastHitHeavy ? EClip::HitHeavy : EClip::HitLight;
			}
		case SDead:   return EClip::Death;    // its last frame holds
		case SDown:
			if (In.bDying) return EClip::Death; // the killing blow's Down is the dying
			return In.LastBlow == EBlow::Spin || In.LastBlow == EBlow::HeadSide ? EClip::DownSide
			     : In.LastBlow == EBlow::BodyFront ? EClip::DownFold : EClip::Down;
		case SDash:
		{
			const int Q = Quadrant(In.Facing, In.Heading);
			return Q == 0 ? EClip::DashFwd : Q == 1 ? EClip::DashBack : Q == 2 ? EClip::DashLeft : EClip::DashRight;
		}
		default: break;
		}
		// a turn the free steer started carries his body round: it plays to
		// its end, and only the four above take over from it
		if (In.Turn != SaudSteer::ETurn::None) return TurnClip(In.Turn);
		if (In.GettingUp > 0.f) return EClip::GetUp;
		// the win, standing: moving or guarding again ends it
		if (In.Victory > 0.f && !In.bBlocking && In.State != SBlock && In.Speed < WalkThreshold) return EClip::Victory;
		if (In.bBlocking || In.State == SBlock) return EClip::Block;
		if (In.Speed >= WalkThreshold)
		{
			const int Tier = PickTier(In.Speed, In.RunSpeed, TierOf(In.Current));
			const bool bAhead = FreeAhead(In.Facing, In.Heading, In.Current);
			if (In.bGaits && bAhead)
			{
				// free: a man walking, at his pace, the way he faces (he turns to
				// where he goes at a rate: SaudSteer::StepFree)
				if (In.bFree) return PickGait(In.Speed, In.Current);
			}
			if (In.bFree && bAhead) return Tier ? EClip::RunFwd : EClip::WalkFwd;
			// fighting (or free but going off his drawn facing): the strafe of
			// the heading's octant against the body as drawn, walk or run
			const int Dir = SaudSteer::Octant(In.Facing, In.Heading, DirOf(In.Current));
			return Tier ? RunClip(Dir) : WalkClip(Dir);
		}
		return EClip::Guard;
	}

	// ----------------------------------------------------- how a clip gives way

	/** What a clip is to the cut into or out of it. */
	enum class EKind : unsigned char { Stand, Step, Dash, Guarded, Strike, Reel, Fall, Rise, Win, Turn };

	inline EKind KindOf(EClip C)
	{
		switch (C)
		{
		case EClip::WalkFwd: case EClip::WalkBack: case EClip::WalkLeft: case EClip::WalkRight: return EKind::Step;
		case EClip::GaitWalkSlow: case EClip::GaitWalk: case EClip::GaitWalkBrisk:
		case EClip::GaitJog: case EClip::GaitRun: return EKind::Step;
		case EClip::DashFwd: case EClip::DashBack: case EClip::DashLeft: case EClip::DashRight: return EKind::Dash;
		case EClip::Block:  return EKind::Guarded;
		case EClip::Attack: return EKind::Strike;
		case EClip::HitLight: case EClip::HitHeavy:
		case EClip::HitHeadStraightLight: case EClip::HitHeadStraight: case EClip::HitHeadSide:
		case EClip::HitBodyFront: case EClip::HitBodySide: return EKind::Reel;
		case EClip::Down: case EClip::DownSide: case EClip::DownFold: case EClip::Death: return EKind::Fall;
		case EClip::GetUp:   return EKind::Rise;
		case EClip::Victory: return EKind::Win;
		case EClip::TurnL90: case EClip::TurnR90: case EClip::Turn180: case EClip::Pivot180: return EKind::Turn;
		default:             return TierOf(C) >= 0 ? EKind::Step : EKind::Stand;
		}
	}

	/** A cut is a crossfade: the new clip's weight on a smooth step over
	    Seconds, the old one still playing under it at its own time.
	    bMatchPhase starts the new loop at the old one's share of its cycle. */
	struct FCut
	{
		float Seconds = 0.f;
		bool bMatchPhase = false;
		/** With bMatchPhase: what to add to the old clip's share of its cycle
		    so the new one comes in on the same foot (LeftStrikeShare). */
		float ShareShift = 0.f;
		/** 0..1, or -1 for none: start the new loop at this share of its
		    cycle, less what the old one-shot still had to play (a pivot's
		    hand-over into his run: PivotRunShare). */
		float StartShare = -1.f;
	};

	/** Where in a step loop's cycle his left foot strikes, as a share: every
	    walk and run clip of the 360 spec, and every gait, lands the left
	    foot on its first frame -- except Run_Left and Run_Right, the old
	    full-speed side steps kept as they were, which land the foot on the
	    side they travel to first: Run_Right its right, so its left comes half
	    a cycle on. A cut that keeps the phase keeps the feet by these. */
	inline float LeftStrikeShare(EClip C)
	{
		return C == EClip::RunRight ? 0.5f : 0.f;
	}

	/** The share of Run_Fwd's cycle a set's Pivot_180 hands over at (its last
	    frame pushes off into that frame of the run), measured from the clips
	    by their builders (2026-10-04): the men's -- Saud, Street, Boss, Saqr,
	    Zayos, and the street rows that play Street's -- frame 13 of 17; the
	    Monkey's 10 of 12; the Gorilla's 15 of 20. */
	inline float PivotRunShare(const char* Set)
	{
		auto Is = [Set](const char* N) { const char* A = Set ? Set : ""; while (*A && *N && *A == *N) { ++A; ++N; } return *A == 0 && *N == 0; };
		if (Is("Monkey"))  return 10.f / 12.f;
		if (Is("Gorilla")) return 15.f / 20.f;
		return 13.f / 17.f;
	}

	/** The clips a pivot hands over into at its run's phase: his straight-
	    ahead loops, every one of which lands the left foot on its first
	    frame (Run_Fwd, Walk_Fwd, the gaits). */
	inline bool TakesPivotPhase(EClip C)
	{
		return C == EClip::RunFwd || C == EClip::WalkFwd || IsGait(C);
	}

	constexpr float CutIntoStrike = 0.05f;   // whole before the Jab's first active frame (0.07 s): the blow lands as thrown
	constexpr float CutIntoReel = 0.03f;     // under the reaction's own 40 ms rise: the jolt is the clip's, not the cut's
	constexpr float CutIntoFall = 0.06f;     // the knockdown's freeze shows the blow; the fall follows it at once
	constexpr float CutIntoDash = 0.04f;     // a sixth of the 0.24 s dash: the push-off is in it
	constexpr float CutIntoBlock = 0.08f;    // the guard is up inside the first half of the 0.20 s parry window
	constexpr float CutIntoRise = 0.10f;     // GetUp begins on Down's last frame; under a quarter of its 0.60 s
	constexpr float CutStep = 0.15f;         // walk to walk: a quarter of the 0.57 s stride, in step
	constexpr float CutSettle = 0.20f;       // anything unhurried: into the guard or a walk, the block lowered, the win
	constexpr float CutIntoTurn = 0.06f;     // a turn's first frame is the body turned back where it stood: in at once

	/** The cut from one clip to the next. What is coming decides: a blow,
	    a reel, a fall, a dash, a block or a rise cut in short; anything
	    else settles. A strike's clip ends exactly when its recovery does,
	    so what follows it blends from its held last frame. */
	inline FCut CutBetween(EClip From, EClip To, bool bRestart)
	{
		const EKind A = KindOf(From), B = KindOf(To);
		FCut C;
		switch (B)
		{
		case EKind::Strike: C.Seconds = CutIntoStrike; return C;
		case EKind::Reel: C.Seconds = CutIntoReel; return C;
		case EKind::Fall: C.Seconds = CutIntoFall; return C;
		case EKind::Dash: C.Seconds = CutIntoDash; return C;
		case EKind::Rise: C.Seconds = CutIntoRise; return C;
		case EKind::Turn: C.Seconds = CutIntoTurn; return C;
		case EKind::Guarded: C.Seconds = CutIntoBlock; C.bMatchPhase = A == EKind::Stand && !bRestart; return C;
		default: break;
		}
		// a pivot pushes off into Run_Fwd's first frame: in as a step
		C.Seconds = (A == EKind::Step || From == EClip::Pivot180) && B == EKind::Step ? CutStep : CutSettle;
		C.bMatchPhase = !bRestart && ((A == EKind::Step && B == EKind::Step) || (A == EKind::Guarded && B == EKind::Stand));
		if (C.bMatchPhase) C.ShareShift = LeftStrikeShare(To) - LeftStrikeShare(From);
		return C;
	}

	/** CutBetween for a man of motion set Set: a pivot handing over into his
	    run starts it at the set's own hand-over share (PivotRunShare). */
	inline FCut CutBetween(EClip From, EClip To, bool bRestart, const char* Set)
	{
		FCut C = CutBetween(From, To, bRestart);
		if (From == EClip::Pivot180 && TakesPivotPhase(To) && !bRestart) C.StartShare = PivotRunShare(Set);
		return C;
	}

	/** A start the fighter's MotionSerial marks -- a second jab, a second
	    hit, a second dash, the win again -- plays its clip from the first
	    frame even when that clip is still fading out. A loop has no first
	    frame to go back to: a walk is never restarted. The picked clip
	    decides, not the asset: a Victory a set does not have falls back to
	    the Guard asset and still plays it once, from its first frame. */
	inline bool Restarts(EClip C, bool bSerialMoved)
	{
		return bSerialMoved && !Loops(C);
	}

	/** Whether the clip showing stays, though the pick has changed: one dash,
	    one clip. The dash's way is picked against the body as drawn, which is
	    still coming round when the dash starts; picked again each frame, the
	    way would cross a quadrant mid-dash and a new dash clip would start
	    over from its first frame. A new dash moves the serial and picks
	    afresh; leaving the dash is another kind and plays. */
	inline bool KeepsClip(EClip Shown, EClip Picked, bool bSerialMoved)
	{
		return !bSerialMoved && KindOf(Shown) == EKind::Dash && KindOf(Picked) == EKind::Dash;
	}

	/** Seconds the get-up runs: A_Saud_GetUp.fbx is 0.60 s, and so is the
	    invulnerability AFighterBase gives on getting up. */
	constexpr float GetUpSeconds = 0.60f;

	/** Seconds the win is held: A_<Set>_Victory is 2.0 s (motion_hits.
	    VICTORY_SECONDS), and the harness holds the clip to this. */
	constexpr float VictorySeconds = 2.0f;

	// ------------------------------------------------------------ the music

	/** A boss's own fight theme, by his DT_Fighters row (2026-10-03, asked
	    as "every boss his own ... music fight"): AL-WAHSH's, AL-SAQR's and
	    ZAYOS's. Any other row has none (nullptr) and a boss wave plays
	    BossMusic. A wave's music starts when it begins and the stage loop
	    comes back when it is cleared (AWaveDirector). The harness holds
	    every boss row in DT_Fighters to a row of DT_Sounds.csv and a file
	    on disk. */
	inline const char* BossTheme(const char* Row)
	{
		if (!Row) return nullptr;
		auto Is = [Row](const char* N) { const char* A = Row; while (*A && *N && *A == *N) { ++A; ++N; } return *A == 0 && *N == 0; };
		if (Is("Boss"))  return "Music_Wahsh";
		if (Is("Saqr"))  return "Music_Saqr";
		if (Is("Zayos")) return "Music_Zayos";
		return nullptr;
	}
	/** A boss with no theme of his own, and the loop a cleared boss wave
	    hands back to. */
	constexpr const char* BossMusic = "Music_Boss";
	constexpr const char* StageMusic = "Music_Stage";
}
