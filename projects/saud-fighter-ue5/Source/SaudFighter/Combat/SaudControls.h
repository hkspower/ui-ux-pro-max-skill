#pragma once

/**
 * The controls -- with no engine in it.
 *
 * Asked 2026-09-30 (Riyadh) as "improve buttons layout with xbox and ps 5
 * controller", settled as: one mapping table for the fight and the menus,
 * the pad's own words for every button (Xbox: A B X Y LB RB LT RT L3 R3
 * MENU VIEW; PlayStation: CROSS CIRCLE SQUARE TRIANGLE L1 R1 L2 R2 L3 R3
 * OPTIONS CREATE), the Unreal key names the engine binds by, the glyphs the
 * prompts are drawn with, and the controls screen's diagram: a stylised pad
 * with every button in its place and a leader line from each to the action
 * it carries. Until this day the Unreal build had no input in C++ at all.
 *
 * The mapping (the design decision, recorded once; see the design note):
 *
 *   fight     Move          left stick            W A S D, arrows
 *             Look          right stick           mouse
 *             Punch         west  (X / SQUARE)    J
 *             Kick          south (A / CROSS)     K
 *             Block/parry   RB or LB (R1 / L1)    L
 *             Dash          east  (B / CIRCLE)    Shift  (and Block tapped while moving, in the game)
 *             Rage          north (Y / TRIANGLE)  Space, U
 *             Pause         MENU / OPTIONS        Esc, P
 *             unbound       LT RT L3 R3 VIEW/CREATE d-pad
 *   menu      Navigate      d-pad, left stick     arrows, W S    (repeat: 0.35 s, then 0.12 s)
 *             Confirm       south                 Enter, Space
 *             Back          east                  Esc, Backspace
 *             Flip the pad  LB or RB              Q, E, Tab
 *             Resume        MENU / OPTIONS        Esc, P
 *
 * Punch west and kick south are the two most-reached face buttons; block
 * is a shoulder because a block is a hold, and either shoulder because half
 * of players guard with the left hand; dash has its own button (east); rage
 * is north, the deliberate reach; confirm south / back east is the Xbox and
 * Western PS5 convention. Adjusting a setting is NavLeft/NavRight (and
 * Confirm cycles): no action of its own.
 *
 * Everything is drawn through FGlyphSink, whose Tri and Text mirror
 * SaudHud::FDrawList's: a triangle with a colour per vertex and a part
 * (EControlsPart), a text as a slot and a value (EControlsText), never a
 * string -- ControlsText() turns the pair into the word, so a draw list
 * stays plain data as the HUD's does. FHudListSink below is the one-struct
 * adapter onto SaudHud::FDrawList; SaudMenu has its own onto its list.
 *
 * The diagram (BuildControlsPage) is laid out in page px (SaudHud::FPage,
 * 1920 x 1080 scaled by height) inside the title-safe area, between a head
 * band (HeadBand page px under the top safe line, for the screen's title)
 * and a foot band (FootBand above the bottom one, for the prompt strip).
 * The keyboard list stands at the right of the pad when the safe area is
 * wide enough (16:9 and wider, 16:10), else under it in two columns (4:3).
 * The pad's left side is the family's own: an Xbox pad's left stick is
 * upper left with a small d-pad under it, a DualSense's d-pad is at the
 * left middle with both sticks low. LayControls() is the layout as data,
 * so the harness can hold that every label is where the layout says and
 * says what the table binds, and that no leader crosses a button or another
 * leader.
 *
 * Only the HUD's palette (SaudHud::Colour): Ink, Bone, Blood, Ember, Trough,
 * Ash, Gold. Header of free functions and plain structs, like SaudAnime.h,
 * so Tools/harness builds it with g++ and checks it (tests/controls.cpp).
 */

#include "SaudAnime.h"

namespace SaudControls
{
	using SaudChar = SaudAnime::SaudChar;
	using SaudHud::FPoint;
	using SaudHud::FRgba;
	using SaudHud::FPage;

	// ------------------------------------------------------------ the names
	enum class EPad : unsigned char { Xbox, PlayStation, Keyboard };
	enum class EButton : unsigned char
	{
		FaceSouth, FaceEast, FaceWest, FaceNorth, LB, RB, LT, RT, L3, R3,
		Menu, View, DpadUp, DpadDown, DpadLeft, DpadRight, LeftStick, RightStick, Count
	};
	enum class EAction : unsigned char
	{
		Move, Look, Punch, Kick, Block, Dash, Rage, Pause,
		NavUp, NavDown, NavLeft, NavRight, Confirm, Back, FlipPad, Count
	};
	enum class EContext : unsigned char { Fight, Menu };

	constexpr int NumButtons = static_cast<int>(EButton::Count);
	constexpr int NumActions = static_cast<int>(EAction::Count);
	/** Move .. Pause: the actions the fight context binds and the diagram lists. */
	constexpr int NumFightActions = static_cast<int>(EAction::Pause) + 1;

	/** A menu's navigation repeats while the d-pad or stick is held: the
	    first repeat after this long, then every NavRepeatNext. The engine
	    turns the stick's axis into a direction with these. */
	constexpr float NavRepeatFirst = 0.35f;
	constexpr float NavRepeatNext = 0.12f;

	struct FBinding { EAction Action; EContext Context; EButton Button; };
	struct FKeyBinding { EAction Action; EContext Context; const SaudChar* KeyName; };

	// ------------------------------------------------------------ the table
	/** The pad bindings, both families (a pad's buttons are the same
	    buttons under either name). Block sits on both shoulders; the left
	    stick carries all four menu directions (the engine reads the axis). */
	inline const FBinding* PadBindings(int& Count)
	{
		static const FBinding Table[] = {
			{EAction::Move, EContext::Fight, EButton::LeftStick},
			{EAction::Look, EContext::Fight, EButton::RightStick},
			{EAction::Punch, EContext::Fight, EButton::FaceWest},
			{EAction::Kick, EContext::Fight, EButton::FaceSouth},
			{EAction::Block, EContext::Fight, EButton::RB},
			{EAction::Block, EContext::Fight, EButton::LB},
			{EAction::Dash, EContext::Fight, EButton::FaceEast},
			{EAction::Rage, EContext::Fight, EButton::FaceNorth},
			{EAction::Pause, EContext::Fight, EButton::Menu},

			{EAction::NavUp, EContext::Menu, EButton::DpadUp},
			{EAction::NavDown, EContext::Menu, EButton::DpadDown},
			{EAction::NavLeft, EContext::Menu, EButton::DpadLeft},
			{EAction::NavRight, EContext::Menu, EButton::DpadRight},
			{EAction::NavUp, EContext::Menu, EButton::LeftStick},
			{EAction::NavDown, EContext::Menu, EButton::LeftStick},
			{EAction::NavLeft, EContext::Menu, EButton::LeftStick},
			{EAction::NavRight, EContext::Menu, EButton::LeftStick},
			{EAction::Confirm, EContext::Menu, EButton::FaceSouth},
			{EAction::Back, EContext::Menu, EButton::FaceEast},
			{EAction::FlipPad, EContext::Menu, EButton::LB},
			{EAction::FlipPad, EContext::Menu, EButton::RB},
			{EAction::Pause, EContext::Menu, EButton::Menu},     // resume
		};
		Count = static_cast<int>(sizeof(Table) / sizeof(Table[0]));
		return Table;
	}

