#include "Game/SaudHUD.h"
#include "Combat/EnemyFighter.h"
#include "Combat/SaudCharacter.h"

#include "CanvasItem.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Misc/App.h"
#include "TextureResource.h"

using namespace SaudHud;

namespace
{
	// The anime look's paper and ink (Tools/look/anime_look.py LOOK), and
	// Saud's own red (assets/saud.js col.band).
	const FLinearColor InkC(0.030f, 0.026f, 0.024f, 1.f);
	const FLinearColor PaperC(0.93f, 0.90f, 0.84f, 1.f);
	const FLinearColor ShadeC(0.36f, 0.34f, 0.32f, 1.f);
	const FLinearColor SaudRed = FLinearColor::FromSRGBColor(FColor(0xff, 0x1a, 0x3c));
	const FLinearColor EnemyRed = FLinearColor::FromSRGBColor(FColor(0x9e, 0x1b, 0x22));
	const FLinearColor StaminaC = FLinearColor::FromSRGBColor(FColor(0xd9, 0xb3, 0x5a));
	const FLinearColor RageGold = FLinearColor::FromSRGBColor(FColor(0xff, 0xc4, 0x2e));
}

void ASaudHUD::DrawHUD()
{
	Super::DrawHUD();
	if (!Canvas)
	{
		return;
	}
	// Real time: the freeze stops the fight, not the page.
	const float Dt = FMath::Clamp(static_cast<float>(FApp::GetDeltaTime()), 0.f, 0.1f);
	Clock += Dt;

	const FPage Page = FPage::For(Canvas->ClipX, Canvas->ClipY);
	const FLayout L = Lay(Page);
	DrawStreetBars(Page, L, Dt);
	DrawPlayer(Page, L, Dt);
	DrawCombo(Page, L, Dt);
	DrawBoss(Page, L, Dt);
}

/* ------------------------------------------------------------ the panels */

void ASaudHUD::DrawPlayer(const FPage& Page, const FLayout& L, float Dt)
{
	const ASaudCharacter* Saud = Cast<ASaudCharacter>(GetOwningPawn());
	if (!Saud)
	{
		return;
	}
	const float HealthF = Saud->GetHealthFraction();
	PlayerGhost.Tick(HealthF, Dt);

	Panel(Page, L.PlayerPanel, PaperC);
	Text(TEXT("SAUD"), L.Name.X, L.Name.Y, Page.Px(NameText), InkC);
	InkBar(Page, L.Health, HealthF, PlayerGhost.Value, SaudRed);
	InkBar(Page, L.Stamina, Saud->MaxStamina > 0.f ? Saud->GetStamina() / Saud->MaxStamina : 0.f,
	       0.f, StaminaC);

	// Rage: five ink blocks, gold and pulsing once all five are full --
	// the finisher is ready.
	const float Rage = Saud->GetRageFraction();
	const bool bReady = Saud->IsRageReady();
	const float Pulse = bReady ? 0.5f + 0.5f * FMath::Sin(Clock * 9.f) : 0.f;
	for (int32 i = 0; i < RageBlocks; ++i)
	{
		const FLinearColor Fill = bReady ? FMath::Lerp(RageGold, PaperC, 0.35f * Pulse) : SaudRed;
		InkBar(Page, L.Rage[i], RageBlock(Rage, i), 0.f, Fill);
	}
}

void ASaudHUD::DrawCombo(const FPage& Page, const FLayout& L, float Dt)
{
	const ASaudCharacter* Saud = Cast<ASaudCharacter>(GetOwningPawn());
	const int32 Combo = Saud ? Saud->ComboCount : 0;
	SinceComboHit = Combo > LastCombo ? 0.f : SinceComboHit + Dt;
	LastCombo = Combo;
	if (Combo < 2)
	{
		return;
	}
	const float Punch = ComboPunch(SinceComboHit);
	const float R = L.ComboRadius * (0.85f + 0.15f * Punch);

	// The burst: an ink star, a paper one inside it -- a lettered sound
	// effect's balloon.
	FPoint Outer[2 * BurstPoints], Inner[2 * BurstPoints];
	for (int32 i = 0; i < 2 * BurstPoints; ++i)
	{
		Outer[i] = BurstPoint(L.Combo, R, Combo, i);
		Inner[i] = BurstPoint(L.Combo, R - Page.Px(Ink * 1.6f), Combo, i);
	}
	Poly(Outer, 2 * BurstPoints, InkC);
	Poly(Inner, 2 * BurstPoints, PaperC);

	const float H = Page.Px(ComboText) * Punch * 0.8f;
	Text(FString::FromInt(Combo), L.Combo.X, L.Combo.Y - 0.62f * H, H, InkC, true);
	Text(TEXT("HITS"), L.Combo.X, L.Combo.Y + 0.40f * H, Page.Px(NameText) * 0.9f, SaudRed, true);
}

void ASaudHUD::DrawBoss(const FPage& Page, const FLayout& L, float Dt)
{
	// The nearest living boss, kept while he lives.
	AEnemyFighter* B = Boss.Get();
	if (!B || !B->IsAlive())
	{
		B = nullptr;
		const APawn* P = GetOwningPawn();
		float Best = TNumericLimits<float>::Max();
		for (TActorIterator<AEnemyFighter> It(GetWorld()); It; ++It)
		{
			if (!It->bIsBoss || !It->IsAlive())
			{
				continue;
			}
			const float D = P ? FVector::DistSquared(P->GetActorLocation(), It->GetActorLocation()) : 0.f;
			if (D < Best)
			{
				Best = D;
				B = *It;
			}
		}
		Boss = B;
		BossGhost = FGhost();
	}
	if (!B)
	{
		return;
	}
	const float F = B->GetHealthFraction();
	BossGhost.Tick(F, Dt);

	// An ink banner with the name reversed out of it in paper; red when
	// he is enraged.
	Panel(Page, L.BossPanel, B->bEnraged ? EnemyRed : InkC);
	Text(B->DisplayName.ToString().ToUpper(), L.BossName.X, L.BossName.Y, Page.Px(BossNameText), PaperC);
	InkBar(Page, L.BossHealth, F, BossGhost.Value, EnemyRed);
}

