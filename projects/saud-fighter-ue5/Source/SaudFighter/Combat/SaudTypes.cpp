#include "Combat/SaudTypes.h"

#include "Gameplay/SaudGameplayTags.h"

/*
 * One table, read both ways. A talent that exists in EAbility but has no tag
 * comes back as an invalid tag rather than as a wrong one, and the log says
 * so -- which is the failure you want, because the alternative is a route
 * that silently never opens.
 */
namespace
{
	struct FTalentPair { EAbility Ability; const FGameplayTag& Tag; };

	static const TArray<FTalentPair>& Pairs()
	{
		static const TArray<FTalentPair> Table = {
			{ EAbility::Vault,     SaudTags::Talent_Vault },
			{ EAbility::DashLeap,  SaudTags::Talent_DashLeap },
			{ EAbility::PowerKick, SaudTags::Talent_PowerKick },
			{ EAbility::Haymaker,  SaudTags::Talent_Haymaker },
			{ EAbility::HawkFist,  SaudTags::Talent_HawkFist },
			{ EAbility::Jump,      SaudTags::Talent_Jump },
			{ EAbility::Climb,     SaudTags::Talent_Climb }
		};
		return Table;
	}
}

namespace SaudTalents
{
	FGameplayTag TagFor(EAbility Ability)
	{
		if (Ability == EAbility::None)
		{
			return FGameplayTag();
		}
		for (const FTalentPair& P : Pairs())
		{
			if (P.Ability == Ability)
			{
				return P.Tag;
			}
		}
		UE_LOG(LogTemp, Warning,
			TEXT("[Saud] EAbility %d has no gameplay tag. Add it to SaudTypes.cpp."),
			static_cast<int32>(Ability));
		return FGameplayTag();
	}

	EAbility AbilityFor(const FGameplayTag& Tag)
	{
		for (const FTalentPair& P : Pairs())
		{
			if (P.Tag == Tag)
			{
				return P.Ability;
			}
		}
		return EAbility::None;
	}
}
