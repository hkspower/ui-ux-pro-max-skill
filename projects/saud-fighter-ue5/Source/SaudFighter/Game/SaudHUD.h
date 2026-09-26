#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "Combat/SaudAnime.h"
#include "SaudHUD.generated.h"

class AEnemyFighter;
class UFont;

/**
 * The fight HUD -- since 2026-09-24, with the anime look; until then this
 * build had no HUD at all: no class, no widget, no Blueprint; the
 * fighters' health existed only as numbers. Drawn as a manga page until
 * 2026-09-26, and since then as a dark fantasy's ("use darker theme style
 * like Demon's Souls"): dark plates, bronze keylines, bone lettering,
 * thin flat bars.
 *
 * Top left, Saud's plate: his name, his health in a deep blood-red with a
 * dim gold trail that holds for a beat and then drains to it, his stamina
 * in moss green under it, his rage as five small gold blocks. Right, the
 * combo count on a serrated seal once it reaches two, punching as it goes
 * up. Bottom, a boss's name over a thin oxblood bar. Over a street man's
 * head, a short bar for a while after he is hit.
 *
 * Every shape and number is SaudHud's (Combat/SaudAnime.h), which the
 * harness checks for the title-safe area and for type legible from a
 * couch at every screen shape; this only draws them. Canvas, not UMG: it
 * needs no asset, so it works the first time the project opens.
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
	TMap<TWeakObjectPtr<AEnemyFighter>, FEnemyMark> Marks;

	int32 LastCombo = 0;
	float SinceComboHit = 1000.f;
	float Clock = 0.f;

	void DrawPlayer(const SaudHud::FPage& Page, const SaudHud::FLayout& L, float Dt);
	void DrawCombo(const SaudHud::FPage& Page, const SaudHud::FLayout& L, float Dt);
	void DrawBoss(const SaudHud::FPage& Page, const SaudHud::FLayout& L, float Dt);
	void DrawStreetBars(const SaudHud::FPage& Page, const SaudHud::FLayout& L, float Dt);

	void Poly(const SaudHud::FPoint* Points, int32 Count, const FLinearColor& Colour);
	void InkBar(const SaudHud::FPage& Page, const SaudHud::FRect& R, float Fill, float Ghost,
	            const FLinearColor& Colour);
	void Panel(const SaudHud::FPage& Page, const SaudHud::FRect& R, const FLinearColor& Fill);
	void Text(const FString& S, float X, float Y, float HeightPx, const FLinearColor& Colour,
	          bool bCentre = false);
};
