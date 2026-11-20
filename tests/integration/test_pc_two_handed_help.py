"""Actual K1 Help interacts with 2H weapon, Reload and physical Net owners.

Prepared action boundaries isolate source-owned interactions without inventing
a complete native battle prefix or replacing the automatic tactical selector.
The individual Help, Reload and Attack receipts below are real executions.
"""
from copy import deepcopy
from dataclasses import fields, replace
from types import SimpleNamespace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.attack_models import AttackRequest, AttackOutcome
from towr.domain.help_models import HELP_BONUS_RULE_ID, HelpActionExecutionRequest
from towr.domain.pc_combat_equipment_models import PcItemLocation, PcWeaponItem
from towr.domain.pc_help_models import build_pc_test_help, pc_help_weapon_use
from towr.domain.pc_melee_models import (
    PcMeleePolicy, PcMeleeWeapon, PcRangedProfile, PcRangedReloadHandPolicy,
    PcRepeaterBonusPolicy, PcShortRangeOpening, PcTwoHandedGrip,
)
from towr.domain.pc_melee_result_models import PcHelpProof, _pc_test, initial_pc_melee_state, pc_melee_action_id
from towr.domain.pc_ranged_models import (
    PcRangedHelpUseProof, build_pc_ranged_reload, complete_pc_ranged_help,
    pc_repeater_attack_modifiers, ranged_reload_declaration,
)
from towr.domain.pc_weighted_net_models import (
    PcNetLocation, complete_weighted_net_throw, weighted_net_for_actor, weighted_net_profile,
)
from towr.domain.ranged_weapon_profiles import REPEATER_SHOOTING_BONUS_RULE_ID
from towr.domain.reload_models import FreeReloadWeaponState, ReloadableWeaponState
from towr.domain.resolution_models import KernelAttackRequest, TargetInjuryPolicy
from towr.domain.test_models import Skill
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundState, CombatTurnStartRequest,
)
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.help_resolution import execute_help_action
from towr.rules.reload_resolution import execute_reload_action
from towr.rules.test_resolution import resolve_test
from towr.rules.turn_resolution import reserve_combat_action_slot, start_combat_turn


def ranged_source(weapon):
    from tests.support.pc_weapon_sources import initial_weapon_items
    source = make_pc_melee_party_scenario(pc_count=2, enemy_count=1, max_rounds=4)
    free = weapon is PcMeleeWeapon.SHORTBOW
    profile = PcRangedProfile(ballistic_skill=3, shooting=4, ammunition_supply_confirmed=True,  has_blackpowder_lore=None if free else True, has_blackpowder_kit=None if free else True, reload_hand_policy=None if free else PcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS, repeater_bonus_policy=None if free else PcRepeaterBonusPolicy.WHEN_AVAILABLE)
    party = tuple(replace(member, pc=replace(member.pc, weapon=weapon, ranged=profile, initiative=None if free else 2,dexterity=None if free else 6),
        initial_weapon_hand=PcTwoHandedGrip.BOTH,combat_equipment=initial_weapon_items(
            weapon,PcTwoHandedGrip.BOTH,initially_loaded=None if free else True))
        for member in source.party)
    enemies = tuple(replace(enemy, definition=replace(enemy.definition,
        protection=(replace(enemy.definition.protection[0], skill=Skill.ATHLETICS),)))
        for enemy in source.enemies)
    return replace(source, party=party, enemies=enemies,
        facts=replace(source.facts, all_opponents_close=False, outnumbering_bonus_approved=False),
        short_range_opening=PcShortRangeOpening(True, True))


def net_source():
    source = make_pc_melee_party_scenario(pc_count=2, enemy_count=1, max_rounds=2)
    party = tuple(replace(member, pc=replace(member.pc, weapon=PcMeleeWeapon.WEIGHTED_NET,
        ballistic_skill=2, throwing=4, brawn=4), policy=PcMeleePolicy.AUTOMATIC_COMBAT,
        initial_weapon_hand=PcTwoHandedGrip.BOTH, combat_equipment=(PcWeaponItem(
            'net:' + member.actor_id, PcMeleeWeapon.WEIGHTED_NET,
            PcItemLocation.HELD, PcTwoHandedGrip.BOTH),)) for member in source.party)
    enemies = tuple(replace(enemy, definition=replace(enemy.definition,
        protection=(replace(enemy.definition.protection[0], skill=Skill.ATHLETICS),)))
        for enemy in source.enemies)
    return replace(source, party=party, enemies=enemies)


