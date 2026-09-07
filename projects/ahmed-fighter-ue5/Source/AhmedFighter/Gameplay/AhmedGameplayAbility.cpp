#include "Gameplay/AhmedGameplayAbility.h"

#include "Combat/FighterBase.h"
#include "Gameplay/AhmedAttributeSet.h"

UAhmedGameplayAbility::UAhmedGameplayAbility()
{
	// One fighter, one body, no prediction: instanced per actor is both the
	// cheapest and the only thing that lets an ability hold state across a
	// swing (which strike of the chain this is, what it has already hit).
	InstancingPolicy = EGameplayAbilityInstancingPolicy::InstancedPerActor;
	NetExecutionPolicy = EGameplayAbilityNetExecutionPolicy::LocalOnly;
}

AFighterBase* UAhmedGameplayAbility::GetFighter() const
{
	return CurrentActorInfo ? Cast<AFighterBase>(CurrentActorInfo->AvatarActor.Get()) : nullptr;
}

UAhmedAbilitySystemComponent* UAhmedGameplayAbility::GetAhmedASC() const
{
	return CurrentActorInfo
		? Cast<UAhmedAbilitySystemComponent>(CurrentActorInfo->AbilitySystemComponent.Get())
		: nullptr;
}

const UAhmedAttributeSet* UAhmedGameplayAbility::GetAttributes() const
{
	const UAhmedAbilitySystemComponent* ASC = GetAhmedASC();
	return ASC ? ASC->GetSet<UAhmedAttributeSet>() : nullptr;
}

void UAhmedGameplayAbility::PushStateTag(FGameplayTag Tag)
{
	if (!Tag.IsValid())
	{
		return;
	}
	if (UAhmedAbilitySystemComponent* ASC = GetAhmedASC())
	{
		ASC->AddLooseGameplayTag(Tag);
		PushedTags.AddTag(Tag);
	}
}

void UAhmedGameplayAbility::EndAbility(const FGameplayAbilitySpecHandle Handle,
	const FGameplayAbilityActorInfo* ActorInfo,
	const FGameplayAbilityActivationInfo ActivationInfo,
	bool bReplicateEndAbility, bool bWasCancelled)
{
	// However this ended -- finished, cancelled, the fighter died mid-swing --
	// every tag it added comes off. This is the whole reason PushStateTag
	// exists rather than each ability remembering to clean up after itself.
	if (PushedTags.Num() > 0)
	{
		if (UAhmedAbilitySystemComponent* ASC = GetAhmedASC())
		{
			ASC->RemoveLooseGameplayTags(PushedTags);
		}
		PushedTags.Reset();
	}
	Super::EndAbility(Handle, ActorInfo, ActivationInfo, bReplicateEndAbility, bWasCancelled);
}
