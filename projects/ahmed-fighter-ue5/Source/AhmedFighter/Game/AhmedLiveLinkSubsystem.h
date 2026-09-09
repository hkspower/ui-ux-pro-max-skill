#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "AhmedLiveLinkSubsystem.generated.h"

class IWebSocket;

/**
 * The live link to the balance server.
 *
 * UAhmedConfigSubsystem pulls the tables at launch and whenever it is asked.
 * This is what asks it. It holds one WebSocket open to the server's /v1/live
 * and, when the server says the payload changed, calls RefreshFromServer --
 * so a number retuned in the browser project's panel and exported reaches a
 * running game in about a second, without a restart and without anyone
 * pressing anything in the editor.
 *
 * It is a convenience for development and for a live game, never a
 * dependency: with the link off, or the server gone, the config subsystem
 * behaves exactly as it did before this file existed. A dropped socket is
 * reconnected with a backoff that caps at a minute; nothing here ever blocks
 * a frame.
 *
 * Switches live in DefaultGame.ini under
 * [/Script/AhmedFighter.AhmedLiveLinkSubsystem].
 */
UCLASS(Config = Game)
class AHMEDFIGHTER_API UAhmedLiveLinkSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	UFUNCTION(BlueprintPure, Category = "Balance")
	bool IsConnected() const { return bConnected; }

	/** The revision the server last announced, or empty. */
	UFUNCTION(BlueprintPure, Category = "Balance")
	FString GetServerRevision() const { return ServerRevision; }

	/** Drop and reconnect now. Safe from a debug menu. */
	UFUNCTION(BlueprintCallable, Category = "Balance")
	void Reconnect();

protected:
	/** ws:// or wss:// address of the server's /v1/live. Empty disables the
	    link. Plain ws:// is refused by iOS at runtime; see Config/IOS. */
	UPROPERTY(Config, EditAnywhere, Category = "Balance")
	FString LiveLinkUrl;

	UPROPERTY(Config, EditAnywhere, Category = "Balance")
	bool bEnableLiveLink = false;

	/** First retry after this many seconds; doubles each time, capped below. */
	UPROPERTY(Config, EditAnywhere, Category = "Balance", meta = (ClampMin = "1.0"))
	float ReconnectSeconds = 2.f;

	UPROPERTY(Config, EditAnywhere, Category = "Balance", meta = (ClampMin = "5.0"))
	float ReconnectCapSeconds = 60.f;

private:
	void Connect();
	void ScheduleReconnect();
	void OnConnected();
	void OnConnectionError(const FString& Error);
	void OnClosed(int32 StatusCode, const FString& Reason, bool bWasClean);
	void OnMessage(const FString& Message);

	TSharedPtr<IWebSocket> Socket;
	FTimerHandle RetryTimer;
	float RetryDelay = 0.f;
	bool bConnected = false;
	bool bShuttingDown = false;
	FString ServerRevision;
};
