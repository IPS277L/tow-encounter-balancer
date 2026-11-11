"""Deterministic Pistol instance, reload progress and actual hand boundaries."""
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.unit.test_k1_reload_resolution import reload_request, weapon_state
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.attack_models import AttackRequest, DamageImpactSpec, DamageProfile
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundEntryId, WoundRecord, WoundRecordOrigin
from towr.domain.pc_heavy_wound_models import PcBodyFact, PcBodyFactKind
from towr.domain.pc_melee_models import (
    PcMeleeWeapon, PcRangedProfile, PcRangedReloadHandPolicy, PcWeaponHand,
)
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.domain.pc_ranged_models import (
    build_pc_ranged_reload, complete_pc_ranged_shot, initial_pc_ranged,
    pc_ranged_unsupported, ranged_reload_declaration, prepare_pc_ranged_shot,
)
from towr.domain.reload_models import _complete_reload_action_after_test
from towr.domain.resolution_models import AttackerStaggerRequest, KernelAttackRequest
from towr.domain.test_models import DiceModifier, Skill, TestProfile, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatTurnStartRequest,
)
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.reload_resolution import execute_reload_action
from towr.rules.test_resolution import resolve_test
from towr.rules.turn_resolution import reserve_combat_action_slot, start_combat_turn


def pistol_source():
    source = make_pc_melee_scenario(weapon=PcMeleeWeapon.SWORD)
    enemy = source.enemies[0]
    protection = replace(enemy.definition.protection[0], skill=Skill.ATHLETICS)
    enemy = replace(enemy, definition=replace(enemy.definition, protection=(protection,)))
    profile = PcRangedProfile(2, 4, 3, 5, True, True, True, True,
        PcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS)
    pc = replace(source.party[0].pc, weapon=PcMeleeWeapon.PISTOL, ranged=profile)
    return replace(source, party=(replace(source.party[0], pc=pc),), enemies=(enemy,))


def pistol_state(*, empty=False):
    state = initial_pc_melee_state(pistol_source())
    round_state = start_combat_turn(CombatTurnStartRequest('turn:pc', state.round_state, 'pc')).state
    state = replace(state, round_state=round_state)
    if empty:
        state = replace(state, party=(replace(state.party[0], ranged=weapon_state(
            weapon_instance_id='pc:weapon', reload_cycle_id='pc:first:cycle')),))
    return state


def reserve(state, declaration):
    combat = reserve_combat_action_slot(CombatActionSlotRequest(
        'reserve', state.round_state, 'pc', declaration, ActionSlotGrant.STANDARD)).state
    return replace(state, round_state=combat)


def shot_request(state):
    enemy = state.enemies[0]
    attack = AttackRequest('attack', TestRequest('shooting', TestProfile(2, 4)), None,
        DamageImpactSpec(DamageProfile(5), enemy.state.current_resilience, ignores_armour=True),
        True, False)
    kernel = KernelAttackRequest('kernel', enemy.state.actor_id, attack,
        enemy.definition.injury_policy, enemy.state.injury, True, False)
    return AttackActionExecutionRequest('shoot', state.round_state, 'pc', enemy.state.actor_id, 1, kernel)


def block_hand(state, side, *, total=16):
    member = state.party[0]
    sequence = len(member.injury.wounds)+1
    entry, kind = {
        16:(WoundEntryId.SLASHED_FOREARMS, PcBodyFactKind.UNUSABLE_ARM),
        18:(WoundEntryId.SPILLING_GUTS, PcBodyFactKind.CLUTCH_STOMACH),
        20:(WoundEntryId.SEVERED_ARM, PcBodyFactKind.LOST_ARM),
    }[total]
    wound = WoundRecord(sequence, entry, total, (), effect_resolved=True,
        origin=WoundRecordOrigin.FIXED_ENTRY)
    member = replace(member, injury=replace(member.injury, wounds=(*member.injury.wounds, wound)),
        body_facts=(*member.body_facts, PcBodyFact(kind, sequence, side)))
    return replace(state, party=(member,))


