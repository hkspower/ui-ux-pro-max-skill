#include "World/WaveDirector.h"
#include "Combat/AhmedArena.h"
#include "Game/AhmedAudioSubsystem.h"

#include "Combat/AhmedCharacter.h"
#include "Combat/EnemyFighter.h"
#include "Engine/DataTable.h"
#include "EngineUtils.h"
#include "Game/AhmedGameInstance.h"
#include "Kismet/GameplayStatics.h"

AWaveDirector::AWaveDirector()
{
	PrimaryActorTick.bCanEverTick = true;
}

AWaveDirector* AWaveDirector::Get(const UWorld* World)
{
	if (!World)
	{
		return nullptr;
	}
	const APawn* Player = UGameplayStatics::GetPlayerPawn(World, 0);
	const FVector Where = Player ? Player->GetActorLocation() : FVector::ZeroVector;

	AWaveDirector* Nearest = nullptr;
	float NearestDist = FLT_MAX;
	for (TActorIterator<AWaveDirector> It(World); It; ++It)
	{
		if (Player && It->Contains(Where))
		{
			return *It;
		}
		const float Dist = FVector::DistSquared(It->GetActorLocation(), Where);
		if (Dist < NearestDist)
		{
			Nearest = *It;
			NearestDist = Dist;
		}
	}
	return Nearest;
}

void AWaveDirector::GetAll(const UWorld* World, TArray<AWaveDirector*>& Out)
{
	Out.Reset();
	if (!World)
	{
		return;
	}
	for (TActorIterator<AWaveDirector> It(World); It; ++It)
	{
		Out.Add(*It);
	}
}

float AWaveDirector::GetStageLength() const
{
	return Stage ? Stage->Length : 0.f;
}

bool AWaveDirector::Contains(const FVector& WorldLocation) const
{
	// A district is a round place, not a strip with two ends. The margin is
	// the doorway: an exit sits just inside the rim and the arriving step
	// lands a little past it, and both are still ours.
	constexpr float Margin = 400.f;
	const float Length = Stage ? Stage->Length : 100000.f;
	return AhmedArena::InCircle(WorldLocation, GetActorLocation(), Length + Margin);
}

void AWaveDirector::BeginPlay()
{
	Super::BeginPlay();

	if (StageTable && !StageRow.IsNone())
	{
		static const FString Context(TEXT("AWaveDirector::BeginPlay"));
		Stage = StageTable->FindRow<FStageDef>(StageRow, Context, false);
	}
	if (!Stage)
	{
		UE_LOG(LogTemp, Error, TEXT("[Ahmed] WaveDirector has no stage row '%s'"), *StageRow.ToString());
		return;
	}

	Waves = Stage->Waves;
	if (Stage->bSurvival && Waves.Num() == 0)
	{
		Waves.Add(MakeSurvivalWave(1));
	}
}

int32 AWaveDirector::CountLivingEnemies() const
{
	int32 Count = 0;
	for (const AEnemyFighter* E : LiveEnemies)
	{
		if (IsValid(E) && E->IsAlive())
		{
			++Count;
		}
	}
	return Count;
}

