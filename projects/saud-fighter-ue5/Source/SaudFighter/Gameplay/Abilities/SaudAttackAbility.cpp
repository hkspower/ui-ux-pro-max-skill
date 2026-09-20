#include "Gameplay/Abilities/SaudAttackAbility.h"
#include "Combat/SaudArena.h"

#include "Combat/SaudTypes.h"
#include "Combat/FighterBase.h"
#include "Gameplay/SaudAttributeSet.h"
#include "Gameplay/SaudGameplayData.h"
#include "Gameplay/SaudGameplayTags.h"
#include "AbilitySystemBlueprintLibrary.h"
#include "Engine/World.h"
#include "GameplayEffect.h"
#include "TimerManager.h"

USaudAttackAbility::USaudAttackAbility()
{
	AbilityInput = ESaudAbilityInput::Punch;

	// A fighter can only be doing one thing. Everything under State.Busy
	// blocks a new strike, and the strike adds its own while it runs -- which
	// is the entire "IsBusy()" check the port had, expressed once as data.
	ActivationBlockedTags.AddTag(SaudTags::State_HitStun);
	ActivationBlockedTags.AddTag(SaudTags::State_Downed);
	ActivationBlockedTags.AddTag(SaudTags::State_Dead);
	ActivationBlockedTags.AddTag(SaudTags::State_Dashing);
	ActivationBlockedTags.AddTag(SaudTags::State_Climbing);
	ActivationBlockedTags.AddTag(SaudTags::State_Attacking);

	AbilityTags.AddTag(SaudTags::Attack);
}

bool USaudAttackAbility::CanActivateAbility(const FGameplayAbilitySpecHandle Handle,
	const FGameplayAbilityActorInfo* ActorInfo,
	const FGameplayTagContainer* SourceTags,
	const FGameplayTagContainer* TargetTags,
	FGameplayTagContainer* OptionalRelevantTags) const
{
	if (!Super::CanActivateAbility(Handle, ActorInfo, SourceTags, TargetTags, OptionalRelevantTags))
	{
		return false;
	}
	if (!Attack)
	{
		return false;
	}
	// Stamina is checked here rather than spent-and-refunded: an attack you
	// cannot afford should never start, because a started-then-cancelled
	// swing still plays its wind-up.
	const USaudAttributeSet* Attr = GetAttributes();
	return Attr && Attr->GetStamina() >= Attack->StaminaCost
		&& Attr->GetMana() >= Attack->ManaCost;
}

void USaudAttackAbility::ActivateAbility(const FGameplayAbilitySpecHandle Handle,
	const FGameplayAbilityActorInfo* ActorInfo,
	const FGameplayAbilityActivationInfo ActivationInfo,
	const FGameplayEventData* TriggerEventData)
{
	if (!CommitAbility(Handle, ActorInfo, ActivationInfo) || !Attack)
	{
		EndAbility(Handle, ActorInfo, ActivationInfo, true, true);
		return;
	}

	HitThisSwing.Reset();
	bChainQueued = false;

	PushStateTag(SaudTags::State_Attacking);

	if (CostEffect)
	{
		FGameplayEffectSpecHandle Cost = MakeOutgoingGameplayEffectSpec(CostEffect, GetAbilityLevel());
		if (Cost.IsValid())
		{
			Cost.Data->SetSetByCallerMagnitude(SaudTags::Data_StaminaCost, -Attack->StaminaCost);
			Cost.Data->SetSetByCallerMagnitude(SaudTags::Data_ManaCost, -Attack->ManaCost);
			ApplyGameplayEffectSpecToOwner(Handle, ActorInfo, ActivationInfo, Cost);
		}
	}

	if (AFighterBase* Fighter = GetFighter())
	{
		Fighter->FaceNearestOpponent();
		if (Attack->Montage.IsValid() || !Attack->Montage.IsNull())
		{
			if (UAnimMontage* Montage = Attack->Montage.LoadSynchronous())
			{
				Fighter->PlayAnimMontage(Montage);
			}
		}
	}

	// The swing is heard before anyone knows whether it lands.
	if (Attack->WhooshCue.IsValid())
	{
		UAbilitySystemBlueprintLibrary::ExecuteGameplayCue(
			GetAvatarActorFromActorInfo(), Attack->WhooshCue, FGameplayCueParameters());
	}

	// Three windows, each scheduling the next. The timer is the timeline.
	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().SetTimer(WindowTimer, this,
			&USaudAttackAbility::EnterActive, FMath::Max(0.01f, Attack->Startup), false);
	}
}

