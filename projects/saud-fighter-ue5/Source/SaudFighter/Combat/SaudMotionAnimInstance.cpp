#include "Combat/SaudMotionAnimInstance.h"
#include "Combat/FighterBase.h"
#include "Combat/SaudArena.h"
#include "Combat/SaudFeel.h"
#include "Combat/SaudMotionComponent.h"

#include "Animation/AnimSequence.h"
#include "AnimationRuntime.h"
#include "BonePose.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Misc/App.h"
#include "Misc/ScopeExit.h"

namespace
{
	// The mannequin's names, the 62-bone strip every man exports.
	const FName PelvisBone(TEXT("pelvis"));
	const FName HeadBone(TEXT("head"));
	const FName Spine02Bone(TEXT("spine_02"));
	const FName Spine03Bone(TEXT("spine_03"));
	const FName ChainBone[SaudIK::ChainBones] = { FName(TEXT("spine_01")), FName(TEXT("spine_02")), FName(TEXT("spine_03")),
	                                              FName(TEXT("neck_01")), FName(TEXT("head")) };
	const FName ThighBone[2]   = { FName(TEXT("thigh_l")),    FName(TEXT("thigh_r")) };
	const FName CalfBone[2]    = { FName(TEXT("calf_l")),     FName(TEXT("calf_r")) };
	const FName FootBone[2]    = { FName(TEXT("foot_l")),     FName(TEXT("foot_r")) };
	const FName BallBone[2]    = { FName(TEXT("ball_l")),     FName(TEXT("ball_r")) };
	const FName UpperBone[2]   = { FName(TEXT("upperarm_l")), FName(TEXT("upperarm_r")) };
	const FName LowerBone[2]   = { FName(TEXT("lowerarm_l")), FName(TEXT("lowerarm_r")) };
	const FName HandBone[2]    = { FName(TEXT("hand_l")),     FName(TEXT("hand_r")) };
	const FName HandEndBone[2] = { FName(TEXT("hand_end_l")), FName(TEXT("hand_end_r")) };

	/** A gap longer than this between two evaluations is frames the proxy
	    missed (a mesh not rendered for about a second stops refreshing its
	    pose), not one slow frame: a hitch of a few tenths keeps the holds. */
	constexpr double MissedSeconds = 0.5;

	/** How far above and below the character's floor a foot is looked for. */
	constexpr float TraceUp = 60.f;
	constexpr float TraceDown = 70.f;
	/** A blow's push (LaunchCharacter, on every hit, block and parry) puts him
	    in Falling with no lift, and the capsule drops its ~2 cm floor gap in
	    0.064 s: a tenth of a second of that, sinking slower than AirSinkMax,
	    is still standing. Walking off a ledge sinks faster at once. */
	constexpr float AirGrace = 0.10f;
	constexpr float AirSinkMax = 50.f;

	const FName& MarkBoneOf(SaudIK::EMarkBone B)
	{
		return B == SaudIK::EMarkBone::Head ? HeadBone : B == SaudIK::EMarkBone::Spine02 ? Spine02Bone : Spine03Bone;
	}

	/** A man's size against Saud's: his reference pose's head over Saud's, times the mesh's own scale. */
	float ScaleOf(const USkeletalMeshComponent* M)
	{
		if (!M || !M->GetSkeletalMeshAsset()) return 1.f;
		const FReferenceSkeleton& Ref = M->GetSkeletalMeshAsset()->GetRefSkeleton();
		const int32 H = Ref.FindBoneIndex(HeadBone);
		if (H == INDEX_NONE) return 1.f;
		const float Height = static_cast<float>(FAnimationRuntime::GetComponentSpaceTransformRefPose(Ref, H).GetLocation().Z);
		return SaudIK::BodyScale(Height) * static_cast<float>(M->GetComponentScale().Z);
	}

	/** A fighter's motion set by name ("Saud" for none): an Island creature
	    throws with his own limbs (SaudIK::StrikeOf(Row, Set)). */
	FString SetOf(const AFighterBase* F)
	{
		return !F || F->MotionSet.IsNone() ? FString(TEXT("Saud")) : F->MotionSet.ToString();
	}

	/** An attack row as a number for SaudIK::FStrikeTrack: -1 for none. */
	int32 RowIdOf(FName Row)
	{
		return Row.IsNone() ? -1 : static_cast<int32>(GetTypeHash(Row) & 0x7fffffff);
	}
}

/* ================================================================= proxy */

FCompactPoseBoneIndex FSaudMotionProxy::Bone(const FBoneContainer& Bones, const FName& Name) const
{
	const int32 Mesh = Bones.GetPoseBoneIndexForBoneName(Name);
	return Mesh == INDEX_NONE ? FCompactPoseBoneIndex(INDEX_NONE) : Bones.MakeCompactPoseIndex(FMeshPoseBoneIndex(Mesh));
}

void FSaudMotionProxy::Extract(const FSaudIKLayer& Layer, FPoseContext& Into) const
{
	FAnimationPoseData Data(Into);
	Layer.Sequence->GetAnimationPose(Data, FAnimExtractContext(static_cast<double>(Layer.Time), false, FDeltaTimeRecord(), Layer.bLoop));
}

