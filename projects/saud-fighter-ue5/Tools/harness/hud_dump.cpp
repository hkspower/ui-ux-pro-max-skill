/**
 * The HUD's draw list as JSON, for Tools/look/hud_preview.py: SaudHud::Build
 * (Combat/SaudAnime.h) on a made-up FHudState at a given screen size, with
 * no engine. Not a test -- run.sh does not build it; hud_preview.py does.
 *
 *   hud_dump W H [key=value ...]
 *
 * keys: health ghost stamina rage ready combo since boss boss_health
 * boss_ghost enraged boss_since clock player, and street=X:Y:Fill:Ghost
 * (repeatable, screen px). Prints {"tris": [[x0,y0,r,g,b,a, x1,...,
 * group, part], ...], "texts": [...], "overflow": bool}. Colours are
 * linear, as the header holds them.
 */
#include "HarnessTypes.h"
#include "../../Source/SaudFighter/Combat/SaudAnime.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>

using namespace SaudHud;

static FDrawList List;

int main(int argc, char** argv)
{
    if (argc < 3)
    {
        std::fprintf(stderr, "usage: hud_dump W H [key=value ...]\n");
        return 2;
    }
    const float W = static_cast<float>(std::atof(argv[1])), H = static_cast<float>(std::atof(argv[2]));
    FHudState S;
    for (int i = 3; i < argc; ++i)
    {
        const char* Eq = std::strchr(argv[i], '=');
        if (!Eq)
        {
            std::fprintf(stderr, "not key=value: %s\n", argv[i]);
            return 2;
        }
        const std::size_t N = static_cast<std::size_t>(Eq - argv[i]);
        const char* V = Eq + 1;
        const float F = static_cast<float>(std::atof(V));
        auto Is = [&](const char* K) { return std::strlen(K) == N && std::strncmp(argv[i], K, N) == 0; };
        if (Is("health")) S.Health = F;
        else if (Is("ghost")) S.Ghost = F;
        else if (Is("stamina")) S.Stamina = F;
        else if (Is("rage")) S.Rage = F;
        else if (Is("ready")) S.bRageReady = F > 0.5f;
        else if (Is("combo")) S.Combo = std::atoi(V);
        else if (Is("since")) S.SinceCombo = F;
        else if (Is("boss")) S.bBoss = F > 0.5f;
        else if (Is("boss_health")) S.BossHealth = F;
        else if (Is("boss_ghost")) S.BossGhost = F;
        else if (Is("enraged")) S.bBossEnraged = F > 0.5f;
        else if (Is("boss_since")) S.BossSince = F;
        else if (Is("clock")) S.Clock = F;
        else if (Is("player")) S.bPlayer = F > 0.5f;
        else if (Is("street") && S.NumStreet < MaxStreetBars)
        {
            FStreetBar& B = S.Street[S.NumStreet++];
            if (std::sscanf(V, "%f:%f:%f:%f", &B.X, &B.Y, &B.Fill, &B.Ghost) != 4)
            {
                std::fprintf(stderr, "street=X:Y:Fill:Ghost\n");
                return 2;
            }
        }
        else
        {
            std::fprintf(stderr, "unknown key: %s\n", argv[i]);
            return 2;
        }
    }
    const FPage P = FPage::For(W, H);
    Build(P, S, List);
    std::printf("{\"scale\": %g, \"overflow\": %s,\n\"tris\": [", P.Scale, List.bOverflow ? "true" : "false");
    for (int t = 0; t < List.NumTris; ++t)
    {
        const FHudTri& T = List.Tris[t];
        std::printf("%s\n[", t ? "," : "");
        for (int v = 0; v < 3; ++v)
        {
            const FHudVert& X = T.V[v];
            std::printf("%.3f, %.3f, %.5f, %.5f, %.5f, %.4f, ", X.P.X, X.P.Y, X.C.R, X.C.G, X.C.B, X.C.A);
        }
        std::printf("%d, %d]", static_cast<int>(T.Group), static_cast<int>(T.Part));
    }
    std::printf("],\n\"texts\": [");
    for (int t = 0; t < List.NumTexts; ++t)
    {
        const FHudText& X = List.Texts[t];
        std::printf("%s\n{\"slot\": %d, \"value\": %d, \"x\": %.3f, \"y\": %.3f, \"h\": %.3f, "
                    "\"rgba\": [%.5f, %.5f, %.5f, %.4f], \"stroke\": %.3f, \"centre\": %s, \"group\": %d, \"after\": %d}",
                    t ? "," : "", static_cast<int>(X.Slot), X.Value, X.At.X, X.At.Y, X.Height, X.Colour.R,
                    X.Colour.G, X.Colour.B, X.Colour.A, X.Stroke, X.bCentre ? "true" : "false",
                    static_cast<int>(X.Group), X.TrisBefore);
    }
    std::printf("]}\n");
    return 0;
}
