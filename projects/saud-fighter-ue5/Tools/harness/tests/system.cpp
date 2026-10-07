/**
 * The System's windows, executed (Combat/SaudSystem.h, 2026-10-07): the
 * queue's order and its limits, the timings in real time at 30 and 60 Hz
 * through a blow's freeze, the layout at the seven screen shapes the HUD is
 * held to -- what Build DRAWS, as tests/anime.cpp holds the HUD -- and the
 * words: every event has its line in Content/Data/DT_SystemLines.json,
 * every stage in DT_Stages.json its "stage entered" quest carrying the
 * stage data's own Arabic, the spec's fixed lines word for word, none of
 * Solo Leveling's terms anywhere, and the open quest shown from the first
 * landing to the victory and removed after it.
 *
 * Every check here has a sabotage in Tools/harness/bites_system.txt.
 */
#include "../HarnessTypes.h"
#include "../../../Source/SaudFighter/Combat/SaudSystem.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include <map>
#include <string>
#include <utility>
#include <vector>

static int Fails = 0;
static void Check(bool Ok, const char* What)
{
    if (!Ok) { ++Fails; std::printf("  FAIL  %s\n", What); }
}

using namespace SaudSystem;
using SaudHud::FHudTri;
using SaudHud::FHudVert;

// ------------------------------------------------------------- a little JSON
struct FJson
{
    enum EType { Null, Bool, Num, String, Arr, Obj } Type = Null;
    std::string S;
    double N = 0.0;
    std::vector<FJson> A;
    std::vector<std::pair<std::string, FJson>> O;
    const FJson* Get(const char* K) const
    {
        for (const auto& KV : O) if (KV.first == K) return &KV.second;
        return nullptr;
    }
    std::string Str(const char* K) const { const FJson* V = Get(K); return V && V->Type == FJson::String ? V->S : std::string(); }
};

struct FParser
{
    const char* P;
    bool Ok = true;
    void Ws() { while (*P == ' ' || *P == '\n' || *P == '\r' || *P == '\t') ++P; }
    static void Utf8(std::string& Out, unsigned C)
    {
        if (C < 0x80) Out += static_cast<char>(C);
        else if (C < 0x800) { Out += static_cast<char>(0xC0 | (C >> 6)); Out += static_cast<char>(0x80 | (C & 0x3F)); }
        else { Out += static_cast<char>(0xE0 | (C >> 12)); Out += static_cast<char>(0x80 | ((C >> 6) & 0x3F)); Out += static_cast<char>(0x80 | (C & 0x3F)); }
    }
    std::string String()
    {
        std::string Out;
        if (*P != '"') { Ok = false; return Out; }
        ++P;
        while (*P && *P != '"')
        {
            if (*P == '\\')
            {
                ++P;
                const char E = *P++;
                if (E == 'n') Out += '\n';
                else if (E == 't') Out += '\t';
                else if (E == 'u')
                {
                    unsigned C = 0;
                    for (int i = 0; i < 4 && *P; ++i, ++P)
                        C = C * 16 + static_cast<unsigned>(std::isdigit(static_cast<unsigned char>(*P)) ? *P - '0' : (std::tolower(*P) - 'a' + 10));
                    Utf8(Out, C);
                }
                else Out += E;
            }
            else Out += *P++;
        }
        if (*P != '"') Ok = false; else ++P;
        return Out;
    }
    FJson Value()
    {
        FJson V;
        Ws();
        if (*P == '{')
        {
            V.Type = FJson::Obj; ++P; Ws();
            if (*P == '}') { ++P; return V; }
            while (Ok)
            {
                Ws();
                std::string K = String();
                Ws();
                if (*P != ':') { Ok = false; break; }
                ++P;
                V.O.emplace_back(K, Value());
                Ws();
                if (*P == ',') { ++P; continue; }
                if (*P == '}') { ++P; break; }
                Ok = false;
            }
        }
        else if (*P == '[')
        {
            V.Type = FJson::Arr; ++P; Ws();
            if (*P == ']') { ++P; return V; }
            while (Ok)
            {
                V.A.push_back(Value());
                Ws();
                if (*P == ',') { ++P; continue; }
                if (*P == ']') { ++P; break; }
                Ok = false;
            }
        }
        else if (*P == '"') { V.Type = FJson::String; V.S = String(); }
        else if (!std::strncmp(P, "true", 4)) { V.Type = FJson::Bool; V.N = 1; P += 4; }
        else if (!std::strncmp(P, "false", 5)) { V.Type = FJson::Bool; P += 5; }
        else if (!std::strncmp(P, "null", 4)) { P += 4; }
        else
        {
            char* End = nullptr;
            V.Type = FJson::Num;
            V.N = std::strtod(P, &End);
            if (End == P) Ok = false;
            P = End;
        }
        return V;
    }
};

static bool ReadFile(const char* Path, std::string& Out)
{
    FILE* F = std::fopen(Path, "rb");
    if (!F) return false;
    char B[4096];
    size_t N;
    while ((N = std::fread(B, 1, sizeof B, F)) > 0) Out.append(B, N);
    std::fclose(F);
    return true;
}
static bool ReadJson(const char* Path, FJson& Out)
{
    std::string Text;
    if (!ReadFile(Path, Text)) return false;
    FParser Ps{Text.c_str()};
    Out = Ps.Value();
    return Ps.Ok;
}
static std::vector<std::vector<std::string>> Csv(const char* Path)
{
    std::vector<std::vector<std::string>> Rows;
    std::string Text;
    if (!ReadFile(Path, Text)) return Rows;
    std::vector<std::string> Row;
    std::string Cell;
    bool Q = false;
    for (size_t i = 0; i < Text.size(); ++i)
    {
        const char C = Text[i];
        if (Q) { if (C == '"' && i + 1 < Text.size() && Text[i + 1] == '"') { Cell += '"'; ++i; } else if (C == '"') Q = false; else Cell += C; }
        else if (C == '"') Q = true;
        else if (C == ',') { Row.push_back(Cell); Cell.clear(); }
        else if (C == '\n') { Row.push_back(Cell); Cell.clear(); Rows.push_back(Row); Row.clear(); }
        else if (C != '\r') Cell += C;
    }
    if (!Cell.empty() || !Row.empty()) { Row.push_back(Cell); Rows.push_back(Row); }
    return Rows;
}

// ------------------------------------------------------------- the lines
static const char* const Fields[] = {"Title", "Head", "Body", "Reward", "Beneath", "Status"};
static FJson Lines;
static const FJson* Row(const std::string& Name)
{
    for (const FJson& R : Lines.A) if (R.Str("Name") == Name) return &R;
    return nullptr;
}
static FLines TplOf(const FJson* R)
{
    FLines L;
    if (!R) return L;
    Put(L.Title, TitleMax, R->Str("Title").c_str());
    Put(L.Head, HeadMax, R->Str("Head").c_str());
    Put(L.Body, BodyMax, R->Str("Body").c_str());
    Put(L.Reward, RewardMax, R->Str("Reward").c_str());
    Put(L.Beneath, BeneathMax, R->Str("Beneath").c_str());
    Put(L.Status, StatusMax, R->Str("Status").c_str());
    return L;
}
/** The event as USaudSystemSubsystem makes it: its row is Event_Key, or
    Event alone. */
