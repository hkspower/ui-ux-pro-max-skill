#include "Game/AhmedGameInstance.h"
#include "Gameplay/AhmedAbilitySystemComponent.h"
#include "Combat/FighterBase.h"
#include "Game/AhmedAudioSubsystem.h"

#include "Kismet/GameplayStatics.h"

void UAhmedGameInstance::Init()
{
	Super::Init();
	LoadProgress();
}

void UAhmedGameInstance::LoadProgress()
{
	if (UGameplayStatics::DoesSaveGameExist(SaveSlotName, 0))
	{
		if (const UAhmedSaveGame* Loaded =
			Cast<UAhmedSaveGame>(UGameplayStatics::LoadGameFromSlot(SaveSlotName, 0)))
		{
			Progress = Loaded->Progress;
			return;
		}
	}
	Progress = FAhmedProgress();		// a clean profile
}

void UAhmedGameInstance::SaveProgress()
{
	UAhmedSaveGame* Save = Cast<UAhmedSaveGame>(
		UGameplayStatics::CreateSaveGameObject(UAhmedSaveGame::StaticClass()));
	if (!Save)
	{
		return;
	}
	Save->Progress = Progress;
	UGameplayStatics::SaveGameToSlot(Save, SaveSlotName, 0);
}

void UAhmedGameInstance::ResetProgress()
{
	Progress = FAhmedProgress();
	UGameplayStatics::DeleteGameInSlot(SaveSlotName, 0);
	OnExperienceChanged.Broadcast(Progress.Experience);
}

void UAhmedGameInstance::AddExperience(int32 Amount)
{
	if (Amount == 0)
	{
		return;
	}
	Progress.Experience = FMath::Max(0, Progress.Experience + Amount);
	OnExperienceChanged.Broadcast(Progress.Experience);
}

bool UAhmedGameInstance::TryPurchaseUpgrade(FName TrackId)
{
	int32* Level = nullptr;
	if (TrackId == TEXT("Boxing"))        Level = &Progress.BoxingLevel;
	else if (TrackId == TEXT("Kicking"))  Level = &Progress.KickingLevel;
	else if (TrackId == TEXT("Vitality")) Level = &Progress.VitalityLevel;
	else if (TrackId == TEXT("Speed"))    Level = &Progress.SpeedLevel;
	else if (TrackId == TEXT("Stamina"))  Level = &Progress.StaminaLevel;

	if (!Level || *Level >= 5)
	{
		return false;
	}

	const int32 Cost = GetUpgradeCost(*Level);
	if (Progress.Experience < Cost)
	{
		return false;
	}

	Progress.Experience -= Cost;
	++(*Level);
	OnExperienceChanged.Broadcast(Progress.Experience);
	SaveProgress();
	return true;
}

bool UAhmedGameInstance::GrantAbility(EAbility Ability)
{
	if (Ability == EAbility::None || HasAbility(Ability))
	{
		return false;
	}
	Progress.Abilities.Add(Ability);

	// The save records it; the ability system is what makes it a move. The
	// tag is the same fact in the language the gameplay layer speaks.
	if (const UWorld* World = GetWorld())
	{
		if (APawn* Player = UGameplayStatics::GetPlayerPawn(World, 0))
		{
			if (AFighterBase* Fighter = Cast<AFighterBase>(Player))
			{
				if (UAhmedAbilitySystemComponent* ASC = Fighter->GetAhmedASC())
				{
					ASC->GrantTalent(AhmedTalents::TagFor(Ability));
				}
			}
		}
	}
	if (UAhmedAudioSubsystem* Audio = UAhmedAudioSubsystem::Get(this)) { Audio->PlayUI(TEXT("Talent_Found")); }
	OnAbilityGranted.Broadcast(Ability);
	return true;
}

void UAhmedGameInstance::MarkGateOpen(FName GateId)
{
	Progress.OpenGates.AddUnique(GateId);
}

FDifficultyDef UAhmedGameInstance::GetDifficulty() const
{
	// Rookie, Pro, Champion — the same three the browser build shipped with.
	// Built field by field rather than brace-initialised: GENERATED_BODY() means
	// a USTRUCT is not reliably an aggregate.
	FDifficultyDef Def;
	switch (FMath::Clamp(Progress.DifficultyIndex, 0, 2))
	{
	case 0:
		Def.DisplayName  = NSLOCTEXT("Ahmed", "Rookie", "ROOKIE");
		Def.EnemyDamage  = 0.62f;
		Def.EnemyHealth  = 0.78f;
		break;
	case 2:
		Def.DisplayName  = NSLOCTEXT("Ahmed", "Champion", "CHAMPION");
		Def.EnemyDamage  = 1.45f;
		Def.EnemyHealth  = 1.38f;
		break;
	default:
		Def.DisplayName  = NSLOCTEXT("Ahmed", "Pro", "PRO");
		Def.EnemyDamage  = 1.00f;
		Def.EnemyHealth  = 1.00f;
		break;
	}
	return Def;
}

void UAhmedGameInstance::CycleDifficulty()
{
	Progress.DifficultyIndex = (Progress.DifficultyIndex + 1) % 3;
	SaveProgress();
}

void UAhmedGameInstance::RecordSurvivalWave(int32 Wave)
{
	if (Wave > Progress.SurvivalBest)
	{
		Progress.SurvivalBest = Wave;
		SaveProgress();
	}
}
