#include "Combat/FighterBase.h"
#include "Game/AhmedAudioSubsystem.h"

#include "Engine/DataTable.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Gameplay/AhmedAbilitySystemComponent.h"
#include "Gameplay/AhmedAttributeSet.h"
#include "Gameplay/AhmedGameplayTags.h"

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

	// One component, one attribute set, made here rather than in Blueprint so
	// that every fighter in the game has them whatever it was spawned from.
	AbilitySystem = CreateDefaultSubobject<UAhmedAbilitySystemComponent>(TEXT("AbilitySystem"));
	Attributes = CreateDefaultSubobject<UAhmedAttributeSet>(TEXT("Attributes"));
}

void AFighterBase::BeginPlay()
{
	Super::BeginPlay();
	Health = MaxHealth;
	Stamina = MaxStamina;

	if (AbilitySystem)
	{
		AbilitySystem->InitAbilityActorInfo(this, this);
		AbilitySystem->InitialiseFighter();
	}
}

UAbilitySystemComponent* AFighterBase::GetAbilitySystemComponent() const
{
	return AbilitySystem;
}

void AFighterBase::Tick_Climb(float DeltaSeconds)
{
	if (ClimbElapsed < 0.f)
	{
		return;
	}
	ClimbElapsed += DeltaSeconds;
	const float T = FMath::Clamp(ClimbElapsed / FMath::Max(0.01f, ClimbDuration), 0.f, 1.f);

	// Up first, then forward. Going diagonally would read as floating; a climb
	// is a pull followed by a step, and the curve is what sells the weight.
	const float Up = FMath::Clamp(T * 1.6f, 0.f, 1.f);
	const float Fwd = FMath::Clamp((T - 0.35f) / 0.65f, 0.f, 1.f);

	FVector Pos = ClimbFrom;
	Pos.Z = FMath::Lerp(ClimbFrom.Z, ClimbTo.Z, FMath::InterpEaseOut(0.f, 1.f, Up, 2.f));
	Pos.X = FMath::Lerp(ClimbFrom.X, ClimbTo.X, FMath::InterpEaseInOut(0.f, 1.f, Fwd, 2.f));
	Pos.Y = FMath::Lerp(ClimbFrom.Y, ClimbTo.Y, Fwd);
	SetActorLocation(Pos, false);

	if (T >= 1.f)
	{
		ClimbElapsed = -1.f;
	}
}

void AFighterBase::BeginLedgeClimb(const FVector& Ledge, float Duration)
{
	ClimbFrom = GetActorLocation();
	ClimbTo = Ledge;
	ClimbDuration = FMath::Max(0.05f, Duration);
	ClimbElapsed = 0.f;
}

void AFighterBase::EndLedgeClimb(const FVector& Ledge)
{
	ClimbElapsed = -1.f;
	SetActorLocation(Ledge, false);
}

void AFighterBase::FaceNearestOpponent()
{
	TArray<AFighterBase*> Targets;
	GatherOpponents(Targets);

	const FVector Origin = GetActorLocation();
	float Best = TNumericLimits<float>::Max();
	const AFighterBase* Nearest = nullptr;
	for (const AFighterBase* T : Targets)
	{
		if (!IsValid(T) || !T->IsAlive())
		{
			continue;
		}
		// Depth counts double: the fighter two metres away in front is a
		// better guess at the intended target than one beside you in Y.
		const FVector D = T->GetActorLocation() - Origin;
		const float Score = FMath::Abs(D.X) + FMath::Abs(D.Y) * 2.f;
		if (Score < Best)
		{
			Best = Score;
			Nearest = T;
		}
	}
	if (Nearest)
	{
		FaceTowards(Nearest->GetActorLocation());
	}
}

void AFighterBase::GatherOpponents(TArray<AFighterBase*>& OutTargets) const
{
	GatherTargets(OutTargets);
}

void AFighterBase::SpendStamina(float Amount)
{
	if (Attributes)
	{
		Attributes->SetStamina(FMath::Max(0.f, Attributes->GetStamina() - Amount));
	}
	Stamina = FMath::Max(0.f, Stamina - Amount);
}

FVector AFighterBase::GetIntendedMoveDirection() const
{
	// Whatever the body is already doing. The player overrides this with the
	// stick, which is what makes a dash go where the player is pointing
	// rather than where the character happens to be drifting.
	const FVector Vel = GetVelocity();
	const FVector Flat(Vel.X, Vel.Y, 0.f);
	return Flat.IsNearlyZero()
		? FVector(GetFacingSign(), 0.f, 0.f)
		: Flat.GetSafeNormal();
}

