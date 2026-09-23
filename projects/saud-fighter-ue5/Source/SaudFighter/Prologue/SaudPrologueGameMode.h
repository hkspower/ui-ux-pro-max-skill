#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "SaudPrologueGameMode.generated.h"

/**
 * The game mode for L_Prologue, and nowhere else.
 *
 * L_Prologue is Saud's life before he fell: one bout, then a short walk to
 * the hole in the street. It is not a stage. It has no row in DT_Stages, it
 * is not on the ring map, it pays no XP and it earns no rank -- ASaudGameMode
 * exists to write a fight into that economy, and this one is not in it. So
 * the level gets its own small game mode rather than a special case bolted
 * onto the one every real stage shares.
 *
 * The duel itself needs no new code: it is one ordinary AWaveDirector with a
 * single wave, and the fall is one ordinary AAreaExit pointed at
 * L_AlHalqa_World, the open world. AAreaExit already refuses to open while the director it
 * shares a level with is arena-locked, so "he cannot leave until he has won"
 * falls out of machinery that already exists -- see Tools/levels/
 * build_prologue.py for how the two are placed.
 *
 * Losing the bout is handled exactly as a real stage handles losing one:
 * AWaveDirector broadcasts OnStageFailed and a Blueprint decides what a
 * player sees and whether the level reloads. Nothing here forces a KO into a
 * restart, because nothing in ASaudGameMode does either -- see its own
 * BP_OnStageFailed. "He wins" is the story, not a rule this class enforces;
 * a player who is knocked down is shown that and left to try again, the same
 * as everywhere else in the game.
 */
UCLASS()
class SAUDFIGHTER_API ASaudPrologueGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	ASaudPrologueGameMode();

	virtual void BeginPlay() override;

	/** Mirrors ASaudGameMode::BP_OnStageFailed: the bout is lost, the level
	    has not changed under the player, and it is Blueprint's to decide what
	    that looks like. */
	UFUNCTION(BlueprintImplementableEvent, Category = "Prologue", meta = (DisplayName = "On Duel Failed"))
	void BP_OnDuelFailed();

protected:
	UFUNCTION()
	void HandleDuelFailed();
};
