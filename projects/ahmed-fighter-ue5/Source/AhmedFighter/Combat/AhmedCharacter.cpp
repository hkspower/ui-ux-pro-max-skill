#include "Combat/AhmedCharacter.h"
#include "Game/AhmedAudioSubsystem.h"

#include "Camera/CameraComponent.h"
#include "Combat/EnemyFighter.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "EngineUtils.h"
#include "Game/AhmedGameInstance.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "World/AbilityGate.h"

AAhmedCharacter::AAhmedCharacter()
{
	PrimaryActorTick.bCanEverTick = true;

	// Side-on camera looking down +Y, pulled back far enough to read the depth
	// of the playfield. Lag keeps it from snapping during dashes.
	CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
	CameraBoom->SetupAttachment(RootComponent);
	CameraBoom->TargetArmLength = 1250.f;
	CameraBoom->SetRelativeRotation(FRotator(-12.f, -90.f, 0.f));
	CameraBoom->bDoCollisionTest = false;
	CameraBoom->bUsePawnControlRotation = false;
	CameraBoom->bInheritPitch = false;
	CameraBoom->bInheritYaw = false;
	CameraBoom->bInheritRoll = false;
	CameraBoom->bEnableCameraLag = true;
	CameraBoom->CameraLagSpeed = 6.f;

	SideViewCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("SideViewCamera"));
	SideViewCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
	SideViewCamera->bUsePawnControlRotation = false;

	MaxHealth = 100.f;
	MaxStamina = 100.f;
	PowerMultiplier = 1.f;
}

void AAhmedCharacter::BeginPlay()
{
	Super::BeginPlay();

	if (UCharacterMovementComponent* Move = GetCharacterMovement())
	{
		BaseWalkSpeed = Move->MaxWalkSpeed;
	}
	ApplyUpgrades();

	if (const APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		if (UEnhancedInputLocalPlayerSubsystem* Subsystem =
			ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PC->GetLocalPlayer()))
		{
			if (DefaultMappingContext)
			{
				Subsystem->AddMappingContext(DefaultMappingContext, 0);
			}
		}
	}
}

void AAhmedCharacter::ApplyUpgrades()
{
	const UAhmedGameInstance* GI = GetWorld() ? GetWorld()->GetGameInstance<UAhmedGameInstance>() : nullptr;
	if (!GI)
	{
		return;
	}

	const FAhmedProgress& P = GI->GetProgress();
	MaxHealth  = 100.f + P.VitalityLevel * 18.f;
	MaxStamina = 100.f + P.StaminaLevel  * 12.f;
	Health  = FMath::Min(Health  <= 0.f ? MaxHealth  : Health,  MaxHealth);
	Stamina = FMath::Min(Stamina <= 0.f ? MaxStamina : Stamina, MaxStamina);

	if (UCharacterMovementComponent* Move = GetCharacterMovement())
	{
		Move->MaxWalkSpeed = BaseWalkSpeed + P.SpeedLevel * 34.f;
	}
}

float AAhmedCharacter::GetOutgoingDamageMultiplier(const FAttackDef& Attack) const
{
	// Boxing and kicking are separate tracks, so each strike scales with its own.
	float Mult = PowerMultiplier;
	if (const UAhmedGameInstance* GI = GetWorld() ? GetWorld()->GetGameInstance<UAhmedGameInstance>() : nullptr)
	{
		const FAhmedProgress& P = GI->GetProgress();
		const int32 Level = (Attack.Family == EAttackFamily::Box) ? P.BoxingLevel : P.KickingLevel;
		Mult *= 1.f + Level * 0.10f;
	}
	return Mult;
}

void AAhmedCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	if (UEnhancedInputComponent* Input = Cast<UEnhancedInputComponent>(PlayerInputComponent))
	{
		if (MoveAction)
		{
			Input->BindAction(MoveAction, ETriggerEvent::Triggered, this, &AAhmedCharacter::Input_Move);
			Input->BindAction(MoveAction, ETriggerEvent::Completed, this, &AAhmedCharacter::Input_Move);
		}
		if (PunchAction) Input->BindAction(PunchAction, ETriggerEvent::Started, this, &AAhmedCharacter::Input_Punch);
		if (KickAction)  Input->BindAction(KickAction,  ETriggerEvent::Started, this, &AAhmedCharacter::Input_Kick);
		if (RageAction)  Input->BindAction(RageAction,  ETriggerEvent::Started, this, &AAhmedCharacter::Input_Rage);
		if (BlockAction)
		{
			Input->BindAction(BlockAction, ETriggerEvent::Started,   this, &AAhmedCharacter::Input_BlockStarted);
			Input->BindAction(BlockAction, ETriggerEvent::Completed, this, &AAhmedCharacter::Input_BlockReleased);
		}
	}
}

