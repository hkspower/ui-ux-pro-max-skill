#pragma once

#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "Combat/SaudTypes.h"
#include "SaudSaveGame.generated.h"

/** Lifetime counters, used by the achievement checks. */
USTRUCT(BlueprintType)
struct FSaudStats
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadWrite, Category = "Stats") int32 Kills = 0;
	UPROPERTY(BlueprintReadWrite, Category = "Stats") int32 CratesSmashed = 0;
	UPROPERTY(BlueprintReadWrite, Category = "Stats") int32 Parries = 0;
	UPROPERTY(BlueprintReadWrite, Category = "Stats") int32 ChampionClears = 0;
	UPROPERTY(BlueprintReadWrite, Category = "Stats") int32 FightsStarted = 0;
	UPROPERTY(BlueprintReadWrite, Category = "Stats") int32 StagesCleared = 0;
	UPROPERTY(BlueprintReadWrite, Category = "Stats") float TimeInTheRing = 0.f;
};

/**
 * The whole player profile. Mirrors the browser build's localStorage schema so
 * a save can be carried across, field for field.
 */
USTRUCT(BlueprintType)
struct FSaudProgress
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadWrite, Category = "Progress") int32 UnlockedStages = 1;
	UPROPERTY(BlueprintReadWrite, Category = "Progress") int32 Experience = 0;
	UPROPERTY(BlueprintReadWrite, Category = "Progress") int32 BestCombo = 0;
	UPROPERTY(BlueprintReadWrite, Category = "Progress") int32 SurvivalBest = 0;

	// Five upgrade tracks. Boxing and kicking scale their own attack families.
	UPROPERTY(BlueprintReadWrite, Category = "Progress") int32 BoxingLevel = 0;
	UPROPERTY(BlueprintReadWrite, Category = "Progress") int32 KickingLevel = 0;
	UPROPERTY(BlueprintReadWrite, Category = "Progress") int32 VitalityLevel = 0;
	UPROPERTY(BlueprintReadWrite, Category = "Progress") int32 SpeedLevel = 0;
	UPROPERTY(BlueprintReadWrite, Category = "Progress") int32 StaminaLevel = 0;

	/** 0 rookie, 1 pro, 2 champion. */
	UPROPERTY(BlueprintReadWrite, Category = "Progress") int32 DifficultyIndex = 1;

	/** The area the player is standing in, and every area they have reached.
	    The map screen draws '?' for anything not in VisitedStages and lets you
	    fast-travel to anything that is. */
	UPROPERTY(BlueprintReadWrite, Category = "Progress") FName CurrentStage;
	UPROPERTY(BlueprintReadWrite, Category = "Progress") TArray<FName> VisitedStages;
	UPROPERTY(BlueprintReadWrite, Category = "Progress") TArray<FName> ClearedStages;
	UPROPERTY(BlueprintReadWrite, Category = "Progress") TMap<FName, FName> StageRanks;
	UPROPERTY(BlueprintReadWrite, Category = "Progress") TArray<EAbility> Abilities;
	UPROPERTY(BlueprintReadWrite, Category = "Progress") TArray<FName> OpenGates;
	UPROPERTY(BlueprintReadWrite, Category = "Progress") TArray<FName> Achievements;
	UPROPERTY(BlueprintReadWrite, Category = "Progress") FSaudStats Stats;

	// Settings
	UPROPERTY(BlueprintReadWrite, Category = "Settings") bool bSound = true;
	UPROPERTY(BlueprintReadWrite, Category = "Settings") bool bMusic = true;
	UPROPERTY(BlueprintReadWrite, Category = "Settings") bool bVibration = true;

	/** Whether L_Prologue -- Saud's life before he fell -- has already played.
	    The one field on this struct that does NOT mirror the browser build's
	    schema: the browser has no prologue, so there is nothing on the other
	    side for this to travel with. See ASaudPrologueGameMode. */
	UPROPERTY(BlueprintReadWrite, Category = "Progress") bool bSeenPrologue = false;
};

UCLASS()
class SAUDFIGHTER_API USaudSaveGame : public USaveGame
{
	GENERATED_BODY()

public:
	UPROPERTY(BlueprintReadWrite, Category = "Save")
	FSaudProgress Progress;

	UPROPERTY(BlueprintReadWrite, Category = "Save")
	int32 SchemaVersion = 1;
};
