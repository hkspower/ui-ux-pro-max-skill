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
 * The look is the System's (2026-10-03; the dark seinen's ink and blood
 * before), with the HUD's palette only: "SAUD" in Ice with the System's
 * cyan bar under it, "KUWAIT FIGHTER" small and dim; the items as square
 * plates -- the focused one the panel's navy lit toward the System's cyan,
 * with its label in Ice and a cyan keyline, breathing slowly on the
 * real-time clock; the others the panel's navy in a dim cyan keyline with
 * a dim label; a navy window with a cyan line along its top behind the
 * column; the pause the same column over a navy scrim.
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
 * The dim text is Ice at DimAlpha, which composites over the plates to a
 * grey-blue and keeps the 7:1 against its Ink stroke the harness holds (it
 * also holds the alpha at or over 0.5).
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
 *   -- since 2026-10-07 (the System, deeper: the status and training
 *      screens). These spell themselves: Spell() below is the string for
 *      EVERY slot but ControlsText, and the engine draws what it returns
 *      for any slot SpellsItself() names (the new ones, the Confirm's
 *      third question, and the hint that names a track):
 *   Status / Training -   "STATUS" / "TRAINING"   (Pause items; Status's TRAINING)
 *   StatusHead       -    "STATUS"                (the heading)
 *   TrainingHead     -    "TRAINING"
 *   TrackName        t    "BOXING" "KICKING" "VITALITY" "SPEED" "STAMINA" "IRON ARM"
 *   CostTag          c    "c XP"; -1 "MAX"        (a track's next level, right on its plate)
 *   SpendXp          x    "XP TO SPEND  x"        (under the Training's bar)
 *   WinName          -    "SAUD"                  (the status window's heading strip)
 *   LevelLine        n    "LEVEL n"
 *   RankTitle        r    "ROOKIE" .. "CHAMPION"  (the Halqa's ladder, Ladder::RankOf)
 *   XpLabel          -    "XP"
 *   XpLine           e/n  "e / n XP"; n 0: "e XP" (earned, and where the next level is)
 *   XpToNext         d/n  "d TO LEVEL n"; n 0: "MAX LEVEL"
 *   StatHp/Mp/Stamina v   "HP v" / "MP v" / "STAMINA v"
 *   Section          s    "SKILLS" / "TRAINING" / "QUEST"
 *   SkillName        k/a  aux 1: "VAULT" "DASH LEAP" "POWER KICK" "HAYMAKER" "HAWK FIST"; aux 0: "?"
 *   QuestName        0/1  "FIND THE WAY UP" / "--"  (removed after the title fight)
 *   QuestState       -    "IN PROGRESS"
 *   AskHead          2    "TRAIN?"; ConfirmNo 2 "NO, KEEP MY XP"; ConfirmYes 2 "YES, TRAIN"
 *   Hint AskTrain    aux  "TRAIN <TRACK> TO LEVEL n" (aux = track * 10 + n)
 *
 * Chars() below carries each string's length so the layout can estimate a
 * label's width (CharAdvance of its height per character) and the harness
 * can hold that no label runs off its plate and no two prompts touch. It is
 * Spell()'s own length (2026-10-07; a table of counts until then).
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

	// ------------------------------------------- the game's numbers (2026-10-07)
	/** The six upgrade tracks, as the game buys them: the browser's
	    assets/upgrades.js (cost(lvl) = 120 + 130 lvl, maxLevel 5), exported
	    to Content/Data/DT_Upgrades.csv -- whose Track column is the id
	    (Box, Kick, Vit, Spd, Stam, Iron). USaudGameInstance::
	    TryPurchaseUpgrade and GetUpgradeCost go through this table, and the
	    harness holds it to the CSV row by row. */
	namespace Train
	{
		constexpr int Tracks = 6;
		constexpr int MaxLevel = 5;
		/** XP for the level after Level. */
		inline int Cost(int Level) { return 120 + 130 * Level; }
		/** Everything spent on a track to stand at Level. */
		inline int Spent(int Level)
		{
			int S = 0;
			for (int l = 0; l < Level; ++l) S += Cost(l);
			return S;
		}
		/** DT_Upgrades' own Track ids, in the order the shop shows them. */
		inline const char* Id(int T)
		{
			static const char* const Ids[Tracks] = {"Box", "Kick", "Vit", "Spd", "Stam", "Iron"};
			return T >= 0 && T < Tracks ? Ids[T] : "";
		}
		/** The long spellings TryPurchaseUpgrade expected before 2026-10-07,
		    still taken from anything that already sends them. */
		inline const char* LongId(int T)
		{
			static const char* const Ids[Tracks] = {"Boxing", "Kicking", "Vitality", "Speed", "Stamina", "IronArm"};
			return T >= 0 && T < Tracks ? Ids[T] : "";
		}
		inline bool Same(const char* A, const char* B)
		{
			if (!A || !B) return false;
			while (*A && *A == *B) { ++A; ++B; }
			return *A == 0 && *B == 0;
		}
		/** A track id (the table's, or the old long one) to its track, or -1. */
		inline int TrackOf(const char* Name)
		{
			for (int T = 0; T < Tracks; ++T)
			{
				if (Same(Name, Id(T)) || Same(Name, LongId(T))) return T;
			}
			return -1;
		}
		inline const char* Name(int T)
		{
			static const char* const Names[Tracks] = {"BOXING", "KICKING", "VITALITY", "SPEED", "STAMINA", "IRON ARM"};
			return T >= 0 && T < Tracks ? Names[T] : "";
		}
	}

	/** The Halqa's ladder: the browser's assets/levels.js (need(n) =
	    round(18 (n-1) + 3.1 (n-1)^2), max 20, the titles at 3, 6, 10, 14,
	    18), exported to DT_Levels.csv and held to it by the harness. The
	    level is driven by EARNED experience -- what training draws down is
	    the spendable (levels.js: "spending on upgrades never costs you a
	    level") -- and the Unreal save keeps only the spendable, so the
	    earned is the spendable plus what the six tracks have cost
	    (USaudGameInstance::GetEarnedExperience): training is the one thing
	    XP is spent on. */
	namespace Ladder
	{
		constexpr int MaxLevel = 20;
		constexpr int Ranks = 6;
		/** Earned XP to stand at Level (integer: 18n + 3.1n^2 rounded half up). */
		inline int Need(int Level)
		{
			if (Level <= 1) return 0;
			const int N = Level - 1;
			return (180 * N + 31 * N * N + 5) / 10;
		}
		inline int LevelOf(int Earned)
		{
			int L = 1;
			while (L < MaxLevel && Earned >= Need(L + 1)) ++L;
			return L;
		}
		/** 0 ROOKIE, 1 AMATEUR, 2 PROSPECT, 3 RANKED, 4 CONTENDER, 5 CHAMPION. */
		inline int RankOf(int Level)
		{
			if (Level >= 18) return 5;
			if (Level >= 14) return 4;
			if (Level >= 10) return 3;
			if (Level >= 6) return 2;
			if (Level >= 3) return 1;
			return 0;
		}
		inline const char* RankName(int R)
		{
			static const char* const Names[Ranks] = {"ROOKIE", "AMATEUR", "PROSPECT", "RANKED", "CONTENDER", "CHAMPION"};
			return R >= 0 && R < Ranks ? Names[R] : "";
		}
	}

	/** What the game makes of his upgrades and his level, as ASaudCharacter::
	    ApplyUpgrades does it (Player.json's numbers; MP's base is SaudFire::
	    MaxMana): the status window shows these. The level's own bonus is
	    levels.js's perLevel (hp 6, mp 4 a level past the first), as the
	    browser's makePlayer() adds it -- DT_Levels' BonusHealth / BonusMana,
	    held to it by the harness -- so the System's "LEVEL UP ... HP +6.
	    MP +4." is true (2026-10-07). */
	namespace Stats
	{
		constexpr int BaseHealth = 100, HealthPerVitality = 18;
		constexpr int BaseStamina = 100, StaminaPerLevel = 12;
		constexpr int BaseMana = 40;
		constexpr int HealthPerRung = 6, ManaPerRung = 4;
		/** What the level adds, on top of the base and the training. */
		inline int LevelHealth(int Level) { return HealthPerRung * (Level > 1 ? Level - 1 : 0); }
		inline int LevelMana(int Level) { return ManaPerRung * (Level > 1 ? Level - 1 : 0); }
	}

	/** The five talents, in EAbility's order (Vault = 1 .. HawkFist = 5). */
	constexpr int Skills = 5;
	inline const char* SkillName(int K)
	{
		static const char* const Names[Skills] = {"VAULT", "DASH LEAP", "POWER KICK", "HAYMAKER", "HAWK FIST"};
		return K >= 0 && K < Skills ? Names[K] : "";
	}
	constexpr int HawkFistSkill = 4;   // the one that was not his: violet

	/** Everything the status window and the training show, from the save
	    (USaudMenuSubsystem::ReadStatus fills it; MakeStatus works out the
	    rest). */
	struct FStatus
	{
		int Spendable = 0;              // FSaudProgress::Experience: what training draws down
		int Earned = 0;                 // spendable + what training has cost: drives the level
		int Level = 1;
		int Rank = 0;
		int LevelFloor = 0;             // Ladder::Need(Level)
		int LevelNext = 0;              // Ladder::Need(Level + 1); 0 at the top
		int MaxHealth = Stats::BaseHealth;
		int MaxMana = Stats::BaseMana;
		int MaxStamina = Stats::BaseStamina;
		int Track[Train::Tracks] = {};
		bool Skill[Skills] = {};
		/** FIND THE WAY UP: open from the first landing until AL-WAHSH is
		    beaten (the System: QUEST REMOVED, no longer required). */
		bool bQuestOpen = true;
	};
	/** The derived half of a status from its spendable XP and track levels. */
	inline void Restat(FStatus& S)
	{
		int Spent = 0;
		for (int T = 0; T < Train::Tracks; ++T)
		{
			S.Track[T] = S.Track[T] < 0 ? 0 : (S.Track[T] > Train::MaxLevel ? Train::MaxLevel : S.Track[T]);
			Spent += Train::Spent(S.Track[T]);
		}
		S.Spendable = S.Spendable < 0 ? 0 : S.Spendable;
		S.Earned = S.Spendable + Spent;
		S.Level = Ladder::LevelOf(S.Earned);
		S.Rank = Ladder::RankOf(S.Level);
		S.LevelFloor = Ladder::Need(S.Level);
		S.LevelNext = S.Level < Ladder::MaxLevel ? Ladder::Need(S.Level + 1) : 0;
		S.MaxHealth = Stats::BaseHealth + Stats::HealthPerVitality * S.Track[2] + Stats::LevelHealth(S.Level);
		S.MaxStamina = Stats::BaseStamina + Stats::StaminaPerLevel * S.Track[4];
		S.MaxMana = Stats::BaseMana + Stats::LevelMana(S.Level);
	}
	inline FStatus MakeStatus(int Spendable, const int Track[Train::Tracks], const bool Skill[Skills], bool bWonTitle)
	{
		FStatus S;
		S.Spendable = Spendable;
		for (int T = 0; T < Train::Tracks; ++T) S.Track[T] = Track[T];
		for (int K = 0; K < Skills; ++K) S.Skill[K] = Skill[K];
		S.bQuestOpen = !bWonTitle;
		Restat(S);
		return S;
	}

	// ------------------------------------------------------------- the model
	/** Confirm (2026-10-02): "are you sure?" before QUIT and before a NEW
	    GAME over a save, opened from the Title like Settings is. Status and
	    Training (2026-10-07): the System's status window and its store,
	    opened from the Pause (Training also from the Status). */
	enum class EScreen : unsigned char { Title, Pause, Settings, Controls, Confirm, Status, Training };

	/** What a Confirm asks. Train: a level of the track M.TrainTrack. */
	enum class EAsk : unsigned char { Quit, NewGame, Train };

	/** Every item any screen can show. */
	enum class EItem : unsigned char
	{
		Continue, Fight, Controls, Settings, Quit,     // Title: CONTINUE|FIGHT, CONTROLS, SETTINGS, QUIT
		Resume, QuitToTitle,                           // Pause: RESUME, STATUS, TRAINING, CONTROLS, SETTINGS, QUIT TO TITLE
		Difficulty, Sound, Music, Vibration, Back,     // Settings: the four, BACK; Controls: BACK
		NewGame,                                       // Title, under CONTINUE, when a save exists
		ConfirmNo, ConfirmYes,                         // Confirm: NO first, so a stray press is safe
		Status, Training,                              // 2026-10-07: the Pause's; Status: TRAINING, BACK
		TrainBox, TrainKick, TrainVit, TrainSpd, TrainStam, TrainIron,   // Training: the six, BACK
		Count
	};
	constexpr int MaxItems = 7;
	/** A Training item's track (0..5), or -1. */
	inline int TrackOfItem(EItem I)
	{
		const int K = static_cast<int>(I) - static_cast<int>(EItem::TrainBox);
		return K >= 0 && K < Train::Tracks ? K : -1;
	}

	/** What the engine must do after Navigate. Tap, Back and Denied are the
	    UI sounds (UI_Tap, UI_Back, UI_Denied); the toggles and the cycle say
	    the model's setting changed and must be saved; the rest are the
	    flow. There is no Restart (the browser's RESTART STAGE is not here). */
	enum class EMenuEffect : unsigned char
	{
		None, StartGame, Resume, QuitToTitle, QuitGame,
		SetSound, SetMusic, ToggleVibration, CycleDifficulty,
		Tap, Back, Denied,
		NewGame,         // the save is replaced and the first fight starts (confirmed)
		Train            // a level of M.TrainTrack bought (confirmed): the engine's TryPurchaseUpgrade
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
	/** (2026-10-07: 0.08 and 0.30 until the Training's seven plates, which
	    at those would still be sliding at 0.68 s.) */
	constexpr float PlateDelay = 0.05f, PlateStagger = 0.05f, PlateArrive = 0.24f;
	constexpr float EnterSeconds = 0.60f;
	/** A denied buy: the plate's keyline crimson and the hint saying why,
	    this long (real seconds), or until the focus moves. */
	constexpr float DeniedSeconds = 1.2f;

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
		// -- 2026-10-07: the status and the training
		/** The screen Open was called with (Title or Pause): the scrim. */
		EScreen Root = EScreen::Title;
		/** The returns under ReturnTo, deepest last: Pause > Status >
		    Training > Confirm is three deep. */
		static constexpr int MaxDepth = 4;
		EScreen OuterTo[MaxDepth] = {};
		int OuterFocus[MaxDepth] = {};
		int Depth = 0;
		/** The save, as the status window and the training show it. */
		FStatus Status;
		/** The track a Train Confirm asks about, and that Train bought. */
		int TrainTrack = -1;
		/** A denied buy: on which item, for how long more, and why. */
		int DeniedItem = -1;
		float DeniedLeft = 0.f;
		bool bDeniedMaxed = false;
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
			Out[1] = EItem::Status;       // 2026-10-07
			Out[2] = EItem::Training;     // 2026-10-07
			Out[3] = EItem::Controls;
			Out[4] = EItem::Settings;
			Out[5] = EItem::QuitToTitle;
			return 6;
		case EScreen::Status:
			Out[0] = EItem::Training;
			Out[1] = EItem::Back;
			return 2;
		case EScreen::Training:
			for (int T = 0; T < Train::Tracks; ++T)
			{
				Out[T] = static_cast<EItem>(static_cast<int>(EItem::TrainBox) + T);
			}
			Out[Train::Tracks] = EItem::Back;
			return Train::Tracks + 1;
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
		M.Root = S;
		M.Depth = 0;
		M.DeniedItem = -1;
		M.DeniedLeft = 0.f;
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
		M.DeniedLeft = FMath::Max(0.f, M.DeniedLeft - Dt);
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
			// what this screen itself goes back to is kept under it (a
			// Training opened from the Status still goes back to the Pause)
			if (M.Screen != M.Root && M.Depth < FMenuModel::MaxDepth)
			{
				M.OuterTo[M.Depth] = M.ReturnTo;
				M.OuterFocus[M.Depth] = M.ReturnFocus;
				++M.Depth;
			}
			M.ReturnTo = M.Screen;
			M.ReturnFocus = M.Focus;
			M.Screen = S;
			M.Focus = 0;
			M.Since = 0.f;
			M.FocusFrom = 0.f;
			M.FocusT = 1.f;
			M.DeniedLeft = 0.f;
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
			if (M.Depth > 0)
			{
				--M.Depth;
				M.ReturnTo = M.OuterTo[M.Depth];
				M.ReturnFocus = M.OuterFocus[M.Depth];
			}
			M.Since = 0.f;
			M.FocusFrom = static_cast<float>(M.Focus);
			M.FocusT = 1.f;
			M.DeniedLeft = 0.f;
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
			M.DeniedLeft = 0.f;   // a denial is about the item it was on
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
		/** A buy that cannot be: the plate's keyline crimson and the hint
		    saying why, for DeniedSeconds. */
		inline EMenuEffect Deny(FMenuModel& M, int Item, bool bMaxed)
		{
			M.DeniedItem = Item;
			M.DeniedLeft = DeniedSeconds;
			M.bDeniedMaxed = bMaxed;
			return EMenuEffect::Denied;
		}
		/** Confirm on a Training track: asked first when it can be bought,
		    Denied when it is at its top or the XP is short. */
		inline EMenuEffect AskTrain(FMenuModel& M, int T)
		{
			const int L = M.Status.Track[T];
			if (L >= Train::MaxLevel) return Deny(M, M.Focus, true);
			if (M.Status.Spendable < Train::Cost(L)) return Deny(M, M.Focus, false);
			M.TrainTrack = T;
			OpenAsk(M, EAsk::Train);
			return EMenuEffect::Tap;
		}
		/** YES on the Train Confirm: back on the Training, on the track,
		    the level bought in the model (the cost off the spendable, the
		    track up one, the status worked out again: the level, which
		    the earned drives, does not move). The engine buys it in the
		    save on Train and reads the save back. */
		inline EMenuEffect Buy(FMenuModel& M)
		{
			const int T = M.TrainTrack;
			Return(M);
			if (T < 0 || T >= Train::Tracks) return EMenuEffect::Denied;
			FStatus& S = M.Status;
			const int L = S.Track[T];
			if (L >= Train::MaxLevel) return Deny(M, M.Focus, true);
			if (S.Spendable < Train::Cost(L)) return Deny(M, M.Focus, false);
			S.Spendable -= Train::Cost(L);
			++S.Track[T];
			Restat(S);
			return EMenuEffect::Train;
		}
		inline EMenuEffect Activate(FMenuModel& M, EItem I)
		{
			if (TrackOfItem(I) >= 0)
			{
				return AskTrain(M, TrackOfItem(I));
			}
			switch (I)
			{
			case EItem::Status:
				OpenSub(M, EScreen::Status);
				return EMenuEffect::Tap;
			case EItem::Training:
				OpenSub(M, EScreen::Training);
				return EMenuEffect::Tap;
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
				if (M.Ask == EAsk::Train) return Buy(M);
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
			case EScreen::Status:
			case EScreen::Training:
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
	enum class EMenuPart : unsigned char
	{
		Scrim, Wash, Slash, Keyline, Plate, Glyph, Diagram, Meter,
		// 2026-10-07: the status window -- its glow, panel, heading strip and
		// edge, its corner marks -- and the marks in it (a skill's slot, a
		// rule, the XP bar's trough and fill; a crimson rule under a cost
		// the XP will not cover)
		Glow, Window, Edge, Bracket, Mark, Bar
	};

	enum class EMenuText : unsigned char
	{
		Saud, Subtitle, Paused, SettingsHead,
		Continue, Fight, Controls, Settings, Quit, Resume, QuitToTitle,
		Difficulty, Sound, Music, Vibration, Back,
		PromptSelect, PromptBack, PromptAdjust, PromptFlip,
		KeySelect, KeyBack, KeyAdjust, KeyFlip,
		ControlsText,
		// 2026-10-02
		NewGame, AskHead, ConfirmNo, ConfirmYes, StageTag, PromptQuit, KeyQuit, Hint,
		// 2026-10-07: the status and the training (they spell themselves)
		Status, Training, StatusHead, TrainingHead, TrackName, CostTag, SpendXp,
		WinName, LevelLine, RankTitle, XpLabel, XpLine, XpToNext, StatHp, StatMp, StatStamina,
		Section, SkillName, QuestName, QuestState
	};

	/** What the hint line under the column says (EMenuText::Hint's value). */
	enum class EHint : unsigned char
	{
		Continue, Fight, NewGame, Controls, Settings, Quit, Resume, QuitToTitle,
		Difficulty, Sound, Music, Vibration, BackTitle, BackPause, AskQuit, AskNewGame,
		// 2026-10-07
		Status, Training, BackStatus, TrainBox, TrainKick, TrainVit, TrainSpd, TrainStam, TrainIron,
		Poor, Maxed, AskTrain,
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
		case EHint::Status: return "YOUR LEVEL, SKILLS AND QUEST";
		case EHint::Training: return "SPEND XP ON THE SIX TRACKS";
		case EHint::BackStatus: return "BACK TO THE STATUS";
		// the tracks: DT_Upgrades' descriptions, in the game's own numbers
		// (SPEED's "+9" is the browser's pixels, and the game gives more:
		// IRON ARM's "Found on the way, not touched" -- so no number)
		case EHint::TrainBox: return "+10% JAB, CROSS AND HOOK DAMAGE";
		case EHint::TrainKick: return "+10% KICK, KNEE AND RAGE DAMAGE";
		case EHint::TrainVit: return "+18 MAX HEALTH A LEVEL";
		case EHint::TrainSpd: return "QUICKER ON YOUR FEET";
		case EHint::TrainStam: return "+12 MAX STAMINA A LEVEL";
		case EHint::TrainIron: return "-12% BLOCK STAMINA AND PUSH A LEVEL";
		case EHint::Poor: return "NOT ENOUGH XP";
		case EHint::Maxed: return "FULLY TRAINED";
		case EHint::AskTrain: return "TRAIN";   // + the track and the level: Spell
		default: return "";
		}
	}
	inline int Digits(int V) { int D = 1; while (V >= 10) { V /= 10; ++D; } return D; }

	/** A string spelled into a fixed buffer: no allocation, no stdio, so
	    the engine and the harness run the same code. */
	struct FSpelled
	{
		char S[64] = {};
		int N = 0;
		FSpelled& Add(const char* T)
		{
			while (T && *T && N < 63) S[N++] = *T++;
			S[N] = 0;
			return *this;
		}
		FSpelled& Num(int V)
		{
			char D[12];
			int K = 0;
			unsigned U = V < 0 ? static_cast<unsigned>(-V) : static_cast<unsigned>(V);
			do { D[K++] = static_cast<char>('0' + U % 10u); U /= 10u; } while (U && K < 12);
			if (V < 0 && N < 63) S[N++] = '-';
			while (K > 0 && N < 63) S[N++] = D[--K];
			S[N] = 0;
			return *this;
		}
	};

	/** The string the engine draws for a slot, value and aux -- every slot
	    but ControlsText (SaudControls' own table). The menu's one table:
	    Chars() is its length, Tools/harness/menu_dump.cpp prints it, and
	    SaudHUD.cpp draws it for the slots SpellsItself() names. ASCII. */
	inline FSpelled Spell(EMenuText Slot, int Value, int Aux = 0)
	{
		FSpelled O;
		switch (Slot)
		{
		case EMenuText::Saud: return O.Add("SAUD");
		case EMenuText::Subtitle: return O.Add("KUWAIT FIGHTER");
		case EMenuText::Paused: return O.Add("PAUSED");
		case EMenuText::SettingsHead: return O.Add("SETTINGS");
		case EMenuText::Continue: return O.Add("CONTINUE");
		case EMenuText::Fight: return O.Add("FIGHT");
		case EMenuText::Controls: return O.Add("CONTROLS");
		case EMenuText::Settings: return O.Add("SETTINGS");
		case EMenuText::Quit: return O.Add("QUIT");
		case EMenuText::Resume: return O.Add("RESUME");
		case EMenuText::QuitToTitle: return O.Add("QUIT TO TITLE");
		case EMenuText::Difficulty:
			return O.Add(Value == 0 ? "DIFFICULTY  ROOKIE" : (Value == 1 ? "DIFFICULTY  PRO" : "DIFFICULTY  CHAMPION"));
		case EMenuText::Sound: return Value <= 0 ? O.Add("SOUND  OFF") : O.Add("SOUND  ").Num(Value);
		case EMenuText::Music: return Value <= 0 ? O.Add("MUSIC  OFF") : O.Add("MUSIC  ").Num(Value);
		case EMenuText::Vibration: return O.Add(Value ? "VIBRATION  ON" : "VIBRATION  OFF");
		case EMenuText::Back: return O.Add("BACK");
		case EMenuText::PromptSelect: return O.Add("SELECT");
		case EMenuText::PromptBack: return O.Add("BACK");
		case EMenuText::PromptAdjust: return O.Add("ADJUST");
		case EMenuText::PromptFlip: return O.Add(Value ? "SHOW PS5" : "SHOW XBOX");
		case EMenuText::KeySelect: return O.Add("ENTER  SELECT");
		case EMenuText::KeyBack: return O.Add("ESC  BACK");
		case EMenuText::KeyAdjust: return O.Add("ARROWS  ADJUST");
		case EMenuText::KeyFlip: return O.Add(Value ? "TAB  SHOW PS5" : "TAB  SHOW XBOX");
		case EMenuText::NewGame: return O.Add("NEW GAME");
		case EMenuText::AskHead: return O.Add(Value == 2 ? "TRAIN?" : (Value ? "NEW GAME?" : "QUIT?"));
		case EMenuText::ConfirmNo: return O.Add(Value == 2 ? "NO, KEEP MY XP" : (Value ? "NO, KEEP MY SAVE" : "NO, STAY"));
		case EMenuText::ConfirmYes: return O.Add(Value == 2 ? "YES, TRAIN" : (Value ? "YES, START OVER" : "YES, QUIT"));
		case EMenuText::StageTag: return O.Add("STAGE ").Num(Value).Add("/").Num(Aux);
		case EMenuText::PromptQuit: return O.Add("QUIT");
		case EMenuText::KeyQuit: return O.Add("ESC  QUIT");
		case EMenuText::Hint:
			if (static_cast<EHint>(Value) == EHint::AskTrain)
			{
				return O.Add("TRAIN ").Add(Train::Name(Aux / 10)).Add(" TO LEVEL ").Num(Aux % 10);
			}
			return O.Add(HintString(static_cast<EHint>(Value)));
		// 2026-10-07
		case EMenuText::Status: return O.Add("STATUS");
		case EMenuText::Training: return O.Add("TRAINING");
		case EMenuText::StatusHead: return O.Add("STATUS");
		case EMenuText::TrainingHead: return O.Add("TRAINING");
		case EMenuText::TrackName: return O.Add(Train::Name(Value));
		case EMenuText::CostTag: return Value < 0 ? O.Add("MAX") : O.Num(Value).Add(" XP");
		case EMenuText::SpendXp: return O.Add("XP TO SPEND  ").Num(Value);
		case EMenuText::WinName: return O.Add("SAUD");
		case EMenuText::LevelLine: return O.Add("LEVEL ").Num(Value);
		case EMenuText::RankTitle: return O.Add(Ladder::RankName(Value));
		case EMenuText::XpLabel: return O.Add("XP");
		case EMenuText::XpLine: return Aux > 0 ? O.Num(Value).Add(" / ").Num(Aux).Add(" XP") : O.Num(Value).Add(" XP");
		case EMenuText::XpToNext: return Aux > 0 ? O.Num(Value).Add(" TO LEVEL ").Num(Aux) : O.Add("MAX LEVEL");
		case EMenuText::StatHp: return O.Add("HP ").Num(Value);
		case EMenuText::StatMp: return O.Add("MP ").Num(Value);
		case EMenuText::StatStamina: return O.Add("STAMINA ").Num(Value);
		case EMenuText::Section: return O.Add(Value == 0 ? "SKILLS" : (Value == 1 ? "TRAINING" : "QUEST"));
		case EMenuText::SkillName: return O.Add(Aux ? SkillName(Value) : "?");
		case EMenuText::QuestName: return O.Add(Value ? "--" : "FIND THE WAY UP");
		case EMenuText::QuestState: return O.Add("IN PROGRESS");
		case EMenuText::ControlsText:
		default: return O;
		}
	}
	/** Whether the engine must draw Spell() for this text: the slots the
	    HUD's own table (SaudHUD.cpp, MenuString) does not know -- every
	    2026-10-07 slot, the Confirm's third question, the track hint. */
	inline bool SpellsItself(EMenuText Slot, int Value)
	{
		if (static_cast<int>(Slot) >= static_cast<int>(EMenuText::Status)) return true;
		if ((Slot == EMenuText::AskHead || Slot == EMenuText::ConfirmNo || Slot == EMenuText::ConfirmYes) && Value >= 2)
			return true;
		return Slot == EMenuText::Hint && Value == static_cast<int>(EHint::AskTrain);
	}

	/** The length of the string a slot and value map to, for the layout's
	    width estimate; 0 for ControlsText (theirs). */
	inline int Chars(EMenuText Slot, int Value, int Aux = 0)
	{
		return Slot == EMenuText::ControlsText ? 0 : Spell(Slot, Value, Aux).N;
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
	constexpr float PlateLean = 0.f;             // square, as the System's bars (0.55 for the dark seinen's)
	constexpr float LabelText = 34.f;            // >= 1080 / 36
	constexpr float LabelIn = 26.f;              // past the lean
	constexpr float StripText = 32.f;            // the prompt strip
	constexpr float GlyphSize = 48.f;            // a prompt glyph's size (its disc's diameter): couch-sized
	constexpr float GlyphGap = 12.f;             // glyph to its word
	constexpr float PromptGap = 48.f;            // between prompts
	constexpr float ScrimAlpha = 0.78f;
	constexpr float PlateAlpha = 0.96f;          // (0.88 until the System: its cyan keyline would show through)
	constexpr float DimAlpha = 0.55f;            // the dim text and keylines: Ice / System at this
	constexpr float PulseHz = 0.38f;             // the focus pulse: one breath in 2.6 s
	/** The focused plate is the panel's navy taken FocusMix of the way to
	    the System's cyan, and FocusPulse further at the top of its breath:
	    a deep lit blue that stands 3:1 off the panel and carries ice
	    lettering 3:1 at its brightest (2026-10-03, the System; it was blood
	    breathing toward ember). */
	constexpr float FocusMix = 0.30f;
	constexpr float FocusPulse = 0.15f;
	constexpr float SysLinePx = 2.f;             // the System's line along the top of the wash
	// 2026-10-02
	constexpr float HintText = 30.f;             // the hint line: 1080 / 36, the least the HUD allows
	constexpr float HintGap = 26.f;              // under the last plate
	constexpr float TagText = 30.f;              // CONTINUE's "STAGE 3/9", right on its plate
	constexpr float MeterW = 200.f, MeterH = 22.f, MeterGap = 4.f;   // a level's ten segments, right on its plate
	constexpr float FocusNudge = 14.f;           // the focused plate stands this far out of the column
	constexpr float SlideIn = 32.f;              // a plate comes in from this far left (inside the column's 40)
	// 2026-10-07: the training's plates and the status window
	constexpr float PipW = 22.f, PipH = 18.f, PipGap = 6.f;      // a track's five levels, on its plate
	constexpr float PipGapToCost = 24.f;
	constexpr float PoorRule = 3.f;              // the crimson rule under a cost the XP will not cover
	constexpr float WinGap = 48.f;               // the column (plate and nudge) to the window
	constexpr float WinMaxW = 780.f;             // the window, at most (it takes what the screen leaves, to this)
	constexpr float WinPad = 24.f;
	constexpr float WinText = 30.f;              // the window's lettering: 1080 / 36, the least the HUD allows
	constexpr float WinBigText = 44.f;           // LEVEL n and the rank
	constexpr float WinQuestText = 34.f;         // the quest's name
	constexpr float XpBarH = 16.f;
	constexpr float SlotH = 36.f, SlotPitch = 44.f;   // a skill's slot
	constexpr float MarkPx = 12.f;               // the square in an acquired skill's slot
	constexpr float TrackPitch = 40.f;           // a track's row in the window
	constexpr float WinPipW = 14.f, WinPipH = 14.f, WinPipGap = 5.f;
	constexpr float RulePx = 1.5f;               // the rules between the window's sections
	/** The window wipes open (WinWipe from WinDelay) and its contents come
	    in after it (WinShowDelay, over WinShow): settled by EnterSeconds. */
	constexpr float WinDelay = 0.10f, WinWipe = 0.30f, WinShowDelay = 0.30f, WinShow = 0.20f;

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
		// 2026-10-07: the status window (Status only; W 0 elsewhere), each
		// line's top left, and its rows
		FRect Window;
		FPoint WinName, Level, Rank, XpLabel, XpLine, XpToNext, Stat[3], Section[3], Quest, QuestState;
		FRect XpBar;
		float Rule[3] = {};                // the rules' y: under the XP, under the stats, over the quest
		FRect Slot[Skills];                // a skill's slot
		FPoint TrackAt[Train::Tracks];     // a track's name
		FRect Pips[Train::Tracks];         // ...and its five levels
		float SubW = 0.f;                  // a sub-column's width (skills | training)
	};

	/** The status window: right of the column (its plates and their nudge,
	    then WinGap), from the heading's top, as wide as the screen leaves
	    up to WinMaxW, its glow on the right safe line at the most; and its
	    contents, top down -- the heading strip with his name; LEVEL n and
	    the rank; the XP bar and its numbers; HP, MP, STAMINA; the skills'
	    five slots beside the six tracks; the quest. */
	inline void LayStatus(const FPage& P, const FMenuModel& M, FMenuLayout& L)
	{
		const float X = P.Left() + P.Px(ColumnIn + PlateW + FocusNudge + WinGap);
		const float Y = P.Top() + P.Px(HeadDown);
		const float W = FMath::Min(P.Right() - P.Px(SaudHud::WindowInset) - X, P.Px(WinMaxW));
		const float Pad = P.Px(WinPad), T = P.Px(WinText), Big = P.Px(WinBigText);
		const float In = X + Pad, Out = X + W - Pad, CW = Out - In;
		const FStatus& S = M.Status;
		L.WinName = {In, Y + 0.5f * (P.Px(SaudHud::HeadH) - T)};
		float At = Y + P.Px(SaudHud::HeadH) + P.Px(16.f);
		L.Level = {In, At};
		L.Rank = {Out - TextWidth(EMenuText::RankTitle, S.Rank, Big), At};
		At += Big + P.Px(18.f);
		L.XpLabel = {In, At};
		const float BarX = In + TextWidth(EMenuText::XpLabel, 0, T) + P.Px(16.f);
		L.XpBar = {BarX, At + 0.5f * (T - P.Px(XpBarH)), Out - BarX, P.Px(XpBarH)};
		At += T + P.Px(10.f);
		const bool bTop = S.LevelNext <= 0;
		L.XpLine = {In, At};
		L.XpToNext = {Out - TextWidth(EMenuText::XpToNext, S.LevelNext - S.Earned, T, bTop ? 0 : S.Level + 1), At};
		At += T + P.Px(14.f);
		L.Rule[0] = At;
		At += P.Px(14.f);
		L.Stat[0] = {In, At};
		L.Stat[1] = {In + 0.30f * CW, At};
		L.Stat[2] = {In + 0.58f * CW, At};
		At += T + P.Px(14.f);
		L.Rule[1] = At;
		At += P.Px(14.f);
		L.SubW = 0.5f * (CW - P.Px(24.f));
		const float X2 = In + L.SubW + P.Px(24.f);
		L.Section[0] = {In, At};
		L.Section[1] = {X2, At};
		At += T + P.Px(12.f);
		for (int K = 0; K < Skills; ++K)
		{
			L.Slot[K] = {In, At + P.Px(SlotPitch) * static_cast<float>(K), L.SubW, P.Px(SlotH)};
		}
		const float PipsW = P.Px(5.f * WinPipW + 4.f * WinPipGap);
		for (int Tk = 0; Tk < Train::Tracks; ++Tk)
		{
			const float Row = At + P.Px(TrackPitch) * static_cast<float>(Tk);
			L.TrackAt[Tk] = {X2, Row + 0.5f * (P.Px(SlotH) - T)};
			L.Pips[Tk] = {X2 + L.SubW - PipsW, Row + 0.5f * (P.Px(SlotH) - P.Px(WinPipH)), PipsW, P.Px(WinPipH)};
		}
		At += FMath::Max(P.Px(SlotPitch) * static_cast<float>(Skills - 1) + P.Px(SlotH),
		                 P.Px(TrackPitch) * static_cast<float>(Train::Tracks - 1) + P.Px(SlotH));
		At += P.Px(16.f);
		L.Rule[2] = At;
		At += P.Px(14.f);
		L.Section[2] = {In, At};
		At += T + P.Px(10.f);
		const float Q = P.Px(WinQuestText);
		L.Quest = {In, At};
		L.QuestState = {Out - TextWidth(EMenuText::QuestState, 0, T), At + 0.5f * (Q - T)};
		At += Q + Pad;
		L.Window = {X, Y, W, At - Y};
	}

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
		if (M.Screen == EScreen::Status)
		{
			LayStatus(P, M, L);
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

	/** The focused plate's fill on the real-time clock: the panel's navy
	    lit toward the System's cyan, breathing a little further, slowly.
	    Never under FocusMix, so it never comes nearer the panel than the
	    3:1 the menu promises; never past FocusMix + FocusPulse, so its ice
	    label keeps 3:1 on it. */
	inline FRgba FocusFill(float Clock)
	{
		const float Pulse = 0.5f + 0.5f * FMath::Sin(Clock * 6.2831853f * PulseHz);
		return SaudHud::LerpColour(Colour::Panel, Colour::System, FocusMix + FocusPulse * Pulse);
	}
	inline FRgba UnfocusedFill()
	{
		return SaudHud::WithAlpha(Colour::Panel, PlateAlpha);
	}
	inline FRgba DimText()
	{
		return SaudHud::WithAlpha(Colour::Ice, DimAlpha);
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
		case EItem::Status: return EMenuText::Status;
		case EItem::Training: return EMenuText::Training;
		case EItem::TrainBox:
		case EItem::TrainKick:
		case EItem::TrainVit:
		case EItem::TrainSpd:
		case EItem::TrainStam:
		case EItem::TrainIron: return EMenuText::TrackName;
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
		case EItem::ConfirmYes: return static_cast<int>(M.Ask);
		default: return TrackOfItem(I) >= 0 ? TrackOfItem(I) : 0;
		}
	}

	/** The hint line for the focused item (and on a Confirm, what Yes does). */
	inline EHint HintOf(const FMenuModel& M, EItem I)
	{
		if (M.Screen == EScreen::Confirm)
		{
			return M.Ask == EAsk::Train ? EHint::AskTrain : (M.Ask == EAsk::NewGame ? EHint::AskNewGame : EHint::AskQuit);
		}
		// a denied buy says why, on the item it was denied on, until the
		// focus moves or it times out
		if (M.Screen == EScreen::Training && M.DeniedLeft > 0.f && M.DeniedItem == M.Focus)
		{
			return M.bDeniedMaxed ? EHint::Maxed : EHint::Poor;
		}
		if (TrackOfItem(I) >= 0)
		{
			return static_cast<EHint>(static_cast<int>(EHint::TrainBox) + TrackOfItem(I));
		}
		switch (I)
		{
		case EItem::Status: return EHint::Status;
		case EItem::Training: return EHint::Training;
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
		default:
			return M.ReturnTo == EScreen::Status ? EHint::BackStatus
			     : (M.ReturnTo == EScreen::Pause ? EHint::BackPause : EHint::BackTitle);
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
		/** The System's window behind the column: a straight navy panel,
		    full Alpha to FadeFrom of its width and fading to nothing
		    (smoothstep) at its end, in strips every PitchPx so the fade is
		    smooth, with the System's cyan line along its top fading with
		    it. (It was the HUD's torn ink strip until 2026-10-03.) */
		inline void SysWash(FMenuList& Out, const FPage& P, const FRect& R, float Alpha, float FadeFrom)
		{
			const int N = static_cast<int>(FMath::Max(2.f, SaudHud::FloorF(R.W / P.Px(SaudHud::PitchPx) + 0.5f))) + 1;
			const float Line = FMath::Max(1.f, P.Px(SysLinePx));
			for (int Pass = 0; Pass < 2; ++Pass)
			{
				FPoint PrevT, PrevB;
				FRgba PrevC;
				for (int i = 0; i < N; ++i)
				{
					const float U = static_cast<float>(i) / static_cast<float>(N - 1);
					const float X = R.X + R.W * U;
					const float K = U <= FadeFrom ? 0.f : FMath::Clamp((U - FadeFrom) / (1.f - FadeFrom), 0.f, 1.f);
					const float A = 1.f - K * K * (3.f - 2.f * K);
					const FPoint Tp = {X, R.Y}, Bt = {X, Pass == 0 ? R.Y + R.H : R.Y + Line};
					const FRgba C = Pass == 0 ? SaudHud::WithAlpha(Colour::Panel, Alpha * A)
					                          : SaudHud::WithAlpha(Colour::System, A);
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
		}

		/** A plate (square since the System): its keyline grown by KeyPx,
		    then its fill. */
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
			const FRgba Word = SaudHud::WithAlpha(Colour::Ice, Alpha);
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
			                    Colour::Ink, Colour::Ice, Sink);
			const float TX = X + GW + P.Px(GlyphGap);
			Out.Text(PadSlot, Value, 0, {TX, Baseline - H}, H, Word, Stroke, false, -1, EMenuPart::Glyph);
			return TX + TextWidth(PadSlot, Value, H) + P.Px(PromptGap);
		}
	}

	namespace Detail
	{
		/** A quad from a rectangle, wound as every other menu quad is. */
		inline void Rect(FMenuList& Out, const FRect& R, const FRgba& C, EMenuPart Pt, int Item, int Tag)
		{
			FPoint Q[4];
			SaudHud::LeanQuad(R, 1.f, 0.f, Q);
			Out.Quad(Q, C, Pt, Item, Tag);
		}

		/** Five level pips in R, Lit of them in Lit's colour, the rest dim
		    cyan; Tag 1 on a lit one (as a meter's segments). */
		inline void Pips(FMenuList& Out, const FRect& R, float Gap, int Lit, const FRgba& On, float Alpha, int Item)
		{
			const float SW = (R.W - 4.f * Gap) / 5.f;
			for (int k = 0; k < Train::MaxLevel; ++k)
			{
				const FRgba C = k < Lit ? On : SaudHud::WithAlpha(Colour::System, DimAlpha * 0.6f * Alpha);
				Rect(Out, {R.X + static_cast<float>(k) * (SW + Gap), R.Y, SW, R.H}, C, EMenuPart::Meter, Item, k < Lit ? 1 : 0);
			}
		}

		/** A Training plate's right side: the track's five levels and what
		    its next one costs (MAX at the top), and a crimson rule under a
		    cost the spendable will not cover. */
		inline void TrackPlate(FMenuList& Out, const FPage& P, const FMenuModel& M, const FRect& R, int T, int Item,
		                       const FRgba& Label, float In)
		{
			const int Lv = M.Status.Track[T];
			const bool bTop = Lv >= Train::MaxLevel;
			const int Cost = bTop ? -1 : Train::Cost(Lv);
			const float TH = P.Px(TagText), Stroke = P.Px(SaudHud::TextStroke);
			// the cost's slot is as wide as the widest cost, so the pips of
			// every plate line up
			const float SlotW = TextWidth(EMenuText::CostTag, Train::Cost(Train::MaxLevel - 1), TH);
			const float TW = TextWidth(EMenuText::CostTag, Cost, TH);
			const float Right = R.X + R.W - P.Px(LabelIn);
			const FPoint At = {Right - TW, R.Y + 0.5f * (R.H - TH)};
			Out.Text(EMenuText::CostTag, Cost, 0, At, TH, Label, Stroke, false, Item, EMenuPart::Plate);
			if (!bTop && M.Status.Spendable < Cost)
			{
				Rect(Out, {At.X, At.Y + TH + P.Px(3.f), TW, FMath::Max(1.f, P.Px(PoorRule))},
				     SaudHud::WithAlpha(Colour::Danger, In), EMenuPart::Mark, Item, 1);
			}
			const float PW = P.Px(5.f * PipW + 4.f * PipGap);
			const FRect Pr = {Right - SlotW - P.Px(PipGapToCost) - PW, R.Y + 0.5f * (R.H - P.Px(PipH)), PW, P.Px(PipH)};
			Pips(Out, Pr, P.Px(PipGap), Lv, Label, In, Item);
		}

		/** A System window in the menu's list, as the HUD draws its own
		    (SaudHud::Window): the glow fading out from the edge, the navy
		    panel cut at two corners, the heading strip and its hairline,
		    the edge, the ice corner marks outside the uncut corners. A is
		    the whole window's alpha (its entrance). */
		inline void SysWindow(FMenuList& Out, const FPage& P, const FRect& R, float A)
		{
			using namespace SaudHud;
			if (R.W <= 2.f * P.Px(CutPx) + 2.f || R.H <= P.Px(HeadH) + 2.f)
			{
				return;
			}
			FPoint Ring[6], EdgeOut[6], GlowOut[6];
			WindowRing(R, P.Px(CutPx), Ring);
			const float E = FMath::Max(1.f, P.Px(EdgePx));
			GrowRing(Ring, 6, E, EdgeOut);
			GrowRing(Ring, 6, E + P.Px(GlowPx), GlowOut);
			const auto Band = [&Out](const FPoint* Inner, const FPoint* Outer, const FRgba& Ci, const FRgba& Co, EMenuPart Pt)
			{
				for (int i = 0; i < 6; ++i)
				{
					const int j = (i + 1) % 6;
					const FPoint Q[4] = {Outer[i], Outer[j], Inner[j], Inner[i]};
					const FRgba C[4] = {Co, Co, Ci, Ci};
					Out.Quad(Q, C, Pt, -1, 0);
				}
			};
			Band(EdgeOut, GlowOut, WithAlpha(Colour::System, GlowAlpha * A), WithAlpha(Colour::System, 0.f), EMenuPart::Glow);
			const FPoint Centre = {R.X + 0.5f * R.W, R.Y + 0.5f * R.H};
			const FRgba Panel = WithAlpha(Colour::Panel, PlateAlpha * A);
			for (int i = 0; i < 6; ++i)
			{
				Out.Tri(Centre, Panel, Ring[i], Panel, Ring[(i + 1) % 6], Panel, EMenuPart::Window, -1, 0);
			}
			const float Head = P.Px(HeadH), C = FMath::Min(P.Px(CutPx), Head);
			const FPoint Strip[5] = {{R.X + C, R.Y}, {R.X + R.W, R.Y}, {R.X + R.W, R.Y + Head}, {R.X, R.Y + Head}, {R.X, R.Y + C}};
			const FRgba Tint = WithAlpha(Colour::System, HeadAlpha * A);
			const FPoint Mid = {R.X + 0.5f * R.W, R.Y + 0.5f * Head};
			for (int i = 0; i < 5; ++i)
			{
				Out.Tri(Mid, Tint, Strip[i], Tint, Strip[(i + 1) % 5], Tint, EMenuPart::Window, -1, 0);
			}
			Rect(Out, {R.X, R.Y + Head, R.W, FMath::Max(1.f, P.Px(1.5f))}, WithAlpha(Colour::System, 0.7f * A), EMenuPart::Edge, -1, 0);
			Band(Ring, EdgeOut, WithAlpha(Colour::System, A), WithAlpha(Colour::System, A), EMenuPart::Edge);
			const float B = P.Px(BracketPx), W = FMath::Max(1.f, P.Px(BracketW)), O = E + P.Px(3.f);
			const FRgba Ice = WithAlpha(Colour::Ice, 0.9f * A);
			const float Rx = R.X + R.W + O, Ty = R.Y - O, Lx = R.X - O, By = R.Y + R.H + O;
			Rect(Out, {Rx - B, Ty - W, B + W, W}, Ice, EMenuPart::Bracket, -1, 0);
			Rect(Out, {Rx, Ty, W, B}, Ice, EMenuPart::Bracket, -1, 0);
			Rect(Out, {Lx - W, By, B + W, W}, Ice, EMenuPart::Bracket, -1, 0);
			Rect(Out, {Lx - W, By - B, W, B}, Ice, EMenuPart::Bracket, -1, 0);
		}

		/** The System's status window: wiping open from its left over
		    WinWipe, its contents coming in after it. */
		inline void StatusWindow(FMenuList& Out, const FPage& P, const FMenuModel& M, const FMenuLayout& L)
		{
			const FStatus& S = M.Status;
			FRect R = L.Window;
			R.W *= Arrive(M, WinDelay, WinWipe);
			SysWindow(Out, P, R, 1.f);
			const float A = Arrive(M, WinShowDelay, WinShow);
			if (A <= 0.f)
			{
				return;
			}
			const float T = P.Px(WinText), Big = P.Px(WinBigText), Stroke = P.Px(SaudHud::TextStroke);
			const FRgba Ice = SaudHud::WithAlpha(Colour::Ice, A);
			const FRgba Dim = SaudHud::WithAlpha(Colour::Ice, DimAlpha * A);
			const FRgba Cyan = SaudHud::WithAlpha(Colour::System, A);
			const auto Line = [&](EMenuText Slot, int V, int Aux, const FPoint& At, float H, const FRgba& C)
			{
				Out.Text(Slot, V, Aux, At, H, C, Stroke, false, -1, EMenuPart::Window);
			};
			const auto Rule = [&](float Y)
			{
				Rect(Out, {L.Window.X + P.Px(WinPad), Y, L.Window.W - 2.f * P.Px(WinPad), FMath::Max(1.f, P.Px(RulePx))},
				     SaudHud::WithAlpha(Colour::System, DimAlpha * A), EMenuPart::Mark, -1, 0);
			};
			Line(EMenuText::WinName, 0, 0, L.WinName, T, Ice);
			Line(EMenuText::LevelLine, S.Level, 0, L.Level, Big, Ice);
			Line(EMenuText::RankTitle, S.Rank, 0, L.Rank, Big, Cyan);
			// the XP bar: how far through this level the earned XP is (full at the top)
			Line(EMenuText::XpLabel, 0, 0, L.XpLabel, T, Ice);
			const bool bTop = S.LevelNext <= 0;
			const float Through = bTop ? 1.f
			    : FMath::Clamp(static_cast<float>(S.Earned - S.LevelFloor) / static_cast<float>(FMath::Max(1, S.LevelNext - S.LevelFloor)), 0.f, 1.f);
			Rect(Out, SaudHud::Grow(L.XpBar, FMath::Max(1.f, P.Px(2.f))), SaudHud::WithAlpha(Colour::System, DimAlpha * A),
			     EMenuPart::Bar, -1, 0);
			Rect(Out, L.XpBar, SaudHud::WithAlpha(Colour::Trough, A), EMenuPart::Bar, -1, 1);
			if (Through * L.XpBar.W >= 0.5f)
			{
				Rect(Out, {L.XpBar.X, L.XpBar.Y, L.XpBar.W * Through, L.XpBar.H}, Cyan, EMenuPart::Bar, -1, 2);
			}
			Line(EMenuText::XpLine, S.Earned, bTop ? 0 : S.LevelNext, L.XpLine, T, Dim);
			Line(EMenuText::XpToNext, bTop ? 0 : S.LevelNext - S.Earned, bTop ? 0 : S.Level + 1, L.XpToNext, T, Dim);
			Rule(L.Rule[0]);
			Line(EMenuText::StatHp, S.MaxHealth, 0, L.Stat[0], T, Ice);
			Line(EMenuText::StatMp, S.MaxMana, 0, L.Stat[1], T, Ice);
			Line(EMenuText::StatStamina, S.MaxStamina, 0, L.Stat[2], T, Ice);
			Rule(L.Rule[1]);
			// the five skills: a slot each, the name when he has it and a
			// "?" when he has not; HAWK FIST's slot violet either way
			Line(EMenuText::Section, 0, 0, L.Section[0], T, Cyan);
			for (int K = 0; K < Skills; ++K)
			{
				const FRect& Sl = L.Slot[K];
				const bool bHas = S.Skill[K];
				const FRgba Edge = K == HawkFistSkill ? SaudHud::WithAlpha(Colour::Shadow, (bHas ? 1.f : DimAlpha) * A)
				                                      : SaudHud::WithAlpha(Colour::System, (bHas ? 1.f : DimAlpha) * A);
				Detail::Plate(Out, Sl, SaudHud::WithAlpha(Colour::Panel, PlateAlpha * A), Edge,
				              FMath::Max(1.f, P.Px(SaudHud::Ink)), -1);
				const float MX = Sl.X + P.Px(12.f);
				if (bHas)
				{
					Rect(Out, {MX, Sl.Y + 0.5f * (Sl.H - P.Px(MarkPx)), P.Px(MarkPx), P.Px(MarkPx)},
					     K == HawkFistSkill ? SaudHud::WithAlpha(Colour::Shadow, A) : Ice, EMenuPart::Mark, -1, 2 + K);
				}
				Line(EMenuText::SkillName, K, bHas ? 1 : 0, {MX + P.Px(MarkPx + 12.f), Sl.Y + 0.5f * (Sl.H - T)}, T,
				     bHas ? Ice : Dim);
			}
			// the six tracks, each its five levels
			Line(EMenuText::Section, 1, 0, L.Section[1], T, Cyan);
			for (int Tk = 0; Tk < Train::Tracks; ++Tk)
			{
				Line(EMenuText::TrackName, Tk, 0, L.TrackAt[Tk], T, S.Track[Tk] > 0 ? Ice : Dim);
				Pips(Out, L.Pips[Tk], P.Px(WinPipGap), S.Track[Tk], Cyan, A, -1);
			}
			// the quest: FIND THE WAY UP, in progress, until the title is
			// won; then nothing ("--": removed, no longer required)
			Rule(L.Rule[2]);
			Line(EMenuText::Section, 2, 0, L.Section[2], T, Cyan);
			Line(EMenuText::QuestName, S.bQuestOpen ? 0 : 1, 0, L.Quest, P.Px(WinQuestText), S.bQuestOpen ? Ice : Dim);
			if (S.bQuestOpen)
			{
				Line(EMenuText::QuestState, 0, 0, L.QuestState, T, Cyan);
			}
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
		const bool bScrim = M.Root == EScreen::Pause || M.Screen == EScreen::Controls;
		if (bScrim)
		{
			const FPoint Q[4] = {{0.f, P.ScreenH}, {0.f, 0.f}, {P.ScreenW, 0.f}, {P.ScreenW, P.ScreenH}};
			Out.Quad(Q, SaudHud::WithAlpha(Colour::Panel, ScrimAlpha), EMenuPart::Scrim, -1, 0);
		}

		if (M.Screen == EScreen::Controls)
		{
			FMenuSink Sink(Out, EMenuPart::Diagram, -1, 0);
			SaudControls::BuildControlsPage(P, M.Shown, Sink);
		}
		else
		{
			// the System's window behind the column, wiping open from the
			// left as the screen opens; the heading in ice, the System's
			// cyan bar wiping open under it, and on the Title the sub-line
			// (on a Confirm, what Yes does: the hint below)
			FRect Wash = L.Wash;
			Wash.W *= Arrive(M, 0.f, WashWipeSeconds);
			if (Wash.W >= 2.f)
			{
				Detail::SysWash(Out, P, Wash, WashAlpha, WashFadeFrom);
			}
			const float HeadA = Arrive(M, 0.05f, 0.25f);
			EMenuText Head = EMenuText::SettingsHead;
			int HeadV = 0;
			if (M.Screen == EScreen::Title) Head = EMenuText::Saud;
			else if (M.Screen == EScreen::Pause) Head = EMenuText::Paused;
			else if (M.Screen == EScreen::Confirm) { Head = EMenuText::AskHead; HeadV = static_cast<int>(M.Ask); }
			else if (M.Screen == EScreen::Status) Head = EMenuText::StatusHead;
			else if (M.Screen == EScreen::Training) Head = EMenuText::TrainingHead;
			Out.Text(Head, HeadV, 0, L.Heading, L.HeadingH, SaudHud::WithAlpha(Colour::Ice, HeadA), Stroke, false, -1,
			         EMenuPart::Wash);
			const float T = FMath::Clamp(M.Since / SlashRevealSeconds, 0.f, 1.f);
			const float Open = 1.f - (1.f - T) * (1.f - T) * (1.f - T);
			if (Open > 0.f)
			{
				FPoint Q[4];
				SaudHud::LeanQuad(L.Slash, Open, 0.f, Q);
				Out.Quad(Q, SaudHud::WithAlpha(Colour::System, SaudHud::SlashAlpha), EMenuPart::Slash, -1, 0);
			}
			if (M.Screen == EScreen::Title)
			{
				Out.Text(EMenuText::Subtitle, 0, 0, L.Subtitle, P.Px(SubText), SaudHud::WithAlpha(Colour::Ice, DimAlpha * HeadA),
				         Stroke, false, -1, EMenuPart::Wash);
			}
			// the Training's spendable XP where the Title's sub-line sits:
			// what every cost on the plates is measured against
			if (M.Screen == EScreen::Training)
			{
				Out.Text(EMenuText::SpendXp, M.Status.Spendable, 0, L.Subtitle, P.Px(SubText),
				         SaudHud::WithAlpha(Colour::Ice, HeadA), Stroke, false, -1, EMenuPart::Wash);
			}
		}

		// the items: square plates, the focused one a lit System blue in a
		// cyan keyline with an ice label, the rest the panel's navy in a dim
		// cyan keyline with a dim label. The focus glides: while it moves two
		// neighbours share it, each lit and nudged out of the column by
		// its share. Each plate slides in from the left as the screen
		// opens, one after another.
		const float H = P.Px(LabelText);
		const FRgba DimKey = SaudHud::WithAlpha(Colour::System, DimAlpha);
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
			// a buy just denied on this plate: its keyline crimson
			const bool bDenied = M.Screen == EScreen::Training && M.DeniedLeft > 0.f && M.DeniedItem == i;
			Detail::Plate(Out, R, Fade(SaudHud::LerpColour(UnfocusedFill(), FocusFill(M.Clock), W)),
			              Fade(bDenied ? Colour::Danger : SaudHud::LerpColour(DimKey, Colour::System, W)), Key, i);
			const FRgba Label = Fade(SaudHud::LerpColour(DimText(), Colour::Ice, W));
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
			// a track: its five levels and what the next costs, right on its
			// plate (MAX at the top); a crimson rule under a cost the XP
			// will not cover
			if (TrackOfItem(List[i]) >= 0)
			{
				Detail::TrackPlate(Out, P, M, R, TrackOfItem(List[i]), i, Label, In);
			}
			// the Train question's YES carries the cost
			if (List[i] == EItem::ConfirmYes && M.Ask == EAsk::Train && M.TrainTrack >= 0 && M.TrainTrack < Train::Tracks)
			{
				const float TH = P.Px(TagText);
				const int C = Train::Cost(M.Status.Track[M.TrainTrack]);
				const float TW = TextWidth(EMenuText::CostTag, C, TH);
				Out.Text(EMenuText::CostTag, C, 0, {R.X + R.W - P.Px(LabelIn) - TW, R.Y + 0.5f * (R.H - TH)}, TH, Label, Stroke,
				         false, i, EMenuPart::Plate);
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
					const FRgba C = k < Lit ? Label : Fade(SaudHud::WithAlpha(Colour::System, DimAlpha * 0.6f));
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
			// (the Train question names the track and the level it buys)
			const int HAux = Hn == EHint::AskTrain && M.TrainTrack >= 0 && M.TrainTrack < Train::Tracks
			                     ? M.TrainTrack * 10 + M.Status.Track[M.TrainTrack] + 1 : 0;
			Out.Text(EMenuText::Hint, static_cast<int>(Hn), HAux, L.Hint, L.HintH, SaudHud::WithAlpha(Colour::Ice, DimAlpha * A),
			         Stroke, false, -1, EMenuPart::Wash);
		}

		// the status window, right of the column
		if (M.Screen == EScreen::Status)
		{
			Detail::StatusWindow(Out, P, M, L);
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
			case EScreen::Status:
			case EScreen::Training:
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
