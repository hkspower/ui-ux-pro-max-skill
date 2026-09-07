#include "Gameplay/AhmedAbilitySystemComponent.h"

#include "Gameplay/AhmedGameplayAbility.h"
#include "Gameplay/AhmedGameplayTags.h"
#include "Abilities/GameplayAbilityTypes.h"
#include "GameplayEffect.h"

DEFINE_LOG_CATEGORY_STATIC(LogAhmedAbilities, Log, All);

UAhmedAbilitySystemComponent::UAhmedAbilitySystemComponent()
{
	// A beat-'em-up is single-player and local; full replication would cost
	// prediction complexity the game never collects on.
	SetIsReplicatedByDefault(false);
}

void UAhmedAbilitySystemComponent::InitialiseFighter(int32 Level)
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

	for (const TSubclassOf<UAhmedGameplayAbility>& Ability : StartingAbilities)
	{
		GrantAbility(Ability, Level);
	}
}

bool UAhmedAbilitySystemComponent::GrantAbility(TSubclassOf<UAhmedGameplayAbility> Ability, int32 Level)
{
	if (!Ability || Granted.Contains(Ability))
	{
		return false;
	}
	// The input ID comes off the ability's own default object, so an ability
	// declares which button it answers to rather than the grant site deciding.
	const UAhmedGameplayAbility* CDO = Ability->GetDefaultObject<UAhmedGameplayAbility>();
	const int32 InputID = CDO ? static_cast<int32>(CDO->AbilityInput) : 0;

	FGameplayAbilitySpec Spec(Ability, Level, InputID, this);
	GiveAbility(Spec);
	Granted.Add(Ability);
	return true;
}

void UAhmedAbilitySystemComponent::GrantTalent(FGameplayTag TalentTag)
{
	if (!TalentTag.IsValid() || HasMatchingGameplayTag(TalentTag))
	{
		return;
	}
	// The tag is the record. Anything that wants to know whether the player
	// can vault asks the tag, not a list kept somewhere else.
	AddLooseGameplayTag(TalentTag);

	if (const TSubclassOf<UAhmedGameplayAbility>* Ability = TalentAbilities.Find(TalentTag))
	{
		GrantAbility(*Ability);
	}
	UE_LOG(LogAhmedAbilities, Log, TEXT("Talent granted: %s"), *TalentTag.ToString());
}

void UAhmedAbilitySystemComponent::PressInput(EAhmedAbilityInput Input)
{
	if (Input == EAhmedAbilityInput::None)
	{
		return;
	}
	const int32 ID = static_cast<int32>(Input);
	AbilityLocalInputPressed(ID);
}

void UAhmedAbilitySystemComponent::ReleaseInput(EAhmedAbilityInput Input)
{
	if (Input == EAhmedAbilityInput::None)
	{
		return;
	}
	AbilityLocalInputReleased(static_cast<int32>(Input));
}

void UAhmedAbilitySystemComponent::SendCombatEvent(FGameplayTag EventTag, AActor* Instigator, float Magnitude)
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
