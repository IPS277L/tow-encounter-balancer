"""ADR-0046 source-aware stand and Prone action policy, using real results.

Authored runtime snapshots exercise the policy boundary, not fresh admission or
an imitation resumed runner. Low-level constructors retain their own guards.
"""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_m8_miscast_continuation_policy import continuation_policy
from tests.unit.test_m8_npc_magic_scenario import frame as make_frame
from tests.unit.test_m8_npc_magic_scenario_runner import admitted, departures, Dice
from tests.unit.test_m8_npc_roster_prone_stand import ready, request as stand_request, with_injury
from tests.unit.test_m8_npc_roster_prone_turn_end import request as end_request
from tests.unit.test_m8_prone_shooting import minion_state, prepare as prepare_shot, PRONE
from towr.domain.condition_models import Condition
from towr.domain.cowardly_flight_casting_models import CowardlyFlightCastingFacts
from towr.domain.npc_magic_journal_policy import (
    validate_magic_step_policy as validate, magic_prone_stand_eligible,
)
from towr.domain.npc_magic_step_models import NpcMagicStep as Step
from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult, NpcRosterCastingTargetContext
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting
from towr.rules.npc_roster_minion_attack_resolution import execute_npc_roster_minion_attack
from towr.rules.npc_roster_prone_resolution import stand_npc_roster_prone, end_npc_roster_prone_turn


def opted():
    return replace(admitted(), miscast_continuation=continuation_policy())


def spent(state):
    return replace(state, spatial_state=replace(state.spatial_state,
        free_move_used_entity_ids=(state.round_state.active_turn.actor_id,)))


def cast(source, state, *, can_move=True):
    request = prepare_npc_roster_casting(
        request_id='policy:cast', state=state,
        selected_zone_id=state.spatial_state.placement_for('enemy').zone_id,
        targets=(NpcRosterCastingTargetContext('enemy', source.policy_for('enemy').willpower_profile, can_move),),
        facts=CowardlyFlightCastingFacts(*((True,) * 12)),
        policy=source.policy_for('wizard').casting_policy)
    return Step(NpcRosterCastingResult(request, execute_cowardly_flight_casting(
        request.casting, SequenceRandom((10, 10, 10)))))


def shot(state, **facts):
    return Step(execute_npc_roster_minion_attack(prepare_shot(state, **facts), SequenceRandom((10,) * 6)))