	/** The keyboard and mouse, by Unreal's key names (EKeys; FKey(Name)).
	    Move and Look are Axis2D under the engine: W/S and the arrows with a
	    swizzle and a negate, A/D as they are, the mouse as Mouse2D. Dash by
	    Block tapped while moving is the game's, not a binding. */
	inline const FKeyBinding* KeyBindings(int& Count)
	{
		static const FKeyBinding Table[] = {
			{EAction::Move, EContext::Fight, SAUD_TEXT("W")},
			{EAction::Move, EContext::Fight, SAUD_TEXT("A")},
			{EAction::Move, EContext::Fight, SAUD_TEXT("S")},
			{EAction::Move, EContext::Fight, SAUD_TEXT("D")},
			{EAction::Move, EContext::Fight, SAUD_TEXT("Up")},
			{EAction::Move, EContext::Fight, SAUD_TEXT("Down")},
			{EAction::Move, EContext::Fight, SAUD_TEXT("Left")},
			{EAction::Move, EContext::Fight, SAUD_TEXT("Right")},
			{EAction::Look, EContext::Fight, SAUD_TEXT("Mouse2D")},
			{EAction::Punch, EContext::Fight, SAUD_TEXT("J")},
			{EAction::Kick, EContext::Fight, SAUD_TEXT("K")},
			{EAction::Block, EContext::Fight, SAUD_TEXT("L")},
			{EAction::Dash, EContext::Fight, SAUD_TEXT("LeftShift")},
			{EAction::Rage, EContext::Fight, SAUD_TEXT("SpaceBar")},
			{EAction::Rage, EContext::Fight, SAUD_TEXT("U")},
			{EAction::Pause, EContext::Fight, SAUD_TEXT("Escape")},
			{EAction::Pause, EContext::Fight, SAUD_TEXT("P")},

			{EAction::NavUp, EContext::Menu, SAUD_TEXT("Up")},
			{EAction::NavUp, EContext::Menu, SAUD_TEXT("W")},
			{EAction::NavDown, EContext::Menu, SAUD_TEXT("Down")},
			{EAction::NavDown, EContext::Menu, SAUD_TEXT("S")},
			{EAction::NavLeft, EContext::Menu, SAUD_TEXT("Left")},
			{EAction::NavRight, EContext::Menu, SAUD_TEXT("Right")},
			{EAction::Confirm, EContext::Menu, SAUD_TEXT("Enter")},
			{EAction::Confirm, EContext::Menu, SAUD_TEXT("SpaceBar")},
			{EAction::Back, EContext::Menu, SAUD_TEXT("Escape")},
			{EAction::Back, EContext::Menu, SAUD_TEXT("BackSpace")},
			{EAction::FlipPad, EContext::Menu, SAUD_TEXT("Q")},
			{EAction::FlipPad, EContext::Menu, SAUD_TEXT("E")},
			{EAction::FlipPad, EContext::Menu, SAUD_TEXT("Tab")},
			{EAction::Pause, EContext::Menu, SAUD_TEXT("Escape")},
			{EAction::Pause, EContext::Menu, SAUD_TEXT("P")},
		};
		Count = static_cast<int>(sizeof(Table) / sizeof(Table[0]));
		return Table;
	}

	/** Unreal's name for a pad button (EKeys). The sticks are their 2D
	    axes; L3 and R3 are the clicks. */
	inline const SaudChar* UEKeyName(EButton Button)
	{
		static const SaudChar* const Names[NumButtons] = {
			SAUD_TEXT("Gamepad_FaceButton_Bottom"), SAUD_TEXT("Gamepad_FaceButton_Right"),
			SAUD_TEXT("Gamepad_FaceButton_Left"), SAUD_TEXT("Gamepad_FaceButton_Top"),
			SAUD_TEXT("Gamepad_LeftShoulder"), SAUD_TEXT("Gamepad_RightShoulder"),
			SAUD_TEXT("Gamepad_LeftTrigger"), SAUD_TEXT("Gamepad_RightTrigger"),
			SAUD_TEXT("Gamepad_LeftThumbstick"), SAUD_TEXT("Gamepad_RightThumbstick"),
			SAUD_TEXT("Gamepad_Special_Right"), SAUD_TEXT("Gamepad_Special_Left"),
			SAUD_TEXT("Gamepad_DPad_Up"), SAUD_TEXT("Gamepad_DPad_Down"),
			SAUD_TEXT("Gamepad_DPad_Left"), SAUD_TEXT("Gamepad_DPad_Right"),
			SAUD_TEXT("Gamepad_Left2D"), SAUD_TEXT("Gamepad_Right2D"),
		};
		const int I = static_cast<int>(Button);
		return I >= 0 && I < NumButtons ? Names[I] : Names[0];
	}

	/** The word for a button in the prompts and the diagram, by family. A
	    keyboard has no pad buttons: it is given the Xbox words. */
	inline const SaudChar* Label(EButton Button, EPad Pad)
	{
		static const SaudChar* const Xbox[NumButtons] = {
			SAUD_TEXT("A"), SAUD_TEXT("B"), SAUD_TEXT("X"), SAUD_TEXT("Y"),
			SAUD_TEXT("LB"), SAUD_TEXT("RB"), SAUD_TEXT("LT"), SAUD_TEXT("RT"), SAUD_TEXT("L3"), SAUD_TEXT("R3"),
			SAUD_TEXT("MENU"), SAUD_TEXT("VIEW"),
			SAUD_TEXT("UP"), SAUD_TEXT("DOWN"), SAUD_TEXT("LEFT"), SAUD_TEXT("RIGHT"),
			SAUD_TEXT("LS"), SAUD_TEXT("RS"),
		};
		static const SaudChar* const PlayStation[NumButtons] = {
			SAUD_TEXT("CROSS"), SAUD_TEXT("CIRCLE"), SAUD_TEXT("SQUARE"), SAUD_TEXT("TRIANGLE"),
			SAUD_TEXT("L1"), SAUD_TEXT("R1"), SAUD_TEXT("L2"), SAUD_TEXT("R2"), SAUD_TEXT("L3"), SAUD_TEXT("R3"),
			SAUD_TEXT("OPTIONS"), SAUD_TEXT("CREATE"),
			SAUD_TEXT("UP"), SAUD_TEXT("DOWN"), SAUD_TEXT("LEFT"), SAUD_TEXT("RIGHT"),
			SAUD_TEXT("LS"), SAUD_TEXT("RS"),
		};
		const int I = static_cast<int>(Button);
		if (I < 0 || I >= NumButtons)
		{
			return SAUD_TEXT("?");
		}
		return Pad == EPad::PlayStation ? PlayStation[I] : Xbox[I];
	}

	/** The word for an action, as the diagram and the prompts print it. */
	inline const SaudChar* ActionName(EAction Action)
	{
		static const SaudChar* const Names[NumActions] = {
			SAUD_TEXT("MOVE"), SAUD_TEXT("CAMERA"), SAUD_TEXT("PUNCH"), SAUD_TEXT("KICK"),
			SAUD_TEXT("BLOCK / PARRY"), SAUD_TEXT("DASH"), SAUD_TEXT("RAGE"), SAUD_TEXT("PAUSE"),
			SAUD_TEXT("UP"), SAUD_TEXT("DOWN"), SAUD_TEXT("LEFT"), SAUD_TEXT("RIGHT"),
			SAUD_TEXT("SELECT"), SAUD_TEXT("BACK"), SAUD_TEXT("FLIP PAD"),
		};
		const int I = static_cast<int>(Action);
		return I >= 0 && I < NumActions ? Names[I] : SAUD_TEXT("?");
	}

