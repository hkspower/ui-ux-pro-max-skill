#pragma once

/**
 * The System's windows: how the Halqa speaks to Saud -- with no engine in
 * it.
 *
 * 2026-10-07 (Riyadh), "improve solo leveling theme all game", settled as
 * the Unreal build only, its STYLE and none of its names: the System is the
 * Halqa itself talking to him. It never explains itself. It speaks in
 * windows -- a short UPPERCASE heading, one or two plain sentences,
 * sometimes a reward -- and every kindness binds him closer: it hands him a
 * quest to find the way up, FIND THE WAY UP, keeps it open the whole game,
 * and rewards him for everything but that. The words are data
 * (Content/Data/DT_SystemLines.json, read by USaudSystemSubsystem); this
 * file is what happens to them:
 *
 *  - the EVENTS (EKind) and what each one is worth: its priority, the lane
 *    it shows in (the window, or the small toast), its timings;
 *  - the QUEUE (FModel): at most one window and one toast at once; a level
 *    up during a quest complete waits for it; a man going down cuts
 *    whatever is showing; two level ups not yet shown are one window; the
 *    boss's WARNING (SaudHud's own, drawn by the HUD) is handed off -- the
 *    System draws no second one and holds its lane while that one wipes
 *    open; every timing in REAL time (FClock::Real), so a blow's freeze --
 *    global time dilation -- holds the fight, not the windows;
 *  - the open quest, shown as a small line on the HUD (QUEST / FIND THE WAY
 *    UP / IN PROGRESS) from the first landing until the victory removes it;
 *  - the LAYOUT and the DRAWING (Build): in the HUD's own primitives and
 *    palette (SaudHud in SaudAnime.h -- the navy panel cut at two corners,
 *    the cyan edge and its glow, ice lettering; crimson for a warning;
 *    violet for HAWK FIST), title-safe at every screen shape, nothing over
 *    the fight's centre box, nothing over the HUD's own windows, every text
 *    stroked and at least 1/36 of the screen tall.
 *
 * Where the windows stand: the screen's top band (above the fight's box,
 * which starts at 0.2 of the height) right of STATUS takes the WINDOW; the
 * left column under STATUS (left of the box, which starts at 0.3 of the
 * width) takes the open-quest line and, under it, the TOAST. The boss's
 * WARNING keeps the bottom band, COMBO the right column.
 *
 * Header of free functions and plain structs, like SaudAnime.h, so
 * Tools/harness builds it with g++ and checks it (tests/system.cpp), and
 * Tools/look/system_preview.py draws it without an engine
 * (Tools/harness/system_dump.cpp prints it). English only: FCanvas does no
 * Arabic shaping, so the lines' Arabic stays data.
 */

#if defined(SAUD_HARNESS)
	#include "HarnessTypes.h"
#else
	#include "CoreMinimal.h"
#endif
#include "SaudAnime.h"
#include <cstring>
#include <initializer_list>

namespace SaudSystem
{
	using SaudHud::FPage;
	using SaudHud::FPoint;
	using SaudHud::FRect;
	using SaudHud::FRgba;

	// ------------------------------------------------------------ the events
	/** Everything the System says. Each has a row in DT_SystemLines.json
	    (Event = KindName; StageEntered, RankUp, SkillAcquired, GateCleared
	    and Speaker are keyed further, by stage, rank, talent, reward and
	    speaker). BossWarning is the hand-off: no System window, the HUD's
	    own WARNING. */
	enum class EKind : unsigned char
	{
		QuestGiven,      // the first landing: FIND THE WAY UP
		QuestUpdated,    // the ring closes: the souq from the desert, after HAWK FIST
		QuestComplete,   // a stage cleared, its XP, the open quest beneath it
		QuestRemoved,    // the victory over AL-WAHSH: FIND THE WAY UP, no longer required
		LevelUp,
		RankUp,          // the title changes: ROOKIE .. CHAMPION
		SkillAcquired,   // a talent: VAULT .. HAWK FIST
		GateCleared,     // a gate opened: the toast
		StageEntered,    // an area's quest, from its story
		BossWarning,     // handed to the HUD's WARNING window
		Down,            // he went down
		Speaker,         // a named speaker's line: AL-SAQR's, before his fight, once
		Count
	};
	constexpr int NumKinds = static_cast<int>(EKind::Count);

	inline const char* KindName(EKind K)
	{
		static const char* const Names[NumKinds] = {
			"QuestGiven", "QuestUpdated", "QuestComplete", "QuestRemoved", "LevelUp", "RankUp",
			"SkillAcquired", "GateCleared", "StageEntered", "BossWarning", "Down", "Speaker"};
		const int I = static_cast<int>(K);
		return I >= 0 && I < NumKinds ? Names[I] : "";
	}

	/** Where an event shows: the window (one at a time), the toast (one at
	    a time, beside it), or nowhere of the System's own. */
	enum class ELane : unsigned char { Window, Toast, None };
	/** A window's edge: the System's cyan; violet for HAWK FIST, the one
	    talent that was not his; crimson for a warning. */
	enum class ETint : unsigned char { System, Shadow, Danger };

