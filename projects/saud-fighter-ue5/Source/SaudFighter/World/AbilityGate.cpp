#include "World/AbilityGate.h"
#include "Game/SaudAudioSubsystem.h"

#include "Combat/SaudCharacter.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Game/SaudGameInstance.h"
#include "Kismet/GameplayStatics.h"

FOnGateOpenedNative AAbilityGate::OnAnyGateOpened;

AAbilityGate::AAbilityGate()
{
	PrimaryActorTick.bCanEverTick = true;

	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	SetRootComponent(Mesh);
	Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	Trigger = CreateDefaultSubobject<UBoxComponent>(TEXT("Trigger"));
	Trigger->SetupAttachment(Mesh);
	Trigger->SetBoxExtent(FVector(180.f, 200.f, 150.f));
	Trigger->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Trigger->SetCollisionResponseToAllChannels(ECR_Overlap);

	// The portal: its origin is the gate box's middle, which is the cube's
	// own origin; the souq's gate wall stands on its foot, so the builders
	// lift it there. Its size is its own, whatever the gate's scale.
	Portal = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Portal"));
	Portal->SetupAttachment(Mesh);
	Portal->SetUsingAbsoluteScale(true);
	Portal->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Portal->SetCastShadow(false);
	Portal->SetCanEverAffectNavigation(false);
}

void AAbilityGate::BeginPlay()
{
	Super::BeginPlay();

	if (GateId.IsNone())
	{
		// Fall back to the level-unique actor name so state still persists.
		GateId = FName(*FString::Printf(TEXT("%s_%s"),
			*GetWorld()->GetName(), *GetName()));
	}

	if (const USaudGameInstance* GI = GetWorld()->GetGameInstance<USaudGameInstance>())
	{
		if (GI->IsGateOpen(GateId))
		{
			bOpen = true;
			BP_OnOpened();
		}
	}

	// Opened on an earlier visit: no portal. Else it starts as it stands,
	// sealed or openable, without waking in front of him.
	PortalState = bOpen ? SaudPortal::Gone : (CanBeOpened() ? SaudPortal::Openable : SaudPortal::Sealed);
	WritePortal();
}

void AAbilityGate::TickPortal(float DeltaSeconds)
{
	const USaudGameInstance* GI = GetWorld() ? GetWorld()->GetGameInstance<USaudGameInstance>() : nullptr;
	// Opened elsewhere (another copy of this gate, a loaded save) is gone
	// without a flare; opened here, the flare runs out first.
	if (!bOpening && (bOpen || (GI && GI->IsGateOpen(GateId))))
	{
		PortalState = SaudPortal::Gone;
	}
	else if (bOpening)
	{
		// Game time: a blow's freeze holds the flare, as it holds the swirl.
		PortalState = FMath::Min(SaudPortal::Gone,
			FMath::Max(PortalState, SaudPortal::Openable) + DeltaSeconds / SaudPortal::OpenSeconds);
		if (PortalState >= SaudPortal::Gone)
		{
			bOpening = false;
		}
	}
	else
	{
		const float Target = CanBeOpened() ? SaudPortal::Openable : SaudPortal::Sealed;
		const float Step = DeltaSeconds / SaudPortal::WakeSeconds;
		PortalState = PortalState > Target ? FMath::Max(Target, PortalState - Step)
			: FMath::Min(Target, PortalState + Step);
	}
	WritePortal();
}

void AAbilityGate::WritePortal()
{
	if (!Portal || PortalState == PortalWritten)
	{
		return;
	}
	PortalWritten = PortalState;
	Portal->SetCustomPrimitiveDataFloat(SaudPortal::DataIndex, PortalState);
	// Gone is not drawn at all, and has no mesh to cost anything.
	Portal->SetVisibility(PortalState < SaudPortal::Gone && Portal->GetStaticMesh() != nullptr);
}

