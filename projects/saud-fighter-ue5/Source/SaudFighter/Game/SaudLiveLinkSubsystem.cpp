#include "Game/SaudLiveLinkSubsystem.h"

#include "Game/SaudConfigSubsystem.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "IWebSocket.h"
#include "WebSocketsModule.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "TimerManager.h"

DEFINE_LOG_CATEGORY_STATIC(LogSaudLiveLink, Log, All);

void USaudLiveLinkSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	// The config subsystem must exist before this one asks it for anything.
	Collection.InitializeDependency<USaudConfigSubsystem>();

	if (!bEnableLiveLink || LiveLinkUrl.IsEmpty())
	{
		UE_LOG(LogSaudLiveLink, Log, TEXT("Live link off."));
		return;
	}
	RetryDelay = ReconnectSeconds;
	Connect();
}

void USaudLiveLinkSubsystem::Deinitialize()
{
	bShuttingDown = true;
	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().ClearTimer(RetryTimer);
	}
	if (Socket.IsValid())
	{
		if (Socket->IsConnected()) { Socket->Close(); }
		Socket.Reset();
	}
	Super::Deinitialize();
}

void USaudLiveLinkSubsystem::Connect()
{
	if (bShuttingDown) { return; }
	if (!FModuleManager::Get().IsModuleLoaded("WebSockets"))
	{
		FModuleManager::Get().LoadModule("WebSockets");
	}

	Socket = FWebSocketsModule::Get().CreateWebSocket(LiveLinkUrl, TEXT(""));
	Socket->OnConnected().AddUObject(this, &USaudLiveLinkSubsystem::OnConnected);
	Socket->OnConnectionError().AddUObject(this, &USaudLiveLinkSubsystem::OnConnectionError);
	Socket->OnClosed().AddUObject(this, &USaudLiveLinkSubsystem::OnClosed);
	Socket->OnMessage().AddUObject(this, &USaudLiveLinkSubsystem::OnMessage);
	Socket->Connect();
}

void USaudLiveLinkSubsystem::Reconnect()
{
	if (Socket.IsValid() && Socket->IsConnected()) { Socket->Close(); }
	RetryDelay = ReconnectSeconds;
	Connect();
}

/* Doubling, capped. A server that is down for an hour should not be hit
   thirty times a minute by every client, and a server that comes back
   should be found within a minute. */
void USaudLiveLinkSubsystem::ScheduleReconnect()
{
	if (bShuttingDown) { return; }
	UWorld* World = GetWorld();
	if (!World) { return; }
	World->GetTimerManager().SetTimer(RetryTimer, this, &USaudLiveLinkSubsystem::Connect,
		RetryDelay, false);
	RetryDelay = FMath::Min(RetryDelay * 2.f, ReconnectCapSeconds);
}

void USaudLiveLinkSubsystem::OnConnected()
{
	bConnected = true;
	RetryDelay = ReconnectSeconds;
	UE_LOG(LogSaudLiveLink, Log, TEXT("Live link up: %s"), *LiveLinkUrl);
}

void USaudLiveLinkSubsystem::OnConnectionError(const FString& Error)
{
	bConnected = false;
	UE_LOG(LogSaudLiveLink, Log, TEXT("Live link could not connect (%s); retrying in %.0fs."),
		*Error, RetryDelay);
	ScheduleReconnect();
}

void USaudLiveLinkSubsystem::OnClosed(int32 StatusCode, const FString& Reason, bool bWasClean)
{
	bConnected = false;
	if (bShuttingDown) { return; }
	UE_LOG(LogSaudLiveLink, Log, TEXT("Live link closed (%d %s); retrying in %.0fs."),
		StatusCode, *Reason, RetryDelay);
	ScheduleReconnect();
}

/* The server sends {"Type":"hello"|"revision"|"pong","Revision":"…"}. Only
   the revision matters, and only whether it differs from what the config
   subsystem holds -- the fetch itself, the validation and the whole-or-nothing
   apply are that subsystem's, unchanged. This file never touches a table. */
void USaudLiveLinkSubsystem::OnMessage(const FString& Message)
{
	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Message);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		UE_LOG(LogSaudLiveLink, Verbose, TEXT("Live link message was not JSON."));
		return;
	}
	const FString Type = Root->GetStringField(TEXT("Type"));
	const FString Revision = Root->GetStringField(TEXT("Revision"));
	if (Revision.IsEmpty()) { return; }
	ServerRevision = Revision;

	if (Type != TEXT("hello") && Type != TEXT("revision")) { return; }

	USaudConfigSubsystem* Config = GetGameInstance()
		? GetGameInstance()->GetSubsystem<USaudConfigSubsystem>() : nullptr;
	if (!Config) { return; }
	if (Config->GetRevision() == Revision)
	{
		UE_LOG(LogSaudLiveLink, Verbose, TEXT("Server at %s; already current."), *Revision);
		return;
	}
	UE_LOG(LogSaudLiveLink, Log, TEXT("Server moved to %s (we hold %s); refreshing."),
		*Revision, Config->GetRevision().IsEmpty() ? TEXT("(none)") : *Config->GetRevision());
	Config->RefreshFromServer();
}
