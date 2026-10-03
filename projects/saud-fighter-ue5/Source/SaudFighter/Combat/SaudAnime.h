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
 * a block do not. Since 2026-09-28 (the dark seinen) the frame has a tone --
 * a blow's blood, a parry's bone, a burning punch's ember -- and a blow that
 * lands heavy leaves a mark where it landed, and, when it lands on the
 * player, a torn blood border round the screen (the wound).
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

	/** What the look's volume pins in the engine's own post-process
	    (2026-10-03, "improve colors accuracy"): the film curve at UE 5's
	    defaults, set rather than inherited so a level's volume or a project
	    setting cannot make the game differ from the preview, which models
	    exactly this curve (anime_look.FILM, checked against these); and the
	    engine's vignette, bloom, grain and colour fringe off -- the look
	    draws its own vignette in M_Anime_Frame and none of the others, and
	    each would land on the picture before that material sees it. */
	namespace Film
	{
		constexpr float Slope = 0.88f;
		constexpr float Toe = 0.55f;
		constexpr float Shoulder = 0.26f;
		constexpr float BlackClip = 0.0f;
		constexpr float WhiteClip = 0.04f;
		constexpr float BlueCorrection = 0.6f;
		constexpr float ExpandGamut = 1.0f;
		constexpr float ToneCurveAmount = 1.0f;
		constexpr float Vignette = 0.0f;
		constexpr float Bloom = 0.0f;
		constexpr float Grain = 0.0f;
		constexpr float Fringe = 0.0f;
	}

	namespace Param
	{
		constexpr const SaudChar* Impact = SAUD_TEXT("Impact");
		constexpr const SaudChar* ImpactInvert = SAUD_TEXT("ImpactInvert");
		constexpr const SaudChar* Speed = SAUD_TEXT("Speed");
		constexpr const SaudChar* SpeedCentreX = SAUD_TEXT("SpeedCentreX");
		constexpr const SaudChar* SpeedCentreY = SAUD_TEXT("SpeedCentreY");
		constexpr const SaudChar* SpeedSeed = SAUD_TEXT("SpeedSeed");
		constexpr const SaudChar* Key = SAUD_TEXT("Key");
		/** The ink's brush pressure and the film grain move on twos: FState::
		    Seed(), written every tick (SpeedSeed only while the speed lines
		    are up). Since 2026-09-28. */
		constexpr const SaudChar* Boil = SAUD_TEXT("Boil");
		/** Since 2026-09-28, the hit effects of the dark seinen: the impact
		    frame's tone (ETone as a number: 0 blood, 1 ember, 2 bone), the
		    player's wound border, and the mark at the point of contact --
		    its age (-1: none), where it is (viewport fraction, Y down), how
		    deep (cm), one figure pixel there (share of the viewport's
		    height, as the fire's) and its seed. */
		constexpr const SaudChar* ImpactTone = SAUD_TEXT("ImpactTone");
		constexpr const SaudChar* Wound = SAUD_TEXT("Wound");
		constexpr const SaudChar* MarkAge = SAUD_TEXT("MarkAge");
		constexpr const SaudChar* MarkX = SAUD_TEXT("MarkX");
		constexpr const SaudChar* MarkY = SAUD_TEXT("MarkY");
		constexpr const SaudChar* MarkDepth = SAUD_TEXT("MarkDepth");
		constexpr const SaudChar* MarkScale = SAUD_TEXT("MarkScale");
		constexpr const SaudChar* MarkSeed = SAUD_TEXT("MarkSeed");
	}

	// ------------------------------------------------------------- the frame
	constexpr float Frame = 1.f / 24.f;        // one frame of film
	constexpr float OnTwos = 2.f * Frame;      // the speed lines redraw on twos

	/** What the impact frame's light half is, since 2026-09-28 (the dark
	    seinen): a blow's BLOOD, a parry's BONE (the reversal, as paper was),
	    and EMBER only for what burns -- a burning HAWK FIST punch's own
	    frame (FState::MarkBurning). Until that day every impact frame was
	    ember (paper before 2026-09-26). The numbers are what M_Anime_Frame
	    reads from MPC_Anime.ImpactTone. */
	enum class ETone : unsigned char { Blood = 0, Ember = 1, Bone = 2 };

	/** An impact frame's shape: how long, which of its halves are the
	    flipped one (ink for its tone), and its tone. */
	struct FImpact
	{
		float Seconds = 0.f;
		bool bInvertFirst = false;
		bool bInvertSecond = false;
		ETone Tone = ETone::Blood;
	};

	/** The mark at the point of contact (since 2026-09-28): a bone needle
	    star with an ink edge, full for MarkHold -- at least the heavy freeze,
	    SaudFeel::HitStopHeavy, so it stands for the whole of it -- shrinking
	    to nothing at MarkSpark, and blood drops flung out of it and falling,
	    gone at MarkSeconds. Heavy clean hits and knockdowns only. */
	constexpr float MarkHold = 2.f * Frame;
	constexpr float MarkSpark = 4.f * Frame;
	constexpr float MarkSeconds = 6.f * Frame;

	/** The wound: a torn blood border round the screen when the PLAYER is
	    hit heavy or knocked down -- the "you were hurt" the picture had no
	    cue for. Full for one film frame, then straight down to nothing at
	    WoundSeconds. */
	constexpr float WoundSeconds = 0.30f;
	constexpr float WoundHold = Frame;

	/** What one blow asks of the picture. */
	struct FBlowLook
	{
		FImpact Impact;
		float SpeedSeconds = 0.f;   // how long the speed lines stay
		float MarkLife = 0.f;       // MarkSeconds, or 0: no mark
		float WoundAmp = 0.f;       // 1 when the player is the one hit, or 0
	};

	/** Heavy clean hit: one frame of ink and blood, a mark where it landed.
	    Knockdown: two, the second flipped -- the cut to black a fall gets --
	    and a mark. Parry: two in bone, the first flipped, because the parry
	    is the reversal; no mark (nothing landed). Light hits and blocks:
	    nothing, so the big ones stay big. The wound only when the man hit is
	    the player (bVictimIsPlayer; defaulted so a caller that does not say
	    never wounds). */
	inline FBlowLook ForBlow(bool bHeavy, bool bBlocked, bool bParried, bool bKnockdown,
	                         bool bVictimIsPlayer = false)
	{
		FBlowLook L;
		if (bParried)
		{
			L.Impact = {2.f * Frame, true, false, ETone::Bone};
			L.SpeedSeconds = 0.30f;
			return L;
		}
		if (bBlocked)
		{
			return L;
		}
		if (bKnockdown)
		{
			L.Impact = {2.f * Frame, false, true, ETone::Blood};
			L.SpeedSeconds = 0.45f;
		}
		else if (bHeavy)
		{
			L.Impact = {Frame, false, false, ETone::Blood};
			L.SpeedSeconds = 0.30f;
		}
		else
		{
			return L;   // a light hit
		}
		L.MarkLife = MarkSeconds;
		if (bVictimIsPlayer)
		{
			L.WoundAmp = 1.f;
		}
		return L;
	}

	/** Share of the speed lines' life they are at full strength before they
	    start to thin. */
	constexpr float SpeedHold = 0.35f;

	/** The picture's state between frames. Like SaudFeel::FState, a blow
	    only ever makes it bigger: a longer impact replaces a shorter one
	    that is running, never the other way; so does a wound. A new mark
	    always restarts the mark (it is where the new blow landed). */
	struct FState
	{
		FImpact Impact;
		float ImpactElapsed = 0.f;
		float SpeedTotal = 0.f;
		float SpeedElapsed = 0.f;
		float MarkTotal = 0.f;
		float MarkElapsed = 0.f;
		int MarkSerial = 0;          // one more for every mark: its seed
		float WoundAmp = 0.f;
		float WoundElapsed = 0.f;
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
			if (L.MarkLife > 0.f)
			{
				MarkTotal = L.MarkLife;
				MarkElapsed = 0.f;
				MarkSerial = (MarkSerial + 1) % 997;
			}
			if (L.WoundAmp > 0.f && L.WoundAmp >= WoundValue())
			{
				WoundAmp = L.WoundAmp;
				WoundElapsed = 0.f;
			}
		}

		void Tick(float RealSeconds)
		{
			Clock += RealSeconds;
			ImpactElapsed = FMath::Min(ImpactElapsed + RealSeconds, Impact.Seconds);
			SpeedElapsed = FMath::Min(SpeedElapsed + RealSeconds, SpeedTotal);
			MarkElapsed = FMath::Min(MarkElapsed + RealSeconds, MarkTotal);
			WoundElapsed = FMath::Min(WoundElapsed + RealSeconds, WoundSeconds);
		}

		/** A burning HAWK FIST punch: the impact frame this same blow just
		    started goes ember. OnBurn arrives after OnBlow in the one call
		    (AFighterBase::ReceiveHit, then OnHitLanded -- anime_look.py
		    checks that order in the source), so the frame is still on its
		    first tick; a frame already running, and a parry's bone, are left
		    alone. */
		void MarkBurning()
		{
			if (Impact.Seconds > 0.f && ImpactElapsed <= 0.f && Impact.Tone == ETone::Blood)
			{
				Impact.Tone = ETone::Ember;
			}
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

		/** The impact frame's tone, as MPC_Anime.ImpactTone: 0 when none. */
		float ToneValue() const
		{
			return ImpactValue() > 0.f ? static_cast<float>(static_cast<int>(Impact.Tone)) : 0.f;
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

		/** Seconds since the mark was made, in real time; -1 when there is
		    none (M_Anime_Frame draws nothing at a negative age). */
		float MarkAge() const
		{
			return MarkElapsed < MarkTotal ? MarkElapsed : -1.f;
		}

		/** A new star and new drops for every mark. */
		float MarkSeed() const
		{
			return static_cast<float>(MarkSerial);
		}

		/** The wound border's strength: its blow's amp for WoundHold, then
		    straight down to 0 at WoundSeconds. */
		float WoundValue() const
		{
			if (WoundAmp <= 0.f || WoundElapsed >= WoundSeconds)
			{
				return 0.f;
			}
			if (WoundElapsed < WoundHold)
			{
				return WoundAmp;
			}
			return WoundAmp * (1.f - (WoundElapsed - WoundHold) / (WoundSeconds - WoundHold));
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
 * The look, since 2026-09-28 ("make all game like dark anime adult style"):
 * a dark seinen's page, not a box HUD. No plates and no keylines round
 * panels: Saud's corner is an ink-wash sweep, torn top and bottom and fading
 * out across the page, with his name, his rage as five leaning cuts, his
 * stamina in ash and his health in blood -- every bar a slash leaning 0.55
 * of its height in an ink keyline, the damage trail in bone, and at low
 * health blood drips hanging under it. The combo is an ink-rimmed blood
 * splat with the count in bone. A boss is named on a manga title panel: an
 * ink band that wipes open, a blood slash behind his name. From 2026-09-26
 * to that day it was a dark fantasy's (dark translucent plates in a bronze
 * keyline, thin flat bars, a sixteen-point seal); before that a manga
 * page's (paper panels, heavy ink borders, a twelve-point starburst).
 *
 * The whole picture is one pure function, Build(): it emits every triangle
 * (with a colour per vertex) and every text item, and SaudHUD.cpp only
 * rasterises that list. So the harness checks what is DRAWN -- every
 * vertex inside title-safe, the groups apart, the contrast, the capacity --
 * and Tools/look/hud_preview.py draws it without an engine
 * (Tools/harness/hud_dump.cpp prints it).
 */
namespace SaudHud
{
	constexpr float PageW = 1920.f;
	constexpr float PageH = 1080.f;
	constexpr float Safe = 0.05f;               // title-safe margin, each side
	constexpr float Ink = 3.f;                  // a bar's ink keyline, page px (2 until 2026-09-28, 5 until 2026-09-26)
	constexpr float Lean = 0.55f;               // bars lean this share of their height (flat 2026-09-26 to -28; 0.45 before)
	constexpr float TextStroke = 3.f;           // the ink round every letter, page px: 2 screen px at 720 lines

	constexpr float NameText = 46.f;            // page pixels, cap height class (36 until 2026-09-28)
	constexpr float ComboText = 112.f;          // (104)
	constexpr float BossNameText = 56.f;        // (40)
	constexpr float HitsText = 34.f;            // "HITS" (NameText * 0.9 before)
	/** Nothing the player must read is smaller than this share of the
	    screen's height: about 30 px at 1080, legible at three metres. */
	constexpr float MinTextShare = 1.f / 36.f;

	constexpr int RageBlocks = 5;

	struct FPoint { float X = 0.f, Y = 0.f; };
	struct FRect { float X = 0.f, Y = 0.f, W = 0.f, H = 0.f; };

	/** A colour in LINEAR light, and its alpha. */
	struct FRgba { float R = 0.f, G = 0.f, B = 0.f, A = 1.f; };

	/** The HUD's palette, linear. Ink, Bone, Blood and Ember are the look's
	    own (Tools/look/anime_look.py LOOK INK, BONE, BLOOD and EMBER, which
	    checks these four against its own), so the HUD, the impact frame and
	    the speed lines are one blood and one ink. Every bar is at least 3:1
	    against the trough it sits in (WCAG 2.1 1.4.11, checked in the
	    harness from these numbers): blood 3.03, ash 4.96, gold 4.08, ember
	    6.0; the bone trail 3.36 against the blood; bone lettering 11.0
	    against its ink stroke. */
	namespace Colour
	{
		constexpr FRgba Ink{0.0022f, 0.0019f, 0.0017f, 1.f};
		constexpr FRgba Bone{0.56f, 0.52f, 0.44f, 1.f};
		constexpr FRgba Blood{0.5271f, 0.0103f, 0.0137f, 1.f};   // #C01A1F (health was #9B1616, 2.07:1)
		constexpr FRgba Ember{0.74f, 0.18f, 0.042f, 1.f};
		constexpr FRgba Trough{0.006f, 0.006f, 0.008f, 1.f};
		constexpr FRgba Ash{0.2541f, 0.2270f, 0.1714f, 1.f};     // #8A8374, stamina (moss #4A6E33 was 2.93:1)
		constexpr FRgba Gold{0.3515f, 0.1441f, 0.0160f, 1.f};    // #A06A22, rage
	}

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

	// ------------------------------------------------------------ the layout
	// Page px, from the safe corner they hang off.
	constexpr float WashW = 700.f, WashH = 156.f;       // Saud's ink-wash sweep
	constexpr float WashAlpha = 0.86f;
	constexpr float WashFadeFrom = 0.50f;               // fades to nothing over the rest of its width
	constexpr float TearPx = 7.f;                       // a torn edge bites this deep...
	constexpr float PitchPx = 14.f;                     // ...every this far along
	constexpr float ComboRadius = 124.f;                // (118 until 2026-09-28)
	constexpr float ComboFromRight = 172.f;             // the splat's centre, in from the right safe line
	constexpr float ComboDown = 300.f;                  // ...and down from the top one
	constexpr float BannerW = 1120.f, BannerH = 104.f;  // the boss's title panel, bottom on the safe line
	constexpr float BannerAlpha = 0.85f;
	constexpr float BannerRevealSeconds = 0.40f;        // the band wipes open when he is first seen...
	constexpr float BannerCutInSeconds = 0.20f;         // ...and his name and the slash cut in here
	constexpr float SlashLean = 1.0f;
	constexpr float SlashAlpha = 0.92f;
	constexpr float EnemyBarW = 124.f, EnemyBarH = 10.f;   // over a street man (110 x 7 before)
	constexpr float EnemyInk = 1.5f;                    // its keyline, page px
	/** At or under this share of health, blood drips hang under the bar. */
	constexpr float DripBelow = 0.30f;
	constexpr float DripMaxPx = 26.f;                   // how far a drip hangs, page px
	constexpr float DripWidthPx = 5.f;
	constexpr float DripCycleSeconds = 1.4f;            // grows over 80 % of it, then drops off

	struct FLayout
	{
		FRect Wash;
		FPoint Name;
		FRect Rage[RageBlocks];
		FRect Stamina;
		FRect Health;
		FPoint Combo;
		float ComboR = 0.f;
		FRect Banner;
		FRect Slash;
		FPoint BossName;
		FRect BossBar;
		float EnemyBarW = 0.f, EnemyBarH = 0.f;
	};

	inline FLayout Lay(const FPage& P)
	{
		FLayout L;
		const float X = P.Left(), Y = P.Top();
		L.Wash = {X, Y, P.Px(WashW), P.Px(WashH)};
		L.Name = {X + P.Px(26.f), Y + P.Px(10.f)};
		for (int i = 0; i < RageBlocks; ++i)
		{
			L.Rage[i] = {X + P.Px(232.f + 36.f * static_cast<float>(i)), Y + P.Px(24.f), P.Px(28.f), P.Px(20.f)};
		}
		L.Stamina = {X + P.Px(26.f), Y + P.Px(72.f), P.Px(440.f), P.Px(12.f)};
		L.Health = {X + P.Px(26.f), Y + P.Px(94.f), P.Px(620.f), P.Px(28.f)};
		L.ComboR = P.Px(ComboRadius);
		L.Combo = {P.Right() - P.Px(ComboFromRight), Y + P.Px(ComboDown)};
		const float BW = P.Px(BannerW), BH = P.Px(BannerH);
		L.Banner = {0.5f * P.ScreenW - 0.5f * BW, P.Bottom() - BH, BW, BH};
		L.Slash = {L.Banner.X + P.Px(22.f), L.Banner.Y + P.Px(8.f), P.Px(500.f), P.Px(50.f)};
		L.BossName = {L.Banner.X + P.Px(46.f), L.Banner.Y + P.Px(4.f)};
		L.BossBar = {L.Banner.X + P.Px(40.f), L.Banner.Y + P.Px(68.f), BW - P.Px(80.f), P.Px(22.f)};
		L.EnemyBarW = P.Px(EnemyBarW);
		L.EnemyBarH = P.Px(EnemyBarH);
		return L;
	}

	/** A slanted quad's four corners, clockwise from the bottom left,
	    leaning right by LeanShare of its height; Fill of the way along. */
	inline void LeanQuad(const FRect& R, float Fill, float LeanShare, FPoint Out[4])
	{
		const float F = FMath::Clamp(Fill, 0.f, 1.f);
		const float S = R.H * LeanShare;
		const float W = (R.W - S) * F;
		Out[0] = {R.X, R.Y + R.H};
		Out[1] = {R.X + S, R.Y};
		Out[2] = {R.X + S + W, R.Y};
		Out[3] = {R.X + W, R.Y + R.H};
	}

	/** A bar's filled part, at the bars' Lean. Fill 0 is a line, not
	    nothing, so a caller can always ask for it (Build draws none). */
	inline void BarQuad(const FRect& R, float Fill, FPoint Out[4])
	{
		LeanQuad(R, Fill, Lean, Out);
	}

	/** The bone trail behind a bar that has just been cut: it holds where
	    the bar was for a beat, then drains down to it. A bar that rises (a
	    heal) is followed at once. */
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

	/** How full each of the rage meter's cuts is. */
	inline float RageBlock(float RageFraction, int Index)
	{
		return FMath::Clamp(FMath::Clamp(RageFraction, 0.f, 1.f) * RageBlocks - static_cast<float>(Index), 0.f, 1.f);
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

	// ---------------------------------------------------------------- hashes
	/** floor() and the speed lines' own hash, frac(sin(i * 12.9898 + seed *
	    78.233) * 43758.5453): the torn edges and the splat are the same kind
	    of random as the lines. Only the HUD's own shapes use them, and the
	    preview draws what the C++ emits, so no second copy has to agree. */
	inline float FloorF(float V)
	{
		const float T = static_cast<float>(static_cast<int>(V));
		return T > V ? T - 1.f : T;
	}
	inline float HudHash(float I, float Seed)
	{
		const float S = FMath::Sin(I * 12.9898f + Seed * 78.233f) * 43758.5453f;
		return S - FloorF(S);
	}

	// ------------------------------------------------------------ the splat
	/** The combo's blood splat: 2 * SplatTips points alternating tips (0.84
	    to 1.00 of its radius) and valleys (0.62 to 0.70), jittered by the
	    count and turned 7 degrees per hit, so a rising count visibly moves.
	    (A sixteen-point seal from 2026-09-26, a twelve-point starburst
	    before.) */
	constexpr int SplatTips = 22;
	constexpr float SplatCore = 0.58f;                  // the ink disc under the count, share of R
	constexpr float SplatCoreAlpha = 0.94f;
	constexpr int SplatDrops = 5;
	/** The ink rim round the splat and its drops, in units of Ink: 3 page
	    px, 2 screen px at 720 lines, so the blood reads on a blood impact
	    frame (the HUD is not cut by it). */
	constexpr float SplatRim = 1.f;

	inline FPoint SplatPoint(const FPoint& Centre, float Radius, int Count, int i)
	{
		const float Turn = FMath::DegreesToRadians(7.f * static_cast<float>(Count));
		const float A = Turn + static_cast<float>(i) * 3.14159265f / static_cast<float>(SplatTips);
		const float J = HudHash(static_cast<float>(i + 3 * Count), 4.f);
		const float R = (i % 2 == 0) ? Radius * (0.84f + 0.16f * J) : Radius * (0.62f + 0.08f * J);
		return {Centre.X + R * FMath::Cos(A), Centre.Y + R * FMath::Sin(A)};
	}

	// ----------------------------------------------------------- the list
	enum class EHudGroup : unsigned char { Player, Combo, Boss, Street };
	/** What a triangle is part of: the harness finds each rule's shapes by
	    it (the backing for coverage, the rim, the drips, the fill). */
	enum class EHudPart : unsigned char
	{
		Wash, Band, Keyline, Trough, Trail, Fill, Drip, Rim, Splat, Core, Slash
	};
	/** Which string a text item is: SaudHUD.cpp has the strings (the name,
	    the count, "HITS", the boss's DisplayName); none is invented here. */
	enum class EHudText : unsigned char { Name, Count, Hits, BossName };

	struct FHudVert { FPoint P; FRgba C; };
	struct FHudTri { FHudVert V[3]; EHudGroup Group = EHudGroup::Player; EHudPart Part = EHudPart::Wash; };
	struct FHudText
	{
		EHudText Slot = EHudText::Name;
		int Value = 0;               // the count, for EHudText::Count
		FPoint At;                   // top left, or top centre when bCentre
		float Height = 0.f;          // screen px
		FRgba Colour;
		float Stroke = 0.f;          // the ink round it, screen px
		bool bCentre = false;
		EHudGroup Group = EHudGroup::Player;
		int TrisBefore = 0;          // drawn after this many triangles: order is kept
	};

	constexpr int MaxTris = 1024;
	constexpr int MaxTexts = 8;
	constexpr int MaxStreetBars = 12;

	/** Fixed capacity, no allocation. A shape that does not fit is dropped
	    and bOverflow says so; the harness holds the worst case well under. */
	struct FDrawList
	{
		FHudTri Tris[MaxTris];
		int NumTris = 0;
		FHudText Texts[MaxTexts];
		int NumTexts = 0;
		bool bOverflow = false;

		void Reset() { NumTris = 0; NumTexts = 0; bOverflow = false; }

		void Tri(const FPoint& A, const FRgba& CA, const FPoint& B, const FRgba& CB, const FPoint& C,
		         const FRgba& CC, EHudGroup G, EHudPart Pt)
		{
			if (NumTris >= MaxTris)
			{
				bOverflow = true;
				return;
			}
			FHudTri& T = Tris[NumTris++];
			T.V[0] = {A, CA};
			T.V[1] = {B, CB};
			T.V[2] = {C, CC};
			T.Group = G;
			T.Part = Pt;
		}
		/** A quad as two triangles, corners in order round it. */
		void Quad(const FPoint Q[4], const FRgba C[4], EHudGroup G, EHudPart Pt)
		{
			Tri(Q[0], C[0], Q[1], C[1], Q[2], C[2], G, Pt);
			Tri(Q[0], C[0], Q[2], C[2], Q[3], C[3], G, Pt);
		}
		void Quad(const FPoint Q[4], const FRgba& C, EHudGroup G, EHudPart Pt)
		{
			const FRgba Cs[4] = {C, C, C, C};
			Quad(Q, Cs, G, Pt);
		}
		/** A polygon star-shaped about Centre, as a fan from it. */
		void Fan(const FPoint& Centre, const FPoint* Ring, int N, const FRgba& C, EHudGroup G, EHudPart Pt)
		{
			for (int i = 0; i < N; ++i)
			{
				Tri(Centre, C, Ring[i], C, Ring[(i + 1) % N], C, G, Pt);
			}
		}
		void Text(EHudText Slot, int Value, const FPoint& At, float Height, const FRgba& C, float Stroke,
		          bool bCentre, EHudGroup G)
		{
			if (NumTexts >= MaxTexts)
			{
				bOverflow = true;
				return;
			}
			FHudText& T = Texts[NumTexts++];
			T.Slot = Slot;
			T.Value = Value;
			T.At = At;
			T.Height = Height;
			T.Colour = C;
			T.Stroke = Stroke;
			T.bCentre = bCentre;
			T.Group = G;
			T.TrisBefore = NumTris;
		}
	};

	/** Everything the HUD shows, as plain data: SaudHUD.cpp gathers it from
	    the game each frame, the harness and hud_dump make it up. */
	struct FStreetBar { float X = 0.f, Y = 0.f, Fill = 1.f, Ghost = 1.f; };   // X, Y: screen px over his head
	struct FHudState
	{
		bool bPlayer = true;
		float Health = 1.f, Ghost = 1.f, Stamina = 1.f, Rage = 0.f;
		bool bRageReady = false;
		int Combo = 0;
		float SinceCombo = 1000.f;         // seconds since the count last went up
		bool bBoss = false;
		float BossHealth = 1.f, BossGhost = 1.f;
		bool bBossEnraged = false;
		float BossSince = 1000.f;          // seconds since he was first seen: the banner's reveal
		FStreetBar Street[MaxStreetBars];
		int NumStreet = 0;
		float Clock = 0.f;                 // real seconds: the rage pulse and the drips
	};

	inline FRgba WithAlpha(FRgba C, float A)
	{
		C.A = A;
		return C;
	}
	inline FRgba LerpColour(const FRgba& A, const FRgba& B, float T)
	{
		return {FMath::Lerp(A.R, B.R, T), FMath::Lerp(A.G, B.G, T), FMath::Lerp(A.B, B.B, T), FMath::Lerp(A.A, B.A, T)};
	}
	inline FRect Grow(const FRect& R, float B)
	{
		return {R.X - B, R.Y - B, R.W + 2.f * B, R.H + 2.f * B};
	}

	/** An ink strip with torn edges: columns every PitchPx, each edge bitten
	    inward only by up to TearPx (the speed lines' hash), full AlphaFrom
	    of its alpha to FadeFrom of its width and then fading to nothing
	    (smoothstep) at its end. ClipW, when under R.W, cuts it off there:
	    a band wiping open keeps its tears where they are. */
	inline void TornStrip(FDrawList& Out, const FPage& P, const FRect& R, float Seed, float Alpha, float FadeFrom,
	                      bool bTornBottom, float ClipW, EHudGroup G, EHudPart Pt)
	{
		const int N = static_cast<int>(FMath::Max(2.f, FloorF(R.W / P.Px(PitchPx) + 0.5f))) + 1;
		const float Tear = P.Px(TearPx);
		const float Stop = R.X + FMath::Clamp(ClipW, 0.f, R.W);
		FPoint PrevT, PrevB;
		FRgba PrevC;
		for (int i = 0; i < N; ++i)
		{
			const float U = static_cast<float>(i) / static_cast<float>(N - 1);
			float X = R.X + R.W * U;
			float Yt = R.Y + Tear * HudHash(static_cast<float>(i), Seed);
			float Yb = R.Y + R.H - (bTornBottom ? Tear * HudHash(static_cast<float>(i + 500), Seed) : 0.f);
			const float K = U <= FadeFrom ? 0.f : FMath::Clamp((U - FadeFrom) / (1.f - FadeFrom), 0.f, 1.f);
			float A = Alpha * (1.f - K * K * (3.f - 2.f * K));
			bool bLast = false;
			if (i > 0 && X > Stop)
			{
				// the column that straddles the clip: cut it there
				const float T = (Stop - PrevT.X) / FMath::Max(X - PrevT.X, 1e-6f);
				Yt = FMath::Lerp(PrevT.Y, Yt, T);
				Yb = FMath::Lerp(PrevB.Y, Yb, T);
				A = FMath::Lerp(PrevC.A, A, T);
				X = Stop;
				bLast = true;
			}
			const FPoint Tp = {X, Yt}, Bt = {X, Yb};
			const FRgba C = WithAlpha(Colour::Ink, A);
			if (i > 0 && X - PrevT.X > 0.25f)
			{
				const FPoint Q[4] = {PrevT, Tp, Bt, PrevB};
				const FRgba Cs[4] = {PrevC, C, C, PrevC};
				Out.Quad(Q, Cs, G, Pt);
			}
			PrevT = Tp;
			PrevB = Bt;
			PrevC = C;
			if (bLast)
			{
				break;
			}
		}
	}

	/** A leaning bar: an ink keyline grown by KeyPx round it, the trough,
	    the bone trail where the bar was (Ghost), then the fill. ClipW, when
	    under R.W, cuts the whole bar off there -- clipped, never squeezed,
	    so it never shows more health than there is. */
	inline void SlashBar(FDrawList& Out, const FRect& R, float Fill, float Ghost, const FRgba& C, float KeyPx,
	                     float ClipW, EHudGroup G)
	{
		const float S = R.H * Lean;
		const float W = FMath::Min(R.W, ClipW);
		if (W <= S + 1.f)
		{
			return;
		}
		// a share of the visible bar that ends where the true one would
		const float Span = (R.W - S) / (W - S);
		const FRect V = {R.X, R.Y, W, R.H};
		FPoint Q[4];
		LeanQuad(Grow(V, KeyPx), 1.f, Lean, Q);
		Out.Quad(Q, Colour::Ink, G, EHudPart::Keyline);
		BarQuad(V, 1.f, Q);
		Out.Quad(Q, Colour::Trough, G, EHudPart::Trough);
		const float F = FMath::Clamp(Fill, 0.f, 1.f) * Span;
		const float Gh = FMath::Clamp(Ghost, 0.f, 1.f) * Span;
		const float MinShare = 0.5f / FMath::Max(W - S, 1.f);   // under half a pixel is not drawn
		if (Gh > F + MinShare)
		{
			BarQuad(V, Gh, Q);
			Out.Quad(Q, WithAlpha(Colour::Bone, 0.9f), G, EHudPart::Trail);
		}
		if (F > MinShare)
		{
			BarQuad(V, F, Q);
			Out.Quad(Q, C, G, EHudPart::Fill);
		}
	}

	/** Blood hanging under a bar at or under DripBelow: three drips under
	    the filled part, at 22, 58 and 86 % of it, each growing to DripMaxPx
	    over 80 % of its own DripCycleSeconds and then dropping off (its top
	    falls to its tip). Never lower than DripMaxPx under the bar. */
	inline void Drips(FDrawList& Out, const FPage& P, const FRect& R, float Fill, float Clock, EHudGroup G)
	{
		if (Fill > DripBelow || Fill <= 0.f)
		{
			return;
		}
		const float W = (R.W - R.H * Lean) * FMath::Clamp(Fill, 0.f, 1.f);   // the fill's bottom edge
		const float Half = 0.5f * P.Px(DripWidthPx);
		if (W < 2.f * Half + 1.f)
		{
			return;
		}
		const float Us[3] = {0.22f, 0.58f, 0.86f};
		const float Base = R.Y + R.H, Longest = P.Px(DripMaxPx);
		for (int k = 0; k < 3; ++k)
		{
			const float X = FMath::Clamp(R.X + Us[k] * W, R.X + Half, R.X + W - Half);
			const float Ph0 = Clock / DripCycleSeconds + HudHash(static_cast<float>(k), 9.f);
			const float Ph = Ph0 - FloorF(Ph0);
			const float Tip = Base + (Ph < 0.8f ? Longest * Ph / 0.8f : Longest);
			const float Top = Ph < 0.8f ? Base : Base + Longest * (Ph - 0.8f) / 0.2f;
			if (Tip - Top < 2.f * Half)
			{
				continue;
			}
			// a stem and a round end: the stem to one half-width above the
			// tip, and a half disc under it
			const float Neck = Tip - Half;
			const FPoint Q[4] = {{X - Half, Top}, {X + Half, Top}, {X + Half, Neck}, {X - Half, Neck}};
			Out.Quad(Q, Colour::Blood, G, EHudPart::Drip);
			FPoint Arc[8];
			for (int j = 0; j < 7; ++j)
			{
				const float A = 3.14159265f * static_cast<float>(j) / 6.f;
				Arc[j] = {X + Half * FMath::Cos(A), Neck + Half * FMath::Sin(A)};
			}
			for (int j = 0; j < 6; ++j)
			{
				Out.Tri({X, Neck}, Colour::Blood, Arc[j], Colour::Blood, Arc[j + 1], Colour::Blood, G, EHudPart::Drip);
			}
		}
	}

	/** A polygon grown outward by D along its corners' bisectors (a mitred
	    offset; the mitre held to five times D, where the splat's sharpest
	    tip needs 4.5), for a ring given in screen winding order round a
	    centre. */
	inline void GrowRing(const FPoint* In, int N, float D, FPoint* Out)
	{
		for (int i = 0; i < N; ++i)
		{
			const FPoint& A = In[(i + N - 1) % N];
			const FPoint& B = In[i];
			const FPoint& C = In[(i + 1) % N];
			// outward normals of the edges A->B and B->C: with Y down and
			// the ring turning clockwise on the screen, (dy, -dx)
			float Ax = B.Y - A.Y, Ay = -(B.X - A.X);
			float Cx = C.Y - B.Y, Cy = -(C.X - B.X);
			const float La = FMath::Max(FMath::Sqrt(Ax * Ax + Ay * Ay), 1e-6f);
			const float Lc = FMath::Max(FMath::Sqrt(Cx * Cx + Cy * Cy), 1e-6f);
			Ax /= La; Ay /= La; Cx /= Lc; Cy /= Lc;
			float Mx = Ax + Cx, My = Ay + Cy;
			const float Lm = FMath::Max(FMath::Sqrt(Mx * Mx + My * My), 1e-6f);
			Mx /= Lm; My /= Lm;
			const float Cos = FMath::Max(Mx * Ax + My * Ay, 0.2f);   // the mitre: D / cos(half the turn)
			Out[i] = {B.X + Mx * D / Cos, B.Y + My * D / Cos};
		}
	}

	/** The combo: an ink rim, the blood splat, its drops (each ink-rimmed),
	    and an ink disc for the count to sit on. */
	inline void Splat(FDrawList& Out, const FPage& P, const FPoint& Centre, float R, int Count, EHudGroup G)
	{
		constexpr int N = 2 * SplatTips;
		FPoint Ring[N], Rim[N];
		for (int i = 0; i < N; ++i)
		{
			Ring[i] = SplatPoint(Centre, R, Count, i);
		}
		const float RimPx = P.Px(Ink * SplatRim);
		GrowRing(Ring, N, RimPx, Rim);
		Out.Fan(Centre, Rim, N, Colour::Ink, G, EHudPart::Rim);
		Out.Fan(Centre, Ring, N, Colour::Blood, G, EHudPart::Splat);
		const float Turn = FMath::DegreesToRadians(7.f * static_cast<float>(Count));
		for (int k = 0; k < SplatDrops; ++k)
		{
			const float A = Turn + 6.2831853f * HudHash(static_cast<float>(k + 40), 4.f);
			const float D = R * (1.08f + 0.12f * HudHash(static_cast<float>(k + 50), 4.f));
			const float Rd = R * (0.04f + 0.03f * HudHash(static_cast<float>(k + 60), 4.f));
			const FPoint At = {Centre.X + D * FMath::Cos(A), Centre.Y + D * FMath::Sin(A)};
			FPoint Drop[12], DropRim[12];
			for (int j = 0; j < 12; ++j)
			{
				const float B = 6.2831853f * static_cast<float>(j) / 12.f;
				Drop[j] = {At.X + Rd * FMath::Cos(B), At.Y + Rd * FMath::Sin(B)};
			}
			GrowRing(Drop, 12, RimPx, DropRim);
			Out.Fan(At, DropRim, 12, Colour::Ink, G, EHudPart::Rim);
			Out.Fan(At, Drop, 12, Colour::Blood, G, EHudPart::Splat);
		}
		FPoint Core[24];
		for (int j = 0; j < 24; ++j)
		{
			const float B = 6.2831853f * static_cast<float>(j) / 24.f;
			Core[j] = {Centre.X + SplatCore * R * FMath::Cos(B), Centre.Y + SplatCore * R * FMath::Sin(B)};
		}
		Out.Fan(Centre, Core, 24, WithAlpha(Colour::Ink, SplatCoreAlpha), G, EHudPart::Core);
	}

	/** The whole HUD for one frame: street bars under everything, then
	    Saud's corner, the combo, the boss's banner. Pure: the same state and
	    page give the same list. */
	inline void Build(const FPage& P, const FHudState& S, FDrawList& Out)
	{
		Out.Reset();
		const FLayout L = Lay(P);
		const float Key = FMath::Max(1.f, P.Px(Ink));

		// Over a street man's head, for a while after he is hit.
		const int NumStreet = S.NumStreet < MaxStreetBars ? S.NumStreet : MaxStreetBars;
		for (int i = 0; i < NumStreet; ++i)
		{
			const FStreetBar& B = S.Street[i];
			const FRect R = {B.X - 0.5f * L.EnemyBarW, B.Y, L.EnemyBarW, L.EnemyBarH};
			SlashBar(Out, R, B.Fill, B.Ghost, Colour::Blood, FMath::Max(1.f, P.Px(EnemyInk)), R.W, EHudGroup::Street);
		}

		if (S.bPlayer)
		{
			const EHudGroup G = EHudGroup::Player;
			TornStrip(Out, P, L.Wash, 1.f, WashAlpha, WashFadeFrom, true, L.Wash.W, G, EHudPart::Wash);
			Out.Text(EHudText::Name, 0, L.Name, P.Px(NameText), Colour::Bone, P.Px(TextStroke), false, G);
			// rage: five leaning cuts, gold, glowing toward ember and pulsing
			// once all five are full -- the finisher is ready
			const float Pulse = S.bRageReady ? 0.5f + 0.5f * FMath::Sin(S.Clock * 9.f) : 0.f;
			const FRgba RageC = S.bRageReady ? LerpColour(Colour::Gold, Colour::Ember, 0.4f + 0.6f * Pulse) : Colour::Gold;
			for (int i = 0; i < RageBlocks; ++i)
			{
				SlashBar(Out, L.Rage[i], RageBlock(S.Rage, i), 0.f, RageC, Key, L.Rage[i].W, G);
			}
			SlashBar(Out, L.Stamina, S.Stamina, 0.f, Colour::Ash, Key, L.Stamina.W, G);
			SlashBar(Out, L.Health, S.Health, S.Ghost, Colour::Blood, Key, L.Health.W, G);
			Drips(Out, P, L.Health, S.Health, S.Clock, G);
		}

		if (S.Combo >= 2)
		{
			const EHudGroup G = EHudGroup::Combo;
			const float Punch = ComboPunch(S.SinceCombo);
			const float R = L.ComboR * (0.85f + 0.15f * Punch);
			Splat(Out, P, L.Combo, R, S.Combo, G);
			const float H = P.Px(ComboText) * 0.8f * Punch;
			Out.Text(EHudText::Count, S.Combo, {L.Combo.X, L.Combo.Y - 0.62f * H}, H, Colour::Bone, P.Px(TextStroke), true, G);
			Out.Text(EHudText::Hits, 0, {L.Combo.X, L.Combo.Y + 0.42f * H}, P.Px(HitsText), Colour::Bone,
			         P.Px(TextStroke), true, G);
		}

		if (S.bBoss)
		{
			const EHudGroup G = EHudGroup::Boss;
			// the band wipes open (ease-out cubic) when he is first seen
			const float T = FMath::Clamp(S.BossSince / BannerRevealSeconds, 0.f, 1.f);
			const float Open = 1.f - (1.f - T) * (1.f - T) * (1.f - T);
			const float Shown = L.Banner.W * Open;
			TornStrip(Out, P, L.Banner, 2.f, BannerAlpha, 0.92f, false, Shown, G, EHudPart::Band);
			if (S.BossSince >= BannerCutInSeconds)
			{
				FPoint Q[4];
				LeanQuad(L.Slash, 1.f, SlashLean, Q);
				Out.Quad(Q, WithAlpha(S.bBossEnraged ? Colour::Ember : Colour::Blood, SlashAlpha), G, EHudPart::Slash);
				Out.Text(EHudText::BossName, 0, L.BossName, P.Px(BossNameText), Colour::Bone, P.Px(TextStroke), false, G);
			}
			SlashBar(Out, L.BossBar, S.BossHealth, S.BossGhost, Colour::Blood, Key,
			         Shown - (L.BossBar.X - L.Banner.X), G);
		}
	}
}
