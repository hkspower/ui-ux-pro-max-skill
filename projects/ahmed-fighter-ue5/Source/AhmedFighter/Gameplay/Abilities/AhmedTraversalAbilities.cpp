#include "Gameplay/Abilities/AhmedTraversalAbilities.h"

#include "Combat/AhmedTypes.h"
#include "Combat/FighterBase.h"
#include "Gameplay/AhmedAttributeSet.h"
#include "Gameplay/AhmedGameplayTags.h"
#include "AbilitySystemBlueprintLibrary.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Engine/World.h"
#include "TimerManager.h"

/* ============================================================== DASH ===== */

UAhmedDashAbility::UAhmedDashAbility()
{
	AbilityInput = EAhmedAbilityInput::Block;		// block-while-moving
	ActivationBlockedTags.AddTag(AhmedTags::State_HitStun);
	ActivationBlockedTags.AddTag(AhmedTags::State_Downed);
	ActivationBlockedTags.AddTag(AhmedTags::State_Dead);
	ActivationBlockedTags.AddTag(AhmedTags::State_Dashing);
	ActivationBlockedTags.AddTag(AhmedTags::State_Climbing);
}

void UAhmedDashAbility::ActivateAbility(const FGameplayAbilitySpecHandle Handle,
	const FGameplayAbilityActorInfo* ActorInfo,
	const FGameplayAbilityActivationInfo ActivationInfo,
	const FGameplayEventData*)
{
	AFighterBase* Fighter = GetFighter();
	const UAhmedAttributeSet* Attr = GetAttributes();
	if (!Fighter || !Attr || Attr->GetStamina() < StaminaCost
		|| !CommitAbility(Handle, ActorInfo, ActivationInfo))
	{
		EndAbility(Handle, ActorInfo, ActivationInfo, true, true);
		return;
	}

	UAhmedAbilitySystemComponent* ASC = GetAhmedASC();
	// DASH LEAP does not add a second dash; it makes this one longer and
	// safer. One button, one move, more of it.
	const bool bLeap = ASC && ASC->HasMatchingGameplayTag(AhmedTags::Talent_DashLeap);

	PushStateTag(AhmedTags::State_Dashing);
	PushStateTag(AhmedTags::State_Invulnerable);

	Fighter->SpendStamina(StaminaCost);

	const FVector Dir = Fighter->GetIntendedMoveDirection();
	Fighter->LaunchCharacter(Dir * (bLeap ? LeapSpeed : Speed), true, false);

	UAbilitySystemBlueprintLibrary::ExecuteGameplayCue(
		Fighter, AhmedTags::Cue_Dash, FGameplayCueParameters());

	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().SetTimer(Timer, this, &UAhmedDashAbility::Finish,
			bLeap ? LeapDuration : Duration, false);
	}
}

void UAhmedDashAbility::Finish()
{
	EndAbility(CurrentSpecHandle, CurrentActorInfo, CurrentActivationInfo, true, false);
}

/* ============================================================= GUARD ===== */

UAhmedGuardAbility::UAhmedGuardAbility()
{
	AbilityInput = EAhmedAbilityInput::Block;
	ActivationBlockedTags.AddTag(AhmedTags::State_HitStun);
	ActivationBlockedTags.AddTag(AhmedTags::State_Downed);
	ActivationBlockedTags.AddTag(AhmedTags::State_Dead);
	ActivationBlockedTags.AddTag(AhmedTags::State_Attacking);
	ActivationBlockedTags.AddTag(AhmedTags::State_Dashing);
}

void UAhmedGuardAbility::ActivateAbility(const FGameplayAbilitySpecHandle Handle,
	const FGameplayAbilityActorInfo* ActorInfo,
	const FGameplayAbilityActivationInfo ActivationInfo,
	const FGameplayEventData*)
{
	if (!CommitAbility(Handle, ActorInfo, ActivationInfo))
	{
		EndAbility(Handle, ActorInfo, ActivationInfo, true, true);
		return;
	}

	PushStateTag(AhmedTags::State_Blocking);
	// The window opens on the press and shuts on its own. Holding the button
	// keeps the guard but never the parry -- that is the trade.
	PushStateTag(AhmedTags::State_ParryWindow);

	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().SetTimer(ParryTimer, this,
			&UAhmedGuardAbility::CloseParryWindow, ParryWindow, false);
	}
}

void UAhmedGuardAbility::CloseParryWindow()
{
	if (UAhmedAbilitySystemComponent* ASC = GetAhmedASC())
	{
		ASC->RemoveLooseGameplayTag(AhmedTags::State_ParryWindow);
	}
}

void UAhmedGuardAbility::InputReleased(const FGameplayAbilitySpecHandle Handle,
	const FGameplayAbilityActorInfo* ActorInfo,
	const FGameplayAbilityActivationInfo ActivationInfo)
{
	EndAbility(Handle, ActorInfo, ActivationInfo, true, false);
}

/* ============================================================== JUMP ===== */

