#pragma once

/**
 * Runtime IK, with no engine in it: where a limb goes, given where the clip
 * put it and what the world is doing.
 *
 * Every clip in Content/Animation was posed on a flat floor against nobody.
 * The world is not flat -- the districts are ground discs on a spiral, the
 * island is rock -- and a strike is thrown at a man who is wherever he is,
 * not at the reach the clip was posed to. So, over the played clip, three
 * things are solved each frame (USaudMotionAnimInstance applies them):
 *
 *   feet     each foot the clip has on the floor is put on the ground under
 *            it, and the pelvis drops so the lower foot can reach; the foot
 *            tilts to the slope.
 *   hands    the striking hand (or foot) of an attack is drawn to the
 *            victim's body over the contact frames, so a jab that lands
 *            neither stops short of the man nor passes through him.
 *   head     the head turns to the nearest opponent, within what a neck
 *            does.
 *
 * All of it is FVector arithmetic on positions; turning positions into bone
 * rotations is the engine's part. Header of free functions and plain structs
 * like SaudArena.h and SaudFeel.h, so Tools/harness builds and checks it.
 */

#if defined(SAUD_HARNESS)
	#include "HarnessTypes.h"
#else
	#include "CoreMinimal.h"
#endif

namespace SaudIK
{
	// ------------------------------------------------------------ two bones

	/** A limb solved: where the middle joint and the end go. */
	struct FTwoBone
	{
		FVector Mid = FVector::ZeroVector;
		FVector End = FVector::ZeroVector;
		bool bReached = true;      // false when the target was past full stretch
	};

	/** Never quite straight: a knee or elbow locked out at 180 degrees is a
	    limb that snaps, so the reach is held to this share of the two
	    segments' length. */
	constexpr float MaxStretch = 0.995f;

	/** The classic two-segment solve. The root stays where it is; Mid lands
	    in the plane of root, target and pole, bent toward the pole; End
	    lands on the target, or as near as the limb reaches. The segments'
	    lengths are the clip's, taken from the pose passed in. */
	inline FTwoBone TwoBone(const FVector& Root, const FVector& Mid, const FVector& End,
	                        const FVector& Target, const FVector& Pole)
	{
		const float A = FVector::Dist(Root, Mid);      // upper segment
		const float B = FVector::Dist(Mid, End);       // lower segment
		FTwoBone R;
		FVector ToTarget = Target - Root;
		float D = ToTarget.Size();
		const float Longest = (A + B) * MaxStretch;
		R.bReached = D <= Longest;
		if (D < 1e-3f)
		{
			R.Mid = Mid; R.End = End;
			return R;
		}
		if (D > Longest)
		{
			D = Longest;
		}
		const FVector Dir = ToTarget.GetSafeNormal();
		R.End = Root + Dir * D;

		// Where the bend goes: the pole's direction with the along-limb part
		// taken out. A pole on the line has nothing to say; the clip's own
		// bend is kept then.
		FVector Bend = (Pole - Root) - Dir * FVector::DotProduct(Pole - Root, Dir);
		if (Bend.IsNearlyZero(1e-3f))
		{
			Bend = (Mid - Root) - Dir * FVector::DotProduct(Mid - Root, Dir);
		}
		Bend = Bend.GetSafeNormal();

		// Law of cosines: how far along the line the middle joint sits, and
		// how far off it.
		const float Along = FMath::Clamp((A * A - B * B + D * D) / (2.f * D), -A, A);
		const float Off = FMath::Sqrt(FMath::Max(0.f, A * A - Along * Along));
		R.Mid = Root + Dir * Along + Bend * Off;
		return R;
	}

	// ----------------------------------------------------------------- feet

	/** A foot is planted, and put on the ground, when the clip has it
	    within this of the floor; above PlantFade it is swinging and left
	    to the clip; between the two the ground's say fades out. */
	constexpr float PlantHeight = 10.f;    // cm above the clip's floor
	constexpr float PlantFade = 28.f;

	/** How far the pelvis will go down for the lower foot: a step deeper
	    than this is a drop, and a drop is the character's to fall, not the
	    hips' to reach. */
	constexpr float MaxPelvisDrop = 40.f;

	/** The foot's tilt is the slope's, up to this. */
	constexpr float MaxFootTiltDegrees = 30.f;

	/** How fast the ground's corrections move, so a step onto a kerb is a
	    step and not a snap. Per second, exponential. */
	constexpr float FootSettleRate = 18.f;
	constexpr float PelvisSettleRate = 12.f;

