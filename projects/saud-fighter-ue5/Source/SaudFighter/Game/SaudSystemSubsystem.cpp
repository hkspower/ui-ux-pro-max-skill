#include "Game/SaudSystemSubsystem.h"

#include "Combat/SaudMenu.h"
#include "Game/SaudConfigSubsystem.h"
#include "Game/SaudGameInstance.h"
#include "Game/SaudLookSubsystem.h"
#include "World/AbilityGate.h"
#include "World/WaveDirector.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

DEFINE_LOG_CATEGORY_STATIC(LogSaudSystem, Log, All);

using namespace SaudSystem;

namespace
{
	// The stage rows the story turns on (DT_Stages.json), and two more names;
	// FNames made where they are used, not at static initialisation.
	const TCHAR* const Souq = TEXT("SouqAlDawar");          // where he lands, and where the ring closes
	const TCHAR* const Desert = TEXT("MukhayyamAlNiran");   // the camp of fires: HAWK FIST, and west is the souq
	const TCHAR* const Arena = TEXT("AlHalqa");             // AL-WAHSH: the victory
	const TCHAR* const SaqrStage = TEXT("AlHilal");         // the neon crescent
	const TCHAR* const Saqr = TEXT("Saqr");                 // AL-SAQR's fighter row (DT_Fighters)
	const TCHAR* const Experience = TEXT("Experience");     // a gate that pays XP: GateCleared_Experience

	const TCHAR* LinesTable = TEXT("/Game/Data/DT_SystemLines.DT_SystemLines");

	void PutT(char* Dst, int32 N, const FString& Src)
	{
		Put(Dst, N, TCHAR_TO_UTF8(*Src));
	}

	FLines Words(const FSaudSystemLine& L)
	{
		FLines W;
		PutT(W.Title, TitleMax, L.Title);
		PutT(W.Head, HeadMax, L.Head);
		PutT(W.Body, BodyMax, L.Body);
		PutT(W.Reward, RewardMax, L.Reward);
		PutT(W.Beneath, BeneathMax, L.Beneath);
		PutT(W.Status, StatusMax, L.Status);
		return W;
	}

	/** What the look draws for a window as it opens; None for the rest. */
	SaudAnime::ESystemFx FxFor(EKind K)
	{
		switch (K)
		{
		case EKind::LevelUp:       return SaudAnime::ESystemFx::LevelUp;
		case EKind::SkillAcquired: return SaudAnime::ESystemFx::SkillAcquired;
		case EKind::RankUp:        return SaudAnime::ESystemFx::RankUp;
		case EKind::QuestComplete: return SaudAnime::ESystemFx::QuestComplete;
		default:                   return SaudAnime::ESystemFx::None;
		}
	}
}

USaudSystemSubsystem* USaudSystemSubsystem::Get(const UObject* WorldContext)
{
	const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	UGameInstance* GI = World ? World->GetGameInstance() : nullptr;
	return GI ? GI->GetSubsystem<USaudSystemSubsystem>() : nullptr;
}

void USaudSystemSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	LoadLines();
	if (const FSaudSystemLine* Q = Lines.Find(FName(TEXT("OpenQuest"))))
	{
		System.Quest = Words(*Q);
	}
	if (USaudGameInstance* GI = Game())
	{
		GI->OnAbilityGranted.AddDynamic(this, &USaudSystemSubsystem::HandleAbilityGranted);
		GI->OnExperienceChanged.AddDynamic(this, &USaudSystemSubsystem::HandleExperienceChanged);
	}
	GateHandle = AAbilityGate::OnAnyGateOpened.AddUObject(this, &USaudSystemSubsystem::HandleGateOpened);
}

void USaudSystemSubsystem::Deinitialize()
{
	AAbilityGate::OnAnyGateOpened.Remove(GateHandle);
	if (USaudGameInstance* GI = Game())
	{
		GI->OnAbilityGranted.RemoveDynamic(this, &USaudSystemSubsystem::HandleAbilityGranted);
		GI->OnExperienceChanged.RemoveDynamic(this, &USaudSystemSubsystem::HandleExperienceChanged);
	}
	Super::Deinitialize();
}

USaudGameInstance* USaudSystemSubsystem::Game() const
{
	return Cast<USaudGameInstance>(GetGameInstance());
}