bool FSaudMotionProxy::Evaluate(FPoseContext& Output)
{
	// ---- the clips, oldest first, each newer one over the mix under it by
	// its share of the two (SaudIK::FoldShare): every clip at its own weight
	const FSaudIKLayer* Live[SaudIK::MaxLayers];
	int32 N = 0;
	for (int32 I = 0; I < Frame.NumLayers && I < SaudIK::MaxLayers; ++I)
	{
		if (Frame.Layers[I].Sequence) Live[N++] = &Frame.Layers[I];
	}
	if (N == 0)
	{
		Output.ResetToRefPose();
		Back.bValid = false;
		return true;
	}
	if (N == 1)
	{
		Extract(*Live[0], Output);
	}
	else
	{
		FPoseContext MixA(Output), MixB(Output), Clip(Output);
		FPoseContext* Under = &MixA;
		FPoseContext* Spare = &MixB;
		Extract(*Live[N - 1], *Under);
		float UnderWeight = Live[N - 1]->Weight;
		for (int32 I = N - 2; I >= 0; --I)
		{
			Extract(*Live[I], Clip);
			FPoseContext& Into = I == 0 ? Output : *Spare;
			const FAnimationPoseData ClipData(Clip);
			const FAnimationPoseData UnderData(*Under);
			FAnimationPoseData IntoData(Into);
			FAnimationRuntime::BlendTwoPosesTogether(ClipData, UnderData, SaudIK::FoldShare(UnderWeight, Live[I]->Weight), IntoData);
			UnderWeight += Live[I]->Weight;
			Swap(Under, Spare);
		}
	}

	// ---- the hips' lag: the whole body turned back about the capsule's axis
	// by what the actor snapped and the body has not yet come round
	// (SaudIK::TurnStep). On the root, in local space, before anything reads
	// component space, so every bone follows.
	if (FMath::Abs(Frame.HipsYaw) > 0.01f)
	{
		const FQuat Lag(Frame.Up, FMath::DegreesToRadians(Frame.HipsYaw));
		FTransform& Root = Output.Pose[FCompactPoseBoneIndex(0)];
		Root.SetRotation((Lag * Root.GetRotation()).GetNormalized());
		Root.SetTranslation(Frame.Pivot + Lag.RotateVector(Root.GetTranslation() - Frame.Pivot));
	}

	const FBoneContainer& Bones = Output.Pose.GetBoneContainer();
	FCSPose<FCompactPose> Raw;   // the clips as they are, turned with the hips: read, never written
	Raw.InitPose(Output.Pose);
	FCSPose<FCompactPose> CS;    // what the solves write
	CS.InitPose(Output.Pose);
	// a second Evaluate in one frame steps nothing; a gap of more than
	// MissedSeconds is frames not evaluated (off screen: the pose is not
	// refreshed while unrendered, though the update runs), and what the feet
	// held from before it is stale -- they start afresh, as after a teleport
	const double Gap = LastClock < 0.0 ? 0.0 : Frame.Clock - LastClock;
	const float Dt = LastClock < 0.0 ? 0.f : FMath::Clamp(static_cast<float>(Gap), 0.f, 0.25f);
	LastClock = Frame.Clock;
	const bool bMissed = Gap > MissedSeconds;

	// ---- the feet's plan, every frame, from the clips' own legs
	SaudIK::FFeetIn In;
	const FTransform& C2W = Frame.ComponentToWorld;
	In.Mesh.Origin = C2W.GetLocation();
	In.Mesh.X = C2W.GetUnitAxis(EAxis::X);
	In.Mesh.Y = C2W.GetUnitAxis(EAxis::Y);
	In.Mesh.Z = C2W.GetUnitAxis(EAxis::Z);
	In.Mesh.Scale = static_cast<float>(C2W.GetScale3D().X);    // uniform
	In.bWanted = Frame.bFeetWanted;
	In.bHold = Frame.bHoldFeet;
	In.bSettle = Frame.bSettleFeet;
	In.bTeleported = Frame.bTeleported || bMissed;
	In.bBlending = N > 1;
	In.bStopping = Frame.bStopping;
	In.ReleaseSeconds = Frame.ReleaseSeconds;
	In.StepSeconds = Frame.StepSeconds;
	In.Velocity = Frame.Velocity;
	In.ClipSerial = Frame.ClipSerial;
	In.ClipTime = Frame.ClipTime;
	In.Down[0] = Frame.ClipDown[0];
	In.Down[1] = Frame.ClipDown[1];
	FLegBones Legs[2];
	bool bLegs = true;
	for (int32 S = 0; S < 2; ++S)
	{
		Legs[S].Thigh = Bone(Bones, ThighBone[S]);
		Legs[S].Calf = Bone(Bones, CalfBone[S]);
		Legs[S].Foot = Bone(Bones, FootBone[S]);
		Legs[S].Ball = Bone(Bones, BallBone[S]);
		bLegs = bLegs && Legs[S].Thigh.IsValid() && Legs[S].Calf.IsValid() && Legs[S].Foot.IsValid() && Legs[S].Ball.IsValid();
	}
	if (bLegs)
	{
		for (int32 S = 0; S < 2; ++S)
		{
			const FTransform FootT = Raw.GetComponentSpaceTransform(Legs[S].Foot);
			const FTransform BallT = Raw.GetComponentSpaceTransform(Legs[S].Ball);
			SaudIK::FFootIn& F = In.Foot[S];
			F.Hip = Raw.GetComponentSpaceTransform(Legs[S].Thigh).GetLocation();
			const FVector Knee = Raw.GetComponentSpaceTransform(Legs[S].Calf).GetLocation();
			F.Ankle = FootT.GetLocation();
			F.Ball = BallT.GetLocation();
			F.LegLength = static_cast<float>(FVector::Dist(F.Hip, Knee) + FVector::Dist(Knee, F.Ankle));
			F.ToeDir = BallT.GetRotation().RotateVector(Frame.ToeLocal[S]);
			F.FootFwd = FootT.GetRotation().RotateVector(Frame.FootFwdLocal[S]);
			F.FootUp = FootT.GetRotation().RotateVector(Frame.FootUpLocal[S]);
			F.AnkleRest = Frame.AnkleRest[S];
			F.BallRest = Frame.BallRest[S];
			F.bStrike = Frame.StrikeLeg == S;
			for (int32 K = 0; K < 2; ++K)
			{
				SaudIK::FGroundPoint& G = K ? F.BallGround : F.HeelGround;
				const SaudIK::FGroundPoint& W = Frame.Ground[S][K];
				G.bHit = W.bHit;
				G.Point = SaudIK::ToMesh(In.Mesh, W.Point);
				G.Normal = SaudIK::DirToMesh(In.Mesh, W.Normal);
			}
		}
	}
	const SaudIK::FFeetPlan Plan = bLegs ? SaudIK::StepFeet(Feet, In, Dt) : SaudIK::FFeetPlan();
	const bool bFeet = bLegs && Plan.Alpha > 0.f;

	// ---- 1. the pelvis: the feet's drop and the weight's carry. No bone under
	// it has been read in component space yet.
	const FCompactPoseBoneIndex Pelvis = Bone(Bones, PelvisBone);
	if (bFeet && Pelvis.IsValid())
	{
		FTransform T = CS.GetComponentSpaceTransform(Pelvis);
		T.AddToTranslation(Plan.Pelvis);
		// the lean into a curve, a start or a stop (SaudIK::FLean): the pelvis
		// turned about its own joint, so the chain over it leans with it and
		// the legs, solved below from where the hips are, keep the feet
		if (Frame.LeanDegrees > 0.01f)
		{
			const FQuat Lean(Frame.LeanAxis, FMath::DegreesToRadians(Frame.LeanDegrees * Plan.Alpha));
			T.SetRotation((Lean * T.GetRotation()).GetNormalized());
		}
		CS.SetComponentSpaceTransform(Pelvis, T);
	}

	// ---- 2. the trunk, the neck and the head, root first: each read after
	// the one under it is set, so it turns from where that one put it
	FVector NeckPivot = FVector::ZeroVector;
	bool bNeck = false;
	if (Frame.bChain)
	{
		const FCompactPoseBoneIndex Chain[SaudIK::ChainBones] = { Bone(Bones, ChainBone[0]), Bone(Bones, ChainBone[1]),
			Bone(Bones, ChainBone[2]), Bone(Bones, ChainBone[3]), Bone(Bones, ChainBone[4]) };
		bool bAll = true;
		for (int32 I = 0; I < SaudIK::ChainBones; ++I) bAll = bAll && Chain[I].IsValid();
		if (bAll)
		{
			for (int32 I = 0; I < SaudIK::ChainBones; ++I)
			{
				FTransform T = CS.GetComponentSpaceTransform(Chain[I]);
				if (I == 3) { NeckPivot = T.GetLocation(); bNeck = true; }   // neck_01, where the chest put it
				const FQuat Yaw(Frame.Up, FMath::DegreesToRadians(Frame.ChainYaw[I]));
				const FQuat Nod(Frame.ChainAxis[I], FMath::DegreesToRadians(Frame.ChainPitch[I]));
				T.SetRotation((Nod * Yaw * T.GetRotation()).GetNormalized());
				CS.SetComponentSpaceTransform(Chain[I], T);
			}
		}
	}

	// ---- 3. the legs, every one the feet have -- the strike's too, which
	// the strike below takes from here, so it leaves the ground with no jump
	if (bFeet)
	{
		for (int32 S = 0; S < 2; ++S)
		{
			const FVector Hip = CS.GetComponentSpaceTransform(Legs[S].Thigh).GetLocation();   // the leg's first read: after the pelvis
			const FVector Knee = CS.GetComponentSpaceTransform(Legs[S].Calf).GetLocation();
			const SaudIK::FFootPose P = SaudIK::FinishFoot(Feet.Hold[S], Plan.Foot[S], In.Foot[S], Hip, Dt);
			// the clip's foot (its yaw the body's), tilted to the ground, rolled onto the ball
			const FQuat FootQ = (FQuat(P.RollAxis, P.Roll) * FQuat::FindBetweenNormals(FVector::UpVector, P.Tilt)
			                    * Raw.GetComponentSpaceTransform(Legs[S].Foot).GetRotation()).GetNormalized();
			FLeg L; L.Root = Legs[S].Thigh; L.Mid = Legs[S].Calf; L.End = Legs[S].Foot;
			SolveLimb(CS, L, P.Ankle, Knee, 1.f, &FootQ, Plan.Alpha);
			FTransform BT = CS.GetComponentSpaceTransform(Legs[S].Ball);   // first read: follows the new foot
			const FVector ToeNow = BT.GetRotation().RotateVector(Frame.ToeLocal[S]);
			BT.SetRotation((FQuat::FindBetweenNormals(ToeNow.GetSafeNormal(), P.Toe.GetSafeNormal()) * BT.GetRotation()).GetNormalized());
			CS.SetComponentSpaceTransform(Legs[S].Ball, BT);
		}
	}

	// ---- 4. the arms and the striking leg: the guard carried with the face,
	// then a block, then the strike; each reads what the one before set
	const FVector Up = Frame.Up;
	if (bNeck)
	{
		const float Yaw = Frame.ChainYaw[3] + Frame.ChainYaw[4];   // the face's own turn beyond the chest
		for (int32 S = 0; S < 2; ++S)
		{
			if (Frame.GuardAlpha[S] <= 0.f || FMath::Abs(Yaw) < 0.01f) continue;
			FLeg Arm; Arm.Root = Bone(Bones, UpperBone[S]); Arm.Mid = Bone(Bones, LowerBone[S]); Arm.End = Bone(Bones, HandBone[S]);
			if (!Arm.Root.IsValid() || !Arm.Mid.IsValid() || !Arm.End.IsValid()) continue;
			const FVector Elbow = CS.GetComponentSpaceTransform(Arm.Mid).GetLocation();
			const FTransform HandT = CS.GetComponentSpaceTransform(Arm.End);
			const SaudIK::FCarry C = SaudIK::Carry(HandT.GetLocation(), NeckPivot, Up, Yaw);
			const FQuat EndQ = (FQuat(Up, FMath::DegreesToRadians(Yaw * C.Share * Frame.GuardAlpha[S])) * HandT.GetRotation()).GetNormalized();
			SolveLimb(CS, Arm, C.Fist, Elbow, Frame.GuardAlpha[S], &EndQ, Frame.GuardAlpha[S]);
		}
	}
	if (Frame.BlockAlpha > 0.f && Frame.BlockSide != INDEX_NONE)
	{
		const int32 S = Frame.BlockSide;
		FLeg Arm; Arm.Root = Bone(Bones, UpperBone[S]); Arm.Mid = Bone(Bones, LowerBone[S]); Arm.End = Bone(Bones, HandBone[S]);
		const FCompactPoseBoneIndex Other = Bone(Bones, HandBone[1 - S]);
		if (Arm.Root.IsValid() && Arm.Mid.IsValid() && Arm.End.IsValid() && Other.IsValid())
		{
			const FVector Sh = CS.GetComponentSpaceTransform(Arm.Root).GetLocation();
			const FVector El = CS.GetComponentSpaceTransform(Arm.Mid).GetLocation();
			const FVector Ha = CS.GetComponentSpaceTransform(Arm.End).GetLocation();
			const FVector OtherHand = CS.GetComponentSpaceTransform(Other).GetLocation();
			const SaudIK::FTwoBone To = SaudIK::Cover(Sh, El, Ha, Frame.BlockMeet, Frame.bBlockHigh, Frame.BlockAlpha, Up, OtherHand, Frame.BodyScale);
			Place(CS, Arm, Ha, To, /*bEndRigid*/ false);   // the Block's upright glove keeps its turn
		}
	}
	if (Frame.StrikeAlpha > 0.f && Frame.StrikeTip != SaudIK::ETip::None)
	{
		const int32 S = Frame.StrikeSide;
		const FLegBones& Leg = Legs[S];
		if (Frame.StrikeTip == SaudIK::ETip::Knee)
		{
			if (bLegs)
			{
				// all four read before any is set: a bone read after its parent is set comes back already turned
				const FCompactPoseBoneIndex Piece[4] = { Leg.Thigh, Leg.Calf, Leg.Foot, Leg.Ball };
				FTransform T[4] = { CS.GetComponentSpaceTransform(Piece[0]), CS.GetComponentSpaceTransform(Piece[1]),
				                    CS.GetComponentSpaceTransform(Piece[2]), CS.GetComponentSpaceTransform(Piece[3]) };
				const FVector Hip = T[0].GetLocation(), Knee = T[1].GetLocation();
				const FVector Aim = SaudIK::KneeAim(Hip, Knee, Frame.StrikeMark, Frame.StrikeLow, Frame.StrikeSkin);
				const float Gate = StrikeGate.Step(SaudIK::SwingGate(Hip, Knee, Aim, false), Dt);
				const FVector To = SaudIK::KneeSwing(Hip, Knee, Aim, Frame.StrikeAlpha * Gate);
				const FQuat Q = FQuat::FindBetweenNormals((Knee - Hip).GetSafeNormal(), (To - Hip).GetSafeNormal());
				for (int32 I = 0; I < 4; ++I)
				{
					T[I].SetRotation((Q * T[I].GetRotation()).GetNormalized());
					T[I].SetLocation(Hip + Q.RotateVector(T[I].GetLocation() - Hip));
					CS.SetComponentSpaceTransform(Piece[I], T[I]);
				}
			}
		}
		else
		{
			const bool bArm = Frame.StrikeTip == SaudIK::ETip::Knuckles;
			FLeg L;
			L.Root = bArm ? Bone(Bones, UpperBone[S]) : Leg.Thigh;
			L.Mid = bArm ? Bone(Bones, LowerBone[S]) : Leg.Calf;
			L.End = bArm ? Bone(Bones, HandBone[S]) : Leg.Foot;
			const FCompactPoseBoneIndex TipB = bArm ? Bone(Bones, HandEndBone[S]) : Leg.Ball;
			if (L.Root.IsValid() && L.Mid.IsValid() && L.End.IsValid() && TipB.IsValid() && Bones.GetParentBoneIndex(TipB) == L.End)
			{
				const FVector Root = CS.GetComponentSpaceTransform(L.Root).GetLocation();
				const FVector Mid = CS.GetComponentSpaceTransform(L.Mid).GetLocation();
				const FTransform EndBefore = CS.GetComponentSpaceTransform(L.End);
				// the tip from its LOCAL offset off the end, taken from Output.Pose: the
				// CS pose's own array holds a bone's component-space transform once it
				// has been read or set, and the feet (3) have done both to the ball.
				// The feet only turn the ball, so its offset from the foot is the clip's.
				const FVector Tip = EndBefore.TransformPosition(Output.Pose[TipB].GetTranslation());
				const FTransform TipBefore = bArm ? FTransform::Identity : CS.GetComponentSpaceTransform(TipB);
				const float Reach = static_cast<float>(FVector::Dist(Root, Mid) + FVector::Dist(Mid, Tip)) * SaudIK::MaxStretch;
				const FVector Mark = SaudIK::ReachableMark(Root, Reach, Frame.StrikeMark, Frame.StrikeLow, static_cast<float>(Tip.Z));
				const FVector Aim = SaudIK::MeetPoint(Mark, Root, Frame.StrikeSkin);
				const float Gate = StrikeGate.Step(SaudIK::SwingGate(Root, Tip, Aim, bArm), Dt);
				Place(CS, L, Tip, SaudIK::SolveStrike(Root, Mid, Tip, Aim, Frame.StrikeAlpha * Gate), /*bEndRigid*/ true);
				if (!bArm)
				{
					// the ball the feet set rides the foot the strike moved
					const FTransform EndAfter = CS.GetComponentSpaceTransform(L.End);
					CS.SetComponentSpaceTransform(TipB, TipBefore.GetRelativeTransform(EndBefore) * EndAfter);
				}
			}
		}
	}
	else
	{
		StrikeGate.Reset();
	}

	// ---- 5. where the feet were drawn, for next frame's traces, after every
	// solve and before the pose goes back to local space
	if (bLegs)
	{
		for (int32 S = 0; S < 2; ++S)
		{
			Back.Heel[S] = C2W.TransformPosition(CS.GetComponentSpaceTransform(Legs[S].Foot).GetLocation());
			Back.Ball[S] = C2W.TransformPosition(CS.GetComponentSpaceTransform(Legs[S].Ball).GetLocation());
			// and how fast each went, for next frame's traces where it will be
			if (In.bTeleported) { Back.HeelTrack[S] = SaudIK::FFootTrack(); Back.BallTrack[S] = SaudIK::FFootTrack(); }
			Back.HeelTrack[S].Push(Back.Heel[S], Dt);
			Back.BallTrack[S].Push(Back.Ball[S], Dt);
		}
	}
	Back.bValid = bLegs;
	Back.Stride = Feet.Stride;

	FCSPose<FCompactPose>::ConvertComponentPosesToLocalPoses(MoveTemp(CS), Output.Pose);
	return true;
}