static FSysEvent Ev(EKind K, const char* Key = "", FArgs A = FArgs())
{
    const std::string Ek = std::string(KindName(K)) + (Key && *Key ? std::string("_") + Key : std::string());
    const FJson* R = Row(Ek);
    if (!R) R = Row(KindName(K));
    return MakeEvent(K, Key, TplOf(R), A);
}
static FArgs Args(int Level = 0, int Hp = 0, int Mp = 0, int Xp = 0, const char* Rank = "", const char* Skill = "", const char* Quest = "")
{
    FArgs A;
    A.Level = Level; A.Hp = Hp; A.Mp = Mp; A.Xp = Xp;
    Put(A.Rank, 24, Rank); Put(A.Skill, 24, Skill); Put(A.Quest, HeadMax, Quest);
    return A;
}
static bool Says(const FLines& L, const char* T, const char* H, const char* B, const char* R, const char* Be = "", const char* St = "")
{
    return Same(L.Title, T) && Same(L.Head, H) && Same(L.Body, B) && Same(L.Reward, R) && Same(L.Beneath, Be) && Same(L.Status, St);
}

static std::string Lower(std::string S)
{
    for (char& C : S) C = static_cast<char>(std::tolower(static_cast<unsigned char>(C)));
    return S;
}
static bool IsWordChar(char C) { return std::isalnum(static_cast<unsigned char>(C)) || C == '\'' || static_cast<unsigned char>(C) >= 0x80; }
/** Term as a whole word (or phrase) anywhere in Text, ignoring case. */
static bool HasWord(const std::string& Text, const std::string& Term)
{
    const std::string T = Lower(Text), W = Lower(Term);
    for (size_t At = T.find(W); At != std::string::npos; At = T.find(W, At + 1))
    {
        const bool L = At == 0 || !IsWordChar(T[At - 1]);
        const bool R = At + W.size() >= T.size() || !IsWordChar(T[At + W.size()]);
        if (L && R) return true;
    }
    return false;
}

