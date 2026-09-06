#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Engine/DataTable.h"
#include "AhmedAudioSubsystem.generated.h"

class USoundBase;

/** Which slider a cue answers to. */
UENUM(BlueprintType)
enum class ESoundBus : uint8
{
	Effects,
	Interface,
	Music
};

/**
 * One row of DT_Sounds: a cue the game fires by name, and what plays for it.
 *
 * The game code never names an asset. It says `Audio->Play("Hit_Heavy",
 * this)` and this table decides what that is, at what volume, with how much
 * pitch drift. Recasting a sound is a table edit; the cue names are the
 * contract and they do not change.
 */
USTRUCT(BlueprintType)
struct FSoundCueDef : public FTableRowBase
{
	GENERATED_BODY()

	/** The asset to play. Soft, so a missing file logs once and the game
	    carries on rather than failing to load. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound")
	TSoftObjectPtr<USoundBase> Sound;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound")
	ESoundBus Bus = ESoundBus::Effects;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound", meta = (ClampMin = "0", ClampMax = "2"))
	float Volume = 1.f;

	/** Random pitch each play, so ten jabs in a row are not the same jab.
	    1.0 / 1.0 plays it straight. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound", meta = (ClampMin = "0.25", ClampMax = "4"))
	float PitchMin = 0.96f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound", meta = (ClampMin = "0.25", ClampMax = "4"))
	float PitchMax = 1.04f;

	/** Play in the world at the caller's position (falls off with distance)
	    rather than flat in both ears. Fight sounds yes, UI no. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound")
	bool bSpatial = true;

	/** Seconds before the same cue may fire again. Stops a five-hit combo
	    from stacking five copies of the same crack into one distorted one. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound", meta = (ClampMin = "0"))
	float Cooldown = 0.04f;

	/** What the cue is for, and what the file should sound like. Read this
	    before recording or buying a replacement. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound", meta = (MultiLine = true))
	FString Description;
};

/**
 * Plays the game's sounds by cue name.
 *
 * Everything that makes a noise -- a landed hook, a parry, a gate giving way,
 * a sealed exit refusing you -- asks for a cue by name and nothing else. The
 * table (DT_Sounds) maps names to assets, volumes and pitch drift, so the
 * sound of the game can be recast without a line of C++ changing, and a cue
 * whose asset is not there yet logs once and stays silent instead of failing.
 *
 * Three buses (effects, interface, music) each carry a volume the settings
 * screen owns; the profile's bSound and bMusic switches gate them.
 */
UCLASS(Config = Game)
class AHMEDFIGHTER_API UAhmedAudioSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;

	/** Anything in the world: hits, footsteps, gates. Positioned at Context. */
	UFUNCTION(BlueprintCallable, Category = "Audio", meta = (DefaultToSelf = "Context"))
	void Play(FName Cue, const AActor* Context);

	UFUNCTION(BlueprintCallable, Category = "Audio")
	void PlayAt(FName Cue, FVector Location);

	/** Flat in both ears, regardless of the row's bSpatial: menus, banners. */
	UFUNCTION(BlueprintCallable, Category = "Audio")
	void PlayUI(FName Cue);

	UFUNCTION(BlueprintCallable, Category = "Audio")
	void SetBusVolume(ESoundBus Bus, float Volume);

	UFUNCTION(BlueprintPure, Category = "Audio")
	float GetBusVolume(ESoundBus Bus) const;

	/** True when the table has a row for the cue AND its asset loaded. */
	UFUNCTION(BlueprintPure, Category = "Audio")
	bool HasCue(FName Cue) const;

	/** Convenience for anything holding a world. */
	static UAhmedAudioSubsystem* Get(const UObject* WorldContext);

protected:
	/** DT_Sounds. Set in DefaultGame.ini; the subsystem is inert without it. */
	UPROPERTY(Config, EditAnywhere, Category = "Audio")
	TSoftObjectPtr<UDataTable> SoundTable;

	UPROPERTY(Config, EditAnywhere, Category = "Audio", meta = (ClampMin = "0", ClampMax = "1"))
	float EffectsVolume = 1.f;

	UPROPERTY(Config, EditAnywhere, Category = "Audio", meta = (ClampMin = "0", ClampMax = "1"))
	float InterfaceVolume = 0.9f;

	UPROPERTY(Config, EditAnywhere, Category = "Audio", meta = (ClampMin = "0", ClampMax = "1"))
	float MusicVolume = 0.8f;

private:
	const FSoundCueDef* Find(FName Cue);
	USoundBase* Resolve(FName Cue, const FSoundCueDef& Row);
	bool BusEnabled(ESoundBus Bus) const;
	void PlayResolved(FName Cue, const FSoundCueDef& Row, USoundBase* Sound,
		const FVector* Location);

	UPROPERTY() TObjectPtr<UDataTable> Table;
	/** Resolved assets, so a soft pointer is loaded once per cue, not per hit. */
	UPROPERTY() TMap<FName, TObjectPtr<USoundBase>> Loaded;
	TSet<FName> Missing;			// logged once each
	TMap<FName, double> LastPlayed;	// cooldowns
};
