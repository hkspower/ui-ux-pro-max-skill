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
 * Content/Animation holds twenty Saud clips, twenty street clips and
 * seventeen boss clips, and
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
 * and, when a fighter has no clip of his own for something, the street
 * men's -- Saud's clips struck on the boxer's guard -- and then Saud's:
 *   /Game/Animation/Street/A_Street_<Clip>
 *   /Game/Animation/Saud/A_Saud_<Clip>
 * Since 2026-09-25 Saud stands as a mixed martial artist and nobody else
 * does. The bosses have their strikes, their guard and their own walks, and
 * borrow the rest (the dashes, a missing reaction) from the street men; the
 * street men have none of their own and do everything from the Street set.
 * Saud himself never borrows, nor does an Island creature (Monkey, Gorilla:
 * another skeleton). An attack's clip is its DT_Attacks row (A_Saud_Jab), the
 * rest are SaudFeel::ClipSuffix. A clip a set lacks is looked for again down
 * SaudFeel::FallbackChain (since 2026-10-04: a 360 diagonal its nearer
 * neighbour, a run clip its walk, a turn the guard), each the set's own way.
 *
 * A clip is never forced on anything already playing it, except when the
 * fighter's MotionSerial moves -- a second jab, a second hit -- which starts
 * it again from its first frame. Since 2026-10-02 one clip gives way to the
 * next on a crossfade (SaudFeel::CutBetween), and the anim instance pulls
 * the pick at the top of its own update, so the clip is this frame's.
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

	/** Hands the mesh the clip the fighter's state calls for. Pulled by
	    USaudMotionAnimInstance at the top of each of its updates, so the clip
	    is this frame's; ticked here only for a Blueprint's own Animation
	    Blueprint. DeltaSeconds runs a turn clip's own clock (TurnHold). */
	void PlayPicked(float DeltaSeconds = 0.f);

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
	/** The set the playing clip is from: AWaveDirector names a man's set
	    after he is made, and a new set is sent again whole. */
	FName PlayingSet = NAME_None;
	/** The clip last handed to our anim instance, for the cut out of it. */
	SaudFeel::EClip ShownClip = SaudFeel::EClip::Guard;
	bool bShown = false;
	TWeakObjectPtr<USaudMotionAnimInstance> ShownOn;

	/** The mesh's anim instance when it is ours; null when a Blueprint's. */
	USaudMotionAnimInstance* Driver() const;

	/** The turn clip playing to its end (SaudFeel::FTurnHold). */
	SaudFeel::FTurnHold TurnHold;

	UAnimSequence* Find(FName MotionSet, const FString& Clip);
	UAnimSequence* LoadOnce(const FString& Path);
};
