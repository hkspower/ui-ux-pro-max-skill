#include "Game/SaudAudioSubsystem.h"
#include "Combat/SaudMenu.h"

#include "Components/AudioComponent.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "Game/SaudGameInstance.h"
#include "HAL/PlatformTime.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundBase.h"

DEFINE_LOG_CATEGORY_STATIC(LogSaudAudio, Log, All);

void USaudAudioSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	Table = SoundTable.LoadSynchronous();
	if (!Table)
	{
		UE_LOG(LogSaudAudio, Warning,
			TEXT("No sound table. Set SoundTable under [/Script/SaudFighter.SaudAudioSubsystem] ")
			TEXT("in DefaultGame.ini; every cue is silent until then."));
		return;
	}
	if (Table->GetRowStruct() != FSoundCueDef::StaticStruct())
	{
		UE_LOG(LogSaudAudio, Error, TEXT("Sound table %s is not a table of FSoundCueDef rows."),
			*Table->GetName());
		Table = nullptr;
		return;
	}
	UE_LOG(LogSaudAudio, Log, TEXT("Sound table loaded: %d cues."), Table->GetRowMap().Num());
}

USaudAudioSubsystem* USaudAudioSubsystem::Get(const UObject* WorldContext)
{
	if (!WorldContext)
	{
		return nullptr;
	}
	const UWorld* World = WorldContext->GetWorld();
	const UGameInstance* GI = World ? World->GetGameInstance() : nullptr;
	return GI ? GI->GetSubsystem<USaudAudioSubsystem>() : nullptr;
}

/* --------------------------------------------------------------- playing */

void USaudAudioSubsystem::Play(FName Cue, const AActor* Context)
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

void USaudAudioSubsystem::PlayAt(FName Cue, FVector Location)
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

float USaudAudioSubsystem::GetLead(FName Cue)
{
	const FSoundCueDef* Row = Find(Cue);
	return Row ? FMath::Max(0.f, Row->Lead) : 0.f;
}

void USaudAudioSubsystem::PlayUI(FName Cue)
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