	/** The keyboard's word for an action: what the diagram's list and a
	    keyboard prompt print beside its name (the keys of KeyBindings, in
	    the player's words). */
	inline const SaudChar* KeyPrompt(EAction Action)
	{
		static const SaudChar* const Names[NumActions] = {
			SAUD_TEXT("W A S D"), SAUD_TEXT("MOUSE"), SAUD_TEXT("J"), SAUD_TEXT("K"),
			SAUD_TEXT("L"), SAUD_TEXT("SHIFT"), SAUD_TEXT("SPACE / U"), SAUD_TEXT("ESC / P"),
			SAUD_TEXT("UP / W"), SAUD_TEXT("DOWN / S"), SAUD_TEXT("LEFT"), SAUD_TEXT("RIGHT"),
			SAUD_TEXT("ENTER"), SAUD_TEXT("ESC"), SAUD_TEXT("Q / E / TAB"),
		};
		const int I = static_cast<int>(Action);
		return I >= 0 && I < NumActions ? Names[I] : SAUD_TEXT("?");
	}

	/** The family's name, the diagram's caption. */
	inline const SaudChar* PadName(EPad Pad)
	{
		return Pad == EPad::PlayStation ? SAUD_TEXT("PLAYSTATION")
		     : (Pad == EPad::Keyboard ? SAUD_TEXT("KEYBOARD") : SAUD_TEXT("XBOX"));
	}

	namespace Detail
	{
		inline SaudChar Lower(SaudChar C)
		{
			return (C >= 'A' && C <= 'Z') ? static_cast<SaudChar>(C + ('a' - 'A')) : C;
		}
		/** Needle (lower case) somewhere in Hay, case-insensitively. */
		inline bool Contains(const SaudChar* Hay, const SaudChar* Needle)
		{
			if (!Hay || !Needle)
			{
				return false;
			}
			for (int i = 0; Hay[i]; ++i)
			{
				int j = 0;
				while (Needle[j] && Hay[i + j] && Lower(Hay[i + j]) == Needle[j])
				{
					++j;
				}
				if (!Needle[j])
				{
					return true;
				}
			}
			return false;
		}
		inline int Chars(const SaudChar* S)
		{
			int N = 0;
			while (S && S[N])
			{
				++N;
			}
			return N;
		}
	}

	/** The family from the hardware's name (UInputDeviceSubsystem's
	    FHardwareDeviceIdentifier, or a platform's own): Sony's names to
	    PlayStation, anything else -- an Xbox pad, a generic one, nothing --
	    to Xbox, the words most players know. */
	inline EPad PadFromDeviceName(const SaudChar* HardwareName)
	{
		static const SaudChar* const Sony[] = {
			SAUD_TEXT("dualsense"), SAUD_TEXT("dualshock"), SAUD_TEXT("playstation"),
			SAUD_TEXT("sony"), SAUD_TEXT("ps5"), SAUD_TEXT("ps4"),
		};
		for (const SaudChar* Needle : Sony)
		{
			if (Detail::Contains(HardwareName, Needle))
			{
				return EPad::PlayStation;
			}
		}
		return EPad::Xbox;
	}

	// ------------------------------------------------------------- the sink
	/** What a triangle is part of, so a list can find a rule's shapes. */
	enum class EControlsPart : unsigned char
	{
		Rim,     // a button's or the pad's rim
		Face,    // a button's disc or tab
		Body,    // the pad's body, grips and d-pad cross
		Line,    // a leader line
		Label    // a button's marking drawn as geometry: a PlayStation shape, the menu bars, a stick's dot
	};
	/** Which word a text is, with its value: ControlsText() gives the string.
	    ButtonLabel: Value from EncodeButtonLabel (button and family);
	    ActionName / KeyName: the EAction; Unbound: "--"; PadName: the EPad. */
	enum class EControlsText : unsigned char { ButtonLabel, ActionName, Unbound, KeyName, PadName };

	inline int EncodeButtonLabel(EButton Button, EPad Pad)
	{
		return static_cast<int>(Pad) * 32 + static_cast<int>(Button);
	}
	inline const SaudChar* ControlsText(EControlsText Slot, int Value)
	{
		switch (Slot)
		{
		case EControlsText::ButtonLabel:
		{
			const int P = Value / 32, B = Value % 32;
			return Label(B >= 0 && B < NumButtons ? static_cast<EButton>(B) : EButton::FaceSouth,
			             P == 1 ? EPad::PlayStation : EPad::Xbox);
		}
		case EControlsText::ActionName:
			return ActionName(Value >= 0 && Value < NumActions ? static_cast<EAction>(Value) : EAction::Move);
		case EControlsText::KeyName:
			return KeyPrompt(Value >= 0 && Value < NumActions ? static_cast<EAction>(Value) : EAction::Move);
		case EControlsText::PadName:
			return PadName(Value == 1 ? EPad::PlayStation : (Value == 2 ? EPad::Keyboard : EPad::Xbox));
		case EControlsText::Unbound:
		default:
			return SAUD_TEXT("--");
		}
	}

	/** Where the glyphs and the diagram draw to: Tri and Text mirror
	    SaudHud::FDrawList's (a colour per vertex, a text as slot and value),
	    with this header's own part and slot enums, so an adapter onto any
	    list is one struct with two overrides. */
	struct FGlyphSink
	{
		virtual ~FGlyphSink() {}
		virtual void Tri(const FPoint& A, const FRgba& CA, const FPoint& B, const FRgba& CB, const FPoint& C,
		                 const FRgba& CC, EControlsPart Part) = 0;
		virtual void Text(EControlsText Slot, int Value, const FPoint& At, float Height, const FRgba& C, float Stroke,
		                  bool bCentre) = 0;
	};

	/** The adapter onto the HUD's own list: triangles under one group and
	    part, texts in the Name slot with the controls slot folded into the
	    value (Slot * 4096 + Value), since FHudText has no slot of ours. */
	struct FHudListSink final : public FGlyphSink
	{
		SaudHud::FDrawList& Out;
		SaudHud::EHudGroup Group;
		SaudHud::EHudPart Part;
		FHudListSink(SaudHud::FDrawList& InOut, SaudHud::EHudGroup InGroup, SaudHud::EHudPart InPart)
			: Out(InOut), Group(InGroup), Part(InPart) {}
		void Tri(const FPoint& A, const FRgba& CA, const FPoint& B, const FRgba& CB, const FPoint& C, const FRgba& CC,
		         EControlsPart) override
		{
			Out.Tri(A, CA, B, CB, C, CC, Group, Part);
		}
		void Text(EControlsText Slot, int Value, const FPoint& At, float Height, const FRgba& C, float Stroke,
		          bool bCentre) override
		{
			Out.Text(SaudHud::EHudText::Name, static_cast<int>(Slot) * 4096 + Value, At, Height, C, Stroke, bCentre, Group);
		}
	};

	// ------------------------------------------------------------ the type
	/** A capital's advance as a share of the text height: the width estimate
	    the layout keeps labels apart with (SaudMenu's is the same). */
	constexpr float CharAdvance = 0.62f;
	inline float TextWidth(const SaudChar* S, float Height)
	{
		return static_cast<float>(Detail::Chars(S)) * CharAdvance * Height;
	}

	// ----------------------------------------------------------- the shapes
	namespace Detail
	{
		constexpr float Pi = 3.14159265f;
		constexpr int DiscSegments = 20;

