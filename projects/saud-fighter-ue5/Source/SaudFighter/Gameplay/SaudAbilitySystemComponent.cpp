#include "Gameplay/SaudAbilitySystemComponent.h"

#include "Gameplay/SaudGameplayAbility.h"
#include "Gameplay/SaudGameplayTags.h"
#include "Abilities/GameplayAbilityTypes.h"
#include "GameplayEffect.h"

DEFINE_LOG_CATEGORY_STATIC(LogSaudAbilities, Log, All);

USaudAbilitySystemComponent::USaudAbilitySystemComponent()
{
	// A beat-'em-up is single-player and local; full replication would cost
	// prediction complexity the game never collects on.
	SetIsReplicatedByDefault(false);
}

void USaudAbilitySystemComponent::InitialiseFighter(int32 Level)
{
	if (bInitialised)
	{
		return;
	}
	bInitialised = true;

	if (DefaultAttributesEffect)
	{
		FGameplayEffectContextHandle Context = MakeEffectContext();
		Context.AddSourceObject(this);
		const FGameplayEffectSpecHandle Spec =
			MakeOutgoingSpec(DefaultAttributesEffect, static_cast<float>(Level), Context);
		if (Spec.IsValid())
		{
			ApplyGameplayEffectSpecToSelf(*Spec.Data.Get());
		}
	}

	for (const TSubclassOf<USaudGameplayAbility>& Ability : StartingAbilities)
	{
		GrantAbility(Ability, Level);
	}
}

bool USaudAbilitySystemComponent::GrantAbility(TSubclassOf<USaudGameplayAbility> Ability, int32 Level)
{
	if (!Ability || Granted.Contains(Ability))
	{
		return false;
	}
	// The input ID comes off the ability's own default object, so an ability
	// declares which button it answers to rather than the grant site deciding.
	const USaudGameplayAbility* CDO = Ability->GetDefaultObject<USaudGameplayAbility>();
	const int32 InputID = CDO ? static_cast<int32>(CDO->AbilityInput) : 0;

	FGameplayAbilitySpec Spec(Ability, Level, InputID, this);
	GiveAbility(Spec);
	Granted.Add(Ability);
	return true;
}

void USaudAbilitySystemComponent::GrantTalent(FGameplayTag TalentTag)
{
	if (!TalentTag.IsValid() || HasMatchingGameplayTag(TalentTag))
	{
		return;
	}
	// The tag is the record. Anything that wants to know whether the player
	// can vault asks the tag, not a list kept somewhere else.
	AddLooseGameplayTag(TalentTag);

	if (const TSubclassOf<USaudGameplayAbility>* Ability = TalentAbilities.Find(TalentTag))
	{
		GrantAbility(*Ability);
	}
	UE_LOG(LogSaudAbilities, Log, TEXT("Talent granted: %s"), *TalentTag.ToString());
}

void USaudAbilitySystemComponent::PressInput(ESaudAbilityInput Input)
{
	if (Input == ESaudAbilityInput::None)
	{
		return;
	}
	const int32 ID = static_cast<int32>(Input);
	AbilityLocalInputPressed(ID);
}

void USaudAbilitySystemComponent::ReleaseInput(ESaudAbilityInput Input)
{
	if (Input == ESaudAbilityInput::None)
	{
		return;
	}
	AbilityLocalInputReleased(static_cast<int32>(Input));
}

void USaudAbilitySystemComponent::SendCombatEvent(FGameplayTag EventTag, AActor* Instigator, float Magnitude)
{
	if (!EventTag.IsValid())
	{
		return;
	}
	FGameplayEventData Payload;
	Payload.EventTag       = EventTag;
	Payload.Instigator     = Instigator;
	Payload.Target         = GetAvatarActor();
	Payload.EventMagnitude = Magnitude;

	HandleGameplayEvent(EventTag, &Payload);
}
