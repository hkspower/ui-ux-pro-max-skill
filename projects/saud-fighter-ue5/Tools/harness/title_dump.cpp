/**
 * The title's shot as JSON, for Tools/blender/title_preview.py:
 * SaudTitle::FrameFor and Shoot (Combat/SaudTitle.h) at a screen size and a
 * time, for a man standing somewhere facing some way, with no engine. Like
 * menu_dump.cpp: not a test -- it lives beside tests/, not in it, so run.sh
 * does not build it; title_preview.py does.
 *
 *   title_dump W H T FeetX FeetY FeetZ FacingX FacingY
 *
 * Everything in the engine's frame: centimetres, Z up, left-handed.
 * Prints {"eye": [x,y,z], "forward": [x,y,z], "hfov": deg, "sweep": deg,
 * "hold": share, "dist": cm, "free_left": share, "free_right": share}.
 */
#include "HarnessTypes.h"
#include "../../Source/SaudFighter/Combat/SaudTitle.h"

#include <cstdio>
#include <cstdlib>

int main(int argc, char** argv)
{
	if (argc != 9)
	{
		std::fprintf(stderr, "title_dump W H T FeetX FeetY FeetZ FacingX FacingY\n");
		return 2;
	}
	const float W = std::strtof(argv[1], nullptr), H = std::strtof(argv[2], nullptr);
	const float T = std::strtof(argv[3], nullptr);
	const FVector Feet(std::strtof(argv[4], nullptr), std::strtof(argv[5], nullptr), std::strtof(argv[6], nullptr));
	const FVector Facing(std::strtof(argv[7], nullptr), std::strtof(argv[8], nullptr), 0.f);

	const SaudHud::FPage P = SaudHud::FPage::For(W, H);
	const SaudTitle::FFrame Fr = SaudTitle::FrameFor(P);
	const SaudTitle::FShot S = SaudTitle::Shoot(Feet, Facing, T, Fr);
	std::printf("{\"eye\": [%.4f, %.4f, %.4f], \"forward\": [%.6f, %.6f, %.6f], \"hfov\": %.5f, \"sweep\": %.4f, "
	            "\"hold\": %.5f, \"dist\": %.3f, \"free_left\": %.5f, \"free_right\": %.5f}\n",
	            S.Eye.X, S.Eye.Y, S.Eye.Z, S.Forward.X, S.Forward.Y, S.Forward.Z, S.HFovDeg, S.SweepDeg,
	            Fr.HoldAt, Fr.Dist, SaudTitle::FreeLeft(P), SaudTitle::FreeRight(P));
	return 0;
}
