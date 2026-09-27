from copy import deepcopy
from dataclasses import replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_kernel import FixedKernelDecisions
from tests.unit.test_m2_npc_attack_controller import candidate, request
from tests.unit.test_m2_npc_roster_attack_execution import change_participant
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.npc_attack_selection_models import NpcAttackSelectionBlock as Block
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.resolution_models import GiveGroundRequest
from towr.engine import npc_attack_controller as controller
from towr.rules import attack_action_execution as attack_executor
from towr.rules.npc_roster_attack_execution import apply_npc_roster_attack_result, execute_npc_roster_attack


class M2NpcAttackControllerExecutionTests(unittest.TestCase):
    def test_multiple_targets_selection_prepares_and_executes_once_in_eight_cases(self):
        for weapon, aware, hit in product(("axe", "warbow"), (False, True), (False, True)):
            with self.subTest(weapon=weapon, aware=aware, hit=hit):
                source = request()
                invalid = candidate(source.state, "out-of-reach", attack=weapon)
                invalid = (replace(invalid, target_range=Range.LONG) if weapon == "axe"
                           else replace(invalid, has_enemy_in_close_range=True))
                preferred = candidate(source.state, "preferred", target_id="brigand:3", attack=weapon, aware=aware)
                later = candidate(source.state, "later", attack=weapon, aware=aware)
                source = replace(source, candidates=(invalid, preferred, later))
                before = deepcopy(source)
                dice = ([1, 2, 10] if hit else [10] * 3) + ([10] * 3 if aware else [])
                rng = Mock(wraps=SequenceRandom([*dice, 7]))
                with patch.object(controller, "prepare_npc_attack_protection",
                                  wraps=controller.prepare_npc_attack_protection) as preparation:
                    selected = controller.select_npc_attack(source)
                preparation.assert_called_once()
                rng.randint.assert_not_called()
                self.assertEqual(selected.selected_candidate.id, "preferred")
                self.assertEqual(len(selected.rejected), 1)
                executable = controller.require_current_npc_attack_selection(
                    selected, source.state, source.round_state, pending_follow_ups=source.pending_follow_ups)
                with patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel:
                    result = execute_npc_roster_attack(executable, rng)
                kernel.assert_called_once()
                self.assertEqual(rng.randint.call_count, len(dice))
                current = apply_npc_roster_attack_result(source.state, result)
                self.assertEqual(result.execution.target_id, "brigand:3")
                self.assertEqual(current.roster.participant("brigand:3").state.injury.defeated, hit)
                self.assertIs(current.roster.participant("brigand:2"), source.state.roster.participant("brigand:2"))
                self.assertEqual(current.consumed_execution_ids, (source.execution_id,))
                self.assertEqual(result.execution.slot.execution.id, source.execution_id)
                self.assertEqual(source, before)
                self.assertTrue(set(executable.preparation.applied_rule_ids) <= set(result.applied_rule_ids))
                self.assertEqual(rng.randint(1, 10), 7)
                after = replace(source, state=current, round_state=result.execution.state,
                                pending_follow_ups=result.pending_follow_ups)
                blocked = controller.select_npc_attack(after)
                self.assertIs(blocked.blocked_reason, Block.PENDING_FOLLOW_UPS if hit else Block.SLOT_EXECUTED)
                self.assertEqual(blocked.pending_follow_ups, result.pending_follow_ups)

    def test_returned_history_prevents_reuse_even_with_old_unexecuted_round(self):
        source = request()
        source = replace(source, candidates=(candidate(source.state, "ranged", attack="warbow", aware=False),))
        selected = controller.select_npc_attack(source)
        executable = controller.require_current_npc_attack_selection(selected, source.state, source.round_state,
                                                                    pending_follow_ups=())
        result = execute_npc_roster_attack(executable, SequenceRandom([10, 10, 10]))
        current = apply_npc_roster_attack_result(source.state, result)
        self.assertEqual(current.roster, source.state.roster)
        blocked = controller.select_npc_attack(replace(source, state=current))
        self.assertIs(blocked.blocked_reason, Block.EXECUTION_CONSUMED)
        rng = Mock()
        with self.assertRaisesRegex(ValueError, "stale"):
            execute_npc_roster_attack(controller.require_current_npc_attack_selection(
                selected, current, result.execution.state, pending_follow_ups=()), rng)
        rng.randint.assert_not_called()

    def test_real_give_ground_blocks_next_selection_and_preserves_exact_follow_up(self):
        source = request()
        target = source.state.roster.participant("brigand:2")
        state = change_participant(source.state, 2, injury=replace(target.state.injury,
            conditions=target.state.injury.conditions.with_condition(Condition.STAGGERED)))
        source = replace(source, state=state)
        selected = controller.select_npc_attack(source)
        result = execute_npc_roster_attack(controller.require_current_npc_attack_selection(
            selected, state, source.round_state, pending_follow_ups=()), SequenceRandom([1, 10, 10, 10, 10, 10]),
            decisions=FixedKernelDecisions(stagger=StaggerChoice.GIVE_GROUND))
        self.assertIsInstance(result.pending_follow_ups[0], GiveGroundRequest)
        next_source = replace(source, state=result.state, round_state=result.execution.state,
                              pending_follow_ups=result.pending_follow_ups)
        with patch.object(controller, "prepare_npc_attack") as prepare:
            blocked = controller.select_npc_attack(next_source)
        prepare.assert_not_called()
        self.assertIs(blocked.blocked_reason, Block.PENDING_FOLLOW_UPS)
        self.assertIs(blocked.pending_follow_ups[0], result.pending_follow_ups[0])
        self.assertIsNone(blocked.execution_request)
