#pragma once

/**
 * The anime look's moving parts -- impact frames, speed lines, and the
 * manga HUD's shapes -- with no engine in it.
 *
 * Since 2026-09-24 (Riyadh) this build is drawn as a gritty fight seinen
 * (Baki, Kengan Ashura, Hajime no Ippo): asked as "make all theme game style
 * like adult japanese anime". The still half of the look -- flat tones, ink,
 * hatching, the banded sky -- is one post-process material,
 * M_Anime_Post, built from Tools/look/anime_look.py. This is the half that
 * moves: what a blow does to that material, through the Material Parameter
 * Collection MPC_Anime, and the geometry the HUD is drawn with.
 *
 * None of these numbers are the browser's. The browser build is stylised
 * its own way and has no impact frame; the timings here are anime's, and
 * they are in anime's unit, the frame at 24 a second, so that "one frame of
 * ink" means what an animator means by it. They run in REAL time, like
 * SaudFeel's shake: an impact frame is drawn during the freeze, and the
 * freeze stops the game's clock, not the picture's.
 *
 * Only blows that matter get one. An impact frame on every jab stops being
 * an impact: a heavy clean hit, a knockdown and a parry do; a light hit and
 * a block do not.
 *
 * Header of free functions and plain structs, like SaudFeel.h, so
 * Tools/harness builds it with g++ and checks it (tests/anime.cpp).
 */

#if defined(SAUD_HARNESS)
	#include "HarnessTypes.h"
	#define SAUD_TEXT(s) s
#else
	#include "CoreMinimal.h"
	#define SAUD_TEXT(s) TEXT(s)
#endif

namespace SaudAnime
{
#if defined(SAUD_HARNESS)
	using SaudChar = char;
#else
	using SaudChar = TCHAR;
#endif
	// ------------------------------------------------------------ the assets
	// Built in the editor by Tools/look/anime_look.py, which checks these
	// names against its own.
	constexpr const SaudChar* CollectionPath = SAUD_TEXT("/Game/Materials/Anime/MPC_Anime.MPC_Anime");
	/** The tones and the ink, before tonemapping. */
	constexpr const SaudChar* PostMaterialPath = SAUD_TEXT("/Game/Materials/Anime/M_Anime_Post.M_Anime_Post");
	/** The speed lines and the impact frame's hard cut, after tonemapping
	    (so after TSR and bloom, which would soften a one-frame cut). */
	constexpr const SaudChar* FrameMaterialPath = SAUD_TEXT("/Game/Materials/Anime/M_Anime_Frame.M_Anime_Frame");

	namespace Param
	{
		constexpr const SaudChar* Impact = SAUD_TEXT("Impact");
		constexpr const SaudChar* ImpactInvert = SAUD_TEXT("ImpactInvert");
		constexpr const SaudChar* Speed = SAUD_TEXT("Speed");
		constexpr const SaudChar* SpeedCentreX = SAUD_TEXT("SpeedCentreX");
		constexpr const SaudChar* SpeedCentreY = SAUD_TEXT("SpeedCentreY");
		constexpr const SaudChar* SpeedSeed = SAUD_TEXT("SpeedSeed");
		constexpr const SaudChar* Key = SAUD_TEXT("Key");
	}

	// ------------------------------------------------------------- the frame
	constexpr float Frame = 1.f / 24.f;        // one frame of film
	constexpr float OnTwos = 2.f * Frame;      // the speed lines redraw on twos

	/** An impact frame's shape: how long, and which of its halves are the
	    flipped one (ink for paper). */
	struct FImpact
	{
		float Seconds = 0.f;
		bool bInvertFirst = false;
		bool bInvertSecond = false;
	};

	/** What one blow asks of the picture. */
	struct FBlowLook
	{
		FImpact Impact;
		float SpeedSeconds = 0.f;   // how long the speed lines stay
	};

	/** Heavy clean hit: one frame of ink and paper. Knockdown: two, the
	    second flipped -- the cut to black a fall gets. Parry: two, the first
	    flipped, because the parry is the reversal. Light hits and blocks:
	    nothing, so the big ones stay big. */
	inline FBlowLook ForBlow(bool bHeavy, bool bBlocked, bool bParried, bool bKnockdown)
	{
		FBlowLook L;
		if (bParried)
		{
			L.Impact = {2.f * Frame, true, false};
			L.SpeedSeconds = 0.30f;
			return L;
		}
		if (bBlocked)
		{
			return L;
		}
		if (bKnockdown)
		{
			L.Impact = {2.f * Frame, false, true};
			L.SpeedSeconds = 0.45f;
			return L;
		}
		if (bHeavy)
		{
			L.Impact = {Frame, false, false};
			L.SpeedSeconds = 0.30f;
		}
		return L;
	}

	/** Share of the speed lines' life they are at full strength before they
	    start to thin. */
	constexpr float SpeedHold = 0.35f;

	/** The picture's state between frames. Like SaudFeel::FState, a blow
	    only ever makes it bigger: a longer impact replaces a shorter one
	    that is running, never the other way. */
	struct FState
	{
		FImpact Impact;
		float ImpactElapsed = 0.f;
		float SpeedTotal = 0.f;
		float SpeedElapsed = 0.f;
		float Clock = 0.f;