EAbility AAbilityGate::GetRequiredAbility() const
{
	switch (GateType)
	{
	case EGateType::Ledge:   return EAbility::Vault;
	case EGateType::Gap:     return EAbility::DashLeap;
	case EGateType::Shutter: return EAbility::PowerKick;
	case EGateType::Wall:    return EAbility::Haymaker;
	default:                 return EAbility::None;	// a plain stash
	}
}

bool AAbilityGate::CanBeOpened() const
{
	const EAbility Need = GetRequiredAbility();
	if (Need == EAbility::None)
	{
		return true;
	}
	const USaudGameInstance* GI = GetWorld() ? GetWorld()->GetGameInstance<USaudGameInstance>() : nullptr;
	return GI && GI->HasAbility(Need);
}

void AAbilityGate::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	TickPortal(DeltaSeconds);

	if (bOpen)
	{
		bPlayerNearby = false;
		return;
	}

	const ASaudCharacter* Player =
		Cast<ASaudCharacter>(UGameplayStatics::GetPlayerPawn(GetWorld(), 0));
	if (!Player)
	{
		return;
	}

	const FVector Delta = Player->GetActorLocation() - GetActorLocation();
	bPlayerNearby = FMath::Abs(Delta.X) < 260.f && FMath::Abs(Delta.Y) < 300.f;

	// Ledges and gaps open by getting there; shutters and walls need striking.
	const bool bTraversal = (GateType == EGateType::Stash
		|| GateType == EGateType::Ledge
		|| GateType == EGateType::Gap);

	if (bPlayerNearby && bTraversal && CanBeOpened())
	{
		ApproachHeld += DeltaSeconds;
		if (ApproachHeld > 0.45f)
		{
			Open();
		}
	}
	else if (!bPlayerNearby)
	{
		ApproachHeld = 0.f;
	}
}

bool AAbilityGate::ReceiveStrike(EAttackFamily Family)
{
	if (bOpen || !bPlayerNearby || !CanBeOpened())
	{
		return false;
	}

	// The right kind of strike, not merely any hit: shutters want kicks,
	// cracked masonry wants fists.
	const bool bMatches =
		(GateType == EGateType::Shutter && Family == EAttackFamily::Kick) ||
		(GateType == EGateType::Wall    && Family == EAttackFamily::Box);
	if (!bMatches)
	{
		return false;
	}

	++StrikesLanded;
	// The strike that breaks it has its own sound; Open() plays it.
	if (StrikesLanded < StrikesToBreak)
	{
		if (USaudAudioSubsystem* Audio = USaudAudioSubsystem::Get(this)) { Audio->Play(TEXT("Gate_Strike"), this); }
	}
	BP_OnStruck(StrikesLanded);
	if (StrikesLanded >= StrikesToBreak)
	{
		Open();
	}
	return true;
}

void AAbilityGate::Open()
{
	if (bOpen)
	{
		return;
	}
	bOpen = true;
	// the portal flares and collapses (TickPortal, over SaudPortal::OpenSeconds)
	bOpening = true;
	PortalState = FMath::Max(PortalState, SaudPortal::Openable);

	if (USaudAudioSubsystem* Audio = USaudAudioSubsystem::Get(this))
	{
		// Shutters and walls come down; ledges, gaps and lockers just open.
		const bool bBroken = GateType == EGateType::Shutter || GateType == EGateType::Wall;
		Audio->Play(bBroken ? TEXT("Gate_Break") : TEXT("Gate_Open"), this);
	}

	if (USaudGameInstance* GI = GetWorld()->GetGameInstance<USaudGameInstance>())
	{
		GI->MarkGateOpen(GateId);
		if (RewardAbility != EAbility::None)
		{
			GI->GrantAbility(RewardAbility);		// Talent_Found plays there
		}
		else if (RewardExperience > 0)
		{
			GI->AddExperience(RewardExperience);
			if (USaudAudioSubsystem* Audio = USaudAudioSubsystem::Get(this)) { Audio->PlayUI(TEXT("Exp_Cache")); }
		}
		GI->SaveProgress();
	}

	OnGateOpened.Broadcast();
	OnAnyGateOpened.Broadcast(GateId, this);
	BP_OnOpened();
}