static void Words()
{
    std::printf("THE LINES  (Content/Data/DT_SystemLines.json)\n");
    const bool bRead = ReadJson("Content/Data/DT_SystemLines.json", Lines) && Lines.Type == FJson::Arr && !Lines.A.empty();
    Check(bRead, "DT_SystemLines.json reads, as an array of rows");
    if (!bRead) return;

    bool Named = true;
    for (const FJson& R : Lines.A)
    {
        const std::string E = R.Str("Event"), K = R.Str("Key"), N = R.Str("Name");
        Named = Named && !E.empty() && N == (K.empty() ? E : E + "_" + K);
        for (const char* F : {"Name", "Event", "Key", "Title", "Head", "Body", "Reward", "Beneath", "Status", "Area", "NameArabic", "StoryArabic"})
            Named = Named && R.Get(F) && R.Get(F)->Type == FJson::String;
    }
    Check(Named, "every row is named Event_Key (or Event) and has every field, as a DataTable row");

    bool Every = Row("OpenQuest") != nullptr;
    for (int k = 0; k < NumKinds; ++k)
    {
        bool Any = false;
        for (const FJson& R : Lines.A) Any = Any || R.Str("Event") == KindName(static_cast<EKind>(k));
        if (!Any) { Every = false; std::printf("  no line for %s\n", KindName(static_cast<EKind>(k))); }
    }
    Check(Every, "every event has a line in DT_SystemLines.json (and the open quest its own)");

    // every stage the game has: its entered quest, from its story, with the
    // stage data's own Arabic copied as it is
    FJson Stages;
    bool StagesOk = ReadJson("Content/Data/DT_Stages.json", Stages) && Stages.Type == FJson::Arr && Stages.A.size() >= 9;
    bool Arabic = StagesOk;
    int NStages = 0;
    for (const FJson& S : Stages.A)
    {
        const std::string Name = S.Str("Name");
        const FJson* R = Row("StageEntered_" + Name);
        ++NStages;
        if (!R || R->Str("Title") != "QUEST" || R->Str("Head").empty() || R->Str("Body").empty())
        {
            StagesOk = false;
            std::printf("  no entered line for %s\n", Name.c_str());
            continue;
        }
        Arabic = Arabic && R->Str("Area") == S.Str("DisplayName") && R->Str("NameArabic") == S.Str("DisplayNameArabic")
              && R->Str("StoryArabic") == S.Str("BriefingArabic") && !R->Str("StoryArabic").empty();
    }
    std::printf("  %d stages in DT_Stages.json\n", NStages);
    Check(StagesOk, "every stage in DT_Stages.json has its entered line: QUEST, its name, a sentence");
    Check(Arabic, "the stage lines carry the stage data's own name and Arabic, word for word");

    bool Talents = true, TalentAr = true;
    const auto TRows = Csv("Content/Data/DT_Talents.csv");
    for (size_t i = 1; i < TRows.size(); ++i)
    {
        if (TRows[i].size() < 4) continue;
        const FJson* R = Row("SkillAcquired_" + TRows[i][0]);
        if (!R || R->Str("Head") != TRows[i][2] + ".") { Talents = false; continue; }
        TalentAr = TalentAr && R->Str("NameArabic") == TRows[i][3];
    }
    Check(Talents && TRows.size() >= 6 && Row("SkillAcquired"), "every talent in DT_Talents.csv has its SKILL ACQUIRED line, and any other a plain one");
    Check(TalentAr, "the talent lines carry DT_Talents' own Arabic, word for word");

    bool Ranks = true;
    const auto LRows = Csv("Content/Data/DT_Levels.csv");
    for (size_t i = 2; i < LRows.size(); ++i)
        if (LRows[i].size() > 4 && LRows[i][4] != LRows[i - 1][4]) Ranks = Ranks && Row("RankUp_" + LRows[i][4]);
    Check(Ranks && LRows.size() > 18, "every rank on the ladder past ROOKIE has its line");

    // AL-SAQR's one line: titled with his name (DT_Fighters'), short
    {
        const FJson* R = Row("Speaker_Saqr");
        const auto FRows = Csv("Content/Data/DT_Fighters.csv");
        std::string Name, Ar;
        for (const auto& F : FRows) if (F.size() > 2 && F[0] == "Saqr") { Name = F[1]; Ar = F[2]; }
        const size_t Len = R ? R->Str("Head").size() + R->Str("Body").size() : 999;
        Check(R && !Name.empty() && R->Str("Title") == Name && R->Str("NameArabic") == Ar && Len <= 48 && R->Str("Reward").empty(),
              "AL-SAQR's line: a window titled with his name, short, no reward");
    }

    // the spec's fixed lines, word for word
    Check(Says(FormatLines(Ev(EKind::QuestGiven).Tpl, FArgs()), "QUEST", "FIND THE WAY UP.", "", "Reward: --."),
          "fixed: QUEST  FIND THE WAY UP.  Reward: --.");
    Check(Says(FormatLines(Ev(EKind::LevelUp).Tpl, Args(7, 6, 4)), "LEVEL UP", "Level 7.", "", "HP +6. MP +4."),
          "fixed: LEVEL UP  Level 7.  HP +6. MP +4.");
    Check(Says(FormatLines(Ev(EKind::RankUp, "PROSPECT").Tpl, Args(6, 0, 0, 0, "PROSPECT")), "RANK", "PROSPECT.", "The Halqa knows your name.", ""),
          "fixed: RANK  PROSPECT.  The Halqa knows your name.");
    Check(Says(FormatLines(Ev(EKind::SkillAcquired, "Vault").Tpl, FArgs()), "SKILL ACQUIRED", "VAULT.", "Low ledges are yours.", ""),
          "fixed: SKILL ACQUIRED  VAULT.  Low ledges are yours.");
    Check(Says(FormatLines(Ev(EKind::SkillAcquired, "HawkFist").Tpl, FArgs()), "SKILL ACQUIRED", "HAWK FIST.", "This was not yours. It is now.", ""),
          "fixed: SKILL ACQUIRED  HAWK FIST.  This was not yours. It is now.");
    Check(Says(FormatLines(Ev(EKind::StageEntered, "BaytAlDarb").Tpl, FArgs()), "QUEST", "SIX ROUNDS.", "They want to see you.", ""),
          "fixed: the striking house: QUEST  SIX ROUNDS.  They want to see you.");
    Check(Says(FormatLines(Ev(EKind::QuestComplete).Tpl, Args(0, 0, 0, 312, "", "", "SIX ROUNDS.")), "QUEST COMPLETE", "SIX ROUNDS.", "",
               "XP +312.", "FIND THE WAY UP", "IN PROGRESS"),
          "fixed: QUEST COMPLETE + XP, FIND THE WAY UP beneath it, IN PROGRESS");
    Check(Says(FormatLines(Ev(EKind::QuestUpdated).Tpl, FArgs()), "QUEST UPDATED", "FIND THE WAY UP.", "You are where you began.", ""),
          "fixed: QUEST UPDATED  FIND THE WAY UP.  You are where you began.");
    Check(Says(FormatLines(Ev(EKind::QuestRemoved).Tpl, FArgs()), "QUEST REMOVED", "FIND THE WAY UP.", "No longer required.", ""),
          "fixed: QUEST REMOVED  FIND THE WAY UP.  No longer required.");
    Check(Says(FormatLines(Ev(EKind::Down).Tpl, FArgs()), "YOU WENT DOWN", "", "", ""), "fixed: a plain YOU WENT DOWN, and nothing else");
    Check(Says(TplOf(Row("OpenQuest")), "QUEST", "FIND THE WAY UP", "", "", "", "IN PROGRESS"), "fixed: the open quest, QUEST  FIND THE WAY UP  IN PROGRESS");
    Check(Says(TplOf(Row("BossWarning")), "WARNING", "", "", ""), "the boss's line is the HUD's own WARNING heading, nothing more");

    // the voice: none of Solo Leveling's names and terms, and the System
    // never says what it is, never says above, Kuwait or home
    {
        static const char* const Forbidden[] = {
            "player", "hunter", "hunters", "arise", "shadow", "shadows", "monarch", "daily quest", "dungeon", "dungeon break",
            "solo leveling", "sung jinwoo", "jinwoo", "system", "above", "kuwait", "home", "upstairs", "surface"};
        bool Clean = true;
        for (const FJson& R : Lines.A)
            for (const auto& KV : R.O)
            {
                for (const char* W : Forbidden)
                    if (HasWord(KV.second.S, W)) { Clean = false; std::printf("  '%s' in %s.%s\n", W, R.Str("Name").c_str(), KV.first.c_str()); }
                for (const char* G : {"e", "d", "c", "b", "a", "s"})
                    for (const std::string& Pat : {std::string(G) + "-rank", std::string(G) + " rank", std::string(G) + "-class",
                                                   std::string("rank ") + G, std::string(G) + "-grade"})
                        if (HasWord(KV.second.S, Pat)) { Clean = false; std::printf("  a gate rank '%s' in %s\n", Pat.c_str(), R.Str("Name").c_str()); }
            }
        Check(Clean, "no forbidden term (Solo Leveling's names, its gate ranks, above, home, Kuwait) anywhere in the lines");
    }

    // what is drawn: ASCII, braces only the ones the System fills, two rows
    bool Ascii = true, Braces = true, Rows2 = true;
    for (const FJson& R : Lines.A)
    {
        for (const char* F : Fields)
        {
            const std::string S = R.Str(F);
            for (unsigned char C : S) Ascii = Ascii && C >= 0x20 && C < 0x7F;
            for (size_t i = S.find('{'); i != std::string::npos; i = S.find('{', i + 1))
            {
                const size_t E = S.find('}', i);
                Braces = Braces && E != std::string::npos && KnownPlaceholder(S.c_str() + i + 1, static_cast<int>(E - i - 1));
            }
            Braces = Braces && std::count(S.begin(), S.end(), '{') == std::count(S.begin(), S.end(), '}');
        }
        Rows2 = Rows2 && !(!R.Str("Body").empty() && (!R.Str("Beneath").empty() || !R.Str("Status").empty()));
    }
    Check(Ascii, "the drawn words are plain ASCII (FCanvas shapes no Arabic; the Arabic stays data)");
    Check(Braces, "every placeholder in a line is one the System fills");
    Check(Rows2, "no window has both a sentence and a quest beneath it (two rows under its heading)");

    // every line fits its window at every screen shape, with the longest
    // numbers and names it can be given
    {
        static const float Shapes[][2] = {{1920, 1080}, {1280, 720}, {3840, 2160}, {2560, 1080}, {3440, 1440}, {1600, 1200}, {1680, 1050}};
        std::string LongQuest;
        for (const FJson& R : Lines.A)
            if (R.Str("Event") == "StageEntered" && R.Str("Head").size() > LongQuest.size()) LongQuest = R.Str("Head");
        const FArgs Worst = Args(20, 114, 76, 99999, "CONTENDER", "POWER KICK", LongQuest.c_str());
        bool Fit = true;
        for (const auto& Sh : Shapes)
        {
            const FPage P = FPage::For(Sh[0], Sh[1]);
            for (const FJson& R : Lines.A)
            {
                const std::string E = R.Str("Event");
                const FLines L = FormatLines(TplOf(&R), Worst);
                bool Ok = true;
                if (E == "OpenQuest") QuestRect(P, L, &Ok);
                else if (E == "GateCleared") ToastRect(P, L, true, &Ok);
                else if (E != "BossWarning") WindowRect(P, L, &Ok);
                if (!Ok) { Fit = false; std::printf("  %s does not fit at %gx%g\n", R.Str("Name").c_str(), Sh[0], Sh[1]); }
            }
        }
        Check(Fit, "every line fits its window at every screen shape");
    }

    // the level up's numbers are the table's own step
    {
        bool Step = LRows.size() > 8;
        for (size_t i = 2; i < LRows.size() && Step; ++i)
            Step = LRows[i].size() > 6 && std::atoi(LRows[i][5].c_str()) - std::atoi(LRows[i - 1][5].c_str()) == 6
                && std::atoi(LRows[i][6].c_str()) - std::atoi(LRows[i - 1][6].c_str()) == 4;
        Check(Step, "the level up's HP +6 and MP +4 are DT_Levels' own step at every level");
    }
}

