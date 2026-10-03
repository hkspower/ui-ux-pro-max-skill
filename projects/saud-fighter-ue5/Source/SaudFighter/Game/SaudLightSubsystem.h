#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "SaudLightSubsystem.generated.h"

class ULocalLightComponent;

/**
 * The night's shadow budget, in the world (Combat/SaudLight.h).
 *
 * Every SaudLight::RecheckSeconds it finds the lights the world builder
 * spawned shadowed (actor tag SaudLight::ShadowTag: the fires, Tools/
 * blender/build_souq.py spawn_night) among those streamed in, and lets only
 * the ShadowBudget nearest the camera cast; the rest stay lit, unshadowed.
 * spawn_night() makes them Movable so their shadows can be switched.
 * How far each light is drawn at all is the light's own MaxDrawDistance,
 * set by the builder; nothing here touches it.
 *
 * A level with no tagged lights (the title, a stage level) costs one scan
 * of its lights four times a second and changes nothing.
 */
UCLASS()
class SAUDFIGHTER_API USaudLightSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	float Clock = 0.f;

	/** Kept between checks only so the arrays are not reallocated. */
	TArray<TWeakObjectPtr<ULocalLightComponent>> Lights;
	TArray<float> Dist;
	TArray<bool> Was;
	TArray<bool> Casts;
};