def boundary(initial, actor, declaration, *, round_number=1, party=None, history=()):
    """Prepare a real fresh action clock; this is not a native journal claim."""
    clock = CombatRoundState(round_number, initial.round_state.participants)
    if actor != initial.source.pc_activation_order[0]:
        preceding = initial.source.pc_activation_order[:initial.source.pc_activation_order.index(actor)]
        clock = replace(clock, completed_turn_entity_ids=preceding)
    clock = start_combat_turn(CombatTurnStartRequest(
        f'boundary:{actor}:{round_number}:start', clock, actor)).state
    view = SimpleNamespace(**{field.name: getattr(initial, field.name) for field in fields(initial)})
    view.round_state, view.history = clock, history
    view.party = initial.party if party is None else party
    view.participant = lambda actor: next(member for member in view.party if member.actor_id == actor)
    view.enemy = lambda actor: next(enemy for enemy in view.enemies if enemy.state.actor_id == actor)
    view.live_party = tuple(member for member in view.party if not member.injury.dead)
    view.live_enemies = tuple(enemy for enemy in view.enemies if not enemy.state.injury.defeated)
    view.exited_npc_ids = ()
    if declaration is None:
        declaration = ranged_reload_declaration(view, actor)
    view.round_state = reserve_combat_action_slot(CombatActionSlotRequest(
        f'boundary:{actor}:{round_number}:reserve', clock, actor, declaration,
        ActionSlotGrant.STANDARD)).state
    return view


def help_boundary(source, skill):
    initial = initial_pc_melee_state(source)
    state = boundary(initial, 'pc1', CombatActionDeclaration(CombatActionKind.HELP))
    action = pc_melee_action_id(state, 'pc1')
    test = _pc_test(state, 'pc1', action + ':help:test', skill)
    if skill is Skill.SHOOTING:
        test = replace(test, dice_modifiers=(*test.dice_modifiers,
            *pc_repeater_attack_modifiers(state, 'pc1')))
    request = HelpActionExecutionRequest(action + ':help:execute', state.round_state,
        'pc1', state.participant('pc1').injury.conditions, 'pc2',
        pc_melee_action_id(state, 'pc2') + ':attack', 1, test, skill, skill)
    return initial, state, request


def execute_help(request, values):
    rng = ScriptedD10(values)
    result = execute_help_action(request, rng)
    rng.assert_exhausted()
    return result


