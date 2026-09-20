#include "Gameplay/SaudGameplayAbility.h"

#include "Combat/FighterBase.h"
#include "Gameplay/SaudAttributeSet.h"

USaudGameplayAbility::USaudGameplayAbility()
{
	// One fighter, one body, no prediction: instanced per actor is both the
	// cheapest and the only thing that lets an ability hold state across a
	// swing (which strike of the chain this is, what it has already hit).
	InstancingPolicy = EGameplayAbilityInstancingPolicy::InstancedPerActor;
	NetExecutionPolicy = EGameplayAbilityNetExecutionPolicy::LocalOnly;
}

AFighterBase* USaudGameplayAbility::GetFighter() const
{
	return CurrentActorInfo ? Cast<AFighterBase>(CurrentActorInfo->AvatarActor.Get()) : nullptr;
}

USaudAbilitySystemComponent* USaudGameplayAbility::GetSaudASC() const
{
	return CurrentActorInfo
		? Cast<USaudAbilitySystemComponent>(CurrentActorInfo->AbilitySystemComponent.Get())
		: nullptr;
}

const USaudAttributeSet* USaudGameplayAbility::GetAttributes() const
{
	const USaudAbilitySystemComponent* ASC = GetSaudASC();
	return ASC ? ASC->GetSet<USaudAttributeSet>() : nullptr;
}

void USaudGameplayAbility::PushStateTag(FGameplayTag Tag)
{
	if (!Tag.IsValid())
	{
		return;
	}
	if (USaudAbilitySystemComponent* ASC = GetSaudASC())
	{
		ASC->AddLooseGameplayTag(Tag);
		PushedTags.AddTag(Tag);
	}
}

void USaudGameplayAbility::EndAbility(const FGameplayAbilitySpecHandle Handle,
	const FGameplayAbilityActorInfo* ActorInfo,
	const FGameplayAbilityActivationInfo ActivationInfo,
	bool bReplicateEndAbility, bool bWasCancelled)
{
	// However this ended -- finished, cancelled, the fighter died mid-swing --
	// every tag it added comes off. This is the whole reason PushStateTag
	// exists rather than each ability remembering to clean up after itself.
	if (PushedTags.Num() > 0)
	{
		if (USaudAbilitySystemComponent* ASC = GetSaudASC())
		{
			ASC->RemoveLooseGameplayTags(PushedTags);
		}
		PushedTags.Reset();
	}
	Super::EndAbility(Handle, ActorInfo, ActivationInfo, bReplicateEndAbility, bWasCancelled);
}
