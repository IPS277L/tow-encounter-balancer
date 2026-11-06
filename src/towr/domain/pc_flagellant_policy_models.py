"""Explicit Feel No Pain and self-Recover choices for canonical Flagellants."""
from dataclasses import dataclass, replace
from enum import Enum

from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition


FLAGELLANT_DEFINITION_IDS = ('pc-book-npc:flagellant_flails', 'pc-book-npc:flagellant_hooks_chains')
FEEL_NO_PAIN_RULE_ID = 'RULE-PROFILE-IMPERIAL-006:feel-no-pain'
FLAGELLANT_RECOVER_RULE_ID = 'RULE-PROFILE-IMPERIAL-006:feel-no-pain-recover'
FLAILS_STAGGERED_RULE_ID = 'RULE-PROFILE-IMPERIAL-006:staggered-flails'
UNBREAKABLE_RULE_ID = 'RULE-PROFILE-IMPERIAL-006:unbreakable'


class PcFeelNoPainPolicy(str, Enum):
    DECLINE = 'decline'
    WOUND_AT_ZERO = 'wound_at_zero'


@dataclass(frozen=True, slots=True)
class PcFlagellantPolicy:
    actor_id: str
    feel_no_pain: PcFeelNoPainPolicy
    recover_when_wounded: bool

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('Flagellant policy requires an exact actor ID')
        if type(self.feel_no_pain) is not PcFeelNoPainPolicy:
            raise TypeError('Feel No Pain must be its exact policy enum')
        if type(self.recover_when_wounded) is not bool:
            raise TypeError('Flagellant recovery must be an exact bool')


def validate_pc_flagellant_policies(source) -> None:
    if type(source.npc_flagellant_policies) is not tuple:
        raise TypeError('Flagellant policies require an exact ordered tuple')
    actors = []
    for policy in source.npc_flagellant_policies:
        if type(policy) is not PcFlagellantPolicy:
            raise TypeError('Flagellant policy must retain its exact type')
        replace(policy)
        if policy.actor_id not in source.enemy_activation_order:
            raise ValueError('Flagellant policy requires an opposition actor')
        definition = source.enemy(policy.actor_id).definition
        validate_pc_book_npc_definition(definition)
        if definition.id not in FLAGELLANT_DEFINITION_IDS:
            raise ValueError('Flagellant policy requires a canonical Flagellant loadout')
        actors.append(policy.actor_id)
    if len(set(actors)) != len(actors):
        raise ValueError('each Flagellant must have at most one policy')
