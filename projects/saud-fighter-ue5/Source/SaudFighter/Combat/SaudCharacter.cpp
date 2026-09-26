#include "Combat/SaudCharacter.h"
#include "Combat/SaudArena.h"
#include "Combat/SaudIK.h"
#include "Game/SaudAudioSubsystem.h"
#include "Game/SaudLookSubsystem.h"

#include "Camera/CameraComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Combat/EnemyFighter.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "EngineUtils.h"
#include "Game/SaudGameInstance.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "World/AbilityGate.h"

ASaudCharacter::ASaudCharacter()
{
	PrimaryActorTick.bCanEverTick = true;

	// Side-on camera looking down +Y, pulled back far enough to read the depth
	// of the playfield. Lag keeps it from snapping during dashes.
	CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
	CameraBoom->SetupAttachment(RootComponent);
	CameraBoom->TargetArmLength = 640.f;
	CameraBoom->SocketOffset = FVector(0.f, 0.f, 90.f);
	CameraBoom->SetRelativeRotation(FRotator(-18.f, 0.f, 0.f));
	// Swept now. On the strip the camera was outside the level looking in and
	// nothing could get between it and Saud; in a district full of buildings
	// a boom that ignores them spends half of a fight inside a wall.
	CameraBoom->bDoCollisionTest = true;
	CameraBoom->ProbeSize = 16.f;
	CameraBoom->bUsePawnControlRotation = false;
	CameraBoom->bInheritPitch = false;
	CameraBoom->bInheritYaw = false;
	CameraBoom->bInheritRoll = false;
	CameraBoom->bEnableCameraLag = true;
	CameraBoom->CameraLagSpeed = 12.f;

	FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
	FollowCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
	FollowCamera->bUsePawnControlRotation = false;

	// The body turns to face where it is going rather than snapping between
	// two directions; the controller does not steer it.
	bUseControllerRotationYaw = false;

	MaxHealth = 100.f;
	MaxStamina = 100.f;
	PowerMultiplier = 1.f;
}

void ASaudCharacter::BeginPlay()
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

void ASaudCharacter::ApplyUpgrades()
{
	const USaudGameInstance* GI = GetWorld() ? GetWorld()->GetGameInstance<USaudGameInstance>() : nullptr;
	if (!GI)
	{
		return;
	}

	const FSaudProgress& P = GI->GetProgress();
	MaxHealth  = 100.f + P.VitalityLevel * 18.f;
	MaxStamina = 100.f + P.StaminaLevel  * 12.f;
	Health  = FMath::Min(Health  <= 0.f ? MaxHealth  : Health,  MaxHealth);
	Stamina = FMath::Min(Stamina <= 0.f ? MaxStamina : Stamina, MaxStamina);

	if (UCharacterMovementComponent* Move = GetCharacterMovement())
	{
		Move->MaxWalkSpeed = BaseWalkSpeed + P.SpeedLevel * 34.f;
	}

	// IRON ARM's look: his right arm turns to iron a fifth of the way per
	// level. The skin material reads IronArmLevel (0..1) against
	// T_Saud_IronArm_Mask -- see Tools/blender/build_iron_arm.py for the
	// blend it has to make. A material without the parameter ignores it.
	if (USkeletalMeshComponent* Body = GetMesh())
	{
		Body->SetScalarParameterValueOnMaterials(TEXT("IronArmLevel"),
			FMath::Clamp(P.IronArmLevel / 5.f, 0.f, 1.f));
	}
}

float ASaudCharacter::GetOutgoingDamageMultiplier(const FAttackDef& Attack) const
{
	// Boxing and kicking are separate tracks, so each strike scales with its own.
	float Mult = PowerMultiplier;
	if (const USaudGameInstance* GI = GetWorld() ? GetWorld()->GetGameInstance<USaudGameInstance>() : nullptr)
	{
		const FSaudProgress& P = GI->GetProgress();
		const int32 Level = (Attack.Family == EAttackFamily::Box) ? P.BoxingLevel : P.KickingLevel;
		Mult *= 1.f + Level * 0.10f;
	}
	// A burning HAWK FIST punch: the browser's x1.55 on top.
	if (bAttackBurning && State == EFighterState::Attack && Attack.Family == EAttackFamily::Box)
	{
		Mult *= SaudFire::DamageMultiplier;
	}
	return Mult;
}