class ProneJournalPolicyTests(unittest.TestCase):
    def test_eligible_stand_is_required_before_normal_casting(self):
        source, state = opted(), ready()
        self.assertTrue(magic_prone_stand_eligible(source, state, source.initial_frame))
        with self.assertRaisesRegex(ValueError, 'mandatory'):
            validate(source, cast(source, state))
        stood = Step(stand_npc_roster_prone(stand_request(state)))
        validate(source, stood)
        validate(source, cast(source, stood.after))
        self.assertEqual(stood.after.consumed_execution_ids, ())
        self.assertEqual(stood.after.spatial_state.free_move_used_entity_ids, ('wizard',))

    def test_eligible_stand_is_required_before_normal_shooting(self):
        source, state = opted(), minion_state(actor_prone=True)
        with self.assertRaisesRegex(ValueError, 'mandatory'):
            validate(source, shot(state))
        stood = Step(stand_npc_roster_prone(stand_request(state, actor_id='ally')))
        validate(source, stood)
        validate(source, shot(stood.after))

    def test_current_close_fact_denies_stand_without_penalizing_casting(self):
        source, state = opted(), ready()
        positions = tuple(replace(p, zone_id='middle') if p.entity_id in ('wizard', 'enemy') else p
                          for p in state.spatial_state.placements)
        state = replace(state, spatial_state=replace(state.spatial_state, placements=positions))
        future = make_frame(state)
        frame = replace(future, pair_ranges=tuple(
            replace(pair, target_range=Range.CLOSE) if 'wizard' in (pair.first_actor_id, pair.second_actor_id)
            else pair for pair in future.pair_ranges))
        source = replace(source, scene_frames=(*source.scene_frames, frame))
        self.assertFalse(magic_prone_stand_eligible(source, state, frame))
        # Low-level caller's False is not authority to override the scene.
        stood = Step(stand_npc_roster_prone(stand_request(state)))
        with self.assertRaisesRegex(ValueError, 'scene/resource'):
            validate(source, stood)
        action = cast(source, state)
        validate(source, action)
        self.assertEqual(action.result.source.casting.caster.casting_profile,
                         state.wizard.caster.casting_profile)

    def test_used_free_move_allows_stationary_prone_actions_but_not_second_stand(self):
        source = opted()
        for state, action in ((spent(ready()), cast), (spent(minion_state(actor_prone=True)), shot)):
            with self.subTest(actor=state.round_state.active_turn.actor_id):
                self.assertFalse(magic_prone_stand_eligible(source, state, source.initial_frame))
                result = action(source, state) if action is cast else action(state)
                validate(source, result)
                self.assertEqual(result.after.spatial_state.free_move_used_entity_ids,
                                 state.spatial_state.free_move_used_entity_ids)
                with self.assertRaises(ValueError):
                    stand_request(state, actor_id=state.round_state.active_turn.actor_id)

    def test_unsafe_broken_is_rejected_before_stand_even_without_enemy_close(self):
        source = opted()
        state = with_injury(ready(), 'wizard', lambda injury: replace(injury,
            conditions=injury.conditions.with_condition(Condition.BROKEN)))
        self.assertFalse(any(p.target_range is Range.CLOSE for p in source.initial_frame.pair_ranges))
        self.assertFalse(magic_prone_stand_eligible(source, state, source.initial_frame))
        # Self-stand is mechanically possible, but this technical Broken route
        # would spend the free movement needed for the unsupported escape.
        stood = Step(stand_npc_roster_prone(stand_request(state)))
        with self.assertRaisesRegex(ValueError, 'unsafe Broken'):
            validate(source, stood)

    def test_stand_needs_exact_current_frame_even_when_old_frame_was_safe(self):
        source, state = opted(), ready()
        positions = tuple(replace(p, zone_id='middle') if p.entity_id == 'enemy' else p
                          for p in state.spatial_state.placements)
        state = replace(state, spatial_state=replace(state.spatial_state, placements=positions))
        stood = Step(stand_npc_roster_prone(stand_request(state)))
        with self.assertRaisesRegex(ValueError, 'current scene frame'):
            validate(source, stood)

    def test_legacy_rejects_actual_prone_actions_targets_stand_and_end(self):
        legacy, source = admitted(), opted()
        target = with_injury(ready(), 'enemy', lambda injury: replace(injury,
            conditions=injury.conditions.with_condition(Condition.PRONE)))
        target = with_injury(target, 'wizard', lambda injury: replace(injury,
            conditions=injury.conditions.without_condition(Condition.PRONE)))
        steps = (cast(source, spent(ready())), cast(source, target),
                 shot(spent(minion_state(actor_prone=True))), shot(minion_state(target_prone=True)),
                 Step(stand_npc_roster_prone(stand_request())),
                 Step(end_npc_roster_prone_turn(end_request())))
        for step in steps:
            with self.subTest(result=type(step.result)), self.assertRaisesRegex(ValueError, 'Prone'):
                validate(legacy, step)

    def test_prone_end_is_admitted_without_new_action_or_condition_removal(self):
        source = opted()
        step = Step(end_npc_roster_prone_turn(end_request()))
        validate(source, step)
        self.assertEqual(step.after.roster, step.before.roster)
        self.assertEqual(step.after.consumed_execution_ids, step.before.consumed_execution_ids)

    def test_prone_shooting_target_uses_one_modifier_and_overrides_authored_departure(self):
        state = minion_state(target_prone=True)
        action = shot(state)
        request = action.result.source.attack
        self.assertEqual(request.preparation.npc_attack.source_request.dice_modifiers, (PRONE,))
        self.assertFalse(request.execution.kernel_request.can_target_leave_zone)
        for can_leave in (False, True):
            source = departures(opted(), can_leave=can_leave)
            before = deepcopy(source)
            validate(source, action)
            self.assertEqual(source, before)

    def test_prone_shooter_does_not_hide_healthy_target_departure_mismatch(self):
        source = opted()
        action = shot(spent(minion_state(actor_prone=True)), can_target_leave_zone=False)
        with self.assertRaisesRegex(ValueError, 'departure'):
            validate(source, action)
        validate(departures(source, can_leave=False), action)

    def test_prone_target_still_requires_exact_scene_range(self):
        source = opted()
        action = shot(minion_state(target_prone=True), target_range=Range.MEDIUM)
        with self.assertRaisesRegex(ValueError, 'facts differ'):
            validate(source, action)

    def test_full_journal_cannot_remove_required_attack_departure_facts(self):
        source = replace(opted(), max_rounds=1)
        dice = Dice((9, 9, 9, 7, 7, 7) + (10,) * 10)
        actual = run_npc_magic_scenario(source, dice)
        dice.exhausted()
        missing = replace(source, scene_frames=tuple(replace(frame, attack_departures=())
                                                    for frame in source.scene_frames))
        with self.assertRaisesRegex(ValueError, 'departure'):
            NpcMagicScenarioResult(missing, actual.steps)

    def test_curse_uses_actual_prone_without_rewriting_authored_give_ground(self):
        source = opted()
        state = with_injury(ready(), 'wizard', lambda injury: replace(injury,
            conditions=injury.conditions.without_condition(Condition.PRONE)))
        state = with_injury(state, 'enemy', lambda injury: replace(injury,
            conditions=injury.conditions.with_condition(Condition.PRONE)))
        before = deepcopy(source)
        action = cast(source, state, can_move=True)
        self.assertTrue(source.initial_frame.give_ground_plans[0].can_leave_zone)
        self.assertFalse(action.result.source.casting.targets[0].can_give_ground)
        validate(source, action)
        self.assertEqual(source, before)
        healthy = with_injury(state, 'enemy', lambda injury: replace(injury,
            conditions=injury.conditions.without_condition(Condition.PRONE)))
        with self.assertRaisesRegex(ValueError, 'target facts'):
            validate(source, cast(source, healthy, can_move=False))


if __name__ == '__main__':
    unittest.main()
