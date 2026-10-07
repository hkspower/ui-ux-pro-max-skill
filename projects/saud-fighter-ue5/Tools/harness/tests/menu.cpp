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
#include "../../../Source/SaudFighter/Combat/SaudFire.h"

#include <cstdio>
#include <cmath>
#include <initializer_list>
#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

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
	const float W = TextWidth(X.Slot, X.Value, X.Height, X.Aux);
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
/** A save part way through the game (2026-10-07): 500 XP to spend, BOXING
    2 and KICKING 1 bought, VAULT and DASH LEAP found, the quest open. */
static FStatus MidStatus(int Spendable = 500, bool bWon = false)
{
	const int Tracks[Train::Tracks] = {2, 1, 0, 0, 0, 0};
	const bool Skills[SaudMenu::Skills] = {true, true, false, false, false};
	return MakeStatus(Spendable, Tracks, Skills, bWon);
}

/** The screen a case is under: the Pause for the status, the training,
    their Confirm and anything opened from the Pause; else the Title. */
static EScreen RootOf(EScreen S, EScreen From, EAsk Ask)
{
	if (S == EScreen::Status || S == EScreen::Training || (S == EScreen::Confirm && Ask == EAsk::Train)) return EScreen::Pause;
	if (From == EScreen::Status || From == EScreen::Training) return EScreen::Pause;
	return S == EScreen::Pause ? EScreen::Pause : From;
}

/** A model on a screen, opened the way the engine opens it: Title or Pause
    by Open, Settings and Controls through the item that opens them, a
    Confirm through QUIT or NEW GAME on the Title; the Status and the
    Training through the Pause (a Training From the Status through the
    Status's TRAINING), the Train question through the Training's first
    track. */