		void Add(const FBlowLook& L)
		{
			const float Left = Impact.Seconds - ImpactElapsed;
			if (L.Impact.Seconds > 0.f && L.Impact.Seconds >= Left)
			{
				Impact = L.Impact;
				ImpactElapsed = 0.f;
			}
			if (L.SpeedSeconds > 0.f && L.SpeedSeconds >= SpeedTotal - SpeedElapsed)
			{
				SpeedTotal = L.SpeedSeconds;
				SpeedElapsed = 0.f;
			}
		}

		void Tick(float RealSeconds)
		{
			Clock += RealSeconds;
			ImpactElapsed = FMath::Min(ImpactElapsed + RealSeconds, Impact.Seconds);
			SpeedElapsed = FMath::Min(SpeedElapsed + RealSeconds, SpeedTotal);
		}

		/** 1 while the impact frame is up, 0 otherwise: it is a cut, not a
		    fade. */
		float ImpactValue() const
		{
			return ImpactElapsed < Impact.Seconds ? 1.f : 0.f;
		}

		/** 1 while the half being shown is the flipped one. */
		float InvertValue() const
		{
			if (ImpactValue() <= 0.f)
			{
				return 0.f;
			}
			const bool bFirst = ImpactElapsed < 0.5f * Impact.Seconds;
			return (bFirst ? Impact.bInvertFirst : Impact.bInvertSecond) ? 1.f : 0.f;
		}

		/** The speed lines: full for the first SpeedHold of their life, then
		    thinning straight to nothing. */
		float SpeedValue() const
		{
			if (SpeedTotal <= 0.f || SpeedElapsed >= SpeedTotal)
			{
				return 0.f;
			}
			const float T = SpeedElapsed / SpeedTotal;
			return T <= SpeedHold ? 1.f : 1.f - (T - SpeedHold) / (1.f - SpeedHold);
		}

		/** Changes every other frame of film, so the lines are redrawn on
		    twos, as a hand-drawn streak would be. */
		float Seed() const
		{
			return static_cast<float>(static_cast<int>(Clock / OnTwos) % 997);
		}
	};
}

/**
 * The HUD's shapes. Everything is laid out on a 1920 x 1080 page and
 * scaled by the screen's height, inside the TV title-safe area (the
 * outermost 5 % is left empty), with type big enough to read from a couch
 * -- CLAUDE.md's "the HUD is read at a distance".
 *
 * The look, since 2026-09-26 ("use darker theme style like Demon's
 * Souls"): dark translucent plates with a thin bronze keyline, thin flat
 * bars -- a Souls bar, not a manga panel edge -- a damage trail that holds
 * and then drains (the "how much did that cost" both genres show), the
 * rage meter as five small blocks, and the combo count on a sixteen-point
 * seal, a serrated disc rather than a lettered starburst. Until that day
 * the bars leaned like a panel edge (0.45 of their height), the ink border
 * was 5 page px and the combo sat on a twelve-point starburst.
 */
namespace SaudHud
{
	constexpr float PageW = 1920.f;
	constexpr float PageH = 1080.f;
	constexpr float Safe = 0.05f;               // title-safe margin, each side
	constexpr float Ink = 2.f;                  // keyline, page pixels (5 until 2026-09-26)
	constexpr float Lean = 0.f;                 // bars are flat (0.45, leaning, until 2026-09-26)

	constexpr float NameText = 36.f;            // page pixels, cap height class
	constexpr float ComboText = 104.f;
	constexpr float BossNameText = 40.f;
	/** Nothing the player must read is smaller than this share of the
	    screen's height: about 30 px at 1080, legible at three metres. */
	constexpr float MinTextShare = 1.f / 36.f;

	constexpr int RageBlocks = 5;

	struct FPoint { float X = 0.f, Y = 0.f; };
	struct FRect { float X = 0.f, Y = 0.f, W = 0.f, H = 0.f; };

	/** The page laid onto a screen: scale by height, centred across. */
	struct FPage
	{
		float Scale = 1.f;
		float ScreenW = PageW, ScreenH = PageH;

		static FPage For(float InW, float InH)
		{
			FPage P;
			P.ScreenW = InW;
			P.ScreenH = InH;
			P.Scale = InH / PageH;
			return P;
		}
		float Px(float PageUnits) const { return PageUnits * Scale; }
		/** The safe area in screen pixels, which is what the layout hangs
		    off: wider screens push the corners out, the height is fixed. */
		float Left() const { return ScreenW * Safe; }
		float Right() const { return ScreenW * (1.f - Safe); }
		float Top() const { return ScreenH * Safe; }
		float Bottom() const { return ScreenH * (1.f - Safe); }
	};

	struct FLayout
	{
		FRect PlayerPanel;
		FRect Health;
		FRect Stamina;
		FRect Rage[RageBlocks];
		FPoint Name;
		FPoint Combo;
		float ComboRadius = 0.f;
		FRect BossPanel;
		FRect BossHealth;
		FPoint BossName;
		float EnemyBarW = 0.f, EnemyBarH = 0.f;
	};

