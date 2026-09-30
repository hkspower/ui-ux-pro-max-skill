#pragma once

/**
 * The main menu, the pause, the settings and the controls screen -- as
 * plain data and pure functions, with no engine in it.
 *
 * Asked 2026-09-30 (Riyadh) as "improve main menu" and "improve buttons
 * layout with xbox and ps 5 controller", settled as the Unreal build. The
 * Unreal build had no menu at all. This is drawn exactly as the HUD is
 * (SaudHud in SaudAnime.h): Build() writes every triangle and every text
 * item into a list, Game/SaudHUD.cpp rasterises the list, Tools/harness/
 * tests/menu.cpp checks what is DRAWN at seven screen shapes, and Tools/
 * look/menu_preview.py draws it without an engine.
 *
 * The look is the dark seinen's, with the HUD's palette only (Ink, Bone,
 * Blood, Ember, Trough, Ash, Gold): "SAUD" in Bone with a Blood slash under
 * it like the health bar, "KUWAIT FIGHTER" small and dim; the items as
 * leaning ink plates -- the focused one Blood with its label in Bone and a
 * Bone keyline, pulsing slowly toward Ember on the real-time clock; the
 * others Trough in a thin Ash keyline with a dim label; a torn ink wash
 * behind the column; the pause the same column over a Trough-black scrim.
 * The settings rows show their value ("DIFFICULTY  PRO", "SOUND  ON"). The
 * controls screen is SaudControls::BuildControlsPage's diagram with a BACK
 * plate and the pad-flip prompt. A prompt strip sits along the bottom safe
 * line: for a pad, its glyphs (SaudControls::Glyph) with a word each; for
 * the keyboard, words only.
 *
 * ENGLISH ONLY. The browser build writes an Arabic sub-line under every
 * label; this menu does not, because FCanvasTextItem does no Arabic
 * shaping (the letters would come out isolated and left-to-right), and a
 * wrong Arabic is worse than none. When the engine gets a shaping text
 * path, add a Sub slot per item here.
 *
 * "Ash text": the DESIGN asks for the dim labels in Ash and for every text
 * to stand 7:1 against its Ink stroke; Ash against Ink is 5.4:1. So the dim
 * text is Bone at DimAlpha, which composites over the plates to an ash
 * tone and keeps the 7:1 the harness holds (it also holds the alpha at or
 * over 0.5).
 *
 * The strings live in the engine (SaudHUD.cpp or the menu's own .cpp): a
 * text item here is a SLOT and a VALUE, and the engine maps them:
 *
 *   slot           value  string
 *   Saud             -    "SAUD"
 *   Subtitle         -    "KUWAIT FIGHTER"
 *   Paused           -    "PAUSED"
 *   SettingsHead     -    "SETTINGS"
 *   Continue         -    "CONTINUE"              (Title, when a save exists)
 *   Fight            -    "FIGHT"                 (Title, when none does)
 *   Controls         -    "CONTROLS"
 *   Settings         -    "SETTINGS"
 *   Quit             -    "QUIT"
 *   Resume           -    "RESUME"
 *   QuitToTitle      -    "QUIT TO TITLE"
 *   Difficulty       0    "DIFFICULTY  ROOKIE"
 *                    1    "DIFFICULTY  PRO"
 *                    2    "DIFFICULTY  CHAMPION"
 *   Sound            0/1  "SOUND  OFF" / "SOUND  ON"
 *   Music            0/1  "MUSIC  OFF" / "MUSIC  ON"
 *   Vibration        0/1  "VIBRATION  OFF" / "VIBRATION  ON"
 *   Back             -    "BACK"
 *   PromptSelect     -    "SELECT"                (after the Confirm glyph)
 *   PromptBack       -    "BACK"                  (after the Back glyph)
 *   PromptAdjust     -    "ADJUST"                (after the d-pad-left glyph)
 *   PromptFlip       0/1  "SHOW XBOX" / "SHOW PS5"  (after the LB/L1 glyph: the pad the flip goes to)
 *   KeySelect        -    "ENTER  SELECT"         (keyboard: no glyph)
 *   KeyBack          -    "ESC  BACK"
 *   KeyAdjust        -    "ARROWS  ADJUST"
 *   KeyFlip          0/1  "TAB  SHOW XBOX" / "TAB  SHOW PS5"
 *   ControlsText     -    forwarded from SaudControls' sink: Value is its
 *                         text slot as an int, Aux its value; the engine
 *                         maps them with SaudControls' own table.
 *
 * Chars() below carries each string's length so the layout can estimate a
 * label's width (CharAdvance of its height per character) and the harness
 * can hold that no label runs off its plate and no two prompts touch.
 *
 * SaudControls.h is another track's header, coded to the contract in the
 * design note (EPad, EAction, EButton, FGlyphSink, Glyph, BuildControlsPage).
 * With SAUD_MENU_STUB_CONTROLS defined the include is skipped and the test
 * supplies a stub of that contract before including this.
 */

