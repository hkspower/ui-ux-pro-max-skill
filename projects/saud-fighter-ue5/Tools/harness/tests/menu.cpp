/**
 * The menu, executed: the model (Navigate wraps and never leaves the item
 * range, Confirm on every item gives the effect the engine must act on,
 * Back leaves a Settings or Controls page for the screen that opened it, a
 * Title with no save has no CONTINUE, the settings rows read and write the
 * model) and the page as SaudMenu::Build DRAWS it (Combat/SaudMenu.h) at
 * every screen, pad and focus, at the seven screen shapes the HUD is held
 * to: title-safe, couch-legible, stroked, the plates apart, exactly one
 * focused item and it 3:1 against the rest, the prompt strip on the bottom
 * safe line with the pad's own glyphs, the palette only, and room in the
 * list.
 *
 * SaudControls.h is the CONTROLS track's, and this builds against the real
 * one. Until it was on disk (2026-09-30 08:01 UTC) it built against a stub
 * of its contract, kept below under SAUD_MENU_STUB_CONTROLS (define it to
 * build without the header again); the stub was never tested, the menu's
 * use of it was.
 */
#include "../HarnessTypes.h"
#include "../../../Source/SaudFighter/Combat/SaudAnime.h"

#if defined(SAUD_MENU_STUB_CONTROLS)
namespace SaudControls
{
	using SaudHud::FPoint;
	using SaudHud::FRgba;
	enum class EPad { Xbox, PlayStation, Keyboard };
	enum class EButton { FaceSouth, FaceEast, FaceWest, FaceNorth, LB, RB, LT, RT, L3, R3,
	                     Menu, View, DpadUp, DpadDown, DpadLeft, DpadRight, LeftStick, RightStick, Count };
	enum class EAction { Move, Look, Punch, Kick, Block, Dash, Rage, Pause,
	                     NavUp, NavDown, NavLeft, NavRight, Confirm, Back, FlipPad, Count };
	enum class EControlsPart : unsigned char { Rim, Face, Body, Line, Label };
	constexpr float TabWide = 2.3f, TriggerWide = 1.9f, GlyphRim = 0.06f;
	constexpr float HeadBand = 100.f, FootBand = 90.f;
	enum class EControlsText : unsigned char { ButtonLabel, ActionName, Unbound, KeyName };
	struct FGlyphSink
	{
		virtual ~FGlyphSink() {}
		virtual void Tri(const FPoint& A, const FRgba& CA, const FPoint& B, const FRgba& CB, const FPoint& C,
		                 const FRgba& CC, EControlsPart Part) = 0;
		virtual void Text(EControlsText Slot, int Value, const FPoint& At, float Height, const FRgba& C, float Stroke,
		                  bool bCentre) = 0;
	};
	static int StubGlyphPad[3] = {0, 0, 0};   // how often Glyph was asked for each pad
	inline void Glyph(EButton Button, EPad Pad, float CX, float CY, float Size, FRgba Ink, FRgba Fill, FGlyphSink& Out)
	{
		++StubGlyphPad[static_cast<int>(Pad)];
		const FPoint C = {CX, CY};
		const float R = 0.5f * Size, Ri = R - 2.f;
		for (int i = 0; i < 12; ++i)
		{
			const float A0 = 6.2831853f * static_cast<float>(i) / 12.f, A1 = 6.2831853f * static_cast<float>(i + 1) / 12.f;
			Out.Tri(C, Ink, {CX + R * std::cos(A0), CY + R * std::sin(A0)}, Ink,
			        {CX + R * std::cos(A1), CY + R * std::sin(A1)}, Ink, EControlsPart::Rim);
		}
		for (int i = 0; i < 12; ++i)
		{
			const float A0 = 6.2831853f * static_cast<float>(i) / 12.f, A1 = 6.2831853f * static_cast<float>(i + 1) / 12.f;
			Out.Tri(C, Fill, {CX + Ri * std::cos(A0), CY + Ri * std::sin(A0)}, Fill,
			        {CX + Ri * std::cos(A1), CY + Ri * std::sin(A1)}, Fill, EControlsPart::Face);
		}
		Out.Text(EControlsText::ButtonLabel, static_cast<int>(Button), {CX, CY - 0.3f * Size}, 0.6f * Size, Ink, 0.f, true);
	}
	inline void BuildControlsPage(const SaudHud::FPage& P, EPad Shown, FGlyphSink& Out)
	{
		// a stand-in: one plate in the middle of the safe area with two labels
		const float X0 = P.Left() + P.Px(300.f), X1 = P.Right() - P.Px(300.f);
		const float Y0 = P.Top() + P.Px(120.f), Y1 = P.Bottom() - P.Px(200.f);
		const FRgba C = SaudHud::WithAlpha(SaudHud::Colour::Trough, 0.8f);
		Out.Tri({X0, Y1}, C, {X0, Y0}, C, {X1, Y0}, C, EControlsPart::Body);
		Out.Tri({X0, Y1}, C, {X1, Y0}, C, {X1, Y1}, C, EControlsPart::Body);
		Out.Text(EControlsText::ActionName, static_cast<int>(Shown), {X0 + P.Px(20.f), Y0 + P.Px(20.f)}, P.Px(40.f),
		         SaudHud::Colour::Bone, P.Px(3.f), false);
		Glyph(EButton::FaceSouth, Shown, X0 + P.Px(60.f), Y0 + P.Px(120.f), P.Px(60.f), SaudHud::Colour::Ink,
		      SaudHud::Colour::Bone, Out);
	}
}
#endif

#include "../../../Source/SaudFighter/Combat/SaudMenu.h"

#include <cstdio>
#include <cmath>
#include <initializer_list>

static int Fails = 0;
static void Check(bool Ok, const char* What)
{
	if (!Ok) { ++Fails; std::printf("  FAIL  %s\n", What); }
}
static bool Near(float A, float B, float Eps = 1e-4f) { return std::fabs(A - B) <= Eps; }

using namespace SaudMenu;
using SaudControls::EAction;
using SaudControls::EPad;

// ------------------------------------------------------------ helpers
static const float Shapes[][2] = {{1920, 1080}, {1280, 720}, {3840, 2160}, {2560, 1080},
                                  {3440, 1440}, {1600, 1200}, {1680, 1050}};
static FMenuList List;

