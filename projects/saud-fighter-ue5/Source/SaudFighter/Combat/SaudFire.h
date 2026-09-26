#pragma once

/**
 * HAWK FIST's fire -- the browser's numbers, the rules, and the state --
 * with no engine in it.
 *
 * Asked 2026-09-26 (Riyadh) as "build flame fire hit for Saud". The fire
 * hit this game has is HAWK FIST (assets/talents.js: "Your punches carry
 * fire. Burns MP, and only punches -- kicks stay cold"): the browser draws
 * it as three tongues on his lead fist while the talent is carried and
 * there is MP to burn (index.html handFlame(), :1206), brightest through a
 * punch, and a burning punch that lands bursts on the man hit (applyHit(),
 * :3534-3540) and costs its MP. This build carried the talent's tags and
 * an IsBurning() on the ability path nothing drives (CLAUDE.md, "The
 * bosses move now": strikes go through AFighterBase::StartAttack), and no
 * picture of it at all. Now:
 *
 *  - the RULES here decide when the fist is lit and when a punch burns, on
 *    the path that runs (ASaudCharacter), with the browser's own numbers:
 *    14 MP a burning punch, x1.55 damage, 10 px more reach, 90 px more push;
 *  - the DRAWING is the anime look's (Tools/look/anime_look.py, step 8 of
 *    M_Anime_Frame): the browser's shapes in its figure pixels, scaled to
 *    the fist's own distance, cut to flat tones with an ink line, behind
 *    the hand so the knuckles stay legible -- the browser's own note. The
 *    numbers it needs are the ones below; anime_look.py reads this header
 *    and holds its copy to them;
 *  - the STATE (FState) is the flame easing on and off as the browser's
 *    hawkLit does, and the burst's clock.
 *
 * Everything is quoted with where it comes from. The browser project owns
 * every number (../CLAUDE.md); nothing here is tuned.
 *
 * Header of free functions and plain structs, like SaudFeel.h, so
 * Tools/harness builds it with g++ and checks it (tests/fire.cpp).
 */

#if defined(SAUD_HARNESS)
	#include "HarnessTypes.h"
	#define SAUD_TEXT(s) s
#else
	#include "CoreMinimal.h"
	#define SAUD_TEXT(s) TEXT(s)
#endif

namespace SaudFire
{
#if defined(SAUD_HARNESS)
	using SaudChar = char;
#else
	using SaudChar = TCHAR;
#endif

	// ------------------------------------------------ the browser's numbers
	/** assets/talents.js hawk.mp, exported to DT_Talents.csv (HawkFist,
	    ManaCost). tests/fire.cpp reads the table and holds this to it. */
	constexpr float ManaCost = 14.f;
	/** assets/saud.js base.mp and mpRegen, exported to Player.json
	    (BaseMana, ManaRegenPerSecond, ManaPerLandedHit); the same test. */
	constexpr float MaxMana = 40.f;
	constexpr float ManaRegenPerSecond = 5.f;
	constexpr float ManaPerLandedHit = 4.f;
	/** hawkAttack(), index.html:3848-3853: a lit punch. */
	constexpr float DamageMultiplier = 1.55f;
	constexpr float ReachPx = 10.f;            // browser pixels, the playfield's
	constexpr float PushPx = 90.f;
	/** Tools/export/export.mjs PX_TO_CM: every playfield distance. */
	constexpr float PxToCm = 2.4f;
	constexpr float ReachCm = ReachPx * PxToCm;   // 24
	constexpr float PushCm = PushPx * PxToCm;     // 216
	/** :3727-3728: the flame eases on and off, approach(hawkLit, want,
	    dt * 4.5) -- 0 to 1 in 0.22 s, not the frame MP crosses the cost. */
	constexpr float LitRate = 4.5f;
	/** :2059-2062: brightest through a punch, so the punch reads as the
	    thing that is on fire. */
	constexpr float HeatSwinging = 1.25f;
	constexpr float HeatIdle = 0.78f;