	struct FRule
	{
		int Priority = 0;       // higher opens first; equal, the older first
		ELane Lane = ELane::Window;
		float Open = 0.30f;     // real seconds: the window wipes open...
		float Hold = -1.f;      // ...holds (under 0: long enough to read, ReadSeconds)...
		float Close = 0.30f;    // ...and fades out
		bool bPreempts = false; // cuts whatever window is showing
	};

	/** What each event is worth. A level up during a quest complete waits
	    for it (60 under 70) and the rewards read in the order a stage's end
	    pays them: the quest, the level, the rank, the talent. A man going
	    down is above everything and does not wait. AL-SAQR's line fades
	    fast. The victory's window holds longest -- then the game's own
	    victory. */
	inline FRule RuleOf(EKind K)
	{
		switch (K)
		{
		case EKind::Down:          return {100, ELane::Window, 0.20f, 2.6f, 0.30f, true};
		case EKind::QuestRemoved:  return {90, ELane::Window, 0.40f, 4.0f, 0.60f, false};
		case EKind::Speaker:       return {85, ELane::Window, 0.20f, 1.8f, 0.12f, false};
		case EKind::QuestComplete: return {70, ELane::Window, 0.30f, -1.f, 0.30f, false};
		case EKind::LevelUp:       return {60, ELane::Window, 0.30f, -1.f, 0.30f, false};
		case EKind::RankUp:        return {55, ELane::Window, 0.30f, -1.f, 0.30f, false};
		case EKind::SkillAcquired: return {50, ELane::Window, 0.30f, -1.f, 0.30f, false};
		case EKind::QuestUpdated:  return {45, ELane::Window, 0.30f, -1.f, 0.30f, false};
		case EKind::QuestGiven:    return {40, ELane::Window, 0.30f, -1.f, 0.30f, false};
		case EKind::StageEntered:  return {30, ELane::Window, 0.30f, -1.f, 0.30f, false};
		case EKind::GateCleared:   return {20, ELane::Toast, 0.20f, 2.2f, 0.30f, false};
		default:                   return {0, ELane::None, 0.f, 0.f, 0.f, false};   // BossWarning, the hand-off
		}
	}

	constexpr float WindowGap = 0.20f;      // real seconds between one window going and the next opening
	constexpr float ToastGap = 0.15f;
	constexpr float PreemptClose = 0.10f;   // what is showing when he goes down fades this fast
	/** The boss's WARNING wipes open over SaudHud's 0.40 s: the System's
	    lane holds that and a beat more, so it reads alone. */
	constexpr float BossHold = SaudHud::BannerRevealSeconds + 0.30f;
	constexpr float QuestFadeSeconds = 0.30f;   // the open-quest line fades in and out
	/** Long enough to read: a second and a fifth, and a twentieth a letter. */
	constexpr float ReadBase = 1.2f, ReadPerChar = 0.05f, ReadMin = 2.4f, ReadMax = 4.5f;

	// ------------------------------------------------------------- the words
	constexpr int TitleMax = 40, HeadMax = 64, BodyMax = 96, RewardMax = 40, BeneathMax = 40, StatusMax = 24, KeyMax = 32;

	/** A window's words, as drawn (or, in an FSysEvent, as templates). Title
	    is the heading strip; Head the big first line, with Reward to its
	    right; Body the line under it; Beneath and Status a quest shown under
	    it (QUEST COMPLETE's FIND THE WAY UP / IN PROGRESS). Plain ASCII. */
	struct FLines
	{
		char Title[TitleMax] = {};
		char Head[HeadMax] = {};
		char Body[BodyMax] = {};
		char Reward[RewardMax] = {};
		char Beneath[BeneathMax] = {};
		char Status[StatusMax] = {};
	};

	inline void Put(char* Dst, int N, const char* Src)
	{
		int i = 0;
		for (; Src && Src[i] && i < N - 1; ++i) Dst[i] = Src[i];
		Dst[i] = 0;
	}
	inline bool Empty(const char* S) { return !S || !S[0]; }
	inline bool Same(const char* A, const char* B) { return std::strcmp(A ? A : "", B ? B : "") == 0; }

	/** The numbers and names a template's {braces} stand for. */
	struct FArgs
	{
		int Level = 0, Hp = 0, Mp = 0, Xp = 0;
		char Rank[24] = {};
		char Skill[24] = {};
		char Quest[HeadMax] = {};
	};

	/** The placeholders a line may carry; anything else in braces is left
	    as it is (and the harness fails a line that has one). */
	inline bool KnownPlaceholder(const char* Name, int Len)
	{
		static const char* const Known[] = {"level", "hp", "mp", "xp", "rank", "skill", "quest"};
		for (const char* K : Known)
		{
			if (static_cast<int>(std::strlen(K)) == Len && std::strncmp(K, Name, Len) == 0) return true;
		}
		return false;
	}

