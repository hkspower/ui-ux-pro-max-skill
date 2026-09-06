#pragma once

#include "CoreMinimal.h"
#include "Engine/DataTable.h"
#include "AhmedTypes.generated.h"

class UAnimMontage;
class UStaticMesh;
class UWorld;

/**
 * Shared data for the whole game. Every tunable that lived in the JS build's
 * ATK / TYPES / STAGES tables lives here as a DataTable row, so designers can
 * retune the game from CSV without touching C++.
 */

/** Which upgrade track an attack scales with. */
UENUM(BlueprintType)
enum class EAttackFamily : uint8
{
	Box		UMETA(DisplayName = "Boxing"),
	Kick	UMETA(DisplayName = "Kicking")
};

/** Combat state machine. Mirrors the JS fighter `state` field one-for-one. */
UENUM(BlueprintType)
enum class EFighterState : uint8
{
	Idle,
	Walk,
	Attack,
	Hit,
	Block,
	Dash,
	Down,
	Dead
};

/** Traversal and demolition abilities found in the world, never bought. */
UENUM(BlueprintType)
enum class EAbility : uint8
{
	None		UMETA(Hidden),
	Vault,
	DashLeap,
	PowerKick,
	Haymaker,
	/** Punches carry fire. Spends mana, and only punches -- kicks stay cold.
	    Unlike the other four this one is not a traversal key: it opens the
	    door to the arena rather than a gate inside a stage. */
	HawkFist
};

/** What a sealed route wants from the player. */
UENUM(BlueprintType)
enum class EGateType : uint8
{
	Stash,		// opens on approach, needs nothing
	Ledge,		// opens on approach, needs Vault
	Gap,		// opens on approach, needs DashLeap
	Shutter,	// three kicks, needs PowerKick
	Wall		// three punches, needs Haymaker
};

UENUM(BlueprintType)
enum class EPickupKind : uint8
{
	Food,		// restores health
	RageOrb		// fills the rage meter
};

/**
 * One strike. Timings are in seconds and run startup -> active -> recovery,
 * exactly as the browser build did: hits only land during the active window.
 */
USTRUCT(BlueprintType)
struct FAttackDef : public FTableRowBase
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Attack")
	EAttackFamily Family = EAttackFamily::Box;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Attack", meta = (ClampMin = "0"))
	float Damage = 7.f;

	/** Wind-up before the hitbox turns on. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Timing", meta = (ClampMin = "0"))
	float Startup = 0.07f;

	/** How long the hitbox stays live. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Timing", meta = (ClampMin = "0"))
	float Active = 0.06f;

	/** Locked-out time after the hitbox closes — this is what makes whiffing hurt. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Timing", meta = (ClampMin = "0"))
	float Recovery = 0.13f;

	/** Reach measured forward from the attacker's centre, in cm. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Attack", meta = (ClampMin = "0"))
	float Reach = 110.f;

	/** Half-width of the hitbox along the depth axis, in cm. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Attack", meta = (ClampMin = "0"))
	float DepthTolerance = 55.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Attack")
	float Knockback = 140.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Attack", meta = (ClampMin = "0"))
	float StaminaCost = 5.f;

	/** Heavy blows can knock down and cause more hitstop. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Attack")
	bool bHeavy = false;

	/** Hits every valid target instead of stopping at the first (the finisher). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Attack")
	bool bMultiHit = false;

	/** Montage to play. Optional — the game is fully playable without animation. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Presentation")
	TSoftObjectPtr<UAnimMontage> Montage;

	float TotalTime() const { return Startup + Active + Recovery; }
};

/** An enemy archetype. */
USTRUCT(BlueprintType)
struct FFighterDef : public FTableRowBase
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Fighter")
	FText DisplayName;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Fighter")
	FText DisplayNameArabic;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Fighter", meta = (ClampMin = "1"))
	float MaxHealth = 46.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Fighter")
	float PowerMultiplier = 0.8f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Fighter")
	float MoveSpeed = 240.f;

	/** Distance the AI tries to hold before committing to a strike. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AI")
	float PreferredRange = 110.f;

	/** Seconds between attack attempts. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AI")
	float AttackInterval = 1.55f;

	/** 0..1 chance of guarding when the player commits nearby. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AI", meta = (ClampMin = "0", ClampMax = "1"))
	float GuardChance = 0.12f;

	/** Strike and retreat rather than staying in the pocket. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AI")
	bool bHitAndRun = false;

	/** Bosses resist knockdown and gain a second phase at half health. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Fighter")
	bool bIsBoss = false;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Fighter")
	int32 ExperienceValue = 14;

	/** Row names into the attack table. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AI")
	TArray<FName> Moves;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Presentation")
	TSoftClassPtr<AActor> PawnClass;
};

/** One locked wave inside a stage. */
USTRUCT(BlueprintType)
struct FWaveDef
{
	GENERATED_BODY()

