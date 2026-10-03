#pragma once

/**
 * Saud's camera: where the boom points, how long it is, what it looks at
 * and how it moves -- with no engine in it.
 *
 * Asked 2026-10-03 (Riyadh) as "improve view saud main camera, make it 3d
 * dynamic view", settled as the Unreal build and all four: frame the fight,
 * move with him, hits and finishers, smarter walls. Until now the camera was
 * a fixed 6.4 m boom at -18 degrees that only the right stick turned
 * (ASaudCharacter), with the browser's shake and push-in on a blow laid
 * over it (USaudFeelSubsystem, unchanged by this).
 *
 *  - FRAME THE FIGHT: with an opponent within EngageCm, the camera looks
 *    across the line from Saud to them -- SideDeg off it, behind his
 *    shoulder, on whichever side it is already nearer -- at a point between
 *    them, and pulls back as far as it takes to hold Saud and every man near
 *    him in the picture. The side only changes when the other is clearly
 *    nearer, so a man circling him does not flip it back and forth.
 *  - MOVE WITH HIM: with no one near, a running Saud has the camera swing in
 *    behind where he is going (faster the faster he goes), look a little
 *    ahead of him, and stand further off at a run than at a walk; stopped,
 *    it stays where it was and comes back in.
 *  - HITS AND FINISHERS: a heavy blow or a parry tips the picture a few
 *    degrees and pushes in a little, springing back; the rage finisher and a
 *    knockout swing the camera round him and in, then hand it back.
 *  - SMARTER WALLS: the boom is shortened before a wall touches it (the
 *    game probes a little past where the camera would be) and eased back out
 *    slowly, never through the wall; whatever stands between the camera and
 *    Saud fades to a dither (FadeStep; the world's surfaces read it).
 *  - The player's stick still turns it, at the old rates, and holds the
 *    automatic framing off for ManualHoldSeconds after the last turn.
 *
 * Every move is an exponential approach with its own time constant, run on
 * real seconds (a blow's freeze stops the world, not the camera's easing).
 * Header of plain structs and free functions, like SaudFeel.h, so
 * Tools/harness builds it with g++ and checks it (tests/camera.cpp).
 * Units: centimetres, degrees, seconds; yaw as Unreal's (0 = +X, 90 = +Y).
 */

#if defined(SAUD_HARNESS)
	#include "HarnessTypes.h"
#else
	#include "CoreMinimal.h"
#endif

#include <cmath>

namespace SaudCamera
{
	// --------------------------------------------------------------- numbers
	constexpr float HFovDeg = 90.f;              // the camera's own (UCameraComponent's default)
	constexpr float SocketUpCm = 90.f;           // what the boom looks at: this far over his root
	constexpr float PitchDeg = -18.f;            // as before
	constexpr float MinPitchDeg = -55.f, MaxPitchDeg = 8.f;
	constexpr float TurnRate = 150.f, PitchRate = 90.f;   // the stick, degrees a second at full tilt
	constexpr float ManualHoldSeconds = 2.0f;

	// alone
	constexpr float IdleArmCm = 560.f;           // stopped
	constexpr float RunArmCm = 740.f;            // at RunSpeedCm and over
	constexpr float RunSpeedCm = 341.f;          // Player.json BaseMoveSpeed
	constexpr float MovingCm = 60.f;             // slower than this he is standing
	constexpr float RecentreDegPerSec = 110.f;   // swinging in behind him at a run
	constexpr float LookAheadSeconds = 0.30f;
	constexpr float LookAheadMaxCm = 140.f;

	// in a fight
	constexpr float EngageCm = 1500.f;           // an opponent nearer than this is in the fight
	constexpr float SideDeg = 32.f;              // the camera's line off the line between them
	constexpr float SideSwitchDeg = 25.f;        // the other side must be this much nearer to take it
	constexpr float FocusShare = 0.40f;          // the look point, this share of the way to them
	constexpr float FightPitchDeg = -15.f;
	constexpr float FightArmMinCm = 520.f, FightArmMaxCm = 1150.f;
	constexpr float FitShare = 0.80f;            // everyone inside this share of the half-width

	// easing (time constants, seconds)
	constexpr float YawTau = 0.35f, FollowYawTau = 0.60f, PitchTau = 0.40f, ArmTau = 0.40f, FocusTau = 0.15f;

	// blows
	constexpr float KickRollDeg = 3.5f;          // a heavy blow or a parry tips the picture this far
	constexpr float KickPush = 0.10f;            // ...and takes this share off the boom
	constexpr float KickFreqHz = 7.f;            // the tip springs back at this rate
	constexpr float KickDecaySec = 0.12f;        // ...dying away with this time constant