/* -------------------------------------------------------------- the words */

void USaudSystemSubsystem::LoadLines()
{
	Lines.Reset();
	if (const UDataTable* Table = LoadObject<UDataTable>(nullptr, LinesTable, nullptr, LOAD_NoWarn))
	{
		Table->ForeachRow<FSaudSystemLine>(TEXT("USaudSystemSubsystem::LoadLines"),
			[this](const FName& Name, const FSaudSystemLine& Row) { Lines.Add(Name, Row); });
	}
	if (Lines.Num() > 0)
	{
		return;
	}
	// Not imported (yet): the hand-authored file itself.
	const FString Path = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data"), TEXT("DT_SystemLines.json"));
	FString Json;
	TArray<TSharedPtr<FJsonValue>> Rows;
	if (!FFileHelper::LoadFileToString(Json, *Path)
		|| !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json), Rows))
	{
		UE_LOG(LogSaudSystem, Warning, TEXT("No System lines: neither %s nor %s. The System says nothing."), LinesTable, *Path);
		return;
	}
	for (const TSharedPtr<FJsonValue>& V : Rows)
	{
		const TSharedPtr<FJsonObject> O = V.IsValid() ? V->AsObject() : nullptr;
		if (!O.IsValid())
		{
			continue;
		}
		FSaudSystemLine L;
		L.Event = FName(*O->GetStringField(TEXT("Event")));
		L.Key = FName(*O->GetStringField(TEXT("Key")));
		L.Title = O->GetStringField(TEXT("Title"));
		L.Head = O->GetStringField(TEXT("Head"));
		L.Body = O->GetStringField(TEXT("Body"));
		L.Reward = O->GetStringField(TEXT("Reward"));
		L.Beneath = O->GetStringField(TEXT("Beneath"));
		L.Status = O->GetStringField(TEXT("Status"));
		L.Area = O->GetStringField(TEXT("Area"));
		L.NameArabic = O->GetStringField(TEXT("NameArabic"));
		L.StoryArabic = O->GetStringField(TEXT("StoryArabic"));
		Lines.Add(FName(*O->GetStringField(TEXT("Name"))), L);
	}
}

const FSaudSystemLine* USaudSystemSubsystem::Line(EKind Kind, FName Key) const
{
	const FString Event(UTF8_TO_TCHAR(KindName(Kind)));
	if (!Key.IsNone())
	{
		if (const FSaudSystemLine* L = Lines.Find(FName(*(Event + TEXT("_") + Key.ToString()))))
		{
			return L;
		}
	}
	return Lines.Find(FName(*Event));
}

void USaudSystemSubsystem::Say(EKind Kind, FName Key, const FArgs& Args)
{
	const FSaudSystemLine* L = Line(Kind, Key);
	if (!L)
	{
		UE_LOG(LogSaudSystem, Warning, TEXT("No System line for %s %s."), UTF8_TO_TCHAR(KindName(Kind)), *Key.ToString());
		return;
	}
	const FString K = Key.IsNone() ? FString() : Key.ToString();
	System.Push(MakeEvent(Kind, TCHAR_TO_UTF8(*K), Words(*L), Args));
}

/* ---------------------------------------------------------- the progress */

bool USaudSystemSubsystem::IsFresh() const
{
	const USaudGameInstance* GI = Game();
	if (!GI)
	{
		return false;
	}
	const FSaudProgress& P = GI->GetProgress();
	return P.Experience == 0 && GI->GetSpentExperience() == 0 && P.ClearedStages.Num() == 0 && P.Abilities.Num() == 0;
}

void USaudSystemSubsystem::SampleLevel()
{
	if (const USaudGameInstance* GI = Game())
	{
		LastLevel = GI->GetLevel();
	}
}

void USaudSystemSubsystem::LevelBonus(int32 From, int32 To, int32& OutHp, int32& OutMp) const
{
	// levels.js perLevel, should the table not be there
	OutHp = 6 * (To - From);
	OutMp = 4 * (To - From);
	const USaudConfigSubsystem* Config = GetGameInstance() ? GetGameInstance()->GetSubsystem<USaudConfigSubsystem>() : nullptr;
	const UDataTable* Table = Config ? Config->GetLevelTable() : nullptr;
	if (!Table)
	{
		return;
	}
	const FLevelDef* A = nullptr;
	const FLevelDef* B = nullptr;
	Table->ForeachRow<FLevelDef>(TEXT("USaudSystemSubsystem::LevelBonus"), [&](const FName&, const FLevelDef& Row)
	{
		if (Row.Level == From) A = &Row;
		if (Row.Level == To) B = &Row;
	});
	if (A && B)
	{
		OutHp = FMath::RoundToInt(B->BonusHealth - A->BonusHealth);
		OutMp = FMath::RoundToInt(B->BonusMana - A->BonusMana);
	}
}