		/** Every triangle wound the same way on the screen (Y down), as the
		    HUD's are, whichever order a shape's corners came in. */
		inline void Tri3(FGlyphSink& Out, const FPoint& A, const FPoint& B, const FPoint& C, const FRgba& Col,
		                 EControlsPart Part)
		{
			const float Cross = (B.X - A.X) * (C.Y - A.Y) - (B.Y - A.Y) * (C.X - A.X);
			if (Cross < 0.f)
			{
				Out.Tri(A, Col, C, Col, B, Col, Part);
			}
			else
			{
				Out.Tri(A, Col, B, Col, C, Col, Part);
			}
		}
		inline void Quad4(FGlyphSink& Out, const FPoint Q[4], const FRgba& Col, EControlsPart Part)
		{
			Tri3(Out, Q[0], Q[1], Q[2], Col, Part);
			Tri3(Out, Q[0], Q[2], Q[3], Col, Part);
		}
		inline void Fan(FGlyphSink& Out, const FPoint& Centre, const FPoint* Ring, int N, const FRgba& Col,
		                EControlsPart Part)
		{
			for (int i = 0; i < N; ++i)
			{
				Tri3(Out, Centre, Ring[i], Ring[(i + 1) % N], Col, Part);
			}
		}
		inline void Rect(FGlyphSink& Out, float X, float Y, float W, float H, const FRgba& Col, EControlsPart Part)
		{
			const FPoint Q[4] = {{X, Y + H}, {X, Y}, {X + W, Y}, {X + W, Y + H}};
			Quad4(Out, Q, Col, Part);
		}
		/** A bar Len long and Wid wide, centred, turned by Angle (radians). */
		inline void Bar(FGlyphSink& Out, const FPoint& C, float Len, float Wid, float Angle, const FRgba& Col,
		                EControlsPart Part)
		{
			const float Ca = FMath::Cos(Angle), Sa = FMath::Sin(Angle);
			const float Hl = 0.5f * Len, Hw = 0.5f * Wid;
			const float Lx[4] = {-Hl, -Hl, Hl, Hl}, Ly[4] = {Hw, -Hw, -Hw, Hw};
			FPoint Q[4];
			for (int i = 0; i < 4; ++i)
			{
				Q[i] = {C.X + Lx[i] * Ca - Ly[i] * Sa, C.Y + Lx[i] * Sa + Ly[i] * Ca};
			}
			Quad4(Out, Q, Col, Part);
		}
		/** A line from A to B, Wid wide. */
		inline void Line(FGlyphSink& Out, const FPoint& A, const FPoint& B, float Wid, const FRgba& Col,
		                 EControlsPart Part)
		{
			float Dx = B.X - A.X, Dy = B.Y - A.Y;
			const float L = FMath::Max(FMath::Sqrt(Dx * Dx + Dy * Dy), 1e-6f);
			Dx /= L;
			Dy /= L;
			const float Nx = -Dy * 0.5f * Wid, Ny = Dx * 0.5f * Wid;
			const FPoint Q[4] = {{A.X + Nx, A.Y + Ny}, {B.X + Nx, B.Y + Ny}, {B.X - Nx, B.Y - Ny}, {A.X - Nx, A.Y - Ny}};
			Quad4(Out, Q, Col, Part);
		}
		inline void CirclePoints(const FPoint& C, float R, int N, FPoint* Ring)
		{
			for (int i = 0; i < N; ++i)
			{
				const float A = 2.f * Pi * static_cast<float>(i) / static_cast<float>(N);
				Ring[i] = {C.X + R * FMath::Cos(A), C.Y + R * FMath::Sin(A)};
			}
		}
		inline void Disc(FGlyphSink& Out, const FPoint& C, float R, const FRgba& Col, EControlsPart Part)
		{
			FPoint Ring[DiscSegments];
			CirclePoints(C, R, DiscSegments, Ring);
			Fan(Out, C, Ring, DiscSegments, Col, Part);
		}
		/** A ring of outer radius R and width W, as quads (no overdraw). */
		inline void Ring(FGlyphSink& Out, const FPoint& C, float R, float W, const FRgba& Col, EControlsPart Part)
		{
			FPoint Outer[DiscSegments], Inner[DiscSegments];
			CirclePoints(C, R, DiscSegments, Outer);
			CirclePoints(C, R - W, DiscSegments, Inner);
			for (int i = 0; i < DiscSegments; ++i)
			{
				const int j = (i + 1) % DiscSegments;
				const FPoint Q[4] = {Outer[i], Outer[j], Inner[j], Inner[i]};
				Quad4(Out, Q, Col, Part);
			}
		}
		/** A rimmed disc: the rim's colour to R, the fill inside it. */
		inline void RimmedDisc(FGlyphSink& Out, const FPoint& C, float R, float RimPx, const FRgba& Rim,
		                       const FRgba& Fill)
		{
			Disc(Out, C, R, Rim, EControlsPart::Rim);
			Disc(Out, C, R - RimPx, Fill, EControlsPart::Face);
		}