	/** Tpl with {level} {hp} {mp} {xp} {rank} {skill} {quest} filled in. */
	inline void Format(const char* Tpl, const FArgs& A, char* Out, int N)
	{
		int o = 0;
		auto Emit = [&](const char* S) { for (; *S && o < N - 1; ++S) Out[o++] = *S; };
		auto EmitInt = [&](int V) {
			char B[16];
			int n = 0;
			const bool bNeg = V < 0;
			unsigned U = bNeg ? static_cast<unsigned>(-V) : static_cast<unsigned>(V);
			do { B[n++] = static_cast<char>('0' + U % 10); U /= 10; } while (U && n < 15);
			if (bNeg && o < N - 1) Out[o++] = '-';
			while (n && o < N - 1) Out[o++] = B[--n];
		};
		for (const char* P = Tpl ? Tpl : ""; *P && o < N - 1;)
		{
			if (*P == '{')
			{
				const char* E = std::strchr(P, '}');
				const int Len = E ? static_cast<int>(E - P - 1) : -1;
				if (E && KnownPlaceholder(P + 1, Len))
				{
					auto Is = [&](const char* K) { return static_cast<int>(std::strlen(K)) == Len && std::strncmp(K, P + 1, Len) == 0; };
					if (Is("level")) EmitInt(A.Level);
					else if (Is("hp")) EmitInt(A.Hp);
					else if (Is("mp")) EmitInt(A.Mp);
					else if (Is("xp")) EmitInt(A.Xp);
					else if (Is("rank")) Emit(A.Rank);
					else if (Is("skill")) Emit(A.Skill);
					else Emit(A.Quest);
					P = E + 1;
					continue;
				}
			}
			Out[o++] = *P++;
		}
		Out[o] = 0;
	}

	inline FLines FormatLines(const FLines& Tpl, const FArgs& A)
	{
		FLines L;
		Format(Tpl.Title, A, L.Title, TitleMax);
		Format(Tpl.Head, A, L.Head, HeadMax);
		Format(Tpl.Body, A, L.Body, BodyMax);
		Format(Tpl.Reward, A, L.Reward, RewardMax);
		Format(Tpl.Beneath, A, L.Beneath, BeneathMax);
		Format(Tpl.Status, A, L.Status, StatusMax);
		return L;
	}

	inline int Chars(const FLines& L)
	{
		return static_cast<int>(std::strlen(L.Title) + std::strlen(L.Head) + std::strlen(L.Body) + std::strlen(L.Reward)
		                        + std::strlen(L.Beneath) + std::strlen(L.Status));
	}
	inline float ReadSeconds(const FLines& L)
	{
		return FMath::Clamp(ReadBase + ReadPerChar * static_cast<float>(Chars(L)), ReadMin, ReadMax);
	}

	/** The one talent that was not his is violet; a man down is crimson;
	    everything else is the System's cyan. */
	inline ETint TintFor(EKind K, const char* Key)
	{
		if (K == EKind::Down) return ETint::Danger;
		if (K == EKind::SkillAcquired && Same(Key, "HawkFist")) return ETint::Shadow;
		return ETint::System;
	}

	struct FSysEvent
	{
		EKind Kind = EKind::StageEntered;
		char Key[KeyMax] = {};      // the stage, rank, talent or speaker it is about
		FLines Tpl;                 // its row's words, braces and all
		FArgs Args;
		ETint Tint = ETint::System;
	};

	inline FSysEvent MakeEvent(EKind K, const char* Key, const FLines& Tpl, const FArgs& Args)
	{
		FSysEvent E;
		E.Kind = K;
		Put(E.Key, KeyMax, Key);
		E.Tpl = Tpl;
		E.Args = Args;
		E.Tint = TintFor(K, Key);
		return E;
	}

	/** Real time and the world's (dilated) time this frame. The windows run
	    on Real only: a blow's freeze slows the world to nearly nothing and
	    must not hold a window open. */
	struct FClock
	{
		float Real = 0.f;
		float World = 0.f;
	};

	inline float EaseOut(float T)
	{
		const float C = FMath::Clamp(T, 0.f, 1.f);
		return 1.f - (1.f - C) * (1.f - C) * (1.f - C);
	}

	/** A window or the toast while it shows. */
	struct FShown
	{
		bool bOn = false;
		FSysEvent E;
		FLines Text;               // formatted, as drawn
		float Age = 0.f;           // real seconds since it began to open
		float Open = 0.f, Hold = 0.f, Close = 0.f;
		bool bCut = false;         // cut short (by a man going down): no gap after it

		float Total() const { return Open + Hold + Close; }
		/** How far it has wiped open, 0..1. */
		float OpenFraction() const { return Open > 0.f ? EaseOut(Age / Open) : 1.f; }
		/** Its words show once it is fully open, so none stands outside it. */
		bool TextShown() const { return Age >= Open; }
		/** 1 until it begins to close, then down to 0. */
		float Fade() const
		{
			const float Into = Age - Open - Hold;
			return Into <= 0.f ? 1.f : (Close > 0.f ? FMath::Clamp(1.f - Into / Close, 0.f, 1.f) : 0.f);
		}
	};

