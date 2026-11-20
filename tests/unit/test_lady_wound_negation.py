"""Real PG74/112 cancellation before effects; no NPC Fate or HP restoration."""
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.support.talent_sources import free_talent
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import (
    AdditionalProfileWound, CharacterInjuryState, CharacterWoundRequest,
    CharacterWoundType, FixedCharacterWoundRequest, ProfileInjuryState,
    ProfileNpcType, ProfileWoundRequest, ProfileDecapitationCause, WoundEntryId,
)
from towr.domain.lady_blessing_models import (
    LadyBlessingState, record_lady_prayer, record_lady_broken_gain,
)
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_lady_negation_models import (
    LADY_NEGATION_RULE_ID, LadyWoundNegationRequest, negate_lady_wound,
)
from towr.rules.injury_resolution import (
    resolve_character_wound, resolve_fixed_character_wound, resolve_profile_wound,
)


def blessing(actor='actor'):
    return record_lady_prayer(LadyBlessingState(actor,
        free_talent(TalentId.BLESSINGS_OF_THE_LADY), 'battle'), 'prayer')


class LadyWoundNegationTests(unittest.TestCase):
    def test_player_and_champion_keep_original_staggered_and_existing_wounds(self):
        earlier = resolve_character_wound(CharacterWoundRequest('old', CharacterInjuryState()),
            SequenceRandom([1])).state
        original = replace(earlier, conditions=ConditionState(frozenset((Condition.STAGGERED, Condition.DRAINED))))
        for kind in CharacterWoundType:
            with self.subTest(kind=kind):
                wound = CharacterWoundRequest('wound', original, kind)
                rolled = resolve_character_wound(wound, SequenceRandom([6, 6]))
                self.assertFalse(rolled.state.conditions.has(Condition.STAGGERED))
                result = negate_lady_wound(LadyWoundNegationRequest('cancel', 'actor', blessing(), wound, rolled))
                self.assertEqual(result.injury, original)
                self.assertEqual(result.remaining_wounds_requested, 0)
                self.assertEqual(result.blessing.negated_wound_id, 'wound')
                self.assertFalse(result.blessing.available)
                self.assertIn(LADY_NEGATION_RULE_ID, result.applied_rule_ids)
                self.assertEqual(len(rolled.state.wounds), 2)  # Source remains the actual accepted roll.

    def test_lethal_character_wound_is_cancelled_before_death_or_follow_up(self):
        wound = CharacterWoundRequest('lethal', CharacterInjuryState(), base_dice=3)
        rolled = resolve_character_wound(wound, SequenceRandom([10, 10, 10]))
        self.assertTrue(rolled.state.dead)
        result = negate_lady_wound(LadyWoundNegationRequest('cancel', 'actor', blessing(), wound, rolled))
        self.assertFalse(result.injury.dead)
        self.assertEqual(result.injury.wounds, ())
        self.assertEqual(rolled.effect_request.entry_id, WoundEntryId.DECAPITATION)

    def test_fixed_character_wound_retains_named_source_without_inventing_dice(self):
        wound = FixedCharacterWoundRequest('fixed', CharacterInjuryState(),
            WoundEntryId.SEVERED_ARM, 20, 'source:fixed')
        rolled = resolve_fixed_character_wound(wound)
        result = negate_lady_wound(LadyWoundNegationRequest('cancel', 'actor', blessing(), wound, rolled))
        self.assertEqual(result.injury, wound.state)
        self.assertEqual(result.source_request.wound_result.entry.id, WoundEntryId.SEVERED_ARM)

    def test_cancel_single_profile_wound_preserves_original_hp_and_conditions(self):
        for kind, count, limit in ((ProfileNpcType.MINION, 0, 1),
                (ProfileNpcType.BRUTE, 1, 2), (ProfileNpcType.MONSTROSITY, 2, 4)):
            with self.subTest(kind=kind):
                original = ProfileInjuryState(count, limit,
                    ConditionState(frozenset((Condition.STAGGERED, Condition.PRONE))))
                wound = ProfileWoundRequest('wound', kind, original)
                rolled = resolve_profile_wound(wound)
                result = negate_lady_wound(LadyWoundNegationRequest('cancel', 'actor', blessing(), wound, rolled))
                self.assertEqual(result.injury, original)
                self.assertEqual(result.remaining_wounds_requested, 0)
                self.assertEqual(result.injury.wounds, count)

    def test_second_simultaneous_wound_survives_even_for_one_wound_minion(self):
        for kind, limit in ((ProfileNpcType.MINION, 1), (ProfileNpcType.BRUTE, 2)):
            with self.subTest(kind=kind):
                wound = ProfileWoundRequest('double', kind, ProfileInjuryState(0, limit,
                    ConditionState(frozenset((Condition.STAGGERED,)))),
                    (AdditionalProfileWound('weapon:extra'),))
                result = negate_lady_wound(LadyWoundNegationRequest('cancel', 'actor', blessing(),
                    wound, resolve_profile_wound(wound)))
                self.assertEqual(result.remaining_wounds_requested, 1)
                self.assertEqual(result.injury.wounds, 1)
                self.assertEqual(result.injury.defeated, kind is ProfileNpcType.MINION)
                self.assertFalse(result.injury.conditions.has(Condition.STAGGERED))

    def test_cancelled_headsman_wound_does_not_leave_profile_decapitated(self):
        original = ProfileInjuryState(0, 2, ConditionState(frozenset((Condition.PRONE,))))
        wound = ProfileWoundRequest('headsman', ProfileNpcType.BRUTE, original,
            decapitation_cause=ProfileDecapitationCause('headsman', 'actor'))
        result = negate_lady_wound(LadyWoundNegationRequest('cancel', 'actor', blessing(),
            wound, resolve_profile_wound(wound)))
        self.assertEqual(result.injury, original)
        self.assertFalse(result.injury.defeated)

    def test_one_negation_cannot_remove_second_headsman_wound_or_its_death(self):
        original = ProfileInjuryState(0, 3, ConditionState(frozenset((Condition.PRONE,))))
        wound = ProfileWoundRequest('headsman', ProfileNpcType.BRUTE, original,
            (AdditionalProfileWound('weapon:extra'),),
            decapitation_cause=ProfileDecapitationCause('headsman', 'actor'))
        result = negate_lady_wound(LadyWoundNegationRequest('cancel', 'actor', blessing(),
            wound, resolve_profile_wound(wound)))
        self.assertEqual(result.injury.wounds, 1)
        self.assertTrue(result.injury.defeated)
        self.assertEqual(result.injury.defeat_cause, wound.decapitation_cause)

    def test_rejects_foreign_stale_or_already_consumed_resource(self):
        wound = CharacterWoundRequest('wound', CharacterInjuryState())
        rolled = resolve_character_wound(wound, SequenceRandom([1]))
        source = LadyWoundNegationRequest('cancel', 'actor', blessing(), wound, rolled)
        for changes in ({'target_id': 'other'}, {'wound_result': replace(rolled, request_id='other')},
                {'blessing': negate_lady_wound(source).blessing}):
            with self.subTest(changes=tuple(changes)), self.assertRaises(ValueError):
                replace(source, **changes)
        lost = record_lady_broken_gain(blessing(), 'actor', ConditionState(),
            ConditionState(frozenset((Condition.BROKEN,))))
        with self.assertRaises(ValueError):
            replace(source, blessing=lost)

    def test_cannot_hide_another_negation_or_replace_profile_result(self):
        wound = CharacterWoundRequest('wound', CharacterInjuryState())
        rolled = resolve_character_wound(wound, SequenceRandom([1]))
        with self.assertRaises(ValueError):
            LadyWoundNegationRequest('cancel', 'actor', blessing(), wound,
                replace(rolled, wound_accepted=False, negated_by_rule_id='other'))
        profile = ProfileWoundRequest('profile', ProfileNpcType.MINION, ProfileInjuryState(0, 1))
        received = resolve_profile_wound(profile)
        with self.assertRaises(ValueError):
            LadyWoundNegationRequest('cancel', 'actor', blessing(), profile,
                replace(received, applied_rule_ids=('forged',)))

    def test_result_rejects_reset_resource_restored_hp_or_extra_rule(self):
        wound = CharacterWoundRequest('wound', CharacterInjuryState())
        rolled = resolve_character_wound(wound, SequenceRandom([1]))
        result = negate_lady_wound(LadyWoundNegationRequest('cancel', 'actor', blessing(), wound, rolled))
        for changes in ({'blessing': blessing()}, {'injury': rolled.state},
                {'remaining_wounds_requested': 1}, {'applied_rule_ids': ('other',)}):
            with self.subTest(changes=tuple(changes)), self.assertRaises(ValueError):
                replace(result, **changes)
        with self.assertRaises(TypeError):
            replace(result, remaining_wounds_requested=False)

    def test_nested_profile_source_and_result_are_readmitted_with_exact_types(self):
        for coordinate in ('extra_count', 'result_hp', 'change_hp', 'rules'):
            with self.subTest(coordinate=coordinate):
                wound = ProfileWoundRequest('wound', ProfileNpcType.BRUTE,
                    ProfileInjuryState(0, 3), (AdditionalProfileWound('extra'),))
                rolled = resolve_profile_wound(wound)
                if coordinate == 'extra_count':
                    object.__setattr__(wound.additional_wounds[0], 'count', True)
                elif coordinate == 'result_hp':
                    object.__setattr__(rolled.state, 'wounds', True)
                elif coordinate == 'change_hp':
                    object.__setattr__(rolled.state_change, 'previous_wounds', False)
                else:
                    object.__setattr__(rolled, 'applied_rule_ids', ['extra'])
                with self.assertRaises((TypeError, ValueError)):
                    LadyWoundNegationRequest('cancel', 'actor', blessing(), wound, rolled)

    def test_headsman_target_must_match_actual_blessing_owner(self):
        wound = ProfileWoundRequest('headsman', ProfileNpcType.BRUTE,
            ProfileInjuryState(0, 2, ConditionState(frozenset((Condition.PRONE,)))),
            decapitation_cause=ProfileDecapitationCause('headsman', 'other'))
        with self.assertRaises(ValueError):
            LadyWoundNegationRequest('cancel', 'actor', blessing(), wound, resolve_profile_wound(wound))


if __name__ == '__main__':
    unittest.main()