// ------------------------------------------------------------- the queue
static FModel M;
static void Run(FModel& Mo, float Seconds, float Hz, float FreezeFrom = -1.f, float FreezeTo = -1.f, float* Clock = nullptr)
{
    const int N = static_cast<int>(std::lround(Seconds * Hz));
    for (int i = 0; i < N; ++i)
    {
        const float T = Clock ? *Clock : 0.f;
        FClock C;
        C.Real = 1.f / Hz;
        C.World = (T >= FreezeFrom && T < FreezeTo) ? 0.f : C.Real;
        Mo.Tick(C);
        if (Clock) *Clock += C.Real;
    }
}
static FModel Fresh()
{
    FModel Mo;
    Mo.Quest = TplOf(Row("OpenQuest"));
    return Mo;
}

static void Queue()
{
    std::printf("THE QUEUE\n");
    // a stage's end, all at once: the quest, the level, the rank, the
    // talent, then the next area
    {
        FModel Mo = Fresh();
        Mo.Push(Ev(EKind::StageEntered, "MarsaAlFajr"));
        Mo.Push(Ev(EKind::SkillAcquired, "Vault"));
        Mo.Push(Ev(EKind::LevelUp, "", Args(3, 6, 4)));
        Mo.Push(Ev(EKind::RankUp, "AMATEUR", Args(3, 0, 0, 0, "AMATEUR")));
        Mo.Push(Ev(EKind::QuestComplete, "", Args(0, 0, 0, 300, "", "", "SIX ROUNDS.")));
        std::vector<EKind> Seen;
        for (int f = 0; f < 60 * 40 && Seen.size() < 5; ++f)
        {
            Mo.Tick({1.f / 60.f, 1.f / 60.f});
            for (int i = 0; i < Mo.NumOpened; ++i) Seen.push_back(Mo.Opened[i]);
        }
        const bool Ordered = Seen.size() == 5 && Seen[0] == EKind::QuestComplete && Seen[1] == EKind::LevelUp && Seen[2] == EKind::RankUp
                          && Seen[3] == EKind::SkillAcquired && Seen[4] == EKind::StageEntered;
        Check(Ordered, "at once: QUEST COMPLETE, then LEVEL UP, RANK, SKILL ACQUIRED, then the next area's quest");
    }
    // a level up during a quest complete waits for it, and a gap after
    {
        FModel Mo = Fresh();
        Mo.Push(Ev(EKind::QuestComplete, "", Args(0, 0, 0, 300, "", "", "SIX ROUNDS.")));
        Run(Mo, 0.5f, 60.f);
        Mo.Push(Ev(EKind::LevelUp, "", Args(4, 6, 4)));
        bool Waited = Mo.Window.E.Kind == EKind::QuestComplete;
        float Gone = -1.f, Opened = -1.f, T = 0.5f;
        for (int f = 0; f < 60 * 10 && Opened < 0.f; ++f)
        {
            const bool Was = Mo.Window.bOn && Mo.Window.E.Kind == EKind::QuestComplete;
            Mo.Tick({1.f / 60.f, 1.f / 60.f});
            T += 1.f / 60.f;
            if (Was && !(Mo.Window.bOn && Mo.Window.E.Kind == EKind::QuestComplete)) Gone = T;
            if (Mo.Window.bOn && Mo.Window.E.Kind == EKind::LevelUp) Opened = T;
            if (Gone < 0.f && Mo.Window.bOn && Mo.Window.E.Kind == EKind::LevelUp) Waited = false;
        }
        Check(Waited && Gone > 0.f && Opened >= Gone + WindowGap - 1.f / 60.f - 1e-4f,
              "a level up during a quest complete waits for it to go, and a gap after");
    }
    // a long night of everything: one window and one toast at most, a new
    // one only once the last has gone, each in its own lane
    {
        FModel Mo = Fresh();
        unsigned Seed = 12345u;
        auto Rand = [&Seed]() { Seed = Seed * 1103515245u + 12345u; return (Seed >> 16) & 0x7FFF; };
        static const char* const Keys[] = {"BaytAlDarb", "AlHilal", "Vault", "HawkFist", "PROSPECT", "Saqr", ""};
        bool OneAtATime = true, Lanes = true, Bounded = true;
        float PrevAge[2] = {0.f, 0.f}, PrevTotal[2] = {0.f, 0.f};
        bool PrevOn[2] = {false, false};
        for (int f = 0; f < 60 * 180; ++f)
        {
            if (Rand() % 100 < 4)
            {
                const EKind K = static_cast<EKind>(Rand() % NumKinds);
                Mo.Push(Ev(K, Keys[Rand() % 7], Args(2 + static_cast<int>(Rand() % 18), 6, 4, 50)));
            }
            Mo.Tick({1.f / 60.f, (f % 50 < 6) ? 0.f : 1.f / 60.f});
            int k = 0;
            for (FShown* S : {&Mo.Window, &Mo.Toast})
            {
                if (S->bOn && PrevOn[k] && S->Age < PrevAge[k] && PrevAge[k] + 1.f / 60.f < PrevTotal[k] - 1e-4f) OneAtATime = false;
                // by what it is, not by the rule's word for it
                if (S->bOn) Lanes = Lanes && ((S == &Mo.Toast) == (S->E.Kind == EKind::GateCleared)) && S->E.Kind != EKind::BossWarning;
                PrevOn[k] = S->bOn; PrevAge[k] = S->Age; PrevTotal[k] = S->Total();
                ++k;
            }
            Bounded = Bounded && Mo.NumQueued <= QueueMax;
        }
        Check(OneAtATime, "at most one window and one toast at once: a new one opens only when the last has gone");
        // and side by side: a gate and a level at once show at once, one in each
        FModel Two = Fresh();
        Two.Push(Ev(EKind::GateCleared, "Experience", Args(0, 0, 0, 450)));
        Two.Push(Ev(EKind::LevelUp, "", Args(4, 6, 4)));
        Two.Tick({1.f / 60.f, 1.f / 60.f});
        Lanes = Lanes && Two.Toast.bOn && Two.Toast.E.Kind == EKind::GateCleared && Two.Window.bOn && Two.Window.E.Kind == EKind::LevelUp;
        Check(Lanes && Bounded, "the toast is the gate's, the window everything else's, the boss's WARNING neither's");
    }
    // he goes down: whatever is showing goes, fast, and DOWN shows
    {
        FModel Mo = Fresh();
        Mo.Push(Ev(EKind::StageEntered, "AlHilal"));
        Run(Mo, 1.0f, 60.f);
        Mo.Push(Ev(EKind::Down));
        Run(Mo, PreemptClose + 2.f / 60.f, 60.f);
        Check(Mo.Window.bOn && Mo.Window.E.Kind == EKind::Down && Mo.Window.E.Tint == ETint::Danger,
              "a man going down cuts what is showing, at once, and the window is crimson");
    }
    // two level ups not yet shown are one window
    {
        FModel Mo = Fresh();
        Mo.Push(Ev(EKind::QuestComplete, "", Args(0, 0, 0, 300, "", "", "THE RAID.")));
        Run(Mo, 0.2f, 60.f);
        Mo.Push(Ev(EKind::LevelUp, "", Args(5, 6, 4)));
        Mo.Push(Ev(EKind::LevelUp, "", Args(6, 6, 4)));
        int Levels = 0;
        bool Merged = false;
        for (int f = 0; f < 60 * 20; ++f)
        {
            Mo.Tick({1.f / 60.f, 1.f / 60.f});
            for (int i = 0; i < Mo.NumOpened; ++i)
                if (Mo.Opened[i] == EKind::LevelUp)
                {
                    ++Levels;
                    Merged = Says(Mo.Window.Text, "LEVEL UP", "Level 6.", "", "HP +12. MP +8.");
                }
        }
        Check(Levels == 1 && Merged, "two level ups not yet shown are one window: the later level, what both were worth");
    }
    // the boss's WARNING is the HUD's
    {
        FModel Mo = Fresh();
        Mo.Push(Ev(EKind::BossWarning, "Saqr"));
        Mo.Push(Ev(EKind::Speaker, "Saqr"));
        bool Held = true, Opened = false;
        float T = 0.f;
        for (int f = 0; f < 60 * 3; ++f)
        {
            Mo.Tick({1.f / 60.f, 1.f / 60.f});
            T += 1.f / 60.f;
            if (Mo.Window.bOn && T < BossHold - 1.f / 60.f) Held = false;
            if (Mo.Window.bOn) Opened = true;
            if (Mo.Window.bOn && Mo.Window.E.Kind == EKind::BossWarning) Held = false;
        }
        Check(Held && Opened && BossHold >= SaudHud::BannerRevealSeconds,
              "the boss's WARNING is the HUD's: no System window of its own, the lane held while it wipes open");
    }
    // said once
    {
        FModel Mo = Fresh();
        Mo.Push(Ev(EKind::StageEntered, "BaytAlDarb"));
        Mo.Push(Ev(EKind::StageEntered, "BaytAlDarb"));
        int Shown = 0;
        for (int f = 0; f < 60 * 15; ++f)
        {
            Mo.Tick({1.f / 60.f, 1.f / 60.f});
            for (int i = 0; i < Mo.NumOpened; ++i) Shown += Mo.Opened[i] == EKind::StageEntered;
        }
        Check(Shown == 1, "an area's quest pushed twice before it shows is said once");
    }
    // a full queue drops the least, never a man going down
    {
        FModel Mo = Fresh();
        Mo.Push(Ev(EKind::Speaker, "Saqr"));
        Mo.Tick({1.f / 60.f, 1.f / 60.f});
        char Key[8];
        for (int i = 0; i < 24; ++i) { std::snprintf(Key, sizeof Key, "S%d", i); Mo.Push(Ev(EKind::StageEntered, Key)); }
        Mo.Push(Ev(EKind::QuestRemoved));
        Check(Mo.Dropped > 0 && Mo.NumQueued == QueueMax && Mo.FindPending(EKind::QuestRemoved) >= 0 && Mo.Next(ELane::Window) == Mo.FindPending(EKind::QuestRemoved),
              "a full queue drops the least of what waits, never the victory or a man going down");
    }
    // the look is told what opened
    {
        FModel Mo = Fresh();
        Mo.Push(Ev(EKind::SkillAcquired, "HawkFist"));
        Mo.Tick({1.f / 60.f, 1.f / 60.f});
        Check(Mo.NumOpened == 1 && Mo.Opened[0] == EKind::SkillAcquired && Mo.Window.E.Tint == ETint::Shadow,
              "what opened is reported for the look's flourish, and HAWK FIST's window is violet");
        Mo.Tick({1.f / 60.f, 1.f / 60.f});
        Check(Mo.NumOpened == 0, "...once, on the frame it opens");
        Check(TintFor(EKind::SkillAcquired, "Vault") == ETint::System && TintFor(EKind::LevelUp, "") == ETint::System
                  && TintFor(EKind::Down, "") == ETint::Danger,
              "every other window is the System's cyan; a man down's crimson");
    }
}

