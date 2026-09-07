#include "Gameplay/AhmedGameplayEffects.h"

#include "Game/AhmedAudioSubsystem.h"
#include "Gameplay/AhmedAttributeSet.h"
#include "Gameplay/AhmedGameplayTags.h"
#include "Camera/CameraShakeBase.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"

/** One SetByCaller modifier, spelled once instead of five times. */
static FGameplayModifierInfo MakeSetByCaller(const FGameplayAttribute& Attribute,
	const FGameplayTag& DataTag, EGameplayModOp::Type Op = EGameplayModOp::Additive)
{
	FGameplayModifierInfo Mod;
	Mod.Attribute = Attribute;
	Mod.ModifierOp = Op;

	FSetByCallerFloat ByCaller;
	ByCaller.DataTag = DataTag;
	Mod.ModifierMagnitude = FGameplayEffectModifierMagnitude(ByCaller);
	return Mod;
}

UGE_AhmedDamage::UGE_AhmedDamage()
{
	DurationPolicy = EGameplayEffectDurationType::Instant;
	// Into the meta attribute, never into Health directly. The attribute set
	// is the one place that decides what a damage number turns into.
	Modifiers.Add(MakeSetByCaller(UAhmedAttributeSet::GetIncomingDamageAttribute(),
		AhmedTags::Data_Damage));
}

UGE_AhmedAttackCost::UGE_AhmedAttackCost()
{
	DurationPolicy = EGameplayEffectDurationType::Instant;
	// The ability passes these as negatives, so the same effect can cost
	// nothing on a move that costs nothing without a branch anywhere.
	Modifiers.Add(MakeSetByCaller(UAhmedAttributeSet::GetStaminaAttribute(),
		AhmedTags::Data_StaminaCost));
	Modifiers.Add(MakeSetByCaller(UAhmedAttributeSet::GetManaAttribute(),
		AhmedTags::Data_ManaCost));
}

UGE_AhmedDefaultAttributes::UGE_AhmedDefaultAttributes()
{
	// Infinite rather than instant: these are what the fighter IS, and an
	// instant effect would be overwritten by the first thing that changed a
	// maximum. Content overrides the magnitudes per archetype.
	DurationPolicy = EGameplayEffectDurationType::Infinite;
}

UGE_AhmedRegeneration::UGE_AhmedRegeneration()
{
	DurationPolicy = EGameplayEffectDurationType::Infinite;
	Period = 0.25f;

	// Stamina back fast, mana back slowly. The asymmetry is the design: you
	// can always throw another punch soon, but HAWK FIST has to be earned by
	// landing hits rather than by waiting.
	FGameplayModifierInfo Stam;
	Stam.Attribute = UAhmedAttributeSet::GetStaminaAttribute();
	Stam.ModifierOp = EGameplayModOp::Additive;
	Stam.ModifierMagnitude = FScalableFloat(24.f * 0.25f);
	Modifiers.Add(Stam);

	FGameplayModifierInfo Mana;
	Mana.Attribute = UAhmedAttributeSet::GetManaAttribute();
	Mana.ModifierOp = EGameplayModOp::Additive;
	Mana.ModifierMagnitude = FScalableFloat(5.f * 0.25f);
	Modifiers.Add(Mana);
}

/* ------------------------------------------------------------------- cue */

bool UAhmedCueNotify_Impact::OnExecute_Implementation(AActor* Target,
	const FGameplayCueParameters& Parameters) const
{
	UWorld* World = Target ? Target->GetWorld() : nullptr;
	if (!World)
	{
		return false;
	}

	const FVector Location = Parameters.Location.IsNearlyZero()
		? Target->GetActorLocation()
		: Parameters.Location;

	if (!Effect.IsNull())
	{
		if (UNiagaraSystem* System = Effect.LoadSynchronous())
		{
			UNiagaraFunctionLibrary::SpawnSystemAtLocation(World, System, Location);
		}
	}

	if (!SoundCue.IsNone())
	{
		if (UAhmedAudioSubsystem* Audio = UAhmedAudioSubsystem::Get(Target))
		{
			Audio->PlayAt(SoundCue, Location);
		}
	}

	// Hit stop. Global time dilation for a few frames, restored by a timer --
	// the cheapest thing in the game and the one that does the most for how a
	// punch feels.
	if (HitStopSeconds > 0.f)
	{
		UGameplayStatics::SetGlobalTimeDilation(World, 0.05f);
		FTimerHandle Restore;
		World->GetTimerManager().SetTimer(Restore,
			FTimerDelegate::CreateWeakLambda(World, [World]()
			{
				UGameplayStatics::SetGlobalTimeDilation(World, 1.f);
			}),
			// Real seconds, so the wait is not itself slowed down.
			HitStopSeconds * 0.05f, false);
	}

	if (CameraShake)
	{
		if (APlayerController* PC = UGameplayStatics::GetPlayerController(World, 0))
		{
			PC->ClientStartCameraShake(CameraShake);
		}
	}
	return true;
}
