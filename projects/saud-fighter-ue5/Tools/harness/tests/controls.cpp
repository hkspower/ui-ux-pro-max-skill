/**
 * The controls, executed: the one mapping table (every fight action on a
 * pad button and a key, no button carrying two fight actions, every menu
 * action bound, confirm and back apart), the pad's words (Xbox and
 * PlayStation differ where the pads do), Unreal's key names (a fixed list
 * here, not the header's), the family from a device's name, the glyphs
 * (never degenerate, the letter or the shape as the family has it) -- and
 * the controls diagram as BuildControlsPage DRAWS it at every screen shape
 * a console or PC puts it on: inside title-safe and the head and foot
 * bands, no label over another, every bound button's label the action the
 * table binds, a leader from each, the keyboard's list beside or under it.
 *
 * Every check here has a sabotage in Tools/harness/bites.txt that
 * Tools/harness/bite.sh applies to a copy and proves is caught.
 */
#include "../HarnessTypes.h"
#include "../../../Source/SaudFighter/Combat/SaudControls.h"

#include <cstdio>
#include <cmath>
#include <cstring>

static int Fails = 0;
static void Check(bool Ok, const char* What)
{
    if (!Ok) { ++Fails; std::printf("  FAIL  %s\n", What); }
}
static bool Same(const char* A, const char* B) { return A && B && std::strcmp(A, B) == 0; }

using namespace SaudControls;
using SaudHud::FPoint;
using SaudHud::FRgba;
using SaudHud::FPage;

// ------------------------------------------------------------ the sink
struct FRecTri { FPoint P[3]; FRgba C[3]; EControlsPart Part; };
struct FRecText { EControlsText Slot; int Value; FPoint At; float Height; FRgba Colour; float Stroke; bool bCentre; };
constexpr int MaxRecTris = 4096, MaxRecTexts = 128;
struct FRecSink final : public FGlyphSink
{
    FRecTri Tris[MaxRecTris];
    int NumTris = 0;
    FRecText Texts[MaxRecTexts];
    int NumTexts = 0;
    bool bOverflow = false;
    void Reset() { NumTris = 0; NumTexts = 0; bOverflow = false; }
    void Tri(const FPoint& A, const FRgba& CA, const FPoint& B, const FRgba& CB, const FPoint& C, const FRgba& CC,
             EControlsPart Part) override
    {
        if (NumTris >= MaxRecTris) { bOverflow = true; return; }
        Tris[NumTris++] = {{A, B, C}, {CA, CB, CC}, Part};
    }
    void Text(EControlsText Slot, int Value, const FPoint& At, float Height, const FRgba& C, float Stroke,
              bool bCentre) override
    {
        if (NumTexts >= MaxRecTexts) { bOverflow = true; return; }
        Texts[NumTexts++] = {Slot, Value, At, Height, C, Stroke, bCentre};
    }
};
static FRecSink List;

// ------------------------------------------------------------ helpers
static const float Shapes[][2] = {{1920, 1080}, {1280, 720}, {3840, 2160}, {2560, 1080},
                                  {3440, 1440}, {1600, 1200}, {1680, 1050}};
// Title-safe is the broadcast standard, 90 % of each dimension -- written
// here rather than read from the header, so a header that forgot it fails.
static bool InSafe(const FPage& P, float X, float Y)
{
    const float E = 0.5f, MX = 0.05f * P.ScreenW, MY = 0.05f * P.ScreenH;
    return X >= MX - E && Y >= MY - E && X <= P.ScreenW - MX + E && Y <= P.ScreenH - MY + E;
}
static float Cross(const FPoint& A, const FPoint& B, const FPoint& C)
{
    return (B.X - A.X) * (C.Y - A.Y) - (B.Y - A.Y) * (C.X - A.X);
}
/** WCAG 2.1 contrast of two linear colours. */
static float Contrast(const FRgba& A, const FRgba& B)
{
    const float La = 0.2126f * A.R + 0.7152f * A.G + 0.0722f * A.B;
    const float Lb = 0.2126f * B.R + 0.7152f * B.G + 0.0722f * B.B;
    return (std::fmax(La, Lb) + 0.05f) / (std::fmin(La, Lb) + 0.05f);
}
static bool SameRgb(const FRgba& A, const FRgba& B)
{
    return std::fabs(A.R - B.R) < 1e-4f && std::fabs(A.G - B.G) < 1e-4f && std::fabs(A.B - B.B) < 1e-4f;
}
/** The HUD's seven, or a d-pad arm dimmed on the line from Ink to Bone. */
static bool IsPalette(const FRgba& C)
{
    using namespace SaudHud::Colour;
    if (SameRgb(C, Ink) || SameRgb(C, Bone) || SameRgb(C, Blood) || SameRgb(C, Ember) || SameRgb(C, Trough)
        || SameRgb(C, Ash) || SameRgb(C, Gold)) return true;
    const float T = (C.R - Ink.R) / (Bone.R - Ink.R);
    return T >= -1e-4f && T <= 1.f + 1e-4f && std::fabs(C.G - (Ink.G + (Bone.G - Ink.G) * T)) < 1e-3f
           && std::fabs(C.B - (Ink.B + (Bone.B - Ink.B) * T)) < 1e-3f;
}
struct FBox { float X0 = 1e9f, Y0 = 1e9f, X1 = -1e9f, Y1 = -1e9f; bool Any = false; };
static bool Overlap(const FBox& A, const FBox& B)
{
    return A.Any && B.Any && A.X0 < B.X1 && B.X0 < A.X1 && A.Y0 < B.Y1 && B.Y0 < A.Y1;
}
/** A text's box from its anchor, its height and its word: 0.62 of the
    height per capital, written here, not read from the header. */
