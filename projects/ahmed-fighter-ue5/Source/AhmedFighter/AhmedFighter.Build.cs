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
			"UMG"
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
			"JsonUtilities"
		});

		// Lets sources include as "Combat/FighterBase.h" rather than by relative path.
		PublicIncludePaths.Add(ModuleDirectory);
	}
}
