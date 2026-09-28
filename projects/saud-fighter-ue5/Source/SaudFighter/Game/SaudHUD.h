#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "Combat/SaudAnime.h"
#include "SaudHUD.generated.h"

class AEnemyFighter;

/**
 * The fight HUD -- since 2026-09-24, with the anime look; until then this
 * build had no HUD at all: no class, no widget, no Blueprint; the
 * fighters' health existed only as numbers. Drawn as a manga page until
 * 2026-09-26, as a dark fantasy's until 2026-09-28 ("use darker theme style
 * like Demon's Souls": dark plates, bronze keylines, thin flat bars), and
 * since then as a dark seinen's ("make all game like dark anime adult
 * style").
 *
 * Top left, Saud's corner on a torn ink-wash sweep: his name, his rage as
 * five leaning cuts, his stamina in ash, his health a leaning blood slash
 * with a bone trail that holds for a beat and then drains, and blood
 * dripping under it at low health. Right, the combo count on an ink-rimmed
 * blood splat once it reaches two, punching as it goes up. Bottom, a
 * boss's name on a manga title panel that wipes open when he is first
 * seen, over a blood slash (ember when he is enraged) and his bar. Over a
 * street man's head, a short leaning bar for a while after he is hit.
 *
 * Every shape, colour and number is SaudHud::Build's (Combat/SaudAnime.h),
 * a pure function the harness checks -- title-safe, apart, out of the
 * fight, legible, 3:1 bars -- on what it draws, and Tools/look/
 * hud_preview.py draws without an engine. This gathers the game's state
 * into an FHudState and rasterises Build's list: its triangles batched
 * into one Canvas triangle item between texts, so the order is kept, and
 * each text stroked in ink. Canvas, not UMG: it needs no asset, so it works
 * the first time the project opens.
 */
UCLASS()
class SAUDFIGHTER_API ASaudHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;

private:
	struct FEnemyMark
	{
		float LastHealth = -1.f;
		float Since = 1000.f;           // seconds since he was last hit
		SaudHud::FGhost Ghost;
	};

	SaudHud::FGhost PlayerGhost;
	SaudHud::FGhost BossGhost;
	TWeakObjectPtr<AEnemyFighter> Boss;
	/** Clock when the boss was first seen: his banner's reveal. */
	float BossFoundAt = 0.f;
	TMap<TWeakObjectPtr<AEnemyFighter>, FEnemyMark> Marks;

	int32 LastCombo = 0;
	float SinceComboHit = 1000.f;
	float Clock = 0.f;

	/** Build's output: about 80 KB, so a member, not on the stack. */
	SaudHud::FDrawList List;

	void GatherPlayer(SaudHud::FHudState& State, float Dt);
	void GatherBoss(SaudHud::FHudState& State, float Dt);
	void GatherStreet(SaudHud::FHudState& State, float Dt);

	/** Draws the list in its order: triangles, flushed before each text. */
	void Emit();
	void Flush(int32 From, int32 To);
	void Text(const SaudHud::FHudText& Item, const FString& S);
};
