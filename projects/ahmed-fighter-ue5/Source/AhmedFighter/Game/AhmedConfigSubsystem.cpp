#include "Game/AhmedConfigSubsystem.h"

#include "Combat/AhmedTypes.h"
#include "Engine/DataTable.h"
#include "HttpModule.h"
#include "Interfaces/IHttpResponse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

DEFINE_LOG_CATEGORY_STATIC(LogAhmedBalance, Log, All);

void UAhmedConfigSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	// 1. The build's own tables. From here the game is playable; everything
	//    below is an improvement on that, never a prerequisite for it.
	UseBakedTables();
	OnBalanceApplied.Broadcast(Source);

	// 2. Anything a previous run downloaded.
	TryCachedPayload();

	// 3. Ask the server, if there is one.
	if (bEnableRemoteBalance && !BalanceApiUrl.IsEmpty())
	{
		RequestRevision();
	}
	else
	{
		UE_LOG(LogAhmedBalance, Log,
			TEXT("Remote balance off; running on %s tables at revision %s."),
			Source == EBalanceSource::Cached ? TEXT("cached") : TEXT("shipped"),
			Revision.IsEmpty() ? TEXT("(none recorded)") : *Revision);
	}
}

void UAhmedConfigSubsystem::Deinitialize()
{
	bInFlight = false;
	Super::Deinitialize();
}

/* -------------------------------------------------------------- the baked */

void UAhmedConfigSubsystem::UseBakedTables()
{
	AttackTable  = BakedAttackTable.LoadSynchronous();
	FighterTable = BakedFighterTable.LoadSynchronous();
	StageTable   = BakedStageTable.LoadSynchronous();
	TalentTable  = BakedTalentTable.LoadSynchronous();
	UpgradeTable = BakedUpgradeTable.LoadSynchronous();
	LevelTable   = BakedLevelTable.LoadSynchronous();
	WeaponTable  = BakedWeaponTable.LoadSynchronous();

	Source = EBalanceSource::Baked;

	// A missing table is a packaging mistake, and it is worth being loud about
	// because the symptom otherwise is an empty roster three menus later.
	if (!AttackTable || !FighterTable || !StageTable)
	{
		UE_LOG(LogAhmedBalance, Error,
			TEXT("A core table did not load. Check the Baked*Table paths in ")
			TEXT("DefaultGame.ini and that Content/Data is in the package."));
	}
}

/* ------------------------------------------------------------- the cached */

FString UAhmedConfigSubsystem::CachePath() const
{
	return FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Balance"), TEXT("config.json"));
}

void UAhmedConfigSubsystem::TryCachedPayload()
{
	const FString Path = CachePath();
	if (!FPaths::FileExists(Path))
	{
		return;
	}

	FString Json;
	if (!FFileHelper::LoadFileToString(Json, *Path))
	{
		UE_LOG(LogAhmedBalance, Warning, TEXT("Cached balance unreadable at %s."), *Path);
		return;
	}

	FString Error;
	if (ApplyPayload(Json, EBalanceSource::Cached, Error))
	{
		UE_LOG(LogAhmedBalance, Log, TEXT("Applied cached balance, revision %s."), *Revision);
		OnBalanceApplied.Broadcast(Source);
	}
	else
	{
		// A bad cache is not worth keeping; the next fetch will replace it.
		UE_LOG(LogAhmedBalance, Warning,
			TEXT("Cached balance rejected (%s). Falling back to the shipped tables."), *Error);
		IFileManager::Get().Delete(*Path);
		UseBakedTables();
	}
}

void UAhmedConfigSubsystem::WriteCache(const FString& Json) const
{
	const FString Path = CachePath();
	if (!FFileHelper::SaveStringToFile(Json, *Path))
	{
		UE_LOG(LogAhmedBalance, Warning, TEXT("Could not write balance cache to %s."), *Path);
	}
}

/* ------------------------------------------------------------- the remote */

TSharedPtr<IHttpRequest, ESPMode::ThreadSafe>
UAhmedConfigSubsystem::MakeRequest(const FString& Path) const
{
	FString Base = BalanceApiUrl;
	Base.RemoveFromEnd(TEXT("/"));

	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
	Req->SetURL(Base + Path);
	Req->SetVerb(TEXT("GET"));
	Req->SetHeader(TEXT("Accept"), TEXT("application/json"));
	Req->SetHeader(TEXT("User-Agent"),
		FString::Printf(TEXT("AhmedFighter/%s"), *FApp::GetBuildVersion()));
	Req->SetTimeout(RequestTimeoutSeconds);
	return Req;
}

