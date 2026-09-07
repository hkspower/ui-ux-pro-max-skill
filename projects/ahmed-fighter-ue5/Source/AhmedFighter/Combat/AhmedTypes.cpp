#include "Combat/AhmedTypes.h"

#include "Gameplay/AhmedGameplayTags.h"

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
			{ EAbility::Vault,     AhmedTags::Talent_Vault },
			{ EAbility::DashLeap,  AhmedTags::Talent_DashLeap },
			{ EAbility::PowerKick, AhmedTags::Talent_PowerKick },
			{ EAbility::Haymaker,  AhmedTags::Talent_Haymaker },
			{ EAbility::HawkFist,  AhmedTags::Talent_HawkFist },
			{ EAbility::Jump,      AhmedTags::Talent_Jump },
			{ EAbility::Climb,     AhmedTags::Talent_Climb }
		};
		return Table;
	}
}

namespace AhmedTalents
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
			TEXT("[Ahmed] EAbility %d has no gameplay tag. Add it to AhmedTypes.cpp."),
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
