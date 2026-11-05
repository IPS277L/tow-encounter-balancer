"""Explicit printed NPC attack modifiers for the admitted PC Melee scene."""
from towr.domain.attack_models import DamageModifier
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.npc_roster_models import NpcDefinition
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.test_models import DiceModifier


CRAVEN_OPPORTUNIST_RULE_ID = 'RULE-PROFILE-TALABEC-004:craven-opportunist'
GOR_PRIMAL_RAGE_RULE_ID = 'RULE-PROFILE-BEASTMEN-002:primal-rage'
GOR_DUAL_AXES_RULE_ID = 'RULE-PROFILE-BEASTMEN-002:dual-axes-damage'


def pc_npc_outnumbering_modifier(definition: NpcDefinition) -> DiceModifier:
    """Caller has established Melee, current numerical superiority and GM approval."""
    validate_pc_book_npc_definition(definition)
    if definition.id == 'pc-book-npc:brigand_axe':
        return DiceModifier(CRAVEN_OPPORTUNIST_RULE_ID,2)
    return DiceModifier('RULE-COMBAT-007:outnumbering',1)


def pc_npc_allows_give_ground(definition: NpcDefinition) -> bool:
    """The Giant Wolf and Pinning Claws' actual victims cannot choose Give Ground."""
    validate_pc_book_npc_definition(definition)
    return definition.id not in ('pc-book-npc:giant_wolf','pc-book-npc:chaos_warhound',
        'pc-book-npc:white_wolf_clamping_jaws')


def pc_npc_attack_modifiers(definition: NpcDefinition,conditions: ConditionState) -> tuple[DiceModifier,...]:
    validate_pc_book_npc_definition(definition)
    if definition.id=='pc-book-npc:gor_dual_axes' and conditions.has(Condition.STAGGERED):
        return (DiceModifier(GOR_PRIMAL_RAGE_RULE_ID,1),)
    return ()


def pc_npc_damage_modifiers(definition: NpcDefinition) -> tuple[DamageModifier,...]:
    validate_pc_book_npc_definition(definition)
    if definition.id=='pc-book-npc:gor_dual_axes':
        return (DamageModifier(GOR_DUAL_AXES_RULE_ID,1),)
    return ()