	/** Distance along the stage that triggers the lock. Negative fires immediately. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wave")
	float TriggerDistance = 1200.f;

	/** Rows from the fighter table, one entry per body to spawn. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wave")
	TArray<FName> Fighters;

	/** Extra scaling applied on top of the stage tier. -1 uses the stage's tier. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wave")
	int32 TierOverride = -1;
};

/** A sealed route placed in a stage. */
USTRUCT(BlueprintType)
struct FGateDef
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gate")
	float Distance = 2400.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gate")
	EGateType Type = EGateType::Wall;

	/** Granted on opening. None means this gate pays experience instead. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gate")
	EAbility RewardAbility = EAbility::None;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gate")
	int32 RewardExperience = 0;
};

USTRUCT(BlueprintType)
struct FStageDef : public FTableRowBase
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stage")
	FText DisplayName;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stage")
	FText DisplayNameArabic;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stage", meta = (MultiLine = true))
	FText Briefing;

	/** Playable length along X, in cm. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stage")
	float Length = 12000.f;

	/** Raises every enemy's health and power in this stage. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stage")
	int32 Tier = 0;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stage")
	bool bIsBossStage = false;

	/** Endless mode: waves are generated instead of authored, and there is no exit. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stage")
	bool bSurvival = false;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stage")
	TArray<FWaveDef> Waves;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stage")
	TArray<FGateDef> Gates;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stage")
	TSoftObjectPtr<UWorld> Level;
};

/**
 * The tables below exist because the browser build grew systems the first
 * port did not have -- talents, upgrade tracks, an XP curve, weapons -- and
 * Tools/export/export.mjs now writes all of them. Each one is a straight
 * mirror of an assets/*.js file, so the shape is dictated by that file rather
 * than chosen here.
 */

/** An ability found in the world. Never bought; see FUpgradeDef for those. */
USTRUCT(BlueprintType)
struct FTalentDef : public FTableRowBase
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Talent")
	EAbility Ability = EAbility::None;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Talent")
	FText DisplayName;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Talent")
	FText DisplayNameArabic;

	/** The glyph the HUD draws for it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Talent")
	FString Icon;

	/** Mana spent per use. Zero for the traversal talents, which are passive. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Talent", meta = (ClampMin = "0"))
	float ManaCost = 0.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Talent", meta = (MultiLine = true))
	FText Description;
};

/** What a kind of sealed route wants. The placement of one is FGateDef. */
USTRUCT(BlueprintType)
struct FGateKindDef : public FTableRowBase
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Gate")
	EGateType GateType = EGateType::Wall;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Gate")
	EAbility RequiredAbility = EAbility::None;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Gate")
	FText DisplayName;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Gate")
	FText DisplayNameArabic;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Gate")
	FText Hint;

