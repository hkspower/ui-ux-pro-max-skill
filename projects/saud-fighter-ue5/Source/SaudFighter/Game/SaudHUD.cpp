#include "Game/SaudHUD.h"
#include "Combat/EnemyFighter.h"
#include "Combat/SaudCharacter.h"
#include "Combat/SaudControls.h"
#include "Game/SaudMenuSubsystem.h"

#include "CanvasItem.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Misc/App.h"
#include "RenderUtils.h"

using namespace SaudHud;

// 2026-09-28, "make all game like dark anime adult style": every colour the
// HUD draws is SaudHud::Colour (Combat/SaudAnime.h), the look's own ink,
// bone, blood and ember among them -- Tools/look/anime_look.py holds those
// four to its LOOK -- and every shape is SaudHud::Build's. Until that day
// this file held the palette itself (InkC, BoneC, a bronze keyline, a moss
// stamina, an oxblood enemy red) and drew each plate and bar on its own.

void ASaudHUD::DrawHUD()
{
	Super::DrawHUD();
	if (!Canvas)
	{
		return;
	}
	// A menu, if one is open: over the fight on a pause (and anything
	// opened from it), instead of the fight under the title (and anything
	// opened from that). ReturnTo is the screen a menu was opened from --
	// the Title or the Pause itself when on one of those.
	const USaudMenuSubsystem* Menu = USaudMenuSubsystem::Get(this);
	const bool bMenu = Menu && Menu->IsOpen();
	const bool bUnderTitle = bMenu && Menu->Model().ReturnTo == SaudMenu::EScreen::Title;

	// Real time: the freeze stops the fight, not the page. A pause stops
	// both: the trails and the boss's wipe hold under the menu (whose own
	// clock the menu subsystem runs, in real time).
	const float Dt = bMenu ? 0.f : FMath::Clamp(static_cast<float>(FApp::GetDeltaTime()), 0.f, 0.1f);
	Clock += Dt;

	FHudState State;
	State.Clock = Clock;
	GatherStreet(State, Dt);
	GatherPlayer(State, Dt);
	GatherBoss(State, Dt);

	const FPage Page = FPage::For(Canvas->ClipX, Canvas->ClipY);
	if (!bUnderTitle)
	{
		Build(Page, State, List);
		Emit();
	}
	if (bMenu)
	{
		SaudMenu::Build(Page, Menu->Model(), MenuList);
		EmitMenu();
	}
}

/* ------------------------------------------------------ the game's state */

void ASaudHUD::GatherPlayer(FHudState& State, float Dt)
{
	const ASaudCharacter* Saud = Cast<ASaudCharacter>(GetOwningPawn());
	const int32 Combo = Saud ? Saud->ComboCount : 0;
	SinceComboHit = Combo > LastCombo ? 0.f : SinceComboHit + Dt;
	LastCombo = Combo;
	State.Combo = Combo;
	State.SinceCombo = SinceComboHit;
	if (!Saud)
	{
		State.bPlayer = false;
		return;
	}
	const float HealthF = Saud->GetHealthFraction();
	PlayerGhost.Tick(HealthF, Dt);
	State.Health = HealthF;
	State.Ghost = PlayerGhost.Value;
	State.Stamina = Saud->MaxStamina > 0.f ? Saud->GetStamina() / Saud->MaxStamina : 0.f;
	State.Rage = Saud->GetRageFraction();
	State.bRageReady = Saud->IsRageReady();
}

void ASaudHUD::GatherBoss(FHudState& State, float Dt)
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
		// has no cut to show. And his banner wipes open from now.
		BossGhost = FGhost();
		if (B)
		{
			BossGhost.Value = BossGhost.Last = B->GetHealthFraction();
			BossFoundAt = Clock;
		}
	}
	if (!B)
	{
		return;
	}
	const float F = B->GetHealthFraction();
	BossGhost.Tick(F, Dt);
	State.bBoss = true;
	State.BossHealth = F;
	State.BossGhost = BossGhost.Value;
	State.bBossEnraged = B->bEnraged;
	State.BossSince = Clock - BossFoundAt;
}

void ASaudHUD::GatherStreet(FHudState& State, float Dt)
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
		if (!E->IsAlive() || M.Since > EnemyBarSeconds || State.NumStreet >= MaxStreetBars)
		{
			continue;
		}
		FVector2D S;
		const FVector Over = E->GetActorLocation() + FVector(0.f, 0.f, 115.f);
		if (!PC->ProjectWorldLocationToScreen(Over, S, true))
		{
			continue;
		}
		State.Street[State.NumStreet++] = {static_cast<float>(S.X), static_cast<float>(S.Y),
		                                   E->GetHealthFraction(), M.Ghost.Value};
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

