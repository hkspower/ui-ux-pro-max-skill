#pragma once

#include "CoreMinimal.h"
#include "Gameplay/AhmedGameplayAbility.h"
#include "AhmedAttackAbility.generated.h"

class UAhmedAttackData;
class UGameplayEffect;
class AFighterBase;

/**
 * Every strike in the game, driven by a UAhmedAttackData.
 *
 * The port had this as a hand-rolled state machine on AFighterBase, ticking
 * an elapsed time and comparing it against three floats. That works for one
 * fighter with five moves and stops working the moment a strike needs to cost
 * mana, or scale with a talent, or be cancelled into by another strike — each
 * of which meant another branch in the same tick function.
 *
 * As an ability the same three windows are a timeline the system owns, and
 * the things that used to be branches become tags: the ability blocks itself
 * on `State_Busy`, spends its cost as an effect, and asks whether HAWK FIST
 * is lit by testing a tag rather than by reading a bool off the character.
 *
 * The chain is the same idea. `NextInChain` points at the follow-up, and
 * pressing Punch during the recovery window activates it, which is why a jab
 * becomes a cross becomes a hook without a combo counter existing anywhere.
 */
UCLASS()
class AHMEDFIGHTER_API UAhmedAttackAbility : public UAhmedGameplayAbility
{
	GENERATED_BODY()

public:
	UAhmedAttackAbility();

	/** The move. Everything below reads from it. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Attack")
	TObjectPtr<UAhmedAttackData> Attack;

	/** The next strike of the chain, if the button comes again in recovery. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Attack")
	TSubclassOf<UAhmedAttackAbility> NextInChain;

	/** Applied to whatever it hits. Carries the damage by SetByCaller so one
	    effect asset serves every strike in the game. */
	UPROPERTY(EditDefaultsOnly, Category = "Attack")
	TSubclassOf<UGameplayEffect> DamageEffect;

	/** Applied to the attacker: the stamina and mana it costs. */
	UPROPERTY(EditDefaultsOnly, Category = "Attack")
	TSubclassOf<UGameplayEffect> CostEffect;

	virtual bool CanActivateAbility(const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayTagContainer* SourceTags,
		const FGameplayTagContainer* TargetTags,
		FGameplayTagContainer* OptionalRelevantTags) const override;

	virtual void ActivateAbility(const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayAbilityActivationInfo ActivationInfo,
		const FGameplayEventData* TriggerEventData) override;

	virtual void InputPressed(const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayAbilityActivationInfo ActivationInfo) override;

protected:
	/** Windows, in order. Each schedules the next. */
	void EnterActive();
	void EnterRecovery();
	void FinishAttack();

	/** Sweep the strip in front of the fighter and apply the damage effect to
	    everything the move is allowed to reach. */
	void ResolveHits();

	/** True when HAWK FIST is lit and this strike is a punch. Kicks stay cold
	    -- that is the talent's whole shape. */
	bool IsBurning() const;

	/** Multiplier from the attacker's attributes for this strike's family. */
	float FamilyMultiplier() const;

private:
	FTimerHandle WindowTimer;
	/** One target per swing, unless the move is multi-hit. */
	TArray<TWeakObjectPtr<AFighterBase>> HitThisSwing;
	/** The button came again during recovery: chain instead of ending. */
	bool bChainQueued = false;
};
