/**
 * The menu's draw list as JSON, for Tools/look/menu_preview.py:
 * SaudMenu::Build (Combat/SaudMenu.h) on a model made from the command
 * line at a given screen size, with no engine. Like hud_dump.cpp: not a
 * test -- it lives beside tests/, not in it, so run.sh does not build it;
 * menu_preview.py does.
 *
 *   menu_dump W H screen=title|pause|settings|controls|confirm|status|training
 *             pad=xbox|ps|keyboard shown=xbox|ps focus=N save=0|1 clock=S since=S
 *             [from=title|pause|status] [ask=quit|new|train] [stage=N] [sound=N] [music=N]
 *             [focusfrom=N focust=T] [xp=N tracks=a,b,c,d,e,f skills=VDPHF won=0|1]
 *             [track=N] [deny=N]
 *
 * The model is built the way the engine builds it: SaudMenu::Open on the
 * Title or the Pause, and a Settings, Controls or Confirm page reached from
 * there through SaudMenu::Navigate (Confirm on the item that opens it), so
 * ReturnTo and the scrim come out as they would in the game. `from` says
 * which of the two a Settings or Controls page was opened from (default
 * title); a Confirm is always the Title's, `ask` says which (quit, or new:
 * NEW GAME over a save, which needs save=1). `stage` is CONTINUE's tag,
 * `sound` and `music` the two levels (0..10), and `focusfrom`/`focust` a
 * focus glide caught part way (2026-10-02). Since 2026-10-07: the Status
 * and the Training are the Pause's (from=status: a Training opened from the
 * Status); `ask=train` asks about the Training's track `track` (default 0);
 * the save is `xp` (spendable), `tracks` (the six levels), `skills` (the
 * five talents found, by letter: Vault, Dash leap, Power kick, Haymaker,
 * hawk Fist) and `won` (the title won: the quest removed); `deny=N`
 * presses Confirm on the Training's item N once more, as a player whose
 * buy is refused would.
 *
 * Prints {"scale", "overflow", "tris": [[x0,y0,r,g,b,a, x1,..., x2,...,
 * part, item, tag], ...], "texts": [{slot, value, aux, x, y, h, rgba,
 * stroke, centre, item, part, after, string}, ...]}. Colours are linear,
 * as the header holds them. "string" is the word the engine will draw for
 * the slot and value -- MenuString() below is the header's own text-slot
 * table, written once, and ControlsText slots go through SaudControls'
 * ControlsText() exactly as the engine's sink will map them.
 */
#include "HarnessTypes.h"
#include "../../Source/SaudFighter/Combat/SaudMenu.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>

using namespace SaudMenu;

static FMenuList List;

/** The word the engine draws for a slot: SaudMenu::Spell, the header's
    own table (since 2026-10-07; this file kept its own copy until then),
    and SaudControls' ControlsText() for a ControlsText slot -- exactly as
    the engine's sink will map them. */
static const char* MenuString(EMenuText Slot, int Value, int Aux)
{
	static FSpelled Buf;   // printed before the next call
	if (Slot == EMenuText::ControlsText)
	{
		return SaudControls::ControlsText(static_cast<SaudControls::EControlsText>(Value), Aux);
	}
	Buf = Spell(Slot, Value, Aux);
	return Buf.S;
}

static void PrintEscaped(const char* S)
{
	std::putchar('"');
	for (; *S; ++S)
	{
		if (*S == '"' || *S == '\\')
		{
			std::putchar('\\');
		}
		std::putchar(*S);
	}
	std::putchar('"');
}

static bool ParsePad(const char* V, SaudControls::EPad& Out)
{
	if (!std::strcmp(V, "xbox")) { Out = SaudControls::EPad::Xbox; return true; }
	if (!std::strcmp(V, "ps") || !std::strcmp(V, "ps5") || !std::strcmp(V, "playstation"))
	{
		Out = SaudControls::EPad::PlayStation;
		return true;
	}
	if (!std::strcmp(V, "keyboard")) { Out = SaudControls::EPad::Keyboard; return true; }
	return false;
}

