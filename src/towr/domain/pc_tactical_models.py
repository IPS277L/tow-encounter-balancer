"""Bounded, deterministic melee advice from public current battle facts.

Scores are simulator heuristics, not tabletop rules or extra Monte Carlo trials.
One defeated Minion is worth 1, a first Staggered is worth 0.5. Future wounds,
Fate rolls and other hidden outcomes are never inspected.
"""
from __future__ import annotations

from towr.domain.reload_models import ranged_weapon_is_loaded
from dataclasses import dataclass, field, replace
from functools import lru_cache
from math import comb
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition
from towr.domain.test_models import DiceModifier, Skill, TestQuality, TestRequest, _expected_initial_roll_parameters
from towr.domain.turn_models import CombatActionKind, ManoeuvreKind

if TYPE_CHECKING:
    from towr.domain.pc_melee_models import PcHelpPolicy, PcMeleeScenario
    from towr.domain.pc_melee_result_models import PcMeleeState
    from towr.domain.pc_potion_models import PcPotionSelection

SuccessDistribution = tuple[float, ...]


class _IncomingRiskMemo:
    """Reuse exact forecast evaluations during one selector invocation only.

    Forecast identity retains every state fact without hashing a whole journal.
    Strong references prevent Python from reusing a discarded forecast's ID.
    Distinct prepared states are intentionally not merged by selected fields.
    """

    def __init__(self, calculate):
        self._calculate = calculate
        self._forecasts = {}
        self._values = {}

    def __call__(self, forecast, target, protection_bonus=0, prone_removed=False,
                 stagger_removed=False, enhancement=None, stagger_added=False):
        key = (id(forecast), target, protection_bonus, prone_removed,
               stagger_removed, enhancement, stagger_added)
        if key not in self._values:
            self._forecasts[id(forecast)] = forecast
            self._values[key] = self._calculate(forecast, target, protection_bonus,
                prone_removed, stagger_removed, enhancement, stagger_added)
        return self._values[key]


@dataclass(frozen=True, slots=True)
class PcTacticalChoice:
    actor_id: str
    action: CombatActionKind
    target_id: str | None
    help_policy: PcHelpPolicy | None
    utility: float
    reason: str
    potion: PcPotionSelection | None = None
    wild_attack: bool = field(default=False,kw_only=True)
    weapon_item_id: str | None = field(default=None,kw_only=True)
    ranged_bonus: bool = field(default=False,kw_only=True)
    ranged_reload: bool = field(default=False,kw_only=True)
    pickup_item_id: str | None = field(default=None,kw_only=True)
    manoeuvre: ManoeuvreKind | None = field(default=None,kw_only=True)
    net_item_id: str | None = field(default=None,kw_only=True)
    net_release_target_id: str | None = field(default=None,kw_only=True)


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


