#pragma once

#include "CoreMinimal.h"
#include "Abilities/GameplayAbility.h"
#include "Gameplay/SaudAbilitySystemComponent.h"
#include "SaudGameplayAbility.generated.h"

class AFighterBase;
class USaudAttributeSet;

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
class SAUDFIGHTER_API USaudGameplayAbility : public UGameplayAbility
{
	GENERATED_BODY()

public:
	USaudGameplayAbility();

	/** The button this answers to. Read off the CDO when the ability is granted. */
	UPROPERTY(EditDefaultsOnly, Category = "Saud|Input")
	ESaudAbilityInput AbilityInput = ESaudAbilityInput::None;

	/** Activate the moment the button goes down, without waiting for the
	    ability system's next tick. What a fighting game needs from its inputs. */
	UPROPERTY(EditDefaultsOnly, Category = "Saud|Input")
	bool bActivateOnInputPressed = true;

protected:
	UFUNCTION(BlueprintPure, Category = "Saud")
	AFighterBase* GetFighter() const;

	UFUNCTION(BlueprintPure, Category = "Saud")
	USaudAbilitySystemComponent* GetSaudASC() const;

	UFUNCTION(BlueprintPure, Category = "Saud")
	const USaudAttributeSet* GetAttributes() const;

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
