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
			"SlateCore"
		});

		// Lets sources include as "Combat/FighterBase.h" rather than by relative path.
		PublicIncludePaths.Add(ModuleDirectory);
	}
}
