#include "Gameplay/AhmedFightStyle.h"

/**
 * The bands, as fractions of the style's own preferred range.
 *
 * They are relative rather than absolute because "close" means something
 * different to a lanky kickboxer than to a squat grappler, and an absolute
 * threshold would leave the tall fighter with no mid range at all.
 */
ERangeBand UAhmedFightStyleData::BandFor(float Distance) const
{
	const float R = FMath::Max(40.f, PreferredRange);
	if (Distance <= R * 0.55f) { return ERangeBand::Close; }
	if (Distance <= R * 1.05f) { return ERangeBand::Mid; }
	if (Distance <= R * 1.85f) { return ERangeBand::Long; }
	return ERangeBand::Out;
}

const FStyleStrike* UAhmedFightStyleData::ChooseStrike(ERangeBand Band,
	const TArray<FStyleStrike>& Extra) const
{
	auto Legal = [Band](const FStyleStrike& S)
	{
		return !S.AttackRow.IsNone() && S.Weight > 0.f && S.Bands.Contains(Band);
	};

	// Weights are normalised across what is legal *now* rather than authored
	// to sum to one, so removing a strike from a style does not mean
	// re-tuning every other strike in it.
	float Total = 0.f;
	for (const FStyleStrike& S : Strikes) { if (Legal(S)) { Total += S.Weight; } }
	for (const FStyleStrike& S : Extra)   { if (Legal(S)) { Total += S.Weight; } }

	if (Total <= 0.f)
	{
		// Nothing to throw from here. Not a failure -- it is the whole reason
		// a boxer walks forward instead of swinging at air.
		return nullptr;
	}

	float Roll = FMath::FRandRange(0.f, Total);
	for (const FStyleStrike& S : Strikes)
	{
		if (Legal(S) && (Roll -= S.Weight) <= 0.f) { return &S; }
	}
	for (const FStyleStrike& S : Extra)
	{
		if (Legal(S) && (Roll -= S.Weight) <= 0.f) { return &S; }
	}
	return nullptr;
}