	// -------------------------------------------- the drawing's numbers
	/** handFlame() and applyHit() draw in the browser's FIGURE pixels: a
	    standing fighter is 148 px for his 180 cm (Tools/blender/
	    build_souq.py, the same figure the souq was taken to metres
	    through). Not the playfield's 2.4 cm: a drawn flame is sized against
	    the drawn man. */
	constexpr float FigurePx = 148.f;
	constexpr float FigureCm = 180.f;
	constexpr float CmPerFigurePx = FigureCm / FigurePx;   // 1.216

	/** The flame: three tongues, each narrower and shorter than the last,
	    on a shared wobble, brightest at the core. Widths are half-widths;
	    a tongue starts TongueRootPx behind the fist and runs its length
	    forward along the forearm. */
	constexpr int Tongues = 3;
	constexpr float TongueRootPx = 3.f;
	inline float TongueHalfWidthPx(int Tongue) { return 5.2f - 1.1f * static_cast<float>(Tongue); }
	inline float TongueLengthPx(int Tongue, float Heat) { return (20.f - 4.5f * static_cast<float>(Tongue)) * Heat; }
	constexpr float SwayRate = 11.f;           // radians a second of game time
	constexpr float SwayPhase = 2.1f;          // between tongues
	constexpr float SwayPx = 3.2f;
	inline float Sway(int Tongue, float Seconds)
	{
		return FMath::Sin(Seconds * SwayRate + static_cast<float>(Tongue) * SwayPhase) * SwayPx;
	}
	/** The glow under it: a radial gradient 2 px ahead of the fist, its
	    radius the heat's. */
	constexpr float GlowCentrePx = 2.f;
	constexpr float GlowRadiusPx = 26.f;

	/** The burst on the man a burning punch hit (applyHit :3538-3540):
	    74 px up him -- half the 148 px figure, which is where the engine's
	    actor location is, at the capsule's middle -- a ring growing from 8
	    to 74 px over 0.28 s, and two handfuls of sparks. */
	constexpr float BurstUpPx = 74.f;
	constexpr float RingFromPx = 8.f;
	constexpr float RingToPx = 74.f;
	constexpr float RingSeconds = 0.28f;
	constexpr float RingAlpha = 0.85f;         // drawFx(): (1 - k) * 0.85
	constexpr float RingWidthPx = 6.f;         // lineWidth 6 (1 - k) + 1
	constexpr float RingSquash = 0.62f;        // the ellipse's height over its width
	constexpr int SparksHot = 14;              // rgba(255,168,52) at 300 px/s
	constexpr int SparksPale = 8;              // rgba(255,238,190) at 190 px/s
	constexpr float SparkSpeedHotPx = 300.f;
	constexpr float SparkSpeedPalePx = 190.f;
	constexpr float SparkSpeedShareMin = 0.3f; // burst(): rand(spd * 0.3, spd)
	constexpr float SparkLiftPx = 40.f;        // vy = sin(a) s - 40: thrown a little up
	constexpr float SparkGravityPx = 460.f;    // updateFx(): vy += 460 dt
	/** updateFx(): vx *= 0.96 a frame, which at the browser's 60 Hz is
	    0.96^60 = e^-2.4493 a second; written as the rate so the shader is
	    not frame-rate dependent as the browser is. */
	constexpr float SparkDragPerSecond = 2.4493f;
	constexpr float SparkLifeMin = 0.25f;
	constexpr float SparkLifeMax = 0.55f;
	constexpr float SparkRadiusMin = 2.f;
	constexpr float SparkRadiusMax = 5.f;
	/** The burst is over when the last spark can have died. */
	constexpr float BurstSeconds = SparkLifeMax;

	// ------------------------------------------------------------ the rules
	/** hawkReady(): the talent carried and the MP to burn. */
	inline bool Lit(bool bHasTalent, float Mana)
	{
		return bHasTalent && Mana >= ManaCost;
	}

	/** hawkAttack(): a lit PUNCH burns. A kick with HAWK FIST is still a
	    kick. Decided when the strike starts, as the browser decides it. */
	inline bool Burning(bool bLit, bool bPunch)
	{
		return bLit && bPunch;
	}

