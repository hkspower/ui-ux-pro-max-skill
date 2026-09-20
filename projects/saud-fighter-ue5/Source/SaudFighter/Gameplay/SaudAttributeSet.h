#pragma once

#include "CoreMinimal.h"
#include "AttributeSet.h"
#include "AbilitySystemComponent.h"
#include "SaudAttributeSet.generated.h"

/** The four accessors every attribute wants. Unreal's own macro, spelled out
    here so the set below reads as a list of attributes rather than of boilerplate. */
#define SAUD_ATTRIBUTE(ClassName, PropertyName) \
	GAMEPLAYATTRIBUTE_PROPERTY_GETTER(ClassName, PropertyName) \
	GAMEPLAYATTRIBUTE_VALUE_GETTER(PropertyName) \
	GAMEPLAYATTRIBUTE_VALUE_SETTER(PropertyName) \
	GAMEPLAYATTRIBUTE_VALUE_INITTER(PropertyName)

/**
 * Every number a fighter carries that another system is allowed to change.
 *
 * The port kept these as plain floats on AFighterBase, which works right up
 * until two things want to change one at once — a rage buff and a difficulty
 * multiplier and a level bonus all raising max health, each having to know
 * about the others. Attributes take that problem away: an effect says what it
 * contributes and the system composes them, so a talent, a difficulty and an
 * upgrade stack without any of them being written to know the others exist.
 *
 * Base value is what the fighter is; current value is what the fighter is
 * right now with everything applied.
 *
 * IncomingDamage is a meta attribute: nothing stores it. An attack writes a
 * number into it, PostGameplayEffectExecute reads it, works out what actually
 * happens (guard, parry, knockdown, death) and zeroes it again. Damage is a
 * message, not a stat.
 */
UCLASS()
class SAUDFIGHTER_API USaudAttributeSet : public UAttributeSet
{
	GENERATED_BODY()

public:
	USaudAttributeSet();

	virtual void PreAttributeChange(const FGameplayAttribute& Attribute, float& NewValue) override;
	virtual void PostGameplayEffectExecute(const FGameplayEffectModCallbackData& Data) override;

	// ---------------------------------------------------------------- vitals

	UPROPERTY(BlueprintReadOnly, Category = "Vitals")
	FGameplayAttributeData Health;
	SAUD_ATTRIBUTE(USaudAttributeSet, Health);

	UPROPERTY(BlueprintReadOnly, Category = "Vitals")
	FGameplayAttributeData MaxHealth;
	SAUD_ATTRIBUTE(USaudAttributeSet, MaxHealth);

	/** Spent by every strike. Empty and the fighter cannot commit to anything. */
	UPROPERTY(BlueprintReadOnly, Category = "Vitals")
	FGameplayAttributeData Stamina;
	SAUD_ATTRIBUTE(USaudAttributeSet, Stamina);

	UPROPERTY(BlueprintReadOnly, Category = "Vitals")
	FGameplayAttributeData MaxStamina;
	SAUD_ATTRIBUTE(USaudAttributeSet, MaxStamina);

	/** Powers the talents. Refills on its own and on landed hits, so it pays
	    for staying in the fight rather than for hoarding. */
	UPROPERTY(BlueprintReadOnly, Category = "Vitals")
	FGameplayAttributeData Mana;
	SAUD_ATTRIBUTE(USaudAttributeSet, Mana);

	UPROPERTY(BlueprintReadOnly, Category = "Vitals")
	FGameplayAttributeData MaxMana;
	SAUD_ATTRIBUTE(USaudAttributeSet, MaxMana);

	/** Fills by dealing damage, spends all at once on the finisher. */
	UPROPERTY(BlueprintReadOnly, Category = "Vitals")
	FGameplayAttributeData Rage;
	SAUD_ATTRIBUTE(USaudAttributeSet, Rage);

	UPROPERTY(BlueprintReadOnly, Category = "Vitals")
	FGameplayAttributeData MaxRage;
	SAUD_ATTRIBUTE(USaudAttributeSet, MaxRage);

	// ------------------------------------------------------------- offence

	/** Multiplies everything this fighter deals. Difficulty, tier and the
	    upgrade tracks all land here rather than each editing damage. */
	UPROPERTY(BlueprintReadOnly, Category = "Offence")
	FGameplayAttributeData PowerMultiplier;
	SAUD_ATTRIBUTE(USaudAttributeSet, PowerMultiplier);

	/** Per-family scaling, so BOXING and KICKING are two independent tracks
	    without the attack needing to know which one bought it. */
	UPROPERTY(BlueprintReadOnly, Category = "Offence")
	FGameplayAttributeData BoxingMultiplier;
	SAUD_ATTRIBUTE(USaudAttributeSet, BoxingMultiplier);

	UPROPERTY(BlueprintReadOnly, Category = "Offence")
	FGameplayAttributeData KickingMultiplier;
	SAUD_ATTRIBUTE(USaudAttributeSet, KickingMultiplier);

	/** Extra centimetres, from a weapon or a talent. */
	UPROPERTY(BlueprintReadOnly, Category = "Offence")
	FGameplayAttributeData BonusReach;
	SAUD_ATTRIBUTE(USaudAttributeSet, BonusReach);

	// ------------------------------------------------------------ movement

	UPROPERTY(BlueprintReadOnly, Category = "Movement")
	FGameplayAttributeData MoveSpeed;
	SAUD_ATTRIBUTE(USaudAttributeSet, MoveSpeed);

	/** How high a jump goes. Zero until JUMP is granted, which is what makes
	    the talent a talent rather than a button that was always there. */
	UPROPERTY(BlueprintReadOnly, Category = "Movement")
	FGameplayAttributeData JumpPower;
	SAUD_ATTRIBUTE(USaudAttributeSet, JumpPower);

	// ------------------------------------------------------- meta (no store)

	/** Written by an attack, consumed immediately. Never persists. */
	UPROPERTY(BlueprintReadOnly, Category = "Meta")
	FGameplayAttributeData IncomingDamage;
	SAUD_ATTRIBUTE(USaudAttributeSet, IncomingDamage);

private:
	/** Keeps a current value inside its own maximum, and both above zero. */
	void ClampToMax(const FGameplayAttribute& Attribute, float& NewValue) const;
};
