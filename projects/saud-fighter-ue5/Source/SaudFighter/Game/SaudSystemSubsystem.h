#pragma once

#include "CoreMinimal.h"
#include "Engine/DataTable.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Combat/SaudSystem.h"
#include "Combat/SaudTypes.h"
#include "SaudSystemSubsystem.generated.h"

class AAbilityGate;
class AWaveDirector;
class USaudGameInstance;

/**
 * One line of the System's (Content/Data/DT_SystemLines.json): which event
 * it is, keyed by what it is about (a stage, a rank, a talent, a speaker),
 * and its words -- English, as drawn, with the {placeholders} SaudSystem::
 * Format fills -- and, where the game's data already carries it, that
 * data's Arabic, kept as data (FCanvas does no Arabic shaping, so none of
 * it is drawn). Hand-authored, like DT_Prologue.json; import it as a
 * DataTable of this row at /Game/Data/DT_SystemLines, or leave it as the
 * JSON file, which the subsystem reads from disk when the table is not
 * there.
 */
USTRUCT(BlueprintType)
struct FSaudSystemLine : public FTableRowBase
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "System") FName Event;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "System") FName Key;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "System") FString Title;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "System") FString Head;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "System") FString Body;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "System") FString Reward;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "System") FString Beneath;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "System") FString Status;
	/** A stage's English name (DT_Stages' DisplayName), for reference. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "System") FString Area;
	/** The data's own Arabic: the stage's, the talent's or the fighter's
	    DisplayNameArabic, and a stage's BriefingArabic. Never drawn. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "System") FString NameArabic;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "System") FString StoryArabic;
};

/**
 * The System: the Halqa talking to Saud, in windows (2026-10-07).
 *
 * It listens -- USaudGameInstance's OnAbilityGranted (SKILL ACQUIRED) and
 * OnExperienceChanged (LEVEL UP, RANK, from the game's own level math,
 * USaudGameInstance::GetLevel / GetRankIndex), AAbilityGate::OnAnyGateOpened
 * (GATE CLEARED), and four one-line hooks: AWaveDirector::Tick (the area
 * he stands in: its quest, the first landing's FIND THE WAY UP, the ring
 * closing), AWaveDirector::BeginWave (a boss: the hand-off to the HUD's
 * WARNING, and AL-SAQR's line), ASaudGameMode::CompleteStage (QUEST
 * COMPLETE, and the victory's QUEST REMOVED) and ASaudGameMode::FailStage
 * (YOU WENT DOWN) -- and turns each into a SaudSystem::FSysEvent with its
 * line's words. SaudSystem::FModel (Combat/SaudSystem.h, checked by the
 * harness) does the rest: the queue, the timings, the open quest. The HUD
 * advances it each frame in real time and draws it (ASaudHUD); the look
 * gets its flourish (USaudLookSubsystem::OnSystemEvent) as a window opens.
 *
 * A game-instance subsystem, so a step from one level to the next does not
 * lose a window waiting to be said, or the area he came from.
 */
UCLASS()
class SAUDFIGHTER_API USaudSystemSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	static USaudSystemSubsystem* Get(const UObject* WorldContext);

	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	// ----------------------------------------------------------- the hooks
	/** AWaveDirector::Tick, every frame: when the player stands in this
	    director's district, that is the area he is in. */
	static void DirectorTick(const AWaveDirector* Director);
	/** AWaveDirector::BeginWave, for a boss's wave: Row is his fighter row. */
	static void BossWave(const AWaveDirector* Director, FName Row);
	/** ASaudGameMode::CompleteStage: the stage and all it paid. */
	static void StageCleared(const UObject* WorldContext, FName StageRow, int32 Experience);
	/** ASaudGameMode::FailStage: he went down. */
	static void WentDown(const UObject* WorldContext);

	// ------------------------------------------------------------- the HUD
	/** Runs the windows' clock: Real seconds (0 under a menu), the world's
	    seconds beside them. The look's flourish for what opens. */
	void Advance(float RealSeconds, float WorldSeconds, UWorld* World);
	const SaudSystem::FModel& Model() const { return System; }

private:
	UFUNCTION()
	void HandleAbilityGranted(EAbility Ability);

	UFUNCTION()
	void HandleExperienceChanged(int32 NewTotal);

	void HandleGateOpened(FName GateId, AAbilityGate* Gate);

	void PlayerIn(FName Stage);
	void LoadLines();
	const FSaudSystemLine* Line(SaudSystem::EKind Kind, FName Key) const;
	void Say(SaudSystem::EKind Kind, FName Key, const SaudSystem::FArgs& Args = SaudSystem::FArgs());
	USaudGameInstance* Game() const;
	/** The level he stands at now, so the next rise is one he earned. */
	void SampleLevel();
	/** HP and MP a level rise is worth: DT_Levels' BonusHealth and
	    BonusMana between the two. */
	void LevelBonus(int32 From, int32 To, int32& OutHp, int32& OutMp) const;
	/** No XP, nothing cleared, no talent, nothing bought: a new profile. */
	bool IsFresh() const;

	UPROPERTY(Transient)
	TMap<FName, FSaudSystemLine> Lines;

	SaudSystem::FModel System;

	/** The area he is in, and the one before it (the ring closes when the
	    souq follows the camp of fires). */
	FName CurrentStage = NAME_None;
	FName LastStage = NAME_None;
	/** Areas whose quest has been given this session. */
	TSet<FName> Announced;
	bool bQuestGiven = false;
	bool bRingClosed = false;
	bool bSaqrSpoken = false;

	int32 LastLevel = 0;
	TWeakObjectPtr<UWorld> LastWorld;
	FDelegateHandle GateHandle;
};