	/** How much of the ground a foot at this height above the clip's floor
	    takes: 1 planted, 0 swinging. */
	inline float PlantAlpha(float FootHeightAboveFloor)
	{
		return 1.f - FMath::Clamp((FootHeightAboveFloor - PlantHeight) / (PlantFade - PlantHeight), 0.f, 1.f);
	}

	/** What one foot's trace said. GroundDelta is the ground's height under
	    the foot relative to the character's floor (the capsule's bottom):
	    negative for a dip, positive for a step up. */
	struct FFootGround
	{
		bool bHit = false;
		float GroundDelta = 0.f;
		FVector Normal = FVector::UpVector;
		float FootHeight = 0.f;     // the clip's foot above its floor
	};

	/** Where the pelvis goes: down to the lower planted foot, never up (a
	    step up under one foot bends that leg; it does not lift the man),
	    never past MaxPelvisDrop. A foot that is swinging, or whose trace
	    missed, has no say. */
	inline float PelvisOffset(const FFootGround& L, const FFootGround& R)
	{
		float Lowest = 0.f;
		if (L.bHit && PlantAlpha(L.FootHeight) > 0.f) Lowest = FMath::Min(Lowest, L.GroundDelta);
		if (R.bHit && PlantAlpha(R.FootHeight) > 0.f) Lowest = FMath::Min(Lowest, R.GroundDelta);
		return FMath::Max(Lowest, -MaxPelvisDrop);
	}

	/** How far the foot itself moves up or down: the ground's delta, weighted
	    by how planted it is. The pelvis has already gone down by
	    PelvisOffset, so the leg root moved with it; the foot's target is the
	    ground regardless, which is why the offset is absolute. */
	inline float FootOffset(const FFootGround& F)
	{
		if (!F.bHit) return 0.f;
		return F.GroundDelta * PlantAlpha(F.FootHeight);
	}

	/** The tilt a foot takes from the slope: the ground normal, limited to
	    MaxFootTiltDegrees from up, weighted by how planted the foot is, as
	    the normal it should be turned to. */
	inline FVector FootNormal(const FFootGround& F)
	{
		if (!F.bHit) return FVector::UpVector;
		const FVector N = F.Normal.GetSafeNormal();
		const float Cos = FMath::Clamp(FVector::DotProduct(N, FVector::UpVector), -1.f, 1.f);
		const float Angle = FMath::Acos(Cos);
		const float Limit = FMath::DegreesToRadians(MaxFootTiltDegrees);
		float Share = PlantAlpha(F.FootHeight);
		if (Angle > Limit && Angle > 1e-4f)
		{
			Share *= Limit / Angle;
		}
		// Slerp from up toward N by Share, on the arc between them.
		if (Angle < 1e-4f || Share <= 0.f) return FVector::UpVector;
		const FVector Axis = FVector::CrossProduct(FVector::UpVector, N).GetSafeNormal();
		const float T = Angle * Share;
		const FVector Side = FVector::CrossProduct(Axis, FVector::UpVector);
		return (FVector::UpVector * FMath::Cos(T) + Side * FMath::Sin(T)).GetSafeNormal();
	}

	/** Exponential approach, frame-rate independent: what Current becomes
	    after Dt at Rate per second. */
	inline float Settle(float Current, float Target, float Rate, float Dt)
	{
		const float K = 1.f - FMath::Exp(-Rate * Dt);
		return Current + (Target - Current) * K;
	}

	// ---------------------------------------------------------------- hands

	/** Which limb a strike is thrown with, as build_motion.py's STRIKES
	    table has it: the Jab is the lead (left) hand, the Cross and Hook the
	    rear (right), the Kick, Knee and Special the rear leg. Anything else
	    strikes with nothing and is left to its clip. Returns the bone
	    suffix side ('l' / 'r') in OutSide. */
	enum class ELimb : unsigned char { None, Arm, Leg };

	inline ELimb StrikingLimb(const char* AttackRow, char& OutSide)
	{
		auto Is = [AttackRow](const char* S)
		{
			int I = 0;
			while (AttackRow[I] && S[I] && AttackRow[I] == S[I]) ++I;
			return AttackRow[I] == 0 && S[I] == 0;
		};
		if (Is("Jab"))                                  { OutSide = 'l'; return ELimb::Arm; }
		if (Is("Cross") || Is("Hook"))                  { OutSide = 'r'; return ELimb::Arm; }
		if (Is("Kick") || Is("Knee") || Is("Special"))  { OutSide = 'r'; return ELimb::Leg; }
		OutSide = 0;
		return ELimb::None;
	}

