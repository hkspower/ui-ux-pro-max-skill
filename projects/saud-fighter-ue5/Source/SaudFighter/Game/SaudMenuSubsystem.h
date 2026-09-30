#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Combat/SaudControls.h"
#include "Combat/SaudMenu.h"
#include "SaudMenuSubsystem.generated.h"

class APlayerController;
class UEnhancedInputComponent;
class UInputAction;
struct FInputActionInstance;
struct FInputActionValue;

/**
 * The main menu and the pause -- 2026-09-30. There was neither.
 *
 * Owns the one SaudMenu::FMenuModel (Combat/SaudMenu.h, engine-free) and
 * is the engine round it: opens the Title (both game modes, at BeginPlay,
 * unless the level was opened with ?ArriveAt -- a door step) and the Pause
 * (ASaudCharacter's Pause action), binds the menu's actions from
 * USaudInputBindings on an input component of its own pushed onto the
 * player controller while a menu is open, turns the left stick into a
 * direction with SaudControls' repeat delays, feeds every action to
 * SaudMenu::Navigate and applies what comes back: the flow (start, resume,
 * quit to title, quit), the settings written to the profile and saved on
 * every change, the UI cues, the vibration test buzz. ASaudHUD asks
 * IsOpen() and Model() each DrawHUD and draws SaudMenu::Build's list.
 *
 * The contexts: the fight's mapping context is added only when a fight is
 * on (BeginFight; StartGame and Resume) and removed while a menu is open,
 * when the menu context is added at a higher priority; so Escape and Space
 * mean one thing at a time. The pause is UGameplayStatics::SetGamePaused;
 * the menu's actions fire through it (bTriggerWhenPaused on the actions,
 * bExecuteWhenPaused on the bindings) and this ticks through it too, on
 * real time, as the HUD does. The Title does not pause the world: nothing
 * can start a wave until Saud walks into one, and he cannot walk.
 */
UCLASS()
class SAUDFIGHTER_API USaudMenuSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	static USaudMenuSubsystem* Get(const UObject* WorldContext);

	/** Title or Pause: the two screens the engine opens. Pause pauses the
	    game; Title starts Music_Menu. */
	void Open(SaudMenu::EScreen Screen);

	/** Closes whatever is open, unpauses, and drops the menu context. Does
	    NOT add the fight context: BeginFight does. */
	void Close();

	/** A fight with no menu first (a door step), and what StartGame and
	    Resume end in: the fight context on, the stage music on. */
	void BeginFight();

	bool IsOpen() const { return bOpen; }
	const SaudMenu::FMenuModel& Model() const { return Menu; }

	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;
	/** The pause stops the world's tick; a paused menu still has to move. */
	virtual bool IsTickableWhenPaused() const override { return true; }

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	/** One menu action in: Navigate, then the effect. */
	void Act(SaudControls::EAction Action);
	void Apply(SaudMenu::EMenuEffect Effect);
	void ReadSettings();
	void WriteSettings();
	void SetFightContext(bool bOn);
	void SetMenuContext(bool bOn);
	/** The menu's own input component on the player controller, bound once. */
	void EnsureMenuInput(APlayerController* PC);
	void ResetHeld();
	/** The direction held now, d-pad over stick; EAction::Count for none. */
	SaudControls::EAction HeldDirection() const;
	int32 NavBit(const UInputAction* Action) const;

	// the bound handlers
	void OnConfirm();
	void OnBack();
	void OnFlip();
	void OnPauseKey();
	void OnNavHeld(const FInputActionInstance& Instance);
	void OnNavReleased(const FInputActionInstance& Instance);
	void OnStick(const FInputActionValue& Value);
	void OnStickReleased();

	SaudMenu::FMenuModel Menu;
	bool bOpen = false;
	/** True while this holds the game paused. */
	bool bPaused = false;

	UPROPERTY()
	TObjectPtr<UEnhancedInputComponent> MenuInput = nullptr;
	TWeakObjectPtr<APlayerController> InputOwner;

	/** The d-pad and the keys held now (bits: up 1, down 2, left 4, right
	    8), the stick's axis, the direction last acted on and the time to its
	    next repeat. */
	int32 NavHeld = 0;
	FVector2D Stick = FVector2D::ZeroVector;
	SaudControls::EAction LastDirection = SaudControls::EAction::Count;
	float Repeat = 0.f;
};