void AWaveDirector::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!Stage || bFinished)
	{
		return;
	}
	ElapsedTime += DeltaSeconds;

	AAhmedCharacter* Player = Cast<AAhmedCharacter>(UGameplayStatics::GetPlayerPawn(GetWorld(), 0));
	if (!Player)
	{
		return;
	}

	// Another district's fight is not this director's business.
	if (!Contains(Player->GetActorLocation()))
	{
		return;
	}

	if (!Player->IsAlive())
	{
		bFinished = true;
		if (UAhmedAudioSubsystem* Audio = UAhmedAudioSubsystem::Get(this)) { Audio->PlayUI(TEXT("Stage_Fail")); }
		OnStageFailed.Broadcast();
		return;
	}

	// Trigger the next wave once the player walks far enough in.
	if (!bArenaLocked && WaveIndex < Waves.Num())
	{
		const FWaveDef& Next = Waves[WaveIndex];
		if (Next.TriggerDistance < 0.f || LocalX(Player->GetActorLocation()) > Next.TriggerDistance)
		{
			BeginWave(Next);
		}
	}

	// Wave cleared?
	if (bArenaLocked && CountLivingEnemies() == 0)
	{
		bArenaLocked = false;
		AttackTokenHolders.Reset();
		if (UAhmedAudioSubsystem* Audio = UAhmedAudioSubsystem::Get(this)) { Audio->PlayUI(TEXT("Wave_Clear")); }
		OnWaveCleared.Broadcast(WaveIndex);
		++WaveIndex;

		if (Stage->bSurvival)
		{
			++SurvivalWave;
			Waves.Add(MakeSurvivalWave(SurvivalWave));
			if (UAhmedGameInstance* GI = GetWorld()->GetGameInstance<UAhmedGameInstance>())
			{
				GI->RecordSurvivalWave(SurvivalWave);
			}
		}
		ApplyArenaBounds();
	}

	// Stage cleared once every wave is down and the exit is reached.
	if (!Stage->bSurvival
		&& WaveIndex >= Waves.Num()
		&& LocalX(Player->GetActorLocation()) >= Stage->Length - 360.f)
	{
		bFinished = true;
		if (UAhmedAudioSubsystem* Audio = UAhmedAudioSubsystem::Get(this)) { Audio->PlayUI(TEXT("Stage_Clear")); }
		OnStageCleared.Broadcast();
	}
}

void AWaveDirector::BeginWave(const FWaveDef& Wave)
{
	AAhmedCharacter* Player = Cast<AAhmedCharacter>(UGameplayStatics::GetPlayerPawn(GetWorld(), 0));
	if (!Player)
	{
		return;
	}

	bArenaLocked = true;
	// The fight happens where he is standing when it starts, not at an offset
	// back down the corridor from him.
	ArenaCentre = FVector(Player->GetActorLocation().X, Player->GetActorLocation().Y,
	                      GetActorLocation().Z);
	ApplyArenaBounds();

	const int32 Tier = (Wave.TierOverride >= 0) ? Wave.TierOverride : Stage->Tier;
	for (int32 i = 0; i < Wave.Fighters.Num(); ++i)
	{
		SpawnFighter(Wave.Fighters[i], Tier, i, Wave.Fighters.Num());
	}

	if (UAhmedAudioSubsystem* Audio = UAhmedAudioSubsystem::Get(this)) { Audio->PlayUI(TEXT("Wave_Start")); }
	OnWaveStarted.Broadcast(WaveIndex);
}

void AWaveDirector::ApplyArenaBounds()
{
	// A locked fight is a circle around where the wave woke. Unlocked, the
	// district is the whole of it, which is a circle big enough to hold the
	// stage rather than a pair of ends on X.
	const FVector Centre = bArenaLocked ? ArenaCentre : GetActorLocation();
	const float Radius = bArenaLocked
		? AhmedGameplay::ArenaRadius
		: (Stage ? Stage->Length : 100000.f);

	if (AAhmedCharacter* Player = Cast<AAhmedCharacter>(UGameplayStatics::GetPlayerPawn(GetWorld(), 0)))
	{
		Player->SetArenaCircle(Centre, Radius);
	}
	for (AEnemyFighter* E : LiveEnemies)
	{
		if (IsValid(E))
		{
			E->SetArenaCircle(Centre, Radius);
		}
	}
}

