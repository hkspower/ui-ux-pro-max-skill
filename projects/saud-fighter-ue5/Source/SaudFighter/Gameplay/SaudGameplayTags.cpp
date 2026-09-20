#include "Gameplay/SaudGameplayTags.h"

/* One definition each. The string is what content and .ini files see; the
   C++ name is what the game says. Keep them in step -- an ability that tests
   a tag the content never applies fails silently, which is the one failure
   mode tags have. */
namespace SaudTags
{
	UE_DEFINE_GAMEPLAY_TAG(Attack, "Saud.Attack");
	/** Any punch. A cracked wall asks for this rather than for a list of punches. */
	UE_DEFINE_GAMEPLAY_TAG(Attack_Box, "Saud.Attack.Box");
	UE_DEFINE_GAMEPLAY_TAG(Attack_Box_Jab, "Saud.Attack.Box.Jab");
	UE_DEFINE_GAMEPLAY_TAG(Attack_Box_Cross, "Saud.Attack.Box.Cross");
	UE_DEFINE_GAMEPLAY_TAG(Attack_Box_Hook, "Saud.Attack.Box.Hook");
	/** Any kick. A steel shutter asks for this. */
	UE_DEFINE_GAMEPLAY_TAG(Attack_Kick, "Saud.Attack.Kick");
	UE_DEFINE_GAMEPLAY_TAG(Attack_Kick_Roundhouse, "Saud.Attack.Kick.Roundhouse");
	UE_DEFINE_GAMEPLAY_TAG(Attack_Kick_Knee, "Saud.Attack.Kick.Knee");
	UE_DEFINE_GAMEPLAY_TAG(Attack_Rage, "Saud.Attack.Rage");
	/** HAWK FIST is lit and this strike carries fire. */
	UE_DEFINE_GAMEPLAY_TAG(Attack_Modifier_Burning, "Saud.Attack.Modifier.Burning");
	UE_DEFINE_GAMEPLAY_TAG(Attack_Modifier_Armed, "Saud.Attack.Modifier.Armed");
	UE_DEFINE_GAMEPLAY_TAG(Attack_Modifier_Heavy, "Saud.Attack.Modifier.Heavy");
	UE_DEFINE_GAMEPLAY_TAG(State_Attacking, "Saud.State.Attacking");
	UE_DEFINE_GAMEPLAY_TAG(State_Recovering, "Saud.State.Recovering");
	UE_DEFINE_GAMEPLAY_TAG(State_Blocking, "Saud.State.Blocking");
	UE_DEFINE_GAMEPLAY_TAG(State_ParryWindow, "Saud.State.ParryWindow");
	UE_DEFINE_GAMEPLAY_TAG(State_Dashing, "Saud.State.Dashing");
	UE_DEFINE_GAMEPLAY_TAG(State_Airborne, "Saud.State.Airborne");
	UE_DEFINE_GAMEPLAY_TAG(State_Climbing, "Saud.State.Climbing");
	UE_DEFINE_GAMEPLAY_TAG(State_HitStun, "Saud.State.HitStun");
	UE_DEFINE_GAMEPLAY_TAG(State_Downed, "Saud.State.Downed");
	UE_DEFINE_GAMEPLAY_TAG(State_Dead, "Saud.State.Dead");
	UE_DEFINE_GAMEPLAY_TAG(State_Invulnerable, "Saud.State.Invulnerable");
	/** Loose parent: anything under it means "cannot start something new". */
	UE_DEFINE_GAMEPLAY_TAG(State_Busy, "Saud.State.Busy");
	UE_DEFINE_GAMEPLAY_TAG(Talent, "Saud.Talent");
	UE_DEFINE_GAMEPLAY_TAG(Talent_Vault, "Saud.Talent.Vault");
	UE_DEFINE_GAMEPLAY_TAG(Talent_DashLeap, "Saud.Talent.DashLeap");
	UE_DEFINE_GAMEPLAY_TAG(Talent_PowerKick, "Saud.Talent.PowerKick");
	UE_DEFINE_GAMEPLAY_TAG(Talent_Haymaker, "Saud.Talent.Haymaker");
	UE_DEFINE_GAMEPLAY_TAG(Talent_HawkFist, "Saud.Talent.HawkFist");
	/** A real jump. Gets over things, and opens the fight upward. */
	UE_DEFINE_GAMEPLAY_TAG(Talent_Jump, "Saud.Talent.Jump");
	/** Pull up onto any ledge, not only the ones VAULT was placed for. */
	UE_DEFINE_GAMEPLAY_TAG(Talent_Climb, "Saud.Talent.Climb");
	UE_DEFINE_GAMEPLAY_TAG(Event_HitLanded, "Saud.Event.HitLanded");
	UE_DEFINE_GAMEPLAY_TAG(Event_HitReceived, "Saud.Event.HitReceived");
	UE_DEFINE_GAMEPLAY_TAG(Event_Blocked, "Saud.Event.Blocked");
	UE_DEFINE_GAMEPLAY_TAG(Event_Parried, "Saud.Event.Parried");
	UE_DEFINE_GAMEPLAY_TAG(Event_Knockdown, "Saud.Event.Knockdown");
	UE_DEFINE_GAMEPLAY_TAG(Event_Defeated, "Saud.Event.Defeated");
	UE_DEFINE_GAMEPLAY_TAG(Event_GateStruck, "Saud.Event.GateStruck");
	UE_DEFINE_GAMEPLAY_TAG(Event_LedgeGrabbed, "Saud.Event.LedgeGrabbed");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Hit_Light, "Saud.Cue.Hit.Light");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Hit_Heavy, "Saud.Cue.Hit.Heavy");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Hit_Knockdown, "Saud.Cue.Hit.Knockdown");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Hit_Burning, "Saud.Cue.Hit.Burning");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Block, "Saud.Cue.Block");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Parry, "Saud.Cue.Parry");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Whoosh_Light, "Saud.Cue.Whoosh.Light");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Whoosh_Heavy, "Saud.Cue.Whoosh.Heavy");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Rage, "Saud.Cue.Rage");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Dash, "Saud.Cue.Dash");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Jump, "Saud.Cue.Jump");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Land, "Saud.Cue.Land");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Climb, "Saud.Cue.Climb");
	/** Damage carried on an effect, set by the ability that made it. */
	UE_DEFINE_GAMEPLAY_TAG(Data_Damage, "Saud.Data.Damage");
	UE_DEFINE_GAMEPLAY_TAG(Data_Knockback, "Saud.Data.Knockback");
	UE_DEFINE_GAMEPLAY_TAG(Data_StaminaCost, "Saud.Data.StaminaCost");
	UE_DEFINE_GAMEPLAY_TAG(Data_ManaCost, "Saud.Data.ManaCost");
	UE_DEFINE_GAMEPLAY_TAG(Cooldown_Dash, "Saud.Cooldown.Dash");
	UE_DEFINE_GAMEPLAY_TAG(Cooldown_Rage, "Saud.Cooldown.Rage");
	UE_DEFINE_GAMEPLAY_TAG(Cooldown_Climb, "Saud.Cooldown.Climb");
}