// Title-safe is the broadcast standard, 90 % of each dimension -- written
// here rather than read from the header, so a header that forgot it fails.
static bool InSafe(const FPage& P, float X, float Y)
{
	const float E = 0.5f, MX = 0.05f * P.ScreenW, MY = 0.05f * P.ScreenH;
	return X >= MX - E && Y >= MY - E && X <= P.ScreenW - MX + E && Y <= P.ScreenH - MY + E;
}
static float Cross(const FPoint& A, const FPoint& B, const FPoint& C)
{
	return (B.X - A.X) * (C.Y - A.Y) - (B.Y - A.Y) * (C.X - A.X);
}
/** WCAG 2.1 contrast of two linear colours (alpha ignored). */
static float Contrast(const FRgba& A, const FRgba& B)
{
	const float La = 0.2126f * A.R + 0.7152f * A.G + 0.0722f * A.B;
	const float Lb = 0.2126f * B.R + 0.7152f * B.G + 0.0722f * B.B;
	return (std::fmax(La, Lb) + 0.05f) / (std::fmin(La, Lb) + 0.05f);
}
static bool SameRgb(const FRgba& A, const FRgba& B, float Eps = 1e-4f)
{
	return Near(A.R, B.R, Eps) && Near(A.G, B.G, Eps) && Near(A.B, B.B, Eps);
}
struct FBox { float X0 = 1e9f, Y0 = 1e9f, X1 = -1e9f, Y1 = -1e9f; bool Any = false; };
static void Add(FBox& B, const FPoint& P)
{
	B.X0 = std::fmin(B.X0, P.X); B.Y0 = std::fmin(B.Y0, P.Y);
	B.X1 = std::fmax(B.X1, P.X); B.Y1 = std::fmax(B.Y1, P.Y); B.Any = true;
}
static bool Overlap(const FBox& A, const FBox& B)
{
	return A.Any && B.Any && A.X0 < B.X1 && B.X0 < A.X1 && A.Y0 < B.Y1 && B.Y0 < A.Y1;
}
static FBox ItemBox(int Item, bool bPlateOnly)
{
	FBox B;
	for (int t = 0; t < List.NumTris; ++t)
	{
		const FMenuTri& T = List.Tris[t];
		if (T.Item != Item) continue;
		if (T.Part != EMenuPart::Plate && (bPlateOnly || T.Part != EMenuPart::Keyline)) continue;
		for (const FMenuVert& V : T.V) Add(B, V.P);
	}
	return B;
}
static FBox PartBox(EMenuPart Pt)
{
	FBox B;
	for (int t = 0; t < List.NumTris; ++t)
		if (List.Tris[t].Part == Pt)
			for (const FMenuVert& V : List.Tris[t].V) Add(B, V.P);
	return B;
}
static int CountPart(EMenuPart Pt)
{
	int N = 0;
	for (int t = 0; t < List.NumTris; ++t) N += List.Tris[t].Part == Pt;
	return N;
}
static const FMenuText* FindText(EMenuText Slot)
{
	for (int t = 0; t < List.NumTexts; ++t)
		if (List.Texts[t].Slot == Slot) return &List.Texts[t];
	return nullptr;
}
static const FMenuText* ItemText(int Item)
{
	for (int t = 0; t < List.NumTexts; ++t)
		if (List.Texts[t].Item == Item) return &List.Texts[t];
	return nullptr;
}
/** A text's box from its anchor and the header's own width estimate. */
static FBox TextBox(const FMenuText& X)
{
	const float W = TextWidth(X.Slot, X.Value, X.Height);
	FBox B;
	Add(B, {X.bCentre ? X.At.X - 0.5f * W : X.At.X, X.At.Y});
	Add(B, {X.bCentre ? X.At.X + 0.5f * W : X.At.X + W, X.At.Y + X.Height});
	return B;
}
/** The plate's own fill, ignoring its keyline. */
static bool PlateFill(int Item, FRgba& Out)
{
	for (int t = 0; t < List.NumTris; ++t)
		if (List.Tris[t].Item == Item && List.Tris[t].Part == EMenuPart::Plate) { Out = List.Tris[t].V[0].C; return true; }
	return false;
}
static bool IsPalette(const FRgba& C)
{
	using namespace SaudHud::Colour;
	if (SameRgb(C, Ink) || SameRgb(C, Bone) || SameRgb(C, Blood) || SameRgb(C, Ember) || SameRgb(C, Trough)
	    || SameRgb(C, Ash) || SameRgb(C, Gold) || SameRgb(C, System) || SameRgb(C, Panel) || SameRgb(C, Shadow)
	    || SameRgb(C, Danger) || SameRgb(C, Ice)) return true;
	// or on the focus's line from the panel to the System's cyan
	const float T = (C.G - Panel.G) / (System.G - Panel.G);
	return T >= -1e-4f && T <= 1.f + 1e-4f && Near(C.R, Panel.R + (System.R - Panel.R) * T, 1e-3f)
	       && Near(C.B, Panel.B + (System.B - Panel.B) * T, 1e-3f);
}
static bool Mine(EMenuPart Pt)
{
	return Pt != EMenuPart::Glyph && Pt != EMenuPart::Diagram;
}

/** Where an item sits on the model's screen, or -1. */
static int IndexOf(const FMenuModel& M, EItem It)
{
	EItem I[MaxItems] = {};
	const int N = Items(M, I);
	for (int k = 0; k < N; ++k) if (I[k] == It) return k;
	return -1;
}

/** A model on a screen, opened the way the engine opens it: Title or Pause
    by Open, Settings and Controls through the item that opens them, a
    Confirm through QUIT or NEW GAME on the Title. */
static FMenuModel Model(EScreen S, bool bSave, EPad Pad, EScreen From = EScreen::Title, EAsk Ask = EAsk::Quit)
{
	FMenuModel M;
	M.bHasSave = bSave;
	M.Pad = Pad;
	const bool bSub = S == EScreen::Settings || S == EScreen::Controls || S == EScreen::Confirm;
	Open(M, bSub ? From : S);
	if (S == EScreen::Settings) { M.Focus = IndexOf(M, EItem::Settings); Navigate(M, EAction::Confirm); }
	if (S == EScreen::Controls) { M.Focus = IndexOf(M, EItem::Controls); Navigate(M, EAction::Confirm); }
	if (S == EScreen::Confirm)
	{
		M.Focus = IndexOf(M, Ask == EAsk::NewGame ? EItem::NewGame : EItem::Quit);
		Navigate(M, EAction::Confirm);
	}
	M.Since = 1.f;
	return M;
}

