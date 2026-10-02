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
 * The settings rows show their value ("DIFFICULTY  PRO", "SOUND  7"). The
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
 *   Sound            0    "SOUND  OFF"            (the level, 0..LevelMax)
 *                    n    "SOUND  n"
 *   Music            0    "MUSIC  OFF"
 *                    n    "MUSIC  n"
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
 *   -- since 2026-10-02 ("improve main menu game ux ui"):
 *   NewGame          -    "NEW GAME"              (Title, when a save exists)
 *   AskHead          0/1  "QUIT?" / "NEW GAME?"   (the confirm's heading; EAsk)
 *   ConfirmNo        0/1  "NO, STAY" / "NO, KEEP MY SAVE"
 *   ConfirmYes       0/1  "YES, QUIT" / "YES, START OVER"
 *   StageTag         r    "STAGE r/n"             (on CONTINUE; Aux is n)
 *   PromptQuit       -    "QUIT"                  (after the Back glyph, on the Title)
 *   KeyQuit          -    "ESC  QUIT"
 *   Hint             EHint, one line under the column saying what the
 *                    focused item does (on the confirm: what Yes does):
 *                    Continue     "PICK UP WHERE YOU LEFT OFF"
 *                    Fight        "START YOUR FIRST FIGHT"
 *                    NewGame      "START OVER FROM THE FIRST FIGHT"
 *                    Controls     "SEE WHAT EVERY BUTTON DOES"
 *                    Settings     "DIFFICULTY, SOUND, MUSIC, VIBRATION"
 *                    Quit         "CLOSE THE GAME"
 *                    Resume       "BACK INTO THE FIGHT"
 *                    QuitToTitle  "LEAVE THIS FIGHT FOR THE TITLE"
 *                    Difficulty   "HOW HARD THE STREETS HIT BACK"
 *                    Sound        "HITS, STEPS AND THE MENUS"
 *                    Music        "THE SCORE BEHIND EVERY FIGHT"
 *                    Vibration    "THE PAD RUMBLES WHEN BLOWS LAND"
 *                    BackTitle    "BACK TO THE TITLE"
 *                    BackPause    "BACK TO THE PAUSE"
 *                    AskQuit      "CLOSE SAUD AND GO BACK TO THE DESKTOP"
 *                    AskNewGame   "YOUR SAVE IS REPLACED. THERE IS NO UNDO"
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
	/** Confirm (2026-10-02): "are you sure?" before QUIT and before a NEW
	    GAME over a save, opened from the Title like Settings is. */
	enum class EScreen : unsigned char { Title, Pause, Settings, Controls, Confirm };

	/** What a Confirm asks. */
	enum class EAsk : unsigned char { Quit, NewGame };

	/** Every item any screen can show. */
	enum class EItem : unsigned char
	{
		Continue, Fight, Controls, Settings, Quit,     // Title: CONTINUE|FIGHT, CONTROLS, SETTINGS, QUIT
		Resume, QuitToTitle,                           // Pause: RESUME, CONTROLS, SETTINGS, QUIT TO TITLE
		Difficulty, Sound, Music, Vibration, Back,     // Settings: the four, BACK; Controls: BACK
		NewGame,                                       // Title, under CONTINUE, when a save exists
		ConfirmNo, ConfirmYes,                         // Confirm: NO first, so a stray press is safe
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
		SetSound, SetMusic, ToggleVibration, CycleDifficulty,
		Tap, Back, Denied,
		NewGame          // the save is replaced and the first fight starts (confirmed)
	};

	/** The sound and music levels run 0 (off) to this, saved per profile. */
	constexpr int LevelMax = 10;

	/** Motion, in real seconds (2026-10-02, "smoother motion"): the focus
	    glides from item to item over FocusGlideSeconds, and a screen's
	    column comes in when it opens -- the wash wiping open, the plates
	    sliding in from the left one after another -- all of it settled
	    by EnterSeconds, so a player pressing at once is never pressing on
	    something still moving far. */
	constexpr float FocusGlideSeconds = 0.18f;
	constexpr float WashWipeSeconds = 0.35f;
	constexpr float PlateDelay = 0.08f, PlateStagger = 0.05f, PlateArrive = 0.30f;
	constexpr float EnterSeconds = 0.60f;

	/** Plain data: the engine's USaudMenuSubsystem holds it, ticks Clock and
	    Since in REAL seconds (the pause stops the game's clock, not the
	    menu's), and sets Pad from the device last used. */
	struct FMenuModel
	{
		EScreen Screen = EScreen::Title;
		int Focus = 0;
		// the settings, mirroring FSaudProgress (Game/SaudSaveGame.h)
		int DifficultyIndex = 1;                 // 0 rookie, 1 pro, 2 champion
		int SoundLevel = LevelMax;               // 0 off .. LevelMax (was an on/off switch)
		int MusicLevel = LevelMax;
		bool bVibration = true;
		SaudControls::EPad Pad = SaudControls::EPad::Xbox;     // in use: the prompt strip's glyphs
		SaudControls::EPad Shown = SaudControls::EPad::Xbox;   // the controls diagram (never Keyboard)
		bool bHasSave = false;                   // Title shows CONTINUE and NEW GAME instead of FIGHT
		int StageReached = 0;                    // CONTINUE's tag: the stage the save has reached (1-based; 0 none)
		int StageCount = 9;                      // ...of this many (the campaign)
		EAsk Ask = EAsk::Quit;                   // what the Confirm screen asks
		// the focus glide: drawn at FocusFrom eased toward Focus as FocusT
		// runs 0 -> 1 (Step); at rest FocusT is 1 and the focus is drawn
		// exactly on Focus
		float FocusFrom = 0.f;
		float FocusT = 1.f;
		float Clock = 0.f;                       // real seconds: the focus pulse
		float Since = 0.f;                       // real seconds since this screen opened: the slash wipe
		// where a Settings or Controls page goes back to, and the item there
		// that opened it
		EScreen ReturnTo = EScreen::Title;
		int ReturnFocus = 0;
	};

	/** The screen's items in order. Title shows CONTINUE first when a save
	    exists, and NEW GAME under it; else FIGHT (never CONTINUE and FIGHT
	    both: either starts the game, and the engine knows which by
	    bHasSave). Before 2026-10-02 a player with a save had no way to
	    start again. */
	inline int Items(const FMenuModel& M, EItem Out[MaxItems])
	{
		switch (M.Screen)
		{
		case EScreen::Title:
			if (M.bHasSave)
			{
				Out[0] = EItem::Continue;
				Out[1] = EItem::NewGame;
				Out[2] = EItem::Controls;
				Out[3] = EItem::Settings;
				Out[4] = EItem::Quit;
				return 5;
			}
			Out[0] = EItem::Fight;
			Out[1] = EItem::Controls;
			Out[2] = EItem::Settings;
			Out[3] = EItem::Quit;
			return 4;
		case EScreen::Confirm:
			Out[0] = EItem::ConfirmNo;
			Out[1] = EItem::ConfirmYes;
			return 2;
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
		M.FocusFrom = 0.f;
		M.FocusT = 1.f;
	}

	/** The real-time clock: the engine calls it every frame with the frame's
	    real length (the pause holds the world's). The focus pulse, the
	    entrance and the focus glide all run on it. */
	inline void Step(FMenuModel& M, float Dt)
	{
		Dt = FMath::Max(Dt, 0.f);
		M.Clock += Dt;
		M.Since += Dt;
		M.FocusT = FMath::Min(1.f, M.FocusT + Dt / FocusGlideSeconds);
	}

	/** Where the focus is drawn now: FocusFrom eased (smoothstep) to Focus. */
	inline float ShownFocus(const FMenuModel& M)
	{
		const float T = FMath::Clamp(M.FocusT, 0.f, 1.f);
		const float E = T * T * (3.f - 2.f * T);
		return M.FocusFrom + (static_cast<float>(M.Focus) - M.FocusFrom) * E;
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
			M.FocusFrom = 0.f;
			M.FocusT = 1.f;
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
			M.FocusFrom = static_cast<float>(M.Focus);
			M.FocusT = 1.f;
		}
		/** The Confirm, asking A, opened from where the player is. */
		inline void OpenAsk(FMenuModel& M, EAsk A)
		{
			M.Ask = A;
			OpenSub(M, EScreen::Confirm);
		}
		/** The focus moves to F: it glides from where it is drawn now,
		    except across the wrap (last <-> first), where it jumps rather
		    than sweep the whole column. */
		inline void MoveFocus(FMenuModel& M, int F, bool bWrapped)
		{
			M.FocusFrom = bWrapped ? static_cast<float>(F) : ShownFocus(M);
			M.Focus = F;
			M.FocusT = bWrapped ? 1.f : 0.f;
		}
		/** A level stepped by Dir, 0..LevelMax: left and right stop at the
		    ends (Denied there), Confirm (bWrap) goes round, so one button
		    can reach every level. */
		inline bool StepLevel(int& Level, int Dir, bool bWrap)
		{
			const int Next = Level + Dir;
			if (Next < 0 || Next > LevelMax)
			{
				if (!bWrap) return false;
				Level = Next < 0 ? LevelMax : 0;
				return true;
			}
			Level = Next;
			return true;
		}
		inline void Flip(FMenuModel& M)
		{
			M.Shown = M.Shown == SaudControls::EPad::PlayStation ? SaudControls::EPad::Xbox
			                                                     : SaudControls::EPad::PlayStation;
		}
		/** A setting adjusted by Dir (+1 confirm/right, -1 left); Denied when
		    the item is not a setting, or a level is already at that end.
		    bWrap: Confirm, which goes round. */
		inline EMenuEffect Adjust(FMenuModel& M, EItem I, int Dir, bool bWrap)
		{
			switch (I)
			{
			case EItem::Difficulty:
				M.DifficultyIndex = (M.DifficultyIndex + 3 + Dir) % 3;
				return EMenuEffect::CycleDifficulty;
			case EItem::Sound:
				return StepLevel(M.SoundLevel, Dir, bWrap) ? EMenuEffect::SetSound : EMenuEffect::Denied;
			case EItem::Music:
				return StepLevel(M.MusicLevel, Dir, bWrap) ? EMenuEffect::SetMusic : EMenuEffect::Denied;
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
				OpenAsk(M, EAsk::Quit);              // asked first (2026-10-02)
				return EMenuEffect::Tap;
			case EItem::NewGame:
				OpenAsk(M, EAsk::NewGame);           // a save would be lost: asked first
				return EMenuEffect::Tap;
			case EItem::ConfirmNo:
				Return(M);
				return EMenuEffect::Back;
			case EItem::ConfirmYes:
				return M.Ask == EAsk::Quit ? EMenuEffect::QuitGame : EMenuEffect::NewGame;
			case EItem::Resume:
				return EMenuEffect::Resume;
			case EItem::QuitToTitle:
				return EMenuEffect::QuitToTitle;
			case EItem::Back:
				Return(M);
				return EMenuEffect::Back;
			default:
				return Adjust(M, I, +1, true);
			}
		}
	}

	/** Whether left/right held repeat on the focused item: a level, which is
	    stepped, does; a toggle or the difficulty, which a held repeat would
	    flip eight times a second, does not. */
	inline bool RepeatsSideways(const FMenuModel& M)
	{
		EItem List[MaxItems] = {};
		const int N = Items(M, List);
		const EItem I = M.Focus >= 0 && M.Focus < N ? List[M.Focus] : EItem::Back;
		return M.Screen == EScreen::Settings && (I == EItem::Sound || I == EItem::Music);
	}

	/** One menu action in. Pure over the model: the focus wraps and never
	    leaves the item range (gliding there, Step); Confirm activates the
	    item; Back leaves a Settings, Controls or Confirm page for the
	    screen it was opened from (with the focus back on the item that
	    opened it), resumes from the Pause, and on the Title asks to quit
	    (since 2026-10-02: it was Denied, and the strip offered no way out);
	    left/right adjust a setting or flip the diagram; the fight's actions
	    do nothing here. */
	inline EMenuEffect Navigate(FMenuModel& M, SaudControls::EAction A)
	{
		using SaudControls::EAction;
		EItem List[MaxItems] = {};
		const int N = Items(M, List);
		switch (A)
		{
		case EAction::NavUp:
			Detail::MoveFocus(M, (M.Focus + N - 1) % N, M.Focus == 0);
			return EMenuEffect::Tap;
		case EAction::NavDown:
			Detail::MoveFocus(M, (M.Focus + 1) % N, M.Focus == N - 1);
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
				return Detail::Adjust(M, List[M.Focus], A == EAction::NavLeft ? -1 : +1, false);
			}
			return EMenuEffect::None;
		case EAction::Back:
			switch (M.Screen)
			{
			case EScreen::Settings:
			case EScreen::Controls:
			case EScreen::Confirm:
				Detail::Return(M);
				return EMenuEffect::Back;
			case EScreen::Pause:
				return EMenuEffect::Resume;
			case EScreen::Title:
			default:
				Detail::OpenAsk(M, EAsk::Quit);
				return EMenuEffect::Tap;
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
	enum class EMenuPart : unsigned char { Scrim, Wash, Slash, Keyline, Plate, Glyph, Diagram, Meter };

	enum class EMenuText : unsigned char
	{
		Saud, Subtitle, Paused, SettingsHead,
		Continue, Fight, Controls, Settings, Quit, Resume, QuitToTitle,
		Difficulty, Sound, Music, Vibration, Back,
		PromptSelect, PromptBack, PromptAdjust, PromptFlip,
		KeySelect, KeyBack, KeyAdjust, KeyFlip,
		ControlsText,
		// 2026-10-02
		NewGame, AskHead, ConfirmNo, ConfirmYes, StageTag, PromptQuit, KeyQuit, Hint
	};

	/** What the hint line under the column says (EMenuText::Hint's value). */
	enum class EHint : unsigned char
	{
		Continue, Fight, NewGame, Controls, Settings, Quit, Resume, QuitToTitle,
		Difficulty, Sound, Music, Vibration, BackTitle, BackPause, AskQuit, AskNewGame,
		Count
	};
	/** The hint's words, here rather than in the engine's string table: the
	    HUD and Tools/harness/menu_dump.cpp both read them, and their length
	    is the layout's width estimate, so they cannot drift apart. ASCII. */
	inline const char* HintString(EHint H)
	{
		switch (H)
		{
		case EHint::Continue: return "PICK UP WHERE YOU LEFT OFF";
		case EHint::Fight: return "START YOUR FIRST FIGHT";
		case EHint::NewGame: return "START OVER FROM THE FIRST FIGHT";
		case EHint::Controls: return "SEE WHAT EVERY BUTTON DOES";
		case EHint::Settings: return "DIFFICULTY, SOUND, MUSIC, VIBRATION";
		case EHint::Quit: return "CLOSE THE GAME";
		case EHint::Resume: return "BACK INTO THE FIGHT";
		case EHint::QuitToTitle: return "LEAVE THIS FIGHT FOR THE TITLE";
		case EHint::Difficulty: return "HOW HARD THE STREETS HIT BACK";
		case EHint::Sound: return "HITS, STEPS AND THE MENUS";
		case EHint::Music: return "THE SCORE BEHIND EVERY FIGHT";
		case EHint::Vibration: return "THE PAD RUMBLES WHEN BLOWS LAND";
		case EHint::BackTitle: return "BACK TO THE TITLE";
		case EHint::BackPause: return "BACK TO THE PAUSE";
		case EHint::AskQuit: return "CLOSE SAUD AND GO BACK TO THE DESKTOP";
		case EHint::AskNewGame: return "YOUR SAVE IS REPLACED. THERE IS NO UNDO";
		default: return "";
		}
	}
	inline int HintChars(EHint H)
	{
		const char* S = HintString(H);
		int N = 0;
		while (S[N]) ++N;
		return N;
	}
	inline int Digits(int V) { int D = 1; while (V >= 10) { V /= 10; ++D; } return D; }

	/** The length of the string a slot and value map to (the table above),
	    for the layout's width estimate; 0 for ControlsText (theirs). */
	inline int Chars(EMenuText Slot, int Value, int Aux = 0)
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
		case EMenuText::Sound:                          // "SOUND  OFF", "SOUND  7", "SOUND  10"
		case EMenuText::Music: return Value <= 0 ? 10 : 7 + Digits(Value);
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
		case EMenuText::NewGame: return 8;
		case EMenuText::AskHead: return Value ? 9 : 5;
		case EMenuText::ConfirmNo: return Value ? 16 : 8;
		case EMenuText::ConfirmYes: return Value ? 15 : 9;
		case EMenuText::StageTag: return 7 + Digits(Value) + Digits(Aux);
		case EMenuText::PromptQuit: return 4;
		case EMenuText::KeyQuit: return 9;
		case EMenuText::Hint: return HintChars(static_cast<EHint>(Value));
		case EMenuText::ControlsText:
		default: return 0;
		}
	}
	/** A capital's advance as a share of the text height (the engine's
	    large font, whose max char height is what Height scales). */
	constexpr float CharAdvance = 0.62f;
	inline float TextWidth(EMenuText Slot, int Value, float Height, int Aux = 0)
	{
		return static_cast<float>(Chars(Slot, Value, Aux)) * CharAdvance * Height;
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
		/** Every colour's alpha is scaled by this: a glyph's rim is a fixed
		    palette colour inside SaudControls::Glyph, so the strip's fade-in
		    has to reach it here (2026-10-02). */
		float Alpha;
		FMenuSink(FMenuList& InOut, EMenuPart InPart, int InItem, int InTag, float InAlpha = 1.f)
			: Out(InOut), Part(InPart), Item(InItem), Tag(InTag), Alpha(InAlpha) {}
		FRgba Faded(const FRgba& C) const { return {C.R, C.G, C.B, C.A * Alpha}; }
		void Tri(const FPoint& A, const FRgba& CA, const FPoint& B, const FRgba& CB, const FPoint& C,
		         const FRgba& CC, SaudControls::EControlsPart Pt) override
		{
			Out.Tri(A, Faded(CA), B, Faded(CB), C, Faded(CC), Part, Item,
			        Part == EMenuPart::Diagram ? static_cast<int>(Pt) : Tag);
		}
		void Text(SaudControls::EControlsText Slot, int Value, const FPoint& At, float Height, const FRgba& C,
		          float Stroke, bool bCentre) override
		{
			Out.Text(EMenuText::ControlsText, static_cast<int>(Slot), Value, At, Height, Faded(C), Stroke, bCentre, Item,
			         Part);
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
	// 2026-10-02
	constexpr float HintText = 30.f;             // the hint line: 1080 / 36, the least the HUD allows
	constexpr float HintGap = 26.f;              // under the last plate
	constexpr float TagText = 30.f;              // CONTINUE's "STAGE 3/9", right on its plate
	constexpr float MeterW = 200.f, MeterH = 22.f, MeterGap = 4.f;   // a level's ten segments, right on its plate
	constexpr float FocusNudge = 14.f;           // the focused plate stands this far out of the column
	constexpr float SlideIn = 32.f;              // a plate comes in from this far left (inside the column's 40)

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
		FPoint Hint;           // the hint line's top left: under the column (on a Confirm, under the slash)
		float HintH = 0.f;
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
		L.HintH = P.Px(HintText);
		if (M.Screen == EScreen::Confirm)
		{
			L.Hint = L.Subtitle;      // what Yes does, where the Title's sub-line sits
		}
		else if (L.NumItems > 0)
		{
			const FRect& Last = L.Plate[L.NumItems - 1];
			L.Hint = {X + P.Px(8.f), Last.Y + Last.H + P.Px(HintGap)};
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
		case EItem::NewGame: return EMenuText::NewGame;
		case EItem::ConfirmNo: return EMenuText::ConfirmNo;
		case EItem::ConfirmYes: return EMenuText::ConfirmYes;
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
		case EItem::Sound: return M.SoundLevel;
		case EItem::Music: return M.MusicLevel;
		case EItem::Vibration: return M.bVibration ? 1 : 0;
		case EItem::ConfirmNo:
		case EItem::ConfirmYes: return M.Ask == EAsk::NewGame ? 1 : 0;
		default: return 0;
		}
	}

	/** The hint line for the focused item (and on a Confirm, what Yes does). */
	inline EHint HintOf(const FMenuModel& M, EItem I)
	{
		if (M.Screen == EScreen::Confirm)
		{
			return M.Ask == EAsk::NewGame ? EHint::AskNewGame : EHint::AskQuit;
		}
		switch (I)
		{
		case EItem::Continue: return EHint::Continue;
		case EItem::Fight: return EHint::Fight;
		case EItem::NewGame: return EHint::NewGame;
		case EItem::Controls: return EHint::Controls;
		case EItem::Settings: return EHint::Settings;
		case EItem::Quit: return EHint::Quit;
		case EItem::Resume: return EHint::Resume;
		case EItem::QuitToTitle: return EHint::QuitToTitle;
		case EItem::Difficulty: return EHint::Difficulty;
		case EItem::Sound: return EHint::Sound;
		case EItem::Music: return EHint::Music;
		case EItem::Vibration: return EHint::Vibration;
		case EItem::Back:
		default: return M.ReturnTo == EScreen::Pause ? EHint::BackPause : EHint::BackTitle;
		}
	}

	/** How far a thing that starts arriving Delay seconds after the screen
	    opened has come, Dur seconds later: 0 not yet, 1 there (ease out). */
	inline float Arrive(const FMenuModel& M, float Delay, float Dur)
	{
		const float T = FMath::Clamp((M.Since - Delay) / Dur, 0.f, 1.f);
		return 1.f - (1.f - T) * (1.f - T) * (1.f - T);
	}
	/** How much of the focus a plate holds now: 1 on the focus at rest, two
	    neighbours sharing it while it glides. */
	inline float FocusWeight(const FMenuModel& M, int i)
	{
		return FMath::Clamp(1.f - FMath::Abs(ShownFocus(M) - static_cast<float>(i)), 0.f, 1.f);
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
		                    SaudControls::EButton Button, EMenuText PadSlot, EMenuText KeySlot, int Value, float Alpha = 1.f)
		{
			const float Stroke = P.Px(SaudHud::TextStroke);
			const FRgba Word = SaudHud::WithAlpha(Colour::Bone, Alpha);
			if (M.Pad == SaudControls::EPad::Keyboard)
			{
				Out.Text(KeySlot, Value, 0, {X, Baseline - H}, H, Word, Stroke, false, -1, EMenuPart::Glyph);
				return X + TextWidth(KeySlot, Value, H) + P.Px(PromptGap);
			}
			const float Size = P.Px(GlyphSize);
			const float GW = Size * GlyphWide(Button);
			// the sink fades the whole glyph, its rim with it: the colours go in whole
			FMenuSink Sink(Out, EMenuPart::Glyph, -1, static_cast<int>(M.Pad), Alpha);
			// a tab's rim is grown round it, so a glyph stands its rim above the line
			SaudControls::Glyph(Button, M.Pad, X + 0.5f * GW, Baseline - 0.5f * Size - SaudControls::GlyphRim * Size, Size,
			                    Colour::Ink, Colour::Bone, Sink);
			const float TX = X + GW + P.Px(GlyphGap);
			Out.Text(PadSlot, Value, 0, {TX, Baseline - H}, H, Word, Stroke, false, -1, EMenuPart::Glyph);
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
			// the torn ink wash behind the column, wiping open from the left
			// as the screen opens; the heading, the blood slash wiping open
			// under it, and on the Title the sub-line (on a Confirm, what
			// Yes does: the hint below)
			FRect Wash = L.Wash;
			Wash.W *= Arrive(M, 0.f, WashWipeSeconds);
			if (Wash.W >= 2.f)
			{
				Detail::TornWash(Out, P, Wash, 5.f, WashAlpha, WashFadeFrom);
			}
			const float HeadA = Arrive(M, 0.05f, 0.25f);
			EMenuText Head = EMenuText::SettingsHead;
			int HeadV = 0;
			if (M.Screen == EScreen::Title) Head = EMenuText::Saud;
			else if (M.Screen == EScreen::Pause) Head = EMenuText::Paused;
			else if (M.Screen == EScreen::Confirm) { Head = EMenuText::AskHead; HeadV = M.Ask == EAsk::NewGame ? 1 : 0; }
			Out.Text(Head, HeadV, 0, L.Heading, L.HeadingH, SaudHud::WithAlpha(Colour::Bone, HeadA), Stroke, false, -1,
			         EMenuPart::Wash);
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
				Out.Text(EMenuText::Subtitle, 0, 0, L.Subtitle, P.Px(SubText), SaudHud::WithAlpha(Colour::Bone, DimAlpha * HeadA),
				         Stroke, false, -1, EMenuPart::Wash);
			}
		}

		// the items: leaning plates, the focused one blood in a bone
		// keyline with a bone label, the rest trough in a dim ash keyline
		// with a dim label. The focus glides: while it moves two
		// neighbours share it, each lit and nudged out of the column by
		// its share. Each plate slides in from the left as the screen
		// opens, one after another.
		const float H = P.Px(LabelText);
		const FRgba DimKey = SaudHud::WithAlpha(Colour::Ash, DimAlpha);
		for (int i = 0; i < N; ++i)
		{
			const bool bColumn = M.Screen != EScreen::Controls;
			const float W = FocusWeight(M, i);
			const float In = bColumn ? Arrive(M, PlateDelay + PlateStagger * static_cast<float>(i), PlateArrive) : 1.f;
			FRect R = L.Plate[i];
			if (bColumn)
			{
				R.X += P.Px(FocusNudge) * W - P.Px(SlideIn) * (1.f - In);
			}
			const auto Fade = [In](FRgba C) { C.A *= In; return C; };
			Detail::Plate(Out, R, Fade(SaudHud::LerpColour(UnfocusedFill(), FocusFill(M.Clock), W)),
			              Fade(SaudHud::LerpColour(DimKey, Colour::Bone, W)), Key, i);
			const FRgba Label = Fade(SaudHud::LerpColour(DimText(), Colour::Bone, W));
			const FPoint At = {R.X + R.H * PlateLean + P.Px(LabelIn), R.Y + 0.5f * (R.H - H)};
			Out.Text(SlotOf(List[i]), ValueOf(M, List[i]), 0, At, H, Label, Stroke, false, i, EMenuPart::Plate);
			// CONTINUE carries where the save has got to, right on its plate
			if (List[i] == EItem::Continue && M.StageReached > 0)
			{
				const float TH = P.Px(TagText);
				const float TW = TextWidth(EMenuText::StageTag, M.StageReached, TH, M.StageCount);
				Out.Text(EMenuText::StageTag, M.StageReached, M.StageCount,
				         {R.X + R.W - P.Px(LabelIn) - TW, R.Y + 0.5f * (R.H - TH)}, TH, Label, Stroke, false, i,
				         EMenuPart::Plate);
			}
			// a level: ten segments, as many lit as the level, right on its plate
			if (List[i] == EItem::Sound || List[i] == EItem::Music)
			{
				const int Lit = ValueOf(M, List[i]);
				const float MW = P.Px(MeterW), MH = P.Px(MeterH), Gap = P.Px(MeterGap);
				const float SW = (MW - Gap * static_cast<float>(LevelMax - 1)) / static_cast<float>(LevelMax);
				const float X0 = R.X + R.W - P.Px(LabelIn) - MW, Y0 = R.Y + 0.5f * (R.H - MH);
				for (int k = 0; k < LevelMax; ++k)
				{
					FPoint Q[4];
					SaudHud::LeanQuad({X0 + static_cast<float>(k) * (SW + Gap), Y0, SW, MH}, 1.f, PlateLean, Q);
					const FRgba C = k < Lit ? Label : Fade(SaudHud::WithAlpha(Colour::Ash, DimAlpha * 0.6f));
					Out.Quad(Q, C, EMenuPart::Meter, i, k < Lit ? 1 : 0);
				}
			}
		}

		// the hint: one dim line under the column saying what the focused
		// item does; on a Confirm, under the slash, what Yes does
		if (M.Screen != EScreen::Controls && N > 0)
		{
			const EHint Hn = HintOf(M, List[M.Focus < 0 ? 0 : (M.Focus >= N ? N - 1 : M.Focus)]);
			const float A = Arrive(M, 0.25f, 0.25f);
			Out.Text(EMenuText::Hint, static_cast<int>(Hn), 0, L.Hint, L.HintH, SaudHud::WithAlpha(Colour::Bone, DimAlpha * A),
			         Stroke, false, -1, EMenuPart::Wash);
		}

		// the prompt strip along the bottom safe line
		{
			const float Baseline = P.Bottom();
			float X = L.StripAt.X;
			const float SH = L.StripH;
			const float A = M.Screen == EScreen::Controls ? 1.f : Arrive(M, 0.25f, 0.25f);
			switch (M.Screen)
			{
			case EScreen::Title:
				// Back on the Title asks to quit: the strip says so
				X = Detail::Prompt(Out, P, M, X, Baseline, SH, EButton::FaceSouth, EMenuText::PromptSelect,
				                   EMenuText::KeySelect, 0, A);
				X = Detail::Prompt(Out, P, M, X, Baseline, SH, EButton::FaceEast, EMenuText::PromptQuit,
				                   EMenuText::KeyQuit, 0, A);
				break;
			case EScreen::Pause:
			case EScreen::Confirm:
				X = Detail::Prompt(Out, P, M, X, Baseline, SH, EButton::FaceSouth, EMenuText::PromptSelect,
				                   EMenuText::KeySelect, 0, A);
				X = Detail::Prompt(Out, P, M, X, Baseline, SH, EButton::FaceEast, EMenuText::PromptBack,
				                   EMenuText::KeyBack, 0, A);
				break;
			case EScreen::Settings:
				X = Detail::Prompt(Out, P, M, X, Baseline, SH, EButton::FaceSouth, EMenuText::PromptSelect,
				                   EMenuText::KeySelect, 0, A);
				X = Detail::Prompt(Out, P, M, X, Baseline, SH, EButton::FaceEast, EMenuText::PromptBack,
				                   EMenuText::KeyBack, 0, A);
				X = Detail::Prompt(Out, P, M, X, Baseline, SH, EButton::DpadLeft, EMenuText::PromptAdjust,
				                   EMenuText::KeyAdjust, 0, A);
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
