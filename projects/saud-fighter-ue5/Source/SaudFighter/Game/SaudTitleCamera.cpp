#include "Game/SaudTitleCamera.h"
#include "Combat/FighterBase.h"
#include "Combat/SaudTitle.h"

#include "Camera/CameraComponent.h"
#include "CollisionQueryParams.h"
#include "Components/CapsuleComponent.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "Misc/App.h"

namespace
{
	/** The sphere the eye is kept out of walls with (cm). */
	constexpr float WallProbe = 12.f;
}

ASaudTitleCamera::ASaudTitleCamera()
{
	PrimaryActorTick.bCanEverTick = true;
	// the title holds the world paused; the sweep goes on
	PrimaryActorTick.bTickEvenWhenPaused = true;
	PrimaryActorTick.TickGroup = TG_PostPhysics;
	if (UCameraComponent* Cam = GetCameraComponent())
	{
		// the shot is worked out for the whole screen, whatever its shape:
		// no bars, and the vertical field of view held by SaudTitle
		Cam->bConstrainAspectRatio = false;
		Cam->SetFieldOfView(SaudTitle::HFovDeg(16.f / 9.f));
	}
}

void ASaudTitleCamera::Follow(AFighterBase* Him)
{
	Subject = Him;
	Clock = 0.f;
	if (!Him)
	{
		return;
	}
	const UCapsuleComponent* Capsule = Him->GetCapsuleComponent();
	Feet = Him->GetActorLocation() - FVector(0.f, 0.f, Capsule ? Capsule->GetScaledCapsuleHalfHeight() : 0.f);
	const FVector F = Him->GetFacing();
	Facing = FVector(F.X, F.Y, 0.f).IsNearlyZero() ? Him->GetActorForwardVector() : F;
	Place();
}

void ASaudTitleCamera::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	// DeltaSeconds is the world's; the sweep runs on the frame's real length
	Clock += FMath::Clamp(static_cast<float>(FApp::GetDeltaTime()), 0.f, 0.1f);
	Clock = FMath::Fmod(Clock, SaudTitle::PeriodS);
	Place();
}

void ASaudTitleCamera::Place()
{
	UWorld* World = GetWorld();
	FVector2D Size(1920.f, 1080.f);
	if (UGameViewportClient* Viewport = World ? World->GetGameViewport() : nullptr)
	{
		Viewport->GetViewportSize(Size);
	}
	if (Size.X < 1.f || Size.Y < 1.f)
	{
		return;
	}

	const SaudTitle::FFrame Fr = SaudTitle::FrameFor(SaudHud::FPage::For(Size.X, Size.Y));
	SaudTitle::FShot S = SaudTitle::Shoot(Feet, Facing, Clock, Fr);

	// Out of the walls: sweep from where the shot aims through him to the
	// eye, and stop short of the first thing on the camera channel.
	if (World)
	{
		const FVector Aim = Feet + FVector(0.f, 0.f, SaudTitle::AimZ);
		FCollisionQueryParams Params(SCENE_QUERY_STAT(SaudTitleCamera), false, this);
		if (AFighterBase* Him = Subject.Get())
		{
			Params.AddIgnoredActor(Him);
		}
		FHitResult Hit;
		if (World->SweepSingleByChannel(Hit, Aim, S.Eye, FQuat::Identity, ECC_Camera,
		                                FCollisionShape::MakeSphere(WallProbe), Params))
		{
			// along the same line: the view keeps its direction, so he
			// keeps his place across the screen and only grows
			S.Eye = Aim + (S.Eye - Aim) * Hit.Time;
		}
	}

	SetActorLocationAndRotation(S.Eye, S.Forward.Rotation());
	if (UCameraComponent* Cam = GetCameraComponent())
	{
		Cam->SetFieldOfView(S.HFovDeg);
	}
}