void USaudSystemSubsystem::HandleExperienceChanged(int32 /*NewTotal*/)
{
	USaudGameInstance* GI = Game();
	if (!GI)
	{
		return;
	}
	if (IsFresh())
	{
		// a new game (ResetProgress): a new landing, its quest not given
		System.SetQuestOpen(false);
		bQuestGiven = bRingClosed = bSaqrSpoken = false;
		Announced.Reset();
		CurrentStage = LastStage = NAME_None;
	}
	if (LastLevel <= 0)
	{
		SampleLevel();
		return;
	}
	// the game's own level math, on the XP he has EARNED (buying a track
	// never costs him a level)
	const int32 Level = GI->GetLevel();
	if (Level > LastLevel)
	{
		FArgs A;
		A.Level = Level;
		LevelBonus(LastLevel, Level, A.Hp, A.Mp);
		Say(EKind::LevelUp, NAME_None, A);
		const int32 RankWas = SaudMenu::Ladder::RankOf(LastLevel);
		const int32 Rank = GI->GetRankIndex();
		if (Rank > RankWas)
		{
			const char* Name = SaudMenu::Ladder::RankName(Rank);
			Put(A.Rank, 24, Name);
			Say(EKind::RankUp, FName(UTF8_TO_TCHAR(Name)), A);
		}
	}
	LastLevel = Level;
}

void USaudSystemSubsystem::HandleAbilityGranted(EAbility Ability)
{
	const FString Key = StaticEnum<EAbility>()->GetNameStringByValue(static_cast<int64>(Ability));
	FArgs A;
	Put(A.Skill, 24, TCHAR_TO_UTF8(*Key.ToUpper()));   // for a talent with no line of its own
	Say(EKind::SkillAcquired, FName(*Key), A);
}

void USaudSystemSubsystem::HandleGateOpened(FName /*GateId*/, AAbilityGate* Gate)
{
	FArgs A;
	if (Gate && Gate->RewardAbility == EAbility::None && Gate->RewardExperience > 0)
	{
		A.Xp = Gate->RewardExperience;
		Say(EKind::GateCleared, FName(Experience), A);
	}
	else
	{
		Say(EKind::GateCleared, NAME_None, A);
	}
	// the flash is where the gate is, now (the toast follows in the queue)
	if (USaudLookSubsystem* Look = Gate ? USaudLookSubsystem::Get(Gate) : nullptr)
	{
		Look->OnSystemEvent(SaudAnime::ESystemFx::GateOpened, Gate);
	}
}

/* ------------------------------------------------------------- the world */

void USaudSystemSubsystem::DirectorTick(const AWaveDirector* Director)
{
	USaudSystemSubsystem* Self = Director ? Get(Director) : nullptr;
	const APawn* Player = Self ? UGameplayStatics::GetPlayerPawn(Director, 0) : nullptr;
	if (Player && Director->Contains(Player->GetActorLocation()))
	{
		Self->PlayerIn(Director->StageRow);
	}
}

