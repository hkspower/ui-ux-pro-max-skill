#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "Combat/SaudIK.h"
#include "SaudMotionAnimInstance.generated.h"

class AFighterBase;
class UAnimSequence;

/** One clip in the mix the proxy lays down. */
struct FSaudIKLayer
{
	UAnimSequence* Sequence = nullptr;
	float Time = 0.f;
	bool bLoop = false;
	float Weight = 0.f;
};

/**
 * Everything one frame of IK needs, in the mesh's component space unless it
 * says the world, gathered on the game thread and handed to the proxy at
 * the end of NativeUpdateAnimation. Nothing in here is a UObject the worker
 * thread would have to touch, and nothing in here is state: every field is
 * written again each update from the instance's members.
 */
struct FSaudIKFrame
{
	// The clips, newest first, their weights summing to 1 (SaudIK::FCrossfade),
	// and the newest's serial and time, which the stride meter reads.
	FSaudIKLayer Layers[SaudIK::MaxLayers];
	int32 NumLayers = 0;
	int32 ClipSerial = 0;
	float ClipTime = 0.f;
	double Clock = 0.0;                          // the clips' clock: the world's seconds, real under the title
	// Each foot's share down by the playing clips' measured plants
	// (SaudIK::MixDown, SaudPlants.h); -1 where they are not measured.
	float ClipDown[2] = { -1.f, -1.f };

	// The mesh in the world, the world's up in its space, the capsule's axis,
	// and his size against Saud's (SaudIK::BodyScale).
	FTransform ComponentToWorld = FTransform::Identity;
	FVector Up = FVector::UpVector;
	FVector Pivot = FVector::ZeroVector;
	float BodyScale = 1.f;

	// Feet: what the proxy's SaudIK::StepFeet needs from the world.
	bool bFeetWanted = false;                    // on the ground, standing: not down, dead or dashing
	bool bHoldFeet = false;                      // SaudIK::HoldsFeet
	bool bTeleported = false;                    // SaudIK::Teleported this frame
	int32 StrikeLeg = -1;                        // the side an attack is thrown with, all attack long; -1 none
	FVector Velocity = FVector::ZeroVector;      // the capsule's, world, flat
	bool bSettleFeet = false;                    // standing, not striking (SaudIK::SettleDrift)
	bool bStopping = false;                      // a walk crossfading to a stand (SaudIK::Stopping): the last swing lands first
	float ReleaseSeconds = SaudIK::ReleaseSeconds;   // a lifted foot's hand-back (SaudIK::ReleaseFor the newest clip)
	float StepSeconds = SaudIK::StepSeconds;         // a shuffle step (SaudIK::ShuffleFor his set)
	SaudIK::FGroundPoint Ground[2][2];           // [side][0 heel, 1 ball]: WORLD point and normal
	float AnkleRest[2] = { 0.f, 0.f };          // foot_'s height in the reference pose
	float BallRest[2] = { 0.f, 0.f };           // ball_'s
	FVector ToeLocal[2] = { FVector::ForwardVector, FVector::ForwardVector };      // rest directions in ball_ / foot_'s own frames
	FVector FootFwdLocal[2] = { FVector::ForwardVector, FVector::ForwardVector };
	FVector FootUpLocal[2] = { FVector::UpVector, FVector::UpVector };

	// The body: the hips' lag turns the root about Pivot; then the chain, root
	// first (spine_01, spine_02, spine_03, neck_01, head), each bone's yaw
	// about Up and pitch about its own level axis. Degrees, weighted already.
	float HipsYaw = 0.f;
	bool bChain = false;
	float ChainYaw[SaudIK::ChainBones] = { 0.f, 0.f, 0.f, 0.f, 0.f };
	float ChainPitch[SaudIK::ChainBones] = { 0.f, 0.f, 0.f, 0.f, 0.f };
	FVector ChainAxis[SaudIK::ChainBones] = { FVector::ZeroVector, FVector::ZeroVector, FVector::ZeroVector, FVector::ZeroVector, FVector::ZeroVector };

	// The strike: the point that lands and its side, the mark (his own, or in
	// front of his guard), his belt for a mark out of reach, how far short
	// the joint stops for its skin, and how much.
	SaudIK::ETip StrikeTip = SaudIK::ETip::None;
	int32 StrikeSide = 0;                        // 0 left, 1 right
	FVector StrikeMark = FVector::ZeroVector;
	FVector StrikeLow = FVector::ZeroVector;
	float StrikeSkin = 0.f;
	float StrikeAlpha = 0.f;