void USaudAttackAbility::EnterActive()
{
	ResolveHits();

	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().SetTimer(WindowTimer, this,
			&USaudAttackAbility::EnterRecovery, FMath::Max(0.01f, Attack->Active), false);
	}
}

void USaudAttackAbility::EnterRecovery()
{
	// Recovery is where a chain is bought. The tag is what the next strike in
	// the chain is allowed to interrupt.
	PushStateTag(SaudTags::State_Recovering);

	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().SetTimer(WindowTimer, this,
			&USaudAttackAbility::FinishAttack, FMath::Max(0.01f, Attack->Recovery), false);
	}
}

void USaudAttackAbility::FinishAttack()
{
	// The button came again while recovering, and there is somewhere to go:
	// hand straight over rather than ending and making the player press twice.
	const bool bChain = bChainQueued && NextInChain != nullptr;
	USaudAbilitySystemComponent* ASC = GetSaudASC();

	EndAbility(CurrentSpecHandle, CurrentActorInfo, CurrentActivationInfo, true, false);

	if (bChain && ASC)
	{
		ASC->TryActivateAbilityByClass(NextInChain);
	}
}

void USaudAttackAbility::InputPressed(const FGameplayAbilitySpecHandle Handle,
	const FGameplayAbilityActorInfo* ActorInfo,
	const FGameplayAbilityActivationInfo ActivationInfo)
{
	Super::InputPressed(Handle, ActorInfo, ActivationInfo);

	// Only during recovery. Pressing during startup or the active window would
	// let a player mash through the commitment the timings exist to impose.
	if (USaudAbilitySystemComponent* ASC = GetSaudASC())
	{
		if (ASC->HasMatchingGameplayTag(SaudTags::State_Recovering))
		{
			bChainQueued = true;
		}
	}
}

bool USaudAttackAbility::IsBurning() const
{
	const USaudAbilitySystemComponent* ASC = GetSaudASC();
	if (!ASC || !Attack)
	{
		return false;
	}
	// Punches only. A kick with HAWK FIST is still a kick.
	return ASC->HasMatchingGameplayTag(SaudTags::Talent_HawkFist)
		&& Attack->AttackTag.MatchesTag(SaudTags::Attack_Box);
}

float USaudAttackAbility::FamilyMultiplier() const
{
	const USaudAttributeSet* Attr = GetAttributes();
	if (!Attr || !Attack)
	{
		return 1.f;
	}
	// The family tag decides which upgrade track scales this, so a new punch
	// is scaled by BOXING without anyone wiring it up.
	if (Attack->AttackTag.MatchesTag(SaudTags::Attack_Box))
	{
		return Attr->GetBoxingMultiplier();
	}
	if (Attack->AttackTag.MatchesTag(SaudTags::Attack_Kick))
	{
		return Attr->GetKickingMultiplier();
	}
	return 1.f;
}

/**
 * The hitbox.
 *
 * The playfield is a strip: X runs along the stage, Y is depth. A strike
 * reaches forward along X and tolerates a band in Y, which is why two
 * fighters standing a metre apart in depth do not trade blows.
 */