UAhmedJumpAbility::UAhmedJumpAbility()
{
	AbilityInput = EAhmedAbilityInput::Jump;
	ActivationBlockedTags.AddTag(AhmedTags::State_HitStun);
	ActivationBlockedTags.AddTag(AhmedTags::State_Downed);
	ActivationBlockedTags.AddTag(AhmedTags::State_Dead);
	ActivationBlockedTags.AddTag(AhmedTags::State_Attacking);
	ActivationBlockedTags.AddTag(AhmedTags::State_Airborne);
	ActivationBlockedTags.AddTag(AhmedTags::State_Climbing);

	// Only with the talent. This is the difference between a jump that was
	// always there and a jump that changes the map when you find it.
	ActivationRequiredTags.AddTag(AhmedTags::Talent_Jump);
}

bool UAhmedJumpAbility::CanActivateAbility(const FGameplayAbilitySpecHandle Handle,
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
	const UAhmedAttributeSet* Attr = GetAttributes();
	if (!Fighter || !Attr || Attr->GetStamina() < StaminaCost)
	{
		return false;
	}
	// Feet on something. No air jumps: the second one would be a different
	// talent, and pretending it is this one hides that.
	const UCharacterMovementComponent* Move = Fighter->GetCharacterMovement();
	return Move && !Move->IsFalling();
}

void UAhmedJumpAbility::ActivateAbility(const FGameplayAbilitySpecHandle Handle,
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

	PushStateTag(AhmedTags::State_Airborne);
	Fighter->SpendStamina(StaminaCost);

	// The attribute is the height, so a later upgrade or a buff raises the
	// jump without this ability knowing about it.
	const UAhmedAttributeSet* Attr = GetAttributes();
	const float Power = (Attr && Attr->GetJumpPower() > 0.f) ? Attr->GetJumpPower() : JumpVelocity;
	if (UCharacterMovementComponent* Move = Fighter->GetCharacterMovement())
	{
		Move->JumpZVelocity = Power;
	}
	Fighter->Jump();

	UAbilitySystemBlueprintLibrary::ExecuteGameplayCue(
		Fighter, AhmedTags::Cue_Jump, FGameplayCueParameters());

	// Poll rather than bind: OnLanded is a character notify and this ability
	// wants to end on the landing whether or not the character forwards it.
	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().SetTimer(LandTimer, this,
			&UAhmedJumpAbility::PollForLanding, 0.05f, true, 0.12f);
	}
}

void UAhmedJumpAbility::PollForLanding()
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
				const_cast<AFighterBase*>(Fighter), AhmedTags::Cue_Land, FGameplayCueParameters());
		}
		EndAbility(CurrentSpecHandle, CurrentActorInfo, CurrentActivationInfo, true, false);
	}
}

/* ============================================================= CLIMB ===== */

UAhmedClimbAbility::UAhmedClimbAbility()
{
	AbilityInput = EAhmedAbilityInput::Interact;
	ActivationBlockedTags.AddTag(AhmedTags::State_HitStun);
	ActivationBlockedTags.AddTag(AhmedTags::State_Downed);
	ActivationBlockedTags.AddTag(AhmedTags::State_Dead);
	ActivationBlockedTags.AddTag(AhmedTags::State_Attacking);
	ActivationBlockedTags.AddTag(AhmedTags::State_Climbing);
	ActivationRequiredTags.AddTag(AhmedTags::Talent_Climb);
}

bool UAhmedClimbAbility::CanActivateAbility(const FGameplayAbilitySpecHandle Handle,
	const FGameplayAbilityActorInfo* ActorInfo,
	const FGameplayTagContainer* SourceTags,
	const FGameplayTagContainer* TargetTags,
	FGameplayTagContainer* OptionalRelevantTags) const
{
	if (!Super::CanActivateAbility(Handle, ActorInfo, SourceTags, TargetTags, OptionalRelevantTags))
	{
		return false;
	}
	const UAhmedAttributeSet* Attr = GetAttributes();
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
bool UAhmedClimbAbility::FindLedge(FVector& OutLedge) const
{
	const AFighterBase* Fighter = GetFighter();
	UWorld* World = Fighter ? Fighter->GetWorld() : nullptr;
	if (!Fighter || !World)
	{
		return false;
	}

	const FVector Origin = Fighter->GetActorLocation();
	const FVector Forward = FVector(Fighter->GetFacingSign(), 0.f, 0.f);

	FCollisionQueryParams Params(SCENE_QUERY_STAT(AhmedClimb), false, Fighter);

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

void UAhmedClimbAbility::ActivateAbility(const FGameplayAbilitySpecHandle Handle,
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

	PushStateTag(AhmedTags::State_Climbing);
	// Untouchable on the way up. A fighter caught halfway through a climb
	// would be a hitbox with no way to answer, which is not a difficulty.
	PushStateTag(AhmedTags::State_Invulnerable);

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
		Fighter, AhmedTags::Cue_Climb, FGameplayCueParameters());

	if (UAhmedAbilitySystemComponent* ASC = GetAhmedASC())
	{
		ASC->SendCombatEvent(AhmedTags::Event_LedgeGrabbed, Fighter, 0.f);
	}

	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().SetTimer(Timer, this,
			&UAhmedClimbAbility::FinishClimb, ClimbDuration, false);
	}
}

void UAhmedClimbAbility::FinishClimb()
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
