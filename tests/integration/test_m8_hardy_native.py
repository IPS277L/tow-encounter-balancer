"""Hardy ownership reaches the real M8 Champion Attack and full journal."""
from copy import deepcopy
from dataclasses import replace
from random import getstate
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.talent_sources import free_talent, paid_talent
from tests.unit.test_m8_npc_magic_scenario import OPPOSITION, scenario, transform_actor
from tests.unit.test_m8_npc_magic_scenario_runner import departures
from towr.domain.injury_models import CharacterWoundType
from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_injury_models import HARDY_RULE_ID
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario


def source_with_hardy(talent):
    # The opposing Wizard is the first real Attack target. The other two
    # actors and all policies/scene facts retain the ordinary M8 source.
    source = scenario(wizard_side=OPPOSITION)
    initial = transform_actor(source.initial, 'wizard', lambda participant: replace(participant,
        definition=replace(participant.definition, talents=() if talent is None else (talent,))))
    return departures(replace(source, initial=initial, max_rounds=1))


def incoming_script(table_values):
    # Enemy's Shooting: two successes; Wizard's Athletics: zero. Then the
    # actual Wounds Table, failed Casting, and the ally's missed Attack.
    return (1, 1, 10, 10, 10, 10, *table_values, *(10,) * 9)


def incoming_champion_attack(result):
    attacks = tuple(step.result.attack for step in result.steps
        if isinstance(step.result, NpcRosterChampionAttackResult))
    if len(attacks) != 1:
        raise AssertionError('expected exactly one actual incoming Champion Attack')
    return attacks[0]


class M8HardyNativeTests(unittest.TestCase):
    def test_paid_and_creation_free_sources_reach_actual_wound_once(self):
        for acquire in (paid_talent, free_talent):
            with self.subTest(acquisition=acquire.__name__):
                talent = acquire(TalentId.HARDY)
                source = source_with_hardy(talent)
                before, global_rng = deepcopy(source), getstate()
                rng = ScriptedD10(incoming_script((2,)))
                result = run_npc_magic_scenario(source, rng)
                rng.assert_exhausted()
                self.assertEqual(rng.index, 16)
                self.assertIs(result.outcome, NpcMagicScenarioOutcome.ROUND_LIMIT_REACHED)
                self.assertIsNone(result.unsupported)
                self.assertIs(result.source, source)
                self.assertEqual(source, before)
                self.assertEqual(getstate(), global_rng)

                attack = incoming_champion_attack(result)
                self.assertEqual(attack.execution.actor_id, 'enemy')
                self.assertEqual(attack.execution.target_id, 'wizard')
                modifiers = attack.source.execution.kernel_request.wound_dice_modifiers
                self.assertEqual(tuple((value.rule_id, value.amount) for value in modifiers),
                    ((HARDY_RULE_ID, -1),))
                roll = attack.execution.resolution.pending_character_wound
                self.assertIsNotNone(roll)
                self.assertIs(roll.source_request.wound.subject_type, CharacterWoundType.CHAMPION)
                self.assertEqual(roll.source_request.wound.dice_modifiers, modifiers)
                self.assertEqual(roll.wound_result.table_roll.dice, 1)
                self.assertEqual(roll.wound_result.table_roll.values, (2,))
                self.assertEqual(attack.completion.source_request.roll, roll)
                self.assertIsNone(attack.resolution.pending_character_wound)

                current = result.current
                wizard = current.roster.participant('wizard')
                self.assertEqual(wizard.definition.talents, (talent,))
                self.assertEqual(wizard.state.injury.wounds[0].roll_values, (2,))
                self.assertEqual(len(wizard.state.injury.wounds), 1)
                self.assertEqual(current.champion_attack.daily_wounds.wound_count, 1)
                self.assertEqual(current.champion_attack.consumed_wound_roll_ids, (roll.request_id,))
                self.assertEqual(current.champion_attack.roster, current.roster)
                self.assertEqual(len(result.steps), 9)
                self.assertEqual(result.executed_actions, 3)

    def test_removing_hardy_changes_real_table_draws_without_changing_attack_tests(self):
        # The first Wound already has the minimum one die. A second genuine
        # incoming Wound normally rolls two; Hardy now reduces it to one.
        ordinary_rng = ScriptedD10(incoming_script((1,)) + incoming_script((1, 1)))
        hardy_rng = ScriptedD10(incoming_script((1,)) + incoming_script((1,)))
        ordinary = run_npc_magic_scenario(replace(source_with_hardy(None), max_rounds=2), ordinary_rng)
        hardy = run_npc_magic_scenario(replace(source_with_hardy(paid_talent(TalentId.HARDY)),
            max_rounds=2), hardy_rng)
        ordinary_rng.assert_exhausted()
        hardy_rng.assert_exhausted()
        plain_attacks, hardy_attacks = tuple(tuple(step.result.attack for step in result.steps
            if isinstance(step.result, NpcRosterChampionAttackResult)) for result in (ordinary, hardy))
        self.assertEqual(len(plain_attacks), 2)
        self.assertEqual(len(hardy_attacks), 2)
        plain_attack, hardy_attack = plain_attacks[1], hardy_attacks[1]
        self.assertEqual(ordinary_rng.index, 33)
        self.assertEqual(hardy_rng.index, 32)
        self.assertEqual(plain_attacks[0].execution.resolution.pending_character_wound.wound_result.table_roll.values,
            (1,))
        self.assertEqual(plain_attack.execution.resolution.attack, hardy_attack.execution.resolution.attack)
        self.assertEqual(plain_attack.execution.resolution.pending_character_wound.wound_result.table_roll.values,
            (1, 1))
        self.assertEqual(hardy_attack.execution.resolution.pending_character_wound.wound_result.table_roll.values,
            (1,))
        self.assertEqual(plain_attack.source.execution.kernel_request.wound_dice_modifiers, ())
        for result in (ordinary, hardy):
            self.assertIs(result.outcome, NpcMagicScenarioOutcome.ROUND_LIMIT_REACHED)
            self.assertEqual(result.current.champion_attack.daily_wounds.wound_count, 2)

    def test_full_journal_rebuild_retains_source_and_rejects_substitution_or_repeated_step(self):
        source = source_with_hardy(paid_talent(TalentId.HARDY))
        rng = ScriptedD10(incoming_script((2,)))
        result = run_npc_magic_scenario(source, rng)
        rng.assert_exhausted()
        replay = NpcMagicScenarioResult(source, result.steps, result.unsupported)
        self.assertEqual(replay, result)
        self.assertEqual(replay.current, result.current)
        previous = source.initial_runtime_state
        for step in replay.steps:
            self.assertEqual(step.before, previous)
            previous = step.after
        self.assertEqual(previous, replay.current)
        with self.assertRaisesRegex(ValueError, 'continuous full-owner source chain'):
            replace(result, source=source_with_hardy(None))
        with self.assertRaises(ValueError):
            replace(result, steps=(*result.steps[:2], result.steps[1], *result.steps[2:]))
        self.assertEqual(rng.index, 16)


if __name__ == '__main__':
    unittest.main()