// ------------------------------------------------------------- the clock
struct FTimes { float Open = -1.f, Text = -1.f, Fading = -1.f, Gone = -1.f; };
static FTimes Measure(EKind K, const char* Key, FArgs A, float Hz, float FreezeFrom, float FreezeTo)
{
    FModel Mo = Fresh();
    Mo.Push(Ev(K, Key, A));
    FTimes T;
    float Clock = 0.f;
    for (int f = 0; f < static_cast<int>(Hz * 12.f); ++f)
    {
        FClock C;
        C.Real = 1.f / Hz;
        C.World = (Clock >= FreezeFrom && Clock < FreezeTo) ? 0.f : C.Real * 1.f;
        Mo.Tick(C);
        Clock += C.Real;
        if (Mo.Window.bOn && T.Open < 0.f) T.Open = Clock;
        if (Mo.Window.bOn && Mo.Window.TextShown() && T.Text < 0.f) T.Text = Clock;
        if (Mo.Window.bOn && Mo.Window.Fade() < 1.f && T.Fading < 0.f) T.Fading = Clock;
        if (!Mo.Window.bOn && T.Open >= 0.f && T.Gone < 0.f) T.Gone = Clock;
    }
    return T;
}

static void Clock()
{
    std::printf("THE CLOCK\n");
    bool Real = true, Same = true;
    for (float Hz : {30.f, 60.f})
    {
        const float Frame = 1.f / Hz + 1e-4f;
        const FSysEvent E = Ev(EKind::LevelUp, "", Args(7, 6, 4));
        const FLines L = FormatLines(E.Tpl, E.Args);
        const FRule R = RuleOf(EKind::LevelUp);
        const float Hold = ReadSeconds(L);
        // a freeze across the opening, another across the hold
        for (float From : {0.05f, 1.2f})
        {
            const FTimes A = Measure(EKind::LevelUp, "", Args(7, 6, 4), Hz, -1.f, -1.f);
            const FTimes B = Measure(EKind::LevelUp, "", Args(7, 6, 4), Hz, From, From + 0.45f);
            Real = Real && std::fabs((A.Text - A.Open) - R.Open) <= Frame && std::fabs((A.Fading - A.Text) - Hold) <= Frame
                && std::fabs((A.Gone - A.Fading) - R.Close) <= Frame;
            Same = Same && A.Open == B.Open && A.Text == B.Text && A.Fading == B.Fading && A.Gone == B.Gone && B.Gone > 0.f;
        }
        std::printf("  %g Hz: opens over %.2f s, holds %.2f s, closes over %.2f s (real seconds)\n", Hz, R.Open, Hold, R.Close);
    }
    Check(Real, "a window opens, holds and closes over its own real seconds, at 30 and 60 Hz");
    Check(Same, "...the same through a blow's freeze: the world's clock stops, the window's does not");

    // reading time, AL-SAQR fast, the victory slow
    {
        const FRule S = RuleOf(EKind::Speaker), V = RuleOf(EKind::QuestRemoved);
        const FTimes T = Measure(EKind::Speaker, "Saqr", FArgs(), 60.f, -1.f, -1.f);
        Check(S.Close <= 0.15f && T.Gone - T.Fading <= 0.15f + 1.f / 60.f && T.Gone - T.Open <= 2.3f,
              "AL-SAQR's window fades fast: out in 0.15 s, gone in 2.3");
        Check(V.Hold >= 3.5f && ReadMin >= 2.f && ReadMax <= 5.f, "the victory's window holds longest; the rest long enough to read and no longer");
    }
    // a gap between two windows
    {
        FModel Mo = Fresh();
        Mo.Push(Ev(EKind::StageEntered, "AlHilal"));
        Mo.Push(Ev(EKind::QuestGiven));
        float Gone = -1.f, Again = -1.f, T = 0.f;
        bool Was = false;
        for (int f = 0; f < 30 * 15; ++f)
        {
            Mo.Tick({1.f / 30.f, 1.f / 30.f});
            T += 1.f / 30.f;
            if (Was && !Mo.Window.bOn && Gone < 0.f) Gone = T;
            if (Gone > 0.f && Mo.Window.bOn && Again < 0.f) Again = T;
            Was = Mo.Window.bOn;
        }
        Check(Gone > 0.f && Again - Gone >= WindowGap - 1.f / 30.f - 1e-4f && WindowGap >= 0.15f,
              "a gap of at least 0.20 s between one window and the next");
    }
}

