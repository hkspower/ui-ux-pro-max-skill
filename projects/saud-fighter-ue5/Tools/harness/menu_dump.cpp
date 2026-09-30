/**
 * The menu's draw list as JSON, for Tools/look/menu_preview.py:
 * SaudMenu::Build (Combat/SaudMenu.h) on a model made from the command
 * line at a given screen size, with no engine. Like hud_dump.cpp: not a
 * test -- it lives beside tests/, not in it, so run.sh does not build it;
 * menu_preview.py does.
 *
 *   menu_dump W H screen=title|pause|settings|controls pad=xbox|ps|keyboard
 *             shown=xbox|ps focus=N save=0|1 clock=S since=S [from=title|pause]
 *
 * The model is built the way the engine builds it: SaudMenu::Open on the
 * Title or the Pause, and a Settings or Controls page reached from there
 * through SaudMenu::Navigate (Confirm on its item), so ReturnTo and the
 * scrim come out as they would in the game. `from` says which of the two
 * a Settings or Controls page was opened from (default title).
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

/** The slot -> string table from the head of SaudMenu.h, the one mapping
    the engine will use. Value picks the variant where the table has one;
    Aux is SaudControls' own value for a ControlsText slot. */
static const char* MenuString(EMenuText Slot, int Value, int Aux)
{
	switch (Slot)
	{
	case EMenuText::Saud: return "SAUD";
	case EMenuText::Subtitle: return "KUWAIT FIGHTER";
	case EMenuText::Paused: return "PAUSED";
	case EMenuText::SettingsHead: return "SETTINGS";
	case EMenuText::Continue: return "CONTINUE";
	case EMenuText::Fight: return "FIGHT";
	case EMenuText::Controls: return "CONTROLS";
	case EMenuText::Settings: return "SETTINGS";
	case EMenuText::Quit: return "QUIT";
	case EMenuText::Resume: return "RESUME";
	case EMenuText::QuitToTitle: return "QUIT TO TITLE";
	case EMenuText::Difficulty:
		return Value == 0 ? "DIFFICULTY  ROOKIE" : (Value == 1 ? "DIFFICULTY  PRO" : "DIFFICULTY  CHAMPION");
	case EMenuText::Sound: return Value ? "SOUND  ON" : "SOUND  OFF";
	case EMenuText::Music: return Value ? "MUSIC  ON" : "MUSIC  OFF";
	case EMenuText::Vibration: return Value ? "VIBRATION  ON" : "VIBRATION  OFF";
	case EMenuText::Back: return "BACK";
	case EMenuText::PromptSelect: return "SELECT";
	case EMenuText::PromptBack: return "BACK";
	case EMenuText::PromptAdjust: return "ADJUST";
	case EMenuText::PromptFlip: return Value ? "SHOW PS5" : "SHOW XBOX";
	case EMenuText::KeySelect: return "ENTER  SELECT";
	case EMenuText::KeyBack: return "ESC  BACK";
	case EMenuText::KeyAdjust: return "ARROWS  ADJUST";
	case EMenuText::KeyFlip: return Value ? "TAB  SHOW PS5" : "TAB  SHOW XBOX";
	case EMenuText::ControlsText:
		return SaudControls::ControlsText(static_cast<SaudControls::EControlsText>(Value), Aux);
	default:
		return "?";
	}
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
		std::fprintf(stderr, "usage: menu_dump W H screen=title|pause|settings|controls pad=xbox|ps|keyboard "
		                     "shown=xbox|ps focus=N save=0|1 clock=S since=S [from=title|pause]\n");
		return 2;
	}
	const float W = static_cast<float>(std::atof(argv[1])), H = static_cast<float>(std::atof(argv[2]));
	EScreen Screen = EScreen::Title, From = EScreen::Title;
	SaudControls::EPad Pad = SaudControls::EPad::Xbox, Shown = SaudControls::EPad::Xbox;
	int Focus = 0;
	bool bSave = false;
	float Clock = 0.f, Since = 1.f;
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
			else { bOk = false; S = EScreen::Title; }
			if (Is("screen")) Screen = S; else From = S;
			if (Is("from") && S != EScreen::Title && S != EScreen::Pause) bOk = false;
		}
		else if (Is("pad")) bOk = ParsePad(V, Pad);
		else if (Is("shown")) bOk = ParsePad(V, Shown) && Shown != SaudControls::EPad::Keyboard;
		else if (Is("focus")) Focus = std::atoi(V);
		else if (Is("save")) bSave = std::atof(V) > 0.5;
		else if (Is("clock")) Clock = static_cast<float>(std::atof(V));
		else if (Is("since")) Since = static_cast<float>(std::atof(V));
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
	if (Screen == EScreen::Title || Screen == EScreen::Pause)
	{
		Open(M, Screen);
	}
	else
	{
		Open(M, From);
		// the item that opens it: CONTROLS is index 1, SETTINGS index 2 on both roots
		M.Focus = Screen == EScreen::Controls ? 1 : 2;
		const EMenuEffect E = Navigate(M, SaudControls::EAction::Confirm);
		if (E != EMenuEffect::Tap || M.Screen != Screen)
		{
			std::fprintf(stderr, "could not open the sub-page from the root\n");
			return 1;
		}
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
