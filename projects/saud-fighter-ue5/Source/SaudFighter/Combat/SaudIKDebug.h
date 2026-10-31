#pragma once

/**
 * The in-game IK, drawn -- with no engine in it.
 *
 * Asked 2026-10-31 (Riyadh) as "improve visual ik", settled as an IK debug
 * view in the game: a console command that draws what the runtime IK
 * (SaudIK.h, USaudMotionAnimInstance) is doing, so it can be seen and tuned
 * while playing. Nothing drew it before.
 *
 *   saud.ik.Show 0   off (the default)
 *   saud.ik.Show 1   every fighter
 *   saud.ik.Show 2   the player's man only
 *
 * What is drawn, all in the world, for one frame at a time:
 *  - each foot's two ground traces (heel and ball): blue where they hit,
 *    red where they found nothing, the hit point and the ground's normal;
 *  - each foot as drawn, heel to ball: green while it is held where it was
 *    planted, yellow while it is free (swinging, or handed back to the clip),
 *    and a held foot's anchor at the ball's height;
 *  - the strike's mark on the man it is drawn to, as big as the skin the
 *    joint stops short for, thicker as the strike's share comes on, and the
 *    line down to his belt for a mark out of reach;
 *  - where a block meets the blow;
 *  - the look, from his head to the head he is turned to.
 * The engine side adds a line of numbers over him (the feet's share, the
 * hips' lag, the lean, the strike's share).
 *
 * This file only decides what to draw (Build fills a fixed list, never
 * allocates); USaudMotionAnimInstance draws it with DrawDebugLine and
 * DrawDebugSphere, compiled out where the engine compiles debug drawing out
 * (shipping builds). Tools/harness builds this with g++ and checks it
 * (tests/ikdebug.cpp).
 */

#if defined(SAUD_HARNESS)
	#include "HarnessTypes.h"
#else
	#include "CoreMinimal.h"
#endif

namespace SaudIKDebug
{
	/** What a piece of the drawing means; its colour follows (Rgb). */
	enum class EColour : unsigned char { Held, Free, Hit, Missed, Normal, Strike, Block, Look };

	struct FRgb { unsigned char R = 255, G = 255, B = 255; };

	inline FRgb Rgb(EColour C)
	{
		switch (C)
		{
		case EColour::Held:   return { 60, 220, 90 };     // green: a foot held where it was planted
		case EColour::Free:   return { 250, 200, 40 };    // yellow: a foot swinging or handed back
		case EColour::Hit:    return { 90, 170, 255 };    // blue: a trace that found ground
		case EColour::Missed: return { 255, 50, 50 };     // red: a trace that found nothing
		case EColour::Normal: return { 255, 255, 255 };   // white: the ground's normal
		case EColour::Strike: return { 255, 120, 30 };    // orange: the strike's mark
		case EColour::Block:  return { 170, 90, 255 };    // violet: where a block meets the blow
		case EColour::Look:   return { 40, 230, 230 };    // cyan: the look
		}
		return {};
	}

	enum class EShape : unsigned char { Line, Sphere };

	/** One thing to draw: a line A to B, or a sphere at A of Radius. World cm. */
	struct FPrim
	{
		EShape Shape = EShape::Line;
		FVector A = FVector::ZeroVector;
		FVector B = FVector::ZeroVector;
		float Radius = 0.f;
		EColour Colour = EColour::Normal;
		float Thickness = 1.f;
	};

	/** Enough for everything at once: 2 feet x 2 traces x 3, 2 feet x 2, a
	    strike's 2, a block's 1, the look's 1 -- 20 -- with room. */
	constexpr int MaxPrims = 32;

	// Sizes at Saud's size, cm; each grows with the man (FView::Size).
	constexpr float NormalCm = 18.f;      // the ground's normal, drawn this long
	constexpr float PointCm = 2.5f;       // a trace's hit point
	constexpr float AnchorCm = 4.f;       // a held foot's anchor
	constexpr float MarkMinCm = 3.f;      // the strike's mark, at least
	constexpr float MeetCm = 6.f;         // where a block meets the blow
	constexpr float ThinLine = 1.f;
	constexpr float ThickLine = 3.f;

	/** One ground trace, as the game took it. */
	struct FTraceView
	{
		bool bTraced = false;
		bool bHit = false;
		FVector From = FVector::ZeroVector;
		FVector To = FVector::ZeroVector;
		FVector Point = FVector::ZeroVector;
		FVector Normal = FVector::UpVector;
	};

