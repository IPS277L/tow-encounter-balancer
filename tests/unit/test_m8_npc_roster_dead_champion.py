"""Source, lifetime and projection guards for the narrow ADR-0044 consumer."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from random import getstate
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.integration.test_m8_champion_casting_handoff import incoming_attack
from tests.integration.test_m8_npc_champion_attack import next_request
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundConditionEffect, WoundEffectDuration
from towr.domain.magic_models import WizardMagicState
from towr.domain.npc_roster_champion_attack_models import (
    NpcRosterChampionAttackRequest, NpcRosterChampionAttackResult,
)
from towr.domain.npc_roster_dead_champion_models import (
    NpcRosterDeadChampionExclusionRequest as Request,
    NpcRosterDeadChampionExclusionResult as Result,
)
from towr.domain.npc_roster_models import NpcRoster
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_dead_champion_resolution import (
    exclude_npc_roster_dead_champion as exclude,
    apply_npc_roster_dead_champion_exclusion as apply,
)


def final_attack(last=(10, 10, 5), *, completed=False, excluded=False):
    """Actual bound rolls; caller supplies the successive reserved round contexts.

    This helper exercises the low-level owner contract, not a scenario runner.
    The first two superficial Wounds make a three-die lethal roll possible.
    """
    source = incoming_attack()
    result = None
    for index, wound in enumerate(((1,), (1, 1), last), 1):
        if result is not None:
            raw = next_request(result.attack, index)
            old = result.state
            owner = replace(old, roster=raw.state.roster, round_state=raw.state.round_state,
                spatial_state=replace(old.spatial_state, round_number=index),
                champion_attack=raw.state)
            source = NpcRosterChampionAttackRequest(owner, raw)
        if index == 3 and (completed or excluded):
            target = source.state.wizard.actor_id
            combat = replace(source.state.round_state,
                completed_turn_entity_ids=(target,) if completed else (),
                excluded_turn_entity_ids=(target,) if excluded else ())
            champion = replace(source.attack.state, round_state=combat)
            source = replace(source, state=replace(source.state, round_state=combat,
                champion_attack=champion), attack=replace(source.attack, state=champion,
                    execution=replace(source.attack.execution, state=combat)))
        raw = execute_npc_champion_attack(source.attack,
            SequenceRandom((1, 2, 10, 10, 10, 10, *wound)))
        result = NpcRosterChampionAttackResult(source, raw)
    return result


def request(attack=None):
    attack = final_attack() if attack is None else attack
    return Request('exclude:dead-wizard', attack.state, attack)


def changed_magic(state):
    return replace(state, wizard=replace(state.wizard, magic_state=WizardMagicState()))


def changed_equipment(state):
    actor = state.roster.participants[1]
    roster = NpcRoster(tuple(replace(p, state=replace(p.state, holds_shield=True))
        if p is actor else p for p in state.roster.participants))
    return replace(state, roster=roster, champion_attack=replace(state.champion_attack, roster=roster))


def changed_completion(attack, *, injury=None, follow_ups=None):
    """Coherent ordinary dataclasses expose the weak old effect DTO boundary."""
    raw = attack.attack
    effect = raw.completion.wound_effect
    injury = raw.completion.state if injury is None else injury
    follow_ups = effect.follow_ups if follow_ups is None else follow_ups
    effect = replace(effect, state=injury, follow_ups=follow_ups)
    completion = replace(raw.completion, state=injury, wound_effect=effect)
    resolution = replace(raw.resolution, target_state=injury, wound_effect=effect,
        character_wound_completion=completion, follow_ups=(*raw.execution.resolution.follow_ups, *follow_ups))
    return replace(attack, attack=replace(raw, completion=completion, resolution=resolution))


class DeadChampionExclusionTests(unittest.TestCase):
    def test_each_lethal_row_excludes_only_the_waiting_wizard(self):
        for dice, total in (((8, 8, 8), 24), ((10, 10, 5), 25),
                            ((10, 10, 6), 26), ((10, 10, 10), 30)):
            with self.subTest(total=total):
                source = request(final_attack(dice))
                result = exclude(source)
                final = apply(source.state, result)
                target = source.state.wizard.actor_id
                self.assertIs(result.source, source)
                self.assertTrue(final.roster.participant(target).state.injury.dead)
                self.assertEqual(final.roster.participant(target).state.injury.wounds[-1].table_total, total)
                self.assertEqual(final.round_state.excluded_turn_entity_ids, (target,))
                self.assertEqual(final.round_state.completed_turn_entity_ids, ())
                self.assertEqual(final.round_state.active_turn, source.state.round_state.active_turn)

    def test_projection_preserves_every_other_root_and_champion_field(self):
        source = request(); old = source.state
        final = exclude(source).state
        for field in fields(old):
            if field.name not in ('round_state', 'champion_attack'):
                with self.subTest(owner='root', field=field.name):
                    self.assertEqual(getattr(final, field.name), getattr(old, field.name))
        for field in fields(old.champion_attack):
            if field.name != 'round_state':
                with self.subTest(owner='champion', field=field.name):
                    self.assertEqual(getattr(final.champion_attack, field.name),
                                     getattr(old.champion_attack, field.name))
        self.assertEqual(final.champion_attack.round_state, final.round_state)
        self.assertEqual(final.round_state.participants, old.round_state.participants)
        self.assertEqual(len(final.roster.participants), len(final.spatial_state.placements))

    def test_completed_and_previously_excluded_targets_are_rejected(self):
        for options in ({'completed': True}, {'excluded': True}):
            with self.subTest(options=options):
                attack = final_attack(**options)
                with self.assertRaises(ValueError): request(attack)

    def test_miss_stagger_and_nonlethal_completed_wounds_are_rejected(self):
        first = incoming_attack()
        for dice in ((10,) * 6, (1, 10, 10, 10, 10, 10), (1, 2, 10, 10, 10, 10, 1)):
            with self.subTest(dice=dice):
                attack = NpcRosterChampionAttackResult(first,
                    execute_npc_champion_attack(first.attack, SequenceRandom(dice)))
                with self.assertRaises(ValueError): request(attack)

    def test_pending_endurance_wound_cannot_be_closed_by_exclusion(self):
        attack = final_attack((1, 1, 2))
        self.assertTrue(attack.attack.pending_follow_ups)
        self.assertIsNotNone(attack.state.champion_attack.pending)
        with self.assertRaises(ValueError): request(attack)

    def test_dead_injury_with_unresolved_last_effect_is_rejected(self):
        attack = final_attack(); raw = attack.attack; old = raw.completion.state
        injury = replace(old, wounds=(*old.wounds[:-1], replace(old.wounds[-1], effect_resolved=False)))
        changed = changed_completion(attack, injury=injury)
        self.assertTrue(changed.state.roster.participant(changed.state.wizard.actor_id).state.injury.dead)
        with self.assertRaises(ValueError): request(changed)

    def test_lethal_completion_cannot_change_other_wounds_conditions_or_effects(self):
        attack = final_attack(); old = attack.attack.completion.state
        prone = old.conditions.with_condition(Condition.PRONE)
        variants = (
            replace(old, conditions=prone),
            replace(old, conditions=prone, active_wound_effects=(WoundConditionEffect(
                old.wounds[-1].sequence, Condition.PRONE, WoundEffectDuration.UNTIL_TREATED),)),
            replace(old, wounds=(replace(old.wounds[0], treated=True), *old.wounds[1:])),
        )
        for injury in variants:
            with self.subTest(injury=injury):
                changed = changed_completion(attack, injury=injury)
                self.assertTrue(changed.state.roster.participant(changed.state.wizard.actor_id).state.injury.dead)
                with self.assertRaises(ValueError): request(changed)

    def test_dead_completion_with_additional_mandatory_followup_is_rejected(self):
        pending = final_attack((1, 1, 2)).attack.pending_follow_ups
        self.assertTrue(pending)
        changed = changed_completion(final_attack(), follow_ups=pending)
        self.assertTrue(changed.state.roster.participant(changed.state.wizard.actor_id).state.injury.dead)
        self.assertIsNotNone(changed.state.champion_attack.pending)
        with self.assertRaises(ValueError): request(changed)

    def test_request_and_apply_require_the_entire_post_attack_source(self):
        source = request(); result = exclude(source)
        for changed in (changed_magic(source.state), changed_equipment(source.state),
                        replace(source.state, consumed_execution_ids=(*source.state.consumed_execution_ids, 'later')),
                        source.attack.source.state):
            with self.subTest(changed=changed.wizard.magic_state):
                with self.assertRaises(ValueError): replace(source, state=changed)
                with self.assertRaises(ValueError): apply(changed, result)

    def test_replay_rejects_a_new_phase_id_and_a_stale_result(self):
        source = request(); result = exclude(source); final = apply(source.state, result)
        with self.assertRaises(ValueError): apply(final, result)
        with self.assertRaises(ValueError): Request('different:phase', final, source.attack)
        self.assertEqual(final.consumed_execution_ids, source.state.consumed_execution_ids)
        self.assertEqual(final.round_state.active_turn.action_slots, source.state.round_state.active_turn.action_slots)

    def test_same_ids_with_changed_full_attack_source_are_rejected(self):
        source = request()
        before = changed_magic(source.attack.source.state)
        changed = replace(source.attack, source=replace(source.attack.source, state=before))
        self.assertEqual(changed.attack.execution.request_id, source.attack.attack.execution.request_id)
        with self.assertRaises(ValueError): replace(source, attack=changed)

    def test_source_and_global_rng_are_unchanged_without_any_reexecution(self):
        source = request(); before = deepcopy(source); global_rng = getstate()
        with patch('towr.rules.npc_champion_attack_execution.execute_attack_action',
                   side_effect=AssertionError('no second Attack')), patch(
                   'towr.rules.npc_champion_attack_execution.complete_character_wound_lifecycle',
                   side_effect=AssertionError('no second Wound completion')), patch(
                   'towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no Test')):
            result = exclude(source)
            self.assertEqual(apply(source.state, result), result.state)
            self.assertEqual(result.state, result.state)
        self.assertEqual(source, before)
        self.assertEqual(getstate(), global_rng)

    def test_typed_request_result_and_function_arguments(self):
        source = request(); result = exclude(source)
        for name in ('state', 'attack'):
            for value in (None, object(), 'same-id'):
                with self.subTest(name=name, value=value), self.assertRaises(TypeError):
                    replace(source, **{name: value})
        for value in (None, source.attack, 'source'):
            with self.assertRaises(TypeError): Result(value)
        for value in (None, result, source.state):
            with self.assertRaises(TypeError): exclude(value)
        for state, value in ((None, result), (source, result), (source.state, None), (source.state, source)):
            with self.assertRaises(TypeError): apply(state, value)

    def test_phase_identifier_is_nonblank_string(self):
        source = request()
        for value in ('', ' ', '\t'):
            with self.subTest(value=value), self.assertRaises(ValueError): replace(source, id=value)
        for value in (None, 1, True):
            with self.subTest(value=value), self.assertRaises(TypeError): replace(source, id=value)

    def test_models_are_frozen_slotted_and_replace_revalidates(self):
        source = request(); result = exclude(source)
        for value in (source, result):
            self.assertFalse(hasattr(value, '__dict__'))
            field = fields(value)[0].name
            with self.assertRaises(FrozenInstanceError): setattr(value, field, None)
        with self.assertRaises(ValueError): replace(source, state=exclude(source).state)
        with self.assertRaises(TypeError): replace(result, source=source.state)


if __name__ == '__main__':
    unittest.main()