	/** How much of the way to the victim the striking limb is drawn, over
	    the attack: in over the last of the startup, full through the active
	    frames, out over the start of the recovery. Zero is the clip alone. */
	constexpr float ContactLeadIn = 0.06f;    // seconds before the first active frame
	constexpr float ContactLeadOut = 0.10f;   // seconds after the last

	inline float ContactAlpha(float Elapsed, float Startup, float Active)
	{
		const float In0 = FMath::Max(0.f, Startup - ContactLeadIn);
		if (Elapsed < In0) return 0.f;
		if (Elapsed < Startup) return (Elapsed - In0) / FMath::Max(1e-3f, Startup - In0);
		const float Out0 = Startup + Active;
		if (Elapsed <= Out0) return 1.f;
		return 1.f - FMath::Clamp((Elapsed - Out0) / ContactLeadOut, 0.f, 1.f);
	}

	/** Where the fist should be to land on the victim: the point of his
	    capsule's surface on the line from the striking limb's root to his
	    centre, at the height the clip already has the fist. If that is
	    beyond the limb, the limb's full stretch along that line -- the
	    swing still goes his way. VictimCentre is the capsule's axis at any
	    height; VictimRadius the capsule's. */
	inline FVector ContactTarget(const FVector& LimbRoot, const FVector& ClipEnd,
	                             const FVector& VictimCentre, float VictimRadius, float LimbLength)
	{
		FVector Centre = VictimCentre;
		Centre.Z = ClipEnd.Z;                          // the clip decides the height
		FVector ToCentre = Centre - LimbRoot;
		ToCentre.Z = 0.f;
		const float D = ToCentre.Size();
		if (D < 1e-3f) return ClipEnd;
		const FVector Dir = ToCentre / D;
		const float Along = FMath::Min(FMath::Max(0.f, D - VictimRadius), LimbLength * MaxStretch);
		FVector T = LimbRoot + Dir * Along;
		T.Z = ClipEnd.Z;
		return T;
	}

	// ----------------------------------------------------------------- head

	/** What a neck does. Past the yaw limit the head stays at the limit
	    rather than facing away from the fight; past the reach the fighter
	    looks where he faces. */
	constexpr float LookMaxYawDegrees = 70.f;
	constexpr float LookMaxPitchDegrees = 30.f;
	constexpr float LookReach = 900.f;         // cm; further than this is not a fight
	constexpr float LookRate = 8.f;            // per second, exponential

	/** The direction the head should look, from where the eyes are to the
	    target, clamped in yaw and pitch against the body's facing. Returns
	    the facing itself when there is nothing to look at. */
	inline FVector LookDirection(const FVector& Eyes, const FVector& Facing, const FVector& Target, bool bHasTarget)
	{
		const FVector F = FVector(Facing.X, Facing.Y, 0.f).GetSafeNormal();
		if (!bHasTarget) return F;
		const FVector To = Target - Eyes;
		if (To.Size() > LookReach || To.IsNearlyZero(1e-3f)) return F;

		const FVector Left = FVector::CrossProduct(FVector::UpVector, F);   // Z up, X fwd: +Y is left
		const float Fwd = FVector::DotProduct(To, F);
		const float Side = FVector::DotProduct(To, Left);
		const float Up = To.Z;
		const float Flat = FMath::Sqrt(Fwd * Fwd + Side * Side);

		float Yaw = FMath::Atan2(Side, Fwd);
		float Pitch = FMath::Atan2(Up, FMath::Max(1e-3f, Flat));
		const float YawLimit = FMath::DegreesToRadians(LookMaxYawDegrees);
		const float PitchLimit = FMath::DegreesToRadians(LookMaxPitchDegrees);
		Yaw = FMath::Clamp(Yaw, -YawLimit, YawLimit);
		Pitch = FMath::Clamp(Pitch, -PitchLimit, PitchLimit);

		const float CP = FMath::Cos(Pitch);
		return (F * (FMath::Cos(Yaw) * CP) + Left * (FMath::Sin(Yaw) * CP) + FVector::UpVector * FMath::Sin(Pitch)).GetSafeNormal();
	}

	/** The neck takes this share of the turn, the head the rest. */
	constexpr float NeckShare = 0.35f;
}
