#include "Combat/FightStyleComponent.h"
#include "Combat/SaudArena.h"
#include "Combat/SaudBrain.h"

#include "Combat/EnemyFighter.h"
#include "Combat/FighterBase.h"
#include "EngineUtils.h"
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
	SlipRemaining  = FMath::Max(0.f, SlipRemaining  - DeltaTime);

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
	// Flat, between centres. It was |To.X| until 2026-09-24 -- the strip's
	// own measure, which put a man standing due north of the player at
	// distance zero, in the Close band, throwing knees at nobody.
	const float Distance = SaudArena::Flat(To);

	Band = Style->BandFor(Distance);
	Fighter->FaceTowards(Them);

	TickRead(DeltaTime, To, Distance);
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
		// The nearest, flat. It scored |X| + 2|Y| -- depth counting double,
		// which was a corridor's idea of "in front".
		const float Score = SaudArena::Flat(T->GetActorLocation() - Origin);
		if (Score < Best)
		{
			Best = Score;
			Nearest = T;
		}
	}
	Opponent = Nearest;
}

/**
 * The read.
 *
 * Everything this can see of him is public on the fighter -- state, guard,
 * facing, the attack he is in and how far into it -- and SaudBrain::Read
 * turns it into one intent. The rolls it decides on are the defence roll
 * the browser's guard already used and an offence roll beside it, both
 * re-rolled a few times a second in TickDefence, so a decision holds for
 * a beat instead of flickering.
 */
void UFightStyleComponent::TickRead(float DeltaTime, const FVector& To, float Distance)
{
	AFighterBase* Fighter = GetFighter();
	if (!Fighter || !Opponent.IsValid())
	{
		Intent = SaudBrain::EIntent::Free;
		return;
	}
	const AFighterBase* Him = Opponent.Get();
	const FVector Self = Fighter->GetActorLocation();
	const FVector HimToMe = -To;

	SaudBrain::FSeen S;
	S.State = static_cast<int>(Him->State);
	S.bBlocking = Him->bBlocking;
	S.bFacingMe = SaudArena::Covers(Him->GetFacing(), HimToMe);
	S.Distance = Distance;
	if (Him->State == EFighterState::Attack)
	{
		if (const FAttackDef* A = Him->GetCurrentAttack())
		{
			S.bAttacking = true;
			S.Elapsed = Him->GetAttackElapsed();
			S.Startup = A->Startup;
			S.Active = A->Active;
			S.Recovery = A->Recovery;
			S.bInHisLine = SaudArena::InHitbox(Him->GetActorLocation(), Him->GetFacing(), Self,
			                                   A->Reach, A->DepthTolerance);
		}
	}
	if (!S.bAttacking)
	{
		bSlippedThisSwing = false;      // his next swing may be stepped off again
	}

	// The quickest thing legal from here, and its reach: what a window is
	// measured against.
	FastestRow = NAME_None;
	FastestStartup = 0.f;
	FastestReach = 0.f;
	bool bCanReach = false;
	auto Consider = [&](const FStyleStrike& K)
	{
		if (K.AttackRow.IsNone() || K.Weight <= 0.f || !K.Bands.Contains(Band))
		{
			return;
		}
		const FAttackDef* Def = Fighter->GetAttackDef(K.AttackRow);
		if (!Def)
		{
			return;
		}
		if (!bCanReach || Def->Startup < FastestStartup)
		{
			FastestRow = K.AttackRow;
			FastestStartup = Def->Startup;
			FastestReach = Def->Reach;
		}
		bCanReach = true;
	};
	for (const FStyleStrike& K : Style->Strikes) { Consider(K); }
	for (const FStyleStrike& K : ExtraStrikes)   { Consider(K); }

	SaudBrain::FReadDials Dials;
	Dials.ReactionSeconds = Style->ReactionSeconds;
	Dials.GuardChance = Style->GuardChance;
	Dials.SlipShare = Style->SlipShare;
	Dials.PunishChance = Style->PunishChance;
	Dials.GuardRespect = Style->GuardRespect;

	Intent = SaudBrain::Read(S, Dials, GuardRoll, OffenceRoll, FastestStartup, FastestReach, bCanReach, BlockedInARow);

	// A slip is one step, once per swing of his; after it the read falls
	// back to the guard, which is what the roll would have given anyway.
	if (Intent == SaudBrain::EIntent::Slip)
	{
		if (bSlippedThisSwing)
		{
			Intent = SaudBrain::EIntent::Guard;
		}
		else
		{
			bSlippedThisSwing = true;
			SlipRemaining = SaudBrain::SlipSeconds;
			SlipDirection = SaudBrain::SlipDirection(Him->GetFacing(), HimToMe);
		}
	}
}