void UAhmedConfigSubsystem::RefreshFromServer()
{
	if (!bEnableRemoteBalance || BalanceApiUrl.IsEmpty())
	{
		UE_LOG(LogAhmedBalance, Log, TEXT("Refresh ignored: remote balance is off."));
		return;
	}
	// One in flight at a time. Queueing a second would only race the first to
	// apply, and the loser would overwrite the winner.
	if (bInFlight)
	{
		UE_LOG(LogAhmedBalance, Verbose, TEXT("Refresh ignored: a fetch is already in flight."));
		return;
	}
	RequestRevision();
}

void UAhmedConfigSubsystem::RequestRevision()
{
	bInFlight = true;
	TSharedPtr<IHttpRequest, ESPMode::ThreadSafe> Req = MakeRequest(TEXT("/v1/revision"));
	Req->OnProcessRequestComplete().BindUObject(this, &UAhmedConfigSubsystem::OnRevisionResponse);
	Req->ProcessRequest();
}

void UAhmedConfigSubsystem::OnRevisionResponse(FHttpRequestPtr, FHttpResponsePtr Res, bool bOk)
{
	if (!bOk || !Res.IsValid() || Res->GetResponseCode() != 200)
	{
		bInFlight = false;
		UE_LOG(LogAhmedBalance, Log,
			TEXT("Balance server unreachable; staying on the %s tables."),
			Source == EBalanceSource::Cached ? TEXT("cached") : TEXT("shipped"));
		return;
	}

	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Res->GetContentAsString());
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		bInFlight = false;
		UE_LOG(LogAhmedBalance, Warning, TEXT("Revision response was not JSON."));
		return;
	}

	const FString Remote = Root->GetStringField(TEXT("Revision"));
	if (Remote.IsEmpty())
	{
		bInFlight = false;
		UE_LOG(LogAhmedBalance, Warning, TEXT("Revision response carried no Revision."));
		return;
	}
	// The cheap call has done its job: nothing to download.
	if (Remote == Revision)
	{
		bInFlight = false;
		UE_LOG(LogAhmedBalance, Log, TEXT("Balance already current at revision %s."), *Revision);
		return;
	}

	UE_LOG(LogAhmedBalance, Log, TEXT("Balance %s -> %s; fetching."),
		Revision.IsEmpty() ? TEXT("(none)") : *Revision, *Remote);
	RequestConfig();
}

void UAhmedConfigSubsystem::RequestConfig()
{
	TSharedPtr<IHttpRequest, ESPMode::ThreadSafe> Req = MakeRequest(TEXT("/v1/config"));
	if (!Revision.IsEmpty())
	{
		Req->SetHeader(TEXT("If-None-Match"), FString::Printf(TEXT("\"%s\""), *Revision));
	}
	Req->OnProcessRequestComplete().BindUObject(this, &UAhmedConfigSubsystem::OnConfigResponse);
	Req->ProcessRequest();
}

void UAhmedConfigSubsystem::OnConfigResponse(FHttpRequestPtr, FHttpResponsePtr Res, bool bOk)
{
	bInFlight = false;

	if (!bOk || !Res.IsValid())
	{
		UE_LOG(LogAhmedBalance, Log, TEXT("Balance fetch failed; keeping what we have."));
		return;
	}
	if (Res->GetResponseCode() == 304)
	{
		UE_LOG(LogAhmedBalance, Log, TEXT("Balance unchanged (304)."));
		return;
	}
	if (Res->GetResponseCode() != 200)
	{
		UE_LOG(LogAhmedBalance, Warning, TEXT("Balance fetch returned %d."), Res->GetResponseCode());
		return;
	}
	if (Res->GetContentLength() > MaxPayloadBytes)
	{
		UE_LOG(LogAhmedBalance, Warning,
			TEXT("Balance payload is %d bytes, over the %d limit; refusing it."),
			Res->GetContentLength(), MaxPayloadBytes);
		return;
	}

	const FString Json = Res->GetContentAsString();
	FString Error;
	if (!ApplyPayload(Json, EBalanceSource::Remote, Error))
	{
		// Nothing has changed: ApplyPayload only swaps tables in once every
		// one of them has parsed.
		UE_LOG(LogAhmedBalance, Warning, TEXT("Balance payload rejected (%s)."), *Error);
		return;
	}

	WriteCache(Json);
	UE_LOG(LogAhmedBalance, Log, TEXT("Balance updated to revision %s."), *Revision);
	OnBalanceApplied.Broadcast(Source);
}

