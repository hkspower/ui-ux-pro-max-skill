#include "Game/SaudLookSubsystem.h"
#include "Combat/FighterBase.h"
#include "Combat/SaudCharacter.h"
#include "Combat/SaudTypes.h"
#include "Combat/SaudIK.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/CapsuleComponent.h"
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
	SysFx = SaudAnime::SystemFx::FEvents();
	Trail = SaudAnime::SystemFx::FTrail();
	RealClock = 0.f;
	TrailRow = NAME_None;
	for (float& Last : Written)
	{
		Last = -1.f;
	}

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

		// The engine's own post-process, pinned to what the preview models
		// (SaudAnime::Film; anime_look.py's FILM and tonemap()).
		FPostProcessSettings& S = Volume->Settings;
		S.bOverride_FilmSlope = true;         S.FilmSlope = SaudAnime::Film::Slope;
		S.bOverride_FilmToe = true;           S.FilmToe = SaudAnime::Film::Toe;
		S.bOverride_FilmShoulder = true;      S.FilmShoulder = SaudAnime::Film::Shoulder;
		S.bOverride_FilmBlackClip = true;     S.FilmBlackClip = SaudAnime::Film::BlackClip;
		S.bOverride_FilmWhiteClip = true;     S.FilmWhiteClip = SaudAnime::Film::WhiteClip;
		S.bOverride_BlueCorrection = true;    S.BlueCorrection = SaudAnime::Film::BlueCorrection;
		S.bOverride_ExpandGamut = true;       S.ExpandGamut = SaudAnime::Film::ExpandGamut;
		S.bOverride_ToneCurveAmount = true;   S.ToneCurveAmount = SaudAnime::Film::ToneCurveAmount;
		S.bOverride_VignetteIntensity = true; S.VignetteIntensity = SaudAnime::Film::Vignette;
		S.bOverride_BloomIntensity = true;    S.BloomIntensity = SaudAnime::Film::Bloom;
		S.bOverride_FilmGrainIntensity = true; S.FilmGrainIntensity = SaudAnime::Film::Grain;
		S.bOverride_SceneFringeIntensity = true; S.SceneFringeIntensity = SaudAnime::Film::Fringe;
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
	// The wound is the player's alone: "you were hurt".
	const bool bVictimIsPlayer = InVictim && InVictim->IsPlayerControlled();

	// The System's energy on his strikes: a heavy blow of Saud's leaves the
	// path his striking limb took. There is no friendly fire, so a blow that
	// lands on anyone but the player is the player's (GatherTargets).
	const APlayerController* PC = UGameplayStatics::GetPlayerController(GetWorld(), 0);
	const ASaudCharacter* Saud = PC ? Cast<ASaudCharacter>(PC->GetPawn()) : nullptr;
	if (Saud && SaudAnime::SystemFx::TrailFor(InVictim && !bVictimIsPlayer, bHeavy, Hit.bParried))
	{
		FVector Tip = FVector::ZeroVector;
		if (StrikingTip(Saud, Tip))
		{
			Trail.Push(Tip, RealClock);     // where the tip is as it lands
		}
		Trail.Capture();
	}

	const SaudAnime::FBlowLook L = SaudAnime::ForBlow(bHeavy, Hit.bBlocked, Hit.bParried, Hit.bKnockdown,
	                                                  bVictimIsPlayer);
	if (L.Impact.Seconds <= 0.f && L.SpeedSeconds <= 0.f)
	{
		return;
	}
	Look.Add(L);
	Victim = InVictim;
	if (L.MarkLife > 0.f && InVictim)
	{
		// the mark stays where the blow landed on him, whatever he does next
		MarkVictim = InVictim;
		MarkOffset = Hit.ImpactPoint - InVictim->GetActorLocation();
	}
}

void USaudLookSubsystem::OnBurn(const AFighterBase* InVictim)
{
	Burned = InVictim;
	// ASaudCharacter::OnHitLanded calls this after AFighterBase::ReceiveHit
	// has handed the same blow to OnBlow (anime_look.py checks that order in
	// the source): the impact frame it started is on its first tick.
	Look.MarkBurning();
}

