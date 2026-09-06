#include "World/AbilityGate.h"
#include "Game/AhmedAudioSubsystem.h"

#include "Combat/AhmedCharacter.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Game/AhmedGameInstance.h"
#include "Kismet/GameplayStatics.h"

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

	if (const UAhmedGameInstance* GI = GetWorld()->GetGameInstance<UAhmedGameInstance>())
	{
		if (GI->IsGateOpen(GateId))
		{
			bOpen = true;
			BP_OnOpened();
		}
	}
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
	const UAhmedGameInstance* GI = GetWorld() ? GetWorld()->GetGameInstance<UAhmedGameInstance>() : nullptr;
	return GI && GI->HasAbility(Need);
}

void AAbilityGate::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (bOpen)
	{
		bPlayerNearby = false;
		return;
	}

	const AAhmedCharacter* Player =
		Cast<AAhmedCharacter>(UGameplayStatics::GetPlayerPawn(GetWorld(), 0));
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
		if (UAhmedAudioSubsystem* Audio = UAhmedAudioSubsystem::Get(this)) { Audio->Play(TEXT("Gate_Strike"), this); }
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

	if (UAhmedAudioSubsystem* Audio = UAhmedAudioSubsystem::Get(this))
	{
		// Shutters and walls come down; ledges, gaps and lockers just open.
		const bool bBroken = GateType == EGateType::Shutter || GateType == EGateType::Wall;
		Audio->Play(bBroken ? TEXT("Gate_Break") : TEXT("Gate_Open"), this);
	}

	if (UAhmedGameInstance* GI = GetWorld()->GetGameInstance<UAhmedGameInstance>())
	{
		GI->MarkGateOpen(GateId);
		if (RewardAbility != EAbility::None)
		{
			GI->GrantAbility(RewardAbility);		// Talent_Found plays there
		}
		else if (RewardExperience > 0)
		{
			GI->AddExperience(RewardExperience);
			if (UAhmedAudioSubsystem* Audio = UAhmedAudioSubsystem::Get(this)) { Audio->PlayUI(TEXT("Exp_Cache")); }
		}
		GI->SaveProgress();
	}

	OnGateOpened.Broadcast();
	BP_OnOpened();
}
