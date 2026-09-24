#pragma once

/**
 * The geometry of a fight in the open, with no engine in it.
 *
 * Until 2026-09-16 this project was a strip: the camera looked one way for
 * the whole game, X was "along", Y was "depth", and a fighter's facing was a
 * sign. Every one of those is a fact about a corridor rather than about a
 * fight, and none of them survives a district you can walk around. What
 * replaces them is here: reach measured along a facing *vector*, a place
 * measured as a circle rather than two ranges, and a stick read against the
 * camera rather than against the world.
 *
 * It is a header of free functions on purpose, exactly like the Unity port's
 * `TwoBoneIK` and `Fighter.InHitbox`: no actors, no components, no world. The
 * project has never been compiled by an engine, so anything that can be
 * executed and checked without one is worth the separation — `Tools/harness`
 * builds this file with g++ against a small stub of `FVector` and `FMath` and
 * property-tests it. That is the only part of this build that has ever run.
 *
 * Centimetres, and Z is up: Unreal's axes, unchanged. What changed is that
 * no direction here is a world axis any more.
 */

#if defined(SAUD_HARNESS)
	#include "HarnessTypes.h"
#else
	#include "CoreMinimal.h"
#endif

namespace SaudArena
{
	/** Flat length of a vector: a fight is measured on the ground plane, and
	    a fighter two metres taller than you is not two metres further away. */
	inline float Flat(const FVector& V)
	{
		return FMath::Sqrt(V.X * V.X + V.Y * V.Y);
	}

	inline FVector FlatVector(const FVector& V)
	{
		return FVector(V.X, V.Y, 0.f);
	}

	/** A unit direction on the ground, or `Fallback` if there is not one. */
	inline FVector Direction(const FVector& From, const FVector& To, const FVector& Fallback)
	{
		const FVector D = FlatVector(To - From);
		const float Len = Flat(D);
		return Len > 1e-3f ? FVector(D.X / Len, D.Y / Len, 0.f) : Fallback;
	}

	/**
	 * Is a target inside this strike?
	 *
	 * Forward along the facing within reach, and inside a band either side of
	 * that line. The two numbers are the ones the whole game was tuned around
	 * — the browser build's reach and depth tolerance — taken along and
	 * across the facing vector instead of along X and Y. Rotating an attacker
	 * and a target together changes nothing, which is the property the
	 * harness checks over every angle.
	 *
	 * `Behind` is the small amount of slack behind the attacker that the
	 * strip version allowed, kept so the spacing is unchanged.
	 */
	constexpr float HitboxBehind = 60.f;
	constexpr float HitboxOver = 60.f;

	/** Where a point is in a fighter's own frame: how far ahead of him along
	    his facing, and how far across it (positive to his left). */
	inline void AlongAcross(const FVector& Origin, const FVector& Facing, const FVector& Target,
	                        float& OutForward, float& OutAcross)
	{
		const FVector Delta = FlatVector(Target - Origin);
		OutForward = Delta.X * Facing.X + Delta.Y * Facing.Y;
		// Across the facing: the perpendicular in the ground plane.
		OutAcross = Delta.X * -Facing.Y + Delta.Y * Facing.X;
	}

	inline bool InHitbox(const FVector& Origin, const FVector& Facing, const FVector& Target,
	                     float Reach, float Lateral, float Behind = HitboxBehind, float Over = HitboxOver)
	{
		float Forward = 0.f, Across = 0.f;
		AlongAcross(Origin, Facing, Target, Forward, Across);
		if (Forward < -Behind || Forward > Reach + Over)
		{
			return false;
		}
		return FMath::Abs(Across) <= Lateral;
	}

	/** Whether a guard covers a blow. You can only block what is in front of
	    you; on the strip that was a sign comparison, here it is the front
	    hemisphere, which is what stops a guard from covering your back. */
	inline bool Covers(const FVector& Facing, const FVector& ToAttacker)
	{
		const FVector D = FlatVector(ToAttacker);
		return (D.X * Facing.X + D.Y * Facing.Y) > 0.f;
	}

	/**
	 * Where the stick points, in the world.
	 *
	 * On the strip the camera never turned, so "right" was +X for the whole
	 * game and the stick could be spent on world axes. A camera that swings
	 * makes that meaningless: pushing away from you has to mean away from you
	 * on screen, or the world becomes unnavigable the first time you turn a
	 * corner. `CameraYaw` is degrees, Unreal's convention — 0 looks down +X.
	 */
	inline FVector CameraRelative(float InputX, float InputY, float CameraYaw)
	{
		const float R = FMath::DegreesToRadians(CameraYaw);
		const float C = FMath::Cos(R), S = FMath::Sin(R);
		// Camera forward is (cos, sin); its right is (-sin, cos).
		const FVector Wish(InputY * C - InputX * S, InputY * S + InputX * C, 0.f);
		const float Len = Flat(Wish);
		return Len > 1.f ? FVector(Wish.X / Len, Wish.Y / Len, 0.f) : Wish;
	}

	/**
	 * Keep a fighter inside the place he is fighting in.
	 *
	 * A locked arena was two numbers on X, with the depth fixed for the whole
	 * game, because a corridor has a near end and a far end and nothing else.
	 * An arena in the open is a circle: it has the same size in every
	 * direction, which is the only shape that does not tell the player which
	 * way the level used to run.
	 */
	inline FVector ClampToCircle(const FVector& Point, const FVector& Centre, float Radius)
	{
		const FVector D = FlatVector(Point - Centre);
		const float Len = Flat(D);
		if (Len <= Radius || Len < 1e-4f)
		{
			return Point;
		}
		const float K = Radius / Len;
		return FVector(Centre.X + D.X * K, Centre.Y + D.Y * K, Point.Z);
	}

