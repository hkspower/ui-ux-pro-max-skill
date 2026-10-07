#include "World/AreaExit.h"
#include "World/AbilityGate.h"      // SaudPortal: the portal's slot and timings
#include "Components/StaticMeshComponent.h"
#include "Combat/SaudArena.h"
#include "Game/SaudAudioSubsystem.h"

#include "Combat/SaudCharacter.h"
#include "Components/BoxComponent.h"
#include "EngineUtils.h"
#include "Game/SaudGameInstance.h"
#include "Kismet/GameplayStatics.h"
#include "World/WaveDirector.h"

AAreaExit::AAreaExit()
{
	// Only the arena door ticks (its portal); BeginPlay turns it on there.
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = false;

	Trigger = CreateDefaultSubobject<UBoxComponent>(TEXT("Trigger"));
	SetRootComponent(Trigger);
	// Tall and deep enough that there is no way past it, thin along X so the
	// player is only "in" it for a step.
	Trigger->SetBoxExtent(FVector(60.f, 700.f, 300.f));
	Trigger->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Trigger->SetCollisionResponseToAllChannels(ECR_Ignore);
	Trigger->SetCollisionResponseToChannel(ECC_Pawn, ECR_Overlap);

	// The portal stands on the floor the trigger stands on, its face across
	// the way through: the mesh's face is its local Y, the way through the
	// trigger's X, so a quarter turn.
	Portal = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Portal"));
	Portal->SetupAttachment(Trigger);
	Portal->SetRelativeLocation(FVector(0.f, 0.f, -300.f));
	Portal->SetRelativeRotation(FRotator(0.f, 90.f, 0.f));
	Portal->SetUsingAbsoluteScale(true);
	Portal->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Portal->SetCastShadow(false);
	Portal->SetCanEverAffectNavigation(false);
	Portal->SetVisibility(false);
}

void AAreaExit::BeginPlay()
{
	Super::BeginPlay();
	Trigger->OnComponentBeginOverlap.AddDynamic(this, &AAreaExit::HandleOverlap);

	// The trigger is thin along its own X and wide along Y, which was right
	// for a door at the end of a strip. A door on a round district's rim
	// stands at any bearing, so it is turned to face the middle: thin along
	// the way through it, wide along the rim. Unturned, a door due north of
	// the middle lay 14 m deep into the district along the road.
	const FVector In = GetInward();
	SetActorRotation(FRotator(0.f, FMath::RadiansToDegrees(FMath::Atan2(In.Y, In.X)), 0.f));

	// Only the arena door is a portal; it stands on the trigger's own floor.
	Portal->SetRelativeLocation(FVector(0.f, 0.f, -Trigger->GetUnscaledBoxExtent().Z));
	if (bArenaDoor && Portal->GetStaticMesh())
	{
		const USaudGameInstance* GI = GetWorld() ? GetWorld()->GetGameInstance<USaudGameInstance>() : nullptr;
		PortalState = IsOpenFor(GI) ? SaudPortal::Openable : SaudPortal::Sealed;
		WritePortal();
		SetActorTickEnabled(true);
	}
	else
	{
		Portal->SetVisibility(false);
	}
}

void AAreaExit::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	TickPortal(DeltaSeconds);
}

void AAreaExit::TickPortal(float DeltaSeconds)
{
	if (bPortalFlare)
	{
		// Used: flare and collapse over OpenSeconds, then whole again, sealed,
		// waking back to what the way is (a door is not used up).
		PortalState = FMath::Max(PortalState, SaudPortal::Openable) + DeltaSeconds / SaudPortal::OpenSeconds;
		if (PortalState >= SaudPortal::Gone)
		{
			bPortalFlare = false;
			PortalState = SaudPortal::Sealed;
		}
	}
	else
	{
		const UWorld* World = GetWorld();
		const USaudGameInstance* GI = World ? World->GetGameInstance<USaudGameInstance>() : nullptr;
		const float Target = IsOpenFor(GI) ? SaudPortal::Openable : SaudPortal::Sealed;
		const float Step = DeltaSeconds / SaudPortal::WakeSeconds;
		PortalState = PortalState > Target ? FMath::Max(Target, PortalState - Step)
			: FMath::Min(Target, PortalState + Step);
	}
	WritePortal();
}

void AAreaExit::WritePortal()
{
	if (PortalState == PortalWritten)
	{
		return;
	}
	PortalWritten = PortalState;
	Portal->SetCustomPrimitiveDataFloat(SaudPortal::DataIndex, PortalState);
	Portal->SetVisibility(PortalState < SaudPortal::Gone);
}