	constexpr int QueueMax = 16;

	/** The System's whole state: what waits, what shows, the open quest. */
	struct FModel
	{
		FSysEvent Queue[QueueMax];
		int Order[QueueMax] = {};
		int NumQueued = 0;
		int Seq = 0;
		int Dropped = 0;

		FShown Window, Toast;
		float WindowWait = 0.f, ToastWait = 0.f;

		/** The open quest (FIND THE WAY UP): opened by the window that gives
		    it, removed by the window that removes it; Quest is its line's
		    words (Title QUEST, Head FIND THE WAY UP, Status IN PROGRESS) and
		    QuestShow its fade, 0..1. */
		bool bQuestOpen = false;
		float QuestShow = 0.f;
		FLines Quest;

		/** What opened on the last Tick, for the look's flourish
		    (USaudLookSubsystem::OnSystemEvent). */
		EKind Opened[2] = {EKind::Count, EKind::Count};
		int NumOpened = 0;

		static int PriorityOf(const FSysEvent& E) { return RuleOf(E.Kind).Priority; }

		int FindPending(EKind K, const char* Key = nullptr) const
		{
			for (int i = 0; i < NumQueued; ++i)
			{
				if (Queue[i].Kind == K && (!Key || Same(Queue[i].Key, Key))) return i;
			}
			return -1;
		}
		bool Pending(EKind K) const { return FindPending(K) >= 0; }

		/** A returning profile: the quest is open (or not) without a window. */
		void SetQuestOpen(bool bOpen) { bQuestOpen = bOpen; }

		void Push(const FSysEvent& E)
		{
			const FRule R = RuleOf(E.Kind);
			if (R.Lane == ELane::None)
			{
				// the boss's WARNING is the HUD's: hold the lane while it opens
				WindowWait = FMath::Max(WindowWait, BossHold);
				return;
			}
			if (E.Kind == EKind::LevelUp)
			{
				// two level ups not yet shown are one window: the later
				// level, what both were worth
				const int i = FindPending(EKind::LevelUp);
				if (i >= 0)
				{
					Queue[i].Args.Level = E.Args.Level;
					Queue[i].Args.Hp += E.Args.Hp;
					Queue[i].Args.Mp += E.Args.Mp;
					return;
				}
			}
			else if (FindPending(E.Kind, E.Key) >= 0)
			{
				return;   // already waiting to be said
			}
			if (R.bPreempts && Window.bOn && RuleOf(Window.E.Kind).Priority < R.Priority)
			{
				// what is showing fades out now, fast, and no gap after it
				if (Window.Age < Window.Open) Window.Open = Window.Age;
				Window.Hold = FMath::Max(0.f, Window.Age - Window.Open);
				Window.Close = FMath::Min(Window.Close, PreemptClose);
				Window.bCut = true;
			}
			if (NumQueued >= QueueMax)
			{
				// full: the least of them goes, if it is less than this one
				int Low = 0;
				for (int i = 1; i < NumQueued; ++i)
				{
					const int Pi = PriorityOf(Queue[i]), Pl = PriorityOf(Queue[Low]);
					if (Pi < Pl || (Pi == Pl && Order[i] < Order[Low])) Low = i;
				}
				++Dropped;
				if (PriorityOf(Queue[Low]) >= R.Priority) return;
				Queue[Low] = E;
				Order[Low] = Seq++;
				return;
			}
			Queue[NumQueued] = E;
			Order[NumQueued] = Seq++;
			++NumQueued;
		}

		/** The next event for a lane: the highest priority, the oldest of
		    equals. -1 when none waits. */
		int Next(ELane Lane) const
		{
			int Best = -1;
			for (int i = 0; i < NumQueued; ++i)
			{
				if (RuleOf(Queue[i].Kind).Lane != Lane) continue;
				if (Best < 0) { Best = i; continue; }
				const int Pi = PriorityOf(Queue[i]), Pb = PriorityOf(Queue[Best]);
				if (Pi > Pb || (Pi == Pb && Order[i] < Order[Best])) Best = i;
			}
			return Best;
		}

		void Take(int i, FShown& Into)
		{
			Into = FShown();
			Into.bOn = true;
			Into.E = Queue[i];
			Into.Text = FormatLines(Queue[i].Tpl, Queue[i].Args);
			const FRule R = RuleOf(Queue[i].Kind);
			Into.Open = R.Open;
			Into.Hold = R.Hold >= 0.f ? R.Hold : ReadSeconds(Into.Text);
			Into.Close = R.Close;
			for (int k = i; k + 1 < NumQueued; ++k)
			{
				Queue[k] = Queue[k + 1];
				Order[k] = Order[k + 1];
			}
			--NumQueued;
			if (Into.E.Kind == EKind::QuestGiven) bQuestOpen = true;     // from the first landing...
			if (Into.E.Kind == EKind::QuestRemoved) bQuestOpen = false;  // ...until the victory removes it
			if (NumOpened < 2) Opened[NumOpened++] = Into.E.Kind;
		}

