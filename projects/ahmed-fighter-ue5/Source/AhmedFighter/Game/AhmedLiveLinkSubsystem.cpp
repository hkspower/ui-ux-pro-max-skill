#include "Game/AhmedLiveLinkSubsystem.h"

#include "Game/AhmedConfigSubsystem.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "IWebSocket.h"
#include "WebSocketsModule.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "TimerManager.h"

DEFINE_LOG_CATEGORY_STATIC(LogAhmedLiveLink, Log, All);

void UAhmedLiveLinkSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	// The config subsystem must exist before this one asks it for anything.
	Collection.InitializeDependency<UAhmedConfigSubsystem>();

	if (!bEnableLiveLink || LiveLinkUrl.IsEmpty())
	{
		UE_LOG(LogAhmedLiveLink, Log, TEXT("Live link off."));
		return;
	}
	RetryDelay = ReconnectSeconds;
	Connect();
}

void UAhmedLiveLinkSubsystem::Deinitialize()
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

void UAhmedLiveLinkSubsystem::Connect()
{
	if (bShuttingDown) { return; }
	if (!FModuleManager::Get().IsModuleLoaded("WebSockets"))
	{
		FModuleManager::Get().LoadModule("WebSockets");
	}

	Socket = FWebSocketsModule::Get().CreateWebSocket(LiveLinkUrl, TEXT(""));
	Socket->OnConnected().AddUObject(this, &UAhmedLiveLinkSubsystem::OnConnected);
	Socket->OnConnectionError().AddUObject(this, &UAhmedLiveLinkSubsystem::OnConnectionError);
	Socket->OnClosed().AddUObject(this, &UAhmedLiveLinkSubsystem::OnClosed);
	Socket->OnMessage().AddUObject(this, &UAhmedLiveLinkSubsystem::OnMessage);
	Socket->Connect();
}

void UAhmedLiveLinkSubsystem::Reconnect()
{
	if (Socket.IsValid() && Socket->IsConnected()) { Socket->Close(); }
	RetryDelay = ReconnectSeconds;
	Connect();
}

/* Doubling, capped. A server that is down for an hour should not be hit
   thirty times a minute by every client, and a server that comes back
   should be found within a minute. */
void UAhmedLiveLinkSubsystem::ScheduleReconnect()
{
	if (bShuttingDown) { return; }
	UWorld* World = GetWorld();
	if (!World) { return; }
	World->GetTimerManager().SetTimer(RetryTimer, this, &UAhmedLiveLinkSubsystem::Connect,
		RetryDelay, false);
	RetryDelay = FMath::Min(RetryDelay * 2.f, ReconnectCapSeconds);
}

void UAhmedLiveLinkSubsystem::OnConnected()
{
	bConnected = true;
	RetryDelay = ReconnectSeconds;
	UE_LOG(LogAhmedLiveLink, Log, TEXT("Live link up: %s"), *LiveLinkUrl);
}

void UAhmedLiveLinkSubsystem::OnConnectionError(const FString& Error)
{
	bConnected = false;
	UE_LOG(LogAhmedLiveLink, Log, TEXT("Live link could not connect (%s); retrying in %.0fs."),
		*Error, RetryDelay);
	ScheduleReconnect();
}

void UAhmedLiveLinkSubsystem::OnClosed(int32 StatusCode, const FString& Reason, bool bWasClean)
{
	bConnected = false;
	if (bShuttingDown) { return; }
	UE_LOG(LogAhmedLiveLink, Log, TEXT("Live link closed (%d %s); retrying in %.0fs."),
		StatusCode, *Reason, RetryDelay);
	ScheduleReconnect();
}

/* The server sends {"Type":"hello"|"revision"|"pong","Revision":"…"}. Only
   the revision matters, and only whether it differs from what the config
   subsystem holds -- the fetch itself, the validation and the whole-or-nothing
   apply are that subsystem's, unchanged. This file never touches a table. */
void UAhmedLiveLinkSubsystem::OnMessage(const FString& Message)
{
	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Message);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		UE_LOG(LogAhmedLiveLink, Verbose, TEXT("Live link message was not JSON."));
		return;
	}
	const FString Type = Root->GetStringField(TEXT("Type"));
	const FString Revision = Root->GetStringField(TEXT("Revision"));
	if (Revision.IsEmpty()) { return; }
	ServerRevision = Revision;

	if (Type != TEXT("hello") && Type != TEXT("revision")) { return; }

	UAhmedConfigSubsystem* Config = GetGameInstance()
		? GetGameInstance()->GetSubsystem<UAhmedConfigSubsystem>() : nullptr;
	if (!Config) { return; }
	if (Config->GetRevision() == Revision)
	{
		UE_LOG(LogAhmedLiveLink, Verbose, TEXT("Server at %s; already current."), *Revision);
		return;
	}
	UE_LOG(LogAhmedLiveLink, Log, TEXT("Server moved to %s (we hold %s); refreshing."),
		*Revision, Config->GetRevision().IsEmpty() ? TEXT("(none)") : *Config->GetRevision());
	Config->RefreshFromServer();
}
