using UnrealBuildTool;

public class AhmedFighter : ModuleRules
{
	public AhmedFighter(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"EnhancedInput",
			"UMG",
			// The gameplay layer. GAS is three modules and all three are
			// required together: the system, the tags it dispatches on, and the
			// task framework abilities run their timing on.
			"GameplayAbilities",
			"GameplayTags",
			"GameplayTasks",
			"MotionWarping",
			"Niagara"
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"Slate",
			"SlateCore",
			// Remote balance: the config subsystem fetches the tables the
			// browser project exports. The game runs without it -- see
			// Game/AhmedConfigSubsystem.h -- but the modules are not optional
			// once the file is in the module.
			"HTTP",
			"Json",
			"JsonUtilities",
			// The live link: one socket to the server's /v1/live, so a
			// retune reaches a running game. Game/AhmedLiveLinkSubsystem.h.
			"WebSockets"
		});

		// Lets sources include as "Combat/FighterBase.h" rather than by relative path.
		PublicIncludePaths.Add(ModuleDirectory);
	}
}