FVector AAreaExit::GetInward() const
{
	// The middle of the district this door is in: the director whose round
	// place holds it. A map with none (a door alone in a test level) keeps
	// the strip's rule: in along +X from a west edge, -X from an east one.
	const AWaveDirector* Own = nullptr;
	float Best = TNumericLimits<float>::Max();
	if (const UWorld* World = GetWorld())
	{
		for (TActorIterator<AWaveDirector> It(World); It; ++It)
		{
			if (!It->Contains(GetActorLocation()))
			{
				continue;
			}
			const float D = FVector::DistSquared2D(It->GetActorLocation(), GetActorLocation());
			if (D < Best)
			{
				Best = D;
				Own = *It;
			}
		}
	}
	if (!Own)
	{
		return FVector(Side == EAreaSide::East ? -1.f : 1.f, 0.f, 0.f);
	}
	return SaudArena::DoorInward(GetActorLocation(), Own->GetActorLocation());
}

bool AAreaExit::IsOpenFor(const USaudGameInstance* GI) const
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
	// A step toward the middle of this door's own district. It was 240 cm
	// along world X, which is inward only for a door due east or west of the
	// middle: in the open world four door steps of eighteen stood the player
	// outside the rim, facing out.
	const FVector In = GetInward();
	const FVector Loc = GetActorLocation();
	return FVector(Loc.X + In.X * 240.f, Loc.Y + In.Y * 240.f, Loc.Z);
}

void AAreaExit::HandleOverlap(UPrimitiveComponent*, AActor* Other, UPrimitiveComponent*, int32, bool, const FHitResult&)
{
	ASaudCharacter* Player = Cast<ASaudCharacter>(Other);
	if (!Player || bTravelling)
	{
		return;
	}

	UWorld* World = GetWorld();
	USaudGameInstance* GI = World ? World->GetGameInstance<USaudGameInstance>() : nullptr;

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
		const FVector In = GetInward();
		const FVector Loc = Player->GetActorLocation();
		Player->SetActorLocation(FVector(Loc.X + In.X * 140.f, Loc.Y + In.Y * 140.f, Loc.Z));

		const double Now = World ? World->GetTimeSeconds() : 0.0;
		if (Now >= RefuseCooldown)
		{
			RefuseCooldown = static_cast<float>(Now) + 1.2f;
			if (USaudAudioSubsystem* Audio = USaudAudioSubsystem::Get(this)) { Audio->Play(TEXT("Exit_Sealed"), this); }
			const bool bHasAbility = RequiredAbility == EAbility::None
				|| (GI && GI->HasAbility(RequiredAbility));
			// "Needs VAULT" if the key is missing; "no way through yet" if the
			// key is there but the far side has not been earned.
			OnExitRefused.Broadcast(bHasAbility ? EAbility::None : RequiredAbility,
				bHasAbility ? AfterClearedStage : NAME_None);
		}
		return;
	}

	if (bArenaDoor)
	{
		bPortalFlare = true;          // the portal flares as he walks through it
	}

	if (DestinationExit)
	{
		// Same level: a step through the doorway. The far exit is told it is
		// travelling too, so landing beside it cannot send him straight back.
		if (USaudAudioSubsystem* Audio = USaudAudioSubsystem::Get(this)) { Audio->PlayUI(TEXT("Exit_Travel")); }
		if (GI)
		{
			FSaudProgress& P = GI->GetMutableProgress();
			P.CurrentStage = DestinationStage;
			P.VisitedStages.AddUnique(DestinationStage);
			GI->SaveProgress();
		}
		DestinationExit->bTravelling = true;
		// Stood a step inside the far door, facing into its district.
		const FVector In = DestinationExit->GetInward();
		Player->SetActorLocation(DestinationExit->GetLandingLocation());
		Player->SetActorRotation(FRotator(0.f, FMath::RadiansToDegrees(FMath::Atan2(In.Y, In.X)), 0.f));
		Player->FaceTowards(Player->GetActorLocation() + In * 100.f);   // the fight's facing, not only the actor's
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
		UE_LOG(LogTemp, Warning, TEXT("[Saud] AreaExit '%s' has no DestinationLevel"), *GetName());
		return;
	}

	bTravelling = true;
	if (USaudAudioSubsystem* Audio = USaudAudioSubsystem::Get(this)) { Audio->PlayUI(TEXT("Exit_Travel")); }

	// The far side reads these on load: where to stand, and what to carry
	// across. Travel is a step through a doorway, not a fresh run.
	FString Options = FString::Printf(TEXT("?ArriveAt=%s"),
		ArriveAt == EAreaSide::East ? TEXT("East") : ArriveAt == EAreaSide::Door ? TEXT("Door")
			: ArriveAt == EAreaSide::Resume ? TEXT("Resume") : TEXT("West"));
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
