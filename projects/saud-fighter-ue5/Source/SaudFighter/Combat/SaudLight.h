#pragma once

/**
 * What the night's lights cost, and which of them cast shadows -- with no
 * engine in it.
 *
 * Asked 2026-10-03 (Riyadh) as "make light and brightness optimization",
 * settled as both: faster lighting and better brightness. The brightness is
 * the world's exposure (Tools/levels/build_world.py exposure_bias()); this
 * is the cost.
 *
 * Measured on the open world's plan before the change: 220 night lights,
 * 181 of them shadowed fires, every one drawn as far as its district was
 * loaded. Around one spot that was up to 92 lights and 57 shadowed point
 * lights (six shadow faces each) at once; 38 on average.
 *
 *  - DRAWN: a light is drawn while its pool (the ground it out-lights the
 *    moon on, build_souq.pool_of) is at least CullDegrees across from the
 *    eye, and fades over the last FadeShare of that. Tools/blender/
 *    build_souq.py spawn_night() sets each light's MaxDrawDistance and
 *    MaxDistanceFadeRange from these; Tools/look/lighting.py holds its copy
 *    to them. A brazier is drawn to 103 m, a pyre to 206 m, a lantern to
 *    46 m: around one spot now at most 34 lights, 27 of them shadowed fires.
 *  - SHADOWED: of the fires authored as shadowed (actor tag ShadowTag), only
 *    the ShadowBudget nearest the camera, within ShadowReachCm, cast at
 *    any moment (USaudLightSubsystem, every RecheckSeconds). A light that
 *    casts keeps its place until a rival is KeepFactor nearer, so walking
 *    past a row of fires does not flicker their shadows on and off.
 *
 * Header of free functions and constants, like SaudFire.h, so Tools/harness
 * builds it with g++ and checks it (tests/light.cpp).
 */

#if defined(SAUD_HARNESS)
	#include "HarnessTypes.h"
#else
	#include "CoreMinimal.h"
#endif

#include <cmath>

namespace SaudLight
{
	/** The actor tag spawn_night() puts on every fire it spawns shadowed. */
	constexpr const char* ShadowTag = "SaudShadow";

	/** At most this many shadowed lights cast at once: the fights' own
	    fires (a fight is lit by its two to four, build_souq NIGHT) and the
	    next ones down the street. */
	constexpr int ShadowBudget = 8;
	/** No light casts farther than this from the camera, 40 m: beyond it a
	    fighter's shadow is a few pixels under the cel cut. */
	constexpr float ShadowReachCm = 4000.f;
	/** A light that casts is ranked this much nearer than it is, and keeps
	    casting this much past the reach. */
	constexpr float KeepFactor = 1.15f;
	/** How often the choice is made again. */
	constexpr float RecheckSeconds = 0.25f;

	/** A light is drawn while its pool is at least this many degrees across
	    (its radius, seen from the eye)... */
	constexpr float CullDegrees = 2.5f;
	/** ...and fades out over this share of that distance. */
	constexpr float FadeShare = 0.25f;

	/** How far a light whose pool is PoolCm in radius is drawn, in cm. */
	inline float DrawDistanceCm(float PoolCm)
	{
		return PoolCm / std::tan(CullDegrees * 3.14159265f / 180.f);
	}

	/** Over how much of that it fades, in cm. */
	inline float FadeRangeCm(float PoolCm)
	{
		return DrawDistanceCm(PoolCm) * FadeShare;
	}

	/**
	 * Which of N shadowed lights cast now: DistCm[i] is light i's distance
	 * from the camera, Was[i] whether it casts already. Fills Out[i] and
	 * returns how many cast: the nearest, at most ShadowBudget, none beyond
	 * the reach, a light that casts counted KeepFactor nearer.
	 */
	inline int PickShadows(const float* DistCm, const bool* Was, int N, bool* Out)
	{
		for (int I = 0; I < N; ++I)
		{
			Out[I] = false;
		}
		int Count = 0;
		while (Count < ShadowBudget)
		{
			int Best = -1;
			float BestScore = 0.f;
			for (int I = 0; I < N; ++I)
			{
				if (Out[I])
				{
					continue;
				}
				const float Reach = Was[I] ? ShadowReachCm * KeepFactor : ShadowReachCm;
				if (!(DistCm[I] <= Reach))
				{
					continue;
				}
				const float Score = Was[I] ? DistCm[I] / KeepFactor : DistCm[I];
				if (Best < 0 || Score < BestScore)
				{
					Best = I;
					BestScore = Score;
				}
			}
			if (Best < 0)
			{
				break;
			}
			Out[Best] = true;
			++Count;
		}
		return Count;
	}
}