	inline FLayout Lay(const FPage& P)
	{
		FLayout L;
		const float X = P.Left(), Y = P.Top();
		// Thin bars, as a Souls HUD draws them: health 16 page px (34
		// before), stamina 10 (14), rage blocks 12 (22).
		L.PlayerPanel = {X, Y, P.Px(620.f), P.Px(120.f)};
		L.Name = {X + P.Px(28.f), Y + P.Px(12.f)};
		L.Health = {X + P.Px(28.f), Y + P.Px(60.f), P.Px(560.f), P.Px(16.f)};
		L.Stamina = {X + P.Px(28.f), Y + P.Px(86.f), P.Px(400.f), P.Px(10.f)};
		const float BlockW = P.Px(20.f), Gap = P.Px(8.f);
		for (int i = 0; i < RageBlocks; ++i)
		{
			L.Rage[i] = {X + P.Px(448.f) + i * (BlockW + Gap), Y + P.Px(85.f), BlockW, P.Px(12.f)};
		}
		L.ComboRadius = P.Px(118.f);
		L.Combo = {P.Right() - L.ComboRadius, P.Top() + P.Px(300.f)};
		const float BW = P.Px(1100.f);
		L.BossPanel = {0.5f * P.ScreenW - 0.5f * BW, P.Bottom() - P.Px(100.f), BW, P.Px(100.f)};
		L.BossName = {L.BossPanel.X + P.Px(36.f), L.BossPanel.Y + P.Px(10.f)};
		L.BossHealth = {L.BossPanel.X + P.Px(36.f), L.BossPanel.Y + P.Px(64.f), BW - P.Px(72.f), P.Px(14.f)};
		L.EnemyBarW = P.Px(110.f);
		L.EnemyBarH = P.Px(7.f);
		return L;
	}

	/** A bar's filled part: four corners, clockwise from the bottom left,
	    leaning right by Lean of its height (flat since 2026-09-26). Fill 0
	    is a line, not nothing, so a caller can always draw it. */
	inline void BarQuad(const FRect& R, float Fill, FPoint Out[4])
	{
		const float F = FMath::Clamp(Fill, 0.f, 1.f);
		const float S = R.H * Lean;
		const float W = (R.W - S) * F;
		Out[0] = {R.X, R.Y + R.H};
		Out[1] = {R.X + S, R.Y};
		Out[2] = {R.X + S + W, R.Y};
		Out[3] = {R.X + W, R.Y + R.H};
	}

	/** The paper-white trail behind a bar that has just been cut: it holds
	    where the bar was for a beat, then drains down to it. A bar that
	    rises (a heal) is followed at once. */
	struct FGhost
	{
		static constexpr float HoldSeconds = 0.45f;
		static constexpr float DrainPerSecond = 0.65f;   // of the whole bar

		float Value = 1.f;
		float Hold = 0.f;
		float Last = 1.f;

		void Tick(float Target, float Dt)
		{
			if (Target < Last)
			{
				Hold = HoldSeconds;              // a new cut restarts the beat
			}
			Last = Target;
			if (Target >= Value)
			{
				Value = Target;
				Hold = 0.f;
				return;
			}
			if (Hold > 0.f)
			{
				Hold = FMath::Max(0.f, Hold - Dt);
				return;
			}
			Value = FMath::Max(Target, Value - DrainPerSecond * Dt);
		}
	};

	/** How full each of the rage meter's blocks is. */
	inline float RageBlock(float RageFraction, int Index)
	{
		return FMath::Clamp(FMath::Clamp(RageFraction, 0.f, 1.f) * RageBlocks - Index, 0.f, 1.f);
	}

	/** The combo's seal: 2N points alternating out and in, turned a little
	    more for every hit so a rising count visibly moves. Since 2026-09-26
	    a serrated disc -- sixteen shallow teeth -- where it was a
	    twelve-point manga starburst (inner radius 0.62). */
	constexpr int BurstPoints = 16;
	constexpr float BurstInner = 0.90f;

	inline FPoint BurstPoint(const FPoint& Centre, float Radius, int Count, int i)
	{
		const float Turn = FMath::DegreesToRadians(7.f * static_cast<float>(Count));
		const float A = Turn + static_cast<float>(i) * 3.14159265f / BurstPoints;
		const float R = (i % 2 == 0) ? Radius : Radius * BurstInner;
		return {Centre.X + R * FMath::Cos(A), Centre.Y + R * FMath::Sin(A)};
	}

	/** The combo number's punch when it goes up: 1.35 at once, back to 1
	    with a 0.12 s time constant. */
	inline float ComboPunch(float SinceHit)
	{
		return 1.f + 0.35f * FMath::Exp(-FMath::Max(0.f, SinceHit) / 0.12f);
	}

	/** A street man's bar is over his head only for a while after he is
	    hit; a boss has the banner instead. */
	constexpr float EnemyBarSeconds = 2.5f;
}
