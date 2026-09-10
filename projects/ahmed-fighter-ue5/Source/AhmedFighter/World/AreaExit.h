#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Combat/AhmedTypes.h"
#include "AreaExit.generated.h"

class UBoxComponent;

/** Which edge of the area this is. Mirrors DT_World.json's West / East / Door. */
UENUM(BlueprintType)
enum class EAreaSide : uint8
{
	West,
	East,
	Door
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnExitRefused, EAbility, Needed, FName, NeedsClearing);

/**
 * A way out of an area, and the whole reason the nine levels are one world
 * rather than a stage select. Walk into it and, if you carry what it wants,
 * the next level loads with you at its matching edge.
 *
 * What it wants comes from DT_World.json via Tools/levels/build_levels.py,
 * which places one of these per link. Both halves of a link carry the same
 * requirement, so a route is sealed from whichever side you arrive at; the
 * browser project's control panel guarantees that when the graph is edited.
 *
 * A refused exit pushes the player back a step and broadcasts why, so the HUD
 * can say SEALED — NEEDS VAULT the way the browser build does.
 *
 * On an open-world map (Tools/fab/lay_out_world.py) every district is in the
 * same level and the exit is a doorway rather than a load: it names the exit
 * it opens onto and steps the player through to it, carrying nothing across
 * because nothing has to be.
 */
UCLASS()
class AHMEDFIGHTER_API AAreaExit : public AActor
{
	GENERATED_BODY()

public:
	AAreaExit();

	virtual void BeginPlay() override;

	/** Level to open. The map's asset name, e.g. L_BaytAlDarb. Unused when
	    the destination is in this level -- see DestinationExit. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Exit")
	FName DestinationLevel;

	/** The far side's doorway, when it is in this same level. Set, the exit
	    steps the player through to it instead of opening DestinationLevel. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Exit")
	TObjectPtr<AAreaExit> DestinationExit = nullptr;

	/** Where an arriving player is stood, along X from this exit: a step
	    inside the district, clear of the trigger so he does not bounce back. */
	UFUNCTION(BlueprintPure, Category = "Exit")
	FVector GetLandingLocation() const;

	/** Stage row of the destination, for the HUD and the save. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Exit")
	FName DestinationStage;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Exit")
	EAreaSide Side = EAreaSide::East;

	/** Talent the route wants. None means it is open. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Exit")
	EAbility RequiredAbility = EAbility::None;

	/** Stage row that must be cleared first. None means always. This is how
	    the Souq's shortcut to the Desert only exists once the Desert is beaten
	    from the far side. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Exit")
	FName AfterClearedStage;

	/** The far side's edge to arrive at. Stored as an option the destination
	    level reads on load, so the player appears at the right end. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Exit")
	EAreaSide ArriveAt = EAreaSide::West;

	UPROPERTY(BlueprintAssignable, Category = "Exit")
	FOnExitRefused OnExitRefused;

	UFUNCTION(BlueprintPure, Category = "Exit")
	bool IsOpenFor(const class UAhmedGameInstance* GI) const;

protected:
	UFUNCTION()
	void HandleOverlap(UPrimitiveComponent* OverlappedComp, AActor* Other,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep,
		const FHitResult& Sweep);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Exit")
	TObjectPtr<UBoxComponent> Trigger = nullptr;

private:
	/** A refusal every frame would spam the HUD; one per approach is enough. */
	float RefuseCooldown = 0.f;
	bool bTravelling = false;
};
