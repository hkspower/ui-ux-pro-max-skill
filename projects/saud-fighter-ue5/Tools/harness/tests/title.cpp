/**
 * The title's shot, executed (Combat/SaudTitle.h): at the seven screen
 * shapes the HUD and the menu are held to, every sixtieth of a second over
 * a whole sweep, with Saud standing anywhere and facing any way --
 *   - the camera stays in front of him, his face to it;
 *   - the menu never covers him: his box is right of the wash, and no
 *     triangle or word SaudMenu::Build draws for the Title touches it;
 *   - he stays inside title-safe, and fills the frame;
 *   - the camera stays above the floor and off him;
 *   - the vertical field of view is held on every screen;
 *   - his middle stands where the menu leaves room;
 *   - the sweep loops without a jump;
 *   - the shot is his, wherever he stands and whichever way he faces.
 * Each is broken once by Tools/harness/bite.sh (bites.txt, "title").
 */
#include "../HarnessTypes.h"
#include "../../../Source/SaudFighter/Combat/SaudTitle.h"

#include <cmath>
#include <cstdio>

using namespace SaudTitle;
using SaudHud::FPage;

static int Fails = 0;
static void Check(bool Ok, const char* What)
{
	if (!Ok) { ++Fails; std::printf("  FAIL  %s\n", What); }
}

static const float Shapes[][2] = {{1920, 1080}, {1280, 720}, {3840, 2160}, {2560, 1080},
                                  {3440, 1440}, {1600, 1200}, {1680, 1050}};
static SaudMenu::FMenuList List;

struct FBox { float X0 = 1e9f, Y0 = 1e9f, X1 = -1e9f, Y1 = -1e9f; };
static void Grow(FBox& B, float X, float Y)
{
	B.X0 = FMath::Min(B.X0, X); B.Y0 = FMath::Min(B.Y0, Y);
	B.X1 = FMath::Max(B.X1, X); B.Y1 = FMath::Max(B.Y1, Y);
}
static bool Touch(const FBox& A, const FBox& B)
{
	return A.X0 < B.X1 && B.X0 < A.X1 && A.Y0 < B.Y1 && B.Y0 < A.Y1;
}

/** Everything the Title draws, as boxes in screen pixels. */
static int MenuBoxes(const FPage& P, FBox* Out, int Cap)
{
	SaudMenu::Build(P, TitleModel(), List);
	int N = 0;
	for (int i = 0; i < List.NumTris && N < Cap; ++i)
	{
		const SaudMenu::FMenuTri& T = List.Tris[i];
		if (T.V[0].C.A < 0.02f && T.V[1].C.A < 0.02f && T.V[2].C.A < 0.02f)
		{
			continue;
		}
		FBox B;
		for (const auto& V : T.V) Grow(B, V.P.X, V.P.Y);
		Out[N++] = B;
	}
	for (int i = 0; i < List.NumTexts && N < Cap; ++i)
	{
		const SaudMenu::FMenuText& T = List.Texts[i];
		const float W = SaudMenu::TextWidth(T.Slot, T.Value, T.Height);
		const float X = T.bCentre ? T.At.X - 0.5f * W : T.At.X;
		FBox B;
		Grow(B, X - T.Stroke, T.At.Y - T.Stroke);
		Grow(B, X + W + T.Stroke, T.At.Y + T.Height + T.Stroke);
		Out[N++] = B;
	}
	return N;
}

static float DegBetween(const FVector& A, const FVector& B)
{
	const float C = FVector::DotProduct(A.GetSafeNormal(), B.GetSafeNormal());
	return FMath::RadiansToDegrees(FMath::Acos(C));
}

