#include "Gameplay/Abilities/SaudTraversalAbilities.h"

#include "Combat/SaudTypes.h"
#include "Combat/FighterBase.h"
#include "Gameplay/SaudAttributeSet.h"
#include "Gameplay/SaudGameplayTags.h"
#include "AbilitySystemBlueprintLibrary.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Engine/World.h"
#include "TimerManager.h"

/* ============================================================== DASH ===== */

USaudDashAbility::USaudDashAbility()
{
	AbilityInput = ESaudAbilityInput::Block;		// block-while-moving
	ActivationBlockedTags.AddTag(SaudTags::State_HitStun);
	ActivationBlockedTags.AddTag(SaudTags::State_Downed);
	ActivationBlockedTags.AddTag(SaudTags::State_Dead);
	ActivationBlockedTags.AddTag(SaudTags::State_Dashing);
	ActivationBlockedTags.AddTag(SaudTags::State_Climbing);
}

void USaudDashAbility::ActivateAbility(const FGameplayAbilitySpecHandle Handle,
	const FGameplayAbilityActorInfo* ActorInfo,
	const FGameplayAbilityActivationInfo ActivationInfo,
	const FGameplayEventData*)
{
	AFighterBase* Fighter = GetFighter();
	const USaudAttributeSet* Attr = GetAttributes();
	if (!Fighter || !Attr || Attr->GetStamina() < StaminaCost
		|| !CommitAbility(Handle, ActorInfo, ActivationInfo))
	{
		EndAbility(Handle, ActorInfo, ActivationInfo, true, true);
		return;
	}

	USaudAbilitySystemComponent* ASC = GetSaudASC();
	// DASH LEAP does not add a second dash; it makes this one longer and
	// safer. One button, one move, more of it.
	const bool bLeap = ASC && ASC->HasMatchingGameplayTag(SaudTags::Talent_DashLeap);

	PushStateTag(SaudTags::State_Dashing);
	PushStateTag(SaudTags::State_Invulnerable);

	Fighter->SpendStamina(StaminaCost);

	const FVector Dir = Fighter->GetIntendedMoveDirection();
	Fighter->LaunchCharacter(Dir * (bLeap ? LeapSpeed : Speed), true, false);

	UAbilitySystemBlueprintLibrary::ExecuteGameplayCue(
		Fighter, SaudTags::Cue_Dash, FGameplayCueParameters());

	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().SetTimer(Timer, this, &USaudDashAbility::Finish,
			bLeap ? LeapDuration : Duration, false);
	}
}

void USaudDashAbility::Finish()
{
	EndAbility(CurrentSpecHandle, CurrentActorInfo, CurrentActivationInfo, true, false);
}

/* ============================================================= GUARD ===== */

USaudGuardAbility::USaudGuardAbility()
{
	AbilityInput = ESaudAbilityInput::Block;
	ActivationBlockedTags.AddTag(SaudTags::State_HitStun);
	ActivationBlockedTags.AddTag(SaudTags::State_Downed);
	ActivationBlockedTags.AddTag(SaudTags::State_Dead);
	ActivationBlockedTags.AddTag(SaudTags::State_Attacking);
	ActivationBlockedTags.AddTag(SaudTags::State_Dashing);
}

void USaudGuardAbility::ActivateAbility(const FGameplayAbilitySpecHandle Handle,
	const FGameplayAbilityActorInfo* ActorInfo,
	const FGameplayAbilityActivationInfo ActivationInfo,
	const FGameplayEventData*)
{
	if (!CommitAbility(Handle, ActorInfo, ActivationInfo))
	{
		EndAbility(Handle, ActorInfo, ActivationInfo, true, true);
		return;
	}

	PushStateTag(SaudTags::State_Blocking);
	// The window opens on the press and shuts on its own. Holding the button
	// keeps the guard but never the parry -- that is the trade.
	PushStateTag(SaudTags::State_ParryWindow);

	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().SetTimer(ParryTimer, this,
			&USaudGuardAbility::CloseParryWindow, ParryWindow, false);
	}
}

void USaudGuardAbility::CloseParryWindow()
{
	if (USaudAbilitySystemComponent* ASC = GetSaudASC())
	{
		ASC->RemoveLooseGameplayTag(SaudTags::State_ParryWindow);
	}
}

void USaudGuardAbility::InputReleased(const FGameplayAbilitySpecHandle Handle,
	const FGameplayAbilityActorInfo* ActorInfo,
	const FGameplayAbilityActivationInfo ActivationInfo)
{
	EndAbility(Handle, ActorInfo, ActivationInfo, true, false);
}

/* ============================================================== JUMP ===== */

