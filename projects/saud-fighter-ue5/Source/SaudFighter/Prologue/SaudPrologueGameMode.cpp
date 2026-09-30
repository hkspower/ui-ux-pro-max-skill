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
	// skip it; nothing opens this level that way.) The level is marked seen
	// when the fight starts (MarkSeen, from USaudMenuSubsystem::BeginFight),
	// not here: a player who quits at that first title has not been through
	// it. Once the fight is on, a player who quits partway has still been
	// here; the prologue is not a gate anything is locked behind.
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

	if (AWaveDirector* Director = AWaveDirector::Get(GetWorld()))
	{
		Director->OnStageFailed.AddDynamic(this, &ASaudPrologueGameMode::HandleDuelFailed);
	}
}

void ASaudPrologueGameMode::MarkSeen()
{
	USaudGameInstance* GI = GetGameInstance<USaudGameInstance>();
	if (GI && !GI->GetProgress().bSeenPrologue)
	{
		GI->GetMutableProgress().bSeenPrologue = true;
		GI->SaveProgress();
	}
}

void ASaudPrologueGameMode::HandleDuelFailed()
{
	BP_OnDuelFailed();
}
