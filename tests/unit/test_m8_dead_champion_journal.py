"""Closed ADR-0044 journal phases, including mandatory predecessor evidence."""
from copy import deepcopy
from dataclasses import replace
from random import getstate
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_m8_npc_magic_scenario import scenario, frame, PLAYERS, OPPOSITION
from tests.unit.test_m8_npc_magic_scenario_result import Journal
from tests.unit.test_m8_npc_magic_scenario_runner import Dice, departures
from towr.domain.npc_magic_journal_policy import (
    magic_dead_champion_exclusion_attack, validate_magic_step_predecessor,
)
from towr.domain.npc_magic_scenario_result_models import (
    NpcMagicScenarioResult, diagnose_npc_magic_unsupported,
)
from towr.domain.npc_magic_step_models import NpcMagicStep, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_dead_champion_models import NpcRosterDeadChampionExclusionRequest
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.turn_models import CombatRoundState
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario as run
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_dead_champion_resolution import exclude_npc_roster_dead_champion


def lethal_scenario(*, wizard_side=OPPOSITION, max_rounds=1, post_death_frame=True):
    """Fresh public admission, three archers and explicit live/archive frames."""
    source = scenario(wizard_side=wizard_side, perspective=wizard_side)
    old = source.initial
    enemy = old.roster.participant('enemy')
    extra = ('enemy2', 'enemy3')
    roster = NpcRoster((*old.roster.participants, *(replace(enemy,
        state=replace(enemy.state, actor_id=i)) for i in extra)))
    combat = CombatRoundState(1, roster.turn_participants)
    placement = old.spatial_state.placement_for('enemy')
    spatial = replace(old.spatial_state, placements=(*old.spatial_state.placements,
        *(replace(placement, entity_id=i) for i in extra)))
    initial = replace(old, roster=roster, round_state=combat, spatial_state=spatial,
        champion_attack=replace(old.champion_attack, roster=roster, round_state=combat))
    enemies = ('enemy', *extra)
    actors = tuple(replace(a, target_actor_ids=enemies,
        defeat_decisions=tuple(replace(a.defeat_decisions[0], target_id=i) for i in enemies))
        if a.actor_id == 'ally' else a for a in source.actors)
    actors = (*actors, *(replace(source.policy_for('enemy'), actor_id=i,
        defeat_decisions=tuple(replace(d, attacker_id=i)
            for d in source.policy_for('enemy').defeat_decisions)) for i in extra))
    all_ids = tuple(p.state.actor_id for p in roster.participants)
    frames = (frame(initial),)
    if post_death_frame:
        frames = (*frames, frame(initial, live=tuple(i for i in all_ids if i != 'wizard')))
    return departures(replace(source, initial=initial, actors=actors,
        activation_order=(*enemies, 'wizard', 'ally'), scene_frames=frames,
        objective=replace(source.objective, target_actor_ids=enemies), max_rounds=max_rounds))


def lethal_values(*, wizard_side=OPPOSITION, last=(10, 10, 5)):
    hits = ((1, 2, 3, 10, 10, 10, 1) + (1, 2, 3, 10, 10, 10, 1, 1)
            + (1, 2, 3, 10, 10, 10, *last))
    return hits + (10,) * 6 if wizard_side is OPPOSITION else (10,) * 9 + hits


def lethal_run(**kwargs):
    last = kwargs.pop('last', (10, 10, 5))
    source = lethal_scenario(**kwargs)
    dice = Dice(lethal_values(wizard_side=kwargs.get('wizard_side', OPPOSITION), last=last))
    result = run(source, dice)
    dice.exhausted()
    return result


def exclusion_index(result):
    return next(i for i, s in enumerate(result.steps)
                if isinstance(s.result.source, NpcRosterDeadChampionExclusionRequest))


def manual_lethal_journal(*, exclude=True):
    """Make the old omitted-phase chain continuous, so provenance must reject it."""
    journal = Journal(lethal_scenario())
    for actor, wound in zip(('enemy', 'enemy2', 'enemy3'), ((1,), (1, 1), (10, 10, 5))):
        journal.start(actor)
        attack = journal.shot(actor, 'wizard', (1, 2, 3, 10, 10, 10, *wound))
        if actor == 'enemy3' and exclude:
            journal.add(exclude_npc_roster_dead_champion(NpcRosterDeadChampionExclusionRequest(
                journal.id('exclusion'), journal.current, attack)))
        journal.end(actor)
    journal.start('ally'); journal.shot('ally', 'enemy'); journal.end('ally')
    return journal


def alternate_attack(attack):
    """A different genuine Test trace yielding exactly the same full post-state."""
    wound = attack.attack.completion.wound_result.table_roll.values
    actual = execute_npc_champion_attack(attack.source.attack,
        SequenceRandom((3, 2, 1, 10, 10, 10, *wound)))
    return NpcRosterChampionAttackResult(attack.source, actual)