void USaudLookSubsystem::OnSystemEvent(SaudAnime::ESystemFx Fx, const AActor* Where, EAbility Skill)
{
	if (Fx == SaudAnime::ESystemFx::GateOpened)
	{
		if (!Where)
		{
			return;        // a flash belongs at a gate: none named, none drawn
		}
		FlashAt = Where;
	}
	SysFx.Add(Fx, Skill == EAbility::HawkFist);
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
	const float RealSeconds = FMath::Clamp(static_cast<float>(FApp::GetDeltaTime()), 0.f, 0.1f);
	Look.Tick(RealSeconds);
	SysFx.Tick(RealSeconds);
	Trail.Tick(RealSeconds);
	RealClock += RealSeconds;

	Write(ESlot::Impact, SaudAnime::Param::Impact, Look.ImpactValue());
	Write(ESlot::Invert, SaudAnime::Param::ImpactInvert, Look.InvertValue());
	Write(ESlot::Tone, SaudAnime::Param::ImpactTone, Look.ToneValue());
	Write(ESlot::Wound, SaudAnime::Param::Wound, Look.WoundValue());
	WriteMark();
	// The brush and the grain boil on twos, every frame, whatever else is
	// drawn: the same seed the speed lines are redrawn on.
	Write(ESlot::Boil, SaudAnime::Param::Boil, Look.Seed());
	// The palette the look draws its ink, bone, blood and ember with: the
	// live one, filled from DT_LookColors (USaudConfigSubsystem). Four
	// vectors a frame; cheaper than knowing when the tables were applied.
	const SaudHud::FPalette& Pal = SaudHud::LivePalette();
	const auto Vec = [this](const TCHAR* Name, const SaudHud::FRgba& C)
	{
		UKismetMaterialLibrary::SetVectorParameterValue(this, Collection, FName(Name), FLinearColor(C.R, C.G, C.B, C.A));
	};
	Vec(SaudAnime::Param::InkColour, Pal.Ink);
	Vec(SaudAnime::Param::BoneColour, Pal.Bone);
	Vec(SaudAnime::Param::BloodColour, Pal.Blood);
	Vec(SaudAnime::Param::EmberColour, Pal.Ember);
	Vec(SaudAnime::Param::SystemColour, Pal.System);
	Vec(SaudAnime::Param::IceColour, Pal.Ice);
	Vec(SaudAnime::Param::ShadowColour, Pal.Shadow);

	float Speed = Look.SpeedValue();
	float X = 0.5f, Y = 0.5f;
	if (Speed > 0.f && !VictimOnScreen(X, Y))
	{
		// Lines round a point off the screen would streak the whole picture
		// from one edge; off screen, they are simply not drawn.
		Speed = 0.f;
	}
	Write(ESlot::Speed, SaudAnime::Param::Speed, Speed);
	if (Speed > 0.f)
	{
		UKismetMaterialLibrary::SetScalarParameterValue(this, Collection, SaudAnime::Param::SpeedCentreX, X);
		UKismetMaterialLibrary::SetScalarParameterValue(this, Collection, SaudAnime::Param::SpeedCentreY, Y);
		Write(ESlot::Seed, SaudAnime::Param::SpeedSeed, Look.Seed());
	}

	// HAWK FIST: the flame on the player's fist and the burst on the man
	// his burning punch hit.
	const APlayerController* PC = UGameplayStatics::GetPlayerController(GetWorld(), 0);
	const ASaudCharacter* Saud = PC ? Cast<ASaudCharacter>(PC->GetPawn()) : nullptr;
	WriteFire(Saud);
	WritePower(Saud, RealSeconds);
	WriteSystem(Saud);
	RecordTrail(Saud);
	WriteTrail();
}

void USaudLookSubsystem::WriteSystem(const ASaudCharacter* Saud)
{
	using SaudAnime::ESystemFx;
	float Pillar = SysFx.AgeOf(ESystemFx::LevelUp);
	float Burst = SysFx.AgeOf(ESystemFx::SkillAcquired);
	float Rank = SysFx.AgeOf(ESystemFx::RankUp);
	if (SysFx.AnyOnSaud())
	{
		// His middle (the pelvis, as the aura's) and the ground under him (the
		// capsule's foot), projected as the fire's fist is. Off the screen,
		// nothing about him is drawn.
		const USkeletalMeshComponent* Body = Saud ? Saud->GetMesh() : nullptr;
		float X = 0.f, Y = 0.f, Depth = 0.f, Scale = 0.f;
		float FX = 0.f, FY = 0.f, FDepth = 0.f, FScale = 0.f;
		const FVector Feet = Saud ? Saud->GetActorLocation()
			- FVector(0.f, 0.f, Saud->GetCapsuleComponent()->GetScaledCapsuleHalfHeight()) : FVector::ZeroVector;
		if (Body && Project(Body->GetSocketLocation(TEXT("pelvis")), X, Y, Depth, Scale)
		    && Project(Feet, FX, FY, FDepth, FScale))
		{
			Set(SaudAnime::Param::SysX, X);
			Set(SaudAnime::Param::SysY, Y);
			Set(SaudAnime::Param::SysFootX, FX);
			Set(SaudAnime::Param::SysFootY, FY);
			Set(SaudAnime::Param::SysDepth, Depth);
			Set(SaudAnime::Param::SysScale, Scale);
		}
		else
		{
			Pillar = Burst = Rank = -1.f;
		}
	}
	Write(ESlot::SysPillarAge, SaudAnime::Param::SysPillarAge, Pillar);
	Write(ESlot::SysBurstAge, SaudAnime::Param::SysBurstAge, Burst);
	Write(ESlot::SysBurstHawk, SaudAnime::Param::SysBurstHawk, SysFx.HawkValue());
	Write(ESlot::SysRankAge, SaudAnime::Param::SysRankAge, Rank);
	Write(ESlot::SysQuestAge, SaudAnime::Param::SysQuestAge, SysFx.AgeOf(ESystemFx::QuestComplete));

	// The gate's flash, at the middle of the gate's bounds.
	float Flash = SysFx.AgeOf(ESystemFx::GateOpened);
	const AActor* Gate = FlashAt.Get();
	if (Flash >= 0.f)
	{
		FVector Origin = FVector::ZeroVector, Extent = FVector::ZeroVector;
		float X = 0.f, Y = 0.f, Depth = 0.f, Scale = 0.f;
		if (Gate)
		{
			Gate->GetActorBounds(false, Origin, Extent);
		}
		if (Gate && Project(Origin, X, Y, Depth, Scale))
		{
			Set(SaudAnime::Param::SysFlashX, X);
			Set(SaudAnime::Param::SysFlashY, Y);
			Set(SaudAnime::Param::SysFlashDepth, Depth);
			Set(SaudAnime::Param::SysFlashScale, Scale);
		}
		else
		{
			Flash = -1.f;
		}
	}
	Write(ESlot::SysFlashAge, SaudAnime::Param::SysFlashAge, Flash);
}

