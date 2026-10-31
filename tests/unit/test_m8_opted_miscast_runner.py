"""ADR-0046 automatic bounded continuation with real, deterministic phases."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.unit.test_m8_miscast_continuation_policy import continuation_policy
from tests.unit.test_m8_npc_magic_scenario_runner import admitted, Dice
from tests.unit.test_m8_npc_roster_prone_stand import ready, with_injury
from towr.domain.condition_models import Condition
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome, NpcMagicUnsupportedReason
from towr.domain.npc_magic_scenario_result_models import diagnose_npc_magic_unsupported
from towr.domain.npc_roster_miscast_models import (
    NpcRosterMiscastPreparationResult, NpcRosterMiscastRollResult, NpcRosterUnnaturalWindResult,
)
from towr.domain.npc_roster_prone_models import NpcRosterProneStandResult, NpcRosterProneTurnEndResult
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario as run


def opted(**changes):
    return replace(admitted(), miscast_continuation=continuation_policy(), **changes)


class OptedMiscastRunnerTests(unittest.TestCase):
    def test_other_row_stops_after_one_full_pool_roll_without_cleanup(self):
        source = opted(); before = deepcopy(source); dice = Dice((9, 9, 9, 1, 1, 1))
        result = run(source, dice); dice.exhausted()
        self.assertEqual(source, before)
        self.assertEqual(result.unsupported.reason, NpcMagicUnsupportedReason.MISCAST_EFFECT)
        self.assertEqual([type(s.result) for s in result.steps[-2:]],
                         [NpcRosterMiscastPreparationResult, NpcRosterMiscastRollResult])
        self.assertEqual(result.steps[-2].origin_witness, result.steps[-3].result)
        self.assertEqual(result.current.wizard.magic_state.miscast_dice, 3)
        self.assertEqual(result.current.pending_miscast_continuation, result.steps[-1].result)
        self.assertEqual(result.unsupported.source_id, result.steps[-1].result.effect_request.resolution_id)
        self.assertEqual(result.executed_actions, 1)

    def test_wind_in_last_round_finishes_then_scoped_end_stand_and_shooting(self):
        dice = Dice((9, 9, 9, 7, 7, 7) + (10,) * 10)
        result = run(opted(max_rounds=1), dice); dice.exhausted()
        self.assertEqual(result.outcome, NpcMagicScenarioOutcome.ROUND_LIMIT_REACHED)
        winds = [s for s in result.steps if isinstance(s.result, NpcRosterUnnaturalWindResult)]
        self.assertEqual(len(winds), 1)
        self.assertEqual(winds[0].after.wizard.magic_state.miscast_dice, 0)
        self.assertTrue(all(p.state.injury.conditions.has(Condition.PRONE)
                            for p in winds[0].after.roster.participants))
        stands = [s for s in result.steps if isinstance(s.result, NpcRosterProneStandResult)]
        self.assertEqual([s.actor_id for s in stands], ['ally', 'enemy'])
        self.assertTrue(all(s.before.consumed_execution_ids == s.after.consumed_execution_ids for s in stands))
        ends = [s for s in result.steps if isinstance(s.result, NpcRosterProneTurnEndResult)]
        self.assertEqual([s.actor_id for s in ends], ['wizard'])
        self.assertEqual((result.completed_rounds, result.executed_actions), (1, 3))
        shots = [s.result.source.attack for s in result.steps if hasattr(s.result.source, 'attack')]
        self.assertEqual(len(shots), 2)
        self.assertTrue(all(not s.execution.kernel_request.can_target_leave_zone for s in shots))
        self.assertTrue(all(result.source.initial_frame.attack_departures))

    def test_stand_precedes_missing_attack_route_and_consumes_no_rng(self):
        source = opted()
        source = replace(source, scene_frames=tuple(replace(f, attack_departures=()) for f in source.scene_frames))
        dice = Dice((9, 9, 9, 7, 7, 8))
        result = run(source, dice); dice.exhausted()
        self.assertEqual(result.unsupported.reason, NpcMagicUnsupportedReason.MISSING_ROUTE)
        self.assertIsInstance(result.steps[-1].result, NpcRosterProneStandResult)
        self.assertEqual(result.steps[-1].actor_id, 'ally')
        self.assertEqual(result.executed_actions, 1)

    def test_roll_rng_exception_has_no_retry_or_effect(self):
        failure = RuntimeError('table RNG failed')
        class FailsOnTable(Dice):
            def randint(self, low, high):
                if self.calls == 3:
                    raise failure
                return super().randint(low, high)
        dice = FailsOnTable((9, 9, 9))
        with patch('towr.engine.npc_magic_scenario_runner.resolve_npc_roster_unnatural_wind') as wind:
            with self.assertRaises(RuntimeError) as caught:
                run(opted(), dice)
        self.assertIs(caught.exception, failure)
        self.assertEqual(dice.calls, 3)
        wind.assert_not_called()

    def test_effect_exception_has_no_cleanup_fallback_or_retry(self):
        failure = ValueError('effect failed'); dice = Dice((9, 9, 9, 7, 7, 7))
        with patch('towr.engine.npc_magic_scenario_runner.resolve_npc_roster_unnatural_wind',
                   side_effect=failure) as wind:
            with self.assertRaises(ValueError) as caught:
                run(opted(), dice)
        self.assertIs(caught.exception, failure); dice.exhausted()
        wind.assert_called_once()

    def test_opted_no_miscast_keeps_legacy_full_trace(self):
        source = replace(admitted(), max_rounds=1)
        legacy_dice, opted_dice = Dice((10,) * 15), Dice((10,) * 15)
        legacy = run(source, legacy_dice)
        actual = run(replace(source, miscast_continuation=continuation_policy()), opted_dice)
        self.assertEqual(actual.steps, legacy.steps)
        self.assertEqual(actual.current, legacy.current)
        legacy_dice.exhausted(); opted_dice.exhausted()

    def test_diagnosis_missing_scene_precedes_unsafe_broken_prone(self):
        state = with_injury(ready(), 'wizard', lambda injury: replace(injury,
            conditions=injury.conditions.with_condition(Condition.BROKEN)))
        source = opted()
        diagnosed = diagnose_npc_magic_unsupported(source, state, 'probe')
        self.assertEqual(diagnosed.reason, NpcMagicUnsupportedReason.BROKEN_ROUTE)
        state = replace(state, spatial_state=replace(state.spatial_state,
            placements=tuple(replace(p, zone_id='middle') if p.entity_id == 'ally' else p
                             for p in state.spatial_state.placements)))
        diagnosed = diagnose_npc_magic_unsupported(source, state, 'probe')
        self.assertEqual(diagnosed.reason, NpcMagicUnsupportedReason.MISSING_SCENE)

    def test_legacy_still_rejects_prone_actor(self):
        diagnosed = diagnose_npc_magic_unsupported(admitted(), ready(), 'probe')
        self.assertEqual(diagnosed.reason, NpcMagicUnsupportedReason.ACTOR_INJURY)

    def test_enemy_close_blocks_stand_without_inventing_stationary_shooting(self):
        from towr.domain.ranged_weapon_profiles import RangedWeaponRange
        from towr.domain.npc_magic_journal_policy import magic_prone_stand_eligible
        from tests.unit.test_m8_npc_magic_scenario import frame
        source = opted()
        state = ready('ally')
        state = replace(state, spatial_state=replace(state.spatial_state,
            placements=tuple(replace(p, zone_id='middle') if p.entity_id in ('ally', 'enemy') else p
                             for p in state.spatial_state.placements)))
        future = frame(state)
        future = replace(future, pair_ranges=tuple(
            replace(pair, target_range=RangedWeaponRange.CLOSE)
            if 'ally' in (pair.first_actor_id, pair.second_actor_id) else pair
            for pair in future.pair_ranges))
        source = replace(source, scene_frames=(*source.scene_frames, future))
        self.assertFalse(magic_prone_stand_eligible(source, state, future))
        result = diagnose_npc_magic_unsupported(source, state, 'probe')
        self.assertEqual(result.reason, NpcMagicUnsupportedReason.NO_LEGAL_TARGET)
        self.assertEqual(result.actor_id, 'ally')

    def test_diagnosis_rejects_ongoing_prone_wound_before_missing_frame(self):
        from towr.domain.injury_models import WoundConditionEffect, WoundEffectDuration, WoundRecord, WoundEntryId
        state = with_injury(ready(), 'wizard', lambda injury: replace(injury,
            wounds=(WoundRecord(1, WoundEntryId.INTERNAL_INJURY, 14, (4, 10), effect_resolved=True),),
            active_wound_effects=(WoundConditionEffect(1, Condition.PRONE, WoundEffectDuration.UNTIL_REMOVED),)))
        state = replace(state, spatial_state=replace(state.spatial_state,
            placements=tuple(replace(p, zone_id='middle') if p.entity_id == 'ally' else p
                             for p in state.spatial_state.placements)))
        diagnosed = diagnose_npc_magic_unsupported(opted(), state, 'probe')
        self.assertEqual(diagnosed.reason, NpcMagicUnsupportedReason.ACTOR_INJURY)

    def test_next_round_wizard_stands_once_and_resumes_casting(self):
        # After one Wind round all ordinary attacks missed. In round two the
        # Wizard stands, casts, and the allied shot hits the objective target.
        dice = Dice((9, 9, 9, 7, 7, 7) + (10,) * 10 + (10,) * 3 + (1, 2, 3, 10, 10, 10))
        result = run(opted(max_rounds=2), dice); dice.exhausted()
        self.assertEqual(result.outcome, NpcMagicScenarioOutcome.OBJECTIVE_ACHIEVED)
        wizard_stands = [s for s in result.steps if isinstance(s.result, NpcRosterProneStandResult)
                         and s.actor_id == 'wizard']
        self.assertEqual(len(wizard_stands), 1)
        self.assertEqual(wizard_stands[0].before.round_state.round_number, 2)
        self.assertEqual(result.executed_actions, 5)

    def test_used_free_move_preserves_prone_and_admits_stationary_casting(self):
        from towr.domain.npc_magic_journal_policy import magic_prone_stand_eligible
        state = ready()
        state = replace(state, spatial_state=replace(state.spatial_state, free_move_used_entity_ids=('wizard',)))
        source = opted()
        self.assertFalse(magic_prone_stand_eligible(source, state, source.initial_frame))
        self.assertIsNone(diagnose_npc_magic_unsupported(source, state, 'probe'))

    def test_untracked_timed_wound_is_chronology_before_stand_or_scene(self):
        from towr.domain.injury_models import WoundConditionEffect, WoundEffectDuration, WoundRecord, WoundEntryId
        state = with_injury(ready(), 'wizard', lambda injury: replace(injury,
            wounds=(WoundRecord(1, WoundEntryId.STOMACH_BLOW, 6, (6,), effect_resolved=True),),
            conditions=injury.conditions.with_condition(Condition.DRAINED),
            active_wound_effects=(WoundConditionEffect(1, Condition.DRAINED,
                WoundEffectDuration.END_OF_NEXT_TURN),)))
        diagnosed = diagnose_npc_magic_unsupported(opted(), state, 'probe')
        self.assertEqual(diagnosed.reason, NpcMagicUnsupportedReason.CHRONOLOGY)

    def test_authored_runtime_harness_dispatches_recover_and_run_origins(self):
        """Exercise orchestration, not a saved-battle API or fresh reachability.

        Only the runtime entry property is replaced with an authored Broken
        owner plus a real reserved turn. All executors and result validators
        run normally; no raw pending or effect result is fabricated.
        """
        from tests.unit.test_m8_npc_magic_scenario import ROUTE
        from towr.domain.magic_models import WizardMagicState
        from towr.domain.npc_magic_scene_models import NpcMagicBrokenPlan, NpcMagicBrokenPlanKind
        from towr.domain.npc_magic_scenario_models import NpcMagicScenario
        from towr.domain.npc_broken_recover_models import NpcBrokenRecoverResult
        from towr.domain.npc_broken_run_models import NpcBrokenRunResult
        from towr.domain.npc_roster_turn_models import NpcRosterTurnStartRequest
        from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind, ManoeuvreKind
        from towr.rules.npc_roster_turn_resolution import start_npc_roster_turn
        for running, wind in ((False, False), (True, False), (True, True)):
            with self.subTest(running=running, wind=wind):
                source = replace(admitted(blocker=True) if running else admitted(enemy_zone='middle'),
                                 miscast_continuation=continuation_policy())
                plan = NpcMagicBrokenPlan('wizard',
                    NpcMagicBrokenPlanKind.FREE_MOVE_RUN if running else NpcMagicBrokenPlanKind.SAFE_RECOVER,
                    ('middle',) if running else (), ROUTE if running else None,
                    'shelter' if running else None, ROUTE if running else None, True)
                source = replace(source, scene_frames=tuple(replace(f, broken_plans=(plan,))
                                                            for f in source.scene_frames))
                entry = with_injury(source.initial_runtime_state, 'wizard', lambda injury: replace(injury,
                    conditions=injury.conditions.with_condition(Condition.BROKEN)))
                entry = replace(entry, wizard=replace(entry.wizard,
                    magic_state=WizardMagicState(2, 1, source.spell.lore_id, 1)))
                declaration = (CombatActionDeclaration(CombatActionKind.MANOEUVRE, manoeuvre=ManoeuvreKind.RUN)
                               if running else CombatActionDeclaration(CombatActionKind.RECOVER))
                entry = start_npc_roster_turn(NpcRosterTurnStartRequest(
                    'harness:reserved', entry, 'wizard', declaration)).state
                before = deepcopy(entry)
                dice = Dice(((7, 7, 7) if wind else (1, 1, 1)) if running else (10, 10, 10, 1, 1, 1))
                with patch.object(NpcMagicScenario, 'initial_runtime_state', property(lambda self: entry)):
                    result = run(source, dice)
                dice.exhausted()
                self.assertEqual(entry, before)
                self.assertEqual(len(result.steps), 6 if wind else 3)
                self.assertIsInstance(result.steps[0].result,
                                      NpcBrokenRunResult if running else NpcBrokenRecoverResult)
                self.assertEqual(result.steps[1].origin_witness, result.steps[0].result)
                self.assertEqual(result.steps[1].result.source.state.pending_interruption,
                                 result.steps[0].result.interruption)
                self.assertEqual(result.unsupported.reason, NpcMagicUnsupportedReason.MISSING_SCENE
                                 if wind else NpcMagicUnsupportedReason.MISCAST_EFFECT)
                self.assertEqual(result.current.wizard.magic_state.miscast_dice, 0 if wind else 3)
                if wind:
                    self.assertIsInstance(result.steps[3].result, NpcRosterUnnaturalWindResult)
                    self.assertIsInstance(result.steps[4].result, NpcRosterProneTurnEndResult)
                    self.assertEqual(result.current.spatial_state.placement_for('wizard').zone_id, 'shelter')
                    self.assertTrue(result.current.roster.participant('wizard').state.injury.conditions.has(Condition.PRONE))
                self.assertEqual(result.executed_actions, 1)


if __name__ == '__main__':
    unittest.main()