class DeadChampionJournalTests(unittest.TestCase):
    def test_step_retains_full_source_and_attacker_identity(self):
        result = lethal_run(); index = exclusion_index(result)
        step, previous = result.steps[index], result.steps[index - 1]
        self.assertIs(step.result.source.attack, previous.result)
        self.assertEqual(step.before, previous.after)
        self.assertEqual(step.id, step.result.source.id)
        self.assertEqual(step.actor_id, 'enemy3')
        self.assertEqual(step.after.round_state.excluded_turn_entity_ids, ('wizard',))
        self.assertEqual(step.after.round_state.active_turn, step.before.round_state.active_turn)

    def test_matcher_only_requires_accepted_lethal_awaiting_attack(self):
        result = lethal_run(); index = exclusion_index(result)
        previous = result.steps[index - 1]
        self.assertIs(magic_dead_champion_exclusion_attack(previous), previous.result)
        self.assertIsNone(magic_dead_champion_exclusion_attack(None))
        for step in (result.steps[0], result.steps[index], result.steps[index + 1]):
            with self.subTest(step=step.id):
                self.assertIsNone(magic_dead_champion_exclusion_attack(step))
        superficial = next(s for s in result.steps if isinstance(s.result, NpcRosterChampionAttackResult))
        self.assertIsNone(magic_dead_champion_exclusion_attack(superficial))
        completed = lethal_run(wizard_side=PLAYERS)
        last = next(s for s in reversed(completed.steps) if isinstance(s.result, NpcRosterChampionAttackResult))
        self.assertIsNone(magic_dead_champion_exclusion_attack(last))

    def test_matching_immediate_pair_is_valid_but_standalone_exclusion_is_not(self):
        result = lethal_run(); index = exclusion_index(result)
        step, previous = result.steps[index], result.steps[index - 1]
        validate_magic_step_predecessor(previous, step)
        for wrong in (None, result.steps[0], step):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                validate_magic_step_predecessor(wrong, step)

    def test_required_phase_cannot_be_replaced_by_end_turn_or_end_of_journal(self):
        result = lethal_run(); index = exclusion_index(result)
        previous = result.steps[index - 1]
        for wrong in (None, result.steps[index + 1]):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                validate_magic_step_predecessor(previous, wrong)
        with self.assertRaises(ValueError):
            NpcMagicScenarioResult(result.source, result.steps[:index])

    def test_old_continuous_attack_end_turn_chronology_chain_is_rejected(self):
        journal = manual_lethal_journal(exclude=False)
        stop = diagnose_npc_magic_unsupported(journal.source, journal.current, journal.steps[-1].id)
        self.assertIs(stop.reason, Reason.CHRONOLOGY)
        for previous, step in zip(journal.steps, journal.steps[1:]):
            self.assertEqual(previous.after, step.before)
        with self.assertRaises(ValueError):
            journal.result(stop)

    def test_distinct_full_attack_with_equal_post_state_cannot_replace_witness(self):
        result = lethal_run(); index = exclusion_index(result)
        step, previous = result.steps[index], result.steps[index - 1]
        other = alternate_attack(previous.result)
        self.assertNotEqual(other, previous.result)
        self.assertEqual(other.state, previous.result.state)
        self.assertEqual(other.source.attack.execution.id, previous.result.source.attack.execution.id)
        changed = NpcMagicStep(replace(step.result, source=replace(step.result.source, attack=other)))
        self.assertEqual(changed.before, step.before)
        self.assertEqual(changed.after, step.after)
        with self.assertRaises(ValueError):
            validate_magic_step_predecessor(previous, changed)
        with self.assertRaises(ValueError):
            replace(result, steps=(*result.steps[:index], changed, *result.steps[index + 1:]))

    def test_phase_namespace_and_collisions_are_checked_without_changing_state(self):
        result = lethal_run(); index = exclusion_index(result); step = result.steps[index]
        for identifier in ('foreign:exclusion', result.steps[0].id):
            changed = NpcMagicStep(replace(step.result, source=replace(step.result.source, id=identifier)))
            self.assertEqual(changed.after, step.after)
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                replace(result, steps=(*result.steps[:index], changed, *result.steps[index + 1:]))

    def test_exclusion_cannot_be_repeated_or_moved_later(self):
        result = lethal_run(); index = exclusion_index(result); steps = result.steps
        for chain in ((*steps[:index + 1], steps[index], *steps[index + 1:]),
                      (*steps[:index], steps[index + 1], steps[index], *steps[index + 2:])):
            with self.assertRaises(ValueError):
                replace(result, steps=chain)

    def test_completed_target_needs_no_phase_and_cannot_precede_an_exclusion(self):
        completed = lethal_run(wizard_side=PLAYERS)
        last = next(s for s in reversed(completed.steps) if isinstance(s.result, NpcRosterChampionAttackResult))
        self.assertIn('wizard', last.after.round_state.completed_turn_entity_ids)
        validate_magic_step_predecessor(last, None)
        awaiting = lethal_run(); index = exclusion_index(awaiting)
        with self.assertRaises(ValueError):
            validate_magic_step_predecessor(last, awaiting.steps[index])
        self.assertEqual(replace(completed), completed)

    def test_valid_journal_reconstruction_is_pure(self):
        result = lethal_run(); before = deepcopy(result); global_rng = getstate()
        with (patch('towr.rules.npc_roster_dead_champion_resolution.exclude_npc_roster_dead_champion',
                    side_effect=AssertionError('no consumer replay')),
              patch('towr.rules.npc_champion_attack_execution.execute_npc_champion_attack',
                    side_effect=AssertionError('no Attack replay')),
              patch('random.Random', side_effect=AssertionError('no RNG'))):
            self.assertEqual(replace(result), result)
        self.assertEqual(result, before)
        self.assertEqual(getstate(), global_rng)


if __name__ == '__main__':
    unittest.main()