// ---------------------------------------------------------------- MODEL
static void ModelRules()
{
	std::printf("MODEL  (Navigate)\n");
	int Navigated = 0;

	// the items, as the design lists them
	{
		EItem I[MaxItems] = {};
		FMenuModel T = Model(EScreen::Title, false, EPad::Xbox);
		int N = Items(T, I);
		Check(N == 4 && I[0] == EItem::Fight && I[1] == EItem::Controls && I[2] == EItem::Settings && I[3] == EItem::Quit,
		      "Title: FIGHT, CONTROLS, SETTINGS, QUIT");
		T.bHasSave = true;
		N = Items(T, I);
		Check(N == 5 && I[0] == EItem::Continue && I[1] == EItem::NewGame && I[2] == EItem::Controls
		      && I[3] == EItem::Settings && I[4] == EItem::Quit, "Title with a save: CONTINUE, NEW GAME, CONTROLS, SETTINGS, QUIT");
		FMenuModel Cq = Model(EScreen::Confirm, true, EPad::Xbox);
		N = Items(Cq, I);
		Check(Cq.Screen == EScreen::Confirm && N == 2 && I[0] == EItem::ConfirmNo && I[1] == EItem::ConfirmYes
		      && Cq.Focus == 0, "Confirm: NO first, and focused, so a stray press is safe; then YES");
		FMenuModel Pa = Model(EScreen::Pause, true, EPad::Xbox);
		N = Items(Pa, I);
		Check(N == 4 && I[0] == EItem::Resume && I[1] == EItem::Controls && I[2] == EItem::Settings
		      && I[3] == EItem::QuitToTitle, "Pause: RESUME, CONTROLS, SETTINGS, QUIT TO TITLE");
		FMenuModel Se = Model(EScreen::Settings, true, EPad::Xbox);
		N = Items(Se, I);
		Check(Se.Screen == EScreen::Settings && N == 5 && I[0] == EItem::Difficulty && I[1] == EItem::Sound
		      && I[2] == EItem::Music && I[3] == EItem::Vibration && I[4] == EItem::Back,
		      "Settings: DIFFICULTY, SOUND, MUSIC, VIBRATION, BACK");
		FMenuModel Co = Model(EScreen::Controls, true, EPad::Xbox);
		N = Items(Co, I);
		Check(Co.Screen == EScreen::Controls && N == 1 && I[0] == EItem::Back, "Controls: the diagram, and BACK");
	}

	// the focus wraps, both ways, on every screen
	{
		bool Wraps = true;
		const EScreen Screens[5] = {EScreen::Title, EScreen::Pause, EScreen::Settings, EScreen::Controls, EScreen::Confirm};
		for (EScreen S : Screens)
		{
			FMenuModel M = Model(S, true, EPad::Xbox);
			const int N = ItemCount(M);
			Wraps = Wraps && M.Focus == 0;
			Wraps = Wraps && Navigate(M, EAction::NavUp) == EMenuEffect::Tap && M.Focus == N - 1;
			Wraps = Wraps && Navigate(M, EAction::NavDown) == EMenuEffect::Tap && M.Focus == 0;
			for (int i = 0; i < N; ++i) Navigate(M, EAction::NavDown);
			Wraps = Wraps && M.Focus == 0;
			Navigated += N + 2;
		}
		Check(Wraps, "the focus wraps at both ends of every screen");
	}

	// ...and never leaves the item range, whatever is pressed (every action
	// the pad and keyboard can send, in a fixed pseudo-random order)
	{
		bool InRange = true, ShownIsPad = true, DiffIn = true, LevelsIn = true;
		unsigned Seed = 12345u;
		FMenuModel M = Model(EScreen::Title, true, EPad::PlayStation);
		for (int i = 0; i < 6000; ++i)
		{
			Seed = Seed * 1664525u + 1013904223u;
			const EAction A = static_cast<EAction>((Seed >> 16) % static_cast<unsigned>(EAction::Count));
			const EMenuEffect E = Navigate(M, A);
			++Navigated;
			// a flow effect closes the menu: the engine reopens the Title
			if (E == EMenuEffect::StartGame || E == EMenuEffect::QuitGame || E == EMenuEffect::QuitToTitle
			    || E == EMenuEffect::NewGame)
			{
				Open(M, EScreen::Title);
				M.bHasSave = (Seed & 1u) != 0u;
			}
			if (E == EMenuEffect::Resume) Open(M, (Seed & 2u) ? EScreen::Pause : EScreen::Title);
			InRange = InRange && M.Focus >= 0 && M.Focus < ItemCount(M);
			ShownIsPad = ShownIsPad && M.Shown != EPad::Keyboard;
			DiffIn = DiffIn && M.DifficultyIndex >= 0 && M.DifficultyIndex <= 2;
			LevelsIn = LevelsIn && M.SoundLevel >= 0 && M.SoundLevel <= LevelMax && M.MusicLevel >= 0
			           && M.MusicLevel <= LevelMax;
			Step(M, 1.f / 60.f);
		}
		Check(LevelsIn, "the sound and music levels stay 0..10");
		Check(InRange, "the focus never leaves the item range, whatever is pressed");
		Check(ShownIsPad, "the diagram never shows a keyboard");
		Check(DiffIn, "the difficulty stays 0..2");
	}

	// Confirm on each item yields the right effect
	{
		FMenuModel M = Model(EScreen::Title, false, EPad::Xbox);
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::StartGame && M.Screen == EScreen::Title, "FIGHT starts the game");
		M = Model(EScreen::Title, true, EPad::Xbox);
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::StartGame, "CONTINUE starts the game (the engine loads the save)");
		M.Focus = IndexOf(M, EItem::Controls);
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::Tap && M.Screen == EScreen::Controls && M.Focus == 0,
		      "CONTROLS opens the controls page, focus at its top");
		M = Model(EScreen::Title, true, EPad::Xbox);
		M.Focus = IndexOf(M, EItem::Settings);
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::Tap && M.Screen == EScreen::Settings && M.Focus == 0,
		      "SETTINGS opens the settings, focus at its top");
		// QUIT and NEW GAME ask first; NO (and Back) go back to the item asked from
		for (const bool bSave : {false, true})
		{
			M = Model(EScreen::Title, bSave, EPad::Xbox);
			const int Q = IndexOf(M, EItem::Quit);
			M.Focus = Q;
			Check(Navigate(M, EAction::Confirm) == EMenuEffect::Tap && M.Screen == EScreen::Confirm && M.Ask == EAsk::Quit
			      && M.Focus == 0, "QUIT asks first, on NO");
			Check(Navigate(M, EAction::Confirm) == EMenuEffect::Back && M.Screen == EScreen::Title && M.Focus == Q,
			      "...NO goes back to QUIT");
			Navigate(M, EAction::Confirm);
			Navigate(M, EAction::NavDown);
			Check(Navigate(M, EAction::Confirm) == EMenuEffect::QuitGame, "...YES quits the game");
		}
		M = Model(EScreen::Title, true, EPad::Xbox);
		const int Ng = IndexOf(M, EItem::NewGame);
		M.Focus = Ng;
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::Tap && M.Screen == EScreen::Confirm && M.Ask == EAsk::NewGame
		      && M.Focus == 0, "NEW GAME asks first, on NO");
		Check(Navigate(M, EAction::Back) == EMenuEffect::Back && M.Screen == EScreen::Title && M.Focus == Ng,
		      "...Back is NO: back to NEW GAME");
		Navigate(M, EAction::Confirm);
		Navigate(M, EAction::NavUp);
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::NewGame, "...YES starts a new game");
		Check(IndexOf(Model(EScreen::Title, false, EPad::Xbox), EItem::NewGame) < 0, "no NEW GAME without a save: FIGHT is one");
		M = Model(EScreen::Title, true, EPad::Xbox);
		M.Focus = 2;
		Check(Navigate(M, EAction::Back) == EMenuEffect::Tap && M.Screen == EScreen::Confirm && M.Ask == EAsk::Quit
		      && M.Focus == 0, "Back on the Title asks to quit, on NO");

		M = Model(EScreen::Pause, true, EPad::Xbox);
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::Resume, "RESUME resumes");
		M.Focus = 3;
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::QuitToTitle, "QUIT TO TITLE quits to the title");
		M.Focus = 1;
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::Tap && M.Screen == EScreen::Controls, "the pause's CONTROLS opens the page");
		Check(Navigate(M, EAction::Pause) == EMenuEffect::None, "the pause button does nothing on a sub-page");
		M = Model(EScreen::Pause, true, EPad::Xbox);
		Check(Navigate(M, EAction::Pause) == EMenuEffect::Resume, "the pause button resumes from the pause");
		M = Model(EScreen::Title, true, EPad::Xbox);
		Check(Navigate(M, EAction::Pause) == EMenuEffect::None && Navigate(M, EAction::Punch) == EMenuEffect::None
		      && M.Focus == 0 && M.Screen == EScreen::Title, "the fight's actions do nothing on the title");

		M = Model(EScreen::Settings, true, EPad::Xbox);
		M.DifficultyIndex = 1;
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::CycleDifficulty && M.DifficultyIndex == 2,
		      "DIFFICULTY cycles up: PRO -> CHAMPION");
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::CycleDifficulty && M.DifficultyIndex == 0, "...CHAMPION -> ROOKIE");
		Check(Navigate(M, EAction::NavLeft) == EMenuEffect::CycleDifficulty && M.DifficultyIndex == 2, "left goes back: ROOKIE -> CHAMPION");
		Check(Navigate(M, EAction::NavRight) == EMenuEffect::CycleDifficulty && M.DifficultyIndex == 0, "right goes on");
		M.Focus = 1;
		M.SoundLevel = LevelMax;
		Check(RepeatsSideways(M), "left/right repeat when held on SOUND");
		Check(Navigate(M, EAction::NavLeft) == EMenuEffect::SetSound && M.SoundLevel == LevelMax - 1, "left turns SOUND down a step");
		Check(Navigate(M, EAction::NavRight) == EMenuEffect::SetSound && M.SoundLevel == LevelMax, "right turns it up");
		Check(Navigate(M, EAction::NavRight) == EMenuEffect::Denied && M.SoundLevel == LevelMax, "...and stops at the top, denied");
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::SetSound && M.SoundLevel == 0, "Confirm goes round: 10 -> OFF");
		Check(Navigate(M, EAction::NavLeft) == EMenuEffect::Denied && M.SoundLevel == 0, "left stops at OFF, denied");
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::SetSound && M.SoundLevel == 1, "Confirm: OFF -> 1");
		M.Focus = 2;
		M.MusicLevel = 5;
		Check(Navigate(M, EAction::NavLeft) == EMenuEffect::SetMusic && M.MusicLevel == 4 && RepeatsSideways(M),
		      "MUSIC is a level too");
		M.Focus = 0;
		Check(!RepeatsSideways(M), "...the difficulty does not repeat sideways");
		M.Focus = 3;
		M.bVibration = false;
		Check(!RepeatsSideways(M), "...nor does VIBRATION");
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::ToggleVibration && M.bVibration, "VIBRATION toggles the model");
		M.Focus = 4;
		Check(Navigate(M, EAction::NavLeft) == EMenuEffect::None && M.Focus == 4, "left on BACK is nothing");
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::Back && M.Screen == EScreen::Title, "BACK goes back");
		M = Model(EScreen::Controls, true, EPad::Xbox);
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::Back && M.Screen == EScreen::Title, "the controls' BACK goes back");
		Navigated += 22;
	}

	// Back on Settings/Controls returns to the screen they were opened
	// from, with the focus on the item that opened them
	{
		bool Ok = true;
		const EScreen Subs[2] = {EScreen::Settings, EScreen::Controls};
		const EScreen Froms[2] = {EScreen::Title, EScreen::Pause};
		for (EScreen From : Froms)
		{
			for (EScreen Sub : Subs)
			{
				FMenuModel M = Model(Sub, true, EPad::Xbox, From);
				FMenuModel Before = M;
				Open(Before, From);
				Before.bHasSave = true;
				const int Opener = IndexOf(Before, Sub == EScreen::Settings ? EItem::Settings : EItem::Controls);
				Ok = Ok && M.Screen == Sub && M.ReturnTo == From;
				Navigate(M, EAction::NavDown);
				Ok = Ok && Navigate(M, EAction::Back) == EMenuEffect::Back && M.Screen == From && M.Focus == Opener;
				// and Back there is the screen's own
				const EMenuEffect E = Navigate(M, EAction::Back);
				Ok = Ok && (From == EScreen::Title ? (E == EMenuEffect::Tap && M.Screen == EScreen::Confirm)
				                                   : (E == EMenuEffect::Resume && M.Screen == From));
				Navigated += 3;
			}
		}
		Check(Ok, "Back on Settings/Controls returns to the screen they were opened from, on the item that opened them");
		Check(Ok, "Back on the Title asks to quit, on the Pause it resumes");
	}

	// the diagram's pad: the pad in the hand when the page opens, flipped by
	// FlipPad or left/right, never a keyboard
	{
		FMenuModel M = Model(EScreen::Controls, true, EPad::PlayStation);
		bool Ok = M.Shown == EPad::PlayStation;
		Ok = Ok && Navigate(M, EAction::FlipPad) == EMenuEffect::Tap && M.Shown == EPad::Xbox;
		Ok = Ok && Navigate(M, EAction::NavLeft) == EMenuEffect::Tap && M.Shown == EPad::PlayStation;
		Ok = Ok && Navigate(M, EAction::NavRight) == EMenuEffect::Tap && M.Shown == EPad::Xbox;
		FMenuModel K = Model(EScreen::Title, true, EPad::Keyboard);
		K.Shown = EPad::PlayStation;
		K.Focus = IndexOf(K, EItem::Controls);
		Navigate(K, EAction::Confirm);
		Ok = Ok && K.Shown == EPad::PlayStation;
		FMenuModel T = Model(EScreen::Title, true, EPad::Xbox);
		Ok = Ok && Navigate(T, EAction::FlipPad) == EMenuEffect::None && T.Screen == EScreen::Title;
		Check(Ok, "the diagram opens on the pad in the hand and flips Xbox <-> PS5; the keyboard keeps what was shown");
		Navigated += 6;
	}

	// the focus glides: from where it is drawn to the new item over
	// FocusGlideSeconds, never past it, the shares always adding to one; it
	// jumps across the wrap and when a screen opens
	{
		bool Glides = true, Jumps = true;
		FMenuModel M = Model(EScreen::Title, true, EPad::Xbox);
		Navigate(M, EAction::NavDown);
		float Prev = ShownFocus(M);
		Glides = Glides && Near(Prev, 0.f);
		bool Halfway = false;
		for (int f = 0; f < 30; ++f)
		{
			Step(M, 1.f / 60.f);
			const float F = ShownFocus(M);
			Glides = Glides && F >= Prev - 1e-5f && F <= 1.f + 1e-5f;
			float Sum = 0.f;
			for (int i = 0; i < ItemCount(M); ++i) Sum += FocusWeight(M, i);
			Glides = Glides && Near(Sum, 1.f, 1e-4f);
			if (f == 5) Halfway = F > 0.25f && F < 0.9f;       // 0.1 s in: on its way
			Prev = F;
		}
		Glides = Glides && Halfway && Near(ShownFocus(M), 1.f);
		M.FocusT = 0.f;
		Step(M, FocusGlideSeconds + 1e-4f);
		Glides = Glides && Near(ShownFocus(M), 1.f);
		M = Model(EScreen::Title, true, EPad::Xbox);
		Navigate(M, EAction::NavUp);
		Jumps = Jumps && Near(ShownFocus(M), static_cast<float>(ItemCount(M) - 1));
		M = Model(EScreen::Pause, true, EPad::Xbox);
		Navigate(M, EAction::NavDown);
		Navigate(M, EAction::Confirm);              // CONTROLS, mid-glide
		Jumps = Jumps && M.Screen == EScreen::Controls && Near(ShownFocus(M), 0.f);
		Check(Glides, "the focus glides to the next item over 0.18 s, never past it, its shares adding to one");
		Check(Jumps, "...and jumps across the wrap and when a screen opens");
		Navigated += 5;
	}
	std::printf("  %d navigations\n", Navigated);
}