		void Tick(const FClock& Clock)
		{
			const float Dt = FMath::Clamp(Clock.Real, 0.f, 0.25f);
			NumOpened = 0;
			WindowWait = FMath::Max(0.f, WindowWait - Dt);
			ToastWait = FMath::Max(0.f, ToastWait - Dt);
			for (FShown* S : {&Window, &Toast})
			{
				if (!S->bOn) continue;
				S->Age += Dt;
				if (S->Age >= S->Total())
				{
					S->bOn = false;
					float& Wait = S == &Window ? WindowWait : ToastWait;
					Wait = FMath::Max(Wait, S->bCut ? 0.f : (S == &Window ? WindowGap : ToastGap));
				}
			}
			if (!Window.bOn && WindowWait <= 0.f)
			{
				const int i = Next(ELane::Window);
				if (i >= 0) Take(i, Window);
			}
			if (!Toast.bOn && ToastWait <= 0.f)
			{
				const int i = Next(ELane::Toast);
				if (i >= 0) Take(i, Toast);
			}
			const float Step = Dt / QuestFadeSeconds;
			QuestShow = bQuestOpen ? FMath::Min(1.f, QuestShow + Step) : FMath::Max(0.f, QuestShow - Step);
		}
	};

	// ------------------------------------------------------------ the layout
	// Page px (1080 lines), as SaudHud's: scaled by the screen's height.
	constexpr float TitleText = SaudHud::TitleText;   // the heading strip, 30
	constexpr float HeadText = 40.f;                  // the window's first line
	constexpr float BodyText = 32.f;                  // its sentence
	constexpr float RewardText = 30.f;                // the reward, right of the first line
	constexpr float LineText = 30.f;                  // the open quest, the line beneath, the toast
	constexpr float PadPx = SaudHud::PadPx;           // 22, as the HUD's windows
	constexpr float TopPad = 8.f, RowGap = 4.f, BottomPad = 10.f;
	constexpr float BareBottom = 22.f;                // a window with nothing under its heading
	constexpr float RowSep = 28.f;                    // between the first line and its reward
	constexpr float GapPx = 16.f;                     // between one window's glow and the next one's
	constexpr float WindowMinW = 520.f;
	constexpr float WindowMaxW = 980.f;
	constexpr float SideMinW = 300.f;                 // the open quest and the toast
	/** The fight's box (SaudHud's rule, tests/anime.cpp): the middle 40 %
	    across and 60 % down. The System never draws in it. */
	constexpr float FightX0 = 0.30f, FightY0 = 0.20f;

	/** A text's width, from its letters' advances as a share of the line
	    height: DejaVu Sans Bold's (the preview's font, wider than the
	    engine's Roboto), printable ASCII from the space, each rounded UP to
	    the next hundredth -- so a line that fits here fits there.
	    system_preview.py measures the real thing and fails what does not
	    fit. */
	inline float Advance(char C)
	{
		static const float Table[95] = {
			0.31f, 0.40f, 0.46f, 0.73f, 0.61f, 0.87f, 0.76f, 0.27f, 0.40f, 0.40f, 0.46f, 0.73f,   //  !"#$%&'()*+
			0.34f, 0.37f, 0.34f, 0.32f, 0.61f, 0.61f, 0.61f, 0.61f, 0.61f, 0.61f, 0.61f, 0.61f,   // ,-./01234567
			0.61f, 0.61f, 0.35f, 0.35f, 0.73f, 0.73f, 0.73f, 0.51f, 0.87f, 0.67f, 0.66f, 0.64f,   // 89:;<=>?@ABC
			0.72f, 0.60f, 0.60f, 0.71f, 0.73f, 0.33f, 0.33f, 0.68f, 0.56f, 0.86f, 0.73f, 0.74f,   // DEFGHIJKLMNO
			0.64f, 0.74f, 0.67f, 0.63f, 0.60f, 0.71f, 0.67f, 0.96f, 0.67f, 0.63f, 0.63f, 0.40f,   // PQRSTUVWXYZ[
			0.32f, 0.40f, 0.73f, 0.44f, 0.44f, 0.59f, 0.62f, 0.52f, 0.62f, 0.59f, 0.38f, 0.62f,   // \]^_`abcdefg
			0.62f, 0.30f, 0.30f, 0.58f, 0.30f, 0.90f, 0.62f, 0.60f, 0.62f, 0.62f, 0.43f, 0.52f,   // hijklmnopqrs
			0.42f, 0.62f, 0.57f, 0.80f, 0.56f, 0.57f, 0.51f, 0.62f, 0.32f, 0.62f, 0.73f};         // tuvwxyz{|}~
		const int I = static_cast<int>(static_cast<unsigned char>(C)) - 32;
		return I >= 0 && I < 95 ? Table[I] : 0.96f;
	}
	inline float TextWidth(const char* S, float Height)
	{
		float W = 0.f;
		for (; S && *S; ++S) W += Advance(*S);
		return W * Height;
	}

