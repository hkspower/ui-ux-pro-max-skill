#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Combat/AhmedTypes.h"
#include "Gameplay/AhmedFightStyle.h"
#include "FightStyleComponent.generated.h"

class AFighterBase;

/**
 * Makes a fighter fight like something in particular.
 *
 * The AI it stands in for did one thing regardless of archetype: hold a
 * flank, close to a fixed distance, throw a uniformly random move off a list.
 * Every enemy in the game therefore moved the same and chose the same, and
 * the only thing separating a kickboxer from a grappler was how much health
 * each had.
 *
 * This asks four questions instead, and a style answers all four differently:
 *
 *   WHERE does it want to stand?  Range discipline. A range fighter resets to
 *     its distance constantly; a pressure fighter walks in and stays.
 *
 *   HOW does it get there?  Footwork -- bouncing in and out, circling, or
 *     flat-footed forward. This is most of what a style looks like before
 *     anyone has thrown anything.
 *
 *   WHAT does it throw?  Range-banded and weighted. A kickboxer teeps at long
 *     and knees in close; a boxer has no answer at long, and that absence is
 *     what makes him close the distance rather than swing at air.
 *
 *   WHAT does it do after?  Reset, counter, or press.
 *
 * It throws through AFighterBase::StartAttack, the same door the old AI used,
 * so a style can only do what an enemy could already do -- it decides, it does
 * not add reach or damage or moves.
 *
 * Without a style asset the component is inert and the fighter's own AI runs
 * unchanged, which is what keeps an unconfigured enemy working.
 */
UCLASS(ClassGroup = (Ahmed), meta = (BlueprintSpawnableComponent))
class AHMEDFIGHTER_API UFightStyleComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UFightStyleComponent();

	virtual void BeginPlay() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType,
		FActorComponentTickFunction* ThisTickFunction) override;

	/** The style this fighter fights in. Null means the component does
	    nothing at all -- see IsDriving(). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Style")
	TObjectPtr<UAhmedFightStyleData> Style = nullptr;

	/** Who it is fighting. Re-acquired from the fighter's own target list
	    whenever it goes stale, so nothing else has to keep it fed. */
	UPROPERTY(BlueprintReadWrite, Category = "Style")
	TWeakObjectPtr<AFighterBase> Opponent;

	/** Multiplies the rhythm without touching the style asset. An enraged
	    boss is the same style throwing faster; writing that into the asset
	    would speed up every other fighter sharing it, for the rest of the
	    session. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Style", meta = (ClampMin = "0.1"))
	float Haste = 1.f;

	/** Strikes this fighter has gained beyond its style -- the finisher an
	    enraged boss earns. Kept here rather than pushed into the style asset,
	    which is shared by every fighter of the archetype and would otherwise
	    keep the finisher for the rest of the session. */
	UPROPERTY(BlueprintReadOnly, Category = "Style")
	TArray<FStyleStrike> ExtraStrikes;

	UFUNCTION(BlueprintCallable, Category = "Style")
	void AddStrike(const FStyleStrike& Strike);

	/** Off while the fighter is not in a fight. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Style")
	bool bActive = true;

	/** True when this component is the thing deciding, which is the signal
	    for the fighter to leave its own AI alone. */
	UFUNCTION(BlueprintPure, Category = "Style")
	bool IsDriving() const { return bActive && Style != nullptr; }

	/** Where it is standing, in this style's terms. */
	UFUNCTION(BlueprintPure, Category = "Style")
	ERangeBand CurrentBand() const { return Band; }

	/** Reactions. Reacting to a hit is a different decision from choosing a
	    strike, and conflating them is how AI ends up mashing. */
	UFUNCTION(BlueprintCallable, Category = "Style")
	void NotifyHitLanded();

	UFUNCTION(BlueprintCallable, Category = "Style")
	void NotifyWhiffed();

protected:
	/** Bound to the fighter's damage delegate: something landed on us. */
	UFUNCTION()
	void HandleDamaged(float NewHealth, const FHitResultData& Hit);

	/** Decide where to be, and ask the movement for it. */
	void TickFootwork(float DeltaTime, const FVector& ToOpponent, float Distance);

	/** Decide whether to throw, and what. */
	void TickOffence();

	/** Decide whether to guard. */
	void TickDefence(float DeltaTime, float Distance);

	/** Watch a swing to its end so a miss costs something. */
	void TickSwingResult();

	bool TryThrow(const FStyleStrike& Strike);

	/** Nearest thing this fighter is allowed to hit. */
	void AcquireOpponent();

private:
	AFighterBase* GetFighter() const;

	ERangeBand Band = ERangeBand::Out;

	float AttackCooldown = 0.f;
	/** Strikes left in the combination currently being thrown. */
	int32 ComboRemaining = 0;
	/** Backing off after committing, for ResetDistance. */
	float ResetRemaining = 0.f;
	float AcquireTimer = 0.f;

	/** A swing is in the air and has not connected yet. */
	bool bSwingPending = false;
	bool bWasAttacking = false;

	/** Which way it is circling, and when it next changes its mind. */
	float CircleDirection = 1.f;
	float CircleTimer = 0.f;

	/** Drives the in-and-out bounce. A phase rather than a timer so the
	    rhythm survives the component being switched off and on mid-fight. */
	float BouncePhase = 0.f;

	/** Rolled a few times a second rather than every frame: a guard that
	    re-decides sixty times a second flickers instead of guarding. */
	float GuardRoll = 1.f;
	float GuardRollTimer = 0.f;
};
