#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "AbilitySystemInterface.h"
#include "Combat/SaudTypes.h"
#include "FighterBase.generated.h"

class UDataTable;
class USaudAbilitySystemComponent;
class USaudAttributeSet;
class USaudMotionComponent;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnFighterDamaged, float, NewHealth, const FHitResultData&, Hit);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnFighterDefeated, AFighterBase*, Fighter);

/**
 * Everything both the player and the enemies share: the attack state machine,
 * health, stamina, blocking, knockdown and hit resolution.
 *
 * Hits are resolved by an explicit facing/reach/depth test against the other
 * fighters rather than by physics overlaps. That is deliberate — the browser
 * original did the same, the results are frame-deterministic, and a beat-'em-up
 * wants forgiving, readable hitboxes rather than physically exact ones.
 */
UCLASS(Abstract)
class SAUDFIGHTER_API AFighterBase : public ACharacter, public IAbilitySystemInterface
{
	GENERATED_BODY()

public:
	AFighterBase();

	virtual void Tick(float DeltaSeconds) override;
	virtual void BeginPlay() override;

	// ---------------------------------------------------------------- combat

	/** Begins an attack if the current state allows it. Returns false if refused. */
	UFUNCTION(BlueprintCallable, Category = "Combat")
	bool StartAttack(FName AttackRow);

	/** Applies a landed blow. Called by the attacker, not the victim. */
	UFUNCTION(BlueprintCallable, Category = "Combat")
	FHitResultData ReceiveHit(AFighterBase* Attacker, const FAttackDef& Attack);

	UFUNCTION(BlueprintPure, Category = "Combat")
	bool IsBusy() const;

	UFUNCTION(BlueprintPure, Category = "Combat")
	bool IsAlive() const { return State != EFighterState::Dead; }

	UFUNCTION(BlueprintPure, Category = "Combat")
	float GetHealthFraction() const { return MaxHealth > 0.f ? Health / MaxHealth : 0.f; }

	UFUNCTION(BlueprintPure, Category = "Fighter")
	float GetHealth() const { return Health; }

	UFUNCTION(BlueprintPure, Category = "Fighter")
	float GetStamina() const { return Stamina; }

	/** Used on arrival from another area: travel carries condition across. */
	UFUNCTION(BlueprintCallable, Category = "Fighter")
	void SetCondition(float NewHealth, float NewStamina)
	{
		Health  = FMath::Clamp(NewHealth,  1.f, MaxHealth);
		Stamina = FMath::Clamp(NewStamina, 0.f, MaxStamina);
	}

	/**
	 * Which way this fighter is looking, as a unit vector on the ground.
	 *
	 * It was a sign on X until 2026-09-16, because the playfield was a strip
	 * and there were only two directions to face. Every reach, lunge,
	 * knockback and guard test below is measured along this now; anything
	 * that reaches for X to mean "forward" is a bug left from the corridor.
	 */
	UFUNCTION(BlueprintPure, Category = "Combat")
	FVector GetFacing() const { return Facing; }

	UFUNCTION(BlueprintCallable, Category = "Combat")
	void FaceTowards(const FVector& WorldLocation);

	/** Fire from the walk cycle's anim notify, one per contact. The cue's
	    pitch drift keeps a loop from sounding like one. */
	UFUNCTION(BlueprintCallable, Category = "Audio")
	void PlayFootstep();

	// ------------------------------------------------------- ability system
	/*
	 * The gameplay layer. Everything a fighter can DO is an ability now, and
	 * everything a fighter IS is an attribute; what remains here is the body
	 * -- where it stands, which way it faces, and what it looks like doing
	 * something. The hooks below are the whole surface the abilities need, so
	 * an ability never reaches into the character for anything else.
	 */

	virtual UAbilitySystemComponent* GetAbilitySystemComponent() const override;

	UFUNCTION(BlueprintPure, Category = "Abilities")
	USaudAbilitySystemComponent* GetSaudASC() const { return AbilitySystem; }

	UFUNCTION(BlueprintPure, Category = "Abilities")
	const USaudAttributeSet* GetAttributes() const { return Attributes; }

	/** Turn to whichever opponent is nearest, before committing to a strike. */
	UFUNCTION(BlueprintCallable, Category = "Combat")
	void FaceNearestOpponent();

	/** Everyone this fighter is allowed to hit. Subclasses narrow it. */
	UFUNCTION(BlueprintCallable, Category = "Combat")
	void GatherOpponents(TArray<AFighterBase*>& OutTargets) const;

	/** Take the blow's push, and go down if it was heavy enough. Called by
	    the attacking ability; the damage itself went through attributes. */
	UFUNCTION(BlueprintCallable, Category = "Combat")
	void ReceiveKnockback(const FVector& Impulse, bool bKnockdown);

	UFUNCTION(BlueprintCallable, Category = "Combat")
	void SpendStamina(float Amount);

	/** Which way the player is asking to go. Enemies override with their AI
	    heading, so a dash works the same for both. */
	UFUNCTION(BlueprintPure, Category = "Movement")
	virtual FVector GetIntendedMoveDirection() const;

	/** Start and finish a ledge climb. The ability owns the timing; the
	    character owns the body, which is the only thing that should be
	    interpolating a position. */
	UFUNCTION(BlueprintCallable, Category = "Movement")
	void BeginLedgeClimb(const FVector& Ledge, float Duration);

	UFUNCTION(BlueprintCallable, Category = "Movement")
	void EndLedgeClimb(const FVector& Ledge);

	/** Advances a climb in progress. Called from Tick; does nothing otherwise. */
	void Tick_Climb(float DeltaSeconds);

protected:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Abilities")
	TObjectPtr<USaudAbilitySystemComponent> AbilitySystem = nullptr;

