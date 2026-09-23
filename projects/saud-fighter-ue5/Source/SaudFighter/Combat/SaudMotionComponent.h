#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Combat/SaudFeel.h"
#include "SaudMotionComponent.generated.h"

class USaudMotionAnimInstance;

class AFighterBase;
class UAnimSequence;

/**
 * Plays the clip a fighter's state calls for.
 *
 * Content/Animation holds twenty Saud clips and seventeen boss clips, and
 * until 2026-09-23 nothing in the build played any of them: there is no
 * Animation Blueprint, and the fighters stood in their bind pose through
 * every punch. This is the smallest thing that plays them -- no blend
 * graph, no asset to author: the mesh runs USaudMotionAnimInstance, which
 * evaluates one clip and solves the runtime IK over it, and this swaps the
 * clip when the state changes. Which clip is SaudFeel::Pick, checked by the
 * harness; this only loads and hands over what it picks.
 *
 * Clips are found by name, the names the files already have:
 *   /Game/Animation/<Folder>/A_<MotionSet>_<Clip>
 * and, when a fighter has no clip of his own for something, Saud's:
 *   /Game/Animation/Saud/A_Saud_<Clip>
 * The bosses have their strikes and their guard and nothing else, so they
 * walk, block, reel and fall as Saud does; the street men have none of their
 * own and do everything as he does. An attack's clip is its DT_Attacks row
 * (A_Saud_Jab), the rest are SaudFeel::ClipSuffix.
 *
 * A clip is never forced on anything already playing it, except when the
 * fighter's MotionSerial moves -- a second jab, a second hit -- which starts
 * it again from its first frame.
 */
UCLASS(ClassGroup = (Saud), meta = (BlueprintSpawnableComponent))
class SAUDFIGHTER_API USaudMotionComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	USaudMotionComponent();

	virtual void BeginPlay() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType,
	                           FActorComponentTickFunction* ThisTickFunction) override;

	/** The clip playing now, for anything that wants to ask. */
	UFUNCTION(BlueprintPure, Category = "Motion")
	FName GetPlayingClip() const { return PlayingName; }

	/** Set false to leave the mesh to an Animation Blueprint instead. With
	    it on, the mesh runs USaudMotionAnimInstance -- the clip plus the
	    runtime IK -- unless a Blueprint gave it an Animation Blueprint of
	    its own, in which case that is kept and the clip goes to it through
	    PlayAnimation's single-node path, without IK. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Motion")
	bool bDriveMesh = true;

private:
	/** Loaded clips by full path, the misses included (as null), so a clip
	    that is not there is looked for once. */
	UPROPERTY(Transient)
	TMap<FName, TObjectPtr<UAnimSequence>> Loaded;

	FName PlayingName = NAME_None;
	uint32 PlayingSerial = 0;

	/** The mesh's anim instance when it is ours; null when a Blueprint's. */
	USaudMotionAnimInstance* Driver() const;

	UAnimSequence* Find(FName MotionSet, const FString& Clip);
	UAnimSequence* LoadOnce(const FString& Path);
};
