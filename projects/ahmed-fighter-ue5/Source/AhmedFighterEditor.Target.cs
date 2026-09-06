using UnrealBuildTool;

public class AhmedFighterEditorTarget : TargetRules
{
	public AhmedFighterEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.V5;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_4;
		ExtraModuleNames.Add("AhmedFighter");
	}
}
