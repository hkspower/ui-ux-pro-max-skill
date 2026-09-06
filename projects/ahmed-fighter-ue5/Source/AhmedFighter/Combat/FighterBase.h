#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "Combat/AhmedTypes.h"
#include "FighterBase.generated.h"

class UDataTable;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnFighterDamaged, float, NewHealth, const FHitResultData&, Hit);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnFighterDefeated, AFighterBase*, Fighter);

/**
 * Everything both the player and the enemies share: the attack state machine,
 * health, stamina, blocking, knockdown and hit resolution.
 *
 * Hits are resolved by an explicit facing/reach/depth test against the other
 * fighters rather than by physics overlaps. That is deliberate — the browser
 * original did the same, the results are frame-deterministic, and a beat-'em-up
 * wants forgiving, readable hitboxes rather than physically exact ones.
 */
UCLASS(Abstract)
class AHMEDFIGHTER_API AFighterBase : public ACharacter
{
	GENERATED_BODY()

public:
	AFighterBase();

	virtual void Tick(float DeltaSeconds) override;
	virtual void BeginPlay() override;

	// ---------------------------------------------------------------- combat

	/** Begins an attack if the current state allows it. Returns false if refused. */
	UFUNCTION(BlueprintCallable, Category = "Combat")
	bool StartAttack(FName AttackRow);

	/** Applies a landed blow. Called by the attacker, not the victim. */
	UFUNCTION(BlueprintCallable, Category = "Combat")
	FHitResultData ReceiveHit(AFighterBase* Attacker, const FAttackDef& Attack);

	UFUNCTION(BlueprintPure, Category = "Combat")
	bool IsBusy() const;

	UFUNCTION(BlueprintPure, Category = "Combat")
	bool IsAlive() const { return State != EFighterState::Dead; }

	UFUNCTION(BlueprintPure, Category = "Combat")
	float GetHealthFraction() const { return MaxHealth > 0.f ? Health / MaxHealth : 0.f; }

	/** +1 facing right along +X, -1 facing left. */
	UFUNCTION(BlueprintPure, Category = "Combat")
	float GetFacingSign() const { return FacingSign; }

	UFUNCTION(BlueprintCallable, Category = "Combat")
	void FaceTowards(const FVector& WorldLocation);

	/** Damage this fighter deals, before the victim's defences. */
	virtual float GetOutgoingDamageMultiplier(const FAttackDef& Attack) const;

	// ---------------------------------------------------------------- events

	UPROPERTY(BlueprintAssignable, Category = "Combat")
	FOnFighterDamaged OnDamaged;

	UPROPERTY(BlueprintAssignable, Category = "Combat")
	FOnFighterDefeated OnDefeated;

	// ------------------------------------------------------------- accessors

	UPROPERTY(BlueprintReadOnly, Category = "Combat")
	EFighterState State = EFighterState::Idle;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Combat")
	float MaxHealth = 100.f;

	UPROPERTY(BlueprintReadOnly, Category = "Combat")
	float Health = 100.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Combat")
	float MaxStamina = 100.f;

	UPROPERTY(BlueprintReadOnly, Category = "Combat")
	float Stamina = 100.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Combat")
	float PowerMultiplier = 1.f;

	UPROPERTY(BlueprintReadOnly, Category = "Combat")
	bool bBlocking = false;

	/** Bosses shrug off most knockdowns so they cannot be stunlocked. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Combat")
	bool bResistsKnockdown = false;

	/** Table the fighter's move names resolve against. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Combat")
	TObjectPtr<UDataTable> AttackTable = nullptr;

protected:
	/** Advances startup -> active -> recovery and fires the hitbox once. */
	void TickAttack(float DeltaSeconds);
	void TickTimers(float DeltaSeconds);

	/** Sweeps for valid targets during the active window. */
	virtual void ResolveAttackHits(const FAttackDef& Attack);

	/** Everything this fighter is allowed to hit. Overridden per side. */
	virtual void GatherTargets(TArray<AFighterBase*>& OutTargets) const;

	/** Gives subclasses a place to react without overriding ReceiveHit wholesale. */
	virtual void OnHitLanded(AFighterBase* Victim, const FHitResultData& Hit) {}
	virtual void OnKnockedDown() {}
	virtual void OnDeath();

	const FAttackDef* FindAttack(FName Row) const;

	/** Cosmetic hooks so Blueprints can add VFX and audio without C++ changes. */
	UFUNCTION(BlueprintImplementableEvent, Category = "Combat", meta = (DisplayName = "On Attack Started"))
	void BP_OnAttackStarted(FName AttackRow);

	UFUNCTION(BlueprintImplementableEvent, Category = "Combat", meta = (DisplayName = "On Hit Received"))
	void BP_OnHitReceived(const FHitResultData& Hit);

	UFUNCTION(BlueprintImplementableEvent, Category = "Combat", meta = (DisplayName = "On Defeated"))
	void BP_OnDefeated();

	// --------------------------------------------------------- runtime state

	FName CurrentAttackRow = NAME_None;
	const FAttackDef* CurrentAttack = nullptr;
	float AttackElapsed = 0.f;
	bool bAttackHitFired = false;

	/** Targets already struck by the current swing, so multi-hit never double-dips. */
	TArray<TWeakObjectPtr<AFighterBase>> HitThisSwing;

	float HitStunRemaining = 0.f;
	float DownRemaining = 0.f;
	float InvulnerableRemaining = 0.f;
	float FacingSign = 1.f;

	/** Set the frame block is pressed; a hit inside this window is a parry. */
	float ParryWindowRemaining = 0.f;
};
