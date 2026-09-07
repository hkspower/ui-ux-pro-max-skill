#pragma once

#include "CoreMinimal.h"
#include "Abilities/GameplayAbility.h"
#include "Gameplay/AhmedAbilitySystemComponent.h"
#include "AhmedGameplayAbility.generated.h"

class AFighterBase;
class UAhmedAttributeSet;

/**
 * What every ability in the game shares.
 *
 * Two things:
 *
 *   It declares its own button. The grant site does not decide what Punch
 *   does; the ability says it is a Punch ability and the component binds it.
 *
 *   It knows its fighter. Almost every ability needs the avatar as a
 *   AFighterBase and its attributes, and doing that cast once here is the
 *   difference between an ability being about the move and an ability being
 *   about getting hold of things.
 */
UCLASS(Abstract)
class AHMEDFIGHTER_API UAhmedGameplayAbility : public UGameplayAbility
{
	GENERATED_BODY()

public:
	UAhmedGameplayAbility();

	/** The button this answers to. Read off the CDO when the ability is granted. */
	UPROPERTY(EditDefaultsOnly, Category = "Ahmed|Input")
	EAhmedAbilityInput AbilityInput = EAhmedAbilityInput::None;

	/** Activate the moment the button goes down, without waiting for the
	    ability system's next tick. What a fighting game needs from its inputs. */
	UPROPERTY(EditDefaultsOnly, Category = "Ahmed|Input")
	bool bActivateOnInputPressed = true;

protected:
	UFUNCTION(BlueprintPure, Category = "Ahmed")
	AFighterBase* GetFighter() const;

	UFUNCTION(BlueprintPure, Category = "Ahmed")
	UAhmedAbilitySystemComponent* GetAhmedASC() const;

	UFUNCTION(BlueprintPure, Category = "Ahmed")
	const UAhmedAttributeSet* GetAttributes() const;

	/** Add a state tag for as long as this ability runs, and take it off on
	    exit however the ability ends. Doing this by hand is how a fighter ends
	    up permanently "attacking" after a cancelled swing. */
	void PushStateTag(FGameplayTag Tag);

	virtual void EndAbility(const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayAbilityActivationInfo ActivationInfo,
		bool bReplicateEndAbility, bool bWasCancelled) override;

private:
	FGameplayTagContainer PushedTags;
};
