#pragma once

/**
 * The title's shot -- where the camera stands behind the main menu, as
 * plain data and pure functions, with no engine in it.
 *
 * Asked 2026-10-01 (Riyadh) as "make suad main menu game", settled as the
 * Unreal build: a live 3D title scene behind the menu the build already has
 * -- Saud himself, standing in his guard where the level put him, the
 * camera sweeping slowly in front of him, in the anime look, lit by the
 * place's own fires. Until then the Title stood over the fight camera as
 * the level opened, frozen, with Saud in his bind pose (the pause stopped
 * his clip before it started).
 *
 * The menu owns the left of the screen: its torn ink wash is WashW page
 * units wide from the left safe line (SaudMenu::Lay), half a 16:9 screen
 * and nearly two thirds of a 4:3 one. So the shot is worked out from the
 * screen: Saud stands at the middle of what the wash leaves, between its
 * right edge and the right safe line, whatever the shape; the vertical
 * field of view is held (the horizontal one follows the aspect) so he is
 * the same size on every screen; and the camera sweeps a slow arc in
 * front of him, never behind, so his face is always the one looking out.
 *
 * Game/SaudTitleCamera.cpp asks Shoot() every frame (on real time: the
 * title holds the world paused) and puts the camera where it says;
 * Tools/harness/tests/title.cpp holds it to the frame at the seven screen
 * shapes the HUD and the menu are held to, over a whole sweep, at any
 * place and facing; Tools/look/title_preview.py draws the shot with the
 * real menu over it.
 *
 * Units: centimetres, Z up; a facing is a unit vector on the ground (the
 * fighter's, AFighterBase::GetFacing). Right is Cross(Up, Forward), as the
 * engine's view has it.
 */

#include "SaudMenu.h"

namespace SaudTitle
{
	constexpr float Pi = 3.14159265358979f;

	/** The vertical field of view, held on every screen (degrees). */
	constexpr float VFovDeg = 32.f;
	/** How far the camera stands from him, on the ground (cm): this far
	    at least, and further where the menu leaves little room (FitW). */
	constexpr float Distance = 560.f;
	/** How wide he is to the camera at the widest point of the sweep, the
	    guard's depth turned into view included (cm): what must fit in the
	    room the menu leaves. Measured on the box below, at the arc's ends. */
	constexpr float FitW = 135.f;
	/** The camera's height over his feet, and the height the shot is aimed
	    through him (cm): a little over his chest, looking a little down. */
	constexpr float EyeZ = 150.f;
	constexpr float AimZ = 98.f;
	/** The sweep: this far either side of straight in front of him, and
	    this long for the whole arc there and back (degrees, seconds). */
	constexpr float SweepDeg = 38.f;
	constexpr float PeriodS = 28.f;
	/** Him, as the box the shot must hold: the guard's fists this far out
	    in front, the shoulders and elbows this wide each side, his back
	    this far behind his feet, his height (cm). The MMA guard's lead fist
	    is 41 cm out (CLAUDE.md, "Saud aligned"). */
	constexpr float FigureFront = 50.f, FigureHalfW = 35.f, FigureBack = 25.f, FigureH = 188.f;
	/** Room kept between him and the wash's edge, and the safe line (a
	    share of the screen's width). */
	constexpr float Margin = 0.02f;

	/** The horizontal field of view the engine is given for a screen of
	    this aspect, so the vertical one is VFovDeg on all of them. */
	inline float HFovDeg(float Aspect)
	{
		const float T = FMath::Tan(FMath::DegreesToRadians(0.5f * VFovDeg)) * Aspect;
		return FMath::RadiansToDegrees(2.f * FMath::Atan(T));
	}

	/** The Title's model, as the engine opens it: what the wash is laid for. */
	inline SaudMenu::FMenuModel TitleModel()
	{
		SaudMenu::FMenuModel M;
		SaudMenu::Open(M, SaudMenu::EScreen::Title);
		return M;
	}

	/** Where the menu stops and the right safe line is, as shares of the
	    screen's width. */
	inline float FreeLeft(const SaudHud::FPage& P)
	{
		const SaudMenu::FMenuLayout L = SaudMenu::Lay(P, TitleModel());
		return (L.Wash.X + L.Wash.W) / P.ScreenW;
	}
	inline float FreeRight(const SaudHud::FPage& P) { return P.Right() / P.ScreenW; }

	/** Where his middle stands across the screen: the middle of what the
	    menu leaves. */
	inline float HoldX(const SaudHud::FPage& P)
	{
		return 0.5f * (FreeLeft(P) + Margin + FreeRight(P) - Margin);
	}