#include "SaudAnime.h"
#if !defined(SAUD_MENU_STUB_CONTROLS)
	#include "SaudControls.h"
#endif

namespace SaudMenu
{
	using SaudHud::FPoint;
	using SaudHud::FRect;
	using SaudHud::FRgba;
	using SaudHud::FPage;
	namespace Colour = SaudHud::Colour;

	// ------------------------------------------------------------- the model
	enum class EScreen : unsigned char { Title, Pause, Settings, Controls };

	/** Every item any screen can show. */
	enum class EItem : unsigned char
	{
		Continue, Fight, Controls, Settings, Quit,     // Title: CONTINUE|FIGHT, CONTROLS, SETTINGS, QUIT
		Resume, QuitToTitle,                           // Pause: RESUME, CONTROLS, SETTINGS, QUIT TO TITLE
		Difficulty, Sound, Music, Vibration, Back,     // Settings: the four, BACK; Controls: BACK
		Count
	};
	constexpr int MaxItems = 5;

	/** What the engine must do after Navigate. Tap, Back and Denied are the
	    UI sounds (UI_Tap, UI_Back, UI_Denied); the toggles and the cycle say
	    the model's setting changed and must be saved; the rest are the
	    flow. There is no Restart (the browser's RESTART STAGE is not here). */
	enum class EMenuEffect : unsigned char
	{
		None, StartGame, Resume, QuitToTitle, QuitGame,
		ToggleSound, ToggleMusic, ToggleVibration, CycleDifficulty,
		Tap, Back, Denied
	};

	/** Plain data: the engine's USaudMenuSubsystem holds it, ticks Clock and
	    Since in REAL seconds (the pause stops the game's clock, not the
	    menu's), and sets Pad from the device last used. */
	struct FMenuModel
	{
		EScreen Screen = EScreen::Title;
		int Focus = 0;
		// the settings, mirroring FSaudProgress (Game/SaudSaveGame.h)
		int DifficultyIndex = 1;                 // 0 rookie, 1 pro, 2 champion
		bool bSound = true;
		bool bMusic = true;
		bool bVibration = true;
		SaudControls::EPad Pad = SaudControls::EPad::Xbox;     // in use: the prompt strip's glyphs
		SaudControls::EPad Shown = SaudControls::EPad::Xbox;   // the controls diagram (never Keyboard)
		bool bHasSave = false;                   // Title shows CONTINUE instead of FIGHT
		float Clock = 0.f;                       // real seconds: the focus pulse
		float Since = 0.f;                       // real seconds since this screen opened: the slash wipe
		// where a Settings or Controls page goes back to, and the item there
		// that opened it
		EScreen ReturnTo = EScreen::Title;
		int ReturnFocus = 0;
	};

	/** The screen's items in order. Title shows CONTINUE first when a save
	    exists, else FIGHT (never both: either starts the game, and the
	    engine knows which by bHasSave). */
	inline int Items(const FMenuModel& M, EItem Out[MaxItems])
	{
		switch (M.Screen)
		{
		case EScreen::Title:
			Out[0] = M.bHasSave ? EItem::Continue : EItem::Fight;
			Out[1] = EItem::Controls;
			Out[2] = EItem::Settings;
			Out[3] = EItem::Quit;
			return 4;
		case EScreen::Pause:
			Out[0] = EItem::Resume;
			Out[1] = EItem::Controls;
			Out[2] = EItem::Settings;
			Out[3] = EItem::QuitToTitle;
			return 4;
		case EScreen::Settings:
			Out[0] = EItem::Difficulty;
			Out[1] = EItem::Sound;
			Out[2] = EItem::Music;
			Out[3] = EItem::Vibration;
			Out[4] = EItem::Back;
			return 5;
		case EScreen::Controls:
		default:
			Out[0] = EItem::Back;
			return 1;
		}
	}
	inline int ItemCount(const FMenuModel& M)
	{
		EItem Tmp[MaxItems] = {};
		return Items(M, Tmp);
	}

	/** The engine opens the Title (both game modes, at start) and the Pause
	    (the pad's Menu button / Esc in a fight) with this. */
	inline void Open(FMenuModel& M, EScreen S)
	{
		M.Screen = S;
		M.Focus = 0;
		M.ReturnTo = S;
		M.ReturnFocus = 0;
		M.Since = 0.f;
	}

