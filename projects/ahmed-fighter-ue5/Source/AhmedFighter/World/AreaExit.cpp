#include "World/AreaExit.h"
#include "Game/AhmedAudioSubsystem.h"

#include "Combat/AhmedCharacter.h"
#include "Components/BoxComponent.h"
#include "Game/AhmedGameInstance.h"
#include "Kismet/GameplayStatics.h"
#include "World/WaveDirector.h"

AAreaExit::AAreaExit()
{
	PrimaryActorTick.bCanEverTick = false;

	Trigger = CreateDefaultSubobject<UBoxComponent>(TEXT("Trigger"));
	SetRootComponent(Trigger);
	// Tall and deep enough that there is no way past it, thin along X so the
	// player is only "in" it for a step.
	Trigger->SetBoxExtent(FVector(60.f, 700.f, 300.f));
	Trigger->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Trigger->SetCollisionResponseToAllChannels(ECR_Ignore);
	Trigger->SetCollisionResponseToChannel(ECC_Pawn, ECR_Overlap);
}

void AAreaExit::BeginPlay()
{
	Super::BeginPlay();
	Trigger->OnComponentBeginOverlap.AddDynamic(this, &AAreaExit::HandleOverlap);
}

bool AAreaExit::IsOpenFor(const UAhmedGameInstance* GI) const
{
	if (!GI)
	{
		return RequiredAbility == EAbility::None && AfterClearedStage.IsNone();
	}
	if (RequiredAbility != EAbility::None && !GI->HasAbility(RequiredAbility))
	{
		return false;
	}
	if (!AfterClearedStage.IsNone() && !GI->GetProgress().ClearedStages.Contains(AfterClearedStage))
	{
		return false;
	}
	return true;
}

FVector AAreaExit::GetLandingLocation() const
{
	// Inward is +X from a west edge and -X from an east one; the door off the
	// souq stands in the strip's middle, so a step back the way it faces.
	const float Inward = (Side == EAreaSide::East) ? -1.f : 1.f;
	FVector Loc = GetActorLocation();
	Loc.X += Inward * 240.f;
	return Loc;
}

void AAreaExit::HandleOverlap(UPrimitiveComponent*, AActor* Other, UPrimitiveComponent*, int32, bool, const FHitResult&)
{
	AAhmedCharacter* Player = Cast<AAhmedCharacter>(Other);
	if (!Player || bTravelling)
	{
		return;
	}

	UWorld* World = GetWorld();
	UAhmedGameInstance* GI = World ? World->GetGameInstance<UAhmedGameInstance>() : nullptr;

	// Waves have to be down before an area lets you out of its far side. The
	// way you came in is always open -- retreating is allowed.
	if (Side != EAreaSide::West)
	{
		if (const AWaveDirector* Director = AWaveDirector::Get(World))
		{
			if (Director->IsArenaLocked())
			{
				return;
			}
		}
	}

	if (!IsOpenFor(GI))
	{
		// Push back a step so the player is not standing inside the trigger
		// when it refuses, then say what it wants.
		const float Dir = (Side == EAreaSide::West) ? 1.f : -1.f;
		FVector Loc = Player->GetActorLocation();
		Loc.X += Dir * 140.f;
		Player->SetActorLocation(Loc);

		const double Now = World ? World->GetTimeSeconds() : 0.0;
		if (Now >= RefuseCooldown)
		{
			RefuseCooldown = static_cast<float>(Now) + 1.2f;
			if (UAhmedAudioSubsystem* Audio = UAhmedAudioSubsystem::Get(this)) { Audio->Play(TEXT("Exit_Sealed"), this); }
			const bool bHasAbility = RequiredAbility == EAbility::None
				|| (GI && GI->HasAbility(RequiredAbility));
			// "Needs VAULT" if the key is missing; "no way through yet" if the
			// key is there but the far side has not been earned.
			OnExitRefused.Broadcast(bHasAbility ? EAbility::None : RequiredAbility,
				bHasAbility ? AfterClearedStage : NAME_None);
		}
		return;
	}

	if (DestinationExit)
	{
		// Same level: a step through the doorway. The far exit is told it is
		// travelling too, so landing beside it cannot send him straight back.
		if (UAhmedAudioSubsystem* Audio = UAhmedAudioSubsystem::Get(this)) { Audio->PlayUI(TEXT("Exit_Travel")); }
		if (GI)
		{
			FAhmedProgress& P = GI->GetMutableProgress();
			P.CurrentStage = DestinationStage;
			P.VisitedStages.AddUnique(DestinationStage);
			GI->SaveProgress();
		}
		DestinationExit->bTravelling = true;
		Player->SetActorLocation(DestinationExit->GetLandingLocation());
		Player->SetActorRotation(FRotator(0.f, DestinationExit->Side == EAreaSide::East ? 180.f : 0.f, 0.f));
		// The district he has stepped into owns him now: its strip is the
		// clamp, not the one he came from.
		if (AWaveDirector* There = AWaveDirector::Get(World))
		{
			There->ApplyArenaBounds();
		}
		if (World)
		{
			// Released next frame, once the overlap from the landing has been
			// and gone. Cannot be released here: the landing overlap fires
			// inside SetActorLocation, before this returns.
			TWeakObjectPtr<AAreaExit> Far = DestinationExit;
			World->GetTimerManager().SetTimerForNextTick([Far]()
			{
				if (Far.IsValid()) { Far->bTravelling = false; }
			});
		}
		return;
	}

	if (DestinationLevel.IsNone())
	{
		UE_LOG(LogTemp, Warning, TEXT("[Ahmed] AreaExit '%s' has no DestinationLevel"), *GetName());
		return;
	}

	bTravelling = true;
	if (UAhmedAudioSubsystem* Audio = UAhmedAudioSubsystem::Get(this)) { Audio->PlayUI(TEXT("Exit_Travel")); }

	// The far side reads these on load: where to stand, and what to carry
	// across. Travel is a step through a doorway, not a fresh run.
	FString Options = FString::Printf(TEXT("?ArriveAt=%s"),
		ArriveAt == EAreaSide::East ? TEXT("East") : ArriveAt == EAreaSide::Door ? TEXT("Door") : TEXT("West"));
	Options += FString::Printf(TEXT("?Health=%d?Stamina=%d?Rage=%d"),
		FMath::RoundToInt(Player->GetHealth()),
		FMath::RoundToInt(Player->GetStamina()),
		FMath::RoundToInt(Player->Rage));

	if (GI)
	{
		GI->GetMutableProgress().CurrentStage = DestinationStage;
		GI->SaveProgress();
	}

	UGameplayStatics::OpenLevel(this, DestinationLevel, true, Options);
}