	// The block: the covering arm, where it meets the blow, glove or elbow, how much.
	int32 BlockSide = INDEX_NONE;
	bool bBlockHigh = true;
	FVector BlockMeet = FVector::ZeroVector;
	float BlockAlpha = 0.f;

	// The guard: how much of the face's own turn each fist is carried by.
	float GuardAlpha[2] = { 0.f, 0.f };

	// The lean into a curve, a start or a stop (SaudIK::FLean): the pelvis --
	// and the chain over it -- turned about LeanAxis (mesh space, level) by
	// LeanDegrees, the feet's share taken by the proxy.
	FVector LeanAxis = FVector(1.f, 0.f, 0.f);
	float LeanDegrees = 0.f;
};

/** What the proxy drew last frame, for the game thread: where to trace the
    feet next, and how fast the newest clip walks. */
struct FSaudFeetBack
{
	bool bValid = false;
	FVector Heel[2] = { FVector::ZeroVector, FVector::ZeroVector };   // world: foot_l/r as drawn
	FVector Ball[2] = { FVector::ZeroVector, FVector::ZeroVector };   // world: ball_l/r as drawn
	// each as drawn and how fast it went: the next traces are taken where it
	// will be, not where it was (SaudIK::FFootTrack, 2026-10-04)
	SaudIK::FFootTrack HeelTrack[2];
	SaudIK::FFootTrack BallTrack[2];
	SaudIK::FStrideMeter Stride;
};

/** The worker-thread half: lays the clips down and bends them. */
class FSaudMotionProxy : public FAnimInstanceProxy
{
public:
	FSaudMotionProxy() {}
	FSaudMotionProxy(UAnimInstance* Instance) : FAnimInstanceProxy(Instance) {}

	virtual bool Evaluate(FPoseContext& Output) override;

	/** This frame's, from the end of NativeUpdateAnimation. */
	void SetFrame(const FSaudIKFrame& In) { Frame = In; }
	const FSaudFeetBack& GetBack() const { return Back; }

private:
	FSaudIKFrame Frame;
	/** The feet's state, frame to frame: holds, smoothing, the stride meter, their share. */
	SaudIK::FFeetState Feet;
	FSaudFeetBack Back;
	double LastClock = -1.0;
	/** The strike's swing gate as drawn, moved at most its whole way in SaudIK::GateSeconds. */
	SaudIK::FGate StrikeGate;

	struct FLeg { FCompactPoseBoneIndex Root, Mid, End; FLeg() : Root(INDEX_NONE), Mid(INDEX_NONE), End(INDEX_NONE) {} };
	struct FLegBones
	{
		FCompactPoseBoneIndex Thigh, Calf, Foot, Ball;
		FLegBones() : Thigh(INDEX_NONE), Calf(INDEX_NONE), Foot(INDEX_NONE), Ball(INDEX_NONE) {}
	};

	void Extract(const FSaudIKLayer& Layer, FPoseContext& Into) const;
	void SolveLimb(FCSPose<FCompactPose>& CS, const FLeg& L, const FVector& Target, const FVector& Pole,
	               float Alpha, const FQuat* EndRotation, float Whole) const;
	void Place(FCSPose<FCompactPose>& CS, const FLeg& L, const FVector& Tip, const SaudIK::FTwoBone& To, bool bEndRigid) const;
	FCompactPoseBoneIndex Bone(const FBoneContainer& Bones, const FName& Name) const;
};

/**
 * The animation instance every fighter's mesh runs (USaudMotionComponent
 * sets it): no Animation Blueprint, no blend graph. It crossfades the clips
 * the motion component hands it and then solves, over that pose, what
 * SaudIK.h decides -- the hips' lag and the chest and face turned to the
 * man that matters, the feet held and on the ground, the striking point on
 * the man, a guard meeting the blow. The maths is SaudIK.h's; this is the
 * traces, the bone names and the transforms.
 */
UCLASS()
class SAUDFIGHTER_API USaudMotionAnimInstance : public UAnimInstance
{
	GENERATED_BODY()

public:
	/** Start a clip over a crossfade of CutSeconds. A clip already playing is
	    left alone unless bRestart; bMatchPhase starts a loop at the share of
	    its cycle the clip it replaces had reached (SaudFeel::CutBetween).
	    bTurn: a turn or pivot clip (Turn_L90 ... Pivot_180) that carries the
	    turn itself, so the hips' lag is cleared under it (SaudIK::TurnStep).
	    ShareShift, StartShare: SaudFeel::FCut's, for SaudIK::FCrossfade::Play. */
	void Play(UAnimSequence* Sequence, bool bLoop, bool bRestart, float CutSeconds = 0.f, bool bMatchPhase = false,
	          bool bTurn = false, float ShareShift = 0.f, float StartShare = -1.f);