static FBox TextBox(const FRecText& X)
{
    const float W = 0.62f * X.Height * static_cast<float>(std::strlen(ControlsText(X.Slot, X.Value)));
    FBox B;
    B.X0 = X.bCentre ? X.At.X - 0.5f * W : X.At.X;
    B.X1 = B.X0 + W;
    B.Y0 = X.At.Y;
    B.Y1 = X.At.Y + X.Height;
    B.Any = true;
    return B;
}
static float Dist(const FPoint& A, const FPoint& B)
{
    return std::sqrt((A.X - B.X) * (A.X - B.X) + (A.Y - B.Y) * (A.Y - B.Y));
}
static const FRecText* TextAt(const FPoint& At, float Tol = 0.5f)
{
    for (int t = 0; t < List.NumTexts; ++t)
        if (std::fabs(List.Texts[t].At.X - At.X) <= Tol && std::fabs(List.Texts[t].At.Y - At.Y) <= Tol)
            return &List.Texts[t];
    return nullptr;
}
static int CountPart(EControlsPart Pt)
{
    int N = 0;
    for (int t = 0; t < List.NumTris; ++t) N += List.Tris[t].Part == Pt;
    return N;
}

// ---------------------------------------------------------- MAPPING
static bool IsFight(EAction A) { return static_cast<int>(A) <= static_cast<int>(EAction::Pause); }
static bool IsMenu(EAction A) { return !IsFight(A) || A == EAction::Pause; }

/** Unreal's key names (InputCoreTypes, EKeys), the ones a fighter could
    bind: written here so a name the engine would not know fails. */
static bool IsUEKey(const char* K)
{
    if (!K || !K[0]) return false;
    if (std::strlen(K) == 1 && K[0] >= 'A' && K[0] <= 'Z') return true;
    static const char* const Names[] = {
        "Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
        "Up", "Down", "Left", "Right", "SpaceBar", "Enter", "Escape", "BackSpace", "Tab",
        "LeftShift", "RightShift", "LeftControl", "RightControl", "LeftAlt", "RightAlt",
        "Mouse2D", "MouseX", "MouseY", "LeftMouseButton", "RightMouseButton", "MiddleMouseButton",
        "Gamepad_FaceButton_Bottom", "Gamepad_FaceButton_Right", "Gamepad_FaceButton_Left", "Gamepad_FaceButton_Top",
        "Gamepad_LeftShoulder", "Gamepad_RightShoulder", "Gamepad_LeftTrigger", "Gamepad_RightTrigger",
        "Gamepad_LeftTriggerAxis", "Gamepad_RightTriggerAxis", "Gamepad_LeftThumbstick", "Gamepad_RightThumbstick",
        "Gamepad_Special_Left", "Gamepad_Special_Right",
        "Gamepad_DPad_Up", "Gamepad_DPad_Down", "Gamepad_DPad_Left", "Gamepad_DPad_Right",
        "Gamepad_Left2D", "Gamepad_Right2D", "Gamepad_LeftX", "Gamepad_LeftY", "Gamepad_RightX", "Gamepad_RightY",
    };
    for (const char* N : Names) if (Same(N, K)) return true;
    return false;
}

