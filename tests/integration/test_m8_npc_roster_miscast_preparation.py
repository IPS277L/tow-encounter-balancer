"""Real M8 origins -> prepared full-owner pending, without table/action RNG."""
from copy import deepcopy
from dataclasses import replace
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_npc_roster_miscast_preparation import casting_pending, interruption_pending, request
from tests.unit.test_m8_npc_broken_run import request as broken_run_request
from tests.unit.test_m8_npc_roster_minion_attack import request as minion_attack_request
from tests.unit.test_m8_npc_roster_casting_completion import begin, completion_request
from tests.unit.test_m8_npc_roster_dead_champion import final_attack
from tests.integration.test_m8_champion_casting_handoff import incoming_attack
from towr.domain.npc_broken_recover_models import NpcBrokenRecoverRequest
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
    prepare_npc_roster_miscast as prepare, apply_npc_roster_miscast_preparation as apply,
)


class MiscastPreparationIntegrationTests(unittest.TestCase):
    def test_actual_defeated_archive_uses_live_casting_anchor_and_keeps_full_round(self):
        source, old = casting_pending(archive=True)
        self.assertTrue(old.roster.participant('enemy').state.injury.defeated)
        self.assertEqual(len(old.round_state.participants), 4)
        self.assertEqual(len(old.pending_miscast.round_state.participants), 3)
        self.assertEqual(old.pending_miscast.round_state, old.casting_round_state)
        self.assertEqual(old.pending_miscast.spatial_state, old.casting_spatial_state)
        result = prepare(request(old)); final = apply(old, result)
        self.assertEqual(final.round_state, old.round_state)
        self.assertEqual(final.round_state.excluded_turn_entity_ids, ('enemy',))
        self.assertEqual(final.spatial_state, old.spatial_state)
        self.assertEqual(final.roster, old.roster)
        self.assertEqual(len(final.spatial_state.placements), 4)
        self.assertEqual(final.minion_attack, old.minion_attack)
        self.assertEqual(final.champion_attack, old.champion_attack)
        self.assertIs(result.source.state.pending_miscast, old.pending_miscast)

    def test_real_wound_recover_run_origins_keep_daily_expiry_and_usage_histories(self):
        for run in (False, True):
            with self.subTest(run=run):
                old = interruption_pending(run=run)
                before = deepcopy(old)
                original = old.pending_interruption
                result = prepare(request(old)); final = result.state
                self.assertEqual(final.roster, old.roster)
                self.assertEqual(final.champion_attack.daily_wounds, old.champion_attack.daily_wounds)
                self.assertEqual(final.champion_attack.consumed_wound_roll_ids,
                                 old.champion_attack.consumed_wound_roll_ids)
                self.assertEqual(final.champion_attack.consumed_execution_ids,
                                 old.champion_attack.consumed_execution_ids)
                self.assertEqual(final.spatial_state, old.spatial_state)
                self.assertEqual(final.spatial_state.free_move_used_entity_ids, (old.wizard.actor_id,))
                self.assertEqual(final.wound_expiries, old.wound_expiries)
                self.assertEqual(final.round_state.active_turn.action_slots[0].execution, original.action)
                self.assertEqual(final.consumed_execution_ids, original.consumed_action_execution_ids)
                self.assertIsNone(final.pending_interruption)
                self.assertEqual(old, before)

    def test_prepared_prefix_reports_roll_continuation_before_end_or_terminal(self):
        source, old = casting_pending()
        result = prepare(request(old)); final = result.state
        stop = diagnose_npc_magic_unsupported(source, final, 'caller:last-id')
        self.assertIs(stop.phase, NpcMagicPhase.CONTINUATION)
        self.assertIs(stop.reason, Reason.MISCAST_ROLL)
        self.assertEqual(stop.source_id, result.roll_request.resolution_id)
        self.assertEqual(stop.actor_id, final.wizard.actor_id)
        self.assertIsNone(npc_magic_terminal_outcome(source, final))
        self.assertTrue(final.round_state.active_turn.action_slots[0].executed)
        self.assertEqual(final.wizard.magic_state.miscast_dice, 3)

    def test_bound_actions_scheduling_and_end_are_blocked_before_any_rng(self):
        source, old = casting_pending()
        result = prepare(request(old)); final = result.state
        raw = old.pending_miscast.source
        minion = minion_attack_request().attack
        champion = incoming_attack().attack
        decision = source.policy_for('ally').defeat_decisions[0]
        blocked = (
            lambda: NpcRosterCastingRequest(final, raw),
            lambda: prepare_npc_roster_casting(request_id='next:cast', state=final,
                selected_zone_id='arena', targets=(), facts=raw.facts, policy=raw.policy),
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
             patch('towr.rules.miscast_resolution.resolve_miscast_roll', side_effect=AssertionError('no table roll')), \
             patch('random.Random', side_effect=AssertionError('no RNG')):
            for operation in blocked:
                with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, '(?i)miscast'):
                    operation()

    def test_other_mandatory_consumers_cannot_bypass_prepared_prefix(self):
        _, old = casting_pending()
        final = prepare(request(old)).state
        _, _, moving, _ = begin()
        completion = completion_request(moving).completion
        lethal = final_attack()
        with self.assertRaisesRegex(ValueError, '(?i)miscast'):
            NpcRosterCastingCompletionRequest(final, completion)
        # A death source cannot legitimately coexist with a living caster's
        # prepared Miscast; the source-bound boundary still rejects it.
        with self.assertRaises(ValueError):
            NpcRosterDeadChampionExclusionRequest('next:death', final, lethal)

    def test_prepared_state_is_not_fresh_input_or_a_supported_journal_step(self):
        source, old = casting_pending()
        result = prepare(request(old)); final = result.state
        with self.assertRaisesRegex(ValueError, '(?i)prepared Miscast'):
            replace(source, initial=final)
        with self.assertRaises(TypeError): NpcMagicStep(result)

    def test_preparation_keeps_input_global_rng_and_native_action_totals(self):
        source, old = casting_pending(available=True)
        before = deepcopy(old); global_rng = getstate()
        result = prepare(request(old)); final = apply(old, result)
        self.assertEqual(old, before)
        self.assertEqual(getstate(), global_rng)
        self.assertEqual(final.consumed_execution_ids, old.consumed_execution_ids)
        self.assertEqual(final.wound_turn_end_receipts, old.wound_turn_end_receipts)
        self.assertEqual(final.round_state.completed_turn_entity_ids, old.round_state.completed_turn_entity_ids)
        self.assertEqual(final.round_state.active_turn, old.round_state.active_turn)
        self.assertIs(final.pending_miscast_continuation.source.state, old)
        self.assertEqual(diagnose_npc_magic_unsupported(source, old, 'raw').reason, Reason.MISCAST_PREPARATION)


if __name__ == '__main__':
    unittest.main()
