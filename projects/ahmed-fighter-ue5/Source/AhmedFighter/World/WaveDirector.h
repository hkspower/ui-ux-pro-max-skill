#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Combat/AhmedTypes.h"
#include "WaveDirector.generated.h"

class AAhmedCharacter;
class AEnemyFighter;
class UDataTable;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnWaveStarted, int32, WaveIndex);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnWaveCleared, int32, WaveIndex);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnStageCleared);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnStageFailed);

/**
 * Runs a stage: gates the player into locked waves, spawns them, hands out the
 * attack tokens that keep crowds fair, and decides when the stage is finished.
 *
 * One director per level. Place it in the map, or let the GameMode spawn it.
 */
UCLASS()
class AHMEDFIGHTER_API AWaveDirector : public AActor
{
	GENERATED_BODY()

public:
	AWaveDirector();

	virtual void Tick(float DeltaSeconds) override;
	virtual void BeginPlay() override;

	/** The single director for this world, or null. */
	static AWaveDirector* Get(const UWorld* World);

	/** Fair-crowd rule: only a couple of enemies may be swinging at any moment. */
	UFUNCTION(BlueprintCallable, Category = "Waves")
	bool TryClaimAttackToken(AEnemyFighter* Claimant);

	UFUNCTION(BlueprintCallable, Category = "Waves")
	void ReleaseAttackToken(AEnemyFighter* Claimant);

	UFUNCTION(BlueprintPure, Category = "Waves")
	bool IsArenaLocked() const { return bArenaLocked; }

	UFUNCTION(BlueprintPure, Category = "Waves")
	int32 GetWaveIndex() const { return WaveIndex; }

	UPROPERTY(BlueprintAssignable, Category = "Waves") FOnWaveStarted OnWaveStarted;
	UPROPERTY(BlueprintAssignable, Category = "Waves") FOnWaveCleared OnWaveCleared;
	UPROPERTY(BlueprintAssignable, Category = "Waves") FOnStageCleared OnStageCleared;
	UPROPERTY(BlueprintAssignable, Category = "Waves") FOnStageFailed  OnStageFailed;

	/** Row in the stage table this level represents. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Stage")
	FName StageRow;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Stage")
	TObjectPtr<UDataTable> StageTable = nullptr;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Stage")
	TObjectPtr<UDataTable> FighterTable = nullptr;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Stage")
	TObjectPtr<UDataTable> AttackTable = nullptr;

	/** Fallback pawn when an archetype row leaves PawnClass empty. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Stage")
	TSubclassOf<AEnemyFighter> DefaultEnemyClass;

	UPROPERTY(BlueprintReadOnly, Category = "Stage")
	int32 EnemiesDefeated = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Stage")
	int32 ExperienceEarned = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Stage")
	float ElapsedTime = 0.f;

protected:
	void BeginWave(const FWaveDef& Wave);
	void SpawnFighter(FName Row, int32 Tier, int32 IndexInWave, int32 WaveSize);
	int32 CountLivingEnemies() const;
	void ApplyArenaBounds();

	/** Endless mode builds its own waves, growing in size and tier. */
	FWaveDef MakeSurvivalWave(int32 WaveNumber) const;

	UFUNCTION()
	void HandleEnemyDefeated(AFighterBase* Fighter);

private:
	const FStageDef* Stage = nullptr;
	TArray<FWaveDef> Waves;

	int32 WaveIndex = 0;
	int32 SurvivalWave = 1;
	bool bArenaLocked = false;
	bool bFinished = false;

	float ArenaOriginX = 0.f;

	UPROPERTY() TArray<TObjectPtr<AEnemyFighter>> LiveEnemies;
	UPROPERTY() TArray<TObjectPtr<AEnemyFighter>> AttackTokenHolders;
};
