#include "Game/SaudInputBindings.h"

#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/LocalPlayer.h"
#include "GameFramework/InputDeviceSubsystem.h"
#include "GenericPlatform/GenericPlatformInputDeviceMapper.h"
#include "InputAction.h"
#include "InputActionValue.h"
#include "InputCoreTypes.h"
#include "InputMappingContext.h"
#include "InputModifiers.h"
#include "UObject/UObjectGlobals.h"

DEFINE_LOG_CATEGORY_STATIC(LogSaudInput, Log, All);

namespace
{
	using SaudControls::EAction;
	using SaudControls::EButton;
	using SaudControls::EContext;

	/** An object name for each action: ActionName() has spaces and a slash. */
	const TCHAR* Ident(EAction A)
	{
		switch (A)
		{
		case EAction::Move: return TEXT("Move");
		case EAction::Look: return TEXT("Look");
		case EAction::Punch: return TEXT("Punch");
		case EAction::Kick: return TEXT("Kick");
		case EAction::Block: return TEXT("Block");
		case EAction::Dash: return TEXT("Dash");
		case EAction::Rage: return TEXT("Rage");
		case EAction::Pause: return TEXT("Pause");
		case EAction::NavUp: return TEXT("NavUp");
		case EAction::NavDown: return TEXT("NavDown");
		case EAction::NavLeft: return TEXT("NavLeft");
		case EAction::NavRight: return TEXT("NavRight");
		case EAction::Confirm: return TEXT("Confirm");
		case EAction::Back: return TEXT("Back");
		case EAction::FlipPad: return TEXT("FlipPad");
		default: return TEXT("Unknown");
		}
	}

	bool IsAxis(EAction A)
	{
		return A == EAction::Move || A == EAction::Look;
	}

	/** The menu's actions fire through a pause; Pause itself resumes one. */
	bool FiresWhenPaused(EAction A)
	{
		return A >= EAction::Pause;
	}

	/** A keyboard key on the Move axis: a key gives 1 on X, so W and Up are
	    swizzled onto Y, S and Down swizzled and negated, A and Left negated,
	    D and Right left as they are. */
	void MoveModifiers(const FName Key, bool& bSwizzle, bool& bNegate)
	{
		static const FName W(TEXT("W")), S(TEXT("S")), A(TEXT("A"));
		static const FName Up(TEXT("Up")), Down(TEXT("Down")), Left(TEXT("Left"));
		bSwizzle = Key == W || Key == Up || Key == S || Key == Down;
		bNegate = Key == S || Key == Down || Key == A || Key == Left;
	}
}

void USaudInputBindings::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	BuildActions();
	BuildContexts();

	// The pad in use: the engine's device subsystem says when the player's
	// most recent hardware device changes; the menu also asks each frame.
	if (UInputDeviceSubsystem* Devices = GEngine ? GEngine->GetEngineSubsystem<UInputDeviceSubsystem>() : nullptr)
	{
		Devices->OnInputHardwareDeviceChanged.AddDynamic(this, &USaudInputBindings::OnHardwareDeviceChanged);
	}
	UE_LOG(LogSaudInput, Log, TEXT("Input built from SaudControls.h: %d actions, two contexts."), Actions.Num());
}

void USaudInputBindings::Deinitialize()
{
	if (UInputDeviceSubsystem* Devices = GEngine ? GEngine->GetEngineSubsystem<UInputDeviceSubsystem>() : nullptr)
	{
		Devices->OnInputHardwareDeviceChanged.RemoveDynamic(this, &USaudInputBindings::OnHardwareDeviceChanged);
	}
	Super::Deinitialize();
}

USaudInputBindings* USaudInputBindings::Get(const UObject* WorldContext)
{
	if (!WorldContext)
	{
		return nullptr;
	}
	const UWorld* World = WorldContext->GetWorld();
	const UGameInstance* GI = World ? World->GetGameInstance() : nullptr;
	return GI ? GI->GetSubsystem<USaudInputBindings>() : nullptr;
}

/* ---------------------------------------------------------------- building */

void USaudInputBindings::BuildActions()
{
	Actions.Reset();
	Actions.SetNum(SaudControls::NumActions);
	for (int32 i = 0; i < SaudControls::NumActions; ++i)
	{
		const EAction A = static_cast<EAction>(i);
		const FName Name = MakeUniqueObjectName(this, UInputAction::StaticClass(),
		                                        FName(*FString::Printf(TEXT("IA_Saud_%s"), Ident(A))));
		UInputAction* Built = NewObject<UInputAction>(this, Name);
		Built->ValueType = IsAxis(A) ? EInputActionValueType::Axis2D : EInputActionValueType::Boolean;
		// The menu's actions must fire through a pause; the fight's context
		// is gone by then, so its actions never see one.
		Built->bTriggerWhenPaused = FiresWhenPaused(A);
		Actions[i] = Built;
	}

	MenuStickAction = NewObject<UInputAction>(
		this, MakeUniqueObjectName(this, UInputAction::StaticClass(), FName(TEXT("IA_Saud_MenuStick"))));
	MenuStickAction->ValueType = EInputActionValueType::Axis2D;
	MenuStickAction->bTriggerWhenPaused = true;
}

