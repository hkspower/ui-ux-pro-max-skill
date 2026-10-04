#pragma once

/**
 * Runtime IK, with no engine in it: where a limb goes, given where the clip
 * put it and what the world is doing.
 *
 * Every clip in Content/Animation was posed on a flat floor against nobody.
 * The world is not flat -- the districts are ground discs on a spiral, the
 * island is rock -- and a strike is thrown at a man who is wherever he is,
 * not at the reach the clip was posed to. So, over the played clips, four
 * things are solved each frame (USaudMotionAnimInstance applies them):
 *
 *   feet     each foot the clip has on the floor -- by the clip's own
 *            measured plants (SaudPlants.h) -- is held where it landed
 *            in the world, and steps after the man when he has moved 12 cm
 *            off it; it stands on the ground under its heel and its ball,
 *            rolls onto the ball when the leg is short, its toes on the
 *            ground; the hips drop to the lower foot and carry the body's
 *            own changes of speed.
 *   hands    the striking point of an attack -- the knuckles, the ball of
 *            the foot, or the knee -- is put on the victim's own mark, a
 *            guard meets the incoming blow, and a guard fist stays by the
 *            face.
 *   body     the hips lag a snapped facing and come round after it; the
 *            chest and the face turn to the man that matters, the chest a
 *            share of the way, within what a trunk and a neck do.
 *   clips    one clip gives way to the next on a crossfade, each at its
 *            own time, never in a cut.
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
#include "SaudArena.h"
#include "SaudPlants.h"

namespace SaudIK
{
	// ------------------------------------------------------- shared pieces

	/** Exponential approach, frame-rate independent: what Current becomes
	    after Dt at Rate per second. */
	inline float Settle(float Current, float Target, float Rate, float Dt)
	{
		const float K = 1.f - FMath::Exp(-Rate * Dt);
		return Current + (Target - Current) * K;
	}

	/** 0 to 1 with no speed at either end (3t^2 - 2t^3): every ramp a limb
	    rides is one, so nothing jerks as the IK comes and goes. */
	inline float SmoothStep(float T)
	{
		T = FMath::Clamp(T, 0.f, 1.f);
		return T * T * (3.f - 2.f * T);
	}

	/** A share that comes and goes on a smooth step: on, it climbs to 1 over
	    InSeconds; off, it falls to 0 over OutSeconds, at any frame rate. Lin
	    is the straight-line progress, Value() the eased share. Both reach 0
	    and 1 exactly, so a solve at 0 is the clip and can be skipped. */
	struct FRamp
	{
		float Lin = 0.f;
		void Step(bool bOn, float Dt, float InSeconds, float OutSeconds)
		{
			const float Rate = bOn ? 1.f / FMath::Max(1e-3f, InSeconds) : -1.f / FMath::Max(1e-3f, OutSeconds);
			Lin = FMath::Clamp(Lin + Rate * FMath::Max(0.f, Dt), 0.f, 1.f);
		}
		float Value() const { return SmoothStep(Lin); }
	};

	/** A critically damped spring, in closed form: exact at any frame rate,
	    no overshoot from rest, its speed kept when the target moves, and a
	    Dt of 0 (the freeze) holds it. 95 % of the way takes 4.74 / Omega. */
	struct FEase
	{
		float X = 0.f;
		float V = 0.f;
		void To(float Target, float Omega, float Dt)
		{
			if (Dt <= 0.f) return;
			const float Y = X - Target;
			const float J = V + Omega * Y;
			const float E = FMath::Exp(-Omega * Dt);
			X = Target + (Y + J * Dt) * E;
			V = (V - J * Omega * Dt) * E;
		}
	};

	/** V turned by Radians about the unit Axis, the way FQuat(Axis, Radians)
	    turns it: about +Z, +X goes to +Y. */
	inline FVector RotateAbout(const FVector& V, const FVector& Axis, float Radians)
	{
		const float C = FMath::Cos(Radians), S = FMath::Sin(Radians);
		const float Along = FVector::DotProduct(Axis, V);
		return V * C + FVector::CrossProduct(Axis, V) * S + Axis * (Along * (1.f - C));
	}

	/** V turned by Share of the least turn that takes direction From onto
	    direction To: FQuat::FindBetweenNormals in vectors. Opposite
	    directions turn about an axis square to From. */
	inline FVector Swing(const FVector& V, const FVector& From, const FVector& To, float Share = 1.f)
	{
		const FVector A = From.GetSafeNormal(), B = To.GetSafeNormal();
		FVector Axis = FVector::CrossProduct(A, B);
		const float SinA = Axis.Size();
		const float Dot = FVector::DotProduct(A, B);
		const float CosA = FMath::Clamp(Dot, -1.f, 1.f);
		if (SinA < 1e-6f)
		{
			if (CosA > 0.f) return V;           // already there
			const float AZ = A.Z;
			Axis = FVector::CrossProduct(A, FMath::Abs(AZ) < 0.9f ? FVector::UpVector : FVector(1.f, 0.f, 0.f)).GetSafeNormal();
		}
		else
		{
			Axis = Axis / SinA;
		}
		return RotateAbout(V, Axis, FMath::Atan2(SinA, CosA) * Share);
	}

	/** A yaw in degrees on (-180, 180]. A value that is no finite number of
	    turns is no turn at all. */
	inline float WrapDegrees(float D)
	{
		if (!(D > -1e6f && D < 1e6f)) return 0.f;
		while (D > 180.f) D -= 360.f;
		while (D <= -180.f) D += 360.f;
		return D;
	}

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
	    lengths are the clip's, taken from the pose passed in. Alpha is how
	    whole the solve is: until it is whole the reach is never held
	    tighter than the clip's own, so at no share a clip limb straighter
	    than MaxStretch is left exactly as it is. */
	inline FTwoBone TwoBone(const FVector& Root, const FVector& Mid, const FVector& End,
	                        const FVector& Target, const FVector& Pole, float Alpha = 1.f)
	{
		const float A = FVector::Dist(Root, Mid);      // upper segment
		const float B = FVector::Dist(Mid, End);       // lower segment
		FTwoBone R;
		FVector ToTarget = Target - Root;
		float D = ToTarget.Size();
		const float ClipReach = FVector::Dist(Root, End);
		const float Whole = FMath::Clamp(Alpha, 0.f, 1.f);
		const float Longest = FMath::Lerp(FMath::Max((A + B) * MaxStretch, FMath::Min(ClipReach, A + B)), (A + B) * MaxStretch, Whole);
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

	/** Where the end joint goes when the lower segment and the end are one
	    piece from the middle joint to a tip it carries (a fist square on its
	    forearm, a foot set on its shin): turned with the lower segment from
	    Mid->Tip onto To.Mid->To.End. The tip then lands on To.End. */
	inline FVector RigidEnd(const FVector& Mid, const FVector& End, const FVector& Tip, const FTwoBone& To)
	{
		return To.Mid + Swing(End - Mid, Tip - Mid, To.End - To.Mid);
	}

	// ----------------------------------------------------------------- feet

	/** A foot is planted, and put on the ground, when the clip has it
	    within this of the floor; above PlantFade it is swinging and left
	    to the clip; between the two the ground's say fades out. The
	    ankle's height; build_motion.py reads these three numbers. */
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
	    takes: 1 planted, 0 swinging. Size: his leg over Saud's -- the bands
	    are Saud's centimetres, and a man half again his size lifts his feet
	    half again as high in the same clip (2026-10-03, the bosses: ZAYOS's
	    planted band was Saud's 10 cm on a leg 1.48 times as long). */
	inline float PlantAlpha(float FootHeightAboveFloor, float Size = 1.f)
	{
		const float K = FMath::Max(Size, 0.1f);
		return 1.f - FMath::Clamp((FootHeightAboveFloor - PlantHeight * K) / ((PlantFade - PlantHeight) * K), 0.f, 1.f);
	}

	// ------------------------------------------------- feet, held in place

	/** The mesh's place in the world: its origin, its three unit axes and
	    its uniform scale. The engine fills it from the component's
	    transform; plain vectors here, so the harness can move and turn a
	    man under his feet. */
	struct FBasis
	{
		FVector Origin = FVector::ZeroVector;
		FVector X = FVector(1.f, 0.f, 0.f);
		FVector Y = FVector(0.f, 1.f, 0.f);
		FVector Z = FVector::UpVector;
		float Scale = 1.f;
	};

	inline FVector ToWorld(const FBasis& B, const FVector& P)
	{
		return B.Origin + (B.X * P.X + B.Y * P.Y + B.Z * P.Z) * B.Scale;
	}

	inline FVector ToMesh(const FBasis& B, const FVector& W)
	{
		const FVector D = (W - B.Origin) / B.Scale;
		return FVector(FVector::DotProduct(D, B.X), FVector::DotProduct(D, B.Y), FVector::DotProduct(D, B.Z));
	}

	/** A direction from the world into the mesh's axes, and back. */
	inline FVector DirToMesh(const FBasis& B, const FVector& V)
	{
		return FVector(FVector::DotProduct(V, B.X), FVector::DotProduct(V, B.Y), FVector::DotProduct(V, B.Z));
	}

	inline FVector DirToWorld(const FBasis& B, const FVector& V)
	{
		return B.X * V.X + B.Y * V.Y + B.Z * V.Z;
	}

	/** V turned by the shortest turn that takes straight up to N: what
	    FQuat::FindBetweenNormals(FVector::UpVector, N).RotateVector(V) does. */
	inline FVector TurnUpTo(const FVector& N, const FVector& V)
	{
		return Swing(V, FVector::UpVector, N);
	}

	/** Current turned toward Target at Rate per second, along the arc:
	    Settle for a direction. */
	inline FVector SettleNormal(const FVector& Current, const FVector& Target, float Rate, float Dt)
	{
		return Swing(Current, Current, Target, 1.f - FMath::Exp(-Rate * Dt)).GetSafeNormal();
	}

	/** The tilt a sole takes from a ground normal: limited to
	    MaxFootTiltDegrees from up, then Share of that along the arc. */
	inline FVector LimitedTilt(const FVector& Normal, float Share)
	{
		const FVector N = Normal.GetSafeNormal();
		const float Up = FVector::DotProduct(N, FVector::UpVector);
		const float Angle = FMath::Acos(FMath::Clamp(Up, -1.f, 1.f));
		const float Limit = FMath::DegreesToRadians(MaxFootTiltDegrees);
		if (Angle < 1e-4f || Share <= 0.f) return FVector::UpVector;
		const float Most = FMath::Min(1.f, Limit / Angle);
		return Swing(FVector::UpVector, FVector::UpVector, N, Most * FMath::Clamp(Share, 0.f, 1.f)).GetSafeNormal();
	}

	/** A ball the clip has within BallDownHeight of the lower ball, and no
	    more than BallRestBand over its own rest height, is on the floor;
	    over BallUpHeight off the lower one it is not; between, it stays
	    what it was. Against the lower ball, not the rest height: a clip
	    retargeted onto another man's legs plants its balls a few cm off
	    that man's rest. The clips ground the sole to 0.2 mm; a swing is past
	    1.5 cm in its first frame -- the street men's 10 cm swing too, which
	    the ankle's PlantHeight band cannot tell from a planted foot. */
	constexpr float BallDownHeight = 1.f;
	constexpr float BallUpHeight = 1.5f;
	constexpr float BallRestBand = 5.f;

	/** A ball this far over the lower one is swinging: it has no say in the
	    ground under it, in the hips, or in its toes. */
	constexpr float SwingHeight = 6.f;

	/** How much of the ground a ball this far over the lower one takes; the
	    bands grown with the man (Size, his leg over Saud's). */
	inline float GroundShare(float Lift, float Size = 1.f)
	{
		const float K = FMath::Max(Size, 0.1f);
		return 1.f - FMath::Clamp((Lift - BallUpHeight * K) / ((SwingHeight - BallUpHeight) * K), 0.f, 1.f);
	}

	/** Saud's leg, hip to ankle (build_motion's 0.882 m): the distances a
	    foot is held and steps by are his, grown with the man. */
	constexpr float SaudLegLength = 88.2f;

	/** How far the clip may carry a held ball off its hold before the foot
	    steps after it: what a bent knee takes without reading wrong, about a
	    quarter of a guard's stance -- 27 degrees of turning on the spot for
	    a foot 25 cm from his middle. */
	constexpr float HoldDrift = 12.f;
	/** Past this a foot steps even while the other is stepping or in the air:
	    a shove, not a shuffle. */
	constexpr float HoldDriftHard = 30.f;
	/** A man standing still brings a held foot left more than this off the
	    clip's spot back under it -- a step, the further foot first -- once
	    its drift has held still for SettleSeconds: the drift a turn leaves
	    under HoldDrift is not kept for as long as he stands. */
	constexpr float SettleDrift = 3.f;
	constexpr float SettleSeconds = 0.25f;
	/** Past this the man jumped (a respawn, a travel), and the hold is dropped
	    with no glide. */
	constexpr float HoldTeleport = 100.f;
	/** A held leg asked for more than this share of its length rolls onto
	    its ball: under MaxStretch, so the heel comes up before TwoBone would
	    drag the foot. */
	constexpr float HoldReach = 0.985f;
	/** Seconds to hand a foot back to the clip when the clip lifts it: inside
	    the first third of the shortest swing the clips have -- the side
	    walks' 0.27 s, measured (SaudPlants.h); it was 0.10 s, against a
	    0.37 s walk that was never measured. */
	constexpr float ReleaseSeconds = 0.08f;
	/** Seconds and height of a step the foot takes on its own: a shuffle, not
	    a stride. */
	constexpr float StepSeconds = 0.14f;
	constexpr float StepLift = 4.f;
	/** How far the heel comes up onto the ball to keep a held foot under a
	    leg too short for it. */
	constexpr float MaxHeelRollDegrees = 30.f;
	/** The toes bend up as far as the rig's toe roll (rig_full_ik.TOE_ROLL,
	    55 degrees) and down a little. */
	constexpr float ToeUpDegrees = 55.f;
	constexpr float ToeDownDegrees = 10.f;
	/** A ground hit whose normal is steeper than 60 degrees is the face of a
	    step: its height counts, its slope does not. */
	constexpr float WalkableZ = 0.5f;
	/** A heel and ball whose heights disagree with their own normals' slope
	    by more than EdgeDegrees stand across an edge: the foot stays level,
	    on the higher. It stays across until they agree within
	    EdgeLeaveDegrees, so the foot of a ramp does not flicker. */
	constexpr float EdgeDegrees = 8.f;
	constexpr float EdgeLeaveDegrees = 5.f;
	/** A foot rises onto a step faster than it settles off one: up within
	    four frames at 60 Hz, so a swinging foot never sinks into a kerb. */
	constexpr float FootRiseRate = 40.f;
	/** The feet come on over a fifth of a second as the knees take the
	    weight, and let go in 0.12 s: a dash or a fall leaves the floor at
	    once and is not dragged down. */
	constexpr float FeetOnSeconds = 0.20f;
	constexpr float FeetOffSeconds = 0.12f;
	/** A rise or fall of the capsule this much more than the ground it
	    covered in one frame explains is a step it took (CharacterMovement
	    steps a kerb in one frame). */
	constexpr float StepAbsorbSlack = 1.f;
	/** The steepest walkable slope: CharacterMovement's WalkableFloorAngle
	    (44.765 degrees, its default; tan 0.992). No slope rises faster per
	    run than this, so with nothing known of the ground a rise past it is
	    a step. */
	constexpr float SlopeLimitDegrees = 44.765f;
	/** With the ground's own grade known (the feet's traces), a rise that
	    grade does not explain by more than this share of the run, plus
	    StepAbsorbSlack, is a step: a 5 cm kerb is absorbed at 341 cm/s at
	    30 Hz (11.4 cm of run a frame), which the slope limit alone would
	    take for a slope (2026-10-04). */
	constexpr float StepGradeSlack = 0.15f;

	/** Whether the capsule's move this frame was a step up or down, told
	    from a slope by its rise over its run: against the ground's own
	    Grade (rise per run along the move, from the feet's traces) when it
	    is known, held to the slope limit; against the slope limit when not. */
	inline bool SteppedCapsule(const FVector& Moved, bool bGradeKnown = false, float Grade = 0.f)
	{
		const float Rise = Moved.Z;
		const float Run = FVector(Moved.X, Moved.Y, 0.f).Size();
		const float Limit = FMath::Tan(FMath::DegreesToRadians(SlopeLimitDegrees));
		if (!bGradeKnown) return FMath::Abs(Rise) > Run * Limit + StepAbsorbSlack;
		const float G = FMath::Clamp(Grade, -Limit, Limit);
		return FMath::Abs(Rise - Run * G) > StepAbsorbSlack + StepGradeSlack * Run;
	}

	/** The pelvis drops to the lower foot faster the faster he goes: at
	    PelvisSettleRate standing, twice it at this speed, and so on, so a
	    run downhill keeps its legs bent rather than hanging the hips over a
	    foot already gone down the slope. Rising back is never hurried. */
	constexpr float PelvisDropDoubleSpeed = 150.f;

	inline float PelvisRate(float Current, float Target, float Speed)
	{
		return Target < Current ? PelvisSettleRate * (1.f + FMath::Max(0.f, Speed) / PelvisDropDoubleSpeed) : PelvisSettleRate;
	}

	/** The part of a change of velocity along the way he goes: a start or a
	    stop. What is left, square to it, is a curve's -- the lean's
	    (FLean), not the hips' to throw outward. */
	inline FVector AlongPath(const FVector& Velocity, const FVector& Last)
	{
		const FVector V(Velocity.X, Velocity.Y, 0.f), L(Last.X, Last.Y, 0.f);
		const FVector Dir = V.Size() > 1.f ? V.GetSafeNormal() : (L.Size() > 1.f ? L.GetSafeNormal() : FVector::ZeroVector);
		return Dir * FVector::DotProduct(V - L, Dir);
	}
	/** The hips carry the body's own changes of speed: they lag a start and
	    run on past a stop by this many seconds of the change (a 0-to-341
	    cm/s start throws them back 5.4 cm), come home at WeightRate, never
	    further than WeightMaxCm. */
	constexpr float WeightKick = 0.6f;
	constexpr float WeightRate = 14.f;
	constexpr float WeightMaxCm = 8.f;
	/** A looping clip whose planted ball travels slower than this (cm per
	    second of the clip) is standing, not walking, and keeps its clock.
	    (100 until 2026-10-03: Saud's slow walk, from motion capture, strides
	    100.2, and sat on the line; nothing that stands strides near 80.) */
	constexpr float StrideMinSpeed = 80.f;
	/** The walk's clock runs between half and 1.6 times its own: outside
	    that a jog reads as a march or a sprint, and the hold takes the rest. */
	constexpr float StrideRateMin = 0.5f;
	constexpr float StrideRateMax = 1.6f;
	/** How fast the stride meter follows its samples, per clip second. */
	constexpr float StrideMeterRate = 8.f;
	/** Only a ball this close to the lower one is metered: flat on the
	    floor, not yet rising into its swing, whose first frames move slower. */
	constexpr float StrideFloorHeight = 0.5f;

	/** A foot is down when this share of the clips playing have it down by
	    their measured plants (SaudPlants.h, see MixDown), and up again under
	    MixDownOff: through a crossfade from a planted clip to a swinging one
	    it changes its mind once. */
	constexpr float MixDownOn = 0.6f;
	constexpr float MixDownOff = 0.4f;

	/** One foot's hold on the ground. */
	struct FFootHold
	{
		bool bDown = false;            // the clip has the ball on the floor
		bool bHeld = false;            // held where it was planted
		FVector Anchor = FVector::ZeroVector;   // world: where the ball is held (Z unused)
		FVector Slip = FVector::ZeroVector;     // mesh: drawn minus the clip's, when it was let go
		float Weight = 0.f;            // 1 held, falling to 0 through a hand-back
		float Progress = 1.f;          // 0..1 through a hand-back; 1 when none runs
		float Seconds = ReleaseSeconds;
		bool bStep = false;            // the hand-back is a step the clip does not take
		float Still = 0.f;             // seconds its drift has held still, while he stands
		float LastDrift = 0.f;
		float Roll = 0.f;              // the heel's roll onto the ball, eased
		FVector RollAxis = FVector(0.f, 1.f, 0.f);
	};

	/** Where a ball is drawn, in the mesh's space: on its hold, at the
	    clip's height; or the clip's place plus what is left of the slip it
	    was let go with. Raw is the clip's ball. */
	inline FVector DrawnBall(const FFootHold& H, const FBasis& Mesh, const FVector& Raw)
	{
		if (H.bHeld)
		{
			const FVector A = ToMesh(Mesh, H.Anchor);
			return FVector(A.X, A.Y, Raw.Z);
		}
		return Raw + H.Slip * H.Weight;
	}

	/** Starts handing a held foot back to the clip, from where it is drawn,
	    in the mesh's space: a foot let go moves with the man, never trails
	    behind him in the world. */
	inline void LetGo(FFootHold& H, bool bStep, const FBasis& Mesh, const FVector& Raw)
	{
		FVector D = DrawnBall(H, Mesh, Raw) - Raw;
		D.Z = 0.f;
		H.Slip = D;
		H.bHeld = false;
		H.Weight = 1.f;
		H.Progress = 0.f;
		H.Seconds = bStep ? StepSeconds : ReleaseSeconds;
		H.bStep = bStep;
	}

	/** A step's height now: up and down again with no jump in speed. */
	inline float StepHeight(const FFootHold& H, float Size)
	{
		if (!H.bStep || H.Progress >= 1.f) return 0.f;
		const float S = FMath::Sin(3.14159265f * H.Progress);
		return StepLift * Size * S * S;
	}

	/** One frame of both feet's holds. Raw: where the clip has each ball,
	    mesh space; Lift: its height over its rest height; Measured: the
	    clips' measured share of each foot down (MixDown), or -1 where they
	    are not measured and the heights decide; bAllowed: the ground may
	    have it (wanted, not the strike's); bHold: a hold can keep what this
	    clip does (see HoldsFeet); bSettle: he stands, and a foot left off
	    its spot may step back under the clip; Size: his leg over Saud's. */
	inline void StepHolds(FFootHold (&H)[2], const FBasis& Mesh, const FVector (&Raw)[2], const float (&Lift)[2],
	                      const float (&Measured)[2], const bool (&bAllowed)[2], bool bHold, bool bSettle, float Size, float Dt,
	                      bool bStopping = false)
	{
		for (int S = 0; S < 2; ++S)
		{
			FFootHold& F = H[S];
			if (!F.bHeld && F.Progress < 1.f)
			{
				F.Progress = FMath::Min(1.f, F.Progress + FMath::Max(0.f, Dt) / F.Seconds);
				F.Weight = 1.f - SmoothStep(F.Progress);
			}
		}
		const float Floor = FMath::Min(Lift[0], Lift[1]);
		// Size is the leg's in the mesh's units; the drift below is the
		// world's, so a mesh drawn at a scale steps after that much more
		const float WorldSize = Size * Mesh.Scale;
		for (int S = 0; S < 2; ++S)
		{
			FFootHold& F = H[S];
			F.bDown = Measured[S] >= 0.f
				? Measured[S] >= (F.bDown ? MixDownOff : MixDownOn)
				: Lift[S] - Floor <= (F.bDown ? BallUpHeight : BallDownHeight) * Size && Lift[S] <= BallRestBand * Size;
		}
		float Drift[2] = { 0.f, 0.f };
		for (int S = 0; S < 2; ++S)
		{
			FFootHold& F = H[S];
			if (!F.bHeld) continue;
			FVector D = F.Anchor - ToWorld(Mesh, Raw[S]);
			D.Z = 0.f;
			Drift[S] = D.Size();
			if (Drift[S] > HoldTeleport * WorldSize)
			{
				F.bHeld = false; F.Weight = 0.f; F.Progress = 1.f; F.bStep = false; F.Slip = FVector::ZeroVector; Drift[S] = 0.f;
			}
		}
		for (int S = 0; S < 2; ++S)
		{
			FFootHold& F = H[S];
			if (!F.bHeld) continue;
			// a stop (a walk crossfading to his guard): the foot standing holds
			// until the last swing has landed, though the walk fading out lifts it
			const bool bLastStance = bStopping && !H[1 - S].bHeld;
			if (!bAllowed[S]) LetGo(F, false, Mesh, Raw[S]);
			else if (!F.bDown && !bLastStance) LetGo(F, false, Mesh, Raw[S]);
			else if (!bHold) LetGo(F, false, Mesh, Raw[S]);
		}
		for (int S = 0; S < 2; ++S)
		{
			FFootHold& F = H[S];
			const FFootHold& O = H[1 - S];
			if (!F.bHeld) continue;
			const bool bOtherStands = O.bHeld;
			const bool bMine = Drift[S] >= Drift[1 - S] || Drift[1 - S] <= HoldDrift * WorldSize;
			if (Drift[S] > HoldDriftHard * WorldSize || (Drift[S] > HoldDrift * WorldSize && bOtherStands && bMine)) LetGo(F, true, Mesh, Raw[S]);
		}
		for (int S = 0; S < 2; ++S)
		{
			FFootHold& F = H[S];
			const bool bSteady = F.bHeld && bSettle && FMath::Abs(Drift[S] - F.LastDrift) < 0.05f * WorldSize;
			F.Still = bSteady ? F.Still + FMath::Max(0.f, Dt) : 0.f;
			F.LastDrift = Drift[S];
		}
		{
			const int Far = Drift[0] >= Drift[1] ? 0 : 1;
			FFootHold& F = H[Far];
			if (F.bHeld && H[1 - Far].bHeld && F.Still >= SettleSeconds && Drift[Far] > SettleDrift * WorldSize)
			{
				LetGo(F, true, Mesh, Raw[Far]);
				F.Still = 0.f;
			}
		}
		for (int S = 0; S < 2; ++S)
		{
			FFootHold& F = H[S];
			if (F.bHeld || !bAllowed[S] || !F.bDown) continue;
			if (!bHold) continue;
			if (F.bStep && F.Progress < 1.f) continue;
			F.Anchor = ToWorld(Mesh, DrawnBall(F, Mesh, Raw[S]));
			F.bHeld = true; F.Weight = 1.f; F.Progress = 1.f; F.bStep = false; F.Slip = FVector::ZeroVector;
		}
	}

	/** Measures how fast a clip carries a planted ball, per second of the
	    clip's own time: the speed it was authored to walk at, at this man's
	    size. */
	struct FStrideMeter
	{
		int Clip = -1;
		float Time = 0.f;
		FVector Ball[2] = { FVector::ZeroVector, FVector::ZeroVector };
		bool bDown[2] = { false, false };
		float Speed = 0.f;
		bool bValid = false;
	};

	inline void MeasureStride(FStrideMeter& M, int Clip, float ClipTime, const FVector (&Ball)[2], const float (&Lift)[2])
	{
		const float Floor = FMath::Min(Lift[0], Lift[1]);
		if (Clip != M.Clip)
		{
			M = FStrideMeter();
			M.Clip = Clip;
		}
		else
		{
			const float Dt = ClipTime - M.Time;
			if (Dt > 1e-4f && Dt < 0.1f)
			{
				for (int S = 0; S < 2; ++S)
				{
					if (Lift[S] - Floor > StrideFloorHeight || !M.bDown[S]) continue;
					FVector D = Ball[S] - M.Ball[S];
					D.Z = 0.f;
					const float V = D.Size() / Dt;
					M.Speed = M.bValid ? Settle(M.Speed, V, StrideMeterRate, Dt) : V;
					M.bValid = true;
				}
			}
		}
		M.Time = ClipTime;
		for (int S = 0; S < 2; ++S) { M.Ball[S] = Ball[S]; M.bDown[S] = Lift[S] - Floor <= StrideFloorHeight; }
	}

	/** The rate a looping clip's clock runs at so its planted feet keep pace
	    with the ground: 1 for a clip that is standing. GroundSpeed is the
	    world's; the meter is in the mesh's units, so it grows by Scale. */
	inline float StrideRate(float GroundSpeed, const FStrideMeter& M, float Scale)
	{
		const float Clip = M.Speed * Scale;
		if (!M.bValid || M.Speed < StrideMinSpeed) return 1.f;
		return FMath::Clamp(GroundSpeed / Clip, StrideRateMin, StrideRateMax);
	}

	/** Whether a hold can keep what the clip does: in an attack, standing,
	    or in a clip whose own feet step (its meter says it walks). A clip
	    that does not step while the capsule moves -- the Block walked, a
	    blow's push -- glides as it did, rather than tap-dance. */
	inline bool HoldsFeet(bool bAttacking, bool bStanding, const FStrideMeter& M, int ClipSerial)
	{
		if (bAttacking) return true;
		if (bStanding) return true;
		return M.Clip == ClipSerial && M.bValid && M.Speed >= StrideMinSpeed;
	}

	/** StrideRate from a clip's measured stride (SaudPlants::FClip::Stride,
	    cm per second of the clip): no meter to fill, so a walk is at the
	    man's pace from its first frame. */
	inline float StrideRateMeasured(float GroundSpeed, float ClipStride, float Scale)
	{
		if (ClipStride < StrideMinSpeed) return 1.f;
		return FMath::Clamp(GroundSpeed / (ClipStride * Scale), StrideRateMin, StrideRateMax);
	}

	/** A man in his guard pushed or edging along no faster than this holds
	    his feet and shuffles after them (HoldDrift, one foot at a time, a
	    StepSeconds step each) -- a guard's shuffle, about two and a half
	    steps a foot a second at the most; faster, the Block glides as it
	    did, rather than tap-dance (2026-10-03, "improve gloss ik": the
	    Block walked at any pace glided). */
	constexpr float BlockShuffleMax = 60.f;

	/** HoldsFeet from a clip's measured stride: a clip that walks holds its
	    feet as the man moves; one that does not (the Block walked) glides --
	    unless it is a guard edging along slowly enough to shuffle. */
	inline bool HoldsFeetMeasured(bool bAttacking, bool bStanding, float ClipStride, bool bBlocking = false,
	                              float GroundSpeed = 0.f, float Size = 1.f)
	{
		// (Size: his size against Saud's, the world's: a bigger man's guard
		// pace is a longer shuffle, 2026-10-03)
		return bAttacking || bStanding || ClipStride >= StrideMinSpeed
		    || (bBlocking && GroundSpeed <= BlockShuffleMax * FMath::Max(Size, 0.1f));
	}

	/** One trace's answer, in the mesh's space. */
	struct FGroundPoint
	{
		bool bHit = false;
		FVector Point = FVector::ZeroVector;
		FVector Normal = FVector::UpVector;
	};

	/** One foot as the clip has it this frame, in the mesh's space, before
	    any IK, and the ground under its heel and its ball. */
	struct FFootIn
	{
		FVector Hip = FVector::ZeroVector;      // thigh_
		FVector Ankle = FVector::ZeroVector;    // foot_
		FVector Ball = FVector::ZeroVector;     // ball_
		FVector ToeDir = FVector(1.f, 0.f, 0.f);    // the toes' way
		FVector FootFwd = FVector(1.f, 0.f, 0.f);   // the sole's forward
		FVector FootUp = FVector::UpVector;         // the sole's up
		float LegLength = 0.f;                  // thigh to calf to foot, the clip's
		float AnkleRest = 0.f;                  // foot_'s height over the sole at rest
		float BallRest = 0.f;                   // ball_'s
		FGroundPoint HeelGround, BallGround;    // the ground under the ankle, and under the ball
		bool bStrike = false;                   // the strike's leg: no hold
	};

	struct FFeetIn
	{
		FBasis Mesh;
		bool bWanted = false;       // on the ground and standing
		bool bHold = false;         // HoldsFeet
		bool bSettle = false;       // standing, not striking: a foot left off its spot steps back
		bool bTeleported = false;   // Teleported: nothing carries over but the feet's share
		bool bBlending = false;     // a crossfade runs: the stride meter waits
		bool bStopping = false;     // a walk crossfading to a stand (Stopping): the last swing lands first
		FVector Velocity = FVector::ZeroVector;   // the capsule's, world, flat
		FFootIn Foot[2];
		int ClipSerial = 0;
		float ClipTime = 0.f;
		float Down[2] = { -1.f, -1.f };   // the clips' measured share of each foot down (MixDown); -1 unmeasured
	};

	struct FFeetState
	{
		FRamp Alpha;
		FFootHold Hold[2];
		float FootZ[2] = { 0.f, 0.f };
		FVector Tilt[2] = { FVector::UpVector, FVector::UpVector };   // world
		bool bEdge[2] = { false, false };
		float PelvisZ = 0.f;
		FEase Weight[2];               // the hips' carry, mesh X and Y
		FVector LastVelocity = FVector::ZeroVector;
		FVector LastOrigin = FVector::ZeroVector;
		bool bKnown = false;
		FStrideMeter Stride;
		float Absorbed = 0.f;          // the capsule's step taken in by the hips this frame (mesh units), 0 none
	};

	struct FFootPlan
	{
		FVector Ball = FVector::ZeroVector;     // where ball_ goes, mesh space
		FVector Tilt = FVector::UpVector;       // the sole's normal
		FVector Ground = FVector::UpVector;     // the ground's normal under the ball, for the toes
		float ToeShare = 0.f;
		float Share = 1.f;                      // the feet's share: the heel's roll is drawn by it
	};

	struct FFeetPlan
	{
		float Alpha = 0.f;
		FVector Pelvis = FVector::ZeroVector;
		FFootPlan Foot[2];
	};

	/** What the ground asks of one foot, before smoothing. */
	struct FFootPlace
	{
		FVector Tilt = FVector::UpVector;
		float Planted = 0.f;            // the ground's height under the sole, by the planted share
		float BallFloor = -1e9f;        // no part of the sole under these (mesh Z)
		float HeelFloor = -1e9f;
		FVector Ground = FVector::UpVector;
	};

	/** The ground under one foot. Lift: its ball over the lower ball. bEdge
	    is the foot's own, kept frame to frame. */
	inline FFootPlace PlaceFoot(const FFootIn& F, bool bWanted, float Lift, bool& bEdge, float Size = 1.f)
	{
		FFootPlace P;
		if (!bWanted) { bEdge = false; return P; }
		const float Share = PlantAlpha(F.Ankle.Z - F.AnkleRest, Size) * GroundShare(Lift, Size);
		const FGroundPoint& H = F.HeelGround;
		const FGroundPoint& B = F.BallGround;
		const float HNZ = H.Normal.Z, BNZ = B.Normal.Z;
		const bool bHN = H.bHit && HNZ >= WalkableZ;
		const bool bBN = B.bHit && BNZ >= WalkableZ;
		FVector N = FVector::UpVector;
		if (bHN && bBN) N = (H.Normal + B.Normal).GetSafeNormal();
		else if (bHN) N = H.Normal;
		else if (bBN) N = B.Normal;
		P.Ground = bBN ? B.Normal : N;
		float Ground = 0.f;
		bool bAcross = false;
		if (H.bHit && B.bHit)
		{
			FVector Along = B.Point - H.Point;
			Along.Z = 0.f;
			const float Run = Along.Size();
			if (Run > 1.f)
			{
				const FVector Dir = Along / Run;
				const float Rise = B.Point.Z - H.Point.Z;
				const float Fall = -FVector::DotProduct(N, Dir), Up = N.Z;
				const float Off = FMath::Abs(FMath::Atan2(Rise, Run) - FMath::Atan2(Fall, Up));
				bAcross = Off > FMath::DegreesToRadians(bEdge ? EdgeLeaveDegrees : EdgeDegrees);
			}
			const float HZ = H.Point.Z, BZ = B.Point.Z;
			Ground = bAcross ? FMath::Max(HZ, BZ) : BZ;
		}
		else if (B.bHit) Ground = B.Point.Z;
		else if (H.bHit) Ground = H.Point.Z;
		bEdge = bAcross;
		if (bAcross) { N = FVector::UpVector; P.Ground = FVector::UpVector; }
		P.Tilt = LimitedTilt(N, Share);
		P.Planted = Ground * Share;
		if (B.bHit) P.BallFloor = B.Point.Z;
		if (H.bHit) P.HeelFloor = H.Point.Z;
		return P;
	}

	/** The ground's grade along the capsule's move, rise per run: the mean
	    of the walkable normals the feet's traces found (the mesh's own
	    space, its Z up), false when none. A kerb's top and foot are level,
	    so its grade is none and the capsule's rise is a step; a ramp's is
	    its own, and the capsule climbing it is not. */
	inline bool GroundGrade(const FFeetIn& In, const FVector& MovedWorld, float& OutGrade)
	{
		OutGrade = 0.f;
		const FVector Flat(MovedWorld.X, MovedWorld.Y, 0.f);
		if (Flat.Size() < 1e-3f) return false;
		FVector D = DirToMesh(In.Mesh, Flat.GetSafeNormal());
		D.Z = 0.f;
		D = D.GetSafeNormal();
		float Sum = 0.f;
		int N = 0;
		for (int S = 0; S < 2; ++S)
		{
			const FGroundPoint* Points[2] = { &In.Foot[S].HeelGround, &In.Foot[S].BallGround };
			for (const FGroundPoint* G : Points)
			{
				const FVector Nm = G->Normal.GetSafeNormal();
				if (!G->bHit || Nm.Z < WalkableZ) continue;
				Sum += static_cast<float>(-(Nm.X * D.X + Nm.Y * D.Y) / Nm.Z);
				++N;
			}
		}
		if (N == 0) return false;
		OutGrade = Sum / N;
		return true;
	}

	/** One frame of the feet: holds, ground, hips. Mesh space out. */
	inline FFeetPlan StepFeet(FFeetState& St, const FFeetIn& In, float Dt)
	{
		FFeetPlan Out;
		if (In.bTeleported)
		{
			const FRamp Keep = St.Alpha;
			St = FFeetState();
			St.Alpha = Keep;
		}
		St.Alpha.Step(In.bWanted, Dt, FeetOnSeconds, FeetOffSeconds);
		const float A = St.Alpha.Value();
		Out.Alpha = A;
		const float Size = 0.5f * (In.Foot[0].LegLength + In.Foot[1].LegLength) / SaudLegLength;
		const float Scale = In.Mesh.Scale;

		FVector Raw[2];
		float Lift[2];
		bool bAllowed[2];
		for (int S = 0; S < 2; ++S)
		{
			Raw[S] = In.Foot[S].Ball;
			Lift[S] = In.Foot[S].Ball.Z - In.Foot[S].BallRest;
			bAllowed[S] = In.bWanted && !In.Foot[S].bStrike;
		}
		StepHolds(St.Hold, In.Mesh, Raw, Lift, In.Down, bAllowed, In.bHold, In.bSettle, Size, Dt, In.bStopping);
		if (!In.bBlending) MeasureStride(St.Stride, In.ClipSerial, In.ClipTime, Raw, Lift);
		const bool bKnown = St.bKnown;

		// A kerb the capsule stepped up or down in one frame: the body is
		// drawn where it was and settles after, as the feet do.
		{
			const FVector Moved = In.Mesh.Origin - St.LastOrigin;
			St.Absorbed = 0.f;
			float Grade = 0.f;
			const bool bGrade = GroundGrade(In, Moved, Grade);
			if (bKnown && In.bWanted && SteppedCapsule(Moved, bGrade, Grade))
			{
				const float Rise = Moved.Z;
				const float Taken = Rise / Scale;
				St.Absorbed = Taken;
				St.PelvisZ -= Taken;
				St.FootZ[0] -= Taken;
				St.FootZ[1] -= Taken;
			}
			St.LastOrigin = In.Mesh.Origin;
			St.bKnown = true;
		}

		const float Floor = FMath::Min(Lift[0], Lift[1]);
		float Drop = 0.f;
		for (int S = 0; S < 2; ++S)
		{
			const FFootIn& F = In.Foot[S];
			const FVector Shown = DrawnBall(St.Hold[S], In.Mesh, F.Ball);
			const FVector Offset(Shown.X - F.Ball.X, Shown.Y - F.Ball.Y, 0.f);

			const FFootPlace P = PlaceFoot(F, In.bWanted, Lift[S] - Floor, St.bEdge[S], Size);
			// eased in the world, so a man turned on the spot does not turn his soles
			St.Tilt[S] = SettleNormal(St.Tilt[S], DirToWorld(In.Mesh, P.Tilt), FootSettleRate, Dt);
			const FVector Tilt = DirToMesh(In.Mesh, St.Tilt[S]).GetSafeNormal();
			// no part of the sole under its ground, tilted about the ball as drawn
			const FVector BallSole(F.Ball.X, F.Ball.Y, F.Ball.Z - F.BallRest);
			const FVector HeelSole(F.Ankle.X, F.Ankle.Y, F.Ankle.Z - F.AnkleRest);
			const FVector HeelAfter = BallSole + TurnUpTo(Tilt, HeelSole - BallSole);
			const float BallSoleZ = BallSole.Z, HeelAfterZ = HeelAfter.Z;
			float Z = P.Planted;
			Z = FMath::Max(Z, P.BallFloor - BallSoleZ);
			Z = FMath::Max(Z, P.HeelFloor - HeelAfterZ);
			St.FootZ[S] = Settle(St.FootZ[S], Z, Z > St.FootZ[S] ? FootRiseRate : FootSettleRate, Dt);
			Drop = FMath::Min(Drop, P.Planted);

			FFootPlan& O = Out.Foot[S];
			O.Ball = F.Ball + Offset * A + FVector::UpVector * (A * (St.FootZ[S] + StepHeight(St.Hold[S], Size)));
			O.Tilt = LimitedTilt(Tilt, A);
			O.Ground = P.Ground;
			O.ToeShare = A * GroundShare(Lift[S] - Floor, Size);
			O.Share = A;
		}
		const float PelvisTo = FMath::Max(Drop, -MaxPelvisDrop * Size);
		St.PelvisZ = Settle(St.PelvisZ, PelvisTo, PelvisRate(St.PelvisZ, PelvisTo, FVector(In.Velocity.X, In.Velocity.Y, 0.f).Size()), Dt);

		// The hips carry the body's own starts and stops, on the ground; a
		// curve's sideways change is the lean's (FLean), not an outward throw.
		const FVector Change = DirToMesh(In.Mesh, AlongPath(In.Velocity, St.LastVelocity)) / Scale;
		St.LastVelocity = In.Velocity;
		const float Kick[2] = { static_cast<float>(Change.X), static_cast<float>(Change.Y) };
		for (int K = 0; K < 2; ++K)
		{
			FEase& W = St.Weight[K];
			if (bKnown && In.bWanted) W.V -= Kick[K] * WeightKick;
			W.To(0.f, WeightRate, Dt);
			const float WMax = WeightMaxCm * Size;
			if (FMath::Abs(W.X) > WMax) { W.X = W.X > 0.f ? WMax : -WMax; W.V = 0.f; }
		}
		Out.Pelvis = FVector(St.Weight[0].X, St.Weight[1].X, St.PelvisZ) * A;
		return Out;
	}

	/** Where the toes point: flat on the ground under the ball, as far as
	    toes bend against their foot (a hinge in the foot's own plane), by
	    Share along the arc from where the clip has them. */
	inline FVector ToeOnGround(const FVector& Toe, const FVector& Fwd, const FVector& Up, const FVector& Ground, float Share)
	{
		if (Share <= 0.f) return Toe;
		const float Into = FVector::DotProduct(Toe, Ground);
		FVector Flat = Toe - Ground * Into;
		if (Flat.IsNearlyZero(1e-3f)) return Toe;
		Flat = Flat.GetSafeNormal();
		const float Above = FVector::DotProduct(Flat, Up), Along = FVector::DotProduct(Flat, Fwd);
		const float Bend = FMath::Clamp(FMath::Atan2(Above, Along),
		                                -FMath::DegreesToRadians(ToeDownDegrees), FMath::DegreesToRadians(ToeUpDegrees));
		const FVector Want = (Fwd * FMath::Cos(Bend) + Up * FMath::Sin(Bend)).GetSafeNormal();
		return Swing(Toe, Toe, Want, Share);
	}

	/** One leg's foot, once the hips are where they go. */
	struct FFootPose
	{
		FVector Ankle = FVector::ZeroVector;
		FVector Tilt = FVector::UpVector;
		FVector RollAxis = FVector(0.f, 1.f, 0.f);
		float Roll = 0.f;
		FVector Toe = FVector(1.f, 0.f, 0.f);
	};

	/** The ankle, its sole's tilt, its roll onto the ball and its toes. A
	    held leg too short for its foot rolls the heel up, the ball fixed,
	    as far as the leg needs and no further than MaxHeelRollDegrees; the
	    roll eases in and out, so a foot that steps never drops its heel. */
	inline FFootPose FinishFoot(FFootHold& Hold, const FFootPlan& Plan, const FFootIn& F, const FVector& Hip, float Dt)
	{
		FFootPose P;
		P.Tilt = Plan.Tilt;
		const FVector Back = TurnUpTo(Plan.Tilt, F.Ankle - F.Ball);
		const float Reach = F.LegLength * HoldReach;
		float Need = 0.f;
		if (Hold.Weight > 0.f && FVector::Dist(Plan.Ball + Back, Hip) > Reach)   // held, or handing back
		{
			const FVector Across = FVector::CrossProduct(Back, FVector::UpVector);
			if (!Across.IsNearlyZero(1e-3f))
			{
				const FVector Axis = Across.GetSafeNormal();
				const float Most = FMath::DegreesToRadians(MaxHeelRollDegrees);
				auto Far = [&](float Ang) -> float { return FVector::Dist(Plan.Ball + RotateAbout(Back, Axis, Ang), Hip); };
				if (Far(Most) < Far(0.f))
				{
					float Lo = 0.f, Hi = Most;
					if (Far(Most) <= Reach)
					{
						for (int I = 0; I < 16; ++I)
						{
							const float Mid = 0.5f * (Lo + Hi);
							if (Far(Mid) > Reach) Lo = Mid; else Hi = Mid;
						}
					}
					Need = Hi;
					Hold.RollAxis = Axis;
				}
			}
		}
		Hold.Roll = Settle(Hold.Roll, Need, Need > Hold.Roll ? FootRiseRate : FootSettleRate, Dt);
		P.RollAxis = Hold.RollAxis;
		P.Roll = Hold.Roll * Plan.Share;           // drawn by the feet's share, so it fades with them
		P.Ankle = Plan.Ball + RotateAbout(Back, P.RollAxis, P.Roll);
		const FVector Toe = RotateAbout(TurnUpTo(P.Tilt, F.ToeDir), P.RollAxis, P.Roll);
		const FVector Fwd = RotateAbout(TurnUpTo(P.Tilt, F.FootFwd), P.RollAxis, P.Roll);
		const FVector Up = RotateAbout(TurnUpTo(P.Tilt, F.FootUp), P.RollAxis, P.Roll);
		P.Toe = ToeOnGround(Toe, Fwd, Up, Plan.Ground, Plan.ToeShare);
		return P;
	}

	// ---------------------------------------------------------------- hands

	/** Which limb throws a strike, which point of it lands, and where on the
	    man: motion_hits.py's TIP and TARGET, the table the Blender pairs were
	    placed by. Anything else strikes with nothing and is left to its clip. */
	enum class ELimb : unsigned char { None, Arm, Leg };
	enum class ETip : unsigned char { None, Knuckles, Ball, Knee };
	enum class EMarkBone : unsigned char { Head, Spine02, Spine03 };

	/** How far under its own skin each striking point's joint sits:
	    hand_end is the knuckle joint, ball_ the joint under the ball of the
	    foot, the calf's joint the knee behind its cap. A blow lands the skin
	    on the mark, so the joint stops this much short of it. */
	constexpr float KnuckleSkin = 2.f;
	constexpr float BallSkin = 2.5f;
	constexpr float KneeSkin = 5.f;

	struct FStrike
	{
		ELimb Limb = ELimb::None;
		char Side = 0;                          // 'l' / 'r', the bone suffix
		ETip Tip = ETip::None;                  // hand_end, ball, or the knee (calf's joint)
		EMarkBone Bone = EMarkBone::Head;       // the victim's bone the mark hangs off
		FVector Mark = FVector::ZeroVector;     // cm at Saud's size: forward, right, up of the blow
		float Skin = 0.f;                       // cm at Saud's size
	};

	/** The table. Blender's frame is the man facing -Y with +X his left; here
	    forward is toward the striker, +Y his right, Z up, centimetres:
	    (forward, right, up) = (-y, -x, z) x 100. The Jab is the lead (left)
	    hand, the Cross and Hook the rear (right), the Kick, Knee and Special
	    the rear leg; a punch lands its knuckles (hand_end), a kick the ball of
	    the foot, the knee its knee. Jab and Cross: the chin, 10 cm in front of
	    the head joint (the eye line) and 10 under it. Hook: the point of his
	    left jaw. Kick: his left ribs, under the arm. Knee: the solar plexus.
	    Special: the chest, low. */
	inline FStrike StrikeOf(const char* Row)
	{
		if (!Row) return FStrike();
		auto Is = [Row](const char* S)
		{
			int I = 0;
			while (Row[I] && S[I] && Row[I] == S[I]) ++I;
			return Row[I] == 0 && S[I] == 0;
		};
		if (Is("Jab"))     return {ELimb::Arm, 'l', ETip::Knuckles, EMarkBone::Head, FVector(10.f, 0.f, -10.f), KnuckleSkin};
		if (Is("Cross"))   return {ELimb::Arm, 'r', ETip::Knuckles, EMarkBone::Head, FVector(10.f, 0.f, -10.f), KnuckleSkin};
		if (Is("Hook"))    return {ELimb::Arm, 'r', ETip::Knuckles, EMarkBone::Head, FVector(6.f, -5.f, -9.f), KnuckleSkin};
		if (Is("Kick"))    return {ELimb::Leg, 'r', ETip::Ball, EMarkBone::Spine03, FVector(2.f, -13.f, -6.f), BallSkin};
		if (Is("Knee"))    return {ELimb::Leg, 'r', ETip::Knee, EMarkBone::Spine02, FVector(14.f, 0.f, 2.f), KneeSkin};
		if (Is("Special")) return {ELimb::Leg, 'r', ETip::Ball, EMarkBone::Spine02, FVector(14.f, 0.f, 8.f), BallSkin};
		return FStrike();
	}

	/** How far a blow's joint stops short of its mark, in the units it is
	    measured in, for a man Scale times Saud's size there. */
	inline float SkinOf(const FStrike& K, float Scale)
	{
		return K.Skin * Scale;
	}

	/** The limb alone, as the fire, the motion table and the feet want it. */
	inline ELimb StrikingLimb(const char* AttackRow, char& OutSide)
	{
		const FStrike K = StrikeOf(AttackRow);
		OutSide = K.Side;
		return K.Limb;
	}

	/** How much of the way to the man the striking limb is drawn, over the
	    attack: in over the last LeadIn of the startup, whole on the first
	    active frame, out over ContactLeadOut from there -- the clip's own
	    fist comes back from its contact frame, and is not held on him.
	    bHoldActive keeps it whole to the last active frame: a multi-hit
	    strike, and a guard, which meets every live frame of a blow. Each
	    ramp is a smooth step, so the limb never jerks onto him or off. Zero
	    is the clip alone. */
	constexpr float ContactLeadIn = 0.06f;    // seconds before the first active frame
	constexpr float ContactLeadOut = 0.08f;   // seconds after it lets go
	/** A swing taken away (a blow, a parry) lets go inside three frames:
	    the reel already moves him. */
	constexpr float ContactTakenSeconds = 0.05f;

	inline float ContactAlpha(float Elapsed, float Startup, float Active, float LeadIn = ContactLeadIn, bool bHoldActive = false)
	{
		const float In0 = FMath::Max(0.f, Startup - LeadIn);
		if (Elapsed < In0) return 0.f;
		if (Elapsed < Startup) return SmoothStep((Elapsed - In0) / FMath::Max(1e-3f, Startup - In0));
		const float Out0 = Startup + (bHoldActive ? Active : 0.f);
		if (Elapsed <= Out0) return 1.f;
		return 1.f - SmoothStep((Elapsed - Out0) / ContactLeadOut);
	}

	/** Saud's head joint in the reference pose, cm. The marks were measured on
	    him (motion_hits.py: "the head joint is at the eye line on this
	    skeleton, 1.672 at rest"), so on another man they grow by his head's
	    height over this. */
	constexpr float MarkRestHead = 167.2f;

	/** A man's size against Saud's, from his own reference head height. */
	inline float BodyScale(float RefHeadHeight)
	{
		return RefHeadHeight > 1.f ? RefHeadHeight / MarkRestHead : 1.f;
	}

	/** Where a mark is on a man: off his bone by Offset (forward, right, up;
	    cm at Saud's size) times his Scale, in the frame of the blow --
	    forward is from him toward the striker, on the ground. Facing the
	    striker that is his own frame; struck from behind, the chin's mark is
	    on the back of his head, not round the far side of it. */
	inline FVector MarkPoint(const FVector& Bone, const FVector& Him, const FVector& Striker,
	                         const FVector& Offset, float Scale, const FVector& HisFacing)
	{
		FVector D(Striker.X - Him.X, Striker.Y - Him.Y, 0.f);
		D = D.IsNearlyZero(1e-3f) ? FVector(HisFacing.X, HisFacing.Y, 0.f).GetSafeNormal() : D.GetSafeNormal();
		const FVector Right = FVector::CrossProduct(FVector::UpVector, D);   // X forward, Z up: +Y is his right
		return Bone + (D * Offset.X + Right * Offset.Y + FVector::UpVector * Offset.Z) * Scale;
	}

	/** His belt: where a blow that cannot reach its mark slides down to, the
	    front of his waist off the pelvis (Saud's waist is 0.78 m round, 12 cm
	    from its middle to its front). */
	constexpr float BeltForward = 12.f;

	/** Where a blow lands when its mark is out of reach: as high on him as the
	    limb reaches, on the line down his front from the mark to his belt --
	    a jab at a giant lands on his chest, not in the air under his chin.
	    Reach is from the limb's root. Nothing on the line in reach: the
	    line's point at the height the clip has the tip, which the solve
	    stretches toward -- a kick that cannot land stays a kick to the ribs. */
	inline FVector ReachableMark(const FVector& Root, float Reach, const FVector& Mark, const FVector& Low, float TipZ)
	{
		const FVector M = Mark - Root;
		if (M.SizeSquared() <= Reach * Reach) return Mark;
		const FVector L = Low - Mark;
		const float LL = L.SizeSquared();
		if (LL < 1e-4f) return Mark;
		// |M + s L| = Reach: the smaller root in [0, 1] is where the line comes into reach
		const float B = FVector::DotProduct(M, L);
		const float C = M.SizeSquared() - Reach * Reach;
		const float Disc = B * B - LL * C;
		if (Disc >= 0.f)
		{
			const float S = (-B - FMath::Sqrt(Disc)) / LL;
			if (S >= 0.f && S <= 1.f) return Mark + L * S;
		}
		const float LZ = L.Z, Below = TipZ - Mark.Z;
		const float S = FMath::Abs(LZ) > 1e-3f ? FMath::Clamp(Below / LZ, 0.f, 1.f) : 0.f;
		return Mark + L * S;
	}

	/** How much of its pull a strike takes, by how far the target is off the
	    clip's own line seen from the limb's root: all of it within the full
	    band, none past the none band, a smooth fade between. An arm swung
	    far round its shoulder with the collarbone still reads as a swipe:
	    30 and 55. A leg: the round kick's clip lands 40 degrees to the
	    kicker's left (motion_hits.py), about 45 off a man straight ahead
	    seen from the hip, and he may step 15 more: 60, and 90, past which he
	    is behind the leg's own swing (the spinning kick facing away). */
	constexpr float SwingFullDegreesArm = 30.f;
	constexpr float SwingNoneDegreesArm = 55.f;
	constexpr float SwingFullDegreesLeg = 60.f;
	constexpr float SwingNoneDegreesLeg = 90.f;

	inline float SwingGate(const FVector& Root, const FVector& ClipTip, const FVector& Target, bool bArm)
	{
		const FVector A = (ClipTip - Root).GetSafeNormal(), B = (Target - Root).GetSafeNormal();
		if (A.IsNearlyZero() || B.IsNearlyZero()) return 0.f;
		const float Dot = FVector::DotProduct(A, B);
		const float Deg = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(Dot, -1.f, 1.f)));
		const float Full = bArm ? SwingFullDegreesArm : SwingFullDegreesLeg;
		const float None = bArm ? SwingNoneDegreesArm : SwingNoneDegreesLeg;
		return 1.f - SmoothStep((Deg - Full) / (None - Full));
	}

	/** The gate moves at most its whole way in this long: a round kick's
	    chamber crosses the band in two or three frames, and the pull must
	    not step with it. */
	constexpr float GateSeconds = 0.06f;

	inline float StepGate(float Shown, float Wanted, float Dt)
	{
		const float Most = FMath::Max(0.f, Dt) / GateSeconds;
		return Shown + FMath::Clamp(Wanted - Shown, -Most, Most);
	}

	/** The gate as drawn, across a swing: it steps toward what the swing
	    allows (StepGate), but a swing's first drawn frame starts at what is
	    allowed, so a man the gate shuts out gets no flick toward him while
	    the gate would have been stepping down from 1. */
	struct FGate
	{
		float V = -1.f;     // < 0: no strike drawn last frame
		float Step(float Wanted, float Dt)
		{
			V = V < 0.f ? Wanted : StepGate(V, Wanted, Dt);
			return V;
		}
		void Reset() { V = -1.f; }
	};

	/** A strike's limb put on its target. The lower segment and the end are
	    one piece from the middle joint to the tip -- a fist stays square on
	    its forearm, a foot set on its shin -- so the two-bone solve runs to
	    the TIP: the knuckles, the ball of the foot. The tip swings about the
	    root toward the target by Alpha, on the arc and not the chord, and the
	    bend goes where the clip's bend goes, turned with the swing. Returns
	    where the middle joint and the tip go. */
	inline FTwoBone SolveStrike(const FVector& Root, const FVector& Mid, const FVector& Tip,
	                            const FVector& Target, float Alpha)
	{
		Alpha = FMath::Clamp(Alpha, 0.f, 1.f);
		const FVector From = Tip - Root, To = Target - Root;
		const float Len = FMath::Lerp(From.Size(), To.Size(), Alpha);
		const FVector Dir = Swing(From, From, To, Alpha).GetSafeNormal();
		const FVector Wanted = Root + Dir * Len;
		const FVector Pole = Root + Swing(Mid - Root, From, To, Alpha);
		return TwoBone(Root, Mid, Tip, Wanted, Pole, Alpha);
	}

	/** The knee strike lands the KNEE: the thigh swings about the hip until
	    the knee points at the target, a thigh's length out, and the leg below
	    turns with it as one piece, its bend kept. Alpha of the way, on the
	    arc. Returns where the knee goes. */
	inline FVector KneeSwing(const FVector& Hip, const FVector& Knee, const FVector& Target, float Alpha)
	{
		return Hip + Swing(Knee - Hip, Knee - Hip, Target - Hip, FMath::Clamp(Alpha, 0.f, 1.f));
	}

	/** A blow is met on the side it lands: the striker's left limb arrives on
	    the man's right and his right arm covers it; the striker's right, on
	    his left. */
	inline char CoverSide(char StrikeSide)
	{
		return StrikeSide == 'l' ? 'r' : StrikeSide == 'r' ? 'l' : 0;
	}

	/** Where a guard meets a blow: on the line the blow comes in on, from the
	    root of the striking limb (the shoulder or the hip, which no IK of his
	    moves) to the mark, BlockStandOff out from the mark -- the Block clip
	    holds the wrists 19 cm in front of the head joint
	    (build_motion.BLOCK_FWD), 9 cm before the chin's mark at 10. */
	constexpr float BlockStandOff = 9.f;
	/** How much further out a striking tip stops when the man guards: the
	    covering forearm's face is a few cm in front of its bones, and the
	    knuckle joint a few under its own skin. */
	constexpr float BlockFaceGap = 8.f;
	/** A guard moves a hand's breadth to a blow, not across the body: the
	    glove or the elbow travels at most this. */
	constexpr float BlockMaxShift = 15.f;
	/** The covering glove stops a fist's width from the other: the Block
	    holds the wrists 7.5 cm either side of his middle, and a blow down
	    the middle must not drive one glove into the other. */
	constexpr float BlockFistGap = 9.f;

	/** The point Out cm from the mark toward From, never past From. The
	    guard meets the blow at BlockStandOff; a guarded blow stops at
	    BlockStandOff + BlockFaceGap; a blow's joint stops its skin short. */
	inline FVector MeetPoint(const FVector& Mark, const FVector& From, float Out)
	{
		const FVector D = From - Mark;
		const float L = D.Size();
		return L < 1e-3f ? Mark : Mark + D * (FMath::Min(Out, L) / L);
	}

	/** Where a knee strike aims its joint: the mark -- slid down his front
	    to where the kneecap's skin reaches, a thigh and a Skin from the hip
	    -- brought Skin back toward the hip, so the joint stops Skin short
	    and the skin lands on it. Past reach, the joint goes his way as far
	    as the thigh does. */
	inline FVector KneeAim(const FVector& Hip, const FVector& Knee, const FVector& Mark, const FVector& Low, float Skin)
	{
		const float Thigh = static_cast<float>(FVector::Dist(Hip, Knee));
		const FVector M = ReachableMark(Hip, Thigh + Skin, Mark, Low, static_cast<float>(Knee.Z));
		return MeetPoint(M, Hip, Skin);
	}

	/** The covering arm moved to a blow, Alpha of the way. A head blow
	    (bHigh): the glove slides across toward the meeting point at the
	    height the clip holds it -- the Block's forearm already stands in
	    front of the face -- at most BlockMaxShift and never within
	    BlockFistGap of the other glove, the elbow bending where it bent. A
	    body blow: the fist stays where the clip has it and the elbow swings
	    on its circle about the shoulder-to-fist line toward the meeting
	    point, at most a BlockMaxShift chord. Up is the world's up in the
	    pose's space. Returns where the elbow and the hand go. */
	inline FTwoBone Cover(const FVector& Shoulder, const FVector& Elbow, const FVector& Hand, const FVector& Meet,
	                      bool bHigh, float Alpha, const FVector& Up, const FVector& OtherHand, float Scale)
	{
		Alpha = FMath::Clamp(Alpha, 0.f, 1.f);
		if (bHigh)
		{
			FVector Move = Meet - Hand;
			const float Rise = FVector::DotProduct(Move, Up);
			Move = Move - Up * Rise;
			const float L = Move.Size();
			if (L > BlockMaxShift) Move = Move * (BlockMaxShift / L);
			// never onto the other glove: the most of the move that keeps a fist's width
			auto Clear = [&](float S) -> bool
			{
				FVector Gap = Hand + Move * S - OtherHand;
				const float GapUp = FVector::DotProduct(Gap, Up);
				Gap = Gap - Up * GapUp;
				return Gap.Size() >= BlockFistGap * Scale;
			};
			if (!Clear(1.f))
			{
				float Lo = 0.f, Hi = 1.f;
				if (!Clear(0.f)) Hi = 0.f;
				else for (int I = 0; I < 16; ++I) { const float Mid = 0.5f * (Lo + Hi); if (Clear(Mid)) Lo = Mid; else Hi = Mid; }
				Move = Move * Lo;
			}
			return TwoBone(Shoulder, Elbow, Hand, Hand + Move * Alpha, Elbow, Alpha);
		}
		// the elbow turns on its circle about the shoulder-to-fist line, toward
		// where the meeting point would have it, by at most a BlockMaxShift chord
		FTwoBone Out;
		Out.Mid = Elbow;
		Out.End = Hand;
		const FVector N = (Hand - Shoulder).GetSafeNormal();
		const float ElbowAlong = FVector::DotProduct(Elbow - Shoulder, N);
		const FVector C = Shoulder + N * ElbowAlong;
		const FVector U = Elbow - C;
		const float R = U.Size();
		const FTwoBone Full = TwoBone(Shoulder, Elbow, Hand, Hand, Meet);
		const float FullAlong = FVector::DotProduct(Full.Mid - C, N);
		const FVector W = (Full.Mid - C) - N * FullAlong;
		if (R < 1e-3f || W.IsNearlyZero(1e-3f)) return Out;
		const float Cos = FVector::DotProduct(U, W) / (R * W.Size());
		const float Side = FVector::DotProduct(FVector::CrossProduct(U, W), N);
		const float Turn = FMath::Acos(FMath::Clamp(Cos, -1.f, 1.f)) * (Side < 0.f ? -1.f : 1.f);
		if (FMath::Abs(Turn) < 1e-4f) return Out;
		const float Half = FMath::Min(1.f, BlockMaxShift / (2.f * R));      // sin of half the most it may turn
		const float Most = 2.f * FMath::Atan2(Half, FMath::Sqrt(1.f - Half * Half));
		const float Took = FMath::Clamp(Turn, -Most, Most);
		Out.Mid = C + RotateAbout(U, N, Took * Alpha);
		return Out;
	}

	/** A guard fist goes where the face goes. The clip holds it by the chin;
	    the chest's turn carries it by the skeleton; what the neck and head
	    turn beyond the chest carries it the rest, about the neck and about
	    up only -- a look down never lowers the guard -- at most
	    GuardMaxShift, the rear fist's travel when the head turns 28 degrees
	    past the chest, so a look far round does not drag the arm across the
	    face. Share is how much of the turn the knuckles take: as much as the
	    fist was carried of the whole way. */
	constexpr float GuardMaxShift = 12.f;

	struct FCarry
	{
		FVector Fist = FVector::ZeroVector;
		float Share = 1.f;
	};

	inline FCarry Carry(const FVector& Fist, const FVector& Pivot, const FVector& Up, float YawDegrees)
	{
		FCarry C;
		const FVector Move = Pivot + RotateAbout(Fist - Pivot, Up, FMath::DegreesToRadians(YawDegrees)) - Fist;
		const float L = Move.Size();
		const float Keep = L > GuardMaxShift ? GuardMaxShift / L : 1.f;
		C.Fist = Fist + Move * Keep;
		C.Share = Keep;
		return C;
	}

	/** A strike's box is taken this much longer than it is -- by the strike's
	    own pull, by a guard and by the look -- so each starts before the
	    blow resolves and on a man stepping in over the lead-in. */
	constexpr float BoxSlack = 40.f;

	/** Whether a man stands where a blow can reach him, or soon will: the
	    sweep's own box (SaudArena::InHitbox), BoxSlack longer. */
	inline bool InBlowBox(const FVector& Striker, const FVector& Facing, const FVector& Him, float Reach, float Lateral)
	{
		return SaudArena::InHitbox(Striker, Facing, Him, Reach + BoxSlack, Lateral);
	}

	/** One swing's hold on one man, frame to frame. A new swing is a frame
	    with a swing after one with none, another row, or the clock run back;
	    its man is found from the lead-in and kept, never replaced. From the
	    first active frame the blow has landed: its mark is held where it was
	    in the striker's own frame, so the fist follows his lunge and not the
	    man thrown clear. A man lost before that is let go and nobody is taken
	    in his place. A swing taken away lets go in ContactTakenSeconds. */
	struct FStrikeTrack
	{
		FRamp Hold;
		float Schedule = 0.f;     // the swing's ContactAlpha, kept when the swing is taken away
		int Row = -1;             // the swing's row, -1 between swings
		float Clock = 0.f;
		bool bHeld = false;       // a man was found this swing
		bool bLanded = false;     // past its first active frame
		bool bTaken = false;      // ended before its recovery did: let go fast
		bool bSpent = false;      // its man was lost: nobody else this swing

		bool NewSwing(bool bLive, int InRow, float InClock) const
		{
			return bLive && (Row < 0 || InRow != Row || InClock < Clock);
		}
		/** bLive: an attack with a striking limb; bHave: a man to draw to
		    this frame; bLost: the held man left the box, cannot be struck,
		    or is gone. */
		void Step(bool bLive, int InRow, float InClock, float Startup, float Active, bool bMultiHit,
		          bool bHave, bool bLost, float Dt)
		{
			if (NewSwing(bLive, InRow, InClock)) *this = FStrikeTrack();
			if (bLive)
			{
				Row = InRow;
				Clock = InClock;
				Schedule = ContactAlpha(InClock, Startup, Active, ContactLeadIn, bMultiHit);
				if (InClock >= Startup) bLanded = true;
			}
			else
			{
				bTaken = bTaken || Row >= 0;
				Row = -1;
			}
			if (bLost && !bLanded) { bSpent = true; bHeld = false; }
			if (bHave && !bSpent) bHeld = true;
			Hold.Step(bLive && bHeld && !bSpent, Dt, ContactLeadIn, bTaken ? ContactTakenSeconds : ContactLeadOut);
		}
		/** The mark may still be read off the man: not landed, not taken. */
		bool FreshMark() const { return !bLanded && !bTaken; }
		float Alpha() const { return Schedule * Hold.Value(); }
	};

	/** The blow a guard holds, frame to frame: one at a time, the next
	    taken as soon as nothing of the last shows -- a guard meets the
	    second blow of a combo, not only the first. */
	struct FBlockTrack
	{
		FRamp Hold;
		float Schedule = 0.f;
		/** Nothing of the last blow shows: the next may be taken now. */
		bool Free() const { return Schedule * Hold.Value() <= 0.f; }
		/** Takes a new blow at schedule S; caught mid-swing, the guard eases
		    in from nothing. */
		void Take(float S)
		{
			Schedule = S;
			if (S > 0.f) Hold = FRamp();
		}
		/** bHolding: a blow is held this frame, at schedule S; none: the last
		    one's schedule stays and the guard lets go of it. */
		void Step(bool bHolding, float S, float Dt)
		{
			if (bHolding) Schedule = S;
			Hold.Step(bHolding, Dt, ContactLeadIn, ContactLeadOut);
		}
		float Alpha() const { return Schedule * Hold.Value(); }
	};

	// ------------------------------------------------------- body and look

	/** What a trunk and a neck do. Past the yaw limit the face holds the
	    limit rather than turning away from the fight: it is about all the
	    trunk's 35 degrees and the neck's 75 give together. Past the reach
	    the fighter looks where he faces. */
	constexpr float LookMaxYawDegrees = 100.f;
	constexpr float LookMaxPitchDegrees = 30.f;
	constexpr float LookReach = 900.f;         // cm; further than this is not a fight

	/** The bones the look turns, root first: spine_01, spine_02, spine_03,
	    neck_01, head. The hips are not one: their lag turns the root. */
	constexpr int ChainBones = 5;

	/** How far the trunk twists over the hips (thoracic and lumbar rotation,
	    about 35 degrees each way) and the neck and head over the chest
	    (cervical, about 75). */
	constexpr float SpineYawLimit = 35.f;
	constexpr float NeckYawLimit = 75.f;

	/** Each trunk bone's share of the trunk's twist: the lumbar turns
	    little, the upper thoracic most. */
	inline constexpr float SpineShare[3] = {0.20f, 0.35f, 0.45f};

	/** The neck takes this share of the neck-and-head turn, the head the rest. */
	constexpr float NeckShare = 0.35f;

	/** Each of the five's share of the look's pitch, root first: the face
	    does most of a nod, the chest a little, the lumbar none. */
	inline constexpr float PitchShare[ChainBones] = {0.f, 0.05f, 0.10f, 0.35f, 0.50f};

	/** Of a look to the side the chest turns this share, the neck and head
	    the rest: a fighter keeps his shoulders to the fight and turns his
	    face to the man beside him. */
	constexpr float ChestLookShare = 0.35f;

	/** How fast each part comes round, per second, exponential, and never
	    faster than its cap in degrees a second: the face first, the chest
	    after it, the hips last, the order a man turns in. The hips' cap is
	    the 1080 degrees a second CharacterMovement's RotationRate names; at
	    60 Hz no frame turns the hips over 18, the chest 24, the face 30. */
	constexpr float HipsRate = 16.f;
	constexpr float ChestRate = 22.f;
	constexpr float HeadRate = 30.f;
	constexpr float HipsMaxTurn = 1080.f;
	constexpr float ChestMaxTurn = 1440.f;
	constexpr float HeadMaxTurn = 1800.f;

	/** In a strike all three come round this much faster, rates and caps,
	    and the chest goes with the hips: the blow is driven from the hips,
	    a jab is live 70 ms after it starts, and the clip already twists the
	    trunk (a cross 60 degrees). */
	constexpr float StrikeQuicken = 3.f;

	/** The look eases on over about a third of a second; a man knocked down
	    gives it up in 0.06 s. */
	constexpr float LookOnSeconds = 0.30f;
	constexpr float LookOffSeconds = 0.06f;

	/** A residual pushed past a half turn keeps going the way it was going,
	    up to this: wrapped at 180, a second snap the same way would reverse
	    a body mid-turn and swing the face back 58 degrees in a frame. */
	constexpr float HipsKeepWay = 270.f;

	/** A capsule that moves this far in one frame was put there -- a door,
	    a respawn -- not walked: the body starts square to its new facing.
	    A dash is 1150-1500 cm/s, 115-150 cm a frame at 10 frames a second. */
	constexpr float TeleportCm = 250.f;

	/** Whether the capsule was put somewhere rather than moved there. */
	inline bool Teleported(const FVector& From, const FVector& To)
	{
		const float X = To.X - From.X, Y = To.Y - From.Y;
		return X * X + Y * Y > TeleportCm * TeleportCm;
	}

	/** Settle, but never faster than MaxDegPerSec: an exponential's first
	    frame is its fastest, and a half turn at 30/s is 70 degrees of it. */
	inline float SettleCapped(float Current, float Target, float Rate, float MaxDegPerSec, float Dt)
	{
		const float Step = (Target - Current) * (1.f - FMath::Exp(-Rate * Dt));
		const float Cap = MaxDegPerSec * FMath::Max(0.f, Dt);
		return Current + FMath::Clamp(Step, -Cap, Cap);
	}

	/** Past what the face can turn to, a man is held over the shoulder the
	    face is already over; the side changes only when he comes within
	    the limit on the other side. A man straight behind is on neither
	    side, and a centimetre of his sway must not swing the face 200
	    degrees across the front. */
	inline float HoldSide(float Raw, float& Side)
	{
		if (Raw * Side < 0.f && FMath::Abs(Raw) > LookMaxYawDegrees) return Side * LookMaxYawDegrees;
		Side = Raw >= 0.f ? 1.f : -1.f;
		return FMath::Clamp(Raw, -LookMaxYawDegrees, LookMaxYawDegrees);
	}

	/** How the body is turned, kept frame to frame on the anim instance.
	    Degrees, + the way FQuat turns +X toward +Y about +Z. Hips is off the
	    actor's yaw; Chest and Head are off the hips, so a snapped yaw
	    leaves them where they are in the world. */
	struct FTurn
	{
		float Hips = 0.f;      // the root: behind a snapped facing, and coming round
		float Chest = 0.f;     // the chest's twist over the hips, before the trunk's limit
		float Head = 0.f;      // the face's turn over the hips, before the neck's limit
		float Pitch = 0.f;     // the face's pitch, + up
		float Side = 1.f;      // the shoulder a man past the limit is held over
		FRamp Weight;          // how much of the chest's and face's turn shows: 0 the clip's own
		// a turn clip carrying the turn (TurnStep's TurnClip): the lag it found
		// and how far the clip has come in, never back
		bool bClip = false;
		float ClipHips = 0.f;
		float ClipShare = 0.f;
	};

	/** One frame. Turned: how far the actor's yaw moved since the last frame.
	    RawYaw, LookPitch: where the face should go, off the facing
	    (LookAngles; 0, 0 with nobody to look at). bMayLook: he looks at the
	    man (not reeling); bLying: down or dead -- the lag holds, the chain
	    lets go. The hips go round the short way and drag the chest and face
	    with them; each then comes on toward its own aim, off the facing, at
	    its own rate. */
	/** TurnClip: a turn or a pivot clip (Turn_L90 ... Pivot_180) is the
	    newest clip, at this crossfade weight; -1 when none is. Such a clip
	    carries the turn itself -- its first frame is the body turned back
	    where it stood -- so the hips' lag must not turn the body a second
	    time: as the clip comes in the lag goes out with it (the drawn body
	    stays where it stood through the cut), and it is held at zero for as
	    long as the clip is the newest. (2026-10-04) */
	inline void TurnStep(FTurn& S, float Turned, float RawYaw, float LookPitch,
	                     bool bMayLook, bool bLying, bool bStriking, bool bTeleported, float Dt, float TurnClip = -1.f)
	{
		if (bTeleported)
		{
			const FRamp Keep = S.Weight;
			S = FTurn();
			S.Weight = Keep;
		}
		else
		{
			float H = S.Hips - WrapDegrees(Turned);
			if (!(H > -1e6f && H < 1e6f)) H = 0.f;
			if (H > HipsKeepWay) H -= 360.f;
			else if (H < -HipsKeepWay) H += 360.f;
			S.Hips = H;
		}
		const float Q = bStriking ? StrikeQuicken : 1.f;
		if (TurnClip >= 0.f && !bTeleported)
		{
			if (!S.bClip) { S.bClip = true; S.ClipHips = S.Hips; S.ClipShare = 0.f; }
			else S.ClipHips -= WrapDegrees(Turned);
			S.ClipShare = FMath::Max(S.ClipShare, FMath::Min(TurnClip, 1.f));
		}
		else S.bClip = false;
		const float Hips = S.Hips;
		// a turn clip: the lag out as the clip comes in, then held at none
		if (S.bClip) S.Hips = S.ClipHips * (1.f - S.ClipShare);
		// on the floor the body lies where it fell; it comes round as he gets up
		else if (!bLying) S.Hips = SettleCapped(Hips, 0.f, HipsRate * Q, HipsMaxTurn * Q, Dt);
		// reeling, the face is the blow's: no look, but the body still comes round to its facing
		const float Yaw = bMayLook ? HoldSide(RawYaw, S.Side) : 0.f;
		const float Pitch = bMayLook ? LookPitch : 0.f;
		const float ChestR = bStriking ? HipsRate : ChestRate;
		const float ChestCap = bStriking ? HipsMaxTurn : ChestMaxTurn;
		S.Chest = SettleCapped(Hips + S.Chest, ChestLookShare * Yaw, ChestR * Q, ChestCap * Q, Dt) - S.Hips;
		S.Head = SettleCapped(Hips + S.Head, Yaw, HeadRate * Q, HeadMaxTurn * Q, Dt) - S.Hips;
		S.Pitch = Settle(S.Pitch, Pitch, HeadRate * Q, Dt);
		S.Weight.Step(!bLying, Dt, LookOnSeconds, LookOffSeconds);
	}

	/** The turn each bone makes, degrees: the root's yaw about up, then the
	    five's yaw about up and pitch about their own level axis, weighted.
	    Summed, the chest ends at the hips plus the trunk's twist and the
	    face at the look, as far as the trunk's and the neck's limits let
	    them. */
	struct FChainTurn
	{
		float Hips = 0.f;
		float Yaw[ChainBones] = {0.f, 0.f, 0.f, 0.f, 0.f};
		float Pitch[ChainBones] = {0.f, 0.f, 0.f, 0.f, 0.f};
	};

	inline FChainTurn ShareTurn(const FTurn& S)
	{
		FChainTurn T;
		T.Hips = S.Hips;
		const float W = S.Weight.Value();
		const float Trunk = FMath::Clamp(S.Chest, -SpineYawLimit, SpineYawLimit);
		const float Neck = FMath::Clamp(S.Head - Trunk, -NeckYawLimit, NeckYawLimit);
		for (int I = 0; I < 3; ++I) T.Yaw[I] = W * SpineShare[I] * Trunk;
		T.Yaw[3] = W * NeckShare * Neck;
		T.Yaw[4] = W * (1.f - NeckShare) * Neck;
		for (int I = 0; I < ChainBones; ++I) T.Pitch[I] = W * PitchShare[I] * S.Pitch;
		return T;
	}

	/** Each of the five's pitch axis: level, square to the way that bone
	    faces once the hips and the bones under it have turned, so a nod
	    raises the face and never rolls it. Forward (level) and Up in the
	    space the pose is in. A positive pitch about it raises the face. */
	inline void PitchAxes(const FChainTurn& T, const FVector& Forward, const FVector& Up, FVector Out[ChainBones])
	{
		float Cum = T.Hips;
		for (int I = 0; I < ChainBones; ++I)
		{
			Cum += T.Yaw[I];
			const FVector Dir = RotateAbout(Forward, Up, FMath::DegreesToRadians(Cum));
			Out[I] = FVector::CrossProduct(Dir, Up).GetSafeNormal();
		}
	}

	/** Where the face should turn, off the body's facing. The yaw is the
	    flat line between the two men's middles, which collision keeps two
	    radii apart -- his head a hand off my eyes would make it anything --
	    raw, on (-180, 180]; HoldSide clamps it. The pitch is from my eyes to
	    his (the head joint is the eye line on this skeleton), clamped.
	    Degrees; yaw + toward +Y of +X. Zero, zero when there is no way to
	    tell. */
	inline void LookAngles(const FVector& MyCentre, const FVector& Eyes, const FVector& Facing,
	                       const FVector& HisCentre, const FVector& HisEyes, float& OutRawYaw, float& OutPitch)
	{
		OutRawYaw = 0.f;
		OutPitch = 0.f;
		const FVector F = FVector(Facing.X, Facing.Y, 0.f).GetSafeNormal();
		const FVector Flat(HisCentre.X - MyCentre.X, HisCentre.Y - MyCentre.Y, 0.f);
		if (F.IsNearlyZero() || Flat.IsNearlyZero(1e-3f)) return;
		const FVector Side = FVector::CrossProduct(FVector::UpVector, F);   // +Y of +X
		const float Fwd = FVector::DotProduct(Flat, F);
		const float Across = FVector::DotProduct(Flat, Side);
		OutRawYaw = FMath::RadiansToDegrees(FMath::Atan2(Across, Fwd));
		const FVector To = HisEyes - Eyes;
		const float Run = FVector(To.X, To.Y, 0.f).Size();
		const float Rise = To.Z;
		OutPitch = FMath::Clamp(FMath::RadiansToDegrees(FMath::Atan2(Rise, FMath::Max(1e-3f, Run))),
		                        -LookMaxPitchDegrees, LookMaxPitchDegrees);
	}

	/** Who a fighter looks at. The man my own strike is drawn to first; then
	    a man whose strike is in its wind-up or live with me in its box (and
	    the man already looked at for that, while his swing lasts, though
	    its box's edge flickers across me); then the nearest, a man behind
	    counting as further than one in front. The man looked at last frame
	    keeps the look until another is clearly better, so two men at one
	    distance do not trade it. */
	struct FLookCandidate
	{
		FVector Centre = FVector::ZeroVector;   // his capsule's middle
		bool bVictim = false;    // the man my own strike is drawn to
		bool bThreat = false;    // his strike, winding up or live, has me in its box
		bool bWasThreat = false; // looked at last frame as a threat, his swing still on
		bool bCurrent = false;   // the man looked at last frame
	};

	/** The man already looked at keeps the look until another is a quarter
	    nearer, by the cost below. */
	constexpr float LookKeepShare = 0.75f;

	/** How much further a man counts for being off the facing: one straight
	    behind counts double, one square to the side half again. */
	constexpr float LookFrontWeight = 1.f;

	/** A strike threatens from its first frame to its last live one: in its
	    wind-up or live, never in its recovery. */
	inline bool Threatens(float Elapsed, float Startup, float Active)
	{
		return Elapsed >= 0.f && Elapsed < Startup + Active;
	}

	/** The index of the man to look at, or -1 for nobody in reach. */
	inline int ChooseLook(const FLookCandidate* C, int N, const FVector& Me, const FVector& Facing)
	{
		const FVector F = FVector(Facing.X, Facing.Y, 0.f).GetSafeNormal();
		int Best = -1, BestTier = -1;
		float BestCost = 0.f;
		for (int I = 0; I < N; ++I)
		{
			const FVector To(C[I].Centre.X - Me.X, C[I].Centre.Y - Me.Y, 0.f);
			const float Dist = To.Size();
			if (Dist > LookReach) continue;
			const bool bSwinging = C[I].bThreat || C[I].bWasThreat;
			const int Tier = C[I].bVictim ? 2 : bSwinging ? 1 : 0;
			const float Cos = Dist > 1e-3f ? FVector::DotProduct(To, F) / Dist : 1.f;
			float Cost = Dist * (1.f + LookFrontWeight * 0.5f * (1.f - Cos));
			if (C[I].bCurrent) Cost *= LookKeepShare;
			if (Tier > BestTier || (Tier == BestTier && Cost < BestCost))
			{
				Best = I;
				BestTier = Tier;
				BestCost = Cost;
			}
		}
		return Best;
	}

	// ------------------------------------------------------ clips, crossfaded

	/** How many clips may sound at once: the one coming in, the one it
	    replaces, and two still going out -- a diagonal walk flicking
	    between two clips under a blow. A fifth inside one cut drops the
	    lightest, the only way a weight ever jumps. */
	constexpr int MaxLayers = 4;

	/** One clip in the mix. Clip is the engine's own number for it; Length
	    in seconds. From is its weight when the running cut began. */
	struct FLayer
	{
		int Clip = -1;
		float Time = 0.f;
		float Length = 0.f;
		bool bLoop = false;
		float Weight = 0.f;
		float From = 0.f;
	};

	/** The clips a fighter shows, newest first, the weights summing to one.
	    A new clip comes in over the cut's seconds on a smooth step;
	    everything else goes out in proportion to what it had, each still
	    playing at its own time -- a loop runs on, a one-shot holds its last
	    frame. A clip still going out that is asked for again comes back
	    from where it is, at its own time and weight. Serial moves whenever
	    the newest clip is new or started again. */
	struct FCrossfade
	{
		FLayer Layers[MaxLayers];
		int Num = 0;
		float Seconds = 0.f;     // the running cut's length
		float Elapsed = 0.f;
		int Serial = 0;

		void Play(int Clip, float Length, bool bLoop, bool bRestart, float CutSeconds, bool bMatchPhase)
		{
			if (Num > 0 && Layers[0].Clip == Clip && !bRestart)
			{
				Layers[0].bLoop = bLoop;
				return;
			}
			++Serial;
			for (int I = 0; I < Num; ++I) Layers[I].From = Layers[I].Weight;

			FLayer In;
			int Found = -1;
			for (int I = 1; I < Num && !bRestart; ++I)
			{
				if (Layers[I].Clip == Clip) { Found = I; break; }
			}
			if (Found >= 0)
			{
				In = Layers[Found];
				In.bLoop = bLoop;
				Remove(Found);
			}
			else
			{
				In.Clip = Clip;
				In.Length = Length;
				In.bLoop = bLoop;
				// A walk into a walk keeps the stride: the same share of the cycle.
				if (bMatchPhase && bLoop && Num > 0 && Layers[0].bLoop && Layers[0].Length > 0.f)
				{
					In.Time = Length * (Layers[0].Time / Layers[0].Length);
				}
				if (Num == MaxLayers) DropLightest();
			}
			for (int I = Num; I > 0; --I) Layers[I] = Layers[I - 1];
			Layers[0] = In;
			++Num;
			Seconds = CutSeconds;
			Elapsed = 0.f;
			if (Seconds <= 0.f || Num == 1) Settle();
		}

		/** Dt is the world's: a freeze holds every clip and every cut. Rate
		    runs the newest clip's clock alone (a walk kept to the ground). */
		void Advance(float Dt, float Rate = 1.f)
		{
			Dt = FMath::Max(0.f, Dt);
			for (int I = 0; I < Num; ++I)
			{
				FLayer& L = Layers[I];
				L.Time += I == 0 ? Dt * Rate : Dt;
				if (L.Length > 0.f)
				{
					L.Time = L.bLoop ? FMath::Fmod(L.Time, L.Length) : FMath::Min(L.Time, L.Length);
				}
			}
			if (Num <= 1)
			{
				if (Num == 1) Layers[0].Weight = Layers[0].From = 1.f;
				return;
			}
			Elapsed += Dt;
			const float S = SmoothStep(Seconds > 0.f ? Elapsed / Seconds : 1.f);
			Layers[0].Weight = Layers[0].From + (1.f - Layers[0].From) * S;
			for (int I = 1; I < Num; ++I) Layers[I].Weight = Layers[I].From * (1.f - S);
			if (S >= 1.f) Settle();
		}

	private:
		void Settle()
		{
			Num = Num > 0 ? 1 : 0;
			if (Num) Layers[0].Weight = Layers[0].From = 1.f;
		}

		void Remove(int At)
		{
			for (int I = At; I < Num - 1; ++I) Layers[I] = Layers[I + 1];
			--Num;
		}

		void DropLightest()
		{
			int Min = 0;
			for (int I = 1; I < Num; ++I) if (Layers[I].Weight < Layers[Min].Weight) Min = I;
			const float Rest = 1.f - Layers[Min].Weight;
			Remove(Min);
			if (Rest <= 1e-6f) return;
			for (int I = 0; I < Num; ++I) { Layers[I].Weight /= Rest; Layers[I].From /= Rest; }
		}
	};

	/** The proxy lays the clips oldest first, each newer one over the mix
	    under it by this share of the two -- so every clip ends up at
	    exactly its own weight, and the newest's share is its weight. */
	inline float FoldShare(float Under, float Weight)
	{
		const float Sum = Under + Weight;
		return Sum > 1e-6f ? Weight / Sum : 0.f;
	}

	// ---------------------------------------------------- the clips' plants

	/** Whether a measured clip has a foot on the floor -- on its ball or
	    flat -- at a time: the frame nearest the time (SaudPlants::Fps), a
	    loop wrapping round, a one-shot holding its ends. Foot 0 left, 1 right. */
	inline bool ClipFootDown(const SaudPlants::FClip& C, int Foot, float Time, bool bLoop)
	{
		if (C.Frames <= 0) return false;
		int F = static_cast<int>(FMath::Max(0.f, Time) * SaudPlants::Fps + 0.5f);
		F = bLoop ? F % C.Frames : (F < C.Frames ? F : C.Frames - 1);
		return C.Foot[Foot][F] != '.';
	}

	/** How much of the mix has each foot down, by the measured plants of the
	    clips in it and their weights. Plants: for each engine clip number,
	    its measured plants or null. Where less than half the mix is
	    measured, both are -1 and the heights decide (StepHolds). */
	inline void MixDown(const FCrossfade& Mix, const SaudPlants::FClip* const* Plants, int NumPlants, float (&Out)[2])
	{
		float Known = 0.f;
		float Down[2] = { 0.f, 0.f };
		for (int I = 0; I < Mix.Num; ++I)
		{
			const FLayer& L = Mix.Layers[I];
			const SaudPlants::FClip* P = L.Clip >= 0 && L.Clip < NumPlants ? Plants[L.Clip] : nullptr;
			if (!P) continue;
			Known += L.Weight;
			for (int S = 0; S < 2; ++S)
			{
				if (ClipFootDown(*P, S, L.Time, L.bLoop)) Down[S] += L.Weight;
			}
		}
		for (int S = 0; S < 2; ++S)
		{
			Out[S] = Known >= 0.5f ? Down[S] / Known : -1.f;
		}
	}

	// ------------------------------------------------- 360: lean, traces, stops

	/** The body leans into a turn as a runner does (2026-10-04): the pelvis
	    and the chain over it tilt toward the turn's centre by
	    atan(v * yawrate / g) -- the angle at which the ground's push and his
	    weight make the curve -- no further than LeanWalkMaxDeg at his walk
	    tier's pace and under, LeanRunMaxDeg at his run, straight between; a
	    start tips it forward and a stop back, atan(dv/dt / g), to
	    LeanPitchMaxDeg; all of it eased (LeanOmega, a critically damped
	    spring: 95 % in 0.47 s), and held in the world's directions, so a
	    body coming round under it does not swing it -- carried round with
	    his way as it turns (CarryLean), so a steady curve's lean is whole
	    and square to it, not trailing the turn. */
	constexpr float Gravity = 980.f;               // cm/s^2
	constexpr float LeanWalkMaxDeg = 12.f;
	constexpr float LeanRunMaxDeg = 20.f;
	constexpr float LeanPitchMaxDeg = 6.f;
	constexpr float LeanOmega = 10.f;
	/** Under this he is standing: no curve is read from a heading that
	    turns while he barely moves (SaudFeel::WalkThreshold). */
	constexpr float LeanMinSpeed = 40.f;

	struct FLean
	{
		FEase Tilt[2];                         // world X and Y of the tilt, degrees toward that way
		FVector LastVelocity = FVector::ZeroVector;
		bool bKnown = false;
	};

	/** How far he may lean into a curve at a speed: WalkSpeed is his walk
	    tier's (SaudSteer::WalkShare of his run), RunSpeed his run's. */
	inline float LeanLimit(float Speed, float WalkSpeed, float RunSpeed)
	{
		const float Span = RunSpeed - WalkSpeed;
		const float T = Span > 1.f ? FMath::Clamp((Speed - WalkSpeed) / Span, 0.f, 1.f) : 1.f;
		return LeanWalkMaxDeg + (LeanRunMaxDeg - LeanWalkMaxDeg) * T;
	}

	/** The lean he is asked for this frame, world, degrees: toward the
	    curve's centre by its turn, along his way by his change of speed. */
	inline FVector LeanWanted(const FVector& Velocity, const FVector& Last, float WalkSpeed, float RunSpeed, float Dt)
	{
		const FVector V(Velocity.X, Velocity.Y, 0.f), L(Last.X, Last.Y, 0.f);
		const float Sp = static_cast<float>(V.Size()), Sl = static_cast<float>(L.Size());
		FVector Out = FVector::ZeroVector;
		if (Dt <= 1e-5f) return Out;
		if (Sp > LeanMinSpeed && Sl > LeanMinSpeed)
		{
			const FVector A = L / Sl, B = V / Sp;
			const float Turn = FMath::Atan2(static_cast<float>(A.X * B.Y - A.Y * B.X), static_cast<float>(A.X * B.X + A.Y * B.Y));
			const float YawRate = Turn / Dt;                                   // rad/s, + toward his left of the way
			const float Roll = FMath::Min(FMath::RadiansToDegrees(FMath::Atan(Sp * FMath::Abs(YawRate) / Gravity)),
			                              LeanLimit(Sp, WalkSpeed, RunSpeed));
			const FVector Centre = FVector::CrossProduct(FVector::UpVector, B) * (YawRate >= 0.f ? 1.0 : -1.0);
			Out += Centre * Roll;
		}
		const FVector Way = Sp > 1.f ? V / Sp : (Sl > 1.f ? L / Sl : FVector::ZeroVector);
		const float Pitch = FMath::Clamp(FMath::RadiansToDegrees(FMath::Atan((Sp - Sl) / Dt / Gravity)), -LeanPitchMaxDeg, LeanPitchMaxDeg);
		Out += Way * Pitch;
		return Out;
	}

	/** The eased lean carried round by the turn of his way this frame
	    (radians, + toward his left), its speed too: a curve's lean turns with
	    the curve. Under LeanMinSpeed his way has no turn to carry. */
	inline void CarryLean(FLean& S, const FVector& Velocity)
	{
		const FVector V(Velocity.X, Velocity.Y, 0.f), L(S.LastVelocity.X, S.LastVelocity.Y, 0.f);
		if (!S.bKnown || V.Size() <= LeanMinSpeed || L.Size() <= LeanMinSpeed) return;
		const float Turn = FMath::Atan2(static_cast<float>(L.X * V.Y - L.Y * V.X), static_cast<float>(L.X * V.X + L.Y * V.Y));
		const float C = FMath::Cos(Turn), Sn = FMath::Sin(Turn);
		const float X = S.Tilt[0].X, Y = S.Tilt[1].X, VX = S.Tilt[0].V, VY = S.Tilt[1].V;
		S.Tilt[0].X = X * C - Y * Sn; S.Tilt[1].X = X * Sn + Y * C;
		S.Tilt[0].V = VX * C - VY * Sn; S.Tilt[1].V = VX * Sn + VY * C;
	}

	/** One frame of the lean; bOn: on the ground and standing up (the
	    feet's), else it eases out. A Dt of 0 (the freeze) holds it. */
	inline void StepLean(FLean& S, const FVector& Velocity, float WalkSpeed, float RunSpeed, bool bOn, float Dt, bool bTeleported = false)
	{
		if (bTeleported) { const FLean Keep = S; S = FLean(); S.Tilt[0] = Keep.Tilt[0]; S.Tilt[1] = Keep.Tilt[1]; }
		if (Dt <= 0.f) return;
		CarryLean(S, Velocity);
		const FVector Want = bOn && S.bKnown ? LeanWanted(Velocity, S.LastVelocity, WalkSpeed, RunSpeed, Dt) : FVector::ZeroVector;
		S.Tilt[0].To(static_cast<float>(Want.X), LeanOmega, Dt);
		S.Tilt[1].To(static_cast<float>(Want.Y), LeanOmega, Dt);
		S.LastVelocity = FVector(Velocity.X, Velocity.Y, 0.f);
		S.bKnown = true;
	}

	/** The lean as a turn of the pelvis: about Axis (world, level: up
	    crossed with the way he leans) by Degrees, which tips his up toward
	    the lean, the way FQuat(Axis, Radians) turns it. */
	inline void LeanAxisAngle(const FLean& S, FVector& OutAxis, float& OutDegrees)
	{
		const FVector T(S.Tilt[0].X, S.Tilt[1].X, 0.f);
		OutDegrees = static_cast<float>(T.Size());
		OutAxis = OutDegrees > 1e-4f ? FVector::CrossProduct(FVector::UpVector, T / OutDegrees) : FVector(1.f, 0.f, 0.f);
	}

	/** Where to trace for a foot this frame: where it was drawn last, plus
	    its own velocity times this frame's Dt -- where it will be, not where
	    it was. A planted foot stands still and is traced where it stands; a
	    swing at a run is traced a frame ahead (at 341 cm/s and 30 Hz the
	    swing foot travels 20 cm and more in a frame). Its speed is held to
	    TraceLeadMaxSpeed, so one bad frame never sends a trace far away. */
	constexpr float TraceLeadMaxSpeed = 2000.f;

	struct FFootTrack
	{
		FVector Last = FVector::ZeroVector;
		FVector Velocity = FVector::ZeroVector;
		bool bValid = false;
		/** Where it was drawn this frame, Dt after the last. */
		void Push(const FVector& At, float Dt)
		{
			if (bValid && Dt > 1e-4f)
			{
				FVector V = (At - Last) / Dt;
				V.Z = 0.f;
				const float Sp = static_cast<float>(V.Size());
				Velocity = Sp > TraceLeadMaxSpeed ? V * (TraceLeadMaxSpeed / Sp) : V;
			}
			else if (!bValid)
			{
				Velocity = FVector::ZeroVector;
			}
			Last = At;
			bValid = true;
		}
		FVector Ahead(float Dt) const { return Last + Velocity * FMath::Max(0.f, Dt); }
	};

	/** A stop: the newest clip stands (measured, striding under
	    StrideMinSpeed) over a walk still fading out (measured, striding
	    over it). Unmeasured clips cannot tell, and are not stops. */
	inline bool Stopping(const FCrossfade& Mix, const SaudPlants::FClip* const* Plants, int NumPlants)
	{
		if (Mix.Num < 2) return false;
		auto PlantsOf = [&](int Clip) -> const SaudPlants::FClip* { return Clip >= 0 && Clip < NumPlants ? Plants[Clip] : nullptr; };
		const SaudPlants::FClip* New = PlantsOf(Mix.Layers[0].Clip);
		if (!New || New->Stride >= StrideMinSpeed) return false;
		for (int I = 1; I < Mix.Num; ++I)
		{
			const SaudPlants::FClip* P = PlantsOf(Mix.Layers[I].Clip);
			if (P && Mix.Layers[I].bLoop && P->Stride >= StrideMinSpeed && Mix.Layers[I].Weight > 0.f) return true;
		}
		return false;
	}
}
