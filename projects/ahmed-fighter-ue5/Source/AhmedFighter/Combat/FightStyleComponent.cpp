#include "Combat/FightStyleComponent.h"

#include "Combat/EnemyFighter.h"
#include "Combat/FighterBase.h"
#include "World/WaveDirector.h"

UFightStyleComponent::UFightStyleComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickInterval = 0.f;
}

AFighterBase* UFightStyleComponent::GetFighter() const
{
	return Cast<AFighterBase>(GetOwner());
}

void UFightStyleComponent::BeginPlay()
{
	Super::BeginPlay();

	// Eating a hit is a reaction, and the fighter already announces it. No
	// need for anything to call in here.
	if (AFighterBase* Fighter = GetFighter())
	{
		Fighter->OnDamaged.AddDynamic(this, &UFightStyleComponent::HandleDamaged);
	}
	CircleDirection = FMath::RandBool() ? 1.f : -1.f;
	// Stagger the first swing across a wave so five enemies do not all throw
	// on the same frame they spawned.
	AttackCooldown = FMath::FRandRange(0.15f, 0.8f);
}

void UFightStyleComponent::TickComponent(float DeltaTime, ELevelTick TickType,
	FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	AFighterBase* Fighter = GetFighter();
	if (!IsDriving() || !Fighter || !Fighter->IsAlive())
	{
		return;
	}

	AttackCooldown = FMath::Max(0.f, AttackCooldown - DeltaTime);
	ResetRemaining = FMath::Max(0.f, ResetRemaining - DeltaTime);
	AcquireTimer   = FMath::Max(0.f, AcquireTimer   - DeltaTime);

	// Runs even while busy: a swing ends during the busy window, and whether
	// it landed is decided there.
	TickSwingResult();

	if (!Opponent.IsValid() || !Opponent->IsAlive() || AcquireTimer <= 0.f)
	{
		AcquireOpponent();
	}
	if (!Opponent.IsValid())
	{
		return;
	}

	// Mid-swing, stunned or on the floor: not making decisions. Ticking a
	// style through those states is how AI queues three strikes into a
	// knockdown and throws them all on standing up.
	if (Fighter->IsBusy())
	{
		return;
	}

	const FVector Self = Fighter->GetActorLocation();
	const FVector Them = Opponent->GetActorLocation();
	const FVector To = Them - Self;
	const float Distance = FMath::Abs(To.X);

	Band = Style->BandFor(Distance);
	Fighter->FaceTowards(Them);

	TickDefence(DeltaTime, Distance);
	TickOffence();
	TickFootwork(DeltaTime, To, Distance);
}

void UFightStyleComponent::AddStrike(const FStyleStrike& Strike)
{
	if (Strike.AttackRow.IsNone())
	{
		return;
	}
	for (const FStyleStrike& S : ExtraStrikes)
	{
		if (S.AttackRow == Strike.AttackRow)
		{
			return;
		}
	}
	ExtraStrikes.Add(Strike);
}

void UFightStyleComponent::AcquireOpponent()
{
	AcquireTimer = 0.5f;

	AFighterBase* Fighter = GetFighter();
	if (!Fighter)
	{
		return;
	}
	TArray<AFighterBase*> Targets;
	Fighter->GatherOpponents(Targets);

	const FVector Origin = Fighter->GetActorLocation();
	float Best = TNumericLimits<float>::Max();
	AFighterBase* Nearest = nullptr;
	for (AFighterBase* T : Targets)
	{
		if (!IsValid(T) || !T->IsAlive())
		{
			continue;
		}
		const FVector D = T->GetActorLocation() - Origin;
		const float Score = FMath::Abs(D.X) + FMath::Abs(D.Y) * 2.f;
		if (Score < Best)
		{
			Best = Score;
			Nearest = T;
		}
	}
	Opponent = Nearest;
}

/**
 * Footwork.
 *
 * Three things layered: hold the style's distance, circle rather than walk
 * straight in, and bounce in and out if the style bounces. The bounce is what
 * makes a points fighter look like one before he has thrown anything.
 */
