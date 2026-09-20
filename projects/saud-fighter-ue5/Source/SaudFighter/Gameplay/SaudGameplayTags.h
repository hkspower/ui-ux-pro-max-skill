#pragma once

#include "NativeGameplayTags.h"

/**
 * The game's whole vocabulary, in one file.
 *
 * Tags replace the enums the port started with, and the reason is not fashion:
 * an enum can only ever answer "which one", while a tag answers "is this any
 * kind of X" — `Saud.Attack.Box` matches a jab, a cross and a hook without
 * naming them, so a cracked wall can ask for a punch rather than a list of
 * punches, and adding a fourth punch does not mean editing the wall.
 *
 * They are declared natively rather than in an .ini so that a typo is a
 * compile error and every reference is findable. The .ini stays for tags
 * designers add to content.
 *
 * The shape:
 *
 *   Saud.Attack.*     what a strike IS. Its family is its parent.
 *   Saud.State.*      what a fighter is doing. Abilities block on these.
 *   Saud.Talent.*     what a fighter has been granted.
 *   Saud.Event.*      a moment, sent through the ability system.
 *   Saud.Cue.*        a moment made visible and audible.
 *   Saud.Data.*       a number carried on an effect (SetByCaller).
 *   Saud.Cooldown.*   what an ability is waiting on.
 */
namespace SaudTags
{
	/* ---- attacks: the family is the parent, which is the point ---------- */
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Box);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Box_Jab);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Box_Cross);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Box_Hook);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Kick);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Kick_Roundhouse);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Kick_Knee);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Rage);
	/** Set on a strike while HAWK FIST is lit. Punches only; kicks stay cold. */
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Modifier_Burning);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Modifier_Armed);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Modifier_Heavy);

	/* ---- state: what stops what ----------------------------------------- */
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Attacking);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Recovering);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Blocking);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_ParryWindow);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Dashing);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Airborne);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Climbing);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_HitStun);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Downed);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Dead);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Invulnerable);
	/** Everything that means "you cannot start something new right now". */
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Busy);

	/* ---- talents: found in the world, never bought ----------------------- */
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Talent);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Talent_Vault);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Talent_DashLeap);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Talent_PowerKick);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Talent_Haymaker);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Talent_HawkFist);
	/** New: a real jump, and a climb up anything with a ledge. */
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Talent_Jump);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Talent_Climb);

	/* ---- events: moments, dispatched rather than called ------------------ */
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Event_HitLanded);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Event_HitReceived);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Event_Blocked);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Event_Parried);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Event_Knockdown);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Event_Defeated);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Event_GateStruck);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Event_LedgeGrabbed);

	/* ---- cues: what a moment looks and sounds like ----------------------- */
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Hit_Light);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Hit_Heavy);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Hit_Knockdown);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Hit_Burning);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Block);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Parry);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Whoosh_Light);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Whoosh_Heavy);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Rage);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Dash);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Jump);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Land);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Climb);

	/* ---- data carried on an effect, by name ------------------------------ */
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Data_Damage);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Data_Knockback);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Data_StaminaCost);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Data_ManaCost);

	/* ---- cooldowns ------------------------------------------------------- */
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cooldown_Dash);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cooldown_Rage);
	SAUDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cooldown_Climb);
}
