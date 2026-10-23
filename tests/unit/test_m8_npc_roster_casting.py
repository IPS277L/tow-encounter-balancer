from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import random
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_m8_cowardly_flight_casting_models import casting_input
from towr.domain.attack_models import ResilienceProfile
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.magic_models import WizardMagicState
from towr.domain.npc_roster_casting_models import (
    NpcCastingWizardState, NpcRosterCastingRequest, NpcRosterCastingResult,
    NpcRosterCastingState,
)
from towr.domain.npc_roster_models import (
    NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcRoster,
)
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting
from towr.rules.npc_roster_casting_resolution import apply_npc_roster_casting_result as apply


def bound_request(casting=None):
    casting = casting or casting_input()
    participants = []
    for actor in casting.round_state.participants:
        wizard = actor.entity_id == casting.actor_id
        definition = NpcDefinition(
            'authored-champion' if wizard else 'authored-minion', 'authored:test',
            TargetInjuryPolicy.CHAMPION if wizard else TargetInjuryPolicy.MINION,
            None if wizard else 1, ResilienceProfile(3), (), (),
        )
        participants.append(NpcParticipantSnapshot(definition, NpcParticipantState(
            actor.entity_id, definition.id, actor.side,
            CharacterInjuryState() if wizard else ProfileInjuryState(0, 1),
            (), definition.resilience, False, False,
        )))
    return NpcRosterCastingRequest(NpcRosterCastingState(
        NpcRoster(participants),
        NpcCastingWizardState(casting.actor_id, casting.caster, casting.magic_state),
        casting.round_state, casting.spatial_state,
    ), casting)


def change_injury(state, actor_id, injury):
    return replace(state, roster=NpcRoster(tuple(
        replace(p, state=replace(p.state, injury=injury))
        if p.state.actor_id == actor_id else p for p in state.roster.participants
    )))


def result_for(request, values=(1, 10, 10)):
    return NpcRosterCastingResult(request, execute_cowardly_flight_casting(
        request.casting, SequenceRandom(values)))


