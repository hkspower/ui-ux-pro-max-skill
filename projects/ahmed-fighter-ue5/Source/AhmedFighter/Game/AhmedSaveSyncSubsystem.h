#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Interfaces/IHttpRequest.h"
#include "Game/AhmedSaveGame.h"
#include "AhmedSaveSyncSubsystem.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnSaveSynced, bool, bOk, FString, Message);

/**
 * The profile, on the server.
 *
 * The game's save is UAhmedGameInstance's FAhmedProgress in a local slot,
 * and that stays the truth: this uploads a copy to the balance server's
 * /v1/saves/{id} and can fetch it back, so a profile follows a player to
 * another machine or survives a reinstall. Nothing happens on its own --
 * Upload and Download are called from a menu or a Blueprint, and a failure
 * leaves the local save exactly as it was.
 *
 * The body is FAhmedProgress as JSON under the same two keys the server
 * checks for (SchemaVersion, Progress), so a save the server accepted is a
 * save this build can read back.
 *
 * Switches live in DefaultGame.ini under
 * [/Script/AhmedFighter.AhmedSaveSyncSubsystem].
 */
UCLASS(Config = Game)
class AHMEDFIGHTER_API UAhmedSaveSyncSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	/** Send the current profile up. Fires OnSynced when the server answers. */
	UFUNCTION(BlueprintCallable, Category = "Save")
	void Upload();

	/** Fetch the server's copy and, if it parses, make it the local profile
	    and write the slot. Fires OnSynced either way. */
	UFUNCTION(BlueprintCallable, Category = "Save")
	void Download();

	UPROPERTY(BlueprintAssignable, Category = "Save")
	FOnSaveSynced OnSynced;

	UFUNCTION(BlueprintPure, Category = "Save")
	bool IsInFlight() const { return bInFlight; }

	/** What the save is stored under. Set from a login, a code the player
	    types, or left to the device id. */
	UFUNCTION(BlueprintCallable, Category = "Save")
	void SetSaveId(const FString& Id) { SaveId = Id; }

	UFUNCTION(BlueprintPure, Category = "Save")
	FString GetSaveId() const;

	/** The profile as the server stores it. Public so it can be checked
	    without a network: a JSON round trip that loses a field loses a run. */
	static bool EncodeProgress(const FAhmedProgress& In, FString& OutJson);
	static bool DecodeProgress(const FString& Json, FAhmedProgress& Out, FString& OutError);

protected:
	/** Base address of the API, no trailing slash. Empty disables sync.
	    Usually the same server as UAhmedConfigSubsystem::BalanceApiUrl. */
	UPROPERTY(Config, EditAnywhere, Category = "Save")
	FString SaveApiUrl;

	UPROPERTY(Config, EditAnywhere, Category = "Save")
	bool bEnableSaveSync = false;

	/** Sent as `Authorization: Bearer`. The server refuses saves without it
	    once SAVE_TOKEN is set on it, which it must be outside development. */
	UPROPERTY(Config, EditAnywhere, Category = "Save")
	FString SaveToken;

	UPROPERTY(Config, EditAnywhere, Category = "Save", meta = (ClampMin = "1.0"))
	float RequestTimeoutSeconds = 8.f;

private:
	bool Ready(FString& OutWhy) const;
	TSharedPtr<IHttpRequest, ESPMode::ThreadSafe> MakeRequest(const FString& Verb) const;
	void OnUploadResponse(FHttpRequestPtr Req, FHttpResponsePtr Res, bool bOk);
	void OnDownloadResponse(FHttpRequestPtr Req, FHttpResponsePtr Res, bool bOk);
	void Finish(bool bOk, const FString& Message);

	FString SaveId;
	bool bInFlight = false;
};