	/** STATUS, as SaudHud lays it, out to the end of its glow. */
	inline float StatusRight(const FPage& P) { return P.Left() + P.Px(SaudHud::WindowInset + SaudHud::PlayerW + SaudHud::WindowInset); }
	inline float StatusBottom(const FPage& P) { return P.Top() + P.Px(SaudHud::WindowInset + SaudHud::PlayerH + SaudHud::WindowInset); }
	/** Where the left column ends: the fight's box, less a window's glow. */
	inline float ColumnRight(const FPage& P) { return FightX0 * P.ScreenW - P.Px(SaudHud::WindowInset) - 1.f; }
	/** The top band's floor: the fight's box, less a window's glow. */
	inline float BandBottom(const FPage& P) { return FightY0 * P.ScreenH - P.Px(SaudHud::WindowInset) - 1.f; }

	inline float WindowHeight(const FPage& P, const FLines& L)
	{
		const bool bRow1 = !Empty(L.Head) || !Empty(L.Reward);
		const bool bRow2 = !Empty(L.Body) || !Empty(L.Beneath) || !Empty(L.Status);
		if (!bRow1 && !bRow2) return P.Px(SaudHud::HeadH + BareBottom);
		float H = SaudHud::HeadH + TopPad + BottomPad;
		if (bRow1) H += HeadText;
		if (bRow2) H += (bRow1 ? RowGap : 0.f) + (!Empty(L.Body) ? BodyText : LineText);
		return P.Px(H);
	}

	/** What a window's words need across, page px scaled. */
	inline float WindowContentW(const FPage& P, const FLines& L)
	{
		const float Pad = P.Px(PadPx);
		float W = TextWidth(L.Title, P.Px(TitleText));
		float Row1 = TextWidth(L.Head, P.Px(HeadText));
		if (!Empty(L.Reward)) Row1 += (Empty(L.Head) ? 0.f : P.Px(RowSep)) + TextWidth(L.Reward, P.Px(RewardText));
		W = FMath::Max(W, Row1);
		W = FMath::Max(W, TextWidth(L.Body, P.Px(BodyText)));
		float Row2b = TextWidth(L.Beneath, P.Px(LineText));
		if (!Empty(L.Status)) Row2b += (Empty(L.Beneath) ? 0.f : P.Px(RowSep)) + TextWidth(L.Status, P.Px(LineText));
		W = FMath::Max(W, Row2b);
		return W + 2.f * Pad;
	}

	/** The window: in the top band, right of STATUS, as near the middle as
	    it can stand. bFits false when its words need more than the band. */
	inline FRect WindowRect(const FPage& P, const FLines& L, bool* bFits = nullptr)
	{
		const float Inset = P.Px(SaudHud::WindowInset);
		const float Clear = StatusRight(P) + P.Px(GapPx) + Inset;
		const float RightLimit = P.Right() - Inset;
		const float Avail = RightLimit - Clear;
		const float Need = WindowContentW(P, L);
		const float W = FMath::Min(FMath::Clamp(Need, P.Px(WindowMinW), P.Px(WindowMaxW)), Avail);
		float X = FMath::Max(Clear, 0.5f * P.ScreenW - 0.5f * W);
		if (X + W > RightLimit) X = RightLimit - W;
		const float Y = P.Top() + Inset;
		const float H = WindowHeight(P, L);
		if (bFits) *bFits = Need <= Avail + 0.5f && Y + H <= BandBottom(P) + 0.5f;
		return {X, Y, W, H};
	}

	inline float QuestHeight(const FPage& P) { return P.Px(SaudHud::HeadH + 6.f + LineText + RowGap + LineText + BottomPad); }
	inline float ToastHeight(const FPage& P) { return P.Px(SaudHud::HeadH + 6.f + LineText + BottomPad); }

	inline float SideWidth(const FPage& P, float Need, bool* bFits)
	{
		const float X = P.Left() + P.Px(SaudHud::WindowInset);
		const float Avail = ColumnRight(P) - X;
		if (bFits) *bFits = Need <= Avail + 0.5f;
		return FMath::Min(FMath::Max(Need, P.Px(SideMinW)), Avail);
	}

	/** The open quest: the left column, under STATUS. */
	inline FRect QuestRect(const FPage& P, const FLines& Q, bool* bFits = nullptr)
	{
		const float Need = FMath::Max(TextWidth(Q.Title, P.Px(TitleText)),
		                              FMath::Max(TextWidth(Q.Head, P.Px(LineText)), TextWidth(Q.Status, P.Px(LineText))))
		                 + 2.f * P.Px(PadPx);
		const float W = SideWidth(P, Need, bFits);
		return {P.Left() + P.Px(SaudHud::WindowInset), StatusBottom(P) + P.Px(GapPx) + P.Px(SaudHud::WindowInset), W, QuestHeight(P)};
	}

