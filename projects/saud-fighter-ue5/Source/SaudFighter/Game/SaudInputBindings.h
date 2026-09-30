#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Combat/SaudControls.h"
#include "SaudInputBindings.generated.h"

class UInputAction;
class UInputMappingContext;

/** The pad in the player's hand changed family (Xbox, PlayStation, or the
    keyboard): the menu's prompt strip redraws its glyphs. */
DECLARE_MULTICAST_DELEGATE_OneParam(FOnSaudPadChanged, SaudControls::EPad);

/**
 * The input, made in C++ -- 2026-09-30.
 *
 * Until this day ASaudCharacter carried six null input-asset pointers and
 * Config/DefaultInput.ini described assets nobody had made, so no input
 * ever reached the fight in C++. This builds the two mapping contexts and
 * every action at Initialize from the one table in Combat/SaudControls.h
 * (PadBindings, KeyBindings, UEKeyName), owns them for the game's life
 * (UPROPERTY, this as outer), and hands them out by context and action:
 *
 *   Fight   Move (Axis2D: left stick; W A S D and the arrows, swizzled and
 *           negated), Look (Axis2D: right stick, Mouse2D), Punch, Kick,
 *           Block, Dash, Rage, Pause
 *   Menu    NavUp/Down/Left/Right (d-pad; arrows, W S), Confirm, Back,
 *           FlipPad, Pause, and MenuStick (Axis2D: the left stick, which
 *           USaudMenuSubsystem turns into a direction with the table's
 *           repeat delays)
 *
 * Neither context is added here. USaudMenuSubsystem adds the fight context
 * when a fight starts and swaps it for the menu context, at a higher
 * priority, while a menu is open.
 *
 * The pad in use: UInputDeviceSubsystem's most recently used hardware
 * device for the local player (RefreshPad). A device whose
 * PrimaryDeviceType is KeyboardAndMouse is the Keyboard; any other's name
 * (HardwareDeviceIdentifier and InputClassName) goes through
 * SaudControls::PadFromDeviceName for the family. Read two ways: the
 * subsystem's OnInputHardwareDeviceChanged, which fires whenever the
 * player's most recent device changes -- keyboard to pad and back
 * included -- and a call from USaudMenuSubsystem::Tick each frame while a
 * menu is open, so the prompt strip can never be a frame behind the hand.
 * (FSlateApplication's pre-input key listeners were the first design;
 * SlateApplication.cpp broadcasts them only under WITH_EDITOR, so a
 * packaged game would never have detected a pad.)
 */
UCLASS()
class SAUDFIGHTER_API USaudInputBindings : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	static USaudInputBindings* Get(const UObject* WorldContext);

	/** The mapping context for a SaudControls context. */
	UInputMappingContext* Context(SaudControls::EContext InContext) const;

	/** The action for a SaudControls action (Move, Look and MenuStick are
	    Axis2D, the rest Boolean). Null only when Initialize never ran. */
	UInputAction* Action(SaudControls::EAction InAction) const;

	/** The left stick in the menu context, as an axis: the menu subsystem
	    reads it into NavUp/Down/Left/Right with the table's repeat. */
	UInputAction* MenuStick() const { return MenuStickAction; }

	/** Fight context under the menu's. */
	static constexpr int32 FightPriority = 0;
	static constexpr int32 MenuPriority = 10;

	SaudControls::EPad PadInUse() const { return Pad; }
	FOnSaudPadChanged OnPadChanged;

	/** Reads the local player's most recently used hardware device and
	    sets the pad in use from it (OnPadChanged fires when it changed). */
	void RefreshPad();

private:
	void BuildActions();
	void BuildContexts();
	/** Adds one key to a context's action; false (and a warning) when the
	    name is not an EKeys key. */
	bool Map(UInputMappingContext* InContext, UInputAction* InAction, const TCHAR* KeyName,
	         bool bSwizzle, bool bNegate, bool bDeadZone);
	void SetPad(SaudControls::EPad NewPad);

	/** UInputDeviceSubsystem::OnInputHardwareDeviceChanged. */
	UFUNCTION()
	void OnHardwareDeviceChanged(const FPlatformUserId UserId, const FInputDeviceId DeviceId);

	/** The local player's platform user, for the device subsystem. */
	FPlatformUserId LocalUser() const;

	UPROPERTY()
	TObjectPtr<UInputMappingContext> FightContext = nullptr;

	UPROPERTY()
	TObjectPtr<UInputMappingContext> MenuContext = nullptr;

	/** Indexed by SaudControls::EAction. */
	UPROPERTY()
	TArray<TObjectPtr<UInputAction>> Actions;

	UPROPERTY()
	TObjectPtr<UInputAction> MenuStickAction = nullptr;

	SaudControls::EPad Pad = SaudControls::EPad::Xbox;
};
