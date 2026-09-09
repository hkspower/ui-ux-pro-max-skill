#include "Game/AhmedAudioSubsystem.h"

#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "Game/AhmedGameInstance.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundBase.h"

DEFINE_LOG_CATEGORY_STATIC(LogAhmedAudio, Log, All);

void UAhmedAudioSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	Table = SoundTable.LoadSynchronous();
	if (!Table)
	{
		UE_LOG(LogAhmedAudio, Warning,
			TEXT("No sound table. Set SoundTable under [/Script/AhmedFighter.AhmedAudioSubsystem] ")
			TEXT("in DefaultGame.ini; every cue is silent until then."));
		return;
	}
	if (Table->GetRowStruct() != FSoundCueDef::StaticStruct())
	{
		UE_LOG(LogAhmedAudio, Error, TEXT("Sound table %s is not a table of FSoundCueDef rows."),
			*Table->GetName());
		Table = nullptr;
		return;
	}
	UE_LOG(LogAhmedAudio, Log, TEXT("Sound table loaded: %d cues."), Table->GetRowMap().Num());
}

UAhmedAudioSubsystem* UAhmedAudioSubsystem::Get(const UObject* WorldContext)
{
	if (!WorldContext)
	{
		return nullptr;
	}
	const UWorld* World = WorldContext->GetWorld();
	const UGameInstance* GI = World ? World->GetGameInstance() : nullptr;
	return GI ? GI->GetSubsystem<UAhmedAudioSubsystem>() : nullptr;
}

/* --------------------------------------------------------------- playing */

void UAhmedAudioSubsystem::Play(FName Cue, const AActor* Context)
{
	if (Context)
	{
		const FVector Loc = Context->GetActorLocation();
		PlayAt(Cue, Loc);
	}
	else
	{
		PlayUI(Cue);
	}
}

void UAhmedAudioSubsystem::PlayAt(FName Cue, FVector Location)
{
	const FSoundCueDef* Row = Find(Cue);
	if (!Row)
	{
		return;
	}
	USoundBase* Sound = Resolve(Cue, *Row);
	if (!Sound)
	{
		return;
	}
	PlayResolved(Cue, *Row, Sound, Row->bSpatial ? &Location : nullptr);
}

float UAhmedAudioSubsystem::GetLead(FName Cue)
{
	const FSoundCueDef* Row = Find(Cue);
	return Row ? FMath::Max(0.f, Row->Lead) : 0.f;
}

void UAhmedAudioSubsystem::PlayUI(FName Cue)
{
	const FSoundCueDef* Row = Find(Cue);
	if (!Row)
	{
		return;
	}
	USoundBase* Sound = Resolve(Cue, *Row);
	if (!Sound)
	{
		return;
	}
	PlayResolved(Cue, *Row, Sound, nullptr);
}

void UAhmedAudioSubsystem::PlayResolved(FName Cue, const FSoundCueDef& Row, USoundBase* Sound,
	const FVector* Location)
{
	if (!BusEnabled(Row.Bus))
	{
		return;
	}

	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	// The cooldown is what keeps a five-hit combo from stacking five copies
	// of one crack into a single distorted one.
	const double Now = World->GetTimeSeconds();
	if (const double* Last = LastPlayed.Find(Cue))
	{
		if (Now - *Last < Row.Cooldown)
		{
			return;
		}
	}
	LastPlayed.Add(Cue, Now);

	const float Volume = Row.Volume * GetBusVolume(Row.Bus);
	const float Pitch  = FMath::FRandRange(FMath::Min(Row.PitchMin, Row.PitchMax),
		FMath::Max(Row.PitchMin, Row.PitchMax));

	if (Location)
	{
		UGameplayStatics::PlaySoundAtLocation(World, Sound, *Location, Volume, Pitch);
	}
	else
	{
		UGameplayStatics::PlaySound2D(World, Sound, Volume, Pitch);
	}
}

/* --------------------------------------------------------------- lookup */

const FSoundCueDef* UAhmedAudioSubsystem::Find(FName Cue)
{
	if (!Table || Cue.IsNone())
	{
		return nullptr;
	}
	static const FString Context(TEXT("UAhmedAudioSubsystem"));
	const FSoundCueDef* Row = Table->FindRow<FSoundCueDef>(Cue, Context, false);
	if (!Row && !Missing.Contains(Cue))
	{
		// Once. A cue the code fires that the table does not list is a bug in
		// one or the other, and it should be visible without being deafening.
		Missing.Add(Cue);
		UE_LOG(LogAhmedAudio, Warning, TEXT("No row for cue '%s' in %s."),
			*Cue.ToString(), *Table->GetName());
	}
	return Row;
}

USoundBase* UAhmedAudioSubsystem::Resolve(FName Cue, const FSoundCueDef& Row)
{
	if (TObjectPtr<USoundBase>* Found = Loaded.Find(Cue))
	{
		return *Found;
	}
	if (Row.Sound.IsNull())
	{
		if (!Missing.Contains(Cue))
		{
			Missing.Add(Cue);
			UE_LOG(LogAhmedAudio, Log, TEXT("Cue '%s' has no asset yet (%s)."),
				*Cue.ToString(), *Row.Description);
		}
		return nullptr;
	}
	USoundBase* Sound = Row.Sound.LoadSynchronous();
	if (!Sound)
	{
		if (!Missing.Contains(Cue))
		{
			Missing.Add(Cue);
			UE_LOG(LogAhmedAudio, Warning, TEXT("Cue '%s' points at %s, which did not load. ")
				TEXT("Drop the file in Content/Audio (see Content/Audio/README.md) and re-import."),
				*Cue.ToString(), *Row.Sound.ToString());
		}
		return nullptr;
	}
	Loaded.Add(Cue, Sound);
	return Sound;
}

/* ----------------------------------------------------------------- buses */

bool UAhmedAudioSubsystem::BusEnabled(ESoundBus Bus) const
{
	const UAhmedGameInstance* GI = GetGameInstance<UAhmedGameInstance>();
	if (!GI)
	{
		return true;
	}
	const FAhmedProgress& P = GI->GetProgress();
	return Bus == ESoundBus::Music ? P.bMusic : P.bSound;
}

void UAhmedAudioSubsystem::SetBusVolume(ESoundBus Bus, float Volume)
{
	Volume = FMath::Clamp(Volume, 0.f, 1.f);
	switch (Bus)
	{
	case ESoundBus::Effects:   EffectsVolume   = Volume; break;
	case ESoundBus::Interface: InterfaceVolume = Volume; break;
	case ESoundBus::Music:     MusicVolume     = Volume; break;
	}
	SaveConfig();
}

float UAhmedAudioSubsystem::GetBusVolume(ESoundBus Bus) const
{
	switch (Bus)
	{
	case ESoundBus::Interface: return InterfaceVolume;
	case ESoundBus::Music:     return MusicVolume;
	default:                   return EffectsVolume;
	}
}

bool UAhmedAudioSubsystem::HasCue(FName Cue) const
{
	if (!Table)
	{
		return false;
	}
	static const FString Context(TEXT("UAhmedAudioSubsystem::HasCue"));
	const FSoundCueDef* Row = Table->FindRow<FSoundCueDef>(Cue, Context, false);
	return Row && !Row->Sound.IsNull();
}