	namespace Detail
	{
		inline void OpenSub(FMenuModel& M, EScreen S)
		{
			M.ReturnTo = M.Screen;
			M.ReturnFocus = M.Focus;
			M.Screen = S;
			M.Focus = 0;
			M.Since = 0.f;
			if (S == EScreen::Controls && M.Pad != SaudControls::EPad::Keyboard)
			{
				M.Shown = M.Pad;   // the diagram opens on the pad in the hand
			}
		}
		inline void Return(FMenuModel& M)
		{
			M.Screen = M.ReturnTo;
			M.Focus = M.ReturnFocus;
			M.ReturnTo = M.Screen;
			M.ReturnFocus = 0;
			M.Since = 0.f;
		}
		inline void Flip(FMenuModel& M)
		{
			M.Shown = M.Shown == SaudControls::EPad::PlayStation ? SaudControls::EPad::Xbox
			                                                     : SaudControls::EPad::PlayStation;
		}
		/** A setting adjusted by Dir (+1 confirm/right, -1 left); Denied when
		    the item is not a setting. */
		inline EMenuEffect Adjust(FMenuModel& M, EItem I, int Dir)
		{
			switch (I)
			{
			case EItem::Difficulty:
				M.DifficultyIndex = (M.DifficultyIndex + 3 + Dir) % 3;
				return EMenuEffect::CycleDifficulty;
			case EItem::Sound:
				M.bSound = !M.bSound;
				return EMenuEffect::ToggleSound;
			case EItem::Music:
				M.bMusic = !M.bMusic;
				return EMenuEffect::ToggleMusic;
			case EItem::Vibration:
				M.bVibration = !M.bVibration;
				return EMenuEffect::ToggleVibration;
			default:
				return EMenuEffect::Denied;
			}
		}
		inline EMenuEffect Activate(FMenuModel& M, EItem I)
		{
			switch (I)
			{
			case EItem::Continue:
			case EItem::Fight:
				return EMenuEffect::StartGame;
			case EItem::Controls:
				OpenSub(M, EScreen::Controls);
				return EMenuEffect::Tap;
			case EItem::Settings:
				OpenSub(M, EScreen::Settings);
				return EMenuEffect::Tap;
			case EItem::Quit:
				return EMenuEffect::QuitGame;
			case EItem::Resume:
				return EMenuEffect::Resume;
			case EItem::QuitToTitle:
				return EMenuEffect::QuitToTitle;
			case EItem::Back:
				Return(M);
				return EMenuEffect::Back;
			default:
				return Adjust(M, I, +1);
			}
		}
	}

	/** One menu action in. Pure over the model: the focus wraps and never
	    leaves the item range; Confirm activates the item; Back leaves a
	    Settings or Controls page for the screen it was opened from (with
	    the focus back on the item that opened it), resumes from the Pause,
	    and is Denied on the Title; left/right adjust a setting or flip the
	    diagram; the fight's actions do nothing here. */
	inline EMenuEffect Navigate(FMenuModel& M, SaudControls::EAction A)
	{
		using SaudControls::EAction;
		EItem List[MaxItems] = {};
		const int N = Items(M, List);
		switch (A)
		{
		case EAction::NavUp:
			M.Focus = (M.Focus + N - 1) % N;
			return EMenuEffect::Tap;
		case EAction::NavDown:
			M.Focus = (M.Focus + 1) % N;
			return EMenuEffect::Tap;
		case EAction::Confirm:
			return Detail::Activate(M, List[M.Focus]);
		case EAction::NavLeft:
		case EAction::NavRight:
			if (M.Screen == EScreen::Controls)
			{
				Detail::Flip(M);
				return EMenuEffect::Tap;
			}
			if (M.Screen == EScreen::Settings && List[M.Focus] != EItem::Back)
			{
				return Detail::Adjust(M, List[M.Focus], A == EAction::NavLeft ? -1 : +1);
			}
			return EMenuEffect::None;
		case EAction::Back:
			switch (M.Screen)
			{
			case EScreen::Settings:
			case EScreen::Controls:
				Detail::Return(M);
				return EMenuEffect::Back;
			case EScreen::Pause:
				return EMenuEffect::Resume;
			case EScreen::Title:
			default:
				return EMenuEffect::Denied;
			}
		case EAction::FlipPad:
			if (M.Screen == EScreen::Controls)
			{
				Detail::Flip(M);
				return EMenuEffect::Tap;
			}
			return EMenuEffect::None;
		case EAction::Pause:
			return M.Screen == EScreen::Pause ? EMenuEffect::Resume : EMenuEffect::None;
		default:
			return EMenuEffect::None;
		}
	}

	// ---------------------------------------------------------- the list
	/** What a triangle is part of: the harness finds each rule's shapes by
	    it. Scrim is the one part allowed outside title-safe (it must cover
	    the whole screen); Glyph and Diagram are SaudControls' shapes. */
	enum class EMenuPart : unsigned char { Scrim, Wash, Slash, Keyline, Plate, Glyph, Diagram };