// ------------------------------------------------------------- the page
static const float Shapes[][2] = {{1920, 1080}, {1280, 720}, {3840, 2160}, {2560, 1080}, {3440, 1440}, {1600, 1200}, {1680, 1050}};
static FSysList List;
static SaudHud::FDrawList Hud;

struct FBox { float X0 = 1e9f, Y0 = 1e9f, X1 = -1e9f, Y1 = -1e9f; bool Any = false; };
static void Add(FBox& B, const FPoint& P)
{
    B.X0 = std::fmin(B.X0, P.X); B.Y0 = std::fmin(B.Y0, P.Y); B.X1 = std::fmax(B.X1, P.X); B.Y1 = std::fmax(B.Y1, P.Y); B.Any = true;
}
static bool Overlap(const FBox& A, const FBox& B) { return A.Any && B.Any && A.X0 < B.X1 && B.X0 < A.X1 && A.Y0 < B.Y1 && B.Y0 < A.Y1; }
static float Cross(const FPoint& A, const FPoint& B, const FPoint& C) { return (B.X - A.X) * (C.Y - A.Y) - (B.Y - A.Y) * (C.X - A.X); }
static float Contrast(const FRgba& A, const FRgba& B)
{
    const float La = 0.2126f * A.R + 0.7152f * A.G + 0.0722f * A.B, Lb = 0.2126f * B.R + 0.7152f * B.G + 0.0722f * B.B;
    return (std::fmax(La, Lb) + 0.05f) / (std::fmin(La, Lb) + 0.05f);
}
static bool InSafe(const FPage& P, float X, float Y)
{
    const float E = 0.5f, MX = 0.05f * P.ScreenW, MY = 0.05f * P.ScreenH;
    return X >= MX - E && Y >= MY - E && X <= P.ScreenW - MX + E && Y <= P.ScreenH - MY + E;
}
static FBox PieceBox(EPiece Pc)
{
    FBox B;
    const int I = static_cast<int>(Pc);
    for (int t = List.From[I]; t < List.To[I]; ++t) for (const FHudVert& V : List.Shapes.Tris[t].V) Add(B, V.P);
    return B;
}
static FBox PanelBox(EPiece Pc)
{
    FBox B;
    const int I = static_cast<int>(Pc);
    for (int t = List.From[I]; t < List.To[I]; ++t)
        if (List.Shapes.Tris[t].Part == SaudHud::EHudPart::Panel) for (const FHudVert& V : List.Shapes.Tris[t].V) Add(B, V.P);
    return B;
}
static FBox HudBox(SaudHud::EHudGroup G)
{
    FBox B;
    for (int t = 0; t < Hud.NumTris; ++t) if (Hud.Tris[t].Group == G) for (const FHudVert& V : Hud.Tris[t].V) Add(B, V.P);
    return B;
}
/** The HUD at its fullest, as tests/anime.cpp's worst case. */
static SaudHud::FHudState HudWorst()
{
    SaudHud::FHudState S;
    S.Health = 0.25f; S.Ghost = 0.5f; S.Stamina = 0.6f; S.Rage = 1.f; S.bRageReady = true;
    S.Combo = 99; S.SinceCombo = 0.f;
    S.bBoss = true; S.BossHealth = 0.5f; S.BossGhost = 0.7f; S.bBossEnraged = true; S.BossSince = 1.f;
    return S;
}

/** A model showing Window (and a toast, and the open quest) Age seconds in. */
static FModel Showing(const FSysEvent& Win, float WinAge, bool bToast, float ToastAge, bool bQuest)
{
    FModel Mo = Fresh();
    Mo.SetQuestOpen(bQuest);
    Mo.QuestShow = bQuest ? 1.f : 0.f;
    Mo.Push(Win);
    if (bToast) Mo.Push(Ev(EKind::GateCleared, "Experience", Args(0, 0, 0, 450)));
    Mo.Tick({0.f, 0.f});
    Mo.Window.Age = WinAge;
    Mo.Toast.Age = ToastAge;
    return Mo;
}

