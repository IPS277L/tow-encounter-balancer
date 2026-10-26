from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import random
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_kernel import FixedKernelDecisions
from tests.unit.test_m8_npc_roster_minion_attack import request as attack_request, changed_roster
from tests.unit.test_m8_npc_magic_scenario import scenario
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.magic_models import WizardMagicState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_roster_minion_defeat_models import NpcRosterMinionDefeatRequest, NpcRosterMinionDefeatResult
from towr.domain.resolution_models import GiveGroundRequest
from towr.rules.npc_roster_minion_attack_resolution import execute_npc_roster_minion_attack
from towr.rules.npc_roster_minion_defeat_resolution import (
    acknowledge_npc_roster_minion_defeat as acknowledge, apply_npc_roster_minion_defeat_result as apply,
)


def defeated():
    return execute_npc_roster_minion_attack(attack_request(), SequenceRandom((1, 2, 3, 10, 10, 10))).state


def request(state=None, disposition=NpcDefeatDisposition.KNOCKED_OUT):
    state = defeated() if state is None else state
    raw = state.pending_minion_attack
    return NpcRosterMinionDefeatRequest('ack:minion', state,
        MinionDefeatDecision(raw.execution.actor_id, raw.execution.target_id, disposition, True))


class RosterMinionDefeatTests(unittest.TestCase):
    def test_all_dispositions_close_exact_pending_and_exclude_waiting_target(self):
        for disposition in NpcDefeatDisposition:
            with self.subTest(disposition=disposition):
                source = request(disposition=disposition); old = source.state
                result = acknowledge(source); final = apply(old, result)
                self.assertIs(result.source, source)
                self.assertIs(result.source.decision.disposition, disposition)
                self.assertTrue(result.excludes_target)
                self.assertIsNone(final.pending_minion_attack)
                self.assertEqual(final.minion_attack.acknowledged_defeat_execution_ids, ('minion:attack',))
                self.assertEqual(final.minion_attack.consumed_execution_ids, old.minion_attack.consumed_execution_ids)
                self.assertEqual(final.consumed_execution_ids, old.consumed_execution_ids)
                self.assertEqual(final.round_state.excluded_turn_entity_ids, ('enemy',))
                self.assertEqual(final.round_state.completed_turn_entity_ids, ())
                self.assertEqual(final.round_state.participants, old.round_state.participants)
                self.assertEqual(final.round_state.side_order, old.round_state.side_order)
                self.assertIs(final.round_state.active_turn, old.round_state.active_turn)
                self.assertIs(final.roster, old.roster)
                self.assertIs(final.spatial_state, old.spatial_state)
                self.assertIs(final.wizard, old.wizard)
                self.assertEqual(final.champion_attack.round_state, final.round_state)
                self.assertIs(final.champion_attack.daily_wounds, old.champion_attack.daily_wounds)
                self.assertEqual(final.roster.participant('enemy').state.available_attack_ids, ('shot',))
                self.assertIn('RULE-NPC-002', result.applied_rule_ids)

    def test_no_attack_test_rng_or_dummy_minion_only_round(self):
        source = request(); before = deepcopy(source); global_rng = random.getstate()
        with (patch('towr.domain.minion_defeat_models.NpcRoundRequest', side_effect=AssertionError('no dummy M2 round')),
              patch('towr.rules.attack_action_execution.execute_attack_action', side_effect=AssertionError('no Attack')),
              patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no Test'))):
            result = acknowledge(source)
            final = apply(source.state, result)
            self.assertEqual(final, result.state)
        self.assertEqual(source, before)
        self.assertEqual(global_rng, random.getstate())

    def test_replay_new_phase_id_new_choice_and_requeue_are_rejected(self):
        source = request(); result = acknowledge(source); final = result.state
        with self.assertRaisesRegex(ValueError, 'already acknowledged'): apply(final, result)
        for changes in ({'id': 'new-phase'}, {'decision': replace(source.decision, disposition=NpcDefeatDisposition.KILLED)}):
            with self.assertRaisesRegex(ValueError, 'current full pending'):
                replace(source, state=final, **changes)
        with self.assertRaisesRegex(ValueError, 'pending Minion attack'):
            replace(final, pending_minion_attack=source.state.pending_minion_attack)

    def test_stale_magic_spatial_phase_history_and_owner_are_rejected(self):
        source = request(); result = acknowledge(source)
        for changes in ({'wizard': replace(source.state.wizard, magic_state=WizardMagicState(1))},
                        {'spatial_state': replace(source.state.spatial_state, free_move_used_entity_ids=('wizard',))},
                        {'champion_attack': None}):
            with self.assertRaisesRegex(ValueError, 'stale full source'):
                apply(replace(source.state, **changes), result)

    def test_decision_requires_gm_and_exact_actor_target(self):
        source = request()
        for decision in (replace(source.decision, gm_approved=False),
                         replace(source.decision, attacker_id='wizard'),
                         replace(source.decision, target_id='wizard')):
            with self.assertRaises(ValueError): replace(source, decision=decision)

    def test_types_ids_and_immutable_source(self):
        source = request(); result = acknowledge(source)
        with self.assertRaises(ValueError): replace(source, id='')
        for changes in ({'id': False}, {'state': None}, {'decision': None}):
            with self.assertRaises(TypeError): replace(source, **changes)
        for value in (None, source.state):
            with self.assertRaises(TypeError): acknowledge(value)
            with self.assertRaises(TypeError): NpcRosterMinionDefeatResult(value)
        with self.assertRaises(TypeError): apply(source.state, source)
        with self.assertRaises(TypeError): apply(None, result)
        with self.assertRaises(FrozenInstanceError): source.id = 'other'
        with self.assertRaises(FrozenInstanceError): result.source = None
        self.assertEqual(replace(result), result)

    def test_missing_or_non_defeat_pending_does_not_authorize_acknowledgement(self):
        source = request()
        with self.assertRaisesRegex(ValueError, 'current full pending'):
            replace(source, state=scenario().initial_runtime_state)
        state = changed_roster(scenario().initial_runtime_state, lambda p: replace(p, state=replace(p.state,
            injury=replace(p.state.injury, conditions=p.state.injury.conditions.with_condition(Condition.STAGGERED))))
            if p.state.actor_id == 'enemy' else p)
        pending = execute_npc_roster_minion_attack(attack_request(state), SequenceRandom((1, 10, 10, 1, 10, 10)),
            decisions=FixedKernelDecisions(stagger=StaggerChoice.GIVE_GROUND)).state
        with self.assertRaisesRegex(ValueError, 'ProfileStateChange'):
            replace(source, state=pending)
        self.assertIsNotNone(pending.pending_minion_attack)

    def test_anonymous_identical_follow_up_cannot_close_a_different_attack(self):
        source = request(); result = acknowledge(source)
        other = execute_npc_roster_minion_attack(attack_request(identifier='other:attack'),
            SequenceRandom((1, 2, 3, 10, 10, 10))).state
        self.assertEqual(other.pending_minion_attack.pending_follow_ups, source.state.pending_minion_attack.pending_follow_ups)
        with self.assertRaisesRegex(ValueError, 'stale full source'): apply(other, result)

    def test_additional_follow_up_is_preserved_by_rejecting_unsupported_queue(self):
        source = request(); attack = source.state.pending_minion_attack
        execution = replace(attack.execution, resolution=replace(attack.execution.resolution,
            follow_ups=(*attack.execution.resolution.follow_ups, GiveGroundRequest('other'))))
        raw = replace(attack, execution=execution)
        pending = replace(source.state, pending_minion_attack=raw)
        with self.assertRaisesRegex(ValueError, 'separate consumer'):
            replace(source, state=pending)
        self.assertEqual(len(pending.pending_minion_attack.pending_follow_ups), 2)

    def test_preserves_prior_family_acknowledgement_and_execution_order(self):
        state = scenario().initial_runtime_state
        state = replace(state, consumed_execution_ids=('old:minion', 'old:cast'),
            minion_attack=replace(state.minion_attack, consumed_execution_ids=('old:minion',),
                                  acknowledged_defeat_execution_ids=('old:minion',)))
        state = execute_npc_roster_minion_attack(attack_request(state), SequenceRandom((1, 2, 3, 10, 10, 10))).state
        final = acknowledge(request(state)).state
        self.assertEqual(final.minion_attack.acknowledged_defeat_execution_ids, ('old:minion', 'minion:attack'))
        self.assertEqual(final.consumed_execution_ids, ('old:minion', 'old:cast', 'minion:attack'))


if __name__ == '__main__':
    unittest.main()