void UFightStyleComponent::TickFootwork(float DeltaTime, const FVector& To, float Distance)
{
	AFighterBase* Fighter = GetFighter();
	if (!Fighter)
	{
		return;
	}
	// Committed to a swing -- TickOffence may have started one a moment ago
	// in this same frame. Feet stay where they are: sliding during startup is
	// the single most common thing that makes a fight look weightless, and
	// walking here would also stamp Walk over the attack state.
	if (Fighter->State == EFighterState::Attack)
	{
		return;
	}

	const float Facing = FMath::Sign(To.X);

	// 1. The distance it wants right now.
	float Wanted = Style->PreferredRange;
	if (ResetRemaining > 0.f && Style->ResetDistance > 0.f)
	{
		Wanted = Style->ResetDistance;			// backing off after committing
	}
	if (Style->BounceRate > 0.f)
	{
		BouncePhase += DeltaTime * Style->BounceRate * 2.f * PI;
		Wanted += FMath::Sin(BouncePhase) * Style->BounceAmplitude;
	}

	// 2. Close or back off, scaled by how much this style cares. A pressure
	//    fighter barely corrects; a range fighter corrects constantly.
	const float Error = Distance - Wanted;
	const float Urgency = FMath::Lerp(0.35f, 1.f, Style->RangeDiscipline);
	float Forward = 0.f;
	if (FMath::Abs(Error) > 18.f)
	{
		Forward = FMath::Clamp(Error / 120.f, -1.f, 1.f) * Urgency * Facing;
	}

	// 3. Circling, towards the opponent's depth line as well as around it --
	//    a strike that misses on depth is not a decision anyone can read.
	CircleTimer -= DeltaTime;
	if (CircleTimer <= 0.f)
	{
		CircleTimer = Style->CircleSwitchTime * FMath::FRandRange(0.6f, 1.5f);
		CircleDirection = FMath::RandBool() ? 1.f : -1.f;
	}
	float Sideways = Style->CircleTendency * CircleDirection;
	if (FMath::Abs(To.Y) > 60.f)
	{
		// Too far off the line to circle: get on it first.
		Sideways = FMath::Sign(To.Y);
	}
	else
	{
		// Do not circle out of the playable strip.
		const float Y = Fighter->GetActorLocation().Y;
		if ((Y < AhmedGameplay::DepthMin + 60.f && Sideways < 0.f)
			|| (Y > AhmedGameplay::DepthMax - 60.f && Sideways > 0.f))
		{
			Sideways = -Sideways;
			CircleDirection = -CircleDirection;
		}
	}

	// Guarding halves the pace, the way it does for a person.
	const float Scale = Fighter->bBlocking ? 0.45f : 1.f;
	if (!FMath::IsNearlyZero(Forward))
	{
		Fighter->AddMovementInput(FVector(1.f, 0.f, 0.f), Forward * Scale);
	}
	if (!FMath::IsNearlyZero(Sideways))
	{
		Fighter->AddMovementInput(FVector(0.f, 1.f, 0.f), Sideways * Scale);
	}

	Fighter->State = (FMath::IsNearlyZero(Forward) && FMath::IsNearlyZero(Sideways))
		? EFighterState::Idle : EFighterState::Walk;
}

/**
 * Offence.
 *
 * Range decides what is available; the style's weights decide which of those.
 * If nothing is legal at this distance the fighter throws nothing and keeps
 * walking, which separates a boxer from a kickboxer far more than any damage
 * number does.
 */
void UFightStyleComponent::TickOffence()
{
	if (AttackCooldown > 0.f || Band == ERangeBand::Out)
	{
		return;
	}
	AFighterBase* Fighter = GetFighter();
	if (!Fighter || !Opponent.IsValid() || !Opponent->IsAlive())
	{
		return;
	}
	// Not while the opponent is on the floor. Hitting someone down is both
	// unfair and, in a crowd, unreadable.
	if (Opponent->State == EFighterState::Down)
	{
		return;
	}

	// Mid-combination: keep going without asking the director again, because
	// the token was claimed for the whole combination.
	if (ComboRemaining > 0)
	{
		if (const FStyleStrike* Next = Style->ChooseStrike(Band, ExtraStrikes))
		{
			if (TryThrow(*Next))
			{
				--ComboRemaining;
				// Inside a combination the gap is the recovery, not the interval.
				AttackCooldown = 0.06f;
				return;
			}
		}
		ComboRemaining = 0;
	}

	// The crowd rule: only a couple may be swinging at once, the rest circle.
	if (AEnemyFighter* Enemy = Cast<AEnemyFighter>(Fighter))
	{
		if (AWaveDirector* Director = AWaveDirector::Get(GetWorld()))
		{
			if (!Director->TryClaimAttackToken(Enemy))
			{
				return;
			}
		}
	}

	const FStyleStrike* Strike = Style->ChooseStrike(Band, ExtraStrikes);
	if (!Strike)
	{
		// Nothing from here. Wait a beat rather than re-rolling every frame.
		AttackCooldown = 0.25f;
		return;
	}
	if (!TryThrow(*Strike))
	{
		AttackCooldown = 0.2f;
		return;
	}

	// Openers start combinations; finishers stand alone.
	ComboRemaining = (FMath::FRand() < Strike->OpensCombination)
		? FMath::RandRange(1, FMath::Max(1, Style->MaxComboLength - 1))
		: 0;

	const float Jitter = FMath::FRandRange(1.f - Style->RhythmJitter, 1.f + Style->RhythmJitter);
	AttackCooldown = Style->AttackInterval * Jitter / FMath::Max(0.1f, Haste);

	if (Style->ResetDistance > 0.f)
	{
		ResetRemaining = FMath::FRandRange(0.6f, 1.1f);
	}
}

