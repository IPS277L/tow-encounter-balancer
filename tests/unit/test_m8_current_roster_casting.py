from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_m8_npc_roster_casting import bound_request, change_injury
from tests.unit.test_m8_npc_champion_attack import request as attack_request
from towr.domain.attack_models import ResilienceProfile
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult, NpcRosterCastingTargetContext
from towr.domain.npc_roster_models import NpcRoster
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting, apply_npc_roster_casting_result


def prepare(state, *, targets=None, request_id='current:cast'):
    original = bound_request().casting
    contexts = targets if targets is not None else tuple(NpcRosterCastingTargetContext(
        t.actor_id, t.willpower_profile, False) for t in original.targets)
    return prepare_npc_roster_casting(request_id=request_id, state=state, selected_zone_id='arena',
                                     targets=contexts, facts=original.facts, policy=original.policy)


def resolve(source, values):
    return NpcRosterCastingResult(source, execute_cowardly_flight_casting(source.casting, SequenceRandom(values)))


class CurrentRosterCastingTests(unittest.TestCase):
    def test_staggered_drained_caster_keeps_normal_profile_and_conditions(self):
        for conditions in ((Condition.STAGGERED,), (Condition.DRAINED,), (Condition.STAGGERED, Condition.DRAINED)):
            with self.subTest(conditions=conditions):
                state = change_injury(bound_request().state, 'wizard', CharacterInjuryState(
                    conditions=ConditionState(conditions)))
                source = prepare(state)
                result = resolve(source, (1, 10, 10))
                updated = apply_npc_roster_casting_result(state, result)
                self.assertEqual(result.casting.execution.casting.test.trace.final_values, (1, 10, 10))
                self.assertEqual(updated.roster.participant('wizard'), state.roster.participant('wizard'))
                self.assertEqual(updated.wizard.magic_state.casting_successes, 1)

    def test_real_stomach_wound_is_preserved_through_casting_without_expiring(self):
        attack = execute_npc_champion_attack(attack_request(), SequenceRandom((1, 2, 10, 10, 10, 10, 6)))
        injury = attack.resolution.target_state
        state = change_injury(bound_request().state, 'wizard', injury)
        result = resolve(prepare(state), (1, 10, 10))
        self.assertEqual(result.state.roster.participant('wizard').state.injury, injury)
        self.assertTrue(injury.active_wound_effects)
        self.assertTrue(injury.conditions.has(Condition.DRAINED))

    def test_wound_restrictions_are_rejected_before_rng(self):
        attack = execute_npc_champion_attack(attack_request(), SequenceRandom((1, 2, 10, 10, 10, 10, 10)))
        state = change_injury(bound_request().state, 'wizard', attack.resolution.target_state)
        with patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no roll')):
            with self.assertRaisesRegex(ValueError, 'Wound effects'):
                prepare(state)

    def test_dead_or_broken_or_defenceless_caster_is_never_admitted(self):
        for injury in (CharacterInjuryState(dead=True), *(CharacterInjuryState(
                conditions=ConditionState((c,))) for c in (Condition.BROKEN, Condition.DEFENCELESS,
                                                         Condition.BLINDED, Condition.DISTRACTED))):
            state = change_injury(bound_request().state, 'wizard', injury)
            with self.assertRaises(ValueError):
                prepare(state)

    def test_known_armour_or_shield_cannot_be_hidden_by_true_facts(self):
        original = bound_request().state
        wizard = original.roster.participant('wizard')
        for changed in (replace(wizard.state, holds_shield=True),
                        replace(wizard.state, current_resilience=ResilienceProfile(3, 1))):
            state = replace(original, roster=NpcRoster(tuple(replace(p, state=changed) if p is wizard else p
                                                             for p in original.roster.participants)))
            with self.assertRaisesRegex(ValueError, 'armour/shield'):
                prepare(state)

    def test_repeat_broken_preserves_other_conditions_and_provenance(self):
        conditions = ConditionState((Condition.STAGGERED, Condition.DRAINED, Condition.BROKEN))
        state = change_injury(bound_request().state, 'first', ProfileInjuryState(0, 1, conditions))
        result = resolve(prepare(state), (1, 2, 3, 1, 2, 3, 10, 10, 10))
        target = result.casting.willpower.targets[-1]
        self.assertFalse(target.resisted)
        self.assertTrue(target.condition_application.was_already_present)
        self.assertEqual(result.state.roster.participant('first').state.injury.conditions, conditions)
        self.assertFalse(result.state.roster.participant('first').state.injury.defeated)

    def test_resisting_curse_does_not_remove_existing_broken(self):
        state = change_injury(bound_request().state, 'first', ProfileInjuryState(
            0, 1, ConditionState((Condition.BROKEN,))))
        result = resolve(prepare(state), (1, 2, 3, 1, 2, 3, 1, 2, 3))
        self.assertTrue(result.casting.willpower.targets[-1].resisted)
        self.assertTrue(result.state.roster.participant('first').state.injury.conditions.has(Condition.BROKEN))

    def test_defeated_target_is_projected_out_but_archived_state_survives(self):
        state = change_injury(bound_request().state, 'first', ProfileInjuryState(1, 1, defeated=True))
        state = replace(state, round_state=replace(state.round_state, excluded_turn_entity_ids=('first',)))
        context = NpcRosterCastingTargetContext('second', bound_request().casting.targets[0].willpower_profile, False)
        source = prepare(state, targets=(context,))
        self.assertEqual(source.casting.round_state.excluded_turn_entity_ids, ())
        self.assertNotIn('first', [p.entity_id for p in source.casting.spatial_state.placements])
        result = resolve(source, (1, 2, 3, 10, 10, 10))
        self.assertIs(result.state.roster.participant('first'), state.roster.participant('first'))
        self.assertEqual(result.state.round_state.participants, state.round_state.participants)
        self.assertEqual(result.state.round_state.excluded_turn_entity_ids, ('first',))
        self.assertIs(result.state.spatial_state, state.spatial_state)

    def test_live_excluded_actor_remains_a_spell_target(self):
        state = bound_request().state
        state = replace(state, round_state=replace(state.round_state, excluded_turn_entity_ids=('first',)))
        source = prepare(state)
        self.assertEqual(tuple(t.actor_id for t in source.casting.targets), ('second', 'first'))

    def test_pending_miscast_uses_live_projection_but_keeps_archive(self):
        state = change_injury(bound_request().state, 'first', ProfileInjuryState(1, 1, defeated=True))
        context = NpcRosterCastingTargetContext('second', bound_request().casting.targets[0].willpower_profile, False)
        source = prepare(state, targets=(context,))
        result = resolve(source, (9, 9, 9))
        self.assertIs(result.state.pending_miscast, result.casting)
        self.assertEqual(result.state.roster, state.roster)
        with self.assertRaisesRegex(ValueError, 'pending Miscast'):
            prepare(result.state, targets=(context,))

    def test_invalid_contexts_missing_enemies_and_absent_side_are_rejected(self):
        original = bound_request()
        context = NpcRosterCastingTargetContext('second', original.casting.targets[0].willpower_profile, False)
        for targets in ((), (context,), (context, context),
                        (replace(context, actor_id='first'), context)):
            with self.subTest(targets=targets), self.assertRaises(ValueError):
                prepare(original.state, targets=targets)
        with self.assertRaises(TypeError):
            prepare(original.state, targets=('second',))
        state = original.state
        for actor in ('first', 'second', 'distant'):
            state = change_injury(state, actor, ProfileInjuryState(1, 1, defeated=True))
        with self.assertRaises(ValueError):
            prepare(state, targets=())  # No automatic victory or one-sided round fabrication.

    def test_prepare_and_apply_are_pure_and_context_is_frozen(self):
        state = bound_request().state
        source = prepare(state)
        result = resolve(source, (1, 10, 10))
        before = deepcopy(state)
        with patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no RNG')):
            self.assertEqual(prepare(state), source)
            self.assertEqual(apply_npc_roster_casting_result(state, result), result.state)
        self.assertEqual(state, before)
        context = NpcRosterCastingTargetContext('first', source.casting.targets[0].willpower_profile, False)
        with self.assertRaises(FrozenInstanceError):
            context.actor_id = 'other'


if __name__ == '__main__':
    unittest.main()
