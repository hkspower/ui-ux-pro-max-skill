#include "Prologue/SaudPrologueGameMode.h"

#include "Combat/SaudCharacter.h"
#include "Combat/SaudTypes.h"
#include "Game/SaudGameInstance.h"
#include "Kismet/GameplayStatics.h"
#include "World/WaveDirector.h"

ASaudPrologueGameMode::ASaudPrologueGameMode()
{
	DefaultPawnClass = ASaudCharacter::StaticClass();
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