		constexpr int CornerSegments = 5;
		/** A rounded box's outline, clockwise on the screen from the top-left
		    corner: the top corners always rounded by R, the bottom ones when
		    bRoundBottom (a tab has a flat bottom). Points written to Ring
		    (at most 4 * (CornerSegments + 1)); returns how many. */
		inline int BoxRing(const FPoint& C, float W, float H, float R, bool bRoundBottom, FPoint* Ring)
		{
			const float Hw = 0.5f * W, Hh = 0.5f * H;
			const float Rr = FMath::Min(R, FMath::Min(Hw, Hh));
			int N = 0;
			const FPoint Corners[4] = {{C.X - Hw + Rr, C.Y - Hh + Rr}, {C.X + Hw - Rr, C.Y - Hh + Rr},
			                           {C.X + Hw - Rr, C.Y + Hh - Rr}, {C.X - Hw + Rr, C.Y + Hh - Rr}};
			const float Start[4] = {Pi, 1.5f * Pi, 0.f, 0.5f * Pi};
			for (int k = 0; k < 4; ++k)
			{
				if (k >= 2 && !bRoundBottom)
				{
					Ring[N++] = k == 2 ? FPoint{C.X + Hw, C.Y + Hh} : FPoint{C.X - Hw, C.Y + Hh};
					continue;
				}
				for (int i = 0; i <= CornerSegments; ++i)
				{
					const float A = Start[k] + 0.5f * Pi * static_cast<float>(i) / static_cast<float>(CornerSegments);
					Ring[N++] = {Corners[k].X + Rr * FMath::Cos(A), Corners[k].Y + Rr * FMath::Sin(A)};
				}
			}
			return N;
		}
		/** The rim round an outline: quads between it and its copy grown
		    RimPx outward (GrowRing) -- a ring, not a disc under the fill, so a
		    translucent fill stays translucent. */
		inline void RimRing(FGlyphSink& Out, const FPoint* Ring, int N, float RimPx, const FRgba& Rim)
		{
			FPoint Grown[64];
			SaudHud::GrowRing(Ring, N, RimPx, Grown);
			for (int i = 0; i < N; ++i)
			{
				const int j = (i + 1) % N;
				const FPoint Q[4] = {Ring[i], Ring[j], Grown[j], Grown[i]};
				Quad4(Out, Q, Rim, EControlsPart::Rim);
			}
		}
		/** A rimmed rounded box: the box, then its rim round it. */
		inline void RimmedBox(FGlyphSink& Out, const FPoint& C, float W, float H, float R, bool bRoundBottom,
		                      float RimPx, const FRgba& Rim, const FRgba& Fill, EControlsPart FillPart)
		{
			FPoint Ring[4 * (CornerSegments + 1)];
			const int N = BoxRing(C, W, H, R, bRoundBottom, Ring);
			Fan(Out, C, Ring, N, Fill, FillPart);
			RimRing(Out, Ring, N, RimPx, Rim);
		}
		/** The part of a ring under the line Y = ClipY (Sutherland-Hodgman
		    against the one half-plane): the points inside, and where an edge
		    crosses, the crossing. Out holds up to N + 2; returns how many. */
		inline int ClipBelow(const FPoint* In, int N, float ClipY, FPoint* Out)
		{
			int M = 0;
			for (int i = 0; i < N; ++i)
			{
				const FPoint& S = In[i];
				const FPoint& E = In[(i + 1) % N];
				const bool bS = S.Y >= ClipY, bE = E.Y >= ClipY;
				if (bS != bE)
				{
					const float T = (ClipY - S.Y) / (E.Y - S.Y);
					Out[M++] = {S.X + (E.X - S.X) * T, ClipY};
				}
				if (bE)
				{
					Out[M++] = E;
				}
			}
			return M;
		}
		/** A rimmed ellipse turned by Tilt (radians), cut off flat above
		    ClipY: the pad's grips hang under the body's bottom edge and never
		    show through it. Its centre must be under the line. */
		inline void RimmedEllipse(FGlyphSink& Out, const FPoint& C, float A, float B, float Tilt, float ClipY,
		                          float RimPx, const FRgba& Rim, const FRgba& Fill, EControlsPart FillPart)
		{
			constexpr int N = 24;
			FPoint Ring[N], Cut[N + 2];
			const float Ct = FMath::Cos(Tilt), St = FMath::Sin(Tilt);
			for (int i = 0; i < N; ++i)
			{
				const float T = 2.f * Pi * static_cast<float>(i) / static_cast<float>(N);
				const float X = A * FMath::Cos(T), Y = B * FMath::Sin(T);
				Ring[i] = {C.X + X * Ct - Y * St, C.Y + X * St + Y * Ct};
			}
			const int M = ClipBelow(Ring, N, ClipY, Cut);
			if (M < 3)
			{
				return;
			}
			Fan(Out, C, Cut, M, Fill, FillPart);
			RimRing(Out, Cut, M, RimPx, Rim);
		}
		/** The d-pad's cross: four arms Half long and 2 * ArmHalfW wide from
		    C, each in its own colour (up, down, left, right). */
		inline void DpadCross(FGlyphSink& Out, const FPoint& C, float Half, float ArmHalfW, const FRgba& Up,
		                      const FRgba& Down, const FRgba& Left, const FRgba& Right, EControlsPart Part)
		{
			Rect(Out, C.X - ArmHalfW, C.Y - Half, 2.f * ArmHalfW, Half, Up, Part);
			Rect(Out, C.X - ArmHalfW, C.Y, 2.f * ArmHalfW, Half, Down, Part);
			Rect(Out, C.X - Half, C.Y - ArmHalfW, Half, 2.f * ArmHalfW, Left, Part);
			Rect(Out, C.X, C.Y - ArmHalfW, Half, 2.f * ArmHalfW, Right, Part);
		}
	}

	// ------------------------------------------------------------ the glyph
	// Shares of a glyph's Size (its disc's diameter, a tab's height).
	constexpr float GlyphRim = 0.06f;        // a button's rim, at least 1.5 px
	constexpr float LetterShare = 0.66f;     // a letter's height: 31.7 page px at the prompt strip's Size 48, over 1/36
	constexpr float TriangleRadius = 0.34f;  // the PlayStation triangle's corners from its centre
	constexpr float DpadGlyphArm = 0.30f;    // a d-pad glyph's arms, from the centre...
	constexpr float DpadGlyphHead = 0.19f;   // ...the lit arm's arrowhead, half its base...
	constexpr float DpadTip = 0.43f;         // ...and its tip
	constexpr float DpadDimAlpha = 0.45f;    // the three unlit arms: Ash at this
	constexpr float LetterStroke = 0.10f;    // the ink round it (3 page px at Size 30)
	constexpr float ShapeStroke = 0.11f;     // a PlayStation shape's line
	constexpr float TabWide = 2.3f;          // a shoulder tab's width
	constexpr float TabCorner = 0.35f;
	constexpr float TriggerWide = 1.9f;      // a trigger tab's width
	constexpr float TriggerCorner = 0.45f;
	constexpr float StickRing = 0.10f;       // a stick's ring width
	constexpr float StickDot = 0.16f;        // its dot's radius