	/** On real time rather than the world's: under the title, which holds
	    the world paused, he still breathes in his guard. A freeze (hit
	    stop) is the world's time and is never real time. */
	void SetRealTime(bool bOn) { bRealTime = bOn; }

	UFUNCTION(BlueprintPure, Category = "Motion")
	UAnimSequence* GetPlaying() const;

	/** The way the body was drawn facing last frame: the actor's yaw less the
	    hips' lag. Zero before the first update. The clip picker reads it, so
	    a walk is picked against the body the player sees. */
	FVector GetShownFacing() const;

	/** The solves, each switchable for a fighter that should not have it. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "IK")
	bool bFeetOnGround = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "IK")
	bool bHandsOnContact = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "IK")
	bool bHeadLooks = true;

	virtual void NativeInitializeAnimation() override;
	virtual void NativeUpdateAnimation(float DeltaSeconds) override;

	/** What the proxy is handed at the end of each update. */
	FSaudIKFrame Frame;

protected:
	virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override { return new FSaudMotionProxy(this); }
	virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy) override { delete InProxy; }

private:
	/** The clips SaudIK::FCrossfade's numbers index, held so the worker never
	    reads a collected clip. */
	UPROPERTY(Transient)
	TArray<TObjectPtr<UAnimSequence>> Clips;

	/** Each of Clips' measured plants (SaudPlants::Find by its asset name),
	    or null for a clip measure_plants.py has not measured. Static data. */
	TArray<const SaudPlants::FClip*> ClipPlants;

	/** Each of Clips: a turn or pivot clip, which carries its own turn. */
	TArray<bool> ClipTurns;

	/** Whether the newest clip is a turn or pivot clip. */
	bool NewestTurns() const;

	/** The newest clip's measured plants, or null. */
	const SaudPlants::FClip* NewestPlants() const;

	SaudIK::FCrossfade Fade;
	double Clock = 0.0;
	bool bRealTime = false;

	/** The rest pose's measures, once (Frame keeps them). */
	bool bMeasured = false;
	float BodyScale = 1.f;

	/** Feet: how long the capsule has been falling (a blow's push falls it a few frames). */
	float AirTime = 0.f;

	/** The lean into curves, starts and stops (SaudIK::StepLean). */
	SaudIK::FLean Lean;

	/** His shuffle step's seconds (SaudIK::ShuffleFor), for the set it was found for. */
	FName ShuffleSet = NAME_None;
	float ShuffleSeconds = 0.f;

	/** The strike: its kind, the man it is drawn to, his size, the mark held
	    in this mesh's space, and the guarded stop eased in. */
	SaudIK::FStrikeTrack StrikeTrack;
	SaudIK::FStrike Strike;
	TWeakObjectPtr<AFighterBase> StrikeVictim;
	float StrikeScale = 1.f;
	FVector StrikeMarkC = FVector::ZeroVector;
	FVector StrikeLowC = FVector::ZeroVector;
	SaudIK::FRamp StrikeGuarded;

	/** The block: the blow it holds, on its striker's clock. */
	SaudIK::FBlockTrack BlockTrack;
	TWeakObjectPtr<AFighterBase> BlockFrom;
	FName BlockRow = NAME_None;
	float BlockClock = 0.f;
	int32 BlockSideHeld = INDEX_NONE;
	bool bBlockHighHeld = true;
	FVector BlockMeetW = FVector::ZeroVector;

	/** The guard fists' shares. */
	SaudIK::FRamp GuardRamp[2];

	/** The body's turn, kept frame to frame (SaudIK::TurnStep), and who he looks at. */
	SaudIK::FTurn Turn;
	float LastYaw = 0.f;
	FVector LastLocation = FVector::ZeroVector;
	bool bTurnKnown = false;
	TWeakObjectPtr<AFighterBase> LookTarget;
	bool bLookAtThreat = false;

	void Measure(const USkeletalMeshComponent* Mesh);
	void UpdateFeet(AFighterBase* Fighter, const FSaudFeetBack& Back, bool bTeleported, float DeltaSeconds);
	void UpdateStrike(AFighterBase* Fighter, float DeltaSeconds);
	void UpdateBlock(AFighterBase* Fighter, float DeltaSeconds);
	void UpdateTurn(AFighterBase* Fighter, bool bTeleported, float DeltaSeconds);
	void UpdateGuard(AFighterBase* Fighter, float DeltaSeconds);
};