void USaudAudioSubsystem::PlayResolved(FName Cue, const FSoundCueDef& Row, USoundBase* Sound,
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
	// of one crack into a single distorted one. On the platform's clock, not
	// the world's: a pause holds world time still, and a UI cue fired from
	// the pause menu would then sit inside the cooldown of the tap that
	// opened it for as long as the menu stayed up (this was
	// World->GetTimeSeconds() until 2026-09-30).
	const double Now = FPlatformTime::Seconds();
	if (const double* Last = LastPlayed.Find(Cue))
	{
		if (Now - *Last < Row.Cooldown)
		{
			return;
		}
	}
	LastPlayed.Add(Cue, Now);

	const float Volume = Row.Volume * GetBusVolume(Row.Bus) * ProfileLevel(Row.Bus);
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

/* ---------------------------------------------------------------- music */

void USaudAudioSubsystem::PlayMusic(FName Cue)
{
	WantedMusic = Cue;
	if (Cue.IsNone() || !BusEnabled(ESoundBus::Music))
	{
		StopMusic(MusicFadeSeconds);
		WantedMusic = Cue;		// still wanted: RefreshMusic brings it back
		return;
	}
	if (Cue == PlayingMusic && IsValid(Music) && Music->IsPlaying())
	{
		return;
	}
	const FSoundCueDef* Row = Find(Cue);
	USoundBase* Sound = Row ? Resolve(Cue, *Row) : nullptr;
	UWorld* World = GetWorld();
	if (!Sound || !World)
	{
		StopMusic(MusicFadeSeconds);
		WantedMusic = Cue;
		return;
	}

	// The old one out under the new one.
	if (IsValid(Music))
	{
		Music->FadeOut(MusicFadeSeconds, 0.f);
		Music = nullptr;
	}
	// bAutoDestroy false: the component is ours to stop. Not persisted across
	// a level transition: a new world starts its own (BeginFight / the
	// title). CreateSound2D under this marks it a UI sound, so it keeps
	// playing while the game is paused.
	Music = UGameplayStatics::SpawnSound2D(World, Sound, Row->Volume * GetBusVolume(ESoundBus::Music)
	                                       * ProfileLevel(ESoundBus::Music), 1.f, 0.f,
	                                       nullptr, false, false);
	PlayingMusic = IsValid(Music) ? Cue : NAME_None;
	if (IsValid(Music))
	{
		Music->bIsUISound = true;
	}
}

void USaudAudioSubsystem::StopMusic(float FadeSeconds)
{
	if (IsValid(Music))
	{
		if (FadeSeconds > 0.f)
		{
			Music->FadeOut(FadeSeconds, 0.f);
		}
		else
		{
			Music->Stop();
		}
	}
	Music = nullptr;
	PlayingMusic = NAME_None;
	WantedMusic = NAME_None;
}

void USaudAudioSubsystem::RefreshMusic()
{
	const FName Wanted = WantedMusic;
	if (Wanted.IsNone())
	{
		return;
	}
	PlayMusic(Wanted);
	// the cue already playing is left alone by PlayMusic: set it to the
	// level now, so a step on the MUSIC meter is heard at once
	if (IsValid(Music) && PlayingMusic == Wanted)
	{
		if (const FSoundCueDef* Row = Find(Wanted))
		{
			Music->SetVolumeMultiplier(Row->Volume * GetBusVolume(ESoundBus::Music) * ProfileLevel(ESoundBus::Music));
		}
	}
}

/* --------------------------------------------------------------- lookup */

const FSoundCueDef* USaudAudioSubsystem::Find(FName Cue)
{
	if (!Table || Cue.IsNone())
	{
		return nullptr;
	}
	static const FString Context(TEXT("USaudAudioSubsystem"));
	const FSoundCueDef* Row = Table->FindRow<FSoundCueDef>(Cue, Context, false);
	if (!Row && !Missing.Contains(Cue))
	{
		// Once. A cue the code fires that the table does not list is a bug in
		// one or the other, and it should be visible without being deafening.
		Missing.Add(Cue);
		UE_LOG(LogSaudAudio, Warning, TEXT("No row for cue '%s' in %s."),
			*Cue.ToString(), *Table->GetName());
	}
	return Row;
}

USoundBase* USaudAudioSubsystem::Resolve(FName Cue, const FSoundCueDef& Row)
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
			UE_LOG(LogSaudAudio, Log, TEXT("Cue '%s' has no asset yet (%s)."),
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
			UE_LOG(LogSaudAudio, Warning, TEXT("Cue '%s' points at %s, which did not load. ")
				TEXT("Drop the file in Content/Audio (see Content/Audio/README.md) and re-import."),
				*Cue.ToString(), *Row.Sound.ToString());
		}
		return nullptr;
	}
	Loaded.Add(Cue, Sound);
	return Sound;
}

/* ----------------------------------------------------------------- buses */

bool USaudAudioSubsystem::BusEnabled(ESoundBus Bus) const
{
	// UGameInstanceSubsystem::GetGameInstance() is not a template.
	const USaudGameInstance* GI = Cast<USaudGameInstance>(GetGameInstance());
	if (!GI)
	{
		return true;
	}
	const FSaudProgress& P = GI->GetProgress();
	return Bus == ESoundBus::Music ? (P.bMusic && P.MusicVolume > 0) : (P.bSound && P.SoundVolume > 0);
}

float USaudAudioSubsystem::ProfileLevel(ESoundBus Bus) const
{
	const USaudGameInstance* GI = Cast<USaudGameInstance>(GetGameInstance());
	if (!GI)
	{
		return 1.f;
	}
	const FSaudProgress& P = GI->GetProgress();
	const int32 Level = Bus == ESoundBus::Music ? P.MusicVolume : P.SoundVolume;
	return FMath::Clamp(static_cast<float>(Level) / static_cast<float>(SaudMenu::LevelMax), 0.f, 1.f);
}

void USaudAudioSubsystem::SetBusVolume(ESoundBus Bus, float Volume)
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

float USaudAudioSubsystem::GetBusVolume(ESoundBus Bus) const
{
	switch (Bus)
	{
	case ESoundBus::Interface: return InterfaceVolume;
	case ESoundBus::Music:     return MusicVolume;
	default:                   return EffectsVolume;
	}
}

bool USaudAudioSubsystem::HasCue(FName Cue) const
{
	if (!Table)
	{
		return false;
	}
	static const FString Context(TEXT("USaudAudioSubsystem::HasCue"));
	const FSoundCueDef* Row = Table->FindRow<FSoundCueDef>(Cue, Context, false);
	return Row && !Row->Sound.IsNull();
}