	/** One button's glyph, centred at (CentreX, CentreY), Size across, in
	    the caller's px. InkColour is the button's disc or tab, FillColour its
	    marking: an Xbox face button is a disc with its letter, a PlayStation
	    one a disc with its shape drawn as geometry (cross: two bars; circle:
	    a ring; square and triangle: hollow), every shape in FillColour and
	    the circle's rim in Blood -- the one PlayStation accent the palette
	    has -- the rest in Ash. Shoulders and triggers are rounded tabs with
	    their name; Menu / Options a disc with three bars; View / Create a
	    disc with two rectangles; a stick a ring with a dot; its click (L3 /
	    R3) a disc with its name; a d-pad direction the cross in a disc with
	    that arm in FillColour. A Keyboard pad draws the Xbox glyph. */
	inline void Glyph(EButton Button, EPad Pad, float CentreX, float CentreY, float Size, FRgba InkColour,
	                  FRgba FillColour, FGlyphSink& Out)
	{
		using namespace Detail;
		using namespace SaudHud::Colour;
		const EPad Family = Pad == EPad::Keyboard ? EPad::Xbox : Pad;
		const FPoint C = {CentreX, CentreY};
		const float S = Size;
		const float RimPx = FMath::Max(1.5f, GlyphRim * S);
		const float LetterH = LetterShare * S;
		const float Stroke = LetterStroke * S;
		const int Word = EncodeButtonLabel(Button, Family);
		const auto Letter = [&](float H)
		{
			Out.Text(EControlsText::ButtonLabel, Word, {C.X, C.Y - 0.5f * H}, H, FillColour, Stroke, true);
		};

		switch (Button)
		{
		case EButton::FaceSouth:
		case EButton::FaceEast:
		case EButton::FaceWest:
		case EButton::FaceNorth:
		{
			const bool bPS = Family == EPad::PlayStation;
			RimmedDisc(Out, C, 0.5f * S, RimPx, bPS && Button == EButton::FaceEast ? Blood : Ash, InkColour);
			if (!bPS)
			{
				Letter(LetterH);
				break;
			}
			const float Line = ShapeStroke * S;
			if (Button == EButton::FaceSouth)          // cross: two bars
			{
				Bar(Out, C, 0.56f * S, Line, 0.25f * Pi, FillColour, EControlsPart::Label);
				Bar(Out, C, 0.56f * S, Line, -0.25f * Pi, FillColour, EControlsPart::Label);
			}
			else if (Button == EButton::FaceEast)      // circle: a ring
			{
				Ring(Out, C, 0.30f * S, Line, FillColour, EControlsPart::Label);
			}
			else if (Button == EButton::FaceWest)      // square: hollow
			{
				const float Hs = 0.26f * S;
				Rect(Out, C.X - Hs, C.Y - Hs, 2.f * Hs, Line, FillColour, EControlsPart::Label);
				Rect(Out, C.X - Hs, C.Y + Hs - Line, 2.f * Hs, Line, FillColour, EControlsPart::Label);
				Rect(Out, C.X - Hs, C.Y - Hs + Line, Line, 2.f * Hs - 2.f * Line, FillColour, EControlsPart::Label);
				Rect(Out, C.X + Hs - Line, C.Y - Hs + Line, Line, 2.f * Hs - 2.f * Line, FillColour, EControlsPart::Label);
			}
			else                                       // triangle: hollow, point up, mitred corners
			{
				const float Ro = TriangleRadius * S, Ri = Ro - Line * 1.1547f;   // the inner triangle: a line in, mitred
				FPoint V[3], W[3];
				for (int i = 0; i < 3; ++i)
				{
					const float A = -0.5f * Pi + 2.f * Pi * static_cast<float>(i) / 3.f;
					V[i] = {C.X + Ro * FMath::Cos(A), C.Y + Ro * FMath::Sin(A)};
					W[i] = {C.X + Ri * FMath::Cos(A), C.Y + Ri * FMath::Sin(A)};
				}
				for (int i = 0; i < 3; ++i)
				{
					const int j = (i + 1) % 3;
					const FPoint Q[4] = {V[i], V[j], W[j], W[i]};
					Quad4(Out, Q, FillColour, EControlsPart::Label);
				}
			}
			break;
		}
		case EButton::LB:
		case EButton::RB:
			RimmedBox(Out, C, TabWide * S, S, TabCorner * S, false, RimPx, Ash, InkColour, EControlsPart::Face);
			Letter(0.7f * S);
			break;
		case EButton::LT:
		case EButton::RT:
			RimmedBox(Out, C, TriggerWide * S, S, TriggerCorner * S, false, RimPx, Ash, InkColour, EControlsPart::Face);
			Letter(0.7f * S);
			break;
		case EButton::L3:
		case EButton::R3:
			RimmedDisc(Out, C, 0.5f * S, RimPx, Ash, InkColour);
			Letter(LetterH);
			break;
		case EButton::Menu:
			RimmedDisc(Out, C, 0.5f * S, RimPx, Ash, InkColour);
			for (int i = -1; i <= 1; ++i)
			{
				Rect(Out, C.X - 0.25f * S, C.Y + 0.2f * S * static_cast<float>(i) - 0.045f * S, 0.5f * S, 0.09f * S,
				     FillColour, EControlsPart::Label);
			}
			break;
		case EButton::View:
			RimmedDisc(Out, C, 0.5f * S, RimPx, Ash, InkColour);
			Rect(Out, C.X - 0.22f * S, C.Y - 0.22f * S, 0.30f * S, 0.26f * S, FillColour, EControlsPart::Label);
			Rect(Out, C.X - 0.11f * S, C.Y - 0.07f * S, 0.36f * S, 0.32f * S, InkColour, EControlsPart::Label);
			Rect(Out, C.X - 0.08f * S, C.Y - 0.04f * S, 0.30f * S, 0.26f * S, FillColour, EControlsPart::Label);
			break;
		case EButton::DpadUp:
		case EButton::DpadDown:
		case EButton::DpadLeft:
		case EButton::DpadRight:
		{
			RimmedDisc(Out, C, 0.5f * S, RimPx, Ash, InkColour);
			const FRgba Dim = SaudHud::WithAlpha(Ash, DpadDimAlpha);
			const float Half = DpadGlyphArm * S, Hw = 0.10f * S;
			DpadCross(Out, C, Half, Hw,
			          Button == EButton::DpadUp ? FillColour : Dim, Button == EButton::DpadDown ? FillColour : Dim,
			          Button == EButton::DpadLeft ? FillColour : Dim, Button == EButton::DpadRight ? FillColour : Dim,
			          EControlsPart::Label);
			// the arrowhead on the lit arm: its base across the arm's end, its tip toward the rim
			const float Dx = Button == EButton::DpadLeft ? -1.f : (Button == EButton::DpadRight ? 1.f : 0.f);
			const float Dy = Button == EButton::DpadUp ? -1.f : (Button == EButton::DpadDown ? 1.f : 0.f);
			const float Hb = DpadGlyphHead * S, Tip = DpadTip * S;
			Tri3(Out, {C.X + Dx * Tip, C.Y + Dy * Tip}, {C.X + Dx * Half - Dy * Hb, C.Y + Dy * Half + Dx * Hb},
			     {C.X + Dx * Half + Dy * Hb, C.Y + Dy * Half - Dx * Hb}, FillColour, EControlsPart::Label);
			break;
		}
		case EButton::LeftStick:
		case EButton::RightStick:
			Ring(Out, C, 0.5f * S, StickRing * S, FillColour, EControlsPart::Rim);
			Disc(Out, C, StickDot * S, FillColour, EControlsPart::Label);
			break;
		default:
			break;
		}
	}

	// ---------------------------------------------------------- the diagram
	// Page px. The pad is drawn about its centre; the labels hang off it.
	constexpr float HeadBand = 100.f;        // left clear under the top safe line: the screen's title
	constexpr float FootBand = 90.f;         // ...and over the bottom one: the prompt strip
	constexpr float LabelText = 30.f;        // every word the player reads: 1/36 of the height
	constexpr float BodyW = 400.f, BodyH = 200.f, BodyCorner = 30.f;
	constexpr float GripX = 108.f, GripY = 105.f, GripA = 58.f, GripB = 108.f, GripTilt = 18.f;   // degrees
	constexpr float PadRim = 3.f;
	constexpr float BodyAlpha = 0.40f;       // the body's Ash wash over the dark
	/** The two pads differ on the left: a DualSense has its d-pad at the
	    left middle and both sticks low; an Xbox pad has its left stick
	    there and a smaller d-pad under it. The right stick is low on both. */
	constexpr float PSDpadX = -115.f, PSDpadY = 0.f, PSDpadHalf = 50.f, PSDpadArm = 11.f;
	constexpr float PSStickX = -50.f, PSStickY = 60.f;
	constexpr float XboxStickX = -115.f, XboxStickY = 0.f;
	constexpr float XboxDpadX = -52.f, XboxDpadY = 60.f, XboxDpadHalf = 36.f, XboxDpadArm = 9.f;
	constexpr float FaceX = 115.f, FaceSpread = 48.f, FaceSize = 50.f;
	constexpr float StickX = 50.f, StickY = 60.f, StickSize = 44.f;   // the right stick
	constexpr float MenuX = 36.f, MenuY = -58.f, MenuSize = 32.f;
	constexpr float ShoulderX = 120.f, ShoulderY = -123.f, ShoulderSize = 44.f;
	constexpr float TriggerY = -176.f;       // clear of the shoulder's rim
	constexpr float LabelGap = 250.f;        // a side label's near edge, from the pad's centre
	constexpr float LabelW = 242.f;          // the widest label, "BLOCK / PARRY", at LabelText
	constexpr float RowTop = -185.f, RowPitch = 40.f;   // the side labels' rows (centres)
	constexpr float TopRowY = -230.f, TopLabelX = 60.f; // the menu and view labels, over the pad
	constexpr float UnderLabelX = 150.f;     // the stick clicks' labels, under the grips beside the caption
	constexpr float LeadInset = 8.f;         // a leader stops this short of its label
	constexpr float LeaderPx = 2.f;
	constexpr float CaptionY = 237.f;        // the family's name under the pad
	constexpr float ListKeyX = 300.f;        // a list row: the action, then its key here (room for a wider font)
	constexpr float ListW = 467.f;           // ...the row's width ("SPACE / U")
	constexpr float ListGap = 40.f;          // between the labels and the list beside them
	constexpr float ListBelowY = 307.f;      // the first row's centre when the list is under the pad
	constexpr float PadBlockHalf = LabelGap + LabelW;
	constexpr float BlockWide = 2.f * PadBlockHalf + ListGap + ListW;   // pad, labels and the list beside: 1491