class M54PistolCoreTests(unittest.TestCase):
    def test_initial_instances_are_loaded_and_actor_owned(self):
        source = pistol_source().party[0]
        first = initial_pc_ranged(source)
        second = initial_pc_ranged(replace(source, actor_id='other', fate=replace(source.fate, actor_id='other'),
            defeat_decisions=tuple(replace(d, attacker_id='other') for d in source.defeat_decisions)))
        self.assertTrue(first.loaded)
        self.assertIsNone(first.exacting)
        self.assertEqual(first.weapon_instance_id, 'pc:weapon')
        self.assertEqual(second.weapon_instance_id, 'other:weapon')
        self.assertIsNone(initial_pc_ranged(make_pc_melee_scenario().party[0]))

    def test_preparation_is_close_pistol_without_aim_and_does_not_spend(self):
        state = reserve(pistol_state(), CombatActionDeclaration(CombatActionKind.ATTACK))
        request = shot_request(state)
        prepared = prepare_pc_ranged_shot(state, request)
        self.assertIs(prepared.source_request.attack, request)
        self.assertIsNone(prepared.aim_follow_up)
        self.assertEqual(prepared.execution.next_reload_cycle_id, 'pc-melee:r1:pc:ranged:cycle')
        self.assertEqual(prepared.execution.attack, request)
        self.assertTrue(state.party[0].ranged.loaded)
        self.assertIn('RULE-EQUIPMENT-004:ignores-armour', prepared.applied_rule_ids)

    def test_hit_and_miss_spend_only_actual_instance_without_second_execution(self):
        for rolls in ([1, 10], [10, 10]):
            state = reserve(pistol_state(), CombatActionDeclaration(CombatActionKind.ATTACK))
            request = shot_request(state)
            execution = execute_attack_action(request, SequenceRandom(rolls))
            proof = complete_pc_ranged_shot(state, request, request, execution)
            self.assertIs(proof.execution.attack, execution)
            self.assertIs(proof.execution.source_request.attack, request)
            self.assertFalse(proof.execution.weapon_state.loaded)
            self.assertEqual(proof.execution.weapon_state.exacting.accumulated_successes, 0)
            self.assertEqual(len(proof.execution.weapon_state.reload_cycle_ids), 1)

    def test_reload_uses_initiative_dexterity_and_own_slot(self):
        state = pistol_state(empty=True)
        state = reserve(state, ranged_reload_declaration(state, 'pc'))
        request = build_pc_ranged_reload(state)
        self.assertEqual(request.dexterity_test.profile, TestProfile(3, 5))
        self.assertEqual(request.dexterity_test.id, 'pc-melee:r1:pc:reload:dexterity')
        self.assertEqual(request.id, 'pc-melee:r1:pc:reload:execute')
        self.assertEqual(request.slot_index, 1)
        self.assertIs(request.weapon_state, state.party[0].ranged)
        result = execute_reload_action(request, SequenceRandom([1, 1, 1]))
        self.assertTrue(result.completed)
        self.assertTrue(result.slot.executed)
        self.assertEqual(len(result.exacting.progress.contributions), 1)

    def test_shot_proof_keeps_base_preparation_and_actual_effective_test(self):
        state = reserve(pistol_state(), CombatActionDeclaration(CombatActionKind.ATTACK))
        base = shot_request(state)
        attack = base.kernel_request.attack
        effective = replace(base, kernel_request=replace(base.kernel_request, attack=replace(attack,
            attacker_test=replace(attack.attacker_test,
                dice_modifiers=(DiceModifier('fixture:effective-test', -1),)))))
        execution = execute_attack_action(effective, SequenceRandom([10]))
        proof = complete_pc_ranged_shot(state, base, effective, execution)
        self.assertIs(proof.preparation.source_request.attack, base)
        self.assertIs(proof.execution.source_request.attack, effective)
        self.assertIs(proof.execution.attack, execution)

    def test_after_test_completion_is_identical_without_rng_for_zero_partial_and_overshoot(self):
        for rolls in ([10, 10, 10], [1, 10, 10], [1, 1, 1, 1]):
            request = reload_request(weapon_state(), rolls=len(rolls))
            test = resolve_test(request.dexterity_test, SequenceRandom(rolls))
            supplied = _complete_reload_action_after_test(request, test)
            normal = execute_reload_action(request, SequenceRandom(rolls))
            self.assertEqual(supplied, normal)
            self.assertIs(supplied.exacting.test_result, test)
            self.assertEqual(supplied.exacting.progress.accumulated_successes, rolls.count(1))
            self.assertEqual(supplied.state.loaded, rolls.count(1) >= 3)

    def test_after_test_completion_rejects_another_test_source(self):
        request = reload_request(weapon_state())
        other = resolve_test(replace(request.dexterity_test, id='other'), SequenceRandom([1, 1, 1]))
        with self.assertRaises(ValueError):
            _complete_reload_action_after_test(request, other)

    def test_loaded_one_hand_shot_precedes_reload_hands_stop(self):
        for total in (16, 18, 20):
            state = block_hand(pistol_state(), PcWeaponHand.RIGHT, total=total)
            self.assertIsNone(pc_ranged_unsupported(state))
            state = reserve(state, CombatActionDeclaration(CombatActionKind.ATTACK))
            prepare_pc_ranged_shot(state, shot_request(state))
            empty = block_hand(pistol_state(empty=True), PcWeaponHand.RIGHT, total=total)
            stop = pc_ranged_unsupported(empty)
            self.assertEqual(stop.reason, 'ranged_reload_hands_unavailable')
            self.assertEqual(stop.table_total, total)
            self.assertIn('pc:weapon:pc:first:cycle', stop.source_id)
            with self.assertRaises(ValueError):
                build_pc_ranged_reload(reserve(empty, ranged_reload_declaration(empty, 'pc')))

    def test_stop_waits_for_recover_pending_and_own_unreserved_live_turn(self):
        state = block_hand(pistol_state(empty=True), PcWeaponHand.RIGHT)
        member = state.party[0]
        dropped = replace(state, party=(replace(member, weapon_hand=None),))
        self.assertIsNone(pc_ranged_unsupported(dropped))
        prone = replace(state, party=(replace(member, injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.PRONE))),))
        self.assertIsNone(pc_ranged_unsupported(prone))
        self.assertIsNone(pc_ranged_unsupported(replace(state,
            pending=(AttackerStaggerRequest('previous-attack'),), pending_actor_id='pc')))
        self.assertIsNone(pc_ranged_unsupported(reserve(state, ranged_reload_declaration(state, 'pc'))))
        defeated = replace(state.enemies[0], state=replace(state.enemies[0].state,
            injury=replace(state.enemies[0].state.injury, wounds=1, defeated=True)))
        self.assertIsNone(pc_ranged_unsupported(replace(state, enemies=(defeated,))))
        self.assertIsNone(pc_ranged_unsupported(replace(state, round_state=replace(state.round_state, active_turn=None))))

    def test_no_usable_hand_uses_latest_blocking_wound_and_grip_boundary(self):
        state = block_hand(pistol_state(), PcWeaponHand.RIGHT, total=16)
        state = block_hand(state, PcWeaponHand.LEFT, total=20)
        stop = pc_ranged_unsupported(state)
        self.assertEqual(stop.reason, 'ranged_grip_unavailable')
        self.assertEqual((stop.wound_sequence, stop.table_total), (2, 20))
        self.assertIn('pc:weapon:initial-loaded', stop.source_id)


if __name__ == '__main__':
    unittest.main()
