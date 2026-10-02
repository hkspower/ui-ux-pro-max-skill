#include "Game/SaudMenuSubsystem.h"
#include "Combat/FighterBase.h"
#include "Combat/SaudMotionAnimInstance.h"
#include "Combat/SaudMotionComponent.h"
#include "Combat/SaudTypes.h"
#include "Game/SaudAudioSubsystem.h"
#include "Game/SaudFeelSubsystem.h"
#include "Game/SaudGameInstance.h"
#include "Game/SaudInputBindings.h"
#include "Game/SaudTitleCamera.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "GameFramework/PlayerController.h"
#include "InputAction.h"
#include "InputActionValue.h"
#include "InputMappingContext.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Misc/App.h"
#include "Prologue/SaudPrologueGameMode.h"

DEFINE_LOG_CATEGORY_STATIC(LogSaudMenu, Log, All);

namespace
{
	using SaudControls::EAction;
	using SaudMenu::EMenuEffect;
	using SaudMenu::EScreen;

	constexpr int32 HeldUp = 1, HeldDown = 2, HeldLeft = 4, HeldRight = 8;
	/** A stick past this is a direction (the fight's dash reads 0.35; a
	    menu wants a firmer push so a rested thumb does not scroll). */
	constexpr float StickDirection = 0.5f;
	constexpr float TestBuzzSeconds = 0.3f;
	/** FIGHT / CONTINUE: the title's camera hands over to his own this
	    smoothly (seconds; the ease's exponent). */
	constexpr float TitleBlendSeconds = 1.2f;
	constexpr float TitleBlendExp = 2.f;

	/** The contexts are swapped while the key that caused the swap is
	    still down: ignore every held key until it is released, so Escape
	    that opened the pause does not also resume it. */
	FModifyContextOptions SwapOptions()
	{
		FModifyContextOptions Options;
		Options.bIgnoreAllPressedKeysUntilRelease = true;
		Options.bForceImmediately = false;
		return Options;
	}
}

USaudMenuSubsystem* USaudMenuSubsystem::Get(const UObject* WorldContext)
{
	const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	return World ? World->GetSubsystem<USaudMenuSubsystem>() : nullptr;
}

bool USaudMenuSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void USaudMenuSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	Menu = SaudMenu::FMenuModel();
	bOpen = false;
	bPaused = false;
	ResetHeld();
}

void USaudMenuSubsystem::Deinitialize()
{
	EndTitleShot(false);
	if (MenuInput)
	{
		if (APlayerController* PC = InputOwner.Get())
		{
			PC->PopInputComponent(MenuInput);
		}
		MenuInput->DestroyComponent();
		MenuInput = nullptr;
	}
	InputOwner = nullptr;
	bOpen = false;
	Super::Deinitialize();
}

TStatId USaudMenuSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(USaudMenuSubsystem, STATGROUP_Tickables);
}

/* ------------------------------------------------------------- the flow */

void USaudMenuSubsystem::Open(EScreen Screen)
{
	APlayerController* PC = UGameplayStatics::GetPlayerController(GetWorld(), 0);
	if (!PC)
	{
		UE_LOG(LogSaudMenu, Warning, TEXT("No player controller: the menu cannot open."));
		return;
	}

	ReadSettings();
	if (USaudInputBindings* Bindings = USaudInputBindings::Get(this))
	{
		Bindings->RefreshPad();
		Menu.Pad = Bindings->PadInUse();
	}
	Menu.Shown = Menu.Pad == SaudControls::EPad::Keyboard ? SaudControls::EPad::Xbox : Menu.Pad;
	SaudMenu::Open(Menu, Screen);
	ResetHeld();

	if (!bOpen)
	{
		bOpen = true;
		EnsureMenuInput(PC);
		if (MenuInput)
		{
			PC->PushInputComponent(MenuInput);
			InputOwner = PC;
		}
		SetFightContext(false);
		SetMenuContext(true);
	}

	// Both screens hold the world: under the title a wave could otherwise
	// wake within its site's radius of where CONTINUE put him. The menu and
	// its music run on real time and the actions trigger through the pause.
	if (!bPaused)
	{
		UGameplayStatics::SetGamePaused(this, true);
		bPaused = true;
	}
	if (Screen == EScreen::Title)
	{
		if (USaudAudioSubsystem* Audio = USaudAudioSubsystem::Get(this))
		{
			Audio->PlayMusic(TEXT("Music_Menu"));
		}
		bWantTitleShot = true;
		StartTitleShot();
	}
}