class PcTwoHandedHelpTests(unittest.TestCase):
    def test_free_bow_help_keeps_weapon_ready_and_binds_the_exact_ally_shooting_test(self):
        source = ranged_source(PcMeleeWeapon.SHORTBOW)
        initial, state, request = help_boundary(source, Skill.SHOOTING)
        original = deepcopy(initial)
        execution = execute_help(request, (1, 1, 1))
        use = complete_pc_ranged_help(state, request, request, execution)
        self.assertIs(type(use), PcRangedHelpUseProof)
        self.assertIs(type(use.weapon_state), FreeReloadWeaponState)
        self.assertEqual(use.previous_weapon_state, use.weapon_state)
        self.assertFalse(use.uses_optional_reload_bonus)
        self.assertIsNone(use.next_reload_cycle_id)
        self.assertEqual(execution.bonus.bonus_dice, 3)
        self.assertIs(execution.slot.declaration.kind, CombatActionKind.HELP)
        proof = PcHelpProof(request, execution, None, ranged_use=use,weapon_use=pc_help_weapon_use(state))
        recipient = boundary(initial, 'pc2', CombatActionDeclaration(CombatActionKind.ATTACK), history=(proof,))
        test_id = pc_melee_action_id(recipient, 'pc2') + ':attack'
        base = _pc_test(recipient, 'pc2', test_id, Skill.SHOOTING)
        augmented, applications = build_pc_test_help(recipient, 'pc2', Skill.SHOOTING, base)
        self.assertEqual(len(applications), 1)
        self.assertEqual(applications[0].source_request.help, execution)
        self.assertEqual(tuple(mod.amount for mod in augmented.dice_modifiers
            if mod.rule_id == HELP_BONUS_RULE_ID), (3,))
        rng = ScriptedD10((1,) * 6)
        result = resolve_test(augmented, rng)
        rng.assert_exhausted()
        self.assertEqual((result.trace.pool_cap, result.trace.rolled_dice, result.successes), (6, 6, 6))
        foreign, unused = build_pc_test_help(recipient, 'pc2', Skill.SHOOTING,
            replace(base, id=base.id + ':foreign'))
        self.assertEqual(foreign.dice_modifiers, base.dice_modifiers)
        self.assertEqual(unused, ())
        self.assertEqual(initial, original)

    def test_repeater_handgun_help_opens_real_reload_five_and_requires_all_five_successes(self):
        initial, state, request = help_boundary(ranged_source(PcMeleeWeapon.REPEATER_HANDGUN), Skill.SHOOTING)
        execution = execute_help(request, (1,) * 6)
        use = complete_pc_ranged_help(state, request, request, execution)
        self.assertTrue(use.uses_optional_reload_bonus)
        self.assertIs(type(use.weapon_state), ReloadableWeaponState)
        self.assertEqual(tuple(mod.amount for mod in use.source_test.dice_modifiers
            if mod.rule_id == REPEATER_SHOOTING_BONUS_RULE_ID), (3,))
        self.assertFalse(use.weapon_state.loaded)
        self.assertEqual(use.weapon_state.required_successes, 5)
        self.assertEqual(use.weapon_state.exacting.accumulated_successes, 0)
        self.assertEqual(use.weapon_state.reload_cycle_ids, (use.next_reload_cycle_id,))
        self.assertEqual(execution.bonus.bonus_dice, 6)
        current = use.weapon_state
        from towr.domain.pc_weapon_inventory import replace_pc_member
        current_member=replace_pc_member(initial.participant('pc1'),ranged=current)
        results = []
        for round_number in (2, 3, 4):
            party = (current_member, initial.participant('pc2'))
            reload_state = boundary(initial, 'pc1', None,
                round_number=round_number, party=party)
            reload_request = build_pc_ranged_reload(reload_state)
            self.assertEqual(reload_request.weapon_state, current)
            rng = ScriptedD10((1, 1))
            result = execute_reload_action(reload_request, rng)
            rng.assert_exhausted()
            self.assertIs(result.slot.declaration.kind, CombatActionKind.IMPROVISE)
            self.assertEqual(result.exacting.test_result.successes, 2)
            self.assertEqual(result.state.required_successes, 5)
            self.assertEqual(result.state.weapon_instance_id, use.previous_weapon_state.weapon_instance_id)
            self.assertEqual(result.state.reload_cycle_ids, use.weapon_state.reload_cycle_ids)
            current = result.state
            current_member=replace_pc_member(current_member,ranged=current)
            results.append(result)
        self.assertEqual(tuple(result.state.loaded for result in results), (False, False, True))
        self.assertEqual(len({result.slot.execution.id for result in results}), 3)
        with self.assertRaises(ValueError):
            replace(use.weapon_state, required_successes=3)
        with self.assertRaises(ValueError):
            replace(use, source_test=replace(use.source_test,
                dice_modifiers=(*use.source_test.dice_modifiers, *use.source_test.dice_modifiers)))

    def test_throwing_help_preserves_the_physical_net_until_its_real_attack(self):
        initial, state, request = help_boundary(net_source(), Skill.THROWING)
        bank = deepcopy(state.weighted_nets)
        helper = weighted_net_for_actor(state, 'pc1')
        self.assertIs(helper.location, PcNetLocation.HELD)
        execution = execute_help(request, (1, 1))
        self.assertIsNone(complete_pc_ranged_help(state, request, request, execution))
        self.assertEqual(state.weighted_nets, bank)
        self.assertEqual(weighted_net_for_actor(state, 'pc1'), helper)
        self.assertIs(execution.slot.declaration.kind, CombatActionKind.HELP)
        self.assertEqual(execution.bonus.bonus_dice, 2)
        proof = PcHelpProof(request, execution, None,
            weapon_use=pc_help_weapon_use(state),
            beneficiary_weapon_item_id=initial.participant('pc2').weapon_inventory.active_item_id)
        recipient = boundary(initial, 'pc2', CombatActionDeclaration(CombatActionKind.ATTACK), history=(proof,))
        recipient_test = _pc_test(recipient, 'pc2', pc_melee_action_id(recipient, 'pc2') + ':attack', Skill.THROWING)
        assisted, applications = build_pc_test_help(recipient, 'pc2', Skill.THROWING, recipient_test)
        self.assertEqual(tuple(application.modifier.amount for application in applications), (2,))
        rng = ScriptedD10((1,) * 4)
        tested = resolve_test(assisted, rng)
        rng.assert_exhausted()
        self.assertEqual((tested.trace.base_dice, tested.trace.pool_cap, tested.trace.rolled_dice), (2, 4, 4))
        self.assertEqual(initial.weighted_nets, bank)
        # A later actual Attack, as distinct from a Help Test, throws this same
        # helper-owned Net. Its real landing supplies the physical transition.
        throwing = boundary(initial, 'pc1', CombatActionDeclaration(CombatActionKind.ATTACK), round_number=2)
        profile = weighted_net_profile(2, 4, 3)
        test = _pc_test(throwing, 'pc1', 'net:actual:throwing', Skill.THROWING)
        attack = AttackRequest('net:actual:test', test, None, profile.condition_impact, True, False)
        kernel = KernelAttackRequest('net:actual:kernel', 'minion1', attack, TargetInjuryPolicy.MINION,
            throwing.enemy('minion1').state.injury, False, False)
        attack_request = AttackActionExecutionRequest('net:actual:execute', throwing.round_state,
            'pc1', 'minion1', 1, kernel)
        rng = ScriptedD10((1, 10))
        actual = execute_attack_action(attack_request, rng)
        rng.assert_exhausted()
        self.assertIs(actual.resolution.attack.outcome, AttackOutcome.HIT)
        landing = complete_weighted_net_throw(throwing, attack_request, actual)
        self.assertEqual(landing.previous_item, helper)
        self.assertEqual(landing.item.item_id, helper.item_id)
        self.assertEqual(landing.item.owner_id, 'pc1')
        self.assertIs(landing.item.location, PcNetLocation.BOUND)
        self.assertEqual(landing.item.bound_target_id, 'minion1')
        self.assertEqual(landing.item.binding.attack_id, attack_request.id)
        self.assertEqual(initial.weighted_nets, bank)


if __name__ == '__main__':
    unittest.main()
