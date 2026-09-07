#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "AhmedFightStyle.generated.h"

/**
 * How far away a fighter is, in the only terms that matter to choosing a
 * strike. A kickboxer has an answer at Long; a boxer does not, and that
 * absence is what makes him close.
 */
UENUM(BlueprintType)
enum class ERangeBand : uint8
{
	/** Outside everything. Only footwork happens here. */
	Out,
	/** Kicking distance. Teeps and roundhouses, nothing with a fist. */
	Long,
	/** Punching distance. The pocket. */
	Mid,
	/** Chest to chest. Knees and elbows. Most kicks cannot fire. */
	Close
};

/** One strike an archetype knows, and when it wants to throw it. */
USTRUCT(BlueprintType)
struct FStyleStrike
{
	GENERATED_BODY()

	/** Row in the attack table, the same name the fighter's Moves list uses.
	    Naming the move rather than an ability class is what lets a style be
	    generated from the browser project's roster. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Strike")
	FName AttackRow;

	/** Bands this strike is thrown from. A knee listed at Long is a knee that
	    whiffs, which is how an archetype ends up looking stupid. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Strike")
	TArray<ERangeBand> Bands;

	/** Relative likelihood inside its band. Not a probability -- the weights
	    of whatever is legal right now are normalised at the moment of
	    choosing, so removing a strike does not mean re-tuning the others. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Strike", meta = (ClampMin = "0"))
	float Weight = 1.f;

	/** Chance this is thrown as the opener of a combination rather than
	    alone. A jab is nearly always an opener; a head kick nearly never. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Strike", meta = (ClampMin = "0", ClampMax = "1"))
	float OpensCombination = 0.f;
};

/**
 * A fighting style.
 *
 * Every archetype in the port fights the same way: hold a flank, close to a
 * fixed distance, throw a uniformly random move off a list. That is why a
 * kickboxer and a grappler feel identical to fight even though their numbers
 * differ -- the numbers were never the thing telling them apart.
 *
 * A style is the answer to four questions, and archetypes differ in all four:
 *
 *   Where does this fighter want to stand?     (range discipline)
 *   How does it get there?                     (footwork)
 *   What does it throw from where it is?       (range-banded selection)
 *   What does it do after something happens?   (reactions)
 *
 * Generated per archetype from the roster by Tools/levels/build_data_assets.py,
 * so the styles stay derived from the browser project's numbers rather than
 * hand-tuned into disagreeing with them.
 */
UCLASS(BlueprintType)
class AHMEDFIGHTER_API UAhmedFightStyleData : public UPrimaryDataAsset
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Identity")
	FText DisplayName;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Identity", meta = (MultiLine = true))
	FString Notes;

	// ---- where it wants to stand -------------------------------------------

	/** The distance it fights at. A boxer's is short, a kickboxer's long, and
	    the difference is most of what a style is. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Range", meta = (ClampMin = "40"))
	float PreferredRange = 130.f;

	/** How hard it works to hold that distance. Near 1 it is a range fighter
	    that resets constantly; near 0 it wanders in and stays. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Range", meta = (ClampMin = "0", ClampMax = "1"))
	float RangeDiscipline = 0.5f;

	/** Distance it retreats to after committing. Zero means it does not. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Range", meta = (ClampMin = "0"))
	float ResetDistance = 0.f;

	// ---- how it moves -------------------------------------------------------

	/** In-and-out bouncing, in cycles per second. Zero is a flat-footed
	    pressure fighter; high is a points fighter never still for a beat. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Footwork", meta = (ClampMin = "0", ClampMax = "4"))
	float BounceRate = 0.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Footwork", meta = (ClampMin = "0"))
	float BounceAmplitude = 0.f;

	/** How much it circles rather than walking straight in. Circling is what
	    makes a crowd look like a fight rather than a queue. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Footwork", meta = (ClampMin = "0", ClampMax = "1"))
	float CircleTendency = 0.3f;

	/** Seconds before it changes which way it is circling. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Footwork", meta = (ClampMin = "0.2"))
	float CircleSwitchTime = 2.5f;

	// ---- what it throws -----------------------------------------------------

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Strikes")
	TArray<FStyleStrike> Strikes;

	/** Seconds between attempts, before the jitter below. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Strikes", meta = (ClampMin = "0.1"))
	float AttackInterval = 1.55f;

	/** How irregular the rhythm is. A metronome is readable and a fight
	    should not be; 0.35 means the gap varies by a third either way. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Strikes", meta = (ClampMin = "0", ClampMax = "0.9"))
	float RhythmJitter = 0.35f;

	/** How many strikes a combination runs to once one starts. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Strikes", meta = (ClampMin = "1", ClampMax = "6"))
	int32 MaxComboLength = 2;

	// ---- how it defends -----------------------------------------------------

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Defence", meta = (ClampMin = "0", ClampMax = "1"))
	float GuardChance = 0.12f;

	/** Guards while walking forward rather than only while holding position.
	    A pressure fighter does; a counter-puncher waits instead. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Defence")
	bool bGuardsWhileAdvancing = false;

	/** Chance it answers immediately after eating one instead of resetting.
	    High makes a brawler; low makes something that respects you. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Defence", meta = (ClampMin = "0", ClampMax = "1"))
	float CounterChance = 0.15f;

	virtual FPrimaryAssetId GetPrimaryAssetId() const override
	{
		return FPrimaryAssetId(TEXT("AhmedFightStyle"), GetFName());
	}

	/** Which band a distance falls in, given this style's reach. Bands are
	    relative to the fighter: "close" for a lanky kickboxer is further out
	    than "close" for a squat grappler. */
	UFUNCTION(BlueprintPure, Category = "Range")
	ERangeBand BandFor(float Distance) const;

	/** Pick a strike legal at this band, weighted, from this style plus
	    anything the fighter has picked up since (an enraged boss's finisher).
	    Returns null when there is nothing to throw from here -- which is a
	    real answer, and what makes a boxer close rather than flail at range. */
	const FStyleStrike* ChooseStrike(ERangeBand Band, const TArray<FStyleStrike>& Extra) const;
};