	/** One button's place in the diagram. */
	struct FSlot
	{
		FPoint Centre;              // screen px
		float Size = 0.f;           // Glyph's Size, screen px; 0: not drawn as a glyph (the d-pad's arms
		                            // are the cross, a stick's click is the stick)
		bool bLabel = false;
		EControlsText LabelSlot = EControlsText::Unbound;
		int LabelValue = 0;
		FPoint LabelAt;             // the label's anchor: top-left, or top-centre when bLabelCentre
		bool bLabelCentre = false;
		FPoint LeadFrom, LeadTo;    // its leader line
	};
	struct FControlsLayout
	{
		FPoint PadCentre;
		float LabelH = 0.f, Stroke = 0.f;
		FSlot Slot[NumButtons];
		FPoint DpadCentre;          // the cross, screen px
		float DpadHalf = 0.f, DpadArm = 0.f;
		FPoint CaptionAt;           // top-centre
		bool bListBeside = false;
		FPoint ListName[NumFightActions], ListKey[NumFightActions];   // top-left
	};

	/** The fight action a button carries, as the diagram's label: the
	    ActionName, or Unbound. */
	inline void DiagramLabel(EButton Button, EControlsText& Slot, int& Value)
	{
		int N = 0;
		const FBinding* B = PadBindings(N);
		for (int i = 0; i < N; ++i)
		{
			if (B[i].Context == EContext::Fight && B[i].Button == Button)
			{
				Slot = EControlsText::ActionName;
				Value = static_cast<int>(B[i].Action);
				return;
			}
		}
		Slot = EControlsText::Unbound;
		Value = 0;
	}

	/** Where every button sits and where its label goes, for one family (a
	    Keyboard is laid out as Xbox). Every leader has its own origin on its
	    button's edge, and none crosses another button or another leader:
	    the face cluster's four go right, the left-hand buttons left, Menu
	    and View up, the stick clicks down to under the grips. */
	inline FControlsLayout LayControls(const FPage& P, EPad Pad)
	{
		enum { None, Left, Right, Top, Under };
		enum { Edge, StickBottom, DpadArmEnd };
		struct FSpec { float X, Y, Size; int Side; int Row; int From; };
		static const FSpec PS[NumButtons] = {
			{FaceX, FaceSpread, FaceSize, Right, 5, Edge},                 // FaceSouth
			{FaceX + FaceSpread, 0.f, FaceSize, Right, 4, Edge},           // FaceEast
			{FaceX - FaceSpread, 0.f, FaceSize, Right, 3, Edge},           // FaceWest: out between north and east
			{FaceX, -FaceSpread, FaceSize, Right, 2, Edge},                // FaceNorth
			{-ShoulderX, ShoulderY, ShoulderSize, Left, 1, Edge},          // LB
			{ShoulderX, ShoulderY, ShoulderSize, Right, 1, Edge},          // RB
			{-ShoulderX, TriggerY, ShoulderSize, Left, 0, Edge},           // LT
			{ShoulderX, TriggerY, ShoulderSize, Right, 0, Edge},           // RT
			{PSStickX, PSStickY, 0.f, Under, 0, StickBottom},              // L3: the stick, led from its bottom
			{StickX, StickY, 0.f, Under, 0, StickBottom},                  // R3
			{MenuX, MenuY, MenuSize, Top, 0, Edge},                        // Menu
			{-MenuX, MenuY, MenuSize, Top, 0, Edge},                       // View
			{PSDpadX, PSDpadY - 0.5f * PSDpadHalf, 0.f, Left, 4, DpadArmEnd},   // DpadUp: the cross's one label
			{PSDpadX, PSDpadY + 0.5f * PSDpadHalf, 0.f, None, 0, Edge},    // DpadDown
			{PSDpadX - 0.5f * PSDpadHalf, PSDpadY, 0.f, None, 0, Edge},    // DpadLeft
			{PSDpadX + 0.5f * PSDpadHalf, PSDpadY, 0.f, None, 0, Edge},    // DpadRight
			{PSStickX, PSStickY, StickSize, Left, 7, Edge},                // LeftStick
			{StickX, StickY, StickSize, Right, 8, Edge},                   // RightStick
		};
		static const FSpec Xbox[NumButtons] = {
			{FaceX, FaceSpread, FaceSize, Right, 5, Edge},
			{FaceX + FaceSpread, 0.f, FaceSize, Right, 4, Edge},
			{FaceX - FaceSpread, 0.f, FaceSize, Right, 3, Edge},
			{FaceX, -FaceSpread, FaceSize, Right, 2, Edge},
			{-ShoulderX, ShoulderY, ShoulderSize, Left, 1, Edge},
			{ShoulderX, ShoulderY, ShoulderSize, Right, 1, Edge},
			{-ShoulderX, TriggerY, ShoulderSize, Left, 0, Edge},
			{ShoulderX, TriggerY, ShoulderSize, Right, 0, Edge},
			{XboxStickX, XboxStickY, 0.f, Left, 5, StickBottom},           // L3: out left under the stick
			{StickX, StickY, 0.f, Under, 0, StickBottom},                  // R3
			{MenuX, MenuY, MenuSize, Top, 0, Edge},
			{-MenuX, MenuY, MenuSize, Top, 0, Edge},
			{XboxDpadX, XboxDpadY - 0.5f * XboxDpadHalf, 0.f, Under, 0, DpadArmEnd},   // DpadUp: the cross's label, under the grip
			{XboxDpadX, XboxDpadY + 0.5f * XboxDpadHalf, 0.f, None, 0, Edge},
			{XboxDpadX - 0.5f * XboxDpadHalf, XboxDpadY, 0.f, None, 0, Edge},
			{XboxDpadX + 0.5f * XboxDpadHalf, XboxDpadY, 0.f, None, 0, Edge},
			{XboxStickX, XboxStickY, StickSize, Left, 3, Edge},            // LeftStick: upper left
			{StickX, StickY, StickSize, Right, 8, Edge},
		};
		const bool bPS = Pad == EPad::PlayStation;
		const FSpec* Spec = bPS ? PS : Xbox;

		FControlsLayout L;
		L.LabelH = P.Px(LabelText);
		L.Stroke = P.Px(SaudHud::TextStroke);
		const float SafeW = (P.Right() - P.Left()) / P.Scale;
		L.bListBeside = SafeW >= BlockWide;
		const float SafeCX = 0.5f * (P.Left() + P.Right());
		const float BandTop = P.Top() + P.Px(HeadBand);
		const float BandH = (P.Bottom() - P.Px(FootBand) - BandTop) / P.Scale;
		const float DiagramTop = TopRowY - 0.5f * LabelText;
		const float DiagramBottom = L.bListBeside ? CaptionY + 0.5f * LabelText
		                                          : ListBelowY + 3.f * RowPitch + 0.5f * LabelText;
		const float CX = L.bListBeside ? SafeCX - P.Px(0.5f * BlockWide - PadBlockHalf) : SafeCX;
		const float CY = BandTop + P.Px(0.5f * (BandH - (DiagramBottom - DiagramTop)) - DiagramTop);
		L.PadCentre = {CX, CY};
		L.DpadCentre = {CX + P.Px(bPS ? PSDpadX : XboxDpadX), CY + P.Px(bPS ? PSDpadY : XboxDpadY)};
		L.DpadHalf = P.Px(bPS ? PSDpadHalf : XboxDpadHalf);
		L.DpadArm = P.Px(bPS ? PSDpadArm : XboxDpadArm);

		for (int b = 0; b < NumButtons; ++b)
		{
			const FSpec& S = Spec[b];
			FSlot& Sl = L.Slot[b];
			Sl.Centre = {CX + P.Px(S.X), CY + P.Px(S.Y)};
			Sl.Size = P.Px(S.Size);
			if (S.Side == None)
			{
				continue;
			}
			Sl.bLabel = true;
			DiagramLabel(static_cast<EButton>(b), Sl.LabelSlot, Sl.LabelValue);
			const float W = TextWidth(ControlsText(Sl.LabelSlot, Sl.LabelValue), L.LabelH);
			const float Sign = S.X > 0.f ? 1.f : -1.f;
			if (S.Side == Top)
			{
				const float LX = CX + Sign * P.Px(TopLabelX);
				Sl.bLabelCentre = true;
				Sl.LabelAt = {LX, CY + P.Px(TopRowY) - 0.5f * L.LabelH};
				Sl.LeadTo = {LX, CY + P.Px(TopRowY + 0.5f * LabelText + LeadInset)};
			}
			else if (S.Side == Under)
			{
				const float LX = CX + Sign * P.Px(UnderLabelX);
				Sl.bLabelCentre = true;
				Sl.LabelAt = {LX, CY + P.Px(CaptionY) - 0.5f * L.LabelH};
				Sl.LeadTo = {LX, CY + P.Px(CaptionY - 0.5f * LabelText - LeadInset)};
			}
			else
			{
				const float RowY = CY + P.Px(RowTop + RowPitch * static_cast<float>(S.Row));
				const float Dir = S.Side == Right ? 1.f : -1.f;
				Sl.LabelAt = {S.Side == Right ? CX + P.Px(LabelGap) : CX - P.Px(LabelGap) - W, RowY - 0.5f * L.LabelH};
				Sl.LeadTo = {CX + Dir * P.Px(LabelGap - LeadInset), RowY};
			}
			// the leader leaves the glyph's edge toward its label; a click's
			// leaves the stick's bottom; the d-pad's the end of the arm that
			// faces its label
			if (S.From == StickBottom)
			{
				Sl.LeadFrom = {Sl.Centre.X, Sl.Centre.Y + 0.5f * P.Px(StickSize)};
			}
			else if (S.From == DpadArmEnd)
			{
				Sl.LeadFrom = S.Side == Under ? FPoint{L.DpadCentre.X, L.DpadCentre.Y + L.DpadHalf}
				                              : FPoint{L.DpadCentre.X - L.DpadHalf, L.DpadCentre.Y};
			}
			else
			{
				float Dx = Sl.LeadTo.X - Sl.Centre.X, Dy = Sl.LeadTo.Y - Sl.Centre.Y;
				const float D = FMath::Max(FMath::Sqrt(Dx * Dx + Dy * Dy), 1e-6f);
				Dx /= D;
				Dy /= D;
				Sl.LeadFrom = {Sl.Centre.X + Dx * 0.5f * Sl.Size, Sl.Centre.Y + Dy * 0.5f * Sl.Size};
			}
		}

		L.CaptionAt = {CX, CY + P.Px(CaptionY) - 0.5f * L.LabelH};
		for (int a = 0; a < NumFightActions; ++a)
		{
			float X0, RowY;
			if (L.bListBeside)
			{
				X0 = CX + P.Px(PadBlockHalf + ListGap);
				RowY = CY + P.Px(RowPitch * (static_cast<float>(a) - 0.5f * static_cast<float>(NumFightActions - 1)));
			}
			else
			{
				const int Col = a < 4 ? 0 : 1;
				X0 = Col == 0 ? CX - P.Px(ListW + 0.5f * ListGap) : CX + P.Px(0.5f * ListGap);
				RowY = CY + P.Px(ListBelowY + RowPitch * static_cast<float>(a - 4 * Col));
			}
			L.ListName[a] = {X0, RowY - 0.5f * L.LabelH};
			L.ListKey[a] = {X0 + P.Px(ListKeyX), RowY - 0.5f * L.LabelH};
		}
		return L;
	}