/* -------------------------------------------------------------- HAWK FIST */

bool ASaudCharacter::IsHawkLit() const
{
	const USaudGameInstance* GI = GetWorld() ? GetWorld()->GetGameInstance<USaudGameInstance>() : nullptr;
	return SaudFire::Lit(GI && GI->HasAbility(EAbility::HawkFist), Mana);
}

float ASaudCharacter::GetHawkHeat() const
{
	const bool bSwingingPunch = State == EFighterState::Attack && CurrentAttack
		&& CurrentAttack->Family == EAttackFamily::Box;
	return SaudFire::Heat(Fire.Lit01, bSwingingPunch);
}

void ASaudCharacter::GetFlameBones(FName& OutHand, FName& OutForearm) const
{
	char Side = 0;
	const bool bPunching = State == EFighterState::Attack && CurrentAttack
		&& CurrentAttack->Family == EAttackFamily::Box;
	if (bPunching)
	{
		SaudIK::StrikingLimb(TCHAR_TO_ANSI(*CurrentAttackRow.ToString()), Side);
	}
	const bool bRight = SaudFire::FlameHand(bPunching, Side) == 'r';
	OutHand = bRight ? FName(TEXT("hand_r")) : FName(TEXT("hand_l"));
	OutForearm = bRight ? FName(TEXT("lowerarm_r")) : FName(TEXT("lowerarm_l"));
}

void ASaudCharacter::OnAttackStarted(const FAttackDef& Attack)
{
	// hawkAttack(): decided as the swing starts, spent when it lands.
	bAttackBurning = SaudFire::Burning(IsHawkLit(), Attack.Family == EAttackFamily::Box);
	bHawkSpent = false;
}

float ASaudCharacter::GetAttackReachBonus(const FAttackDef& Attack) const
{
	return (bAttackBurning && State == EFighterState::Attack) ? SaudFire::ReachCm : 0.f;
}

float ASaudCharacter::GetAttackKnockbackBonus(const FAttackDef& Attack) const
{
	return (bAttackBurning && State == EFighterState::Attack) ? SaudFire::PushCm : 0.f;
}

float ASaudCharacter::GetBlockCostMultiplier(bool bPush) const
{
	// IRON ARM: each bought level takes its share off what a block costs.
	const USaudGameInstance* GI = GetWorld() ? GetWorld()->GetGameInstance<USaudGameInstance>() : nullptr;
	if (!GI)
	{
		return 1.f;
	}
	const float PerLevel = bPush ? SaudGameplay::IronArmBlockPushPerLevel : SaudGameplay::IronArmBlockStaminaPerLevel;
	return FMath::Max(0.f, 1.f - GI->GetProgress().IronArmLevel * PerLevel);
}

void ASaudCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	if (UEnhancedInputComponent* Input = Cast<UEnhancedInputComponent>(PlayerInputComponent))
	{
		if (MoveAction)
		{
			Input->BindAction(MoveAction, ETriggerEvent::Triggered, this, &ASaudCharacter::Input_Move);
			Input->BindAction(MoveAction, ETriggerEvent::Completed, this, &ASaudCharacter::Input_Move);
		}
		if (PunchAction) Input->BindAction(PunchAction, ETriggerEvent::Started, this, &ASaudCharacter::Input_Punch);
		if (KickAction)  Input->BindAction(KickAction,  ETriggerEvent::Started, this, &ASaudCharacter::Input_Kick);
		if (RageAction)  Input->BindAction(RageAction,  ETriggerEvent::Started, this, &ASaudCharacter::Input_Rage);
		if (LookAction)
		{
			Input->BindAction(LookAction, ETriggerEvent::Triggered, this, &ASaudCharacter::Input_Look);
			Input->BindAction(LookAction, ETriggerEvent::Completed, this, &ASaudCharacter::Input_Look);
		}
		if (BlockAction)
		{
			Input->BindAction(BlockAction, ETriggerEvent::Started,   this, &ASaudCharacter::Input_BlockStarted);
			Input->BindAction(BlockAction, ETriggerEvent::Completed, this, &ASaudCharacter::Input_BlockReleased);
		}
	}
}