static void Mapping()
{
    std::printf("MAPPING  (one table, the fight and the menus)\n");
    int NP = 0, NK = 0;
    const FBinding* Pad = PadBindings(NP);
    const FKeyBinding* Key = KeyBindings(NK);
    std::printf("  %d pad bindings, %d key bindings, %d buttons, %d actions\n", NP, NK, NumButtons, NumActions);
    Check(NP > 0 && NK > 0, "the tables are not empty");

    // every fight action has at least one pad button and one key
    bool PadFight = true, KeyFight = true;
    for (int a = 0; a < NumActions; ++a)
    {
        const EAction A = static_cast<EAction>(a);
        if (!IsFight(A)) continue;
        bool HasPad = false, HasKey = false;
        for (int i = 0; i < NP; ++i) HasPad = HasPad || (Pad[i].Action == A && Pad[i].Context == EContext::Fight);
        for (int i = 0; i < NK; ++i) HasKey = HasKey || (Key[i].Action == A && Key[i].Context == EContext::Fight);
        if (!HasPad) { PadFight = false; std::printf("  %s has no pad button in the fight\n", ActionName(A)); }
        if (!HasKey) { KeyFight = false; std::printf("  %s has no key in the fight\n", ActionName(A)); }
    }
    Check(PadFight, "every fight action has a pad button");
    Check(KeyFight, "every fight action has a key");

    // no pad button carries two fight actions (Block on both shoulders is
    // one action on two buttons, the other way round)
    bool OneEach = true;
    for (int b = 0; b < NumButtons; ++b)
    {
        int Carried = -1;
        for (int i = 0; i < NP; ++i)
        {
            if (Pad[i].Context != EContext::Fight || Pad[i].Button != static_cast<EButton>(b)) continue;
            const int A = static_cast<int>(Pad[i].Action);
            if (Carried >= 0 && Carried != A)
            {
                OneEach = false;
                std::printf("  %s carries %s and %s\n", Label(static_cast<EButton>(b), EPad::Xbox),
                            ActionName(static_cast<EAction>(Carried)), ActionName(Pad[i].Action));
            }
            Carried = A;
        }
    }
    Check(OneEach, "no pad button carries two fight actions");

    // every menu action has a pad button and a key (Pause is Resume there)
    bool PadMenu = true, KeyMenu = true;
    for (int a = 0; a < NumActions; ++a)
    {
        const EAction A = static_cast<EAction>(a);
        if (!IsMenu(A)) continue;
        bool HasPad = false, HasKey = false;
        for (int i = 0; i < NP; ++i) HasPad = HasPad || (Pad[i].Action == A && Pad[i].Context == EContext::Menu);
        for (int i = 0; i < NK; ++i) HasKey = HasKey || (Key[i].Action == A && Key[i].Context == EContext::Menu);
        if (!HasPad) { PadMenu = false; std::printf("  %s has no pad button in the menu\n", ActionName(A)); }
        if (!HasKey) { KeyMenu = false; std::printf("  %s has no key in the menu\n", ActionName(A)); }
    }
    Check(PadMenu, "every menu action has a pad button");
    Check(KeyMenu, "every menu action has a key");

    // Confirm and Back are never the same button or key; Confirm is south
    // and Back east, the Xbox and Western PS5 convention
    bool Apart = true, Convention = true;
    for (int i = 0; i < NP; ++i)
    {
        if (Pad[i].Context != EContext::Menu) continue;
        if (Pad[i].Action == EAction::Confirm && Pad[i].Button != EButton::FaceSouth) Convention = false;
        if (Pad[i].Action == EAction::Back && Pad[i].Button != EButton::FaceEast) Convention = false;
        for (int j = 0; j < NP; ++j)
            if (Pad[j].Context == EContext::Menu && Pad[i].Action == EAction::Confirm && Pad[j].Action == EAction::Back
                && Pad[i].Button == Pad[j].Button) Apart = false;
    }
    for (int i = 0; i < NK; ++i)
        for (int j = 0; j < NK; ++j)
            if (Key[i].Context == EContext::Menu && Key[j].Context == EContext::Menu
                && Key[i].Action == EAction::Confirm && Key[j].Action == EAction::Back
                && Same(Key[i].KeyName, Key[j].KeyName)) Apart = false;
    Check(Apart, "Confirm and Back differ, on the pad and on the keyboard");
    Check(Convention, "Confirm is the south button and Back the east");

    // the table as designed: punch west, kick south, block either shoulder,
    // dash east, rage north, pause the menu button, move and look the sticks
    auto Bound = [&](EAction A, EButton B, EContext Ctx)
    {
        for (int i = 0; i < NP; ++i)
            if (Pad[i].Action == A && Pad[i].Button == B && Pad[i].Context == Ctx) return true;
        return false;
    };
    Check(Bound(EAction::Punch, EButton::FaceWest, EContext::Fight) && Bound(EAction::Kick, EButton::FaceSouth, EContext::Fight)
              && Bound(EAction::Block, EButton::RB, EContext::Fight) && Bound(EAction::Block, EButton::LB, EContext::Fight)
              && Bound(EAction::Dash, EButton::FaceEast, EContext::Fight) && Bound(EAction::Rage, EButton::FaceNorth, EContext::Fight)
              && Bound(EAction::Pause, EButton::Menu, EContext::Fight) && Bound(EAction::Move, EButton::LeftStick, EContext::Fight)
              && Bound(EAction::Look, EButton::RightStick, EContext::Fight),
          "the fight is punch west, kick south, block either shoulder, dash east, rage north, pause menu, sticks move and look");
    Check(Bound(EAction::FlipPad, EButton::LB, EContext::Menu) && Bound(EAction::FlipPad, EButton::RB, EContext::Menu)
              && Bound(EAction::NavUp, EButton::DpadUp, EContext::Menu) && Bound(EAction::NavDown, EButton::DpadDown, EContext::Menu)
              && Bound(EAction::NavLeft, EButton::DpadLeft, EContext::Menu) && Bound(EAction::NavRight, EButton::DpadRight, EContext::Menu)
              && Bound(EAction::NavUp, EButton::LeftStick, EContext::Menu) && Bound(EAction::Pause, EButton::Menu, EContext::Menu),
          "the menu is d-pad and stick to navigate, either shoulder to flip the pad, the menu button to resume");
    Check(std::fabs(NavRepeatFirst - 0.35f) < 1e-6f && std::fabs(NavRepeatNext - 0.12f) < 1e-6f,
          "navigation repeats after 0.35 s, then every 0.12 s");

    // the pad's words, the ones asked for
    const char* XboxWords[NumButtons] = {"A", "B", "X", "Y", "LB", "RB", "LT", "RT", "L3", "R3", "MENU", "VIEW",
                                         "UP", "DOWN", "LEFT", "RIGHT", "LS", "RS"};
    const char* PSWords[NumButtons] = {"CROSS", "CIRCLE", "SQUARE", "TRIANGLE", "L1", "R1", "L2", "R2", "L3", "R3",
                                       "OPTIONS", "CREATE", "UP", "DOWN", "LEFT", "RIGHT", "LS", "RS"};
    bool Words = true, Faces = true, Others = true, KeyboardIsXbox = true;
    for (int b = 0; b < NumButtons; ++b)
    {
        const EButton B = static_cast<EButton>(b);
        if (!Same(Label(B, EPad::Xbox), XboxWords[b]) || !Same(Label(B, EPad::PlayStation), PSWords[b])) Words = false;
        const bool Differ = !Same(Label(B, EPad::Xbox), Label(B, EPad::PlayStation));
        if (b <= static_cast<int>(EButton::RB) && !Differ) Faces = false;
        if ((B == EButton::LT || B == EButton::RT || B == EButton::Menu || B == EButton::View) && !Differ) Others = false;
        if (!Same(Label(B, EPad::Keyboard), Label(B, EPad::Xbox))) KeyboardIsXbox = false;
    }
    Check(Words, "Xbox: A B X Y LB RB LT RT L3 R3 MENU VIEW; PlayStation: CROSS CIRCLE SQUARE TRIANGLE L1 R1 L2 R2 L3 R3 OPTIONS CREATE");
    Check(Faces, "the labels differ between Xbox and PlayStation on the four face buttons and both shoulders");
    Check(Others, "...and on the triggers, the menu and the view button");
    Check(KeyboardIsXbox, "a keyboard is given the Xbox words");

    // every Unreal key name is one Unreal has
    bool Real = true, Distinct = true;
    for (int b = 0; b < NumButtons; ++b)
    {
        if (!IsUEKey(UEKeyName(static_cast<EButton>(b))))
        {
            Real = false;
            std::printf("  %s is not an Unreal key\n", UEKeyName(static_cast<EButton>(b)));
        }
        for (int c = b + 1; c < NumButtons; ++c)
            if (Same(UEKeyName(static_cast<EButton>(b)), UEKeyName(static_cast<EButton>(c)))) Distinct = false;
    }
    for (int i = 0; i < NK; ++i)
        if (!IsUEKey(Key[i].KeyName)) { Real = false; std::printf("  %s is not an Unreal key\n", Key[i].KeyName); }
    Check(Real, "every UE key name is a real UE key name");
    Check(Distinct, "every pad button has its own UE key name");
    Check(Same(UEKeyName(EButton::Menu), "Gamepad_Special_Right") && Same(UEKeyName(EButton::FaceSouth), "Gamepad_FaceButton_Bottom")
              && Same(UEKeyName(EButton::LeftStick), "Gamepad_Left2D") && Same(UEKeyName(EButton::L3), "Gamepad_LeftThumbstick"),
          "the menu button is Gamepad_Special_Right, south the bottom face button, a stick its 2D axis, its click the thumbstick");

    // the family from the device's name
    const bool Sony = PadFromDeviceName("DualSense Wireless Controller") == EPad::PlayStation
                   && PadFromDeviceName("DualShock 4") == EPad::PlayStation
                   && PadFromDeviceName("PS5 Controller") == EPad::PlayStation
                   && PadFromDeviceName("Sony Interactive Entertainment Wireless Controller") == EPad::PlayStation
                   && PadFromDeviceName("dualsense") == EPad::PlayStation
                   && PadFromDeviceName("PlayStation") == EPad::PlayStation;
    const bool Rest = PadFromDeviceName("Xbox One Controller") == EPad::Xbox
                   && PadFromDeviceName("XInput Controller") == EPad::Xbox
                   && PadFromDeviceName("Generic Gamepad") == EPad::Xbox
                   && PadFromDeviceName("") == EPad::Xbox && PadFromDeviceName(nullptr) == EPad::Xbox;
    Check(Sony, "DualSense, DualShock, PS5, Sony and PlayStation read as PlayStation");
    Check(Rest, "an Xbox pad, a generic one and no name read as Xbox");

    // the words
    const char* FightWords[NumFightActions] = {"MOVE", "CAMERA", "PUNCH", "KICK", "BLOCK / PARRY", "DASH", "RAGE", "PAUSE"};
    bool Actions = true, Keys = true;
    for (int a = 0; a < NumActions; ++a)
    {
        const EAction A = static_cast<EAction>(a);
        if (a < NumFightActions && !Same(ActionName(A), FightWords[a])) Actions = false;
        if (!ActionName(A)[0] || Same(ActionName(A), "?") || !KeyPrompt(A)[0] || Same(KeyPrompt(A), "?")) Keys = false;
    }
    Check(Actions, "the fight actions read MOVE, CAMERA, PUNCH, KICK, BLOCK / PARRY, DASH, RAGE, PAUSE");
    Check(Keys, "every action has a name and a keyboard word");
    Check(Same(ActionName(EAction::Confirm), "SELECT") && Same(ActionName(EAction::Back), "BACK")
              && Same(KeyPrompt(EAction::Confirm), "ENTER") && Same(KeyPrompt(EAction::Back), "ESC"),
          "the prompt strip's words: SELECT and BACK, ENTER and ESC");
    // a text as slot and value resolves to its word
    Check(Same(ControlsText(EControlsText::ButtonLabel, EncodeButtonLabel(EButton::FaceSouth, EPad::PlayStation)), "CROSS")
              && Same(ControlsText(EControlsText::ButtonLabel, EncodeButtonLabel(EButton::FaceNorth, EPad::Xbox)), "Y")
              && Same(ControlsText(EControlsText::ActionName, static_cast<int>(EAction::Punch)), "PUNCH")
              && Same(ControlsText(EControlsText::KeyName, static_cast<int>(EAction::Kick)), "K")
              && Same(ControlsText(EControlsText::Unbound, 0), "--")
              && Same(ControlsText(EControlsText::PadName, static_cast<int>(EPad::PlayStation)), "PLAYSTATION"),
          "a text's slot and value resolve to its word");
}