void USaudMenuSubsystem::Close()
{
	if (!bOpen)
	{
		return;
	}
	bOpen = false;
	ResetHeld();
	if (bPaused)
	{
		UGameplayStatics::SetGamePaused(this, false);
		bPaused = false;
	}
	SetMenuContext(false);
	if (APlayerController* PC = InputOwner.Get())
	{
		if (MenuInput)
		{
			PC->PopInputComponent(MenuInput);
		}
	}
}

void USaudMenuSubsystem::BeginFight()
{
	SetFightContext(true);
	if (USaudAudioSubsystem* Audio = USaudAudioSubsystem::Get(this))
	{
		Audio->PlayMusic(TEXT("Music_Stage"));
	}
	// The prologue is marked seen when its fight starts, not when its level
	// opens: a player who quits at the first title has not been through it.
	if (ASaudPrologueGameMode* Prologue = GetWorld() ? GetWorld()->GetAuthGameMode<ASaudPrologueGameMode>() : nullptr)
	{
		Prologue->MarkSeen();
	}
}

/* ------------------------------------------------------- the live title */

void USaudMenuSubsystem::StartTitleShot()
{
	UWorld* World = GetWorld();
	APlayerController* PC = UGameplayStatics::GetPlayerController(World, 0);
	AFighterBase* Him = PC ? Cast<AFighterBase>(PC->GetPawn()) : nullptr;
	if (!World || !Him)
	{
		return;
	}
	if (!TitleCamera.IsValid())
	{
		FActorSpawnParameters Params;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		Params.ObjectFlags |= RF_Transient;
		TitleCamera = World->SpawnActor<ASaudTitleCamera>(ASaudTitleCamera::StaticClass(), FTransform::Identity, Params);
	}
	ASaudTitleCamera* Cam = TitleCamera.Get();
	if (!Cam)
	{
		return;
	}
	Cam->Follow(Him);
	PC->SetViewTarget(Cam);
	KeepPosing(Him, true);
	Posing = Him;
}

void USaudMenuSubsystem::EndTitleShot(bool bBlend)
{
	bWantTitleShot = false;
	KeepPosing(Posing.Get(), false);
	Posing = nullptr;
	ASaudTitleCamera* Cam = TitleCamera.Get();
	TitleCamera = nullptr;
	if (!Cam)
	{
		return;
	}
	APlayerController* PC = UGameplayStatics::GetPlayerController(GetWorld(), 0);
	APawn* Pawn = PC ? PC->GetPawn() : nullptr;
	if (bBlend && PC && Pawn)
	{
		// the world is running again by now (Close came first): the blend
		// runs, and the camera goes once it is done
		PC->SetViewTargetWithBlend(Pawn, TitleBlendSeconds, VTBlend_EaseInOut, TitleBlendExp);
		Cam->SetLifeSpan(TitleBlendSeconds + 0.5f);
	}
	else
	{
		if (PC && Pawn)
		{
			PC->SetViewTarget(Pawn);
		}
		Cam->Destroy();
	}
}

void USaudMenuSubsystem::KeepPosing(AFighterBase* Him, bool bOn)
{
	if (!Him)
	{
		return;
	}
	// Only these two: the mesh (its anim instance plays the clip) and the
	// motion component (which picks it). The rest of him -- movement,
	// abilities, the fight's timers -- stays held by the pause.
	if (USkeletalMeshComponent* Mesh = Him->GetMesh())
	{
		Mesh->SetTickableWhenPaused(bOn);
		if (USaudMotionAnimInstance* Anim = Cast<USaudMotionAnimInstance>(Mesh->GetAnimInstance()))
		{
			Anim->SetRealTime(bOn);
		}
	}
	if (USaudMotionComponent* Motion = Him->FindComponentByClass<USaudMotionComponent>())
	{
		Motion->SetTickableWhenPaused(bOn);
	}
}

