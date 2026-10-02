#include "Combat/SaudMotionComponent.h"
#include "Combat/FighterBase.h"
#include "Combat/SaudMotionAnimInstance.h"

#include "Animation/AnimSequence.h"
#include "Components/SkeletalMeshComponent.h"

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
		PlayPicked();
	}
}

void USaudMotionComponent::PlayPicked()
{
	AFighterBase* Fighter = Cast<AFighterBase>(GetOwner());
	USkeletalMeshComponent* Mesh = Fighter ? Fighter->GetMesh() : nullptr;
	if (!bDriveMesh || !Mesh || !Mesh->GetSkeletalMeshAsset())
	{
		return;
	}
	USaudMotionAnimInstance* Inst = Driver();
	// A new anim instance, or a new set of clips: everything is sent again.
	if (Inst != ShownOn.Get() || Fighter->MotionSet != PlayingSet)
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

	const SaudFeel::EClip Clip = SaudFeel::Pick(In);
	const FString Name = Clip == SaudFeel::EClip::Attack
		? Fighter->GetCurrentAttackRow().ToString()
		: FString(ANSI_TO_TCHAR(SaudFeel::ClipSuffix(Clip)));
	if (Name.IsEmpty() || Name == TEXT("None"))
	{
		return;
	}

	const FName Key(*Name);
	const bool bSerialMoved = Fighter->MotionSerial != PlayingSerial;
	if (Key == PlayingName && !bSerialMoved)
	{
		return;
	}

	UAnimSequence* Seq = Find(Fighter->MotionSet, Name);
	if (!Seq && SaudFeel::Fallback(Clip) != Clip)
	{
		// a set built before the reactions by blow: the old hit, or Down
		Seq = Find(Fighter->MotionSet, FString(ANSI_TO_TCHAR(SaudFeel::ClipSuffix(SaudFeel::Fallback(Clip)))));
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
		const SaudFeel::FCut Cut = bShown ? SaudFeel::CutBetween(ShownClip, Clip, bRestart) : SaudFeel::FCut();
		Inst->Play(Seq, SaudFeel::Loops(Clip), bRestart, Cut.Seconds, Cut.bMatchPhase);
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
	// Saud's clips are in Saud/, the street men's in Street/, every other
	// set that has its own is a boss's.
	const FString Folder = (Set == TEXT("Saud") || Set == TEXT("Street")) ? Set : FString(TEXT("Bosses"));

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