	/** The toast: the left column, under the open quest (under STATUS when
	    the quest is not shown). */
	inline FRect ToastRect(const FPage& P, const FLines& T, bool bUnderQuest, bool* bFits = nullptr)
	{
		const float Need = FMath::Max(TextWidth(T.Title, P.Px(TitleText)),
		                              FMath::Max(TextWidth(T.Body, P.Px(LineText)), TextWidth(T.Reward, P.Px(LineText))))
		                 + 2.f * P.Px(PadPx);
		const float W = SideWidth(P, Need, bFits);
		const float Inset = P.Px(SaudHud::WindowInset), Gap = P.Px(GapPx);
		const float Y = bUnderQuest ? StatusBottom(P) + Gap + Inset + QuestHeight(P) + Inset + Gap + Inset
		                            : StatusBottom(P) + Gap + Inset;
		return {P.Left() + Inset, Y, W, ToastHeight(P)};
	}

	// ----------------------------------------------------------- the drawing
	enum class EPiece : unsigned char { Window, Toast, Quest };
	constexpr int NumPieces = 3;
	enum class EAlign : unsigned char { Left, Centre, Right };
	/** Which line of its window a text is: the harness holds each to its
	    contrast (a heading 4.5:1 against the ink, the rest 7:1). */
	enum class ESlot : unsigned char { Title, Head, Body, Reward, Beneath, Status };

	struct FSysText
	{
		const char* S = nullptr;    // the model's words: valid while the model is
		ESlot Slot = ESlot::Body;
		FPoint At;                  // top left; top centre; top RIGHT for Right
		float Height = 0.f;         // screen px, the line height
		FRgba Colour;
		float Stroke = 0.f;
		EAlign Align = EAlign::Left;
		EPiece Piece = EPiece::Window;
		int TrisBefore = 0;         // drawn after this many triangles
	};

	constexpr int MaxSysTexts = 16;

	struct FSysList
	{
		SaudHud::FDrawList Shapes;  // the triangles, in SaudHud's own list
		FSysText Texts[MaxSysTexts];
		int NumTexts = 0;
		bool bOverflow = false;
		/** Each piece: drawn or not, its panel as laid out (full open),
		    its triangles [From, To). */
		bool bOn[NumPieces] = {};
		FRect Box[NumPieces];
		int From[NumPieces] = {}, To[NumPieces] = {};

		void Reset()
		{
			Shapes.Reset();
			NumTexts = 0;
			bOverflow = false;
			for (int i = 0; i < NumPieces; ++i) { bOn[i] = false; Box[i] = FRect(); From[i] = To[i] = 0; }
		}
		void Text(const char* S, ESlot Slot, const FPoint& At, float Height, const FRgba& C, float Stroke, EAlign Align, EPiece Piece)
		{
			if (Empty(S)) return;
			if (NumTexts >= MaxSysTexts) { bOverflow = true; return; }
			FSysText& T = Texts[NumTexts++];
			T.S = S; T.Slot = Slot; T.At = At; T.Height = Height; T.Colour = C; T.Stroke = Stroke; T.Align = Align;
			T.Piece = Piece; T.TrisBefore = Shapes.NumTris;
		}
	};

	inline FRgba EdgeColour(ETint T)
	{
		return T == ETint::Danger ? SaudHud::Colour::Danger : (T == ETint::Shadow ? SaudHud::Colour::Shadow : SaudHud::Colour::System);
	}
	/** A heading in its window's colour -- violet lifted halfway to ice,
	    since the violet itself is 4.4:1 on the ink and a heading needs 4.5. */
	inline FRgba TitleColour(ETint T)
	{
		return T == ETint::Shadow ? SaudHud::LerpColour(SaudHud::Colour::Shadow, SaudHud::Colour::Ice, 0.5f) : EdgeColour(T);
	}
	/** A reward or a status: the System's cyan; ice in a crimson window
	    (crimson is a heading's colour, not a line's: 5.6:1). */
	inline FRgba RewardColour(ETint T)
	{
		return T == ETint::Danger ? SaudHud::Colour::Ice : SaudHud::Colour::System;
	}

	inline void FadeTris(SaudHud::FDrawList& L, int From, int To, float Fade)
	{
		for (int t = From; t < To; ++t)
			for (SaudHud::FHudVert& V : L.Tris[t].V) V.C.A *= Fade;
	}