	/** A screen's frame for the shot: its aspect, where his middle stands
	    across it, how far the camera stands off. */
	struct FFrame
	{
		float Aspect = 16.f / 9.f;
		float HoldAt = 0.72f;
		float Dist = Distance;
	};

	inline FFrame FrameFor(const SaudHud::FPage& P)
	{
		FFrame F;
		F.Aspect = P.ScreenW / P.ScreenH;
		F.HoldAt = HoldX(P);
		const float Room = FreeRight(P) - FreeLeft(P) - 2.f * Margin;
		const float Th = FMath::Tan(FMath::DegreesToRadians(0.5f * HFovDeg(F.Aspect)));
		F.Dist = FMath::Max(Distance, FitW / (FMath::Max(Room, 0.05f) * 2.f * Th));
		return F;
	}

	struct FShot
	{
		FVector Eye;
		FVector Forward;        // unit
		float HFovDeg = 60.f;
		float SweepDeg = 0.f;   // where the arc is now, off straight in front
	};

	/** A flat vector turned by A radians about Up (X toward Y). */
	inline FVector Turn(const FVector& V, float A)
	{
		const float C = FMath::Cos(A), S = FMath::Sin(A);
		return FVector(V.X * C - V.Y * S, V.X * S + V.Y * C, V.Z);
	}

	/** The shot at T seconds into the title, for a man standing with his
	    feet at Feet facing Facing, on a screen with this frame. */
	inline FShot Shoot(const FVector& Feet, const FVector& Facing, float T, const FFrame& Fr)
	{
		const float Aspect = Fr.Aspect, HoldAt = Fr.HoldAt;
		FShot S;
		const FVector Face = FVector(Facing.X, Facing.Y, 0.f).GetSafeNormal();
		S.SweepDeg = SweepDeg * FMath::Sin(2.f * Pi * T / PeriodS);
		const FVector Out = Turn(Face, FMath::DegreesToRadians(S.SweepDeg));
		S.Eye = Feet + Out * Fr.Dist + FVector(0.f, 0.f, EyeZ);
		const FVector Aim = Feet + FVector(0.f, 0.f, AimZ);
		S.HFovDeg = HFovDeg(Aspect);
		// look past him to his side by the angle that puts him at HoldAt:
		// a point straight ahead is the screen's middle, and one at angle a
		// to the right is at 0.5 + 0.5 tan(a) / tan(hfov / 2)
		const float Th = FMath::Tan(FMath::DegreesToRadians(0.5f * S.HFovDeg));
		const float Off = FMath::Atan((2.f * HoldAt - 1.f) * Th);
		const FVector To = (Aim - S.Eye).GetSafeNormal();
		S.Forward = Turn(To, -Off).GetSafeNormal();
		return S;
	}

	struct FSeen
	{
		float X = 0.f, Y = 0.f;   // screen shares, Y down
		float Depth = 0.f;        // cm along the view
	};

	/** A point as the shot sees it: a pinhole with the shot's horizontal
	    field of view on a screen of this aspect. */
	inline FSeen Project(const FShot& S, float Aspect, const FVector& P)
	{
		const FVector F = S.Forward;
		const FVector R = FVector::CrossProduct(FVector::UpVector, F).GetSafeNormal();
		const FVector U = FVector::CrossProduct(F, R);
		const FVector D = P - S.Eye;
		FSeen Out;
		Out.Depth = FVector::DotProduct(D, F);
		const float Th = FMath::Tan(FMath::DegreesToRadians(0.5f * S.HFovDeg)), Tv = Th / Aspect;
		const float Z = FMath::Max(Out.Depth, 1e-3f);
		Out.X = 0.5f + 0.5f * FVector::DotProduct(D, R) / (Z * Th);
		Out.Y = 0.5f - 0.5f * FVector::DotProduct(D, U) / (Z * Tv);
		return Out;
	}

	/** The eight corners of the box he stands in. */
	inline void Figure(const FVector& Feet, const FVector& Facing, FVector Out[8])
	{
		const FVector F = FVector(Facing.X, Facing.Y, 0.f).GetSafeNormal();
		const FVector R = FVector::CrossProduct(FVector::UpVector, F);
		const float Along[2] = {-FigureBack, FigureFront}, Across[2] = {-FigureHalfW, FigureHalfW}, Up[2] = {0.f, FigureH};
		for (int n = 0; n < 8; ++n)
			Out[n] = Feet + F * Along[n & 1] + R * Across[(n >> 1) & 1] + FVector(0.f, 0.f, Up[(n >> 2) & 1]);
	}
}