	// orbits: the finisher, a knockout
	struct FOrbitSpec { float Seconds, SweepDeg, ArmShare, PitchDeg; };
	constexpr FOrbitSpec FinisherOrbit{1.40f, 70.f, 0.72f, -8.f};
	constexpr FOrbitSpec KnockoutOrbit{1.00f, 45.f, 0.80f, -10.f};

	// walls
	constexpr float ProbeCm = 24.f;              // the camera's own radius against a wall
	constexpr float SoftMarginCm = 120.f;        // probe this much past the camera, and come in early
	constexpr float WallInTau = 0.08f, WallOutTau = 0.50f;
	constexpr float WallOutMaxCmPerSec = 300.f;  // and never back out faster than this

	// occluders
	constexpr int FadeDataIndex = 0;             // the custom primitive data slot the materials read
	constexpr float FadeProbeCm = 30.f;          // the line from the camera to him, this thick
	constexpr float FadeMax = 0.85f;             // a wall between them keeps a trace of itself
	constexpr float FadeInSec = 0.15f, FadeOutSec = 0.30f;

	// ---------------------------------------------------------------- maths
	inline float Wrap180(float D)
	{
		D = std::fmod(D + 180.f, 360.f);
		if (D < 0.f) D += 360.f;
		return D - 180.f;
	}

	/** Exponential approach: the share of the way to go covered in Dt. */
	inline float Ease(float Dt, float Tau)
	{
		return Tau <= 0.f ? 1.f : 1.f - std::exp(-Dt / Tau);
	}

	inline float EaseAngle(float From, float To, float Dt, float Tau)
	{
		return From + Wrap180(To - From) * Ease(Dt, Tau);
	}

	inline float YawOf(const FVector& V)
	{
		return static_cast<float>(std::atan2(V.Y, V.X) * 180.0 / 3.14159265358979);
	}

	inline float Flat(const FVector& V) { return static_cast<float>(V.Size2D()); }

	/** Smoothstep 0..1. */
	inline float Smooth(float T)
	{
		T = T < 0.f ? 0.f : (T > 1.f ? 1.f : T);
		return T * T * (3.f - 2.f * T);
	}

	/** Where the camera stands for a view: back along its yaw and pitch
	    from the focus by the arm. */
	inline FVector EyeOf(const FVector& Focus, float Yaw, float Pitch, float Arm)
	{
		const double Y = Yaw * 3.14159265358979 / 180.0, P = Pitch * 3.14159265358979 / 180.0;
		const FVector Fwd(std::cos(P) * std::cos(Y), std::cos(P) * std::sin(Y), std::sin(P));
		return Focus - Fwd * Arm;
	}

	/** How far off the camera's forward a point is, degrees, seen from above
	    (the horizontal half-field is what a fight across the screen fills). */
	inline float OffAxisDeg(const FVector& Eye, float Yaw, const FVector& At)
	{
		return std::fabs(Wrap180(YawOf(At - Eye) - Yaw));
	}

	// --------------------------------------------------------------- inputs
	struct FInputs
	{
		float Dt = 0.f;                  // real seconds
		FVector Saud;                    // his root
		FVector Velocity;                // his, cm/s
		float LookX = 0.f, LookY = 0.f;  // the right stick, -1..1
		const FVector* Opponents = nullptr;
		int NumOpponents = 0;            // every living one; the near ones are picked here
	};

	struct FView
	{
		float Yaw = 0.f, Pitch = PitchDeg, Arm = IdleArmCm, Roll = 0.f;
		FVector Focus;
		bool bFighting = false;
	};

	enum class EOrbit : unsigned char { None, Finisher, Knockout };

	// ---------------------------------------------------------------- state
	struct FState
	{
		FView View;
		bool bStarted = false;
		/** The look point as an offset from his head, eased: eased as a
		    place, it trailed a running man by his speed times FocusTau, and
		    the look-ahead was half eaten by it. */
		FVector FocusOff;
		float ManualLeft = 0.f;          // seconds the stick's turn still holds
		int Side = 0;                    // +1 / -1: which side of the line between them; 0 unset
		// blows
		float KickAge = 1e9f, KickSign = 1.f, KickStrength = 0.f;
		// orbit
		EOrbit Orbit = EOrbit::None;
		float OrbitAge = 0.f, OrbitSign = 1.f;
		// walls: the boom's length after them, and its length before them
		float WallArm = -1.f;

		/** A heavy blow or a parry, on Saud or by him. Strength 0..1; Sign
		    which way the picture tips. */
		void Kick(float Strength, float Sign)
		{
			KickAge = 0.f;
			KickStrength = Strength < 0.f ? 0.f : (Strength > 1.f ? 1.f : Strength);
			KickSign = Sign < 0.f ? -1.f : 1.f;
		}