void ASaudCharacter::Input_Move(const FInputActionValue& Value)
{
	MoveInput = Value.Get<FVector2D>();
}

void ASaudCharacter::Input_Look(const FInputActionValue& Value)
{
	LookInput = Value.Get<FVector2D>();
}

void ASaudCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	ChainWindowRemaining = FMath::Max(0.f, ChainWindowRemaining - DeltaSeconds);

	ComboWindowRemaining -= DeltaSeconds;
	if (ComboWindowRemaining <= 0.f && ComboCount != 0)
	{
		ComboCount = 0;
		OnComboChanged.Broadcast(ComboCount);
	}

	// HAWK FIST: MP back slowly with the clock (the browser's mpRegen.idle),
	// and the flame eased toward lit or out, in game time -- it stands
	// still through a freeze as the browser's does.
	Mana = FMath::Min(SaudFire::MaxMana, Mana + SaudFire::ManaRegenPerSecond * DeltaSeconds);
	Fire.Tick(DeltaSeconds, IsHawkLit());

	if (DashRemaining > 0.f)
	{
		DashRemaining -= DeltaSeconds;
		if (DashRemaining <= 0.f && State == EFighterState::Dash)
		{
			State = EFighterState::Idle;
		}
	}

	// The boom is the player's. It is swung and pitched before movement is
	// read, because movement is measured against where it ends up.
	if (!LookInput.IsNearlyZero())
	{
		CameraYaw += LookInput.X * CameraTurnRate * DeltaSeconds;
		CameraPitch = FMath::Clamp(CameraPitch - LookInput.Y * CameraPitchRate * DeltaSeconds,
		                           CameraMinPitch, CameraMaxPitch);
	}
	if (CameraBoom)
	{
		CameraBoom->SetWorldRotation(FRotator(CameraPitch, CameraYaw, 0.f));
	}

	// Movement is only accepted from a neutral state — commitment is the point.
	if (!IsBusy() && State != EFighterState::Dash)
	{
		const float SpeedScale = bBlocking ? 0.38f : 1.f;
		if (!MoveInput.IsNearlyZero())
		{
			// Against the camera, not the world. A camera that swings makes
			// "push the stick away from you" mean something different every
			// second otherwise, and a district becomes unnavigable the first
			// time you turn a corner.
			const FVector Wish = SaudArena::CameraRelative(MoveInput.X, MoveInput.Y, CameraYaw);
			AddMovementInput(Wish, SpeedScale);

			// Face where you are going. It used to be a sign on X, which is
			// why he could only ever look two ways.
			if (Wish.SizeSquared2D() > 0.03f)
			{
				FaceTowards(GetActorLocation() + Wish);
			}
			State = EFighterState::Walk;
		}
		else if (State == EFighterState::Walk)
		{
			State = EFighterState::Idle;
		}
	}

	// Keep Saud inside the place he is fighting in.
	SetActorLocation(SaudArena::ClampToCircle(GetActorLocation(), ArenaCentre, ArenaRadius));
}

void ASaudCharacter::SetArenaCircle(const FVector& InCentre, float InRadius)
{
	ArenaCentre = InCentre;
	ArenaRadius = InRadius;
}

void ASaudCharacter::GatherTargets(TArray<AFighterBase*>& OutTargets) const
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