bool USaudLookSubsystem::StrikingTip(const ASaudCharacter* Saud, FVector& OutTip) const
{
	const FName Row = Saud ? Saud->GetCurrentAttackRow() : NAME_None;
	const USkeletalMeshComponent* Body = Saud ? Saud->GetMesh() : nullptr;
	if (Row.IsNone() || !Body)
	{
		return false;
	}
	// The tip the strike lands with (SaudIK::StrikeOf, the runtime IK's own
	// table): the knuckles' joint, the ball of the foot, or the knee (the
	// calf's joint).
	const SaudIK::FStrike K = SaudIK::StrikeOf(TCHAR_TO_ANSI(*Row.ToString()));
	if (K.Limb == SaudIK::ELimb::None || (K.Side != 'l' && K.Side != 'r'))
	{
		return false;
	}
	const TCHAR* Side = K.Side == 'l' ? TEXT("_l") : TEXT("_r");
	const TCHAR* Bone = K.Tip == SaudIK::ETip::Knuckles ? TEXT("hand_end")
		: K.Tip == SaudIK::ETip::Ball ? TEXT("ball")
		: K.Tip == SaudIK::ETip::Knee ? TEXT("calf")
		: (K.Limb == SaudIK::ELimb::Arm ? TEXT("hand") : TEXT("foot"));
	OutTip = Body->GetSocketLocation(FName(*FString::Printf(TEXT("%s%s"), Bone, Side)));
	return true;
}

void USaudLookSubsystem::RecordTrail(const ASaudCharacter* Saud)
{
	// Through a heavy swing of his, the striking tip's path, stamped in real
	// time; a new swing, or none, forgets the last one's. (The trail already
	// showing is left alone: it is where it was.)
	const FAttackDef* Attack = Saud ? Saud->GetCurrentAttack() : nullptr;
	const FName Row = (Attack && Attack->bHeavy && Saud->State == EFighterState::Attack)
		? Saud->GetCurrentAttackRow() : NAME_None;
	if (Row != TrailRow)
	{
		Trail.Forget();
		TrailRow = Row;
	}
	FVector Tip = FVector::ZeroVector;
	if (!Row.IsNone() && StrikingTip(Saud, Tip))
	{
		Trail.Push(Tip, RealClock);
	}
}

void USaudLookSubsystem::WriteTrail()
{
	// The trail's points stay where they were in the world -- an after-image
	// -- and are projected each tick; one of them off the screen, or behind
	// the camera, and it is not drawn.
	using namespace SaudAnime::SystemFx;
	float Age = Trail.Age;
	if (Age >= 0.f)
	{
		float X[TrailPoints] = {}, Y[TrailPoints] = {};
		float Near = 1e9f, Scale = 0.f;
		for (int32 i = 0; i < TrailPoints && Age >= 0.f; ++i)
		{
			float D = 0.f, S = 0.f;
			if (!Project(Trail.Points[i], X[i], Y[i], D, S))
			{
				Age = -1.f;
			}
			else if (D < Near)
			{
				Near = D;
				Scale = S;
			}
		}
		if (Age >= 0.f)
		{
			for (int32 i = 0; i < TrailPoints; ++i)
			{
				Set(SaudAnime::Param::TrailX[i], X[i]);
				Set(SaudAnime::Param::TrailY[i], Y[i]);
			}
			Set(SaudAnime::Param::TrailDepth, Near);
			Set(SaudAnime::Param::TrailScale, Scale);
		}
	}
	Write(ESlot::TrailAge, SaudAnime::Param::TrailAge, Age);
}

