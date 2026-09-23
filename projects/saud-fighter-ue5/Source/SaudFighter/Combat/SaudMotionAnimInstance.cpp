#include "Combat/SaudMotionAnimInstance.h"
#include "Combat/FighterBase.h"
#include "Combat/SaudArena.h"

#include "Animation/AnimSequence.h"
#include "AnimationRuntime.h"
#include "BonePose.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"

namespace
{
	// The mannequin's names, the 62-bone strip every man exports.
	const FName PelvisBone(TEXT("pelvis"));
	const FName NeckBone(TEXT("neck_01"));
	const FName HeadBone(TEXT("head"));
	const FName ThighBone[2] = { FName(TEXT("thigh_l")), FName(TEXT("thigh_r")) };
	const FName CalfBone[2]  = { FName(TEXT("calf_l")),  FName(TEXT("calf_r")) };
	const FName FootBone[2]  = { FName(TEXT("foot_l")),  FName(TEXT("foot_r")) };
	const FName UpperBone[2] = { FName(TEXT("upperarm_l")), FName(TEXT("upperarm_r")) };
	const FName LowerBone[2] = { FName(TEXT("lowerarm_l")), FName(TEXT("lowerarm_r")) };
	const FName HandBone[2]  = { FName(TEXT("hand_l")),  FName(TEXT("hand_r")) };

	/** How far above and below the character's floor a foot is looked for. */
	constexpr float TraceUp = 60.f;
	constexpr float TraceDown = 70.f;
	/** The eyes sit this far above the head bone. */
	constexpr float EyesAboveHead = 10.f;
}

/* ================================================================= proxy */

FCompactPoseBoneIndex FSaudMotionProxy::Bone(const FBoneContainer& Bones, const FName& Name) const
{
	const int32 Mesh = Bones.GetPoseBoneIndexForBoneName(Name);
	return Mesh == INDEX_NONE ? FCompactPoseBoneIndex(INDEX_NONE) : Bones.MakeCompactPoseIndex(FMeshPoseBoneIndex(Mesh));
}

void FSaudMotionProxy::PreUpdate(UAnimInstance* InAnimInstance, float DeltaSeconds)
{
	FAnimInstanceProxy::PreUpdate(InAnimInstance, DeltaSeconds);
	if (const USaudMotionAnimInstance* Inst = Cast<USaudMotionAnimInstance>(InAnimInstance))
	{
		Frame = Inst->Frame;
	}
}