/** Every rule at one screen shape, one place, one facing. */
static void Hold(float W, float H, const FVector& Feet, float FacingDeg, bool& Front, bool& Menu, bool& Safe,
                 bool& Big, bool& Floor, bool& Fov, bool& Middle, bool& Smooth)
{
	const FPage P = FPage::For(W, H);
	const float Aspect = W / H;
	const FVector Facing(FMath::Cos(FMath::DegreesToRadians(FacingDeg)), FMath::Sin(FMath::DegreesToRadians(FacingDeg)), 0.f);
	static FBox Boxes[SaudMenu::MaxTris + SaudMenu::MaxTexts];
	const int NB = MenuBoxes(P, Boxes, static_cast<int>(sizeof(Boxes) / sizeof(Boxes[0])));
	const FFrame Fr = FrameFor(P);
	const float Hold = Fr.HoldAt, Left = FreeLeft(P);

	// the vertical field of view, held
	{
		const FShot S = Shoot(Feet, Facing, 0.f, Fr);
		const float Tv = FMath::Tan(FMath::DegreesToRadians(0.5f * S.HFovDeg)) / Aspect;
		if (std::fabs(FMath::RadiansToDegrees(2.f * FMath::Atan(Tv)) - VFovDeg) > 0.05f) Fov = false;
	}

	const float Dt = 1.f / 60.f;
	FShot Prev = Shoot(Feet, Facing, -Dt, Fr);
	for (float T = 0.f; T <= PeriodS + 1e-3f; T += Dt)
	{
		const FShot S = Shoot(Feet, Facing, T, Fr);
		const FVector Flat(S.Eye.X - Feet.X, S.Eye.Y - Feet.Y, 0.f);

		// in front of him
		if (DegBetween(Flat, Facing) > 60.f) Front = false;
		// above the floor, off him
		const float Up = S.Eye.Z - Feet.Z;
		if (Up < 100.f || Up > 250.f || Flat.Size() < Distance - 1.f || std::fabs(Flat.Size() - Fr.Dist) > 1.f) Floor = false;

		FVector C[8];
		Figure(Feet, Facing, C);
		FBox Him;
		for (const FVector& Q : C)
		{
			const FSeen Seen = Project(S, Aspect, Q);
			if (Seen.Depth < 150.f) Floor = false;
			Grow(Him, Seen.X * W, Seen.Y * H);
		}
		// right of the wash, touching nothing the menu draws
		if (Him.X0 < (Left + 0.5f * Margin) * W) Menu = false;
		for (int i = 0; i < NB && Menu; ++i)
		{
			if (Touch(Him, Boxes[i])) Menu = false;
		}
		// title-safe, and big enough to read from the couch
		if (Him.X1 > P.Right() || Him.Y0 < P.Top() || Him.Y1 > P.Bottom()) Safe = false;
		const float Tall = (Him.Y1 - Him.Y0) / H;
		if (Tall < 0.45f || Tall > 0.90f) Big = false;
		// his middle where the menu leaves room (at the front of the arc it is exact)
		if (std::fabs(S.SweepDeg) < 1.f)
		{
			const FSeen Mid = Project(S, Aspect, Feet + FVector(0.f, 0.f, AimZ));
			if (std::fabs(Mid.X - Hold) > 0.01f) Middle = false;
		}
		// smooth: the eye moves no faster than 120 cm/s (a slow dolly: the
		// arc's middle is 100 at the 4:3 distance), the view turns no
		// faster than 20 degrees a second, and the arc comes round to itself
		if ((S.Eye - Prev.Eye).Size() > 120.f * Dt + 1e-3f) Smooth = false;
		if (DegBetween(S.Forward, Prev.Forward) > 20.f * Dt + 1e-3f) Smooth = false;
		Prev = S;
	}
	const FShot A = Shoot(Feet, Facing, 3.f, Fr), B = Shoot(Feet, Facing, 3.f + PeriodS, Fr);
	if ((A.Eye - B.Eye).Size() > 0.5f || DegBetween(A.Forward, B.Forward) > 0.05f) Smooth = false;
}

static void Frames()
{
	std::printf("THE SHOT  (seven screens, a whole sweep, three places, three facings)\n");
	bool Front = true, Menu = true, Safe = true, Big = true, Floor = true, Fov = true, Middle = true, Smooth = true;
	const FVector Places[3] = {FVector(0.f, 0.f, 0.f), FVector(123456.f, -98765.f, 330.f), FVector(-40000.f, 7000.f, -120.f)};
	const float Facings[3] = {0.f, 90.f, 217.f};
	for (const auto& Sh : Shapes)
		for (const FVector& At : Places)
			for (float F : Facings)
				Hold(Sh[0], Sh[1], At, F, Front, Menu, Safe, Big, Floor, Fov, Middle, Smooth);
	Check(Front, "the camera stays in front of him, his face to it");
	Check(Menu, "the menu never covers him");
	Check(Safe, "he stays inside title-safe");
	Check(Big, "he fills the frame (45-90 % of the height)");
	Check(Floor, "the camera stays above the floor and off him");
	Check(Fov, "the vertical field of view is held on every screen");
	Check(Middle, "his middle stands where the menu leaves room");
	Check(Smooth, "the sweep loops without a jump");
}

static void His()
{
	std::printf("HIS SHOT  (the same shot relative to him, wherever he stands and whichever way he faces)\n");
	FFrame Fr;
	const FVector F0(1.f, 0.f, 0.f);
	const FVector A(0.f, 0.f, 0.f), B(55555.f, -22222.f, 480.f);
	bool Place = true, Turned = true;
	for (float T = 0.f; T < PeriodS; T += 0.7f)
	{
		const FShot SA = Shoot(A, F0, T, Fr), SB = Shoot(B, F0, T, Fr);
		if (((SA.Eye - A) - (SB.Eye - B)).Size() > 0.5f || DegBetween(SA.Forward, SB.Forward) > 0.01f) Place = false;
		// facing turned 90 degrees: the shot turns with him
		const FShot SR = Shoot(A, FVector(0.f, 1.f, 0.f), T, Fr);
		const FVector Want = Turn(SA.Eye - A, 0.5f * Pi);
		if (((SR.Eye - A) - Want).Size() > 0.5f) Turned = false;
	}
	Check(Place && Turned, "the shot is his, wherever he stands and whichever way he faces");
}

int main()
{
	Frames(); His();
	if (Fails) { std::printf("%d title check(s) failed\n", Fails); return 1; }
	std::printf("all title checks passed\n");
	return 0;
}