// ---------------------------------------------------------- GLYPHS
static bool IsFace(EButton B) { return static_cast<int>(B) <= static_cast<int>(EButton::FaceNorth); }
static bool HasWord(EButton B, EPad Pad)
{
    if (IsFace(B)) return Pad != EPad::PlayStation;
    return B == EButton::LB || B == EButton::RB || B == EButton::LT || B == EButton::RT || B == EButton::L3 || B == EButton::R3;
}

static void Glyphs()
{
    std::printf("GLYPHS  (a disc and its letter, or its shape)\n");
    bool NoNaN = true, Wound = true, Fits = true, Worded = true, Shaped = true, Palette = true, SameAsXbox = true;
    int MaxTris = 0, XboxTris[NumButtons] = {0};
    const float Size = 50.f;
    const FPoint C = {400.f, 300.f};
    for (int p = 0; p < 3; ++p)
    {
        const EPad Pad = static_cast<EPad>(p);
        for (int b = 0; b < NumButtons; ++b)
        {
            const EButton B = static_cast<EButton>(b);
            List.Reset();
            Glyph(B, Pad, C.X, C.Y, Size, SaudHud::Colour::Ink, SaudHud::Colour::Bone, List);
            if (List.NumTris < 6) Shaped = false;
            if (List.NumTris > MaxTris) MaxTris = List.NumTris;
            for (int t = 0; t < List.NumTris; ++t)
            {
                const FRecTri& T = List.Tris[t];
                for (int v = 0; v < 3; ++v)
                {
                    if (!(T.P[v].X == T.P[v].X) || !(T.P[v].Y == T.P[v].Y)) NoNaN = false;
                    // inside the glyph's own box: a tab is wider than it is tall
                    if (std::fabs(T.P[v].X - C.X) > 1.3f * Size || std::fabs(T.P[v].Y - C.Y) > 0.65f * Size) Fits = false;
                    if (!IsPalette(T.C[v])) Palette = false;
                }
                if (!(Cross(T.P[0], T.P[1], T.P[2]) > 1e-3f)) Wound = false;
            }
            // the word: an Xbox face button, a shoulder, a trigger or a click
            // has its label, once, centred on the glyph, tall enough to read;
            // a PlayStation face button has none -- the shape is geometry
            int WordsSeen = 0;
            for (int t = 0; t < List.NumTexts; ++t)
            {
                const FRecText& X = List.Texts[t];
                if (X.Slot != EControlsText::ButtonLabel) { Worded = false; continue; }
                ++WordsSeen;
                const EPad Family = Pad == EPad::Keyboard ? EPad::Xbox : Pad;
                if (!Same(ControlsText(X.Slot, X.Value), Label(B, Family))) Worded = false;
                if (!X.bCentre || std::fabs(X.At.X - C.X) > 0.5f || X.Height < 0.6f * Size) Worded = false;
                if (std::fabs(X.At.Y + 0.5f * X.Height - C.Y) > 0.5f) Worded = false;
                if (X.Stroke < 0.08f * Size || Contrast(X.Colour, SaudHud::Colour::Ink) < 7.f) Worded = false;
            }
            if (WordsSeen != (HasWord(B, Pad) ? 1 : 0)) Worded = false;
            if (!HasWord(B, Pad) && CountPart(EControlsPart::Label) == 0) Shaped = false;
            if (IsFace(B) && Pad == EPad::PlayStation)
            {
                // the shape stands out of the disc: at least a bar's worth of it
                FBox S;
                for (int t = 0; t < List.NumTris; ++t)
                {
                    if (List.Tris[t].Part != EControlsPart::Label) continue;
                    for (int v = 0; v < 3; ++v)
                    {
                        S.X0 = std::fmin(S.X0, List.Tris[t].P[v].X); S.X1 = std::fmax(S.X1, List.Tris[t].P[v].X);
                        S.Y0 = std::fmin(S.Y0, List.Tris[t].P[v].Y); S.Y1 = std::fmax(S.Y1, List.Tris[t].P[v].Y);
                        S.Any = true;
                    }
                }
                if (!S.Any || S.X1 - S.X0 < 0.4f * Size || S.Y1 - S.Y0 < 0.4f * Size) Shaped = false;
                if (S.Any && (S.X1 - S.X0 > 0.9f * Size || S.Y1 - S.Y0 > 0.9f * Size)) Shaped = false;
            }
            if (Pad == EPad::Xbox) XboxTris[b] = List.NumTris;
            if (Pad == EPad::Keyboard && List.NumTris != XboxTris[b]) SameAsXbox = false;
        }
    }
    std::printf("  at most %d triangles a glyph\n", MaxTris);
    Check(NoNaN, "every glyph is numbers");
    Check(Wound, "no glyph is degenerate: every triangle has area, wound the same way");
    Check(Fits, "every glyph stays in its own box");
    Check(Worded, "an Xbox face button, a shoulder, a trigger and a click carry their word once, centred and legible; a PlayStation face button none");
    Check(Shaped, "a PlayStation face button's shape, the menu bars, the view's rectangles, a stick's dot and the d-pad's arm are drawn as geometry, inside the disc");
    Check(Palette, "a glyph is drawn in the HUD's palette");
    Check(SameAsXbox, "a keyboard draws the Xbox glyph");

    // the PlayStation circle's rim is the one accent, in Blood; every other
    // disc's rim is Ash
    bool Accent = true;
    for (int b = 0; b < NumButtons; ++b)
    {
        const EButton B = static_cast<EButton>(b);
        if (B == EButton::LeftStick || B == EButton::RightStick) continue;
        for (int p = 0; p < 2; ++p)
        {
            List.Reset();
            Glyph(B, static_cast<EPad>(p), C.X, C.Y, Size, SaudHud::Colour::Ink, SaudHud::Colour::Bone, List);
            const bool WantBlood = p == 1 && B == EButton::FaceEast;
            for (int t = 0; t < List.NumTris; ++t)
                if (List.Tris[t].Part == EControlsPart::Rim
                    && !SameRgb(List.Tris[t].C[0], WantBlood ? SaudHud::Colour::Blood : SaudHud::Colour::Ash)) Accent = false;
        }
    }
    Check(Accent, "the PlayStation circle's rim is Blood, the one accent; every other rim is Ash");
}