/* -------------------------------------------------------------- applying */

/**
 * Whole or nothing. Every table is parsed into a fresh UDataTable first, and
 * only if all of them succeed do they replace the live ones. Applying half a
 * payload would leave attacks tuned against a roster that never arrived, which
 * is a worse state than being out of date.
 */
bool UAhmedConfigSubsystem::ApplyPayload(const FString& Json, EBalanceSource NewSource, FString& OutError)
{
	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		OutError = TEXT("payload is not valid JSON");
		return false;
	}

	const FString NewRevision = Root->GetStringField(TEXT("Revision"));
	if (NewRevision.IsEmpty())
	{
		OutError = TEXT("payload carries no Revision");
		return false;
	}

	UDataTable* NewAttack  = nullptr;
	UDataTable* NewFighter = nullptr;
	UDataTable* NewTalent  = nullptr;
	UDataTable* NewUpgrade = nullptr;
	UDataTable* NewLevel   = nullptr;
	UDataTable* NewWeapon  = nullptr;
	UDataTable* NewStage   = nullptr;

	const TArray<TTuple<const TCHAR*, UScriptStruct*, UDataTable**, bool>> Specs =
	{
		{ TEXT("Attacks"),  FAttackDef::StaticStruct(),   &NewAttack,  true  },
		{ TEXT("Fighters"), FFighterDef::StaticStruct(),  &NewFighter, true  },
		{ TEXT("Talents"),  FTalentDef::StaticStruct(),   &NewTalent,  false },
		{ TEXT("Upgrades"), FUpgradeDef::StaticStruct(),  &NewUpgrade, false },
		{ TEXT("Levels"),   FLevelDef::StaticStruct(),    &NewLevel,   false },
		{ TEXT("Weapons"),  FWeaponDef::StaticStruct(),   &NewWeapon,  false },
		{ TEXT("Stages"),   FStageDef::StaticStruct(),    &NewStage,   false }
	};

	for (const auto& Spec : Specs)
	{
		const TArray<TSharedPtr<FJsonValue>>* Rows = nullptr;
		if (!Root->TryGetArrayField(Spec.Get<0>(), Rows) || !Rows)
		{
			if (Spec.Get<3>())
			{
				OutError = FString::Printf(TEXT("required table '%s' is missing"), Spec.Get<0>());
				return false;
			}
			continue;
		}

		// Back to a string so UDataTable can do the row-struct binding itself
		// rather than this file reimplementing property reflection.
		FString RowsJson;
		const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&RowsJson);
		FJsonSerializer::Serialize(*Rows, Writer);

		UDataTable* Table = NewObject<UDataTable>(this);
		Table->RowStruct = Spec.Get<1>();
		const TArray<FString> Problems = Table->CreateTableFromJSONString(RowsJson);
		if (Problems.Num() > 0)
		{
			OutError = FString::Printf(TEXT("table '%s': %s"),
				Spec.Get<0>(), *FString::Join(Problems, TEXT("; ")));
			return false;
		}
		if (Table->GetRowMap().Num() == 0)
		{
			OutError = FString::Printf(TEXT("table '%s' parsed to zero rows"), Spec.Get<0>());
			return false;
		}
		*Spec.Get<2>() = Table;
	}

	// Every table parsed. Swap them in together.
	AttackTable  = NewAttack;
	FighterTable = NewFighter;
	if (NewTalent)  { TalentTable  = NewTalent;  }
	if (NewUpgrade) { UpgradeTable = NewUpgrade; }
	if (NewLevel)   { LevelTable   = NewLevel;   }
	if (NewWeapon)  { WeaponTable  = NewWeapon;  }
	if (NewStage)   { StageTable   = NewStage;   }

	Revision = NewRevision;
	Source = NewSource;
	return true;
}