/* -------------------------------------------------------- a new game */

void USaudMenuSubsystem::StartNewGame()
{
	UWorld* World = GetWorld();
	USaudGameInstance* GI = World ? World->GetGameInstance<USaudGameInstance>() : nullptr;
	if (!GI)
	{
		return;
	}
	// The progress goes; the settings are the player's, not the save's,
	// and stay.
	const FSaudProgress Old = GI->GetProgress();
	GI->ResetProgress();
	FSaudProgress& P = GI->GetMutableProgress();
	P.DifficultyIndex = Old.DifficultyIndex;
	P.bSound = Old.bSound;
	P.bMusic = Old.bMusic;
	P.bVibration = Old.bVibration;
	P.SoundVolume = Old.SoundVolume;
	P.MusicVolume = Old.MusicVolume;
	GI->SaveProgress();
	// From the very start, the prologue, straight into its fight: ?Start
	// tells its game mode to begin the fight rather than open the title.
	if (USaudAudioSubsystem* Audio = USaudAudioSubsystem::Get(this))
	{
		Audio->StopMusic(0.5f);
	}
	Close();
	UGameplayStatics::OpenLevel(this, SaudGameplay::PrologueLevel, true, TEXT("Start"));
}

/* ------------------------------------------------------------ the tick */

void USaudMenuSubsystem::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
	if (!bOpen)
	{
		return;
	}
	// The level opens the title from the game mode's BeginPlay, which can
	// come before his pawn is in it or his mesh has its anim instance: try
	// again until the shot is up, and hold him posing every frame (cheap,
	// and it catches an anim instance made after the shot was).
	if (bWantTitleShot)
	{
		if (!TitleCamera.IsValid())
		{
			StartTitleShot();
		}
		else
		{
			KeepPosing(Posing.Get(), true);
		}
	}
	// DeltaTime is the world's, which a pause holds at zero. The pulse, the
	// wipe, the entrance and the focus glide run on the frame's real
	// length, as the HUD's clock does (SaudMenu::Step).
	const float Real = FMath::Clamp(static_cast<float>(FApp::GetDeltaTime()), 0.f, 0.1f);
	SaudMenu::Step(Menu, Real);

	if (USaudInputBindings* Bindings = USaudInputBindings::Get(this))
	{
		Bindings->RefreshPad();
		Menu.Pad = Bindings->PadInUse();
	}

	// The held direction: once when it changes, and up / down again after
	// NavRepeatFirst, then every NavRepeatNext, while it is held. Left and
	// right repeat only on a level (SOUND, MUSIC: SaudMenu::RepeatsSideways)
	// -- elsewhere they toggle a setting, and a held toggle would flip it
	// eight times a second.
	const EAction Direction = HeldDirection();
	if (Direction != LastDirection)
	{
		LastDirection = Direction;
		if (Direction != EAction::Count)
		{
			Act(Direction);
			Repeat = SaudControls::NavRepeatFirst;
		}
	}
	else if (Direction == EAction::NavUp || Direction == EAction::NavDown
	         || ((Direction == EAction::NavLeft || Direction == EAction::NavRight) && SaudMenu::RepeatsSideways(Menu)))
	{
		Repeat -= Real;
		if (Repeat <= 0.f)
		{
			Act(Direction);
			Repeat = SaudControls::NavRepeatNext;
		}
	}
}

EAction USaudMenuSubsystem::HeldDirection() const
{
	if (NavHeld & HeldUp) return EAction::NavUp;
	if (NavHeld & HeldDown) return EAction::NavDown;
	if (NavHeld & HeldLeft) return EAction::NavLeft;
	if (NavHeld & HeldRight) return EAction::NavRight;
	// the stick: its larger axis, past the threshold; Y up is positive
	const float Ax = FMath::Abs(Stick.X), Ay = FMath::Abs(Stick.Y);
	if (Ay >= Ax && Ay > StickDirection)
	{
		return Stick.Y > 0.f ? EAction::NavUp : EAction::NavDown;
	}
	if (Ax > StickDirection)
	{
		return Stick.X > 0.f ? EAction::NavRight : EAction::NavLeft;
	}
	return EAction::Count;
}

