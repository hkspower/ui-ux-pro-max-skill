#include "Game/AhmedGameMode.h"

#include "Combat/AhmedCharacter.h"
#include "Game/AhmedGameInstance.h"
#include "Kismet/GameplayStatics.h"
#include "World/WaveDirector.h"

AAhmedGameMode::AAhmedGameMode()
{
	DefaultPawnClass = AAhmedCharacter::StaticClass();
	PrimaryActorTick.bCanEverTick = false;
}

void AAhmedGameMode::BeginPlay()
{
	Super::BeginPlay();

	Director = AWaveDirector::Get(GetWorld());
	if (Director)
	{
		Director->OnStageCleared.AddDynamic(this, &AAhmedGameMode::HandleStageCleared);
		Director->OnStageFailed.AddDynamic(this, &AAhmedGameMode::HandleStageFailed);
	}

	if (UAhmedGameInstance* GI = GetGameInstance<UAhmedGameInstance>())
	{
		++GI->GetMutableProgress().Stats.FightsStarted;
	}
}

FName AAhmedGameMode::ScoreStage(int32 Kills, int32 BestCombo, float HealthFraction, float Seconds) const
{
	float Score = Kills * 12.f + BestCombo * 22.f + HealthFraction * 320.f - Seconds * 1.1f;

	if (const UAhmedGameInstance* GI = GetGameInstance<UAhmedGameInstance>())
	{
		// Harder difficulties rank more generously — the fight itself was the tax.
		Score *= 0.8f + GI->GetProgress().DifficultyIndex * 0.2f;
	}

	if (Score > 620.f) return TEXT("S");
	if (Score > 470.f) return TEXT("A");
	if (Score > 330.f) return TEXT("B");
	return TEXT("C");
}

void AAhmedGameMode::HandleStageCleared()
{
	CompleteStage(Director ? Director->StageRow : NAME_None);
}

void AAhmedGameMode::HandleStageFailed()
{
	FailStage();
}

void AAhmedGameMode::CompleteStage(FName StageRow)
{
	UAhmedGameInstance* GI = GetGameInstance<UAhmedGameInstance>();
	if (!GI || !Director)
	{
		return;
	}

	const AAhmedCharacter* Player =
		Cast<AAhmedCharacter>(UGameplayStatics::GetPlayerPawn(GetWorld(), 0));

	const float HealthFrac = Player ? Player->GetHealthFraction() : 0.f;
	const int32 BestCombo  = Player ? Player->BestCombo : 0;

	const FName Rank = ScoreStage(Director->EnemiesDefeated, BestCombo,
		HealthFrac, Director->ElapsedTime);

	// A clear bonus on top of the experience the fights already paid.
	const int32 Bonus = 60 + BestCombo * 8 + FMath::RoundToInt(HealthFrac * 90.f);
	GI->AddExperience(Bonus);

	FAhmedProgress& P = GI->GetMutableProgress();
	P.ClearedStages.AddUnique(StageRow);
	P.BestCombo = FMath::Max(P.BestCombo, BestCombo);
	P.Stats.StagesCleared++;
	P.Stats.TimeInTheRing += Director->ElapsedTime;
	if (P.DifficultyIndex == 2)
	{
		P.Stats.ChampionClears++;
	}

	// Ranks only ever improve.
	static const TArray<FName> Order = { TEXT("S"), TEXT("A"), TEXT("B"), TEXT("C") };
	if (const FName* Existing = P.StageRanks.Find(StageRow))
	{
		if (Order.IndexOfByKey(Rank) < Order.IndexOfByKey(*Existing))
		{
			P.StageRanks.Add(StageRow, Rank);
		}
	}
	else
	{
		P.StageRanks.Add(StageRow, Rank);
	}

	GI->SaveProgress();
	BP_OnStageCleared(Rank, Director->ExperienceEarned + Bonus);
}

void AAhmedGameMode::FailStage()
{
	if (UAhmedGameInstance* GI = GetGameInstance<UAhmedGameInstance>())
	{
		GI->SaveProgress();
	}
	BP_OnStageFailed();
}
