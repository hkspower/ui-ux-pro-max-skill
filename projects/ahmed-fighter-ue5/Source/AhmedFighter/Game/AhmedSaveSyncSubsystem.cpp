#include "Game/AhmedSaveSyncSubsystem.h"

#include "Game/AhmedGameInstance.h"
#include "GenericPlatform/GenericPlatformMisc.h"
#include "HttpModule.h"
#include "Interfaces/IHttpResponse.h"
#include "JsonObjectConverter.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

DEFINE_LOG_CATEGORY_STATIC(LogAhmedSaveSync, Log, All);

/* ------------------------------------------------------------ the shape */

bool UAhmedSaveSyncSubsystem::EncodeProgress(const FAhmedProgress& In, FString& OutJson)
{
	TSharedPtr<FJsonObject> Progress = FJsonObjectConverter::UStructToJsonObject(In);
	if (!Progress.IsValid()) { return false; }

	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetNumberField(TEXT("SchemaVersion"), 1);
	Root->SetObjectField(TEXT("Progress"), Progress);

	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutJson);
	return FJsonSerializer::Serialize(Root, Writer);
}

bool UAhmedSaveSyncSubsystem::DecodeProgress(const FString& Json, FAhmedProgress& Out, FString& OutError)
{
	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		OutError = TEXT("not JSON");
		return false;
	}
	if (!Root->HasTypedField<EJson::Number>(TEXT("SchemaVersion")))
	{
		OutError = TEXT("no SchemaVersion");
		return false;
	}
	const TSharedPtr<FJsonObject>* Progress = nullptr;
	if (!Root->TryGetObjectField(TEXT("Progress"), Progress) || !Progress || !Progress->IsValid())
	{
		OutError = TEXT("no Progress");
		return false;
	}
	// Into a fresh struct, so a body that half-parses does not leave the
	// caller's profile half-overwritten.
	FAhmedProgress Parsed;
	if (!FJsonObjectConverter::JsonObjectToUStruct(Progress->ToSharedRef(), &Parsed, 0, 0))
	{
		OutError = TEXT("Progress does not fit FAhmedProgress");
		return false;
	}
	Out = Parsed;
	return true;
}

/* ------------------------------------------------------------- the calls */

FString UAhmedSaveSyncSubsystem::GetSaveId() const
{
	if (!SaveId.IsEmpty()) { return SaveId; }
	// The device id is the fallback: one profile per install, no login.
	FString Id = FPlatformMisc::GetDeviceId();
	if (Id.IsEmpty()) { Id = FPlatformMisc::GetLoginId(); }
	// The server takes [A-Za-z0-9_-]{1,64} and nothing else.
	FString Clean;
	for (TCHAR C : Id)
	{
		if (FChar::IsAlnum(C) || C == TEXT('_') || C == TEXT('-')) { Clean.AppendChar(C); }
	}
	return Clean.Left(64);
}

bool UAhmedSaveSyncSubsystem::Ready(FString& OutWhy) const
{
	if (!bEnableSaveSync || SaveApiUrl.IsEmpty()) { OutWhy = TEXT("save sync is off"); return false; }
	if (bInFlight) { OutWhy = TEXT("a sync is already in flight"); return false; }
	if (GetSaveId().IsEmpty()) { OutWhy = TEXT("no save id"); return false; }
	return true;
}

TSharedPtr<IHttpRequest, ESPMode::ThreadSafe> UAhmedSaveSyncSubsystem::MakeRequest(const FString& Verb) const
{
	FString Base = SaveApiUrl;
	Base.RemoveFromEnd(TEXT("/"));
	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
	Req->SetURL(Base + TEXT("/v1/saves/") + GetSaveId());
	Req->SetVerb(Verb);
	Req->SetHeader(TEXT("Accept"), TEXT("application/json"));
	Req->SetHeader(TEXT("User-Agent"), FString::Printf(TEXT("AhmedFighter/%s"), *FApp::GetBuildVersion()));
	if (!SaveToken.IsEmpty())
	{
		Req->SetHeader(TEXT("Authorization"), TEXT("Bearer ") + SaveToken);
	}
	Req->SetTimeout(RequestTimeoutSeconds);
	return Req;
}

void UAhmedSaveSyncSubsystem::Upload()
{
	FString Why;
	if (!Ready(Why)) { Finish(false, Why); return; }
	UAhmedGameInstance* GI = Cast<UAhmedGameInstance>(GetGameInstance());
	if (!GI) { Finish(false, TEXT("no game instance")); return; }

	FString Body;
	if (!EncodeProgress(GI->GetProgress(), Body)) { Finish(false, TEXT("could not encode the profile")); return; }

	bInFlight = true;
	TSharedPtr<IHttpRequest, ESPMode::ThreadSafe> Req = MakeRequest(TEXT("PUT"));
	Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
	Req->SetContentAsString(Body);
	Req->OnProcessRequestComplete().BindUObject(this, &UAhmedSaveSyncSubsystem::OnUploadResponse);
	Req->ProcessRequest();
}

void UAhmedSaveSyncSubsystem::OnUploadResponse(FHttpRequestPtr, FHttpResponsePtr Res, bool bOk)
{
	bInFlight = false;
	if (!bOk || !Res.IsValid()) { Finish(false, TEXT("server unreachable")); return; }
	const int32 Code = Res->GetResponseCode();
	if (Code == 200 || Code == 201) { Finish(true, FString::Printf(TEXT("uploaded (%d)"), Code)); return; }
	if (Code == 401) { Finish(false, TEXT("server wants a token")); return; }
	Finish(false, FString::Printf(TEXT("upload refused (%d)"), Code));
}

void UAhmedSaveSyncSubsystem::Download()
{
	FString Why;
	if (!Ready(Why)) { Finish(false, Why); return; }
	bInFlight = true;
	TSharedPtr<IHttpRequest, ESPMode::ThreadSafe> Req = MakeRequest(TEXT("GET"));
	Req->OnProcessRequestComplete().BindUObject(this, &UAhmedSaveSyncSubsystem::OnDownloadResponse);
	Req->ProcessRequest();
}

void UAhmedSaveSyncSubsystem::OnDownloadResponse(FHttpRequestPtr, FHttpResponsePtr Res, bool bOk)
{
	bInFlight = false;
	if (!bOk || !Res.IsValid()) { Finish(false, TEXT("server unreachable")); return; }
	const int32 Code = Res->GetResponseCode();
	if (Code == 404) { Finish(false, TEXT("no save on the server")); return; }
	if (Code == 401) { Finish(false, TEXT("server wants a token")); return; }
	if (Code != 200) { Finish(false, FString::Printf(TEXT("download refused (%d)"), Code)); return; }

	FAhmedProgress Parsed; FString Error;
	if (!DecodeProgress(Res->GetContentAsString(), Parsed, Error))
	{
		Finish(false, TEXT("server save rejected: ") + Error);
		return;
	}
	UAhmedGameInstance* GI = Cast<UAhmedGameInstance>(GetGameInstance());
	if (!GI) { Finish(false, TEXT("no game instance")); return; }
	// Only now, with the whole thing parsed, does the local profile change.
	GI->GetMutableProgress() = Parsed;
	GI->SaveProgress();
	Finish(true, TEXT("downloaded and saved"));
}

void UAhmedSaveSyncSubsystem::Finish(bool bOk, const FString& Message)
{
	if (bOk) { UE_LOG(LogAhmedSaveSync, Log, TEXT("%s"), *Message); }
	else     { UE_LOG(LogAhmedSaveSync, Warning, TEXT("%s"), *Message); }
	OnSynced.Broadcast(bOk, Message);
}