USaudJumpAbility::USaudJumpAbility()
{
	AbilityInput = ESaudAbilityInput::Jump;
	ActivationBlockedTags.AddTag(SaudTags::State_HitStun);
	ActivationBlockedTags.AddTag(SaudTags::State_Downed);
	ActivationBlockedTags.AddTag(SaudTags::State_Dead);
	ActivationBlockedTags.AddTag(SaudTags::State_Attacking);
	ActivationBlockedTags.AddTag(SaudTags::State_Airborne);
	ActivationBlockedTags.AddTag(SaudTags::State_Climbing);

	// Only with the talent. This is the difference between a jump that was
	// always there and a jump that changes the map when you find it.
	ActivationRequiredTags.AddTag(SaudTags::Talent_Jump);
}

bool USaudJumpAbility::CanActivateAbility(const FGameplayAbilitySpecHandle Handle,
	const FGameplayAbilityActorInfo* ActorInfo,
	const FGameplayTagContainer* SourceTags,
	const FGameplayTagContainer* TargetTags,
	FGameplayTagContainer* OptionalRelevantTags) const
{
	if (!Super::CanActivateAbility(Handle, ActorInfo, SourceTags, TargetTags, OptionalRelevantTags))
	{
		return false;
	}
	const AFighterBase* Fighter = GetFighter();
	const USaudAttributeSet* Attr = GetAttributes();
	if (!Fighter || !Attr || Attr->GetStamina() < StaminaCost)
	{
		return false;
	}
	// Feet on something. No air jumps: the second one would be a different
	// talent, and pretending it is this one hides that.
	const UCharacterMovementComponent* Move = Fighter->GetCharacterMovement();
	return Move && !Move->IsFalling();
}

void USaudJumpAbility::ActivateAbility(const FGameplayAbilitySpecHandle Handle,
	const FGameplayAbilityActorInfo* ActorInfo,
	const FGameplayAbilityActivationInfo ActivationInfo,
	const FGameplayEventData*)
{
	AFighterBase* Fighter = GetFighter();
	if (!Fighter || !CommitAbility(Handle, ActorInfo, ActivationInfo))
	{
		EndAbility(Handle, ActorInfo, ActivationInfo, true, true);
		return;
	}

	PushStateTag(SaudTags::State_Airborne);
	Fighter->SpendStamina(StaminaCost);

	// The attribute is the height, so a later upgrade or a buff raises the
	// jump without this ability knowing about it.
	const USaudAttributeSet* Attr = GetAttributes();
	const float Power = (Attr && Attr->GetJumpPower() > 0.f) ? Attr->GetJumpPower() : JumpVelocity;
	if (UCharacterMovementComponent* Move = Fighter->GetCharacterMovement())
	{
		Move->JumpZVelocity = Power;
	}
	Fighter->Jump();

	UAbilitySystemBlueprintLibrary::ExecuteGameplayCue(
		Fighter, SaudTags::Cue_Jump, FGameplayCueParameters());

	// Poll rather than bind: OnLanded is a character notify and this ability
	// wants to end on the landing whether or not the character forwards it.
	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().SetTimer(LandTimer, this,
			&USaudJumpAbility::PollForLanding, 0.05f, true, 0.12f);
	}
}

void USaudJumpAbility::PollForLanding()
{
	const AFighterBase* Fighter = GetFighter();
	const UCharacterMovementComponent* Move = Fighter ? Fighter->GetCharacterMovement() : nullptr;
	if (!Fighter || !Move || !Move->IsFalling())
	{
		if (UWorld* World = GetWorld())
		{
			World->GetTimerManager().ClearTimer(LandTimer);
		}
		if (Fighter)
		{
			UAbilitySystemBlueprintLibrary::ExecuteGameplayCue(
				const_cast<AFighterBase*>(Fighter), SaudTags::Cue_Land, FGameplayCueParameters());
		}
		EndAbility(CurrentSpecHandle, CurrentActorInfo, CurrentActivationInfo, true, false);
	}
}

/* ============================================================= CLIMB ===== */

USaudClimbAbility::USaudClimbAbility()
{
	AbilityInput = ESaudAbilityInput::Interact;
	ActivationBlockedTags.AddTag(SaudTags::State_HitStun);
	ActivationBlockedTags.AddTag(SaudTags::State_Downed);
	ActivationBlockedTags.AddTag(SaudTags::State_Dead);
	ActivationBlockedTags.AddTag(SaudTags::State_Attacking);
	ActivationBlockedTags.AddTag(SaudTags::State_Climbing);
	ActivationRequiredTags.AddTag(SaudTags::Talent_Climb);
}

bool USaudClimbAbility::CanActivateAbility(const FGameplayAbilitySpecHandle Handle,
	const FGameplayAbilityActorInfo* ActorInfo,
	const FGameplayTagContainer* SourceTags,
	const FGameplayTagContainer* TargetTags,
	FGameplayTagContainer* OptionalRelevantTags) const
{
	if (!Super::CanActivateAbility(Handle, ActorInfo, SourceTags, TargetTags, OptionalRelevantTags))
	{
		return false;
	}
	const USaudAttributeSet* Attr = GetAttributes();
	if (!Attr || Attr->GetStamina() < StaminaCost)
	{
		return false;
	}
	FVector Unused;
	return FindLedge(Unused);
}

