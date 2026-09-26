#include "Game/SaudLookSubsystem.h"
#include "Combat/FighterBase.h"
#include "Combat/SaudCharacter.h"
#include "Combat/SaudTypes.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetMaterialLibrary.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialParameterCollection.h"
#include "Misc/App.h"

USaudLookSubsystem* USaudLookSubsystem::Get(const UObject* WorldContext)
{
	const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	return World ? World->GetSubsystem<USaudLookSubsystem>() : nullptr;
}

bool USaudLookSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId USaudLookSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(USaudLookSubsystem, STATGROUP_Tickables);
}

void USaudLookSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	Look = SaudAnime::FState();

	Collection = LoadObject<UMaterialParameterCollection>(nullptr, SaudAnime::CollectionPath,
	                                                     nullptr, LOAD_NoWarn | LOAD_Quiet);
	UMaterialInterface* Post = LoadObject<UMaterialInterface>(nullptr, SaudAnime::PostMaterialPath,
	                                                          nullptr, LOAD_NoWarn | LOAD_Quiet);
	UMaterialInterface* Frame = LoadObject<UMaterialInterface>(nullptr, SaudAnime::FrameMaterialPath,
	                                                           nullptr, LOAD_NoWarn | LOAD_Quiet);
	if (!Post || !Frame || !Collection)
	{
		// Loaded by path, so a packaged build carries them only because
		// DefaultGame.ini cooks /Game/Materials/Anime always.
		UE_LOG(LogTemp, Warning, TEXT("Anime look not built (%s): run Tools/look/anime_look.py in the editor."),
		       SaudAnime::CollectionPath);
		Collection = nullptr;
		return;
	}

	FActorSpawnParameters Params;
	Params.ObjectFlags |= RF_Transient;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	Volume = InWorld.SpawnActor<APostProcessVolume>(Params);
	if (Volume)
	{
		// Unbound: the whole world, whatever camera looks at it. Priority
		// over a level's own volumes, so a level's exposure and grade still
		// apply underneath and the ink is laid over them.
		Volume->bUnbound = true;
		Volume->Priority = 10.f;
		Volume->BlendWeight = 1.f;
		Volume->Settings.AddBlendable(Post, 1.f);
		Volume->Settings.AddBlendable(Frame, 1.f);
	}
}

void USaudLookSubsystem::Deinitialize()
{
	// The volume is transient and goes with its world; destroy it only
	// while that world is still standing.
	if (IsValid(Volume) && Volume->GetWorld() && !Volume->GetWorld()->bIsTearingDown)
	{
		Volume->Destroy();
	}
	Volume = nullptr;
	Super::Deinitialize();
}

void USaudLookSubsystem::OnBlow(const AFighterBase* InVictim, const FHitResultData& Hit, bool bHeavy)
{
	const SaudAnime::FBlowLook L = SaudAnime::ForBlow(bHeavy, Hit.bBlocked, Hit.bParried, Hit.bKnockdown);
	if (L.Impact.Seconds <= 0.f && L.SpeedSeconds <= 0.f)
	{
		return;
	}
	Look.Add(L);
	Victim = InVictim;
}

void USaudLookSubsystem::OnBurn(const AFighterBase* InVictim)
{
	Burned = InVictim;
}

void USaudLookSubsystem::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
	if (!Collection)
	{
		return;
	}
	// The world's clock is all but stopped during a freeze; the picture's is
	// not. Real time, as USaudFeelSubsystem does.
	Look.Tick(FMath::Clamp(static_cast<float>(FApp::GetDeltaTime()), 0.f, 0.1f));

	Write(0, SaudAnime::Param::Impact, Look.ImpactValue());
	Write(1, SaudAnime::Param::ImpactInvert, Look.InvertValue());

	float Speed = Look.SpeedValue();
	float X = 0.5f, Y = 0.5f;
	if (Speed > 0.f && !VictimOnScreen(X, Y))
	{
		// Lines round a point off the screen would streak the whole picture
		// from one edge; off screen, they are simply not drawn.
		Speed = 0.f;
	}
	Write(2, SaudAnime::Param::Speed, Speed);
	if (Speed > 0.f)
	{
		UKismetMaterialLibrary::SetScalarParameterValue(this, Collection, SaudAnime::Param::SpeedCentreX, X);
		UKismetMaterialLibrary::SetScalarParameterValue(this, Collection, SaudAnime::Param::SpeedCentreY, Y);
		Write(3, SaudAnime::Param::SpeedSeed, Look.Seed());
	}

	// HAWK FIST: the flame on the player's fist and the burst on the man
	// his burning punch hit.
	const APlayerController* PC = UGameplayStatics::GetPlayerController(GetWorld(), 0);
	WriteFire(PC ? Cast<ASaudCharacter>(PC->GetPawn()) : nullptr);
}

