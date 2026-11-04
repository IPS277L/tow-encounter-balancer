"""Explicit NPC outnumbering replacement for the admitted PC Melee scene."""
from towr.domain.npc_roster_models import NpcDefinition
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.test_models import DiceModifier


CRAVEN_OPPORTUNIST_RULE_ID = 'RULE-PROFILE-TALABEC-004:craven-opportunist'


def pc_npc_outnumbering_modifier(definition: NpcDefinition) -> DiceModifier:
    """Caller has established Melee, current numerical superiority and GM approval."""
    validate_pc_book_npc_definition(definition)
    if definition.id == 'pc-book-npc:brigand_axe':
        return DiceModifier(CRAVEN_OPPORTUNIST_RULE_ID,2)
    return DiceModifier('RULE-COMBAT-007:outnumbering',1)