bool UFightStyleComponent::TryThrow(const FStyleStrike& Strike)
{
	AFighterBase* Fighter = GetFighter();
	if (!Fighter || Strike.AttackRow.IsNone() || !Fighter->StartAttack(Strike.AttackRow))
	{
		return false;
	}
	bSwingPending = true;
	return true;
}

/**
 * Defence.
 *
 * The guard is rolled a few times a second rather than every frame: one that
 * re-decides sixty times a second flickers instead of guarding, which looks
 * like a bug and plays like one.
 */
void UFightStyleComponent::TickDefence(float DeltaTime, float Distance)
{
	AFighterBase* Fighter = GetFighter();
	if (!Fighter || !Opponent.IsValid())
	{
		return;
	}

	GuardRollTimer -= DeltaTime;
	if (GuardRollTimer <= 0.f)
	{
		GuardRollTimer = FMath::FRandRange(0.35f, 0.9f);
		GuardRoll = FMath::FRand();
	}

	// Only worth guarding against something actually coming.
	const bool bThreat = Opponent->State == EFighterState::Attack
		&& Distance < Style->PreferredRange * 2.f;

	const bool bAdvancing = Distance > Style->PreferredRange * 1.1f;
	if (bAdvancing && !Style->bGuardsWhileAdvancing)
	{
		Fighter->bBlocking = false;
		return;
	}
	Fighter->bBlocking = bThreat && GuardRoll < Style->GuardChance;
}

/* ------------------------------------------------------------- reactions */

/**
 * A swing ends whether or not it touched anybody, and the difference has to
 * cost something. Without this an AI that misses simply throws again, which
 * is how a fight becomes noise.
 */
void UFightStyleComponent::TickSwingResult()
{
	const AFighterBase* Fighter = GetFighter();
	if (!Fighter)
	{
		return;
	}
	const bool bAttacking = Fighter->State == EFighterState::Attack;
	if (bWasAttacking && !bAttacking && bSwingPending)
	{
		NotifyWhiffed();
	}
	bWasAttacking = bAttacking;
}

void UFightStyleComponent::HandleDamaged(float NewHealth, const FHitResultData& Hit)
{
	if (!Style)
	{
		return;
	}
	// Answering back is a decision, not a reflex: a style with a low counter
	// chance resets instead, and that is what makes it feel like it respects
	// the player rather than trading blindly.
	ComboRemaining = 0;
	bSwingPending = false;			// interrupted, not missed

	if (FMath::FRand() < Style->CounterChance)
	{
		AttackCooldown = 0.f;		// fire the moment the stun ends
	}
	else
	{
		AttackCooldown = FMath::Max(AttackCooldown, Style->AttackInterval * 0.6f / FMath::Max(0.1f, Haste));
		ResetRemaining = Style->ResetDistance > 0.f ? 0.8f : 0.f;
	}
}

void UFightStyleComponent::NotifyHitLanded()
{
	bSwingPending = false;
	// Landing one is what earns the rest of the combination -- but a style
	// that hits and resets stops here instead.
	if (Style && Style->ResetDistance > 0.f && ComboRemaining <= 0)
	{
		ResetRemaining = FMath::FRandRange(0.6f, 1.f);
	}
}

void UFightStyleComponent::NotifyWhiffed()
{
	bSwingPending = false;
	// A whiff costs the combination and a beat of hesitation.
	ComboRemaining = 0;
	if (Style)
	{
		AttackCooldown = FMath::Max(AttackCooldown, Style->AttackInterval * 0.75f / FMath::Max(0.1f, Haste));
	}
}