void USaudLookSubsystem::WriteFire(const ASaudCharacter* Saud)
{
	float Heat = Saud ? Saud->GetHawkHeat() : 0.f;
	float X = 0.f, Y = 0.f, Depth = 0.f, Scale = 0.f;
	if (Heat > 0.f)
	{
		FName Hand, Forearm;
		Saud->GetFlameBones(Hand, Forearm);
		const USkeletalMeshComponent* Body = Saud->GetMesh();
		float EX = 0.f, EY = 0.f, EDepth = 0.f, EScale = 0.f;
		if (!Body || !Project(Body->GetSocketLocation(Hand), X, Y, Depth, Scale)
		    || !Project(Body->GetSocketLocation(Forearm), EX, EY, EDepth, EScale))
		{
			Heat = 0.f;      // a fist off the screen has no flame on it
		}
		else
		{
			// The flame runs along the forearm, elbow to fist, on the screen.
			int32 W = 0, H = 0;
			UGameplayStatics::GetPlayerController(GetWorld(), 0)->GetViewportSize(W, H);
			const float Aspect = H > 0 ? static_cast<float>(W) / static_cast<float>(H) : 1.f;
			float DX = (X - EX) * Aspect, DY = Y - EY;
			const float Len = FMath::Sqrt(DX * DX + DY * DY);
			if (Len < 1e-4f)
			{
				DX = 0.f; DY = -1.f;   // the forearm seen end-on: the flame stands up
			}
			else
			{
				DX /= Len; DY /= Len;
			}
			Set(SaudFire::Param::FireX, X);
			Set(SaudFire::Param::FireY, Y);
			Set(SaudFire::Param::FireDirX, DX);
			Set(SaudFire::Param::FireDirY, DY);
			Set(SaudFire::Param::FireDepth, Depth);
			Set(SaudFire::Param::FireScale, Scale);
			Set(SaudFire::Param::FireTime, Saud->GetFire().Clock);
		}
	}
	Write(4, SaudFire::Param::FireHeat, Heat);

	float Age = -1.f;
	const AFighterBase* V = Burned.Get();
	if (Saud && V && Saud->GetFire().Bursting())
	{
		// At the burst's height up the man: half his figure, the actor's
		// own location (SaudFire::BurstUpPx).
		float BX = 0.f, BY = 0.f, BDepth = 0.f, BScale = 0.f;
		if (Project(V->GetActorLocation(), BX, BY, BDepth, BScale))
		{
			Age = Saud->GetFire().BurstAge;
			Set(SaudFire::Param::BurnX, BX);
			Set(SaudFire::Param::BurnY, BY);
			Set(SaudFire::Param::BurnDepth, BDepth);
			Set(SaudFire::Param::BurnScale, BScale);
			Set(SaudFire::Param::BurnSeed, Saud->GetFire().BurstSeed);
		}
	}
	Write(5, SaudFire::Param::BurnAge, Age);
}

bool USaudLookSubsystem::Project(const FVector& At, float& OutX, float& OutY, float& OutDepth, float& OutScale) const
{
	const APlayerController* PC = UGameplayStatics::GetPlayerController(GetWorld(), 0);
	if (!PC || !PC->PlayerCameraManager)
	{
		return false;
	}
	int32 W = 0, H = 0;
	PC->GetViewportSize(W, H);
	FVector2D Screen, Up;
	// One figure pixel straight up in the world, projected beside the
	// point: how big the browser's pixel is at this distance.
	const FVector Rise(0.f, 0.f, SaudFire::CmPerFigurePx);
	if (W <= 0 || H <= 0 || !PC->ProjectWorldLocationToScreen(At, Screen, true)
	    || !PC->ProjectWorldLocationToScreen(At + Rise, Up, true))
	{
		return false;
	}
	OutX = static_cast<float>(Screen.X) / static_cast<float>(W);
	OutY = static_cast<float>(Screen.Y) / static_cast<float>(H);
	OutScale = static_cast<float>(FVector2D::Distance(Screen, Up)) / static_cast<float>(H);
	// Scene depth is along the camera's own axis, not the distance.
	const FVector CamAt = PC->PlayerCameraManager->GetCameraLocation();
	const FVector CamFwd = PC->PlayerCameraManager->GetCameraRotation().Vector();
	OutDepth = static_cast<float>(FVector::DotProduct(At - CamAt, CamFwd));
	// A little off the edge still counts: a flame on a fist just outside
	// the frame reaches into it.
	return OutDepth > 0.f && OutScale > 0.f && OutX >= -0.2f && OutX <= 1.2f && OutY >= -0.2f && OutY <= 1.2f;
}

void USaudLookSubsystem::Write(int32 Slot, const TCHAR* Name, float Value)
{
	if (Written[Slot] == Value)
	{
		return;
	}
	Written[Slot] = Value;
	Set(Name, Value);
}

void USaudLookSubsystem::Set(const TCHAR* Name, float Value)
{
	UKismetMaterialLibrary::SetScalarParameterValue(this, Collection, FName(Name), Value);
}

bool USaudLookSubsystem::VictimOnScreen(float& OutX, float& OutY) const
{
	const AFighterBase* V = Victim.Get();
	const APlayerController* PC = UGameplayStatics::GetPlayerController(GetWorld(), 0);
	if (!V || !PC)
	{
		return false;
	}
	int32 W = 0, H = 0;
	PC->GetViewportSize(W, H);
	FVector2D Screen;
	// The chest, not the feet: that is where the blow is.
	const FVector At = V->GetActorLocation() + FVector(0.f, 0.f, 40.f);
	if (W <= 0 || H <= 0 || !PC->ProjectWorldLocationToScreen(At, Screen, true))
	{
		return false;
	}
	OutX = static_cast<float>(Screen.X) / static_cast<float>(W);
	OutY = static_cast<float>(Screen.Y) / static_cast<float>(H);
	return OutX >= 0.f && OutX <= 1.f && OutY >= 0.f && OutY <= 1.f;
}
