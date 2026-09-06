#include "Combat/FighterBase.h"

#include "Engine/DataTable.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"

AFighterBase::AFighterBase()
{
	PrimaryActorTick.bCanEverTick = true;

	// A beat-'em-up wants snappy, weightless-feeling ground control: no
	// acceleration ramp to fight against, and the character turns instantly.
	if (UCharacterMovementComponent* Move = GetCharacterMovement())
	{
		Move->bOrientRotationToMovement = false;
		Move->bUseControllerDesiredRotation = false;
		Move->MaxAcceleration = 6000.f;
		Move->BrakingDecelerationWalking = 4000.f;
		Move->GroundFriction = 12.f;
		Move->RotationRate = FRotator(0.f, 1080.f, 0.f);
	}
	bUseControllerRotationYaw = false;
}

void AFighterBase::BeginPlay()
{
	Super::BeginPlay();
	Health = MaxHealth;
	Stamina = MaxStamina;
}

void AFighterBase::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	TickTimers(DeltaSeconds);

	if (State == EFighterState::Attack)
	{
		TickAttack(DeltaSeconds);
	}

	// Blocking drains stamina; everything else refills it.
	const float Regen = bBlocking ? -13.f : AhmedGameplay::StaminaRegenPerSecond;
	Stamina = FMath::Clamp(Stamina + Regen * DeltaSeconds, 0.f, MaxStamina);
}

void AFighterBase::TickTimers(float DeltaSeconds)
{
	InvulnerableRemaining = FMath::Max(0.f, InvulnerableRemaining - DeltaSeconds);
	ParryWindowRemaining  = FMath::Max(0.f, ParryWindowRemaining  - DeltaSeconds);

	if (State == EFighterState::Hit)
	{
		HitStunRemaining -= DeltaSeconds;
		if (HitStunRemaining <= 0.f)
		{
			State = EFighterState::Idle;
		}
	}
	else if (State == EFighterState::Down)
	{
		DownRemaining -= DeltaSeconds;
		if (DownRemaining <= 0.f)
		{
			if (Health <= 0.f)
			{
				OnDeath();
			}
			else
			{
				State = EFighterState::Idle;
				InvulnerableRemaining = 0.6f;	// brief mercy on getting up
			}
		}
	}
}

bool AFighterBase::IsBusy() const
{
	return State == EFighterState::Attack
		|| State == EFighterState::Hit
		|| State == EFighterState::Down
		|| State == EFighterState::Dead;
}

const FAttackDef* AFighterBase::FindAttack(FName Row) const
{
	if (!AttackTable || Row.IsNone())
	{
		return nullptr;
	}
	static const FString Context(TEXT("AFighterBase::FindAttack"));
	return AttackTable->FindRow<FAttackDef>(Row, Context, /*bWarnIfMissing*/ false);
}

bool AFighterBase::StartAttack(FName AttackRow)
{
	if (IsBusy() || State == EFighterState::Dash)
	{
		return false;
	}

	const FAttackDef* Attack = FindAttack(AttackRow);
	if (!Attack)
	{
		UE_LOG(LogTemp, Warning, TEXT("[Ahmed] Unknown attack row '%s'"), *AttackRow.ToString());
		return false;
	}

	if (Stamina < Attack->StaminaCost)
	{
		return false;
	}
	Stamina -= Attack->StaminaCost;

	CurrentAttackRow = AttackRow;
	CurrentAttack    = Attack;
	AttackElapsed    = 0.f;
	bAttackHitFired  = false;
	bBlocking        = false;
	HitThisSwing.Reset();
	State = EFighterState::Attack;

	BP_OnAttackStarted(AttackRow);
	return true;
}

void AFighterBase::TickAttack(float DeltaSeconds)
{
	if (!CurrentAttack)
	{
		State = EFighterState::Idle;
		return;
	}

	AttackElapsed += DeltaSeconds;

	const float ActiveStart = CurrentAttack->Startup;
	const float ActiveEnd   = CurrentAttack->Startup + CurrentAttack->Active;

	if (AttackElapsed >= ActiveStart && AttackElapsed < ActiveEnd)
	{
		// Step into the strike, the way a fighter closes distance on a committed blow.
		const float Lunge = CurrentAttack->bHeavy ? 165.f : 120.f;
		AddMovementInput(FVector(FacingSign, 0.f, 0.f), Lunge * DeltaSeconds, /*bForce*/ true);

		if (!bAttackHitFired || CurrentAttack->bMultiHit)
		{
			ResolveAttackHits(*CurrentAttack);
		}
	}

	if (AttackElapsed >= CurrentAttack->TotalTime())
	{
		CurrentAttack    = nullptr;
		CurrentAttackRow = NAME_None;
		State            = EFighterState::Idle;
	}
}

void AFighterBase::GatherTargets(TArray<AFighterBase*>& OutTargets) const
{
	// Base behaviour: everyone else in the level. Subclasses narrow this to
	// their opposing side so friendly fire never happens.
	if (const UWorld* World = GetWorld())
	{
		for (TActorIterator<AFighterBase> It(World); It; ++It)
		{
			if (*It != this && It->IsAlive())
			{
				OutTargets.Add(*It);
			}
		}
	}
}