void USaudMenuSubsystem::ResetHeld()
{
	NavHeld = 0;
	Stick = FVector2D::ZeroVector;
	LastDirection = EAction::Count;
	Repeat = 0.f;
}

/* ---------------------------------------------------------- the effects */

void USaudMenuSubsystem::Act(EAction Action)
{
	if (!bOpen)
	{
		return;
	}
	Apply(SaudMenu::Navigate(Menu, Action));
}

void USaudMenuSubsystem::Apply(EMenuEffect Effect)
{
	USaudAudioSubsystem* Audio = USaudAudioSubsystem::Get(this);
	const auto Cue = [Audio](const TCHAR* Name)
	{
		if (Audio)
		{
			Audio->PlayUI(FName(Name));
		}
	};

	switch (Effect)
	{
	case EMenuEffect::StartGame:
		Close();
		EndTitleShot(true);
		Cue(TEXT("UI_Tap"));
		BeginFight();
		break;

	case EMenuEffect::NewGame:
		// Confirmed on the Confirm screen (SaudMenu): the save is replaced
		// and the first fight starts, with no title in between.
		Cue(TEXT("UI_Tap"));
		StartNewGame();
		break;

	case EMenuEffect::Resume:
		Close();
		Cue(TEXT("UI_Back"));
		SetFightContext(true);
		break;

	case EMenuEffect::QuitToTitle:
		// The world goes, and its music with it; the title opens again in
		// the open world's game mode and starts its own.
		if (Audio)
		{
			Audio->StopMusic(0.5f);
		}
		Close();
		UGameplayStatics::OpenLevel(this, SaudGameplay::WorldLevel);
		break;

	case EMenuEffect::QuitGame:
		// Not FPlatformMisc::RequestExit: that closes the editor under PIE.
		UKismetSystemLibrary::QuitGame(this, UGameplayStatics::GetPlayerController(GetWorld(), 0),
		                               EQuitPreference::Quit, false);
		break;

	case EMenuEffect::SetSound:
		WriteSettings();
		Cue(TEXT("UI_Tap"));		// at the new level, so the step is heard; silent at OFF
		break;

	case EMenuEffect::SetMusic:
		WriteSettings();
		if (Audio)
		{
			Audio->RefreshMusic();	// starts, stops, or sets the playing music to the level
		}
		Cue(TEXT("UI_Tap"));
		break;

	case EMenuEffect::ToggleVibration:
		WriteSettings();
		if (Menu.bVibration)
		{
			if (USaudFeelSubsystem* Feel = USaudFeelSubsystem::Get(this))
			{
				Feel->TestBuzz(TestBuzzSeconds);
			}
		}
		Cue(TEXT("UI_Tap"));
		break;

	case EMenuEffect::CycleDifficulty:
		WriteSettings();
		Cue(TEXT("UI_Tap"));
		break;

	case EMenuEffect::Tap:
		Cue(TEXT("UI_Tap"));
		break;
	case EMenuEffect::Back:
		Cue(TEXT("UI_Back"));
		break;
	case EMenuEffect::Denied:
		Cue(TEXT("UI_Denied"));
		break;
	case EMenuEffect::None:
	default:
		break;
	}
}

/* --------------------------------------------------------- the profile */