	/** Shutters take kicks and walls take punches: the right family of strike,
	    not just any hit. None means the gate opens on approach. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Gate")
	EAttackFamily BreakFamily = EAttackFamily::Box;
};

/** One bought level of one upgrade track. The browser holds this as a cost
    function; a DataTable cannot, so the export samples every level into a
    row and Unreal gets the lookup it wanted anyway. */
USTRUCT(BlueprintType)
struct FUpgradeDef : public FTableRowBase
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Upgrade")
	FName Track;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Upgrade")
	FText DisplayName;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Upgrade")
	FText DisplayNameArabic;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Upgrade")
	FText Description;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Upgrade", meta = (ClampMin = "1"))
	int32 Level = 1;

	/** Experience for this level alone. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Upgrade", meta = (ClampMin = "0"))
	int32 Cost = 120;

	/** Everything spent on this track to reach this level. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Upgrade", meta = (ClampMin = "0"))
	int32 CumulativeCost = 120;
};

/** One rung of the fighter's rank. Sampled from the browser's curve for the
    same reason the upgrade costs are. */
USTRUCT(BlueprintType)
struct FLevelDef : public FTableRowBase
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Level", meta = (ClampMin = "1"))
	int32 Level = 1;

	/** Total earned experience needed to stand here. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Level", meta = (ClampMin = "0"))
	int32 ExperienceRequired = 0;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Level", meta = (ClampMin = "0"))
	int32 StepFromPrevious = 0;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Level")
	FText Title;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Level")
	float BonusHealth = 0.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Level")
	float BonusMana = 0.f;
};

/** What a smashed crate can put in your hands. Every one multiplies punches
    and none of them touch kicks, so picking one up is a trade. */
USTRUCT(BlueprintType)
struct FWeaponDef : public FTableRowBase
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon")
	FText DisplayName;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon")
	FText DisplayNameArabic;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon", meta = (ClampMin = "1"))
	float DamageMultiplier = 1.9f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon")
	float BonusReach = 62.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon")
	float BonusKnockback = 360.f;

	/** Connecting swings before it gives out. Whiffs cost nothing but time. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon", meta = (ClampMin = "1"))
	int32 Uses = 12;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Presentation")
	float Length = 86.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Presentation")
	float Thickness = 10.8f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Presentation")
	TSoftObjectPtr<UStaticMesh> Mesh;
};

/** Difficulty multipliers, chosen on the map screen. */
USTRUCT(BlueprintType)
struct FDifficultyDef
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Difficulty")
	FText DisplayName;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Difficulty")
	float EnemyDamage = 1.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Difficulty")
	float EnemyHealth = 1.f;
};

/** Everything one strike needs to know about the blow that landed. */
USTRUCT(BlueprintType)
struct FHitResultData
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Hit")
	float Damage = 0.f;

	UPROPERTY(BlueprintReadOnly, Category = "Hit")
	bool bBlocked = false;

	UPROPERTY(BlueprintReadOnly, Category = "Hit")
	bool bParried = false;

	UPROPERTY(BlueprintReadOnly, Category = "Hit")
	bool bKnockdown = false;

	UPROPERTY(BlueprintReadOnly, Category = "Hit")
	FVector ImpactPoint = FVector::ZeroVector;
};

/** Static gameplay constants shared across the module. */
namespace AhmedGameplay
{
	/** The playfield is a strip: X runs along the stage, Y is depth. */
	constexpr float DepthMin = -420.f;
	constexpr float DepthMax = 420.f;

	/** How much of the arena is reserved so fights never happen under the HUD. */
	constexpr float ArenaWidth = 2200.f;

	constexpr float StaminaRegenPerSecond = 24.f;
	constexpr float BlockDamageMultiplier = 0.20f;
	constexpr float ParryWindow = 0.20f;
	constexpr float ComboWindow = 0.95f;
	constexpr float ComboResetTime = 1.7f;
	constexpr float RageMax = 100.f;

	/** At most this many enemies may be attacking at once, so crowds stay fair. */
	constexpr int32 MaxSimultaneousAttackers = 2;
}