class NpcRosterCastingTests(unittest.TestCase):
    def test_definition_ids_are_distinct_from_actor_and_binding_is_explicit(self):
        request = bound_request()
        wizard = request.state.wizard
        self.assertEqual(wizard.actor_id, 'wizard')
        self.assertNotEqual(wizard.actor_id, wizard.caster.id)
        self.assertNotEqual(wizard.caster.id, request.state.roster.participant('wizard').definition.id)
        with self.assertRaisesRegex(ValueError, 'Champion'):
            replace(request.state, wizard=replace(wizard, actor_id='friend'))
        with self.assertRaisesRegex(ValueError, 'unknown roster actor'):
            replace(request.state, wizard=replace(wizard, actor_id='missing'))

    def test_frozen_typed_models_copy_execution_history(self):
        request = bound_request()
        ids = ['earlier']
        state = replace(request.state, consumed_execution_ids=ids)
        ids.clear()
        self.assertEqual(state.consumed_execution_ids, ('earlier',))
        for obj in (state, state.wizard, request, result_for(request)):
            self.assertFalse(hasattr(obj, '__dict__'))
            with self.assertRaises(FrozenInstanceError):
                setattr(obj, fields(obj)[0].name, None)
        for ids, error in ((['a', 'a'], ValueError), ([' '], ValueError),
                           ([1], TypeError), ('abc', TypeError), (None, TypeError)):
            with self.subTest(ids=ids), self.assertRaises(error):
                replace(state, consumed_execution_ids=ids)
        for obj, names in ((request, ('state', 'casting')),
                           (state, ('roster', 'wizard', 'round_state', 'spatial_state')),
                           (state.wizard, ('caster', 'magic_state')),
                           (result_for(request), ('source', 'casting'))):
            for name in names:
                with self.subTest(name=name), self.assertRaises(TypeError):
                    replace(obj, **{name: None})
        for actor_id, error in (('', ValueError), (None, TypeError)):
            with self.assertRaises(error):
                replace(state.wizard, actor_id=actor_id)

    def test_storage_preserves_injury_but_request_controls_casting_admission(self):
        request = bound_request()
        state = request.state
        for injury in (CharacterInjuryState(dead=True), CharacterInjuryState(
                conditions=ConditionState((Condition.BROKEN,)))):
            changed = change_injury(state, 'wizard', injury)
            with self.assertRaisesRegex(ValueError, 'current condition'):
                replace(request, state=changed)
        changed = change_injury(state, 'first', ProfileInjuryState(1, 1, defeated=True))
        self.assertNotIn('first', tuple(p.entity_id for p in changed.casting_round_state.participants))

    def test_source_target_conditions_must_equal_roster(self):
        request = bound_request()
        changed = change_injury(request.state, 'first', ProfileInjuryState(
            0, 1, conditions=ConditionState((Condition.STAGGERED,))))
        with self.assertRaisesRegex(ValueError, 'target injury'):
            replace(request, state=changed)

    def test_roster_round_order_and_spatial_coverage_are_checked(self):
        state = bound_request().state
        with self.assertRaisesRegex(ValueError, 'ordered round'):
            replace(state, roster=NpcRoster(tuple(reversed(state.roster.participants))))
        spatial = state.spatial_state
        with self.assertRaisesRegex(ValueError, 'placements'):
            replace(state, spatial_state=replace(spatial, placements=spatial.placements[1:]))
        with self.assertRaisesRegex(ValueError, 'another round'):
            replace(state, spatial_state=replace(spatial, round_number=4))
        placement = spatial.placements[0]
        with self.assertRaisesRegex(ValueError, 'sides'):
            replace(state, spatial_state=replace(spatial, placements=(
                replace(placement, side_id=state.round_state.active_turn.side.value),
                *spatial.placements[1:])))

    def test_request_rejects_changed_magic_caster_and_spatial_sources(self):
        request = bound_request()
        state = request.state
        moved = replace(state.spatial_state, placements=tuple(
            replace(p, zone_id='empty') if p.entity_id == 'distant' else p
            for p in state.spatial_state.placements))
        for changed in (
            replace(state, wizard=replace(state.wizard, magic_state=WizardMagicState(1))),
            replace(state, wizard=replace(state.wizard, caster=replace(state.wizard.caster, id='other'))),
            replace(state, spatial_state=moved),
        ):
            with self.assertRaisesRegex(ValueError, 'actor-bound'):
                replace(request, state=changed)

    def test_result_rejects_different_request_even_when_outcome_matches(self):
        request = bound_request()
        result = result_for(request)
        other = replace(request.casting, id='other')
        with self.assertRaisesRegex(ValueError, 'complete bound request'):
            replace(result, casting=execute_cowardly_flight_casting(other, SequenceRandom((1, 10, 10))))

    def test_apply_rejects_replay_and_request_rejects_reused_execution_id(self):
        request = bound_request()
        result = result_for(request)
        updated = apply(request.state, result)
        with self.assertRaisesRegex(ValueError, 'already been consumed'):
            apply(updated, result)
        with self.assertRaisesRegex(ValueError, 'already been consumed'):
            replace(request, state=replace(request.state, consumed_execution_ids=('cast',)))

    def test_apply_rejects_changed_unaffected_actor_and_history(self):
        request = bound_request()
        result = result_for(request)
        friend = request.state.roster.participant('friend')
        roster = NpcRoster(tuple(replace(p, state=replace(p.state, holds_shield=True))
                                if p is friend else p for p in request.state.roster.participants))
        for state in (replace(request.state, roster=roster),
                      replace(request.state, consumed_execution_ids=('other',))):
            with self.assertRaisesRegex(ValueError, 'stale source'):
                apply(state, result)

    def test_pending_is_full_result_and_cannot_be_dropped_or_mismatched(self):
        request = bound_request()
        result = result_for(request, (9, 9, 9))
        state = apply(request.state, result)
        self.assertIs(state.pending_miscast, result.casting)
        self.assertEqual(state.wizard.magic_state, result.casting.magic_state)
        for changes in ({'pending_miscast': None}, {'consumed_execution_ids': ()},
                        {'wizard': replace(state.wizard, magic_state=WizardMagicState())},
                        {'pending_miscast': result_for(request).casting}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(state, **changes)
        with self.assertRaises(TypeError):
            replace(state, pending_miscast='pending')
        with self.assertRaisesRegex(ValueError, 'pending Miscast blocks'):
            NpcRosterCastingRequest(state, request.casting)
        with self.assertRaisesRegex(ValueError, 'target snapshot'):
            change_injury(state, 'first', ProfileInjuryState(
                0, 1, conditions=ConditionState((Condition.BROKEN,))))

    def test_pure_application_preserves_input_and_never_calls_rng_or_executor(self):
        request = bound_request()
        result = result_for(request)
        original, rng_state = deepcopy(request), random.getstate()
        with patch('towr.engine.cowardly_flight_casting.execute_cowardly_flight_casting',
                   side_effect=AssertionError('no execution')), patch(
                   'towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no Test')), patch(
                   'random.Random.randint', side_effect=AssertionError('no RNG')):
            updated = apply(request.state, result)
        self.assertEqual(request, original)
        self.assertEqual(random.getstate(), rng_state)
        self.assertEqual(updated.consumed_execution_ids, ('cast',))
        for state, value in ((None, result), (request.state, None)):
            with self.assertRaises(TypeError):
                apply(state, value)


if __name__ == '__main__':
    unittest.main()
