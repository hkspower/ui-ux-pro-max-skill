#pragma once

#include "CoreMinimal.h"
#include "Combat/FighterBase.h"
#include "EnemyFighter.generated.h"

class AAhmedCharacter;
class UFightStyleComponent;

/**
 * Enemy AI, ported from the browser build's flanking behaviour.
 *
 * Two rules make crowds fair rather than overwhelming: only a fixed number of
 * enemies may attack at once (an "attack token"), and each enemy holds its own
 * lane and side so they surround the player instead of stacking on one spot.
 */
UCLASS()
class AHMEDFIGHTER_API AEnemyFighter : public AFighterBase
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

	/** Set to true once a boss drops below half health. */
	UPROPERTY(BlueprintReadOnly, Category = "Fighter")
	bool bEnraged = false;

	/** Which side of the player this one tries to occupy: +1 ahead, -1 behind. */
	UPROPERTY(BlueprintReadWrite, Category = "AI")
	float FlankSide = 1.f;

	/** Extra stand-off distance so several enemies do not share one spot. */
	UPROPERTY(BlueprintReadWrite, Category = "AI")
	float LaneOffset = 0.f;

	/** Depth offset from the player, so they spread across the strip. */
	UPROPERTY(BlueprintReadWrite, Category = "AI")
	float DepthOffset = 0.f;

	UFUNCTION(BlueprintCallable, Category = "Arena")
	void SetArenaBounds(float InMinX, float InMaxX);

	UFUNCTION(BlueprintCallable, Category = "Arena")
	void SetArenaFrame(float InMinX, float InMaxX, float InMinY, float InMaxY);

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
	void TickAI(float DeltaSeconds, AAhmedCharacter* Player);
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

	float ArenaMinX = -FLT_MAX;
	float ArenaMaxX =  FLT_MAX;
	float ArenaMinY = AhmedGameplay::DepthMin;
	float ArenaMaxY = AhmedGameplay::DepthMax;
};
