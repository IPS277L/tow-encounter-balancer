"""Bounded, deterministic melee advice from public current battle facts.

Scores are simulator heuristics, not tabletop rules or extra Monte Carlo trials.
One defeated Minion is worth 1, a first Staggered is worth 0.5. Future wounds,
Fate rolls and other hidden outcomes are never inspected.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from math import comb
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition
from towr.domain.test_models import DiceModifier, Skill, TestQuality, TestRequest, _expected_initial_roll_parameters
from towr.domain.turn_models import CombatActionKind

if TYPE_CHECKING:
    from towr.domain.pc_melee_models import PcHelpPolicy, PcMeleeScenario
    from towr.domain.pc_melee_result_models import PcMeleeState
    from towr.domain.pc_potion_models import PcPotionSelection

SuccessDistribution = tuple[float, ...]


@dataclass(frozen=True, slots=True)
class PcTacticalChoice:
    actor_id: str
    action: CombatActionKind
    target_id: str | None
    help_policy: PcHelpPolicy | None
    utility: float
    reason: str
    potion: PcPotionSelection | None = None


@lru_cache(maxsize=4096)
def _binomial(dice: int, numerator: int) -> SuccessDistribution:
    p = numerator / 100
    return tuple(comb(dice, i) * p**i * (1-p)**(dice-i) for i in range(dice+1))


def _distribution(request: TestRequest) -> SuccessDistribution:
    parameters = _expected_initial_roll_parameters(request)
    dice, threshold = parameters[5:7]
    grim = any(item.quality is TestQuality.GRIM for item in request.quality_modifiers)
    glorious = any(item.quality is TestQuality.GLORIOUS for item in request.quality_modifiers)
    locked = {lock.value for lock in request.reroll_locks}
    numerator = (threshold**2 if grim and not glorious else
        100-(10-threshold)**2 if glorious and not grim else threshold*10)
    if grim and not glorious:
        numerator += sum(value <= threshold for value in locked)*(10-threshold)
    elif glorious and not grim:
        numerator -= sum(value > threshold for value in locked)*threshold
    raw = _binomial(dice, numerator)
    delta = sum(item.amount for item in request.success_modifiers)
    if not delta:
        return raw
    values = [0.0] * (max(0, dice+delta)+1)
    for successes, probability in enumerate(raw):
        values[max(0, successes+delta)] += probability
    return tuple(values)


@lru_cache(maxsize=8192)
def _impact_value(attack: SuccessDistribution, protection: SuccessDistribution,
                  damage: int, resilience: int, multiplier: int,
                  staggered: bool, defenceless: bool = False, defensive_stance: bool = False) -> float:
    """Expected immediate Minion progress, or Wound pressure for defence advice."""
    total = 0.0
    if defensive_stance:
        total -= .5*sum(probability*sum(protection[successes+1:])
            for successes,probability in enumerate(attack))
    for successes, probability in enumerate(attack):
        if not successes:
            continue
        for opposed, other in enumerate(protection):
            if opposed > successes:
                break
            wound = defenceless or damage+(successes-opposed)*multiplier > resilience
            total += probability*other*(1.0 if wound or staggered else 0.5)
    return total


def validate_automatic_melee_scenario(scenario: PcMeleeScenario) -> None:
    from towr.domain.pc_melee_models import PcMeleePolicy, PC_RANGED_WEAPONS
    from towr.domain.resolution_models import TargetInjuryPolicy
    if not any(member.policy is PcMeleePolicy.AUTOMATIC_MELEE for member in scenario.party):
        return
    if (not scenario.facts.all_opponents_close or scenario.short_range_opening is not None
            or any(member.pc.weapon in PC_RANGED_WEAPONS for member in scenario.party)):
        raise ValueError('automatic melee tactics require an all-Close melee party')
    if any(enemy.definition.injury_policy is not TargetInjuryPolicy.MINION
            or len(enemy.definition.attacks) != 1
            or enemy.definition.attacks[0].skill is not Skill.MELEE
            or len(enemy.definition.protection) != (2 if enemy.definition.generated_components is not None else 1)
            or enemy.definition.protection[0].skill not in (Skill.ATHLETICS, Skill.DEFENCE, Skill.MELEE)
            for enemy in scenario.enemies):
        raise ValueError('automatic melee tactics currently require Melee Minions with ordinary Protection')
    if any(member.wizard is not None for member in scenario.party):
        if scenario.facts.daylight_confirmed is not True or scenario.facts.can_leave_zone or any(not enemy.definition.source_rule_id.startswith('authored:')
                for enemy in scenario.enemies):
            raise ValueError('PC magic requires the closed numeric/generated Minion scene')


def select_pc_tactic(state: PcMeleeState, actor_id: str | None = None) -> PcTacticalChoice:
    """Reevaluate Attack, standard Recover and exact-Test Help, without RNG.

    Later allies are considered only from present facts. A forward-only memoized
    plan avoids intentionally sending Attack Help to an ally currently planning
    Help/Recover. Actual future changes may still leave the bonus unused.
    """
    from towr.domain.pc_melee_models import PcMeleePolicy, PcHelpPolicy, PcHelpTarget
    from towr.domain.pc_melee_result_models import (
        _pc_test, _pc_recover_needed, pc_melee_action_id, pc_protection_skill,
    )
    from towr.domain.pc_help_models import eligible_pc_help_beneficiary, build_pc_test_help
    from towr.domain.pc_ally_recover_models import pc_recover_removable
    from towr.domain.pc_backup_weapon_models import pc_active_weapon
    from towr.domain.pc_weapon_models import pc_weapon_damage, pc_weapon_damage_modifiers, pc_weapon_attack_modifiers, pc_weapon_test_modifiers
    from towr.domain.pc_npc_ability_models import (pc_npc_allows_enemy_higher_ground,
        pc_npc_attack_modifiers, pc_npc_damage_modifiers, pc_npc_damage_profile, pc_npc_outnumbering_modifier)
    from towr.domain.pc_npc_distraction_models import pc_npc_distraction_test_modifiers
    from towr.domain.pc_npc_grudge_models import pc_npc_grudge_melee_modifiers
    from towr.domain.pc_shield_models import pc_shield_resilience
    from towr.domain.injury_models import WoundRestriction
    from towr.domain.pc_heavy_wound_models import restriction_sources
    from towr.domain.pc_potion_models import pc_effective_definition, potion_options
    from towr.domain.potion_models import ConsumableKind

    actor_id = actor_id or state.round_state.active_turn.actor_id
    unavailable = (*state.round_state.completed_turn_entity_ids, *state.round_state.excluded_turn_entity_ids)
    enemies = tuple(enemy for enemy in state.source.enemy_activation_order
        if not state.enemy(enemy).state.injury.defeated and enemy not in state.exited_npc_ids)
    plans: dict[str, PcTacticalChoice] = {}
    attacks: dict[tuple[str, int, str | None], tuple[float, str | None]] = {}

    def test(actor: str, skill: Skill) -> TestRequest:
        return _pc_test(state, actor, pc_melee_action_id(state, actor)+':attack', skill)

    def best_attack(actor: str, extra: int = 0, enhancement: str | None = None) -> tuple[float, str | None]:
        key = (actor, extra, enhancement)
        if key in attacks:
            return attacks[key]
        pc, member = pc_effective_definition(state, actor), state.participant(actor)
        if enhancement is not None:
            pc = replace(pc, **{enhancement: getattr(pc, enhancement)+1})
        weapon = pc_active_weapon(state, actor)
        best = (0.0, None)
        for enemy_id in state.source.participant(actor).target_priority:
            if enemy_id not in enemies:
                continue
            enemy = state.enemy(enemy_id)
            modifiers = []
            if state.source.facts.outnumbering_bonus_approved and sum(
                    not ally.injury.conditions.has(Condition.DEFENCELESS) for ally in state.live_party) > sum(
                    not item.state.injury.conditions.has(Condition.DEFENCELESS) for item in state.live_enemies):
                modifiers.append(DiceModifier('RULE-COMBAT-007:outnumbering', 1))
            if enemy.state.injury.conditions.has(Condition.PRONE) and pc_npc_allows_enemy_higher_ground(enemy.definition):
                modifiers.append(DiceModifier('RULE-COMBAT-007:higher-ground', 1))
            modifiers.extend(pc_weapon_attack_modifiers(weapon, enemy.state.injury.conditions))
            if extra:
                modifiers.append(DiceModifier('tactics:prospective-help', extra))
            request = _pc_test(state, actor, pc_melee_action_id(state, actor)+':attack', Skill.MELEE, tuple(modifiers))
            if enhancement is not None:
                request = replace(request, profile=pc.melee_profile)
            request, _ = build_pc_test_help(state, actor, Skill.MELEE, request)
            from towr.domain.pc_generated_equipment import npc_protection_test
            profile,protection = npc_protection_test(state,enemy_id,actor,'tactics:protection')
            damage = pc_weapon_damage(weapon, pc.strength)
            base = damage.base + sum(item.amount for item in pc_weapon_damage_modifiers(weapon, enemy.state.current_resilience))
            defenceless = enemy.state.injury.conditions.has(Condition.DEFENCELESS)
            from towr.domain.pc_generated_talents import has_generated_talent
            from towr.domain.generated_npc_models import GeneratedTalent
            stance = (not defenceless and profile.skill is Skill.DEFENCE
                and enemy.state.injury.conditions.has(Condition.STAGGERED)
                and not member.injury.conditions.has(Condition.STAGGERED)
                and has_generated_talent(enemy.definition,GeneratedTalent.DEFENSIVE_STANCE))
            value = _impact_value(_distribution(request), (1.0,) if defenceless else _distribution(protection),
                base, enemy.state.current_resilience.total, damage.success_multiplier,
                enemy.state.injury.conditions.has(Condition.STAGGERED), defenceless,stance)
            if best[1] is None or value > best[0]+1e-12:
                best = (value, enemy_id)
        attacks[key] = best
        return best

    def incoming_risk(target: str, protection_bonus: int = 0,
                      prone_removed: bool = False, stagger_removed: bool = False,
                      enhancement: str | None = None) -> float:
        # NPC target order is a source fact. Future deaths/target changes are not
        # anticipated. Prospective Protection Help applies to ONE exact Test.
        first = next((actor for actor in state.source.enemy_target_priority
            if not state.participant(actor).injury.dead), None)
        if target != first:
            return 0.0
        member = state.participant(target)
        target_conditions = member.injury.conditions
        if stagger_removed:
            target_conditions = target_conditions.without_condition(Condition.STAGGERED)
        if prone_removed:
            target_conditions = target_conditions.without_condition(Condition.PRONE)
        value = 0.0
        incoming = tuple(enemy for enemy in enemies if enemy not in unavailable)
        for enemy_id in incoming:
            enemy = state.enemy(enemy_id)
            attack = enemy.definition.attacks[0]
            from towr.domain.pc_generated_talents import wild_attack_available,WILD_ATTACK_RULE_ID
            from towr.domain.test_models import QualityModifier
            wild = wild_attack_available(enemy.definition,enemy.state.injury.conditions)
            attack_conditions = (enemy.state.injury.conditions.with_condition(Condition.STAGGERED)
                if wild else enemy.state.injury.conditions)
            modifiers = []
            if target_conditions.has(Condition.PRONE):
                modifiers.append(DiceModifier('RULE-COMBAT-007:higher-ground', 1))
            if (state.source.facts.outnumbering_bonus_approved
                    and len(state.live_enemies) > len(state.live_party)):
                modifiers.append(pc_npc_outnumbering_modifier(enemy.definition))
            modifiers.extend(pc_npc_attack_modifiers(enemy.definition, attack_conditions,
                target_conditions=target_conditions, attacker_wounds=enemy.state.injury.wounds))
            from towr.domain.pc_generated_equipment import generated_attack_modifiers,generated_damage_modifiers
            modifiers.extend(generated_attack_modifiers(enemy.definition,attack_conditions,
                target_conditions))
            modifiers.extend(pc_npc_grudge_melee_modifiers(state, enemy_id, target))
            modifiers.extend(pc_npc_distraction_test_modifiers(state, enemy_id, target))
            if enemy.state.injury.conditions.has(Condition.DRAINED):
                modifiers = [modifier for modifier in modifiers if modifier.amount <= 0]
            from towr.domain.pc_magic_models import magic_test_modifiers
            attacker = TestRequest('tactics:incoming', attack.test_profile,
                (*modifiers,*magic_test_modifiers(state,enemy_id,Skill.MELEE)[0]),
                (QualityModifier(WILD_ATTACK_RULE_ID,TestQuality.GLORIOUS),) if wild else ())
            skill = pc_protection_skill(member, Skill.MELEE)
            bonus = protection_bonus if enemy_id == incoming[0] else 0
            defender = _pc_test(state, target, pc_melee_action_id(state, enemy_id)+':protection', skill,
                (DiceModifier('tactics:prospective-help', bonus),) if bonus else ())
            if enhancement is not None:
                pc = pc_effective_definition(state, target)
                pc = replace(pc, **{enhancement: getattr(pc, enhancement)+1})
                profile = {Skill.MELEE: pc.melee_profile, Skill.DEFENCE: pc.defence_profile,
                    Skill.ATHLETICS: pc.athletics_profile, Skill.ENDURANCE: pc.endurance_profile}[skill]
                defender = replace(defender, profile=profile)
            defender, _ = build_pc_test_help(state, target, skill, defender)
            if stagger_removed:
                weapon = pc_active_weapon(state, target)
                old = pc_weapon_test_modifiers(weapon, skill, member.injury.conditions)
                new = pc_weapon_test_modifiers(weapon, skill, member.injury.conditions.without_condition(Condition.STAGGERED))
                if member.injury.conditions.has(Condition.DRAINED):
                    new = tuple(modifier for modifier in new if modifier.amount <= 0)
                defender = replace(defender, dice_modifiers=tuple(modifier for modifier in defender.dice_modifiers
                    if modifier.rule_id not in {item.rule_id for item in old})+new)
            damage = pc_npc_damage_profile(enemy.definition, unopposed=False)
            if damage is None:
                continue
            base = damage.base+sum(modifier.amount for modifier in
                (pc_npc_damage_modifiers(enemy.definition)
                + generated_damage_modifiers(enemy.definition,pc_shield_resilience(state,target))))
            value += _impact_value(_distribution(attacker), _distribution(defender), base,
                pc_shield_resilience(state, target).total+int(enhancement == 'toughness'), damage.success_multiplier,
                member.injury.conditions.has(Condition.STAGGERED) and not stagger_removed)
        return value

    def plan(actor: str) -> PcTacticalChoice:
        if actor in plans:
            return plans[actor]
        member = state.participant(actor)
        from towr.domain.pc_heavy_wound_models import usable_weapon_hand
        from towr.domain.pc_backup_weapon_models import pc_preferred_weapon_hand
        from towr.domain.pc_magic_models import magic_hand
        casting_with_unusable_weapon = (state.source.participant(actor).wizard is not None
            and magic_hand(state,actor) is not None and usable_weapon_hand(member) is None
            and pc_preferred_weapon_hand(state,actor) is None)
        needs_recover = _pc_recover_needed(member) and not casting_with_unusable_weapon
        if casting_with_unusable_weapon:
            choice = PcTacticalChoice(actor,CombatActionKind.RECOVER,actor,None,0.0,'weapon_grip_unavailable')
        elif needs_recover:
            choice = PcTacticalChoice(actor, CombatActionKind.RECOVER, actor, None, 1.0, 'restore_own_combat_readiness')
        else:
            score, target = best_attack(actor)
            choice = PcTacticalChoice(actor, CombatActionKind.ATTACK, target, None, score, 'best_immediate_attack')

        for option in potion_options(member):
            item = next(item for item in member.potions if item.id == option.item_id)
            if item.kind is ConsumableKind.HEALING:
                wound = member.injury.wounds[option.wound_sequence-1]
                effects = tuple(effect for effect in member.injury.active_wound_effects
                    if effect.wound_sequence == option.wound_sequence)
                value = 0.2+min(0.5, wound.table_total*0.025)+min(0.6, len(effects)*0.2)
                if any(getattr(effect, 'condition', None) is Condition.CRITICALLY_INJURED for effect in effects):
                    value += 1.0
                if member.injury.conditions.has(Condition.DEFENCELESS):
                    value += 3.0
                if needs_recover:
                    value += 1.0
                reason = 'heal_actual_wound'
            else:
                horizon = min(3, state.source.max_rounds-state.round_state.round_number)
                value = horizon*(max(0.0, best_attack(actor, enhancement=item.characteristic)[0]-best_attack(actor)[0])
                    +min(1.0, max(0.0, incoming_risk(actor)-incoming_risk(actor, enhancement=item.characteristic))))
                if needs_recover and value > 0:
                    value += 1.0
                reason = 'enhance_for_remaining_turns'
            if value > choice.utility+1e-12:
                choice = PcTacticalChoice(actor, CombatActionKind.RECOVER, actor, None, value, reason, option)
        if needs_recover or member.injury.conditions.has(Condition.DEFENCELESS):
            plans[actor] = choice
            return choice

        def consider(action: CombatActionKind, target: str | None, utility: float,
                     reason: str, help_policy: PcHelpPolicy | None = None) -> None:
            nonlocal choice
            if utility > choice.utility+1e-12:
                choice = PcTacticalChoice(actor, action, target, help_policy, utility, reason)

        for ally in state.party:
            if ally.injury.dead or ally.injury.conditions.has(Condition.DEFENCELESS):
                continue
            stagger = pc_recover_removable(ally, Condition.STAGGERED)
            prone = pc_recover_removable(ally, Condition.PRONE)
            if not (stagger or prone):
                continue
            if prone and restriction_sources(ally.injury, WoundRestriction.REMOVING_PRONE_CAUSES_CRITICAL):
                continue
            value = min(1.0, max(0.0, incoming_risk(ally.actor_id)-incoming_risk(
                ally.actor_id, prone_removed=prone, stagger_removed=stagger)))
            if prone:
                if ally.actor_id not in unavailable and ally.actor_id != actor:
                    value += best_attack(ally.actor_id)[0]
            if ally.actor_id != actor and pc_recover_removable(member, Condition.STAGGERED) and not stagger:
                value += min(1.0, max(0.0, incoming_risk(actor)-incoming_risk(actor, stagger_removed=True)))
            consider(CombatActionKind.RECOVER, ally.actor_id, value, 'restore_useful_ally_or_remove_stagger')

        for ally_id in state.source.pc_activation_order:
            if ally_id == actor:
                continue
            for kind in (PcHelpTarget.MELEE_ATTACK, PcHelpTarget.FIRST_INCOMING_PROTECTION):
                skill = Skill.MELEE if kind is PcHelpTarget.MELEE_ATTACK else pc_protection_skill(state.participant(ally_id), Skill.MELEE)
                policy = PcHelpPolicy(ally_id, kind, None if kind is PcHelpTarget.MELEE_ATTACK else skill)
                if eligible_pc_help_beneficiary(state, policy, actor) is None:
                    continue
                if kind is PcHelpTarget.MELEE_ATTACK:
                    if state.source.pc_activation_order.index(ally_id) <= state.source.pc_activation_order.index(actor):
                        continue
                    source = state.source.participant(ally_id)
                    if source.policy not in (PcMeleePolicy.AUTOMATIC_MELEE, PcMeleePolicy.ATTACK_OR_RECOVER_SELF):
                        continue
                    if source.policy is PcMeleePolicy.AUTOMATIC_MELEE and plan(ally_id).action is not CombatActionKind.ATTACK:
                        continue
                    before = best_attack(ally_id)[0]
                    value = sum(probability*max(0.0, best_attack(ally_id, successes)[0]-before)
                        for successes, probability in enumerate(_distribution(test(actor, skill))))
                else:
                    before = incoming_risk(ally_id)
                    value = sum(probability*max(0.0, before-incoming_risk(ally_id, successes))
                        for successes, probability in enumerate(_distribution(test(actor, skill))))
                consider(CombatActionKind.HELP, ally_id, value, 'improve_exact_upcoming_test', policy)
        wizard = state.source.participant(actor).wizard
        if wizard is not None:
            from towr.domain.pc_magic_models import magic_hand,spell_choice
            if magic_hand(state,actor) is not None:
                request = _pc_test(state,actor,pc_melee_action_id(state,actor)+':willpower',Skill.WILLPOWER)
                from towr.rules.miscast_pool_resolution import rule_of_nine_reroll_lock
                request = replace(request,reroll_locks=(*request.reroll_locks,rule_of_nine_reroll_lock()))
                distribution = _distribution(request)
                accumulated = member.magic.casting_successes
                value = 0.0
                for successes, probability in enumerate(distribution):
                    if accumulated+successes >= 2:
                        value += probability*spell_choice(state,actor,successes)[2]
                    elif state.round_state.round_number < state.source.max_rounds:
                        value += probability*0.6*sum(chance*spell_choice(state,actor,final)[2]
                            for final,chance in enumerate(distribution) if accumulated+successes+final>=2)
                value *= 1-min(0.4,member.magic.miscast_dice/(wizard.wizard_level+1)*0.2)
                consider(CombatActionKind.IMPROVISE, actor, value, 'cast_best_available_elemental_spell')
            if member.magic.casting_lore_id is None and member.magic.miscast_dice:
                consider(CombatActionKind.RECOVER,actor,
                    0.2+0.25*member.magic.miscast_dice/wizard.wizard_level,'dispose_residual_magic')
        plans[actor] = choice
        return choice

    return plan(actor_id)
