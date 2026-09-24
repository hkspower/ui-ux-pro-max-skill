#pragma once

#include "CoreMinimal.h"
#include "Combat/FighterBase.h"
#include "EnemyFighter.generated.h"

class ASaudCharacter;
class UFightStyleComponent;

/**
 * Enemy AI, ported from the browser build's flanking behaviour.
 *
 * Two rules make crowds fair rather than overwhelming: only a fixed number of
 * enemies may attack at once (an "attack token"), and each enemy holds its own
 * lane and side so they surround the player instead of stacking on one spot.
 */
UCLASS()
class SAUDFIGHTER_API AEnemyFighter : public AFighterBase
{
	GENERATED_BODY()

public:
	AEnemyFighter();

	virtual void Tick(float DeltaSeconds) override;

	/** Applies an archetype row plus the stage tier and difficulty scaling. */
	UFUNCTION(BlueprintCallable, Category = "Setup")
	void ConfigureFromDefinition(const FFighterDef& Def, int32 Tier, float DifficultyHealth, float DifficultyDamage);

	UPROPERTY(BlueprintReadOnly, Category = "Fighter")
	int32 ExperienceValue = 14;

	UPROPERTY(BlueprintReadOnly, Category = "Fighter")
	bool bIsBoss = false;

	/** His row's name, for the HUD's boss banner (Game/SaudHUD). */
	UPROPERTY(BlueprintReadOnly, Category = "Fighter")
	FText DisplayName;

	/** Set to true once a boss drops below half health. */
	UPROPERTY(BlueprintReadOnly, Category = "Fighter")
	bool bEnraged = false;

	/**
	 * The bearing this one holds around the player, in degrees off the line
	 * from him to it. It was a side on X — `+1 ahead, -1 behind` — which is a
	 * fact about a corridor: in a district it lined the whole wave up east
	 * and west of the player however he turned. `SaudArena::CrowdSlot`
	 * assigns it, and `PushApart` stops two of them wanting one spot.
	 */
	UPROPERTY(BlueprintReadWrite, Category = "AI")
	float CrowdBearing = 22.f;

	/** Extra stand-off distance so several enemies do not share one spot. */
	UPROPERTY(BlueprintReadWrite, Category = "AI")
	float LaneOffset = 0.f;

	/**
	 * The role this one holds in the crowd, since 2026-09-24: a bearing off
	 * the PLAYER'S FACING (0 in front of him, +-110 on his flanks, 180 at
	 * his back, +-50 out wide) and a lane for anyone past the first six.
	 * AWaveDirector hands them out every frame from where everyone stands
	 * (SaudBrain::AssignRoles); the style's footwork steers to it. CrowdBearing
	 * above is measured off the enemy's own approach and is what the plain
	 * AI still uses; this is measured off the man being fought.
	 */
	UPROPERTY(BlueprintReadOnly, Category = "AI")
	float CrowdRoleBearing = 0.f;

	UPROPERTY(BlueprintReadOnly, Category = "AI")
	float CrowdRoleLane = 0.f;

	UPROPERTY(BlueprintReadOnly, Category = "AI")
	bool bHasCrowdRole = false;

	/** The distance this one fights at: the style's when it has one. */
	UFUNCTION(BlueprintPure, Category = "AI")
	float GetFightingRange() const;

	UFUNCTION(BlueprintCallable, Category = "Arena")
	void SetArenaCircle(const FVector& InCentre, float InRadius);



	/** How this one fights. When the archetype names a style asset this takes
	    over the decisions entirely and TickAI below never runs; when it does
	    not, the component is inert and nothing changes. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AI")
	TObjectPtr<UFightStyleComponent> FightStyle = nullptr;

protected:
	virtual void GatherTargets(TArray<AFighterBase*>& OutTargets) const override;
	virtual void OnKnockedDown() override;

	/** Fires when a boss crosses the halfway mark. */
	UFUNCTION(BlueprintImplementableEvent, Category = "Fighter", meta = (DisplayName = "On Enraged"))
	void BP_OnEnraged();

	virtual void OnHitLanded(AFighterBase* Victim, const FHitResultData& Hit) override;

	/** The plain AI: close, and swing at random. Used only by archetypes with
	    no fight style asset. */
	void TickAI(float DeltaSeconds, ASaudCharacter* Player);
	void EnterPhaseTwo();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AI")
	TArray<FName> Moves;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AI")
	float PreferredRange = 110.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AI")
	float AttackInterval = 1.55f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AI")
	float GuardChance = 0.12f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AI")
	bool bHitAndRun = false;

private:
	float AttackCooldown = 0.f;
	float GuardRollTimer = 0.f;
	float GuardRoll = 1.f;
	float RetreatRemaining = 0.f;

	FVector ArenaCentre = FVector::ZeroVector;
	float ArenaRadius = FLT_MAX;
};
