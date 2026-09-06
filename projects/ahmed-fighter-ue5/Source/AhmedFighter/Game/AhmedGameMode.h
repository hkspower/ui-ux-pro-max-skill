#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "Combat/AhmedTypes.h"
#include "AhmedGameMode.generated.h"

class AWaveDirector;

/**
 * Scores a stage and writes the result into the profile. The rank formula is
 * the browser build's, unchanged: kills, best combo, health left and time, then
 * eased by difficulty so a Champion run is not punished for taking longer.
 */
UCLASS()
class AHMEDFIGHTER_API AAhmedGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	AAhmedGameMode();

	virtual void BeginPlay() override;

	UFUNCTION(BlueprintCallable, Category = "Stage")
	FName ScoreStage(int32 Kills, int32 BestCombo, float HealthFraction, float Seconds) const;

	UFUNCTION(BlueprintCallable, Category = "Stage")
	void CompleteStage(FName StageRow);

	UFUNCTION(BlueprintCallable, Category = "Stage")
	void FailStage();

	UFUNCTION(BlueprintImplementableEvent, Category = "Stage", meta = (DisplayName = "On Stage Cleared"))
	void BP_OnStageCleared(FName Rank, int32 ExperienceEarned);

	UFUNCTION(BlueprintImplementableEvent, Category = "Stage", meta = (DisplayName = "On Stage Failed"))
	void BP_OnStageFailed();

protected:
	/** Reads the ?ArriveAt / ?Health options an AAreaExit passes across. */
	void PlaceArrivingPlayer();

	UFUNCTION()
	void HandleStageCleared();

	UFUNCTION()
	void HandleStageFailed();

private:
	UPROPERTY()
	TObjectPtr<AWaveDirector> Director = nullptr;
};