	enum class EMenuText : unsigned char
	{
		Saud, Subtitle, Paused, SettingsHead,
		Continue, Fight, Controls, Settings, Quit, Resume, QuitToTitle,
		Difficulty, Sound, Music, Vibration, Back,
		PromptSelect, PromptBack, PromptAdjust, PromptFlip,
		KeySelect, KeyBack, KeyAdjust, KeyFlip,
		ControlsText
	};

	/** The length of the string a slot and value map to (the table above),
	    for the layout's width estimate; 0 for ControlsText (theirs). */
	inline int Chars(EMenuText Slot, int Value)
	{
		switch (Slot)
		{
		case EMenuText::Saud: return 4;
		case EMenuText::Subtitle: return 14;
		case EMenuText::Paused: return 6;
		case EMenuText::SettingsHead: return 8;
		case EMenuText::Continue: return 8;
		case EMenuText::Fight: return 5;
		case EMenuText::Controls: return 8;
		case EMenuText::Settings: return 8;
		case EMenuText::Quit: return 4;
		case EMenuText::Resume: return 6;
		case EMenuText::QuitToTitle: return 13;
		case EMenuText::Difficulty: return Value == 0 ? 18 : (Value == 1 ? 15 : 20);
		case EMenuText::Sound: return Value ? 9 : 10;
		case EMenuText::Music: return Value ? 9 : 10;
		case EMenuText::Vibration: return Value ? 13 : 14;
		case EMenuText::Back: return 4;
		case EMenuText::PromptSelect: return 6;
		case EMenuText::PromptBack: return 4;
		case EMenuText::PromptAdjust: return 6;
		case EMenuText::PromptFlip: return Value ? 8 : 9;
		case EMenuText::KeySelect: return 13;
		case EMenuText::KeyBack: return 9;
		case EMenuText::KeyAdjust: return 14;
		case EMenuText::KeyFlip: return Value ? 13 : 14;
		case EMenuText::ControlsText:
		default: return 0;
		}
	}
	/** A capital's advance as a share of the text height (the engine's
	    large font, whose max char height is what Height scales). */
	constexpr float CharAdvance = 0.62f;
	inline float TextWidth(EMenuText Slot, int Value, float Height)
	{
		return static_cast<float>(Chars(Slot, Value)) * CharAdvance * Height;
	}

	struct FMenuVert { FPoint P; FRgba C; };
	struct FMenuTri
	{
		FMenuVert V[3];
		EMenuPart Part = EMenuPart::Wash;
		int Item = -1;          // the item index a plate or keyline belongs to
		int Tag = 0;            // Glyph: the EPad drawn; Diagram: SaudControls' own part
	};
	struct FMenuText
	{
		EMenuText Slot = EMenuText::Saud;
		int Value = 0;
		int Aux = 0;            // ControlsText: SaudControls' value
		FPoint At;              // top left, or top centre when bCentre
		float Height = 0.f;     // screen px
		FRgba Colour;
		float Stroke = 0.f;     // the ink round it, screen px
		bool bCentre = false;
		int Item = -1;          // the item this labels, or -1
		EMenuPart Part = EMenuPart::Wash;   // what it sits on (Plate, Wash, Glyph = the prompt strip, Diagram)
		int TrisBefore = 0;
	};

	/** Larger than the HUD's: the controls diagram draws every button. */
	constexpr int MaxTris = 4096;
	constexpr int MaxTexts = 96;

	/** Fixed capacity, no allocation, the HUD's FDrawList's shape. */
	struct FMenuList
	{
		FMenuTri Tris[MaxTris];
		int NumTris = 0;
		FMenuText Texts[MaxTexts];
		int NumTexts = 0;
		bool bOverflow = false;

		void Reset() { NumTris = 0; NumTexts = 0; bOverflow = false; }