void ASaudHUD::Emit()
{
	int32 Done = 0;
	for (int32 i = 0; i < List.NumTexts; ++i)
	{
		const FHudText& T = List.Texts[i];
		Flush(Done, T.TrisBefore);
		Done = T.TrisBefore;
		switch (T.Slot)
		{
		case EHudText::Name:
			Text(T, TEXT("SAUD"));
			break;
		case EHudText::Count:
			Text(T, FString::FromInt(T.Value));
			break;
		case EHudText::Hits:
			Text(T, TEXT("HITS"));
			break;
		case EHudText::BossName:
			if (const AEnemyFighter* B = Boss.Get())
			{
				Text(T, B->DisplayName.ToString().ToUpper());
			}
			break;
		}
	}
	Flush(Done, List.NumTris);
}

namespace
{
	/** One triangle item for a run of either list's triangles (the HUD's
	    FHudTri and the menu's FMenuTri both carry V[3] of a point and a
	    colour), each vertex its own colour and alpha. */
	template <typename TTri>
	void DrawTris(UCanvas* Canvas, const TTri* Tris, int32 From, int32 To)
	{
		if (!Canvas || To <= From)
		{
			return;
		}
		TArray<FCanvasUVTri> Batch;
		Batch.Reserve(To - From);
		for (int32 i = From; i < To; ++i)
		{
			const TTri& T = Tris[i];
			FCanvasUVTri U;
			U.V0_Pos = FVector2D(T.V[0].P.X, T.V[0].P.Y);
			U.V1_Pos = FVector2D(T.V[1].P.X, T.V[1].P.Y);
			U.V2_Pos = FVector2D(T.V[2].P.X, T.V[2].P.Y);
			U.V0_Color = FLinearColor(T.V[0].C.R, T.V[0].C.G, T.V[0].C.B, T.V[0].C.A);
			U.V1_Color = FLinearColor(T.V[1].C.R, T.V[1].C.G, T.V[1].C.B, T.V[1].C.A);
			U.V2_Color = FLinearColor(T.V[2].C.R, T.V[2].C.G, T.V[2].C.B, T.V[2].C.A);
			Batch.Add(U);
		}
		FCanvasTriangleItem Item(Batch, GWhiteTexture);
		Item.BlendMode = SE_BLEND_Translucent;
		Canvas->DrawItem(Item);
	}
}

void ASaudHUD::Flush(int32 From, int32 To)
{
	DrawTris(Canvas, List.Tris, From, To);
}

void ASaudHUD::Text(const FHudText& T, const FString& S)
{
	DrawText(T.At, T.Height, T.Colour, T.Stroke, T.bCentre, S);
}

void ASaudHUD::DrawText(const FPoint& At, float Height, const FRgba& TextColour, float Stroke, bool bCentre,
                        const FString& S)
{
	UFont* Font = GEngine ? GEngine->GetLargeFont() : nullptr;
	if (!Font || S.IsEmpty())
	{
		return;
	}
	const float Native = FMath::Max(1.f, static_cast<float>(Font->GetMaxCharHeight()));
	const float Scale = Height / Native;
	float X = At.X;
	if (bCentre)
	{
		float W = 0.f, H = 0.f;
		Canvas->StrLen(Font, S, W, H);
		X -= 0.5f * W * Scale;
	}
	// The ink stroke: the text eight times in ink, Stroke away round it,
	// then the fill over them -- heavy lettering that reads over the world,
	// a blood splat or an impact frame alike.
	static const FVector2D Round[8] = {{1.f, 0.f}, {-1.f, 0.f}, {0.f, 1.f}, {0.f, -1.f},
	                                   {0.7071f, 0.7071f}, {-0.7071f, 0.7071f}, {0.7071f, -0.7071f},
	                                   {-0.7071f, -0.7071f}};
	// Full ink under any text at half its opacity or more -- every text at
	// rest (the dim ones are 0.55); under a text fading in (the menu's
	// entrance, SaudMenu, 2026-10-02) the ink fades with it from there, so
	// no outline stands alone before its letters.
	const FLinearColor InkC(Colour::Ink.R, Colour::Ink.G, Colour::Ink.B, FMath::Min(1.f, 2.f * TextColour.A));
	const FText Line = FText::FromString(S);
	for (const FVector2D& D : Round)
	{
		FCanvasTextItem StrokeItem(FVector2D(X, At.Y) + D * Stroke, Line, Font, InkC);
		StrokeItem.Scale = FVector2D(Scale, Scale);
		Canvas->DrawItem(StrokeItem);
	}
	FCanvasTextItem Fill(FVector2D(X, At.Y), Line, Font,
	                     FLinearColor(TextColour.R, TextColour.G, TextColour.B, TextColour.A));
	Fill.Scale = FVector2D(Scale, Scale);
	Canvas->DrawItem(Fill);
}