void FSaudMotionProxy::SolveLimb(FCSPose<FCompactPose>& CS, const FLeg& L, const FVector& Target, const FVector& Pole,
                                 float Alpha, const FQuat* EndRotation, float Whole) const
{
	FTransform RootT = CS.GetComponentSpaceTransform(L.Root);
	FTransform MidT = CS.GetComponentSpaceTransform(L.Mid);
	FTransform EndT = CS.GetComponentSpaceTransform(L.End);
	const FVector Root = RootT.GetLocation(), Mid = MidT.GetLocation(), End = EndT.GetLocation();

	const FVector Wanted = FMath::Lerp(End, Target, FMath::Clamp(Alpha, 0.f, 1.f));
	const SaudIK::FTwoBone R = SaudIK::TwoBone(Root, Mid, End, Wanted, Pole, Whole);

	// Each segment turns by what its direction turned; positions come from
	// the solve, so the lengths are the clip's to the millimetre.
	const FQuat RootTurn = FQuat::FindBetweenNormals((Mid - Root).GetSafeNormal(), (R.Mid - Root).GetSafeNormal());
	RootT.SetRotation((RootTurn * RootT.GetRotation()).GetNormalized());
	CS.SetComponentSpaceTransform(L.Root, RootT);

	const FQuat MidTurn = FQuat::FindBetweenNormals((End - Mid).GetSafeNormal(), (R.End - R.Mid).GetSafeNormal());
	MidT.SetRotation((MidTurn * MidT.GetRotation()).GetNormalized());
	MidT.SetLocation(R.Mid);
	CS.SetComponentSpaceTransform(L.Mid, MidT);

	// The end keeps the clip's turn (a fist stays a fist), or takes the one
	// asked for: a foot tilted to the ground, a guard fist turned with the face.
	if (EndRotation)
	{
		EndT.SetRotation(*EndRotation);
	}
	EndT.SetLocation(R.End);
	CS.SetComponentSpaceTransform(L.End, EndT);
}

