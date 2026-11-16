"""Typed supply and injury evidence for GM90's Defenceless Recover exception."""
from dataclasses import dataclass, replace

from towr.domain.injury_models import CharacterInjuryState
from towr.domain.potion_models import ConsumableItem, ConsumableKind, heal_potion_wound


@dataclass(frozen=True, slots=True)
class HealingPotionRecoverSource:
    actor_id: str
    item: ConsumableItem
    injury: CharacterInjuryState
    wound_sequence: int

    def __post_init__(self) -> None:
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise ValueError('Healing Potion needs its consuming actor')
        if type(self.item) is not ConsumableItem or self.item.kind is not ConsumableKind.HEALING:
            raise TypeError('Healing Recover requires actual typed Healing Potion supply')
        replace(self.item)
        # Validate eligibility; the native owner supplies independent Condition
        # causes when it applies the actual healing after standard benefits.
        heal_potion_wound(self.injury, self.wound_sequence)