int main(int argc, char** argv)
{
	if (argc < 3)
	{
		std::fprintf(stderr, "usage: menu_dump W H screen=title|pause|settings|controls|confirm|status|training "
		                     "pad=xbox|ps|keyboard shown=xbox|ps focus=N save=0|1 clock=S since=S "
		                     "[from=title|pause|status] [ask=quit|new|train] [stage=N] [sound=N] [music=N] "
		                     "[focusfrom=N focust=T] [xp=N tracks=a,b,c,d,e,f skills=VDPHF won=0|1] [track=N] [deny=N]\n");
		return 2;
	}
	const float W = static_cast<float>(std::atof(argv[1])), H = static_cast<float>(std::atof(argv[2]));
	EScreen Screen = EScreen::Title, From = EScreen::Title;
	SaudControls::EPad Pad = SaudControls::EPad::Xbox, Shown = SaudControls::EPad::Xbox;
	int Focus = 0;
	bool bSave = false;
	float Clock = 0.f, Since = 1.f;
	EAsk Ask = EAsk::Quit;
	int Stage = 0, Sound = LevelMax, Music = LevelMax, FocusFrom = -1;
	float FocusT = 1.f;
	int Xp = 0, Tracks[Train::Tracks] = {}, TrainT = 0, Deny = -1;
	bool Skills[SaudMenu::Skills] = {}, bWon = false;
	for (int i = 3; i < argc; ++i)
	{
		const char* Eq = std::strchr(argv[i], '=');
		if (!Eq)
		{
			std::fprintf(stderr, "not key=value: %s\n", argv[i]);
			return 2;
		}
		const std::size_t N = static_cast<std::size_t>(Eq - argv[i]);
		const char* V = Eq + 1;
		auto Is = [&](const char* K) { return std::strlen(K) == N && std::strncmp(argv[i], K, N) == 0; };
		bool bOk = true;
		if (Is("screen") || Is("from"))
		{
			EScreen S;
			if (!std::strcmp(V, "title")) S = EScreen::Title;
			else if (!std::strcmp(V, "pause")) S = EScreen::Pause;
			else if (!std::strcmp(V, "settings")) S = EScreen::Settings;
			else if (!std::strcmp(V, "controls")) S = EScreen::Controls;
			else if (!std::strcmp(V, "confirm")) S = EScreen::Confirm;
			else if (!std::strcmp(V, "status")) S = EScreen::Status;
			else if (!std::strcmp(V, "training")) S = EScreen::Training;
			else { bOk = false; S = EScreen::Title; }
			if (Is("screen")) Screen = S; else From = S;
			if (Is("from") && S != EScreen::Title && S != EScreen::Pause && S != EScreen::Status) bOk = false;
		}
		else if (Is("pad")) bOk = ParsePad(V, Pad);
		else if (Is("shown")) bOk = ParsePad(V, Shown) && Shown != SaudControls::EPad::Keyboard;
		else if (Is("focus")) Focus = std::atoi(V);
		else if (Is("save")) bSave = std::atof(V) > 0.5;
		else if (Is("clock")) Clock = static_cast<float>(std::atof(V));
		else if (Is("since")) Since = static_cast<float>(std::atof(V));
		else if (Is("ask"))
		{
			if (!std::strcmp(V, "quit")) Ask = EAsk::Quit;
			else if (!std::strcmp(V, "new")) Ask = EAsk::NewGame;
			else if (!std::strcmp(V, "train")) Ask = EAsk::Train;
			else bOk = false;
		}
		else if (Is("stage")) Stage = std::atoi(V);
		else if (Is("sound")) { Sound = std::atoi(V); bOk = Sound >= 0 && Sound <= LevelMax; }
		else if (Is("music")) { Music = std::atoi(V); bOk = Music >= 0 && Music <= LevelMax; }
		else if (Is("focusfrom")) FocusFrom = std::atoi(V);
		else if (Is("focust")) FocusT = static_cast<float>(std::atof(V));
		else if (Is("xp")) Xp = std::atoi(V);
		else if (Is("tracks"))
		{
			int K = 0;
			for (const char* C = V; *C && K < Train::Tracks; ++C)
				if (*C >= '0' && *C <= '9') Tracks[K++] = *C - '0';
			bOk = K == Train::Tracks;
		}
		else if (Is("skills"))
		{
			const char* Letters = "VDPHF";
			for (int K = 0; K < SaudMenu::Skills; ++K) Skills[K] = std::strchr(V, Letters[K]) != nullptr;
		}
		else if (Is("won")) bWon = std::atof(V) > 0.5;
		else if (Is("track")) { TrainT = std::atoi(V); bOk = TrainT >= 0 && TrainT < Train::Tracks; }
		else if (Is("deny")) Deny = std::atoi(V);
		else
		{
			std::fprintf(stderr, "unknown key: %s\n", argv[i]);
			return 2;
		}
		if (!bOk)
		{
			std::fprintf(stderr, "bad value: %s\n", argv[i]);
			return 2;
		}
	}

	// The model, the engine's way: Open the root, Navigate into a sub-page.
	FMenuModel M;
	M.Pad = Pad;
	M.bHasSave = bSave;
	M.Clock = Clock;
	M.StageReached = Stage;
	M.SoundLevel = Sound;
	M.MusicLevel = Music;
	M.Status = MakeStatus(Xp, Tracks, Skills, bWon);
	// confirm on the item named, on the screen the model is on
	const auto Press = [&](EItem Opener) -> bool
	{
		EItem Its[MaxItems];
		const int NI = Items(M, Its);
		M.Focus = -1;
		for (int i = 0; i < NI; ++i)
		{
			if (Its[i] == Opener) M.Focus = i;
		}
		return M.Focus >= 0 && Navigate(M, SaudControls::EAction::Confirm) == EMenuEffect::Tap;
	};
	bool bOpened = true;
	if (Screen == EScreen::Title || Screen == EScreen::Pause)
	{
		Open(M, Screen);
	}
	else if (Screen == EScreen::Status || Screen == EScreen::Training || (Screen == EScreen::Confirm && Ask == EAsk::Train))
	{
		Open(M, EScreen::Pause);
		if (Screen == EScreen::Status || From == EScreen::Status) bOpened = Press(EItem::Status);
		if (Screen != EScreen::Status) bOpened = bOpened && Press(EItem::Training);
		if (Screen == EScreen::Confirm)
			bOpened = bOpened && Press(static_cast<EItem>(static_cast<int>(EItem::TrainBox) + TrainT));
	}
	else
	{
		if (Screen == EScreen::Confirm)
		{
			From = EScreen::Title;   // only the Title asks
		}
		if (From == EScreen::Status) From = EScreen::Pause;
		Open(M, From);
		// the item that opens it, found by name: where it sits depends on
		// the root and on whether there is a save
		bOpened = Press(Screen == EScreen::Controls ? EItem::Controls
		              : Screen == EScreen::Settings ? EItem::Settings
		              : Ask == EAsk::NewGame        ? EItem::NewGame
		                                            : EItem::Quit);
	}
	if (!bOpened || M.Screen != Screen)
	{
		std::fprintf(stderr, "could not open the page from the root (NEW GAME needs save=1; a Train question "
		                     "needs xp for the track)\n");
		return 1;
	}
	M.Shown = Shown;   // after Navigate: OpenSub sets Shown from Pad
	M.Since = Since;
	const int N = ItemCount(M);
	if (Focus < 0 || Focus >= N)
	{
		std::fprintf(stderr, "focus %d outside 0..%d, clamped\n", Focus, N - 1);
		Focus = Focus < 0 ? 0 : N - 1;
	}
	M.Focus = Focus;
	M.FocusFrom = static_cast<float>(FocusFrom < 0 ? Focus : FocusFrom);
	M.FocusT = FocusFrom < 0 ? 1.f : FocusT;
	// a refused buy, just pressed: the plate crimson, the hint saying why
	if (Deny >= 0 && Screen == EScreen::Training)
	{
		M.Focus = Deny < N ? Deny : N - 1;
		M.FocusFrom = static_cast<float>(M.Focus);
		if (Navigate(M, SaudControls::EAction::Confirm) != EMenuEffect::Denied)
		{
			std::fprintf(stderr, "deny=%d: that buy was not refused\n", Deny);
			return 1;
		}
		M.Since = Since;
	}

	const FPage P = FPage::For(W, H);
	Build(P, M, List);

	std::printf("{\"scale\": %g, \"overflow\": %s, \"screen\": %d, \"pad\": %d, \"shown\": %d,\n\"tris\": [", P.Scale,
	            List.bOverflow ? "true" : "false", static_cast<int>(M.Screen), static_cast<int>(M.Pad),
	            static_cast<int>(M.Shown));
	for (int t = 0; t < List.NumTris; ++t)
	{
		const FMenuTri& T = List.Tris[t];
		std::printf("%s\n[", t ? "," : "");
		for (int v = 0; v < 3; ++v)
		{
			const FMenuVert& X = T.V[v];
			std::printf("%.3f, %.3f, %.5f, %.5f, %.5f, %.4f, ", X.P.X, X.P.Y, X.C.R, X.C.G, X.C.B, X.C.A);
		}
		std::printf("%d, %d, %d]", static_cast<int>(T.Part), T.Item, T.Tag);
	}
	std::printf("],\n\"texts\": [");
	for (int t = 0; t < List.NumTexts; ++t)
	{
		const FMenuText& X = List.Texts[t];
		std::printf("%s\n{\"slot\": %d, \"value\": %d, \"aux\": %d, \"x\": %.3f, \"y\": %.3f, \"h\": %.3f, "
		            "\"rgba\": [%.5f, %.5f, %.5f, %.4f], \"stroke\": %.3f, \"centre\": %s, \"item\": %d, "
		            "\"part\": %d, \"after\": %d, \"string\": ",
		            t ? "," : "", static_cast<int>(X.Slot), X.Value, X.Aux, X.At.X, X.At.Y, X.Height, X.Colour.R,
		            X.Colour.G, X.Colour.B, X.Colour.A, X.Stroke, X.bCentre ? "true" : "false", X.Item,
		            static_cast<int>(X.Part), X.TrisBefore);
		PrintEscaped(MenuString(X.Slot, X.Value, X.Aux));
		std::putchar('}');
	}
	std::printf("]}\n");
	return 0;
}
