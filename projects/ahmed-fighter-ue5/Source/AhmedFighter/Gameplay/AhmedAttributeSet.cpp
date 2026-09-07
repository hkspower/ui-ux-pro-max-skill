#include "Gameplay/AhmedAttributeSet.h"

#include "Gameplay/AhmedAbilitySystemComponent.h"
#include "Gameplay/AhmedGameplayTags.h"
#include "GameplayEffectExtension.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"

DEFINE_LOG_CATEGORY_STATIC(LogAhmedAttributes, Log, All);

UAhmedAttributeSet::UAhmedAttributeSet()
{
	// Ahmed's level-one numbers, from the browser project's ahmed.js. Enemies
	// overwrite them from their own row on spawn; these are what a fighter is
	// before anything has said otherwise.
	InitHealth(100.f);
	InitMaxHealth(100.f);
	InitStamina(100.f);
	InitMaxStamina(100.f);
	InitMana(40.f);
	InitMaxMana(40.f);
	InitRage(0.f);
	InitMaxRage(100.f);

	InitPowerMultiplier(1.f);
	InitBoxingMultiplier(1.f);
	InitKickingMultiplier(1.f);
	InitBonusReach(0.f);

	InitMoveSpeed(341.f);		// 142 px/s * 2.4
	InitJumpPower(0.f);			// no jump until JUMP is found

	InitIncomingDamage(0.f);
}

void UAhmedAttributeSet::ClampToMax(const FGameplayAttribute& Attribute, float& NewValue) const
{
	if (Attribute == GetHealthAttribute())       { NewValue = FMath::Clamp(NewValue, 0.f, GetMaxHealth()); }
	else if (Attribute == GetStaminaAttribute()) { NewValue = FMath::Clamp(NewValue, 0.f, GetMaxStamina()); }
	else if (Attribute == GetManaAttribute())    { NewValue = FMath::Clamp(NewValue, 0.f, GetMaxMana()); }
	else if (Attribute == GetRageAttribute())    { NewValue = FMath::Clamp(NewValue, 0.f, GetMaxRage()); }
}

void UAhmedAttributeSet::PreAttributeChange(const FGameplayAttribute& Attribute, float& NewValue)
{
	Super::PreAttributeChange(Attribute, NewValue);
	ClampToMax(Attribute, NewValue);

	// Multipliers are allowed to be small but never negative — a negative one
	// would turn a punch into healing, which is the kind of thing that only
	// shows up in a build.
	if (Attribute == GetPowerMultiplierAttribute()
		|| Attribute == GetBoxingMultiplierAttribute()
		|| Attribute == GetKickingMultiplierAttribute())
	{
		NewValue = FMath::Max(0.f, NewValue);
	}

	// Speed is an attribute, but the movement component is what actually moves
	// the fighter, so it has to be told.
	if (Attribute == GetMoveSpeedAttribute())
	{
		NewValue = FMath::Max(0.f, NewValue);
		if (ACharacter* Character = Cast<ACharacter>(GetOwningActor()))
		{
			if (UCharacterMovementComponent* Move = Character->GetCharacterMovement())
			{
				Move->MaxWalkSpeed = NewValue;
			}
		}
	}

	if (Attribute == GetJumpPowerAttribute())
	{
		NewValue = FMath::Max(0.f, NewValue);
		if (ACharacter* Character = Cast<ACharacter>(GetOwningActor()))
		{
			if (UCharacterMovementComponent* Move = Character->GetCharacterMovement())
			{
				Move->JumpZVelocity = NewValue;
			}
		}
	}
}

/**
 * Where damage actually becomes something.
 *
 * An attack does not subtract health. It writes a number into IncomingDamage
 * and lets this decide what that number means: whether the guard was up and
 * facing, whether it was inside the parry window, whether the blow knocks
 * down, whether it kills. Keeping that in one place is the reason a new
 * attack cannot introduce a new way of dying.
 */
void UAhmedAttributeSet::PostGameplayEffectExecute(const FGameplayEffectModCallbackData& Data)
{
	Super::PostGameplayEffectExecute(Data);

	// Data.Target is the component the effect landed on.
	UAhmedAbilitySystemComponent* ASC = Cast<UAhmedAbilitySystemComponent>(&Data.Target);
	AActor* TargetActor = Data.Target.GetAvatarActor();
	AActor* SourceActor = Data.EffectSpec.GetEffectContext().GetOriginalInstigator();

	if (Data.EvaluatedData.Attribute == GetIncomingDamageAttribute())
	{
		const float Raw = GetIncomingDamage();
		SetIncomingDamage(0.f);			// meta: never stored

		if (Raw <= 0.f || GetHealth() <= 0.f)
		{
			return;
		}

		// Already dead, or untouchable this instant.
		if (Data.Target.HasMatchingGameplayTag(AhmedTags::State_Dead)
			|| Data.Target.HasMatchingGameplayTag(AhmedTags::State_Invulnerable))
		{
			return;
		}

		float Damage = Raw;
		const bool bGuarding = Data.Target.HasMatchingGameplayTag(AhmedTags::State_Blocking);
		const bool bParry = bGuarding
			&& Data.Target.HasMatchingGameplayTag(AhmedTags::State_ParryWindow);

		if (bParry)
		{
			// The whole reward for reading a strike: no damage, stamina back,
			// and the attacker eats the stagger. The ability system carries
			// that back to the attacker as an event rather than this reaching
			// into another actor.
			SetStamina(FMath::Min(GetMaxStamina(), GetStamina() + 18.f));
			if (ASC)
			{
				ASC->SendCombatEvent(AhmedTags::Event_Parried, SourceActor, 0.f);
			}
			return;
		}

		if (bGuarding)
		{
			Damage *= 0.20f;
			SetStamina(FMath::Max(0.f, GetStamina() - 14.f));
			if (ASC)
			{
				ASC->SendCombatEvent(AhmedTags::Event_Blocked, SourceActor, Damage);
			}
		}

		SetHealth(FMath::Clamp(GetHealth() - Damage, 0.f, GetMaxHealth()));

		if (ASC)
		{
			ASC->SendCombatEvent(AhmedTags::Event_HitReceived, SourceActor, Damage);
			if (GetHealth() <= 0.f)
			{
				ASC->SendCombatEvent(AhmedTags::Event_Defeated, SourceActor, 0.f);
			}
		}

		UE_LOG(LogAhmedAttributes, VeryVerbose, TEXT("%s took %.1f (%s), %.0f/%.0f left"),
			*GetNameSafe(TargetActor), Damage, bGuarding ? TEXT("blocked") : TEXT("clean"),
			GetHealth(), GetMaxHealth());
		return;
	}

	// Anything else that has a maximum gets clamped after the fact too: a
	// PreAttributeChange clamp only sees the incoming value, not the result of
	// an additive stack.
	if (Data.EvaluatedData.Attribute == GetHealthAttribute())
	{
		SetHealth(FMath::Clamp(GetHealth(), 0.f, GetMaxHealth()));
	}
	else if (Data.EvaluatedData.Attribute == GetStaminaAttribute())
	{
		SetStamina(FMath::Clamp(GetStamina(), 0.f, GetMaxStamina()));
	}
	else if (Data.EvaluatedData.Attribute == GetManaAttribute())
	{
		SetMana(FMath::Clamp(GetMana(), 0.f, GetMaxMana()));
	}
	else if (Data.EvaluatedData.Attribute == GetRageAttribute())
	{
		SetRage(FMath::Clamp(GetRage(), 0.f, GetMaxRage()));
	}
}
