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
 * One director per district. The generated stage maps hold one each at the
 * origin; an open-world map laid out by Tools/fab/lay_out_world.py holds all
 * of them, each at its own district's origin, and every distance the stage
 * table speaks of is measured from that origin along world X. A director only
 * runs while the player is inside its district, so nine of them in one level
 * do not fight over him.
 */
UCLASS()
class AHMEDFIGHTER_API AWaveDirector : public AActor
{
	GENERATED_BODY()

public:
	AWaveDirector();

	virtual void Tick(float DeltaSeconds) override;
	virtual void BeginPlay() override;

	/** The director whose district the player is standing in; failing that
	    the nearest one, so a single-director level behaves as it always has. */
	static AWaveDirector* Get(const UWorld* World);

	/** Every director in the world, for a GameMode that has to listen to all. */
	static void GetAll(const UWorld* World, TArray<AWaveDirector*>& Out);

	/** Distance along the stage: world X relative to this district's origin. */
	UFUNCTION(BlueprintPure, Category = "Stage")
	float LocalX(const FVector& WorldLocation) const { return WorldLocation.X - GetActorLocation().X; }

	/** True inside this district's strip, with a step of margin either side. */
	UFUNCTION(BlueprintPure, Category = "Stage")
	bool Contains(const FVector& WorldLocation) const;

	/** How long the stage is, from its row; 0 until BeginPlay has read it. */
	UFUNCTION(BlueprintPure, Category = "Stage")
	float GetStageLength() const;

	/** Clamp the player and the live enemies to this district: the locked
	    arena while a wave is up, the whole strip otherwise. An AAreaExit
	    calls it for the district it has just stepped the player into. */
	UFUNCTION(BlueprintCallable, Category = "Stage")
	void ApplyArenaBounds();

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