bool FSaudMotionProxy::Evaluate(FPoseContext& Output)
{
	if (!Frame.Sequence)
	{
		Output.ResetToRefPose();
		return true;
	}

	// The clip, at the time the game thread advanced it to.
	FAnimationPoseData PoseData(Output);
	Frame.Sequence->GetAnimationPose(PoseData, FAnimExtractContext(static_cast<double>(Frame.Time), false, FDeltaTimeRecord(), Frame.bLoop));

	const bool bFeet = Frame.FeetAlpha > 0.f;
	const bool bStrike = Frame.StrikeAlpha > 0.f && Frame.StrikeLimb != SaudIK::ELimb::None;
	const bool bLook = Frame.LookAlpha > 0.f;
	if (!bFeet && !bStrike && !bLook)
	{
		return true;
	}

	const FBoneContainer& Bones = Output.Pose.GetBoneContainer();
	FCSPose<FCompactPose> CS;
	CS.InitPose(Output.Pose);

	// ---- the pelvis first, so every leg read below starts from where it is
	if (bFeet)
	{
		const FCompactPoseBoneIndex Pelvis = Bone(Bones, PelvisBone);
		if (Pelvis.IsValid())
		{
			FTransform T = CS.GetComponentSpaceTransform(Pelvis);
			T.AddToTranslation(Frame.PelvisOffset * Frame.FeetAlpha);
			CS.SetComponentSpaceTransform(Pelvis, T);
		}
		for (int32 S = 0; S < 2; ++S)
		{
			FLeg L;
			L.Root = Bone(Bones, ThighBone[S]); L.Mid = Bone(Bones, CalfBone[S]); L.End = Bone(Bones, FootBone[S]);
			if (!L.Root.IsValid() || !L.Mid.IsValid() || !L.End.IsValid()) continue;
			// A striking leg is the strike's; the ground has no say in a kick.
			if (bStrike && Frame.StrikeLimb == SaudIK::ELimb::Leg && Frame.StrikeSide == S) continue;

			const FVector Ankle = CS.GetComponentSpaceTransform(L.End).GetLocation();
			const FVector Knee = CS.GetComponentSpaceTransform(L.Mid).GetLocation();
			const FQuat Tilt = FQuat::FindBetweenNormals(FVector::UpVector, Frame.FootNormal[S].GetSafeNormal());
			SolveLimb(CS, L, Ankle + Frame.FootOffset[S], Knee, Frame.FeetAlpha, &Tilt);
		}
	}

	// ---- the striking limb
	if (bStrike)
	{
		FLeg L;
		const int32 S = Frame.StrikeSide;
		if (Frame.StrikeLimb == SaudIK::ELimb::Arm)
		{
			L.Root = Bone(Bones, UpperBone[S]); L.Mid = Bone(Bones, LowerBone[S]); L.End = Bone(Bones, HandBone[S]);
		}
		else
		{
			L.Root = Bone(Bones, ThighBone[S]); L.Mid = Bone(Bones, CalfBone[S]); L.End = Bone(Bones, FootBone[S]);
		}
		if (L.Root.IsValid() && L.Mid.IsValid() && L.End.IsValid())
		{
			const FVector Mid = CS.GetComponentSpaceTransform(L.Mid).GetLocation();
			SolveLimb(CS, L, Frame.StrikeTarget, Mid, Frame.StrikeAlpha, nullptr);
		}
	}

	// ---- the head: turned from where the body faces to where it looks, the
	// neck taking its share. About each joint, so nothing moves but the turn.
	if (bLook)
	{
		const FQuat Turn = FQuat::FindBetweenNormals(Frame.Facing.GetSafeNormal(), Frame.LookDir.GetSafeNormal());
		const FQuat Blend = FQuat::Slerp(FQuat::Identity, Turn, Frame.LookAlpha);
		const FQuat NeckQ = FQuat::Slerp(FQuat::Identity, Blend, SaudIK::NeckShare);
		const FQuat HeadQ = FQuat::Slerp(FQuat::Identity, Blend, 1.f - SaudIK::NeckShare);
		const FCompactPoseBoneIndex Neck = Bone(Bones, NeckBone);
		const FCompactPoseBoneIndex Head = Bone(Bones, HeadBone);
		if (Neck.IsValid())
		{
			FTransform T = CS.GetComponentSpaceTransform(Neck);
			T.SetRotation(NeckQ * T.GetRotation());
			CS.SetComponentSpaceTransform(Neck, T);
		}
		if (Head.IsValid())
		{
			// Read after the neck moved, so the head turns from where the neck put it.
			FTransform T = CS.GetComponentSpaceTransform(Head);
			T.SetRotation(HeadQ * T.GetRotation());
			CS.SetComponentSpaceTransform(Head, T);
		}
	}

	FCSPose<FCompactPose>::ConvertComponentPosesToLocalPoses(MoveTemp(CS), Output.Pose);
	return true;
}