void AAhmedCharacter::Input_Move(const FInputActionValue& Value)
{
	MoveInput = Value.Get<FVector2D>();
}

void AAhmedCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	ChainWindowRemaining = FMath::Max(0.f, ChainWindowRemaining - DeltaSeconds);

	ComboWindowRemaining -= DeltaSeconds;
	if (ComboWindowRemaining <= 0.f && ComboCount != 0)
	{
		ComboCount = 0;
		OnComboChanged.Broadcast(ComboCount);
	}

	if (DashRemaining > 0.f)
	{
		DashRemaining -= DeltaSeconds;
		if (DashRemaining <= 0.f && State == EFighterState::Dash)
		{
			State = EFighterState::Idle;
		}
	}

	// Movement is only accepted from a neutral state — commitment is the point.
	if (!IsBusy() && State != EFighterState::Dash)
	{
		const float SpeedScale = bBlocking ? 0.38f : 1.f;
		if (!MoveInput.IsNearlyZero())
		{
			AddMovementInput(FVector(1.f, 0.f, 0.f), MoveInput.X * SpeedScale);
			AddMovementInput(FVector(0.f, 1.f, 0.f), MoveInput.Y * SpeedScale);

			if (FMath::Abs(MoveInput.X) > 0.16f)
			{
				FaceTowards(GetActorLocation() + FVector(MoveInput.X, 0.f, 0.f));
			}
			State = EFighterState::Walk;
		}
		else if (State == EFighterState::Walk)
		{
			State = EFighterState::Idle;
		}
	}

	// Keep Ahmed inside the strip: the arena along X, the walkable depth in Y.
	FVector Loc = GetActorLocation();
	Loc.X = FMath::Clamp(Loc.X, ArenaMinX, ArenaMaxX);
	Loc.Y = FMath::Clamp(Loc.Y, ArenaMinY, ArenaMaxY);
	SetActorLocation(Loc);
}

void AAhmedCharacter::SetArenaBounds(float InMinX, float InMaxX)
{
	SetArenaFrame(InMinX, InMaxX, AhmedGameplay::DepthMin, AhmedGameplay::DepthMax);
}

void AAhmedCharacter::SetArenaFrame(float InMinX, float InMaxX, float InMinY, float InMaxY)
{
	ArenaMinX = InMinX;
	ArenaMaxX = InMaxX;
	ArenaMinY = InMinY;
	ArenaMaxY = InMaxY;
}

void AAhmedCharacter::GatherTargets(TArray<AFighterBase*>& OutTargets) const
{
	if (const UWorld* World = GetWorld())
	{
		for (TActorIterator<AEnemyFighter> It(World); It; ++It)
		{
			if (It->IsAlive())
			{
				OutTargets.Add(*It);
			}
		}
	}
}

void AAhmedCharacter::ResolveAttackHits(const FAttackDef& Attack)
{
	Super::ResolveAttackHits(Attack);

	// Sealed routes take the same swing the enemies do — a shutter only yields
	// to a kick, cracked masonry only to a fist.
	const FVector Origin = GetActorLocation();
	for (TActorIterator<AAbilityGate> It(GetWorld()); It; ++It)
	{
		AAbilityGate* Gate = *It;
		if (!IsValid(Gate) || Gate->IsOpen())
		{
			continue;
		}
		const FVector Delta = Gate->GetActorLocation() - Origin;
		const float Forward = Delta.X * FacingSign;
		if (Forward < -80.f || Forward > Attack.Reach + 120.f)
		{
			continue;
		}
		if (FMath::Abs(Delta.Y) > 320.f)
		{
			continue;
		}
		if (StruckGatesThisSwing.Contains(Gate))
		{
			continue;
		}
		if (Gate->ReceiveStrike(Attack.Family))
		{
			StruckGatesThisSwing.Add(Gate);
		}
	}
}

