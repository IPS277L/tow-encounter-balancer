"""Fresh admitted lethal traces through the closed ADR-0044 runner phase."""
from copy import deepcopy
from dataclasses import fields, replace
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_dead_champion_journal import (
    lethal_scenario, lethal_values, lethal_run, exclusion_index,
)
from tests.unit.test_m8_npc_magic_scenario import frame, PLAYERS, OPPOSITION
from tests.unit.test_m8_npc_magic_scenario_runner import Dice, admitted, departures
from towr.domain.npc_magic_scene_models import NpcMagicSceneKey
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_dead_champion_models import NpcRosterDeadChampionExclusionResult
from towr.domain.npc_roster_turn_models import NpcRosterRoundAdvanceResult
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndResult
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario as run
from towr.rules.npc_roster_dead_champion_resolution import exclude_npc_roster_dead_champion
from towr.rules.npc_wound_turn_end import end_npc_wound_turn


def lethal_last_opposition(*, perspective):
    """Defeat the allied Minion first; the next round kills its Wizard."""
    source = lethal_scenario(max_rounds=2)
    actors = tuple(replace(a, target_actor_ids=('ally', 'wizard'))
        if a.actor_id == 'enemy' else a for a in source.actors)
    all_ids = tuple(p.state.actor_id for p in source.initial.roster.participants)
    frames = tuple(frame(source.initial, live=live) for live in (
        all_ids, tuple(i for i in all_ids if i != 'ally'),
        tuple(i for i in all_ids if i not in ('ally', 'wizard'))))
    return departures(replace(source, actors=actors, scene_frames=frames,
        perspective_side=perspective,
        objective=NpcDefeatObjective(('wizard', 'ally') if perspective is PLAYERS
                                    else ('enemy', 'enemy2', 'enemy3'))))


