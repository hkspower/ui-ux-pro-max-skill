#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Combat/SaudTypes.h"
#include "AbilityGate.generated.h"

class UBoxComponent;
class UStaticMeshComponent;

DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnGateOpened);

class AAbilityGate;
/** Any gate, opened: its id and the gate. Native and static, so a system
    that wants every gate (the System's "GATE CLEARED" window) subscribes
    once rather than to each actor. Fired from AAbilityGate::Open(). */
DECLARE_MULTICAST_DELEGATE_TwoParams(FOnGateOpenedNative, FName, AAbilityGate*);

/**
 * The System's portal in a sealed way (Tools/look/portal.py draws it,
 * Tools/blender/build_gates.py makes and places its mesh). Its state is one
 * custom primitive data value, in slot DataIndex of the portal's own
 * component: 0 sealed (he lacks the talent), 1 openable (he has it), 1..2
 * opening (struck or used: the flare and the collapse), 2 gone. The
 * material reads the slot; portal.py holds these numbers to its mirror.
 */
namespace SaudPortal
{
	/** Not the camera's fade slot (SaudCamera::FadeDataIndex, 0). */
	constexpr int32 DataIndex = 1;
	/** Sealed to openable (and back), when the talent is gained. */
	constexpr float WakeSeconds = 0.6f;
	/** Openable to gone, once opened: the flare, then the collapse. */
	constexpr float OpenSeconds = 0.9f;
	constexpr float Sealed = 0.f;
	constexpr float Openable = 1.f;
	constexpr float Gone = 2.f;
}

/**
 * A sealed route. Ledges and gaps open by reaching them with the right
 * traversal ability; shutters and cracked walls take three strikes of the
 * matching family.
 *
 * Gates never block the way forward — place them off the critical path, set
 * into the back wall. A stage must stay completable whatever the player
 * carries, otherwise finding an ability late can soft-lock the run.
 */
UCLASS()
class SAUDFIGHTER_API AAbilityGate : public AActor
{
	GENERATED_BODY()

public:
	AAbilityGate();

	virtual void Tick(float DeltaSeconds) override;
	virtual void BeginPlay() override;

	/** Called by the player's strike resolution. Returns true if it counted. */
	UFUNCTION(BlueprintCallable, Category = "Gate")
	bool ReceiveStrike(EAttackFamily Family);

	UFUNCTION(BlueprintPure, Category = "Gate")
	bool IsOpen() const { return bOpen; }

	/** Which ability this gate wants, derived from its type. */
	UFUNCTION(BlueprintPure, Category = "Gate")
	EAbility GetRequiredAbility() const;

	/** True when the player already carries the key. */
	UFUNCTION(BlueprintPure, Category = "Gate")
	bool CanBeOpened() const;

	UPROPERTY(BlueprintAssignable, Category = "Gate")
	FOnGateOpened OnGateOpened;

	/** Every gate's opening, for systems that want them all. */
	static FOnGateOpenedNative OnAnyGateOpened;

	/** The portal's state as it is drawn (SaudPortal: 0 sealed .. 2 gone). */
	UFUNCTION(BlueprintPure, Category = "Gate")
	float GetPortalState() const { return PortalState; }

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gate")
	EGateType GateType = EGateType::Wall;

	/** Granted on opening. None means this gate pays experience instead. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gate")
	EAbility RewardAbility = EAbility::None;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gate")
	int32 RewardExperience = 0;

	/** Stable id so the opened state survives leaving and re-entering the level. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gate")
	FName GateId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gate", meta = (ClampMin = "1"))
	int32 StrikesToBreak = 3;

protected:
	void Open();

	UFUNCTION(BlueprintImplementableEvent, Category = "Gate", meta = (DisplayName = "On Opened"))
	void BP_OnOpened();

	UFUNCTION(BlueprintImplementableEvent, Category = "Gate", meta = (DisplayName = "On Struck"))
	void BP_OnStruck(int32 StrikesLanded);

	/** Drives the on-screen prompt: shown when the player is close enough. */
	UPROPERTY(BlueprintReadOnly, Category = "Gate")
	bool bPlayerNearby = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Gate")
	TObjectPtr<UStaticMeshComponent> Mesh = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Gate")
	TObjectPtr<UBoxComponent> Trigger = nullptr;

	/** The System's rift in the gate (SM_Portal_<Type>, set by the level
	    builders). Rides on the gate's mesh at its own size (absolute
	    scale: the gate's cube is scaled, the portal is in centimetres),
	    collides with nothing and casts no shadow. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Gate")
	TObjectPtr<UStaticMeshComponent> Portal = nullptr;

private:
	/** The state each tick: sealed or openable from the game instance
	    (HasAbility, through CanBeOpened; IsGateOpen), the flare once
	    opened; written to the portal's slot only when it changes. */
	void TickPortal(float DeltaSeconds);
	void WritePortal();

	float PortalState = SaudPortal::Sealed;
	float PortalWritten = -1.f;
	bool bOpening = false;
	bool bOpen = false;
	int32 StrikesLanded = 0;
	float ApproachHeld = 0.f;
};
