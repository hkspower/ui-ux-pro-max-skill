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
#include "RenderUtils.h"

using namespace SaudHud;

namespace
{
	// 2026-09-26, "use darker theme style like Demon's Souls": the HUD of a
	// dark fantasy rather than a manga page. The ink and the bone are the
	// look's own (Tools/look/anime_look.py LOOK INK and BONE, which checks
	// these two against its own): dark translucent plates keylined in a
	// dull bronze, lettering in bone, the bars the Souls' three -- a deep
	// blood-red health, a moss-green stamina, and the rage an ember gold --
	// in an empty trough near black, and the damage trail a dim gold that
	// drains, as a Souls bar's does. Until that day: paper panels with a
	// heavy ink border, Saud's bright band red (#ff1a3c) for his health,
	// an amber stamina and a hot rage gold.
	const FLinearColor InkC(0.0022f, 0.0019f, 0.0017f, 1.f);
	const FLinearColor BoneC(0.56f, 0.52f, 0.44f, 1.f);
	const FLinearColor PlateC(0.006f, 0.006f, 0.007f, 0.78f);   // a dark plate, the world through it
	const FLinearColor TroughC(0.010f, 0.011f, 0.014f, 0.92f);  // an empty bar
	const FLinearColor BronzeC = FLinearColor::FromSRGBColor(FColor(0x6b, 0x55, 0x33));
	const FLinearColor TrailC = FLinearColor::FromSRGBColor(FColor(0xa8, 0x86, 0x3c));
	const FLinearColor HealthC = FLinearColor::FromSRGBColor(FColor(0x9b, 0x16, 0x16));
	const FLinearColor EnemyRed = FLinearColor::FromSRGBColor(FColor(0x6e, 0x0e, 0x12));
	const FLinearColor StaminaC = FLinearColor::FromSRGBColor(FColor(0x4a, 0x6e, 0x33));
	const FLinearColor RageC = FLinearColor::FromSRGBColor(FColor(0xa0, 0x6a, 0x22));
	const FLinearColor EmberC = FLinearColor::FromSRGBColor(FColor(0xe8, 0x74, 0x2a));
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

	Panel(Page, L.PlayerPanel, PlateC);
	Text(TEXT("SAUD"), L.Name.X, L.Name.Y, Page.Px(NameText), BoneC);
	InkBar(Page, L.Health, HealthF, PlayerGhost.Value, HealthC);
	InkBar(Page, L.Stamina, Saud->MaxStamina > 0.f ? Saud->GetStamina() / Saud->MaxStamina : 0.f,
	       0.f, StaminaC);

	// Rage: five small blocks, a dull gold, glowing to ember and pulsing
	// once all five are full -- the finisher is ready.
	const float Rage = Saud->GetRageFraction();
	const bool bReady = Saud->IsRageReady();
	const float Pulse = bReady ? 0.5f + 0.5f * FMath::Sin(Clock * 9.f) : 0.f;
	for (int32 i = 0; i < RageBlocks; ++i)
	{
		const FLinearColor Fill = bReady ? FMath::Lerp(RageC, EmberC, 0.4f + 0.6f * Pulse) : RageC;
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

	// The seal: a bronze-rimmed serrated disc, dark inside, the count in
	// bone and HITS in ember.
	FPoint Outer[2 * BurstPoints], Inner[2 * BurstPoints];
	for (int32 i = 0; i < 2 * BurstPoints; ++i)
	{
		Outer[i] = BurstPoint(L.Combo, R, Combo, i);
		Inner[i] = BurstPoint(L.Combo, R - Page.Px(Ink * 1.5f), Combo, i);
	}
	Poly(Outer, 2 * BurstPoints, BronzeC);
	Poly(Inner, 2 * BurstPoints, PlateC);

	const float H = Page.Px(ComboText) * Punch * 0.8f;
	Text(FString::FromInt(Combo), L.Combo.X, L.Combo.Y - 0.62f * H, H, BoneC, true);
	Text(TEXT("HITS"), L.Combo.X, L.Combo.Y + 0.40f * H, Page.Px(NameText) * 0.9f, EmberC, true);
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
		// Start the trail where he is, not at full: a boss met already hurt
		// has no cut to show.
		BossGhost = FGhost();
		if (B)
		{
			BossGhost.Value = BossGhost.Last = B->GetHealthFraction();
		}
	}
	if (!B)
	{
		return;
	}
	const float F = B->GetHealthFraction();
	BossGhost.Tick(F, Dt);

	// A dark plate at the foot of the screen, his name in bone over a thin
	// oxblood bar, as a Souls boss is named; the name goes to ember when
	// he is enraged.
	Panel(Page, L.BossPanel, PlateC);
	Text(B->DisplayName.ToString().ToUpper(), L.BossName.X, L.BossName.Y, Page.Px(BossNameText),
	     B->bEnraged ? EmberC : BoneC);
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
	// The keyline: the whole bar, grown by a thin bronze edge, then the
	// dark trough, the draining trail and the bar.
	const float B = FMath::Max(1.f, Page.Px(Ink * 0.75f));
	const FRect Outer = {R.X - B, R.Y - B, R.W + 2.f * B, R.H + 2.f * B};
	BarQuad(Outer, 1.f, Q);
	Poly(Q, 4, BronzeC);
	BarQuad(R, 1.f, Q);
	Poly(Q, 4, TroughC);
	if (Ghost > Fill)
	{
		BarQuad(R, Ghost, Q);
		Poly(Q, 4, TrailC);
	}
	if (Fill > 0.f)
	{
		BarQuad(R, Fill, Q);
		Poly(Q, 4, Colour);
	}
}

void ASaudHUD::Panel(const FPage& Page, const FRect& R, const FLinearColor& Fill)
{
	// A panel is a bar that is always full: a dark plate in a bronze
	// keyline. The plate is translucent, so the keyline is drawn as four
	// strips round it rather than a quad under it, or the bronze would
	// show through.
	FPoint Q[4];
	const float B = FMath::Max(1.f, Page.Px(Ink));
	const FRect Edges[4] = {
		{R.X - B, R.Y - B, R.W + 2.f * B, B},     // top
		{R.X - B, R.Y + R.H, R.W + 2.f * B, B},   // bottom
		{R.X - B, R.Y, B, R.H},                   // left
		{R.X + R.W, R.Y, B, R.H},                 // right
	};
	for (const FRect& E : Edges)
	{
		BarQuad(E, 1.f, Q);
		Poly(Q, 4, BronzeC);
	}
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
	// Lettering with an ink keyline, so it reads over the world as well
	// as over a plate.
	Item.bOutlined = true;
	Item.OutlineColor = InkC;
	if (bCentre)
	{
		float W = 0.f, H = 0.f;
		Canvas->StrLen(Font, S, W, H);
		Item.Position.X -= 0.5f * W * Scale;
	}
	Canvas->DrawItem(Item);
}
