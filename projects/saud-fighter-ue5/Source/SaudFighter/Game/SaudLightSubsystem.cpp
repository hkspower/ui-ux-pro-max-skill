#include "Game/SaudLightSubsystem.h"
#include "Combat/SaudLight.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/LocalLightComponent.h"
#include "Engine/Light.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"

bool USaudLightSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId USaudLightSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(USaudLightSubsystem, STATGROUP_Tickables);
}

void USaudLightSubsystem::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
	Clock += DeltaTime;
	if (Clock < SaudLight::RecheckSeconds)
	{
		return;
	}
	Clock = 0.f;

	UWorld* World = GetWorld();
	const APlayerCameraManager* Camera = World ? UGameplayStatics::GetPlayerCameraManager(World, 0) : nullptr;
	if (!Camera)
	{
		return;
	}
	const FVector Eye = Camera->GetCameraLocation();

	// What is streamed in now: World Partition loads and unloads districts,
	// so the set is found again each time rather than kept.
	static const FName Tag(SaudLight::ShadowTag);
	Lights.Reset();
	Dist.Reset();
	Was.Reset();
	for (TActorIterator<ALight> It(World); It; ++It)
	{
		if (!It->ActorHasTag(Tag))
		{
			continue;
		}
		ULocalLightComponent* Light = Cast<ULocalLightComponent>(It->GetLightComponent());
		if (!Light)
		{
			continue;
		}
		Lights.Add(Light);
		Dist.Add(static_cast<float>(FVector::Dist(Eye, Light->GetComponentLocation())));
		Was.Add(Light->CastShadows != 0);
	}
	if (Lights.Num() == 0)
	{
		return;
	}

	Casts.SetNumZeroed(Lights.Num());
	SaudLight::PickShadows(Dist.GetData(), Was.GetData(), Lights.Num(), Casts.GetData());
	for (int32 I = 0; I < Lights.Num(); ++I)
	{
		ULocalLightComponent* Light = Lights[I].Get();
		if (Light && Was[I] != Casts[I])
		{
			Light->SetCastShadows(Casts[I]);
		}
	}
}