void FSaudMotionProxy::Place(FCSPose<FCompactPose>& CS, const FLeg& L, const FVector& Tip, const SaudIK::FTwoBone& To, bool bEndRigid) const
{
	// all three read before any is set
	FTransform RootT = CS.GetComponentSpaceTransform(L.Root);
	FTransform MidT = CS.GetComponentSpaceTransform(L.Mid);
	FTransform EndT = CS.GetComponentSpaceTransform(L.End);
	const FVector Root = RootT.GetLocation(), Mid = MidT.GetLocation(), End = EndT.GetLocation();

	RootT.SetRotation((FQuat::FindBetweenNormals((Mid - Root).GetSafeNormal(), (To.Mid - Root).GetSafeNormal()) * RootT.GetRotation()).GetNormalized());
	CS.SetComponentSpaceTransform(L.Root, RootT);

	// the lower segment and the end turn as one piece, from the middle joint to the tip
	const FQuat MidTurn = FQuat::FindBetweenNormals((Tip - Mid).GetSafeNormal(), (To.End - To.Mid).GetSafeNormal());
	MidT.SetRotation((MidTurn * MidT.GetRotation()).GetNormalized());
	MidT.SetLocation(To.Mid);
	CS.SetComponentSpaceTransform(L.Mid, MidT);

	if (bEndRigid)
	{
		EndT.SetRotation((MidTurn * EndT.GetRotation()).GetNormalized());
	}
	EndT.SetLocation(SaudIK::RigidEnd(Mid, End, Tip, To));
	CS.SetComponentSpaceTransform(L.End, EndT);
}

/* ============================================================== instance */

void USaudMotionAnimInstance::NativeInitializeAnimation()
{
	Super::NativeInitializeAnimation();
	Frame = FSaudIKFrame();
	Clips.Reset();
	ClipPlants.Reset();
	ClipTurns.Reset();
	Lean = SaudIK::FLean();
	ShuffleSet = NAME_None;
	ShuffleSeconds = 0.f;
	Fade = SaudIK::FCrossfade();
	Clock = 0.0;
	bMeasured = false;
	BodyScale = 1.f;
	AirTime = 0.f;
	StrikeTrack = SaudIK::FStrikeTrack();
	Strike = SaudIK::FStrike();
	StrikeVictim.Reset();
	StrikeGuarded = SaudIK::FRamp();
	BlockTrack = SaudIK::FBlockTrack();
	BlockFrom.Reset();
	BlockSideHeld = INDEX_NONE;
	GuardRamp[0] = GuardRamp[1] = SaudIK::FRamp();
	Turn = SaudIK::FTurn();
	bTurnKnown = false;
	LookTarget.Reset();
	bLookAtThreat = false;
}

void USaudMotionAnimInstance::Play(UAnimSequence* Sequence, bool bLoop, bool bRestart, float CutSeconds, bool bMatchPhase,
                                   bool bTurn, float ShareShift, float StartShare)
{
	if (!Sequence)
	{
		return;
	}
	int32 Id = Clips.IndexOfByKey(Sequence);
	if (Id == INDEX_NONE)
	{
		Id = Clips.Add(Sequence);
		// its measured feet, by the asset's name (A_Saud_Walk_Fwd): the two arrays stay in step
		ClipPlants.Add(SaudPlants::Find(TCHAR_TO_ANSI(*Sequence->GetName())));
		ClipTurns.Add(bTurn);
	}
	Fade.Play(Id, Sequence->GetPlayLength(), bLoop, bRestart, CutSeconds, bMatchPhase, ShareShift, StartShare);
}

const SaudPlants::FClip* USaudMotionAnimInstance::NewestPlants() const
{
	return Fade.Num > 0 && ClipPlants.IsValidIndex(Fade.Layers[0].Clip) ? ClipPlants[Fade.Layers[0].Clip] : nullptr;
}

bool USaudMotionAnimInstance::NewestTurns() const
{
	return Fade.Num > 0 && ClipTurns.IsValidIndex(Fade.Layers[0].Clip) && ClipTurns[Fade.Layers[0].Clip];
}

UAnimSequence* USaudMotionAnimInstance::GetPlaying() const
{
	return Fade.Num > 0 && Clips.IsValidIndex(Fade.Layers[0].Clip) ? Clips[Fade.Layers[0].Clip].Get() : nullptr;
}

FVector USaudMotionAnimInstance::GetShownFacing() const
{
	return bTurnKnown ? FRotator(0.f, LastYaw + Turn.Hips, 0.f).Vector() : FVector::ZeroVector;
}