		void Tri(const FPoint& A, const FRgba& CA, const FPoint& B, const FRgba& CB, const FPoint& C,
		         const FRgba& CC, EMenuPart Pt, int Item, int Tag)
		{
			if (NumTris >= MaxTris)
			{
				bOverflow = true;
				return;
			}
			FMenuTri& T = Tris[NumTris++];
			T.V[0] = {A, CA};
			T.V[1] = {B, CB};
			T.V[2] = {C, CC};
			T.Part = Pt;
			T.Item = Item;
			T.Tag = Tag;
		}
		void Quad(const FPoint Q[4], const FRgba C[4], EMenuPart Pt, int Item, int Tag)
		{
			Tri(Q[0], C[0], Q[1], C[1], Q[2], C[2], Pt, Item, Tag);
			Tri(Q[0], C[0], Q[2], C[2], Q[3], C[3], Pt, Item, Tag);
		}
		void Quad(const FPoint Q[4], const FRgba& C, EMenuPart Pt, int Item, int Tag)
		{
			const FRgba Cs[4] = {C, C, C, C};
			Quad(Q, Cs, Pt, Item, Tag);
		}
		void Text(EMenuText Slot, int Value, int Aux, const FPoint& At, float Height, const FRgba& C, float Stroke,
		          bool bCentre, int Item, EMenuPart Pt)
		{
			if (NumTexts >= MaxTexts)
			{
				bOverflow = true;
				return;
			}
			FMenuText& T = Texts[NumTexts++];
			T.Slot = Slot;
			T.Value = Value;
			T.Aux = Aux;
			T.At = At;
			T.Height = Height;
			T.Colour = C;
			T.Stroke = Stroke;
			T.bCentre = bCentre;
			T.Item = Item;
			T.Part = Pt;
			T.TrisBefore = NumTris;
		}
	};

	/** SaudControls draws through a sink whose Tri/Text mirror FDrawList's;
	    this one lands its shapes in the menu's list under Part/Item/Tag. */
	struct FMenuSink final : public SaudControls::FGlyphSink
	{
		FMenuList& Out;
		EMenuPart Part;
		int Item;
		int Tag;
		FMenuSink(FMenuList& InOut, EMenuPart InPart, int InItem, int InTag)
			: Out(InOut), Part(InPart), Item(InItem), Tag(InTag) {}
		void Tri(const FPoint& A, const FRgba& CA, const FPoint& B, const FRgba& CB, const FPoint& C,
		         const FRgba& CC, SaudControls::EControlsPart Pt) override
		{
			Out.Tri(A, CA, B, CB, C, CC, Part, Item, Part == EMenuPart::Diagram ? static_cast<int>(Pt) : Tag);
		}
		void Text(SaudControls::EControlsText Slot, int Value, const FPoint& At, float Height, const FRgba& C,
		          float Stroke, bool bCentre) override
		{
			Out.Text(EMenuText::ControlsText, static_cast<int>(Slot), Value, At, Height, C, Stroke, bCentre, Item, Part);
		}
	};

	// ------------------------------------------------------------ the look
	// Page px (1920 x 1080, scaled by height, hung off the safe corners).
	constexpr float ColumnIn = 40.f;             // the column, in from the left safe line
	constexpr float WashW = 860.f, WashH = 880.f, WashDown = 20.f;
	constexpr float WashAlpha = 0.80f;
	constexpr float WashFadeFrom = 0.55f;
	constexpr float TitleText = 170.f;           // "SAUD"
	constexpr float HeadText = 120.f;            // "PAUSED", "SETTINGS"
	constexpr float HeadDown = 50.f;
	constexpr float SlashW = 460.f, SlashH = 20.f, SlashGap = 10.f;
	constexpr float SlashRevealSeconds = 0.40f;  // wipes open like the boss banner
	constexpr float SubText = 36.f;              // "KUWAIT FIGHTER"
	constexpr float SubGap = 12.f;
	/** The first plate hangs this far under the slash on every screen (the
	    Title's sub-line sits inside the gap), so the column's top follows
	    the heading actually drawn: 170 px "SAUD", 120 px "PAUSED". */
	constexpr float ItemsGap = 80.f;
	constexpr float PlateW = 560.f, PlateH = 66.f, PlateGap = 16.f;
	constexpr float PlateLean = 0.55f;           // as the bars
	constexpr float LabelText = 34.f;            // >= 1080 / 36
	constexpr float LabelIn = 26.f;              // past the lean
	constexpr float StripText = 32.f;            // the prompt strip
	constexpr float GlyphSize = 48.f;            // a prompt glyph's size (its disc's diameter): couch-sized
	constexpr float GlyphGap = 12.f;             // glyph to its word
	constexpr float PromptGap = 48.f;            // between prompts
	constexpr float ScrimAlpha = 0.78f;
	constexpr float PlateAlpha = 0.88f;
	constexpr float DimAlpha = 0.55f;            // the dim (ash) text and keylines: Bone / Ash at this
	constexpr float PulseHz = 0.38f;             // the focus pulse: one breath in 2.6 s
	constexpr float PulseToEmber = 0.15f;        // how far toward Ember at the top of it: it stays Blood (Ember is the HUD's "enraged")

	/** A glyph's width in units of its Size: a shoulder is a tab, a trigger
	    a narrower one (SaudControls' own shares), everything else a disc or
	    a cross Size across. */
	inline float GlyphWide(SaudControls::EButton B)
	{
		using SaudControls::EButton;
		if (B == EButton::LB || B == EButton::RB) return SaudControls::TabWide;
		if (B == EButton::LT || B == EButton::RT) return SaudControls::TriggerWide;
		return 1.f;
	}

