#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "Combat/SaudIK.h"
#include "SaudMotionAnimInstance.generated.h"

class AFighterBase;
class UAnimSequence;

/**
 * Everything one frame of IK needs, in the mesh's component space, gathered
 * on the game thread and handed to the proxy. Nothing in here is a UObject
 * the worker thread would have to touch.
 */
struct FSaudIKFrame
{
	// The clip.
	UAnimSequence* Sequence = nullptr;
	float Time = 0.f;
	bool bLoop = false;

	// Feet: how far each foot moves (component space), the normal it stands
	// on, and how much of the whole leg solve applies.
	FVector FootOffset[2] = { FVector::ZeroVector, FVector::ZeroVector };
	FVector FootNormal[2] = { FVector::UpVector, FVector::UpVector };
	FVector PelvisOffset = FVector::ZeroVector;
	float FeetAlpha = 0.f;

	// The strike: which limb, where its end goes, how much.
	SaudIK::ELimb StrikeLimb = SaudIK::ELimb::None;
	int32 StrikeSide = 0;        // 0 left, 1 right
	FVector StrikeTarget = FVector::ZeroVector;
	float StrikeAlpha = 0.f;

	// The head: which way to look, how much.
	FVector Facing = FVector(1.f, 0.f, 0.f);
	FVector LookDir = FVector(1.f, 0.f, 0.f);
	float LookAlpha = 0.f;
};

/** The worker-thread half: plays the clip and bends it. */
class FSaudMotionProxy : public FAnimInstanceProxy
{
public:
	FSaudMotionProxy() {}
	FSaudMotionProxy(UAnimInstance* Instance) : FAnimInstanceProxy(Instance) {}

	virtual void PreUpdate(UAnimInstance* InAnimInstance, float DeltaSeconds) override;
	virtual bool Evaluate(FPoseContext& Output) override;

private:
	FSaudIKFrame Frame;

	struct FLeg { FCompactPoseBoneIndex Root, Mid, End; FLeg() : Root(INDEX_NONE), Mid(INDEX_NONE), End(INDEX_NONE) {} };
	void SolveLimb(FCSPose<FCompactPose>& CS, const FLeg& L, const FVector& Target, const FVector& Pole,
	               float Alpha, const FQuat* EndTilt) const;
	FCompactPoseBoneIndex Bone(const FBoneContainer& Bones, const FName& Name) const;
};

/**
 * The animation instance every fighter's mesh runs (USaudMotionComponent
 * sets it): no Animation Blueprint, no blend graph. It evaluates the one
 * clip the motion component hands it and then solves, over that pose, the
 * three things SaudIK.h decides -- feet on the ground, the striking hand on
 * the man, the head on the nearest opponent. The maths is SaudIK.h's; this
 * is the traces, the bone names and the transforms.
 */
UCLASS()
class SAUDFIGHTER_API USaudMotionAnimInstance : public UAnimInstance
{
	GENERATED_BODY()

public:
	/** Start a clip. A clip already playing is left alone unless bRestart. */
	void Play(UAnimSequence* Sequence, bool bLoop, bool bRestart);

	UFUNCTION(BlueprintPure, Category = "Motion")
	UAnimSequence* GetPlaying() const { return Playing; }

	/** The three solves, each switchable for a fighter that should not have it. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "IK")
	bool bFeetOnGround = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "IK")
	bool bHandsOnContact = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "IK")
	bool bHeadLooks = true;

	virtual void NativeInitializeAnimation() override;
	virtual void NativeUpdateAnimation(float DeltaSeconds) override;

	/** What the proxy copies on PreUpdate. Game thread writes, once a frame. */
	FSaudIKFrame Frame;

protected:
	virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override { return new FSaudMotionProxy(this); }
	virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy) override { delete InProxy; }

private:
	UPROPERTY(Transient)
	TObjectPtr<UAnimSequence> Playing = nullptr;

	float PlayTime = 0.f;
	bool bLooping = false;

	/** The feet's rest height above the mesh's floor, so a foot's height in
	    the clip is measured from its sole and not its ankle. From the
	    reference pose, once. */
	float AnkleRest = 0.f;
	bool bMeasured = false;

	/** Smoothed ground corrections, world Z, and the smoothed look. */
	float FootOffsetZ[2] = { 0.f, 0.f };
	float PelvisZ = 0.f;
	FVector LookDirWorld = FVector(1.f, 0.f, 0.f);

	void UpdateFeet(AFighterBase* Fighter, float DeltaSeconds);
	void UpdateStrike(AFighterBase* Fighter);
	void UpdateLook(AFighterBase* Fighter, float DeltaSeconds);
};
