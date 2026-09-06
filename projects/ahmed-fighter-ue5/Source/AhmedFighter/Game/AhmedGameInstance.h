#pragma once

#include "CoreMinimal.h"
#include "Engine/GameInstance.h"
#include "Combat/AhmedTypes.h"
#include "Game/AhmedSaveGame.h"
#include "AhmedGameInstance.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnAbilityGranted, EAbility, Ability);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnExperienceChanged, int32, NewTotal);

/**
 * Owns the player profile across levels: progression, abilities, opened gates,
 * difficulty and settings, plus load and save.
 */
UCLASS()
class AHMEDFIGHTER_API UAhmedGameInstance : public UGameInstance
{
	GENERATED_BODY()

public:
	virtual void Init() override;

	// ------------------------------------------------------------ progression

	UFUNCTION(BlueprintCallable, Category = "Progress")
	void LoadProgress();

	UFUNCTION(BlueprintCallable, Category = "Progress")
	void SaveProgress();

	UFUNCTION(BlueprintCallable, Category = "Progress")
	void ResetProgress();

	UFUNCTION(BlueprintPure, Category = "Progress")
	const FAhmedProgress& GetProgress() const { return Progress; }

	UFUNCTION(BlueprintCallable, Category = "Progress")
	FAhmedProgress& GetMutableProgress() { return Progress; }

	UFUNCTION(BlueprintCallable, Category = "Progress")
	void AddExperience(int32 Amount);

	/** Returns false when the track is maxed or the player cannot afford it. */
	UFUNCTION(BlueprintCallable, Category = "Progress")
	bool TryPurchaseUpgrade(FName TrackId);

	UFUNCTION(BlueprintPure, Category = "Progress")
	int32 GetUpgradeCost(int32 CurrentLevel) const { return 120 + CurrentLevel * 130; }

	// -------------------------------------------------------------- abilities

	UFUNCTION(BlueprintPure, Category = "Abilities")
	bool HasAbility(EAbility Ability) const { return Progress.Abilities.Contains(Ability); }

	UFUNCTION(BlueprintCallable, Category = "Abilities")
	bool GrantAbility(EAbility Ability);

	UPROPERTY(BlueprintAssignable, Category = "Abilities")
	FOnAbilityGranted OnAbilityGranted;

	UPROPERTY(BlueprintAssignable, Category = "Progress")
	FOnExperienceChanged OnExperienceChanged;

	// ------------------------------------------------------------------ gates

	UFUNCTION(BlueprintPure, Category = "Gates")
	bool IsGateOpen(FName GateId) const { return Progress.OpenGates.Contains(GateId); }

	UFUNCTION(BlueprintCallable, Category = "Gates")
	void MarkGateOpen(FName GateId);

	// ------------------------------------------------------------- difficulty

	UFUNCTION(BlueprintPure, Category = "Settings")
	FDifficultyDef GetDifficulty() const;

	UFUNCTION(BlueprintCallable, Category = "Settings")
	void CycleDifficulty();

	// -------------------------------------------------------------- survival

	UFUNCTION(BlueprintCallable, Category = "Progress")
	void RecordSurvivalWave(int32 Wave);

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Save")
	FString SaveSlotName = TEXT("AhmedProfile");

private:
	UPROPERTY()
	FAhmedProgress Progress;
};