static FMenuModel Model(EScreen S, bool bSave, EPad Pad, EScreen From = EScreen::Title, EAsk Ask = EAsk::Quit)
{
	FMenuModel M;
	M.bHasSave = bSave;
	M.Pad = Pad;
	M.Status = MidStatus();
	const bool bTrainAsk = S == EScreen::Confirm && Ask == EAsk::Train;
	const bool bSub = S == EScreen::Settings || S == EScreen::Controls || S == EScreen::Confirm || S == EScreen::Status
	                  || S == EScreen::Training;
	Open(M, bSub ? RootOf(S, From, Ask) : S);
	if (S == EScreen::Settings) { M.Focus = IndexOf(M, EItem::Settings); Navigate(M, EAction::Confirm); }
	if (S == EScreen::Controls) { M.Focus = IndexOf(M, EItem::Controls); Navigate(M, EAction::Confirm); }
	if (S == EScreen::Confirm && !bTrainAsk)
	{
		M.Focus = IndexOf(M, Ask == EAsk::NewGame ? EItem::NewGame : EItem::Quit);
		Navigate(M, EAction::Confirm);
	}
	if (S == EScreen::Status || From == EScreen::Status)
	{
		M.Focus = IndexOf(M, EItem::Status);
		Navigate(M, EAction::Confirm);
	}
	if (S == EScreen::Training || bTrainAsk)
	{
		M.Focus = IndexOf(M, EItem::Training);
		Navigate(M, EAction::Confirm);
	}
	if (bTrainAsk)
	{
		M.Focus = IndexOf(M, EItem::TrainBox);
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
		Check(N == 6 && I[0] == EItem::Resume && I[1] == EItem::Status && I[2] == EItem::Training && I[3] == EItem::Controls
		      && I[4] == EItem::Settings && I[5] == EItem::QuitToTitle,
		      "Pause: RESUME, STATUS, TRAINING, CONTROLS, SETTINGS, QUIT TO TITLE");
		FMenuModel St = Model(EScreen::Status, true, EPad::Xbox);
		N = Items(St, I);
		Check(St.Screen == EScreen::Status && N == 2 && I[0] == EItem::Training && I[1] == EItem::Back,
		      "Status: the window, and TRAINING, BACK");
		FMenuModel Tr = Model(EScreen::Training, true, EPad::Xbox);
		N = Items(Tr, I);
		Check(Tr.Screen == EScreen::Training && N == 7 && I[0] == EItem::TrainBox && I[1] == EItem::TrainKick
		      && I[2] == EItem::TrainVit && I[3] == EItem::TrainSpd && I[4] == EItem::TrainStam && I[5] == EItem::TrainIron
		      && I[6] == EItem::Back, "Training: BOXING, KICKING, VITALITY, SPEED, STAMINA, IRON ARM, BACK");
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
		const EScreen Screens[7] = {EScreen::Title, EScreen::Pause, EScreen::Settings, EScreen::Controls, EScreen::Confirm,
		                            EScreen::Status, EScreen::Training};
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
		M.Status = MidStatus(4000);   // enough to buy, so the walk buys
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
			InRange = InRange && M.Status.Spendable >= 0 && M.Depth >= 0 && M.Depth <= FMenuModel::MaxDepth;
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
		M.Focus = IndexOf(M, EItem::QuitToTitle);
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::QuitToTitle, "QUIT TO TITLE quits to the title");
		M.Focus = IndexOf(M, EItem::Controls);
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
		Navigate(M, EAction::Confirm);              // STATUS, mid-glide
		Jumps = Jumps && M.Screen == EScreen::Status && Near(ShownFocus(M), 0.f);
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
	// 2026-10-07
	{EScreen::Status, true, EScreen::Pause, "status", EAsk::Quit},
	{EScreen::Training, true, EScreen::Pause, "training", EAsk::Quit},
	{EScreen::Training, true, EScreen::Status, "training from status", EAsk::Quit},
	{EScreen::Confirm, true, EScreen::Pause, "confirm train", EAsk::Train},
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
	float GapOf[7] = {-1.f, -1.f, -1.f, -1.f, -1.f, -1.f, -1.f};   // slash bottom to the first plate, page px, per screen
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
							const bool bWant = RootOf(C.Screen, C.From, C.Ask) == EScreen::Pause || C.Screen == EScreen::Controls;
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
							                              : C.Screen == EScreen::Confirm ? EMenuText::AskHead
							                              : C.Screen == EScreen::Status ? EMenuText::StatusHead
							                              : C.Screen == EScreen::Training ? EMenuText::TrainingHead : EMenuText::SettingsHead);
							Heading = Heading && (C.Screen != EScreen::Confirm || (H && H->Value == static_cast<int>(C.Ask)));
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
	std::printf("  the slash to the first plate: title %.0f, pause %.0f, settings %.0f, confirm %.0f, status %.0f, "
	            "training %.0f page px\n", GapOf[0], GapOf[1], GapOf[2], GapOf[4], GapOf[5], GapOf[6]);
	Check(GapsAgree && GapOf[0] >= 0.f && GapOf[1] >= 0.f && GapOf[2] >= 0.f && GapOf[4] >= 0.f && Near(GapOf[0], GapOf[1], 2.f)
	      && Near(GapOf[0], GapOf[2], 2.f) && Near(GapOf[0], GapOf[4], 2.f) && Near(GapOf[0], GapOf[5], 2.f)
	      && Near(GapOf[0], GapOf[6], 2.f),
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

// ============================================ STATUS AND TRAINING (2026-10-07)
// The System's status window and its store. The numbers first -- the ladder,
// the costs, the ids, the stats are the game's own, read from its data and
// its engine source -- then the model (buying spends, levels the track, is
// asked first, is refused when poor or maxed, never costs a level), then the
// two pages as Build draws them at the seven shapes.

static std::string Slurp(const char* Path)
{
	std::string S;
	if (FILE* F = std::fopen(Path, "rb"))
	{
		char Buf[4096];
		size_t N;
		while ((N = std::fread(Buf, 1, sizeof Buf, F)) > 0) S.append(Buf, N);
		std::fclose(F);
	}
	return S;
}
/** The file with every space, tab and line break taken out. */
static std::string Squeezed(const char* Path)
{
	std::string S = Slurp(Path), O;
	for (char C : S) if (C != ' ' && C != '\t' && C != '\n' && C != '\r') O += C;
	return O;
}
/** A CSV's rows (a quoted field may hold commas), the header first. */
static std::vector<std::vector<std::string>> CsvRows(const char* Path)
{
	std::vector<std::vector<std::string>> Rows;
	const std::string S = Slurp(Path);
	std::vector<std::string> Row;
	std::string Field;
	bool bQuoted = false;
	for (size_t i = 0; i < S.size(); ++i)
	{
		const char C = S[i];
		if (bQuoted)
		{
			if (C == '"' && i + 1 < S.size() && S[i + 1] == '"') { Field += '"'; ++i; }
			else if (C == '"') bQuoted = false;
			else Field += C;
		}
		else if (C == '"') bQuoted = true;
		else if (C == ',') { Row.push_back(Field); Field.clear(); }
		else if (C == '\n') { Row.push_back(Field); Field.clear(); Rows.push_back(Row); Row.clear(); }
		else if (C != '\r') Field += C;
	}
	if (!Field.empty() || !Row.empty()) { Row.push_back(Field); Rows.push_back(Row); }
	return Rows;
}
static int Column(const std::vector<std::string>& Header, const char* Name)
{
	for (size_t i = 0; i < Header.size(); ++i) if (Header[i] == Name) return static_cast<int>(i);
	return -1;
}
/** The number after "Key": in a JSON file (the first). */
static float JsonNumber(const std::string& S, const char* Key, bool& Found)
{
	const std::string K = std::string("\"") + Key + "\":";
	const size_t At = S.find(K);
	Found = At != std::string::npos;
	return Found ? std::strtof(S.c_str() + At + K.size(), nullptr) : 0.f;
}
/** The body of a C++ function in a file, from its name to its closing
    brace at the start of a line. */
static std::string Body(const char* Path, const char* Signature)
{
	const std::string S = Slurp(Path);
	const size_t At = S.find(Signature);
	if (At == std::string::npos) return std::string();
	const size_t End = S.find("\n}", At);
	return S.substr(At, End == std::string::npos ? std::string::npos : End - At + 2);
}
static std::string NoSpace(const std::string& S)
{
	std::string O;
	for (char C : S) if (C != ' ' && C != '\t' && C != '\n' && C != '\r') O += C;
	return O;
}

static void TrainingNumbers()
{
	std::printf("NUMBERS  (the ladder, the costs, the ids, the stats: the game's own)\n");
	// the ladder: DT_Levels.csv, every row
	{
		const auto Rows = CsvRows("Content/Data/DT_Levels.csv");
		const int CL = Rows.empty() ? -1 : Column(Rows[0], "Level");
		const int CX = Rows.empty() ? -1 : Column(Rows[0], "ExperienceRequired");
		const int CT = Rows.empty() ? -1 : Column(Rows[0], "Title");
		bool Xp = CL >= 0 && CX >= 0 && CT >= 0 && Rows.size() == static_cast<size_t>(Ladder::MaxLevel) + 1;
		bool Titles = Xp, Levels = Xp;
		for (size_t r = 1; Xp && r < Rows.size(); ++r)
		{
			const int L = std::atoi(Rows[r][static_cast<size_t>(CL)].c_str());
			const int Need = std::atoi(Rows[r][static_cast<size_t>(CX)].c_str());
			Xp = Xp && L == static_cast<int>(r) && Ladder::Need(L) == Need;
			Titles = Titles && Rows[r][static_cast<size_t>(CT)] == Ladder::RankName(Ladder::RankOf(L));
			Levels = Levels && Ladder::LevelOf(Need) == L && (L == 1 || Ladder::LevelOf(Need - 1) == L - 1);
		}
		Levels = Levels && Ladder::LevelOf(1000000) == Ladder::MaxLevel && Ladder::LevelOf(0) == 1;
		bool F = false;
		const float Max = JsonNumber(Slurp("Content/Data/Player.json"), "LevelMax", F);
		Check(Xp && F && static_cast<int>(Max) == Ladder::MaxLevel, "the ladder is DT_Levels.csv's: the XP every level needs, to 20");
		Check(Titles, "every level's title is DT_Levels.csv's: ROOKIE .. CHAMPION");
		Check(Levels, "the level is the highest the earned XP reaches, and never past 20");
	}
	// the tracks: DT_Upgrades.csv, every row
	{
		const auto Rows = CsvRows("Content/Data/DT_Upgrades.csv");
		const int CTr = Rows.empty() ? -1 : Column(Rows[0], "Track");
		const int CN = Rows.empty() ? -1 : Column(Rows[0], "DisplayName");
		const int CL = Rows.empty() ? -1 : Column(Rows[0], "Level");
		const int CC = Rows.empty() ? -1 : Column(Rows[0], "Cost");
		const int CCu = Rows.empty() ? -1 : Column(Rows[0], "CumulativeCost");
		bool Ids = CTr >= 0 && CN >= 0 && CL >= 0 && CC >= 0 && CCu >= 0
		           && Rows.size() == static_cast<size_t>(Train::Tracks * Train::MaxLevel) + 1;
		bool Costs = Ids, Names = Ids;
		int MaxSeen = 0;
		for (size_t r = 1; Ids && r < Rows.size(); ++r)
		{
			const std::string& Id = Rows[r][static_cast<size_t>(CTr)];
			const int Want = static_cast<int>((r - 1) / Train::MaxLevel);   // the table's own order
			const int L = std::atoi(Rows[r][static_cast<size_t>(CL)].c_str());
			Ids = Ids && Train::TrackOf(Id.c_str()) == Want && Id == Train::Id(Want);
			Names = Names && Rows[r][static_cast<size_t>(CN)] == Train::Name(Want);
			Costs = Costs && Train::Cost(L - 1) == std::atoi(Rows[r][static_cast<size_t>(CC)].c_str())
			        && Train::Spent(L) == std::atoi(Rows[r][static_cast<size_t>(CCu)].c_str());
			MaxSeen = std::max(MaxSeen, L);
		}
		bool F = false;
		const float Max = JsonNumber(Slurp("Content/Data/Player.json"), "UpgradeMaxLevel", F);
		Check(Ids, "every DT_Upgrades Track id is a track the shop buys: Box, Kick, Vit, Spd, Stam, Iron");
		Check(Names, "the tracks' names are DT_Upgrades.csv's");
		Check(Costs && MaxSeen == Train::MaxLevel && F && static_cast<int>(Max) == Train::MaxLevel,
		      "the costs are DT_Upgrades.csv's, level by level and summed, five levels a track");
		Check(Train::TrackOf("Boxing") == 0 && Train::TrackOf("Stamina") == 4 && Train::TrackOf("Iron") == 5
		      && Train::TrackOf("box") < 0 && Train::TrackOf("") < 0 && Train::TrackOf("Rage") < 0,
		      "the old long ids still buy; anything else is no track");
	}
	// the shop's own call: TryPurchaseUpgrade and GetUpgradeCost go through
	// that table (read from the engine source: it cannot be compiled here)
	{
		const std::string Buy = NoSpace(Body("Source/SaudFighter/Game/SaudGameInstance.cpp", "bool USaudGameInstance::TryPurchaseUpgrade"));
		const std::string Cost = NoSpace(Body("Source/SaudFighter/Game/SaudGameInstance.cpp", "int32 USaudGameInstance::GetUpgradeCost"));
		const std::string Spent = NoSpace(Body("Source/SaudFighter/Game/SaudGameInstance.cpp", "int32 USaudGameInstance::GetSpentExperience"));
		const std::string H = Squeezed("Source/SaudFighter/Game/SaudGameInstance.h");
		Check(!Buy.empty() && Buy.find("SaudMenu::Train::TrackOf(TCHAR_TO_ANSI(*TrackId.ToString()))") != std::string::npos
		      && Buy.find("TEXT(\"Boxing\")") == std::string::npos && Buy.find("&Progress.BoxingLevel,&Progress.KickingLevel,"
		      "&Progress.VitalityLevel,&Progress.SpeedLevel,&Progress.StaminaLevel,&Progress.IronArmLevel") != std::string::npos
		      && Buy.find("GetUpgradeCost(*Level)") != std::string::npos && Buy.find("SaudMenu::Train::MaxLevel") != std::string::npos,
		      "TryPurchaseUpgrade takes the table's ids through SaudMenu::Train, the tracks in the table's order");
		Check(Cost.find("returnSaudMenu::Train::Cost(CurrentLevel);") != std::string::npos
		      && Spent.find("SaudMenu::Train::Spent(Progress.BoxingLevel)") != std::string::npos
		      && Spent.find("SaudMenu::Train::Spent(Progress.IronArmLevel)") != std::string::npos
		      && H.find("GetEarnedExperience()const{returnProgress.Experience+GetSpentExperience();}") != std::string::npos,
		      "GetUpgradeCost is the table's; the earned XP is the spendable plus what the six tracks cost");
		// the quest closes on the arena: AlHalqa, AL-WAHSH's boss stage
		const std::string Won = NoSpace(Body("Source/SaudFighter/Game/SaudGameInstance.cpp", "bool USaudGameInstance::HasWonTheTitle"));
		const std::string Stages = Squeezed("Content/Data/DT_Stages.json");
		const size_t At = Stages.find("\"Name\":\"AlHalqa\"");
		const size_t Next = At == std::string::npos ? At : Stages.find("\"Name\":", At + 10);
		const std::string Row = At == std::string::npos ? std::string() : Stages.substr(At, Next == std::string::npos ? std::string::npos : Next - At);
		Check(Won.find("ClearedStages.Contains(FName(TEXT(\"AlHalqa\")))") != std::string::npos
		      && Row.find("\"bIsBossStage\":true") != std::string::npos && Row.find("\"Index\":8") != std::string::npos,
		      "the title is won when AL-HALQA, the arena's boss stage, is cleared");
	}
	// HP, MP, STAMINA: what the game gives (ApplyUpgrades; SaudFire's MP)
	{
		const std::string J = Slurp("Content/Data/Player.json");
		bool F1, F2, F3, F4, F5;
		const int H = static_cast<int>(JsonNumber(J, "BaseHealth", F1)), V = static_cast<int>(JsonNumber(J, "Vitality", F2));
		const int St = static_cast<int>(JsonNumber(J, "BaseStamina", F3)), Sp = static_cast<int>(JsonNumber(J, "Stamina", F4));
		const int Mp = static_cast<int>(JsonNumber(J, "BaseMana", F5));
		const std::string Apply = NoSpace(Body("Source/SaudFighter/Combat/SaudCharacter.cpp", "void ASaudCharacter::ApplyUpgrades"));
		Check(F1 && F2 && F3 && F4 && F5 && H == Stats::BaseHealth && V == Stats::HealthPerVitality && St == Stats::BaseStamina
		      && Sp == Stats::StaminaPerLevel && Mp == Stats::BaseMana && Near(static_cast<float>(Stats::BaseMana), SaudFire::MaxMana)
		      && Apply.find("MaxHealth=100.f+P.VitalityLevel*18.f+SaudMenu::Stats::LevelHealth(Level);") != std::string::npos
		      && Apply.find("MaxStamina=100.f+P.StaminaLevel*12.f;") != std::string::npos
		      && Apply.find("MaxMana=SaudFire::MaxMana+SaudMenu::Stats::LevelMana(Level);") != std::string::npos
		      && Apply.find("constint32Level=GI->GetLevel();") != std::string::npos,
		      "HP, MP and STAMINA are the game's: Player.json's and the level's, as ApplyUpgrades and SaudFire give them");
		// the level's own HP and MP: DT_Levels' BonusHealth / BonusMana at every rung
		const auto Rows = CsvRows("Content/Data/DT_Levels.csv");
		const int CL = Rows.empty() ? -1 : Column(Rows[0], "Level");
		const int CH = Rows.empty() ? -1 : Column(Rows[0], "BonusHealth");
		const int CM = Rows.empty() ? -1 : Column(Rows[0], "BonusMana");
		bool Rung = CL >= 0 && CH >= 0 && CM >= 0 && Rows.size() == static_cast<size_t>(Ladder::MaxLevel) + 1;
		for (size_t R = 1; Rung && R < Rows.size(); ++R)
		{
			const int L = std::atoi(Rows[R][static_cast<size_t>(CL)].c_str());
			Rung = std::atoi(Rows[R][static_cast<size_t>(CH)].c_str()) == Stats::LevelHealth(L)
			    && std::atoi(Rows[R][static_cast<size_t>(CM)].c_str()) == Stats::LevelMana(L);
		}
		const std::string Ch = Squeezed("Source/SaudFighter/Combat/SaudCharacter.cpp");
		const std::string ChH = Squeezed("Source/SaudFighter/Combat/SaudCharacter.h");
		Check(Rung && Stats::LevelHealth(1) == 0 && Stats::LevelMana(1) == 0,
		      "every level's HP and MP are DT_Levels.csv's: +6 HP, +4 MP a level past the first");
		Check(Ch.find("Mana=FMath::Min(MaxMana,Mana+SaudFire::ManaRegenPerSecond*DeltaSeconds);") != std::string::npos
		      && Ch.find("Mana=FMath::Min(MaxMana,Mana+SaudFire::ManaPerLandedHit);") != std::string::npos
		      && Ch.find("OnExperienceChanged.AddUniqueDynamic(this,&ASaudCharacter::HandleExperienceChanged);") != std::string::npos
		      && ChH.find("returnMaxMana>0.f?Mana/MaxMana:0.f;") != std::string::npos,
		      "his MP fills to the level's MP, the bar reads it, and a level earned mid-stage raises it at once");
	}
	// the five skills: DT_Talents' names, in EAbility's order
	{
		const auto Rows = CsvRows("Content/Data/DT_Talents.csv");
		const int CN = Rows.empty() ? -1 : Column(Rows[0], "DisplayName");
		bool Ok = CN >= 0 && Rows.size() == static_cast<size_t>(SaudMenu::Skills) + 1;
		for (int K = 0; Ok && K < SaudMenu::Skills; ++K) Ok = Rows[static_cast<size_t>(K) + 1][static_cast<size_t>(CN)] == SkillName(K);
		const std::string T = Squeezed("Source/SaudFighter/Combat/SaudTypes.h");
		const size_t E = T.find("enumclassEAbility:uint8{");
		const size_t A[5] = {T.find("Vault,", E), T.find("DashLeap,", E), T.find("PowerKick,", E), T.find("Haymaker,", E),
		                     T.find("HawkFist,", E)};
		Ok = Ok && E != std::string::npos && T.find("None", E) < A[0];
		for (int K = 0; Ok && K < 4; ++K) Ok = A[K] != std::string::npos && A[K] < A[K + 1];
		Check(Ok && A[4] != std::string::npos && std::strcmp(SkillName(HawkFistSkill), "HAWK FIST") == 0,
		      "the five skills are DT_Talents.csv's, in EAbility's order, HAWK FIST the last");
	}
	// the status from a save
	{
		const int Zero[Train::Tracks] = {};
		const bool None[SaudMenu::Skills] = {};
		const FStatus S0 = MakeStatus(0, Zero, None, false);
		Check(S0.Level == 1 && S0.Rank == 0 && S0.Earned == 0 && S0.LevelFloor == 0 && S0.LevelNext == 21 && S0.MaxHealth == 100
		      && S0.MaxMana == 40 && S0.MaxStamina == 100 && S0.bQuestOpen, "a new save: LEVEL 1, ROOKIE, 21 XP to LEVEL 2, HP 100, MP 40, STAMINA 100");
		const FStatus S1 = MidStatus(300);
		Check(S1.Earned == 300 + 370 + 120 && S1.Spendable == 300, "the earned XP is the spendable plus what training has cost");
		const int Tv[Train::Tracks] = {0, 0, 3, 0, 2, 0};
		const FStatus S2 = MakeStatus(0, Tv, None, true);
		Check(S2.MaxHealth == 154 + 6 * (S2.Level - 1) && S2.MaxStamina == 124 && S2.MaxMana == 40 + 4 * (S2.Level - 1) && S2.Level > 1,
		      "VITALITY gives 18 HP a level, STAMINA 12, and his level 6 HP and 4 MP a rung");
		Check(!S2.bQuestOpen, "the quest is removed once the title is won");
		const int Tm[Train::Tracks] = {5, 5, 5, 5, 5, 5};
		const FStatus S3 = MakeStatus(500, Tm, None, false);
		Check(S3.Level == Ladder::MaxLevel && S3.LevelNext == 0 && S3.Rank == 5, "every track maxed is past LEVEL 20: CHAMPION, at the top");
	}
}

/** The first text of a slot (and, for repeats, the n-th). */
static const FMenuText* NthText(EMenuText Slot, int N)
{
	for (int t = 0; t < List.NumTexts; ++t)
		if (List.Texts[t].Slot == Slot && N-- == 0) return &List.Texts[t];
	return nullptr;
}
static int CountText(EMenuText Slot)
{
	int N = 0;
	for (int t = 0; t < List.NumTexts; ++t) N += List.Texts[t].Slot == Slot;
	return N;
}
static bool Inside(const FBox& In, const FBox& B, float E = 0.5f)
{
	return B.Any && In.Any && B.X0 >= In.X0 - E && B.Y0 >= In.Y0 - E && B.X1 <= In.X1 + E && B.Y1 <= In.Y1 + E;
}

/** A status model with a given save, on the Status page, at rest. */
static FMenuModel StatusModel(EPad Pad, const FStatus& S)
{
	FMenuModel M = Model(EScreen::Status, true, Pad);
	M.Status = S;
	M.Since = 1.f;
	return M;
}

static void StatusPage()
{
	std::printf("STATUS  (the System's window, at the seven shapes)\n");
	const int Early[Train::Tracks] = {0, 0, 0, 0, 0, 0}, Mid[Train::Tracks] = {2, 1, 1, 0, 0, 0},
	          Late[Train::Tracks] = {5, 4, 5, 3, 4, 5}, Top[Train::Tracks] = {5, 5, 5, 5, 5, 5};
	const bool SkE[SaudMenu::Skills] = {}, SkM[SaudMenu::Skills] = {true, true, false, false, false},
	           SkL[SaudMenu::Skills] = {true, true, true, true, true}, SkOdd[SaudMenu::Skills] = {false, true, false, true, true};
	const FStatus Saves[6] = {MakeStatus(35, Early, SkE, false), MakeStatus(300, Mid, SkM, false),
	                          MakeStatus(640, Late, SkL, false), MakeStatus(640, Late, SkL, true),
	                          MakeStatus(99999, Top, SkL, true), MakeStatus(0, Mid, SkOdd, false)};
	bool Present = true, Values = true, InWindow = true, Apart = true, Clear = true, Skills = true, Hawk = true;
	bool Quest = true, Bar = true, Pipped = true, Framed = true, Glows = true;
	int Builds = 0;
	for (const auto& Sh : Shapes)
	{
		const FPage P = FPage::For(Sh[0], Sh[1]);
		for (const FStatus& S : Saves)
		{
			for (EPad Pad : Pads)
			{
				for (int Focus = 0; Focus < 2; ++Focus)
				{
					FMenuModel M = StatusModel(Pad, S);
					M.Focus = Focus;
					M.FocusFrom = static_cast<float>(Focus);
					Build(P, M, List);
					++Builds;
					const FMenuLayout L = Lay(P, M);
					FBox Win;
					Add(Win, {L.Window.X, L.Window.Y});
					Add(Win, {L.Window.X + L.Window.W, L.Window.Y + L.Window.H});
					// every line of the window is there, saying the save
					const FMenuText* Name = FindText(EMenuText::WinName);
					const FMenuText* Lv = FindText(EMenuText::LevelLine);
					const FMenuText* Rk = FindText(EMenuText::RankTitle);
					const FMenuText* Xl = FindText(EMenuText::XpLine);
					const FMenuText* Xn = FindText(EMenuText::XpToNext);
					const FMenuText* Hp = FindText(EMenuText::StatHp);
					const FMenuText* Mp = FindText(EMenuText::StatMp);
					const FMenuText* Stm = FindText(EMenuText::StatStamina);
					const FMenuText* Qn = FindText(EMenuText::QuestName);
					Present = Present && Name && Lv && Rk && Xl && Xn && Hp && Mp && Stm && Qn && FindText(EMenuText::XpLabel)
					          && CountText(EMenuText::Section) == 3 && CountText(EMenuText::SkillName) == SaudMenu::Skills
					          && CountText(EMenuText::TrackName) == Train::Tracks;
					if (!Present) continue;
					const bool bTop = S.LevelNext <= 0;
					Values = Values && Lv->Value == S.Level && Rk->Value == S.Rank && Xl->Value == S.Earned
					         && Xl->Aux == (bTop ? 0 : S.LevelNext) && Xn->Value == (bTop ? 0 : S.LevelNext - S.Earned)
					         && Xn->Aux == (bTop ? 0 : S.Level + 1) && Hp->Value == S.MaxHealth && Mp->Value == S.MaxMana
					         && Stm->Value == S.MaxStamina;
					for (int k = 0; k < 3; ++k) Values = Values && NthText(EMenuText::Section, k)->Value == k;
					// the quest: FIND THE WAY UP, IN PROGRESS, until the title is won
					Quest = Quest && Qn->Value == (S.bQuestOpen ? 0 : 1)
					        && (FindText(EMenuText::QuestState) != nullptr) == S.bQuestOpen;
					// the skills: the name when found, "?" when not; the slot
					// lit and marked when found; HAWK FIST's violet either way
					for (int K = 0; K < SaudMenu::Skills; ++K)
					{
						const FMenuText* X = NthText(EMenuText::SkillName, K);
						Skills = Skills && X && X->Value == K && X->Aux == (S.Skill[K] ? 1 : 0)
						         && (S.Skill[K] ? SameRgb(X->Colour, SaudHud::Colour::Ice) && X->Colour.A > 0.99f : X->Colour.A < 0.6f);
						int Marks = 0;
						for (int t = 0; t < List.NumTris; ++t)
							Marks += List.Tris[t].Part == EMenuPart::Mark && List.Tris[t].Tag == 2 + K;
						Skills = Skills && Marks == (S.Skill[K] ? 2 : 0);
						// the slot's keyline: the first Keyline triangles of the window, two a slot
						int Seen = 0;
						for (int t = 0; t < List.NumTris; ++t)
						{
							const FMenuTri& T = List.Tris[t];
							if (T.Part != EMenuPart::Keyline || T.Item != -1) continue;
							if (Seen++ != 2 * K) continue;
							const FRgba Want = K == HawkFistSkill ? SaudHud::Colour::Shadow : SaudHud::Colour::System;
							(K == HawkFistSkill ? Hawk : Skills) = (K == HawkFistSkill ? Hawk : Skills) && SameRgb(T.V[0].C, Want)
							                                       && (S.Skill[K] ? T.V[0].C.A > 0.99f : T.V[0].C.A < 0.6f);
							FBox Sl;
							for (const FMenuVert& V : T.V) Add(Sl, V.P);
							Skills = Skills && Overlap(Sl, TextBox(*X));
						}
						Skills = Skills && Seen == 2 * SaudMenu::Skills;
					}
					// every track's five pips, lit to its level
					int Lit[Train::Tracks] = {}, Segs = 0;
					for (int t = 0; t < List.NumTris; ++t)
					{
						const FMenuTri& T = List.Tris[t];
						if (T.Part != EMenuPart::Meter || T.Item != -1) continue;
						++Segs;
						FBox B;
						for (const FMenuVert& V : T.V) Add(B, V.P);
						for (int Tk = 0; Tk < Train::Tracks; ++Tk)
						{
							const FRect& R = L.Pips[Tk];
							if (B.Y0 >= R.Y - 0.5f && B.Y1 <= R.Y + R.H + 0.5f) Lit[Tk] += T.Tag;
						}
					}
					Pipped = Pipped && Segs == 2 * 5 * Train::Tracks;
					for (int Tk = 0; Tk < Train::Tracks; ++Tk) Pipped = Pipped && Lit[Tk] == 2 * S.Track[Tk];
					// the XP bar: through this level as far as the earned XP is
					{
						FBox Fill, Trough;
						for (int t = 0; t < List.NumTris; ++t)
							if (List.Tris[t].Part == EMenuPart::Bar)
								for (const FMenuVert& V : List.Tris[t].V) Add(List.Tris[t].Tag == 2 ? Fill : (List.Tris[t].Tag == 1 ? Trough : Win), V.P);
						const float Want = bTop ? 1.f
						    : static_cast<float>(S.Earned - S.LevelFloor) / static_cast<float>(S.LevelNext - S.LevelFloor);
						const float Got = Fill.Any ? (Fill.X1 - Fill.X0) / (Trough.X1 - Trough.X0) : 0.f;
						Bar = Bar && Trough.Any && Near(Got, Want, 1.f / (Trough.X1 - Trough.X0) + 1e-3f)
						      && (!Fill.Any || (Near(Fill.X0, Trough.X0, 0.5f) && Fill.Y0 >= Trough.Y0 - 0.5f && Fill.Y1 <= Trough.Y1 + 0.5f));
						Bar = Bar && Contrast(SaudHud::Colour::System, SaudHud::Colour::Trough) >= 3.f;
					}
					// every text of the window inside it, none touching another
					for (int t = 0; t < List.NumTexts; ++t)
					{
						const FMenuText& X = List.Texts[t];
						if (X.Part != EMenuPart::Window) continue;
						const FBox B = TextBox(X);
						InWindow = InWindow && Inside(Win, B);
						for (int u = t + 1; u < List.NumTexts; ++u)
							if (List.Texts[u].Part == EMenuPart::Window && Overlap(B, TextBox(List.Texts[u]))) Apart = false;
					}
					// the window clear of the column: its plates, the heading,
					// the bar, the hint and the prompt strip -- its glow included
					{
						FBox Whole;
						for (int t = 0; t < List.NumTris; ++t)
						{
							const EMenuPart Pt = List.Tris[t].Part;
							if (Pt == EMenuPart::Glow || Pt == EMenuPart::Window || Pt == EMenuPart::Edge || Pt == EMenuPart::Bracket)
								for (const FMenuVert& V : List.Tris[t].V) Add(Whole, V.P);
						}
						for (int i = 0; i < 2; ++i) Clear = Clear && !Overlap(Whole, ItemBox(i, false));
						Clear = Clear && !Overlap(Whole, PartBox(EMenuPart::Slash)) && !Overlap(Whole, PartBox(EMenuPart::Glyph));
						for (int t = 0; t < List.NumTexts; ++t)
							if (List.Texts[t].Part != EMenuPart::Window) Clear = Clear && !Overlap(Whole, TextBox(List.Texts[t]));
						Clear = Clear && Inside(Whole, Win, 0.5f) && Whole.X0 < Win.X0 && Whole.X1 > Win.X1;
					}
					// the window's look: a solid cyan edge, a glow fading to
					// nothing, the navy panel, ice corner marks outside it
					{
						bool Edge = false, GlowIn = false, GlowOut = true;
						int Brackets = 0;
						for (int t = 0; t < List.NumTris; ++t)
						{
							const FMenuTri& T = List.Tris[t];
							if (T.Part == EMenuPart::Edge) Edge = Edge || (SameRgb(T.V[0].C, SaudHud::Colour::System) && T.V[0].C.A > 0.99f);
							if (T.Part == EMenuPart::Glow)
							{
								GlowIn = GlowIn || T.V[2].C.A > 0.3f;
								// each glow triangle reaches the outer ring, where it is nothing
								GlowOut = GlowOut && std::fmin(T.V[0].C.A, std::fmin(T.V[1].C.A, T.V[2].C.A)) < 1e-4f;
							}
							if (T.Part == EMenuPart::Window) Glows = Glows && (SameRgb(T.V[0].C, SaudHud::Colour::Panel) || SameRgb(T.V[0].C, SaudHud::Colour::System));
							if (T.Part == EMenuPart::Bracket)
							{
								++Brackets;
								for (const FMenuVert& V : T.V) Framed = Framed && !(V.P.X > Win.X0 + 0.5f && V.P.X < Win.X1 - 0.5f && V.P.Y > Win.Y0 + 0.5f && V.P.Y < Win.Y1 - 0.5f)
								                                                && SameRgb(T.V[0].C, SaudHud::Colour::Ice);
							}
						}
						Glows = Glows && Edge && GlowIn && GlowOut;
						Framed = Framed && Brackets == 8;
					}
				}
			}
		}
	}
	std::printf("  %d builds: 6 saves x 3 pads x 2 focuses at 7 shapes\n", Builds);
	Check(Present, "the status window shows SAUD, the level, the rank, XP, HP, MP, STAMINA, the skills, the tracks, the quest");
	Check(Values, "...each read off the save: the level and rank from the earned XP, the XP to the next, the game's HP, MP, STAMINA");
	Check(Skills, "a skill found shows its name in a lit, marked slot; one not found a dim '?' in a dim slot");
	Check(Hawk, "HAWK FIST's slot is violet, found or not");
	Check(Pipped, "every track shows its five levels, lit to the level bought");
	Check(Bar, "the XP bar is as full as the earned XP is through the level (full at the top), 3:1 on its trough");
	Check(Quest, "the quest is FIND THE WAY UP, IN PROGRESS, until the title is won, then removed");
	Check(InWindow && Apart, "every line of the window is inside it, none touching another");
	Check(Clear, "the window stands clear of the column, the heading, the hint and the prompt strip, its glow included");
	Check(Glows, "the window is the System's: a solid cyan edge, a glow fading to nothing, the navy panel");
	Check(Framed, "...and ice corner marks outside its two uncut corners");
}

static void TrainingPage()
{
	std::printf("TRAINING  (the store, at the seven shapes)\n");
	const int Tracks[Train::Tracks] = {2, 1, 0, 5, 4, 0};
	const bool Sk[SaudMenu::Skills] = {true, false, false, false, false};
	bool Plates = true, Costs = true, Poor = true, Spend = true, Hints = true, Clear = true;
	int Builds = 0;
	for (const auto& Sh : Shapes)
	{
		const FPage P = FPage::For(Sh[0], Sh[1]);
		for (int Xp : {0, 300, 600, 9999})
		{
			for (EPad Pad : Pads)
			{
				for (int Focus = 0; Focus < 7; ++Focus)
				{
					FMenuModel M = Model(EScreen::Training, true, Pad);
					M.Status = MakeStatus(Xp, Tracks, Sk, false);
					M.Focus = Focus;
					M.FocusFrom = static_cast<float>(Focus);
					Build(P, M, List);
					++Builds;
					const FMenuText* Sx = FindText(EMenuText::SpendXp);
					Spend = Spend && Sx && Sx->Value == Xp && Sx->Colour.A > 0.99f && SameRgb(Sx->Colour, SaudHud::Colour::Ice)
					        && Sx->At.Y >= PartBox(EMenuPart::Slash).Y1 && TextBox(*Sx).Y1 <= ItemBox(0, false).Y0;
					const FMenuText* Hn = FindText(EMenuText::Hint);
					Hints = Hints && Hn && Hn->Value == (Focus < 6 ? static_cast<int>(EHint::TrainBox) + Focus : static_cast<int>(EHint::BackPause));
					for (int T = 0; T < Train::Tracks; ++T)
					{
						const FBox Pl = ItemBox(T, true);
						const FMenuText* Lb = ItemText(T);
						const FMenuText* Ct = nullptr;
						for (int t = 0; t < List.NumTexts; ++t)
							if (List.Texts[t].Item == T && List.Texts[t].Slot == EMenuText::CostTag) Ct = &List.Texts[t];
						FBox Pips;
						int Segs = 0, Lit = 0, Rules = 0;
						for (int t = 0; t < List.NumTris; ++t)
						{
							const FMenuTri& Tr = List.Tris[t];
							if (Tr.Item != T) continue;
							if (Tr.Part == EMenuPart::Meter) { ++Segs; Lit += Tr.Tag; for (const FMenuVert& V : Tr.V) Add(Pips, V.P); }
							if (Tr.Part == EMenuPart::Mark) { ++Rules; Poor = Poor && SameRgb(Tr.V[0].C, SaudHud::Colour::Danger); }
						}
						Plates = Plates && Lb && Lb->Slot == EMenuText::TrackName && Lb->Value == T && Segs == 10
						         && Lit == 2 * Tracks[T] && Inside(Pl, Pips) && TextBox(*Lb).X1 < Pips.X0;
						const bool bTop = Tracks[T] >= Train::MaxLevel;
						Costs = Costs && Ct && Ct->Value == (bTop ? -1 : Train::Cost(Tracks[T])) && Inside(Pl, TextBox(*Ct))
						        && Pips.X1 < TextBox(*Ct).X0;
						Poor = Poor && Rules == (!bTop && Xp < Train::Cost(Tracks[T]) ? 2 : 0);
					}
					// the pips of every plate line up
					float X0 = -1.f;
					for (int T = 0; T < Train::Tracks; ++T)
					{
						FBox Pi;
						for (int t = 0; t < List.NumTris; ++t)
							if (List.Tris[t].Item == T && List.Tris[t].Part == EMenuPart::Meter)
								for (const FMenuVert& V : List.Tris[t].V) Add(Pi, V.P);
						const float X = Pi.X0 - ItemBox(T, true).X0;
						if (X0 < 0.f) X0 = X;
						Clear = Clear && Near(X, X0, 0.5f);
					}
				}
			}
		}
	}
	std::printf("  %d builds: 4 purses x 3 pads x 7 focuses at 7 shapes\n", Builds);
	Check(Plates, "every track's plate: its name, then its five levels lit to the level bought");
	Check(Costs, "...then what the next level costs (MAX at the top), right on the plate, clear of the pips");
	Check(Clear, "the pips of every plate line up");
	Check(Poor, "a crimson rule under every cost the XP will not cover, and only those");
	Check(Spend, "the XP to spend under the heading's bar, in ice, above the plates");
	Check(Hints, "the hint says what each track gives (BACK: back to the pause)");
}

static void Buying()
{
	std::printf("BUYING  (the model)\n");
	// asked first: Confirm on a track it can buy opens the question, NO first
	{
		FMenuModel M = Model(EScreen::Training, true, EPad::Xbox);
		M.Status = MidStatus(600);   // BOXING at 2: 380 for the third
		const int Box = IndexOf(M, EItem::TrainBox);
		M.Focus = Box;
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::Tap && M.Screen == EScreen::Confirm && M.Ask == EAsk::Train
		      && M.TrainTrack == 0 && M.Focus == 0 && M.Status.Spendable == 600, "a track it can buy is asked first, on NO; nothing spent yet");
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::Back && M.Screen == EScreen::Training && M.Focus == Box
		      && M.Status.Spendable == 600 && M.Status.Track[0] == 2, "...NO goes back to the track, nothing spent");
		Navigate(M, EAction::Confirm);
		Check(Navigate(M, EAction::Back) == EMenuEffect::Back && M.Screen == EScreen::Training && M.Status.Spendable == 600,
		      "...Back is NO");
		Navigate(M, EAction::Confirm);
		Navigate(M, EAction::NavDown);
		const int Level = M.Status.Level, Earned = M.Status.Earned;
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::Train && M.Screen == EScreen::Training && M.Focus == Box
		      && M.TrainTrack == 0, "YES buys it: Train, back on the track");
		Check(M.Status.Spendable == 600 - 380 && M.Status.Track[0] == 3, "...the cost spent, the track a level up");
		Check(M.Status.Level == Level && M.Status.Earned == Earned, "...and his level does not move: training never costs one");
	}
	// refused: too poor, or at the top
	{
		FMenuModel M = Model(EScreen::Training, true, EPad::Xbox);
		M.Status = MidStatus(379);   // BOXING's third is 380
		M.Focus = IndexOf(M, EItem::TrainBox);
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::Denied && M.Screen == EScreen::Training && M.Status.Spendable == 379
		      && M.Status.Track[0] == 2, "a cost the XP will not cover is denied, nothing spent");
		Check(HintOf(M, EItem::TrainBox) == EHint::Poor, "...the hint says NOT ENOUGH XP");
		const FPage P = FPage::For(1920, 1080);
		M.Since = 1.f;
		Build(P, M, List);
		bool Crimson = false;
		for (int t = 0; t < List.NumTris; ++t)
			if (List.Tris[t].Item == M.Focus && List.Tris[t].Part == EMenuPart::Keyline)
				Crimson = SameRgb(List.Tris[t].V[0].C, SaudHud::Colour::Danger);
		Check(Crimson, "...its plate's keyline crimson");
		Step(M, DeniedSeconds + 0.01f);
		Check(HintOf(M, EItem::TrainBox) == EHint::TrainBox, "...for 1.2 s, then the hint is the track's again");
		Navigate(M, EAction::Confirm);
		Navigate(M, EAction::NavDown);
		Check(HintOf(M, EItem::TrainKick) == EHint::TrainKick && M.DeniedLeft <= 0.f, "...or until the focus moves");
		M.Status = MidStatus(99999);
		M.Status.Track[5] = Train::MaxLevel;
		M.Focus = IndexOf(M, EItem::TrainIron);
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::Denied && M.Status.Spendable == 99999 && HintOf(M, EItem::TrainIron) == EHint::Maxed,
		      "a track at its top is denied: FULLY TRAINED");
		// a purse emptied under an open question is refused at YES
		M = Model(EScreen::Training, true, EPad::Xbox);
		M.Status = MidStatus(500);
		M.Focus = IndexOf(M, EItem::TrainBox);
		Navigate(M, EAction::Confirm);
		M.Status.Spendable = 10;
		Navigate(M, EAction::NavDown);
		Check(Navigate(M, EAction::Confirm) == EMenuEffect::Denied && M.Status.Spendable == 10 && M.Status.Track[0] == 2,
		      "YES is checked again: a purse emptied under the question is denied");
	}
	// the question names the track and the level, and YES carries the cost
	{
		FMenuModel M = Model(EScreen::Confirm, true, EPad::Xbox, EScreen::Pause, EAsk::Train);
		const FPage P = FPage::For(1920, 1080);
		Build(P, M, List);
		const FMenuText* Hn = FindText(EMenuText::Hint);
		const FMenuText* Ct = FindText(EMenuText::CostTag);
		Check(Hn && Hn->Value == static_cast<int>(EHint::AskTrain) && Hn->Aux == 0 * 10 + 3
		      && std::strcmp(Spell(Hn->Slot, Hn->Value, Hn->Aux).S, "TRAIN BOXING TO LEVEL 3") == 0
		      && FindText(EMenuText::AskHead) && FindText(EMenuText::AskHead)->Value == 2,
		      "the question: TRAIN? -- TRAIN BOXING TO LEVEL 3");
		Check(Ct && Ct->Item == 1 && Ct->Value == Train::Cost(2), "...its YES carries the cost");
	}
	// back out the way in: Pause > Status > Training > the question > YES,
	// then Back, Back: on the Pause's STATUS
	{
		FMenuModel M = Model(EScreen::Confirm, true, EPad::Xbox, EScreen::Status, EAsk::Train);
		const bool In = M.Screen == EScreen::Confirm && M.Root == EScreen::Pause;
		Navigate(M, EAction::NavDown);
		const bool Bought = Navigate(M, EAction::Confirm) == EMenuEffect::Train && M.Screen == EScreen::Training;
		const bool Hint = HintOf(M, EItem::Back) == EHint::BackStatus;
		const bool Up1 = Navigate(M, EAction::Back) == EMenuEffect::Back && M.Screen == EScreen::Status && M.Focus == 0;
		const bool Up2 = Navigate(M, EAction::Back) == EMenuEffect::Back && M.Screen == EScreen::Pause
		                 && M.Focus == IndexOf(M, EItem::Status);
		Check(In && Bought && Hint && Up1 && Up2,
		      "Back goes back the way in: the Training to the Status, the Status to the Pause's STATUS");
		FMenuModel T = Model(EScreen::Training, true, EPad::Xbox, EScreen::Pause);
		Check(Navigate(T, EAction::Back) == EMenuEffect::Back && T.Screen == EScreen::Pause && T.Focus == IndexOf(T, EItem::Training)
		      && Navigate(T, EAction::Back) == EMenuEffect::Resume, "...the Training opened from the Pause to its TRAINING");
		FMenuModel S = Model(EScreen::Status, true, EPad::Xbox);
		Check(Navigate(S, EAction::NavLeft) == EMenuEffect::None && Navigate(S, EAction::Pause) == EMenuEffect::None
		      && S.Screen == EScreen::Status, "left, right and the pause button do nothing on the status");
	}
	// spelled: every slot's string is what Chars measures
	{
		bool Ok = true;
		for (int Sl = 0; Sl <= static_cast<int>(EMenuText::QuestState); ++Sl)
		{
			if (Sl == static_cast<int>(EMenuText::ControlsText)) continue;
			for (int V = -1; V < 30; ++V)
				for (int A = 0; A < 60; A += 7)
				{
					const FSpelled S = Spell(static_cast<EMenuText>(Sl), V, A);
					int N = 0;
					while (S.S[N]) ++N;
					Ok = Ok && N == Chars(static_cast<EMenuText>(Sl), V, A) && (N > 0 || V < 0 || V > 5 || (Sl == static_cast<int>(EMenuText::SkillName) && V > 4));
				}
		}
		Check(Ok && std::strcmp(Spell(EMenuText::CostTag, 640).S, "640 XP") == 0 && std::strcmp(Spell(EMenuText::CostTag, -1).S, "MAX") == 0
		      && std::strcmp(Spell(EMenuText::XpLine, 790, 860).S, "790 / 860 XP") == 0
		      && std::strcmp(Spell(EMenuText::XpToNext, 70, 15).S, "70 TO LEVEL 15") == 0
		      && std::strcmp(Spell(EMenuText::SkillName, 4, 0).S, "?") == 0 && std::strcmp(Spell(EMenuText::SkillName, 4, 1).S, "HAWK FIST") == 0
		      && std::strcmp(Spell(EMenuText::QuestName, 0).S, "FIND THE WAY UP") == 0
		      && std::strcmp(Spell(EMenuText::QuestState, 0).S, "IN PROGRESS") == 0,
		      "every slot spells itself, and Chars is its length");
		Check(SpellsItself(EMenuText::QuestName, 0) && SpellsItself(EMenuText::AskHead, 2) && !SpellsItself(EMenuText::AskHead, 1)
		      && SpellsItself(EMenuText::Hint, static_cast<int>(EHint::AskTrain)) && !SpellsItself(EMenuText::Hint, 0)
		      && !SpellsItself(EMenuText::Resume, 0), "the engine is told which slots it must spell from here");
	}
}

int main()
{
	ModelRules();
	PageRules();
	TrainingNumbers();
	StatusPage();
	TrainingPage();
	Buying();
#if defined(SAUD_MENU_STUB_CONTROLS)
	std::printf("  (built against the stub of SaudControls: Glyph asked for xbox %d, ps %d, keyboard %d times)\n",
	            SaudControls::StubGlyphPad[0], SaudControls::StubGlyphPad[1], SaudControls::StubGlyphPad[2]);
#endif
	if (Fails) { std::printf("%d menu check(s) failed\n", Fails); return 1; }
	std::printf("all menu checks passed\n");
	return 0;
}
