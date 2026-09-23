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
		Block, HitLight, HitHeavy, Down, GetUp, Attack
	};

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
		default:               return "";
		}
	}

	inline bool Loops(EClip C)
	{
		return C == EClip::Guard || C == EClip::Block
			|| C == EClip::WalkFwd || C == EClip::WalkBack || C == EClip::WalkLeft || C == EClip::WalkRight;
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
		float GettingUp = 0.f;         // seconds left of the get-up
		float Speed = 0.f;             // cm/s on the ground
		FVector Facing = FVector(1.f, 0.f, 0.f);
		FVector Heading = FVector(1.f, 0.f, 0.f);
	};

	/** EFighterState's order, mirrored: Idle, Walk, Attack, Hit, Block, Dash,
	    Down, Dead. The harness checks the numbers against this list. */
	enum : int { SIdle = 0, SWalk, SAttack, SHit, SBlock, SDash, SDown, SDead };

	/** Below this a fighter is standing, whatever the state says: the
	    capsule's own drift under a guard is not a step. */
	constexpr float WalkThreshold = 40.f;

	inline EClip Pick(const FMotionInput& In)
	{
		switch (In.State)
		{
		case SAttack: return EClip::Attack;
		case SHit:    return In.bLastHitHeavy ? EClip::HitHeavy : EClip::HitLight;
		case SDown:
		case SDead:   return EClip::Down;          // death reuses Down; the last frame holds
		case SDash:
		{
			const int Q = Quadrant(In.Facing, In.Heading);
			return Q == 0 ? EClip::DashFwd : Q == 1 ? EClip::DashBack : Q == 2 ? EClip::DashLeft : EClip::DashRight;
		}
		default: break;
		}
		if (In.GettingUp > 0.f) return EClip::GetUp;
		if (In.bBlocking || In.State == SBlock) return EClip::Block;
		if (In.Speed >= WalkThreshold)
		{
			const int Q = Quadrant(In.Facing, In.Heading);
			return Q == 0 ? EClip::WalkFwd : Q == 1 ? EClip::WalkBack : Q == 2 ? EClip::WalkLeft : EClip::WalkRight;
		}
		return EClip::Guard;
	}

	/** Seconds the get-up runs: A_Saud_GetUp.fbx is 0.60 s, and so is the
	    invulnerability AFighterBase gives on getting up. */
	constexpr float GetUpSeconds = 0.60f;
}