void FSaudMotionProxy::SolveLimb(FCSPose<FCompactPose>& CS, const FLeg& L, const FVector& Target, const FVector& Pole,
                                 float Alpha, const FQuat* EndTilt) const
{
	FTransform RootT = CS.GetComponentSpaceTransform(L.Root);
	FTransform MidT = CS.GetComponentSpaceTransform(L.Mid);
	FTransform EndT = CS.GetComponentSpaceTransform(L.End);
	const FVector Root = RootT.GetLocation(), Mid = MidT.GetLocation(), End = EndT.GetLocation();

	const FVector Wanted = FMath::Lerp(End, Target, FMath::Clamp(Alpha, 0.f, 1.f));
	const SaudIK::FTwoBone R = SaudIK::TwoBone(Root, Mid, End, Wanted, Pole);

	// Each segment turns by what its direction turned; positions come from
	// the solve, so the lengths are the clip's to the millimetre.
	const FQuat RootTurn = FQuat::FindBetweenNormals((Mid - Root).GetSafeNormal(), (R.Mid - Root).GetSafeNormal());
	RootT.SetRotation(RootTurn * RootT.GetRotation());
	CS.SetComponentSpaceTransform(L.Root, RootT);

	const FQuat MidTurn = FQuat::FindBetweenNormals((End - Mid).GetSafeNormal(), (R.End - R.Mid).GetSafeNormal());
	MidT.SetRotation(MidTurn * MidT.GetRotation());
	MidT.SetLocation(R.Mid);
	CS.SetComponentSpaceTransform(L.Mid, MidT);

	// The end keeps the clip's orientation (a fist stays a fist, a foot stays
	// flat), tilted to the ground when there is ground.
	if (EndTilt)
	{
		EndT.SetRotation(FQuat::Slerp(FQuat::Identity, *EndTilt, Alpha) * EndT.GetRotation());
	}
	EndT.SetLocation(R.End);
	CS.SetComponentSpaceTransform(L.End, EndT);
}

/* ============================================================== instance */

void USaudMotionAnimInstance::NativeInitializeAnimation()
{
	Super::NativeInitializeAnimation();
	bMeasured = false;
}

void USaudMotionAnimInstance::Play(UAnimSequence* Sequence, bool bLoop, bool bRestart)
{
	if (Sequence != Playing || bRestart)
	{
		PlayTime = 0.f;
	}
	Playing = Sequence;
	bLooping = bLoop;
}

void USaudMotionAnimInstance::NativeUpdateAnimation(float DeltaSeconds)
{
	Super::NativeUpdateAnimation(DeltaSeconds);

	// The clip's clock. DeltaSeconds is the world's, so a freeze holds it.
	if (Playing)
	{
		const float Len = Playing->GetPlayLength();
		PlayTime += DeltaSeconds;
		if (bLooping && Len > 0.f)
		{
			PlayTime = FMath::Fmod(PlayTime, Len);
		}
		else
		{
			PlayTime = FMath::Min(PlayTime, Len);     // the last frame holds
		}
	}
	Frame.Sequence = Playing;
	Frame.Time = PlayTime;
	Frame.bLoop = bLooping;

	AFighterBase* Fighter = Cast<AFighterBase>(TryGetPawnOwner());
	USkeletalMeshComponent* Mesh = GetSkelMeshComponent();
	Frame.FeetAlpha = Frame.StrikeAlpha = Frame.LookAlpha = 0.f;
	if (!Fighter || !Mesh || !Mesh->GetSkeletalMeshAsset())
	{
		return;
	}

	if (!bMeasured)
	{
		// The ankle's height in the reference pose, mesh space: the mesh's
		// origin is on its floor, so this is the sole to the ankle.
		const FReferenceSkeleton& Ref = Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();
		const int32 Foot = Ref.FindBoneIndex(FootBone[0]);
		AnkleRest = Foot == INDEX_NONE ? 0.f : FAnimationRuntime::GetComponentSpaceTransformRefPose(Ref, Foot).GetLocation().Z;
		bMeasured = true;
	}

	if (bFeetOnGround) UpdateFeet(Fighter, DeltaSeconds);
	if (bHandsOnContact) UpdateStrike(Fighter);
	if (bHeadLooks) UpdateLook(Fighter, DeltaSeconds);
}