void ASaudHUD::DrawStreetBars(const FPage& Page, const FLayout& L, float Dt)
{
	APlayerController* PC = GetOwningPlayerController();
	if (!PC)
	{
		return;
	}
	for (TActorIterator<AEnemyFighter> It(GetWorld()); It; ++It)
	{
		AEnemyFighter* E = *It;
		if (E->bIsBoss)
		{
			continue;
		}
		FEnemyMark& M = Marks.FindOrAdd(E);
		const float H = E->GetHealth();
		M.Since = (M.LastHealth >= 0.f && H < M.LastHealth) ? 0.f : M.Since + Dt;
		M.LastHealth = H;
		M.Ghost.Tick(E->GetHealthFraction(), Dt);
		if (!E->IsAlive() || M.Since > EnemyBarSeconds)
		{
			continue;
		}
		FVector2D S;
		const FVector Over = E->GetActorLocation() + FVector(0.f, 0.f, 115.f);
		if (!PC->ProjectWorldLocationToScreen(Over, S, true))
		{
			continue;
		}
		const FRect R = {static_cast<float>(S.X) - 0.5f * L.EnemyBarW, static_cast<float>(S.Y),
		                 L.EnemyBarW, L.EnemyBarH};
		InkBar(Page, R, E->GetHealthFraction(), M.Ghost.Value, EnemyRed);
	}
	// Forget the ones that have gone.
	for (auto It = Marks.CreateIterator(); It; ++It)
	{
		if (!It.Key().IsValid())
		{
			It.RemoveCurrent();
		}
	}
}

/* -------------------------------------------------------------- drawing */

void ASaudHUD::Poly(const FPoint* Points, int32 Count, const FLinearColor& Colour)
{
	if (Count < 3)
	{
		return;
	}
	// A fan from the centroid: the starburst is not convex, but it is
	// star-shaped about its centre, which is all a fan needs.
	FVector2D C(0.f, 0.f);
	for (int32 i = 0; i < Count; ++i)
	{
		C += FVector2D(Points[i].X, Points[i].Y);
	}
	C /= static_cast<float>(Count);
	TArray<FCanvasUVTri> Tris;
	Tris.Reserve(Count);
	for (int32 i = 0; i < Count; ++i)
	{
		const FPoint& A = Points[i];
		const FPoint& B = Points[(i + 1) % Count];
		FCanvasUVTri T;
		T.V0_Pos = C;
		T.V1_Pos = FVector2D(A.X, A.Y);
		T.V2_Pos = FVector2D(B.X, B.Y);
		T.V0_Color = T.V1_Color = T.V2_Color = Colour;
		Tris.Add(T);
	}
	FCanvasTriangleItem Item(Tris, GWhiteTexture);
	Item.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Item);
}

void ASaudHUD::InkBar(const FPage& Page, const FRect& R, float Fill, float Ghost, const FLinearColor& Colour)
{
	FPoint Q[4];
	// The ink border: the whole bar, grown by the ink width.
	const float B = FMath::Max(1.f, Page.Px(Ink * 0.6f));
	const FRect Outer = {R.X - B, R.Y - B, R.W + 2.f * B, R.H + 2.f * B};
	BarQuad(Outer, 1.f, Q);
	Poly(Q, 4, InkC);
	BarQuad(R, 1.f, Q);
	Poly(Q, 4, ShadeC);
	if (Ghost > Fill)
	{
		BarQuad(R, Ghost, Q);
		Poly(Q, 4, PaperC);
	}
	if (Fill > 0.f)
	{
		BarQuad(R, Fill, Q);
		Poly(Q, 4, Colour);
	}
}

void ASaudHUD::Panel(const FPage& Page, const FRect& R, const FLinearColor& Fill)
{
	// A panel is a bar that is always full: the same lean, a heavier ink.
	FPoint Q[4];
	const float B = Page.Px(Ink);
	const FRect Outer = {R.X - B, R.Y - B, R.W + 2.f * B, R.H + 2.f * B};
	BarQuad(Outer, 1.f, Q);
	Poly(Q, 4, InkC);
	BarQuad(R, 1.f, Q);
	Poly(Q, 4, Fill);
}

void ASaudHUD::Text(const FString& S, float X, float Y, float HeightPx, const FLinearColor& Colour, bool bCentre)
{
	UFont* Font = GEngine ? GEngine->GetLargeFont() : nullptr;
	if (!Font || S.IsEmpty())
	{
		return;
	}
	const float Native = FMath::Max(1.f, static_cast<float>(Font->GetMaxCharHeight()));
	const float Scale = HeightPx / Native;
	FCanvasTextItem Item(FVector2D(X, Y), FText::FromString(S), Font, Colour);
	Item.Scale = FVector2D(Scale, Scale);
	// Lettering with an ink keyline, as a manga letters over art.
	Item.bOutlined = true;
	Item.OutlineColor = Colour.Equals(InkC) ? PaperC : InkC;
	if (bCentre)
	{
		float W = 0.f, H = 0.f;
		Canvas->StrLen(Font, S, W, H);
		Item.Position.X -= 0.5f * W * Scale;
	}
	Canvas->DrawItem(Item);
}