		/** The rage finisher, or a man knocked out: swing round him. A
		    finisher is never cut short by a knockout it causes. */
		void StartOrbit(EOrbit Kind)
		{
			if (Kind == EOrbit::None) return;
			if (Orbit == EOrbit::Finisher && Kind == EOrbit::Knockout && OrbitAge < FinisherOrbit.Seconds) return;
			Orbit = Kind;
			OrbitAge = 0.f;
			OrbitSign = Side < 0 ? -1.f : 1.f;
		}

		const FOrbitSpec* OrbitSpec() const
		{
			return Orbit == EOrbit::Finisher ? &FinisherOrbit : Orbit == EOrbit::Knockout ? &KnockoutOrbit : nullptr;
		}

		/** One tick: the view to hold, before walls. */
		FView Tick(const FInputs& In)
		{
			const float Dt = In.Dt > 0.f ? In.Dt : 0.f;
			const FVector Root = In.Saud;
			const FVector Head = Root + FVector(0.0, 0.0, SocketUpCm);
			if (!bStarted)
			{
				bStarted = true;
				FocusOff = FVector(0.0, 0.0, 0.0);
			}

			// --- the stick
			const bool bTurning = std::fabs(In.LookX) > 0.05f || std::fabs(In.LookY) > 0.05f;
			if (bTurning)
			{
				View.Yaw = Wrap180(View.Yaw + In.LookX * TurnRate * Dt);
				View.Pitch = View.Pitch - In.LookY * PitchRate * Dt;
				View.Pitch = View.Pitch < MinPitchDeg ? MinPitchDeg : (View.Pitch > MaxPitchDeg ? MaxPitchDeg : View.Pitch);
				ManualLeft = ManualHoldSeconds;
			}
			else if (ManualLeft > 0.f)
			{
				ManualLeft -= Dt;
			}
			const bool bAuto = ManualLeft <= 0.f && !bTurning;

			// --- who is near: weighted toward the nearest
			FVector Sum(0.0, 0.0, 0.0);
			double WSum = 0.0;
			float Spread = 0.f;
			int Near = 0;
			for (int I = 0; I < In.NumOpponents; ++I)
			{
				const FVector To = In.Opponents[I] - Root;
				const float D = Flat(To);
				if (D > EngageCm) continue;
				const double W = 1.0 / (1.0 + D / 300.0);
				Sum += In.Opponents[I] * W;
				WSum += W;
				++Near;
			}
			View.bFighting = Near > 0;

			float WantYaw = View.Yaw, WantPitch = PitchDeg, WantArm = IdleArmCm, YTau = FollowYawTau;
			FVector WantFocus = Head;
			const float Speed = Flat(In.Velocity);

			if (View.bFighting)
			{
				const FVector C = Sum / WSum;
				const FVector Mid = Root + (C - Root) * FocusShare;
				WantFocus = FVector(Mid.X, Mid.Y, Head.Z);
				const float Axis = YawOf(C - Root);
				// the side the camera is already nearer, unless the other is clearly nearer
				const float A = Wrap180(Axis + SideDeg), B = Wrap180(Axis - SideDeg);
				const float DA = std::fabs(Wrap180(A - View.Yaw)), DB = std::fabs(Wrap180(B - View.Yaw));
				if (Side == 0) Side = DA <= DB ? 1 : -1;
				else if (Side > 0 && DB + SideSwitchDeg < DA) Side = -1;
				else if (Side < 0 && DA + SideSwitchDeg < DB) Side = 1;
				WantYaw = Side > 0 ? A : B;
				WantPitch = FightPitchDeg;
				YTau = YawTau;
				// pull back until Saud and every near man sit inside the picture
				const float Half = static_cast<float>(std::tan(HFovDeg * 0.5 * 3.14159265358979 / 180.0)) * FitShare;
				float Need = FightArmMinCm;
				for (int I = -1; I < In.NumOpponents; ++I)
				{
					const FVector P = I < 0 ? Root : In.Opponents[I];
					if (I >= 0 && Flat(P - Root) > EngageCm) continue;
					// in the camera's own frame: along its forward, and across it
					const float Ry = static_cast<float>(WantYaw * 3.14159265358979 / 180.0);
					const FVector D = P - WantFocus;
					const float Along = static_cast<float>(D.X * std::cos(Ry) + D.Y * std::sin(Ry));
					const float Across = static_cast<float>(-D.X * std::sin(Ry) + D.Y * std::cos(Ry));
					// at distance Arm + Along from the eye, |Across| must fit Half of it
					const float Arm = std::fabs(Across) / Half - Along;
					if (Arm > Need) Need = Arm;
				}
				Spread = Need;
				WantArm = Need > FightArmMaxCm ? FightArmMaxCm : Need;
			}
			else
			{
				const float Run = Speed / RunSpeedCm > 1.f ? 1.f : Speed / RunSpeedCm;
				WantArm = IdleArmCm + (RunArmCm - IdleArmCm) * Run;
				if (Speed > MovingCm)
				{
					// in behind where he is going, as fast as he is going
					const float Behind = YawOf(In.Velocity);
					const float Step = RecentreDegPerSec * Run * Dt;
					const float Gap = Wrap180(Behind - View.Yaw);
					WantYaw = View.Yaw + (std::fabs(Gap) <= Step ? Gap : (Gap > 0.f ? Step : -Step));
					YTau = 0.f;
					const FVector Ahead = In.Velocity * LookAheadSeconds;
					const float L = Flat(Ahead);
					const FVector Cap = L > LookAheadMaxCm ? Ahead * (LookAheadMaxCm / L) : Ahead;
					WantFocus = Head + FVector(Cap.X, Cap.Y, 0.0);
				}
			}
			(void)Spread;

			// --- the orbit, laid over everything
			float OrbitYaw = 0.f, ArmMul = 1.f;
			if (const FOrbitSpec* O = OrbitSpec())
			{
				OrbitAge += Dt;
				const float T = OrbitAge / O->Seconds;
				if (T >= 1.f)
				{
					Orbit = EOrbit::None;
				}
				else
				{
					// out and back: the sweep rises and the arm and pitch dip, then all return
					const float Bell = std::sin(3.14159265f * T);
					OrbitYaw = OrbitSign * O->SweepDeg * Smooth(T * 1.6f) * (T < 0.7f ? 1.f : 1.f - Smooth((T - 0.7f) / 0.3f));
					ArmMul = 1.f - (1.f - O->ArmShare) * Bell;
					WantPitch = WantPitch + (O->PitchDeg - WantPitch) * Bell;
				}
			}

			// --- ease toward it
			if (bAuto)
			{
				View.Yaw = Wrap180(EaseAngle(View.Yaw, WantYaw, Dt, YTau));
				View.Pitch = View.Pitch + (WantPitch - View.Pitch) * Ease(Dt, PitchTau);
			}
			View.Arm = View.Arm + (WantArm - View.Arm) * Ease(Dt, ArmTau);
			const float E = Ease(Dt, FocusTau);
			const FVector WantOff = WantFocus - Head;
			FocusOff = FocusOff + (FVector(WantOff.X, WantOff.Y, 0.0) - FocusOff) * E;
			View.Focus = Head + FocusOff;

			// --- the blow's tip and push, springing back
			KickAge += Dt;
			float Roll = 0.f, Push = 0.f;
			if (KickAge < 1.f)
			{
				const float Env = std::exp(-KickAge / KickDecaySec);
				Roll = KickSign * KickRollDeg * KickStrength * Env * std::cos(2.f * 3.14159265f * KickFreqHz * KickAge);
				Push = KickPush * KickStrength * Env;
			}

			FView Out = View;
			Out.Yaw = Wrap180(View.Yaw + OrbitYaw);
			Out.Arm = View.Arm * ArmMul * (1.f - Push);
			Out.Roll = Roll;
			return Out;
		}

