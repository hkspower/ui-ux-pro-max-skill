#include "Combat/SaudMotionComponent.h"
#include "Combat/FighterBase.h"
#include "Combat/SaudMotionAnimInstance.h"

#include "Animation/AnimSequence.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"

USaudMotionComponent::USaudMotionComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	// After the fighter has moved its state on this frame, so the clip is
	// this frame's and not last frame's.
	PrimaryComponentTick.TickGroup = TG_PostPhysics;
}

void USaudMotionComponent::BeginPlay()
{
	Super::BeginPlay();
	AFighterBase* Fighter = Cast<AFighterBase>(GetOwner());
	USkeletalMeshComponent* Mesh = Fighter ? Fighter->GetMesh() : nullptr;
	if (!bDriveMesh || !Mesh)
	{
		return;
	}
	// Our instance, unless a Blueprint set an Animation Blueprint: that is
	// its author's, and the clip goes to it the single-node way below.
	if (!Mesh->GetAnimClass())
	{
		Mesh->SetAnimInstanceClass(USaudMotionAnimInstance::StaticClass());
	}
	// Posed once now, so his first drawn frame is his guard and not the bind
	// pose: the update pulls PlayPicked.
	if (Driver())
	{
		Mesh->TickAnimation(0.f, false);
		Mesh->RefreshBoneTransforms();
	}
}

USaudMotionAnimInstance* USaudMotionComponent::Driver() const
{
	const AFighterBase* Fighter = Cast<AFighterBase>(GetOwner());
	const USkeletalMeshComponent* Mesh = Fighter ? Fighter->GetMesh() : nullptr;
	return Mesh ? Cast<USaudMotionAnimInstance>(Mesh->GetAnimInstance()) : nullptr;
}

void USaudMotionComponent::TickComponent(float DeltaTime, ELevelTick TickType,
                                         FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	// Our anim instance pulls the pick itself; a Blueprint's is handed it here.
	if (!Driver())
	{
		PlayPicked(DeltaTime);
	}
}

void USaudMotionComponent::PlayPicked(float DeltaSeconds)
{
	AFighterBase* Fighter = Cast<AFighterBase>(GetOwner());
	USkeletalMeshComponent* Mesh = Fighter ? Fighter->GetMesh() : nullptr;
	if (!bDriveMesh || !Mesh || !Mesh->GetSkeletalMeshAsset())
	{
		return;
	}
	USaudMotionAnimInstance* Inst = Driver();
	// A new anim instance, a new set of clips, or our instance left with
	// nothing playing (re-initialised on a re-register): everything is sent again.
	if (Inst != ShownOn.Get() || Fighter->MotionSet != PlayingSet || (Inst && !Inst->GetPlaying()))
	{
		ShownOn = Inst;
		PlayingSet = Fighter->MotionSet;
		PlayingName = NAME_None;
		bShown = false;
	}

	SaudFeel::FMotionInput In;
	In.State = static_cast<int>(Fighter->State);
	In.bBlocking = Fighter->bBlocking;
	In.bLastHitHeavy = Fighter->bLastHitHeavy;
	In.LastBlow = SaudFeel::BlowOf(TCHAR_TO_ANSI(*Fighter->LastHitAttack.ToString()));
	In.bDying = Fighter->GetHealth() <= 0.f;
	In.Victory = Fighter->VictoryRemaining;
	In.GettingUp = Fighter->GetUpRemaining;
	const FVector Vel = Fighter->GetVelocity();
	const FVector Flat(Vel.X, Vel.Y, 0.f);
	In.Speed = Flat.Size();
	// The way the body is drawn facing, so a walk or a dash is picked against
	// the body the player sees while it comes round after a snapped facing.
	const FVector Shown = Inst ? Inst->GetShownFacing() : FVector::ZeroVector;
	In.Facing = Shown.IsNearlyZero() ? Fighter->GetFacing() : Shown;
	In.Heading = Flat.IsNearlyZero() ? In.Facing : Flat.GetSafeNormal();
	// Free or fighting is the fighter's own test, held (AFighterBase::
	// IsMovingFree, SaudSteer::FreeHeld), the same for everyone: free, he
	// turns to where he goes and walks and runs as a man does; fighting, he
	// faces his man and strafes. Saud's set alone has the motion-capture
	// gaits for going straight ahead; anyone else plays his Run_Fwd / Walk_Fwd.
	const bool bSaudSet = Fighter->MotionSet.IsNone() || Fighter->MotionSet == FName(TEXT("Saud"));
	In.bFree = Fighter->IsMovingFree();
	In.bGaits = bSaudSet;
	In.RunSpeed = Fighter->GetRunSpeed();
	In.Current = bShown ? ShownClip : SaudFeel::EClip::Guard;
	// A turn the steer started (a new serial with a turn on) plays its clip to
	// the end on our own clock (SaudFeel::FTurnHold), unless an attack, a hit,
	// a fall or a dash takes over (below).
	const bool bTurnStarted = TurnHold.Step(Fighter->GetLocoTurn(), Fighter->GetLocoTurnSerial(), DeltaSeconds);
	In.Turn = TurnHold.Turn;

	const SaudFeel::EClip Clip = SaudFeel::Pick(In);
	const SaudFeel::EKind Kind = SaudFeel::KindOf(Clip);
	if (Kind == SaudFeel::EKind::Strike || Kind == SaudFeel::EKind::Reel || Kind == SaudFeel::EKind::Fall
		|| Kind == SaudFeel::EKind::Dash)
	{
		TurnHold.Stop();
	}
	const FString Name = Clip == SaudFeel::EClip::Attack
		? Fighter->GetCurrentAttackRow().ToString()
		: FString(ANSI_TO_TCHAR(SaudFeel::ClipSuffix(Clip)));
	if (Name.IsEmpty() || Name == TEXT("None"))
	{
		return;
	}

	const FName Key(*Name);
	// a new turn is a new start, as a second jab is: Turn_L90 after Turn_L90
	// plays again from its first frame
	const bool bSerialMoved = Fighter->MotionSerial != PlayingSerial || (bTurnStarted && SaudFeel::IsTurnClip(Clip));
	if (Key == PlayingName && !bSerialMoved)
	{
		return;
	}
	if (Inst && bShown && SaudFeel::KeepsClip(ShownClip, Clip, bSerialMoved))
	{
		return;     // one dash, one clip (SaudFeel::KeepsClip)
	}

	UAnimSequence* Seq = Find(Fighter->MotionSet, Name);
	// a turn clip of the set's own carries the turn; one it stands in for
	// (his guard) does not, and the hips' lag turns him as before
	const bool bOwnTurn = Seq && SaudFeel::IsTurnClip(Clip);
	// a set built before what was picked: a reaction by blow plays the old
	// hit or Down; a diagonal its neighbour nearer the heading, then the
	// other; a run clip its walk; a turn his guard (SaudFeel::FallbackChain).
	// Each looked for in the set's own way (Find): an Island set never borrows.
	if (!Seq && Clip != SaudFeel::EClip::Attack)
	{
		const SaudFeel::FClipChain Chain = SaudFeel::FallbackChain(Clip, SaudSteer::ErrorDeg(In.Facing, In.Heading));
		for (int32 I = 1; I < Chain.Num && !Seq; ++I)
		{
			Seq = Find(Fighter->MotionSet, FString(ANSI_TO_TCHAR(SaudFeel::ClipSuffix(Chain.Clip[I]))));
		}
	}
	// a second jab, hit, dash or win from its first frame, even while the
	// first still fades; a loop never restarts
	const bool bRestart = SaudFeel::Restarts(Clip, bSerialMoved);
	PlayingName = Key;
	PlayingSerial = Fighter->MotionSerial;
	if (!Seq)
	{
		return;
	}
	if (Inst)
	{
		// Ours: the clip over a crossfade, and the IK over it. The first clip
		// a man shows comes in whole.
		// (a pivot hands over into his run at his set's own share of its cycle)
		const FString SetName = Fighter->MotionSet.IsNone() ? FString(TEXT("Saud")) : Fighter->MotionSet.ToString();
		const SaudFeel::FCut Cut = bShown ? SaudFeel::CutBetween(ShownClip, Clip, bRestart, TCHAR_TO_ANSI(*SetName)) : SaudFeel::FCut();
		Inst->Play(Seq, SaudFeel::Loops(Clip), bRestart, Cut.Seconds, Cut.bMatchPhase, bOwnTurn, Cut.ShareShift, Cut.StartShare);
		ShownClip = Clip;
		bShown = true;
	}
	else
	{
		// A Blueprint's Animation Blueprint is on the mesh: single-node
		// playback takes it over for this clip, without the IK.
		Mesh->PlayAnimation(Seq, SaudFeel::Loops(Clip));
	}
}

