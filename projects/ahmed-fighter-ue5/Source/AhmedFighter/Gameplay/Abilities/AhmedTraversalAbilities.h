#pragma once

#include "CoreMinimal.h"
#include "Gameplay/AhmedGameplayAbility.h"
#include "AhmedTraversalAbilities.generated.h"

/**
 * Moving through the world, as abilities.
 *
 * These are the talents the Metroidvania is built on. Each one is granted by
 * finding it, and each one both adds a move and opens the routes that were
 * sealed against it — which is the same fact expressed once, as a tag, rather
 * than twice, as a move and a list of doors.
 */

/**
 * DASH. Block-while-moving: a short burst with invulnerability through it.
 *
 * With DASH LEAP granted it goes further and stays untouchable longer, and
 * carries the fighter over broken ground. The talent does not add a second
 * ability; it changes this one, because a player who has to remember which
 * dash they are doing has been given a worse game.
 */
UCLASS()
class AHMEDFIGHTER_API UAhmedDashAbility : public UAhmedGameplayAbility
{
	GENERATED_BODY()

public:
	UAhmedDashAbility();

	virtual void ActivateAbility(const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayAbilityActivationInfo ActivationInfo,
		const FGameplayEventData* TriggerEventData) override;

protected:
	UPROPERTY(EditDefaultsOnly, Category = "Dash") float Speed = 1150.f;
	UPROPERTY(EditDefaultsOnly, Category = "Dash") float LeapSpeed = 1500.f;
	UPROPERTY(EditDefaultsOnly, Category = "Dash") float Duration = 0.24f;
	UPROPERTY(EditDefaultsOnly, Category = "Dash") float LeapDuration = 0.32f;
	UPROPERTY(EditDefaultsOnly, Category = "Dash") float StaminaCost = 14.f;

	void Finish();

private:
	FTimerHandle Timer;
};

/**
 * GUARD. Held, not tapped.
 *
 * The parry window opens on the press and closes 0.2s later whether or not
 * the button is still down — holding block guards at a fifth damage but never
 * parries. That asymmetry is the whole reason blocking is a decision.
 */
UCLASS()
class AHMEDFIGHTER_API UAhmedGuardAbility : public UAhmedGameplayAbility
{
	GENERATED_BODY()

public:
	UAhmedGuardAbility();

	virtual void ActivateAbility(const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayAbilityActivationInfo ActivationInfo,
		const FGameplayEventData* TriggerEventData) override;

	virtual void InputReleased(const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayAbilityActivationInfo ActivationInfo) override;

protected:
	UPROPERTY(EditDefaultsOnly, Category = "Guard") float ParryWindow = 0.20f;

	void CloseParryWindow();

private:
	FTimerHandle ParryTimer;
};

/**
 * JUMP.
 *
 * A talent rather than a button that was always there. Until it is found,
 * JumpPower is zero and the input does nothing — which is what makes finding
 * it change the shape of every area behind you, not just the one ahead.
 *
 * The jump is short and heavy on purpose. This is a brawler: air time is a
 * commitment, and a floaty jump would turn every fight into one.
 */
UCLASS()
class AHMEDFIGHTER_API UAhmedJumpAbility : public UAhmedGameplayAbility
{
	GENERATED_BODY()

public:
	UAhmedJumpAbility();

	virtual bool CanActivateAbility(const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayTagContainer* SourceTags,
		const FGameplayTagContainer* TargetTags,
		FGameplayTagContainer* OptionalRelevantTags) const override;

	virtual void ActivateAbility(const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayAbilityActivationInfo ActivationInfo,
		const FGameplayEventData* TriggerEventData) override;

protected:
	/** Written into the JumpPower attribute when the talent is granted. */
	UPROPERTY(EditDefaultsOnly, Category = "Jump") float JumpVelocity = 620.f;

	UPROPERTY(EditDefaultsOnly, Category = "Jump") float StaminaCost = 8.f;

	/** Checked while airborne: landing ends the ability and fires the cue. */
	void PollForLanding();

private:
	FTimerHandle LandTimer;
};

/**
 * CLIMB.
 *
 * Pull up onto any ledge, not only the ones VAULT was placed for. VAULT opens
 * the gates a designer put a ledge marker on; CLIMB is the general case, and
 * it is the later talent because a general answer devalues the specific one if
 * it arrives first.
 *
 * It works by tracing forward at chest height for a wall, then down from
 * above it for a surface to stand on. If both hit and the gap between them is
 * a body's worth of clearance, the fighter goes up.
 */
UCLASS()
class AHMEDFIGHTER_API UAhmedClimbAbility : public UAhmedGameplayAbility
{
	GENERATED_BODY()

public:
	UAhmedClimbAbility();

	virtual bool CanActivateAbility(const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayTagContainer* SourceTags,
		const FGameplayTagContainer* TargetTags,
		FGameplayTagContainer* OptionalRelevantTags) const override;

	virtual void ActivateAbility(const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayAbilityActivationInfo ActivationInfo,
		const FGameplayEventData* TriggerEventData) override;

	/** Look for something to climb. Fills OutLedge with where the hands go. */
	UFUNCTION(BlueprintCallable, Category = "Climb")
	bool FindLedge(FVector& OutLedge) const;

protected:
	/** How far forward a ledge can be and still be reachable. */
	UPROPERTY(EditDefaultsOnly, Category = "Climb") float ReachDistance = 90.f;

	/** The band of heights a ledge can sit in. Below the floor of this the
	    fighter walks over it; above the ceiling it is a wall, not a ledge. */
	UPROPERTY(EditDefaultsOnly, Category = "Climb") float MinLedgeHeight = 60.f;
	UPROPERTY(EditDefaultsOnly, Category = "Climb") float MaxLedgeHeight = 260.f;

	/** Headroom needed on top, or the fighter would climb into a ceiling. */
	UPROPERTY(EditDefaultsOnly, Category = "Climb") float RequiredClearance = 140.f;

	UPROPERTY(EditDefaultsOnly, Category = "Climb") float ClimbDuration = 0.55f;
	UPROPERTY(EditDefaultsOnly, Category = "Climb") float StaminaCost = 12.f;

	void FinishClimb();

private:
	FTimerHandle Timer;
	FVector TargetLedge = FVector::ZeroVector;
};
