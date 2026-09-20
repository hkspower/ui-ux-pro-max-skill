#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "Combat/SaudTypes.h"
#include "SaudGameMode.generated.h"

class AWaveDirector;

/**
 * Scores a stage and writes the result into the profile. The rank formula is
 * the browser build's, unchanged: kills, best combo, health left and time, then
 * eased by difficulty so a Champion run is not punished for taking longer.
 */
UCLASS()
class SAUDFIGHTER_API ASaudGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	ASaudGameMode();

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
	/** The director of the district the player is in. A generated stage map
	    has one; an open-world map has one per district, and this follows him. */
	AWaveDirector* CurrentDirector() const;

	UPROPERTY()
	TObjectPtr<AWaveDirector> Director = nullptr;
};
