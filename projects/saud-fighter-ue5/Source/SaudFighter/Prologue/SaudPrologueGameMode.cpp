#include "Prologue/SaudPrologueGameMode.h"

#include "Combat/SaudCharacter.h"
#include "Game/SaudHUD.h"
#include "Combat/SaudTypes.h"
#include "Game/SaudGameInstance.h"
#include "Game/SaudMenuSubsystem.h"
#include "Kismet/GameplayStatics.h"
#include "World/WaveDirector.h"

ASaudPrologueGameMode::ASaudPrologueGameMode()
{
	DefaultPawnClass = ASaudCharacter::StaticClass();
	HUDClass = ASaudHUD::StaticClass();
	PrimaryActorTick.bCanEverTick = false;
}

void ASaudPrologueGameMode::BeginPlay()
{
	Super::BeginPlay();

	USaudGameInstance* GI = GetGameInstance<USaudGameInstance>();

	// Second launch onward: he has already fallen once. The level exists to
	// be seen exactly once, the same way the story only happens to him once,
	// so anyone returning to the game goes straight to where he landed.
	if (GI && GI->GetProgress().bSeenPrologue)
	{
		UGameplayStatics::OpenLevel(this, SaudGameplay::WorldLevel);
		return;
	}

	// The title first, read from the profile as it is on entry: a first
	// run has no save, so it says FIGHT, and the duel starts on it. The
	// pawn has no fight input until then. (A door step, ?ArriveAt, would
	// skip it; nothing opens this level that way.)
	if (USaudMenuSubsystem* Menu = USaudMenuSubsystem::Get(this))
	{
		if (UGameplayStatics::ParseOption(OptionsString, TEXT("ArriveAt")).IsEmpty())
		{
			Menu->Open(SaudMenu::EScreen::Title);
		}
		else
		{
			Menu->BeginFight();
		}
	}

	// Marked now, on entry, the same moment ASaudGameMode marks a real
	// stage visited -- not on the fall. A player who quits partway through
	// has still been here; the prologue is not a gate anything is locked
	// behind, so there is nothing to lose by not making him repeat it.
	if (GI)
	{
		GI->GetMutableProgress().bSeenPrologue = true;
		GI->SaveProgress();
	}

	if (AWaveDirector* Director = AWaveDirector::Get(GetWorld()))
	{
		Director->OnStageFailed.AddDynamic(this, &ASaudPrologueGameMode::HandleDuelFailed);
	}
}

void ASaudPrologueGameMode::HandleDuelFailed()
{
	BP_OnDuelFailed();
}