void USaudMotionAnimInstance::NativeUpdateAnimation(float InDeltaSeconds)
{
	Super::NativeUpdateAnimation(InDeltaSeconds);

	// Into the proxy last, on every way out: its PreUpdate runs before this
	// function, so a copy there would hand it last frame's.
	FSaudMotionProxy& Proxy = GetProxyOnGameThread<FSaudMotionProxy>();
	ON_SCOPE_EXIT { Proxy.SetFrame(Frame); };
	const FSaudFeetBack Back = Proxy.GetBack();     // what last frame's evaluation drew

	// The clips' clock. DeltaSeconds is the world's, so a freeze holds it --
	// except under the title (SetRealTime), where the world is paused.
	const float DeltaSeconds = bRealTime
		? FMath::Clamp(static_cast<float>(FApp::GetDeltaTime()), 0.f, 0.1f)
		: InDeltaSeconds;
	AFighterBase* Fighter = Cast<AFighterBase>(TryGetPawnOwner());
	USkeletalMeshComponent* Mesh = GetSkelMeshComponent();

	// The clip this frame's state calls for, picked here so it is this
	// frame's: the motion component itself ticks after the mesh.
	if (Fighter && Fighter->Motion)
	{
		Fighter->Motion->PlayPicked(DeltaSeconds);
	}

	// A looping walk at the pace the man moves: by the clip's measured stride
	// (SaudPlants) from its first frame, or else by what the proxy's stride
	// meter has read of it (SaudIK::StrideRate). A turn or pivot clip is a
	// one-shot timed to the steer's hold (SaudSteer::TurnSeconds): always 1x.
	float Rate = 1.f;
	if (Fighter && Mesh && Fade.Num > 0 && Fade.Layers[0].bLoop && !NewestTurns())
	{
		const FVector V = Fighter->GetVelocity();
		const float Ground = static_cast<float>(FVector(V.X, V.Y, 0.f).Size());
		// his world stride: the clip's (measured at Saud's size) on his own
		// legs and the mesh's scale -- BodyScale, not the mesh's scale alone
		// (a boss half again Saud's size walked his clip half again too fast)
		const float Scale = FMath::Max(0.1f, BodyScale);
		if (const SaudPlants::FClip* P = NewestPlants())
		{
			Rate = SaudIK::StrideRateMeasured(Ground, P->Stride, Scale);
		}
		else if (Back.Stride.Clip == Fade.Serial)
		{
			Rate = SaudIK::StrideRate(Ground, Back.Stride, Scale);
		}
	}
	Fade.Advance(DeltaSeconds, Rate);
	Clock += DeltaSeconds;
	Frame.Clock = Clock;
	Frame.NumLayers = Fade.Num;
	for (int32 I = 0; I < SaudIK::MaxLayers; ++I)
	{
		const SaudIK::FLayer& L = Fade.Layers[I];
		FSaudIKLayer& Out = Frame.Layers[I];
		const bool bOn = I < Fade.Num && Clips.IsValidIndex(L.Clip);
		Out.Sequence = bOn ? Clips[L.Clip].Get() : nullptr;
		Out.Time = L.Time;
		Out.bLoop = L.bLoop;
		Out.Weight = bOn ? L.Weight : 0.f;
	}
	Frame.ClipSerial = Fade.Serial;
	Frame.ClipTime = Fade.Num > 0 ? Fade.Layers[0].Time : 0.f;
	SaudIK::MixDown(Fade, ClipPlants.GetData(), ClipPlants.Num(), Frame.ClipDown);

	// With no fighter or mesh nothing is solved: the proxy eases the feet out.
	Frame.bFeetWanted = false;
	Frame.bSettleFeet = false;
	Frame.bTeleported = false;
	Frame.StrikeTip = SaudIK::ETip::None;
	Frame.StrikeAlpha = 0.f;
	Frame.BlockSide = INDEX_NONE;
	Frame.BlockAlpha = 0.f;
	Frame.GuardAlpha[0] = Frame.GuardAlpha[1] = 0.f;
	Frame.HipsYaw = 0.f;
	Frame.bChain = false;
	Frame.LeanDegrees = 0.f;
	Frame.bStopping = false;
	if (!Fighter || !Mesh || !Mesh->GetSkeletalMeshAsset())
	{
		return;
	}
	if (!bMeasured)
	{
		Measure(Mesh);
	}
	Frame.ComponentToWorld = Mesh->GetComponentTransform();
	Frame.Up = Frame.ComponentToWorld.InverseTransformVectorNoScale(FVector::UpVector).GetSafeNormal();
	Frame.Pivot = Frame.ComponentToWorld.InverseTransformPosition(Fighter->GetActorLocation());
	// The proxy works in the mesh's own units: his size there is the
	// reference head's ratio alone, the component's scale taken back out
	// (BodyScale has it in, for the world's distances below).
	Frame.BodyScale = BodyScale / FMath::Max(1e-4f, static_cast<float>(Mesh->GetComponentScale().Z));

	// Put somewhere new -- a door, a respawn -- rather than walked there.
	const bool bTeleported = bTurnKnown && SaudIK::Teleported(LastLocation, Fighter->GetActorLocation());

	UpdateFeet(Fighter, Back, bTeleported, DeltaSeconds);
	UpdateStrike(Fighter, DeltaSeconds);       // before the turn: the look's first choice is the strike's man
	UpdateBlock(Fighter, DeltaSeconds);
	UpdateTurn(Fighter, bTeleported, DeltaSeconds);
	UpdateGuard(Fighter, DeltaSeconds);
}

void USaudMotionAnimInstance::Measure(const USkeletalMeshComponent* Mesh)
{
	// From the reference pose, once, each side on its own: the bone axes are
	// mirrored between sides. The mesh's origin is on its floor, so a height
	// here is from the sole.
	const FReferenceSkeleton& Ref = Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();
	for (int32 S = 0; S < 2; ++S)
	{
		const int32 Foot = Ref.FindBoneIndex(FootBone[S]);
		const int32 Ball = Ref.FindBoneIndex(BallBone[S]);
		if (Foot == INDEX_NONE || Ball == INDEX_NONE)
		{
			continue;
		}
		const FTransform F = FAnimationRuntime::GetComponentSpaceTransformRefPose(Ref, Foot);
		const FTransform B = FAnimationRuntime::GetComponentSpaceTransformRefPose(Ref, Ball);
		// at rest the toes lie flat, along the foot: forward is the ankle-to-ball line on the floor
		FVector Fwd = B.GetLocation() - F.GetLocation();
		Fwd.Z = 0.f;
		Fwd = Fwd.GetSafeNormal();
		Frame.ToeLocal[S] = B.GetRotation().UnrotateVector(Fwd);
		Frame.FootFwdLocal[S] = F.GetRotation().UnrotateVector(Fwd);
		Frame.FootUpLocal[S] = F.GetRotation().UnrotateVector(FVector::UpVector);
		Frame.AnkleRest[S] = static_cast<float>(F.GetLocation().Z);
		Frame.BallRest[S] = static_cast<float>(B.GetLocation().Z);
	}
	BodyScale = ScaleOf(Mesh);
	bMeasured = true;
}

