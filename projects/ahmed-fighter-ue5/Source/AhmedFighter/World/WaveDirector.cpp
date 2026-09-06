#include "World/WaveDirector.h"

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
	for (TActorIterator<AWaveDirector> It(World); It; ++It)
	{
		return *It;
	}
	return nullptr;
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

	if (!Player->IsAlive())
	{
		bFinished = true;
		OnStageFailed.Broadcast();
		return;
	}

	// Trigger the next wave once the player walks far enough in.
	if (!bArenaLocked && WaveIndex < Waves.Num())
	{
		const FWaveDef& Next = Waves[WaveIndex];
		if (Next.TriggerDistance < 0.f || Player->GetActorLocation().X > Next.TriggerDistance)
		{
			BeginWave(Next);
		}
	}

	// Wave cleared?
	if (bArenaLocked && CountLivingEnemies() == 0)
	{
		bArenaLocked = false;
		AttackTokenHolders.Reset();
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
		&& Player->GetActorLocation().X >= Stage->Length - 360.f)
	{
		bFinished = true;
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
	ArenaOriginX = Player->GetActorLocation().X - 400.f;
	ApplyArenaBounds();

	const int32 Tier = (Wave.TierOverride >= 0) ? Wave.TierOverride : Stage->Tier;
	for (int32 i = 0; i < Wave.Fighters.Num(); ++i)
	{
		SpawnFighter(Wave.Fighters[i], Tier, i, Wave.Fighters.Num());
	}

	OnWaveStarted.Broadcast(WaveIndex);
}

void AWaveDirector::ApplyArenaBounds()
{
	const float MinX = bArenaLocked ? ArenaOriginX : 0.f;
	const float MaxX = bArenaLocked ? ArenaOriginX + AhmedGameplay::ArenaWidth
									: (Stage ? Stage->Length : 100000.f);

	if (AAhmedCharacter* Player = Cast<AAhmedCharacter>(UGameplayStatics::GetPlayerPawn(GetWorld(), 0)))
	{
		Player->SetArenaBounds(MinX, MaxX);
	}
	for (AEnemyFighter* E : LiveEnemies)
	{
		if (IsValid(E))
		{
			E->SetArenaBounds(MinX, MaxX);
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

	// Alternate the side they walk in from so waves surround rather than queue.
	const bool bFromRight = (IndexInWave % 3) != 2;
	const float SpawnX = bFromRight
		? ArenaOriginX + AhmedGameplay::ArenaWidth + 200.f + IndexInWave * 90.f
		: ArenaOriginX - 200.f - IndexInWave * 70.f;
	const float SpawnY = FMath::FRandRange(AhmedGameplay::DepthMin * 0.8f, AhmedGameplay::DepthMax * 0.8f);

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;

	AEnemyFighter* Enemy = GetWorld()->SpawnActor<AEnemyFighter>(
		PawnClass, FVector(SpawnX, SpawnY, GetActorLocation().Z), FRotator::ZeroRotator, Params);
	if (!Enemy)
	{
		return;
	}

	const UAhmedGameInstance* GI = GetWorld()->GetGameInstance<UAhmedGameInstance>();
	const FDifficultyDef Diff = GI ? GI->GetDifficulty() : FDifficultyDef();

	Enemy->AttackTable = AttackTable;
	Enemy->ConfigureFromDefinition(*Def, Tier, Diff.EnemyHealth, Diff.EnemyDamage);
	Enemy->FlankSide   = (IndexInWave % 2 == 0) ? 1.f : -1.f;
	Enemy->LaneOffset  = (IndexInWave / 2) * 60.f;
	Enemy->DepthOffset = FMath::FRandRange(-190.f, 190.f);
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