void ASaudCharacter::ResolveAttackHits(const FAttackDef& Attack)
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
		// A gate is wider than a man and forgiving to line up with, so it
		// takes the same box with more slack rather than a rule of its own.
		if (!SaudArena::InHitbox(Origin, Facing, Gate->GetActorLocation(),
		                          Attack.Reach, 320.f, 80.f, 120.f))
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

void ASaudCharacter::FaceNearestEnemy()
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

FName ASaudCharacter::NextPunchInChain()
{
	static const FName Chain[] = { TEXT("Jab"), TEXT("Cross"), TEXT("Hook") };

	ChainStep = (ChainWindowRemaining > 0.f) ? (ChainStep + 1) % 3 : 0;
	ChainWindowRemaining = SaudGameplay::ComboWindow;
	return Chain[ChainStep];
}

void ASaudCharacter::BeginAttackBookkeeping()
{
	StruckGatesThisSwing.Reset();
}

void ASaudCharacter::Input_Punch()
{
	if (IsBusy() || State == EFighterState::Dash)
	{
		return;
	}
	FaceNearestEnemy();
	BeginAttackBookkeeping();
	StartAttack(NextPunchInChain());
}

void ASaudCharacter::Input_Kick()
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

void ASaudCharacter::Input_BlockStarted()
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
		const USaudGameInstance* GI = GetWorld() ? GetWorld()->GetGameInstance<USaudGameInstance>() : nullptr;
		const bool bLeap = GI && GI->HasAbility(EAbility::DashLeap);

		Stamina -= 14.f;
		State = EFighterState::Dash;
		DashRemaining = bLeap ? 0.32f : 0.24f;
		++MotionSerial;
		InvulnerableRemaining = bLeap ? 0.34f : 0.26f;

		const FVector Dir = FVector(MoveInput.X, MoveInput.Y, 0.f).GetSafeNormal();
		LaunchCharacter(Dir * (bLeap ? 1500.f : 1150.f), true, false);
		if (USaudAudioSubsystem* Audio = USaudAudioSubsystem::Get(this))
		{
			Audio->Play(bLeap ? TEXT("Dash_Leap") : TEXT("Dash"), this);
		}
		return;
	}

	bBlocking = true;
	ParryWindowRemaining = SaudGameplay::ParryWindow;
}

void ASaudCharacter::Input_BlockReleased()
{
	bBlocking = false;
}

void ASaudCharacter::Input_Rage()
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
		if (USaudAudioSubsystem* Audio = USaudAudioSubsystem::Get(this)) { Audio->Play(TEXT("Rage"), this); }
		OnRageChanged.Broadcast(GetRageFraction());
		BP_OnRageReleased();
	}
}

void ASaudCharacter::OnHitLanded(AFighterBase* Victim, const FHitResultData& Hit)
{
	// applyHit(), before it asks whether the blow was blocked: a burning
	// swing spends its MP on the first man it lands on and bursts on him,
	// guard or no guard; any other landed blow gives a little MP back.
	if (bAttackBurning && !bHawkSpent)
	{
		bHawkSpent = true;
		Mana = FMath::Max(0.f, Mana - SaudFire::ManaCost);
		Fire.Burn();
		if (USaudLookSubsystem* Look = USaudLookSubsystem::Get(this))
		{
			Look->OnBurn(Victim);
		}
	}
	else
	{
		Mana = FMath::Min(SaudFire::MaxMana, Mana + SaudFire::ManaPerLandedHit);
	}

	if (Hit.bBlocked || Hit.Damage <= 0.f)
	{
		return;
	}

	Rage = FMath::Clamp(Rage + Hit.Damage * 0.85f, 0.f, SaudGameplay::RageMax);
	OnRageChanged.Broadcast(GetRageFraction());

	++ComboCount;
	ComboWindowRemaining = SaudGameplay::ComboResetTime;
	BestCombo = FMath::Max(BestCombo, ComboCount);
	OnComboChanged.Broadcast(ComboCount);
}
