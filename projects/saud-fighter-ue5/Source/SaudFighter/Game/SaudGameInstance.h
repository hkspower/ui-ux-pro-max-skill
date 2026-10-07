#pragma once

#include "CoreMinimal.h"
#include "Engine/GameInstance.h"
#include "Combat/SaudTypes.h"
#include "Game/SaudSaveGame.h"
#include "SaudGameInstance.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnAbilityGranted, EAbility, Ability);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnExperienceChanged, int32, NewTotal);

/**
 * Owns the player profile across levels: progression, abilities, opened gates,
 * difficulty and settings, plus load and save.
 */
UCLASS()
class SAUDFIGHTER_API USaudGameInstance : public UGameInstance
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
	const FSaudProgress& GetProgress() const { return Progress; }

	UFUNCTION(BlueprintCallable, Category = "Progress")
	FSaudProgress& GetMutableProgress() { return Progress; }

	UFUNCTION(BlueprintCallable, Category = "Progress")
	void AddExperience(int32 Amount);

	/** Buys the next level of a track. TrackId is DT_Upgrades' own Track
	    id -- Box, Kick, Vit, Spd, Stam, Iron -- (the long Boxing, Kicking,
	    Vitality, Speed, Stamina it expected until 2026-10-07 still work):
	    SaudMenu::Train::TrackOf. Returns false when the id is no track's,
	    the track is maxed or the player cannot afford it. The training
	    screen (USaudMenuSubsystem) calls it. */
	UFUNCTION(BlueprintCallable, Category = "Progress")
	bool TryPurchaseUpgrade(FName TrackId);

	/** XP for the level after CurrentLevel: the browser's cost(lvl), through
	    SaudMenu::Train (held to DT_Upgrades.csv by the harness). */
	UFUNCTION(BlueprintPure, Category = "Progress")
	int32 GetUpgradeCost(int32 CurrentLevel) const;

	/** What the six tracks have cost so far. */
	UFUNCTION(BlueprintPure, Category = "Progress")
	int32 GetSpentExperience() const;

	/** Every XP ever earned: the spendable (Progress.Experience) plus what
	    training has cost -- training is the one thing XP is spent on. It
	    drives the level, so buying a level of a track never costs one of
	    his (the browser's xpTotal against its xp). */
	UFUNCTION(BlueprintPure, Category = "Progress")
	int32 GetEarnedExperience() const { return Progress.Experience + GetSpentExperience(); }

	/** His level, 1..20, on the Halqa's ladder (SaudMenu::Ladder, held to
	    DT_Levels.csv), from the earned XP; and its rank, 0 ROOKIE .. 5
	    CHAMPION. */
	UFUNCTION(BlueprintPure, Category = "Progress")
	int32 GetLevel() const;

	UFUNCTION(BlueprintPure, Category = "Progress")
	int32 GetRankIndex() const;

	/** Whether the title is won: AL-HALQA, the arena, among the cleared
	    stages (ASaudGameMode::CompleteStage). The quest FIND THE WAY UP is
	    open until then. */
	UFUNCTION(BlueprintPure, Category = "Progress")
	bool HasWonTheTitle() const;

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
	FString SaveSlotName = TEXT("SaudProfile");

private:
	UPROPERTY()
	FSaudProgress Progress;
};