void USaudMenuSubsystem::ReadSettings()
{
	const UWorld* World = GetWorld();
	const USaudGameInstance* GI = World ? World->GetGameInstance<USaudGameInstance>() : nullptr;
	if (!GI)
	{
		return;
	}
	const FSaudProgress& P = GI->GetProgress();
	Menu.DifficultyIndex = FMath::Clamp(P.DifficultyIndex, 0, 2);
	Menu.SoundLevel = P.bSound ? FMath::Clamp(P.SoundVolume, 0, SaudMenu::LevelMax) : 0;
	Menu.MusicLevel = P.bMusic ? FMath::Clamp(P.MusicVolume, 0, SaudMenu::LevelMax) : 0;
	Menu.bVibration = P.bVibration;
	// A save worth continuing: he has fallen (the prologue is marked on
	// entry), or reached a second stage, or cleared one. A profile that has
	// only changed a setting is not a game in progress.
	Menu.bHasSave = P.bSeenPrologue || P.UnlockedStages > 1 || P.ClearedStages.Num() > 0;
	// CONTINUE's tag: the furthest stage the save has opened, of the
	// campaign's nine (the browser build's CAMPAIGN; the stage table does
	// not mark the survival stage apart, so the count is the model's own)
	Menu.StageReached = Menu.bHasSave ? FMath::Clamp(P.UnlockedStages, 1, Menu.StageCount) : 0;
}

void USaudMenuSubsystem::WriteSettings()
{
	UWorld* World = GetWorld();
	USaudGameInstance* GI = World ? World->GetGameInstance<USaudGameInstance>() : nullptr;
	if (!GI)
	{
		return;
	}
	FSaudProgress& P = GI->GetMutableProgress();
	P.DifficultyIndex = FMath::Clamp(Menu.DifficultyIndex, 0, 2);
	P.SoundVolume = FMath::Clamp(Menu.SoundLevel, 0, SaudMenu::LevelMax);
	P.MusicVolume = FMath::Clamp(Menu.MusicLevel, 0, SaudMenu::LevelMax);
	P.bSound = P.SoundVolume > 0;
	P.bMusic = P.MusicVolume > 0;
	P.bVibration = Menu.bVibration;
	GI->SaveProgress();
}

/* ------------------------------------------------------------ the input */

void USaudMenuSubsystem::SetFightContext(bool bOn)
{
	const USaudInputBindings* Bindings = USaudInputBindings::Get(this);
	const APlayerController* PC = UGameplayStatics::GetPlayerController(GetWorld(), 0);
	UEnhancedInputLocalPlayerSubsystem* Input =
		PC ? ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PC->GetLocalPlayer()) : nullptr;
	const UInputMappingContext* Fight = Bindings ? Bindings->Context(SaudControls::EContext::Fight) : nullptr;
	if (!Input || !Fight)
	{
		return;
	}
	if (bOn && !Input->HasMappingContext(Fight))
	{
		Input->AddMappingContext(Fight, USaudInputBindings::FightPriority, SwapOptions());
	}
	else if (!bOn && Input->HasMappingContext(Fight))
	{
		Input->RemoveMappingContext(Fight, SwapOptions());
	}
}

void USaudMenuSubsystem::SetMenuContext(bool bOn)
{
	const USaudInputBindings* Bindings = USaudInputBindings::Get(this);
	const APlayerController* PC = UGameplayStatics::GetPlayerController(GetWorld(), 0);
	UEnhancedInputLocalPlayerSubsystem* Input =
		PC ? ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PC->GetLocalPlayer()) : nullptr;
	const UInputMappingContext* MenuCtx = Bindings ? Bindings->Context(SaudControls::EContext::Menu) : nullptr;
	if (!Input || !MenuCtx)
	{
		return;
	}
	if (bOn && !Input->HasMappingContext(MenuCtx))
	{
		Input->AddMappingContext(MenuCtx, USaudInputBindings::MenuPriority, SwapOptions());
	}
	else if (!bOn && Input->HasMappingContext(MenuCtx))
	{
		Input->RemoveMappingContext(MenuCtx, SwapOptions());
	}
}

