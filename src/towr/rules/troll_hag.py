from __future__ import annotations

from towr.domain.injury_models import ProfileInjuryState
from towr.domain.test_models import DiceModifier


MOTHER_KNOWS_BEST_RULE_ID = "RULE-NPC-024:mother-knows-best"
TROLL_HAG_WIZARD_LEVEL = 2


def mother_knows_best_casting_modifier(
    state: ProfileInjuryState,
) -> DiceModifier | None:
    if not isinstance(state, ProfileInjuryState):
        raise TypeError("state must be a ProfileInjuryState")
    if state.wounds > 0:
        return None
    return DiceModifier(
        rule_id=MOTHER_KNOWS_BEST_RULE_ID,
        amount=1,
    )
