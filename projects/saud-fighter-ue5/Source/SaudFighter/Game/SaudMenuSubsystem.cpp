#include "Game/SaudMenuSubsystem.h"
#include "Combat/SaudTypes.h"
#include "Game/SaudAudioSubsystem.h"
#include "Game/SaudFeelSubsystem.h"
#include "Game/SaudGameInstance.h"
#include "Game/SaudInputBindings.h"

#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformMisc.h"
#include "InputAction.h"
#include "InputActionValue.h"
#include "InputMappingContext.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/App.h"

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
	if (const USaudInputBindings* Bindings = USaudInputBindings::Get(this))
	{
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

	USaudAudioSubsystem* Audio = USaudAudioSubsystem::Get(this);
	if (Screen == EScreen::Pause)
	{
		if (!bPaused)
		{
			UGameplayStatics::SetGamePaused(this, true);
			bPaused = true;
		}
	}
	else if (Audio)
	{
		Audio->PlayMusic(TEXT("Music_Menu"));
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
}

/* ------------------------------------------------------------ the tick */

void USaudMenuSubsystem::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
	if (!bOpen)
	{
		return;
	}
	// DeltaTime is the world's, which a pause holds at zero. The pulse and
	// the wipe run on the frame's real length, as the HUD's clock does.
	const float Real = FMath::Clamp(static_cast<float>(FApp::GetDeltaTime()), 0.f, 0.1f);
	Menu.Clock += Real;
	Menu.Since += Real;

	if (const USaudInputBindings* Bindings = USaudInputBindings::Get(this))
	{
		Menu.Pad = Bindings->PadInUse();
	}

	// The held direction: once when it changes, and up / down again after
	// NavRepeatFirst, then every NavRepeatNext, while it is held. Left and
	// right do not repeat -- they toggle a setting, and a held toggle would
	// flip it eight times a second.
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
	else if (Direction == EAction::NavUp || Direction == EAction::NavDown)
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
		Cue(TEXT("UI_Tap"));
		BeginFight();
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
		FPlatformMisc::RequestExit(false);
		break;

	case EMenuEffect::ToggleSound:
		WriteSettings();
		Cue(TEXT("UI_Tap"));		// audible only when it went on: the bus is gated
		break;

	case EMenuEffect::ToggleMusic:
		WriteSettings();
		if (Audio)
		{
			Audio->RefreshMusic();
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
	Menu.bSound = P.bSound;
	Menu.bMusic = P.bMusic;
	Menu.bVibration = P.bVibration;
	// A save worth continuing: he has fallen (the prologue is marked on
	// entry), or reached a second stage, or cleared one. A profile that has
	// only changed a setting is not a game in progress.
	Menu.bHasSave = P.bSeenPrologue || P.UnlockedStages > 1 || P.ClearedStages.Num() > 0;
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
	P.bSound = Menu.bSound;
	P.bMusic = Menu.bMusic;
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

	MenuInput = NewObject<UEnhancedInputComponent>(PC, TEXT("SaudMenuInput"));
	MenuInput->RegisterComponent();
	// Nothing under this component on the stack hears a key while a menu
	// is open (the fight context is gone by then too).
	MenuInput->bBlockInput = true;

	// Every binding fires through the pause. Nav actions are held (each
	// frame while down) and released; the rest are a press.
	const auto Bind = [this](const UInputAction* Action, ETriggerEvent Event, auto Handler)
	{
		if (Action)
		{
			FEnhancedInputActionEventBinding& Binding = MenuInput->BindAction(Action, Event, this, Handler);
			Binding.bExecuteWhenPaused = true;
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
	Act(EAction::Pause);
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