void AFighterBase::ResolveAttackHits(const FAttackDef& Attack)
{
	TArray<AFighterBase*> Targets;
	GatherTargets(Targets);

	const FVector Origin = GetActorLocation();

	for (AFighterBase* Target : Targets)
	{
		if (!IsValid(Target) || !Target->IsAlive())
		{
			continue;
		}
		if (Target->State == EFighterState::Down || Target->InvulnerableRemaining > 0.f)
		{
			continue;
		}
		if (HitThisSwing.Contains(Target))
		{
			continue;
		}

		const FVector Delta = Target->GetActorLocation() - Origin;

		// Forward of the attacker, within reach, and roughly on the same depth line.
		const float Forward = Delta.X * FacingSign;
		if (Forward < -60.f || Forward > Attack.Reach + 60.f)
		{
			continue;
		}
		if (FMath::Abs(Delta.Y) > Attack.DepthTolerance)
		{
			continue;
		}

		HitThisSwing.Add(Target);
		bAttackHitFired = true;

		const FHitResultData Hit = Target->ReceiveHit(this, Attack);
		OnHitLanded(Target, Hit);

		if (!Attack.bMultiHit)
		{
			return;
		}
	}
}

float AFighterBase::GetOutgoingDamageMultiplier(const FAttackDef& Attack) const
{
	return PowerMultiplier;
}

FHitResultData AFighterBase::ReceiveHit(AFighterBase* Attacker, const FAttackDef& Attack)
{
	FHitResultData Result;
	Result.ImpactPoint = GetActorLocation() + FVector(0.f, 0.f, 60.f);

	if (!IsAlive() || InvulnerableRemaining > 0.f || !IsValid(Attacker))
	{
		return Result;
	}

	// A guard only counts if it is facing the blow.
	const FVector ToAttacker = Attacker->GetActorLocation() - GetActorLocation();
	const bool bFacingAttacker = (ToAttacker.X * FacingSign) > 0.f;
	const bool bGuarding = bBlocking && bFacingAttacker && State != EFighterState::Attack;

	// Perfect parry: the guard went up inside the window before the blow landed.
	if (bGuarding && ParryWindowRemaining > 0.f && Attacker->State == EFighterState::Attack)
	{
		ParryWindowRemaining  = 0.f;
		InvulnerableRemaining = 0.30f;
		Stamina = FMath::Min(MaxStamina, Stamina + 18.f);

		// The attacker eats the stagger — that is the whole reward for reading it.
		Attacker->State            = EFighterState::Hit;
		Attacker->HitStunRemaining = 0.46f;
		Attacker->CurrentAttack    = nullptr;
		Attacker->LaunchCharacter(FVector(FacingSign * 260.f, 0.f, 0.f), true, false);

		Result.bParried = true;
		BP_OnHitReceived(Result);
		return Result;
	}

	float Damage = Attack.Damage * Attacker->GetOutgoingDamageMultiplier(Attack);
	Damage *= FMath::FRandRange(0.92f, 1.10f);
	if (bGuarding)
	{
		Damage *= AhmedGameplay::BlockDamageMultiplier;
	}
	Damage = FMath::Max(1.f, FMath::RoundToFloat(Damage));

	Result.Damage   = Damage;
	Result.bBlocked = bGuarding;

	if (bGuarding)
	{
		Stamina = FMath::Max(0.f, Stamina - 14.f);
		LaunchCharacter(FVector(Attacker->GetFacingSign() * Attack.Knockback * 0.30f, 0.f, 0.f), true, false);
		OnDamaged.Broadcast(Health, Result);
		BP_OnHitReceived(Result);
		return Result;
	}

	Health = FMath::Max(0.f, Health - Damage);
	State  = EFighterState::Hit;
	HitStunRemaining = Attack.bHeavy ? 0.34f : 0.22f;
	CurrentAttack = nullptr;
	LaunchCharacter(FVector(Attacker->GetFacingSign() * Attack.Knockback, 0.f, 0.f), true, false);

	// Knockdown: always on a killing blow, sometimes on a heavy one, always on
	// the finisher. Bosses shrug most of them off so they cannot be stunlocked.
	const float KnockdownChance = bResistsKnockdown ? 0.12f : 0.45f;
	const bool bKnockdown = Health <= 0.f
		|| Attack.bMultiHit
		|| (Attack.bHeavy && FMath::FRand() < KnockdownChance);

	if (bKnockdown)
	{
		State = EFighterState::Down;
		DownRemaining = Health <= 0.f ? 1.05f : 0.85f;
		Result.bKnockdown = true;
		OnKnockedDown();
	}

	OnDamaged.Broadcast(Health, Result);
	BP_OnHitReceived(Result);
	return Result;
}

void AFighterBase::FaceTowards(const FVector& WorldLocation)
{
	const float Sign = (WorldLocation.X >= GetActorLocation().X) ? 1.f : -1.f;
	if (!FMath::IsNearlyEqual(Sign, FacingSign))
	{
		FacingSign = Sign;
		SetActorRotation(FRotator(0.f, FacingSign > 0.f ? 0.f : 180.f, 0.f));
	}
}

void AFighterBase::OnDeath()
{
	State = EFighterState::Dead;
	SetActorEnableCollision(false);
	OnDefeated.Broadcast(this);
	BP_OnDefeated();
}