void USaudMotionAnimInstance::UpdateFeet(AFighterBase* Fighter, float DeltaSeconds)
{
	USkeletalMeshComponent* Mesh = GetSkelMeshComponent();
	UWorld* World = GetWorld();
	const UCapsuleComponent* Capsule = Fighter->GetCapsuleComponent();
	if (!Mesh || !World || !Capsule) return;

	// No ground under a man in the air, on the floor, or mid-dash: the clip
	// is his then. The alpha eases so a landing does not snap the feet.
	const UCharacterMovementComponent* Move = Fighter->GetCharacterMovement();
	const bool bWants = !(Move && Move->IsFalling())
		&& Fighter->State != EFighterState::Down && Fighter->State != EFighterState::Dead
		&& Fighter->State != EFighterState::Dash;
	Frame.FeetAlpha = SaudIK::Settle(Frame.FeetAlpha, bWants ? 1.f : 0.f, SaudIK::FootSettleRate, DeltaSeconds);

	const float FloorZ = Fighter->GetActorLocation().Z - Capsule->GetScaledCapsuleHalfHeight();
	FCollisionQueryParams Params(SCENE_QUERY_STAT(SaudFootIK), false, Fighter);

	SaudIK::FFootGround Ground[2];
	for (int32 S = 0; S < 2; ++S)
	{
		// Last frame's foot: one frame stale, which at any frame rate a
		// fight runs at is under a centimetre of a walking foot.
		const FVector Foot = Mesh->GetSocketLocation(FootBone[S]);
		Ground[S].FootHeight = FMath::Max(0.f, Foot.Z - FloorZ - AnkleRest);

		FHitResult Hit;
		const FVector Start(Foot.X, Foot.Y, FloorZ + TraceUp);
		const FVector End(Foot.X, Foot.Y, FloorZ - TraceDown);
		if (World->LineTraceSingleByChannel(Hit, Start, End, ECC_WorldStatic, Params))
		{
			Ground[S].bHit = true;
			Ground[S].GroundDelta = Hit.ImpactPoint.Z - FloorZ;
			Ground[S].Normal = Hit.ImpactNormal;
		}
	}

	// Smoothed, in world Z; handed over in the mesh's own space.
	const FTransform& C2W = Mesh->GetComponentTransform();
	PelvisZ = SaudIK::Settle(PelvisZ, SaudIK::PelvisOffset(Ground[0], Ground[1]), SaudIK::PelvisSettleRate, DeltaSeconds);
	Frame.PelvisOffset = C2W.InverseTransformVectorNoScale(FVector(0.f, 0.f, PelvisZ));
	for (int32 S = 0; S < 2; ++S)
	{
		FootOffsetZ[S] = SaudIK::Settle(FootOffsetZ[S], SaudIK::FootOffset(Ground[S]), SaudIK::FootSettleRate, DeltaSeconds);
		Frame.FootOffset[S] = C2W.InverseTransformVectorNoScale(FVector(0.f, 0.f, FootOffsetZ[S]));
		Frame.FootNormal[S] = C2W.InverseTransformVectorNoScale(SaudIK::FootNormal(Ground[S])).GetSafeNormal();
	}
}

