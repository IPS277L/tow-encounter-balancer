"""Actual M8 origins -> preparation -> one roll -> complete bound Wind.

Later action snapshots only verify existing Prone stops, not runner reachability.
"""
from copy import deepcopy
from dataclasses import replace
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_npc_roster_unnatural_wind import request, outside_pending, with_ally_conditions
from tests.unit.test_m8_npc_roster_miscast_preparation import casting_pending, interruption_pending
from towr.domain.condition_models import Condition
from towr.domain.npc_magic_scenario_result_models import diagnose_npc_magic_unsupported, npc_magic_terminal_outcome
from towr.domain.npc_magic_step_models import NpcMagicStep, NpcMagicPhase, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_roster_miscast_models import NpcRosterUnnaturalWindRequest
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.rules.npc_roster_miscast_resolution import resolve_npc_roster_unnatural_wind as resolve, apply_npc_roster_unnatural_wind as apply


class UnnaturalWindIntegrationTests(unittest.TestCase):
    def test_actual_casting_chain_finishes_effect_but_preserves_the_end_turn_prone_stop(self):
        source, raw = casting_pending(); wind_request = request(raw)
        result = resolve(wind_request); final = apply(wind_request.state, result)
        self.assertEqual(raw.wizard.magic_state.miscast_dice, 3)
        self.assertEqual(wind_request.state.wizard.magic_state.miscast_dice, 3)
        self.assertEqual(final.wizard.magic_state.miscast_dice, 0)
        self.assertIsNone(final.pending_miscast_continuation)
        self.assertEqual(result.source.state.pending_miscast_continuation.roll.total, 21)
        origin = result.source.state.pending_miscast_continuation.source.state.pending_miscast_continuation.source.state
        self.assertIs(origin, raw)
        stop = diagnose_npc_magic_unsupported(source, final, 'after:wind')
        self.assertIs(stop.phase, NpcMagicPhase.END_TURN)
        self.assertIs(stop.reason, Reason.END_TURN)
        self.assertEqual(stop.source_id, 'after:wind')
        self.assertIsNone(npc_magic_terminal_outcome(source, final))
        with self.assertRaisesRegex(ValueError, '(?i)unsupported.*Condition'):
            NpcWoundTurnEndRequest('end:after-wind', final, final.wizard.actor_id)

    def test_actual_bound_recover_run_origins_keep_injuries_expiries_daily_and_action_histories(self):
        for run in (False, True):
            with self.subTest(run=run):
                raw = interruption_pending(run=run); before = deepcopy(raw)
                source = request(raw); result = resolve(source); final = result.state
                origin = source.state.pending_miscast_continuation.source.state.pending_miscast_continuation.source.state
                self.assertIs(origin.pending_interruption, raw.pending_interruption)
                self.assertEqual(final.round_state, raw.round_state)
                self.assertEqual(final.spatial_state, raw.spatial_state)
                self.assertEqual(final.wound_expiries, raw.wound_expiries)
                self.assertEqual(final.wound_turn_end_receipts, raw.wound_turn_end_receipts)
                self.assertEqual(final.champion_attack.daily_wounds, raw.champion_attack.daily_wounds)
                self.assertEqual(final.champion_attack.consumed_wound_roll_ids, raw.champion_attack.consumed_wound_roll_ids)
                self.assertEqual(final.champion_attack.consumed_execution_ids, raw.champion_attack.consumed_execution_ids)
                self.assertEqual(final.consumed_execution_ids, raw.consumed_execution_ids)
                wizard_before = raw.roster.participant(raw.wizard.actor_id).state.injury
                wizard_after = final.roster.participant(raw.wizard.actor_id).state.injury
                self.assertEqual(replace(wizard_after, conditions=wizard_before.conditions), wizard_before)
                self.assertTrue(wizard_after.conditions.has(Condition.PRONE))
                self.assertEqual(final.wizard.magic_state.miscast_dice, 0)
                self.assertIsNone(final.pending_interruption)
                with self.assertRaises(ValueError): NpcWoundTurnEndRequest('end:wind', final, final.wizard.actor_id)
                self.assertEqual(raw, before)

    def test_outside_and_defeated_archives_survive_complete_effect_without_new_targets(self):
        for raw in (outside_pending()[1], casting_pending(archive=True)[1]):
            source = request(raw); result = resolve(source); final = result.state
            self.assertEqual(tuple(t.target_id for t in result.wind.targets), ('wizard', 'ally'))
            self.assertEqual(final.roster.participant('enemy'), raw.roster.participant('enemy'))
            self.assertEqual(final.spatial_state, raw.spatial_state)
            self.assertEqual(final.round_state, raw.round_state)
            self.assertEqual(final.round_state.excluded_turn_entity_ids, raw.round_state.excluded_turn_entity_ids)
            self.assertEqual(len(final.roster.participants), len(raw.roster.participants))
            self.assertEqual(final.wizard.magic_state.miscast_dice, 0)

    def test_already_prone_application_preserves_staggered_and_metadata(self):
        raw = with_ally_conditions(casting_pending()[1]); source = request(raw); result = resolve(source)
        ally = next(t for t in result.wind.targets if t.target_id == 'ally')
        self.assertEqual(ally.state, raw.roster.participant('ally').state.injury)
        self.assertIs(ally.condition_application.was_already_present, True)
        self.assertIs(ally.condition_application.blocked, False)
        self.assertEqual(ally.condition_application.request_id, source.id + ':ally:prone')
        self.assertEqual(ally.condition_application.source_rule_id, source.wind_request.source.rule_id)
        self.assertTrue(result.state.roster.participant('ally').state.injury.conditions.has(Condition.STAGGERED))

    def test_authored_later_action_snapshots_still_report_actor_and_target_prone_stops(self):
        # No scheduler is bypassed by the consumer: these explicit snapshots
        # exercise diagnosis only; automatic progression stops at END_TURN above.
        source, raw = casting_pending(); final = resolve(request(raw)).state
        combat = final.round_state
        turn = combat.active_turn
        combat = replace(combat, active_turn=replace(turn, action_slots=(replace(turn.action_slots[0], execution=None),)))
        authored = replace(final, round_state=combat, champion_attack=replace(final.champion_attack, round_state=combat))
        stop = diagnose_npc_magic_unsupported(source, authored, 'authored:next-action')
        self.assertIs(stop.phase, NpcMagicPhase.ACTION)
        self.assertIs(stop.reason, Reason.ACTOR_INJURY)
        roster = NpcRoster(tuple(replace(p, state=replace(p.state, injury=replace(p.state.injury,
            conditions=p.state.injury.conditions.without_condition(Condition.PRONE))))
            if p.state.actor_id == final.wizard.actor_id else p for p in authored.roster.participants))
        authored = replace(authored, roster=roster, champion_attack=replace(authored.champion_attack, roster=roster),
            minion_attack=replace(authored.minion_attack, roster=roster))
        stop = diagnose_npc_magic_unsupported(source, authored, 'authored:target-check')
        self.assertIs(stop.phase, NpcMagicPhase.ACTION)
        self.assertIs(stop.reason, Reason.TARGET_INJURY)
        self.assertEqual(stop.missing_actor_ids, ('enemy',))

    def test_new_result_is_not_a_closed_journal_step_or_a_fresh_input(self):
        source, raw = casting_pending(); result = resolve(request(raw))
        with self.assertRaises(TypeError): NpcMagicStep(result)
        with self.assertRaises(ValueError): replace(source, initial=result.state)
        with self.assertRaises(ValueError): NpcRosterUnnaturalWindRequest(result.source.id, result.state)
        self.assertIsNotNone(raw.pending_miscast)
        self.assertIsNone(raw.pending_miscast_continuation)

    def test_complete_wind_creates_no_new_rng_action_slot_or_receipt(self):
        _, raw = casting_pending(available=True); source = request(raw)
        before = deepcopy(source.state); global_rng = getstate()
        with patch('towr.rules.npc_roster_miscast_resolution.resolve_miscast_roll', side_effect=AssertionError('no reroll')), \
             patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no Test')), \
             patch('random.Random', side_effect=AssertionError('no RNG')):
            result = resolve(source); final = apply(source.state, result)
        self.assertEqual(source.state, before)
        self.assertEqual(getstate(), global_rng)
        self.assertEqual(final.round_state, raw.round_state)
        self.assertEqual(final.consumed_execution_ids, raw.consumed_execution_ids)
        self.assertEqual(final.wound_turn_end_receipts, raw.wound_turn_end_receipts)
        self.assertEqual(final.wizard.magic_state.miscast_dice, 0)
        self.assertEqual(final.wizard.magic_state.casting_successes, 0)
        self.assertIsNone(final.wizard.magic_state.casting_lore_id)


if __name__ == '__main__':
    unittest.main()