	struct FMenuLayout
	{
		FRect Wash;
		FPoint Heading;
		float HeadingH = 0.f;
		FRect Slash;
		FPoint Subtitle;
		FRect Plate[MaxItems];
		int NumItems = 0;
		FPoint StripAt;        // the prompt strip's left, on the bottom safe line (its baseline)
		float StripH = 0.f;
	};

	inline FMenuLayout Lay(const FPage& P, const FMenuModel& M)
	{
		FMenuLayout L;
		const float X = P.Left() + P.Px(ColumnIn), Y = P.Top();
		L.Wash = {P.Left(), Y + P.Px(WashDown), P.Px(WashW), P.Px(WashH)};
		L.HeadingH = P.Px(M.Screen == EScreen::Title ? TitleText : HeadText);
		L.Heading = {X, Y + P.Px(HeadDown)};
		L.Slash = {X + P.Px(4.f), L.Heading.Y + L.HeadingH + P.Px(SlashGap), P.Px(SlashW), P.Px(SlashH)};
		L.Subtitle = {X + P.Px(8.f), L.Slash.Y + L.Slash.H + P.Px(SubGap)};
		L.StripH = P.Px(StripText);
		L.StripAt = {X, P.Bottom() - L.StripH};
		EItem List[MaxItems] = {};
		L.NumItems = Items(M, List);
		const float W = P.Px(PlateW), H = P.Px(PlateH);
		if (M.Screen == EScreen::Controls)
		{
			// the diagram has the page between SaudControls' head band and
			// foot band (the strip's); BACK sits in the head band, top right
			// (in from the right safe line by its keyline, which is grown round it)
			const float Key = FMath::Max(1.f, P.Px(SaudHud::Ink));
			L.Plate[0] = {P.Right() - W - Key, Y + 0.5f * (P.Px(SaudControls::HeadBand) - H), W, H};
		}
		else
		{
			const float Top = L.Slash.Y + L.Slash.H + P.Px(ItemsGap);
			for (int i = 0; i < L.NumItems; ++i)
			{
				L.Plate[i] = {X, Top + P.Px(static_cast<float>(i) * (PlateH + PlateGap)), W, H};
			}
		}
		return L;
	}

	/** The focused plate's fill on the real-time clock: Blood breathing a
	    little toward Ember, slowly -- never so far it reads Ember, which is
	    the HUD's "enraged". Never under Blood, so it is never nearer the
	    Trough than the palette promises (3:1). */
	inline FRgba FocusFill(float Clock)
	{
		const float Pulse = 0.5f + 0.5f * FMath::Sin(Clock * 6.2831853f * PulseHz);
		return SaudHud::LerpColour(Colour::Blood, Colour::Ember, PulseToEmber * Pulse);
	}
	inline FRgba UnfocusedFill()
	{
		return SaudHud::WithAlpha(Colour::Trough, PlateAlpha);
	}
	inline FRgba DimText()
	{
		return SaudHud::WithAlpha(Colour::Bone, DimAlpha);
	}

	inline EMenuText SlotOf(EItem I)
	{
		switch (I)
		{
		case EItem::Continue: return EMenuText::Continue;
		case EItem::Fight: return EMenuText::Fight;
		case EItem::Controls: return EMenuText::Controls;
		case EItem::Settings: return EMenuText::Settings;
		case EItem::Quit: return EMenuText::Quit;
		case EItem::Resume: return EMenuText::Resume;
		case EItem::QuitToTitle: return EMenuText::QuitToTitle;
		case EItem::Difficulty: return EMenuText::Difficulty;
		case EItem::Sound: return EMenuText::Sound;
		case EItem::Music: return EMenuText::Music;
		case EItem::Vibration: return EMenuText::Vibration;
		case EItem::Back:
		default: return EMenuText::Back;
		}
	}
	/** The value a settings row shows, read from the model. */
	inline int ValueOf(const FMenuModel& M, EItem I)
	{
		switch (I)
		{
		case EItem::Difficulty: return M.DifficultyIndex;
		case EItem::Sound: return M.bSound ? 1 : 0;
		case EItem::Music: return M.bMusic ? 1 : 0;
		case EItem::Vibration: return M.bVibration ? 1 : 0;
		default: return 0;
		}
	}