void USaudMotionAnimInstance::UpdateFeet(AFighterBase* Fighter, const FSaudFeetBack& Back, bool bTeleported, float DeltaSeconds)
{
	USkeletalMeshComponent* Mesh = GetSkelMeshComponent();
	UWorld* World = GetWorld();
	const UCapsuleComponent* Capsule = Fighter->GetCapsuleComponent();
	if (!Mesh || !World || !Capsule) return;

	// No ground under a man in the air, on the floor, mid-dash or climbing;
	// a blow's push is still the ground (AirGrace).
	const UCharacterMovementComponent* Move = Fighter->GetCharacterMovement();
	const bool bFalling = Move && Move->IsFalling();
	AirTime = bFalling ? AirTime + DeltaSeconds : 0.f;
	const FVector Vel = Fighter->GetVelocity();
	const bool bGround = Move && (Move->IsMovingOnGround() || (bFalling && AirTime <= AirGrace && Vel.Z > -AirSinkMax));
	const EFighterState St = Fighter->State;
	Frame.bFeetWanted = bFeetOnGround && bGround
		&& St != EFighterState::Down && St != EFighterState::Dead && St != EFighterState::Dash;
	Frame.bTeleported = bTeleported;
	Frame.Velocity = FVector(Vel.X, Vel.Y, 0.f);
	const bool bAttacking = St == EFighterState::Attack;
	const bool bStanding = Frame.Velocity.Size() < SaudFeel::WalkThreshold;
	Frame.bSettleFeet = bStanding && !bAttacking;
	const SaudPlants::FClip* Newest = NewestPlants();
	Frame.bHoldFeet = Newest ? SaudIK::HoldsFeetMeasured(bAttacking, bStanding, Newest->Stride,
	                                                     St == EFighterState::Block, Frame.Velocity.Size(), BodyScale)
	                         : SaudIK::HoldsFeet(bAttacking, bStanding, Back.Stride, Fade.Serial);
	// a walk crossfading to his guard: the standing foot holds until the last swing lands
	Frame.bStopping = SaudIK::Stopping(Fade, ClipPlants.GetData(), ClipPlants.Num());
	// a foot handed back inside the newest clip's own quickest swing; a shuffle
	// inside his set's (SaudIK::ReleaseFor, ShuffleFor; the set's looked up once)
	Frame.ReleaseSeconds = SaudIK::ReleaseFor(Newest);
	if (Fighter->MotionSet != ShuffleSet || ShuffleSeconds <= 0.f)
	{
		ShuffleSet = Fighter->MotionSet;
		ShuffleSeconds = SaudIK::ShuffleFor(TCHAR_TO_ANSI(*SetOf(Fighter)));
	}
	Frame.StepSeconds = ShuffleSeconds;

	// The lean into a curve, a start or a stop, in the world's directions,
	// handed over in the mesh's: on with the feet (SaudIK::StepLean)
	{
		const float RunSpeed = FMath::Max(1.f, Fighter->GetRunSpeed());
		SaudIK::StepLean(Lean, Frame.Velocity, SaudSteer::WalkShare * RunSpeed, RunSpeed, Frame.bFeetWanted, DeltaSeconds, bTeleported);
		FVector Axis; float Degrees = 0.f;
		SaudIK::LeanAxisAngle(Lean, Axis, Degrees);
		Frame.LeanAxis = Mesh->GetComponentTransform().InverseTransformVectorNoScale(Axis).GetSafeNormal();
		Frame.LeanDegrees = Frame.LeanAxis.IsNearlyZero() ? 0.f : Degrees;
	}

	// The leg an attack is thrown with is the strike's from its first frame: never held.
	Frame.StrikeLeg = -1;
	if (bAttacking)
	{
		char Side = 0;
		if (SaudIK::StrikingLimb(TCHAR_TO_ANSI(*Fighter->GetCurrentAttackRow().ToString()), TCHAR_TO_ANSI(*SetOf(Fighter)), Side) == SaudIK::ELimb::Leg)
		{
			Frame.StrikeLeg = Side == 'r' ? 1 : 0;
		}
	}

	// Two traces a foot, under where the proxy drew its heel and its ball,
	// against the world's ground and nothing else: never a pawn's capsule.
	const float FloorZ = static_cast<float>(Fighter->GetActorLocation().Z) - Capsule->GetScaledCapsuleHalfHeight();
	FCollisionQueryParams Params(SCENE_QUERY_STAT(SaudFootIK), false, Fighter);
	FCollisionObjectQueryParams GroundTypes;
	GroundTypes.AddObjectTypesToQuery(ECC_WorldStatic);
	GroundTypes.AddObjectTypesToQuery(ECC_WorldDynamic);
	for (int32 S = 0; S < 2; ++S)
	{
		for (int32 K = 0; K < 2; ++K)
		{
			SaudIK::FGroundPoint& G = Frame.Ground[S][K];
			G = SaudIK::FGroundPoint();
			if (!Frame.bFeetWanted) continue;
			// where the foot will be this frame: where it was drawn plus its own
			// velocity (SaudIK::FFootTrack) -- a swing at a run is a frame ahead
			const FVector At = Back.bValid ? (K ? Back.BallTrack[S].Ahead(DeltaSeconds) : Back.HeelTrack[S].Ahead(DeltaSeconds))
			                               : Mesh->GetSocketLocation(K ? BallBone[S] : FootBone[S]);   // the first frame only
			FHitResult Hit;
			G.bHit = World->LineTraceSingleByObjectType(Hit, FVector(At.X, At.Y, FloorZ + TraceUp),
			                                            FVector(At.X, At.Y, FloorZ - TraceDown), GroundTypes, Params)
			      && !Hit.bStartPenetrating;
			if (G.bHit)
			{
				G.Point = FVector(Hit.ImpactPoint);
				G.Normal = FVector(Hit.ImpactNormal);
			}
		}
	}
}

