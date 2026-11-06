"""Explicit printed NPC attack modifiers for the admitted PC Melee scene."""
from towr.domain.attack_models import DamageModifier,DamageProfile
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.npc_roster_models import NpcDefinition
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.injury_models import MinionStaggerDefeatSpec,CharacterInjuryState,WoundDiceModifier
from towr.domain.test_models import DiceModifier


CRAVEN_OPPORTUNIST_RULE_ID = 'RULE-PROFILE-TALABEC-004:craven-opportunist'
GOR_PRIMAL_RAGE_RULE_ID = 'RULE-PROFILE-BEASTMEN-002:primal-rage'
GOR_DUAL_AXES_RULE_ID = 'RULE-PROFILE-BEASTMEN-002:dual-axes-damage'
UNGOR_PRIMAL_SPITE_RULE_ID = 'RULE-PROFILE-BEASTMEN-001:primal-spite'
GOBLIN_DIRTY_COWARD_RULE_ID = 'RULE-PROFILE-GREENSKIN-001:dirty-coward'
RAZORGOR_WOUNDED_MELEE_RULE_ID = 'RULE-PROFILE-CREATURE-009:wounded-melee'
MINOTAUR_WOUNDED_MELEE_RULE_ID = 'RULE-PROFILE-BEASTMEN-005:wounded-melee'
MINOTAUR_DUAL_AXES_RULE_ID = 'RULE-PROFILE-BEASTMEN-005:dual-axes-damage'
RAZORGOR_DEVOUR_RULE_ID = 'RULE-PROFILE-CREATURE-009:devour-the-fallen'
MINOTAUR_DEVOUR_RULE_ID = 'RULE-PROFILE-BEASTMEN-005:devour-the-fallen'


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


def pc_npc_allows_enemy_higher_ground(definition: NpcDefinition) -> bool:
    validate_pc_book_npc_definition(definition)
    return definition.id!='pc-book-npc:dwarf_miner_pickaxe'


def pc_npc_attack_modifiers(definition: NpcDefinition,conditions: ConditionState,
        *,target_conditions: ConditionState,attacker_wounds: int) -> tuple[DiceModifier,...]:
    validate_pc_book_npc_definition(definition)
    if type(attacker_wounds) is not int:
        raise TypeError('NPC attack requires its exact actual Wound count')
    if not 0<=attacker_wounds<definition.wound_limit:
        raise ValueError('defeated or inconsistent NPC Wound count cannot prepare an attack')
    if attacker_wounds:
        if definition.id=='pc-book-npc:razorgor':
            return (DiceModifier(RAZORGOR_WOUNDED_MELEE_RULE_ID,attacker_wounds),)
        if definition.id in ('pc-book-npc:minotaur_axe','pc-book-npc:minotaur_dual_axes',
                'pc-book-npc:minotaur_greataxe'):
            return (DiceModifier(MINOTAUR_WOUNDED_MELEE_RULE_ID,attacker_wounds),)
    if definition.id in ('pc-book-npc:gor_dual_axes','pc-book-npc:gor_axe_shield','pc-book-npc:gor_axe') and conditions.has(Condition.STAGGERED):
        return (DiceModifier(GOR_PRIMAL_RAGE_RULE_ID,1),)
    if definition.id == 'pc-book-npc:bestigor_massive_axe' and conditions.has(Condition.STAGGERED):
        from towr.domain.pc_npc_blood_rage_policy_models import BLOOD_RAGE_RULE_ID
        return (DiceModifier(BLOOD_RAGE_RULE_ID,1),)
    if definition.id == 'pc-book-npc:flagellant_flails' and conditions.has(Condition.STAGGERED):
        from towr.domain.pc_flagellant_policy_models import FLAILS_STAGGERED_RULE_ID
        return (DiceModifier(FLAILS_STAGGERED_RULE_ID,-2),)
    if definition.id=='pc-book-npc:ungor_spear' and target_conditions.has(Condition.STAGGERED):
        return (DiceModifier(UNGOR_PRIMAL_SPITE_RULE_ID,1),)
    return ()


def pc_npc_damage_modifiers(definition: NpcDefinition) -> tuple[DamageModifier,...]:
    validate_pc_book_npc_definition(definition)
    if definition.id=='pc-book-npc:gor_dual_axes':
        return (DamageModifier(GOR_DUAL_AXES_RULE_ID,1),)
    if definition.id=='pc-book-npc:minotaur_dual_axes':
        return (DamageModifier(MINOTAUR_DUAL_AXES_RULE_ID,1),)
    return ()


def pc_npc_wound_dice_modifiers(definition: NpcDefinition,
        target_injury: CharacterInjuryState) -> tuple[WoundDiceModifier,...]:
    """Bind Devour to the actual target before Attack; never inspect the new Wound."""
    validate_pc_book_npc_definition(definition)
    if type(target_injury) is not CharacterInjuryState:
        raise TypeError('Devour requires the actual PC injury snapshot')
    vulnerable=(target_injury.conditions.has(Condition.STAGGERED)
        or target_injury.conditions.has(Condition.PRONE) or any(not w.healed for w in target_injury.wounds))
    if vulnerable:
        if definition.id=='pc-book-npc:razorgor':
            return (WoundDiceModifier(RAZORGOR_DEVOUR_RULE_ID,1),)
        if definition.id in ('pc-book-npc:minotaur_axe','pc-book-npc:minotaur_dual_axes',
                'pc-book-npc:minotaur_greataxe'):
            return (WoundDiceModifier(MINOTAUR_DEVOUR_RULE_ID,1),)
    return ()


def pc_npc_damage_profile(definition: NpcDefinition,*,unopposed: bool) -> DamageProfile:
    """Backstabba uses the actual absence of opposition, not zero defender successes."""
    validate_pc_book_npc_definition(definition)
    if type(unopposed) is not bool:
        raise TypeError('unopposed Attack eligibility must be an exact boolean')
    printed=definition.attacks[0].damage
    if definition.id=='pc-book-npc:nasty_skulker' and unopposed:
        return DamageProfile(printed.base,2)
    return printed


def pc_npc_stagger_defeat_spec(definition: NpcDefinition) -> MinionStaggerDefeatSpec | None:
    validate_pc_book_npc_definition(definition)
    if definition.id in ('pc-book-npc:goblin_warrior_spear','pc-book-npc:night_goblin_spear'):
        return MinionStaggerDefeatSpec(GOBLIN_DIRTY_COWARD_RULE_ID)
    return None