static void Page()
{
    std::printf("THE PAGE  (what Build draws, at seven screen shapes)\n");
    std::string LongQuest;
    for (const FJson& R : Lines.A)
        if (R.Str("Event") == "StageEntered" && R.Str("Head").size() > LongQuest.size()) LongQuest = R.Str("Head");
    std::vector<FSysEvent> Wins;
    for (const FJson& R : Lines.A)
    {
        const std::string E = R.Str("Event");
        for (int k = 0; k < NumKinds; ++k)
            if (E == KindName(static_cast<EKind>(k)) && RuleOf(static_cast<EKind>(k)).Lane == ELane::Window)
                Wins.push_back(MakeEvent(static_cast<EKind>(k), R.Str("Key").c_str(), TplOf(&R),
                                         Args(20, 114, 76, 99999, "CONTENDER", "POWER KICK", LongQuest.c_str())));
    }
    bool AllIn = true, Clear = true, OffHud = true, Apart = true, TextIn = true, Legible = true, Stroked = true;
    bool Edged = true, Wound = true, NoNaN = true, Fits = true, NoRun = true, Drawn = true;
    for (const auto& Sh : Shapes)
    {
        const FPage P = FPage::For(Sh[0], Sh[1]);
        SaudHud::Build(P, HudWorst(), Hud);
        const FBox HudBoxes[3] = {HudBox(SaudHud::EHudGroup::Player), HudBox(SaudHud::EHudGroup::Combo), HudBox(SaudHud::EHudGroup::Boss)};
        FBox Fight;
        Fight.X0 = 0.30f * P.ScreenW; Fight.X1 = 0.70f * P.ScreenW; Fight.Y0 = 0.20f * P.ScreenH; Fight.Y1 = 0.80f * P.ScreenH; Fight.Any = true;
        for (const FSysEvent& W : Wins)
            for (float Age : {0.05f, 0.15f, 1.5f, 1000.f})
            {
                FModel Mo = Showing(W, Age == 1000.f ? 0.f : Age, true, Age == 1000.f ? 2.4f : Age, true);
                if (Age == 1000.f) Mo.Window.Age = Mo.Window.Open + Mo.Window.Hold + 0.5f * Mo.Window.Close;   // fading
                Build(P, Mo, List);
                Fits = Fits && !List.bOverflow;
                Drawn = Drawn && List.bOn[0] && List.bOn[1] && List.bOn[2];
                for (int t = 0; t < List.Shapes.NumTris; ++t)
                {
                    const FHudTri& T = List.Shapes.Tris[t];
                    FBox B;
                    for (const FHudVert& V : T.V)
                    {
                        if (!(V.P.X == V.P.X) || !(V.P.Y == V.P.Y)) NoNaN = false;
                        if (!InSafe(P, V.P.X, V.P.Y)) AllIn = false;
                        Add(B, V.P);
                    }
                    if (Overlap(B, Fight)) Clear = false;
                    if (!(Cross(T.V[0].P, T.V[1].P, T.V[2].P) > 1e-3f)) Wound = false;
                }
                const FBox Mine[3] = {PieceBox(EPiece::Window), PieceBox(EPiece::Toast), PieceBox(EPiece::Quest)};
                for (int a = 0; a < 3; ++a)
                {
                    for (const FBox& H : HudBoxes) if (Overlap(Mine[a], H)) OffHud = false;
                    for (int b = a + 1; b < 3; ++b) if (Overlap(Mine[a], Mine[b])) Apart = false;
                }
                float HeadEnd = -1.f, RewardStart = -1.f;
                for (int i = 0; i < List.NumTexts; ++i)
                {
                    const FSysText& X = List.Texts[i];
                    // inside the panel as DRAWN (a window wiping open is narrower than its layout)
                    const FBox Pan = PanelBox(X.Piece);
                    const FRect R = {Pan.X0, Pan.Y0, Pan.X1 - Pan.X0, Pan.Y1 - Pan.Y0};
                    const float W = TextWidth(X.S, X.Height);
                    const float X0 = X.Align == EAlign::Left ? X.At.X : (X.Align == EAlign::Right ? X.At.X - W : X.At.X - 0.5f * W);
                    const bool In = InSafe(P, X0, X.At.Y) && InSafe(P, X0 + W, X.At.Y + X.Height)
                          && X0 >= R.X + 1.f && X0 + W <= R.X + R.W - 1.f && X.At.Y >= R.Y && X.At.Y + X.Height <= R.Y + R.H + 0.5f;
                    if (!In && TextIn) std::printf("  '%s' (piece %d) at %gx%g: %.0f..%.0f x %.0f..%.0f outside %.0f..%.0f x %.0f..%.0f\n", X.S,
                                                   static_cast<int>(X.Piece), Sh[0], Sh[1], X0, X0 + W, X.At.Y, X.At.Y + X.Height, R.X, R.X + R.W, R.Y, R.Y + R.H);
                    TextIn = TextIn && In;
                    Legible = Legible && X.Height >= P.ScreenH / 36.f - 0.01f;
                    Stroked = Stroked && X.Stroke >= 2.f * P.ScreenH / 720.f - 0.01f
                           && Contrast(X.Colour, SaudHud::Colour::Ink) >= (X.Slot == ESlot::Title ? 4.5f : 7.f);
                    if (X.Piece == EPiece::Window && X.Slot == ESlot::Head) HeadEnd = X0 + W;
                    if (X.Piece == EPiece::Window && X.Slot == ESlot::Reward) RewardStart = X0;
                }
                if (HeadEnd > 0.f && RewardStart > 0.f) NoRun = NoRun && HeadEnd + P.Px(14.f) <= RewardStart;   // a clear gap
                // every window at rest: a solid edge, a glow fading out
                if (Age == 1.5f)
                    for (int Pc = 0; Pc < 3; ++Pc)
                    {
                        int Edges = 0, Glows = 0;
                        bool Fades = true;
                        for (int t = List.From[Pc]; t < List.To[Pc]; ++t)
                        {
                            const FHudTri& T = List.Shapes.Tris[t];
                            if (T.Part == SaudHud::EHudPart::Edge) { ++Edges; for (const FHudVert& V : T.V) Edged = Edged && V.C.A >= 0.999f; }
                            if (T.Part == SaudHud::EHudPart::Glow)
                            {
                                ++Glows;
                                float Lo = 1.f, Hi = 0.f;
                                for (const FHudVert& V : T.V) { Lo = std::fmin(Lo, V.C.A); Hi = std::fmax(Hi, V.C.A); }
                                Fades = Fades && Lo <= 1e-4f && Hi > 0.05f;
                            }
                        }
                        Edged = Edged && Edges >= 12 && Glows >= 12 && Fades;
                    }
            }
    }
    Check(NoNaN, "the System's shapes are numbers");
    Check(Drawn && Fits, "the window, the toast and the open quest are drawn, and fit the draw list");
    Check(AllIn, "every vertex the System draws is inside title-safe, at every screen shape");
    Check(Clear, "nothing the System draws is over the fight's centre box");
    Check(OffHud, "nothing the System draws is over the HUD's own windows (STATUS, COMBO, WARNING)");
    Check(Apart, "the window, the toast and the open quest never overlap");
    Check(TextIn, "every word inside its own window, and in title-safe, at every screen shape");
    Check(NoRun, "the first line and its reward never run into each other");
    Check(Legible, "no word the System shows is under 1/36 of the screen");
    Check(Stroked, "every word stroked in ink, 2 px at 720 lines; headings 4.5:1 against it, the rest 7:1");
    Check(Edged, "every System window has a solid edge and a glow fading out from it to nothing");
    Check(Wound, "no triangle is inverted or degenerate");

    // its colours: HAWK FIST violet, a man down crimson, the rest cyan
    {
        const FPage P = FPage::For(1920, 1080);
        auto EdgeOf = [&](const FSysEvent& E) {
            FModel Mo = Showing(E, 1.5f, false, 0.f, false);
            Build(P, Mo, List);
            for (int t = List.From[0]; t < List.To[0]; ++t)
                if (List.Shapes.Tris[t].Part == SaudHud::EHudPart::Edge) return List.Shapes.Tris[t].V[0].C;
            return FRgba{};
        };
        auto Is = [](const FRgba& A, const FRgba& B) { return std::fabs(A.R - B.R) < 1e-4f && std::fabs(A.G - B.G) < 1e-4f && std::fabs(A.B - B.B) < 1e-4f; };
        Check(Is(EdgeOf(Ev(EKind::SkillAcquired, "HawkFist")), SaudHud::Colour::Shadow) && Is(EdgeOf(Ev(EKind::Down)), SaudHud::Colour::Danger)
                  && Is(EdgeOf(Ev(EKind::SkillAcquired, "Vault")), SaudHud::Colour::System) && Is(EdgeOf(Ev(EKind::QuestRemoved)), SaudHud::Colour::System),
              "drawn: HAWK FIST's window edged violet, a man down's crimson, every other the System's cyan");
    }

    // how much of the screen it darkens, alpha-weighted, at 1080p
    {
        const FPage P = FPage::For(1920, 1080);
        auto Cover = [&](bool bQuestOnly) {
            double Sum = 0.0;
            int N = 0;
            for (float Y = 1.5f; Y < P.ScreenH; Y += 3.f)
                for (float X = 1.5f; X < P.ScreenW; X += 3.f)
                {
                    ++N;
                    float ClearA = 1.f;
                    for (int t = 0; t < List.Shapes.NumTris; ++t)
                    {
                        const FHudTri& T = List.Shapes.Tris[t];
                        if (T.Part != SaudHud::EHudPart::Panel && T.Part != SaudHud::EHudPart::Head && T.Part != SaudHud::EHudPart::Glow) continue;
                        if (bQuestOnly && (t < List.From[2] || t >= List.To[2])) continue;
                        const FPoint& A = T.V[0].P; const FPoint& B = T.V[1].P; const FPoint& C = T.V[2].P;
                        if (X < std::fmin(A.X, std::fmin(B.X, C.X)) || X > std::fmax(A.X, std::fmax(B.X, C.X))
                            || Y < std::fmin(A.Y, std::fmin(B.Y, C.Y)) || Y > std::fmax(A.Y, std::fmax(B.Y, C.Y))) continue;
                        const FPoint Pt = {X, Y};
                        const float D = Cross(A, B, C), L0 = Cross(B, C, Pt) / D, L1 = Cross(C, A, Pt) / D, L2 = 1.f - L0 - L1;
                        if (L0 < 0.f || L1 < 0.f || L2 < 0.f) continue;
                        ClearA *= 1.f - (L0 * T.V[0].C.A + L1 * T.V[1].C.A + L2 * T.V[2].C.A);
                    }
                    Sum += 1.0 - ClearA;
                }
            return static_cast<float>(Sum / N);
        };
        float Worst = 0.f;
        const FSysEvent* Widest = nullptr;
        for (const FSysEvent& W : Wins)
        {
            FLines L = FormatLines(W.Tpl, W.Args);
            if (!Widest || WindowRect(P, L).W * WindowRect(P, L).H > WindowRect(P, FormatLines(Widest->Tpl, Widest->Args)).W * WindowRect(P, FormatLines(Widest->Tpl, Widest->Args)).H)
                Widest = &W;
        }
        FModel Mo = Showing(*Widest, 1.5f, true, 1.0f, true);
        Build(P, Mo, List);
        Worst = Cover(false);
        const float Quest = Cover(true);
        std::printf("  coverage at 1080p, alpha-weighted: %.1f %% at its fullest (window, toast, open quest), %.1f %% the open quest alone\n",
                    100.f * Worst, 100.f * Quest);
        Check(Worst <= 0.09f && Quest <= 0.025f, "the System darkens at most 9 % of the screen at its fullest, the open quest alone 2.5 %");
    }
}

