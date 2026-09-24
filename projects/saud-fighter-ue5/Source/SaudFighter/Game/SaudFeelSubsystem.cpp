#include "Game/SaudFeelSubsystem.h"
#include "Combat/FighterBase.h"
#include "Game/SaudGameInstance.h"
#include "Game/SaudLookSubsystem.h"

#include "Camera/CameraComponent.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/WorldSettings.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/App.h"

USaudFeelSubsystem* USaudFeelSubsystem::Get(const UObject* WorldContext)
{
	const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	return World ? World->GetSubsystem<USaudFeelSubsystem>() : nullptr;
}

bool USaudFeelSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	// A fight happens in a game; an editor viewport has no blows to feel.
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void USaudFeelSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	Feel = SaudFeel::FState();
	bHoldingTime = false;
	bCameraMoved = false;
	RealClock = 0.f;
}

void USaudFeelSubsystem::Deinitialize()
{
	ReleaseTime();
	RestoreCamera();
	Super::Deinitialize();
}

TStatId USaudFeelSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(USaudFeelSubsystem, STATGROUP_Tickables);
}

/* ------------------------------------------------------------------ blows */

void USaudFeelSubsystem::OnBlow(const AFighterBase* Victim, const AFighterBase* Attacker,
                                const FHitResultData& Hit, bool bHeavy)
{
	const bool bVictimIsPlayer = Victim && Victim->IsPlayerControlled();
	const bool bAttackerIsPlayer = Attacker && Attacker->IsPlayerControlled();

	const SaudFeel::FBlowFeel F = SaudFeel::ForBlow(bHeavy, Hit.bBlocked, Hit.bParried, Hit.bKnockdown,
	                                                bVictimIsPlayer, bAttackerIsPlayer);
	Feel.Add(F);

	// The freeze starts on this frame, not the next: the blow's own frame is
	// the one that holds.
	if (Feel.Frozen())
	{
		HoldTime();
	}

	// Only a blow the player is in reaches his hands.
	if (bVictimIsPlayer || bAttackerIsPlayer)
	{
		Buzz(F);
	}

	// And the picture's half of it: the impact frame and the speed lines.
	if (USaudLookSubsystem* Look = USaudLookSubsystem::Get(this))
	{
		Look->OnBlow(Victim, Hit, bHeavy);
	}
}

void USaudFeelSubsystem::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	// DeltaTime is the world's, and during a freeze the world's clock is all
	// but stopped. Everything here runs on the frame's real length.
	const float Real = FMath::Clamp(static_cast<float>(FApp::GetDeltaTime()), 0.f, 0.1f);
	RealClock += Real;
	Feel.Tick(Real);

	if (Feel.Frozen())
	{
		HoldTime();
	}
	else
	{
		ReleaseTime();
	}

	if (Feel.ShakePx > 0.f || Feel.Punch > 0.f)
	{
		ApplyCamera();
	}
	else
	{
		RestoreCamera();
	}
}

/* ------------------------------------------------------------------- time */

void USaudFeelSubsystem::HoldTime()
{
	if (bHoldingTime)
	{
		return;
	}
	UWorld* World = GetWorld();
	AWorldSettings* Settings = World ? World->GetWorldSettings() : nullptr;
	if (!Settings)
	{
		return;
	}
	DilationBefore = Settings->TimeDilation;
	UGameplayStatics::SetGlobalTimeDilation(World, FrozenDilation);
	bHoldingTime = true;
}

void USaudFeelSubsystem::ReleaseTime()
{
	if (!bHoldingTime)
	{
		return;
	}
	bHoldingTime = false;
	if (UWorld* World = GetWorld())
	{
		UGameplayStatics::SetGlobalTimeDilation(World, DilationBefore > 0.f ? DilationBefore : 1.f);
	}
}

/* ----------------------------------------------------------------- camera */

UCameraComponent* USaudFeelSubsystem::FindCamera() const
{
	const APlayerController* PC = UGameplayStatics::GetPlayerController(GetWorld(), 0);
	const AActor* Target = PC ? PC->GetViewTarget() : nullptr;
	return Target ? Target->FindComponentByClass<UCameraComponent>() : nullptr;
}

void USaudFeelSubsystem::ApplyCamera()
{
	UCameraComponent* Cam = FindCamera();
	if (Cam != Camera.Get())
	{
		// A new view: give the old one back as it was, take this one as it is.
		RestoreCamera();
		Camera = Cam;
		BaseFov = Cam ? Cam->FieldOfView : 0.f;
		BaseRotation = Cam ? Cam->GetRelativeRotation() : FRotator::ZeroRotator;
	}
	if (!Cam)
	{
		return;
	}

	// The shake is the browser's share of a 720-pixel picture, turned into
	// degrees of this camera's vertical field of view. FieldOfView is
	// horizontal; the aspect is the viewport's when there is one.
	float Aspect = Cam->AspectRatio;
	if (const APlayerController* PC = UGameplayStatics::GetPlayerController(GetWorld(), 0))
	{
		int32 W = 0, H = 0;
		PC->GetViewportSize(W, H);
		if (W > 0 && H > 0)
		{
			Aspect = static_cast<float>(W) / static_cast<float>(H);
		}
	}
	const float HalfH = FMath::DegreesToRadians(BaseFov * 0.5f);
	const float VFov = FMath::RadiansToDegrees(2.f * FMath::Atan(FMath::Tan(HalfH) / FMath::Max(0.1f, Aspect)));

	// The browser moves the picture by up to shake/2 each way.
	const float Amp = 0.5f * SaudFeel::ShakeDegrees(Feel.ShakePx, VFov);
	float P = 0.f, Y = 0.f;
	SaudFeel::ShakeWave(RealClock, P, Y);
	Cam->SetRelativeRotation(BaseRotation + FRotator(P * Amp, Y * Amp, 0.f));
	Cam->SetFieldOfView(SaudFeel::PunchFov(BaseFov, Feel.Punch));
	bCameraMoved = true;
}

void USaudFeelSubsystem::RestoreCamera()
{
	if (!bCameraMoved)
	{
		return;
	}
	bCameraMoved = false;
	if (UCameraComponent* Cam = Camera.Get())
	{
		Cam->SetRelativeRotation(BaseRotation);
		Cam->SetFieldOfView(BaseFov);
	}
}

/* ------------------------------------------------------------------- pad */

void USaudFeelSubsystem::Buzz(const SaudFeel::FBlowFeel& F)
{
	const float Seconds = SaudFeel::PadBuzzSeconds(F.Buzz);
	if (Seconds <= 0.f || F.BuzzStrength <= 0.f)
	{
		return;
	}
	// The profile's vibration switch, the same one the browser's haptic()
	// reads (save.haptics).
	const UWorld* World = GetWorld();
	const USaudGameInstance* GI = World ? World->GetGameInstance<USaudGameInstance>() : nullptr;
	if (GI && !GI->GetProgress().bVibration)
	{
		return;
	}
	if (APlayerController* PC = UGameplayStatics::GetPlayerController(World, 0))
	{
		// All four motors: a blow is felt in both hands. The native overload,
		// not the latent Blueprint one -- nothing waits on it.
		PC->PlayDynamicForceFeedback(F.BuzzStrength, Seconds, true, true, true, true,
		                             EDynamicForceFeedbackAction::Start);
	}
}
