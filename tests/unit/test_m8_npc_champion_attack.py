from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import random
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_m2_npc_roster_attack_execution import request as minion_request
from towr.domain.attack_models import ResilienceProfile
from towr.domain.condition_models import Condition, ConditionState, StaggerChoice
from towr.domain.infection_models import DailyWoundState
from towr.domain.injury_models import CharacterInjuryState
from towr.domain.npc_champion_attack_models import (
    NpcChampionAttackRequest, NpcChampionAttackResult, NpcChampionAttackState,
)
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.resolution_models import TargetInjuryPolicy
from tests.unit.test_k1_kernel import FixedKernelDecisions
from towr.rules.npc_champion_attack_execution import (
    apply_npc_champion_attack_result as apply, execute_npc_champion_attack as execute,
)


def request(*, selected='warbow', staggered=False):
    base = minion_request(selected=selected)
    old_target = base.state.roster.participant(base.execution.target_id)
    definition = replace(old_target.definition, id='authored:champion',
                         injury_policy=TargetInjuryPolicy.CHAMPION, wound_limit=None)
    injury = CharacterInjuryState(conditions=ConditionState(
        (Condition.STAGGERED,) if staggered else ()))
    target = replace(old_target, definition=definition,
                     state=replace(old_target.state, definition_id=definition.id, injury=injury))
    roster = NpcRoster(tuple(target if p is old_target else p for p in base.state.roster.participants))
    state = NpcChampionAttackState(roster, base.execution.state,
                                  DailyWoundState('day:1', target.state.actor_id))
    execution = replace(base.execution, kernel_request=replace(base.execution.kernel_request,
                        target_policy=TargetInjuryPolicy.CHAMPION, target_state=injury))
    return NpcChampionAttackRequest(state, base.preparation, execution)