	namespace Detail
	{
		/** The HUD's TornStrip (SaudAnime.h) for the menu's list: an ink
		    strip with both edges torn by up to TearPx every PitchPx (the
		    same hash, so Tools/look draws it the same), full Alpha to
		    FadeFrom of its width and fading to nothing (smoothstep) at its
		    end. SaudHud's writes an FDrawList, so it is written again here
		    rather than copied through one. */
		inline void TornWash(FMenuList& Out, const FPage& P, const FRect& R, float Seed, float Alpha, float FadeFrom)
		{
			const int N = static_cast<int>(FMath::Max(2.f, SaudHud::FloorF(R.W / P.Px(SaudHud::PitchPx) + 0.5f))) + 1;
			const float Tear = P.Px(SaudHud::TearPx);
			FPoint PrevT, PrevB;
			FRgba PrevC;
			for (int i = 0; i < N; ++i)
			{
				const float U = static_cast<float>(i) / static_cast<float>(N - 1);
				const float X = R.X + R.W * U;
				const float Yt = R.Y + Tear * SaudHud::HudHash(static_cast<float>(i), Seed);
				const float Yb = R.Y + R.H - Tear * SaudHud::HudHash(static_cast<float>(i + 500), Seed);
				const float K = U <= FadeFrom ? 0.f : FMath::Clamp((U - FadeFrom) / (1.f - FadeFrom), 0.f, 1.f);
				const float A = Alpha * (1.f - K * K * (3.f - 2.f * K));
				const FPoint Tp = {X, Yt}, Bt = {X, Yb};
				const FRgba C = SaudHud::WithAlpha(Colour::Ink, A);
				if (i > 0)
				{
					const FPoint Q[4] = {PrevT, Tp, Bt, PrevB};
					const FRgba Cs[4] = {PrevC, C, C, PrevC};
					Out.Quad(Q, Cs, EMenuPart::Wash, -1, 0);
				}
				PrevT = Tp;
				PrevB = Bt;
				PrevC = C;
			}
		}

		/** A leaning plate: its keyline grown by KeyPx, then its fill. */
		inline void Plate(FMenuList& Out, const FRect& R, const FRgba& Fill, const FRgba& Key, float KeyPx, int Item)
		{
			FPoint Q[4];
			SaudHud::LeanQuad(SaudHud::Grow(R, KeyPx), 1.f, PlateLean, Q);
			Out.Quad(Q, Key, EMenuPart::Keyline, Item, 0);
			SaudHud::LeanQuad(R, 1.f, PlateLean, Q);
			Out.Quad(Q, Fill, EMenuPart::Plate, Item, 0);
		}

		/** One prompt: for a pad, its glyph then its word; for the keyboard,
		    the keyboard word alone. Returns the x after it. */
		inline float Prompt(FMenuList& Out, const FPage& P, const FMenuModel& M, float X, float Baseline, float H,
		                    SaudControls::EButton Button, EMenuText PadSlot, EMenuText KeySlot, int Value)
		{
			const float Stroke = P.Px(SaudHud::TextStroke);
			if (M.Pad == SaudControls::EPad::Keyboard)
			{
				Out.Text(KeySlot, Value, 0, {X, Baseline - H}, H, Colour::Bone, Stroke, false, -1, EMenuPart::Glyph);
				return X + TextWidth(KeySlot, Value, H) + P.Px(PromptGap);
			}
			const float Size = P.Px(GlyphSize);
			const float GW = Size * GlyphWide(Button);
			FMenuSink Sink(Out, EMenuPart::Glyph, -1, static_cast<int>(M.Pad));
			// a tab's rim is grown round it, so a glyph stands its rim above the line
			SaudControls::Glyph(Button, M.Pad, X + 0.5f * GW, Baseline - 0.5f * Size - SaudControls::GlyphRim * Size, Size,
			                    Colour::Ink, Colour::Bone, Sink);
			const float TX = X + GW + P.Px(GlyphGap);
			Out.Text(PadSlot, Value, 0, {TX, Baseline - H}, H, Colour::Bone, Stroke, false, -1, EMenuPart::Glyph);
			return TX + TextWidth(PadSlot, Value, H) + P.Px(PromptGap);
		}
	}