void AWaveDirector::SpawnFighter(FName Row, int32 Tier, int32 IndexInWave, int32 WaveSize)
{
	if (!FighterTable)
	{
		return;
	}
	static const FString Context(TEXT("AWaveDirector::SpawnFighter"));
	const FFighterDef* Def = FighterTable->FindRow<FFighterDef>(Row, Context, false);
	if (!Def)
	{
		UE_LOG(LogTemp, Warning, TEXT("[Ahmed] Unknown fighter row '%s'"), *Row.ToString());
		return;
	}

	UClass* PawnClass = Def->PawnClass.IsNull() ? DefaultEnemyClass.Get() : Def->PawnClass.LoadSynchronous();
	if (!PawnClass)
	{
		UE_LOG(LogTemp, Warning, TEXT("[Ahmed] No pawn class for fighter '%s'"), *Row.ToString());
		return;
	}

	// In from around the ring rather than from one of two ends: a wave that
	// can only arrive from east and west is a wave in a corridor. Spread by
	// index so six of them do not walk in shoulder to shoulder, and jittered
	// so it is not a parade.
	const float Angle = (WaveSize > 0 ? (IndexInWave / (float)WaveSize) : 0.f) * 360.f
	                  + FMath::FRandRange(-18.f, 18.f);
	const float Radians = FMath::DegreesToRadians(Angle);
	const FVector Spawn = ArenaCentre
		+ FVector(FMath::Cos(Radians), FMath::Sin(Radians), 0.f) * AhmedGameplay::SpawnRing;

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;

	AEnemyFighter* Enemy = GetWorld()->SpawnActor<AEnemyFighter>(
		PawnClass, FVector(Spawn.X, Spawn.Y, GetActorLocation().Z), FRotator::ZeroRotator, Params);
	if (!Enemy)
	{
		return;
	}

	const UAhmedGameInstance* GI = GetWorld()->GetGameInstance<UAhmedGameInstance>();
	const FDifficultyDef Diff = GI ? GI->GetDifficulty() : FDifficultyDef();

	Enemy->AttackTable = AttackTable;
	Enemy->ConfigureFromDefinition(*Def, Tier, Diff.EnemyHealth, Diff.EnemyDamage);
	// The slot it holds in the crowd, so a wave spreads round him instead of
	// piling onto one spot. The numbers used to be here, ad hoc.
	AhmedArena::CrowdSlot(IndexInWave, Enemy->CrowdBearing, Enemy->LaneOffset);
	Enemy->OnDefeated.AddDynamic(this, &AWaveDirector::HandleEnemyDefeated);

	LiveEnemies.Add(Enemy);
	ApplyArenaBounds();
}

void AWaveDirector::HandleEnemyDefeated(AFighterBase* Fighter)
{
	AEnemyFighter* Enemy = Cast<AEnemyFighter>(Fighter);
	if (!Enemy)
	{
		return;
	}
	ReleaseAttackToken(Enemy);
	++EnemiesDefeated;
	ExperienceEarned += Enemy->ExperienceValue;

	if (UAhmedGameInstance* GI = GetWorld()->GetGameInstance<UAhmedGameInstance>())
	{
		GI->AddExperience(Enemy->ExperienceValue);
	}
}

bool AWaveDirector::TryClaimAttackToken(AEnemyFighter* Claimant)
{
	AttackTokenHolders.RemoveAll([](const AEnemyFighter* E)
	{
		return !IsValid(E) || !E->IsAlive() || E->State != EFighterState::Attack;
	});

	if (AttackTokenHolders.Contains(Claimant))
	{
		return true;
	}
	if (AttackTokenHolders.Num() >= AhmedGameplay::MaxSimultaneousAttackers)
	{
		return false;
	}
	AttackTokenHolders.Add(Claimant);
	return true;
}

void AWaveDirector::ReleaseAttackToken(AEnemyFighter* Claimant)
{
	AttackTokenHolders.Remove(Claimant);
}

FWaveDef AWaveDirector::MakeSurvivalWave(int32 WaveNumber) const
{
	FWaveDef Wave;
	Wave.TriggerDistance = -1.f;					// endless waves start immediately
	Wave.TierOverride = WaveNumber / 2;

	TArray<FName> Pool = { TEXT("Thug"), TEXT("Brawler") };
	if (WaveNumber >= 2)  Pool.Add(TEXT("Runner"));
	if (WaveNumber >= 3)  Pool.Add(TEXT("Kickboxer"));
	if (WaveNumber >= 5)  Pool.Add(TEXT("Grappler"));
	if (WaveNumber >= 6)  Pool.Add(TEXT("Bouncer"));
	if (WaveNumber >= 7)  Pool.Add(TEXT("Enforcer"));
	if (WaveNumber >= 9)  Pool.Add(TEXT("Contender"));

	const int32 Count = FMath::Min(6, 2 + WaveNumber / 2);
	for (int32 i = 0; i < Count; ++i)
	{
		Wave.Fighters.Add(Pool[FMath::RandRange(0, Pool.Num() - 1)]);
	}
	// A boss every fifth wave, the big one every tenth.
	if (WaveNumber % 10 == 0)     Wave.Fighters.Add(TEXT("AlWahsh"));
	else if (WaveNumber % 5 == 0) Wave.Fighters.Add(TEXT("AlSaqr"));

	return Wave;
}
