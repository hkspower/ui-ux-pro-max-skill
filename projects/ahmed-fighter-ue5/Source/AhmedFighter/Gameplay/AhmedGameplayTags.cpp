#include "Gameplay/AhmedGameplayTags.h"

/* One definition each. The string is what content and .ini files see; the
   C++ name is what the game says. Keep them in step -- an ability that tests
   a tag the content never applies fails silently, which is the one failure
   mode tags have. */
namespace AhmedTags
{
	UE_DEFINE_GAMEPLAY_TAG(Attack, "Ahmed.Attack");
	/** Any punch. A cracked wall asks for this rather than for a list of punches. */
	UE_DEFINE_GAMEPLAY_TAG(Attack_Box, "Ahmed.Attack.Box");
	UE_DEFINE_GAMEPLAY_TAG(Attack_Box_Jab, "Ahmed.Attack.Box.Jab");
	UE_DEFINE_GAMEPLAY_TAG(Attack_Box_Cross, "Ahmed.Attack.Box.Cross");
	UE_DEFINE_GAMEPLAY_TAG(Attack_Box_Hook, "Ahmed.Attack.Box.Hook");
	/** Any kick. A steel shutter asks for this. */
	UE_DEFINE_GAMEPLAY_TAG(Attack_Kick, "Ahmed.Attack.Kick");
	UE_DEFINE_GAMEPLAY_TAG(Attack_Kick_Roundhouse, "Ahmed.Attack.Kick.Roundhouse");
	UE_DEFINE_GAMEPLAY_TAG(Attack_Kick_Knee, "Ahmed.Attack.Kick.Knee");
	UE_DEFINE_GAMEPLAY_TAG(Attack_Rage, "Ahmed.Attack.Rage");
	/** HAWK FIST is lit and this strike carries fire. */
	UE_DEFINE_GAMEPLAY_TAG(Attack_Modifier_Burning, "Ahmed.Attack.Modifier.Burning");
	UE_DEFINE_GAMEPLAY_TAG(Attack_Modifier_Armed, "Ahmed.Attack.Modifier.Armed");
	UE_DEFINE_GAMEPLAY_TAG(Attack_Modifier_Heavy, "Ahmed.Attack.Modifier.Heavy");
	UE_DEFINE_GAMEPLAY_TAG(State_Attacking, "Ahmed.State.Attacking");
	UE_DEFINE_GAMEPLAY_TAG(State_Recovering, "Ahmed.State.Recovering");
	UE_DEFINE_GAMEPLAY_TAG(State_Blocking, "Ahmed.State.Blocking");
	UE_DEFINE_GAMEPLAY_TAG(State_ParryWindow, "Ahmed.State.ParryWindow");
	UE_DEFINE_GAMEPLAY_TAG(State_Dashing, "Ahmed.State.Dashing");
	UE_DEFINE_GAMEPLAY_TAG(State_Airborne, "Ahmed.State.Airborne");
	UE_DEFINE_GAMEPLAY_TAG(State_Climbing, "Ahmed.State.Climbing");
	UE_DEFINE_GAMEPLAY_TAG(State_HitStun, "Ahmed.State.HitStun");
	UE_DEFINE_GAMEPLAY_TAG(State_Downed, "Ahmed.State.Downed");
	UE_DEFINE_GAMEPLAY_TAG(State_Dead, "Ahmed.State.Dead");
	UE_DEFINE_GAMEPLAY_TAG(State_Invulnerable, "Ahmed.State.Invulnerable");
	/** Loose parent: anything under it means "cannot start something new". */
	UE_DEFINE_GAMEPLAY_TAG(State_Busy, "Ahmed.State.Busy");
	UE_DEFINE_GAMEPLAY_TAG(Talent, "Ahmed.Talent");
	UE_DEFINE_GAMEPLAY_TAG(Talent_Vault, "Ahmed.Talent.Vault");
	UE_DEFINE_GAMEPLAY_TAG(Talent_DashLeap, "Ahmed.Talent.DashLeap");
	UE_DEFINE_GAMEPLAY_TAG(Talent_PowerKick, "Ahmed.Talent.PowerKick");
	UE_DEFINE_GAMEPLAY_TAG(Talent_Haymaker, "Ahmed.Talent.Haymaker");
	UE_DEFINE_GAMEPLAY_TAG(Talent_HawkFist, "Ahmed.Talent.HawkFist");
	/** A real jump. Gets over things, and opens the fight upward. */
	UE_DEFINE_GAMEPLAY_TAG(Talent_Jump, "Ahmed.Talent.Jump");
	/** Pull up onto any ledge, not only the ones VAULT was placed for. */
	UE_DEFINE_GAMEPLAY_TAG(Talent_Climb, "Ahmed.Talent.Climb");
	UE_DEFINE_GAMEPLAY_TAG(Event_HitLanded, "Ahmed.Event.HitLanded");
	UE_DEFINE_GAMEPLAY_TAG(Event_HitReceived, "Ahmed.Event.HitReceived");
	UE_DEFINE_GAMEPLAY_TAG(Event_Blocked, "Ahmed.Event.Blocked");
	UE_DEFINE_GAMEPLAY_TAG(Event_Parried, "Ahmed.Event.Parried");
	UE_DEFINE_GAMEPLAY_TAG(Event_Knockdown, "Ahmed.Event.Knockdown");
	UE_DEFINE_GAMEPLAY_TAG(Event_Defeated, "Ahmed.Event.Defeated");
	UE_DEFINE_GAMEPLAY_TAG(Event_GateStruck, "Ahmed.Event.GateStruck");
	UE_DEFINE_GAMEPLAY_TAG(Event_LedgeGrabbed, "Ahmed.Event.LedgeGrabbed");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Hit_Light, "Ahmed.Cue.Hit.Light");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Hit_Heavy, "Ahmed.Cue.Hit.Heavy");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Hit_Knockdown, "Ahmed.Cue.Hit.Knockdown");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Hit_Burning, "Ahmed.Cue.Hit.Burning");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Block, "Ahmed.Cue.Block");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Parry, "Ahmed.Cue.Parry");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Whoosh_Light, "Ahmed.Cue.Whoosh.Light");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Whoosh_Heavy, "Ahmed.Cue.Whoosh.Heavy");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Rage, "Ahmed.Cue.Rage");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Dash, "Ahmed.Cue.Dash");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Jump, "Ahmed.Cue.Jump");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Land, "Ahmed.Cue.Land");
	UE_DEFINE_GAMEPLAY_TAG(Cue_Climb, "Ahmed.Cue.Climb");
	/** Damage carried on an effect, set by the ability that made it. */
	UE_DEFINE_GAMEPLAY_TAG(Data_Damage, "Ahmed.Data.Damage");
	UE_DEFINE_GAMEPLAY_TAG(Data_Knockback, "Ahmed.Data.Knockback");
	UE_DEFINE_GAMEPLAY_TAG(Data_StaminaCost, "Ahmed.Data.StaminaCost");
	UE_DEFINE_GAMEPLAY_TAG(Data_ManaCost, "Ahmed.Data.ManaCost");
	UE_DEFINE_GAMEPLAY_TAG(Cooldown_Dash, "Ahmed.Cooldown.Dash");
	UE_DEFINE_GAMEPLAY_TAG(Cooldown_Rage, "Ahmed.Cooldown.Rage");
	UE_DEFINE_GAMEPLAY_TAG(Cooldown_Climb, "Ahmed.Cooldown.Climb");
}
