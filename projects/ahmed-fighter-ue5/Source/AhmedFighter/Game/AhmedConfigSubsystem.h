#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Interfaces/IHttpRequest.h"
#include "AhmedConfigSubsystem.generated.h"

class UDataTable;

/**
 * Remote balance.
 *
 * Every number the game runs on ships inside the build, in Content/Data,
 * exported from the browser project by Tools/export/export.mjs. The game is
 * complete and correct with nothing but those tables, and that is the point:
 * this subsystem is an optimisation on the release cycle, never a dependency.
 *
 * On launch it does three things, in this order, and the first one is what
 * the player actually plays:
 *
 *   1. Point at the baked tables. The game is ready. No network, no wait.
 *   2. If a cached payload from a previous run is present and its revision is
 *      newer than the baked one, apply it. Still no network.
 *   3. Ask the server for its revision. If it differs, fetch the payload,
 *      validate it, cache it, and apply. If anything at all goes wrong --
 *      offline, timeout, malformed, a table that fails to parse -- the game
 *      keeps whatever it already had and says so in the log.
 *
 * A payload is applied whole or not at all. Half-applying a balance change is
 * worse than not applying it, because the halves were tuned against each
 * other.
 *
 * Endpoint and switches live in DefaultGame.ini under
 * [/Script/AhmedFighter.AhmedConfigSubsystem].
 */

/** Where the numbers in play came from. Shown on the settings screen so a
    tester can tell a stale build from a stale server. */
UENUM(BlueprintType)
enum class EBalanceSource : uint8
{
	Baked		UMETA(DisplayName = "Shipped with the build"),
	Cached		UMETA(DisplayName = "Downloaded on a previous run"),
	Remote		UMETA(DisplayName = "Downloaded just now")
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnBalanceApplied, EBalanceSource, Source);

UCLASS(Config = Game)
class AHMEDFIGHTER_API UAhmedConfigSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	/** Fires whenever a payload is applied, including the baked one at boot. */
	UPROPERTY(BlueprintAssignable, Category = "Balance")
	FOnBalanceApplied OnBalanceApplied;

	/** Ask the server again. Safe to call from a debug menu at any time; a
	    second call while one is in flight is ignored rather than queued. */
	UFUNCTION(BlueprintCallable, Category = "Balance")
	void RefreshFromServer();

	UFUNCTION(BlueprintPure, Category = "Balance")
	EBalanceSource GetSource() const { return Source; }

	/** Sixteen hex characters identifying exactly which numbers are in play. */
	UFUNCTION(BlueprintPure, Category = "Balance")
	FString GetRevision() const { return Revision; }

	UFUNCTION(BlueprintPure, Category = "Balance")
	bool IsFetchInFlight() const { return bInFlight; }

	/* ---- the tables everything else reads ------------------------------- */
	UFUNCTION(BlueprintPure, Category = "Balance")
	UDataTable* GetAttackTable() const { return AttackTable; }

	UFUNCTION(BlueprintPure, Category = "Balance")
	UDataTable* GetFighterTable() const { return FighterTable; }

	UFUNCTION(BlueprintPure, Category = "Balance")
	UDataTable* GetStageTable() const { return StageTable; }

	UFUNCTION(BlueprintPure, Category = "Balance")
	UDataTable* GetTalentTable() const { return TalentTable; }

	UFUNCTION(BlueprintPure, Category = "Balance")
	UDataTable* GetUpgradeTable() const { return UpgradeTable; }

	UFUNCTION(BlueprintPure, Category = "Balance")
	UDataTable* GetLevelTable() const { return LevelTable; }

	UFUNCTION(BlueprintPure, Category = "Balance")
	UDataTable* GetWeaponTable() const { return WeaponTable; }

protected:
	/* ---- settings, from DefaultGame.ini --------------------------------- */

	/** Base address, no trailing slash. Empty disables remote balance
	    entirely, which is the right setting for a store build until the
	    endpoint is real. HTTPS only on iOS -- see Config/IOS/IOSEngine.ini. */
	UPROPERTY(Config, EditAnywhere, Category = "Balance")
	FString BalanceApiUrl;

	UPROPERTY(Config, EditAnywhere, Category = "Balance")
	bool bEnableRemoteBalance = false;

	/** Seconds before a fetch is abandoned. Deliberately short: the game is
	    already playable, so a slow answer is worth less than a fast start. */
	UPROPERTY(Config, EditAnywhere, Category = "Balance", meta = (ClampMin = "1.0"))
	float RequestTimeoutSeconds = 6.f;

	/** Refuse a payload larger than this. A balance file is tens of kilobytes;
	    anything far past that is a mistake or an attack, and either way it
	    should not reach the JSON parser. */
	UPROPERTY(Config, EditAnywhere, Category = "Balance", meta = (ClampMin = "1024"))
	int32 MaxPayloadBytes = 2 * 1024 * 1024;

	/* ---- the baked tables, set in DefaultGame.ini ------------------------ */
	UPROPERTY(Config, EditAnywhere, Category = "Balance")
	TSoftObjectPtr<UDataTable> BakedAttackTable;

	UPROPERTY(Config, EditAnywhere, Category = "Balance")
	TSoftObjectPtr<UDataTable> BakedFighterTable;

	UPROPERTY(Config, EditAnywhere, Category = "Balance")
	TSoftObjectPtr<UDataTable> BakedStageTable;

	UPROPERTY(Config, EditAnywhere, Category = "Balance")
	TSoftObjectPtr<UDataTable> BakedTalentTable;

	UPROPERTY(Config, EditAnywhere, Category = "Balance")
	TSoftObjectPtr<UDataTable> BakedUpgradeTable;

	UPROPERTY(Config, EditAnywhere, Category = "Balance")
	TSoftObjectPtr<UDataTable> BakedLevelTable;

	UPROPERTY(Config, EditAnywhere, Category = "Balance")
	TSoftObjectPtr<UDataTable> BakedWeaponTable;

private:
	void UseBakedTables();
	void TryCachedPayload();
	void RequestRevision();
	void RequestConfig();

	void OnRevisionResponse(FHttpRequestPtr Req, FHttpResponsePtr Res, bool bOk);
	void OnConfigResponse(FHttpRequestPtr Req, FHttpResponsePtr Res, bool bOk);

	/** Parse and swap in a whole payload. Returns false and changes nothing if
	    any part of it fails, which is the only safe way to fail here. */
	bool ApplyPayload(const FString& Json, EBalanceSource NewSource, FString& OutError);

	FString CachePath() const;
	void WriteCache(const FString& Json) const;
	TSharedPtr<IHttpRequest, ESPMode::ThreadSafe> MakeRequest(const FString& Path) const;

	UPROPERTY() TObjectPtr<UDataTable> AttackTable;
	UPROPERTY() TObjectPtr<UDataTable> FighterTable;
	UPROPERTY() TObjectPtr<UDataTable> StageTable;
	UPROPERTY() TObjectPtr<UDataTable> TalentTable;
	UPROPERTY() TObjectPtr<UDataTable> UpgradeTable;
	UPROPERTY() TObjectPtr<UDataTable> LevelTable;
	UPROPERTY() TObjectPtr<UDataTable> WeaponTable;

	EBalanceSource Source = EBalanceSource::Baked;
	FString Revision;
	bool bInFlight = false;
};