	/** One window: SaudHud's window wiping open, its words once it is open,
	    all of it fading as it closes. */
	inline void DrawWindow(FSysList& Out, const FPage& P, const FShown& S, const FRect& Full, EPiece Piece)
	{
		const int I = static_cast<int>(Piece);
		const float Fade = S.Fade();
		const FRect R = {Full.X, Full.Y, Full.W * S.OpenFraction(), Full.H};
		const ETint Tint = S.E.Tint;
		Out.bOn[I] = true;
		Out.Box[I] = Full;
		Out.From[I] = Out.Shapes.NumTris;
		SaudHud::Window(Out.Shapes, P, R, EdgeColour(Tint), 1.f, SaudHud::EHudGroup::Combo);
		FadeTris(Out.Shapes, Out.From[I], Out.Shapes.NumTris, Fade);
		Out.To[I] = Out.Shapes.NumTris;
		if (!S.TextShown()) return;
		const float Pad = P.Px(PadPx), Stroke = P.Px(SaudHud::TextStroke), Head = P.Px(SaudHud::HeadH);
		const FLines& L = S.Text;
		auto A = [Fade](FRgba C) { C.A *= Fade; return C; };
		const FRgba Ice = A(SaudHud::Colour::Ice), Title = A(TitleColour(Tint)), Reward = A(RewardColour(Tint));
		const bool bToast = Piece == EPiece::Toast;
		Out.Text(L.Title, ESlot::Title, {R.X + Pad, R.Y + 0.5f * (Head - P.Px(TitleText))}, P.Px(TitleText), Title, Stroke,
		         EAlign::Left, Piece);
		float Y = R.Y + Head + P.Px(bToast ? 6.f : TopPad);
		if (bToast)
		{
			// one line: what the gate gave, or that it is open
			Out.Text(!Empty(L.Body) ? L.Body : L.Reward, !Empty(L.Body) ? ESlot::Body : ESlot::Reward, {R.X + Pad, Y},
			         P.Px(LineText), Empty(L.Body) ? Reward : Ice, Stroke, EAlign::Left, Piece);
			return;
		}
		if (!Empty(L.Head) || !Empty(L.Reward))
		{
			Out.Text(L.Head, ESlot::Head, {R.X + Pad, Y}, P.Px(HeadText), Ice, Stroke, EAlign::Left, Piece);
			Out.Text(L.Reward, ESlot::Reward, {R.X + R.W - Pad, Y + P.Px(HeadText - RewardText)}, P.Px(RewardText), Reward,
			         Stroke, EAlign::Right, Piece);
			Y += P.Px(HeadText + RowGap);
		}
		if (!Empty(L.Body))
		{
			Out.Text(L.Body, ESlot::Body, {R.X + Pad, Y}, P.Px(BodyText), Ice, Stroke, EAlign::Left, Piece);
		}
		else
		{
			// the open quest, beneath, still in progress
			Out.Text(L.Beneath, ESlot::Beneath, {R.X + Pad, Y}, P.Px(LineText), Ice, Stroke, EAlign::Left, Piece);
			Out.Text(L.Status, ESlot::Status, {R.X + R.W - Pad, Y}, P.Px(LineText), Reward, Stroke, EAlign::Right, Piece);
		}
	}

	/** The open quest's line: QUEST, FIND THE WAY UP, IN PROGRESS. */
	inline void DrawQuest(FSysList& Out, const FPage& P, const FModel& M, const FRect& R)
	{
		const int I = static_cast<int>(EPiece::Quest);
		const float Fade = M.QuestShow;
		Out.bOn[I] = true;
		Out.Box[I] = R;
		Out.From[I] = Out.Shapes.NumTris;
		SaudHud::Window(Out.Shapes, P, R, SaudHud::Colour::System, 1.f, SaudHud::EHudGroup::Combo);
		FadeTris(Out.Shapes, Out.From[I], Out.Shapes.NumTris, Fade);
		Out.To[I] = Out.Shapes.NumTris;
		const float Pad = P.Px(PadPx), Stroke = P.Px(SaudHud::TextStroke), Head = P.Px(SaudHud::HeadH);
		FRgba Cy = SaudHud::Colour::System, Ice = SaudHud::Colour::Ice;
		Cy.A *= Fade;
		Ice.A *= Fade;
		Out.Text(M.Quest.Title, ESlot::Title, {R.X + Pad, R.Y + 0.5f * (Head - P.Px(TitleText))}, P.Px(TitleText), Cy, Stroke,
		         EAlign::Left, EPiece::Quest);
		const float Y = R.Y + Head + P.Px(6.f);
		Out.Text(M.Quest.Head, ESlot::Head, {R.X + Pad, Y}, P.Px(LineText), Ice, Stroke, EAlign::Left, EPiece::Quest);
		Out.Text(M.Quest.Status, ESlot::Status, {R.X + Pad, Y + P.Px(LineText + RowGap)}, P.Px(LineText), Cy, Stroke,
		         EAlign::Left, EPiece::Quest);
	}

	/** Everything the System shows this frame, over the HUD. Pure: the
	    same model and page give the same list. */
	inline void Build(const FPage& P, const FModel& M, FSysList& Out)
	{
		Out.Reset();
		const bool bQuest = M.QuestShow > 0.f && !Empty(M.Quest.Head);
		if (bQuest)
		{
			DrawQuest(Out, P, M, QuestRect(P, M.Quest));
		}
		if (M.Toast.bOn)
		{
			DrawWindow(Out, P, M.Toast, ToastRect(P, M.Toast.Text, bQuest), EPiece::Toast);
		}
		if (M.Window.bOn)
		{
			DrawWindow(Out, P, M.Window, WindowRect(P, M.Window.Text), EPiece::Window);
		}
		Out.bOverflow = Out.bOverflow || Out.Shapes.bOverflow;
	}
}
