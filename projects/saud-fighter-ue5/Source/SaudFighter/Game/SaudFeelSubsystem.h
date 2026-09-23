#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Combat/SaudFeel.h"
#include "Combat/SaudTypes.h"
#include "SaudFeelSubsystem.generated.h"

class AFighterBase;
class UCameraComponent;

/**
 * The weight of a blow: the freeze, the camera's jolt and push-in, and the
 * pad's buzz. AFighterBase::ReceiveHit calls OnBlow for every parry, block
 * and clean hit; the numbers are the browser's (Combat/SaudFeel.h).
 *
 * One per world, because the freeze is the world's clock and the camera is
 * the local player's. The freeze holds global time dilation near zero, and
 * everything here -- the freeze itself included -- runs out in real time,
 * the way the browser keeps drawing its shake while the fight stands still.
 *
 * The camera is whatever the local player is looking through, found each
 * frame rather than held, so a cutscene camera or a respawn needs nothing
 * wired. The victim's white flash is the fighter's own (AFighterBase::Tick):
 * it is a property of one body, not of the view.
 */
UCLASS()
class SAUDFIGHTER_API USaudFeelSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	static USaudFeelSubsystem* Get(const UObject* WorldContext);

	/** A blow landed on Victim: parried, blocked or clean, as Hit says. */
	void OnBlow(const AFighterBase* Victim, const AFighterBase* Attacker,
	            const FHitResultData& Hit, bool bHeavy);

	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	/** How far the world's clock runs during a freeze. The browser stops its
	    fight outright; zero is not a dilation Unreal takes, and this is below
	    anything a frame can show. */
	static constexpr float FrozenDilation = 0.001f;

	SaudFeel::FState Feel;

	/** True while this subsystem holds the world's clock, and what the clock
	    was before it did, so a freeze never leaves a slow-motion someone
	    else set at 1. */
	bool bHoldingTime = false;
	float DilationBefore = 1.f;

	/** Real seconds since the world began, for the shake's wave. */
	float RealClock = 0.f;

	/** The camera the shake and punch were last put on, and the field of
	    view and turn it had before they were. Left exactly as found when they end. */
	TWeakObjectPtr<UCameraComponent> Camera;
	float BaseFov = 0.f;
	FRotator BaseRotation = FRotator::ZeroRotator;
	bool bCameraMoved = false;

	void HoldTime();
	void ReleaseTime();
	void ApplyCamera();
	void RestoreCamera();
	void Buzz(const SaudFeel::FBlowFeel& F);
	UCameraComponent* FindCamera() const;
};