/* ------------------------------------------------------------- the menu */

void ASaudHUD::EmitMenu()
{
	int32 Done = 0;
	for (int32 i = 0; i < MenuList.NumTexts; ++i)
	{
		const SaudMenu::FMenuText& T = MenuList.Texts[i];
		FlushMenu(Done, T.TrisBefore);
		Done = T.TrisBefore;
		DrawText(T.At, T.Height, T.Colour, T.Stroke, T.bCentre, MenuString(T));
	}
	FlushMenu(Done, MenuList.NumTris);
}

void ASaudHUD::FlushMenu(int32 From, int32 To)
{
	DrawTris(Canvas, MenuList.Tris, From, To);
}

FString ASaudHUD::MenuString(const SaudMenu::FMenuText& T)
{
	using SaudMenu::EMenuText;
	const bool bOn = T.Value != 0;
	switch (T.Slot)
	{
	case EMenuText::Saud: return TEXT("SAUD");
	case EMenuText::Subtitle: return TEXT("KUWAIT FIGHTER");
	case EMenuText::Paused: return TEXT("PAUSED");
	case EMenuText::SettingsHead: return TEXT("SETTINGS");
	case EMenuText::Continue: return TEXT("CONTINUE");
	case EMenuText::Fight: return TEXT("FIGHT");
	case EMenuText::Controls: return TEXT("CONTROLS");
	case EMenuText::Settings: return TEXT("SETTINGS");
	case EMenuText::Quit: return TEXT("QUIT");
	case EMenuText::Resume: return TEXT("RESUME");
	case EMenuText::QuitToTitle: return TEXT("QUIT TO TITLE");
	case EMenuText::Difficulty:
		return T.Value == 0 ? TEXT("DIFFICULTY  ROOKIE")
		     : (T.Value == 1 ? TEXT("DIFFICULTY  PRO") : TEXT("DIFFICULTY  CHAMPION"));
	// a level: OFF at 0, else its number (the meter beside it shows it too)
	case EMenuText::Sound: return bOn ? FString::Printf(TEXT("SOUND  %d"), T.Value) : FString(TEXT("SOUND  OFF"));
	case EMenuText::Music: return bOn ? FString::Printf(TEXT("MUSIC  %d"), T.Value) : FString(TEXT("MUSIC  OFF"));
	case EMenuText::Vibration: return bOn ? TEXT("VIBRATION  ON") : TEXT("VIBRATION  OFF");
	case EMenuText::Back: return TEXT("BACK");
	case EMenuText::PromptSelect: return TEXT("SELECT");
	case EMenuText::PromptBack: return TEXT("BACK");
	case EMenuText::PromptAdjust: return TEXT("ADJUST");
	case EMenuText::PromptFlip: return bOn ? TEXT("SHOW PS5") : TEXT("SHOW XBOX");
	case EMenuText::KeySelect: return TEXT("ENTER  SELECT");
	case EMenuText::KeyBack: return TEXT("ESC  BACK");
	case EMenuText::KeyAdjust: return TEXT("ARROWS  ADJUST");
	case EMenuText::KeyFlip: return bOn ? TEXT("TAB  SHOW PS5") : TEXT("TAB  SHOW XBOX");
	case EMenuText::NewGame: return TEXT("NEW GAME");
	case EMenuText::AskHead: return bOn ? TEXT("NEW GAME?") : TEXT("QUIT?");
	case EMenuText::ConfirmNo: return bOn ? TEXT("NO, KEEP MY SAVE") : TEXT("NO, STAY");
	case EMenuText::ConfirmYes: return bOn ? TEXT("YES, START OVER") : TEXT("YES, QUIT");
	case EMenuText::StageTag: return FString::Printf(TEXT("STAGE %d/%d"), T.Value, T.Aux);
	case EMenuText::PromptQuit: return TEXT("QUIT");
	case EMenuText::KeyQuit: return TEXT("ESC  QUIT");
	case EMenuText::Hint:
		return FString(UTF8_TO_TCHAR(SaudMenu::HintString(static_cast<SaudMenu::EHint>(T.Value))));
	case EMenuText::ControlsText:
		// SaudControls' own table: Value is its slot, Aux its value.
		return FString(SaudControls::ControlsText(static_cast<SaudControls::EControlsText>(T.Value), T.Aux));
	default:
		return FString();
	}
}
