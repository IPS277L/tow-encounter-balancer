"""Actual M8 raw origins -> prepared -> rolled pending; no effect/runner policy."""
from copy import deepcopy
from dataclasses import fields, replace
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from tests.unit.test_m8_npc_roster_miscast_preparation import casting_pending, interruption_pending
from tests.unit.test_m8_npc_roster_miscast_roll import request
from tests.unit.test_m8_npc_broken_run import request as broken_run_request
from tests.unit.test_m8_npc_roster_minion_attack import request as minion_attack_request
from tests.unit.test_m8_npc_roster_casting_completion import begin, completion_request
from tests.unit.test_m8_npc_roster_dead_champion import final_attack
from tests.integration.test_m8_champion_casting_handoff import incoming_attack
from towr.domain.npc_broken_recover_models import NpcBrokenRecoverRequest
from towr.domain.npc_magic_journal_policy import validate_magic_step_policy
from towr.domain.npc_magic_scenario_result_models import diagnose_npc_magic_unsupported, npc_magic_terminal_outcome
from towr.domain.npc_magic_step_models import NpcMagicStep, NpcMagicUnsupportedReason as Reason, NpcMagicPhase
from towr.domain.npc_roster_casting_models import NpcRosterCastingRequest
from towr.domain.npc_roster_casting_completion_models import NpcRosterCastingCompletionRequest
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackRequest
from towr.domain.npc_roster_dead_champion_models import NpcRosterDeadChampionExclusionRequest
from towr.domain.npc_roster_minion_attack_models import NpcRosterMinionAttackRequest
from towr.domain.npc_roster_minion_defeat_models import NpcRosterMinionDefeatRequest
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartRequest, NpcRosterRoundAdvanceRequest
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.test_models import InlineProfile
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting
from towr.rules.npc_roster_miscast_resolution import (
    roll_npc_roster_miscast as roll, apply_npc_roster_miscast_roll as apply,
)