// ------------------------------------------------------------- the quest
static void Quest()
{
    std::printf("THE OPEN QUEST\n");
    FModel Mo = Fresh();
    const FPage P = FPage::For(1920, 1080);
    auto Shown = [&]() { Build(P, Mo, List); return List.bOn[static_cast<int>(EPiece::Quest)]; };
    Run(Mo, 2.f, 60.f);
    const bool NotBefore = !Shown() && !Mo.bQuestOpen;
    // the first landing: QUEST FIND THE WAY UP, then the souq's own
    Mo.Push(Ev(EKind::StageEntered, "SouqAlDawar"));
    Mo.Push(Ev(EKind::QuestGiven));
    bool FromLanding = true;
    float T = 0.f, Given = -1.f;
    for (int f = 0; f < 60 * 4; ++f)
    {
        Mo.Tick({1.f / 60.f, 1.f / 60.f});
        T += 1.f / 60.f;
        for (int i = 0; i < Mo.NumOpened; ++i) if (Mo.Opened[i] == EKind::QuestGiven) Given = T;
        if (Given >= 0.f && T > Given + QuestFadeSeconds + 1.f / 60.f && !(Shown() && Mo.QuestShow >= 1.f)) FromLanding = false;
        if (Given < 0.f && Shown()) FromLanding = false;
    }
    // the whole game: areas, fights, levels, falls, the ring closing
    const EKind Game[] = {EKind::StageEntered, EKind::LevelUp, EKind::QuestComplete, EKind::Down, EKind::SkillAcquired,
                          EKind::GateCleared, EKind::RankUp, EKind::QuestUpdated, EKind::BossWarning, EKind::Speaker};
    bool Beneath = false;
    for (int r = 0; r < 3; ++r)
        for (EKind K : Game)
        {
            Mo.Push(Ev(K, K == EKind::StageEntered ? "AlHilal" : (K == EKind::Speaker ? "Saqr" : ""), Args(5 + r, 6, 4, 200, "", "", "THE CRESCENT.")));
            for (int f = 0; f < 60 * 6; ++f)
            {
                Mo.Tick({1.f / 60.f, (f % 40 < 5) ? 0.f : 1.f / 60.f});
                FromLanding = FromLanding && Shown() && Mo.QuestShow >= 1.f;
                if (Mo.Window.bOn && Mo.Window.E.Kind == EKind::QuestComplete && Mo.Window.TextShown())
                {
                    Build(P, Mo, List);
                    for (int i = 0; i < List.NumTexts; ++i)
                        if (List.Texts[i].Piece == EPiece::Window && List.Texts[i].Slot == ESlot::Status && Same(List.Texts[i].S, "IN PROGRESS")) Beneath = true;
                }
            }
        }
    // the victory removes it, for good
    Mo.Push(Ev(EKind::QuestRemoved));
    float Removed = -1.f;
    bool Gone = true;
    T = 0.f;
    for (int f = 0; f < 60 * 30; ++f)
    {
        if (f == 600) Mo.Push(Ev(EKind::LevelUp, "", Args(12, 6, 4)));
        if (f == 900) Mo.Push(Ev(EKind::StageEntered, "BilaNihaya"));
        Mo.Tick({1.f / 60.f, 1.f / 60.f});
        T += 1.f / 60.f;
        for (int i = 0; i < Mo.NumOpened; ++i) if (Mo.Opened[i] == EKind::QuestRemoved) Removed = T;
        if (Removed < 0.f && !Shown()) Gone = false;   // not before the victory's window
        if (Removed >= 0.f && T > Removed + QuestFadeSeconds + 1.f / 60.f && (Shown() || Mo.bQuestOpen)) Gone = false;
    }
    Check(NotBefore, "the open quest is not shown before the first landing");
    Check(FromLanding && Given >= 0.f, "the open quest is shown from the first landing's window, through the whole game");
    Check(Beneath, "QUEST COMPLETE shows the open quest beneath it, IN PROGRESS");
    Check(Gone && Removed >= 0.f, "the victory's QUEST REMOVED takes the open quest away, for good");
}

int main()
{
    Words();
    Queue();
    Clock();
    Page();
    Quest();
    if (Fails) { std::printf("%d system check(s) failed\n", Fails); return 1; }
    std::printf("all system checks passed\n");
    return 0;
}