	/** The browser's approach(): toward the target by at most Step. */
	inline float Approach(float Value, float Target, float Step)
	{
		return Value < Target ? FMath::Min(Value + Step, Target) : FMath::Max(Value - Step, Target);
	}

	/** How bright the flame is drawn: the eased lit-ness, brighter through
	    a punch. Zero is not drawn at all. */
	inline float Heat(float Lit01, bool bSwingingPunch)
	{
		return Lit01 * (bSwingingPunch ? HeatSwinging : HeatIdle);
	}

	/** Which fist the flame is on: the lead (left) fist while he stands,
	    guards or moves -- the browser draws it on the lead hand -- and the
	    fist a punch is thrown with while he throws it, since the punch is
	    the thing that is on fire. `StrikingSide` is SaudIK::StrikingLimb's
	    side ('l', 'r') or 0 for a strike with no arm. */
	inline char FlameHand(bool bPunching, char StrikingSide)
	{
		return (bPunching && StrikingSide != 0) ? StrikingSide : 'l';
	}

	/** The ring's radius at an age, in figure px; negative once it is gone. */
	inline float RingRadiusPx(float Age)
	{
		if (Age < 0.f || Age >= RingSeconds)
		{
			return -1.f;
		}
		return FMath::Lerp(RingFromPx, RingToPx, Age / RingSeconds);
	}

	// ------------------------------------------------------------ the state
	/** What the game keeps between frames, in GAME time: the browser's
	    flame and particles run in the fight's own clock and stand still
	    through a freeze, unlike the impact frame (SaudAnime), which is the
	    picture's. */
	struct FState
	{
		float Lit01 = 0.f;         // the flame, eased
		float BurstAge = -1.f;     // seconds since the burning hit; -1 for none
		float BurstSeed = 0.f;     // changes per burst, so the sparks do
		float Clock = 0.f;         // for the sway

		void Burn()
		{
			BurstAge = 0.f;
			BurstSeed += 1.f;
		}

		void Tick(float GameSeconds, bool bLit)
		{
			Clock += GameSeconds;
			Lit01 = Approach(Lit01, bLit ? 1.f : 0.f, GameSeconds * LitRate);
			if (BurstAge >= 0.f)
			{
				BurstAge += GameSeconds;
				if (BurstAge >= BurstSeconds)
				{
					BurstAge = -1.f;
				}
			}
		}

		bool Bursting() const { return BurstAge >= 0.f && BurstAge < BurstSeconds; }
	};

	// ------------------------------------------------------------ the names
	/** MPC_Anime's fire parameters, written by USaudLookSubsystem and read
	    by M_Anime_Frame; Tools/look/anime_look.py checks them against this
	    header. Positions are fractions of the viewport (Y down), the
	    direction a unit vector in that space with the aspect applied, the
	    depths the scene depth in cm, and each scale how big one of the
	    browser's figure pixels is there, as a fraction of the viewport's
	    height. */
	namespace Param
	{
		constexpr const SaudChar* FireHeat = SAUD_TEXT("FireHeat");     // 0: no flame
		constexpr const SaudChar* FireX = SAUD_TEXT("FireX");
		constexpr const SaudChar* FireY = SAUD_TEXT("FireY");
		constexpr const SaudChar* FireDirX = SAUD_TEXT("FireDirX");
		constexpr const SaudChar* FireDirY = SAUD_TEXT("FireDirY");
		constexpr const SaudChar* FireDepth = SAUD_TEXT("FireDepth");
		constexpr const SaudChar* FireScale = SAUD_TEXT("FireScale");
		constexpr const SaudChar* FireTime = SAUD_TEXT("FireTime");
		constexpr const SaudChar* BurnAge = SAUD_TEXT("BurnAge");       // < 0: no burst
		constexpr const SaudChar* BurnX = SAUD_TEXT("BurnX");
		constexpr const SaudChar* BurnY = SAUD_TEXT("BurnY");
		constexpr const SaudChar* BurnDepth = SAUD_TEXT("BurnDepth");
		constexpr const SaudChar* BurnScale = SAUD_TEXT("BurnScale");
		constexpr const SaudChar* BurnSeed = SAUD_TEXT("BurnSeed");
	}
}