	/** The controls screen's diagram for one family (a Keyboard shows the
	    Xbox pad): the grips and body, the d-pad cross, a leader from every
	    labelled button, every button's glyph, the labels, the family's name
	    under the pad, and the keyboard's list of the fight actions with their
	    keys. Pure: the same page and family give the same list. */
	inline void BuildControlsPage(const FPage& P, EPad Shown, FGlyphSink& Out)
	{
		using namespace Detail;
		using namespace SaudHud::Colour;
		const EPad Family = Shown == EPad::Keyboard ? EPad::Xbox : Shown;
		const FControlsLayout L = LayControls(P, Family);
		const FPoint C = L.PadCentre;
		const float Rim = FMath::Max(1.f, P.Px(PadRim));
		const FRgba Body = SaudHud::WithAlpha(Ash, BodyAlpha);

		// the pad: two grips, the body over them, the d-pad cross (ink in an ash rim)
		const float Tilt = FMath::DegreesToRadians(GripTilt);
		const float BodyBottom = C.Y + P.Px(0.5f * BodyH);
		RimmedEllipse(Out, {C.X - P.Px(GripX), C.Y + P.Px(GripY)}, P.Px(GripA), P.Px(GripB), Tilt, BodyBottom, Rim, Ash,
		              Body, EControlsPart::Body);
		RimmedEllipse(Out, {C.X + P.Px(GripX), C.Y + P.Px(GripY)}, P.Px(GripA), P.Px(GripB), -Tilt, BodyBottom, Rim, Ash,
		              Body, EControlsPart::Body);
		RimmedBox(Out, C, P.Px(BodyW), P.Px(BodyH), P.Px(BodyCorner), true, Rim, Ash, Body, EControlsPart::Body);
		DpadCross(Out, L.DpadCentre, L.DpadHalf + Rim, L.DpadArm + Rim, Ash, Ash, Ash, Ash, EControlsPart::Rim);
		DpadCross(Out, L.DpadCentre, L.DpadHalf, L.DpadArm, Ink, Ink, Ink, Ink, EControlsPart::Body);

		// the leaders, under the glyphs so each leaves a button's edge
		for (int b = 0; b < NumButtons; ++b)
		{
			const FSlot& S = L.Slot[b];
			if (S.bLabel)
			{
				Line(Out, S.LeadFrom, S.LeadTo, FMath::Max(1.f, P.Px(LeaderPx)), Ash, EControlsPart::Line);
			}
		}
		// the buttons
		for (int b = 0; b < NumButtons; ++b)
		{
			const FSlot& S = L.Slot[b];
			if (S.Size > 0.f)
			{
				Glyph(static_cast<EButton>(b), Family, S.Centre.X, S.Centre.Y, S.Size, Ink, Bone, Out);
			}
		}
		// the labels
		for (int b = 0; b < NumButtons; ++b)
		{
			const FSlot& S = L.Slot[b];
			if (S.bLabel)
			{
				Out.Text(S.LabelSlot, S.LabelValue, S.LabelAt, L.LabelH, Bone, L.Stroke, S.bLabelCentre);
			}
		}
		Out.Text(EControlsText::PadName, static_cast<int>(Family), L.CaptionAt, L.LabelH, Bone, L.Stroke, true);

		// the keyboard: the same actions, their keys
		for (int a = 0; a < NumFightActions; ++a)
		{
			Out.Text(EControlsText::ActionName, a, L.ListName[a], L.LabelH, Bone, L.Stroke, false);
			Out.Text(EControlsText::KeyName, a, L.ListKey[a], L.LabelH, Bone, L.Stroke, false);
		}
	}
}
