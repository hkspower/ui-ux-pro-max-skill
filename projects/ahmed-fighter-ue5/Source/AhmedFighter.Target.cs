using UnrealBuildTool;

public class AhmedFighterTarget : TargetRules
{
	public AhmedFighterTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.V5;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_4;
		ExtraModuleNames.Add("AhmedFighter");
	}
}