def validate_automatic_combat_scenario(scenario: PcMeleeScenario) -> None:
    from towr.domain.pc_melee_models import PcMeleePolicy, PC_RANGED_WEAPONS
    from towr.domain.resolution_models import TargetInjuryPolicy
    if not any(member.policy is PcMeleePolicy.AUTOMATIC_COMBAT for member in scenario.party):
        return
    from towr.domain.pc_melee_models import PcMeleeWeapon
    supported=(PcMeleeWeapon.PISTOL,PcMeleeWeapon.REPEATER_PISTOL,PcMeleeWeapon.REPEATER_HANDBOW)
    if scenario.battlefield is None and (not scenario.facts.all_opponents_close or scenario.short_range_opening is not None
            or any(member.pc.weapon in PC_RANGED_WEAPONS and member.pc.weapon not in supported for member in scenario.party)):
        raise ValueError('automatic combat requires all-Close melee or supported one-handed ranged weapons')
    if any(enemy.definition.injury_policy is not TargetInjuryPolicy.MINION
            or len(enemy.definition.attacks) != 1
            or (enemy.definition.attacks[0].skill is not Skill.MELEE
                and not (enemy.definition.attacks[0].skill is Skill.SHOOTING
                    and enemy.definition.generated_components is not None
                    and enemy.definition.generated_components.ranged is not None)
                and not (enemy.definition.attacks[0].skill is Skill.THROWING
                    and enemy.definition.generated_components is not None
                    and enemy.definition.generated_components.weapon.value == 'weighted_net'))
            or len(enemy.definition.protection) != (2 if enemy.definition.generated_components is not None else 1)
            or enemy.definition.protection[0].skill not in (Skill.ATHLETICS, Skill.DEFENCE, Skill.MELEE)
            for enemy in scenario.enemies):
        raise ValueError('automatic melee tactics require ordinary Melee or complete generated Shooting Minions')
    if any(member.wizard is not None for member in scenario.party):
        if scenario.facts.daylight_confirmed is not True or (scenario.facts.can_leave_zone and scenario.battlefield is None) or any(not enemy.definition.source_rule_id.startswith('authored:')
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
    from towr.domain.pc_mount_models import pc_is_mounted
    from towr.domain.pc_battlefield_movement_models import (
        pc_battlefield_attack_available, pc_battlefield_allows_outnumbering,
    )

    actor_id = actor_id or state.round_state.active_turn.actor_id
    from towr.domain.pc_weapon_inventory import pending_pc_weapon_swap
    swap=pending_pc_weapon_swap(state,actor_id)
    if swap is not None:
        return swap.intent
    from towr.domain.pc_generated_talents import pending_wild_attack
    committed = pending_wild_attack(state)
    if committed is not None and committed.actor_id == actor_id and committed.intent is not None:
        return committed.intent
    from towr.domain.pc_talent_advice import (pc_has_combat_talent,pc_wild_eligible,
        pc_wild_test_variant,pc_test_distribution)
    unavailable = (*state.round_state.completed_turn_entity_ids, *state.round_state.excluded_turn_entity_ids)
    enemies = tuple(enemy for enemy in state.source.enemy_activation_order
        if not state.enemy(enemy).state.injury.defeated and enemy not in state.exited_npc_ids)
    plans: dict[str, PcTacticalChoice] = {}
    attacks: dict[tuple[str, int, str | None, bool, str | None, bool], tuple[float, str | None]] = {}
    help_continuations={}

    def test(actor: str, skill: Skill) -> TestRequest:
        return _pc_test(state, actor, pc_melee_action_id(state, actor)+':attack', skill)

    def best_attack(actor: str, extra: int = 0, enhancement: str | None = None,
                    wild: bool = False, weapon_item_id=None, ranged_bonus=False) -> tuple[float, str | None]:
        from towr.domain.pc_ranged_advice import pc_attack_value
        from towr.domain.pc_weapon_inventory import pc_weapon_inventory_view
        inventory=state.participant(actor).weapon_inventory
        item_key=(inventory.active_item_id if weapon_item_id is None and inventory is not None
            else weapon_item_id)
        key = (actor, extra, enhancement, wild, item_key, ranged_bonus)
        if key in attacks:
            return attacks[key]
        view=state
        if weapon_item_id is not None:
            view=pc_weapon_inventory_view(state,actor,weapon_item_id)
            if view is None:
                attacks[key]=(0.0,None)
                return attacks[key]
        from towr.domain.pc_melee_models import PC_THROWING_WEAPONS
        if (state.source.participant(actor).pc.ranged is not None
                or state.source.participant(actor).pc.weapon in PC_THROWING_WEAPONS):
            attacks[key]=pc_attack_value(view,actor,extra=extra,enhancement=enhancement,
                wild=wild,bonus=ranged_bonus)
            return attacks[key]
        pc, member = pc_effective_definition(state, actor), state.participant(actor)
        if enhancement is not None:
            pc = replace(pc, **{enhancement: getattr(pc, enhancement)+1})
        weapon = pc_active_weapon(state, actor)
        best = (0.0, None)
        for enemy_id in state.source.participant(actor).target_priority:
            if enemy_id not in enemies or not pc_battlefield_attack_available(state,actor,enemy_id):
                continue
            enemy = state.enemy(enemy_id)
            modifiers = []
            if pc_battlefield_allows_outnumbering(state,actor):
                modifiers.append(DiceModifier('RULE-COMBAT-007:outnumbering', 1))
            if enemy.state.injury.conditions.has(Condition.PRONE) and pc_npc_allows_enemy_higher_ground(enemy.definition):
                modifiers.append(DiceModifier('RULE-COMBAT-007:higher-ground', 1))
            modifiers.extend(pc_weapon_attack_modifiers(weapon, enemy.state.injury.conditions,
                target_mounted=pc_is_mounted(state,enemy_id)))
            if extra:
                modifiers.append(DiceModifier('tactics:prospective-help', extra))
            request = _pc_test(state, actor, pc_melee_action_id(state, actor)+':attack', Skill.MELEE, tuple(modifiers))
            if enhancement is not None:
                request = replace(request, profile=pc.melee_profile)
            request, _ = build_pc_test_help(state, actor, Skill.MELEE, request)
            if wild:
                request = pc_wild_test_variant(request,weapon,member.injury.conditions)
            from towr.domain.pc_generated_equipment import npc_protection_test
            profile,protection = npc_protection_test(state,enemy_id,actor,'tactics:protection')
            from towr.domain.pc_melee_models import PcTwoHandedGrip
            damage = pc_weapon_damage(weapon, pc.strength,
                two_handed=member.weapon_hand is PcTwoHandedGrip.BOTH)
            base = damage.base + sum(item.amount for item in pc_weapon_damage_modifiers(weapon, enemy.state.current_resilience))
            defenceless = enemy.state.injury.conditions.has(Condition.DEFENCELESS)
            from towr.domain.pc_generated_talents import has_generated_talent
            from towr.domain.generated_npc_models import GeneratedTalent
            stance = (not defenceless and profile.skill is Skill.DEFENCE
                and enemy.state.injury.conditions.has(Condition.STAGGERED)
                and not wild and not member.injury.conditions.has(Condition.STAGGERED)
                and has_generated_talent(enemy.definition,GeneratedTalent.DEFENSIVE_STANCE))
            value = _impact_value(pc_test_distribution(state,actor,Skill.MELEE,request), (1.0,) if defenceless else _distribution(protection),
                base, enemy.state.current_resilience.total, damage.success_multiplier,
                enemy.state.injury.conditions.has(Condition.STAGGERED), defenceless,stance)
            if best[1] is None or value > best[0]+1e-12:
                best = (value, enemy_id)
        attacks[key] = best
        return best

    def calculate_incoming_risk(forecast, target: str, protection_bonus: int,
                      prone_removed: bool, stagger_removed: bool,
                      enhancement: str | None, stagger_added: bool) -> float:
        # NPC target order is a source fact. Future deaths/target changes are not
        # anticipated. Prospective Protection Help applies to ONE exact Test.
        first = next((actor for actor in forecast.source.enemy_target_priority
            if not forecast.participant(actor).injury.dead), None)
        if target != first:
            return 0.0
        member = forecast.participant(target)
        target_conditions = member.injury.conditions
        if stagger_added:
            target_conditions = target_conditions.with_condition(Condition.STAGGERED)
        if stagger_removed:
            target_conditions = target_conditions.without_condition(Condition.STAGGERED)
        if prone_removed:
            target_conditions = target_conditions.without_condition(Condition.PRONE)
        value = 0.0
        from towr.domain.pc_npc_ranged_models import pc_npc_ranged_weapon
        incoming = tuple(enemy for enemy in enemies if enemy not in unavailable
            and (forecast.enemy(enemy).definition.attacks[0].skill is not Skill.SHOOTING
                or (pc_npc_ranged_weapon(forecast,enemy) is not None
                    and ranged_weapon_is_loaded(pc_npc_ranged_weapon(forecast,enemy)))))
        for enemy_id in incoming:
            if not pc_battlefield_attack_available(forecast,enemy_id,target):
                continue
            enemy = forecast.enemy(enemy_id)
            attack = enemy.definition.attacks[0]
            if attack.skill is Skill.SHOOTING:
                from towr.domain.pc_generated_ranged_advice import (
                    pc_close_shooting_protection,npc_repeater_bonus)
                from towr.domain.pc_magic_models import magic_test_modifiers
                from towr.domain.ranged_weapon_profiles import (RangedWeaponId,
                    ranged_weapon_reload_profile,REPEATER_SHOOTING_BONUS_RULE_ID)
                modifiers = list(pc_npc_attack_modifiers(enemy.definition,enemy.state.injury.conditions,
                    target_conditions=target_conditions,attacker_wounds=enemy.state.injury.wounds))
                if target_conditions.has(Condition.PRONE):
                    modifiers.append(DiceModifier('RULE-HEALTH-008:prone-shooting',-1))
                modifiers.extend(pc_npc_distraction_test_modifiers(forecast,enemy_id,target))
                dice,qualities=magic_test_modifiers(forecast,enemy_id,Skill.SHOOTING)
                modifiers.extend(dice)
                if enemy.state.injury.conditions.has(Condition.DRAINED):
                    modifiers=[m for m in modifiers if m.amount <= 0]
                attacker=TestRequest('tactics:incoming-shooting',attack.test_profile,
                    tuple(modifiers),qualities)
                bonus=protection_bonus if enemy_id==incoming[0] else 0
                skill,defender=pc_close_shooting_protection(forecast,target,enemy_id,
                    pc_melee_action_id(forecast,enemy_id)+':protection',conditions=target_conditions,
                    extra_dice=bonus,enhancement=enhancement)
                resilience=pc_shield_resilience(forecast,target)
                if enhancement=='toughness':
                    resilience=replace(resilience,toughness=resilience.toughness+1)
                defenceless=target_conditions.has(Condition.DEFENCELESS)
                if npc_repeater_bonus(forecast,enemy_id,attacker,None if defenceless else defender,target,
                        target_conditions=target_conditions,resilience=resilience,defender_skill=skill):
                    profile=ranged_weapon_reload_profile(RangedWeaponId(enemy.definition.generated_components.weapon.value))
                    attacker=replace(attacker,dice_modifiers=(*attacker.dice_modifiers,
                        DiceModifier(REPEATER_SHOOTING_BONUS_RULE_ID,profile.optional_shooting_bonus_dice)))
                resistance=resilience.toughness if attack.ignores_armour else resilience.total
                value+=_impact_value(_distribution(attacker),(1.0,) if defenceless else
                    pc_test_distribution(forecast,target,skill,defender,include_policy=True),
                    attack.damage.base,resistance,attack.damage.success_multiplier,
                    target_conditions.has(Condition.STAGGERED),defenceless)
                continue
            from towr.domain.pc_generated_talents import wild_attack_available,WILD_ATTACK_RULE_ID
            from towr.domain.test_models import QualityModifier
            wild = wild_attack_available(enemy.definition,enemy.state.injury.conditions)
            attack_conditions = (enemy.state.injury.conditions.with_condition(Condition.STAGGERED)
                if wild else enemy.state.injury.conditions)
            modifiers = []
            if target_conditions.has(Condition.PRONE):
                modifiers.append(DiceModifier('RULE-COMBAT-007:higher-ground', 1))
            if pc_battlefield_allows_outnumbering(forecast,enemy_id):
                modifiers.append(pc_npc_outnumbering_modifier(enemy.definition))
            modifiers.extend(pc_npc_attack_modifiers(enemy.definition, attack_conditions,
                target_conditions=target_conditions, attacker_wounds=enemy.state.injury.wounds))
            from towr.domain.pc_generated_equipment import generated_attack_modifiers,generated_damage_modifiers
            modifiers.extend(generated_attack_modifiers(enemy.definition,attack_conditions,
                target_conditions,target_mounted=pc_is_mounted(forecast,target)))
            modifiers.extend(pc_npc_grudge_melee_modifiers(forecast, enemy_id, target))
            modifiers.extend(pc_npc_distraction_test_modifiers(forecast, enemy_id, target))
            if enemy.state.injury.conditions.has(Condition.DRAINED):
                modifiers = [modifier for modifier in modifiers if modifier.amount <= 0]
            from towr.domain.pc_magic_models import magic_test_modifiers
            attacker = TestRequest('tactics:incoming', attack.test_profile,
                (*modifiers,*magic_test_modifiers(forecast,enemy_id,Skill.MELEE)[0]),
                (QualityModifier(WILD_ATTACK_RULE_ID,TestQuality.GLORIOUS),) if wild else ())
            skill = pc_protection_skill(member, Skill.MELEE)
            bonus = protection_bonus if enemy_id == incoming[0] else 0
            defender = _pc_test(forecast, target, pc_melee_action_id(forecast, enemy_id)+':protection', skill,
                (DiceModifier('tactics:prospective-help', bonus),) if bonus else ())
            if enhancement is not None:
                pc = pc_effective_definition(forecast, target)
                pc = replace(pc, **{enhancement: getattr(pc, enhancement)+1})
                profile = {Skill.MELEE: pc.melee_profile, Skill.DEFENCE: pc.defence_profile,
                    Skill.ATHLETICS: pc.athletics_profile, Skill.ENDURANCE: pc.endurance_profile}[skill]
                defender = replace(defender, profile=profile)
            defender, _ = build_pc_test_help(forecast, target, skill, defender)
            if stagger_removed or stagger_added:
                weapon = pc_active_weapon(forecast, target)
                old = pc_weapon_test_modifiers(weapon, skill, member.injury.conditions)
                new = pc_weapon_test_modifiers(weapon, skill, target_conditions)
                if member.injury.conditions.has(Condition.DRAINED):
                    new = tuple(modifier for modifier in new if modifier.amount <= 0)
                defender = replace(defender, dice_modifiers=tuple(modifier for modifier in defender.dice_modifiers
                    if modifier.rule_id not in {item.rule_id for item in old})+new)
            damage = pc_npc_damage_profile(enemy.definition, unopposed=False)
            if damage is None:
                continue
            base = damage.base+sum(modifier.amount for modifier in
                (pc_npc_damage_modifiers(enemy.definition)
                + generated_damage_modifiers(enemy.definition,pc_shield_resilience(forecast,target))))
            from towr.domain.generated_npc_models import GeneratedTalent
            from towr.domain.pc_heavy_wound_models import has_ongoing_condition
            stance = (skill is Skill.DEFENCE and target_conditions.has(Condition.STAGGERED)
                and not has_ongoing_condition(member.injury,Condition.STAGGERED)
                and not attack_conditions.has(Condition.STAGGERED)
                and pc_has_combat_talent(forecast,target,GeneratedTalent.DEFENSIVE_STANCE))
            value += _impact_value(_distribution(attacker), pc_test_distribution(forecast,target,skill,defender), base,
                pc_shield_resilience(forecast, target).total+int(enhancement == 'toughness'), damage.success_multiplier,
                target_conditions.has(Condition.STAGGERED), defensive_stance=stance)
        return value

    risk_memo = _IncomingRiskMemo(calculate_incoming_risk)

    def incoming_risk(target: str, protection_bonus: int = 0,
                      prone_removed: bool = False, stagger_removed: bool = False,
                      enhancement: str | None = None, stagger_added: bool = False, view=None) -> float:
        return risk_memo(state if view is None else view,target,protection_bonus,
            prone_removed,stagger_removed,enhancement,stagger_added)

    def plan(actor: str) -> PcTacticalChoice:
        if actor in plans:
            return plans[actor]
        member = state.participant(actor)
        from towr.domain.pc_heavy_wound_models import usable_weapon_hand,usable_hands
        from towr.domain.pc_backup_weapon_models import pc_preferred_weapon_hand
        from towr.domain.pc_magic_models import magic_hand
        casting_with_unusable_weapon = (state.source.participant(actor).wizard is not None
            and magic_hand(state,actor) is not None and usable_weapon_hand(member) is None
            and pc_preferred_weapon_hand(state,actor) is None)
        needs_recover = _pc_recover_needed(member) and not casting_with_unusable_weapon
        ranged_actor=state.source.participant(actor).pc.ranged is not None
        from towr.domain.pc_melee_models import PC_THROWING_WEAPONS
        net_actor=state.source.participant(actor).pc.weapon in PC_THROWING_WEAPONS
        if casting_with_unusable_weapon:
            choice = PcTacticalChoice(actor,CombatActionKind.RECOVER,actor,None,0.0,'weapon_grip_unavailable')
        elif needs_recover:
            choice = PcTacticalChoice(actor, CombatActionKind.RECOVER, actor, None, 1.0, 'restore_own_combat_readiness')
        else:
            score, target = best_attack(actor)
            choice = (PcTacticalChoice(actor, CombatActionKind.ATTACK, target, None, score, 'best_immediate_attack')
                if target is not None else PcTacticalChoice(actor, CombatActionKind.RECOVER,actor,None,0.0,'no_available_attack'))

        if net_actor and needs_recover and not member.injury.conditions.has(Condition.PRONE):
            # A deployed physical Net is not a dropped held weapon. Ordinary
            # Recover cannot return it from a distant target or a binding.
            choice=PcTacticalChoice(actor,CombatActionKind.RECOVER,actor,None,0.0,
                'recover_without_available_net')

        if ranged_actor:
            # Weapon/reload candidates below carry their true finite action cost;
            # a naked immediate Shoot value must not bypass that comparison.
            # Retain unavailable action boundaries unless the agreed no-hand
            # Recover fallback below keeps the rest of the battle running.
            unloaded=not ranged_weapon_is_loaded(member.ranged)
            choice=PcTacticalChoice(actor,CombatActionKind.IMPROVISE if unloaded else CombatActionKind.ATTACK,
                actor if unloaded else next(iter(enemies),None),None,-1.0,'unavailable_prepared_weapon_action',
                weapon_item_id=state.source.participant(actor).combat_equipment[0].id,ranged_reload=unloaded)
            if state.source.battlefield is not None or not usable_hands(member):
                # A real standard action keeps allies and mandatory end-phase
                # effects running; it never restores an unavailable weapon hand.
                choice=PcTacticalChoice(actor,CombatActionKind.RECOVER,actor,None,0.0,
                    'recover_without_usable_hands')

        if state.source.battlefield is not None and not needs_recover:
            from towr.domain.pc_battlefield_manoeuvre_models import proposed_pc_battlefield_manoeuvre
            proposal=proposed_pc_battlefield_manoeuvre(state)
            if proposal is not None and proposal.actor_id == actor and choice.action is CombatActionKind.RECOVER:
                choice=PcTacticalChoice(actor,CombatActionKind.MANOEUVRE,proposal.target_id,None,0.1,
                    'advance_to_usable_weapon_range',manoeuvre=proposal.kind)

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
        if (needs_recover and not (ranged_actor or net_actor)) or member.injury.conditions.has(Condition.DEFENCELESS):
            plans[actor] = choice
            return choice

        def consider(action: CombatActionKind, target: str | None, utility: float,
                     reason: str, help_policy: PcHelpPolicy | None = None, wild: bool = False,
                     weapon_item_id=None,ranged_bonus=False,ranged_reload=False,pickup_item_id=None,
                     net_item_id=None,net_release_target_id=None) -> None:
            nonlocal choice
            if (utility > choice.utility+1e-12 or
                    (abs(utility-choice.utility) <= 1e-12 and choice.wild_attack and not wild)):
                choice = PcTacticalChoice(actor, action, target, help_policy, utility, reason,wild_attack=wild,
                    weapon_item_id=weapon_item_id,ranged_bonus=ranged_bonus,ranged_reload=ranged_reload,pickup_item_id=pickup_item_id,
                    net_item_id=net_item_id,net_release_target_id=net_release_target_id)

        if net_actor:
            from towr.domain.pc_ranged_advice import net_inventory_action_choices
            for option in net_inventory_action_choices(state,actor,
                    incoming_risk=lambda prepared:incoming_risk(actor,view=prepared)):
                consider(option.action,option.target_id,option.utility,option.reason,
                    weapon_item_id=option.weapon_item_id)

        from towr.domain.pc_weighted_net_models import selected_weighted_net_recovery,PcNetRecoverKind
        net_recovery=selected_weighted_net_recovery(state,actor)
        if net_recovery is not None:
            if net_recovery.kind is PcNetRecoverKind.RELEASE:
                consider(CombatActionKind.RECOVER,actor,.3,'release_movement_blocking_net',
                    net_item_id=net_recovery.item_id,net_release_target_id=net_recovery.target_id)
            elif net_actor:
                consider(CombatActionKind.RECOVER,actor,.15,'recover_physical_net',
                    net_item_id=net_recovery.item_id)

        if ranged_actor:
            from towr.domain.pc_ranged_advice import ranged_action_choices
            if member.injury.conditions.has(Condition.PRONE):
                consider(CombatActionKind.RECOVER,actor,1.0,'restore_own_combat_readiness')
            for option in ranged_action_choices(state,actor,incoming_risk=lambda prepared:incoming_risk(actor,view=prepared)):
                consider(option.action,option.target_id,option.utility,option.reason,option.help_policy,option.wild_attack,
                    option.weapon_item_id,option.ranged_bonus,option.ranged_reload,option.pickup_item_id)

        from towr.domain.pc_melee_result_models import pc_attack_skill
        wild_eligible = (not ranged_actor and pc_wild_eligible(state,actor)
            and pc_attack_skill(state,actor) is Skill.MELEE)
        wild_risk = (max(0.0,incoming_risk(actor,stagger_added=True)-incoming_risk(actor))
            if wild_eligible else 0.0)
        if wild_eligible:
            score,target = best_attack(actor,wild=True)
            if target is not None:
                consider(CombatActionKind.ATTACK,target,score-wild_risk,'wild_attack_after_risk',wild=True)

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
            for kind in (PcHelpTarget.ATTACK, PcHelpTarget.FIRST_INCOMING_PROTECTION):
                intended=None
                if kind is PcHelpTarget.ATTACK:
                    source=state.source.participant(ally_id)
                    intended=plan(ally_id) if source.policy is PcMeleePolicy.AUTOMATIC_COMBAT and state.source.pc_activation_order.index(ally_id)>state.source.pc_activation_order.index(actor) else None
                    if intended is not None:
                        if intended.action is not CombatActionKind.ATTACK:continue
                        view=state
                        if intended.weapon_item_id is not None:
                            from towr.domain.pc_weapon_inventory import pc_weapon_inventory_view
                            view=pc_weapon_inventory_view(state,ally_id,intended.weapon_item_id)
                            if view is None:continue
                        skill=pc_attack_skill(view,ally_id)
                    else:skill=pc_attack_skill(state,ally_id)
                else:
                    from towr.domain.pc_help_models import pc_help_incoming_actor
                    incoming=pc_help_incoming_actor(state,PcHelpPolicy(ally_id,kind,Skill.ATHLETICS))
                    if incoming is None:
                        continue
                    attack_skill=state.enemy(incoming).definition.attacks[0].skill
                    if attack_skill in (Skill.SHOOTING,Skill.THROWING):
                        from towr.domain.pc_generated_ranged_advice import pc_close_shooting_protection
                        skill,_=pc_close_shooting_protection(state,ally_id,incoming,
                            pc_melee_action_id(state,incoming)+':protection')
                    else:
                        skill=pc_protection_skill(state.participant(ally_id),attack_skill)
                policy = PcHelpPolicy(ally_id, kind, skill)
                eligibility_state=state
                if intended is not None and intended.weapon_item_id is not None:
                    from towr.domain.pc_weapon_inventory import pc_weapon_inventory_view
                    eligibility_state=pc_weapon_inventory_view(state,ally_id,intended.weapon_item_id)
                    if eligibility_state is None:continue
                if skill is Skill.SHOOTING and state.source.participant(actor).pc.ranged is None:
                    continue
                if not ranged_actor and eligible_pc_help_beneficiary(eligibility_state, policy, actor,planned_choice=intended) is None:
                    continue
                if kind is PcHelpTarget.ATTACK:
                    if state.source.pc_activation_order.index(ally_id) <= state.source.pc_activation_order.index(actor):
                        continue
                    source = state.source.participant(ally_id)
                    if source.policy not in (PcMeleePolicy.AUTOMATIC_COMBAT, PcMeleePolicy.ATTACK_OR_RECOVER_SELF):
                        continue
                    if source.policy is PcMeleePolicy.AUTOMATIC_COMBAT and plan(ally_id).action is not CombatActionKind.ATTACK:
                        continue
                    ally_wild = source.policy is PcMeleePolicy.AUTOMATIC_COMBAT and plan(ally_id).wild_attack
                    intended=plan(ally_id) if source.policy is PcMeleePolicy.AUTOMATIC_COMBAT else None
                    ally_item=intended.weapon_item_id if intended is not None else None
                    ally_bonus=intended.ranged_bonus if intended is not None else False
                    before = best_attack(ally_id,wild=ally_wild,weapon_item_id=ally_item,ranged_bonus=ally_bonus)[0]
                    if ranged_actor:
                        from towr.domain.pc_ranged_advice import pc_help_mode_values
                        from towr.domain.pc_weapon_inventory import pc_weapon_inventory_view,pc_weapon_swap_used
                        inventory=member.weapon_inventory
                        for item in inventory.items:
                            if pc_weapon_swap_used(state,actor) and item.id!=inventory.active_item_id:continue
                            view=pc_weapon_inventory_view(eligibility_state,actor,item.id)
                            if view is None or eligible_pc_help_beneficiary(view,policy,actor,planned_choice=intended) is None:continue
                            help_test=_pc_test(view,actor,pc_melee_action_id(view,actor)+':help:test',skill)
                            benefit=lambda successes:max(0.0,best_attack(ally_id,successes,wild=ally_wild,weapon_item_id=ally_item,ranged_bonus=ally_bonus)[0]-before)
                            price=max(0.0,incoming_risk(actor,view=view)-incoming_risk(actor)) if item.id!=inventory.active_item_id else 0.0
                            for bonus,value in pc_help_mode_values(view,actor,skill,help_test,benefit,future_cache=help_continuations):
                                consider(CombatActionKind.HELP,ally_id,value-price,'improve_exact_upcoming_test',policy,
                                    weapon_item_id=item.id,ranged_bonus=bonus)
                            if skill is Skill.MELEE and pc_wild_eligible(view,actor):
                                prepared=pc_wild_test_variant(help_test,pc_active_weapon(view,actor),view.participant(actor).injury.conditions)
                                values=pc_help_mode_values(view,actor,skill,prepared,benefit,future_cache=help_continuations)
                                penalty=max(0.0,incoming_risk(actor,stagger_added=True,view=view)-incoming_risk(actor,view=view))
                                for _,value in values:
                                    consider(CombatActionKind.HELP,ally_id,value-price-penalty,'wild_melee_help_after_risk',policy,
                                        wild=True,weapon_item_id=item.id)
                        continue
                    help_test = test(actor,skill)
                    value = sum(probability*max(0.0, best_attack(ally_id, successes,wild=ally_wild,weapon_item_id=ally_item,ranged_bonus=ally_bonus)[0]-before)
                        for successes, probability in enumerate(pc_test_distribution(state,actor,skill,help_test)))
                    if wild_eligible and skill is Skill.MELEE:
                        prepared = pc_wild_test_variant(help_test,pc_active_weapon(state,actor),member.injury.conditions)
                        wild_value = sum(probability*max(0.0,best_attack(ally_id,successes,wild=ally_wild,weapon_item_id=ally_item,ranged_bonus=ally_bonus)[0]-before)
                            for successes,probability in enumerate(pc_test_distribution(state,actor,skill,prepared)))
                        consider(CombatActionKind.HELP,ally_id,wild_value-wild_risk,
                            'wild_melee_help_after_risk',policy,wild=True)
                else:
                    if ranged_actor and eligible_pc_help_beneficiary(eligibility_state,policy,actor,planned_choice=intended) is None:
                        continue
                    before = incoming_risk(ally_id)
                    value = sum(probability*max(0.0, before-incoming_risk(ally_id, successes))
                        for successes, probability in enumerate(pc_test_distribution(state,actor,skill,test(actor,skill))))
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