UAnimSequence* USaudMotionComponent::Find(FName MotionSet, const FString& Clip)
{
	const FString Set = MotionSet.IsNone() ? TEXT("Saud") : MotionSet.ToString();
	// Saud's clips are in Saud/, the street men's in Street/, the monkey
	// island's creatures' in Island/, every other set that has its own is a
	// boss's.
	const bool bCreature = Set == TEXT("Monkey") || Set == TEXT("Gorilla");
	const FString Folder = (Set == TEXT("Saud") || Set == TEXT("Street")) ? Set
		: bCreature ? FString(TEXT("Island")) : FString(TEXT("Bosses"));

	const FString Own = FString::Printf(TEXT("/Game/Animation/%s/A_%s_%s.A_%s_%s"),
	                                    *Folder, *Set, *Clip, *Set, *Clip);
	if (UAnimSequence* Seq = LoadOnce(Own))
	{
		return Seq;
	}
	if (Set == TEXT("Saud"))
	{
		return nullptr;
	}
	// A creature borrows nothing: the men's clips are on another skeleton,
	// and a clip it lacks falls back within its own set (SaudFeel::Fallback).
	if (bCreature)
	{
		return nullptr;
	}
	// Anyone else borrows the street men's: Saud's clips on the boxer's
	// guard, because since 2026-09-25 Saud alone stands as a mixed martial
	// artist. Saud's own are the last resort, for a project whose Street
	// clips have not been imported.
	if (Set != TEXT("Street"))
	{
		if (UAnimSequence* Seq = LoadOnce(FString::Printf(
			TEXT("/Game/Animation/Street/A_Street_%s.A_Street_%s"), *Clip, *Clip)))
		{
			return Seq;
		}
	}
	return LoadOnce(FString::Printf(TEXT("/Game/Animation/Saud/A_Saud_%s.A_Saud_%s"), *Clip, *Clip));
}

UAnimSequence* USaudMotionComponent::LoadOnce(const FString& Path)
{
	const FName Key(*Path);
	if (const TObjectPtr<UAnimSequence>* Hit = Loaded.Find(Key))
	{
		return Hit->Get();
	}
	UAnimSequence* Seq = LoadObject<UAnimSequence>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet);
	Loaded.Add(Key, Seq);
	return Seq;
}