void USaudMotionAnimInstance::UpdateStrike(AFighterBase* Fighter, float DeltaSeconds)
{
	USkeletalMeshComponent* Mesh = GetSkelMeshComponent();
	const FAttackDef* Attack = Fighter->State == EFighterState::Attack ? Fighter->GetCurrentAttack() : nullptr;
	const FName Row = Attack ? Fighter->GetCurrentAttackRow() : NAME_None;
	const SaudIK::FStrike Kind = Attack ? SaudIK::StrikeOf(TCHAR_TO_ANSI(*Row.ToString()), TCHAR_TO_ANSI(*SetOf(Fighter))) : SaudIK::FStrike();
	const bool bLive = bHandsOnContact && Mesh && Kind.Limb != SaudIK::ELimb::None;
	const int32 RowId = RowIdOf(Row);
	const float Elapsed = Fighter->GetAttackElapsed();
	if (StrikeTrack.NewSwing(bLive, RowId, Elapsed))
	{
		// a new swing: nobody held, nothing spent, the last swing's man forgotten
		StrikeTrack = SaudIK::FStrikeTrack();
		Strike = Kind;
		StrikeVictim.Reset();
		StrikeGuarded = SaudIK::FRamp();
		StrikeMarkC = FVector::ZeroVector;     // no swing inherits another's mark
		StrikeLowC = FVector::ZeroVector;
	}

	// The man: found from the lead-in and kept for the swing. The sweep's own
	// pick first -- the first man in its order inside its own box -- then the
	// nearest in the box BoxSlack longer, for a man stepping in.
	AFighterBase* Victim = nullptr;
	bool bLost = false;
	if (bLive)
	{
		const FVector Origin = Fighter->GetActorLocation(), Facing = Fighter->GetFacing();
		const float Reach = Attack->Reach + Fighter->GetAttackReachBonus(*Attack);
		if (StrikeTrack.bHeld)
		{
			AFighterBase* Held = StrikeVictim.Get();
			if (Held && Held->CanBeStruck() && SaudIK::InBlowBox(Origin, Facing, Held->GetActorLocation(), Reach, Attack->DepthTolerance))
			{
				Victim = Held;
			}
			else
			{
				bLost = true;     // gone, struck down, or out of reach: let go; nobody else this swing
			}
		}
		else if (!StrikeTrack.bSpent
		         && SaudIK::ContactAlpha(Elapsed, Attack->Startup, Attack->Active, SaudIK::ContactLeadIn, Attack->bMultiHit) > 0.f)
		{
			TArray<AFighterBase*> Targets;
			Fighter->GatherOpponents(Targets);
			for (AFighterBase* T : Targets)
			{
				if (IsValid(T) && T->CanBeStruck() && SaudArena::InHitbox(Origin, Facing, T->GetActorLocation(), Reach, Attack->DepthTolerance))
				{
					Victim = T;
					break;
				}
			}
			if (!Victim)
			{
				double Best = TNumericLimits<double>::Max();
				for (AFighterBase* T : Targets)
				{
					if (!IsValid(T) || !T->CanBeStruck() || !SaudIK::InBlowBox(Origin, Facing, T->GetActorLocation(), Reach, Attack->DepthTolerance)) continue;
					const double D = FVector::DistSquared2D(Origin, T->GetActorLocation());
					if (D < Best) { Best = D; Victim = T; }
				}
			}
			if (Victim)
			{
				StrikeVictim = Victim;
				StrikeScale = ScaleOf(Victim->GetMesh());
			}
		}
	}
	const bool bWasHeld = StrikeTrack.bHeld;
	StrikeTrack.Step(bLive, RowId, Elapsed, Attack ? Attack->Startup : 0.f, Attack ? Attack->Active : 0.f,
	                 Attack && Attack->bMultiHit, Victim != nullptr, bLost, DeltaSeconds);

	// The mark, read off the man until the blow lands or is taken away; then
	// held where it was in this mesh's space, so the fist follows the lunge
	// and not a man thrown clear.
	// read while fresh, and on the frame a man is first taken however late:
	// a man taken after the blow landed is drawn to his own mark, not the last one
	if ((StrikeTrack.FreshMark() || (Victim && !bWasHeld)) && Victim && Victim->GetMesh() && Mesh)
	{
		const FVector Him = Victim->GetActorLocation(), Me = Fighter->GetActorLocation(), HisFacing = Victim->GetFacing();
		USkeletalMeshComponent* Body = Victim->GetMesh();
		const FVector MarkW = SaudIK::MarkPoint(Body->GetSocketLocation(MarkBoneOf(Strike.Bone)), Him, Me, Strike.Mark, StrikeScale, HisFacing);
		const FVector LowW = SaudIK::MarkPoint(Body->GetSocketLocation(PelvisBone), Him, Me, FVector(SaudIK::BeltForward, 0.f, 0.f), StrikeScale, HisFacing);
		// a guarded blow stops in front of his guard, on the line from the root of the striking limb
		const int32 S = Strike.Side == 'r' ? 1 : 0;
		const FVector RootW = Mesh->GetSocketLocation(Strike.Limb == SaudIK::ELimb::Arm ? UpperBone[S] : ThighBone[S]);
		const FVector StopW = SaudIK::MeetPoint(MarkW, RootW, (SaudIK::BlockStandOff + SaudIK::BlockFaceGap) * StrikeScale);
		const bool bGuarded = Victim->bBlocking && Victim->State != EFighterState::Attack && SaudArena::Covers(HisFacing, Me - Him);   // ReceiveHit's own bGuarding
		StrikeGuarded.Step(bGuarded, DeltaSeconds, SaudIK::ContactLeadIn, SaudIK::ContactLeadIn);
		const float G = StrikeGuarded.Value();
		const FTransform& C2W = Mesh->GetComponentTransform();
		StrikeMarkC = C2W.InverseTransformPosition(FMath::Lerp(MarkW, StopW, G));
		StrikeLowC = C2W.InverseTransformPosition(FMath::Lerp(LowW, StopW, G));   // a guarded blow never slides down him
	}

	const float Alpha = StrikeTrack.Alpha();
	Frame.StrikeTip = Alpha > 0.f ? Strike.Tip : SaudIK::ETip::None;
	Frame.StrikeSide = Strike.Side == 'r' ? 1 : 0;
	Frame.StrikeMark = StrikeMarkC;
	Frame.StrikeLow = StrikeLowC;
	Frame.StrikeSkin = SaudIK::SkinOf(Strike, Frame.BodyScale);   // mesh units, as the proxy's bones
	Frame.StrikeAlpha = Alpha;
}

void USaudMotionAnimInstance::UpdateBlock(AFighterBase* Fighter, float DeltaSeconds)
{
	USkeletalMeshComponent* Mesh = GetSkelMeshComponent();
	const EFighterState St = Fighter->State;
	const bool bGuarding = bHandsOnContact && Mesh && (Fighter->bBlocking || St == EFighterState::Block)
		&& (St == EFighterState::Idle || St == EFighterState::Walk || St == EFighterState::Block)
		&& Fighter->GetUpRemaining <= 0.f;
	const FVector Me = Fighter->GetActorLocation(), MyFacing = Fighter->GetFacing();

	// A blow coming at me: a swing with a striking limb, its box (BoxSlack
	// longer) holding me, from in front of me.
	auto Incoming = [&](AFighterBase* A) -> const FAttackDef*
	{
		if (!IsValid(A) || A->State != EFighterState::Attack) return nullptr;
		const FAttackDef* Att = A->GetCurrentAttack();
		char Side = 0;
		if (!Att || SaudIK::StrikingLimb(TCHAR_TO_ANSI(*A->GetCurrentAttackRow().ToString()), TCHAR_TO_ANSI(*SetOf(A)), Side) == SaudIK::ELimb::None) return nullptr;
		if (!SaudIK::InBlowBox(A->GetActorLocation(), A->GetFacing(), Me, Att->Reach + A->GetAttackReachBonus(*Att), Att->DepthTolerance)) return nullptr;
		return SaudArena::Covers(MyFacing, A->GetActorLocation() - Me) ? Att : nullptr;
	};

	AFighterBase* From = nullptr;
	const FAttackDef* Att = nullptr;
	if (bGuarding)
	{
		// the blow held, while its swing lasts
		AFighterBase* Held = BlockFrom.Get();
		if (Held && Held->State == EFighterState::Attack && Held->GetCurrentAttackRow() == BlockRow && Held->GetAttackElapsed() >= BlockClock)
		{
			Att = Incoming(Held);
			From = Att ? Held : nullptr;
		}
		// another as soon as nothing of the last shows: the one furthest into his swing
		if (!From && BlockTrack.Free())
		{
			TArray<AFighterBase*> Them;
			Fighter->GatherOpponents(Them);
			float Best = -1.f;
			for (AFighterBase* A : Them)
			{
				if (const FAttackDef* AA = Incoming(A))
				{
					const float S = SaudIK::ContactAlpha(A->GetAttackElapsed(), AA->Startup, AA->Active, AA->Startup, true);
					if (S > Best) { Best = S; From = A; Att = AA; }
				}
			}
			if (From)
			{
				BlockFrom = From;
				BlockRow = From->GetCurrentAttackRow();
				BlockTrack.Take(Best);
			}
		}
	}
	if (From && Att && From->GetMesh() && Mesh)
	{
		BlockClock = From->GetAttackElapsed();
		const SaudIK::FStrike K = SaudIK::StrikeOf(TCHAR_TO_ANSI(*BlockRow.ToString()), TCHAR_TO_ANSI(*SetOf(From)));
		// the striker's own clock, his whole wind-up: the guard arrives as the blow does
		const float S = SaudIK::ContactAlpha(BlockClock, Att->Startup, Att->Active, Att->Startup, true);
		const FVector Mark = SaudIK::MarkPoint(Mesh->GetSocketLocation(MarkBoneOf(K.Bone)), Me, From->GetActorLocation(), K.Mark, BodyScale, MyFacing);
		const int32 HisSide = K.Side == 'r' ? 1 : 0;
		const FVector HisRoot = From->GetMesh()->GetSocketLocation(K.Limb == SaudIK::ELimb::Arm ? UpperBone[HisSide] : ThighBone[HisSide]);
		BlockMeetW = SaudIK::MeetPoint(Mark, HisRoot, SaudIK::BlockStandOff * BodyScale);
		BlockSideHeld = SaudIK::CoverSide(K.Side) == 'r' ? 1 : 0;
		bBlockHighHeld = K.Bone == SaudIK::EMarkBone::Head;     // the glove for a head blow, the elbow for a body blow
		BlockTrack.Step(true, S, DeltaSeconds);
	}
	else
	{
		BlockFrom.Reset();
		BlockTrack.Step(false, 0.f, DeltaSeconds);
	}
	const float Alpha = BlockTrack.Alpha();
	Frame.BlockSide = Alpha > 0.f ? BlockSideHeld : INDEX_NONE;
	Frame.bBlockHigh = bBlockHighHeld;
	Frame.BlockMeet = Mesh ? Mesh->GetComponentTransform().InverseTransformPosition(BlockMeetW) : FVector::ZeroVector;
	Frame.BlockAlpha = Alpha;
}