void AFighterBase::ReceiveKnockback(const FVector& Impulse, bool bKnockdown)
{
	if (!IsAlive())
	{
		return;
	}
	LaunchCharacter(Impulse, true, false);
	bSwingFired = true;		// whatever was being thrown is over

	if (bKnockdown && !bResistsKnockdown)
	{
		State = EFighterState::Down;
		DownRemaining = 0.85f;
		if (AbilitySystem)
		{
			// The tag is what stops everything else: no ability activates
			// through State.Downed, so being on the floor needs no other code.
			AbilitySystem->AddLooseGameplayTag(AhmedTags::State_Downed);
			AbilitySystem->SendCombatEvent(AhmedTags::Event_Knockdown, nullptr, 0.f);
		}
		OnKnockedDown();
	}
	else
	{
		State = EFighterState::Hit;
		HitStunRemaining = 0.22f;
		if (AbilitySystem)
		{
			AbilitySystem->AddLooseGameplayTag(AhmedTags::State_HitStun);
		}
	}
}

void AFighterBase::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	TickTimers(DeltaSeconds);
	Tick_Climb(DeltaSeconds);

	// The tags mirror the timers: whatever put one on, running out takes it
	// off, so nothing can be left permanently stunned by a cancelled hit.
	if (AbilitySystem)
	{
		if (HitStunRemaining <= 0.f) { AbilitySystem->RemoveLooseGameplayTag(AhmedTags::State_HitStun); }
		if (DownRemaining <= 0.f)    { AbilitySystem->RemoveLooseGameplayTag(AhmedTags::State_Downed); }
	}

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

	// The swing is heard before it lands; whether it lands is the next sound.
	// The clip is not started here: its swish sits some way into the file,
	// so it is scheduled to begin that much before the first active frame
	// and peaks on it. A lead longer than the startup starts at once and
	// lands late by the difference, which the table is cut to avoid.
	SwingCue = Attack->bHeavy ? TEXT("Whoosh_Heavy") : TEXT("Whoosh_Light");
	UAhmedAudioSubsystem* Audio = UAhmedAudioSubsystem::Get(this);
	SwingAt = FMath::Max(0.f, Attack->Startup - (Audio ? Audio->GetLead(SwingCue) : 0.f));
	bSwingFired = false;
	if (SwingAt <= 0.f)
	{
		FireSwingCue();
	}
	BP_OnAttackStarted(AttackRow);
	return true;
}

void AFighterBase::FireSwingCue()
{
	if (bSwingFired)
	{
		return;
	}
	bSwingFired = true;
	if (UAhmedAudioSubsystem* Audio = UAhmedAudioSubsystem::Get(this))
	{
		Audio->Play(SwingCue, this);
	}
}

void AFighterBase::TickAttack(float DeltaSeconds)
{
	if (!CurrentAttack)
	{
		State = EFighterState::Idle;
		return;
	}

	AttackElapsed += DeltaSeconds;
	if (!bSwingFired && AttackElapsed >= SwingAt)
	{
		FireSwingCue();
	}

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
		if (UAhmedAudioSubsystem* Audio = UAhmedAudioSubsystem::Get(this)) { Audio->Play(TEXT("Parry"), this); }
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
		if (UAhmedAudioSubsystem* Audio = UAhmedAudioSubsystem::Get(this)) { Audio->Play(TEXT("Block"), this); }
		OnDamaged.Broadcast(Health, Result);
		BP_OnHitReceived(Result);
		return Result;
	}

	Health = FMath::Max(0.f, Health - Damage);
	State  = EFighterState::Hit;
	HitStunRemaining = Attack.bHeavy ? 0.34f : 0.22f;
	CurrentAttack = nullptr;
	bSwingFired = true;		// the swing this blow interrupted never happened
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

	// Knockdown, heavy or light -- one sound per blow, and the one that puts a
	// fighter down is its own so the player can hear the difference.
	if (UAhmedAudioSubsystem* Audio = UAhmedAudioSubsystem::Get(this))
	{
		Audio->Play(bKnockdown ? TEXT("Hit_Knockdown")
			: Attack.bHeavy ? TEXT("Hit_Heavy") : TEXT("Hit_Light"), this);
	}
	OnDamaged.Broadcast(Health, Result);
	BP_OnHitReceived(Result);
	return Result;
}

void AFighterBase::PlayFootstep()
{
	if (!IsAlive())
	{
		return;
	}
	if (UAhmedAudioSubsystem* Audio = UAhmedAudioSubsystem::Get(this)) { Audio->Play(TEXT("Footstep"), this); }
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
	if (UAhmedAudioSubsystem* Audio = UAhmedAudioSubsystem::Get(this)) { Audio->Play(TEXT("KO"), this); }
	OnDefeated.Broadcast(this);
	BP_OnDefeated();
}
