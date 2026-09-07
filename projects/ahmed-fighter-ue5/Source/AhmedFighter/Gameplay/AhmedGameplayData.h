#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "GameplayTagContainer.h"
#include "AhmedGameplayData.generated.h"

class UAnimMontage;
class UNiagaraSystem;
class UAhmedGameplayAbility;

/**
 * One strike, as a Data Asset.
 *
 * The same numbers the DataTable holds, with three things a table row cannot
 * carry: gameplay tags, an ability class, and hard references to the montage
 * and the effect it should spawn. A row can only hold data; an asset can hold
 * the whole move.
 *
 * These are GENERATED from Content/Data by Tools/levels/build_data_assets.py,
 * which is what keeps the browser project the single source of the numbers.
 * Editing one by hand works until the next export overwrites it.
 */
UCLASS(BlueprintType)
class AHMEDFIGHTER_API UAhmedAttackData : public UPrimaryDataAsset
{
	GENERATED_BODY()

public:
	/** What this strike IS. Its family is the parent tag, so a cracked wall
	    can ask for Ahmed.Attack.Box and get any punch. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Identity")
	FGameplayTag AttackTag;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Identity")
	FText DisplayName;

	// ---- timing: the state machine, unchanged from the browser build -------

	/** Wind-up before the hitbox opens. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Timing", meta = (ClampMin = "0"))
	float Startup = 0.07f;

	/** How long it stays open. A hit only lands in here. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Timing", meta = (ClampMin = "0"))
	float Active = 0.06f;

	/** Locked out afterwards. This is what makes a whiff cost something. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Timing", meta = (ClampMin = "0"))
	float Recovery = 0.13f;

	// ---- what it does ------------------------------------------------------

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Damage", meta = (ClampMin = "0"))
	float Damage = 7.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Damage", meta = (ClampMin = "0"))
	float Reach = 130.f;

	/** Half-width along the depth axis. The playfield is a strip, so a strike
	    that ignored depth would hit someone standing a metre behind. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Damage", meta = (ClampMin = "0"))
	float DepthTolerance = 80.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Damage")
	float Knockback = 210.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cost", meta = (ClampMin = "0"))
	float StaminaCost = 5.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cost", meta = (ClampMin = "0"))
	float ManaCost = 0.f;

	/** Heavy blows knock down and hitstop harder. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Damage")
	bool bHeavy = false;

	/** Hits everything in reach instead of stopping at the first. The finisher. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Damage")
	bool bMultiHit = false;

	/** Chance a heavy blow puts the victim down. Bosses shrug most off. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Damage", meta = (ClampMin = "0", ClampMax = "1"))
	float KnockdownChance = 0.45f;

	// ---- presentation ------------------------------------------------------

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Presentation")
	TSoftObjectPtr<UAnimMontage> Montage;

	/** Cue fired as the swing starts, and as it lands. Tags, so the same
	    moment can drive a Niagara system, a sound and a camera shake without
	    the ability knowing about any of them. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Presentation")
	FGameplayTag WhooshCue;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Presentation")
	FGameplayTag ImpactCue;

	/** Warps the strike toward the target so a punch lands on a body rather
	    than in the air next to one. Zero disables it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Presentation", meta = (ClampMin = "0"))
	float MotionWarpDistance = 0.f;

	float TotalTime() const { return Startup + Active + Recovery; }

	virtual FPrimaryAssetId GetPrimaryAssetId() const override
	{
		return FPrimaryAssetId(TEXT("AhmedAttack"), GetFName());
	}
};

/**
 * A talent: what it is called, what it grants, and what it opens.
 *
 * The browser build keeps these in talents.js and the export writes them into
 * DT_Talents; this is the same content with the ability class attached, which
 * is the piece a table cannot hold.
 */
UCLASS(BlueprintType)
class AHMEDFIGHTER_API UAhmedTalentData : public UPrimaryDataAsset
{
	GENERATED_BODY()

public:
	/** Ahmed.Talent.Vault and so on. This tag IS the record of having it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Identity")
	FGameplayTag TalentTag;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Identity")
	FText DisplayName;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Identity")
	FText DisplayNameArabic;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Identity")
	FString Icon;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Identity", meta = (MultiLine = true))
	FText Description;

	/** Granted with the tag. Passive talents leave this empty and are read
	    off the tag alone. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Grant")
	TSubclassOf<UAhmedGameplayAbility> GrantedAbility;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Grant", meta = (ClampMin = "0"))
	float ManaCost = 0.f;

	virtual FPrimaryAssetId GetPrimaryAssetId() const override
	{
		return FPrimaryAssetId(TEXT("AhmedTalent"), GetFName());
	}
};
