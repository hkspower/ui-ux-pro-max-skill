#include "Prologue/AhmedPrologueGameMode.h"

#include "Combat/AhmedCharacter.h"
#include "Game/AhmedGameInstance.h"
#include "Kismet/GameplayStatics.h"
#include "World/WaveDirector.h"

AAhmedPrologueGameMode::AAhmedPrologueGameMode()
{
	DefaultPawnClass = AAhmedCharacter::StaticClass();
	PrimaryActorTick.bCanEverTick = false;
}

void AAhmedPrologueGameMode::BeginPlay()
{
	Super::BeginPlay();

	UAhmedGameInstance* GI = GetGameInstance<UAhmedGameInstance>();

	// Second launch onward: he has already fallen once. The level exists to
	// be seen exactly once, the same way the story only happens to him once,
	// so anyone returning to the game goes straight to where he landed.
	if (GI && GI->GetProgress().bSeenPrologue)
	{
		UGameplayStatics::OpenLevel(this, TEXT("L_SouqAlDawar"));
		return;
	}

	// Marked now, on entry, the same moment AAhmedGameMode marks a real
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
		Director->OnStageFailed.AddDynamic(this, &AAhmedPrologueGameMode::HandleDuelFailed);
	}
}

void AAhmedPrologueGameMode::HandleDuelFailed()
{
	BP_OnDuelFailed();
}
