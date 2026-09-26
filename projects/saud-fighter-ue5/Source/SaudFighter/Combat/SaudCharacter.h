#pragma once

#include "CoreMinimal.h"
#include "Combat/FighterBase.h"
#include "Combat/SaudFire.h"
#include "SaudCharacter.generated.h"

class UCameraComponent;
class USpringArmComponent;
class UInputAction;
class UInputMappingContext;
struct FInputActionValue;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnComboChanged, int32, ComboCount);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnRageChanged, float, RageFraction);

/**
 * Saud. Adds to the shared fighter: the three-punch chain, the dodge dash,
 * the parry window, the rage meter and its finisher, and the upgrade tracks.
 */
UCLASS()
class SAUDFIGHTER_API ASaudCharacter : public AFighterBase
{
	GENERATED_BODY()

public:
	ASaudCharacter();

	virtual void Tick(float DeltaSeconds) override;
	virtual void BeginPlay() override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

	virtual float GetOutgoingDamageMultiplier(const FAttackDef& Attack) const override;
	virtual float GetBlockCostMultiplier(bool bPush) const override;
	virtual float GetAttackReachBonus(const FAttackDef& Attack) const override;
	virtual float GetAttackKnockbackBonus(const FAttackDef& Attack) const override;

	// ------------------------------------------------------------ HAWK FIST
	/*
	 * "Your punches carry fire. Burns MP, and only punches -- kicks stay
	 * cold." The rules and every number are the browser's, in
	 * Combat/SaudFire.h. On this path -- the state machine the fight runs
	 * on -- there was no mana and nothing burned; the ability path's
	 * USaudAttackAbility::IsBurning is still its own. Mana is kept here as
	 * Rage is: a number on the man, filled by the clock and by landing
	 * hits, spent by a burning punch when it lands.
	 */

	UFUNCTION(BlueprintPure, Category = "Combat")
	float GetMana() const { return Mana; }

	UFUNCTION(BlueprintPure, Category = "Combat")
	float GetManaFraction() const { return Mana / SaudFire::MaxMana; }

	/** hawkReady(): HAWK FIST carried and the MP to burn. */
	UFUNCTION(BlueprintPure, Category = "Combat")
	bool IsHawkLit() const;

	/** How bright the flame on his fist is drawn, 0 for none: the eased
	    lit-ness, brighter through a punch. */
	UFUNCTION(BlueprintPure, Category = "Combat")
	float GetHawkHeat() const;

	/** Which fist the flame is on and the forearm behind it (the flame
	    points along it), as bone names: the lead fist, or the one a punch
	    is thrown with. */
	void GetFlameBones(FName& OutHand, FName& OutForearm) const;

	const SaudFire::FState& GetFire() const { return Fire; }

	/** Rebuilds max health, stamina and speed from the saved upgrade levels. */
	UFUNCTION(BlueprintCallable, Category = "Progression")
	void ApplyUpgrades();

	UFUNCTION(BlueprintPure, Category = "Combat")
	float GetRageFraction() const { return Rage / SaudGameplay::RageMax; }

	UFUNCTION(BlueprintPure, Category = "Combat")
	bool IsRageReady() const { return Rage >= SaudGameplay::RageMax; }

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

	/** Right stick or mouse: the boom the player swings and pitches. On the
	    strip there was nothing to bind this to — the camera looked one way
	    for the whole game. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> LookAction = nullptr;

	// ---------------------------------------------------------------- camera

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Camera")
	TObjectPtr<USpringArmComponent> CameraBoom = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Camera")
	TObjectPtr<UCameraComponent> FollowCamera = nullptr;

	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Camera")
	float CameraTurnRate = 150.f;

	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Camera")
	float CameraPitchRate = 90.f;

	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Camera")
	float CameraMinPitch = -55.f;

	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Camera")
	float CameraMaxPitch = 8.f;

	/** Which way the boom is looking. Movement is measured against this, so
	    pushing the stick away from the player means away on screen. */
	UFUNCTION(BlueprintPure, Category = "Camera")
	float GetCameraYaw() const { return CameraYaw; }

	/**
	 * Where this fighter may stand: a circle, since 2026-09-16.
	 *
	 * It was two numbers on X with the depth fixed for the whole game,
	 * because a corridor has a near end and a far end and nothing else. An
	 * arena in the open is the same size in every direction — any other
	 * shape tells the player which way the level used to run.
	 */
	UFUNCTION(BlueprintCallable, Category = "Arena")
	void SetArenaCircle(const FVector& InCentre, float InRadius);

protected:
	virtual void OnHitLanded(AFighterBase* Victim, const FHitResultData& Hit) override;
	virtual void OnAttackStarted(const FAttackDef& Attack) override;
	virtual void GatherTargets(TArray<AFighterBase*>& OutTargets) const override;

	/** Strikes hit fighters first, then any sealed route standing in reach. */
	virtual void ResolveAttackHits(const FAttackDef& Attack) override;

	void Input_Move(const FInputActionValue& Value);
	void Input_Look(const FInputActionValue& Value);
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
	FVector2D LookInput = FVector2D::ZeroVector;

	/** Gates already struck by the current swing. */
	TArray<TWeakObjectPtr<class AAbilityGate>> StruckGatesThisSwing;

	int32 ChainStep = 0;
	float ChainWindowRemaining = 0.f;
	float ComboWindowRemaining = 0.f;
	float DashRemaining = 0.f;

	FVector ArenaCentre = FVector::ZeroVector;
	float ArenaRadius = FLT_MAX;

	float CameraYaw = 0.f;
	float CameraPitch = -18.f;

	float BaseWalkSpeed = 520.f;

	/** HAWK FIST: the MP (the browser's p.mp), the flame and the burst's
	    clock, whether this swing burns (decided when it starts, as
	    hawkAttack() does) and whether it has spent its MP yet (once per
	    swing, on the first man it lands on: applyHit's hawkSwing). */
	float Mana = SaudFire::MaxMana;
	SaudFire::FState Fire;
	bool bAttackBurning = false;
	bool bHawkSpent = false;
};