class MiscastRollIntegrationTests(unittest.TestCase):
    def test_raw_prepared_rolled_have_distinct_canonical_continuation_diagnoses(self):
        scenario, raw = casting_pending()
        source = request(raw); result = roll(source, Dice((7, 7, 7)))
        for state, reason, source_id in (
                (raw, Reason.MISCAST_PREPARATION, raw.pending_miscast.source.id),
                (source.state, Reason.MISCAST_ROLL, source.id),
                (result.state, Reason.MISCAST_EFFECT, result.effect_request.resolution_id)):
            with self.subTest(reason=reason):
                diagnosis = diagnose_npc_magic_unsupported(scenario, state, 'caller:irrelevant')
                self.assertIs(diagnosis.phase, NpcMagicPhase.CONTINUATION)
                self.assertIs(diagnosis.reason, reason)
                self.assertEqual(diagnosis.source_id, source_id)
                self.assertEqual(diagnosis.actor_id, raw.wizard.actor_id)
                self.assertIsNone(npc_magic_terminal_outcome(scenario, state))

    def test_non_wind_entry_is_a_pending_effect_with_its_actual_trace_and_pool(self):
        scenario, raw = casting_pending(); source = request(raw)
        rng = Dice((10, 10, 10)); result = roll(source, rng); rng.exhausted()
        final = apply(source.state, result)
        self.assertEqual(result.effect_request.total, 30)
        self.assertEqual(result.effect_request.roll_values, (10, 10, 10))
        self.assertEqual(final.wizard.magic_state.miscast_dice, 3)
        self.assertIs(final.pending_miscast_continuation, result)
        self.assertIsNone(npc_magic_terminal_outcome(scenario, final))
        stop = diagnose_npc_magic_unsupported(scenario, final, 'last:action')
        self.assertIs(stop.reason, Reason.MISCAST_EFFECT)
        self.assertEqual(stop.source_id, result.effect_request.resolution_id)

    def test_actual_defeated_archive_and_live_casting_proof_survive_both_phases(self):
        _, raw = casting_pending(archive=True)
        source = request(raw); result = roll(source, Dice((10, 10, 2))); final = result.state
        origin = result.source.state.pending_miscast_continuation.source.state
        self.assertIs(origin, raw)
        self.assertEqual(len(origin.round_state.participants), 4)
        self.assertEqual(len(origin.pending_miscast.round_state.participants), 3)
        self.assertEqual(origin.pending_miscast.round_state, origin.casting_round_state)
        self.assertTrue(final.roster.participant('enemy').state.injury.defeated)
        self.assertEqual(final.round_state.excluded_turn_entity_ids, ('enemy',))
        self.assertEqual(len(final.spatial_state.placements), 4)
        for field in fields(raw):
            if field.name not in ('wizard', 'pending_miscast', 'pending_miscast_continuation'):
                with self.subTest(field=field.name):
                    self.assertEqual(getattr(final, field.name), getattr(raw, field.name))

    def test_actual_bound_recover_run_origins_keep_wound_daily_expiry_usage_and_receipts(self):
        for run in (False, True):
            with self.subTest(run=run):
                raw = interruption_pending(run=run); before = deepcopy(raw)
                source = request(raw); rng = Dice((7, 7, 7))
                result = roll(source, rng); rng.exhausted(); final = apply(source.state, result)
                origin = result.source.state.pending_miscast_continuation.source.state
                self.assertIs(origin.pending_interruption, raw.pending_interruption)
                self.assertEqual(final.roster, raw.roster)
                self.assertEqual(final.champion_attack, raw.champion_attack)
                self.assertEqual(final.minion_attack, raw.minion_attack)
                self.assertEqual(final.wound_expiries, raw.wound_expiries)
                self.assertEqual(final.wound_turn_end_receipts, raw.wound_turn_end_receipts)
                self.assertEqual(final.consumed_execution_ids, raw.consumed_execution_ids)
                self.assertEqual(final.round_state, raw.round_state)
                self.assertEqual(final.spatial_state, raw.spatial_state)
                self.assertEqual(final.spatial_state.free_move_used_entity_ids, (raw.wizard.actor_id,))
                self.assertIsNone(final.pending_interruption)
                self.assertEqual(final.wizard.magic_state.miscast_dice, raw.wizard.magic_state.miscast_dice)
                self.assertEqual(raw, before)

    def test_all_bound_actions_scheduling_and_end_remain_blocked_by_rolled_prefix(self):
        scenario, raw = casting_pending(); source = request(raw)
        result = roll(source, Dice((7, 7, 7))); final = result.state
        casting = raw.pending_miscast.source
        minion = minion_attack_request().attack
        champion = incoming_attack().attack
        decision = scenario.policy_for('ally').defeat_decisions[0]
        blocked = (
            lambda: NpcRosterCastingRequest(final, casting),
            lambda: prepare_npc_roster_casting(request_id='next:cast', state=final,
                selected_zone_id='arena', targets=(), facts=casting.facts, policy=casting.policy),
            lambda: NpcRosterChampionAttackRequest(final, champion),
            lambda: NpcRosterMinionAttackRequest(final, minion),
            lambda: NpcRosterMinionDefeatRequest('next:defeat', final, decision),
            lambda: NpcRosterTurnStartRequest('next:start', final, final.wizard.actor_id,
                CombatActionDeclaration(CombatActionKind.RECOVER)),
            lambda: NpcRosterRoundAdvanceRequest('next:round', final),
            lambda: NpcWoundTurnEndRequest('next:end', final, final.wizard.actor_id),
            lambda: NpcBrokenRecoverRequest('next:recover', final, final.wizard.actor_id,
                InlineProfile(3, 3), None, True, True),
            lambda: replace(broken_run_request(), state=final),
        )
        with patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no Test')), \
             patch('towr.rules.npc_roster_miscast_resolution.resolve_miscast_roll', side_effect=AssertionError('no reroll')), \
             patch('random.Random', side_effect=AssertionError('no RNG')):
            for operation in blocked:
                with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, '(?i)miscast'):
                    operation()
        _, _, moving, _ = begin()
        with self.assertRaises(ValueError): NpcRosterCastingCompletionRequest(final, completion_request(moving).completion)
        with self.assertRaises(ValueError): NpcRosterDeadChampionExclusionRequest('next:death', final, final_attack())

    def test_rolled_state_is_not_fresh_input_or_an_admitted_legacy_journal_step(self):
        scenario, raw = casting_pending(); source = request(raw)
        result = roll(source, Dice((7, 7, 7)))
        with self.assertRaises(ValueError): replace(scenario, initial=result.state)
        with self.assertRaises(ValueError): validate_magic_step_policy(scenario, NpcMagicStep(result))
        self.assertIsNotNone(raw.pending_miscast)
        self.assertIsNone(raw.pending_miscast_continuation)

    def test_roll_does_not_apply_prone_create_actions_or_touch_global_rng(self):
        _, raw = casting_pending(available=True); source = request(raw)
        before = deepcopy(source.state); global_rng = getstate(); rng = Dice((7, 7, 7))
        with patch('towr.rules.miscast_effect_resolution.resolve_unnatural_wind', side_effect=AssertionError('no effect')), \
             patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no action Test')), \
             patch('random.Random', side_effect=AssertionError('no global RNG')):
            result = roll(source, rng); rng.exhausted(); final = apply(source.state, result)
        self.assertEqual(final.roster, raw.roster)
        self.assertEqual(final.round_state, raw.round_state)
        self.assertEqual(final.consumed_execution_ids, raw.consumed_execution_ids)
        self.assertEqual(final.wound_turn_end_receipts, raw.wound_turn_end_receipts)
        self.assertEqual(final.wizard.magic_state.casting_successes, 0)
        self.assertEqual(final.wizard.magic_state.miscast_dice, 3)
        self.assertEqual(source.state, before)
        self.assertEqual(getstate(), global_rng)


if __name__ == '__main__':
    unittest.main()
