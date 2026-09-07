#pragma once

#include "NativeGameplayTags.h"

/**
 * The game's whole vocabulary, in one file.
 *
 * Tags replace the enums the port started with, and the reason is not fashion:
 * an enum can only ever answer "which one", while a tag answers "is this any
 * kind of X" — `Ahmed.Attack.Box` matches a jab, a cross and a hook without
 * naming them, so a cracked wall can ask for a punch rather than a list of
 * punches, and adding a fourth punch does not mean editing the wall.
 *
 * They are declared natively rather than in an .ini so that a typo is a
 * compile error and every reference is findable. The .ini stays for tags
 * designers add to content.
 *
 * The shape:
 *
 *   Ahmed.Attack.*     what a strike IS. Its family is its parent.
 *   Ahmed.State.*      what a fighter is doing. Abilities block on these.
 *   Ahmed.Talent.*     what a fighter has been granted.
 *   Ahmed.Event.*      a moment, sent through the ability system.
 *   Ahmed.Cue.*        a moment made visible and audible.
 *   Ahmed.Data.*       a number carried on an effect (SetByCaller).
 *   Ahmed.Cooldown.*   what an ability is waiting on.
 */
namespace AhmedTags
{
	/* ---- attacks: the family is the parent, which is the point ---------- */
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Box);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Box_Jab);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Box_Cross);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Box_Hook);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Kick);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Kick_Roundhouse);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Kick_Knee);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Rage);
	/** Set on a strike while HAWK FIST is lit. Punches only; kicks stay cold. */
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Modifier_Burning);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Modifier_Armed);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Attack_Modifier_Heavy);

	/* ---- state: what stops what ----------------------------------------- */
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Attacking);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Recovering);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Blocking);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_ParryWindow);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Dashing);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Airborne);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Climbing);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_HitStun);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Downed);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Dead);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Invulnerable);
	/** Everything that means "you cannot start something new right now". */
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Busy);

	/* ---- talents: found in the world, never bought ----------------------- */
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Talent);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Talent_Vault);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Talent_DashLeap);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Talent_PowerKick);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Talent_Haymaker);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Talent_HawkFist);
	/** New: a real jump, and a climb up anything with a ledge. */
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Talent_Jump);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Talent_Climb);

	/* ---- events: moments, dispatched rather than called ------------------ */
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Event_HitLanded);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Event_HitReceived);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Event_Blocked);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Event_Parried);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Event_Knockdown);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Event_Defeated);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Event_GateStruck);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Event_LedgeGrabbed);

	/* ---- cues: what a moment looks and sounds like ----------------------- */
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Hit_Light);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Hit_Heavy);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Hit_Knockdown);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Hit_Burning);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Block);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Parry);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Whoosh_Light);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Whoosh_Heavy);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Rage);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Dash);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Jump);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Land);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cue_Climb);

	/* ---- data carried on an effect, by name ------------------------------ */
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Data_Damage);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Data_Knockback);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Data_StaminaCost);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Data_ManaCost);

	/* ---- cooldowns ------------------------------------------------------- */
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cooldown_Dash);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cooldown_Rage);
	AHMEDFIGHTER_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cooldown_Climb);
}