	/** One foot as the IK drew it last frame. Anchor's Z is not kept by the
	    IK (SaudIK::FFootHold): it is drawn at the ball's height. */
	struct FFootView
	{
		bool bDrawn = false;
		FVector Heel = FVector::ZeroVector;
		FVector Ball = FVector::ZeroVector;
		bool bHeld = false;
		FVector Anchor = FVector::ZeroVector;
	};

	/** Everything the view draws, in the world. */
	struct FView
	{
		float Size = 1.f;                    // his size against Saud's (SaudIK BodyScale, world)
		FTraceView Trace[2][2];              // [side][0 heel, 1 ball]
		FFootView Foot[2];
		bool bStrike = false;
		FVector StrikeMark = FVector::ZeroVector;
		FVector StrikeLow = FVector::ZeroVector;
		float StrikeSkin = 0.f;              // world cm
		float StrikeAlpha = 0.f;
		bool bBlock = false;
		FVector BlockMeet = FVector::ZeroVector;
		float BlockAlpha = 0.f;
		bool bLook = false;
		FVector LookFrom = FVector::ZeroVector;
		FVector LookTo = FVector::ZeroVector;
	};

	struct FList
	{
		FPrim Prim[MaxPrims];
		int Num = 0;
		/** False, and nothing written, once the list is full. */
		bool Add(const FPrim& P)
		{
			if (Num >= MaxPrims) return false;
			Prim[Num++] = P;
			return true;
		}
	};

	inline FPrim Line(const FVector& A, const FVector& B, EColour C, float Thickness)
	{
		FPrim P; P.Shape = EShape::Line; P.A = A; P.B = B; P.Colour = C; P.Thickness = Thickness;
		return P;
	}

	inline FPrim Sphere(const FVector& At, float Radius, EColour C, float Thickness)
	{
		FPrim P; P.Shape = EShape::Sphere; P.A = At; P.B = At; P.Radius = Radius; P.Colour = C; P.Thickness = Thickness;
		return P;
	}

	/** What to draw for one fighter this frame. Out is cleared first. */
	inline void Build(const FView& V, FList& Out)
	{
		Out.Num = 0;
		const float S = V.Size > 0.f ? V.Size : 1.f;

		// the ground under each foot, as traced
		for (int Side = 0; Side < 2; ++Side)
		{
			for (int K = 0; K < 2; ++K)
			{
				const FTraceView& T = V.Trace[Side][K];
				if (!T.bTraced) continue;
				Out.Add(Line(T.From, T.To, T.bHit ? EColour::Hit : EColour::Missed, ThinLine));
				if (!T.bHit) continue;
				Out.Add(Sphere(T.Point, PointCm * S, EColour::Hit, ThinLine));
				Out.Add(Line(T.Point, T.Point + T.Normal.GetSafeNormal() * (NormalCm * S), EColour::Normal, ThinLine));
			}
		}

		// each foot as drawn, and a held foot's anchor
		for (int Side = 0; Side < 2; ++Side)
		{
			const FFootView& F = V.Foot[Side];
			if (!F.bDrawn) continue;
			Out.Add(Line(F.Heel, F.Ball, F.bHeld ? EColour::Held : EColour::Free, ThickLine));
			if (F.bHeld)
			{
				Out.Add(Sphere(FVector(F.Anchor.X, F.Anchor.Y, F.Ball.Z), AnchorCm * S, EColour::Held, ThinLine));
			}
		}

		// the strike's mark, as big as the skin it stops short for, thicker as it comes on
		if (V.bStrike && V.StrikeAlpha > 0.f)
		{
			const float A = V.StrikeAlpha < 1.f ? V.StrikeAlpha : 1.f;
			const float R = V.StrikeSkin > MarkMinCm * S ? V.StrikeSkin : MarkMinCm * S;
			Out.Add(Sphere(V.StrikeMark, R, EColour::Strike, ThinLine + (ThickLine - ThinLine) * A));
			Out.Add(Line(V.StrikeMark, V.StrikeLow, EColour::Strike, ThinLine));
		}

		// where a block meets the blow
		if (V.bBlock && V.BlockAlpha > 0.f)
		{
			Out.Add(Sphere(V.BlockMeet, MeetCm * S, EColour::Block, ThinLine + (ThickLine - ThinLine) * (V.BlockAlpha < 1.f ? V.BlockAlpha : 1.f)));
		}

		// the look
		if (V.bLook)
		{
			Out.Add(Line(V.LookFrom, V.LookTo, EColour::Look, ThinLine));
		}
	}
}
