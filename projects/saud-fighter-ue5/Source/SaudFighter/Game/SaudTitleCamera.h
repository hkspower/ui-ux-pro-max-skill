#pragma once

#include "CoreMinimal.h"
#include "Camera/CameraActor.h"
#include "SaudTitleCamera.generated.h"

class AFighterBase;

/**
 * The camera behind the title -- 2026-10-01 (Riyadh), asked as "make suad
 * main menu game": Saud himself, live, in his guard where the level put
 * him, with the menu over the left of the screen and the camera sweeping
 * slowly in front of him.
 *
 * Where it stands is Combat/SaudTitle.h (Shoot, FrameFor), engine-free and
 * held by Tools/harness/tests/title.cpp; this only asks it every frame and
 * puts itself there. It runs on real time and ticks through the pause, as
 * the menu does: the title holds the world paused.
 *
 * The one thing the harness cannot know is the level: a sphere is swept
 * from the point the shot aims through him out to the eye, on the camera
 * channel, and the eye is pulled in to the first wall it meets. In a close
 * alley that trades the framing for a view of him rather than of a wall.
 *
 * USaudMenuSubsystem spawns it when the Title opens and blends the view
 * back to the pawn's own camera when FIGHT / CONTINUE is chosen.
 */
UCLASS(NotPlaceable)
class SAUDFIGHTER_API ASaudTitleCamera : public ACameraActor
{
	GENERATED_BODY()

public:
	ASaudTitleCamera();

	/** Frame him. His feet and facing are taken now and held: under the
	    title he does not move. */
	void Follow(AFighterBase* Him);

	virtual void Tick(float DeltaSeconds) override;

private:
	TWeakObjectPtr<AFighterBase> Subject;
	FVector Feet = FVector::ZeroVector;
	FVector Facing = FVector(1.f, 0.f, 0.f);
	/** Seconds of the sweep, real time. */
	float Clock = 0.f;

	void Place();
};