void USaudAttackAbility::ResolveHits()
{
	AFighterBase* Fighter = GetFighter();
	if (!Fighter || !Attack || !DamageEffect)
	{
		return;
	}

	const USaudAttributeSet* Attr = GetAttributes();
	const float Reach = Attack->Reach + (Attr ? Attr->GetBonusReach() : 0.f);
	const FVector Facing = Fighter->GetFacing();
	const FVector Origin = Fighter->GetActorLocation();

	TArray<AFighterBase*> Candidates;
	Fighter->GatherOpponents(Candidates);

	const float Power = (Attr ? Attr->GetPowerMultiplier() : 1.f) * FamilyMultiplier();
	const float Burn = IsBurning() ? 1.55f : 1.f;

	for (AFighterBase* Target : Candidates)
	{
		if (!IsValid(Target) || !Target->IsAlive())
		{
			continue;
		}
		if (!Attack->bMultiHit && HitThisSwing.Num() > 0)
		{
			break;					// one body per swing unless it is the finisher
		}
		if (HitThisSwing.Contains(Target))
		{
			continue;
		}

		// In front along the facing, in reach, inside the band either side.
		// The ability system and the legacy state machine must agree about
		// what a strike reaches, so both ask the same function.
		if (!SaudArena::InHitbox(Origin, Facing, Target->GetActorLocation(),
		                          Reach, Attack->DepthTolerance, 0.f, 0.f))
		{
			continue;
		}

		UAbilitySystemComponent* TargetASC = Target->GetAbilitySystemComponent();
		if (!TargetASC)
		{
			continue;
		}

		FGameplayEffectSpecHandle Spec = MakeOutgoingGameplayEffectSpec(DamageEffect, GetAbilityLevel());
		if (!Spec.IsValid())
		{
			continue;
		}
		// Damage rides on the spec rather than being baked into the effect,
		// so one damage effect serves every strike in the game.
		const float Damage = Attack->Damage * Power * Burn * FMath::FRandRange(0.92f, 1.10f);
		Spec.Data->SetSetByCallerMagnitude(SaudTags::Data_Damage, Damage);
		Spec.Data->SetSetByCallerMagnitude(SaudTags::Data_Knockback, Attack->Knockback);
		if (Attack->bHeavy)
		{
			Spec.Data->AddDynamicAssetTag(SaudTags::Attack_Modifier_Heavy);
		}
		if (Burn > 1.f)
		{
			Spec.Data->AddDynamicAssetTag(SaudTags::Attack_Modifier_Burning);
		}

		ApplyGameplayEffectSpecToTarget(CurrentSpecHandle, CurrentActorInfo, CurrentActivationInfo,
			Spec, TargetASC->AbilityActorInfo->AbilitySystemComponent.IsValid()
				? UAbilitySystemBlueprintLibrary::AbilityTargetDataFromActor(Target)
				: FGameplayAbilityTargetDataHandle());

		HitThisSwing.Add(Target);

		// Knockback and knockdown are the victim's business, but the strike
		// is what decides how hard: heavy blows put people down, and the
		// finisher always does.
		const bool bKnockdown = Attack->bMultiHit
			|| (Attack->bHeavy && FMath::FRand() < Attack->KnockdownChance);
		Target->ReceiveKnockback(FVector(Facing * Attack->Knockback, 0.f, 0.f), bKnockdown);

		if (Attack->ImpactCue.IsValid())
		{
			FGameplayCueParameters Cue;
			Cue.Location = Target->GetActorLocation() + FVector(0.f, 0.f, 60.f);
			Cue.RawMagnitude = Damage;
			UAbilitySystemBlueprintLibrary::ExecuteGameplayCue(Target, Attack->ImpactCue, Cue);
		}

		// Tell the attacker it landed: rage, combo and the audio all hang off
		// this one event rather than off the hit loop.
		if (USaudAbilitySystemComponent* ASC = GetSaudASC())
		{
			ASC->SendCombatEvent(SaudTags::Event_HitLanded, Target, Damage);
		}
	}
}
