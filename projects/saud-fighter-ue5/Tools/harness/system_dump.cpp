/**
 * The System's draw list as JSON, for Tools/look/system_preview.py:
 * SaudSystem::Build (Combat/SaudSystem.h) on a model the arguments make,
 * at a given screen size and a given number of real seconds in, with no
 * engine. Not a test -- run.sh does not build it; system_preview.py does.
 *
 *   system_dump W H SECONDS [quest=0|1] [questline=Title|Head|Status]
 *               [event=Kind|Key|Title|Head|Body|Reward|Beneath|Status|level|hp|mp|xp|rank|skill|quest] ...
 *
 * Each event is pushed at 0 s, in the order given (Kind is SaudSystem::
 * KindName's); the model is ticked at 60 Hz for SECONDS. quest=1 opens the
 * open quest (shown in full from the start); questline is its words.
 * Prints {"tris": [[x0,y0,r,g,b,a, x1,..., group, part], ...], "texts":
 * [{"s", "x", "y", "h", "rgba", "stroke", "align", "piece", "after"}],
 * "pieces": [{"on", "x", "y", "w", "h"}], "overflow"}. Colours linear.
 */
#include "HarnessTypes.h"
#include "../../Source/SaudFighter/Combat/SaudSystem.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

using namespace SaudSystem;

static FModel Model;
static FSysList List;

static std::vector<std::string> Split(const char* S, char By)
{
    std::vector<std::string> Out(1);
    for (; *S; ++S)
    {
        if (*S == By) Out.emplace_back();
        else Out.back() += *S;
    }
    return Out;
}

static void JsonString(const char* S)
{
    std::putchar('"');
    for (; S && *S; ++S)
    {
        if (*S == '"' || *S == '\\') std::putchar('\\');
        std::putchar(*S);
    }
    std::putchar('"');
}

int main(int argc, char** argv)
{
    if (argc < 4)
    {
        std::fprintf(stderr, "usage: system_dump W H SECONDS [quest=0|1] [questline=...] [event=...] ...\n");
        return 2;
    }
    const float W = static_cast<float>(std::atof(argv[1])), H = static_cast<float>(std::atof(argv[2]));
    const float Seconds = static_cast<float>(std::atof(argv[3]));
    for (int i = 4; i < argc; ++i)
    {
        const char* A = argv[i];
        if (!std::strncmp(A, "quest=", 6))
        {
            Model.SetQuestOpen(std::atoi(A + 6) != 0);
            Model.QuestShow = Model.bQuestOpen ? 1.f : 0.f;
        }
        else if (!std::strncmp(A, "questline=", 10))
        {
            const auto F = Split(A + 10, '|');
            if (F.size() != 3) { std::fprintf(stderr, "questline=Title|Head|Status\n"); return 2; }
            Put(Model.Quest.Title, TitleMax, F[0].c_str());
            Put(Model.Quest.Head, HeadMax, F[1].c_str());
            Put(Model.Quest.Status, StatusMax, F[2].c_str());
        }
        else if (!std::strncmp(A, "event=", 6))
        {
            const auto F = Split(A + 6, '|');
            if (F.size() != 15) { std::fprintf(stderr, "event= takes 15 fields, got %zu: %s\n", F.size(), A); return 2; }
            EKind K = EKind::Count;
            for (int k = 0; k < NumKinds; ++k) if (F[0] == KindName(static_cast<EKind>(k))) K = static_cast<EKind>(k);
            if (K == EKind::Count) { std::fprintf(stderr, "no such event: %s\n", F[0].c_str()); return 2; }
            FLines T;
            Put(T.Title, TitleMax, F[2].c_str());
            Put(T.Head, HeadMax, F[3].c_str());
            Put(T.Body, BodyMax, F[4].c_str());
            Put(T.Reward, RewardMax, F[5].c_str());
            Put(T.Beneath, BeneathMax, F[6].c_str());
            Put(T.Status, StatusMax, F[7].c_str());
            FArgs Ar;
            Ar.Level = std::atoi(F[8].c_str());
            Ar.Hp = std::atoi(F[9].c_str());
            Ar.Mp = std::atoi(F[10].c_str());
            Ar.Xp = std::atoi(F[11].c_str());
            Put(Ar.Rank, 24, F[12].c_str());
            Put(Ar.Skill, 24, F[13].c_str());
            Put(Ar.Quest, HeadMax, F[14].c_str());
            Model.Push(MakeEvent(K, F[1].c_str(), T, Ar));
        }
        else
        {
            std::fprintf(stderr, "unknown argument: %s\n", A);
            return 2;
        }
    }
    const int Frames = static_cast<int>(Seconds * 60.f + 0.5f);
    Model.Tick({0.f, 0.f});
    for (int f = 0; f < Frames; ++f) Model.Tick({1.f / 60.f, 1.f / 60.f});

    const FPage P = FPage::For(W, H);
    Build(P, Model, List);
    std::printf("{\"scale\": %g, \"overflow\": %s,\n\"tris\": [", P.Scale, List.bOverflow ? "true" : "false");
    for (int t = 0; t < List.Shapes.NumTris; ++t)
    {
        const SaudHud::FHudTri& T = List.Shapes.Tris[t];
        std::printf("%s\n[", t ? "," : "");
        for (int v = 0; v < 3; ++v)
        {
            const SaudHud::FHudVert& X = T.V[v];
            std::printf("%.3f, %.3f, %.5f, %.5f, %.5f, %.4f, ", X.P.X, X.P.Y, X.C.R, X.C.G, X.C.B, X.C.A);
        }
        std::printf("%d, %d]", static_cast<int>(T.Group), static_cast<int>(T.Part));
    }
    std::printf("],\n\"texts\": [");
    for (int t = 0; t < List.NumTexts; ++t)
    {
        const FSysText& X = List.Texts[t];
        std::printf("%s\n{\"s\": ", t ? "," : "");
        JsonString(X.S);
        std::printf(", \"slot\": %d, \"x\": %.3f, \"y\": %.3f, \"h\": %.3f, \"rgba\": [%.5f, %.5f, %.5f, %.4f], \"stroke\": %.3f, "
                    "\"align\": %d, \"piece\": %d, \"after\": %d}",
                    static_cast<int>(X.Slot), X.At.X, X.At.Y, X.Height, X.Colour.R, X.Colour.G, X.Colour.B, X.Colour.A, X.Stroke,
                    static_cast<int>(X.Align), static_cast<int>(X.Piece), X.TrisBefore);
    }
    std::printf("],\n\"pieces\": [");
    for (int i = 0; i < NumPieces; ++i)
    {
        const FRect& R = List.Box[i];
        std::printf("%s{\"on\": %s, \"x\": %.3f, \"y\": %.3f, \"w\": %.3f, \"h\": %.3f}", i ? ", " : "", List.bOn[i] ? "true" : "false",
                    R.X, R.Y, R.W, R.H);
    }
    std::printf("]}\n");
    return 0;
}
