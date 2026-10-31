"""ADR-0046 standalone Prone admission, without enabling runner dispatch."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.integration.test_m8_npc_broken_recover import wounded_broken_wizard
from tests.unit.test_m8_cowardly_flight_casting_models import casting_input
from tests.unit.test_m8_npc_roster_casting import bound_request, result_for
from tests.unit.test_m8_npc_roster_prone_stand import with_injury, with_round
from tests.unit.test_m8_npc_wound_turn_end import wounded
from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    WoundConditionEffect, WoundEffectDuration, WoundEntryId, WoundRecord,
    WoundRestriction, WoundRestrictionEffect,
)
from towr.domain.npc_roster_casting_models import (
    NpcRosterCastingRequest, NpcRosterCastingResult, NpcRosterCastingTargetContext,
)
from towr.rules.npc_roster_casting_resolution import (
    apply_npc_roster_casting_result, prepare_npc_roster_casting,
)
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting


def prone(state, actor='wizard'):
    return with_injury(state, actor, lambda i: replace(
        i, conditions=i.conditions.with_condition(Condition.PRONE)))


def prepare(state, contexts=None, identifier='prone:cast'):
    template = casting_input()
    if contexts is None:
        contexts = tuple(NpcRosterCastingTargetContext(
            p.entity_id, template.targets[0].willpower_profile, False)
            for p in state.casting_round_state.participants
            if p.side is not state.round_state.active_turn.side
            and state.spatial_state.placement_for(p.entity_id).zone_id
            == state.spatial_state.placement_for(state.wizard.actor_id).zone_id)
    return prepare_npc_roster_casting(
        request_id=identifier, state=state,
        selected_zone_id=state.spatial_state.placement_for(state.wizard.actor_id).zone_id,
        targets=contexts, facts=template.facts, policy=template.policy)


def wounded_caster():
    _, _, state = wounded_broken_wizard(1)
    actor = state.wizard.actor_id
    state = with_injury(state, actor, lambda i: replace(i,
        conditions=i.conditions.without_condition(Condition.BROKEN).with_condition(Condition.PRONE)))
    turn = state.round_state.active_turn
    declaration = casting_input().round_state.active_turn.action_slots[0].declaration
    return with_round(state, replace(state.round_state, active_turn=replace(turn,
        action_slots=(replace(turn.action_slots[0], declaration=declaration),))))


class ProneCastingTests(unittest.TestCase):
    def test_prone_caster_preserves_actual_injury_and_normal_profile(self):
        state = prone(bound_request().state)
        source = prepare(state)
        self.assertIs(source.state, state)
        self.assertEqual(source.casting.caster.casting_profile, state.wizard.caster.casting_profile)
        self.assertTrue(source.state.roster.participant('wizard').state.injury.conditions.has(Condition.PRONE))

    def test_prone_caster_has_identical_casting_trace_and_no_extra_roll(self):
        state = bound_request().state
        ordinary = prepare(state)
        laying = prepare(prone(state))
        control = execute_cowardly_flight_casting(ordinary.casting, SequenceRandom((1, 10, 10)))
        actual = execute_cowardly_flight_casting(laying.casting, SequenceRandom((1, 10, 10)))
        self.assertEqual(actual, control)
        final = NpcRosterCastingResult(laying, actual).state
        self.assertTrue(final.roster.participant('wizard').state.injury.conditions.has(Condition.PRONE))
        self.assertEqual(final.spatial_state, state.spatial_state)

    def test_target_dto_admits_prone_only_with_effective_false(self):
        target = casting_input().targets[0]
        injury = replace(target.injury, conditions=target.injury.conditions.with_condition(Condition.PRONE))
        self.assertFalse(replace(target, injury=injury, can_give_ground=False).can_give_ground)
        with self.assertRaisesRegex(ValueError, 'Prone'):
            replace(target, injury=injury, can_give_ground=True)
        for bad in (0, 1, None, 'false'):
            with self.subTest(bad=bad), self.assertRaises(TypeError):
                replace(target, injury=injury, can_give_ground=bad)

    def test_helper_derives_effective_false_without_changing_context(self):
        state = prone(bound_request().state, 'second')
        profile = casting_input().targets[0].willpower_profile
        contexts = (NpcRosterCastingTargetContext('second', profile, True),
                    NpcRosterCastingTargetContext('first', profile, True))
        before = deepcopy((state, contexts))
        source = prepare(state, contexts)
        self.assertEqual(tuple(t.can_give_ground for t in source.casting.targets), (False, True))
        self.assertEqual((state, contexts), before)
        self.assertTrue(contexts[0].can_give_ground)

    def test_prone_target_can_already_have_given_ground_this_round(self):
        state = prone(bound_request().state, 'second')
        state = replace(state, spatial_state=replace(state.spatial_state, gave_ground_entity_ids=('second',)))
        profile = casting_input().targets[0].willpower_profile
        source = prepare(state, (NpcRosterCastingTargetContext('second', profile, True),
                                 NpcRosterCastingTargetContext('first', profile, False)))
        self.assertFalse(source.casting.targets[0].can_give_ground)
        self.assertEqual(source.state.spatial_state.gave_ground_entity_ids, ('second',))

    def test_other_conditions_and_broken_caster_remain_rejected(self):
        for condition in (Condition.BROKEN, Condition.DEFENCELESS, Condition.BLINDED):
            state = with_injury(prone(bound_request().state), 'wizard', lambda i: replace(
                i, conditions=i.conditions.with_condition(condition)))
            with self.subTest(condition=condition), self.assertRaisesRegex(ValueError, 'current condition'):
                prepare(state)
        target = casting_input().targets[0]
        with self.assertRaises(ValueError):
            replace(target, injury=replace(target.injury, conditions=target.injury.conditions
                .with_condition(Condition.PRONE).with_condition(Condition.BLINDED)))

    def test_standalone_prone_does_not_admit_ongoing_wound_effects(self):
        wound = WoundRecord(1, WoundEntryId.INTERNAL_INJURY, 14, (4, 10), effect_resolved=True)
        effects = (
            WoundConditionEffect(1, Condition.PRONE, WoundEffectDuration.UNTIL_REMOVED),
            WoundRestrictionEffect(1, WoundRestriction.REMOVING_PRONE_CAUSES_CRITICAL,
                                  WoundEffectDuration.UNTIL_TREATED),
            WoundConditionEffect(1, Condition.DRAINED, WoundEffectDuration.NEXT_TEST),
        )
        for effect in effects:
            state = with_injury(prone(bound_request().state), 'wizard', lambda i: replace(i,
                wounds=(wound,), active_wound_effects=(effect,),
                conditions=i.conditions.with_condition(effect.condition)
                if isinstance(effect, WoundConditionEffect) else i.conditions))
            with self.subTest(effect=effect), self.assertRaisesRegex(ValueError, 'Wound'):
                prepare(state)
        state = with_injury(prone(bound_request().state), 'wizard', lambda i: replace(
            i, wounds=(replace(wound, effect_resolved=False),)))
        with self.assertRaisesRegex(ValueError, 'Wound'):
            prepare(state)

    def test_allowed_wound_effects_are_preserved_without_prone_becoming_effect_whitelist(self):
        wound = WoundRecord(1, WoundEntryId.INTERNAL_INJURY, 14, (4, 10), effect_resolved=True)
        for condition in (Condition.STAGGERED, Condition.DRAINED):
            effect = WoundConditionEffect(1, condition, WoundEffectDuration.UNTIL_HEALED)
            state = with_injury(prone(bound_request().state), 'wizard', lambda i: replace(i,
                wounds=(wound,), active_wound_effects=(effect,), conditions=i.conditions.with_condition(condition)))
            source = prepare(state)
            final = result_for(source).state.roster.participant('wizard').state.injury
            self.assertEqual(final, state.roster.participant('wizard').state.injury)

    def test_real_stomach_expiry_and_full_history_survive_admission(self):
        state = wounded_caster()
        source = prepare(state)
        self.assertIs(source.state, state)
        self.assertTrue(source.state.wound_expiries)
        self.assertEqual(source.state.champion_attack.daily_wounds, state.champion_attack.daily_wounds)

    def test_untracked_overdue_and_future_expiry_rejected(self):
        state = wounded_caster()
        with self.assertRaisesRegex(ValueError, 'chronology'):
            prepare(replace(state, wound_expiries=()))
        combat = replace(state.round_state, round_number=state.round_state.round_number + 1)
        overdue = replace(state, round_state=combat,
            champion_attack=replace(state.champion_attack, round_state=combat),
            spatial_state=replace(state.spatial_state, round_number=combat.round_number))
        with self.assertRaisesRegex(ValueError, 'expiry'):
            prepare(overdue)
        future = replace(state, wound_expiries=wounded(completed=True).wound_expiries)
        with self.assertRaisesRegex(ValueError, 'chronology'):
            prepare(future)

    def test_prone_target_activates_full_owner_clock_guard(self):
        state = wounded_caster()
        actor = state.wizard.actor_id
        state = with_injury(state, actor, lambda i: replace(i, conditions=i.conditions.without_condition(Condition.PRONE)))
        enemy = next(p.entity_id for p in state.round_state.participants
                     if p.side is not state.round_state.active_turn.side)
        state = prone(state, enemy)
        with self.assertRaisesRegex(ValueError, 'chronology'):
            prepare(replace(state, wound_expiries=()))

    def test_live_excluded_actor_rejected_in_prone_context(self):
        state = prone(bound_request().state)
        state = with_round(state, replace(state.round_state, excluded_turn_entity_ids=('first',)))
        with self.assertRaisesRegex(ValueError, 'live excluded'):
            prepare(state)

    def test_pending_miscast_remains_blocking_and_preserves_prone(self):
        source = prepare(prone(bound_request().state))
        result = result_for(source, (9, 9, 9))
        state = result.state
        self.assertIsNotNone(state.pending_miscast)
        self.assertTrue(state.roster.participant('wizard').state.injury.conditions.has(Condition.PRONE))
        with self.assertRaisesRegex(ValueError, 'Miscast'):
            prepare(state)

    def test_target_injury_source_cannot_be_substituted(self):
        state = prone(bound_request().state, 'second')
        source = prepare(state)
        target = source.casting.targets[0]
        stripped = replace(target, injury=replace(target.injury,
            conditions=target.injury.conditions.without_condition(Condition.PRONE)))
        with self.assertRaisesRegex(ValueError, 'target injury'):
            NpcRosterCastingRequest(state, replace(source.casting, targets=(stripped, *source.casting.targets[1:])))

    def test_apply_is_full_source_exact_and_cannot_replay(self):
        source = prepare(prone(bound_request().state))
        result = result_for(source)
        final = apply_npc_roster_casting_result(source.state, result)
        with self.assertRaisesRegex(ValueError, 'consumed'):
            apply_npc_roster_casting_result(final, result)
        changed = prone(source.state, 'friend')
        with self.assertRaisesRegex(ValueError, 'stale source'):
            apply_npc_roster_casting_result(changed, result)


if __name__ == '__main__':
    unittest.main()
