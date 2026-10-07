#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Combat/SaudAnime.h"
#include "Combat/SaudFire.h"
#include "Combat/SaudTypes.h"
#include "SaudLookSubsystem.generated.h"

class AActor;
class AFighterBase;
class ASaudCharacter;
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
 * impact frame, the speed lines and their centre, and the boil (the seed
 * the ink's brush and the film grain move on, on twos) into MPC_Anime from
 * SaudAnime::FState, in real time, because the impact frame is drawn during
 * the freeze. USaudFeelSubsystem::OnBlow hands every blow on.
 *
 * Fighters are told apart from the world by custom depth, which
 * AFighterBase turns on for its mesh: they get the heavy ink line.
 *
 * HAWK FIST's fire (Combat/SaudFire.h) is drawn by M_Anime_Frame too:
 * each tick this projects Saud's burning fist -- where it is on the
 * screen, which way the forearm points, how deep, how big one of the
 * browser's figure pixels is at that distance -- and, after a burning
 * punch lands, the man it landed on, into MPC_Anime. The state itself
 * (the eased flame, the burst's clock) is the player's, in game time.
 *
 * The hit effects of the dark seinen (since 2026-09-28) go through the
 * same collection: the impact frame's tone (a blow's blood, a parry's bone,
 * a burning punch's ember -- OnBurn retags the frame OnBlow just started),
 * the wound border when the player is the one hit, and the mark where a
 * heavy blow landed, projected each tick from the victim as he moves, the
 * same way the fire's burst is.
 *
 * The System's events (2026-10-07): the windows track calls OnSystemEvent
 * when the System speaks -- a level, a skill, a rank, a quest done, a gate
 * opened -- and the picture answers (SaudAnime::SystemFx): a pillar of cyan
 * light round Saud, a ring burst and a rim on him, a wider ring, a glow
 * round the screen's edge, a flash at the gate. Their ages run in real time
 * and Saud and the gate are projected each tick, as the fire's fist is. And
 * a heavy blow of Saud's that lands leaves a thin cyan trail along the path
 * his striking limb took (SystemFx::FTrail): the limb's tip is recorded
 * through every heavy swing of his and the last 0.12 s of it taken when the
 * blow lands.
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

	/** A burning HAWK FIST punch landed on Victim: the burst is drawn on
	    him for as long as ASaudCharacter's SaudFire::FState says, and the
	    impact frame that same blow started (OnBlow runs first, in the same
	    call) goes ember. */
	void OnBurn(const AFighterBase* Victim);

	/** The System spoke (the windows track, SaudSystemSubsystem): the picture
	    shows Fx. Where is what it happened at -- the gate for GateOpened (no
	    gate, no flash); a level, a skill and a rank are drawn about the
	    player's Saud whatever Where is, and a quest round the screen. Skill:
	    the talent a SkillAcquired gave -- HAWK FIST's is drawn in violet and
	    ember; left None, the System's cyan and ice. */
	void OnSystemEvent(SaudAnime::ESystemFx Fx, const AActor* Where, EAbility Skill = EAbility::None);

	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void Deinitialize() override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	SaudAnime::FState Look;

	/** Saud's power-up (2026-10-03): his aura's level, eased in real time. */
	SaudAnime::Power::FPower Power;

	/** The System's events in the picture, and the trail on his heavy blows
	    (2026-10-07), in real time. */
	SaudAnime::SystemFx::FEvents SysFx;
	SaudAnime::SystemFx::FTrail Trail;

	/** Real seconds since the world began: the trail's samples are stamped
	    with it. */
	float RealClock = 0.f;

	/** The heavy swing whose limb is being recorded (None between swings). */
	FName TrailRow = NAME_None;

	/** The gate a GateOpened flash is drawn at. */
	TWeakObjectPtr<const AActor> FlashAt;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialParameterCollection> Collection = nullptr;

	UPROPERTY(Transient)
	TObjectPtr<APostProcessVolume> Volume = nullptr;

	/** Who the last blow landed on: the speed lines are centred on him,
	    followed while they last. */
	TWeakObjectPtr<const AFighterBase> Victim;

	/** Who the last burning punch landed on: the burst is drawn on him. */
	TWeakObjectPtr<const AFighterBase> Burned;

	/** Who the last mark was made on, and where on him the blow landed
	    (Hit.ImpactPoint less his location): the mark follows him. */
	TWeakObjectPtr<const AFighterBase> MarkVictim;
	FVector MarkOffset = FVector::ZeroVector;

	/** The MPC_Anime scalars written through Write(), a slot each. Sized
	    (since 2026-09-28) for every scalar the look and the hit effects
	    write each frame, the impact's tone, the wound and the hit mark's
	    included; it was seven magic numbers. */
	enum class ESlot : uint8
	{
		Impact, Invert, Speed, Seed, FireHeat, BurnAge, Boil,
		Tone, Wound, MarkAge, MarkX, MarkY, MarkDepth, MarkScale, MarkSeed,
		Aura, AuraTime,
		SysPillarAge, SysBurstAge, SysBurstHawk, SysRankAge, SysQuestAge, SysFlashAge, TrailAge,
		Count
	};

	/** Last values written, so an idle frame writes nothing; -1 from the
	    world's BeginPlay until the first write. */
	float Written[static_cast<int32>(ESlot::Count)] = {};

	void Write(ESlot Slot, const TCHAR* Name, float Value);
	void Set(const TCHAR* Name, float Value);
	bool VictimOnScreen(float& OutX, float& OutY) const;
	void WriteFire(const ASaudCharacter* Saud);
	void WriteMark();
	/** Saud's aura and eyes: the level from his rage and the finisher, his
	    middle and his eyes projected as the fire's fist is. */
	void WritePower(const ASaudCharacter* Saud, float RealSeconds);
	/** The System's events: their ages, Saud's middle and feet while one is
	    drawn about him, the gate's point while it flashes. */
	void WriteSystem(const ASaudCharacter* Saud);
	/** The trail: the striking limb's tip recorded through a heavy swing of
	    his, and the trail's points projected while it shows. */
	void RecordTrail(const ASaudCharacter* Saud);
	void WriteTrail();
	/** The world position of the tip Saud's current strike lands with (the
	    knuckles, the ball of the foot, the knee); false between strikes. */
	bool StrikingTip(const ASaudCharacter* Saud, FVector& OutTip) const;
	/** A world point as the fire parameters want it: viewport fraction (Y
	    down), scene depth in cm, and the size of one figure pixel there as
	    a fraction of the viewport's height. False when it cannot be seen. */
	bool Project(const FVector& At, float& OutX, float& OutY, float& OutDepth, float& OutScale) const;
};