void USaudMotionAnimInstance::UpdateTurn(AFighterBase* Fighter, bool bTeleported, float DeltaSeconds)
{
	USkeletalMeshComponent* Mesh = GetSkelMeshComponent();
	if (!Mesh) return;

	// How far the actor turned since the last frame: FaceTowards snaps it,
	// and the body comes round after (SaudIK::TurnStep).
	const float Yaw = static_cast<float>(Fighter->GetActorRotation().Yaw);
	const FVector Location = Fighter->GetActorLocation();
	const float Turned = bTurnKnown ? SaudIK::WrapDegrees(Yaw - LastYaw) : 0.f;
	LastYaw = Yaw;
	LastLocation = Location;
	bTurnKnown = true;

	const EFighterState St = Fighter->State;
	const bool bLying = St == EFighterState::Down || St == EFighterState::Dead;
	const bool bMayLook = bHeadLooks && St != EFighterState::Hit && !bLying;
	const FVector Forward = Fighter->GetActorForwardVector();    // the facing the mesh rides, not GetFacing

	// Who he looks at: the man his own strike is drawn to, then a man
	// swinging at him, then the nearest in front; the man already looked at
	// keeps the look until another is clearly better.
	// the strike's man only while the swing is live: after it he is one of the rest
	AFighterBase* Victim = StrikeTrack.bHeld && StrikeTrack.Row >= 0 ? StrikeVictim.Get() : nullptr;
	TArray<AFighterBase*> Opponents;
	Fighter->GatherOpponents(Opponents);
	TArray<SaudIK::FLookCandidate, TInlineAllocator<8>> Candidates;
	TArray<AFighterBase*, TInlineAllocator<8>> Who;
	for (AFighterBase* T : Opponents)
	{
		if (!IsValid(T) || !T->IsAlive()) continue;
		SaudIK::FLookCandidate C;
		C.Centre = T->GetActorLocation();
		const FAttackDef* A = T->State == EFighterState::Attack ? T->GetCurrentAttack() : nullptr;
		const bool bSwinging = A && SaudIK::Threatens(T->GetAttackElapsed(), A->Startup, A->Active);
		C.bThreat = bSwinging && SaudIK::InBlowBox(T->GetActorLocation(), T->GetFacing(), Location,
		                                           A->Reach + T->GetAttackReachBonus(*A), A->DepthTolerance);
		C.bVictim = Victim == T;
		C.bCurrent = LookTarget.Get() == T;
		C.bWasThreat = C.bCurrent && bLookAtThreat && bSwinging;
		Candidates.Add(C);
		Who.Add(T);
	}
	const int32 Pick = SaudIK::ChooseLook(Candidates.GetData(), Candidates.Num(), Location, Forward);
	AFighterBase* Target = Pick >= 0 ? Who[Pick] : nullptr;
	LookTarget = Target;
	bLookAtThreat = Pick >= 0 && (Candidates[Pick].bThreat || Candidates[Pick].bWasThreat);

	// The yaw from the line between the two men's middles; the pitch from
	// his eyes to the other's -- the head joint, which is the eye line on
	// this skeleton. No eye bones: the face is the eyes' aim.
	float RawYaw = 0.f, Pitch = 0.f;
	if (Target)
	{
		USkeletalMeshComponent* Theirs = Target->GetMesh();
		const FVector Eyes = Mesh->GetSocketLocation(HeadBone);
		const FVector His = Theirs && Theirs->DoesSocketExist(HeadBone)
			? Theirs->GetSocketLocation(HeadBone) : Target->GetActorLocation() + FVector(0.f, 0.f, 60.f);
		SaudIK::LookAngles(Location, Eyes, Forward, Target->GetActorLocation(), His, RawYaw, Pitch);
	}
	// a turn or pivot clip carries the turn itself: the lag goes out as it
	// comes in and is held at none under it, so the body is not turned twice
	const float TurnClip = NewestTurns() ? Fade.Layers[0].Weight : -1.f;
	SaudIK::TurnStep(Turn, Turned, RawYaw, Pitch, bMayLook && Target != nullptr, bLying,
	                 St == EFighterState::Attack, bTeleported, DeltaSeconds, TurnClip);

	// Handed over in the mesh's own space.
	const FTransform& C2W = Mesh->GetComponentTransform();
	const SaudIK::FChainTurn Chain = SaudIK::ShareTurn(Turn);
	Frame.HipsYaw = Chain.Hips;
	FVector Axes[SaudIK::ChainBones];
	SaudIK::PitchAxes(Chain, C2W.InverseTransformVectorNoScale(Forward).GetSafeNormal(), Frame.Up, Axes);
	for (int32 I = 0; I < SaudIK::ChainBones; ++I)
	{
		Frame.ChainYaw[I] = Chain.Yaw[I];
		Frame.ChainPitch[I] = Chain.Pitch[I];
		Frame.ChainAxis[I] = Axes[I];
	}
	Frame.bChain = Turn.Weight.Value() > 0.f;
}

void USaudMotionAnimInstance::UpdateGuard(AFighterBase* Fighter, float DeltaSeconds)
{
	// A fist neither throwing nor blocking keeps the place its clip gives it
	// by the face while the face turns: both standing (Idle, Walk, Block) and
	// in a leg strike, the other fist in a punch, neither reeling, down,
	// dashing, getting up or winning. Each comes and goes over 0.08 s.
	const EFighterState St = Fighter->State;
	const bool bStanding = (St == EFighterState::Idle || St == EFighterState::Walk || St == EFighterState::Block)
		&& Fighter->GetUpRemaining <= 0.f && Fighter->VictoryRemaining <= 0.f;
	const bool bSwinging = St == EFighterState::Attack && Fighter->GetCurrentAttack();
	char Side = 0;
	const SaudIK::ELimb Limb = bSwinging
		? SaudIK::StrikingLimb(TCHAR_TO_ANSI(*Fighter->GetCurrentAttackRow().ToString()), TCHAR_TO_ANSI(*SetOf(Fighter)), Side) : SaudIK::ELimb::None;
	for (int32 S = 0; S < 2; ++S)
	{
		const bool bThrowing = Limb == SaudIK::ELimb::Arm && Side == (S ? 'r' : 'l');
		GuardRamp[S].Step(bHandsOnContact && (bStanding || (bSwinging && !bThrowing)), DeltaSeconds,
		                  SaudIK::ContactLeadOut, SaudIK::ContactLeadOut);
		Frame.GuardAlpha[S] = GuardRamp[S].Value();
	}
}