void USaudLookSubsystem::WritePower(const ASaudCharacter* Saud, float RealSeconds)
{
	// Full rage burns at Power::Ready; the finisher (the attack Input_Rage
	// starts, "Rage") at full.
	const bool bReady = Saud && Saud->IsRageReady();
	const bool bFinisher = Saud && Saud->GetCurrentAttackRow() == FName(TEXT("Rage"));
	Power.Tick(SaudAnime::Power::Target(bReady, bFinisher), RealSeconds);
	float Level = Power.Level;
	const USkeletalMeshComponent* Body = Saud ? Saud->GetMesh() : nullptr;
	if (Level > 0.f && Body)
	{
		float X = 0.f, Y = 0.f, Depth = 0.f, Scale = 0.f;
		if (!Project(Body->GetSocketLocation(TEXT("pelvis")), X, Y, Depth, Scale))
		{
			Level = 0.f;      // off the screen: nothing to burn round
		}
		else
		{
			Set(SaudAnime::Param::AuraX, X);
			Set(SaudAnime::Param::AuraY, Y);
			Set(SaudAnime::Param::AuraDepth, Depth);
			Set(SaudAnime::Param::AuraScale, Scale);
			// His eyes, from the head joint (at the eye line; there are no
			// eye bones): forward along his facing, apart across it.
			const FVector Head = Body->GetSocketLocation(TEXT("head"));
			const FVector Fwd = Saud->GetActorForwardVector();
			const FVector Right = Saud->GetActorRightVector();
			const FVector Mid = Head + Fwd * SaudAnime::Power::EyeForwardCm;
			const FVector Half = Right * (0.5f * SaudAnime::Power::EyeApartCm);
			float X0 = 0.f, Y0 = 0.f, D0 = 0.f, S0 = 0.f, X1 = 0.f, Y1 = 0.f, D1 = 0.f, S1 = 0.f;
			if (Project(Mid - Half, X0, Y0, D0, S0) && Project(Mid + Half, X1, Y1, D1, S1))
			{
				Set(SaudAnime::Param::EyeX0, X0);
				Set(SaudAnime::Param::EyeY0, Y0);
				Set(SaudAnime::Param::EyeX1, X1);
				Set(SaudAnime::Param::EyeY1, Y1);
				Set(SaudAnime::Param::EyeDepth, FMath::Min(D0, D1));
				Set(SaudAnime::Param::EyeScale, 0.5f * (S0 + S1));
			}
			else
			{
				Set(SaudAnime::Param::EyeScale, 0.f);
			}
		}
	}
	Write(ESlot::AuraTime, SaudAnime::Param::AuraTime, Power.Clock);
	Write(ESlot::Aura, SaudAnime::Param::Aura, Level);
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
	Write(ESlot::FireHeat, SaudFire::Param::FireHeat, Heat);

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
	Write(ESlot::BurnAge, SaudFire::Param::BurnAge, Age);
}

void USaudLookSubsystem::WriteMark()
{
	// The mark at the point of contact, projected as the fire's burst is:
	// where it is on the screen, how deep, how big a figure pixel is there.
	// Off the screen (or the man gone) it is simply not drawn.
	float Age = Look.MarkAge();
	const AFighterBase* V = MarkVictim.Get();
	float X = 0.f, Y = 0.f, Depth = 0.f, Scale = 0.f;
	if (Age >= 0.f && (!V || !Project(V->GetActorLocation() + MarkOffset, X, Y, Depth, Scale)))
	{
		Age = -1.f;
	}
	if (Age >= 0.f)
	{
		Write(ESlot::MarkX, SaudAnime::Param::MarkX, X);
		Write(ESlot::MarkY, SaudAnime::Param::MarkY, Y);
		Write(ESlot::MarkDepth, SaudAnime::Param::MarkDepth, Depth);
		Write(ESlot::MarkScale, SaudAnime::Param::MarkScale, Scale);
		Write(ESlot::MarkSeed, SaudAnime::Param::MarkSeed, Look.MarkSeed());
	}
	Write(ESlot::MarkAge, SaudAnime::Param::MarkAge, Age);
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

void USaudLookSubsystem::Write(ESlot Slot, const TCHAR* Name, float Value)
{
	float& Last = Written[static_cast<int32>(Slot)];
	if (Last == Value)
	{
		return;
	}
	Last = Value;
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