		/**
		 * The boom against the world. Want is the length the view asks for;
		 * SoftFree how far the game's probe found clear when it looked
		 * SoftMarginCm past the camera (Want + SoftMarginCm if nothing);
		 * HardFree how far it is clear at the camera itself. The boom comes in
		 * before the wall reaches it, eases out slowly, and is never longer
		 * than HardFree.
		 */
		float WallStep(float Want, float SoftFree, float HardFree, float Dt)
		{
			float Target = SoftFree - SoftMarginCm;
			if (Target > Want) Target = Want;
			if (Target < 0.f) Target = 0.f;
			if (WallArm < 0.f) WallArm = Target;
			const float Tau = Target < WallArm ? WallInTau : WallOutTau;
			float Step = (Target - WallArm) * Ease(Dt, Tau);
			if (Step > WallOutMaxCmPerSec * Dt) Step = WallOutMaxCmPerSec * Dt;
			WallArm = WallArm + Step;
			if (WallArm > HardFree) WallArm = HardFree;
			if (WallArm < 0.f) WallArm = 0.f;
			return WallArm;
		}
	};

	/** One occluder's fade, toward FadeMax while it stands between the camera
	    and Saud and back to 0 when it does not. */
	inline float FadeStep(float Fade, bool bBetween, float Dt)
	{
		if (bBetween)
		{
			Fade += FadeMax * (Dt / FadeInSec);
			return Fade > FadeMax ? FadeMax : Fade;
		}
		Fade -= FadeMax * (Dt / FadeOutSec);
		return Fade < 0.f ? 0.f : Fade;
	}
}