class DeadChampionRunnerTests(unittest.TestCase):
    def test_all_lethal_rows_publish_exclusion_before_end_without_extra_rng(self):
        for wound, total in (((8, 8, 8), 24), ((10, 10, 5), 25),
                             ((10, 10, 6), 26), ((10, 10, 10), 30)):
            with self.subTest(total=total):
                result = lethal_run(last=wound); index = exclusion_index(result)
                attack, step, ended = result.steps[index - 1:index + 2]
                self.assertIsInstance(attack.result, NpcRosterChampionAttackResult)
                self.assertIsInstance(step.result, NpcRosterDeadChampionExclusionResult)
                self.assertIsInstance(ended.result, NpcWoundTurnEndResult)
                self.assertIs(step.result.source.attack, attack.result)
                self.assertEqual(step.before.roster.participant('wizard').state.injury.wounds[-1].table_total, total)
                self.assertEqual(ended.before, step.after)
                self.assertEqual(step.after.round_state.active_turn.actor_id, 'enemy3')
                self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
                self.assertEqual((result.executed_actions, result.started_rounds, result.completed_rounds), (4, 1, 1))
                self.assertEqual(result.current.round_state.excluded_turn_entity_ids, ('wizard',))
                self.assertEqual(sum(isinstance(s.result, NpcRosterDeadChampionExclusionResult) for s in result.steps), 1)

    def test_both_sides_preserve_completed_turns_and_skip_no_op_exclusion(self):
        for side, actions, completed in ((OPPOSITION, 4, ('enemy', 'enemy2', 'enemy3', 'ally')),
                                         (PLAYERS, 5, ('wizard', 'ally', 'enemy', 'enemy2', 'enemy3'))):
            with self.subTest(side=side):
                result = lethal_run(wizard_side=side)
                self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
                self.assertEqual(result.executed_actions, actions)
                self.assertEqual(result.current.round_state.completed_turn_entity_ids, completed)
                self.assertEqual(result.current.round_state.excluded_turn_entity_ids,
                                 ('wizard',) if side is OPPOSITION else ())
                phases = tuple(s for s in result.steps if isinstance(s.result, NpcRosterDeadChampionExclusionResult))
                self.assertEqual(len(phases), int(side is OPPOSITION))

    def test_exclusion_preserves_all_other_full_owner_fields_and_input_rng(self):
        source = lethal_scenario(); before = deepcopy(source); global_rng = getstate()
        dice = Dice(lethal_values()); result = run(source, dice); dice.exhausted()
        self.assertEqual(dice.calls, 30)
        step = result.steps[exclusion_index(result)]
        for field in fields(step.before):
            if field.name not in ('round_state', 'champion_attack'):
                self.assertEqual(getattr(step.after, field.name), getattr(step.before, field.name))
        for field in fields(step.before.champion_attack):
            if field.name != 'round_state':
                self.assertEqual(getattr(step.after.champion_attack, field.name),
                                 getattr(step.before.champion_attack, field.name))
        self.assertEqual(step.after.champion_attack.round_state, step.after.round_state)
        self.assertEqual(len(result.current.roster.participants), 5)
        self.assertEqual(result.current.spatial_state.placements, source.initial.spatial_state.placements)
        self.assertEqual(result.current.champion_attack.daily_wounds.wound_count, 3)
        self.assertEqual(len(result.current.champion_attack.consumed_wound_roll_ids), 3)
        self.assertEqual(len(result.current.minion_attack.consumed_execution_ids), 1)
        self.assertEqual(source, before)
        self.assertEqual(getstate(), global_rng)

    def test_missing_post_death_frame_is_a_stop_after_exclusion_not_before(self):
        source = lethal_scenario(post_death_frame=False)
        dice = Dice(lethal_values()[:-6]); result = run(source, dice); dice.exhausted()
        self.assertEqual(dice.calls, 24)
        self.assertIs(result.outcome, Outcome.UNSUPPORTED_PATH)
        self.assertIs(result.unsupported.reason, Reason.MISSING_SCENE)
        self.assertEqual(result.unsupported.actor_id, 'ally')
        self.assertEqual(result.unsupported.required_scene_key, NpcMagicSceneKey(
            source.initial.spatial_state.placements, ('ally', 'enemy', 'enemy2', 'enemy3')))
        self.assertEqual(result.current.round_state.excluded_turn_entity_ids, ('wizard',))
        self.assertEqual(result.current.round_state.completed_turn_entity_ids, ('enemy', 'enemy2', 'enemy3'))
        self.assertEqual(len(result.current.roster.participants), 5)
        self.assertEqual((result.executed_actions, result.started_rounds, result.completed_rounds), (3, 1, 0))
        self.assertLess(exclusion_index(result), len(result.steps) - 1)

    def test_surviving_allies_continue_and_next_round_keeps_dead_archive(self):
        for side in (OPPOSITION, PLAYERS):
            source = lethal_scenario(wizard_side=side, max_rounds=2)
            dice = Dice((*lethal_values(wizard_side=side), *((10,) * 24)))
            result = run(source, dice); dice.exhausted()
            self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
            self.assertEqual(result.started_rounds, 2)
            self.assertEqual(result.completed_rounds, 2)
            self.assertEqual(result.executed_actions, 8 if side is OPPOSITION else 9)
            advances = tuple(s for s in result.steps if isinstance(s.result, NpcRosterRoundAdvanceResult))
            self.assertEqual(len(advances), 1)
            self.assertEqual(advances[0].after.round_state.excluded_turn_entity_ids, ('wizard',))
            self.assertEqual(result.current.round_state.excluded_turn_entity_ids, ('wizard',))
            self.assertEqual(result.current.spatial_state.placements, source.initial.spatial_state.placements)
            self.assertEqual(sum(isinstance(s.result, NpcRosterDeadChampionExclusionResult) for s in result.steps),
                             int(side is OPPOSITION))

    def test_terminal_objective_and_perspective_follow_exclusion_and_attacker_end(self):
        values = ((1, 2, 3, 10, 10, 10) + (1, 2, 3, 10, 10, 10, 1)
                  + (1, 2, 3, 10, 10, 10, 1, 1) + (10, 10, 10)
                  + (1, 2, 3, 10, 10, 10, 10, 10, 5))
        for side, outcome in ((PLAYERS, Outcome.OBJECTIVE_ACHIEVED), (OPPOSITION, Outcome.PERSPECTIVE_DEFEATED)):
            source = lethal_last_opposition(perspective=side); dice = Dice(values)
            result = run(source, dice); dice.exhausted()
            self.assertIs(result.outcome, outcome)
            self.assertEqual((result.executed_actions, result.started_rounds, result.completed_rounds), (5, 2, 1))
            index = exclusion_index(result)
            self.assertEqual(index, len(result.steps) - 2)
            self.assertIsInstance(result.steps[-1].result, NpcWoundTurnEndResult)
            self.assertEqual(result.current.round_state.excluded_turn_entity_ids, ('ally', 'wizard'))
            self.assertEqual(result.current.round_state.completed_turn_entity_ids, ('enemy',))

    def test_wound_pending_and_miscast_stops_do_not_trigger_exclusion(self):
        cases = ((admitted(wizard_side=OPPOSITION), (1, 2, 3, 10, 10, 10, 4), Reason.WOUND_EFFECT),
                 (admitted(), (9, 9, 9), Reason.MISCAST_PREPARATION))
        for source, values, reason in cases:
            with self.subTest(reason=reason):
                dice = Dice(values)
                with patch('towr.engine.npc_magic_scenario_runner.exclude_npc_roster_dead_champion',
                           side_effect=AssertionError('no exclusion')):
                    result = run(source, dice)
                dice.exhausted()
                self.assertIs(result.unsupported.reason, reason)
                self.assertEqual(result.executed_actions, 1)
                self.assertFalse(any(isinstance(s.result, NpcRosterDeadChampionExclusionResult) for s in result.steps))

    def test_consumer_runs_once_between_lethal_roll_and_attacker_end(self):
        source = lethal_scenario(); dice = Dice(lethal_values()); events = []
        def consume(request):
            events.append(('exclude', request.attack.attack.execution.actor_id, dice.calls))
            return exclude_npc_roster_dead_champion(request)
        def finish(request):
            events.append(('end', request.actor_id, dice.calls))
            return end_npc_wound_turn(request)
        with patch('towr.engine.npc_magic_scenario_runner.exclude_npc_roster_dead_champion', side_effect=consume) as consumer, \
             patch('towr.engine.npc_magic_scenario_runner.end_npc_wound_turn', side_effect=finish):
            result = run(source, dice)
        dice.exhausted(); self.assertEqual(consumer.call_count, 1)
        self.assertEqual(events, [('end', 'enemy', 7), ('end', 'enemy2', 15),
                                 ('exclude', 'enemy3', 24), ('end', 'enemy3', 24), ('end', 'ally', 30)])
        self.assertEqual(result.executed_actions, 4)

    def test_consumer_failure_propagates_without_retry_end_or_new_rng(self):
        source = lethal_scenario(); before = deepcopy(source); dice = Dice(lethal_values()[:-6])
        failure = ValueError('exclusion execution failed')
        with patch('towr.engine.npc_magic_scenario_runner.exclude_npc_roster_dead_champion', side_effect=failure) as consume, \
             patch('towr.engine.npc_magic_scenario_runner.end_npc_wound_turn', wraps=end_npc_wound_turn) as finish:
            with self.assertRaises(ValueError) as caught:
                run(source, dice)
        self.assertIs(caught.exception, failure)
        self.assertEqual(consume.call_count, 1)
        self.assertEqual(finish.call_count, 2)
        dice.exhausted(); self.assertEqual(source, before)


if __name__ == '__main__':
    unittest.main()
