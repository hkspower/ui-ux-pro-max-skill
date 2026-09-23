#include "Combat/SaudMotionComponent.h"
#include "Combat/FighterBase.h"

#include "Animation/AnimSequence.h"
#include "Components/SkeletalMeshComponent.h"

USaudMotionComponent::USaudMotionComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	// After the fighter has moved its state on this frame, so the clip is
	// this frame's and not last frame's.
	PrimaryComponentTick.TickGroup = TG_PostPhysics;
}

void USaudMotionComponent::TickComponent(float DeltaTime, ELevelTick TickType,
                                         FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	AFighterBase* Fighter = Cast<AFighterBase>(GetOwner());
	USkeletalMeshComponent* Mesh = Fighter ? Fighter->GetMesh() : nullptr;
	if (!bDriveMesh || !Mesh || !Mesh->GetSkeletalMeshAsset())
	{
		return;
	}

	SaudFeel::FMotionInput In;
	In.State = static_cast<int>(Fighter->State);
	In.bBlocking = Fighter->bBlocking;
	In.bLastHitHeavy = Fighter->bLastHitHeavy;
	In.GettingUp = Fighter->GetUpRemaining;
	const FVector Vel = Fighter->GetVelocity();
	const FVector Flat(Vel.X, Vel.Y, 0.f);
	In.Speed = Flat.Size();
	In.Facing = Fighter->GetFacing();
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
	if (Key == PlayingName && Fighter->MotionSerial == PlayingSerial)
	{
		return;
	}

	UAnimSequence* Seq = Find(Fighter->MotionSet, Name);
	PlayingName = Key;
	PlayingSerial = Fighter->MotionSerial;
	if (Seq)
	{
		// Single-node: no Animation Blueprint to author, and none to break.
		Mesh->PlayAnimation(Seq, SaudFeel::Loops(Clip));
	}
}

UAnimSequence* USaudMotionComponent::Find(FName MotionSet, const FString& Clip)
{
	const FString Set = MotionSet.IsNone() ? TEXT("Saud") : MotionSet.ToString();
	// Saud's clips are in Saud/, every other set that has its own is a boss's.
	const FString Folder = Set == TEXT("Saud") ? TEXT("Saud") : TEXT("Bosses");

	const FString Own = FString::Printf(TEXT("/Game/Animation/%s/A_%s_%s.A_%s_%s"),
	                                    *Folder, *Set, *Clip, *Set, *Clip);
	if (UAnimSequence* Seq = LoadOnce(Own))
	{
		return Seq;
	}
	return Set == TEXT("Saud") ? nullptr
		: LoadOnce(FString::Printf(TEXT("/Game/Animation/Saud/A_Saud_%s.A_Saud_%s"), *Clip, *Clip));
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