// ----------------------------------------------------------------- PAGE
struct FCase { EScreen Screen; bool bSave; EScreen From; const char* Name; EAsk Ask; };
static const FCase Cases[] = {
	{EScreen::Title, false, EScreen::Title, "title", EAsk::Quit},
	{EScreen::Title, true, EScreen::Title, "title+save", EAsk::Quit},
	{EScreen::Pause, true, EScreen::Pause, "pause", EAsk::Quit},
	{EScreen::Settings, true, EScreen::Title, "settings", EAsk::Quit},
	{EScreen::Settings, true, EScreen::Pause, "settings from pause", EAsk::Quit},
	{EScreen::Controls, true, EScreen::Title, "controls", EAsk::Quit},
	{EScreen::Controls, true, EScreen::Pause, "controls from pause", EAsk::Quit},
	{EScreen::Confirm, false, EScreen::Title, "confirm quit", EAsk::Quit},
	{EScreen::Confirm, true, EScreen::Title, "confirm new game", EAsk::NewGame},
};
static const EPad Pads[3] = {EPad::Xbox, EPad::PlayStation, EPad::Keyboard};
static const float Clocks[4] = {0.f, 0.7f, 1.3f, 2.05f};

static void PageRules()
{
	std::printf("PAGE  (what Build draws)\n");
	bool NoNaN = true, AllIn = true, TextIn = true, Legible = true, Stroked = true, Bright = true, Wound = true;
	bool Apart = true, OneFocus = true, FocusReads = true, Labelled = true, Palette = true, Fits = true;
	bool StripOnLine = true, StripPad = true, StripApart = true, ScrimWhole = true, Heading = true;
	bool Continue = true, ValuesRead = true, Pulses = true, OffDiagram = true, BigGlyphs = true, StripWords = true;
	float GapOf[5] = {-1.f, -1.f, -1.f, -1.f, -1.f};   // slash bottom to the first plate, page px, per screen
	bool Hinted = true, Tagged = true, Metered = true, Nudged = true;
	bool GapsAgree = true;
	int Builds = 0, WorstTris = 0, WorstTexts = 0;
	const char* WorstName = "";
	for (const auto& Sh : Shapes)
	{
		const FPage P = FPage::For(Sh[0], Sh[1]);
		for (const FCase& C : Cases)
		{
			for (EPad Pad : Pads)
			{
				FMenuModel Base = Model(C.Screen, C.bSave, Pad, C.From, C.Ask);
				const int N = ItemCount(Base);
				for (int Focus = 0; Focus < N; ++Focus)
				{
					for (float Clock : Clocks)
					{
						FMenuModel M = Base;
						M.Focus = Focus;
						M.Clock = Clock;
						M.FocusFrom = static_cast<float>(Focus);   // at rest: the glide has its own rule
						M.DifficultyIndex = Focus % 3;
						M.SoundLevel = (Focus * 3 + 1) % (LevelMax + 1);
						M.MusicLevel = Clock > 1.f ? LevelMax : 0;
						M.bVibration = Focus == 0;
						M.StageReached = C.bSave ? 1 + (Focus * 4) % 9 : 0;
						Build(P, M, List);
						++Builds;
						if (List.NumTris > WorstTris) { WorstTris = List.NumTris; WorstName = C.Name; }
						if (List.NumTexts > WorstTexts) WorstTexts = List.NumTexts;
						Fits = Fits && !List.bOverflow;

						// every vertex: a number, inside title-safe (the scrim
						// excepted: it must cover the screen), wound the same way
						for (int t = 0; t < List.NumTris; ++t)
						{
							const FMenuTri& T = List.Tris[t];
							for (const FMenuVert& V : T.V)
							{
								if (!(V.P.X == V.P.X) || !(V.P.Y == V.P.Y)) NoNaN = false;
								if (T.Part != EMenuPart::Scrim && !InSafe(P, V.P.X, V.P.Y)) AllIn = false;
								if (Mine(T.Part) && !IsPalette(V.C)) Palette = false;
							}
							if (Mine(T.Part) && !(Cross(T.V[0].P, T.V[1].P, T.V[2].P) > 1e-3f)) Wound = false;
						}
						// every text inside title-safe, legible, stroked, bright
						// (SaudControls' own texts are held to the safe area
						// here and to their sizes in their own test)
						for (int t = 0; t < List.NumTexts; ++t)
						{
							const FMenuText& X = List.Texts[t];
							const FBox B = TextBox(X);
							TextIn = TextIn && InSafe(P, B.X0, B.Y0) && InSafe(P, B.X1, B.Y1);
							if (X.Slot == EMenuText::ControlsText) continue;
							Legible = Legible && X.Height >= SaudHud::MinTextShare * P.ScreenH - 0.01f;
							Stroked = Stroked && X.Stroke >= 2.f * P.ScreenH / 720.f - 0.01f
							          && Contrast(X.Colour, SaudHud::Colour::Ink) >= 7.f;
							Bright = Bright && X.Colour.A >= 0.5f;
						}
						// the plates apart, each label on its plate, exactly
						// one focused and it reads against the rest
						int Focused = 0;
						for (int i = 0; i < N; ++i)
						{
							const FBox Bi = ItemBox(i, false);
							for (int j = i + 1; j < N; ++j) if (Overlap(Bi, ItemBox(j, false))) Apart = false;
							const FMenuText* X = ItemText(i);
							const FBox Pl = ItemBox(i, true);
							if (!X || !Pl.Any) { Labelled = false; continue; }
							const FBox TB = TextBox(*X);
							Labelled = Labelled && TB.X0 >= Pl.X0 && TB.X1 <= Pl.X1 && TB.Y0 >= Pl.Y0 && TB.Y1 <= Pl.Y1 + 0.5f;
							FRgba Fill;
							if (!PlateFill(i, Fill)) { OneFocus = false; continue; }
							const bool bStands = Contrast(Fill, UnfocusedFill()) >= 3.f;
							if (bStands) ++Focused;
							if (bStands != (i == Focus)) OneFocus = false;
							if (i == Focus) FocusReads = FocusReads && bStands && SameRgb(X->Colour, SaudHud::Colour::Ice);
							else FocusReads = FocusReads && SameRgb(Fill, SaudHud::Colour::Panel);
						}
						OneFocus = OneFocus && Focused == 1;
						// the settings rows read the model
						if (C.Screen == EScreen::Settings)
						{
							const FMenuText* D = FindText(EMenuText::Difficulty);
							const FMenuText* S = FindText(EMenuText::Sound);
							const FMenuText* Mu = FindText(EMenuText::Music);
							const FMenuText* V = FindText(EMenuText::Vibration);
							ValuesRead = ValuesRead && D && S && Mu && V && D->Value == M.DifficultyIndex
							             && S->Value == M.SoundLevel && Mu->Value == M.MusicLevel
							             && V->Value == (M.bVibration ? 1 : 0);
							// each level a meter of LevelMax segments on its own
							// plate, as many lit as the level, clear of its label
							for (const EItem It : {EItem::Sound, EItem::Music})
							{
								const int i = IndexOf(M, It);
								const int Want = It == EItem::Sound ? M.SoundLevel : M.MusicLevel;
								int Segs = 0, Lit = 0;
								FBox Me;
								for (int t = 0; t < List.NumTris; ++t)
								{
									const FMenuTri& T = List.Tris[t];
									if (T.Part != EMenuPart::Meter || T.Item != i) continue;
									++Segs;
									Lit += T.Tag;
									for (const FMenuVert& V : T.V) Add(Me, V.P);
								}
								const FBox Pl = ItemBox(i, true);
								const FMenuText* X = ItemText(i);
								Metered = Metered && Segs == 2 * LevelMax && Lit == 2 * Want && Me.Any && X
								          && Me.X0 >= Pl.X0 - 0.5f && Me.X1 <= Pl.X1 + 0.5f && Me.Y0 >= Pl.Y0 - 0.5f
								          && Me.Y1 <= Pl.Y1 + 0.5f && !Overlap(Me, TextBox(*X));
							}
						}
						// a Title with no save has no CONTINUE, with one no FIGHT
						if (C.Screen == EScreen::Title)
						{
							Continue = Continue && (FindText(EMenuText::Continue) != nullptr) == C.bSave
							           && (FindText(EMenuText::NewGame) != nullptr) == C.bSave
							           && (FindText(EMenuText::Fight) != nullptr) == !C.bSave;
							// CONTINUE carries the stage reached, right on its own
							// plate, clear of its label
							const FMenuText* Tg = FindText(EMenuText::StageTag);
							if (C.bSave)
							{
								const int i = IndexOf(M, EItem::Continue);
								const FBox Pl = ItemBox(i, true);
								const FMenuText* X = ItemText(i);
								Tagged = Tagged && Tg && X && Tg->Value == M.StageReached && Tg->Aux == M.StageCount
								         && Tg->Item == i && TextBox(*Tg).X1 <= Pl.X1 && TextBox(*Tg).X0 >= TextBox(*X).X1
								         && TextBox(*Tg).Y0 >= Pl.Y0 && TextBox(*Tg).Y1 <= Pl.Y1 + 0.5f;
							}
							else
							{
								Tagged = Tagged && !Tg;
							}
						}
						// the hint: one line saying what the focused item does,
						// on the wash, under the column (on a Confirm, under the
						// slash, what YES does), touching no plate and not the strip
						if (C.Screen != EScreen::Controls)
						{
							int Hints = 0;
							const FMenuText* Hn = nullptr;
							for (int t = 0; t < List.NumTexts; ++t)
								if (List.Texts[t].Slot == EMenuText::Hint) { ++Hints; Hn = &List.Texts[t]; }
							EItem I[MaxItems] = {};
							Items(M, I);
							const FMenuLayout L = Lay(P, M);
							bool Ok = Hints == 1 && Hn && Hn->Item == -1 && Hn->Value == static_cast<int>(HintOf(M, I[Focus]));
							if (Ok)
							{
								const FBox HB = TextBox(*Hn);
								Ok = HB.X1 <= L.Wash.X + L.Wash.W && HB.X0 >= L.Wash.X;
								for (int i = 0; i < N; ++i) Ok = Ok && !Overlap(HB, ItemBox(i, false));
								Ok = Ok && !Overlap(HB, PartBox(EMenuPart::Glyph));
								for (int t = 0; t < List.NumTexts; ++t)
									if (List.Texts[t].Part == EMenuPart::Glyph) Ok = Ok && !Overlap(HB, TextBox(List.Texts[t]));
								if (C.Screen == EScreen::Confirm)
									Ok = Ok && HB.Y0 >= PartBox(EMenuPart::Slash).Y1 && HB.Y1 <= ItemBox(0, false).Y0;
								else
									Ok = Ok && HB.Y0 >= ItemBox(N - 1, false).Y1;
							}
							Hinted = Hinted && Ok;
						}
						// at rest the focused plate stands FocusNudge out of the column
						if (C.Screen != EScreen::Controls && N > 1)
						{
							const int Other = Focus == 0 ? 1 : 0;
							// 14 page px, written here: a header that lost it fails
							Nudged = Nudged && Near(ItemBox(Focus, true).X0 - ItemBox(Other, true).X0, P.Px(14.f), 0.5f);
						}
						// the prompt strip: on the bottom safe line, glyphs for
						// the pad in use (none for the keyboard), nothing touching
						{
							int Glyphs = 0, PadWords = 0, KeyWords = 0, Words = 0;
							FBox Prev;
							bool bPrev = false;
							for (int t = 0; t < List.NumTris; ++t)
							{
								const FMenuTri& T = List.Tris[t];
								if (T.Part != EMenuPart::Glyph) continue;
								++Glyphs;
								StripPad = StripPad && T.Tag == static_cast<int>(Pad);
								for (const FMenuVert& V : T.V)
									StripOnLine = StripOnLine && V.P.Y <= P.Bottom() + 0.5f
									            && V.P.Y >= P.Bottom() - P.Px(GlyphSize) * (1.f + 2.f * SaudControls::GlyphRim) - 0.5f;
							}
							for (int t = 0; t < List.NumTexts; ++t)
							{
								const FMenuText& X = List.Texts[t];
								if (X.Part != EMenuPart::Glyph || X.Slot == EMenuText::ControlsText) continue;
								++Words;
								const bool bPadWord = X.Slot == EMenuText::PromptSelect || X.Slot == EMenuText::PromptBack
								                      || X.Slot == EMenuText::PromptAdjust || X.Slot == EMenuText::PromptFlip
								                      || X.Slot == EMenuText::PromptQuit;
								PadWords += bPadWord;
								KeyWords += !bPadWord;
								StripOnLine = StripOnLine && Near(X.At.Y + X.Height, P.Bottom(), 0.5f);
								StripWords = StripWords && X.Height >= P.Px(32.f) - 0.01f;
								const FBox B = TextBox(X);
								if (bPrev && Overlap(Prev, B)) StripApart = false;
								Prev = B;
								bPrev = true;
								// the glyph for this word is just left of it and clear of it
								if (bPadWord)
								{
									FBox G;
									for (int u = 0; u < X.TrisBefore; ++u)
										if (List.Tris[u].Part == EMenuPart::Glyph)
											for (const FMenuVert& V : List.Tris[u].V) Add(G, V.P);
									StripApart = StripApart && G.Any && G.X1 <= B.X0 + 0.5f;
								}
							}
							// every glyph couch-sized: the first (a face disc) stands
							// its full 48 page px tall
							if (Pad != EPad::Keyboard)
							{
								FBox First;
								for (int t = 0; t < List.NumTris; ++t)
									if (List.Tris[t].Part == EMenuPart::Glyph)
									{
										for (const FMenuVert& V : List.Tris[t].V) Add(First, V.P);
										if (t + 1 < List.NumTris && List.Tris[t + 1].Part != EMenuPart::Glyph) break;
									}
								BigGlyphs = BigGlyphs && First.Any && First.Y1 - First.Y0 >= P.Px(48.f) - 0.5f;
							}
							const int Want = C.Screen == EScreen::Settings ? 3 : 2;   // the Title's Back says QUIT
							StripPad = StripPad && Words == Want
							           && (Pad == EPad::Keyboard ? (Glyphs == 0 && KeyWords == Want)
							                                     : (Glyphs > 0 && PadWords == Want));
							// the Title's Back asks to quit, and its prompt says so
							if (C.Screen == EScreen::Title)
								StripPad = StripPad && FindText(Pad == EPad::Keyboard ? EMenuText::KeyQuit : EMenuText::PromptQuit);
							if (C.Screen == EScreen::Controls)
							{
								const FMenuText* F = FindText(Pad == EPad::Keyboard ? EMenuText::KeyFlip : EMenuText::PromptFlip);
								StripPad = StripPad && F && F->Value == (M.Shown == EPad::Xbox ? 1 : 0);
							}
						}
						// on the controls page nothing of the menu's own -- the BACK
						// plate, the strip -- overlaps SaudControls' diagram (its
						// shapes and its texts), each compared on its own
						if (C.Screen == EScreen::Controls)
						{
							FBox D = PartBox(EMenuPart::Diagram);
							for (int t = 0; t < List.NumTexts; ++t)
								if (List.Texts[t].Part == EMenuPart::Diagram)
								{
									const FBox B = TextBox(List.Texts[t]);
									Add(D, {B.X0, B.Y0});
									Add(D, {B.X1, B.Y1});
								}
							FBox Strip;
							for (int t = 0; t < List.NumTris; ++t)
								if (List.Tris[t].Part == EMenuPart::Glyph)
									for (const FMenuVert& V : List.Tris[t].V) Add(Strip, V.P);
							for (int t = 0; t < List.NumTexts; ++t)
								if (List.Texts[t].Part == EMenuPart::Glyph)
								{
									const FBox B = TextBox(List.Texts[t]);
									Add(Strip, {B.X0, B.Y0});
									Add(Strip, {B.X1, B.Y1});
								}
							const FBox Plate = ItemBox(0, false);
							OffDiagram = OffDiagram && D.Any && Strip.Any && Plate.Any && !Overlap(D, Strip) && !Overlap(D, Plate);
						}
						// the scrim: the whole screen under the pause and what it
						// opens, and under the diagram; none under the title
						{
							const bool bWant = C.Screen == EScreen::Pause || C.From == EScreen::Pause || C.Screen == EScreen::Controls;
							const FBox S = PartBox(EMenuPart::Scrim);
							ScrimWhole = ScrimWhole && S.Any == bWant
							             && (!bWant || (Near(S.X0, 0.f) && Near(S.Y0, 0.f) && Near(S.X1, P.ScreenW) && Near(S.Y1, P.ScreenH)));
						}
						// the heading in bone with the blood slash under it,
						// the sub-line under that on the title
						if (C.Screen != EScreen::Controls)
						{
							const FMenuText* H = FindText(C.Screen == EScreen::Title ? EMenuText::Saud
							                              : C.Screen == EScreen::Pause ? EMenuText::Paused
							                              : C.Screen == EScreen::Confirm ? EMenuText::AskHead : EMenuText::SettingsHead);
							Heading = Heading && (C.Screen != EScreen::Confirm || (H && H->Value == (C.Ask == EAsk::NewGame ? 1 : 0)));
							const FBox S = PartBox(EMenuPart::Slash);
							Heading = Heading && H && SameRgb(H->Colour, SaudHud::Colour::Ice) && S.Any
							          && S.Y0 >= H->At.Y + H->Height - 0.5f && S.X0 >= H->At.X - 0.5f;
							for (int t = 0; t < List.NumTris; ++t)
								if (List.Tris[t].Part == EMenuPart::Slash)
									Heading = Heading && SameRgb(List.Tris[t].V[0].C, SaudHud::Colour::System);
							const FMenuText* Sub = FindText(EMenuText::Subtitle);
							Heading = Heading && (Sub != nullptr) == (C.Screen == EScreen::Title)
							          && (!Sub || (Sub->At.Y >= S.Y1 - 0.5f && SameRgb(Sub->Colour, SaudHud::Colour::Ice)));
							// and the wash is behind the heading: drawn first (after the scrim, when there is one)
							Heading = Heading && List.Tris[CountPart(EMenuPart::Scrim)].Part == EMenuPart::Wash;
							// the first plate the same distance under the slash on every screen
							const float Gap = (ItemBox(0, true).Y0 - S.Y1) / P.Scale;
							float& G = GapOf[static_cast<int>(C.Screen)];
							if (G < 0.f) G = Gap;
							else GapsAgree = GapsAgree && Near(G, Gap, 2.f);
						}
					}
					// the focus pulse moves on the clock, and slowly
					{
						FMenuModel M = Base;
						M.Focus = Focus;
						M.FocusFrom = static_cast<float>(Focus);
						FRgba F0, F1, F2;
						M.Clock = 0.f;  Build(P, M, List); PlateFill(Focus, F0);
						// somewhere in the first second the breath has moved (its top
						// is at a quarter period, 0.66 s at 0.38 Hz; fixed times, so a
						// frozen or infinite frequency cannot pass by accident)
						float Moved = 0.f;
						for (float T : {0.33f, 0.66f, 1.0f})
						{
							M.Clock = T; Build(P, M, List); PlateFill(Focus, F1);
							Moved = std::fmax(Moved, std::fabs(F1.R - F0.R) + std::fabs(F1.G - F0.G) + std::fabs(F1.B - F0.B));
						}
						M.Clock = 1.f / 60.f; Build(P, M, List); PlateFill(Focus, F2);
						Pulses = Pulses && Moved > 5e-3f && Moved == Moved && SameRgb(F0, F2, 0.02f);
						Builds += 5;
					}
				}
			}
		}
	}
	Check(NoNaN, "the menu's shapes are numbers");
	Check(AllIn, "every vertex the menu draws is inside the title-safe area, at every screen shape (the scrim excepted)");
	Check(TextIn, "every text is inside title-safe, to its estimated width");
	Check(Legible, "no text the player reads is under 1/36 of the screen");
	Check(Stroked, "every text has an ink stroke of 2 screen px at 720 lines, 7:1 against its fill");
	Check(Bright, "no text is dimmed under half");
	Check(Wound, "no triangle is inverted or degenerate");
	Check(Palette, "the HUD's palette only (and the focus between the panel and the System's cyan)");
	Check(Apart, "no item plate overlaps another");
	Check(Labelled, "every item's label sits on its own plate");
	Check(OneFocus, "exactly one focused item");
	Check(FocusReads, "the focused plate is 3:1 against the unfocused fill, its label ice; the rest the panel's navy");
	Check(Pulses, "the focus pulses on the real-time clock, slowly");
	Check(ValuesRead, "the settings rows read the model");
	Check(Continue, "a Title with no save has no CONTINUE, with one no FIGHT");
	Check(StripOnLine, "the prompt strip sits on the bottom safe line");
	Check(StripPad, "the prompt strip shows the pad in use's glyphs, or the keyboard's words; the flip names the other pad, the Title's Back says QUIT");
	Check(StripApart, "nothing in the prompt strip touches");
	Check(ScrimWhole, "the pause (and what it opens, and the diagram) stands over a scrim covering the screen; the title has none");
	Check(Heading, "the heading in ice over the wash, the System's bar under it, the sub-line under that");
	Check(OffDiagram, "on the controls page the BACK plate and the strip stay off SaudControls' diagram");
	Check(BigGlyphs, "the prompt strip's glyphs are couch-sized: 48 page px");
	Check(StripWords, "the prompt strip's words are 32 page px or more");
	Check(Hinted, "one hint line says what the focused item does (on a Confirm, what YES does), on the wash, touching nothing");
	Check(Tagged, "CONTINUE carries the stage the save has reached, on its own plate, clear of its label");
	Check(Metered, "SOUND and MUSIC are ten-segment meters on their own plates, lit to the level, clear of the label");
	Check(Nudged, "at rest the focused plate stands 14 page px out of the column");
	std::printf("  the slash to the first plate: title %.0f, pause %.0f, settings %.0f, confirm %.0f page px\n", GapOf[0],
	            GapOf[1], GapOf[2], GapOf[4]);
	Check(GapsAgree && GapOf[0] >= 0.f && GapOf[1] >= 0.f && GapOf[2] >= 0.f && GapOf[4] >= 0.f && Near(GapOf[0], GapOf[1], 2.f)
	      && Near(GapOf[0], GapOf[2], 2.f) && Near(GapOf[0], GapOf[4], 2.f),
	      "the first plate sits the same distance under the slash on every screen");
	std::printf("  %d builds: %d cases x %d pads x every focus x %d clocks at %d shapes\n", Builds,
	            static_cast<int>(sizeof(Cases) / sizeof(Cases[0])), 3, 4, static_cast<int>(sizeof(Shapes) / sizeof(Shapes[0])));
	std::printf("  worst case: %d triangles (%s), %d texts; capacity %d / %d\n", WorstTris, WorstName, WorstTexts,
	            MaxTris, MaxTexts);
	Check(Fits && WorstTris * 4 <= MaxTris * 3 && WorstTexts * 4 <= MaxTexts * 3,
	      "the whole page fits the list with room to spare");

	// the slash wipes open over 0.4 s from when the screen opens
	{
		const FPage P = FPage::For(1920, 1080);
		FMenuModel M = Model(EScreen::Title, true, EPad::Xbox);
		M.Since = 0.f; Build(P, M, List);
		const float W0 = PartBox(EMenuPart::Slash).Any ? PartBox(EMenuPart::Slash).X1 - PartBox(EMenuPart::Slash).X0 : 0.f;
		M.Since = 0.15f; Build(P, M, List);
		const FBox H = PartBox(EMenuPart::Slash);
		const float W1 = H.Any ? H.X1 - H.X0 : 0.f;
		M.Since = 0.4f; Build(P, M, List);
		const FBox F = PartBox(EMenuPart::Slash);
		const float W2 = F.Any ? F.X1 - F.X0 : 0.f;
		std::printf("  the slash at 0, 0.15 and 0.4 s: %.0f, %.0f, %.0f px\n", W0, W1, W2);
		Check(W0 < 1.f && W1 > 0.3f * W2 && W1 < 0.95f * W2 && Near(W2, P.Px(SlashW), 0.5f), "the System's bar wipes open over 0.4 s");
	}

	// the entrance: as a screen opens the wash wipes open, the plates slide
	// in from the left one after another, the hint and the strip fade in --
	// inside title-safe the whole way, never sliding back, and settled (the
	// very page drawn at rest) by EnterSeconds
	{
		bool Safe = true, InOrder = true, Wipes = true, Settles = true, Moves = true, Unseen = true;
		for (const auto& Sh : Shapes)
		{
			const FPage P = FPage::For(Sh[0], Sh[1]);
			for (const FCase& C : Cases)
			{
				if (C.Screen == EScreen::Controls) continue;
				FMenuModel M = Model(C.Screen, C.bSave, EPad::Xbox, C.From, C.Ask);
				M.StageReached = C.bSave ? 3 : 0;
				const int N = ItemCount(M);
				float PrevX[MaxItems], PrevWash = -1.f, RestA[MaxItems];
				for (int i = 0; i < MaxItems; ++i) PrevX[i] = -1e9f;
				// each plate's own fill alpha at rest, to measure how far in it is
				{
					FMenuModel R = M;
					R.Since = 30.f;
					Build(P, R, List);
					for (int i = 0; i < N; ++i) { FRgba F; RestA[i] = PlateFill(i, F) ? F.A : 1.f; }
				}
				for (int f = 0; f <= 72; ++f)
				{
					M.Since = static_cast<float>(f) / 60.f;
					Build(P, M, List);
					for (int t = 0; t < List.NumTris; ++t)
						for (const FMenuVert& V : List.Tris[t].V)
							if (List.Tris[t].Part != EMenuPart::Scrim && !InSafe(P, V.P.X, V.P.Y)) Safe = false;
					for (int t = 0; t < List.NumTexts; ++t)
					{
						const FBox B = TextBox(List.Texts[t]);
						Safe = Safe && InSafe(P, B.X0, B.Y0) && InSafe(P, B.X1, B.Y1);
					}
					const FBox W = PartBox(EMenuPart::Wash);
					const float WW = W.Any ? W.X1 - W.X0 : 0.f;
					Wipes = Wipes && WW >= PrevWash - 0.5f;
					PrevWash = WW;
					float A[MaxItems];
					for (int i = 0; i < N; ++i)
					{
						FRgba F;
						A[i] = PlateFill(i, F) ? F.A : 0.f;
						const FBox B = ItemBox(i, true);
						Moves = Moves && B.Any && B.X0 >= PrevX[i] - 0.01f;
						PrevX[i] = B.X0;
					}
					// a plate below never further in than the one above, as
					// DRAWN (their own fills differ: how far each has come is
					// its alpha over its alpha at rest)
					for (int i = 0; i + 1 < N; ++i)
						InOrder = InOrder && A[i] / RestA[i] + 1e-4f >= A[i + 1] / RestA[i + 1];
				}
				// settled by EnterSeconds: the same list as long after
				M.Since = EnterSeconds;
				Build(P, M, List);
				static FMenuList Rest;
				FMenuModel R = M;
				R.Since = 30.f;
				Build(P, R, Rest);
				bool Same = List.NumTris == Rest.NumTris && List.NumTexts == Rest.NumTexts;
				for (int t = 0; Same && t < List.NumTris; ++t)
					for (int v = 0; v < 3; ++v)
						Same = Same && Near(List.Tris[t].V[v].P.X, Rest.Tris[t].V[v].P.X, 1e-3f)
						       && Near(List.Tris[t].V[v].P.Y, Rest.Tris[t].V[v].P.Y, 1e-3f)
						       && Near(List.Tris[t].V[v].C.A, Rest.Tris[t].V[v].C.A, 1e-4f);
				for (int t = 0; Same && t < List.NumTexts; ++t)
					Same = Same && Near(List.Texts[t].At.X, Rest.Texts[t].At.X, 1e-3f)
					       && Near(List.Texts[t].Colour.A, Rest.Texts[t].Colour.A, 1e-4f);
				Settles = Settles && Same;
				// and at 0 s the plates are not yet in: the column comes in
				M.Since = 0.f;
				Build(P, M, List);
				FRgba F0;
				Settles = Settles && PlateFill(0, F0) && F0.A < 0.05f;
				// nor the prompt strip: none of a glyph, rim included, shows
				for (int t = 0; t < List.NumTris; ++t)
					if (List.Tris[t].Part == EMenuPart::Glyph)
						for (const FMenuVert& V : List.Tris[t].V) Unseen = Unseen && V.C.A < 0.01f;
				for (int t = 0; t < List.NumTexts; ++t)
					if (List.Texts[t].Part == EMenuPart::Glyph) Unseen = Unseen && List.Texts[t].Colour.A < 0.01f;
			}
		}
		Check(Unseen, "at 0 s the prompt strip is not drawn yet -- glyph rims and all");
		Check(Safe, "the entrance stays inside title-safe the whole way in");
		Check(Wipes && Moves, "the wash wipes open and the plates slide in, never back");
		Check(InOrder, "the plates arrive one after another, top first");
		Check(Settles, "the column comes in from nothing and is settled -- the page at rest -- by 0.6 s");
	}

	// the contrasts the look promises, from the numbers
	{
		using namespace SaudHud::Colour;
		float Lowest = 1e9f, LabelLowest = 1e9f, Nearest = 1e9f, Furthest = 0.f;
		for (int k = 0; k < 200; ++k)
		{
			const FRgba F = FocusFill(0.0137f * static_cast<float>(k));
			Lowest = std::fmin(Lowest, Contrast(F, Panel));
			LabelLowest = std::fmin(LabelLowest, Contrast(Ice, F));
			const float T = (F.G - Panel.G) / (System.G - Panel.G);
			Nearest = std::fmin(Nearest, T);
			Furthest = std::fmax(Furthest, T);
		}
		const float CIce = Contrast(Ice, Ink);
		std::printf("  contrast: focused plate at least %.2f on the panel, its ice label at least %.2f on it, ice %.2f on ink\n",
		            Lowest, LabelLowest, CIce);
		Check(Lowest >= 3.f && LabelLowest >= 3.f && CIce >= 7.f, "the focus stands 3:1 through its whole pulse, and its label on it");
		// ...a lit blue, not the System's cyan itself: 30-45 % of the way there
		std::printf("  the pulse goes %.0f-%.0f %% of the way from the panel to the System's cyan\n", 100.f * Nearest, 100.f * Furthest);
		Check(Nearest >= 0.30f - 1e-3f && Furthest <= 0.45f + 1e-3f && Furthest - Nearest > 0.05f,
		      "the focus breathes 30-45 % of the way from the panel to the System's cyan");
	}
}

int main()
{
	ModelRules();
	PageRules();
#if defined(SAUD_MENU_STUB_CONTROLS)
	std::printf("  (built against the stub of SaudControls: Glyph asked for xbox %d, ps %d, keyboard %d times)\n",
	            SaudControls::StubGlyphPad[0], SaudControls::StubGlyphPad[1], SaudControls::StubGlyphPad[2]);
#endif
	if (Fails) { std::printf("%d menu check(s) failed\n", Fails); return 1; }
	std::printf("all menu checks passed\n");
	return 0;
}
