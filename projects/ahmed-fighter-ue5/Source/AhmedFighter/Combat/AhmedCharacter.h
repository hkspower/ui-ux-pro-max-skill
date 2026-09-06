#pragma once

#include "CoreMinimal.h"
#include "Combat/FighterBase.h"
#include "AhmedCharacter.generated.h"

class UCameraComponent;
class USpringArmComponent;
class UInputAction;
class UInputMappingContext;
struct FInputActionValue;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnComboChanged, int32, ComboCount);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnRageChanged, float, RageFraction);

/**
 * Ahmed. Adds to the shared fighter: the three-punch chain, the dodge dash,
 * the parry window, the rage meter and its finisher, and the upgrade tracks.
 */
UCLASS()
class AHMEDFIGHTER_API AAhmedCharacter : public AFighterBase
{
	GENERATED_BODY()

public:
	AAhmedCharacter();

	virtual void Tick(float DeltaSeconds) override;
	virtual void BeginPlay() override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

	virtual float GetOutgoingDamageMultiplier(const FAttackDef& Attack) const override;

	/** Rebuilds max health, stamina and speed from the saved upgrade levels. */
	UFUNCTION(BlueprintCallable, Category = "Progression")
	void ApplyUpgrades();

	UFUNCTION(BlueprintPure, Category = "Combat")
	float GetRageFraction() const { return Rage / AhmedGameplay::RageMax; }

	UFUNCTION(BlueprintPure, Category = "Combat")
	bool IsRageReady() const { return Rage >= AhmedGameplay::RageMax; }

	UPROPERTY(BlueprintAssignable, Category = "Combat")
	FOnComboChanged OnComboChanged;

	UPROPERTY(BlueprintAssignable, Category = "Combat")
	FOnRageChanged OnRageChanged;

	UPROPERTY(BlueprintReadOnly, Category = "Combat")
	int32 ComboCount = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Combat")
	int32 BestCombo = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Combat")
	float Rage = 0.f;

	// ----------------------------------------------------------------- input

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputMappingContext> DefaultMappingContext = nullptr;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> MoveAction = nullptr;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> PunchAction = nullptr;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> KickAction = nullptr;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> BlockAction = nullptr;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> RageAction = nullptr;

	// ---------------------------------------------------------------- camera

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Camera")
	TObjectPtr<USpringArmComponent> CameraBoom = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Camera")
	TObjectPtr<UCameraComponent> SideViewCamera = nullptr;

	/** The arena clamps the player so fights never drift under the touch controls. */
	UFUNCTION(BlueprintCallable, Category = "Arena")
	void SetArenaBounds(float InMinX, float InMaxX);

protected:
	virtual void OnHitLanded(AFighterBase* Victim, const FHitResultData& Hit) override;
	virtual void GatherTargets(TArray<AFighterBase*>& OutTargets) const override;

	/** Strikes hit fighters first, then any sealed route standing in reach. */
	virtual void ResolveAttackHits(const FAttackDef& Attack) override;

	void Input_Move(const FInputActionValue& Value);
	void Input_Punch();
	void Input_Kick();
	void Input_BlockStarted();
	void Input_BlockReleased();
	void Input_Rage();

	/** Turns toward whichever enemy is nearest before committing to a strike. */
	void FaceNearestEnemy();

	/** Advances jab -> cross -> hook while taps stay inside the combo window. */
	FName NextPunchInChain();

	UFUNCTION(BlueprintImplementableEvent, Category = "Combat", meta = (DisplayName = "On Parry"))
	void BP_OnParry();

	UFUNCTION(BlueprintImplementableEvent, Category = "Combat", meta = (DisplayName = "On Rage Released"))
	void BP_OnRageReleased();

	/** Clears the per-swing gate list so one swing cannot count twice. */
	void BeginAttackBookkeeping();

private:
	FVector2D MoveInput = FVector2D::ZeroVector;

	/** Gates already struck by the current swing. */
	TArray<TWeakObjectPtr<class AAbilityGate>> StruckGatesThisSwing;

	int32 ChainStep = 0;
	float ChainWindowRemaining = 0.f;
	float ComboWindowRemaining = 0.f;
	float DashRemaining = 0.f;

	float ArenaMinX = -FLT_MAX;
	float ArenaMaxX =  FLT_MAX;

	float BaseWalkSpeed = 520.f;
};
