#include "Combat/EnemyFighter.h"

#include "Combat/AhmedCharacter.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "World/WaveDirector.h"

AEnemyFighter::AEnemyFighter()
{
	PrimaryActorTick.bCanEverTick = true;
	AutoPossessAI = EAutoPossessAI::Disabled;	// the behaviour lives here, not in a controller
}

void AEnemyFighter::ConfigureFromDefinition(const FFighterDef& Def, int32 Tier,
	float DifficultyHealth, float DifficultyDamage)
{
	const float TierBoost = 1.f + Tier * 0.10f;

	MaxHealth = FMath::Max(1.f, FMath::RoundToFloat(Def.MaxHealth * TierBoost * DifficultyHealth));
	Health = MaxHealth;

	PowerMultiplier  = Def.PowerMultiplier * TierBoost * DifficultyDamage;
	PreferredRange   = Def.PreferredRange;
	AttackInterval   = Def.AttackInterval;
	GuardChance      = Def.GuardChance;
	bHitAndRun       = Def.bHitAndRun;
	bIsBoss          = Def.bIsBoss;
	bResistsKnockdown = Def.bIsBoss;
	ExperienceValue  = Def.ExperienceValue;
	Moves            = Def.Moves;

	// Enemies are not stamina limited — that budget is the player's problem.
	MaxStamina = Stamina = 9999.f;

	if (UCharacterMovementComponent* Move = GetCharacterMovement())
	{
		Move->MaxWalkSpeed = Def.MoveSpeed;
	}
}

void AEnemyFighter::SetArenaBounds(float InMinX, float InMaxX)
{
	ArenaMinX = InMinX;
	ArenaMaxX = InMaxX;
}

void AEnemyFighter::GatherTargets(TArray<AFighterBase*>& OutTargets) const
{
	if (APawn* Player = UGameplayStatics::GetPlayerPawn(GetWorld(), 0))
	{
		if (AFighterBase* Fighter = Cast<AFighterBase>(Player))
		{
			if (Fighter->IsAlive())
			{
				OutTargets.Add(Fighter);
			}
		}
	}
}

void AEnemyFighter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (bIsBoss && !bEnraged && Health <= MaxHealth * 0.5f && IsAlive())
	{
		EnterPhaseTwo();
	}

	AAhmedCharacter* Player = Cast<AAhmedCharacter>(UGameplayStatics::GetPlayerPawn(GetWorld(), 0));
	if (Player && IsAlive() && !IsBusy())
	{
		TickAI(DeltaSeconds, Player);
	}

	FVector Loc = GetActorLocation();
	Loc.X = FMath::Clamp(Loc.X, ArenaMinX, ArenaMaxX);
	Loc.Y = FMath::Clamp(Loc.Y, AhmedGameplay::DepthMin, AhmedGameplay::DepthMax);
	SetActorLocation(Loc);
}

void AEnemyFighter::EnterPhaseTwo()
{
	bEnraged = true;
	PowerMultiplier *= 1.28f;
	AttackInterval  *= 0.70f;
	InvulnerableRemaining = 0.7f;

	if (UCharacterMovementComponent* Move = GetCharacterMovement())
	{
		Move->MaxWalkSpeed *= 1.20f;
	}
	// Phase two earns the finisher.
	Moves.AddUnique(TEXT("Rage"));
	BP_OnEnraged();
}

void AEnemyFighter::TickAI(float DeltaSeconds, AAhmedCharacter* Player)
{
	AttackCooldown  = FMath::Max(0.f, AttackCooldown - DeltaSeconds);
	RetreatRemaining = FMath::Max(0.f, RetreatRemaining - DeltaSeconds);

	GuardRollTimer -= DeltaSeconds;
	if (GuardRollTimer <= 0.f)
	{
		GuardRollTimer = FMath::FRandRange(0.4f, 1.1f);
		GuardRoll = FMath::FRand();
	}

	const FVector Self = GetActorLocation();
	const FVector Target = Player->GetActorLocation();
	const FVector Delta = Target - Self;

	FaceTowards(Target);

	// Guard when the player commits nearby — this is what makes bouncers a wall.
	bBlocking = (Player->State == EFighterState::Attack)
		&& FMath::Abs(Delta.X) < 240.f
		&& GuardRoll < GuardChance;

	const bool bInRange = FMath::Abs(Delta.X) < PreferredRange * 0.95f
		&& FMath::Abs(Delta.Y) < 70.f;

	if (bInRange && AttackCooldown <= 0.f && Moves.Num() > 0 && Player->State != EFighterState::Down)
	{
		// Only a couple of enemies may swing at once; the rest circle.
		if (AWaveDirector* Director = AWaveDirector::Get(GetWorld()))
		{
			if (!Director->TryClaimAttackToken(this))
			{
				return;
			}
		}

		const FName Move = Moves[FMath::RandRange(0, Moves.Num() - 1)];
		if (StartAttack(Move))
		{
			AttackCooldown = AttackInterval * FMath::FRandRange(0.75f, 1.45f);
			if (bHitAndRun)
			{
				RetreatRemaining = FMath::FRandRange(0.7f, 1.2f);
			}
		}
		return;
	}

	// Hold a spot on one side of the player, in your own lane and depth.
	float DesiredX = Target.X + FlankSide * (PreferredRange * 0.70f + LaneOffset);
	if (RetreatRemaining > 0.f)
	{
		DesiredX = Target.X + FlankSide * 660.f;		// back off after committing
	}

	// Never try to stand where the arena will not let you — flip sides instead.
	if (DesiredX < ArenaMinX + 50.f || DesiredX > ArenaMaxX - 50.f)
	{
		FlankSide = -FlankSide;
		DesiredX = Target.X + FlankSide * (PreferredRange * 0.70f + LaneOffset);
	}
	// Far away, forget the lane and just close.
	if (FMath::Abs(Delta.X) > 950.f)
	{
		DesiredX = Target.X;
	}

	const float DesiredY = FMath::Clamp(Target.Y + DepthOffset,
		AhmedGameplay::DepthMin, AhmedGameplay::DepthMax);

	const FVector Desired(DesiredX, DesiredY, Self.Z);
	const FVector ToDesired = Desired - Self;

	if (ToDesired.Size2D() > 20.f)
	{
		const FVector Dir = ToDesired.GetSafeNormal2D();
		const float Scale = bBlocking ? 0.4f : 1.f;
		AddMovementInput(FVector(Dir.X, 0.f, 0.f), Scale);
		AddMovementInput(FVector(0.f, Dir.Y, 0.f), Scale);
		State = EFighterState::Walk;
	}
	else if (State == EFighterState::Walk)
	{
		State = EFighterState::Idle;
	}
}

void AEnemyFighter::OnKnockedDown()
{
	// Drop the token immediately so someone else can press the attack.
	if (AWaveDirector* Director = AWaveDirector::Get(GetWorld()))
	{
		Director->ReleaseAttackToken(this);
	}
}
