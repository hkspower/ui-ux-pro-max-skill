#include "Combat/SaudCharacter.h"
#include "Combat/SaudArena.h"
#include "Combat/SaudIK.h"
#include "Game/SaudAudioSubsystem.h"
#include "Game/SaudInputBindings.h"
#include "Game/SaudLookSubsystem.h"
#include "Game/SaudMenuSubsystem.h"
#include "Gameplay/SaudAttributeSet.h"

#include "Camera/CameraComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Combat/EnemyFighter.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "EngineUtils.h"
#include "Game/SaudGameInstance.h"
#include "Components/PrimitiveComponent.h"
#include "Engine/World.h"
#include "Misc/App.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "World/AbilityGate.h"

ASaudCharacter::ASaudCharacter()
{
	PrimaryActorTick.bCanEverTick = true;

	// The boom is a mount only. Where it points, how long it is, what it
	// looks at and how it meets a wall are SaudCamera.h's, set every frame
	// by UpdateCamera (2026-10-03, "make it 3d dynamic view"); its own
	// collision snapped the camera in and out, and its own lag would ease
	// what is already eased.
	CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
	CameraBoom->SetupAttachment(RootComponent);
	CameraBoom->TargetArmLength = SaudCamera::IdleArmCm;
	CameraBoom->TargetOffset = FVector(0.f, 0.f, SaudCamera::SocketUpCm);
	CameraBoom->SetRelativeRotation(FRotator(SaudCamera::PitchDeg, 0.f, 0.f));
	CameraBoom->bDoCollisionTest = false;
	CameraBoom->bUsePawnControlRotation = false;
	CameraBoom->bInheritPitch = false;
	CameraBoom->bInheritYaw = false;
	CameraBoom->bInheritRoll = false;
	CameraBoom->bEnableCameraLag = false;

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

	// His outline for the look's aura (2026-10-03): AFighterBase already
	// writes custom depth for every fighter; Saud alone writes this stencil.
	if (USkeletalMeshComponent* Body = GetMesh())
	{
		Body->SetCustomDepthStencilValue(SaudAnime::Power::SaudStencil);
	}

	// His base speed is his data's: the MoveSpeed attribute, 341 cm/s
	// (USaudAttributeSet's InitMoveSpeed: Player.json's BaseMoveSpeed, the
	// browser's 142 px/s). It read the movement component's own MaxWalkSpeed
	// here, which nothing had set -- UE's default 600 -- so he ran at 600
	// and up while the gaits, the camera and the harness all said 341.
	BaseWalkSpeed = (Attributes && Attributes->GetMoveSpeed() > 0.f) ? Attributes->GetMoveSpeed() : SaudCamera::RunSpeedCm;
	if (UCharacterMovementComponent* Move = GetCharacterMovement())
	{
		Move->MaxWalkSpeed = BaseWalkSpeed;
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

	// The actions made in C++ (Game/SaudInputBindings.h), for every pointer
	// a Blueprint left null. The fight's context itself is the menu
	// subsystem's to add, when a fight starts.
	if (const USaudInputBindings* Bindings = USaudInputBindings::Get(this))
	{
		using SaudControls::EAction;
		if (!MoveAction)  MoveAction  = Bindings->Action(EAction::Move);
		if (!LookAction)  LookAction  = Bindings->Action(EAction::Look);
		if (!PunchAction) PunchAction = Bindings->Action(EAction::Punch);
		if (!KickAction)  KickAction  = Bindings->Action(EAction::Kick);
		if (!BlockAction) BlockAction = Bindings->Action(EAction::Block);
		if (!RageAction)  RageAction  = Bindings->Action(EAction::Rage);
		if (!DashAction)  DashAction  = Bindings->Action(EAction::Dash);
		if (!PauseAction) PauseAction = Bindings->Action(EAction::Pause);
	}

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
		if (DashAction)  Input->BindAction(DashAction,  ETriggerEvent::Started, this, &ASaudCharacter::Input_Dash);
		if (PauseAction) Input->BindAction(PauseAction, ETriggerEvent::Started, this, &ASaudCharacter::Input_Pause);
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

	// The camera: framed, moving with him, the stick's to turn. Before
	// movement is read, because movement is measured against where it ends up.
	UpdateCamera();

	// Movement is only accepted from a neutral state — commitment is the point.
	if (!IsBusy() && State != EFighterState::Dash)
	{
		const float SpeedScale = bBlocking ? 0.38f : 1.f;
		// Against the camera, not the world. A camera that swings makes
		// "push the stick away from you" mean something different every
		// second otherwise, and a district becomes unnavigable the first
		// time you turn a corner.
		const FVector Wish = SaudArena::CameraRelative(MoveInput.X, MoveInput.Y, CameraYaw);

		// Which way he faces (Combat/SaudSteer.h). It snapped to the stick
		// every frame, in a fight too, so he never strafed and a reversal
		// at a run was the mesh spinning.
		float Share = 1.f;
		if (IsMovingFree() || GetLocoTurn() != SaudSteer::ETurn::None)
		{
			// FREE: his body turns toward where he goes at a rate; from
			// standing a big turn is a turn on the spot, a reversal at a run
			// a pivot, his movement held while the clip carries the turn (a
			// turn begun before men came near plays out the same way).
			Share = SteerFree(Wish, Wish.SizeSquared2D() > SaudSteer::PushedSq, DeltaSeconds);
		}
		else if (const AFighterBase* Man = NearestOpponent())
		{
			// FIGHTING: he faces his man and moves along the stick without
			// turning to it -- a strafe, any of eight ways.
			FaceTowards(Man->GetActorLocation());
		}

		if (!MoveInput.IsNearlyZero())
		{
			if (Share > 0.f)
			{
				AddMovementInput(Wish, SpeedScale * Share);
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

void ASaudCharacter::UpdateCamera()
{
	if (!CameraBoom)
	{
		return;
	}
	// Real seconds: a blow's freeze stops the world, not the camera's easing.
	const float Dt = static_cast<float>(FApp::GetDeltaTime());
	TArray<AFighterBase*> Targets;
	GatherTargets(Targets);
	TArray<FVector> Opponents;
	for (const AFighterBase* T : Targets)
	{
		Opponents.Add(T->GetActorLocation());
	}
	if (!bCameraStarted)
	{
		bCameraStarted = true;
		Cam.View.Yaw = CameraYaw;
		Cam.View.Pitch = CameraPitch;
	}
	SaudCamera::FInputs In;
	In.Dt = Dt;
	In.Saud = GetActorLocation();
	In.Velocity = GetVelocity();
	In.LookX = LookInput.X;
	In.LookY = LookInput.Y;
	In.Opponents = Opponents.GetData();
	In.NumOpponents = Opponents.Num();
	const SaudCamera::FView V = Cam.Tick(In);
	CameraYaw = V.Yaw;
	CameraPitch = V.Pitch;

	// The walls: probe SoftMarginCm past where the camera would be, from what
	// it looks at, so it comes in before one touches it. The fighters are
	// not walls.
	const FRotator Rot(V.Pitch, V.Yaw, V.Roll);
	const FVector Back = -FRotator(V.Pitch, V.Yaw, 0.f).Vector();
	float SoftFree = V.Arm + SaudCamera::SoftMarginCm;
	float HardFree = 1.0e9f;
	if (UWorld* World = GetWorld())
	{
		FCollisionQueryParams Q(SCENE_QUERY_STAT(SaudCamera), false, this);
		for (AFighterBase* T : Targets)
		{
			Q.AddIgnoredActor(T);
		}
		FHitResult Hit;
		if (World->SweepSingleByChannel(Hit, V.Focus, V.Focus + Back * SoftFree, FQuat::Identity, ECC_Camera,
		                                FCollisionShape::MakeSphere(SaudCamera::ProbeCm), Q))
		{
			SoftFree = Hit.Distance;
			HardFree = Hit.Distance;
		}
	}
	const float Arm = Cam.WallStep(V.Arm, SoftFree, HardFree, Dt);

	CameraBoom->TargetOffset = V.Focus - GetActorLocation();
	CameraBoom->TargetArmLength = Arm;
	CameraBoom->SetWorldRotation(Rot);
	UpdateCameraFades(V.Focus + Back * Arm, Dt);
}

void ASaudCharacter::UpdateCameraFades(const FVector& Eye, float Dt)
{
	// Whatever stands between the camera and him -- every static or moving
	// surface on the line, not only the first -- fades to a dither through
	// custom primitive data slot SaudCamera::FadeDataIndex, which the
	// world's materials read (Tools/look/camera_fade.py).
	TSet<UPrimitiveComponent*> Between;
	if (UWorld* World = GetWorld())
	{
		TArray<FHitResult> Hits;
		FCollisionObjectQueryParams Objects;
		Objects.AddObjectTypesToQuery(ECC_WorldStatic);
		Objects.AddObjectTypesToQuery(ECC_WorldDynamic);
		FCollisionQueryParams Q(SCENE_QUERY_STAT(SaudCameraFade), false, this);
		World->SweepMultiByObjectType(Hits, Eye, GetActorLocation() + FVector(0.f, 0.f, 40.f), FQuat::Identity,
		                              Objects, FCollisionShape::MakeSphere(SaudCamera::FadeProbeCm), Q);
		for (const FHitResult& H : Hits)
		{
			UPrimitiveComponent* C = H.GetComponent();
			if (C && !Cast<APawn>(C->GetOwner()))
			{
				Between.Add(C);
			}
		}
	}
	for (UPrimitiveComponent* C : Between)
	{
		CameraFades.FindOrAdd(C);
	}
	for (auto It = CameraFades.CreateIterator(); It; ++It)
	{
		UPrimitiveComponent* C = It.Key().Get();
		if (!C)
		{
			It.RemoveCurrent();
			continue;
		}
		const bool bBetween = Between.Contains(C);
		const float F = SaudCamera::FadeStep(It.Value(), bBetween, Dt);
		if (F != It.Value() || bBetween)
		{
			C->SetCustomPrimitiveDataFloat(SaudCamera::FadeDataIndex, F);
		}
		It.Value() = F;
		if (F <= 0.f && !bBetween)
		{
			It.RemoveCurrent();
		}
	}
}

void ASaudCharacter::OnCameraBlow(const AFighterBase* Victim, const AFighterBase* Attacker,
                                  const FHitResultData& Hit, bool bHeavy)
{
	if (Hit.bParried || (bHeavy && !Hit.bBlocked))
	{
		// tip away from where the blow landed, as the camera sees it
		const FVector Right = FRotator(0.f, CameraYaw, 0.f).RotateVector(FVector(0.f, 1.f, 0.f));
		const float Side = FVector::DotProduct(Hit.ImpactPoint - GetActorLocation(), Right) >= 0.f ? -1.f : 1.f;
		Cam.Kick(Hit.bParried ? 0.8f : 1.f, Side);
	}
	// a man knocked out by Saud: the swing round him, when it ends the fight
	// or the man is a boss (every street man's fall would be too many)
	// (a killing blow leaves him Down, not yet Dead, when it is reported:
	// his health is what says the fight is over for him)
	if (Attacker == this && Victim && Victim->GetHealth() <= 0.f)
	{
		const AEnemyFighter* Enemy = Cast<AEnemyFighter>(Victim);
		bool bOthersNear = false;
		TArray<AFighterBase*> Targets;
		GatherTargets(Targets);
		for (const AFighterBase* T : Targets)
		{
			if (T != Victim && FVector::Dist2D(T->GetActorLocation(), GetActorLocation()) <= SaudCamera::EngageCm)
			{
				bOthersNear = true;
			}
		}
		if ((Enemy && Enemy->bIsBoss) || !bOthersNear)
		{
			Cam.StartOrbit(SaudCamera::EOrbit::Knockout);
		}
	}
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
	// The nearest living man, flat. It scored |X| + 2|Y| and would not turn
	// to a man within 20 cm of him in world X -- the strip's "in front",
	// which left a man due north or south of him never faced.
	if (const AFighterBase* Man = NearestOpponent())
	{
		FaceTowards(Man->GetActorLocation());
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
	// Flat distance to the nearest man; it was |dX| in world X, a strip's.
	float Nearest = TNumericLimits<float>::Max();
	NearestOpponent(&Nearest);
	const bool bClose = Nearest < 120.f;
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
	if (TryDash())
	{
		return;
	}

	bBlocking = true;
	ParryWindowRemaining = SaudGameplay::ParryWindow;
}

bool ASaudCharacter::TryDash()
{
	const bool bMoving = MoveInput.Size() > 0.35f;
	if (!bMoving || Stamina < 14.f)
	{
		return false;
	}
	const USaudGameInstance* GI = GetWorld() ? GetWorld()->GetGameInstance<USaudGameInstance>() : nullptr;
	const bool bLeap = GI && GI->HasAbility(EAbility::DashLeap);

	Stamina -= 14.f;
	State = EFighterState::Dash;
	DashRemaining = bLeap ? 0.32f : 0.24f;
	++MotionSerial;
	InvulnerableRemaining = bLeap ? 0.34f : 0.26f;

	// Against the camera, as the walk is: it read the raw stick as world X
	// and Y, so a dash went somewhere else than the step it came from.
	const FVector Dir = SaudArena::CameraRelative(MoveInput.X, MoveInput.Y, CameraYaw).GetSafeNormal();
	LaunchCharacter(Dir * (bLeap ? 1500.f : 1150.f), true, false);
	if (USaudAudioSubsystem* Audio = USaudAudioSubsystem::Get(this))
	{
		Audio->Play(bLeap ? TEXT("Dash_Leap") : TEXT("Dash"), this);
	}
	return true;
}

void ASaudCharacter::Input_Dash()
{
	// The dash button: the same dash Block-while-moving takes, and standing
	// still it is nothing at all (no guard, no sound), as the browser has it.
	if (IsBusy())
	{
		return;
	}
	TryDash();
}

void ASaudCharacter::Input_Pause()
{
	// The fight's context goes while the menu is up, so a stick or a
	// shoulder still held would never send its release: drop them here.
	MoveInput = FVector2D::ZeroVector;
	LookInput = FVector2D::ZeroVector;
	bBlocking = false;
	if (USaudMenuSubsystem* Menu = USaudMenuSubsystem::Get(this))
	{
		Menu->Open(SaudMenu::EScreen::Pause);
	}
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
		Cam.StartOrbit(SaudCamera::EOrbit::Finisher);
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