void USaudSystemSubsystem::PlayerIn(FName Stage)
{
	if (Stage == CurrentStage || !Lines.Contains(FName(*(FString(TEXT("StageEntered_")) + Stage.ToString()))))
	{
		return;   // the same area, or not one of the Halqa's (the prologue)
	}
	USaudGameInstance* GI = Game();
	if (!GI)
	{
		return;
	}
	SampleLevel();
	LastStage = CurrentStage;
	CurrentStage = Stage;
	const FSaudProgress& P = GI->GetProgress();
	const bool bWon = GI->HasWonTheTitle();   // AL-HALQA cleared: the quest is gone

	// FIND THE WAY UP: given at the first landing, open the whole game
	if (bWon)
	{
		System.SetQuestOpen(false);
	}
	else if (!System.bQuestOpen && !bQuestGiven)
	{
		if (Stage == FName(Souq) && IsFresh())
		{
			Say(EKind::QuestGiven, NAME_None);
			bQuestGiven = true;
		}
		else
		{
			System.SetQuestOpen(true);   // a profile that landed before
		}
	}
	// the ring closes: west out of the desert is the souq, with fire in his hands
	if (Stage == FName(Souq) && LastStage == FName(Desert) && !bWon && !bRingClosed && GI->HasAbility(EAbility::HawkFist))
	{
		Say(EKind::QuestUpdated, NAME_None);
		bRingClosed = true;
	}
	// the area's own quest, while it is not cleared, once a session
	if (!P.ClearedStages.Contains(Stage) && !Announced.Contains(Stage))
	{
		Announced.Add(Stage);
		Say(EKind::StageEntered, Stage);
	}
}

void USaudSystemSubsystem::BossWave(const AWaveDirector* Director, FName Row)
{
	USaudSystemSubsystem* Self = Director ? Get(Director) : nullptr;
	if (!Self)
	{
		return;
	}
	// the HUD's own WARNING says it; the System holds its lane meanwhile
	Self->System.Push(MakeEvent(EKind::BossWarning, TCHAR_TO_UTF8(*Row.ToString()), FLines(), FArgs()));
	// AL-SAQR, before his fight, once: the line Saud does not hear
	const USaudGameInstance* GI = Self->Game();
	if (Row == FName(Saqr) && !Self->bSaqrSpoken && GI && !GI->GetProgress().ClearedStages.Contains(FName(SaqrStage)))
	{
		Self->bSaqrSpoken = true;
		Self->Say(EKind::Speaker, FName(Saqr));
	}
}

void USaudSystemSubsystem::StageCleared(const UObject* WorldContext, FName StageRow, int32 Earned)
{
	USaudSystemSubsystem* Self = Get(WorldContext);
	const FSaudSystemLine* Quest = Self ? Self->Line(EKind::StageEntered, StageRow) : nullptr;
	if (!Quest || Quest->Key != StageRow)
	{
		return;   // not one of the Halqa's areas
	}
	if (StageRow == FName(Arena))
	{
		// AL-WAHSH: the quest is not completed. It is removed -- once (the
		// title won, ClearedStages holds AlHalqa now: HasWonTheTitle; a
		// rematch after it says nothing).
		if (Self->System.bQuestOpen)
		{
			Self->Say(EKind::QuestRemoved, NAME_None);
		}
		return;
	}
	FArgs A;
	A.Xp = Earned;
	PutT(A.Quest, HeadMax, Quest->Head);
	Self->Say(EKind::QuestComplete, StageRow, A);
}

void USaudSystemSubsystem::WentDown(const UObject* WorldContext)
{
	if (USaudSystemSubsystem* Self = Get(WorldContext))
	{
		Self->Say(EKind::Down, NAME_None);
	}
}

/* --------------------------------------------------------------- the HUD */

void USaudSystemSubsystem::Advance(float RealSeconds, float WorldSeconds, UWorld* World)
{
	if (World != LastWorld.Get())
	{
		// a new level: the profile may have been loaded under the title
		LastWorld = World;
		SampleLevel();
	}
	FClock Clock;
	Clock.Real = RealSeconds;
	Clock.World = WorldSeconds;
	System.Tick(Clock);
	USaudLookSubsystem* Look = World ? USaudLookSubsystem::Get(World) : nullptr;
	if (!Look)
	{
		return;
	}
	const APawn* Player = UGameplayStatics::GetPlayerPawn(World, 0);
	for (int32 i = 0; i < System.NumOpened; ++i)
	{
		const SaudAnime::ESystemFx Fx = FxFor(System.Opened[i]);
		if (Fx == SaudAnime::ESystemFx::None)
		{
			continue;
		}
		EAbility Skill = EAbility::None;
		if (System.Opened[i] == EKind::SkillAcquired)
		{
			const int64 V = StaticEnum<EAbility>()->GetValueByNameString(UTF8_TO_TCHAR(System.Window.E.Key));
			Skill = V == INDEX_NONE ? EAbility::None : static_cast<EAbility>(V);
		}
		Look->OnSystemEvent(Fx, Player, Skill);
	}
}