// ------------------------------------------------------------ PAGE
static void Page()
{
    std::printf("PAGE  (what BuildControlsPage draws)\n");
    bool NoNaN = true, AllIn = true, TextIn = true, Apart = true, Wound = true, Banded = true, Legible = true;
    bool Stroked = true, Palette = true, Labelled = true, Led = true, Listed = true, Captioned = true, Worded = true;
    bool Shown = true, Fits = true;
    int Worst = 0, WorstTexts = 0, Tris1080[2] = {0, 0}, Texts1080[2] = {0, 0};
    bool Beside169 = false, Under43 = true;
    int NP = 0;
    const FBinding* Pad = PadBindings(NP);
    for (const auto& Sh : Shapes)
    {
        const FPage P = FPage::For(Sh[0], Sh[1]);
        const FControlsLayout L = LayControls(P);
        if (Sh[0] == 1920.f) Beside169 = L.bListBeside;
        if (Sh[0] == 1600.f) Under43 = !L.bListBeside;
        for (int p = 0; p < 2; ++p)
        {
            const EPad Family = static_cast<EPad>(p);
            List.Reset();
            BuildControlsPage(P, Family, List);
            if (List.bOverflow) Fits = false;
            if (List.NumTris > Worst) Worst = List.NumTris;
            if (List.NumTexts > WorstTexts) WorstTexts = List.NumTexts;
            if (Sh[0] == 1920.f) { Tris1080[p] = List.NumTris; Texts1080[p] = List.NumTexts; }
            const float BandTop = P.Top() + P.Px(100.f), BandBottom = P.Bottom() - P.Px(90.f);   // written here
            for (int t = 0; t < List.NumTris; ++t)
            {
                const FRecTri& T = List.Tris[t];
                for (int v = 0; v < 3; ++v)
                {
                    if (!(T.P[v].X == T.P[v].X) || !(T.P[v].Y == T.P[v].Y)) NoNaN = false;
                    if (!InSafe(P, T.P[v].X, T.P[v].Y)) AllIn = false;
                    if (T.P[v].Y < BandTop - 0.5f || T.P[v].Y > BandBottom + 0.5f) Banded = false;
                    if (!IsPalette(T.C[v])) Palette = false;
                }
                if (!(Cross(T.P[0], T.P[1], T.P[2]) > 1e-3f)) Wound = false;
            }
            for (int t = 0; t < List.NumTexts; ++t)
            {
                const FRecText& X = List.Texts[t];
                const FBox B = TextBox(X);
                if (!InSafe(P, B.X0, B.Y0) || !InSafe(P, B.X1, B.Y1)) TextIn = false;
                if (B.Y0 < BandTop - 0.5f || B.Y1 > BandBottom + 0.5f) Banded = false;
                if (X.Height < P.ScreenH / 36.f - 0.01f) Legible = false;
                if (X.Stroke < 2.f * P.ScreenH / 720.f - 0.01f || Contrast(X.Colour, SaudHud::Colour::Ink) < 7.f) Stroked = false;
                for (int u = t + 1; u < List.NumTexts; ++u)
                    if (Overlap(B, TextBox(List.Texts[u]))) Apart = false;
            }

            // every labelled button's label is the fight action the table
            // binds to it, or "--"; every bound button is labelled
            for (int b = 0; b < NumButtons; ++b)
            {
                const EButton Bt = static_cast<EButton>(b);
                const FSlot& S = L.Slot[b];
                int Want = -1;
                for (int i = 0; i < NP; ++i)
                    if (Pad[i].Context == EContext::Fight && Pad[i].Button == Bt && Want < 0) Want = static_cast<int>(Pad[i].Action);
                if (Want >= 0 && !S.bLabel) { Shown = false; std::printf("  %s is bound but not in the diagram\n", Label(Bt, EPad::Xbox)); }
                if (!S.bLabel) continue;
                const FRecText* X = TextAt(S.LabelAt);
                if (!X) { Labelled = false; continue; }
                const bool Right = Want >= 0 ? (X->Slot == EControlsText::ActionName && X->Value == Want)
                                             : X->Slot == EControlsText::Unbound;
                if (!Right)
                {
                    Labelled = false;
                    std::printf("  %s reads %s, the table says %s\n", Label(Bt, EPad::Xbox), ControlsText(X->Slot, X->Value),
                                Want >= 0 ? ActionName(static_cast<EAction>(Want)) : "--");
                }
                // a leader from the button to its label, in Line triangles
                bool From = false, To = false;
                const float Tol = 3.f * P.Scale;
                for (int t = 0; t < List.NumTris; ++t)
                {
                    if (List.Tris[t].Part != EControlsPart::Line) continue;
                    for (int v = 0; v < 3; ++v)
                    {
                        From = From || Dist(List.Tris[t].P[v], S.LeadFrom) <= Tol;
                        To = To || Dist(List.Tris[t].P[v], S.LeadTo) <= Tol;
                    }
                }
                // ...leaving within reach of the button, stopping just short of the label's box
                const FBox LB = TextBox(*X);
                const float Gx = std::fmax(0.f, std::fmax(LB.X0 - S.LeadTo.X, S.LeadTo.X - LB.X1));
                const float Gy = std::fmax(0.f, std::fmax(LB.Y0 - S.LeadTo.Y, S.LeadTo.Y - LB.Y1));
                if (!From || !To || Dist(S.LeadFrom, S.Centre) > P.Px(60.f) || std::sqrt(Gx * Gx + Gy * Gy) > P.Px(12.f)) Led = false;
            }
            // the glyphs' own words: on Xbox the face letters, on both the
            // shoulders' and triggers' names, each by its button
            for (int b = 0; b < NumButtons; ++b)
            {
                const EButton Bt = static_cast<EButton>(b);
                const FSlot& S = L.Slot[b];
                if (S.Size <= 0.f) continue;
                int Seen = 0;
                for (int t = 0; t < List.NumTexts; ++t)
                {
                    const FRecText& X = List.Texts[t];
                    if (X.Slot != EControlsText::ButtonLabel || X.Value != EncodeButtonLabel(Bt, Family)) continue;
                    ++Seen;
                    if (Dist(X.At, S.Centre) > S.Size) Worded = false;
                }
                if (Seen != (HasWord(Bt, Family) ? 1 : 0)) Worded = false;
            }
            // the caption and the keyboard's list
            const FRecText* Cap = TextAt(L.CaptionAt);
            if (!Cap || Cap->Slot != EControlsText::PadName || Cap->Value != p || !Cap->bCentre) Captioned = false;
            for (int a = 0; a < NumFightActions; ++a)
            {
                const FRecText* N = TextAt(L.ListName[a]);
                const FRecText* K = TextAt(L.ListKey[a]);
                if (!N || N->Slot != EControlsText::ActionName || N->Value != a) Listed = false;
                if (!K || K->Slot != EControlsText::KeyName || K->Value != a) Listed = false;
                if (N && K && K->At.X < N->At.X + 0.62f * N->Height * static_cast<float>(std::strlen(ActionName(static_cast<EAction>(a))))) Listed = false;
            }
        }
        std::printf("  %4.0f x %4.0f: the keyboard's list %s the pad\n", Sh[0], Sh[1], L.bListBeside ? "beside" : "under");
    }
    std::printf("  at 1080p: xbox %d triangles, %d texts; playstation %d triangles, %d texts\n",
                Tris1080[0], Texts1080[0], Tris1080[1], Texts1080[1]);
    std::printf("  worst over the seven shapes: %d triangles, %d texts\n", Worst, WorstTexts);
    Check(NoNaN, "the diagram's shapes are numbers");
    Check(AllIn, "every vertex the diagram draws is inside the title-safe area, at every screen shape");
    Check(TextIn, "every label is inside the title-safe area, at every screen shape");
    Check(Banded, "the diagram keeps the head band (the title) and the foot band (the prompt strip) clear");
    Check(Apart, "no label overlaps another");
    Check(Wound, "no shape is degenerate: every triangle has area, wound the same way");
    Check(Legible, "no word the player reads is under 1/36 of the screen");
    Check(Stroked, "every word has an ink stroke of 2 screen px at 720 lines, 7:1 against its fill");
    Check(Palette, "the diagram is drawn in the HUD's palette");
    Check(Shown, "every button the fight binds is in the diagram, with a label");
    Check(Labelled, "every bound button's label is the action the table binds; the rest read --");
    Check(Led, "a leader runs from every labelled button's edge to its label");
    Check(Worded, "the glyphs carry their words: the letters on Xbox, the shoulders and triggers on both");
    Check(Captioned, "the family's name is under the pad");
    Check(Listed, "the keyboard's list has every fight action with its key beside it");
    Check(Beside169 && Under43, "the list stands beside the pad on 16:9 and under it on 4:3");
    Check(Fits && Worst <= 1200 && WorstTexts <= 48, "the worst case fits a list of 1200 triangles and 48 texts");
}

int main()
{
    Mapping();
    Glyphs();
    Page();
    if (Fails) { std::printf("%d controls check(s) failed\n", Fails); return 1; }
    std::printf("all controls checks passed\n");
    return 0;
}