void USaudMotionAnimInstance::UpdateStrike(AFighterBase* Fighter)
{
	USkeletalMeshComponent* Mesh = GetSkelMeshComponent();
	Frame.StrikeLimb = SaudIK::ELimb::None;
	Frame.StrikeAlpha = 0.f;
	if (!Mesh || Fighter->State != EFighterState::Attack) return;
	const FAttackDef* Attack = Fighter->GetCurrentAttack();
	if (!Attack) return;

	char Side = 0;
	const SaudIK::ELimb Limb = SaudIK::StrikingLimb(TCHAR_TO_ANSI(*Fighter->GetCurrentAttackRow().ToString()), Side);
	if (Limb == SaudIK::ELimb::None) return;
	const int32 S = Side == 'r' ? 1 : 0;

	const float Alpha = SaudIK::ContactAlpha(Fighter->GetAttackElapsed(), Attack->Startup, Attack->Active);
	if (Alpha <= 0.f) return;

	// The man it is thrown at: the nearest opponent inside the blow's own
	// box, a little wider, so the pull starts before the hit resolves.
	TArray<AFighterBase*> Targets;
	Fighter->GatherOpponents(Targets);
	const FVector Origin = Fighter->GetActorLocation();
	const FVector Facing = Fighter->GetFacing();
	AFighterBase* Victim = nullptr;
	float Best = TNumericLimits<float>::Max();
	for (AFighterBase* T : Targets)
	{
		if (!IsValid(T) || !T->IsAlive()) continue;
		if (!SaudArena::InHitbox(Origin, Facing, T->GetActorLocation(), Attack->Reach + 40.f, Attack->DepthTolerance)) continue;
		const float D = FVector::DistSquared2D(Origin, T->GetActorLocation());
		if (D < Best) { Best = D; Victim = T; }
	}
	if (!Victim) return;

	const FName& RootName = Limb == SaudIK::ELimb::Arm ? UpperBone[S] : ThighBone[S];
	const FName& MidName = Limb == SaudIK::ELimb::Arm ? LowerBone[S] : CalfBone[S];
	const FName& EndName = Limb == SaudIK::ELimb::Arm ? HandBone[S] : FootBone[S];
	const FVector Root = Mesh->GetSocketLocation(RootName);
	const FVector Mid = Mesh->GetSocketLocation(MidName);
	const FVector End = Mesh->GetSocketLocation(EndName);
	const float Length = FVector::Dist(Root, Mid) + FVector::Dist(Mid, End);
	const UCapsuleComponent* Cap = Victim->GetCapsuleComponent();
	const float Radius = Cap ? Cap->GetScaledCapsuleRadius() : 34.f;

	const FVector Target = SaudIK::ContactTarget(Root, End, Victim->GetActorLocation(), Radius, Length);
	Frame.StrikeLimb = Limb;
	Frame.StrikeSide = S;
	Frame.StrikeTarget = Mesh->GetComponentTransform().InverseTransformPosition(Target);
	Frame.StrikeAlpha = Alpha;
}

void USaudMotionAnimInstance::UpdateLook(AFighterBase* Fighter, float DeltaSeconds)
{
	USkeletalMeshComponent* Mesh = GetSkelMeshComponent();
	if (!Mesh) return;

	// Nobody to look at while reeling, down or dead; the clip has the head.
	const bool bWants = Fighter->State != EFighterState::Hit && Fighter->State != EFighterState::Down
		&& Fighter->State != EFighterState::Dead;

	TArray<AFighterBase*> Targets;
	Fighter->GatherOpponents(Targets);
	const FVector Eyes = Mesh->GetSocketLocation(HeadBone) + FVector(0.f, 0.f, EyesAboveHead);
	AFighterBase* Nearest = nullptr;
	float Best = TNumericLimits<float>::Max();
	for (AFighterBase* T : Targets)
	{
		if (!IsValid(T) || !T->IsAlive()) continue;
		const float D = FVector::DistSquared(Eyes, T->GetActorLocation());
		if (D < Best) { Best = D; Nearest = T; }
	}

	const FVector Facing = Fighter->GetFacing();
	// His head, or his middle when the bone is not there.
	const FVector Target = !Nearest ? FVector::ZeroVector
		: Nearest->GetMesh() ? Nearest->GetMesh()->GetSocketLocation(HeadBone)
		: Nearest->GetActorLocation() + FVector(0.f, 0.f, 60.f);
	const FVector Wanted = SaudIK::LookDirection(Eyes, Facing, Target, Nearest != nullptr);

	// The head follows at LookRate, and settles back on the facing when
	// there is nothing to follow.
	const float K = 1.f - FMath::Exp(-SaudIK::LookRate * DeltaSeconds);
	LookDirWorld = FMath::Lerp(LookDirWorld, Wanted, K).GetSafeNormal();
	if (LookDirWorld.IsNearlyZero()) LookDirWorld = Facing;

	const FTransform& C2W = Mesh->GetComponentTransform();
	Frame.Facing = C2W.InverseTransformVectorNoScale(Facing).GetSafeNormal();
	Frame.LookDir = C2W.InverseTransformVectorNoScale(LookDirWorld).GetSafeNormal();
	Frame.LookAlpha = SaudIK::Settle(Frame.LookAlpha, bWants && Nearest ? 1.f : 0.f, SaudIK::LookRate, DeltaSeconds);
}