void USaudMenuSubsystem::EnsureMenuInput(APlayerController* PC)
{
	if (MenuInput)
	{
		if (InputOwner.Get() != PC)
		{
			// a new controller (a respawn): the old component is his
			if (APlayerController* Old = InputOwner.Get())
			{
				Old->PopInputComponent(MenuInput);
			}
			MenuInput->DestroyComponent();
			MenuInput = nullptr;
		}
		else
		{
			return;
		}
	}
	const USaudInputBindings* Bindings = USaudInputBindings::Get(this);
	if (!PC || !Bindings)
	{
		return;
	}

	// NAME_None: a fixed name would re-construct a not-yet-collected old
	// component in place on a respawn.
	MenuInput = NewObject<UEnhancedInputComponent>(PC, NAME_None);
	MenuInput->RegisterComponent();
	// Nothing under this component on the stack hears a key while a menu
	// is open (the fight context is gone by then too).
	MenuInput->bBlockInput = true;

	// The actions fire through the pause by their own bTriggerWhenPaused
	// (USaudInputBindings sets it on every menu action, Pause and the
	// stick); an Enhanced Input binding carries no such flag. Nav actions
	// are held (each frame while down) and released; the rest are a press.
	const auto Bind = [this](const UInputAction* Action, ETriggerEvent Event, auto Handler)
	{
		if (Action)
		{
			MenuInput->BindAction(Action, Event, this, Handler);
		}
	};
	Bind(Bindings->Action(EAction::Confirm), ETriggerEvent::Started, &USaudMenuSubsystem::OnConfirm);
	Bind(Bindings->Action(EAction::Back), ETriggerEvent::Started, &USaudMenuSubsystem::OnBack);
	Bind(Bindings->Action(EAction::FlipPad), ETriggerEvent::Started, &USaudMenuSubsystem::OnFlip);
	Bind(Bindings->Action(EAction::Pause), ETriggerEvent::Started, &USaudMenuSubsystem::OnPauseKey);
	for (const EAction Nav : {EAction::NavUp, EAction::NavDown, EAction::NavLeft, EAction::NavRight})
	{
		Bind(Bindings->Action(Nav), ETriggerEvent::Triggered, &USaudMenuSubsystem::OnNavHeld);
		Bind(Bindings->Action(Nav), ETriggerEvent::Completed, &USaudMenuSubsystem::OnNavReleased);
	}
	Bind(Bindings->MenuStick(), ETriggerEvent::Triggered, &USaudMenuSubsystem::OnStick);
	Bind(Bindings->MenuStick(), ETriggerEvent::Completed, &USaudMenuSubsystem::OnStickReleased);
}

int32 USaudMenuSubsystem::NavBit(const UInputAction* Action) const
{
	const USaudInputBindings* Bindings = USaudInputBindings::Get(this);
	if (!Bindings || !Action)
	{
		return 0;
	}
	if (Action == Bindings->Action(EAction::NavUp)) return HeldUp;
	if (Action == Bindings->Action(EAction::NavDown)) return HeldDown;
	if (Action == Bindings->Action(EAction::NavLeft)) return HeldLeft;
	if (Action == Bindings->Action(EAction::NavRight)) return HeldRight;
	return 0;
}

void USaudMenuSubsystem::OnConfirm()
{
	Act(EAction::Confirm);
}

void USaudMenuSubsystem::OnBack()
{
	Act(EAction::Back);
}

void USaudMenuSubsystem::OnFlip()
{
	Act(EAction::FlipPad);
}

void USaudMenuSubsystem::OnPauseKey()
{
	// Escape is Back AND Pause in the menu context. On Settings or Controls
	// opened from the Pause, Back has already stepped back to the Pause
	// screen by the time this fires; acting on Pause then would resume the
	// game the player only meant to step back in. Only a press ON the pause
	// screen resumes.
	if (Menu.Screen == EScreen::Pause)
	{
		Act(EAction::Pause);
	}
}

void USaudMenuSubsystem::OnNavHeld(const FInputActionInstance& Instance)
{
	NavHeld |= NavBit(Instance.GetSourceAction());
}

void USaudMenuSubsystem::OnNavReleased(const FInputActionInstance& Instance)
{
	NavHeld &= ~NavBit(Instance.GetSourceAction());
}

void USaudMenuSubsystem::OnStick(const FInputActionValue& Value)
{
	Stick = Value.Get<FVector2D>();
}

void USaudMenuSubsystem::OnStickReleased()
{
	Stick = FVector2D::ZeroVector;
}