/**
 * Footwork.
 *
 * Layered: hold the style's distance, circle rather than walk straight in,
 * bounce in and out if the style bounces -- and, in a crowd, steer to the
 * place the director gave this one round the player, step off a teammate's
 * line, and go round a guard the read says to go round. A slip in progress
 * is the whole of the footwork for its 0.2 s.
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

	// Stepping off his line: nothing else moves the feet until it is done.
	if (SlipRemaining > 0.f && !SlipDirection.IsNearlyZero())
	{
		Fighter->AddMovementInput(SlipDirection, 1.f);
		Fighter->State = EFighterState::Walk;
		return;
	}

	// Towards the opponent, and across that line. On the strip these were
	// the sign of X and the world's Y — footwork that only worked because
	// every fight happened along one axis.
	const FVector Towards = SaudArena::Direction(FVector::ZeroVector, To,
	                                              Fighter->GetFacing());
	const FVector Across(-Towards.Y, Towards.X, 0.f);

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
	// Waiting him out -- his dash, his knockdown -- is done a step further
	// back than the fighting distance, out of the swing he stands up into.
	if (Intent == SaudBrain::EIntent::Wait)
	{
		Wanted *= 1.35f;
	}
	const AEnemyFighter* Enemy = Cast<AEnemyFighter>(Fighter);
	if (Enemy && Enemy->bHasCrowdRole)
	{
		Wanted += Enemy->CrowdRoleLane;
	}

	// 2. Close or back off, scaled by how much this style cares. A pressure
	//    fighter barely corrects; a range fighter corrects constantly.
	const float Error = Distance - Wanted;
	const float Urgency = FMath::Lerp(0.35f, 1.f, Style->RangeDiscipline);
	float Forward = 0.f;
	if (FMath::Abs(Error) > 18.f)
	{
		Forward = FMath::Clamp(Error / 120.f, -1.f, 1.f) * Urgency;
	}

	// 3. Circling: around him, at whatever angle the two of them are at.
	CircleTimer -= DeltaTime;
	if (CircleTimer <= 0.f)
	{
		CircleTimer = Style->CircleSwitchTime * FMath::FRandRange(0.6f, 1.5f);
		CircleDirection = FMath::RandBool() ? 1.f : -1.f;
	}
	// Circling is around him now, not along a depth band. On the strip there
	// was a line to get back onto and two walls to avoid; in the open the
	// only thing to stay off is the other fighters, which the enemy's own
	// approach handles, so this is the tendency and nothing else.
	float Sideways = Style->CircleTendency * CircleDirection;

	// 4. The crowd, and the guard. A role is a bearing off HIS facing; the
	//    steer is how hard to go round him to reach it, and RoundHim is
	//    which way round raises the bearing. A guard facing this fighter
	//    wants the same thing with the bearing at his back, harder.
	const FVector Self = Fighter->GetActorLocation();
	const FVector Them = Self + To;
	const FVector Round = SaudBrain::RoundHim(Them, Self);
	float RoundStep = 0.f;
	if (Intent == SaudBrain::EIntent::Flank && Opponent.IsValid())
	{
		const float Now = SaudBrain::BearingOf(Them, Opponent->GetFacing(), Self);
		// The nearer side of his back, so the way round is the short one.
		RoundStep = SaudBrain::RoleSteer(Now, Now >= 0.f ? 150.f : -150.f);
		Sideways = 0.f;
	}
	else if (Enemy && Enemy->bHasCrowdRole && Opponent.IsValid())
	{
		const float Now = SaudBrain::BearingOf(Them, Opponent->GetFacing(), Self);
		const float Steer = SaudBrain::RoleSteer(Now, Enemy->CrowdRoleBearing);
		if (Steer != 0.f)
		{
			RoundStep = Steer * FMath::Max(0.45f, Style->CircleTendency);
			Sideways = 0.f;                 // the role's way round, not a coin's
		}
	}

	// 5. A teammate on the line to him: step off it, this frame.
	FVector Clear = FVector::ZeroVector;
	if (Enemy)
	{
		for (TActorIterator<AEnemyFighter> It(GetWorld()); It; ++It)
		{
			const AEnemyFighter* Other = *It;
			if (Other == Enemy || !IsValid(Other) || !Other->IsAlive()) { continue; }
			if (SaudBrain::LineBlocked(Self, Them, Other->GetActorLocation(), SaudGameplay::CrowdLineWidth))
			{
				Clear = SaudBrain::ClearLineStep(Self, Them, Other->GetActorLocation());
				break;
			}
		}
	}

	// Guarding halves the pace, the way it does for a person.
	const float Scale = Fighter->bBlocking ? 0.45f : 1.f;
	// Summed into one call: two calls are two sweeps, and the second starts
	// where the first left off, which quietly makes a circling step faster
	// than a straight one.
	const FVector Step = Towards * Forward + Across * Sideways + Round * RoundStep + Clear * 0.8f;
	if (!Step.IsNearlyZero())
	{
		Fighter->AddMovementInput(Step.GetSafeNormal2D(), FMath::Min(1.f, Step.Size2D()) * Scale);
	}

	Fighter->State = Step.IsNearlyZero() ? EFighterState::Idle : EFighterState::Walk;
}

/**
 * Offence.
 *
 * Range decides what is available; the style's weights decide which of those.
 * If nothing is legal at this distance the fighter throws nothing and keeps
 * walking, which separates a boxer from a kickboxer far more than any damage
 * number does. The read overrides the rhythm: a window is taken at once
 * with the fastest thing that fits it, and a guard, a dash or a knockdown
 * is not swung at.
 */
