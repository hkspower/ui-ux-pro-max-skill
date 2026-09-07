#pragma once

#include "CoreMinimal.h"
#include "AbilitySystemComponent.h"
#include "AhmedAbilitySystemComponent.generated.h"

class UAhmedGameplayAbility;

/** Which button an ability is on. The value is the input ID GAS binds to. */
UENUM(BlueprintType)
enum class EAhmedAbilityInput : uint8
{
	None		= 0,
	Punch		= 1,
	Kick		= 2,
	Block		= 3,	// tap is a guard, tap-while-moving is a dash
	Rage		= 4,
	Jump		= 5,
	Interact	= 6		// climb a ledge, open a gate, take a weapon
};

/**
 * The fighter's ability system.
 *
 * Adds three things to the stock component, each because the stock one leaves
 * the game to solve it in a worse place:
 *
 *   Input, by tag rather than by index. Pressing Punch does not name an
 *   ability — it asks for whatever is on Punch and lets the abilities' own
 *   activation rules decide which one answers. That is what makes a jab
 *   become a cross become a hook without a combo counter anywhere.
 *
 *   Combat events as one call. Every hit, block, parry and death goes out as
 *   a gameplay event, so an ability, a HUD widget and the audio subsystem can
 *   each listen without any of them knowing about the others.
 *
 *   A record of what has been granted, so the profile can be written back
 *   and reloaded without the abilities being granted twice.
 */
UCLASS()
class AHMEDFIGHTER_API UAhmedAbilitySystemComponent : public UAbilitySystemComponent
{
	GENERATED_BODY()

public:
	UAhmedAbilitySystemComponent();

	/** Press and release for one input. Held inputs (block) need both. */
	UFUNCTION(BlueprintCallable, Category = "Abilities")
	void PressInput(EAhmedAbilityInput Input);

	UFUNCTION(BlueprintCallable, Category = "Abilities")
	void ReleaseInput(EAhmedAbilityInput Input);

	/**
	 * Send a moment to whoever is listening. Target may be null.
	 * `Magnitude` rides along as EventMagnitude — damage, usually.
	 */
	UFUNCTION(BlueprintCallable, Category = "Abilities")
	void SendCombatEvent(FGameplayTag EventTag, AActor* Instigator, float Magnitude);

	/** Grant one ability at a level, remembering it so a reload does not
	    double it. Returns false if it was already there. */
	UFUNCTION(BlueprintCallable, Category = "Abilities")
	bool GrantAbility(TSubclassOf<UAhmedGameplayAbility> Ability, int32 Level = 1);

	/** Grant the ability a talent tag stands for, and add the tag itself so
	    gates and routes can ask `HasMatchingGameplayTag` rather than keeping
	    their own list. */
	UFUNCTION(BlueprintCallable, Category = "Abilities")
	void GrantTalent(FGameplayTag TalentTag);

	UFUNCTION(BlueprintPure, Category = "Abilities")
	bool HasTalent(FGameplayTag TalentTag) const { return HasMatchingGameplayTag(TalentTag); }

	/** Abilities granted at spawn, before any talent is found. */
	UPROPERTY(EditDefaultsOnly, Category = "Abilities")
	TArray<TSubclassOf<UAhmedGameplayAbility>> StartingAbilities;

	/** What each talent grants when it is found. Set on the pawn, so the
	    talent table stays data and the classes stay content. */
	UPROPERTY(EditDefaultsOnly, Category = "Abilities")
	TMap<FGameplayTag, TSubclassOf<UAhmedGameplayAbility>> TalentAbilities;

	/** Applied once on possession: the attribute values a fighter starts at. */
	UPROPERTY(EditDefaultsOnly, Category = "Abilities")
	TSubclassOf<class UGameplayEffect> DefaultAttributesEffect;

	/** Grants StartingAbilities and applies DefaultAttributesEffect. Safe to
	    call twice; the second call is a no-op. */
	UFUNCTION(BlueprintCallable, Category = "Abilities")
	void InitialiseFighter(int32 Level = 1);

protected:
	UPROPERTY()
	TSet<TSubclassOf<UAhmedGameplayAbility>> Granted;

	bool bInitialised = false;
};