class NpcChampionAttackTests(unittest.TestCase):
    def test_miss_and_stagger_need_no_wound_completion(self):
        for dice, expected in (((10,) * 6, False), ((1, 10, 10, 10, 10, 10), True)):
            source = request()
            rng = Mock(wraps=SequenceRandom(dice))
            result = execute(source, rng)
            self.assertEqual(rng.randint.call_count, 6)
            self.assertIsNone(result.completion)
            self.assertEqual(result.resolution.target_state.conditions.has(Condition.STAGGERED), expected)
            self.assertEqual(result.state.daily_wounds, source.state.daily_wounds)
            self.assertIsNone(result.state.pending)
            self.assertTrue(result.state.round_state.active_turn.action_slots[0].executed)

    def test_champion_wound_is_completed_once_and_not_minion_defeat(self):
        source = request(staggered=True)
        rng = Mock(wraps=SequenceRandom((1, 2, 10, 10, 10, 10, 6)))
        result = execute(source, rng)
        updated = apply(source.state, result)
        injury = updated.roster.participant(source.execution.target_id).state.injury
        self.assertEqual(rng.randint.call_count, 7)
        self.assertIsNotNone(result.execution.resolution.pending_character_wound)
        self.assertIsNone(result.resolution.pending_character_wound)
        self.assertIs(result.resolution.character_wound_completion, result.completion)
        self.assertTrue(injury.conditions.has(Condition.DRAINED))
        self.assertFalse(injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(injury.dead)
        self.assertEqual(len(injury.wounds), 1)
        self.assertTrue(injury.wounds[0].effect_resolved)
        self.assertEqual(updated.daily_wounds.wound_count, 1)
        self.assertEqual(updated.consumed_wound_roll_ids,
                         (result.execution.resolution.pending_character_wound.request_id,))
        self.assertEqual(updated.round_state.completed_turn_entity_ids, ())
        for p in source.state.roster.participants:
            if p.state.actor_id != source.execution.target_id:
                self.assertIs(updated.roster.participant(p.state.actor_id), p)

    def test_unresolved_wound_effect_keeps_full_source_and_blocks_next_attack(self):
        source = request()
        result = execute(source, SequenceRandom((1, 2, 10, 10, 10, 10, 4)))
        state = apply(source.state, result)
        self.assertTrue(result.pending_follow_ups)  # Endurance / dropped item is not silently ignored.
        self.assertIs(state.pending, result)
        self.assertEqual(state.pending.resolution.follow_ups, result.pending_follow_ups)
        with self.assertRaisesRegex(ValueError, 'pending attack follow-ups'):
            replace(source, state=state)
        with self.assertRaisesRegex(ValueError, 'pending attack differs'):
            replace(state, consumed_execution_ids=())
        with self.assertRaisesRegex(ValueError, 'drops or changes'):
            replace(result, resolution=replace(result.resolution, follow_ups=()))

    def test_repeated_stagger_retains_give_ground_or_applies_prone(self):
        for choice in (StaggerChoice.GIVE_GROUND, StaggerChoice.FALL_PRONE):
            source = request(staggered=True)
            result = execute(source, SequenceRandom((1, 10, 10, 10, 10, 10)),
                             decisions=FixedKernelDecisions(stagger=choice))
            if choice is StaggerChoice.GIVE_GROUND:
                self.assertTrue(result.pending_follow_ups)
                self.assertIs(result.state.pending, result)
            else:
                self.assertTrue(result.resolution.target_state.conditions.has(Condition.PRONE))
                self.assertIsNone(result.state.pending)

    def test_close_miss_staggers_attacker_without_escalation(self):
        source = request(selected='axe')
        result = execute(source, SequenceRandom((10,) * 6))
        self.assertTrue(result.state.roster.participant(source.execution.actor_id).state.injury.conditions.has(
            Condition.STAGGERED))
        self.assertEqual(result.pending_follow_ups, ())
        self.assertEqual(result.resolution.target_state, source.execution.kernel_request.target_state)

    def test_pure_apply_rejects_replay_and_stale_other_actor(self):
        source = request()
        before = deepcopy(source)
        result = execute(source, SequenceRandom((10,) * 6))
        global_state = random.getstate()
        with patch('towr.rules.npc_champion_attack_execution.execute_attack_action',
                   side_effect=AssertionError('no execution')), patch(
                   'towr.rules.npc_champion_attack_execution.complete_character_wound_lifecycle',
                   side_effect=AssertionError('no completion')):
            updated = apply(source.state, result)
            with self.assertRaisesRegex(ValueError, 'already consumed'):
                apply(updated, result)
        participant = source.state.roster.participants[1]
        roster = NpcRoster(tuple(replace(p, state=replace(p.state, holds_shield=True))
                                if p is participant else p for p in source.state.roster.participants))
        with self.assertRaisesRegex(ValueError, 'stale source'):
            apply(replace(source.state, roster=roster), result)
        self.assertEqual(source, before)
        self.assertEqual(random.getstate(), global_state)

    def test_admission_rejects_wrong_policy_round_and_reused_ids(self):
        source = request()
        for state in (replace(source.state, consumed_execution_ids=(source.execution.id,)),
                      replace(source.state, consumed_wound_roll_ids=(source.execution.kernel_request.id + ':wound-lifecycle',))):
            with self.assertRaisesRegex(ValueError, 'already consumed'):
                replace(source, state=state)
        with self.assertRaisesRegex(ValueError, 'kernel differs'):
            replace(source, execution=replace(source.execution, kernel_request=replace(
                source.execution.kernel_request, target_policy=TargetInjuryPolicy.PLAYER)))
        with self.assertRaisesRegex(ValueError, 'current round'):
            replace(source, state=replace(source.state, round_state=replace(source.state.round_state, round_number=2)))
        executed = execute(source, SequenceRandom((10,) * 6))
        with self.assertRaisesRegex(ValueError, 'unexecuted standard'):
            replace(source, state=replace(source.state, round_state=executed.execution.state),
                    execution=replace(source.execution, state=executed.execution.state))

    def test_admission_rejects_stale_resilience_and_target_injury(self):
        source = request()
        target = source.state.roster.participant(source.execution.target_id)
        for changed in (replace(target.state, current_resilience=ResilienceProfile(8)),
                        replace(target.state, injury=CharacterInjuryState(conditions=ConditionState((Condition.STAGGERED,))))):
            roster = NpcRoster(tuple(replace(p, state=changed) if p is target else p
                                    for p in source.state.roster.participants))
            with self.assertRaises(ValueError):
                replace(source, state=replace(source.state, roster=roster))

    def test_result_cannot_drop_completion_or_change_its_source(self):
        source = request()
        result = execute(source, SequenceRandom((1, 2, 10, 10, 10, 10, 1)))
        with self.assertRaises(TypeError):
            replace(result, completion=None)
        with self.assertRaisesRegex(ValueError, 'another source'):
            replace(result, source=replace(source, execution=replace(source.execution, id='other')))
        with self.assertRaisesRegex(ValueError, 'Wound consequences'):
            replace(result, resolution=replace(result.resolution, target_state=CharacterInjuryState()))
        with self.assertRaisesRegex(ValueError, 'Wound completion differs'):
            replace(result, source=replace(source, state=replace(source.state,
                    daily_wounds=DailyWoundState('other-day', source.execution.target_id))))

    def test_unknown_initial_conditions_are_rejected_before_execution(self):
        source = request()
        for actor_id, condition in ((source.execution.actor_id, Condition.BROKEN),
                                    (source.execution.target_id, Condition.PRONE),
                                    (source.execution.target_id, Condition.DRAINED)):
            participant = source.state.roster.participant(actor_id)
            injury = replace(participant.state.injury, conditions=ConditionState((condition,)))
            roster = NpcRoster(tuple(replace(p, state=replace(p.state, injury=injury))
                                    if p is participant else p for p in source.state.roster.participants))
            with self.assertRaisesRegex(ValueError, 'only initial Staggered'):
                replace(source, state=replace(source.state, roster=roster))

    def test_daily_history_cannot_be_detached_from_current_injury(self):
        source = request()
        result = execute(source, SequenceRandom((1, 2, 10, 10, 10, 10, 1)))
        with self.assertRaisesRegex(ValueError, 'daily Wound history'):
            replace(source.state, daily_wounds=result.state.daily_wounds)
        with self.assertRaisesRegex(ValueError, 'open daily Wound'):
            replace(source, state=replace(source.state, daily_wounds=replace(
                source.state.daily_wounds, closed_by_infection_id='closed')))

    def test_pending_result_requires_an_actual_followup_and_exact_round(self):
        source = request()
        miss = execute(source, SequenceRandom((10,) * 6))
        with self.assertRaisesRegex(ValueError, 'unresolved follow-ups'):
            replace(miss.state, pending=miss)
        pending = execute(source, SequenceRandom((1, 2, 10, 10, 10, 10, 4)))
        with self.assertRaisesRegex(ValueError, 'pending attack differs'):
            replace(pending.state, round_state=replace(pending.state.round_state, active_turn=None))

    def test_frozen_types_and_history_copy(self):
        source = request()
        ids = ['earlier']
        state = replace(source.state, consumed_execution_ids=ids)
        ids.clear()
        self.assertEqual(state.consumed_execution_ids, ('earlier',))
        for obj, name in ((source, 'state'), (state, 'roster'), (execute(source, SequenceRandom((10,) * 6)), 'source')):
            self.assertFalse(hasattr(obj, '__dict__'))
            with self.assertRaises(FrozenInstanceError):
                setattr(obj, name, None)
            with self.assertRaises(TypeError):
                replace(obj, **{name: None})
        for invalid in (('same', 'same'), (' ',)):
            with self.assertRaises(ValueError):
                replace(state, consumed_execution_ids=invalid)


if __name__ == '__main__':
    unittest.main()
