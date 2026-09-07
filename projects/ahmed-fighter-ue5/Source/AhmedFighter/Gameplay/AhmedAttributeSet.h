#pragma once

#include "CoreMinimal.h"
#include "AttributeSet.h"
#include "AbilitySystemComponent.h"
#include "AhmedAttributeSet.generated.h"

/** The four accessors every attribute wants. Unreal's own macro, spelled out
    here so the set below reads as a list of attributes rather than of boilerplate. */
#define AHMED_ATTRIBUTE(ClassName, PropertyName) \
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
class AHMEDFIGHTER_API UAhmedAttributeSet : public UAttributeSet
{
	GENERATED_BODY()

public:
	UAhmedAttributeSet();

	virtual void PreAttributeChange(const FGameplayAttribute& Attribute, float& NewValue) override;
	virtual void PostGameplayEffectExecute(const FGameplayEffectModCallbackData& Data) override;

	// ---------------------------------------------------------------- vitals

	UPROPERTY(BlueprintReadOnly, Category = "Vitals")
	FGameplayAttributeData Health;
	AHMED_ATTRIBUTE(UAhmedAttributeSet, Health);

	UPROPERTY(BlueprintReadOnly, Category = "Vitals")
	FGameplayAttributeData MaxHealth;
	AHMED_ATTRIBUTE(UAhmedAttributeSet, MaxHealth);

	/** Spent by every strike. Empty and the fighter cannot commit to anything. */
	UPROPERTY(BlueprintReadOnly, Category = "Vitals")
	FGameplayAttributeData Stamina;
	AHMED_ATTRIBUTE(UAhmedAttributeSet, Stamina);

	UPROPERTY(BlueprintReadOnly, Category = "Vitals")
	FGameplayAttributeData MaxStamina;
	AHMED_ATTRIBUTE(UAhmedAttributeSet, MaxStamina);

	/** Powers the talents. Refills on its own and on landed hits, so it pays
	    for staying in the fight rather than for hoarding. */
	UPROPERTY(BlueprintReadOnly, Category = "Vitals")
	FGameplayAttributeData Mana;
	AHMED_ATTRIBUTE(UAhmedAttributeSet, Mana);

	UPROPERTY(BlueprintReadOnly, Category = "Vitals")
	FGameplayAttributeData MaxMana;
	AHMED_ATTRIBUTE(UAhmedAttributeSet, MaxMana);

	/** Fills by dealing damage, spends all at once on the finisher. */
	UPROPERTY(BlueprintReadOnly, Category = "Vitals")
	FGameplayAttributeData Rage;
	AHMED_ATTRIBUTE(UAhmedAttributeSet, Rage);

	UPROPERTY(BlueprintReadOnly, Category = "Vitals")
	FGameplayAttributeData MaxRage;
	AHMED_ATTRIBUTE(UAhmedAttributeSet, MaxRage);

	// ------------------------------------------------------------- offence

	/** Multiplies everything this fighter deals. Difficulty, tier and the
	    upgrade tracks all land here rather than each editing damage. */
	UPROPERTY(BlueprintReadOnly, Category = "Offence")
	FGameplayAttributeData PowerMultiplier;
	AHMED_ATTRIBUTE(UAhmedAttributeSet, PowerMultiplier);

	/** Per-family scaling, so BOXING and KICKING are two independent tracks
	    without the attack needing to know which one bought it. */
	UPROPERTY(BlueprintReadOnly, Category = "Offence")
	FGameplayAttributeData BoxingMultiplier;
	AHMED_ATTRIBUTE(UAhmedAttributeSet, BoxingMultiplier);

	UPROPERTY(BlueprintReadOnly, Category = "Offence")
	FGameplayAttributeData KickingMultiplier;
	AHMED_ATTRIBUTE(UAhmedAttributeSet, KickingMultiplier);

	/** Extra centimetres, from a weapon or a talent. */
	UPROPERTY(BlueprintReadOnly, Category = "Offence")
	FGameplayAttributeData BonusReach;
	AHMED_ATTRIBUTE(UAhmedAttributeSet, BonusReach);

	// ------------------------------------------------------------ movement

	UPROPERTY(BlueprintReadOnly, Category = "Movement")
	FGameplayAttributeData MoveSpeed;
	AHMED_ATTRIBUTE(UAhmedAttributeSet, MoveSpeed);

	/** How high a jump goes. Zero until JUMP is granted, which is what makes
	    the talent a talent rather than a button that was always there. */
	UPROPERTY(BlueprintReadOnly, Category = "Movement")
	FGameplayAttributeData JumpPower;
	AHMED_ATTRIBUTE(UAhmedAttributeSet, JumpPower);

	// ------------------------------------------------------- meta (no store)

	/** Written by an attack, consumed immediately. Never persists. */
	UPROPERTY(BlueprintReadOnly, Category = "Meta")
	FGameplayAttributeData IncomingDamage;
	AHMED_ATTRIBUTE(UAhmedAttributeSet, IncomingDamage);

private:
	/** Keeps a current value inside its own maximum, and both above zero. */
	void ClampToMax(const FGameplayAttribute& Attribute, float& NewValue) const;
};