/**
 * Two traces. Forward at chest height to find the wall, then down from just
 * above the top of it to find what to stand on. If the drop lands within the
 * climbable band and there is headroom, that is a ledge.
 */
bool USaudClimbAbility::FindLedge(FVector& OutLedge) const
{
	const AFighterBase* Fighter = GetFighter();
	UWorld* World = Fighter ? Fighter->GetWorld() : nullptr;
	if (!Fighter || !World)
	{
		return false;
	}

	const FVector Origin = Fighter->GetActorLocation();
	const FVector Forward = Fighter->GetFacing();

	FCollisionQueryParams Params(SCENE_QUERY_STAT(SaudClimb), false, Fighter);

	// 1. Is there a wall in front, at chest height?
	FHitResult Wall;
	const FVector ChestStart = Origin + FVector(0.f, 0.f, MinLedgeHeight * 0.5f);
	if (!World->LineTraceSingleByChannel(Wall, ChestStart, ChestStart + Forward * ReachDistance,
		ECC_WorldStatic, Params))
	{
		return false;
	}

	// 2. Drop a trace from above the wall, just past its face, looking for the
	//    top surface.
	FHitResult Top;
	const FVector Above = Wall.ImpactPoint + Forward * 40.f
		+ FVector(0.f, 0.f, MaxLedgeHeight + 60.f);
	if (!World->LineTraceSingleByChannel(Top, Above,
		Above - FVector(0.f, 0.f, MaxLedgeHeight + 120.f), ECC_WorldStatic, Params))
	{
		return false;
	}

	const float LedgeHeight = Top.ImpactPoint.Z - Origin.Z;
	if (LedgeHeight < MinLedgeHeight || LedgeHeight > MaxLedgeHeight)
	{
		return false;			// a step, or a wall -- neither is a ledge
	}

	// 3. Room to stand once up there.
	FHitResult Clearance;
	const FVector Stand = Top.ImpactPoint + FVector(0.f, 0.f, 10.f);
	if (World->LineTraceSingleByChannel(Clearance, Stand,
		Stand + FVector(0.f, 0.f, RequiredClearance), ECC_WorldStatic, Params))
	{
		return false;
	}

	OutLedge = Top.ImpactPoint + Forward * 45.f + FVector(0.f, 0.f, 8.f);
	return true;
}

void USaudClimbAbility::ActivateAbility(const FGameplayAbilitySpecHandle Handle,
	const FGameplayAbilityActorInfo* ActorInfo,
	const FGameplayAbilityActivationInfo ActivationInfo,
	const FGameplayEventData*)
{
	AFighterBase* Fighter = GetFighter();
	if (!Fighter || !FindLedge(TargetLedge) || !CommitAbility(Handle, ActorInfo, ActivationInfo))
	{
		EndAbility(Handle, ActorInfo, ActivationInfo, true, true);
		return;
	}

	PushStateTag(SaudTags::State_Climbing);
	// Untouchable on the way up. A fighter caught halfway through a climb
	// would be a hitbox with no way to answer, which is not a difficulty.
	PushStateTag(SaudTags::State_Invulnerable);

	Fighter->SpendStamina(StaminaCost);

	// Off the ground for the duration so the movement component does not
	// fight the interpolation.
	if (UCharacterMovementComponent* Move = Fighter->GetCharacterMovement())
	{
		Move->SetMovementMode(MOVE_Flying);
		Move->StopMovementImmediately();
	}
	Fighter->BeginLedgeClimb(TargetLedge, ClimbDuration);

	UAbilitySystemBlueprintLibrary::ExecuteGameplayCue(
		Fighter, SaudTags::Cue_Climb, FGameplayCueParameters());

	if (USaudAbilitySystemComponent* ASC = GetSaudASC())
	{
		ASC->SendCombatEvent(SaudTags::Event_LedgeGrabbed, Fighter, 0.f);
	}

	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().SetTimer(Timer, this,
			&USaudClimbAbility::FinishClimb, ClimbDuration, false);
	}
}

void USaudClimbAbility::FinishClimb()
{
	if (AFighterBase* Fighter = GetFighter())
	{
		Fighter->EndLedgeClimb(TargetLedge);
		if (UCharacterMovementComponent* Move = Fighter->GetCharacterMovement())
		{
			Move->SetMovementMode(MOVE_Walking);
		}
	}
	EndAbility(CurrentSpecHandle, CurrentActorInfo, CurrentActivationInfo, true, false);
}