	UPROPERTY()
	TObjectPtr<USaudAttributeSet> Attributes = nullptr;

	/** Ledge climb in progress: where from, where to, and how far through. */
	FVector ClimbFrom = FVector::ZeroVector;
	FVector ClimbTo = FVector::ZeroVector;
	float ClimbElapsed = -1.f;
	float ClimbDuration = 0.f;

public:

	/** Damage this fighter deals, before the victim's defences. */
	virtual float GetOutgoingDamageMultiplier(const FAttackDef& Attack) const;

	/** What a blocked hit costs this fighter, as a multiplier on the
	    stamina (bPush false) or the knockback (bPush true). 1 for everyone;
	    Saud's IRON ARM upgrade lowers it. */
	virtual float GetBlockCostMultiplier(bool bPush) const { return 1.f; }

	// ---------------------------------------------------------------- events

	UPROPERTY(BlueprintAssignable, Category = "Combat")
	FOnFighterDamaged OnDamaged;

	UPROPERTY(BlueprintAssignable, Category = "Combat")
	FOnFighterDefeated OnDefeated;

	// ------------------------------------------------------------- accessors

	UPROPERTY(BlueprintReadOnly, Category = "Combat")
	EFighterState State = EFighterState::Idle;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Combat")
	float MaxHealth = 100.f;

	UPROPERTY(BlueprintReadOnly, Category = "Combat")
	float Health = 100.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Combat")
	float MaxStamina = 100.f;

	UPROPERTY(BlueprintReadOnly, Category = "Combat")
	float Stamina = 100.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Combat")
	float PowerMultiplier = 1.f;

	UPROPERTY(BlueprintReadOnly, Category = "Combat")
	bool bBlocking = false;

	/** Bosses shrug off most knockdowns so they cannot be stunlocked. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Combat")
	bool bResistsKnockdown = false;

	/** Table the fighter's move names resolve against. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Combat")
	TObjectPtr<UDataTable> AttackTable = nullptr;

	// ---------------------------------------------------------------- motion

	/** Whose clips this fighter plays: A_<MotionSet>_* in Content/Animation.
	    The DT_Fighters row for an enemy (AWaveDirector sets it); anything
	    without clips of its own plays Saud's. See USaudMotionComponent. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Motion")
	FName MotionSet = TEXT("Saud");

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Motion")
	TObjectPtr<USaudMotionComponent> Motion = nullptr;

	/** Whether the blow that put this fighter in Hit was heavy: it picks
	    Hit_Heavy over Hit_Light. */
	bool bLastHitHeavy = false;

	/** Seconds left of getting up after Down -- the same 0.6 s as the
	    invulnerability, and the length of A_Saud_GetUp. */
	float GetUpRemaining = 0.f;

	/** Moves on every start of something that must play from its first
	    frame even when the clip is already the one playing: a second jab, a
	    second hit, a second dash. */
	uint32 MotionSerial = 0;

	FName GetCurrentAttackRow() const { return CurrentAttackRow; }

protected:
	/** Advances startup -> active -> recovery and fires the hitbox once. */
	void TickAttack(float DeltaSeconds);
	void TickTimers(float DeltaSeconds);

	/** Sweeps for valid targets during the active window. */
	virtual void ResolveAttackHits(const FAttackDef& Attack);

	/** Everything this fighter is allowed to hit. Overridden per side. */
	virtual void GatherTargets(TArray<AFighterBase*>& OutTargets) const;

	/** Gives subclasses a place to react without overriding ReceiveHit wholesale. */
	virtual void OnHitLanded(AFighterBase* Victim, const FHitResultData& Hit) {}
	virtual void OnKnockedDown() {}
	virtual void OnDeath();

	const FAttackDef* FindAttack(FName Row) const;

	/** Cosmetic hooks so Blueprints can add VFX and audio without C++ changes. */
	UFUNCTION(BlueprintImplementableEvent, Category = "Combat", meta = (DisplayName = "On Attack Started"))
	void BP_OnAttackStarted(FName AttackRow);

	UFUNCTION(BlueprintImplementableEvent, Category = "Combat", meta = (DisplayName = "On Hit Received"))
	void BP_OnHitReceived(const FHitResultData& Hit);

	UFUNCTION(BlueprintImplementableEvent, Category = "Combat", meta = (DisplayName = "On Defeated"))
	void BP_OnDefeated();

	// --------------------------------------------------------- runtime state

	FName CurrentAttackRow = NAME_None;
	const FAttackDef* CurrentAttack = nullptr;
	float AttackElapsed = 0.f;
	bool bAttackHitFired = false;

	/** The swing's sound and when in the attack to start it. The clip is
	    begun early by its own lead so the swish peaks on the first active
	    frame; a swing that is interrupted before then never sounds, because
	    it never happened. */
	FName SwingCue = NAME_None;
	float SwingAt = 0.f;
	bool bSwingFired = true;
	void FireSwingCue();

	/** Targets already struck by the current swing, so multi-hit never double-dips. */
	TArray<TWeakObjectPtr<AFighterBase>> HitThisSwing;

	float HitStunRemaining = 0.f;
	float DownRemaining = 0.f;
	float InvulnerableRemaining = 0.f;
	FVector Facing = FVector(1.f, 0.f, 0.f);

	/** Set the frame block is pressed; a hit inside this window is a parry. */
	float ParryWindowRemaining = 0.f;

	/** The victim's white flash on a clean hit (the browser's f.flash), in
	    game time, so it holds through the freeze as the browser's does. It
	    drives the body's HitFlash material parameter; FlashShown is what was
	    last sent, so the parameter is set only when it changes. */
	float FlashRemaining = 0.f;
	float FlashShown = 0.f;
};