	/** True inside the circle, with a margin. */
	inline bool InCircle(const FVector& Point, const FVector& Centre, float Radius)
	{
		return Flat(FlatVector(Point - Centre)) <= Radius;
	}

	/**
	 * Where an enemy wants to stand.
	 *
	 * It used to pick a side on X — `Target.X + FlankSide * range` — which in
	 * an open district means every enemy in a wave lines up east and west of
	 * the player however he turns. Here the spot is a *bearing*: an angle off
	 * the line from the player to this fighter, so the crowd spreads around
	 * him and closing from behind is a thing that can happen.
	 *
	 * `BearingDegrees` is that angle, `Range` how far out, and `Lane` pushes
	 * the ones further back in the queue further out so they do not stack.
	 */
	inline FVector FlankSpot(const FVector& TargetPos, const FVector& SelfPos,
	                         float BearingDegrees, float Range, float Lane)
	{
		const FVector Out = Direction(TargetPos, SelfPos, FVector(1.f, 0.f, 0.f));
		const float R = FMath::DegreesToRadians(BearingDegrees);
		const float C = FMath::Cos(R), S = FMath::Sin(R);
		const FVector Turned(Out.X * C - Out.Y * S, Out.X * S + Out.Y * C, 0.f);
		const float D = Range + Lane;
		return FVector(TargetPos.X + Turned.X * D, TargetPos.Y + Turned.Y * D, SelfPos.Z);
	}

	/**
	 * The slot one fighter holds in a crowd.
	 *
	 * `FlankSpot` answers "where, at this bearing" and will happily put two
	 * fighters in the same place if they are given the same one — which the
	 * harness caught it doing: six enemies in a wave, alternating sides off
	 * their own approach lines, ended up with a pair 35 cm apart. So the
	 * assignment is here rather than at the call site, where it was a pair of
	 * ad-hoc numbers.
	 *
	 * Two to a ring, opposite sides, and each ring further round and further
	 * out than the last. The worst case is a whole wave arriving from one
	 * direction, and even then no two of them want the same ground.
	 */
	inline void CrowdSlot(int IndexInWave, float& OutBearing, float& OutLane)
	{
		const int Ring = IndexInWave / 2;
		const float Side = (IndexInWave % 2 == 0) ? 1.f : -1.f;
		OutBearing = Side * (22.f + Ring * 34.f);
		OutLane = Ring * 90.f;
	}

	/**
	 * Push a wanted spot off someone already standing there.
	 *
	 * `CrowdSlot` spreads a wave that arrives from one direction, and cannot
	 * do better than that: each fighter's bearing is measured off its own
	 * approach, so two coming from different sides can still want the same
	 * ground and neither assignment knows about the other. The harness had
	 * six of them from six directions land a pair 56 cm apart.
	 *
	 * On a strip that never came up — enemies queued along one axis. In the
	 * open it is the ordinary case, so the spot is a want and this is the
	 * correction: applied against each neighbour every frame, a crowd relaxes
	 * into a ring around the player instead of a heap on one side of him.
	 */
	inline FVector PushApart(const FVector& Spot, const FVector& Other, float MinGap)
	{
		const FVector D = FlatVector(Spot - Other);
		const float Len = Flat(D);
		if (Len >= MinGap)
		{
			return Spot;
		}
		// Standing exactly on someone: step off along a fixed direction
		// rather than dividing by nothing.
		const FVector Away = Len > 1e-3f ? FVector(D.X / Len, D.Y / Len, 0.f)
		                                 : FVector(1.f, 0.f, 0.f);
		const float Move = (MinGap - Len) * 0.5f;
		return FVector(Spot.X + Away.X * Move, Spot.Y + Away.Y * Move, Spot.Z);
	}

	/**
	 * Where a fraction along the old stage falls in an open district.
	 *
	 * The same derivation the Unity port uses (`District.Spiral`) and the
	 * same one `Tools/fab/lay_out_world.py` lays a district out with: an
	 * outward spiral of a turn and a third, so walking out from the middle
	 * meets the stage's content in the order the stage intended while leaving
	 * every one of them approachable from any direction.
	 *
	 * Here so that the game and the map cannot disagree about it.
	 */
	inline FVector SpiralPoint(float T, float Extent, float Phase)
	{
		const float Turns = 1.35f;
		const float Angle = Phase + T * Turns * 2.f * 3.14159265358979f;
		const float Radius = Extent * (0.18f + 0.68f * T);
		return FVector(FMath::Cos(Angle) * Radius, FMath::Sin(Angle) * Radius, 0.f);
	}

	/**
	 * How far a district reaches from its middle, in centimetres, given the
	 * stage's own Length.
	 *
	 * The same derivation `Tools/fab/lay_out_world.py` lays the open world
	 * out with and the Unity port's `District.LengthToExtent` uses -- three
	 * copies of one number for the same reason SpiralPoint is: the game, the
	 * open-world map and the per-stage blockout all have to agree on how big
	 * a district is, and none of them can include another's source file.
	 * A short stage is not a cupboard and a long one is not a county: the
	 * clamp keeps every district walkable at the scale a fighter and a
	 * camera actually read.
	 */
	inline float DistrictExtent(float Length)
	{
		constexpr float LengthToExtent = 1.7f;
		constexpr float MinExtent = 6000.f;
		constexpr float MaxExtent = 13000.f;
		return FMath::Clamp(Length * LengthToExtent, MinExtent, MaxExtent);
	}
}
