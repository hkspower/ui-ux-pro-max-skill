#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Combat/AhmedTypes.h"
#include "AbilityGate.generated.h"

class UBoxComponent;
class UStaticMeshComponent;

DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnGateOpened);

/**
 * A sealed route. Ledges and gaps open by reaching them with the right
 * traversal ability; shutters and cracked walls take three strikes of the
 * matching family.
 *
 * Gates never block the way forward — place them off the critical path, set
 * into the back wall. A stage must stay completable whatever the player
 * carries, otherwise finding an ability late can soft-lock the run.
 */
UCLASS()
class AHMEDFIGHTER_API AAbilityGate : public AActor
{
	GENERATED_BODY()

public:
	AAbilityGate();

	virtual void Tick(float DeltaSeconds) override;
	virtual void BeginPlay() override;

	/** Called by the player's strike resolution. Returns true if it counted. */
	UFUNCTION(BlueprintCallable, Category = "Gate")
	bool ReceiveStrike(EAttackFamily Family);

	UFUNCTION(BlueprintPure, Category = "Gate")
	bool IsOpen() const { return bOpen; }

	/** Which ability this gate wants, derived from its type. */
	UFUNCTION(BlueprintPure, Category = "Gate")
	EAbility GetRequiredAbility() const;

	/** True when the player already carries the key. */
	UFUNCTION(BlueprintPure, Category = "Gate")
	bool CanBeOpened() const;

	UPROPERTY(BlueprintAssignable, Category = "Gate")
	FOnGateOpened OnGateOpened;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gate")
	EGateType GateType = EGateType::Wall;

	/** Granted on opening. None means this gate pays experience instead. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gate")
	EAbility RewardAbility = EAbility::None;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gate")
	int32 RewardExperience = 0;

	/** Stable id so the opened state survives leaving and re-entering the level. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gate")
	FName GateId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gate", meta = (ClampMin = "1"))
	int32 StrikesToBreak = 3;

protected:
	void Open();

	UFUNCTION(BlueprintImplementableEvent, Category = "Gate", meta = (DisplayName = "On Opened"))
	void BP_OnOpened();

	UFUNCTION(BlueprintImplementableEvent, Category = "Gate", meta = (DisplayName = "On Struck"))
	void BP_OnStruck(int32 StrikesLanded);

	/** Drives the on-screen prompt: shown when the player is close enough. */
	UPROPERTY(BlueprintReadOnly, Category = "Gate")
	bool bPlayerNearby = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Gate")
	TObjectPtr<UStaticMeshComponent> Mesh = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Gate")
	TObjectPtr<UBoxComponent> Trigger = nullptr;

private:
	bool bOpen = false;
	int32 StrikesLanded = 0;
	float ApproachHeld = 0.f;
};