void AAhmedCharacter::FaceNearestEnemy()
{
	TArray<AFighterBase*> Targets;
	GatherTargets(Targets);

	AFighterBase* Best = nullptr;
	float BestScore = TNumericLimits<float>::Max();
	const FVector Origin = GetActorLocation();

	for (AFighterBase* T : Targets)
	{
		const FVector D = T->GetActorLocation() - Origin;
		// Weight depth heavily: someone directly ahead matters more than
		// someone the same distance away but on a different line.
		const float Score = FMath::Abs(D.X) + FMath::Abs(D.Y) * 2.f;
		if (Score < BestScore)
		{
			BestScore = Score;
			Best = T;
		}
	}

	if (Best && FMath::Abs(Best->GetActorLocation().X - Origin.X) > 20.f)
	{
		FaceTowards(Best->GetActorLocation());
	}
}

FName AAhmedCharacter::NextPunchInChain()
{
	static const FName Chain[] = { TEXT("Jab"), TEXT("Cross"), TEXT("Hook") };

	ChainStep = (ChainWindowRemaining > 0.f) ? (ChainStep + 1) % 3 : 0;
	ChainWindowRemaining = AhmedGameplay::ComboWindow;
	return Chain[ChainStep];
}

void AAhmedCharacter::BeginAttackBookkeeping()
{
	StruckGatesThisSwing.Reset();
}

void AAhmedCharacter::Input_Punch()
{
	if (IsBusy() || State == EFighterState::Dash)
	{
		return;
	}
	FaceNearestEnemy();
	BeginAttackBookkeeping();
	StartAttack(NextPunchInChain());
}

void AAhmedCharacter::Input_Kick()
{
	if (IsBusy() || State == EFighterState::Dash)
	{
		return;
	}
	FaceNearestEnemy();

	// Close in and it becomes a knee — a roundhouse at that range would whiff.
	TArray<AFighterBase*> Targets;
	GatherTargets(Targets);
	bool bClose = false;
	for (const AFighterBase* T : Targets)
	{
		if (FMath::Abs(T->GetActorLocation().X - GetActorLocation().X) < 120.f)
		{
			bClose = true;
			break;
		}
	}
	BeginAttackBookkeeping();
	StartAttack(bClose ? TEXT("Knee") : TEXT("Kick"));
}

void AAhmedCharacter::Input_BlockStarted()
{
	if (IsBusy())
	{
		return;
	}

	// Block while moving is a dodge dash; standing still it is a guard. The
	// parry window opens on the press, never on the hold.
	const bool bMoving = MoveInput.Size() > 0.35f;
	if (bMoving && Stamina >= 14.f)
	{
		const UAhmedGameInstance* GI = GetWorld() ? GetWorld()->GetGameInstance<UAhmedGameInstance>() : nullptr;
		const bool bLeap = GI && GI->HasAbility(EAbility::DashLeap);

		Stamina -= 14.f;
		State = EFighterState::Dash;
		DashRemaining = bLeap ? 0.32f : 0.24f;
		InvulnerableRemaining = bLeap ? 0.34f : 0.26f;

		const FVector Dir = FVector(MoveInput.X, MoveInput.Y, 0.f).GetSafeNormal();
		LaunchCharacter(Dir * (bLeap ? 1500.f : 1150.f), true, false);
		if (UAhmedAudioSubsystem* Audio = UAhmedAudioSubsystem::Get(this))
		{
			Audio->Play(bLeap ? TEXT("Dash_Leap") : TEXT("Dash"), this);
		}
		return;
	}

	bBlocking = true;
	ParryWindowRemaining = AhmedGameplay::ParryWindow;
}

void AAhmedCharacter::Input_BlockReleased()
{
	bBlocking = false;
}

void AAhmedCharacter::Input_Rage()
{
	if (IsBusy() || !IsRageReady())
	{
		return;
	}
	FaceNearestEnemy();
	BeginAttackBookkeeping();
	if (StartAttack(TEXT("Rage")))
	{
		Rage = 0.f;
		InvulnerableRemaining = 0.55f;
		if (UAhmedAudioSubsystem* Audio = UAhmedAudioSubsystem::Get(this)) { Audio->Play(TEXT("Rage"), this); }
		OnRageChanged.Broadcast(GetRageFraction());
		BP_OnRageReleased();
	}
}

void AAhmedCharacter::OnHitLanded(AFighterBase* Victim, const FHitResultData& Hit)
{
	if (Hit.bBlocked || Hit.Damage <= 0.f)
	{
		return;
	}

	Rage = FMath::Clamp(Rage + Hit.Damage * 0.85f, 0.f, AhmedGameplay::RageMax);
	OnRageChanged.Broadcast(GetRageFraction());

	++ComboCount;
	ComboWindowRemaining = AhmedGameplay::ComboResetTime;
	BestCombo = FMath::Max(BestCombo, ComboCount);
	OnComboChanged.Broadcast(ComboCount);
}