	/** The whole screen for one frame. Pure: the same page and model give
	    the same list. */
	inline void Build(const FPage& P, const FMenuModel& M, FMenuList& Out)
	{
		using SaudControls::EButton;
		Out.Reset();
		const FMenuLayout L = Lay(P, M);
		const float Key = FMath::Max(1.f, P.Px(SaudHud::Ink));
		const float Stroke = P.Px(SaudHud::TextStroke);
		EItem List[MaxItems] = {};
		const int N = Items(M, List);

		// The scrim: the pause and anything opened from it stand over a
		// stopped fight; the controls diagram wants a dark ground always.
		const bool bScrim = M.Screen == EScreen::Pause || M.ReturnTo == EScreen::Pause || M.Screen == EScreen::Controls;
		if (bScrim)
		{
			const FPoint Q[4] = {{0.f, P.ScreenH}, {0.f, 0.f}, {P.ScreenW, 0.f}, {P.ScreenW, P.ScreenH}};
			Out.Quad(Q, SaudHud::WithAlpha(Colour::Trough, ScrimAlpha), EMenuPart::Scrim, -1, 0);
		}

		if (M.Screen == EScreen::Controls)
		{
			FMenuSink Sink(Out, EMenuPart::Diagram, -1, 0);
			SaudControls::BuildControlsPage(P, M.Shown, Sink);
		}
		else
		{
			// the torn ink wash behind the column, the heading, the blood
			// slash wiping open under it, and on the Title the sub-line
			Detail::TornWash(Out, P, L.Wash, 5.f, WashAlpha, WashFadeFrom);
			const EMenuText Head = M.Screen == EScreen::Title ? EMenuText::Saud
			                     : (M.Screen == EScreen::Pause ? EMenuText::Paused : EMenuText::SettingsHead);
			Out.Text(Head, 0, 0, L.Heading, L.HeadingH, Colour::Bone, Stroke, false, -1, EMenuPart::Wash);
			const float T = FMath::Clamp(M.Since / SlashRevealSeconds, 0.f, 1.f);
			const float Open = 1.f - (1.f - T) * (1.f - T) * (1.f - T);
			if (Open > 0.f)
			{
				FPoint Q[4];
				SaudHud::LeanQuad(L.Slash, Open, SaudHud::SlashLean, Q);
				Out.Quad(Q, SaudHud::WithAlpha(Colour::Blood, SaudHud::SlashAlpha), EMenuPart::Slash, -1, 0);
			}
			if (M.Screen == EScreen::Title)
			{
				Out.Text(EMenuText::Subtitle, 0, 0, L.Subtitle, P.Px(SubText), DimText(), Stroke, false, -1,
				         EMenuPart::Wash);
			}
		}

		// the items: leaning plates, the focused one blood in a bone
		// keyline with a bone label, the rest trough in a dim ash keyline
		// with a dim label
		const float H = P.Px(LabelText);
		for (int i = 0; i < N; ++i)
		{
			const bool bFocus = i == M.Focus;
			const FRect& R = L.Plate[i];
			Detail::Plate(Out, R, bFocus ? FocusFill(M.Clock) : UnfocusedFill(),
			              bFocus ? Colour::Bone : SaudHud::WithAlpha(Colour::Ash, DimAlpha), Key, i);
			const FPoint At = {R.X + R.H * PlateLean + P.Px(LabelIn), R.Y + 0.5f * (R.H - H)};
			Out.Text(SlotOf(List[i]), ValueOf(M, List[i]), 0, At, H, bFocus ? Colour::Bone : DimText(), Stroke, false, i,
			         EMenuPart::Plate);
		}

		// the prompt strip along the bottom safe line
		{
			const float Baseline = P.Bottom();
			float X = L.StripAt.X;
			const float SH = L.StripH;
			switch (M.Screen)
			{
			case EScreen::Title:
				X = Detail::Prompt(Out, P, M, X, Baseline, SH, EButton::FaceSouth, EMenuText::PromptSelect,
				                   EMenuText::KeySelect, 0);
				break;
			case EScreen::Pause:
				X = Detail::Prompt(Out, P, M, X, Baseline, SH, EButton::FaceSouth, EMenuText::PromptSelect,
				                   EMenuText::KeySelect, 0);
				X = Detail::Prompt(Out, P, M, X, Baseline, SH, EButton::FaceEast, EMenuText::PromptBack,
				                   EMenuText::KeyBack, 0);
				break;
			case EScreen::Settings:
				X = Detail::Prompt(Out, P, M, X, Baseline, SH, EButton::FaceSouth, EMenuText::PromptSelect,
				                   EMenuText::KeySelect, 0);
				X = Detail::Prompt(Out, P, M, X, Baseline, SH, EButton::FaceEast, EMenuText::PromptBack,
				                   EMenuText::KeyBack, 0);
				X = Detail::Prompt(Out, P, M, X, Baseline, SH, EButton::DpadLeft, EMenuText::PromptAdjust,
				                   EMenuText::KeyAdjust, 0);
				break;
			case EScreen::Controls:
			default:
				X = Detail::Prompt(Out, P, M, X, Baseline, SH, EButton::FaceEast, EMenuText::PromptBack,
				                   EMenuText::KeyBack, 0);
				// the flip goes to the other pad: 0 says "SHOW XBOX", 1 "SHOW PS5"
				X = Detail::Prompt(Out, P, M, X, Baseline, SH, EButton::LB, EMenuText::PromptFlip, EMenuText::KeyFlip,
				                   M.Shown == SaudControls::EPad::Xbox ? 1 : 0);
				break;
			}
			(void)X;
		}
	}
}
