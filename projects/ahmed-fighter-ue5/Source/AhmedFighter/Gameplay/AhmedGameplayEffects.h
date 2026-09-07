#pragma once

#include "CoreMinimal.h"
#include "GameplayEffect.h"
#include "GameplayEffectExecutionCalculation.h"
#include "GameplayCueNotify_Static.h"
#include "AhmedGameplayEffects.generated.h"

/**
 * The effects, in C++ rather than as Blueprint assets.
 *
 * A Blueprint effect is easier to tweak and impossible to review — the whole
 * definition lives in a binary asset. These are the three the game cannot
 * work without, so they are code, and content is free to add more.
 *
 * All three carry their numbers by SetByCaller. One damage effect serves
 * every strike in the game because the strike sets the number, which is the
 * difference between a system and forty near-identical assets.
 */

/** Damage. Writes IncomingDamage, which the attribute set turns into what
    actually happened -- guard, parry, knockdown, death. */
UCLASS()
class AHMEDFIGHTER_API UGE_AhmedDamage : public UGameplayEffect
{
	GENERATED_BODY()
public:
	UGE_AhmedDamage();
};

/** What a strike costs the fighter throwing it. Negative magnitudes, applied
    to the attacker, so one asset covers stamina and mana together. */
UCLASS()
class AHMEDFIGHTER_API UGE_AhmedAttackCost : public UGameplayEffect
{
	GENERATED_BODY()
public:
	UGE_AhmedAttackCost();
};

/** The numbers a fighter starts a level with. Applied once on possession. */
UCLASS()
class AHMEDFIGHTER_API UGE_AhmedDefaultAttributes : public UGameplayEffect
{
	GENERATED_BODY()
public:
	UGE_AhmedDefaultAttributes();
};

/** Stamina and mana coming back over time. Infinite, applied at spawn. */
UCLASS()
class AHMEDFIGHTER_API UGE_AhmedRegeneration : public UGameplayEffect
{
	GENERATED_BODY()
public:
	UGE_AhmedRegeneration();
};

/**
 * What a moment looks and sounds like.
 *
 * A cue is fired by tag from the ability that caused it, and this turns that
 * into a Niagara system and a sound. The ability does not know either of them
 * exist, which is why an artist can change how a hook lands without opening a
 * C++ file.
 *
 * Static rather than actor-backed: these are one-shot bursts with no state,
 * and spawning an actor per punch would be a lot of actors.
 */
UCLASS(Blueprintable)
class AHMEDFIGHTER_API UAhmedCueNotify_Impact : public UGameplayCueNotify_Static
{
	GENERATED_BODY()

public:
	virtual bool OnExecute_Implementation(AActor* Target,
		const FGameplayCueParameters& Parameters) const override;

	/** Sprayed at the impact point. */
	UPROPERTY(EditDefaultsOnly, Category = "Impact")
	TSoftObjectPtr<class UNiagaraSystem> Effect;

	/** Cue name in DT_Sounds. The audio subsystem owns the file, the volume
	    and the pitch drift; this only names the moment. */
	UPROPERTY(EditDefaultsOnly, Category = "Impact")
	FName SoundCue;

	/** Frames the game freezes for. The single most important number in a
	    beat-'em-up after the damage itself: it is what makes a hit feel like
	    a hit rather than a number going down. */
	UPROPERTY(EditDefaultsOnly, Category = "Impact", meta = (ClampMin = "0", ClampMax = "0.3"))
	float HitStopSeconds = 0.05f;

	UPROPERTY(EditDefaultsOnly, Category = "Impact")
	TSubclassOf<class UCameraShakeBase> CameraShake;
};