void USaudInputBindings::BuildContexts()
{
	FightContext = NewObject<UInputMappingContext>(
		this, MakeUniqueObjectName(this, UInputMappingContext::StaticClass(), FName(TEXT("IMC_Saud_Fight"))));
	MenuContext = NewObject<UInputMappingContext>(
		this, MakeUniqueObjectName(this, UInputMappingContext::StaticClass(), FName(TEXT("IMC_Saud_Menu"))));

	// The pad. Menu navigation on the left stick is one Axis2D action
	// (MenuStick) rather than four Boolean ones: an axis cannot say which
	// way it points to a Boolean action, so the table's four LeftStick rows
	// in the menu context are that one mapping.
	int32 NumPad = 0;
	const SaudControls::FBinding* Pads = SaudControls::PadBindings(NumPad);
	for (int32 i = 0; i < NumPad; ++i)
	{
		const SaudControls::FBinding& B = Pads[i];
		if (B.Context == EContext::Menu && B.Button == EButton::LeftStick)
		{
			continue;
		}
		const bool bStick = B.Button == EButton::LeftStick || B.Button == EButton::RightStick;
		Map(Context(B.Context), Action(B.Action), SaudControls::UEKeyName(B.Button), false, false, bStick);
	}
	Map(MenuContext, MenuStickAction, SaudControls::UEKeyName(EButton::LeftStick), false, false, true);

	// The keyboard and the mouse.
	int32 NumKeys = 0;
	const SaudControls::FKeyBinding* Keys = SaudControls::KeyBindings(NumKeys);
	for (int32 i = 0; i < NumKeys; ++i)
	{
		const SaudControls::FKeyBinding& K = Keys[i];
		bool bSwizzle = false, bNegate = false;
		if (K.Action == EAction::Move)
		{
			MoveModifiers(FName(K.KeyName), bSwizzle, bNegate);
		}
		Map(Context(K.Context), Action(K.Action), K.KeyName, bSwizzle, bNegate, false);
	}
}

bool USaudInputBindings::Map(UInputMappingContext* InContext, UInputAction* InAction, const TCHAR* KeyName,
                             bool bSwizzle, bool bNegate, bool bDeadZone)
{
	if (!InContext || !InAction || !KeyName)
	{
		return false;
	}
	const FKey Key = FKey(FName(KeyName));
	if (!Key.IsValid())
	{
		UE_LOG(LogSaudInput, Warning, TEXT("SaudControls names a key Unreal does not have: '%s' (for %s)."), KeyName,
		       *InAction->GetName());
		return false;
	}
	FEnhancedActionKeyMapping& Mapping = InContext->MapKey(InAction, Key);
	if (bNegate)
	{
		Mapping.Modifiers.Add(NewObject<UInputModifierNegate>(InContext));
	}
	if (bSwizzle)
	{
		// The default order, YXZ: the key's X becomes the action's Y.
		Mapping.Modifiers.Add(NewObject<UInputModifierSwizzleAxis>(InContext));
	}
	if (bDeadZone)
	{
		// A stick at rest is not always at zero; the modifier's default
		// radial 0.2 keeps drift out of the fight and the menu.
		Mapping.Modifiers.Add(NewObject<UInputModifierDeadZone>(InContext));
	}
	return true;
}

/* --------------------------------------------------------------- accessors */

UInputMappingContext* USaudInputBindings::Context(EContext InContext) const
{
	return InContext == EContext::Menu ? MenuContext.Get() : FightContext.Get();
}

UInputAction* USaudInputBindings::Action(EAction InAction) const
{
	const int32 I = static_cast<int32>(InAction);
	return Actions.IsValidIndex(I) ? Actions[I].Get() : nullptr;
}

/* --------------------------------------------------------------- the pad */

void USaudInputBindings::SetPad(SaudControls::EPad NewPad)
{
	if (NewPad == Pad)
	{
		return;
	}
	Pad = NewPad;
	OnPadChanged.Broadcast(Pad);
}

void USaudInputBindings::OnHardwareDeviceChanged(const FPlatformUserId UserId, const FInputDeviceId DeviceId)
{
	(void)UserId;
	(void)DeviceId;
	RefreshPad();
}

FPlatformUserId USaudInputBindings::LocalUser() const
{
	FPlatformUserId User = PLATFORMUSERID_NONE;
	if (const UGameInstance* GI = GetGameInstance())
	{
		if (const ULocalPlayer* LP = GI->GetFirstGamePlayer())
		{
			User = LP->GetPlatformUserId();
		}
	}
	if (!User.IsValid())
	{
		User = IPlatformInputDeviceMapper::Get().GetPrimaryPlatformUser();
	}
	return User;
}

void USaudInputBindings::RefreshPad()
{
	// Not const: GetMostRecentlyUsedHardwareDevice may not be.
	UInputDeviceSubsystem* Devices = GEngine ? GEngine->GetEngineSubsystem<UInputDeviceSubsystem>() : nullptr;
	if (!Devices)
	{
		return;
	}
	const FHardwareDeviceIdentifier Device = Devices->GetMostRecentlyUsedHardwareDevice(LocalUser());
	if (Device.PrimaryDeviceType == EHardwareDevicePrimaryType::KeyboardAndMouse)
	{
		SetPad(SaudControls::EPad::Keyboard);
		return;
	}
	// Both names, so "DualSense" is found whichever field the platform put
	// it in; anything else -- an Xbox pad, a generic one, no name -- is Xbox.
	const FString Name = Device.HardwareDeviceIdentifier.ToString() + TEXT(" ") + Device.InputClassName.ToString();
	SetPad(SaudControls::PadFromDeviceName(*Name));
}
