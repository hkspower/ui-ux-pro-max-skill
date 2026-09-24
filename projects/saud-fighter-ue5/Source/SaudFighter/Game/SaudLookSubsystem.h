#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Combat/SaudAnime.h"
#include "SaudLookSubsystem.generated.h"

class AFighterBase;
class APostProcessVolume;
class UMaterialInterface;
class UMaterialParameterCollection;
struct FHitResultData;

/**
 * The anime look, in the world: puts M_Anime_Post over everything and
 * moves it when a blow lands.
 *
 * At the world's BeginPlay it spawns one unbound post-process volume
 * carrying the material, so every camera -- the player's boom, a cutscene's,
 * a respawn's -- sees the same picture with nothing wired per level; the
 * level builders do not need to know it exists. Every tick it writes the
 * impact frame, the speed lines and their centre into MPC_Anime from
 * SaudAnime::FState, in real time, because the impact frame is drawn during
 * the freeze. USaudFeelSubsystem::OnBlow hands every blow on.
 *
 * Fighters are told apart from the world by custom depth, which
 * AFighterBase turns on for its mesh: they get the heavy ink line.
 *
 * If the assets are not there (the editor script has not been run), it
 * logs once and does nothing: the game is exactly the game without it.
 */
UCLASS()
class SAUDFIGHTER_API USaudLookSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	static USaudLookSubsystem* Get(const UObject* WorldContext);

	/** A blow landed on Victim: parried, blocked or clean, as Hit says. */
	void OnBlow(const AFighterBase* Victim, const FHitResultData& Hit, bool bHeavy);

	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void Deinitialize() override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	SaudAnime::FState Look;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialParameterCollection> Collection = nullptr;

	UPROPERTY(Transient)
	TObjectPtr<APostProcessVolume> Volume = nullptr;

	/** Who the last blow landed on: the speed lines are centred on him,
	    followed while they last. */
	TWeakObjectPtr<const AFighterBase> Victim;

	/** Last values written, so an idle frame writes nothing. */
	float Written[5] = {-1.f, -1.f, -1.f, -1.f, -1.f};

	void Write(int32 Slot, const TCHAR* Name, float Value);
	bool VictimOnScreen(float& OutX, float& OutY) const;
};
