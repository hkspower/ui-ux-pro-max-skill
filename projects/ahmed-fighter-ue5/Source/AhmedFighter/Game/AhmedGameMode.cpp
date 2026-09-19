#include "Game/AhmedGameMode.h"

#include "Combat/AhmedArena.h"
#include "Combat/AhmedCharacter.h"
#include "Game/AhmedGameInstance.h"
#include "Kismet/GameplayStatics.h"
#include "World/WaveDirector.h"
#include "Engine/DataTable.h"

AAhmedGameMode::AAhmedGameMode()
{
	DefaultPawnClass = AAhmedCharacter::StaticClass();
	PrimaryActorTick.bCanEverTick = false;
}

void AAhmedGameMode::BeginPlay()
{
	Super::BeginPlay();

	// Listen to every director in the level: one on a stage map, nine on an
	// open-world map. Which one is speaking is the one the player is in.
	TArray<AWaveDirector*> Directors;
	AWaveDirector::GetAll(GetWorld(), Directors);
	for (AWaveDirector* D : Directors)
	{
		D->OnStageCleared.AddDynamic(this, &AAhmedGameMode::HandleStageCleared);
		D->OnStageFailed.AddDynamic(this, &AAhmedGameMode::HandleStageFailed);
	}
	Director = AWaveDirector::Get(GetWorld());

	UAhmedGameInstance* GI = GetGameInstance<UAhmedGameInstance>();
	if (GI)
	{
		++GI->GetMutableProgress().Stats.FightsStarted;
		if (Director)
		{
			FAhmedProgress& P = GI->GetMutableProgress();
			P.CurrentStage = Director->StageRow;
			P.VisitedStages.AddUnique(Director->StageRow);
		}
	}

	PlaceArrivingPlayer();
}

/**
 * The other half of AAreaExit. An exit opens the next level with options that
 * say which edge to appear at and what condition to arrive in, so walking
 * between areas is a step through a doorway rather than a fresh run.
 *
 * Since 2026-09-19 this reads a bearing, not an offset along X. A district
 * is round -- Tools/levels/build_levels.py and Tools/fab/lay_out_world.py
 * both put its West door on the rim at 180 degrees, its East door at 0, and
 * a Door link at 90 -- and PlayerStart already stands at the West door, so
 * arriving there needs nothing done to him. Arriving at East or Door means
 * finding that OTHER door on this district's own rim and stepping him onto
 * it, facing back toward the middle.
 */
void AAhmedGameMode::PlaceArrivingPlayer()
{
	AAhmedCharacter* Player = Cast<AAhmedCharacter>(UGameplayStatics::GetPlayerPawn(GetWorld(), 0));
	if (!Player)
	{
		return;
	}
	const FString Arrive = UGameplayStatics::ParseOption(OptionsString, TEXT("ArriveAt"));
	if (Arrive.IsEmpty() || Arrive == TEXT("West"))
	{
		return;		// PlayerStart already stands at the West door
	}

	if (Director)
	{
		if (const UDataTable* Table = Director->StageTable)
		{
			static const FString Context(TEXT("AAhmedGameMode::PlaceArrivingPlayer"));
			if (const FStageDef* Stage = Table->FindRow<FStageDef>(Director->StageRow, Context, false))
			{
				const float BearingDeg = (Arrive == TEXT("East")) ? 0.f : 90.f;	// Door
				const float Radians = FMath::DegreesToRadians(BearingDeg);
				const float Radius = AhmedArena::DistrictExtent(Stage->Length) - AhmedGameplay::ExitMargin;
				const FVector Origin = Director->GetActorLocation();

				FVector Loc = Player->GetActorLocation();
				Loc.X = Origin.X + FMath::Cos(Radians) * Radius;
				Loc.Y = Origin.Y + FMath::Sin(Radians) * Radius;
				Player->SetActorLocation(Loc);

				// Facing back the way he came: inward, toward the middle.
				const float FacingYaw = FMath::RadiansToDegrees(
					FMath::Atan2(-FMath::Sin(Radians), -FMath::Cos(Radians)));
				Player->SetActorRotation(FRotator(0.f, FacingYaw, 0.f));
			}
		}
	}

	const FString H = UGameplayStatics::ParseOption(OptionsString, TEXT("Health"));
	const FString S = UGameplayStatics::ParseOption(OptionsString, TEXT("Stamina"));
	const FString R = UGameplayStatics::ParseOption(OptionsString, TEXT("Rage"));
	if (!H.IsEmpty())
	{
		Player->SetCondition(FCString::Atof(*H), S.IsEmpty() ? Player->GetStamina() : FCString::Atof(*S));
	}
	if (!R.IsEmpty())
	{
		Player->Rage = FMath::Clamp(FCString::Atof(*R), 0.f, AhmedGameplay::RageMax);
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

AWaveDirector* AAhmedGameMode::CurrentDirector() const
{
	return AWaveDirector::Get(GetWorld());
}

void AAhmedGameMode::HandleStageCleared()
{
	Director = CurrentDirector();
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