void UFightStyleComponent::TickOffence()
{
	switch (Intent)
	{
	case SaudBrain::EIntent::Guard:
	case SaudBrain::EIntent::Slip:
	case SaudBrain::EIntent::Wait:
	case SaudBrain::EIntent::Flank:
		return;                     // not the moment, or not from here
	default:
		break;
	}
	const bool bWindow = Intent == SaudBrain::EIntent::Punish || Intent == SaudBrain::EIntent::Press;
	if (!bWindow && (AttackCooldown > 0.f || Band == ERangeBand::Out))
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

	// The crowd rule: only a couple may be swinging at once, the rest circle
	// -- and only from a place a swing can be thrown (the director's say).
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

	// A punish is the fastest strike that fits the window, not the style's
	// favourite; the read already checked it fits.
	const FStyleStrike* Strike = nullptr;
	FStyleStrike Fast;
	if (Intent == SaudBrain::EIntent::Punish && !FastestRow.IsNone())
	{
		Fast.AttackRow = FastestRow;
		Fast.Bands = { Band };
		Fast.Weight = 1.f;
		Strike = &Fast;
	}
	else
	{
		Strike = Style->ChooseStrike(Band, ExtraStrikes);
	}
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

	// Openers start combinations; finishers stand alone. A punish opens one
	// as its strike would: landing it is what earns the rest.
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
 * like a bug and plays like one. Whether to guard is the read's answer:
 * the browser's roll against the style's guard chance, while something is
 * coming this way, less the share that is a step off the line instead.
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
		OffenceRoll = FMath::FRand();
	}

	const bool bAdvancing = Distance > Style->PreferredRange * 1.1f;
	if (bAdvancing && !Style->bGuardsWhileAdvancing)
	{
		Fighter->bBlocking = false;
		return;
	}
	Fighter->bBlocking = Intent == SaudBrain::EIntent::Guard;
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
	BlockedInARow = 0;				// it got through: the guard is not a wall after all
	// Landing one is what earns the rest of the combination -- but a style
	// that hits and resets stops here instead.
	if (Style && Style->ResetDistance > 0.f && ComboRemaining <= 0)
	{
		ResetRemaining = FMath::FRandRange(0.6f, 1.f);
	}
}

void UFightStyleComponent::NotifyBlocked()
{
	bSwingPending = false;
	++BlockedInARow;
	// A guard that stopped it ends the combination: the rest would go into
	// the same guard.
	ComboRemaining = 0;
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
